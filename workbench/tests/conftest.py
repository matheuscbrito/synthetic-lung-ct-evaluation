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
