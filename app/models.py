from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Status = Literal["todo", "in-progress", "done", "blocked"]


class Command(BaseModel):
    cmd: str
    shell: str = "powershell"
    cwd: str = ""
    note: str = ""


class PathRef(BaseModel):
    path: str
    note: str = ""


class Image(BaseModel):
    file: str  # filename inside the workflow's assets folder
    caption: str = ""


class StepIn(BaseModel):
    """Fields a client may set when creating or replacing a step."""

    title: str
    description: str = ""  # Markdown
    paths: list[PathRef] = Field(default_factory=list)
    commands: list[Command] = Field(default_factory=list)
    images: list[Image] = Field(default_factory=list)
    diagram: str = ""  # Mermaid source
    status: Status = "todo"
    notes: str = ""  # free-form Markdown scratch space
    tags: list[str] = Field(default_factory=list)


class StepPatch(BaseModel):
    """Partial update: only fields that are sent are changed."""

    title: Optional[str] = None
    description: Optional[str] = None
    paths: Optional[list[PathRef]] = None
    commands: Optional[list[Command]] = None
    images: Optional[list[Image]] = None
    diagram: Optional[str] = None
    status: Optional[Status] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None


class Step(StepIn):
    id: str


class WorkflowIn(BaseModel):
    title: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    diagram: str = ""  # workflow-level overview diagram (Mermaid)


class WorkflowPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    diagram: Optional[str] = None


class Workflow(WorkflowIn):
    slug: str
    created: str
    updated: str
    steps: list[Step] = Field(default_factory=list)


class Reorder(BaseModel):
    order: list[str]  # complete list of step ids in the new order


class WorkflowSummary(BaseModel):
    slug: str
    title: str
    description: str
    tags: list[str]
    step_count: int
    updated: str
