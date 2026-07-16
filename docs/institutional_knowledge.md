# Institutional Knowledge — the desk's compounding encyclopedia

The CRO loop APPENDS to this every cycle it learns something durable. It is the memory that makes
research cheaper over time: read it before proposing an idea, and never re-learn a lesson already here.
Companion: the code gate `libs/research/alpha_economics.py` (scores ideas by EV before effort) and
the graveyard in `web/discovery.json`.

## Prime directive
Maximize **expected log-growth per research-hour**, not the number of alphas explored. Answer
*"should we build this?"* (EV gate) before *"can we build this?"* (backtest). Free-data-first: before
naming a paid vendor, ask **"can 90% of this be approximated for free?"** — usually yes.

## Meta-learnings (patterns over outcomes → these are the `_PRIORS`)
- **Funding/carry is the lone repeat survivor.** Every price-only family died; carry has a real risk
  premium (leverage demand) → `funding_family` prior ×2.0.
- **Price-only edges mostly die net-of-cost.** momentum, reversal, low-vol all rejected: reversal &
  leadlag had positive Spearman IC but **negative gross Sharpe** — IC lives mid-distribution, the
  tradeable top/bottom buckets don't carry it. Low-vol *inverts* in crypto (lottery demand). → `price_only` ×0.30.
- **Narrow breadth starves everything.** Options VRP had the campaign's best IC (+0.06) but breadth 2
  → IR = IC·√breadth ≈ nothing. Good signal ≠ tradeable. → `narrow_breadth` ×0.25.
- **Positive IC ≠ profitable strategy.** Never promote on IC alone; require net-of-cost tradeable P&L.
- **Turnover cost kills thin edges** unless maker-first execution recovers half the fee. → `high_turnover_no_maker` ×0.50.
- **No economic mechanism → overfit.** A data-mined signal with no risk-premium story won't persist;
  a fat backtest Sharpe (e.g. the 9.84 that DSR killed) is a red flag, not a green one. → hard kill.
- **The binding constraint is DATA, not architecture.** 302 lib modules, ~0 validated alphas; the
  lever is genuinely-new (mostly free) data + calendar-time forward validation, not more code.

- **On a two-venue hedge, account BOTH sides' realized PnL symmetrically (2026-07-09).** The carry
  book computed net = spot OPEN marks + futures-account equity delta. The futures delta keeps every
  closed perp leg's realized loss forever; the closed spot legs' realized gains sat invisibly in the
  spot wallet → a phantom −$394 "loss" that grew with every close (true book: ≈ breakeven). Any
  time one leg is measured by ACCOUNT DELTA and the other by POSITION MARKS, realized PnL leaks.
  Fix: bank realized spot PnL in state at close; risk controls must judge COMBINED equity or a
  broad rally reads as ruin on the futures account and flattens a perfectly-hedged book.
- **Paginate every venue history endpoint (2026-07-09).** Binance income serves ≤1000 rows/call; a
  busy book exceeds that in days, after which funding/realized/commission all silently understate
  and the numbers LOOK plausible. Truncation is the failure mode that never throws an error.
- **Rate-tie churn: a rank cutoff through tie groups is a lottery (2026-07-09).** 277 perps had
  positive funding, 42 exactly at the 1bp default floor; "hold while in top-60" made hold-set
  membership random → 159 closes in week one, median hold 2.9h, fees (−$60) ≈ the entire funding
  harvest (+$39). Funding pays 8-hourly: closing before one funding event is PURE cost. Hysteresis
  must key on the ECONOMIC condition (funding > 0), never on a rank cut through ties.
- **Heartbeat liveness ≠ data liveness (2026-07-09).** `liquidation_listener.py` connected to
  Binance mainnet WS, held a fresh heartbeat, and reported "LISTENING" for 14 straight days while
  archiving ZERO real events. Root cause: Binance's `fstream.binance.com` completes the WS handshake
  (HTTP 101) from this network but silently drops every subsequent data frame — verified by testing
  the highest-frequency stream on the exchange (BTCUSDT `aggTrade`, normally many msgs/sec) for
  150s+, with and without permessage-deflate, getting exactly zero messages, while the same process
  got Binance TESTNET data instantly, Bybit data instantly, and a generic echo server instantly. A
  silent geo/network block that permits the handshake but withholds the payload is indistinguishable
  from "the process is fine, the market is just quiet" if the only signal you check is a heartbeat
  file. Fix: any listener for a genuinely sparse event stream needs a SECOND signal — heartbeat
  proves the loop is alive, a separate "time since last real payload" check (with a generous but
  finite threshold, `data_health.py` now uses 24h) proves the pipe itself is alive. Switched the
  liquidation source to Bybit's public `allLiquidation` stream (same economic mechanism — forced-
  liquidation overshoot mean-reversion — different venue), which the network verified reachable.
