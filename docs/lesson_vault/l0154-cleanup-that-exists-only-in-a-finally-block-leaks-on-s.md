---
id: L0154
cost: hygiene
tags: ["ops"]
enforced_by: tests/scripts/test_law_gate_reaper.py::test_reaps_a_checkout_older_than_any_live_run
---

# L0154

Cleanup that exists ONLY in a finally block leaks on SIGKILL. Any process that allocates scratch must also REAP ITS OWN SPECIES on entry -- prefix-scoped and past a lifetime a live run cannot reach -- or the first OOM kill starts a loop that makes the next one likelier.

## Evidence

2026-08-13: run_law_gate.py:250 removes its 150MB HEAD worktree in a finally, which covers every path the interpreter walks out of and not the one that leaks. Two orphans (300MB, both clean, no process holding them) with MemAvailable at 270MB vs a 400MB floor -- the box could not run its own test suite. Reaping took MemAvailable to 1152MB.

## Enforced by

`tests/scripts/test_law_gate_reaper.py::test_reaps_a_checkout_older_than_any_live_run`

## Tags

#ops

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0029-two-pids-with-matching-args-are-not-two-processes-unti]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
