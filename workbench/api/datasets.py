"""Datasets do workbench (Dsr e Dgen): estado do histórico, primeira avaliação e descoberta de execuções.

Cada dataset tem o seu histórico (`outputs/placar`, `outputs/placar_dgen`) e nunca mistura cortes
com o outro. Dsr é o padrão de todas as rotas. Os helpers abaixo são portados (somente leitura)
de `frameworks/texture_evaluator/ui_placar.py`:

- `discovered_agent_runs`: linhas 62-81 (execuções completas do agente ainda fora do histórico);
- `validate_complete_version`: linhas 84-106 (a versão precisa conter exatamente os cortes da referência);
- a lista de réguas que tornam o histórico desatualizado: linha 1147 (ver `data.STALE_KEYS`).
"""
from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from frameworks.texture_evaluator import placar
from frameworks.texture_evaluator.placar import PlacarError
from workbench.api import data
from workbench.api.data import NotFound, Workbench, ROOT

DATASETS = {
    "Dsr": {"folder": ROOT / "dados" / "Dsr", "masks": ROOT / "dados" / "Dgen",
            "history": ROOT / "outputs" / "placar", "mode": "same anatomy"},
    "Dgen": {"folder": ROOT / "dados" / "Dgen", "masks": ROOT / "dados" / "Dgen",
             "history": ROOT / "outputs" / "placar_dgen", "mode": "mask only"},
}
DEFAULT = "Dsr"
NAME_PATTERN = re.compile(r"[A-Za-z0-9._-]+")  # uso com fullmatch: sem âncoras, `$` aceitaria "\n" no fim
ADMIN_LOCK = threading.Lock()  # uma escrita no histórico por vez (compartilhada com board.py)


def normalise(datasets) -> dict:
    """Aceita o mapa de datasets ou uma única pasta de histórico (legado: vira o dataset Dsr)."""
    if isinstance(datasets, (str, Path)):
        return {DEFAULT: {**DATASETS[DEFAULT], "history": Path(datasets)}}
    return dict(datasets)


def config(datasets: dict, name: str) -> dict:
    if name not in datasets:
        raise NotFound(f"unknown dataset: {name}")
    return datasets[name]


def wb_for(dataset: str = DEFAULT, datasets: dict = DATASETS) -> Workbench:
    """Histórico do dataset pedido; dataset desconhecido ou sem histórico vira 404."""
    return data.load(Path(config(normalise(datasets), dataset)["history"]))


def load_state(history_dir: Path) -> dict | None:
    """Histórico com pelo menos uma versão, ou None quando o dataset ainda não foi avaliado."""
    history = placar.load_history(Path(history_dir))
    return history if history and history.get("versions") else None


def status_json(cfg: dict) -> dict:
    history_dir = Path(cfg["history"])
    history = load_state(history_dir)
    if history is None:
        return {"stale": False, "has_history": False, "baseline": None, "reference": None, "token": None}
    token = (history_dir / placar.HISTORY_FILE).stat().st_mtime
    baseline, reference = history["versions"][0]["name"], history.get("reference")
    if data.is_stale(history):
        # histórico desatualizado: responde antes de montar o placar, que quebraria sem as réguas novas
        return {"stale": True, "has_history": True, "baseline": baseline, "reference": reference, "token": token}
    data.load(history_dir)
    return {"stale": False, "has_history": True, "baseline": baseline, "reference": reference, "token": token}


def datasets_json(datasets: dict) -> list[dict]:
    out = []
    for name, cfg in normalise(datasets).items():
        history = load_state(Path(cfg["history"]))
        out.append({"name": name, "mode": cfg["mode"], "has_history": history is not None,
                    "stale": data.is_stale(history) if history else False,
                    "n_versions": len(history["versions"]) if history else 0})
    return out


def validate_complete_version(folder: Path, history: dict) -> None:
    """Garante comparação honesta: a versão precisa conter toda a referência.

    Port de `ui_placar.validate_complete_version` (linhas 84-106).
    """
    expected = set(history["originals"])
    found = {paths.case_id for paths in placar.case_paths(folder, None)}
    missing, extra = sorted(expected - found), sorted(found - expected)
    problems = []
    if missing:
        problems.append(f"missing {len(missing)} of {len(expected)} slices")
    if extra:
        problems.append(f"{len(extra)} slices not in the reference")
    if problems:
        raise PlacarError("; ".join(problems))


def discovered_agent_runs(history: dict) -> list[Path]:
    """Execuções completas do agente ainda não adicionadas ao histórico.

    Port de `ui_placar.discovered_agent_runs` (linhas 62-81). `LUNG_AGENT_RUNS` tem prioridade
    sobre `../lung-agent-lab/runs/real`.
    """
    default_root = ROOT.parent / "lung-agent-lab" / "runs" / "real"
    runs_root = Path(os.environ.get("LUNG_AGENT_RUNS", default_root))
    if not runs_root.is_dir():
        return []
    known = {Path(item["folder"]).resolve() for item in history["versions"]}
    expected = set(history["originals"])
    found = []
    for report_file in sorted(runs_root.glob("*/report.json")):
        try:
            report = json.loads(report_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        cases = report.get("cases", [])
        case_ids = {case.get("case_id") for case in cases if case.get("case_id")}
        folder = report_file.parent.resolve()
        if report.get("completed") and case_ids == expected and folder not in known:
            found.append(folder)
    return found


def init_dataset(name: str, cfg: dict) -> dict:
    """Primeira avaliação de um dataset: a pasta de referência vira o histórico (`add_version` + `write_outputs`)."""
    history_dir = Path(cfg["history"])
    with ADMIN_LOCK:
        if (history_dir / placar.HISTORY_FILE).exists():
            raise HTTPException(409, f"{name} already has history; use the existing versions")
        try:
            message = placar.add_version(history_dir, name, Path(cfg["folder"]), Path(cfg["masks"]))
            placar.write_outputs(history_dir, placar.build_board(history_dir))
        except (PlacarError, FileNotFoundError, NotADirectoryError, ValueError) as exc:
            raise HTTPException(400, str(exc)) from exc
    return {"message": message, "name": name}


def router(datasets: dict) -> APIRouter:
    api = APIRouter()

    @api.get("/api/datasets")
    def list_datasets():
        return datasets_json(datasets)

    @api.post("/api/datasets/{name}/init")
    def init(name: str):
        return init_dataset(name, config(normalise(datasets), name))

    @api.get("/api/versions/detected")
    def detected(dataset: str = Query(DEFAULT)):
        cfg = config(normalise(datasets), dataset)
        history = load_state(Path(cfg["history"]))
        if history is None:  # sem referência não há cortes para comparar
            return []
        return [{"name": folder.name, "folder": str(folder)} for folder in discovered_agent_runs(history)]

    return api
