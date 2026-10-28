"""Placar interno de geradores (`board.board_json`, base do `/api/board` do contrato), figuras do framework e
administração de versões."""
import json
import shutil
from collections import Counter
from urllib.parse import quote

import numpy as np
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from frameworks.noise_evaluator.integration import noise_verdict
from frameworks.texture_evaluator import placar
from frameworks.texture_evaluator.placar import load_history, load_rows
from workbench.api import data as wb_data
from workbench.api.app import create_app
from workbench.api import board as wb_board
from workbench.api.data import NotFound
from workbench.tests.conftest import DATA_OK, HISTORY_DIR, ROOT, board_of, framework_counts, nonzero, workbench_of

pytestmark = pytest.mark.skipif(not DATA_OK, reason="outputs/placar/historico.json ou dados/Dsr ausente")

CID = "1.000000-P4P100S300I00003 Gated 0.0A-29193-1-058"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
RESULTS = {"improved", "worse", "small change", "no clear difference", "n/a"}


def real_names():
    return [item["name"] for item in load_history(HISTORY_DIR)["versions"]]


def test_board_baseline_only():
    b = board_of()
    g = b["generators"][0]
    assert b["baseline"] == "Dsr" and g["is_baseline"] and g["vs_baseline"] is None
    assert nonzero(g["counts"]["texture"]) == framework_counts(load_rows(HISTORY_DIR, "Dsr"))["texture"]
    assert nonzero(g["counts"]["brightness"]) == framework_counts(load_rows(HISTORY_DIR, "Dsr"))["brightness"]


def test_board_counts_match_framework_for_every_version():
    b = board_of()
    assert [g["name"] for g in b["generators"]] == real_names()
    for g in b["generators"]:
        expected = framework_counts(load_rows(HISTORY_DIR, g["name"]))
        assert nonzero(g["counts"]["texture"]) == expected["texture"], g["name"]
        assert nonzero(g["counts"]["brightness"]) == expected["brightness"], g["name"]


def test_board_vs_itself(tmp_history):
    b = board_of(tmp_history)
    other = next(g for g in b["generators"] if g["name"] == "Dsr-copy")
    assert not other["is_baseline"]
    assert {r["result"] for r in other["vs_baseline"]} <= {"no clear difference", "n/a"}


def test_board_median_z_keys_and_nulls():
    g = board_of()["generators"][0]
    # brilho e textura (e NEx) seguem como antes; ruído tem campo próprio
    assert set(g["median_abs_z"]) == {"delta_mu", "sat31", "ll", "glcm_contrast", "glcm_energy",
                                      "wavelet_fine", "wavelet_coarse", "wavelet_entropy", "nex"}
    assert set(g["median_abs_z_noise"]) == {"nps_quantity", "nps_grain", "nps_low_band", "nps_high_band", "nps_air"}
    assert g["median_abs_z_noise"]["nps_air"] is None
    assert g["median_abs_z"]["sat31"] is None
    assert isinstance(g["median_abs_z"]["nex"], float)
    assert all(isinstance(v, float) for k, v in g["median_abs_z"].items() if v is not None)
    assert all(isinstance(v, float) for k, v in g["median_abs_z_noise"].items() if v is not None)


def noise_counts(rows):
    return nonzero(Counter(wb_data.STATUS[noise_verdict(row)] for row in rows))


def test_board_counts_noise_match_framework():
    b = board_of()
    for g in b["generators"]:
        assert nonzero(g["counts"]["noise"]) == noise_counts(load_rows(HISTORY_DIR, g["name"])), g["name"]


def test_board_scores_for_every_indicator():
    b = board_of()
    expected = placar.build_board(HISTORY_DIR)["scores"]
    from workbench.api.board import INDICATOR_LABEL
    for g in b["generators"]:
        assert set(g["scores"]) == set(INDICATOR_LABEL)
        for key, (value, low, high) in expected[g["name"]].items():
            if key in INDICATOR_LABEL:
                assert g["scores"][key] == [placar.json_value(value), placar.json_value(low), placar.json_value(high)]


def test_board_noise_indicators_in_vs_baseline():
    rows = board_of()["generators"][1]["vs_baseline"]
    noise = [r for r in rows if r["group"] == "noise"]
    assert {r["indicator"] for r in noise} == {"nps_abs_quantity_z", "nps_abs_grain_z", "nps_abs_low_band_z",
                                               "nps_abs_high_band_z", "nps_air_synthetic", "nps_aprovada"}
    assert {r["label"] for r in noise} == {"NPS · quantity", "NPS · grain size", "NPS · wide patterns",
                                           "NPS · fine grain", "Air spots", "NPS · slices approved"}
    assert {r["result"] for r in noise} <= RESULTS


