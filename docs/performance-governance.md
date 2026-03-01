# Performance and Resilience Governance

This document defines how performance guardrails are enforced and how to tune runtime resource
behavior without code changes.

## Guardrails (Measured and Enforced)

Performance checks run in `tests/performance/test_benchmarks.py` and use
`benchmarks/baseline.json`.

Current enforced constraints:

- split path median runtime must be `<= baseline["split_chapters_seconds"] * 2`
- outline detection median runtime must be `<= baseline["outline_detection_seconds"] * 2`
- both medians must be `<= performance.benchmark_budget_seconds`

Measurement process:

- each benchmark runs `performance.benchmark_iterations` iterations
- median is used (not mean) to reduce single-spike noise
- checks run inside `make test` and therefore inside `make check` and CI

## Baseline Update Policy

Use baseline updates only for justified changes, not to mask regressions.

Allowed reasons:

- intentional algorithmic change that shifts normal runtime profile
- dependency/runtime change with validated and acceptable impact
- benchmark fixture/input change that materially changes workload shape

Required process:

1. Run current benchmarks and record before values.
2. Run `python scripts/update_benchmarks.py`.
3. Review `benchmarks/baseline.json` diff and explain each changed metric in the PR.
4. Include environment notes in the PR:
   - machine class (CPU, RAM)
   - Python version (from `.python-version`)
   - iteration count used
5. Re-run `make test` and `make check`.

Not allowed:

- updating baseline without linking to a measured reason
- baseline-only PRs with no benchmark evidence

## Operational Tuning and Resource Limits

All tuning must be done through config in
`Chapter_Splitter/chapter_splitter/config/settings.toml` or an override file.

### IO Deadlines

- `io.pdf_read_timeout_seconds`: upper bound for PDF reads
- `io.pdf_write_timeout_seconds`: upper bound for chapter PDF writes
- `io.operation_timeout_seconds`: global operation deadline for split/detect workflows
- `io.viewer_timeout_seconds`: max wait when opening external viewer

Operational guidance:

- increase for very large PDFs or slow disks
- decrease for strict responsiveness and fast failure behavior
- keep all timeout values finite and non-zero

### Retry/Backoff

- `retry.max_attempts`: maximum attempts for retry-protected operations
- `retry.initial_delay_seconds`: first delay before retry
- `retry.max_delay_seconds`: cap on retry delay
- `retry.jitter_ratio`: jitter to avoid retry bursts

Operational guidance:

- low-latency/local workloads: lower attempts and delays
- unstable storage/network mounts: moderate attempts with bounded max delay
- avoid unbounded retry growth; keep `max_delay_seconds` conservative

### Throughput and Output Controls

- `io.output_collision_policy`: `error`, `overwrite`, or `suffix`
- `io.output_collision_max_suffix`: upper bound when suffix mode is used
- `validation.max_chapters`: hard cap on chapter count in one run
- `ui.action_rate_limit_seconds`: UI backpressure against repeated actions

Operational guidance:

- high-volume automated runs: prefer deterministic output policy (`error` or `overwrite`)
- user-interactive safety: use `suffix` with a bounded `output_collision_max_suffix`
- raise `validation.max_chapters` only with measured runtime impact review

### Benchmark Knobs

- `performance.benchmark_iterations`: sample count for benchmark medians
- `performance.benchmark_budget_seconds`: absolute budget ceiling for hot paths

Operational guidance:

- CI speed focus: keep iterations lower but stable
- release hardening: temporarily increase iterations for tighter confidence
- tighten budget when optimizing, relax only with explicit justification

## Release/PR Expectations

When a PR affects split/detect performance characteristics, include:

1. benchmark before/after numbers
2. whether baseline changed
3. exact config knobs adjusted (if any)
4. risk assessment for slower machines and large files
