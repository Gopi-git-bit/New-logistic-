# M1 Staging Route Plan

## Status and Scope

**Task:** `M1-STAGING-ROUTE`
**Baseline:** `1af111cf78994f8c934d4d3229a54c40ece8a3db`
**Mode:** Read-only VPS discovery and documentation-only route design.

This plan records verified server facts and proposed future routing. It does not authorize Apache, ServerAvatar, DNS, TLS, firewall, port, service, container, environment, database, or deployment changes. It does not authorize live Razorpay, Odoo posting, settlements, refunds, Paperclip runtime activation, or WhatsApp integration.

## Controlling Decisions

- Preserve the existing ServerAvatar/Apache topology.
- MVP is one responsive same-origin web application for customers, vendors/drivers, and admins.
- Future API routing is under `/api`; the application enforces admin and resource access with server-side RBAC.
- PostgreSQL, Redis-like queues, internal workers, and future Paperclip remain private.
- Real-time updates use authenticated HTTP commands plus Server-Sent Events (SSE); browser location is consented, controlled, periodic, and only during active trips.
- Staging uses distinct data, database identity/role, payment evidence, and Odoo behavior. It never uses production data or live financial execution.

## Verified Current Topology

| Surface | Verified current fact | Confidence |
|---|---|---|
| Host | Ubuntu Linux host `srv1943844` | High |
| Public web server | Apache 2.4.58 service is active | High |
| Public listeners | Apache owns `80` and `443` | High |
| Production hosts | Apache vhosts serve `zippylogitech.com` and `www.zippylogitech.com`; an additional ServerAvatar alias exists | High |
| TLS | Valid Let's Encrypt ECDSA certificate covers `zippylogitech.com` and `www.zippylogitech.com` through 2026-12-01 | High |
| Current site type | ServerAvatar-managed Apache PHP/FastCGI site with HTTP Basic Auth; document-root paths are intentionally redacted | High |
| Current proxy routes | No `ProxyPass`, `ProxyPassMatch`, or `/api` route found in enabled site configuration | High |
| Apache capabilities | `proxy`, `proxy_fcgi`, `rewrite`, `headers`, `http2`, and `ssl` modules are loaded | High |
| Zippy API/frontend processes | No local listeners at `127.0.0.1:8000`, `127.0.0.1:3000`, or `127.0.0.1:3001`; no Uvicorn, Node app, Next.js, Vite, or Gunicorn Zippy process found | High |
| Current public endpoint status | `/`, `/api/`, and `/api/v1/health` return HTTP `403`, consistent with the active Basic Auth site rather than an API proxy | High |
| Containers | `docker ps` returned no running containers | High |
| Staging site/hostname | No Apache staging vhost or staging hostname reference found | High |
| Internal services | Host Redis is loopback-only; MySQL has listeners but is outside Zippy's approved architecture | High |
| ServerAvatar management | ServerAvatar agent has a listener; its management identity and private paths are not recorded | Medium |

## Evidence Table

| Command or inspection | Sanitized result | Confidence |
|---|---|---|
| `hostname`; `uname -a` | `srv1943844`; Ubuntu Linux kernel 6.8.0-139-generic | High |
| `systemctl is-active apache2`; `apache2ctl -v` | `active`; Apache 2.4.58 | High |
| `apache2ctl -S` | Port `80`/`443` production vhosts for `zippylogitech.com` and `www`; default localhost vhosts also exist | High |
| `apache2ctl -M` | Proxy, FastCGI proxy, headers, rewrite, HTTP/2, and SSL modules loaded | High |
| `ss -lntp` | Apache on public `80`/`443`; SSH on `22`; host Redis loopback-only `6379`; no local Zippy API/frontend listeners | High |
| `docker ps --format ...` | No running containers | High |
| Apache enabled-site listing and sanitized vhost reads | Four enabled sites; Zippy HTTP/HTTPS sites use PHP FastCGI, Basic Auth, and no reverse proxy target | High |
| `certbot certificates` | Valid certificate for production hostnames only; no staging certificate found | High |
| Status-only `curl` probes | Public root/API/health `403`; local API/frontend probes unavailable | High |
| Repository `docker-compose.yml` and proxy configuration | Development Compose publishes public/internal ports; repository Nginx routes `/api/` to portal rather than FastAPI | High |
| `grep` for staging site/hostname references | No staging host/site reference found in Apache configuration | High |

