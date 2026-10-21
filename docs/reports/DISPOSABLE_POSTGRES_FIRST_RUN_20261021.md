# First disposable PostgreSQL proof — 21 October 2026

## Source and authorization

Owner Gopinathan / Gopi-git-bit requested PR #32 merge and PostgreSQL verification.
PR #32 merged at `b0a6579d5fdb14e4093be350e06b2e214c4346fc`.
All five post-merge checks passed in [CI 39639034033](https://github.com/Gopi-git-bit/New-logistic-/actions/runs/39639034033).
Checkout/upload pins were read from their upstream commits before dispatch.

One [proof run 39639263651](https://github.com/Gopi-git-bit/New-logistic-/actions/runs/39639263651),
attempt 1, was dispatched as Gopi-git-bit with a 45-minute expiry.
Admission passed. The bounded runner returned NOT_VERIFIED during PREFLIGHT.

## Verified failure evidence

The retained [artifact 12364866321](https://github.com/Gopi-git-bit/New-logistic-/actions/runs/39639263651/artifacts/12364866321)
was downloaded and its ZIP SHA-256 verified:
`f788a5d5b2f10802c983e00ca0fc19755442c1496ca5f93e6b414edded5edc57`.

The summary records:
- Exact source/workflow SHA and accepted CI run above.
- Host port 5432 absent; Docker/Compose checks exited 0.
- First Git source command exited 128; failure COMMAND_FAILED.
- Empty phases array: **zero of the 72 integration cases verified**.
- Private cleanup PASS. No phase resources or proof image were created.
- Provider calls 0; publication false.

The public summary deliberately omits raw command output. Consequently the
artifact establishes the failed command and stage, not its private stderr.
The ownership diagnosis is supported by code inspection and a local reproduction:
the root proof executor discards global Git config while checkout is runner-owned.
Git rejects a different-owner checkout with exit 128; exact-path command-local
safe.directory permits the read. Do not claim private runner stderr was recovered.

## Correction and verification

prepare_source now adds `-c safe.directory=<resolved checkout>` to its four
read-only Git operations. It writes no global/local trust config, uses no wildcard,
and preserves exact HEAD, clean-worktree and committed-byte checks.
A real local Git regression forces different-owner checking, verifies initial
denial, successful source preparation, continued denial without the override for
both the original and a second checkout, and dirty-source rejection.

All **115 offline harness tests** pass, plus scoped Ruff lint/format and strict
typing for the changed runner. These are guard tests, not database proofs.

A corrected proof requires the fix to be reviewed/merged, green exact-merge CI
and a fresh source-bound execution authorization. This report does not replay
the consumed run. All 72 cases remain outstanding; Xano behavior is unaffected.
Publication, migration, live M7 and Qwen remain disabled.
