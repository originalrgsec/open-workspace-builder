---
type: policy
created: 2026-03-13
updated: 2026-04-19
tags: [policy, licensing, open-source, compliance]
applies-to: all-projects
---

# Allowed Open Source Licenses

## Purpose

Defines which open source licenses are permitted in the projects built from this workspace. The governing principle is zero IP encumbrance: no license may require disclosure of proprietary source code, restrict commercial use, or create ongoing compliance obligations that are easy to accidentally violate.

This policy applies to all direct dependencies and transitive dependencies in any project or internal tool built from this workspace. The AI agent should reference this document when selecting packages, frameworks, or libraries.

## Allowed (Permissive)

These licenses impose no meaningful restrictions on commercial use or proprietary code. Include the required copyright notices in your distribution and you are compliant.

| License | Notes |
|---------|-------|
| MIT | Most common permissive license. No restrictions beyond copyright notice. |
| Apache 2.0 | Permissive with explicit patent grant and patent retaliation clause. Preferred over MIT when available. |
| BSD 2-Clause | Functionally equivalent to MIT. |
| BSD 3-Clause | Adds a no-endorsement clause. No practical impact on use. |
| ISC | Simplified BSD/MIT equivalent. Common in Node.js ecosystem. |
| CC0 / Public Domain / Unlicense | No restrictions whatsoever. |
| 0BSD | Zero-clause BSD. Even less restrictive than MIT (no notice requirement). |
| PSF-2.0 (Python Software Foundation License) | Permissive license used by core Python ecosystem packages (`typing_extensions`, `pytz`, parts of the standard library). Functionally MIT-equivalent with a grant-back clause that does not affect downstream users. |
| CNRI-Python | Another Python-family permissive license. Appears in compound licenses for core Python tooling (e.g., `regex`). Treated as equivalent to PSF-2.0 / MIT. |
| Zlib | Permissive license from the zlib compression library. Functionally equivalent to MIT/BSD. Appears in compound licenses for scientific-computing packages (notably `numpy`). |

## Allowed with Conditions

These licenses are safe when used as intended but require awareness of specific conditions.

| License | Condition |
|---------|-----------|
| MPL 2.0 (Mozilla Public License) | File-level copyleft. Modifications to MPL-licensed source files must be released. Using the library unmodified as a dependency creates no obligation. Do not fork and modify MPL source files without understanding the disclosure requirement. |
| BSL (Business Source License) | Evaluate per project. Read the "Additional Use Grant" in each BSL project. Typically restricts offering the software as a competing hosted service, which may or may not apply to your use case. Converts to a permissive license after the change date. |
| Artistic License 2.0 | Permissive in practice. Unusual language but low risk. Rarely encountered outside Perl. |

## External CLI Tool Invocations

Copyleft license obligations (GPL, LGPL, AGPL) are triggered by linking — importing a library into your process so that it becomes part of the compiled or interpreted program. Invoking a separately installed CLI binary via subprocess (e.g., `subprocess.run(["semgrep", ...])`) does not constitute linking. The calling program and the CLI tool run in separate processes with no shared address space, so copyleft obligations do not propagate to the caller.

Tools used exclusively through CLI invocation are exempt from the Disallowed table, provided all of the following conditions hold:

| Condition | Rationale |
|-----------|-----------|
| The tool is invoked only via subprocess or shell command, never imported as a library | Importing creates a linking relationship that triggers copyleft. |
| The tool is installed separately (system package, pipx, standalone binary), not bundled into the distribution | Bundling may constitute distribution of the copyleft work alongside proprietary code. |
| No proprietary source code is derived from or patches the tool's source | Modifying copyleft source triggers disclosure requirements on the modifications. |
| The tool's output is not itself copyleft-encumbered (check the tool's license for output clauses) | Some licenses (notably AGPL) have broad output clauses. Verify per tool. |

When relying on this exemption, record the tool, its license, and the invocation method in the project's `decisions/` folder so that future maintainers do not accidentally convert a CLI invocation into a library import.

### Example CLI Tool Exemption

The workspace itself uses this pattern for Semgrep:

| Tool | License | Invocation Method | Rationale |
|------|---------|-------------------|-----------|
| Semgrep | LGPL-2.1 | `subprocess.run()` via `owb security sast` | Invoked as a separate process, never imported as a Python library. No Semgrep source is bundled or modified. |

Document your own CLI tool exemptions in the same format in the project's `decisions/` folder.

## Disallowed (Copyleft / Commercial Restriction)

These licenses create IP encumbrance risk and must not be used as linked dependencies in any project built from this workspace. See "External CLI Tool Invocations" above for the exemption that applies to tools invoked exclusively via subprocess.

| License | Reason |
|---------|--------|
| GPL v2 / GPL v3 | Strong copyleft. Linking GPL code into an application requires the entire application to be distributed under GPL. |
| AGPL v3 | Network copyleft. Triggers GPL obligations when software is accessed over a network (SaaS). Any web service using AGPL code must release its entire source. |
| LGPL v2.1 / LGPL v3 | Weak copyleft. Requires dynamic linking and user ability to relink. Creates ongoing compliance obligations that are easy to violate accidentally. Disallowed as a linked dependency for simplicity. |
| SSPL (Server Side Public License) | Requires open-sourcing the entire service stack (monitoring, backups, orchestration), not just the application. Used by MongoDB. |
| CC BY-NC (Creative Commons NonCommercial) | Explicitly prohibits commercial use. |
| CC BY-SA (Creative Commons ShareAlike) | Copyleft for content. Derivative works must use the same license. |
| Commons Clause | Addendum restricting sale of the software. Ambiguously worded and commercially risky. |
| EUPL (European Union Public License) | Copyleft with broad compatibility claims but complex interaction with other licenses. Avoid. |

## Enforcement

When adding a dependency to a project:

1. Check the package license before adding it (most package managers display this: `npm info <pkg> license`, `pip show <pkg>`, `cargo info <pkg>`).
2. If the license is in the Allowed table, proceed.
3. If the license is in Allowed with Conditions, verify the condition does not apply to your use case.
4. If the license is in Disallowed or not listed here, check whether the tool qualifies for the External CLI Tool Invocation exemption. If it does, record it in the exemptions table and file an ADR. If it does not, find an alternative or escalate for a policy exception.
5. For transitive dependencies, run a license audit periodically (`license-checker` for npm, `pip-licenses` for Python, `cargo-deny` for Rust).

## Audit Tools

| Ecosystem | Tool | Command |
|-----------|------|---------|
| npm / Node.js | license-checker | `npx license-checker --summary` |
| Python / pip | pip-licenses | `pip-licenses --format=table` |
| Rust / Cargo | cargo-deny | `cargo deny check licenses` |
| Go | go-licenses | `go-licenses csv .` |
| Multi-language | FOSSA / Snyk | SaaS license scanning (evaluate if project scale warrants) |

## Exceptions

CLI tool invocation exemptions are tracked in the "External CLI Tool Invocations" section above and do not require a full exception. If a critical dependency has a disallowed license, cannot qualify for the CLI exemption, and no permissively-licensed alternative exists, document the business justification and risk assessment as a decision record in the relevant project's `decisions/` folder.

## Review Schedule

Review this policy annually or when entering a new technology ecosystem.
