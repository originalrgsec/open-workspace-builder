# Glossary

**Golden Path**
:   A pre-configured, opinionated setup path that gets developers to a productive state quickly. In OWB, `owb init` is the golden path — it generates a fully configured workspace from a single command.

**IDP (Internal Developer Platform)**
:   A self-service layer that standardizes how developers set up and operate their environments. OWB functions as an IDP for AI coding assistants. See [IDP for AI Coding](../concepts/idp-for-ai-coding.md).

**Policy as Code**
:   The practice of expressing security and operational rules as machine-readable definitions that are enforced automatically. OWB uses policy-as-code for inline rules, scanner patterns, pre-commit hooks, and drift detection. See [Policy as Code](../concepts/policy-as-code.md).

**SBOM (Software Bill of Materials)**
:   A structured inventory of all components (dependencies, skills, agents, MCP servers) in a workspace. OWB's SBOM capability (planned, S107) will generate machine-readable inventories for audit and compliance.

**SSCA (Software Supply Chain Assurance)**
:   The set of practices that protect the integrity of tools, dependencies, and content entering a development environment. OWB applies SSCA to the AI workspace through package quarantine, pre-install SCA gates, secrets scanning, and content provenance tracking. See [Supply Chain Security](../concepts/supply-chain-security.md).

**Drift**
:   The divergence between a workspace's current state and its reference configuration. `owb diff` detects drift; `owb migrate` resolves it. `owb security drift` specifically detects changes to directive files that could indicate tampering.

**Pattern Registry**
:   OWB's extensible catalog of known attack signatures used by the security scanner. Ships with 58 patterns across 12 categories. Users can add custom patterns.

**Trust Tier**
:   A classification (T0 through T3) assigned to content sources based on their security scan history and reputation. Higher tiers receive less scrutiny; lower tiers require full scanning on every update.

**Quarantine**
:   A mandatory waiting period (7 days by default) between a package's publication on PyPI and its eligibility for installation. Protects against supply chain attacks that rely on fast adoption of compromised releases.
