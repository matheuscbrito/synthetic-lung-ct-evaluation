"""API dos otimizadores (somente leitura), com logs e resumos temporários: nunca os resultados reais."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.api import notebook, optimizers

CANDIDATE = {"steps": 25, "noise_level": 1, "sampler": "ddim", "scale_factor": 1.0, "seed": 42,
             "eta": 0.0, "latent_noise_scale": 1.0, "conditioning_noise_scale": 1.0}


def _line(**fields):
    return json.dumps(fields, ensure_ascii=False)


def _write(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _gp_lines():
    base = {"method": "gp", "config_index": 0, "cases_cumulative": 0, "best_full_improvement_pct": 0.0}
    return [
        _line(**base, event="inicio", backend="real", budget=269, seed=0, gp_parados="podar",
              nm_initial_step=None, n_sobol_initial=4),
        _line(**base, event="baseline", candidate=CANDIDATE, scope="full", cases_generated=0,
              mean_improvement_pct=0.0, verdict="baseline"),
        _line(**base, event="cache", candidate=CANDIDATE, scope="full", cases_generated=0,
              mean_improvement_pct=0.0, verdict="baseline"),
        _line(method="gp", config_index=1, cases_cumulative=5, best_full_improvement_pct=0.0, event="etapa",
              candidate=CANDIDATE, scope="screen", cases_generated=5, mean_improvement_pct=-60.6991,
              metric_improvement_pct={"glcm_contrast_z": -55.8226}, verdict="descartada",
              reason="pior que a melhor atual", case_wins=0, case_losses=5, rejected=0, pair_issues=0,
              new_best=False, report="/x/report.json"),
        # mesma contagem de casos que o ponto anterior: a curva deve ficar com o último valor
        _line(method="gp", config_index=2, cases_cumulative=5, best_full_improvement_pct=12.5, event="etapa",
              candidate=CANDIDATE, scope="quick", cases_generated=0, mean_improvement_pct=12.5,
              metric_improvement_pct={}, verdict="melhor", reason="supera", case_wins=5, case_losses=0,
              rejected=0, pair_issues=0, new_best=True, report="/x/q.json"),
        _line(method="gp", config_index=3, cases_cumulative=10, best_full_improvement_pct=44.1667,
              event="etapa", candidate=CANDIDATE, scope="full", cases_generated=5, mean_improvement_pct=44.1667,
              metric_improvement_pct={}, verdict="melhor", reason="supera", case_wins=5, case_losses=0,
              rejected=0, pair_issues=0, new_best=True, report="/x/f.json"),
    ]


GP_RESUMO = {"method": "gp", "backend": "real", "budget": 269, "cases_used": 269, "configs_measured": 41,
             "best": {"steps": 43, "noise_level": 2}, "best_full_improvement_pct": 44.1667, "seed": 0}


@pytest.fixture
def results(tmp_path):
    """Diretório com logs de GP-BO e Nelder-Mead (com resumos) e agente (sem resumo)."""
    _write(tmp_path / "gpbo-log.jsonl", _gp_lines())
    (tmp_path / "gpbo-resumo.json").write_text(json.dumps(GP_RESUMO), encoding="utf-8")
    _write(tmp_path / "nm-log.jsonl", [
        _line(method="nm", config_index=0, cases_cumulative=0, best_full_improvement_pct=0.0, event="inicio",
              backend="real", budget=269, seed=0),
        _line(method="nm", config_index=1, cases_cumulative=5, best_full_improvement_pct=3.0, event="etapa",
              candidate=CANDIDATE, scope="screen", cases_generated=5, mean_improvement_pct=4.5,
              metric_improvement_pct={"nex_delta": 1.0}, verdict="melhor", reason="x", case_wins=5,
              case_losses=0, rejected=0, pair_issues=0, new_best=True, report="/x"),
        _line(method="nm", config_index=0, cases_cumulative=0, best_full_improvement_pct=0.0, event="orcamento_esgotado"),
    ])
    (tmp_path / "nm-resumo.json").write_text(json.dumps({"method": "nm", "cases_used": 5,
                                                         "configs_measured": 1, "best": None,
                                                         "best_full_improvement_pct": 3.0}), encoding="utf-8")
    _write(tmp_path / "agente-log.jsonl", [
        _line(method="agente", event="baseline", config_index=0, cases_cumulative=0, cases_generated=0,
              scope="full", mean_improvement_pct=0.0, best_full_improvement_pct=0.0, verdict="baseline"),
        _line(method="agente", event="etapa", config_index=4, cases_cumulative=5, best_full_improvement_pct=0.0,
              candidate=CANDIDATE, scope="screen", cases_generated=5, mean_improvement_pct=7.2794,
              metric_improvement_pct={}, verdict="melhor", reason="supera", case_wins=5, case_losses=0,
              rejected=0, pair_issues=0, new_best=False, report="/x"),
    ])
    return tmp_path


@pytest.fixture
def client(monkeypatch, results):
    monkeypatch.setattr(optimizers, "RESULTS_DIR", results)
    app = FastAPI()
    app.include_router(optimizers.router)
    return TestClient(app)


def _method(body, name):
    return next(m for m in body["methods"] if m["method"] == name)


def test_missing_dir_reports_not_exists(monkeypatch, tmp_path):
    missing = tmp_path / "nao-existe"
    monkeypatch.setattr(optimizers, "RESULTS_DIR", missing)
    app = FastAPI()
    app.include_router(optimizers.router)
    body = TestClient(app).get("/api/optimizers").json()
    assert body["source"] == {"path": str(missing), "exists": False}
    assert body["methods"] == []


def test_source_reports_results_dir(client, results):
    body = client.get("/api/optimizers").json()
    assert body["source"] == {"path": str(results), "exists": True}


def test_methods_have_labels_in_fixed_order(client):
    body = client.get("/api/optimizers").json()
    assert [(m["method"], m["label"]) for m in body["methods"]] == [
        ("gp", "GP-BO"), ("nm", "Nelder-Mead"), ("agente", "Agent (retired)")]


def test_gp_summary_comes_from_resumo(client):
    summary = _method(client.get("/api/optimizers").json(), "gp")["summary"]
    assert summary == {"budget": 269, "cases_used": 269, "configs_measured": 41,
                       "best_full_improvement_pct": 44.1667, "best": {"steps": 43, "noise_level": 2}}


def test_agent_without_resumo_has_null_summary(client):
    assert _method(client.get("/api/optimizers").json(), "agente")["summary"] is None


def test_steps_come_only_from_etapa_events(client):
    gp = _method(client.get("/api/optimizers").json(), "gp")
    assert [s["config_index"] for s in gp["steps"]] == [1, 2, 3]
    first = gp["steps"][0]
    assert first == {
        "config_index": 1, "scope": "screen", "candidate": CANDIDATE, "mean_improvement_pct": -60.6991,
        "metric_improvement_pct": {"glcm_contrast_z": -55.8226}, "verdict": "descartada",
        "reason": "pior que a melhor atual", "case_wins": 0, "case_losses": 5, "rejected": 0,
        "pair_issues": 0, "new_best": False, "cases_generated": 5, "cases_cumulative": 5,
    }


def test_curve_uses_etapa_cache_and_baseline_deduplicated_by_cases(client):
    gp = _method(client.get("/api/optimizers").json(), "gp")
    # baseline (0), cache (0), etapa (5, 5), etapa (10): um ponto por contagem, com o último valor
    assert gp["curve"] == [
        {"cases": 0, "best_full_improvement_pct": 0.0},
        {"cases": 5, "best_full_improvement_pct": 12.5},
        {"cases": 10, "best_full_improvement_pct": 44.1667},
    ]


def test_curve_ignores_inicio_and_other_events(client):
    nm = _method(client.get("/api/optimizers").json(), "nm")
    # inicio (0 casos) e orcamento_esgotado não entram na curva; só a etapa de 5 casos
    assert nm["curve"] == [{"cases": 5, "best_full_improvement_pct": 3.0}]
    assert [s["config_index"] for s in nm["steps"]] == [1]


def test_malformed_lines_are_skipped_and_counted(monkeypatch, tmp_path):
    _write(tmp_path / "nm-log.jsonl", [
        _line(method="nm", event="etapa", config_index=1, cases_cumulative=5, best_full_improvement_pct=1.0,
              candidate=CANDIDATE, scope="screen", cases_generated=5, mean_improvement_pct=1.0,
              metric_improvement_pct={}, verdict="melhor", reason="x", case_wins=1, case_losses=0,
              rejected=0, pair_issues=0, new_best=True),
        "{linha truncada",
        "[1, 2, 3]",
    ])
    monkeypatch.setattr(optimizers, "RESULTS_DIR", tmp_path)
    app = FastAPI()
    app.include_router(optimizers.router)
    body = TestClient(app).get("/api/optimizers").json()
    assert body["skipped"] == 2
    assert len(_method(body, "nm")["steps"]) == 1


def test_non_finite_values_become_null(monkeypatch, tmp_path):
    _write(tmp_path / "nm-log.jsonl", [
        '{"method": "nm", "event": "etapa", "config_index": 1, "cases_cumulative": 5, '
        '"best_full_improvement_pct": NaN, "candidate": {}, "scope": "screen", "cases_generated": 5, '
        '"mean_improvement_pct": Infinity, "metric_improvement_pct": {}, "verdict": "x", "reason": "x", '
        '"case_wins": 0, "case_losses": 0, "rejected": 0, "pair_issues": 0, "new_best": false}',
    ])
    monkeypatch.setattr(optimizers, "RESULTS_DIR", tmp_path)
    app = FastAPI()
    app.include_router(optimizers.router)
    response = TestClient(app).get("/api/optimizers")
    assert response.status_code == 200
    nm = _method(response.json(), "nm")
    assert nm["curve"] == [{"cases": 5, "best_full_improvement_pct": None}]
    assert nm["steps"][0]["mean_improvement_pct"] is None


def test_notebook_alias_delegates_to_notebook_module(monkeypatch, tmp_path):
    (tmp_path / "CADERNO.md").write_text("# Caderno\n\nsem tabela\n", encoding="utf-8")
    monkeypatch.setattr(notebook, "LAB_DIR", tmp_path)
    app = FastAPI()
    app.include_router(optimizers.router)
    response = TestClient(app).get("/api/optimizers/notebook")
    assert response.status_code == 200
    assert response.json() == notebook.read_caderno(tmp_path)


def test_unreadable_log_is_counted_as_skipped(tmp_path):
    events, skipped = optimizers._read_log(tmp_path / "ausente-log.jsonl")
    assert events == [] and skipped == 1
