"""Motivos estruturados e limites compartilhados: os limites de |z| batem com `decision.metric_status`."""
from frameworks.texture_evaluator import decision
from workbench.api import reasons


def _metric(key, technique, group, status, z, value=1.0):
    return {"key": key, "technique": technique, "group": group, "status": status, "value": value,
            "z": z, "z_low": None, "z_high": None}


def test_z_limits_match_framework_status():
    review, reject = reasons.Z_LIMITS["review"], reasons.Z_LIMITS["reject"]
    assert decision.metric_status(review) == "aprovada"
    assert decision.metric_status(review + 1e-9) == "revisão"
    assert decision.metric_status(reject) == "revisão"
    assert decision.metric_status(reject + 1e-9) == "reprovada"


def test_reason_limit_value_comes_from_shared_constants():
    metrics = [
        _metric("delta_mu", "GLCM", "brightness", "rejected", 2.5),
        _metric("glcm_contrast", "GLCM", "texture", "review", 1.4),
        _metric("sat31", "GLCM", "brightness", "rejected", None, value=20.0),
        _metric("nps_air", "Air", "noise", "rejected", None, value=3.0),
    ]
    out = reasons.why(metrics)
    assert out["brightness"][0]["limit_value"] == reasons.Z_LIMITS["reject"]
    assert out["brightness"][1]["limit_value"] == reasons.SATURATION_LIMIT
    assert out["texture"][0]["limit_value"] == reasons.Z_LIMITS["review"]
    assert out["noise"][0]["limit_value"] is None
