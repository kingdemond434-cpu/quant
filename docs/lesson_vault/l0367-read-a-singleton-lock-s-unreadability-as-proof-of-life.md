---
id: L0367
cost: blind
tags: ["ops"]
enforced_by: desks/mt5/tests/test_clock_fixer.py::test_an_unreadable_lock_is_a_HELD_lock_not_a_dead_resident
---

# L0367

Read a singleton lock's UNREADABILITY as proof of life, never as death: the resident holds a Windows byte-range lock on byte 0 of its own lock file, so PermissionError on read means a live process owns it. The clock fixer treated the OSError as 'no holder' and reported twenty-two healthy residents DEAD, restarting them every fifteen minutes. 'I cannot read it' and 'nobody holds it' are opposite facts and must never share a code path.

## Evidence

desks/mt5/research/clock_fixer.py _lock_state; measured 2026-09-17 on the box: every dept_* lock raised PermissionError while its resident ran

## Enforced by

`desks/mt5/tests/test_clock_fixer.py::test_an_unreadable_lock_is_a_HELD_lock_not_a_dead_resident`

## Tags

#ops

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
