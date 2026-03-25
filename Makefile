.PHONY: check-deps audit-deps audit-deps-deep test lint

check-deps:
	uv run pip-audit --desc --skip-editable

audit-deps:
	uv run owb audit deps --format text

audit-deps-deep:
	uv run owb audit deps --deep --format text

test:
	uv run pytest tests/ -x

lint:
	uv run ruff check src/ tests/
