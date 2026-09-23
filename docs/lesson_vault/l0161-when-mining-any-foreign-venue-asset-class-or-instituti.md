---
id: L0161
cost: blind
tags: ["mining"]
---

# L0161

When mining any foreign venue, asset class or institution, extract its RATIOS, not its THRESHOLDS. A threshold is asset-class-bound and does not travel; a ratio of two like-measured quantities is dimensionless, so annualisation, cost base, return definition and periodicity all cancel and it travels intact. Corollary for source selection: a TRANSCRIPT or talk states thresholds, while an API, schema or config states the measurement NAMESPACE -- so when both exist, mine the API for what they MEASURE and treat the talk only as evidence of where they set bars.

## Evidence

libs/validation/brain_calibration.py imported BRAIN's Sharpe target 1.25, fitness bar 1.0 and self-correlation cap 0.7 from a webinar transcript, then spent 10 lines of its own docstring warning the numbers are US-equity-bound and 'COMPARABLE IN ORDER OF MAGNITUDE ONLY'. rocky-d/wqb (MIT) read 2026-08-13 shows the same platform exposes os.osISSharpeRatio, os.sharpe60/125/250/500, os.preCloseSharpeRatio and is.prodCorrelation -- dimensionless instruments the caveat does not touch. Desk grep: zero hits for the first two families, prodCorrelation absent, so the un-portable half was imported and the portable half was never seen.

## Tags

#mining

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0011-the-real-edge-oos-sharpe-band-is-0-5-1-5-a-backtest-sh]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0013-positive-ic-is-not-a-profitable-strategy-ic-lives-mid-]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
