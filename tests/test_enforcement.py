"""Tests for hook-based policy enforcement (OWB-S067)."""

from __future__ import annotations

import json
import stat
from pathlib import Path

import yaml

from open_workspace_builder.config import Config, EnforcementConfig, StageConfig
from open_workspace_builder.enforcement import (
    deploy_hooks,
    generate_manifest,
    remove_hook_registration,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_policies_dir(tmp_path: Path) -> Path:
    """Create a policies directory with sample policy files."""
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "development-process.md").write_text(
        "# Development Process\n\nSprint mechanics and completion checklist.\n",
        encoding="utf-8",
    )
    (policies / "oss-health-policy.md").write_text(
        "# OSS Health Policy\n\nDependency health scoring and adoption thresholds.\n",
        encoding="utf-8",
    )
    (policies / "_index.md").write_text(
        "# Policy Index\n\nThis is an index file.\n",
        encoding="utf-8",
    )
    return policies


# ---------------------------------------------------------------------------
# generate_manifest
# ---------------------------------------------------------------------------


class TestGenerateManifest:
    """generate_manifest scans a policies dir and writes policy-manifest.yaml."""

    def test_generates_manifest_file(self, tmp_path: Path) -> None:
        policies = _make_policies_dir(tmp_path)
        manifest_path = tmp_path / "policy-manifest.yaml"
        generate_manifest(policies_dir=policies, output_path=manifest_path)
        assert manifest_path.is_file()

    def test_manifest_contains_policies(self, tmp_path: Path) -> None:
        policies = _make_policies_dir(tmp_path)
        manifest_path = tmp_path / "policy-manifest.yaml"
        generate_manifest(policies_dir=policies, output_path=manifest_path)
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        assert "policies" in data
        names = [p["path"] for p in data["policies"]]
        assert "development-process.md" in names
        assert "oss-health-policy.md" in names

    def test_manifest_excludes_index_files(self, tmp_path: Path) -> None:
        policies = _make_policies_dir(tmp_path)
        manifest_path = tmp_path / "policy-manifest.yaml"
        generate_manifest(policies_dir=policies, output_path=manifest_path)
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        names = [p["path"] for p in data["policies"]]
        assert "_index.md" not in names

    def test_manifest_entries_have_summary(self, tmp_path: Path) -> None:
        policies = _make_policies_dir(tmp_path)
        manifest_path = tmp_path / "policy-manifest.yaml"
        generate_manifest(policies_dir=policies, output_path=manifest_path)
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        for entry in data["policies"]:
            assert "summary" in entry
            assert len(entry["summary"]) > 0

    def test_manifest_with_empty_dir(self, tmp_path: Path) -> None:
        policies = tmp_path / "policies"
        policies.mkdir()
        manifest_path = tmp_path / "policy-manifest.yaml"
        generate_manifest(policies_dir=policies, output_path=manifest_path)
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        assert data["policies"] == []

    def test_manifest_with_missing_dir(self, tmp_path: Path) -> None:
        policies = tmp_path / "nonexistent"
        manifest_path = tmp_path / "policy-manifest.yaml"
        generate_manifest(policies_dir=policies, output_path=manifest_path)
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        assert data["policies"] == []

    def test_manifest_is_sorted(self, tmp_path: Path) -> None:
        policies = _make_policies_dir(tmp_path)
        (policies / "allowed-licenses.md").write_text(
            "# Allowed Licenses\n\nApproved OSS licenses.\n", encoding="utf-8"
        )
        manifest_path = tmp_path / "policy-manifest.yaml"
        generate_manifest(policies_dir=policies, output_path=manifest_path)
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        names = [p["path"] for p in data["policies"]]
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# deploy_hooks
# ---------------------------------------------------------------------------


