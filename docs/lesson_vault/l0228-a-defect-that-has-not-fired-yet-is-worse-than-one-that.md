---
id: L0228
cost: blind
tags: ["verification"]
---

# L0228

A defect that has not fired yet is worse than one that has: verify a pipeline claim by CALLING the function, never by scanning its last output artifact. An artifact written before the break looks exactly like a healthy one, and the break behind you gets noticed while the break scheduled for tonight does not.

## Evidence

2026-08-29 BRAIN s9: s8 read edge_search_results.json and reported ZERO ext_ features; the same file holds 3390/3543 (95.7%) ext_ hypotheses over 1730 names, nested at params.feature. A direct call to resolve_inputs() raises TypeError for AUDUSD, XAUUSD AND ADAUSD -- the 24 tz-aware parquets landed 2026-08-28 23:55, AFTER that artifact was written, so the NEXT run deletes 95.7% of its own hypotheses with one swallowed print as the only symptom. R0719.

## Tags

#verification

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0030-knowledge-that-is-not-injected-at-runtime-does-not-exi]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
