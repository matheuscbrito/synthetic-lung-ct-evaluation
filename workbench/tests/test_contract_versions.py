"""Contrato de versões (§4.6): rótulos, origem (provenance), avisos e metadados em `workbench.json`.

Escritas só em `tmp_history` (cópia do histórico real) e em pastas temporárias.
"""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from frameworks.texture_evaluator import placar
from workbench.api import datasets as ds
from workbench.api.app import create_app
from workbench.api.contract import versions as cv
from workbench.tests.conftest import DATA_OK, HISTORY_DIR, ROOT

pytestmark = pytest.mark.skipif(not DATA_OK, reason="outputs/placar/historico.json ou dados/Dsr ausente")

REAL_DSR = ROOT / "dados" / "Dsr"
CONTRACT_KEYS = {"name", "label", "is_reference", "added", "mode_label", "n_items", "n_common", "warnings", "provenance"}


def get_versions(client, dataset="Dsr"):
    return client.get("/api/versions", params={"dataset": dataset}).json()


def by_name(rows):
    return {row["name"]: row for row in rows}


def write_detected_run(folder: Path, optimizer: str, step) -> Path:
    """Pasta de execução com `report.json` completo (todos os cortes da referência) e metadados do otimizador."""
    folder.mkdir(parents=True, exist_ok=True)
    real = {paths.case_id: paths for paths in placar.case_paths(REAL_DSR, None)}
    records = []
    for case_id in placar.load_history(HISTORY_DIR)["originals"]:
        source = real[case_id]
        records.append({"case_id": case_id, "evaluation": {"files": {
            "original": str(source.original), "synthetic": str(source.synthetic),
            "mask": str(ROOT / "dados" / "Dgen" / f"{case_id}_mask.tiff")}}})
    report = {"completed": True, "cases": records, "optimizer": optimizer, "step": step}
    (folder / "report.json").write_text(json.dumps(report), encoding="utf-8")
    return folder


def set_suspicious(history_dir: Path, name: str, value) -> None:
    path = history_dir / placar.HISTORY_FILE
    history = json.loads(path.read_text(encoding="utf-8"))
    entry = next(item for item in history["versions"] if item["name"] == name)
    entry["suspicious_pairs"] = value
    path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- rótulos padrão (funções puras)

def test_version_label_defaults_are_pure():
    history = {"reference": "Dsr", "versions": [{"name": "Dsr"}, {"name": "Dsr-copy"}]}
    assert cv.version_label("Dsr", history, {}) == "reference"
    assert cv.version_label("Dsr-copy", history, {}) == "Dsr-copy"


def test_version_label_baseline_when_reference_missing():
    # sem a referência nas versões, a linha de base padrão é a primeira: vira "baseline"
    history = {"reference": "Gone", "versions": [{"name": "A"}, {"name": "B"}]}
    assert cv.version_label("A", history, {}) == "baseline"
    assert cv.version_label("B", history, {}) == "B"


def test_version_label_meta_wins_over_defaults():
    history = {"reference": "Dsr", "versions": [{"name": "Dsr"}]}
    assert cv.version_label("Dsr", history, {"Dsr": {"label": "Ruler", "provenance": None}}) == "Ruler"
    assert cv.version_label("Dsr", history, {"Dsr": {"label": None, "provenance": None}}) == "reference"


def test_lab_baseline_is_first_version_named_baseline():
    history = {"reference": "Dsr", "versions": [{"name": "Dsr"}, {"name": "X-baseline"}, {"name": "Y-baseline"}]}
    assert cv.lab_baseline(history) == "X-baseline"
    assert cv.version_label("X-baseline", history, {}) == "baseline"
    assert cv.version_label("Y-baseline", history, {}) == "Y-baseline"


def test_lab_baseline_none_without_baseline_suffix_and_reference_present():
    history = {"reference": "Dsr", "versions": [{"name": "Dsr"}, {"name": "B"}]}
    assert cv.lab_baseline(history) is None