- **venv-launched processes on this machine show a paired system-Python312 PID -- cause unresolved,
  do not over-interpret it as a duplicate scheduler (2026-07-09).** Found `run_cashcarry_executor.py
  --live` visible as TWO PIDs (one under `.venv`, one under the raw system Python312 install), same
  args, same creation second. First hypothesis was "an orphaned duplicate executor double-writing
  the live account" and PID 28876 (system-Python copy) was killed as a precaution; its `.venv`
  twin (11732) died moments later too, and `watchdog.py` auto-respawned a clean instance within
  ~3min (no rebalance missed, 600s cadence). BUT the same pairing reproduced on the low-stakes
  `liquidation_listener.py` when relaunched via a **fully-qualified venv path** — WMI's
  `ParentProcessId` showed the Python312 PID was a genuine OS-level CHILD of the venv PID, and
  separately, plain `python`/`pythonw` on this machine's bash PATH resolves to system Python312 (no
  pyarrow installed there) rather than the venv. Net: this looks like a structural property of how
  processes launch on this machine (parent stub + real worker, or a PATH/App-Execution-Alias
  interaction) rather than a rogue independently-scheduled duplicate — but this was NOT conclusively
  root-caused before the investigation was stopped (further live-executor process experiments were
  judged higher-risk than the remaining uncertainty justified). Ground-truth account state
  (deployed_notional, carry count) never showed doubling, before or after any of this. Lesson:
  (1) don't equate "two PIDs with matching args" with "two independent competing processes" without
  checking `ParentProcessId` first; (2) always use the fully-qualified venv interpreter path for
  ANY manual process launch or diagnostic one-liner on this machine — bare `python` silently runs
  a different, less-provisioned environment; (3) when a live-capital process is involved, prefer
  read-only ground-truth verification (account state, heartbeat) over corrective kills unless the
  evidence is unambiguous — this session's kill was probably unnecessary and caused a brief (~3min)
  executor gap that a slower, more conservative investigation would have avoided.

## Failure taxonomy (tag every rejection with one → feeds the EV priors)
`crowded` · `no_breadth` · `overfit` · `no_economics` · `implementation_impossible` · `costs_killed_edge`
· `wrong_sign` · `regime_artifact` (e.g. bull-flattered trend).

## Alpha map (search for the MISSING branches; grep before building)
```
Funding → Carry (DEPLOYED) → Cross-venue funding (HL archive) → Basis (level ✓, momentum ?) → Options VRP (breadth-starved)
Trend   → TS-momentum majors (shadow 1/90) → Breakout ? → Regime-switch ?
Flow    → OI divergence (fwd) → Liquidations (fwd) → Whale/large-holder ? → Taker flow ✓
On-chain→ Stablecoin exchange reserves (fwd) → DEX volume ? → Gas/fees ? → Mint/burn ?
Macro   → Rates ? → DXY ? → BTC-correlation regime ?
```
`?` = unbuilt branch worth an EV score. `✓` = built. `fwd` = forward-accumulating clock.

## Economic stress checklist (how each edge dies — economically, not statistically)
For every deployed/candidate edge, pre-mortem: Binance delists the pair · funding goes to zero/negative ·
a stablecoin depegs · fees double · a government bans the venue/asset · the counterparty (testnet/exchange)
goes down mid-hedge (→ orphan drift, see reconcile limit-fallback). If any single event is fatal, size for it.

## Reverse-engineering prompts (when a fund/strategy comes up)
Why does this desk exist? What inefficiency/risk-premium is it harvesting? What information source?
Can crypto replicate it? What FREE data approximates the paid signal? → then derive 5–10 orthogonal
hypotheses and EV-score them; only the top few enter research.

