# git-repo-evaluator — common dev tasks
# Note: on Windows, run via Git Bash / WSL, or use the equivalent commands directly.

.PHONY: install dev api dashboard test lint format eval batch build docker-up docker-down clean

install:
	python -m pip install -e ".[dev]"
	cd dashboard && npm install

dev:
	docker-compose up --build

api:
	uvicorn api.main:app --reload --host $${API_HOST:-127.0.0.1} --port $${API_PORT:-8000}

dashboard:
	cd dashboard && npm run dev

test:
	pytest tests/ -v
	cd dashboard && npm test --if-present

lint:
	ruff check cli/ api/ tests/
	black --check cli/ api/ tests/
	cd dashboard && npm run lint --if-present

format:
	ruff check --fix cli/ api/ tests/
	black cli/ api/ tests/

eval:
	python -m cli.main evaluate $(REPO)

batch:
	python -m cli.main batch $(FILE)

build:
	docker build -t git-repo-evaluator .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache __pycache__ */__pycache__ */*/__pycache__
