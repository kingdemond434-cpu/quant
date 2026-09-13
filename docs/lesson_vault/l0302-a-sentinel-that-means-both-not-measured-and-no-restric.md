---
id: L0302
cost: capital
tags: ["governance"]
---

# L0302

A sentinel that means BOTH 'not measured' and 'no restriction' will eventually apply no restriction. Never let None do both jobs on a gate: make the unmeasured case its own value and fail CLOSED, and never put the rule that leads a file behind an off-by-default flag.

## Evidence

2026-09-14 e8_book.select(tradeable=None) read None as 'apply no venue filter'; the scheduled task runs e8_book.py with no args so --live-venue was never passed, and rule 1 of the file's own docstring (the venue must list it) never ran on any scheduled pass. 8 of 24 slots on the live $100k E8 account held Scandi/EM crosses E8 does not carry; n_blocked_by_venue published 0, meaning 'I did not look'.

## Tags

#governance

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0034-never-slide-a-signal-parameter-to-clear-an-observation]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
