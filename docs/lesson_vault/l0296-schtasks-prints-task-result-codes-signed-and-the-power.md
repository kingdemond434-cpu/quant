---
id: L0296
cost: blind
tags: ["ops", "monitoring"]
---

# L0296

schtasks prints task result codes SIGNED and the PowerShell cmdlets print them UNSIGNED, so the same outcome appears as two different numbers. Normalise to one canonical form before any verdict, or a monitor reports healthy tasks as failing depending on which tool read the row.

## Evidence

2026-09-12: ops/process_health.py's first run called MT5-Hourly, MT5-LocalDashboard and MT5-MoatRecorder-Watchdog FAILING while all three were RUNNING -- 267009 was recognised and its signed sibling -2147020576 was not. Three false alarms in eight rows teaches the operator to scroll past the board.

## Tags

#ops #monitoring

## Related

- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0065-a-green-local-gate-proves-nothing-unless-the-installed]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
