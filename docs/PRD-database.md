# PRD — Database (§7 Schema, RLS, PostGIS, pgvector)

> Source of truth for all database specifications.

## 1. Database Stack

- **Engine**: PostgreSQL 16
- **Extensions**: PostGIS (geospatial), pgvector (embeddings), uuid-ossp
- **Docker Image**: `postgis/postgis:16-3.4` + `postgresql-16-pgvector`
- **Extension name**: `vector` (NOT `pgvector` — Postgres 16 convention)

## 2. Schema Overview

### Core Tables (18 app tables)

| Table | Purpose |
|-------|---------|
| `users` | Unified identity with `base_role`, `active_role`, `payment_hold` |
| `customer_profiles` | Customer-specific data |
| `driver_profiles` | Driver-specific data |
| `transport_companies` | Company-specific data, dual-role support |
| `vehicles` | Vehicle registry with `current_status`, `current_location` |
| `vehicle_telemetry` | Time-series location/telemetry data |
| `orders` | Full order lifecycle, pricing, commission fields |
| `payments` | Payment records |
| `payment_transactions` | Financial transaction ledger |
| `admin_actions` | Admin intervention audit log |
| `driver_alerts` | Driver alert system |
| `ai_agent_activities` | Agent activity log |
| `ai_agent_interventions` | Agent intervention records |
| `notification_queue` | Notification queue with retry logic |
| `webhook_events` | Webhook event log |
| `order_documents` | Document storage references |
| `order_event_log` | Order event timeline |
| `agent_registry` | Active agent registry |
| `agent_tasks` | Durable task queue |
| `sop_sections` | Standard Operating Procedure sections |

## 3. Key Constraints

### Order State Machine
```
pending → inventory_confirmed → payment_succeeded → driver_assigned → in_transit → delivered → payment_settled
```
All transitions enforced by `transition_order()` SECURITY DEFINER function.

### Commission Rules
- Driver providers: 10% commission of `total_amount`
- Transport company providers: Flat ₹700 service fee
- Customers: Zero commission

### Payment Modes
- `full`: 100% advance (advance = total)
- `partial`: Minimum 50% advance
- `to_pay`: 0% advance (consignee pays on delivery)

### Positive Amounts
- `base_amount > 0 AND total_amount > 0` (CHECK constraint)

## 4. PostGIS Usage

### Geospatial Columns
- `pickup_location GEOGRAPHY(POINT, 4326)`
- `delivery_location GEOGRAPHY(POINT, 4326)`
- `current_location GEOGRAPHY(POINT, 4326)` (vehicles)

### Spatial Queries
```sql
-- Match nearby drivers
SELECT * FROM match_nearby_drivers(
    ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography,
    radius_meters, limit, required_class, cargo_weight
);
```

### Indexes
- GiST indexes on all geography columns
- `ST_DWithin` for proximity queries

## 5. pgvector Usage

### Vector Columns
- `sop_sections.vector_embedding VECTOR(1536)` — SOP semantic search

### Vector Search
```sql
-- Semantic SOP search
SELECT * FROM sop_sections
ORDER BY vector_embedding <=> $query_embedding
LIMIT 5;
```

## 6. Row Level Security (RLS)

### Policy Principles
1. Users read/update only their own `users` row
2. Customers see only their own orders and profiles
3. Drivers see only their own profile, assigned orders, telemetry
4. Transport companies see their own company and assigned orders
5. Admins have full read access
6. Telemetry INSERT open to authenticated service accounts

### Auth Stubs (Vanilla Postgres)
```sql
-- 00000000000004_auth_stub.sql
CREATE OR REPLACE FUNCTION auth.uid() RETURNS UUID AS $$
BEGIN
    RETURN current_setting('request.jwt.claims', true)::json->>'sub';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION auth.role() RETURNS TEXT AS $$
BEGIN
    RETURN current_setting('request.jwt.claims', true)->>'role';
END;
$$ LANGUAGE plpgsql;
```

## 7. Migration Files

| File | Purpose |
|------|---------|
| `00000000000000_extensions.sql` | PostGIS, pgvector, uuid-ossp |
| `00000000000001_initial_schema.sql` | All 18 tables + constraints |
| `00000000000002_functions_triggers.sql` | `transition_order`, triggers |
| `00000000000003_views.sql` | Materialized views |
| `00000000000004_auth_stub.sql` | Auth function stubs |
| `00000000000005_rls_policies.sql` | RLS policies |
| `00000000000006_seed_data.sql` | Initial data |
| `00000000000007_pricing_engine.sql` | Pricing functions |
| `00000000000008_matching_dispatch.sql` | Driver matching |
| `00000000000009_payment_rules.sql` | Payment validation |
| `00000000000010_agent_control_plane.sql` | Agent queue + RPCs |
| `00000000000011_odoo_pipeline_webhooks.sql` | Odoo sync + webhooks |
| `00000000000012_pod_notification.sql` | POD + notifications |
| `00000000000012b_upsert_document.sql` | Document upsert |
| `00000000000012c_fix_mark_failed.sql` | Notification failure fix |

## 8. Verification Suites

Each milestone has a verification SQL suite:

```bash
# Run verification
docker cp supabase/verify_mN.sql zippy-db:/tmp/vN.sql
docker exec zippy-db psql -U postgres -d postgres -f /tmp/vN.sql
```

| Suite | Assertions |
|-------|------------|
| `verify_m1.sql` | 11 |
| `verify_m2.sql` | 21 |
| `verify_m3.sql` | 14 |
| `verify_m4.sql` | 12 |
| `verify_m5.sql` | 11 |
| `verify_m6.sql` | 12 |

## 9. Key Gotchas

1. **`service_role` doesn't exist** — GRANT statements wrapped in `IF EXISTS` DO blocks
2. **plpgsql composite IS NOT NULL** — Use `IF FOUND THEN` instead
3. **Multi-column table functions** — Cannot be `PERFORM`ed; use `SELECT ... INTO`
4. **`agent_registry` CHECK constraint** — Hard-coded; adding agent requires constraint update
5. **Docker healthcheck race** — Gate on stable table count before running tests
6. **`validate_payment_plan` full mode** — Requires `advance == total`, not just non-zero
7. **`grab_notification_jobs` WHERE clause** — Skips rows where `attempts >= max_attempts`