## Accounting lesson — 2026-07-10 (the phantom "-$900 on the 3x lab" — now permanently fixed)
- **A one-sided realized accumulator WILL fabricate a dashboard loss.** `realized_spot_pnl` (the
  banked realized of CLOSED spot legs, whose proceeds sit in the spot wallet invisible to open marks)
  froze at the 07-09 backfill (337.26) because the stale 07-03 executor lacked the bank-at-close code,
  while the matching perp realized (−650.68) stayed captured in the futures-equity delta → a one-sided
  phantom, magnified 3× to −$865 on the levered lab. The book was actually ~breakeven/profitable
  (funding +47). Symmetric-correct value = Σ(deduped price_pnl basis) − venue futures REALIZED_PNL =
  61.17 − (−650.68) = **711.85**.
- **PERMANENT FIX = derive from exchange truth, don't accumulate.** `libs/execution/carry_accounting.py`
  `derive_spot_realized(venue_realized_pnl, trades)` = deduped basis − venue realized. Substituted into
  `net = spot_open + realized_spot_pnl + (fut_eq − start_eq)` the venue-realized term CANCELS, leaving
  `net = spot_open + basis + funding − fees` — un-fakeable. The executor reconciles it every rebalance
  and on restart (`_reconcile_spot_realized`, single-writer, self-heals a stale value in ≤1 cycle);
  `run_live_combined` derives it independently so the DASHBOARD is truthful even if the executor is
  down. Dedupe closes by `(symbol, opened)` — a flatten logs the same close 2–3× and would double-count
  basis. Curves that recorded the phantom were reset once (they were never a real drawdown).
- **Config-reload shipped:** `data/cashcarry_config.json` tunes `top`/`hold_top`/`capital` live — the
  running executor picks it up next rebalance, so a param change never again needs the flatten+restart
  that caused the 07-10 incident. New executor code activates on next natural respawn (dashboard is
  already protected). Verify a param is live by reading the config vs the running cmdline.

## Ops lessons — 2026-07-10 (carry-executor restart incident; read BEFORE any process surgery)
- **A committed param/code fix is INERT until the running process is actually restarted.** The
  `--hold-top 60→3000` churn fix (committed to watchdog.py 2026-07-08) never took effect: the live
  cash-carry executor had been running continuously since 2026-07-03 and was never respawned, so it
  kept churning (measured 2026-07-10: 20–38 closes/day, 48% held <8h, e.g. OPUSDT opened+closed in
  10 min on POSITIVE funding). The 2026-07-09 log's "executor_restarted: true" restarted the wrong
  thing. **Verify a fix is LIVE by inspecting the running process's cmdline / observed behavior, not
  by confirming the code was edited.** After a real restart on 2026-07-10: 0 closes in 20 min.
- **The venv python is a REDIRECTOR STUB (re-confirmed definitively).** `.venv\Scripts\pythonw.exe`
  spawns a `Python312\pythonw.exe` CHILD worker (proven: a trivial `.venv pythonw -c "sleep"` spawns
  a Python312 child). So every "`.venv` + `Python312` pair" running the same script is ONE logical
  process, NOT a duplicate. **Count venv stubs (parent), never raw PIDs.** WMI returns EMPTY cmdlines
  for these pythonw processes from a Medium-integrity shell — use `psutil` (reads cmdlines) to map
  daemons. This exact trap already cost the 2026-07-09 cycle a probably-needless kill; it cost this
  cycle hours of false "double-book" panic. This lesson pre-existed in the ledger — **READ THIS FILE
  FIRST (principle 0) before diving into a live-ops incident.**
- **The CRO cycle cannot kill S4U daemons.** The cycle shell runs Medium-integrity / non-S4U-session;
  QuantWatchdog (S4U) and the daemons it spawns are cross-session → `taskkill`/`Stop-Process` return
  Access Denied even as the same user `dell`. Only the watchdog itself (S4U) or an ELEVATED shell can
  kill them; non-elevated S4U/Highest scheduled-task creation is also denied. To restart the executor
  from the cycle, the only self-service levers are (a) the `_KILL` switch (but it FLATTENS the whole
  book) or (b) letting QuantWatchdog respawn on a stale heartbeat. There is NO graceful
  exit-without-flatten signal yet (backlog).
