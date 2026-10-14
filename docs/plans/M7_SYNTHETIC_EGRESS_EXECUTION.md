# M7 synthetic control package: review and later execution

This is preparation, not installation or activation authority. PR #17 contains
the client, bounded listener, three exact nftables JSON files, offline evidence
collector, disabled unit templates and this operator protocol. Review the complete
head and its CI before separately authorizing installation/topology and one pair
of control phases. M7 inference, credentials, claim state, fallback and production
remain denied. No provider, account, database, payment or governance call is needed.

## Artifacts and bounds

| Artifact | Contract |
|---|---|
| `probe_oms_synthetic_egress.py` | Passive by default; explicit controls only from the proven zero-capability target; 14 tuples per phase, 16s shared deadline, 1s per tuple |
| `serve_oms_synthetic_peer.py` | Passive by default; `--serve` verifies non-root identity, NoNewPrivileges, read-only source and named peer namespace; all 14 fixed listeners; 40s shared lifetime; fewer than 28 exchanges |
| `oms_synthetic_contract.py` | Fixed family/source/address/transport/port tuples and exact policy expressions; no caller-selected destinations |
| `synthetic-calibration.nft.json` | Only the dedicated target table; all 14 synthetic tuples counted/accepted; other traffic default-drop |
| `synthetic-restricted.nft.json` | Same target table; six positives counted/accepted, eight negatives explicitly counted/dropped; other traffic default-drop |
| `synthetic-peer.nft.json` | Only the new peer table; exact target-to-peer input tuples; established/related replies only; forwarding default-drop |
| `zippy-oms-staging-egress-probe@.service.in` | Separate marker, zero capabilities, fixed named target namespace, 18s oneshot, no restart/boot enablement |
| `zippy-oms-staging-synthetic-peer.service.in` | Separate peer marker/user/namespace, only CAP_NET_BIND_SERVICE for ports 53/443, 42s oneshot, no restart/boot enablement |
| `collect_oms_synthetic_evidence.py` | Passive by default; offline `--evidence-dir` reads only fixed private regular files; correlates all phases without sockets, subprocesses, policy writes or authorization |

The JSON files use explicit `add` commands, never a global flush, NAT, jump to an
unknown chain or host policy. Replies use the fixed synthetic echo protocol, not
HTTP/TLS/DNS/database protocol. The client records only a SHA-256 fingerprint of
each synthetic challenge, not responses or exception text. The peer records the
same fingerprint after echoing, case index and time. No credential is hashed/read.

CI's `M7 synthetic policy check` validates these files using `nft --check` inside
a disposable runner namespace and confirms checking left the ruleset empty.
It then applies each policy there and compares its kernel-exported JSON with the
contract, requiring zero counters. This namespace has no uplink; no peer,
listener or network control runs. Namespace cleanup removes its policies without
changing host rules. This is separate from the required VPS's own parser/kernel
and effective behavior checks.

The comparer accepts two captured nftables 1.0.9 representations: the fixed
`ip`/`ip6` address and `tcp`/`udp` port selectors imply their explicit family and
transport guards, and the exact established/related reply-state set exports
using `==` instead of `in`. Only the entire known selector prefix and exact
reply expression are normalized. Unknown or conflicting selectors, rule order,
ports, addresses, named counters, verdicts, comments and chain settings remain
strict. Before/after handle identity and counter correlation are unchanged.
The recorded CI exports are regression fixtures, not VPS egress evidence.

## Scoped setup protocol, after approval only

1. Verify `srv1943844`, expected IP `200.234.43.145`, reviewed commit/tree and
   fresh host/target namespace identities. Preserve the dirty application checkout,
   `/opt/paperclip`, databases, Docker networks/services, all credentials and state.
   Inspect every destination/parent/type/link/owner and refuse conflicts. No
   package upgrades or host firewall/routing changes are within this scope.
2. Create a new root-owned 0700 evidence directory with 0600 files. Record an
   installation ledger of original source/unit hashes/modes, exact paths newly
   created, namespace identities, target links/addresses/routes/neighbors/rules
   and original drop-default table with four empty destination sets. Capture
   only dedicated metadata; do not dump environments or unrestricted journals.
   Refuse other clients or additional tables in the target namespace.
3. Seal only the four new/updated synthetic scripts plus their reviewed unit
   templates/policies. Keep the installed credential-free PR15 boundary script
   unchanged. Source belongs in root-owned read-only `/opt/zippy-m7-staging`;
   exported policy files and unit candidates must have reviewed hashes. Do not
   copy the whole application checkout or expose its `.env` in the bundle.
