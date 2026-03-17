# PRD: Claude Workspace Builder

## Business Problem

Setting up a productive Claude Code or Cowork workspace requires assembling multiple independent components: an Obsidian knowledge vault with project templates, context files that calibrate Claude's behavior, ECC agents and commands for development workflows, and custom skills for specialized tasks. There is no standard way to do this. Users who discover one component (e.g., the ECC catalog) often miss others entirely. Users who build workspaces manually accumulate structural drift over time, with no tooling to detect gaps or reconcile against a known-good reference.

A real-world migration test confirmed this: a user who built a vault from a detailed blog post ended up with working context files but zero ECC agents, no custom skills, missing structural scaffolding, and 8 fewer templates than the reference. The ECC catalog was the highest-value component and the hardest to discover without the builder.

The additional problem is trust. The ECC catalog is third-party content (MIT licensed, maintained by an external developer). Agents, commands, and rules are markdown files that act as system prompts for Claude. A compromised or malicious prompt file could instruct Claude to exfiltrate data, modify files, or bypass user oversight. No tooling exists to scan these files for prompt injection or malicious instructions before a user installs them.

## Target Customers

Claude Code and Cowork power users who want a structured, repeatable workspace with project management capabilities. The immediate audience is individual developers and technical professionals. The secondary audience is small teams sharing a common workspace configuration.

### Personas

**Persona 1: Solo Power User**
- Context: Uses Claude Code or Cowork daily for software development, research, and project management. Has multiple active projects. Values structure and repeatability.
- Pain points: Building a workspace from scratch is tedious and error-prone. Keeping up with ECC updates requires manually checking the upstream repo. No way to know if the workspace is drifting from best practices.
- Goals: Run one command to get a fully configured workspace. Periodically sync with upstream improvements without losing customizations. Trust that installed content is safe.

**Persona 2: New Adopter**
- Context: Heard about structured Claude workspaces from a blog post, conference talk, or colleague. Wants to get started quickly without reading a 46K Python file to understand what it does.
- Pain points: The current prototype is a single file with all content inline. The README describes the output structure but not the value proposition for each component. No getting-started guide split by environment (Claude Code vs. Cowork).
- Goals: Install via pip, run one command, understand what was generated and why, start using the workspace within 15 minutes.

**Persona 3: Team Lead / Workspace Maintainer**
- Context: Wants to establish a standard workspace configuration for a team. Needs to customize the default templates, add team-specific skills, and distribute updates.
- Pain points: No fork-and-customize workflow. No way to push workspace updates to team members. No way to audit what content is installed across team members' environments.
- Goals: Fork the builder, add team customizations, distribute via repo clone or private fork, push updates that team members can review and accept incrementally.

## Use Cases

### UC-1: Fresh Workspace Bootstrap

- **Actor:** Solo Power User or New Adopter
- **Trigger:** User installs the tool and runs `cwb init` (or `cwb init --interactive` for guided setup)
- **Flow:** The builder reads the config (defaults or user-provided), generates the full workspace structure (vault, ECC catalog, skills, context templates, CLAUDE.md), and writes it to the target directory. If `--interactive`, the user is prompted for tier names, which ECC components to include, and which skills to install.
- **Outcome:** A fully structured workspace ready for use. Context template files contain placeholder content with instructions for population.

### UC-2: Drift Detection

- **Actor:** Solo Power User or Team Lead
- **Trigger:** User runs `cwb diff <vault-path>` to compare their existing workspace against the current builder reference
- **Flow:** The builder walks the target directory, compares every expected file against the reference (presence, content hash for structural files, version for templates), and produces a gap report. The report categorizes gaps as: missing files, outdated templates, extra files (user additions), and modified files (user customizations).
- **Outcome:** A structured report showing exactly where the workspace has diverged, with recommendations per gap.

### UC-3: Interactive Migration

