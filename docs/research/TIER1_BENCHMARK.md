# TIER-1 PROCESS BENCHMARK — the standing gap register the desk hunts WITHOUT being told

*(principal orders 2026-07-31: "the quant should always maximise itself every day and any time it
sees gaps, I shouldn't have to manually tell — close every single gap left to tier-1 processes,
except something which can't be changed except by time" + "it shouldn't be just those 3 but
rather ALL highly aggressive profitable tier-1 firms with our motive similarity.")*

## THE BENCHMARK COHORT — every aggressive profitable systematic firm, weighted by MOTIVE SIMILARITY

The desk's motive: **compounding its OWN capital, survival-first, fully systematic, maximum
aggression inside hard ruin rails.** The cohort is therefore ranked by how similar that motive is
— a prop firm compounding its own book is a closer benchmark than a fee-collecting pod shop:

- **THE STANDING EXCEPTION, cited fully in every benchmark context: RenTech/Medallion** — the
  ceiling exemplar of the entire cohort and the proof of what the maximum actually is
  (internal-capital compounding, fully systematic, decades of survival, "we never override the
  model"). Every layer's T1 grade implicitly asks: *would this process be recognisable inside
  Medallion?* RenTech appears in full wherever this cohort is referenced — the deep sweep's
  EXTERNAL perspective, this register, doctrine — never abbreviated away.
- **HIGHEST similarity (own-capital prop, systematic):** RenTech Medallion (above, first always),
  Jane Street, XTX, Jump (incl. Jump Crypto), DRW/Cumberland, Optiver, SIG, IMC, Tower, HRT.
  Benchmark their: correctness culture (Jane Street's EV-discipline and "what makes this trade
  wrong" = our fences and gates), forecasting-at-scale and data-quality obsession (XTX),
  simulation/prod parity (HRT/Jump), options/vol expertise (Optiver/SIG), multi-strategy
  treasury discipline (DRW).
- **CRYPTO-NATIVE prop (same market, same 24/7 physics):** Wintermute, GSR, Amber, QCP,
  B2C2. Benchmark their: venue breadth with counterparty-risk scoring (the FTX lesson),
  24/7 ops automation, inventory/treasury management, withdrawal discipline.
- **PARTIAL similarity (external capital, still process-elite):** Citadel, DE Shaw, Two Sigma,
  Millennium/Point72, TGS, Voleon, PDT. Benchmark ONLY their transferable practices — ruthless
  per-sleeve capital reallocation and hard drawdown pulls (the pod mechanism), ML validation
  culture, forecast combination — while noting the motive mismatch: they manage redemption risk
  and fees; we manage ruin risk and compounding. Their caution is sometimes OUR timidity.
- **NEGATIVE EXEMPLARS (aggressive, profitable, DEAD — the cohort's control group):** Alameda
  (aggression without rails: commingling, no ruin rail, discretionary overrides), LTCM (leverage
  + convergence bets + no regime humility), Archegos (concentration + opacity). Every one died
  of a defect our constitution names: L1.23 survival-first, the capital-event ledger, the ruin
  rail's absorbing state, two-source-of-truth bans. **The desk's differentiator inside this
  cohort is not aggression — everyone here was aggressive — it is that our aggression is
  fenced.** These rows are doctrine context, never queue items.

Scale: **T1** = the process standard of the highest-similarity cohort above · **T2** = mid-tier
fund / serious prop · **T3** = advanced independent · **T4** = retail. Rated on PROCESS, not
capital.
`run_max_push.py` parses the table below every refresh: every row not at T1 whose `time_bound`
is `no` enters the daily max-push queue automatically. Editing this file IS re-benchmarking —
add rows when a new layer exists, re-grade when evidence moves a tier, and NEVER delete a
below-T1 row without landing it at T1 (the parser treats a vanished row as a silent cap).
Rows whose only closer is calendar time carry `time_bound: yes` and are listed, not queued —
they are walls, not work.

| layer | tier_now | closer_to_t1 | time_bound |
|---|---|---|---|
| validation_methodology | T3 | CUT 08-01: purge/embargo INERT (.train unreferenced; cpcv fraction identical to 6dp across a 250x parameter range), _PERIODS_PER_YEAR=24*260 on daily bars = 4.135x Sharpe overstatement, 3 of 11 gates carry zero information, certification is 2 targets x 1 SEED. Closer: N22 leak fix + N23 annualisation + real certification at SR 1-3 (8x12 harness exists, zero callers) | no |
| research_governance | T2 | CUT 08-01: L2.3's third disposition converts 0/6 on its first due date; the two push/CI-blocking fences are substring whitelists with unreachable failure states; 15 rows park in a status the tooling cannot write. Closer: one honest conversion meter + rate-based admission control | no |
| self_audit_layer | T2 | CUT 08-01: the T1 justification cited planted controls that do not exist (grep 'plant' -> no output). Closer: measure audit recall d by planting defects (X1), then restore | no |
| llm_native_automation | T3 | CUT 08-01: miner_seats_productive 9.1% -- 10 of 11 seats configured, credentialed, unit-tested, producing nothing; frontier seat's trailing echo swallows exit code so 7 failed digs report Result=success. Closer: exit $rc + brain_mutex distinguishable + reaper glob | no |
| risk_rails | T2 | R0071 money-path cluster + one clean live cycle | no |
| data_moat | T3 | CUT 08-01: its own closer (run_moat_backup) replicates a 0-table database and its restore drill hashes the replica against ITSELF. Closer: drill compares replica to SOURCE + the 7.4MB irreplaceable set committed + T7 retention probe 08-08 | no |
| data_engineering | T3 | CUT 08-01: survivorship at the source (LUNA/UST/FTT/SRM absent; panel selected on today's liquidity then backfilled 7y), 40% of symbols frozen 6 weeks, 5 non-crypto asset classes dark 43 days unnoticed. Closer: point-in-time universe from the exchangeInfo call already being discarded | no |
| alpha_generation_process | T2 | horizon-honest power gate (R0030/O1) + positive-control battery + resurrection consumer + fusion axes earned | no |
| alpha_generation_throughput | T4 | unfreeze generator post-R0077; L1.25a forbids idle generation; feed 12/12 forward slots daily | no |
| knowledge_reuse_read_side | T4 | phantom-DB repoint x4 (R0079) + one consumer per composed store, born-fenced | no |
| monitoring_observability | T3 | CUT 08-01: pager ~29% precision (2 of 7 standing CRITICALs provably false, 1 structurally unreachable); 11 fences exit 0 on absent input; no time-series store exists. Closer: != "OK" refusal path + false_page_rate ratchet | no |
| execution | T3 | R0071 stops/guards + TCA fields on all open paths (R0084) + maker-first routing measured | no |
| portfolio_construction | T3 | multi-sleeve risk model + correlation-budgeted allocation once n_sleeves >= 3 (R0101) | no |
| security_opsec | T4 | CUT 08-01: anonymous off-box fetch of the research web root returns desk content not a login page; push-capable PAT live in remote.origin.url and leaked to LLM vendors; deploy gate executes fetched code BEFORE gating it. Closer: Cloudflare Access + PAT rotation (principal) + scratch-checkout CI | no |
| conversion_repair | T2 | L1.28b fence flow: dispositions >= arrivals for 30 consecutive days | no |
| venue_breadth_counterparty | T4 | Bybit second venue (spec exists: BYBIT_SECOND_VENUE_SPEC.md) + venue-risk scoring + withdrawal drill -- the FTX lesson, Wintermute exemplar | no |
| simulation_prod_parity | T2 | cross-engine parity suite actually running (optional_test_deps ceiling: arch/backtrader/vectorbt) + verify_backtest_engine green + TCA-vs-sim drift measured -- HRT/Jump exemplar | no |
| inventory_treasury | T3 | fee-asset (BNB) auto-policy + stablecoin treasury rules + funding-payment sweep -- DRW/Wintermute exemplar | no |
| capital_reallocation | T2 | per-sleeve drawdown pulls + reallocate to measured performers once n_sleeves >= 2 (derisk ladder is the embryo) -- the one pod-shop practice worth taking | no |
| vol_surface_expertise | T4 | CUT 08-01: the only options dataset is a side-effect of the executor, forward-archive-only, ~1 obs/day, 15 gaps >24h in 35 days. Closer: schedule collect_deribit_surface hourly, decoupled from the executor | no |
| forecast_combination | T2 | fusion axes earn entry, then ensemble weighting across surviving axes -- XTX/TGS exemplar | no |
| capital_scale | T4 | compounding through capacity bands | **yes** |
| forward_history_depth | T3 | RE-GRADED 08-01 -- NOT time-bound: 82.86% of on-disk observations are discarded before any test runs (min_len truncation, 6+ scripts) and 345d of free first-party L2 is downloadable now. Closer: stratified campaign window (campaign_window.py exists, ZERO callers) + the free L2 backfill as features | no |
| track_record | — | Gate-0 -> first clean live year | **yes** |

**Grading map used by the parser** (declared, arguable, in one place): T1=1.00, T2=0.66,
T3=0.40, T4=0.15. A layer graded `—` in tier_now is time_bound by definition.

**Standing rule:** the deep sweep's synthesis (A) ceiling table and this register must agree —
where they diverge, the sweep re-grades this file in the same session (ledger-first, R0056
pattern), so the benchmark can never fossilize into flattery.
