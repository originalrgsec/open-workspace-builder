"""Tests for OWB-S092 — SCA/SAST defaults changed to enabled."""

from __future__ import annotations

from open_workspace_builder.config import SecurityConfig, load_config


class TestSecurityConfigDefaults:
    """AC-1: SecurityConfig.sca_enabled and sast_enabled default to True."""

    def test_sca_enabled_default_true(self) -> None:
        cfg = SecurityConfig()
        assert cfg.sca_enabled is True

    def test_sast_enabled_default_true(self) -> None:
        cfg = SecurityConfig()
        assert cfg.sast_enabled is True

    def test_load_config_security_defaults(self) -> None:
        """Full config load should propagate the new defaults."""
        config = load_config()
        assert config.security.sca_enabled is True
        assert config.security.sast_enabled is True

    def test_explicit_false_override(self) -> None:
        """Explicit False should still be honoured."""
        cfg = SecurityConfig(sca_enabled=False, sast_enabled=False)
        assert cfg.sca_enabled is False
        assert cfg.sast_enabled is False
