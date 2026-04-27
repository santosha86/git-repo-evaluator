"""Optional qualitative analysis of an EvaluationReport via the Claude API.

Invoked when the user passes --deep and ANTHROPIC_API_KEY is set.
"""

import os

from .models import EvaluationReport

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "2000"))

SYSTEM_PROMPT = """You are a senior software engineer helping a solopreneur decide whether to adopt an open-source GitHub repository for production use.

You will receive a structured automated-evaluation report with:
- 10 dimension scores (0-10) with weights and evidence
- A weighted final score and letter grade
- A list of vulnerability findings (secrets, dependency hygiene, AI/LLM risks, supply-chain signals)

Produce a response with EXACTLY these four sections, in order, using Markdown headers:

## Executive summary
Two short paragraphs. What is this project, and should it be trusted?

## Top 3 strengths
Bullet list. Reference the evidence when relevant.

## Top 3 risks
Bullet list. Include any critical/high vulnerabilities verbatim.

## Recommendation
One of: **Adopt**, **Adopt with caution**, **Evaluate further**, or **Avoid**. Then one sentence justifying the call.

Be concise and blunt. Prioritize actionable findings over generic advice."""


def _format_report_for_prompt(report: EvaluationReport) -> str:
    lines = [
        f"# Repository: {report.repo_owner}/{report.repo_name}",
        f"URL: {report.repo_url}",
        f"Evaluated: {report.evaluated_at.isoformat()}",
        "",
        f"## Final: {report.final_score:.2f}/10 — Grade {report.grade}",
        "",
        "## Dimension scores",
    ]
    for name, dim in report.dimensions.items():
        ev = "; ".join(dim.evidence) if dim.evidence else "—"
        lines.append(f"- **{name}** {dim.score:.2f}/10 (weight {dim.weight*100:.0f}%): {ev}")
    if report.vulnerabilities:
        lines += ["", f"## Vulnerability findings ({len(report.vulnerabilities)})"]
        for v in report.vulnerabilities:
            loc = (
                f" at {v.file}:{v.line}"
                if v.file and v.line
                else (f" ({v.file})" if v.file else "")
            )
            lines.append(f"- [{v.severity}] [{v.category}] {v.title}{loc} — {v.description}")
    else:
        lines += ["", "## Vulnerability findings: none detected by automated scan"]
    return "\n".join(lines)


def analyze(report: EvaluationReport) -> str | None:
    """Call Claude for a qualitative take on the report.

    Returns None if ANTHROPIC_API_KEY is not set. Raises on API errors.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None

    # Deferred import so the CLI works without anthropic configured.
    from anthropic import Anthropic

    client = Anthropic()
    user_prompt = _format_report_for_prompt(report)

    msg = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
    )
    parts = [block.text for block in msg.content if getattr(block, "type", "") == "text"]
    return "\n".join(parts).strip()
