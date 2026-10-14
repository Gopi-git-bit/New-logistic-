# Algorithm Triage — Zippy Logistics

> Categorization of every algorithm in `algorithm.txt` against Zippy's existing codebase.
> Source of truth: `docs/soul.md`, `supabase/migrations/`, `api/`, `workers/`

---

## Legend

| Tag | Meaning |
|-----|---------|
| **NOW** | Deterministic logic needed for production. Implement immediately. |
| **DATA** | Valuable, but production data must exist before activating it. |
| **LATER** | Advanced optimization/ML with a valid future role. |
| **MERGE** | Duplicates existing DB/domain rules, pricing, routing, or dispatch logic. |
| **ABANDON** | Unnecessary, overly complex, conflicting, unsafe, or insufficient business value. |

---

## 1. Route Planning & Optimization

### 1a. Shortest-path / Mapbox Directions
**Status:** MERGE  
**Why:** Zippy already integrates Mapbox (`capabilities.py` → external `mapbox`). `generate_order_quote()` uses `ST_DDistance` great-circle for pricing. Mapbox Directions API provides real-time routing natively. Building a custom routing engine would duplicate Mapbox's core product.

### 1b. Full VRP (Vehicle Routing Problem) — CVRP, VRPTW, PDP variants
**Status:** LATER  
**Why:** Zippy is an MSME marketplace, not a fleet management system. Drivers are independent/3rd-party. Multi-stop VRP optimization only matters when one company controls 50+ vehicles on the same route. Relevant when Zippy scales to enterprise transport companies running 100+ trucks. Use Google OR-Tools or Mapbox Optimization API when needed.

### 1c. Adaptive mid-journey re-routing
**Status:** DATA  
**Why:** Requires live GPS telemetry feed from drivers, which isn't active yet. Once driver tracking is live, use Mapbox Directions API with `approaches=unrestricted` for real-time re-routing. No custom algorithm needed — Mapbox handles this.

### 1d. Geofencing (virtual boundary alerts)
**Status:** NOW  
**Why:** PostGIS supports `ST_Within` against polygon geofences. Zippy needs pickup/delivery zone validation and automatic status transitions (arriving_pickup → loading, arriving_delivery → unloading). Already partially in the schema (`dispatch_offers.pickup_zone`, `delivery_zone`). Implementation: add geofence check to `transition_order()` triggers.

---

## 2. Real-Time Shipment Tracking

### 2a. GPS pings + live map
**Status:** NOW  
**Why:** Core feature for customer trust. Zippy's `vehicle_telemetry` table exists; `match_nearby_drivers` already uses `current_location`. Need: FlutterFlow/web dashboard showing live driver position on Mapbox. No algorithm needed — just Supabase Realtime subscription + Mapbox marker.

### 2b. Predictive ETA (ML-based historical learning)
**Status:** DATA  
**Why:** Requires 6+ months of trip data (route, driver, time-of-day, actual arrival). Once Zippy has 1000+ completed trips, train a simple regression model (departure_time + route_hash → actual_duration). Store predictions in `trips.estimated_arrival`. Not needed at MVP — Mapbox ETA is sufficient.

### 2c. IoT sensor data (temperature, humidity, shock, tilt)
**Status:** ABANDON  
**Why:** Zippy is a truck marketplace, not a cold-chain logistics provider. MSME freight in India is dry van / open body. Temperature-controlled pharmaceuticals are a niche vertical. Add only if a specific customer segment demands it (e.g., pharma logistics vertical).

### 2d. Vehicle health / predictive maintenance telematics
**Status:** ABANDON  
**Why:** Drivers own their vehicles. Zippy doesn't maintain them. Predictive maintenance is a fleet-owner concern (Tata Motors, Ashok Leyland provide this). Not Zippy's domain.

### 2e. RFID / smart lock tamper detection
**Status:** ABANDON  
**Why:** Over-engineered for MSME freight. India's road freight doesn't use container seals for <₹10L shipments. Security is handled via POD verification + GPS tracking. Add only for high-value cargo vertical.

---

## 3. Carrier & Load Management

### 3a. IVSAA — Intelligent Vehicle Selection & Allocation (multi-criteria scoring)
**Status:** NOW  
**Why:** Zippy's current `match_nearby_drivers` only scores by `rating * 10 - distance * 0.05`. Missing: cargo compatibility (body_type, refrigeration), driver experience on route, vehicle age/maintenance, cost efficiency. The hard-constraint filtering (capacity, availability) is already there. Add weighted scoring on top. **This is the highest-impact algorithmic upgrade.**

