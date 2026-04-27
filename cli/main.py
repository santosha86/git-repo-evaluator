"""Click CLI entrypoint for git-repo-evaluator."""

import asyncio
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from .evaluator import evaluate_repo
from .models import EvaluationReport
from .storage import load_recent, load_repo_history, save_evaluation

console = Console()


def _parse_repo(arg: str) -> tuple[str, str]:
    s = arg.strip().rstrip("/")
    if s.endswith(".git"):
        s = s[:-4]
    if "github.com/" in s:
        s = s.split("github.com/", 1)[1]
    if "/" not in s:
        raise click.BadParameter(
            f"Cannot parse repo from '{arg}'. Use owner/name or a full GitHub URL."
        )
    parts = s.split("/")
    return parts[0], parts[1]


def _md_report(report: EvaluationReport) -> str:
    lines = [
        f"# Evaluation: {report.repo_owner}/{report.repo_name}",
        "",
        f"**URL:** {report.repo_url}  ",
        f"**Evaluated:** {report.evaluated_at.isoformat()}  ",
        f"**Final score:** {report.final_score:.2f} / 10  ",
        f"**Grade:** **{report.grade}**",
        "",
        "## Dimension scores",
        "",
        "| Dimension | Score | Weight | Evidence |",
        "|---|---|---|---|",
    ]
    for name, dim in report.dimensions.items():
        ev = "; ".join(dim.evidence)
        lines.append(f"| {name} | {dim.score:.2f} | {dim.weight*100:.0f}% | {ev} |")
    if report.vulnerabilities:
        lines += ["", "## Vulnerabilities", ""]
        for v in report.vulnerabilities:
            lines.append(f"- **[{v.severity}]** {v.title} — {v.description}")
    if report.llm_analysis:
        lines += ["", "## Deep analysis (Claude)", "", report.llm_analysis]
    return "\n".join(lines) + "\n"


def _render_console(report: EvaluationReport) -> None:
    title = (
        f"{report.repo_owner}/{report.repo_name}"
        f"  —  Grade [bold]{report.grade}[/bold]"
        f"  ({report.final_score:.2f}/10)"
    )
    t = Table(title=title)
    t.add_column("Dimension", style="cyan", no_wrap=True)
    t.add_column("Score", justify="right")
    t.add_column("Weight", justify="right")
    t.add_column("Evidence", overflow="fold")
    for name, dim in report.dimensions.items():
        t.add_row(
            name,
            f"{dim.score:.2f}",
            f"{dim.weight*100:.0f}%",
            "; ".join(dim.evidence),
        )
    console.print(t)
    if report.vulnerabilities:
        vt = Table(title="Vulnerabilities")
        vt.add_column("Severity", style="red")
        vt.add_column("Category")
        vt.add_column("Title")
        for v in report.vulnerabilities:
            vt.add_row(v.severity, v.category, v.title)
        console.print(vt)


@click.group()
@click.version_option(package_name="git-repo-evaluator")
def cli() -> None:
    """git-repo-evaluator — score and audit GitHub repositories."""


@cli.command()
@click.argument("repo_arg")
@click.option(
    "--deep",
    is_flag=True,
    help="Include Claude qualitative analysis (requires ANTHROPIC_API_KEY).",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["console", "json", "md"]),
    default="console",
    show_default=True,
)
@click.option("--output", type=click.Path(dir_okay=False), help="Write output to file.")
@click.option("--no-save", is_flag=True, help="Do not persist this evaluation to CSV.")
def evaluate(
    repo_arg: str, deep: bool, fmt: str, output: Optional[str], no_save: bool
) -> None:
    """Evaluate a GitHub repo. REPO_ARG is owner/name or a full GitHub URL."""
    owner, name = _parse_repo(repo_arg)
    console.print(f"[cyan]-> Evaluating[/cyan] [bold]{owner}/{name}[/bold] ...")
    try:
        report = asyncio.run(evaluate_repo(owner, name, deep=deep))
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from e

    if not no_save:
        save_evaluation(report)

    if fmt == "console":
        _render_console(report)
        return
    text = report.model_dump_json(indent=2) if fmt == "json" else _md_report(report)
    if output:
        Path(output).write_text(text, encoding="utf-8")
        console.print(f"[green]Wrote[/green] {output}")
    else:
        console.print(text)


