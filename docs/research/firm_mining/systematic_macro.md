# Systematic macro / factor firms: top 20 additions for the MT5 desk

Cluster: AQR, Man AHL / Man Group, Winton, Bridgewater, Aspect, Transtrend, Graham, and CTA-adjacent work (CFM, Duke/Man co-authors).
Machine-readable rows: `systematic_macro.json` has 56 sources, 25 hypothesis rows and 21 capability gaps.

**What the evidence labels mean.**
- DOCUMENTED: the number or claim was read directly in the primary PDF or page.
- REPORTED: stated by the firm, but the detail behind it was not extracted.
- SPECULATED: the step from the source to an MT5 CFD is my own inference.

**How the quotes were checked.**
- Quotes taken from PDFs were compared against the extracted text. The only differences are PDF line-break hyphenation and ligatures.
- Quotes from man.com and transtrend.com pages came through a page-summarising fetch tool. Re-check them before citing them externally.

**How the list is ranked.** Expected contribution of new, independent return mechanisms to the book, weighed against the cost to build and the trial budget spent.

| # | Addition | Kind | Firm / source | Evidence | Why it ranks here |
|---|---|---|---|---|---|
| 1 | **True long-horizon value** (FX: 5-year real-FX change or OECD PPP deviation; commodities: 5-year reversal; bonds: 5-year change in yield) | gap (signal) | AQR, *Value and Momentum Everywhere* | DOCUMENTED | The desk's `style_premia` "value" is a ~6-week mean-reversion, not AQR value. Value is the most diversifying style against a trend-heavy book: its correlation with momentum is −0.64 (*Investing With Style*). |
| 2 | **Value × momentum combo** | gap (combination) | AQR, VME | DOCUMENTED | "much closer to the efficient frontier than either strategy alone". This combo is missing from the COMBOS list. |
| 3 | **Macro momentum composite**: 1-year changes in growth and inflation forecasts, trade-weighted FX, the 2-year yield, and the 1-year equity return | gap (signal) | AQR, Brooks 2017 | DOCUMENTED | Sharpe 1.2 over 1970–2016 with negative correlation to equities. A 50/50 blend with trend reached Sharpe 1.4 and a −12.8% max drawdown. It would be a second independent mechanism for the E8 count. |
| 4 | **1/3/12-month TSMOM blend** (`multi_speed_trend` with speeds 21/63/252 days) across 24 diversified CFDs | hypothesis | AQR, *Century of Evidence* | DOCUMENTED | This is the canonical managed-futures replica: positive in every decade since 1880, and positive in 8 of the 10 largest 60/40 crises. |
| 5 | **Conditional month-end 60/40 rebalancing flow**: short US500 / long UST10Y at month-end when equities are overweight, and the reverse | gap (signal) | Harvey–Mazzoleni–Melone (Man co-authors) | DOCUMENTED | A 1-SD move in the signal predicts −16/−17 bp in equities the next day. The front-running portfolio has Sharpe > 1 over 1997–2023. The forced participant is named. |
| 6 | **Vol-targeted sizing with an EWMA vol known at t−2, applied per asset class** | gap (sizing) | Man AHL, *Impact of Volatility Targeting* | DOCUMENTED | Raises Sharpe for risk assets (indices, credit-like) and thins left tails everywhere. It is two-sided, so it fits Growth Governance Rule 2. |
| 7 | **Similarity regime model** (7 FRED state variables; 15% most similar months, excluding the last 36) | gap (regime) | Man Group, *Regimes* (2026) | DOCUMENTED | Non-parametric and walk-forward-able. Reported alpha from long-similar / short-dissimilar is significant. |
| 8 | **Carry on high-yield FX crosses, quiet-gated** (`carry`) | hypothesis | AQR, KMPV *Carry* | DOCUMENTED | Carry Sharpe is 0.6–0.9 within each asset class and 1.5 diversified. All carry books lose together in global recessions. |
| 9 | **Named macro-series selector for `macro_conditional`** (VIX, 2-year yield change, CPI, real yields) | gap (regime) | Brunnermeier–Nagel–Pedersen | DOCUMENTED | Rows 8, 10 and 12 cannot be expressed without it. A VIX rise coincides with carry unwinds, and a high VIX *level* predicts higher returns for investment currencies. |
| 10 | **Fade extreme COT speculator positioning in carry currencies** (`cot_positioning`, 156 weeks, 90th percentile) | hypothesis | BNP (AQR/Pedersen) | DOCUMENTED | "speculators’ positions increase crash risk" |
| 11 | **Cross-sectional carry ranking from swap history, plus carry1-12 smoothing** | gap (signal) | KMPV | DOCUMENTED | The headline carry results are cross-sectional. For commodities, carry1-12 beats current carry because commodity carry is seasonal. |
| 12 | **Inflation-regime conditioner** (CPI YoY accelerating and ≥5%): tilt toward trend and energy/commodities, away from bond longs | gap (regime) | Man, *Best Strategies for Inflationary Times* | DOCUMENTED | Commodities had positive real returns in all 8 US regimes and trend was strongly positive; nominal bonds were worst. |
| 13 | **Commodity carry via CFD swap as a proxy for backwardation** (`carry` on energy and softs) | hypothesis | AQR, *Commodities for the Long Run* | DOCUMENTED (mapping SPECULATED) | 7.9% vs 1.5% return in backwardation vs contango. |
| 14 | **Bond trend** (1/3/12 months on UST10Y, UST05Y, UKGILT) | hypothesis | Man AHL, *Equity and Bond Crisis Alpha* | DOCUMENTED | Works in bond bear and bull markets. There is a "bond smile" as well as an equity smile. |
| 15 | **Cross-sectional 12-month momentum** within commodities, FX and index CFDs (`cross_sectional`) | hypothesis | AQR, VME | DOCUMENTED | Needs the skip-month capability (gap) to match the paper exactly. |
| 16 | **Fast trend as the crisis leg on indices** (speeds 10/21) | hypothesis | Man AHL, *Need for Speed*; Graham primer | DOCUMENTED | Crisis alpha rises with speed but after-cost Sharpe falls, so fast trend is kept only as convexity. |
| 17 | **Momentum turning points**: trade when 1-month and 12-month trend disagree (`crisis_only`) | hypothesis | Goulding–Harvey–Mazzoleni | DOCUMENTED | Intermediate speed beats both slow and fast. More turning points per year explain the 2009–19 CTA drought (*Breaking Bad Trends*). |
| 18 | **Nonlinear, saturating forecast function** | gap (signal) | Aspect *How?*; CFM *Two Centuries* | DOCUMENTED | Trend predictability saturates for large signals. The desk's binary sign rules add turnover and reversal risk. |
| 19 | **Replace drawdown-triggered de-risking with vol scaling** | gap (risk/process) | Man AHL, *Drawdowns*; *Is This Time Different?* | DOCUMENTED | A drawdown rule is a "poor man’s volatility scaling". Trend drawdowns worse than 10% were followed by +9.8% average 12-month returns. |
| 20 | **EM-FX and esoteric-commodity trend universe expansion** | hypothesis | AQR *Trends Everywhere*; Transtrend; Man market mix | DOCUMENTED | Alternative assets had gross Sharpe 1.34 vs 1.17 for traditional. Universe choice beats rule choice (Transtrend). Retail spreads are the binding constraint. |

