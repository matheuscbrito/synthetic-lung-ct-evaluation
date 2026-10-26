"""Paridade do payload por corte: ruído (NPS e ar), NEx pareado, IC 95% e motivos estruturados.

Os vereditos esperados vêm das funções do framework sobre as linhas reais do CSV, nunca de números fixos.
"""
import math
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from frameworks.noise_evaluator.integration import AIR_LABEL, AIR_LIMITS, NPS_METRICS, noise_statuses, noise_verdict
from frameworks.texture_evaluator import decision
from frameworks.texture_evaluator.placar import load_rows
from workbench.api import data as wb_data
from workbench.api import reasons
from workbench.api.app import create_app
from workbench.api.data import slice_json
from workbench.tests.conftest import DATA_OK, HISTORY_DIR, framework_counts, nonzero

pytestmark = pytest.mark.skipif(not DATA_OK, reason="outputs/placar/historico.json ou dados/Dsr ausente")

NPS_KEYS = ("quantity", "grain", "low_band", "high_band")
NOISE_TECHNIQUES = {"quantity", "grain", "low_band", "high_band", "air"}
METRIC_KEYS = {"z_low", "z_high", "pct_of_original", "certain"}


@pytest.fixture(scope="module")
def dsr_rows():
    return load_rows(HISTORY_DIR, "Dsr")


@pytest.fixture(scope="module")
def calibration():
    import json
    return json.loads((HISTORY_DIR / "historico.json").read_text(encoding="utf-8"))["calibration"]


@pytest.fixture(scope="module")
def slices(dsr_rows, calibration):
    return [slice_json(row, calibration) for row in dsr_rows]


def same(actual, cell):
    """Célula vazia ou NaN no CSV (medida ausente) vira None no payload; senão, valor aproximado."""
    value = float(cell) if cell not in ("", None) else float("nan")
    if math.isnan(value):
        assert actual is None
    else:
        assert actual == pytest.approx(value)


def by_key(slice_, key):
    return next(m for m in slice_["metrics"] if m["key"] == key)


def test_three_verdicts_match_framework(dsr_rows, slices):
    for row, body in zip(dsr_rows, slices):
        assert body["case_id"] == row["case_id"]
        assert body["brightness"]["verdict"] == wb_data.STATUS[decision.brightness_verdict(row)]
        assert body["texture"]["verdict"] == wb_data.STATUS[decision.texture_status(row)]
        assert body["noise"]["verdict"] == wb_data.STATUS[noise_verdict(row)]


def test_verdict_counts_match_framework_counts(dsr_rows, slices):
    expected = framework_counts(dsr_rows)
    assert nonzero(Counter(s["texture"]["verdict"] for s in slices)) == expected["texture"]
    assert nonzero(Counter(s["brightness"]["verdict"] for s in slices)) == expected["brightness"]
    assert nonzero(Counter(s["noise"]["verdict"] for s in slices)) == nonzero(
        Counter(wb_data.STATUS[noise_verdict(row)] for row in dsr_rows))


def test_nex_is_paired_z(dsr_rows, slices):
    for row, body in zip(dsr_rows, slices):
        nex = by_key(body, "nex")
        same(nex["z"], row["nex_z"])
        assert nex["value"] == nex["z"]
        assert nex["unit"] == "IQR"
        same(nex["real"], row["nex_real"])
        same(nex["synthetic"], row["nex_synthetic"])
        same(nex["z_low"], row["nex_z_low"])
        same(nex["z_high"], row["nex_z_high"])
        assert nex["status"] == wb_data.STATUS[decision.NEX_STATUS[row["nex_status"]]]


def test_metrics_carry_ci_fields(slices):
    for body in slices:
        for metric in body["metrics"]:
            assert METRIC_KEYS <= metric.keys(), metric["key"]
            assert (metric["certain"] is None) == (metric["z_low"] is None or metric["z_high"] is None)


def test_certain_means_interval_excludes_zero(slices):
    for body in slices:
        for metric in body["metrics"]:
            if metric["certain"] is not None:
                assert metric["certain"] == (metric["z_low"] > 0 or metric["z_high"] < 0)


def test_pct_of_original(dsr_rows, slices):
    for row, body in zip(dsr_rows, slices):
        glcm = by_key(body, "glcm_contrast")
        expected = 100 * float(row["glcm_contrast_synthetic"]) / float(row["glcm_contrast_real"])
        assert glcm["pct_of_original"] == pytest.approx(expected)
        assert by_key(body, "delta_mu")["pct_of_original"] is None


def test_noise_group_metrics(dsr_rows, slices):
    for row, body in zip(dsr_rows, slices):
        statuses = noise_statuses(row)
        for key, label in NPS_METRICS.items():
            metric = by_key(body, f"nps_{key}")
            assert metric["group"] == "noise" and metric["label"] in {"NPS quantity", "NPS grain size", "NPS wide patterns", "NPS fine grain"}
            assert metric["status"] == wb_data.STATUS[statuses[label]]
            same(metric["real"], row[f"nps_{key}_real"])
            same(metric["synthetic"], row[f"nps_{key}_synthetic"])
            same(metric["z"], row[f"nps_{key}_z"])
            same(metric["z_low"], row[f"nps_{key}_z_low"])
            same(metric["z_high"], row[f"nps_{key}_z_high"])
        air = by_key(body, "nps_air")
        assert air["label"] == "Air spots" and air["group"] == "noise" and air["unit"] == "%"
        same(air["value"], row["nps_air_synthetic"])
        same(air["real"], row["nps_air_real"])
        assert air["status"] == wb_data.STATUS[statuses[AIR_LABEL]]
        same(air["peak_sigmas"], row["nps_air_peak_sigmas"])
        assert air["available"] is (str(row["nps_air_available"]).lower() == "true")


