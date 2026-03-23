#!/usr/bin/env python3
"""
open-workspace-builder — Bootstrap a Claude Code / Cowork workspace.

Creates the Obsidian knowledge vault structure, installs curated ECC (Everything
Claude Code) catalog items, installs custom Cowork skills with associated scripts,
deploys template context files, and generates a .claude/CLAUDE.md entry point.

Run inside a Claude Code or Cowork session to set up a fresh workspace, or run
standalone to generate the structure at a target path.

Usage:
    python build.py                          # builds in ./output/
    python build.py --target /path/to/dest   # builds at specified path
    python build.py --config config.yaml     # uses custom config
    python build.py --dry-run                # prints what would be created
"""

import argparse
import os
import shutil
import sys
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# Default configuration — edit config.yaml to override
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    # Where to write the built workspace (relative to script location if not absolute)
    "target": "output",

    # Vault settings
    "vault": {
        "name": "Obsidian",
        "parent_dir": "Claude Context",
        "create_bootstrap": True,
        "create_templates": True,
    },

    # ECC catalog — items to install from ecc-curated/
    "ecc": {
        "source_dir": "ecc-curated",
        "agents": [
            "architect",
            "build-error-resolver",
            "chief-of-staff",
            "code-reviewer",
            "database-reviewer",
            "doc-updater",
            "e2e-runner",
            "go-build-resolver",
            "go-reviewer",
            "harness-optimizer",
            "loop-operator",
            "planner",
            "python-reviewer",
            "refactor-cleaner",
            "security-reviewer",
            "tdd-guide",
        ],
        "commands": [
            "build-fix",
            "checkpoint",
            "code-review",
            "e2e",
            "eval",
            "go-build",
            "go-review",
            "go-test",
            "plan",
            "python-review",
            "refactor-clean",
            "tdd",
            "test-coverage",
            "update-docs",
            "verify",
        ],
        "rules": {
            "common": [
                "agents",
                "coding-style",
                "development-workflow",
                "git-workflow",
                "patterns",
                "performance",
                "security",
                "testing",
            ],
            "golang": [
                "coding-style",
                "patterns",
                "security",
                "testing",
            ],
            "python": [
                "coding-style",
                "patterns",
                "security",
                "testing",
            ],
        },
    },

    # Custom Cowork skills to install
    "skills": {
        "source_dir": "skills",
        "install": [
            "mobile-inbox-triage",
            "vault-audit",
            "oss-health-check",
        ],
    },

    # Context file templates to deploy
    "context_templates": {
        "deploy": True,
        "files": [
            "about-me.template.md",
            "brand-voice.template.md",
            "working-style.template.md",
        ],
    },

    # CLAUDE.md template
    "claude_md": {
        "deploy": True,
    },
}


# ---------------------------------------------------------------------------
# Vault structure definition
# ---------------------------------------------------------------------------

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

# Index and structural files to create (relative to vault root)
# Format: (path, content_function_name)
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


# ---------------------------------------------------------------------------
# Vault file content generators
# ---------------------------------------------------------------------------

def vault_file_content(rel_path: str) -> str:
    """Return the content for a vault structural file based on its path."""
    generators = {
        "_index.md": _vault_index,
        "_bootstrap.md": _vault_bootstrap,
        "self/_index.md": _self_index,
        "research/_index.md": _research_index,
        "projects/_index.md": _projects_index,
        "projects/Work/_index.md": _tier_index("Work"),
        "projects/Personal/_index.md": _tier_index("Personal"),
        "projects/Open Source/_index.md": _tier_index("Open Source"),
        "decisions/_index.md": _decisions_index,
        "code/_index.md": _code_index,
        "business/_index.md": _business_index,
    }
    gen = generators.get(rel_path)
    if gen:
        return gen() if callable(gen) else gen
    return f"# {Path(rel_path).stem}\n"


def _vault_index():
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


def _vault_bootstrap():
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


def _self_index():
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


def _research_index():
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


def _projects_index():
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


def _tier_index(tier_name):
    def _gen():
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
    return _gen


def _decisions_index():
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


def _code_index():
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


def _business_index():
    return textwrap.dedent("""\
        ---
        type: index
        area: business
        ---

        # Business

        Strategy, finance, compliance, and contacts for the business entity.
    """)


# ---------------------------------------------------------------------------
# Template file contents (the 18 Obsidian vault templates)
# ---------------------------------------------------------------------------