Implementation plan:
- Enhance `match_nearby_drivers()` to accept cargo attributes (fragile, hazardous, temp-controlled)
- Add scoring dimensions: route_familiarity, vehicle_age, fuel_efficiency, cost_efficiency
- Make weights configurable per tenant (`pricing_overrides` table pattern)

### 3b. Automated load tendering (broadcast to carrier network)
**Status:** DATA  
**Why:** Requires a network of pre-approved carriers with defined SLAs. Zippy currently matches directly to drivers. When transport companies onboard as providers (multi-role), broadcast tendering becomes relevant. Collect carrier performance data first.

### 3c. 3D Bin Packing (3D-BPSOA)
**Status:** ABANDON  
**Why:** Zippy's MSME customers ship palletized/loose cargo, not containerized freight. Bin packing optimization matters for LTL (less-than-truckload) consolidation and container loading. Zippy is full-truckload FOC (free on carrier). The 80-88% volumetric efficiency gains apply to 32ft multi-axle trucks doing Amazon-style sortation, not a Tata Ace doing local delivery.

---

## 4. Freight Audit & Payment

### 4a. Automated invoice verification against contract rates
**Status:** NOW  
**Why:** Zippy already has settlement via Odoo, but no automated audit. When a trip completes, the system should verify: quoted amount vs actual distance vs contract rate vs any accessorial charges (waiting time, detour). Flag discrepancies >5% for human review. Implementation: SQL function `audit_settlement(order_id)` that compares `orders.total_amount` with `pricing_engine.calculate_quote()` output and distance实际traveled (from GPS).

### 4b. Payment reconciliation matching (bank statement ↔ invoice)
**Status:** DATA  
**Why:** Razorpay handles payment capture. Odoo handles invoicing. Reconciliation requires actual payment data flowing through both systems. Activate after Razorpay webhook integration is live and Odoo sync is running in production.

---

## 5. Order & Inventory Integration

### 5a. OMS ↔ TMS data flow
**Status:** MERGE  
**Why:** Zippy already does this. Order placed in Next.js portal → FastAPI → PostgreSQL → `transition_order()` RPC. Status updates flow back via Supabase Realtime. This is the core product, not an algorithm.

### 5b. WMS ↔ TMS integration
**Status:** ABANDON  
**Why:** Zippy is not a warehouse management system. WMS integration is for companies like Amazon, Flipkart who own warehouses. Zippy connects shippers to drivers. The warehouse-side work is the customer's problem.

---

## 6. Analytics & Predictive Intelligence

### 6a. KPI dashboard (on-time delivery %, cost/mile, fleet utilization)
**Status:** NOW  
**Why:** Requires no ML. Just SQL queries over existing tables (`orders`, `trips`, `vehicle_telemetry`). Build as PostgreSQL views or a simple analytics endpoint. Critical for transport company admins to manage operations.

### 6b. Demand forecasting (ML-based)
**Status:** LATER  
**Why:** Requires 12+ months of order history with seasonal patterns. Relevant for: transport companies deciding fleet expansion, Zippy deciding which corridors to promote. Use Prophet or simple ARIMA once data exists. Not MVP.

### 6c. Anomaly detection (fraud, unusual patterns)
**Status:** DATA  
**Why:** Requires production data to establish baselines. Once live: detect drivers claiming delivery without GPS confirmation, orders with abnormally high cancellations, pricing outliers. Simple statistical rules first (z-score), ML later.

### 6d. Carrier performance scoring
**Status:** DATA  
**Why:** Requires completed trip data. Score drivers on: on-time %, damage rate, customer rating, route efficiency. Feed into IVSAA scoring. Activate after 500+ completed trips.

---

## 7. Dynamic Pricing (DPYMA)

### 7a. Cost-plus deterministic pricing
**Status:** MERGE  
**Why:** Already implemented in `calculate_quote()`. Formula: `rate_per_km × distance + toll_band + 3% loading + 5% GST`. This IS the cost-plus model. No new algorithm needed.

### 7b. Real-time diesel price integration
**Status:** DATA  
**Why:** Diesel prices change daily in India. API integration with data.gov.in or GoodReturns is straightforward. But: the pricing formula already uses rate bands that can be updated periodically. Real-time integration adds marginal value vs operational complexity. Update bands weekly, not real-time.

### 7c. Demand-based surge pricing
**Status:** LATER  
**Why:** Relevant for peak seasons (Diwali, monsoon) when truck availability drops 30-40%. But: Zippy's business model is commission-based (10% driver, ₹700 transport company). Surge pricing affects the customer price, not Zippy's revenue. Implement only if transport companies request it as a feature. Requires demand signal data first.

