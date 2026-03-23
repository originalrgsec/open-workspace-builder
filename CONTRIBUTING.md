# Contributing to owb (Open Workspace Builder)

Thank you for your interest in contributing! This document covers the development setup, coding conventions, and PR process.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/VolcanixLLC/open-workspace-builder.git
cd open-workspace-builder

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev,yaml,security]"

# Verify the CLI works
owb --version
```

## Running Tests

```bash
# Run the full test suite
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_config.py
```

All tests must pass before opening a PR.

## Code Style

- **Linter:** [Ruff](https://docs.astral.sh/ruff/) (configured in `pyproject.toml`)
- **Target:** Python 3.10+
- **Line length:** 100 characters
- **Formatting:** Run `ruff check --fix` and `ruff format` before committing

## Branch Naming

Use prefixed branch names:

```
feature/<story-id>-<short-description>
fix/<issue-id>-<short-description>
chore/<description>
```

Examples: `feature/s018-readme-docs`, `fix/42-scan-crash`, `chore/update-deps`

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <description>

<optional body>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`

## Pull Request Process

1. Create a feature branch from `main`.
2. Make your changes with tests.
3. Ensure `pytest` passes and `ruff check` is clean.
4. Run `owb security scan` on any new content files (agents, commands, rules, skills).
5. Push your branch and open a PR against `main`.
6. PRs require owner review before merge (branch protection is enabled).

## Project Structure

```
src/open_workspace_builder/
├── cli.py              # Click CLI entry point
├── config.py           # Configuration dataclasses + YAML loading
├── engine/             # Workspace construction modules
│   ├── builder.py      # Orchestrator
│   ├── vault.py        # Obsidian vault scaffolding
│   ├── ecc.py          # ECC content installation
│   ├── skills.py       # Skill installation
│   ├── context.py      # Context template deployment
│   ├── differ.py       # Workspace diff logic
│   ├── migrator.py     # Workspace migration
│   └── ecc_update.py   # ECC upstream sync
└── security/           # Three-layer content scanner
    ├── scanner.py      # Scanner orchestrator
    ├── structural.py   # Layer 1: file type/size/encoding
    ├── patterns.py     # Layer 2: regex pattern matching
    ├── semantic.py     # Layer 3: Claude API analysis
    └── reputation.py   # Append-only flag event ledger
```

## Security Requirements

- Run `owb security scan` on any new or modified content files before committing.
- Never commit secrets, API keys, or credentials.
- Content files pulled from external sources must pass all three scanner layers.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
