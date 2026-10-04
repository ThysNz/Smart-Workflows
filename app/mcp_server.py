"""MCP server so an AI model can read and edit workflows.

Talks to the storage layer directly (same data folder as the web app), so the
web UI does not need to be running. Run with:  python -m app.mcp_server
"""
from __future__ import annotations

import base64
import urllib.parse
import urllib.request
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import storage
from .models import Reorder, StepIn, StepPatch, WorkflowIn, WorkflowPatch

mcp = FastMCP("smart-workflows")


@mcp.tool()
def list_workflows() -> list[dict]:
    """List all workflows (slug, title, description, tags, step_count)."""
    return [w.model_dump() for w in storage.list_workflows()]


@mcp.tool()
def get_workflow(slug: str) -> dict:
    """Get a full workflow including all steps and their ids."""
    return storage.get_workflow(slug).model_dump()


@mcp.tool()
def create_workflow(title: str, description: str = "", tags: list[str] | None = None, diagram: str = "") -> dict:
    """Create a workflow. `diagram` is optional Mermaid source for an overview."""
    return storage.create_workflow(
        WorkflowIn(title=title, description=description, tags=tags or [], diagram=diagram)
    ).model_dump()


@mcp.tool()
def update_workflow(slug: str, title: str | None = None, description: str | None = None,
                    tags: list[str] | None = None, diagram: str | None = None) -> dict:
    """Update workflow-level fields. Omitted fields are left unchanged."""
    return storage.update_workflow(
        slug, WorkflowPatch(title=title, description=description, tags=tags, diagram=diagram)
    ).model_dump()


@mcp.tool()
def delete_workflow(slug: str) -> str:
    """Permanently delete a workflow and its images."""
    storage.delete_workflow(slug)
    return "deleted"


@mcp.tool()
def add_step(slug: str, step: StepIn, position: int | None = None) -> dict:
    """Add a step. `position` is a 0-based index; omit to append.

    step fields: title, description (Markdown), paths [{path, note}],
    commands [{cmd, shell, cwd, note}], diagram (Mermaid), status
    (todo|in-progress|done|blocked), notes (Markdown), tags.
    """
    return storage.add_step(slug, step, position).model_dump()


@mcp.tool()
def update_step(slug: str, step_id: str, patch: StepPatch) -> dict:
    """Partially update a step. Only provided fields change; lists are replaced whole."""
    return storage.update_step(slug, step_id, patch).model_dump()


@mcp.tool()
def delete_step(slug: str, step_id: str) -> str:
    """Delete a step."""
    storage.delete_step(slug, step_id)
    return "deleted"


@mcp.tool()
def reorder_steps(slug: str, order: list[str]) -> dict:
    """Reorder steps. `order` must list every step id exactly once."""
    return storage.reorder_steps(slug, Reorder(order=order)).model_dump()


MAX_IMAGE = 20 * 1024 * 1024


@mcp.tool()
def add_image(slug: str, step_id: str, caption: str = "", filename: str = "image.png",
              data_base64: str | None = None, url: str | None = None) -> dict:
    """Attach an image to a step. Provide exactly one of:

    - `data_base64`: the image bytes, base64-encoded (use `filename` for the name/extension)
    - `url`: an http(s) URL the server will download

    The server runs in a container and cannot read host file paths.
    """
    if bool(data_base64) == bool(url):
        raise ValueError("provide exactly one of data_base64 or url")
    if data_base64:
        data = base64.b64decode(data_base64.split(",", 1)[-1], validate=False)
    else:
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError("url must be http(s)")
        req = urllib.request.Request(url, headers={"User-Agent": "smart-workflows"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read(MAX_IMAGE + 1)
        if filename == "image.png":
            filename = Path(urllib.parse.urlparse(url).path).name or filename
    if len(data) > MAX_IMAGE:
        raise ValueError("image too large (20 MB max)")
    return storage.add_image(slug, step_id, filename, data, caption).model_dump()


@mcp.tool()
def remove_image(slug: str, step_id: str, file: str, delete_file: bool = True) -> dict:
    """Detach an image (by its `file` name) from a step; optionally delete the file too."""
    return storage.remove_image(slug, step_id, file, delete_file).model_dump()


@mcp.tool()
def search(query: str) -> list[dict]:
    """Search workflow/step titles, descriptions, paths, commands and notes."""
    return storage.search(query)


if __name__ == "__main__":
    mcp.run()
