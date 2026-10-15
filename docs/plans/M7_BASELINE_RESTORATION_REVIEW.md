# New M7 baseline restoration procedure — review only

Owner instruction, 15 October 2026: end historical procedure recovery and prepare
a new, tested, explicitly reviewed namespace-only procedure. This authorizes
preparation and disposable tests, not VPS installation/execution, merge,
diagnostic start, synthetic activation, credentials or live inference.

## Provenance and why this is new

The historical source was PR #17 merge
`2502282867f8516e2d22a3eb6c6105e482bb68cd`. Its baseline ledger records policy
SHA-256 `4d75914aeefda08f9fc8700290afdbc212eb2cd7990dda138c25b5f3d7d2dfb4`.
The exact same `infra/m7-staging/egress.nft.in` bytes are present at reviewed
main merge `10f12c5cc693217dc1ec5be0b9f2d424fbae2369` (PR #19).
The new helper pins this digest and loads those unchanged bytes through stdin.

The original namespace creation script was not recovered. Historical topology
showed only loopback, down, without addresses/neighbors/routes. The recovered
`restore-batch.json` deletes an existing table first; it is not a fresh-namespace
installer and is not used here. Historical inode `4026532335` is not an expected
current identity. The owner-reported manual host terminal exposed systemd and
the expected IP, while `ip netns list` showed no registered namespace. The Codex
agent's restricted context was separate and could not establish host visibility.

## Exact proposed scope

`workers/scripts/restore_oms_staging_baseline.py` is a new standalone stdlib
operator tool. No default invocation mutates anything. There is no installer,
service registration, systemd change, reboot persistence, model route, grant or
runtime-agent wiring. It cannot recover or certify previous execution evidence.

Future authorization must name the exact reviewed feature head and helper hash,
the fixed host `srv1943844` / `200.234.43.145`, and these resources only:

| Resource | Proposed operation |
| --- | --- |
| `/run/netns/zippy-oms-staging` | Create only if absent, never replace; iproute2 manages its runtime bind mount |
| Fresh namespace policy | Load unchanged `egress.nft.in`; three drop-default chains, four empty sets, exact seven rules |
| `/opt/zippy-m7-restore-RANDOM/` | New root-owned 0700 evidence directory, atomic 0600 receipt and empty 0700 `docker-config/` |
| Same attempt's namespace | Explicit rollback only after receipt, boot, inode, topology and process-use checks |

The empty sets are `provider_v4`, `provider_v6`, `dns_v4`, `dns_v6`.
No links/addresses/routes/neighbors are added, and loopback stays down.
`ip netns add` may create/use `/run/netns` as runtime namespace infrastructure;
this does not add boot restoration. Existing resolver, fixtures, probe files,
units/drop-ins/markers, Git checkout, application services, Docker and host
firewall configurations are not written. No packets, provider calls, credentials,
listeners, synthetic clients or diagnostics are involved.

## Commands to review — NOT AUTHORIZED ON THE VPS

Use an independently verified root-controlled checkout of the final reviewed
feature head, outside the dirty application checkout. `REVIEWED_CHECKOUT` below
is a placeholder to resolve before execution, not a request to fetch/install
anything on the VPS now. Verify helper and policy hashes against reviewed bytes.
Do not execute an arbitrary working copy as root. Do not copy this helper over
the installed diagnostic source bundle.

Passive plan (no host inspection, commands or writes):

```sh
/usr/bin/python3 -I /REVIEWED_CHECKOUT/workers/scripts/restore_oms_staging_baseline.py plan
```

After separate explicit namespace-restoration approval only:

```sh
/usr/bin/python3 -I /REVIEWED_CHECKOUT/workers/scripts/restore_oms_staging_baseline.py apply
```

It prints the unique evidence directory. Use that exact path in place of
`EXACT_EVIDENCE_DIR` for subsequent actions; no glob or guessed historical path.
Read-only re-verification, when separately within the approved scope:

```sh
/usr/bin/python3 -I /REVIEWED_CHECKOUT/workers/scripts/restore_oms_staging_baseline.py verify --evidence-dir /opt/EXACT_EVIDENCE_DIR
```

Explicit scoped rollback, if included in the restoration approval:

```sh
/usr/bin/python3 -I /REVIEWED_CHECKOUT/workers/scripts/restore_oms_staging_baseline.py rollback --evidence-dir /opt/EXACT_EVIDENCE_DIR
```

The only namespace/policy mutations performed internally are:

```sh
/usr/sbin/ip netns add zippy-oms-staging
/usr/sbin/ip netns exec zippy-oms-staging /usr/sbin/nft --check --file -
/usr/sbin/ip netns exec zippy-oms-staging /usr/sbin/nft --file -
# Explicit rollback only, after all ownership/topology/use guards:
/usr/sbin/ip netns delete zippy-oms-staging
```

These are explanatory fragments, not a standalone execution recipe: the helper
supplies digest-checked policy bytes on stdin and runs the surrounding guards.
There is no `delete table`, global flush, host rule write, process kill, link
creation or service/Docker operation in this command sequence.

## Verification, receipt and failure handling

Every active CLI action requires Linux, EUID 0, the exact hostname, PID 1
`systemd`, self network/mount namespace equality with PID 1, and the expected
IPv4 address observed through host `ip -json address`. Hostname/root alone fail.
Commands use fixed executable paths, a clean environment, five-second individual
limits and one shared 90-second deadline. The helper never invokes a shell.

Apply rejects existing namespace paths, including dangling symlinks. It records
ownership only after successful exclusive `ip netns add`, then binds its receipt
to current boot ID, device/inode identity, helper hash and policy hash. Before
loading, require only unaddressed down loopback, no routes/neighbors/users and
an empty ruleset. Checking the policy precedes loading the exact pinned bytes.

Verification compares the entire exported table, chains/hooks/priorities/drop
policies, empty sets/types and ordered rule expressions with the fixed contract.
Only runtime handles and metainfo are excluded; an explicitly empty element list
is equivalent to its omission. Unknown objects, extra rules, populated sets,
changed ports/verdicts/selectors and boolean priority substitutions fail.

Host preservation compares before/after SHA-256 observations of stateless nft
policy (including handles), IPv4/IPv6 iptables rules, host links, local Docker
network inspection and the fixed diagnostic unit/script/resolver/marker/fixture.
Only generated `iptables-save` comment lines are omitted. Raw host/Docker data
is not persisted or printed; receipt contains hashes. Docker reads use the fixed
local Unix socket and an explicit empty config directory, not inherited endpoint
or operator configuration. These are local read operations, not registry calls.

Unexpected concurrent Docker/firewall changes produce NOT_VERIFIED. Do not
restore a host snapshot to force equality. This tool is for an exclusive operator
window; checks do not prevent malicious or concurrent root from replacing a
namespace between operations. A root-owned receipt is local ownership evidence,
not a trusted provider execution authorization or protection against hostile root.

On an ordinary failure, write NOT_VERIFIED and retain the receipt and any newly
created namespace. There is no automatic deletion or retry. A failed/ambiguous
namespace-add command does not confer ownership; a process crash may leave an
IN_PROGRESS receipt. Both require manual review, never a guessed cleanup claim.

Rollback accepts only a private root-owned regular single-link receipt from
the current boot, matching source/hash and the same newly created namespace
device/inode. Refuse IN_PROGRESS, REMOVED, stale, replaced or uncertain records.
Require topology still empty and `ip netns pids` empty, then recheck ownership
immediately before deleting that name. Never kill users or delete a conflicting
namespace. Retain evidence and the empty Docker config after rollback. A later
host-preservation mismatch is reported even if owned namespace removal succeeded;
the receipt's REMOVED state distinguishes that outcome. Never edit receipts to
force verification or remove ownership guards.

Acceptance is LOCAL_BASELINE_CHECKS_PASSED / BASELINE_VERIFIED only. It does not
prove effective external egress, sandboxed process identity, credential/state
isolation, an enforced monetary cap or trusted endpoint-bound one-use authority.
Fresh credential-free diagnostic, synthetic activation, live M7 inference and
Qwen fallback remain separate execution gates. D-33 remains pending; every refund
still requires manual approval.

## Disposable validation boundary

Unit regressions use fake local commands only. The dedicated GitHub-hosted
Ubuntu 24.04 job creates this fixed name only on its disposable runner, with no
uplink or traffic. Its separate harness refuses the production hostname/IP and
requires hosted-CI markers and root. It exercises the operational core after
that CI gate, not a production CLI bypass; the production CLI has no CI flag.
It proves apply/export/verify, conflict refusal, changed-set rejection, ownership
mismatch, rollback refusal while a bounded sleep fixture uses the namespace,
successful scoped deletion, and injected policy-load failure followed by guarded
partial cleanup. It terminates only its own sleep fixture. Unprovable cleanup
is left for runner disposal rather than deleting an unknown namespace.

References: [iproute2 namespace manual](https://man7.org/linux/man-pages/man8/ip-netns.8.html)
and [upstream nft manual](https://www.netfilter.org/projects/nftables/manpage.html).
