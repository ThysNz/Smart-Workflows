"""File-backed storage: one folder per workflow, workflow.json + assets/."""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .models import (
    Image,
    Reorder,
    Step,
    StepIn,
    StepPatch,
    Workflow,
    WorkflowIn,
    WorkflowPatch,
    WorkflowSummary,
)

DATA_DIR = Path(os.environ.get("WORKFLOWS_DATA", Path(__file__).resolve().parent.parent / "data"))
WF_DIR = DATA_DIR / "workflows"
WF_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.RLock()


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "workflow"


def _dir(slug: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        raise NotFound(slug)
    return WF_DIR / slug


def assets_dir(slug: str) -> Path:
    return _dir(slug) / "assets"


def _load(slug: str) -> Workflow:
    f = _dir(slug) / "workflow.json"
    if not f.exists():
        raise NotFound(slug)
    return Workflow.model_validate_json(f.read_text(encoding="utf-8"))


def _save(wf: Workflow) -> Workflow:
    wf.updated = _now()
    d = _dir(wf.slug)
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "workflow.json.tmp"
    tmp.write_text(wf.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(d / "workflow.json")  # atomic swap
    return wf


# ---- workflows -------------------------------------------------------------

def list_workflows() -> list[WorkflowSummary]:
    out = []
    with _lock:
        for d in sorted(WF_DIR.iterdir()):
            if (d / "workflow.json").exists():
                wf = _load(d.name)
                out.append(
                    WorkflowSummary(
                        slug=wf.slug, title=wf.title, description=wf.description,
                        tags=wf.tags, step_count=len(wf.steps), updated=wf.updated,
                    )
                )
    return sorted(out, key=lambda w: w.updated, reverse=True)


def create_workflow(data: WorkflowIn) -> Workflow:
    with _lock:
        base = slugify(data.title)
        slug, n = base, 2
        while (WF_DIR / slug).exists():
            slug, n = f"{base}-{n}", n + 1
        now = _now()
        return _save(Workflow(slug=slug, created=now, updated=now, **data.model_dump()))


def get_workflow(slug: str) -> Workflow:
    with _lock:
        return _load(slug)


def update_workflow(slug: str, patch: WorkflowPatch) -> Workflow:
    with _lock:
        wf = _load(slug)
        for k, v in patch.model_dump(exclude_none=True).items():
            setattr(wf, k, v)
        return _save(wf)


def delete_workflow(slug: str) -> None:
    with _lock:
        d = _dir(slug)
        if not (d / "workflow.json").exists():
            raise NotFound(slug)
        shutil.rmtree(d)


# ---- steps -----------------------------------------------------------------

def _find(wf: Workflow, step_id: str) -> int:
    for i, s in enumerate(wf.steps):
        if s.id == step_id:
            return i
    raise NotFound(step_id)


def add_step(slug: str, data: StepIn, position: int | None = None) -> Step:
    with _lock:
        wf = _load(slug)
        step = Step(id=uuid.uuid4().hex[:8], **data.model_dump())
        if position is None or position >= len(wf.steps):
            wf.steps.append(step)
        else:
            wf.steps.insert(max(position, 0), step)
        _save(wf)
        return step


def update_step(slug: str, step_id: str, patch: StepPatch) -> Step:
    with _lock:
        wf = _load(slug)
        i = _find(wf, step_id)
        merged = wf.steps[i].model_dump()
        merged.update(patch.model_dump(exclude_none=True))
        wf.steps[i] = Step.model_validate(merged)
        _save(wf)
        return wf.steps[i]


def delete_step(slug: str, step_id: str) -> None:
    with _lock:
        wf = _load(slug)
        del wf.steps[_find(wf, step_id)]
        _save(wf)


def reorder_steps(slug: str, r: Reorder) -> Workflow:
    with _lock:
        wf = _load(slug)
        if sorted(r.order) != sorted(s.id for s in wf.steps):
            raise Conflict("order must contain every step id exactly once")
        by_id = {s.id: s for s in wf.steps}
        wf.steps = [by_id[i] for i in r.order]
        return _save(wf)


# ---- assets ----------------------------------------------------------------

def save_asset(slug: str, filename: str, data: bytes) -> str:
    with _lock:
        _load(slug)  # must exist
        d = assets_dir(slug)
        d.mkdir(exist_ok=True)
        stem = slugify(Path(filename).stem)
        ext = re.sub(r"[^a-z0-9.]", "", Path(filename).suffix.lower()) or ".png"
        name = f"{stem}{ext}"
        n = 2
        while (d / name).exists():
            name, n = f"{stem}-{n}{ext}", n + 1
        (d / name).write_bytes(data)
        return name


def add_image(slug: str, step_id: str, filename: str, data: bytes, caption: str = "") -> Step:
    """Save an image into the workflow's assets and attach it to a step."""
    with _lock:
        wf = _load(slug)
        i = _find(wf, step_id)
        name = save_asset(slug, filename, data)
        wf.steps[i].images.append(Image(file=name, caption=caption))
        _save(wf)
        return wf.steps[i]


def remove_image(slug: str, step_id: str, file: str, delete_file: bool = True) -> Step:
    with _lock:
        wf = _load(slug)
        i = _find(wf, step_id)
        wf.steps[i].images = [im for im in wf.steps[i].images if im.file != file]
        still_used = any(im.file == file for s in wf.steps for im in s.images)
        if delete_file and not still_used:
            (assets_dir(slug) / Path(file).name).unlink(missing_ok=True)
        _save(wf)
        return wf.steps[i]


# ---- search ----------------------------------------------------------------

def search(q: str) -> list[dict]:
    q = q.lower().strip()
    hits = []
    if not q:
        return hits
    with _lock:
        for summary in list_workflows():
            wf = _load(summary.slug)
            if q in (wf.title + " " + wf.description).lower():
                hits.append({"workflow": wf.slug, "step": None, "title": wf.title, "match": "workflow"})
            for s in wf.steps:
                fields = {
                    "title": s.title,
                    "description": s.description,
                    "path": " ".join(p.path for p in s.paths),
                    "command": " ".join(c.cmd for c in s.commands),
                    "notes": s.notes,
                }
                for field, text in fields.items():
                    if q in text.lower():
                        hits.append({"workflow": wf.slug, "step": s.id, "title": s.title, "match": field})
                        break
    return hits