TEMPLATES = {}

TEMPLATES["adr.md"] = textwrap.dedent("""\
    ---
    type: adr
    version: 1.0
    status: draft
    project:
    created:
    updated:
    tags: []
    ---

    # ADR: Project/Feature Name

    ## Overview

    (One paragraph: what architectural approach this document defines, and what PRD it implements.)

    - PRD: [[projects/project-name/prd]]

    ## C4 Model

    ### Level 1: System Context

    (The system as a black box. What external actors interact with it? What are the high-level data flows?)

    **Actors:**
    - (actor) → (what they do with the system)

    **External Systems:**
    - (system) → (integration type, data exchanged)

    ### Level 2: Container Diagram

    | Container | Technology | Purpose | Communication |
    |-----------|-----------|---------|---------------|
    | | | | |

    ### Level 3: Component Diagram

    **Container: [name]**

    | Component | Responsibility | Interfaces |
    |-----------|---------------|------------|
    | | | |

    ### Level 4: Code (Deferred to SDR)

    (Detailed code structure covered in SDR. Placeholder for C4 completeness.)

    ## Data Flow Diagrams

    ### DFD-1: [flow name]

    **Trust Boundaries:**

    | Boundary | Inside | Outside | Enforcement |
    |----------|--------|---------|-------------|
    | | | | |

    **Data Flows:**

    | ID | Source | Destination | Data | Classification | Protocol | Crosses Boundary? |
    |----|--------|-------------|------|---------------|----------|-------------------|
    | DF-1 | | | | | | |

    **Data Stores:**

    | Store | Data Held | Classification | Access Control |
    |-------|-----------|---------------|----------------|
    | | | | |

    **Data Classification Levels:**
    - Public — no confidentiality requirement
    - Internal — business-sensitive
    - Confidential — regulated or high-impact (PII, credentials, financial)
    - Restricted — highest sensitivity (encryption keys, secrets)

    → Full threat analysis: [[projects/project-name/threat-model]]

    ## Key Architectural Decisions

    ### AD-1: Title

    - **Context:** (what drove this decision)
    - **Decision:** (what was chosen)
    - **Alternatives considered:** (what else was evaluated)
    - **Consequences:** (tradeoffs, risks, follow-on work)
    - **License check:** (verify against allowed licenses)
    - **OSS health check:** (record overall rating, date, flags)

    ## Technology Stack

    | Layer | Technology | Rationale |
    |-------|-----------|-----------|
    | Language | | |
    | Framework | | |
    | Database | | |
    | Hosting | | |
    | CI/CD | | |
    | Monitoring | | |

    ## Security Architecture

    ### Authentication
    ### Authorization
    ### Data Protection
    ### Threat Model
    → See [[projects/project-name/threat-model]]

    ## Performance and Scalability
    ## Reliability

    ## Open Questions

    -

    ## Links

    - PRD: [[projects/project-name/prd]]
    - SDR: [[projects/project-name/sdr]]
    - Threat Model: [[projects/project-name/threat-model]]
""")

TEMPLATES["budget-draw-schedule.md"] = textwrap.dedent("""\
    ---
    type: budget
    project:
    updated:
    tags: []
    ---

    # Budget & Draw Schedule

    ## Budget Summary

    | Category | Estimated | Actual | Variance | Notes |
    |----------|-----------|--------|----------|-------|
    | | | | | |
    | **Total** | | | | |

    ## Draw Schedule

    | Draw # | Milestone | Amount | Date Requested | Date Funded | Notes |
    |--------|-----------|--------|----------------|-------------|-------|
    | 1 | | | | | |

    ## Change Orders

    | CO # | Date | Description | Cost Impact | Approved By | Decision Ref |
    |------|------|-------------|-------------|-------------|--------------|
    | 1 | | | | | |
""")

TEMPLATES["decision-record.md"] = textwrap.dedent("""\
    ---
    type: decision
    number:
    status: accepted
    date:
    tags: []
    ---

    # DRN-000: Decision Title

    ## Context
    ## Options Considered

    1. **Option A** — (brief description, pros, cons)
    2. **Option B** — (brief description, pros, cons)

    ## Decision
    ## Consequences
""")

