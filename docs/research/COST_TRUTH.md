# COST TRUTH -- charged vs quoted vs realised

Generated 2026-09-23T04:50:28+00:00 by `desks/mt5/research/cost_truth.py` (hourly leg `cost_truth`). DERIVED -- edit the organ, never this page.

Account **495044** (Fusion Markets Pty Ltd, FusionMarkets-Live, EUR), terminal MEASURED, 433 deals, 65 symbols, 8 with a realised reading.

## The commission term, which is ~98% of the charged cost

- model charges **2.0** per lot per side (libs/portfolio/fusion_cost)
- account actually pays **2.0** per lot per side (median over 8 symbol readings, p10 2.0, p90 2.0)
- rate overcharge **1.0x**, regime overcharge **1.0x**, total **1.0x**
- why: BOTH HALVES FIXED 2026-09-23. The spine derived commission over spread as zero/(raw-zero), but raw is the 0.2x regime, so the ratio was 5x too large; it now carries the multiplier. And the rate was the brochure USD 2.25 applied as ACCOUNT currency against a measured 2.00. This reading holds them there.

## Where the model charges more than the venue

| symbol | charged pts | quoted pts (reference) | spread ratio | commission ratio |
|---|---:|---:|---:|---:|
| AUDCHF | 110.5 | 3.0 | 36.8333 | 1.0 |
| CADCHF | 3.0 | 1.0 | 3.0 | 1.0 |
| GBPCHF | 3.0 | 1.0 | 3.0 | 1.0 |
| XAUUSD | 14.5 | 5.0 | 2.9 | 1.0 |
| GBPAUD | 4.0 | 2.0 | 2.0 | 1.0 |
| GBPNZD | 4.0 | 2.0 | 2.0 | 1.0 |

## Session structure (M1 spread in points, the broker's own tape)

| symbol | asia | london | ny | late | rollover | live |
|---|---:|---:|---:|---:|---:|---:|
| ADAUSD | 31.0 | 31.0 | 31.0 | 31.0 | 31.0 | 32.0 |
| AUDCAD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| AUDCHF | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 4.0 |
| AUDJPY | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| AUDNZD | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 6.0 |
| AUDSGD | 0.0 | 1.0 | 2.0 | 1.0 | 1.0 | 8.0 |
| AUDUSD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| BTCUSD | 1794.0 | 1794.0 | 1794.0 | 1794.0 | 1794.0 | 1952.0 |
| CADCHF | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 2.0 |
| CADJPY | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| CHFDKK | 77.0 | 54.0 | 45.0 | 53.0 | 59.0 | 68.0 |
| CHFJPY | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| CHFNOK | 637.0 | 272.0 | 230.0 | 265.0 | 268.0 | 665.0 |
| CHFSEK | 1455.0 | 616.0 | 563.0 | 598.0 | 681.0 | 1639.0 |
| CHFSGD | 2.0 | 2.0 | 3.0 | 3.0 | 2.0 | 10.0 |
| DOTUSD | 30.0 | 30.0 | 30.0 | 30.0 | 30.0 | 31.0 |
| EURAUD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| EURCAD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EURCHF | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| EURGBP | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EURILS | 890.0 | 191.0 | 80.0 | 150.0 | 150.0 | 869.0 |
| EURJPY | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EURMXN | 495.0 | 213.0 | 169.0 | 160.0 | 157.0 | 528.0 |
| EURNOK | 458.0 | 148.0 | 117.0 | 185.0 | 178.0 | 498.0 |
| EURNZD | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 6.0 |
| EURPLN | 184.0 | 94.0 | 72.0 | 74.0 | 75.0 | 169.0 |
| EURSEK | 375.0 | 116.0 | 94.0 | 123.0 | 116.0 | 436.0 |
| EURUSD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EURZAR | 786.0 | 309.0 | 238.0 | 299.0 | 326.0 | 728.0 |
| GBPAUD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| GBPCAD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 2.0 |
| GBPCHF | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| GBPJPY | 3.0 | 3.0 | 2.0 | 3.0 | 3.0 | 6.0 |
| GBPMXN | 1034.0 | 531.0 | 393.0 | 340.0 | 337.0 | 1067.0 |
| GBPNOK | 896.0 | 380.0 | 317.0 | 420.0 | 431.0 | 880.0 |
| GBPNZD | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 9.0 |
| GBPSEK | 493.0 | 188.0 | 173.0 | 232.0 | 244.0 | 452.0 |
| GBPSGD | 2.0 | 2.0 | 4.0 | 3.0 | 3.0 | 15.0 |
| GBPUSD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| GBPZAR | 1496.0 | 602.0 | 536.0 | 639.0 | 709.0 | 1396.0 |
| GER40 | 320.0 | 320.0 | 80.0 | 120.0 | 120.0 | 320.0 |
| NAS100 | 80.0 | 80.0 | 80.0 | 80.0 | 80.0 | 80.0 |
| NZDCAD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 2.0 |
| NZDCHF | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 2.0 |
| NZDHUF | 30280.0 | 11200.0 | 9200.0 | 10800.0 | 11100.0 | 22380.0 |
| NZDUSD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| SGDJPY | 2.0 | 2.0 | 3.0 | 2.0 | 2.0 | 11.0 |
| US30 | 280.0 | 160.0 | 160.0 | 120.0 | 120.0 | 280.0 |
| USDCAD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| USDCHF | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| USDDKK | 53.0 | 39.0 | 36.0 | 41.0 | 42.0 | 52.0 |
| USDHUF | 48480.0 | 17200.0 | 13800.0 | 16300.0 | 17100.0 | 35180.0 |
| USDJPY | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| USDMXN | 394.0 | 216.0 | 171.0 | 151.0 | 148.0 | 404.0 |
| USDNOK | 388.0 | 145.0 | 116.0 | 175.0 | 172.0 | 364.0 |
| USDPLN | 160.0 | 55.0 | 48.0 | 55.0 | 55.0 | 161.0 |
| USDRUB | 248697.0 | 90806.0 | 77649.0 | 130024.0 | 159868.0 | 285946.0 |
| USDZAR | 691.0 | 238.0 | 182.0 | 193.0 | 188.0 | 668.0 |
| XALUSD | 3950.0 | 3900.0 | 1950.0 | 2000.0 | - | 4200.0 |
| XAUAUD | 13.0 | 12.0 | 12.0 | 13.0 | 13.0 | 27.0 |
| XAUEUR | 6.0 | 6.0 | 6.0 | 6.0 | 6.0 | 12.0 |
| XAUUSD | 5.0 | 5.0 | 5.0 | 5.0 | 5.0 | 8.0 |
| XBRUSD | 20.0 | 20.0 | 20.0 | 20.0 | 20.0 | 40.0 |
| XCUUSD | 6050.0 | 5850.0 | 3100.0 | 3150.0 | - | 6600.0 |
| XTIUSD | 20.0 | 20.0 | 20.0 | 20.0 | 20.0 | 30.0 |

