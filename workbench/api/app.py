"""API FastAPI do QC workbench, sobre o histórico do placar do avaliador de textura."""
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from frameworks.texture_evaluator.placar import PlacarError
from workbench.api import data
from workbench.api.data import HISTORY_DIR, NotFound


def create_app(history_dir: Path = HISTORY_DIR) -> FastAPI:
    app = FastAPI(title="QC workbench")

    @app.exception_handler(NotFound)
    async def not_found(request, exc: NotFound):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(PlacarError)
    async def broken_history(request, exc: PlacarError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.get("/api/status")
    def status():
        try:
            wb = data.load(history_dir)
        except NotFound:
            return {"stale": False, "has_history": False, "baseline": None}
        return {"stale": data.is_stale(wb.history), "has_history": True, "baseline": wb.baseline}

    @app.get("/api/versions")
    def versions():
        return data.versions_json(data.load(history_dir))

    @app.get("/api/slices")
    def slices(version: str = Query(...)):
        wb = data.load(history_dir)
        rows = wb.rows(version)
        calibration = wb.history["calibration"]
        return {"version": version, "n_cases": len(rows),
                "slices": [data.slice_json(row, calibration) for row in rows]}

    return app


app = create_app()
