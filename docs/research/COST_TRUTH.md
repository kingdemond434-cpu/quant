# COST TRUTH -- charged vs quoted vs realised

Generated 2026-09-23T04:07:05+00:00 by `desks/mt5/research/cost_truth.py` (hourly leg `cost_truth`). DERIVED -- edit the organ, never this page.

Account **495044** (Fusion Markets Pty Ltd, FusionMarkets-Live, EUR), terminal MEASURED, 433 deals, 54 symbols, 8 with a realised reading.

## The commission term, which is ~98% of the charged cost

- model charges **2.25** per lot per side (libs/portfolio/fusion_cost)
- account actually pays **2.0** per lot per side (median over 8 symbol readings, p10 2.0, p90 2.0)
- rate overcharge **1.125x**, regime overcharge **5.0x**, total **5.625x**
- why: the spine derives commission/spread as zero/(raw-zero), but raw is the 0.2x regime, so raw-zero is 0.2 of the spread and the ratio is 5.0x too large; the rate itself is charged in account currency at a figure documented as USD

## Where the model charges more than the venue

| symbol | charged pts | quoted pts (reference) | spread ratio | commission ratio |
|---|---:|---:|---:|---:|
| GBPCHF | 165.0 | 1.0 | 165.0 | 5.0 |
| CADCHF | 98.0 | 1.0 | 98.0 | 5.0 |
| AUDCHF | 110.5 | 3.0 | 36.8333 | 5.0 |
| XAUUSD | 14.5 | 5.0 | 2.9 | 5.625 |
| GBPAUD | 4.0 | 2.0 | 2.0 | 5.0 |
| CHFNOK | 267.0 | 248.0 | 1.0766 | 5.625 |
| AUDCAD | 1.0 | 1.0 | 1.0 | 5.625 |
| AUDNZD | 1.0 | 1.0 | 1.0 | 5.625 |
| CADJPY | 1.5 | 1.0 | 1.5 | 5.0 |
| CHFSGD | 3.0 | 2.0 | 1.5 | 5.0 |
| GBPSGD | 3.0 | 2.0 | 1.5 | 5.0 |
| USDZAR | 329.0 | 249.0 | 1.3213 | 5.0 |
| EURJPY | 5.0 | 4.0 | 1.25 | 5.0 |
| BTCUSD | 1900.0 | 1794.0 | 1.0591 | 5.0 |
| CHFJPY | 1.0 | 1.0 | 1.0 | 5.0 |
| NAS100 | 80.0 | 80.0 | 1.0 | 5.0 |
| NZDCHF | 1.0 | 1.0 | 1.0 | 5.0 |
| EURZAR | 312.0 | 332.0 | 0.9398 | 5.0 |
| US30 | 150.0 | 160.0 | 0.9375 | 5.0 |
| EURMXN | 185.0 | 200.0 | 0.925 | 5.0 |
| USDDKK | 34.0 | 42.0 | 0.8095 | 5.0 |
| XBRUSD | 16.0 | 20.0 | 0.8 | 5.0 |
| XTIUSD | 16.0 | 20.0 | 0.8 | 5.0 |
| EURCHF | 0.5 | 3.0 | 0.1667 | 5.625 |
| EURNOK | 153.0 | 197.0 | 0.7766 | 5.0 |

## Session structure (M1 spread in points, the broker's own tape)

