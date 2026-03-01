# ADR 0002: Typed Config Validation and Explicit Injection

- Status: Accepted
- Date: 2026-02-20

## Context

Configuration controls timeouts, retries, collision behavior, and UI behavior. Hidden global state
for config makes testing and runtime behavior less predictable.

## Decision

- keep a typed settings schema and strict validation on startup
- load config explicitly at entry boundaries
- inject resolved settings into runtime workflows instead of relying on global singleton access

## Consequences

### Positive

- runtime behavior is explicit and deterministic
- unit tests can inject settings without process-global side effects
- configuration failures surface early and consistently

### Trade-Offs

- more explicit parameters are passed across some boundaries
- entrypoint code owns more wiring responsibility
