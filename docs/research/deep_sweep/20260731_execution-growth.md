# DEEP COLD AUDIT — EXECUTION-GROWTH — 2026-07-31

_Auditor: weekly deep cold sweep (execution-growth subsystem). READ-ONLY. Every claim carries its proving command output. The 2026-07-30 sweep found 20 issues (headline: dead-man rail silently disarmed; S0→S1 gate unwired; `_MIN_FUNDING` second lock). Since then `libs/execution/` gained five new/modified modules (`staging.py`, `ramp_gate.py`, `canary.py`, `protective_stops.py`, `sub_accounts.py` — the last written 02:00 TODAY). This sweep therefore has three mandates: (1) RATCHET CHECK — re-verify every prior critical finding by OUTCOME, not by the existence of new code; (2) audit the post-sweep code for the desk's proven failure mode (built, green, called by nobody); (3) hunt seams the prior sweep did not open._

**STATUS: COMPLETE** — 16 findings (R-CHECK + F1–F16) + full ratchet re-verification of the 07-30 sweep's 20, every claim carrying its proving command. Four outputs, scores, and headline at the end.

---

## FINDINGS LOG (raw, verified as discovered — synthesized into the four outputs at the end)

### R-CHECK (RATCHET, the good news first — yesterday's two worst findings are genuinely fixed, verified by OUTCOME)

**The Tier-3 dead-man rail is RE-ARMED and fires.** Not read from the commit — replayed against the live state file:
```
$ cat data/deadman_state.json
{"version": 2, ..., "high_water": 5777.27640201, "breaches": 0,
 "disarmed_live": false, "disarmed_paged": false}
$ .venv/bin/python  # replay run_deadman_switch.should_fire against the live state copy
high_water = 5777.28   _MIN_HW = 500.0
equity=   5777.28 -> 6 consecutive polls should_fire=[F, F, F, F, F, F]
equity=   3697.46 -> 6 consecutive polls should_fire=[F, F, F, F, True, True]   <- fires at 64% HW
equity=    100.00 -> ... True after 5 breaches
equity=      1.00 -> ... True after 5 breaches
```
`fut_eq` is now `max(sum(per-asset marginBalance), totalMarginBalance)` (run_deadman_switch.py:131-133), the state carries explicit `disarmed_live`/`disarmed_paged` flags, and high_water re-anchored to $5,777. The absorbing state is cleared the RIGHT way (measurement fix, not re-baseline): the executor journal shows `net=$3701` and `last_risk_action: "ok"`, RISK-FLATTEN gone.

**The S0→S1 freeze-exit gate was rewired to real artifacts.** `run_cadence.py` now maps every criterion to `(artifact, writer)` in `_FREEZE_SOURCES`, `check_freeze_exit_sources()` asserts each writer exists, and `days` is measured from oldest ROW timestamp, not mtime:
```
$ .venv/bin/python -c "...run_cadence._freeze_exit_met()"
(False, 'gate0=False, fills_4wk=False, cost_model=True, calib_10=True, no_criticals=True')
```
Two criteria now honestly pass; the two that fail are honest too (tape frozen at 26.42/28 days, gate0_complete not yet written). This is the ratchet working as designed.

---

### F1 (**THE HEADLINE — CRITICAL, INTERNAL/survival-rail, launch-blocking**) — the launch-day capital-deposit trigger reads a state file that DOES NOT EXIST and a key that NOTHING WRITES. Run as documented, it records the ruin-rail inception as deposit-only — silently loosening the rail by the entire pre-existing equity (~89% on today's book).

The designed launch posture (deploy/finish_setup.sh header): *"fully set up, held, deposit is the trigger... ends by printing the ONE command that remains (recording the deposit)."* That command is `scripts/record_capital_event.py --deposit <usd> --by ... --reason ...`.

**Proof 1 — the phantom file.** The recorder and the readiness board read `data/cashcarry_state.json`; the executor's state lives in `data/cashcarry_positions.json`:
```
$ grep -n "_STATE = " scripts/run_cashcarry_executor.py scripts/record_capital_event.py
scripts/run_cashcarry_executor.py:40:_STATE = Path("data/cashcarry_positions.json")
scripts/record_capital_event.py:40:_STATE = _ROOT / "data/cashcarry_state.json"
$ ls data/cashcarry_state.json
ls: cannot access 'data/cashcarry_state.json': No such file or directory
```

**Proof 2 — the phantom key.** Even with the filename fixed, both scripts read `last_combined_equity`, which has two readers and ZERO writers — the executor computes `eq_c` per tick in memory and persists only `peak_combined_equity`:
```
$ grep -rn "last_combined_equity" scripts/ libs/ --include=*.py | grep -v __pycache__
scripts/record_capital_event.py:53:    return float(st.get("last_combined_equity",
scripts/check_gate0_ready.py:143:        eq = float(st.get("last_combined_equity", raw))
```

**Proof 3 — measured on the launch box, beside a live book.** `data/cashcarry_positions.json` holds `start_futures_equity: 5000.0`, `peak_combined_equity: 8708.60`; the executor prints `net=$3701` (eq_c ≈ $8,701) every tick. The recorder sees none of it:
```
$ .venv/bin/python scripts/record_capital_event.py --show
inception (raw state)     $0.00
inception (effective)     $0.00
combined equity           $0.00
capital events recorded: 0
```

**Consequence, traced through `libs/risk/capital_events.rebase()`.** With the state unreadable, `equity_now` defaults to $0.00, so `--deposit 1000` records `new_start = 0 + 1000 = $1,000` into the append-only ledger. The executor then honours the ledger (`run_cashcarry_executor.py:698`: `effective_start_equity`), so the ruin rail measures drawdown from $1,000 while the book actually carries ≈$8,700 of combined equity. The flatten line moves from 0.65×(equity+deposit) ≈ $6,300 to **$650** — the book could lose ~$8,000 (92%) before the survival rail fires. The refusal logic cannot catch it: `deposit_usd > 0` passes every gate, and the ledger row it writes (`equity_before: 0.0`) poisons the cumulative-loss chain "the desk's memory of what has been lost" permanently — the ledger is append-only by design.

**Why the drills didn't catch it.** `data/drill_report.json` shows `ruin_rail_reentry: 4/4 PASS` — but the drill exercises `CE.rebase()` as a pure function with synthetic arguments. It proves the mechanism and says nothing about the wiring, which is the constitution's own warning (*"unit tests are what make this invisible"*) reproduced in the drill layer one day after it was written into §42.

