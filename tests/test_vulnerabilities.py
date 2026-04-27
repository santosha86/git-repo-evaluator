from cli.vulnerabilities import (
    analyze_dependency_hygiene,
    detect_ai_llm_risks,
    scan_suspicious_filenames,
    scan_text_for_secrets,
    supply_chain_checks,
)


def test_suspicious_filenames_flags_env_and_keys() -> None:
    paths = {".env", "src/main.py", "certs/server.pem", "ok/README.md"}
    findings = scan_suspicious_filenames(paths)
    titles = [f.title for f in findings]
    assert any(".env" in t for t in titles)
    assert any("server.pem" in t for t in titles)
    assert not any("main.py" in t for t in titles)


def test_scan_text_catches_aws_and_github_tokens() -> None:
    content = "\n".join(
        [
            "aws_access_key_id = AKIAIOSFODNN7EXAMPLE",
            "some_github = ghp_abcdefghijklmnopqrstuvwxyz0123456789",
            "harmless = AKIA_this_is_not_a_key",
        ]
    )
    findings = scan_text_for_secrets("config.env", content)
    titles = " ".join(f.title for f in findings)
    assert "aws access key" in titles
    assert "github token" in titles
    # line 3 should not produce a hit (underscores break the regex)
    for f in findings:
        assert f.line in (1, 2)


def test_scan_text_catches_private_key_header() -> None:
    content = "foo\n-----BEGIN RSA PRIVATE KEY-----\nbar"
    findings = scan_text_for_secrets("id_rsa", content)
    assert any("private key" in f.title.lower() for f in findings)
    assert findings[0].severity == "critical"


def test_dependency_hygiene_flags_missing_lockfile() -> None:
    paths = {"package.json", "src/index.js"}
    findings = analyze_dependency_hygiene(paths)
    assert any("lockfile" in f.title.lower() for f in findings)


def test_dependency_hygiene_ok_when_lockfile_present() -> None:
    paths = {"package.json", "package-lock.json", ".github/dependabot.yml"}
    findings = analyze_dependency_hygiene(paths)
    # should not flag missing lockfile or missing automation
    assert not any("lockfile" in f.title.lower() for f in findings)
    assert not any("automated dependency" in f.title.lower() for f in findings)


def test_ai_risk_triggered_by_readme_keywords() -> None:
    readme = "This library wraps the Anthropic Claude API for simple LLM access."
    findings = detect_ai_llm_risks(set(), readme)
    assert len(findings) == 1
    assert findings[0].category == "ai_risk"


def test_ai_risk_not_triggered_without_keywords() -> None:
    assert detect_ai_llm_risks(set(), "A calculator in Rust.") == []


def test_supply_chain_flags_archived() -> None:
    findings = supply_chain_checks({"archived": True}, set())
    assert any("archived" in f.title.lower() for f in findings)
