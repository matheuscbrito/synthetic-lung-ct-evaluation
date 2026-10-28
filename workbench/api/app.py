"""API FastAPI do QC workbench, sobre o histórico do placar do avaliador de textura.

Toda rota de dados aceita `dataset` (Dsr por padrão, Dgen); dataset desconhecido é 404.
"""
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, Response

from frameworks.texture_evaluator.placar import PlacarError
from workbench.api import board, contract, datasets as ds, images
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

    @app.get("/api/image/{version}/{case_id}/{kind}.png")
    def image(version: str, case_id: str, kind: str, size: int | None = Query(None, ge=1, le=2048),
              window: Literal["pair", "reference"] = "pair", dataset: str = Query(DEFAULT)):
        case = images.case(_wb(dataset), version, case_id)
        return Response(images.render(case, kind, size, window == "reference"), media_type="image/png",
                        headers={"Cache-Control": "max-age=3600"})

    app.include_router(board.router(datasets))
    app.include_router(ds.router(datasets))
    contract.include(app, datasets)

    return app


app = create_app()
