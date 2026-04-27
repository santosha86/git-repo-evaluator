"""Pydantic data models shared by CLI, storage, and API layers."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DimensionName = Literal[
    "popularity",
    "momentum",
    "community",
    "maintenance",
    "documentation",
    "code_quality",
    "security",
    "licensing",
    "architecture",
    "real_world_value",
]

DIMENSION_WEIGHTS: dict[str, float] = {
    "popularity": 0.10,
    "momentum": 0.12,
    "community": 0.10,
    "maintenance": 0.15,
    "documentation": 0.10,
    "code_quality": 0.10,
    "security": 0.15,
    "licensing": 0.08,
    "architecture": 0.05,
    "real_world_value": 0.05,
}

Severity = Literal["critical", "high", "medium", "low", "info"]


class DimensionScore(BaseModel):
    name: str
    score: float = Field(ge=0, le=10)
    weight: float
    evidence: list[str] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)


class VulnerabilityFinding(BaseModel):
    finding_id: str
    severity: Severity
    category: str  # "secret" | "dependency" | "ai_risk" | "supply_chain" | "git_history"
    title: str
    description: str
    file: str | None = None
    line: int | None = None


class EvaluationReport(BaseModel):
    eval_id: str
    repo_owner: str
    repo_name: str
    repo_url: str
    evaluated_at: datetime
    dimensions: dict[str, DimensionScore]
    final_score: float
    grade: str
    vulnerabilities: list[VulnerabilityFinding] = Field(default_factory=list)
    llm_analysis: str | None = None


def grade_for(score: float) -> str:
    if score >= 9:
        return "A+"
    if score >= 8:
        return "A"
    if score >= 7:
        return "B+"
    if score >= 6:
        return "B"
    if score >= 5:
        return "C+"
    if score >= 4:
        return "C"
    if score >= 3:
        return "D"
    return "F"
