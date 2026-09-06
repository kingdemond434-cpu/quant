---
id: L0088
cost: blind
tags: ["ops"]
---

# L0088

A guard that fails CLOSED on a missing data file must have that file in git. data/* is gitignored wholesale here, so a fresh clone gives the guard nothing to read and it blocks everything -- and a sleeve that has silently stopped trading looks exactly like a sleeve finding no setups.

## Evidence

R0276: libs/execution/event_guard.py blocks on EMPTY/STALE by design; wiring it while data/event_calendar.json stayed gitignored would have refused every conviction entry on any fresh checkout. Fixed with a !data/event_calendar.json exception plus a monthly idempotent rebuild, and state['event_window'] is now published on every run.

## Tags

#ops

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
- [[l0058-check-the-as-of-date-of-a-ratio-s-denominator-separate]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
