# M7 readiness evidence and separate fallback preparation

Owner instruction, 2026-10-12: continue the remaining M7 readiness gates and
prepare OpenRouter/Qwen as an automatic fallback option. This records the new
fallback preference separately from the single-provider DeepSeek preflight.
It does not grant live provider, VPS setup, deployment or financial authority.

Source checkpoint: PR #13 merged into master at
`e82924a8a57e6c0115aa0e6405703f030bd54803`, reviewed source head
`3922e42ab58a5dac3fc237cf756dd4e6d75df5e5`. All seven pre-merge checks and five
post-merge CI jobs passed. The disposable proofs executed all 72 integration
cases, with 164 suite tests passed and zero skips. This is database/development
evidence, not installed M7 target or provider-budget acceptance.

## Evidence checkpoint

| Gate | Current evidence | Precise remaining requirement |
|---|---|---|
| New DeepSeek key connectivity | OWNER-REPORTED PASS: VS Code test authenticated, found two configured models, received exactly `DEEPSEEK_API_OK` from `deepseek-flash`, and used 66 tokens | Sanitized script/run provenance, time, execution identity and key label; the smoke test is not an M7 authorized runner test |
| Dedicated staging credential | Previous GitHub metadata confirms `DEEPSEEK_STAGING_API_KEY` in the Production environment; that metadata predates the reported key replacement | Establish account/key owner and dedicated staging scope, then bind that key to the isolated target's private credential file; no value belongs in evidence |
| Installed unprivileged target | Reviewed service/namespace templates exist, but installation and effective boundaries are UNVERIFIED | Observed non-root execution UID, sealed source/dependencies, private state and credential ownership, restricted mounts and absence of business credentials |
| Restricted egress | Empty destination sets and drop-default template are reviewed; effective policy remains UNVERIFIED | Observe the actual target namespace's IPv4/IPv6 rules, approved TLS/DNS destinations and denial of database/payment/governance destinations |
| Hard spending cap | UNVERIFIED; 66 tokens measures usage, not enforced spend | Owner-approved monetary amount/currency and provider-account evidence of enforcement, credits, balance, reset/recharge behavior and worst-case charge |
| Endpoint-bound authorization | VERIFIED DENIED: capability absent and trusted registry empty | Separately reviewed trusted issuer integration and one-use approval bound to actual source, UID, credential path, endpoint/model, limits, expiry and evidence |
| OpenRouter/Qwen fallback | Owner preference recorded; persistent primary circuit guard prepared; fallback NOT IMPLEMENTED OR ENABLED | Exact Qwen model ID and provider routing choice, separate key/account evidence, aggregate budget, endpoint authorization and mocked fallback proof |

The claim that both configured models are available does not select the second
model or authorize model switching during the DeepSeek-specific preflight.
The current primary remains `deepseek-flash` at
`https://api.deepseek.com/chat/completions`, with disabled thinking, explicit JSON
output and output-token limits. Automatic model fallback remains disabled in the
merged implementation while its separate preparation is reviewed.

## Next evidence collection, without inference

`workers/scripts/collect_oms_staging_evidence.py` is a standalone, standard-library
collector for the existing VS Code Remote-SSH window. It checks the expected
Linux hostname before querying the named target. It reads only selected systemd
properties, effective process UID/capabilities, relevant mount flags, namespace
inodes, named nftables policy/set counts and a rules hash, plus credential/state
file metadata. It never reads a key, Environment/ExecStart, process environments,
business files or unrestricted service logs. Commands are only `systemctl show`
and the named namespace's `nft -j list table` through `ip netns exec`; no service
start, firewall application, curl, provider request or account call is present.

The normal exit 0 means evidence was collected, not readiness approval. JSON
always retains `readiness=UNVERIFIED`, and flags wrong hosts, absent processes,
root effective identity and unobserved access/destination denial. A wrong host
returns exit 2 without querying target properties. Configured sandbox settings
and firewall policy/hash alone never produce an isolation PASS.

After fetching the reviewed PR #14 head in the existing repository, execute the
collector from its exact reviewed SHA with `git show <SHA>:workers/scripts/collect_oms_staging_evidence.py`
piped to `python3 - --expected-host srv1943844`. This needs no checkout, temporary
key, dependency installation or worktree changes. Do not run from a local Windows
terminal and promote those observations to VPS evidence.

Use the existing authorized VS Code Remote-SSH session to collect safe metadata
from the actual named target. Do not replace a target with the privileged shell
identity, or claim container/network flags prove effective isolation.

1. Confirm hostname, repository/bundle SHA and operator identity. Preserve all
   worktrees. Identify the staging service and its namespace explicitly; if
   absent, record NOT INSTALLED rather than testing from the root host shell.
2. Read only the named service's non-secret properties: load/active state,
   configured identity, namespace path, sandbox settings and enable-marker
   presence. Do not print Environment, credential contents, full command lines,
   process environments, `.env` files or unrestricted service logs.
3. Inspect only metadata for the nominated staging credential and claim store:
   owner, mode, size, regular-file/link status and directory ownership. Do not
   read, hash or copy the credential. Metadata alone does not prove secure
   injection or provider scope.
4. If a staging process already exists, verify its effective UID, capabilities,
   mount restrictions and network-namespace identity. A configured `User=` is
   not effective process evidence. No active process means execution identity
   remains unverified; do not start inference to obtain it.
