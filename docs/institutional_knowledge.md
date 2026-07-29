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
Funding → Carry (DEPLOYED) → Cross-venue funding (HL archive) → Basis (level ✓, momentum ✗) → Options VRP (breadth-starved)
Trend   → TS-momentum majors (shadow 1/90) → Breakout ✗ → Regime-switch ✗
Flow    → OI divergence (fwd) → Liquidations (fwd) → Whale/large-holder ⧗ → Taker flow ✓
On-chain→ Stablecoin exchange reserves (fwd) → DEX volume ✗ → Gas/fees ✗ → Mint/burn ✗
Macro   → Rates ✗ → DXY ✗ → BTC-correlation regime ✗
```
`?` = unbuilt branch worth an EV score. `✓` = built. `✗` = tested + rejected (see
research_agenda.json do_not_repeat -- do not re-test without new evidence). `⧗` = tested,
EV-gate verdict is data-availability-limited not an economic kill (revisit when its data
matures). `fwd` = forward-accumulating clock. 2026-07-18 mined 3 branches (Breakout,
Regime-switch, Whale/large-holder via recorder aggTrades) -- 2 permanent rejects, 1 pending
recorder history (`large_print_flow_clustering`, revisit at >=30d aggTrades). 2026-07-19
closed the last 3 open `?` branches (hypothesis quota, pre-research EV-gate, all rejected
below threshold -- honest expected outcome, zero survivors is normal): `dex_cex_volume_ratio_
flow` (no strong mechanism, EV 0.0039), `stablecoin_mint_burn_supply_signal` (narrow breadth +
adjacent to the already-running stablecoin_flows family, EV 0.0005), `btc_correlation_regime_
carry_conditioning` (overlay-on-existing-book, same structural class as the rejected vol-target
overlay, EV 0.0003). The alpha map currently has NO open `?` branches -- next generation cycle
should lean on recombination (signal x filter x sizing x regime x venue x horizon variants) and
newly-maturing data clocks (OI/LS ~07-29, stablecoin ~08-11) per the generator checklist rather
than inventing new top-level branches from nothing.

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


## OPS LESSON 2026-07-16 — the pager itself died silently (429 retry spiral); alerting was OFF during the 07-13 incident

- The alert layer's own failure mode was the one it exists to prevent. `run_alerts.py` deduped
  on SUCCESS only, so any failed push retried every 3-min tick; standing alerts kept ntfy.sh's
  free quota exhausted from ~07-11 onward and **every page after that was dropped** — including
  the dead-man's 07-13 fire page (same endpoint, same IP). The principal was never paged, and
  the incident sat 3 days. 39 failed pushes were observed in a single 2h window.
- **Meta-lesson: a watchdog needs a watchdog-of-delivery.** Liveness of the alert *process*
  (it ran fine every 3 min) says nothing about DELIVERY. Success-only dedupe + fixed-interval
  retry against a rate-limited endpoint is a self-sustaining outage: the retries themselves
  keep the quota at zero. Always back off ATTEMPTS, not successes, and treat "pushes succeed"
  as a monitored condition (the alert state file's newest success timestamp is the signal).
- Fixed 2026-07-16: per-key 30-min attempt backoff in run_alerts.py. The dead-man's `_page`
  is Tier-3 never-touch and unchanged — it recovers automatically once quota refills.


## INCIDENT 2026-07-16 19:06Z — leverage-optimizer runaway sized the book from $40k; caught same evening by the venue-truth sweep

- **What happened:** the dynamic-leverage optimizer's confidence went 0 → 0.89 within hours of
  the morning's incident reset and flipped `active` (gate: confidence > 0). The executor then
  sized from `notional_per_leg` $40,122 instead of the operator's $4,500. Two single-name
  rebalances ballooned: HFTUSDT $5,741 (real, hedged, 1.28× book) and COOKIEUSDT $7,475
  intended — where BOTH legs failed to fill but the state recorded the full pair, and the
  reconciler retried + failed **silently** every 10 minutes for over an hour.
- **Meta-lesson 1 (the day's theme, third occurrence):** *a fix changes the operating regime of
  its neighbours.* The morning's free-capital sizing was correct — against the capital it was
  handed. The capital PIPE was the unaudited neighbour. After any incident reset, every
  statistic downstream of the reset (variance, SE, confidence) is contaminated until enough
  fresh data accumulates — gates that read those statistics must be frozen or re-based.
- **Meta-lesson 2:** *silent failure is never neutral.* `_mkt_or_limit` returns '' on failure
  and the reconciler logs nothing — a broken pair sat invisible for 75 minutes. Any retry loop
  that can fail must surface its failure count (now in the gap register).
- **Meta-lesson 3:** the same-day catch happened ONLY because venue-truth equity became a
  surfaced feed this afternoon (gap #10). Instrumentation built from incident #1 caught
  incident #2 within hours. This is what the compounding-lessons flywheel looks like.
- **Fixes:** executor `_dynamic_capital` clamped (de-risk below operator capital allowed,
  levering above it forbidden) pending root-cause + a ≥30-live-day re-enable gate; phantom
  COOKIE pair surgically removed (venue truth restored); HFT de-risk escalated rather than
  midnight-churned. Root-cause of the confidence jump = top brain task.
- **2026-07-17 follow-up:** the silent-reconciler-failure gap (meta-lesson 2 above) is FIXED --
  `_reconcile`'s `_do()` wrapper counts consecutive `_mkt_or_limit` failures per symbol, surfaces
  a `RECONCILE-FAIL` line + error-log write on the 3rd strike, resets on success. Regression tests
  in `tests/execution/test_reconcile_fail_counter.py`.

## Architecture fact — 2026-07-17 (forward-shadow clocks are market-data-driven, NOT executor-state-driven)
- **The carry forward-shadow clock (`web/cashcarry_shadow.json`, the file that actually gates
  fast-track promotion) computes forward returns from the market-data funding/basis PANEL via
  `cashcarry_returns()`, applied continuously since `shadow_start` — it is completely decoupled
  from the live testnet executor's operational state.** An operational incident that flattens or
  restarts the executor (e.g. the 2026-07-13 dead-man fire, 3 days flat) does NOT create a gap or
  contamination in this clock; it only affects the separate, informational `web/portfolio.json`
  deployed-equity tracker. Ruled explicitly 2026-07-17 (ledger
  `2026-07-17-shadow-clock-contamination-ruling`) after an external panel model raised the
  contamination question — verify this architectural fact from code before re-litigating it.
- **Meta-lesson:** know which of the desk's two equity/return series a question is actually about
  before reasoning about contamination, resets, or incident impact — "the strategy's forward
  track record" (market-data shadow) and "the executor's live P&L" (operational, incident-exposed)
  are different measurements of different things, and only the first one gates promotion today.

## Ops note — 2026-07-17 (periodic auto-commit is a background service, not a competing session)
- Commits named `desk snapshot <timestamp>` appear every few minutes throughout the day, even
  mid-cycle while the AI brain is actively working. This is a periodic background snapshot
  (tied to the 3-min `quant-refresh.timer` / cadence machinery) that commits whatever is dirty in
  the working tree, NOT a second concurrent Claude session editing the repo. Confirmed 2026-07-17:
  `ps aux` showed no second `claude` process; the file changes attributed to "another session" were
  the tail end of the PRIOR interactive session's writes landing on disk just as the next headless
  cycle started, then swept up by the next periodic commit. Don't panic-diagnose a collision from
  commit timestamps alone — check `ps aux` for an actual second process before assuming one.


## INCIDENT 2026-07-17 14:01Z — dead-man fire #3: FALSE IN SUBSTANCE (contaminated high-water mark)

- Venue equity at latch (~$4,720) was ABOVE the 07-16 segment start (~$4,171): nothing was
  lost. The HWM ($7,233) had been inflated during the leverage-runaway hours when an
  oversized book marked at tickers; the rail then measured −35% from a poisoned peak.
- **Meta-lesson (the week's lesson, final form): after ANY anomaly, every downstream statistic
  is contaminated — variance, confidence, AND reference points like high-water marks. A rail
  that ratchets its reference during an anomalous period will later fire on the ghost of that
  anomaly.** The documented operator reset is the designed cure; the rail itself is correct
  and stays never-touch.
- Also fixed: pager dedup per-key (slow defects 24h, latched-rail nag deliberately 6h);
  wallet hygiene sweep consolidated ~$84k of stranded carry-history spot (incl. faucet BTC —
  filter broader than intended, harmless on testnet) into USDT so the measure re-baselines
  clean. Reset offered to principal; unanswered → book stays flat until explicit approval.

## Ops lesson — 2026-07-18 (cadence-duty state-key mismatches silently perpetuate; audit dossiers can be stale relative to live state)
- **A cadence duty can re-fire forever if the code checks one state key but a prior cycle wrote
  a different one.** `run_cadence.py` gates the fred_macro family-generate duty on
  `gen_done_fred_macro_family`, but the 2026-07-17 cycle set `gen_done_fred_macro` (no
  `_family` suffix) — a one-character mismatch that made `cadence_duties.md` re-flag already-
  completed work every day. Fixed by setting the correct key (work itself was not re-done).
  **Rule: when marking a cadence duty done, grep the exact key name run_cadence.py checks —
  don't infer it from the duty's prose description.**
- **A panel/micro-audit dossier can describe a STALE gap-register state, not live reality.**
  Two 07-18 micro-auditors flagged HFTUSDT concentration as "unresolved, decision-pending"
  because the dossier generator apparently carried forward the 07-16 gap-register text; the
  position had actually been closed 07-17T14:03:56Z in the dead-man fire #3 flatten, verified
  directly against `data/cashcarry_trades.json` and `data/cashcarry_positions.json`. **Rule:
  ALWAYS verify a panel/audit finding about position/portfolio state against the live state
  file, not just the dossier's narrative — the dossier is a snapshot, the state files are truth.**
- Built `libs/execution/binance_live.py` + `binance_spot_live.py` + `libs/execution/staging.py`
  (S0/S1/S2 stage machine) — see ledger `2026-07-18-live-connector-stage-machine-build`.
  Fully inert (no keyfile placed); triple-guard arming; capability whitelist AST-verified.
  Remaining connector spec scope (venue-side stops, pager ladder, canary, mutation testing +
  fuzz breaker report) tracked in GAP register row 2.
- **`docs/institutional_knowledge.md` is 379 lines, well past the ~200-line active-lesson
  budget** (memory-compression governance item, monthly). GAP register row 29 already tracks
  that the quarterly memory-consolidation cadence duty has never executed — this line is the
  cross-reference so the next cycle with spare capacity picks it up rather than rediscovering it.

## INCIDENT 2026-07-19 14:27Z — dead-man fire #4; a same-author diagnosis error caught by the panel, and a 29h pager blackout

- **Full facts/autopsy/panel corrections:** `data/INCIDENT_20260719_DEADMAN.md`, GAP register
  rows 34/37/38, ledger `2026-07-19-deadman-fire4-incident-autopsy`, `2026-07-19-pager-unicode-
  fix-and-neighbours`. Book is testnet-only; zero real capital at risk. Compressed lessons only:
- **A same-author "no catastrophic loss" call was WRONG and the 13-model panel caught it same
  cycle.** My first-pass read of a $1.8-2.6k (36-52% of HW) unattributed equity gap as "modest
  slippage" was near-unanimously rejected by the panel as premature — treat any unattributed
  equity gap that size as an UNRESOLVED accounting break requiring double-entry reconciliation,
  never as slippage-by-assertion. Direct evidence for the 2026-07-12 lesson ("the designer is
  part of the attack surface") recurring in a NEW guise: diagnosis quality, not just design.
- **My proposed dead-man fix ("couple equity to executor position state") was also wrong** — the
  panel's counter (venue-native, all-spot-balance valuation, zero executor coupling, plus
  quiescence bounds) is the correct direction: coupling the isolated rail to the exact subsystem
  whose bugs it exists to catch trades false-positives for false-negatives, a strictly worse
  failure mode under the ruin constraint. Generalizable rule: when proposing a fix to an
  isolation-designed rail, the fix must never re-introduce the dependency the isolation exists to
  remove — verify this explicitly before proposing, not just before implementing.
- **A pager can die from ONE non-ASCII character and stay dark for 29h+ with zero signal.** An
  emoji added to an alert Title (2026-07-18T18:05Z) broke HTTP header encoding and silently
  killed all 39 subsequent pushes across every alert category — including this dead-man fire
  itself. The `--test` self-check used different (ASCII-only) text and never exercised the
  broken path. Rule: a self-test that doesn't send exactly what production sends verifies
  nothing about production. Fixed (ASCII markers + defensive latin-1 encode), but end-to-end
  delivery is still unconfirmed (a real ntfy 429 hit immediately after) — single-channel
  alerting is now confirmed insufficient by near-unanimous panel consensus (GAP row 38).

## Ops + data lesson — 2026-07-21 (CI can be RED at HEAD; recorder now records BOTH legs)
- **Run `scripts/run_ci.py` at CYCLE START, not just after your own edits.** This cycle CI lint
  was already RED at HEAD — 15 pre-existing ruff errors (E501/E702/F401/F541/B023/SIM105/E402) in
  tooling scripts committed by earlier same-day headless cycles (track_findings, build_audit_coverage,
  deep_review, ingest_axes, capacity_test). A red gate is the desk-wide safety net down for everyone,
  and "my change is clean" is not the same as "the gate is green." Restored to green (behavior-
  preserving style fixes). Lesson: verify the gate is green BEFORE building on it; a green CI is a
  monitored condition, not an assumption. (These files aren't in pytest's path, so tests passed while
  lint rotted — CI's own lint step is the only thing that catches script-level style regressions.)
- **Data-moat recorder now records the SPOT leg too (`run_recorder_spot.py`, gap #35).** The desk is
  delta-neutral: every carry trade is spot+perp, so a pre-live TCA/cost model built on the perp-only
  tape (run_recorder.py, `fapi`) silently mis-priced half of every trade. Spot (`api.binance.com`)
  uses a SEPARATE per-IP weight bucket from USD-M futures (`fapi.binance.com`) — 6000/min vs 2400/min
  — so the two recorders don't contend for rate budget. Both are stdlib-only, isolated (no keys, no
  book access), gzip-jsonl hourly under data/moat/{fut,spot,bybit}/, cron pgrep self-heal. Three
  recorders now ~12GB/mo combined vs ~31GB free — DISK is the shared neighbour, guarded at 80% in each.
- **UNKNOWN IS NOT ZERO: a venue 502 was published as a $0.00 funding harvest (2026-07-26).** The
  carry book reported `funding_harvested=0.00` and a bleed verdict of "inf% — hedge losing more than
  it earns", while the molded book had recorded `funding=101.96` on the same book two hours earlier.
  `/fapi/v1/income` was returning HTTP 502 (3/3 live attempts). In `_mark()` the equity read and the
  income read shared ONE `_safe()` block, so the equity assignment landed and the swallowed income
  error left funding/commission at their initialised `0.0` — a PARTIAL update publishing a real
  futures PnL beside a fabricated zero, which is exactly the pair the alarm reads as a total bleed.
  An HTTP error was rendered as an economic verdict on the forward record the sizing gate reads.
  **Three durable rules.** (1) Give every venue read its OWN guard: a shared try/except across two
  calls makes failure partial, and a partial failure is published as if both succeeded. (2) A
  measurement that fails must surface as UNMEASURED, never as a zero — they are opposite states and
  only one of them is an execution problem. (3) Fixing a failure SHAPE on one code path does not fix
  its siblings: this is the SAME shape as the 2026-07-19 stranded-inventory incident (GAP row 34),
  which was fixed on the ORDER path (`_filled`) and left standing on the MEASUREMENT path for a week.
  Run the adjacency sweep in the same pass — it found a second live instance in run_live_combined,
  where the pattern was half-applied (venue_realized already used None-means-unknown; funding two
  lines above still seeded 0.0). Corollary: silencing a false alarm is only safe if the silence is
  itself tracked (max_audit `check_carry_funding_measured`).
- **A convention honoured by one check and ignored by its sibling is a blind spot (2026-07-26).**
  `check_artifact_ungoverned` implements trailing-slash directory claims with a comment predicting
  that exact-path claims "would fire permanently on correctly-governed output"; `check_findings_scope`
  in the same file did exact matching only. So `docs/research/deep_sweep/` — excluded WITH a stated
  reason since it was written — was never actually excluded there, and `findings-scope-unmonitored`
  fired forever on dated reports. The defect was UNCLOSABLE by construction: satisfying it required
  listing files that do not exist yet. When a rule is written for one organ, grep for its siblings.
- **Guards must be calibrated against measured cost, not a constant (2026-07-26).** The panel
  pre-flight credit check estimated `0.05/seat` = $0.65/run against a measured ~$2.93 ($56.60
  lifetime over 12 runs), and its own inline comment claimed "~$1.10/run" — disagreeing with its own
  arithmetic. A guard 5-7x optimistic does not prevent mid-run exhaustion, it CAUSES it by
  green-lighting a run the balance cannot cover. Now self-calibrating from the usage counter's
  advance. Any guard carrying a hardcoded cost/latency/size constant should be asked, once a
  quarter, whether reality still matches it.
- **A daemon with two supervisors has no supervisor (2026-07-26).** `watchdog.py` (cron, every 3min)
  Popen-spawned the cash-carry executor *and* `quant-cashcarry.service` supervised it — laptop-era
  code that survived the 07-12 systemd migration. The watchdog's copy is owned by cron, so it
  outlives `systemctl restart`, holds the single-instance lock, and every systemd spawn exits 0 on
  that lock: `Restart=always` then respawned ~190x/hour (NRestarts=5354). Two supervisors do not
  give redundancy, they give an orphan plus a storm. Rule: exactly one supervisor per singleton;
  when a unit exists, every other starter defers to it and keeps a backstop only for the case where
  systemd has nothing running at all.
- **An orphan pins the process to the code it loaded at spawn (2026-07-26, third instance).** The
  orphan started 12:48 and the funding-measurement fix was written 20:06, so the fix was INERT in
  the only process that owned the book, which kept publishing a fabricated `inf%` BLEED from an
  HTTP 502 for hours. This is IK:141 (2026-07-10, churn fix inert 2 days) recurring, and the storm
  is IK:290 (2026-07-13, 14,225 restarts) recurring — the 07-13 fix was applied to the KILL exit and
  left standing on the SINGLETON exit 380 lines away in the same file. **One instance is never one
  instance: when you fix an exit-under-supervision, grep every other exit in that file.**
- **A lesson that is only written down will be re-learned; only a check is a fix (2026-07-26).**
  Both classes above were already in this file and both recurred anyway. What broke the loop was
  making them mechanical. Note the trap in doing so: `check_stale_daemons` asked systemd for
  MainPID and skipped on `0` — but `0` is precisely what systemd reports while a unit sits in
  `activating (auto-restart)`, which is the state an orphan *causes*. The inert-code detector was
  blind to the commonest way code goes inert. **A monitor that sources its ground truth from the
  component that is failing cannot see the failure**; it now discovers workers independently via
  the process table. Corollary found the same hour: `pgrep -f <script>` matched every claude
  process, because the injected doctrine quotes `run_cashcarry_executor.py` and
  `run_deadman_switch.py` in its risk-path duty — match argv elements, never a command-line
  substring, or the monitor reports the wrong process.
- **A "success" predicate that reads a RECEIPT instead of the GOAL STATE builds a perpetual-motion
  fee machine (2026-07-28).** The carry close checked `_filled(order)`; a reduceOnly cover against
  an ALREADY-FLAT futures leg is rejected by the venue, so `fut_ok` was False forever, the pair
  never retired, and `_reconcile` — blind to the KILL order — rebuilt both legs in front of every
  retry. The book round-tripped its entire notional through market orders every 600s: 11,136 venue
  COMMISSION events against 251 logged round-trips, $1,456 of fees in 48h against $113 of LIFETIME
  harvest, and it ran NAKED LONG SPOT the whole time. Two lessons. (1) For any unwind, success is
  "the leg is flat", never "an order filled" — and the check must be FAIL-CLOSED so an unreadable
  venue leaves the flag untouched (that is what preserves the 07-19 stranded-inventory guard while
  fixing this). (2) **A reconciler that restores invariants must know when the desired invariant
  has CHANGED.** Under a flatten/kill order the target is FLAT, so "heal the hedge" becomes "undo
  the rail". Any self-healing loop needs the current goal as an input, or it will faithfully fight
  the operator.
- **The trade log is not the fee bill; reconcile them or the leak hides in the gap (2026-07-28).**
  The book's own log explained ~$126 of a $1,746 venue bill — 44 venue fills per logged round-trip.
  Every diagnosis of a cost problem must start by reconciling the desk's records against the
  venue's, because a loop that trades without logging is invisible to every tool that reads the log.
- **Detection was never the gap; NAMING THE CAUSE was (2026-07-28).** §40's fee-ratio check fired
  ~27h before this was diagnosed, reporting "fees are 63x the harvest" — a symptom consistent with a
  dozen causes, so it cost a full investigation to localise and was carried as backlog meanwhile.
  The new `check_close_retry_loop` reports the fingerprint instead (same symbol failing to close
  while the reconciler rebuilds it). **When an alarm is true but keeps getting deferred, the fix is
  usually to make it name the mechanism, not to make it louder.**
- **A stale test fake silently disarms the regression test it exists to run (2026-07-28).**
  `test_fill_verification`'s fake `place_market` never accepted the `reduce_only` kwarg production
  started passing on 07-27, so it raised TypeError, `_safe()` swallowed it, both legs read unfilled,
  and the guard on the 07-19 money-path incident had been failing for a day. CI reported it and the
  desk shipped anyway. **A red CI is not a nuisance, it is every guard switched off at once** — the
  gate was red on lint (558 ruff errors, mostly one-off `hl_*.py` research scripts) and on one
  artifact-governance test, and commits kept landing.
- **A gate whose instructions contradict its threshold rejects ~100% and teaches dishonesty
  (2026-07-28).** `Idea.est_sharpe` is documented as "an honest prior — be conservative", but
  `_EV_THRESHOLD=0.05` needs ~est_sharpe ≥1.6 at breadth 40 to QUEUE (carry ref 3.28 → 0.1171 PASS;
  modest/broad 0.6 → 0.019 REJECT). Conservative honesty is therefore auto-rejected and optimism is
  rewarded, and the whole "many small decorrelated sleeves" class dies at the door. Calibrate every
  gate against a KNOWN-good reference and a known-marginal one; a reject rate near 100% is a
  property of the gate to investigate, never evidence that the candidates were bad.
- **A P&L that cannot see its dominant cost will report a fee fire as break-even (2026-07-28).**
  `_tca` records slippage-vs-mid and carries **no commission term**, so every per-trade `net` in
  the carry trade log (= price_pnl + est_funding) was fee-blind by construction — and
  `run_trade_forensics` summed exactly that field for its hold-class verdicts, its symbol
  blacklist, and the forward track record Gate 0 sizes real capital on. Over 14 days the venue
  billed **$1,628.81** while the log's aggregate net read **+$0.16**. The `>24h` class read
  -42 bps against a true **-635 bps**. Before trusting ANY per-trade verdict, verify each cost term
  is actually *in* the record; "realized edge = modeled edge − implementation loss" is a lie if the
  instrument cannot see the loss. Fixed by joining venue COMMISSION events onto round-trips
  (`commission_events` + `_fee_attribution`), publishing fee-blind and net-of-fee side by side
  because **the divergence is the diagnostic**.
- **An alarm without an enforcement arm is a log line (2026-07-28).** §40 fired ~27h before the
  churn loop was diagnosed, reporting the symptom ("fees are 63x harvest") with no authority to
  stop anything. The only mechanism that halted a $1,750 fee fire was the **equity ruin rail at
  -35%** — i.e. after the money was gone. Detection and authority are different capabilities: pair
  them, or the alarm is theatre. 94.1% of that ruin breach was the software defect; thesis-only PnL
  was -2.19%, so without the bug there is no breach and no dead-man fire.
- **Measure the FINGERPRINT, not the symptom, and make it generalise.** A sign test on P&L missed
  the fire because the class was *already* flagged bleeding — it moved -42 → -635 bps in silence.
  **Fee intensity** (fee as bps of notional vs the ~10 bps a futures round-trip should bill) catches
  any case of the venue charging for fills the book never intended, whatever the mechanism. It
  fires at **59x** on the incident.
- **Verify your own writes, not just other people's state (2026-07-28).** `max_audit` stripped its
  escalation with `existing.split(MARK)[0]` — which keeps only the text BEFORE the marker. Once the
  escalation owned line 1 (every run after the first, since the 07-24 delivery fix), that returned
  `""` and **silently deleted the entire human-written page below it**. Every `PRINCIPAL_ACTION`
  page written since 2026-07-24 was destroyed by the next sweep, on the desk's **only**
  human-escalation channel, with no error anywhere. Found only by re-reading the file after writing
  it. VERIFY-THEN-CLAIM applies to the desk's own output, not merely to inherited state — and a fix
  that solves "stale line 1" by making a generic line 1 permanent has traded one failure for
  another (routine sweeps must never outrank an event-driven ask only a human can clear).
- **Demand the artifact, never the flag — including inside the auditor (2026-07-28).**
  `check_generation` read only `cadence_state.last_live_generate`, a key a cycle sets by hand. It
  reported generation "skipped" on a day the Stage-A executor had already written real verdicts,
  and would equally have reported it DONE for a cycle that touched nothing but the timestamp. Same
  root as the desk's own `check_production` ("scheduled but not PRODUCING"). Likewise
  `check_artifact_governance` walked `docs/` without a gitignore filter, demanding governance for
  local scratch — making the check, and the CI test asserting on it, **environment-dependent**: red
  on the box that generated the scratch, green on a clean runner. A gate whose verdict depends on
  which machine ran it cannot be trusted in either direction.
- **Coverage that rises because findings stopped being counted is a blinder desk.** Routing the
  101-item subsystem triage into §35 scope raised open findings **67 → 168** and immediately
  surfaced 4 items that had been invisible to the only organ that works a backlog. The honest
  direction for a coverage metric is scope UP, not denominator down.
- **Check the function SIGNATURE before debating the threshold (2026-07-29).** The gauntlet's
  `pbo` and `reality_check` gates call `probability_backtest_overfitting(returns_matrix)` and
  `whites_reality_check(returns_matrix)` — **neither takes the candidate's own returns as an
  argument.** A gate that cannot see the thing it judges is not a strict gate, it is a *campaign
  constant*: measured PBO 0.6159 and White RC p 0.4220 forced **420/420** rejections at any
  quality. That is the whole 420-tested/0-survivors record. Both statistics are properties of a
  SEARCH PROCEDURE — PBO ranks the in-sample-*best*, White's RC tests the *maximum* — and neither
  was ever a per-strategy test. Before asking "is this bar too high?", ask "does this bar take the
  candidate as input?"; the first question is unanswerable if the second answer is no.
- **A too-strict gate and a too-loose gate can be the same gate (2026-07-29).** Everyone measured
  the 420/0 direction and concluded "strict"; nobody measured the other. Holding 60 pure-noise
  candidates fixed and adding ONE genuine winner to the batch flips the old gates from admitting
  0/60 to admitting **60/60 pure nulls** — because the campaign statistic is driven by the batch's
  best member. So the status quo was an unquantified phantom-edge hole that opens *precisely when
  the desk starts finding real edge*, i.e. in the state it is trying to reach. **When you catch a
  gate rejecting ~100%, do not stop at "too strict" — construct the batch where it passes
  everything.** The one-directional measurement is what let this survive four sweeps as "blocked,
  do not loosen".
- **"No change to the verdict" can be the confession, not the reassurance (2026-07-29).**
  `campaign_pbo_rc` was introduced as a caching speedup whose docstring promised "a large speedup
  with no change to the verdict". That claim was *literally true* — and true only because the
  per-call fallback recomputes the identical campaign statistic. The caching was a red herring: a
  cycle that "fixed the cache" would have changed nothing. When an optimisation can prove it never
  alters an output, check whether the output was ever a function of the input you thought.
- **A null result is a claim about the instrument until you have ruled the instrument out
  (2026-07-29).** 420-tested/0-survivors was read for months as *"price space is picked clean"* — a
  conclusion about the world — and that read steered real strategy (it is cited in the
  generation-ROI finding that mass generation is self-defeating). The measurable cause was two
  broken gates. Scope every negative result to ROUTE-vs-CAPABILITY before letting it set direction;
  the same error shape as the blocked-YouTube-endpoint episode that nearly bought a paid proxy.
- **Adjacency is not optional after a fix (2026-07-29).** On 07-28 the desk learned *"a reject rate
  near 100% is a property of the gate to investigate, never evidence that the candidates were
  bad"* — and fixed the EV gate. It did not then sweep for the same SHAPE elsewhere, so the
  identical defect sat one layer down in the gauntlet, at far higher stakes, for another day. A
  lesson that stays in the file where it was learned is half a lesson.
