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
