"""Benchmark do contrato genérico (§4.3): `GET /api/board` e `GET /api/transitions`.

Reescreve na forma genérica o que já existe, sem recalcular nada:
- contagens, `scores` e comparação com a linha de base vêm de `board.board_json` (memoizado);
- coorte vem de `compare.cohort` (Wilcoxon do NEx pareado, porte de `ui_placar.py:1431-1437`);
- transições vêm de `compare.transitions`, com `axis` sendo qualquer chave de `AXES`.
A linha de base padrão é a do laboratório (`versions.lab_baseline`), senão `data.default_baseline`;
`/api/schema` usa a mesma regra (`default_baseline`).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from workbench.api import board, compare, data, datasets as ds
from workbench.api.contract import AXES
from workbench.api.contract import versions as cv
from workbench.api.datasets import DEFAULT

# texto em inglês de `board.RESULT` -> vocabulário do contrato
RESULT = {"improved": "improved", "worse": "worse", "small change": "small",
          "no clear difference": "same", "n/a": "same"}
REFERENCE_SUBTITLE = "ruler reference"
COHORT_TEST = "nex_shift"  # schema.COHORT_TESTS
NA = "n/a"


def default_baseline(history: dict) -> str:
    """Linha de base padrão do benchmark e do schema: a do laboratório, senão a padrão do histórico."""
    return cv.lab_baseline(history) or data.default_baseline(history)


def _number(value, fmt: str) -> str:
    return NA if value is None else format(value, fmt)


def cohort_entry(stat: dict) -> dict:
    """Resultado do teste de coorte a partir de `compare.cohort(...)["nex_test"]`.

    Sistemático (p < 0.05): revisão; testado sem desvio: aprovado; sem valores suficientes: inconclusivo.
    Textos traduzidos de `ui_placar.py:1434-1436`.
    """
    if stat["systematic"]:
        tendency = {"higher": "NEx tends to be higher", "lower": "NEx tends to be lower"}.get(stat["direction"])
        result = {"label": "Systematic deviation" + (f": {tendency}" if tendency else ""), "status": "review"}
    elif stat["p"] is None:
        result = {"label": "Too few values to test", "status": "inconclusive"}
    else:
        result = {"label": "No systematic deviation", "status": "approved"}
    p = stat["p"]
    p_text = NA if p is None else format(p, ".3f" if p < compare.NEX_ALPHA else ".2f")  # como ui_placar.py:1435-1436
    return {"test": COHORT_TEST, "result": result,
            "detail": [{"label": "p", "value": p_text},
                       {"label": "median z", "value": _number(stat["median_z"], ".2f")},
                       {"label": "n", "value": str(stat["n"])}]}


def _vs_baseline(entries: list[dict] | None) -> list[dict] | None:
    if entries is None:
        return None
    return [{"indicator": e["indicator"], "gain": e["gain"], "ci": e["ci"], "result": RESULT[e["result"]]}
            for e in entries]


def board_contract(wb: data.Workbench, baseline: str | None = None) -> dict:
    """§4.3: uma linha por versão do placar (cortes comuns), na ordem do placar."""
    history = wb.history
    baseline = baseline or default_baseline(history)
    source = board.board_json(wb, baseline)  # versão desconhecida: 404
    meta = cv.load_meta(Path(wb.history_dir))
    versions = []
    for generator in source["generators"]:
        name = generator["name"]
        is_reference = name == history.get("reference")
        is_baseline = name == baseline
        versions.append({
            "name": name,
            "label": cv.version_label(name, history, meta),
            "subtitle": REFERENCE_SUBTITLE if is_reference else "",
            "is_reference": is_reference,
            "provenance": (meta.get(name) or {}).get("provenance"),
            "counts": {axis: dict(generator["counts"][axis]) for axis, _ in AXES},
            "scores": generator["scores"],
            "vs_baseline": _vs_baseline(generator["vs_baseline"]),
            "cohort": [] if is_baseline else [cohort_entry(compare.cohort(wb, name)["nex_test"])],
        })
    return {"n_items": source["n_cases"], "baseline": baseline, "versions": versions}


def transitions_contract(wb: data.Workbench, before: str, after: str, axis: str) -> list[dict]:
    if axis not in {key for key, _ in AXES}:
        raise HTTPException(400, f"unknown axis: {axis}")
    wb.entry(before)  # desconhecida: 404
    wb.entry(after)
    return [{"id": t["case_id"], "before": t["before"], "after": t["after"], "change": t["change"],
             "became_approved": t["became_approved"]} for t in compare.transitions(wb, before, after, axis)]


def router(datasets: dict) -> APIRouter:
    api = APIRouter()

    def _wb(dataset: str) -> data.Workbench:
        return ds.wb_for(dataset, datasets)

    @api.get("/api/board")
    def board_route(dataset: str = Query(DEFAULT), baseline: str | None = Query(None)):
        return board_contract(_wb(dataset), baseline)

    @api.get("/api/transitions")
    def transitions_route(before: str = Query(...), after: str = Query(...), axis: str = Query(...),
                          dataset: str = Query(DEFAULT)):
        return transitions_contract(_wb(dataset), before, after, axis)

    return api