TEMPLATES["financing-tracker.md"] = textwrap.dedent("""\
    ---
    type: financing-tracker
    project:
    updated:
    tags: []
    ---

    # Financing Tracker

    ## Funding Sources

    ### Source Name

    - **Type:** (construction loan, mortgage, cash, etc.)
    - **Institution/Account:**
    - **Amount:**
    - **Terms:**
    - **Status:** exploring | applied | approved | funded | closed
    - **Decision ref:**
    - **Notes:**

    ## Cash Requirements Summary

    | Milestone | Amount Needed | Source | Status | Notes |
    |-----------|--------------|--------|--------|-------|
    | | | | | |

    ## Tax Implications
    ## Key Dates

    | Date | Event | Notes |
    |------|-------|-------|
    | | | |
""")

TEMPLATES["mobile-inbox.md"] = textwrap.dedent("""\
    ---
    type: mobile-inbox
    date:
    source: claude-mobile | voice-memo | manual
    projects: []
    tags: []
    processed: false
    ---

    # Mobile Note

    ## Context

    (What prompted this thought?)

    ## Content

    (The idea, insight, decision, question, or task.)

    ## Action Items

    -
""")

TEMPLATES["post-mortem.md"] = textwrap.dedent("""\
    ---
    type: post-mortem
    project:
    status: final
    date:
    tags: []
    ---

    # Post-Mortem: Project/Effort Name

    ## Summary
    ## Original Goals
    ## Timeline

    | Date | Event | Impact |
    |------|-------|--------|
    | | | |

    ## Architecture and Design Decisions

    ### Decision 1: Title

    - **What was chosen:**
    - **Why it seemed right:**
    - **What actually happened:**

    ## What Went Wrong

    ### Failure 1: Title

    - **What happened:**
    - **Direct cause:**
    - **Impact:**

    ## Root Cause Analysis
    ## What Worked
    ## Lessons Learned
    ## Recommendations
    ## Artifacts

    ## Links

    - Project: [[projects/project-name/_index]]
""")

TEMPLATES["prd.md"] = textwrap.dedent("""\
    ---
    type: prd
    version: 1.0
    status: draft
    project:
    created:
    updated:
    tags: []
    ---

    # PRD: Product/Feature Name

    ## Business Problem
    ## Target Customers

    ### Personas

    **Persona 1: Name/Role**
    - Context:
    - Pain points:
    - Goals:

    ## Use Cases

    ### UC-1: Title
    - **Actor:**
    - **Trigger:**
    - **Flow:**
    - **Outcome:**

    ## Goals

    1. **Goal:** → **Metric:** → **Target:**

    ## Non-Goals
    ## Assumptions
    ## Constraints
    ## Success Criteria
    ## Open Questions

    ## Links

    - ADR: [[projects/project-name/adr]]
    - SDR: [[projects/project-name/sdr]]
""")

TEMPLATES["project-index.md"] = textwrap.dedent("""\
    ---
    type: project
    status: active
    phase:
    created:
    updated:
    tags: []
    ---

    # Project Name

    ## Summary
    ## Goals
    ## Current Phase

    ## Key Links

    - Status: [[projects/project-name/status]]
    - Decisions: [[projects/project-name/decisions/]]
    - Specs: [[projects/project-name/specs/]]
    - Sessions: [[projects/project-name/sessions/]]
""")

TEMPLATES["readme.md"] = textwrap.dedent("""\
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

    - adr.md — Architecture Decision Record (C4, DFDs, tech stack)
    - budget-draw-schedule.md — Line-item budget with draw milestones
    - decision-record.md — Individual decision records
    - financing-tracker.md — Funding sources and cash requirements
    - mobile-inbox.md — Mobile capture note format
    - post-mortem.md — Project post-mortem
    - prd.md — Product Requirements Document
    - project-index.md — Project folder _index.md template
    - research-note.md — Processed research note
    - roadmap.md — Phased delivery roadmap
    - sdr.md — Software Design Record
    - selections-tracker.md — Materials/fixtures tracker
    - session-log.md — Claude session log
    - spec.md — Lightweight spec (deprecated in favor of full chain)
    - story.md — Implementation story with acceptance criteria
    - threat-model.md — STRIDE threat model with NIST scoring
    - vendor-contact-list.md — Vendor and contact tracker
""")

TEMPLATES["research-note.md"] = textwrap.dedent("""\
    ---
    type: research
    source:
    date:
    tags: []
    ---

    # Title

    ## Key Findings
    ## Relevance

    ## Source Details

    - URL/Reference:
    - Author:
    - Date accessed:
""")

