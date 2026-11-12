"""Audita tamanho/homogeneidade das ROIs e executa a sensibilidade do NPS.

O estudo mantém as coordenadas escolhidas na CT real para todos os geradores.
Sem DICOM, a frequência permanece em ciclos/pixel. Exemplo::

    python -m frameworks.noise_evaluator.roi_study \
      --method DSR=dados/Dsr \
      --method Baseline=dados/Dsr-baseline \
      --method GPBO-11=dados/Dsr-gpbo11 \
      --mask-dir dados/Dgen --output-dir outputs/nps_roi_study
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from dataclasses import asdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.patches import Rectangle
import numpy as np

from .core import (
    NPSConfig,
    ROI,
    candidate_rois,
    compare_spectra,
    estimate_local_nps,
    nonoverlapping_rois,
)
from .regions import soft_tissue_mask
from .run_nps import _load_cases


ROI_SIZES = (16, 24, 32, 48, 64)
THRESHOLD_QUANTILES = {"strict": 0.25, "moderate": 0.50, "permissive": 0.75}
MIN_ANALYSIS_ROIS = 4
PRIMARY_CONFIG = "roi24_permissive"
SENSITIVITY_CONFIG = "roi32_moderate"


def _write_csv(rows: list[dict], path: Path) -> None:
    fields: list[str] = []
    for row in rows:
        fields.extend(key for key in row if key not in fields)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _parse_method(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("use NOME=PASTA, por exemplo GPBO-11=dados/Dsr-gpbo11")
    name, raw_path = value.split("=", 1)
    if not name.strip() or not raw_path.strip():
        raise argparse.ArgumentTypeError("nome e pasta não podem ser vazios")
    return name.strip(), Path(raw_path)


def _patient_id(case_id: str) -> str:
    match = re.search(r"P4P(?P<patient>\d+)S", case_id)
    return match.group("patient") if match else case_id


def _base_config(size: int, threshold: float | None = None) -> NPSConfig:
    return NPSConfig(
        roi_size=size,
        stride=max(4, size // 4),
        min_tissue=0.98,
        min_rois=1,
        max_rois=64,
        structure_sigma=3.0,
        max_structure_score=threshold,
    )


def _load_aligned(methods: list[tuple[str, Path]], mask_dir: Path, erosion_radius: int):
    loaded: dict[str, dict] = {}
    rejected: dict[str, list[dict]] = {}
    for name, path in methods:
        cases, failures = _load_cases(path, mask_dir, erosion_radius)
        loaded[name] = {case.paths.case_id: case for case in cases}
        rejected[name] = failures
    common = sorted(set.intersection(*(set(cases) for cases in loaded.values())))
    if not common:
        raise RuntimeError("nenhum case_id válido é comum a todos os métodos")
    return loaded, rejected, common


def calibrate_thresholds(real_cases: list, masks: dict[str, np.ndarray]) -> tuple[dict[int, dict[str, float]], list[dict]]:
    thresholds: dict[int, dict[str, float]] = {}
    rows: list[dict] = []
    for size in ROI_SIZES:
        scores: list[float] = []
        config = _base_config(size)
        for case in real_cases:
            scores.extend(roi.structure_score for roi in candidate_rois(case.original, masks[case.paths.case_id], config))
        if not scores:
            thresholds[size] = {name: float("nan") for name in THRESHOLD_QUANTILES}
            continue
        values = np.asarray(scores)
        thresholds[size] = {name: float(np.quantile(values, quantile)) for name, quantile in THRESHOLD_QUANTILES.items()}
        for name, value in thresholds[size].items():
            rows.append({"roi_size": size, "profile": name, "quantile": THRESHOLD_QUANTILES[name], "max_structure_score": value, "candidate_count": len(values)})
    return thresholds, rows


def audit_viability(real_cases: list, masks: dict[str, np.ndarray], thresholds: dict[int, dict[str, float]]):
    detail: list[dict] = []
    profiles = ("unfiltered", *THRESHOLD_QUANTILES)
    for size in ROI_SIZES:
        for profile in profiles:
            threshold = None if profile == "unfiltered" else thresholds[size][profile]
            if threshold is not None and not np.isfinite(threshold):
                continue
            config = _base_config(size, threshold)
            for case in real_cases:
                candidates = candidate_rois(case.original, masks[case.paths.case_id], config)
                selected = nonoverlapping_rois(candidates, config)
                detail.append({
                    "case_id": case.paths.case_id,
                    "patient_id": _patient_id(case.paths.case_id),
                    "roi_size": size,
                    "profile": profile,
                    "max_structure_score": threshold,
                    "candidate_count": len(candidates),
                    "nonoverlap_count": len(selected),
                    "median_structure_score": float(np.median([roi.structure_score for roi in selected])) if selected else float("nan"),
                    "max_selected_structure_score": max((roi.structure_score for roi in selected), default=float("nan")),
                })
    summary: list[dict] = []
    for size in ROI_SIZES:
        for profile in profiles:
            group = [row for row in detail if row["roi_size"] == size and row["profile"] == profile]
            if not group:
                continue
            counts = np.asarray([row["nonoverlap_count"] for row in group])
            summary.append({
                "roi_size": size,
                "profile": profile,
                "cases": len(group),
                "median_rois": float(np.median(counts)),
                "min_rois": int(counts.min()),
                "pct_at_least_1": float(100 * np.mean(counts >= 1)),
                "pct_at_least_5": float(100 * np.mean(counts >= 5)),
                "pct_at_least_10": float(100 * np.mean(counts >= 10)),
                "pct_no_valid_roi": float(100 * np.mean(counts == 0)),
            })
    return detail, summary


def _sensitivity_configs(thresholds: dict[int, dict[str, float]]) -> list[tuple[str, NPSConfig]]:
    configs = [("baseline_16_unfiltered", _base_config(16))]
    for profile in THRESHOLD_QUANTILES:
        configs.append((f"roi32_{profile}", _base_config(32, thresholds[32][profile])))
    configs.append((PRIMARY_CONFIG, _base_config(24, thresholds[24]["permissive"])))
    for size in (24, 48, 64):
        configs.append((f"roi{size}_moderate", _base_config(size, thresholds[size]["moderate"])))
    return [(name, config) for name, config in configs if config.max_structure_score is None or np.isfinite(config.max_structure_score)]


def run_sensitivity(loaded: dict[str, dict], common: list[str], masks: dict[str, np.ndarray], configs):
    rows: list[dict] = []
    method_names = list(loaded)
    canonical = loaded[method_names[0]]
    for config_name, config in configs:
        for case_id in common:
            case = canonical[case_id]
            candidates = candidate_rois(case.original, masks[case_id], config)
            rois = nonoverlapping_rois(candidates, config)
            if not rois:
                continue
            real_nps = estimate_local_nps(case.original, rois, config)
            for method in method_names:
                synthetic = loaded[method][case_id].synthetic
                synthetic_nps = estimate_local_nps(synthetic, rois, config)
                comparison = compare_spectra(real_nps, synthetic_nps)
                std_ratio = comparison["noise_std_ratio"]
                composite = np.mean([
                    abs(math.log(max(std_ratio, np.finfo(float).eps))) / math.log(1.15),
                    abs(comparison["mean_frequency_delta_nyquist"]) / 0.05,
                    comparison["nps_shape_js_distance"] / 0.10,
                ])
                rows.append({
                    "config": config_name,
                    "case_id": case_id,
                    "patient_id": _patient_id(case_id),
                    "method": method,
                    "roi_size": config.roi_size,
                    "profile": "unfiltered" if config.max_structure_score is None else config_name.rsplit("_", 1)[-1],
                    "max_structure_score": config.max_structure_score,
                    "roi_count": len(rois),
                    "real_noise_std": real_nps.features["noise_std"],
                    "synthetic_noise_std": synthetic_nps.features["noise_std"],
                    **comparison,
                    "composite_distance": float(composite),
                })
    return rows


def _composite(comparison: dict[str, float]) -> float:
    return float(np.mean([
        abs(math.log(max(comparison["noise_std_ratio"], np.finfo(float).eps))) / math.log(1.15),
        abs(comparison["mean_frequency_delta_nyquist"]) / 0.05,
        comparison["nps_shape_js_distance"] / 0.10,
    ]))


def aggregate_cases_by_patient(case_rows: list[dict]) -> list[dict]:
    """Resume comparações pareadas por corte, sem supor ruído igual entre cortes.

    Cada corte é comparado primeiro com sua sintética nas mesmas coordenadas.
    Depois usamos a mediana dos cortes de cada paciente, dando peso igual a cada
    corte em vez de concatenar espectros de condições potencialmente distintas.
    """
    value_keys = (
        "real_noise_std", "synthetic_noise_std", "noise_std_ratio", "noise_std_delta_pct",
        "peak_frequency_delta", "mean_frequency_delta", "median_frequency_delta",
        "mean_frequency_delta_nyquist", "low_band_delta", "mid_band_delta", "high_band_delta",
        "anisotropy_delta", "periodic_peak_ratio", "nps_shape_rmse", "nps_shape_js_distance",
        "nps_log_curve_correlation",
    )
    rows: list[dict] = []
    groups = sorted({(row["config"], row["patient_id"], row["method"]) for row in case_rows})
    for config, patient, method in groups:
        subset = [
            row for row in case_rows
            if row["config"] == config and row["patient_id"] == patient and row["method"] == method
        ]
        roi_count = sum(int(row["roi_count"]) for row in subset)
        if roi_count < MIN_ANALYSIS_ROIS:
            continue
        values = {
            key: float(np.nanmedian([float(row[key]) for row in subset]))
            for key in value_keys
        }
        first = subset[0]
        rows.append({
            "config": config,
            "patient_id": patient,
            "method": method,
            "case_count": len(subset),
            "roi_count": roi_count,
            "roi_size": first["roi_size"],
            "profile": first["profile"],
            "max_structure_score": first["max_structure_score"],
            **values,
            "composite_distance": _composite(values),
        })
    return rows


def summarize_sensitivity(patient_rows: list[dict]) -> list[dict]:
    """Resume pacientes com peso igual, independentemente do número de cortes/ROIs."""
    keys = ("composite_distance", "noise_std_ratio", "mean_frequency_delta_nyquist", "nps_shape_js_distance", "nps_log_curve_correlation")
    summary: list[dict] = []
    for config, method in sorted({(row["config"], row["method"]) for row in patient_rows}):
        subset = [row for row in patient_rows if row["config"] == config and row["method"] == method]
        values = {key: float(np.median([row[key] for row in subset])) for key in keys}
        summary.append({
            "config": config,
            "method": method,
            "patients": len(subset),
            "cases": sum(row["case_count"] for row in subset),
            "median_rois_per_patient": float(np.median([row["roi_count"] for row in subset])),
            "min_rois_per_patient": min(row["roi_count"] for row in subset),
            **values,
        })
    for config in sorted({row["config"] for row in summary}):
        ranked = sorted((row for row in summary if row["config"] == config), key=lambda row: row["composite_distance"])
        for rank, row in enumerate(ranked, 1):
            row["composite_rank"] = rank
    return summary


def save_roi_examples(path: Path, real_cases: list, masks: dict[str, np.ndarray], threshold: float) -> None:
    config_all = _base_config(32)
    config_keep = _base_config(32, threshold)
    examples = []
    for case in real_cases:
        all_candidates = candidate_rois(case.original, masks[case.paths.case_id], config_all)
        accepted = nonoverlapping_rois(candidate_rois(case.original, masks[case.paths.case_id], config_keep), config_keep)
        rejected = [roi for roi in all_candidates if roi.structure_score > threshold]
        examples.append((case, accepted, rejected))
    examples.sort(key=lambda item: len(item[1]))
    indices = sorted(set(np.linspace(0, len(examples) - 1, min(6, len(examples)), dtype=int)))
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    for axis, index in zip(axes.ravel(), indices):
        case, accepted, rejected = examples[index]
        axis.imshow(case.original, cmap="gray")
        for roi in rejected[:12]:
            axis.add_patch(Rectangle((roi.x, roi.y), roi.size, roi.size, fill=False, ec="#e45756", lw=0.8, alpha=0.5))
        for roi in accepted[:12]:
            axis.add_patch(Rectangle((roi.x, roi.y), roi.size, roi.size, fill=False, ec="#2ca02c", lw=1.4))
        axis.set_title(f"{case.paths.case_id[-24:]}\n{len(accepted)} aceitas", fontsize=9)
        axis.axis("off")
    for axis in axes.ravel()[len(indices):]:
        axis.axis("off")
    fig.suptitle("ROI 32×32, threshold moderado — verde aceita; vermelho rejeitada por estrutura", fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _display_limits(image: np.ndarray, mask: np.ndarray | None = None) -> tuple[float, float]:
    """Janela robusta apenas para visualização (não altera a seleção)."""
    values = np.asarray(image, dtype=float)[mask] if mask is not None and np.any(mask) else np.asarray(image, dtype=float).ravel()
    return tuple(float(value) for value in np.percentile(values, (1, 99)))


def _diagnostic_case(real_cases: list, masks: dict[str, np.ndarray], threshold: float, roi_size: int = 32):
    """Escolhe automaticamente um corte com várias ROIs para a explicação visual."""
    config = _base_config(roi_size, threshold)
    ranked = []
    for case in real_cases:
        case_id = case.paths.case_id
        selected = nonoverlapping_rois(candidate_rois(case.original, masks[case_id], config), config)
        ranked.append((len(selected), case_id, case, selected))
    return max(ranked, key=lambda item: (item[0], item[1]))


def save_roi_walkthrough(
    path: Path,
    real_cases: list,
    masks: dict[str, np.ndarray],
    threshold: float,
    roi_size: int = 32,
    profile_label: str = "moderado",
) -> str:
    """Mostra máscara, threshold e a seleção final sem misturar as três etapas."""
    count, case_id, case, selected = _diagnostic_case(real_cases, masks, threshold, roi_size)
    mask = masks[case_id]
    all_candidates = candidate_rois(case.original, mask, _base_config(roi_size))
    accepted_candidates = [roi for roi in all_candidates if roi.structure_score <= threshold]
    rejected_candidates = [roi for roi in all_candidates if roi.structure_score > threshold]
    vmin, vmax = _display_limits(case.original)

    fig, axes = plt.subplots(1, 4, figsize=(20, 5.7), constrained_layout=True)
    for axis in axes:
        axis.imshow(case.original, cmap="gray", vmin=vmin, vmax=vmax)
        axis.axis("off")

    axes[0].set_title("1. CT real", fontweight="bold")

    overlay = np.zeros((*mask.shape, 4), dtype=float)
    overlay[mask] = (0.0, 0.85, 1.0, 0.42)
    axes[1].imshow(overlay)
    axes[1].set_title(f"2. Máscara de tecido mole\n{100 * mask.mean():.1f}% dos pixels", fontweight="bold")

    if all_candidates:
        scores = np.asarray([roi.structure_score for roi in all_candidates])
        norm = Normalize(vmin=float(scores.min()), vmax=float(max(scores.max(), threshold)))
        centers_x = [roi.x + roi.size / 2 for roi in all_candidates]
        centers_y = [roi.y + roi.size / 2 for roi in all_candidates]
        axes[2].scatter(centers_x, centers_y, c=scores, cmap="RdYlGn_r", norm=norm, s=14, alpha=0.8, linewidths=0)
    axes[2].set_title(
        f"3. Candidatas {roi_size}×{roi_size}\n{len(accepted_candidates)} passam; {len(rejected_candidates)} excedem o limiar",
        fontweight="bold",
    )

    for index, roi in enumerate(selected[:20], 1):
        axes[3].add_patch(Rectangle((roi.x, roi.y), roi.size, roi.size, fill=False, ec="#00e676", lw=2.0))
        axes[3].text(
            roi.x + 2,
            roi.y + 9,
            str(index),
            color="black",
            fontsize=7,
            fontweight="bold",
            bbox={"boxstyle": "circle,pad=0.15", "fc": "#00e676", "ec": "none", "alpha": 0.95},
        )
    axes[3].set_title(f"4. ROIs finais sem sobreposição\n{count} patches; até 20 mostrados", fontweight="bold")

    fig.suptitle(
        f"Como as ROIs são extraídas — ROI {roi_size}×{roi_size}, threshold {profile_label} = {threshold:.5f}\n{case_id}",
        fontsize=14,
        fontweight="bold",
    )
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return case_id


def save_extracted_patches(
    path: Path,
    case_id: str,
    loaded: dict[str, dict],
    masks: dict[str, np.ndarray],
    threshold: float,
    max_patches: int = 8,
    roi_size: int = 32,
) -> None:
    """Amplia os mesmos recortes na CT real e em cada imagem sintética."""
    method_names = list(loaded)
    case = loaded[method_names[0]][case_id]
    config = _base_config(roi_size, threshold)
    rois = nonoverlapping_rois(candidate_rois(case.original, masks[case_id], config), config)[:max_patches]
    columns = ["CT real", *method_names]
    images = [case.original, *(loaded[name][case_id].synthetic for name in method_names)]
    if not rois:
        return

    fig, axes = plt.subplots(len(rois), len(columns), figsize=(2.45 * len(columns), 2.25 * len(rois)), squeeze=False)
    for row, roi in enumerate(rois):
        patches = [image[roi.slices] for image in images]
        for column, (label, patch) in enumerate(zip(columns, patches)):
            axis = axes[row, column]
            vmin, vmax = (float(value) for value in np.percentile(patch, (1, 99)))
            axis.imshow(patch, cmap="gray", vmin=vmin, vmax=vmax, interpolation="nearest")
            axis.set_xticks([])
            axis.set_yticks([])
            if row == 0:
                axis.set_title(label, fontweight="bold")
            if column == 0:
                axis.set_ylabel(
                    f"ROI {row + 1}\n(x={roi.x}, y={roi.y})\nscore={roi.structure_score:.5f}",
                    fontsize=8,
                    rotation=0,
                    labelpad=47,
                    va="center",
                )
    fig.suptitle(
        "Recortes realmente enviados ao NPS\nAs coordenadas são idênticas; contraste ajustado por patch somente para visualização",
        fontsize=14,
        fontweight="bold",
    )
    fig.tight_layout(rect=(0.04, 0, 1, 0.97))
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def save_simple_summary(
    path: Path,
    viability: list[dict],
    patient_rows: list[dict],
    sensitivity: list[dict],
) -> None:
    """Cria um resumo visual em linguagem simples da análise recomendada."""
    primary_coverage = next(
        row for row in viability if row["roi_size"] == 24 and row["profile"] == "permissive"
    )
    secondary_coverage = next(
        row for row in viability if row["roi_size"] == 32 and row["profile"] == "moderate"
    )
    primary_patients = [row for row in patient_rows if row["config"] == PRIMARY_CONFIG and row["method"] == "DSR"]
    primary_methods = sorted(
        (row for row in sensitivity if row["config"] == PRIMARY_CONFIG),
        key=lambda row: row["composite_rank"],
    )
    secondary_methods = sorted(
        (row for row in sensitivity if row["config"] == SENSITIVITY_CONFIG),
        key=lambda row: row["composite_rank"],
    )

    fig = plt.figure(figsize=(16, 10), facecolor="white")
    grid = fig.add_gridspec(2, 2, height_ratios=(0.9, 1.1), hspace=0.36, wspace=0.28)

    coverage_axis = fig.add_subplot(grid[0, 0])
    labels = ["24×24 permissiva\n(principal)", "32×32 moderada\n(sensibilidade)"]
    any_values = [primary_coverage["pct_at_least_1"], secondary_coverage["pct_at_least_1"]]
    enough_values = [primary_coverage["pct_at_least_5"], secondary_coverage["pct_at_least_5"]]
    x = np.arange(2)
    coverage_axis.bar(x - 0.18, any_values, width=0.36, color="#5b8ff9", label="≥1 ROI no corte")
    coverage_axis.bar(x + 0.18, enough_values, width=0.36, color="#61b15a", label="≥5 ROIs no corte")
    for xpos, value in zip(np.r_[x - 0.18, x + 0.18], np.r_[any_values, enough_values]):
        coverage_axis.text(xpos, value + 2, f"{value:.0f}%", ha="center", fontsize=10, fontweight="bold")
    coverage_axis.set_ylim(0, 110)
    coverage_axis.set_ylabel("Cortes cobertos (%)")
    coverage_axis.set_xticks(x, labels)
    coverage_axis.set_title("1. Quantos cortes conseguimos aproveitar?", loc="left", fontweight="bold")
    coverage_axis.legend(frameon=False, loc="upper right")
    coverage_axis.spines[["top", "right"]].set_visible(False)

    patients_axis = fig.add_subplot(grid[0, 1])
    primary_patients.sort(key=lambda row: row["patient_id"])
    patient_labels = [f"Paciente {row['patient_id']}" for row in primary_patients]
    roi_counts = [row["roi_count"] for row in primary_patients]
    bars = patients_axis.barh(patient_labels, roi_counts, color="#5b8ff9")
    patients_axis.set_xscale("log")
    patients_axis.set_xlabel("ROIs 24×24 acumuladas (escala log)")
    patients_axis.set_title("2. Quantas caixinhas cada paciente forneceu?", loc="left", fontweight="bold")
    for bar, value in zip(bars, roi_counts):
        patients_axis.text(value * 1.08, bar.get_y() + bar.get_height() / 2, str(value), va="center", fontweight="bold")
    patients_axis.spines[["top", "right"]].set_visible(False)

    rank_axis = fig.add_subplot(grid[1, 0])
    rank_axis.axis("off")
    rank_axis.set_title("3. Qual método ficou mais parecido com a CT real?", loc="left", fontweight="bold")
    lines = ["ANÁLISE PRINCIPAL — 24×24 permissiva, 3 pacientes"]
    for row in primary_methods:
        lines.append(
            f"{int(row['composite_rank'])}º  {row['method']}: distância {row['composite_distance']:.2f}  "
            f"| ruído {row['noise_std_ratio']:.2f}× o real"
        )
    lines.extend(("", "SENSIBILIDADE — 32×32 moderada, apenas 2 pacientes"))
    for row in secondary_methods:
        lines.append(
            f"{int(row['composite_rank'])}º  {row['method']}: distância {row['composite_distance']:.2f}  "
            f"| ruído {row['noise_std_ratio']:.2f}× o real"
        )
    rank_axis.text(0, 0.94, "\n".join(lines), va="top", fontsize=12, linespacing=1.65, family="monospace")

    conclusion_axis = fig.add_subplot(grid[1, 1])
    conclusion_axis.axis("off")
    conclusion_axis.set_title("4. Tradução bem simples", loc="left", fontweight="bold")
    winner = primary_methods[0]
    conclusion = (
        "Pegamos pequenas caixinhas de tecido liso na CT real.\n"
        "Usamos as mesmas caixinhas nas três imagens sintéticas.\n"
        "Comparamos quantidade, tamanho do grão e forma do ruído.\n\n"
        f"Com 24×24, os 3 pacientes entram. O mais próximo foi {winner['method']}.\n"
        "Com 32×32, faltam dados de um paciente: serve só como conferência.\n\n"
        "IMPORTANTE: cada corte é comparado primeiro com seu próprio par.\n"
        "Depois resumimos os cortes; não fingimos que todos têm o mesmo ruído."
    )
    conclusion_axis.text(0, 0.94, conclusion, va="top", fontsize=13, linespacing=1.55)

    fig.suptitle("Estudo de ruído: o que coube e o que encontramos", fontsize=18, fontweight="bold", y=0.98)
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _markdown_table(rows: list[dict], fields: list[str]) -> str:
    if not rows:
        return "Sem resultados."
    header = "| " + " | ".join(fields) + " |"
    separator = "|" + "|".join("---" for _ in fields) + "|"
    body = []
    for row in rows:
        values = []
        for field in fields:
            value = row.get(field, "")
            values.append(f"{value:.3f}" if isinstance(value, float) else str(value))
        body.append("| " + " | ".join(values) + " |")
    return "\n".join((header, separator, *body))


def write_report(path: Path, viability: list[dict], sensitivity: list[dict], common: list[str], rejected: dict[str, list[dict]]) -> None:
    main_viability = [
        row for row in viability
        if row["profile"] in ("unfiltered", "moderate")
        or (row["roi_size"] == 24 and row["profile"] == "permissive")
    ]
    baseline = [row for row in sensitivity if row["config"] == "baseline_16_unfiltered"]
    primary = [row for row in sensitivity if row["config"] == PRIMARY_CONFIG]
    secondary = [row for row in sensitivity if row["config"] == SENSITIVITY_CONFIG]
    winners = [row for row in sensitivity if row.get("composite_rank") == 1]
    winner_text = ", ".join(f"{row['config']}: {row['method']} ({row['patients']} paciente(s))" for row in winners)
    winner_methods = {row["method"] for row in winners}
    stability_text = (
        f"O ranking foi estável: {next(iter(winner_methods))} venceu todas as configurações."
        if len(winner_methods) == 1
        else "O ranking não foi estável entre os tamanhos e thresholds; a conclusão anterior precisa ser apresentada como dependente da configuração."
    )
    full_patient_count = max((row["patients"] for row in sensitivity), default=0)
    limited = [row["config"] for row in winners if row["patients"] < full_patient_count]
    coverage_text = (
        "Configurações com cobertura parcial: " + ", ".join(limited) + "."
        if limited else "Todas as configurações incluíram a coorte completa."
    )
    text = f"""# Estudo de tamanho e homogeneidade das ROIs do NPS

