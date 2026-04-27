"""CSV-based persistence with JSON sidecars for nested evaluation evidence."""

import csv
import json
import os
import uuid
from pathlib import Path
from typing import Optional

from filelock import FileLock

from .models import DIMENSION_WEIGHTS, EvaluationReport


def _data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", "./data")).resolve()


EVAL_HEADERS: list[str] = [
    "eval_id",
    "repo_owner",
    "repo_name",
    "repo_url",
    "evaluated_at",
    *DIMENSION_WEIGHTS.keys(),
    "final_score",
    "grade",
    "details_path",
]

VULN_HEADERS: list[str] = [
    "eval_id",
    "finding_id",
    "severity",
    "category",
    "title",
    "file",
    "line",
    "description",
]

REPOS_HEADERS: list[str] = [
    "repo_owner",
    "repo_name",
    "repo_url",
    "first_evaluated",
    "last_evaluated",
    "eval_count",
    "latest_grade",
    "latest_score",
]


def _ensure_files() -> None:
    base = _data_dir()
    (base / "details").mkdir(parents=True, exist_ok=True)
    for path, headers in [
        (base / "evaluations.csv", EVAL_HEADERS),
        (base / "vulnerabilities.csv", VULN_HEADERS),
        (base / "repos.csv", REPOS_HEADERS),
    ]:
        if not path.exists():
            with path.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(headers)


def new_eval_id() -> str:
    return uuid.uuid4().hex[:12]


def save_evaluation(report: EvaluationReport) -> Path:
    _ensure_files()
    base = _data_dir()
    detail_path = base / "details" / f"{report.eval_id}.json"
    detail_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    eval_csv = base / "evaluations.csv"
    with FileLock(str(eval_csv) + ".lock"):
        with eval_csv.open("a", newline="", encoding="utf-8") as f:
            row: dict = {
                "eval_id": report.eval_id,
                "repo_owner": report.repo_owner,
                "repo_name": report.repo_name,
                "repo_url": report.repo_url,
                "evaluated_at": report.evaluated_at.isoformat(),
                **{
                    name: f"{report.dimensions[name].score:.2f}"
                    for name in DIMENSION_WEIGHTS
                },
                "final_score": f"{report.final_score:.2f}",
                "grade": report.grade,
                "details_path": str(detail_path.relative_to(base)).replace("\\", "/"),
            }
            csv.DictWriter(f, fieldnames=EVAL_HEADERS).writerow(row)

    if report.vulnerabilities:
        vuln_csv = base / "vulnerabilities.csv"
        with FileLock(str(vuln_csv) + ".lock"):
            with vuln_csv.open("a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=VULN_HEADERS)
                for v in report.vulnerabilities:
                    w.writerow(
                        {
                            "eval_id": report.eval_id,
                            "finding_id": v.finding_id,
                            "severity": v.severity,
                            "category": v.category,
                            "title": v.title,
                            "file": v.file or "",
                            "line": v.line if v.line is not None else "",
                            "description": (v.description or "")
                            .replace("\n", " ")
                            .replace("\r", " "),
                        }
                    )

    _upsert_repo(report)
    return detail_path


def _upsert_repo(report: EvaluationReport) -> None:
    base = _data_dir()
    repos_csv = base / "repos.csv"
    rows: list[dict] = []
    found = False
    with FileLock(str(repos_csv) + ".lock"):
        if repos_csv.exists():
            with repos_csv.open("r", encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    if (
                        row.get("repo_owner") == report.repo_owner
                        and row.get("repo_name") == report.repo_name
                    ):
                        row["last_evaluated"] = report.evaluated_at.isoformat()
                        row["eval_count"] = str(int(row.get("eval_count") or "0") + 1)
                        row["latest_grade"] = report.grade
                        row["latest_score"] = f"{report.final_score:.2f}"
                        found = True
                    rows.append(row)
        if not found:
            rows.append(
                {
                    "repo_owner": report.repo_owner,
                    "repo_name": report.repo_name,
                    "repo_url": report.repo_url,
                    "first_evaluated": report.evaluated_at.isoformat(),
                    "last_evaluated": report.evaluated_at.isoformat(),
                    "eval_count": "1",
                    "latest_grade": report.grade,
                    "latest_score": f"{report.final_score:.2f}",
                }
            )
        with repos_csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=REPOS_HEADERS)
            w.writeheader()
            w.writerows(rows)


def load_recent(limit: int = 20) -> list[dict]:
    base = _data_dir()
    eval_csv = base / "evaluations.csv"
    if not eval_csv.exists():
        return []
    with eval_csv.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return list(reversed(rows[-limit:]))


def load_repo_history(owner: str, name: str) -> list[dict]:
    base = _data_dir()
    eval_csv = base / "evaluations.csv"
    if not eval_csv.exists():
        return []
    with eval_csv.open("r", encoding="utf-8", newline="") as f:
        return [
            r
            for r in csv.DictReader(f)
            if r.get("repo_owner") == owner and r.get("repo_name") == name
        ]


def load_detail(eval_id: str) -> Optional[dict]:
    path = _data_dir() / "details" / f"{eval_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
