# Runbook: Split Failure

## Trigger

- `chapter-splitter split ...` exits non-zero
- GUI export fails with split/write/validation error

## Triage

1. Confirm required files exist:
```bash
ls -la /path/to/book.pdf
ls -la /path/to/chapters.toml
```
2. Re-run split with explicit command:
```bash
chapter-splitter split --pdf /path/to/book.pdf --chapters /path/to/chapters.toml
```
3. If collision suspected, test with override policy:
```bash
chapter-splitter split --pdf /path/to/book.pdf --chapters /path/to/chapters.toml --collision-policy suffix
```
4. Validate repo health and regressions:
```bash
make test
make security
```

## Common Causes and Fixes

- invalid chapter ranges/titles:
  fix `chapters.toml` and re-run
- output collisions:
  use `--collision-policy suffix` or clean output directory
- PDF parser/read error:
  verify PDF opens in a viewer and is not corrupted
- timeout/cancellation:
  increase IO timeout in config override for long documents

## Recovery

1. Export into a clean directory:
```bash
mkdir -p /tmp/chapter_splitter_recovery_out
chapter-splitter split --pdf /path/to/book.pdf --chapters /path/to/chapters.toml --output-dir /tmp/chapter_splitter_recovery_out --collision-policy suffix
```
2. Validate generated outputs before replacing prior artifacts.

## Verification

Expected:
- command exits `0`
- target output directory contains chapter PDFs
- no error dialog/log event with `*_error`