## Negative and "do not" evidence (saves trial budget)
- **Fast trend has decayed.** In Winton's working paper, the fast (1-week turnover) trend system's 10-year gross Sharpe went 1.85 → 0.85 → 0.00 over 1984–2013. Fast-trend cells on majors should need stronger out-of-sample evidence.
- **Buy-the-dip on the S&P has no robust alpha.** AQR tested 196 variants since 1965. It is registered here as a falsification test (`drawdown_conditional`).
- **Value-spread timing of style premia does not help** (Asness et al. 2017).
- **AQR does not define defensive/BAB for FX, commodities or rate futures.** The desk's `style_premia` "defensive" cells on those instruments have no source.
- **Transtrend's Trendpot has "No predictive value!"** It is an attribution measure. The desk should test that claim, not assume it either way.

## Key sources (full list of 56 in the JSON)
- AQR:
  - [Time Series Momentum](https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf)
  - [Century of Evidence](https://www.chesler.us/resources/academia/A_Century_of_Evidence_on_Trend_Following.pdf)
  - [Carry](https://w4.stern.nyu.edu/facdir/lpederse/papers/Carry.pdf)
  - [Value and Momentum Everywhere](https://pages.stern.nyu.edu/~lpederse/papers/ValMomEverywhere.pdf)
  - [Macro Momentum](https://www.aqr.com/-/media/AQR/Documents/Insights/White-Papers/A-Half-Century-of-Macro-Momentum.pdf)
  - [Investing With Style](https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/JOIM-Investing-With-Style.pdf)
  - [Trends Everywhere](https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/AQR-Trends-Everywhere_JOIM.pdf?sc_lang=en)
  - [Commodities for the Long Run](https://www.nber.org/system/files/working_papers/w22793/w22793.pdf)
  - [Hold the Dip](https://www.aqr.com/-/media/AQR/Documents/Alternative-Thinking/AQR-Alternative-Thinking---Hold-the-Dip.pdf?sc_lang=en)
- Man Group:
  - [Volatility Targeting](https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf)
  - [Regimes](https://people.duke.edu/~charvey/Research/Published_Papers/P176_Regimes.pdf)
  - [Inflationary Times](https://people.duke.edu/~charvey/Research/Published_Papers/P154_The_best_strategies.pdf)
  - [FX Hedging](https://people.duke.edu/~charvey/Research/Published_Papers/P175_The_best_strategies.pdf)
  - [Best of Strategies for Worst of Times](https://people.duke.edu/~charvey/Research/Published_Papers/P140_The_best_of.pdf)
  - [Unintended Consequences of Rebalancing](https://www.nber.org/system/files/working_papers/w33554/w33554.pdf)
  - [Need for Speed](https://www.man.com/insights/need-for-speed-trend-following)
- Winton: [Historical Performance of Trend Following](https://www.trendfollowing.com/whitepaper/d.pdf)
- Transtrend: [Trendpot](https://www.trendfollowing.com/whitepaper/Transtrend_Presentation.pdf)
- Aspect: [Trend Following: How?](https://aspectcapital.s3.amazonaws.com/documents/Aspect_Capital_Insight__Series_-_Trend_Following_-_How.pdf)
- Bridgewater: [All Weather Story](https://www.bridgewater.com/_document/the-all-weather-story?id=00000171-8623-d7de-affd-feaf4ee20000)

## Coverage gaps in this mining pass
- **Millburn and Campbell:** no primary research text could be retrieved (CME-hosted PDFs returned 503).
- **Research Affiliates:** the site now redirects to Syzygy and RAFI, so its FX PPP/carry articles were not reached.
- **Web search:** the session's WebSearch budget (200) ran out partway through. Ilmanen's books and podcast interviews were not mined.
