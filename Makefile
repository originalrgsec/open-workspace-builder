.PHONY: check-deps audit-deps audit-deps-deep test lint sast sast-json check-suppressions

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

sast:			## Run Semgrep SAST scan on source code
	semgrep --config auto src/

sast-json:		## Run Semgrep with JSON output
	semgrep --config auto --json --output sast-results.json src/

check-suppressions:	## Check if suppressed CVEs have fixes available
	uv run owb audit check-suppressions
