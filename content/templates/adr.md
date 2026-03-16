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
