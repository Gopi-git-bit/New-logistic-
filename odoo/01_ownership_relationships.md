# Odoo 18 Database Ownership & Relationship Blueprint

## Critical rule

**Do not run custom SQL directly against Odoo core tables to build this integration.**
Odoo owns and migrates its PostgreSQL schema through ORM modules. Extend Odoo through a custom module/API fields when necessary.

Odoo is the **ERP / financial System of Record**.

Zippy Operational DB stores only external references such as:

- `odoo_partner_id`
- `odoo_sale_order_id`
- `odoo_picking_id`
- `odoo_move_id`
- `odoo_payment_id`

Paperclip stores only governance references such as:

- target system = `ODOO`
- entity type = `account.move`
- entity ID = Odoo record ID
- requested action = `POST_VENDOR_BILL`
- policy result / approval / execution grant

---

## 1. Odoo authoritative model relationships

```text
res.partner
  │
  ├── crm.lead
  │      │
  │      └── conversion / quotation
  │
  ├── sale.order
  │      ├── sale.order.line
  │      ├── stock.picking
  │      │      └── stock.move / stock.move.line
  │      └── account.move (customer invoice)
  │             └── account.move.line
  │
  ├── purchase.order
  │      ├── purchase.order.line
  │      ├── stock.picking (receipt, where applicable)
  │      └── account.move (vendor bill)
  │             └── account.move.line
  │
  └── account.payment
         └── reconciliation through account.move.line
```

### Canonical ownership

| Odoo object | Authority |
|---|---|
| `res.partner` | Verified ERP customer/vendor master |
| `crm.lead` | Qualified sales/CRM record |
| `sale.order` | ERP quotation / confirmed commercial sale |
| `purchase.order` | ERP procurement/vendor commitment where used |
| `stock.picking` | ERP delivery/receipt document |
| `stock.move` | Inventory movement |
| `account.move` | Customer invoice, vendor bill, credit note, journal entry |
| `account.move.line` | Accounting lines / receivable / payable |
| `account.payment` | ERP-side payment record |
| reconciliation | Odoo accounting authority |
| taxes / journals / chart of accounts | Odoo authority |

---

## 2. Zippy ↔ Odoo relationship map

```text
Zippy customers.id
   └── external_references
         └── Odoo res.partner(id)

Zippy vendors.id
   └── external_references
         └── Odoo res.partner(id)

Zippy orders.id
   ├── external_references → Odoo sale.order(id)
   ├── external_references → Odoo stock.picking(id)
   └── financial_requests
          └── external_references → Odoo account.move(id)

Zippy payment_gateway_events
   └── financial_request(record_customer_payment)
          └── Paperclip approval when policy requires
                 └── Odoo account.payment(id)
                        └── Odoo reconciliation

Zippy pod_documents + document_verifications
   └── Paperclip PAY-INV-002 check
         └── execution grant
               └── Odoo account.move.action_post
```

There must be **no cross-database foreign key**. Cross-system relationships are stored as immutable IDs/references.

---

## 3. Recommended minimal custom Odoo fields

Implement these through an Odoo custom module, **not raw SQL**.

### `res.partner`

- `x_zippy_customer_id` — Char / UUID string
- `x_zippy_vendor_id` — Char / UUID string
- `x_zippy_company_id` — Char / UUID string
- `x_zippy_sync_version` — Integer
- `x_zippy_last_sync_at` — Datetime

### `sale.order`

- `x_zippy_order_id` — Char, indexed, unique at application level
- `x_zippy_order_number` — Char
- `x_zippy_company_id` — Char
- `x_zippy_idempotency_key` — Char
- `x_zippy_governance_ref` — Char, optional for high-risk flows

### `stock.picking`

- `x_zippy_order_id` — Char
- `x_zippy_trip_id` — Char
- `x_zippy_pod_ref` — Char
- `x_zippy_pod_status` — Selection (`pending`, `verified`, `partial`, `rejected`)
- `x_zippy_delivery_event_at` — Datetime

### `account.move`

