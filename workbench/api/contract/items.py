"""Itens do contrato genérico (§4.1): `GET /api/items?dataset=&version=`.

Cada item é o `data.slice_json` de um corte reescrito na forma genérica: vereditos e técnicas por
eixo de `AXES`, métricas por chave, motivos com eixo e nota em texto, e `facts` no lugar dos
campos avulsos (`noise_roi_count`, `wavelet_type`, `pair_mode`, `density`).
Números não finitos já chegam como None de `slice_json`; métrica sem leitura sai `available: false`
com valor, z, IC e % nulos, e seus motivos carregam só a nota (Review Focus 2).
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from frameworks.texture_evaluator import regional
from workbench.api import data, datasets as ds, reasons
from workbench.api.contract import AXES, DATASET_LABEL

NOTE_LABEL = {reasons.NOTE_FEW_WINDOWS: "too few windows to measure", reasons.NOTE_LUNG: "lung area not measured",
              reasons.NOTE_AIR: "air not available", reasons.NOTE_CI: "interval includes zero"}
# códigos de `data.WAVELET_CODE` -> texto da UI
WAVELET_LABEL = {"preserved": "preserved texture", "blurred": "blurred", "noise": "noise",
                 "lost_contrast": "lost contrast", "gained_contrast": "gained contrast", "saturated": "saturated"}
NA = "n/a"


def _ci(low, high) -> list | None:
    return None if low is None or high is None else [low, high]


def _available(metric: dict) -> bool:
    """Sem leitura (valor nulo) ou marcada indisponível (ar) → indisponível."""
    return metric["value"] is not None and metric.get("available", True) is not False


def _metric(metric: dict) -> dict:
    available = _available(metric)
    # ui_placar.py: air_chart tooltip (pico em múltiplos do ruído natural da própria CT).
    peak = metric.get("peak_sigmas")
    note = f"Peak: {peak:.1f} × natural noise" if available and peak is not None else None
    return {"value": metric["value"] if available else None,
            "z": metric["z"] if available else None,
            "ci": _ci(metric["z_low"], metric["z_high"]) if available else None,
            "real": metric["real"], "synthetic": metric["synthetic"],
            "pct": metric["pct_of_original"] if available else None,
            "status": metric["status"], "available": available, "note": note}


def _reason(axis: str, entry: dict, available: bool) -> dict:
    """Métrica indisponível: nenhum número no motivo (a UI mostra só a nota)."""
    numbers = available and entry["value"] is not None
    return {"axis": axis, "metric": entry["metric"], "status": entry["status"],
            "value": entry["value"] if numbers else None,
            "z": entry["z"] if numbers else None,
            "ci": _ci(entry["z_low"], entry["z_high"]) if numbers else None,
            "limit": entry["limit"],
            "limit_value": entry["limit_value"] if numbers else None,
            "direction": entry["direction"] if numbers else None,
            "note": NOTE_LABEL.get(entry["note"], entry["note"])}


def _density(density: dict) -> str:
    """Status da densidade e, quando finito, o deslocamento da mediana: "ok · −0.04 IQR"."""
    text = density["status"].replace("_", " ")
    shift = density["median_shift_iqr"]
    return text if shift is None else f"{text} · {shift:.2f} IQR".replace("-", "−")


def _pairing(mode_code: str | None) -> str:
    # ui_placar.py:1563; threshold comes from the frozen judge, never a UI constant.
    if mode_code == "same_anatomy":
        return f"Same anatomy · correlation below {regional.PAIR_MIN_CORRELATION:g} flags a suspicious pair"
    if mode_code == "mask_only":
        return "Mask only · no spatial comparison: matching contours do not imply matching anatomy"
    return NA if mode_code is None else DATASET_LABEL.get(mode_code.replace("_", " "), mode_code)


def _facts(s: dict) -> list[dict]:
    rois = s["noise_roi_count"]
    code = s["wavelet_type_code"]
    return [{"label": "Noise ROIs", "value": NA if rois is None else str(rois)},
            {"label": "Wavelet type", "value": WAVELET_LABEL.get(code, s["wavelet_type"] or NA)},
            {"label": "Pairing", "value": _pairing(s["mode_code"])},
            {"label": "Density", "value": _density(s["density"])}]


def item_json(slice: dict) -> dict:  # noqa: A002 (nome do contrato)
    axes = [key for key, _ in AXES]
    metrics = {m["key"]: _metric(m) for m in slice["metrics"]}
    return {
        "id": slice["case_id"],
        "label": slice["label"],
        "group": None if slice["patient"] == "?" else slice["patient"],
        "verdicts": {axis: slice[axis]["verdict"] for axis in axes},
        "techniques": {axis: slice[axis]["techniques"] for axis in axes},
        "metrics": metrics,
        "reasons": [_reason(axis, entry, metrics[entry["metric"]]["available"])
                    for axis in axes for entry in slice["why"][axis]],
        "facts": _facts(slice),
    }


def router(datasets: dict) -> APIRouter:
    api = APIRouter()

    @api.get("/api/items")
    def items(version: str = Query(...), dataset: str = Query(ds.DEFAULT)):
        wb = ds.wb_for(dataset, datasets)
        calibration = wb.history["calibration"]
        return {"version": version, "items": [item_json(data.slice_json(row, calibration)) for row in wb.rows(version)]}

    return api