## Current Virtual Hosts, Listeners, and Routes

### Apache Virtual Hosts

| Listener | Current host coverage | Routing state |
|---|---|---|
| `*:80` | Default local vhost and production Zippy hostname aliases | Zippy site serves a ServerAvatar PHP/FastCGI document root; Basic Auth is configured; no `/api` proxy found |
| `*:443` | Default local TLS vhost and production Zippy hostname aliases | Same Zippy document root/PHP FastCGI behavior; TLS active; no `/api` proxy found |

Apache's `IncludeOptional` content may add site-local behavior, but the configured Zippy vhosts contain no discovered API reverse-proxy target. Future implementation must inspect the final rendered ServerAvatar vhost before any change; this plan does not infer an undeclared target.

### Listener and Service Matrix

| Port/surface | Current owner | Intended MVP disposition |
|---|---|---|
| `80`, `443` | Apache | Retain Apache as the only public HTTP/TLS entrypoint |
| `22` | SSH | Administration only; no routing change proposed |
| `6379` loopback | Host Redis | Do not expose; do not assume it is the MVP queue |
| `3306`, `33060` | Host MySQL | Not part of Zippy MVP; no change authorized |
| `8000`, `3000`, `3001` | No listener | Future app ports only, bound privately when separately approved |
| PostgreSQL | No verified Zippy PostgreSQL listener | Future MVP database remains private and separately isolated |

## Repository Versus Server Conflicts

| Conflict | Verified evidence | Planning consequence |
|---|---|---|
| Public listener conflict | Repository Compose publishes Nginx `80/443`, while Apache already owns public `80/443` | Future MVP must not start that Nginx service or bind application containers to public ports |
| API route conflict | Repository Nginx sends `/api/` to portal, but the owner-approved API is FastAPI | Future Apache route matrix must send `/api/` to the private FastAPI service, not a frontend container |
| Missing production Compose | Deployment workflow validates `docker-compose.production.yml`, which is absent | No deployment path is currently usable; staging-route design must precede any implementation |
| Invalid database init source | Compose mounts plain `supabase/migrations` as initdb source rather than `infra/supabase/migrations/` | Do not start existing Compose as an initialization mechanism |
| Current site behavior | Apache serves Basic-Auth PHP/FastCGI content and returns `403` for public root/API/health probes | Existing production hostname cannot be treated as a deployed MVP app or health route |
| Runtime absence | No Zippy containers, API/frontend processes, or local listeners | No health claim, proxy target, or deployment readiness can be inferred |
| Deployment root drift | A source checkout exists under Apache public content while the working repository is under `/opt` | A future release layout must keep source, secrets, and repository metadata outside the public document root |
| Supabase assumptions | API/workers and Compose expect Supabase/service-role paths, while approved MVP uses VPS PostgreSQL and no Supabase Cloud | The app/database contract must be reconciled before staging deployment |

## Proposed Staging Topology

**Status: PROPOSED — OWNER/DNS APPROVAL REQUIRED.** No staging hostname, Apache site, certificate, database, service, or route exists today.

1. Create one dedicated staging hostname under owner/DNS control, for example `staging.zippylogitech.com` only after explicit approval. This example is not an approved hostname.
2. Create a distinct ServerAvatar-managed Apache staging vhost and TLS certificate only after owner/infrastructure approval.
3. Deploy one responsive web application and FastAPI service to staging with separate release paths, service identities, logs, and configuration from production.
4. Keep all staging application processes on private loopback or a private container network. Apache is the only staging public HTTPS entrypoint.
5. Create a distinct staging PostgreSQL database and least-privilege database role. It must not share production data, credentials, volumes, backups, or migration-state ledger.
6. Use only Razorpay sandbox and/or manually recorded test payment evidence. Do not activate live keys, automatic refunds, settlements, Odoo posting, reconciliation, or financial execution.
7. Use a separate staging Odoo database or test-only boundary if Odoo is introduced later; initial MVP staging may validate only mocked/controlled external references until separately approved.
8. Keep Paperclip runtime, agents, Langfuse, Honcho, WhatsApp, Redis exposure, and unrelated host MySQL outside the staging route unless separately authorized.

