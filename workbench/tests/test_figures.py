"""Figuras do workbench: seleção de versões (`versions=`), figura de NPS/ar e o dataset Dgen.

Só leitura do histórico real de outputs/placar; o histórico do Dgen é uma cópia temporária.
"""
import io
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from frameworks.texture_evaluator.placar import load_history
from workbench.api import datasets as ds
from workbench.api.app import create_app
from workbench.tests.conftest import DATA_OK, HISTORY_DIR

pytestmark = pytest.mark.skipif(not DATA_OK, reason="outputs/placar/historico.json ou dados/Dsr ausente")

CID = "1.000000-P4P100S300I00003 Gated 0.0A-29193-1-058"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def real_names():
    return [item["name"] for item in load_history(HISTORY_DIR)["versions"]]


def width(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/png"
    assert response.content[:8] == PNG_MAGIC
    return Image.open(io.BytesIO(response.content)).size[0]


def test_technique_versions_subset_is_honoured(client):
    names = real_names()
    url = f"/api/figure/{quote(CID)}/technique/delta_mu.png"
    full = width(client.get(url))
    one = width(client.get(url, params={"versions": names[0]}))
    two = width(client.get(url, params={"versions": f"{names[0]},{names[1]}"}))
    # cada versão a mais é uma coluna a mais: a figura cresce com a seleção
    assert one < two < full


def test_map_versions_subset_is_honoured(client):
    names = real_names()
    url = f"/api/figure/{quote(CID)}/map/fina.png"
    full = width(client.get(url, params={"compared": 1}))
    one = width(client.get(url, params={"compared": 1, "versions": names[0]}))
    assert one < full


def test_versions_unknown_is_404(client):
    for url in (f"/api/figure/{quote(CID)}/technique/delta_mu.png",
                f"/api/figure/{quote(CID)}/map/fina.png",
                f"/api/figure/{quote(CID)}/nps.png"):
        params = {"versions": "Dsr,bogus"}
        if "map" in url:
            params["compared"] = 1
        assert client.get(url, params=params).status_code == 404, url


def test_nps_figure_real_case_png(client):
    assert width(client.get(f"/api/figure/{quote(CID)}/nps.png")) >= 200


def test_nps_figure_explicit_versions(client):
    names = real_names()
    url = f"/api/figure/{quote(CID)}/nps.png"
    assert width(client.get(url, params={"versions": f"{names[0]},{names[-1]}"})) >= 200
    assert width(client.get(url, params={"versions": names[-1]})) >= 200


def test_nps_figure_rejects_more_than_two_versions(client):
    names = real_names()
    if len(names) < 3:
        pytest.skip("precisa de três versões no histórico real")
    r = client.get(f"/api/figure/{quote(CID)}/nps.png", params={"versions": ",".join(names[:3])})
    assert r.status_code == 400


def test_nps_figure_unknown_case_404(client):
    assert client.get("/api/figure/nope/nps.png").status_code == 404


def test_figures_dgen_dataset_path(tmp_history):
    """Dgen com histórico próprio: as três rotas de figura respondem com o dataset pedido."""
    datasets = {"Dsr": {**ds.DATASETS["Dsr"], "history": HISTORY_DIR},
                "Dgen": {**ds.DATASETS["Dgen"], "history": tmp_history}}
    c = TestClient(create_app(datasets))
    params = {"dataset": "Dgen", "versions": "Dsr"}
    assert width(c.get(f"/api/figure/{quote(CID)}/technique/delta_mu.png", params=params)) > 0
    assert width(c.get(f"/api/figure/{quote(CID)}/map/fina.png", params={**params, "compared": 1})) > 0
    assert width(c.get(f"/api/figure/{quote(CID)}/nps.png", params=params)) > 0


def test_figures_dgen_without_history_404(tmp_path):
    datasets = {"Dsr": {**ds.DATASETS["Dsr"], "history": HISTORY_DIR},
                "Dgen": {**ds.DATASETS["Dgen"], "history": tmp_path / "placar_dgen"}}
    c = TestClient(create_app(datasets))
    assert c.get(f"/api/figure/{quote(CID)}/nps.png", params={"dataset": "Dgen"}).status_code == 404


def test_versions_only_commas_means_all(client):
    """Lista vazia depois de limpar (só vírgulas) vale como não pedida, sem quebrar a NPS."""
    assert width(client.get(f"/api/figure/{quote(CID)}/nps.png", params={"versions": ","})) >= 200
    assert width(client.get(f"/api/figure/{quote(CID)}/technique/delta_mu.png", params={"versions": ","})) > 0
