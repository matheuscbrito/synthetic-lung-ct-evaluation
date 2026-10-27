"""Calibração só nas reais (v3): réguas por vizinhos da mesma série, σ0 do Wiener, impressão de referência e k.

Gera o conteúdo de `calibracao.json`:

- `sigma0`: mediana, entre as originais, do MAD-HH₁ nos pixels sem estrutura;
  fica fixo no filtro wavelet-Wiener para todas as imagens;
- `fingerprint`: espectro radial médio (log10) do resíduo das reais, por filtro,
  e `lsd_norm`, a distância típica real × referência;
- `neighbour_pairs` (controle (a)): cada original com o vizinho da **mesma série**
  do mesmo paciente (índice do corte e fase mais próximos); corte sozinho na série fica de fora;
- `metrics`: para cada métrica, a escala da régua v2
  `scale = max(IQR do Δ entre vizinhos, 2 × IQR da diferença metade par × ímpar)`
  (o "IQR do Δ" é estimado como 2 × mediana|Δ|; em `shape_dist`, o IQR de fato)
  (mais a resolução de 1 bin para f_pico), e, como diagnóstico, P25/mediana/P75/IQR
  entre cortes e a repetibilidade (IQR par × ímpar ÷ IQR entre cortes). Para
  `shape_dist` (um lado só) também a `reference` = mediana da distância entre vizinhos;
- `k`: multiplicador global da escala, o menor (em 1,0–2,0) que faz o controle (a)
  chegar a ≥ 85% aprovada e ≤ 5% reprovada e o controle (b) — resíduo deslocado,
  nova realização do ruído na mesma anatomia (`controls.py`) — a ≥ 95% aprovada;
- `lopo`: o mesmo procedimento deixando um paciente fora (réguas e k só nos
  outros), com (a) e (b) medidos no paciente de fora (fora da amostra).
"""
from __future__ import annotations

import re
from collections import Counter

import numpy as np

from .decision import DRAWS, ONE_SIDED, SEED, score
from .fingerprint import log_profile, lsd
from .measure import PAIR_METRICS, TECHNIQUES, all_metric_keys, compute_metrics, make_plan, measure, pair_metric, raw_pair
from .noise_level import pooled_mad1
from .nps import LEAK_FACTOR, MAX_OVERLAP, MAX_ROIS, MIN_COVER, MIN_ROIS, ROI_SIZE, SKIP_BINS
from .regions import EDGE_PERCENTILE, SOFT_KEEP, VESSEL_PERCENTILE
from .residual import DENOISERS, LEVELS, WAVELET, WINDOWS
from .controls import SHIFT, residual_shift_control
from .stationarity import BLOCK, MIN_VALID, RHO_MIN, STRIDE, map_rho

VERSION = "noise_signature 0.3 (2026-10-26)"
MIN_CALIBRATION = 4
K_GRID = tuple(np.round(np.arange(1.0, 2.0001, 0.05), 2))
K_EXTENDED = tuple(np.round(np.arange(2.1, 5.0001, 0.1), 2))   # só para relatar o k que seria preciso
K_TARGET_APPROVED, K_TARGET_REJECTED = 0.85, 0.05
K_TARGET_CONTROL = 0.95                       # controle (b): resíduo deslocado, mesma anatomia
SPLIT_FACTOR = 2.0
# f_pico é discreto (um bin de frequência): a régua nunca fica menor que um bin
RESOLUTION = {"t1_lung_f_peak": 1 / ROI_SIZE["lung"], "t1_soft_f_peak": 1 / ROI_SIZE["soft"]}
CONFIG = {
    "roi_size": ROI_SIZE, "roi_min_cover": MIN_COVER, "roi_max_overlap": MAX_OVERLAP, "min_rois": MIN_ROIS, "max_rois": MAX_ROIS,
    "skip_bins": SKIP_BINS, "leak_factor": LEAK_FACTOR, "vessel_percentile": VESSEL_PERCENTILE, "edge_percentile": EDGE_PERCENTILE,
    "soft_keep": SOFT_KEEP, "wavelet": WAVELET, "levels": LEVELS, "windows": list(WINDOWS),
    "block": BLOCK, "block_stride": STRIDE, "block_min_valid": MIN_VALID, "map_rho_min": RHO_MIN,
    "bootstrap_draws": DRAWS, "bootstrap_seed": SEED, "split_factor": SPLIT_FACTOR,
    "k_grid": [float(K_GRID[0]), float(K_GRID[-1])],
    "k_target": {"vizinhos_aprovada_min": K_TARGET_APPROVED, "vizinhos_reprovada_max": K_TARGET_REJECTED, "controle_residuo_aprovada_min": K_TARGET_CONTROL},
    "neighbour_mode": "same_series", "control_shift_px": list(SHIFT),
}


