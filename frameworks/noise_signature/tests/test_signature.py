from __future__ import annotations

import unittest

import numpy as np
from scipy.ndimage import gaussian_filter, uniform_filter1d

from types import SimpleNamespace

from frameworks.noise_signature.calibrate import neighbour_pairs, rulers
from frameworks.noise_signature.decision import (DECISION_METRICS, bootstrap, certain_status, combine, final_status, score,
                                                 score_metric)
from frameworks.noise_signature.measure import all_metric_keys
from frameworks.noise_signature.fingerprint import acf_shape, grid_peak, residual_spectra, roi_acf
from frameworks.noise_signature.noise_level import roi_levels, t3_metrics
from frameworks.noise_signature.nps import MIN_ROIS, RoiSet, leak_keep, patches, roi_features, select_rois, t1_metrics
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
        self.assertEqual(final_status({"quantidade": "revisão", "grão": "reprovada", "espectro": "aprovada"}), "reprovada")

    def test_paired_bootstrap_resamples_same_units(self) -> None:
        values = {"roi": {"x": np.arange(20, dtype=float)}}
        zfun = lambda a, b: {"d": float(b["roi"]["x"].mean() - a["roi"]["x"].mean())}
        low, high = bootstrap(zfun, values, values, paired=True)["d"]
        self.assertEqual((low, high), (0.0, 0.0))
        low, high = bootstrap(zfun, values, values, paired=False)["d"]
        self.assertLess(low, 0.0)
        self.assertGreater(high, 0.0)



def _raw(d: dict | None = None) -> dict:
    """Leitura bruta de par com todas as diferenças zero (IC [0, 0]), exceto as dadas."""
    raw = {}
    for key in all_metric_keys():
        value = (d or {}).get(key, 0.0)
        raw.update({f"{key}_d": value, f"{key}_d_low": value * 0.9, f"{key}_d_high": value * 1.1})
    raw["t4_map_rho"] = 0.9
    return raw


def _calib(scale: float = 1.0, reference: float = 0.5) -> dict:
    return {"k": 1.0, "metrics": {key: {"scale": scale, "reference": reference} for key in all_metric_keys()}}