TEMPLATES["roadmap.md"] = textwrap.dedent("""\
    ---
    type: roadmap
    status: draft
    project: {{project-name}}
    created: {{date}}
    updated: {{date}}
    tags: [roadmap, phased-delivery]
    ---

    # Roadmap: {{Project Title}}

    ## Purpose
    ## Guiding Principles

    ---

    ## Phase 1: POC

    **Timeline:**
    **Cost:**
    **Target:**

    ### Product State
    ### Technical Stack

    | Component | Phase 1 Implementation |
    |-----------|----------------------|
    | | |

    ### What You Build
    ### What You Do NOT Build
    ### Transition Trigger → Phase 2

    ---

    ## Phase 2: MVP

    **Timeline:**
    **Cost:**
    **Target:**

    ### Product State
    ### Technical Stack

    | Component | Phase 2 Implementation | Change from Phase 1 |
    |-----------|----------------------|---------------------|
    | | | |

    ### What Changes from Phase 1
    ### Transition Trigger → Phase 3

    ---

    ## Phase 3: Production

    **Timeline:**
    **Cost:**
    **Target:**

    ### Product State
    ### Technical Stack

    | Component | Phase 3 Implementation | Change from Phase 2 |
    |-----------|----------------------|---------------------|
    | | | |

    ### What Changes from Phase 2

    ---

    ## Cost Summary

    | Phase | One-Time | Monthly | Notes |
    |-------|----------|---------|-------|
    | Phase 1 | | | |
    | Phase 2 | | | |
    | Phase 3 | | | |
""")

TEMPLATES["sdr.md"] = textwrap.dedent("""\
    ---
    type: sdr
    version: 1.0
    status: draft
    project:
    created:
    updated:
    tags: []
    ---

    # SDR: Project/Feature Name

    ## Overview

    - PRD: [[projects/project-name/prd]]
    - ADR: [[projects/project-name/adr]]

    ## Repository Structure

    ```
    repo-name/
    ├── src/
    ├── tests/
    │   ├── unit/
    │   ├── integration/
    ├── config/
    ├── docs/
    ├── .claude/
    │   └── CLAUDE.md
    ```

    ## Module Design

    ### Module: [name]

    **Purpose:**
    **Location:**

    | File/Class | Responsibility |
    |-----------|---------------|
    | | |

    ## Data Schemas

    ### Schema: [name]

    ## API Contracts

    ### Endpoint: [METHOD /path]

    ## Configuration

    | Variable | Purpose | Default | Required |
    |----------|---------|---------|----------|
    | | | | |

    ## Error Handling Strategy
    ## Testing Strategy

    ## Story Breakdown

    1. [[projects/project-name/stories/S001-title]]

    ## Sprint Plan

    ### Sprint 1: [theme]
    - Stories: S001, S002, S003
    - Goal:

    ## Open Questions

    ## Links

    - PRD: [[projects/project-name/prd]]
    - ADR: [[projects/project-name/adr]]
""")

TEMPLATES["selections-tracker.md"] = textwrap.dedent("""\
    ---
    type: selections-tracker
    project:
    updated:
    tags: []
    ---

    # Selections Tracker

    ## Format

    ### Category — Item Name

    - **Product/Model:**
    - **Vendor/Supplier:**
    - **Cost:**
    - **Status:** not started | researching | selected | ordered | delivered | installed
    - **Decision ref:**
    - **Notes:**

    ## Selections

    <!-- Add entries grouped by category -->
""")

TEMPLATES["session-log.md"] = textwrap.dedent("""\
    ---
    type: session
    date:
    tool: cowork | code
    project:
    tags: []
    ---

    # Session: YYYY-MM-DD

    ## Context
    ## Work Done
    ## Decisions Made
    ## State Changes
    ## Open Items
""")

TEMPLATES["spec.md"] = textwrap.dedent("""\
    ---
    type: spec
    status: draft
    project:
    created:
    updated:
    tags: []
    ---

    # Spec: Feature/Module Name

    ## Purpose
    ## Inputs
    ## Outputs
    ## Behavior
    ## Constraints
    ## Acceptance Criteria

    - [ ]

    ## Dependencies
    ## Open Questions
""")

