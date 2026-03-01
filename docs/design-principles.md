# Design Principles

## What We Optimize For

- deterministic behavior across local and CI workflows
- explicit contracts at boundaries (typed config, typed errors, structured logs)
- composable core logic that is UI-agnostic and testable
- small, incremental changes over large rewrites
- operational clarity: one-command checks, clear runbooks, clear failure semantics

## How We Build

- keep IO at edges and domain logic in core modules
- fail fast on invalid config and invalid inputs
- use boring, proven tooling and pinned dependencies
- keep retries/timeouts/cancellation explicit for long-running operations
- keep observability structured from day one (events, correlation IDs, metrics hooks)

## Anti-Goals

- hidden mutable global state for runtime-critical decisions
- deep cross-layer imports and circular dependencies
- ad-hoc error handling with inconsistent exit behavior
- unbounded operations or silent failures
- undocumented operational procedures for common incidents
