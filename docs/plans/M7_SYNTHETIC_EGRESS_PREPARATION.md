# Bounded M7 synthetic egress preparation

Preparation only, 2026-10-13, based on master merge
`12c714e4af559b0ddd69ccd33958d28e783b13f4`. No automatic installation, namespace
creation, firewall application, route/NAT change, service activation or provider
request is supplied. This draft does not grant authority to perform the controls.

## Installed diagnostic checkpoint

The owner authorized deploying only the reviewed diagnostic unit from PR #16.
The operator verified Linux `srv1943844`, IP `200.234.43.145`, merge tree
`27bd6b7bdfe3ca5ea5cf4052cffa675491dc538d` and all five post-merge CI jobs.
The dirty application checkout on `feat/m6-r1-remove-mandatory-odoo` was preserved;
this preparation uses a separate feature checkout based on current master.

Only `/etc/systemd/system/zippy-oms-staging-probe.service` changed, from SHA-256
`4e6f43739e4e2d7ac0d656d85b695a8c16ad4400e23a70c689c9992a95f65e70` to
`e0b69400dbc7dcf2bb396633b9f35ec5e346fd0f9e52762ece3fc5c552a4f5cd`, replacing
the source ReadOnlyPaths directive with its explicit same-path read-only bind.
The original unit/metadata were privately backed up and the candidate validated
before atomic replacement and configuration reload. The installed PR #15 probe
script remains SHA-256
`67c77c4026f81c3a8c6c93468706df5134e1585e62ffec321e31384e64895eb8`.

One bounded run at 2026-10-13 18:07:59 IST exited 0 and reported
`LOCAL_CHECKS_PASSED`. Independent observations captured exactly one source mount
with read-only per-mount options. The actual probe EUID was 64021, effective
capabilities zero and NoNewPrivileges true. Outside the sandbox, ordinary UID
65534 opened/closed the exact synthetic fixture without reading bytes; inside,
permission denial was observed. Fresh host/named/probe namespace comparisons
proved the named network boundary and distinct mount/IPC namespaces. These are
facts from that invocation, not future identity/inode promises.

Successful oneshot completion cleared the systemctl InvocationID property before
the first journal lookup. The same run's JSON was recovered with its captured
PID and narrow time window, yielding invocation
`fa648c7a2dfc49a69504132f7cf75312`; no rerun occurred. Sanitized evidence and the
change ledger are in `/tmp/m7-diagnostic-deploy-20261013-r9txoay2/`.
Only the credential-free diagnostic gate is PASS. Provider requests are zero.

## What the new harness records

`workers/scripts/probe_oms_synthetic_egress.py` is stdlib-only. Its default CLI
is passive preparation output with zero socket attempts. Explicit
`--perform-controls` requires the fixed Linux host, a non-root identity, the
existing credential-free boundary probe's LOCAL_CHECKS_PASSED result, and an
actual network inode matching `/run/netns/zippy-oms-staging` before any socket.
It uses no credentials, provider imports, hostname lookup, HTTP, TLS, DNS query,
database protocol or operational data. Targets and ports cannot be overridden.

The disabled `zippy-oms-staging-egress-probe@.service.in` template accepts
`calibration` or `restricted` as its instance, uses a separate
`owner-egress-probe-enabled` condition, clean environment/isolated Python, the
same non-root/capability/mount/fixture restrictions and an 18-second oneshot
bound. There is no installation section, restart, key or state-store directive.
Do not create the marker or install this unit under the diagnostic-only approval.

Each phase has 14 attempts, at most one second per attempt, a single 16-second
monotonic run deadline and a 64-byte response bound (one extra byte detects an
oversized response). Socket connect/send/receive share the same attempt deadline;
later operations never restart it. Every socket closes on success or error.
Two phases mean at most 28 attempts, with no retries. Bound future calibration
and restricted invocations plus transition time to 40 seconds in their reviewed
operator protocol; a delayed transition invalidates the evidence.

The synthetic peer protocol echoes the exact `M7-CONTROL ` prefix plus a fresh
24-character hexadecimal nonce. TCP peers must close after the bounded echo;
UDP must return one exact datagram. A stale/wrong/oversized response fails.
Responses and exception messages are not logged; only fixed destinations,
protocol/port, expected control and sanitized result codes are emitted.

## Proposed isolated topology and control matrix

No peer topology exists yet. The installed target still has only down loopback,
no IPv4/IPv6 routes, default-drop policy and four empty destination sets.
Missing routes cannot prove firewall denial. Preserve that state during this PR.

Under future explicit setup authority, use one veth pair entirely between the
existing target namespace and a new `zippy-m7-synthetic-peer` namespace. Create
the link inside these namespaces; no host interface, host routes, host firewall,
NAT, shared Docker networking or external uplink is required. Target addresses
are `192.0.2.1/29` and `2001:db8:7::1/64`; peer addresses are the table below.
These documentation ranges are synthetic destinations, not provider IPs.
Pre-reviewed namespace-local static neighbor entries must prevent IPv6 neighbor
discovery/default-drop rules from confounding the test. Missing IPv6 support,
link reachability or neighbor evidence leaves the gate UNVERIFIED.

