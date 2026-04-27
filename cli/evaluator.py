"""Scoring engine — runs all 10 dimensions and produces an EvaluationReport."""

import asyncio
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from .github_client import GitHubClient
from .models import (
    DIMENSION_WEIGHTS,
    DimensionScore,
    EvaluationReport,
    grade_for,
)
from .storage import new_eval_id
from .vulnerabilities import run_vulnerability_scan


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _clip(v: float, lo: float = 0.0, hi: float = 10.0) -> float:
    return max(lo, min(hi, v))


def _paths_of(tree: list[dict]) -> set[str]:
    return {entry.get("path", "") for entry in tree if entry.get("path")}


def _has_any(paths: set[str], candidates: list[str]) -> bool:
    pl = {p.lower() for p in paths}
    return any(c.lower() in pl for c in candidates)


def _has_prefix(paths: set[str], prefixes: list[str]) -> bool:
    pl = [p.lower() for p in paths]
    return any(any(p.startswith(prefix.lower()) for p in pl) for prefix in prefixes)


# ---------- dimensions ----------


def score_popularity(repo: dict) -> DimensionScore:
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    watchers = repo.get("subscribers_count", 0)
    star_score = _clip(math.log10(stars + 1) * 2.0)
    fork_score = _clip(math.log10(forks + 1) * 2.5)
    watch_score = _clip(math.log10(watchers + 1) * 2.5)
    score = 0.7 * star_score + 0.2 * fork_score + 0.1 * watch_score
    return DimensionScore(
        name="popularity",
        score=round(score, 2),
        weight=DIMENSION_WEIGHTS["popularity"],
        evidence=[f"{stars:,} stars", f"{forks:,} forks", f"{watchers:,} watchers"],
        raw={"stars": stars, "forks": forks, "watchers": watchers},
    )


def score_momentum(repo: dict, recent_commits: list) -> DimensionScore:
    created = _parse_dt(repo.get("created_at"))
    age_months = max(((_now() - created).days / 30.0) if created else 1, 1)
    stars = repo.get("stargazers_count", 0)
    star_velocity = stars / age_months

    cutoff = _now() - timedelta(days=90)
    n_recent = 0
    for c in recent_commits:
        cd = _parse_dt(((c.get("commit") or {}).get("author") or {}).get("date"))
        if cd and cd >= cutoff:
            n_recent += 1

    velocity_score = _clip(math.log10(star_velocity + 1) * 4.0)
    commit_score = _clip(n_recent / 10.0)
    score = 0.5 * velocity_score + 0.5 * commit_score
    return DimensionScore(
        name="momentum",
        score=round(score, 2),
        weight=DIMENSION_WEIGHTS["momentum"],
        evidence=[
            f"{n_recent} commits in last 90 days",
            f"{star_velocity:.1f} stars/month avg",
        ],
        raw={
            "recent_commits_90d": n_recent,
            "stars_per_month": round(star_velocity, 2),
        },
    )


def score_community(contributors: list, closed_prs: list) -> DimensionScore:
    n = len(contributors)
    contrib_score = _clip(math.log10(n + 1) * 3.5)

    bus_factor_score = 5.0
    top_share = 0.0
    if contributors:
        total = sum(c.get("contributions", 0) for c in contributors) or 1
        top = max((c.get("contributions", 0) for c in contributors), default=0)
        top_share = top / total
        bus_factor_score = _clip((1 - top_share) * 12)

    merge_score = 5.0
    if closed_prs:
        merged = sum(1 for p in closed_prs if p.get("merged_at"))
        merge_score = _clip((merged / len(closed_prs)) * 10)

    score = 0.4 * contrib_score + 0.3 * bus_factor_score + 0.3 * merge_score
    evidence = [f"{n} contributors"]
    if contributors:
        evidence.append(f"top contributor share: {top_share:.0%}")
    if closed_prs:
        evidence.append(f"PR merge rate: {merge_score:.1f}/10")
    return DimensionScore(
        name="community",
        score=round(score, 2),
        weight=DIMENSION_WEIGHTS["community"],
        evidence=evidence,
        raw={"contributors": n, "top_contributor_share": round(top_share, 3)},
    )


def score_maintenance(repo: dict, releases: list) -> DimensionScore:
    if repo.get("archived"):
        return DimensionScore(
            name="maintenance",
            score=0.0,
            weight=DIMENSION_WEIGHTS["maintenance"],
            evidence=["repo is archived"],
            raw={"archived": True},
        )
    pushed = _parse_dt(repo.get("pushed_at"))
    days_since = (_now() - pushed).days if pushed else 9999
    if days_since <= 7:
        push_score = 10.0
    elif days_since <= 30:
        push_score = 8.5
    elif days_since <= 90:
        push_score = 7.0
    elif days_since <= 180:
        push_score = 5.0
    elif days_since <= 365:
        push_score = 3.0
    else:
        push_score = 1.0

    release_score = 5.0
    if releases:
        latest = _parse_dt(releases[0].get("published_at") or releases[0].get("created_at"))
        if latest:
            d = (_now() - latest).days
            release_score = (
                10.0 if d < 90 else 8.0 if d < 180 else 6.0 if d < 365 else 3.0
            )
    elif days_since < 365:
        release_score = 4.0

    score = 0.7 * push_score + 0.3 * release_score
    return DimensionScore(
        name="maintenance",
        score=round(score, 2),
        weight=DIMENSION_WEIGHTS["maintenance"],
        evidence=[
            f"last push {days_since} days ago",
            f"{len(releases)} recent releases" if releases else "no releases",
        ],
        raw={"days_since_push": days_since, "release_count": len(releases)},
    )