Casos comuns aos métodos: **{len(common)}**. A seleção foi feita somente na CT real, no tecido mole liso fora do pulmão, e as mesmas coordenadas foram reutilizadas em todos os geradores. Sem metadados DICOM, as frequências continuam em ciclos/pixel.

![Resumo visual](simple_results.png)

![Etapas da extração 24×24](roi_extraction_walkthrough_24_permissive.png)

![Patches pareados 24×24](roi_extracted_patches_24_permissive.png)

## Conclusão curta

- Vencedor por configuração: {winner_text}.
- Um vencedor calculado com apenas um ou dois pacientes é exploratório, não uma confirmação da conclusão anterior.
- {stability_text}
- {coverage_text}

## Viabilidade

{_markdown_table(main_viability, ['roi_size', 'profile', 'cases', 'median_rois', 'pct_at_least_1', 'pct_at_least_5', 'pct_at_least_10', 'pct_no_valid_roi'])}

## Análise principal exploratória: 24×24 permissiva

Esta é a maior configuração testada que mantém os três pacientes. Cada corte é comparado primeiro com sua imagem sintética pareada; as métricas são resumidas por paciente sem concatenar os espectros de cortes distintos.

{_markdown_table(primary, ['method', 'patients', 'cases', 'median_rois_per_patient', 'min_rois_per_patient', 'noise_std_ratio', 'mean_frequency_delta_nyquist', 'nps_shape_js_distance', 'composite_distance', 'composite_rank'])}

