"""Datasets do workbench: Dsr e Dgen, estado do histórico, primeira avaliação, execuções encontradas e validação.

Todas as escritas vão para pastas temporárias; o histórico real em outputs/ nunca é tocado.
"""
import json
import shutil
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from frameworks.texture_evaluator import placar
from frameworks.texture_evaluator.placar import load_history
from workbench.api import datasets as ds
from workbench.api.app import create_app
from workbench.tests.conftest import DATA_OK, HISTORY_DIR, ROOT

pytestmark = pytest.mark.skipif(not DATA_OK, reason="outputs/placar/historico.json ou dados/Dsr ausente")

CID = "1.000000-P4P100S300I00003 Gated 0.0A-29193-1-058"
SECOND = "1.000000-P4P105S300I00004 Gated 0.0A-69532-1-059"
REAL_DSR = ROOT / "dados" / "Dsr"


@pytest.fixture
def two_datasets(tmp_history, tmp_path):
    """Dsr com histórico temporário (cópia do real); Dgen sem nenhum histórico."""
    return {
        "Dsr": {**ds.DATASETS["Dsr"], "history": tmp_history},
        "Dgen": {**ds.DATASETS["Dgen"], "history": tmp_path / "placar_dgen"},
    }


def real_case_paths():
    return {p.case_id: p for p in placar.case_paths(REAL_DSR, None)}


def write_report(folder, cases, completed=True):
    """`report.json` mínimo: cada caso aponta para os TIFFs reais (somente leitura)."""
    folder.mkdir(parents=True, exist_ok=True)
    real = real_case_paths()
    records = []
    for case_id, source in cases:
        mask = ROOT / "dados" / "Dgen" / f"{source}_mask.tiff"
        records.append({"case_id": case_id, "evaluation": {"files": {
            "original": str(real[source].original), "synthetic": str(real[source].synthetic), "mask": str(mask)}}})
    (folder / "report.json").write_text(json.dumps({"completed": completed, "cases": records}), encoding="utf-8")
    return folder


def all_reference_cases():
    return [(case_id, case_id) for case_id in load_history(HISTORY_DIR)["originals"]]


def test_datasets_listing(two_datasets):
    body = TestClient(create_app(two_datasets)).get("/api/datasets").json()
    dsr, dgen = body
    history = load_history(two_datasets["Dsr"]["history"])
    assert dsr == {"name": "Dsr", "mode": "same anatomy", "has_history": True, "stale": False,
                   "n_versions": len(history["versions"])}
    assert dgen == {"name": "Dgen", "mode": "mask only", "has_history": False, "stale": False, "n_versions": 0}


def test_real_dataset_list_is_read_only(client):
    body = client.get("/api/datasets").json()
    assert [d["name"] for d in body] == ["Dsr", "Dgen"]
    assert body[0]["has_history"] is True


def test_dgen_without_history(two_datasets):
    c = TestClient(create_app(two_datasets))
    status = c.get("/api/status", params={"dataset": "Dgen"}).json()
    assert status == {"stale": False, "has_history": False, "baseline": None, "reference": None, "token": None}
    assert c.get("/api/board", params={"dataset": "Dgen"}).status_code == 404
    assert c.get("/api/versions", params={"dataset": "Dgen"}).status_code == 404


def test_unknown_dataset_is_404(two_datasets):
    c = TestClient(create_app(two_datasets))
    for path in ("/api/status", "/api/versions", "/api/board", "/api/versions/detected"):
        assert c.get(path, params={"dataset": "Nope"}).status_code == 404, path
    assert c.post("/api/datasets/Nope/init").status_code == 404


def test_default_dataset_is_dsr(two_datasets):
    c = TestClient(create_app(two_datasets))
    assert c.get("/api/versions").json() == c.get("/api/versions", params={"dataset": "Dsr"}).json()
    assert c.get("/api/status").json() == c.get("/api/status", params={"dataset": "Dsr"}).json()


def test_path_argument_is_dsr_only(tmp_history):
    c = TestClient(create_app(tmp_history))
    assert [d["name"] for d in c.get("/api/datasets").json()] == ["Dsr"]
    assert c.get("/api/versions", params={"dataset": "Dsr"}).status_code == 200


