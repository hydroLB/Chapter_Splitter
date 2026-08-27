# Security Policy

## Reporting a Vulnerability

Do not disclose vulnerability details in public issues.

Use the repository's **Security → Report a vulnerability** form. Do not post exploit details,
proofs of concept, secrets, or affected user data in a public issue.

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

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |
| Earlier snapshots | No |

## Dependency and Secret Automation

- Dependency update automation is configured with Dependabot in `.github/dependabot.yml`.
- Dependabot is limited to direct Python dependencies, grouped monthly, with one open PR slot to keep update noise low while avoiding manual drift across dependency manifests.
- CI runs repository secret scanning with `gitleaks` on every push/PR.
- The repo-owned pre-push hook scans repository Git history with `gitleaks` before `make check`.
- Local secret scanning can be run manually with pre-commit:
  `pre-commit run --hook-stage manual gitleaks --all-files`.
- Threat model notes for critical local attack surfaces are documented in `docs/threat-model.md`.

## Local Security Workflow

Before opening a PR for security-sensitive changes, run:

```bash
make security
pre-commit run --hook-stage manual gitleaks --all-files
```

## Operational Hardening Guidance

Run the application with the least privileges required to access the target PDFs and output directory.
