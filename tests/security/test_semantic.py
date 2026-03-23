"""Tests for S011 — Layer 3 semantic analysis (mocked ModelBackend)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from open_workspace_builder.security.semantic import _parse_response, analyze_content


def _make_mock_backend(response_text: str) -> MagicMock:
    """Create a mock ModelBackend returning the given response text."""
    backend = MagicMock()
    backend.completion.return_value = response_text
    return backend


class TestParseResponse:
    """Tests for _parse_response."""

    def test_clean_response(self) -> None:
        resp = json.dumps({"verdict": "clean", "flags": []})
        assert _parse_response(resp) == []

    def test_flagged_response(self) -> None:
        resp = json.dumps(
            {
                "verdict": "malicious",
                "flags": [
                    {
                        "category": "exfiltration",
                        "severity": "critical",
                        "evidence": "curl -d $SECRET",
                        "explanation": "Sends secrets externally",
                    }
                ],
            }
        )
        flags = _parse_response(resp)
        assert len(flags) == 1
        assert flags[0].category == "exfiltration"
        assert flags[0].severity == "critical"
        assert flags[0].layer == 3

    def test_multiple_flags(self) -> None:
        resp = json.dumps(
            {
                "verdict": "malicious",
                "flags": [
                    {"category": "a", "severity": "warning", "evidence": "e1", "explanation": "x1"},
                    {
                        "category": "b",
                        "severity": "critical",
                        "evidence": "e2",
                        "explanation": "x2",
                    },
                ],
            }
        )
        flags = _parse_response(resp)
        assert len(flags) == 2

    def test_json_in_markdown_code_block(self) -> None:
        resp = '```json\n{"verdict": "clean", "flags": []}\n```'
        assert _parse_response(resp) == []

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(ValueError, match="Could not parse"):
            _parse_response("not json at all")


class TestAnalyzeContent:
    """Tests for analyze_content with mocked ModelBackend."""

    def test_clean_file_returns_no_flags(self) -> None:
        backend = _make_mock_backend(json.dumps({"verdict": "clean", "flags": []}))
        flags = analyze_content("# Normal doc", "test.md", backend)

        assert flags == []
        backend.completion.assert_called_once()
        call_kwargs = backend.completion.call_args[1]
        assert call_kwargs["operation"] == "security_scan"

    def test_malicious_file_returns_flags(self) -> None:
        resp = json.dumps(
            {
                "verdict": "malicious",
                "flags": [
                    {
                        "category": "exfiltration",
                        "severity": "critical",
                        "evidence": "curl command",
                        "explanation": "Data exfiltration",
                    }
                ],
            }
        )
        backend = _make_mock_backend(resp)
        flags = analyze_content("curl -d $SECRET ...", "bad.md", backend)

        assert len(flags) == 1
        assert flags[0].severity == "critical"

    def test_system_prompt_passed_through(self) -> None:
        backend = _make_mock_backend(json.dumps({"verdict": "clean", "flags": []}))
        analyze_content("test content", "test.md", backend)

        call_kwargs = backend.completion.call_args[1]
        assert "security analyst" in call_kwargs["system_prompt"]
        assert "test.md" in call_kwargs["user_message"]

    def test_backend_error_propagates(self) -> None:
        backend = MagicMock()
        backend.completion.side_effect = RuntimeError("API timeout")

        with pytest.raises(RuntimeError, match="API timeout"):
            analyze_content("test", "test.md", backend)
