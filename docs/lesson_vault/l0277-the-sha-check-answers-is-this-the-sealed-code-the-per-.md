---
id: L0277
cost: blind
tags: ["release"]
enforced_by: tests/ops/test_release_accepts_state_sync.py::test_the_measured_refusal_is_now_an_acceptance
---

# L0277

The SHA check answers 'is this the sealed CODE'; the per-file hashes answer 'is this the sealed STATE'. Classify state directories as state for the SHA diff, or the hourly state-sync commit refuses every seal within the hour.

## Evidence

2026-09-08 gateway log every minute: 'running 92480baa4c66 carries 83 path(s) the sealed release never named' -- all under desks/mt5/data/, all evidence files the sync commits by design.

## Enforced by

`tests/ops/test_release_accepts_state_sync.py::test_the_measured_refusal_is_now_an_acceptance`

## Tags

#release

## Related

- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
