# M7 isolated execution preparation

Authority/scope: D-40, preparation only. Source base is PR #11
`6ed3f35676fa8f5b622ef226a35c3ec20ee66771`. Preserve that PR and all VPS
worktrees. The service and firewall files are review templates, not installed
configuration. **Live execution remains NO-GO.**

## Implemented boundaries

- Standalone CLI explicitly selects `--provider-profile deepseek-direct`.
  Its adapter sends only the closed profile's disabled-thinking field;
  endpoint/model mismatch still fails. No automatic model fallback.
- The existing external capability check still denies before client creation.
  A second endpoint-bound grant check remains denied by an empty immutable
  registry. There is no JSON/CLI/environment grant loader or registration API.
- The trusted-record contract binds agent, operation, exact endpoint/model,
  profile, source SHA plus actual adapter/runner source digest, unprivileged UID,
  exact credential file and claim-directory paths, timeout/output limits,
  one request, validity window and required owner/budget/key/isolation evidence.
  The full run must fit before expiry; this is rechecked after preparation I/O.
  Before client initialization, the runner captures one monotonic deadline capped
  by both the granted expiry and configured duration. Initialization, request
  construction, HTTP and cleanup consume that same window; ranking never resets
  it. An exhausted request window prevents HTTP, including after request building.
- Atomic exclusive file creation and fsync consume an approved invocation before
  client creation. A concurrent/restarted caller finds the consumed marker;
  failures never remove it. Changing claim directories does not reset a grant.
  This is a staging reservation, not a provider idempotency or billing API.
- `--credential-file` is mutually exclusive with an environment API key. The
  private regular file is opened without following symlinks, checked for owner,
  mode, link count and size, and read only after both authorization checks.
  Errors contain reason codes, not contents. The project `.env` is never loaded.

## Disabled unprivileged target template

`infra/m7-staging/zippy-oms-staging.service.in` has no installation section.
The enable marker, sealed bundle, key, namespace, resolver file, source SHA and
grant placeholders are intentionally absent/unapproved. It cannot be treated as
an installed working target.

The proposed service uses a dynamic non-root identity, private state directory,
read-only system/source, inaccessible business/governance paths and Docker
socket, no capabilities, no-new-privileges, private IPC/temp/devices and explicit
network namespace. It has no restart policy. `TimeoutStartSec=12` bounds the
one-shot process; RuntimeMaxSec is not used because systemd ignores it for
Type=oneshot. The adapter/runner's configurable ceiling remains 10 seconds.

Systemd loads only a separately approved provider credential, then `env -i`
passes the five-value configuration contract (key comes from the explicit file)
plus the existing safe environment names. No production credential file is
mounted or inherited. A future operator must verify the actual service UID,
decrypted credential ownership/mode, state-directory mapping and mounts before
issuing a grant; the template alone is not that evidence.

## Namespace egress template

`infra/m7-staging/egress.nft.in` contains only its dedicated inet table and
drop-default INPUT/OUTPUT/FORWARD chains. Provider IPv4/IPv6 destination sets
permit TCP/443; resolver sets permit UDP/TCP/53. All sets are empty by default,
so the template denies every external destination. It contains no host firewall
flush, host OUTPUT modification, NAT, namespace creation or automatic installer.

Never apply it to the host namespace. Filling sets requires independently
verified provider/resolver destinations, suitable route/link/IPv6 neighbor
handling and an isolated target. IP allowlisting is not hostname authentication:
the closed HTTPS endpoint, TLS validation and disabled redirects remain necessary.
Test the effective namespace policy and its host separation before approval.
No IPs were invented, DNS lookup performed or provider connectivity probed.

## Trusted authority and budget limitations

The registry is empty. Signed/authenticated owner/governance issuance and its
transport/storage integration are not supplied by this preparatory slice.
Do not populate it manually from request metadata or test records, change the
global matrix to enable all provider requests, or monkeypatch a real invocation.

`--source-sha` is an asserted identifier, not attestation. The source digest binds
six actual source files, including the prepared persistent circuit guard; it is
not a dependency/OS image digest. A future owner
must verify the sealed artifact's provenance, dependencies, source digest and
isolation evidence before a trusted authority can register any matching grant.
Hostile in-process Python/root is outside this module's security boundary.

The grant's Decimal spend ceiling and evidence references do not control
DeepSeek billing. Provider-enforced hard quota or independently isolated capped
balance, credits/currency/no-recharge evidence and the owner-approved amount
remain required. USD 0.10, 128 output tokens and 10 seconds are proposals, not
approval or an established worst-case charge. No authenticated balance/model/key
probe, purchase or top-up occurred.

## Credential metadata checkpoint

GitHub repository secret listing: three entries, no DeepSeek/OMS key.
Environments: `copilot` (no secrets) and `Production`.
`Production` has `DEEPSEEK_API_KEY`, created 2026-10-12; no
`OMS_STAGING_API_KEY` entry. This proves storage of a name only, not value,
validity, scope, a dedicated staging account, VPS injection or budget isolation.
No workflow is added or changed to expose/use that secret. Do not reuse the
Production secret as staging evidence or put it in source, argv or logs.

## Validation and future acceptance

Mocked proofs cover exact CLI payload, denied execution before key/client access,
binding changes, expiry/full-run window, limits/evidence denial, concurrent and
cross-instance one-use claims, alternate claim-store denial, private-file versus
symlink/mode handling, and all inherited fallback/cancellation/cleanup cases.
The systemd template passes `systemd-analyze verify --man=no` in the scratch
environment without errors/warnings; no service is started. nft is unavailable
there, so nft syntax/kernel evaluation and effective egress remain UNVERIFIED.
Static policy checks are not host firewall proof. No database test gap is closed.

Next acceptance requires: review and exact-head CI; separately approved host
setup; observed non-root UID/mount/file/network boundaries; a dedicated injected
key; hard-budget evidence; a trusted independently approved one-use grant; and
explicit permission for the single synthetic request. No merge is required or
authorized merely to test a reviewed feature commit. Keep NO-GO while any item
is missing. D-33 pending; every refund remains manually approved.

Rollback for this preparation: do not install/activate the templates; preserve
the source diff for review. If host setup is later approved, stop only the named
staging service/namespace and revoke its dedicated credential under that separate
cleanup scope. Never delete shared host rules, operational data, queues or audit
records. Never remove a consumed claim to permit a retry.
