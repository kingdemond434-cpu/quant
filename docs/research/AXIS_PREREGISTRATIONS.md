# AXIS PRE-REGISTRATIONS -- generate run 2026-07-22T23:16Z (clock-saturation duty)

Authored per-axis hypotheses, EV-gated honestly (no tuning-to-pass), routed per the TWO-STAGE LAW: rejects are SCREEN-level kills with explicit revisit conditions -- the axes stay ingested and re-open on new mechanisms.

| axis | hypothesis | ev | p_survive | verdict |
|---|---|---|---|---|
| cme | cme_anchored_basis_dislocation | 0.0326 | 0.48 | REJECT (EV below thresh) |
| etf_flows | etf_flow_pressure | 0.0191 | 0.24 | REJECT (EV below thresh) |
| wikipedia | attention_surge_fade | 0.0182 | 0.24 | REJECT (EV below thresh) |
| fx | dxy_shock_beta_rotation | 0.0052 | 0.084 | REJECT (EV below thresh) |
| equity | crypto_equity_leadlag | 0.0005 | 0.0158 | REJECT (EV below thresh) |
| index | risk_regime_rotation | 0.0027 | 0.0525 | REJECT (EV below thresh) |
| metal | digital_gold_rotation | 0.0005 | 0.0158 | REJECT (EV below thresh) |
| energy | miner_margin_squeeze | 0.0011 | 0.06 | REJECT (EV below thresh) |
| mining | hashrate_capitulation | 0.0003 | 0.0131 | REJECT (EV below thresh) |
| fed | net_liquidity_impulse | 0.0026 | 0.0525 | REJECT (EV below thresh) |
| crossasset | crossasset_carry_confirm | 0.0023 | 0.0525 | REJECT (EV below thresh) |

## Covered axes (bookkeeping)
- **binance_metrics**: COVERED: this axis IS the derivative-metrics archive feeding the oi_divergence + ls_contrarian + liquidation_reversal forward clocks (24/40d accruing, peek e-values live) -- evidence has been accruing since 07-09; the gen_done key was simply never set.
- **crypto**: COVERED: this axis IS the price lake the autodiscovery factory tests daily (12 price families, content-hash dedup) and every deployed/shadow sleeve runs on.

## Full cards

### cme_anchored_basis_dislocation (cme)
- **Mechanism:** CME front-month annualized basis is the INSTITUTIONAL cost of regulated long exposure; perp funding is crypto-native leverage cost. When the CME anchor and the cross-sectional perp basis complex dislocate (z of spread), institutional vs degen positioning has diverged -- fade the perp side toward the anchor across the perp universe (xsec, not BTC-only, so breadth is real).
- **Construction/falsify:** Construction: daily CME basis (front vs spot) minus median perp basis; xsec tilt on per-name deviation from that anchor. Falsify: 40 fwd days, NW-t of the tilt <=0, or |corr| to funding_carry >0.5 (not orthogonal enough to earn a slot).
- **EV:** 0.0326 (p_survive 0.48, tags ['new_orthogonal_data', 'funding_family']) -> REJECT (EV below thresh)

### etf_flow_pressure (etf_flows)
- **Mechanism:** Spot-ETF net creations are REALIZED institutional demand hitting a thin float; flows are autocorrelated at daily horizon, so a 5d flow z-score should lead 1-3d BTC/ETH returns and, through beta, the whole complex (tilt sizing, breadth via the perp cross-section).
- **Construction/falsify:** Construction: 5d z of aggregate net flows -> directional tilt scaled across perps by BTC beta. Falsify: 40 fwd days NW-t<=0, or signal decays under 1d latency (flows publish EOD).
- **EV:** 0.0191 (p_survive 0.24, tags ['new_orthogonal_data']) -> REJECT (EV below thresh)