This is yesterday's F1 defect class (a gate reading files nobody writes) — found, named, fixed in `run_cadence.py`, generalised into `check_freeze_exit_sources()`... and reproduced the same day in the two NEW launch scripts, one of which (`check_gate0_ready.py:75-81`) contains a docstring describing catching exactly this defect in its own first draft. The class survives because the check that was built (`check_freeze_exit_sources`) covers only the freeze-exit gate's five criteria, not the pattern. Fix is ~4 lines (point both scripts at `data/cashcarry_positions.json`; have the executor persist `last_combined_equity` each tick — it already writes the state file anyway); the class fix is a repo-wide "every `data/*.json` path a script READS must have a WRITER" assertion in max_audit.

---

### F2 (CRITICAL, ADJACENCY — the equity-read fix stopped one file short of the money) — `binance_live.py:188`, the MAINNET connector the desk is about to arm, still reads USDT-only `totalMarginBalance`. The exact bug that flattened the testnet book and disarmed the dead-man rail survives on the live path.

Yesterday's F6/F13 chain (totalMarginBalance is USDT-only under `multiAssetsMargin=False` → $5,000 USDC valued at zero → rail flattens a solvent book → high_water falls below `_MIN_HW` → dead-man silently disarmed) was fixed in TWO of the three connectors:
```
$ grep -n "totalMarginBalance\|marginBalance" libs/execution/binance_live.py libs/execution/binance_testnet.py scripts/run_deadman_switch.py
libs/execution/binance_live.py:188:        "equity": float(a.get("totalMarginBalance", 0.0)),   <- UNFIXED
scripts/run_deadman_switch.py:131-133:  fut_eq = max(sum(marginBalance), totalMarginBalance)     <- fixed
libs/execution/binance_testnet.py:181-183: eq = max(sum(marginBalance), totalMarginBalance)      <- fixed
```
The commit that fixed it (`fccc580`) touched `binance_testnet.py` and `run_deadman_switch.py` only. `binance_live.py` — modified the same day for "behavioural coverage" (`de017ef`) — kept the old single-field read.

**Why this bites, concretely.** On mainnet the desk PLANS to hold non-USDT assets in the futures wallet: funding BNB for the 25% fee discount is an open recommendation (yesterday's #10), and BNB used for fee burn sits in the futures wallet as collateral. The moment it does, every consumer of `binance_live.account_summary()["equity"]` — which on live includes the executor's ruin-rail input `eq = float(fut.account_summary()["equity"])` (run_cashcarry_executor.py:682) once the connectors are swapped — undervalues the book by the BNB balance. Near a threshold this fires a false pause/flatten; combined with F1's understated inception the two errors compound in opposite directions on the same rail. The deadman itself is safe (it computes its own sum), but the executor rail and anything else reading the connector's `equity` are not. Fix is the same 3 lines already proven in `binance_testnet.py:181-183`, copied to the file that will actually carry money.

---

### F3 (CRITICAL, INTERNAL/gate-optimality, carried 1 day — now the SOLE blocker on the launch clock) — `_MIN_FUNDING` still vetoes all 248 tradeable candidates including the exact top-4 the launch config selects; R0057 (its deletion) sits OPEN and undisposed while the tape clock it freezes is the last desk-owned launch criterion.

Reproduced live this morning, on the top-4 the `top=4` launch config actually ranks first:
```
$ .venv/bin/python  # _ranked() + _entry_gate() on the live universe, current funding snapshot
top-4 by net (what _rebalance opens from):
  BTCUSDT   f=1.000bps/8h rt=0.018 floor_ok=False cost_ok=True GATE=False net24=+2.98
  BNBUSDT   f=0.650bps/8h rt=0.352 floor_ok=False cost_ok=True GATE=False net24=+1.60
  XRPUSDT   f=1.000bps/8h rt=1.820 floor_ok=False cost_ok=True GATE=False net24=+1.18
  ETHUSDT   f=0.374bps/8h rt=0.104 floor_ok=False cost_ok=True GATE=False net24=+1.02
whole universe: 248 positive-funding tradeable, 0 pass the gate
```
Every one passes the cost test (`funding×periods > rt_bps` — the test that actually protects) and fails ONLY the absolute floor. The journal agrees: `entry-gate: 4 cand(s) below funding/cost bar`, `carries=0`, tape frozen at 26.42/28 days (`fills_4wk=False` in the now-honest freeze-exit gate). The chain is exact: floor → no opens → no tape rows → `fills_4wk` never reaches 28d → S0→S1 freeze never lifts, regardless of the sign-off.

Disposition state: R0057 ("delete the absolute floor, do not lower it", roi_bps 7000, raised 2026-07-30T17:08) is **`status: open, disposed: null`** — it breaches the 24h no-orphaned-recommendation law at 17:08 today. R0066 (same defect from the growth audit) was `scheduled` with a reason demanding "a net-of-cost EV threshold derived from measured round-trip cost" — **which is precisely the test the gate already contains** (`_entry_gate` line 379: `funding × periods × 1e4 > _rt_bps(sym)`). The scheduled work item asks for something that already exists; the only change needed is deleting the redundant floor in front of it.

---

### F4 (HIGH, INTERNAL/two-evaluators) — there are now TWO Gate-0 evaluators that disagree: `check_gate0_ready.py` measures reality; `run_live_guard.py`'s `promo_evidence` reads the sign-off from a file that doesn't carry it, never supplies `symbol_count`, and calls the ramp rung "capital_fraction". One gate, two verdicts, different wrong reasons.

`run_live_guard.py:234-241` assembles the evidence for `staging.s1_entry_met`:
```python
promo_evidence = {
    ...
    "capital_fraction": size_fraction,          # <- the RAMP RUNG (0.10), not capital/equity (34.2% at the 00:09 board)
    "principal_signoff": bool(_load(... "data/stage_state.json", {}).get("principal_signoff")),
}                                               # <- stage_state.json has no such key; the signoff
                                                #    lives in data/gate0_signoff.json
$ cat data/stage_state.json
{"stage": "S0", "note": "S1 flips at live-connector deployment (Gate 0); ..."}   # no principal_signoff key
```
And `symbol_count` is absent from the dict entirely, so `s1_entry_met`'s `symbol_count_4_5` check reads its default 0 → False forever. Meanwhile `check_gate0_ready.py` reads the real sign-off file and computes the real capital fraction. Consequences: (a) live_guard's stage-gate will report S1 unmet even when every real criterion is green — and its one escalation hook (`if gate_met and not _PRINCIPAL.exists(): write PRINCIPAL_ACTION`) can therefore never fire; (b) worse in the other direction, `capital_fraction: size_fraction` reads the ramp floor rung (0.10) which PASSES `<= 0.10` regardless of the actually-configured capital — at the 00:09 board the true fraction was 34.2% NOT-READY while live_guard's dict would have said True. Two evaluators for the gate that admits real capital, wired to different sources, wrong in opposite directions.

---

### F5 (HIGH, INTERNAL/scheduler-drift) — the installed crontab is NOT the manifest: gate-0 readiness runs 4-hourly where the manifest (and the launch window) demand hourly, the safety drills run WEEKLY where the manifest says daily, and the drift-checker that knows this has no consumer with authority.

```
$ grep -E "gate0|drills" ops/crontab.manifest
9 * * * *   ... check_gate0_ready.py     # "gate0 readiness HOURLY for the launch window"
40 3 * * *  ... run_drills.py            # "drills DAILY (19 checks in ~3s)"
$ crontab -l | grep -E "gate0|drills"
9 */4 * * * ... check_gate0_ready.py     # installed: every 4 HOURS
40 3 * * 1  ... run_drills.py            # installed: WEEKLY, Mondays
$ .venv/bin/python scripts/check_scheduler_manifest.py | head
scheduler-manifest check | 73 cron entries, 13 systemd entries, 70 scripts referenced
  DRIFT   manifest-only (box does not run it): ... run_drills.py (40 3 * * *)
  DRIFT   manifest-only (box does not run it): ... check_utilisation.py, run_max_push.py,
          blindspot_max.py, build_enforcement_matrix.py, check_timidity_language.py, ... (19+ lines)
```
Measured effect today: the gate-0 board (`data/gate0_readiness.json`, generated 00:09) still reports `capital $4,500 / equity $13,155 = 34.2% NOT-READY` and `top=10` — but `data/cashcarry_config.json` was updated to `capital=200, top=4` at 02:00. The launch board is stale against the launch config during the launch window, purely because the hourly cadence exists only in the manifest. `daily_research_cycle` is additionally DOUBLE-scheduled (two 02:00 entries from different installer generations, one pgrep-guarded, one flock-guarded — two different lock mechanisms that do not see each other). The deploy path has a self-installing scheduler (`a92fe0e`) but this box's crontab predates it; the drift-checker fires and its output goes to a log.

---

### F6 (MEDIUM-HIGH, INTERNAL/false-green) — the Gate-0 board's `connector_verified` criterion reads READY off 517 TESTNET fills; the live connector it vouches for has never made a signed call.

`check_gate0_ready.py:56-69` — docstring: *"Verified means a real round-trip against the venue was recorded — not that code exists."* Implementation: `coverage()["n"] > 0` over `data/moat/execution_tape/cashcarry_trades.jsonl` — a tape whose 517 rows are all testnet fills:
```
$ cat data/gate0_readiness.json | grep -A3 connector_verified
"criterion": "connector_verified", "status": "READY",
"detail": "517 recorded fills in the execution tape"
```
The criterion cannot distinguish "the mainnet connector works" from "the testnet book traded last month" — the tape has no venue field it filters on. The sign-off record itself (data/gate0_signoff.json, written 22:28) lists `connector_verified` among the criteria "remain[ing] unmet", contradicting the board's READY 2 hours later — the human and the board are reading the same word differently. The right evidence for this row is `binance_live.is_armed()` + one recorded signed read (the canary's own artifact, `data/canary_state.json.last_ok_ts` — which exists as a concept but has never been produced, see F7). Until then the board overstates readiness on exactly the criterion that distinguishes paper from money.

