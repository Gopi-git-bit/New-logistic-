# Isolated OMS Recommendation Bridge

## Implemented development boundary

Authority: D-39. Base: PR #9 reviewed head
`70c372fdd1f1328eb09a4175f028d4a7755fa77d`.

The [adapter](../../workers/src/zippy_workers/recommendation_provider.py) implements
the existing `RecommendationAgent.rank` protocol using OpenAI-compatible chat
completions. The [standalone runner](../../workers/scripts/run_oms_recommendation.py)
uses three fixed synthetic distance/score fixtures, preserves existing shortlist
order and validates output through `recommend_drivers`. It does not rerun the SQL
matcher, prove operational eligibility or assign anything. Recommendations remain
advisory; acceptance in the separate fake review contract grants no authority.

The existing fake-only shadow/review restrictions are unchanged. No normal API,
worker entry point or registry imports the adapter/runner. Nothing instantiates
telemetry or the legacy tracer. M6 development acceptance and existing evidence
are reused; deployed/live gates are not upgraded to PASS.

## Required configuration

All five names must be supplied explicitly in the dedicated process environment:

| Name | Requirement |
|---|---|
| `OMS_STAGING_ENDPOINT` | Exact full HTTPS chat-completions endpoint, including path; <=2048 characters; no userinfo, query or fragment; no default |
| `OMS_STAGING_API_KEY` | Dedicated provider-only staging credential; nonempty printable value <=2048 characters; never printed or placed in command arguments |
| `OMS_STAGING_MODEL` | Owner-approved exact provider model ID, <=256 printable characters; no default, alias selection or routing/failover |
| `OMS_STAGING_TIMEOUT_SECONDS` | Finite total run deadline >0 and <=10 seconds; half reserved for cancellation and concurrent response/client cleanup |
| `OMS_STAGING_MAX_OUTPUT_TOKENS` | Explicit positive integer <=256, sent as `max_tokens` |

Only `PATH`, `PYTHONPATH`, `PYTHONDONTWRITEBYTECODE`, `LANG`, `LC_ALL` and
`SYSTEMROOT` may accompany these names. Any other environment name causes
`ISOLATION_VIOLATION` before provider construction, even if empty. Do not inherit
operational database/service-role, payment, assignment, governance, proxy,
Langfuse or general provider credentials. The client ignores proxy/environment
configuration (`trust_env=False`), follows no redirects and makes no retries.
Repository `.env` files are never loaded.

Within a separately authorized, already isolated environment with these names
injected securely and the existing worker dependencies available:

```sh
PYTHONPATH=workers/src python3 workers/scripts/run_oms_recommendation.py --run-synthetic-shadow
```

This command would make a provider request. It has **not** been executed against
a live provider and must not be run without separate owner authorization. The
flag makes invocation explicit; it does not grant approval.

Each run sends at most one request, <=4096 request-body bytes and <=16384 raw
identity-encoded response bytes. At most 16 candidates are accepted before
serialization; numeric features are normalized to finite floats. Configuration
field limits prevent excessive request allocation before the final body cap.
Compressed responses are refused without reading/decompressing; oversized
Content-Length and raw chunks are rejected before consumption/buffer extension.
Only positional candidate references and synthetic numeric
features are placed in user content. The exact configured model/output limit and
a fixed ranking instruction form the remaining request body. There are no tools,
financial/operational identifiers or prompt inputs from real users.

Valid output must contain exactly one permutation of the eligible references
and no extra ranking fields. The provider envelope must contain one completed
assistant text choice without tool calls/refusal. Duplicate JSON keys, truncation
and oversized responses fail explicitly.

Reports contain baseline references, advisory result/reason, provider outcome,
request count and `telemetry_enabled=false`. Provider envelope/transport failures
use the existing `AGENT_FAILURE`, `AGENT_UNAVAILABLE` or `AGENT_TIMEOUT` fallback
plus a safe provider outcome; ranking validation failures use `MALFORMED_OUTPUT`.
No provider body/diagnostic or secret is printed. Cleanup/configuration failures
exit nonzero rather than returning a successful report.