### attention_surge_fade (wikipedia)
- **Mechanism:** Wikipedia pageview spikes on coin articles = late retail attention; attention peaks lag price and mark local crowding -- fade names with attention z-spikes vs the cross-section (classic attention/overreaction literature, but on a fresher, less-arbed proxy than Google Trends).
- **Construction/falsify:** Construction: per-coin pageview z (7d) -> xsec fade of top decile, ~40-60 mapped names. Falsify: 40 fwd days NW-t<=0 or sign flips (attention momentum, not fade -> graveyard wrong_sign, do NOT flip-fit).
- **EV:** 0.0182 (p_survive 0.24, tags ['new_orthogonal_data']) -> REJECT (EV below thresh)

### dxy_shock_beta_rotation (fx)
- **Mechanism:** USD liquidity shocks transmit to crypto with a lag via risk appetite; a 5d DXY shock should rotate the crypto cross-section (high-beta alts vs BTC) rather than just level.
- **Construction/falsify:** Construction: DXY 5d z -> xsec tilt low-beta-over-high-beta on shock. Falsify: 40 fwd days NW-t<=0. NOTE: macro-overlay class rejected 3x on 07-17 (FRED) -- this differs only by being xsec-rotation not level-overlay; if the gate rejects, that precedent stands.
- **EV:** 0.0052 (p_survive 0.084, tags ['new_orthogonal_data', 'crowded_known']) -> REJECT (EV below thresh)

### crypto_equity_leadlag (equity)
- **Mechanism:** Crypto-adjacent equities (COIN/MSTR/miners) trade US hours with institutional flow; their overnight/US-session moves may lead 24h crypto (information arrives via the regulated market first).
- **Construction/falsify:** Construction: US-close basket return -> next-Asia-session crypto tilt. Falsify: 40 fwd days NW-t<=0; also falsified if lead vanishes at 1h latency (then it is just beta).
- **EV:** 0.0005 (p_survive 0.0158, tags ['price_only', 'crowded_known']) -> REJECT (EV below thresh)

### risk_regime_rotation (index)
- **Mechanism:** SPX/NDX drawdown states compress crypto dispersion and flip carry/momentum regimes; an equity-vol regime flag may time the desk's own sleeve weights (meta-allocation, breadth = the whole book).
- **Construction/falsify:** Construction: NDX 20d vol regime -> sleeve-weight tilt in the combiner. Falsify: regime-split Sharpe difference insignificant at 40 fwd days. NOTE: overlay class -- the est_sharpe=refinement penalty applies honestly.
- **EV:** 0.0027 (p_survive 0.0525, tags ['crowded_known']) -> REJECT (EV below thresh)

### digital_gold_rotation (metal)
- **Mechanism:** Gold and BTC compete for the debasement-hedge flow; strong gold with flat BTC implies hedge demand exists but is choosing metal -- a relative-rotation signal for BTC vs alts.
- **Construction/falsify:** Construction: gold 20d momentum vs BTC 20d -> BTC-dominance tilt. Falsify: 40 fwd days NW-t<=0.
- **EV:** 0.0005 (p_survive 0.0158, tags ['price_only', 'crowded_known']) -> REJECT (EV below thresh)

### miner_margin_squeeze (energy)
- **Mechanism:** Energy price spikes squeeze miner margins -> forced BTC treasury selling with a lag -- a supply-pressure channel (works jointly with the mining axis for hashprice).
- **Construction/falsify:** Construction: energy 20d shock x mining-difficulty trend -> BTC supply-pressure flag. Falsify: no excess BTC-down conditional response at 40 fwd days.
- **EV:** 0.0011 (p_survive 0.06, tags ['new_orthogonal_data', 'narrow_breadth']) -> REJECT (EV below thresh)

### hashrate_capitulation (mining)
- **Mechanism:** Hash-ribbon style: sustained hashrate/difficulty decline marks miner capitulation, historically near local bottoms (published; the crowding is priced honestly in tags).
- **Construction/falsify:** Construction: 30d vs 60d hashrate cross -> BTC long flag. Falsify: 40 fwd days conditional return <= unconditional.
- **EV:** 0.0003 (p_survive 0.0131, tags ['crowded_known', 'narrow_breadth']) -> REJECT (EV below thresh)

