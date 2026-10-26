"""Placar de geradores, figuras do framework e administração de versões."""
import json
import shutil
from collections import Counter
from urllib.parse import quote

import numpy as np
import pytest
from fastapi.testclient import TestClient

from frameworks.noise_evaluator.integration import noise_verdict
from frameworks.texture_evaluator import placar
from frameworks.texture_evaluator.placar import load_history, load_rows
from workbench.api import data as wb_data
from workbench.api.app import create_app
from workbench.tests.conftest import DATA_OK, HISTORY_DIR, ROOT, framework_counts, nonzero

pytestmark = pytest.mark.skipif(not DATA_OK, reason="outputs/placar/historico.json ou dados/Dsr ausente")

CID = "1.000000-P4P100S300I00003 Gated 0.0A-29193-1-058"
RESULTS = {"improved", "worse", "small change", "no clear difference", "n/a"}


def real_names():
    return [item["name"] for item in load_history(HISTORY_DIR)["versions"]]


def test_board_baseline_only(client):
    b = client.get("/api/board").json()
    g = b["generators"][0]
    assert b["baseline"] == "Dsr" and g["is_baseline"] and g["vs_baseline"] is None
    assert nonzero(g["counts"]["texture"]) == framework_counts(load_rows(HISTORY_DIR, "Dsr"))["texture"]
    assert nonzero(g["counts"]["brightness"]) == framework_counts(load_rows(HISTORY_DIR, "Dsr"))["brightness"]


def test_board_counts_match_framework_for_every_version(client):
    b = client.get("/api/board").json()
    assert [g["name"] for g in b["generators"]] == real_names()
    for g in b["generators"]:
        expected = framework_counts(load_rows(HISTORY_DIR, g["name"]))
        assert nonzero(g["counts"]["texture"]) == expected["texture"], g["name"]
        assert nonzero(g["counts"]["brightness"]) == expected["brightness"], g["name"]


def test_board_vs_itself(tmp_history):
    b = TestClient(create_app(tmp_history)).get("/api/board").json()
    other = next(g for g in b["generators"] if g["name"] == "Dsr-copy")
    assert not other["is_baseline"]
    assert {r["result"] for r in other["vs_baseline"]} <= {"no clear difference", "n/a"}


def test_board_median_z_keys_and_nulls(client):
    g = client.get("/api/board").json()["generators"][0]
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


def test_board_counts_noise_match_framework(client):
    b = client.get("/api/board").json()
    for g in b["generators"]:
        assert nonzero(g["counts"]["noise"]) == noise_counts(load_rows(HISTORY_DIR, g["name"])), g["name"]


def test_board_scores_for_every_indicator(client):
    b = client.get("/api/board").json()
    expected = placar.build_board(HISTORY_DIR)["scores"]
    keys = {i.key for i in placar.INDICATORS}
    for g in b["generators"]:
        assert set(g["scores"]) == keys
        for key, (value, low, high) in expected[g["name"]].items():
            assert g["scores"][key] == [placar.json_value(value), placar.json_value(low), placar.json_value(high)]


def test_board_noise_indicators_in_vs_baseline(client):
    rows = client.get("/api/board").json()["generators"][1]["vs_baseline"]
    noise = [r for r in rows if r["group"] == "noise"]
    assert {r["indicator"] for r in noise} == {"nps_abs_quantity_z", "nps_abs_grain_z", "nps_abs_low_band_z",
                                               "nps_abs_high_band_z", "nps_air_synthetic", "nps_aprovada"}
    assert {r["label"] for r in noise} == {"NPS · quantity", "NPS · grain size", "NPS · wide patterns",
                                           "NPS · fine grain", "Air spots", "NPS · slices approved"}
    assert {r["result"] for r in noise} <= RESULTS


def test_board_baseline_param_changes_reference(client):
    b = client.get("/api/board", params={"baseline": "Dsr-baseline"}).json()
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


def test_board_unknown_baseline_404(client):
    assert client.get("/api/board", params={"baseline": "Versao-inexistente"}).status_code == 404


def test_board_results_are_english(tmp_history):
    b = TestClient(create_app(tmp_history)).get("/api/board").json()
    rows = b["generators"][1]["vs_baseline"]
    assert {r["result"] for r in rows} <= RESULTS
    assert all(set(r) == {"indicator", "label", "group", "gain", "ci", "result"} for r in rows)


def test_figures(client):
    assert client.get(f"/api/figure/{quote(CID)}/map/fina.png", params={"compared": 1}).status_code == 200
    assert client.get(f"/api/figure/{quote(CID)}/technique/glcm_contraste.png").status_code == 200


def test_figures_are_png(client):
    r = client.get(f"/api/figure/{quote(CID)}/technique/delta_mu.png")
    assert r.headers["content-type"] == "image/png" and r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_figure_unknown_technique_layer_case_404(client):
    assert client.get(f"/api/figure/{quote(CID)}/technique/bogus.png").status_code == 404
    assert client.get(f"/api/figure/{quote(CID)}/map/bogus.png", params={"compared": 1}).status_code == 404
    assert client.get(f"/api/figure/{quote(CID)}/technique/delta_mu.png").status_code == 200
    assert client.get("/api/figure/nope/technique/delta_mu.png").status_code == 404


def test_map_veredito_needs_comparison(client):
    assert client.get(f"/api/figure/{quote(CID)}/map/veredito.png", params={"compared": 0}).status_code == 400


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
    b = TestClient(create_app(tmp_history)).get("/api/board").json()
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


def test_refresh_errors_are_400(tmp_path):
    c = TestClient(create_app(tmp_path / "vazio"))
    r = c.post("/api/refresh")
    assert r.status_code == 400 and "detail" in r.json()


def test_map_unknown_case_404(client):
    assert client.get("/api/figure/nope/map/veredito.png", params={"compared": 1}).status_code == 404
    assert client.get("/api/figure/nope/map/brilho.png", params={"compared": 0}).status_code == 404
