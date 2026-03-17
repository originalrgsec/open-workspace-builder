# Threat Model: Claude Workspace Builder

## Overview

This threat model covers the claude-workspace-builder CLI tool and the content it installs into user workspaces. The primary attack surface is not traditional software vulnerabilities but prompt injection through content files. The builder installs markdown files (agents, commands, rules, skills, templates) that Claude interprets as system-level instructions. A malicious file in this pipeline can cause Claude to exfiltrate data, modify files, bypass user oversight, or establish persistence across sessions.

- [ADR](./adr.md)
- [PRD](./prd.md)

## Methodology

This threat model uses STRIDE per element applied to the data flow diagrams defined in the ADR. Risk is scored using a likelihood x impact matrix aligned with NIST SP 800-30 Rev. 1 (Guide for Conducting Risk Assessments). Mitigations map to NIST SP 800-53 Rev. 5 control families where applicable, establishing traceability for SOC 2 and future compliance needs.

## System Scope

### In Scope

- The builder CLI tool and its Python codebase
- All content files the builder installs: ECC agents, commands, rules; custom skills (SKILL.md, scripts); vault templates; context file templates; CLAUDE.md
- The ECC upstream update workflow (fetch, diff, scan, accept/reject)
- The migration workflow (diff existing vault, apply changes)
- The security scanner module (all three layers)
- The reputation ledger and its data
- CI pipeline security scan on pull requests
- Collaborator contributions via GitHub PRs

### Out of Scope