def patient_key(case_id: str) -> str:
    """Paciente do nome do corte (ex.: P4P117 em `1.000000-P4P117S301I00005 ...`)."""
    match = re.search(r"P\d+P\d+", case_id)
    return match.group(0) if match else case_id


def slice_info(case_id: str) -> tuple[str, str, int, int]:
    """(paciente, série, fase respiratória, índice do corte), ex.: P4P117, S301, 5, 33 de `...P4P117S301I00005 ...-1-033`."""
    match = re.search(r"(P\d+P\d+)(S\d+)I(\d+).*-(\d+)$", case_id)
    if not match:
        return patient_key(case_id), "", 0, 0
    return match.group(1), match.group(2), int(match.group(3)), int(match.group(4))


NEIGHBOUR_MODES = ("same_series", "same_series_first", "index")


def neighbour_pairs(case_ids, mode: str = "same_series") -> list[tuple[int, int]]:
    """Cada corte com o vizinho do mesmo paciente (menor |Δ índice do corte|, depois menor |Δ fase|).

    - `same_series` (v3, controle (a)): só cortes da mesma série (mesma aquisição);
      corte sem par na série fica de fora;
    - `same_series_first` (v2): mesma série se houver, senão outra série;
    - `index`: ignora a série.
    """
    if mode not in NEIGHBOUR_MODES:
        raise ValueError(mode)
    info = [slice_info(c) for c in case_ids]
    pairs = []
    for i, (patient, series, phase, index) in enumerate(info):
        partners = [j for j, other in enumerate(info) if j != i and other[0] == patient and (mode != "same_series" or other[1] == series)]
        if partners:
            j = min(partners, key=lambda j: (mode == "same_series_first" and info[j][1] != series, abs(info[j][3] - index), abs(info[j][2] - phase), j))
            pairs.append((i, j))
    return pairs


def cross_series_pairs(case_ids) -> list[tuple[int, int]]:
    """Controle (c): pares do mesmo paciente em séries diferentes (i < j)."""
    info = [slice_info(c) for c in case_ids]
    return [(i, j) for i in range(len(info)) for j in range(i + 1, len(info)) if info[i][0] == info[j][0] and info[i][1] != info[j][1]]


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


def _iqr(values) -> float:
    return summary(values)["iqr"]


def rulers(readings, splits, nn_raws) -> dict:
    """Escala v2 de cada métrica a partir das leituras por corte, das metades e dos pares vizinhos."""
    metrics = {}
    for key in all_metric_keys():
        stats = summary(r.get(key, np.nan) for r in readings) if not key.endswith(("shape_dist", "sigma_ratio")) else summary([])
        split_iqr = _iqr(s.get(key, np.nan) for s in splits)
        d = np.array([raw[f"{key}_d"] for raw in nn_raws], dtype=float)
        d = d[np.isfinite(d)]
        if key in ONE_SIDED:
            nn = summary(d)
            nn_iqr, stats["reference"] = nn["iqr"], nn["median"]
        else:
            nn_iqr = float(2 * np.median(np.abs(d))) if d.size >= MIN_CALIBRATION else float("nan")
        candidates = {"vizinhos": nn_iqr, "repetibilidade": SPLIT_FACTOR * split_iqr, "resolução": RESOLUTION.get(key, float("nan"))}
        finite = {name: v for name, v in candidates.items() if np.isfinite(v) and v > 0}
        stats.update({
            "split_iqr": split_iqr, "nn_iqr": nn_iqr, "nn_n": int(d.size),
            "repeatability_iqr": float(split_iqr / stats["iqr"]) if np.isfinite(stats["iqr"]) and stats["iqr"] > 0 else float("nan"),
            "repeatability_nn": float(split_iqr / nn_iqr) if np.isfinite(nn_iqr) and nn_iqr > 0 else float("nan"),
            "scale": max(finite.values()) if finite else float("nan"),
            "scale_source": max(finite, key=finite.get) if finite else None,
        })
        metrics[key] = stats
    return metrics


