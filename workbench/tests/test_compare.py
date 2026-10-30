"""Transições entre versões, estatística de coorte (Wilcoxon do NEx) e contagem de wavelet."""
from collections import Counter

import numpy as np
import pytest
from scipy.stats import wilcoxon

from frameworks.noise_evaluator.integration import noise_verdict
from frameworks.texture_evaluator import decision, placar
from frameworks.texture_evaluator.placar import load_rows
from workbench.api import compare, data as wb_data
from workbench.api.data import NotFound
from workbench.tests.conftest import DATA_OK, HISTORY_DIR

pytestmark = pytest.mark.skipif(not DATA_OK, reason="outputs/placar/historico.json ou dados/Dsr ausente")

VERDICT_FN = {"brightness": decision.brightness_verdict, "texture": decision.texture_status, "noise": noise_verdict}


@pytest.fixture(scope="module")
def wb():
    return wb_data.load(HISTORY_DIR)


def framework_rows(name):
    return {row["case_id"]: row for row in load_rows(HISTORY_DIR, name)}


def test_transitions_shape_and_common_slices(wb):
    items = compare.transitions(wb, "Dsr", "gpbo-11-full", "texture")
    assert items and all(set(i) == {"case_id", "label", "before", "after", "change", "became_approved"} for i in items)
    assert {i["change"] for i in items} <= {"improved", "worsened", "same"}
    assert {i["before"] for i in items} <= {"approved", "review", "rejected", "inconclusive"}
    assert all(isinstance(i["became_approved"], bool) for i in items)


@pytest.mark.parametrize("verdict", ["brightness", "texture", "noise"])
def test_transitions_match_framework_verdicts(wb, verdict):
    before, after = framework_rows("Dsr"), framework_rows("gpbo-11-full")
    items = compare.transitions(wb, "Dsr", "gpbo-11-full", verdict)
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
    items = compare.transitions(wb_data.load(tmp_history), "Dsr", "Dsr-copy", "noise")
    assert items and {i["change"] for i in items} == {"same"} and not any(i["became_approved"] for i in items)


def test_cohort_nex_wilcoxon_matches_framework(wb):
    body = compare.cohort(wb, "Dsr")
    values = np.array([float(r["nex_z"]) for r in load_rows(HISTORY_DIR, "Dsr") if r["nex_z"] not in ("", None)])
    values = values[np.isfinite(values)]
    stat = body["nex_test"]
    assert stat["n"] == values.size
    assert stat["median_z"] == pytest.approx(float(np.median(values)))
    p = float(wilcoxon(values).pvalue)
    assert stat["p"] == pytest.approx(p)
    assert stat["systematic"] is (p < 0.05)
    assert stat["direction"] == (("higher" if np.median(values) > 0 else "lower") if stat["systematic"] else None)


def test_cohort_wavelet_types_count_framework_rows(wb):
    body = compare.cohort(wb, "gpbo-11-full")
    expected = Counter(r["wavelet_verdict"] for r in load_rows(HISTORY_DIR, "gpbo-11-full"))
    assert body["wavelet_types"] == dict(expected)
    assert sum(body["wavelet_types"].values()) == sum(expected.values())


def test_cohort_copy_runs_test_and_unknown_version_is_not_found(tmp_history):
    copy = wb_data.load(tmp_history)
    body = compare.cohort(copy, "Dsr-copy")
    assert body["nex_test"]["n"] >= 10 and body["nex_test"]["p"] is not None
    with pytest.raises(NotFound):
        compare.cohort(copy, "Versao-inexistente")


def test_cohort_small_n_has_no_median_or_test():
    import dataclasses
    wb = wb_data.load(HISTORY_DIR)  # cópia própria: o fixture de módulo não é alterado
    rows = wb.board["rows"]["Dsr"][:5]
    small = dataclasses.replace(wb, board={**wb.board, "rows": {**wb.board["rows"], "Dsr": rows}})
    stat = compare.cohort(small, "Dsr")["nex_test"]
    assert stat["n"] < compare.NEX_MIN_N
    assert stat["median_z"] is None and stat["p"] is None
    assert stat["systematic"] is False and stat["direction"] is None


def test_cohort_direction_only_when_systematic(wb):
    stat = compare.cohort(wb, "gpbo-11-full")["nex_test"]
    assert stat["n"] >= compare.NEX_MIN_N and stat["median_z"] is not None
    assert (stat["direction"] is not None) == stat["systematic"]


def test_cohort_wavelet_type_codes(wb):
    from workbench.api.data import WAVELET_CODE
    body = compare.cohort(wb, "gpbo-11-full")
    expected = Counter(WAVELET_CODE[r["wavelet_verdict"]] for r in load_rows(HISTORY_DIR, "gpbo-11-full"))
    assert body["wavelet_type_codes"] == dict(expected)