### net_liquidity_impulse (fed)
- **Mechanism:** Standalone (NOT overlay -- the 07-17 overlay class is dead): 4w impulse of WALCL-TGA-RRP as a direct directional signal for the crypto complex, the 'net liquidity' trade.
- **Construction/falsify:** Construction: 4w net-liquidity z -> directional tilt. Falsify: 40 fwd days NW-t<=0. PRIOR: 3 FRED-family ideas EV-rejected 07-17 at 0.004-0.013; this is the last un-tested standalone form -- if it also rejects, the fed axis is ledgered exhausted.
- **EV:** 0.0026 (p_survive 0.0525, tags ['crowded_known']) -> REJECT (EV below thresh)

### crossasset_carry_confirm (crossasset)
- **Mechanism:** Cross-asset trend/carry agreement (FX carry, commodity trend, equity trend all risk-on) as a breadth-100 conditioning state for crypto sleeve sizing -- the diversified-macro regime read, distinct from any single index.
- **Construction/falsify:** Construction: 3-asset-class trend agreement score -> sleeve sizing multiplier within existing rails. Falsify: regime-split difference insignificant at 40 fwd days. Overlay penalty applies.
- **EV:** 0.0023 (p_survive 0.0525, tags ['crowded_known']) -> REJECT (EV below thresh)

---

## COT POSITIONING PANEL -- pre-registered 2026-07-29 BEFORE any computation (register #77)

Not a crypto axis: this is a MEASUREMENT on 26 years of free CFTC Commitments-of-Traders data that
the desk has owned and never read. Two questions, both pre-committed here with their kill criteria
so the result cannot be spun after the fact. Screen only -- ZERO promotion authority (L1.6).

