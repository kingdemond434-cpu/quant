---
id: L0316
cost: blind
tags: ["wiring", "measurement"]
---

# L0316

Always pass encoding='utf-8', errors='replace' when capturing a subprocess with text=True. text=True alone decodes with the system locale (cp1252 on Windows) while git and most tools emit UTF-8, and the UnicodeDecodeError is raised inside subprocess's READER THREAD where the caller cannot catch it -- the capture is lost and the process exits non-zero having printed nothing.

## Evidence

2026-09-14: all three pre-commit hook scripts (moneypath_precommit_guard, check_moneypath_fence, check_protected_records) captured git this way. A staged diff over 79 paths carried byte 0x81 at offset 122398, the guard crashed, the hook returned non-zero, and EVERY commit on the trading box failed -- including Adopt-Release's, the only durable path from origin to the machine that trades. Visible symptom: a scheduled task reporting result 1 with an empty error.

## Tags

#wiring #measurement

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0050-before-trusting-any-imported-statistical-construction-]]
