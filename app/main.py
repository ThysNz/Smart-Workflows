from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import storage
from .models import (
    Reorder, Step, StepIn, StepPatch, Workflow, WorkflowIn, WorkflowPatch, WorkflowSummary,
)

app = FastAPI(
    title="Smart Workflows",
    description="Document workflows as ordered steps with paths, CLI commands, images and diagrams.",
)

STATIC = Path(__file__).resolve().parent.parent / "static"
MAX_UPLOAD = 20 * 1024 * 1024


@app.exception_handler(storage.NotFound)
async def _nf(_, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail": f"not found: {exc}"}, status_code=404)


@app.exception_handler(storage.Conflict)
async def _conflict(_, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail": str(exc)}, status_code=409)


# ---- workflows -------------------------------------------------------------

@app.get("/api/workflows", response_model=list[WorkflowSummary])
def list_workflows():
    return storage.list_workflows()


@app.post("/api/workflows", response_model=Workflow, status_code=201)
def create_workflow(body: WorkflowIn):
    return storage.create_workflow(body)


@app.get("/api/workflows/{slug}", response_model=Workflow)
def get_workflow(slug: str):
    return storage.get_workflow(slug)


@app.patch("/api/workflows/{slug}", response_model=Workflow)
def update_workflow(slug: str, body: WorkflowPatch):
    return storage.update_workflow(slug, body)


@app.delete("/api/workflows/{slug}", status_code=204)
def delete_workflow(slug: str):
    storage.delete_workflow(slug)


# ---- steps -----------------------------------------------------------------

@app.post("/api/workflows/{slug}/steps", response_model=Step, status_code=201)
def add_step(slug: str, body: StepIn, position: int | None = None):
    return storage.add_step(slug, body, position)


@app.patch("/api/workflows/{slug}/steps/{step_id}", response_model=Step)
def update_step(slug: str, step_id: str, body: StepPatch):
    return storage.update_step(slug, step_id, body)


@app.delete("/api/workflows/{slug}/steps/{step_id}", status_code=204)
def delete_step(slug: str, step_id: str):
    storage.delete_step(slug, step_id)


@app.put("/api/workflows/{slug}/order", response_model=Workflow)
def reorder(slug: str, body: Reorder):
    return storage.reorder_steps(slug, body)


# ---- assets & search -------------------------------------------------------

@app.post("/api/workflows/{slug}/assets", status_code=201)
async def upload_asset(slug: str, file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "file too large (20 MB max)")
    name = storage.save_asset(slug, file.filename or "image.png", data)
    return {"file": name, "url": f"/assets/{slug}/{name}"}


@app.get("/assets/{slug}/{name}")
def get_asset(slug: str, name: str):
    p = (storage.assets_dir(slug) / name).resolve()
    if storage.assets_dir(slug).resolve() not in p.parents or not p.is_file():
        raise HTTPException(404, "asset not found")
    return FileResponse(p)


@app.get("/api/search")
def search(q: str):
    return storage.search(q)


# ---- UI --------------------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
