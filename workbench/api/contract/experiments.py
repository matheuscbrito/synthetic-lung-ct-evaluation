"""Contrato §4.5 (`GET /api/experiments`): experimentos do caderno do lab, somente leitura.

Adaptador do CADERNO.md (`workbench.api.notebook`). Regras portadas de docs/planning/mockups-v3/bundle_real.py
(seção "experiments"): palavras de veredito viram estados do contrato; a pontuação vem das colunas de escopo.
Ids e textos passam intactos; o agente aposentado não tem campo de autoria nem de busca.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from workbench.api import notebook
from workbench.api.contract.runs import finite

OBJECTIVE = {"label": "Improvement vs baseline", "unit": "%", "goal": 15}
SCOPES = [{"key": str(n), "label": f"{n} slices"} for n in (5, 7, 10, 37)]
OUTCOME = {
    "melhor": ("approved", "Better"),
    "pior": ("rejected", "Worse"),
    "insuficiente": ("review", "Not enough"),
    "quase": ("inconclusive", "No effect"),
    "interrompida": ("inconclusive", "Interrupted"),
    "nota": ("inconclusive", "Reference"),
}


def _outcome(verdict: str) -> dict:
    status, label = OUTCOME.get(verdict, ("inconclusive", verdict))
    return {"status": status, "label": label}


def _scores(row: dict) -> dict:
    """Três valores são os escopos 5, 10 e 37; um valor vai para o escopo da linha (37 se não houver)."""
    vals = row["vals"]
    if len(vals) == 3:
        return dict(zip(("5", "10", "37"), vals))
    if len(vals) == 1:
        return {str(row["scope"] or 37): vals[0]}
    return {}


def _experiment(row: dict) -> dict:
    return {
        "id": row["id"],
        "parent": None if row["base"] == "baseline" else row["base"],
        "change": row["change"],
        "outcome": _outcome(row["verdict"]),
        "scores": _scores(row),
        "is_best": row["best"],
        "note": row["reason"],
    }


def router(datasets: dict) -> APIRouter:
    api = APIRouter()

    @api.get("/api/experiments")
    def experiments():
        result = notebook.read_caderno(notebook.LAB_DIR)
        source = result["source"]
        if not source["exists"]:
            raise HTTPException(status_code=404, detail="CADERNO.md not found")
        parsed = result["parsed"] or {"rows": [], "metrics": [], "learned": [], "next": []}
        rows = parsed["rows"]
        best = next((row["id"] for row in rows if row["best"]), None)
        return finite({
            "source": {"label": "CADERNO.md", "path": source["path"]},
            "objective": OBJECTIVE,
            "scopes": SCOPES,
            "experiments": [_experiment(row) for row in rows],
            "tables": [{
                "title": "Per-metric improvement · 37 slices",
                "for": best,
                "columns": ["Metric", "Current best", "Other lineage"],
                "rows": [[metric["name"], metric["best"], metric["other"]] for metric in parsed["metrics"]],
            }] if best else [],
            "sections": [
                {"title": "What we learned", "items": [{"head": item["head"], "body": item["body"]} for item in parsed["learned"]]},
                {"title": "Next search", "items": [{"head": None, "body": text} for text in parsed["next"]]},
            ],
        })

    return api
