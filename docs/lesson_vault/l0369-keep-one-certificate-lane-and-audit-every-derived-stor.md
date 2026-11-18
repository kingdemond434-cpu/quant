---
id: L0369
cost: capital
tags: ["governance", "promotion"]
enforced_by: desks/mt5/tests/test_certificate_truth.py::test_the_fence_fails_on_residue_and_passes_once_the_lane_is_the_truth
---

# L0369

Keep ONE certificate lane and audit every derived store against it: external_gauntlet.py writes UNIVERSAL_SURVIVORS.json under the exact ten-gate attestation, promoter.py reads it, and the survivors ledger, sleeve registry, shadow and lane states, sleeves.json and forward_reconcile.json are DERIVED -- a row in any of them the lane (or its power-cure candidates) does not back is a divergence, never a second truth. Certificate discovery is banned: no discovered-family certificate, cure candidate, claim, clock or live sleeve may stand; research/certificate_truth.py publishes every divergence hourly to reports/CERTIFICATE_TRUTH.json, its one-time --apply moves the discovered residue to data/certificate_history.jsonl (status RETIRED, reason named) and retires every unbacked clock with the lane's reason, and scripts/check_certificate_truth.py fails the law gate on any residue. The split-brain symptom is stores that each count differently (n=0 in the canon while the registry holds hundreds of LIVE clocks); the fence catches it by comparing the stores to the lane instead of trusting whichever one an organ opened.

## Evidence

measured 2026-09-22 on the trading box: UNIVERSAL_SURVIVORS.json n=0 while sleeve_registry.json held ~693 clocks, 124 of the banned discovered family; on the build box the audit found 56 banned certificates (canon + seal), 21 banned cure candidates, 36 banned claims, 46 banned clocks, 24 banned live sleeves and 58 unbacked clocks; desks/mt5/research/certificate_truth.py, scripts/check_certificate_truth.py, hourly_cycle:certificate_truth

## Enforced by

`desks/mt5/tests/test_certificate_truth.py::test_the_fence_fails_on_residue_and_passes_once_the_lane_is_the_truth`

## Tags

#governance #promotion

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0010-textbook-mechanisms-on-daily-bars-are-picked-clean-spe]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
