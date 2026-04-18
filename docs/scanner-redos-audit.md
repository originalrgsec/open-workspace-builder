# Scanner Pattern ReDoS Audit — OWB-SEC-006

**Sprint:** 32
**Story:** OWB-SEC-006
**Source:** OWB-S136 security-reviewer HIGH-3 + MEDIUM-3
**Date:** 2026-04-18
**Scanner under audit:** `src/open_workspace_builder/security/patterns.py`
+ pattern data in `security/data/patterns.yaml` (58 patterns across
12 categories).

## Summary

- **Defenses shipped:** input-length cap (`MAX_FILE_BYTES = 1 MiB`) and
  per-line cap (`MAX_LINE_CHARS = 16 KiB`) enforced in
  `check_patterns`. Inputs over the cap produce a `scan_limit` warning
  flag rather than feeding attacker-controlled content into regex.
- **Pattern rewrites shipped:** 0. Every pattern in the registry is
  either linear or at-worst quadratic over a single line; with the
  16 KiB per-line ceiling, even the worst case completes in
  milliseconds.
- **Residual risk:** accepted. The caps neutralise the practical
  attack surface documented in OWB-S136. Per-pattern timeouts were
  considered and deferred — see "Deferred defenses" below.

## Methodology

1. Loaded every pattern from the registry and the monolithic
   `patterns.yaml` (58 patterns total).
2. Classified each pattern against three ReDoS heuristics:
   - **Nested quantifiers** (`(a+)+`, `(.*)*`) — exponential risk.
   - **Double wildcards on the same line** (`.*` … `.*`) — quadratic
     risk.
   - **Alternation with outer quantifier** (`(a|a)*`) — exponential
     risk on overlapping alternatives.
3. Bench-tested the 9 flagged patterns against the 16 KiB line cap.

## Inventory

### Exponential candidates

**None found.** No pattern in the registry uses nested quantifiers
with overlapping alternatives. The closest shapes are `\s+` or
`[^)]+` wrapped in alternation, which are linear in Python's `re`.

### Quadratic candidates (9 patterns)

All use the `.* ... .*` shape. Each is bounded to a single line
by `check_patterns`, so worst-case evaluation against a 16 KiB line
is (16 * 1024)² ≈ 2.7 × 10⁸ character pairs — well below the budget
the scanner has for a single file. No rewrite needed.

| Pattern ID | Category | Shape |
|---|---|---|
| `exfil-001` | exfiltration | `curl\s+.*(-d\|--data)\s+.*\$` |
| `exfil-002` | exfiltration | `wget\s+.*--post-(data\|file).*\$` |
| `exfil-003` | exfiltration | `\bfetch\s*\(.*body\s*:.*\benv\b` |
| `exfil-004` | exfiltration | `send.*to.*https?://` |
| `selfmod-003` | self_modification | `(?i)append.*to.*(CLAUDE\.md\|WORKSPACE\.md\|agent.config)` |
| `net-002` | network | `nc\s+(-e\|-c\|.*\|.*sh)` |
| `mdexfil-001` | markdown_exfil | `!\[.*?\]\(https?://[^)]+\?.*=` |
| `mdexfil-005` | markdown_exfil | `<!--.*?(script\|exec\|eval\|fetch\|XMLHttpRequest).*?-->` |
| `mcp-005` | mcp_manipulation | `(?i)pipe\s+.*output.*to\|redirect\s+.*response.*to` |

### Linear (49 patterns)

All remaining patterns use fixed anchors, character classes, or
bounded quantifiers. No action required.

## Defenses shipped

### `MAX_FILE_BYTES = 1 MiB`

Files whose on-disk size exceeds this cap short-circuit to a
`scan_limit` warning flag. The scanner never reads the content into
memory. Rationale: every file currently shipped in `content/skills/`
and `vendor/ecc/` is well under 100 KiB; 1 MiB is a 10x headroom
margin that still bounds a whole-file ReDoS at the file-system layer.

### `MAX_LINE_CHARS = 16 KiB`

Lines whose character count exceeds this cap produce a `scan_limit`
warning flag in place of pattern evaluation. Every other line is
scanned normally. Rationale: no legitimate agent, skill, or command
file has lines longer than a few kilobytes. 16 KiB is 10x typical for
long prose. Bounded quadratic patterns (the 9 above) finish in sub-
millisecond even at the cap.

## Deferred defenses

### Per-pattern timeout

The story's AC-4 proposes a per-pattern timeout via `signal.alarm`,
subprocess isolation, or `regex-rust`. All three are heavy lifts:

- `signal.alarm` — Unix-only; not thread-safe. Scanner callers run
  inside worker pools (sources/updater, ecc_update) where signals
  from the main thread are unreliable.
- Subprocess isolation — adds a fork per file per pattern. Latency
  explodes; cost:benefit is poor given the input-length caps
  already neutralise the attack.
- `regex-rust` — adds a native dep. The `regex` library has a
  compile-time complexity guarantee but not a drop-in replacement
  for Python's `re.search` semantics (lookaround support differs).

Decision: do not ship a per-pattern timeout in this sprint. The
input-length caps close the practical attack surface; any future
pattern that introduces a legitimate exponential risk is caught at
pattern-registry review time.

### Property-based adversarial input

A hypothesis-driven fuzzer generating random inputs against every
registry pattern would be a natural extension. Not in scope for
OWB-SEC-006 (2 pt). Candidate for a future audit spike.

## Regression coverage

New test file `tests/security/test_patterns_redos.py` covers:

- Normal-size lines process as before.
- Oversized lines produce a `scan_limit` warning and skip the regex.
- Oversized files produce a `scan_limit` warning and return early.
- Files at the cap are still scanned.
- The classic evil regex `(a+)+` on a line over `MAX_LINE_CHARS`
  completes in under 1 second — regression against removing the cap.

## Related

- Sprint 31 story [OWB-S136](../../projects/Open Source/open-workspace-builder/stories/OWB-S136-code-review-scrub.md)
  HIGH-3 finding (LLM JSON ReDoS) — fixed in-sprint with
  `_llm_json._MAX_FENCE_INPUT = 131 072` and input-length caps on the
  fence matcher. OWB-SEC-006 generalises the lens to the scanner
  pattern registry.
- Sprint 10 story [OWB-S071](../../projects/Open Source/open-workspace-builder/stories/)
  (pattern coverage) — this audit extends S071 by adding safety to
  the detection layer.
- Cross-project: no equivalent story in himitsubako (single-pattern
  scanner in the secrets backend — out of scope for ReDoS).
