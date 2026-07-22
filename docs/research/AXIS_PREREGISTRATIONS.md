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