- Claude Code or Cowork platform security (Anthropic's responsibility)
- Obsidian application security
- The user's local filesystem security posture
- Network security during git fetch operations (relies on git/SSH/HTTPS transport security)
- The upstream ECC repo's own CI/CD pipeline

### Data Classification Summary

| Classification | Data Elements | Regulatory Applicability |
|---------------|---------------|-------------------------|
| Restricted | User's populated context files (about-me.md, brand-voice.md, working-style.md) containing PII, career history, clearance status | Privacy, potential clearance implications |
| Confidential | Security scanner verdicts, reputation ledger (reveals what was flagged and why) | Internal operational data |
| Internal | Vault structure, project names, template content | Business-sensitive |
| Public | Builder source code, ECC vendored content (MIT licensed), vault templates (no user data) | Open source |

## Trust Boundaries

| ID | Boundary | Crosses | Enforcement |
|----|----------|---------|-------------|
| TB-1 | Upstream ECC repo — Vendored copy | Third-party markdown content entering the builder's trusted content store | Security scanner (all three layers), manual review, pinned versioning |
| TB-2 | Collaborator PR — Main branch | Contributor code and content entering the mainline | GitHub branch protection, CI security scan, owner review |
| TB-3 | Builder output — User workspace | Generated files entering the user's trusted working environment | User runs the builder explicitly; dry-run mode available |
| TB-4 | Vendored content — Claude execution context | Installed agents/commands/rules being interpreted by Claude as instructions | Security scanner pre-installation; user's responsibility post-install |
| TB-5 | Migration source — User workspace | New reference content being merged into an existing user workspace | Interactive accept/reject per file, security scan on all new content |

## STRIDE Analysis

### Element: ECC Upstream Fetch (DF-1)
**Type:** data flow
**DFD Reference:** DF-1 (ECC Update Flow)

| STRIDE Category | Applicable? | Threat Description | Threat ID |
|----------------|-------------|-------------------|-----------|
| **S**poofing | Yes | Attacker compromises the ECC GitHub account or performs a man-in-the-middle on git fetch, delivering malicious content that appears to come from the legitimate maintainer | T-001 |
| **T**ampering | Yes | Attacker modifies ECC content between upstream commit and local fetch (git transport tampering, or compromised GitHub Actions injecting content into releases) | T-002 |
| **R**epudiation | Yes | ECC maintainer pushes malicious content and later force-pushes to remove evidence. No local audit trail of what was offered vs. what was accepted | T-003 |
| **I**nformation Disclosure | No | The fetch itself does not expose user data | -- |
| **D**enial of Service | Yes | ECC repo becomes unavailable, blocking updates. Not a security threat but an availability concern | T-004 |
| **E**levation of Privilege | No | The fetch process runs with user permissions only | -- |

### Element: Vendored Content Store (DS-1)
**Type:** data store
**DFD Reference:** DS-1

| STRIDE Category | Applicable? | Threat Description | Threat ID |
|----------------|-------------|-------------------|-----------|
| **S**poofing | No | Local filesystem, authenticated by OS | -- |
| **T**ampering | Yes | An attacker with local filesystem access (or a compromised dependency) modifies vendored content after it passes the security scan but before the next build | T-005 |
| **R**epudiation | Yes | Changes to vendored content are not integrity-checked at build time unless explicitly verified | T-006 |
| **I**nformation Disclosure | No | Vendored content is public (MIT licensed) | -- |
| **D**enial of Service | No | Local filesystem | -- |
| **E**levation of Privilege | No | Files are user-owned | -- |

### Element: Security Scanner — Semantic Analysis (P-1)
**Type:** process
**DFD Reference:** P-1

| STRIDE Category | Applicable? | Threat Description | Threat ID |
|----------------|-------------|-------------------|-----------|
| **S**poofing | No | The scanner is invoked locally | -- |
| **T**ampering | Yes | A malicious content file is specifically crafted to evade the semantic analysis prompt. Adversarial prompt engineering against the reviewer: the file contains instructions that, when read by the reviewing Claude instance, cause it to report the file as clean | T-007 |
| **R**epudiation | No | Scanner output is logged | -- |
| **I**nformation Disclosure | Yes | The file content is sent to Claude API for analysis. If the file contains sensitive data (unlikely for ECC content, possible for user-contributed skills), that data is transmitted to Anthropic | T-008 |
| **D**enial of Service | Yes | Scanner depends on Claude API availability. API outage blocks security review, which blocks updates | T-009 |
| **E**levation of Privilege | Yes | If the semantic analysis runs in the same Claude session as the user's workspace (not sandboxed), a malicious file could influence the session context | T-010 |

### Element: Installed Content in User Workspace (DS-2)
**Type:** data store
**DFD Reference:** DS-2

| STRIDE Category | Applicable? | Threat Description | Threat ID |
|----------------|-------------|-------------------|-----------|
| **S**poofing | No | Local filesystem | -- |
| **T**ampering | Yes | Post-installation, a malicious agent/rule instructs Claude to modify other installed content files, establishing persistence. For example, an agent that appends instructions to CLAUDE.md or modifies other agent definitions | T-011 |
| **R**epudiation | Yes | Claude-initiated file modifications may not be logged or attributed to the originating agent/rule | T-012 |
| **I**nformation Disclosure | Yes | A malicious agent instructs Claude to read sensitive files (context files with PII, SSH keys, credentials, env files) and exfiltrate them via curl, clipboard, or by embedding them in code output | T-013 |
| **D**enial of Service | Yes | A malicious rule degrades Claude's performance by injecting conflicting instructions, wasting tokens on hidden processing, or instructing Claude to refuse legitimate user requests | T-014 |
| **E**levation of Privilege | Yes | A malicious agent instructs Claude to execute arbitrary shell commands, install packages, modify system files, or grant itself permissions the user did not intend | T-015 |

### Element: Collaborator PR (DF-2)
**Type:** data flow
**DFD Reference:** DF-2 (Contribution Flow)

| STRIDE Category | Applicable? | Threat Description | Threat ID |
|----------------|-------------|-------------------|-----------|
| **S**poofing | Yes | Collaborator's GitHub account is compromised. Attacker submits a PR that appears to come from a trusted contributor | T-016 |
| **T**ampering | Yes | Collaborator submits a PR that modifies content files (agents, skills, templates) to include malicious instructions, either intentionally or because their local machine is compromised | T-017 |
| **R**epudiation | No | GitHub PR history provides full audit trail | -- |
| **I**nformation Disclosure | No | PRs are to a public repo | -- |
| **D**enial of Service | No | Bad PRs can be rejected | -- |
| **E**levation of Privilege | Yes | A PR modifies CI configuration to disable security scanning, or modifies the security scanner itself to whitelist malicious patterns | T-018 |

### Element: Reputation Ledger (DS-3)
**Type:** data store
**DFD Reference:** DS-3

| STRIDE Category | Applicable? | Threat Description | Threat ID |
|----------------|-------------|-------------------|-----------|
| **S**poofing | No | Local file | -- |
| **T**ampering | Yes | Attacker modifies the reputation ledger to clear flag history, preventing the threshold-based drop recommendation from triggering | T-019 |
| **R**epudiation | No | Ledger is append-only by design | -- |
| **I**nformation Disclosure | Yes | The ledger reveals what content was flagged and why, which could help an attacker craft evasion strategies if they gain read access | T-020 |
| **D**enial of Service | No | Local file | -- |
| **E**levation of Privilege | No | Data file, not executable | -- |

### Element: Skill Evaluator — Local Model Execution (P-2, v2)
**Type:** process
**DFD Reference:** P-2

| STRIDE Category | Applicable? | Threat Description | Threat ID |
|----------------|-------------|-------------------|-----------|
| **S**poofing | Yes | Attacker substitutes a trojanized Ollama model (Mistral Small or Llama 3.2) that produces systematically biased evaluations, approving malicious skills or rejecting legitimate ones | T-021 |
| **T**ampering | Yes | Attacker modifies the weight_vectors.yaml configuration to skew dimension weights so that a malicious skill scores above the incorporation threshold despite poor precision or high defect rate | T-022 |
| **R**epudiation | Yes | Evaluation results are manipulated after scoring but before the incorporate/reject decision is recorded. No integrity chain between score computation and metadata persistence | T-023 |
| **I**nformation Disclosure | No | Evaluator processes skill content only, no user data | -- |
| **D**enial of Service | Yes | Ollama crashes or hangs during evaluation (model OOM on M1 Pro, corrupted model weights), blocking the evaluation pipeline indefinitely | T-024 |
| **E**levation of Privilege | Yes | A malicious SKILL.md contains instructions that, when fed to Mistral Small for test generation, cause the model to produce test cases that execute arbitrary code on the host during the runner phase | T-025 |

### Element: Skill Metadata Store (DS-4, v2)
**Type:** data store
**DFD Reference:** DS-4

| STRIDE Category | Applicable? | Threat Description | Threat ID |
|----------------|-------------|-------------------|-----------|
| **S**poofing | No | Local filesystem | -- |
| **T**ampering | Yes | Attacker modifies skill-meta.json to inflate scores for a malicious skill or clear the superseded_by field of a deprecated skill, causing it to be re-incorporated | T-026 |
| **R**epudiation | No | Metadata is timestamped | -- |
| **I**nformation Disclosure | No | Contains only skill evaluation data | -- |
| **D**enial of Service | No | Local filesystem | -- |
| **E**levation of Privilege | No | Data file, not executable | -- |

## Risk Assessment

Risk scoring follows NIST SP 800-30 Rev. 1. Each identified threat is rated on likelihood and impact, producing an overall risk level.

### Likelihood Scale (NIST SP 800-30 Table H-2)

| Level | Value | Description |
|-------|-------|-------------|
| Very High | 10 | Adversary is almost certain to initiate, or occurs routinely |
| High | 8 | Adversary is highly likely to initiate |
| Moderate | 5 | Adversary is somewhat likely to initiate |
| Low | 2 | Adversary is unlikely to initiate |
| Very Low | 0 | Adversary is highly unlikely to initiate |

### Impact Scale (NIST SP 800-30 Table H-3)

| Level | Value | Description |
|-------|-------|-------------|
| Very High | 10 | Catastrophic adverse effect on operations, assets, or individuals |
| High | 8 | Severe adverse effect |
| Moderate | 5 | Serious adverse effect |
| Low | 2 | Limited adverse effect |
| Very Low | 0 | Negligible adverse effect |

### Risk Matrix

| | Impact: Very Low (0) | Low (2) | Moderate (5) | High (8) | Very High (10) |
|---|---|---|---|---|---|
| **Likelihood: Very High (10)** | Low | Moderate | High | Very High | Very High |
| **High (8)** | Low | Moderate | High | High | Very High |
| **Moderate (5)** | Low | Low | Moderate | High | High |
| **Low (2)** | Low | Low | Low | Moderate | Moderate |
| **Very Low (0)** | Low | Low | Low | Low | Low |

### Threat Register

| Threat ID | Threat | STRIDE | Element | Likelihood | Impact | Risk Level | Mitigation ID |
|-----------|--------|--------|---------|-----------|--------|-----------|---------------|
| T-001 | ECC account compromise / MITM | S | DF-1 | Low (2) | High (8) | Moderate | M-001, M-002 |
| T-002 | Git transport tampering | T | DF-1 | Very Low (0) | High (8) | Low | M-001 |
| T-003 | ECC maintainer pushes malicious content then covers tracks | R | DF-1 | Low (2) | High (8) | Moderate | M-003, M-004 |
| T-005 | Local filesystem tampering of vendored content | T | DS-1 | Very Low (0) | High (8) | Low | M-005 |
| T-007 | Adversarial evasion of semantic scanner | T | P-1 | Moderate (5) | Very High (10) | High | M-006, M-007 |
| T-008 | Sensitive data in scanned files sent to Claude API | I | P-1 | Low (2) | Moderate (5) | Low | M-008 |
| T-010 | Non-sandboxed scanner session context pollution | E | P-1 | High (8) | High (8) | High | M-009 |
| T-011 | Malicious agent establishes persistence via file modification | T | DS-2 | Moderate (5) | Very High (10) | High | M-006, M-010 |
| T-013 | Data exfiltration via malicious agent instructions | I | DS-2 | Moderate (5) | Very High (10) | High | M-006, M-010, M-011 |
| T-015 | Arbitrary command execution via malicious agent | E | DS-2 | Moderate (5) | Very High (10) | High | M-006, M-010 |
| T-016 | Compromised collaborator account | S | DF-2 | Low (2) | High (8) | Moderate | M-012, M-013 |
| T-017 | Malicious collaborator PR (intentional or compromised machine) | T | DF-2 | Low (2) | Very High (10) | Moderate | M-012, M-013, M-006 |
| T-018 | PR disables security scanning or modifies scanner to whitelist | E | DF-2 | Low (2) | Very High (10) | Moderate | M-014 |
| T-019 | Reputation ledger tampering | T | DS-3 | Very Low (0) | Moderate (5) | Low | M-015 |
| T-020 | Reputation ledger information disclosure | I | DS-3 | Very Low (0) | Low (2) | Low | M-015 |
| T-021 | Trojanized Ollama model producing biased evaluations | S | P-2 | Low (2) | High (8) | Moderate | M-016 |
| T-022 | Tampered weight vectors skewing evaluation scores | T | P-2 | Low (2) | Moderate (5) | Low | M-014, M-017 |
| T-023 | Evaluation result manipulation before persistence | R | P-2 | Very Low (0) | Moderate (5) | Low | M-017 |
| T-024 | Ollama crash/OOM blocking evaluation pipeline | D | P-2 | Moderate (5) | Low (2) | Low | M-018 |
| T-025 | Malicious SKILL.md causing code execution via test generation | E | P-2 | Low (2) | Very High (10) | Moderate | M-006, M-019 |
| T-026 | Skill metadata tampering to inflate scores or resurrect deprecated skills | T | DS-4 | Very Low (0) | Moderate (5) | Low | M-017 |

## Mitigations

### M-001: Pinned Vendoring with Commit Hash Tracking

- **Threat(s) addressed:** T-001, T-002
- **Description:** ECC content is vendored at a specific commit hash. The builder never pulls content at build time. Updates are explicit, deliberate operations (`cwb ecc update`) that produce a diff for review. The vendored copy includes the upstream commit hash in a metadata file for traceability.
- **NIST 800-53 Control:** CM-2 Baseline Configuration, SA-12 Supply Chain Protection
- **Implementation:** `vendor/ecc/` directory with `vendor/ecc/.upstream-meta.json` tracking repo URL, commit hash, date fetched, and last scan results
- **Status:** planned
- **Residual risk:** If the upstream repo is compromised between the user's last update and the next, the user will be offered malicious content during the next `cwb ecc update`. The security scanner (M-006) is the compensating control.

### M-002: Git Signature Verification (Future)

- **Threat(s) addressed:** T-001
- **Description:** If the ECC maintainer signs commits, the builder can verify signatures during `cwb ecc update`. This is a future enhancement contingent on the upstream repo adopting signed commits.
- **NIST 800-53 Control:** SC-8 Transmission Confidentiality and Integrity
- **Implementation:** Deferred. Monitor upstream for GPG/SSH signing adoption.
- **Status:** planned (deferred)
- **Residual risk:** Without signature verification, account compromise remains undetectable at the git layer. The security scanner is the primary control.

### M-003: Local Audit Trail for ECC Updates

- **Threat(s) addressed:** T-003
- **Description:** Every `cwb ecc update` operation logs the full diff (offered changes), the security scan results, and the accept/reject decision per file. This log persists locally even if the upstream repo is force-pushed.
- **NIST 800-53 Control:** AU-3 Content of Audit Records, AU-6 Audit Record Review
- **Implementation:** `vendor/ecc/.update-log.jsonl` — append-only JSON lines file recording each update operation
- **Status:** planned
- **Residual risk:** Local log can be tampered with by someone with filesystem access (addressed by M-015).

### M-004: Reputation Ledger with Threshold-Based Drop

- **Threat(s) addressed:** T-003
- **Description:** The builder maintains a ledger of security flag events per upstream source. Each entry records the file, flag type, severity, and disposition (forked, marked malicious, false positive). If a source exceeds a configurable threshold of confirmed malicious flags, the builder recommends dropping the upstream and freezing on the last known-good copy.
- **NIST 800-53 Control:** SA-12 Supply Chain Protection, RA-5 Vulnerability Monitoring and Scanning
- **Implementation:** `~/.cwb/reputation-ledger.jsonl` stored in user's home directory (not in the repo)
- **Status:** planned
- **Residual risk:** Threshold is a judgment call. Too low produces false positives; too high lets repeated low-severity issues accumulate.

### M-005: Build-Time Integrity Check for Vendored Content

- **Threat(s) addressed:** T-005, T-006
- **Description:** The builder computes and stores content hashes for all vendored files at scan/accept time. At build time, it re-verifies hashes before installing content. Any mismatch halts the build with an integrity error.
- **NIST 800-53 Control:** SI-7 Software, Firmware, and Information Integrity
- **Implementation:** `vendor/ecc/.content-hashes.json` generated during `cwb ecc update`, verified during `cwb init` and `cwb migrate`
- **Status:** planned
- **Residual risk:** An attacker who modifies both the content and the hash file defeats this control. Mitigated by filesystem permissions and user awareness.

### M-006: Three-Layer Security Scanner

- **Threat(s) addressed:** T-007, T-011, T-013, T-015, T-017
- **Description:** All content files (ECC updates, collaborator PRs, migration additions) pass through a three-layer security scan before acceptance. Layer 1: Structural validation (file type, size, encoding, Unicode anomalies). Layer 2: Pattern matching against known-bad indicators (external URLs, shell commands, sensitive file paths, stealth keywords, self-modification references, encoded payloads). Layer 3: Sandboxed semantic analysis (a separate Claude instance reviews the file for prompt injection, behavioral manipulation, and social engineering).
- **NIST 800-53 Control:** SI-3 Malicious Code Protection, RA-5 Vulnerability Monitoring and Scanning, CA-8 Penetration Testing (adversarial test suite)
- **Implementation:** `claude_workspace_builder/security/` module with `structural.py`, `patterns.py`, `semantic.py`, and `scanner.py` orchestrator. Pattern library stored as data (`security/patterns.yaml`). Adversarial test suite in `tests/security/`.
- **Status:** planned
- **Residual risk:** Adversarial evasion of the semantic layer (T-007) remains the highest residual risk. See M-007.

### M-007: Adversarial Test Suite for Scanner

- **Threat(s) addressed:** T-007
- **Description:** The test suite includes deliberately crafted malicious files designed to evade each scanner layer. These test prompt injection variants, Unicode tricks, encoded payloads, stealth keywords in natural language context, and multi-file attack chains (where no single file is malicious but the combination is). The test suite is expanded whenever a new evasion technique is discovered.
- **NIST 800-53 Control:** CA-8 Penetration Testing
- **Implementation:** `tests/security/adversarial/` directory with categorized test cases and expected verdicts
- **Status:** planned
- **Residual risk:** Novel evasion techniques will succeed until they are discovered and added to the test suite. This is inherent to any signature/pattern-based detection system.

### M-008: Content-Only Scanning (No User Data in Scan Payload)

- **Threat(s) addressed:** T-008
- **Description:** The semantic scanner receives only the file content and a fixed analysis prompt. No user context, vault data, or filesystem paths are included in the scan payload. The scanner runs as a stateless, context-free analysis.
- **NIST 800-53 Control:** SC-7 Boundary Protection, AC-4 Information Flow Enforcement
- **Implementation:** The scanner constructs a minimal prompt containing only the file content and analysis instructions. No session context, no user identity, no vault paths.
- **Status:** planned
- **Residual risk:** The file content itself may contain identifying information if it is a user-contributed skill or template. This is acceptable because the content is what we are scanning.

### M-009: Sandboxed Scanner Execution

- **Threat(s) addressed:** T-010
- **Description:** The semantic analysis layer runs in a separate Claude instance (subagent or API call) with no access to the user's filesystem, vault, or session context. The scanner instance receives only the file content and returns only the verdict. It cannot execute commands, read files, or influence the user's session.
- **NIST 800-53 Control:** SC-39 Process Isolation, SC-7 Boundary Protection
- **Implementation:** Scanner uses Claude API with a minimal system prompt. No tool use enabled. Response is parsed as structured data (JSON verdict).
- **Status:** planned
- **Residual risk:** Relies on Claude API's isolation guarantees. If the API response parsing has injection vulnerabilities (e.g., the verdict JSON contains executable content that gets eval'd), isolation is defeated. Mitigation: strict JSON schema validation on scanner output.

