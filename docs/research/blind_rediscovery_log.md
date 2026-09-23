# BLIND REDISCOVERY LOG

> **UNIVERSE RETARGETED 2026-08-18, header added 2026-09-05.** Inventions logged before that date
> were derived blind against the retired crypto-exchange desk's problem set. They are kept because
> the point of this organ is the CONVERGENCE MEASUREMENT -- what a fresh-eyes pass re-derives
> independently is evidence about the desk's coverage, and that evidence does not expire with the
> venue. New passes run against the MT5/Fusion book.

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

## A GOVERNANCE CONFLICT — surfaced, not routed around (R0210)

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

**Ledger rows for this session: R0202–R0210.** They were originally written as R0197–R0205, renumbered twice as a sibling session pushed, and
renumbered at push time: a sibling session had already taken R0197–R0199 on origin (trail-width and
funding-sign cost-hunt rows). Both sessions' rows are preserved in full — 208 total, IDs unique and
monotonic, origin's 199 untouched. Recorded here because a renumber that is not written down looks
identical to a dropped row, and dropping an inconvenient row is the one thing the ledger forbids.

_Session closed 2026-07-31. Next scheduled run: 2026-08-31, or earlier on due-by-state._

---

# APPENDED 2026-08-05 — R0210 RESOLVED: option (b), and every card now has an owner

_Appended, not edited. The integrity rule above forbids quiet edits to a card, so this is a dated
correction that leaves the 2026-07-31 record exactly as it was written._

**The conflict, restated in one line:** this seat is frozen to RESEARCH ONLY and may not run a
screen, while L1.39 requires every finding to advance its next pipeline stage in the same run, and
for an invented mechanism that stage is the Stage-A screen. Five days on, the cost of leaving it
unresolved is measurable rather than hypothetical: of the nine cards, four had reached a screen
(BR-03 under R0121 SCREEN-CONDITIONAL, BR-04 under R0204, BR-07 under R0203, BR-08 screened and
refuted-reversed under R0206) and **four had no owner, no clock and no artifact at all**.

**RESOLUTION: option (b) — keep the freeze, make the handoff explicit.** Option (a), granting this
seat read-only `axis_screen` execution, was not taken, and the reason is specific rather than
cautious: this seat's entire value is that it reasons from the desk's own artifacts *without* the
desk's own conclusions, and the 12-month originality measurement (R0209) is only interpretable if
the seat stayed blind. Screen execution means reading screen output, which is the desk's
conclusions arriving by the back door. The freeze is not overhead here — it is the instrument.

**What makes (b) real rather than a promise.** The obvious implementation — an "owner" column in
the table above — is a write-only inbox, the failure this desk has paid for repeatedly. Instead
every card leaves the seat as a **row in the recommendation ledger**, which is chased:
`recommendations.owed()` treats a scheduled row past its due date exactly like an undisposed
orphan, and `carryover_brief.py:77` imports that function directly rather than restating it, so an
unowned card surfaces at the top of every cycle until disposed. This is inside the freeze — the
ledger lives under `docs/research/*` and adding a row runs a sanctioned CLI, touching neither
`scripts/` nor `libs/`. Bound into the seat's own instructions at
`ops/blindrediscovery_dig_prompt.txt` (OUTPUTS / ROUTING) and into the companion section of
`docs/research/PROSPECTOR_SPEC.md`, so it binds the next run rather than this note.

**The four unowned cards, now owned:**

| card | mechanism | screening owner | row |
|---|---|---|---|
| BR-01 | funding × OI (dollar burden) as deleveraging pressure and carry-selection variable | cycle org | **R0381** |
| BR-02 | cross-sectional funding half-life → select on expected funding over the hold | cycle org | **R0382** |
| BR-06 | measured μ(σ) → Kelly f*(σ) instead of flat sizing | cycle org (L1.38-fenced) | **R0383** |
| BR-09 | pre-settlement dodge flow above a cost-derived threshold | cycle org | **R0384** |

BR-06 carries an extra fence and it is stated on its row: it touches the only deployed sleeve, so
it faces the L1.38 change window, and under the two-stage law a measured μ(σ) earns a measurement
and a forward clock, never a size change.

**Found while resolving this, fixed in the same commit — the seat was being throttled by a
sentence nobody could see.** `PROSPECTOR_SPEC.md:124` still read *"invent up to 5 mechanisms"*.
The principal's 2026-07-19 exhaustion order removed that cap from
`ops/blindrediscovery_dig_prompt.txt` and never followed it through the delegation, and
`check_timidity_language.py` could not catch it because `_prompt_surfaces()` globbed
`ops/*prompt*.txt` and stopped there — while the prompt's own first line orders the organ to *read
the spec*. **A doc a prompt orders an organ to read is a prompt surface**; instructions reached by
one hop of indirection bind exactly as hard as inline ones. That is the same transitive-
reachability blindness `check_orphan_code` was fixed for, in a different costume, and it is the
L1.36 REACHING condition failing in the one direction the fence was built to prevent: the law was
enforced, the surface was unreached. The cap is gone and the four delegated instruction docs are
now swept. Records (`prospector_coverage.md`, `prospector_watchlist.md`) are deliberately **not**
swept — the draft that globbed them fired QUOTA-CAP on "up to 26 years", a data span in a coverage
record, and a gate that cries wolf gets switched off.

_R0210 closed 2026-08-05._

---

# SESSION 2026-08-11 — second formal run

