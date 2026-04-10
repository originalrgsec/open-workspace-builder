# PRD: Open Workspace Builder

## Business Problem

Setting up a productive Claude Code or Cowork workspace requires assembling multiple independent components: an Obsidian knowledge vault with project templates, context files that calibrate Claude's behavior, ECC agents and commands for development workflows, and custom skills for specialized tasks. There is no standard way to do this. Users who discover one component (e.g., the ECC catalog) often miss others entirely. Users who build workspaces manually accumulate structural drift over time, with no tooling to detect gaps or reconcile against a known-good reference.

A real-world migration test confirmed this: a user who built a vault from a detailed blog post ended up with working context files but zero ECC agents, no custom skills, missing structural scaffolding, and 8 fewer templates than the reference. The ECC catalog was the highest-value component and the hardest to discover without the builder.

The additional problem is trust. The ECC catalog is third-party content (MIT licensed, maintained by an external developer). Agents, commands, and rules are markdown files that act as system prompts for Claude. A compromised or malicious prompt file could instruct Claude to exfiltrate data, modify files, or bypass user oversight. No tooling exists to scan these files for prompt injection or malicious instructions before a user installs them.

## Bootstrap Stages

OWB structures workspace maturity as a four-stage progression. Each stage builds on the security scanning, process discipline, and trust calibration established in the previous stage. Stages are not skipped. The entire point of the progression is to earn the trust required to operate at the next level.

### Stage 0 — Cold Start

The user has no OWB workspace. They are either starting fresh or working from a manually assembled vault that was not built by OWB.

**What happens:** The user installs OWB and runs `owb init`. The setup wizard walks through model provider selection, vault structure, ECC enablement, security settings, and secrets backend configuration. The builder scaffolds the full workspace: knowledge vault, context files, development policies, skills, and a workspace config entry point.

**Exit criteria:**

- `owb init` completes successfully
- Workspace passes `owb diff` with zero missing structural files
- Context files are populated (not stubs)
- At least one project is scaffolded in the vault with a status file and bootstrap entry
- Security scanner is functional (Layers 1-2 operational; Layer 3 configured if API key available)

### Stage 1 — Interactive Operation

The human drives every session. All Claude Code or Cowork sessions are started, directed, and ended by the human. The workspace is fully integrated: the PLC (product lifecycle) and SDLC (software development lifecycle) are executable from the CLI prompt using vault state, ECC agents, and custom skills. OWB handles drift detection, migration, upstream updates, dependency auditing, and security scanning as part of the normal operating rhythm.

**What happens:** The human works interactively across projects. Claude reads the bootstrap file on session start, loads project-specific state, executes work, updates status and session logs at session end. The human manages sprint planning, backlog prioritization, and release decisions. All code-producing sessions require human presence. Scheduled tasks (cron-triggered scans, suppression monitoring) may run unattended, but they produce reports for human review rather than taking autonomous action.

**Exit criteria:**

- Minimum 3 successful sprint cycles completed end-to-end using the OWB-managed PLC/SDLC
- All vault policies passing: development process checklist, integration verification, OSS health checks
- Security scanner has processed at least 50 files with zero false-negative escapes on adversarial test suite
- Dependency SCA and SAST integrated into CI with zero unacknowledged findings
- The human can articulate which decisions they make repeatedly that could be delegated, and which decisions require human judgment. This becomes the input to the Stage 2 delegation policy.

### Stage 2 — Build Farm

The human shifts from driving every session to managing a backlog. A headless build farm runs sandboxed agent sessions coordinated by an orchestrator and a head agent. Sessions execute with pre-authorized tool permissions (no confirmation prompts within the sandbox boundary), but network access is controlled and scoped by configuration. The human communicates with the head agent through a third-party chat interface (Slack, Matrix, or equivalent).

**What the human does:** Design, sprint planning, backlog management, and acceptance review. The human defines what gets built (user stories, acceptance criteria, sprint scope) and reviews what was built (PR review, demo, release sign-off). The human does not start or attend individual build sessions.

**What the system does:** The orchestrator reads the sprint backlog, decomposes stories into tasks, dispatches tasks to sandboxed agent sessions, collects results, runs integration verification, and reports status to the human via the chat channel. Each session runs in an isolated sandbox with controlled filesystem, network, and tool access defined by a sandbox policy. The head agent manages session lifecycle, error recovery, and escalation to the human when a task exceeds its delegation authority.