**And `keys_present` is a SECOND false green on the same board.** The filter counts any `data/secrets/` file with "binance" in the name:
```
$ .venv/bin/python  # reproduce _keys_present()'s filter
board counts as live-venue credentials: ['binance_live.json', 'binance_spot_testnet.json',
                                         'binance_testnet.example.json', 'binance_testnet.json']
```
Two testnet keyfiles and the checked-in **.example** file count as live-venue credentials — the row read READY before any live key existed. The one file that IS named for live (`binance_live.json`, written 00:01 tonight) holds an 18-character key and 18-character secret — real Binance keys are 64 characters; this is a stub. The spot-leg live keyfile (`binance_live_spot.json`) does not exist at all, which is the exact HALF-ARMED hazard `run_live_guard._arming()` was written to name. The connector itself is honest — `binance_live.is_armed()` → `(False, 'keys_present=True, live_enable_flag=False, vps_verified=False')` — so the fix is to make the board's row read `is_armed()[0]` per leg instead of globbing filenames. As it stands, of the board's three green rows, two (`keys_present`, `connector_verified`) are false greens and only `principal_signoff` measures what it claims.

---

### F7 (CRITICAL, INTERNAL/actuation — the rails compute, the executor ignores) — the entire §4/§5/§6 guard stack (ladder size multipliers, canary limit-only/half-size mode, ramp SIZE_STEPS) produces an `effective_size_fraction` that NO order path ever applies. The executor's only coupling to the guard is the binary KILL file.

```
$ grep -n "live_guard\|effective_size\|size_fraction\|ramp\|canary\|derisk\|ladder" scripts/run_cashcarry_executor.py
(exit 1 — zero matches)
$ grep -n "_KILL" scripts/run_cashcarry_executor.py | head -3
46:_KILL = Path("data/CASHCARRY_KILL")
628:    _flatten_only = _KILL.exists() or state.get("last_risk_action") == "flatten"
721:    _KILL_FORCES_RAIL = _KILL.exists()
```
`run_live_guard.py:262` computes `effective_size = size_fraction × rung.size_multiplier × mode.size_multiplier` and writes it to a report. Nothing reads it. Concretely on live day: (a) the ramp gate's fail-closed 0.10 floor rung sizes NOTHING — the executor trades at whatever `cashcarry_config.capital` says, so "ramp to full size over weeks" is a report, not a behavior; (b) canary DEGRADED mode (limit-only, 0.5×) is unenforceable — the executor will place market orders while the canary says limit-only; (c) ladder rung size multipliers same. The guard can freeze (binary) but cannot size or restrict order type. Every one of these modules is individually excellent (fail-closed defaults throughout — `ramp_gate` reads every metric with a failing default, `canary.mode()` treats no-record as degraded); the failure is one missing consumer edge: the executor should read `data/live_guard.json:effective_size_fraction` (and a limit_only flag) each rebalance, exactly as it already hot-reads `cashcarry_config.json`.

**Compounding it, the canary is cadence-starved by its own runner.** `CANARY_INTERVAL_S = 6h`, `is_stale()` fires at 2× = 12h, and `mode()` degrades on stale (*"canary has not run in Xh -- probe itself unproven"*). The only runner is `daily_research_cycle` (daily). Even working perfectly, the probe runs every 24h, so the canary reads DEGRADED ~12 of every 24 hours by arithmetic — a permanent half-size, limit-only oscillation nobody chose... which currently costs nothing because of (b). Two defects mask each other: fixing the actuation without fixing the cadence would halve launch size on alternate half-days; fixing neither leaves the rails decorative.

