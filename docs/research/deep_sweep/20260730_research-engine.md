# DEEP COLD AUDIT — RESEARCH-ENGINE — 2026-07-30

_Auditor: Claude Opus 5. **Provenance, corrected mid-run:** this IS the scheduled auditor — the
20260730T1200 catch-up window, position 7 of 8. `ps -eo pid,lstart,cmd` shows PID 1362655
`claude --effort max --append-system-prompt "THE CONSTITUTION GOVERNS..."` started 12:00:07Z, and
`data/cro_ai_logs/deep_sweep_20260730T1200.log` ends on the bare line `auditor: research-engine`
with no verdict. My own first draft of this header claimed "interactive retry run"; that was wrong
and is left visible here as a specimen of the exact defect this audit hunts — an organ's
self-description is not evidence of its provenance. Read-only. Every claim carries its proving
command output. Written incrementally per the COMPLETION CONTRACT — if this run is cut off, what
is below is the deliverable._

**Headline: the research engine's generation stage produced ZERO new hypotheses on each of the
last 6 days; its "information value" instrument is an algebraic constant; and the audit organ that
should have caught both has never once completed a run — because its own success test measures
BYTES.**

## SCORES

- **current_capability_pct: 30%.** Split, because the average hides the shape: *screening* runs at
  ~80% (K-1, the best component on the desk), *record-keeping* at ~75% (K-2, rich rows), *judgment* at
  ~85% (K-4/K-6, the GAP re-rank and the panel overturns), but *generation* at **~5%** (0 new
  hypotheses/day for 6 days, LLM generator never run once), *knowledge reuse* at **~5%** (0% gate
  recall, 3 reader-zero stores, 96% of refutations invisible), *non-English reach* at **~10%** (4.3%
  of URLs, 0 translation code, 5/7 miners silently dead), and *remediation* at **~13%** (6/46
  recommendations implemented). A research engine is a chain; it is worth its weakest link, and two
  links are near zero.
- **practical_ceiling_estimate: 85%.** Bounded by two things that are genuinely hard, not by effort:
  one quota-limited LLM seat, and calendar-time forward-clock accrual (`needs_days: 40`) which no
  compute compresses.
- **ceiling_gap: 55 points** — and critically, **the top 5 opportunities are all LOW-to-MEDIUM
  complexity**. This is not a gap that needs new science. O-1 wires two things that both already
  exist; O-4 is ~20 lines the desk already scoped; O-7 is a `shlex.split` and a timeout constant.
- **opportunity_cost_1y: SEVERE.** Concretely, not rhetorically:
  - **Generation:** 0 new hypotheses/day from the only quota-free engine × 365. The counterfactual is
    not speculative — the desk measured it: 420 price hypotheses → 0 survivors, versus one new axis
    screened in ~1 hour producing the best IC ever recorded here.
  - **Waste:** ≥5.9% of lifetime experiments (25/424) provably spent on graveyarded ground, and 43%
    (186/434) duplicate triples in the generator's own store. That waste inflates the multiplicity
    denominator, which is the mechanism currently making the promotion gate a ~100% veto — **so the
    duplicate work is not merely wasted, it is actively suppressing real candidates.**
  - **Audit:** 4 of 4 sweeps of the self-designated "highest-return section" lost, ≈1 month of the
    desk's own best diagnostic instrument.
  - **Frontier:** 8 sources that answer HTTP 200 today never queried; 4 doctrine-named languages at
    literal zero; the highest-conversion channel (repo mining, K-5) has zero CN coverage.
  - **Compounding:** 27 undisposed recommendations at a 13% implementation rate. If diagnosis
    continues to outrun remediation at 46:6, every future audit — including this one — has an expected
    realised value near zero. **That is the compounding cost that dominates all the others.**
- **confidence: 0.9.** Nearly every finding is a deterministic command output, not an inference: the
  0/43 recall test, the 6-day `tested=0` log, the reader-count greps, the four-decimal IC match on the
  re-run netflow screen, the `recommendations.py report` output. Lower confidence (~0.6) on the
  *magnitude* of forgone alpha, since 0 survivors in 424 trials is also consistent with "there is
  little edge in the explored space" — which is exactly why O-2's honest sell is discovery rate, not
  a promised edge.
- **unknown_unknown_score: 0.75 (HIGH).** Justified by base rates I measured rather than by modesty:
  3 of 3 stores I checked had zero readers; 3 of 3 freshness guards I checked measured mtime/bytes
  instead of content; 3 independent routes found the same self-greening shape; 1 file read revealed a
  dead lever replicated in 5 runners. Each pattern was found by spot-check, and each spot-check hit.
  **T-5, T-6 and T-7 exist precisely to convert this score into a count.**
- **info_gain_if_investigated: VERY HIGH for T-1/T-2/T-5.** T-1 is a deterministic experiment whose
  answer changes a mandatory gate. T-2 produces a number the desk currently **cannot state at all**
  (its own duplicate-trial rate) and which feeds directly into the DSR bar. T-5 generalises the
  single largest finding in this report from 3 stores to all of them.
- **expected_alpha_contribution: HIGH but indirect.** Nothing here is an edge. O-1+O-2 together are
  the only path from 0 hypotheses/day to a non-zero validated-discovery rate, and O-1 additionally
  *raises the pass probability of every genuine candidate* by removing duplicate trials from the
  multiplicity denominator. Direct contribution: none. Indirect: this subsystem is the sole source of
  all future alpha, and two of its links are near zero.
- **expected_compounding_contribution: VERY HIGH.** O-1, O-2, O-3 are all flagged ⚡. O-3 in
  particular raises the value of *every* future experiment by making it retrievable — the difference
  between 152 rows of institutional memory and 152 rows of institutional trivia.
- **CEILING EXPANSION — what defines the 85%, and what would move it?** The ceiling is set by
  **two assumptions, one real and one merely historical**:
  - *Real:* forward-clock accrual is calendar-bound (40+ days). Unmovable by compute. It does,
    however, argue hard for **maximising the number of clocks running in parallel** — which loops back
    to `MAX_FORWARD_SLOTS=12` and the unreconciled slot count in T-4. If the true occupancy is 3 and
    not 12, the ceiling is being self-imposed by a bookkeeping error.
  - *Merely historical:* "one quota-limited seat" is treated as a hard wall, and it is not. The desk
    already owns sklearn, numpy and scipy and **already wrote an IDF-cosine retriever** — so
    retrieval, dedup, screening and prioritisation can all run at zero marginal quota cost. Every one
    of those is currently either LLM-gated or hand-run. The honest statement is: **the seat is scarce
    and the deterministic compute is free, and the desk has been spending the scarce one on work the
    free one can do.** Moving that boundary is what lifts the ceiling, and no measurement of where it
    currently sits has ever been taken.
  - A third, softer bound: the doctrine's own 38.3k-char preamble on every call (R-26) means the
    scarce resource is partly spent re-reading instructions. Compression is a ceiling-lift, not
    hygiene.

## 1. WHAT WE KNOW (validated strengths, each with its proving command)

**K-1. The Stage-A screen harness is statistically serious and is the desk's single best asset.**
`python3 -c "json.load(open('data/idle_axis_screen.json'))"` → per-construction trial rows with
`n_eff`, `min_detectable_ic`, `powered`, `residual_ic`, de-contamination flags, explicit
`SCREEN-UNDERPOWERED` verdicts, and stage marked `"A (zero promotion authority)"`. Power analysis
*before* belief. It has caught Coinbase-premium and Turkey-premium as pure timing artifacts and a
sign-flip on exchange netflow that, per commit `b3c0a56`, "every other heuristic called an edge."
Keep unconditionally (R-30).

**K-2. Negative results genuinely dominate the record — the graveyard doctrine is executed, not
aspirational.** `research_memory`: 152 rows, `failure=124, success=17, pending=5` — a 7:1
failure:success logging ratio. Row quality is high: `lessons 146/150`, `failure_cause 110/150`,
`metrics_json 150/150`, mean statement 268 chars (R-8, with a real sample).

**K-3. Preregistration with honest EV gating exists and rejects the desk's own ideas.**
`head docs/research/AXIS_PREREGISTRATIONS.md` → 11 axis hypotheses with mechanism, falsification
condition, EV and p_survive; **11/11 honestly REJECTED below threshold** rather than tuned to pass.

**K-4. The GAP register works, is re-ranked on time, and self-corrects.** Stamp
`_Re-ranked 2026-07-30T07:35Z_`; 89 rows; the re-rank prose records a deliberate non-advance with its
measurement and retracts its own earlier finding F0007 by name (R-31). This is the proof that the
desk's judgment is sound and its bottleneck is throughput, not discernment.

**K-5. Repo mining converts end-to-end.** `docs/REPO_EXTRACTION.md` Tier-1: 5 adopted repos → 5 named
wired modules (`libs/backtest/queue_fill.py`, `libs/research/microstructure.py`,
`libs/research/stationarity.py`, triple-barrier labels). The only mining channel with verifiable
artifact→module→use conversion (R-22).

**K-6. The external panel produces real adversarial overturns.** `docs/research/panel_rulings.md`:
a 12/12 near-unanimous pushback correctly overturned a CRO first-pass loss diagnosis; a proposal to
relax a regime gate into a haircut was rejected on the explicit ground that it "effectively LOOSENS a
validation gate -- HARD line" (R-27).

**K-7. Reporting culture is honest under pressure.** `ZERO survivors net-of-cost (honest).` is printed
by the factory itself; `verdict_hint` refuses to endorse scaling ("Do NOT rent hardware yet"); the
litminer's own closing commit reads *"net new tradeable axes: ZERO"*. The desk does not dress up
nulls. **This is why the findings above are findable at all** — nothing was hidden, only unread.

**K-8. Free-tier tooling that works, works.** `fetch_video_transcript.py dQw4w9WgXcQ` →
`[transcript via https://api.piped.private.coffee] 2089 chars`, live today. The free-first protocol
produced a genuinely working YouTube caption path (R-20 — Bilibili half unproven).

## 2. WHAT WE DON'T KNOW (ignorance ledger)

**Known-unknowns, each with why it is unknown:**

1. **How many times the daily netflow re-screen has actually fired.**
   `collect_coinmetrics_flows.py:244` calls `_screen_all()` unconditionally every morning, but
   `data/batch_coinmetrics_screen.json` is overwritten and `data/*` is gitignored (`.gitignore:11`).
   The evidence of repetition destroys itself. **We cannot count our own duplicate trials.**
2. **The true forward-clock count.** `north_star.forward_tested = 0` vs `web/discovery.json` showing
   3 pending vs `MAX_FORWARD_SLOTS=12` claimed full at 12/12 (R-14). Three representations, no
   reconciler. This is the denominator of the Holm correction on the only path to capital.
3. **Whether failed auth pings consume session quota.** ~1,900 dead probes
   (`owed=deep_sweep quota=DEAD` × 640) and no per-request accounting exists on this box.
   `quota_watch.log` is 0 bytes (R-6i).
4. **The complete novelty-verdict history.** 9 verdicts are all that survive; `reports/` is gitignored
   and screen artifacts overwrite in place. `idle_axis_screen.json`'s stale `n_priors: 40` proves at
   least one earlier run existed with a different corpus (R-24).
5. **Whether the 07-26 EN/CN digs produced anything.** `data/cro_ai_logs/` oldest file is 07-28 20:37;
   pre-07-28 organ logs are gone and no rotation config exists. Two 24-28 minute digs are
   unrecoverable (R-17).
6. **Whether the weekly `0 4 * * 0` deep-sweep cron has ever fired.** Its redirect target
   `data/cro_ai_logs/deep_sweep.log` **does not exist**, yet reports exist. Every traceable sweep was
   started by `organ_catchup`, not cron.
7. **Whether the litminer/prospector/dataaxis timers ever succeeded before 07-25.** `journalctl`
   returns "No entries" for all three across all boots (R-17).
8. **What `hypothesis_generator.py`'s dedup would do.** Never executed, so its accept rate is
   unmeasurable rather than unmeasured (R-25).
9. **Whether Bilibili captions are obtainable at all.** 0/3 on real popular BVids; the doctrine
   asserts it works (R-20). Unknown whether this is video-selection, API-surface, or capability.

**Suspected unknown-unknowns (where confidence is lowest, deliberately probed):**

- **Other stores with zero readers.** I proved 3 write-only stores by grepping 3 filenames. There are
  ~60 files in `data/*.json`. **A systematic writer/reader census across every artifact has never been
  run**, and the three I checked were 3-for-3 dead. The base rate suggests more.
- **Other self-greening `ok: True` paths.** R-5 (naver), R-17 (frontier rotation `|| echo`), R-4
  (unread `steps_ok`) are three instances of one shape found by three different routes. No repo-wide
  audit of "returns success on missing precondition" exists.
- **How many other computed-then-discarded variables exist.** `_MINE_PRIORITY` is dead in **5**
  runners (R-18). That pattern was found by reading one file. Nobody has grepped for
  assigned-never-interpolated shell variables.
- **Whether any organ's *content* has silently degraded.** Every freshness check on this desk is an
  mtime or a byte count (R-6c the 1200-byte floor, R-2.4 `pilot.json`, R-27b `panel_rulings.md`).
  Three of three content-vs-mtime checks I ran found a divergence. **We have no content-drift
  detection anywhere.**

## 3. WHAT COULD MATTER MOST (ranked opportunities)

Ranked by expected impact × confidence ÷ (cost × maintenance). **⚡ = compounding multiplier** (raises
the value of every future improvement). Every item names the higher-ERV alternative it displaces per
L1.14.

---

### ⚡ O-1. Point the existing TF-IDF cosine at `research_memory`; retire the Jaccard gate. **[Rank 1]**

- **Exactly what:** replace `_similarity` in `libs/alpha_factory/hypothesis_novelty.py` with the
  IDF-weighted cosine already implemented at `scripts/knowledge_engine.py:80-99` (or
  `TfidfVectorizer(analyzer='char_wb', ngram_range=(3,5))` — sklearn is installed). Build
  `PriorIdea` rows from **`research_memory` (152 rows) + graveyard (43) + research_candidates (505)**
  instead of graveyard-only. Emit `data/graveyard_priors.json` as the one canonical machine
  graveyard. Calibrate the threshold on the labelled positive control from R-23.
- **Why:** the gate is mandatory doctrine and has **0/43 recall on verbatim graveyard entries**, a
  100% accept rate over 9 lifetime verdicts, and a threshold that is arithmetically unreachable for
  70-94% of prior pairs. It reads 7.2% of the record. This is the mechanism by which R-10 happened and
  will happen again — re-run the gate today on exchange_netflow and it returns `0.918 novel`.
- **Evidence:** R-23, R-24, R-28 (recall test, unreachability table, 100%-accept histogram, the
  `grep` proving no caller builds priors from `research_memory`).
- **Expected benefit:** eliminates the largest *silent* waste channel in the engine. Directly
  measured waste already: 12+4 netflow cells + 9 `try_premium` cells on a graveyarded axis = **25 of
  424 experiments (5.9%)** provably spent on dead ground, plus **186/434 (43%)** duplicate triples in
  the generator's own store, plus **19 pairs in the desk's own record at or above its own redundancy
  bar**. Every one of those inflates the multiplicity denominator that makes real edges unpromotable.