def score_documentation(paths: set[str], readme: Optional[str]) -> DimensionScore:
    pts = 0.0
    found: list[str] = []
    if readme:
        rl = len(readme)
        if rl > 5000:
            pts += 4
            found.append("substantial README")
        elif rl > 1000:
            pts += 3
            found.append("README")
        elif rl > 200:
            pts += 1.5
            found.append("short README")
        else:
            pts += 0.5
    if _has_any(
        paths, ["CONTRIBUTING.md", "CONTRIBUTING.rst", ".github/CONTRIBUTING.md"]
    ):
        pts += 1.5
        found.append("CONTRIBUTING")
    if _has_any(paths, ["CHANGELOG.md", "CHANGELOG", "CHANGES.md", "HISTORY.md"]):
        pts += 1.5
        found.append("CHANGELOG")
    if _has_prefix(paths, ["docs/", "doc/", "documentation/"]):
        pts += 2.0
        found.append("docs/")
    if _has_prefix(paths, ["examples/", "example/", "samples/"]):
        pts += 1.0
        found.append("examples/")
    return DimensionScore(
        name="documentation",
        score=_clip(pts),
        weight=DIMENSION_WEIGHTS["documentation"],
        evidence=found or ["minimal documentation"],
        raw={"readme_chars": len(readme) if readme else 0},
    )


CI_FILES = [
    ".circleci/config.yml",
    ".travis.yml",
    "azure-pipelines.yml",
    ".gitlab-ci.yml",
    "Jenkinsfile",
]
LINTER_FILES = [
    ".eslintrc",
    ".eslintrc.js",
    ".eslintrc.json",
    ".eslintrc.cjs",
    ".prettierrc",
    ".ruff.toml",
    "ruff.toml",
    ".flake8",
    "tslint.json",
    ".golangci.yml",
    "rustfmt.toml",
]
LOCKFILES = [
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Pipfile.lock",
    "go.sum",
    "Cargo.lock",
    "composer.lock",
    "uv.lock",
]


def score_code_quality(paths: set[str]) -> DimensionScore:
    pts = 0.0
    found: list[str] = []
    if any(p.startswith(".github/workflows") for p in paths) or _has_any(paths, CI_FILES):
        pts += 2.5
        found.append("CI configured")
    if _has_prefix(paths, ["tests/", "test/", "__tests__/", "spec/"]) or any(
        "_test." in p.lower() or p.lower().endswith(".test.ts") or p.lower().endswith(".test.js")
        for p in paths
    ):
        pts += 2.5
        found.append("tests present")
    if _has_any(paths, LINTER_FILES) or "pyproject.toml" in {p.lower() for p in paths}:
        pts += 1.5
        found.append("linter/formatter config")
    if _has_any(paths, ["Dockerfile", "dockerfile"]):
        pts += 1.5
        found.append("Dockerfile")
    if _has_any(paths, LOCKFILES):
        pts += 2.0
        found.append("dependency lockfile")
    return DimensionScore(
        name="code_quality",
        score=_clip(pts),
        weight=DIMENSION_WEIGHTS["code_quality"],
        evidence=found or ["no quality signals detected"],
        raw={},
    )


def score_security(paths: set[str]) -> DimensionScore:
    pts = 5.0
    notes: list[str] = []
    if _has_any(paths, ["SECURITY.md", ".github/SECURITY.md"]):
        pts += 2.0
        notes.append("SECURITY.md")
    if ".gitignore" in {p.lower() for p in paths}:
        pts += 1.0
        notes.append(".gitignore")
    if _has_any(paths, [".github/dependabot.yml", ".github/dependabot.yaml"]):
        pts += 2.0
        notes.append("Dependabot")
    if any(p == ".env" or p.endswith("/.env") for p in paths):
        pts -= 4.0
        notes.append("WARNING: .env file committed")
    if any(
        "secret" in p.lower() and p.lower().endswith((".json", ".yml", ".yaml", ".env"))
        for p in paths
    ):
        pts -= 2.0
        notes.append("WARNING: suspicious secrets file")
    return DimensionScore(
        name="security",
        score=_clip(pts),
        weight=DIMENSION_WEIGHTS["security"],
        evidence=notes or ["baseline (no security signals found)"],
        raw={},
    )


PERMISSIVE = {
    "mit",
    "apache-2.0",
    "bsd-2-clause",
    "bsd-3-clause",
    "isc",
    "unlicense",
    "mpl-2.0",
}
COPYLEFT = {"gpl-3.0", "gpl-2.0", "agpl-3.0", "lgpl-3.0", "lgpl-2.1"}


