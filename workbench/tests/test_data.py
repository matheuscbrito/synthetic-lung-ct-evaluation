import json
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from workbench.api.app import create_app
from workbench.api.data import NotFound, patient, slice_json, slice_label
from workbench.tests.conftest import DATA_OK, HISTORY_DIR, framework_counts, nonzero, slices_of
from frameworks.texture_evaluator.placar import load_rows

pytestmark = pytest.mark.skipif(not DATA_OK, reason="outputs/placar/historico.json ou dados/Dsr ausente")


def any_dsr_row():
    return load_rows(HISTORY_DIR, "Dsr")[0]


def calibration():
    return json.loads((HISTORY_DIR / "historico.json").read_text(encoding="utf-8"))["calibration"]


def test_counts_match_framework():
    rows = load_rows(HISTORY_DIR, "Dsr")
    slices = slices_of("Dsr")
    assert len(slices) == len(rows)
    expected = framework_counts(rows)
    assert nonzero(Counter(s["texture"]["verdict"] for s in slices)) == expected["texture"]
    assert nonzero(Counter(s["brightness"]["verdict"] for s in slices)) == expected["brightness"]


def test_slice_schema():
    s = slices_of("Dsr")[0]
    assert [m["key"] for m in s["metrics"]] == ["delta_mu", "sat31", "ll", "glcm_contrast", "glcm_energy",
                                                "wavelet_fine", "wavelet_coarse", "wavelet_entropy", "nex",
                                                "nps_quantity", "nps_grain", "nps_low_band", "nps_high_band", "nps_air"]
    assert set(s["texture"]["techniques"]) == {"GLCM", "Wavelet", "NEx"}
    assert s["patient"] in {"100", "105", "117"}


def test_label_and_patient():
    cid = "1.000000-P4P100S300I00003 Gated 0.0A-29193-1-058"
    assert slice_label(cid) == "0.0A · 058" and patient(cid) == "100"


def test_nan_becomes_null():
    row = {**any_dsr_row(), "nex_z": "nan"}
    nex = next(m for m in slice_json(row, calibration())["metrics"] if m["key"] == "nex")
    assert nex["value"] is None and nex["z"] is None


def test_unknown_version_is_not_found():
    with pytest.raises(NotFound):
        slices_of("nope")


def test_versions_and_status(client):
    v = client.get("/api/versions").json()
    history = json.loads((HISTORY_DIR / "historico.json").read_text(encoding="utf-8"))
    assert [item["name"] for item in v] == [item["name"] for item in history["versions"]]
    assert [item["is_reference"] for item in v] == [item["name"] == history["reference"] for item in v]
    assert all(item["n_common"] == len(history["originals"]) for item in v)
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


def test_slice_mask_only_flag():
    slices = slices_of("Dsr")
    assert all(isinstance(s["mask_only"], bool) for s in slices)
    assert all(s["mask_only"] == (s["pair_mode"] == "só máscara") for s in slices)


def test_slice_english_codes_match_framework_labels():
    from frameworks.texture_evaluator import regional
    from wavelet.src.densidade_wavelet import wavelet_verdict  # noqa: F401  (fonte dos rótulos)
    from workbench.api.data import WAVELET_CODE
    slices = slices_of("Dsr")
    rows = {row["case_id"]: row for row in load_rows(HISTORY_DIR, "Dsr")}
    for s in slices:
        assert s["mode_code"] == ("mask_only" if s["mask_only"] else "same_anatomy")
        assert s["wavelet_type_code"] == WAVELET_CODE[rows[s["case_id"]]["wavelet_verdict"]]
        assert s["wavelet_type"] == rows[s["case_id"]]["wavelet_verdict"]  # campo antigo mantido
    assert regional.SAME_ANATOMY == "mesma anatomia" and regional.MASK_ONLY == "só máscara"


def test_wavelet_codes_cover_every_framework_label():
    from wavelet.src.densidade_wavelet import wavelet_verdict
    from workbench.api.data import WAVELET_CODE
    labels = set()
    for fine in range(0, 201, 5):
        for coarse in range(0, 201, 5):
            for ratio in (0.5, 0.95, 1.0, 1.05, 2.0):
                labels.add(wavelet_verdict({"fine": fine, "coarse": coarse, "ratio": ratio}))
    assert labels == set(WAVELET_CODE)
    assert set(WAVELET_CODE.values()) == {"preserved", "blurred", "noise", "lost_contrast", "gained_contrast", "saturated"}


def test_pct_of_original_is_null_for_air_sat_and_delta():
    s = slices_of("Dsr")[0]
    by_key = {m["key"]: m for m in s["metrics"]}
    for key in ("nps_air", "sat31", "delta_mu"):
        assert by_key[key]["pct_of_original"] is None, key
    assert by_key["ll"]["pct_of_original"] is not None


def test_pct_of_original_null_even_with_air_values():
    row = dict(any_dsr_row())
    row["nps_air_real"], row["nps_air_synthetic"] = "0.5", "1.0"
    by_key = {m["key"]: m for m in slice_json(row, calibration())["metrics"]}
    assert by_key["nps_air"]["real"] == 0.5 and by_key["nps_air"]["synthetic"] == 1.0
    assert by_key["nps_air"]["pct_of_original"] is None
