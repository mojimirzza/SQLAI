# Stage 4 Change Log — Production Readiness & Integration

This stage hardens the Stage 3 architecture rather than replacing it.

## P0 / Blockers fixed
1. Enriched Orchestrator no longer references an undefined `event_publisher`.
2. Sidecar no longer receives an undefined `record.id`; the query record is persisted before optional Sidecar hooks.
3. Sidecar `DBReader` now imports `os` for alert-database path handling.
4. Sidecar CLI now imports `json` for suggestion output.

## P1 / Production hardening
- Deterministic `PolicyGate` for role authorization, memory access, and protected tables.
- API default role changed from admin to analyst.
- Trusted gateway identity headers supported.
- Sidecar drill-down SQL now passes through the canonical SQLGlot validator and table allow-list.
- Unsupported dimensions fail closed instead of being silently discarded.
- Explicit end dates are inclusive.
- Added missing relative date contracts: this_week, last_week, last_3_months.
- Structured observability helper added.

## Verification target
- Python compilation
- Existing smoke tests
- Stage 4 regression tests
- Sidecar SQL guard tests

## Remaining Stage 4 boundary
A deployment's real IdP/gateway is still responsible for authenticating the trusted identity headers. Full load testing and external integration testing require the deployment environment and are not faked inside this repository.
