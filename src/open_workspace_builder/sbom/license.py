"""OWB-S107b — SBOM license detection.

Detects the license for a discovered component using a four-step priority
order:

1. Explicit ``license:`` frontmatter field on the component itself.
2. Sibling ``LICENSE`` / ``LICENSE.md`` / ``LICENSE.txt`` / ``COPYING`` file.
3. ``LICENSE`` file in any parent directory up to the workspace root.
4. ``NOASSERTION`` — explicit "we couldn't determine this."

License files are SPDX-identified by distinctive-phrase fingerprinting rather
than full-text hashing. Hashing is too brittle (whitespace, copyright year,
copyright holder all break exact matches), so each SPDX license is identified
by a small list of phrases that must all be present in the (whitespace- and
case-normalized) text. This is the same approach used by GitHub's Licensee
and the FSF license detection tooling.

The runtime allowed-license policy lives in
``src/open_workspace_builder/data/allowed_licenses.toml``, the machine-readable
twin of the human-authored vault doc at ``Obsidian/code/allowed-licenses.md``.
The two are kept in sync via CI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from importlib import resources
from pathlib import Path
from typing import Mapping

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - py3.10 fallback
    import tomli as tomllib  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class LicenseSource(str, Enum):
    """Where the license was discovered for a component."""

    FRONTMATTER = "frontmatter"
    SIBLING_FILE = "sibling-file"
    PARENT_FILE = "parent-file"
    WORKSPACE_ROOT = "workspace-root"
    NOASSERTION = "noassertion"


@dataclass(frozen=True)
class LicenseEntry:
    """Detected license information for a single component.

    A ``spdx_id`` of ``None`` means either no license was found
    (``source == NOASSERTION``) or a license file was found but could not be
    matched to a known SPDX ID (``source`` is one of the FILE values and
    ``custom_name`` is set).
    """

    spdx_id: str | None
    source: LicenseSource
    allowed: bool
    custom_name: str | None = None
    evidence_path: str | None = None


@dataclass(frozen=True)
class AllowedLicensePolicy:
    """Loaded view of ``allowed_licenses.toml`` for runtime cross-reference."""

    policy_version: int
    source_doc: str
    allowed: frozenset[str] = field(default_factory=frozenset)
    conditional: frozenset[str] = field(default_factory=frozenset)
    disallowed: frozenset[str] = field(default_factory=frozenset)

    def is_allowed(self, spdx_id: str) -> bool:
        """Return True if the SPDX ID is in the allowed or conditional buckets."""
        return spdx_id in self.allowed or spdx_id in self.conditional

    def classify(self, spdx_id: str) -> str:
        """Return one of ``allowed``, ``conditional``, ``disallowed``, ``unknown``."""
        if spdx_id in self.allowed:
            return "allowed"
        if spdx_id in self.conditional:
            return "conditional"
        if spdx_id in self.disallowed:
            return "disallowed"
        return "unknown"


# ---------------------------------------------------------------------------
# Policy loader
# ---------------------------------------------------------------------------


def load_allowed_licenses() -> AllowedLicensePolicy:
    """Load the bundled ``allowed_licenses.toml`` policy.

    The toml file is shipped inside the package under ``data/`` so the
    license cross-reference works in any workspace, not just one with the
    vault available.
    """
    pkg_files = resources.files("open_workspace_builder.data")
    toml_path = pkg_files / "allowed_licenses.toml"
    raw_bytes = toml_path.read_bytes()
    data = tomllib.loads(raw_bytes.decode("utf-8"))

    return AllowedLicensePolicy(
        policy_version=int(data.get("policy_version", 1)),
        source_doc=str(data.get("source_doc", "")),
        allowed=frozenset(data.get("allowed", {}).get("ids", [])),
        conditional=frozenset(data.get("conditional", {}).get("ids", [])),
        disallowed=frozenset(data.get("disallowed", {}).get("ids", [])),
    )


# ---------------------------------------------------------------------------
# SPDX identification by distinctive-phrase fingerprinting
# ---------------------------------------------------------------------------


# Each entry maps an SPDX ID to a list of phrases that must ALL appear in the
# normalized text for the license to match. Phrases are matched
# case-insensitively against text that has been collapsed to single spaces.
#
# Order matters: more-specific licenses must come BEFORE less-specific ones
# because the first match wins. For example, "Apache-2.0" must come before
# any hypothetical "Apache-1.x" entry, and "BSD-3-Clause" before "BSD-2-Clause"
# because the 3-clause is a strict superset of the 2-clause.

_SPDX_FINGERPRINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Apache-2.0",
        (
            "apache license",
            "version 2.0",
            "terms and conditions for use, reproduction, and distribution",
        ),
    ),
    (
        "BSD-3-Clause",
        (
            "redistribution and use in source and binary forms",
            "neither the name of",
            "endorse or promote products",
        ),
    ),
    (
        "BSD-2-Clause",
        (
            "redistribution and use in source and binary forms",
            "redistributions of source code must retain",
            "redistributions in binary form must reproduce",
        ),
    ),
    (
        "MIT",
        (
            "permission is hereby granted, free of charge",
            "without restriction, including without limitation",
            "to use, copy, modify, merge, publish, distribute",
        ),
    ),
    (
        "ISC",
        (
            "permission to use, copy, modify",
            "for any purpose with or without fee",
            "the above copyright notice and this permission notice",
        ),
    ),
    (
        "GPL-3.0",
        (
            "gnu general public license",
            "version 3",
            "free, copyleft license",
        ),
    ),
    (
        "GPL-2.0",
        (
            "gnu general public license",
            "version 2",
        ),
    ),
    (
        "AGPL-3.0",
        (
            "gnu affero general public license",
            "version 3",
        ),
    ),
    (
        "LGPL-3.0",
        (
            "gnu lesser general public license",
            "version 3",
        ),
    ),
    (
        "LGPL-2.1",
        (
            "gnu lesser general public license",
            "version 2.1",
        ),
    ),
    (
        "MPL-2.0",
        (
            "mozilla public license",
            "version 2.0",
        ),
    ),
    (
        "Unlicense",
        (
            "free and unencumbered software released into the public domain",
            "anyone is free to copy, modify, publish",
        ),
    ),
    (
        "0BSD",
        (
            "permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby granted",
            "the software is provided",
        ),
    ),
)

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_for_match(text: str) -> str:
    """Lowercase and collapse all whitespace runs to a single space."""
    return _WHITESPACE_RE.sub(" ", text.lower()).strip()


def identify_spdx(license_text: str) -> str | None:
    """Attempt to identify the SPDX ID of a license text.

    Args:
        license_text: Raw license file content.

    Returns:
        The SPDX ID (e.g. ``"MIT"``, ``"Apache-2.0"``) if every distinctive
        phrase for that license is present, else ``None``.
    """
    if not license_text or not license_text.strip():
        return None

    normalized = _normalize_for_match(license_text)
    for spdx_id, phrases in _SPDX_FINGERPRINTS:
        if all(phrase in normalized for phrase in phrases):
            return spdx_id
    return None


# ---------------------------------------------------------------------------
# License file discovery
# ---------------------------------------------------------------------------


_LICENSE_FILENAMES: tuple[str, ...] = (
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    "LICENCE",
    "LICENCE.md",
    "LICENCE.txt",
    "COPYING",
    "COPYING.md",
    "COPYING.txt",
)


def _find_license_file(directory: Path) -> Path | None:
    """Return the first known license filename present in ``directory``."""
    for name in _LICENSE_FILENAMES:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Top-level detection
# ---------------------------------------------------------------------------


def detect_license(
    *,
    component_path: Path,
    workspace: Path,
    frontmatter: Mapping[str, str],
    policy: AllowedLicensePolicy | None = None,
) -> LicenseEntry:
    """Detect a component's license following the four-step priority order.

    Args:
        component_path: Path to the component file (e.g. SKILL.md).
        workspace: Workspace root for the parent-directory walk fallback.
        frontmatter: Parsed component frontmatter as a flat string→string map.
        policy: Optional pre-loaded allowed-license policy. If omitted, loads
            the bundled policy on every call (cache via the caller for
            performance).

    Returns:
        A :class:`LicenseEntry` with detection source, SPDX ID (if any), and
        allowed flag.
    """
    if policy is None:
        policy = load_allowed_licenses()

    # Step 1: explicit frontmatter
    explicit = frontmatter.get("license") if frontmatter else None
    if explicit:
        return LicenseEntry(
            spdx_id=explicit,
            source=LicenseSource.FRONTMATTER,
            allowed=policy.is_allowed(explicit),
        )

    # Step 2: sibling LICENSE in same dir as the component
    sibling_dir = component_path.parent
    sibling = _find_license_file(sibling_dir)
    if sibling is not None:
        return _entry_from_license_file(
            license_file=sibling,
            workspace=workspace,
            source=LicenseSource.SIBLING_FILE,
            policy=policy,
        )

    # Step 3: parent directory walk up to (but not including) workspace root
    parent = sibling_dir.parent
    workspace_resolved = workspace.resolve()
    while parent != parent.parent:
        try:
            parent_resolved = parent.resolve()
        except OSError:
            break
        # Stop once we leave the workspace tree
        if not _is_within(parent_resolved, workspace_resolved):
            break
        # Skip the workspace root itself — that's step 4
        if parent_resolved == workspace_resolved:
            break
        found = _find_license_file(parent)
        if found is not None:
            return _entry_from_license_file(
                license_file=found,
                workspace=workspace,
                source=LicenseSource.PARENT_FILE,
                policy=policy,
            )
        parent = parent.parent

    # Step 4: workspace root LICENSE
    root_license = _find_license_file(workspace)
    if root_license is not None:
        return _entry_from_license_file(
            license_file=root_license,
            workspace=workspace,
            source=LicenseSource.WORKSPACE_ROOT,
            policy=policy,
        )

    # Step 5: NOASSERTION
    return LicenseEntry(
        spdx_id=None,
        source=LicenseSource.NOASSERTION,
        allowed=False,
    )


def _entry_from_license_file(
    *,
    license_file: Path,
    workspace: Path,
    source: LicenseSource,
    policy: AllowedLicensePolicy,
) -> LicenseEntry:
    """Read a license file, identify its SPDX ID, and build a LicenseEntry."""
    try:
        text = license_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""

    spdx_id = identify_spdx(text)
    try:
        rel_path = str(license_file.relative_to(workspace))
    except ValueError:
        rel_path = str(license_file)

    if spdx_id is not None:
        return LicenseEntry(
            spdx_id=spdx_id,
            source=source,
            allowed=policy.is_allowed(spdx_id),
            evidence_path=rel_path,
        )

    # Found a license file but couldn't identify it. Record as custom.
    return LicenseEntry(
        spdx_id=None,
        source=source,
        allowed=False,
        custom_name=f"LicenseRef-OWB-{license_file.name}",
        evidence_path=rel_path,
    )


def _is_within(path: Path, ancestor: Path) -> bool:
    """Return True if ``path`` is at or below ``ancestor``."""
    try:
        path.relative_to(ancestor)
        return True
    except ValueError:
        return False