**OWB's role:** OWB is the security, process, and compliance orchestrator for the build farm. It does not build the sandbox infrastructure or the chat integration itself. OWB defines the policies that govern what agents can and cannot do, evaluates and incorporates agent definitions from external sources (e.g., open-source agent rosters like agency-agents), scans all agent content through the three-layer security pipeline before deployment, and enforces the delegation policy that controls which decisions require human approval.

**Key artifacts OWB manages at this stage:**

- **Sandbox policy** (`sandbox-policy.yaml`): Defines filesystem boundaries, network allowlist, tool permissions, and session timeout for each sandbox tier.
- **Delegation policy** (`delegation-policy.yaml`): Configurable rules defining what the head agent can decide autonomously vs. what requires human escalation. Established through a wizard that walks the human through categories of decisions (architectural, dependency, security, release, financial) and sets thresholds for each.
- **Agent roster** (`agents/`): The set of agent definitions deployed to the build farm. Every agent passes the security scanner and skill evaluator before deployment. OWB tracks provenance (which upstream source, which version, which evaluation score).
- **Session audit log**: Every headless session is logged with inputs, outputs, tool invocations, and security verdicts. The human can query this log at any time.

**Exit criteria:**

- Orchestrator and head agent are operational with at least 2 successful unattended sprint cycles
- Sandbox policy is tested and enforced (agent sessions cannot escape filesystem or network boundaries)
- Delegation policy is calibrated: zero incidents where the agent made a decision that should have been escalated, and zero unnecessary escalations that blocked the build pipeline
- Session audit log is complete and queryable
- The head agent can recover from common failure modes (test failures, build errors, dependency conflicts) without human intervention
- Chat integration is functional: the human receives status updates, can ask questions, and can override decisions through the chat channel

### Stage 3 — Director Model

The single head agent is replaced by a three-tier hierarchy: the human + head agent at the top, director agents in the middle, and specialist teams at the bottom. This stage addresses the capacity limit of Stage 2: a single head agent managing all tasks across all projects becomes a bottleneck as the number of concurrent projects and the complexity of the backlog grow.

**Architecture:**

- **Tier 1 — Human + Head Agent:** The human communicates with director agents through the chat channel. The head agent handles cross-director coordination, resource allocation, and escalation routing.
- **Tier 2 — Director Agents:** Each director agent owns a domain (e.g., backend engineering, frontend, security, documentation, testing). Directors receive assignments from the human or head agent, decompose them into specialist tasks, manage specialist sessions, and report results upstream. Directors sit between the specialist agents and the PLC/SDLC process: they understand the sprint plan, the acceptance criteria, and the integration verification requirements.
- **Tier 3 — Specialist Agents:** The current ECC agents (planner, tdd-guide, code-reviewer, security-reviewer, build-error-resolver, etc.) are demoted to specialists working under director agents. External agent definitions evaluated and incorporated from upstream sources (agency-agents and similar projects) also populate this tier. Specialists execute discrete tasks and report results to their director.

**OWB's role at this stage:**

- **Director agent definition and evaluation:** OWB provides templates for director agent definitions that encode the PLC/SDLC process, delegation rules, and escalation paths. New director agents pass the full evaluation pipeline (classify, test, score, judge) before deployment.
- **Team composition policy** (`team-policy.yaml`): Defines which specialists report to which director, maximum concurrent sessions per director, and fallback routing when a specialist is unavailable.
- **Cross-director coordination rules:** Defines how directors communicate when a task spans domains (e.g., a feature requiring both backend and frontend changes). OWB enforces that cross-domain work follows the integration verification policy.
- **Trust calibration wizard:** Extends the Stage 2 delegation wizard to cover director-level autonomy. The human walks through scenarios specific to each director's domain and sets per-director delegation boundaries.
- **Agent provenance and lineage:** Every agent in every tier is tracked: where it came from, which version, when it was last evaluated, what its security scan verdict was. OWB can produce a full audit report of the agent hierarchy at any time.

**Exit criteria:**

- At least 2 director agents operational with their specialist teams
- Cross-director coordination tested on at least 1 multi-domain feature
- Per-director delegation policies calibrated with zero escalation failures
- Full agent hierarchy audit passes: every agent at every tier has provenance, evaluation score, and security verdict
- The human's involvement is limited to design, sprint planning, backlog management, acceptance review, and exception handling. Build execution runs autonomously.