- **Complexity:** LOW. Both halves exist; this is wiring plus a threshold calibration. ~1 day.
- **Dependencies:** none new (sklearn/numpy/scipy present). Benefits from O-3 but does not need it.
- **Validation method:** the R-23 positive control is the acceptance test — **recall on 43 verbatim
  graveyard names must exceed 0.90** at a threshold whose false-positive rate on the 11
  `AXIS_PREREGISTRATIONS` (known-distinct) hypotheses stays under 0.10. Report the full histogram, not
  a single number, per GATE-OPTIMALITY DUTY.
- **Failure modes:** (a) over-blocking legitimate horizon variants — R-23 cause 3 shows Jaccard
  already scores 5d-vs-20d at 1.000, so char n-grams *reduce* this risk, but the 5d/20d pair must be
  in the negative-control set; (b) IDF instability at n=152 — mitigate with add-one smoothing;
  (c) a *tighter* gate slows generation, which is fine at the current rate of 0/day but must be
  re-checked once O-2 lands.
- **Alternatives considered:** local embedding model (better on paraphrase, needs a download + CPU
  budget — do it *after* the lexical baseline is measured, so the gain is attributable);
  LLM-as-judge (best quality, spends the bottleneck resource — reserve for the ~50 nearest lexical
  candidates only); raising the Jaccard threshold (**rejected** — arithmetically unreachable, so no
  threshold fixes it).
- **ROI:** highest in this report. Confidence **0.95** (the recall test is deterministic and I ran it).
- **Interactions:** merges the two forked gates (R-24) — `alpha_lifecycle.py`'s `_DEAD_MECHS` family
  filter should be *kept* and folded in, since it correctly flagged `M_FLOW_PRESSURE` two days before
  the netflow screen ran.
- **Maintenance:** low; corpus grows automatically from `research_memory`.
- **Monitoring:** log every verdict append-only (not overwrite-in-place — R-24's stale `n_priors: 40`
  and the destroyed netflow history are both artifacts of overwriting). Alert if the accept rate
  exceeds 0.95 or falls below 0.30 over a 20-verdict window.
- **Retirement condition:** retire if, over 50 verdicts, the gate's rejections show no measurable
  reduction in duplicate trials — i.e. if duplicate-triple share does not fall from 43%.
- **Horizon:** 1w wiring; 1m the first duplicate prevented; 3m a clean multiplicity denominator;
  1y the difference between a real edge promotable and not.
- **Displaces:** nothing. It is cheaper than every other item here and unblocks three of them.

---

### ⚡ O-2. Give the generator new mechanisms — or admit generation is 0/day. **[Rank 2]**

- **Exactly what:** extend `libs/autodiscovery/generators.py` beyond the 6 price families to the
  non-price axes already ingested and sitting idle (OI, long/short, liquidations, basis, stablecoin
  flows, DeFi utilisation, FRED macro, exchange netflow, order-book depth). Gate each new generator on
  a **stated mechanism prior**, per SCREEN-ON-DISCOVERY point 2.
- **Why:** `tested=0` for **6 consecutive days on both timeframes** (R-1). The desk's only
  quota-independent discovery loop contributes zero. `ops/run_crypto_factory.sh:8-15` pre-authorises
  this as "EXPECTED, not a failure" and names the lifting condition ("NEW mechanism generators") —
  which nobody owns. 6 of the 7 existing families are price-only, in a space the desk has already
  measured at 420 tested / 0 survivors.
- **Evidence:** R-1 (6-day log), R-2 (`distinct_families: 1` forever; 0 H8 rows ever), R-15 (40/40
  schedule items are one mechanism), R-25 (43% duplicate triples).
- **Expected benefit:** the *only* route from 0 hypotheses/day to non-zero without spending quota. The
  desk's own comparison is stark: 420 price hypotheses → 0 survivors, vs one new axis screened in
  ~1 hour producing the best IC the desk has ever recorded.
- **Complexity:** MEDIUM per generator (~0.5–1 day each), and it is *incremental* — one new generator
  is a shippable unit.
- **Dependencies:** O-1 strongly recommended first, so new volume does not re-draw dead ground.
- **Validation:** `tested > 0` in the next cron run, `distinct_families > 1` in
  `information_value.jsonl`, and every new cell carrying a `mechanism` field.
- **Failure modes:** volume without mechanism priors is breadth-mining the 420/0 result already
  refuted — the mechanism-prior gate is **not optional**; and new families must register trials in
  `trials_ledger` (currently 0 rows) or they inflate multiplicity invisibly.
