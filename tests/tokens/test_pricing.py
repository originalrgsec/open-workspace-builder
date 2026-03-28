"""Tests for the pricing registry."""

from __future__ import annotations

from pathlib import Path


from open_workspace_builder.tokens.models import ModelPricing
from open_workspace_builder.tokens.pricing import get_pricing, load_pricing


class TestLoadPricing:
    def test_defaults_include_opus(self) -> None:
        pricing = load_pricing(override_path=Path("/nonexistent/path.yaml"))
        assert "claude-opus-4-6" in pricing
        opus = pricing["claude-opus-4-6"]
        assert opus.input_per_mtok == 5.00
        assert opus.output_per_mtok == 25.00

    def test_defaults_include_sonnet(self) -> None:
        pricing = load_pricing(override_path=Path("/nonexistent/path.yaml"))
        assert "claude-sonnet-4-6" in pricing
        sonnet = pricing["claude-sonnet-4-6"]
        assert sonnet.input_per_mtok == 3.00
        assert sonnet.output_per_mtok == 15.00

    def test_defaults_include_haiku(self) -> None:
        pricing = load_pricing(override_path=Path("/nonexistent/path.yaml"))
        assert "claude-haiku-4-5-20251001" in pricing
        haiku = pricing["claude-haiku-4-5-20251001"]
        assert haiku.input_per_mtok == 1.00
        assert haiku.output_per_mtok == 5.00

    def test_yaml_overrides(self, tmp_path: Path) -> None:
        pricing_yaml = tmp_path / "pricing.yaml"
        pricing_yaml.write_text(
            "models:\n"
            "  custom-model:\n"
            "    input_per_mtok: 0.50\n"
            "    output_per_mtok: 1.50\n"
            "    cache_write_per_mtok: 0.60\n"
            "    cache_read_per_mtok: 0.05\n"
        )
        pricing = load_pricing(override_path=pricing_yaml)
        assert "custom-model" in pricing
        assert pricing["custom-model"].input_per_mtok == 0.50
        # Defaults are still present
        assert "claude-opus-4-6" in pricing

    def test_yaml_override_replaces_default(self, tmp_path: Path) -> None:
        pricing_yaml = tmp_path / "pricing.yaml"
        pricing_yaml.write_text(
            "models:\n"
            "  claude-opus-4-6:\n"
            "    input_per_mtok: 10.00\n"
            "    output_per_mtok: 50.00\n"
            "    cache_write_per_mtok: 12.50\n"
            "    cache_read_per_mtok: 1.00\n"
        )
        pricing = load_pricing(override_path=pricing_yaml)
        assert pricing["claude-opus-4-6"].input_per_mtok == 10.00

    def test_missing_yaml_returns_defaults(self) -> None:
        pricing = load_pricing(override_path=Path("/definitely/not/a/file.yaml"))
        assert len(pricing) >= 3


class TestGetPricing:
    def test_exact_match(self) -> None:
        registry = {
            "claude-opus-4-6": ModelPricing(5.0, 25.0, 6.25, 0.50),
        }
        result = get_pricing("claude-opus-4-6", registry)
        assert result is not None
        assert result.input_per_mtok == 5.0

    def test_date_suffix_fallback(self) -> None:
        registry = {
            "claude-haiku-4-5": ModelPricing(1.0, 5.0, 1.25, 0.10),
        }
        result = get_pricing("claude-haiku-4-5-20251001", registry)
        assert result is not None
        assert result.input_per_mtok == 1.0

    def test_unknown_model(self) -> None:
        registry = {
            "claude-opus-4-6": ModelPricing(5.0, 25.0, 6.25, 0.50),
        }
        result = get_pricing("unknown-model", registry)
        assert result is None
