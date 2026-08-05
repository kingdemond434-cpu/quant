# CAPABILITY HUNT PROPOSALS 20260805 slot 0

LENS: REGIME-CONDITIONED EDGE -- an edge that exists only in a nameable, DETECTABLE regime (high-funding, high-vol, post-liquidation, low-liquidity) we could switch on and off. What regime do we not yet detect, and what edge would it gate?

## A -- Claude family

The regime map came back. It **confirms the core finding and corrects two things I said** — reporting both.

## CORRECTIONS TO MY OWN PROPOSAL

**I was wrong on brainstorm #9.** I cited `regime_mult` clamp `[0.2,1.0]` as a live de-risk-only defect. It is in `run_crypto_testnet.py`, which is **retired** — heartbeat last written Jun 28 vs `data/cashcarry_exec_heartbeat` written today. Withdraw it.

The live fact is worse and simpler: **the producer→consumer link is severed.** `run_cashcarry_executor.py:82-83` *spawns* `classify_regime.py` and `run_regime_engine.py` as data-flywheel subprocesses and **never reads `data/crypto_regime.json` back.** The only live book on this desk writes the regime label and does not consume it. Nothing with capital conditions on regime at all. That replaces #9 at **S**.

**I under-claimed the core.** I said the desk *fails to test* conditionality. It is stronger than that: `libs/autodiscovery/regime.py:36` `regime_robust()` **requires net-positive in ≥2 of 3 vol terciles before REGISTRY**, and it is a **live fence with 35 script callers**, rejection string at `orchestrator.py:245`: `"failed: regime_robustness (edge confined to one volatility regime)"`. So `FailureCause.REGIME_DEPENDENT` is not a passive taxonomy label — **it is an actively enforced kill rule.** A single-regime edge is not merely invisible to the screen; it is affirmatively rejected by a running gate. The belief I identified as never-written-down is in fact compiled and executing.

That makes the proposal more important and **more expensive**: it now requires retiring or reframing a live fence, which under RETIREMENT NEEDS EVIDENCE means a statistically significant demonstration, not an argument. Revised cost: **not 4–6h — call it 4–6h for the estimator plus a genuine evidence campaign for the fence.** I should not have priced it without that.

## THREE PLACES PRESCRIBE THE TEST THAT DOES NOT EXIST

This is now a documented pattern, not one bug:
- `scripts/research_autopsy.py:129` — `"environment-specific -- test conditional on regime or not at all"`
- `scripts/graveyard_resurrect.py:34` — `regime_artifact` → tier 3, `"RESURRECT-ABLE: died in one regime. Re-test conditioned on regime."`
- `libs/discovery/regime_diversification.py` — takes a caller-supplied `regime_performance` mapping; **nothing computes that mapping in production.**

Three organs route work to a conditional re-test. The function has never existed. `graveyard_resurrect.py:34` is a partial-novelty hit against my proposal and I disclose it — but it prescribes the test rather than implementing it, so it is the *third* instance of the class, not a duplicate.

## THE PRIOR AGAINST ME — reported, not buried

`research_agenda.json` shows **three regime-conditioning ideas already EV-rejected**: vol-regime-conditioned trend overlay (`ev 0.0002`, `price_only`), FRED regime overlay (`0.0039`), equity-vol regime flag (`0.0027`, `crowded_known`), with the note that overlay-only ideas are structurally penalised. And `run_trend_regime_shadow.py`'s own docstring scores regime-filtered trend at **`p_survive ~7%`** and calls it *"a classic overfit trap."*

That is real adverse evidence. My defence is narrow and I'll state it as such: those three priced regime overlays as **new alpha streams**; mine changes a **test statistic** and adds no stream. But the 7% prior stands and should discipline the build.

## THE FALSIFIER IS NOW CHEAPER AND ALREADY RUNNING