## Re-judged on measured costs

- 7 published rows re-priced; **0** were refused on a cost the broker does not charge and are restored to the queue; 0 are positive once the overcharge is removed.
  - `CHFNOK.carry.asia#input_symbol=CHFNOK` net -0.45838233 -> -0.39717052 (net rose on measured costs but stays negative: the refusal earns its place)
  - `XAUUSD.trend_ma_cross.continuous` net -0.06646664 -> -0.06534597 (net rose on measured costs but stays negative: the refusal earns its place)
  - `xau_m5_anti_breakout_overlap` net -0.00910692 -> -0.01310725 (the measured cost is HIGHER than the model charged: the refusal is confirmed and then some)
  - `xau_m5_anti_momentum_ny` net -0.00910692 -> -0.01310725 (the measured cost is HIGHER than the model charged: the refusal is confirmed and then some)
  - `XAUUSD.clock_transition.continuous#hold_bars=2_label=broker_rollover_lead_bars=2_mode=out_of_side=1_stamp_hour=23` net -0.0047422 -> -0.01310725 (the measured cost is HIGHER than the model charged: the refusal is confirmed and then some)
  - `CHFNOK.pca_residual.continuous#factor_symbols=['BCHUSD', 'ETHUSD', 'USDZAR', 'EURUSD', 'XAGUSD', 'JPN225', 'XNGUSD', 'WHEAT']` net -0.06297 -> -0.08766413 (the measured cost is HIGHER than the model charged: the refusal is confirmed and then some)
  - `CHFNOK.relative_value.continuous#peer_symbol=EURCHF` net -0.06297 -> -0.08766413 (the measured cost is HIGHER than the model charged: the refusal is confirmed and then some)

## Registry corrections, verified against the broker's own quote

- **106** corrections already APPLIED to the registry through `repair_universe_spreads.py --only-verified` (mode full).
- 30 still pending; **0** move the charge TOWARD the quote and are applied, 30 move AWAY and are refused, 0 have no measured quote here yet and are not applied, 0 are neutral.

