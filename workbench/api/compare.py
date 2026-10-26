"""Comparação entre versões do placar: transições corte a corte e estatística de coorte.

- `transitions`: muda a classificação de cada corte entre duas versões (brilho, textura ou ruído).
  A gravidade e a regra de "passou a aprovada" vêm de `TRANSITION_SEVERITY` em
  `frameworks/texture_evaluator/ui_placar.py` (linhas 254-291), portado (somente leitura):
  aprovada = 0, revisão = 1, inconclusivo = 1 (revisão), reprovada = 2.
- `cohort`: teste de Wilcoxon do NEx pareado da versão contra a própria original (n ≥ 10 não nulos,
  p < 0.05), como em `ui_placar.py:1431-1437` (crédito: mesma lógica, sem alterar o framework).
  Também conta os tipos de wavelet da versão.

Os vereditos saem de `data.slice_json`, sem recalcular nada aqui. Cortes são os cortes comuns do placar.
"""
from __future__ import annotations

from collections import Counter
from typing import Literal

import numpy as np
from fastapi import APIRouter, Query
from scipy.stats import wilcoxon

from frameworks.texture_evaluator import placar
from workbench.api import data, datasets as ds
from workbench.api.datasets import DEFAULT

# ui_placar.TRANSITION_SEVERITY, na escala de códigos da API (inconclusive = review)
TRANSITION_SEVERITY = {"approved": 0, "review": 1, "inconclusive": 1, "rejected": 2}
NEX_MIN_N = 10  # ui_placar.py:1432 (valores não nulos)
NEX_ALPHA = 0.05


def _finite(values) -> np.ndarray:
    out = np.array([data._num(v) for v in values], dtype=float)
    return out[np.isfinite(out)]


def transitions(wb: data.Workbench, before: str, after: str, verdict: str) -> list[dict]:
    old = {row["case_id"]: row for row in wb.board["rows"][before]}
    new = {row["case_id"]: row for row in wb.board["rows"][after]}
    calibration = wb.history["calibration"]
    out = []
    for case_id in sorted(old.keys() & new.keys()):
        previous = data.slice_json(old[case_id], calibration)[verdict]["verdict"]
        current = data.slice_json(new[case_id], calibration)[verdict]["verdict"]
        delta = TRANSITION_SEVERITY[current] - TRANSITION_SEVERITY[previous]
        out.append({
            "case_id": case_id,
            "label": data.slice_label(case_id),
            "before": previous,
            "after": current,
            "change": "improved" if delta < 0 else "worsened" if delta > 0 else "same",
            "became_approved": previous != "approved" and current == "approved",
        })
    return out


def cohort(wb: data.Workbench, version: str) -> dict:
    """Wilcoxon do NEx pareado (porte de ui_placar.py:1431-1437) e contagem de tipos de wavelet."""
    wb.entry(version)  # desconhecida: 404
    rows = wb.board["rows"][version]
    calibration = wb.history["calibration"]
    nex = _finite(row.get("nex_z") for row in rows)
    stat = {"n": int(nex.size), "p": None, "median_z": None, "systematic": False, "direction": None}
    if nex.size and np.any(nex != 0):
        stat["median_z"] = placar.json_value(float(np.median(nex)))
    if nex.size >= NEX_MIN_N and np.any(nex != 0):
        p = float(wilcoxon(nex).pvalue)
        median = float(np.median(nex))
        stat.update(p=placar.json_value(p), systematic=p < NEX_ALPHA,
                    direction="higher" if median > 0 else "lower" if median < 0 else None)
    types = Counter(data.slice_json(row, calibration)["wavelet_type"] for row in rows)
    return {"nex_test": stat, "wavelet_types": dict(types)}


def router(datasets: dict) -> APIRouter:
    api = APIRouter()

    def _wb(dataset: str) -> data.Workbench:
        return ds.wb_for(dataset, datasets)

    @api.get("/api/transitions")
    def transitions_route(before: str = Query(...), after: str = Query(...),
                          verdict: Literal["brightness", "texture", "noise"] = Query(...),
                          dataset: str = Query(DEFAULT)):
        wb = _wb(dataset)
        wb.entry(before)  # desconhecida: 404
        wb.entry(after)
        return transitions(wb, before, after, verdict)

    @api.get("/api/cohort")
    def cohort_route(version: str = Query(...), dataset: str = Query(DEFAULT)):
        wb = _wb(dataset)
        return cohort(wb, version)

    return api
