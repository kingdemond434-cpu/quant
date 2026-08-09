# CAPABILITY HUNT PROPOSALS 20260801 slot 4

LENS: CROSS-DOMAIN TRANSFER -- import one idea from control theory, epidemiology, reliability engineering, information theory, or aviation safety that has no equivalent here.

## A -- Claude family

## MISSING CAPABILITY

**An execution EXCITATION BUDGET** — a bounded, pre-registered, randomised perturbation of the desk's *own* order parameters (urgency/wait, maker-vs-taker, probe size), logged as an experiment, whose only purpose is to buy observations at operating points the desk's own gates forbid. Transferred from control theory: **dual control / persistent excitation** (Feldbaum 1960; Åström–Wittenmark). A certainty-equivalence controller that only ever regulates converges to a *self-confirming* model — correct on-policy, arbitrarily wrong off-policy — and when the controller also *gates* on that model, the reachable set becomes **absorbing** (Rothschild 1974's incomplete-learning result: a greedy policy on an uncertain cost curve gets stuck sub-optimally with positive probability, and no amount of further data ever fixes it).

## WHY IT IS INVISIBLE TODAY

Because every file in the loop is individually correct, and the defect only exists in the **cycle**. Trace it:

- `run_recorder.py:94-102` — `_universe() = [_BENCH, _book_symbols(), _recently_traded(), _CORE][:32]`. The L2 recorder records **the symbols the desk already holds and recently traded**, capped at 32 by a Binance weight budget (`:150-156`).
- `run_cost_model.py:12` — walks `data/moat/{spot,fut}/SYM` only. So **only recorded symbols can ever get a cost measurement**. 30 symbols in `data/cost_model.json`.
- `run_cashcarry_executor.py:374-389` — `_rt_bps()`: unmeasured ⇒ `_DEFAULT_RT_BPS = 39.5` (p90, fail-closed, `:337`).
- `:392-401` — `_entry_gate`: `funding*1e4*periods > _rt_bps(sym)`. An unmeasured name needs ~4× the funding of a measured one.
- ⇒ never traded ⇒ never recorded ⇒ never measured. **Forever.**

`traded → recorded → measured → cheap → traded` is a closed cycle with no entry path. The only ways in are two hardcoded tuples (`_BENCH`, `_CORE`). Every fence this desk owns inspects **nodes and edges** — `check_orphan_code` (import graph), `check_money_path_wired` (has a caller), `check_freshness` (producer→consumer age), `run_reality_gap` (adjacent-link ratios). **Nothing looks for cycles**, and nothing asks whether an excluded item has a path back. The fail-closed default is *good* engineering, correctly reasoned in its own comment ("'Unmeasured' is NOT a random subset") — its composition with the recorder's traded-set universe is what welds the gate, and no single-file review can see that.

The second invisibility: the desk is **fanatical about exploration in research** (L1.9, L1.25a "null streaks throttle nothing", L1.31 "exploration is resource-bound, never information-bound") and runs **zero exploration in execution**. That asymmetry has never been written down. L1.11(b) mandates "endogenous execution intelligence… own fills → an Execution Reality Model no competitor holds" — every artifact reads that as *record what happens*. Nothing reads it as **make what happens informative**.

## MECHANISM

1. **Free first step, today:** `run_cashcarry_executor.py:1465,1512` already draws `rng.uniform(0.85, 1.15)` cadence jitter for anti-front-running — genuine exogenous variation in the live path — and **discards the draw**. Persist `(jitter, arm, seed, design_cell)` to the tape. Zero risk, zero capital, immediate identifying variation.
2. `libs/execution/excitation.py` — assigns each order an arm from a pre-registered design over knobs the executor **already has but never varies**: `_MAKER_WAIT=8.0` / `_MAKER_WAIT_OPEN=240.0` (`:960-965`, deterministic per side), `_MAKER=True` (`:52`, a global), and a minimum-notional probe slice. Randomised at bounded ε under a **hard daily dollar cap**. It varies *how*, never *how much* — position size and every rail are untouched.
3. `data/excitation_design.json` — the (symbol-tier × size × urgency) grid with `n_observed` / `n_target` / information-gain priority. **A cell with `n_observed=0` reports `UNIDENTIFIED`, never a prior** (L1.28a: unmeasured counts as zero, applied to the cost surface).
4. `scripts/run_cost_identification.py` → `data/cost_surface.json` — fits cost ~ f(urgency, size, spread, depth) using **randomised-arm observations for the causal coefficients**, observational fills for the intercept. It emits `cost_ratio`, `slippage_ks_p`, `calibration_mae_falling_months` — **the three ramp-gate fields that currently have no producer anywhere in the repo** (`data/ramp_state.json` does not exist).
5. `scripts/check_excitation.py` — statuses `OK` / `UNIDENTIFIED` / `ABSORBING` (an exclusion with no path back) / `NO-EXCITATION` (ε=0 or budget unspent — an idleness defect) / `NO-DATA`. Never OK on absent input.
6. **Re-entry condition on the execution denylist.** `_structurally_bleeding` (`:347-370`) blocks new opens at `n>=5, bps<=-20` with **no expiry and no re-test** — and because it blocks opens, `n` freezes at 5 permanently. L1.16a requires every kill to record its re-entry condition; the alpha graveyard has that discipline, **the execution graveyard has none**. Each block gets *m* minimum-size probes after *d* days.

## WHAT IT WOULD HAVE CAUGHT

`run_cashcarry_executor.py:310-318`, the desk's own audit over 250 closes: the executor opened carries at the Binance *baseline* funding rate — **n=50, net −$176.24, −92.7 bps** — and the comment concludes: *"Those 50 trades ate ~80% of the desk's gross profit."* The cost side of that lesson was purchased with **50 full-size round-trips**. A $100-notional probe arm buys the same observation for ~$0.40. Same shape, same file: NOMUSDT −149 bps and KNCUSDT −211 bps (`:334`) — both now permanently denylisted on n=5, so if either was a thin hour or a venue hiccup rather than a structural property, **the desk can never find out**.

And the live one: `data/live_guard.json` has `ramp.size_fraction = 0.1`, blocked by `a_cost_le_1_25x`, `c_slippage_ks_p_gt_0_05`, `e_mae_falling_2_months` — three cost-calibration statistics **nothing in the repo computes**. The ramp cannot advance by waiting.

## ROI

**Direct:** unpins the ramp from the 0.10 floor rung. If the sleeve has edge, 10%→higher rungs is a multiple on its entire contribution to E[log W], and the blocking evidence is exactly what this produces. **Direct:** breaks the absorbing set — the carry universe is the ~30 names it already trades against a scored candidate pool the executor's own comment puts at 245 (`:327`). **Cascade — this is the big one:** capacity (L1.18a) is *entirely* a statement about d(cost)/d(size). The band, the runway, and every REACHES-LIVE/TIGHT/DOA verdict are computed off a slope that has never been measured against a single fill. **Cascade:** L1.5 says no alpha is valid until it beats T-bills *net of costs* — every net verdict the gauntlet has issued used the book-walk number, today measured at **3.32× low** (modelled 5.74 bps vs realised 19.03 bps). That biases rejections and acceptances in *both* directions. It multiplies every sleeve, every capacity number, and every future validation verdict.

**And it kills a fix that cannot work.** The queued remedy (deep-sweep F24/O8) is to extend `sizes_usdt` to $10k/$50k/$250k and re-walk the recorded books. That is structurally incapable of producing the number: walking a recorded book measures the cost of consuming *displayed* depth in a book **that existed without your order in it** — biased down by refill/fade and other participants' reaction, biased up by hidden liquidity, with neither bias signed a priori. No amount of book-walking resolves a counterfactual.

## COST

~10–14h (excitation module, design artifact, identification script, fence, tape fields, denylist re-entry). Step 1 alone is ~20 minutes. Maintenance low. Capital cost is a **declared, capped, reported budget** — under L1.28a it is a ceiling that must be spent or explained. It competes with R0058/R0084 (TCA coverage 10/523 tape rows) — but those are its **prerequisite, not its rival**, and it makes R0219's 66 bps decomposition tractable. **Deadline: L1.38 freezes money-path *improvements* for the launch window and the first 20 fills. Either the design lands before arm, or it waits — and those first fills are the most informative and the only ones that can never be re-randomised.**

## FALSIFIER

`exhausted_frac = 0.0` at every size on all 30 modelled names — the desk never exhausts top-20 depth at $2,500. If a fit on randomised arms shows the **size**-slope is statistically indistinguishable from the book-walk slope, then at this book's size impact genuinely is ~zero and only the *level* matters, which observational fills already give. That would not kill the proposal but would correctly re-weight it: **prioritise the urgency/wait arms over the size arms at current equity**, since the 3.32× gap must then live in timing, leg latency, adverse selection on the maker leg, and fees. It dies outright if the ramp gate is re-specified to drop `cost_ratio`/`slippage_ks_p`, which removes the largest ROI term.

NOVELTY-CHECK: `grep -rniE "dither|persistent excitation|system identification|closed-loop ident|epsilon.greedy|execution (A/B|experiment)|exploration bonus|randomis(ed|e).*(order|routing)" libs/ scripts/ docs/ data/` → zero hits; the only `random` on the money path is `run_cashcarry_executor.py:1466` anti-front-run jitter. Closest owned rows checked and distinguished: **R0106** (probe capital — unit is a *candidate sleeve*, no randomisation, no design), **R0207** (names the observational-identification gap but proposes *external* natural experiments applied to *alpha*), **R0194** (assumes a √-impact curve from AQR literature — the exact inverse), **R0058/R0084** (passive instrumentation), **V15/N19/F24/O8** (model-vs-realised comparison and bigger book-walks, no intervention).

---

## BRAINSTORM

- **Persist the jitter draw** — `run_cashcarry_executor.py:1512` generates exogenous variation and discards it; one field on the tape starts an identification dataset today — S — ledger (splinter of the above, buildable inside a freeze as instrumentation).
- **The cost model computes 5 size buckets and the gate reads 1** — `_rt_bps` reads only `["pair"]["500"]`; 80% of a computed curve discarded, and the discarded part is the slope capacity depends on — A — ledger.
- **Capture–recapture estimator for undetected defects** — two independent detectors already run (Claude + GPT-9, L1.33); their *overlap* gives a Lincoln–Petersen estimate of the population **neither found**. `unknown_unknown_score` has 40 uses and 0 estimator; this is the estimator, from 1890s ecology — S — a fence.
- **Markout, the tier-1 execution statistic, is absent** — nothing measures P&L at t+1s/10s/60s after a maker fill; a post-only quote that is instantly underwater is being picked off, and slip-vs-arrival cannot see it — S — ledger.
- **Execution denylist has no re-entry condition** — L1.16a is enforced on the alpha graveyard and nowhere near the execution one; `n` freezes at 5 by construction — A — ledger.
- **No fence detects a feedback CYCLE** — every checker walks nodes/edges; add a cycle detector over producer→consumer→gate→producer paths and flag any gate whose output reaches its own input — A — a fence.
- **Common-cause failure / beta-factor across sleeves** — decorrelation is measured on returns; *survival* correlation is driven by shared venue, feed, clock convention and library. 12 forward clocks probably share one klines source; one API change kills all 12 "uncorrelated" sleeves — S — a fence.
- **Funding is used as its own forecast** — `_entry_gate` uses the *current* 8h rate as a prediction of the *next* period's, an untested martingale assumption on the sleeve's entire revenue line; score it like L1.29 scores probabilities — A — ledger.
- **`est_funding` is modelled, never reconciled against venue funding transfers** — the revenue half of a carry desk has no realised-vs-predicted check while the cost half now has three — A — ledger.
- **Shadow price of a recorder slot** — the universe is capped at 32 by a 2400 weight/min budget; nobody has computed the marginal bps of forgone carry from slot 33, so a bandwidth constant silently sets the tradeable universe — A — ledger.
- **ASRS near-miss register** — aviation's largest safety win is counting events that caused no harm; they are 100–1000× more frequent than incidents and give power to estimate the accident rate *before* one happens. The desk logs defects and losses, never near misses — A — a fence.
- **FOQA exceedance monitoring** — score *every* order against a stable-execution envelope (spread band, depth band, leg latency) regardless of whether it made money; outcome-independent process monitoring decouples execution quality from P&L noise — A — a fence.
- **Aviation "stabilised approach" abort gate** — a fixed pre-trade checkpoint where an unstabilised order is *abandoned* rather than pushed through; distinct from a risk limit, which caps size but never aborts — B — ledger.
- **Threat & Error Management: enumerate latent threats at session start** — dirty tree, sibling session, stale artifact, frozen clock — before they become errors, rather than detecting the error afterwards — B — a fence.
- **Screening interval vs sojourn time** — cancer-screening arithmetic: re-validation cadence must be shorter than each sleeve's decay half-life or dead edges are held; nobody computes a per-sleeve sojourn time — A — ledger.
- **Sentinel cohort** — 5 fixed canary symbols always traded at minimum size regardless of gates, as a venue-wide microstructure tripwire; complements excitation and is immune to the absorbing set — A — ledger.
- **Defect R₀** — measure how many copies each defect class spawns (4 duplicate exchangeInfo parsers, 11 fences exiting 0 on absent input); if R>1 the class grows faster than adjacency sweeps clear it — B — a fence.
- **Anti-windup on evidence clocks** — `window_ge_8_weeks` counts calendar while the actuator is saturated (book frozen); a clock that accrues while the plant cannot respond is textbook integral windup and already froze Gate 0 at 26.42/28 days — A — a fence.
- **Observability horizon per sleeve** — state in advance the n at which "decaying" becomes distinguishable from "unlucky"; below it, a demotion decision is unobservable and should be declared so rather than made — A — ledger.
- **Data-processing-inequality audit of the feature pipeline** — measure MI(feature; target) at each stage; the de-contamination gate is a low-pass filter that provably destroys information and nobody has quantified how much — A — ledger.
- **MDL/compression novelty gate** — a hypothesis that fails to compress the graveyard is redundant; strictly better than the TF-IDF gate measured at 0% recall — A — ledger.
- **Fisher information per dollar risked** — D-optimal ranking of which probe trade to run next; the allocation rule the excitation budget needs, and reusable for ranking forward-clock candidates — B — ledger.
- **Reliability bathtub / infant mortality burn-in** — new *code* fails at a higher rate early, independent of alpha uncertainty; size a newly-deployed sleeve down for its first N fills for implementation risk, which the ramp gate does not model — B — ledger.
- **PFD and proof-test interval for dormant protective functions** — IEC 61508 arithmetic on `flatten_to_neutral`, `place_stop_market`, kill switch: drills exist, a *computed* failure-on-demand probability and a derived test interval do not — A — a fence.
- **Aliasing audit** — state each signal's sampling rate against its process bandwidth; a daily-sampled controller on an intraday process aliases, and "no slow price alpha at daily resolution" may be a Nyquist statement misread as a market fact — A — axis watchlist.
- **Venue/counterparty single point of existence** — one venue is both the execution path and the custody path; no second-venue capability exists even in degraded form — S — ledger.
- **Order-flow fingerprintability** — cadence jitter exists but size is deterministic given config and the symbol set is small and stable; measure whether displayed depth on our side thins *before* our order arrives — B — ledger.
- **Rejection-reason histogram per gate** — GATE-OPTIMALITY requires accept/reject rates, but a gate rejecting 100% for *shifting reasons* is healthy while one rejecting 100% for the *same* reason is welded; the current check cannot tell them apart — A — a fence.
- **`_DEFAULT_RT_BPS = 39.5` as a p90 is a point estimate of a tail** — it carries no uncertainty, so a name one bp over the bar is refused with the same confidence as one 30 bps over — B — ledger.
- **Excursion: what is the desk's own half-life?** — L1.30 counts edge births and deaths but nothing estimates the *desk's* survival curve as a function of replacement rate; the countdown L1.30 warns about has no clock face — A — ledger.
- **Time-reversal test on every artifact** — for each decision-path file, ask what a reader would conclude if it froze today; L1.44 contracts the *age*, nothing contracts the *consequence* — B — a fence.

I could keep going — the next line I was about to write is **queueing-theoretic admission control on the findings queue** (ρ = 35.1/10.9 = 3.2 > 1 means the backlog diverges regardless of effort, so the lever is service capacity or admission, never exhortation), which I stopped short of because L1.28b already states that arithmetic explicitly. Resuming from there next run: the same ρ analysis applied to the **forward-slot queue** (12 slots, 90-day clocks ⇒ a hard ceiling of ~48 promotion decisions/year — a bandwidth limit at the *slot* stage that no amount of generation can raise).


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 400: Bad Request. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
