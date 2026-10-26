"""Placar de geradores, figuras do framework e administração de versões do workbench.

O placar vem do `placar.build_board` (cortes comuns a todas as versões). Os vereditos
por corte saem de `data.slice_json`, sem recalcular nada aqui. A comparação com a
referência usa `placar.compare` e os textos são os de `placar.change_label`, traduzidos
para o inglês da interface.
"""
from __future__ import annotations

import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # antes de qualquer import de pyplot (feito pelo framework de visual)

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from fastapi import APIRouter, HTTPException, Query  # noqa: E402
from fastapi.responses import Response  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from frameworks.texture_evaluator import placar  # noqa: E402
from frameworks.texture_evaluator.visual import MAP_LAYERS, TECHNIQUE_FIGURES, map_figure, technique_figure  # noqa: E402
from workbench.api import data, datasets as ds  # noqa: E402
from workbench.api.data import NotFound, Workbench  # noqa: E402
from workbench.api.datasets import DEFAULT  # noqa: E402
from workbench.api.nps_figure import nps_case_png  # noqa: E402

DPI = 120
STATUSES = ("approved", "review", "rejected", "inconclusive")
RESULT = {"melhorou": "improved", "piorou": "worse", "mudança pequena": "small change",
          "sem diferença clara": "no clear difference", "n/a": "n/a"}
# indicadores do placar que o workbench mostra, com rótulo em inglês; "final", "brilho" e "textura"
# (contagens) misturam brilho e textura ou não batem com os vereditos do workbench e ficam de fora
INDICATOR_LABEL = {
    "abs_delta_mu": "Brightness Δμ",
    "abs_delta_ll": "Wavelet LL",
    "nex": "NEx",
    "map_area_brilho_local_pct": "Map: brightness area",
    "wavelet_fine_pct": "Wavelet 2 px",
    "wavelet_coarse_pct": "Wavelet 4 px",
    "wavelet_ratio": "Wavelet 2 px ÷ 4 px",
    "glcm_contrast_pct": "GLCM contrast",
    "glcm_energy_pct": "GLCM energy",
    "map_area_textura_alterada_pct": "Map: texture area",
    "map_corr_textura": "Map: spatial correlation",
    "nps_abs_quantity_z": "NPS · quantity",
    "nps_abs_grain_z": "NPS · grain size",
    "nps_abs_low_band_z": "NPS · wide patterns",
    "nps_abs_high_band_z": "NPS · fine grain",
    "nps_air_synthetic": "Air spots",
    "nps_aprovada": "NPS · slices approved",
}
GROUP = {"brilho": "brightness", "textura": "texture", "ruido": "noise"}
# métricas com z que entram na mediana de brilho e textura; as do ruído têm campo próprio
BRIGHTNESS_TEXTURE = ("brightness", "texture")
class VersionIn(BaseModel):
    name: str | None = None  # padrão: nome da pasta
    folder: str


def _counts(rows: list[dict], calibration: dict, key: str) -> dict[str, int]:
    counts = {status: 0 for status in STATUSES}  # inconclusivo: hoje só o ruído o produz; sempre no formato
    for row in rows:
        verdict = data.slice_json(row, calibration)[key]["verdict"]
        if verdict in counts:
            counts[verdict] += 1
    return counts


def _median_abs_z(slices: list[dict], groups: tuple[str, ...]) -> dict[str, float | None]:
    """Mediana de |z| por métrica dos grupos pedidos; métrica sem z (sat31, nps_air) sai como null."""
    out: dict[str, float | None] = {}
    for index, metric in enumerate(slices[0]["metrics"]):
        if metric["group"] not in groups:
            continue
        zs = [abs(s["metrics"][index]["z"]) for s in slices if s["metrics"][index]["z"] is not None]
        out[metric["key"]] = placar.json_value(float(np.median(zs))) if zs else None
    return out


def _vs_baseline(baseline_rows: list[dict], rows: list[dict]) -> list[dict]:
    gains = placar.compare(baseline_rows, rows, np.random.default_rng(0))
    out = []
    for indicator in placar.INDICATORS:
        if indicator.key not in INDICATOR_LABEL:
            continue
        gain, low, high = gains[indicator.key]
        out.append({"indicator": indicator.key, "label": INDICATOR_LABEL[indicator.key], "group": GROUP[indicator.group],
                    "gain": placar.json_value(gain), "ci": [placar.json_value(low), placar.json_value(high)],
                    "result": RESULT[placar.change_label(gain, low, high, indicator)]})
    return out


