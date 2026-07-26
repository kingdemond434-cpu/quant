# DEEP COLD AUDIT — ALPHA-DISCOVERY SUBSYSTEM — 2026-07-26

_Auditor: weekly deep cold audit (doctrine v2). Scope: hypothesis diversity, unexplored market
behaviors, crowded themes, neglected regimes, cross-asset transfer, temporal-resolution gaps,
feature interactions, regime-conditioned hypotheses, causal-vs-correlational, hypothesis
redundancy, negative-result reuse, abandoned-idea reassessment, falsification quality, ignored
markets/public-info, untestable-for-missing-data signals. READ-ONLY sweep; every claim carries
its proving command._

## SCORES (headline)

- current_capability_pct: **45%** — falsification/negative-knowledge machinery is world-class (~90th pct);
  generation breadth, construction diversity, and gate calibration are far below their own ceiling
  (effective independent hypotheses tested ≈ 8 price constructions + ~10 screened data axes; ≥9 ingested
  axes never screened; intraday resolution 0% exploited).
- practical_ceiling_estimate: **85%** with existing data + existing harness (no new spend): every ingested
  axis screened, 12/12 slots saturated, moat/intraday program running, gate discriminating instead of vetoing.
- ceiling_gap: **~40 points**, most of it closable with tools already built (axis_screen, anytime_valid,
  backfill scripts) pointed at data already on disk.
