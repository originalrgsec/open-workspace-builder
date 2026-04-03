"""Pre-commit hook framework (OWB-S088).

Provides:
- HookEntry dataclass for hook definitions
- Default hooks for gitleaks (secrets) and ruff (lint + format)
- YAML generation and merge for .pre-commit-config.yaml
"""

from __future__ import annotations

from dataclasses import dataclass

import yaml


@dataclass(frozen=True)
class HookEntry:
    """A single pre-commit hook definition."""

    repo: str  # "local" or a URL
    rev: str | None  # tag/version for remote repos
    hook_id: str
    name: str
    entry: str  # command to run
    language: str  # "system", "python", etc.
    types: tuple[str, ...] = ("text",)
    stages: tuple[str, ...] = ("pre-commit",)
    pass_filenames: bool = True
    args: tuple[str, ...] = ()


# Pinned versions for default hooks
_GITLEAKS_REV = "v8.22.1"
_RUFF_REV = "v0.11.4"
_TRIVY_REV = "v0.69.3"
_SEMGREP_REV = "v1.156.0"


def default_hooks() -> tuple[HookEntry, ...]:
    """Return the default set of pre-commit hooks OWB generates."""
    return (
        HookEntry(
            repo="https://github.com/gitleaks/gitleaks",
            rev=_GITLEAKS_REV,
            hook_id="gitleaks",
            name="gitleaks",
            entry="gitleaks protect --staged",
            language="system",
        ),
        HookEntry(
            repo="https://github.com/astral-sh/ruff-pre-commit",
            rev=_RUFF_REV,
            hook_id="ruff",
            name="ruff",
            entry="ruff check",
            language="python",
            args=("--fix",),
        ),
        HookEntry(
            repo="https://github.com/astral-sh/ruff-pre-commit",
            rev=_RUFF_REV,
            hook_id="ruff-format",
            name="ruff-format",
            entry="ruff format",
            language="python",
        ),
        HookEntry(
            repo="local",
            rev=None,
            hook_id="trivy",
            name="trivy vulnerability scan",
            entry="trivy fs --scanners vuln",
            language="system",
            pass_filenames=False,
        ),
        HookEntry(
            repo="https://github.com/semgrep/pre-commit",
            rev=_SEMGREP_REV,
            hook_id="semgrep",
            name="semgrep",
            entry="semgrep scan --config auto",
            language="python",
            types=("python",),
        ),
    )


def _hook_to_yaml_dict(hook: HookEntry) -> dict:
    """Convert a HookEntry to the YAML dict for a single hook within a repo.

    Local hooks require additional fields (name, entry, language, etc.)
    because pre-commit cannot derive them from a remote manifest.
    """
    entry: dict = {"id": hook.hook_id}
    if hook.args:
        entry["args"] = list(hook.args)
    if hook.repo == "local":
        entry["name"] = hook.name
        entry["entry"] = hook.entry
        entry["language"] = hook.language
        if not hook.pass_filenames:
            entry["pass_filenames"] = False
        if hook.types != ("text",):
            entry["types"] = list(hook.types)
        if hook.stages != ("pre-commit",):
            entry["stages"] = list(hook.stages)
    return entry


def _group_hooks_by_repo(hooks: tuple[HookEntry, ...]) -> list[dict]:
    """Group HookEntry objects by repo URL and produce the repos list.

    Local hooks (repo == "local") omit the rev field.
    """
    repo_order: list[str] = []
    repo_map: dict[str, dict] = {}

    for hook in hooks:
        if hook.repo not in repo_map:
            repo_order.append(hook.repo)
            repo_entry: dict = {"repo": hook.repo, "hooks": []}
            if hook.rev is not None:
                repo_entry["rev"] = hook.rev
            repo_map[hook.repo] = repo_entry
        repo_map[hook.repo]["hooks"].append(_hook_to_yaml_dict(hook))

    return [repo_map[url] for url in repo_order]


def generate_precommit_config(hooks: tuple[HookEntry, ...] | None = None) -> str:
    """Generate .pre-commit-config.yaml content as a YAML string.

    If hooks is None, uses default_hooks().
    """
    effective_hooks = hooks if hooks is not None else default_hooks()
    repos = _group_hooks_by_repo(effective_hooks)
    config = {"repos": repos}
    return yaml.dump(config, default_flow_style=False, sort_keys=False)


def merge_precommit_config(
    existing_yaml: str, new_hooks: tuple[HookEntry, ...]
) -> str:
    """Merge new hooks into an existing .pre-commit-config.yaml.

    Rules:
    - If a repo URL already exists and a hook ID already exists under it,
      the existing hook config is preserved (no overwrite).
    - If a repo URL already exists but the hook ID is new, the hook is appended.
    - If the repo URL is entirely new, the full repo entry is appended.
    """
    existing = yaml.safe_load(existing_yaml) if existing_yaml.strip() else None
    if not existing or "repos" not in existing:
        existing = {"repos": []}

    repos: list[dict] = list(existing["repos"])

    # Index existing repos by URL for fast lookup
    repo_index: dict[str, int] = {}
    for i, repo in enumerate(repos):
        repo_index[repo["repo"]] = i

    new_grouped = _group_hooks_by_repo(new_hooks)

    for new_repo in new_grouped:
        url = new_repo["repo"]
        if url in repo_index:
            # Repo exists — merge hooks without overwriting
            existing_repo = repos[repo_index[url]]
            existing_hook_ids = {h["id"] for h in existing_repo.get("hooks", [])}
            for new_hook in new_repo["hooks"]:
                if new_hook["id"] not in existing_hook_ids:
                    existing_repo["hooks"].append(new_hook)
        else:
            repos.append(new_repo)
            repo_index[url] = len(repos) - 1

    merged = {"repos": repos}
    return yaml.dump(merged, default_flow_style=False, sort_keys=False)