def test_board_baseline_param_changes_reference():
    b = board_of(baseline="Dsr-baseline")
    assert b["baseline"] == "Dsr-baseline"
    by_name = {g["name"]: g for g in b["generators"]}
    assert by_name["Dsr-baseline"]["is_baseline"] and by_name["Dsr-baseline"]["vs_baseline"] is None
    assert not by_name["Dsr"]["is_baseline"] and by_name["Dsr"]["vs_baseline"] is not None
    # mesmo cálculo do framework, com os cortes comuns ordenados como no placar
    history_rows = {name: {r["case_id"]: r for r in load_rows(HISTORY_DIR, name)} for name in real_names()}
    common = sorted(set.intersection(*(set(rows) for rows in history_rows.values())))
    previous = [history_rows["Dsr-baseline"][c] for c in common]
    current = [history_rows["Dsr"][c] for c in common]
    gains = placar.compare(previous, current, np.random.default_rng(0))
    nex = next(r for r in by_name["Dsr"]["vs_baseline"] if r["indicator"] == "nex")
    assert nex["gain"] == placar.json_value(gains["nex"][0])
    assert nex["ci"] == [placar.json_value(gains["nex"][1]), placar.json_value(gains["nex"][2])]


def test_board_unknown_baseline_is_not_found():
    with pytest.raises(NotFound, match="version not found: Versao-inexistente"):
        board_of(baseline="Versao-inexistente")


def test_board_results_are_english(tmp_history):
    b = board_of(tmp_history)
    rows = b["generators"][1]["vs_baseline"]
    assert {r["result"] for r in rows} <= RESULTS
    assert all(set(r) == {"indicator", "label", "group", "gain", "ci", "result"} for r in rows)


def test_figures():
    wb = workbench_of()
    names = list(wb.board["names"])
    assert wb_board.map_png(wb, CID, "fina", True, names)[:8] == PNG_MAGIC
    assert wb_board.technique_png(wb, CID, "glcm_contraste", names)[:8] == PNG_MAGIC
    assert wb_board.technique_png(wb, CID, "delta_mu", names)[:8] == PNG_MAGIC


def test_figure_unknown_technique_layer_case_is_not_found():
    wb = workbench_of()
    names = list(wb.board["names"])
    with pytest.raises(NotFound, match="unknown technique: bogus"):
        wb_board.technique_png(wb, CID, "bogus", names)
    with pytest.raises(NotFound, match="unknown layer: bogus"):
        wb_board.map_png(wb, CID, "bogus", True, names)
    with pytest.raises(NotFound):
        wb_board.technique_png(wb, "nope", "delta_mu", names)
    with pytest.raises(NotFound):
        wb_board.map_png(wb, "nope", "veredito", True, names)
    with pytest.raises(NotFound):
        wb_board.map_png(wb, "nope", "brilho", False, names)


def test_map_veredito_needs_comparison():
    wb = workbench_of()
    with pytest.raises(HTTPException) as error:
        wb_board.map_png(wb, CID, "veredito", False, list(wb.board["names"]))
    assert error.value.status_code == 400
    assert error.value.detail == "the verdict layer exists only compared with the original"


def test_admin_errors(tmp_history):
    c = TestClient(create_app(tmp_history))
    assert c.post("/api/versions", json={"name": "x", "folder": "/nope"}).status_code == 400
    assert c.delete("/api/versions/Dsr").status_code == 400
    assert c.delete("/api/versions/Versao-inexistente").status_code == 404
    assert c.delete("/api/versions/Dsr-copy").status_code == 200
    assert [v["name"] for v in c.get("/api/versions").json()] == real_names()


def test_add_duplicate_name_400(tmp_history):
    c = TestClient(create_app(tmp_history))
    r = c.post("/api/versions", json={"name": "Dsr-copy", "folder": str(ROOT / "dados" / "Dsr")})
    assert r.status_code == 400 and "detail" in r.json()


def test_admin_writes_only_to_app_history(tmp_history):
    c = TestClient(create_app(tmp_history))
    assert c.delete("/api/versions/Dsr-copy").status_code == 200
    assert (tmp_history / "placar.csv").exists()
    assert not (tmp_history / "versoes" / "Dsr-copy.csv").exists()
    hist = json.loads((tmp_history / "historico.json").read_text(encoding="utf-8"))
    assert [v["name"] for v in hist["versions"]] == real_names()


def test_refresh_route(tmp_history):
    c = TestClient(create_app(tmp_history))
    r = c.post("/api/refresh")
    assert r.status_code == 200 and "recalculada" in r.json()["message"]


def test_board_has_no_merged_verdict_indicators(tmp_history):
    b = board_of(tmp_history)
    keys = {r["indicator"] for r in b["generators"][1]["vs_baseline"]}
    assert not keys & {"aprovada", "brilho", "textura"}
    for r in b["generators"][1]["vs_baseline"]:
        assert r["group"] in {"brightness", "texture", "noise"}
        assert not any(w in r["label"].lower() for w in ("filtro", "veredito", "mapa:"))


