"""Read-only stress fixture API for `bash workbench/dev.sh --stress`.

Only serves the checked-in bundle; no access to real history or administration.
Blank fixture images are represented by an explicitly labelled placeholder.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response

ROOT = Path(__file__).resolve().parents[3]
BUNDLE = json.loads((ROOT / "workbench/web/src/fixtures/stress.json").read_text())
app = FastAPI()


@app.get("/mockups/{kind}")
def mockup(kind: str):
    if kind not in ("real", "stress"):
        raise HTTPException(404)
    return FileResponse(ROOT / f"docs/planning/2026-10-27-workbench-mockups-v3-{kind}.html")


@app.get("/api/{path:path}")
def fixture(path: str, request: Request):
    b, params = BUNDLE, request.query_params
    if path == "status":
        return {"stale": False, "has_history": True, "baseline": b["baseline"], "token": 1}
    if path == "schema":
        return b["schema"]
    if path == "datasets":
        return b["schema"]["datasets"]
    if path == "versions":
        return b["versions"]
    if path == "versions/detected":
        return b["detected"]
    if path == "items":
        version = params.get("version", b["current"])
        if version not in b["items"]:
            raise HTTPException(404, "unknown fixture version")
        return {"version": version, "items": b["items"][version]}
    if path == "board":
        if params.get("baseline", b["baseline"]) != b["baseline"]:
            raise HTTPException(400, "fixture board only supports the bundled baseline")
        return b["board"]
    if path == "transitions":
        return b["transitions"].get(params.get("axis"), [])
    if path in ("runs", "experiments"):
        return b[path]
    if path.startswith("image/") or path.startswith("inspect/") and path.endswith(".png"):
        return Response('<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512">'
                        '<rect width="512" height="512" fill="#161616"/>'
                        '<text x="256" y="256" fill="#aaa" text-anchor="middle" font-size="24">'
                        'Fixture image</text></svg>', media_type="image/svg+xml")
    if path.startswith("inspect/"):
        key = path.removeprefix("inspect/")
        if key in b["inspect"]:
            return b["inspect"][key]
        raise HTTPException(404, "unknown fixture inspector")
    raise HTTPException(404, "not available in the read-only stress fixture")
