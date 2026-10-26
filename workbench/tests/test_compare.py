"""Transições entre versões, estatística de coorte (Wilcoxon do NEx) e contagem de wavelet."""
from collections import Counter

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from scipy.stats import wilcoxon

from frameworks.noise_evaluator.integration import noise_verdict
from frameworks.texture_evaluator import decision, placar
from frameworks.texture_evaluator.placar import PlacarError, load_rows
from workbench.api import compare, data as wb_data
from workbench.api.data import NotFound
from workbench.api.datasets import DATASETS
from workbench.tests.conftest import DATA_OK, HISTORY_DIR, ROOT

pytestmark = pytest.mark.skipif(not DATA_OK, reason="outputs/placar/historico.json ou dados/Dsr ausente")

VERDICT_FN = {"brightness": decision.brightness_verdict, "texture": decision.texture_status, "noise": noise_verdict}


def app_for(history_dir):
    """App mínimo com o router de comparação (o controlador liga no app principal)."""
    app = FastAPI()

    @app.exception_handler(NotFound)
    async def not_found(request, exc: NotFound):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(PlacarError)
    async def broken(request, exc: PlacarError):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    datasets = {"Dsr": {**DATASETS["Dsr"], "history": history_dir}}
    app.include_router(compare.router(datasets))
    return app


@pytest.fixture
def cmp_client():
    return TestClient(app_for(HISTORY_DIR))


def framework_rows(name):
    return {row["case_id"]: row for row in load_rows(HISTORY_DIR, name)}


def test_transitions_shape_and_common_slices(cmp_client):
    r = cmp_client.get("/api/transitions", params={"before": "Dsr", "after": "Dsr-gpbo11", "verdict": "texture"})
    assert r.status_code == 200
    items = r.json()
    assert items and all(set(i) == {"case_id", "label", "before", "after", "change", "became_approved"} for i in items)
    assert {i["change"] for i in items} <= {"improved", "worsened", "same"}
    assert {i["before"] for i in items} <= {"approved", "review", "rejected", "inconclusive"}
    assert all(isinstance(i["became_approved"], bool) for i in items)


@pytest.mark.parametrize("verdict", ["brightness", "texture", "noise"])
def test_transitions_match_framework_verdicts(cmp_client, verdict):
    before, after = framework_rows("Dsr"), framework_rows("Dsr-gpbo11")
    items = cmp_client.get("/api/transitions", params={"before": "Dsr", "after": "Dsr-gpbo11", "verdict": verdict}).json()
    assert [i["case_id"] for i in items] == sorted(before.keys() & after.keys())
    severity = {"aprovada": 0, "revisão": 1, "inconclusivo": 1, "reprovada": 2}  # ui_placar.TRANSITION_SEVERITY
    for item in items:
        old = VERDICT_FN[verdict](before[item["case_id"]])
        new = VERDICT_FN[verdict](after[item["case_id"]])
        assert item["before"] == wb_data.STATUS[old] and item["after"] == wb_data.STATUS[new]
        delta = severity[new] - severity[old]
        expected = "improved" if delta < 0 else "worsened" if delta > 0 else "same"
        assert item["change"] == expected
        assert item["became_approved"] == (old != "aprovada" and new == "aprovada")


def test_transitions_same_version_has_no_change(tmp_history):
    client = TestClient(app_for(tmp_history))
    items = client.get("/api/transitions", params={"before": "Dsr", "after": "Dsr-copy", "verdict": "noise"}).json()
    assert items and {i["change"] for i in items} == {"same"} and not any(i["became_approved"] for i in items)


def test_transitions_errors(cmp_client):
    assert cmp_client.get("/api/transitions", params={"before": "Dsr", "after": "Dsr", "verdict": "final"}).status_code == 422
    assert cmp_client.get("/api/transitions", params={"before": "Nao", "after": "Dsr", "verdict": "texture"}).status_code == 404
    assert cmp_client.get("/api/transitions", params={"before": "Dsr", "after": "Dsr", "verdict": "texture",
                                                      "dataset": "Dgen"}).status_code == 404


def test_cohort_nex_wilcoxon_matches_framework(cmp_client):
    body = cmp_client.get("/api/cohort", params={"version": "Dsr"}).json()
    values = np.array([float(r["nex_z"]) for r in load_rows(HISTORY_DIR, "Dsr") if r["nex_z"] not in ("", None)])
    values = values[np.isfinite(values)]
    stat = body["nex_test"]
    assert stat["n"] == values.size
    assert stat["median_z"] == pytest.approx(float(np.median(values)))
    p = float(wilcoxon(values).pvalue)
    assert stat["p"] == pytest.approx(p)
    assert stat["systematic"] is (p < 0.05)
    assert stat["direction"] == (("higher" if np.median(values) > 0 else "lower") if stat["systematic"] else None)


def test_cohort_wavelet_types_count_framework_rows(cmp_client):
    body = cmp_client.get("/api/cohort", params={"version": "Dsr-gpbo11"}).json()
    expected = Counter(r["wavelet_verdict"] for r in load_rows(HISTORY_DIR, "Dsr-gpbo11"))
    assert body["wavelet_types"] == dict(expected)
    assert sum(body["wavelet_types"].values()) == sum(expected.values())


def test_cohort_copy_runs_test_and_unknown_version_404(tmp_history):
    client = TestClient(app_for(tmp_history))
    body = client.get("/api/cohort", params={"version": "Dsr-copy"}).json()
    assert body["nex_test"]["n"] >= 10 and body["nex_test"]["p"] is not None
    assert client.get("/api/cohort", params={"version": "Versao-inexistente"}).status_code == 404


def test_cohort_unknown_dataset_404(cmp_client):
    assert cmp_client.get("/api/cohort", params={"version": "Dsr", "dataset": "Dgen"}).status_code == 404


def test_cohort_small_n_has_no_median_or_test():
    import dataclasses
    wb = wb_data.load(HISTORY_DIR)
    rows = wb.board["rows"]["Dsr"][:5]
    small = dataclasses.replace(wb, board={**wb.board, "rows": {**wb.board["rows"], "Dsr": rows}})
    stat = compare.cohort(small, "Dsr")["nex_test"]
    assert stat["n"] < compare.NEX_MIN_N
    assert stat["median_z"] is None and stat["p"] is None
    assert stat["systematic"] is False and stat["direction"] is None


def test_cohort_direction_only_when_systematic(cmp_client):
    stat = cmp_client.get("/api/cohort", params={"version": "Dsr-gpbo11"}).json()["nex_test"]
    assert stat["n"] >= compare.NEX_MIN_N and stat["median_z"] is not None
    assert (stat["direction"] is not None) == stat["systematic"]


def test_cohort_wavelet_type_codes(cmp_client):
    from workbench.api.data import WAVELET_CODE
    body = cmp_client.get("/api/cohort", params={"version": "Dsr-gpbo11"}).json()
    expected = Counter(WAVELET_CODE[r["wavelet_verdict"]] for r in load_rows(HISTORY_DIR, "Dsr-gpbo11"))
    assert body["wavelet_type_codes"] == dict(expected)