## Proposed Production Topology

**Status: PROPOSED — OWNER/INFRASTRUCTURE APPROVAL REQUIRED.** This describes a later controlled rollout, not M1 implementation.

```text
Internet HTTPS
    |
Apache / ServerAvatar on 80 and 443
    |-- /              -> private responsive web application
    |-- /api/          -> private FastAPI application
    |-- /api/v1/events -> private FastAPI SSE endpoint
    |-- /api/v1/health -> private FastAPI liveness endpoint
    `-- static assets  -> frontend/static release path or frontend service

Private network / loopback only
    |-- PostgreSQL operational database
    |-- worker/outbox processes when approved
    |-- Odoo API boundary when approved
    `-- Paperclip governance database/service only when consequential agents are approved
```

### Future Routing Intent

| Public route | Private target/behavior | Access and cache policy |
|---|---|---|
| `/` | Responsive frontend entry application | Public entry only; authenticated areas enforce server-side RBAC |
| `/api/` | FastAPI API under the same origin | Authentication, authorization, idempotency, request size limits, correlation ID, and rate limits required |
| `/api/v1/health` | FastAPI liveness endpoint | Must not disclose secrets, database URLs, topology, or privileged health details |
| `/api/v1/ready` | FastAPI readiness endpoint | Restricted operational use or sanitized response; no dependency credentials/details |
| `/api/v1/events` | Authenticated SSE status stream for authorized trip/payment updates | No cache; disabled proxy buffering; long response timeout; reconnect requires renewed authentication/authorization and resumes only from an authorized event cursor |
| Static frontend assets | Versioned frontend/static release target | Cache immutable versioned assets; do not cache protected HTML/API/SSE responses |
| `/admin/...` | Frontend route only; backend verifies admin claims for every protected API action | No proxy-only authorization; server-side RBAC and audit are mandatory |

Suggested internal service ports are planning placeholders, not approved bindings: frontend `127.0.0.1:3000`; FastAPI `127.0.0.1:8000`; optional worker has no public listener; PostgreSQL and queues have no public listener. The specific process manager or container binding remains an implementation decision gated by an approved staging route.

## Proxy, TLS, and HTTP Requirements

### TLS and Hostnames

- Keep Apache/ServerAvatar as TLS termination until an approved replacement/cutover decision.
- Obtain a distinct certificate only after the approved staging DNS name resolves to the staging vhost.
- Configure an explicit hostname allowlist and application trusted-host policy for production and staging; do not accept arbitrary `Host` headers.
- Redirect HTTP to HTTPS only after testing the staging hostname and certificate flow.
- Preserve ACME `/.well-known` handling required by the current ServerAvatar configuration.

### Forwarded Headers, CORS, and Same-Origin

- Apache must set and preserve `Host`, `X-Forwarded-Proto`, `X-Forwarded-For`, and a trusted proxy address contract to the FastAPI service.
- FastAPI may trust forwarded headers only from its approved local Apache proxy, never from arbitrary clients.
- Same-origin frontend/API routing is the default; CORS should be disabled or limited to the exact approved staging/production origins, never wildcard credentials.
- The existing Basic Auth site must not be silently reused as application authorization; application authentication/RBAC remains independent and server-enforced.

### SSE Requirements

- For `/api/v1/events`, disable Apache proxy buffering and response transformation/compression that delays events.
- Set a bounded but sufficiently long proxy timeout and keepalive policy appropriate for SSE; define an operational disconnect/reconnect test before release.
- Require authenticated reconnects and re-authorize the requested trip/payment stream each time.
- Send no-cache headers and avoid intermediary caching. Do not send credentials, raw model reasoning, payment data, or unrelated participant location data in event payloads.
- Use event IDs/cursors, heartbeats, rate limits, connection limits, and backpressure/slow-client handling in the future API contract.

## Data, Upload, Rate-Limit, and Logging Requirements

### Staging Data Isolation

- Use an independently created staging database/database role, separate credentials, storage, migration ledger, backups, and test data.
- Never route staging to production PostgreSQL, production Odoo data, production Paperclip data, or live payment credentials.
- Use sanitized fixtures only. Legacy seed files contain production-like fields and are not staging data authorization.