| symbol | charged | corrected to | broker quotes | error before | after |
|---|---:|---:|---:|---:|---:|
| USDRUB | 21060.0 | 2582.5 | 90025.0 | 68965.0 | 87442.5 (AWAY) |
| XCUUSD | 4950.0 | 5100.0 | 3300.0 | 1650.0 | 1800.0 (AWAY) |
| XALUSD | 3150.0 | 3250.0 | 2100.0 | 1050.0 | 1150.0 (AWAY) |
| USDZAR | 329.0 | 349.0 | 249.0 | 80.0 | 100.0 (AWAY) |
| EURPLN | 124.0 | 134.0 | 87.0 | 37.0 | 47.0 (AWAY) |
| NZDHUF | 11624.0 | 12200.0 | 11600.0 | 24.0 | 600.0 (AWAY) |
| EURZAR | 312.0 | 358.0 | 332.0 | 20.0 | 26.0 (AWAY) |
| CHFNOK | 267.0 | 300.0 | 248.0 | 19.0 | 52.0 (AWAY) |
| USDPLN | 74.0 | 82.0 | 59.0 | 15.0 | 23.0 (AWAY) |
| EURSEK | 143.0 | 149.0 | 137.0 | 6.0 | 12.0 (AWAY) |
| DOTUSD | 33.0 | 34.0 | 30.0 | 3.0 | 4.0 (AWAY) |
| ADAUSD | 33.0 | 34.0 | 31.0 | 2.0 | 3.0 (AWAY) |
| EURAUD | 0.0 | 13.0 | 2.0 | 2.0 | 11.0 (AWAY) |
| GBPJPY | 1.0 | 13.0 | 3.0 | 2.0 | 10.0 (AWAY) |
| GBPNZD | 4.0 | 5.0 | 2.0 | 2.0 | 3.0 (AWAY) |
| AUDJPY | 0.0 | 16.0 | 1.0 | 1.0 | 15.0 (AWAY) |
| AUDSGD | 0.0 | 4.0 | 1.0 | 1.0 | 3.0 (AWAY) |
| EURCAD | 0.0 | 3.0 | 1.0 | 1.0 | 2.0 (AWAY) |
| GBPCAD | 0.0 | 3.0 | 1.0 | 1.0 | 2.0 (AWAY) |
| GBPSGD | 3.0 | 4.0 | 2.0 | 1.0 | 2.0 (AWAY) |
| NZDCAD | 0.0 | 17.0 | 1.0 | 1.0 | 16.0 (AWAY) |
| AUDUSD | 0.0 | 14.0 | 0.0 | 0.0 | 14.0 (AWAY) |
| CHFJPY | 1.0 | 18.0 | 1.0 | 0.0 | 17.0 (AWAY) |
| EURGBP | 0.0 | 13.0 | 0.0 | 0.0 | 13.0 (AWAY) |
| EURUSD | 0.0 | 12.0 | 0.0 | 0.0 | 12.0 (AWAY) |
| GBPUSD | 0.0 | 13.0 | 0.0 | 0.0 | 13.0 (AWAY) |
| NZDUSD | 0.0 | 14.0 | 0.0 | 0.0 | 14.0 (AWAY) |
| USDCAD | 0.0 | 13.0 | 0.0 | 0.0 | 13.0 (AWAY) |
| USDCHF | 0.0 | 13.0 | 0.0 | 0.0 | 13.0 (AWAY) |
| USDJPY | 0.0 | 13.0 | 0.0 | 0.0 | 13.0 (AWAY) |

## Named defects in code this organ does not own

- **data/universe/universe.json:median_spread_pts (the scalar every gate divides by) -- CORRECTION ALREADY COMPUTED AND NEVER APPLIED** -- 136 of 251 symbols carry a spread the desk's own repair tool already recomputed on 2026-09-16 (reports/SPREAD_PROVENANCE.json, apply_mode=report_only, applied=false). GBPCHF is stamped source=realized_fills at 165.0 pts on a symbol this account has NEVER traded, against a bar median of 3.0 and a terminal quoting 0.0/1.0 today; CADCHF 98.0 against 3.0; AUDCHF 110.5 against a live 2.0. Fix: `python desks/mt5/scripts/repair_universe_spreads.py --apply  # its own fills_overridden block already names GBPCHF 55.0x and CADCHF 32.7x` [REPORTED]
- **desks/mt5/research/net_edge_spine.py:commission_term** -- ratio = zero / (raw - zero) treats the RAW regime's 0.2x spread as the whole spread. Fix: `ratio = 0.2 * zero / (raw - zero)  # the RAW regime multiplier, divided out` [FIXED]
- **libs/portfolio/fusion_cost.py:COMMISSION_PER_LOT_PER_SIDE** -- 2.25 is documented as USD and applied as account currency; the account pays 2.00 EUR per lot per side, measured over every deal it has ever done. Fix: `set it from the measured per-side commission published here, or state the currency and convert` [FIXED]
- **desks/mt5/research/cost_surface.py:_EXEC_OUT** -- writes reports/COST_SURFACE.json while net_edge_spine reads reports/EXECUTION_COST_SURFACE.json, so the realised surface never reached the consumer and every spread term fell back to the modelled scalar. Fix: `this organ writes EXECUTION_COST_SURFACE.json (one writer, one reader) and reads COST_SURFACE.json; both pairs are declared in libs/ops/control_plane/edges.py and checked by plumbing_watchdog` [FIXED]
- **desks/mt5/research/cost_surface.py:deal_costs** -- cost_r there is (commission + swap)/risk, and the spine feeds cost_r into its SPREAD term and then adds commission again. Fix: `keep cost_r to spread and slippage, as the surface written here does` [FIXED]

Impact: matched_fills is 0: market impact is unpriced, so every net that needs it is a BOUND and the verdict says so