- **Intermittent GIL fatal crash on executor startup.** Some detached-`pythonw` executor spawns die
  before the first heartbeat with `Fatal Python error: PyEval_SaveThread ... GIL ... thread state is
  NULL` inside the first startup network call (`binance_spot_testnet.open_orders` → socket
  `create_connection`). It's INTERMITTENT (a clean single launch usually survives on attempt 1 and
  then runs for hours; the same call run plainly never crashes) — no gevent/eventlet in the tree, so
  the suspect is an OpenBLAS/numpy-thread × socket race in the windowless detached context. Hard
  crash → goes to DEVNULL, leaves NO trace in cashcarry_error.log. Mitigation used: retry-launch until
  one survives (the single-instance heartbeat lock then rejects the rest). Backlog: try
  `OPENBLAS_NUM_THREADS=1`/`OMP_NUM_THREADS=1` in the watchdog spawn env.
- **`_KILL` flattens; it is not a restart.** `data/CASHCARRY_KILL` makes the executor close ALL carries
  then exit. Using it to apply a param change costs a full book turnover (all legs closed + reopened).
  It also interacts badly with the 3-min watchdog: while `_KILL` is present every respawn exits on it,
  so the heartbeat never freshens and the watchdog keeps spawning (a benign exit-storm). Correct
  drain procedure: `Disable-ScheduledTask QuantWatchdog` → wait for executors to exit → remove `_KILL`
  → `Enable`+`Start` watchdog once → verify a single sustained stub. The single-instance lock is
  startup-only (checks heartbeat<150s once), so a stale-heartbeat window can still let a second stub
  through; it self-resolves as the loser exits on the next lock check.

## Research-infra lesson — 2026-07-11 (crypto autodiscovery factory industrialized + its failure mode)
- **The 12-generator autodiscovery factory now runs over CRYPTO every daily cycle.** `libs/autodiscovery/
  crypto_adapter.py` turns lake D1 bars (+ Level-3 `funding`) into `MarketSeries`; `run_crypto_research.py`
  feeds the top-30 liquid perps through the SAME gauntlet (net of ~5bps/side perp cost, cross-campaign
  DSR deflation on cumulative trials) and emits `web/autodiscovery_crypto.json`. Wired into
  `daily_research_cycle.py` (`autodiscovery` step). Idempotent: the store's content-hash dedup skips
  every already-tested hypothesis, so after the first sweep daily re-runs are near-instant (only NEW
  symbols/generators are tested) — verified: 2nd run skipped 195/390 as duplicates.
- **First sweep result: 30 symbols × 6 families = 390 trials, ZERO survivors** (DSR/PBO/reality-check
  reject all; the multiple-testing controls are doing their job). This is the honest expected outcome,
  not a defect — it INDUSTRIALIZES what the hand-tests already found: crypto price-pattern edges don't
  clear the gauntlet. `funding_stress_reversal` (LIQUIDITY family — fade crowded perp funding, the one
  genuinely crypto-native hypothesis, economically distinct from funding *carry*) was tested across the
  liquid universe and REJECTED on DSR/PBO/RC → add to the mental graveyard; do not hand-rebuild it.
- **FAILURE MODE — the campaign Reality-Check bootstrap OOM-crashes at ~1000 candidates.** An unbounded
  sweep (all 246 lake symbols, or an 80-cap ≈ 1040 candidates) dies SILENTLY mid-cycle — no traceback,
  process just vanishes (the T×N `campaign_pbo_rc` matrix + per-candidate CPCV over N≈1000 exhausts
  memory / oversubscribes the multiprocessing pool on this box). A 15-cap (195 cand) and 30-cap (390
  cand) complete cleanly. **RULE: keep the crypto factory universe bounded (default top-30 liquid).**
  This is not just a crash workaround — it is economically honest (the top ~30 perps hold essentially
  all real research capacity) AND statistically kinder (fewer cumulative trials = less DSR-deflation
  drag on the day a genuine candidate appears). Breadth-mining 200 microcaps is negative-EV on every axis.
- **Meta:** the factory's durable value is NOT this first (empty) sweep — it is the reusable pipeline
  that will auto-gauntlet each NEW free data axis (OI/LS/liquidations/stablecoin) the instant its
  forward clock matures, without hand-writing a bespoke backtest each time. Wide funnel, unchanged filter.

