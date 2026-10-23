"""Leitura somente leitura do CADERNO.md do agente, com fixture inline (nunca o arquivo real)."""
from fastapi.testclient import TestClient

from workbench.api import notebook
from workbench.api.app import create_app

FIXTURE = """# Caderno de experimentos

Memória da busca. Todas contra o baseline fixo. "M" = busca de Matheus; "L" = busca de Lucas.
Quando há três números, são os escopos de 5, 10 e 37 casos.

## Melhor atual

| steps | eta |
|---|---|
| 35 | **0.4** |

Melhora média por métrica (37 casos, contra o baseline):

| métrica | melhor atual (eta 0,4) | Lucas (eta 0,35) |
|---|---:|---:|
| GLCM contraste | +19,81% | +11,94% |
| **média** | **+23,05%** | **+15,96%** |
| nota | 76,73 | 74,63 |

Melhorou nas sete métricas.

## O que aprendemos

- **`steps`: 35 é o ponto.** Sozinho dá +7,8%. Com 45 piora.
- **`eta`: o parâmetro mais confiável.** De 0 a 0,4 a melhora quase só sobe.

## Tentativas

| # | base | mudança | melhora vs baseline | veredito e motivo |
|---|---|---|---|---|
| M2 | baseline | `noise_level` 50 | +4,40% (10) | pior: +1 rejeição |
| M3 | M2 | **`steps` 45** | n/d (7 casos) | insuficiente: 2 cortes melhores |
| M4 | baseline | **`eta` 0,2** | +7,3 / +5,3 / +4,8% | melhor (29/8) |
| M5 | M4 | **`conditioning` 1,4** | +25,3 / +24,1 / +23,1% | **melhor (27/10); melhor atual** |

## Para a próxima busca

Pistas a confirmar, nenhuma executada:

1. `eta` 0,4 → 0,5, mantendo `conditioning` 1,4. Vigiar o NEx.
   Segunda linha da mesma pista.
2. `conditioning_noise_scale` 1,4 → 1,5.
"""


def test_parse_searches_legend():
    assert notebook.parse_caderno(FIXTURE)["searches"] == {"M": "Matheus", "L": "Lucas"}


def test_parse_rows_fields():
    rows = notebook.parse_caderno(FIXTURE)["rows"]
    assert [r["id"] for r in rows] == ["M2", "M3", "M4", "M5"]
    assert all(r["search"] == "Matheus" for r in rows)
    single, nd, three, best = rows
    assert single["vals"] == [4.4] and single["scope"] == "10" and single["verdict"] == "pior"
    assert single["base"] == "baseline" and single["best"] is False
    assert nd["vals"] == [] and nd["scope"] == "7" and nd["verdict"] == "insuficiente"
    assert nd["gain_text"] == "n/d (7 casos)"
    assert three["vals"] == [7.3, 5.3, 4.8] and three["scope"] is None and three["verdict"] == "melhor"
    assert best["best"] is True and best["verdict"] == "melhor"
    assert best["vals"] == [25.3, 24.1, 23.1]
    assert best["base"] == "M4" and best["change"] == "conditioning 1,4"
    assert "*" not in best["reason"] and "`" not in best["change"]


def test_parse_metrics_and_lessons_and_next():
    parsed = notebook.parse_caderno(FIXTURE)
    assert parsed["metrics"] == [
        {"name": "GLCM contraste", "best": "+19,81%", "other": "+11,94%"},
        {"name": "média", "best": "+23,05%", "other": "+15,96%"},
    ]
    assert parsed["learned"][0] == {"head": "steps: 35 é o ponto.", "body": "Sozinho dá +7,8%. Com 45 piora."}
    assert parsed["learned"][1]["head"] == "eta: o parâmetro mais confiável."
    assert len(parsed["next"]) == 2
    assert parsed["next"][0].startswith("eta 0,4 → 0,5, mantendo conditioning 1,4. Vigiar o NEx.")
    assert "Segunda linha" in parsed["next"][0]


def test_missing_file_reports_not_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(notebook, "LAB_DIR", tmp_path)
    assert notebook.read_caderno(tmp_path) == {
        "source": {"path": str(tmp_path / "CADERNO.md"), "exists": False},
        "parsed": None,
        "raw": None,
    }


def test_unparsable_returns_raw(tmp_path):
    (tmp_path / "CADERNO.md").write_text("# Caderno\n\nSem tabela de tentativas.\n", encoding="utf-8")
    out = notebook.read_caderno(tmp_path)
    assert out["source"]["exists"] is True
    assert out["parsed"] is None
    assert out["raw"] == "# Caderno\n\nSem tabela de tentativas.\n"


def test_endpoint_returns_parsed(tmp_path, monkeypatch):
    (tmp_path / "CADERNO.md").write_text(FIXTURE, encoding="utf-8")
    monkeypatch.setattr(notebook, "LAB_DIR", tmp_path)
    body = TestClient(create_app()).get("/api/agent/notebook").json()
    assert body["source"]["exists"] is True and body["raw"] is None
    assert [r["id"] for r in body["parsed"]["rows"]] == ["M2", "M3", "M4", "M5"]


def test_endpoint_missing_file_is_200_not_404(tmp_path, monkeypatch):
    monkeypatch.setattr(notebook, "LAB_DIR", tmp_path)
    response = TestClient(create_app()).get("/api/agent/notebook")
    assert response.status_code == 200
    assert response.json()["source"]["exists"] is False


def parse_metrics(text):
    return notebook.parse_caderno(text)["metrics"]


def test_metrics_table_at_end_of_file():
    # a tabela de métricas é o último bloco do arquivo: não há linha em branco depois dela
    text = (
        "## Melhor atual\n\n"
        "Melhora média por métrica (37 casos, contra o baseline):\n\n"
        "| métrica | melhor atual (eta 0,4) | Lucas (eta 0,35) |\n"
        "|---|---:|---:|\n"
        "| GLCM contraste | +19,81% | +11,94% |\n"
        "| **média** | **+23,05%** | **+15,96%** |"
    )
    assert parse_metrics(text) == [
        {"name": "GLCM contraste", "best": "+19,81%", "other": "+11,94%"},
        {"name": "média", "best": "+23,05%", "other": "+15,96%"},
    ]


def test_unreadable_notebook_returns_error_line(tmp_path, monkeypatch):
    (tmp_path / "CADERNO.md").write_bytes(b"\xff\xfe\x00bytes que nao sao utf-8 \x80\x81")
    monkeypatch.setattr(notebook, "LAB_DIR", tmp_path)
    response = TestClient(create_app()).get("/api/agent/notebook")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == {"path": str(tmp_path / "CADERNO.md"), "exists": True}
    assert body["parsed"] is None and body["raw"] is None
    assert isinstance(body["error"], str) and body["error"]


def test_unreadable_file_os_error_returns_error_line(tmp_path, monkeypatch):
    (tmp_path / "CADERNO.md").write_text(FIXTURE, encoding="utf-8")
    monkeypatch.setattr(notebook, "LAB_DIR", tmp_path)

    def denied(self, *args, **kwargs):
        raise PermissionError("sem permissão de leitura")

    monkeypatch.setattr(notebook.Path, "read_text", denied)
    out = notebook.read_caderno(tmp_path)
    assert out == {
        "source": {"path": str(tmp_path / "CADERNO.md"), "exists": True},
        "parsed": None,
        "raw": None,
        "error": "sem permissão de leitura",
    }
