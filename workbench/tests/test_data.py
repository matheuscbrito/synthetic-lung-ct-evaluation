import json
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from workbench.api.app import create_app
from workbench.api.data import patient, slice_json, slice_label
from workbench.tests.conftest import DATA_OK, HISTORY_DIR, framework_counts, nonzero
from frameworks.texture_evaluator.placar import load_rows

pytestmark = pytest.mark.skipif(not DATA_OK, reason="outputs/placar/historico.json ou dados/Dsr ausente")


def any_dsr_row():
    return load_rows(HISTORY_DIR, "Dsr")[0]


def calibration():
    return json.loads((HISTORY_DIR / "historico.json").read_text(encoding="utf-8"))["calibration"]


def test_counts_match_framework(client):
    rows = load_rows(HISTORY_DIR, "Dsr")
    body = client.get("/api/slices", params={"version": "Dsr"}).json()
    assert body["n_cases"] == len(rows)
    expected = framework_counts(rows)
    assert nonzero(Counter(s["texture"]["verdict"] for s in body["slices"])) == expected["texture"]
    assert nonzero(Counter(s["brightness"]["verdict"] for s in body["slices"])) == expected["brightness"]


def test_slice_schema(client):
    s = client.get("/api/slices", params={"version": "Dsr"}).json()["slices"][0]
    assert [m["key"] for m in s["metrics"]] == ["delta_mu", "sat31", "ll", "glcm_contrast", "glcm_energy",
                                                "wavelet_fine", "wavelet_coarse", "wavelet_entropy", "nex"]
    assert set(s["texture"]["techniques"]) == {"GLCM", "Wavelet", "NEx"}
    assert s["patient"] in {"100", "105", "117"}


def test_label_and_patient():
    cid = "1.000000-P4P100S300I00003 Gated 0.0A-29193-1-058"
    assert slice_label(cid) == "0.0A · 058" and patient(cid) == "100"


def test_nan_becomes_null():
    row = {**any_dsr_row(), "nex_delta": "nan"}
    assert slice_json(row, calibration())["metrics"][-1]["value"] is None


def test_unknown_version_404(client):
    assert client.get("/api/slices", params={"version": "nope"}).status_code == 404


def test_versions_and_status(client):
    v = client.get("/api/versions").json()
    history = json.loads((HISTORY_DIR / "historico.json").read_text(encoding="utf-8"))
    assert [item["name"] for item in v] == [item["name"] for item in history["versions"]]
    assert v[0]["name"] == "Dsr" and v[0]["is_baseline"] is True
    assert [item["reference"] for item in v] == [item["name"] == history["reference"] for item in v]
    assert all(item["n_common"] == 37 for item in v)
    assert all(isinstance(item["suspicious_pairs"], int) for item in v)
    status = client.get("/api/status").json()
    assert status["stale"] is False and status["has_history"] is True and status["baseline"] == "Dsr"
    assert status["reference"] == history["reference"]
    assert isinstance(status["token"], float)


def test_stale_history(stale_dir):
    assert TestClient(create_app(stale_dir)).get("/api/status").json()["stale"] is True


def test_very_stale_history_does_not_500(very_stale_dir):
    r = TestClient(create_app(very_stale_dir)).get("/api/status")
    assert r.status_code == 200
    assert r.json()["stale"] is True and r.json()["has_history"] is True and r.json()["baseline"] == "Dsr"


def test_slice_mask_only_flag(client):
    slices = client.get("/api/slices", params={"version": "Dsr"}).json()["slices"]
    assert all(isinstance(s["mask_only"], bool) for s in slices)
    assert all(s["mask_only"] == (s["pair_mode"] == "só máscara") for s in slices)
