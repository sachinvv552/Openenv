"""FastAPI app for SupportBench."""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from .env import SupportBenchAction, SupportBenchEnv
from .tasks import TASKS


app = FastAPI(title="SupportBench OpenEnv")
ENV = SupportBenchEnv()


class ResetRequest(BaseModel):
    task_id: Optional[str] = None


@app.get("/")
def root():
    return {
        "name": "supportbench",
        "description": "Customer support triage benchmark for OpenEnv-style agents.",
        "tasks": [task["task_id"] for task in TASKS],
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tasks")
def tasks():
    return [
        {
            "task_id": task["task_id"],
            "difficulty": task["difficulty"],
            "title": task["title"],
        }
        for task in TASKS
    ]


@app.post("/reset")
def reset(request: Optional[ResetRequest] = None):
    task_id = request.task_id if request else None
    observation = ENV.reset(task_id=task_id)
    return observation.model_dump()


@app.get("/state")
def state():
    return ENV.state().model_dump()


@app.post("/step")
def step(action: SupportBenchAction):
    result = ENV.step(action)
    return result.model_dump()
