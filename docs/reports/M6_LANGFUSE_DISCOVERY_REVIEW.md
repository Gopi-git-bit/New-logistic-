# M6-LANGFUSE Discovery and Boundary Review

**Status:** `DISCOVERY COMPLETE — OWNER BOUNDARY APPROVAL REQUIRED`

**Baseline commit:** `d2b3e837e66f6995379aac3333d5130ce618d59e` (`docs: accept M5 and begin M6 discovery`)

**Discovery date:** 2026-09-27

**Scope:** Read-only repository inspection and official Langfuse documentation review. No implementation, dependency installation, credential configuration, container start, telemetry export, external request, deployment, staging, commit, or push occurred.

---

## 1. Preflight Result

All preflight checks passed:

| Check | Result |
|---|---|
| Repository | `/opt/new-logistic` |
| Branch | `master` |
| Worktree/index | clean |
| Local HEAD | `d2b3e837e66f6995379aac3333d5130ce618d59e` |
| `origin/master` | identical to HEAD |
| Remote `master` | identical to HEAD |
| Latest commit subject | `docs: accept M5 and begin M6 discovery` |
| Author | `Gopinathan <gopinathdisp@gmail.com>` |
| D-30 | exists exactly once in `docs/DECISIONS.md` |
| M5-E012 | exists exactly once as an evidence record in `docs/TEST_EVIDENCE.md` |
| `M5-PAPERCLIP` | `COMPLETE` |
| `M6-LANGFUSE` | sole `IN_PROGRESS` task; discovery and boundary definition only |
| M6 implementation | explicitly unbegun |
| Deployment workflow | disabled: `if: ${{ false }}` in `.github/workflows/deploy-hostinger.yml` |
| `/opt/paperclip` | untouched; no modifications |

---

## 2. Repository Inventory

### 2.1 Existing observability references

| Term | Source files (excl. deps/docs) | Notes |
|---|---|---|
| `langfuse` | `workers/src/zippy_workers/config.py`, `workers/src/zippy_workers/tracing.py`, `workers/pyproject.toml`, `.env.example`, `.env.production.example`, `docker-compose.yml` | Langfuse SDK and config already declared for workers; no runtime tests. |
| `telemetry` | `workers/src/zippy_workers/capabilities.py` (domain name), docs/migrations | No application telemetry pipeline exists. |
| `trace` / `span` / `observation` | `workers/src/zippy_workers/tracing.py`, `api/main.py` (correlation id), docs | Only `tracing.py` implements spans; no tests. |
| `prompt` / `completion` / `token` / `cost` | `workers/src/zippy_workers/tracing.py` (metadata only), docs/PRDs | No prompt/response/token capture implemented. |
| `OpenTelemetry` / `OTEL` | `docs/HEARTBEAT.md` (legacy claim) only | No OTEL SDK or collector present. |
| `Sentry` | `workers/pyproject.toml` only | Declared dependency; no Sentry initialization. |
| `Prometheus` / `Grafana` | none | No infrastructure metrics stack present. |
| `logging` / `logger` / `loguru` | `workers/src/zippy_workers/main.py` (structlog), `api/config.py`, `api/main.py`, `api/gateway.py` | structlog in workers; no logging telemetry export. |
| `redact` | `api/redaction.py`, `api/tests/test_output_redaction.py`, `api/tests/test_config_redaction.py`, `api/tests_m5/test_service.py` | Secret redaction exists for logs/errors; not wired to telemetry export. |

### 2.2 Existing code that would be in scope for M6