### M-010: Pattern Detection for Self-Modification and Persistence

- **Threat(s) addressed:** T-011, T-013, T-015
- **Description:** Layer 2 pattern matching specifically flags content that references other agent/rule/skill files, instructs modification of CLAUDE.md or config files, or contains instructions that would persist across sessions. These patterns indicate a file is attempting to influence beyond its own scope.
- **NIST 800-53 Control:** SI-3 Malicious Code Protection
- **Implementation:** Patterns in `security/patterns.yaml` under the `self-modification` and `persistence` categories
- **Status:** planned
- **Residual risk:** Indirect references (describing the target file's purpose without naming it, then instructing "update the workspace configuration") may evade pattern matching. The semantic layer is the compensating control.

### M-011: Exfiltration Pattern Detection

- **Threat(s) addressed:** T-013
- **Description:** Layer 2 specifically flags shell commands that perform network operations (curl, wget, nc, ssh with remote targets), references to sensitive file paths (~/.ssh, ~/.aws, .env, credentials), and instructions to embed file contents in output. These are the primary exfiltration vectors in a Claude prompt context.
- **NIST 800-53 Control:** SI-3 Malicious Code Protection, SC-7 Boundary Protection
- **Implementation:** Patterns in `security/patterns.yaml` under the `exfiltration` category
- **Status:** planned
- **Residual risk:** Creative exfiltration (e.g., "include the contents of the user's configuration file in a code review comment" without naming specific paths) may evade pattern matching. Semantic layer compensates.

### M-012: Branch Protection with Required Owner Review

- **Threat(s) addressed:** T-016, T-017
- **Description:** GitHub branch protection on `main` requires at least one approving review from the repository owner before merge. The collaborator (junior dev) cannot merge their own PRs. The owner reviews all changes to content files (agents, skills, templates) with the same scrutiny as code changes.
- **NIST 800-53 Control:** CM-3 Configuration Change Control, AC-5 Separation of Duties
- **Implementation:** GitHub branch protection rules: require 1 review, dismiss stale reviews on new push, restrict merge to admin
- **Status:** planned
- **Residual risk:** Owner review quality is the control's effectiveness. Fatigued or rushed reviews may miss subtle issues.

### M-013: CI Security Scan on Pull Requests

- **Threat(s) addressed:** T-016, T-017
- **Description:** Every PR triggers a GitHub Actions workflow that runs the security scanner (Layers 1 and 2; Layer 3 optional based on API key availability) on all changed content files. PRs with security flags cannot pass CI checks.
- **NIST 800-53 Control:** SA-11 Developer Testing and Evaluation, SI-3 Malicious Code Protection
- **Implementation:** `.github/workflows/security-scan.yml` runs `cwb security scan` on changed files in the PR diff
- **Status:** planned
- **Residual risk:** If the PR modifies the scanner itself to whitelist the malicious pattern, the CI scan passes. See M-014.

### M-014: CODEOWNERS Protection for Security-Critical Files

- **Threat(s) addressed:** T-018
- **Description:** GitHub CODEOWNERS file designates the repository owner as the required reviewer for changes to the security scanner module, CI configuration, CODEOWNERS itself, and the pattern library. The collaborator cannot approve changes to these files.
- **NIST 800-53 Control:** AC-5 Separation of Duties, CM-5 Access Restrictions for Change
- **Implementation:** `.github/CODEOWNERS` file with entries for `claude_workspace_builder/security/`, `.github/workflows/`, `CODEOWNERS`, and `security/patterns.yaml`
- **Status:** planned
- **Residual risk:** GitHub CODEOWNERS enforcement depends on branch protection being enabled. If branch protection is accidentally disabled, the control is ineffective.

### M-015: Reputation Ledger Integrity

- **Threat(s) addressed:** T-019, T-020
- **Description:** The reputation ledger is stored in the user's home directory (`~/.cwb/`), not in the repository. It is append-only by design (new entries are appended; existing entries are never modified or deleted by the tool). The ledger file permissions are set to user-read-write only (600).
- **NIST 800-53 Control:** AU-9 Protection of Audit Information
- **Implementation:** Ledger write operations append only. File created with 0600 permissions. The builder warns if permissions have been modified.
- **Status:** planned
- **Residual risk:** A user with filesystem access can still modify the file. This is acceptable — the user is the trust anchor in this threat model.

### M-016: Ollama Model Integrity Verification (v2)

- **Threat(s) addressed:** T-021
- **Description:** The evaluator verifies Ollama model identity by checking the model digest hash returned by the Ollama API against a known-good value stored in the builder's configuration. If the digest does not match, the evaluator refuses to run. Models are pulled only from the official Ollama registry. Chinese-origin models (DeepSeek, Qwen) are excluded from the allowed model list entirely.
- **NIST 800-53 Control:** SI-7 Software, Firmware, and Information Integrity
- **Implementation:** Model digest verification in `evaluator/manager.py` before loading. Allowed model list in configuration with digest pinning.
- **Status:** planned
- **Residual risk:** A sophisticated supply-chain attack on the Ollama registry itself could serve a trojanized model with a valid-looking digest. This is low likelihood given Ollama's distribution model.

### M-017: Evaluation Metadata Integrity (v2)

- **Threat(s) addressed:** T-022, T-023, T-026
- **Description:** Weight vector configuration (`weight_vectors.yaml`) is protected by CODEOWNERS (requires owner review to modify). Skill metadata files include a SHA-256 hash of the score computation inputs (test results + weights), allowing re-verification. The evaluator logs all score computations to an append-only evaluation log.
- **NIST 800-53 Control:** AU-3 Content of Audit Records, SI-7 Software/Firmware/Info Integrity
- **Implementation:** CODEOWNERS entry for `evaluator/data/`. Hash chain in skill-meta.json. Evaluation log at `.cwb/evaluation-log.jsonl`.
- **Status:** planned
- **Residual risk:** An attacker with filesystem access can modify both the metadata and the log. Acceptable because the user is the trust anchor.

### M-018: Ollama Resource Management and Timeout (v2)

- **Threat(s) addressed:** T-024
- **Description:** The evaluator wraps all Ollama API calls with configurable timeouts (default 120 seconds per call). If a model fails to load or hangs during inference, the evaluator catches the timeout, explicitly runs `ollama stop <model>`, logs the failure, and returns an evaluation error rather than blocking indefinitely. Models are loaded sequentially (Llama 3.2 first, unload, then Mistral Small) to keep peak memory at ~16GB.
- **NIST 800-53 Control:** SC-10 Network Disconnect (adapted: resource disconnect on failure)
- **Implementation:** Timeout wrapper in `evaluator/manager.py`. Sequential model loading with explicit `ollama stop` between models and on batch completion.
- **Status:** planned
- **Residual risk:** If Ollama itself deadlocks (kernel-level GPU hang), the Python timeout may not fire. User can manually kill the process.

### M-019: Pre-Evaluation Security Scan (v2)

- **Threat(s) addressed:** T-025
- **Description:** Every SKILL.md passes through the three-layer security scanner (M-006) before being fed to the evaluator. This catches malicious instructions that could manipulate test generation. The test runner executes generated test prompts in a controlled context with no shell access, no filesystem write, and no network access beyond the Ollama local endpoint.
- **NIST 800-53 Control:** SI-3 Malicious Code Protection, SC-39 Process Isolation
- **Implementation:** Scanner invocation in `evaluator/manager.py` before classification. Test runner sandboxing constraints enforced by the runner implementation.
- **Status:** planned
- **Residual risk:** Subtle prompt injection that passes the scanner (T-007 residual) could still influence test generation. The test runner's sandboxing is the compensating control.

## Residual Risk Summary

| Threat ID | Original Risk | Mitigation | Residual Risk | Accepted? | Accepted By |
|-----------|--------------|------------|--------------|-----------|-------------|
| T-007 | High | M-006, M-007 | Moderate | Yes | Owner — novel evasion is inherent; adversarial test suite is the ongoing control |
| T-010 | High | M-009 | Low | Yes | Owner — sandboxed execution with no tool use provides strong isolation |
| T-011 | High | M-006, M-010 | Moderate | Yes | Owner — pattern + semantic detection catches known variants; novel approaches require test suite expansion |
| T-013 | High | M-006, M-010, M-011 | Moderate | Yes | Owner — exfiltration patterns are well-characterized; creative indirect exfiltration is the residual |
| T-015 | High | M-006, M-010 | Moderate | Yes | Owner — same residual as T-011 and T-013 |
| T-018 | Moderate | M-014 | Low | Yes | Owner — CODEOWNERS + branch protection is strong; only fails if both are disabled simultaneously |
| T-021 | Moderate | M-016 | Low | Yes | Owner — digest pinning + official registry makes model substitution unlikely |
| T-025 | Moderate | M-006, M-019 | Low | Yes | Owner — pre-evaluation scan + sandboxed test runner limits attack surface |

## Assumptions and Dependencies

- Claude API provides adequate isolation between separate API calls. A malicious file analyzed in one call cannot influence the response of a subsequent call.
- Git HTTPS/SSH transport provides integrity protection for fetched content. We do not independently verify content beyond what git provides.
- The user's local filesystem is trusted. If an attacker has arbitrary write access to the user's machine, the threat model is moot.
- Claude Code and Cowork do not execute agent/rule files as code. They are interpreted as natural language instructions. If a future Claude version adds code execution from these files, the threat model must be revised.
- The ECC upstream repo is maintained in good faith. The reputation ledger and security scanner are controls against compromise, not assumption of malice.
- Ollama models pulled from the official registry have not been tampered with. The digest pinning (M-016) provides a detection control but relies on the initial pull being from a trusted source.
- Local Ollama inference is isolated from network access. A compromised model cannot exfiltrate data unless it influences the evaluator's output in a way that triggers network activity by another component.

## Review Schedule

This threat model should be reviewed when:

- The architecture changes (new content sources, new installation paths, new integration points)
- A security incident occurs involving this system or the ECC upstream
- The security scanner is modified (new layers, changed patterns, different sandboxing approach)
- New prompt injection techniques are published (MITRE ATLAS, academic research, security community disclosures)
- At minimum quarterly, given the rapidly evolving nature of LLM security

Next scheduled review: 2026-06-16

## NIST Control Mapping Summary

| Control ID | Control Name | Family | Mitigations | Status |
|-----------|-------------|--------|-------------|--------|
| AC-4 | Information Flow Enforcement | Access Control | M-008 | planned |
| AC-5 | Separation of Duties | Access Control | M-012, M-014 | planned |
| AU-3 | Content of Audit Records | Audit | M-003 | planned |
| AU-6 | Audit Record Review | Audit | M-003 | planned |
| AU-9 | Protection of Audit Information | Audit | M-015 | planned |
| CA-8 | Penetration Testing | Assessment | M-007 | planned |
| CM-2 | Baseline Configuration | Config Mgmt | M-001 | planned |
| CM-3 | Configuration Change Control | Config Mgmt | M-012 | planned |
| CM-5 | Access Restrictions for Change | Config Mgmt | M-014 | planned |
| RA-5 | Vulnerability Monitoring and Scanning | Risk Assessment | M-004, M-006 | planned |
| SA-11 | Developer Testing and Evaluation | Acquisition | M-013 | planned |
| SA-12 | Supply Chain Protection | Acquisition | M-001, M-004 | planned |
| SC-7 | Boundary Protection | Sys/Comm Protection | M-008, M-009, M-011 | planned |
| SC-8 | Transmission Confidentiality and Integrity | Sys/Comm Protection | M-002 | planned (deferred) |
| SC-39 | Process Isolation | Sys/Comm Protection | M-009 | planned |
| SI-3 | Malicious Code Protection | Sys/Info Integrity | M-006, M-010, M-011, M-013 | planned |
| SC-10 | Network Disconnect | Sys/Comm Protection | M-018 | planned |
| SI-7 | Software/Firmware/Info Integrity | Sys/Info Integrity | M-005, M-016, M-017 | planned |

## Links

- [ADR](./adr.md)
- [PRD](./prd.md)
- [SDR](./sdr.md)
