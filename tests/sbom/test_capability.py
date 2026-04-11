"""OWB-S107b — Tests for SBOM capability extraction.

Capabilities are *declared* attributes of a skill, agent, command, or MCP
server: the tools they may invoke, the MCP servers they reference, and any
network or environment access they declare. The SBOM records what was
declared, not what gets enforced at runtime.

Critical safety property: env values from .mcp.json must NEVER appear in
extracted output. Only env *keys* are recorded.
"""

from __future__ import annotations

import json


from open_workspace_builder.sbom.capability import (
    CapabilityKind,
    extract_mcp_server_capabilities,
    extract_skill_capabilities,
    parse_allowed_tools,
)


# ---------------------------------------------------------------------------
# parse_allowed_tools — flexible frontmatter shape
# ---------------------------------------------------------------------------


class TestParseAllowedTools:
    def test_yaml_list_form(self) -> None:
        # `allowed-tools: [Read, Write, Bash]`
        assert parse_allowed_tools("[Read, Write, Bash]") == ("Read", "Write", "Bash")

    def test_comma_separated_scalar(self) -> None:
        assert parse_allowed_tools("Read, Write, Bash") == ("Read", "Write", "Bash")

    def test_single_tool(self) -> None:
        assert parse_allowed_tools("Read") == ("Read",)

    def test_wildcard(self) -> None:
        assert parse_allowed_tools("*") == ("*",)

    def test_empty_string(self) -> None:
        assert parse_allowed_tools("") == ()

    def test_none(self) -> None:
        assert parse_allowed_tools(None) == ()

    def test_strips_whitespace(self) -> None:
        assert parse_allowed_tools("  Read ,   Write  ") == ("Read", "Write")

    def test_strips_brackets_and_quotes(self) -> None:
        assert parse_allowed_tools('["Read", "Write"]') == ("Read", "Write")


# ---------------------------------------------------------------------------
# Skill / agent / command capability extraction
# ---------------------------------------------------------------------------


class TestExtractSkillCapabilities:
    def test_allowed_tools_per_tool_property(self) -> None:
        caps = extract_skill_capabilities({"allowed-tools": "Read, Write, Bash"})
        tool_caps = [c for c in caps if c.kind == CapabilityKind.TOOL]
        assert sorted(c.value for c in tool_caps) == ["Bash", "Read", "Write"]

    def test_wildcard_recorded_with_warning_flag(self) -> None:
        caps = extract_skill_capabilities({"allowed-tools": "*"})
        wildcards = [c for c in caps if c.kind == CapabilityKind.TOOL and c.value == "*"]
        assert len(wildcards) == 1
        assert wildcards[0].warning is True

    def test_mcp_connections(self) -> None:
        caps = extract_skill_capabilities({"mcp": "github, slack"})
        mcp_caps = [c for c in caps if c.kind == CapabilityKind.MCP]
        assert sorted(c.value for c in mcp_caps) == ["github", "slack"]

    def test_explicit_network_declaration(self) -> None:
        caps = extract_skill_capabilities({"network": "true"})
        net_caps = [c for c in caps if c.kind == CapabilityKind.NETWORK]
        assert len(net_caps) == 1
        assert net_caps[0].value == "declared"

    def test_no_network_field_emits_no_property(self) -> None:
        # Absence of `network` field is not False — the SBOM only records
        # what was declared, never inferred absences.
        caps = extract_skill_capabilities({"name": "demo"})
        net_caps = [c for c in caps if c.kind == CapabilityKind.NETWORK]
        assert net_caps == []

    def test_network_false_explicit_emits_property(self) -> None:
        caps = extract_skill_capabilities({"network": "false"})
        net_caps = [c for c in caps if c.kind == CapabilityKind.NETWORK]
        assert len(net_caps) == 1
        assert net_caps[0].value == "declared-false"

    def test_empty_frontmatter(self) -> None:
        assert extract_skill_capabilities({}) == ()

    def test_combined(self) -> None:
        caps = extract_skill_capabilities(
            {
                "allowed-tools": "Read, Write",
                "mcp": "github",
                "network": "true",
            }
        )
        kinds = sorted({c.kind.value for c in caps})
        assert kinds == ["mcp", "network", "tool"]


