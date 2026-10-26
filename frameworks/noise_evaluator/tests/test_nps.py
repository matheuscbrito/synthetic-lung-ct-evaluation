from __future__ import annotations

import unittest

import numpy as np
from scipy.ndimage import gaussian_filter

from frameworks.noise_evaluator.core import NPSConfig, ROI, compare_spectra, estimate_local_nps, select_rois
from frameworks.noise_evaluator.report import case_assessment
from frameworks.noise_evaluator.integration import certain_status, measure_air, noise_verdict, status_from_z


class NPSTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = NPSConfig(roi_size=32, stride=32, min_tissue=1.0, min_rois=4, max_rois=16)
        self.rois = [ROI(x=x, y=y, size=32, structure_score=0.0, tissue_fraction=1.0) for y in range(0, 128, 32) for x in range(0, 128, 32)]

    def test_white_noise_magnitude_tracks_standard_deviation(self) -> None:
        rng = np.random.default_rng(7)
        image = rng.normal(0, 2.0, size=(128, 128))
        result = estimate_local_nps(image, self.rois, self.config)
        self.assertAlmostEqual(result.features["noise_std"], 2.0, delta=0.35)
        self.assertAlmostEqual(sum(result.features[key] for key in ("low_band_fraction", "mid_band_fraction", "high_band_fraction")), 1.0, places=6)

    def test_smoothing_moves_power_to_lower_frequencies(self) -> None:
        rng = np.random.default_rng(8)
        white = rng.normal(size=(128, 128))
        smooth = gaussian_filter(white, sigma=2.0)
        white_result = estimate_local_nps(white, self.rois, self.config)
        smooth_result = estimate_local_nps(smooth, self.rois, self.config)
        self.assertLess(smooth_result.features["mean_frequency"], white_result.features["mean_frequency"])
        self.assertGreater(smooth_result.features["low_band_fraction"], white_result.features["low_band_fraction"])

    def test_identical_spectra_compare_as_equal(self) -> None:
        rng = np.random.default_rng(9)
        image = rng.normal(size=(128, 128))
        result = estimate_local_nps(image, self.rois, self.config)
        comparison = compare_spectra(result, result)
        self.assertAlmostEqual(comparison["noise_std_ratio"], 1.0)
        self.assertAlmostEqual(comparison["nps_shape_js_distance"], 0.0)
        self.assertAlmostEqual(comparison["mean_frequency_delta"], 0.0)

    def test_roi_selection_stays_inside_mask(self) -> None:
        image = np.zeros((128, 128), dtype=float)
        image[:, 64:] = 5.0
        mask = np.zeros_like(image, dtype=bool)
        mask[16:112, 16:112] = True
        rois = select_rois(image, mask, self.config)
        self.assertGreaterEqual(len(rois), self.config.min_rois)
        self.assertTrue(all(mask[roi.slices].all() for roi in rois))

    def test_roi_selection_never_overlaps_beyond_limit(self) -> None:
        image = np.zeros((128, 128), dtype=float)
        mask = np.zeros_like(image, dtype=bool)
        mask[16:56, 16:56] = True
        config = NPSConfig(roi_size=32, stride=8, min_tissue=1.0, min_rois=4, max_rois=16)
        with self.assertRaises(ValueError):
            select_rois(image, mask, config)

    def test_air_spots_detect_invented_blotches(self) -> None:
        rng = np.random.default_rng(10)
        original = np.zeros((256, 256), dtype=float)
        original[40:216, 40:216] = 1.0 + rng.normal(0, 0.03, size=(176, 176))
        lung = np.zeros_like(original, dtype=bool)
        lung[96:160, 96:160] = True
        synthetic = original.copy()
        synthetic[0:40, 0:40] += 0.5
        clean = measure_air(original, original, lung, 0.03)
        self.assertTrue(clean["nps_air_available"])
        self.assertEqual(clean["nps_air_real"], 0.0)
        self.assertEqual(clean["nps_air_status"], "aprovada")
        damaged = measure_air(original, synthetic, lung, 0.03)
        self.assertGreater(damaged["nps_air_synthetic"], 2.0)
        self.assertEqual(damaged["nps_air_status"], "reprovada")

    def test_certain_status_needs_interval_clear_of_zero(self) -> None:
        self.assertEqual(certain_status(1.5, -0.2, 3.0), "aprovada")
        self.assertEqual(certain_status(1.5, 0.3, 2.8), "revisão")
        self.assertEqual(certain_status(2.5, 1.0, 4.0), "reprovada")

    def test_lung_unavailable_still_uses_air(self) -> None:
        row = {"nps_available": False, "nps_air_available": True, "nps_air_status": "reprovada"}
        self.assertEqual(noise_verdict(row), "reprovada")

    def test_plain_language_assessment_uses_all_four_checks(self) -> None:
        close = {
            "noise_std_ratio": 1.02,
            "mean_frequency_delta_nyquist": 0.01,
            "nps_shape_js_distance": 0.04,
            "nps_log_curve_correlation": 0.99,
        }
        attention = {**close, "noise_std_ratio": 0.80}
        far = {**attention, "nps_shape_js_distance": 0.25}
        self.assertEqual(case_assessment(close)["verdict"], "close")
        self.assertEqual(case_assessment(attention)["verdict"], "attention")
        self.assertEqual(case_assessment(far)["verdict"], "far")

    def test_iqr_thresholds_match_framework_rule(self) -> None:
        self.assertEqual(status_from_z(1.0), "aprovada")
        self.assertEqual(status_from_z(-1.01), "revisão")
        self.assertEqual(status_from_z(2.0), "revisão")
        self.assertEqual(status_from_z(2.01), "reprovada")

    def test_worst_nps_metric_decides(self) -> None:
        row = {"nps_available": True, "nps_air_available": True, "nps_air_status": "aprovada"}
        statuses = ("aprovada", "revisão", "aprovada", "reprovada")
        for metric, status in zip(("quantity", "grain", "low_band", "high_band"), statuses):
            row[f"nps_{metric}_status"] = status
        self.assertEqual(noise_verdict(row), "reprovada")


    def test_unmeasured_lung_is_never_approved(self) -> None:
        row = {"nps_available": False, "nps_air_available": True, "nps_air_status": "aprovada"}
        self.assertEqual(noise_verdict(row), "revisão")

if __name__ == "__main__":
    unittest.main()