**Fired by:** due-by-state, 11 days after the 2026-07-31 run (standing cadence is monthly; the
early-fire rule names "material new internal raw material" and the interval supplied it: the moat
corpus grew 7.1 → **17 GB**, three new law-built instrumentation layers landed (L1.45 excitation,
L1.46 clock provenance, L1.47 funding clock) each carrying measured facts that did not exist on
07-31, BR-08 was screened and refuted-reversed, the kimchi kill was re-based, and the graveyard
gained ~12 entries including the RU statarb family prior R0296. §33 gate: BACKLOG-CLEAR, mining
authorised.

**Method compliance:** ZERO external search. Every input below is a desk artifact.

### Inputs read (complete)
| Artifact | What was taken |
|---|---|
| `docs/graveyard.md` (739 lines, full) | every kill class + kill basis; the RU statarb prior; the SFD-class probe; the barrier-migration synthesis |
| `research_agenda.json` (50 `do_not_repeat`, 20-item queue) | full — including the 2026-07-31 L1.16a re-opens and the 2026-08-05 EV rejects |
| `data/strategy_coverage.json` | family states: STATISTICAL-ARBITRAGE the one NEVER-HUNTED family; 6 thin |
| Prior session (BR-01…BR-09) + R0381–R0384 | collision set; BR numbering continues at BR-10 |
| `data/decision_ledger.json` (230 records; 14 since 08-01 read in full) | the 08-05 execution-hypotheses record (H1–H3), the EV-gate recalibration history |
| `docs/research/MECHANISM_GRAPH.md` M1–M5 + addendum | node discipline; M5 feedback named as the desk's own candidate (not re-invented here) |
| `data/funding_capture.json` (L1.47) | close-phase octiles, 59/266 forfeit closes z=+4.8, 41.4% mis-marked |
| `data/excitation_design.json` (L1.45) | frozen arms; the identification target |
| `data/data_assets.json` (120 assets) + on-disk verification | what is actually testable today (COT zcache has NO crypto markets — checked, one candidate dropped for it) |
| `docs/research/prospector_watchlist.md`, `weak_signal_registry.md` | prior-art: SFD-class probe card (2026-08-04), WS-001 barrier law, R0296 statarb prior |
| `data/mine_generation_priors.json`, forward slots / promotion queue | routing capacity |

**Novelty gate:** all nine candidates scored against the **rebuilt** 231-prior corpus
(`build_graveyard_priors.py` re-run this session so the 08-11 kills are in it) via
`libs.alpha_factory.hypothesis_novelty`. Max similarity 0.30, none redundant at the 0.7 bar.
Unlike the 07-31 run this pass carries real weight: the gate's recall was fixed 2026-08-11
(IDF-containment, 195/195 on replay, FP 0/30). The manual per-card graveyard cross-check was
still performed and is written into each card.

---

## THE FINDING — what the desk's narrative cannot see (run 2)

Three findings this run, each with named evidence and each converted to cards in the same session.

### Finding 1 — the desk's laws are manufacturing proprietary data faster than its research engine notices

Three instrumentation layers were built in the last six weeks, each to satisfy a law, and each is
consumed by exactly ONE fence and ZERO hypotheses:

| Series | Law that built it | Only consumer today | Its own text says |
|---|---|---|---|
| excitation-arm fills | L1.45 | `run_cost_identification` → `check_excitation` | (fills are the identification corpus) |
| `delta = t_recv − t_venue` | L1.46 | `check_clock_provenance` | "first-class and **STRUCTURALLY UNBUYABLE**" |
| funding-cycle phase (octiles) | L1.47 | `check_funding_capture` | "a free control variable with the same P&L units as hold duration" |

The pattern: **instrumentation built to satisfy a law stops being read as data.** Each series is
proprietary in the strictest sense (requires our quotes, our vantage, our fills), each is accruing
daily at zero marginal cost, and none has ever had a hypothesis pointed at it. This is the 07-31
finding ("82% of data unscreened") in a sharper form — that was data collected FOR research and
not yet screened; this is data the GOVERNANCE layer creates as a by-product, which no organ's
charter treats as research material at all. BR-16, BR-17 and BR-12 are the conversion.

### Finding 2 — the desk learned its independence lesson for validation and never fed it back into selection

The desk measured its cross-section at **N_eff 1.54 raw / 29 market-neutral** and built the
demeaning-floor discipline (`cohort_independence`) — for *validating* candidates. The deployed
carry sleeve still selects on the **raw funding level**, which maximally loads the common
leverage-appetite factor: the whole book's payment stream is close to ONE bet timed by market-wide
sentiment, and every queued refinement (BR-01 burden, BR-02 half-life, realised-cost H1,
dispersion-crowding) modifies the rank input without decomposing it. The independence arithmetic
the desk applies to candidate returns has never been applied to its own selection variable.
BR-11 is the conversion, and it opens the one NEVER-HUNTED family (statistical arbitrage) on the
funding surface — where the desk's priors are strongest — instead of in dead price space.

### Finding 3 — the contract lifecycle is instrumented at one end

`listing_events.py` pre-registers the birth end of the perp lifecycle. §42 named "delisting
unwinds" as ground on day one, and no organ ever built the death end: the announcement collector
runs (472 rows) but carries ~1 delist-tagged row, `futclose_daily` (139 symbols of dated-future
closes) has no hypothesis consumer, and the lake's 296 symbol dirs include early-enders nobody
has classified as delistings vs collector boundaries. "We have an event study" has been reading
as coverage while covering half the lifecycle. BR-10 (and the BR-14 reject's idle-data
observation) are the conversion.

---

## PRIOR-ART COLLISIONS — declared before the cards

- **BR-12 vs the 2026-08-04 SFD-class watchlist probe.** The SFD kill banked "audit the CADENCE,
  not the formula" — a venue-clock LAG game on throttled references. BR-12 is the **incentive**
  half of the same surface (pushing the reference INTO the averaging window). Lag ≠ marking; both
  declared, neither claims the other.
- **BR-12 vs BR-09/BR-03.** BR-09 is dodge flow (no post-stamp reversion predicted); BR-03 is
  venue-as-sampling-scheme. BR-12's signature is reversion after the stamp, scaling with an
  incentive rank. Three different observables on the settlement clock.
- **BR-16 vs `execution_maker_carry` (queue rank 1).** That is a POLICY (post-only entries);
  BR-16 is a SENSOR derived from those fills. The policy generates the sensor's data.
- **BR-16 nearest prior `lit_prediction_market_microstructure_vs_book` (sim 0.23).** That kill's
  mechanism — features re-deriving a price that already contains them — does not transfer: our own
  fills are in nobody's book.
- **BR-11 vs BR-01/BR-02 and `cross_venue_funding_dispersion_crowding` (queued).** BR-01 rescales
  the level by OI; BR-02 is a per-name time-series property; the queued gauge is cross-VENUE
  same-symbol dispersion as a stress meter. BR-11 is the cross-SYMBOL factor decomposition of the
  selection variable itself. Four different objects.
- **Dropped for collision, recorded so the check is auditable:** funding-interval transition
  events (inside BR-05's pre-registered event classes); liquidation-cascade carry entry timing
  (the killed conditioning-overlay class, and M5 feedback strength is the MECHANISM_GRAPH's own
  named candidate — not this seat's invention to claim); borrow-rate vs funding (dropped by the
  07-31 run, M1 saturated); Deribit skew-vs-funding consistency (breadth 2 → EV ~0.0005,
  pre-rejected; `options_skew_riskreversal` already queued); COT crypto positioning (verified
  NOT on disk — `cot_zcache` is FX/metals only — and the intent overlaps the queued
  dispersion-crowding gauge); intra-window premium session attribution (no premium-path archive
  exists yet; named as future ground, not carded).

---

## THE CARDS — seven queued, two EV-rejected honestly

All EV scores from `libs.research.alpha_economics.ev_score` (threshold 0.002), inputs honest, not
tuned. All nine logged in `research_memory`. Ledger rows R0445–R0451 bind a screening owner
(cycle org) and a due date to every queued card, per R0210(b). **None of these earns a cent; a
Stage-A pass earns a pre-registered forward clock at most (L1.6).**

| card | mechanism node | EV | p | novelty | route |
|---|---|---|---|---|---|
| BR-11 funding-factor residual selection | M1 funding node, decomposed | **0.0104** | 0.30 | 0.726 | **R0445**, due 08-25 |
| BR-12 settlement-marking pressure | funding-benchmark node (new) | **0.0103** | 0.48 | 0.772 | **R0446**, due 08-25 |
| BR-15 negative-funding borrow asymmetry | M1 funding node, sign-split | **0.0095** | 0.30 | 0.779 | **R0447**, due 09-01 |
| BR-13 CME-closure weekend differential | funding node × calendar (new) | **0.0074** | 0.30 | 0.726 | **R0448**, due 09-01 |
| BR-16 own-quote adverse-selection gauge | execution reality (L1.11b ERM) | **0.0070** | 0.24 | 0.767 | **R0450**, due 09-08 |
| BR-17 venue-clock delta congestion | infrastructure latency (new) | **0.0059** | 0.24 | 0.797 | **R0451**, due 09-08 |
| BR-10 delisting forced-unwind | contract-lifecycle forced flow | **0.0048** | 0.24 | 0.786 | **R0449**, due 09-08 |
| BR-14 dated-futures fixed-vs-floating | basis term structure | 0.0011 | 0.105 | 0.704 | **EV-REJECTED**, recorded |
| BR-18 residual pair reversion (cost-first) | lottery-demand reversion | 0.0014 | 0.045 | 0.728 | **EV-REJECTED**, recorded |

Full mechanism text, WHO-is-forced, data-on-disk paths, timestamp-alignment declarations,
falsifiers and the strongest-spurious-argument for each card live in the ledger rows (R0445–R0451,
written at full §32 depth) — not duplicated here; the ledger is the chased copy.

**The two rejects, and why they are reported rather than resubmitted:**
- **BR-14** (lock carry via short dated future when implied fixed rate is rich vs expected
  funding): dies on `crowded_known` (cash-and-carry-to-expiry is THE institutional trade; the CME
  variant was EV-rejected 08-05) × breadth ~10, and the un-crowded remainder is exactly where
  dated books are sub-viable. The card's independently-standing observation — `futclose_daily` has
  zero hypothesis consumers — is banked in Finding 3.
- **BR-18** (residualized fork/ecosystem pair reversion, estimator frozen at OLS+σ per R0296,
  falsifier = measured costs): the `price_only` prior (0.30, earned by 420/0 plus three external
  replications) takes honest inputs to 0.0014. Not tuned to pass. The statarb family-opening duty
  is discharged by BR-11 instead — on the surface where the desk's priors are strongest. If BR-11
  survives Stage A, the residual-object approach gains evidence and BR-18 may re-enter under
  L1.16a with that named change.

**Timidity check.** Nine candidates, no cap applied, none shrunk to review easier. The two
rejections are the gate's honest arithmetic on honest inputs — recorded with their inputs, like
BR-04 before them, not quietly dropped.

---

## THE 12-MONTH LITERATURE COMPARISON LOG (run-2 additions)

Same integrity rule as 07-31: verdicts recorded from a search performed on the check-back date;
cards are never quietly edited, corrections append with their own date.

| id | invented (blind) | one-line mechanism | check-back | literature verdict |
|---|---|---|---|---|
| BR-10 | 2026-08-11 | perp delisting = forced unwind with a public deadline; event-study the announce→settle window | 2027-08-11 | _pending_ |
| BR-11 | 2026-08-11 | decompose funding cross-section into leverage-appetite factor + idiosyncratic residual; select carry on the residual | 2027-08-11 | _pending_ |
| BR-12 | 2026-08-11 | benchmark-fixing pressure on the premium index inside the funding averaging window, detected by post-stamp reversion scaled by |funding|·OI/depth | 2027-08-11 | _pending_ |
| BR-13 | 2026-08-11 | weekend CME closure removes the basis-arb balance sheet weekly; funding differential appears only on CME-listed names | 2027-08-11 | _pending_ |
| BR-14 | 2026-08-11 | perp-vs-dated-future as floating-vs-fixed carry term choice (EV-rejected at invention) | 2027-08-11 | _pending_ |
| BR-15 | 2026-08-11 | negative funding persists longer than positive because shorting spot requires borrow — asymmetric arb supply | 2027-08-11 | _pending_ |
| BR-16 | 2026-08-11 | own randomized maker quotes as informed-flow probes; markout dispersion = proprietary toxicity gauge | 2027-08-11 | _pending_ |
| BR-17 | 2026-08-11 | recv-minus-venue timestamp delta as a continuous matching-engine congestion sensor leading vol/spread | 2027-08-11 | _pending_ |
| BR-18 | 2026-08-11 | residualized economic-family pair reversion off retail lottery demand (EV-rejected at invention) | 2027-08-11 | _pending_ |

---

## ROUTING

Forward slots 12/12 with the promotion queue's candidate side still thin — unchanged from 07-31:
Stage-A screens need no slot and are unblocked today (BR-11, BR-13, BR-15 runnable immediately on
lake data; BR-12, BR-16, BR-17 on the moat/execution tape; BR-10 after event-list assembly).
Every queued card is a ledger row with an owner and a due date, chased by `recommendations.owed()`
until disposed. This seat ran inside its freeze: no screen was executed here, no code was touched,
and the handoff is explicit per R0210(b).

**Observed in passing, not chased (freeze):** `data/screen_funding_interval_mismatch.json`
appeared in one directory listing this session and was absent minutes later — shared-tree sibling
activity or a vanishing screen artifact. Whichever it is, the BR-03/R0121 screen's artifact state
deserves one glance from the cycle org; noted here rather than rowed to avoid double-carding a
sibling's in-flight work.

## SUBSYSTEM COVERAGE (L1.0(e))

| Subsystem | Depth | What it produced |
|---|---|---|
| Data | **deep** | Finding 1 (three fence-only proprietary series); COT-not-on-disk verification; moat 17 GB re-measure |
| Research process | **deep** | Finding 2 (validation lesson never fed back to selection); statarb family opened on the right surface |
| Validation / stats | medium | novelty-gate rebuild + post-fix weighting; DSR-honest cell accounting written into every falsifier |
| Execution | **deep** | BR-16/BR-17; L1.47 phase facts read as research material |
| Portfolio / sizing | medium | BR-11's N_eff-of-payment-stream framing |
| Risk | medium | BR-15's compensation-vs-inefficiency falsifier; BR-10 endogeneity declaration |
| Governance | medium | Finding 1 IS a governance observation; two honest EV-rejects recorded |
| Ops / infra | shallow | vanishing-artifact observation above |

## NEXT UN-EXHAUSTED GROUND (L1.35 — named before closing)

**Sections claimed EXHAUSTED this run:** none.

1. **The moat trade tape as an object in itself** (17 GB; BR-12/BR-17 consume stamp-windows and
   deltas — the aggressor-sequence structure between stamps is untouched).
2. **Intra-window premium-index path archive** — does not exist yet; the BR-03 screen and BR-12
   both want it; whoever builds it unlocks the session-attribution ground named and not carded
   this run.
3. **`data/unlock_events.json` + the now-running `circulating_supply` point-in-time collector** —
   the unlock axis re-test with a defensible conditioning variable becomes possible as the PIT
   series accrues; the 0/27 screen died partly on `pct_circ_now` look-ahead, not on the mechanism.
4. **The graveyard's kill-bases as a dataset** (carried from 07-31, still unmined): which death
   mechanisms recur names the desk's systematic failure modes.
5. **CME `statistics`/`definition` tapes** (carried from 07-31, still untouched at 1.08 GB).

## CLOSE — blunt

**No new tradeable edge was found, and none of the nine cards is one.** Seven mechanism cards
with falsifiers and owners; base rate says perhaps one survives Stage A. The deliverable is the
three findings, and the sharpest of them is Finding 1: the desk's governance layer is now
generating unbuyable data as a by-product — own-quote probes, venue-clock deltas, funding-phase
octiles — and every one of those series terminates in a fence instead of a hypothesis. The prior
run found the desk had not screened the data it collected on purpose; this run finds it does not
even regard as data what it collects by law. Fresh eyes in a year should check whether that
pattern has a third instance — whatever L1.58+ builds next will probably also emit a proprietary
series with a fence as its only reader.

_Session closed 2026-08-11. Ledger rows R0445–R0451. Next scheduled run: 2026-09-11, or earlier
on due-by-state._

---

# SESSION 2026-08-12 — third formal run

**Fired by:** due-by-state, **one day** after the 2026-08-11 run. A one-day interval sets a high bar
for "material new internal raw material", and the interval cleared it: **107 commits**, the
graveyard priors corpus rebuilt **231 → 251 canonical priors** (~20 new kills in a day, including
`hijri_ramadan_calendar_axis`, `mcpt_return_permutation`, `era_selfref_mark_liquidation_796` and
seven `lit_*` entries), and **three new instrumentation layers landed the same day** — R0334
execution decomposition, R0371 fee attribution, and the capability-hunt s1 third cost basis. §33
gate: BACKLOG-CLEAR, mining authorised.

**Method compliance:** ZERO external search. Every input below is a desk artifact.

### Inputs read (complete)
| Artifact | What was taken |
|---|---|
| `docs/graveyard.md` (1090 lines, full index built) | complete kill index with S/T classification; the `era_selfref_mark_liquidation_796` **residue clause**; the four adjacent kills that buried BR-22 |
| `research_agenda.json` (50 `do_not_repeat`, full queue) | verbatim slugs — `liquidation_heatmap_cascade_predict[13]` and `vpin_ofi_microstructure[12]` each killed a candidate before it was written |
| `data/strategy_coverage.json` | 14 families: 7 HUNTED, 6 THIN, 1 MENTIONED-NEVER-TESTED |
| Prior sessions (BR-01…BR-18) + R0445–R0451 | collision set; numbering continues at **BR-19** |
| `libs/research/mine_conversion.py` (read to the line) | **the finding** — the `wired` definition and `backing_reason()`'s corroboration test |
| `libs/research/alpha_economics.py` (read to the line) | `EV = P × dSharpe × …` — the gate is parameterised in Sharpe |
| `data/decision_ledger.json` (232 records) | the 2026-08-05 execution-hypotheses record **in full** — it killed one of my two candidate findings |
| `data/jp_funding_clamp_census.json` (produced today) | killed my other candidate finding |
| `data/freshness_contracts.jsonl` (1,435 contracts / 1,096 paths) | the instrument that makes the finding's fix cheap |
| `data/print_impact.json`, `moat_series.jsonl`, `fee_attribution.json`, `execution_quality.json`, `funding_caps.json`, `oi_ls_universe.jsonl`, `micro_feature_store.json`, `geckoterminal_trades.jsonl` | the orphan set, verified by grep for consumers rather than assumed |
| `scripts/screen_funding_interval_mismatch.py` | collision clearance for BR-19 |

**Novelty gate:** priors corpus **rebuilt this session** (`build_graveyard_priors.py`, 251 priors) so
today's ~20 kills are in it. All four candidates scored via `libs.alpha_factory.hypothesis_novelty`.
Max similarity **0.309**, none redundant at the 0.7 bar. Manual per-card graveyard cross-check
performed in addition, and it is what killed two candidates the automated gate passed.

---

## TWO CANDIDATE FINDINGS DIED AGAINST THE DESK'S OWN RECORDS — recorded, because the discipline is the deliverable

Both were developed to the point of being cardable before being checked. Recording them is not
padding: an early-fired run's main risk is re-deriving yesterday's work, and this is the evidence
the check was actually performed.

1. **"The desk's carry selection variable is CENSORED."** Binance funding is
   `premium + clamp(interest − premium, ±0.05%)`, so a ±0.05% dead band pins funding at the
   0.01% constant and destroys the premium information inside it; the desk ranks carry names on
   the censored variable. **Already measured — the same day.** `data/jp_funding_clamp_census.json`
   (JP frontier miner, 2026-08-12): `share_exactly_0.0001` **0.3556**, `share_on_either_constant`
   **0.4162**, and a live cross-section where 56 names tied at the 8h dead-band constant span
   **74.9 bps** of premium. The census even proposes the premium tie-break. Dropped as a
   re-derivation.
2. **"The EV gate is structurally blind to cost-side mechanisms."** True — `ev_score` is
   proportional to `est_sharpe`, so a cost mechanism must be translated into a Sharpe to be scored
   at all. **Already flagged**, 2026-08-05, in the `flagged_gap` field of
   `2026-08-05-generation-three-execution-hypotheses-and-a-miscalibrated-ev-gate`: *"it penalises
   execution/cost work hardest — which the constitution ranks equal to alpha"* (F0023/R0038).
   One increment survives and is **contributed to the open row rather than carded as new**: R0038's
   proposed remedy is a *recalibration with an acceptance-rate target*, and recalibration cannot
   fix a **missing dimension**. A threshold move changes which Sharpes pass; it does not give a
   bps-saved-per-round-trip a way to be expressed. BR-20 below is the live instance — it rejected
   at 0.0016 in exactly that class, and was recorded rather than re-tagged.

---

## THE FINDING — what the desk's narrative cannot see (run 3)

### §33 credits conversion by asking whether a file was WRITTEN, never whether anything READS it — so the maximally law-compliant dig manufactures orphans

Runs 1 and 2 each found a version of idle data: run 1 that 82% of collected data was unscreened,
run 2 that governance-built instrumentation terminates in a **fence** instead of a hypothesis. Two
sightings of a symptom. **This run found the generator**, and it is written into the law that
exists to prevent it.

`libs/research/mine_conversion.py:29` defines the disposition:

> `wired -- code exists AND executed AND wrote a real artifact`

and `backing_reason()` (lines 316–357) corroborates that claim with exactly three tests: the named
path **exists**, is **non-empty**, and its **mtime postdates the find**. There is **no consumer
check anywhere in the module.** The disposition is named *wired* — a word that means *connected to
something* — and the instrument measures *written*. The vocabulary promises a connection and the
test certifies a file.

So the behaviour that maximally satisfies §33 is: mine a source, write a collector, emit a
`.jsonl`, claim `[§33: wired -> data/X.jsonl]`, and the gate prints **BACKLOG-CLEAR** — the exact
string at the top of this seat's own prompt today. Every organ downstream reads that as *conversion
is complete*.

**Measured on disk right now.** Six artifacts with zero consumers of any kind — not a research
reader, not even a fence — every one of which would be creditable as `wired` today:

| artifact | size / rows | what it holds | consumers |
|---|---|---|---|
| `data/moat_series.jsonl` | 82 MB / **93,345** | per-symbol-day `withdrawal_rate`, `book_slope`, `replenishment_halflife` | writer only |
| `data/geckoterminal_trades.jsonl` | 19 MB / **38,271** | DEX trades with `tx_from` wallet attribution | writer only |
| `data/print_impact.json` | 74 KB | **99 fitted impact curves**, 34 dual-basis pairs | writer only |
| `data/tail_funding_divergence.jsonl` | 987 rows | cross-venue funding spread, OI-filtered | writer only — *its own docstring says so* |
| `data/funding_caps.json` | **747 symbols** | per-symbol funding cap/floor | none |
| `data/carry_viability.json` | 45 symbols | per-symbol breakeven funding | none |

**Why the desk cannot see it, stated precisely:** the desk built reachability analysis for **code**
— an import-graph walk, and L1.49's insistence that reachability is measured from the declaration
site — and **never built the equivalent for data**. A function nobody calls is a named defect class
here. A dataset nobody reads is a *conversion*.

**And the fix is a join, not a subsystem.** L1.44 already self-builds `data/freshness_contracts.jsonl`
from **actual read sites** — 1,435 contracts over 1,096 distinct paths, keyed
`{ts, event, path, caller, kind, max_age_h, age_h, guardian}`. Checked this run: **not one of the
six orphans appears in it.** The registry that answers "does anything read this?" already exists,
already self-builds, and already excludes exactly the right files; `backing_reason()` simply never
consults it. This is R0371's shape one level up — *the first repair is a consumer, not a producer*.
Routed as **R0525**, owner cycle org, due 2026-08-19. This seat is frozen out of `libs/`.

**A run-2 forecast resolved in one day, and it resolved correct.** Run 2 closed by predicting:
*"whatever L1.58+ builds next will probably also emit a proprietary series with a fence as its only
reader."* L1.60 landed 2026-08-12 and emitted `data/denominator_attrition.json` — read by
`check_denominator_attrition.py` and nothing else. Recorded here as a resolved prediction (L1.29
material), not claimed as this run's finding: it confirms run 2's Finding 1, and the mechanism above
is *why* it keeps happening.

---

## PRIOR-ART COLLISIONS — declared before the cards

- **BR-19 vs `screen_funding_interval_mismatch.py`.** That screen tested whether the funding
  *calendars* are OFFSET (a settlement-straddle arb) and found the mechanism **geometrically
  impossible** — Binance's 4h grid is a strict superset of its 8h grid. BR-19 makes no calendar
  claim; it treats the parameter as a venue-revealed risk classification. Different object.
- **BR-19 vs BR-05 (spec changes as natural experiments).** BR-05 pre-registers *transitions* as
  events. BR-19 is the *standing cross-sectional state*. Run 2 dropped interval-transition events
  into BR-05; this does not re-open them.
- **BR-19 vs L1.47 and `jp_funding_clamp_census`.** L1.47 uses `fundingIntervalHours` for **accrual
  arithmetic** (a correctness fix — `/8.0` under-counts 4h names 2×). The census measures the
  information the clamp **destroys**. BR-19 claims the parameter **carries** information. Three
  uses of one field; only the third is a signal claim.
- **BR-21 vs H1 (2026-08-05).** H1's predictor is our **own realised** round-trip cost. That
  predictor is structurally undefined for a name the desk has never traded — the L1.45 cycle
  exactly. BR-21's predictor is third-party book state, defined on the whole universe. The
  distinction *is* the card.
- **BR-21/BR-20 vs `vpin_ofi_microstructure` (`do_not_repeat[12]`).** That was rejected for
  requiring L2 tick infrastructure and for IC decay. Both cards here consume **already-computed
  daily/interval aggregates** that exist on disk; neither proposes tick infrastructure.
- **BR-20 vs BR-07 and BR-16.** BR-07 is depth *withdrawal* (the cancel side only). BR-16 is
  adverse selection measured on **our own** quotes. BR-20 is the displayed-vs-traded ratio from
  **third-party** prints. Three observables, one surface.
- **BR-22 vs four adjacent kills** — `dex_cex_volume_ratio_flow`, `exchange_netflow` (0/12 cells),
  `hyperliquid_trader_skill_persistence` (position-overlap artifact), `hl_elite_directional_order_flow`
  (sign flips under cohort perturbation). Declared, and it is why BR-22 carries `crowded_known`.
- **Dropped before carding, recorded so the check is auditable:** *liquidation-level clustering from
  the OI tape* — `do_not_repeat[13] liquidation_heatmap_cascade_predict` is DEFERRED with breadth
  limited to BTC/ETH and a paid CoinGlass dependency, and `lit_liquidation_csd_alarms` confines the
  survivor to **rails-only sizing, never alpha**. *Thin index-constituent mark dislocation* — named
  as live residue by `era_selfref_mark_liquidation_796`, but no index-constituent series exists on
  disk; carried to next ground rather than carded on data the desk does not have. *Fee-concentration
  as its own card* (`top4_share` 0.8589) — folded into BR-21 as motivating evidence instead of
  double-carding, since it shares BR-11's and H1's object.

---

## THE CARDS — two queued, two EV-rejected honestly

All EV scores from `libs.research.alpha_economics.ev_score` (threshold 0.002) on honest inputs, not
tuned. All four logged in `research_memory`, including both rejects. **None of these earns a cent;
a Stage-A pass earns a pre-registered forward clock at most (L1.6).**

| card | mechanism | EV | p | novelty | route |
|---|---|---|---|---|---|
| **BR-21** replenishment half-life as an **ex-ante** cost prior for never-traded names | breaks the L1.45 exclusion cycle | **0.0044** | 0.24 | 0.721 | **R0524**, due 08-26 |
| **BR-19** venue risk-parameter metadata (interval + adjusted cap) as carry conditioning | venue's own risk verdict, published | **0.0029** | 0.48 | 0.691 | **R0523**, due 08-26 |
| BR-20 displayed-vs-traded liquidity ratio as an adverse-selection state | maker display is a revealed expectation | 0.0016 | 0.24 | 0.754 | **EV-REJECTED**, recorded |
| BR-22 wallet-attributed DEX accumulation leads perp funding | on-chain flow is attributable, perp flow is not | 0.0004 | 0.084 | 0.753 | **EV-REJECTED**, recorded |

**BR-19 — the mechanism.** Binance publishes, per symbol, `fundingIntervalHours` (measured live:
**426 of 812 names on 4h**, 384 on 8h, 2 on 1h) and an `adjustedFundingRateCap` (`funding_caps.json`,
747 symbols at ±2%, BTCDOM ±3%). These are set by the venue's risk desk from the full position and
liquidation distribution — information no participant can reconstruct — and the venue is *forced to
publish them* (they are contract terms) and *forced to set them accurately* (its own insurance fund
is the counterparty). A name given a shorter interval or a widened cap is one the venue expects to
run persistently extreme funding. Nobody joins these fields to returns because they read as plumbing
constants; `screen_funding_interval_mismatch.py`'s own docstring notes `fundingIntervalHours` was
"fetched nowhere in this repo". **Falsifier:** within the tradeable carry universe, regress realised
carry PnL / funding persistence / basis-leg damage on interval class and cap class **controlling for
the funding level**; if the parameter adds nothing beyond the level, dead. Cells pre-registered:
2 parameter classes × 3 horizons, DSR-counted. **Strongest argument it is spurious:** the parameter
is assigned *from* historical funding extremity, so it may be a lagged, coarsened copy of the funding
level the desk already ranks on — which the level control is designed to expose.

**BR-21 — the mechanism.** `print_impact.json` established that at $450 notional this desk is a
**spread taker, not an impact maker** (impact 1.6% of cost), so cost is governed by passive placement
and symbol selection. `fee_attribution.json` shows commission is **88.7% of the sleeve's non-funding
loss** and `top4_share` **0.8589** — four names carry it. Whether a passive order fills and whether a
taker order walks is governed by how fast the book **refills**, not by displayed depth at the instant
of the walk. `moat_series.jsonl` already holds `replenishment_halflife` and `withdrawal_rate` for
**93,345 symbol-days** and nothing reads it. **The load-bearing distinction:** realised-cost
predictors (H1, the bleed denylist) are undefined for names never traded, and `n` grows only through
opens — the exact never-traded/never-measured cycle L1.45 names. A book-state predictor is defined
on the whole universe, including names the desk has never touched. **Falsifier:** rank the traded
universe by `replenishment_halflife`, test against realised round-trip bps out-of-sample, and check
whether the four fee-dominant names sit in the predicted bad tail. **Strongest argument it is
spurious:** replenishment and spread are both functions of the same liquidity latent, so the
half-life may add nothing over the half-spread the book walk already prices — the pre-registered
control is the book-walk cost itself.

**The two rejects, reported rather than resubmitted.** BR-20 scores **0.0016** against a 0.002 bar —
a near miss, and it sits precisely in the class F0023/R0038 flagged as under-priced by this gate.
It was **not re-tagged to clear**. The honest response to a gate you have measured as biased is to
report the bias on the row (done, above) and let the arithmetic stand; tuning a card because you know
the gate is wrong is how a bar stops being a bar. BR-22 at **0.0004** is a genuinely weak card: the
*dataset* is new, but the graveyard asks for a materially new **mechanism**, and wallet attribution
is a better instrument pointed at a family the desk has already killed four ways.

**Timidity check.** Four candidates, no cap applied, none shrunk to review easier. Two rejections are
the gate's honest arithmetic on honest inputs. Two further candidate *findings* were killed by the
desk's own records before they reached a card — which is why this run produced two cards and not six.

---

## THE 12-MONTH LITERATURE COMPARISON LOG (run-3 additions)

| id | invented (blind) | one-line mechanism | check-back | literature verdict |
|---|---|---|---|---|
| BR-19 | 2026-08-12 | exchange-published funding interval + adjusted funding cap as a venue-revealed risk classification conditioning carry | 2027-08-12 | _pending_ |
| BR-20 | 2026-08-12 | ratio of print-derived to depth-derived execution cost as a per-symbol revealed adverse-selection expectation (EV-rejected at invention) | 2027-08-12 | _pending_ |
| BR-21 | 2026-08-12 | order-book replenishment half-life as an ex-ante cost prior for never-traded symbols | 2027-08-12 | _pending_ |
| BR-22 | 2026-08-12 | wallet-attributed DEX accumulation leading perp funding (EV-rejected at invention) | 2027-08-12 | _pending_ |

---

## ROUTING

Every queued card is a ledger row with a named owner and a due date, chased by
`recommendations.owed()` until disposed: **R0523** (BR-19), **R0524** (BR-21), **R0525** (the §33
finding). Stage-A screens need no forward slot and are runnable immediately — BR-19 on
`funding_caps.json` + the lake's `funding`/`basis` columns, BR-21 on `moat_series.jsonl` against
`fee_attribution.json`. This seat ran inside its freeze: no screen executed, no `scripts/` or
`libs/` file touched, handoff explicit per R0210(b).

## SUBSYSTEM COVERAGE (L1.0(e))

| Subsystem | Depth | What it produced |
|---|---|---|
| Governance / research process | **deep** | THE FINDING — §33's conversion test is consumer-blind, with the code lines and the cheap fix |
| Data | **deep** | the six-artifact orphan set, verified by consumer-grep; L1.44 registry coverage measured |
| Execution | **deep** | BR-21, BR-20; the spread-taker reading and the fee concentration read as research material |
| Validation / stats | medium | priors corpus rebuilt 231→251; two candidate findings killed on manual cross-check the automated gate passed |
| Portfolio / sizing | shallow | none this run — named honestly rather than padded |
| Risk | shallow | index-constituent residue identified, not carded (no data on disk) |
| Ops / infra | medium | `oi_ls_universe.jsonl` verified as a genuine 2020–2026 panel (256,625 rows, 365 symbols) whose only reader is `max_audit` |

## NEXT UN-EXHAUSTED GROUND (L1.35 — named before closing)

**Sections claimed EXHAUSTED this run:** none.

1. **`data/oi_ls_universe.jsonl` — 256,625 rows, 2020→2026, 365 symbols, read only by a fence.**
   The `oi_ls_liq_forward` clock correctly cannot be filled by history (forward evidence must be
   forward), but a *Stage-A* screen on six years of panel is a different object and nothing blocks
   it. One malformed row carries date `1993` — a data-integrity note, not a card.
2. **Index-constituent series for tail perps** — `era_selfref_mark_liquidation_796` names this as
   live residue and no collector exists. Whoever builds it unlocks the one graveyard-sanctioned
   re-entry on that class.
3. **`data/micro_feature_store.json` as it accrues** — 42 symbols × 27 days of hourly microstructure
   *with* `mid_close`. Checked this run against the graveyard's claim that the `jp_intraday` 1h–6h
   cells are untestable "for want of an hourly lake": **too thin today**, and the claim stands. Re-test
   the blocker when the panel passes ~12 months.
4. **The graveyard's kill-bases as a dataset** — carried from 07-31 and 08-11, **still unmined**, and
   now partly built: a full S/T-classified kill index was constructed as an input to this run and
   discarded with the session. Third naming; it should be an artifact, not a re-derivation each time.
5. **The moat trade tape's aggressor-sequence structure between stamps** (carried from 08-11).
6. **CME `statistics`/`definition` tapes** (carried from 07-31, still untouched at 1.08 GB).

## CLOSE — blunt

**No new tradeable edge was found, and neither queued card is one.** Base rate says perhaps one of
two survives Stage A, and BR-19's own strongest-spurious argument is that it may be a coarsened copy
of a variable the desk already ranks on.

The deliverable is the finding, and it is a governance defect with a measured price: **§33 — the law
written to stop the desk cataloguing without converting — accepts a written file as proof of
conversion.** Six datasets totalling over 100 MB, including 93,345 symbol-days of proprietary
microstructure and 99 fitted impact curves, are creditable as `wired` today and are read by nothing.
The desk hunts orphaned *code* by walking the import graph and has never once asked the same question
of a *dataset*, while its conversion law credits datasets. Runs 1 and 2 both reported idle data as a
symptom; this is the generator, and it is three lines from being fixed by a registry the desk already
built for another purpose.

Fresh eyes in a year should check one thing: whether `[§33: wired]` still means *written*. If it
does, the next run will find a seventh orphan and a fourth restatement of the same finding.

_Session closed 2026-08-12. Ledger rows R0523–R0525. Cards BR-19…BR-22. Next scheduled run:
2026-09-12, or earlier on due-by-state._
