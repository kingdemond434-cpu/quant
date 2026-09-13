---
id: L0296
cost: slow
tags: ["staleness", "wiring"]
---

# L0296

Staleness on this desk has exactly three causes and they need different fixes: (1) NO CLOCK -- the organ was built and never scheduled; (2) THE CLOCK RUNS AND THE ORGAN EXITS NON-ZERO -- read the log, the artifact keeps its old internal stamp while its mtime refreshes from adopt; (3) THE ORGAN RUNS AND REWRITES WITHOUT REFRESHING updated_at. Check mtime AND the internal stamp AND the task's last result code before concluding anything -- any one of the three alone gives the wrong answer.

## Evidence

2026-09-13: heal_orphaned_clocks.py calls itself a STANDING FIXER and is scheduled nowhere (cause 1). MT5-Shadow rc=1 with a fresh mtime from Adopt-Release restoring the file from HEAD (cause 2) -- a mirror-side read showed mtime 09-12 while the box showed 09-13. Board timestamps read from internal fields, not mtime, so the two disagree by design.

## Tags

#staleness #wiring

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0030-knowledge-that-is-not-injected-at-runtime-does-not-exi]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
