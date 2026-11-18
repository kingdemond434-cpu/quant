---
id: L0351
cost: capital
tags: ["ops", "migration"]
---

# L0351

A migration is not done when the new box trades; it is done when the OLD box cannot. Disable every scheduled task and write data/GATEWAY_PAUSED on the source box the same hour the destination is armed, and verify by reading the source box's own gateway log -- two gateways with different rosters on one account is churn that looks like bad edges.

## Evidence

local schtasks 2026-09-16: MT5-Gateway Ready last 11:47 result 0, local gateway.log 09:46:53Z 'state: armed=True pos=9 pending=4 sleeves=36' while the big box ran the same live Fusion account with a 65-row roster; local Adopt-And-Seal PowerShell at 2,388 MB, free memory 69 MB

## Tags

#ops #migration

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0029-two-pids-with-matching-args-are-not-two-processes-unti]]
- [[l0050-before-trusting-any-imported-statistical-construction-]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
