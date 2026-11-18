---
id: L0332
cost: hygiene
tags: ["git", "ops"]
---

# L0332

Before acting on a 'branches have diverged by N commits' report, check whether they share a merge base at all. An orphan branch has NO common ancestor, so 'diverged' is the wrong frame, three-dot diffs fail outright, and any merge-base-based convergence rule is permanently unsatisfiable rather than merely unsatisfied.

## Evidence

2026-09-14: desk-sync-clean vs the live branch reported as '6 vs 4336'. git rev-list --max-parents=0 shows 8b4e3315de9 IS the branch root -- it was re-created as an orphan on 2026-09-11 19:43 and holds six commits total. CLAUDE.md's standing rule (merge-base --is-ancestor origin/<desk> origin/desk-sync-clean, merge if false) could not return true and had been silently uncashable for three days. Of 195 differing code files, live held 100, desk-sync-clean 3, and live was newer on every shared file sampled.

## Tags

#git #ops

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