| Family | Allowed synthetic peer | Denied synthetic peer | Positive ports | Additional port denial |
|---|---|---|---|---|
| IPv4 | 192.0.2.2 | 192.0.2.3 | TCP 443, TCP 53, UDP 53 | TCP 5432 at 192.0.2.2 |
| IPv6 | 2001:db8:7::2 | 2001:db8:7::3 | TCP 443, TCP 53, UDP 53 | TCP 5432 at 2001:db8:7::2 |

All listed denied address/port combinations must have live synthetic echo
listeners during calibration, including TCP5432 on the allowed peers. No real
database, payment, governance or provider destination may substitute for them.

The bounded echo-listener artifact, namespace-local privilege binding for ports
53/443, exact calibration/counter policy and operator evidence collector still
need concrete review before setup. This draft supplies the client harness,
disabled client template and protocol, not an automatic listener/policy installer.
Do not silently rely on root identity, an unknown echo server or permissive
host networking to fill those gaps. Listener privileged-port capability, if
required, belongs only to a separately reviewed peer boundary; the target retains
zero capabilities. Listener duration must be bounded and cleanup ledgered.

## Future evidence sequence and acceptance

1. Obtain exact-head review/CI and separate scoped topology/control activation
   approval. Seal source hashes and interpreter provenance. Inspect/refuse
   resource conflicts. Record the original dedicated namespace policy, empty
   sets, routes, links and all resources to be newly created or temporarily changed.
2. Review the exact temporary calibration and restricted policy files plus
   bounded listener/collector artifacts. Work only inside the independently
   verified named namespaces; preserve drop-default INPUT/OUTPUT/FORWARD. Never
   load a file in the host namespace or use a shared/global ruleset flush.
3. Calibration must permit all 14 fixed synthetic tuples temporarily, with no
   other destinations. From the actual restricted unit, require all 14 nonce
   echoes; collect fresh EUID/capabilities/NNP/mount/inode facts. Non-root positive
   controls are required outside the target for fixture access as before.
4. For the restricted phase, permit only .2/::2 TCP443 and TCP/UDP53 in the
   corresponding provider/DNS sets. TCP5432 and every .3/::3 tuple remain denied.
   Include reviewed per-tuple output counters/trace for all six permitted and
   eight denied cases, with explicit deny rules before final default drop.
   Capture policy/source hashes and all per-tuple counter baselines before the
   phase, then deltas after it. Each tuple is attempted only once; synchronize
   any trace evidence with the harness's UTC start and per-case elapsed times. The
   observation mechanism must not use a privileged root client as target proof.
5. Require successful permitted responses for both families, retained peer
   listener-health evidence, completed calibration and policy-correlated drops
   for each negative case. Packet/byte counter increases must match the exact
   family/address/transport/port, timeframe and actual target boundary. Other
   namespace clients/listeners/traffic invalidate attribution. Absent responses
   without that correlation are UNVERIFIED, even if every positive passes.
6. Join fresh host/named/target namespace observations, phase timestamps,
   calibration output, target output, dedicated effective rules/counters and
   listener-health evidence in one dated operator record. Missing, partial or
   inconsistent evidence leaves the gate UNVERIFIED; do not synthesize a PASS.
7. Restore the exact original namespace policy and empty sets, remove only the
   newly created synthetic listeners/link/peer namespace/neighbor entries and
   egress unit/marker, and verify original no-uplink/no-route state. Preserve the
   installed credential-free diagnostic, source, fixture and all evidence. On
   conflict, preserve resources and report rather than overwriting/removing them.

The harness intentionally never reports effective-egress or M7 readiness PASS.
`CALIBRATION_RESPONSES_OBSERVED` and
`CANDIDATE_CONTROLS_REQUIRE_EXTERNAL_PROOF` mean only that its local observations
fit the phase. Timeouts and permission errors remain explicitly unverified;
connection refused, no-route/neighbor failures and invalid responses fail local
control suitability. Exit 0 is not a readiness approval. Independently verified
counter/control correlation is mandatory before an operator can accept the
synthetic gate, and still does not establish future DeepSeek/TLS/DNS connectivity.

## Remaining readiness and rollback

Capability/grant/circuit denials are unchanged; denial preservation is PASS,
trusted authorization for live execution UNVERIFIED. Credential injection,
provider claim-state isolation, effective egress, dedicated staging scope and
provider spending enforcement remain pending. Owner-reported $15 credits/cap
and no recharge are unverified enforcement evidence. GitHub OpenRouter key
storage is not VPS injection. Exact Qwen model/route and combined budget remain
unapproved. M7 inference, fallback and production stay denied. D-33 remains
pending; every refund requires manual approval.

Diagnostic-unit rollback is limited to the private original backup in the
deployment evidence directory: verify current corrected and backup hashes,
stop only the diagnostic if active, restore only its original root-owned 0444
unit, validate and reload configuration. Do not delete existing namespaces,
firewall, bundle, fixture, markers, credentials or claim state. No rollback was
executed; the successful corrected diagnostic remains installed. This draft's
uninstalled client/template/plan have no host resources to roll back.
