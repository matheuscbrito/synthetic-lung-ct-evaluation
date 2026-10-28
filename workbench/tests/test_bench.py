"""Benchmark, transições e coorte do contrato genérico (§4.3): `/api/board` e `/api/transitions`.

Valores esperados vêm de `items.item_json`, `compare.transitions`, `compare.cohort` e `versions` (nunca fixos).
Somente leitura do histórico real; a escrita de rótulo usa `tmp_history`.
"""
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from workbench.api import compare, data, datasets as ds
from workbench.api.app import create_app
from workbench.api.contract import AXES, bench, items, schema
from workbench.api.contract import versions as cv
from workbench.tests.conftest import DATA_OK

pytestmark = pytest.mark.skipif(not DATA_OK, reason="histórico real de outputs/placar ausente")

AXIS_KEYS = [key for key, _ in AXES]
STATUS_KEYS = {"approved", "inconclusive", "review", "rejected"}
VERSION_KEYS = {"name", "label", "subtitle", "is_reference", "provenance", "counts", "scores", "vs_baseline", "cohort"}


@pytest.fixture(scope="module")
def api():
    return TestClient(create_app())


@pytest.fixture(scope="module")
def wb():
    return ds.wb_for(ds.DEFAULT)


@pytest.fixture(scope="module")
def body(api):
    response = api.get("/api/board", params={"dataset": ds.DEFAULT})
    assert response.status_code == 200
    return response.json()


def expected_baseline(history: dict) -> str:
    return cv.lab_baseline(history) or data.default_baseline(history)


def test_default_baseline_is_lab_baseline(body, wb):
    assert body["baseline"] == expected_baseline(wb.history)
    assert body["n_items"] == wb.board["n_cases"]


def test_default_baseline_falls_back_to_data_default():
    history = {"reference": "a", "versions": [{"name": "a"}, {"name": "b"}]}
    assert cv.lab_baseline(history) is None
    assert bench.default_baseline(history) == data.default_baseline(history) == "a"


def test_schema_default_baseline_matches_board(api, body):
    schema = api.get("/api/schema", params={"dataset": ds.DEFAULT}).json()
    assert schema["dataset"]["default_baseline"] == body["baseline"]


def test_versions_shape_label_subtitle(body, wb):
    meta = cv.load_meta(wb.history_dir)
    assert [v["name"] for v in body["versions"]] == list(wb.board["names"])
    for version in body["versions"]:
        assert set(version) == VERSION_KEYS
        name = version["name"]
        is_reference = name == wb.history.get("reference")
        assert version["is_reference"] is is_reference
        assert version["subtitle"] == ("ruler reference" if is_reference else "")
        assert version["label"] == cv.version_label(name, wb.history, meta)
        assert version["provenance"] == (meta.get(name) or {}).get("provenance")


def test_counts_equal_item_verdict_tallies(body, wb):
    calibration = wb.history["calibration"]
    for version in body["versions"]:
        rows = [items.item_json(data.slice_json(row, calibration)) for row in wb.board["rows"][version["name"]]]
        assert set(version["counts"]) == set(AXIS_KEYS)
        for axis in AXIS_KEYS:
            tally = Counter(item["verdicts"][axis] for item in rows)
            assert version["counts"][axis] == {status: tally.get(status, 0) for status in STATUS_KEYS}


def test_scores_come_from_board_json(body, wb):
    from workbench.api import board
    keys = {item["key"] for item in schema.indicators()}
    generators = {g["name"]: g for g in board.board_json(wb, body["baseline"])["generators"]}
    for version in body["versions"]:
        expected = {key: value for key, value in generators[version["name"]]["scores"].items() if key in keys}
        assert version["scores"] == expected


def test_board_indicators_are_the_schema_indicators(body):
    """Só os indicadores do schema chegam à interface (os `map_*` ficam de fora, como em `schema.indicators`)."""
    keys = {item["key"] for item in schema.indicators()}
    for version in body["versions"]:
        assert set(version["scores"]) <= keys
        assert {entry["indicator"] for entry in version["vs_baseline"] or []} <= keys


