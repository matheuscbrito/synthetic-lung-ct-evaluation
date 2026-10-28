"""Contrato §4.5 (`GET /api/experiments`): caderno somente leitura, com CADERNO.md temporário (nunca o real)."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.api import notebook
from workbench.api.contract import experiments
from workbench.tests.test_notebook import FIXTURE


def _chain_table(last):
    """Tabela de tentativas com M4 a `last`: M4 nasce do baseline e cada Mn nasce de M(n-1)."""
    rows = ["| # | base | mudança | melhora vs baseline | veredito e motivo |", "|---|---|---|---|---|"]
    for n in range(4, last + 1):
        base = "baseline" if n == 4 else f"M{n - 1}"
        verdict = "melhor (27/10); melhor atual" if n == last else "pior: +1 rejeição"
        rows.append(f"| M{n} | {base} | `eta` 0,{n} | +25,3 / +24,1 / +23,1% | {verdict} |")
    return "\n".join(rows)


CHAIN = FIXTURE.split("## Tentativas")[0] + "## Tentativas\n\n" + _chain_table(12) + "\n\n## Para a próxima busca\n\n1. Próxima.\n"


def _client(monkeypatch, lab):
    monkeypatch.setattr(notebook, "LAB_DIR", lab)
    app = FastAPI()
    app.include_router(experiments.router({}))
    return TestClient(app)


def test_missing_notebook_is_404(monkeypatch, tmp_path):
    assert _client(monkeypatch, tmp_path).get("/api/experiments").status_code == 404


def test_unreadable_notebook_reports_error_instead_of_empty_success(monkeypatch, tmp_path):
    (tmp_path / "CADERNO.md").write_bytes(b"\xff\xfe")
    response = _client(monkeypatch, tmp_path).get("/api/experiments")
    assert response.status_code == 422
    assert response.json()["detail"] == "Notebook could not be read"


def test_source_and_objective(monkeypatch, tmp_path):
    (tmp_path / "CADERNO.md").write_text(FIXTURE, encoding="utf-8")
    body = _client(monkeypatch, tmp_path).get("/api/experiments").json()
    assert body["source"] == {"label": "CADERNO.md", "path": str(tmp_path / "CADERNO.md")}
    assert body["objective"] == {"label": "Improvement vs baseline", "unit": "%", "goal": 15}


def test_scopes_are_fixed(monkeypatch, tmp_path):
    (tmp_path / "CADERNO.md").write_text(FIXTURE, encoding="utf-8")
    body = _client(monkeypatch, tmp_path).get("/api/experiments").json()
    assert body["scopes"] == [{"key": "5", "label": "5 slices"}, {"key": "7", "label": "7 slices"},
                              {"key": "10", "label": "10 slices"}, {"key": "37", "label": "37 slices"}]


def test_experiments_in_source_order_without_search(monkeypatch, tmp_path):
    (tmp_path / "CADERNO.md").write_text(FIXTURE, encoding="utf-8")
    exps = _client(monkeypatch, tmp_path).get("/api/experiments").json()["experiments"]
    assert [e["id"] for e in exps] == ["M2", "M3", "M4", "M5"]
    assert all("search" not in e and "author" not in e for e in exps)


def test_outcomes_and_scores(monkeypatch, tmp_path):
    (tmp_path / "CADERNO.md").write_text(FIXTURE, encoding="utf-8")
    exps = {e["id"]: e for e in _client(monkeypatch, tmp_path).get("/api/experiments").json()["experiments"]}
    assert exps["M2"]["outcome"] == {"status": "rejected", "label": "Worse"}
    assert exps["M3"]["outcome"] == {"status": "review", "label": "Not enough"}
    assert exps["M4"]["outcome"] == {"status": "approved", "label": "Better"}
    assert exps["M2"]["scores"] == {"10": 4.4}
    assert exps["M3"]["scores"] == {}  # "n/d (7 casos)" não traz melhora
    assert exps["M4"]["scores"] == {"5": 7.3, "10": 5.3, "37": 4.8}
    assert exps["M5"]["scores"] == {"5": 25.3, "10": 24.1, "37": 23.1}
    assert exps["M5"]["is_best"] is True and exps["M4"]["is_best"] is False
    assert exps["M5"]["note"] == "melhor (27/10); melhor atual"


def test_parent_chain_reaches_baseline(monkeypatch, tmp_path):
    (tmp_path / "CADERNO.md").write_text(CHAIN, encoding="utf-8")
    exps = {e["id"]: e for e in _client(monkeypatch, tmp_path).get("/api/experiments").json()["experiments"]}
    chain, current = [], "M12"
    while current is not None:
        chain.append(current)
        current = exps[current]["parent"]
    assert chain[-1] == "M4" and chain[:3] == ["M12", "M11", "M10"]
    assert exps["M4"]["parent"] is None


def test_table_for_best_experiment(monkeypatch, tmp_path):
    (tmp_path / "CADERNO.md").write_text(FIXTURE, encoding="utf-8")
    table = _client(monkeypatch, tmp_path).get("/api/experiments").json()["tables"][0]
    assert table["for"] == "M5"
    assert table["columns"] == ["Metric", "Current best", "Other lineage"]
    assert table["rows"][0] == ["GLCM contraste", "+19,81%", "+11,94%"]


def test_sections_learned_and_next(monkeypatch, tmp_path):
    (tmp_path / "CADERNO.md").write_text(FIXTURE, encoding="utf-8")
    sections = _client(monkeypatch, tmp_path).get("/api/experiments").json()["sections"]
    assert [s["title"] for s in sections] == ["What we learned", "Next search"]
    assert sections[0]["items"][0]["head"] == "steps: 35 é o ponto."
    assert sections[1]["items"][0]["head"] is None
    assert sections[1]["items"][0]["body"].startswith("eta 0,4 → 0,5")


def test_unparsable_notebook_has_no_experiments(monkeypatch, tmp_path):
    (tmp_path / "CADERNO.md").write_text("# Caderno\n\nSem tabela.\n", encoding="utf-8")
    body = _client(monkeypatch, tmp_path).get("/api/experiments").json()
    assert body["experiments"] == [] and body["tables"] == []
