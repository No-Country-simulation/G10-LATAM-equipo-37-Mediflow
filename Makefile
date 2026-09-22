.PHONY: dev test lint evals down

dev:
	docker compose -f docker-compose.dev.yml up --build

down:
	docker compose -f docker-compose.dev.yml down

lint:
	ruff check .

test: lint
	pytest -q

evals:
	python evals/run.py --golden evals/golden/golden_v0.jsonl --report evals/output/report.md
