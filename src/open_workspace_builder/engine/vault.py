"""Vault structure creation and template deployment.

Reads templates from content/templates/ at runtime rather than embedding them.
"""

from __future__ import annotations

import textwrap
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_workspace_builder.config import VaultConfig

# Directories to create (relative to vault root)
VAULT_DIRS = [
    "_templates",
    "self",
    "research",
    "research/inbox",
    "research/processed",
    "research/archive",
    "research/mobile-inbox",
    "research/mobile-inbox/archive",
    "projects",
    "projects/Work",
    "projects/Personal",
    "projects/Open Source",
    "decisions",
    "code",
    "business",
]

# Structural files to create (relative to vault root)
VAULT_FILES = [
    "_index.md",
    "_bootstrap.md",
    "self/_index.md",
    "research/_index.md",
    "projects/_index.md",
    "projects/Work/_index.md",
    "projects/Personal/_index.md",
    "projects/Open Source/_index.md",
    "decisions/_index.md",
    "code/_index.md",
    "business/_index.md",
]


def _vault_index() -> str:
    return textwrap.dedent("""\
        # Vault Index

        This is the top-level map of content for the knowledge vault.

        ## Quick Start

        For Claude sessions: read [[_bootstrap]] first. It contains a compact project manifest
        with current phases and next actions, eliminating the need to traverse multiple index
        files before starting work.

        ## Areas

        - [[self/_index|Self]] — identity, voice, working style, tool inventory
        - [[research/_index|Research]] — learning, sources, and processed findings
        - [[projects/_index|Projects]] — active project state, decisions, specs, session logs
        - [[decisions/_index|Decisions]] — cross-project architectural and strategic decision log
        - [[code/_index|Code]] — cross-project code patterns, architecture, debug notes
        - [[business/_index|Business]] — strategy, finance, compliance, contacts
    """)


def _vault_bootstrap() -> str:
    return textwrap.dedent("""\
        ---
        type: bootstrap
        updated: YYYY-MM-DD
        purpose: Single-read session entry point. Load this first to get the full project map and current state.
        ---

        # Bootstrap

        This file provides a compact manifest of all projects, their current phase, and their
        top next action. It is designed to be the first file Claude reads in any new session,
        replacing the need to traverse multiple _index.md files before starting work.

        ## Context Files (read as needed)

        | File | Location | Purpose |
        |------|----------|---------|
        | Working Style | `Claude Context/working-style.md` | Behavioral instructions, output calibration, tool preferences |
        | Brand Voice | `Claude Context/brand-voice.md` | Writing voice, register tiers, vocabulary, anti-patterns |
        | About Me | `Claude Context/about-me.md` | Professional background, domain expertise, project details |

        ## Project Manifest

        <!-- Add your projects here. Use the format below. -->

        ### Category Name

        | Project | Phase | Next Action |
        |---------|-------|-------------|
        | **Project Name** | Phase | Next action description |

        ## Cross-Project Decision Index

        See [[decisions/_index]] for all architectural and strategic decisions across projects.

        ## Research Vault

        - **Inbox:** 0 items
        - **Mobile Inbox** (`research/mobile-inbox/`): 0 items
        - **Processed:** 0 notes

        ## Vault Structure Reference

        ```
        Obsidian/
        ├── _bootstrap.md          ← you are here
        ├── _index.md              ← vault area map
        ├── _templates/            ← note templates
        ├── self/                  ← identity context (stubs → workspace root)
        ├── research/              ← inbox → processed pipeline
        │   ├── archive/           ← originals
        │   ├── mobile-inbox/      ← mobile capture inbox
        │   └── processed/         ← cleaned notes with frontmatter
        ├── projects/              ← project tiers
        │   ├── Work/
        │   ├── Personal/
        │   └── Open Source/
        ├── code/                  ← cross-project code patterns
        ├── business/              ← strategy, finance
        └── decisions/             ← cross-project decision index
        ```
    """)


