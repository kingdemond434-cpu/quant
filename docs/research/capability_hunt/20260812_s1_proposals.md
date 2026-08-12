# CAPABILITY HUNT PROPOSALS 20260812 slot 1

LENS: DATA ASYMMETRY -- information that could exist ONLY because of how WE combine data (our own-timestamp L2, our execution tape, cross-source joins). What proprietary feature is a competitor structurally unable to buy? (L1.11a: rank by reconstruction cost.)

## A -- Claude family

## THE DEEP PROPOSAL

**MISSING CAPABILITY:** *Estimate execution cost from **other traders' prints**, not just from displayed depth and not just from our own 531 fills.* The recorded tape holds ~48,000 gapless aggTrade prints per symbol per hour — each one a completed execution experiment at a known size and published aggressor side, against the same book we snapshot, paid for by somebody else. Nothing on this desk fits an impact curve to them.

**WHY IT IS INVISIBLE TODAY** — four independent instruments each report green over the gap:

1. **The doctrine has a scope word nobody audited.** L1.11(b) says *"an Execution Reality Model from **our own** fills."* Written to stop the desk trusting a vendor's generic coefficient — correct. Read as *only our own fills count*, which caps n at 531 rows / 73 symbols (`data/moat/execution_tape/`, last real event 2026‑08‑01, 11 days stale) and **permanently excludes every never‑traded name**. `libs/execution/passive_impact.py` encodes exactly two bases, `"counterfactual"` (book walk) and `"own_fills"` (status `UNIDENTIFIED`, `n_with_offset: 0`). There is no third label for *other people's fills* — and that missing label is the entire gap. A third‑party print is not a vendor model; it is realized execution data.
2. **The utilisation meter has no vocabulary for row kind.** `data/moat_utilisation.json` counts symbol‑hours and bytes: `symbol_days_read_pct: 100.0`. Trade rows are the overwhelming majority of Binance row count; the meter cannot distinguish "read the depth rows" from "read the tape." A never‑mined trade half reads as fully consumed.
3. **A fabricated denominator inside the feature‑coverage metric.** `scripts/feature_library.py:159-172` `GRAMMAR` enumerates 6 observables for the liquidity mechanism, **all of them book‑state**. So "% of construction space covered" is computed against a space that excludes the gapless half of the tape by construction — L1.57's exact defect, sitting unfenced inside the desk's own coverage number.
4. **A null read as a dead search space.** `data/moat_survivors.json`: 2,430 triples, `times_survived == 0` for every single one, across 9 mechanisms — **all nine book‑derived, off a 5.25–8.8s poll.** That is L1.25's ordered diagnostic stopping at question 1. Question 2 is *search space*, and the answer was in the same files.

Meanwhile `data/cost_model.json` — **the most‑consumed derivative on the desk, 23 readers** — is produced by `scripts/run_cost_model.py`, which walks displayed depth and reads no trade row at all (grep for `k=='t'` in it returns nothing). It feeds `_rt_bps` → `_net_bps` → the ranking of the *entire* tradeable universe and `_entry_gate` (`run_cashcarry_executor.py:544,859,993`). L1.45 already states in plain words why this cannot work: *"a book‑walk measures DISPLAYED depth in a book that existed WITHOUT OUR ORDER IN IT."* The desk wrote that law, built excitation as the remedy, and left the 10⁶×‑larger observational source untouched because the law said *our own*.

**MECHANISM.** New `libs/research/print_impact.py` + `scripts/fit_print_impact.py` → `data/print_impact.json`, over the existing tested loader `libs/research/moat_microstructure.partitions()` (it already handles both recorder schemas and the `m` aggressor‑sign inversion).

