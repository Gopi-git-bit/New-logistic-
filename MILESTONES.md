# Milestone Master Index

| Milestone | Status | Entry Criteria | Exit Criteria | Human Gate |
|-----------|--------|----------------|---------------|------------|
| M0 | ✅ Complete | Repo exists, stack confirmed | `pnpm install`, compose config, CI green | None |
| M1 | ✅ Complete | M0 done | Supabase schema + seed + RLS + types verified on live DB | None |
| M2 | ✅ Complete | M1 done | Pricing engine, matching RPC, payment rules verified on live DB | None |
| M3 | ✅ Complete | M2 done | Heartbeat kernel + LoopGuardian + agent harness tested (pytest 11/11, DB suite 14/14) | None |
| M4 | ✅ Complete | M3 done | Odoo pipeline + webhook router verified (node 8/8, pytest 19/19, DB 12/12) | None |
| M5 | ✅ Complete | M4 done | POD/OCR pipeline, notification queue verified (pytest 43/43, DB 11/11) | None |
| M6 | ✅ Complete | M5 done | E2E order flow portal + console verified (pytest 60/60, DB 12/12) | None |
| M7 | ⏳ Not started | M6 done | DeepSeek harness, Hermes, Paperclip, Honcho | **Confirm model IDs (R1)** |
| M8 | ⏳ Not started | M7 done | Multi-tenant hardening, security tests | **Choose OCR (R2)** |
| M9 | ⏳ Not started | M8 done | Production readiness gates, Sonar/Trivy | **Choose permit API (R5)** |
| M10 | ⏳ Not started | M9 done | Go-live smoke test, live payment, runbook | **Confirm Honcho (R9), Razorpay live keys (R4)** |

## Completed Artifacts

### M0
- Monorepo skeleton (`apps/portal`, `apps/console`, `apps/workers`, 3 packages)
- Docker Compose infra (Postgres/PostGIS+pgvector, Redis, Odoo 18, nginx, worker/portal/console stubs)
- CI workflow, env template, Biome/Turbo/pnpm tooling

### M1
- 7 migrations (extensions → auth stub → DDL → functions/triggers → views → RLS → seed), all verified on live Postgres 16 + PostGIS + pgvector
- `transition_order` SECURITY DEFINER state machine — legal/idempotent/illegal-path tested
- Commission & service-fee triggers — driver 10% / company ₹700 tested live
- Long-halt telemetry trigger — 35-min probe created active alert
- RLS cross-tenant denial proven via non-owner role probes
- `infra/supabase/verify_m1.sql` repeatable verification suite — all PASS

**Bugs caught & fixed during live verification:**
1. `vehicles.assigned_driver_id` added; halt trigger now attributes driver from telemetry → vehicle → owner-profile chain
2. Trigger record-check switched `IF last_location IS NOT NULL` → `IF FOUND` (composite null semantics)
3. Extension name corrected to `vector`; auth stub ordering fixed; migration made re-runnable

### M2
- `00000000000007_pricing_engine.sql` — `pricing_rate_bands` + `pricing_toll_bands` reference tables; `infer_vehicle_class()` (upward gap resolution); `calculate_quote()` (weight-interpolated rate, toll bands, 3% loading, 5% GST); `generate_order_quote()` (distance from geo fallback, persists amounts, emits `order_quote_generated` event, pending-only guard)
- `00000000000008_matching_dispatch.sql` — `match_nearby_drivers()` returning **users.user_id** as assignment identity (D-05), deterministic score `rating×10 − km×0.05`, capacity/class/radius filters
- `00000000000009_payment_rules.sql` — `validate_payment_plan()` (full=100%, partial≥50%, to_pay=0) and BEFORE INSERT payment-hold guard with admin-override escape hatch
- `packages/shared-types/src/pricing.ts` — Quote/Match/plan types mirrored from DB

**Bugs caught & fixed during live verification:**
1. plpgsql OUT-param/column ambiguity (`vehicle_class`) → qualified all internal references
2. `count(*)` bigint vs declared integer in RETURN QUERY → explicit cast
3. Healthcheck-vs-init race documented; suites now gate on stable table count (23 post-M3)

### M3
- `00000000000010_agent_control_plane.sql` — `agent_registry` (7 agents, pause/block/budget) + durable `agent_tasks` queue with dedupe keys + claim (SKIP LOCKED)/complete/fail/dead-letter/spend/heartbeat RPCs
- Python core (`apps/workers`): `capabilities.py` 7-agent matrix · `state_machine.py` §13 flows · `loop_guardian.py` cap/malformed/hallucination/loop gates · `tracing.py` Langfuse-safe (trace=heartbeat_id) · `executor.py` intervention sink → `ai_agent_interventions` · `kernel.py` tick loop
- pytest suite: **11/11** in workspace venv (malformed, hallucinated, unauthorized, loop, cap, budget cases)
- verify_m3.sql: **14/14** live (pause-skip at claim, dead-letter ladder, dedupe, budget exhaustion + catch-path persistence)

