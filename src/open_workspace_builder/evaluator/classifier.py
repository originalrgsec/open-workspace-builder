"""Skill type classifier using LLM-based classification with weight vector lookup."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from open_workspace_builder._llm_json import parse_json_object

if TYPE_CHECKING:
    from open_workspace_builder.llm.backend import ModelBackend

_WEIGHT_VECTORS_PATH = Path(__file__).parent / "data" / "weight_vectors.yaml"

_CLASSIFICATION_SYSTEM_PROMPT = """\
You are a skill type classifier. Given the content of an AI skill (its prompt, \
instructions, and configuration), classify it into exactly one skill type.

Valid skill types:
- marketing-copywriting
- security-analysis
- code-review
- research-analysis
- project-management
- document-generation
- data-analysis
- devops-infrastructure
- testing-qa
- general

Respond ONLY with valid JSON matching this schema:
{
  "skill_type": "<one of the valid types above>",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<brief explanation>"
}
"""


@dataclass(frozen=True)
class ClassificationResult:
    """Result of classifying a skill into a type."""

    skill_type: str
    confidence: float
    reasoning: str


def load_weight_vectors(path: Path | None = None) -> dict[str, dict[str, float]]:
    """Load skill type to weight vector mapping from YAML."""
    import yaml  # type: ignore[import-untyped]

    resolved = path or _WEIGHT_VECTORS_PATH
    raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    return raw.get("skill_types", {})


def _parse_classification(response_text: str) -> ClassificationResult:
    """Parse classification response from LLM JSON output."""
    data = parse_json_object(response_text, context="classification response")

    skill_type = data.get("skill_type", "")
    confidence = float(data.get("confidence", 0.0))
    reasoning = str(data.get("reasoning", ""))

    if not skill_type:
        raise ValueError("Response missing 'skill_type'")
    if confidence < 0.0 or confidence > 1.0:
        raise ValueError(f"Confidence {confidence} out of range [0.0, 1.0]")

    return ClassificationResult(
        skill_type=skill_type,
        confidence=confidence,
        reasoning=reasoning,
    )


class SkillClassifier:
    """Classifies skills into types using LLM-based analysis."""

    def __init__(self, model_backend: ModelBackend) -> None:
        self._backend = model_backend

    def classify(self, skill_content: str) -> ClassificationResult:
        """Classify skill content into a skill type.

        Uses the 'classify' operation on the model backend. System prompt contains
        classification instructions (not user-controlled). User message contains
        the skill content (untrusted input), preventing prompt injection.
        """
        response = self._backend.completion(
            operation="classify",
            system_prompt=_CLASSIFICATION_SYSTEM_PROMPT,
            user_message=f"Classify the following skill content:\n\n{skill_content}",
            max_tokens=512,
        )
        return _parse_classification(response)
