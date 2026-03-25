# Dependency Security Gate

## Pre-Install Audit (MANDATORY)

Before executing ANY command that introduces a new Python dependency, run the supply-chain security scan first:

```bash
owb audit package <package-name>
```

This applies to:
- `uv add <package>`
- `pip install <package>`
- `uv pip install <package>`
- Adding a line to `pyproject.toml` dependencies and running `uv sync`

**If the audit reports findings:**
- STOP. Do not proceed with the install.
- Present all findings (CVEs and GuardDog flags) to the user.
- Wait for the user to decide: proceed anyway, pin a different version, or skip.

**If the audit is clean:** Proceed with the install.

**For bulk installs** (`uv sync`, `pip install -r requirements.txt`):
- Run `owb audit deps` AFTER the install completes to catch transitive dependencies.
- If findings are reported, present them to the user immediately.

## Version Pinning

When adding a new dependency:
- Pin to the specific version that passed the audit (e.g., `package==1.2.3`), not an open range.
- If the user requests an open range, note the security tradeoff.

## Shared Environment

All Python projects under this workspace share a single virtual environment at the workspace root. Do not create per-project `.venv` directories. Use `uv` for all package operations.
