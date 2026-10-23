"""Placar de geradores, figuras do framework e administração de versões."""
import json
import shutil
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from workbench.api.app import create_app
from workbench.tests.conftest import DATA_OK, ROOT

pytestmark = pytest.mark.skipif(not DATA_OK, reason="outputs/placar/historico.json ou dados/Dsr ausente")

CID = "1.000000-P4P100S300I00003 Gated 0.0A-29193-1-058"
RESULTS = {"improved", "worse", "small change", "no clear difference", "n/a"}


def test_board_baseline_only(client):
    b = client.get("/api/board").json()
    g = b["generators"][0]
    assert b["baseline"] == "Dsr" and g["is_baseline"] and g["vs_baseline"] is None
    assert g["counts"]["texture"] == {"approved": 8, "review": 29, "rejected": 0}


def test_board_vs_itself(tmp_history):
    b = TestClient(create_app(tmp_history)).get("/api/board").json()
    other = b["generators"][1]
    assert other["name"] == "Dsr-copy" and not other["is_baseline"]
    assert {r["result"] for r in other["vs_baseline"]} <= {"no clear difference", "n/a"}


def test_board_median_z_keys_and_nulls(client):
    g = client.get("/api/board").json()["generators"][0]
    assert set(g["median_abs_z"]) == {"delta_mu", "sat31", "ll", "glcm_contrast", "glcm_energy",
                                      "wavelet_fine", "wavelet_coarse", "wavelet_entropy", "nex"}
    assert g["median_abs_z"]["sat31"] is None and g["median_abs_z"]["nex"] is None
    assert all(isinstance(v, float) for k, v in g["median_abs_z"].items() if v is not None)


def test_board_results_are_english(tmp_history):
    b = TestClient(create_app(tmp_history)).get("/api/board").json()
    rows = b["generators"][1]["vs_baseline"]
    assert {r["result"] for r in rows} <= RESULTS
    assert all(set(r) == {"indicator", "label", "gain", "ci", "result"} for r in rows)


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
    assert [v["name"] for v in c.get("/api/versions").json()] == ["Dsr"]


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
    assert [v["name"] for v in hist["versions"]] == ["Dsr"]


def test_refresh_route(tmp_history):
    c = TestClient(create_app(tmp_history))
    r = c.post("/api/refresh")
    assert r.status_code == 200 and "recalculada" in r.json()["message"]
