---
id: L0303
cost: blind
tags: ["research-loop", "rotation"]
---

# L0303

A rotation cursor that only some code paths stamp will never rotate. If work moved to a parallel worker, the record of that work must move with it.

## Evidence

2026-09-12: _built_syms was stamped only in the serial loop while an 8-worker pre-warm did all the building, so built_fresh was 0, _save_build_cursor returned at its `if not built` guard, and the cursor never advanced. Every sweep re-sorted by an unchanged cursor and rebuilt the same head: 20,352 cells with 7,923 judged and the same 11,146 deferred, every hour, forever.

## Tags

#research-loop #rotation

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
