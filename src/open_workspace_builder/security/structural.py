"""S009 — Layer 1: Structural checks (file type, size, encoding)."""

from __future__ import annotations

from pathlib import Path

from open_workspace_builder.security.scanner import ScanFlag

# Zero-width and invisible Unicode characters to detect.
_INVISIBLE_CHARS: dict[str, str] = {
    "\u200b": "U+200B ZERO WIDTH SPACE",
    "\u200c": "U+200C ZERO WIDTH NON-JOINER",
    "\u200d": "U+200D ZERO WIDTH JOINER",
    "\ufeff": "U+FEFF BYTE ORDER MARK",
}

_RTL_OVERRIDE = "\u202e"

# Executable/binary extensions that should never appear as workspace content.
_BINARY_EXTENSIONS: frozenset[str] = frozenset({
    ".exe", ".dll", ".so", ".dylib", ".bin", ".com",
    ".sh", ".bat", ".cmd", ".ps1", ".msi", ".app",
    ".pyc", ".pyo", ".class", ".jar", ".war",
})

_MARKDOWN_EXTENSIONS: frozenset[str] = frozenset({".md", ".markdown", ".mdown", ".mkd"})


def check_file_type(path: Path) -> list[ScanFlag]:
    """Verify file is markdown; flag executables, binaries, and symlinks."""
    flags: list[ScanFlag] = []

    if path.is_symlink():
        flags.append(ScanFlag(
            category="structural",
            severity="warning",
            evidence=f"Symlink: {path} -> {path.resolve()}",
            description="File is a symlink — potential path traversal",
            layer=1,
        ))

    suffix = path.suffix.lower()
    if suffix in _BINARY_EXTENSIONS:
        flags.append(ScanFlag(
            category="structural",
            severity="critical",
            evidence=f"Binary/executable extension: {suffix}",
            description="Binary or executable file in content directory",
            layer=1,
        ))
    elif suffix not in _MARKDOWN_EXTENSIONS:
        flags.append(ScanFlag(
            category="structural",
            severity="info",
            evidence=f"Non-markdown extension: {suffix}",
            description="File is not a markdown file",
            layer=1,
        ))

    return flags


def check_file_size(path: Path, max_kb: int = 500) -> list[ScanFlag]:
    """Flag files exceeding max_kb kilobytes."""
    flags: list[ScanFlag] = []
    try:
        size_kb = path.stat().st_size / 1024
        if size_kb > max_kb:
            flags.append(ScanFlag(
                category="structural",
                severity="warning",
                evidence=f"File size: {size_kb:.1f} KB (limit: {max_kb} KB)",
                description="Oversized content file",
                layer=1,
            ))
    except OSError as exc:
        flags.append(ScanFlag(
            category="structural",
            severity="warning",
            evidence=str(exc),
            description="Could not read file size",
            layer=1,
        ))
    return flags


def check_encoding(path: Path) -> list[ScanFlag]:
    """Detect zero-width characters, RTL overrides, and homoglyphs."""
    flags: list[ScanFlag] = []
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        flags.append(ScanFlag(
            category="structural",
            severity="warning",
            evidence=str(exc),
            description="Could not read file for encoding check",
            layer=1,
        ))
        return flags

    for line_num, line in enumerate(content.splitlines(), start=1):
        for char, name in _INVISIBLE_CHARS.items():
            if char in line:
                flags.append(ScanFlag(
                    category="encoding",
                    severity="warning",
                    evidence=f"Line {line_num}: {name}",
                    description=f"Invisible Unicode character detected: {name}",
                    line_number=line_num,
                    layer=1,
                ))

        if _RTL_OVERRIDE in line:
            flags.append(ScanFlag(
                category="encoding",
                severity="critical",
                evidence=f"Line {line_num}: U+202E RIGHT-TO-LEFT OVERRIDE",
                description="RTL override character — can disguise text direction",
                line_number=line_num,
                layer=1,
            ))

        # Detect characters in non-visible Unicode ranges (homoglyphs).
        for i, ch in enumerate(line):
            cp = ord(ch)
            # Skip standard ASCII, common Latin, and standard punctuation.
            if cp < 0x0250:
                continue
            # Skip common CJK, emoji, and standard symbol ranges.
            if 0x2000 <= cp <= 0x206F:  # General Punctuation (already covered above)
                continue
            # Flag Cyrillic, Greek, and other lookalike ranges mixed in ASCII text.
            if 0x0370 <= cp <= 0x03FF or 0x0400 <= cp <= 0x04FF:
                # Only flag if the file is predominantly ASCII (likely homoglyph attack).
                ascii_ratio = sum(1 for c in content if ord(c) < 128) / max(len(content), 1)
                if ascii_ratio > 0.9:
                    flags.append(ScanFlag(
                        category="encoding",
                        severity="warning",
                        evidence=f"Line {line_num}, col {i + 1}: U+{cp:04X} in ASCII-dominant file",
                        description="Potential homoglyph character in predominantly ASCII file",
                        line_number=line_num,
                        layer=1,
                    ))
                    break  # One flag per line is sufficient.

    return flags


def check_structural(path: Path) -> list[ScanFlag]:
    """Run all Layer 1 structural checks, return combined flags."""
    flags: list[ScanFlag] = []
    flags.extend(check_file_type(path))
    flags.extend(check_file_size(path))
    flags.extend(check_encoding(path))
    return flags
