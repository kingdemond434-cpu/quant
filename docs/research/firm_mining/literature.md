# Literature cluster: practitioner books and academic papers by or about top-firm quants

Scope: this covers methods, anomaly catalogues and validation science, mapped to the MT5/Fusion CFD universe. There is no single-name equity statistical hunting in it.
Output: `literature.json` has 93 sources, 55 hypothesis rows and 36 capability-gap rows. Of the 93 sources, 27 were read as full-text PDFs (or, where noted, a fetched page). The rest were read through abstracts or summaries only, and every row names which. A quote is left empty unless the verbatim text was actually seen.

Evidence labels:
- **DOCUMENTED**: peer-reviewed, with data.
- **REPORTED**: book, practitioner or working-paper claim.
- **SPECULATED**: the transfer to CFDs is our own inference.

Broker stamps assume the venue is on UTC+3 in summer and UTC+2 in winter. On that basis, stamp 18 is the bar that opens at 16:00 London in both seasons. Check this against `measure_broker_offset` before sweeping.

## Ranked top 25 additions

| # | Addition | Kind / family | Evidence | Why it ranks here |
|---|---|---|---|---|
| 1 | **Signed calendar-window family**: fixed-direction windows anchored to `forced_flow_calendar` kinds | gap: signal | DOCUMENTED (Lucca-Moench JF 2015; Mueller et al. JF 2017; Lou-Yan-Zhang RFS 2013; Savor-Wilson JFQA 2013) | `forced_flow.pre_flow` trades the sign of the last 3 closes, so the most-cited calendar effects cannot be expressed faithfully today. These include the pre-FOMC long (+49bp over the 24h before the announcement, about 80% of the 1994-2011 US equity premium), the FOMC-day short-USD trade (high-yield basket 14.47bp/day vs 1.73bp), and pre-/post-auction UST. One build unlocks five or more mechanisms. |
| 2 | **FX-fix W-pattern (Krohn-Mueller-Whelan)**: USD up into the Tokyo/ECB fixes and down after the Tokyo/London fixes | `clock_transition` london_fix out_of 18/6; tokyo_open into/out_of; london_open out_of | DOCUMENTED (JF 2024, G9 1999-2019) | About 2bp per leg, t-stats of 5-11 and pervasive. **Caveat: client-market returns after costs are significantly negative**, so it pays only at raw-spread costs or with passive entries. That makes it a test of the desk's cost edge. |
| 3 | **Exact fix labels** (tokyo_fix, ecb_fix, lbma_gold_am/pm) in `clock_transition.CATALOGUE` | gap: signal | DOCUMENTED (Krohn; Ito-Yamada; Caminschi-Heaney) | Today's approximations (tokyo_open, london_open, comex_settle) are different hypotheses, and each one spends trials. |
| 4 | **Effective number of trials (ONC clustering) feeding DSR** | gap: validation | DOCUMENTED (López de Prado-Lewis QF 2019; Bailey-LdP JPM 2014) | CLAUDE.md records DSR rejecting 42 of 42 cells at 597 trials. Counting correlated variants as independent is timidity by arithmetic. K_eff keeps false discoveries controlled and restores power. |
| 5 | **Market intraday momentum / gamma hedging into the close** | `hedging_demand_close` (close_hour 22, require_elevated_vol) on US500/NAS100/US30/US2000, plus UST, XAU, XTI and FX at their own venue closes | DOCUMENTED (Gao et al. JFE 2018, R² 1.6-2.6%; Baltussen et al. JFE 2021, 60+ futures 1974-2020) | Documented in every asset class. The family already exists, so the work is getting close_hour right per venue and season. |
| 6 | **Time-series momentum at 1/3/12 months, vol-scaled; slow/fast turning-point blend** | `multi_speed_trend` speeds [252], [21,63,252], [21,252] | DOCUMENTED (MOP JFE 2012, all 58 instruments; Hurst-Ooi-Pedersen positive every decade since 1880 and in 8 of the 10 largest crises; Garg-Goulding-Harvey-Mazzoleni JFE 2023) | The strongest cross-asset evidence in finance, and it doubles as crisis convexity. |
| 7 | **Carry on every CFD via broker swap** (indices, bonds, energy, softs, FX), and carry gated by calm vol | `carry`; `style_premia` carry, combo carry_calm_vol | DOCUMENTED (Koijen-Moskowitz-Pedersen-Vrugt JFE 2018; LRV RFS 2011; Menkhoff et al. JF 2012: global FX vol explains >90% of the carry spread) | The swap is a model-free carry that is observable on every symbol. The vol gate (or 1/σ² scaling) harvests the premium outside the crash state. |
| 8 | **Volatility-managed, asset-class-aware sizing** (two-sided capital modifier) | gap: sizing | DOCUMENTED (Moreira-Muir JF 2017; Harvey et al./Man JPM 2018) | Sharpe rises for equity and carry sleeves and exposure *increases* in calm regimes (Rule 2). For FX, commodities and bonds the Sharpe effect is neutral, but tails are thinner. |
| 9 | **Meta-labelling as a two-sided sizing layer** per certified sleeve, with triple-barrier labels, uniqueness weights and purged CV | gap: combination (partial in repo) | REPORTED (AFML ch. 3-4; Joubert JFDS 2022) | Filters false positives and scales conviction up as well as down, without re-learning side. |
| 10 | **Grinold-Kahn breadth accountant**: IR = TC·IC·√N_eff, with N_eff = N/(1+(N-1)ρ̄) | gap: combination | DOCUMENTED (Grinold-Kahn; Clarke-de Silva-Thorley 2002) | Puts a number on E8's "count mechanisms, not certificates" and ranks candidate sleeves by breadth added per unit of heat. |
| 11 | **Factor-exposure accounting** (DOL, HML-FX, TSMOM, US500 beta, vol) over the live book | gap: risk | DOCUMENTED (LRV 2011; AMP 2013) | Exposes "independent" sleeves that are really the same dollar or carry bet. |
| 12 | **Cross-sectional FX momentum (1m, sextiles) and FX value (5y reversal)** | `cross_sectional` momentum h=21 / reversal h=1260 | DOCUMENTED (Menkhoff et al. JFE 2012: 6-10% p.a.; RFS 2017: value Sharpe ~0.5, 0.8-0.9 when adjusted for fundamentals) | Two premia that are low-correlation with carry and with each other. Value plus momentum combine well (AMP). |
| 13 | **Local-hours depreciation** (Breedon-Ranaldo): EUR/GBP weaken in European hours, USD weakens in US hours, AUD/JPY weaken in Asian hours | `clock_transition` london_open / ny_open / tokyo_open out_of | DOCUMENTED (JMCB 2013; EUR/USD profitable after costs 1997-2007) | Flow-based and different from the fix mechanism. Cheap to test. |
| 14 | **European-open window for US index futures** | `clock_transition` london_open into/out_of on US500/NAS100/US30 | DOCUMENTED (Bondarenko-Muravyev JFQA 2023: Sharpe 1.6, positive every year 2006-2018, after costs) | The whole S&P premium sits in about 4 hours, which is an unusually concentrated and dated edge. |
| 15 | **Pre-auction UST weakness then recovery**; month-end dash-for-cash | `forced_flow` bond_auction / month_end post_flow_fade | DOCUMENTED (Lou-Yan-Zhang RFS 2013; Etula et al. RFS 2020) | These are forced participants on a dated calendar, which is exactly the family's thesis. |
| 16 | **COT liquidity provision (fade speculator changes) and the hedging-pressure premium**, plus a **falsifier prior** for FX COT momentum | `cot_change_fade`, `cot_positioning`; `cot_change_momentum` expected to fail | DOCUMENTED (Kang-Rouwenhorst-Tang JF 2020; Basu-Miffre JBF 2013; Klitgaard-Weir NY Fed: 75% same-week hit, nothing next week) | The desk's `_cot_entries` already enters the Monday after release, so the publication lag is honoured. A COT-momentum pass would therefore be suspicious. |
| 17 | **Commodity term-structure data**: basis, basis-momentum, term premia | gap: data | DOCUMENTED (Szymanowska et al. JF 2014: spot premia 5-14% p.a.; Boons-Prado JF 2019; Gorton-Rouwenhorst) | The best-documented commodity predictors, invisible without front/second-month prices. Broker swap is a partial proxy. |
| 18 | **Turn-of-month, Halloween and gold autumn calendar cells** | `turn_of_month` (1,3,+1); `calendar_month` (Nov-Apr indices; XAU Sep/Nov) | DOCUMENTED (McConnell-Xu FAJ 2008: 31 of 35 countries; Bouman-Jacobsen AER 2002: 36 of 37; Baur 2013: Sep +2.2%, Nov +1.8%) | Declared families with explicit literature parameters. Count the six Halloween months as six trials. |
| 19 | **Lead-lag: US to international indices; commodity FX to metals; oil to CAD; US500 to US2000** | `lead_lag` | DOCUMENTED (Rapach-Strauss-Zhou JF 2013; Chen-Rogoff-Rossi QJE 2010; Ferraro-Rogoff-Rossi, which calls the lagged effect *ephemeral*; Lo-MacKinlay RFS 1990) | Information-diffusion mechanisms. Keep them to H1/D1 because of non-synchronous quoting. |
| 20 | **Diurnal-periodicity-adjusted volatility** for every ATR-threshold family | gap: validation | DOCUMENTED (Andersen-Bollerslev JEF 1997) | Raw ATR marks the London/NY open as "abnormal" every day. Fixing that sharpens dip_atr_shock, jump, usd_session_shock, fx_fixing_reversal and hedging_demand_close. |
| 21 | **Forecast-combination shrinkage**: ridge toward 1/N for ensemble weights; Novy-Marx n^k charge | gap: combination / validation | DOCUMENTED (Claeskens et al. IJF 2016; DeMiguel-Garlappi-Uppal RFS 2009; Kelly-Malamud-Zhou JF 2024; Novy-Marx NBER 2015) | Stops the ensemble family from fitting its weights in-sample and laundering overfit members past DSR. |
| 22 | **Dynamic momentum weighting** (forecast mean/variance) and **Kelly under parameter uncertainty** | gap: sizing | DOCUMENTED (Daniel-Moskowitz JFE 2016: about 2x Sharpe; Thorp 2006: g(cf*)/g(f*) = c(2−c)) | Both are evidence-derived and two-sided, so they are compatible with "never reduce aggressiveness". They measure robust forward E[log W]; they are not caps. |
| 23 | **Macro data for economic momentum, NFA and fundamentals-adjusted value**; **FX options (VRP, risk reversals)**; **consensus surprises** | gaps: data | DOCUMENTED (Dahlquist-Hasseltoft JFE 2020: Sharpe 0.70; Della Corte et al. RFS/JFE 2016; ABDV AER 2003) | Distinct FX premia that price-only families cannot express. ABDV shows the direction of an event reaction depends on the sign of the surprise. |
| 24 | **Same-slot seasonality signal** (half-hour, weekday and calendar month selected from their own history) | gap: signal | DOCUMENTED (Heston-Korajczyk-Sadka JF 2010: persists ≥40 days; Keloharju-Linnainmaa-Nyberg JF 2016: also in commodities and country indices) | Turns fixed-slot calendar families into an adaptive, out-of-sample slot selector. |
| 25 | **Negative prior on the opening-range breakout**; cost-realistic replication rule for exotic CFDs | `opening_range` (REPORTED); gap: validation | REPORTED (MQL5 replication 2026: gross +0.13R reproduced on 5 index CFDs, net ~0 or negative); DOCUMENTED (Hou-Xue-Zhang: 65% of 452 anomalies fail, 96% of the trading-frictions category) | Stops trials being spent re-discovering an edge that is gross-only. Thin exotics are the CFD analogue of microcaps. |

