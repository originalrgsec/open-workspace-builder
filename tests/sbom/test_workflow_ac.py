"""OWB-S107a — Workflow-level acceptance test per integration-verification-policy §1.

This test exercises the full `owb sbom generate` CLI pipeline end-to-end
against a realistic workspace fixture. It is not a unit-level call; it
invokes the Click command as an operator would, reads the resulting file,
and verifies the AC contract that motivates S107a:

1. Generate an SBOM on a known workspace.
2. Every discovered extension appears as a component with a stable bom-ref
   and `sha256-norm1:` content hash.
3. Modify one skill (whitespace + `updated:` field only) and regenerate.
   Hashes must be identical — this is the stability contract.
4. Modify one skill's body and regenerate. Exactly one component hash
   must change.
5. The entire emitted document validates against the official CycloneDX 1.6
   JSON schema.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from open_workspace_builder.cli import owb


def _build_fixture_workspace(root: Path) -> Path:
    """Create a realistic workspace fixture with skills, agents, commands, MCP."""
    ws = root / "fixture-workspace"

    # Skills
    (ws / ".claude" / "skills" / "xlsx").mkdir(parents=True)
    (ws / ".claude" / "skills" / "xlsx" / "SKILL.md").write_text(
        "---\nname: xlsx\nversion: 1.2.0\nupdated: 2026-04-10\n---\n"
        "# XLSX skill\nCreates and reads Excel files.\n",
        encoding="utf-8",
    )
    (ws / ".claude" / "skills" / "pdf").mkdir(parents=True)
    (ws / ".claude" / "skills" / "pdf" / "SKILL.md").write_text(
        "---\nname: pdf\nversion: 0.3.1\n---\n# PDF skill\n",
        encoding="utf-8",
    )

    # Agents
    (ws / ".claude" / "agents").mkdir(parents=True)
    (ws / ".claude" / "agents" / "planner.md").write_text(
        "---\nname: planner\n---\n# Planner\n", encoding="utf-8"
    )
    (ws / ".claude" / "agents" / "reviewer.md").write_text(
        "---\nname: reviewer\n---\n# Reviewer\n", encoding="utf-8"
    )

    # Commands
    (ws / ".claude" / "commands").mkdir(parents=True)
    (ws / ".claude" / "commands" / "commit.md").write_text(
        "---\nname: commit\n---\n# /commit\n", encoding="utf-8"
    )

    # MCP servers
    mcp = {
        "mcpServers": {
            "github": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-github"],
            },
            "filesystem": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-filesystem", "/tmp"],
            },
        }
    }
    (ws / ".mcp.json").write_text(json.dumps(mcp, indent=2), encoding="utf-8")

    return ws


def _run_generate(ws: Path, output: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(owb, ["sbom", "generate", str(ws), "--output", str(output)])
    assert result.exit_code == 0, f"generate failed: {result.output}"


def _component_hashes(sbom_path: Path) -> dict[str, str]:
    """Return a {component-name: sha256-hex} map from an emitted SBOM."""
    data = json.loads(sbom_path.read_text(encoding="utf-8"))
    result: dict[str, str] = {}
    for c in data.get("components", []):
        sha = next(
            (h["content"] for h in c.get("hashes", []) if h["alg"] == "SHA-256"),
            None,
        )
        assert sha is not None, f"component {c['name']} missing SHA-256"
        result[c["name"]] = sha
    return result


class TestWorkflowAC:
    def test_generate_then_modify_updated_field_then_regenerate_hashes_stable(
        self, tmp_path: Path
    ) -> None:
        """The stability contract.

        Generate baseline. Bump `updated:` in the xlsx skill. Regenerate.
        All hashes must be identical — no drift from a cosmetic edit.
        """
        ws = _build_fixture_workspace(tmp_path)
        sbom_before = tmp_path / "before.cdx.json"
        sbom_after = tmp_path / "after.cdx.json"

        _run_generate(ws, sbom_before)
        hashes_before = _component_hashes(sbom_before)

        # Bump `updated:` on xlsx + add trailing whitespace to reviewer.
        xlsx_file = ws / ".claude" / "skills" / "xlsx" / "SKILL.md"
        xlsx_file.write_text(
            "---\nname: xlsx\nversion: 1.2.0\nupdated: 2099-12-31\n---\n"
            "# XLSX skill\nCreates and reads Excel files.\n",
            encoding="utf-8",
        )
        reviewer_file = ws / ".claude" / "agents" / "reviewer.md"
        reviewer_file.write_text("---\nname: reviewer   \n---\n# Reviewer  \n", encoding="utf-8")

        _run_generate(ws, sbom_after)
        hashes_after = _component_hashes(sbom_after)

        assert hashes_before == hashes_after, (
            f"Hashes drifted across cosmetic changes. before={hashes_before} after={hashes_after}"
        )

    def test_modify_skill_body_flips_exactly_one_component_hash(self, tmp_path: Path) -> None:
        """Drift contract: real content changes move exactly their hash."""
        ws = _build_fixture_workspace(tmp_path)
        sbom_before = tmp_path / "before.cdx.json"
        sbom_after = tmp_path / "after.cdx.json"

        _run_generate(ws, sbom_before)
        hashes_before = _component_hashes(sbom_before)

        # Meaningful body change to the pdf skill only.
        pdf_file = ws / ".claude" / "skills" / "pdf" / "SKILL.md"
        pdf_file.write_text(
            "---\nname: pdf\nversion: 0.3.1\n---\n# PDF skill v2\nNew body.\n",
            encoding="utf-8",
        )

        _run_generate(ws, sbom_after)
        hashes_after = _component_hashes(sbom_after)

        changed = {name for name in hashes_before if hashes_before[name] != hashes_after.get(name)}
        assert changed == {"pdf"}, f"expected only pdf to change, got {changed}"

    def test_all_discovered_components_present_in_sbom(self, tmp_path: Path) -> None:
        """Every fixture artifact appears exactly once in the SBOM."""
        ws = _build_fixture_workspace(tmp_path)
        sbom_path = tmp_path / "workspace.cdx.json"
        _run_generate(ws, sbom_path)
        hashes = _component_hashes(sbom_path)
        # 2 skills + 2 agents + 1 command + 2 MCP servers = 7
        assert set(hashes.keys()) == {
            "xlsx",
            "pdf",
            "planner",
            "reviewer",
            "commit",
            "github",
            "filesystem",
        }

    def test_emitted_document_validates_against_cyclonedx_schema(self, tmp_path: Path) -> None:
        """AC 1: valid CycloneDX 1.6 per the official schema validator."""
        from cyclonedx.schema import SchemaVersion
        from cyclonedx.validation.json import JsonStrictValidator

        ws = _build_fixture_workspace(tmp_path)
        sbom_path = tmp_path / "workspace.cdx.json"
        _run_generate(ws, sbom_path)

        json_str = sbom_path.read_text(encoding="utf-8")
        validator = JsonStrictValidator(SchemaVersion.V1_6)
        errors = validator.validate_str(json_str)
        assert errors is None, f"Schema validation failed: {errors}"

    def test_every_component_has_norm1_tag_in_properties(self, tmp_path: Path) -> None:
        """Normalization version is machine-discoverable per component."""
        ws = _build_fixture_workspace(tmp_path)
        sbom_path = tmp_path / "workspace.cdx.json"
        _run_generate(ws, sbom_path)

        data = json.loads(sbom_path.read_text(encoding="utf-8"))
        for c in data["components"]:
            props = {p["name"]: p["value"] for p in c.get("properties", [])}
            assert props.get("owb:normalization") == "norm1", (
                f"component {c['name']} missing norm1 tag"
            )
            assert props["owb:content-hash"].startswith("sha256-norm1:")