def test_stale_when_nps_air_key_missing(tmp_path):
    shutil.copy(HISTORY_DIR / "historico.json", tmp_path / "historico.json")
    shutil.copytree(HISTORY_DIR / "versoes", tmp_path / "versoes")
    path = tmp_path / "historico.json"
    history = json.loads(path.read_text(encoding="utf-8"))
    del history["calibration"]["nps_reference"]["air_fallback_sigma"]
    path.write_text(json.dumps(history, ensure_ascii=False), encoding="utf-8")
    status = TestClient(create_app(tmp_path)).get("/api/status").json()
    assert status["stale"] is True and status["has_history"] is True and status["reference"] == "Dsr"


def test_init_first_run_on_tmp_dataset(tmp_path):
    folder = tmp_path / "Dsr-src"
    folder.mkdir()
    for case_id in (CID, SECOND):
        for suffix in (".tiff", "_generate.tiff"):
            (folder / f"{case_id}{suffix}").symlink_to(REAL_DSR / f"{case_id}{suffix}")
    cfg = {**ds.DATASETS["Dsr"], "folder": folder, "history": tmp_path / "placar"}
    c = TestClient(create_app({"Dsr": cfg}))
    assert c.get("/api/status").json()["has_history"] is False
    r = c.post("/api/datasets/Dsr/init")
    assert r.status_code == 200 and r.json()["name"] == "Dsr"
    assert (tmp_path / "placar" / "historico.json").exists()
    assert {s["case_id"] for s in c.get("/api/slices", params={"version": "Dsr"}).json()["slices"]} == {CID, SECOND}
    assert c.get("/api/datasets").json()[0]["n_versions"] == 1
    assert c.post("/api/datasets/Dsr/init").status_code == 409


def test_init_existing_history_is_409(tmp_history):
    assert TestClient(create_app(tmp_history)).post("/api/datasets/Dsr/init").status_code == 409


def test_init_unknown_dataset_is_404(two_datasets):
    assert TestClient(create_app(two_datasets)).post("/api/datasets/Nope/init").status_code == 404


