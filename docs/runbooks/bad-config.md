# Runbook: Bad Config

## Trigger

- app/CLI fails at startup with `ConfigurationError`
- message references config schema, TOML parse, or missing override path

## Triage

1. Capture failing command and config source:
```bash
echo "$CHAPTER_SPLITTER_CONFIG"
echo "$CHAPTER_SPLITTER_CONFIG_PATH"
```
2. Reproduce with full checks:
```bash
make check
```
3. Validate config file path exists:
```bash
ls -la "$CHAPTER_SPLITTER_CONFIG"
```
4. Run CLI with explicit config to isolate environment effects:
```bash
chapter-splitter --config /absolute/path/to/config.toml split --pdf /tmp/in.pdf --chapters /tmp/chapters.toml
```

## Recovery

1. Remove/clear bad override:
```bash
unset CHAPTER_SPLITTER_CONFIG
unset CHAPTER_SPLITTER_CONFIG_PATH
```
2. Run with defaults:
```bash
make dev
```
3. If override is required, repair invalid keys/types against:
- `Chapter_Splitter/chapter_splitter/config/settings.toml`

## Verification

```bash
make test
make dev
```

Expected:
- no `ConfigurationError` on startup
- app/CLI executes with deterministic behavior

## Escalation Data

Include in incident notes:
- failing config file
- exact exception text
- command and environment variables used