### 7d. Competitive price monitoring (scraping competitor rates)
**Status:** ABANDON  
**Why:** Unethical (web scraping competitors), legally risky, and fragile. Zippy's value is not price wars — it's trust, transparency, and governance. Compete on service quality, not price matching.

### 7e. Customer segmentation pricing (loyalty discounts)
**Status:** DATA  
**Why:** Requires customer order history. Implement after production data shows repeat customer patterns. Simple tiered discounts (5% for >50 orders/month, 10% for >200 orders/month) don't need ML.

---

## 8. Warehouse Slotting (IWSMA)

### 8a. Dynamic SKU slotting
**Status:** ABANDON  
**Why:** Zippy is NOT a warehouse management system. This algorithm optimizes pick paths inside warehouses. Zippy operates at the transport layer — goods leave the warehouse and Zippy moves them. Out of scope.

### 8b. Affinity-based co-location
**Status:** ABANDON  
**Why:** Same as above. This is an internal warehouse optimization problem.

---

## 9. Bin Packing & Loading

### 9a. 3D Bin Packing (3D-BPSOA)
**Status:** ABANDON  
**Why:** Already covered in §3c. NP-hard problem requiring GA/SA/DRL. Irrelevant for Zippy's FTL MSME freight.

### 9b. Simple load optimization (weight distribution, stack rules)
**Status:** LATER  
**Why:** Basic heuristics (heavy items bottom, fragile on top, weight balanced across axles) could be a useful driver-facing feature. But: drivers know how to load their trucks. Only add if customers report damage issues. Low priority.

---

## 10. Algorithms NOT in the Document (Zippy-Specific)

These are Zippy-specific algorithms from the PRD that the document doesn't cover:

| Algorithm | Status | Notes |
|-----------|--------|-------|
| `transition_order()` state machine | **DONE** | Core governance |
| Commission calculation (10% / ₹700) | **DONE** | Revenue model |
| Payment plan validation | **DONE** | Business rules |
| Paperclip governance chain | **DONE** | Unique to Zippy |
| Hermes tool allowlist | **DONE** | Security |
| LoopGuardian (agent constraints) | **DONE** | Agent safety |
| Idempotency (INSERT ON CONFLICT) | **DONE** | Reliability |
| POD verification lifecycle | **DONE** | Settlement gate |
| Long-halt detection | **DONE** | Basic anomaly |

---

## Implementation Priority Matrix

| Priority | Algorithm | Effort | Impact |
|----------|-----------|--------|--------|
| **P0 — NOW** | Enhanced IVSAA (vehicle selection scoring) | 2 days | High — better matches = fewer cancellations |
| **P0 — NOW** | Geofence-based status transitions | 1 day | Medium — automates arrival/departure |
| **P0 — NOW** | Settlement audit function | 1 day | High — prevents overpayment |
| **P0 — NOW** | KPI dashboard (SQL views) | 1 day | Medium — transport company retention |
| **P1 — DATA** | Carrier performance scoring | 0.5 day | Medium — feeds IVSAA |
| **P1 — DATA** | Customer segmentation pricing | 0.5 day | Medium — retention |
| **P1 — DATA** | Anomaly detection (statistical) | 1 day | Medium — fraud prevention |
| **P1 — DATA** | Predictive ETA | 2 days | Medium — customer experience |
| **P2 — LATER** | Full VRP (OR-Tools) | 5 days | Low now, high at scale |
| **P2 — LATER** | Demand-based surge pricing | 2 days | Low — niche use case |
| **P2 — LATER** | Demand forecasting | 3 days | Low — needs 12mo data |
| **P3 — ABANDON** | 3D bin packing | — | — |
| **P3 — ABANDON** | Warehouse slotting | — | — |
| **P3 — ABANDON** | IoT sensors | — | — |
| **P3 — ABANDON** | Predictive maintenance | — | — |
| **P3 — ABANDON** | RFID/smart locks | — | — |
| **P3 — ABANDON** | WMS integration | — | — |
| **P3 — ABANDON** | Competitive scraping | — | — |

---

## Summary

| Category | Count | Algorithms |
|----------|-------|------------|
| **NOW** | 4 | IVSAA scoring, geofencing, settlement audit, KPI dashboard |
| **DATA** | 6 | Carrier scoring, customer pricing, anomaly detection, predictive ETA, payment reconciliation, diesel price integration |
| **LATER** | 3 | Full VRP, surge pricing, demand forecasting |
| **MERGE** | 3 | Mapbox routing, OMS data flow, cost-plus pricing |
| **ABANDON** | 8 | 3D bin packing, warehouse slotting, IoT sensors, predictive maintenance, RFID, WMS, competitive scraping, load optimization |