- **Alternatives:** rent CPU (**rejected by the desk's own instrument** — "the constraint is
  DATA/MECHANISM, not volume"); wait for forward clocks (that is the current state, and it is 0/day).
- **ROI:** very high. Confidence **0.85** on "moves tested off 0"; **0.35** on "produces a survivor"
  — and that asymmetry is the honest sell: this buys *discovery rate*, not a promised edge.
- **Interactions:** raises load on the screen harness (fine, it is the strong component) and on the
  multiplicity budget (which is why O-1 and `trials_ledger` come first).
- **Maintenance:** medium — each generator is code that can rot. Mitigate by requiring each to write
  a dated artifact.
- **Monitoring:** alert on `tested == 0` for 2 consecutive runs. **This alert does not exist today,
  which is why 6 days passed unremarked.**
- **Retirement:** retire an individual generator whose family reaches ~130 trials with 0 survivors
  (the desk's existing family-kill precedent).
- **Displaces:** breadth-first source hunting (O-6). Justified: a new *source* with no generator to
  consume it becomes idle data, which L1.8 calls a defect — and the desk already has 8+ ingested
  idle axes.

---

### ⚡ O-3. Make research memory readable: one canonical prior store + a read path that blocks. **[Rank 3]**

- **Exactly what:** (a) a `priors` module that materialises `research_memory` + graveyard +
  candidates into one queryable store; (b) a CLI on `knowledge_engine.py` (it currently has
  **no argparse at all**) so any organ can ask "has this been tested?"; (c) populate `predecessor_id`
  so lineage exists; (d) write resurrection *outcomes* back to the queue.
- **Why:** three stores have **zero readers** (`graveyard_resurrection_queue.json`,
  `negative_knowledge.json`, `knowledge_engine.json` — one code reference each, the writer's output
  path). `research_memory`'s 152 rich rows are read as `COUNT(*)` twice and one JSON key once. 96% of
  recorded refutations are invisible to every dedup mechanism. `predecessor_id` is 0/150.
- **Evidence:** R-8, R-11, R-12, R-13.
- **Expected benefit:** ⚡ this is the substrate O-1 reads, the corpus O-2 must avoid, and the only
  way cross-domain synthesis ever becomes possible. It converts a 152-row asset from a counter into
  a tool.
- **Complexity:** MEDIUM (~2-3 days). The schema is already right; this is a read layer.
- **Validation:** `knowledge_engine.py --query "<text>"` returns the correct prior for ≥90% of the 43
  graveyard names; the resurrection queue no longer lists `multilingual_wikipedia_attention` and
  `defi_health` as `priority 5 / PRIME RESURRECTION` after their 0/96 result.
- **Failure modes:** a read path nobody calls is the *current* state — so this item is only complete
  when at least one production caller **blocks** on it. Ship the caller in the same PR.
- **Alternatives:** keep hand-run `research_memory.py report` (current state — invisible to code,
  blocks nothing).
- **ROI:** high, compounding. Confidence **0.9** on buildability, **0.6** on adoption (adoption is
  the historical failure mode here — cf. `libs/alpha_factory`, built and never called).
- **Monitoring:** count reads per store per week; **a store with 0 reads for 14 days is a defect**,
  which is exactly the check that would have caught all three dead stores.
- **Retirement:** retire any store still at 0 reads 30 days after the read layer ships — that is
  evidence it should be deleted, not fixed.
- **Displaces:** building any *new* metadata store. There is no case for another writer.

---

### O-4. Fix the sweep runner: rotate seats, synthesis-first, content-not-bytes, streak alarm. **[Rank 4]**

- **Exactly what:** inbox item **#74**, already written and costed at ~20 lines — `start seat =
  week# mod 8`; guard synthesis on `synth.exists()`; add a per-auditor failure-streak alarm; and
  **replace the 1200-byte `ok` test with a content test** (e.g. reject if `TBD`/placeholder count
  exceeds a threshold, or require all four output headings non-empty). Also: honour
  `brain_env.sh`'s opus-first chain instead of overriding to fable-first, and wait for the reset
  timestamp the CLI already prints instead of burning 5 auditors in 36 seconds.
- **Why:** research-engine is position 7 of 8 in a never-rotated sequence that restarts at position 1
  every UTC midnight, completing ~2.1 auditors per window. It has produced 0 complete reports in 4
  sweeps. On 07-29 a 3,380-byte skeleton scored `OK` and **blocked its own retry** for the rest of the
  only day the sweep ever completed. Four consecutive deaths were invisible: the only consumer of the
  `AUDITOR FAILED` marker is the writer, and `max_audit.py:1510` excludes the directory.
- **Evidence:** R-6 (a)-(i), all command-cited.
- **Expected benefit:** the highest-ERV auditor stops being structurally starved. Meta-benefit: every
  future finding in this section depends on this organ running.
- **Complexity:** LOW (~20 lines, self-estimated by the desk).
- **Validation:** two consecutive sweeps in which research-engine produces a >20KB report with zero
  `TBD` scores; a deliberately-injected stub must **fail** the content test.
- **Failure modes:** rotation could starve `alpha-discovery` instead — mitigate by rotating rather
  than reordering, so starvation is uniformly distributed and *measured* per seat.
- **Alternatives:** run the sweep less often with more windows (does not fix the ordering);
  buy a second seat (**a paid answer to a free problem** — rotation is free and untried, so per the
  FREE-FIRST protocol this cannot be proposed yet).
- **ROI:** very high per line of code. Confidence **0.9**.
- **Interactions:** the content test will re-open ~6 previously "passing" skeleton reports for
  re-run — that is the correct outcome and should be expected, not treated as a regression.
- **Monitoring:** append a per-auditor JSONL outcome record (none exists today) and alarm at streak
  ≥2. **Retirement:** never; this is the audit organ's liveness.
- **Displaces:** nothing meaningful. It has been diagnosed twice and unlanded for 4 days (R-16).

---

### O-5. Dispose the 27 open recommendations before generating one more finding. **[Rank 5 — and the honest bottleneck]**

- **Exactly what:** work `scripts/recommendations.py` to zero undisposed rows. R0004 (novelty→live
  generation, = O-1) and R0008 (`trials_ledger` 0 rows) first — both 4.0 days overdue. Then R0030,
  R0033, R0034 (gate-optimality), R0002 (doctrine bloat, = R-26).
- **Why:** 46 total / 6 implemented (13%) / **27 open, ~25 flagged DEFECT past grace**. §41 is
  explicit that this is a defect state, not a backlog. Two of the overdue rows are verbatim the fixes
  for this sweep's two largest findings.
- **Evidence:** R-16 (full report output), R-6g (inbox #74 unlanded), R-26 (doctrine grew 42% while
  its ticket sat overdue), R-31 (53 open : 8 closed in the GAP register).
- **Expected benefit:** this is the desk's **binding constraint per L1.13**. The diagnostic capability
  demonstrably exceeds the remediation capability, so the marginal ERV of another finder — another
  audit, probe, or battery — is near zero while 27 correct diagnoses sit undisposed. **This audit
  itself is subject to that judgment.**
- **Complexity:** variable, but disposition is cheap: implement, reject with a substantive reason, or
  schedule with an enforced due date. **A reasoned rejection is a disposition.**
- **Validation:** `recommendations.py report` shows 0 rows past grace.
- **Failure modes:** mass-rejection to clear the queue. Guard: rejections need substantive reasons and
  the implemented:rejected ratio should be reported, since a kill-share above the bar is itself a
  §33-style defect.
- **ROI:** highest *organizational* ROI in the report. Confidence **0.99** on the diagnosis; the
  uncertainty is entirely about will.
- **Monitoring:** already built and already firing. Nobody is reading it — which is the finding.
- **Displaces:** **this audit's own successors.** Stated plainly: if the next cycle must choose
  between running another cold sweep and disposing these 27 rows, it should dispose the rows.

---

### O-6. Query the eight reachable, never-touched frontier sources; add TR/ES operators. **[Rank 6]**

Gitee, Feixiaohao, Xueqiu, Qiita, Zenn, velog, smart-lab and cyberleninka all return **HTTP 200 from
this box today** and have never been queried (R-19). Turkish and Spanish have **zero** operator
adaptations. Baidu Tieba is recorded in `docs/graveyard.md:94` as "unreachable" when it is **403
bot-blocked** — a factual error that `OP-026`'s paywall-substitute ladder already addresses. Under the
FREE-FRONTIER law "no free source exists" requires a *documented failed search*; several of these are
recorded in desk docs as *"NOT DONE THIS RUN"* going back to 07-19. **Gated behind O-2** (a new source
with no generator becomes idle data). CN repo mining ranks first inside this item, because repo mining
is the desk's highest-conversion channel (K-5) and has zero CN coverage.

### O-7. Instrument the 65-step research cycle: read `steps_ok`, raise the CI timeout, fix the two-token bug. **[Rank 7]**

Three surgical fixes: (a) `daily_research_cycle.py:80-81` — `shlex.split(script)` or list form, which
makes `desk_brief` and `contributor_score` run for the first time ever (0/3 today) and populates the
75-byte empty `contributor_scoreboard.json` that is supposed to tell the desk which intelligence
source earns allocation; (b) raise the `ci_gate` timeout above 300s — CI is **green** and takes
>400s, so the gate rejects 100% of runs regardless of code health; (c) add a consumer for `steps_ok`
that alarms on any step at 0 successes over N runs. Evidence: R-3, R-4, R-7. Complexity: hours.
**This is the cheapest item in the report.**

### O-8. Kill the self-greening trio. **[Rank 8]**

(a) `collect_naver_krsearch` must return `ok: False` with a named blocker when credentials are absent
instead of "graceful skip, cycle stays green" — it has reported success with zero data 6/6 days on the
Korean axis the doctrine mandates. (b) `ops/run_frontier_rotation.sh:21` must not swallow region
failures with `|| echo`; systemd reported `Result=success` while **7/7 regions failed**. (c) Move
`brain_auth_check` **after** log creation in `run_litminer_dig.sh:5`, `run_prospector_dig.sh:5`,
`run_dataaxis_dig.sh` so a quota-dead organ leaves evidence. Evidence: R-5, R-17. Complexity: ~10
lines total. ADJACENCY: these are three instances of one shape found by three independent routes —
**sweep the repo for the pattern rather than fixing three files.**

### O-9. Delete the dead tier. **[Rank 9]**

`libs/alpha_factory/*` (5 engines + controller + research_graph, test-only, 42 days idle,
vocabulary-mismatched), `libs/discovery/{hypotheses,factory,signals}` generation half,
`libs/autodiscovery/generation_roi.py`, `web/pilot.json`. Per L1.12, these have **negative** marginal
ERV: they are where a reader looks for the learning loop, and they have been a no-op for 6 weeks.
Redesign `information_value.py` (algebraic constant, 0/1244 lessons) rather than deleting it — the
*idea* is right, the implementation is degenerate. Evidence: R-2, R-25, R-30.

### O-10. Interpolate `_MINE_PRIORITY`; fix `max_audit.py:2193` `glob`→`rglob`; add `prospector_coverage.md` to `_DIG_DOCS`. **[Rank 10]**

Five organ runners compute the §33 conversion-priority directive and discard it — an inert lever in
5 copies. The rogue-doc detector is non-recursive, so the entire `deep_sweep/` tree (~1.2MB, 17
unscoped cards, **including this report**) is outside the law, a gap the litminer diagnosed 4 days
ago at `literature_coverage.md:194` and which is still open. `_DIG_DOCS` excludes the file where both
surviving frontier miners write. Evidence: R-18. Complexity: ~5 lines.

### O-11. Compress the doctrine; measure the panel. **[Rank 11]**

`ops/principal_doctrine.txt` is 38,257 chars against its own 16,000 guard (2.4×), grew 42% *after*
R0002 was filed, and is prepended to every organ call on a single quota-limited seat. Compress,
preserving every commitment (R-26). Separately: the panel scorecard has **2 scored findings across 26
providers, 0 non-null hit rates**, is 13 days stale, and cannot ever trigger its own down-weighting
policy — while the panel spends ~$60/mo. Either score it or stop paying for the unmeasured half
(R-27).

### O-12. Persist `fetch_video_transcript.py` output; verify or retract the Bilibili claim. **[Rank 12]**

`main():99-100` writes to stdout only, so **zero** transcript artifacts exist and no fetch can ever be
cited or dedup'd. Bilibili captions returned nothing on 3/3 real popular BVids while
`principal_doctrine.txt:205` asserts the capability works. Either demonstrate it end-to-end or amend
the doctrine line — an unverified positive claim in the doctrine is the SCOPE-THE-NEGATIVE-RESULT
discipline running in reverse (R-20).

### O-13. Give the literature pipeline a conversion path. **[Rank 13]**

83 papers ingested, **0 have reached a screen**; `discovery_hypotheses.md` holds 2 open hypotheses
untouched for 11 days; the feed itself fails 6/7 runs on network timeout. The pipeline works and its
triage is well-reasoned — the missing piece is paper→mechanism→screen. Gated behind O-2 (needs a
generator to consume a mechanism). Evidence: R-3, R-21.

## 4. WHAT WE TEST NEXT (concrete experiments)

**T-1. Novelty-gate recall calibration.** *Run:* for each of 43 graveyard names + 152
`research_memory` statements, score every candidate against the corpus-minus-itself under three
metrics (current Jaccard; IDF-cosine from `knowledge_engine.py:80-99`; `TfidfVectorizer` char_wb 3-5).
*Success:* a threshold exists with recall ≥0.90 on verbatim priors and FPR ≤0.10 on the 11
`AXIS_PREREGISTRATIONS` known-distinct hypotheses. *Report:* the full histogram plus the
accept/reject rate, per GATE-OPTIMALITY DUTY. *Retire:* if no metric clears both bars, escalate to a
local embedding model and record the lexical ceiling as measured — a documented ceiling with its
lifting condition.

**T-2. Duplicate-trial census (the number the desk cannot currently state).** *Run:* enumerate every
(signal, target, horizon, window) tuple across `research_candidates` (505), `research_memory` (152),
and every `reports/axis_screens/*` + `data/*screen*.json`; cluster under the T-1 winning metric.
*Success:* a single number for "fraction of lifetime trials that re-tested known ground." *Prior
from this sweep:* ≥5.9% provable (25/424) and plausibly ≥40% (186/434 duplicate triples in one store).
*Why it matters:* this is the numerator that corrects the DSR/Holm denominator — the gate the desk
already knows has become a 100% veto.

**T-3. Generator un-blocking, one axis, pre-registered.** *Run:* add exactly ONE non-price generator
(recommend order-book `replenish_rate`, since `information_advantage` scores `data/moat` at 1.026 —
10× the next source, and it is genuinely OUR timestamps). Pre-register the mechanism and the
target/horizon sweep cells in `trials_ledger` **before** running. *Success:* `tested > 0`,
`distinct_families > 1`, every cell logged with its mechanism, and — per TARGET/HORIZON SWEEP DUTY —
every cell counted, not just the best one. *Retire:* family-kill at ~130 trials / 0 survivors.

**T-4. Forward-clock reconciliation.** *Run:* reconcile `north_star.forward_tested` (0),
`web/discovery.json.pending` (3), and `slot_registry` (claimed 12/12). *Success:* one authoritative
count, one writer, and the Holm `m` provably equal to it. *Why:* this is the denominator on the only
path to capital, and commit `9dddc49` already found it running ~3.2× loose once.

**T-5. Store read/write census (repo-wide).** *Run:* for every file in `data/*.json*` and every
sqlite table, count distinct code writers and code readers, classifying readers as
gate / derive / display. *Success:* a table; **any store with 0 readers is a delete-or-wire
decision with a date.** *Prior:* 3 of the 3 stores I checked were reader-zero, so expect more. This
is the generalised form of R-8 and directly serves the PROACTIVE BATTERY's GENERALISE-THE-RULE move.

**T-6. Self-greening sweep.** *Run:* grep every collector/organ for paths that return success on a
missing precondition (absent credential, empty result, swallowed exit, `|| echo`, `|| true`).
*Success:* a list with a fix or a justification each. *Prior:* 3 instances found by 3 unrelated routes
(R-5, R-17b, R-4) — the base rate says this is a class.

**T-7. Content-drift detection.** *Run:* for the 10 most-cited artifacts, compare mtime-freshness
against content-freshness (last substantive change). *Success:* a divergence list. *Prior:* 3 of 3
checked diverged — `web/pilot.json` (mtime 08:40, data 02:40, value unchangeable),
`panel_rulings.md` (mtime today, substance 12 days old), the 1200-byte sweep floor (bytes, not
content). *Why:* every freshness guard on this desk is an mtime or a byte count, and all three are
already known-wrong.

**T-8. The eight-source probe.** *Run:* one shallow, legitimacy-gated query against each of Gitee,
Feixiaohao, Xueqiu, Qiita, Zenn, velog, smart-lab, cyberleninka. *Success:* per source, either a
carded find with a §33 disposition **or** a documented failed search with a graded residual gap — the
FREE-FRONTIER law's own standard. *Note:* this is deliberately ranked **behind** O-2; running it
first manufactures idle data, which L1.8 calls a defect.

---

## FINDINGS LOG (command-cited; perspectives tagged INTERNAL / EXTERNAL / FUTURE / CONTRARIAN / GREENFIELD / FRONTIER)

### R-1 [INTERNAL] The only quota-free generation engine has tested ZERO hypotheses for 6 consecutive days

The crypto hypothesis factory is the desk's one generation organ that runs independently of the
LLM quota — the answer to PARALLEL MAXIMALISM. Its measured output:

```
$ grep -nE "^===|tested=" data/cro_ai_logs/crypto_factory_cron.log
=== 2026-07-25T03:30:01Z crypto factory harness ===
[cycle] tested=0 survivors=0 rejected=0 promoted_paper=0 skipped_dup=140
[cycle] tested=0 survivors=0 rejected=0 promoted_paper=0 skipped_dup=420
=== 2026-07-26T03:30:01Z ...  tested=0 / tested=0   (skipped_dup=140 / 420)
=== 2026-07-27T03:30:01Z ...  tested=0 / tested=0
=== 2026-07-28T03:30:01Z ...  tested=0 / tested=0
=== 2026-07-29T03:30:02Z ...  tested=0 / tested=0
=== 2026-07-30T03:30:01Z ...  tested=0 / tested=0
```

Six for six, both timeframes, 21 seconds wall-clock per run. `skipped_dup` is identical every day
(140 H8 / 420 D1) — the generator re-draws the same finite pool and the content-hash dedup rejects
all of it. `ops/run_crypto_factory.sh:8-15` documents this as **expected**: "this harness will
re-skip duplicates in seconds until NEW mechanism generators … give it something genuinely new to
test. That is EXPECTED, not a failure."

**That framing is the defect.** The honest read is that generation throughput is *structurally
zero* and has been for at least six days, and the desk has written itself a permission slip. The
harness's stated purpose — "so those additions get tested automatically the moment they land" — is
a *trigger*, not a *generator*. Under L1.8 (PARALLEL MAXIMALISM, "mining and acquisition run at
absolute maximum capacity … idle data is a defect") and the No-Ceiling Axiom, a generator that
cannot enlarge its own hypothesis space is at 0% of capacity, not at ceiling. The comment names the
lifting condition ("NEW mechanism generators") and then nobody owns it: `git log --oneline --
libs/autodiscovery/` last touched the generator families weeks ago, and the family list is
unchanged across all 6 runs (`['liquidity','momentum','mean_reversion','trend',
'volatility_expansion','volatility_compression','cross_asset']` — 6 of 7 are price-only).

This is the same conclusion the desk reached from a different direction (420 price hypotheses → 0
survivors; the one new axis, kimchi, screened in ~1h). The difference is that the SCREEN-ON-
DISCOVERY duty was written for human/LLM organs, and **the automated generator was never
retrofitted to it.** It still generates from price families exclusively while every ingested
non-price axis (OI, long-short, liquidations, basis, stablecoin flows, DeFi utilisation, FRED
macro, exchange netflow) sits outside its generator set.

**Opportunity cost of one year unfixed:** the desk's only zero-marginal-cost discovery loop
contributes 0 hypotheses/day × 365. Every hypothesis therefore has to come through the
quota-limited brain, which (see R-6) completes ~2 auditors per 5-hour window. This is the single
largest throughput constraint in the research engine.

---

### R-2 [INTERNAL, CONTRARIAN] The "information value" instrument is an algebraic constant — 1244/1244 rows identical

`libs/research/information_value.py:1-13` declares itself the desk's honest success metric:
"judge research by UNCERTAINTY REMOVED, not alpha count … is throughput buying learning or just
noise?" Measured:

```
$ python3 -c "...collections.Counter over data/information_value.jsonl..."
total rows: 1244
by family: [('crypto_D1', 1244)]
by name: [('factory_reject', 1244)]
survived: Counter({False: 1244})
fwd_validated: Counter({False: 1244})
distinct info_bits values: [(0.2345, 1244)]
distinct prior: [(0.15, 1244)]
by day: [('2026-07-30', 434), ('2026-07-22', 420), ('2026-07-16', 390)]
lessons non-empty: 0
```

Four independent degeneracies in the desk's headline research-quality metric:

1. **`info_bits_per_experiment` is pinned by algebra, not measured.** Every row is a reject at a
   hardcoded prior of 0.15, so `surprise_bits` returns `-log2(0.85) = 0.2345` for all of them
   (`information_value.py:28-32`). The reported 0.2345 in `web/pilot.json` cannot move while
   survivors = 0. It is a **100%-constant gate**: it carries zero information and cannot
   distinguish a good research week from a dead one. The prior is not updated from the desk's own
   realised base rate either — 0/1244 observed vs a 0.15 assumption is a 15-sigma miscalibration
   that no code notices.
2. **`distinct_families` reports 1, forever.** The docstring says this answers "is breadth growing,
   or are we re-drawing one pool?" — and it is hardwired to `crypto_{timeframe}`
   (`information_value.py:62`), so at most 2 values can ever appear, and only D1 ever has. The
   H8 timeframe runs FIRST every single day and has **never logged a single row** (0 `crypto_H8`
   entries in 1244) because `record_factory_cycle(result.tested=0, …)` writes nothing. The breadth
   metric is blind to the very thing it claims to measure, AND the ledger silently undercounts
   the campaign by the entire H8 arm (~140 trials).
3. **`lesson` is empty in 1244/1244 rows.** The one field carrying transferable knowledge —
   *why* the idea died — is 100% unpopulated. `record_factory_cycle` never passes it
   (`information_value.py:63-66`). The "learning" ledger stores a counter, not a lesson. This is
   INFORMATION ENTROPY at its purest: 1244 experiments' worth of死 mechanism, unrecoverable.
4. **The dashboard card looks fresher than the data.**
   ```
   $ ls -la data/information_value.jsonl web/pilot.json
   -rw-rw-r-- 245068 Jul 30 02:40 data/information_value.jsonl
   -rw-rw-r--    571 Jul 30 08:40 web/pilot.json
   $ python3 -c "print(json.load(open('web/pilot.json'))['updated'])"
   2026-07-30T08:40:49.766761+00:00
   ```
   The card is rewritten on every factory run even when `tested=0`, so its `updated` stamp
   advances while its content cannot. A reader sees "updated 6 hours ago"; the underlying evidence
   last changed at 02:40 and before that on 07-22. **Config-vs-outcome inside the freshness field
   itself.**

Rows appeared on only 3 of the last 14 days (07-16: 390, 07-22: 420, 07-30: 434 — all in a single
minute each: `07-30T02:40` ×434). So the instrument confirms R-1 independently: on 11 of 14 days
the research engine logged zero experiments of any kind.

**Contrarian test applied:** is the metric maybe *correctly* reporting a genuinely dead research
programme? No — that would be a valid finding, but then `distinct_families=1` and `lesson=0/1244`
would still be defects, and the H8 undercount would still misstate the trial denominator that
DSR/multiplicity control depends on. The instrument is broken *independently* of whether the
research is.

---

### R-3 [INTERNAL] Two steps of the daily research cycle have never run once — a shell-quoting bug, 3/3 failures

```
$ python3 (aggregate over data/cro_ai_logs/daily_research_cycle.log)
TOTAL step-invocations: 289   distinct steps: 65
  7x FAIL / 0x ok  ci_gate            timeout after 300s  /  "CI: FAILED -> ['lint (ruff)']"
  6x FAIL / 1x ok  research_feed      TimeoutError: The read operation timed out
  4x FAIL / 2x ok  axis_shadows       HTTPError 418: I'm a teapot
  4x FAIL / 3x ok  shadow_8h          HTTPError 418: I'm a teapot
  3x FAIL / 4x ok  listing_watch      HTTPError 418: Unknown
  3x FAIL / 4x ok  micro_audit        micro-audit brief failed sanitization -- refusing to send
  3x FAIL / 0x ok  desk_brief         can't open file 'scripts/research_exchange.py brief'
  3x FAIL / 0x ok  contributor_score  can't open file 'scripts/research_exchange.py score'
  1x FAIL / 6x ok  root_cause         TypeError: float() argument ... not 'NoneType'
  1x FAIL / 6x ok  cadence            TimeoutExpired: run_external_panel.py after 720s
```

**`desk_brief` and `contributor_score`: 0 successes ever, and the cause is one line.**
`scripts/daily_research_cycle.py:80-81` registers the steps as
```python
("desk_brief",        "scripts/research_exchange.py brief", 60),
("contributor_score", "scripts/research_exchange.py score", 60),
```
and `:105` invokes `subprocess.run([_PY, script], …)` — `script` is passed as a **single argv
element**, so Python is asked to open a file literally named `scripts/research_exchange.py brief`.
No `shlex.split`, no list form. Every other step is a bare path so the bug is invisible except on
these two.

What that costs: `research_exchange.py` is the desk's *research board / external-LLM brief* and
its *contributor scoring* ("which intelligence source earns allocation"). Both are
research-engine PRIORITIZATION organs. The scoreboard is the evidence:
```
$ cat data/contributor_scoreboard.json ; ls -la data/contributor_scoreboard.json
{"updated": "2026-07-27T20:39:...", "sources": {}, ...}   (75 bytes, Jul 27 20:39)
```
75 bytes, `sources` empty. **The desk cannot say which of its intelligence sources earns
allocation, because the organ that would tell it has never executed.** That directly disables the
measured-conversion-rate steering that §33's `mine_generation_priors.json` is supposed to embody.

**`ci_gate`: 7 FAIL / 0 ok.** The research cycle's own code-health gate has never passed — it
either times out at 300s or reports `lint (ruff)` failures. So every research cycle for at least a
week has run against a codebase whose gate is red, and nothing blocked, paged, or escalated.

---

### R-4 [INTERNAL, capability gap] The cycle records its own failures into a field that NOTHING reads

`scripts/daily_research_cycle.py:139` writes `"steps_ok": {k: v.get("ok") …}` into
`data/cro_cycle_log.json` for all 65 steps, every day.

```
$ grep -rn "steps_ok" --include=*.py --include=*.json --include=*.md . | grep -v .venv
scripts/daily_research_cycle.py:139:        "steps_ok": {k: v.get("ok") for k, v in steps.items()},
```

**One hit: the writer.** Zero readers. No monitor, no alert, no digest, no gate consumes
`steps_ok`. `_run()` (`:103-112`) never raises and `main()` (`:124-126`) never checks the return —
it prints and continues. That is why a step at **0/7 lifetime success** (`ci_gate`) and two steps
at **0/3** (`desk_brief`, `contributor_score`) survived undetected: the desk built the telemetry
and never built the consumer. A 65-step pipeline with per-step success recorded and no
streak-detector is the definition of a self-greening organ — the cycle's final line is a cheerful
`CRO cycle 2026-07-30: next-ROI=… | constraint=…` regardless of how many steps died.

---

### R-5 [INTERNAL, FRONTIER-negative] The Korean-language collector reports `ok: True` while collecting nothing, every single day

```
$ grep -n naver_krsearch data/cro_ai_logs/daily_research_cycle.log
28:[naver_krsearch] {'ok': True, 'rc': 0, 'tail': 'collect_naver_krsearch: no NAVER_CLIENT_ID/SECRET
   (env or data/secrets/naver.json) -- graceful skip, cycle stays green'}
58: … 88: … 119: … 169: … 235: (6 of 6 cycle runs, identical)
```

Six for six, `ok: True`, zero data. The phrase **"cycle stays green"** is in the source as a
design goal. This is the self-greening guard pattern the doctrine names as prime quarry, applied to
exactly the capability the FREE-FRONTIER law says must never be English-only: Korean. The kimchi
premium — the desk's single best-ever Stage-A screen (IC +0.148) before it was retracted as an
artifact — came from the Korean axis. The Korean *search* collector, which would surface the next
one, has never run and never complains.

Missing-credential-as-success is a *class*, not an instance (PROACTIVE BATTERY move 2, ADJACENCY):
any collector whose absent-secret path returns rc=0 is invisible to R-4's non-existent monitor. The
correct behaviour for a doctrine-mandated capability is `ok: False` + a named blocker, so it lands
in the pager and the GAP register.

---

### R-6 [INTERNAL, meta] The research-engine cold audit has never completed — its success test measures BYTES, which manufactured a false pass that then BLOCKED its own retry

This is the fourth consecutive sweep in which this report was not produced. The mechanism is now
fully diagnosed, and it is not research-engine-specific:

**(a) Fixed, never-rotated order; research-engine is 7th of 8.** `scripts/run_deep_sweep.py:136`
iterates the `SUBSYSTEMS` dict in insertion order:
`1 alpha-discovery, 2 data-intelligence, 3 data-moat, 4 infrastructure, 5 execution-growth,
6 validation-stats, 7 research-engine, 8 meta-and-blindspots`, then synthesis 9th (`:151-181`).
Sequential single-threaded loop (`:136-148`) — deliberate, per the module docstring ("the box
cannot fan out parallel agents").

**(b) Failure is a contiguous SUFFIX every time — the signature of one shared exhausted resource.**
```
$ for f in $(ls -tr data/cro_ai_logs/deep_sweep_*.log); do grep '^\[deep-sweep\]' $f; done
07-28T2000  new: 1,2,3        first failure 4  -> 4-8 failed, synthesis NO
07-29T0100  new: 1            first failure 2  -> 1/8
07-29T0600  new: 2,3,4        first failure 5  -> 4/8
07-29T1100  new: 5            first failure 6  -> 5/8
07-29T1600  new: 6,7*         first failure 8  -> 7/8
07-29T2110  new: 8            -> 8/8, synthesis YES
07-30T0200  new: 1,2,3        first failure 4  -> 3/8
07-30T0740  new: 4,5,6        first failure 7  -> 6/8
```
Positions 1-3 have never failed on a fresh window; positions 7-8 have never succeeded on one. Mean
**~2.1 new completions per window**; windows arrive ~every 5h. Reaching position 7 from a cold
stamp needs ~3.3 windows ≈ **17h**, against a stamp that resets at UTC midnight
(`stamp = …strftime("%Y%m%d")`, `:134`) and is shared with every other organ on the box. 07-29 is
the only date that ever got six windows, and the only date the sweep ever finished.

Subsystem-specific causes are **ruled out**: prompt sizes are near-identical (research-engine
≈8407B vs alpha-discovery ≈8314B), and every research-engine death is a pre-flight `exit 90` from
`brain_auth_check` — *before* `claude` is invoked — so report length/complexity cannot be the
cause.

**(c) The 1200-byte floor manufactures false passes.** `run_deep_sweep.py:108`:
`ok = report.exists() and report.stat().st_size >= 1200`. Bytes, not content. Placeholder counts
(`grep -coiE "TBD|placeholder|IN PROGRESS|incremental"`):
```
20260730_infrastructure.md    122,891B   1 placeholder   OK (real)
20260730_data-intelligence.md 119,011B   2               OK (real)
20260729_research-engine.md     3,380B  11               OK  <-- SKELETON scored as success
20260730_validation-stats.md    1,889B  19               OK  <-- skeleton
20260730_alpha-discovery.md     1,736B  28               OK  <-- skeleton
20260728_data-moat.md           5,407B  17               OK  <-- skeleton
```
`20260729_research-engine.md` has all ten SCORES as `TBD` and sections 2/3/4 empty. It counted
toward "7/8 produced", was fed to the synthesis lead as a *good* report, and then:
```
$ grep research-engine data/cro_ai_logs/deep_sweep_20260729T2110.log
research-engine: already produced today -- skipping (resume)
```
**The false pass permanently blocked research-engine's own retry** for the remaining usable windows
of the only day the sweep ever completed. `run_deep_sweep.py:8-9` states the rule this violates:
"the audit that hunts config-vs-outcome must never itself be config-vs-outcome." ~6 of ~24
nominally-passing reports across the four sweeps are skeletons.

**(d) No retry, no backoff, no downgrade.** `grep -nE "sleep|retry|attempt|backoff|range\(|while "
scripts/run_deep_sweep.py` → **no output**. `run_auditor` is called exactly once per key (`:146`);
on auth failure it writes the stub and moves straight to the next auditor. Measured cost, from the
07-28 stub mtimes: `20:36:41 infrastructure / 20:36:49 execution-growth / 20:36:58
validation-stats / 20:37:08 research-engine / 20:37:17 meta-and-blindspots` — **five auditors
burned in 36 seconds**, ~9s apart, against a pool that had just printed its reset time. Nothing
waits for the reset the CLI itself reported.

**(e) The model chain walks, but its last resort is dead code, and the sweep inverts it.**
`ops/brain_env.sh:76` sets `claude-opus-5 claude-opus-4-8 claude-fable-5` with the justification
at `:74-75` ("one max-effort dig drained the whole fable-5 METERED pool… Max-seat models lead;
fable is last"). `run_deep_sweep.py:80` **overrides it back to fable-first**. The 07-26 stub is the
receipt: `docs/research/deep_sweep/20260726_execution-growth.md` (147 bytes) contains
`"You're out of usage credits. Run /usage-credits to keep using Fable 5…"`. Separately,
`brain_env.sh:52` gates the metered-API escape hatch on `[ -f "$_BRAIN_KEYFILE" ]`, and
`ls -la data/secrets/ | grep anthropic` → no output. **The final fallback is unreachable**; all
three chain entries resolve to the same single Max OAuth seat once metered credits are gone.

**(f) Four consecutive deaths were structurally invisible.**
- `grep -rn "AUDITOR FAILED" --include=*.py --include=*.sh .` → **one hit, the writer**
  (`run_deep_sweep.py:126`). Nothing consumes the marker.
- No JSON/JSONL ledger of per-auditor outcome exists; no streak counter
  (`grep -rn "streak\|consecutive" scripts/organ_catchup.py libs/ops/organ_catchup.py` → nothing).
- `scripts/max_audit.py:1510` lists `docs/research/deep_sweep/` in `_FINDING_DOCS_EXCLUDED`, so
  the daily audit never inspects sweep content or size.
- `scripts/page_digest.py`: `grep -n "deep_sweep\|AUDITOR\|1200"` → no hits. And the pager is
  itself lossy: `cat data/cro_ai_logs/digest_page.log` → `HTTPError 429: Too Many Requests` on 2
  of 4 lines.
- Pages fire but are generic: `brain_env.sh:62` sends `"BRAIN AUTH DOWN, cycle aborted"` with no
  subsystem name. The 07-28 event sent five identical pages in 36 seconds.
- `data/cro_ai_logs/quota_watch.log` is **0 bytes** since 07-28 21:20 — `scripts/quota_verdict.py`
  (cron `20 */3`) produces no output at all. The quota monitor is dead, and its scope excludes
  sweep auditors anyway.

**The desk's only detector for this entire failure class is a human running `ls -la`.**

**(g) The fix was diagnosed, written down, and never landed.**
`docs/research/improvement_inbox.md:1047-1055` item **#74 — "SWEEP-RUNNER: ROTATE SEATS +
SYNTHESIS-FIRST + FAILURE-STREAK ALARM (P0-3)"** proposes `start seat = week# mod 8`,
synthesis-first on resume, and a per-seat streak alarm — self-estimated **~20 lines**. It cites
`docs/research/deep_sweep/20260729_meta-and-blindspots.md:132-146`, which had already identified
this exact mechanism.
```
$ git log --oneline -1 -- scripts/run_deep_sweep.py
53cda72  2026-07-26 15:11
```
Nothing has landed since the diagnosis; two more sweeps have failed identically. **This is a
§41 orphaned recommendation on the highest-ERV auditor in the rotation.**

**(h) Bonus defect in the same file:** `:152` is `if good:` with no `synth.exists()` guard
(`grep -n "synth"` → `:151,156,184` only). Every catch-up re-fire after a completed sweep re-runs
the max-effort SYNTHESIS from scratch, consuming an entire window.

**(i) Probe overhead.** `brain_auth_check` spends a real `claude -p` call per model — up to 3 pings
× 8 auditors per sweep, plus `organ_catchup._quota_ok` up to 3 more every 5 minutes.
`grep -c "owed=deep_sweep quota=DEAD" data/cro_ai_logs/organ_catchup.log` → **640 dead probes vs
11 successful fires (98.3% dead)**, ≈1,900 pings. Whether failed pings consume session budget is
**undetermined** — no per-request accounting exists on this box, which is itself the gap.

---

### R-7 [INTERNAL] `ci_gate` can never pass: the timeout is shorter than the runtime. 7/7 failures are structural.

R-3 showed `ci_gate` at 7 FAIL / 0 ok. I ran it directly:

```
$ .venv/bin/python scripts/run_ci.py
[PASS] lint (ruff): All checks passed!
[PASS] tests (pytest): SKIPPED [1] tests/research/test_principal_page_integrity.py:108 ...
[PASS] stress harness: STRESS: growth-proof ruin-capped growth >= over-bet growth ...
CI: ALL GREEN
```
**CI is green — but it took longer than 400 s** (my 400 s foreground budget expired and the job
finished in background). `scripts/daily_research_cycle.py:34` allots it **300 s**:
```python
("ci_gate", "scripts/run_ci.py", 300),
```
So the recent failures are `rc: 'timeout'`, not real defects. The gate **rejects 100% of runs
regardless of code health** — the exact pathology the GATE-OPTIMALITY DUTY names: a gate at ~100%
reject carries zero information. Worse, it is *anti*-informative: it trained the desk to read
`ci_gate: False` as noise, so if lint genuinely broke tomorrow nobody would notice the difference.
(The two oldest entries — `CI: FAILED -> ['lint (ruff)', 'tests (pytest)']` and
`CI: FAILED -> ['lint (ruff)']` — were real; they were then masked by the timeout regime.)

---

### R-8 [INTERNAL, CONTRARIAN — the single largest finding in this sweep] Research memory is WRITE-ONLY. Three stores have exactly one code reference each, and it is the writer.

The RESEARCH-MEMORY DUTY exists to stop rediscovery: *"A factory that forgets its experiments
re-runs them."* Measured, the factory forgets.

```
$ for f in graveyard_resurrection_queue.json negative_knowledge.json knowledge_engine.json; do
    echo "## $f"; grep -rn "$f" --include=*.py --include=*.sh --include=*.js --include=*.html . \
    | grep -v rollback | grep -v .venv; done
## graveyard_resurrection_queue.json
scripts/graveyard_resurrect.py:22:OUT = Path("data/graveyard_resurrection_queue.json")
## negative_knowledge.json
scripts/negative_knowledge.py:31:OUT = ROOT / "data/negative_knowledge.json"
## knowledge_engine.json
scripts/knowledge_engine.py:47:OUT = ROOT / "data/knowledge_engine.json"
```

**Three stores. Three writers. Zero readers — not even a display reader.** (Every other grep hit is
auditor prose in `docs/research/deep_sweep/*`.) Contents: 42 queued resurrections, 44 negative-
knowledge records of which 10 are flagged `revivable_now`, and a 247-document corpus. All inert.

`research_memory` (the sqlite table, **150 rows**, `2026-07-24 → 2026-07-30`) has 2 writers and 3
readers — and here is what the readers actually read:

| site | query | what it extracts |
|---|---|---|
| `scripts/max_audit.py:1001` | `SELECT COUNT(*)` | liveness (defect if 0) |
| `scripts/max_audit.py:1107` | `COUNT(*) WHERE created_at>=-7d` | growth (defect if 0) |
| `scripts/max_audit.py:110` | `SELECT metrics_json` | **one key: `axis`** |
| `scripts/research_memory.py:65` | `report` subcommand | display; **not in cron, not in `daily_research_cycle.py`** — invoked only by hand |
| `libs/alpha_factory/research_memory.py:117,123` | `get()`/`all()` | **dead code** |

So the desk's richest research asset is consumed as `COUNT(*)` twice and one JSON key once.

**The `libs/alpha_factory` learning loop is unreachable AND type-mismatched — a no-op twice over.**
`AlphaFactoryController`, `ResearchAllocator`, `HypothesisEngine`, `ResearchGraph` are instantiated
**only in `tests/`** (`grep -rn "AlphaFactoryController\|ResearchAllocator\|HypothesisEngine"
--include=*.py . | grep -v tests` → only `__init__.py` re-exports). The one non-test path,
`app/dashboard.py:60`, needs streamlit (`python3 -c "import streamlit"` → `ModuleNotFoundError`);
the live server is `scripts/serve_dashboard.py`, a static `SimpleHTTPRequestHandler`.
And even if it ran: `hypothesis_engine.py:53` and `research_allocator.py:41` call
`memory.success_rate(category.value)` with an `AlphaCategory`
(`trend_following, momentum, carry, …`, `libs/self_improvement/models.py:48`), while the CLI writes
`_CATS = ("hypothesis","dataset","method","mission","construction")`
(`scripts/research_memory.py:25`). Verified DB categories:
`['construction','dataset','hypothesis','method','mission']`. **The vocabularies are disjoint**, so
every `success_rate()` returns 0.0 and falls back to `_DEFAULT_EDGE = 0.5`. The prior never learns.

**Row quality is genuinely excellent — which makes this worse, not better.** Fill rates across 150
rows: `lessons 146/150`, `failure_cause 110/150`, `failure_stage 105/150`, `metrics_json 150/150`,
mean statement 268 chars, only 11/150 metrics-thin. A real row:
```
rm-20260726T010118-49063a | construction | failure
stmt   : energy construction: XNG_mom20->BTC_20d -- Natural gas 20d momentum -> absolute BTC 20d.
         Miner cost-squeeze at the monthly horizon.
lessons: Correct mechanism sign and clean de-contamination, but only 0.56 sigma on n=66, and the
         shift test FLIPS it to +0.2423. Also the single worst case of harness Sharpe inflation in
         the sweep: -4.22 reported vs -0.80 true, a 5.4x overstatement
metrics: {"ic":-0.0695,"n":66,"residual_ic":-0.0552,"sharpe_corrected":-0.8,
          "sharpe_harness":-4.22,"multiplicity_threshold_ic":0.3078,"shift_test_ic":0.2423,...}
```
A future agent could learn a great deal from that. Nothing does. `predecessor_id` is **0/150**, so
there is no genealogy either — every experiment is an orphan.

**INFORMATION ENTROPY, quantified.** The only store that gates anything is the 43-row markdown
table `docs/graveyard.md`. Cross-matching:
```
research_memory failure rows:                                    124
rows whose construction name appears in docs/graveyard.md:         5
rows invisible to every dedup gate:                              119  (96%)
```
**96% of the desk's recorded refutations cannot be seen by any mechanism that prevents
rediscovery.**

---

### R-9 [INTERNAL] The novelty gate is advisory in 2 of 3 call sites, and its prior corpus is 2 hardcoded objects in the one site that blocks

Classified by whether behaviour actually changes:

**GENUINE GATES (3):**
- `scripts/hypothesis_generator.py:154-158` — `if words & dead_tok: dup += 1; continue`. Drops LLM
  proposals on *name-token* collision with a graveyard name.
- `scripts/breadth_expander.py:192-199` — same for data sources. Its comment names the incident:
  *"the 2026-07-27 sweep re-suggested Bithumb/Coinone/Bitso/Mercado -- all TESTED AND KILLED the
  same day -- because dedup only read the class map."*
- `scripts/screen_exchange_netflow.py:109-112` — `if nov.is_redundant: return 0`. Hard abort. **But
  its priors are two hardcoded inline `PriorIdea` objects** (`:97-105`) — not the graveyard, not
  research_memory.

**ADVISORY ONLY (2):** `scripts/screen_idle_axes.py:94-102` and `scripts/screen_fred_macro_axis.py:187-196`
compute redundancy, print it, and proceed regardless. `grep -n "redundant" scripts/screen_idle_axes.py`
→ lines 99, 102 only (a dict key and a print). No branch on `is_redundant` in either file.

This is by design: `libs/alpha_factory/hypothesis_novelty.py:13` —
*"Advisory by design — it returns a novelty score and the nearest prior failure, never a hard
block."* That is a defensible choice for an *advisory* tool, but the UNIVERSAL DUTY SET states the
gate exists because *"a redundant hypothesis burns DSR multiplicity budget twice"* — a cost that
advice does not prevent.

**Measured bypass.** `data/idle_axis_screen.json` (2026-07-28T20:23):
```json
{"candidate":"try_premium::stablecoin_rent","novelty_score":0.881,
 "nearest_id":"collector:onchain_activity_throughput","nearest_similarity":0.119,
 "is_redundant":false,"n_priors":40}
```
`try_premium_timing` sits in the graveyard as a permanent `timing_artifact` kill. With 40 priors
loaded, the similarity engine matched an unrelated collector, returned `is_redundant:false`, and
**9 cells ran** (`try_premium::T1/T2/T3 × 1d/5d/20d`) — one printing a false `SCREEN-INTERESTING`
at `n_eff 3.9`.

**And the cost it claims to protect is itself unwired.** `trials_ledger` has **0 rows in all three
databases**, and `libs/store/trials.py::TrialsLedger` appears only in `tests/`. The multiplicity
budget the novelty gate exists to conserve is not being counted anywhere.

---

### R-10 [INTERNAL, the proof of rediscovery] The same four experiments were re-run on 2026-07-30 — twice in 66 minutes — and scored 97.3% NOVEL

This is the direct, numeric proof that R-8/R-9 cost real compute and real multiplicity budget.

| # | when | what | evidence |
|---|---|---|---|
| 1 | 07-26T00:54 | 4 cells, h=1d | `rm-…5f6054/fc0fd8/c12222/33c2d2`, `axis:"coinmetrics_flows"` |
| 2 | 07-28T15:25 | **BLOCKED** by the gate | `rm-20260728T152514-36796d`, `failure_stage: novelty_gate` |
| 3 | 07-30T02:41 | **12 cells RAN** | `reports/screen_exchange_netflow.json`, `rm-20260730T024116-185ecc`, `axis:"exchange_netflow"` |
| 4 | 07-30T03:47 | **4 cells RAN again** | `data/batch_coinmetrics_screen.json` |

Run 1 vs run 3, same four constructions:

| construction | 07-26 IC / residual | 07-30 IC / residual |
|---|---|---|
| netflow_native_btc | **−0.0075 / −0.0074** | **−0.0074 / −0.0073** |
| netflow_over_exchange_supply_btc | **0.0095 / 0.0095** | **0.0095 / 0.0095** |
| netflow_native_eth | **0.0039 / 0.0033** | **0.0039 / 0.0033** |
| netflow_over_exchange_supply_eth | **0.0031 / 0.0026** | **0.0032 / 0.0027** |

Identical to four decimals. What the gate said on run 3:
```
$ python3 -c "print(json.load(open('reports/screen_exchange_netflow.json'))['novelty'])"
{'score': 0.9727272727272728, 'nearest': 'kimchi-premium', 'similarity': 0.02727}
```
**97.3% novel, nearest prior "kimchi-premium"** — because the two hand-written priors at
`screen_exchange_netflow.py:97-105` do not include the 07-26 netflow screen. The research_memory
row then records the falsehood as fact: *"Genuinely novel axis (novelty 0.973, nearest prior kimchi
at sim 0.027)"* (`rm-20260730T024116-185ecc`). The `axis` tag was also renamed
`coinmetrics_flows → exchange_netflow`, defeating even axis-level dedup.

**Run 4 is mechanical and recurs daily.** `crontab -l` → `47 3 * * * … scripts/collect_coinmetrics_flows.py`;
`collect_coinmetrics_flows.py:244` calls `_screen_all(rows)` **unconditionally** on every run
(`:218` `stage_a_screen(sig, ret, name=f"cm_{label}_{asset}")`, 2 constructions × 2 assets). No
memory check, no novelty gate. The same four Stage-A trials are re-run every morning and the
artifact is overwritten — and `data/*` is gitignored (`.gitignore:11`), so **the repetition leaves
no trace at all.** Number of times this has actually fired: **undetermined**, because the evidence
is destroyed on each run.

Honest counterweight: 16/150 rows do describe *justified* re-runs (alignment-bug re-run of the
07-24 CME screen; shift-sensitivity controls). Those are correct practice. The netflow case is not
one of them.

---

### R-11 [INTERNAL] The one memory-consulting gate that works has the incentive INVERTED against it

Exactly one code path can reject work before compute is spent
(`screen_exchange_netflow.py:109`), and it did fire once — `rm-20260728T152514-36796d`:
> *"BLOCKED BY THE NOVELTY GATE before any compute was spent: the aggregate exchange-flow metric
> class is already dead on the record — cm_netflow_native_btc n=5,549 IC −0.0075 (SCREEN-WEAK)"*

Two days later the same gate in the same file let the same hypothesis through at 97.3% novel (R-10).

Meanwhile the *only* content-reading consumer of research_memory — `max_audit.py:110`, which reads
the `axis` tag — **pushes in the opposite direction**: an axis with no research_memory row is
flagged idle, which raises a `data-utilization-paralysis` defect, which pressures an organ to
screen it. It never consults the graveyard. The desk diagnosed this itself in
`rm-20260728T202913-32e4c9`:
> *"Coverage parity reads research_memory, so **a graveyarded axis looks identical to an untested
> one and invites exactly the re-test the graveyard forbids — as happened on 2026-07-26**."*

131/150 rows carry an `axis` tag; 19 carry none; the tag is the only field any gate consumes. So the
enforcement surface is: one advisory scorer, one hard gate with a 2-item corpus, a 43-row prose
table missing 96% of refutations, and a coverage metric that actively rewards re-testing dead
ground.

---

### R-12 [INTERNAL] The knowledge graph is nine hardcoded tuples, and the organ that claims to answer "has this already been tested?" cannot accept a query

- `scripts/knowledge_engine.py:105-129` — `CAUSAL` is a **9-element hardcoded list of tuples**;
  `REVIVAL` (`:131-144`) is 4 hardcoded dicts. Neither is derived from any store; neither grows
  when the desk logs an experiment. `data/knowledge_engine.json` reports `corpus 247, causal
  edges 9, genome 4, revival 4`.
- Item A of that engine self-describes as *"RESEARCH MEMORY — 'has this effectively already been
  tested?' answered BEFORE compute is spent"* (`knowledge_engine.py:7`). It runs TF-IDF retrieval
  against **three hardcoded query strings** (`:154-156`, e.g. `"order book depth withdrawal
  predicts volatility"`), and `grep -n "argparse\|sys.argv" scripts/knowledge_engine.py` → **no
  matches**. There is no way to pass it a candidate. **It cannot answer the question it names.**
- `libs/alpha_factory/research_graph.py` is a real typed DAG
  (`idea→feature→signal→factor→alpha→performance`) with **no persistence**
  (`grep -n "save\|load\|dumps"` → nothing) and only one instantiator, the test-only
  `AlphaFactoryController:53`.
- The corpus itself is mostly noise: `data/experiment_registry.jsonl` has 429 rows of which
  **338 are `M_UNMAPPED`**, and `scripts/data_vitals.py:69` labels it *"DERIVED — harvested from
  git; timestamps are commit dates"*. It is a git log re-badged as an experiment registry.
  research_memory's 150 rich rows are in **neither** the knowledge-engine corpus nor the registry.

**Cross-domain synthesis is therefore not possible from what is stored.** There is no queryable
representation linking mechanism → axis → construction → outcome, so the desk cannot ask "what have
we learned about *timing artifacts* across all axes?" — the question the kimchi and Turkey-premium
retractions make the most valuable question on the board.

---

### R-13 [INTERNAL] The resurrection engine: 42 queued, 1 resurrection ever, human-mediated, result never written back, not scheduled

- `data/graveyard_resurrection_queue.json`: **42 entries**, `updated 2026-07-27T12:48:43Z` — three
  days stale, priorities `{5:2, 3:8, 2:13, 1:8, 0:11}`.
- **No automated trigger.** `scripts/graveyard_resurrect.py:11`: *"It does NOT resurrect anything —
  it produces the queue the brain/CRO works."* `scripts/negative_knowledge.py:145`: *"These are NOT
  auto-resurrected… Zero promotion authority."*
- **Not scheduled anywhere.** Absent from `crontab -l` and absent from the `daily_research_cycle.py`
  step list (`negative_knowledge` and `knowledge_engine` are there at `:87`/`:71`;
  `graveyard_resurrect` is not). It has run **once**.
- **The one resurrection, traced.** `scripts/horizon_search.py:5`: *"The resurrection engine
  shortlisted exactly two: multilingual_wikipedia_attention and defi_health."* Timeline:
  ```
  data/graveyard_resurrection_queue.json  2026-07-27 12:48:43
  data/horizon_discovery.json             2026-07-27 12:54:12   (+5m29s)
  ```
  8 series × 12 horizons = **96 cells, 0 survivors** (commit `121d8bd` "horizon discovery (0/96)").
  But `horizon_search.py:67-75` **hardcodes the two candidate names** — it never reads the queue
  file. A human read the printed output and typed them in. And **the 0/96 result was never written
  back**: the queue still lists both as `priority 5 / PRIME RESURRECTION` today. `horizon_search.py`
  is scheduled nowhere.
- **Zero of the 10 `revivable_now` records in `negative_knowledge.json` have been re-tested.**
  `git log --all -i --grep=resurrect` returns only the 4 commits that *built* these organs.

So the failed-experiment learning loop is: derive a queue → print it → a human copies two names by
hand → run them → discard the result → the queue still says they are prime candidates. The loop is
open at both ends.

---

### R-14 [INTERNAL] The desk's own north-star metric reads `validated_alpha_discovery_rate: 0.0` — and the 19→0 break is the whole pipeline

```
$ python3 -c "print(json.load(open('data/research_cio.json'))['north_star'])"
{'window_days': 45.0, 'experiments': 424, 'decided': 203, 'survived_screening': 19,
 'forward_tested': 0, 'deployed': 0, 'validated_alpha_discovery_rate': 0.0}
```

424 experiments → 203 decided → **19 survived screening → 0 forward-tested → 0 deployed**, over a
45-day window. The supreme co-objective (MAXIMUM ALPHA-DISCOVERY RATE) is measured by the desk's own
instrument at exactly **zero**, and has a hard break at Stage A → Stage B: 19 survivors, none of
which entered forward evidence.

**But `forward_tested: 0` is itself suspect**, and this matters more than the zero. `MAX_FORWARD_SLOTS
= 12` (`libs/research/slot_registry.py:37`), and the desk's own commit `b70298d` states the cohort
is "capacity-blocked at 12/12". Meanwhile:
```
$ python3 -c "print(len(json.load(open('web/discovery.json'))['pending']))"
3
   oi_divergence / ls_contrarian / liquidation_reversal -- all "PENDING (32/40d archived)"
```
So three separate representations disagree: `north_star.forward_tested = 0`, `web/discovery.json`
shows 3 pending clocks, and the slot registry is claimed full at 12/12. **At most one of these can be
right, and no code reconciles them.** Whatever the true number, the metric the desk uses to score its
supreme objective is not measuring the thing it names. That is worse than a zero — a true zero is
actionable; an unreconciled zero teaches nothing and cannot be improved against.

**And the 45-day window makes the metric structurally incapable of ever reading non-zero on new
axes**: forward clocks need 40+ days of archived data (`needs_days: 40, have_days: 32`), so anything
discovered inside the window cannot be forward-validated inside the window. The rate is guaranteed
0.0 by arithmetic for any new axis. GATE-OPTIMALITY DUTY applies to metrics too: a number that can
only ever print 0 carries no information.

---

### R-15 [INTERNAL, CONTRARIAN] The prioritizer's 40-item schedule is one mechanism, one transform, and four distinct scores

```
$ python3 -c "...Counter over data/research_cio.json['schedule']..."
schedule len 40
distinct mechanisms: [('M_LIQUIDITY_WITHDRAWAL', 40)]
distinct transforms: [('replenish_rate', 40)]
distinct priors:      [(1.05, 12), (1.15, 12), (1.0, 10), (1.2, 6)]
distinct sched_score: [(1.0773, 12), (0.7866, 12), (1.026, 10), (0.8208, 6)]
distinct observables: depth5:9 depth10:9 spread_bps:7 imbalance:5 concentration:5 slope:5
```

The research schedule — the organ that decides what the desk works on next — is a **Cartesian grid
over one mechanism and one transform**: 6 observables × 2 windows × normalisations, all
`M_LIQUIDITY_WITHDRAWAL / replenish_rate`. 40 items collapse to **4 distinct priority scores**, so
within each block of 6–12 items the prioritizer expresses no preference at all; the ordering inside a
tie-block is arbitrary.

This is defensible on one reading — `information_advantage` correctly scores `data/moat (order
books)` at 1.026, an order of magnitude above everything else (CNY premium 0.371, venue divergence
0.154, funding/OI/LS 0.060, GitHub 0.010, on-chain 0.005, social 0.0002), because those are OUR
timestamps and nobody can replicate them. Concentrating on the highest-advantage source is right.

**But it is a monoculture, and it violates L1.18 (ALPHA DIVERSITY: maximum INDEPENDENT compounding
sources).** 40/40 candidates share one mechanism, so their outcomes are near-perfectly correlated: if
`replenish_rate` is not predictive, the entire schedule is dead simultaneously, and the desk will have
spent its whole queue learning one bit. A schedule with 40 slots and 1 mechanism has an effective
breadth of 1. The `blind_spots` list in the same file names four other mechanisms
(`M_STRUCTURAL_BARRIER` advantage 0.371 ALIVE, `M_FORCED_DELEVERAGE` 0.059 ALIVE,
`M_FUNDAMENTAL_PROXY` WEAK, `M_ATTENTION_DELAY` FAMILY KILL) — and **zero of them appear in the
schedule**, including the one scored 2nd-highest and marked ALIVE.

Also note `M_LIQUIDITY_WITHDRAWAL: coverage 0.004, tested 10, verdict UNTESTED` — the top-priority
mechanism is genuinely under-explored, which is the correct reason to weight it. The defect is
weighting it at 100%.

---

### R-16 [INTERNAL, §41] 46 recommendations, 27 open, **~25 of them DEFECTS past grace** — and one of them is the exact fix for R-8/R-9/R-10

```
$ .venv/bin/python scripts/recommendations.py report
recommendations: 46 total | 6 implemented | 3 rejected | 10 scheduled | 27 open
  DEFECT [UNDISPOSED past grace] R0004 (deep_sweep, 4.0d): O2 data-moat: wire hypothesis_novelty
    into live generation + compile ONE canonical machine graveyard (data/gra...
  DEFECT [UNDISPOSED past grace] R0008 (deep_sweep, 4.0d): O7 data-moat: populate-or-retire the
    trials_ledger (0 rows in every DB while docstring claims nothing is valid...
  DEFECT [UNDISPOSED past grace] R0030 (…generation, 1.7d): GATE-OPTIMALITY, measured: stage_a_screen
    needs n_eff >= (1.96/0.03)^2 = 4268 independent obs to call a cell P...
  DEFECT [UNDISPOSED past grace] R0033 (cycle, 1.2d): GATE-OPTIMALITY ROOT CAUSE: validate()'s pbo +
    reality_check gates are CAMPAIGN CONSTANTS…
  DEFECT [SCHEDULED past due] R0002 (max_audit, 4.0d): prompt-doctrine-bloat…
  [+21 more UNDISPOSED past grace]
```

**The finding organs work. The doing organ does not.** §41 states undisposed past 24h is a DEFECT,
not backlog — so this is ~25 concurrent live defects, the oldest at 4.0 days. Implementation rate is
**6/46 = 13%**, and 27 rows have no disposition at all.

Two of the undisposed rows are, verbatim, the fixes for this sweep's largest findings:
- **R0004** — "wire hypothesis_novelty into live generation + compile ONE canonical machine
  graveyard" → this is R-8 (96% of refutations invisible), R-9 (advisory gate, 2-item corpus) and
  R-10 (the same 4 experiments re-run at 97.3% "novel"). Undisposed 4.0 days.
- **R0008** — "populate-or-retire the trials_ledger (0 rows in every DB…)" → this is the unwired
  multiplicity budget that R-9 depends on. Undisposed 4.0 days.

Combined with R-6(g) — inbox item #74, the ~20-line sweep-runner fix, diagnosed on 07-29 and still
unlanded — the pattern is unambiguous and it is the research engine's **binding constraint**: this
desk's diagnostic capability substantially exceeds its remediation capability. Adding another
finder (another audit, another probe, another battery) has near-zero marginal ERV while 27 correct
diagnoses sit undisposed. **L1.13 BOTTLENECK PRIMACY says all engineering effort belongs here.**

---

### R-17 [INTERNAL] Five of seven mining organs cannot leave a log when they die — the failure is in the runner's line ordering

`ops/run_litminer_dig.sh:5` runs `brain_auth_check || exit 1` **before** `mkdir -p
data/cro_ai_logs` and `LOG=…` at `:16-17`. Identical structure in `run_prospector_dig.sh:5` and
`run_dataaxis_dig.sh`. So a quota-dead organ exits **leaving no file at all**:

```
$ ls data/cro_ai_logs/ | grep -E 'frontier|litminer|prospector|dataaxis'
frontier_cn_20260728T1524.log      # 168 bytes -- the ONLY organ dig log on this box
$ cat data/cro_ai_logs/frontier_cn_20260728T1524.log
=== frontier-cn start Tue Jul 28 03:24:39 PM UTC 2026 ===
You're out of usage credits · resets 8pm (UTC)
=== frontier-cn exit 1 at Tue Jul 28 03:48:28 PM UTC 2026 ===
```

`systemctl show` proves litminer, prospector and dataaxis each ran and exited 1 on 07-29, while
`journalctl -u quant-litminer.service` returns "No entries" and the log directory is empty.
**Silent death by construction** — the desk cannot distinguish "never scheduled" from "ran and died"
for three of its mining organs, which is why their output artifacts (`literature_coverage.md`
07-26, `prospector_watchlist.md` **07-18**) went 4 and 12 days stale unremarked.

**And the rotation actively launders the failures.** `ops/run_frontier_rotation.sh:21`:
```bash
bash ops/run_frontier_miner.sh "$r" || echo "…failed"
```
The `|| echo` swallows every non-zero exit, so systemd records `Result=success ExecMainStatus=0`
**while all seven regions failed**. Measured:
```
$ for r in en cn ru kr jp ar br; do …count dig outputs…; done
en=0  cn=1(stub)  ru=0  kr=0  jp=0  ar=0  br=0
$ journalctl -u quant-frontier.service   # 07-25 -> 07-29, 65 lines
ru/kr/jp/ar/br failed on EVERY invocation, each in 8-11 seconds (brain_auth_check exhaustion)
```
Only `en` (07-26, 07-28) and `cn` (07-26, 07-28) ever ran long enough to dig. This is a
**self-greening guard on the FREE-FRONTIER capability** — exit 0 reported for a rotation in which
100% of regions failed. Adjacent instance of the same shape as R-5 (naver) and R-4 (unread
`steps_ok`): three independent organs, one failure pattern — *success is reported by the wrapper,
never measured from the artifact*.

---

### R-18 [INTERNAL] The §33 conversion-priority directive is computed by all five organ runners and then thrown away

```
run_litminer_dig.sh:11        _MINE_PRIORITY="$(.venv/bin/python scripts/mine_gate.py …)"
run_prospector_dig.sh:11      (same)
run_dataaxis_dig.sh:12        (same)
run_frontier_miner.sh:23      (same)
run_blindrediscovery_dig.sh:11 (same)
```
Every one computes `_MINE_PRIORITY`, every one carries the comment "prepend it to this run's
instructions", and **not one interpolates it into its `claude -p` invocation.** The variable is
discarded. So §33's measured-conversion steering — the law that is supposed to make generation follow
evidence rather than enthusiasm — **reaches no organ at all.** An inert lever, five copies.

Related scope holes that make most mined output owe no disposition:
- `_DIG_DOCS` (`scripts/max_audit.py:1881`) is 4 files and **excludes `prospector_coverage.md`** —
  the file where both surviving frontier miners actually write. Their finds are invisible to §33.
- The rogue-doc detector at `scripts/max_audit.py:2193` uses `research.glob("*.md")` —
  **non-recursive**: `glob` sees 50 files, `rglob` sees 90. The entire `deep_sweep/` tree (~1.2 MB,
  17 unscoped numbered cards, all 5 `LIT_*` files) is outside the law. The litminer diagnosed this
  itself — `docs/research/literature_coverage.md:194`: *"docs/research/deep_sweep/ IS UNGOVERNED, AND
  THIS ORGAN CREATED 7 OF THE 15 FILES"* — and it is still ungoverned 4 days later. **This report is
  being written into that ungoverned tree.**

Also: the §33 accounting universe is 5 finds (`scripts/mine_gate.py` → "all 5 carded find(s)
disposed"), `docs/research/mining_record.json` best_finds=5 is 5 days stale, and
`conversion_record.json` has `n_records: 2` — the ratchet that "only moves down" is built on two
observations.

---

### R-19 [FRONTIER-negative, NEGATIVE SPACE] Non-English mining is 4.3% of sourced URLs, translation capability is zero lines of code, and eight named sources that return HTTP 200 today have never been queried

**Measured language coverage:**
```
$ (regex over docs/**.md, ccTLD of every https?:// host)
530 URL references, 134 unique hosts
NON-ENGLISH ccTLD refs: 6/530 = 1.1%
  cyberleninka.ru, journal.kci.go.kr, jvcea.or.jp, www.bk.mufg.jp, www.kci.go.kr
```
**All six non-English URLs in the repo come from ONE file**, `LIT_d_nonenglish_theses.md`, written
07-26 and never extended. Corrected for `.com`-hosted native platforms and verified false positives
(`.tr` → `treasury.gov`/`trycloudflare.com`; `.es` → `esma.europa.eu`), true native-platform URLs are
**23/535 = 4.3%**. The canonical registry `data/data_universe_map.json` (60 source groups, 46 URLs)
is 8/46 non-English, covering KR(5) JP(2) RU(1) — **zero `.cn`, `.br`, `.tr`, `.es`, or
Arabic-region hosts.**

Native-script census (the honest proxy for foreign text actually handled):
```
FILE                              CJK  HANGUL  CYRIL  ARABIC  KANA
LIT_d_nonenglish_theses.md        399     264    683       0     89
search_operator_library.md        134      30    101      20     13
LIT_a / LIT_b / LIT_c / CHARTER     0       0      0       0      0
```
**Arabic: 20 characters repo-wide, all inside one operator template.**

**Translation capability: none.**
```
$ .venv/bin/pip list | grep -iE "translat|deepl|googletrans|argos|transformers|sentencepiece|fasttext|langdetect"
(no output)
```
No library, no API, no model call, no pipeline, no test, no artifact. The doctrine's position is a
prompt clause — `ops/frontier_*_prompt.txt:3`: *"LLM translation is the desk's edge over the
crowd"*; `FREE_DATA_ADDENDA_BCD.md:115`: *"the language barrier IS the moat"*. **The entire moat
rests on one sentence in a prompt whose 5 of 7 regional consumers have never once executed**
(R-17). When the model is quota-dead there is no fallback, and quota-dead is the *normal* state for
ru/kr/jp/ar/br.

**Search Operator Library:** `docs/research/search_operator_library.md`, 34 operators, **all marked
`[active]`, zero ever demoted** (`## ARCHIVED` → "(none yet)") — a ratchet-only accumulator, so
claimed validated-gain is never revisited. Language adaptations: CN 13, KR 12, JP 11, RU 10, PT 4,
BR 1, AR 1, **TR 0, ES 0** — two doctrine-named languages have zero. Lexicons exist for exactly two
languages (EN era-jargon 22 rows, CN crypto-jargon 14 rows). No code parses the file; it is loaded
by prompt text only (`ops/frontier_*_prompt.txt:3`), so its usefulness is gated entirely on R-17's
dead organs. **19 of 34 operators (56%) were handed to the desk by the principal or doctrine, not
mined** — and RU/KR/JP/AR/BR miners have contributed **zero**.

**NEGATIVE SPACE table — the doctrine's named sources, with today's reachability:**

| source | HTTP today | verdict |
|---|---|---|
| **Gitee** | **200** | **NEVER MINED** — every mention is `"NOT DONE THIS RUN … (Gitee/CN-GitHub repo chain, OP-001)"` |
| **Feixiaohao** | **200** | **NEVER TOUCHED** — reachable, never once queried |
| **Xueqiu** | **200** | **NEVER MINED** — sole hit is `"NOT DONE THIS RUN"` |
| **Qiita** | **200** | **NEVER MINED** — asserted "already captured by OP-017", no artifact |
| **Zenn / velog / tistory** | **200** | **NEVER TOUCHED** (zero find-doc mentions) |
| **smart-lab** | **200** | **NEVER MINED** |
| habr | 302 | **NEVER MINED** — "RU practitioner layer … separate ground" (planned) |
| Bilibili | 301 | **NEVER MINED** — all 32 doctrine mentions are tool-capability notes |
| Naver | 302 | collector exists, **BLOCKED**: no credentials; `data/naver_krsearch.jsonl` MISSING (R-5) |
| Baidu Tieba | **403** | **NEVER MINED** — and misfiled: `docs/graveyard.md:94` calls it *"unreachable"*; 403 is a bot policy, and `OP-026`'s paywall-substitute ladder applies |
| DCInside / 5ch | — | **NEVER MINED** — `grade: needs-legitimacy-review`, never reviewed |
| Yandex | — | **NEVER TOUCHED** (0 uses as a search engine) |
| **Turkish (btcturk/paribu)** | — | **NEVER TOUCHED**, 0 operator adaptations |
| **Spanish (any)** | — | **NEVER TOUCHED**, 0 operator adaptations |
| **Arabic (any community)** | — | **NEVER TOUCHED** |
| **Portuguese/BR (any)** | — | **NEVER TOUCHED** |
| CSDN | 200 | mined once (07-19), Chinese RSRS, EV-killed |
| 8btc | 000 | mined once — real find, 2017 banzhuan thread via Wayback, depth-2 |
| ChainNode | DNS fail | never mined; genuinely unreachable |
| cyberleninka | 200 | mined once — honest null (LIT_d D-4) |

**The negative space is not a network problem.** Gitee, Feixiaohao, Xueqiu, Qiita, Zenn, velog,
smart-lab and cyberleninka all return **200 from this box today**. They were never queried. Per the
FREE-FIRST protocol, "no free source exists" requires a documented failed search — these are not
failed searches, they are unattempted ones, and several are recorded in desk docs as *"NOT DONE THIS
RUN"* going back to 07-19.

---

### R-20 [INTERNAL] `fetch_video_transcript.py`: YouTube works, Bilibili has never worked, doctrine asserts both, artifacts are zero — and the script cannot persist output

Live test today:
```
$ .venv/bin/python scripts/fetch_video_transcript.py dQw4w9WgXcQ
[transcript via https://api.piped.private.coffee] 2089 chars      # YouTube: WORKS
$ (3 real BVids from api.bilibili.com/x/web-interface/popular)
bilibili: no public subtitles for BV1rW326hEKe (…)   x3           # Bilibili: 0/3
```
`ops/principal_doctrine.txt:205` asserts *"fetch_video_transcript.py now reads YouTube and Bilibili
captions free, making video a first-class dig source for every organ."* The YouTube half is true.
The **Bilibili half has never been demonstrated end-to-end** — the API is reachable and `view`
returns Chinese titles, but the caption path returned nothing on every video tried. A doctrine line
asserting an unproven capability is exactly the SCOPE-THE-NEGATIVE-RESULT failure inverted: the desk
scoped a *positive* result it had not verified.

**Zero artifacts, and structurally so:**
```
$ find . -path ./.git -prune -o \( -iname "*transcript*" -o -iname "*caption*" -o -iname "*subtitle*" \) -print
./scripts/fetch_video_transcript.py        # the script itself, nothing else
```
`main()` at `:99-100` writes to **stdout only** — there is no persistence path, so even a successful
fetch leaves no evidence and cannot be cited, re-read, or dedup'd. `docs/research/video_locked_log.md`
(mtime 07-20) is a **header with zero rows**. It is wired into 9 prompts
(`ops/frontier_{en,cn,ru,kr,jp,ar,br}_prompt.txt:79`, `litminer_dig_prompt.txt:94`,
`prospector_dig_prompt.txt:96`) — 5 of those 7 frontier prompts have never executed (R-17).

---

### R-21 [INTERNAL] Literature mining: a real arXiv pipeline, 83 papers ingested, **zero papers have reached a screen**

The pipeline is genuine: `scripts/collect_research_feed.py`, keyless arXiv Atom API over
`q-fin.TR + q-fin.PM + q-fin.ST`, 25/day, dedupes into `docs/research/feed_inbox.md`, scheduled from
`daily_research_cycle.py:43`.
```
$ python3 -c "…len(json.load(open('data/research_feed.json'))['seen'])…"
83
```
83 papers ingested; triage is well-reasoned (~45 dispositioned with named reasons in the 07-10 and
07-17 batches). **Outcome: zero papers have reached a screen.** The only traceable paper→decision
path is a rejection — `research_agenda.json:139`:
*"quarter_hour_periodicity_crypto_futures (REJECTED 2026-07-17 by EV gate: ev 0.0006,
crowded_known; arXiv 2607.09426)"*. One more was folded into `engineering_backlog.json` as a design
reference. The litminer's own closing commit is honest about it: `b1168be` *"lit run 3 CLOSE:
exhaustion state per ground + honest nulls (net new tradeable axes: ZERO)"*.

And the collector is **English-only by construction** — `collect_research_feed.py:8` states
`SSRN/blogs/changelogs deliberately NOT scraped`. SSRN, Semantic Scholar, Crossref, OpenAlex, CNKI,
J-STAGE, KCI and cyberleninka appear **only in prose**; none has an ingestion path. It also fails 6
of 7 runs on network timeout (R-3), so even the English arm is ~14% reliable.

The organ that should convert papers into hypotheses is empty:
`docs/research/discovery_hypotheses.md` holds **2 hypotheses, both `[status: open]`, both
`outcome: —`, untouched since 2026-07-19** (11 days). It *is* in `_DIG_DOCS`, so §33 watches it —
there is nothing to watch.

---

### R-22 [EXTERNAL, and the one genuine strength] Repo mining is the desk's best-converted channel — and it is 100% English

`docs/REPO_EXTRACTION.md` Tier-1 records five adopted repos with **named wired code**:

| repo | wired into |
|---|---|
| `nkaz001/hftbacktest` | `libs/backtest/queue_fill.py` (queue-priority fill) |
| `nkaz001/algotrading-example` | `libs/research/microstructure.py` (`book_imbalance`, `depth_imbalance_signal`) |
| `hudson-and-thames/mlfinlab` | triple-barrier labels (AFML ch.3) |
| `statsmodels` + `arch` | `libs/research/stationarity.py` |
| `polakowo/vectorbt` | pinned as `[crosscheck]` |

This is real, verifiable conversion — mined artifact → named module → used by the screen harness. It
is the pattern every other mining channel should be measured against, and it is the strongest
evidence in this report that the desk's mining doctrine *works when the organ actually runs*.

**It is also entirely English GitHub.** `OP-001` prescribes a Gitee chain and `OP-011` a
scraper-as-evidence path for Gitee; neither has executed. `data/generated_collectors/` is **empty
(0 files)**. No Gitee/CSDN repo has produced a wired collector or a screened axis. The channel with
the highest measured conversion rate is the one where the doctrine's language mandate has zero
coverage — which under §33's own `mine_generation_priors.json` logic ("favour the top, starve
anything under 25%") argues for **CN repo mining as the single highest-expected-conversion
unexploited surface on the board**.

---

### R-23 [INTERNAL, **the single sharpest finding in this sweep**] The novelty gate has 0% recall on its own graveyard, and its threshold is mathematically unreachable

The UNIVERSAL DUTY SET makes this gate mandatory: *"before spending compute on any new hypothesis,
screen it against the graveyard via libs/alpha_factory/hypothesis_novelty."* Here is every verdict it
has ever produced, in the repo's entire history:

```
file                          candidate                               nov    sim  redund n_priors
idle_axis_screen.json         onchain_activity::throughput_multiweek  0.865  0.135  False    46
idle_axis_screen.json         crypto::taker_flow_absorption           0.869  0.131  False    46
idle_axis_screen.json         try_premium::stablecoin_rent            0.881  0.119  False    40
fred_macro_screen.json        dollar_funding_squeeze                  0.885  0.115  False    57
fred_macro_screen.json        reserve_quantity_impulse                0.892  0.108  False    57
fred_macro_screen.json        equity_vol_deleveraging                 0.884  0.116  False    57
fred_macro_screen.json        curve_slope_policy_path                 0.884  0.116  False    57
fred_macro_screen.json        nominal_yield_opportunity_cost          0.884  0.116  False    57
screen_exchange_netflow.json  (nearest kimchi-premium)                0.973  0.027  False     2

accept rate 9/9 = 100.0%    is_redundant=True: 0
nearest_similarity: min 0.027  max 0.135   vs threshold 0.700  -- 5.2x below
HISTOGRAM  [0.0,0.1): 1   [0.1,0.2): 8   [0.2,0.7): 0   [0.7,1.0): 0
```

**Nine verdicts, nine accepts, and the closest call was 0.565 away from the bar.** Under
GATE-OPTIMALITY DUTY that is a zero-information gate by definition.

**It is not merely unexercised — it has 0% recall.** Positive control: feed each graveyard row's own
name back as a candidate with that exact row in the corpus:
```
$ .venv/bin/python  # hypothesis_novelty(name, priors=_graveyard_priors())
RECALL on exact graveyard NAMES: 0/43 = 0.0%   (threshold 0.70)
sim vs own graveyard row: mean 0.212  median 0.176  max 0.667  min 0.066
how many reach 0.70? 0
nearest_id was the CORRECT row in 34/43 cases
```
**The gate finds the right prior 79% of the time and then declares it novel.** Feeding it a verbatim
copy of a dead idea does not trip it.

Three structural causes, each independently sufficient:

1. **The threshold is arithmetically unreachable.** Jaccard ≤ min(|A|,|B|)/max(|A|,|B|), so 0.70 is
   impossible whenever token-set sizes differ by more than 1.43×. Prior statements are built as
   `f"{name} {verdict} {lesson}"[:1500]` (`scripts/screen_idle_axes.py:74`) → median 32, mean 48.7,
   max 152 tokens. Measured unreachability per candidate:
   ```
   crypto::taker_flow_absorption          |A|=37  0.70 UNREACHABLE vs 33/47 priors (70%)
   onchain_activity::throughput_multiweek |A|=41  UNREACHABLE vs 35/47 (74%)
   try_premium::stablecoin_rent           |A|=51  UNREACHABLE vs 43/47 (91%)
   a short candidate |A|=5                        UNREACHABLE vs 44/47 (94%)
   ```
   The gate cannot fire for most (candidate, prior) pairs *no matter what the text says*.
2. **The mechanism term — the part the docstring says dominates — is dead code for the graveyard.**
   `_similarity` = `0.7 * feature_jaccard + 0.3 * statement_jaccard` **only if both sides declare
   features** (`hypothesis_novelty.py:55-108`). `_graveyard_priors()` never passes `features=`, so
   all 43 graveyard priors default to `()`: `priors WITH features: 4 | WITHOUT: 43`. The 0.7-weighted
   term is live for 4 of 47 priors.
3. **The `len>=3` tokenizer erases horizons — so the metric is wrong in BOTH directions.**
   `1d 3d 5d h1 m5 oi ls fx ic` are all dropped; `20d` is kept. Measured consequence:
   ```
   prior:     "metal construction: XAU_mom20->BTCminusALT_5d  -- ... -> BTC-minus-ALT 5d."
   candidate: "metal construction: XAU_mom20->BTCminusALT_20d -- ... -> BTC-minus-ALT 20d."
   jaccard = 1.000   redundant = True
   ```
   Two *distinct pre-registered trials* score as an exact re-test. So the gate simultaneously misses
   real duplicates and would false-flag legitimate horizon variants — the worst of both errors.

**Two measured false negatives on hypotheses the desk itself calls dead:**
- `try_premium::stablecoin_rent` scored **0.881 novel**, nearest `collector:onchain_activity_throughput`
  — while `docs/graveyard.md:38` holds `try_premium_timing (Turkey capital-control)` and
  `screen_idle_axes.py:413-415` states in its own docstring that `try_premium` *"is graveyarded …
  re-testing an identical hypothesis is forbidden."* 9 cells ran.
- Re-run **today**, with the exchange_netflow kill now in the corpus:
  `novelty 0.918, redundant False, nearest 'exchange_netflow (Coin Metrics netflow_ntv…)'`.
  **The desk could re-spend the 16-year netflow screen tomorrow and the mandated gate would
  greenlight it.** (This closes the loop on R-10: not an accident, a guaranteed repeat.)

---

### R-24 [INTERNAL] The gate reads 7.2% of the desk's record, is scheduled nowhere, and a SECOND forked gate — the only scheduled one — disagrees with it

**Corpus coverage:**
```
research_memory rows                    152   (124 failures, machine-readable, richly annotated)
research_candidates rows (3 DBs)        505   (all status='rejected')
docs/graveyard.md rows                   43   <-- the ONLY thing the gate reads
TOTAL available record                  657
gate corpus                              47   = 7.2%   (43 graveyard + 4 hardcoded)

$ grep -rn "research_memory" --include="*.py" scripts/ libs/ | grep -i "prior\|novel"
(empty)
```
**No caller anywhere converts `research_memory` into a `PriorIdea`.** `data/graveyard_priors.json`
— the canonical machine graveyard — **does not exist**. R0004 in the ledger says exactly this and is
still `status: open` (R-16).

Worse, `screen_exchange_netflow.py:96-106` runs on **2 hand-typed priors, one of which is
`kimchi-premium` — a RETRACTED result** (`lesson="Retracted: ~73% timestamp artifact"`). The most
recent gate invocation on this desk (07-30 02:41) measured novelty against a known artifact.
And the `n_priors: 40` verdict in `idle_axis_screen.json` is a **stale carried-forward row**
(`screen_idle_axes.py:459`) — the corpus is now 47 and that verdict was never re-scored.

**Scheduling:**
```
$ grep -rn "hypothesis_novelty" --include="*.py" libs scripts app api tools | grep -v hypothesis_novelty.py
libs/autodiscovery/generation_roi.py:23,76      <- dead lib, unscheduled caller, no artifact
scripts/screen_fred_macro_axis.py:90,189
scripts/screen_idle_axes.py:50,96
scripts/screen_exchange_netflow.py:42,93
$ crontab -l | grep -E "screen_idle_axes|screen_fred|screen_exchange|hypothesis_generator"
(empty)
$ grep -rn "screen_idle_axes|screen_fred_macro|screen_exchange_netflow" scripts/daily_research_cycle.py ops/ .github/
(empty)
```
**Four non-test call sites, none scheduled.** The mandatory gate fires only when a human hand-runs a
screen — three times ever.

**Every live generation path bypasses it:**
- The only live generator (`libs/autodiscovery/crypto_adapter.py`, 434 candidates) dedups on
  `content_hash = sha256(family+subtype+symbol+sorted(params))` (`libs/autodiscovery/memory.py:31-34,
  59-63`) — byte-exact, semantically blind, never touches the graveyard.
- `scripts/hypothesis_generator.py:165-168` rolls **its own** dedup (reject if any name-word of
  len>4 intersects `dead_tok`) — a single-word veto with no threshold. It has never run anyway.
- `breadth_expander.py`, `conversion_engine.py`, `run_axis_generate.py`: no novelty call at all.

**A SECOND, FORKED GATE EXISTS — and it is the only one that is scheduled.**
`scripts/alpha_lifecycle.py:169-219` implements an independent `novelty()`: tokenizer `[a-z]{4,}` +
stopwords, thresholds **0.5 DUPLICATE / 0.25 adjacent** (not 0.7), plus a keyword `_DEAD_MECHS`
family filter (`M_PRICE_PATTERN, M_ATTENTION_DELAY, M_SKILL_PERSISTENCE, M_FLOW_PRESSURE`) that gate
A has no equivalent of. It **is** in the daily cycle (`daily_research_cycle.py:74`) — but it only
scores **3 hardcoded demo strings** (`alpha_lifecycle.py:243`).

They contradict each other on a real candidate:
```
candidate = the exchange_netflow statement
gate B (alpha_lifecycle.py:188, SCHEDULED):  verdict=DEAD-MECHANISM  dead_mechanism=M_FLOW_PRESSURE
gate A (hypothesis_novelty, MANDATED):       novelty=0.918  redundant=False
as actually logged 07-30 02:41 (2 priors):   novelty=0.973
```
`M_FLOW_PRESSURE` (keywords `netflow`, `inflow predicts`, `outflow predicts`) landed in commit
`8581024` dated **2026-07-28 — two days before** the netflow screen spent 12 cells. **The scheduled
gate would have flagged it; the mandated gate was the one wired in, and it said novel.** The desk has
two novelty gates, and it wired the blind one into the screens and the sighted one into three demo
strings.

---

### R-25 [INTERNAL] Generation inventory: the LLM idea tier has never run, the alpha_factory tier is 42 days idle, and exact-hash dedup blocks nothing

**ALIVE (artifact written 07-30 08:40–08:41):** `libs/autodiscovery/*` via `run_crypto_research.py`
(→ `web/autodiscovery_crypto.json`, 434 cumulative tested, **0 survivors ever**, all 434
`status=rejected`); `breadth_expander.py` (→ 217 rows); `conversion_engine.py` (→ 328 items).

**DEAD:**
- `scripts/hypothesis_generator.py` — output `data/hypothesis_queue.jsonl` is **MISSING**. Its own
  docstring line 3 reads `*** UNTESTED (OpenRouter 402) ***`, corroborated by
  `scripts/research_erv.py:152`: *"hypothesis queue is EMPTY (hypothesis_generator has never run --
  402)."* Not in cron. **The desk's LLM hypothesis generator has never produced a single
  hypothesis.**
- `libs/alpha_factory/{hypothesis_engine, alpha_discovery_engine, concept_evolution_engine,
  idea_ranking_engine, alpha_factory_controller}.py` — a closed import loop reachable **only from
  `tests/alpha_factory/`**, all mtime 2026-06-18. **42 days idle.**
- `data/sor_autodiscovery.sqlite:research_candidates` — 57 rows, all created 2026-06-20. **Frozen 40
  days.**
- `libs/autodiscovery/generation_roi.py` — sole caller unscheduled, writes no artifact.
- `reports/autodiscovery/` Jun 20 (40d); `research_agenda.json` Jul 22 (8d).
- `trials_ledger` — the hash-chained pre-registration ledger — **0 rows in all three DBs**.

**Measured duplicate work inside the one live generator:**
```
data/sor_crypto.sqlite (434 rows)
distinct (family,subtype,symbol) triples  : 248
triples tested more than once             : 124
rows repeating an already-tested triple   : 186   (43% of the store)
distinct content_hash                     : 434   <-- exact-hash dedup blocks NOTHING
```
And across the desk's own written record (43 graveyard names + 150 research_memory statements,
18,528 pairs, scored with the gate's own `_jaccard`):
```
pairs >= 0.50 : 135      pairs >= 0.70 (the gate's own bar) : 19      pairs == 1.000 : 4
sim=1.000  XAU_mom20->BTCminusALT_5d          |  XAU_mom20->BTCminusALT_20d
sim=1.000  "NO MECHANISM DECLARED ... futclose_daily"  recorded 4x under hypothesis/method/dataset
sim=0.960  cme_calendar_spread_ann->btc_1d    |  ->btc_20d
sim=0.838  Stage-A cm_netflow_native_btc      |  cm_netflow_native_eth
sim=0.826  fed_d20_neg_rrp->btc_20d           |  fed_d20_neg_tga->btc_20d
```
**19 pairs in the desk's own record sit at or above its own redundancy bar** — and the gate scored
none of them, because it was never pointed at them.

---

### R-26 [INTERNAL, cost] The doctrine prepended to every organ call is 38.3k chars — 2.4× its own guard — and it grew 42% *after* the defect was raised

```
$ wc -c ops/principal_doctrine.txt
38257
$ grep -n "16000" scripts/max_audit.py
1026:    if doc.exists() and doc.stat().st_size > 16000:
1020:  # (a) Doctrine bloat: the doctrine is prepended to EVERY organ call; past ~16k chars the ...
$ python3 -c "…max_audit_report.json live[25]…"
prompt-doctrine-bloat: "principal_doctrine.txt 27.0k chars (>16k) -- consolidate the stacked axiom
  blocks into tighter prose (preserve every commitment, cut the repetition); every organ pays this
  context"
$ git log --format="%ad %h" --date=short -- ops/principal_doctrine.txt | head -6
2026-07-30 d0b8923 / 833831c / 99b0e88 / 1c7328d / 4366388 / a1126a0     # six commits today
```
Three separate facts here, all bad:
1. **2.4× the guard.** 38,257 vs a 16,000 limit. At ~4 chars/token that is ~9.5k tokens of preamble
   on **every organ call** on a box whose binding constraint is a single quota-limited seat (R-6).
   The sweep spends this 8 times per run plus ~1,900 auth pings' worth of session overhead.
2. **The live defect message understates it by 42%** — the audit reports 27.0k while the file is
   38.3k, because it grew across six commits today. So the guard is *lagging its own subject*, and a
   reader of `max_audit_report.json` gets a number 11k chars stale.
3. **R0002 — the recommendation to fix it — is `SCHEDULED past due` at 4.0 days** (R-16). The
   doctrine grew 42% *while its own remediation ticket sat overdue.* A ratchet running the wrong
   direction.

This is a genuine tension, not a cheap shot: the doctrine's content is load-bearing and this audit is
demonstrably better for having it. But "every organ pays this context" is the desk's own phrasing, and
under L1.13 the payer is the bottleneck resource. The fix is compression, not deletion — and it is
overdue.

---

### R-27 [EXTERNAL, cost inversion] The external panel produces real adversarial value and its quality is measured at **zero**

The panel is genuinely the desk's strongest external-perspective organ, and it works:
`docs/research/panel_inbox.md` 60KB (updated today 08:15), `data/external_panel_log.jsonl` 1.6MB,
`panel_rulings.md` with categorised REJECTED(7) / IMPLEMENTED(5) / QUEUED(6) / FLAGGED(11). The
rulings are substantive — e.g. a near-unanimous 12/12 adversarial pushback that correctly overturned a
CRO first-pass diagnosis, and a `grok` ruling on shadow-clock contamination verified against code.
**This is L1.7 ADVERSARIAL VALIDATION working as designed.**

Two defects sit on top of it:

**(a) The scorecard that decides which panelist is worth paying is empty and 13 days stale.**
```
$ ls -la data/panel_scorecard.json data/panel_verdicts.jsonl
   4981  Jul 17 08:55  data/panel_scorecard.json      # 13 days stale
  18366  Jul 21 09:27  data/panel_verdicts.jsonl      #  9 days stale
$ python3 -c "…sum over providers…"
providers: 26   TOTALS: {'responses': 40, 'actioned': 6, 'validated': 2, 'falsified': 0, 'scored': 2}
hit_rate non-null: 0
```
Its own policy: *"hit_rate = validated/(validated+falsified); null until >= 5 scored findings.
Down-weight/drop persistent low scorers at monthly governance."* With **2 scored findings across 26
providers and 0 non-null hit rates**, that policy can never trigger. Meanwhile the panel costs real
money — `data/panel_budget.json` sets a **$120/mo envelope**, and `panel_budget_state.json` shows
`usage_at_run_start: 60.59`. **The desk is spending ~$60/mo on external review with zero measurement
of which reviewer earns it.** That is a COST-INVERSION finding: a paid capability whose value signal
is unbuilt, while the free capability that would substitute (structured self-adversarial probes) is
also unbuilt.

**(b) The rulings pipeline stopped 12 days ago while intake kept running.**
```
$ grep -oE "2026-0[0-9]-[0-9]{2}" docs/research/panel_rulings.md | sort | uniq -c
   1 2026-07-16    6 2026-07-17    2 2026-07-18    1 2026-07-30
```
Nine of the ten dated rulings are from 07-16→07-18. The file's mtime is today, but its *content*
last gained substance 12 days ago — another freshness-field-vs-content trap (same shape as
`web/pilot.json`, R-2.4). And 17 items sit in QUEUED(6)+FLAGGED(11), several referencing GAP rows
from 07-17. `panel_verdicts.jsonl` — where dispositions are recorded — went silent 07-21 while
`panel_inbox.md` kept growing to 60KB. **Intake outran disposition by 9 days**, the identical §41
pattern as R-16, one level up.

Honest counterweight: the FLAGGED reasons I read are *good* — e.g. rejecting a proposal to relax a
regime gate into a haircut on the explicit ground that it "effectively LOOSENS a validation gate --
HARD line". The judgment is sound. The bookkeeping is broken.

---

### R-28 [FRONTIER / GREENFIELD] A strictly better similarity function is **already written, already in this repo**, and pointed at three demo strings

The mandated novelty gate uses hand-rolled token Jaccard on `len>=3` tokens (R-23). Meanwhile:

```
$ .venv/bin/python -c "import sklearn, numpy, scipy, pandas, pyarrow"     # all OK
   OK numpy / scipy / sklearn / pandas / pyarrow
   MISS torch / sentence_transformers / faiss / rapidfuzz / tiktoken
$ grep -n "idf\|cosine" scripts/knowledge_engine.py
80:def _idf(docs: list[dict]) -> dict:
88:def retrieve(query: str, docs: list[dict], idf: dict, k: int = 4) -> list[dict]:
97:        num = sum(q[w] * t[w] * (idf.get(w, 1.0) ** 2) for w in q if w in t)
98:        den = (math.sqrt(...) * math.sqrt(...))          # TF-IDF cosine
```

**`scripts/knowledge_engine.py:80-99` already implements IDF-weighted cosine retrieval** — which
solves every one of R-23's three structural causes at once: IDF down-weights the boilerplate that
inflates prior token-sets (cause 1), cosine is not bounded by set-size asymmetry (cause 1), and
weighting by rarity makes the mechanism words dominate without needing a declared `features` field
(cause 2). And `sklearn.feature_extraction.text.TfidfVectorizer` with `analyzer='char_wb',
ngram_range=(3,5)` — **zero new dependencies** — additionally fixes cause 3, because character
n-grams preserve `1d`/`5d`/`20d` that the `len>=3` word tokenizer deletes.

So the desk owns a better tool, wired to **three hardcoded demo query strings**
(`knowledge_engine.py:154-156`), with `grep -n "argparse\|sys.argv"` → no matches (R-12), while the
*mandated* gate runs the weaker metric on 7.2% of the corpus and has never rejected anything.

This is the highest-leverage single change in this report: **point the existing TF-IDF cosine at the
existing 657-row record, with `research_memory` as the corpus.** It is not a research project. It is
plumbing that already exists on both ends.

**Genuine frontier gap (what is NOT here):** no local embedding model (`torch`,
`sentence_transformers` absent), so semantic similarity across paraphrase ("stablecoin rent" vs
"funding cost of parked dollars") remains out of reach for a pure-lexical metric. Two free routes
exist and neither has been attempted: (a) a small ONNX/GGUF embedding model run locally on CPU —
one-time download, no per-call quota, fixes paraphrase permanently; (b) an LLM-as-judge pass over the
~50 nearest lexical candidates, ~1 call per new hypothesis, which the desk's own seat can afford at
the current generation rate of **zero per day** (R-1). Under EXHAUSTION/no-ceiling, "lexical Jaccard"
is not a ceiling — it is a 2010 baseline nobody has tried to beat.

---

### R-29 [FUTURE] With 2-3 years of compute/AI/public-data, this engine is redesigned around three inversions

Not speculation for its own sake — each inversion is named because a *measured* defect in this report
disappears under it.

1. **Memory becomes the queryable substrate, not a log.** Today: 657 records, 47 readable by the
   gate, 0 readers for three stores, `predecessor_id` 0/150 (R-8, R-12, R-24). Redesigned: every
   experiment is a node with typed edges (mechanism, axis, target, horizon, data-source, outcome,
   failure-mode), embedded and indexed, so the load-bearing question the kimchi and Turkey-premium
   retractions raise — *"what have we learned about timing artifacts across all axes?"* — becomes a
   single query instead of an impossible one. This kills R-8, R-10, R-12, R-23, R-24 simultaneously,
   which is why it ranks first in §3.
2. **Generation becomes mechanism-conditioned synthesis, not grid enumeration.** Today: 40 schedule
   items = 1 mechanism × 1 transform (R-15), and 434 candidates = 248 triples with 43% repeats
   (R-25). Redesigned: an LLM proposes *mechanisms* against the ingested-axis inventory and the
   graveyard, the grid is generated *downstream* of an accepted mechanism, and every cell is
   pre-registered into a live `trials_ledger` (which today has **0 rows**). Generation volume then
   scales without inflating the multiplicity denominator with near-duplicates.
3. **The quota bottleneck is designed around instead of collided with.** Today: sequential 8-auditor
   loop, ~2.1 completions/window, position 7 never reached, 98.3% dead probes, 38.3k-char preamble on
   every call (R-6, R-26). Redesigned: cheap deterministic organs do all retrieval/screening locally
   (they already can — sklearn is installed), and the LLM seat is spent only on the irreducibly
   generative steps, with rotation so no position is structurally starved.

The honest constraint that does NOT go away: forward-clock evidence needs calendar time
(`needs_days: 40`). No amount of compute compresses that, which is why R-14's 45-day window is a real
design problem and not just a bug.

---

### R-30 [GREENFIELD] Rebuilt from scratch today with only validated knowledge, ~60% of the current research engine would not be built

Scoring the existing architecture on baggage / lock-in / replaceability:

| component | keep? | evidence |
|---|---|---|
| `libs/research/axis_screen.py` (power analysis, de-contamination, residual IC, forward-clock registration) | **KEEP — the crown jewel** | It caught Coinbase-premium AND Turkey-premium as pure timing artifacts, and a sign-flip on netflow that "every other heuristic called an edge" |
| `docs/GAP_REGISTER.md` + `scripts/recommendations.py` | **KEEP** | genuinely drives work; re-ranked today (R-31) |
| research_memory schema (12 cols, mechanism+lesson+metrics) | **KEEP the schema** | 146/150 lessons populated, mean 268 chars — the data is excellent (R-8) |
| external panel | **KEEP, add scoring** | real adversarial overturns (R-27) |
| repo-extraction pipeline | **KEEP** | 5 repos → named wired modules; best-converted channel (R-22) |
| `libs/alpha_factory/*` (5 engines, controller, research_graph) | **DELETE** | test-only for 42 days, vocabulary-mismatched, no persistence (R-8, R-25) |
| `libs/discovery/{hypotheses,factory,signals}` generation half | **DELETE** | test-only |
| `libs/autodiscovery/generation_roi.py` | **DELETE** | unscheduled, no artifact |
| `scripts/hypothesis_generator.py` | **DELETE or wire** | never run once; docstring still says `*** UNTESTED (OpenRouter 402) ***` |
| `libs/research/information_value.py` | **REDESIGN** | algebraic constant; 0/1244 lessons (R-2) |
| `scripts/knowledge_engine.py` | **REDESIGN — keep the TF-IDF core, delete the hardcoded graph** | 9 hardcoded causal tuples, 3 hardcoded queries, no CLI (R-12, R-28) |
| two forked novelty gates | **MERGE into one, TF-IDF, corpus = research_memory** | they contradict each other on live candidates (R-24) |
| `web/pilot.json` "scale-or-not" card | **DELETE** | cannot change value; the decision it exists to inform ("rent hardware?") is already answered |

L1.12 PROVISIONAL ARCHITECTURE says justify every component by marginal ERV and delete dead weight
ruthlessly. **~13 modules here have negative marginal ERV** — they consume audit attention, appear in
coverage metrics as if live, and create the false impression that hypothesis generation is a solved,
staffed capability. `libs/alpha_factory` in particular is actively harmful: it is where a reader
would *look* for the learning loop, and it has been a no-op for 42 days.

---

### R-31 [INTERNAL — nothing found, and that is the finding] The GAP register is the one process organ that genuinely works

I went looking for the same rot here and did not find it.

```
$ grep -n "Re-ranked" docs/GAP_REGISTER.md | tail -1
461:_Re-ranked 2026-07-30T07:35Z. **One move, and one deliberate un-move.** …
$ grep -cE "^\| *#?[0-9]+" docs/GAP_REGISTER.md      -> 89 rows
$ grep -oiE "\| *(open|closed|deferred|retired|done)" … | sort | uniq -c
   53 open   8 closed   7 deferred   6 retired   3 done
```
Re-ranked **today**, stamped as the law requires, 483 lines. And the re-rank prose is the highest-
quality reasoning artifact I read in this sweep — it records a **deliberate non-advance** with its
measurement (`pbo 0/9 → 6/9`, `reality_check 9/9 → 2/9`, "the constant was welded *open* on RC, not
only shut on pbo"), it reverts a change that measured well because the positive control is still
broken, and it **corrects its own prior finding by name**: *"I had also recorded (F0007) that the
migration's safety precondition was already met… **that was wrong**… conflating the two is exactly how
a phantom-edge-critical change gets waved through."*

That is L1.7 and L1.17 executed properly, unprompted. It is also the proof that the desk's *judgment*
is not the problem — R-16's 27 undisposed recommendations are a throughput failure, not a discernment
failure.

The one caveat worth naming: **53 open vs 8 closed** means the register is accumulating ~6.6:1, and
`#71` has been "blocked on a principal/panel ruling since 07-26 (4 days)". The register names its own
staleness rather than hiding it — correct behaviour — but a 6.6:1 open:closed ratio is the same
bottleneck R-16 measures from the other side.

