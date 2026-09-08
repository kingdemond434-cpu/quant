---
id: L0267
cost: nine of eleven research arms allocated on price alone
tags: ["bandit", "research-allocation", "clamp", "breadth"]
---

# L0267

An asymmetric clamp does not neutralise a signal, it keeps half of it. The research bandit clamped a cold arm with `min(ratio, pooled_ratio)`, which removes a CHEAP arm's price advantage and leaves an EXPENSIVE arm's price penalty untouched. With `worth` flat at 1.0 across all arms -- which it was, because the marginal-dElogW source needs an artifact this host does not have -- the score reduced to p_pooled/cost and corr(share, 1/cost) came out +0.87. The arm owning all 11 empty alpha clusters got 5.81%; the arm that ensembles sleeves the book already holds got 13.57%. Use assignment, not `min`, when the intent is 'this signal does not apply here'.

## Evidence

RESEARCH_BANDIT.json 2026-09-04: worth=1.000 for all 11 arms, born=0 for 9 of them; after the fix corr(share,1/cost) = -0.38 and breadth-buying arms went 20.6% -> 54.6%

## Tags

#bandit #research-allocation #clamp #breadth

## Related

- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0048-rank-when-the-source-is-noisy-z-score-when-it-is-expen]]
- [[l0058-check-the-as-of-date-of-a-ratio-s-denominator-separate]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