**And the ramp's evidence dict has no producer.** `_ramp()` reads `ramp_state.json:evidence` — grep finds no writer of that key anywhere. Fail-closed means the ramp stays at 0.10 forever (safe), but "the size ladder can never step up because nobody measures the five conditions" is the same delivery-break class as everything else in this list — it will be discovered as a mystery in week 9.

---

### F8 (CRITICAL, INTERNAL/launch-blocking) — `place_stop_market` — the venue-side protective stop §3 is built on — has ZERO production callers, while go_live.md's pre-arming checklist REQUIRES it wired into the executor. On live, the first open position is naked by construction; when the guard notices (daily, F7), it freezes the book and pages.

```
$ grep -rn "place_stop_market" scripts/ libs/ tests/ --include=*.py | grep -v __pycache__
libs/execution/binance_live.py:358:def place_stop_market(...)          <- definition
tests/execution/test_binance_live_behaviour.py:5,44,49,54,58,64        <- tests only
$ grep -n "protective stops" docs/playbooks/go_live.md
19:- Venue-side protective stops (`binance_live.place_stop_market`) wired into the executor's
```
The full §3 chain exists: the venue capability (`binance_live.py:358`, reduce-only STOP_MARKET, behaviour-tested), the pure invariant logic (`protective_stops.py`, quantity-covering with partial-cover detection — genuinely good), the reconciler driver (`run_live_guard._reconcile`). What does not exist is the ONE edge that matters: nothing in the executor's open path places a stop after opening. The chain on launch day: open fills → no stop resting → `reconcile()` (whenever live_guard next runs) finds naked > 60s → `freeze_entries` → CASHCARRY_KILL written → book frozen + page. The launch does not lose money to this — it *self-strangles*: designed rails, working as coded, freeze a healthy book because the placement half was never wired. `go_live.md:19` knows this is required — but it is a prose checklist item with no mechanical check; `check_gate0_ready.py` does not measure it (the board's `connector_verified` READY, F6, actively suggests otherwise). §42's own words: *"before calling any knob, governor or helper done, name the production caller. If there is none, it is not done."* Four of the five S1 rail mechanisms currently fail that test (stops placement, ramp actuation, canary actuation, ladder size actuation); the fifth (freeze) passes.

---

### F9 (HIGH, INTERNAL/outcome-not-config) — the S1 rail driver has never executed: zero artifacts from `run_live_guard` (no live_guard.json, no canary/ramp/derisk state), and the sub-accounts capability shipped today is manifest-only. The 60-second naked-position invariant is wired to a 24-hour clock.

```
$ ls data/live_guard.json data/ramp_state.json data/canary_state.json data/derisk_state.json data/subaccounts.json
ls: cannot access ... No such file or directory   (all five)
$ pgrep -af daily_research_cycle    # today's cycle started 02:00, in flight at audit time
1495143 .venv/bin/python scripts/daily_research_cycle.py
```
`run_live_guard` was wired into `daily_research_cycle.py:58` yesterday; today's 02:00 cycle is its first chance to run. That closes the "never ran" gap within hours *if it succeeds* — but the structural defect stays: a NAKED_GRACE_S=60s invariant and a 6h canary evaluated once per day. The guard needs its own cron line at minutes-cadence once keys are armed (it is deliberately inert/cheap at S0 — the design supports it; only the schedule is missing). `sub_accounts.probe` (principal-ordered capability, 13 tests green, manifest line `48 5 * * *`) has never run for the F5 reason: the manifest line was never installed. Config says daily; outcome says zero executions ever.

---

### F10 (HIGH, INTERNAL — the generalised checker has the same hole one level down) — the rewritten freeze-exit gate's `gate0` criterion reads `data/gate0_complete`, which has ZERO writers; `_FREEZE_SOURCES` names `max_audit.py` as its writer, but max_audit only READS the file; and `check_freeze_exit_sources()` cannot see this because it only asserts the writer FILE exists on disk.

```
$ grep -rn "gate0_complete" scripts/ libs/ --include=*.py | grep -v __pycache__
scripts/run_cadence.py:160:    "gate0": ("data/gate0_complete", "scripts/max_audit.py"),   <- claimed writer
scripts/run_cadence.py:214:    checks["gate0"] = Path("data/gate0_complete").exists()      <- the read
scripts/max_audit.py:1257:    if not (ROOT / "data/gate0_complete").exists():             <- max_audit READS it
scripts/max_audit.py:1263:        "Gate 0 is COMPLETE (data/gate0_complete) but ..."       <- and reads it again
(no write/touch/open-w anywhere)
```
Yesterday's F1 was "three of five criteria read files nothing writes"; the fix rewired two honestly (verified in R-CHECK above), declared the pattern generalised via `check_freeze_exit_sources()` — and the FIRST criterion still reads a file nothing writes. The checker passes because its assertion is `(_ROOT / writer).exists()` — the writer *file* exists; whether that file contains a write of the artifact was never checked. So `_freeze_exit_met()` remains unsatisfiable as written: when the tape crosses 28 days, `gate0` will still read False forever, and the S0→S1 freeze still cannot lift. Same fix class as F1: either have max_audit actually write `data/gate0_complete` when its Gate-0 conditions hold (presumably the intent), or point the criterion at `data/gate0_readiness.json:ready`. And strengthen the checker to grep the writer for the artifact name — the assertion that was built is weaker than the defect it was built from.

---

### F11 (MEDIUM-HIGH, INTERNAL/wrong-denominator) — the Gate-0 capital-fraction gate divides live launch capital by the MOLDED PAPER equity curve ($13,155, honestly stamped "PAPER (testnet)" in its own row), so the board can read 1.5% READY while the fraction against real launch capital would be 20% — a breach.

```
$ tail -1 data/nav_attestation.jsonl
{"date": "2026-07-30", "equity_marked": 13154.86, ..., "mode": "PAPER (testnet) -- pre-Gate-0", ...}
```
`check_gate0_ready._capital_fraction` computes `cfg.capital / _desk_equity_usd()`, and `_desk_equity_usd` → `capacity_policy.live_book_usd()` → last NAV-chain row = the molded curve seeded at a simulated $15,000. Every capacity band correctly uses this pre-Gate-0 (it is the only book there is). But the S1 criterion is *"capital fraction <= 0.10 of authorized LIVE capital"* — and on launch day authorized live capital is the deposit (~$1,000 per the runbook example), not the paper curve. `capital=200 / 13,155 = 1.5%` READY today; `200 / 1,000 = 20%` is the honest launch-day number. The gate goes green by dividing real dollars by simulated ones. Post-deposit this self-corrects only if the NAV chain switches to venue truth immediately (its writer stamps `mode` but nothing gates the criterion on mode ≠ PAPER). Cheap fix: the capital-fraction row should refuse (BLOCKED-UNKNOWN) while the NAV chain's latest row is PAPER-mode, or read the live wallet once keys are armed — the row already has the fail-honest vocabulary for exactly this.