4. Create only the new `zippy-m7-synthetic-peer` namespace after proving it absent.
   Create a veth wholly between that peer and the existing target, without ever
   attaching a host interface, bridge, external uplink or default route. The
   following are the fixed commands to review; they are not run by this PR:

   ```sh
   ip netns add zippy-m7-synthetic-peer
   ip -n zippy-oms-staging link add m7ctl-target type veth peer name m7ctl-peer netns zippy-m7-synthetic-peer
   ip -n zippy-oms-staging link set m7ctl-target address 02:00:00:07:00:01 addrgenmode none
   ip -n zippy-m7-synthetic-peer link set m7ctl-peer address 02:00:00:07:00:02 addrgenmode none
   ip -n zippy-oms-staging addr add 192.0.2.1/29 dev m7ctl-target
   ip -n zippy-m7-synthetic-peer addr add 192.0.2.2/29 dev m7ctl-peer
   ip -n zippy-m7-synthetic-peer addr add 192.0.2.3/29 dev m7ctl-peer
   ip -n zippy-oms-staging -6 addr add 2001:db8:7::1/64 dev m7ctl-target nodad
   ip -n zippy-m7-synthetic-peer -6 addr add 2001:db8:7::2/64 dev m7ctl-peer nodad
   ip -n zippy-m7-synthetic-peer -6 addr add 2001:db8:7::3/64 dev m7ctl-peer nodad
   ip -n zippy-oms-staging link set m7ctl-target up
   ip -n zippy-m7-synthetic-peer link set m7ctl-peer up
   ```

   Install permanent neighbors *only on these new links*: target .2/.3 and
   ::2/::3 map to peer MAC `02:00:00:07:00:02`; peer .1 and ::1 map to target MAC
   `02:00:00:07:00:01`. Use `ip -n NAME [-6] neigh add ADDRESS lladdr MAC nud
   permanent dev LINK` for each of the six fixed entries. No IPv6 router/neighbor
   discovery exception is added to the drop policies. Inspect actual addresses,
   neighbors, link peers and both-family routes; unsupported syntax/IPv6 or
   conflicts stop setup and leave evidence UNVERIFIED. Leave loopback unchanged.
5. Validate actual candidate batches with `ip netns exec NAME nft --check --json
   --file PRIVATE_BATCH` before any apply. A target phase batch must contain
   exactly one `delete` of table `inet zippy_oms_staging`, followed by the chosen
   reviewed JSON file's `add` commands. It must replace that table atomically;
   never delete/flush the namespace or global ruleset. Peer creation uses only
   `synthetic-peer.nft.json` inside the independently verified peer namespace.
   Unexpected tables/rules or an absent original target table are conflicts.
6. Install only the two reviewed synthetic diagnostic templates under their exact
   names, with root ownership/private backup/ledger. Validate before reload.
   Create only `owner-egress-probe-enabled` and `owner-synthetic-peer-enabled`
   under the separately approved synthetic scope. Never create provider or
   credential enable markers. Do not enable at boot, restart applications or
   give the target CAP_NET_ADMIN/CAP_NET_BIND_SERVICE.

## Bounded phase and evidence protocol

Perform one calibration and one restricted invocation, at most 28 client attempts
total, with no retry. Start the peer once, require its LISTENERS_READY JSON (all
14 sockets bound), then finish both phases and all eight counter snapshots within
its 40s lifetime. If setup/transition/capture cannot meet the bounds, report a
failed attempt; do not extend deadlines or replay the control run automatically.

Capture the original policy before peer start. Apply target calibration, then
start the peer using `systemctl start --no-block zippy-oms-staging-synthetic-peer`.
After readiness, capture target and peer calibration baselines (all counters
zero), run `zippy-oms-staging-egress-probe@calibration` once, and capture both
post-phase snapshots. Require 14 valid echoes. Ensure TCP connections from that
phase are closed and counters settled before the restricted baseline: stale
packets or any other namespace traffic invalidate attribution.