def test_lab_baseline_falls_back_to_default_when_reference_missing():
    history = {"reference": "Gone", "versions": [{"name": "A"}, {"name": "B"}]}
    assert cv.lab_baseline(history) == "A"


def test_lab_baseline_label_on_real_history_copy(tmp_history):
    rows = by_name(get_versions(TestClient(create_app(tmp_history))))
    assert rows["Dsr-baseline"]["label"] == "baseline"
    assert rows["Dsr-baseline"]["is_reference"] is False
    assert rows["Dsr"]["label"] == "reference"
    assert rows["Dsr-copy"]["label"] == "Dsr-copy"


def test_load_and_save_meta_round_trip(tmp_path):
    assert cv.load_meta(tmp_path) == {}
    cv.save_meta(tmp_path, "M12", "M12", {"run": "gp", "step": "12"})
    assert cv.load_meta(tmp_path) == {"M12": {"label": "M12", "provenance": {"run": "gp", "step": "12"}}}
    raw = json.loads((tmp_path / cv.META_FILE).read_text(encoding="utf-8"))
    assert raw == {"versions": {"M12": {"label": "M12", "provenance": {"run": "gp", "step": "12"}}}}
    assert not (tmp_path / (cv.META_FILE + ".tmp")).exists()  # escrita atômica não deixa temporário


# ---------------------------------------------------------------- contrato via API

def test_contract_fields_and_values(tmp_history):
    client = TestClient(create_app(tmp_history))
    rows = get_versions(client)
    history = placar.load_history(tmp_history)
    board = client.get("/api/board").json()
    assert [row["name"] for row in rows] == [item["name"] for item in history["versions"]]
    for row, item in zip(rows, history["versions"]):
        assert set(row) == CONTRACT_KEYS
        assert row["added"] == item["added"]
        assert row["n_items"] == item["n_cases"]
        assert row["n_common"] == board["n_items"]
        assert row["mode_label"] == "Same anatomy"
        assert row["provenance"] is None


def test_default_labels_on_real_history_copy(tmp_history):
    rows = by_name(get_versions(TestClient(create_app(tmp_history))))
    assert rows["Dsr"]["label"] == "reference" and rows["Dsr"]["is_reference"] is True
    assert rows["Dsr-copy"]["label"] == "Dsr-copy" and rows["Dsr-copy"]["is_reference"] is False


def test_patch_sets_label_and_provenance(tmp_history):
    client = TestClient(create_app(tmp_history))
    r = client.patch("/api/versions/Dsr-copy", json={"label": "GP-BO #11", "provenance": {"run": "gp", "step": "11"}})
    assert r.status_code == 200
    row = by_name(get_versions(client))["Dsr-copy"]
    assert row["label"] == "GP-BO #11"
    assert row["provenance"] == {"run": "gp", "step": "11"}
    assert r.json()["label"] == "GP-BO #11"


def test_patch_partial_keeps_other_field(tmp_history):
    client = TestClient(create_app(tmp_history))
    client.patch("/api/versions/Dsr-copy", json={"provenance": {"run": "gp", "step": "7"}})
    client.patch("/api/versions/Dsr-copy", json={"label": "Step 7"})
    row = by_name(get_versions(client))["Dsr-copy"]
    assert row["label"] == "Step 7" and row["provenance"] == {"run": "gp", "step": "7"}


def test_patch_null_label_clears_it(tmp_history):
    client = TestClient(create_app(tmp_history))
    client.patch("/api/versions/Dsr-copy", json={"label": "Temp"})
    client.patch("/api/versions/Dsr-copy", json={"label": None})
    assert by_name(get_versions(client))["Dsr-copy"]["label"] == "Dsr-copy"