TEMPLATES["story.md"] = textwrap.dedent("""\
    ---
    type: story
    id:
    status: backlog
    project:
    sprint:
    priority:
    estimate:
    created:
    updated:
    tags: []
    ---

    # S000: Story Title

    ## User Story

    As a [persona/role], I want [capability] so that [business value].

    ## Context

    - SDR Module: [[projects/project-name/sdr#module-name]]
    - PRD Use Case: [[projects/project-name/prd#uc-1-title]]

    ## Acceptance Criteria

    ### AC-1: [descriptive name]
    - **Given:**
    - **When:**
    - **Then:**

    ## Edge Cases

    ### EC-1: [descriptive name]
    - **Given:**
    - **When:**
    - **Then:**

    ## Error Cases

    ### ERR-1: [descriptive name]
    - **Given:**
    - **When:**
    - **Then:**

    ## Technical Notes
    ## Dependencies

    - **Blocked by:**
    - **Blocks:**

    ## Test File Mapping

    | Criterion | Test File | Test Function |
    |-----------|-----------|--------------|
    | AC-1 | | |
""")

TEMPLATES["threat-model.md"] = textwrap.dedent("""\
    ---
    type: threat-model
    version: 1.0
    status: draft
    project:
    created:
    updated:
    review_date:
    tags: []
    ---

    # Threat Model: Project/Feature Name

    ## Overview

    - ADR: [[projects/project-name/adr]]
    - PRD: [[projects/project-name/prd]]

    ## Methodology

    STRIDE per element applied to ADR data flow diagrams. Risk scored using
    likelihood x impact matrix aligned with NIST SP 800-30 Rev. 1. Mitigations
    map to NIST SP 800-53 Rev. 5 control families.

    ## System Scope

    ### In Scope
    ### Out of Scope

    ### Data Classification Summary

    | Classification | Data Elements | Regulatory Applicability |
    |---------------|---------------|-------------------------|
    | | | |

    ## Trust Boundaries

    | ID | Boundary | Crosses | Enforcement |
    |----|----------|---------|-------------|
    | TB-1 | | | |

    ## STRIDE Analysis

    ### Element: [name from DFD]
    **Type:** (process | data store | data flow | external entity)
    **DFD Reference:**

    | STRIDE Category | Applicable? | Threat Description | Threat ID |
    |----------------|-------------|-------------------|-----------|
    | **S**poofing | | | T-001 |
    | **T**ampering | | | T-002 |
    | **R**epudiation | | | T-003 |
    | **I**nformation Disclosure | | | T-004 |
    | **D**enial of Service | | | T-005 |
    | **E**levation of Privilege | | | T-006 |

    ## Risk Assessment

    ### Likelihood Scale (NIST SP 800-30)

    | Level | Value | Description |
    |-------|-------|-------------|
    | Very High | 10 | Almost certain to initiate |
    | High | 8 | Highly likely |
    | Moderate | 5 | Somewhat likely |
    | Low | 2 | Unlikely |
    | Very Low | 0 | Highly unlikely |

    ### Impact Scale (NIST SP 800-30)

    | Level | Value | Description |
    |-------|-------|-------------|
    | Very High | 10 | Catastrophic |
    | High | 8 | Severe |
    | Moderate | 5 | Serious |
    | Low | 2 | Limited |
    | Very Low | 0 | Negligible |

    ### Threat Register

    | Threat ID | Threat | STRIDE | Element | Likelihood | Impact | Risk Level | Mitigation ID |
    |-----------|--------|--------|---------|-----------|--------|-----------|---------------|
    | T-001 | | | | | | | M-001 |

    ## Mitigations

    ### M-001: [title]

    - **Threat(s) addressed:**
    - **Description:**
    - **NIST 800-53 Control:**
    - **Implementation:**
    - **Status:** planned | implemented | verified
    - **Residual risk:**

    ## Residual Risk Summary

    | Threat ID | Original Risk | Mitigation | Residual Risk | Accepted? | Accepted By |
    |-----------|--------------|------------|--------------|-----------|-------------|
    | | | | | | |

    ## Review Schedule

    Next scheduled review: (date)

    ## NIST Control Mapping Summary

    | Control ID | Control Name | Family | Mitigations | Status |
    |-----------|-------------|--------|-------------|--------|
    | | | | | |

    ## Links

    - ADR: [[projects/project-name/adr]]
    - PRD: [[projects/project-name/prd]]
    - SDR: [[projects/project-name/sdr]]
""")

