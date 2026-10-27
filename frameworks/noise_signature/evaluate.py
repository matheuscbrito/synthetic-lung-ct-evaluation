"""Avalia a assinatura de ruído de cada par real × sintética.

Uso (da raiz do repositório):

    python -m frameworks.noise_signature.evaluate --data-dir dados/Dsr --mask-dir dados/Dgen \\
        --output-dir outputs/noise_signature/Dsr [--calibration calibracao.json] \\
        [--pair-mode auto|same-anatomy|mask-only] [--limit N]

Sem `--calibration`, calibra nas originais válidas do próprio dataset e grava
`calibracao.json` na pasta de saída. Saídas: `resultados.csv` (uma linha por
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
from .decision import (INCONCLUSIVE, PREFIX_LABELS, TECHNIQUE_LABELS, TECHNIQUE_PREFIXES, bootstrap, certain_status, combine,
                       denoisers_agree, final_status, metric_reason, pt)
from .measure import PAIR_METRICS, TECHNIQUES, compute_metrics, group_size, make_plan, measure, pair_metric
from .nps import MIN_ROIS
from .stationarity import RHO_MIN, map_rho

SAME_ANATOMY, MASK_ONLY = "same-anatomy", "mask-only"
SIDES = ("real", "synthetic")


def _iqr(calib: dict, key: str) -> float:
    value = calib["metrics"].get(key, {}).get("iqr", float("nan"))
    return float(value) if value is not None and np.isfinite(value) and value > 0 else float("nan")


def _zfun(prefix: str, calib: dict):
    """z de cada métrica de uma técnica (e da forma do NPS, quando houver) entre duas leituras."""
    technique, pair = TECHNIQUES[prefix], PAIR_METRICS.get(prefix)
    iqr = {name: _iqr(calib, f"{prefix}_{name}") for name in technique.metrics}
    reference = calib["shape_reference"].get(prefix, {}) if pair else {}

    def zfun(real: dict, synthetic: dict) -> dict:
        a, b = compute_metrics(prefix, real, calib), compute_metrics(prefix, synthetic, calib)
        out = {name: (b[name] - a[name]) / iqr[name] for name in technique.metrics}
        if pair:
            spread = reference.get("iqr", float("nan"))
            out[pair] = (pair_metric(prefix, real, synthetic) - reference.get("median", float("nan"))) / spread if spread else float("nan")
        return out
    return zfun


def technique_columns(prefix: str, real: dict, synthetic: dict, calib: dict, paired: bool) -> dict:
    """Valor real, sintético, z, IC 95% do z e status de cada métrica de uma técnica."""
    technique, pair = TECHNIQUES[prefix], PAIR_METRICS.get(prefix)
    values = {"real": compute_metrics(prefix, real, calib), "synthetic": compute_metrics(prefix, synthetic, calib)}
    zfun = _zfun(prefix, calib)
    z = zfun(real, synthetic)
    finite = any(np.isfinite(v) for v in z.values())
    bands = bootstrap(zfun, real, synthetic, paired) if finite else {}
    if pair:
        values["real"][pair] = calib["shape_reference"].get(prefix, {}).get("median", float("nan"))
        values["synthetic"][pair] = pair_metric(prefix, real, synthetic)
    out = {}
    for name in technique.metrics + ((pair,) if pair else ()):
        low, high = bands.get(name, (float("nan"), float("nan")))
        out.update({
            f"{prefix}_{name}_real": values["real"][name], f"{prefix}_{name}_synthetic": values["synthetic"][name],
            f"{prefix}_{name}_z": z[name], f"{prefix}_{name}_z_low": low, f"{prefix}_{name}_z_high": high,
            f"{prefix}_{name}_status": certain_status(z[name], low, high),
        })
    return out


def metric_names(prefix: str) -> tuple:
    pair = PAIR_METRICS.get(prefix)
    return TECHNIQUES[prefix].metrics + ((pair,) if pair else ())


def decide(row: dict, same_anatomy: bool) -> dict:
    """Status por região/técnica, veredito final e motivos em português simples."""
    reasons = []
    for prefix in TECHNIQUES:
        row[f"{prefix}_status"] = combine(row[f"{prefix}_{name}_status"] for name in metric_names(prefix))

    # T2: a decisão usa o Wiener; a mediana 3×3 é o controle. A discordância fica
    # registrada (coluna e motivo) para a leitura humana, sem mudar o status.
    agree = denoisers_agree(row, TECHNIQUES["t2_wiener"].metrics)
    row["t2_denoisers_agree"] = agree
    if not agree:
        names = [name for name in TECHNIQUES["t2_wiener"].metrics
                 if INCONCLUSIVE not in (row[f"t2_wiener_{name}_status"], row[f"t2_median_{name}_status"])
                 and (row[f"t2_wiener_{name}_status"] == "aprovada") != (row[f"t2_median_{name}_status"] == "aprovada")]
        reasons.append(f"T2 resíduo: os filtros Wiener e mediana 3×3 discordam em {', '.join(names)} (leitura da T2 menos segura)")

    # T4: mapa de ruído pareado (só mesma anatomia), fora da régua IQR
    if same_anatomy and np.isfinite(row["t4_map_rho"]):
        row["t4_map_rho_status"] = "revisão" if row["t4_map_rho"] < RHO_MIN else "aprovada"
        if row["t4_map_rho"] < RHO_MIN:
            reasons.append(f"T4 distribuição: o mapa de ruído da sintética não acompanha o da real (ρ = {pt(row['t4_map_rho'], 2)} < {pt(RHO_MIN)}) — revisão")
    else:
        row["t4_map_rho_status"] = "não verificável" if not same_anatomy else INCONCLUSIVE

    techniques = {
        "t1": combine([row["t1_lung_status"], row["t1_soft_status"]]),
        "t2": row["t2_wiener_status"],
        "t3": combine([row["t3_lung_status"], row["t3_soft_status"]]),
        "t4": combine([row["t4_status"], row["t4_map_rho_status"]]),
    }
    for key, status in techniques.items():
        row[f"{key}_status"] = status
    for prefix in ("t1_lung", "t1_soft", "t2_wiener", "t3_lung", "t3_soft", "t4"):
        for name in metric_names(prefix):
            if row[f"{prefix}_{name}_status"] in ("revisão", "reprovada"):
                reasons.append(metric_reason(row, prefix, name))
    for prefix, count in (("t1_lung", row["t1_lung_n_used"]), ("t1_soft", row["t1_soft_n_used"])):
        if row[f"{prefix}_status"] == INCONCLUSIVE:
            reasons.append(f"{PREFIX_LABELS[prefix]}: inconclusivo (só {count} ROIs sem anatomia; mínimo {MIN_ROIS})")
    for key, status in techniques.items():
        if status == INCONCLUSIVE:
            reasons.append(f"{TECHNIQUE_LABELS[key]}: inconclusivo, não pode aprovar o corte")
    verdict = final_status(techniques)
    return {"noise_signature_status": verdict,
            "noise_signature_reasons": "; ".join(reasons) or "ruído dentro do esperado nas quatro técnicas"}


def evaluate_pair(case_id: str, original: np.ndarray, synthetic: np.ndarray, lung_mask: np.ndarray, calib: dict, same_anatomy: bool):
    """Mede o par e devolve (linha do CSV, leituras real/sintética para as figuras)."""
    sigma0 = float(calib["sigma0"])
    plan_real = make_plan(original, lung_mask)
    plan_synthetic = plan_real if same_anatomy else make_plan(synthetic, lung_mask)
    real, generated = measure(original, plan_real, sigma0), measure(synthetic, plan_synthetic, sigma0)
    row: dict = {"case_id": case_id, "pair_mode": SAME_ANATOMY if same_anatomy else MASK_ONLY,
                 "pair_correlation": pair_correlation(original, synthetic, lung_mask)}
    for name in ("lung", "soft"):
        row[f"t1_{name}_n_rois"] = len(plan_real.rois[name])
        row[f"t1_{name}_n_used"] = group_size(real[f"t1_{name}"]["roi"])
        row[f"t1_{name}_leak_real"], row[f"t1_{name}_leak_synthetic"] = real[f"leak_{name}"], generated[f"leak_{name}"]
    row["t4_n_blocks"] = len(plan_real.blocks)
    for prefix in TECHNIQUES:
        row.update(technique_columns(prefix, real[prefix], generated[prefix], calib, paired=same_anatomy))
    row["t4_map_rho"] = map_rho(real["t4"]["blocks"]["map"], generated["t4"]["blocks"]["map"]) if same_anatomy else float("nan")
    verdict = decide(row, same_anatomy)
    ordered = {"case_id": case_id, **verdict, **{f"{k}_status": row.pop(f"{k}_status") for k in TECHNIQUE_PREFIXES},
               "t2_denoisers_agree": row.pop("t2_denoisers_agree")}
    ordered.update(row)
    return ordered, (real, generated)


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

    keys = [f"{prefix}_{name}" for prefix in ("t1_lung", "t1_soft", "t2_wiener", "t3_lung", "t3_soft", "t4") for name in metric_names(prefix)]
    data = [[float(r[f"{k}_z"]) for r in rows if np.isfinite(float(r[f"{k}_z"]))] for k in keys]
    shown = [(k, d) for k, d in zip(keys, data) if d]
    if shown:
        fig, axis = plt.subplots(figsize=(12, 0.32 * len(shown) + 1.5))
        axis.boxplot([d for _, d in shown], vert=False, showfliers=True)
        axis.set_yticks(range(1, len(shown) + 1))
        axis.set_yticklabels([k for k, _ in shown], fontsize=8)
        for edge in (-2, -1, 1, 2):
            axis.axvline(edge, color="#999", lw=0.8, ls="--" if abs(edge) == 1 else ":")
        axis.set_xlabel("z = (sintética − real) / IQR das reais")
        axis.set_title("Assinatura de ruído — z por métrica na coorte")
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
        "technique_status_counts": {key: dict(Counter(row[f"{key}_status"] for row in rows)) for key in TECHNIQUE_PREFIXES},
        "runtime_s": round(time.time() - start, 1),
    }
    (args.output_dir / "protocolo.json").write_text(json.dumps(protocol, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8")
    print(f"{len(rows)} pares em {protocol['runtime_s']} s · {dict(counts)} · saída em {args.output_dir}")


if __name__ == "__main__":
    main()