## Governance lesson — 2026-07-12 (external adversarial review: same-author blind spots are structural)
- **The designer is part of the attack surface.** Five independent frontier models reviewed
  docs/SYSTEM_REVIEW.md and found FOUR consensus leaks the desk's own designer missed for weeks —
  all at boundaries, none in the core loop: (1) naive forward t-stat assumed IID on autocorrelated
  carry returns (inflated significance exactly when N is small); (2) no multiplicity correction
  across the concurrently-monitored forward cohort (~18% family-wise false-positive at 4 candidates);
  (3) the Kelly time-ladder conflated "bigger fraction" with "more aggressive" — naive full Kelly on
  an ESTIMATED edge is an overbet that compounds SLOWER (shrunk-Kelly S²/(S²+SE²) is the true
  max-E[log] bet); (4) ADL on the short perp leg → the reconcile would have RE-SHORTED into the
  squeeze that took the leg. **Why the designer missed them: the person who chooses an assumption is
  the worst-positioned to question it.** Fixes shipped 2026-07-12 (forward_stats, kelly_shrink,
  ADL-flatten + basis-stop, dead-man switch, unknown_novel root-cause class, 7 black-swan scenarios).
- **RULE (standing, monthly-governance item 8):** external adversarial review by ≥2 independent
  models every quarter, findings triaged through the EV gate, consensus findings get highest priors.
  It found four real leaks for the cost of a copy-paste — the cheapest research audit that exists.
- **Reviewer calibration note:** external reviewers were also WRONG where they lacked internals
  (claimed the LLM enforces rails at runtime — they're deterministic code; claimed hysteresis holds
  negative-funding names — it exits them; claimed memory compression strips mechanisms — the
  graveyard keeps mechanism text). Verify every external claim against the code before acting;
  consensus-across-models on things they CAN see from the dossier is the high-signal subset.
- **Dead-man switch (scripts/run_deadman_switch.py) is TIER-3 NEVER-TOUCH.** Its entire value is
  independence from the AI that edits everything else: no LLM, no config reads, no libs imports,
  hard-coded 0.65×high-water / 5-consecutive-minute trigger → kill file + flatten + page. After a
  fire it LATCHES (data/deadman_state.json "fired") — a human must clear state + kill file
  deliberately after investigating. Never "improve" it autonomously.

## INCIDENT 2026-07-11 19:39Z — dead-man switch FALSE-FIRED; book flat ~1 day (root causes + permanent fixes)
- **What happened:** the Tier-3 dead-man rail flattened a healthy, perfectly-hedged book. Chain:
  (1) an OLD-code dead-man instance — spawned by the S4U scheduled watchdog — survived every
  kill attempt because `Stop-Process -ErrorAction SilentlyContinue` MASKED the Access-Denied
  (user sessions cannot kill S4U daemons; the 07-10 lesson, re-learned expensively); (2) the
  zombie kept writing its old-measure high-water (~$335k, whole faucet wallet) into the SHARED
  state file; (3) the new-code instance re-read that poisoned high-water each loop, compared it
  to the true ~$15.7k book equity, counted 5 "breaches", and fired: kill file + futures
  flattened + carry spot legs sold. Cost: ~1 day of funding (~$4) + re-entry fees (~$10-20).
- **Root causes:** (a) silent kill failures (SilentlyContinue on cross-session Stop-Process);
  (b) TWO WRITERS on one mutable state file — the new instance INHERITED foreign state instead
  of validating provenance; (c) deploy-verification checked HEARTBEAT FRESHNESS (liveness) but
  not WRITER IDENTITY — the heartbeat was fresh precisely BECAUSE two processes wrote it.
- **Permanent fixes (shipped same day):** state schema `version: 2` — any unversioned/foreign
  state is DISCARDED, never inherited (kills the poisoned-HW vector); pid-stamped heartbeat +
  single-writer invariant — an instance that detects a foreign live writer EXITS immediately
  (never share a rail); durable `data/DEADMAN_FIRED` latch file (state-file races can no longer
  un-latch a fire); startup guard 150s (was 30s — a hole vs the 60s write cadence); watchdog
  reaper (`data/.reap_deadman` marker → the S4U watchdog kills zombie instances from INSIDE
  their own session via psutil, the only place with rights).
