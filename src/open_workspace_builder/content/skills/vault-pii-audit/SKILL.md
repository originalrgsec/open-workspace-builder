---
name: vault-pii-audit
description: Scan the Obsidian vault and the AI agent's memory directories for PII (emails, phone numbers, addresses, government IDs, account numbers) and secrets (API keys, tokens, credentials, private keys). Use this skill at session end, after processing research inbox items, after bulk imports of external content, or whenever the user mentions PII, secrets audit, credential scanning, sensitive data, or redaction. Also use proactively when session logs are written or vault files are modified. Supports two modes — "full" scans everything, "session" scans only current session artifacts.
---

# Vault PII Audit

Scan vault files and the AI agent's memory for PII and secrets, then redact findings by replacing plaintext values with encrypted-store references.

## When This Skill Activates

- End of any session that modified vault files
- After processing research inbox or mobile inbox
- After importing external content (conversation exports, data dumps)
- When the user asks about PII, secrets, credential exposure, or data redaction
- Proactively when session logs are written

## First-Run Setup

The first time the skill is invoked in a workspace it interviews the operator once, records the answers to a **PII profile** file, and uses that profile for every subsequent run. A second run with the profile in place skips the interview.

### Profile location (two-level)

- **Vault default:** `<vault_root>/.owb/pii-profile.yaml`. Created by the first-run interview. Applies to every scan unless a per-project override exists.
- **Per-project override (optional):** `<project_root>/.owb/pii-profile.yaml`. When present, the project-level profile wins for scans scoped to that project. Projects that do not need different settings simply omit this file and inherit the vault default.

`<vault_root>` resolves from (in order):
1. the `--vault-root` CLI flag passed to `scripts/scan.py`;
2. the `OWB_VAULT_ROOT` environment variable, if set;
3. the current working directory, if it contains `_bootstrap.md`.

If none of these resolve, the skill exits with a prompt asking the operator to set `OWB_VAULT_ROOT` or pass `--vault-root`. OWB does not assume a fixed vault location; the user configures it at `owb init` time.

### Interview flow (first run only)

If the vault-level profile does not exist, pause before scanning and ask the operator:

1. **PII element survey.** "What PII elements should I screen for in this vault?" Present the default category list (emails, phone numbers, addresses, government IDs like SSN / tax ID, financial account numbers, terminal-prompt hostnames, machine identifiers) and let the operator keep / drop / add categories. Record the final set under `categories:` in the profile.
2. **Exclusions.** "Are there strings that look like PII but are not sensitive for you?" Common examples: company contact emails, attribution emails, public usernames. Record under `exclusions.emails:`, `exclusions.patterns:`, etc. Pre-seeded exclusions that OWB ships (`noreply@anthropic.com`, `@users.noreply.github.com`, RFC 2606 reserved domains) do not need to be repeated.
3. **Storage backend.** "How should the encrypted PII store be managed?" Offer:
   - **(recommended) himitsubako** — an age / SOPS wrapper. Requires the `himitsubako` package in the operator's Python environment. Best for operators who want the store managed for them.
   - **direct age + SOPS** — operator manages the `.age` file and key material themselves. Best for operators who already have an age / SOPS workflow.
   - **decline both (refuse fallback)** — operator does not want an encrypted store. See **Refuse Fallback** below.
   Record the choice under `storage.backend:` with a value of `himitsubako`, `age`, or `refuse-plaintext`.
4. **himitsubako detection (if chosen).** Probe `python -c "import himitsubako"`. If missing, print the install command (`uv add himitsubako` or `pip install himitsubako`) and pause until the operator confirms install. Do not silently fall back to age.
5. **Age key (if chosen).** Ask for the key file path. Default suggestion: `~/.config/<vault-name>/age-key.txt`. Record under `storage.age_key_path:`.
6. **Write the profile.** Save `<vault_root>/.owb/pii-profile.yaml` with the schema below. Commit it (or `.owb/.gitignore` it) per operator preference — the profile itself contains no secrets, only policy.

### Profile schema

```yaml
# <vault_root>/.owb/pii-profile.yaml
version: 1
categories:
  - email
  - phone
  - address
  - ssn
  - tax_id
  - credit_card
  - terminal_prompt
  # Add / remove categories per the first-run interview.
exclusions:
  emails:
    # noreply@anthropic.com, @users.noreply.github.com, and RFC 2606
    # reserved domains are pre-seeded. Add your own below.
    - info@example.com
  patterns: []  # Raw regex additions (power users only).
storage:
  backend: himitsubako  # or "age" or "refuse-plaintext"
  # For age backend only:
  age_key_path: ~/.config/<vault-name>/age-key.txt
  store_path: .secure/pii_store.yaml.age
```

### Refuse Fallback

If the operator declines both himitsubako and direct age, the skill **refuses to proceed** rather than writing a plaintext findings index. On refuse:

- Print the three recovery paths: install himitsubako, configure a direct-age backend, or re-run the skill with `--accept-plaintext` to explicitly accept an unencrypted findings inventory.
- Exit the skill without scanning.

This matches `pii-handling-policy.md` §Encrypted PII Store "Refuse fallback" clause. The `--accept-plaintext` path is for operators who have audited the decision; it is not a silent default.

## Two Modes

### Full Mode

