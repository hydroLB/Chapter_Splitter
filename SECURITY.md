# Security Policy

## Reporting a Vulnerability

Do not open public issues for potential vulnerabilities.

Use one of the following private reporting paths:

1. GitHub Security Advisory (preferred): open a private advisory in this repository.
2. Maintainer email: include `SECURITY` in the subject and provide a private proof of concept.

Include:

- affected version or commit SHA
- environment details (OS, Python version)
- reproduction steps
- impact assessment and attack preconditions
- suggested remediation (if available)

### Response Targets

- acknowledgment: within 2 business days
- triage status update: within 5 business days
- remediation plan for confirmed issues: within 10 business days

## Supported Versions

Security fixes are provided for:

- latest tagged release: full support
- previous tagged release: best-effort critical fixes for 30 days after the next release

Development branches and untagged snapshots are not guaranteed for security patch support.

## Dependency and Secret Automation

- Dependency update automation is configured with Dependabot in `.github/dependabot.yml`.
- CI runs repository secret scanning with `gitleaks` on every push/PR.
- Local secret scanning can be run manually with pre-commit:
  `pre-commit run gitleaks --all-files`.
- Threat model notes for critical local attack surfaces are documented in `docs/threat-model.md`.

## Local Security Workflow

Before opening a PR for security-sensitive changes, run:

```bash
make security
pre-commit run gitleaks --all-files
```

## Operational Hardening Guidance

Run the application with the least privileges required to access the target PDFs and output directory.