5. Read the named namespace's effective nftables/routing/resolver metadata with
   existing authority. Record IPv4 and IPv6, deny defaults and approved address
   sets. Keep source rules or sanitized rule hashes and verifier identity. A
   successful curl to DeepSeek does not prove denial of other destinations.
6. Obtain owner-supplied provider-account settings evidence separately. Do not
   create keys, top up, change budgets, read account APIs or invoke authenticated
   model/balance probes merely to complete this checklist.
7. Reconcile every item into a single dated evidence record. Retain UNKNOWN,
   UNVERIFIED or FAIL when observation is unavailable. Evidence strings in a
   grant do not enforce a budget or authenticate an issuer.

Host setup is a separate concrete gate: review the existing
[service/egress plan](M7_OMS_ISOLATION_PREPARATION.md), identify exact service,
namespace, source bundle and credential/account boundary, then obtain scoped
installation authority. Installation may prepare an isolated target, but must
not populate the grant registry, add provider capability or enable inference.
Never apply the namespace firewall template to host OUTPUT or shared networks.

Effective denial probes should use local synthetic destinations outside business
systems and must be scoped separately from passive inventory. Do not probe live
databases, payment gateways or governance services to claim isolation evidence.
No provider retry or fallback is required to prove those boundaries.

## Separate OpenRouter/Qwen fallback design

### Prepared strict circuit guard

`provider_circuit.py` implements a persistent single-inflight primary latch in
the trusted grant's already-private claim directory. Nonblocking file locking,
exclusive reservations, private regular-file/owner/link checks and fsync prevent
concurrent admissions or process restart from clearing a failed/abandoned run.
One provider failure opens the circuit. Authentication/invalid-output/configuration,
cleanup and cancellation failures also latch it, without granting fallback.
There is no cooldown, half-open probe, automatic reset or reset CLI. Operator
deletion of its own state or hostile in-process Python is outside this boundary.

The runner reserves only after the existing capability and trusted grant checks,
then before credential-file read/client construction. A successful, validated,
single-request result and completed cleanup release that reservation. Storage
errors fail closed; partial failure markers or abandoned reservations keep later
invocations blocked. The source digest also binds this circuit module. No real
grant is registered, so the normal CLI still denies before touching circuit state.

`assert_fallback_authorized` deliberately denies while no trusted Qwen policy
exists. An open breaker or a second API key cannot authorize another request.
These mocked preparations change neither the primary model nor live authority.

The owner has selected the fallback family, not an exact model. Do not guess a
Qwen identifier, use an automatic model router, or reuse the DeepSeek credential.
The OpenRouter completion endpoint is
`https://openrouter.ai/api/v1/chat/completions`; exact model/provider choices and
their account availability remain pending. A credential can be kept separately
without injecting it into the DeepSeek-only process.

Future automatic fallback acceptance must include:

- One explicit Qwen model and approved provider route, its own private staging
  credential and issuer-approved endpoint/model binding.
- An explicitly approved request policy. The current grant allows one request;
  it must not be reused as authority for a second provider call. A future policy
  needs an independently authorized primary and fallback request, one shared
  finite deadline and aggregate spending evidence for both providers.
- At most one fallback attempt, after the primary request and its resources are
  closed. Never run both providers concurrently or restart the deadline. Do not
  assume timeout/cancellation means the primary was unbilled.
- Explicit eligible failure conditions. Authorization, credential, isolation,
  budget, cleanup and invalid-output failures must not trigger a provider switch.
  They remain errors or the existing deterministic advisory fallback.
- The same minimized synthetic inputs, complete-permutation output validation,
  no operational writes, no tools and safe outcome/request-count reporting.
- OpenRouter internal routing must also be explicit. Its documented provider
  fallback default is enabled; a proposed single-route policy should use an
  approved `provider.only` choice, `allow_fallbacks: false` and
  `require_parameters: true`. Do not silently drop required JSON/output limits
  or send a multi-model list. Validate the chosen route before live acceptance.
- Mocked regressions proving unchanged DeepSeek success behavior, exactly one
  authorized fallback, correct aggregate limits, no authority escalation,
  denied missing evidence, redaction, cleanup and unchanged deterministic
  assignment. No live outage drill or extra inference is implied.

These are design requirements for a separate reviewed implementation, not
runtime configuration or permission to register a grant. DeepSeek's original
one-provider preflight remains independently assessable.

Official references checked on 2026-10-12:

- [OpenRouter provider selection](https://openrouter.ai/docs/guides/routing/provider-selection)
- [OpenRouter model fallbacks](https://openrouter.ai/docs/guides/routing/model-fallbacks)
- [OpenRouter key-limit schema](https://openrouter.ai/docs/api/api-reference/api-keys/create-a-new-api-key)

Public documentation or a key-limit field is not evidence of the user's effective
account budget or a demonstrated hard ceiling. Preserve account settings,
currency/credits/reset/BYOK coverage and enforcement evidence without secrets.

## Access and activation checkpoint

This ChatGPT session can inspect GitHub source, but has no exposed Hostinger VPS
tools. The authorized Desktop Commander device inventory returned only offline
Windows devices; no VPS terminal was accessed. Local scratch identity or its
network configuration is not host evidence. No host isolation/egress gate was
upgraded by this preparation.

No secret was loaded, no account/provider request was sent, and no VPS/service/
firewall/deployment change occurred. The approved grant registry stays empty and
the provider capability remains denied. D-33 remains pending; every refund
requires manual approval. M7 activation and the first authorized M7 live run
remain blocked until all applicable gates have verified evidence.
