"""OWB-SEC-005: Validate ``repo_url`` before dispatching to git.

Attack surface (from OWB-S136 security-reviewer HIGH-2):

1. ``file:///etc/passwd`` — local file exfiltration via git's file
   transport. ``git clone`` copies the contents into the workspace
   where OWB later scans / commits them.
2. ``ssh://target.internal`` / ``git://host:9418`` — SSRF probing
   of internal services or authenticated git endpoints. The
   CVE-2017-1000117-class argument-injection pattern lives here:
   a hostname starting with ``-`` is parsed by git as a flag.
3. Unbounded ``https://`` clone of an attacker-controlled URL —
   resource exhaustion. (Not covered here; a size cap at the
   subprocess level is tracked in OWB-S143.)

Design choices:

- ``urllib.parse.urlsplit`` (not ``urlparse``): the former does not
  accept semicolons as path separators, which matters for modern
  URL safety.
- Default scheme allowlist is ``{"https"}``. All existing OWB
  source configs use https, so the default is backwards-compatible
  for production users.
- Opt-in extension via ``SourcesConfig.allowed_schemes`` /
  ``allowed_hosts`` (wired in sources/updater.py and
  engine/ecc_update.py).
- Control characters and leading ``-`` fail fast before any parse
  attempt, because these are the argument-injection shapes.
"""

from __future__ import annotations

from urllib.parse import urlsplit

_DEFAULT_ALLOWED_SCHEMES: frozenset[str] = frozenset({"https"})


class UrlValidationError(ValueError):
    """Raised when a repo URL fails the validation checks.

    Subclasses ``ValueError`` so existing callers that catch
    ``ValueError`` at config-load boundaries keep working; the
    failure is always a user-input error, not a bug.
    """


def validate_repo_url(
    url: str,
    allowed_schemes: frozenset[str] | None = None,
    allowed_hosts: tuple[str, ...] = (),
) -> None:
    """Validate ``url`` before passing it to ``git clone``/``git fetch``.

    Args:
        url: The URL to validate. Typically
            ``SourceEntryConfig.repo_url`` or the ``repo_url``
            field of ``.upstream-meta.json``.
        allowed_schemes: Permitted schemes. ``None`` falls back
            to the default (``{"https"}``).
        allowed_hosts: Optional hostname allowlist. Empty tuple
            means any host is accepted. Matching is case-
            insensitive and strips a trailing ``.``.

    Raises:
        UrlValidationError: If the URL is empty, has a control
            character, begins with ``-``, has a disallowed scheme,
            or — when ``allowed_hosts`` is non-empty — has a host
            not in the allowlist.
    """
    if not url:
        raise UrlValidationError("repo_url is empty")

    if any(c in url for c in ("\x00", "\n", "\r")):
        raise UrlValidationError(f"repo_url contains a control character: {url!r}")

    if url.startswith("-"):
        raise UrlValidationError(f"repo_url begins with '-' (argument-injection shape): {url!r}")

    schemes = allowed_schemes if allowed_schemes is not None else _DEFAULT_ALLOWED_SCHEMES

    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if not scheme:
        raise UrlValidationError(
            f"repo_url has no scheme (must be one of {sorted(schemes)}): {url!r}"
        )
    if scheme not in schemes:
        raise UrlValidationError(
            f"repo_url scheme '{scheme}' not in allowlist {sorted(schemes)}: {url!r}"
        )

    host = parts.hostname or ""
    if host.startswith("-"):
        raise UrlValidationError(
            f"repo_url host begins with '-' (argument-injection shape): {url!r}"
        )

    if not host:
        raise UrlValidationError(f"repo_url has no host: {url!r}")

    if allowed_hosts:
        normalised_host = host.rstrip(".").lower()
        normalised_allow = {h.rstrip(".").lower() for h in allowed_hosts}
        if normalised_host not in normalised_allow:
            raise UrlValidationError(
                f"repo_url host '{host}' not in allowlist {sorted(allowed_hosts)}: {url!r}"
            )
