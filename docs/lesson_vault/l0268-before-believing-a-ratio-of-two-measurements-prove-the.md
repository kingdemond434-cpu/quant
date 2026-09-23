---
id: L0268
cost: would have shifted 28 posterior means down on a producer bug
tags: ["execution", "cost", "provenance", "registry", "ratios"]
---

# L0268

Before believing a RATIO of two measurements, prove they are the same quantity. Pricing execution at each sleeve's own fill hour divided the measured hourly spread by the pooled scalar the replay charged, and produced an 11-16x under-charge on 28 sleeves -- including GBPJPY, a MAJOR cross, at 15x, which flatly contradicted cost_surface's own finding that the error concentrates in the exotics while the majors read clean. The denominator was the defect: 23 of 195 symbols carry median_spread_pts = 0.0 and 241 of 251 carry NO _provenance for that field at all, because three producers write it with three different meanings and a point-in-time symbol_info.spread snapshot is not a median. Gate on provenance, not on plausibility.

## Evidence

universe.json: 10 of 251 symbols have _provenance.median_spread_pts; GBPJPY median_spread_pts=1.0 beside spread_pts_at_collection=7.0 and measured hourly medians of 13-50

## Tags

#execution #cost #provenance #registry #ratios

## Related

- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
- [[l0043-the-crypto-cross-section-is-1-54-independent-bets-raw-]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
