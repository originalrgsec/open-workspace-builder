# First Run: Existing Vault

This guide walks through running OWB against an existing Obsidian vault for the first time. If you do not have an existing vault, see [First Run: Fresh](getting-started/first-run-fresh.md) instead.

The approach is conservative: build against a disposable copy, verify everything, then repeat on the live vault.

## Understanding the Workspace Layout

OWB builds a **workspace** that contains a vault as a subdirectory. When deciding where to target the build, the key constraint is that Claude Code CLI finds `.claude/` by traversing upward from wherever you start a session. If your workspace root is a parent of your code projects, every CLI session in those projects will inherit the ECC content.

A typical layout looks like this:

```
~/workspace/                      <-- build target
├── .claude/                      <-- ECC agents, commands, rules (deployed by OWB)
│   ├── agents/
│   ├── commands/
│   └── rules/
├── .skills/                      <-- custom skills (Cowork only)
│   └── skills/
├── Obsidian/                     <-- your vault (directly under workspace root)
├── about-me.md                   <-- context files (deployed by OWB)
├── brand-voice.md
├── working-style.md
├── code-project-a/               <-- CLI sessions here find .claude/ above
└── code-project-b/
```

If your code projects live outside the workspace root, CLI sessions in those directories will not find `.claude/`. See Troubleshooting for options.

## Prerequisites

**0. Your vault MUST be backed up to a Git remote before proceeding.**

OWB's migrate command modifies vault files in place. If something goes wrong, you need a known-good snapshot to restore from. A local copy (Step 1 below) protects against accidental changes during the test run, but only a pushed Git remote protects against the live migration in Step 8.

If your vault is not already under Git version control, initialize it now:

```bash
cd /path/to/your/vault
git init
git add -A
git commit -m "vault snapshot: pre-OWB first run"
git remote add origin <your-remote-url>
git push -u origin main
```

