---
id: L0065
cost: blind
tags: ["environment", "verification"]
---

# L0065

A green local gate proves nothing unless the installed versions match the DECLARED pins. Check before trusting it: an out-of-pin box reports the OPPOSITE verdict from CI, and 'unused ignore' is the direction that deletes a needed one.

## Evidence

2026-08-05: mypy clean locally on pyarrow 25.0.0 vs pyproject's >=24,<25. On the pinned 24.0.0 the two ds.* calls in libs/data/lake.py are no-untyped-call, so ignores deleted that morning as 'unused' were required -- the VPS deploy gate caught it, the local run could not. Same root cause as the pandas 2.3-vs-3.0 straddle.

## Tags

#environment #verification

## Related

- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
- [[l0052-a-403-from-a-public-venue-endpoint-is-a-user-agent-bot]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