def test_vs_baseline_results_and_shape(body):
    seen = set()
    for version in body["versions"]:
        if version["name"] == body["baseline"]:
            assert version["vs_baseline"] is None
            continue
        assert version["vs_baseline"]
        for entry in version["vs_baseline"]:
            assert set(entry) == {"indicator", "gain", "ci", "result"}
            assert entry["result"] in {"improved", "worse", "small", "same"}
            seen.add(entry["result"])
    assert seen


def test_vs_baseline_result_mapping():
    assert bench.RESULT == {"improved": "improved", "worse": "worse", "small change": "small",
                            "no clear difference": "same", "n/a": "same"}


def test_cohort_follows_compare_cohort(body, wb):
    for version in body["versions"]:
        if version["name"] == body["baseline"]:
            assert version["cohort"] == []
            continue
        (entry,) = version["cohort"]
        stat = compare.cohort(wb, version["name"])["nex_test"]
        assert entry["test"] == "nex_shift"
        assert (entry["result"]["status"] == "review") is stat["systematic"]
        assert entry["result"]["status"] in STATUS_KEYS and entry["result"]["label"]
        assert [d["label"] for d in entry["detail"]] == ["p", "median z", "n"]
        assert all(isinstance(d["value"], str) for d in entry["detail"])
        assert entry["detail"][2]["value"] == str(stat["n"])


@pytest.mark.parametrize("stat, status", [
    ({"n": 30, "p": 0.01, "median_z": 0.8, "systematic": True, "direction": "higher"}, "review"),
    ({"n": 30, "p": 0.6, "median_z": 0.1, "systematic": False, "direction": None}, "approved"),
    ({"n": 4, "p": None, "median_z": None, "systematic": False, "direction": None}, "inconclusive"),
])
def test_cohort_entry_statuses(stat, status):
    entry = bench.cohort_entry(stat)
    assert entry["result"]["status"] == status
    assert [d["label"] for d in entry["detail"]] == ["p", "median z", "n"]
    if stat["p"] is None:
        assert entry["detail"][0]["value"] == "n/a" and entry["detail"][1]["value"] == "n/a"


def test_explicit_baseline_switches_vs_baseline(api, wb):
    reference = wb.history["reference"]
    body = api.get("/api/board", params={"dataset": ds.DEFAULT, "baseline": reference}).json()
    assert body["baseline"] == reference
    by_name = {v["name"]: v for v in body["versions"]}
    assert by_name[reference]["vs_baseline"] is None and by_name[reference]["cohort"] == []
    assert api.get("/api/board", params={"dataset": ds.DEFAULT, "baseline": "nope"}).status_code == 404
    assert api.get("/api/board", params={"dataset": "nope"}).status_code == 404


def test_board_label_follows_meta(tmp_history):
    client = TestClient(create_app(tmp_history))
    assert client.patch("/api/versions/Dsr-copy", params={"dataset": "Dsr"}, json={"label": "copy #1"}).status_code == 200
    body = client.get("/api/board", params={"dataset": "Dsr"}).json()
    assert {v["name"]: v["label"] for v in body["versions"]}["Dsr-copy"] == "copy #1"


@pytest.mark.parametrize("axis", AXIS_KEYS)
def test_transitions_match_compare(api, wb, axis):
    names = list(wb.board["names"])
    before, after = names[0], names[-1]
    response = api.get("/api/transitions",
                       params={"dataset": ds.DEFAULT, "before": before, "after": after, "axis": axis})
    assert response.status_code == 200
    expected = [{"id": t["case_id"], "before": t["before"], "after": t["after"], "change": t["change"],
                 "became_approved": t["became_approved"]} for t in compare.transitions(wb, before, after, axis)]
    assert response.json() == expected


def test_transitions_unknown_axis_is_400(api, wb):
    name = wb.board["names"][0]
    response = api.get("/api/transitions", params={"dataset": ds.DEFAULT, "before": name, "after": name, "axis": "foo"})
    assert response.status_code == 400


def test_transitions_unknown_version_is_404(api, wb):
    name = wb.board["names"][0]
    response = api.get("/api/transitions", params={"dataset": ds.DEFAULT, "before": name, "after": "nope", "axis": "noise"})
    assert response.status_code == 404