TEMPLATES["vendor-contact-list.md"] = textwrap.dedent("""\
    ---
    type: vendor-contacts
    project:
    updated:
    tags: []
    ---

    # Vendor & Contact List

    ## Format

    ### Role — Company/Person Name

    - **Contact:** (name, phone, email)
    - **Contract status:** no contract | negotiating | signed | complete
    - **Scope:**
    - **Notes:**

    ## Contacts

    <!-- Add entries grouped by role -->
""")


# ---------------------------------------------------------------------------
# Context file templates (sanitized versions of private files)
# ---------------------------------------------------------------------------

CONTEXT_TEMPLATES = {}

CONTEXT_TEMPLATES["about-me.template.md"] = textwrap.dedent("""\
    # About Me

    ## Identity & Current Role

    (Describe your current role and any business entities you operate.)

    ## Professional Background

    (Years of experience, career arc, key domains of expertise.)

    ### Career History

    (List positions in reverse chronological order with accomplishments.)

    ### Domain Expertise

    (List your areas of expertise with depth indicators.)

    ### Education & Credentials

    (Degrees, certifications, patents if applicable.)

    ## What I'm Building

    (Your business goals, target revenue, product direction.)

    ## What Claude Helps Me With

    (Types of work you need Claude to assist with.)

    ## What Good Looks Like

    | Work Type | What "Great" Means |
    |-----------|-------------------|
    | Design | |
    | Writing | |
    | Code | |
    | Systems | |

    ## Skill Self-Assessment

    | Domain | Level |
    |--------|-------|
    | (your domain) | (novice/mid/expert) |
""")

CONTEXT_TEMPLATES["brand-voice.template.md"] = textwrap.dedent("""\
    # Brand Voice

    ## How I Write

    (Describe your consistent writing traits: vocabulary preferences, sentence structure,
    how you handle evidence and frameworks, etc.)

    ## Registers I Write In

    | Context | Style |
    |--------|-------|
    | Executive / formal | |
    | Technical / analytical | |
    | Peer / casual | |
    | New contact | |

    ## What Sounds Wrong to Me

    (List AI-isms, patterns, and habits you want Claude to avoid in your voice.)

    ## Phrases and Patterns I Actually Use

    (Concrete examples from your own writing that Claude should emulate.)

    ## What "Sounds Like Me" Means in Practice

    (Describe the gestalt: what should a reader feel when reading output in your voice?)
""")

CONTEXT_TEMPLATES["working-style.template.md"] = textwrap.dedent("""\
    # Working Style

    ## How I Want Claude to Behave

    ### Questions First
    (Do you want Claude to ask before starting non-trivial tasks?)

    ### Output Length
    (What is your preference: concise, detailed, maximum information density?)

    ### Managing Context Window
    (Any token-efficiency preferences?)

    ## Tool and Connection Preferences

    ### Execution Method — Order of Preference
    (MCP > API > CLI > Browser? Customize to your setup.)

    ### Cost Awareness
    (Which tools are free vs. credit-consuming in your setup?)

    ## Default Output Formats by Project Type

    | Work Type | Format |
    |-----------|--------|
    | Documents | |
    | Data | |
    | Presentations | |
    | Code | local filesystem |

    ## Structural Preferences
    (Headers, tables, diagrams — when do you want them?)

    ## What I Don't Want
    (Anti-patterns: affirmations, recapping, preamble, etc.)

    ## Decision Authority

    ### Claude's Authority (Implementation)
    (What Claude can decide without asking.)

    ### Owner's Authority (Architectural / Business)
    (What requires your input.)

    ## Standing Preferences
    (Domains to treat as peer vs. domains to explain.)
""")


# ---------------------------------------------------------------------------
# CLAUDE.md template
# ---------------------------------------------------------------------------

