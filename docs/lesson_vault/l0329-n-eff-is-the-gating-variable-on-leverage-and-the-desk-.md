---
id: L0329
cost: capital
tags: ["risk", "portfolio"]
---

# L0329

n_eff is the GATING VARIABLE on leverage, and the desk's is unmeasured on the real book. Never import a leverage figure from a fund whose diversification you have not matched: extreme leverage is survivable only because thousands of near-independent bets make the aggregate so, and that precondition is a measurement, not an aspiration. Measure n_eff on the live book BEFORE any leverage argument is entertained.

## Evidence

2026-09-14: Renaissance Medallion runs roughly 12.5x exposure (Senate records, ~10% own capital). This desk's measured n_effective is 5.592 with mean |pearson| 0.163 and a ceiling of 6.1 -- about six effective bets. data/strategy_paths.json now exists but portfolio_monte_carlo needs 60 common daily marks and the forward window holds 19, so dependence_blindness on the REAL book is still UNMEASURED and resolves around 2026-10-26.

## Tags

#risk #portfolio

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
