# Zippy Logistics — API Reliability & Security Contract

> Mandatory for all API interactions. Every agent, service, and integration MUST comply.

---

## 1. API Contract Layers

```
API CONTRACT
│
├── Functional Contract
│   endpoints / schemas / responses
│
├── Governance Contract
│   Paperclip / HITL / permissions
│
├── Reliability Contract
│   retries / timeout / rate limiting / idempotency
│
└── Security Contract
    authentication / authorization / token lifecycle
    encryption / secret management / auditing
```

---

## 2. Idempotency

### Mandatory Operations

Idempotency is **required** for all state-changing POST/PATCH operations involving:

- Booking creation
- Assignment / provider selection
- Invoice creation
- Payment intent
- Settlement
- Order transition
- External provider calls (Odoo, Razorpay, Stripe)

### Required Header

```
Idempotency-Key: <uuid>
```

### Server Storage

| Field | Purpose |
|-------|---------|
| `idempotency_key` | Unique request identifier |
| `request_hash` | Payload fingerprint for conflict detection |
| `operation_status` | pending / completed / failed |
| `response_code` | HTTP status of original execution |
| `response_body` / `reference` | Cached result |
| `created_at` | Timestamp |
| `expires_at` | TTL (default: 24 hours) |

### Behavior

- **Repeated identical request** → return previous result, DO NOT execute again
- **Same key + different payload** → return `409 IDEMPOTENCY_CONFLICT`

### Database Implementation

```sql
-- Already implemented in agent_tasks table
UNIQUE constraint on dedupe_key
-- enqueue_agent_task() handles deduplication
```

---

## 3. Required Headers

### Standard Headers (All Requests)

```http
Authorization: Bearer <token>
Idempotency-Key: <uuid>
X-Correlation-ID: <workflow-id>
X-Request-Timestamp: <ISO-8601>
```

### Agent-Specific Headers

```http
X-Agent-ID: <agent-id>
X-Decision-ID: <paperclip-decision-id>
```

### Header Requirements

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Always | JWT or service token |
| `Idempotency-Key` | State-changing ops | UUID v4 |
| `X-Correlation-ID` | Always | Workflow/trace ID for observability |
| `X-Agent-ID` | Agent calls | Identifies calling agent |
| `X-Decision-ID` | Paperclip-approved actions | **Mandatory** for actions requiring governance approval |
| `X-Request-Timestamp` | Always | ISO-8601 with timezone |

### Governance Enforcement

> `X-Decision-ID` becomes **mandatory** for actions requiring Paperclip approval.

This directly reinforces the governance model:
1. Hermes proposes
2. Paperclip approves
3. Only then does Zippy or Odoo execute

---

## 4. Retry Policy

### Retry Allowed

| Status Code | Condition |
|-------------|-----------|
| `408` | Request Timeout |
| `425` | Too Early |
| `429` | Too Many Requests |
| `500` | Internal Server Error |
| `502` | Bad Gateway |
| `503` | Service Unavailable |
| `504` | Gateway Timeout |
| — | Network timeout / connection reset |

### Do NOT Auto-Retry

| Status Code | Reason |
|-------------|--------|
| `400` | Bad Request |
| `401` | Unauthorized (refresh token first) |
| `403` | Forbidden |
| `404` | Not Found |
| `409` | Business conflict |
| `422` | Validation Error |
| — | Governance rejection |
| — | Payment rejection |

### Backoff Strategy

Exponential backoff with jitter:

```
attempt 1 → ~1 second
attempt 2 → ~2 seconds
attempt 3 → ~4 seconds
attempt 4 → ~8 seconds
attempt 5 → ~16 seconds
```

**Respect `Retry-After` header whenever supplied.**

### Critical Rule

> **Never retry a state-changing request unless it is protected by an idempotency key.**

This is especially important for:
- Odoo invoices
- Payment processing
- Driver assignments
- Booking creation

---

## 5. Rate Limiting

### Two Levels

#### Global Limit
Protects the API/server itself.

#### Per-Principal Limit
Scoped by identity type:

| Principal | Scope |
|-----------|-------|
| Customer | Per user |
| Driver | Per user |
| Internal service | Per service |
| Agent | Per agent identity |
| Integration | Per external system |
| IP/device | Where appropriate |

