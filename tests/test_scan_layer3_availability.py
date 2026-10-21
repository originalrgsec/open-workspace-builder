"""`owb security scan` must not silently drop Layer 3 when it cannot run."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from open_workspace_builder.cli import owb

_REASON = "open_workspace_builder.cli._layer3_unavailable_reason"


def _target(tmp_path: Path) -> Path:
    f = tmp_path / "note.md"
    f.write_text("# Plain note\n", encoding="utf-8")
    return f


def test_explicit_layer3_unavailable_is_usage_error(tmp_path: Path) -> None:
    with patch(_REASON, return_value="models.security_scan is empty in config"):
        result = CliRunner().invoke(
            owb, ["security", "scan", str(_target(tmp_path)), "--layers", "1,2,3"]
        )
    assert result.exit_code == 2
    assert "Layer 3 requested but unavailable" in result.output


def test_config_layer3_unavailable_warns(tmp_path: Path) -> None:
    with patch(_REASON, return_value="litellm is not installed"):
        result = CliRunner().invoke(owb, ["security", "scan", str(_target(tmp_path))])
    assert "Layer 3 (semantic) is enabled in config but will NOT run" in result.output


def test_layers_without_3_do_not_check(tmp_path: Path) -> None:
    with patch(_REASON) as reason:
        CliRunner().invoke(owb, ["security", "scan", str(_target(tmp_path)), "--layers", "1,2"])
    reason.assert_not_called()
