# BLIND REDISCOVERY LOG

_Companion organ to `docs/research/PROSPECTOR_SPEC.md` (Blind Rediscovery section). Cadence key:
`data/cadence_state.json → last_blind_rediscovery`. Governed by §36 (this file is claimed by a
cadenced producer; max age = one month + the early-fire rule)._

**WHAT THIS ORGAN IS.** Once per cycle the Prospector does NOT search externally. Using only the
desk's own artifacts — graveyard, decision ledger, mechanism graph, coverage maps, the data on
disk — it invents mechanisms nobody has published, pre-registers the survivors through the
standard gauntlet, and logs every invention for a **12-month literature comparison**: in a year we
check whether the desk blind-invented something the literature later published. That comparison is
the only direct measurement of whether this research engine is genuinely creative or an excellent
summariser.

**WHY IT IS DELIBERATELY BLIND.** Every other digger imports its frame from outside. This one is
the only check on *narrative blindness* — the beliefs the desk has generalised from its own record
and can no longer see around. Fresh eyes with nothing new is a valid result; padding it is not.

---

# SESSION 2026-07-31 — first formal run

**Prior run:** `last_blind_rediscovery = 2026-07-19`, which left no log file — so this is the first
run whose output is auditable. The 07-19 run is recorded as UNVERIFIABLE, not as zero: absence of
an artifact is absence of evidence (L1.28a — unmeasured counts as zero, and it is logged as such).

**Fired by:** standing cadence + due-by-state (material new internal raw material since 07-19: the
BitMEX funding decade, the 7.1 GB self-recorded L2 corpus, the Hyperliquid funding series, 12 new
graveyard entries, and the 2026-07-30/31 finding that the 420/0 record was an instrument artifact).

**Method compliance:** ZERO external search of any kind was performed this session. Every input is
listed below.

