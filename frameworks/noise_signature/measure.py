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
from .decision import bootstrap
from .nps import MIN_ROIS, ROI_SIZE, RoiSet, leak_keep, roi_features, select_rois, shape_dist, t1_metrics
from .regions import REGION_NAMES, Regions, build_regions
from .residual import DENOISERS, residual
from .stationarity import METRICS as T4_METRICS, Blocks, block_units, select_blocks, t4_metrics

T1_METRICS = ("sigma", "f_peak", "f_avg", "anisotropy", "acf_len")
# métricas do par (comparam duas leituras T1): forma do NPS e razão de σ (log)
PAIR_METRICS = {"t1_lung": ("shape_dist", "sigma_ratio"), "t1_soft": ("shape_dist", "sigma_ratio")}


@dataclass
class Plan:
    regions: Regions
    rois: dict[str, RoiSet]
    t1_keep: dict[str, np.ndarray]     # ROIs sem vazamento de anatomia (na imagem do plano)
    blocks: Blocks
    t1_fallback: dict[str, bool]       # True: poucas ROIs sem vazamento; ficou a metade que menos vaza


def make_plan(image: np.ndarray, lung_mask: np.ndarray) -> Plan:
    regions = build_regions(image, lung_mask)
    rois = {name: select_rois(regions.get(name).host, regions.get(name).strict, ROI_SIZE[name]) for name in REGION_NAMES}
    keep, fallback = {}, {}
    for name in REGION_NAMES:
        keep[name], fallback[name] = leak_keep(roi_features(image, rois[name]))
    return Plan(regions, rois, keep, select_blocks(regions.host_union), fallback)


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
        return t2_metrics(groups, None if reference is None else np.asarray(reference), ctx.get("lsd_norm", {}).get(kind, 1.0),
                          ctx.get("min_units", MIN_ROIS))
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
    return technique.compute(groups, {**ctx, "min_units": min_units})


def pair_metric(prefix: str, name: str, real: dict, synthetic: dict, min_units: int = MIN_ROIS) -> float:
    """Métrica do par entre duas leituras T1: `shape_dist` ou `sigma_ratio` = log(σ_sint/σ_real)."""
    if group_size(real["roi"]) < min_units or group_size(synthetic["roi"]) < min_units:
        return float("nan")
    if name == "shape_dist":
        return shape_dist(real["roi"], synthetic["roi"])
    if name == "sigma_ratio":
        size = ROI_SIZE[prefix.split("_")[1]]
        a, b = t1_metrics(real["roi"], size)["sigma"], t1_metrics(synthetic["roi"], size)["sigma"]
        return float(np.log(b / a)) if a > 0 and b > 0 else float("nan")
    raise ValueError(name)


def metric_names(prefix: str) -> tuple:
    """Métricas de uma técnica, mais as do par (T1)."""
    return TECHNIQUES[prefix].metrics + PAIR_METRICS.get(prefix, ())


def all_metric_keys() -> list[str]:
    return [f"{prefix}_{name}" for prefix in TECHNIQUES for name in metric_names(prefix)]


def pair_differences(prefix: str, real: dict, synthetic: dict, ctx: dict, min_units: int = MIN_ROIS) -> dict:
    """Diferença bruta d de cada métrica entre duas leituras (sem régua).

    Métricas de uma imagem: d = sintética − real. Do par: d = a própria
    métrica (`shape_dist` ≥ 0; `sigma_ratio` = log σ_sint/σ_real).
    """
    a, b = compute_metrics(prefix, real, ctx, min_units), compute_metrics(prefix, synthetic, ctx, min_units)
    out = {name: b[name] - a[name] for name in TECHNIQUES[prefix].metrics}
    for name in PAIR_METRICS.get(prefix, ()):
        out[name] = pair_metric(prefix, name, real, synthetic, min_units)
    return out


def raw_pair(real_side: dict, synthetic_side: dict, ctx: dict, paired: bool) -> dict:
    """Valores real/sintético, d e IC 95% de d (bootstrap das ROIs/blocos) de todas as métricas.

    Nada aqui depende da régua: o z e o status saem de `decision.score`, o que
    deixa recalibrar a régua (e o multiplicador k) sem medir de novo.
    """
    out: dict = {}
    for prefix in TECHNIQUES:
        real, synthetic = real_side[prefix], synthetic_side[prefix]
        values = {"real": compute_metrics(prefix, real, ctx), "synthetic": compute_metrics(prefix, synthetic, ctx)}
        d = pair_differences(prefix, real, synthetic, ctx)
        finite = any(np.isfinite(v) for v in d.values())
        bands = bootstrap(lambda x, y: pair_differences(prefix, x, y, ctx), real, synthetic, paired) if finite else {}
        for name in metric_names(prefix):
            low, high = bands.get(name, (float("nan"), float("nan")))
            key = f"{prefix}_{name}"
            out[f"{key}_real"] = values["real"].get(name, float("nan"))
            out[f"{key}_synthetic"] = values["synthetic"].get(name, float("nan"))
            out[f"{key}_d"], out[f"{key}_d_low"], out[f"{key}_d_high"] = d[name], low, high
    return out
