"""Tests for OWB-SEC-005: repo_url validation in sources updater.

Covers the validator used by both `_clone_or_fetch` (sources/updater.py)
and `fetch_upstream` (engine/ecc_update.py). Threat model in the story:
file:// path exfiltration, ssh:// / git:// SSRF, argument-injection
URLs, unbounded clone DoS.
"""

from __future__ import annotations

import pytest

from open_workspace_builder.sources.url_validator import (
    UrlValidationError,
    validate_repo_url,
)


class TestSchemeAllowlist:
    """AC-1: Default allowlist is https only. AC-2: additional schemes opt-in."""

    def test_https_accepted_by_default(self) -> None:
        validate_repo_url("https://github.com/originalrgsec/owb.git")

    def test_http_rejected_by_default(self) -> None:
        with pytest.raises(UrlValidationError, match="scheme"):
            validate_repo_url("http://github.com/evil/repo.git")

    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "file:///home/user/.ssh/id_rsa",
            "ssh://internal.corp/repo.git",
            "git://localhost:9418/repo",
            "ftp://anon@server/file",
            "javascript:alert(1)",
            "data:text/plain,hi",
        ],
    )
    def test_dangerous_schemes_rejected_by_default(self, url: str) -> None:
        with pytest.raises(UrlValidationError, match="scheme"):
            validate_repo_url(url)

    def test_additional_scheme_opt_in(self) -> None:
        validate_repo_url(
            "ssh://git@github.com/originalrgsec/owb.git",
            allowed_schemes=frozenset({"https", "ssh"}),
        )

    def test_empty_scheme_rejected(self) -> None:
        with pytest.raises(UrlValidationError, match="scheme"):
            validate_repo_url("/tmp/local-repo")

    def test_empty_url_rejected(self) -> None:
        with pytest.raises(UrlValidationError):
            validate_repo_url("")


class TestArgumentInjection:
    """AC-4: Reject argument-injection payloads."""

    def test_leading_dash_rejected(self) -> None:
        with pytest.raises(UrlValidationError, match="argument"):
            validate_repo_url("--upload-pack=evil")

    def test_leading_dash_with_whitespace_rejected(self) -> None:
        with pytest.raises(UrlValidationError):
            validate_repo_url(" --upload-pack=evil".strip())

    def test_embedded_upload_pack_in_host_rejected(self) -> None:
        """Classic git argument-injection — hostname beginning with '-'."""
        with pytest.raises(UrlValidationError):
            validate_repo_url("https://-upload-pack=evil/repo.git")

    def test_null_byte_rejected(self) -> None:
        with pytest.raises(UrlValidationError, match="control character"):
            validate_repo_url("https://github.com/repo.git\x00extra")

    def test_newline_rejected(self) -> None:
        with pytest.raises(UrlValidationError, match="control character"):
            validate_repo_url("https://github.com/repo.git\nextra")


class TestHostAllowlist:
    """AC-3: Optional hostname allowlist."""

    def test_no_host_allowlist_means_any_host(self) -> None:
        validate_repo_url("https://example.com/repo.git", allowed_hosts=())

    def test_host_in_allowlist_accepted(self) -> None:
        validate_repo_url(
            "https://github.com/originalrgsec/owb.git",
            allowed_hosts=("github.com", "gitlab.com"),
        )

    def test_host_not_in_allowlist_rejected(self) -> None:
        with pytest.raises(UrlValidationError, match="host"):
            validate_repo_url(
                "https://evil.example.com/repo.git",
                allowed_hosts=("github.com", "gitlab.com"),
            )

    def test_host_match_is_case_insensitive(self) -> None:
        validate_repo_url(
            "https://GitHub.com/owner/repo.git",
            allowed_hosts=("github.com",),
        )

    def test_trailing_dot_normalized(self) -> None:
        validate_repo_url(
            "https://github.com./owner/repo.git",
            allowed_hosts=("github.com",),
        )

    def test_missing_host_rejected(self) -> None:
        """https:// with no host is malformed and unsafe."""
        with pytest.raises(UrlValidationError, match="host"):
            validate_repo_url("https:///owner/repo.git")
