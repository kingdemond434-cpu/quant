---
id: L0082
cost: blind
tags: ["research-method"]
---

# L0082

A positive control is not enough -- add a NO-TREATMENT control that isolates each factor alone. A study can recover the known answer perfectly and still be wrong about the effect it was built to measure, because the bug lives in the INTERACTION, not the baseline. And check every argmax against the edge of its own grid before believing it.

## Evidence

R0266's absorbing-Kelly study passed its positive control 12/12 (recovered full Kelly with no barrier, no noise) and still reported 'the two shrinks DOUBLE-COUNT in 12/12 cells' -- a confident wrong number. Only CONTROL A (estimation noise, NO barrier) exposed it: f* stayed at 1.00, proving E[logW] is linear in mu and that the shift came from the absorbing floor capping downside at log(barrier) while upside stayed unbounded, i.e. a 1-year-horizon convexity artifact. A separate first version also fixed kelly_lev=1.0, putting the true optimum at 3.93x and 6.02x for S=1.5/2.3 outside a grid capped at 3.0 -- two cells would have reported their argmax AT THE GRID EDGE. scripts/study_absorbing_kelly.py, docs/research/absorbing_kelly_study.json

## Tags

#research-method

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0013-positive-ic-is-not-a-profitable-strategy-ic-lives-mid-]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