- **RULES:** (1) never use SilentlyContinue on process kills — capture and CHECK the error;
  (2) after any daemon code change, verify the running process's WRITE-SIGNATURE (versioned
  state/pid-stamped heartbeat), not just heartbeat freshness — liveness proves something runs,
  identity proves the RIGHT thing runs; (3) any shared state file must carry a schema version
  and readers must refuse foreign versions; (4) reset procedure for the dead-man is now:
  delete `DEADMAN_FIRED` + `deadman_state.json` + `CASHCARRY_KILL`, then let watchdog respawn.
- **Honest accounting:** the rail's TRIGGER LOGIC was never wrong — the false fire came from my
  deployment process (zombie + shared state), i.e. operational risk I created while reducing
  market risk. The consecutive-reading guard worked as designed against API noise but was
  helpless against a poisoned reference point. Reviewers' "5 minutes is too tight" was NOT the
  failure mode; writer identity was.


## INCIDENT 2026-07-13 05:04Z — dead-man switch TRUE-FIRED on a real sizing bug; book flat 3 days (caught 2026-07-16)

- **What happened:** at 05:00:14Z a routine rebalance closed ZECUSDT and opened NOMUSDT at
  2,737,082 units = **$4,297 notional of a $4,500 book** into a near-empty testnet spot book.
  Five minutes later the dead-man's venue-truth equity read −40.9% from high-water (5 consecutive
  breaches) and it fired: kill file, reduce-only flatten, spot legs sold, principal paged. The
  flatten sold 2.7M NOM back into the same empty book — the round trip burned **~$4.7k of venue
  cash**. The executor's mark-based books recorded **−$54.73** for the same trade.
- **Root cause (three stacked defects):** (1) `_alloc`'s concentration cap had a documented
  "n×cap_frac < 1 → cap relaxes" path, so 1–2 fresh opens got ~the whole book; (2) opens were
  sized from FULL `--capital`, not free capital (capital − already-deployed notional); (3) no
  liquidity/depth check on entries (closes had `_mkt_or_limit`, opens had nothing).
- **Why it appeared NOW:** the 2026-07-09 churn/hysteresis fix made opens RARE — which turned the
  cap-relax path from cold (10-name initial builds, feasible cap) to hot (single-name top-ups).
  **Meta-lesson: a fix in one control changes the operating regime of its neighbours — after any
  behavioural fix, re-derive which code paths just became hot and re-read them.**
- **Second meta-lesson (accounting):** mark-based PnL is structurally blind to execution damage —
  fills through an empty book cost venue cash that ticker-marks never see. The executor said
  −$79 while the venue lost 41% from HWM. Only the dead-man (venue ground truth) saw it. Open
  defect: `spot_cost` = ticker at open, not actual fill (`cummulativeQuoteQty` / myTrades) —
  FIXED SAME DAY (2026-07-16): `avg_fill()` on both connectors (spot `myTrades`, futures
  `userTrades`) now sets cost basis at open and exit marks at close; ticker is only the
  fallback when the venue read fails. Dashboard history from before 2026-07-16 still
  understates the NOM damage; the dead-man remains the independent equity backstop.
- **Third meta-lesson (ops):** exit-on-KILL + systemd Restart made the executor respawn every
  ~17s for 3 days (14,225 restarts), which also starved the daily data flywheel that rides the
  executor loop (OI/LS + breadth clocks lost ~3 days) and froze the dashboard feed. Halted must
  not mean headless: the executor now idles under KILL, keeps flywheel + feeds alive, and
  resumes the moment the kill file clears.
- **Fixes shipped 2026-07-16** (CI ALL GREEN; regression tests in
  `tests/execution/test_executor_sizing.py`): hard cap (never re-inflate; cash remainder),
  free-capital sizing, `quote_depth()` thin-book guard on BOTH entry legs (≥5× order notional
  within 1% of touch), idle-under-KILL. Originals in `*.bak-20260716`.
- **The rail worked.** First true fire, zero human latency mattered, flatten executed, page sent.
  The 2026-07-12 external-review hardening (single-writer, versioned state) held: no double-fire,
  no zombie writer. Reset remains the principal's documented operator action
  (delete `data/deadman_state.json` + `data/DEADMAN_FIRED`, then remove `data/CASHCARRY_KILL`).
