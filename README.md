# git-repo-evaluator

> Decide whether a public GitHub repo is worth cloning — before you clone it.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6.svg)](https://www.typescriptlang.org/)
[![Tailwind](https://img.shields.io/badge/Tailwind-3.4-38BDF8.svg)](https://tailwindcss.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-19%2F19_passing-success.svg)](#testing)

A local-first **CLI + web dashboard** that grades any public GitHub repository on a 0-10 scale across **10 weighted dimensions** and runs a **vulnerability scan** for leaked secrets, dependency hygiene issues, AI/LLM risks, and supply-chain red flags. Optional `--deep` mode adds a Claude-generated qualitative review.

All data stays on your machine — CSV files + JSON sidecars, no database, no telemetry.

---

## Why I built this

Every week I see a trending GitHub repo on Hacker News or X and wonder: *should I install this on my laptop?* Existing tools either focus narrowly on dependency CVEs or ask me to read 50K-line repos by hand.

This tool answers the broader question — **is the project healthy, well-maintained, securely engineered, and worth my time?** — in 5-15 seconds, with reproducible scoring and evidence-backed findings.

---

## Demo

| CLI | Web dashboard |
|---|---|
| ![cli demo](docs/cli-demo.gif) *(placeholder)* | ![dashboard demo](docs/dashboard-demo.gif) *(placeholder)* |

```text
$ git-repo-evaluator evaluate facebook/react
-> Evaluating facebook/react ...
                       facebook/react  —  Grade A  (8.94/10)
┌──────────────────┬───────┬────────┬───────────────────────────────────────────┐
│ Dimension        │ Score │ Weight │ Evidence                                  │
├──────────────────┼───────┼────────┼───────────────────────────────────────────┤
│ popularity       │ 10.00 │   10%  │ 230,000 stars; 47,000 forks               │
│ momentum         │  9.50 │   12%  │ 412 commits in last 90 days               │
│ community        │  7.85 │   10%  │ 1,624 contributors; PR merge rate 8.2/10  │
│ maintenance      │ 10.00 │   15%  │ last push 2 days ago; 5 recent releases   │
│ documentation    │ 10.00 │   10%  │ substantial README; CONTRIBUTING; docs/   │
│ code_quality     │ 10.00 │   10%  │ CI configured; tests; lockfile; Dockerfile│
│ security         │ 10.00 │   15%  │ SECURITY.md; .gitignore; Dependabot       │
│ licensing        │ 10.00 │    8%  │ MIT (permissive)                          │
│ architecture     │  8.50 │    5%  │ modular layout; clean top-level           │
│ real_world_value │  7.00 │    5%  │ healthy fork/star ratio (0.20); releases  │
└──────────────────┴───────┴────────┴───────────────────────────────────────────┘
```

---

## Quick start

```bash
git clone https://github.com/<your-username>/git-repo-evaluator.git
cd git-repo-evaluator

# Backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

# First evaluation (CLI)
git-repo-evaluator evaluate facebook/react

# Or run the full stack — API + dashboard
uvicorn api.main:app --reload &           # http://127.0.0.1:8000
cd dashboard && npm install && npm run dev # http://localhost:5173
```

> **Tip**: add a `GITHUB_TOKEN` to `.env` to raise the GitHub rate limit from **60 req/hr → 5,000 req/hr**. See [.env.example](.env.example).

---

## Scoring methodology

Each repo is scored across **10 weighted dimensions** that sum to 100%:

| Dimension | Weight | Signals |
|---|---|---|
| **popularity** | 10% | Stars, forks, watchers (log scale to dampen outliers) |
| **momentum** | 12% | Commits in last 90 days, stars/month velocity |
| **community** | 10% | # contributors, bus factor (top contributor's share), PR merge rate |
| **maintenance** | 15% | Days since last push, recent releases, archived flag |
| **documentation** | 10% | README size, CONTRIBUTING, CHANGELOG, `docs/`, `examples/` |
| **code_quality** | 10% | CI workflow, tests dir, linter config, Dockerfile, dependency lockfile |
| **security** | 15% | SECURITY.md, .gitignore, Dependabot, absence of committed `.env`/secrets |
| **licensing** | 8% | Permissive (MIT/Apache) > copyleft (GPL) > none |
| **architecture** | 5% | Modular layout (`src/`, `lib/`), config separation |
| **real_world_value** | 5% | Fork/star ratio, has releases, not an "awesome list" / tutorial |

Final letter grade: **A+** ≥ 9.0, **A** ≥ 8.0, **B+** ≥ 7.0, ..., **F** < 3.0.

All scoring formulas are deterministic and live in [cli/evaluator.py](cli/evaluator.py). Weights are defined in [cli/models.py](cli/models.py).

---

## Vulnerability scanning

The vuln scanner is **independent of the score** — it surfaces actionable findings rather than reducing them to a number. Five categories:

| Category | What it checks |
|---|---|
| **Secrets** | Regex patterns for AWS keys, GitHub tokens (classic + fine-grained PAT), Anthropic, OpenAI, Stripe, Google, Slack tokens, JWTs, RSA/OpenSSH/EC private keys |
| **Sensitive filenames** | Flags committed `.env`, `id_rsa`, `credentials.json`, `*.pem`, `*.key`, etc. |
| **Dependency hygiene** | Detects missing lockfiles, no Dependabot/CI automation |
| **AI/LLM risks** | Heuristic flag for projects integrating LLMs — reminds you to verify prompt-injection hardening, output sanitization, key handling |
| **Supply chain** | Archived repos, low-star forks, drifting upstreams |

For each finding the scanner emits `severity` (critical / high / medium / low / info), `file`, `line`, and a one-line `description`. See [cli/vulnerabilities.py](cli/vulnerabilities.py).

---

## Architecture

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│  React Dashboard    │◄──►│  FastAPI Backend    │◄──►│  Scoring Engine     │
│  (Vite + Tailwind   │    │  (api/main.py)      │    │  (cli/evaluator.py) │
│   + Recharts)       │    │                     │    │                     │
└─────────────────────┘    └──────────┬──────────┘    └──────────┬──────────┘
                                      │                          │
                                      │             ┌────────────┴────────────┐
                                      │             │                         │
                                      │             ▼                         ▼
                                      │   ┌─────────────────────┐   ┌──────────────────┐
                                      │   │  GitHub REST API    │   │  Vulnerability   │
                                      │   │  (async httpx +     │   │  Scanner         │
                                      │   │   rate-limit retry) │   │  (regex + heur.) │
                                      │   └─────────────────────┘   └──────────────────┘
                                      │
                                      ▼
                            ┌─────────────────────┐    ┌──────────────────────────┐
                            │  CSV + JSON storage │    │  (optional)              │
                            │  data/*.csv         │    │  Claude API for --deep   │
                            │  data/details/*.json│    │  qualitative analysis    │
                            └─────────────────────┘    └──────────────────────────┘
```

**Design decisions worth highlighting:**

- **Async-first GitHub client** — six `httpx` calls (commits, contributors, releases, PRs, file tree, README) run concurrently via `asyncio.gather`, cutting eval time from ~30s to ~5-15s.
- **CSV + JSON sidecar storage** instead of SQLite — fully readable in Excel, Git-diffable, no schema migrations, no external service. Tradeoff: poor for >100K evaluations, fine for personal use.
- **Pydantic v2 across the stack** — same models in CLI, API, and JSON serialization, no DTO duplication.
- **Deterministic scoring + LLM augmentation** — the score is reproducible (same inputs → same output). Claude is *only* invoked with `--deep` and only generates a human-readable summary; it never decides scores.
- **File locks** (`filelock`) on CSV writes for safe concurrent batch evals.

---

## CLI reference

```bash
# Single evaluation (default: console table output, persisted to CSV)
git-repo-evaluator evaluate <owner/name>
git-repo-evaluator evaluate https://github.com/<owner>/<name>

# With Claude qualitative analysis
git-repo-evaluator evaluate <owner/name> --deep

# Output formats
git-repo-evaluator evaluate <owner/name> --format json --output report.json
git-repo-evaluator evaluate <owner/name> --format md   --output report.md

# Side-by-side compare
git-repo-evaluator compare facebook/react vuejs/vue

# Bulk evaluation from a text file (one owner/name per line)
git-repo-evaluator batch repos.txt --output results/

# Browse history
git-repo-evaluator history --last 20
git-repo-evaluator trends <owner/name>
```

---

## API reference

Run `uvicorn api.main:app --reload` to start the API server (port 8000).

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness probe |
| GET | `/api/repos` | All tracked repos with latest grade |
| GET | `/api/repos/{owner}/{name}/history` | Score over time |
| GET | `/api/repos/{owner}/{name}/latest` | Full latest report |
| GET | `/api/evaluations?limit=N` | Recent evaluations across all repos |
| GET | `/api/evaluations/{eval_id}` | Full evaluation report (JSON) |
| GET | `/api/evaluations/{eval_id}/vulnerabilities` | Vulnerability findings only |
| POST | `/api/evaluate` | Trigger new evaluation. Body: `{"repo": "owner/name", "deep": false}` |
| DELETE | `/api/evaluations/{eval_id}` | Remove a stored evaluation |

OpenAPI docs are auto-generated at `http://127.0.0.1:8000/docs`.

---

## Tech stack

**Backend** — Python 3.11+, [Click](https://click.palletsprojects.com/) (CLI), [httpx](https://www.python-httpx.org/) (async HTTP), [Pydantic v2](https://docs.pydantic.dev/) (models), [FastAPI](https://fastapi.tiangolo.com/) (REST), [Rich](https://rich.readthedocs.io/) (terminal output), [filelock](https://py-filelock.readthedocs.io/), [Anthropic SDK](https://github.com/anthropics/anthropic-sdk-python) (optional)

**Frontend** — [React 18](https://react.dev/) + [TypeScript](https://www.typescriptlang.org/), [Vite](https://vitejs.dev/), [Tailwind CSS](https://tailwindcss.com/), [Recharts](https://recharts.org/) (radar charts), [React Router](https://reactrouter.com/)

**Tooling** — [pytest](https://docs.pytest.org/) (19 tests), [Ruff](https://github.com/astral-sh/ruff) + [Black](https://github.com/psf/black) (lint/format), [respx](https://lundberg.github.io/respx/) (HTTP mocking), Docker + docker-compose, Make

---

## Project structure

```
git-repo-evaluator/
├── cli/                          # CLI + scoring engine
│   ├── main.py                   # Click commands (evaluate / compare / batch / history / trends)
│   ├── evaluator.py              # Async orchestrator + 10 dimension scorers
│   ├── github_client.py          # Async GitHub REST client w/ rate-limit handling
│   ├── vulnerabilities.py        # Secret patterns, dep hygiene, AI/LLM heuristics
│   ├── claude_analysis.py        # Optional --deep mode (Anthropic SDK + cached system prompt)
│   ├── storage.py                # CSV writes + JSON sidecars + file locks
│   └── models.py                 # Pydantic v2 models, dimension weights, grade ladder
├── api/
│   └── main.py                   # FastAPI app w/ CORS, 8 routes
├── dashboard/                    # React + TS + Tailwind dashboard
│   ├── src/components/           # RadarScores, VulnerabilityTable, GradeBadge
│   ├── src/pages/                # Home, EvaluationDetail
│   ├── src/lib/api.ts            # Typed API client
│   └── vite.config.ts            # Proxies /api → backend
├── tests/                        # 19 tests: models, storage, vulnerabilities, API
├── data/                         # CSV files (created on first run)
│   ├── evaluations.csv
│   ├── repos.csv
│   ├── vulnerabilities.csv
│   └── details/<eval_id>.json    # Full evaluation reports
├── pyproject.toml
├── docker-compose.yml
└── Makefile
```

---

## Development

```bash
make install      # pip install -e ".[dev]" + npm install
make test         # pytest + (optional) frontend tests
make lint         # ruff + black --check + eslint
make format       # auto-fix
make api          # uvicorn dev server
make dashboard    # vite dev server
make dev          # docker-compose up (full stack)
```

### Testing

19 tests across 4 modules:

```bash
pytest tests/ -v
```

- `test_models.py` — weights sum to 1.0, grade thresholds
- `test_storage.py` — CSV round-trip, repo upsert
- `test_vulnerabilities.py` — secret-regex hits, dep hygiene, AI heuristic, archived flag
- `test_api.py` — FastAPI test client (health, list, detail, 404, evaluate validation)

---

## Limitations & honest caveats

What this tool **does not** do:

- **Doesn't run the code** — a repo can score A and still contain malicious logic that only executes at runtime. Always read `package.json` scripts, `setup.py`, etc. before installing.
- **Doesn't query CVE databases** — it only checks if a lockfile exists. For real CVE scanning, run `npm audit` or `pip-audit` after cloning.
- **Only scans committed files** — secrets removed in a later commit but still in git history won't be caught.
- **Regex-based secret detection has false negatives** — obfuscated or custom-format keys may slip through.
- **Heuristic, not agentic** — the scoring pipeline is fixed; Claude (when invoked with `--deep`) only summarizes the report, it doesn't autonomously dig deeper.

---

## Roadmap

- [ ] **Agentic mode** — let Claude pick which suspicious files to read, run `npm audit` itself, iterate until confident
- [ ] **CVE integration** — wire up GitHub Advisory DB and `osv.dev` for real dependency vulnerability data
- [ ] **Git history scanning** — clone shallow + scan for secrets removed in later commits
- [ ] **Compare-mode dashboard view** — side-by-side radar charts
- [ ] **Scheduled scans** — re-evaluate tracked repos weekly, alert on score regressions

---

## License

MIT — see [LICENSE](LICENSE).

## Author

Built by **Santosh Achanta** ([santosh.achanta64@gmail.com](mailto:santosh.achanta64@gmail.com)).

If you found this useful or have feedback, please open an issue or reach out.