class TestDeployHooks:
    """deploy_hooks writes the hook script, manifest, and settings.json entry."""

    def test_creates_hook_script(self, tmp_path: Path) -> None:
        policies = _make_policies_dir(tmp_path)
        owb_dir = tmp_path / ".owb"
        config = Config(
            enforcement=EnforcementConfig(hooks_enabled=True),
            stage=StageConfig(current_stage=2),
        )
        deploy_hooks(
            config=config,
            policies_dir=policies,
            owb_dir=owb_dir,
            agent_config_dir=tmp_path / ".claude",
        )
        script = owb_dir / "hooks" / "policy-reminder.sh"
        assert script.is_file()
        assert script.stat().st_mode & stat.S_IXUSR  # executable

    def test_creates_manifest(self, tmp_path: Path) -> None:
        policies = _make_policies_dir(tmp_path)
        owb_dir = tmp_path / ".owb"
        config = Config(
            enforcement=EnforcementConfig(hooks_enabled=True),
            stage=StageConfig(current_stage=2),
        )
        deploy_hooks(
            config=config,
            policies_dir=policies,
            owb_dir=owb_dir,
            agent_config_dir=tmp_path / ".claude",
        )
        manifest = owb_dir / "policy-manifest.yaml"
        assert manifest.is_file()

    def test_registers_in_settings_json(self, tmp_path: Path) -> None:
        policies = _make_policies_dir(tmp_path)
        owb_dir = tmp_path / ".owb"
        claude_dir = tmp_path / ".claude"
        config = Config(
            enforcement=EnforcementConfig(hooks_enabled=True),
            stage=StageConfig(current_stage=2),
        )
        deploy_hooks(
            config=config,
            policies_dir=policies,
            owb_dir=owb_dir,
            agent_config_dir=claude_dir,
        )
        settings = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
        assert "hooks" in settings
        hooks = settings["hooks"]
        assert "UserPromptSubmit" in hooks

    def test_skips_when_hooks_disabled(self, tmp_path: Path) -> None:
        policies = _make_policies_dir(tmp_path)
        owb_dir = tmp_path / ".owb"
        config = Config(
            enforcement=EnforcementConfig(hooks_enabled=False),
            stage=StageConfig(current_stage=2),
        )
        deploy_hooks(
            config=config,
            policies_dir=policies,
            owb_dir=owb_dir,
            agent_config_dir=tmp_path / ".claude",
        )
        assert not (owb_dir / "hooks" / "policy-reminder.sh").exists()

    def test_skips_when_stage_below_2(self, tmp_path: Path) -> None:
        policies = _make_policies_dir(tmp_path)
        owb_dir = tmp_path / ".owb"
        config = Config(
            enforcement=EnforcementConfig(hooks_enabled=True),
            stage=StageConfig(current_stage=1),
        )
        deploy_hooks(
            config=config,
            policies_dir=policies,
            owb_dir=owb_dir,
            agent_config_dir=tmp_path / ".claude",
        )
        assert not (owb_dir / "hooks" / "policy-reminder.sh").exists()

    def test_preserves_existing_settings(self, tmp_path: Path) -> None:
        policies = _make_policies_dir(tmp_path)
        owb_dir = tmp_path / ".owb"
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(parents=True)
        existing = {"some_key": "some_value", "hooks": {"OtherHook": [{"command": "echo hi"}]}}
        (claude_dir / "settings.json").write_text(json.dumps(existing), encoding="utf-8")
        config = Config(
            enforcement=EnforcementConfig(hooks_enabled=True),
            stage=StageConfig(current_stage=2),
        )
        deploy_hooks(
            config=config,
            policies_dir=policies,
            owb_dir=owb_dir,
            agent_config_dir=claude_dir,
        )
        settings = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
        assert settings["some_key"] == "some_value"
        assert "OtherHook" in settings["hooks"]
        assert "UserPromptSubmit" in settings["hooks"]


# ---------------------------------------------------------------------------
# remove_hook_registration
# ---------------------------------------------------------------------------


class TestRemoveHookRegistration:
    """remove_hook_registration removes the hook entry from settings.json."""

    def test_removes_hook_entry(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        settings = {
            "hooks": {
                "UserPromptSubmit": [{"command": "bash .owb/hooks/policy-reminder.sh"}],
                "OtherHook": [{"command": "echo hi"}],
            }
        }
        (claude_dir / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        remove_hook_registration(agent_config_dir=claude_dir)
        updated = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
        assert "UserPromptSubmit" not in updated["hooks"]
        assert "OtherHook" in updated["hooks"]

    def test_noop_when_no_settings(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        # No settings.json — should not raise
        remove_hook_registration(agent_config_dir=claude_dir)

    def test_noop_when_no_hook_entry(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        settings = {"hooks": {"OtherHook": [{"command": "echo hi"}]}}
        (claude_dir / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        remove_hook_registration(agent_config_dir=claude_dir)
        updated = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
        assert "OtherHook" in updated["hooks"]
