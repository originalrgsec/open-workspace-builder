# Project Documentation

Design documents for the Open Workspace Builder.

| Document | Description |
|----------|-------------|
| [PRD](./prd.md) | Product Requirements Document — personas, use cases, goals, constraints |
| [ADR](./adr.md) | Architecture Decision Record — C4 model, data flow diagrams, key decisions, technology stack |
| [SDR](./sdr.md) | Software Design Record — module design, data schemas, sprint plan, testing strategy |
| [Threat Model](./threat-model.md) | STRIDE analysis, risk assessment, mitigations, NIST 800-53 control mapping |
| [How-To: First Run](./howto-first-run.md) | Step-by-step guide for running OWB against an existing vault |

## Security Capabilities

OWB provides multi-layer security scanning for workspace content and dependencies:

- **Content scanner:** Three-layer analysis (structural, pattern, semantic) for prompt injection and malicious instructions
- **SCA (Software Composition Analysis):** pip-audit for known CVEs, GuardDog for heuristic malware detection, pre-install gate via ECC rule
- **SAST (Static Application Security Testing):** Semgrep integration for source code analysis
- **CVE suppression monitoring:** Automated weekly check for upstream fixes on suppressed vulnerabilities
- **Trust tier scoring:** SCA/SAST findings affect trust tier assignment in the evaluator pipeline
