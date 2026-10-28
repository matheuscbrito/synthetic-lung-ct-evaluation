"""Calibração do workbench: réguas do histórico e constantes do juiz, por dataset.

Valores de `history["calibration"]` (ver `ui_placar.calibration_limits`: revisão = mean_iqr, rejeição = 2·mean_iqr)
e das constantes do framework: `noise_evaluator.integration.AIR_LIMITS` / `AIR_SIGMAS`,
`texture_evaluator.regional.PAIR_MIN_CORRELATION`, chaves de `texture_evaluator.visual.TECHNIQUE_FIGURES` e
`MAP_LAYERS`. Os limites de Sat31 e de |z| vêm de `reasons.py` (`SATURATION_LIMIT` e `Z_LIMITS`), que os
conferem com `ui_placar.OFFICIAL_SATURATION` e `decision.metric_status` nos testes.
Ausência de régua (histórico desatualizado) vira `null`, nunca erro.
"""
from __future__ import annotations

from frameworks.noise_evaluator.integration import AIR_LIMITS, AIR_SIGMAS
from frameworks.texture_evaluator import placar, regional, visual
from workbench.api import reasons


def _float_or_none(value):
    return None if value is None else float(value)


def calibration_json(history: dict) -> dict:
    cal = history.get("calibration", {})
    mean_iqr = _float_or_none(cal.get("mean_iqr"))
    nex = cal.get("nex_reference") or {}
    nps_metrics = (cal.get("nps_reference") or {}).get("metrics") or {}
    body = {
        "reference": history.get("reference"),
        "n_cases": len(history.get("originals", [])),
        "mean_iqr": mean_iqr,
        "delta_mu": {"review": mean_iqr, "reject": None if mean_iqr is None else 2 * mean_iqr},
        "sat31_limit": reasons.SATURATION_LIMIT,
        "z_limits": dict(reasons.Z_LIMITS),
        "nex": {"iqr": _float_or_none(nex.get("iqr")), "repeatability_iqr": _float_or_none(nex.get("repeatability_iqr"))},
        "nps": {key: {"repeatability_iqr": _float_or_none(metric.get("repeatability_iqr"))}
                for key, metric in nps_metrics.items()},
        "air": {"limits": list(AIR_LIMITS), "sigmas": AIR_SIGMAS},
        "pair_min_correlation": regional.PAIR_MIN_CORRELATION,
        "technique_figures": list(visual.TECHNIQUE_FIGURES),
        "map_layers": list(visual.MAP_LAYERS),
    }
    return placar.json_value(body)
