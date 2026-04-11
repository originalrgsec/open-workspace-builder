"""OWB-S107a / S107b — Component discovery for the SBOM builder.

Walks a workspace and emits one :class:`Component` per skill, agent,
command, or MCP server declaration. Discovery is additive: it reads files
but does not modify the scanner walk.

S107b extends each :class:`Component` with provenance, capabilities, and
license enrichment. The new fields default to empty so S107a callers (and
the persisted CycloneDX output for unmodified components) remain unchanged.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from open_workspace_builder.sbom.capability import (
    Capability,
    extract_mcp_server_capabilities,
    extract_skill_capabilities,
)
from open_workspace_builder.sbom.license import (
    AllowedLicensePolicy,
    LicenseEntry,
    detect_license,
    load_allowed_licenses,
)
from open_workspace_builder.sbom.normalize import compute_hash
from open_workspace_builder.sbom.provenance import (
    Provenance,
    detect_provenance,
)

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$")


class ComponentKind(str, Enum):
    """What kind of AI workspace extension a component represents."""

    SKILL = "skill"
    AGENT = "agent"
    COMMAND = "command"
    MCP_SERVER = "mcp-server"


@dataclass(frozen=True)
class Component:
    """A single SBOM component representing one AI workspace extension.

    The first seven fields are the S107a substrate and must remain stable —
    they participate in `bom-ref` and content-hash identity. S107b enrichment
    fields (provenance, capabilities, license) default to empty so adding
    them does not perturb existing hashes for unmodified components.
    """

    kind: ComponentKind
    name: str
    version: str
    bom_ref: str
    content_hash: str
    evidence_path: str
    source: str
    # S107b enrichment — defaults preserve S107a behavior.
    provenance: Provenance | None = None
    capabilities: tuple[Capability, ...] = ()
    license: LicenseEntry | None = None


def discover_components(workspace: Path) -> tuple[Component, ...]:
    """Discover every skill, agent, command, and MCP server in a workspace.

    Args:
        workspace: The workspace root to walk.

    Returns:
        A deterministically sorted tuple of :class:`Component` instances.
        Returns an empty tuple for a missing or empty workspace.
    """
    if not workspace.is_dir():
        return ()

    # Load the allowed-license policy once per discover() call so the
    # per-component license cross-reference doesn't re-parse the toml on
    # every file.
    policy = load_allowed_licenses()

    components: list[Component] = []
    components.extend(_discover_skills(workspace, policy))
    components.extend(_discover_agents(workspace, policy))
    components.extend(_discover_commands(workspace, policy))
    components.extend(_discover_mcp_servers(workspace, policy))

    return tuple(sorted(components, key=lambda c: (c.kind.value, c.name, c.bom_ref)))


# ---------------------------------------------------------------------------
# Discovery per kind
# ---------------------------------------------------------------------------


def _discover_skills(workspace: Path, policy: AllowedLicensePolicy) -> list[Component]:
    """Find every .claude/skills/**/SKILL.md file."""
    skills_dir = workspace / ".claude" / "skills"
    if not skills_dir.is_dir():
        return []

    found: list[Component] = []
    for skill_file in sorted(skills_dir.rglob("SKILL.md")):
        if not skill_file.is_file():
            continue
        found.append(
            _component_from_markdown_file(
                kind=ComponentKind.SKILL,
                path=skill_file,
                workspace=workspace,
                name_default=skill_file.parent.name,
                policy=policy,
            )
        )
    return found


def _discover_agents(workspace: Path, policy: AllowedLicensePolicy) -> list[Component]:
    """Find every .claude/agents/**/*.md file."""
    agents_dir = workspace / ".claude" / "agents"
    if not agents_dir.is_dir():
        return []

    found: list[Component] = []
    for agent_file in sorted(agents_dir.rglob("*.md")):
        if not agent_file.is_file():
            continue
        found.append(
            _component_from_markdown_file(
                kind=ComponentKind.AGENT,
                path=agent_file,
                workspace=workspace,
                name_default=agent_file.stem,
                policy=policy,
            )
        )
    return found


def _discover_commands(workspace: Path, policy: AllowedLicensePolicy) -> list[Component]:
    """Find every .claude/commands/**/*.md file."""
    commands_dir = workspace / ".claude" / "commands"
    if not commands_dir.is_dir():
        return []

    found: list[Component] = []
    for cmd_file in sorted(commands_dir.rglob("*.md")):
        if not cmd_file.is_file():
            continue
        found.append(
            _component_from_markdown_file(
                kind=ComponentKind.COMMAND,
                path=cmd_file,
                workspace=workspace,
                name_default=cmd_file.stem,
                policy=policy,
            )
        )
    return found


def _discover_mcp_servers(workspace: Path, policy: AllowedLicensePolicy) -> list[Component]:
    """Parse .mcp.json and emit one component per declared server."""
    mcp_file = workspace / ".mcp.json"
    if not mcp_file.is_file():
        return []

    try:
        raw = mcp_file.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return []

    servers = data.get("mcpServers", {}) if isinstance(data, dict) else {}
    if not isinstance(servers, dict):
        return []

    found: list[Component] = []
    for server_name, server_config in sorted(servers.items()):
        # Hash the per-server declaration so that changing a server's command
        # or args shows up as drift, without dragging in unrelated servers.
        declaration = json.dumps(
            {server_name: server_config},
            sort_keys=True,
            separators=(",", ":"),
        )
        content_hash = compute_hash(declaration)
        version = content_hash.rsplit(":", 1)[1][:12]

        rel_path = str(mcp_file.relative_to(workspace))
        bom_ref = f"owb:mcp-server/{server_name}@{version}"

        # S107b enrichment for MCP servers: capabilities from the per-server
        # config (transport, exec, env keys), license from the workspace
        # (the .mcp.json file itself rarely has its own LICENSE), provenance
        # from .mcp.json's git history.
        capabilities = (
            extract_mcp_server_capabilities(server_name, server_config)
            if isinstance(server_config, dict)
            else ()
        )
        license_entry = detect_license(
            component_path=mcp_file,
            workspace=workspace,
            frontmatter={},
            policy=policy,
        )
        provenance = detect_provenance(
            component_path=mcp_file,
            workspace=workspace,
            frontmatter={},
        )

        found.append(
            Component(
                kind=ComponentKind.MCP_SERVER,
                name=server_name,
                version=version,
                bom_ref=bom_ref,
                content_hash=content_hash,
                evidence_path=rel_path,
                source="local",
                provenance=provenance,
                capabilities=capabilities,
                license=license_entry,
            )
        )
    return found


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _component_from_markdown_file(
    *,
    kind: ComponentKind,
    path: Path,
    workspace: Path,
    name_default: str,
    policy: AllowedLicensePolicy,
) -> Component:
    """Build a Component from a markdown file with optional YAML frontmatter."""
    content = path.read_text(encoding="utf-8", errors="replace")
    frontmatter = _parse_frontmatter(content)

    name = frontmatter.get("name", name_default)
    source = frontmatter.get("source", "local")
    content_hash = compute_hash(content)

    version = frontmatter.get("version")
    if version is None:
        # Fallback: first 12 chars of the normalized hash hex.
        version = content_hash.rsplit(":", 1)[1][:12]

    bom_ref = f"owb:{kind.value}/{name}@{version}"
    rel_path = str(path.relative_to(workspace))

    # S107b enrichment
    capabilities = extract_skill_capabilities(frontmatter)
    license_entry = detect_license(
        component_path=path,
        workspace=workspace,
        frontmatter=frontmatter,
        policy=policy,
    )
    provenance = detect_provenance(
        component_path=path,
        workspace=workspace,
        frontmatter=frontmatter,
    )

    return Component(
        kind=kind,
        name=name,
        version=version,
        bom_ref=bom_ref,
        content_hash=content_hash,
        evidence_path=rel_path,
        source=source,
        provenance=provenance,
        capabilities=capabilities,
        license=license_entry,
    )


def _parse_frontmatter(content: str) -> dict[str, str]:
    """Extract a flat string→string map from YAML frontmatter.

    This is a deliberately minimal parser — we only read top-level scalar
    keys like ``name``, ``version``, and ``source``. Nested structures and
    lists are ignored because S107a doesn't need them; S107b can expand.
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}

    body = match.group(1)
    result: dict[str, str] = {}
    for line in body.split("\n"):
        key_match = _FRONTMATTER_KEY_RE.match(line)
        if key_match:
            key, value = key_match.group(1), key_match.group(2).strip()
            # Strip simple matching quotes.
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            result[key] = value
    return result
