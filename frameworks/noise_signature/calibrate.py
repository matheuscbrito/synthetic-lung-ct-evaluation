"""Calibração só nas reais: réguas IQR, σ0 do Wiener e impressão de referência.

Gera o conteúdo de `calibracao.json`:

- `sigma0`: mediana, entre as originais, do MAD-HH₁ nos pixels sem estrutura;
  fica fixo no filtro wavelet-Wiener para todas as imagens;
- `fingerprint`: espectro radial médio (log10) do resíduo das reais, por filtro,
  e `lsd_norm`, a distância típica real × referência;
- `metrics`: P25, mediana, P75, IQR e repetibilidade (IQR da diferença entre
  metade par × metade ímpar das ROIs, em IQR da métrica) de cada métrica;
- `shape_reference`: mediana e IQR da distância de forma do NPS entre cortes
  reais do mesmo paciente (a régua de `shape_dist`).
"""
from __future__ import annotations

import re
from itertools import combinations

import numpy as np

from .decision import DRAWS, SEED
from .fingerprint import log_profile, lsd
from .measure import PAIR_METRICS, TECHNIQUES, compute_metrics, make_plan, measure, pair_metric
from .noise_level import pooled_mad1
from .nps import LEAK_FACTOR, MAX_OVERLAP, MAX_ROIS, MIN_COVER, MIN_ROIS, ROI_SIZE, SKIP_BINS
from .regions import EDGE_PERCENTILE, SOFT_KEEP, VESSEL_PERCENTILE
from .residual import DENOISERS, LEVELS, WAVELET, WINDOWS
from .stationarity import BLOCK, MIN_VALID, RHO_MIN, STRIDE

VERSION = "noise_signature 0.1 (2026-10-26)"
MIN_CALIBRATION = 4
# f_pico é discreto (um bin de frequência): a régua nunca fica menor que um bin
RESOLUTION = {"t1_lung_f_peak": 1 / ROI_SIZE["lung"], "t1_soft_f_peak": 1 / ROI_SIZE["soft"]}
CONFIG = {
    "roi_size": ROI_SIZE, "roi_min_cover": MIN_COVER, "roi_max_overlap": MAX_OVERLAP, "min_rois": MIN_ROIS, "max_rois": MAX_ROIS,
    "skip_bins": SKIP_BINS, "leak_factor": LEAK_FACTOR, "vessel_percentile": VESSEL_PERCENTILE, "edge_percentile": EDGE_PERCENTILE,
    "soft_keep": SOFT_KEEP, "wavelet": WAVELET, "levels": LEVELS, "windows": list(WINDOWS),
    "block": BLOCK, "block_stride": STRIDE, "block_min_valid": MIN_VALID, "map_rho_min": RHO_MIN,
    "bootstrap_draws": DRAWS, "bootstrap_seed": SEED,
}


def patient_key(case_id: str) -> str:
    """Paciente do nome do corte (ex.: P4P117 em `1.000000-P4P117S301I00005 ...`)."""
    match = re.search(r"P\d+P\d+", case_id)
    return match.group(0) if match else case_id


def summary(values) -> dict:
    values = np.asarray([v for v in values if np.isfinite(v)], dtype=float)
    if values.size < MIN_CALIBRATION:
        return {"p25": float("nan"), "median": float("nan"), "p75": float("nan"), "iqr": float("nan"), "n": int(values.size)}
    p25, median, p75 = np.percentile(values, [25, 50, 75])
    return {"p25": float(p25), "median": float(median), "p75": float(p75), "iqr": float(p75 - p25), "n": int(values.size)}


def halves(groups: dict) -> tuple[dict, dict]:
    """Metade par × metade ímpar das linhas de cada grupo (ROIs ou blocos)."""
    even = {name: {key: value[0::2] for key, value in arrays.items()} for name, arrays in groups.items()}
    odd = {name: {key: value[1::2] for key, value in arrays.items()} for name, arrays in groups.items()}
    return even, odd


def calibrate(valid, dataset: str = "") -> dict:
    """Réguas tiradas só das originais válidas (cada uma com o próprio plano)."""
    if len(valid) < MIN_CALIBRATION:
        raise RuntimeError(f"calibração precisa de pelo menos {MIN_CALIBRATION} originais válidas")
    plans = [make_plan(case.original, case.lung_mask) for case in valid]
    sigma0 = float(np.nanmedian([pooled_mad1(case.original, plan.regions.strict_union) for case, plan in zip(valid, plans)]))
    sides = [measure(case.original, plan, sigma0) for case, plan in zip(valid, plans)]

    ctx: dict = {"sigma0": sigma0, "fingerprint": {}, "lsd_norm": {}}
    for kind in DENOISERS:
        profiles = [side[f"t2_{kind}"]["lung"]["prof"] for side in sides if len(side[f"t2_{kind}"]["lung"]["prof"]) >= MIN_ROIS]
        reference = np.mean([log_profile(prof) for prof in profiles], axis=0)
        ctx["fingerprint"][kind] = reference.tolist()
        ctx["lsd_norm"][kind] = float(np.median([lsd(prof, reference) for prof in profiles]))

    metrics = {}
    for prefix, technique in TECHNIQUES.items():
        readings = [compute_metrics(prefix, side[prefix], ctx) for side in sides]
        split = [halves(side[prefix]) for side in sides]
        diffs = [(compute_metrics(prefix, a, ctx, MIN_ROIS // 2), compute_metrics(prefix, b, ctx, MIN_ROIS // 2)) for a, b in split]
        for name in technique.metrics:
            stats = summary(r[name] for r in readings)
            key = f"{prefix}_{name}"
            if key in RESOLUTION and np.isfinite(stats["iqr"]):
                stats["iqr"] = max(stats["iqr"], RESOLUTION[key])
            repeat = summary(b[name] - a[name] for a, b in diffs)
            stats["repeatability_iqr"] = float(repeat["iqr"] / stats["iqr"]) if stats["iqr"] and np.isfinite(stats["iqr"]) else float("nan")
            metrics[key] = stats

    shape_reference = {}
    patients = [patient_key(case.paths.case_id) for case in valid]
    for prefix in PAIR_METRICS:
        distances = [pair_metric(prefix, sides[i][prefix], sides[j][prefix]) for i, j in combinations(range(len(valid)), 2) if patients[i] == patients[j]]
        split = [pair_metric(prefix, *halves(side[prefix]), MIN_ROIS // 2) for side in sides]
        stats = summary(distances)
        stats["n_pairs"] = len(distances)
        stats["split_half_median"] = float(np.nanmedian(split)) if np.isfinite(split).any() else float("nan")
        shape_reference[prefix] = stats

    return {
        "version": VERSION, "dataset": dataset, "n_cases": len(valid), "patients": sorted(set(patients)),
        "cases": [case.paths.case_id for case in valid], "config": CONFIG, **ctx,
        "metrics": metrics, "shape_reference": shape_reference,
    }