def board_json(wb: Workbench, baseline: str | None = None) -> dict:
    """Placar com `baseline` como referência da comparação (padrão: a referência do histórico)."""
    board = wb.board
    baseline = baseline or wb.baseline
    wb.entry(baseline)  # desconhecida: 404
    rows_by_name = board["rows"]
    calibration = wb.history["calibration"]
    generators = []
    for name in board["names"]:
        rows = rows_by_name[name]
        slices = [data.slice_json(row, calibration) for row in rows]
        is_baseline = name == baseline
        scores = board["scores"][name]
        generators.append({
            "name": name,
            "mode": wb.entry(name)["mode"],
            "is_baseline": is_baseline,
            "counts": {"brightness": _counts(rows, calibration, "brightness"),
                       "texture": _counts(rows, calibration, "texture"),
                       "noise": _counts(rows, calibration, "noise")},
            "median_abs_z": _median_abs_z(slices, BRIGHTNESS_TEXTURE),
            "median_abs_z_noise": _median_abs_z(slices, ("noise",)),
            "scores": {key: placar.json_value(list(values)) for key, values in scores.items()},
            "vs_baseline": None if is_baseline else _vs_baseline(rows_by_name[baseline], rows),
        })
    return {"baseline": baseline, "n_cases": board["n_cases"], "generators": generators}


def _png(fig) -> bytes:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buffer.getvalue()


def _version_names(wb: Workbench, versions: str | None) -> list[str]:
    """Versões pedidas (lista separada por vírgula, na ordem pedida); vazio ou ausente: todas. Desconhecida: 404."""
    if versions is None or not versions.strip():
        return list(wb.board["names"])
    names = list(dict.fromkeys(item.strip() for item in versions.split(",") if item.strip()))
    for name in names:
        wb.entry(name)  # desconhecida: 404
    return names or list(wb.board["names"])  # só vírgulas: como se não tivesse sido pedido


def _case_rows(wb: Workbench, case_id: str, names: list[str] | None = None) -> dict[str, dict]:
    """Linha do corte em cada versão pedida (padrão: todas do placar); corte fora dos cortes comuns é 404."""
    rows = {}
    for name in names if names is not None else wb.board["names"]:
        match = next((row for row in wb.board["rows"][name] if row["case_id"] == case_id), None)
        if match is None:
            raise NotFound(f"slice not found: {case_id}")
        rows[name] = match
    return rows


