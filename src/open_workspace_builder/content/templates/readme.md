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
