"""Descritores do contrato genérico (`GET /api/schema`): eixos, status, métricas, inspetores e add-ons."""
import math

import pytest
from fastapi.testclient import TestClient

from frameworks.noise_evaluator.integration import AIR_LIMITS
from frameworks.texture_evaluator.visual import MAP_LAYERS, TECHNIQUE_FIGURES
from workbench.api import calibration, data, datasets as ds, notebook, optimizers, reasons
from workbench.api.app import create_app
from workbench.api.contract import AXES, DATASET_LABEL, versions

from .conftest import DATA_OK, HISTORY_DIR

pytestmark = pytest.mark.skipif(not DATA_OK, reason="needs outputs/placar and dados/Dsr")


def _schema(client, dataset="Dsr"):
    response = client.get("/api/schema", params={"dataset": dataset})
    assert response.status_code == 200, response.text
    return response.json()


def test_axes_and_statuses(client):
    body = _schema(client)
    assert [axis["key"] for axis in body["axes"]] == ["texture", "brightness", "noise"]
    assert [axis["label"] for axis in body["axes"]] == [label for _, label in AXES]
    assert all(isinstance(axis["guide"], str) and axis["guide"].strip() for axis in body["axes"])
    assert [(s["key"], s["tone"], s["severity"]) for s in body["statuses"]] == [
        ("approved", "good", 0), ("inconclusive", "neutral", 1), ("review", "warn", 2), ("rejected", "bad", 3)]
    assert all(s["label"] for s in body["statuses"])


def test_noise_method_and_chart_guidance_reach_schema(client):
    body = _schema(client)
    guide = next(a["guide"] for a in body["axes"] if a["key"] == "noise")
    for explanation in ("32 × 32", "overlap by at most 25%", "plane", "subtracted", "Fine anatomy can remain"):
        assert explanation in guide
    descriptions = {m["key"]: m["description"] for m in body["metrics"]}
    for key in ("nps_quantity", "nps_grain", "nps_low_band", "nps_high_band", "nex"):
        assert "Zero is the original" in descriptions[key]
        assert "95% bootstrap interval" in descriptions[key]
    assert "positive means stronger" in descriptions["nps_quantity"]
    assert "positive means finer" in descriptions["nps_grain"]
    assert "positive means more concentrated in wide" in descriptions["nps_low_band"]
    assert "positive means more concentrated in fine" in descriptions["nps_high_band"]
    assert "crosses zero stays green" in descriptions["nps_quantity"]
    assert "never rejects" in descriptions["nex"]
    assert "0.3%" in descriptions["nps_air"] and "policy limits, not clinical" in descriptions["nps_air"]


def test_metric_limits_from_calibration(client):
    body = _schema(client)
    wb = data.load(HISTORY_DIR)
    cal = calibration.calibration_json(wb.history)
    reference = wb.history["reference"]
    first = data.slice_json(wb.rows(reference)[0], wb.history["calibration"])
    by_key = {}
    for metric in body["metrics"]:
        assert metric["key"] not in by_key
        by_key[metric["key"]] = metric
    assert list(by_key) == [m["key"] for m in first["metrics"]]
    for metric in first["metrics"]:
        descriptor = by_key[metric["key"]]
        assert descriptor["label"] == metric["label"]
        assert descriptor["axis"] == metric["group"]
        if metric["key"] != "delta_mu":
            assert descriptor["unit"] == metric["unit"]
        assert descriptor["decimals"] == (1 if metric["unit"] == "%" else 2)
        assert descriptor["description"]
    assert by_key["delta_mu"]["limits"] == {"kind": "abs_value", "review": cal["delta_mu"]["review"],
                                            "reject": cal["delta_mu"]["reject"]}
    assert by_key["delta_mu"]["display"] == "value"
    assert by_key["delta_mu"]["unit"] == ""
    assert by_key["sat31"]["limits"] == {"kind": "above", "review": None, "reject": reasons.SATURATION_LIMIT}
    assert by_key["nps_air"]["limits"] == {"kind": "above", "review": AIR_LIMITS[0], "reject": AIR_LIMITS[1]}
    for key in ("ll", "glcm_contrast", "glcm_energy", "wavelet_fine", "wavelet_coarse", "wavelet_entropy", "nex",
                "nps_quantity", "nps_grain", "nps_low_band", "nps_high_band"):
        assert by_key[key]["limits"] == {"kind": "abs_z", "review": reasons.Z_LIMITS["review"],
                                         "reject": reasons.Z_LIMITS["reject"]}
    assert by_key["nex"]["repeatability"] == cal["nex"]["repeatability_iqr"]
    # display "z" sai das leituras da referência: alguma linha com z finito
    rows = [data.slice_json(row, wb.history["calibration"]) for row in wb.rows(reference)]
    for index, metric in enumerate(first["metrics"]):
        if metric["key"] == "delta_mu":
            continue
        has_z = any(r["metrics"][index]["z"] is not None and math.isfinite(r["metrics"][index]["z"]) for r in rows)
        assert by_key[metric["key"]]["display"] == ("z" if has_z else "value")
    techniques = {t["key"] for t in body["techniques"]}
    assert {m["technique"] for m in body["metrics"]} <= techniques