| symbol | asia | london | ny | late | rollover | live |
|---|---:|---:|---:|---:|---:|---:|
| AUDCAD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| AUDCHF | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| AUDJPY | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| AUDNZD | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 5.0 |
| AUDSGD | 0.0 | 1.0 | 2.0 | 1.0 | 1.0 | 1.0 |
| AUDUSD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| BTCUSD | 1794.0 | 1794.0 | 1794.0 | 1794.0 | 1794.0 | 2062.0 |
| CADCHF | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| CADJPY | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| CHFDKK | 77.0 | 54.0 | 45.0 | 53.0 | 59.0 | 80.0 |
| CHFJPY | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 5.0 |
| CHFNOK | 637.0 | 272.0 | 230.0 | 265.0 | 268.0 | 504.0 |
| CHFSEK | 1454.0 | 616.0 | 563.0 | 598.0 | 681.0 | 1702.0 |
| CHFSGD | 2.0 | 2.0 | 3.0 | 3.0 | 2.0 | 4.0 |
| EURAUD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 4.0 |
| EURCHF | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 2.0 |
| EURGBP | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EURILS | 890.0 | 190.0 | 80.0 | 150.0 | 150.0 | 3093.0 |
| EURJPY | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 5.0 |
| EURMXN | 494.0 | 212.0 | 169.0 | 160.0 | 157.0 | 493.0 |
| EURNOK | 457.0 | 148.0 | 117.0 | 185.0 | 178.0 | 402.0 |
| EURNZD | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 4.0 |
| EURUSD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| EURZAR | 786.0 | 308.0 | 238.0 | 299.0 | 326.0 | 721.0 |
| GBPAUD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| GBPCAD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 2.0 |
| GBPCHF | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| GBPJPY | 3.0 | 3.0 | 2.0 | 3.0 | 3.0 | 5.0 |
| GBPMXN | 1034.0 | 530.0 | 393.0 | 340.0 | 337.0 | 1058.0 |
| GBPNOK | 895.0 | 378.0 | 317.0 | 420.0 | 431.0 | 865.0 |
| GBPSEK | 493.0 | 187.0 | 173.0 | 232.0 | 244.0 | 448.0 |
| GBPSGD | 2.0 | 2.0 | 4.0 | 3.0 | 3.0 | 4.0 |
| GBPUSD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| GBPZAR | 1495.0 | 602.0 | 536.0 | 639.0 | 709.0 | 1346.0 |
| GER40 | 320.0 | 320.0 | 80.0 | 120.0 | 120.0 | 320.0 |
| NAS100 | 80.0 | 80.0 | 80.0 | 80.0 | 80.0 | 80.0 |
| NZDCAD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| NZDCHF | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 2.0 |
| NZDUSD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| SGDJPY | 2.0 | 2.0 | 3.0 | 2.0 | 2.0 | 4.0 |
| US30 | 280.0 | 160.0 | 160.0 | 120.0 | 120.0 | 280.0 |
| USDCAD | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| USDCHF | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| USDDKK | 53.0 | 39.0 | 36.0 | 41.0 | 42.0 | 61.0 |
| USDHUF | 48480.0 | 17200.0 | 13800.0 | 16300.0 | 17100.0 | 48980.0 |
| USDJPY | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| USDMXN | 394.0 | 216.0 | 171.0 | 151.0 | 148.0 | 430.0 |
| USDNOK | 388.0 | 145.0 | 116.0 | 175.0 | 172.0 | 332.0 |
| USDZAR | 690.0 | 237.0 | 182.0 | 193.0 | 188.0 | 654.0 |
| XAUAUD | 13.0 | 12.0 | 12.0 | 13.0 | 13.0 | 28.0 |
| XAUEUR | 6.0 | 6.0 | 6.0 | 6.0 | 6.0 | 14.0 |
| XAUUSD | 5.0 | 5.0 | 5.0 | 5.0 | 5.0 | 10.0 |
| XBRUSD | 20.0 | 20.0 | 20.0 | 20.0 | 20.0 | 40.0 |
| XTIUSD | 20.0 | 20.0 | 20.0 | 20.0 | 20.0 | 20.0 |

## Re-judged on measured costs

