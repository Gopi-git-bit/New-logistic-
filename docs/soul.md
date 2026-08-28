# Zippy Logistics — Soul (§0 Source of Truth)

> **Every agent MUST read this file before starting any task.**

## Core Philosophy

Zippy Logistics is an AI-augmented logistics platform that connects MSMEs/shippers with verified drivers and transport companies. The platform replaces the fragmented, phone-based logistics industry with a deterministic, auditable, and intelligent system.

## Business Goals

1. **Zero-touch order lifecycle** — Customer books → system prices → driver assigned → tracking → delivery → POD → settlement, fully automated with human-in-the-loop for exceptions only.
2. **Deterministic pricing** — Every quote is reproducible from inputs. No LLM hallucinated prices. Formula: `rate_per_km × distance + toll_bands + 3% loading + 5% GST`.
3. **Multi-role transport companies** — A single entity can be customer (place orders when under-capacity) and provider (accept orders when over-capacity). Role switching is explicit and audited.
4. **Commission transparency** — Drivers: 10% of total. Transport companies as providers: ₹700 flat service fee. Customers pay zero commission.
5. **Agent governance** — All AI agents operate under LoopGuardian constraints (cap, malformed-query, hallucination, infinite-loop detection). No agent can self-approve or bypass HITL.

## Non-Negotiables

| Rule | Description |
|------|-------------|
| **RLS is sacred** | Never bypass Row Level Security. Never add `SECURITY DEFINER` unless defined in PRD-database.md |
| **State machine is law** | Never mutate `orders.status` directly. ALWAYS use `transition_order()` RPC |
| **No hardcoded business logic** | Prices, tax rates, commission percentages live in the pricing engine (`packages/pricing/`) |
| **Idempotency is mandatory** | Every mutation must be idempotent. Use `idempotency_key` for bookings, payments, webhooks |
| **Agents don't approve themselves** | No agent can approve its own HITL decisions or bypass Paperclip decision-locks |
| **Odoo is system of record** | All financial data (invoices, payments, settlements) flows through Odoo 18 CE |

## Architecture Decisions (Canonical)

- **No Kubernetes** — VPS + Docker Compose
- **No Kafka/Celery** — PostgreSQL LISTEN/NOTIFY + Python workers
- **No Django/FastAPI** — Supabase (Postgres RPC) + Next.js API routes
- **No n8n** — Python-native workflow orchestration
- **Razorpay primary, Stripe failover** — Payment processing
- **Hostinger VPS + Vercel** — Deployment

## Stack

| Layer | Technology |
|-------|------------|
| Frontend (Customer) | Next.js 15 App Router |
| Frontend (Admin/Driver) | Vite 6 + React 19 |
| Backend | Supabase (Postgres RPC, RLS, Realtime) |
| Workers | Python 3.11/3.12 headless runners |
| Database | PostgreSQL 16 + PostGIS + pgvector |
| AI Models | DeepSeek (primary), OpenRouter routing |
| Observability | Langfuse |
| ERP | Odoo 18 CE (system of record) |
| Payments | Razorpay (primary), Stripe (failover) |
| Maps | Mapbox |
| Orchestration | Docker Compose (local), VPS (production) |

## Agent Hierarchy

```
1. Customer Service Agent     — Unified customer interface
2. Order Management Agent     — Lifecycle orchestration + matching
3. Transportation Agent       — Route optimization + real-time execution
4. Resource Management Agent  — Fleet + transport company relationships
5. Payment & Settlement Agent — Financial transactions + commissions
6. Platform Administration    — Governance, compliance, oversight
7. Communication Agent        — Multi-channel notifications
8. Document Processing Agent  — OCR, POD, document management
```

All agents operate under LoopGuardian constraints. No agent has unilateral power. The Platform Administration Agent has oversight authority over all other agents.
