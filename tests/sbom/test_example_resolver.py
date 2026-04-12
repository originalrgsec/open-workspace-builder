"""OWB-S120 — Verify SBOM example path resolution in both source-tree
and installed-wheel layouts.

The module-level constants ``FIXTURE_WORKSPACE`` and ``EXAMPLE_SBOM_PATH``
must resolve to real filesystem paths containing the expected content,
regardless of whether OWB is imported from the source tree or from a
pip-installed wheel.
"""

from __future__ import annotations

from pathlib import Path


class TestExamplePathResolution:
    def test_fixture_workspace_is_directory(self) -> None:
        from open_workspace_builder.sbom._example import FIXTURE_WORKSPACE

        assert isinstance(FIXTURE_WORKSPACE, Path)
        assert FIXTURE_WORKSPACE.is_dir(), (
            f"FIXTURE_WORKSPACE does not exist as a directory: {FIXTURE_WORKSPACE}"
        )

    def test_fixture_workspace_contains_expected_files(self) -> None:
        from open_workspace_builder.sbom._example import FIXTURE_WORKSPACE

        expected = [
            FIXTURE_WORKSPACE / ".mcp.json",
            FIXTURE_WORKSPACE / ".claude" / "agents" / "example-agent.md",
            FIXTURE_WORKSPACE / ".claude" / "skills" / "hello" / "SKILL.md",
        ]
        for path in expected:
            assert path.is_file(), f"Missing expected fixture file: {path}"

    def test_example_sbom_path_is_file(self) -> None:
        from open_workspace_builder.sbom._example import EXAMPLE_SBOM_PATH

        assert isinstance(EXAMPLE_SBOM_PATH, Path)
        assert EXAMPLE_SBOM_PATH.is_file(), f"EXAMPLE_SBOM_PATH does not exist: {EXAMPLE_SBOM_PATH}"

    def test_example_sbom_is_valid_json(self) -> None:
        import json

        from open_workspace_builder.sbom._example import EXAMPLE_SBOM_PATH

        content = EXAMPLE_SBOM_PATH.read_text(encoding="utf-8")
        data = json.loads(content)
        assert data.get("bomFormat") == "CycloneDX"

    def test_paths_use_importlib_resources(self) -> None:
        """Verify paths are derived from importlib.resources, not hardcoded parents[N]."""
        import open_workspace_builder.sbom._example as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "parents[" not in source, (
            "_example.py still uses Path.parents[] for path resolution — "
            "should use importlib.resources.files() per OWB-S120"
        )

    def test_discover_components_works_on_fixture(self) -> None:
        from open_workspace_builder.sbom._example import FIXTURE_WORKSPACE
        from open_workspace_builder.sbom.discover import discover_components

        components = discover_components(FIXTURE_WORKSPACE)
        assert len(components) > 0, "discover_components found no components in fixture workspace"

    def test_regenerate_from_package_data(self) -> None:
        """Regeneration must work when FIXTURE_WORKSPACE comes from package data."""
        from open_workspace_builder.sbom._example import regenerate_example_sbom

        result = regenerate_example_sbom()
        assert len(result) > 100
        assert '"bomFormat"' in result