Scans the entire vault and the AI agent's memory directories. Use for first-run audits, quarterly reviews, or after bulk imports. Invoke: "run a full PII audit" or "scan the vault for secrets".

### Session Mode

Scans only files modified during the current session. Use at session end for ongoing enforcement. Invoke: "run session PII audit" or "check this session for PII".

## How It Works

### Step 1: Determine Scope

**Full mode:** Scan these locations (paths resolve against `<vault_root>` as described above):

- `<vault_root>/` (entire vault, excluding `.obsidian/`, `.smart-env/`, `.secure/`, `.git/`, `.trash/`, `.owb/`, `__pycache__/`, `node_modules/`)
- The AI agent's memory directories. For Claude Code the default is `~/.claude/projects/*/memory/` and `~/.claude/projects/*/MEMORY.md`. Override with `--memory-root` if your agent persists memory elsewhere.

**Session mode:** Scan only files modified in the current session:

- Any vault files written or edited during this session
- Session log if one was written
- Any memory files created or updated

### Step 2: Run Detection Patterns

Invoke `scripts/scan.py` with the resolved vault root and memory root:

```bash
python scripts/scan.py --mode full \
    --vault-root "$VAULT_ROOT" \
    --pii-profile "$VAULT_ROOT/.owb/pii-profile.yaml"
```

The script applies regex patterns for each category enabled in the profile:

**Secrets:**

- API keys: OpenAI (`sk-`), GitHub (`ghp_`, `gho_`, `github_pat_`), Slack (`xox[bpras]-`), AWS (`AKIA`), Anthropic (`sk-ant-`)
- Auth tokens: Bearer tokens, OAuth tokens, JWT tokens
- Private keys: `AGE-SECRET-KEY-`, `-----BEGIN … PRIVATE KEY-----`
- Credentials: connection strings with embedded passwords, `password=`, `://user:pass@`
- High-entropy hex strings (32+ chars) near context words: "api", "key", "token", "secret", "auth"

**PII (conditional on profile `categories:`):**

- Email addresses (honoring `exclusions.emails` from the profile)
- Phone numbers
- Government IDs: SSN (`\d{3}-\d{2}-\d{4}`), tax ID (`\d{2}-\d{7}`)
- Credit card numbers
- Terminal prompts with personal usernames / hostnames

### Step 3: Review Findings

Present findings to the user in a masked table:

```
| # | Type | File | Line | Preview (masked) |
|---|------|------|------|------------------|
| 1 | API key | research/inbox/... | 42 | sk-***...***abc |
| 2 | Email | sessions/... | 15 | j***@gmail.com |
```

Ask the user to confirm which findings should be redacted. Some may be false positives (example patterns in documentation, third-party public emails in attribution). If the operator keeps seeing the same false positive on every run, offer to append it to `exclusions:` in the profile so it is suppressed next time.

### Step 4: Redact Confirmed Findings

For each confirmed finding, follow the backend chosen in the profile:

**himitsubako backend:**

```bash
# Look up or assign an identifier via himitsubako.
hmb get <vault_root>/.secure/pii_store/<identifier>  # check if present
hmb put <vault_root>/.secure/pii_store/<identifier> <value>
```

**Age backend:**

```bash
# Decrypt the store to stdout (never a temp file on disk).
age -d -i <key_path> <vault_root>/.secure/pii_store.yaml.age
# Edit in-memory, re-encrypt via pipeline.
```

In both cases:

1. **Look up or assign an identifier.** Reuse an existing `SEC-NNN` / `PII-NNN` if the value is already tracked; otherwise assign the next sequential number.
2. **Update the encrypted store.** Add a new entry or update the `source_files` list for existing entries.
3. **Redact the source file.** Replace the plaintext value with `[SEC-NNN]` or `[PII-NNN]` via the Edit tool. Preserve surrounding context so the redacted file remains readable in place.
4. **Update the secrets inventory.** If you maintain `.secure/secrets-inventory.md` (optional plaintext metadata index), add or update the row. Inventory values are IDs and status only, never the underlying secret.
5. **Verify the redaction.** Grep the file for the original value to confirm it is gone.

### Step 5: Report

Summarize what was found and what was done:

```
PII Audit Complete (session mode)
- Files scanned: 3
- Findings: 1 (1 redacted, 0 false positives)
- New PII store entries: 0 (reused existing SEC-003)
- Credentials flagged as needs_rotation: 0
```

If any findings have `status: needs_rotation` or `status: active`, remind the user to rotate those credentials.

## Policy Reference

Read `pii-handling-policy.md` (deployed under `code/` in the scaffolded vault) for the full policy including complete detection pattern list, exclusion rules, remediation procedure details, and audit cadence.

## Important Rules

- Never output actual PII or secret values in responses. Mask them (e.g., `sk-***...***abc`, `j***@gmail.com`).
- Never store PII in agent memory files. Use `[PII-NNN]` references if a memory needs to reference a person or credential.
- The `.secure/` directory must be in `.gitignore`. Verify this; scaffold it if missing.
- Temporary decrypted content must not be written to disk. Use shell pipelines or variables.
- When in doubt about whether something is PII, flag it for the user to decide rather than ignoring it.
- The profile at `<vault_root>/.owb/pii-profile.yaml` is policy, not secret material. It is safe to commit to a private vault backup. Do not commit the encrypted store or any key file.
