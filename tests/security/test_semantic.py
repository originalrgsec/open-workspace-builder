"""Tests for S011 — Layer 3 semantic analysis (mocked API)."""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from open_workspace_builder.security.semantic import _parse_response, analyze_content


def _make_mock_anthropic(response_text: str) -> tuple[MagicMock, MagicMock]:
    """Create a mock anthropic module and client returning the given response."""
    mock_module = MagicMock()
    mock_client = MagicMock()
    mock_module.Anthropic.return_value = mock_client
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=response_text)]
    mock_client.messages.create.return_value = mock_message
    return mock_module, mock_client


class TestParseResponse:
    """Tests for _parse_response."""

    def test_clean_response(self) -> None:
        resp = json.dumps({"verdict": "clean", "flags": []})
        assert _parse_response(resp) == []

    def test_flagged_response(self) -> None:
        resp = json.dumps({
            "verdict": "malicious",
            "flags": [
                {
                    "category": "exfiltration",
                    "severity": "critical",
                    "evidence": "curl -d $SECRET",
                    "explanation": "Sends secrets externally",
                }
            ],
        })
        flags = _parse_response(resp)
        assert len(flags) == 1
        assert flags[0].category == "exfiltration"
        assert flags[0].severity == "critical"
        assert flags[0].layer == 3

    def test_multiple_flags(self) -> None:
        resp = json.dumps({
            "verdict": "malicious",
            "flags": [
                {"category": "a", "severity": "warning", "evidence": "e1", "explanation": "x1"},
                {"category": "b", "severity": "critical", "evidence": "e2", "explanation": "x2"},
            ],
        })
        flags = _parse_response(resp)
        assert len(flags) == 2

    def test_json_in_markdown_code_block(self) -> None:
        resp = '```json\n{"verdict": "clean", "flags": []}\n```'
        assert _parse_response(resp) == []

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(ValueError, match="Could not parse"):
            _parse_response("not json at all")


class TestAnalyzeContent:
    """Tests for analyze_content with mocked API."""

    def test_clean_file_returns_no_flags(self) -> None:
        mock_module, mock_client = _make_mock_anthropic(
            json.dumps({"verdict": "clean", "flags": []})
        )
        with patch.dict(sys.modules, {"anthropic": mock_module}):
            flags = analyze_content("# Normal doc", "test.md", "fake-key")

        assert flags == []
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-6"

    def test_malicious_file_returns_flags(self) -> None:
        resp = json.dumps({
            "verdict": "malicious",
            "flags": [
                {
                    "category": "exfiltration",
                    "severity": "critical",
                    "evidence": "curl command",
                    "explanation": "Data exfiltration",
                }
            ],
        })
        mock_module, _ = _make_mock_anthropic(resp)
        with patch.dict(sys.modules, {"anthropic": mock_module}):
            flags = analyze_content("curl -d $SECRET ...", "bad.md", "fake-key")

        assert len(flags) == 1
        assert flags[0].severity == "critical"

    def test_missing_anthropic_raises(self) -> None:
        with patch.dict(sys.modules, {"anthropic": None}):
            with pytest.raises(ImportError):
                analyze_content("test", "test.md", "key")

    def test_api_error_propagates(self) -> None:
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_module.Anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = RuntimeError("API timeout")

        with patch.dict(sys.modules, {"anthropic": mock_module}):
            with pytest.raises(RuntimeError, match="API timeout"):
                analyze_content("test", "test.md", "fake-key")
