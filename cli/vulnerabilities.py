"""Vulnerability scanner: secrets, dependency hygiene, AI/LLM risks."""

import re
import uuid
from typing import Optional

from .github_client import GitHubClient
from .models import VulnerabilityFinding

# ---------- secret-detection patterns ----------

SECRET_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}"), "critical"),
    ("github_token_classic", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"), "critical"),
    ("github_pat_finegrained", re.compile(r"github_pat_[A-Za-z0-9_]{60,}"), "critical"),
    ("anthropic_api_key", re.compile(r"sk-ant-[a-zA-Z0-9_\-]{40,}"), "critical"),
    ("openai_api_key", re.compile(r"sk-(proj-|svcacct-)?[A-Za-z0-9_\-]{40,}"), "critical"),
    (
        "private_key_pem",
        re.compile(r"-----BEGIN (RSA |OPENSSH |DSA |EC |PGP )?PRIVATE KEY-----"),
        "critical",
    ),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"), "high"),
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z_\-]{35}"), "high"),
    ("stripe_live_key", re.compile(r"sk_live_[A-Za-z0-9]{24,}"), "critical"),
    ("jwt_token", re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"), "medium"),
]

SUSPICIOUS_FILENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "credentials.json",
    "credentials.yml",
    "secrets.yml",
    "secrets.yaml",
    "aws_credentials",
    "service-account.json",
}

SUSPICIOUS_EXTENSIONS = (".pem", ".key", ".pfx", ".p12", ".jks")

# Files that often contain hardcoded config worth scanning even if small
SCANNABLE_CONFIG_NAMES = {
    "config.js",
    "config.ts",
    "config.py",
    "config.json",
    "settings.py",
    "docker-compose.yml",
    "docker-compose.yaml",
}


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------- path-based scans ----------


def scan_suspicious_filenames(paths: set[str]) -> list[VulnerabilityFinding]:
    findings: list[VulnerabilityFinding] = []
    for p in paths:
        name = p.rsplit("/", 1)[-1].lower()
        if name in SUSPICIOUS_FILENAMES:
            findings.append(
                VulnerabilityFinding(
                    finding_id=_new_id(),
                    severity="high",
                    category="secret",
                    title=f"Sensitive filename committed: {p}",
                    description=(
                        f"{p} is a filename that typically stores credentials. "
                        "Verify it contains no secrets and add it to .gitignore."
                    ),
                    file=p,
                )
            )
        elif p.lower().endswith(SUSPICIOUS_EXTENSIONS):
            findings.append(
                VulnerabilityFinding(
                    finding_id=_new_id(),
                    severity="medium",
                    category="secret",
                    title=f"Key/cert file committed: {p}",
                    description=(
                        f"{p} has a key-material extension. "
                        "Confirm it is a public cert, not a private key."
                    ),
                    file=p,
                )
            )
    return findings


# ---------- content-based scan ----------


def scan_text_for_secrets(filename: str, content: str) -> list[VulnerabilityFinding]:
    findings: list[VulnerabilityFinding] = []
    seen_on_line: set[tuple[int, str]] = set()
    for lineno, line in enumerate(content.splitlines(), start=1):
        for label, pattern, severity in SECRET_PATTERNS:
            if (lineno, label) in seen_on_line:
                continue
            if pattern.search(line):
                seen_on_line.add((lineno, label))
                findings.append(
                    VulnerabilityFinding(
                        finding_id=_new_id(),
                        severity=severity,  # type: ignore[arg-type]
                        category="secret",
                        title=f"Potential {label.replace('_', ' ')} leak",
                        description=f"Regex match for {label} in {filename}.",
                        file=filename,
                        line=lineno,
                    )
                )
    return findings


# ---------- dependency hygiene ----------