### Stage Progression Rules

1. **No skipping.** Each stage builds the security posture, process discipline, and trust calibration required for the next. A user who has not completed Stage 1's exit criteria does not have the operational maturity to run a Stage 2 build farm safely.
2. **OWB tracks current stage.** The workspace config records which stage the workspace is operating at. OWB commands surface stage-appropriate guidance. Running `owb init` produces a Stage 0 workspace; graduating to Stage 1 is implicit once exit criteria are met. Stage 2 and 3 graduation requires explicit `owb stage promote` with a checklist verification.
3. **Stages are preserved.** OWB does not deprecate lower stages. A Stage 3 workspace can still run interactive Stage 1 sessions. The human can always drop to a lower stage for debugging, experimentation, or sensitive work.
4. **Sprints are tagged by stage.** The vault's sprint metadata includes which stage the sprint was executed at. Multiple sprints occur within a stage. The stage defines the operating model; the sprint defines the work unit.

## Target Customers

Individual developers and technical professionals who use AI coding assistants (Claude Code, Cowork, or model-agnostic equivalents) and want a structured, repeatable workspace with built-in security scanning and policy enforcement.

> **Note (DRN-066, 2026-04-09):** OWB is scoped to solo developers. Personas 3-5 and Stages 2-3 are historical — they describe capabilities extracted to a separate Volcanix commercial product. They are preserved here as design context.

### Personas

**Persona 1: Solo Power User**
- Context: Uses Claude Code or Cowork daily for software development, research, and project management. Has multiple active projects. Values structure and repeatability.
- Pain points: Building a workspace from scratch is tedious and error-prone. Keeping up with ECC updates requires manually checking the upstream repo. No way to know if the workspace is drifting from best practices.
- Goals: Run one command to get a fully configured workspace. Periodically sync with upstream improvements without losing customizations. Trust that installed content is safe.

**Persona 2: New Adopter**
- Context: Heard about structured Claude workspaces from a blog post, conference talk, or colleague. Wants to get started quickly without reading a 46K Python file to understand what it does.
- Pain points: The current prototype is a single file with all content inline. The README describes the output structure but not the value proposition for each component. No getting-started guide split by environment (Claude Code vs. Cowork).
- Goals: Install via pip, run one command, understand what was generated and why, start using the workspace within 15 minutes.

**Persona 3: Team Lead / Workspace Maintainer** *(historical — out of scope per DRN-066)*
- Context: Wants to establish a standard workspace configuration for a team. Needs to customize the default templates, add team-specific skills, and distribute updates.
- Pain points: No fork-and-customize workflow. No way to push workspace updates to team members. No way to audit what content is installed across team members' environments.
- Goals: Fork the builder, add team customizations, distribute via repo clone or private fork, push updates that team members can review and accept incrementally.

**Persona 4: Build Farm Operator** *(historical — out of scope per DRN-066)*
- Context: Has completed multiple successful interactive sprint cycles and wants to shift from driving every session to managing a backlog. Comfortable with sandboxed execution and has the infrastructure (or is willing to build it) for headless agent sessions.
- Pain points: The bottleneck is human attention, not agent capability. Every session requires the human to start it, monitor it, and close it. Sprint velocity is capped by the number of hours the human can sit at a terminal.
- Goals: Define the work (stories, acceptance criteria), let the build farm execute it, review results asynchronously through a chat channel. Maintain full audit trail and the ability to intervene at any time.

**Persona 5: Multi-Agent Team Operator** *(historical — out of scope per DRN-066)*
- Context: Operating a Stage 2 build farm successfully but hitting capacity limits. The single head agent cannot efficiently manage tasks across multiple domains simultaneously. The operator wants to delegate domain-specific coordination to director agents.
- Pain points: Task decomposition and specialist routing is a bottleneck at the head-agent level. Cross-domain features require manual coordination. The operator spends time on routing decisions that a domain-aware director could handle.
- Goals: Stand up a director-specialist hierarchy where each director owns a domain, manages its specialists, and coordinates with other directors on cross-domain work. The operator's role is design, planning, and exception handling.

## Use Cases

### UC-1: Fresh Workspace Bootstrap

