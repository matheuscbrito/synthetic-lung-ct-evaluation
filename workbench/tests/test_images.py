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