def _self_index() -> str:
    return textwrap.dedent("""\
        ---
        type: index
        area: self
        ---

        # Self

        Identity context files. These are stubs that point to the canonical source files
        in the workspace root (`Claude Context/`).

        ## Context Files

        - Working Style → `Claude Context/working-style.md`
        - Brand Voice → `Claude Context/brand-voice.md`
        - About Me → `Claude Context/about-me.md`

        ## Tool Inventory

        (Document your Claude tooling setup: MCP connectors, skills, agents, scheduled tasks.)
    """)


def _research_index() -> str:
    return textwrap.dedent("""\
        ---
        type: index
        area: research
        ---

        # Research

        ## Pipeline

        1. **Inbox** (`research/inbox/`) — raw notes, unprocessed
        2. **Mobile Inbox** (`research/mobile-inbox/`) — captures from mobile via iOS Shortcut
        3. **Processed** (`research/processed/`) — cleaned notes with frontmatter and project tags
        4. **Archive** (`research/archive/`) — originals preserved with date-prefixed filenames

        ## How to Use

        New research goes into `inbox/` (or `mobile-inbox/` if captured on mobile).
        Claude processes it during triage: reads, classifies, routes to the correct
        project folder or `processed/`, and archives the original.
    """)


def _projects_index() -> str:
    return textwrap.dedent("""\
        ---
        type: index
        area: projects
        ---

        # Projects

        ## Tiers

        - [[projects/Work/_index|Work]] — professional and client projects
        - [[projects/Personal/_index|Personal]] — personal and side projects
        - [[projects/Open Source/_index|Open Source]] — open-source contributions and maintained projects

        ## Creating a New Project

        1. Create a folder under the appropriate tier: `projects/<Tier>/<project-name>/`
        2. Copy `_templates/project-index.md` to `_index.md` in the new folder
        3. Create a `status.md` with frontmatter including `last-updated:`
        4. Add the project to `_bootstrap.md` under the correct tier table
        5. Add the project to this tier's `_index.md`
    """)


def _tier_index(tier_name: str) -> str:
    return textwrap.dedent(f"""\
        ---
        type: index
        area: projects
        tier: {tier_name}
        ---

        # {tier_name} Projects

        <!-- List projects in this tier. Link to each project's _index.md. -->
        <!-- Example: - [[projects/{tier_name}/project-name/_index|Project Name]] — one-line description -->
    """)


def _decisions_index() -> str:
    return textwrap.dedent("""\
        ---
        type: index
        area: decisions
        ---

        # Decisions Index

        Cross-project architectural and strategic decision log. Every accepted decision
        from any project's ADR or decision records should have an entry here for
        cross-project visibility.

        ## Format

        | ID | Date | Project | Decision | Status |
        |----|------|---------|----------|--------|
        <!-- DRN-001 | YYYY-MM-DD | project-name | Decision title | accepted/pending/superseded -->
    """)


def _code_index() -> str:
    return textwrap.dedent("""\
        ---
        type: index
        area: code
        ---

        # Code

        Cross-project code patterns, architecture notes, and policies.

        ## Contents

        - OSS health policy (scoring thresholds for dependency evaluation)
        - Allowed licenses list
        - Shared patterns and architecture notes
    """)


def _business_index() -> str:
    return textwrap.dedent("""\
        ---
        type: index
        area: business
        ---

        # Business

        Strategy, finance, compliance, and contacts for the business entity.
    """)


def _status_content(project_name: str, created_date: str) -> str:
    """Generate a status.md for a project from the status template."""
    return textwrap.dedent(f"""\
        ---
        type: status
        project: "{project_name}"
        created: "{created_date}"
        last-updated: "{created_date}"
        phase: planning
        ---

        # Status — {project_name}

        ## Current Phase

        Planning

        ## Recent Activity

        - Project created on {created_date}

        ## Blockers

        None

        ## Next Actions

        - [ ] Define project scope and goals
        - [ ] Create PRD from template
    """)


