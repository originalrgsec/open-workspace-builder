#!/usr/bin/env python3
"""
security-writetime.py — Claude Code PreToolUse hook

Scans file writes (Edit, Write, MultiEdit) for a tailored set of dangerous
patterns relevant to Python, GitHub Actions, and infrastructure code. Warns
via stderr without blocking: exits 0 in all cases. Review-time skills and
agents (code-reviewer, security-reviewer) handle remediation; this hook is
a cheap write-time signal, not a replacement for review.

Rule set is deliberately narrow. Every rule targets a concrete bug class
with a known attack path, not style. False positives are actively pruned:
substring matches are avoided in favor of anchored regex, and any match
on a line ending with ``# noqa: security`` is suppressed.

Install: Add to your Claude Code settings.json under hooks.PreToolUse:

    {
      "hooks": {
        "PreToolUse": [
          {
            "matcher": "Edit|Write|MultiEdit",
            "command": "python3 /path/to/security-writetime.py"
          }
        ]
      }
    }

Exit behavior:
  - Always exits 0 (warn-only). stderr carries the warning; stdout is
    silent.
  - Non-write tool calls, empty content, and unparseable payloads all
    pass through without output.

Rule inventory (current): see ``RULES`` below. Rules are hard-coded as
a ``@dataclass(frozen=True)`` tuple. A follow-up story on the
open-workspace-builder backlog will move these to a declarative
YAML/TOML loader with Pydantic schema validation.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from typing import Callable


SUPPRESS_MARKER = "noqa: security"


@dataclass(frozen=True)
class Rule:
    name: str
    message: str
    path_filter: Callable[[str], bool]
    pattern: re.Pattern[str]


def any_path(_: str) -> bool:
    return True


def is_python(path: str) -> bool:
    return path.endswith(".py")


def is_github_workflow(path: str) -> bool:
    return "/.github/workflows/" in path and (path.endswith(".yml") or path.endswith(".yaml"))


def is_config_file(path: str) -> bool:
    lowered = path.lower()
    return lowered.endswith((".toml", ".yml", ".yaml", ".ini", ".conf", ".cfg", ".env"))


RULES: tuple[Rule, ...] = (
    Rule(
        name="gha-workflow-injection",
        path_filter=is_github_workflow,
        pattern=re.compile(
            r"run:[^\n]*\$\{\{\s*github\.(event|head_ref|pull_request\.head\.ref)",
            re.IGNORECASE,
        ),
        message=(
            "GitHub Actions workflow injection risk.\n"
            "Untrusted inputs (github.event.*, github.head_ref) used directly inside a run: block.\n"
            "Fix: assign to env: first, then reference the env var:\n"
            "  env:\n"
            "    TITLE: ${{ github.event.issue.title }}\n"
            '  run: echo "$TITLE"\n'
            "Background: https://github.blog/security/vulnerability-research/how-to-catch-github-actions-workflow-injections-before-attackers-do/"
        ),
    ),
    Rule(
        name="py-subprocess-shell-true",
        path_filter=is_python,
        pattern=re.compile(
            r"\bsubprocess\.\w+\([^)]*shell\s*=\s*True",
            re.DOTALL,
        ),
        message=(
            "subprocess called with shell=True.\n"
            "This enables shell metacharacter injection if any argument is user-controlled.\n"
            "Fix: pass the command as a list and drop shell=True, or use shlex.quote() if shell is unavoidable."
        ),
    ),
    Rule(
        name="py-yaml-unsafe-load",
        path_filter=is_python,
        pattern=re.compile(
            r"\byaml\.load\((?![^)]*\b(Safe|C?Safe)Loader\b)",
        ),
        message=(
            "yaml.load() without SafeLoader.\n"
            "Default loader constructs arbitrary Python objects, enabling RCE on untrusted YAML.\n"
            "Fix: yaml.safe_load(data) or yaml.load(data, Loader=yaml.SafeLoader)."
        ),
    ),
    Rule(
        name="py-requests-verify-false",
        path_filter=is_python,
        pattern=re.compile(
            r"\b(requests|httpx)\.\w+\([^)]*verify\s*=\s*False",
            re.DOTALL,
        ),
        message=(
            "HTTP client with verify=False.\n"
            "TLS certificate verification disabled. Enables MITM and breaks chain-of-trust.\n"
            "Fix: remove verify=False, or pass verify=<path-to-ca-bundle> for private CAs."
        ),
    ),
    Rule(
        name="py-flask-debug-true",
        path_filter=is_python,
        pattern=re.compile(
            r"(Flask\([^)]*debug\s*=\s*True|\.run\([^)]*debug\s*=\s*True)",
            re.DOTALL,
        ),
        message=(
            "Flask debug=True.\n"
            "Enables the Werkzeug debugger, which exposes an RCE console on any unhandled exception.\n"
            "Fix: drive debug from an env var and never enable in production."
        ),
    ),
    Rule(
        name="py-eval-exec",
        path_filter=is_python,
        pattern=re.compile(r"(?<![\w.])(eval|exec)\s*\("),
        message=(
            "eval() or exec() on dynamic input.\n"
            "Direct code execution primitives. Almost always a design smell outside of REPLs and test harnesses.\n"
            "Fix: use ast.literal_eval() for literal parsing, or a proper parser for structured input."
        ),
    ),
    Rule(
        name="py-pickle-loads",
        path_filter=is_python,
        pattern=re.compile(r"\bpickle\.loads?\("),
        message=(
            "pickle.load/pickle.loads on potentially untrusted data.\n"
            "Pickle deserialization runs arbitrary code. Safe only on data you produced yourself.\n"
            "Fix: use json, msgpack, or a schema-validated format. If pickle is required, document the trust boundary."
        ),
    ),
    Rule(
        name="bind-all-interfaces",
        path_filter=is_config_file,
        pattern=re.compile(r"(?:^|[\s=:\"'])0\.0\.0\.0(?:[\s:\"'/]|$)"),
        message=(
            "Binding to 0.0.0.0 in a config file.\n"
            "Exposes the service on every interface. Intended on containers, risky on hosts.\n"
            "Fix: bind to 127.0.0.1 for local services, or the specific interface for LAN services. Docker Compose can publish with 127.0.0.1:port:port."
        ),
    ),
    Rule(
        name="hardcoded-private-key",
        path_filter=any_path,
        pattern=re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED |)PRIVATE KEY-----"),
        message=(
            "Hardcoded private key material.\n"
            "A private key block was written directly into a file. If this commits, the key is compromised forever.\n"
            "Fix: move to a secrets manager (himitsubako, age-encrypted store, Vault, or equivalent), gitignore the path, rotate the key if it has been staged."
        ),
    ),
)


def extract_content(tool_name: str, tool_input: dict) -> tuple[str, str]:
    """Return (file_path, content) for the write tool being invoked."""
    file_path = tool_input.get("file_path", "") or ""
    if tool_name == "Write":
        return file_path, tool_input.get("content", "") or ""
    if tool_name == "Edit":
        return file_path, tool_input.get("new_string", "") or ""
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits", []) or []
        joined = "\n".join(e.get("new_string", "") or "" for e in edits)
        return file_path, joined
    return file_path, ""


def line_is_suppressed(content: str, match_start: int) -> bool:
    """Check whether the matching line ends with the suppression marker."""
    line_start = content.rfind("\n", 0, match_start) + 1
    line_end = content.find("\n", match_start)
    if line_end == -1:
        line_end = len(content)
    line = content[line_start:line_end]
    return SUPPRESS_MARKER in line


def evaluate(file_path: str, content: str) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    if not content:
        return findings
    for rule in RULES:
        if not rule.path_filter(file_path):
            continue
        for match in rule.pattern.finditer(content):
            if line_is_suppressed(content, match.start()):
                continue
            findings.append((rule.name, rule.message))
            break
    return findings


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "Write", "MultiEdit"):
        return 0

    tool_input = payload.get("tool_input", {}) or {}
    file_path, content = extract_content(tool_name, tool_input)
    if not file_path or not content:
        return 0

    findings = evaluate(file_path, content)
    if not findings:
        return 0

    lines = [
        f"security-writetime: {len(findings)} warning(s) on {file_path}",
    ]
    for name, message in findings:
        lines.append(f"\n[{name}]")
        lines.append(message)
    lines.append(
        f"\nAppend `# {SUPPRESS_MARKER}` to the offending line to silence an accepted-risk finding."
    )
    print("\n".join(lines), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
