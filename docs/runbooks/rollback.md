# Runbook: Rollback

## Trigger

- newly merged change causes runtime regression, build break, or incident
- urgent restore to known-good behavior is required

## Preconditions

- identify target rollback commit or last known-good tag
- ensure no destructive commands are run without explicit operator approval

## Triage Inputs

1. Identify current commit and branch:
```bash
git rev-parse --abbrev-ref HEAD
git rev-parse --short HEAD
```
2. Locate candidate known-good references:
```bash
git tag --sort=-creatordate | head -n 10
git log --oneline --decorate -n 20
```

## Rollback Procedure (Safe, Non-Destructive)

1. Create rollback branch from current main tip:
```bash
git checkout main
git pull --ff-only
git checkout -b codex/rollback-<incident-id>
```
2. Revert offending commits (newest first if multiple):
```bash
git revert <bad-commit-sha>
```
3. Validate rollback candidate:
```bash
make check
```
4. Open rollback PR with incident context and explicit revert list.

## Fast Runtime Mitigation (Optional)

If incident is config-driven, apply temporary safe overrides while rollback PR is reviewed:

- disable risky override config
- set conservative collision policy and timeout values
- switch to last known-good workflow command set

## Verification

Expected:
- rollback PR is green on CI
- reproduced incident no longer occurs on rollback branch
- release/build artifacts regenerate successfully if packaging was impacted

## Post-Rollback Follow-Up

- document root cause
- add regression test that fails on the reverted behavior
- schedule forward fix as a separate small PR
