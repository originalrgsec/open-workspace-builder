# Policy Enforcement Rules

These rules are extracted from the project's governance documents. When any rule
here conflicts with another rule file, this file takes precedence. Full policy
documents are available in the project's vault or documentation directory.

## Design Artifacts (product-development-workflow)

- [ ] PRD, ADR, SDR, and threat model exist before implementation begins
- [ ] Cross-project decisions are indexed in the decisions log before adoption
- [ ] Every retrospective links to at least one concrete deliverable (story, policy change, or process update)

## Sprint Completion (development-process)

- [ ] All stories pass workflow-level acceptance criteria
- [ ] Project docs (PRD, ADR, SDR, threat model) updated to reflect sprint changes
- [ ] CHANGELOG.md updated in Keep a Changelog format
- [ ] Release manifest written to `docs/releases/`
- [ ] Release tagged after final PR merges

## Integration Verification (integration-verification-policy)

- [ ] Acceptance criteria describe end-to-end operator workflows, not isolated module behavior
- [ ] Pipeline smoke test run before marking sprint complete — primary commands executed, output verified at every stage
- [ ] Configuration errors fail loudly with actionable messages; silent empty results on misconfiguration are bugs
- [ ] CLI contract test exists and passes: every documented command responds to `--help`
- [ ] Factory/builder tests verify constructed objects work for all intended use cases, not just construction success

## Dependency Health (oss-health-policy)

- [ ] License check passes before health evaluation (disallowed license = stop)
- [ ] Health evaluation completed before adopting any new dependency
- [ ] Any single Red in Maintenance Activity or Security Posture = reject
- [ ] Any single Red in other categories = document justification if adopting
- [ ] Two or more Yellows = document risk assessment
- [ ] Exceptions recorded as decision records with mitigation strategy and 12-month review date

## License Compliance (allowed-licenses)

- [ ] Dependency license checked before adding (Allowed = proceed; Conditional = verify condition; Disallowed or unlisted = find alternative)
- [ ] Transitive dependency license audit run periodically
- [ ] No GPL, AGPL, LGPL, SSPL, Commons Clause, or CC-NC/CC-SA licensed code without a documented exception

## When to Consult Full Policy Documents

| Activity | Policy to Read |
|----------|---------------|
| Planning a feature or sprint | product-development-workflow, development-process |
| Writing acceptance criteria | integration-verification-policy |
| Completing a sprint | development-process (completion checklist) |
| Reviewing code | integration-verification-policy (wiring checks) |
| Adding a dependency | oss-health-policy, allowed-licenses |
| Writing tests | integration-verification-policy (workflow-level AC) |
| Release preparation | development-process (release notes, versioning) |
| Installing packages or dependencies | supply-chain-protection (quarantine, SCA) |
| Configuring pre-commit hooks | supply-chain-protection (secrets scanning) |
| Starting a session on any project | supply-chain-protection (pin advancement check) |