- **Actor:** Solo Power User
- **Trigger:** User runs `cwb migrate <vault-path>` after reviewing a diff report
- **Flow:** For each gap identified in the diff, the builder presents the change and prompts accept/reject. Missing files are offered for creation. Outdated templates show a diff. Modified files are flagged but never overwritten without explicit consent. A `--accept-all` flag skips interactive prompts. All new or modified content runs through the security scanner before being applied.
- **Outcome:** The workspace is updated to include new reference content while preserving all user customizations. A migration log records every action taken.

### UC-4: ECC Upstream Update

- **Actor:** Solo Power User or Team Lead
- **Trigger:** User runs `cwb ecc update` to pull the latest from the upstream ECC repo
- **Flow:** The builder fetches the latest upstream commit, diffs each file against the pinned vendored copy, runs the three-layer security scan on every changed file, presents results with security flags, and prompts accept/reject per file. Accepted changes update the vendored copy. The reputation ledger is updated.
- **Outcome:** The vendored ECC copy is updated with reviewed, security-scanned changes. Rejected or flagged changes are logged. If the upstream repo exceeds the flag threshold, the builder recommends dropping it.

### UC-5: Security Scan

- **Actor:** Any user, CI pipeline, or pre-commit hook
- **Trigger:** User runs `cwb security scan <path>`, or a PR triggers the CI scan, or a pre-commit hook fires
- **Flow:** The scanner runs three layers on the target files: structural validation (file type, size, encoding), pattern matching (URLs, shell commands, sensitive paths, stealth keywords), and sandboxed semantic analysis (Claude reviews content for prompt injection, behavioral manipulation, and social engineering). Results are returned as a structured report with per-file verdicts: clean, flagged (with specific concerns), or malicious (with evidence).
- **Outcome:** A security report. Flagged or malicious files block the triggering operation (merge, update, migration) until resolved by forking to a safe edit or marking as malicious.

### UC-6: Skill Packaging for Cowork

- **Actor:** Cowork user
- **Trigger:** User runs `cwb package-skills` after a build or independently
- **Flow:** The builder packages each custom skill directory into a `.skill` zip file in the format Cowork expects. The zip includes SKILL.md, any associated scripts, and metadata.
- **Outcome:** Installable `.skill` packages that the user can load through Cowork's skill installation flow.

### UC-7: Skill Evaluation (v2)

- **Actor:** Solo Power User or Team Lead
- **Trigger:** User runs `cwb eval <skill-path>` for a new skill, `cwb eval <skill-path> --compare` for a replacement candidate, or the evaluator is triggered automatically during `cwb ecc update` for new/changed skills
- **Flow:** The Ollama classifier (Llama 3.2) determines the skill type and maps it to a dimension weight vector. The test generator (Mistral Small 22B Q4 on Ollama) creates a tailored test suite or reuses an existing one. The test suite runs against baseline (raw Claude) and the candidate skill. Results are scored across four dimensions (novelty, efficiency, precision/accuracy, defect rate) with type-specific weighting. Composite scores are compared against baseline and any existing duplicative skill. Models are explicitly loaded at evaluation start and unloaded on batch completion to minimize resource consumption.
- **Outcome:** A scored evaluation with composite and per-dimension results. If the candidate exceeds both the baseline and any existing duplicative skill by the incorporation threshold, it is recommended for incorporation. The superseded skill is deprecated. All scores, test suites, and results persist as skill metadata for future comparisons. When a superseded skill is updated upstream, it is automatically re-evaluated against the incumbent.

### UC-8: Vault Versioning (v2)

- **Actor:** Builder (automated)
- **Trigger:** Any `cwb init`, `cwb migrate`, or `cwb ecc update` operation
- **Flow:** The builder writes or updates `.cwb/vault-meta.json` in the workspace with the builder version, timestamp, update count, and source commit hashes. The differ reads this metadata to compare against the specific builder version the vault was built from.
- **Outcome:** Every workspace is version-stamped. Drift detection is version-aware.

## Goals

