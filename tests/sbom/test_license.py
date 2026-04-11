"""OWB-S107b — Tests for SBOM license detection.

Covers the four-step detection priority order (frontmatter → sibling
LICENSE → parent walk → NOASSERTION), SPDX identification by distinctive
phrase fingerprinting, and the allowed-licenses cross-reference loaded from
the bundled `data/allowed_licenses.toml`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from open_workspace_builder.sbom.license import (
    LicenseSource,
    detect_license,
    identify_spdx,
    load_allowed_licenses,
)


# ---------------------------------------------------------------------------
# allowed_licenses.toml loader
# ---------------------------------------------------------------------------


class TestLoadAllowedLicenses:
    def test_loads_bundled_toml(self) -> None:
        policy = load_allowed_licenses()
        assert policy.policy_version == 1
        assert "MIT" in policy.allowed
        assert "Apache-2.0" in policy.allowed
        assert "MPL-2.0" in policy.conditional
        assert "GPL-3.0" in policy.disallowed

    def test_is_allowed_permissive(self) -> None:
        policy = load_allowed_licenses()
        assert policy.is_allowed("MIT") is True
        assert policy.is_allowed("Apache-2.0") is True
        assert policy.is_allowed("BSD-3-Clause") is True

    def test_is_allowed_conditional_returns_true(self) -> None:
        # Conditional licenses are allowed by default — the condition is for
        # human awareness, not blocking.
        policy = load_allowed_licenses()
        assert policy.is_allowed("MPL-2.0") is True

    def test_is_allowed_disallowed_returns_false(self) -> None:
        policy = load_allowed_licenses()
        assert policy.is_allowed("GPL-3.0") is False
        assert policy.is_allowed("AGPL-3.0") is False
        assert policy.is_allowed("LGPL-2.1") is False

    def test_is_allowed_unknown_returns_false(self) -> None:
        # Unknown licenses are not allowed by default. Add to the toml first.
        policy = load_allowed_licenses()
        assert policy.is_allowed("Made-Up-License-1.0") is False

    def test_classification_string(self) -> None:
        policy = load_allowed_licenses()
        assert policy.classify("MIT") == "allowed"
        assert policy.classify("MPL-2.0") == "conditional"
        assert policy.classify("GPL-3.0") == "disallowed"
        assert policy.classify("Made-Up-License-1.0") == "unknown"


# ---------------------------------------------------------------------------
# SPDX identification by distinctive phrase fingerprinting
# ---------------------------------------------------------------------------


# Canonical phrases per license. The fingerprinter must identify each license
# even when copyright year and holder vary, when whitespace is reflowed, and
# when the file is wrapped at different column widths.

MIT_TEXT = """\
MIT License

Copyright (c) 2026 Some Person

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software.
"""

APACHE_TEXT = """\
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION
"""

BSD3_TEXT = """\
BSD 3-Clause License

Copyright (c) 2026, The Project Authors.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

  Neither the name of the copyright holder nor the names of its
  contributors may be used to endorse or promote products derived from
  this software without specific prior written permission.
"""

BSD2_TEXT = """\
BSD 2-Clause License

Copyright (c) 2026, Author.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice.
2. Redistributions in binary form must reproduce the above copyright notice.
"""

GPL3_TEXT = """\
                    GNU GENERAL PUBLIC LICENSE
                       Version 3, 29 June 2007

 Copyright (C) 2007 Free Software Foundation, Inc.

 The GNU General Public License is a free, copyleft license for software.
"""

ISC_TEXT = """\
ISC License

Copyright (c) 2026, The Authors

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.
"""

UNLICENSE_TEXT = """\
This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or distribute
this software, either in source code form or as a compiled binary.