---

### F12 (MEDIUM, INTERNAL/process-vs-disk drift) — the running executor predates every money-path commit of the last 44 hours; the rail re-arm "worked" on the running process only because the venue-side `multiAssetsMargin` flag was flipped, changing the API response under the OLD code. Nothing tracks code-in-memory vs code-on-disk for money-path services.

```
$ systemctl show quant-cashcarry.service -p ExecMainStartTimestamp -p NRestarts
ExecMainStartTimestamp=Wed 2026-07-29 06:36:30 UTC        NRestarts=0
$ stat -c '%y %n' libs/execution/binance_testnet.py
2026-07-30 22:56 libs/execution/binance_testnet.py         <- fixed 40h after the process started
$ .venv/bin/python -c "...binance_testnet _signed /fapi/v2/account..."
multiAssetsMargin = True | totalMarginBalance = 5769.49    <- venue flag now ON (was False yesterday)
```
The in-memory executor still runs the pre-fix `account_summary()` (single-field read). It currently reports correct equity *only because* `multiAssetsMargin=True` makes `totalMarginBalance` complete — flip that venue flag back and the running process re-enters yesterday's blind state with no code change and no signal. More generally: `fccc580`, `de017ef` and the maker/close changes all landed while the process kept running; config hot-reload covers `top/hold_top/capital` only, never code. A restart-after-money-path-commit rule (or a max_audit check comparing ExecMainStartTimestamp against the newest mtime of the executor's import closure) is ~10 lines and closes a class: audited-code ≠ trading-code is invisible today.

---

### F13 (MEDIUM-HIGH aggregate, INTERNAL/§33-unconverted — the carry-over ledger, every line re-verified today) — seven of yesterday's findings are untouched, several now stale enough to owe dispositions:

| yesterday's finding | state today (measured) |
|---|---|
| `venue_reconcile` verdict self-contradiction (F9-old) | UNFIXED and now stale: `verdict: NO_GAP, residual: -4399.91, updated: 2026-07-29T16:06` — 34h old |
| CI stamps phantom naked-leg incidents (F12-old) | STILL FIRING: `data/cashcarry_error.log` stamped 2026-07-31T02:04:24 with the same MOVEUSDT 47306.0 fixture |
| SPOT-EXCESS demands human action into an unread log (F16-old) | UNCHANGED: still an action-list line, no pager/PRINCIPAL_ACTION hook (executor:570) |
| reconcile retry unbounded (F15-old) | UNCHANGED: surfaces at 3 consecutive fails, no cap/escalation after (the 2,334× spin remains possible) |
| tape duplicate closes (F5-old) | UNCHANGED: 262 closes, 89 phantom extra rows; state persist still one non-atomic `write_text` at `_rebalance` end (executor:874) |
| hurdle-rate verdict zero consumers (F18-old) | UNCHANGED: `grep hurdle scripts/max_audit.py` → nothing |
| BNB burn inert (F8-old) | UNCHANGED: futures BNB `walletBalance: 0.00000000`, `feeBurn: True` — ~148h old |
| TCA unwired (F19-old) | WORSE than unchanged: the desk's own CRO ranked `execution_tca_fill_log` its top ROI item (0.128) last cycle, and `web/tca.json` still has no writer — only an existence check in research_cycle.py:125 |

R0057 (delete `_MIN_FUNDING`) breaches its 24h disposition bar at 17:08 today. These are not re-findings; they are the §33 conversion debt of the audit organ itself, listed so the synthesis seat can row/dispose each.

---

### F14 (MEDIUM, INTERNAL/drill coverage) — the drill battery is honest and green (3/3, pure functions against temp copies) but drills 3 of ≥7 rails, and by construction cannot see wiring defects — proven this sweep: `ruin_rail_reentry` 4/4 PASS while the CLI that invokes the same mechanism reads $0.00 equity from a phantom file (F1).

```
$ grep -n "DRILLS = " scripts/run_drills.py
186:DRILLS = (drill_host_death, drill_derisk_ladder, drill_ruin_rail_reentry)
```
Not drilled: the dead-man switch (the ONE rail found silently disarmed this week — no drill asserts `should_fire` fires at 0.64×HW, or that `high_water ≥ _MIN_HW` while live), the CASHCARRY_KILL freeze path (does the executor actually honour the file? asserted nowhere), the canary degrade/recover cycle, stage demote-on-tripwire, and the capital-event CLI end-to-end (a `--show` on a healthy box asserting equity ≠ $0.00 would have caught F1 in one line). The drill harness is the right vehicle — each addition is ~30 lines in an existing green frame. Also worth stating: drills run WEEKLY on this box (F5 drift), so "0 critical drill failures" ages up to 7 days, and the S2 gate consumes `critical_drill_failures` with a fail-closed default that will read -1/refuse if the report goes stale — correct behavior, surprising week-9 mystery.

---

### F15 (LOW-MEDIUM, FRONTIER — post-Gate-0 levers, named now so they are on the register) — the execution path is REST-polling only: no user-data stream, no order-amend, no WS order entry.

```
$ grep -rn "listenKey\|userDataStream\|wss://" libs/execution/*.py scripts/run_cashcarry_executor.py
(nothing)
```
Three venue capabilities, all free, all standard since well before the desk existed: (a) **user-data stream** (`listenKey`) pushes fills/position changes in real time — the reconcile loop currently discovers naked legs by polling on a rebalance interval, and the ERM's fill timestamps are poll-quantised; (b) **order amend** (futures `PUT /fapi/v1/order`) preserves queue position on maker requotes — the maker path currently cancel/replaces, going to the back of the queue each time, which directly suppresses the maker fill-rate the strategy's economics assume; (c) **WS order entry** cuts the REST round-trip. None are pre-Gate-0 blockers; (b) is the cheapest and most aligned with the measured problem (spot maker fill-rate 33% on n=9). Ranked correctly behind every wiring fix above.

---

### F16 (empty seams — checked, found empty, reported per the exhaustion mandate)