## Other hypotheses filed (lower rank)

- Evans WMR-fix reversal (`fx_fixing_reversal`, pre-2015).
- Safe-haven lead-lag US500 to USDJPY/USDCHF.
- EIA crude and gas storage drift (`event_reaction` inventory).
- Goldman-roll fade on energy CFDs (SPECULATED: the edge is in the futures spread, not the outright price).
- Gold Tokyo-to-NY session fade (SPECULATED).
- Carry-crash re-entry (`drawdown_conditional`, SPECULATED).
- Nagel VIX-conditioned weekly index reversal.
- AUS200/CA60 Kalman pair (Chan's EWA/EWC analogue).
- HMM `regime_transition`.
- Crypto-CFD TSMOM (Liu-Tsyvinski).
- Overnight index drift (Lou-Polk-Skouras; the index transfer is REPORTED).
- A deliberate **negative control**: no pre-FOMC drift in UST. If that cell "passes", the harness is leaking.

## Machinery already in the repo (verify, don't rebuild)

Grep hits exist for deflated_sharpe, pbo, purged/combinatorial CV, hrp, meta_label, triple_barrier (`libs/features/labels.py`), kelly, breadth (`libs/research/breadth.py`), regime/HMM (`libs/regime/`) and vol scaling.

Grep found none of the following: sample-uniqueness / sequential bootstrap, clustered feature importance, VPIN, diurnal-vol normalisation in the MT5 families, or a fixed-direction calendar window.

## Main sources (full list with URLs in literature.json)

**FX:**
- Krohn-Mueller-Whelan (JF 2024)
- Evans (JBF 2018)
- Ito-Yamada (JIE 2017)
- Melvin-Prins (JFM 2015)
- Breedon-Ranaldo (JMCB 2013)
- Ranaldo-Söderlind (RoF 2010)
- Evans-Lyons (JPE 2002)
- LRV (RFS 2011, JFE 2014)
- Menkhoff-Sarno-Schmeling-Schrimpf (JFE 2012, JF 2012, RFS 2017)
- Brunnermeier-Nagel-Pedersen (2008)
- Della Corte et al. (JFE 2016, RFS 2016)
- Dahlquist-Hasseltoft (JFE 2020)
- Mueller-Tahbaz-Salehi-Vedolin (JF 2017)
- ABDV (AER 2003)
- Andersen-Bollerslev (JEF 1997)

**Equity-index / macro calendar:**
- Lucca-Moench
- Cieslak-Morse-Vissing-Jorgensen
- Savor-Wilson
- Gao-Han-Li-Zhou
- Baltussen-Da-Lammers-Martens
- Elaut-Frömmel-Lampaert
- Bondarenko-Muravyev
- Lou-Polk-Skouras
- Heston-Korajczyk-Sadka
- McConnell-Xu
- Bouman-Jacobsen
- Keloharju-Linnainmaa-Nyberg
- Etula et al.
- Lou-Yan-Zhang
- Rapach-Strauss-Zhou

**Trend / style / carry:**
- Moskowitz-Ooi-Pedersen
- Hurst-Ooi-Pedersen
- Garg-Goulding-Harvey-Mazzoleni
- Levine-Pedersen
- Asness-Moskowitz-Pedersen
- Koijen-Moskowitz-Pedersen-Vrugt
- Daniel-Moskowitz
- Moreira-Muir
- Harvey et al. (Man)
- Nagel
- Lo-MacKinlay
- Lo (AMH)

**Commodities:**
- Gorton-Rouwenhorst
- Szymanowska et al.
- Boons-Prado
- Basu-Miffre
- Kang-Rouwenhorst-Tang
- Klitgaard-Weir
- Mou
- Wen et al.
- Halova-Kurov-Kucher
- Baur
- Caminschi-Heaney
- Iwatsubo-Watkins-Xu
- Chen-Rogoff-Rossi
- Ferraro-Rogoff-Rossi

**Validation / ML / combination / sizing:**
- Harvey-Liu-Zhu
- Harvey-Liu
- Hou-Xue-Zhang
- Chen-Zimmermann
- Novy-Marx
- Bailey-López de Prado (DSR)
- Bailey-Borwein-LdP-Zhu (PBO)
- LdP-Lewis (ONC)
- LdP (HRP, AFML ch. 3-5, CFI)
- Joubert
- Arian-Norouzi-Seco
- Easley-LdP-O'Hara (VPIN)
- Thorp
- Spitznagel
- Claeskens et al.
- DeMiguel-Garlappi-Uppal
- Kelly-Malamud-Zhou
- Nystrup et al.
- Ang-Timmermann

**Books:**
- Chan (*Algorithmic Trading*)
- Narang (*Inside the Black Box*)
- Kakushadze-Serur (*151 Trading Strategies*)
- Kakushadze (*101 Formulaic Alphas*)
- Tulchinsky (*Finding Alphas*)
- Grinold-Kahn
- Zarattini-Aziz, plus the MQL5 replication
