# Reading list — literature to READ, never to crawl (2026-09-16)

The miner converts structured disclosure and prose that names a registered family with exact
parameters. A research paper never carries either, so crawling one converts at zero by
construction (measured: AQR Research 2 rows → 0, Man Institute 2 rows → 0, Kakushadze & Serur
1 row → 0). These sources were moved out of `deep_forest_sources.json` (`reading_list` block) and
into this file. What they change is what the desk BUILDS; the testable mechanisms they name were
donated as structured hypotheses in `desks/mt5/data/intelligence/literature/` (compiled as
STRUCTURED_HYPOTHESIS, judged by the same ten gates as everything else).

| Source | What to take | Where it landed |
|---|---|---|
| AQR — *Time Series Momentum* (Moskowitz, Ooi, Pedersen 2012); *Value and Momentum Everywhere* (Asness, Moskowitz, Pedersen 2013); *Carry* (Koijen, Moskowitz, Pedersen, Vrugt 2018); Asness on multiple testing | trend and carry across FX / commodities / indices with vol scaling; the multiplicity discipline the sealed campaign constant already enforces | `trend_ma_cross`, `momentum_volgate` donations across classes; carry needs the swap table (not a price-only family) |
| Man Institute (Man AHL research) | trend following with volatility targeting; transaction-cost and capacity work; they publish negative results | `momentum_volgate`; cost model already bound at certification (`cost_surface`, `cost_bias_r`) |
| Kakushadze & Serur — *151 Trading Strategies* (2018) | a catalogue of the price-only families the desk hunts: session breakouts, overnight drift, day-of-week, RSI/Bollinger reversion, volatility squeeze, pullbacks, failed breakouts, level breakouts | donations for each family it names |
| Kakushadze — *101 Formulaic Alphas* (2016); Guotai Junan Alpha191 (2017) | the OPERATOR vocabulary (`ts_rank`, `delta`, `decay_linear`, `corr`, `signedpower`) for automated factor generation; the factors themselves are cross-sectional equity and do not transfer | grammar for `joint_genome` / `formula` families (existing) |
| Transtrend (Diversified Trend Program), Aspect Capital, Quantica Capital notes | position size depends on what else is in the book; ~400 markets of futures/FX; correlation regimes | `leg_balance`, `_corr_abs` factor blend, macro regime kernel |
| Winton / David Harding | data quality over model sophistication; hypothesis-first research | the parser bank, PIT stamps, the NO-log |
| FactorMiner (2026), AlphaLogics (2026), Alpha-GPT (2023), warm-start GP for alpha mining (arXiv 2412.00896), AlphaGen, alpha-gfn, AlphaCFG, RD-Agent/Qlib | depth generators: propose only, never judge; multi-seed evaluation before any stochastic learner earns survivor status | not adopted yet — sidecar candidates behind the narrow donation bridge |

## External evidence cards

Cards about other firms' and papers' results live in `docs/research/EXTERNAL_EVIDENCE.json`,
graded by evidence class (live / audited / backtest / simulation / preprint) so a claim from a
single-seed backtest is never read as a track record.
