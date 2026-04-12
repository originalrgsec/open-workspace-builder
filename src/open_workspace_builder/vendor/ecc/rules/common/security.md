# Security Guidelines

## Mandatory Security Checks

Before ANY commit, verify these LLM-judgment items. Items enforced by pre-commit
hooks (secrets scanning, SAST, linting) are omitted; configure tooling-level
enforcement separately.

- [ ] All user inputs validated
- [ ] CSRF protection enabled
- [ ] Authentication/authorization verified
- [ ] Rate limiting on all endpoints
- [ ] Error messages don't leak sensitive data

## Secret Management

- ALWAYS use environment variables or a secret manager
- Validate that required secrets are present at startup
- Rotate any secrets that may have been exposed

## Security Response Protocol

If security issue found:
1. STOP immediately
2. Use **security-reviewer** agent
3. Fix CRITICAL issues before continuing
4. Rotate any exposed secrets
5. Review entire codebase for similar issues
