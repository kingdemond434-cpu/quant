---
id: L0335
cost: capital
tags: ["execution", "wiring"]
enforced_by: desks/mt5/tests/test_family_params_from_certificate.py::test_the_roster_carries_the_certificate_to_the_executor
---

# L0335

When a sleeve reports NO SIGNAL, prove the signal function was given its certified parameters before believing it. A family called with empty params returns an empty list forever, which is indistinguishable from a quiet market and is therefore logged by nothing. Check the whole chain -- registry row, roster dict, call params, resolved inputs -- because a constructed dict is a whitelist and drops silently whatever nobody thought to add.

## Evidence

2026-09-14: 53 LIVE forex sleeves, armed since 2026-09-11, heat-capped in at 20.2%, had sent ZERO orders ever (59 intents on record, all XAUUSD); E8 was armed with a green guard and sent 0 of 20, every row NO_SIGNAL. One cause, three layers: roster() built a new sleeve dict and omitted ; _family_call_params read s['params'] which no row has; e8_executor spread a nested {condition, params} envelope through a scalar-only filter that also dropped list-valued . Fixed with a docket join VERIFIED by re-hashing to the certificate's cell id. Measured after: 52 of 53 gateway sleeves resolve, 351 signals over 8 sleeves where there were 0; E8 book 0 -> 681 signals, 16 of 20 producing.

## Enforced by

`desks/mt5/tests/test_family_params_from_certificate.py::test_the_roster_carries_the_certificate_to_the_executor`

## Tags

#execution #wiring

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
