"""Inspetores do contrato genérico (§4.2): `GET /api/inspect/{key}` reescreve as ferramentas do workbench."""
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import numpy as np
import pytest

from frameworks.texture_evaluator.run_mvp import context_from_dict
from frameworks.texture_evaluator.visual import MAP_LAYERS, TECHNIQUE_FIGURES
from workbench.api import data, datasets as ds, images, tools
from workbench.api.contract import versions
from workbench.api.contract.items import item_json
from workbench.tests.conftest import DATA_OK

pytestmark = pytest.mark.skipif(not DATA_OK, reason="histórico real de outputs/placar ausente")


@pytest.fixture(scope="module")
def wb():
    return ds.wb_for(ds.DEFAULT)


@pytest.fixture(scope="module")
def cid(wb):
    return wb.board["rows"][wb.board["names"][0]][0]["case_id"]


def _labels(wb):
    meta = versions.load_meta(Path(wb.history_dir))
    return {v["name"]: versions.version_label(v["name"], wb.history, meta) for v in wb.history["versions"]}


def _get(client, key, **params):
    return client.get(f"/api/inspect/{key}", params={"dataset": ds.DEFAULT, **params})


def test_spectrum_series_band_and_marker(client, wb, cid):
    names = [v["name"] for v in wb.history["versions"]][-2:]
    body = _get(client, "spectrum", version=names[0], item=cid, compare=",".join(names))
    assert body.status_code == 200
    body = body.json()
    roles = [s["role"] for s in body["series"]]
    assert roles == ["real"] + ["version"] * len(names)
    labels = _labels(wb)
    assert [s["label"] for s in body["series"][1:]] == [labels[name] for name in names]
    band = tools.reference_band(wb)
    assert body["band"]["lo"] == pytest.approx(band["p5"]) and body["band"]["hi"] == pytest.approx(band["p95"])
    assert [m["x"] for m in body["markers"]] == [0.5]
    ruler = context_from_dict(wb.history["calibration"]).ruler
    case = images.case(wb, names[1], cid)
    _, synthetic = tools.radial_spectrum(tools.normalise(case.synthetic, ruler), case.lung_mask)
    assert body["series"][2]["y"] == pytest.approx(synthetic)
    assert body["series"][0]["x"] == body["band"]["x"]


def test_spectrum_without_compare_uses_version(client, wb, cid):
    body = _get(client, "spectrum", version="Dsr", item=cid).json()
    assert [s["label"] for s in body["series"][1:]] == [_labels(wb)["Dsr"]]


def test_glcm_panels(client, wb, cid):
    version = wb.history["versions"][-1]["name"]
    body = _get(client, "glcm", version=version, item=cid).json()
    scale = context_from_dict(wb.history["calibration"]).scale
    case = images.case(wb, version, cid)
    assert [p["label"] for p in body["panels"]] == ["Real", f"Synthetic · {_labels(wb)[version]}"]
    assert np.allclose(body["panels"][0]["values"], tools.glcm_matrix(case.original, case.lung_mask, scale))
    assert np.allclose(body["panels"][1]["values"], tools.glcm_matrix(case.synthetic, case.lung_mask, scale))
    assert len(body["rows"]) == len(body["cols"]) == scale.levels


def test_nex_interval(client, wb, cid):
    version = wb.history["versions"][-1]["name"]
    body = _get(client, "nex", version=version, item=cid).json()
    item = item_json(data.slice_json(wb.row(version, cid), wb.history["calibration"]))
    assert body["value"] == item["metrics"]["nex"]["z"]
    assert body["ci"] == item["metrics"]["nex"]["ci"]
    edges = [b["from"] for b in body["bands"]] + [body["bands"][-1]["to"]]
    assert edges == [-4, -1, 1, 4]  # NEx sozinho nunca rejeita: só revisão além de ±1 IQR
    assert [b["status"] for b in body["bands"]] == ["review", "approved", "review"]