@cli.command()
@click.argument("repo_a")
@click.argument("repo_b")
def compare(repo_a: str, repo_b: str) -> None:
    """Compare two repos side by side."""
    oa, na = _parse_repo(repo_a)
    ob, nb = _parse_repo(repo_b)

    async def _both() -> tuple[EvaluationReport, EvaluationReport]:
        a, b = await asyncio.gather(evaluate_repo(oa, na), evaluate_repo(ob, nb))
        return a, b

    a, b = asyncio.run(_both())
    save_evaluation(a)
    save_evaluation(b)

    t = Table(title=f"{oa}/{na}   vs   {ob}/{nb}")
    t.add_column("Dimension", style="cyan")
    t.add_column(na, justify="right")
    t.add_column(nb, justify="right")
    t.add_column("delta", justify="right")
    for dim_name in a.dimensions:
        sa = a.dimensions[dim_name].score
        sb = b.dimensions[dim_name].score
        t.add_row(dim_name, f"{sa:.2f}", f"{sb:.2f}", f"{sa - sb:+.2f}")
    t.add_row(
        "FINAL",
        f"{a.final_score:.2f}",
        f"{b.final_score:.2f}",
        f"{a.final_score - b.final_score:+.2f}",
    )
    console.print(t)
    console.print(f"Grades: [bold]{a.grade}[/bold]  vs  [bold]{b.grade}[/bold]")


@cli.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--output",
    type=click.Path(file_okay=False),
    default="results",
    show_default=True,
)
def batch(file: str, output: str) -> None:
    """Evaluate many repos from a text file (one per line)."""
    repos = [
        ln.strip()
        for ln in Path(file).read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    Path(output).mkdir(parents=True, exist_ok=True)
    for r in repos:
        try:
            owner, name = _parse_repo(r)
            console.print(f"[cyan]->[/cyan] {owner}/{name}")
            report = asyncio.run(evaluate_repo(owner, name))
            save_evaluation(report)
            (Path(output) / f"{owner}__{name}.md").write_text(
                _md_report(report), encoding="utf-8"
            )
        except Exception as e:
            console.print(f"  [red]error:[/red] {e}")


@cli.command()
@click.option("--last", "limit", default=20, show_default=True)
def history(limit: int) -> None:
    """Show recent evaluations."""
    rows = load_recent(limit)
    if not rows:
        console.print("[yellow]No evaluations yet.[/yellow]")
        return
    t = Table(title=f"Last {len(rows)} evaluations")
    t.add_column("When")
    t.add_column("Repo", style="cyan")
    t.add_column("Grade")
    t.add_column("Score", justify="right")
    for r in rows:
        t.add_row(
            r["evaluated_at"][:19],
            f"{r['repo_owner']}/{r['repo_name']}",
            r["grade"],
            r["final_score"],
        )
    console.print(t)


@cli.command()
@click.argument("repo_arg")
def trends(repo_arg: str) -> None:
    """Show score history for a single repo."""
    owner, name = _parse_repo(repo_arg)
    rows = load_repo_history(owner, name)
    if not rows:
        console.print(f"[yellow]No history for {owner}/{name}[/yellow]")
        return
    t = Table(title=f"{owner}/{name} — score over time")
    t.add_column("When")
    t.add_column("Grade")
    t.add_column("Score", justify="right")
    for r in rows:
        t.add_row(r["evaluated_at"][:19], r["grade"], r["final_score"])
    console.print(t)


if __name__ == "__main__":
    cli()
