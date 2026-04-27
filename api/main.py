"""FastAPI app exposing evaluator data to the React dashboard."""

import csv
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from cli.evaluator import evaluate_repo
from cli.models import EvaluationReport
from cli.storage import (
    load_detail,
    load_recent,
    load_repo_history,
    save_evaluation,
)

app = FastAPI(
    title="git-repo-evaluator API",
    version="0.1.0",
    description="Evaluate GitHub repos across 10 weighted dimensions with vulnerability scanning.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", "./data")).resolve()


# ---------- request models ----------


class EvaluateRequest(BaseModel):
    repo: str  # "owner/name" or full GitHub URL
    deep: bool = False


# ---------- helpers ----------


def _parse_repo(arg: str) -> tuple[str, str]:
    s = arg.strip().rstrip("/")
    if s.endswith(".git"):
        s = s[:-4]
    if "github.com/" in s:
        s = s.split("github.com/", 1)[1]
    if "/" not in s:
        raise HTTPException(status_code=400, detail=f"Invalid repo: {arg!r}")
    parts = s.split("/")
    return parts[0], parts[1]


def _all_repos() -> list[dict]:
    p = _data_dir() / "repos.csv"
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _vulns_for(eval_id: str) -> list[dict]:
    p = _data_dir() / "vulnerabilities.csv"
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("eval_id") == eval_id]


# ---------- routes ----------


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/repos")
def list_repos() -> list[dict]:
    return _all_repos()


@app.get("/api/repos/{owner}/{name}/history")
def repo_history(owner: str, name: str) -> list[dict]:
    return load_repo_history(owner, name)


@app.get("/api/repos/{owner}/{name}/latest")
def repo_latest(owner: str, name: str) -> dict:
    history = load_repo_history(owner, name)
    if not history:
        raise HTTPException(status_code=404, detail=f"No evaluations for {owner}/{name}")
    latest = history[-1]
    detail = load_detail(latest["eval_id"])
    if not detail:
        raise HTTPException(status_code=404, detail="Detail JSON missing")
    return detail


@app.get("/api/evaluations")
def list_evaluations(limit: int = 50) -> list[dict]:
    return load_recent(limit)


@app.get("/api/evaluations/{eval_id}")
def evaluation_detail(eval_id: str) -> dict:
    detail = load_detail(eval_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Evaluation not found: {eval_id}")
    return detail


@app.get("/api/evaluations/{eval_id}/vulnerabilities")
def evaluation_vulnerabilities(eval_id: str) -> list[dict]:
    return _vulns_for(eval_id)


@app.post("/api/evaluate")
async def trigger_evaluation(req: EvaluateRequest) -> EvaluationReport:
    owner, name = _parse_repo(req.repo)
    try:
        report = await evaluate_repo(owner, name, deep=req.deep)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Evaluation failed: {e}") from e
    save_evaluation(report)
    return report


@app.delete("/api/evaluations/{eval_id}")
def delete_evaluation(eval_id: str) -> dict:
    detail = _data_dir() / "details" / f"{eval_id}.json"
    if not detail.exists():
        raise HTTPException(status_code=404, detail=f"Evaluation not found: {eval_id}")
    detail.unlink()
    return {"deleted": eval_id}


@app.get("/")
def root() -> dict:
    return {
        "name": "git-repo-evaluator API",
        "routes": [
            "/health",
            "/api/repos",
            "/api/repos/{owner}/{name}/history",
            "/api/repos/{owner}/{name}/latest",
            "/api/evaluations",
            "/api/evaluations/{eval_id}",
            "/api/evaluations/{eval_id}/vulnerabilities",
            "/api/evaluate (POST)",
        ],
    }
