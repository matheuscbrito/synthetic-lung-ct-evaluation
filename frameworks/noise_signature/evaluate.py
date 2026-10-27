"""Avalia a assinatura de ruído de cada par real × sintética.

Uso (da raiz do repositório):

    python -m frameworks.noise_signature.evaluate --data-dir dados/Dsr --mask-dir dados/Dgen \\
        --output-dir outputs/noise_signature/Dsr [--calibration calibracao.json] \\
        [--pair-mode auto|same-anatomy|mask-only] [--limit N]

Sem `--calibration`, calibra nas originais válidas do próprio dataset (réguas
pelos pares reais vizinhos e multiplicador k) e grava `calibracao.json` na
pasta de saída. Saídas: `resultados.csv` (uma linha por
corte), `protocolo.json` e `figuras/`.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np

from wavelet.src.load_data import CasePaths, discover_cases
from wavelet.src.validate_cases import ValidCase, validate_case
from frameworks.texture_evaluator.regional import PAIR_MIN_CORRELATION, pair_correlation

from .calibrate import CONFIG, VERSION, calibrate
from .decision import (DECISION_METRICS, EIXOS, TECHNIQUE_PREFIXES, active_decision_metrics, denoisers_agree, score)
from .measure import TECHNIQUES, all_metric_keys, group_size, make_plan, measure, raw_pair
from .stationarity import map_rho

SAME_ANATOMY, MASK_ONLY = "same-anatomy", "mask-only"
SIDES = ("real", "synthetic")
METRIC_FIELDS = ("real", "synthetic", "d", "d_low", "d_high", "z", "z_low", "z_high", "status")


def metric_keys() -> list[str]:
    """Todas as métricas (decisão + diagnóstico), na ordem do CSV."""
    return all_metric_keys()


def evaluate_pair(case_id: str, original: np.ndarray, synthetic: np.ndarray, lung_mask: np.ndarray, calib: dict,
                  same_anatomy: bool, synthetic_mask: np.ndarray | None = None):
    """Mede o par e devolve (linha do CSV, leituras real/sintética para as figuras).

    `synthetic_mask` (opcional, só máscara): máscara própria da segunda imagem,
    usada para comparar duas reais de cortes diferentes.
    """
    sigma0 = float(calib["sigma0"])
    plan_real = make_plan(original, lung_mask)
    plan_synthetic = plan_real if same_anatomy else make_plan(synthetic, lung_mask if synthetic_mask is None else synthetic_mask)
    real, generated = measure(original, plan_real, sigma0), measure(synthetic, plan_synthetic, sigma0)
    common = lung_mask if synthetic_mask is None else (lung_mask & synthetic_mask)
    raw = raw_pair(real, generated, calib, paired=same_anatomy)
    raw["t4_map_rho"] = map_rho(real["t4"]["blocks"]["map"], generated["t4"]["blocks"]["map"]) if same_anatomy else float("nan")
    scored = score(raw, calib, same_anatomy)

    row: dict = {"case_id": case_id, "noise_signature_status": scored["noise_signature_status"],
                 "noise_signature_reasons": scored["noise_signature_reasons"],
                 "noise_signature_diagnostics": scored["noise_signature_diagnostics"]}
    row.update({f"eixo_{eixo}_status": scored[f"eixo_{eixo}_status"] for eixo in EIXOS})
    row.update({f"{tech}_status": scored[f"{tech}_status"] for tech in TECHNIQUE_PREFIXES})
    merged = {**raw, **scored}
    row["t2_denoisers_agree"] = denoisers_agree(merged, TECHNIQUES["t2_wiener"].metrics)
    row.update({"pair_mode": SAME_ANATOMY if same_anatomy else MASK_ONLY, "pair_correlation": pair_correlation(original, synthetic, common),
                "k": float(calib.get("k", 1.0))})
    for name in ("lung", "soft"):
        row[f"t1_{name}_n_rois"] = len(plan_real.rois[name])
        row[f"t1_{name}_n_used"] = group_size(real[f"t1_{name}"]["roi"])
        row[f"t1_{name}_leak_fallback"] = bool(plan_real.t1_fallback[name])
        row[f"t1_{name}_leak_real"], row[f"t1_{name}_leak_synthetic"] = real[f"leak_{name}"], generated[f"leak_{name}"]
    row["t4_n_blocks"] = len(plan_real.blocks)
    row["t4_map_rho"], row["t4_map_rho_status"] = raw["t4_map_rho"], scored["t4_map_rho_status"]
    active = set(active_decision_metrics(same_anatomy))
    for key in metric_keys():
        row[f"{key}_role"] = "decisão" if key in active else "diagnóstico"
        for field in METRIC_FIELDS:
            row[f"{key}_{field}"] = merged.get(f"{key}_{field}", float("nan"))
    return row, (real, generated)


def load_valid(data_dir: Path, mask_dir: Path | None):
    valid, rejected = [], []
    for paths in discover_cases(data_dir):
        if mask_dir:
            paths = CasePaths(paths.case_id, paths.original, paths.synthetic, mask_dir / f"{paths.case_id}_mask.tiff")
        result = validate_case(paths, erosion_radius=2)
        (valid if isinstance(result, ValidCase) else rejected).append(result)
    return valid, rejected


def resolve_mode(mode: str, valid) -> tuple[bool, float]:
    median = float(np.median([pair_correlation(c.original, c.synthetic, c.lung_mask) for c in valid]))
    if mode == "auto":
        return median >= PAIR_MIN_CORRELATION, median
    return mode == SAME_ANATOMY, median


def _json_default(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(type(value))


def save_figures(rows: list[dict], readings: list, output_dir: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from .nps import ROI_SIZE, frequencies, SKIP_BINS

    folder = output_dir / "figuras"
    folder.mkdir(parents=True, exist_ok=True)
    for row, (real, generated) in readings:
        fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
        for axis, name, title in zip(axes, ("lung", "soft"), ("pulmão", "tecido mole")):
            freqs = frequencies(ROI_SIZE[name])[SKIP_BINS:]
            for side, label, color in ((real, "real", "#1f6f8b"), (generated, "sintética", "#d1495b")):
                profile = side[f"t1_{name}"]["roi"]["profile"]
                if len(profile):
                    axis.semilogy(freqs, profile.mean(axis=0)[SKIP_BINS:], color=color, label=f"{label} ({len(profile)} ROIs)")
            axis.set_title(f"NPS radial — {title}")
            axis.set_xlabel("ciclos/pixel")
            axis.legend(fontsize=8)
        fig.suptitle(f"{row['case_id']} · {row['noise_signature_status']}", fontsize=9)
        fig.tight_layout()
        fig.savefig(folder / f"nps_{row['case_id']}.png", dpi=120)
        plt.close(fig)

    keys = list(DECISION_METRICS) + [k for k in metric_keys() if k not in DECISION_METRICS and not k.startswith("t2_median")]
    data = [[float(r[f"{k}_z"]) for r in rows if np.isfinite(float(r[f"{k}_z"]))] for k in keys]
    shown = [(k, d) for k, d in zip(keys, data) if d]
    if shown:
        fig, axis = plt.subplots(figsize=(12, 0.32 * len(shown) + 1.5))
        axis.boxplot([d for _, d in shown], vert=False, showfliers=True)
        axis.set_yticks(range(1, len(shown) + 1))
        axis.set_yticklabels([k + (" ★" if k in DECISION_METRICS else "") for k, _ in shown], fontsize=8)
        for edge in (-2, -1, 1, 2):
            axis.axvline(edge, color="#999", lw=0.8, ls="--" if abs(edge) == 1 else ":")
        axis.set_xlabel("z = d / (k · escala dos vizinhos reais)")
        axis.set_title("Assinatura de ruído — z por métrica na coorte (★ = decide)")
        fig.tight_layout()
        fig.savefig(folder / "coorte_z.png", dpi=120)
        plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--mask-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, help="calibracao.json existente; sem ele, calibra nas originais deste dataset")
    parser.add_argument("--pair-mode", choices=("auto", SAME_ANATOMY, MASK_ONLY), default="auto")
    parser.add_argument("--limit", type=int, help="avalia só os N primeiros pares válidos")
    parser.add_argument("--figures", type=int, default=4, help="quantos cortes ganham figura do NPS")
    args = parser.parse_args()
    start = time.time()

    valid, rejected = load_valid(args.data_dir, args.mask_dir)
    if not valid:
        raise RuntimeError("nenhum par válido")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.calibration:
        calib = json.loads(args.calibration.read_text(encoding="utf-8"))
        calib_path = args.calibration
    else:
        calib = calibrate(valid, dataset=str(args.data_dir))
        calib_path = args.output_dir / "calibracao.json"
        calib_path.write_text(json.dumps(calib, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8")

    cases = valid[: args.limit] if args.limit else valid
    same_anatomy, median_corr = resolve_mode(args.pair_mode, cases)
    rows, readings = [], []
    for index, case in enumerate(cases):
        row, sides = evaluate_pair(case.paths.case_id, case.original, case.synthetic, case.lung_mask, calib, same_anatomy)
        rows.append(row)
        if index < args.figures:
            readings.append((row, sides))
        print(f"[{index + 1}/{len(cases)}] {case.paths.case_id}: {row['noise_signature_status']}", flush=True)

    with (args.output_dir / "resultados.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    save_figures(rows, readings, args.output_dir)
    counts = Counter(row["noise_signature_status"] for row in rows)
    protocol = {
        "version": VERSION, "data_dir": str(args.data_dir), "mask_dir": str(args.mask_dir) if args.mask_dir else None,
        "pair_mode": SAME_ANATOMY if same_anatomy else MASK_ONLY, "pair_mode_requested": args.pair_mode,
        "median_pair_correlation": median_corr, "n_valid": len(valid), "n_evaluated": len(rows),
        "rejected": [{"case_id": r.paths.case_id, "reason": r.reason} for r in rejected],
        "calibration": {"path": str(calib_path), "dataset": calib.get("dataset"), "n_cases": calib.get("n_cases"),
                        "sigma0": calib.get("sigma0"), "version": calib.get("version")},
        "config": CONFIG, "status_counts": dict(counts),
        "k": calib.get("k"), "decision_metrics": {eixo: list(keys) for eixo, keys in EIXOS.items()},
        "technique_status_counts": {key: dict(Counter(row[f"{key}_status"] for row in rows)) for key in TECHNIQUE_PREFIXES},
        "eixo_status_counts": {eixo: dict(Counter(row[f"eixo_{eixo}_status"] for row in rows)) for eixo in EIXOS},
        "runtime_s": round(time.time() - start, 1),
    }
    (args.output_dir / "protocolo.json").write_text(json.dumps(protocol, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8")
    print(f"{len(rows)} pares em {protocol['runtime_s']} s · {dict(counts)} · saída em {args.output_dir}")


if __name__ == "__main__":
    main()