# ---------------------------------------------------------------------------
# MCP server capability extraction — env key safety is critical
# ---------------------------------------------------------------------------


class TestExtractMcpServerCapabilities:
    def test_stdio_transport(self) -> None:
        config = {"command": "node", "args": ["server.js"]}
        caps = extract_mcp_server_capabilities("demo", config)
        transport_caps = [c for c in caps if c.kind == CapabilityKind.TRANSPORT]
        assert len(transport_caps) == 1
        assert transport_caps[0].value == "stdio"

    def test_sse_transport(self) -> None:
        config = {"transport": "sse", "url": "https://example.com"}
        caps = extract_mcp_server_capabilities("demo", config)
        transport_caps = [c for c in caps if c.kind == CapabilityKind.TRANSPORT]
        assert transport_caps[0].value == "sse"

    def test_http_transport(self) -> None:
        config = {"transport": "http", "url": "https://example.com"}
        caps = extract_mcp_server_capabilities("demo", config)
        transport_caps = [c for c in caps if c.kind == CapabilityKind.TRANSPORT]
        assert transport_caps[0].value == "http"

    def test_exec_capability_for_command(self) -> None:
        config = {"command": "node", "args": ["server.js", "--port", "1234"]}
        caps = extract_mcp_server_capabilities("demo", config)
        exec_caps = [c for c in caps if c.kind == CapabilityKind.EXEC]
        assert len(exec_caps) == 1
        # Records the command name only; never the full args (could leak paths
        # or secrets in some configurations).
        assert exec_caps[0].value == "node"

    def test_env_keys_recorded(self) -> None:
        config = {
            "command": "node",
            "args": ["server.js"],
            "env": {
                "GITHUB_TOKEN": "ghp_supersecret",
                "API_URL": "https://api.example.com",
            },
        }
        caps = extract_mcp_server_capabilities("demo", config)
        env_caps = [c for c in caps if c.kind == CapabilityKind.ENV]
        env_keys = sorted(c.value for c in env_caps)
        assert env_keys == ["API_URL", "GITHUB_TOKEN"]

    def test_env_values_never_leak(self) -> None:
        # CRITICAL SAFETY TEST: env values must NEVER appear in any
        # capability output, ever. A leak here means secrets in SBOMs.
        config = {
            "command": "node",
            "env": {
                "SECRET_TOKEN": "this-is-a-secret-value",
                "ANOTHER_SECRET": "another-secret-value",
            },
        }
        caps = extract_mcp_server_capabilities("demo", config)
        # Serialize every capability and assert no secret values appear.
        all_text = json.dumps([{"k": c.kind.value, "v": c.value, "n": c.name} for c in caps])
        assert "this-is-a-secret-value" not in all_text
        assert "another-secret-value" not in all_text

    def test_no_env_section(self) -> None:
        config = {"command": "node"}
        caps = extract_mcp_server_capabilities("demo", config)
        env_caps = [c for c in caps if c.kind == CapabilityKind.ENV]
        assert env_caps == []

    def test_empty_config(self) -> None:
        # Defensive: empty or malformed config shouldn't crash, just return
        # an empty tuple.
        assert extract_mcp_server_capabilities("demo", {}) == ()

    def test_default_transport_is_stdio_when_command_present(self) -> None:
        # MCP convention: a command-based server is stdio unless specified.
        config = {"command": "python", "args": ["-m", "myserver"]}
        caps = extract_mcp_server_capabilities("demo", config)
        transport = [c for c in caps if c.kind == CapabilityKind.TRANSPORT]
        assert transport[0].value == "stdio"