def test_inspectors(client):
    inspectors = {item["key"]: item for item in _schema(client)["inspectors"]}
    assert list(inspectors) == ["spectrum", "glcm", "nex", "nex_windows", "wavelet", "fine_detail", "coarse_detail", "figure", "map", "noise_figure"]
    assert inspectors["spectrum"]["chart"] == "curves" and inspectors["spectrum"]["compare"] is True
    assert inspectors["glcm"]["chart"] == "matrix"
    assert inspectors["nex"]["chart"] == "interval"
    assert inspectors["nex_windows"]["chart"] == "matrix"
    assert inspectors["wavelet"]["chart"] == "bars"
    assert inspectors["noise_figure"]["chart"] == "image"
    figure = inspectors["figure"]
    assert figure["chart"] == "image"
    assert [c["key"] for c in figure["options"][0]["choices"]] == list(TECHNIQUE_FIGURES)
    mapping = inspectors["map"]
    assert mapping["chart"] == "image"
    options = {option["key"]: option for option in mapping["options"]}
    assert [c["key"] for c in options["layer"]["choices"]] == list(MAP_LAYERS)
    assert [c["key"] for c in options["compared"]["choices"]] == ["yes", "no"]
    for item in inspectors.values():
        assert item["label"]
        for option in item.get("options") or []:
            assert option["label"] and all(choice["label"] for choice in option["choices"])


def test_dataset_labels_and_item_nouns(client):
    body = _schema(client)
    assert body["datasets"]
    assert {item["label"] for item in body["datasets"]} <= set(DATASET_LABEL.values())
    assert [item["key"] for item in body["datasets"]] == list(ds.DATASETS)
    dataset = body["dataset"]
    assert dataset["key"] == "Dsr"
    assert dataset["label"] == DATASET_LABEL[ds.DATASETS["Dsr"]["mode"]]
    assert dataset["item"] == {"singular": "slice", "plural": "slices"}
    group_by = dataset["group_by"]
    assert group_by["key"] == "patient" and group_by["label"] == "Patient"
    assert "independent" in group_by["note"]
    wb = data.load(HISTORY_DIR)
    assert dataset["reference_version"] == wb.history["reference"]
    assert dataset["default_baseline"] == (versions.lab_baseline(wb.history) or data.default_baseline(wb.history))
    assert dataset["has_history"] is True
    assert body["cohort_tests"] == [{"key": "nex_shift", "label": "NEx cohort test", "axis": "texture"}]
    indicators = body["indicators"]
    assert indicators and not any(item["key"].startswith("map_") for item in indicators)
    for item in indicators:
        expected = "higher" if "aprovada" in item["key"] else "lower" if item["ideal"] == 0 else "closer"
        assert item["better"] == expected
        assert item["axis"] in {key for key, _ in AXES}
    assert any("aprovada" in item["key"] and item["better"] == "higher" for item in indicators)


def test_unknown_dataset_is_404(client):
    assert client.get("/api/schema", params={"dataset": "nope"}).status_code == 404


def test_addons_follow_sources(client, tmp_path, monkeypatch):
    results, lab = tmp_path / "results", tmp_path / "lab"
    results.mkdir()
    lab.mkdir()
    monkeypatch.setattr(optimizers, "RESULTS_DIR", results)
    monkeypatch.setattr(notebook, "LAB_DIR", lab)
    assert _schema(client)["addons"] == {"optimizers": False, "experiments": False}
    (results / "gpbo-log.jsonl").write_text("{}\n", encoding="utf-8")
    (lab / notebook.CADERNO).write_text("# caderno\n", encoding="utf-8")
    assert _schema(client)["addons"] == {"optimizers": True, "experiments": True}
    monkeypatch.setattr(optimizers, "RESULTS_DIR", tmp_path / "missing")
    assert _schema(client)["addons"]["optimizers"] is False


def test_schema_without_history(tmp_path):
    datasets = {"Dsr": {**ds.DATASETS["Dsr"], "history": tmp_path / "empty"}}
    body = _schema(TestClient(create_app(datasets)))
    assert body["dataset"]["has_history"] is False
    assert body["dataset"]["reference_version"] is None
    assert body["metrics"] == []
    assert [axis["key"] for axis in body["axes"]] == ["texture", "brightness", "noise"]
    assert body["datasets"] == [{"key": "Dsr", "label": "Same anatomy", "mode_label": "same anatomy",
                                 "has_history": False}]


def test_schema_with_stale_history(stale_dir):
    datasets = {"Dsr": {**ds.DATASETS["Dsr"], "history": stale_dir}}
    body = _schema(TestClient(create_app(datasets)))
    assert body["dataset"]["has_history"] is True
    assert body["dataset"]["stale"] is True
    assert isinstance(body["metrics"], list)
    assert all("limits" in metric for metric in body["metrics"])
    assert [axis["key"] for axis in body["axes"]] == ["texture", "brightness", "noise"]
    assert [status["key"] for status in body["statuses"]] == ["approved", "inconclusive", "review", "rejected"]


def test_technique_keys_match_items(client):
    """As chaves de técnica do schema são as dos itens; toda métrica aponta para uma delas."""
    body = _schema(client)
    wb = data.load(HISTORY_DIR)
    reference = wb.history["reference"]
    item_keys = set()
    for row in wb.rows(reference):
        item = data.slice_json(row, wb.history["calibration"])
        for axis, _ in AXES:
            item_keys |= set(item[axis]["techniques"])
    schema_keys = [t["key"] for t in body["techniques"]]
    assert len(schema_keys) == len(set(schema_keys))
    assert set(schema_keys) == item_keys
    assert all(t["label"] for t in body["techniques"])
    for metric in body["metrics"]:
        assert metric["technique"] in schema_keys, metric["key"]
    by_key = {m["key"]: m["technique"] for m in body["metrics"]}
    assert by_key["nps_quantity"] == "quantity" and by_key["nps_air"] == "air"
    assert by_key["delta_mu"] == by_key["sat31"] == by_key["glcm_contrast"] == "GLCM"
    assert by_key["ll"] == by_key["wavelet_fine"] == "Wavelet" and by_key["nex"] == "NEx"