CLAUDE_MD_TEMPLATE = textwrap.dedent("""\
    # CLAUDE.md

    <!-- This file tells Claude Code and Cowork how to behave in this workspace. -->
    <!-- Fill in the sections below and customize to your needs. -->

    (One-sentence description of who you are and what this workspace is for.)

    ## Required Context Files

    At the start of any non-trivial session, read the following files to load working context:

    1. **working-style.md** — Behavioral instructions, output calibration, tool preferences
    2. **brand-voice.md** — Writing voice, register tiers, vocabulary, anti-patterns
    3. **about-me.md** — Professional background, domain expertise, project details

    ## Obsidian Knowledge Vault

    An Obsidian vault at `Claude Context/Obsidian/` serves as persistent project memory.

    **Session startup:** Read `Claude Context/Obsidian/_bootstrap.md` first. It contains a
    compact manifest of all projects with current phases and next actions.

    **Project work:** After bootstrap, read the specific project's `_index.md` and `status.md`.
    At session end, update `status.md` and write a session log to `sessions/`.

    **Research lookup:** Processed research notes have a `projects:` frontmatter field for
    targeted retrieval.

    **Decision checks:** Read `Claude Context/Obsidian/decisions/_index.md` before recommending
    technology or architecture choices.

    The vault structure:

    - `_bootstrap.md` — session entry point
    - `self/` — identity context
    - `research/` — inbox → processed pipeline
    - `projects/` — one subfolder per project with status, decisions, specs, session logs
    - `decisions/` — cross-project decision index
    - `code/` — cross-project code patterns
    - `business/` — strategy, finance, compliance
    - `_templates/` — note templates

    If the Obsidian MCP server is available, use it. Otherwise, read/write vault files
    directly from the filesystem.
""")


# ---------------------------------------------------------------------------
# Builder logic
# ---------------------------------------------------------------------------

