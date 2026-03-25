"""Agent Skills spec validation per agentskills.io/specification."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Name pattern: lowercase alphanumeric + hyphens, no leading/trailing/consecutive hyphens
_NAME_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
_CONSECUTIVE_HYPHENS = re.compile(r"--")

# ECC directory markers — paths containing these are treated as ECC content
_ECC_PATH_MARKERS = ("ecc-curated", "vendor/ecc", "vendor\\ecc")

_TRIGGER_KEYWORDS = ("when", "use this")

_MAX_NAME_LENGTH = 64
_MAX_DESCRIPTION_LENGTH = 1024
_MAX_COMPATIBILITY_LENGTH = 500
_MAX_BODY_LINES = 500


@dataclass(frozen=True)
class SpecValidationResult:
    """Result of validating a skill against the Agent Skills spec."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _is_ecc_path(skill_path: str) -> bool:
    """Return True if the path is under an ECC directory."""
    normalized = str(skill_path).replace("\\", "/")
    return any(marker.replace("\\", "/") in normalized for marker in _ECC_PATH_MARKERS)


def _parse_frontmatter(text: str) -> tuple[dict[str, str] | None, str]:
    """Extract YAML frontmatter and body from SKILL.md content.

    Returns (frontmatter_dict, body) or (None, full_text) if no frontmatter.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, text

    end_index = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_index = i
            break

    if end_index is None:
        return None, text

    # Parse the YAML frontmatter manually to avoid external dependency.
    # The spec requires simple key: value pairs.
    fm: dict[str, str] = {}
    current_key: str | None = None
    current_value_lines: list[str] = []

    for line in lines[1:end_index]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Check for a new key: value pair
        colon_pos = line.find(":")
        if colon_pos > 0 and not line[:colon_pos].startswith(" "):
            # Save previous key
            if current_key is not None:
                fm[current_key] = _join_value(current_value_lines)
            current_key = line[:colon_pos].strip()
            raw_value = line[colon_pos + 1 :].strip()
            # Handle block scalar indicators
            if raw_value in (">", "|", ">-", "|-"):
                current_value_lines = []
            else:
                current_value_lines = [_strip_quotes(raw_value)]
        elif current_key is not None:
            # Continuation line for multi-line value
            current_value_lines.append(stripped)

    if current_key is not None:
        fm[current_key] = _join_value(current_value_lines)

    body = "\n".join(lines[end_index + 1 :])
    return fm, body


def _strip_quotes(value: str) -> str:
    """Remove surrounding quotes from a YAML value."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def _join_value(lines: list[str]) -> str:
    """Join multi-line YAML value into a single string."""
    return " ".join(line for line in lines if line).strip()


def validate_frontmatter(frontmatter: dict[str, str], *, is_ecc: bool = False) -> SpecValidationResult:
    """Validate parsed frontmatter against Agent Skills spec rules.

    If is_ecc is True, structural errors are downgraded to warnings.
    """
    errors: list[str] = []
    warnings: list[str] = []

    _downgrade = warnings if is_ecc else errors

    # Required: name
    name = frontmatter.get("name", "").strip()
    if not name:
        _downgrade.append("Missing required field: name")
    else:
        _validate_name_field(name, _downgrade, warnings)

    # Required: description
    description = frontmatter.get("description", "").strip()
    if not description:
        _downgrade.append("Missing required field: description")
    elif len(description) > _MAX_DESCRIPTION_LENGTH:
        _downgrade.append(
            f"Description exceeds {_MAX_DESCRIPTION_LENGTH} characters ({len(description)})"
        )

    # Optional: compatibility
    compat = frontmatter.get("compatibility", "")
    if compat and len(compat) > _MAX_COMPATIBILITY_LENGTH:
        warnings.append(
            f"Compatibility exceeds {_MAX_COMPATIBILITY_LENGTH} characters ({len(compat)})"
        )

    # Optional: allowed-tools — space-delimited string
    allowed_tools = frontmatter.get("allowed-tools", "")
    if allowed_tools:
        _validate_allowed_tools(allowed_tools, warnings)

    # Warning: description lacks trigger keywords
    if description and not any(kw in description.lower() for kw in _TRIGGER_KEYWORDS):
        warnings.append(
            "Description lacks trigger keywords (no 'when' or 'use this')"
        )

    return SpecValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def _validate_name_field(name: str, errors: list[str], warnings: list[str]) -> None:
    """Validate the name field against spec rules."""
    if len(name) > _MAX_NAME_LENGTH:
        errors.append(f"Name exceeds {_MAX_NAME_LENGTH} characters ({len(name)})")
    if name != name.lower():
        errors.append(f"Name must be lowercase: {name!r}")
    if not _NAME_PATTERN.match(name):
        errors.append(f"Name contains invalid characters: {name!r}")
    if name.startswith("-"):
        errors.append(f"Name must not start with a hyphen: {name!r}")
    if name.endswith("-"):
        errors.append(f"Name must not end with a hyphen: {name!r}")
    if _CONSECUTIVE_HYPHENS.search(name):
        errors.append(f"Name must not contain consecutive hyphens: {name!r}")


def _validate_allowed_tools(value: str, warnings: list[str]) -> None:
    """Validate allowed-tools is a space-delimited string of identifiers."""
    parts = value.split()
    for part in parts:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_*]*$", part):
            warnings.append(f"allowed-tools contains suspicious token: {part!r}")


def validate_skill(skill_path: str) -> SpecValidationResult:
    """Validate a skill directory against the Agent Skills spec.

    Checks for SKILL.md existence, frontmatter presence and validity,
    body length, and subdirectory structure.
    """
    path = Path(skill_path)
    errors: list[str] = []
    warnings: list[str] = []
    is_ecc = _is_ecc_path(skill_path)

    skill_md = path / "SKILL.md"
    if not skill_md.exists():
        errors.append(f"SKILL.md not found in {path}")
        return SpecValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    content = skill_md.read_text(encoding="utf-8")
    frontmatter, body = _parse_frontmatter(content)

    if frontmatter is None:
        msg = "YAML frontmatter not found (missing --- delimiters)"
        if is_ecc:
            warnings.append(msg)
        else:
            errors.append(msg)
        return SpecValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    # Validate frontmatter
    fm_result = validate_frontmatter(frontmatter, is_ecc=is_ecc)
    errors.extend(fm_result.errors)
    warnings.extend(fm_result.warnings)

    # Check name matches parent directory
    name = frontmatter.get("name", "").strip()
    if name and name != path.name:
        msg = f"Name {name!r} does not match directory name {path.name!r}"
        if is_ecc:
            warnings.append(msg)
        else:
            errors.append(msg)

    # Warning: body over 500 lines
    body_lines = body.strip().split("\n") if body.strip() else []
    if len(body_lines) > _MAX_BODY_LINES:
        warnings.append(f"SKILL.md body exceeds {_MAX_BODY_LINES} lines ({len(body_lines)})")

    # Warning: missing subdirectories
    expected_dirs = ("scripts", "references", "assets")
    missing_dirs = [d for d in expected_dirs if not (path / d).is_dir()]
    if missing_dirs:
        warnings.append(f"Missing optional subdirectories: {', '.join(missing_dirs)}")

    return SpecValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