def status_rates(raws, metrics: dict, k: float, same_anatomy: bool = False) -> dict:
    statuses = [score(raw, {"metrics": metrics}, same_anatomy=same_anatomy, k=k)["noise_signature_status"] for raw in raws]
    counts = Counter(statuses)
    n = max(len(statuses), 1)
    return {"k": float(k), "n": len(statuses), "aprovada": counts.get("aprovada", 0) / n,
            "revisão": counts.get("revisão", 0) / n, "reprovada": counts.get("reprovada", 0) / n}


def _meets(a: dict, b: dict | None) -> bool:
    ok = a["aprovada"] >= K_TARGET_APPROVED and a["reprovada"] <= K_TARGET_REJECTED
    return ok and (b is None or b["aprovada"] >= K_TARGET_CONTROL)


def choose_k(nn_raws, metrics: dict, control_raws=None) -> dict:
    """Menor k da grade que cumpre as metas nos controles (a) e (b); senão o melhor k da grade.

    (a) vizinhos da mesma série (só máscara): ≥ 85% aprovada e ≤ 5% reprovada;
    (b) resíduo deslocado (mesma anatomia): ≥ 95% aprovada.
    Sem k que cumpra: o que maximiza (aprovada − reprovada) somado nos dois; empate → maior k.
    """
    def rates(k):
        a = status_rates(nn_raws, metrics, k)
        b = status_rates(control_raws, metrics, k, same_anatomy=True) if control_raws else None
        return {"k": float(k), "a": a, "b": b}

    grid = [rates(k) for k in K_GRID]
    ok = [g for g in grid if _meets(g["a"], g["b"])]
    gain = lambda g: round(g["a"]["aprovada"] - g["a"]["reprovada"] + (g["b"]["aprovada"] - g["b"]["reprovada"] if g["b"] else 0), 9)
    chosen = ok[0] if ok else max(grid, key=lambda g: (gain(g), g["k"]))
    needed = chosen if ok else next((g for g in (rates(k) for k in K_EXTENDED) if _meets(g["a"], g["b"])), None)
    return {"k": chosen["k"], "target_met": bool(ok), "in_sample": chosen, "grid": grid,
            "k_needed": needed["k"] if needed else None}


