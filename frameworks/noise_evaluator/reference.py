"""Perfil de referência para comparar novas versões do gerador."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

import numpy as np

from .core import NPSConfig


REFERENCE_METRICS = (
    "noise_std_ratio",
    "noise_std_delta_pct",
    "mean_frequency_delta_nyquist",
    "low_band_delta",
    "mid_band_delta",
    "high_band_delta",
    "anisotropy_delta",
    "periodic_peak_ratio",
    "nps_shape_rmse",
    "nps_shape_js_distance",
    "nps_log_curve_correlation",
)


def _summary(values: np.ndarray) -> dict[str, float]:
    p5, p25, median, p75, p95 = np.percentile(values, (5, 25, 50, 75, 95))
    return {
        "p5": float(p5),
        "p25": float(p25),
        "median": float(median),
        "p75": float(p75),
        "p95": float(p95),
        "iqr": float(p75 - p25),
    }


def build_reference_profile(rows: list[dict], config: NPSConfig, dataset_name: str, pair_mode: str) -> dict:
    metrics = {}
    for key in REFERENCE_METRICS:
        values = np.asarray([float(row[key]) for row in rows if np.isfinite(float(row[key]))])
        if values.size:
            metrics[key] = _summary(values)
    return {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_name": dataset_name,
        "case_count": len(rows),
        "pair_mode": pair_mode,
        "method": "local-nps-proxy",
        "config": {
            "roi_size": config.roi_size,
            "stride": config.stride,
            "min_tissue": config.min_tissue,
            "min_rois": config.min_rois,
            "max_rois": config.max_rois,
            "structure_sigma": config.structure_sigma,
            "pixel_spacing_mm": config.pixel_spacing_mm,
        },
        "metrics": metrics,
        "interpretation": "Faixa descritiva P5–P95 da base de referência; não é limiar clínico de aprovação.",
    }


def save_reference_profile(profile: dict, path: Path) -> None:
    path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


def load_reference_profile(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def apply_reference_profile(rows: list[dict], profile: dict) -> None:
    metrics = profile.get("metrics", {})
    for row in rows:
        outside = 0
        distances = []
        for key, summary in metrics.items():
            if key not in row or not np.isfinite(float(row[key])):
                continue
            value = float(row[key])
            outside += int(value < summary["p5"] or value > summary["p95"])
            scale = max(float(summary["iqr"]), (float(summary["p95"]) - float(summary["p5"])) / 3.29, np.finfo(float).eps)
            distance = abs(value - float(summary["median"])) / scale
            row[f"reference_{key}_iqr_distance"] = float(distance)
            distances.append(distance)
        row["reference_outside_p5_p95_count"] = outside
        row["reference_max_iqr_distance"] = float(max(distances)) if distances else float("nan")