- `x_zippy_order_id` — Char
- `x_zippy_financial_request_id` — Char
- `x_zippy_idempotency_key` — Char
- `x_paperclip_proposal_id` — Char
- `x_paperclip_decision` — Selection (`approved`, `hold`, `rejected`, `hitl_required`)
- `x_paperclip_policy_version` — Char
- `x_paperclip_grant_nonce` — Char
- `x_zippy_pod_ref` — Char
- `x_zippy_rate_variance_pct` — Float
- `x_zippy_weight_variance_pct` — Float

### `account.payment`

- `x_zippy_order_id` — Char
- `x_zippy_gateway_provider` — Char
- `x_zippy_gateway_payment_id` — Char
- `x_zippy_financial_request_id` — Char
- `x_zippy_idempotency_key` — Char

---

## 4. Odoo integration invariants

### ODOO-BRIDGE-001 — No duplicate side effect

Every create/post/payment command must carry a Zippy idempotency key.
Before creating a new Odoo record, integration code searches for the same key.

### ODOO-BRIDGE-002 — No posting without governance when required

For governed actions, `account.move.action_post` or refund/settlement execution must require a currently valid Paperclip execution grant.

### ODOO-BRIDGE-003 — Odoo ID returned to Zippy

After Odoo creates an authoritative record, the result ID is written to Zippy `external_references`.

### ODOO-BRIDGE-004 — Zippy does not mirror the ledger

Do not copy journal lines, receivable/payable balances, tax ledgers or full invoice state into Supabase. Read them from Odoo when needed.

### ODOO-BRIDGE-005 — Reconciliation authority

Razorpay/webhook state can initiate reconciliation, but only Odoo determines whether the invoice is financially reconciled.

### ODOO-BRIDGE-006 — POD governance

A POD in Zippy is operational evidence. Paperclip verifies the evidence against policy. Odoo receives the approved consequence; Odoo does not become the high-frequency POD/telemetry database.

---

## 5. Recommended command/event bridge

```text
ZIPPY OPERATIONAL EVENT
        │
        ▼
financial_requests
        │
        ▼
Paperclip proposal
        │
  APPROVE / HOLD
        │
        ▼
execution_grant
        │
        ▼
Hermes Odoo capability
        │ JSON-RPC/XML-RPC
        ▼
ODOO ORM
        │
        ▼
Authoritative Odoo record
        │
        ▼
external_references in Zippy
        │
        ▼
operational event / UI status
```

Never use:

```text
Hermes → raw SQL → Odoo PostgreSQL
```

and never use:

```text
Zippy invoice table ⇄ Odoo invoice table
```

as two competing masters.

---

## 6. Recommended typed Odoo capabilities

Expose narrow functions through your API/MCP/tool layer:

### Read

- `odoo_get_partner`
- `odoo_get_sale_order`
- `odoo_get_picking`
- `odoo_get_invoice`
- `odoo_get_payment_status`
- `odoo_get_open_receivable`

### Controlled write

- `odoo_upsert_partner`
- `odoo_create_sale_order`
- `odoo_confirm_sale_order`
- `odoo_validate_picking`
- `odoo_create_customer_invoice_draft`
- `odoo_create_vendor_bill_draft`
- `odoo_post_move_with_grant`
- `odoo_create_payment_with_grant`
- `odoo_reconcile_payment_with_grant`
- `odoo_create_credit_note_with_grant`

Do not expose:

- arbitrary SQL
- generic unrestricted `execute_kw`
- deleting journal entries
- modifying posted accounting records without governed reversal flows
- changing taxes, journals, accounts or financial policies through Hermes

---

## 7. Source-of-truth conflict rule

If systems disagree:

1. **Physical/operational state** → Zippy Operational DB wins.
2. **Financial/accounting state** → Odoo wins.
3. **Whether an agent was permitted to perform an action** → Paperclip wins.
4. **AI trace/tool telemetry** → Langfuse is evidence, not business truth.
5. **Memory/preferences** → Honcho is contextual only and can never override current Zippy/Odoo state.