- Per (venue, symbol): bucket prints by signed notional; regress mid‑change over horizons ≥ book cadence on signed size → λ (Kyle), plus permanent/temporary decomposition (mid at t+Δ vs t+5min) and realized spread. Order rows by **receipt**, not raw `t` — Binance depth rows carry our clock and trade rows carry the venue's, so `clock_provenance.sort_key()` is mandatory, not optional.
- Emit a per‑symbol **cost curve over notional**, spanning the desk's actual $65–450 range, for **every recorded symbol including ones never traded**.
- Status values, fail‑loud (L1.41): `MEASURED` / `UNDERPOWERED` (too few large prints) / `UNIDENTIFIED` (size has no variance in the fitted range) / `NO-DATA`. Zero promotion authority — it feeds `cost_model.json` as an additional basis **labelled by basis**, never merged silently, and `_rt_bps`'s existing `max(modelled, realised)` tighten‑only rule stays untouched.

**WHAT IT WOULD HAVE CAUGHT** (this desk's own record):

- **COOKIEUSDT** — 130.47 bps measured pair round‑trip against ~6.7 bps of funding over a 24h hold, 21 opens, ~19× loss per rotation (`run_cashcarry_executor.py:984-991`). The same comment records the mechanism: *"11 of the 16 most-traded names had no measured cost at all."* Every one of those 11 has a public print tape on the venue we were already recording. The curve prices them **before the first open**, with no fill required.
- **NOMUSDT, 2026‑07‑13 dead‑man TRUE fire** — $4,297 opened into a thin book, venue equity −40.9% in five minutes. Displayed depth cleared `_DEPTH_MULT`; the print tape shows what actually happens when a real order of that size hits that book.
- The 7.75× cost/funding ratio, the −51.74 bps execution attribution, and the 88.3%‑fees loss decomposition are all the same wound.

**ROI.** Direct: `cost_model.json` decides *which names the book holds*. On a sleeve whose measured loss is 88.3% cost, moving cost estimation from displayed‑depth‑at‑$500 to a measured impact curve is first‑order, not marginal. Cascade: (a) breaks L1.45's never‑traded→never‑measured cycle at scale — one name priced per fill becomes every recorded name priced per hour; (b) gives excitation a prior so its bounded arm budget targets the least‑identified operating points instead of spreading uniformly; (c) gives R0251 (the 32‑symbol recorder cap silently acting as capacity policy) a real bps number to trade off; (d) makes the gauntlet's cost adjustment measured rather than assumed (L1.5); (e) doubles the screenable feature space at **zero collection cost** — decisive when `data/moat_mine.json` says the recorders auto‑pause on disk in **2.9 days**: the marginal byte should be mined, not written.

**COST.** ~200–400 lines over an existing, tested loader; no new collector, no network, no key, freeze‑safe (read‑only over `data/moat`). Maintenance: one batch job. Competes with the book‑feature screens that have produced 0 survivors from 2,430 triples — and it is the same tape, read the other way.

**FALSIFIER — runnable today, and I would run it first.** The print‑derived curve must predict *our own* realized slippage out‑of‑sample. `execution_tape` carries `spot_slip_bps`/`fut_slip_bps` per leg on 531 rows / 73 symbols; realized round‑trips exist for NOMUSDT (−149), KNCUSDT (−211), COOKIEUSDT (−130.47). If predicted cost at the desk's actual notional has ~zero rank correlation with realized slippage across those names, the estimator is confounded (large prints arrive *because* the book is already moving) and it adds nothing over the book walk — kill it. Second falsifier: if at 5.25–8.8s book cadence λ's per‑symbol CI spans an order of magnitude, it cannot rank names and is useless for `_net_bps`.

**Honest caveat on the asymmetry claim.** Binance aggTrades are refetchable from `data.binance.vision`, so the moat is **not** in owning the bytes — consistent with the desk's own finding that the irreplaceable set is 7.4MB, not 8.7GB. The asymmetry is (a) the join to our own book at our own clock, (b) Bybit's per‑print `isBlockTrade`/`isRPITrade`/`seq`, which **no feature code reads** and which is a free institutional‑vs‑retail label, and above all (c) **caring about the $65–450 tail of the size distribution on ~200 thin perps.** Nobody sells a cost model there because nobody trades there — that is §42 ground, and the reconstruction cost for a competitor is not the data, it is wanting the answer at our size.

**NOVELTY-CHECK:** `grep -rniE "kyle|hasbrouck|amihud|roll_measure|permanent impact|temporary impact|realized_spread|price_impact|vpin" --include=*.py libs/ scripts/` → zero implementations (only a string signature in `mechanism_census.py:447` and literature coefficients in `market_impact_forecaster.py`); `grep -rn "cost_model.json" scripts/ | grep _OUT` → sole producer `run_cost_model.py`, which walks books only; `scripts/calibrate_impact.py` fits sqrt‑impact **from `book_walk`**, and `grep -rn calibrate_impact ops/crontab.manifest ops/*.sh` → **not scheduled**; ledger search for `declin|counterfactual|impact` returns R0267 (passive **fill‑probability** on our own fills, explicitly `own_fills` scoped) and R0251 (recorder cap) — neither estimates taker impact from third‑party prints.

---

## BRAINSTORM (raw generation, not novelty-checked)

**Defects the two sweeps surfaced — highest ROI because they are already broken:**

1. **All three recorders are running stale code** — L1.46's `c`/`E`/`T`/`vt`/`sq` markers landed 2026‑08‑06 (`9853a62`) and appear in **zero rows on disk**; measured cadence 8.81s vs 5.0s configured. Every hour since 08‑06 is unbuyable data recorded without the provenance the desk built to make joins legal. — **S** — `ship_restart.py` + ledger.
2. **Test fixtures are permanently welded into the irreplaceable execution tape** — 5 `OLDUSDT` rows verbatim from `tests/execution/test_carry_entry_gate.py:138` inflate `execution_tape.coverage()["days"]` from 30.69 to **2404.91**, and `libs/risk/capital_events.py:12` names that number load‑bearing. — **S** — ledger + a fence forbidding test symbols in the money‑path tape.
3. **`fill_quality.json`: 0 of 500 rows carry a fee field** on a sleeve whose loss is 88.3% fees. Cost per round trip is UNMEASURED. — **S** — executor writes `commission`/`commissionAsset` per fill.
4. **`data/bybit_l2_samples/bybit_ob200_20250821.zip` (155.8MB)** is a free Bybit publication at **8× depth and 41× resolution** of the 15.6GB tape we record beside it — zero readers. Recording a strictly‑worse subsample of a free file while disk auto‑pauses in 2.9 days. — **A** — retire or re‑aim the Bybit recorder; ingest the free archive.
5. **`data/execution_quality.json` scores the R0334 six components off `conviction_book.jsonl` with `"book": "PAPER"`** — the execution scorecard is not reading the live tape. — **A** — ledger.
6. **`screen_orderbook_state.py` is a pure null run** — 12/12 `NO-INPUT`, pointed at bybit cells whose trade prints it cannot parse; 240 of 38,680 files read. A screen reporting NO‑INPUT 12/12 for weeks is a welded gate. — **A** — fence.
7. **`scripts/screen_moat_microstructure.py` is fully orphaned** — no cron, artifact never existed — and it exists specifically to challenge `run_moat_campaign`'s missing angle‑20 gate after a reported **annualised Sharpe of 97.27** on 2026‑08‑02. The audit of the implausible result never ran. — **S** — schedule it.
8. **`libs/execution/tca.py` and `journal.py` are tests‑only**; SoR `orders`/`fills`/`positions` tables are 0 rows in two 50MB sqlite files. Built‑never‑wired inside execution. — **B** — L2.9 capability audit.
9. **`data/passive_impact.json` (R0267, implemented) has exactly one toucher: its own writer.** The Execution Reality Model's output has no consumer. — **A** — wire into `_passive_price`.
10. **`moat_series.jsonl` (80MB), `upbit_snapshot/` (75MB), `micro_feature_store.json` (5MB) are write‑only** — 160MB of derived state read only by its writers. — **B** — L2.9.

**Measurement / instrument gaps:**

11. **Moat utilisation should be measured in ROW KINDS, not bytes** — depth vs trade vs meta, each with its own read‑coverage ratchet; today one number hides a 50% blind half. — **A** — `moat_utilisation.py`.
12. **`feature_library.GRAMMAR` needs trade‑tape observables** (signed flow, VPIN, λ, run‑length, size distribution) or its coverage % is a fabricated denominator under L1.57. — **A** — fence.
13. **Bybit's `isBlockTrade` / `isRPITrade` as a free institutional‑vs‑retail conditioning variable** — split every microstructure feature by counterparty class; a mechanism that only works against retail flow is a different (and more durable) claim. — **A** — axis watchlist.
14. **Δ = t_recv − t_venue has zero non‑test consumers** — measured as a data‑quality statistic, never screened as a venue‑load axis. Exchange dissemination latency spikes under matching‑engine stress; the desk polls Binance constantly and discards every reading. — **B** — axis watchlist.
15. **`data/BINANCE_BAN_UNTIL` is a LATCH, not a LOG** — it holds one line (`code=429 retry_after=9`, today 09:37) and overwrites. Every prior rate‑limit event is destroyed. Same defect class the desk already named in L1.47 (*"a flag computed and dropped is evidence destroyed at zero saving"*), never generalised. — **A** — append‑only venue‑state series.
16. **Venue API health as a counterparty‑risk series, not a pipeline‑health verdict.** `source_health.py` asks "is our collector working"; nobody asks "what is the venue telling us about itself." The whole live book is on one counterparty, and on 2026‑07‑31 a venue‑side 418 crashed every close‑all tick — a survival‑rail failure caused by venue state we do not trend. — **A** — new fence + axis.
17. **A daily survivorship‑free universe snapshot** (`exchange_filters()` ∪ `current_funding()` symbol sets, stamped) — the desk already computes this every tick and throws it away; venues purge delisted history (Upbit erased a treatment group; 4,455 dead names). Unbuyable once gone, and survivorship bias *manufactures* phantom edges. — **S** — cheapest irreplaceable series available.
18. **Vintage archive beyond circulating supply** — TVL, unlock schedules, OI history, market‑cap rank are all silently restated; `pct_circ_now` already produced a look‑ahead in a conditioning variable. PIT supply started 5 days ago; the others have not. — **A** — collector.
19. **No fence asks "did a historical value CHANGE?"** — L1.44 asks age, L1.46 asks which clock, L1.55 asks whether inputs were readable. A silently revised past value passes all three green. — **A** — new fence.
20. **Screen‑score vs forward‑outcome correlation across all 19 forward clocks** — the desk has never measured whether its own Stage‑A screen predicts its own Stage‑B results. If ρ≈0 the bottleneck is screen design, not sample size, and every Stage‑A hour is waste. UNDERPOWERED is a valid and informative answer. — **S** — validation.
21. **Price the entry gate under L1.51** — it is the desk's largest clamp and structurally unpriceable today (it redirects rather than idles capital, so `check_idle_cost.py` cannot see it). Needs the decision tape that gap rows 105/106 already own. — **A** — feed `decision_ledger.jsonl` from the executor.
22. **`_rt_bps`'s pessimistic default is a third L1.45 exclusion cycle** — unmeasured → pessimistic → never ranked → never traded → never recorded → never measured. The docstring calls it a feature. Ask of every exclusion: what is the path back? — **A** — the print‑impact curve above is the path back.
23. **`build_bars.py` reads 0.9% of partitions, spot only, 3 days stale** — 18.3GB → 253KB. Bars are the input universe of the entire candidate generator. — **A**.
24. **Candidate generation is daily‑bars‑only** — `generators.py`'s 12 families all take OHLC; `data/lake/bronze/` contains no microstructure dataset at all; the moat lives outside the lake and nothing in the alpha pipeline reads any moat artifact. The four microstructure screens are isolated cron lines writing to files no candidate path opens. — **S** — this is the structural reason the tape yields nothing.
25. **`stage_a_screen` is horizon‑agnostic and supports 60s bars** — the harness is not the constraint; every caller is. Intraday screening is one adapter away. — **A**.

**Estimator / power ideas:**

26. **VPIN and order‑flow toxicity from the gapless print tape** — pure trade‑tape, no book‑cadence penalty, zero implementations. — **A**.
27. **Trade‑sign autocorrelation and aggressor run‑length** as a crowding/informed‑flow axis — free, direction‑agnostic (the desk's only repeat survivor class is direction‑agnostic). — **B**.
28. **Realized spread vs effective spread per print** = the market maker's revenue; its collapse is a liquidity‑withdrawal early warning that the 5s book cannot see. — **B**.
29. **Book resiliency (post‑print depth recovery half‑life) at print resolution** — `replenishment_halflife` exists but returns one scalar per file and is excluded as `SCALAR-NOT-SCREENABLE`; the print tape makes it a proper series. — **B**.
30. **Excitation needs an OFFSET arm** — `passive_impact` refuses `own_fills` because the executor quotes at the touch on every order, so placement offset has zero variance. `excitation_design.json` varies only `maker_wait_s`. One arm unblocks the Execution Reality Model. — **S** — smallest unlock on the list.
31. **Cross-venue print‑time lead‑lag using receipt ordering** — R0117 rests on a false premise (8.28s vs 4.32s pollers, no shared trigger); the *trade* tapes are event‑driven and gapless, so the lead‑lag question is answerable there even though it is not answerable on the books. — **A**.
32. **Funding‑settlement phase joined to the print tape** — L1.47 measured that 22.3% of closes walk within an hour of a payment; the print tape says whether the book is systematically worse in that window (i.e. whether the phase edge is capturable or is just other people's flow). — **B**.
33. **Positive control on the microstructure screen** — plant a known‑good intraday signal and confirm the moat gauntlet can pass it. 2,430/0 has never been shown to accept anything (the desk's own `certify_gauntlet.py` lesson, unapplied here). — **S**.
34. **Power‑correct the null**: `reports/moat_campaign.json` reports `power_at_target 0.050`, `hurdle_annual_sharpe 8.29`. A hurdle of 8.29 Sharpe is a wall, not a bar (L1.49). Fix the design; never the threshold. — **S**.
35. **n_eff, not observation count** — gap row #100 already names two organs that derived authority from sampling frequency. Any intraday expansion must deflate by autocorrelation up front or it recreates the defect at 48,000 rows/hour. — **A** — pre‑registration rule.
36. **Cross‑language first‑appearance diffusion clock** — the desk mines KR/JP/RU/CN/BR/AR daily; stamping first‑observation per item per language builds a lag series nobody sells. Announcements already carry `first_seen`; forum mining does not. — **B**.
37. **A meta‑model over the graveyard** — 434 rejects with continuous OOS statistics (not just the degenerate 0/1 label) → which mechanism families are worth screening. Raises discovery rate per compute unit. — **B**.
38. **Lens‑yield measurement for the 8 exploration lenses** — rotation is deterministic and attributable, so yield is measurable and an unproductive lens is retirable by evidence; nothing computes it. — **B**.
39. **Disk is the binding constraint in 2.9 days and nothing prices the trade‑off** — recording a 4th venue vs mining the tape vs deleting Bybit's 85%‑of‑bytes‑for‑9.6%‑of‑rows stream. That is an L1.13 bottleneck decision with no number attached. — **A**.
40. **Compress the tape by row kind** — Bybit depth at 25×2 levels is 85.3% of bytes; storing depth diffs instead of snapshots buys weeks of runway for free and is pure L1.28a headroom. — **A**.
41. **A cycle detector for exclusions** — L1.45's defect was a *cycle*, and every fence walks nodes and edges. Three instances are now on the record (recorder universe, bleed denylist, `_rt_bps` default). A generic "what is the path back?" checker over every exclusion list. — **A**.

*Context is fine; stopping here for output length, not for lack of seam.* Next I was about to draw the **negative-exemplars** lens (#4) against the single‑counterparty concentration — specifically: which of FTX's, Alameda's and Archegos's death signatures this desk would currently not detect, given that its entire book, its kill path, its price feed and its cost model all terminate at one venue, and that its only independent read on that venue is a 429 code it overwrites.

*Read-only throughout — nothing was modified.*


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 402: Payment Required. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