def _templates_readme() -> str:
    """Generate the _templates/readme.md file."""
    return textwrap.dedent("""\
        # _templates/

        These templates define the standard format for notes that Claude creates and
        depends on for session continuity and cross-session retrieval.

        ## Design Document Chain (PRD → ADR → Threat Model → SDR → Stories)

        The PRD defines what to build and why. The ADR defines how to build it
        architecturally and includes data flow diagrams with trust boundaries. The
        threat model applies STRIDE to the DFDs and scores risk using NIST SP 800-30.
        The SDR defines how to build it at code level and breaks work into stories.
        Each story has testable acceptance criteria for TDD.

        ## Available Templates

        See the individual template files in this directory for formats and usage.
    """)


_CONTENT_GENERATORS: dict[str, str | None] = {}


def vault_file_content(rel_path: str) -> str:
    """Return the content for a vault structural file based on its path."""
    generators = {
        "_index.md": _vault_index,
        "_bootstrap.md": _vault_bootstrap,
        "self/_index.md": _self_index,
        "research/_index.md": _research_index,
        "projects/_index.md": _projects_index,
        "projects/Work/_index.md": lambda: _tier_index("Work"),
        "projects/Personal/_index.md": lambda: _tier_index("Personal"),
        "projects/Open Source/_index.md": lambda: _tier_index("Open Source"),
        "decisions/_index.md": _decisions_index,
        "code/_index.md": _code_index,
        "business/_index.md": _business_index,
    }
    gen = generators.get(rel_path)
    if gen:
        return gen()
    return f"# {Path(rel_path).stem}\n"


def _load_templates(content_root: Path) -> dict[str, str]:
    """Load all template files from content/templates/ directory."""
    templates_dir = content_root / "content" / "templates"
    templates: dict[str, str] = {}
    if templates_dir.exists():
        for template_file in sorted(templates_dir.iterdir()):
            if template_file.is_file() and template_file.suffix == ".md":
                templates[template_file.name] = template_file.read_text(encoding="utf-8")
    return templates


class VaultBuilder:
    """Builds the Obsidian vault structure."""

    def __init__(
        self,
        vault_config: VaultConfig,
        content_root: Path,
        dry_run: bool = False,
    ) -> None:
        self._config = vault_config
        self._content_root = content_root
        self._dry_run = dry_run
        self.created_dirs: list[Path] = []
        self.created_files: list[Path] = []

    def build(self, target: Path) -> None:
        """Build the vault structure under target."""
        print("=== Building Obsidian Vault ===")
        parent = self._config.parent_dir
        vault_name = self._config.name
        vault_root = target / parent / vault_name

        for d in VAULT_DIRS:
            self._mkdir(vault_root / d)

        for f in VAULT_FILES:
            content = vault_file_content(f)
            self._write(vault_root / f, content)

        # Generate status.md per project tier
        today = date.today().isoformat()
        tiers = [d for d in VAULT_DIRS if d.startswith("projects/") and d.count("/") == 1]
        for tier_dir in tiers:
            tier_name = Path(tier_dir).name
            self._write(
                vault_root / tier_dir / "status.md",
                _status_content(tier_name, today),
            )

        # Ensure self/ has _index.md with context file stubs
        # (already in VAULT_FILES, but verify content points to context files)

        # Ensure research/mobile-inbox/archive/ exists with .gitkeep
        archive_dir = vault_root / "research" / "mobile-inbox" / "archive"
        self._mkdir(archive_dir)
        self._write(archive_dir / ".gitkeep", "")

        # Generate _templates/readme.md unconditionally
        self._write(vault_root / "_templates" / "readme.md", _templates_readme())

        if self._config.create_templates:
            print("  Installing vault templates...")
            templates = _load_templates(self._content_root)
            for name, content in sorted(templates.items()):
                self._write(vault_root / "_templates" / name, content)

    def _mkdir(self, path: Path) -> None:
        if self._dry_run:
            print(f"  [mkdir] {path}")
        else:
            path.mkdir(parents=True, exist_ok=True)
        self.created_dirs.append(path)

    def _write(self, path: Path, content: str) -> None:
        if self._dry_run:
            print(f"  [write] {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.created_files.append(path)
