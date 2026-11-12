from __future__ import annotations

import unittest
from dataclasses import replace

import numpy as np
from scipy.ndimage import gaussian_filter

from frameworks.noise_evaluator.core import NPSConfig, ROI, candidate_rois, compare_spectra, estimate_local_nps, select_rois, spectrum_from_roi_spectra
from frameworks.noise_evaluator.report import case_assessment
from frameworks.noise_evaluator.integration import NPS_CONFIG, certain_status, measure_air, measure_nps, noise_verdict, status_from_z
from frameworks.noise_evaluator.regions import AIR_LEVEL, HU_PER_UNIT, REGION_KEYS, segment_regions
from frameworks.noise_evaluator.roi_study import aggregate_cases_by_patient


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

    def test_spectra_can_be_pooled_across_slices(self) -> None:
        rng = np.random.default_rng(91)
        first = estimate_local_nps(rng.normal(size=(128, 128)), self.rois[:8], self.config)
        second = estimate_local_nps(rng.normal(size=(128, 128)), self.rois[8:], self.config)
        pooled = spectrum_from_roi_spectra(np.concatenate((first.roi_spectra, second.roi_spectra)), self.config)
        self.assertEqual(pooled.roi_spectra.shape[0], 16)
        self.assertGreater(pooled.features["noise_std"], 0)

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

    def test_structure_threshold_rejects_heterogeneous_candidates(self) -> None:
        yy, xx = np.mgrid[:128, :128]
        image = np.zeros((128, 128), dtype=float)
        image[:, 64:] = 0.02 * xx[:, 64:] + np.sin(yy[:, 64:] / 3)
        mask = np.ones_like(image, dtype=bool)
        unfiltered = candidate_rois(image, mask, self.config)
        threshold = float(np.median([roi.structure_score for roi in unfiltered]))
        filtered = candidate_rois(image, mask, replace(self.config, max_structure_score=threshold))
        self.assertGreater(len(unfiltered), len(filtered))
        self.assertTrue(all(roi.structure_score <= threshold for roi in filtered))

    def test_case_aggregation_uses_patient_median_without_pooling_spectra(self) -> None:
        base = {
            "config": "roi24_permissive", "patient_id": "100", "method": "Baseline",
            "roi_size": 24, "profile": "permissive", "max_structure_score": 0.01,
            "roi_count": 2, "real_noise_std": 1.0, "synthetic_noise_std": 1.0,
            "noise_std_ratio": 1.0, "noise_std_delta_pct": 0.0,
            "peak_frequency_delta": 0.0, "mean_frequency_delta": 0.0,
            "median_frequency_delta": 0.0, "mean_frequency_delta_nyquist": 0.0,
            "low_band_delta": 0.0, "mid_band_delta": 0.0, "high_band_delta": 0.0,
            "anisotropy_delta": 0.0, "periodic_peak_ratio": 1.0, "nps_shape_rmse": 0.0,
            "nps_shape_js_distance": 0.1, "nps_log_curve_correlation": 0.9,
            "composite_distance": 0.0,
        }
        rows = [
            {**base, "case_id": "case-a"},
            {**base, "case_id": "case-b", "noise_std_ratio": 3.0},
            {**base, "case_id": "case-c", "patient_id": "105", "roi_count": 3},
        ]
        aggregated = aggregate_cases_by_patient(rows)
        self.assertEqual(len(aggregated), 1)
        self.assertEqual(aggregated[0]["case_count"], 2)
        self.assertEqual(aggregated[0]["roi_count"], 4)
        self.assertEqual(aggregated[0]["noise_std_ratio"], 2.0)

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

    def test_unavailable_nps_ignores_rejected_air(self) -> None:
        row = {"nps_available": False, "nps_air_available": True, "nps_air_status": "reprovada"}
        self.assertEqual(noise_verdict(row), "inconclusivo")

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
        statuses = ("aprovada", "revisão", "reprovada")
        for metric, status in zip(("quantity", "grain", "high_band"), statuses):
            row[f"nps_{metric}_status"] = status
        self.assertEqual(noise_verdict(row), "reprovada")


    def test_unmeasured_lung_is_never_approved(self) -> None:
        row = {"nps_available": False, "nps_air_available": True, "nps_air_status": "aprovada"}
        self.assertEqual(noise_verdict(row), "inconclusivo")


def _from_hu(hu):
    return (np.asarray(hu, dtype=float) + 1000) / HU_PER_UNIT + AIR_LEVEL


def _phantom(seed: int = 11):
    """Tórax sintético: corpo de músculo (+40 HU), dois pulmões (−850 HU), um osso (+700 HU) e ruído de 20 HU."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:256, :256]
    hu = np.full((256, 256), -1000.0)
    body = ((yy - 128) / 100) ** 2 + ((xx - 128) / 120) ** 2 <= 1
    hu[body] = 40.0
    lung = np.zeros_like(body)
    for cx in (85, 171):
        lung |= ((yy - 120) / 45) ** 2 + ((xx - cx) / 28) ** 2 <= 1
    hu[lung] = -850.0
    bone = (yy - 205) ** 2 + (xx - 128) ** 2 <= 10 ** 2
    hu[bone] = 700.0
    hu[body] += rng.normal(0, 20, size=int(body.sum()))
    return _from_hu(hu), lung, bone


class RegionsTest(unittest.TestCase):
    def test_every_pixel_has_exactly_one_region(self) -> None:
        image, lung, _ = _phantom()
        regions = segment_regions(image, lung)
        self.assertEqual(tuple(regions), REGION_KEYS)
        self.assertTrue((np.sum([regions[key] for key in REGION_KEYS], axis=0) == 1).all())

    def test_soft_tissue_keeps_away_from_lung_bone_and_skin(self) -> None:
        image, lung, bone = _phantom()
        regions = segment_regions(image, lung)
        soft = regions["soft"]
        self.assertGreater(soft.sum(), 5000)
        self.assertFalse((soft & lung).any())
        self.assertFalse((soft & bone).any())
        self.assertTrue(regions["lung"][lung].all())
        self.assertTrue(regions["bone"][bone].all())
        self.assertTrue(regions["air"][0, 0])

    def test_fat_muscle_border_is_an_edge(self) -> None:
        image, lung, _ = _phantom()
        hu = (image - AIR_LEVEL) * HU_PER_UNIT - 1000
        hu[175:196, 160:204] = -100.0  # bloco de gordura abaixo do pulmão direito da imagem
        regions = segment_regions(_from_hu(hu), lung)
        self.assertTrue(regions["edges"][185, 160])
        self.assertTrue(regions["soft"][185, 182])

    def test_nps_squares_sit_only_in_smooth_soft_tissue(self) -> None:
        image, lung, _ = _phantom()
        rois, result = measure_nps(image, lung)
        soft = segment_regions(image, lung)["soft"]
        self.assertGreaterEqual(len(rois), NPS_CONFIG.min_rois)
        self.assertTrue(all(roi.size == 16 for roi in rois))
        self.assertTrue(all(soft[roi.slices].mean() >= NPS_CONFIG.min_tissue for roi in rois))
        self.assertGreater(result.features["noise_std"], 0)


if __name__ == "__main__":
    unittest.main()
