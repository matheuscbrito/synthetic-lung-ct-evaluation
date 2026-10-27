from __future__ import annotations

import unittest

import numpy as np
from scipy.ndimage import gaussian_filter, uniform_filter1d

from frameworks.noise_signature.decision import bootstrap, certain_status, combine, final_status
from frameworks.noise_signature.fingerprint import acf_shape, grid_peak, residual_spectra, roi_acf
from frameworks.noise_signature.noise_level import roi_levels, t3_metrics
from frameworks.noise_signature.nps import RoiSet, patches, roi_features, select_rois, t1_metrics
from frameworks.noise_signature.regions import lung_region
from frameworks.noise_signature.residual import residual, wiener_denoise

SIZE = 256
FULL = np.ones((SIZE, SIZE), bool)


def rois(size: int = 32) -> RoiSet:
    return select_rois(FULL, FULL, size)


def t1(image: np.ndarray) -> dict:
    return t1_metrics(roi_features(image, rois()), 32)


def t3(image: np.ndarray) -> dict:
    return t3_metrics({"roi": roi_levels(image, FULL, rois())})


def acf(image: np.ndarray) -> tuple[float, float]:
    return acf_shape(roi_acf(patches(image, rois())).mean(axis=0))


class NPSTest(unittest.TestCase):
    def test_white_noise_sigma_within_five_percent(self) -> None:
        image = np.random.default_rng(1).normal(0, 2.0, (SIZE, SIZE))
        self.assertAlmostEqual(t1(image)["sigma"], 2.0, delta=0.1)

    def test_smoothed_noise_is_coarser(self) -> None:
        white = np.random.default_rng(2).normal(size=(SIZE, SIZE))
        smooth = gaussian_filter(white, 1.0)
        self.assertLess(t1(smooth)["f_avg"], t1(white)["f_avg"])
        self.assertGreater(t3(smooth)["corr_index"], t3(white)["corr_index"] + 0.3)
        self.assertAlmostEqual(t3(white)["corr_index"], 1.0, delta=0.1)
        self.assertAlmostEqual(t3(white)["coherence"], 0.5, delta=0.05)
        self.assertGreater(acf(smooth)[0], acf(white)[0] + 0.5)

    def test_anisotropic_noise(self) -> None:
        white = np.random.default_rng(3).normal(size=(SIZE, SIZE))
        smeared = uniform_filter1d(white, 3, axis=1)   # suaviza só ao longo de x
        self.assertAlmostEqual(t1(white)["anisotropy"], 1.0, delta=0.1)
        self.assertLess(t1(smeared)["anisotropy"], 0.7)
        self.assertAlmostEqual(t3(white)["hv_ratio"], 1.0, delta=0.1)
        self.assertLess(t3(smeared)["hv_ratio"], 0.8)

    def test_anatomy_only_image_leaks_and_has_no_noise(self) -> None:
        yy, xx = np.mgrid[:SIZE, :SIZE]
        image = 0.002 * xx + 0.001 * yy
        for cy, cx in ((60, 60), (60, 190), (190, 120)):
            image = image + 1.0 * (np.hypot(yy - cy, xx - cx) < 20)
        image = gaussian_filter(image, 1.0)
        features = roi_features(image, rois())
        self.assertGreater(features["leak"].mean(), 0.1)
        flat = RoiSet(np.array([100, 130]), np.array([200, 20]), 32)   # regiões só com o gradiente
        self.assertLess(t1_metrics(roi_features(image, flat), 32)["sigma"], 1e-4)
        # nas ROIs com vazamento o NPS tem o máximo no 1º bin útil
        leaky = features["profile"][features["leak"]]
        self.assertTrue(np.all(leaky[:, 2] >= leaky[:, 3:].max(axis=1)))


class FingerprintTest(unittest.TestCase):
    def test_grid_peak_detects_period_eight(self) -> None:
        rng = np.random.default_rng(4)
        white = rng.normal(size=(SIZE, SIZE))
        tile = rng.normal(size=(8, 8))
        patterned = white + 0.6 * np.tile(tile, (SIZE // 8, SIZE // 8))
        spec = lambda image: residual_spectra(patches(image, rois()))
        self.assertLess(abs(grid_peak(spec(white))), 0.5)
        self.assertGreater(grid_peak(spec(patterned)), 1.5)

    def test_wiener_uses_fixed_sigma0(self) -> None:
        image = np.random.default_rng(5).normal(size=(128, 128))
        np.testing.assert_allclose(wiener_denoise(image, 0.0), image, atol=1e-8)
        energies = [np.std(residual(image, "wiener", s)) for s in (0.25, 0.5, 1.0)]
        self.assertTrue(energies[0] < energies[1] < energies[2])
        # σ0 é fixo: o mesmo filtro aplicado a um ruído 2× maior não "se adapta" (resíduo relativo menor)
        louder = 2 * image
        self.assertLess(np.std(residual(louder, "wiener", 0.5)) / 2, np.std(residual(image, "wiener", 0.5)))


class RegionTest(unittest.TestCase):
    def test_vessel_disc_is_excluded(self) -> None:
        rng = np.random.default_rng(6)
        yy, xx = np.mgrid[:SIZE, :SIZE]
        disc = np.hypot(yy - 128, xx - 128) < 10
        image = rng.normal(0, 0.05, (SIZE, SIZE)) + 1.0 * disc
        lung = np.zeros((SIZE, SIZE), bool)
        lung[20:-20, 20:-20] = True
        region = lung_region(image, lung)
        self.assertFalse(region.strict[disc].any())
        self.assertGreater(region.strict.mean(), 0.3)


class DecisionTest(unittest.TestCase):
    def test_thresholds_and_interval(self) -> None:
        self.assertEqual(certain_status(0.8, 0.2, 1.4), "aprovada")
        self.assertEqual(certain_status(1.5, 1.1, 1.9), "revisão")
        self.assertEqual(certain_status(-2.5, -3.0, -2.1), "reprovada")
        self.assertEqual(certain_status(2.5, -0.1, 3.0), "aprovada")       # IC cruza zero: não pesa
        self.assertEqual(certain_status(float("nan"), 0, 0), "inconclusivo")

    def test_worst_wins_and_inconclusive_never_approves(self) -> None:
        self.assertEqual(combine(["aprovada", "reprovada", "revisão"]), "reprovada")
        self.assertEqual(combine(["inconclusivo", "aprovada"]), "aprovada")
        self.assertEqual(combine(["inconclusivo"]), "inconclusivo")
        self.assertEqual(final_status({"t1": "inconclusivo", "t2": "aprovada", "t3": "aprovada", "t4": "aprovada"}), "revisão")
        self.assertEqual(final_status({"t1": "inconclusivo", "t2": "reprovada", "t3": "aprovada", "t4": "aprovada"}), "reprovada")
        self.assertEqual(final_status({key: "inconclusivo" for key in ("t1", "t2")}), "revisão")
        self.assertEqual(final_status({"t1": "aprovada", "t2": "aprovada"}), "aprovada")

    def test_paired_bootstrap_resamples_same_units(self) -> None:
        values = {"roi": {"x": np.arange(20, dtype=float)}}
        zfun = lambda a, b: {"d": float(b["roi"]["x"].mean() - a["roi"]["x"].mean())}
        low, high = bootstrap(zfun, values, values, paired=True)["d"]
        self.assertEqual((low, high), (0.0, 0.0))
        low, high = bootstrap(zfun, values, values, paired=False)["d"]
        self.assertLess(low, 0.0)
        self.assertGreater(high, 0.0)


if __name__ == "__main__":
    unittest.main()
