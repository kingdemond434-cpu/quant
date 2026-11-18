---
id: L0241
cost: blind
tags: ["reporting", "severity"]
---

# L0241

When you correct a check's TEXT because you learned its finding is more serious than you thought, correct its SEVERITY in the same edit. A check that explains a fault correctly and then reports the opposite verdict is worse than no check -- the verdict is the line a person acts on.

## Evidence

check_gold_live reported the release verdict with INFO severity, written when I believed NEW_RISK_OK gated only the promoted lanes. On finding it also gates gold (gateway.py:2116, in the bracket loop's CALLER) I rewrote the message to 'NOTHING places until this is true ... GOLD is refused by this too' and left it INFO, so it never entered `blocking`. The box then printed that sentence and 'VERDICT: nothing on the money path refuses the gold book' in the same run, with NEW_RISK_OK=False. [cost as recorded: told the principal a live gold book was armed when the gateway was refusing every order]

## Tags

#reporting #severity

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0023-never-accept-done-for-a-human-step-verify-with-the-act]]