## One proposed bounded live-validation run -- not authorized

1. **Owner preflight:** approve one endpoint, exact model, dedicated key and this
   single synthetic invocation. Confirm support for `response_format=json_object`
   and `max_tokens`. Confirm model pricing, data policy/residency and that no
   provider tools or automatic model routing are enabled.
2. **Proposed limits:** one invocation, one request, no retries, three fixed
   synthetic candidates, total timeout **2 seconds** (at most 1 second for request
   handling, with the remainder reserved for cleanup), output limit **128 tokens**.
   The implementation ceilings above are not defaults or live authorization.
   Proposed total spend ceiling: **USD 0.10**, subject to explicit owner approval.
3. **Enforce spending outside the runner:** use an isolated provider account/key
   with an enforceable hard quota or prepaid remaining balance <=the approved
   ceiling. Verify the worst-case input/output charge fits that ceiling using the
   selected model's actual tariff. Token/request caps alone are not a monetary
   guarantee. If a hard cap cannot be enforced or pricing is unconfirmed, do not
   run. Do not repeat the command automatically or invoke financial adapters.
4. **Isolate:** use a dedicated unprivileged process/container with no repository
   credential-file mount, operational/governance/financial mounts or writable
   business storage. Inject only the allowlisted environment; deny database,
   payment and governance network destinations. Allow outbound TLS only to the
   approved endpoint and required DNS. This preflight is not a hostile-Python
   sandbox and is not a production authentication mechanism.
5. **Acceptance:** exactly one request; only approved fields sent; accepted
   ranking is a complete permutation or the exact baseline is returned with a
   safe reason/outcome. No operational mutation or background task remains.
   Streams/client close and the finite process exits. Provider outage/rate-limit
   drills remain mocked; no extra live requests are implied by this plan.
6. **Evidence:** retain the reviewed implementation SHA, configuration names
   (never key values), request count, safe result/reason, elapsed time and cleanup
   confirmation. Obtain actual usage/charge evidence through separately approved
   provider-account access. Do not claim this report reconciles provider invoices
   or an authoritative financial ledger.
7. **Cleanup:** stop only the dedicated process, revoke/delete its provider-only
   key and remove named slice-owned temporary resources. Apply approved provider
   retention/deletion policy. No operational data, shared queues or authoritative
   audit records are deleted or altered.
8. **Rollback:** disable/remove the standalone invocation path and adapter, or
   revert a later reviewed feature commit if one is separately authorized.
   Deterministic assignment continues unchanged; no database rollback is needed.

## Remaining owner decisions and gates

- A particular provider/endpoint/model, credential/account owner, live-call
  permission, monetary ceiling and enforceable budget mechanism are **not**
  approved by selecting the implementation protocol.
- Hosting/process identity, egress policy and credential injection need isolated
  execution approval. No cloud migration or general agent activation is implied.
- M6's live correlation/instrumentation, deployed storage/credential/network
  isolation, real exporter recovery and real usage/invoice/ledger reconciliation
  remain UNVERIFIED. Residency, retention, sampling and live emitters require
  separate approval. This bridge leaves telemetry entirely uninstantiated.
- Trusted operational snapshot production, real identity authentication, durable
  human review and runtime integration remain deferred; synthetic fixtures are
  not evidence for those surfaces.
- D-33 remains pending. Paperclip/settlement controls, deterministic assignment
  and manual approval for every refund are unchanged. No SQL, live payments,
  merge, deployment or agent activation is authorized. Unrelated integrations
  remain deferred.

## Publication provenance

The source base is reviewed PR #9 head
`70c372fdd1f1328eb09a4175f028d4a7755fa77d`. At finalization, fetched master remains
`a3b4d97542d55fa39c5b738504783ae2f40703ba`; the draft PR against master therefore
also contains PR #9's inherited nine-file fake-review delta. That delta is not new
bridge work. D-39's finalization instruction authorizes the scoped commit, branch
push and draft PR, not merge or live execution. Exact-head CI/publication status
must be verified separately; historical PR #9 CI is not bridge CI. If terminal
authentication fails, preserve the commit and export its patch without repeating
sign-in loops.