**Key lesson encoded:** a failed RPC rolls back its own side effects — so the kernel's catch-path persists `paused/BUDGET_EXHAUSTED` after exhaustion (`set_status`), giving cheap fast-path skips thereafter.

### M5
- Migration 12: `order_documents` table (7 columns, FK→orders, RLS) + `notification_queue` table (8 columns, idempotency key unique, RLS) + `enqueue_notification()` idempotent RPC + `grab_notification_jobs()` skip-locked RPC + `mark_notification_sent()` + `mark_notification_failed()` (exponential backoff, permanent-failure ladder) + `upsert_order_document()` RPC; `document_processing` agent registered (8th agent, CHECK constraint extended)
- Workers: `ocr_provider.py` (engine-agnostic `OCRExtractor` protocol, `TesseractExtractor` via subprocess, `make_ocr_provider` factory) + `notification_sender.py` (pluggable `NotificationSender` protocol, `StubSender`/`TwilioSMSSender`/`ResendEmailSender` stubs, `make_notification_sender` factory) + `handlers.py` extended with `process_document_upload()` (OCR extract → upsert → auto-transition to `delivered` for POD) + `process_notification_job()` (deliver → mark sent/failed → log) + `kernel.py` auto-injection for `document_processing` + `communication` agents
- pytest: **43/43** (11 M3 + 8 M4 + 24 M5: OCR protocol, notification lifecycle, handler edge cases)
- verify_m5: **11/11** (order_documents insert+OCR, enqueue dedupe, notification lifecycle sent/failed, retryable+permanent failure, RLS)

**Bugs caught & fixed during live verification:**
1. `enqueue_notification` returned existing ID on conflict (correct), not NULL — test assertion corrected to `second_id = first_id`
2. `mark_notification_failed` SELECT FOR UPDATE missed row after `grab_notification_jobs` incremented attempts — removed status filter from SELECT (check via `!= 'processing'` instead)
3. `grab_notification_jobs` skips rows where `attempts >= max_attempts` — permanent failure test must grab FIRST then force attempts past max
4. M3 verify_m3 T1 agent count hardcoded to 7 — changed to `>= 7` after document_processing added
5. `service_role` GRANT fails in vanilla Postgres — wrapped in `IF EXISTS` DO block

**Key lesson encoded:** `grab_notification_jobs` uses `attempts < max_attempts` in its WHERE clause — so permanently-failed rows are invisible to grab. To test permanent failure, grab first (status→processing), THEN force attempts past max before calling `mark_notification_failed`.

### M4
- Portal: `app/api/webhooks/razorpay/route.ts` (public URL per D-08) + pure utils `lib/webhooks/razorpay.ts` — HMAC constant-time verify, replay-safe dedupe via `webhook_events.idempotency_key`, ACK-200-then-enqueue contract
- Migration 11: orders gain `odoo_sale_order_id/invoice_id/sync_status` mirror columns; `enqueue_agent_task()` idempotent RPC; WF-5 `sweep_dead_webhooks()/revive_dead_webhooks()`; WF-1 `stale_processing_payments()`
- Workers: `odoo_client.py` (Odoo 18 CE `/jsonrpc`) capability-gated to order_management/resource_management; `handlers.py` payment-event → state machine advance → Odoo push chain
- Node native TS tests **8/8** · pytest **19/19** (incl. fake-Odoo failure path marking sync failed) · verify_m4 **12/12**

### M6
- E2E order lifecycle: `place_order` (quote → validate_payment_plan → status 'pending'), `assign_driver` (match_nearby_drivers → assign_provider → 'driver_assigned'), `update_delivery_status` ('pickup'→'in_transit', 'delivered')
- `handlers.py` extended: Db protocol gains 5 methods (`generate_quote`, `match_drivers`, `assign_provider`, `validate_payment_plan`, `get_order`) + 3 new handlers (`place_order`, `assign_driver`, `update_delivery_status`)
- `kernel.py` `SupabaseTaskSource` extended with matching Db methods (RPC calls for quote/match/assign/validate); `default_tools_for()` wired with 3 lambdas; `resource_management` agent added to agent routing
- verify_m6.sql: **12/12** live (RPCs exist, validate_payment_plan 4 modes, generate_order_quote, match_nearby_drivers, full lifecycle pending→delivered→settled, assign_order_provider, idempotent re-quote, commission auto-calc, order_event_log)
- pytest: **60/60** total (11 M3 + 8 M4 + 24 M5 + 17 M6)
- Bug fixed: `validate_payment_plan` requires `advance == total` for full mode; `place_order` handler auto-sets advance=total when full and no advance_amount provided

## Remaining Human Decisions

- **R1**: Confirm `deepseek-v4-pro` / `deepseek-v4-flash` availability on OpenRouter or pick substitutes.
- **R2**: OCR engine — Tesseract default (M5), interface is engine-agnostic; vision-LLM swap requires zero code changes (implement `OCRExtractor` protocol).
- **R4**: Razorpay live merchant KYC (business/compliance).
- **R5**: Choose national permit verification provider.
- **R9**: Confirm Honcho deployment model.

See `docs/PRD/M0.md` and `docs/PRD/M1.md` for milestone contracts.