| File | Current role | M6 relevance |
|---|---|---|
| `workers/src/zippy_workers/tracing.py` | Minimal Langfuse span emitter with offline no-op fallback | Core telemetry client; needs redaction, masking, tenant pseudonymization, and test coverage. |
| `workers/src/zippy_workers/config.py` | Worker settings including optional Langfuse keys | Configuration boundary; keys are optional, defaults to Langfuse Cloud US. |
| `workers/src/zippy_workers/main.py` | Worker CLI entry point | Would initialize telemetry (disabled by default). |
| `workers/src/zippy_workers/kernel.py` | Heartbeat task kernel | Would emit traces around task claim/execute/complete. |
| `workers/src/zippy_workers/executor.py` | Tool execution wrapper | Would emit spans around tool invocations, guardian verdicts, and outcomes. |
| `workers/src/zippy_workers/loop_guardian.py` | Loop/budget/hallucination guard | Would emit spans around guardian decisions. |
| `workers/src/zippy_workers/handlers.py` | Business handlers (M4/M5/M6) | Would emit spans around external calls (Odoo, Razorpay, etc.) with redaction. |
| `workers/src/zippy_workers/capabilities.py` | Capability matrix | Defines which agents may call external services; telemetry must respect this boundary. |
| `api/main.py` | FastAPI application | Would propagate trace/correlation IDs; no telemetry SDK present. |
| `api/redaction.py` | Secret redaction utilities | Would be reused/extended for telemetry redaction. |
| `workers/pyproject.toml` | Worker dependencies | Already includes `langfuse>=2.55.0` and `sentry-sdk>=2.19.0`. |
| `.env.example` | Environment template | Already documents `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`. |
| `.env.production.example` | Production environment template | Same Langfuse variables; no additional controls. |
| `docker-compose.yml` | Local orchestration | Passes Langfuse env vars to `workers` service only. |
| `.github/workflows/ci.yml` | CI pipeline | No telemetry-specific checks; security scan exists. |

### 2.3 Existing tests

| Test file | Relevance |
|---|---|
| `api/tests/test_output_redaction.py` | Proves HTTP/error output redaction; would inform telemetry redaction proof. |
| `api/tests/test_config_redaction.py` | Proves `Settings` repr excludes secrets; would inform telemetry-safe config handling. |
| `workers/tests/test_m6_handlers.py` | M6 handler logic tests; no telemetry coverage. |
| No `test_tracing.py` | Confirmed gap. |

---

## 3. External Facts (Official Langfuse Documentation)

Source: `https://langfuse.com/docs`, `https://langfuse.com/self-hosting`, `https://langfuse.com/docs/observability/features/masking`, `https://langfuse.com/docs/administration/data-retention` (retrieved 2026-09-27).

| Topic | Official fact |
|---|---|
| Deployment models | Langfuse Cloud (managed SaaS, multi-tenant, US/EU/Japan/HIPAA regions); Self-hosted OSS (Docker/Kubernetes); Self-hosted Enterprise Edition. |
| Self-host components | Langfuse Web, Langfuse Worker, PostgreSQL (OLTP), ClickHouse (OLAP), Redis/Valkey (cache/queue), S3-compatible blob storage. |
| Self-host minimum VM | 4 cores, 16 GiB RAM, 100 GiB storage recommended for VM deployment. |
| Self-host network | Internet access optional; can run air-gapped in VPC/on-premises. Default Docker Compose exposes UI on port 3000 and MinIO on 9090. |
| Authentication | No built-in default admin; first user created via UI or headless initialization. SSO/SCIM is Enterprise Edition. |
| Data masking | Python SDK supports `mask_otel_spans` (recommended) and legacy `mask` hooks. Can redact/replace OpenTelemetry span attributes before export. If masking raises or returns invalid result, the export batch is dropped. |
| Data retention | Minimum 3 days on Cloud Pro/Enterprise. Self-hosted OSS stores data indefinitely by default; retention feature requires Enterprise Edition. |
| Prompt/response storage | Langfuse traces can capture inputs/outputs by default unless masked or deleted. |
| OpenTelemetry | Langfuse accepts OTLP traces and provides OpenTelemetry-compatible SDK span processors. |
| Cost | Langfuse Cloud has Hobby/Core/Pro/Enterprise tiers. Self-hosted OSS has infrastructure cost only; Enterprise Edition is licensed. |
| Compliance | Langfuse Cloud is SOC 2 Type II and ISO 27001 audited; GDPR compliant; DPA available; HIPAA-ready region available. |

---

## 4. Existing Observability State

