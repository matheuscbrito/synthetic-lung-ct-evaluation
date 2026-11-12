"""Inspetores do contrato genérico (§4.2): `GET /api/inspect/{key}?dataset=&version=&item=&compare=`.

Cada inspetor de `schema.inspectors()` vira um payload por tipo de gráfico, sem nome de métrica na forma:
- `spectrum` (curves), `glcm` e `nex_windows` (matrix), `nex` (interval) e `wavelet` (bars) saem das
  funções de `tools` (as antigas rotas `/api/tools/*` foram removidas);
- `noise_figure` (assessment) junta vereditos, espectros e uma imagem da região medida.
- `figure` e `map` (image) devolvem `{url, caption}`; a URL aponta para
  `GET /api/inspect/{key}.png`, que desenha com `board.technique_png`, `board.map_png` e `board.nps_png`.
Séries e painéis são rotulados pelo rótulo de exibição da versão (`versions.version_label`), nunca pela pasta.
Opções fora das `choices` do schema são 400; inspetor desconhecido é 404.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from urllib.parse import quote, urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from frameworks.noise_evaluator import masked_nps
from frameworks.noise_evaluator.integration import MASKED_CONFIG

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
IMAGE_KEYS = ("figure", "map", "noise_figure", "fine_detail", "coarse_detail")


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
    if key in ("fine_detail", "coarse_detail"):
        return board.technique_png(wb, item, {"fine_detail": "wavelet_fina", "coarse_detail": "wavelet_grossa"}[key], names)
    if key == "figure":
        return board.technique_png(wb, item, options["technique"], names)
    if key == "map":
        return board.map_png(wb, item, options["layer"], options["compared"] == "yes", names)
    return board.nps_png(wb, item, names)


NOISE_ROWS = {
    "quantity": ("Grain strength", "How strong the fluctuations are", "stronger grain", "weaker grain", 3, ""),
    "grain": ("Mean frequency", "Higher frequency means finer grain", "finer grain", "coarser grain", 3, " cycles/px"),
    "high_band": ("Fine-grain share", "Power at 0.30 cycles/pixel and above", "more fine grain", "less fine grain", 1, "%"),
}


def _noise_assessment(wb: Workbench, item: str, name: str, label) -> dict:
    row = wb.row(name, item)
    reference = wb.history["calibration"].get("nps_reference", {})
    result = {"label": label(name), "verdict": "inconclusive", "summary": "", "readings": []}
    if reference.get("config") != MASKED_CONFIG:
        return {**result, "summary": "Refresh the evaluation to calculate the masked noise results."}
    body = data.slice_json(row, wb.history["calibration"])
    result["verdict"] = body["noise"]["verdict"]
    if result["verdict"] == "inconclusive":
        return {**result, "summary": row.get("nps_error") or "Noise could not be measured in this slice."}
    by_key = {m["key"]: m for m in body["metrics"]}
    for key, (title, explanation, above, below, digits, unit) in NOISE_ROWS.items():
        m = by_key[f"nps_{key}"]
        scale = 100 if unit == "%" else 1
        z = m["z"]
        real, synthetic = m["real"], m["synthetic"]
        if unit == "%":
            change = f"{100 * (synthetic - real):+.1f} pp"
        elif real:
            change = f"{100 * (synthetic / real - 1):+.1f}%"
        else:
            change = "—"
        result["readings"].append({
            "label": title, "description": explanation, "status": m["status"],
            "original": f"{scale * real:.{digits}f}{unit}", "synthetic": f"{scale * synthetic:.{digits}f}{unit}",
            "change": change, "distance": z, "direction": above if z > 0 else below if z < 0 else "equal",
        })
    drivers = [r for r in result["readings"] if r["status"] == result["verdict"]]
    if result["verdict"] == "approved":
        result["summary"] = "All three readings are within 1 IQR of the original."
    else:
        phrases = [f"{r['label']} shows {r['direction']} ({abs(r['distance']):.2f} IQR from the original)"
                   for r in drivers]
        result["summary"] = ". ".join(phrases) + "."
    return result


def noise_report(wb: Workbench, dataset: str, item: str, version: str, names: list[str]) -> dict:
    if len(names) > 2:
        raise HTTPException(400, "select at most two versions")
    names = sorted(names, key=lambda name: name != version)
    label = _labeller(wb)
    assessments = [_noise_assessment(wb, item, name, label) for name in names]
    measured = [name for name, result in zip(names, assessments) if result["verdict"] != "inconclusive"]
    curve = broad_curve = overlay = None
    if measured:
        cases = [images.case(wb, name, item) for name in measured]
        comparisons = [masked_nps.measure(c.original, c.lung_mask, c.synthetic) for c in cases]
        geometry, freq, first_profiles = comparisons[0]
        profiles = [first_profiles[0], *(p[1] for _, _, p in comparisons)]

        def spectrum_band(band):
            return {"x": {"label": "Spatial frequency (cycles/pixel)"}, "y": {"label": "Noise power", "scale": "linear"},
                    "band": None, "markers": [],
                    "series": [{"label": name, "role": role, "x": freq[band].tolist(), "y": profile[band].tolist()}
                               for name, role, profile in zip(["Original", *(label(n) for n in measured)],
                                                              ["real", *["version"] * len(measured)], profiles)]}
        curve = spectrum_band(freq >= masked_nps.GRAIN)
        broad_curve = spectrum_band((freq >= masked_nps.LOW) & (freq < masked_nps.GRAIN))
        query = urlencode({"dataset": dataset, "version": measured[0], "item": item}, quote_via=quote)
        height, width = geometry.used.shape
        overlay = {"url": f"/api/inspect/noise_figure.png?{query}",
                   "caption": "The outlined blocks met the soft-tissue coverage requirement. Green shows the pixels used in the calculation.",
                   "width": width, "height": height, "block_size": masked_nps.TILE,
                   "min_coverage": masked_nps.MIN_COVER,
                   "pixel_count": int(geometry.used.sum()),
                   "blocks": [asdict(block) for block in geometry.blocks]}
    return {"assessments": assessments, "curve": curve, "broad_curve": broad_curve, "overlay": overlay,
            "limits": dict(reasons.Z_LIMITS),
            "rule": "Approved ≤ 1 IQR · Review > 1 to 2 IQR · Rejected > 2 IQR. "
                    "IQR is the spread of the middle half of the original readings. These are project triage limits.",
            "curve_title": "Grain spectrum",
            "curve_hint": "Read left to right from coarser to finer grain. The height shows noise power.",
            "details_title": "Broad patterns",
            "details_hint": "Below 0.125 cycles/pixel, anatomy can dominate the curve, so this band stays outside the verdict."}


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
        if key == "noise_figure" and request.query_params.get("method", "masked") != "masked":
            raise HTTPException(400, "only the masked method is available")
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
        if key == "noise_figure":
            if request.query_params.get("method", "masked") != "masked":
                raise HTTPException(400, "only the masked method is available")
            names = _compare(wb, version, compare)
            try:
                return noise_report(wb, dataset, item, version, names)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
        if key in IMAGE_KEYS:
            wb.row(version, item)  # corte desconhecido: 404 já no JSON, não só no PNG
            return image(descriptor, dataset, version, item, compare, options)
        try:
            return _data(wb, key, item, version, compare)
        except ValueError as exc:  # pulmão vazio ou pequeno demais para a medida (ex.: GLCM sem pares vizinhos)
            raise HTTPException(422, f"{descriptor['label']} cannot be measured on this slice: {exc}") from exc

    return api