Atomically apply the restricted target batch; leave peer policy/listeners intact.
Capture target restricted baseline (fresh zero counters) and peer restricted
baseline (identical counters/handles to peer calibration's after snapshot). Run
`zippy-oms-staging-egress-probe@restricted` once, then capture both after snapshots.
Require six echoes and eight timeout-only negatives with exact target drop-counter
increments and no corresponding peer counter/event increments. Permission errors,
refused connections, absent routes, invalid echoes or missing IPv6 are not proof.

Use only `ip netns exec zippy-oms-staging nft --json --handle list ruleset` or
the peer equivalent for these snapshots. Wrap each parsed JSON ruleset with
`captured_at_utc` and independently observed `network_inode`. Timestamps must
bracket the phase and fall within listener health. Preserve object handles;
changed rules/tables/counters, missing selectors or extra permissive rules fail.

Capture each dedicated invocation's JSON through bounded journal reads filtered
by unit, narrow time and report PID. Preserve journald `_SYSTEMD_INVOCATION_ID`
and `_PID` in the wrapper; do not rely on a completed oneshot retaining systemctl
InvocationID. Reject ambiguous/missing runs instead of rerunning. Each phase and
peer wrapper is `{unit, invocation_id, pid, report}`. The listener emits a ready
record and a final record; their identity must match. Wait for its bounded final
record. All 20 echoed challenges must correlate uniquely to the client cases;
negative challenge hashes must never appear at the peer. Wall/monotonic case
timing allows only 250ms correlation tolerance, not extension of network deadlines.

The private evidence directory contains exactly the collector's fixed inputs:

- `manifest.json`: version 1, host, reviewed `source_sha`, exact `source_sha256`
  mapping for all four synthetic scripts, `policy_sha256` mapping for calibration,
  restricted and peer JSON files; fresh host/target/peer network inodes and host
  mount/IPC inodes. Operator-observed `exclusive_target`, `no_uplink`,
  `fixture_positive_control` and `restoration_verified` must all be true.
- `listener-ready.json`, `listener-final.json`, `calibration.json`,
  `restricted.json`: invocation wrappers described above.
- `calibration-before.json`, `calibration-after.json`, `restricted-before.json`,
  `restricted-after.json`, and the four `peer-` prefixed counterparts: snapshot
  wrappers `{captured_at_utc, network_inode, ruleset}`.
- `original-policy.json`, `restored-policy.json`: the same snapshot wrapper in
  the target namespace, before peer start and after cleanup respectively.

Repeat the ordinary non-root fixture open/close control before these runs without
reading bytes, and independently capture fresh host/target/peer identities,
exclusive processes and no-uplink topology. Manifest flags are operator statements;
the offline collector cannot authenticate them or the source commit. Retain their
raw bounded supporting observations privately for manual review. Do not fabricate
missing flags/hashes/timestamps or promote mock fixtures to host evidence.

## Cleanup, restoration and failure handling

After the peer's final record, stop only these synthetic units if still active and
remove only the newly created synthetic enable markers. Bring down the ledgered
`m7ctl-target` link before restoring policy. Prepare an atomic restore batch that
deletes only `inet zippy_oms_staging` and adds the original captured objects:
table first, then chains/sets/counters, then rules in original chain order. Strip
only handles/metainfo from input; preserve all original selectors, empty sets,
counter values and policies. Check/apply only inside the verified target namespace.

Verify the original/restored policy records match (handles/metainfo excepted).
Delete only the ledgered veth, newly created peer namespace/table, new neighbors,
synthetic units/markers and four synthetic script additions/updates as appropriate
to their saved before-state. Restore any approved overwritten client file from
its verified backup. Preserve the pre-existing bundle, fixture, resolver,
credential-free diagnostic and original marker. Validate/reload after unit removal.
Verify original links/routes/no-uplink state and empty sets. Record restored
policy within 120s of peer completion; retain all evidence and before/after hashes.

On a resource/hash/identity conflict, do not overwrite or delete the changed
resource. Leave the owned synthetic link down, stop only identified owned units,
leave provider authority denied, and report partial restoration. Failed cleanup,
missing logs or counter ambiguity prevents accepting the synthetic gate. An
authorization for this protocol is never permission to modify host OUTPUT,
shared networks, production services, credentials, business data or provider state.

After restoration, run the offline collector with isolated Python and the private
evidence directory. It rejects symlinks, FIFOs, hardlinks, wrong ownership/modes,
oversized/duplicate-key JSON and incomplete/mismatched correlation. A valid
record produces `SYNTHETIC_CONTROLS_CORRELATED_REVIEW_REQUIRED`, not readiness or
activation approval. An independently reviewed synthetic proof still does not
establish DeepSeek/TLS/DNS connectivity, staging key scope, hard spending,
provider claim-state isolation or trusted one-use authority. Qwen route/model and
combined budget remain pending. D-33 remains pending; refunds remain manual.

References: [upstream nft manual](https://www.netfilter.org/projects/nftables/manpage.html)
and [libnftables JSON reference](https://manpages.debian.org/testing/libnftables1/libnftables-json.5.en.html).
