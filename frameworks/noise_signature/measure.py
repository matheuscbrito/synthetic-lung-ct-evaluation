"""Plano de medida (regiões, ROIs, blocos) e leituras por ROI de uma imagem.

O plano é feito numa imagem e aplicado às duas: no modo mesma anatomia ele vem
da real, de modo que real e sintética são medidas nos mesmos pixels e o
bootstrap pode reamostrar as mesmas ROIs nos dois lados. No modo só máscara
cada imagem tem o seu plano.

Uma "leitura" de imagem (`side`) é um dicionário prefixo → grupos de unidades;
cada grupo é um dicionário de matrizes com uma linha por ROI ou bloco. As
técnicas (`TECHNIQUES`) transformam grupos em métricas.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from .fingerprint import METRICS as T2_METRICS, roi_units, t2_metrics
from .noise_level import METRICS as T3_METRICS, filter_maps, roi_levels, t3_metrics
from .nps import MIN_ROIS, ROI_SIZE, RoiSet, roi_features, select_rois, shape_dist, t1_metrics
from .regions import REGION_NAMES, Regions, build_regions
from .residual import DENOISERS, residual
from .stationarity import METRICS as T4_METRICS, Blocks, block_units, select_blocks, t4_metrics

T1_METRICS = ("sigma", "f_peak", "f_avg", "anisotropy")
PAIR_METRICS = {"t1_lung": "shape_dist", "t1_soft": "shape_dist"}


@dataclass
class Plan:
    regions: Regions
    rois: dict[str, RoiSet]
    t1_keep: dict[str, np.ndarray]     # ROIs sem vazamento de anatomia (na imagem do plano)
    blocks: Blocks


def make_plan(image: np.ndarray, lung_mask: np.ndarray) -> Plan:
    regions = build_regions(image, lung_mask)
    rois = {name: select_rois(regions.get(name).host, regions.get(name).strict, ROI_SIZE[name]) for name in REGION_NAMES}
    keep = {name: ~roi_features(image, rois[name])["leak"] for name in REGION_NAMES}
    return Plan(regions, rois, keep, select_blocks(regions.host_union))


def measure(image: np.ndarray, plan: Plan, sigma0: float) -> dict:
    """Todas as leituras por ROI/bloco de uma imagem, no plano dado."""
    maps = filter_maps(image)
    side: dict = {}
    for name in REGION_NAMES:
        rois, strict = plan.rois[name], plan.regions.get(name).strict
        features = roi_features(image, rois)
        side[f"leak_{name}"] = float(features["leak"].mean()) if len(rois) else float("nan")
        side[f"t1_{name}"] = {"roi": {key: value[plan.t1_keep[name]] for key, value in features.items()}}
        side[f"t3_{name}"] = {"roi": {"roi": roi_levels(image, strict, rois, maps)}}
    for kind in DENOISERS:
        res = residual(image, kind, sigma0)
        side[f"t2_{kind}"] = {
            "lung": roi_units(res, plan.rois["lung"], plan.regions.lung.strict, spectral=True),
            "soft": roi_units(res, plan.rois["soft"], plan.regions.soft.strict, spectral=False),
        }
    side["t4"] = {"blocks": {"map": block_units(image, plan.blocks)}, "lung": side["t3_lung"]["roi"], "soft": side["t3_soft"]["roi"]}
    return side


@dataclass(frozen=True)
class Technique:
    metrics: tuple
    compute: Callable[[dict, dict], dict]
    required: tuple                  # grupos que precisam de ≥ MIN_ROIS linhas


def _t2(kind: str) -> Callable[[dict, dict], dict]:
    def compute(groups: dict, ctx: dict) -> dict:
        reference = ctx.get("fingerprint", {}).get(kind)
        return t2_metrics(groups, None if reference is None else np.asarray(reference), ctx.get("lsd_norm", {}).get(kind, 1.0))
    return compute


TECHNIQUES: dict[str, Technique] = {
    "t1_lung": Technique(T1_METRICS, lambda g, ctx: t1_metrics(g["roi"], ROI_SIZE["lung"]), ("roi",)),
    "t1_soft": Technique(T1_METRICS, lambda g, ctx: t1_metrics(g["roi"], ROI_SIZE["soft"]), ("roi",)),
    "t2_wiener": Technique(T2_METRICS, _t2("wiener"), ("lung",)),
    "t2_median": Technique(T2_METRICS, _t2("median"), ("lung",)),
    "t3_lung": Technique(T3_METRICS, lambda g, ctx: t3_metrics(g["roi"]), ("roi",)),
    "t3_soft": Technique(T3_METRICS, lambda g, ctx: t3_metrics(g["roi"]), ("roi",)),
    "t4": Technique(T4_METRICS, lambda g, ctx: t4_metrics(g), ()),
}


def group_size(arrays: dict) -> int:
    return len(next(iter(arrays.values())))


def compute_metrics(prefix: str, groups: dict, ctx: dict, min_units: int = MIN_ROIS) -> dict:
    """Métricas de uma técnica; com poucas ROIs nos grupos exigidos, tudo NaN (inconclusivo)."""
    technique = TECHNIQUES[prefix]
    if any(group_size(groups[name]) < min_units for name in technique.required):
        return {name: float("nan") for name in technique.metrics}
    return technique.compute(groups, ctx)


def pair_metric(prefix: str, real: dict, synthetic: dict, min_units: int = MIN_ROIS) -> float:
    """Métrica de forma do par (shape_dist) entre duas leituras T1."""
    if group_size(real["roi"]) < min_units or group_size(synthetic["roi"]) < min_units:
        return float("nan")
    return shape_dist(real["roi"], synthetic["roi"])
