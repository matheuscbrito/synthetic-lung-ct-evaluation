"""Contrato §4.4 (`GET /api/runs`): execuções dos otimizadores em uso, a partir de `optimizers` (somente leitura).

Adaptador do formato do lab (`*-log.jsonl` + `*-resumo.json`). Regras portadas de
docs/planning/mockups-v3/bundle_real.py (seção "optimizer runs"): o agente aposentado fica de fora,
os vereditos viram estados do contrato e os parâmetros são as chaves do candidato que variam entre passos.
"""
from __future__ import annotations

import json
import math

from fastapi import APIRouter

from workbench.api import optimizers

RETIRED = ("agente",)
OBJECTIVE = {"label": "Improvement vs start", "unit": "%", "goal": 15, "higher_is_better": True}
PARAM_LABELS = {"steps": "steps", "noise_level": "noise", "eta": "eta",
                "latent_noise_scale": "latent", "conditioning_noise_scale": "cond"}
BEST_ONLY = ("sampler",)  # aparece em best_params, nunca como coluna de passo
OUTCOME = {"melhor": ("approved", "Better"), "pior": ("rejected", "Worse"), "insuficiente": ("review", "Not enough")}

def finite(value):
    """Números não finitos viram null no fio; o resto passa intacto (ids e textos não são convertidos)."""
    if isinstance(value, dict):
        return {key: finite(item) for key, item in value.items()}
    if isinstance(value, list):
        return [finite(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _outcome(verdict) -> dict:
    status, label = OUTCOME.get(verdict, ("inconclusive", verdict))
    return {"status": status, "label": label}


def _varying(candidates: list[dict]) -> list[str]:
    return [key for key in PARAM_LABELS if len({json.dumps(c.get(key)) for c in candidates}) > 1]


def _best_candidate(summary: dict | None, steps: list[dict]) -> dict:
    best = (summary or {}).get("best")
    if isinstance(best, dict):
        return best
    new_best = [step for step in steps if step.get("new_best")]
    source = new_best[-1] if new_best else (steps[-1] if steps else {})
    return source.get("candidate") or {}


def _run_summary(method: dict, steps: list[dict], curve: list[dict]) -> dict:
    """Resumo do método; campo ausente do `resumo` cai no último ponto da curva (ou nos passos)."""
    summary = method["summary"] or {}
    last = curve[-1] if curve else {}
    evaluated = summary.get("configs_measured")
    if evaluated is None:
        evaluated = len({step.get("config_index") for step in steps})
    best = summary.get("best_full_improvement_pct")
    if best is None:
        best = last.get("best_full_improvement_pct")
    used = summary.get("cases_used")
    if used is None:
        used = last.get("cases")
    return {"best": best, "evaluated": evaluated, "used": used, "budget": summary.get("budget")}


def _run(method: dict, varying: list[str]) -> dict:
    steps, curve = method["steps"], method["curve"]
    best = _best_candidate(method["summary"], steps)
    return {
        "key": method["method"],
        "label": method["label"],
        "summary": _run_summary(method, steps, curve),
        "best_params": {key: best[key] for key in varying + list(BEST_ONLY) if key in best},
        "curve": [{"x": point["cases"], "y": point["best_full_improvement_pct"]} for point in curve],
        "steps": [{
            "id": str(step.get("config_index")),
            "stage": step.get("scope"),
            "params": {key: (step.get("candidate") or {}).get(key) for key in varying},
            "score": step.get("mean_improvement_pct"),
            "outcome": _outcome(step.get("verdict")),
            "wins": step.get("case_wins"),
            "losses": step.get("case_losses"),
            "is_best": bool(step.get("new_best")),
        } for step in steps],
    }


def router(datasets: dict) -> APIRouter:
    api = APIRouter()

    @api.get("/api/runs")
    def runs():
        base = optimizers.RESULTS_DIR
        methods = []
        if base.is_dir():
            for method, label, prefix in optimizers.METHODS:
                if method in RETIRED:
                    continue
                entry, _ = optimizers._method(method, label, prefix, base)
                if entry is not None:
                    methods.append(entry)
        candidates = [step["candidate"] for method in methods for step in method["steps"] if step.get("candidate")]
        varying = _varying(candidates)
        return finite({
            "sources": [{"label": "lung-agent-lab logs", "path": str(base), "exists": base.is_dir()}],
            "objective": OBJECTIVE,
            "budget_axis": {"label": "cases generated"},
            "params": [{"key": key, "label": PARAM_LABELS[key]} for key in varying],
            "runs": [_run(method, varying) for method in methods],
        })

    return api
