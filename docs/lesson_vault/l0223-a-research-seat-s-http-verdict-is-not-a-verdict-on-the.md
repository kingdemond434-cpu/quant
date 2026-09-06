---
id: L0223
cost: blind
tags: ["ops"]
---

# L0223

A research seat's HTTP verdict is not a verdict on the desk's collector for the same host: seats and production collectors send DIFFERENT User-Agents, so their blocks are independent facts and neither may be inferred from the other. Check the collector's own UA and its artifact's max OBSERVATION date before filing 'the collector is dead' -- and never read your own successful probe as proof a collector is healthy.

## Evidence

api.stlouisfed.org 2026-08-28: UA 'ClaudeBot (quant research desk)' -> 403 Access Denied, while 'Mozilla/5.0' and 'curl/8.0' -> 400 (normal missing-key error). scripts/collect_fred_macro.py:59 sends 'quant-fred/1.0', is unaffected, and data/fred_macro.json carries max observation 2026-08-27. I nearly filed a wired daily collector as silently dead.

## Tags

#ops

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
