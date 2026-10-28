"""Fixtures do workbench: usam o histórico real de outputs/placar (somente leitura)."""
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

HISTORY_DIR = ROOT / "outputs" / "placar"
DATA_OK = (HISTORY_DIR / "historico.json").exists() and (ROOT / "dados" / "Dsr").exists()

from frameworks.texture_evaluator import decision  # noqa: E402
from workbench.api import board as wb_board, data as wb_data, datasets as wb_ds  # noqa: E402
from workbench.api.app import create_app  # noqa: E402


def framework_counts(rows: list[dict]) -> dict:
    """Contagens por veredito das linhas do CSV, pelas funções de `decision` (nunca números fixos).

    Só entram os vereditos presentes (zeros são omitidos), como em `nonzero`.
    """
    def tally(verdict):
        return nonzero(Counter(wb_data.STATUS[verdict(row)] for row in rows))
    return {"brightness": tally(decision.brightness_verdict), "texture": tally(decision.texture_status)}


def nonzero(counts) -> dict:
    return {key: value for key, value in dict(counts).items() if value}


def workbench_of(datasets=wb_ds.DATASETS, dataset: str = "Dsr") -> wb_data.Workbench:
    """Histórico do dataset (o mesmo que as rotas usam); `datasets` aceita uma pasta de histórico, como `create_app`."""
    return wb_ds.wb_for(dataset, wb_ds.normalise(datasets))


def board_of(datasets=wb_ds.DATASETS, baseline: str | None = None, dataset: str = "Dsr") -> dict:
    """Placar interno (`board.board_json`) que alimenta `GET /api/board` do contrato."""
    return wb_board.board_json(workbench_of(datasets, dataset), baseline)


def slices_of(version: str, datasets=wb_ds.DATASETS, dataset: str = "Dsr") -> list[dict]:
    """Payload interno por corte (`data.slice_json`) que alimenta `/api/items` e os inspetores."""
    wb = workbench_of(datasets, dataset)
    return [wb_data.slice_json(row, wb.history["calibration"]) for row in wb.rows(version)]


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def stale_dir(tmp_path):
    """Cópia do histórico sem a régua de NEx: deve aparecer como desatualizado."""
    shutil.copy(HISTORY_DIR / "historico.json", tmp_path / "historico.json")
    shutil.copytree(HISTORY_DIR / "versoes", tmp_path / "versoes")
    path = tmp_path / "historico.json"
    history = json.loads(path.read_text(encoding="utf-8"))
    del history["calibration"]["nex_reference"]
    path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    return tmp_path


@pytest.fixture
def tmp_history(tmp_path):
    """Cópia do histórico para testes que escrevem: inclui `Dsr-copy`, uma duplicata de Dsr como segunda versão."""
    shutil.copy(HISTORY_DIR / "historico.json", tmp_path / "historico.json")
    shutil.copytree(HISTORY_DIR / "versoes", tmp_path / "versoes")
    shutil.copy(tmp_path / "versoes" / "Dsr.csv", tmp_path / "versoes" / "Dsr-copy.csv")
    path = tmp_path / "historico.json"
    history = json.loads(path.read_text(encoding="utf-8"))
    dsr = next(item for item in history["versions"] if item["name"] == "Dsr")
    history["versions"].append({**dsr, "name": "Dsr-copy"})
    path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    return tmp_path


@pytest.fixture
def very_stale_dir(tmp_path):
    """Histórico antigo: sem `ll_iqr` e sem as colunas `wavelet_ll_*` dos CSVs; antes quebrava o placar."""
    shutil.copy(HISTORY_DIR / "historico.json", tmp_path / "historico.json")
    shutil.copytree(HISTORY_DIR / "versoes", tmp_path / "versoes")
    path = tmp_path / "historico.json"
    history = json.loads(path.read_text(encoding="utf-8"))
    del history["calibration"]["ll_iqr"]
    path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    for csv_path in (tmp_path / "versoes").glob("*.csv"):
        lines = csv_path.read_text(encoding="utf-8").splitlines()
        header = lines[0].split(",")
        keep = [i for i, name in enumerate(header) if not name.startswith("wavelet_ll_")]
        csv_path.write_text("\n".join(",".join(line.split(",")[i] for i in keep) for line in lines) + "\n", encoding="utf-8")
    return tmp_path