def calibration_inputs(valid, neighbour_mode: str = "same_series", controls: bool = True) -> dict:
    """Medidas das originais (cada uma com o próprio plano), metades par × ímpar, controle (a) e controle (b) (d bruto)."""
    if len(valid) < MIN_CALIBRATION:
        raise RuntimeError(f"calibração precisa de pelo menos {MIN_CALIBRATION} originais válidas")
    ids = [case.paths.case_id for case in valid]
    plans = [make_plan(case.original, case.lung_mask) for case in valid]
    sigma0 = float(np.nanmedian([pooled_mad1(case.original, plan.regions.strict_union) for case, plan in zip(valid, plans)]))
    sides = [measure(case.original, plan, sigma0) for case, plan in zip(valid, plans)]

    ctx: dict = {"sigma0": sigma0, "fingerprint": {}, "lsd_norm": {}}
    for kind in DENOISERS:
        profiles = [side[f"t2_{kind}"]["lung"]["prof"] for side in sides if len(side[f"t2_{kind}"]["lung"]["prof"]) >= MIN_ROIS]
        reference = np.mean([log_profile(prof) for prof in profiles], axis=0)
        ctx["fingerprint"][kind] = reference.tolist()
        ctx["lsd_norm"][kind] = float(np.median([lsd(prof, reference) for prof in profiles]))

    readings, splits = [], []
    for side in sides:
        reading, split = {}, {}
        for prefix in TECHNIQUES:
            a, b = halves(side[prefix])
            ma, mb = compute_metrics(prefix, a, ctx, MIN_ROIS // 2), compute_metrics(prefix, b, ctx, MIN_ROIS // 2)
            for name, value in compute_metrics(prefix, side[prefix], ctx).items():
                reading[f"{prefix}_{name}"] = value
                split[f"{prefix}_{name}"] = mb[name] - ma[name]
            for name in PAIR_METRICS.get(prefix, ()):
                split[f"{prefix}_{name}"] = pair_metric(prefix, name, a, b, MIN_ROIS // 2)
        readings.append(reading)
        splits.append(split)

    pairs = neighbour_pairs(ids, neighbour_mode)
    nn_raws = [raw_pair(sides[i], sides[j], ctx, paired=False) for i, j in pairs]
    control_raws, coverage = [], []
    if controls:
        for case, plan, side in zip(valid, plans, sides):
            image, cov = residual_shift_control(case.original, sigma0, case.lung_mask, plan.regions.soft.host)
            other = measure(image, plan, sigma0)
            raw = raw_pair(side, other, ctx, paired=True)
            raw["t4_map_rho"] = map_rho(side["t4"]["blocks"]["map"], other["t4"]["blocks"]["map"])
            control_raws.append(raw)
            coverage.append(cov)
    return {"ids": ids, "sides": sides, "ctx": ctx, "readings": readings, "splits": splits, "pairs": pairs, "nn_raws": nn_raws,
            "control_raws": control_raws, "control_coverage": coverage}


def calibrate(valid, dataset: str = "", lopo: bool = True) -> dict:
    """Réguas pelos vizinhos da mesma série e k pelos controles (a) e (b), com validação deixando um paciente fora."""
    inputs = calibration_inputs(valid)
    ids, ctx, readings, splits, pairs, nn_raws, control_raws = (
        inputs[k] for k in ("ids", "ctx", "readings", "splits", "pairs", "nn_raws", "control_raws"))
    metrics = rulers(readings, splits, nn_raws)
    k_info = choose_k(nn_raws, metrics, control_raws)

    patients = [patient_key(c) for c in ids]
    folds = []
    if lopo:
        for patient in sorted(set(patients)):
            test = [n for n, (i, _) in enumerate(pairs) if patients[i] == patient]
            if not test:
                continue
            train_slices = [i for i, p in enumerate(patients) if p != patient]
            test_slices = [i for i, p in enumerate(patients) if p == patient]
            train = [n for n, (i, _) in enumerate(pairs) if patients[i] != patient]
            fold_metrics = rulers([readings[i] for i in train_slices], [splits[i] for i in train_slices], [nn_raws[n] for n in train])
            fold_k = choose_k([nn_raws[n] for n in train], fold_metrics, [control_raws[i] for i in train_slices] if control_raws else None)
            held = status_rates([nn_raws[n] for n in test], fold_metrics, fold_k["k"])
            held_b = status_rates([control_raws[i] for i in test_slices], fold_metrics, fold_k["k"], same_anatomy=True) if control_raws else {}
            folds.append({"held_out": patient, "k": fold_k["k"], "target_met_in_training": fold_k["target_met"],
                          "n_train_pairs": len(train), "n_test_pairs": len(test), "test": held,
                          "n_test_controls": len(test_slices), "test_controls": held_b})
    pooled, pooled_b = {}, {}
    if folds:
        total = sum(f["n_test_pairs"] for f in folds)
        pooled = {"n": total, **{s: sum(f["test"][s] * f["n_test_pairs"] for f in folds) / total for s in ("aprovada", "revisão", "reprovada")}}
        if control_raws:
            total_b = sum(f["n_test_controls"] for f in folds)
            pooled_b = {"n": total_b, **{s: sum(f["test_controls"][s] * f["n_test_controls"] for f in folds) / total_b
                                         for s in ("aprovada", "revisão", "reprovada")}}

    return {
        "version": VERSION, "dataset": dataset, "n_cases": len(valid), "patients": sorted(set(patients)),
        "cases": ids, "config": CONFIG, **ctx,
        "neighbour_pairs": [[ids[i], ids[j]] for i, j in pairs],
        "control_shift_coverage": inputs["control_coverage"],
        "metrics": metrics, "k": k_info["k"], "k_calibration": k_info,
        "lopo": {"folds": folds, "pooled_out_of_sample": pooled, "pooled_out_of_sample_controls": pooled_b},
    }