For more information, please refer to <https://unlicense.org>
"""


class TestIdentifySpdx:
    def test_mit(self) -> None:
        assert identify_spdx(MIT_TEXT) == "MIT"

    def test_apache_2_0(self) -> None:
        assert identify_spdx(APACHE_TEXT) == "Apache-2.0"

    def test_bsd_3_clause(self) -> None:
        assert identify_spdx(BSD3_TEXT) == "BSD-3-Clause"

    def test_bsd_2_clause(self) -> None:
        assert identify_spdx(BSD2_TEXT) == "BSD-2-Clause"

    def test_gpl_3_0(self) -> None:
        assert identify_spdx(GPL3_TEXT) == "GPL-3.0"

    def test_isc(self) -> None:
        assert identify_spdx(ISC_TEXT) == "ISC"

    def test_unlicense(self) -> None:
        assert identify_spdx(UNLICENSE_TEXT) == "Unlicense"

    def test_unknown_returns_none(self) -> None:
        assert identify_spdx("This is not a license file at all.") is None

    def test_empty_returns_none(self) -> None:
        assert identify_spdx("") is None

    def test_whitespace_insensitive(self) -> None:
        # Reflow MIT to a single line — fingerprint must still match.
        compressed = " ".join(MIT_TEXT.split())
        assert identify_spdx(compressed) == "MIT"

    def test_case_insensitive(self) -> None:
        assert identify_spdx(MIT_TEXT.lower()) == "MIT"

    def test_copyright_year_variation(self) -> None:
        # Identification must not depend on the copyright year.
        text = MIT_TEXT.replace("2026", "1999")
        assert identify_spdx(text) == "MIT"

    def test_copyright_holder_variation(self) -> None:
        text = MIT_TEXT.replace("Some Person", "Some Other Entity, LLC")
        assert identify_spdx(text) == "MIT"


# ---------------------------------------------------------------------------
# detect_license — full priority chain
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace_with_license(tmp_path: Path) -> Path:
    """A workspace with a root LICENSE file (MIT) and one nested skill dir."""
    (tmp_path / "LICENSE").write_text(MIT_TEXT, encoding="utf-8")
    skill_dir = tmp_path / ".claude" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\n---\nbody\n", encoding="utf-8")
    return tmp_path


class TestDetectLicense:
    def test_explicit_frontmatter_field_wins(self, workspace_with_license: Path) -> None:
        skill_path = workspace_with_license / ".claude" / "skills" / "demo" / "SKILL.md"
        entry = detect_license(
            component_path=skill_path,
            workspace=workspace_with_license,
            frontmatter={"license": "Apache-2.0"},
        )
        assert entry.spdx_id == "Apache-2.0"
        assert entry.source == LicenseSource.FRONTMATTER
        assert entry.allowed is True

    def test_sibling_license_file(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / ".claude" / "skills" / "demo"
        skill_dir.mkdir(parents=True)
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text("---\nname: demo\n---\nbody\n", encoding="utf-8")
        (skill_dir / "LICENSE").write_text(BSD3_TEXT, encoding="utf-8")

        entry = detect_license(
            component_path=skill_path,
            workspace=tmp_path,
            frontmatter={},
        )
        assert entry.spdx_id == "BSD-3-Clause"
        assert entry.source == LicenseSource.SIBLING_FILE
        assert entry.allowed is True

    def test_parent_directory_walk_finds_license(self, workspace_with_license: Path) -> None:
        skill_path = workspace_with_license / ".claude" / "skills" / "demo" / "SKILL.md"
        entry = detect_license(
            component_path=skill_path,
            workspace=workspace_with_license,
            frontmatter={},
        )
        assert entry.spdx_id == "MIT"
        assert entry.source in (LicenseSource.PARENT_FILE, LicenseSource.WORKSPACE_ROOT)
        assert entry.allowed is True

    def test_disallowed_license_marked_not_allowed(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / ".claude" / "skills" / "demo"
        skill_dir.mkdir(parents=True)
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text("---\nname: demo\n---\nbody\n", encoding="utf-8")
        (skill_dir / "LICENSE").write_text(GPL3_TEXT, encoding="utf-8")

        entry = detect_license(
            component_path=skill_path,
            workspace=tmp_path,
            frontmatter={},
        )
        assert entry.spdx_id == "GPL-3.0"
        assert entry.allowed is False

    def test_no_license_anywhere_returns_noassertion(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / ".claude" / "skills" / "demo"
        skill_dir.mkdir(parents=True)
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text("---\nname: demo\n---\nbody\n", encoding="utf-8")

        entry = detect_license(
            component_path=skill_path,
            workspace=tmp_path,
            frontmatter={},
        )
        assert entry.spdx_id is None
        assert entry.source == LicenseSource.NOASSERTION
        assert entry.allowed is False

    def test_frontmatter_unknown_id_marked_not_allowed(self, workspace_with_license: Path) -> None:
        skill_path = workspace_with_license / ".claude" / "skills" / "demo" / "SKILL.md"
        entry = detect_license(
            component_path=skill_path,
            workspace=workspace_with_license,
            frontmatter={"license": "Made-Up-License-1.0"},
        )
        assert entry.spdx_id == "Made-Up-License-1.0"
        assert entry.allowed is False

    def test_unrecognized_license_file_falls_to_custom(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / ".claude" / "skills" / "demo"
        skill_dir.mkdir(parents=True)
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text("---\nname: demo\n---\nbody\n", encoding="utf-8")
        (skill_dir / "LICENSE").write_text(
            "This is some custom license text nobody recognizes.", encoding="utf-8"
        )

        entry = detect_license(
            component_path=skill_path,
            workspace=tmp_path,
            frontmatter={},
        )
        # File found but couldn't be SPDX-matched.
        assert entry.spdx_id is None
        assert entry.source == LicenseSource.SIBLING_FILE
        assert entry.allowed is False
        assert entry.custom_name is not None

    def test_license_md_extension_recognized(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / ".claude" / "skills" / "demo"
        skill_dir.mkdir(parents=True)
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text("---\nname: demo\n---\nbody\n", encoding="utf-8")
        (skill_dir / "LICENSE.md").write_text(ISC_TEXT, encoding="utf-8")

        entry = detect_license(
            component_path=skill_path,
            workspace=tmp_path,
            frontmatter={},
        )
        assert entry.spdx_id == "ISC"

    def test_copying_filename_recognized(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / ".claude" / "skills" / "demo"
        skill_dir.mkdir(parents=True)
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text("---\nname: demo\n---\nbody\n", encoding="utf-8")
        (skill_dir / "COPYING").write_text(GPL3_TEXT, encoding="utf-8")

        entry = detect_license(
            component_path=skill_path,
            workspace=tmp_path,
            frontmatter={},
        )
        assert entry.spdx_id == "GPL-3.0"