If your vault is already synced to a remote (e.g., via the [obsidian-git](https://github.com/denolehov/obsidian-git) plugin), verify the remote is current:

```bash
cd /path/to/your/vault
git log origin/main -1 --format="Remote last commit: %ci"
git status --short | head -20
```

If there are uncommitted local changes, push them before proceeding. Do not run OWB against a vault whose latest state is not on the remote.

**1. OWB is installed and on PATH.**

```bash
owb --version
```

If using a CLI wrapper, verify that too:

```bash
<wrapper> --version
```

If not installed, activate your project venv first (e.g., `source ~/projects/Code/.venv/bin/activate` for the shared workspace venv), then:

```bash
cd /path/to/open-workspace-builder && pip install -e .
```

**2. (Optional) An LLM API key is available.**

Layer 3 semantic scanning and evaluator operations require a model backend. For a first run, Layers 1 and 2 are sufficient. ECC deployment does not require an API key.

```bash
echo $ANTHROPIC_API_KEY   # or whatever provider you configured
```

**3. You know where your live vault is.**

```bash
LIVE_VAULT="/path/to/your/vault"
ls "$LIVE_VAULT/_bootstrap.md"
```

## Step 1: Copy the Vault

Create a disposable copy. Everything in this guide runs against the copy first. If anything goes wrong, delete it and start over.

```bash
WORK_DIR=$(mktemp -d)
TEST_VAULT="$WORK_DIR/vault-copy"
cp -R "$LIVE_VAULT" "$TEST_VAULT"
```

**Verify:** `ls "$TEST_VAULT/_bootstrap.md"` returns the file.

## Step 2: Review Config

OWB reads its config from `~/.<cli_name>/config.yaml`. If you are using a CLI wrapper,
the wrapper installs pre-baked defaults on first invocation.

If no config exists yet, run any `owb` command (e.g., `owb --version`) to generate the default,
then edit `~/.owb/config.yaml` to set:

- `vault.name` to your vault directory name (e.g., `Obsidian`)
- `vault.parent_dir` to empty (vault sits directly under workspace root)
- `ecc.enabled` to `true` if you want ECC deployed

**Verify:** `cat ~/.owb/config.yaml` shows your vault structure reflected in the config.

## Step 3: Dry Run

Preview the build without writing anything.

```bash
owb init -t "$WORK_DIR/test-workspace" --dry-run
```

Review the output for vault directories, ECC content, custom skills, and context templates. Confirm the structure matches your expectations.

**Verify:** `ls "$WORK_DIR/test-workspace"` fails (directory was not created).

## Step 4: Build

```bash
owb init -t "$WORK_DIR/test-workspace"
```

**Verify:**

```bash
# Vault structure
ls "$WORK_DIR/test-workspace/<vault_parent_dir>/<vault_name>/"

# ECC content (if enabled)
ls "$WORK_DIR/test-workspace/<config_dir>/agents/"
ls "$WORK_DIR/test-workspace/<config_dir>/commands/"
ls "$WORK_DIR/test-workspace/<config_dir>/rules/"

# Custom skills
ls "$WORK_DIR/test-workspace/.skills/skills/"

# Workspace config file
head -20 "$WORK_DIR/test-workspace/<config_dir>/<config_filename>"
```

Replace `<vault_name>`, `<config_dir>`, and `<config_filename>` with values from your config (defaults: `Obsidian`, `.ai`, `WORKSPACE.md`). CLI wrappers may override these defaults (e.g., `.claude`, `CLAUDE.md`). The vault deploys directly under the workspace root (no intermediate parent directory).

**Note:** Context files (about-me.md, brand-voice.md, working-style.md) are deployed as stubs if they do not already exist. If they exist, `owb init` skips them. Run `owb context status <target>` to check their fill state, or `owb context migrate <target>` to add missing template sections.

**Note:** Cross-project policies (product-development-workflow, development-process, integration-verification-policy, oss-health-policy, allowed-licenses) are deployed to `Obsidian/code/`. These are process guidance documents consumed by ECC agents. If `content/policies/` is empty or missing, this step is skipped gracefully.

## Step 5: Diff

Compare your existing vault against the reference state OWB would produce.

```bash
owb diff "$TEST_VAULT"
```

Output categories:

- **Missing** — files OWB wants to create that do not exist
- **Outdated** — files that exist but differ from the reference
- **Modified** — files you have customized

Exit code 0 = no gaps. Exit code 1 = gaps exist. Gaps are expected on a first run.

Save for detailed review:

```bash
owb diff "$TEST_VAULT" -o "$WORK_DIR/diff-report.json"
python3 -m json.tool "$WORK_DIR/diff-report.json" | less
```

**Verify:** Every missing or outdated file is something you expect OWB to add or update. No surprises.

## Step 6: Migrate (Interactive)

Apply changes interactively. OWB prompts for each file with its diff and security scan result.

```bash
owb migrate "$TEST_VAULT"
```

Accept files you are comfortable with. Reject anything unexpected. Files blocked by security scanning cannot be accepted.

**Verify:**

```bash
owb diff "$TEST_VAULT"
# Exit code 0 = fully converged
```

## Step 7: Validate

Before touching the live vault, run these checks against the migrated copy:

```bash
# Security scan
owb security scan "$TEST_VAULT" -o "$WORK_DIR/security-report.json"
echo "Exit code: $?"   # 0 = clean, 2 = issues

# Bootstrap intact
head -30 "$TEST_VAULT/_bootstrap.md"

# Spot-check project status files
head -10 "$TEST_VAULT/projects/<tier>/<project>/status.md"
```

Also open the vault copy in Obsidian and check for broken links.

**Verify:** Security scan clean. Bootstrap and status files intact. No broken links in Obsidian.

## Step 8: Apply to Live Vault

Once the test run is clean, repeat Steps 5-7 against the live vault.

**Make a timestamped backup first:**

```bash
BACKUP_DIR="$HOME/vault-backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
cp -R "$LIVE_VAULT" "$BACKUP_DIR/vault-backup-$TIMESTAMP"
```

Then:

```bash
owb diff "$LIVE_VAULT" -o /tmp/live-diff-report.json
owb migrate "$LIVE_VAULT"
owb diff "$LIVE_VAULT"            # confirm converged
owb security scan "$LIVE_VAULT"   # confirm clean
```

**Verify:** Diff returns exit code 0. Obsidian opens with no broken links.

## Step 9: Build to Workspace Root

The migrate steps (5-8) update vault content but do not deploy ECC to the workspace root.
This step deploys `.claude/` (or `.ai/`) so CLI sessions pick it up.

**Important:** The target MUST be the workspace root, NOT the vault directory. See
Troubleshooting if you are unsure which directory to use.

```bash
owb init -t /path/to/workspace --dry-run    # preview first
owb init -t /path/to/workspace               # deploy
```

**Verify:**

```bash
ls /path/to/workspace/<config_dir>/agents/
ls /path/to/workspace/<config_dir>/commands/
ls /path/to/workspace/<config_dir>/rules/
```

Replace `<config_dir>` with `.ai` (OWB default) or the value your CLI wrapper uses.

## Step 10: Confirm ECC in Claude Code CLI

Start a new Claude Code CLI session from within the workspace:

```bash
cd /path/to/workspace-root
claude
```

Inside the session:

- Type `/` to check for ECC commands in autocomplete
- Ask Claude to list available agents
- Verify rules are referenced in the system prompt

If ECC is not visible, the session was likely started from outside the workspace tree. See Troubleshooting.

## Step 11: Clean Up

```bash
rm -rf "$WORK_DIR"
```

Keep the backup until you have completed at least one full sprint on the managed vault without issues.

## Troubleshooting

**Tiers not detected.** The scanner looks for directories containing subdirectories with `_index.md` or `status.md`. If your vault uses a different convention, edit the config manually.

**ECC not deployed.** Check the config for `ecc: enabled: true`. OWB disables ECC by default. Enable it in the config or use a CLI wrapper that enables it.

**Security scan blocks a file.** Check flag details in the scan output. For false positives, re-run with `--layers 1,2` to skip semantic analysis.

**Migrate exits with code 2.** At least one file was blocked by security. Review and investigate before proceeding.

**CLI session does not find `.claude/`.** Claude Code traverses upward to find `.claude/`. If code projects are outside the workspace tree, the traversal will not reach it. Options: (a) move code projects under the workspace root, (b) target the build at a common parent directory, (c) symlink `.claude/` into the code project root.

**Migrate blocked by security scanner false positives.** First-party ECC content (agents,
shell scripts) can trigger heuristic flags. If this happens: (a) accept files you recognize
as shipped ECC content, (b) reject anything unrecognized, (c) use `owb migrate --accept-all`
to accept missing files and skip modified ones. Do NOT fall back to `owb init -t <vault>`
as a workaround — see next entry.

**Nested Obsidian/Obsidian/ directory appeared.** This happens when `owb init` targets the
vault directory instead of the workspace root. The `init` command always creates an
`Obsidian/` subdirectory under the target. If the target IS the vault, you get nesting.
Fix: `rm -rf /path/to/vault/Obsidian /path/to/vault/.claude /path/to/vault/.skills /path/to/vault/.ai`.
The correct `init` target is always the workspace root, never the vault. Step 9 uses `init`
for the workspace root; Steps 5-8 use `migrate` for the vault. These are not interchangeable.

**Context files overwritten.** `owb init` detects existing context files (about-me.md,
brand-voice.md, working-style.md) and skips them. However, vault scaffold files
(`_bootstrap.md`, `_templates/`) are currently overwritten without checking. Back up your
vault before any `init` run. Tracked as OWB-S060.
