---
type: policy
scope: all-projects
created: 2026-03-30
updated: 2026-04-19
tags: [policy, security, pii, secrets, encryption, vault]
---

# PII and Secrets Handling Policy

## Purpose

Defines how personally identifiable information (PII) and secrets (API keys, tokens, credentials) are handled across the Obsidian vault, the AI agent's memory system, and all project artifacts produced in this workspace. The governing principle is that PII and secrets must never exist in plaintext in files that are synced, backed up, or accessible to tools without encryption.

Companion documents:

- [[code/allowed-licenses]] — dependency license policy
- [[code/oss-health-policy]] — dependency health evaluation

## Encrypted PII Store

All PII and secret values are stored once in an encrypted file and referenced by identifier from anywhere else in the vault.

**Storage backend (choose one, preference order):**

1. **[himitsubako](https://pypi.org/project/himitsubako/)** (recommended). An age/SOPS wrapper designed for this pattern. The `vault-pii-audit` skill will offer this as the default on first run and will scaffold the store for you.
2. **Direct age + SOPS.** If you prefer to manage the store directly, the encrypted file lives at `.secure/pii_store.yaml.age` in the vault root. Encrypt with `sops -e` or `age -r <recipient>`. Decrypt with `age -d -i <key>` or `sops -d`. `.secure/` must be excluded from any git remote via `.gitignore`.

**Encryption key:** managed by your chosen backend. If you are using direct age, the key file lives outside the vault (e.g., under `~/.config/<project>/`).

**Identifier format:**

- Secrets: `SEC-NNN` (API keys, tokens, credentials, infrastructure URLs that reveal account identity)
- PII: `PII-NNN` (personal names, machine identifiers, addresses, phone numbers, account numbers)

**Many-to-one references:** Each PII / secret value is stored exactly once in the encrypted store. Vault files that originally contained the value are redacted and replaced with `[SEC-NNN]` or `[PII-NNN]` references pointing to the encrypted store. Multiple files can reference the same identifier.

**Refuse fallback (no plaintext inventory):** The `vault-pii-audit` skill will not write a plaintext index of findings. If you decline both himitsubako and direct-age backends, the skill refuses to run rather than falling back to a plaintext inventory. Your options on refusal are: (a) install himitsubako, (b) configure a direct-age backend, or (c) explicitly pass the operator-accepts-plaintext flag to the skill and accept that your findings index is unencrypted.

## What Requires Encryption

### Always Encrypt (Secrets)

| Category | Examples | Detection Pattern |
|----------|----------|-------------------|
| API keys | OpenAI `sk-*`, GitHub `ghp_*` / `gho_*`, Slack `xoxb-*`, AWS `AKIA*` | Prefix matching |
| Auth tokens | OAuth access / refresh tokens, JWT tokens, session cookies | Context: near "token", "bearer", "authorization" |
| Credentials | Passwords, connection strings with embedded passwords | `password=`, `passwd=`, `://user:pass@` |
| Age private keys | `AGE-SECRET-KEY-*` | Prefix matching |
| Service URLs with credentials | URLs containing auth tokens in path or query params | `://token@host`, `?key=`, `?token=` |
| Infrastructure identifiers that reveal account identity | Cloud workspace hostnames, tenant IDs | Context-dependent |

### Always Encrypt (PII)

| Category | Examples | Detection Pattern |
|----------|----------|-------------------|
| Email addresses | Personal email addresses | Email regex (with operator-specified exclusions) |
| Phone numbers | Any format | `\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}` |
| Physical addresses | Street addresses with city/state/zip | Context-dependent |
| Government IDs | SSN, tax ID, passport, driver's license | `\d{3}-\d{2}-\d{4}`, `\d{2}-\d{7}` |
| Financial account numbers | Bank accounts, routing numbers, credit cards | 13-19 consecutive digits, `\d{9}` near "routing" |
| Machine hostnames containing personal names | Terminal prompts with `user@hostname` | `[a-z]+@[A-Z][a-z]+-[A-Z]` patterns in terminal output |
| Local usernames in terminal output | Shell prompts captured in research notes | `username@hostname` patterns |

### Operator-Configured Exclusions

Some strings look like PII to a generic regex but are legitimately non-sensitive for your workspace (company contact emails, attribution emails for open-source tools, etc.). These are configured per-operator during the `vault-pii-audit` first-run interview and stored at `<vault_root>/.owb/pii-profile.yaml` (with an optional per-project override at `<project_root>/.owb/pii-profile.yaml`).

Pre-seeded exclusions that ship with OWB:

| Item | Reason |
|------|--------|
| `noreply@anthropic.com` | Automated attribution for Claude / the Anthropic SDK. Public. |
| GitHub usernames | Public identifiers. |
| Third-party email addresses in code attribution (`@author` tags) | Open source attribution. Public. |

All other exclusions are operator-defined during the interview.

## Detection Patterns (Regex)

These patterns are used by the `vault-pii-audit` skill for automated scanning. The `exclude:` lists are populated from `<vault_root>/.owb/pii-profile.yaml` (and any per-project override) at skill-run time, not hard-coded here.

```yaml
secrets:
  - name: api_key_openai
    pattern: 'sk-[a-zA-Z0-9]{20,}'
  - name: api_key_github
    pattern: '(ghp_[a-zA-Z0-9]{36}|gho_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{80,})'
  - name: api_key_slack
    pattern: 'xox[bpras]-[a-zA-Z0-9-]+'
  - name: api_key_aws
    pattern: 'AKIA[A-Z0-9]{16}'
  - name: api_key_anthropic
    pattern: 'sk-ant-[a-zA-Z0-9-]+'
  - name: bearer_token
    pattern: 'Bearer\s+[a-zA-Z0-9._\-]{20,}'
  - name: age_private_key
    pattern: 'AGE-SECRET-KEY-[A-Z0-9]+'
  - name: connection_string_password
    pattern: '(password|passwd|pwd)\s*[:=]\s*\S+'
  - name: url_with_credentials
    pattern: '://[^@\s]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
  - name: hex_api_key
    pattern: '[a-f0-9]{32,}'
    context_required: true  # Only flag if near "api", "key", "token", "secret", "auth"

pii:
  - name: email_address
    pattern: '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    # exclude: populated from <vault_root>/.owb/pii-profile.yaml
  - name: phone_number
    pattern: '\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
  - name: ssn
    pattern: '\d{3}-\d{2}-\d{4}'
  - name: tax_id
    pattern: '\d{2}-\d{7}'
  - name: credit_card
    pattern: '\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{1,4}\b'
  - name: terminal_prompt_with_name
    pattern: '[a-z]+@[A-Z][a-zA-Z]+-[A-Z]'
```

## Remediation Procedure

When PII or a secret is found in a vault file:

1. **Check the encrypted store.** Does this value already have an identifier? If yes, use that identifier.
2. **Assign an identifier.** If new, assign the next `SEC-NNN` or `PII-NNN` number.
3. **Add to encrypted store.** Add the entry with type, description, value, status, discovery date, and source files.
4. **Redact the source file.** Replace the plaintext value with `[SEC-NNN]` or `[PII-NNN]`. Do not delete surrounding context — the reference should be readable in place.
5. **Update source_files list.** If the value was already in the store but appears in a new file, update the source_files list in the encrypted store.

## Audit Cadence

| Scope | Trigger | Tool |
|-------|---------|------|
| Full vault + agent memory | First run, quarterly, or after bulk imports | `vault-pii-audit` skill (full mode) |
| Session artifacts only | End of every agent session | `vault-pii-audit` skill (session mode) |
| New files only | When processing research inbox or mobile inbox | Integrated into triage workflow |

## Agent Memory Policy

The AI agent's memory system (wherever the agent persists cross-session notes) must not contain PII or secrets. Memory files should reference concepts, patterns, and decisions — not specific personal data. If a memory entry needs to reference a person or credential, use the `[PII-NNN]` / `[SEC-NNN]` identifier, not the value.

## Session Log Policy

Session logs written to `Obsidian/sessions/` are high-risk for PII leakage because they capture conversational context. The `vault-pii-audit` skill runs against session logs at session end. If PII was discussed during the session (which is normal), the session log should describe what was done without reproducing the PII values.

## Review Schedule

Review this policy annually or when:

- A new type of PII is introduced to the workflow
- The encryption key is rotated
- A PII exposure incident occurs

## Links

- PII profile (pattern + exclusion config): `<vault_root>/.owb/pii-profile.yaml`
- Per-project override (optional): `<project_root>/.owb/pii-profile.yaml`
- Encrypted PII store: `.secure/pii_store.yaml.age` (or himitsubako equivalent)
- Vault audit skill: `vault-pii-audit`
