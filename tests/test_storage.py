from datetime import UTC, datetime

from cli.models import DIMENSION_WEIGHTS, DimensionScore, EvaluationReport, grade_for
from cli.storage import load_recent, load_repo_history, save_evaluation


def _make_report(
    eval_id: str = "test12345678",
    owner: str = "acme",
    name: str = "widget",
    score: float = 8.5,
) -> EvaluationReport:
    dims = {
        n: DimensionScore(name=n, score=score, weight=w, evidence=["sample"], raw={})
        for n, w in DIMENSION_WEIGHTS.items()
    }
    return EvaluationReport(
        eval_id=eval_id,
        repo_owner=owner,
        repo_name=name,
        repo_url=f"https://github.com/{owner}/{name}",
        evaluated_at=datetime.now(UTC),
        dimensions=dims,
        final_score=score,
        grade=grade_for(score),
    )


def test_save_and_load_history(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    detail = save_evaluation(_make_report())
    assert detail.exists()

    recent = load_recent(10)
    assert len(recent) == 1
    assert recent[0]["repo_owner"] == "acme"
    assert recent[0]["grade"] == "A"

    hist = load_repo_history("acme", "widget")
    assert len(hist) == 1


def test_upsert_repo_increments_count(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    save_evaluation(_make_report(eval_id="aaaaaaaaaaaa"))
    save_evaluation(_make_report(eval_id="bbbbbbbbbbbb", score=9.2))

    repos_csv = tmp_path / "repos.csv"
    text = repos_csv.read_text(encoding="utf-8")
    assert "acme,widget" in text
    last_line = text.strip().splitlines()[-1]
    assert ",2," in last_line