def test_noise_techniques_and_extras(dsr_rows, slices):
    for row, body in zip(dsr_rows, slices):
        noise = body["noise"]
        assert set(noise["techniques"]) == NOISE_TECHNIQUES
        statuses = noise_statuses(row)
        assert noise["techniques"]["air"] == wb_data.STATUS[statuses[AIR_LABEL]]
        assert noise["techniques"]["quantity"] == wb_data.STATUS[statuses[NPS_METRICS["quantity"]]]
        assert body["noise_roi_count"] == int(row["nps_roi_count"])
        assert body["noise_available"] is (str(row["nps_available"]).lower() == "true")


def test_wavelet_energy(dsr_rows, slices):
    for row, body in zip(dsr_rows, slices):
        same(body["wavelet_energy"]["real"], row["wavelet_energy_real"])
        same(body["wavelet_energy"]["synthetic"], row["wavelet_energy_synthetic"])


def test_nan_ci_gives_nulls(dsr_rows, calibration):
    row = {**dsr_rows[0], "nex_z_low": "nan", "nex_z_high": "", "nps_quantity_z_low": "nan"}
    body = slice_json(row, calibration)
    nex = by_key(body, "nex")
    assert nex["z_low"] is None and nex["z_high"] is None and nex["certain"] is None
    assert nex["z"] is not None
    quantity = by_key(body, "nps_quantity")
    assert quantity["z_low"] is None and quantity["certain"] is None


def test_metric_without_ci_columns_is_null(slices):
    glcm = by_key(slices[0], "glcm_contrast")
    assert glcm["z_low"] is None and glcm["z_high"] is None and glcm["certain"] is None


def test_reasons_exist_only_for_non_approved_metrics(dsr_rows, slices):
    for row, body in zip(dsr_rows, slices):
        reasons = body["why"]
        assert set(reasons) == {"brightness", "texture", "noise"}
        for group in ("brightness", "texture", "noise"):
            flagged = [m["key"] for m in body["metrics"] if m["group"] == group and m["status"] != "approved"]
            assert [r["metric"] for r in reasons[group]] == flagged, (row["case_id"], group)
            for reason in reasons[group]:
                assert reason["status"] != "approved"
                assert reason["limit"] in {"review", "reject", None}
                assert reason["direction"] in {"higher", "lower", None}


def test_reasons_cover_framework_non_approved_techniques(dsr_rows, slices):
    for row, body in zip(dsr_rows, slices):
        why = body["why"]
        for technique, status in decision.brightness_statuses(row).items():
            has = any(r["technique"] == technique for r in why["brightness"])
            assert has == (status != "aprovada"), (row["case_id"], technique)
        for technique, status in decision.technique_statuses(row).items():
            has = any(r["technique"] == technique for r in why["texture"])
            assert has == (status != "aprovada"), (row["case_id"], technique)
        statuses = noise_statuses(row)
        for key, label in NPS_METRICS.items():
            has = any(r["metric"] == f"nps_{key}" for r in why["noise"])
            assert has == (statuses[label] != "aprovada"), (row["case_id"], key)


def test_reason_shape_and_limits(slices):
    seen = [r for body in slices for group in body["why"].values() for r in group]
    assert seen, "o Dsr real tem ao menos um motivo"
    keys = {"technique", "metric", "status", "value", "z", "z_low", "z_high", "limit", "limit_value", "direction", "note"}
    for reason in seen:
        assert set(reason) == keys
        assert reason["limit"] == {"review": "review", "rejected": "reject"}.get(reason["status"])
        if reason["metric"] == "sat31":
            assert reason["limit_value"] == reasons.SATURATION_LIMIT
        elif reason["metric"] == "nps_air" and reason["limit"] is not None:
            assert reason["limit_value"] == AIR_LIMITS[0 if reason["limit"] == "review" else 1]
        elif reason["z"] is not None and reason["limit"] is not None:
            assert reason["limit_value"] == reasons.Z_LIMITS[reason["limit"]]
        else:
            assert reason["limit_value"] is None
        assert reason["note"] in {None, "few_windows", "lung_not_measured", "air_unavailable", "ci_includes_zero"}


def test_reason_notes_for_inconclusive_nex(dsr_rows, calibration):
    row = {**dsr_rows[0], "nex_status": "inconclusivo"}
    body = slice_json(row, calibration)
    entry = next(r for r in body["why"]["texture"] if r["metric"] == "nex")
    assert entry["status"] == "inconclusive" and entry["note"] == "few_windows" and entry["limit"] is None


def test_reason_notes_when_lung_not_measured(dsr_rows, calibration):
    row = {**dsr_rows[0], "nps_available": "False", "nps_air_available": "False"}
    body = slice_json(row, calibration)
    notes = {r["metric"]: r["note"] for r in body["why"]["noise"]}
    assert all(notes[f"nps_{k}"] == "lung_not_measured" for k in NPS_KEYS if f"nps_{k}" in notes)
    assert notes.get("nps_air") == "air_unavailable"


def test_slices_endpoint_exposes_new_fields(client):
    body = client.get("/api/slices", params={"version": "Dsr"}).json()
    first = body["slices"][0]
    assert {"noise", "wavelet_energy", "why", "noise_roi_count", "noise_available"} <= first.keys()
    assert all(math.isfinite(m["z"]) for m in first["metrics"] if m["z"] is not None)