- **Workers:** `tracing.py` is a hand-rolled minimal Langfuse HTTP client that emits spans when `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are both present. It has no redaction, no tenant pseudonymization, no tests, and silently swallows all export exceptions (fail-open). It uses `heartbeat_id` as trace root.
- **API:** No Langfuse or OpenTelemetry SDK. Correlation IDs are generated server-side and returned in headers.
- **Frontend:** No observability SDK references.
- **Sentry:** Declared as a dependency but not initialized.
- **Prometheus/Grafana:** Absent.
- **Redaction:** Exists for logs/error output but is not integrated with telemetry export.
- **Tests:** No telemetry-specific tests.

### Confirmed Gaps

1. No redaction before telemetry export.
2. No tenant-safe pseudonymous identifiers in traces.
3. No classification of which fields may/cannot be exported.
4. No prompt/response body policy.
5. No trace/span test coverage.
6. No fail-closed behavior on redaction uncertainty.
7. No sampling, cost ceiling, or retention controls.
8. No separation of dev/test/staging/production telemetry projects.
9. No health check or bounded retry strategy for Langfuse export.
10. No duplicate-event handling or idempotency for telemetry.
11. No documented procedure for credential rotation or incident response.
12. No Prometheus/Grafana/Sentry integration plan.

---

## 5. Proposed Trust Boundary

### 5.1 Architecture options

| Option | Recommendation | Rationale |
|---|---|---|
| **Langfuse Cloud** | Possible for dev/staging evaluation only if owner approves | Fastest start, managed infrastructure, but sends telemetry outside Hostinger VPC. Requires DPA and region decision for any PII/pseudonymized data. |
| **Isolated self-host on Hostinger** | **Recommended for production** | Keeps observability data within the same VPC as Zippy; aligns with existing self-hosted PostgreSQL/Redis/Odoo pattern; avoids third-party data residency questions for sensitive pseudonymized data. |

### 5.2 Required self-host components (if selected)

Langfuse self-hosting requires its **own** PostgreSQL database, ClickHouse, Redis/Valkey, and S3-compatible blob storage. These must **not** share the Zippy operational database or the Paperclip governance database.

### 5.3 Network boundary

- Langfuse Web UI must not be exposed to the public internet without authentication/SSO.
- Workers and FastAPI services emit traces via internal network only.
- No browser/client-side telemetry.
- Langfuse does **not** accept commands from external clients to mutate Zippy, Paperclip, or Odoo state.

### 5.4 Allowed producers

- `workers` service only (initially).
- FastAPI API later if owner approves.
- No frontend producers.

### 5.5 Development / test / staging / production separation

| Environment | Recommended telemetry target |
|---|---|
| Local dev | Disabled by default; optional local Langfuse Docker Compose (disposable). |
| Unit/integration tests | Synthetic in-memory telemetry sink only; no network calls. |
| Staging | Separate Langfuse project or separate self-hosted instance. |
| Production | Separate Langfuse project or separate self-hosted instance; disabled until explicit owner approval. |

---

## 6. Data Classification Matrix

Default: **prohibit** secrets, credentials, raw payment/accounting data, and unnecessary personal data.

| Data category | Classification | Export rule |
|---|---|---|
| System prompts | Restricted | May export only if owner explicitly approves prompt storage; otherwise mask/delete. |
| Model prompts and responses | Restricted | May export only if owner approves and redaction passes; default is **prohibited**. |
| Tenant identifiers | Sensitive | Pseudonymize to server-generated stable hash; never export raw tenant UUID/name. |
| User identifiers (customer, driver, vehicle owner) | Sensitive | Pseudonymize; never export email/phone/name. |
| Order / trip / vehicle / driver data | Sensitive | Aggregate or pseudonymize; no raw addresses, cargo details, or live route data. |
| Customer / consignee data | Prohibited | No names, emails, phone numbers, addresses. |
| Payment / refund / settlement data | Prohibited | No amounts, transaction IDs, Razorpay/Stripe IDs, bank details. |
| Odoo / accounting data | Prohibited | No invoice IDs, ledger entries, partner IDs, sale order IDs. |
| Access tokens / JWTs / API keys / DB URLs / webhook secrets | Prohibited | Never emit; redaction must fail-closed if uncertainty. |
| Policy checksums / payload hashes / governance grants / denial reasons | Restricted | Grant IDs and decision statuses may export; raw payload hashes only if non-reversible. |
| Audit identifiers | Permitted | Trace/correlation IDs, span IDs, timestamps, outcome status. |
| Exception messages and stack traces | Restricted | May export type name and sanitized message only; no raw env/secret leakage. |
| Token usage / latency / cost / model name / confidence / outcome | Permitted | Core observability metrics; no raw content. |

---

## 7. Responsibility Matrix

| Concern | Proposed owner | Notes |
|---|---|---|
| LLM traces, prompts, token usage, evaluation | **Langfuse** | Under approved data classification; masked/redacted before export. |
| Infrastructure and service metrics | **Prometheus/Grafana** | Not in M6 scope; recommend future milestone. |
| Application exceptions and stack traces | **Sentry** | Not in M6 scope; dependency already declared. |
| Durable business workflow state | **Zippy PostgreSQL** | Source of truth remains Zippy DB. |
| Governance decisions and grants | **Paperclip** | Langfuse must not become authority over Paperclip. |
| Financial and accounting records | **Odoo** | No financial data in telemetry. |
| Trace/correlation ID generation | **Zippy server** | Server-generated; clients may not select trace IDs. |
| Redaction before export | **Zippy application code** | Must run before any data leaves the process. |

---

## 8. Security and Reliability Recommendations

### 8.1 Redaction

- Reuse/extend `api/redaction.py` patterns in a new `workers/src/zippy_workers/telemetry_redaction.py` module.
- Apply redaction **before** calling `Langfuse` SDK or HTTP ingestion.
- Fail-closed: if redaction cannot classify a value as safe, drop the affected span/attribute, not the business operation.

### 8.2 Identity

- Generate trace IDs server-side (`uuid4` or similar).
- Map tenant/user identifiers to opaque pseudonyms using HMAC-SHA256 with a server-side pepper.
- Never use client-provided `trace_id` or `user_id` directly.

### 8.3 Least privilege

- Use project-scoped Langfuse public/secret keys.
- Separate keys per environment.
- Rotate keys on compromise and quarterly.

### 8.4 Transport

- TLS 1.2+ for all telemetry traffic.
- For self-hosted, keep Langfuse inside the same Docker network or VPC.

### 8.5 Retention and deletion

- Self-hosted OSS default is indefinite; owner must decide retention and deletion procedure.
- If Cloud is used, configure minimum viable retention and deletion.
- Backups of Langfuse data must be separate from Zippy operational backups.

### 8.6 Sampling and cost

- Default sampling to 0% (disabled); enable only with owner approval.
- Implement configurable sample rate and monthly event/cost ceiling.
- Exceeding ceiling disables export (not business operations).

### 8.7 Health, retries, backpressure

- Bounded retries (e.g., 3 attempts with exponential backoff).
- Circuit breaker or disable-on-repeated-failure.
- Export timeouts (e.g., 3s as currently used).
- Telemetry failures must never block task execution.

### 8.8 Duplicate handling

- Generate deterministic span/observation IDs from task id + step index where applicable.
- Langfuse ingestion is idempotent on `id`.

### 8.9 Telemetry outage behavior

- Fail-open for telemetry export (drop spans).
- Fail-closed for redaction uncertainty (drop span, not business outcome).

### 8.10 Authority prevention

- Langfuse is append-only evidence.
- No Langfuse callback/webhook may modify Zippy, Paperclip, or Odoo state.
- Telemetry code must not query Langfuse to make business decisions.

---

## 9. Threat and Failure Analysis

| Threat | Mitigation |
|---|---|
| Secret leak via telemetry | Redaction before export; fail-closed on uncertainty; secret scan in CI. |
| PII leak via prompts/responses | Default prohibition on prompt/response export; masking if owner approves. |
| Telemetry becomes business authority | Read-only traces; no Langfuse-driven decisions. |
| Tenant isolation breakdown | Pseudonymize tenant IDs; separate projects per environment. |
| Cost overrun | Sampling + monthly ceiling + disable switch. |
| Langfuse outage degrades Zippy | Fail-open export; no synchronous blocking. |
| Redaction failure silently exports secrets | Fail-closed: drop affected span and log alert. |
| Credential compromise | Least-privilege project keys; rotation procedure. |
| Data residency violation | Self-host on Hostinger or select Cloud region with DPA. |
| Retention policy absent | Owner-defined retention + deletion runbook. |

---

## 10. Proposed Disposable M6 Proof

Design only; not executed.

A disposable M6 proof would:

1. Stand up a network-isolated, socket-only, SCRAM-authenticated PostgreSQL container (same pattern as M5-A).
2. Start a disposable Langfuse self-hosted container or use a synthetic Langfuse HTTP sink.
3. Run worker tests with:
   - telemetry disabled by default;
   - synthetic data only;
   - redaction before export;
   - secrets never emitted;
   - tenant identifiers pseudonymized;
   - no raw financial, Odoo, payment, refund, or personal data;
   - unavailable Langfuse does not corrupt or falsely succeed business operations;
   - redaction uncertainty blocks the affected telemetry export;
   - retry limits and duplicate handling verified;
   - trace correlation without client-selected authority;
   - no direct writes to Zippy, Paperclip, or Odoo databases;
   - complete disposable cleanup verified.

Markers would include: `telemetry_disabled_by_default=PASS`, `redaction_before_export=PASS`, `secret_scan=PASS`, `pseudonymized_tenant=PASS`, `no_financial_data=PASS`, `fail_open_on_export_error=PASS`, `fail_closed_on_redaction_error=PASS`, `bounded_retries=PASS`, `duplicate_handling=PASS`, `cleanup=PASS`.

---

## 11. Owner Decisions Required Before Implementation

| Decision | Recommended Minimal MVP choice |
|---|---|
| Cloud or isolated self-hosted Langfuse | **Isolated self-host on Hostinger** for production; Langfuse Cloud acceptable only for dev evaluation with owner approval. |
| Permitted telemetry fields | Audit identifiers, token usage, latency, cost, model name, confidence, outcome status, agent/task type, guardian verdict. |
| Prohibited fields | Secrets, credentials, JWTs, DB URLs, payment data, refund data, settlement data, Odoo IDs, raw personal data, raw addresses, raw prompts/responses unless separately approved. |
| Retention period | **30 days** for event traces; indefinite for dataset items only if explicitly saved. |
| Regional / data-residency requirement | **India/Hostinger VPC** for production; EU Cloud region only if DPA signed. |
| Sampling percentage | **0% disabled by default**; opt-in per-environment with owner approval. |
| Monthly cost ceiling | **₹0 for disabled state**; define ceiling before enabling any sampling. |
| Administrator identity | Owner-designated administrator for Langfuse UI/keys. |
| Prompt/response bodies stored | **No** by default; opt-in with separate owner approval and masking rules. |
| Fail-open vs. fail-closed | **Telemetry export fail-open; redaction uncertainty fail-closed.** |
| Which services may emit traces | `workers` only initially; FastAPI later if approved. |
| Production telemetry during M6 | **Prohibited.** M6 is discovery and staging-only boundary definition. |
| Deletion and incident-response procedures | Document key rotation, retention deletion, and secret-leak response before enabling any export. |

These are recommendations, not approved decisions.

---

## 12. Explicit Prohibitions

Until an owner-approved M6 implementation scope is recorded:

- Do not install or run Langfuse, ClickHouse, Redis, MinIO, or any Langfuse dependency.
- Do not add or modify dependencies in `workers/pyproject.toml`, `package.json`, or any lock file.
- Do not configure, generate, or rotate Langfuse credentials.
- Do not start containers or modify `docker-compose.yml`.
- Do not export telemetry to Langfuse Cloud or any external service.
- Do not instrument FastAPI, workers, or frontend with live telemetry.
- Do not modify `docs/EXECUTION_TRACKER.md` or `docs/HEARTBEAT.md` during this discovery pass.
- Do not modify Zippy, Paperclip, or Odoo runtime code.
- Do not modify `/opt/paperclip`.
- Do not stage, commit, push, or deploy.

---

## 13. Prospective Implementation File Inventory

If owner approval is granted, the following files are prospective targets (no changes made):

| File | Expected change |
|---|---|
| `workers/src/zippy_workers/tracing.py` | Replace hand-rolled client with redacting Langfuse SDK client or extend with redaction layer; add tests. |
| `workers/src/zippy_workers/telemetry_redaction.py` | New module: classify and redact telemetry payloads before export. |
| `workers/src/zippy_workers/config.py` | Add telemetry enable/disable, sample rate, cost ceiling, environment project. |
| `workers/src/zippy_workers/main.py` | Initialize telemetry only when explicitly enabled. |
| `workers/src/zippy_workers/kernel.py` | Emit trace per task with pseudonymized IDs. |
| `workers/src/zippy_workers/executor.py` | Emit span per tool invocation with guardian verdict and outcome. |
| `workers/src/zippy_workers/handlers.py` | Emit spans around external calls with redacted metadata. |
| `workers/tests/test_tracing.py` | New tests for redaction, masking, fail-open/fail-closed, duplicate handling. |
| `.env.example` | Add telemetry enable/disable and project variables. |
| `docker-compose.yml` | Add optional Langfuse self-host services only if approved. |

---

## 14. Evidence

- `M6-E001: Langfuse Discovery and Boundary Review` appended to `docs/TEST_EVIDENCE.md`.

---

## 15. Conclusion

M6-LANGFUSE discovery is complete. The repository already declares Langfuse as a worker dependency and includes a minimal fail-open span emitter, but lacks redaction, tenant pseudonymization, classification, tests, and production controls. The recommended boundary is an isolated self-hosted Langfuse instance on Hostinger with telemetry disabled by default, workers-only emission, strict redaction before export, and separate environments. All implementation decisions remain pending owner approval.