### Response Headers

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 15
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: <timestamp>
```

### Agent Behavior

Hermes/Composio must:
1. Read `Retry-After` header
2. Pause that capability
3. Retry later
4. **Never** blindly hammer the service

---

## 6. Authentication & Authorization

### Identity Separation

| Identity | Auth Method | Scope |
|----------|-------------|-------|
| Human users | JWT/OAuth session | Full user capabilities |
| Flutter/mobile | Short-lived access + refresh token | User-scoped |
| Internal Zippy services | Service identity | Service-specific |
| Hermes | Dedicated agent identity | Narrowly scoped capabilities |
| Paperclip | Separate governance identity | Approval/rejection only |
| Odoo connector | Isolated integration credential | ERP operations only |
| External integrations | Separate scoped credentials | Per-integration scope |

### Critical Rule

> **Do NOT give Hermes a shared administrator credential.**

Hermes should only get narrowly scoped capabilities — never database/Odoo/Paperclip admin rights.

---

## 7. Token Lifecycle

### Token Types

| Token | Lifetime | Rotation |
|-------|----------|----------|
| Access Token | 5–15 minutes | Rotated on refresh |
| Refresh Token | Longer (e.g., 7 days) | Rotatable, revocable |
| Service Token | Scoped to exact capabilities | Auto-rotated |

### Token Operations

| Operation | Action |
|-----------|--------|
| On token refresh | Invalidate/rotate old refresh token |
| On suspected compromise | Revoke credential, rotate secret, terminate affected sessions, audit event |

### Prohibited

❌ Tokens in query strings
❌ Secrets committed to Git
❌ Service-role keys in Flutter/browser
❌ Tokens inside Langfuse prompts/traces
❌ Plaintext credentials in Paperclip/Honcho
❌ One shared API key for all agents

---

## 8. Encryption

### In Transit

| Requirement | Standard |
|-------------|----------|
| Minimum | TLS 1.2+ |
| Preferred | TLS 1.3 |
| Protocol | HTTPS only |

### At Rest

| Data | Protection |
|------|------------|
| Database/storage | Encryption enabled |
| Secrets | Encrypted secret manager / environment secret store |
| High-sensitivity fields | Application-level encryption |
| Backups | Encrypted |

### Logging

> Credentials, tokens, and payment secrets MUST be redacted in all logs.

---

## 9. Credential Isolation

Each system maintains separate credentials:

```
Zippy DB credentials
≠ Paperclip DB credentials
≠ Odoo DB credentials
≠ Langfuse credentials
≠ Honcho credentials
```

> A compromise in one system should NOT automatically grant access to another.

---

## 10. Standard Error Envelope

Every API response must use this format:

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Request rate exceeded.",
    "retryable": true,
    "retry_after_seconds": 15,
    "correlation_id": "wf_123456"
  }
}
```

### Error Code Categories

| Category | retryable | Agent Action |
|----------|-----------|--------------|
| `RATE_LIMIT_EXCEEDED` | true | Wait, retry later |
| `IDEMPOTENCY_CONFLICT` | false | Abort, check payload |
| `AUTHENTICATION_FAILED` | false | Refresh credentials |
| `AUTHORIZATION_DENIED` | false | Escalate to HITL |
| `VALIDATION_ERROR` | false | Correct request |
| `GOVERNANCE_REJECTION` | false | Escalate to HITL |
| `PAYMENT_REJECTED` | false | Escalate to HITL |
| `SERVICE_UNAVAILABLE` | true | Retry with backoff |
| `INTERNAL_ERROR` | true | Retry, then escalate |

### Agent Decision Matrix

The error envelope allows autonomous agents to deterministically decide:

| Action | Condition |
|--------|-----------|
| Retry | `retryable: true` + idempotency key present |
| Stop | `retryable: false` |
| Escalate to HITL | Governance/payment/auth errors |
| Refresh credentials | `AUTHENTICATION_FAILED` |
| Correct request | `VALIDATION_ERROR` |

---

## 11. Implementation Checklist

- [ ] All state-changing endpoints accept `Idempotency-Key` header
- [ ] Server stores idempotency results with 24h TTL
- [ ] All responses include `X-Correlation-ID`
- [ ] Paperclip-approved actions require `X-Decision-ID`
- [ ] Retry logic implements exponential backoff with jitter
- [ ] Rate limiting returns standard headers
- [ ] Each service has isolated credentials
- [ ] Tokens never appear in logs or query strings
- [ ] All errors use standard envelope format
- [ ] Agent error handler reads `retryable` field deterministically