@pytest.mark.parametrize("label", ["../x", "a/b", "", "x" * 41, "tab\tname", "ç"])
def test_patch_rejects_bad_label(tmp_history, label):
    client = TestClient(create_app(tmp_history))
    assert client.patch("/api/versions/Dsr-copy", json={"label": label}).status_code == 400


def test_patch_accepts_allowed_label(tmp_history):
    client = TestClient(create_app(tmp_history))
    assert client.patch("/api/versions/Dsr-copy", json={"label": "GP-BO #11"}).status_code == 200
    assert client.patch("/api/versions/Dsr-copy", json={"label": "x" * 40}).status_code == 200


def test_patch_unknown_version_is_404(tmp_history):
    client = TestClient(create_app(tmp_history))
    assert client.patch("/api/versions/Versao-inexistente", json={"label": "A"}).status_code == 404


def test_patch_unknown_dataset_is_404(tmp_history):
    client = TestClient(create_app(tmp_history))
    assert client.patch("/api/versions/Dsr-copy", params={"dataset": "Nope"}, json={"label": "A"}).status_code == 404
    assert client.get("/api/versions", params={"dataset": "Nope"}).status_code == 404


def test_meta_survives_removal_of_another_version(tmp_history):
    client = TestClient(create_app(tmp_history))
    client.patch("/api/versions/Dsr-copy", json={"label": "Copy", "provenance": {"run": "gp", "step": "2"}})
    client.patch("/api/versions/Dsr-gpbo11", json={"label": "GP-BO #11"})
    assert client.delete("/api/versions/Dsr-gpbo11").status_code == 200
    meta = cv.load_meta(tmp_history)
    assert "Dsr-gpbo11" not in meta
    assert meta["Dsr-copy"] == {"label": "Copy", "provenance": {"run": "gp", "step": "2"}}
    assert by_name(get_versions(client))["Dsr-copy"]["label"] == "Copy"


def test_warning_only_when_suspicious_pairs(tmp_history):
    set_suspicious(tmp_history, "Dsr-copy", 3)
    set_suspicious(tmp_history, "Dsr-baseline", 0)
    set_suspicious(tmp_history, "Dsr-gpbo11", None)  # versão anterior ao campo: contagem desconhecida
    rows = by_name(get_versions(TestClient(create_app(tmp_history))))
    assert rows["Dsr-copy"]["warnings"] == [{"label": "suspicious pairs", "count": 3}]
    assert rows["Dsr-baseline"]["warnings"] == []
    assert rows["Dsr-gpbo11"]["warnings"] == []


def test_add_from_detected_run_stores_provenance(tmp_history, tmp_path):
    folder = write_detected_run(tmp_path / "gp-11", optimizer="gp", step=11)
    client = TestClient(create_app(tmp_history))
    r = client.post("/api/versions", json={"name": "Dsr-gp11", "folder": str(folder)})
    assert r.status_code == 200, r.text
    row = by_name(get_versions(client))["Dsr-gp11"]
    assert row["provenance"] == {"run": "gp", "step": "11"}
    assert row["label"] == "Dsr-gp11"


def test_add_with_label_stores_label_and_hand_added_has_no_provenance(tmp_history, tmp_path):
    folder = write_detected_run(tmp_path / "plain", optimizer=None, step=None)
    client = TestClient(create_app(tmp_history))
    r = client.post("/api/versions", json={"name": "Dsr-plain", "folder": str(folder), "label": "M12"})
    assert r.status_code == 200, r.text
    row = by_name(get_versions(client))["Dsr-plain"]
    assert row["label"] == "M12" and row["provenance"] is None


def test_add_with_bad_label_is_400_and_adds_nothing(tmp_history, tmp_path):
    folder = write_detected_run(tmp_path / "bad", optimizer=None, step=None)
    client = TestClient(create_app(tmp_history))
    r = client.post("/api/versions", json={"name": "Dsr-bad", "folder": str(folder), "label": "../x"})
    assert r.status_code == 400
    assert "Dsr-bad" not in by_name(get_versions(client))