### Upload and Body Size

- Define explicit Apache and FastAPI request-body limits before enabling vehicle-registration documents or POD uploads.
- Restrict MIME type, filename, image/PDF dimensions, decompression behavior, malware scanning policy, object-storage path authorization, and per-user upload rate/size limits.
- Store document metadata and verification evidence separately from binaries; do not make a browser-provided file or OCR output financial proof.

### Rate Limits

- Limit public registration, authentication, booking, vehicle registration, upload, webhook, and SSE connection/reconnect routes separately.
- Scope limits by authenticated account, IP/device where appropriate, API/service identity, and endpoint sensitivity.
- Keep webhook verification and idempotency ahead of consequential processing. A limit or error must not cause duplicate payment or refund behavior.

### Logging and Correlation

- Propagate a generated or validated correlation ID from Apache/API through order, trip, payment evidence, Odoo references, exceptions, and approved future governance records.
- Log route, status, latency, authorization outcome, idempotency result, and redacted error category; exclude credentials, authorization headers, database URLs, private document content, raw payment payloads, and raw model reasoning.
- Keep authoritative operational audit events separate from future Langfuse observability. No logging system becomes a business source of truth.

## Deployment Order and Acceptance Tests

Every step below requires a reviewed plan and explicit owner/infrastructure authorization. None is authorized by this document.

1. Approve staging hostname, DNS, ServerAvatar application/release layout, private port bindings, and rollback owner.
2. Approve canonical migration manifest and M2 initialization/rollback requirements before creating any staging database.
3. Provision isolated staging database/service identities and run only approved staging migration/verification evidence.
4. Deploy responsive frontend and FastAPI to private targets; do not expose a port directly to the internet.
5. Configure/test the Apache staging vhost, TLS, same-origin `/api`, health/readiness route, static assets, trusted headers, CORS, request-size limits, and SSE behavior.
6. Run authenticated contract checks for customer, vendor/driver, and admin RBAC; test forbidden cross-party trip/payment access and blocked-account behavior.
7. Run sandbox/manual payment evidence and draft/read-only Odoo boundary tests. Verify no automatic posting, settlement, reconciliation, or refund action occurs.
8. Prove failure behavior: unavailable API target, invalid forwarded host, expired/rejected session, stale location, slow SSE consumer, duplicate webhook, timeout-after-success, and rollback.
9. Obtain review evidence and owner authorization before any production routing or traffic change.

## Rollback Procedure

Future routing changes require a pre-approved rollback plan. At minimum:

1. Stop promotion and preserve redacted logs, correlation IDs, configuration revision, and health evidence.
2. Restore the previously approved Apache vhost/release mapping through ServerAvatar/Apache owner procedures; do not improvise edits.
3. Disable only the new staging/proxy target while keeping Apache public listeners unchanged.
4. Revoke affected staging service credentials/sessions if exposure is suspected; do not expose or copy secret values into incident records.
5. Keep database recovery separate: use only the approved staging backup/disposable-environment procedure, never production data.
6. Record the outcome and keep production traffic on the last known approved route.

## Approval Gates

Explicit owner/infrastructure approval is required before each of the following:

- Any staging DNS hostname, Apache vhost, TLS certificate, ServerAvatar application setting, document-root change, proxy directive, service process, container, or port binding.
- Any staging database, role, credential, volume, migration, seed, restore, or backup.
- Trusted proxy/host/CORS policy, SSE endpoint name/timeout/buffering configuration, request-size limit, object storage, or rate-limit value.
- Razorpay sandbox setup, live payment activation, Odoo connection, Odoo custom module, Paperclip runtime, agent activation, WhatsApp integration, or public webhook exposure.
- Any production traffic, source/release-path change, firewall change, DNS cutover, or Apache reload/restart.

## Completion Assessment

Read-only topology evidence is sufficient to document a safe staging-only route design. The plan identifies Apache as the current public boundary, confirms there is no deployed Zippy target or staging hostname, and supplies an approval-gated same-origin routing contract. It does not resolve implementation authorization, current Basic Auth behavior, migration safety, backup policy, or production readiness.
