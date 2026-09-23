---
id: L0241
cost: told the principal a live gold book was armed when the gateway was refusing every order
tags: ["reporting", "severity"]
---

# L0241

When you correct a check's TEXT because you learned its finding is more serious than you thought, correct its SEVERITY in the same edit. A check that explains a fault correctly and then reports the opposite verdict is worse than no check -- the verdict is the line a person acts on.

## Evidence

check_gold_live reported the release verdict with INFO severity, written when I believed NEW_RISK_OK gated only the promoted lanes. On finding it also gates gold (gateway.py:2116, in the bracket loop's CALLER) I rewrote the message to 'NOTHING places until this is true ... GOLD is refused by this too' and left it INFO, so it never entered `blocking`. The box then printed that sentence and 'VERDICT: nothing on the money path refuses the gold book' in the same run, with NEW_RISK_OK=False.

## Tags

#reporting #severity

## Related

- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0023-never-accept-done-for-a-human-step-verify-with-the-act]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0061-before-grading-a-cross-venue-join-defect-check-whether]]