- **Actor:** Solo Power User or New Adopter
- **Trigger:** User installs the tool and runs `owb init` (or `owb init --interactive` for guided setup)
- **Flow:** The builder reads the config (defaults or user-provided), generates the full workspace structure (vault, ECC catalog, skills, context templates, CLAUDE.md), and writes it to the target directory. If `--interactive`, the user is prompted for tier names, which ECC components to include, and which skills to install.
- **Outcome:** A fully structured workspace ready for use. Five cross-project development policies are installed to Obsidian/code/. Context template files contain placeholder content with instructions for population.

### UC-2: Drift Detection

- **Actor:** Solo Power User
- **Trigger:** User runs `owb diff <vault-path>` to compare their existing workspace against the current builder reference
- **Flow:** The builder walks the target directory, compares every expected file against the reference (presence, content hash for structural files, version for templates), and produces a gap report. The report categorizes gaps as: missing files, outdated templates, extra files (user additions), and modified files (user customizations).
- **Outcome:** A structured report showing exactly where the workspace has diverged, with recommendations per gap.

### UC-3: Interactive Migration

- **Actor:** Solo Power User
- **Trigger:** User runs `owb migrate <vault-path>` after reviewing a diff report
- **Flow:** For each gap identified in the diff, the builder presents the change and prompts accept/reject. Missing files are offered for creation. Outdated templates show a diff. Modified files are flagged but never overwritten without explicit consent. A `--accept-all` flag skips interactive prompts. All new or modified content runs through the security scanner before being applied.
- **Outcome:** The workspace is updated to include new reference content while preserving all user customizations. A migration log records every action taken.

### UC-4: ECC Upstream Update

- **Actor:** Solo Power User
- **Trigger:** User runs `owb ecc update` to pull the latest from the upstream ECC repo
- **Flow:** The builder fetches the latest upstream commit, diffs each file against the pinned vendored copy, runs the three-layer security scan on every changed file, presents results with security flags, and prompts accept/reject per file. Accepted changes update the vendored copy. The reputation ledger is updated.
- **Outcome:** The vendored ECC copy is updated with reviewed, security-scanned changes. Rejected or flagged changes are logged. If the upstream repo exceeds the flag threshold, the builder recommends dropping it.

### UC-5: Security Scan

- **Actor:** Any user, CI pipeline, or pre-commit hook
- **Trigger:** User runs `owb security scan <path>`, or a PR triggers the CI scan, or a pre-commit hook fires
- **Flow:** The scanner runs three layers on the target files: structural validation (file type, size, encoding), pattern matching (URLs, shell commands, sensitive paths, stealth keywords), and sandboxed semantic analysis (Claude reviews content for prompt injection, behavioral manipulation, and social engineering). Optional `--sca` flag adds dependency vulnerability scanning (pip-audit + GuardDog). Optional `--sast` flag adds Semgrep static analysis on source code. Results are returned as a structured report with per-file verdicts: clean, flagged (with specific concerns), or malicious (with evidence). SCA and SAST findings appear in separate report sections.
- **Outcome:** A security report. Flagged or malicious files block the triggering operation (merge, update, migration) until resolved by forking to a safe edit or marking as malicious. Critical SCA findings or SAST errors block trust tier T0 assignment.

### UC-6: Skill Evaluation — New Skill

- **Actor:** Solo Power User
- **Trigger:** User runs `owb eval <skill-path>` to evaluate a new skill before incorporating it
- **Flow:** The evaluator classifies the skill type, generates a tailored test suite, executes tests against both a baseline (raw LLM) and the skill-augmented LLM, scores each on four dimensions (novelty, efficiency, precision, defect_rate), computes weighted composites, and decides whether to incorporate or reject.
- **Outcome:** An evaluation result with per-dimension scores, composite delta vs baseline, and an incorporate/reject decision with reasoning.

### UC-7: Skill Evaluation — Update Existing

- **Actor:** Solo Power User
- **Trigger:** User runs `owb eval <skill-path> --compare` to evaluate an updated version of an existing skill
- **Flow:** The evaluator loads the existing test suite and stored scores, executes the existing tests against the new version, compares scores with the stored results, and decides whether to replace, keep, or reject.
- **Outcome:** A decision to deprecate-and-replace (new version is better), reject (new version is worse), or keep existing (within threshold).