`data/trend_regime_shadow_state.json` shows a pre-registered on/off regime gate accruing since **2026-07-08** — *"FLAT unless lagged |BTC 30d| ≥ 10%"* — with ~28 days of forward evidence in `web/trend_regime_shadow.json` (24KB, carries `forward_days`). **This desk has been running the exact experiment that decides my proposal, for four weeks, and nobody has read it for this purpose.** Read that first. If a regime-gated sleeve is not beating its ungated incumbent there, the 7% prior is being confirmed and this should not be built.

Two further build-cost corrections: `libs/research/label_factory.py:227-256` `regime_transition(win=20, ratio=1.8)` with `REGIME_CONFIRM_BARS` already supplies the partition primitive (cheaper) — but **five mutually incompatible regime taxonomies** exist (9-regime, 5-regime, 7-member `ResearchRegime`, 2-axis `crypto_regime`, HMM bull/bear×3vol) with no mapping, so "declare a partition" is currently ambiguous and a canonical vocabulary is a real prerequisite (dearer).

---

# BRAINSTORM (continued — resuming at the cross-domain transfers I flagged)

33. **Control theory — dwell-time constraint on regime switching**: a gate that flips on every label change chatters and pays the round-trip cost twice; minimum-dwell is the standard fix and `REGIME_CONFIRM_BARS` already implements half of it, unwired to any gate. **S** → executor.
34. **Epidemiology — case-definition drift**: `rv_med` is a trailing 365d median, so the same market prints different labels across time; every conditional backtest is contaminated by a moving definition, exactly as a shifting case definition breaks an incidence series. **S** → fence over the backfill.
35. **Aviation — mode confusion**: with the clamp, "regime off" and "sized to zero" are indistinguishable from any dashboard; the desk cannot tell a gate that fired from a book that has no signal. Needs a mode annunciator. **A** → `live_book`.
36. **Reliability engineering — common-cause failure**: five regime taxonomies means five chances to disagree silently; a single canonical vocabulary with explicit mappings is the standard remedy and is a prerequisite for #1 anyway. **S** → ledger.
37. **Information theory — the gate that carries zero bits**: `governance.structural_break_pass: bool = False` is required-True with **nothing in the repo able to set it** — a permanently-firing gate, precisely the GATE-OPTIMALITY defect the constitution orders monitored. **S** → fence audit (adjacent to the deep_sweep W-18 note, but the *unsatisfiable* framing is the actionable part).
38. **`libs/risk/crisis.py` `crisis_controller` is built, fail-closed, and has no live caller** — a real crisis detector returning `exposure_scalar` + `suspend_negative_tail`, wired to nothing on the cash-carry book. This is the Alameda/LTCM lens: the detector exists, the wire does not. **S** → executor.
39. **Zero changepoint detectors of any kind** — no CUSUM, BOCPD, Chow, Bai-Perron, `ruptures`; and `hypothesis_engine.py:23` posits *"trend signals improve through regime transitions"*, a hypothesis with no detector and no test. **S** → axis watchlist.
40. **Jan-2024 spot-ETF break is known and unencoded** — `GAP_REGISTER.md:346` records a DiD showing crypto carry cut **36%** and demands it be recorded as a boundary on every carry backtest; not done, so every carry backtest still pools across it. **S** → this is the single highest-value regime boundary the desk already owns.
41. **`regime_confidence: 1.0` while `hmm_gmm_agree: false`** is live right now and no alert watches it; two estimators disagreeing at stated full confidence is a broken instrument reporting certainty. **A** → fence.
42. **`BayesianRegimeFilter` is docstring'd "the production hook" with zero callers** — an online recursive filter built for the executor, never connected. **B** → wire or retire.
43. **The HMM's trend axis is degenerate** — `web/regime_engine.json` labels all three states **bull**/{low,mid,high}\_vol on 1079/1052/393 days. So the desk has one usable regime axis (vol), not three, and f≈1 on trend — which directly caps the 1/√f gain and should be measured before building. **S** → the falsifier.
44. **Transition matrix diagonal ≈0.973** implies ~37-day mean regime duration; with 12 forward clocks and 0 deaths in 90d, most clocks have accrued inside ~2 regime episodes. Promotion evidence is far less independent than the slot count implies. **S** → feeds `replacement_rate.json`.
45. **`screen_collateral_allocation.py:99-112` `funding_regimes()` already reports "the winner CHANGES with the funding regime"** — a conditional result sitting in a research script, never routed to a clock or a card. **A** → §33 disposition owed.
46. **`web/crypto_portfolio.json→regimes` holds the desk's richest conditional evidence** (`funding_carry` +1.16 bull / −0.43 bear; `ts_trend` +1.82 funding_rich / −0.30 funding_poor) produced by a path that **bypasses the angle-20 gate, the power deflator and the DSR trial counter entirely**. Either it is evidence and must be railed, or it is decoration and must be labelled. **S** → this is the highest-signal unrailed artifact found.
47. **`run_conviction_trader.py:1010` tags every trade with entry `vol_regime`** — a live, growing, regime-labelled *execution* panel nobody has analysed; conditional slippage/fill-quality by regime is measurable today with zero new collection. **S** → the W-axis, and cheaper than any alpha work.
48. **`check_promotion_gate.py:191-197` `two_regimes` requires the record to span ≥2 regimes** — with a degenerate trend axis and 37-day episodes, check whether this is satisfiable in practice or is a second permanently-firing gate. **A** → gate-optimality audit.
49. **`libs/research/fusion_search.py:115-123` `_conditioned`** zeroes a signal unless peers agree in sign — a conditioning primitive already in the search space, never evaluated as a regime gate. **B** → reuse.
50. **`libs/hypmax/moat_features.py:207-226` `spread_regime_shift`** is a liquidity-regime detector on the owned tape, registered in `MANUFACTURED` — the post-liquidation/thin-book regime from #1 is closer to buildable than I priced it. **A** → axis watchlist.
51. **`oi_divergence` `EXHAUSTION` states are a live derivative-shadow sleeve** — forced-liquidation exhaustion is already a detected state with a slot; it is a regime label wearing a signal's costume and could gate mean-reversion rather than trade directionally. **A** → axis watchlist.
52. **Regime-conditional capacity is anti-correlated with regime-conditional signal** — the stressed regimes where conditional edges are strongest are exactly where depth collapses; any gate built without a regime-conditional capacity term will size into an empty book. **S** → `capacity_policy`, and this is a prerequisite, not a follow-on.
53. **`libs/validation/revalidation.py` is marked test-only in a deep_sweep doc** — *"the structural-break / drift / decay triggers that are supposed to force revalidation never fire."* A live edge decaying through a regime change triggers no revalidation. This is the "capability whose absence would let a live edge die uncaught" case exactly. **S** → ledger.
54. **`libs/discovery/regime_diversification.py` scores 9 regimes the desk cannot detect** — breadth × Gini over a vocabulary with no production producer, so the score is computed over an empty mapping and reads as a number. **B** → wire or retire.
55. **Audit the `regime_robust()` ≥2-of-3 fence for what it has actually killed** — 35 callers, one rejection string; count the rejections and read them. If it has killed N candidates on single-regime confinement, that N *is* the measured cost of the belief, and it converts my proposal from an argument into an arithmetic. **S** → run this before anything else; it is a grep and a count.

*(Still generating; context is the constraint now, not the seam. Next lines I was about to write: the adversary lens on regime — a competitor who knows our gate thresholds can trade the boundary against us, since `_GATE_MIN_ABS=0.10` and `HIGH_FUNDING_8H=0.0001` are published constants in a public-shaped repo; then the crowding-decay asymmetry of conditional vs unconditional edges; then whether `hypothesis_novelty` should treat a conditional restatement as novel. Resume there.)*


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 400: Bad Request. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