- **Funding fidelity (U4, still open):** capability to read venue `FUNDING_FEE` income exists (`binance_live.py:198,238`, `run_deadman_reconciliation.py:117`) but no artifact compares `est_funding` against credited funding, so every funding number in the forward record remains modelled, not measured. Unchanged from yesterday; the comparison is ~20 lines against data already on disk.
- **Latency (U7, still open):** `_tca()` now stamps `wait_s` per fill (real progress, wired 07-27) but there is no venue round-trip latency percentile tracking and no alert on degradation. The canary records `latency_ms` per probe — once it runs (F9), that seam half-closes for free.
- **Venue-relations pressure recurred and cleared:** yesterday's daily cycle logged `HTTP 418: I'm a teapot` on two steps (axis_shadows, shadow_8h) — the second 418 episode in three days. At audit time the endpoint serves normally (my `_ranked()` reproduction pulled 248 live funding rows). Single-IP concentration remains the structural exposure; the second-venue spec's circular Gate-0 dependency noted yesterday stands.
- **Order-path information leakage:** re-checked the new close/reduceOnly logic (executor:1085-1093) — reduce-only on close legs, cancel-before-replace retained; no resting-size stacking. Clean.
- **Key hygiene on the launch path:** `finish_setup.sh` writes secrets `chmod 600` under `umask 077`, never echoes them back, and `.gitignore` covers `data/secrets` (checked: `git check-ignore data/secrets/binance_live.json` → ignored). Clean.

---

## 1. WHAT WE KNOW — validated strengths, each with its proving command

**W1. The dead-man rail is armed and fires — verified by replay, not by commit message.** `should_fire` returns True after 5 consecutive breaches at 64% of the $5,777 high-water, at every tested equity (see R-CHECK). The state now carries `disarmed_live`/`disarmed_paged` flags so the failure mode that hid for weeks has a name in the state file.

**W2. The freeze-exit rewrite is real and mostly honest.** `_freeze_exit_met()` → `cost_model=True, calib_10=True` from artifacts that exist; `days` from row timestamps, not mtime; `_FREEZE_SOURCES` documents claimed writers. (The `gate0` criterion's writer claim is false — F10 — but the *structure* now makes that claim checkable, which is why this sweep could check it.)

**W3. The absorbing state was cleared the right way.** No re-baseline, no threshold touch: the equity *measurement* was fixed (per-asset sum + venue `multiAssetsMargin=True`), and the journal shows `net=$3701`, `last_risk_action: "ok"`, zero RISK-FLATTEN lines since. `capital_events.effective_start_equity` is verified read-only-when-no-ledger (executor:694-698).

**W4. The new rail modules are individually excellent.** Every one is fail-closed by construction, and each encodes a hard-won lesson: `ramp_gate` reads every metric with a failing default; `canary.mode()` treats no-record as degraded; `staging.s2_entry_met` defaults `critical_drill_failures` to -1 (the mutation-testing find, twice); `protective_stops` compares *quantities* not presence (partial-cover detection); `capital_events.rebase` refuses unsigned/unreasoned/zero-deposit re-bases with correct override semantics. The defects in this report are all WIRING; the mechanisms are the best-engineered on the desk.

**W5. The three-factor live arming design is honest.** `binance_live.is_armed()` → `(False, 'keys_present=True, live_enable_flag=False, vps_verified=False')` — keys alone cannot arm it, a stub key cannot fake it, and the reason string names what is missing. Ditto `finish_setup.sh` key hygiene: umask 077, chmod 600, never echoes a secret, `data/*` gitignored (verified with `git check-ignore`).

**W6. Config hot-reload works, measured end-to-end.** `cashcarry_config.json` edited at 02:00 → journal shows `entry-gate: 4 cand(s)` on the next rebalance (was 10). The claim in the commit message ("live-tunable, no restart") is TRUE for `top/hold_top/capital` — which is exactly why F12 (code is NOT hot) deserves its own line.

**W7. Fill instrumentation is now on every executor order path.** `_tca()` stamps `spot_mode/fut_mode/slip_bps/wait_s` at open, topup, and close (executor:766,817,866,1004-1028). The ERM's n=9 problem is now a *book-is-flat* problem, not a missing-instrumentation problem.

**W8. The drill harness is the right vehicle and tells the truth about itself.** `"No drill places or cancels a live order. Every drill runs pure decision functions against temp-directory copies"` — honest scope, honest artifact, 19 checks in ~3s. Its coverage is thin (F14), but nothing about it lies.

**W9. The daily cycle runs the guard from today.** `run_live_guard` is in the daily step list and today's 02:00 cycle was mid-flight at audit time — the wiring commitment is real even though zero artifacts existed yet (F9).

## 2. WHAT WE DON'T KNOW — ignorance ledger

| # | Unknown | Why we cannot answer it |
|---|---|---|
| U1 | Whether `record_capital_event` has ever been run against real state | it reads a file that has never existed (F1); `--show` returns $0.00 on a live book, so every prior invocation saw fiction |
| U2 | Maker fill-rate / slippage distribution at usable confidence | unchanged n=9/n=4 — the book has been flat since 07-28; instrumentation is ready (W7), evidence is not accruing (F3) |
| U3 | Whether BNB fee burn works | balance still 0.00000000 (148h); the 25% discount has never once applied |
| U4 | est_funding vs venue FUNDING_FEE fidelity | comparison never built; income-reading capability exists unused (F16) |
| U5 | Venue round-trip latency distribution | no percentile tracking; canary would half-close this and has never run (F9) |
| U6 | Whether the executor honours CASHCARRY_KILL end-to-end under live conditions | code reads it (executor:628,721,1302) but no drill or test asserts the full freeze behavior (F14) |
| U7 | What `daily_research_cycle` does with a failing live_guard step | first execution was in flight at audit close; failure handling of the new step is unobserved |
| U8 | Real behavior of `binance_live` order paths | behaviour-tested against mocks; zero signed calls ever made (stub key, `is_armed()=False`) — the first real order remains the first test |
| U9 | Whether the venue `multiAssetsMargin` flag stays True | someone flipped it at the venue (undocumented); the running executor's correctness now depends on it (F12) |
| U10 | Fill behavior above the $500 cost-model notional | unchanged from yesterday; capacity beyond the tested size is extrapolation |

**Suspected unknown-unknowns.** Yesterday's sweep predicted "more inert levers of the same class; the population is not exhausted" — this sweep found SEVEN more (gate0_complete phantom writer, cashcarry_state.json phantom file ×2 scripts, last_combined_equity phantom key, ramp evidence no-producer, web/tca.json no-writer, keys_present filename-glob, connector_verified venue-blind). The generator is still running: every one was created *after* the pattern was named. The class fix (a repo-wide read-implies-writer assertion) is now the highest-leverage single check on the desk, and until it exists I predict the next sweep finds more.

## 3. WHAT COULD MATTER MOST — ranked by impact × confidence / (cost × maintenance)

**⚡ = compounding multiplier.**

| # | Action | Impact | Conf | Cost | Why it ranks here |
|---|---|---|---|---|---|
| **1** | **Fix the capital-event wiring before launch day** — point `record_capital_event.py` + `check_gate0_ready.py` at `data/cashcarry_positions.json`; have the executor persist `last_combined_equity` per tick; add a refusal when computed equity is 0 on a box with a state file (F1) | the launch trigger currently loosens the ruin rail ~89% and poisons an append-only ledger | high | ~15 lines | The single worst live path on the desk: it fires exactly once, on launch day, with money, and it is wrong. Everything else can be fixed after launch; this one cannot be fixed after it runs. |
| **2** | **Copy the 3-line equity fix to `binance_live.py:188`** (max of per-asset sum vs totalMarginBalance) (F2) | prevents replaying the entire F3/F6/F13 chain on mainnet, where the default is `multiAssetsMargin=False` | high | 3 lines | Proven fix, proven failure mode, unprotected on the one connector that will carry real money. Do it the same hour as #1. |
| **3** | **Wire stop placement into the executor's open path** (`place_stop_market` after each open; abort+close on stop-placement failure) (F8) | without it the launch book self-freezes on its first position | high | ~25 lines | go_live.md already requires it; the board should measure it (add a `stops_wired` row). §3 is currently a detector that punishes the absence of its own actuator. |
| **4** | **Give the executor ONE consumer edge for the guard** — read `live_guard.json:effective_size_fraction` + `limit_only` each rebalance, multiply into sizing, honour limit-only (F7) ⚡ | turns the entire §4/§5/§6 stack from reports into behavior | high | ~15 lines | One edge activates four mechanisms at once. Must land with #5, or canary staleness halves size on alternate half-days. |
| **5** | **Schedule `run_live_guard` at minutes-cadence + install the manifest** (fixes F5 drift wholesale: guard, drills daily, gate0 hourly, sub_accounts probe) (F5, F9) ⚡ | the 60s invariant stops being checked daily; every manifest-only organ starts existing | high | one `crontab` install + 1 line | The deploy already has a self-installing scheduler; this box never ran it. One command retires ~20 phantom schedule entries. |
| **6** | **Delete `_MIN_FUNDING`, dispose R0057** (F3) | restarts the book; unfreezes the Gate-0 tape clock at 26.42/28d | high | 1 line | Third consecutive sweep naming it. The launch sign-off is given, the sizing is set, and this constant is the only thing keeping the evidence clock frozen. R0066's "build an EV threshold" is already built — it IS the cost test. |
| **7** | **The class fix: read-implies-writer assertion in max_audit** — for every `data/*` path a script reads, assert a writer writes it (grep the writer for the artifact name, not merely for existence) (F1, F10, U-U section) ⚡⚡ | kills the desk's most prolific defect generator | high | ~40 lines | Seven new instances in 24h, three sweeps running. Fixing instances without the class check has a measured recurrence rate of ~7/day. This is the highest expected-value 40 lines available. |
| **8** | **Make the Gate-0 board measure what it names** — `keys_present` → `is_armed()[0]` per leg; `connector_verified` → live signed-read artifact; `capital_fraction` → refuse while NAV row is PAPER-mode; add `stops_wired` (F6, F11) | the launch board currently shows 2 false greens of 3 desk-green rows | high | ~30 lines | The principal signs off against this board. It must not be greener than reality during the one week it matters. |
| **9** | **Extend the drill battery to the unraveled rails**: deadman `should_fire` live-replay, KILL-file honoured, capital-event CLI `--show` ≠ $0.00 on a live box, canary degrade/recover (F14) ⚡ | drills become able to catch wiring, not just mechanisms | med-high | ~120 lines | The `--show ≠ $0` drill alone would have caught F1. Cheap, additive, already has a green harness and a (manifest) daily slot. |
| **10** | **Dispose the F13 carry-over table** — venue_reconcile verdict, CI error-log redirect, retry cap, SPOT-EXCESS page, hurdle consumer, BNB decision, atomic persist, TCA writer | eight known defects, all with written fixes from prior sweeps | high | ~80 lines total | None is individually urgent; collectively they are the audit organ's own §33 conversion debt, and every one has now been re-verified twice. |

**Interactions.** #1+#2 are one change window (both touch the equity read on the money path). #3+#4+#5 are one change window (the guard stack becomes real). #6 should land only after #1+#2 (restarting the book before the rail reads true equity re-runs yesterday's sequence in miniature — same ordering the 07-30 sweep specified, still correct). #7 makes #1/#10-class defects structurally impossible and should not wait for them.

**Opportunity cost of not fixing, 1 year.** #1 unfixed: the ruin rail launches ~89% looser than designed and the capital-events ledger is corrupted at inception — unbounded tail, and the reputational cost of a survival-rail failure on launch day is the program. #3/#4 unfixed: the launch self-freezes (measured behavior, not speculation), read as "live trading failed", likely triggering weeks of wrong-tree debugging — call it a month of launch delay, which at the desk's own compounding assumptions is the entire year's edge on the launch tranche. #7 unfixed: ~7 new phantom-artifact defects per day at the current generation rate, each costing a future audit hour to find — the compounding cost dwarfs the 40-line fix by any discounting.

## 4. WHAT WE TEST NEXT — concrete experiments

**T1 — Capital-event dress rehearsal (BEFORE launch day, on this box).** Fix #1, then run `record_capital_event.py --show` and assert it prints the executor's actual equity (±$1 of `net + 5000`), then a `--deposit 100 --kind DEPOSIT` against a COPY of state in a temp dir asserting `start_equity_after == equity_before + 100` with `equity_before > 0`. Success: the dress rehearsal is added as drill #4 and runs weekly. Kill condition: none — this is a survival-rail path; the drill stays forever.

**T2 — Guard actuation proof.** After #4+#5: place the canary into synthetic DEGRADED (write `degraded_until` in a temp state), run one executor rebalance in `--dry`, assert the log shows halved size and no market orders. Success: an assertion in tests/execution that fails if the executor ever stops consuming the guard. This is the outcome-check for the entire rail stack.

**T3 — First-live-order protocol (the U8 retirement).** On real keys, before the executor is armed: one manual minimum-notional round-trip through `binance_live.place_market` + `place_stop_market` + cancel, recorded to the tape with `venue: "live"` field added to the schema (also fixes F6's venue-blindness for all future evidence). Success: tape row with venue=live, stop visible in `open_orders()` during the window, clean cancel. This is the honest version of `connector_verified`.

**T4 — Funding fidelity (U4, unchanged design from yesterday, now with an owner).** Compare `est_funding` per position against venue `FUNDING_FEE` income rows over the next 20 live/testnet position-days. Success: median abs divergence < 10%; failure re-labels every funding number in the forward record as modelled. ~20 lines against data already collected.

**T5 — Read-implies-writer census (the #7 pre-work).** Enumerate every `Path("data/...")`/`_ROOT / "data/..."` READ in scripts/ and libs/, join against writes, publish the orphan list as an artifact with a ratchet floor. Success: the census exists, its count only falls, and max_audit fires on any new read-without-writer. Prediction to falsify: ≥5 more instances beyond the 7 found here.

**T6 — Process-vs-disk drift check (F12).** max_audit check comparing each money-path service's `ExecMainStartTimestamp` against the newest mtime in its import closure; defect when code is newer than the process by >24h. Success: the check fires TODAY for quant-cashcarry (started 07-29, code from 07-30), and clears after the next deliberate restart window.

---

## SCORES

| metric | value | basis |
|---|---|---|
| **current_capability_pct** | **34%** (floor 28% from 07-30, ratchet respected) | Up: dead-man armed (verified), freeze-exit mostly real, absorbing state cleared, fill instrumentation wired, rail modules built to a high standard. Held down hard by: the launch trigger reads fiction (F1), the live connector keeps yesterday's bug (F2), the guard stack actuates nothing (F7/F8), and the book still cannot open (F3). |
| **practical_ceiling_estimate** | **80%** (unchanged) | Single-venue, pre-live. The remaining 20% still needs multi-venue failover, impact/capacity modelling above $500 notional, live-fill calibration. |
| **ceiling_gap** | **46 pts** | Almost all of it remains recoverable by wiring, not by new capability — the striking fact of the 07-30 sweep is MORE true today: the desk built five more excellent mechanisms and connected one of them. |
| **opportunity_cost_1y** | **launch-day tail is the dominant term** | With sign-off given and keys arriving, the cost model changed shape overnight: it is no longer "100% of compounding foregone" (the freeze is now honestly fixable) — it is a bounded-probability, unbounded-severity launch-day failure: a rail loosened 89% at inception (F1) plus a self-freezing first week (F8/F7) plus a board that reads greener than reality (F6). |
| **confidence** | **high (0.9)** | Every load-bearing claim executed live: venue reads (signed), pure-function replays on live state, journal counts, filter reproductions, `--show` on the real box. The two extrapolations (launch-day deposit flow F1, self-freeze sequence F8) are traced through code line-by-line but have, by definition, never run — flagged as such. |
| **unknown_unknown_score** | **HIGH (0.8, up from 0.75)** | Yesterday predicted the inert-lever population was not exhausted; this sweep found seven MORE, all created after the pattern was named. The generator outruns the finder. Score falls only when #7 (the class check) exists. |
| **info_gain_if_investigated** | **very high** | T3+T2 together convert the entire launch stack from believed-working to observed-working before real size arrives. |
| **expected_alpha_contribution** | **direct: LOW. indirect: TOTAL.** | Unchanged, sharpened: the carry itself remains ~5%/yr-class vs T-bills; but every finding here sits between the desk and its FIRST deployed dollar. Execution is not an alpha source; it is now the entire critical path to the objective. |
| **expected_compounding_contribution** | **VERY HIGH** | #7 (read-implies-writer) and #9 (wiring-aware drills) raise the value of every future mechanism the desk builds — which, on this week's evidence, it builds at ~5/day. |

**CEILING EXPANSION.** The 80% ceiling assumes execution capability is gated on live evidence that only Gate 0 can produce. This week weakened that assumption from a second direction: the desk can now build near-ceiling *mechanisms* in a day (five in one day, all fail-closed, all property-tested) — the binding constraint is provably not engineering capacity but **integration verification**: nothing systematically proves that built things are called, called things are scheduled, and scheduled things actuate. That is an organisational/methodological ceiling, it is the same lesson four days running, and it moves with ~160 lines (#7, #9, T2, T6). If those land, the honest ceiling estimate RISES (multi-venue and impact modelling stop being "post-Gate-0 someday" and become the only remaining gap), and the desk's mechanism-production rate becomes a compounding asset instead of a liability inventory.

---

## HEADLINE

**The desk is one signed command away from launch, and that command is wired to a file that does not exist.** `record_capital_event.py` — the designed launch trigger, "the ONE command that remains" — reads `data/cashcarry_state.json` (never written by anything; the executor's state is `cashcarry_positions.json`) and a key (`last_combined_equity`) that has zero writers. Run as documented on launch day it records the book's equity as **$0.00** into an append-only ledger and re-bases the ruin rail to deposit-only — on today's book, moving the flatten line from ~$6,300 to **$650**, an ~89% silent loosening of a survival rail, unfixable after the fact because the ledger is deliberately immutable. Verified live: `--show` prints `$0.00` on a box running an $8,700 book. The drill that covers this rail passed 4/4 — it tests the mechanism, and the defect is the wiring.

Around that center, one pattern, six more instances: the equity fix that re-armed the dead-man **stopped one file short of the money** (`binance_live.py:188` still carries yesterday's USDT-only bug, on the connector about to hold real capital, where the venue default reproduces yesterday's exact conditions); the S1 guard stack computes size fractions, degraded modes and ladder rungs that **no order path consumes** (the executor's only guard input is the binary KILL file); the venue-side stop the §3 invariant demands has **zero production callers**, so the launch book's first position freezes the desk by design; the freeze-exit gate's `gate0` criterion reads a file whose claimed writer only reads it — the checker built yesterday to generalise this exact defect asserts only that the writer *file exists*; and the Gate-0 board the principal signs against shows two false greens out of three desk-green rows (`keys_present` counts testnet and .example files; `connector_verified` counts 517 testnet fills as live-connector proof).

The mechanisms themselves are the best-engineered on this desk — fail-closed defaults, honest refusal semantics, property tests, a drill harness that tells the truth about its own scope. The desk has fully solved "build it right" and has not begun to enforce "prove it is connected." Seven new read-without-writer instances appeared in the 24 hours since the pattern was named. **Fix order: the capital-event wiring and the live-connector equity read first (one hour, before keys are real); then stops placement + guard actuation + the scheduler install (the launch stack becomes behavior); then delete `_MIN_FUNDING` so the evidence clock restarts; then the 40-line read-implies-writer class check so this list stops regrowing.**

_Report complete. 16 findings + ratchet verification of 20 prior, all command-verified. Register rows owed to the synthesis seat: F1, F2, F7, F8, F10 (new critical/high), F13 table (8 carried items), R0057 breach. Auditor: weekly deep cold sweep, execution-growth, 2026-07-31._