### UC-8: Multi-Source Update

- **Actor:** Solo Power User
- **Trigger:** User runs `owb update <source>` to pull updates from a named upstream source
- **Flow:** The updater discovers files in the source according to configured glob patterns, runs a repo-level security audit (checking for hooks dirs, setup scripts, event triggers), presents results for review, and applies accepted changes. Each source is independently configured with its own repo URL, pin, and discovery rules.
- **Outcome:** The local copy of the source is updated with reviewed, security-audited changes. Backward-compatible: `owb ecc update` still works as an alias.

### UC-9: Context File Lifecycle

- **Actor:** Solo Power User or New Adopter
- **Trigger:** User runs `owb init` (deploys stubs), `owb context status` (checks fill state), or `owb context migrate` (reformats existing files)
- **Flow:** During `owb init`, the builder checks if context files (about-me.md, brand-voice.md, working-style.md) already exist at the target. Existing files are skipped with a message. Missing files receive template stubs with placeholder text. The workspace config file includes a "First Session Tasks" section that instructs the assistant to check for unfilled context stubs and initiate a guided dialogue. `owb context status` reports whether each file is missing, a stub, or filled. `owb context migrate` compares existing files against the latest template, identifies missing sections, and offers interactive reformatting.
- **Outcome:** Context files are never overwritten without consent. Stubs are filled interactively during the first assistant session. Existing files can be reformatted to match new template sections without losing content.

### UC-10: Dependency Supply Chain Audit

- **Actor:** Any user, CI pipeline
- **Trigger:** User runs `owb audit deps`, `owb audit package <name>`, or `owb audit check-suppressions`
- **Flow:** `owb audit deps` scans installed packages against the OSV vulnerability database via pip-audit, with optional `--deep` flag to add GuardDog heuristic malware detection. `owb audit package <name>` runs both pip-audit and GuardDog against a single package before installation. An ECC rule enforces running this scan before any pip/uv install command in Claude Code sessions. `owb audit check-suppressions` queries the OSV API to check whether upstream fixes have landed for suppressed CVEs. A weekly CI job (suppression-monitor.yml) opens GitHub issues when fixes become available.
- **Outcome:** Known vulnerabilities and malicious code patterns are detected before dependencies enter the environment. Suppressed CVEs are automatically tracked and flagged for action when patches ship.

### UC-11: Stage Promotion *(Stage 1 → 2, Stage 2 → 3)* — *historical, out of scope per DRN-066*

- **Actor:** Build Farm Operator or Multi-Agent Team Operator
- **Trigger:** User runs `owb stage promote` after believing they have met exit criteria for their current stage
- **Flow:** OWB evaluates the exit criteria checklist for the current stage. For Stage 1 → 2: verifies sprint cycle count, vault policy compliance, scanner coverage, SCA/SAST integration, and prompts the user to define an initial delegation policy through an interactive wizard. For Stage 2 → 3: verifies unattended sprint cycles, sandbox enforcement, delegation calibration, audit log completeness, and prompts for director agent definitions and team composition. Unmet criteria are reported with specific remediation guidance.
- **Outcome:** The workspace stage is promoted and recorded in config. Stage-appropriate templates, policies, and scaffolding are deployed. If criteria are unmet, the user receives a clear report of what remains.

### UC-12: Delegation Policy Configuration *(Stage 2+)* — *historical, out of scope per DRN-066*

- **Actor:** Build Farm Operator
- **Trigger:** User runs `owb delegation wizard` or `owb delegation edit`
- **Flow:** The wizard walks the user through categories of decisions: architectural (new dependency, API design, schema change), security (CVE response, secrets rotation, scanner override), release (version bump, changelog, tag), financial (API cost thresholds, compute budget). For each category, the user sets a delegation level: autonomous (agent decides), inform (agent decides and notifies), approve (agent proposes, human approves), or escalate (agent stops and asks). Thresholds can be numeric (e.g., "approve any dependency addition with fewer than 100 GitHub stars") or categorical.
- **Outcome:** A `delegation-policy.yaml` is written to the workspace. The head agent and director agents reference this policy when deciding whether to proceed autonomously or escalate. The policy is version-controlled and auditable.

### UC-13: Agent Roster Ingestion *(Stage 2+)* — *historical, out of scope per DRN-066*

