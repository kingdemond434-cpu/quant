---
id: L0174
cost: wasted
tags: ["shared-tree"]
enforced_by: tests/scripts/test_moneypath_precommit_guard.py::test_ssh_trample_refused_state_lands
---

# L0174

Uncommitted work under desks/mt5 has a half-life of MINUTES: the C:-side hourly pusher overwrites VPS-owned code with stale copies at arbitrary times and the sweep commit launders them into history. Commit-and-push each fix the moment its tests pass, and give EVERY re-applied property its own moneypath-fence marker -- a file with one marker can lose a second property invisibly.

## Evidence

2026-08-26 01:19-01:21Z: stale copies of 8 just-fixed files landed mid-session and sweep eb1818f4 committed them within 2 minutes; uncommitted engine swap and gateway patch destroyed and re-done. Fence now 21 markers at 5min cadence; root fix = GAP 134 (C:-side push must exclude *.py)

## Enforced by

`tests/scripts/test_moneypath_precommit_guard.py::test_ssh_trample_refused_state_lands`

## Tags

#shared-tree

## Related

- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0050-before-trusting-any-imported-statistical-construction-]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0068-to-prove-a-failing-test-is-environment-rather-than-you]]
- [[l0069-a-sibling-can-claim-your-l1-x-number-mid-build-check-t]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