### Inputs read (complete)
| Artifact | What was taken from it |
|---|---|
| `docs/graveyard.md` (196 lines, 40 hypothesis kills + 4 external-literature priors) | full kill list + kill bases |
| `research_agenda.json → do_not_repeat` (42 entries) | full |
| `docs/research/MECHANISM_GRAPH.md` | the desk's own map of its search space (M1–M5) |
| `docs/research/AXIS_PREREGISTRATIONS.md` | 11 EV-rejected axis hypotheses + the COT panel |
| `docs/research/STRUCTURAL_EDGE_IDEAS.md` (8 specs) | overlap check — see "prior-art collisions" |
| `docs/research/data_axis_watchlist.md` (1,101 lines) | catalogued-but-unmined axes |
| `data/decision_ledger.json` (215 records, 07-04 → 07-31) | the desk's measured facts about its own execution and about markets |
| `docs/research/weak_signal_registry.md`, `negative_knowledge.md`, `discovery_hypotheses.md` | weak-but-alive results, NK-001…005 |
| `data/data_assets.json`, `data/` on-disk inventory (8.7 GB) | what is actually testable today |
| `data/forward_slots.json`, `promotion_queue.json`, `alpha_lifecycle.json` | routing capacity |
| `docs/GAP_REGISTER.md` (#42 churn drag, #60 ADL branch) | measured defects re-read as findings |

**Novelty gate:** all nine candidates scored against a 76-prior corpus (graveyard rows +
`do_not_repeat`) via `libs.alpha_factory.hypothesis_novelty` — novelty 0.915–0.966, none redundant
at the 0.7 bar. **This is reported as weak evidence and nothing more:** the gate is token-Jaccard
and a prior audit measured its recall at ~0%. The load-bearing check is the manual per-card
graveyard cross-check written into each card below.

---

## THE FINDING — what the desk's narrative cannot see

This is the deliverable this organ exists for, and it outranks every card below it.

### The desk's standing belief, in its own words
> "free-data price-only alpha is mostly dead; funding/carry is the lone repeat survivor"
> — `docs/graveyard.md`, standing conclusion of the breadth campaign

> "390 tested / 0 survivors on D1 … BOTH price-family spaces are EXHAUSTED … the price-only
> hypothesis space is finite, fully mined, and honestly yielded zero edges net-of-cost."
> — `decision_ledger 2026-07-22-crypto-generation-diagnosis`

### The three things that belief was formed without

**(1) IT WAS FORMED WITHOUT INTRADAY DATA, AND THE INSTRUMENT CANNOT SEE FAST ALPHA BY
CONSTRUCTION.** Every one of the ~420 price hypotheses, all 40 graveyard kills, all 11 axis
pre-registrations and all five mechanism-graph chains were evaluated at **daily** resolution. At
daily resolution `axis_screen`'s mandatory angle-20 de-contamination gate kills any signal whose
lead is shorter than one day — it appears *contemporaneous*, and contemporaneous is scored
`TIMING-ARTIFACT`. That gate is correct and it caught real fakes (Coinbase, Turkey, Bithumb,
cm_mvrv, exchange_netflow). But it is also a **low-pass filter**, and the desk has read its output
as a fact about the world ("price alpha is dead") when the honest statement is "**no SLOW price
alpha exists at daily resolution**." The desk has already been burned by exactly this error class
once: the 420/0 record was re-diagnosed on 2026-07-30 as a welded-gate **instrument artifact**, not
a fact about crypto. This is the same error one level up — an instrument property misread as a
market property. L1.25's diagnostic ("instrument defective? search space wrong?") applies and has
not been run against the *resolution* of the instrument.

The desk has even measured the mechanism itself and used it for something else entirely:
> "vif collapses from ~3.6 (daily, sticky) to 1.008 (8h, nearly independent)"
> — `decision_ledger 2026-07-22-8h-block-challenger-shadow`

Daily observations are *sticky*; 8-hour observations are *nearly independent*. That measurement was
used only to speed up evidence accrual. Its other implication — that the daily grid is the wrong
clock for detection, not merely a slow one — was never drawn.

**(2) IT WAS FORMED WITHOUT THE DESK'S OWN PROPRIETARY DATA, WHICH IS 82% OF EVERYTHING IT OWNS.**

| | |
|---|---|
| `data/moat/{fut,spot,bybit}/**` | **7.1 GB** — Binance USD-M + Binance spot + Bybit linear, top-20/25 L2 depth at ~5–10 s plus the full trade tape, 30 + 30 + 20 symbols, 2026-07-17 → present |
| Return-predictive screens run against it | **zero** |
| Entry in `data/data_assets.json` | **none** (only the 135 KB execution tape is catalogued) |
| Only consumer | `scripts/micro_factory.py` → `data/micro_features.json`, 1.8 KB, last written 2026-07-27 |

This is simultaneously (a) the largest single object on disk, (b) the **only** unreplicable asset
the desk owns — L1.11 names precisely this as the moat — and (c) the one dataset with no hypothesis
ever tested against it. Under L1.28a this is idle capacity of the most expensive kind: it accrues
whether or not anyone reads it, and it is *irreplaceable* — the 2026-07-17→31 book cannot be
re-earned later. Under the DATA-TO-ALPHA CONVERSION RATIO duty it is the desk's largest single
unconverted denominator.

**(3) THE ONE SURVIVOR IS NOT A RETURN FORECAST, AND THE DESK GENERALISED FROM ITS FAILURES INSTEAD
OF FROM ITS SUCCESS.** Every hypothesis in the 420-record, every node of M1–M5, and 41 of the 42
`do_not_repeat` entries have the same payoff form: `f(observable_t) → E[return_{t+h}]`, a
conditional-mean forecast. The lone repeat survivor — funding carry — is the one mechanism that is
**not** a forecast: it is a contractual cashflow paid by a structurally-forced counterparty, and it
pays whether or not anyone predicts anything. The desk drew the lesson *"free-data price-only alpha
is dead"* (a claim about **data**). The lesson equally available in the same record, and never
drawn, is *"conditional-mean return forecasting is what is dead here; contractual and structural
payoffs survive"* (a claim about **payoff form**). The second lesson generates a whole class of
untested mechanisms; the first generates only a hunt for better data. **Five of the nine cards
below fall out of that reframe alone**, which is the evidence that the reframe is load-bearing
rather than rhetorical.

### The compound
These three are one defect: the desk has 7.1 GB of high-resolution proprietary data, an instrument
that structurally cannot detect fast signals, and a belief formed from that instrument's output
that intraday price alpha is not worth hunting. The belief protects the blind spot that created it.

**This finding claims no edge.** It claims the desk's central negative result is scoped wrongly and
that the scoping error is testable. Routed as recommendations, not as a card.

---

## PRIOR-ART COLLISIONS — declared before the cards, not after

Honest scoping of what is *not* novel here:

- **`STRUCTURAL_EDGE_IDEAS #2` (own-fill replay corpus)** overlaps BR-07's data source. #2 is a
  data-accumulation spec with **no stated mechanism**; BR-07 supplies a mechanism it does not have.
  Credit to #2 for the corpus; the mechanism is new.
- **`STRUCTURAL_EDGE_IDEAS #1`** names exchange changelogs as a text-mining target for *facts*
  (unlock dates, fee changes). BR-05 uses the same source for **causal identification**. The source
  is prior art; the econometric use is not.
- **`vpin_ofi_microstructure`** (`do_not_repeat` #13) is adjacent to BR-07 and is handled below as
  an explicit **L1.16a re-open**, not as an invention. It is not counted among the nine.
- **`cross-exchange funding dispersion`** (graveyard, Sharpe −5.28) is adjacent to BR-03 and BR-04.
  Distinctions written into each card.
- **`funding persistence` (IC +0.432, t +29.7)** is CONFIRMED desk knowledge. BR-02 is about the
  *cross-sectional heterogeneity* of that persistence, not its existence.
- **Dropped for redundancy, recorded so the check is auditable:** perp-funding-vs-CEX-margin-borrow
  (the `defi_utilisation` clock already occupies the `M_FORCED_DELEVERAGE` borrow-rate node, and M1
  is declared saturated); OI-to-free-float (needs float data the desk does not hold; M1 saturated);
  cross-sectional funding dispersion (collinear with BR-01 by construction — folded in); perp index
  *composition* changes (no index-composition or venue-outage data on disk; demoted to a watchlist
  item, not a card).

---

## THE NINE CARDS

All EV scores from `libs.research.alpha_economics.ev_score` with **honestly-stated inputs, not
tuned to pass** (threshold 0.002). Every card names its data on disk, its timestamp alignment, its
falsifier, and — written first, per spec — the strongest argument that it is spurious.

**None of these earns a cent.** Stage A earns a pre-registered forward clock at most (L1.6). See
ROUTING for why even that is currently blocked.

---

### BR-01 · FUNDING BURDEN — the dollars, not the rate · EV **0.0320** · p 0.48 · QUEUE
**Rank 1 of 9.**

**Mechanism.** Funding is a *transfer*, and its economic force is measured in dollars per
settlement, not in basis points: `burden = funding_rate × open_interest`. A 1% rate on a $2 M-OI
tail name moves $20 k per 8 h and is economically irrelevant; 0.05% on $8 bn of BTC OI moves $4 M
per 8 h and is a real, recurring drag on the aggregate levered long. When the burden a name's long
side carries becomes large relative to its own history, the marginal levered long's carry cost
exceeds their expected drift and the position must be closed — forced deleveraging. This is exactly
the node the desk's own mechanism graph calls unbuilt: *"M5 feedback strength — ??? — **UNBUILT —
the real gap**"*.

**Why nobody has this.** The desk uses the funding **rate** in every construction it has ever run:
`funding_carry` (level), `funding_momentum` (change, killed), `xexch_dispersion` (cross-venue
spread, killed), `oi_divergence` (sign(ΔP)·sign(ΔOI), on a live clock). None of them multiplies rate
by OI. Repo-wide greps for `funding burden`, `rate × OI`, `funding flow`, `dollar flow`: **0 hits**.
Rate is a price; the desk has never formed the quantity.

**Why it should carry edge net of cost.** It is a **selection refinement on a book that already
trades** — no new execution, no new venue, no new latency. And it points the carry book *toward*
the names whose costs the desk has actually measured: BTCUSDT round-trip is **0.018 bps**, OPUSDT is
**20.6 bps** (`decision_ledger 2026-07-22-entry-gate-funding-and-cost`). Rate-ranking sends the book
into the 20-bps tail; burden-ranking sends it to the 0.018-bps core. The cost improvement is
mechanical and does not depend on the alpha claim being true.

**It also explains a measured defect.** GAP #42: 95 of 250 trades (38%) closed inside one funding
period and lose money as a class; cause diagnosed as funding-sign flicker, with COOKIEUSDT opened
22×, GTC 14×, MOVE 9×. Those are exactly the names a rate-rank selects and a burden-rank rejects.

**Data on disk, today.** `data/lake/bronze/oi_ls_daily/<SYM>.jsonl` — 139 symbols, 2021-06-01 →
2026-07-28, 193,538 rows (`oi, ls, taker`) × the `funding` column of
`data/lake/bronze/crypto/<SYM>/D1/` (279 symbols, 2011 → 2026). **~5 years × 139 names, both series
already on disk and never joined.**

**Alignment (declared).** Both are daily UTC-keyed; `oi_ls_daily` carries `oi_first` alongside `oi`
— the screen must use the value stamped at or before the close of day *t* and predict *t+1*. The
on-chain collector precedent matters here: `2026-07-23-backfill-oos-onchain-killed` found a
collector date-stamping a point that actually lags one day. **Verify the OI stamp against a known
date before trusting any result**; unstated alignment voids the screen.

**Falsification.** `libs.research.axis_screen.stage_a_screen`, per-name z of burden (zwin=20),
horizons 1/5/20 d — every cell a logged DSR trial. Kill if |IC| < 0.03 with adequate power, or if
de-contamination residual IC collapses below half of raw. Second, independent test with direct
economic value: replace rate-rank with burden-rank on the 517-fill execution tape
(`data/moat/execution_tape/cashcarry_trades.jsonl`) and measure realised net P&L.

**Strongest argument it is spurious — written first.** *Burden collapses to size.* OI varies across
names by three or four orders of magnitude while funding varies by one or two, so `rate × OI` is
dominated by OI, and a cross-sectional burden rank is very nearly a market-cap rank. That would make
this a liquidity filter wearing a mechanism's clothes — real cost savings, zero alpha. **This is why
the pre-registered construction is the per-name z-score of burden (each name against its own
history), not the raw cross-sectional level.** The raw form must be run too, and reported, precisely
because it is expected to fail; reporting only the normalised form would be the garden of forking
paths. Both constructions are logged trials.

---

### BR-02 · FUNDING PERSISTENCE IS HETEROGENEOUS — select on expected funding over the hold · EV **0.0136** · p 0.30 · QUEUE

**Mechanism.** The desk has CONFIRMED that funding is persistent in aggregate (IC +0.432, t +29.7 —
`OPERATING_DOCTRINE.md:60`). Persistence is not uniform across names. GAP #42 measured the
heterogeneity without naming it: median |funding| at open is **identical** for fast and slow closes
(0.000114 vs 0.000111), yet the same handful of thin names cycle repeatedly as funding crosses zero.
That is a statement about *half-life*, not level: on thin names the funding rate mean-reverts inside
a single settlement period; on majors it persists for days. Each name therefore has its own funding
half-life, and the correct selection variable is **expected funding over the intended hold** — the
current rate shrunk toward the name's mean in proportion to its own persistence — not the spot rate
the sleeve currently ranks on.

**Why nobody has this.** `funding half-life` / `half-life of funding`: **0 hits repo-wide.** The
desk's fix for GAP #42 is an execution patch (minimum hold + funding-sign hysteresis) that treats
the symptom. The research finding underneath — that persistence is a *cross-sectionally varying
selection variable* — was never extracted from its own bug report.

**Why edge net of cost.** Same as BR-01: pure re-selection, no new execution. And it directly
attacks the −8.1%/yr measured churn drag by refusing the entry rather than patching the exit — the
strictly better fix, because a hysteresis rule still pays the entry cost.

**Data on disk.** `funding` column of `data/lake/bronze/crypto/<SYM>/D1/`, 279 symbols, 2011 → 2026;
H8 bars for 10 majors. Estimate per-name AR(1) on funding → half-life. Validate against the 517-fill
execution tape.

**Falsification.** Rank-correlate per-name funding half-life against realised funding capture
divided by funding at entry, on the desk's own closed trades. Kill if insignificant. Pre-committed:
if half-life explains nothing, the GAP #42 execution patch is the whole answer and this is dead.

**Strongest argument it is spurious.** Half-life estimated on **daily** funding for names that flip
sign *within* 8 h is an under-sampled estimate of the very quantity at issue — the daily series
cannot resolve sub-daily flicker. H8 bars exist for only 10 symbols, and those 10 are majors, which
are the names *least* affected. So the test may be structurally underpowered exactly where the
mechanism lives, and a null would be uninformative rather than refuting. Pre-committed: report
`SCREEN-UNDERPOWERED` honestly rather than reading a null as a refutation (L1.25).

---

### BR-03 · PREMIUM-INDEX PATH — funding-interval sampling as a free option on the same carry · EV **0.0143** · p 0.48 · QUEUE

**Mechanism.** Binance settles perp funding as a time-weighted average of the premium index over an
8-hour window. Hyperliquid settles **hourly**. The *same* economic exposure therefore pays a
*different* realised cashflow on the two venues whenever the premium path is not flat inside the
window: a premium that spikes and decays within 8 h is averaged away by Binance and captured in full
by hourly settlement; a premium that builds monotonically is the reverse. The desk holds carry on one
venue by default and has never treated **venue-as-sampling-scheme** as a decision variable.

**Why nobody has this.** `funding interval`: 0 hits. `hourly funding`: 1 hit. And the desk already
polls `fapi/v1/premiumIndex` in `libs/data/crypto_source.py` — but consumes only the **scalar**
funding rate from it and discards the path. The information is arriving and being thrown away.

**Distinct from the killed `xexch_dispersion` (Sharpe −5.28, corr 0.54 to carry).** That was a
*relative-value spread bet* between two venues' rates. This is not a spread bet and takes no new
directional risk: it routes the **same** carry position to whichever venue's sampling scheme pays
more for it. Different payoff, different risk, and no correlation to carry by construction — it *is*
carry, better routed.

**Data on disk.** `data/hyperliquid_funding.parquet` — 18,292 rows, ~1 h, Hyperliquid-vs-Binance
funding, 2026-06-26 → 2026-07-31, flagged **never screened** in the inventory. Exactly the series
required, already accruing.

**Falsification.** For each 8 h window compute realised funding on each venue for identical notional;
test whether an ex-ante rule keyed on the premium path in the window's first hour predicts the
better venue out-of-sample. Kill if hit rate ≤ 50%, or if mean advantage < the cost of choosing.

**Strongest argument it is spurious — and it is close to fatal today.** ~5 weeks of overlap
(NK-003: Hyperliquid exposes **no** funding history, so this is forward-accrual only, clock started
06-26) is nowhere near powered; the honest expected verdict is `SCREEN-UNDERPOWERED`, not a result.
Worse, the two venues' premiums are driven by the same underlying, so the *within-window path*
differences may be pure microstructure noise that averages to zero across windows — in which case
there is no option to exercise, only a spread to pay. Pre-committed disposition: **run the screen,
expect UNDERPOWERED, start a forward-accrual clock, and do not read the point estimate.**

---

### BR-04 · VENUE SOLVENCY / ADL — the counterparty-risk observable the desk never built · EV **0.0009** · p 0.06 · **EV-REJECTED (recorded, not tuned)**

**Mechanism.** Perp venues absorb liquidation shortfalls from a public insurance fund. When it
depletes, auto-deleveraging force-closes **profitable** positions — which, during a squeeze, is
precisely the desk's short-perp carry leg. The carry payoff therefore carries a state-dependent
haircut whose driver (insurance-fund balance and depletion rate) is public and free on Binance,
Bybit and BitMEX. The desk treats ADL purely as an *execution event*: SYSTEM_REVIEW #7 / GAP #60
documents that its ADL branch is live-ammo on the same decision surface that already lost
**$1,837.68**, and it has never modelled ADL's *probability*.

**This generalises a lesson the desk already wrote down and never operationalised.** From the
`era_crossvenue_fiat_premium_arb` kill: *"a cross-venue premium that PERSISTS is rent on a capital-
control / withdrawal / counterparty barrier — it is compensation, not inefficiency."* The desk
recorded that counterparty risk is a priced, structural quantity — and then built no observable for
it. `insurance fund` appears **exactly once** in the entire repo: `data_axis_watchlist.md:766`, as
an un-acquired data *target* with no mechanism attached. Textbook catalogue-and-stop.

**Falsification.** Collect insurance-fund history (free, public); test whether fund drawdown rate
leads force-close/ADL event intensity, and whether high-depletion states coincide with worse
realised carry P&L on the desk's own tape.

**WHY THE REJECT IS REPORTED RATHER THAN FIXED — a gate-optimality finding.** EV 0.0009 sits below
the 0.002 threshold, driven by `narrow_breadth` (4 venues) and a low `est_sharpe`. But
`est_sharpe` is **the wrong frame for this candidate**: BR-04 generates no return stream. Its value
is the removal of a left tail on the one deployed edge — it enters E[log W] through avoided ruin,
which `ev_score` has no term for. Per the GATE-OPTIMALITY DUTY this is a **gate mis-application**,
not a verdict on the mechanism, and the correct response is to say so rather than to inflate
`est_sharpe` until it passes. **Inputs were not tuned.** Routed as a recommendation against the EV
gate itself (R-row below), and the card is held for re-scoring once the gate can price risk-side
inputs.

**Strongest argument it is spurious.** ADL events on major venues are rare enough that the desk may
never observe one at its size, making this an expensively-monitored tail that never binds. If
insurance-fund depletion has occurred fewer than ~10 times across the available history, no
statistical claim is possible and this is a *monitoring* item, not a research item.

---

### BR-05 · CONTRACT-SPEC CHANGES AS NATURAL EXPERIMENTS — the identification strategy the desk has never used · EV **0.0117** · p 0.24 · QUEUE
**Highest second-order value (L1.15): it changes what the desk can know, not what it holds.**

**The observation.** Every hypothesis this desk has ever tested is **observational** — an IC or
Sharpe on a correlational panel, defended by de-contamination and multiplicity control. It has never
once used an **exogenous shock** for causal identification. Meanwhile exchanges publish hundreds of
dated, exogenous rule changes: funding-interval revisions, margin-tier and leverage-cap changes, fee
schedule changes, index-constituent changes, listings and delistings. Each is a natural experiment
with untreated pairs available as controls — difference-in-differences on a silver platter.

**The desk already knows natural experiments are its highest-grade evidence — it just thinks they
must be found abroad.** From the `era_ta_indicator_stack_crypto` kill: *"THE CLEANEST PUBLIC
IN-SAMPLE-vs-FORWARD NATURAL EXPERIMENT THE DESK HAS FOUND … the ONLY variable changed was whether
scoring was pre-registered-forward or in-sample, and it flipped the entire result set."* The desk
found one externally, correctly called it the cleanest evidence it had, and never realised it can
**manufacture** them — from a feed it is already collecting.

**It is already collecting the feed.** `data/exchange_announcements.jsonl` — 111 rows, OKX + Binance
+ Cointelegraph, live to 2026-07-31, **never tested**.

**First pre-registered experiment.** When Binance changes a pair's funding interval or leverage cap:
what happens to that pair's basis, OI and realised volatility relative to matched control pairs?
That answers whether funding structure **causes** positioning or merely reflects it — the
identification question sitting directly underneath the desk's only deployed edge, and one no
correlational test can settle.

**Falsification.** Pre-register the event window and control-matching rule *in code* before looking,
per the `listing_events.py` precedent (window and threshold as constants; a second window is a
second trial and raises `VARIANTS_TRIED`). If the DiD estimate is insignificant across ≥20 events,
the channel is not causal — a first-class negative with immediate budget value.

**Strongest argument it is spurious.** Rule changes are **not** exogenous: exchanges change margin
tiers and leverage caps *because* they observe rising risk, so the "treatment" is assigned on the
outcome. That is textbook endogeneity and it can manufacture a confident, entirely spurious causal
estimate — a worse failure than a null, because it wears a stronger methodological costume. Any
design must use only changes plausibly unrelated to the specific pair's state (venue-wide policy
changes, scheduled reviews) and must report the endogeneity argument alongside the estimate.

---

### BR-06 · THE KELLY DENOMINATOR — μ(σ) for the deployed carry sleeve · EV **0.0146** · p 0.30 · QUEUE
**Applies to the only edge that works, and needs no new data.**

**The observation.** The desk killed the vol-target overlay and wrote the reason in the graveyard:
> "vol-target overlay | Sharpe 1.40→1.07 — HURTS | `regime_artifact` | **carry edge is
> vol-correlated; de-levering high vol cuts the good periods**"

That is not merely a kill. **It is a measurement: carry's expected return rises with volatility.**
The desk filed it as a dead end and never asked the question it answers. The objective is
max E[log W]; the Kelly fraction is `f* = μ/σ²`. If μ itself rises with σ, then `f*(σ)` is *not* the
naive vol-target's `1/σ` and *not* flat — it is set by the measured shape of μ(σ). If μ grows more
slowly than σ², size should still fall with vol, just less than vol-targeting says. If it grows
faster, size should **rise** with vol. The desk currently does neither: it sizes flat, having
concluded from the kill that "vol conditioning does not work."

**Why nobody has this.** `Kelly denominator`, `conditional variance`, `vol forecast`, `mu(sigma)`:
**0 hits repo-wide.** The desk has spent essentially its entire research budget on μ and none on σ,
while its stated objective is a function of both — and σ is the far more forecastable of the two.

**Distinct from the killed overlay class (which was killed three times, correctly).** The overlay
class *conditions a directional signal on a regime* — "trade carry only when X." This does not
condition anything: the sleeve holds carry **always**, at size `f*(σ)` derived from its own measured
μ(σ) curve. "When to trade" versus "how much to hold" are different questions, and only the first
was tested.

**Data on disk.** `funding` and `basis` columns of `data/lake/bronze/crypto/<SYM>/D1/` (2011 → 2026,
279 symbols) plus the desk's own execution tape. No new acquisition.

**Falsification.** Estimate μ(σ) for the carry construction on lake history; derive f*(σ); compare
the sized book against flat sizing out-of-sample. Kill if μ ∝ σ² within error (f* statistically
flat — vol conditioning genuinely adds nothing), or if the sized version fails out-of-sample.

**Strongest argument it is spurious.** The 1.40→1.07 measurement came from a *specific* overlay on a
*specific* sleeve in a *specific* sample; reading it as a stable structural μ(σ) relationship is a
large extrapolation from one number. Worse, μ(σ) estimated on the same history used to size the book
is an in-sample fit that will flatter itself, and vol-conditional sizing is a well-known route to
levering into the exact regime that ruins a book. **A rail interaction is explicit here:** any f*(σ)
that rises with σ must remain strictly inside the L1.23 survival rails, which are untouchable —
this card may inform sizing *within* the rails and may never be a reason to move one.

---

### BR-07 · DEPTH WITHDRAWAL ACROSS THREE SYNCHRONISED BOOKS — the cancel, not the trade · EV **0.0044** · p 0.24 · QUEUE
**The only card that consumes the 7.1 GB idle proprietary corpus.**

**Mechanism.** The desk records Binance USD-M, Binance spot and Bybit linear **simultaneously**,
with its own timestamps. An informed market maker's first action on new information is not to trade
— it is to **cancel**: pull depth before being picked off. Trades are therefore a *lagging* record of
information arrival, and depth withdrawal is the leading one. The observable is which venue's book
thins first, and by how much, across three synchronised books.

**Why this is not the dead `taker_flow` and not the killed elite-flow work.** `taker_flow`
(`do_not_repeat` #3) and the Hyperliquid elite-flow kill both measured **trades**, and the elite-flow
kill diagnosed exactly why they cannot work: *"taker flow is CONCURRENT with price (buying moves
price), so it cannot lead it."* A cancellation moves no price. It is, by construction, the one
order-book event that can precede a price move without causing it — which is precisely what the
de-contamination gate is looking for and precisely what trade-based signals cannot supply. Repo-wide:
`queue position` 0 hits, `free float` 0 hits.

**Why it should carry value net of cost — and the framing matters.** As a **standalone alpha sleeve
this is unlikely to clear costs** and I do not claim it does: a 10-second-horizon signal must beat a
~3.8–5 bps measured round-trip, which is a brutal bar. Its defensible use is **execution timing**:
the desk *must already* trade to rebalance carry, and choosing the 10-second window in which to
cross the spread using depth asymmetry saves basis points on fills it was going to make anyway.
That is cost reduction — certain, not probabilistic — and it attacks the measured churn cost
directly. The alpha claim is the option; the cost claim is the floor.

**Data on disk.** `data/moat/fut/<SYM>/*.jsonl.gz` (955 MB, 30 symbols, depth ~1/10 s + every
trade), `data/moat/spot/` (524 MB, 30 symbols), `data/moat/bybit/` (5.7 GB, 20 symbols) — all
2026-07-17/21 → present. Depth *changes* between snapshots are computable directly; individual
cancels are not resolvable at 5–10 s sampling, and the design must not pretend otherwise.

**Falsification.** Per symbol, regress next-interval mid-return on cross-venue depth-withdrawal
asymmetry, at the recorded resolution; require the de-contamination gate to pass at that resolution
(where it is a genuine test rather than a low-pass filter). Separately and independently: measure
realised slippage on the desk's own fills conditioned on the signal — that test needs no alpha claim
at all. Kill the alpha branch if IC is insignificant; kill the execution branch if conditioned
slippage is not better than unconditioned.

**Strongest argument it is spurious.** At 5–10 s sampling, "depth withdrawal" is indistinguishable
from depth *consumed by trades* — and consumed depth is just taker flow, which is already dead and
already known to be contemporaneous. If withdrawal cannot be separated from consumption at this
resolution, the signal is taker flow in disguise and inherits its kill. The design must difference
out traded volume before it may claim to be measuring cancels, and if that differencing leaves
nothing, the card dies there. Second: only ~14 days exist, on 30 symbols, in one volatility regime.

---

### BR-08 · CARRY ENTRY BUYS THE BASIS AT ITS WORST · EV **0.0260** · p 0.30 · QUEUE
**Rank 2 of 9, and it is a live question about money the desk is already trading.**

**The measured fact nobody has explained.** From `decision_ledger 2026-07-28-fee-blind-pnl-and-
page-destruction`:
> "**73 churn-free round-trips run −58.27 bps net-of-fee, and only 12 of those bps are commission**
> — the dominant term is **price_pnl at −51.74 bps**, which for a delta-neutral pair should be ~0
> and does **NOT amortize with hold time**."

For a delta-neutral cash-and-carry, `price_pnl` **is the change in the basis**. A systematic −51.74
bps means the desk systematically loses on basis moves after entry.

**The mechanism that would explain it.** Perp funding is computed *from* the premium index — the
perp's price relative to spot. So "rank names by highest funding" is mechanically "rank names by
widest perp premium." Entering the top of that rank means shorting the perp at its local premium
extreme. If the premium **converges** afterwards, the desk profits on basis and the trade is
doubly good. The measurement says the opposite happens: the premium **keeps widening** after entry.
That is economically coherent — extreme funding marks a name being aggressively bought with
leverage, and that flow continues — and it reframes the carry harvest as **compensation for taking
the wrong side of an ongoing squeeze**, not a free cashflow. If true, the correct selection is not
max funding, but max funding **conditional on the premium no longer widening**.

**Why this is a live, unresolved question and not settled desk knowledge.** The desk has two
conflicting unexplained measurements of the same quantity and has reconciled neither: the 73-trade
study says non-funding P&L is strongly **negative** (−51.74 bps); the live `bleed_alert` says
non-funding P&L is strongly **positive** (+$3,573, "3161% of funding harvest"), which a prior cycle
attributed to an accounting echo rather than a leak. The desk itself caveats the 73-trade number
(n=73, `>72h` bucket n=1, partly contaminated by the naked-long-spot incident window). **The card is
not "the desk is losing money on basis" — that is not established. The card is: the dominant P&L
term of the only deployed sleeve is unattributed, and there is a specific, testable mechanism that
would explain the negative reading.**

**Falsification.** On lake history (`funding` + `basis`, 279 symbols, 2011 → 2026): condition on
funding-rank at entry and measure the forward *basis* path at 1/3/8/24 h and 1/5 d. Pre-committed
directional prediction: if the mechanism is real, top-funding-rank names show basis **widening**
over the first funding period and the effect strengthens with rank. Kill if the forward basis path
is flat or converging — which would refute the mechanism and send the −51.74 bps back to the
contamination explanation, itself a valuable answer.

**Strongest argument it is spurious.** n=73 with a contaminated window and a `>72h` bucket of n=1 is
not a fact, it is a hint — and the desk's own bleed alert points the *opposite* direction on a larger
sample. It is entirely possible that both readings are execution and accounting artifacts of a book
that spent the period churning (11,136 commission events for 251 logged round-trips; ~44 venue fills
per logged trade), and that there is no basis mechanism at all. The lake-history test is specified
precisely because it is **independent of the desk's own broken execution record** — it tests the
mechanism on market data, where an accounting artifact cannot reach.

---

### BR-09 · PRE-SETTLEMENT DODGE FLOW — with a cost-derived threshold · EV **0.0176** · p 0.48 · QUEUE

**Mechanism.** Funding settles at fixed instants (00:00 / 08:00 / 16:00 UTC). A holder who does not
want to pay it can close before and reopen after. Whether that is rational is a **calculable
inequality**: dodging is worth it only when the funding cost exceeds the round-trip cost of dodging.
So the prediction is not "there is flow around settlement" (vague, and adjacent to a published
periodicity effect) but the sharp conditional form: **pre-settlement flow appears only when
|funding| exceeds roughly twice the round-trip cost for that name, and its magnitude scales with the
excess.** Below the threshold, nothing should happen at all.

**Why this is defensible where the rejected quarter-hour effect was not.** `quarter_hour_
periodicity_crypto_futures` was rejected as `crowded_known` — a published periodic pattern with no
mechanism and no threshold. This is a mechanism with a **quantitative, name-specific threshold
derived from a cost stack**, and the desk holds a measured per-symbol cost curve nobody else has
(BTCUSDT 0.018 bps → OPUSDT 20.6 bps). The prediction is falsifiable in a way a periodicity claim
is not: it predicts *where the effect must be absent*, which is much harder to fit by accident.

**Data on disk.** `data/moat/fut/<SYM>/` at ~10 s covers the settlement instants directly: 3
settlements/day × ~14 days × 30 symbols. Per-symbol costs from `run_cost_model.py`; funding from the
lake.

**Falsification.** Bucket symbols by (|funding| ÷ measured round-trip cost) and test for excess
volume/OI change in the minutes before settlement. Kill if there is no threshold behaviour — i.e. if
flow is flat in the ratio, or present below the threshold where it should be absent. **The
below-threshold null is the load-bearing test**, not the above-threshold effect.

**Strongest argument it is spurious.** ~42 settlement events per symbol is a small sample for an
effect that only appears in the high-|funding| tail, so the conditioning that makes the card sharp
also guts its power. And if the effect is real it is almost certainly already arbitraged — it is
mechanical, public, and computable by anyone with a fee schedule. Most likely honest outcome:
`SCREEN-UNDERPOWERED`, accruing forward.

---

## AN L1.16a RE-OPEN — declared as a re-open, not counted as an invention

**`vpin_ofi_microstructure`** (`do_not_repeat` #13, REJECTED 2026-07-03).

- **Original mechanism of death, verbatim:** *"gross +59.4 bps decaying 2024→+82 bps to 2026→+12
  bps; **requires L2 tick infra**; IC decay kills expected ROI."*
- **Named enabling change:** the L2 tick infrastructure now **exists and is running at zero marginal
  cost** — 7.1 GB across three venues since 2026-07-17, recorded for other reasons. The kill was
  half economic (IC decay) and half **infrastructure cost**, and the infrastructure half is now free.
- **Why this addresses that mechanism:** the rejection weighed +12 bps of decayed gross against the
  cost of building tick infra. That cost is now zero and sunk. The economic half of the kill stands
  and must be re-tested honestly on current data — +12 bps against a 3.8–5 bps round-trip is thin
  but no longer obviously negative.
- **Disposition:** routed as a recommendation for a re-scored EV gate, **not** re-opened unilaterally
  here. L1.16a requires the enabling change to be named and to address the original death mechanism;
  it does, for half the kill, and that half must be stated rather than glossed.

---

## THE 12-MONTH LITERATURE COMPARISON LOG

**Purpose (spec):** measure whether this research engine is genuinely creative or an excellent
summariser. Every invention is logged with the date it was invented *blind*. On the check-back date
the desk searches the external literature for each mechanism and records whether it was published in
the interim, and if so whether before or after our invention date.

**Reading the result — pre-committed now, so it cannot be spun later:**
- *Published AFTER our date* → genuine independent invention. The engine originates.
- *Published BEFORE our date and we missed it* → the engine is a summariser with a coverage gap, and
  the external diggers failed to surface it.
- *Never published* → either genuinely novel, or (the honest alternative that must be considered
  first) too weak to be worth anyone's publication.

| id | invented (blind) | one-line mechanism | check-back | literature verdict |
|---|---|---|---|---|
| BR-01 | 2026-07-31 | funding rate × OI (dollar burden) as forced-deleveraging pressure and carry-selection variable | 2027-07-31 | _pending_ |
| BR-02 | 2026-07-31 | cross-sectional heterogeneity of funding half-life → select on expected funding over the hold | 2027-07-31 | _pending_ |
| BR-03 | 2026-07-31 | funding-interval sampling differences make venue choice a free option on identical carry | 2027-07-31 | _pending_ |
| BR-04 | 2026-07-31 | insurance-fund depletion as an ADL counterparty-risk haircut on carry payoff | 2027-07-31 | _pending_ |
| BR-05 | 2026-07-31 | dated exchange rule changes as DiD natural experiments for causal identification | 2027-07-31 | _pending_ |
| BR-06 | 2026-07-31 | measured μ(σ) for carry → Kelly f*(σ) instead of flat sizing or vol targeting | 2027-07-31 | _pending_ |
| BR-07 | 2026-07-31 | cross-venue depth withdrawal (cancels, not trades) as the non-contemporaneous lead | 2027-07-31 | _pending_ |
| BR-08 | 2026-07-31 | funding-rank selection is mechanically basis-momentum selection → adverse basis entry | 2027-07-31 | _pending_ |
| BR-09 | 2026-07-31 | pre-settlement dodge flow appears only above a cost-derived threshold | 2027-07-31 | _pending_ |

**Integrity rule for the check-back:** the verdict is recorded from a *search performed on the
check-back date*, and a card may not be quietly edited between now and then. Any correction to a
card's text is appended with its own date, never overwritten.

---

## ROUTING — and the blocker that stops it

**Pipeline capacity is exhausted, and this is a live idleness defect, not an excuse.**

| | |
|---|---|
| `data/forward_slots.json` | `m_concurrent 12`, `cap 12`, **`idle_slots 0`** — cohort FULL, Holm bar 2.61 |
| `data/promotion_queue.json` | `slots {occupied 12, cap 12, free 0}`, **`n_candidates 0`** — queue EMPTY |
| Estimated latency for a new candidate | ~181 days (90 clock + 90 queue + 1 decision) |

So: every forward slot is occupied, **and the candidate queue behind them is empty**. Under L1.30
(replacement rate) that is a countdown nobody is watching — when a slot frees, there is nothing
staged to enter it, and the desk waits a full pipeline latency to find out. Under L1.28a an empty
candidate queue with a non-empty candidate space is idle capacity. **These nine cards are exactly
the inventory that queue is missing**, and populating it costs no slot and no capital.

**Disposition of each card, per the two-stage law (L1.6):**
1. **Stage-A screens need no slot** and are unblocked today — BR-01, BR-02, BR-06 and BR-08 are
   runnable immediately on data already on disk. They are the first four to run.
2. **Forward clocks are blocked** until a slot frees. Cards are staged in the promotion queue, not
   held in a document.
3. **Zero promotion authority.** Nothing here reaches capital. BR-06 and BR-08 touch the *deployed*
   sleeve and therefore additionally face the L1.38 change-window rule; they are research findings
   about that sleeve, and any sizing or selection change is a separate, gated act.

---

## A GOVERNANCE CONFLICT — surfaced, not routed around (R0208)

This seat's charter is **"RESEARCH ONLY (freeze) … No code"**. L1.39 (ZERO IDLE FINDINGS) requires
every finding to advance its next pipeline stage **in the same run**, and for an invented mechanism
that next stage is the Stage-A screen (`MECHANISM_GRAPH`: mechanism → observable → hypothesis → EV
gate → **Stage-A screen** → forward clock). This run therefore stopped at the EV gate and
pre-registration and **could not screen**, although BR-01, BR-02, BR-06 and BR-08 are runnable today
on data already on disk.

SCREEN-ON-DISCOVERY does not strictly bite — it is scoped to *surfacing a new data axis*, and these
are mechanisms on axes already ingested — so the freeze is not violated. But **digger parity is**:
the charter binds the diggers as one family that advances together under UPGRADE PROPAGATION, every
other digger screens in-run, and this one is structurally barred from it.

Two resolutions, neither taken unilaterally here: **(a)** grant this seat read-only screen execution
through the audited `libs.research.axis_screen` harness (writes only to `reports/` and `data/`) —
the parity-restoring option; **(b)** keep the freeze and bind a named screening owner and date to
every card at pre-registration. Doing neither leaves invented mechanisms parked at the EV gate with
no clock, which is precisely the found-never-fixed defect L1.28b exists to kill.

---

## SUBSYSTEM COVERAGE (L1.0(e) — 100% breadth every cycle; depth rotates, breadth never)

| Subsystem | Depth this run | What it produced |
|---|---|---|
| Data | **deep** | full 8.7 GB on-disk inventory; found the 7.1 GB unscreened proprietary corpus |
| Validation / stats | **deep** | de-contamination gate re-read as a low-pass filter; power caveats pre-committed on 3 cards |
| Research process | **deep** | payoff-form reframe; natural-experiment identification gap (BR-05) |
| Portfolio / sizing | **deep** | BR-06 — μ(σ) and the Kelly denominator, unexamined |
| Execution | medium | measured cost curve (0.018 → 20.6 bps) used in BR-01/BR-07/BR-09; churn drag re-read |
| Risk | medium | BR-04 ADL/counterparty; rail-interaction constraint written into BR-06 |
| Governance | shallow | EV-gate mis-application on risk-side inputs (gate-optimality finding) |
| Ops / infra | shallow | confirmed recorder liveness and corpus growth; no defects hunted this run |

---

## NEXT UN-EXHAUSTED GROUND (L1.35 — named before closing)

**Sections claimed EXHAUSTED this run:** none. No section of this seat's ground was mined to
genuine depth today; the run was breadth-first across the desk's own artifact set.

**Named next ground, in order:**
1. **`data/moat/` at depth.** 7.1 GB read only for BR-07's design. The trade tape, the spot-vs-perp
   book relationship, and queue dynamics are each their own un-mined section.
2. **The 215-record decision ledger as a market-data source.** This run harvested ~8 measured
   market facts from it; it was read for lessons, not mined systematically. Every record with a
   number in it is a potential mechanism.
3. **The CME `statistics` and `definition` tapes** — 1.08 GB of the 1.1 GB CME directory, and the
   axis screen used only the OHLCV files. Settlement/OI/stat-type events on a regulated venue are
   untouched.
4. **`data/unlock_events.json`** — 5.0 MB of forward-looking token unlock schedules, ingested
   2026-07-24, never tested. Dated forced supply is the purest forced-flow object the desk holds.
5. **The graveyard's kill *bases* as a dataset.** 40 kills each carry a mechanism of death; nobody
   has asked which death mechanisms recur, which would name the desk's systematic failure modes.

---

## CLOSE — blunt

**This run did not find a new tradeable edge, and none of the nine cards is one.** They are
hypotheses with mechanisms, falsifiers and honest arguments against, and the base rate says roughly
one may survive Stage A.

**The finding is the deliverable, and it is not padding.** The desk's most load-bearing belief —
"price-only alpha is dead, the lever is new data" — was formed by an instrument that structurally
cannot detect fast signals, from a sample containing zero intraday observations, while 82% of the
desk's own data by volume (and 100% of its unreplicable data) sits unscreened. The desk has already
been burned once by reading an instrument property as a market property; the 420/0 record was
re-diagnosed as a welded-gate artifact on 2026-07-30. This is the same error class at the level of
*resolution* rather than *threshold*, and it has not been tested.

**The strongest card is not the most novel one.** BR-08 asks why the dominant P&L term of the only
deployed sleeve is unattributed and mutually contradictory across two of the desk's own
measurements. That is a live question about money already being traded, and it outranks every new
axis on this page.

**Timidity check.** Nine cards, no numeric cap applied, none held back for being large or awkward.
BR-04 was EV-rejected and is reported as rejected with its inputs untouched — the gate was named as
mis-applied rather than gamed, which is the only honest way to disagree with a gate.

**Ledger rows for this session: R0200–R0208.** They were originally written as R0197–R0205 and
renumbered at push time: a sibling session had already taken R0197–R0199 on origin (trail-width and
funding-sign cost-hunt rows). Both sessions' rows are preserved in full — 208 total, IDs unique and
monotonic, origin's 199 untouched. Recorded here because a renumber that is not written down looks
identical to a dropped row, and dropping an inconvenient row is the one thing the ledger forbids.

_Session closed 2026-07-31. Next scheduled run: 2026-08-31, or earlier on due-by-state._