- **Actor:** Build Farm Operator or Multi-Agent Team Operator
- **Trigger:** User runs `owb agents ingest <source>` to evaluate and incorporate agent definitions from an external project
- **Flow:** OWB clones or fetches the source repository, discovers agent definition files using configured glob patterns, runs the three-layer security scan on every agent file, runs the skill evaluator to classify and score each agent, and presents a ranked list with security verdicts and evaluation scores. The user accepts or rejects each agent. Accepted agents are copied to the workspace agent roster with provenance metadata (source repo, commit hash, evaluation score, scan verdict, ingestion date).
- **Outcome:** The agent roster is populated with security-scanned, evaluated agent definitions from external sources. Provenance is tracked for audit. Rejected agents are logged with reasons.

### UC-14: Sandbox Policy Configuration *(Stage 2+)* — *historical, out of scope per DRN-066*

- **Actor:** Build Farm Operator
- **Trigger:** User runs `owb sandbox wizard` or edits `sandbox-policy.yaml` directly
- **Flow:** The wizard walks the user through sandbox boundary definitions: filesystem mount points (read-only source, read-write workspace, no access to host home directory), network allowlist (package registries, Git remotes, API endpoints), tool permissions (which CLI tools are available inside the sandbox), session timeout, and resource limits (CPU, memory, disk). Multiple sandbox tiers can be defined (e.g., "build" for code-producing sessions, "scan" for security-only sessions, "research" for web-accessing sessions).
- **Outcome:** A `sandbox-policy.yaml` is written. The orchestrator references this policy when launching headless sessions. Sessions that attempt to exceed their sandbox boundary are terminated and logged.

### UC-15: Director Agent Definition *(Stage 3)* — *historical, out of scope per DRN-066*

- **Actor:** Multi-Agent Team Operator
- **Trigger:** User runs `owb director create <domain>` or defines a director agent manually using OWB's director template
- **Flow:** OWB provides a director agent template that encodes the PLC/SDLC process awareness, delegation rules, specialist routing logic, and escalation paths. The user customizes the template for a specific domain (e.g., backend engineering, testing, documentation). The completed director definition passes the full evaluation pipeline (classify, test, score, judge) and three-layer security scan. OWB generates the team composition config linking the director to its specialist agents.
- **Outcome:** A director agent is deployed to the agent roster with its specialist team defined. The director can receive task assignments from the head agent, decompose them into specialist tasks, and manage execution within its domain.

## Goals

### Stage 0-1 Goals

1. **Goal:** Reduce time-to-productive-workspace from hours to minutes — **Metric:** Time from install to first use — **Target:** Under 5 minutes for default config, under 15 minutes for interactive setup
2. **Goal:** Ensure all installed content passes security review — **Metric:** Percentage of content files scanned before installation — **Target:** 100% of ECC and contributed content scanned; zero unscanned files in any update or migration path
3. **Goal:** Enable non-destructive workspace maintenance — **Metric:** User customizations preserved through update cycles — **Target:** Zero user files overwritten without explicit consent
4. **Goal:** Distribute as an installable Python package — **Metric:** Successful install via `pip install git+https://...` on Python 3.10+ across macOS, Linux, Windows — **Target:** Works on all three platforms with zero extra dependencies for core functionality

### Stage 2-3 Goals *(historical — out of scope per DRN-066)*

> The following goals describe capabilities extracted to the Volcanix commercial platform. They are preserved as design context.

5. **Goal:** Enable unattended build execution with human oversight — **Metric:** Percentage of sprint tasks completed without human intervention during execution — **Target:** 80%+ of tasks complete autonomously; remaining 20% escalated cleanly
6. **Goal:** Enforce sandbox boundaries on headless sessions — **Metric:** Sandbox escape attempts detected and blocked — **Target:** 100% of boundary violations caught; zero successful escapes
7. **Goal:** Provide complete audit trail for unattended sessions — **Metric:** Session log completeness — **Target:** Every tool invocation, file modification, and decision point logged with timestamp and context
8. **Goal:** Enable domain-specialized agent coordination — **Metric:** Cross-director handoff success rate — **Target:** 95%+ of cross-domain tasks completed without human routing intervention
9. **Goal:** Maintain full agent hierarchy provenance — **Metric:** Agents with complete provenance records — **Target:** 100% of agents at all tiers have source, version, evaluation score, and security verdict on record

