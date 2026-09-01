# Zippy Logistics — Build Start Plan

## Purpose

This document defines the safe starting sequence for continued implementation after M0–M6.
It is intentionally aligned with `docs/AUTHORITY-MATRIX.md` and `docs/PRD-backend.md`.

## Current baseline

- M0–M6 are complete.
- FastAPI is the primary API layer.
- Supabase/PostgreSQL is operational truth.
- Odoo is financial/ERP truth.
- Paperclip is governance truth.
- Hermes executes only approved, allowlisted capabilities.
- Langfuse is observability only.
- Honcho is advisory memory only.
- PostgreSQL queues + Python workers provide background durability; Temporal is not part of the current canonical stack.

## Non-blocker: TinyFish / Composio

TinyFish integration failure must not block core application development.
Composio is treated as an optional tool-access adapter, not as the data bus and not as a source of truth.
No application workflow may depend on TinyFish for correctness.

When TinyFish becomes available, integrate it behind a typed adapter and feature flag. It must never receive raw database administration capability.

## Build sequence

### Phase 0 — Protect the architecture

1. Work only on feature branches.
2. Preserve the authority matrix and system-of-record boundaries.
3. Never add direct cross-database writes.
4. Require `decision_id` for governed external mutations.
5. Fail closed when Paperclip is unavailable.
6. Keep optional integrations optional.

### Phase 1 — M7 governed execution foundation

1. Add one provider-neutral governed execution gateway.
2. Gateway submits a typed proposal to Paperclip.
3. Only `APPROVE` may reach Hermes.
4. `REJECT`, `HOLD`, `HUMAN_REVIEW`, timeout, malformed response, or service failure must not execute the tool.
5. Hermes remains responsible for the tool allowlist.
6. Preserve correlation IDs across proposal and execution.
7. Add unit tests for approve/reject/hold/fail-closed/unauthorized execution paths.

Exit criteria:

- No governed mutation can call Hermes without a Paperclip decision ID.
- Paperclip failure cannot accidentally allow execution.
- Tests prove no execution happens on non-APPROVE decisions.

### Phase 2 — M7 model/provider layer

1. Introduce a model-provider protocol independent of DeepSeek/OpenRouter.
2. Keep model IDs in configuration only.
3. Do not hard-code `deepseek-v4-pro` or `deepseek-v4-flash` as required runtime capabilities until verified.
4. Add deterministic fallback behavior when model provider is disabled/unavailable.

### Phase 3 — Honcho memory adapter

1. Implement memory read/write behind an interface.
2. Keep Honcho optional.
3. DB state always overrides memory.
4. Add tests proving memory cannot mutate authoritative state.

### Phase 4 — Composio adapters

1. Add typed capabilities only for approved tools.
2. Keep GitHub/ServerAvatar/TinyFish integrations isolated by adapter.
3. No `execute_sql`, arbitrary table writes, or unrestricted admin tools.
4. TinyFish remains disabled until connection health is verified.

### Phase 5 — M8 security hardening

Proceed only after M7 tests are green. Focus on tenant isolation, authz, secret handling, abuse/rate-limit tests, and integration credential scoping.

### Phase 6 — M9/M10 production gates

Run CI, security scans, migration verification, smoke tests, production configuration checks, live payment readiness, rollback/runbook verification, and canary deployment before full traffic.

## First implementation slice

Branch: `codex/m7-governed-execution-foundation`

Files:

- `api/services/governed_execution.py`
- `api/tests/test_governed_execution.py`

This slice does not require TinyFish, Composio, Honcho, or final DeepSeek model IDs.
