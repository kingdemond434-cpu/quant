---
id: L0262
cost: wasted
tags: ["timeframes", "miners", "grading", "false-negative"]
---

# L0262

A hardcoded chart's severity depends entirely on where it sits, so grade the hits, never count them. A raw grep reports ~330 and is useless. Four of those are `"timeframe": "H1"` written as a DEFAULT in miner sources, which flattens the chart a strategy was actually described on before the docket ever sees it -- so a cell hunted on M5 is replayed on H1 bars and its failure reads as 'this mechanism does not work' rather than 'it was never tested'. Those four matter more than the other three hundred together.

## Evidence

PIPELINE 280, MINER_SOURCE 4, OTHER 39, THROWAWAY 33 [cost as recorded: mined strategies tested on the wrong chart]

## Tags

#timeframes #miners #grading #false-negative

## Related

- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0034-never-slide-a-signal-parameter-to-clear-an-observation]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0052-a-403-from-a-public-venue-endpoint-is-a-user-agent-bot]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0060-rank-a-mined-comment-tree-by-mechanism-keyword-density]]
