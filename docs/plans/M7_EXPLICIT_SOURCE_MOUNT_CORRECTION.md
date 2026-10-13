# M7 explicit source-mount correction

Preparation only, 2026-10-13. Parent: draft PR #16 at
`8eeebca360189502cb07f74feb7a57ae9b6a5347`. The installed credential-free
diagnostic remains pinned to PR #15 merge
`558fb39e6335624faec7540f2e4f34b0e7124ce4`. This correction does not install,
reload or start a unit, provision credentials, merge the PR or authorize inference.

## Observed failure and configuration correction

The existing sanitized VPS evidence in
`/tmp/m7-install-20261013-hiysm496/runtime-evidence.json` and `mount-detail.json`
records three bounded credential-free runs on `srv1943844`. The probe returned
`NOT_VERIFIED`, exit 1, with `bundle_readonly=null`. Its mount namespace had a
read-only `/` mount but no exact `/opt/zippy-m7-staging` entry. Non-root identity,
zero effective capabilities, NoNewPrivileges, synthetic fixture permission denial
and independently compared namespaces were observed. These are dated observations,
not UID/inode promises for a future run. Provider requests were zero.

All three disabled templates replace exactly one directive:

```diff
 BindReadOnlyPaths=/etc/netns/zippy-oms-staging/resolv.conf:/etc/resolv.conf
-ReadOnlyPaths=/opt/zippy-m7-staging
+BindReadOnlyPaths=/opt/zippy-m7-staging:/opt/zippy-m7-staging
```

The VPS runs systemd `255 (255.4-1ubuntu8.17)`. Its installed
`/usr/share/man/man5/systemd.exec.5.gz` and
[upstream documentation](https://github.com/systemd/systemd/blob/main/man/systemd.exec.xml)
describe unit-private read-only binds and append semantics for repeated nonempty
assignments. The resolver bind remains present; no empty bind-list assignment or
host-wide bind/remount is added. Static acceptance does not establish that this
platform will expose the required effective mount after activation.

The detector is unchanged: it requires exactly one exact source mount with `ro`
in the per-mount options. A read-only ancestor, absent mount, writable mount or
ambiguous duplicate remains a failure. New regressions reproduce the observed
read-only-root shape in both credential-free and optional credential-metadata
modes; the unsafe source boundary must prevent credential metadata inspection.
All three templates are checked for both bind destinations, marker separation,
clean environment and preserved sandbox/time/restart/credential restrictions.
PR #16's inherited wall-clock deadline-fixture correction is retained; no runtime
window, capability, grant registry, circuit or fallback guard changes.

## Validation and limits

Run the affected target-probe, credential-probe and staging-authorization tests;
Ruff lint and format checks on those Python files and the unchanged probe;
strict mypy on the probe; and installed-platform `systemd-analyze verify --man=no`
on temporary concrete copies of all three templates. No unit is installed or
started by static validation. Existing unrelated ServerAvatar obsolete-syslog
warnings must be distinguished from target-unit errors.

Publish the exact corrected head on the existing PR #16 branch while preserving
its parent commits. Keep it draft/unmerged. Record the actual SHA, targeted counts
and exact-head CI results in the PR and external correction evidence; do not treat
old-head CI or the PR #15 retry as corrected-source acceptance.

## Exact later installation gate and rollback

After corrected-head review and explicit diagnostic-installation authorization:

1. Verify the named host and inspect the existing diagnostic unit, parents,
   ownership, type, links, drop-ins and markers. Refuse conflicts. The only
   authorized candidate destination is
   `/etc/systemd/system/zippy-oms-staging-probe.service`.
2. Verify its current bytes still match the installed PR #15 template: SHA-256
   `4e6f43739e4e2d7ac0d656d85b695a8c16ad4400e23a70c689c9992a95f65e70`.
   Verify the installed PR #15 probe remains SHA-256
   `67c77c4026f81c3a8c6c93468706df5134e1585e62ffec321e31384e64895eb8`.
   This unit correction needs no script or source-bundle replacement.
3. Export only the reviewed corrected diagnostic template. Its SHA-256 is
   `e0b69400dbc7dcf2bb396633b9f35ec5e346fd0f9e52762ece3fc5c552a4f5cd`.
   Validate the concrete candidate before loading. Retain a private root-owned
   backup of the existing unit and its metadata in the new installation ledger.
   The installation diff must be exactly the single directive replacement above.
4. Replace only that diagnostic unit, preserving root ownership and mode 0444,
   and reload unit configuration. Do not change the existing source bundle,
   resolver, namespace, firewall, synthetic fixture, or any credential/provider
   template, unit, key or marker. Do not enable at boot or add restarts.
5. Before one bounded credential-free run, demonstrate a non-root outside-sandbox
   open of the exact synthetic fixture without reading bytes. Collect fresh host
   and named network namespace facts. Capture only the dedicated invocation's
   sanitized JSON/exit status and relevant actual service mount/process metadata.
6. Accept the mount correction only with one exact read-only source mount,
   successful probe exit, actual non-root EUID, zero effective capabilities,
   NoNewPrivileges, fixture denial and fresh network/mount/IPC comparisons.
   Static configuration alone is insufficient. A failure remains a failure.

Rollback, only for a later separately authorized installation: stop only the
dedicated diagnostic if active; verify its unit still matches the installed
corrected hash; restore only the saved PR #15 unit with its original owner/mode;
validate and reload. Preserve both before/after evidence. Do not rerun the old
known-failing diagnostic unchanged, delete namespaces/firewall/fixtures, or remove
provider state, application edits or shared resources. The current correction
preparation has made no installed-unit change to roll back.

## Remaining gates

Authorization-denial preservation is PASS; trusted authorization for live
execution remains UNVERIFIED. Credential injection, provider state isolation,
reachable synthetic IPv4/IPv6 egress controls, dedicated staging scope, provider
spending enforcement and endpoint-bound one-use authority remain pending.
Owner-reported $15 credits/cap and no recharge do not verify enforcement. Empty
sets and absent routes do not prove denial of reachable destinations. GitHub
secret storage metadata is not VPS injection. DeepSeek remains `deepseek-flash`
at `https://api.deepseek.com/chat/completions`; OpenRouter/Qwen is not activated.
No production deployment/application restart or provider request is authorized.
D-33 remains pending; every refund requires manual approval.
