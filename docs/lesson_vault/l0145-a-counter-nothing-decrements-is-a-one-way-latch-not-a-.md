---
id: L0145
cost: blind
enforced_by: tests/ops/test_seat_blank_recency.py::TestTheFenceClearsWhenTheSeatRecovers::test_old_blanks_alone_no_longer_fire
---

# L0145

A counter nothing decrements is a one-way latch, not a detector. Any fence keyed on a lifetime tally fires forever once it crosses the bar, whatever the subject is doing now -- ask of every threshold counter: what makes this go DOWN?

## Evidence

seat_blanks in build_audit_coverage only increments and nothing resets it, so seat-chronic-nemotron-3-super-120b-a12b fired every run at lifetime 4 while free_roster_canary showed the seat alive and answering 4/4. Its recommendation is to SWAP a live seat off an already under-driven roster.

## Enforced by

`tests/ops/test_seat_blank_recency.py::TestTheFenceClearsWhenTheSeatRecovers::test_old_blanks_alone_no_longer_fire`

## Related

- [[l0046-split-gates-by-what-forward-data-can-repair-structural]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
- [[l0071-a-negative-exit-code-is-a-verdict-about-the-box-never-]]
- [[l0079-grep-for-a-governance-flag-s-consumers-not-its-writers]]
- [[l0081-persist-accumulated-state-in-a-finally-never-only-at-t]]