## Conferência metodológica: 32×32 moderada

Esta configuração tem melhor resolução em frequência, mas inclui somente dois pacientes e permanece exploratória.

{_markdown_table(secondary, ['method', 'patients', 'cases', 'median_rois_per_patient', 'min_rois_per_patient', 'noise_std_ratio', 'mean_frequency_delta_nyquist', 'nps_shape_js_distance', 'composite_distance', 'composite_rank'])}

## Reprodução do baseline 16×16

{_markdown_table(baseline, ['method', 'patients', 'cases', 'median_rois_per_patient', 'noise_std_ratio', 'mean_frequency_delta_nyquist', 'nps_shape_js_distance', 'composite_distance', 'composite_rank'])}

## Sensibilidade e estabilidade do ranking

{_markdown_table(sensitivity, ['config', 'method', 'patients', 'cases', 'median_rois_per_patient', 'min_rois_per_patient', 'noise_std_ratio', 'mean_frequency_delta_nyquist', 'nps_shape_js_distance', 'composite_distance', 'composite_rank'])}

## Interpretação

- `composite_distance` é apenas um resumo transparente para ordenar os métodos: erro de magnitude / 15%, deslocamento de frequência / 5% de Nyquist e distância JS / 0,10, com pesos iguais. As três colunas componentes continuam sendo o resultado principal.
- A comparação real × sintética é calculada dentro de cada corte. Depois usamos a mediana dos cortes por paciente e a mediana dos pacientes na coorte.
- Os espectros de cortes diferentes não são concatenados; portanto, não presumimos que todos os cortes do paciente tenham o mesmo ruído.
- `strict`, `moderate` e `permissive` são os percentis 25, 50 e 75 do escore de estrutura, calibrados no conjunto real.
- Rejeições durante a leitura dos pares: {json.dumps({name: len(items) for name, items in rejected.items()}, ensure_ascii=False)}.
"""
    path.write_text(text, encoding="utf-8")


def run(args: argparse.Namespace) -> None:
    methods = args.method
    loaded, rejected, common = _load_aligned(methods, args.mask_dir, args.erosion_radius)
    canonical = loaded[methods[0][0]]
    real_cases = [canonical[case_id] for case_id in common]
    masks = {case.paths.case_id: soft_tissue_mask(case.original, case.lung_mask) for case in real_cases}
    args.output_dir.mkdir(parents=True, exist_ok=True)

    thresholds, threshold_rows = calibrate_thresholds(real_cases, masks)
    viability_detail, viability_summary = audit_viability(real_cases, masks, thresholds)
    configs = _sensitivity_configs(thresholds)
    sensitivity_rows = run_sensitivity(loaded, common, masks, configs)
    patient_rows = aggregate_cases_by_patient(sensitivity_rows)
    sensitivity_summary = summarize_sensitivity(patient_rows)

    _write_csv(threshold_rows, args.output_dir / "roi_thresholds.csv")
    _write_csv(viability_detail, args.output_dir / "roi_viability_by_case.csv")
    _write_csv(viability_summary, args.output_dir / "roi_viability_summary.csv")
    _write_csv(sensitivity_rows, args.output_dir / "nps_sensitivity_by_case.csv")
    _write_csv(patient_rows, args.output_dir / "nps_sensitivity_by_patient.csv")
    _write_csv(sensitivity_summary, args.output_dir / "nps_sensitivity_summary.csv")
    save_roi_examples(args.output_dir / "roi_examples_32_moderate.png", real_cases, masks, thresholds[32]["moderate"])
    diagnostic_case_id = save_roi_walkthrough(
        args.output_dir / "roi_extraction_walkthrough_32_moderate.png",
        real_cases,
        masks,
        thresholds[32]["moderate"],
    )
    save_extracted_patches(
        args.output_dir / "roi_extracted_patches_32_moderate.png",
        diagnostic_case_id,
        loaded,
        masks,
        thresholds[32]["moderate"],
    )
    primary_case_id = save_roi_walkthrough(
        args.output_dir / "roi_extraction_walkthrough_24_permissive.png",
        real_cases,
        masks,
        thresholds[24]["permissive"],
        roi_size=24,
        profile_label="permissivo",
    )
    save_extracted_patches(
        args.output_dir / "roi_extracted_patches_24_permissive.png",
        primary_case_id,
        loaded,
        masks,
        thresholds[24]["permissive"],
        roi_size=24,
    )
    save_simple_summary(
        args.output_dir / "simple_results.png",
        viability_summary,
        patient_rows,
        sensitivity_summary,
    )
    write_report(args.output_dir / "report.md", viability_summary, sensitivity_summary, common, rejected)
    protocol = {
        "methods": {name: str(path) for name, path in methods},
        "mask_dir": str(args.mask_dir),
        "common_cases": len(common),
        "roi_sizes": ROI_SIZES,
        "threshold_quantiles": THRESHOLD_QUANTILES,
        "minimum_rois_for_nps": MIN_ANALYSIS_ROIS,
        "thresholds": thresholds,
        "configs": {name: asdict(config) for name, config in configs},
        "frequency_unit": "ciclos/pixel",
        "selection_rule": "calibrada na CT real e reutilizada nas mesmas coordenadas em todos os métodos",
        "primary_analysis": PRIMARY_CONFIG,
        "sensitivity_analysis": SENSITIVITY_CONFIG,
        "aggregation_rule": "comparação pareada por corte; mediana dos cortes por paciente; mediana dos pacientes na coorte",
    }
    (args.output_dir / "protocol.json").write_text(json.dumps(protocol, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Estudo concluído: {len(common)} casos; relatório em {args.output_dir / 'report.md'}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--method", action="append", type=_parse_method, required=True, help="NOME=PASTA; repita para cada gerador")
    result.add_argument("--mask-dir", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--erosion-radius", type=int, default=2)
    return result


def main() -> None:
    run(parser().parse_args())


if __name__ == "__main__":
    main()
