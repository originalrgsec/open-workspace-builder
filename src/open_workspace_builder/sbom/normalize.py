"""OWB-S107a — Content normalization and hashing for SBOM components.

The norm1 algorithm produces stable content hashes across trivial formatting
changes so that `owb sbom verify` does not report drift for cosmetic edits.

Rules:
1. Strip trailing whitespace from every line.
2. Normalize all line endings to LF.
3. Strip the `updated:` YAML frontmatter field (templates bump it on every save).
4. Hash the normalized UTF-8 bytes with SHA-256.
5. Version the algorithm in the output: ``sha256-norm1:<hex>``.

Any future change to the normalization rules MUST bump the version tag
(``norm1`` → ``norm2``) so that SBOMs generated under the old rules remain
interpretable under their original algorithm.
"""

from __future__ import annotations

import hashlib
import re

NORM_VERSION = "norm1"
"""The current normalization algorithm version. Bump on any rule change."""

HASH_PREFIX = f"sha256-{NORM_VERSION}"
"""The fixed prefix for every hash string this module produces."""

_UPDATED_LINE_RE = re.compile(r"^updated:.*$", re.MULTILINE)


def normalize_content(content: str) -> str:
    """Apply the norm1 normalization rules to a string.

    Args:
        content: Raw file content as a string.

    Returns:
        Normalized content suitable for hashing. The output uses LF line
        endings, has no trailing whitespace, has the ``updated:`` frontmatter
        field stripped, and has no trailing newline.
    """
    # Rule 2: normalize line endings. Handle CRLF first so we don't
    # double-convert to \n\n when the input has CRLF.
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    # Rule 3: strip `updated:` inside the leading YAML frontmatter only.
    # Frontmatter is delimited by `---` on the first line and the next `---`.
    content = _strip_updated_in_frontmatter(content)

    # Rule 1: strip trailing whitespace per line.
    lines = [line.rstrip() for line in content.split("\n")]

    # Collapse trailing empty lines to nothing so that a lone `\n` normalizes
    # to an empty string and `a\nb\n` normalizes the same as `a\nb`.
    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


def _strip_updated_in_frontmatter(content: str) -> str:
    """Remove the ``updated:`` line only within a leading YAML frontmatter block.

    A YAML frontmatter block starts with a `---` on the first line and ends
    with the next `---` on its own line. The ``updated:`` line is removed only
    when it appears inside that block; body occurrences are preserved.
    """
    if not content.startswith("---\n") and not content.startswith("---"):
        return content

    # Split on lines; find the frontmatter range.
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return content

    # Find the closing delimiter.
    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        # Unterminated frontmatter — leave untouched.
        return content

    front = lines[1:end_idx]
    body = lines[end_idx:]

    # Drop any line whose key is exactly `updated`.
    front = [ln for ln in front if not _UPDATED_LINE_RE.match(ln)]

    return "\n".join([lines[0], *front, *body])


def compute_hash(content: str | bytes) -> str:
    """Compute the norm1 content hash for a string or bytes input.

    Args:
        content: File content as ``str`` or UTF-8 ``bytes``.

    Returns:
        A hash string in the form ``sha256-norm1:<hex>`` where ``<hex>`` is
        the lowercase 64-character SHA-256 digest of the normalized content.
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    normalized = normalize_content(content)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"{HASH_PREFIX}:{digest}"
