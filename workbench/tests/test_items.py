"""Itens do contrato genérico (§4.1): `item_json` e `GET /api/items` batem com `data.slice_json`."""
import pytest

from workbench.api import data, datasets as ds
from workbench.api.contract import AXES
from workbench.api.contract import items
from workbench.tests.conftest import DATA_OK

pytestmark = pytest.mark.skipif(not DATA_OK, reason="histórico real de outputs/placar ausente")

AXIS_KEYS = [key for key, _ in AXES]
NOTE_LABEL = {"few_windows": "too few windows to measure", "lung_not_measured": "lung area not measured",
              "air_unavailable": "air not available", "ci_includes_zero": "interval includes zero"}
WAVELET_LABEL = {"preserved": "preserved texture", "blurred": "blurred", "noise": "noise",
                 "lost_contrast": "lost contrast"}


def _real_slices():
    """Todos os cortes de todas as versões de todos os datasets reais."""
    out = []
    for name in ds.DATASETS:
        try:
            wb = ds.wb_for(name)
        except data.NotFound:
            continue
        for version in wb.history["versions"]:
            out += [data.slice_json(row, wb.history["calibration"]) for row in wb.rows(version["name"])]
    return out


@pytest.fixture(scope="module")
def slices():
    found = _real_slices()
    assert found
    return found


def test_items_match_slice_json(slices):
    for s in slices:
        item = items.item_json(s)
        assert item["id"] == s["case_id"] and item["label"] == s["label"]
        for axis in AXIS_KEYS:
            assert item["verdicts"][axis] == s[axis]["verdict"]
            assert item["techniques"][axis] == s[axis]["techniques"]
        assert set(item["metrics"]) == {m["key"] for m in s["metrics"]}
        for m in s["metrics"]:
            out = item["metrics"][m["key"]]
            assert out["status"] == m["status"]
            if not out["available"]:
                assert out["z"] is None and out["ci"] is None and out["value"] is None
                continue
            assert out["z"] == m["z"]
            ci = None if m["z_low"] is None or m["z_high"] is None else [m["z_low"], m["z_high"]]
            assert out["ci"] == ci
            assert out["pct"] == m["pct_of_original"]
            assert out["real"] == m["real"] and out["synthetic"] == m["synthetic"]


def test_items_route_matches_item_json(client):
    wb = ds.wb_for(ds.DEFAULT)
    version = wb.history["versions"][0]["name"]
    body = client.get("/api/items", params={"dataset": ds.DEFAULT, "version": version}).json()
    expected = [items.item_json(data.slice_json(row, wb.history["calibration"])) for row in wb.rows(version)]
    assert body["version"] == version
    assert [i["id"] for i in body["items"]] == [i["id"] for i in expected]
    assert client.get("/api/items", params={"dataset": "nope", "version": version}).status_code == 404


def test_reasons_carry_axis_and_note_label(slices):
    seen = set()
    for s in slices:
        item = items.item_json(s)
        expected = [(axis, entry) for axis in AXIS_KEYS for entry in s["why"][axis]]
        assert len(item["reasons"]) == len(expected)
        for reason, (axis, entry) in zip(item["reasons"], expected):
            assert reason["axis"] == axis and reason["metric"] == entry["metric"]
            assert reason["note"] == (None if entry["note"] is None else NOTE_LABEL[entry["note"]])
            seen.add(entry["note"])
    # as notas presentes nos dados reais são todas traduzidas (nenhum código cru escapa)
    assert seen - {None} <= set(NOTE_LABEL)


def test_note_labels_cover_every_reason_code():
    assert items.NOTE_LABEL == NOTE_LABEL


def test_facts(slices):
    for s in slices:
        facts = items.item_json(s)["facts"]
        assert [f["label"] for f in facts] == ["Noise ROIs", "Wavelet type", "Pairing", "Density"]
        assert all(isinstance(f["value"], str) for f in facts)
        values = {f["label"]: f["value"] for f in facts}
        if s["wavelet_type_code"] in WAVELET_LABEL:
            assert values["Wavelet type"] == WAVELET_LABEL[s["wavelet_type_code"]]
        assert values["Density"].startswith(s["density"]["status"].replace("_", " "))
        if s["noise_roi_count"] is not None:
            assert values["Noise ROIs"] == str(s["noise_roi_count"])
        assert values["Pairing"] in {"Same anatomy", "Mask only"}


def test_density_fact_format():
    base = {"density": {"status": "ok", "median_shift_iqr": -0.04}}
    assert items._density(base["density"]) == "ok · −0.04 IQR"
    assert items._density({"status": "too_dark", "median_shift_iqr": None}) == "too dark"


def test_unavailable_metric():
    """Review Focus 2: leituras NaN do NPS → métrica indisponível, sem motivo com número nulo."""
    wb = ds.wb_for(ds.DEFAULT)
    row = dict(wb.rows(wb.history["versions"][0]["name"])[0])
    for key in ("quantity", "grain", "low_band", "high_band"):
        for suffix in ("real", "synthetic", "z", "z_low", "z_high"):
            row[f"nps_{key}_{suffix}"] = ""
        row[f"nps_{key}_status"] = "inconclusivo"
    row["nps_available"] = "False"
    row["nps_roi_count"] = ""
    item = items.item_json(data.slice_json(row, wb.history["calibration"]))
    nps = [key for key in item["metrics"] if key.startswith("nps_") and key != "nps_air"]
    assert nps
    for key in nps:
        metric = item["metrics"][key]
        assert metric["available"] is False and metric["z"] is None and metric["ci"] is None
        for reason in (r for r in item["reasons"] if r["metric"] == key):
            # sem número para mostrar: o motivo é só a nota, nunca uma frase com valor nulo
            assert reason["note"] is not None
            assert reason["value"] is None and reason["z"] is None and reason["limit_value"] is None
    assert {f["label"]: f["value"] for f in item["facts"]}["Noise ROIs"] == "n/a"