1. **Goal:** Reduce time-to-productive-workspace from hours to minutes — **Metric:** Time from install to first use — **Target:** Under 5 minutes for default config, under 15 minutes for interactive setup
2. **Goal:** Ensure all installed content passes security review — **Metric:** Percentage of content files scanned before installation — **Target:** 100% of ECC and contributed content scanned; zero unscanned files in any update or migration path
3. **Goal:** Enable non-destructive workspace maintenance — **Metric:** User customizations preserved through update cycles — **Target:** Zero user files overwritten without explicit consent
4. **Goal:** Distribute as an installable Python package via private GitHub repo — **Metric:** Successful install via `pip install git+https://...` on Python 3.10+ across macOS, Linux, Windows — **Target:** Works on all three platforms with zero extra dependencies for core functionality. PyPI distribution is a future option if the project goes public.
5. **Goal:** (v2) Maintain best-of-breed skill selection across multiple sources — **Metric:** Skills incorporated only when they demonstrably outperform baseline and existing alternatives — **Target:** All incorporated skills score above incorporation threshold on composite score vs both baselines

## Non-Goals

- Building a GUI or web interface. This is a CLI tool.
- Managing Claude API keys, billing, or account configuration.
- Replacing Obsidian as a knowledge management tool. The vault is an Obsidian vault; the builder scaffolds it.
- Real-time sync. The builder runs on-demand, not as a daemon.
- Supporting non-Claude AI coding assistants (Cursor, Copilot, etc.). The ECC repo supports these; the builder focuses on Claude.
- Community skill marketplace. Skills are either bundled or user-provided; there is no discovery/install-from-registry flow in v1.
- Using Chinese-origin LLMs (DeepSeek, Qwen, etc.) for any evaluation or classification task. Security risk concern based on differential code quality by prompt language.

## Assumptions

- Users have Python 3.10+ installed. The builder has no compiled dependencies.
- ECC upstream repo (github.com/affaan-m/everything-claude-code) remains publicly accessible and MIT licensed. If it goes private or changes license, the builder freezes on the last known-good vendored copy.
- Claude Code and Cowork's `.claude/` and `.skills/` directory conventions remain stable. Changes to these conventions require builder updates.
- Users are comfortable with CLI tools. The interactive mode lowers the barrier but does not eliminate it.

## Constraints

- Zero required dependencies for core build functionality. Optional dependencies (PyYAML for config, GitPython or subprocess git for ECC updates) are acceptable but must degrade gracefully if missing.
- The security scanner's semantic analysis layer requires a Claude API call or Claude Code subagent. This means the scan has a cost (tokens) and requires either an API key or a Claude Code session. The structural and pattern-matching layers work offline.
- The builder must not modify files outside the target directory. No global system changes.
- All ECC content must carry its upstream MIT license attribution. The builder's own code is separately licensed (MIT, Volcanix LLC copyright).

## Success Criteria

- A user with repo access can `pip install git+https://github.com/VolcanixLLC/claude-workspace-builder.git && cwb init` and have a working workspace.
- A user with an existing workspace can run `cwb diff` and get an accurate gap report on the first try.
- The security scanner catches the adversarial test cases in the test suite (prompt injection, data exfiltration instructions, stealth keywords, Unicode tricks).
- A contributor can submit a PR that passes CI (tests + security scan) without manual intervention from the maintainer for clean content.
- The ECC update workflow produces a clear per-file accept/reject experience with security verdicts visible.

## Open Questions

1. Should the builder support a `cwb ecc pin <commit-hash>` command to lock to a specific upstream version, or is the current "always diff against latest" model sufficient?
2. What is the right threshold for the reputation ledger to recommend dropping an upstream repo? Three confirmed malicious flags? Five? Should it be configurable?
3. Should the semantic security scan be optional (for users without API access) or mandatory? If optional, should the builder warn that structural/pattern checks alone are insufficient?
4. Should the builder generate a `.claude/CLAUDE.md` that references the vault, or should it leave CLAUDE.md management to the user? The current prototype generates one, but some users may have their own.

## Links

- [ADR](./adr.md)
- [SDR](./sdr.md)
- [Threat Model](./threat-model.md)
