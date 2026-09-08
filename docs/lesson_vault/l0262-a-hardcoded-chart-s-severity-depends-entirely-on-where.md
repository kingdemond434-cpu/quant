---
id: L0262
cost: mined strategies tested on the wrong chart
tags: ["timeframes", "miners", "grading", "false-negative"]
---

# L0262

A hardcoded chart's severity depends entirely on where it sits, so grade the hits, never count them. A raw grep reports ~330 and is useless. Four of those are `"timeframe": "H1"` written as a DEFAULT in miner sources, which flattens the chart a strategy was actually described on before the docket ever sees it -- so a cell hunted on M5 is replayed on H1 bars and its failure reads as 'this mechanism does not work' rather than 'it was never tested'. Those four matter more than the other three hundred together.

## Evidence

PIPELINE 280, MINER_SOURCE 4, OTHER 39, THROWAWAY 33

## Tags

#timeframes #miners #grading #false-negative

## Related

- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0061-before-grading-a-cross-venue-join-defect-check-whether]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
