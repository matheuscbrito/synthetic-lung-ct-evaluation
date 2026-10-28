"""Gera workbench/web/src/fixtures/real.json a partir das rotas do contrato (FastAPI TestClient).

Uso, na raiz do repositório:

    .venv/bin/python workbench/web/scripts/make_real_fixture.py [saida.json]

Lê o histórico real (somente leitura) pelas mesmas rotas que a interface usa: /api/schema, /api/versions,
/api/items, /api/inspect/{key}, /api/board, /api/transitions, /api/runs, /api/experiments e
/api/versions/detected. Nada é recalculado aqui. As execuções e o caderno vêm de OPTIMIZER_RESULTS e
LUNG_AGENT_LAB (variáveis lidas pela API); sem eles, `runs`/`experiments` ficam null.

Regras do bundle (as mesmas de docs/planning/mockups-v3/bundle_real.py):
- `current` é a versão rotulada CURRENT_LABEL; `baseline` é `schema.dataset.default_baseline`;
- `focus` é o pior item do eixo FOCUS_AXIS reprovado que também tem motivo em outro eixo (senão o pior);
- `compare_items` é o foco e o pior item de cada um dos outros status (review, approved) no mesmo eixo;
- `inspect` tem um payload por inspetor de dados (não-imagem), do foco, comparado com a linha de base;
- `compare_inspect` é a sobreposição do inspetor de comparação, montada como em CompareView.overlayOf;
- campos de imagem (thumbs, panes, compare_images) ficam "" para manter o arquivo pequeno.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from workbench.api.app import create_app  # noqa: E402

OUT = ROOT / "workbench" / "web" / "src" / "fixtures" / "real.json"
CURRENT_LABEL = "GP-BO #11"
FOCUS_AXIS = "noise"
OTHER_STATUSES = ("review", "approved")


def get(client: TestClient, path: str, **params):
    response = client.get(path, params=params)
    response.raise_for_status()
    return response.json()


def optional(client: TestClient, path: str, **params):
    response = client.get(path, params=params)
    return response.json() if response.status_code == 200 else None


def worst_abs_z(item: dict, axis: str, metric_axis: dict) -> float:
    values = [abs(m["z"]) for key, m in item["metrics"].items() if m.get("z") is not None and metric_axis.get(key) == axis]
    return max(values, default=0.0)


def pick_focus(items: list[dict], axis: str, schema: dict) -> tuple[str, list[str]]:
    severity = {s["key"]: s["severity"] for s in schema["statuses"]}
    metric_axis = {m["key"]: m["axis"] for m in schema["metrics"]}
    ordered = sorted(items, key=lambda i: (-severity[i["verdicts"][axis]], -worst_abs_z(i, axis, metric_axis), i["id"]))
    focus = next((i["id"] for i in ordered
                  if i["verdicts"][axis] == "rejected" and any(r["axis"] != axis for r in i["reasons"])), ordered[0]["id"])
    others = [next((i["id"] for i in ordered if i["verdicts"][axis] == status and i["id"] != focus), None)
              for status in OTHER_STATUSES]
    return focus, [focus] + [i for i in others if i]


def overlay(payloads: list[dict], labels: list[str]) -> dict:
    """Porte de CompareView.overlayOf: série real do primeiro item e uma série por item."""
    first = payloads[0]
    reference = [s for s in first["series"] if s["role"] == "real"]
    series = []
    for payload, label in zip(payloads, labels):
        own = next((s for s in payload["series"] if s["role"] != "real"), None)
        if own:
            series.append({**own, "role": "item", "label": label})
    return {**first, "series": reference + series}


def build(client: TestClient) -> dict:
    schema = get(client, "/api/schema")
    dataset = schema["dataset"]["key"]
    versions = get(client, "/api/versions", dataset=dataset)
    current = next(v["name"] for v in versions if v["label"] == CURRENT_LABEL)
    baseline = schema["dataset"]["default_baseline"]
    items = {v["name"]: get(client, "/api/items", dataset=dataset, version=v["name"])["items"] for v in versions}
    cur = items[current]
    axis = FOCUS_AXIS if any(a["key"] == FOCUS_AXIS for a in schema["axes"]) else schema["axes"][0]["key"]
    focus, compare_items = pick_focus(cur, axis, schema)

    inspect = {}
    for desc in schema["inspectors"]:
        if desc["chart"] == "image":
            continue
        inspect[desc["key"]] = get(client, f"/api/inspect/{desc['key']}", dataset=dataset, version=current,
                                   item=focus, compare=baseline)
    compare_desc = next(d for d in schema["inspectors"] if d.get("compare"))
    label = {i["id"]: i["label"] for i in cur}
    compare_payloads = [get(client, f"/api/inspect/{compare_desc['key']}", dataset=dataset, version=current, item=i)
                        for i in compare_items]

    return {
        "title": "QC Workbench · real data",
        "schema": schema,
        "baseline": baseline,
        "current": current,
        "items": items,
        "thumbs": {i["id"]: "" for i in cur},
        "focus": focus,
        "compare_items": compare_items,
        "pane_versions": [baseline, schema["dataset"]["reference_version"], current],
        "panes": {key: "" for key in ("real", schema["dataset"]["reference_version"], baseline, current, "overlay")},
        "inspect": inspect,
        "compare_images": {i: "" for i in compare_items},
        "compare_inspect": {"inspector": compare_desc["key"],
                            "payload": overlay(compare_payloads, [label[i] for i in compare_items])},
        "board": get(client, "/api/board", dataset=dataset, baseline=baseline),
        "transitions": {a["key"]: get(client, "/api/transitions", dataset=dataset, before=baseline, after=current,
                                      axis=a["key"]) for a in schema["axes"]},
        "runs": optional(client, "/api/runs") if schema["addons"]["optimizers"] else None,
        "experiments": optional(client, "/api/experiments") if schema["addons"]["experiments"] else None,
        "versions": versions,
        "detected": get(client, "/api/versions/detected", dataset=dataset),
    }


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT
    bundle = build(TestClient(create_app()))
    out.write_text(json.dumps(bundle, ensure_ascii=False) + "\n", encoding="utf-8")
    print("ok", out, len(bundle["items"][bundle["current"]]), bundle["focus"], bundle["compare_items"])


if __name__ == "__main__":
    main()
