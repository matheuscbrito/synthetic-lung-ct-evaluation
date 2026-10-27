"""Contrato §4.4 (`GET /api/runs`): execuções dos otimizadores em uso, com logs temporários (nunca os reais)."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.api import optimizers
from workbench.api.contract import runs
from workbench.tests.test_optimizers import CANDIDATE, _line, _write


def _candidate(steps, eta, sampler="ddim"):
    return {**CANDIDATE, "steps": steps, "eta": eta, "sampler": sampler}


def _etapa(method, index, cases, score, candidate, verdict, best, new_best=False, scope="full"):
    return _line(method=method, config_index=index, cases_cumulative=cases, best_full_improvement_pct=best,
                 event="etapa", candidate=candidate, scope=scope, cases_generated=cases,
                 mean_improvement_pct=score, metric_improvement_pct={}, verdict=verdict, reason="x",
                 case_wins=4, case_losses=1, rejected=0, pair_issues=0, new_best=new_best, report="/x")


def _gp_lines():
    base = {"method": "gp", "config_index": 0, "cases_cumulative": 0, "best_full_improvement_pct": 0.0}
    return [
        _line(**base, event="inicio", backend="real", budget=269, seed=0),
        _line(**base, event="baseline", candidate=_candidate(25, 0.0), scope="full", cases_generated=0,
              mean_improvement_pct=0.0, verdict="baseline"),
        _etapa("gp", 1, 5, -3.0, _candidate(30, 0.1), "pior", best=0.0),
        _etapa("gp", 2, 10, 12.5, _candidate(43, 0.2), "melhor", best=12.5, new_best=True),
        _etapa("gp", 3, 15, 9.0, _candidate(40, 0.3), "insuficiente", best=12.5),
        _etapa("gp", 4, 20, 8.0, _candidate(40, 0.4), "descartada", best=12.5),
        "[1, 2]",  # JSON válido, mas não é um evento
        "{linha malformada",
    ]


GP_RESUMO = {"method": "gp", "budget": 269, "cases_used": 269, "configs_measured": 41,
             "best": {"steps": 43, "eta": 0.2, "sampler": "ddim"}, "best_full_improvement_pct": 44.1667}


@pytest.fixture
def results(tmp_path):
    _write(tmp_path / "gpbo-log.jsonl", _gp_lines())
    (tmp_path / "gpbo-resumo.json").write_text(json.dumps(GP_RESUMO), encoding="utf-8")
    _write(tmp_path / "nm-log.jsonl", [
        _line(method="nm", config_index=0, cases_cumulative=0, best_full_improvement_pct=0.0, event="inicio"),
        _etapa("nm", 1, 5, 3.0, _candidate(20, 0.0), "melhor", best=3.0, new_best=True),
        _etapa("nm", 2, 10, 2.0, _candidate(22, 0.0), "pior", best=3.0),
    ])
    _write(tmp_path / "agente-log.jsonl", [
        _etapa("agente", 4, 5, 7.3, _candidate(35, 0.4), "melhor", best=7.3, new_best=True),
    ])
    return tmp_path


@pytest.fixture
def client(monkeypatch, results):
    monkeypatch.setattr(optimizers, "RESULTS_DIR", results)
    app = FastAPI()
    app.include_router(runs.router(None))
    return TestClient(app)


def _run(body, key):
    return next(r for r in body["runs"] if r["key"] == key)


def test_agent_is_excluded(client):
    body = client.get("/api/runs").json()
    assert [r["key"] for r in body["runs"]] == ["gp", "nm"]
    assert "agente" not in json.dumps(body)


def test_run_labels_and_objective(client):
    body = client.get("/api/runs").json()
    assert [(r["key"], r["label"]) for r in body["runs"]] == [("gp", "GP-BO"), ("nm", "Nelder-Mead")]
    assert body["objective"] == {"label": "Improvement vs start", "unit": "%", "goal": 15, "higher_is_better": True}
    assert body["budget_axis"] == {"label": "cases generated"}


def test_source_reports_results_dir(client, results):
    assert client.get("/api/runs").json()["sources"] == [
        {"label": "lung-agent-lab logs", "path": str(results), "exists": True}]


def test_params_keep_only_varying_keys(client):
    keys = [p["key"] for p in client.get("/api/runs").json()["params"]]
    assert keys == ["steps", "eta"]
    assert "seed" not in keys and "scale_factor" not in keys


def test_sampler_only_in_best_params(client):
    body = client.get("/api/runs").json()
    assert "sampler" not in [p["key"] for p in body["params"]]
    assert _run(body, "gp")["best_params"] == {"steps": 43, "eta": 0.2, "sampler": "ddim"}


def test_step_params_are_labelled_keys(client):
    gp = _run(client.get("/api/runs").json(), "gp")
    assert gp["steps"][0]["params"] == {"steps": 30, "eta": 0.1}


def test_outcomes_are_translated_and_unknown_kept(client):
    steps = _run(client.get("/api/runs").json(), "gp")["steps"]
    outcomes = [s["outcome"] for s in steps[:4]]
    assert outcomes == [
        {"status": "rejected", "label": "Worse"},
        {"status": "approved", "label": "Better"},
        {"status": "review", "label": "Not enough"},
        {"status": "inconclusive", "label": "descartada"},
    ]


def test_steps_carry_id_stage_score_wins_and_best_flag(client):
    steps = _run(client.get("/api/runs").json(), "gp")["steps"]
    assert steps[1] == {"id": "2", "stage": "full", "params": {"steps": 43, "eta": 0.2}, "score": 12.5,
                        "outcome": {"status": "approved", "label": "Better"},
                        "wins": 4, "losses": 1, "is_best": True}
    assert steps[0]["is_best"] is False


def test_malformed_and_incomplete_lines_are_skipped(client):
    steps = _run(client.get("/api/runs").json(), "gp")["steps"]
    assert [s["id"] for s in steps] == ["1", "2", "3", "4"]


def test_curve_points_use_x_and_y(client):
    curve = _run(client.get("/api/runs").json(), "gp")["curve"]
    assert curve == [{"x": 0, "y": 0.0}, {"x": 5, "y": 0.0}, {"x": 10, "y": 12.5},
                     {"x": 15, "y": 12.5}, {"x": 20, "y": 12.5}]


def test_summary_comes_from_resumo(client):
    assert _run(client.get("/api/runs").json(), "gp")["summary"] == {
        "best": 44.1667, "evaluated": 41, "used": 269, "budget": 269}


def test_summary_without_resumo_falls_back_to_log(client):
    nm = _run(client.get("/api/runs").json(), "nm")
    assert nm["summary"] == {"best": 3.0, "evaluated": 2, "used": 10, "budget": None}
    assert nm["best_params"] == {"steps": 20, "eta": 0.0, "sampler": "ddim"}


def test_null_best_in_resumo_does_not_crash(client, results):
    (results / "nm-resumo.json").write_text(json.dumps({"method": "nm", "best": None,
                                                         "best_full_improvement_pct": 3.0,
                                                         "configs_measured": 1, "cases_used": 5,
                                                         "budget": 5}), encoding="utf-8")
    assert _run(client.get("/api/runs").json(), "nm")["best_params"] == {"steps": 20, "eta": 0.0, "sampler": "ddim"}


def test_missing_dir_reports_not_exists(monkeypatch, tmp_path):
    missing = tmp_path / "nao-existe"
    monkeypatch.setattr(optimizers, "RESULTS_DIR", missing)
    app = FastAPI()
    app.include_router(runs.router({}))
    body = TestClient(app).get("/api/runs").json()
    assert body["sources"] == [{"label": "lung-agent-lab logs", "path": str(missing), "exists": False}]
    assert body["runs"] == []


def test_empty_dir_has_no_runs(monkeypatch, tmp_path):
    monkeypatch.setattr(optimizers, "RESULTS_DIR", tmp_path)
    app = FastAPI()
    app.include_router(runs.router({}))
    body = TestClient(app).get("/api/runs").json()
    assert body["sources"][0]["exists"] is True
    assert body["runs"] == []
