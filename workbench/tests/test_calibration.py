"""Calibração (`calibration.calibration_json`, lida por `/api/schema`): réguas do histórico e constantes do juiz."""
import json
import math

import pytest

from frameworks.noise_evaluator import integration
from frameworks.texture_evaluator import placar, regional, visual
from workbench.api import calibration, reasons
from workbench.tests.conftest import DATA_OK, HISTORY_DIR

pytestmark = pytest.mark.skipif(not DATA_OK, reason="outputs/placar/historico.json ou dados/Dsr ausente")


def body_for(history_dir):
    return calibration.calibration_json(placar.load_history(history_dir))


def test_calibration_matches_history_and_framework_constants(tmp_history):
    history = placar.load_history(tmp_history)
    body = body_for(tmp_history)
    mean_iqr = history["calibration"]["mean_iqr"]
    assert body["reference"] == history["reference"]
    assert body["n_cases"] == len(history["originals"])
    assert body["mean_iqr"] == pytest.approx(mean_iqr)
    assert body["delta_mu"] == {"review": pytest.approx(mean_iqr), "reject": pytest.approx(2 * mean_iqr)}
    assert body["sat31_limit"] == reasons.SATURATION_LIMIT
    assert body["z_limits"] == reasons.Z_LIMITS
    nex = history["calibration"]["nex_reference"]
    assert body["nex"] == {"iqr": pytest.approx(nex["iqr"]), "repeatability_iqr": pytest.approx(nex["repeatability_iqr"])}
    metrics = history["calibration"]["nps_reference"]["metrics"]
    assert set(body["nps"]) == set(metrics)
    for key, metric in metrics.items():
        assert body["nps"][key] == {"repeatability_iqr": pytest.approx(metric["repeatability_iqr"])}
    assert body["air"] == {"limits": list(integration.AIR_LIMITS), "sigmas": integration.AIR_SIGMAS}
    assert body["pair_min_correlation"] == regional.PAIR_MIN_CORRELATION
    assert body["technique_figures"] == list(visual.TECHNIQUE_FIGURES)
    assert body["map_layers"] == list(visual.MAP_LAYERS)


def test_stale_history_returns_null_for_missing_reference(stale_dir):
    body = body_for(stale_dir)
    assert body["nex"] == {"iqr": None, "repeatability_iqr": None}
    assert body["mean_iqr"] is not None
    assert body["air"] == {"limits": list(integration.AIR_LIMITS), "sigmas": integration.AIR_SIGMAS}


def test_non_finite_values_become_null(tmp_history):
    path = tmp_history / placar.HISTORY_FILE
    history = json.loads(path.read_text(encoding="utf-8"))
    history["calibration"]["nex_reference"]["repeatability_iqr"] = float("nan")
    path.write_text(json.dumps(history, allow_nan=True), encoding="utf-8")
    body = body_for(tmp_history)
    assert body["nex"]["repeatability_iqr"] is None
    assert not math.isnan(body["mean_iqr"])
