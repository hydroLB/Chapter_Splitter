# ADR 0003: Error Code Contract and Structured Observability

- Status: Accepted
- Date: 2026-02-20

## Context

Operational debugging needs stable log fields, correlation IDs, and predictable exit semantics.
Previously, exception handling logic was duplicated across boundaries.

## Decision

- keep existing typed exception classes and add typed error codes
- centralize exception-to-payload mapping for app/CLI/UI boundaries
- standardize structured error fields (`error_code`, `exit_code`, `location`, `reason`)
- provide minimal metrics hooks (`MetricsSink`) with a no-op default backend

## Consequences

### Positive

- consistent logs and exit behavior across entrypoints
- easier alerting/triage via stable error fields
- instrumentation can be upgraded without changing business logic

### Trade-Offs

- boundary handlers depend on shared mapper contract
- metrics backend integration is deferred and must be added separately
