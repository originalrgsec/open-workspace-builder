---
type: policy
created: 2026-03-13
updated: 2026-03-25
tags: [policy, licensing, open-source, compliance]
applies-to: all-projects
---

# Allowed Open Source Licenses

## Purpose

Defines which open source licenses are permitted in your technology stack. The governing principle is zero IP encumbrance: no license may require disclosure of proprietary source code, restrict commercial use, or create ongoing compliance obligations that are easy to accidentally violate.

This policy applies to all direct dependencies and transitive dependencies in any product or internal tool. Reference this document when selecting packages, frameworks, or libraries.

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

## Allowed with Conditions

These licenses are safe when used as intended but require awareness of specific conditions.

| License | Condition |
|---------|-----------|
| MPL 2.0 (Mozilla Public License) | File-level copyleft. Modifications to MPL-licensed source files must be released. Using the library unmodified as a dependency creates no obligation. Do not fork and modify MPL source files without understanding the disclosure requirement. |
| BSL (Business Source License) | Evaluate per project. Read the "Additional Use Grant" in each BSL project. Typically restricts offering the software as a competing hosted service, which does not apply to most infrastructure use. Converts to a permissive license after the change date. |
| Artistic License 2.0 | Permissive in practice. Unusual language but low risk. Rarely encountered outside Perl. |

## Disallowed (Copyleft / Commercial Restriction)

These licenses create IP encumbrance risk and must not be used in any project without a documented exception.

| License | Reason |
|---------|--------|
| GPL v2 / GPL v3 | Strong copyleft. Linking GPL code into an application requires the entire application to be distributed under GPL. |
| AGPL v3 | Network copyleft. Triggers GPL obligations when software is accessed over a network (SaaS). Any web service using AGPL code must release its entire source. |
| LGPL v2.1 / LGPL v3 | Weak copyleft. Requires dynamic linking and user ability to relink. Creates ongoing compliance obligations that are easy to violate accidentally. Disallowed for simplicity. |
| SSPL (Server Side Public License) | Requires open-sourcing the entire service stack (monitoring, backups, orchestration), not just the application. Used by MongoDB. |
| CC BY-NC (Creative Commons NonCommercial) | Explicitly prohibits commercial use. |
| CC BY-SA (Creative Commons ShareAlike) | Copyleft for content. Derivative works must use the same license. |
| Commons Clause | Addendum restricting sale of the software. Ambiguously worded and commercially risky. |
| EUPL (European Union Public License) | Copyleft with broad compatibility claims but complex interaction with other licenses. Avoid. |

## Enforcement

When adding a dependency to any project:

1. Check the package license before adding it (most package managers display this: `npm info <pkg> license`, `pip show <pkg>`, `cargo info <pkg>`)
2. If the license is in the Allowed table, proceed
3. If the license is in Allowed with Conditions, verify the condition does not apply to your use case
4. If the license is in Disallowed or not listed here, do not add the dependency — find an alternative or escalate for a policy exception
5. For transitive dependencies, run a license audit periodically (`license-checker` for npm, `pip-licenses` for Python, `cargo-deny` for Rust)

## Audit Tools

| Ecosystem | Tool | Command |
|-----------|------|---------|
| npm / Node.js | license-checker | `npx license-checker --summary` |
| Python / pip | pip-licenses | `pip-licenses --format=table` |
| Rust / Cargo | cargo-deny | `cargo deny check licenses` |
| Go | go-licenses | `go-licenses csv .` |
| Multi-language | FOSSA / Snyk | SaaS license scanning (evaluate if project scale warrants) |

## Exceptions

If a critical dependency has a disallowed license and no permissively-licensed alternative exists, document the business justification and risk assessment as a decision record in the relevant project's `decisions/` folder.

## Review Schedule

Review this policy annually or when entering a new technology ecosystem.
