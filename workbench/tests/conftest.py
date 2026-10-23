"""Fixtures do workbench: usam o histórico real de outputs/placar (somente leitura)."""
import json
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

HISTORY_DIR = ROOT / "outputs" / "placar"
DATA_OK = (HISTORY_DIR / "historico.json").exists() and (ROOT / "dados" / "Dsr").exists()

from workbench.api.app import create_app  # noqa: E402


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