class V2DecisionTest(unittest.TestCase):
    def test_one_sided_shape_dist(self) -> None:
        entry = {"scale": 0.2, "reference": 0.3}
        self.assertEqual(score_metric("t1_soft_shape_dist", 0.0, 0.0, 0.0, entry, 1.0)[3], "aprovada")   # cópia: distância 0
        self.assertEqual(score_metric("t1_soft_shape_dist", 0.1, 0.05, 0.2, entry, 1.0)[0], 0.0)        # mais parecida que vizinhos
        z, low, high, status = score_metric("t1_soft_shape_dist", 0.9, 0.8, 1.0, entry, 1.0)
        self.assertAlmostEqual(z, 3.0)
        self.assertEqual(status, "reprovada")
        # comum (dois lados) e k: z = d / (k · escala)
        self.assertAlmostEqual(score_metric("t2_wiener_lsd", -0.6, -0.7, -0.5, {"scale": 0.2}, 2.0)[0], -1.5)

    def test_scale_uses_real_pair_spread(self) -> None:
        readings = [{} for _ in range(10)]
        splits = [{"t2_wiener_lsd": 0.01 * (-1) ** i, "t3_soft_immerkaer": 0.5 * (-1) ** i} for i in range(10)]
        nn = []
        for i in range(10):
            raw = {f"{key}_d": float("nan") for key in all_metric_keys()}
            raw["t2_wiener_lsd_d"] = (0.1 + 0.02 * i) * (-1) ** i
            raw["t3_soft_immerkaer_d"] = 0.01 * (-1) ** i
            nn.append(raw)
        metrics = rulers(readings, splits, nn)
        expected = 2 * np.median([0.1 + 0.02 * i for i in range(10)])
        self.assertAlmostEqual(metrics["t2_wiener_lsd"]["scale"], expected)          # vizinhos dominam
        self.assertEqual(metrics["t2_wiener_lsd"]["scale_source"], "vizinhos")
        self.assertAlmostEqual(metrics["t3_soft_immerkaer"]["scale"], 2 * 1.0)      # 2 × IQR par × ímpar domina
        self.assertEqual(metrics["t3_soft_immerkaer"]["scale_source"], "repetibilidade")

    def test_diagnostic_metrics_never_change_verdict(self) -> None:
        calib = _calib()
        base = score(_raw(), calib, same_anatomy=True)
        self.assertEqual(base["noise_signature_status"], "aprovada")
        diagnostic = [k for k in all_metric_keys() if k not in DECISION_METRICS]
        noisy = score(_raw({k: 50.0 for k in diagnostic}), calib, same_anatomy=True)
        self.assertEqual(noisy["noise_signature_status"], "aprovada")
        self.assertEqual(noisy["t3_lung_mad1_status"], "reprovada")                 # reportada, mas não decide
        self.assertIn("ruído fino", noisy["noise_signature_diagnostics"])
        decided = score(_raw({"t2_wiener_lsd": 5.0}), calib, same_anatomy=True)
        self.assertEqual(decided["noise_signature_status"], "reprovada")
        self.assertEqual(decided["eixo_espectro_status"], "reprovada")
        # σ_ratio só decide com a mesma anatomia
        ratio = _raw({"t1_soft_sigma_ratio": 5.0})
        self.assertEqual(score(ratio, calib, same_anatomy=True)["noise_signature_status"], "reprovada")
        self.assertEqual(score(ratio, calib, same_anatomy=False)["noise_signature_status"], "aprovada")

    def test_inconclusive_axis_never_approves(self) -> None:
        raw = _raw()
        for key in ("t3_soft_immerkaer", "t1_soft_sigma_ratio"):
            raw[f"{key}_d"] = float("nan")
        out = score(raw, _calib(), same_anatomy=True)
        self.assertEqual(out["eixo_quantidade_status"], "inconclusivo")
        self.assertEqual(out["noise_signature_status"], "revisão")

    def test_leak_fallback_keeps_least_leaking_half(self) -> None:
        n = 20
        profiles = np.ones((n, 18))
        profiles[:, 2] = np.linspace(1.5, 3.0, n)          # todas vazam; as primeiras vazam menos
        keep, fallback = leak_keep({"profile": profiles, "leak": np.ones(n, bool)})
        self.assertTrue(fallback)
        self.assertEqual(keep.sum(), max(MIN_ROIS, n // 2))
        self.assertTrue(keep[:10].all())
        keep, fallback = leak_keep({"profile": profiles, "leak": np.zeros(n, bool)})
        self.assertFalse(fallback)
        self.assertTrue(keep.all())

    def test_neighbours_prefer_same_series_then_index(self) -> None:
        ids = ["x-P1P1S300I00002 a-1-010", "x-P1P1S300I00002 a-1-020", "x-P1P1S301I00002 a-1-011", "x-P1P2S300I00001 a-1-010"]
        self.assertEqual(neighbour_pairs(ids), [(0, 1), (1, 0), (2, 0)])
        self.assertEqual(neighbour_pairs(ids, same_series_first=False)[0], (0, 2))


def _phantom(seed: int, size: int = 320) -> tuple[np.ndarray, np.ndarray]:
    """Corpo de tecido mole com dois pulmões e ruído branco levemente correlacionado."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:size, :size]
    c = (size - 1) / 2
    body = ((xx - c) / 155) ** 2 + ((yy - c) / 125) ** 2 <= 1
    lungs = (((xx - c + 60) / 38) ** 2 + ((yy - c) / 60) ** 2 <= 1) | (((xx - c - 60) / 38) ** 2 + ((yy - c) / 60) ** 2 <= 1)
    image = np.full((size, size), -0.6)
    image[body] = 0.2 + 0.02 * np.sin(yy[body] / 40.0)     # tecido mole com leve variação lenta
    image[lungs] = -0.3
    image = gaussian_filter(image, 1.0) + body * gaussian_filter(rng.normal(0, 0.03, (size, size)), 0.6)
    image[~body] = -0.6
    return image, lungs & (gaussian_filter(lungs.astype(float), 2) > 0.99)


class CopyOfRealTest(unittest.TestCase):
    def test_copy_of_real_is_approved(self) -> None:
        from frameworks.noise_signature.calibrate import calibrate
        from frameworks.noise_signature.evaluate import evaluate_pair
        cases = []
        for i in range(6):
            image, lung = _phantom(i)
            cases.append(SimpleNamespace(original=image, lung_mask=lung, paths=SimpleNamespace(case_id=f"x-P1P1S300I00002 a-1-{i:03d}")))
        calib = calibrate(cases, lopo=False)
        image, lung = cases[0].original, cases[0].lung_mask
        row, _ = evaluate_pair("copia", image, image.copy(), lung, calib, same_anatomy=True)
        self.assertEqual(row["noise_signature_status"], "aprovada", row["noise_signature_reasons"])
        # e o dobro do ruído não passa
        louder = image + (image > -0.59) * gaussian_filter(np.random.default_rng(99).normal(0, 0.05, image.shape), 0.6)
        row, _ = evaluate_pair("ruidosa", image, louder, lung, calib, same_anatomy=True)
        self.assertEqual(row["noise_signature_status"], "reprovada", row["noise_signature_reasons"])


if __name__ == "__main__":
    unittest.main()
