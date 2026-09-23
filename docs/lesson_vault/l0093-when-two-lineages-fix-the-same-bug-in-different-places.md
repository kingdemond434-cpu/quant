---
id: L0093
cost: slow
---

# L0093

When two lineages fix the same bug in different places, a merge can keep NEITHER: lineage A fixed the sub-daily sharpe ceiling at the call site, lineage B moved it into the harness and deleted A's copy; the merge took A's harness + B's caller and the rule existed NOWHERE, while git log -S showed only the ADD (history simplification hides merge-side drops). Pin the INVARIANT with an end-to-end behavioral test on the output artifact, never the code location -- location tests break on legitimate refactors and go silent on merge deletions.

## Evidence

9e11c7d restoring d10a8b4's eff_sharpe_ceiling; 4 tests red 6d (moat positive control dead); 22/27 moat verdicts SUSPECT-LOOKAHEAD; git log --full-history -S eff_sharpe_ceiling showed only the add

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
