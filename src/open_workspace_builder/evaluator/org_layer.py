"""Organizational layer classifier for skills and content."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_workspace_builder.llm.backend import ModelBackend

_EXAMPLES_PATH = Path(__file__).parent / "data" / "org_layer_examples.yaml"

_CONFIDENCE_THRESHOLD = 0.7


def _build_system_prompt(examples_path: Path | None = None) -> str:
    """Build the system prompt with few-shot examples from YAML."""
    resolved = examples_path or _EXAMPLES_PATH
    examples_block = ""

    try:
        import yaml  # type: ignore[import-untyped]

        raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        layers = raw.get("layers", [])
        parts: list[str] = []
        for layer_def in layers:
            layer_num = layer_def["layer"]
            name = layer_def["name"]
            desc = layer_def["description"]
            parts.append(f"Layer {layer_num} ({name}): {desc}")
            for ex in layer_def.get("examples", []):
                parts.append(f"  Example: {ex}")
        examples_block = "\n".join(parts)
    except Exception:
        examples_block = (
            "Layer 0 (Identity): Context files, templates, policies\n"
            "Layer 1 (Director): Delegates work, decomposes tasks, routes to other agents\n"
            "Layer 2 (Specialist): Domain expertise, focused execution, no delegation\n"
            "Layer 3 (Sub-agent): Invoked by others, narrow bounded tasks, leaf nodes"
        )

    return f"""\
You are an organizational layer classifier. Given the content of an AI skill \
or configuration file, classify it into one of four layers.

Detection heuristics:
- Delegation/routing/decomposition language → Layer 1 (Director)
- Domain expertise, focused execution, no delegation → Layer 2 (Specialist)
- Narrow tasks, invoked by others, minimal context → Layer 3 (Sub-agent)
- No agent behavior (context, template, policy) → Layer 0 (Identity)

{examples_block}

Respond ONLY with valid JSON matching this schema:
{{
  "layer": <int 0-3>,
  "confidence": <float 0.0-1.0>,
  "reasoning": "<brief explanation>",
  "delegates_to": [<list of layer ints this delegates work to, empty if none>],
  "delegated_by": [<list of layer ints that invoke this, empty if none>]
}}
"""


@dataclass(frozen=True)
class OrgLayerResult:
    """Result of classifying content into an organizational layer."""

    layer: int
    confidence: float
    reasoning: str
    delegated_by: tuple[int, ...]
    delegates_to: tuple[int, ...]
    needs_review: bool


def _parse_layer_response(response_text: str) -> OrgLayerResult:
    """Parse org layer classification from LLM JSON response."""
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        import re

        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
        else:
            raise ValueError(f"Could not parse layer response as JSON: {response_text[:200]}")

    layer = int(data.get("layer", -1))
    if layer not in (0, 1, 2, 3):
        raise ValueError(f"Invalid layer {layer}, must be 0-3")

    confidence = float(data.get("confidence", 0.0))
    if confidence < 0.0 or confidence > 1.0:
        raise ValueError(f"Confidence {confidence} out of range [0.0, 1.0]")

    reasoning = str(data.get("reasoning", ""))
    delegates_to = tuple(int(x) for x in data.get("delegates_to", []))
    delegated_by = tuple(int(x) for x in data.get("delegated_by", []))

    if layer == 3 and delegates_to:
        raise ValueError(
            f"Layer 3 (Sub-agent) cannot have delegates_to entries, got {delegates_to}"
        )

    needs_review = confidence < _CONFIDENCE_THRESHOLD

    return OrgLayerResult(
        layer=layer,
        confidence=confidence,
        reasoning=reasoning,
        delegated_by=delegated_by,
        delegates_to=delegates_to,
        needs_review=needs_review,
    )


class OrgLayerClassifier:
    """Classifies skills and content into organizational layers using LLM analysis."""

    def __init__(
        self,
        model_backend: ModelBackend,
        examples_path: Path | None = None,
    ) -> None:
        self._backend = model_backend
        self._system_prompt = _build_system_prompt(examples_path)

    def classify_layer(self, skill_content: str) -> OrgLayerResult:
        """Classify skill content into an organizational layer (0-3).

        Layer 0 (Identity): Context files, templates, policies
        Layer 1 (Director): Delegates work, decomposes tasks
        Layer 2 (Specialist): Domain expertise, focused execution
        Layer 3 (Sub-agent): Narrow bounded tasks, leaf nodes
        """
        response = self._backend.completion(
            operation="classify",
            system_prompt=self._system_prompt,
            user_message=(f"Classify the organizational layer of this content:\n\n{skill_content}"),
            max_tokens=512,
        )
        return _parse_layer_response(response)