class WorkspaceBuilder:
    """Builds a Claude workspace from configuration."""

    def __init__(self, config: dict, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run
        self.created_files = []
        self.created_dirs = []
        self.copied_files = []
        self.script_dir = Path(__file__).parent.resolve()

    def build(self, target: Path):
        """Run the full build pipeline."""
        target = target.resolve()
        print(f"Building workspace at: {target}")
        print()

        self._build_vault(target)
        self._install_ecc(target)
        self._install_skills(target)
        self._deploy_context_templates(target)
        self._deploy_claude_md(target)

        print()
        print(f"Build complete.")
        print(f"  Directories created: {len(self.created_dirs)}")
        print(f"  Files created:       {len(self.created_files)}")
        print(f"  Files copied:        {len(self.copied_files)}")

    def _mkdir(self, path: Path):
        if self.dry_run:
            print(f"  [mkdir] {path}")
        else:
            path.mkdir(parents=True, exist_ok=True)
        self.created_dirs.append(path)

    def _write(self, path: Path, content: str):
        if self.dry_run:
            print(f"  [write] {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.created_files.append(path)

    def _copy(self, src: Path, dst: Path):
        if self.dry_run:
            print(f"  [copy]  {src.name} → {dst}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        self.copied_files.append(dst)

    def _copy_tree(self, src: Path, dst: Path):
        """Copy a directory tree, creating destination dirs as needed."""
        if not src.exists():
            print(f"  [warn]  Source not found: {src}")
            return
        for item in sorted(src.rglob("*")):
            rel = item.relative_to(src)
            dest_path = dst / rel
            if item.is_dir():
                self._mkdir(dest_path)
            elif item.is_file():
                self._copy(item, dest_path)

    # --- Vault ---

    def _build_vault(self, target: Path):
        print("=== Building Obsidian Vault ===")
        vault_cfg = self.config.get("vault", {})
        parent = vault_cfg.get("parent_dir", "Claude Context")
        vault_name = vault_cfg.get("name", "Obsidian")
        vault_root = target / parent / vault_name

        # Create directory structure
        for d in VAULT_DIRS:
            self._mkdir(vault_root / d)

        # Create structural files
        for f in VAULT_FILES:
            content = vault_file_content(f)
            self._write(vault_root / f, content)

        # Create templates
        if vault_cfg.get("create_templates", True):
            print("  Installing vault templates...")
            for name, content in sorted(TEMPLATES.items()):
                self._write(vault_root / "_templates" / name, content)

    # --- ECC ---

    def _install_ecc(self, target: Path):
        print("=== Installing ECC Catalog (Curated) ===")
        ecc_cfg = self.config.get("ecc", {})
        source_dir_name = ecc_cfg.get("source_dir", "ecc-curated")
        source = self.script_dir / source_dir_name

        if not source.exists():
            print(f"  [warn]  ECC source not found at {source}")
            print(f"          Copy your ecc-curated/ folder into {self.script_dir}")
            return

        # Agents
        agents_src = source / "agents"
        agents_dst = target / ".claude" / "agents"
        for agent_name in ecc_cfg.get("agents", []):
            src_file = agents_src / f"{agent_name}.md"
            if src_file.exists():
                self._copy(src_file, agents_dst / f"{agent_name}.md")
            else:
                print(f"  [warn]  Agent not found: {agent_name}")

        # Commands
        commands_src = source / "commands"
        commands_dst = target / ".claude" / "commands"
        for cmd_name in ecc_cfg.get("commands", []):
            src_file = commands_src / f"{cmd_name}.md"
            if src_file.exists():
                self._copy(src_file, commands_dst / f"{cmd_name}.md")
            else:
                print(f"  [warn]  Command not found: {cmd_name}")

        # Rules
        rules_src = source / "rules"
        rules_dst = target / ".claude" / "rules"
        rules_cfg = ecc_cfg.get("rules", {})
        for category, filenames in rules_cfg.items():
            for fname in filenames:
                src_file = rules_src / category / f"{fname}.md"
                if src_file.exists():
                    self._copy(src_file, rules_dst / category / f"{fname}.md")
                else:
                    print(f"  [warn]  Rule not found: {category}/{fname}")

    # --- Skills ---

    def _install_skills(self, target: Path):
        print("=== Installing Custom Skills ===")
        skills_cfg = self.config.get("skills", {})
        source_dir_name = skills_cfg.get("source_dir", "skills")
        source = self.script_dir / source_dir_name

        if not source.exists():
            print(f"  [warn]  Skills source not found at {source}")
            print(f"          Copy your skills/ folder into {self.script_dir}")
            return

        skills_dst = target / ".skills" / "skills"

        for skill_name in skills_cfg.get("install", []):
            skill_src = source / skill_name
            if skill_src.exists():
                print(f"  Installing skill: {skill_name}")
                self._copy_tree(skill_src, skills_dst / skill_name)
            else:
                print(f"  [warn]  Skill not found: {skill_name}")

    # --- Context Templates ---

    def _deploy_context_templates(self, target: Path):
        ctx_cfg = self.config.get("context_templates", {})
        if not ctx_cfg.get("deploy", True):
            return

        print("=== Deploying Context File Templates ===")
        context_dir = target / "Claude Context"

        for filename in ctx_cfg.get("files", []):
            # Write template version
            content = CONTEXT_TEMPLATES.get(filename, f"# {filename}\n\n(Fill in your details.)\n")
            # Strip .template from the deployed filename
            deployed_name = filename.replace(".template", "")
            self._write(context_dir / deployed_name, content)

    # --- CLAUDE.md ---

    def _deploy_claude_md(self, target: Path):
        claude_cfg = self.config.get("claude_md", {})
        if not claude_cfg.get("deploy", True):
            return

        print("=== Deploying CLAUDE.md Template ===")
        self._write(target / ".claude" / "CLAUDE.md", CLAUDE_MD_TEMPLATE)


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_config(config_path: str | None) -> dict:
    """Load config from YAML file, falling back to defaults."""
    config = dict(DEFAULT_CONFIG)

    if config_path and os.path.exists(config_path):
        try:
            import yaml
            with open(config_path) as f:
                user_config = yaml.safe_load(f) or {}
            # Shallow merge top-level keys
            for key, value in user_config.items():
                if isinstance(value, dict) and isinstance(config.get(key), dict):
                    config[key] = {**config[key], **value}
                else:
                    config[key] = value
            print(f"Loaded config from: {config_path}")
        except ImportError:
            print("Warning: PyYAML not installed. Using default config.")
            print("  Install with: pip install pyyaml")
        except Exception as e:
            print(f"Warning: Could not load config file: {e}")
            print("  Using default config.")

    return config


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Build a Claude Code / Cowork workspace with Obsidian vault, "
                    "ECC catalog, custom skills, and context templates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python build.py                          # build to ./output/
              python build.py --target ~/my-workspace  # build at specific path
              python build.py --dry-run                # preview without writing
              python build.py --config my-config.yaml  # use custom config
        """),
    )
    parser.add_argument(
        "--target", "-t",
        default=None,
        help="Target directory for the built workspace (default: ./output/)",
    )
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="Path to YAML config file (default: uses built-in config)",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Print what would be created without writing anything",
    )

    args = parser.parse_args()
    config = load_config(args.config)

    target = Path(args.target) if args.target else Path(config.get("target", "output"))

    builder = WorkspaceBuilder(config, dry_run=args.dry_run)
    builder.build(target)


if __name__ == "__main__":
    main()
