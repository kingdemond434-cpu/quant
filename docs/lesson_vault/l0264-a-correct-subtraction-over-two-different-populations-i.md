---
id: L0264
cost: 23 phantom work items, and an afternoon chasing them
tags: ["counting", "issue-board", "populations", "enrolment"]
---

# L0264

A correct subtraction over two different populations is a wrong number that looks arithmetic. certs:clockless was certified - unrunnable - forward_clocks, where `certified` counts CERTIFICATES and `forward_clocks` counts rows that are NOT TERMINAL -- so every certificate whose clock had been retired or killed appeared as a missing clock. The board advertised 23 work items and told the reader to search the log for refusals that were never issued. Measured on the box: 52 of 52 enrolled, 0 refused, 101 rows across four lanes. Replace the aggregate with a per-certificate join, and return UNMEASURED rather than 0 where the join cannot run.

## Evidence

check_enrolment_gap on the live box: 52/52 passed enrolment, 0 refused, 2 BLOCKED_NO_BARS; dashboard reported forward_clocks=29 and clockless=23

## Tags

#counting #issue-board #populations #enrolment

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0044-removing-a-common-factor-manufactures-negative-residua]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0061-before-grading-a-cross-venue-join-defect-check-whether]]
