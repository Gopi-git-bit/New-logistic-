# Zippy Logistics — Memory

> Current state of the project. Updated after each milestone completion.

## Current Phase: M6 Complete ✅ + Architecture Correction

**Last updated**: 2026-08-29

## Architecture Correction (D-09)

Backend execution model corrected:
- **FastAPI** — Application API layer
- **Qoder Wake** — Autonomous backend engineering/execution
- **Paperclip** — Governance authority
- **Hermes** — Approved tool/API execution
- **Odoo 18** — ERP / financial system of record
- **Apidog/OpenAPI** — API contract
- **No Temporal** — Background execution via PostgreSQL queues + Python workers

## Completed Milestones

| Milestone | Status | Key Deliverable |
|-----------|--------|-----------------|
| M0 | ✅ | Monorepo skeleton, Docker Compose, CI, Biome/Turbo/pnpm |
| M1 | ✅ | 18 tables, `transition_order` state machine, commission triggers, RLS, seed data |
| M2 | ✅ | Pricing engine, `match_nearby_drivers`, `validate_payment_plan` |
| M3 | ✅ | Agent control plane, task queue, pause/budget RPCs, LoopGuardian |
| M4 | ✅ | Odoo sync pipeline, webhook router, idempotent `enqueue_agent_task()` |
| M5 | ✅ | POD/OCR pipeline, notification queue, document processing agent |
| M6 | ✅ | E2E order lifecycle (place_order → assign_driver → update_delivery_status) |

## Test Suite Status

| Suite | Count | Status |
|-------|-------|--------|
| pytest (M3) | 11 | ✅ All passing |
| pytest (M4) | 8 | ✅ All passing |
| pytest (M5) | 24 | ✅ All passing |
| pytest (M6) | 17 | ✅ All passing |
| Node TS (M4) | 8 | ✅ All passing |
| verify_m1.sql | 11 | ✅ All passing |
| verify_m2.sql | 21 | ✅ All passing |
| verify_m3.sql | 14 | ✅ All passing |
| verify_m4.sql | 12 | ✅ All passing |
| verify_m5.sql | 11 | ✅ All passing |
| verify_m6.sql | 12 | ✅ All passing |
| **Total** | **119** | **✅** |

## Database State

- **Docker image**: `postgis/postgis:16-3.4` + `postgresql-16-pgvector`
- **Table count**: 25 (stable)
- **Extensions**: postgis, vector, uuid-ossp
- **14 migrations** (00–12c) applied and verified

## Pending Human Decisions

| ID | Decision | Status |
|----|----------|--------|
| R1 | Confirm `deepseek-v4-pro` / `deepseek-v4-flash` availability | ⏳ Pending |
| R2 | OCR engine — Tesseract default, vision-LLM swap is zero-code | ✅ Decided (Tesseract) |
| R4 | Razorpay live merchant KYC | ⏳ Pending |
| R5 | National permit verification provider | ⏳ Pending |
| R9 | Honcho deployment model | ⏳ Pending |

## Key Lessons Learned

1. **Failed RPCs roll back side effects** — Budget exhaustion pause must be persisted by caller's catch-path
2. **plpgsql composite IS NOT NULL** — Always use `IF FOUND THEN` instead
3. **Multi-column table functions** — Cannot be `PERFORM`ed; must use `SELECT ... INTO` or `RETURN QUERY`
4. **`service_role` doesn't exist in vanilla Postgres** — GRANT statements wrapped in `IF EXISTS` DO blocks
5. **`agent_registry` CHECK constraint** — Hard-coded; adding new agent requires `DROP CONSTRAINT` + `ADD CONSTRAINT`
6. **Docker healthcheck race** — Container turns green while init scripts still run; gate on stable table count
7. **`validate_payment_plan` full mode** — Requires `advance == total`, not just non-zero
