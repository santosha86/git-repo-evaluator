from datetime import datetime, timezone

from fastapi.testclient import TestClient

from api.main import app
from cli.models import DIMENSION_WEIGHTS, DimensionScore, EvaluationReport, grade_for
from cli.storage import save_evaluation

client = TestClient(app)


def _seed(tmp_path, monkeypatch) -> EvaluationReport:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    dims = {
        n: DimensionScore(name=n, score=7.5, weight=w, evidence=["seed"], raw={})
        for n, w in DIMENSION_WEIGHTS.items()
    }
    report = EvaluationReport(
        eval_id="seed00000001",
        repo_owner="acme",
        repo_name="widget",
        repo_url="https://github.com/acme/widget",
        evaluated_at=datetime.now(timezone.utc),
        dimensions=dims,
        final_score=7.5,
        grade=grade_for(7.5),
    )
    save_evaluation(report)
    return report


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_root_lists_routes() -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "routes" in r.json()


def test_list_evaluations_reads_seeded_csv(tmp_path, monkeypatch) -> None:
    _seed(tmp_path, monkeypatch)
    r = client.get("/api/evaluations")
    assert r.status_code == 200
    rows = r.json()
    assert any(row["eval_id"] == "seed00000001" for row in rows)


def test_evaluation_detail_404_when_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    r = client.get("/api/evaluations/doesnotexist")
    assert r.status_code == 404


def test_evaluation_detail_returns_json(tmp_path, monkeypatch) -> None:
    _seed(tmp_path, monkeypatch)
    r = client.get("/api/evaluations/seed00000001")
    assert r.status_code == 200
    body = r.json()
    assert body["repo_owner"] == "acme"
    assert "dimensions" in body


def test_repo_latest(tmp_path, monkeypatch) -> None:
    _seed(tmp_path, monkeypatch)
    r = client.get("/api/repos/acme/widget/latest")
    assert r.status_code == 200
    assert r.json()["grade"] == "B+"


def test_evaluate_rejects_bad_repo_string() -> None:
    r = client.post("/api/evaluate", json={"repo": "not-a-repo"})
    assert r.status_code == 400
