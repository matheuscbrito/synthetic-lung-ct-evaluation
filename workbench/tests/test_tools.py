"""Dados das ferramentas do workbench: espectro, matrizes GLCM, janelas NEx e sub-bandas wavelet."""
import numpy as np
import pytest

from frameworks.texture_evaluator.glcm.src import extract_glcm
from frameworks.texture_evaluator.run_mvp import context_from_dict
from workbench.api import data, images
from workbench.api.tools import glcm_matrix, nex_windows, radial_spectrum, reference_band, wavelet_bands
from workbench.tests.conftest import DATA_OK

pytestmark = pytest.mark.skipif(not DATA_OK, reason="outputs/placar/historico.json ou dados/Dsr ausente")

CID = "1.000000-P4P100S300I00003 Gated 0.0A-29193-1-058"


@pytest.fixture
def client_case():
    wb = data.load(data.HISTORY_DIR)
    case = images.case(wb, "Dsr", wb.rows("Dsr")[0]["case_id"])
    return wb, case


def test_spectrum_white_noise_is_flat():
    rng = np.random.default_rng(0); img = rng.normal(size=(128, 128)); mask = np.ones_like(img, bool)
    f, p = radial_spectrum(img, mask)
    assert len(f) == 64 and 0 < f[0] < f[-1] <= 0.5
    assert np.std(p[5:]) / np.mean(p[5:]) < 0.25


def test_spectrum_period_two_stripes_peak_at_nyquist():
    img = np.indices((128, 128))[1] % 2 * 1.0; f, p = radial_spectrum(img, np.ones_like(img, bool))
    assert int(np.argmax(p)) >= 60


def test_glcm_matrix_matches_framework(client_case):
    wb, case = client_case; scale = context_from_dict(wb.history["calibration"]).scale
    m = np.array(glcm_matrix(case.original, case.lung_mask, scale))
    gray = np.arange(32); contrast = (m * (gray[:, None] - gray[None, :]) ** 2).sum()
    assert m.shape == (32, 32) and np.isclose(m.sum(), 1)
    assert np.isclose(contrast, extract_glcm(case.original, case.lung_mask, scale)["glcm_contrast"])


def test_nex_windows_are_inside_mask_and_finite():
    img = np.random.default_rng(1).normal(size=(96, 96)); mask = np.zeros_like(img, bool); mask[10:80, 10:80] = True
    windows = nex_windows(img, mask)
    assert windows and all(mask[w["row"]:w["row"] + 32, w["col"]:w["col"] + 32].all() for w in windows)
    assert all(np.isfinite(w["value"]) for w in windows)


def test_wavelet_bands_order_and_mask_pooling():
    img = np.random.default_rng(2).normal(size=(64, 64)); mask = np.ones_like(img, bool)
    bands = wavelet_bands(img, mask)
    assert [(b["level"], b["band"]) for b in bands] == [(1, "LH"), (1, "HL"), (1, "HH"), (2, "LH"), (2, "HL"), (2, "HH")]
    assert all(b["energy"] > 0 for b in bands)


def test_reference_band_is_ordered(client_case):
    wb, _ = client_case
    band = reference_band(wb)
    assert len(band["p5"]) == len(band["p95"]) == 64 and all(a <= b for a, b in zip(band["p5"], band["p95"]))
