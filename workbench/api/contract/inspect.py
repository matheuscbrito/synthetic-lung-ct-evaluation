"""Inspetores do contrato genérico (§4.2): `GET /api/inspect/{key}?dataset=&version=&item=&compare=`.

Cada inspetor de `schema.inspectors()` vira um payload por tipo de gráfico, sem nome de métrica na forma:
- `spectrum` (curves), `glcm` e `nex_windows` (matrix), `nex` (interval) e `wavelet` (bars) saem das
  funções de `tools` (as antigas rotas `/api/tools/*` foram removidas);
- `figure`, `map` e `noise_figure` (image) devolvem `{url, caption}`; a URL aponta para
  `GET /api/inspect/{key}.png`, que desenha com `board.technique_png`, `board.map_png` e `board.nps_png`.
Séries e painéis são rotulados pelo rótulo de exibição da versão (`versions.version_label`), nunca pela pasta.
Opções fora das `choices` do schema são 400; inspetor desconhecido é 404.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote, urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from frameworks.texture_evaluator.run_mvp import context_from_dict
from workbench.api import board, data, datasets as ds, images, reasons, tools
from workbench.api.contract import schema, versions
from workbench.api.contract.items import item_json
from workbench.api.data import Workbench

NYQUIST = 0.5
# faixas do intervalo NEx em IQR: NEx sozinho nunca rejeita (revisão quando |z| > 1 e o IC exclui 0), então só
# há revisão além de ±`reasons.Z_LIMITS["review"]`; os extremos ±4 só delimitam o desenho
_NEX_REVIEW = reasons.Z_LIMITS["review"]
NEX_BANDS = [(-4, -_NEX_REVIEW, "review"), (-_NEX_REVIEW, _NEX_REVIEW, "approved"), (_NEX_REVIEW, 4, "review")]
DATA_KEYS = ("spectrum", "glcm", "nex", "nex_windows", "wavelet")
IMAGE_KEYS = ("figure", "map", "noise_figure")


def _descriptor(key: str) -> dict:
    found = next((item for item in schema.inspectors() if item["key"] == key), None)
    if found is None:
        raise HTTPException(404, f"unknown inspector: {key}")
    return found


def _options(descriptor: dict, query: dict) -> dict:
    """Valor de cada opção do descritor: o pedido, ou a primeira escolha; fora das `choices` → 400."""
    out = {}
    for option in descriptor["options"]:
        keys = [choice["key"] for choice in option["choices"]]
        value = query.get(option["key"])
        if value is None or value == "":
            value = keys[0]
        if value not in keys:
            raise HTTPException(400, f"invalid {option['key']}: {value} (choices: {', '.join(keys)})")
        out[option["key"]] = value
    return out


def _compare(wb: Workbench, version: str, compare: str | None) -> list[str]:
    """Versões a sobrepor, na ordem pedida e sem repetir; vazio: só `version`. Desconhecida: 404."""
    names = list(dict.fromkeys(name.strip() for name in (compare or "").split(",") if name.strip())) or [version]
    for name in names:
        wb.entry(name)
    return names


def _labeller(wb: Workbench):
    meta = versions.load_meta(Path(wb.history_dir))
    return lambda name: versions.version_label(name, wb.history, meta)


def spectrum(wb: Workbench, item: str, names: list[str], label) -> dict:
    ruler = context_from_dict(wb.history["calibration"]).ruler
    first = images.case(wb, names[0], item)  # a original é a mesma em toda versão do corte
    freq, real = tools.radial_spectrum(tools.normalise(first.original, ruler), first.lung_mask)
    series = [{"label": "Real", "role": "real", "x": freq, "y": real}]
    for name in names:
        case = images.case(wb, name, item)
        _, synthetic = tools.radial_spectrum(tools.normalise(case.synthetic, ruler), case.lung_mask)
        series.append({"label": label(name), "role": "version", "x": freq, "y": synthetic})
    band = tools.reference_band(wb)
    return {"x": {"label": "Frequency (cycles/px)", "scale": "linear"},
            "y": {"label": "Power", "scale": "log"},
            "band": {"label": "Real slices P5–P95", "x": freq, "lo": band["p5"], "hi": band["p95"]},
            "markers": [{"x": NYQUIST, "label": "Nyquist"}],
            "series": series}


def glcm(wb: Workbench, item: str, version: str, label) -> dict:
    case = images.case(wb, version, item)
    scale = context_from_dict(wb.history["calibration"]).scale
    tones = list(range(scale.levels))
    return {"rows": tones, "cols": tones,
            "panels": [{"label": "Real", "values": tools.glcm_matrix(case.original, case.lung_mask, scale)},
                       {"label": f"Synthetic · {label(version)}",
                        "values": tools.glcm_matrix(case.synthetic, case.lung_mask, scale)}],
            "scale": {"label": "Share of neighbouring tone pairs"}}


def nex(wb: Workbench, item: str, version: str) -> dict:
    metric = item_json(data.slice_json(wb.row(version, item), wb.history["calibration"]))["metrics"]["nex"]
    return {"value": metric["z"], "ci": metric["ci"], "label": "NEx (IQR)",
            "bands": [{"from": low, "to": high, "status": status} for low, high, status in NEX_BANDS]}


def _grid(windows: list[dict], rows: list[int], cols: list[int]) -> list[list[float | None]]:
    values = {(w["row"], w["col"]): tools.json_number(w["value"]) for w in windows}
    return [[values.get((row, col)) for col in cols] for row in rows]


def nex_windows(wb: Workbench, item: str, version: str, label) -> dict:
    """Janelas NEx num grade de posições (px do canto); posição sem janela no pulmão sai null."""
    case = images.case(wb, version, item)
    real = tools.nex_windows(case.original, case.lung_mask)
    synthetic = tools.nex_windows(case.synthetic, case.lung_mask)
    rows = sorted({w["row"] for w in real + synthetic})
    cols = sorted({w["col"] for w in real + synthetic})
    return {"rows": rows, "cols": cols,
            "panels": [{"label": "Real", "values": _grid(real, rows, cols)},
                       {"label": f"Synthetic · {label(version)}", "values": _grid(synthetic, rows, cols)}],
            "scale": {"label": f"NEx per {tools.TILE} px window"}}


def wavelet(wb: Workbench, item: str, version: str) -> dict:
    case = images.case(wb, version, item)
    ruler = context_from_dict(wb.history["calibration"]).ruler
    real = tools.wavelet_bands(tools.normalise(case.original, ruler), case.lung_mask)
    synthetic = tools.wavelet_bands(tools.normalise(case.synthetic, ruler), case.lung_mask)
    bars = [{"label": f"{r['band']} e{r['level']}",
             "value": tools.log2_ratio(tools.json_number(r["energy"]), tools.json_number(s["energy"]))}
            for r, s in zip(real, synthetic)]
    facts = item_json(data.slice_json(wb.row(version, item), wb.history["calibration"]))["facts"]
    kind = next((fact["value"] for fact in facts if fact["label"] == "Wavelet type"), None)
    return {"y": {"label": "log2(synthetic / real energy)"}, "zero": 0, "bars": bars,
            "note": f"Wavelet type: {kind}" if kind else None}


def _caption(descriptor: dict, options: dict) -> str:
    if descriptor["key"] == "figure":
        choice = next(c for c in descriptor["options"][0]["choices"] if c["key"] == options["technique"])
        return f"{choice['label']}. {choice['description']}" if choice.get("description") else choice["label"]
    if descriptor["key"] == "map":
        layer = next(c for c in descriptor["options"][0]["choices"] if c["key"] == options["layer"])
        return (f"{layer['label']} · " + ("compared with the original" if options["compared"] == "yes"
                                           else "each image on its own") + f". {descriptor['description']}")
    return descriptor.get("description") or descriptor["label"]


def image(descriptor: dict, dataset: str, version: str, item: str, compare: str | None, options: dict) -> dict:
    params = {"dataset": dataset, "version": version, "item": item}
    if compare:
        params["compare"] = compare
    params.update(options)
    return {"url": f"/api/inspect/{descriptor['key']}.png?{urlencode(params, quote_via=quote)}",
            "caption": _caption(descriptor, options)}


def png(wb: Workbench, key: str, item: str, names: list[str], options: dict) -> bytes:
    if key == "figure":
        return board.technique_png(wb, item, options["technique"], names)
    if key == "map":
        return board.map_png(wb, item, options["layer"], options["compared"] == "yes", names)
    return board.nps_png(wb, item, names)


def _data(wb: Workbench, key: str, item: str, version: str, compare: str | None) -> dict:
    label = _labeller(wb)
    if key == "spectrum":
        return spectrum(wb, item, _compare(wb, version, compare), label)
    if key == "glcm":
        return glcm(wb, item, version, label)
    if key == "nex":
        return nex(wb, item, version)
    if key == "nex_windows":
        return nex_windows(wb, item, version, label)
    return wavelet(wb, item, version)


def router(datasets: dict) -> APIRouter:
    api = APIRouter()

    @api.get("/api/inspect/{key}.png")
    def inspect_png(key: str, request: Request, version: str = Query(...), item: str = Query(...),
                    compare: str | None = Query(None), dataset: str = Query(ds.DEFAULT)):
        descriptor = _descriptor(key)
        if key not in IMAGE_KEYS:
            raise HTTPException(404, f"inspector {key} has no image")
        options = _options(descriptor, dict(request.query_params))
        wb = ds.wb_for(dataset, datasets)
        return Response(png(wb, key, item, _compare(wb, version, compare), options), media_type="image/png")

    @api.get("/api/inspect/{key}")
    def inspect(key: str, request: Request, version: str = Query(...), item: str = Query(...),
                compare: str | None = Query(None), dataset: str = Query(ds.DEFAULT)):
        descriptor = _descriptor(key)
        options = _options(descriptor, dict(request.query_params))
        wb = ds.wb_for(dataset, datasets)
        wb.entry(version)  # desconhecida: 404
        if key in IMAGE_KEYS:
            wb.row(version, item)  # corte desconhecido: 404 já no JSON, não só no PNG
            return image(descriptor, dataset, version, item, compare, options)
        try:
            return _data(wb, key, item, version, compare)
        except ValueError as exc:  # pulmão vazio ou pequeno demais para a medida (ex.: GLCM sem pares vizinhos)
            raise HTTPException(422, f"{descriptor['label']} cannot be measured on this slice: {exc}") from exc

    return api