- 24 published rows re-priced; **6** were refused on a cost the broker does not charge and are restored to the queue; 6 are positive once the overcharge is removed.
  - `external.EURCHF.discovered.p=16bd35526c7f3515` net -0.5382099 -> 0.05384614 (refused on a cost the broker does not charge)
  - `external.EURCHF.discovered.p=e266baf78567bef3` net -0.59324277 -> -0.00118673 (net rose on measured costs but stays negative: the refusal earns its place)
  - `external.EURCHF.discovered.p=a5bbf78b5c8595c0` net -0.68840611 -> -0.09635007 (net rose on measured costs but stays negative: the refusal earns its place)
  - `external.EURCHF.discovered.p=c7d53510458ba32c` net -0.6908928 -> -0.09883676 (net rose on measured costs but stays negative: the refusal earns its place)
  - `external.EURCHF.discovered.p=c14e361e680e6d0b` net -0.71235755 -> -0.12030151 (net rose on measured costs but stays negative: the refusal earns its place)
  - `external.EURCHF.discovered.p=4cba1afa572a99cd` net -0.71331506 -> -0.12125902 (net rose on measured costs but stays negative: the refusal earns its place)
  - `external.EURCHF.discovered.p=6c7943b997558157` net -0.72238099 -> -0.13032495 (net rose on measured costs but stays negative: the refusal earns its place)
  - `external.EURCHF.discovered.p=9bc1f7c40f200e78` net -0.72392887 -> -0.13187283 (net rose on measured costs but stays negative: the refusal earns its place)
  - `external.EURCHF.discovered.p=16bd35526c7f3515` net -0.5382099 -> 0.05384614 (refused on a cost the broker does not charge)
  - `external.AUDCAD.discovered.p=8030fb339510dceb` net -0.20944835 -> 0.05743767 (refused on a cost the broker does not charge)
  - `external.AUDCAD.discovered.p=a7324e7affe1f80a` net -0.28139463 -> -0.01450861 (net rose on measured costs but stays negative: the refusal earns its place)
  - `external.AUDCAD.discovered.p=7c996ac8456c8919` net -0.3020176 -> -0.03513158 (net rose on measured costs but stays negative: the refusal earns its place)

## Named defects in code this organ does not own

- **data/universe/universe.json:median_spread_pts (the scalar every gate divides by) -- CORRECTION ALREADY COMPUTED AND NEVER APPLIED** -- 136 of 251 symbols carry a spread the desk's own repair tool already recomputed on 2026-09-16 (reports/SPREAD_PROVENANCE.json, apply_mode=report_only, applied=false). GBPCHF is stamped source=realized_fills at 165.0 pts on a symbol this account has NEVER traded, against a bar median of 3.0 and a terminal quoting 0.0/1.0 today; CADCHF 98.0 against 3.0; AUDCHF 110.5 against a live 2.0. Fix: `python desks/mt5/scripts/repair_universe_spreads.py --apply  # its own fills_overridden block already names GBPCHF 55.0x and CADCHF 32.7x` [REPORTED]
- **desks/mt5/research/net_edge_spine.py:commission_term** -- ratio = zero / (raw - zero) treats the RAW regime's 0.2x spread as the whole spread. Fix: `ratio = 0.2 * zero / (raw - zero)  # the RAW regime multiplier, divided out` [REPORTED]
- **libs/portfolio/fusion_cost.py:COMMISSION_PER_LOT_PER_SIDE** -- 2.25 is documented as USD and applied as account currency; the account pays 2.00 EUR per lot per side, measured over every deal it has ever done. Fix: `set it from the measured per-side commission published here, or state the currency and convert` [REPORTED]
- **desks/mt5/research/cost_surface.py:_EXEC_OUT** -- writes reports/COST_SURFACE.json while net_edge_spine reads reports/EXECUTION_COST_SURFACE.json, so the realised surface never reached the consumer and every spread term fell back to the modelled scalar. Fix: `this organ now writes EXECUTION_COST_SURFACE.json; the two producers must be reconciled to one name` [BRIDGED]
- **desks/mt5/research/cost_surface.py:deal_costs** -- cost_r there is (commission + swap)/risk, and the spine feeds cost_r into its SPREAD term and then adds commission again. Fix: `keep cost_r to spread and slippage, as the surface written here does` [REPORTED]

Impact: matched_fills is 0: market impact is unpriced, so every net that needs it is a BOUND and the verdict says so

