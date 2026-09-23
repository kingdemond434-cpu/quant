---
id: L0056
cost: capital
tags: ["risk"]
---

# L0056

A drawdown rail measures a RATIO -- so an accounting change to its denominator can clear it without any risk falling. Any capital-event re-baseline must either preserve the rail's reference point or re-arm the rail explicitly; never let bookkeeping un-pause a book.

## Evidence

journalctl quant-cashcarry 2026-08-01: 12:10:22 RISK-PAUSE-OPENS drawdown -17.6%<=-15% (net -1860.22, carries=0); 12:22:51 capital_events RESTART +4790.70; 14:19:29 'open BNBUSDT 0.01' -- opens resumed with zero trades in between

## Tags

#risk

## Related

- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
- [[l0073-a-rail-s-reference-point-and-a-performance-number-may-]]
- [[l0074-an-alarm-must-name-the-cause-its-data-supports-never-t]]
- [[l0083-verify-a-shipped-fix-against-a-key-only-the-new-code-c]]
- [[l0144-a-persistently-red-test-is-a-disabled-gate-so-triage-r]]
- [[l0161-when-mining-any-foreign-venue-asset-class-or-instituti]]
