"""API FastAPI do QC workbench, sobre o histórico do placar do avaliador de textura.

Toda rota de dados aceita `dataset` (Dsr por padrão, Dgen); dataset desconhecido é 404.
"""
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, Response

from frameworks.texture_evaluator.placar import PlacarError
from frameworks.texture_evaluator.run_mvp import context_from_dict
from workbench.api import board, data, datasets as ds, images, notebook, optimizers, tools
from workbench.api.data import NotFound
from workbench.api.datasets import DATASETS, DEFAULT


def create_app(datasets: dict | Path = DATASETS) -> FastAPI:
    """`datasets` é o mapa de datasets; uma única pasta de histórico (Path) vale como o dataset Dsr."""
    datasets = ds.normalise(datasets)
    app = FastAPI(title="QC workbench")

    @app.exception_handler(NotFound)
    async def not_found(request, exc: NotFound):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(PlacarError)
    async def broken_history(request, exc: PlacarError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    def _wb(dataset: str):
        return ds.wb_for(dataset, datasets)

    @app.get("/api/status")
    def status(dataset: str = Query(DEFAULT)):
        return ds.status_json(ds.config(datasets, dataset))

    @app.get("/api/versions")
    def versions(dataset: str = Query(DEFAULT)):
        return data.versions_json(_wb(dataset))

    @app.get("/api/slices")
    def slices(version: str = Query(...), dataset: str = Query(DEFAULT)):
        wb = _wb(dataset)
        rows = wb.rows(version)
        calibration = wb.history["calibration"]
        return {"version": version, "n_cases": len(rows),
                "slices": [data.slice_json(row, calibration) for row in rows]}

    @app.get("/api/image/{version}/{case_id}/{kind}.png")
    def image(version: str, case_id: str, kind: str, size: int | None = Query(None, ge=1, le=2048),
              window: Literal["pair", "reference"] = "pair", dataset: str = Query(DEFAULT)):
        case = images.case(_wb(dataset), version, case_id)
        return Response(images.render(case, kind, size, window == "reference"), media_type="image/png",
                        headers={"Cache-Control": "max-age=3600"})

    def _tool_case(version: str, case_id: str, dataset: str):
        wb = _wb(dataset)
        return wb, images.case(wb, version, case_id)

    @app.get("/api/tools/{version}/{case_id}/spectrum")
    def tool_spectrum(version: str, case_id: str, dataset: str = Query(DEFAULT)):
        wb, case = _tool_case(version, case_id, dataset)
        ruler = context_from_dict(wb.history["calibration"]).ruler
        freq, real = tools.radial_spectrum(tools.normalise(case.original, ruler), case.lung_mask)
        _, synthetic = tools.radial_spectrum(tools.normalise(case.synthetic, ruler), case.lung_mask)
        band = tools.reference_band(wb)
        return {"freq": freq, "real": real, "synthetic": synthetic, "ref_p5": band["p5"], "ref_p95": band["p95"], "nyquist": 0.5}

    @app.get("/api/tools/{version}/{case_id}/glcm")
    def tool_glcm(version: str, case_id: str, dataset: str = Query(DEFAULT)):
        wb, case = _tool_case(version, case_id, dataset)
        scale = context_from_dict(wb.history["calibration"]).scale
        return {"levels": scale.levels,
                "real": tools.glcm_matrix(case.original, case.lung_mask, scale),
                "synthetic": tools.glcm_matrix(case.synthetic, case.lung_mask, scale),
                "tones": {"real": tools.tone_shares(case.original, case.lung_mask, scale),
                          "synthetic": tools.tone_shares(case.synthetic, case.lung_mask, scale)}}

    @app.get("/api/tools/{version}/{case_id}/nex")
    def tool_nex(version: str, case_id: str, dataset: str = Query(DEFAULT)):
        wb, case = _tool_case(version, case_id, dataset)
        row = wb.row(version, case_id)
        band = wb.history["calibration"].get("nex_reference") or {}
        windows = [{"row": w["row"], "col": w["col"], "value": tools.json_number(w["value"])}
                   for w in tools.nex_windows(case.original, case.lung_mask)]
        synthetic = [{"row": w["row"], "col": w["col"], "value": tools.json_number(w["value"])}
                     for w in tools.nex_windows(case.synthetic, case.lung_mask)]
        return {"real": windows, "synthetic": synthetic, "tile": tools.TILE,
                "value_real": tools.json_number(row["nex_real"]), "value_synthetic": tools.json_number(row["nex_synthetic"]),
                "p5": tools.json_number(band.get("p5")), "p95": tools.json_number(band.get("p95"))}

    @app.get("/api/tools/{version}/{case_id}/wavelet")
    def tool_wavelet(version: str, case_id: str, dataset: str = Query(DEFAULT)):
        wb, case = _tool_case(version, case_id, dataset)
        row = wb.row(version, case_id)
        ruler = context_from_dict(wb.history["calibration"]).ruler
        real = tools.wavelet_bands(tools.normalise(case.original, ruler), case.lung_mask)
        synthetic = tools.wavelet_bands(tools.normalise(case.synthetic, ruler), case.lung_mask)
        bands = [{"level": r["level"], "band": r["band"], "real": tools.json_number(r["energy"]),
                  "synthetic": tools.json_number(s["energy"]),
                  "log2_ratio": tools.log2_ratio(tools.json_number(r["energy"]), tools.json_number(s["energy"]))}
                 for r, s in zip(real, synthetic)]
        return {"bands": bands, "type": row["wavelet_verdict"]}

    @app.get("/api/agent/notebook")
    def agent_notebook():
        return notebook.read_caderno(notebook.LAB_DIR)

    app.include_router(board.router(datasets))
    app.include_router(ds.router(datasets))
    app.include_router(optimizers.router)

    return app


app = create_app()
