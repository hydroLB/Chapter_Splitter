# ADR 0001: Layered Boundaries with Import Enforcement

- Status: Accepted
- Date: 2026-02-20

## Context

The project has both CLI and desktop UI entrypoints and a growing set of PDF/config/io modules.
Without explicit layering, deep imports and cross-module coupling increase maintenance and
regression risk.

## Decision

Adopt explicit layer direction:

- `core` (domain)
- service modules (`config`, `pdf`, `io`, `observability`, `utils`)
- interface modules (`app`, `cli`, `ui`)

Enforce direction in CI with a repository boundary check (`make boundaries`).

## Consequences

### Positive

- architecture drift is caught on PRs
- core logic remains reusable and test-focused
- interfaces can evolve independently from domain internals

### Trade-Offs

- some import patterns require explicit public exports
- boundary checker requires maintenance when packages are reorganized
