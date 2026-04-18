"""LLM JSON response parsing helpers.

LLM responses often wrap JSON in markdown code fences, e.g.:

    ```json
    {"key": "value"}
    ```

or return it as raw JSON. This module provides a single helper that
handles both shapes, consolidating an identical try/fence-regex pattern
previously duplicated across the evaluator and security modules.
"""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE_OBJECT_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_FENCE_ARRAY_RE = re.compile(r"```(?:json)?\s*(\[.*?\])\s*```", re.DOTALL)


def parse_json_object(response_text: str, *, context: str = "LLM response") -> dict[str, Any]:
    """Parse a JSON object from an LLM response.

    Tries a direct ``json.loads`` first; on failure, falls back to
    extracting a ``{ ... }`` payload from a markdown code fence.

    Args:
        response_text: Raw LLM response text.
        context: Human-readable label included in the ``ValueError``
            message when neither path yields a parseable object.

    Returns:
        The decoded JSON object as a dict.

    Raises:
        ValueError: if neither direct parse nor fence extraction
            succeeds. The first 200 chars of the response are echoed
            back to aid debugging.
    """
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        match = _FENCE_OBJECT_RE.search(response_text)
        if match is None:
            raise ValueError(f"Could not parse {context} as JSON: {response_text[:200]}")
        data = json.loads(match.group(1))

    if not isinstance(data, dict):
        raise ValueError(
            f"Expected JSON object in {context}, got {type(data).__name__}: {response_text[:200]}"
        )
    return data


def parse_json_array(response_text: str, *, context: str = "LLM response") -> list[Any]:
    """Parse a JSON array from an LLM response.

    Same contract as :func:`parse_json_object` but for top-level arrays.
    """
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        match = _FENCE_ARRAY_RE.search(response_text)
        if match is None:
            raise ValueError(f"Could not parse {context} as JSON: {response_text[:200]}")
        data = json.loads(match.group(1))

    if not isinstance(data, list):
        raise ValueError(
            f"Expected JSON array in {context}, got {type(data).__name__}: {response_text[:200]}"
        )
    return data