## Non-Goals

- Building a GUI or web interface. OWB is a CLI tool.
- Multi-user or team workflows. OWB is designed for individual developers (see DRN-066). Team collaboration, build farms, and multi-agent orchestration are served by a separate Volcanix commercial product.
- Building sandbox infrastructure or orchestrators. OWB defines policies; infrastructure is a separate concern.
- Managing Claude API keys, billing, or account configuration.
- Replacing Obsidian as a knowledge management tool. The vault is an Obsidian vault; the builder scaffolds it.
- Real-time sync. The builder runs on-demand, not as a daemon.
- Community skill marketplace. Skills are either bundled or user-provided; there is no discovery/install-from-registry flow.

## Assumptions

- Users have Python 3.10+ installed. The builder has no compiled dependencies.
- ECC upstream repo (github.com/affaan-m/everything-claude-code) remains publicly accessible and MIT licensed. If it goes private or changes license, the builder freezes on the last known-good vendored copy.
- Claude Code and Cowork's `.claude/` and `.skills/` directory conventions remain stable. Changes to these conventions require builder updates.
- Users are comfortable with CLI tools. The interactive mode lowers the barrier but does not eliminate it.

## Constraints

- Zero required dependencies for core build functionality. Optional dependencies (PyYAML for config, GitPython or subprocess git for ECC updates) are acceptable but must degrade gracefully if missing.
- The security scanner's semantic analysis layer requires a Claude API call or Claude Code subagent. This means the scan has a cost (tokens) and requires either an API key or a Claude Code session. The structural and pattern-matching layers work offline.
- The builder must not modify files outside the target directory. No global system changes.
- All ECC content must carry its upstream MIT license attribution. The builder's own code is separately licensed under MIT.

## Success Criteria

- A user with repo access can `pip install git+https://github.com/originalrgsec/open-workspace-builder.git && owb init` and have a working workspace.
- A user with an existing workspace can run `owb diff` and get an accurate gap report on the first try.
- The security scanner catches the adversarial test cases in the test suite (prompt injection, data exfiltration instructions, stealth keywords, Unicode tricks).
- A contributor can submit a PR that passes CI (tests + security scan) without manual intervention from the maintainer for clean content.
- The ECC update workflow produces a clear per-file accept/reject experience with security verdicts visible.

## Open Questions

### Stage 0-1

1. Should the builder support a `owb ecc pin <commit-hash>` command to lock to a specific upstream version, or is the current "always diff against latest" model sufficient?
2. What is the right threshold for the reputation ledger to recommend dropping an upstream repo? Three confirmed malicious flags? Five? Should it be configurable?
3. Should the semantic security scan be optional (for users without API access) or mandatory? If optional, should the builder warn that structural/pattern checks alone are insufficient?
4. Should the builder generate a `.claude/CLAUDE.md` that references the vault, or should it leave CLAUDE.md management to the user? The current prototype generates one, but some users may have their own.

### Stage 2

5. Which orchestrator framework should OWB evaluate and recommend? Candidates include agency-agents, hermes-paperclip-adapter, and other multi-agent coordination projects. OWB's OSS health pipeline and security scanner should evaluate these before any adoption decision.
6. What is the right sandbox technology? Docker containers, lightweight VMs (Firecracker, gVisor), or a managed service? The answer likely depends on the user's infrastructure. OWB should define the policy interface and remain sandbox-implementation-agnostic.
7. How should the delegation policy handle novel decision categories that the wizard did not anticipate? Default to escalate? Default to the nearest configured category?
8. What chat protocol should OWB target for human-agent communication? Slack and Matrix are the leading candidates. Should OWB define a protocol-agnostic message interface that adapters can implement?

### Stage 3

9. How should director agents handle conflicting priorities when two directors need the same specialist simultaneously? Queue-based? Priority-weighted? Escalate to head agent?
10. What is the right granularity for director domains? Too broad (e.g., "engineering") and the director becomes a bottleneck. Too narrow (e.g., "Python backend" vs. "Go backend") and coordination overhead increases.
11. How should OWB handle director agent failure or degradation? Automatic failover to another director? Escalate all tasks to the head agent? Pause and notify the human?

## Links

- [ADR](./adr.md)
- [SDR](./sdr.md)
- [Threat Model](./threat-model.md)