def test_add_version_rejects_bad_names(tmp_history):
    c = TestClient(create_app(tmp_history))
    folder = str(ROOT / "dados" / "Dsr")
    assert c.post("/api/versions", json={"name": "a b/c", "folder": folder}).status_code == 400
    assert c.post("/api/versions", json={"name": "../x", "folder": folder}).status_code == 400
    r = c.post("/api/versions", json={"name": "Dsr-copy ", "folder": folder})
    assert r.status_code == 400


def test_add_version_rejects_csv_collision(tmp_history):
    from workbench.api import board
    from frameworks.texture_evaluator import placar
    # nome válido cujo CSV colide com o de uma versão existente
    history = placar.load_history(tmp_history)
    history["versions"][1]["name"] = "weird name"  # versão existente com espaço: CSV vira weird_name.csv
    (tmp_history / "versoes" / "weird_name.csv").write_text("x\n", encoding="utf-8")
    (tmp_history / "historico.json").write_text(json.dumps(history), encoding="utf-8")
    c = TestClient(create_app(tmp_history))
    r = c.post("/api/versions", json={"name": "weird_name", "folder": str(ROOT / "dados" / "Dsr")})
    assert r.status_code == 400 and "detail" in r.json()


def test_refresh_without_history_is_404(tmp_path):
    c = TestClient(create_app(tmp_path / "vazio"))
    r = c.post("/api/refresh")
    assert r.status_code == 404 and r.json()["detail"] == "dataset has no history: Dsr"


def test_refresh_unknown_dataset_is_404(tmp_history):
    r = TestClient(create_app(tmp_history)).post("/api/refresh", params={"dataset": "Nope"})
    assert r.status_code == 404 and r.json()["detail"] == "unknown dataset: Nope"


def test_error_details_are_english(tmp_history):
    c = TestClient(create_app(tmp_history))
    assert c.get("/api/status", params={"dataset": "Nope"}).json()["detail"] == "unknown dataset: Nope"
    assert c.get(f"/api/image/Dsr/{quote(CID)}/bogus.png").json()["detail"] == "unknown image kind: bogus"
    assert c.post("/api/versions", json={"folder": "/nao/existe"}).json()["detail"] == \
        "version folder not found: /nao/existe"
    assert c.delete("/api/versions/Dsr").json()["detail"] == "the reference version cannot be removed"


def test_board_indicator_metadata():
    from workbench.api.board import INDICATOR_LABEL, UNIT
    b = board_of()
    by_key = {i.key: i for i in placar.INDICATORS}
    expected_keys = [i.key for i in placar.INDICATORS if i.key in INDICATOR_LABEL]
    assert [m["key"] for m in b["indicators"]] == expected_keys
    for m in b["indicators"]:
        ind = by_key[m["key"]]
        assert set(m) == {"key", "label", "group", "unit", "ideal", "min_change"}
        assert m["label"] == INDICATOR_LABEL[m["key"]]
        assert m["group"] in {"brightness", "texture", "noise"}
        assert m["unit"] == UNIT[ind.unit]
        assert isinstance(m["ideal"], float) and m["ideal"] == ind.ideal
        assert m["min_change"] == ind.min_change
    for g in b["generators"]:
        assert set(g["scores"]) == set(expected_keys)


def test_board_mode_code():
    assert {g["mode_code"] for g in board_of()["generators"]} == {"same_anatomy"}


def test_default_baseline_is_history_reference(tmp_history):
    path = tmp_history / "historico.json"
    history = json.loads(path.read_text(encoding="utf-8"))
    history["reference"] = "Dsr-copy"
    path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    assert board_of(tmp_history)["baseline"] == "Dsr-copy"
    assert TestClient(create_app(tmp_history)).get("/api/status").json()["baseline"] == "Dsr-copy"


def test_default_baseline_without_reference_is_first_version(tmp_history):
    path = tmp_history / "historico.json"
    history = json.loads(path.read_text(encoding="utf-8"))
    del history["reference"]
    path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    assert board_of(tmp_history)["baseline"] == "Dsr"


def test_board_is_memoised_and_computes_each_row_once(monkeypatch):
    from workbench.api import board as wb_board, data as wb_data_mod
    wb = wb_data_mod.load(HISTORY_DIR)
    monkeypatch.setattr(wb_board, "_BOARD_CACHE", {})
    calls = {"n": 0}
    real = wb_data_mod.slice_json

    def counting(row, calibration):
        calls["n"] += 1
        return real(row, calibration)

    monkeypatch.setattr(wb_data_mod, "slice_json", counting)
    first = wb_board.board_json(wb)
    total_rows = sum(len(rows) for rows in wb.board["rows"].values())
    assert calls["n"] == total_rows
    calls["n"] = 0
    second = wb_board.board_json(wb)
    assert second == first and calls["n"] == 0
