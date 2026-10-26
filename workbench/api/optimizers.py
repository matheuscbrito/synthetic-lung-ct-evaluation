"""Experimentos dos otimizadores (GP-BO, Nelder-Mead e agente), lidos dos logs do lung-agent-lab (somente leitura).

Os logs `*-log.jsonl` trazem um evento por linha: `etapa` (passo medido), `cache` (medida reaproveitada),
`baseline` e `inicio`. Os resumos `*-resumo.json` trazem o orçamento e a melhor configuração. Vereditos e
razões vêm prontos do lab; nada é recalculado aqui. Linhas malformadas são puladas e contadas em `skipped`.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter

from frameworks.texture_evaluator import placar
from workbench.api import notebook

RESULTS_DIR = Path(os.environ.get("OPTIMIZER_RESULTS", notebook.LAB_DIR / "resultados" / "otimizador-real"))

# (método, rótulo na interface, prefixo dos arquivos em RESULTS_DIR)
METHODS = (
    ("gp", "GP-BO", "gpbo"),
    ("nm", "Nelder-Mead", "nm"),
    ("agente", "Agent (retired)", "agente"),
)
CURVE_EVENTS = ("baseline", "cache", "etapa")
SUMMARY_FIELDS = ("budget", "cases_used", "configs_measured", "best_full_improvement_pct", "best")
STEP_FIELDS = (
    "config_index", "scope", "candidate", "mean_improvement_pct", "metric_improvement_pct", "verdict",
    "reason", "case_wins", "case_losses", "rejected", "pair_issues", "new_best", "cases_generated",
    "cases_cumulative",
)

router = APIRouter()


def _read_log(path: Path) -> tuple[list[dict], int]:
    """Eventos do JSONL e quantas linhas não viraram objeto JSON (linhas em branco não contam).

    Arquivo que não pode ser lido conta como uma linha pulada, como `_summary` trata o resumo.
    """
    try:
        raw_lines = path.read_bytes().splitlines()
    except OSError:
        return [], 1
    events, skipped = [], 0
    for raw in raw_lines:
        if not raw.strip():
            continue
        try:
            event = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            skipped += 1
            continue
        if isinstance(event, dict):
            events.append(event)
        else:
            skipped += 1
    return events, skipped


def _summary(path: Path) -> dict | None:
    """Resumo do método, ou None quando o arquivo não existe ou não é um objeto JSON."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return {key: data.get(key) for key in SUMMARY_FIELDS}


def _steps(events: list[dict]) -> list[dict]:
    return [{key: event.get(key) for key in STEP_FIELDS} for event in events if event.get("event") == "etapa"]


def _curve(events: list[dict]) -> list[dict]:
    """Um ponto por contagem de casos (o último evento daquela contagem), em ordem crescente de casos."""
    points: dict[int, object] = {}
    for event in events:
        if event.get("event") not in CURVE_EVENTS:
            continue
        cases = event.get("cases_cumulative")
        if not isinstance(cases, int) or isinstance(cases, bool):
            continue
        points[cases] = event.get("best_full_improvement_pct")
    return [{"cases": cases, "best_full_improvement_pct": value} for cases, value in sorted(points.items())]


def _method(method: str, label: str, prefix: str, base: Path) -> tuple[dict | None, int]:
    log_path = base / f"{prefix}-log.jsonl"
    summary_path = base / f"{prefix}-resumo.json"
    if not log_path.is_file() and not summary_path.is_file():
        return None, 0
    events, skipped = _read_log(log_path) if log_path.is_file() else ([], 0)
    entry = {
        "method": method,
        "label": label,
        "summary": _summary(summary_path),
        "curve": _curve(events),
        "steps": _steps(events),
    }
    return entry, skipped


@router.get("/api/optimizers")
def optimizers_overview():
    base = RESULTS_DIR
    methods, skipped = [], 0
    if base.is_dir():
        for method, label, prefix in METHODS:
            entry, lines_skipped = _method(method, label, prefix, base)
            skipped += lines_skipped
            if entry is not None:
                methods.append(entry)
    return placar.json_value({
        "source": {"path": str(base), "exists": base.is_dir()},
        "methods": methods,
        "skipped": skipped,
    })


@router.get("/api/optimizers/notebook")
def optimizers_notebook():
    return notebook.read_caderno(notebook.LAB_DIR)
