"""Model pricing registry with hardcoded defaults and YAML override support."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from open_workspace_builder.tokens.models import ModelPricing

# Hardcoded defaults based on Anthropic pricing as of 2026-03-28.
# Cache write = 1.25x input (1-hour tier). Cache read = 0.1x input.
_DEFAULT_PRICING: dict[str, ModelPricing] = {
    "claude-opus-4-6": ModelPricing(
        input_per_mtok=5.00,
        output_per_mtok=25.00,
        cache_write_per_mtok=6.25,
        cache_read_per_mtok=0.50,
    ),
    "claude-sonnet-4-6": ModelPricing(
        input_per_mtok=3.00,
        output_per_mtok=15.00,
        cache_write_per_mtok=3.75,
        cache_read_per_mtok=0.30,
    ),
    "claude-haiku-4-5-20251001": ModelPricing(
        input_per_mtok=1.00,
        output_per_mtok=5.00,
        cache_write_per_mtok=1.25,
        cache_read_per_mtok=0.10,
    ),
    # Alias without date suffix for flexible matching.
    "claude-haiku-4-5": ModelPricing(
        input_per_mtok=1.00,
        output_per_mtok=5.00,
        cache_write_per_mtok=1.25,
        cache_read_per_mtok=0.10,
    ),
}


def _load_yaml_overrides(path: Path) -> dict[str, ModelPricing]:
    """Load pricing overrides from a YAML file.

    Expected format:
        models:
          model-name:
            input_per_mtok: 5.00
            output_per_mtok: 25.00
            cache_write_per_mtok: 6.25
            cache_read_per_mtok: 0.50
    """
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return {}

    if not path.exists():
        return {}

    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    models_raw = raw.get("models", {})
    result: dict[str, ModelPricing] = {}
    for model_name, pricing_dict in models_raw.items():
        if not isinstance(pricing_dict, dict):
            continue
        result[model_name] = ModelPricing(
            input_per_mtok=float(pricing_dict.get("input_per_mtok", 0)),
            output_per_mtok=float(pricing_dict.get("output_per_mtok", 0)),
            cache_write_per_mtok=float(pricing_dict.get("cache_write_per_mtok", 0)),
            cache_read_per_mtok=float(pricing_dict.get("cache_read_per_mtok", 0)),
        )
    return result


def load_pricing(override_path: Path | None = None) -> dict[str, ModelPricing]:
    """Load the pricing registry: defaults overlaid with optional YAML overrides.

    Override path defaults to ~/.owb/pricing.yaml if not specified.
    """
    pricing = dict(_DEFAULT_PRICING)
    search_path = override_path or Path.home() / ".owb" / "pricing.yaml"
    overrides = _load_yaml_overrides(search_path)
    pricing.update(overrides)
    return pricing


def get_pricing(model: str, registry: dict[str, ModelPricing] | None = None) -> ModelPricing | None:
    """Look up pricing for a model name, with fuzzy matching on known aliases."""
    if registry is None:
        registry = load_pricing()
    if model in registry:
        return registry[model]
    # Try without date suffixes (e.g., "claude-haiku-4-5-20251001" -> "claude-haiku-4-5")
    parts = model.rsplit("-", 1)
    if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 8:
        return registry.get(parts[0])
    return None
