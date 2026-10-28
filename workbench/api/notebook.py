"""Experimentos do agente, lidos do CADERNO.md do lung-agent-lab (somente leitura).

O caderno é texto em português: as linhas da tabela de tentativas, a melhora por métrica,
as lições e a próxima busca são extraídas por regra, sem interpretar nada além disso.
Números usam vírgula decimal, como no original; o texto não é traduzido.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from workbench.api.data import ROOT

LAB_DIR = Path(os.environ.get("LUNG_AGENT_LAB", ROOT.parent / "lung-agent-lab"))
CADERNO = "CADERNO.md"

_ID = re.compile(r"^[A-Z]\d+$")
_NUMBER = re.compile(r"[+−-]?\d+(?:,\d+)?(?=\s*(?:/|%))")
_LEGEND = re.compile(r'"([A-Z])"\s*=\s*busca de (\w+)')
_SCOPE = re.compile(r"\((\d+)(?: casos)?\)")
_LESSON = re.compile(r"^- \*\*(.+?)\*\*\s*(.*?)(?=^- |\Z)", re.S | re.M)
_NEXT = re.compile(r"^\d+\.\s+(.*?)(?=^\d+\.|\n\n|\Z)", re.S | re.M)


def _plain(text: str) -> str:
    """Remove a marcação do caderno (negrito e código) e normaliza espaços."""
    return " ".join(text.replace("*", "").replace("`", "").split())


def _number(text: str) -> float:
    return float(text.replace(",", ".").replace("+", "").replace("−", "-"))


def _section(text: str, heading: str) -> str | None:
    """Corpo de uma seção `## heading` até o próximo `## ` (ou o fim)."""
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return match.group(1) if match else None


def _row(cells: list[str], searches: dict[str, str]) -> dict:
    rid, base, change, gain, verdict = cells
    clean_gain = _plain(gain)
    clean_verdict = _plain(verdict)
    vals = [_number(v) for v in _NUMBER.findall(clean_gain)]
    scope = _SCOPE.search(clean_gain)
    word = clean_verdict.split()[0].strip(":;,") if clean_verdict else ""
    return {
        "id": rid,
        "base": _plain(base),
        "change": _plain(change),
        "gain_text": clean_gain,
        "vals": vals,
        "scope": scope.group(1) if scope and len(vals) <= 1 else None,
        "verdict": word,
        "reason": clean_verdict,
        "best": "melhor atual" in clean_verdict,
        "search": searches.get(rid[0], rid[0]),
    }


def parse_caderno(text: str) -> dict:
    """Tabela de tentativas, melhora por métrica, lições e próxima busca do caderno."""
    searches = {letter: name for letter, name in _LEGEND.findall(text)}

    rows = []
    attempts = _section(text, "Tentativas") or ""
    for line in attempts.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.strip().startswith("|") and len(cells) == 5 and _ID.match(cells[0]):
            rows.append(_row(cells, searches))

    metrics = []
    m = re.search(r"Melhora média por métrica.*?\n\n(\|.*?)(?:\n\n|\Z)", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            cells = [_plain(c) for c in line.strip().strip("|").split("|")]
            if len(cells) >= 3 and cells[1].endswith("%"):
                metrics.append({"name": cells[0], "best": cells[1], "other": cells[2]})

    learned = []
    lessons = _section(text, "O que aprendemos") or ""
    for head, body in _LESSON.findall(lessons):
        learned.append({"head": _plain(head), "body": _plain(body)})

    following = _section(text, "Para a próxima busca") or ""
    next_steps = [_plain(item) for item in _NEXT.findall(following)]

    return {"searches": searches, "rows": rows, "metrics": metrics, "learned": learned, "next": next_steps}


def read_caderno(lab_dir: Path) -> dict:
    """Leitura usada por `/api/experiments`: o caderno interpretado, o texto bruto sem tentativas, ou um erro de leitura."""
    path = Path(lab_dir) / CADERNO
    source = {"path": str(path), "exists": path.is_file()}
    if not source["exists"]:
        return {"source": source, "parsed": None, "raw": None}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        # arquivo existe mas não pode ser lido: a tela mostra a mensagem, sem 500
        return {"source": source, "parsed": None, "raw": None, "error": str(error)}
    parsed = parse_caderno(text)
    if not parsed["rows"]:
        return {"source": source, "parsed": None, "raw": text}
    return {"source": source, "parsed": parsed, "raw": None}