def test_nex_windows_matrix(client, wb, cid):
    body = _get(client, "nex_windows", version="Dsr", item=cid).json()
    case = images.case(wb, "Dsr", cid)
    windows = tools.nex_windows(case.original, case.lung_mask)
    assert [p["label"] for p in body["panels"]][0] == "Real"
    grid = body["panels"][0]["values"]
    for w in windows:
        value = grid[body["rows"].index(w["row"])][body["cols"].index(w["col"])]
        assert value == pytest.approx(w["value"])


def test_wavelet_bars(client, wb, cid):
    version = wb.history["versions"][-1]["name"]
    body = _get(client, "wavelet", version=version, item=cid).json()
    ruler = context_from_dict(wb.history["calibration"]).ruler
    case = images.case(wb, version, cid)
    real = tools.wavelet_bands(tools.normalise(case.original, ruler), case.lung_mask)
    synthetic = tools.wavelet_bands(tools.normalise(case.synthetic, ruler), case.lung_mask)
    assert [b["label"] for b in body["bars"]] == [f"{r['band']} e{r['level']}" for r in real]
    expected = [tools.log2_ratio(tools.json_number(r["energy"]), tools.json_number(s["energy"]))
                for r, s in zip(real, synthetic)]
    assert [b["value"] for b in body["bars"]] == pytest.approx(expected)
    assert body["zero"] == 0


def test_map_png(client, wb, cid):
    layer = next(iter(MAP_LAYERS))
    body = _get(client, "map", version=wb.history["versions"][-1]["name"], item=cid, layer=layer, compared="yes")
    assert body.status_code == 200
    url = body.json()["url"]
    assert url.startswith("/api/inspect/map.png?") and body.json()["caption"]
    query = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
    assert query["item"] == cid and query["layer"] == layer and query["compared"] == "yes"
    png = client.get(url)
    assert png.status_code == 200 and png.headers["content-type"] == "image/png" and png.content


def test_figure_and_noise_urls(client, wb, cid):
    technique = next(iter(TECHNIQUE_FIGURES))
    figure = _get(client, "figure", version=wb.history["versions"][-1]["name"], item=cid, technique=technique).json()
    assert figure["url"].startswith("/api/inspect/figure.png?") and figure["caption"]
    noise = _get(client, "noise_figure", version=wb.history["versions"][-1]["name"], item=cid).json()
    png = client.get(noise["url"])
    assert png.status_code == 200 and png.headers["content-type"] == "image/png" and png.content


def test_errors(client, cid):
    assert _get(client, "map", version="Dsr", item=cid, layer="nope", compared="yes").status_code == 400
    assert client.get("/api/inspect/map.png", params={"version": "Dsr", "item": cid, "layer": "nope"}).status_code == 400
    assert _get(client, "map", version="Dsr", item=cid, compared="maybe").status_code == 400
    assert _get(client, "unknown", version="Dsr", item=cid).status_code == 404
    assert client.get("/api/inspect/unknown.png", params={"version": "Dsr", "item": cid}).status_code == 404
    assert _get(client, "spectrum", version="Versao-inexistente", item=cid).status_code == 404
    assert _get(client, "glcm", version="Dsr", item="nope").status_code == 404


@pytest.mark.parametrize("key, function", [("glcm", "glcm_matrix"), ("spectrum", "radial_spectrum")])
def test_tiny_lung_is_422(client, cid, monkeypatch, key, function):
    def broken(*args, **kwargs):
        raise ValueError("ROI has no valid neighbour pairs")

    monkeypatch.setattr(tools, function, broken)
    response = _get(client, key, version="Dsr", item=cid)
    assert response.status_code == 422
    assert "ROI has no valid neighbour pairs" in response.json()["detail"]


@pytest.mark.parametrize("key", ["fine_detail", "coarse_detail"])
def test_detail_image_compares_selected_versions(client, wb, cid, key):
    names = [v["name"] for v in wb.history["versions"]][-2:]
    response = _get(client, key, version=names[-1], item=cid, compare=",".join(names))
    assert response.status_code == 200
    body = response.json()
    assert body["caption"] and parse_qs(urlsplit(body["url"]).query)["compare"] == [",".join(names)]
    png = client.get(body["url"])
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"
