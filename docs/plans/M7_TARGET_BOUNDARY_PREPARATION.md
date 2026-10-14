# Credential-free M7 target preparation

Source base: merged PR #14, `deb0f15de8815e039ef46f1df8c5358b5aefe79a`.
Owner instruction: prepare the isolated M7 staging target first. This change
prepares a reviewable diagnostic target; it does not install or start a service.
The ordinary application deployment and production authentication/pricing remain
separate. No production Compose file or deployment activation is supplied here.

## Why a separate diagnostic target

The passive observer reported no loaded/running `zippy-oms-staging.service` and
unobserved credential/state/firewall metadata. A configured identity is not an
effective process identity. The provider runner cannot be used to discover the
boundary while provider authority and spending evidence are missing.

The new `zippy-oms-staging-probe.service.in` runs the standalone stdlib
`probe_oms_staging_target.py` inside the prepared UID/mount/network boundary.
It uses the same dynamic user, named network namespace, read-only source and
business-path restrictions as the provider template, with
an additional required inaccessible synthetic fixture directory. It uses a clean
environment and isolated Python, no credential directive or provider imports,
no socket operations, no restart policy and no installation section.

Its separate `owner-probe-enabled` condition never satisfies the provider
service's `owner-enabled` condition. Do not copy either marker from the other.
The provider service, empty trusted grant registry, capability denial, strict
circuit and single DeepSeek profile remain unchanged. Qwen remains unwired.

## Concrete installation scope for later review

| Resource | Prepared boundary / required future evidence |
|---|---|
| Host | Existing `srv1943844`, expected IP `200.234.43.145`; verify through the actual connected target before any write |
| Source | Root-owned read-only `/opt/zippy-m7-staging`; include the reviewed probe script and seal its exact bytes; Python/OS/dependencies require separate provenance verification |
| Probe service | `/etc/systemd/system/zippy-oms-staging-probe.service`; reviewed template only, no automatic enable/start |
| Identity/state | Dynamic `zippy-m7-oms`; the probe has no StateDirectory and never opens/reassigns the provider claim store; observed UID is not a promise of the UID allocated to a later invocation |
| Network | Existing separately prepared `/run/netns/zippy-oms-staging` and resolver file; do not substitute the host namespace or alter host OUTPUT/shared Docker networks |
| Synthetic fixture | Root-owned `/var/lib/zippy-m7-denial-fixtures` with mode 0755 and one root-owned `readable.fixture`, mode 0444, containing synthetic text only; do not touch business files |
| Marker | `/etc/zippy/m7-staging/owner-probe-enabled`, only under separately scoped probe-start authority; leave the provider enable marker absent |
| Credentials | None loaded by this probe; dedicated injection, provider account and hard cap remain unverified |

Before preparing resources, inspect their current ownership/type and refuse
to replace existing paths, symlinks, units or namespaces. Preserve the application
worktree, `/opt/paperclip`, databases, containers and shared firewall rules.
Installation does not authorize a provider call, a grant registration or deployment
of the operational API/heartbeat workers. This PR includes no automatic installer.

## Observation and acceptance

The probe refuses root and wrong-host execution before inspecting metadata or
opening the fixture. It reports effective UID/capabilities/no-new-privileges from
its own `/proc` view, the actual explicit read-only source mount, and network,
mount and IPC namespace inodes. It attempts only a nonblocking, no-symlink,
read-only open of the fixed synthetic fixture, closing without reading bytes.
Only EACCES/EPERM records an observed denial; missing paths and other failures
remain unverified. Accessible fixtures or unsafe/missing metadata exit nonzero.

Exit 0 / `LOCAL_CHECKS_PASSED` is deliberately not readiness approval. Readiness,
effective egress, business-path access, spending and trusted authorization remain
UNVERIFIED. The diagnostic service also differs from the provider service by
having no credential or writable state-directory mount and no provider execution;
it cannot prove those later boundaries by substitution.

Before promoting fixture denial to sandbox evidence, a separately authorized
operator must demonstrate the exact fixture can be opened outside the sandbox
by an ordinary non-root identity, without reading contents, and preserve its
metadata/time/control result. A root-only positive control is insufficient.
Compare the probe namespace inode facts against independently observed host and
named-namespace inodes from the same run; a configured namespace path alone is
not effective separation evidence. Capture only this dedicated probe's sanitized
JSON output, never unrestricted logs, environments or credentials.

Effective IPv4/IPv6 destination denial still needs separately scoped synthetic
network controls after reviewing/installing namespace policy. Do not use live
business destinations or provider requests for this step. No account/balance,
model-list or inference call is needed for target preparation.

Acceptance order: code review and exact-head CI; separately scoped resource
installation; controlled credential-free probe and independent positive controls;
effective namespace/egress evidence; dedicated staging injection and enforced
budget; trusted endpoint-bound one-use authorization; explicitly authorized
single-provider M7 live test. Keep inference denied while any applicable gate
is missing. D-33 remains pending; every refund requires manual approval.

Reference: [systemd's upstream systemd.exec documentation](https://github.com/systemd/systemd/blob/main/man/systemd.exec.xml)
defines the template namespace/path/privilege controls. Static template verification and mocked tests
do not demonstrate their installation or effective behavior on the VPS.
