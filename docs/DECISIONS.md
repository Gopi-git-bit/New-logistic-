# Zippy Logistics — DECISIONS (§25 Change Control)

> All deviations from the PRD must be logged here before implementation. This is mandatory.

## Format

```
| # | Date | Decision | Rationale | Impact | Approved By |
|---|------|----------|-----------|--------|-------------|
```

## Log

| # | Date | Decision | Rationale | Impact | Approved By |
|---|------|----------|-----------|--------|-------------|
| D-01 | 2026-08-01 | Tesseract as default OCR | Free, no API costs, runs locally | None — interface is engine-agnostic | @Gopi |
| D-02 | 2026-08-01 | `vector` extension name (not `pgvector`) | Postgres 16 naming convention | Migration scripts updated | @Gopi |
| D-03 | 2026-08-01 | Docker Compose over Kubernetes | Solo developer, VPS deployment | Simpler ops, single-node | @Gopi |
| D-04 | 2026-08-01 | Razorpay primary, Stripe failover | India-first payments | Dual integration | @Gopi |
| D-05 | 2026-08-15 | `match_nearby_drivers` returns `users.user_id` | Driver assignment is by user, not vehicle | D-05 alignment | @Gopi |
| D-06 | 2026-08-15 | `validate_payment_plan` full mode = 100% advance | Business rule: full payment means full advance | Handler auto-sets advance=total | @Gopi |
| D-07 | 2026-08-28 | Move workers/ to root level | PRD canonical structure | Repository reorganization | @Gopi |
| D-08 | 2026-08-29 | API Reliability & Security Contract | Autonomous-agent-safe API specification | New doc `docs/API-RELIABILITY-SECURITY.md` | @Gopi |
| D-09 | 2026-08-29 | Backend Execution Model Correction | FastAPI + Qoder Wake + Paperclip + Hermes + Odoo 18; No Temporal | Updated soul.md, PRD-backend.md, PRD-agents.md, copilot-instructions.md | @Gopi |
| D-10 | 2026-08-29 | Production API Key Wiring & Integration Hardening | Full audit + canonical env contract + FastAPI + config validation + secret redaction | New files: api/, .env.production.example, Dockerfile.api, docs/DEPLOYMENT-KEY-OWNERSHIP.md | @Gopi |
| D-11 | 2026-09-02 | Composio/TinyFish integration boundary | Composio is a typed MCP tool gateway; TinyFish is a bounded adapter. Neither is a system of record or database synchronization bus. | Added runtime contract, allowlisted adapter, production Compose wiring and deployment health gate | @Gopi |

## Pending Decisions

| ID | Question | Options | Recommendation |
|----|----------|---------|----------------|
| R1 | DeepSeek model IDs | `deepseek-v4-pro` / `deepseek-v4-flash` on OpenRouter | Confirm availability first |
| R4 | Razorpay live keys | Sandbox → Live KYC | Business/compliance required |
| R5 | Permit verification API | Vahan API, SERPAPI, custom | National permit scope TBD |
| R9 | Honcho deployment | Self-hosted vs managed | Self-hosted for control |