def router(datasets: dict) -> APIRouter:
    api = APIRouter()

    def _wb(dataset: str) -> Workbench:
        return ds.wb_for(dataset, datasets)

    @api.get("/api/board")
    def board(dataset: str = Query(DEFAULT), baseline: str | None = Query(None)):
        return board_json(_wb(dataset), baseline)

    @api.get("/api/figure/{case_id}/technique/{technique}.png")
    def technique(case_id: str, technique: str, dataset: str = Query(DEFAULT), versions: str | None = Query(None)):
        if technique not in TECHNIQUE_FIGURES:
            raise NotFound(f"unknown technique: {technique}")
        wb = _wb(dataset)
        names = _version_names(wb, versions)
        fig = technique_figure(wb.history_dir, case_id, technique, _case_rows(wb, case_id, names))
        return _response(fig)

    @api.get("/api/figure/{case_id}/map/{layer}.png")
    def map_png(case_id: str, layer: str, compared: bool = False, dataset: str = Query(DEFAULT),
                versions: str | None = Query(None)):
        if layer not in MAP_LAYERS:
            raise NotFound(f"unknown layer: {layer}")
        if layer == "veredito" and not compared:
            raise HTTPException(400, "the verdict layer exists only compared with the original")
        wb = _wb(dataset)  # histórico ausente: 404
        names = _version_names(wb, versions)
        _case_rows(wb, case_id, names)  # corte desconhecido: 404
        fig = map_figure(wb.history_dir, case_id, layer, compared, version_names=names)
        return _response(fig)

    @api.get("/api/figure/{case_id}/nps.png")
    def nps(case_id: str, dataset: str = Query(DEFAULT), versions: str | None = Query(None)):
        """NPS e teste do ar de um corte.

        `versions` tem uma ou duas versões, sem repetir nomes: a primeira é a referência e a última a comparada.
        Clientes devem sempre passar `versions=<referência>,<comparada>`: sem isso a figura compara a referência
        da linha de base com a última versão do histórico, e a figura muda quando uma versão entra ou sai.
        Respostas: 400 para nomes repetidos ou mais de duas versões; 404 para versão ou corte desconhecido e
        para corte que não pode ser carregado.
        """
        wb = _wb(dataset)
        requested = [item.strip() for item in (versions or "").split(",") if item.strip()]
        repeated = sorted({name for name in requested if requested.count(name) > 1})
        if repeated:
            raise HTTPException(400, f"duplicate version in versions=: {', '.join(repeated)}")
        for name in requested:
            wb.entry(name)  # desconhecida: 404
        if len(requested) > 2:
            raise HTTPException(400, "the NPS figure compares at most two versions: reference and compared")
        if not requested:
            names = [wb.baseline, wb.history["versions"][-1]["name"]]
        else:
            names = [wb.baseline, requested[0]] if len(requested) == 1 else requested
        _case_rows(wb, case_id, names)  # corte desconhecido: 404
        try:
            png = nps_case_png(wb.history, case_id, names[0], names[1])
        except placar.PlacarError as exc:  # corte que não pode ser carregado nas versões pedidas
            raise HTTPException(404, f"slice could not be loaded: {case_id}") from exc
        return Response(png, media_type="image/png")

    @api.post("/api/versions")
    def add_version(body: VersionIn, dataset: str = Query(DEFAULT)):
        cfg = ds.config(datasets, dataset)
        history_dir = Path(cfg["history"])
        folder = Path(body.folder).expanduser()
        if not folder.is_dir():
            raise HTTPException(400, f"version folder not found: {folder}")
        name = (body.name or "").strip() or folder.resolve().name
        if not ds.NAME_PATTERN.fullmatch(name):
            raise HTTPException(400, "invalid name: use only letters, digits, dot, hyphen and underscore")
        with ds.ADMIN_LOCK:
            history = placar.load_history(history_dir)
            if history is None or not history.get("versions"):
                raise HTTPException(400, f"{dataset} has not been evaluated yet: use POST /api/datasets/{dataset}/init")
            resolved = folder.resolve()
            if any(Path(item["folder"]).resolve() == resolved for item in history["versions"]):
                raise HTTPException(400, f"this run is already in the history: {folder.name}")
            target = placar.rows_path(history_dir, name)
            if any(placar.rows_path(history_dir, item["name"]) == target for item in history["versions"]):
                raise HTTPException(400, f"the name {name!r} would use the same file as another version")
            try:
                ds.validate_complete_version(folder, history)
                message = placar.add_version(history_dir, name, folder, Path(cfg["masks"]))
                placar.write_outputs(history_dir, placar.build_board(history_dir))
            except (placar.PlacarError, FileNotFoundError, NotADirectoryError, ValueError) as exc:
                raise HTTPException(400, str(exc)) from exc
        return {"message": message, "name": name}

    @api.delete("/api/versions/{name}")
    def remove_version(name: str, dataset: str = Query(DEFAULT)):
        cfg = ds.config(datasets, dataset)
        wb = _wb(dataset)
        wb.entry(name)  # desconhecida: 404
        if name == wb.baseline:
            raise HTTPException(400, "the reference version cannot be removed")
        with ds.ADMIN_LOCK:
            try:
                placar.remove_version(Path(cfg["history"]), name)
                placar.write_outputs(Path(cfg["history"]), placar.build_board(Path(cfg["history"])))
            except (placar.PlacarError, FileNotFoundError, NotADirectoryError, ValueError) as exc:
                raise HTTPException(400, str(exc)) from exc
        return {"message": f"version removed: {name}"}

    @api.post("/api/refresh")
    def refresh(dataset: str = Query(DEFAULT)):
        history_dir = Path(ds.config(datasets, dataset)["history"])
        if ds.load_state(history_dir) is None:  # sem histórico não há versão para recalcular: 404, não 400
            raise HTTPException(404, f"dataset has no history: {dataset}")
        with ds.ADMIN_LOCK:
            try:
                message = placar.refresh_history(history_dir)
                placar.write_outputs(history_dir, placar.build_board(history_dir))
            except (placar.PlacarError, FileNotFoundError, NotADirectoryError, StopIteration, ValueError) as exc:
                raise HTTPException(400, str(exc) or type(exc).__name__) from exc
        return {"message": message}

    return api


def _response(fig) -> Response:
    # sem cache: a figura muda quando uma versão entra ou sai
    return Response(_png(fig), media_type="image/png")
