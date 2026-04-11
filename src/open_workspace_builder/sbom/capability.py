"""OWB-S107b — SBOM capability extraction.

Each skill, agent, command, and MCP server in a workspace declares some set
of capabilities — tools it may invoke, MCP servers it references, network
access, env keys it consumes. This module parses those declarations and
records them as :class:`Capability` records that the SBOM builder turns into
CycloneDX ``properties`` under the ``owb:capability:*`` namespace.

**Critical safety property:** when extracting from ``.mcp.json`` configs,
env *keys* are recorded but env *values* are NEVER recorded. Values may
contain API tokens, OAuth secrets, or other credentials, and a leaked value
in an SBOM could be more damaging than a leaked secret in a log file because
SBOMs are designed to be shared with external SSCA pipelines.

The output is *declared* capabilities, not *enforced* capabilities. A skill
that lists ``Read`` in ``allowed-tools`` is declaring an intent; whether the
runtime actually restricts the skill to ``Read`` is a separate concern.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class CapabilityKind(str, Enum):
    """Categories of capability surfaced in the SBOM."""

    TOOL = "tool"
    MCP = "mcp"
    NETWORK = "network"
    EXEC = "exec"
    ENV = "env"
    TRANSPORT = "transport"


@dataclass(frozen=True)
class Capability:
    """A single declared capability for one component.

    Attributes:
        kind: Category of capability (tool, mcp, network, exec, env, transport).
        value: The capability identifier (tool name, mcp server name, etc.).
        name: Optional descriptive name; mostly unused, reserved for richer
            reporting in S107c.
        warning: True if the capability raises an SBOM warning (e.g. tool
            wildcards). Renders as a separate property in the builder.
    """

    kind: CapabilityKind
    value: str
    name: str | None = None
    warning: bool = False


# ---------------------------------------------------------------------------
# Frontmatter parsing helpers
# ---------------------------------------------------------------------------


def parse_allowed_tools(value: str | None) -> tuple[str, ...]:
    """Parse a frontmatter ``allowed-tools`` value into a tuple of tool names.

    Accepts the YAML list form (``[Read, Write]``), comma-separated scalar
    (``Read, Write``), single scalar (``Read``), and the wildcard (``*``).
    Strips whitespace, brackets, and surrounding quotes from each entry.
    Returns an empty tuple for ``None``, empty string, or unparseable input.
    """
    if value is None:
        return ()
    text = value.strip()
    if not text:
        return ()

    # Strip leading/trailing brackets if present (the minimal frontmatter
    # parser delivers them as part of the scalar value).
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]

    parts = [p.strip() for p in text.split(",")]
    cleaned: list[str] = []
    for p in parts:
        if not p:
            continue
        # Strip surrounding quotes
        if len(p) >= 2 and p[0] == p[-1] and p[0] in ('"', "'"):
            p = p[1:-1]
        cleaned.append(p)
    return tuple(cleaned)


# ---------------------------------------------------------------------------
# Skill / agent / command extraction
# ---------------------------------------------------------------------------


def extract_skill_capabilities(frontmatter: Mapping[str, str]) -> tuple[Capability, ...]:
    """Extract declared capabilities from a skill/agent/command frontmatter.

    Args:
        frontmatter: Flat string→string map as produced by the discover
            module's frontmatter parser.

    Returns:
        Deterministically-ordered tuple of :class:`Capability` records.
    """
    if not frontmatter:
        return ()

    out: list[Capability] = []

    # Tools
    for tool in parse_allowed_tools(frontmatter.get("allowed-tools")):
        out.append(
            Capability(
                kind=CapabilityKind.TOOL,
                value=tool,
                warning=(tool == "*"),
            )
        )

    # MCP connections
    for mcp_name in parse_allowed_tools(frontmatter.get("mcp")):
        out.append(Capability(kind=CapabilityKind.MCP, value=mcp_name))

    # Network — only emit if explicitly declared
    network_value = frontmatter.get("network")
    if network_value is not None:
        normalized = network_value.strip().lower()
        if normalized in ("true", "yes", "1"):
            out.append(Capability(kind=CapabilityKind.NETWORK, value="declared"))
        elif normalized in ("false", "no", "0"):
            out.append(Capability(kind=CapabilityKind.NETWORK, value="declared-false"))

    return tuple(_sorted_caps(out))


# ---------------------------------------------------------------------------
# MCP server extraction
# ---------------------------------------------------------------------------


def extract_mcp_server_capabilities(
    server_name: str,
    config: Mapping[str, Any],
) -> tuple[Capability, ...]:
    """Extract declared capabilities for one MCP server config block.

    Args:
        server_name: Name of the server as listed in ``mcpServers``.
        config: The per-server config dict from ``.mcp.json``.

    Returns:
        Deterministically-ordered tuple of :class:`Capability` records.
        Critically, env *values* are NEVER included in any output.
    """
    if not isinstance(config, Mapping) or not config:
        return ()

    out: list[Capability] = []

    # Transport: explicit field wins, default stdio when a command is present
    transport = config.get("transport")
    if not transport:
        if config.get("command"):
            transport = "stdio"
        elif config.get("url"):
            transport = "http"
    if transport:
        out.append(Capability(kind=CapabilityKind.TRANSPORT, value=str(transport)))

    # Exec: command name only, never the full args
    command = config.get("command")
    if command:
        out.append(Capability(kind=CapabilityKind.EXEC, value=str(command)))

    # Env: KEYS ONLY. Never values. This is a hard safety boundary.
    env = config.get("env")
    if isinstance(env, Mapping):
        for env_key in env.keys():
            out.append(Capability(kind=CapabilityKind.ENV, value=str(env_key)))

    return tuple(_sorted_caps(out))


def _sorted_caps(caps: list[Capability]) -> list[Capability]:
    """Sort capabilities deterministically by (kind, value)."""
    return sorted(caps, key=lambda c: (c.kind.value, c.value))
