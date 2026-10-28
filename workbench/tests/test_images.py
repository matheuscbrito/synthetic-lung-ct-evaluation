"""Endpoints de imagem do workbench: pares real/sintético, diferença e contorno da máscara."""
from io import BytesIO
from urllib.parse import quote

import numpy as np
import pytest
from PIL import Image

from workbench.tests.conftest import DATA_OK, HISTORY_DIR

pytestmark = pytest.mark.skipif(not DATA_OK, reason="outputs/placar/historico.json ou dados/Dsr ausente")

CID = "1.000000-P4P100S300I00003 Gated 0.0A-29193-1-058"


def test_real_png(client):
    r = client.get(f"/api/image/Dsr/{quote(CID)}/real.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert Image.open(BytesIO(r.content)).size == (512, 512)


def test_thumbnail_size(client):
    r = client.get(f"/api/image/Dsr/{quote(CID)}/synthetic.png", params={"size": 128})
    assert Image.open(BytesIO(r.content)).size == (128, 128)


def test_contour_is_rgba_and_sparse(client):
    im = Image.open(BytesIO(client.get(f"/api/image/Dsr/{quote(CID)}/contour.png").content))
    alpha = np.array(im)[..., 3]
    assert im.mode == "RGBA" and 0 < (alpha > 0).mean() < 0.05


def test_unknown_case_and_kind_404(client):
    assert client.get("/api/image/Dsr/nope/real.png").status_code == 404
    assert client.get(f"/api/image/Dsr/{quote(CID)}/bogus.png").status_code == 404


def test_unknown_version_404(client):
    assert client.get(f"/api/image/Versao-inexistente/{quote(CID)}/real.png").status_code == 404


def test_image_is_cacheable(client):
    r = client.get(f"/api/image/Dsr/{quote(CID)}/diff.png")
    assert r.status_code == 200 and r.headers["cache-control"] == "max-age=3600"


def test_reference_window_is_shared_between_versions():
    from types import SimpleNamespace
    from workbench.api import images
    rng = np.random.default_rng(0)
    original = rng.normal(size=(32, 32))
    mask = np.ones((32, 32), dtype=bool)
    a = SimpleNamespace(original=original, synthetic=original + 5.0, lung_mask=mask)
    b = SimpleNamespace(original=original, synthetic=original * 3.0, lung_mask=mask)
    assert images.window(a, reference=True) == images.window(b, reference=True)
    assert images.window(a) != images.window(b)  # sem a opção, a janela depende da sintética


def test_reference_window_query(client):
    r = client.get(f"/api/image/Dsr/{quote(CID)}/synthetic.png", params={"window": "reference"})
    assert r.status_code == 200
    assert client.get(f"/api/image/Dsr/{quote(CID)}/synthetic.png", params={"window": "bogus"}).status_code == 422


def test_cache_buster_param_is_ignored(client):
    r = client.get(f"/api/image/Dsr/{quote(CID)}/real.png", params={"v": "1700000000"})
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
