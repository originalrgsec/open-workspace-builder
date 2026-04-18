"""Unit tests for the shared LLM JSON-fence parser helper."""

from __future__ import annotations

import pytest

from open_workspace_builder._llm_json import (
    _MAX_FENCE_INPUT,
    parse_json_array,
    parse_json_object,
)


class TestParseJsonObject:
    def test_raw_json_object(self) -> None:
        assert parse_json_object('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}

    def test_fenced_with_json_tag(self) -> None:
        text = 'Here is the response:\n```json\n{"score": 0.9}\n```\nDone.'
        assert parse_json_object(text) == {"score": 0.9}

    def test_fenced_without_tag(self) -> None:
        text = '```\n{"key": "value"}\n```'
        assert parse_json_object(text) == {"key": "value"}

    def test_malformed_text_raises(self) -> None:
        with pytest.raises(ValueError, match="Could not parse response as JSON"):
            parse_json_object("this is not json", context="response")

    def test_context_appears_in_error(self) -> None:
        with pytest.raises(ValueError, match="classification response"):
            parse_json_object("not json", context="classification response")

    def test_top_level_array_raises_type_mismatch(self) -> None:
        with pytest.raises(ValueError, match="Expected JSON object"):
            parse_json_object("[1, 2, 3]")

    def test_fenced_array_in_object_parser_raises_could_not_parse(self) -> None:
        # The object fence regex only matches `{ ... }`. A fenced array
        # does not match the object regex, so the parser reports
        # "Could not parse ... as JSON" rather than "Expected JSON object".
        with pytest.raises(ValueError, match="Could not parse"):
            parse_json_object('```json\n[{"a": 1}]\n```')

    def test_malformed_json_inside_fence_reraises(self) -> None:
        # Fence regex matches; the substring is still not valid JSON.
        text = "```json\n{not: json}\n```"
        with pytest.raises(ValueError):
            parse_json_object(text)

    def test_input_length_cap_prevents_redos(self) -> None:
        # Pathological payload: open fence, no close, filled with braces.
        # Without the length cap, the lazy `.*?` in the regex would
        # backtrack through every position. Capped, the search returns
        # quickly with no match and the caller gets a clean ValueError.
        payload = "```json\n{" + ("x" * (_MAX_FENCE_INPUT * 4))
        with pytest.raises(ValueError, match="Could not parse"):
            parse_json_object(payload)


class TestParseJsonArray:
    def test_raw_json_array(self) -> None:
        assert parse_json_array("[1, 2, 3]") == [1, 2, 3]

    def test_fenced_array(self) -> None:
        text = '```json\n[{"id": "A"}, {"id": "B"}]\n```'
        assert parse_json_array(text) == [{"id": "A"}, {"id": "B"}]

    def test_object_raises_type_mismatch(self) -> None:
        with pytest.raises(ValueError, match="Expected JSON array"):
            parse_json_array('{"not": "an array"}')

    def test_malformed_text_raises(self) -> None:
        with pytest.raises(ValueError, match="Could not parse"):
            parse_json_array("no json here")

    def test_input_length_cap_prevents_redos(self) -> None:
        payload = "```json\n[" + ("x" * (_MAX_FENCE_INPUT * 4))
        with pytest.raises(ValueError, match="Could not parse"):
            parse_json_array(payload)
