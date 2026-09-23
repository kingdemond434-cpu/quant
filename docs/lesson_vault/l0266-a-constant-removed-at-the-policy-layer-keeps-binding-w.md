---
id: L0266
cost: a removed cap that removed nothing for two days
tags: ["heat", "ceiling", "money-path", "dead-removal"]
---

# L0266

A constant removed at the POLICY layer keeps binding wherever it is also the SAMPLER or the READER. HEAT_HARD_CEILING was retired as the heat law on 2026-09-05 and `measured_ceiling` was rewritten to read the bound off the growth curve -- and the removal was completely inert, because the free optimum was still solved with `hard_cap=HEAT_HARD_CEILING` (so 'what growth wants' could not be REPORTED above 30%), the state curves skipped every grid point above it, `decision_core.allocator_heat` rejected any artifact total above it, and `cap_by_heat` clamped the budget at it a second time. When retiring a bound, grep every use and classify each as policy, sampler, or reader: only the policy one is the law, and the other three enforce it silently.

## Evidence

5 live binding sites found on 2026-09-07 after the 2026-09-05 removal; corr(share, 1/cost)=0.87 was the analogous defect in the research bandit

## Tags

#heat #ceiling #money-path #dead-removal

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0036-a-0-guard-does-not-survive-floating-point-dust-use-a-m]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