def test_discovered_runs_filter(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    cases = [case_id for case_id, _ in all_reference_cases()]
    write_report(runs / "complete", all_reference_cases())
    write_report(runs / "running", all_reference_cases(), completed=False)
    write_report(runs / "partial", [(c, c) for c in cases[:-1]])
    monkeypatch.setenv("LUNG_AGENT_RUNS", str(runs))
    history = load_history(HISTORY_DIR)
    found = [p.name for p in ds.discovered_agent_runs(history)]
    assert found == ["complete"]


def test_discovered_runs_skip_folders_already_in_history(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    write_report(runs / "known", all_reference_cases())
    history = load_history(HISTORY_DIR)
    history["versions"] = [{**history["versions"][0], "folder": str(runs / "known")}]
    monkeypatch.setenv("LUNG_AGENT_RUNS", str(runs))
    assert ds.discovered_agent_runs(history) == []


def test_detected_route(tmp_history, tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    write_report(runs / "complete", all_reference_cases())
    monkeypatch.setenv("LUNG_AGENT_RUNS", str(runs))
    body = TestClient(create_app(tmp_history)).get("/api/versions/detected").json()
    assert [item["name"] for item in body] == ["complete"]
    assert body[0]["folder"].endswith("complete")


def test_detected_without_history_is_empty(two_datasets):
    assert TestClient(create_app(two_datasets)).get("/api/versions/detected", params={"dataset": "Dgen"}).json() == []


def test_add_version_missing_slices_400(tmp_history, tmp_path):
    cases = all_reference_cases()[:-1]
    folder = write_report(tmp_path / "incomplete", cases)
    r = TestClient(create_app(tmp_history)).post("/api/versions", json={"folder": str(folder)})
    n = len(load_history(HISTORY_DIR)["originals"])
    assert r.status_code == 400 and r.json()["detail"] == f"missing 1 of {n} slices"


def test_add_version_extra_slices_400(tmp_history, tmp_path):
    extra = all_reference_cases() + [("1.000000-EXTRA-slice", CID)]
    folder = write_report(tmp_path / "extra", extra)
    r = TestClient(create_app(tmp_history)).post("/api/versions", json={"folder": str(folder)})
    assert r.status_code == 400 and r.json()["detail"] == "1 slices not in the reference"


def test_add_version_duplicate_folder_400(tmp_history):
    r = TestClient(create_app(tmp_history)).post("/api/versions", json={"folder": str(ROOT / "dados" / "Dsr-baseline")})
    assert r.status_code == 400 and "already in the history" in r.json()["detail"]


def test_add_version_default_name_is_folder_name(tmp_history, tmp_path):
    folder = tmp_path / "bad name"
    folder.mkdir()
    r = TestClient(create_app(tmp_history)).post("/api/versions", json={"folder": str(folder)})
    assert r.status_code == 400 and "invalid name" in r.json()["detail"]


def test_board_reads_dataset_history(two_datasets):
    c = TestClient(create_app(two_datasets))
    assert c.get("/api/board", params={"dataset": "Dsr"}).json()["baseline"] == "Dsr"
    assert c.get("/api/figure/" + quote(CID) + "/technique/delta_mu.png", params={"dataset": "Dgen"}).status_code == 404


def _two_history_dirs(tmp_path):
    """Dsr com duas versões (cópia reduzida do real) e Dgen com o histórico real copiado para tmp."""
    dsr_dir = tmp_path / "placar"
    (dsr_dir / "versoes").mkdir(parents=True)
    history = json.loads((HISTORY_DIR / "historico.json").read_text(encoding="utf-8"))
    history["versions"] = [v for v in history["versions"] if v["name"] in {"Dsr", "Dsr-baseline"}]
    (dsr_dir / "historico.json").write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    for name in ("Dsr", "Dsr-baseline"):
        shutil.copy(HISTORY_DIR / "versoes" / f"{name}.csv", dsr_dir / "versoes" / f"{name}.csv")
    dgen_dir = tmp_path / "placar_dgen"
    shutil.copytree(ROOT / "outputs" / "placar_dgen", dgen_dir)
    return dsr_dir, dgen_dir


def test_two_histories_are_isolated(tmp_path):
    dsr_dir, dgen_dir = _two_history_dirs(tmp_path)
    datasets = {"Dsr": {**ds.DATASETS["Dsr"], "history": dsr_dir}, "Dgen": {**ds.DATASETS["Dgen"], "history": dgen_dir}}
    c = TestClient(create_app(datasets))
    dsr_versions = [v["name"] for v in c.get("/api/versions", params={"dataset": "Dsr"}).json()]
    dgen_versions = [v["name"] for v in c.get("/api/versions", params={"dataset": "Dgen"}).json()]
    assert dsr_versions == ["Dsr", "Dsr-baseline"] and dgen_versions == ["Dgen"]
    # a versão de um dataset não existe no outro
    assert c.get("/api/slices", params={"version": "Dgen", "dataset": "Dsr"}).status_code == 404
    assert c.get("/api/slices", params={"version": "Dsr", "dataset": "Dgen"}).status_code == 404
    dsr_slices = c.get("/api/slices", params={"version": "Dsr", "dataset": "Dsr"}).json()["slices"]
    dgen_slices = c.get("/api/slices", params={"version": "Dgen", "dataset": "Dgen"}).json()["slices"]
    assert dsr_slices != dgen_slices
    dsr_metrics = {s["case_id"]: s["metrics"] for s in dsr_slices}
    assert any(dsr_metrics[s["case_id"]] != s["metrics"] for s in dgen_slices)
    dsr_img = c.get(f"/api/image/Dsr/{quote(CID)}/synthetic.png", params={"dataset": "Dsr"})
    dgen_img = c.get(f"/api/image/Dgen/{quote(CID)}/synthetic.png", params={"dataset": "Dgen"})
    assert dsr_img.status_code == 200 and dgen_img.status_code == 200
    assert dsr_img.content != dgen_img.content


def test_name_pattern_uses_fullmatch():
    assert ds.NAME_PATTERN.fullmatch("Versao_1.2-a")
    assert not ds.NAME_PATTERN.fullmatch("Versao\n")
    assert ds.NAME_PATTERN.match("Versao\n")  # por isso a validação usa fullmatch