- opportunity_cost_1y: at the desk's own measured hit rate (1 validated axis — kimchi — per ~10 screened),
  the ≥9 unscreened ingested axes + unmined intraday moat plausibly hide 1–3 kimchi-grade signals. One
  kimchi-grade edge (screen IC +0.148, timing Sharpe 1.3) compounding a year vs. not = the single largest
  line item the desk controls; secondarily, every week of slot under-saturation burns irreplaceable
  calendar time (the desk's own #1 bottleneck) at ~50–75% utilization.
- confidence: **0.8** on the INTERNAL findings (all command-verified); 0.5 on the ranked opportunity sizes.
- unknown_unknown_score: **medium-high (0.6)** — concentrated in (a) intraday/microstructure behavior the
  desk has never once looked at despite owning the data, and (b) the true false-negative rate of the EV
  gate, which is unmeasured by design (no reject shadow-tracking artifact exists).
- info_gain_if_investigated: highest for the gate-calibration audit (bounded cost, resolves whether the
  desk has been discarding real edges for a month) and the moat screen (first look at a 3.5GB owned dataset).
- expected_alpha_contribution: direct — 1–3 new Stage-B candidates within 60d from axis screens + trader-split
  + intraday families; indirect — gate recalibration raises the yield of every future generation cycle.
- expected_compounding_contribution: trials_ledger population + single clock registry + gate audit loop are
  pure compounding multipliers: they make every future validation cheaper and every future audit honest.
- CEILING EXPANSION: the 85% ceiling assumes daily-bar, single-venue-class, crypto-only discovery. The
  assumption that defines it is **organizational, not technological**: "research = daily bars" is a habit
  formed when the lake was built, not a measured limit — the moat recorder already collects 1s depth. If
  the intraday program validates even one family, the ceiling itself moves (event-time research on owned
  tick data is a different, larger search space).

---

## 1. WHAT WE KNOW (validated strengths, each with proving command)

**K1 — Falsification quality is genuinely excellent; this is the subsystem's proven strength.**
`docs/graveyard.md` (83 lines) carries: kill-basis discipline (economic vs data/infra vs
external-literature, three explicitly separated evidence classes), the de-contamination (angle-20)
artifact gate that caught `coinbase_premium_timing` (contam corr +0.256) and `try_premium_timing`
(−0.495), the lookahead rail that caught `bithumb_kr_premium_lookahead` (IC 0.72 / Sharpe 10.0 —
flagged SUSPECT-LOOKAHEAD by the |IC|>0.35 tripwire), and a redundancy kill (`coinone_kr_premium`:
passes the gate but same-axis as kimchi → not a separate clock). Era natural-experiment mining
(Bitcointalk contest: 0/8 beat B&H forward vs 6/8 in-sample) independently corroborates the desk's
own 420/0 record. Proving: `cat docs/graveyard.md` rows 37–46.

**K2 — Negative-result reuse is real and disciplined, including externally sourced nulls.**
External-literature priors (HXZ 2020 per-category replication rates, McLean–Pontiff 58% haircut,
Brigida TVL nulls) were imported with provenance discipline — one finding (Li & Zhu F11) was
deliberately HELD BACK because only summary-level text was available ("Recording the abstention
because the temptation to round it up is exactly how a phantom prior gets installed permanently").
Proving: `docs/graveyard.md:70-83`. The prospector session credits "nothing new" as a valid result
(`docs/research/prospector_watchlist.md:17-25`).

**K3 — The Two-Stage Discovery Law is a statistically sound design, mechanically enforced on the
over-budget side.** Stage A unlimited/zero promotion authority; Stage B forward-only with a
12-slot Holm-bounded cohort. `grep -n "slot_budget" scripts/run_alerts.py` → line 243 pages
`slot_budget_exceeded` when count > 12. The forward clocks genuinely refuse screen-sample P&L:
`data/axis_shadow_state.json` → "P&L starts at the clock's first row, never the screen sample."

**K4 — Screen-on-discovery operates and produced the desk's best asset.** Batch screen artifacts
on disk: `ls data/batch_*.json` → altdata, bridge, coinmetrics, github(×2), kaiko, onchain, premium
(8 files, 07-23→07-26). Kimchi premium came through this path and now runs a Stage-B clock
(`data/axis_shadow_state.json`: kimchi_premium ACCRUING 4/40d). The wikipedia axis was screened to
a clean SCREEN-WEAK verdict across 5 languages (`data/batch_altdata_screen.json`: IC 0.013–0.065,
decontam passed) — negative screens are being banked as first-class results.

**K5 — The reconstruction lever (MAX_SURVIVORS Part 1 #1) has actually run, not just been specced.**
`wc -l data/oi_ls_history.jsonl` → 600 rows back to 2021-06-01;
git log 2026-07-23: "OI/LS universe backfill: threaded archive downloader + cross-sectional held-out
OOS (chained)"; `data/batch_kaiko_reconstruction.json` updated 2026-07-26 with a documented VWM
methodology and honest exclusion (gemini pagination gap excluded rather than truncated).

**K6 — Anytime-valid inference is wired in, not decorative.** `grep -rln "anytime_valid" scripts/`
→ ingest_axes.py, ingest_crypto_enriched.py, run_derivative_shadow.py, run_factory.py. Peek
e-values are live on the derivative-metrics clocks (AXIS_PREREGISTRATIONS covered-axes note).

**K7 — Forecast calibration is measured and self-correcting.** `research_state.json:137-146`:
n=30 resolved, Brier 0.0722, bias −0.2 labeled "under-confident" with a shrinkage rule. The desk
knows its own forecast error direction.

## 2. WHAT WE DON'T KNOW (ignorance ledger)

**U1 — The EV gate's false-negative rate is unmeasured, and its measurement loop is broken.**
Lifetime record assembled this audit: **1 QUEUE ever** (funding_decay_predictor, 2026-07-12 —
never built, still rank-3 in `engineering_backlog_top` 14 days later) vs ≥16 REJECTs (11/11 axis
pre-registrations 07-22, 3+ graveyard EV-kills 07-19, prospector session 0-kept 07-19, kama_squeeze
07-11). `grep -rn "QUEUE (top-EV" data/ docs/ scripts/` → hits only the source file. The gate's own
scoring ledger `data/ev_gate_audit.json` holds **3 entries** — the entire 11-verdict 07-22 batch was
never appended, so the n≥50 recalibration trigger is unreachable at the observed logging rate. The
reject shadow-tracking specced in `MAX_SURVIVORS_PROGRAM.md` Part 1 #2b has **no artifact on disk**
(`grep -rln "reject.*shadow" data/` → no reject-tracking file). GATE-OPTIMALITY DUTY names exactly
this pattern: a gate rejecting ~100% carries zero information. We do not know whether cme_anchored_
basis_dislocation (p_survive 0.48 — the gate's own highest-ever prior) is a real edge, because it
was vetoed before any data touched it.

**U2 — The desk's true effective trial count is unknowable from the designed source.** The
hash-chained `trials_ledger` is **empty in all four research DBs** (`SELECT COUNT(*) FROM
trials_ledger` → 0, 0, 0, 0 in sor_crypto/sor_autodiscovery/sor_research/sor_research_lake_v2).
Raw candidates: 420+57+14+49 = 540, but the 420 decompose into **8 constructions** × 12 symbols ×
param grids (`SELECT family,subtype`: ma_cross 90, time_series_mom 90, funding_stress_reversal 60,
zscore_fade 60, shock_fade 30, vol_trend 30, squeeze_breakout 30, inverse_reference 30), generated
on 2 batch days. Whether DSR/Holm deflates by ~540 (over-penalizing → real edges silently lost) or
by ~8 (under-penalizing) is not recorded anywhere. MAX_SURVIVORS Part 1 #2a (effective-trial
clustering) is specced, not run.

**U3 — Everything intraday.** The desk owns 3.5GB / 9,574 files of 1s-depth + 5s-trades across
3 venue books × ~20 symbols (`du -sh data/moat/` → 3.5G) and 33,990 tick liquidation rows
(`data/liquidations.parquet` since 07-09), yet `grep -rln "moat" libs/ scripts/` shows **only
execution/recorder/forensics consumers — zero research consumers**. Research resolution is D1 + H8
funding only (`find data/lake/bronze -type d` → 356 D1 dirs, 10 H8). Funding-settlement boundary
effects, expiry pinning, cascade micro-reversal, book-imbalance predictivity — all named in the
desk's own 07-24 forced-mechanism mandate — are untested and *untestable at D1*. The desk has
never once looked at its own highest-resolution, only-proprietary dataset through a research lens.
`libs/research/microstructure.py` (book-imbalance primitive) exists and has never been screened
into a candidate.

**U4 — Whether kimchi generalizes, and what Plan B is.** The flagship axis is 4/40 forward days
(cum −2.6%, ann Sharpe −14.6 — noise at n=4, but the desk's discovery narrative leans heavily on
one axis). The regional-premium class is otherwise exhausted (KR/JP/BR/TR/Coinbase all dead —
graveyard rows 38–41), so kimchi failing forward would leave the new-axis pipeline holding
stablecoin_supply (3d) and cny (0d) only.

**U5 — Bear/stress-regime behavior of every current candidate.** The desk's entire live+shadow
existence is 2026-06→07 (one regime). Backfilled OI/LS reaches 2021-06 (600d, covers two crash
regimes) but only Stage-A can use it — Stage-B is forward-only by law, correctly. Unknown: which
of the current 6-7 clocks' signals are regime-conditional. The black_swan_library (19 scenarios)
gates *promoted* alphas; nothing regime-stresses *candidates* pre-slot.

**U6 — Whether the authored-mechanism path produces different alpha than the screen path.** 100%
of surviving discoveries came from data screens (kimchi, stablecoin, cny); 0% from authored
structural hypotheses — because the authored path has a 0% gate pass-rate (U1), not because it was
tried and failed. These search different spaces: screens test "axis has a simple daily timing
signal"; authored hypotheses test structure (basis dislocations, flow pressure, xsec rotation).
The desk cannot currently distinguish "authored hypotheses don't work" from "authored hypotheses
are never allowed to run."

**U7 — The desk-wide Holm cohort.** `data/axis_shadow_state.json` corrects with m_concurrent=3
(its own 3 axes). The true concurrent Stage-B cohort is ~9-10 (3 axis clocks + 3 derivative-metrics
clocks + trend_regime challenger + carry/perp_ls). If each subsystem Holm-corrects only within its
own file, the desk-wide false-promotion rate exceeds design. Not verified either way this sweep
(the binance-metrics clocks' Holm computation was not read) — flagged for the daily integrity watch.

## 3. WHAT COULD MATTER MOST (ranked opportunities)

Ranked by expected impact × confidence / (cost × maintenance). ★ = compounding multiplier.

**R1 ★ — Run the gate-calibration audit that is already specced (MAX_SURVIVORS Part 1 #2).**
- *Exactly what:* (a) cluster the 540 candidates by mechanism fingerprint → effective-N; recompute
  the DSR/Holm bar with it; (b) append ALL historical EV verdicts to `ev_gate_audit.json` (the 07-22
  batch of 11 is missing); (c) start shadow-tracking a sample of EV-rejects forward (zero capital,
  pure information); (d) recalibrate `effort_h`: the 8h default predates the axis_screen harness —
  kimchi screened in ~1h. At effort_h=1 the same arithmetic flips cme (0.0326→~0.26), etf_flows
  (0.0191→~0.15), wikipedia (→~0.15) to QUEUE; the gate becomes a discriminator instead of a veto.
- *Why:* U1+U2. A gate with a 0% accept rate carries zero information (GATE-OPTIMALITY DUTY) and
  its cost is invisible: every real edge it killed is compounding lost silently.
- *Evidence:* `libs/research/alpha_economics.py:33-34` (_BASE_P 0.15, threshold 0.05, effort 8h ⇒
  a default-shaped idea needs p_survive≥1.6, an impossibility — cap is 0.95); AXIS_PREREGISTRATIONS
  11/11 REJECT; ev_gate_audit.json n=3.
- *Benefit:* recovers wrongly-rejected edges (each is a Stage-B candidate); makes the multiplicity
  bar honest in BOTH directions. *Complexity:* low — hours; all inputs on disk. *Dependencies:* none.
- *Validation:* the audit's own output — accept-rate histogram per GATE-OPTIMALITY DUTY; reject
  shadow-track P&L after 40d. *Failure modes:* effort-recalibration overshoots → gate becomes a
  rubber stamp; guard: Stage-A screens cost ~1h, so even 100% QUEUE only costs screen-hours, never
  bar integrity (Two-Stage law). *Alternatives:* delete the gate entirely and screen everything —
  rejected: the mechanism-first prior (420/0 evidence) is worth keeping as a *ranking*, not a veto.
- *ROI:* very high. *Confidence:* 0.85. *Interactions:* feeds R2 directly. *Maintenance:* the audit
  ledger append must be wired into the same code path as the verdict (fix the leak, not the symptom).
  *Monitoring:* per-cycle accept/reject histogram (already mandated by GATE-OPTIMALITY DUTY, not
  produced today). *Retirement:* when n≥50 scored verdicts and the priors become posteriors, per the
  ledger's own policy. *Horizons:* 1w audit done / 1m recalibrated gate + first shadow-reject data /
  3m first recovered edge at Stage B / 1y-3y compounding via higher generation yield.

**R2 — Screen the ≥9 ingested-but-never-screened axes through the audited harness; saturate the
12-slot budget.** 
- *Exactly what:* run `libs.research.axis_screen` over the lake axes that have data but no batch
  artifact: cme, etf_flows, fx, equity, index, metal, energy, mining, fed (+ crossasset composite),
  using the AXIS_PREREGISTRATIONS mechanism cards (already written, already pre-registered!) as the
  stated mechanisms. Enroll survivors in empty Stage-B slots. Fix slot accounting while there:
  `run_alerts.py:242` counts a hardcoded 6 + an empty registry (`cat data/shadow_sleeves.json` →
  `[]`) while real clocks live in `axis_shadow_state.json` — the guard cannot see the true cohort.
- *Why:* Stage A is statistically free by the desk's own law; each screen is ~1h by the kimchi
  precedent; the axes are INGESTED (`ls data/lake/bronze/` → 15 axis dirs) so this is pure
  data-utilization debt. Slot vacancy (~6-10 of 12 occupied depending on count) directly wastes the
  desk's own #1 bottleneck: calendar time. At 7/12 occupancy the desk burns ~42% of its forward-clock
  throughput. CLOCK-SATURATION DUTY calls an empty clock "idle capital's research twin."
- *Evidence:* `ls data/batch_*.json` → screens exist for only altdata/bridge/coinmetrics/github/
  onchain/premium/kaiko; none for the 9 axes above. Screen-hit precedent: 1 validated axis (kimchi)
  per ~10 screened.
- *Benefit:* 1–2 new Stage-B clocks within 2 weeks at historical hit rate. *Complexity:* low-medium
  (alignment care per axis — the FX-close vs UTC-close hazard is a documented standing trap).
  *Dependencies:* R1(d) optional but synergistic. *Validation:* verdicts logged per §26.3, every
  construction recorded, negative screens graveyarded with reason. *Failure modes:* timestamp
  misalignment manufacturing a bithumb-style artifact — the hardened rail (|IC|>0.35 tripwire)
  already guards this. *Alternatives:* wait for the EV gate rework first — rejected: screens don't
  need gate permission under the Two-Stage law. *ROI:* high. *Confidence:* 0.8. *Interactions:*
  consumes AXIS_PREREGISTRATIONS cards; fills TWO_STAGE slots; the cross-asset lake was built for
  exactly this. *Maintenance:* one collector per axis already exists. *Monitoring:* axis_shadow_state
  clock count vs 12, alert on <10 occupied (invert the existing over-budget alert). *Retirement:* when
  all ingested axes carry a screen verdict (then the duty is data-driven, not backlog-driven).
  *Horizons:* 1w screens done / 1m slots saturated / 3m first Holm survivor possible / 1y validated
  breadth beyond funding-family.

**R3 ★ — Open the intraday/microstructure search space on data the desk already owns (the moat).**
- *Exactly what:* a bounded first program, three families at native resolution, all
  capacity-appropriate for a $15k desk: (1) funding-settlement boundary drift (H8 boundaries; lake
  already H8); (2) liquidation-cascade micro-reversal (liquidations.parquet ticks × moat depth);
  (3) book-imbalance predictivity at minutes (microstructure.py primitive, never screened). Each a
  counted trial at the standard bar.
- *Why:* U3. This is the only dataset the desk owns that nobody else has (its own recorder's tape) —
  the definitionally uncrowded search space — and the 420/0 lesson ("edges are in untouched axes")
  points here harder than at any external axis. Sub-institutional capacity is the desk's stated moat
  (`STRUCTURAL_EDGE_IDEAS.md` #3).
- *Evidence:* `du -sh data/moat/` → 3.5G; 9,574 files; consumers grep → zero research readers.
- *Benefit:* first entry into an entire orthogonal alpha class (execution-adjacent, high-frequency
  decay-resistant at small size). *Complexity:* medium — event-time feature builds from jsonl.gz
  depth snapshots; real engineering. *Dependencies:* none (data + primitives exist). *Validation:*
  same gauntlet; costs modeled at taker unless maker-verified; intraday costs are the killer —
  model them FIRST (funding_momentum died of costs at daily; intraday is stricter). *Failure modes:*
  cost-floor kills everything (informative null — closes the class honestly); moat depth (30d) too
  short for significance → screens rank, clocks confirm, same as everywhere. *Alternatives:* buy
  Tardis history — rejected pending free-first evidence per data_universe_map posture. *ROI:* high
  variance, high option value. *Confidence:* 0.55. *Interactions:* execution_tape/TCA share the
  parsing; features feed execution quality even if no alpha survives (double-dip). *Maintenance:*
  recorder already runs. *Monitoring:* per-family trial counts in the (to-be-populated) trials_ledger.
  *Retirement:* class closes if all three families fail cost-floor at native resolution. *Horizons:*
  1m first screens / 3m first forward clock / 1y an uncrowded validated family or an honest closure.

**R4 — Wire the trader-type split the desk's own literature organ already identified as the
binding constraint.** 
- *Exactly what:* add Binance `topLongShortPositionRatio` + `topLongShortAccountRatio` to
  `collect_binance_metrics.py` (same free keyless family as the three endpoints already pulled);
  screen `top − global` divergence per the KRT hedging-pressure design in LIT_b.
- *Why:* `grep -rn "topLongShort" scripts/ libs/` → **absent**, while
  `LIT_b_forgotten_literature.md:131-140` states "LACK, and this is the binding constraint: a
  trader-type split… the aggregate is uninformative (t=−0.43) and only the split predicts." Every
  uncollected day is forward history destroyed at source (mining-never-regresses law).
- *Benefit:* converts a mechanism-rich literature finding into an accruing axis for the cost of one
  collector field. *Complexity:* trivial. *Dependencies:* none. *Validation:* axis_screen + clock.
  *Failure modes:* endpoint history is shallow (30d rolling) — start NOW for exactly that reason.
  *ROI:* very high per unit effort. *Confidence:* 0.9 on the wiring, 0.3 on the edge. *Maintenance:*
  ~zero. *Monitoring:* collector heartbeat. *Retirement:* screen verdict decides. *Horizons:* 1w
  collecting / 3m screenable / 1y clock-resolvable.

**R5 — Reassess the two formally-abandoned-with-conditions ideas whose conditions are now cheap
to meet.** 
- (a) **Options VRP** — killed `no_breadth` with the desk's best campaign IC (+0.06), revisit
  condition "more vol markets." `data/deribit_surface.parquet` is still BTC+ETH only, 66 rows,
  ~2/day (`pd.read_parquet` → currencies {BTC:33, ETH:33}). Deribit now lists SOL/XRP options:
  widen the collector + raise cadence → the revisit condition is met by a config change. The
  breadth-2 kill was correct; leaving the revisit unscheduled for a signal with that pedigree is not.
- (b) **funding_decay_predictor** — the only idea the EV gate ever queued (p_survive 0.30,
  funding-family ×2.0 — the desk's lone repeat-survivor family), sitting unbuilt since 07-12
  (`engineering_backlog_top` rank 3, effort 4h). Either build it or write down why the gate's sole
  QUEUE is not worth 4 hours — silence is the one indefensible state.
- *ROI:* high (both are pre-vetted). *Confidence:* 0.7. *Horizons:* 1m both testable.

**R6 ★ — Populate the trials_ledger and unify clock state (single source of multiplicity truth).**
- *Exactly what:* every screen construction, EV verdict, and factory candidate appends one
  hash-chained row (the schema exists in all 4 DBs, unused); migrate the scattered clock states
  (axis_shadow_state, per-sleeve shadow files, hardcoded `_standing=6`) into the registry
  `shadow_sleeves.json` the law already names.
- *Why:* U2 + U7. The desk's statistical honesty currently rests on documents, not on the
  tamper-evident ledger built for it; the slot guard reads a constant.
- *Complexity:* low-medium. *ROI:* pure compounding. *Confidence:* 0.85. *Retirement:* never — this
  IS the bookkeeping. *Horizons:* 1m wired / every future audit cheaper and every future DSR honest.

*Explicitly NOT recommended this sweep:* new language miners (STOP line stands), paid data (free
frontier unexhausted — R2/R3/R4 are all $0), re-testing graveyarded classes (sacred), loosening any
Stage-B bar (the bar is the product).

## 4. WHAT WE TEST NEXT (concrete experiments)

**T1 — Gate false-negative probe (from R1).** Hypothesis: the EV gate discards real edges.
Method: shadow-track the 11 EV-rejected axis hypotheses forward at $0 (they are pre-registered
already — the cards in AXIS_PREREGISTRATIONS carry construction + falsifier). Success criterion:
after 40 forward days, if ≥1 rejected hypothesis clears its own falsifier bar (NW-t>0 at the stated
construction), the gate's false-negative rate is nonzero and effort_h recalibrates. Validation:
Holm-correct within this probe cohort; these accrue NO slot rights (information-only, outside the
12-slot budget since they cannot promote). Retirement: probe ends at 40d with either a measured FN
rate or a vindicated gate — both are permanent calibration assets.

**T2 — Nine-axis screen sweep (from R2).** Hypothesis: ≥1 of the 9 unscreened ingested axes holds
a kimchi-grade signal. Method: axis_screen per axis, mechanism cards as pre-registrations, every
construction logged, alignment declared per axis (FX/CME close-time hazard explicit). Success:
any SCREEN-PASS earns a real Stage-B slot; 9 SCREEN-WEAKs close the cross-asset question with
evidence and free the attention permanently. Timeline: ~2 weeks part-time. Retirement: automatic —
verdicts are terminal either way.

**T3 — Funding-settlement boundary study (from R3, first intraday probe).** Hypothesis: predictable
drift exists around the three daily 8h funding timestamps, exploitable at $15k size. Method: event
study on moat trades/depth ±30min around boundaries, 20 symbols × ~30d ≈ 1,800 events; cost-floor
first (gross must exceed 2× modeled round-trip per HYPOTHESIS_MAX_SPEC #1). Success: boundary drift
t≥2 after costs → full gauntlet trial. Failure: closes the family honestly; the cost model itself
is reusable execution knowledge. This doubles as the moat's first research read — instrumentation
value regardless of outcome.

**T4 — Trader-split screen (from R4).** Hypothesis: `top − global` L/S divergence predicts
short-horizon returns (KRT mechanism: only the type-split carries information). Method: collect 30d,
then axis_screen with the LIT_b-specified construction; pre-register before first screen. Success:
standard screen bar. Note: publication-lag-free positioning is the crypto structural advantage over
the weekly COT original — this is the desk's cheapest genuinely-new mechanism test.

**T5 — MVRV weekly-horizon escalation (owed by the graveyard's own kill note).** The
`cm_mvrv_btc_daily_level` kill states: "the honest escalation is a PRE-REGISTERED weekly-horizon /
realized-cap-orthogonalized construction on a proper clock slot." No such clock exists
(`data/axis_shadow_state.json` → 3 axes, none MVRV). Either register it or write down why not —
an owed escalation left silent is exactly the §33-style leak this subsystem otherwise avoids.
Blocked-by: CC BY-NC licence ruling (pending per graveyard note) — resolve that first; if licence
fails, the closure reason is recorded and the debt clears.

**Success metric for the subsystem overall (next sweep re-measures):** (1) EV-gate accept rate
enters (0%, 100%) exclusive; (2) Stage-B occupancy ≥10/12; (3) ≥1 non-daily-bar family carries a
counted trial; (4) trials_ledger row count > 0; (5) ingested-axes-without-screen-verdict = 0.

---

## APPENDIX A — six-perspective findings log (raw, evidence-first)

### A1 INTERNAL (measured, not configured)
1. **EV gate accept rate ≈ 0% lifetime; its audit ledger captures 3 of ≥17 verdicts; its single
   QUEUE was never built.** (U1/R1 — the sweep's sharpest internal finding.) The gate that decides
   what the desk researches has no functioning feedback loop: `ev_gate_audit.json` policy says
   "the daily cycle appends one entry per EV verdict" — outcome: 3 entries, 07-22's 11 verdicts absent.
2. **Slot machinery: registry empty, guard hardcoded, occupancy below budget.**
   `data/shadow_sleeves.json` = `[]`; `run_alerts.py:242` `_standing = 6` (a constant); actual
   clocks scattered across axis_shadow_state.json + 5 per-sleeve shadow files. The over-budget
   alert can fire; no under-budget signal exists anywhere — asymmetric enforcement on the side
   that doesn't cost calendar time.
3. **Generation cadence stalled at batch events.** All 15 `gen_done_*` keys in cadence_state.json
   share literally the same timestamp (2026-07-22T23:16:12.083734) — one batch marked every axis
   done simultaneously; no candidate rows in any DB since 07-22; the 07-24 three-mechanism mandate
   (combinatorial/mutation/forced-mechanism) has zero artifacts after ~2 cycles. Watch item, not
   yet a breach — but "generation-first, quota-free engines" currently produces 0 trials/day.

### A2 EXTERNAL (how another world-class team would improve this)
1. **They would know their gate's false-negative rate.** Serious shops score their idea-selection
   funnel end-to-end (every rejected idea shadow-tracked cheaply). This desk has the spec
   (MAX_SURVIVORS #2b) and not the artifact.
2. **They would mine their own exhaust first.** The only data a small desk owns exclusively is its
   own tape (moat) and its own fills. Both are collected here and neither is researched
   (`execution_tape.py` is TCA-only; STRUCTURAL_EDGE_IDEAS #2 own-fill corpus is gated POST-LIVE
   and fills exist — 253 closed trades in research_state.json — but no replay corpus artifact).
3. **Construction diversity:** an external team would not accept that 100% of tested constructions
   are (a) daily z-score timing screens or (b) price-family param grids. Event studies, xsec ranks
   on non-price characteristics, and term-structure constructions are standard tools absent from
   the tested record (visible in it only as EV-vetoed cards).

### A3 FUTURE (2-3y compute/AI/data redesign)
1. **Generation is free in the LLM era; selection and validation are the moat.** The desk's
   Two-Stage law is already the correct 2-3y architecture. The component that will look archaic
   soonest is the *pre-research EV veto* — a hand-tuned scalar formula deciding what an LLM-priced
   research loop may look at. At ~1h/screen, the economically rational gate is "screen everything
   with a mechanism card; rank by EV; veto nothing" — the gate becomes a scheduler.
2. **Event-time research will be table stakes.** Daily bars are a human-era convenience; the moat
   recorder is already event-native. Building the event-time feature layer now (R3) is buying the
   future architecture early on data that cannot be re-collected later.

### A4 CONTRARIAN (test the core assumptions)
1. **"420 hypotheses / 0 survivors ⇒ price space is dead" — the conclusion is likely right but the
   evidence is narrower than the number implies.** 420 = 8 constructions × grids at D1 on 12
   symbols. Weekly/intraday horizons, event-time constructions, and 250+ lake symbols beyond the 12
   were never in the 420. The external evidence (era experiment, HXZ, Fieberg) independently
   supports the conclusion, so no re-litigation of price-only D1 — but the desk should stop citing
   "420" as breadth evidence (effective-N ≈ 8) and should not let the `price_only ×0.30` prior leak
   onto construction classes that were never inside the 420 (e.g. intraday microstructure, which is
   price-adjacent but mechanism-distinct).
2. **"Calendar time cannot be engineered away" (research_state bottleneck #1) is true per-clock and
   false per-desk.** Clock *throughput* = occupancy × time. At ~6-10 of 12 slots, the desk wastes
   17-50% of the exact resource it names as binding. The lever it lists ("keep the flywheel alive")
   protects existing clocks but ignores the vacancy dimension entirely.
3. **"Free-data price-only alpha is mostly dead; the lever is genuinely-new data"** (graveyard
   standing conclusion) — consistent with kimchi, BUT the desk's revealed behavior contradicts its
   own belief: if new axes are the lever, screening ingested-but-unscreened axes is the highest-EV
   act available, and it hasn't happened for 9 axes (R2). Beliefs and behavior disagree; one is wrong.

### A5 GREENFIELD (rebuild-from-scratch score)
1. **A greenfield build would have ONE hypothesis registry, ONE clock table, ONE trials ledger.**
   Current state: 4 SQLite files with identical schemas (3 of them single-batch relics), designed
   tables empty (trials_ledger ×4, campaigns 0 in 3 of 4), clock state in ≥6 JSON files, slot
   count hardcoded. Historical baggage score: moderate — nothing is *wrong*, but every audit
   (including this one) pays a fragmentation tax to reassemble the truth. R6 is the cheap 80%.
2. **The legacy MT5/EA layer (ea/, run_mt5_portfolio.py, cot_zcache 26y×11 instruments, 10-family
   EDGE_FAMILIES incl. seasonality/positioning)** is a parallel factory from the desk's prior life.
   Notably its family taxonomy is RICHER than the crypto factory's (seasonality, positioning,
   flow, structural have no crypto counterpart in the 420's 7 families) — the greenfield insight
   is not "delete the legacy" but "port its taxonomy": funding-settlement time-of-day IS crypto
   seasonality; trader-split IS crypto positioning (R4).

### A6 FRONTIER (recently possible, unexploited)
1. **CFTC COT now covers crypto:** BTC + micro-BTC + ETH futures COT (leveraged-funds vs dealer
   positioning, free, weekly) — the desk has 26 years of COT muscle memory in the legacy stack and
   an open inbox item (#70) for the bench, but no crypto-COT axis anywhere
   (`grep -rin "\bCOT\b" docs/` → legacy + literature only). Mechanism-rich (hedging pressure),
   free, and orthogonal to every current clock. Candidate for the next digger charter.
2. **Deribit's altcoin option listings (SOL/XRP)** directly satisfy the VRP graveyard revisit
   condition (R5a) — the condition was written when breadth was 2; the world moved.
3. **Prediction markets (Polymarket/Kalshi)** are watchlisted (`data_axis_watchlist.md:745` #17,
   #57) and appear in feed_inbox papers, but no collector/screen exists. Event-probability term
   structures around crypto catalysts (ETF decisions, halvings, FOMC) are a new public axis with
   REST APIs. Unscored here — belongs in the watchlist re-rank with a mechanism card first.

## APPENDIX B — negative-space sweep (never asked / never collected / never tested)

- **Questions never asked:** does the desk's own execution create information (own-fill replay,
  STRUCTURAL_EDGE_IDEAS #2 — specced, gated, unbuilt)? What do the 253 closed live trades say about
  where slippage-alpha lives? Is there time-of-day structure in funding/basis (crypto seasonality)?
- **Markets never studied:** options beyond ATM-IV snapshots (surface dynamics, skew term
  structure, expiry pinning — 66 rows total on disk); DEX microstructure (the EV gate killed a
  DEX/CEX *volume-ratio* idea pre-research; no on-chain DEX flow was ever screened); prediction
  markets (A6.3); crypto COT (A6.1).
- **Data collected but never researched:** the moat (3.5GB — zero research reads, U3); COT z-cache
  (26y×11, legacy-only); deribit_surface (no consumer in libs/research); 253 live fills.
- **Resolutions never tested:** anything below D1 except H8 collection (0 intraday trials ever).
- **Communities/languages:** covered — the desk's foreign-frontier machinery (Search Operator
  Library, CN/KR/JP packages) is genuinely strong; the STOP line on new language miners is
  evidence-backed. Nothing found here.
- **Failure modes never simulated at candidate stage:** black_swan_library (19 scenarios) gates
  only PROMOTED alphas; candidates reach Stage-B slots without regime-stress screening (U5).
- **Signals untestable for missing data:** trader-type split (fix is free — R4); pre-2026 L2
  (destroyed at source, correctly graded residual_gap); HL funding history (NK-003, correctly
  parked with reopen conditions). The registry handles these honestly — nothing new to add.

## APPENDIX C — commands run (audit trail, all read-only)

Key proving commands (abbreviated; every finding above cites its own):
- `cat alpha_pipeline.json research_state.json` — 8 alphas / 0 survived / bottleneck rankings
- `sqlite3` counts: research_candidates 420+57+14+49; trials_ledger 0×4; family/subtype GROUP BY
- `cat docs/research/AXIS_PREREGISTRATIONS.md` — 11/11 REJECT (EV below thresh)
- `cat data/ev_gate_audit.json` — 3 entries, policy vs outcome divergence
- `grep -rn "QUEUE (top-EV" data/ docs/ scripts/` — source file only
- `cat data/shadow_sleeves.json` → `[]`; `sed -n '225,250p' scripts/run_alerts.py` → `_standing = 6`
- `cat data/axis_shadow_state.json` — kimchi 4/40d, stablecoin 3/40d, cny 0/40d, m_concurrent 3
- `du -sh data/moat/` → 3.5G; `find data/moat -type f | wc -l` → 9,574; moat consumers grep → no research
- `find data/lake/bronze -type d` → 356 D1 vs 10 H8; `ls data/lake/bronze/` → 15 axes; crypto 268 symbols
- parquet inspections: deribit_surface (66,6) BTC/ETH only; cot_zcache (8405,11) 2000→2026;
  liquidations (33990,6); oi_ls_history.jsonl 600 rows → 2021-06-01
- `grep -rn "topLongShort" scripts/ libs/` → absent; LIT_b:131-140 names it the binding constraint
- `python3 -c` cadence_state gen_done keys — 15 keys, one shared timestamp 2026-07-22T23:16:12
- `git log -- scripts/backfill_oi_ls_oos.py` → 2026-07-23 backfill ran (K5)
