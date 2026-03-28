# CLI Reference

All commands accept `--help` for detailed usage information.

## `owb init`

Scaffold a new workspace.

```bash
owb init                          # interactive wizard on first run
owb init --from-vault ~/vault     # generate config from existing vault
owb init --no-wizard              # skip wizard, use defaults
owb init --target ~/workspace     # scaffold to a specific directory
owb init --dry-run                # preview without writing files
owb init --config my-config.yaml  # use a pre-written config file
```

On first run, the wizard walks through model provider selection, vault structure, ECC enablement, and security settings, then writes the result to `~/.owb/config.yaml`.

## `owb diff`

Detect workspace drift by comparing an existing workspace against the reference state.

```bash
owb diff ./workspace              # print human-readable report
owb diff ./workspace -o report.json  # also write JSON for automation
```

Reports files that are missing, outdated, modified, or extra (user additions).

## `owb migrate`

Bring an existing workspace up to date. Each changed file is reviewed interactively unless `--accept-all` is used.

```bash
owb migrate ./workspace           # interactive review
owb migrate ./workspace --accept-all  # batch mode
owb migrate ./workspace --dry-run     # preview without writing
```

Files that fail the security scanner are blocked from migration.

## `owb security scan`

Run the three-layer content scanner on files or directories.

```bash
owb security scan ./path              # scan file or directory
owb security scan ./path --layers 1,2 # structural + pattern only
owb security scan ./path -o report.json  # write JSON report
```

Layers: 1 (structural), 2 (pattern), 3 (semantic/LLM). Layer 3 requires the `llm` package extra and a configured model.

## `owb update`

Update content from named upstream sources.

```bash
owb update ecc                    # update ECC source
owb update <source>               # update any configured source
owb ecc update                    # backward-compatible alias
owb ecc update --accept-all       # auto-accept clean files
owb ecc status                    # show pinned commit, flag history
```

## `owb eval`

Evaluate skills using the multi-stage pipeline: classify, generate tests, execute, score, decide.

```bash
owb eval ./path/to/skill              # evaluate a new skill
owb eval ./path/to/skill --compare    # compare against existing version
```

## `owb audit`

Run supply chain and license audits.

```bash
owb audit deps                        # pip-audit + GuardDog scan
owb audit package <name>              # audit a single package before install
owb audit licenses                    # check dependency licenses
owb audit check-suppressions          # review suppression registry
```

## `owb auth`

Manage API keys and authentication credentials.

```bash
owb auth setup                        # configure API key via secrets backend
owb auth google                       # run Google OAuth flow for Sheets export
owb auth google-store                 # store Google OAuth client credentials
```

`owb auth google-store` accepts `--client-id` and `--client-secret` flags, encrypts them via the configured secrets backend, then `owb auth google` runs the OAuth InstalledAppFlow to obtain refresh tokens.

## `owb validate`

Validate skill files against the AgentSkills specification.

```bash
owb validate ./path/to/skill          # validate a single skill
owb validate ./skills/                # validate all skills in directory
```

## `owb metrics`

Token consumption tracking, cost analysis, and budget management.

### `owb metrics tokens`

Report token consumption and API-equivalent costs from Claude Code session files.

```bash
owb metrics tokens                                # full report, text format
owb metrics tokens --format json                  # JSON output
owb metrics tokens --since 20260301 --until 20260331  # date range filter
owb metrics tokens --project myproject            # filter by project name
owb metrics tokens --claude-dir ~/.claude         # custom Claude data dir
```

### `owb metrics export`

Export token data to Google Sheets or Excel.

```bash
owb metrics export --format gsheets --sheet-id SHEET_ID   # Google Sheets
owb metrics export --format xlsx --output report.xlsx     # Excel file
owb metrics export --format gsheets --sheet-id ID --since 20260301
```

Google Sheets export requires the `[sheets]` extra and configured OAuth credentials (see `owb auth google`). Excel export requires the `[xlsx]` extra.

### `owb metrics record`

Record session costs to a local JSONL ledger. Designed to be called from a Claude Code session-end hook.

```bash
owb metrics record                                # record all sessions
owb metrics record --story OWB-S076               # tag with story ID
owb metrics record --ledger ~/.owb/data/ledger.jsonl  # custom ledger path
owb metrics record --claude-dir ~/.claude         # custom Claude data dir
```

Skips sessions already in the ledger (deduplicates by session ID).

### `owb metrics sync`

Record sessions and optionally export to Google Sheets in one command. Designed for sprint-close hooks.

```bash
owb metrics sync                                  # record only
owb metrics sync --sheet-id SHEET_ID              # record + export to Sheets
owb metrics sync --story OWB-S076 --sheet-id ID   # tag and export
```

### `owb metrics forecast`

Show monthly cost forecast from ledger data.

```bash
owb metrics forecast                              # text output
owb metrics forecast --format json                # JSON output
owb metrics forecast --current-date 2026-03-28    # override current date
owb metrics forecast --ledger ~/.owb/data/ledger.jsonl
```

Extrapolates month-to-date cost to a projected monthly total based on daily average.

### `owb metrics budget-check`

Check month-to-date cost against a budget threshold. Exits with code 2 if over budget.

```bash
owb metrics budget-check --threshold 200          # check against $200/mo
owb metrics budget-check --threshold 200 --current-date 2026-03-28
```

Exit codes: 0 = under budget, 2 = over budget. Useful in hook scripts.

### `owb metrics by-story`

Show cost breakdown grouped by story ID from ledger data.

```bash
owb metrics by-story                              # text output
owb metrics by-story --format json                # JSON output
owb metrics by-story --since 20260301             # date filter
```

Requires sessions to have been recorded with `--story` tags via `owb metrics record`.

## Global Options

| Flag | Description |
|------|-------------|
| `--config PATH` | Use a specific config file instead of auto-detected |
| `--dry-run` | Preview actions without writing files |
| `--verbose` | Enable detailed output |
| `--version` | Print version and exit |
| `--help` | Show help for any command |

## Optional Dependencies

Install extras for additional functionality:

```bash
pip install "open-workspace-builder[sheets]"  # Google Sheets export
pip install "open-workspace-builder[xlsx]"    # Excel export
pip install "open-workspace-builder[llm]"     # Layer 3 semantic scanner
pip install "open-workspace-builder[mcp]"     # MCP server
```

| Flag | Description |
|------|-------------|
| `--config PATH` | Use a specific config file instead of auto-detected |
| `--dry-run` | Preview actions without writing files |
| `--verbose` | Enable detailed output |
| `--version` | Print version and exit |
| `--help` | Show help for any command |
