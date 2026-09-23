---
id: L0207
cost: blind
tags: ["data-liveness"]
---

# L0207

Measure a source's liveness on max(observation_date), never on HTTP status, byte count or a vendor publishing stamp -- a stamp NEWER than the last observation proves DISCONTINUATION.

## Evidence

SNB cube rendoblid: HTTP 200, 7534 rows, PublishingDate 2025-09-01, last obs 2025-07-31, while sibling cube zimoma published 2026-08-03 -- the host probe reads GREEN on a frozen dataset

## Tags

#data-liveness

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
- [[l0073-a-rail-s-reference-point-and-a-performance-number-may-]]
