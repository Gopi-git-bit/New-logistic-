# nftables 1.0.9 export regression fixtures

These three JSON documents were captured from actual kernel exports in the
disposable namespace of GitHub Actions run
[38597603993](https://github.com/Gopi-git-bit/New-logistic-/actions/runs/38597603993),
job `115968232728`, on 14 October 2026. The source head was
`5afe4651903c814204b6f855e224fbe0caf2eb1d`; its policies match main at
`5c634eb610a5714cad8ec33f1242184b8e8abdba`.

The runner reported `nftables v1.0.9 (Old Doc Yak #3)`. For each phase it applied
`infra/m7-staging/synthetic-PHASE.nft.json` inside that namespace and captured
`nft --json --handle list ruleset`. The fixtures preserve the captured objects,
handles, selectors and zero counters; JSON indentation was changed for review.

The original comparator rejected all three exports. The actual differences were
removal of redundant `meta nfproto`/`meta l4proto` guards implied by the fixed
payload selectors, and `in` becoming `==` for the established/related reply-state
set. No other security fields were discarded to obtain agreement.

No interfaces, uplink, listeners, clients or provider calls were created. The
namespace was deleted by the workflow's exit trap. These fixtures reproduce
serialization compatibility, not runtime network isolation or effective egress.
