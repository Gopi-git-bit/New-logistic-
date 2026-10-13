# M7 staging credential injection preparation

Base: PR #15 merged at `558fb39e6335624faec7540f2e4f34b0e7124ce4` after
review of `205bedf060132aafef15fc3e7e3b798b5e4438e8`. Owner authorizes preparing
staging credential injection as PR #16. This change remains a disabled diagnostic
preparation, not a credential upload, provider request or production deployment.

## Prepared injection path

The new `zippy-oms-staging-credential-probe.service.in` uses systemd
`LoadCredential=provider-key:/etc/zippy/m7-staging/provider.key`. A separately
approved staging file is copied into the service-private credential directory on
activation; the probe never reads, hashes or authenticates the key contents.
No `.env`, environment API key, literal credential, GitHub secret download or
automatic provisioning is supplied. The clean environment carries no key values.

The metadata mode is explicitly selected with `--verify-staging-credential`.
It runs only after the existing local boundary checks pass. It opens the fixed
system-service directory `/run/credentials/zippy-oms-staging-credential-probe.service`
without following the final directory symlink, then opens only `provider-key`
relative to that descriptor without following the final file symlink. It checks
directory type/owner/private mode and file regularity, target UID, mode 0400/0600,
single link and size 1..2048, matching the provider reader's file contract.
Descriptors are closed and errors redacted. It reads no bytes and makes no sockets
or provider/account requests. Renamed/nonstandard credential directories fail
closed; review a separate platform binding rather than accepting arbitrary paths.

The original credential-free unit/mode stays available without opening any key.
The credential probe has its own `owner-credential-probe-enabled` marker, no
provider state-directory mount, restart policy, installation section or installer.
Its marker cannot enable the provider runner. The provider capability, empty
trusted registry, endpoint/model profile and strict circuit remain unchanged.

## Required installation and evidence

1. Verify the real named host, sealed reviewed source/interpreter and independently
   observed namespace/fixture controls from the PR #15 plan. Preserve existing
   units, namespaces, application worktrees and provider claim state.
2. Establish the dedicated staging key owner/account/scope through sanitized owner
   evidence. A secret named `DEEPSEEK_STAGING_API_KEY` in GitHub Production proves
   only its stored name; do not infer dedication, value validity or target injection.
3. Under separately scoped credential provisioning, place only the approved key
   in `/etc/zippy/m7-staging/provider.key`, root-owned, private, regular, unlinked
   from other files and within the declared size. Validate existing paths before
   writing and refuse replacement/symlinks. Do not paste values, print/log/hash
   them, pass values in argv, source the application's `.env` or restart workers.
4. Review/install only the new diagnostic unit under its exact prepared name.
   Start it only with its separately authorized marker. systemd reads/copies the
   file for injection; the script examines only its metadata. This is distinct
   from the fully credential-free probe and requires approval of that file scope.
5. Capture the dedicated unit's sanitized JSON and source/run identity. Compare
   the observed file UID/mode/type/link/size with the actual running target UID.
   A probe's dynamic UID is not automatically the future provider invocation UID.

`LOCAL_CREDENTIAL_CHECKS_PASSED` / `PRIVATE_STAGING_FILE_OBSERVED` is not M7
readiness, secure-store provenance, key dedication, key authentication, provider
budget or trusted issuer approval. `credential_loaded=false` and
`credential_contents_read=false` refer to the Python probe, not systemd's copy.
The provider's writable claim-store boundary remains unverified because this
probe does not mount it. All other existing positive-control, namespace, egress
and production readiness requirements still apply.

No production service or Qwen fallback is enabled by a green probe. Production
authentication/pricing, reviewed deployment manifest and build/restart/health
evidence remain separate from M7 staging. Enforced spend, dedicated injection,
effective isolation/egress and trusted endpoint-bound one-use authorization are
required before an explicitly authorized single DeepSeek inference. D-33 remains
pending; refunds remain manual.

## Inherited post-merge CI timing correction

PR #15's first post-merge worker job failed one inherited client-initialization
deadline fixture with `OMS_STAGING_GRANT_WINDOW_TOO_SHORT` (490 other tests passed).
Its mock grant had only 100ms of real wall-clock preparation margin. The production
runner correctly denied the expired preparation; the fixture still used real
wall time despite simulating monotonic initialization delay.

PR #16 fixes the fixture by controlling wall time too, while using the actual
window validator and preserving the HTTP prohibition, fixed monotonic deadline,
timeout/cleanup outcomes and drained-task assertions. No runtime timeout or
authorization guard is relaxed. Preserve the failed run and distinguish any
unchanged-source retry from acceptance of this corrected test source.

The same merge-commit CI run `38371544721` passed on attempt 2 with 491 worker
tests and all five jobs successful. The failed first attempt remains evidence of
the fixture issue; the unchanged-source retry is not acceptance of PR #16's fix.

Hostinger installation was not executed: the callable VPS inventory read returned
401 `Unauthenticated.`, and no terminal/installation tool was exposed here. A
working SSH connection or another GPT's access does not transfer to this session.

Reference: [upstream systemd credentials documentation](https://github.com/systemd/systemd/blob/main/docs/CREDENTIALS.md).
Static template validation and mocked private files do not certify runtime
credential copying, VPS isolation or secure injection of the owner's real key.
