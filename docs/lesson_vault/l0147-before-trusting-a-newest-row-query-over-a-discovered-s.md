---
id: L0147
cost: blind
tags: ["governance"]
enforced_by: tests/research/test_campaign_retention.py::TestTheSubjectCannotBeOutbidByAnotherPopulation::test_a_fresher_foreign_plan_does_not_hide_a_stale_subject
---

# L0147

Before trusting a 'newest row' query over a DISCOVERED scope, ask whether two producers can write the same key. If they can, the query has no subject: name the subject in code and group by producer, or a second population silently takes over the metric and every read stays individually honest.

## Evidence

check_campaign_retention judged the newest campaign_strata row across all audit stores. sor_research writes ~90 k=1 rows/day at 100pct retention; sor_crypto (the subject it was built to floor) writes one. Measured 2026-08-13: the subject had been silent 170.9h and the fence reported 'OK ... plan 23.0h old' at 100pct. Fixed in 814d01fd.

## Enforced by

`tests/research/test_campaign_retention.py::TestTheSubjectCannotBeOutbidByAnotherPopulation::test_a_fresher_foreign_plan_does_not_hide_a_stale_subject`

## Tags

#governance

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0024-judge-a-source-by-whether-it-carries-measured-data-not]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
