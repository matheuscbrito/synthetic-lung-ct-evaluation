"""Versões do contrato genérico (§4.6): rótulos, origem (provenance), avisos e rotas `/api/v2/versions`.

Rótulo e origem ficam num arquivo lateral `<histórico>/workbench.json` (`{"versions": {nome: {label, provenance}}}`);
o `historico.json` congelado nunca é editado. A escrita é atômica (arquivo temporário + `os.replace`) e sempre
sob `datasets.ADMIN_LOCK`: quem já tem o lock (rotas de add/remove) chama `save_meta`/`drop_meta` depois de soltá-lo.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from frameworks.texture_evaluator.placar import PlacarError
from workbench.api import data, datasets as ds
from workbench.api.contract import DATASET_LABEL
from workbench.api.datasets import DEFAULT

META_FILE = "workbench.json"
LABEL_PATTERN = re.compile(r"[A-Za-z0-9 #._-]{1,40}")  # uso com fullmatch: sem âncoras (`$` aceita "\n" no fim)
SUSPICIOUS_WARNING = "suspicious pairs"


class VersionPatch(BaseModel):
    """Campos ausentes ficam como estão; `null` limpa o rótulo ou a origem."""
    label: str | None = None
    provenance: dict | None = None


def check_label(label: str | None) -> None:
    if label is not None and not LABEL_PATTERN.fullmatch(label):
        raise HTTPException(400, "invalid label: use 1 to 40 letters, digits, space, #, dot, hyphen or underscore")


def _meta_path(history_dir: Path) -> Path:
    return Path(history_dir) / META_FILE


def load_meta(history_dir: Path) -> dict:
    """Mapa `{nome: {"label", "provenance"}}` do arquivo lateral; sem arquivo: vazio.

    Arquivo ilegível vira 409 (PlacarError), para não ser sobrescrito em silêncio pela próxima escrita.
    """
    path = _meta_path(history_dir)
    if not path.exists():
        return {}
    try:
        versions = json.loads(path.read_text(encoding="utf-8")).get("versions", {})
    except (OSError, ValueError, AttributeError) as error:
        raise PlacarError(f"workbench.json ilegível em {history_dir}: {error}") from error
    if not isinstance(versions, dict):
        raise PlacarError(f"workbench.json sem o mapa de versões em {history_dir}")
    return versions


def _write_meta(history_dir: Path, mutate: Callable[[dict], None]) -> None:
    """Lê, altera e grava o arquivo lateral de forma atômica, sob `ADMIN_LOCK` (não chamar com o lock tomado)."""
    with ds.ADMIN_LOCK:
        versions = load_meta(history_dir)
        mutate(versions)
        path = _meta_path(history_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".tmp")
        temp.write_text(json.dumps({"versions": versions}, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temp, path)


def save_meta(history_dir: Path, name: str, label: str | None, provenance: dict | None) -> None:
    def mutate(versions: dict) -> None:
        versions[name] = {"label": label, "provenance": provenance}

    _write_meta(Path(history_dir), mutate)


def drop_meta(history_dir: Path, name: str) -> None:
    _write_meta(Path(history_dir), lambda versions: versions.pop(name, None))


def detected_provenance(folder: Path) -> dict | None:
    """Origem de uma execução do otimizador: `optimizer` e `step` do `report.json`; ausentes ou nulos: None."""
    try:
        report = json.loads((Path(folder) / "report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(report, dict):
        return None
    optimizer, step = report.get("optimizer"), report.get("step")
    if optimizer is None or step is None:
        return None
    return {"run": optimizer, "step": str(step)}


def version_label(name: str, history: dict, meta: dict) -> str:
    """Rótulo de exibição: o do arquivo lateral; senão `reference`, `baseline` (linha de base padrão) ou o nome.

    Porte da regra de rótulos do workbench: a referência é sempre `reference`; a linha de base padrão, quando
    não é a referência, é `baseline`; qualquer outra versão aparece pelo nome da pasta.
    """
    label = (meta.get(name) or {}).get("label")
    if label:
        return label
    if name == history.get("reference"):
        return "reference"
    if name == data.default_baseline(history):
        return "baseline"
    return name


def _mode_label(mode: str) -> str:
    """Modo do histórico (em português) para o texto do dataset: "Same anatomy" ou "Mask only"."""
    code = data.MODE_CODE.get(mode)
    return DATASET_LABEL.get(code.replace("_", " "), mode) if code else mode


def versions_contract(wb: data.Workbench, meta: dict) -> list[dict]:
    """§4.6: uma linha por versão, na ordem do histórico."""
    history = wb.history
    rows = []
    for item in history["versions"]:
        name = item["name"]
        suspicious = item.get("suspicious_pairs") or 0  # None: versão anterior ao campo, sem aviso
        rows.append({
            "name": name,
            "label": version_label(name, history, meta),
            "is_reference": name == history.get("reference"),
            "added": item["added"],
            "mode_label": _mode_label(item["mode"]),
            "n_items": item["n_cases"],
            "n_common": wb.board["n_cases"],
            "warnings": [{"label": SUSPICIOUS_WARNING, "count": suspicious}] if suspicious > 0 else [],
            "provenance": (meta.get(name) or {}).get("provenance"),
        })
    return rows


def router(datasets: dict) -> APIRouter:
    api = APIRouter()

    def _wb(dataset: str) -> data.Workbench:
        return ds.wb_for(dataset, datasets)

    @api.get("/api/v2/versions")
    def list_versions(dataset: str = Query(DEFAULT)):
        wb = _wb(dataset)
        return versions_contract(wb, load_meta(Path(wb.history_dir)))

    @api.patch("/api/versions/{name}")
    def patch_version(name: str, body: VersionPatch, dataset: str = Query(DEFAULT)):
        wb = _wb(dataset)
        wb.entry(name)  # desconhecida: 404
        if "label" in body.model_fields_set:
            check_label(body.label)
        fields = body.model_fields_set

        def mutate(versions: dict) -> None:
            entry = {"label": None, "provenance": None, **(versions.get(name) or {})}
            if "label" in fields:
                entry["label"] = body.label
            if "provenance" in fields:
                entry["provenance"] = body.provenance
            versions[name] = entry

        _write_meta(Path(wb.history_dir), mutate)
        return next(row for row in versions_contract(wb, load_meta(Path(wb.history_dir))) if row["name"] == name)

    return api
