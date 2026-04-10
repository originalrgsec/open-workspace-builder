"""Tests for owb stage CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from open_workspace_builder.cli import owb


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def vault_with_meta(tmp_path: Path) -> Path:
    """Create a vault directory with vault-meta.json."""
    vault = tmp_path / "Obsidian"
    vault.mkdir()
    meta = {"version": "0.8.2", "stage": 0}
    (vault / "vault-meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return vault


# ---------------------------------------------------------------------------
# owb stage status
# ---------------------------------------------------------------------------


class TestStageStatus:
    """owb stage status shows current stage and exit criteria."""

    def test_status_shows_current_stage(self, runner: CliRunner, tmp_path: Path) -> None:
        vault = tmp_path / "Obsidian"
        vault.mkdir()
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            f"target: {vault}\nstage:\n  current_stage: 0\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            owb, ["stage", "status", "--vault", str(vault), "--config", str(config_file)]
        )
        assert result.exit_code == 0
        assert "Stage 0" in result.output

    def test_status_shows_criteria(self, runner: CliRunner, tmp_path: Path) -> None:
        vault = tmp_path / "Obsidian"
        vault.mkdir()
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            f"target: {vault}\nstage:\n  current_stage: 0\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            owb, ["stage", "status", "--vault", str(vault), "--config", str(config_file)]
        )
        assert result.exit_code == 0
        # Should show criteria names
        assert "Structural files" in result.output

    def test_status_at_max_stage(self, runner: CliRunner, tmp_path: Path) -> None:
        vault = tmp_path / "Obsidian"
        vault.mkdir()
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            f"target: {vault}\nstage:\n  current_stage: 1\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            owb, ["stage", "status", "--vault", str(vault), "--config", str(config_file)]
        )
        assert result.exit_code == 0
        assert "Stage 1" in result.output


# ---------------------------------------------------------------------------
# owb stage promote
# ---------------------------------------------------------------------------


class TestStagePromote:
    """owb stage promote checks criteria and advances stage."""

    def test_promote_fails_when_criteria_unmet(self, runner: CliRunner, tmp_path: Path) -> None:
        vault = tmp_path / "Obsidian"
        vault.mkdir()
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            f"target: {vault}\nstage:\n  current_stage: 0\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            owb, ["stage", "promote", "--vault", str(vault), "--config", str(config_file)]
        )
        assert result.exit_code != 0
        assert "Cannot promote" in result.output or "not met" in result.output.lower()

    def test_promote_succeeds_when_criteria_met(self, runner: CliRunner, tmp_path: Path) -> None:
        vault = tmp_path / "Obsidian"
        vault.mkdir()
        # Populate Stage 0 → 1 exit criteria
        (vault / "_index.md").write_text("# Index\nContent here.", encoding="utf-8")
        (vault / "_bootstrap.md").write_text("# Bootstrap\nContent here.", encoding="utf-8")
        self_dir = vault / "self"
        self_dir.mkdir()
        (self_dir / "_index.md").write_text(
            "# Self\nReal content about the user.", encoding="utf-8"
        )
        proj = vault / "projects" / "TestProj"
        proj.mkdir(parents=True)
        (proj / "status.md").write_text("# Status\nActive.", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            f"target: {vault}\nstage:\n  current_stage: 0\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            owb, ["stage", "promote", "--vault", str(vault), "--config", str(config_file)]
        )
        assert result.exit_code == 0
        assert "Promoted to Stage 1" in result.output

    def test_promote_writes_updated_config(self, runner: CliRunner, tmp_path: Path) -> None:
        vault = tmp_path / "Obsidian"
        vault.mkdir()
        # Populate exit criteria
        (vault / "_index.md").write_text("# Index\nContent here.", encoding="utf-8")
        (vault / "_bootstrap.md").write_text("# Bootstrap\nContent here.", encoding="utf-8")
        self_dir = vault / "self"
        self_dir.mkdir()
        (self_dir / "_index.md").write_text(
            "# Self\nReal content about the user.", encoding="utf-8"
        )
        proj = vault / "projects" / "TestProj"
        proj.mkdir(parents=True)
        (proj / "status.md").write_text("# Status\nActive.", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            f"target: {vault}\nstage:\n  current_stage: 0\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            owb, ["stage", "promote", "--vault", str(vault), "--config", str(config_file)]
        )
        assert result.exit_code == 0
        # Config file should now show stage 1
        import yaml

        updated = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        assert updated["stage"]["current_stage"] == 1

    def test_promote_with_enable_hooks_persists_config(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        vault = tmp_path / "Obsidian"
        vault.mkdir()
        (vault / "_index.md").write_text("# Index\nContent here.", encoding="utf-8")
        (vault / "_bootstrap.md").write_text("# Bootstrap\nContent here.", encoding="utf-8")
        self_dir = vault / "self"
        self_dir.mkdir()
        (self_dir / "_index.md").write_text(
            "# Self\nReal content about the user.", encoding="utf-8"
        )
        proj = vault / "projects" / "TestProj"
        proj.mkdir(parents=True)
        (proj / "status.md").write_text("# Status\nActive.", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            f"target: {vault}\nstage:\n  current_stage: 0\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            owb,
            [
                "stage",
                "promote",
                "--vault",
                str(vault),
                "--config",
                str(config_file),
                "--enable-hooks",
            ],
        )
        assert result.exit_code == 0
        import yaml

        updated = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        assert updated["enforcement"]["hooks_enabled"] is True

    def test_promote_no_hooks_flag_does_not_persist(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        vault = tmp_path / "Obsidian"
        vault.mkdir()
        (vault / "_index.md").write_text("# Index\nContent here.", encoding="utf-8")
        (vault / "_bootstrap.md").write_text("# Bootstrap\nContent here.", encoding="utf-8")
        self_dir = vault / "self"
        self_dir.mkdir()
        (self_dir / "_index.md").write_text(
            "# Self\nReal content about the user.", encoding="utf-8"
        )
        proj = vault / "projects" / "TestProj"
        proj.mkdir(parents=True)
        (proj / "status.md").write_text("# Status\nActive.", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            f"target: {vault}\nstage:\n  current_stage: 0\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            owb,
            [
                "stage",
                "promote",
                "--vault",
                str(vault),
                "--config",
                str(config_file),
            ],
        )
        assert result.exit_code == 0
        import yaml

        updated = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        assert "enforcement" not in updated

    def test_promote_beyond_phase1_rejected(self, runner: CliRunner, tmp_path: Path) -> None:
        vault = tmp_path / "Obsidian"
        vault.mkdir()
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            f"target: {vault}\nstage:\n  current_stage: 1\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            owb, ["stage", "promote", "--vault", str(vault), "--config", str(config_file)]
        )
        assert result.exit_code != 0
        assert "ABOP Engineering Platform" in result.output

    def test_promote_to_phase2_error_message(self, runner: CliRunner, tmp_path: Path) -> None:
        vault = tmp_path / "Obsidian"
        vault.mkdir()
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            f"target: {vault}\nstage:\n  current_stage: 1\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            owb, ["stage", "promote", "--vault", str(vault), "--config", str(config_file)]
        )
        assert result.exit_code != 0
        assert "Phase 1 is OWB's operational ceiling" in result.output
        assert "Phase 2 and Phase 3 capabilities" in result.output
