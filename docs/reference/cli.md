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

## Global Options

| Flag | Description |
|------|-------------|
| `--config PATH` | Use a specific config file instead of auto-detected |
| `--dry-run` | Preview actions without writing files |
| `--verbose` | Enable detailed output |
| `--version` | Print version and exit |
| `--help` | Show help for any command |
