# Runbook: Packaging Failure

## Trigger

- `make build` or `python -m build` fails
- CI build artifact step fails on PR

## Triage

1. Reproduce locally from clean build outputs:
```bash
rm -rf build dist
python -m build
```
2. Run deterministic quality gate:
```bash
make check
```
3. Verify tool/runtime pinning:
```bash
cat .python-version
python --version
```
4. Confirm dependency files are present and pinned:
```bash
ls -la requirements.txt requirements-dev.txt requirements.lock requirements-dev.lock pyproject.toml
```

## Common Causes and Fixes

- metadata/version mismatch:
  align `pyproject.toml` version and release process docs
- missing package files in sdist/wheel:
  verify module paths and package data declarations
- incompatible environment/toolchain:
  recreate virtual environment and reinstall pinned dependencies

## Recovery

1. Recreate environment:
```bash
rm -rf .venv311
make install-dev
```
2. Build again:
```bash
make build
```
3. Verify artifacts:
```bash
ls -la dist/
```

## Verification

Expected:
- `chapter_splitter-*.tar.gz` and `chapter_splitter-*.whl` exist in `dist/`
- `make check` passes end-to-end
