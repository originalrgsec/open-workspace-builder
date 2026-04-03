"""Trust manifest for first-party ECC content (S061).

Computes SHA-256 hashes of shipped ECC files to identify unmodified first-party
content during migrate operations. Files matching the manifest are trusted and
skip security scanning. Modified files (hash mismatch) are scanned normally.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def _sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def compute_ecc_hashes(content_root: Path) -> dict[str, dict[str, str]]:
    """Compute SHA-256 hashes for all files in vendor/ecc/.

    Returns a dict mapping relative paths (relative to vendor/ecc/) to
    {"sha256": "<hex>"}.
    """
    ecc_dir = content_root / "vendor" / "ecc"
    if not ecc_dir.is_dir():
        return {}

    result: dict[str, dict[str, str]] = {}
    for f in sorted(ecc_dir.rglob("*")):
        if not f.is_file():
            continue
        rel = str(f.relative_to(ecc_dir))
        result[rel] = {"sha256": _sha256(f)}

    return result


def load_trust_manifest(content_root: Path) -> dict[str, dict[str, str]]:
    """Load or compute the trust manifest for first-party ECC content.

    Currently computes hashes at runtime from vendor/ecc/. A future
    optimization could pre-compute and bundle a manifest file during
    the build/release process.
    """
    return compute_ecc_hashes(content_root)


def is_trusted(
    file_path: Path,
    rel_path: str,
    manifest: dict[str, dict[str, str]],
) -> bool:
    """Check if a file matches the trust manifest (unmodified first-party content).

    Args:
        file_path: Absolute path to the file to check.
        rel_path: Relative path used as the manifest key.
        manifest: Trust manifest from load_trust_manifest().

    Returns:
        True if the file's hash matches the manifest entry. False if the file
        is not in the manifest or has been modified.
    """
    entry = manifest.get(rel_path)
    if entry is None:
        return False

    try:
        file_hash = _sha256(file_path)
    except OSError:
        return False

    return file_hash == entry["sha256"]
