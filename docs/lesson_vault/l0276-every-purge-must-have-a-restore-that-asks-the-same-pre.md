---
id: L0276
cost: capital
tags: ["certification"]
enforced_by: desks/mt5/tests/test_certificates_cannot_be_lost_to_an_outage.py::test_a_row_comes_back_only_when_the_reason_that_retired_it_no_longer_holds
---

# L0276

Every purge must have a restore that asks the same predicate the other way, on every pass. A transient outage in one input must never permanently delete evidence that took weeks of forward time to earn.

## Evidence

2026-09-04 universe registry collapsed to a 23-symbol stump; ~60 certificates retired as untradeable; registry restored the same day, certificates never were. Canon 66 in the repo, 5 on the board, 40 forward clocks RETIRED_ORPHAN on 2026-09-08.

## Enforced by

`desks/mt5/tests/test_certificates_cannot_be_lost_to_an_outage.py::test_a_row_comes_back_only_when_the_reason_that_retired_it_no_longer_holds`

## Tags

#certification

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
- [[l0071-a-negative-exit-code-is-a-verdict-about-the-box-never-]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