def analyze_dependency_hygiene(paths: set[str]) -> list[VulnerabilityFinding]:
    findings: list[VulnerabilityFinding] = []
    paths_lower = {p.lower() for p in paths}

    if "package.json" in paths_lower and not (
        {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"} & paths_lower
    ):
        findings.append(
            VulnerabilityFinding(
                finding_id=_new_id(),
                severity="medium",
                category="dependency",
                title="package.json without a lockfile",
                description=(
                    "Missing lockfile means dependency resolution is non-reproducible; "
                    "upstream package drift can silently introduce vulnerabilities."
                ),
                file="package.json",
            )
        )

    has_py_deps = bool(
        {"requirements.txt", "setup.py", "pyproject.toml", "pipfile"} & paths_lower
    )
    has_py_lock = bool(
        {"poetry.lock", "pipfile.lock", "uv.lock", "requirements-lock.txt"} & paths_lower
    )
    if has_py_deps and not has_py_lock:
        findings.append(
            VulnerabilityFinding(
                finding_id=_new_id(),
                severity="low",
                category="dependency",
                title="Python deps without a pinned lockfile",
                description=(
                    "Consider adding a lockfile (uv.lock / poetry.lock / pip-compile) "
                    "for reproducible and auditable builds."
                ),
            )
        )

    if not (
        {".github/dependabot.yml", ".github/dependabot.yaml"} & paths_lower
        or any(p.startswith(".github/workflows") for p in paths_lower)
    ):
        findings.append(
            VulnerabilityFinding(
                finding_id=_new_id(),
                severity="info",
                category="dependency",
                title="No automated dependency updates",
                description="No Dependabot config or CI workflow detected; dependency drift may go unnoticed.",
            )
        )

    return findings


# ---------- AI/LLM risk heuristics ----------

AI_KEYWORDS = (
    "llm",
    "anthropic",
    "openai",
    "claude",
    "gpt-",
    "chatgpt",
    "langchain",
    "llamaindex",
    "rag ",
    "embedding",
    "vector store",
    "prompt injection",
)


def detect_ai_llm_risks(
    paths: set[str], readme: Optional[str]
) -> list[VulnerabilityFinding]:
    findings: list[VulnerabilityFinding] = []
    text = (readme or "").lower()
    is_ai_repo = any(k in text for k in AI_KEYWORDS)
    if not is_ai_repo:
        return findings

    findings.append(
        VulnerabilityFinding(
            finding_id=_new_id(),
            severity="info",
            category="ai_risk",
            title="AI/LLM project — manual review recommended",
            description=(
                "Project integrates LLMs. Verify: "
                "(1) prompt-injection hardening on untrusted input, "
                "(2) output sanitization before rendering, "
                "(3) API-key handling via env vars, not source, "
                "(4) rate limiting / cost caps, "
                "(5) PII redaction if user data is sent to external APIs."
            ),
        )
    )
    return findings


# ---------- supply-chain quick checks ----------


def supply_chain_checks(repo: dict, paths: set[str]) -> list[VulnerabilityFinding]:
    findings: list[VulnerabilityFinding] = []
    if repo.get("archived"):
        findings.append(
            VulnerabilityFinding(
                finding_id=_new_id(),
                severity="high",
                category="supply_chain",
                title="Repository is archived",
                description=(
                    "Upstream is archived / read-only. New issues will not be fixed; "
                    "avoid adopting for new work or plan a migration."
                ),
            )
        )
    if repo.get("fork") and (repo.get("stargazers_count", 0) < 5):
        findings.append(
            VulnerabilityFinding(
                finding_id=_new_id(),
                severity="medium",
                category="supply_chain",
                title="Low-star fork",
                description=(
                    "This is a fork with few stars; verify why and prefer the upstream."
                ),
            )
        )
    if "package.json" in {p.lower() for p in paths} and not any(
        p.lower() == ".github/codeql.yml" or "codeql" in p.lower() for p in paths
    ):
        # non-blocking heuristic
        pass
    return findings


# ---------- orchestration ----------


async def fetch_and_scan_files(
    gh: GitHubClient,
    owner: str,
    name: str,
    paths: set[str],
    max_files: int = 6,
) -> list[VulnerabilityFinding]:
    """Fetch content for a small set of suspicious / config files and regex-scan them."""
    findings: list[VulnerabilityFinding] = []
    candidates: list[str] = []
    for p in paths:
        lower_name = p.rsplit("/", 1)[-1].lower()
        if (
            lower_name in SUSPICIOUS_FILENAMES
            or lower_name in SCANNABLE_CONFIG_NAMES
            or p.lower().endswith(SUSPICIOUS_EXTENSIONS)
        ):
            candidates.append(p)

    for p in candidates[:max_files]:
        try:
            content = await gh.get_file_content(owner, name, p)
        except Exception:
            continue
        if content:
            findings.extend(scan_text_for_secrets(p, content))
    return findings


async def run_vulnerability_scan(
    gh: GitHubClient,
    owner: str,
    name: str,
    repo: dict,
    paths: set[str],
    readme: Optional[str],
) -> list[VulnerabilityFinding]:
    findings: list[VulnerabilityFinding] = []
    findings.extend(scan_suspicious_filenames(paths))
    findings.extend(analyze_dependency_hygiene(paths))
    findings.extend(detect_ai_llm_risks(paths, readme))
    findings.extend(supply_chain_checks(repo, paths))
    if readme:
        findings.extend(scan_text_for_secrets("README", readme))
    findings.extend(await fetch_and_scan_files(gh, owner, name, paths))
    return findings
