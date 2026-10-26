"""Motivos estruturados do veredito: uma entrada por métrica que não ficou aprovada.

Portado (somente leitura) das condições de `frameworks/texture_evaluator/ui_placar.py`:
- `glcm_brightness_why` e `wavelet_brightness_why` (linhas 162-181): Sat31 acima de 15%,
  |Δμ| e LL em IQR entre os limites de revisão (1) e rejeição (2);
- `technique_why` (linhas 313-333): NEx inconclusivo por poucas janelas e NEx fora de ±1 IQR;
- `noise_reason` (`frameworks/noise_evaluator/integration.py`): quais leituras do ruído pesam
  e quando a medida não existe (pulmão ou ar não medidos).

Os textos do framework não são copiados: o motivo sai como dado (técnica, métrica, status,
limite cruzado, sentido e nota). Os limites de IQR vêm do próprio status de cada métrica,
calculado em `data.py` com as mesmas regras de `decision.metric_status`.
"""
from __future__ import annotations

import math

# Sat31 acima deste valor (%) rejeita o brilho: `ui_placar.py:42` (OFFICIAL_SATURATION)
# e `run_mvp.py:88`.
SATURATION_LIMIT = 15.0

LIMIT = {"review": "review", "rejected": "reject"}
GROUPS = ("brightness", "texture", "noise")
NOTE_FEW_WINDOWS = "few_windows"
NOTE_LUNG = "lung_not_measured"
NOTE_AIR = "air_unavailable"
NOTE_CI = "ci_includes_zero"
# métricas em que um status não aprovado sempre significa valor acima do limite
ALWAYS_HIGHER = {"sat31", "nps_air"}


def _finite(value) -> float | None:
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else None


def _direction(metric: dict) -> str | None:
    z = _finite(metric.get("z"))
    if z is not None and z != 0:
        return "higher" if z > 0 else "lower"
    if metric["key"] in ALWAYS_HIGHER:
        return "higher"
    return None


def _note(metric: dict) -> str | None:
    """Por que a leitura não pesa ou não existe; nota de intervalo só para métrica não aprovada."""
    key, status = metric["key"], metric["status"]
    if status == "inconclusive":
        if key == "nex":
            return NOTE_FEW_WINDOWS
        if key == "nps_air":
            return NOTE_AIR
        return NOTE_LUNG
    low, high = metric.get("z_low"), metric.get("z_high")
    if low is not None and high is not None and low <= 0 <= high:
        return NOTE_CI
    return None


def entry(metric: dict) -> dict:
    """Um motivo: a métrica como o corte a mediu e o limite que ela cruzou."""
    return {
        "technique": metric["technique"],
        "metric": metric["key"],
        "status": metric["status"],
        "value": metric["value"],
        "z": metric["z"],
        "z_low": metric.get("z_low"),
        "z_high": metric.get("z_high"),
        "limit": LIMIT.get(metric["status"]),
        "direction": _direction(metric),
        "note": _note(metric),
    }


def why(metrics: list[dict]) -> dict[str, list[dict]]:
    """Motivos por grupo (brilho, textura, ruído), só para métricas com status diferente de aprovado."""
    out: dict[str, list[dict]] = {group: [] for group in GROUPS}
    for metric in metrics:
        if metric["status"] != "approved":
            out[metric["group"]].append(entry(metric))
    return out
