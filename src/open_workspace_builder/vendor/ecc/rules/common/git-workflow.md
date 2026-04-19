# Git Workflow

## Commit Message Format

```
<type>: <description>

<optional body>
```

Types: feat, fix, refactor, docs, test, chore, perf, ci

Attribution lines (e.g., `Co-Authored-By: …`) are controlled by your Claude Code `settings.json`. If your workspace disables attribution globally, do not add it per-commit.

## Autonomous Git Operations

When this rule is adopted for a project, all non-destructive git operations are default-yes. Do not ask before executing:

- Committing and pushing to any branch (including `main` on personal / stealth projects where the operator has opted into autonomous pushes)
- Creating, updating, commenting on, reviewing pull requests
- Merging pull requests (squash merge per project default unless stated otherwise)
- Tagging releases, creating release notes, publishing release artifacts
- Creating, renaming, or deleting branches that do not contain uncommitted work
- Opening issues, commenting on issues, closing issues

This is an opt-in posture. Without this rule in place, treat shared-state actions (PRs, pushes, issues) as requiring confirmation per the Claude Code default.

### Actions that remain gated (always ask)

These are truly destructive or cross-account and must still be confirmed:

- `git push --force` / `--force-with-lease`, history rewrite (`rebase -i`, `reset --hard` on published refs), deleting commits that have been pushed
- `git reset --hard` / `git clean -fd` when uncommitted work is present
- Deleting or renaming branches that contain uncommitted work
- Pushing to any remote other than the project's own origin (including pushing to a different GitHub account's repo)
- Any operation that crosses a configured account boundary (e.g., work vs. personal GitHub accounts, where separate SSH host aliases and identities are in use)

## Pull Request Workflow

When creating PRs:

1. Analyze full commit history (not just latest commit)
2. Use `git diff [base-branch]...HEAD` to see all changes
3. Draft comprehensive PR summary
4. Include test plan with TODOs
5. Push with `-u` flag if new branch

> For the full development process (planning, TDD, code review) before git operations, see [development-workflow.md](./development-workflow.md).
