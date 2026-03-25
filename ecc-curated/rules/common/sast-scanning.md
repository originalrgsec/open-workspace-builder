# SAST Scanning

## When to Run SAST

Run `owb security sast <path>` in these situations:

- Before opening a pull request or merging a feature branch
- When the user requests a security review of their code
- Before tagging a release
- After significant refactoring that touches security-sensitive code (auth, crypto, user input handling, subprocess calls)

## Interpreting Results

- **ERROR**: Likely real vulnerability. Must be fixed or explicitly acknowledged before proceeding.
- **WARNING**: Potential issue. Review and fix if applicable, or add `# nosemgrep` with a justification comment if it is a false positive.
- **INFO**: Informational. No action required unless the user is doing a thorough security review.

## False Positives

If a finding is a false positive, suppress it inline:

```python
result = some_function()  # nosemgrep: rule-id-here — reason for suppression
```

Do not add blanket suppressions. Each suppression must have a specific rule ID and reason.