### A. post_publication_decay (measurement, not a signal)
- **Question:** the desk adopted a BORROWED -58% McLean-Pontiff post-publication haircut as a
  standing prior (register #71). Does the desk's own panel reproduce it?
- **Mechanism under test:** hedging-pressure / speculator-positioning effects were published
  ~1992-2000 (Bessembinder 1992; De Roon-Nijman-Veld 2000) and became widely tradeable after.
  If publication crowds an effect, its Sharpe should fall AFTER the publication boundary.
- **Construction (fixed now):** commercial net position / open interest, 52-week z-score, weekly
  observations; sign-based time-series positioning on the next week's return. Split at 2000-01-01
  (the later of the two canonical publication dates). Sharpe before vs after; decay reported as
  1 - (Sharpe_after / Sharpe_before).
- **Kill/report criteria:** the number is the deliverable either way. Measured decay materially
  below the borrowed 58% means the imported prior is too harsh for this data and must be
  re-derived, not re-used; materially above means the prior is optimistic. Both outcomes are
  reported; neither promotes anything.
- **Trials charged:** 2 (commercial and non-commercial constructions), logged per asset.

### B. ghr_lagged_positioning (a gating test with direct budget value)
- **Question:** Gorton-Hayashi-Rouwenhorst REJECT hedging pressure -- positions significant
  CONTEMPORANEOUSLY, zero LAGGED. Only the lagged form is tradeable. Does the desk's panel agree?
- **Construction (fixed now):** regress next-week return on LAGGED positioning z (the only
  tradeable form), per asset and pooled, Newey-West t-stats.
- **PRE-COMMITTED CONSEQUENCE:** if pooled lagged predictability is indistinguishable from zero,
  that is a REJECT for the positioning-axis CLASS, and it CANCELS any multi-week crypto
  positioning-data acquisition on the queue -- a negative result with immediate budget value.
  If it is significant, the crypto positioning acquisition is JUSTIFIED and gets a clock.
- **Trials charged:** 1 pooled + one per asset, all logged.

### Honest scope, fixed before running
- Price legs come from FRED (public domain, keyless): WTI crude, EUR/USD, USD/JPY, GBP/USD,
  S&P 500, 10Y Treasury yield -> mapped to their COT contracts. Metals, grains and softs are
  DROPPED, not silently omitted: Stooq sits behind a JS proof-of-work bot gate and register #80
  is an OPEN principal ruling on whether defeating an anti-bot gate is inside §13 -- so the gate
  was not defeated, and Yahoo's chart endpoint returned HTTP 429. The panel is therefore 6 assets
  wide, and that limit is part of the result, not a footnote.
- Weekly alignment: COT is as-of Tuesday, published Friday. Returns are taken from the FOLLOWING
  week to avoid using data before it was public -- the publication lag is a lookahead trap and is
  handled explicitly, not assumed away.

## COT POSITION-CHANGE LIQUIDITY PREMIUM (KRT channel) -- pre-registered 2026-08-25 BEFORE any
computation (data_axis_watchlist card #40; §33 T2 conversion). Screen only -- ZERO promotion
authority (L1.6); survivors go to the canonical 10-gate door, never past it.

### C. krt_position_change_liquidity (the construction the 41y screen never charged)
- **Mechanism under test (KRT JF 2020; Maréchal JFM 2023 replication):** noncommercials demanding
  immediacy move futures away from value; commercials accommodate and earn the reversion at ~weekly
  horizon. Change-CHASERS pay, faders earn. Distinct from the LEVEL/insurance channel the desk
  already killed (COT_SCREEN_RESULT.md, pooled NW t=-0.64) -- that kill is not re-litigated.
- **Universe (fixed by what is on-box, drops stated):** gold, silver, aud, cad, chf, gbp, jpy,
  nzd, sp500, nasdaq100 from `desks/mt5/cot/*.parquet` (legacy futures-only, weekly). DROPPED:
  eur (no legacy parquet on box; TFF taxonomy is a different construction -- follow-up: extend the
  fetcher), dxy (not an MT5 leg), crude/natgas (no COT parquet on box -- follow-up with eur).
- **Signal (fixed):** spec_share = (noncomm_long - noncomm_short) / OI at report_date.
  dx1 = spec_share_t - spec_share_{t-1}; dx4 = spec_share_t - spec_share_{t-4}.
- **Release alignment (fixed; the 41y screen's Wed-start residual is NOT reused):** report_date is
  Tuesday, published Friday 15:30 ET. Entry = first price close with date STRICTLY > report_date
  + 3 calendar days; exit = first close STRICTLY > report_date + 10 days. Only post-release
  closes are ever used (typically Monday -> Monday).
- **Price legs (fixed):** FRED keyless daily, orientation corrected to the CONTRACT underlying
  (DEXJPUS, DEXSZUS, DEXCAUS inverted; DEXUSAL/DEXUSUK/DEXUSNZ as-is); sp500 = FRED SP500
  (2016->); nasdaq100 = FRED NASDAQCOM (composite as NAS100 proxy -- stated approximation);
  gold/silver = desk `desks/mt5/universe/XA{U,G}USD_H1.parquet` resampled to daily last close
  (2018->; server-clock-mislabelled-UTC caveat noted, sub-material at weekly horizon).
- **Tests, sign expected NEGATIVE on every cell (fade the change):**
  1. PRIMARY: pooled TS regression next-week return ~ dx1 (x standardized per-asset by trailing
     104w past-only std), Newey-West(4) t. 2. pooled dx4. 3. per-asset TS cells (asset x horizon).
  4. XS weekly Spearman(dx, next-week return) across assets, weeks with >=6 assets; mean IC/se.
  5. Recency (RESEARCH 6b): trailing 24 months, same cells, same bar.
- **Per-asset guard:** <100 usable weeks -> cell dropped, stated.
- **Trials charged:** every computed cell, full + recent windows, logged in the artifact
  (<=48; exact count in `data/cot_change_screen.json`). Returns are GROSS (cost_basis declared
  in the artifact); cost stress belongs to the gauntlet, not the screen.
- **KILL (fixed):** pooled dx1 beta >= 0 OR NW t > -1.96 on the full window -> SCREEN-KILL, card
  gets [§33: killed] with the mechanism note. SURVIVE -> hypothesis card into the desk queue for
  the 10-gate door. Decay watch (RT2012): recent-window sign flip on a full-window pass is
  flagged, never smoothed over.
