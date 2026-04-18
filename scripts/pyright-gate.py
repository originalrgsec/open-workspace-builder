#!/usr/bin/env python3
"""OWB-S139: Pyright budget-gate wrapper.

Runs `uv run pyright` and compares the observed error count against
the frozen budget from DRN-078. Fails the hook when `count > budget`,
passes otherwise — including when count equals the budget (budget is
a ceiling, not a target).

The budget is intentionally a runtime constant so a change requires
editing this file, which makes budget changes visible in code review
and traceable to a DRN bump. Matches the "no new errors" design in
HMB-S037 / DRN-077 (OWB's budget differs because the base is 96
existing errors, inventoried in DRN-078).

Usage as a pre-commit hook (repo-local):
    - repo: local
      hooks:
        - id: pyright
          name: pyright (basic per DRN-078, budget=96)
          entry: python3 scripts/pyright-gate.py
          language: system
          pass_filenames: false

Usage in CI: the same script runs via `pre-commit run pyright --all-files`
so local and CI cannot drift (OWB-S139 AC-4).
"""

from __future__ import annotations

import re
import subprocess
import sys

# Frozen per DRN-078 (accepted 2026-04-18, Sprint 31 close).
# Raising this ceiling requires a new DRN or an explicit sprint
# decision; lowering is encouraged (OWB-S144 drops it to ~36).
PYRIGHT_BUDGET = 96

_SUMMARY_RE = re.compile(r"(?P<errors>\d+)\s+errors?,\s+\d+\s+warnings?,\s+\d+\s+informations?")


def parse_error_count(output: str) -> int | None:
    """Extract the error count from pyright's summary line.

    Returns None when no summary line is present (pyright did not
    run to completion).
    """
    match = _SUMMARY_RE.search(output)
    if match is None:
        return None
    return int(match.group("errors"))


def check_budget(count: int, budget: int) -> tuple[bool, str]:
    """Compare observed error count against the frozen budget.

    Returns (passed, message). `passed` is False when count exceeds
    budget; True otherwise.
    """
    if count > budget:
        msg = (
            f"pyright: FAIL — {count} errors exceeds budget of {budget} "
            f"(DRN-078 frozen ceiling). Fix the new error(s) rather than "
            f"raising the budget. If a legitimate exception exists, file a "
            f"new DRN and bump PYRIGHT_BUDGET in scripts/pyright-gate.py."
        )
        return False, msg
    msg = f"pyright: OK — {count} errors within budget of {budget} (DRN-078)."
    return True, msg


def main() -> int:
    result = subprocess.run(
        ["uv", "run", "pyright"],
        capture_output=True,
        text=True,
        check=False,
    )
    combined = result.stdout + result.stderr
    count = parse_error_count(combined)
    if count is None:
        sys.stderr.write("pyright-gate: could not parse pyright output. Raw output follows:\n\n")
        sys.stderr.write(combined)
        return 2
    passed, message = check_budget(count, PYRIGHT_BUDGET)
    stream = sys.stdout if passed else sys.stderr
    stream.write(message + "\n")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
