# Threat Model Notes

## Scope

This note documents realistic abuse paths and mitigations for the highest-risk surfaces in this
repository:

- file input (PDF and chapter TOML)
- config override path (`--config`, `CHAPTER_SPLITTER_CONFIG`)
- output writes (chapter exports and TOML/session writes)
- structured logging and redaction

The model assumes local desktop/CLI execution with user-selected files and no network-facing API.

## Assets and Trust Boundaries

### Assets

- user PDFs and generated chapter outputs
- local filesystem integrity for output directories
- configuration integrity for runtime behavior
- log records that may include user-provided content and paths

### Trust Boundaries

- untrusted file content crossing into parser/loader code (`pypdf`, TOML reader)
- untrusted path input crossing into filesystem operations
- untrusted strings crossing into logs/UI messages

## Critical Surfaces

### 1) File Input

#### Abuse Paths

- malicious or malformed PDF causes parser exceptions or expensive processing
- oversized chapter TOML causes high memory/time consumption
- misleading chapter content attempts to trigger unsafe filenames or invalid ranges

#### Existing Mitigations

- typed domain validation for chapter ranges and constraints
- cooperative IO deadlines and cancellation checks at application-controlled checkpoints
- retry policy constrained by config and bounded backoff
- strict TOML parsing and type checks for chapter structures
- sanitized output filename generation (`safe_filename`)
- structured domain exceptions for controlled failure behavior

#### Residual Risk

- parser-level denial-of-service remains possible with adversarial PDFs
- very large local files can still consume resources before cancellation triggers
- a blocking parser or serializer call cannot be forcibly interrupted by a deadline or token

### 2) Config Override

#### Abuse Paths

- attacker-controlled config path changes operational behavior (timeouts, output policy, retries)
- invalid values attempt to disable safeguards (timeouts <= 0, malformed enums)

#### Existing Mitigations

- centralized schema validation with strict type and bounds checks
- invalid config fails fast with `ConfigurationError`
- config read deadline enforcement through `CHAPTER_SPLITTER_CONFIG_TIMEOUT_SECONDS`

#### Residual Risk

- if a user intentionally points to a hostile local config, behavior can still be degraded within
  allowed schema bounds

### 3) Output Writes

#### Abuse Paths

- path collision/overwrite causes data loss
- partial writes leave corrupted artifacts
- write targets point to sensitive locations via user-chosen paths

#### Existing Mitigations

- explicit collision policy (`error`/`overwrite`/`suffix`) with deterministic checks
- chapter PDFs are staged beside their destinations before any batch commit begins
- ordinary commit failures trigger reverse-order rollback; overwrite mode preserves originals in
  temporary backups until commit succeeds
- non-overwrite commits use no-clobber installation, preventing a target created after planning from
  being silently replaced
- output parent validation and directory creation checks
- cancellation and timeout checks during export loops

#### Residual Risk

- user-specified output paths can still target unintended locations on the same machine
- overwrite mode remains destructive by design
- process or machine termination during the multi-file commit window can leave a partial batch

### 4) Logging Redaction

#### Abuse Paths

- sensitive values leak via log message text or structured extras
- user-provided strings attempt log-forging style payloads

#### Existing Mitigations

- structured JSON logging with explicit event fields
- context correlation IDs for traceability
- recursive redaction for configured keys and sensitive value substrings in nested mappings,
  sequences, and exception diagnostics, with cycle-safe traversal
- log contract tests for required schema, correlation IDs, recursive redaction, and sanitized
  exception tracebacks

#### Residual Risk

- secrets not covered by configured key/value redaction rules may still be logged
- operator misconfiguration of redaction keys/values reduces protection

## Recommended Operational Controls

- run as non-admin user with least-privilege filesystem access
- keep secret scanning in CI (`gitleaks`) and run local scan before security-sensitive PRs
- review config overrides in support/debug sessions before execution
- avoid `overwrite` collision policy unless explicitly required

## Out of Scope

- remote code execution from external network inputs (no service endpoint in current architecture)
- host-level compromise or privileged local malware