def score_licensing(repo: dict) -> DimensionScore:
    lic = repo.get("license") or {}
    key = (lic.get("key") or "").lower()
    name = lic.get("name") or "none"
    if not key:
        return DimensionScore(
            name="licensing",
            score=0.0,
            weight=DIMENSION_WEIGHTS["licensing"],
            evidence=["no license — all rights reserved by default"],
            raw={"license": None},
        )
    if key in PERMISSIVE:
        score, note = 10.0, f"{name} (permissive)"
    elif key in COPYLEFT:
        score, note = 6.0, f"{name} (copyleft — review for commercial use)"
    else:
        score, note = 5.0, f"{name} (other)"
    return DimensionScore(
        name="licensing",
        score=score,
        weight=DIMENSION_WEIGHTS["licensing"],
        evidence=[note],
        raw={"license": key},
    )


def score_architecture(paths: set[str]) -> DimensionScore:
    pts = 4.0
    found: list[str] = []
    modular = ["src/", "lib/", "packages/", "modules/", "internal/", "cmd/", "app/", "pkg/"]
    if _has_prefix(paths, modular):
        pts += 3.0
        found.append("modular layout")
    if _has_any(
        paths,
        [
            "config.yaml",
            "config.yml",
            "config.toml",
            "config.json",
            ".env.example",
            "settings.py",
        ],
    ):
        pts += 1.5
        found.append("config separated")
    top_level = [p for p in paths if "/" not in p]
    if 0 < len(top_level) <= 25:
        pts += 1.5
        found.append("clean top-level")
    return DimensionScore(
        name="architecture",
        score=_clip(pts),
        weight=DIMENSION_WEIGHTS["architecture"],
        evidence=found or ["flat or unclear layout"],
        raw={"top_level_files": len(top_level)},
    )


def score_real_world_value(repo: dict, releases: list) -> DimensionScore:
    stars = max(repo.get("stargazers_count", 0), 1)
    forks = repo.get("forks_count", 0)
    ratio = forks / stars
    pts = 0.0
    notes: list[str] = []
    if 0.05 <= ratio <= 0.5:
        pts += 5.0
        notes.append(f"healthy fork/star ratio ({ratio:.2f})")
    elif ratio > 0:
        pts += 2.5
        notes.append(f"fork/star ratio {ratio:.2f}")
    if releases:
        pts += 3.0
        notes.append("has releases")
    desc = (repo.get("description") or "").lower()
    if any(w in desc for w in ["awesome", "list of", "tutorial", "example", "demo"]):
        pts -= 1.0
        notes.append("likely list/tutorial/example repo")
    if not repo.get("fork"):
        pts += 2.0
    return DimensionScore(
        name="real_world_value",
        score=_clip(pts),
        weight=DIMENSION_WEIGHTS["real_world_value"],
        evidence=notes or ["limited signals"],
        raw={"fork_star_ratio": round(ratio, 3)},
    )


# ---------- orchestration ----------


async def evaluate_repo(owner: str, name: str, deep: bool = False) -> EvaluationReport:
    async with GitHubClient() as gh:
        repo = await gh.get_repo(owner, name)
        branch = repo.get("default_branch") or "main"
        since = (_now() - timedelta(days=90)).isoformat()

        commits, contributors, releases, closed_prs, tree, readme = await asyncio.gather(
            gh.list_commits(owner, name, since=since),
            gh.list_contributors(owner, name),
            gh.list_releases(owner, name),
            gh.list_closed_pulls(owner, name),
            gh.get_tree(owner, name, branch),
            gh.get_readme(owner, name),
        )
        paths = _paths_of(tree)
        vulns = await run_vulnerability_scan(gh, owner, name, repo, paths, readme)

    dims: dict[str, DimensionScore] = {
        "popularity": score_popularity(repo),
        "momentum": score_momentum(repo, commits),
        "community": score_community(contributors, closed_prs),
        "maintenance": score_maintenance(repo, releases),
        "documentation": score_documentation(paths, readme),
        "code_quality": score_code_quality(paths),
        "security": score_security(paths),
        "licensing": score_licensing(repo),
        "architecture": score_architecture(paths),
        "real_world_value": score_real_world_value(repo, releases),
    }
    final = sum(d.score * d.weight for d in dims.values())

    report = EvaluationReport(
        eval_id=new_eval_id(),
        repo_owner=owner,
        repo_name=name,
        repo_url=repo.get("html_url") or f"https://github.com/{owner}/{name}",
        evaluated_at=_now(),
        dimensions=dims,
        final_score=round(final, 2),
        grade=grade_for(final),
        vulnerabilities=vulns,
        llm_analysis=None,
    )

    if deep:
        try:
            from .claude_analysis import analyze
            report.llm_analysis = analyze(report)
        except Exception as e:
            report.llm_analysis = f"[Claude analysis unavailable: {e}]"

    return report
