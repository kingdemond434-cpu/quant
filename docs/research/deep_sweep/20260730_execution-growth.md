# DEEP COLD AUDIT — EXECUTION-GROWTH — 2026-07-30

_Auditor: weekly deep cold sweep (execution-growth subsystem). READ-ONLY. Every claim carries its proving command output. Prior run (20260730 slot) died BRAIN_AUTH_FAILED; the 07-29 run died mid-findings (F1–F3 written, outputs 2–4 never filled). This run writes the skeleton first and appends incrementally._

**STATUS: COMPLETE.** 20 findings, every claim carrying its proving command output. Scores, headline and the four outputs are at the END of this document (the findings log is the working record; the synthesis follows it).

---

## FINDINGS LOG (raw, verified as discovered — synthesized into the four outputs at the end)

---

### F1 (CRITICAL, GREENFIELD/INTERNAL) — THE S0→S1 DEPLOYMENT GATE IS UNWIRED: three of its five criteria read files that NO organ on this desk has ever written, and the fourth is an INVERTED staleness test that can only pass when the fill feed is DEAD.

`scripts/run_cadence.py:150 _freeze_exit_met()` is the desk's only coded path from research-freeze (S0) to deployed capital (S1) — `docs/EVIDENCE_GATED_PROGRESSIONS.md:7` names it as the CODED enforcement of "Freeze lifts (S0→post-freeze)".

**Proof 1 — the three files do not exist and have no writer.** Each appears exactly once in the entire non-test, non-rollback codebase: at the point `_freeze_exit_met` *reads* it.
```
$ ls -la data/fills.csv data/weekly_cost_summary.json data/calibration.csv data/gate0_complete
ls: cannot access 'data/fills.csv': No such file or directory
ls: cannot access 'data/weekly_cost_summary.json': No such file or directory
ls: cannot access 'data/calibration.csv': No such file or directory
ls: cannot access 'data/gate0_complete': No such file or directory

$ grep -rn "fills.csv" --include=*.py --include=*.sh . | grep -v data/rollback | grep -vE "^\./tests/"
scripts/run_cadence.py:155:    fills = Path("data/fills.csv")
scripts/run_cadence.py:173:    """Best-effort mtime proxy for oldest fill; refined when fills.csv exists."""
$ grep -rn "weekly_cost_summary.json" ... | grep -v rollback | grep -vE "^\./tests/"
scripts/run_cadence.py:160:    checks["cost_model"] = Path("data/weekly_cost_summary.json").exists()
$ grep -rn "calibration.csv" ... | grep -v rollback | grep -vE "^\./tests/"
scripts/run_cadence.py:162:        calib = Path("data/calibration.csv")
```
The executor writes its fills to `data/cashcarry_trades.json` and `data/moat/execution_tape/cashcarry_trades.jsonl`. **Nothing anywhere writes `fills.csv`.** The gate is reading a filename that was imagined and never built.

**Proof 2 — `fills_4wk` is logically inverted.** `_oldest_line_age()` returns `p.stat().st_mtime` (the file's LAST-write time), and the check is `(time.time() - _oldest_line_age(fills)) > 28*86400`. That reads "the file has not been touched for 28+ days", i.e. it demands a **dead** fill feed. A healthy, actively-appended `fills.csv` has `now - mtime ≈ 0` and fails forever. Demonstrated on a synthetic 60-row file, ageing only its mtime:
```
$ .venv/bin/python -c "<replay of the exact expression from run_cadence.py:156-159>"
  fills.csv FRESH (written now)    -> fills_4wk=False
  fills.csv 7d stale               -> fills_4wk=False
  fills.csv 29d stale              -> fills_4wk=True
  fills.csv 60d stale              -> fills_4wk=True
```
The function's own docstring concedes it: `"""Best-effort mtime proxy for oldest fill; refined when fills.csv exists."""` — a placeholder that was never refined, now load-bearing on the deployment decision.

**Proof 3 — the live verdict, and where it goes.**
```
$ .venv/bin/python -c "import scripts.run_cadence as C; print(C._freeze_exit_met())"
freeze_exit_met = False
why: gate0=False, fills_4wk=False, cost_model=False, calib_10=False, no_criticals=True
```
That string is written to `state["freeze_exit_status"]` (run_cadence.py:294) and **read by nothing**:
```
$ grep -rn "freeze_exit_status" --include=*.py --include=*.md --include=*.json . | grep -v rollback
scripts/run_cadence.py:294:            state["freeze_exit_status"] = why
```
One write, zero reads. No max_audit check, no principal page, no alarm. `data/cadence_state.json` has carried `"freeze_exit_status": "gate0=False, fills_4wk=False, cost_model=False, calib_10=False, no_criticals=True"` silently.

**Consequence.** The desk's entire research apparatus (L1.20: "research exists to improve deployed capital") funnels into a gate that is not merely unmet but **unbuildable as written**: satisfying it honestly requires creating a `fills.csv` and then abandoning it for a month. Nobody would discover this by working *toward* the gate, because the status string nobody reads is the only place the failure is stated. The desk could accumulate a flawless track record and the freeze would still never lift. This is the dominant limiter on objective #1, and it is a ~15-line fix (point the checks at the artifacts that actually exist; compare oldest-ROW timestamp, not mtime).

---

### F2 (CRITICAL, INTERNAL) — Gate 0's ">=4 weeks of live fills" clock is FROZEN at 26.42 days, 1.58 days short, and can never advance: the book that feeds it is in an absorbing state.

`libs/execution/execution_tape.py` exists specifically because Gate 0 was once structurally unreachable (its docstring: *"GATE 0 WAS STRUCTURALLY UNREACHABLE… A 18.6-day buffer evicts fills faster than 28 days can accrue"*). The eviction was fixed. The clock has now stopped for a **second, independent reason**.
```
$ .venv/bin/python -c "from libs.execution import execution_tape as T; print(T.coverage())"
{'n': 517, 'days': 26.42, 'first': '2026-07-02T05:18:33.130420+00:00', 'last': '2026-07-28T15:20:03.394160+00:00'}
```
`days` is computed as `last - first` over row timestamps. No row has been added since 2026-07-28T15:20 because the book is flat and cannot open (F3). So `days` is pinned at 26.42 — **1.58 days below the 28-day bar, permanently.** The desk is closer to this criterion than it will ever be again.

---

### F3 (CRITICAL, INTERNAL) — the carry book is in a mathematically ABSORBING state: the ruin rail measures drawdown against a FROZEN inception equity, and its remedy (flatten) removes the only mechanism that could clear it.

Live, every tick, for 21 hours at audit time:
```
$ journalctl -u quant-cashcarry.service | grep "RISK-FLATTEN" | head -1
Jul 29 11:14:20 [11:14:20] carries=0 net=$-1860.14 funding=$113.04 ['entry-gate: 10 cand(s) below funding/cost bar', 'RISK-FLATTEN ruin-floor breach -37.2%<=-35%']
$ journalctl -u quant-cashcarry.service --since 2026-07-28 | grep -c "RISK-FLATTEN"
113          # 113 consecutive rebalances, 100% of them, zero clears
```
Mechanism (`libs/risk/risk_controls.py:evaluate`): the flatten branch keys on `dd_start = eq/start_equity - 1`, where `start_equity = state["start_futures_equity"] = 5000.0`, frozen at inception 2026-07-02 and **never re-based**. With the book flat, `eq_c` is a constant (`futures equity + banked realised spot PnL`); with `risk.action == "flatten"` the executor sets `target, cands = set(), []` (run_cashcarry_executor.py:697-698), so opens are impossible; with no opens there is no funding; with no funding `eq_c` never rises. Self-sustaining.
```
$ .venv/bin/python -c "risk_controls.evaluate(5000-1860.14, 5000.0, 5061.379, 0.0, ruin_cap_lev=8.0)"
{'action': 'flatten', 'reasons': ['ruin-floor breach -37.2%<=-35%'], 'dd_from_start_pct': -37.2}
```
**This finding is NOT new and IS correctly escalated — see W1.** It is recorded here because F2 (the frozen Gate-0 clock) is its downstream consequence and had not been connected to it.

---

### F4 (HIGH, INTERNAL/moat) — the Execution Reality Model has n=9. 504 of 517 tape rows carry NO execution-quality fields at all; maker fill-rate is 33% on nine observations and slippage is measurable on four.

L1.11 names "an Execution Reality Model from our own fills" as a moat component. Measured:
```
$ .venv/bin/python  # mode histogram over the full tape
  OPEN  spot_mode {None: 200, 'taker_fallback': 2, 'maker': 2}
  OPEN  fut_mode  {None: 200, 'maker': 4}
  CLOSE spot_mode {None: 257, 'taker_fallback': 1, 'already-flat': 4}
  CLOSE fut_mode  {None: 257, 'maker': 1, 'already-flat': 4}
$ # slippage, the whole evidence base:
  CLOSE spot_slip_bps  n=4 median=48.89 mean=42.87 p90=59.17 max=59.88
  CLOSE fut_slip_bps   n=4 median=-5.25 mean=-5.09 p90=-4.58 max=-3.86
  CLOSE wait_s         n=4 median=3.70  mean=3.73  max=5.04
$ # true maker fill-rate, excluding already-flat non-fills:
  spot legs n=9 {'taker_fallback': 6, 'maker': 3} -> maker rate 33.3 %
  fut  legs n=9 {'maker': 9}                      -> maker rate 100.0 %
```
Cause: 504 of 517 rows were **backfilled** on 2026-07-26 from the rolling `cashcarry_trades.json` buffer, which never carried mode/slip/wait fields; only rows taped live afterwards have them.
```
$ rows by _taped date: {'2026-07-26': 504, '2026-07-27': 9, '2026-07-28': 4}
```
Consequences: (a) the maker-first strategy's central claim is evidenced by **three** maker fills; (b) `coverage()['days']=26.42` counts a 26-day span in which only 2 days produced execution-quality data — the Gate-0 "cost model populated from live measurements" criterion would be satisfied by a window that is 97.5% blind; (c) the one measured spot close slipped **+48.9 bps median**, ~16x a single 8h funding payment (~3 bps), but n=4 makes it an anecdote, not a model.

---

### F5 (HIGH, INTERNAL/data-integrity) — the "never-truncated, immutable" execution tape contains 89 duplicate close rows (34% of all closes) and 19 closes with no matching open.

```
$ .venv/bin/python  # over data/moat/execution_tape/cashcarry_trades.jsonl
opens 204 closes 262                      # 58 more closes than opens
distinct (symbol,opened) close keys: 173  rows: 262
duplicated close keys: 50   extra rows from dupes: 89
close-keys with NO matching open in tape: 10  rows: 19
top duplicated: XVGUSDT/2026-07-10T07:46:45 x4, DEXEUSDT x4, KITEUSDT x4,
                TSTUSDT x4, BNBUSDT x4, ZECUSDT x4, MOVEUSDT x4, NOMUSDT x4
```
This is the materialised cost of the 07-29 audit's F2 (close logged per-symbol, state persisted only at `_rebalance` end → a crash between the two replays every close). 89 of 262 close rows are phantom. Every consumer that sums `est_funding`, `price_pnl`, `held_hours` or counts winrate over the tape — the cost model, `run_trade_forensics`, TCA, and the Gate-0 evidence base — is reading a book that closed the same position up to four times. Note the tape module's dedupe is deliberately **multiplicity-preserving** (`backfill()` docstring: *"the executor legitimately emits byte-identical records… so a set-based backfill would collapse real fills"*), which is right for genuine repeat top-ups but means the tape faithfully preserves the executor's duplication bug forever. The fix belongs upstream (atomic state persist per close), not in the tape.



---

## 1. WHAT WE KNOW — validated strengths, each with its proving command

(filled at end)

## 2. WHAT WE DON'T KNOW — ignorance ledger

(filled at end)

## 3. WHAT COULD MATTER MOST — ranked opportunities

(filled at end)

## 4. WHAT WE TEST NEXT — concrete experiments

(filled at end)
---

### F6 (CRITICAL, INTERNAL — NEW, and it changes the pending Tier-3 decision) — the ruin rail undercounts the FUTURES account by $5,000: `account_summary()` reads `totalMarginBalance`, which is USDT-only because `multiAssetsMargin=False`. Both rails share the bug, and the reconciliation built to catch undercounts reads the same undercounted number.

The principal page (`data/PRINCIPAL_ACTION.md`, URGENT 2026-07-29) documents a $4,399.91 undercount of **stranded spot inventory**. That is correct and separate. This is an **additional, larger, futures-side** undercount that no organ has reported.

**Measured at the venue, read-only:**
```
$ .venv/bin/python -c "from libs.execution import binance_testnet as f; f._signed('/fapi/v2/account',{})"
  totalWalletBalance       = 209.43368256
  totalMarginBalance       = 209.43368256      <-- what the rail reads as "equity"
  multiAssetsMargin        = False
  assets with nonzero balance:
    BTC    wallet=    0.01000000  marginBal=    0.01000000  maxWithdraw=0.01000000
    USDT   wallet=  209.43368256  marginBal=  209.43368256  maxWithdraw=209.43368256
    USDC   wallet= 5000.00000000  marginBal= 5000.00000000  maxWithdraw=5000.00000000
  account_summary() -> {'wallet': 209.43, 'equity': 209.43, ...}
```
With `multiAssetsMargin=False` each asset has its own margin pool, so the account-level `totalMarginBalance` reports **USDT only**. $5,000 of USDC and 0.01 BTC sit in the same futures wallet, are tracked by the venue per-asset (`marginBalance: 5000`), and are fully withdrawable (`maxWithdrawAmount: 5000`) — and the rail values them at zero.

**This is the entire cause of the flatten.** Re-running the pure rail function with the USDC counted:
```
$ .venv/bin/python -c "risk_controls.evaluate(...)"
  rail sees (USDT only)    eq=   209.43  eq_c=  3139.86  dd_start= -37.20%  action=flatten
  +USDC counted            eq=  5209.43  eq_c=  8139.86  dd_start= +62.80%  action=ok
```
The book is not down 37%. On assets actually owned in the futures wallet it is **up 62.8%** against inception, and the rail would return `ok`.

**Both rails share the blind spot.** The dead-man switch — the Tier-3 "isolated, never-touch" rail whose whole design point is independence — reads the identical field:
```
$ grep -n "totalMarginBalance" scripts/run_deadman_switch.py
125:        fut_eq = float(acct["totalMarginBalance"])
```
`data/deadman_state.json` confirms it inherited the number: `"high_water": 209.43368256`. Two rails, one shared undercount: they are not independent on the axis that actually fired.

**The reconciliation cannot catch it.** `scripts/run_venue_reconcile.py` — written specifically to find rail undercounts — reads the spot account for inventory but takes the futures side straight from the same wrapper: `web/venue_reconcile.json` reports `"futures_margin_balance": 209.43` and `"rail_equity_measure": 209.43`. It has no USDC/BTC line for the futures wallet at all.

**Why this is decision-relevant right now.** The principal page's option **(A)** is *"re-baseline inception to the reconciled true equity"*. The reconciled true equity available today is built on `futures_margin_balance = 209.43`. Executing (A) as written would re-baseline to a figure **$5,000 too low**, and re-arm the identical absorbing trap at a lower level within days. **Option (A) should not be executed until `account_summary()` sums per-asset `marginBalance` (or `multiAssetsMargin` is enabled).** That is a ~5-line change and it is a precondition, not a follow-up.

Caveat stated honestly: this is the testnet account, and the round $5,000.00000000 USDC is consistent with a faucet grant rather than earned capital — so its *economic* meaning here is arguably noise. The **defect is not the balance, it is the measurement**: a mainnet account holding USDC collateral with `multiAssetsMargin=False` would be mis-valued by the ruin rail in exactly this way, and the rail would flatten a solvent book. That is a live-capital ruin-rail correctness bug that happens to have been exposed by testnet funds.

---

### F7 (HIGH, INTERNAL) — the churn loop quantified from venue records: 8,818 commission events and $3.14M of futures turnover in 7 days on a $4,500 book — 699x capital turnover, ~100x/day.

```
$ python3 -c "json.load(open('web/venue_reconcile.json'))"
  commission_7d                 = 1572.26
  commission_events_7d          = 8818
  implied_futures_turnover_7d   = 3144520.0
  residual_bps_of_turnover      = -7.0
```
Against `--capital 4500` (the service's `ExecStart`), $3.14M of one-leg futures turnover in 7 days is **699x** the book. The lifetime ledger agrees on the outcome:
```
$ python3 -c "json.load(open('web/cashcarry_live.json'))"
  funding_harvested   = 113.04
  fut_commission      = 1750.65
  leak_attribution    = {'basis': -222.53, 'fut_fees': 1750.65, 'residual': 0.0}
  non_funding_pnl     = -1973.18
  harvest_eaten_frac  = 17.456
  bleed_verdict = 'BLEED: non-funding PnL -1973.18 is 1746% of +113.04 funding harvest'
```
**88.7% of the entire lifetime loss is self-billed commission** ($1,750.65 of $1,973.18). Basis — the risk the strategy actually takes — accounts for $222.53, and `residual: 0.0` means there is no unexplained loss: the sleeve was not beaten by the market, it was beaten by its own order rate. The strategy has still never had a clean test (principal page finding 3, independently confirmed here from the venue commission stream).

---

### F8 (MEDIUM-HIGH, INTERNAL/measured lever) — BNB fee burn is ON and INERT: measured balance is exactly 0.00000000 while `feeBurn: True`. The ~25% discount has never applied to a single one of the 8,818 commission events.

```
$ .venv/bin/python -c "from libs.execution import binance_testnet as f; ..."
  BNB    balance=      0.00000000 avail=0.00000000
  feeBurn state: {'feeBurn': True}
```
This is the mandate's "MEASURED not configured" case in its purest form: the flag is green, the lever is dead. `_enable_fee_burn()` (run_cashcarry_executor.py:1344) fires both POSTs inside `contextlib.suppress(Exception)` — **fully silent**, so a rejected enable is indistinguishable from a successful one; only the balance check catches it. Already a live defect (`bnb-burn-unfunded`), unfixed for 123.6h at audit open.

Magnitude: 25% of the $1,750.65 lifetime commission is ~$437 — **3.9x the entire $113.04 funding harvest**. Two second-order consequences nobody has stated:
1. **Broker-behaviour bias in the cost model.** Every commission figure in the forward track record — the record Gate 0 sizes real capital on — is inflated ~25% versus what a BNB-funded live account would pay. The bias is *pessimistic*, which is the safe direction, but it is an unquantified systematic offset between the paper book and the live book it is meant to predict.
2. **The lever is unvalidated.** If BNB cannot be faucet-funded on testnet, the desk will switch on a 25% cost reduction for the first time *with real money*, having never once observed it work. That is an untested change to the largest single cost line.

Disposition owed either way: fund it, or ledger it as a testnet limitation with the live-side validation plan attached. Neither has happened.

---

### F9 (MEDIUM, INTERNAL/self-greening) — `run_venue_reconcile` publishes `verdict = "NO_GAP"` on a report whose own body says `UNDERCOUNT: $4,399.91` and `unexplained_residual: -4399.91`.

```
$ python3 -c "json.load(open('web/venue_reconcile.json'))"
  verdict                = 'NO_GAP'
  unexplained_residual   = -4399.91
  explained_share        = None
  notes[0] = 'UNDERCOUNT: $4,399.91 of real book inventory carries no live futures short and is
              valued at $0 by the ruin rail. Real assets, verified on venue.'
```
The verdict is keyed **only** on the spot stablecoin cash gap (`run_venue_reconcile.py:216-218`):
```python
out["verdict"] = ("UNRECONCILED" if (bps is not None and bps > 100)
                  else "RECONCILED" if gap > 0 else "NO_GAP")
```
`gap = cash_gap_vs_baseline = 0.0`, so the else-branch fires. The stranded-inventory finding — the reason the organ was written — **cannot influence its own verdict**. Any consumer reading the headline field sees a green light over a red payload. Additionally `residual_bps_of_turnover = -7.0` is negative, so it matches neither `bps > 100` nor `elif bps >= 0`: a negative residual falls through both branches and is silently unremarked.

---

### F10 (MEDIUM, ADJACENCY) — the reconciliation reads the rolling 500-row buffer, not the never-truncated tape built to replace it.

```
  trade_log_rows      = 500
  trade_log_truncated = True
  faucet_noise_value  = 182036.70
  notes[1] = 'LOWER BOUND: the trade log is a rolling window (500 rows), so symbols traded before
              it are counted as faucet noise. True book inventory is >= this figure.'
```
`libs/execution/execution_tape.py` exists precisely because `data/cashcarry_trades.json` is a `log[-500:]` buffer that had already destroyed ~141 fills. The tape (517 rows, never truncated) is right there and unused by this organ. Consequence: every symbol the book traded before the 500-row window is misfiled into `faucet_noise_value = $182,036.70` and written off, so the $4,399.91 stranded figure — the number the principal's Tier-3 decision rests on — is an unnecessary lower bound. Switching the source to `execution_tape.read()` is a one-line import and strictly tightens the estimate.

---

### F11 (CRITICAL, INTERNAL/gate-optimality — the SECOND independent blocker, and nobody has noticed it) — `_MIN_FUNDING` is the sole reason the book cannot trade, it has ZERO protective value in the live universe, and its only marginal effect is to veto the four net-positive liquid majors. Clearing the ruin rail will NOT restart the sleeve.

The journal shows the entry gate rejecting every candidate, every tick, for the entire journal window:
```
$ journalctl -u quant-cashcarry.service | grep -oE "entry-gate: [0-9]+ cand" | sort | uniq -c
    312 entry-gate: 10 cand      139 entry-gate: 9 cand
     50 entry-gate: 8 cand        11 entry-gate: 7 cand
$ journalctl -u quant-cashcarry.service --since 2026-07-28 | grep -icE "\bopen(ed)?\b"
0
```
Reproduced against the live venue universe:
```
$ .venv/bin/python  # _ranked() + _entry_gate(), real mainnet funding, real cost model
tradeable positive-funding candidates: 245
across ALL 245 positive-funding tradeable names: 0 pass the entry gate
  reject cause: structurally_bleeding=4  funding<0.00015=240  funding*3 <= rt_bps=1
```
**First, the honest half: the cost-aware test is excellent and must not be touched.** Of the 204 opens the book actually made, the current gate would allow **2 (1%)** — and the historical economics show why that is right:
```
symbol          n  med f_bps   rt_bps  net/24h   gate
COOKIEUSDT     21       2.40   131.38  -124.18  False     <- opened 21 times, -124 bps each
GTCUSDT        13       6.74    39.50   -19.28  False
MOVEUSDT        9       2.11    39.50   -33.17  False
TSTUSDT         9       3.02    39.50   -30.44  False
```
The `funding*3 > rt_bps` test is the fix for the churn loss. It is working.

**Now the defect, isolated by a 2×2 over the two gate conditions on the live non-bleeding universe (n=246):**
```
 MIN_FUNDING floor  cost test     n   verdict
              True       True     0   OPENED
              True      False     1   rejected      <- cost test protected; floor did NOT
             False       True     4   rejected      <- floor vetoed; cost test approved
             False      False   241   rejected

Names the COST test APPROVES but the MIN_FUNDING floor VETOES: 4
   BTCUSDT      f= 0.725 bps/8h  rt=  0.018  net/24h= +2.156 bps
   ETHUSDT      f= 0.454 bps/8h  rt=  0.104  net/24h= +1.258 bps
   XRPUSDT      f= 1.000 bps/8h  rt=  1.820  net/24h= +1.180 bps
   BNBUSDT      f= 0.494 bps/8h  rt=  0.352  net/24h= +1.131 bps

Names the FLOOR approves but the COST test vetoes: 1
   IOTXUSDT     f= 3.907 bps/8h  rt= 39.500  net/24h=  -27.78 bps
```
`_MIN_FUNDING = 0.00015` (1.5 bps/8h) is an **absolute** floor applied to a universe whose measured round-trip costs span **0.018 bps (BTCUSDT) to 131.38 bps (COOKIEUSDT)** — a 7,300x range. No single absolute funding number can be correct across it. Its stated rationale (`run_cashcarry_executor.py:315`, *"below this a carry cannot pay for its own exit"*) is empirically false by ~120x for BTCUSDT, whose 24h funding capture is 2.156 bps against an 0.018 bps round-trip.

In the live universe the floor rejects nothing the cost test would have allowed through (the (True,False) cell contains IOTXUSDT, caught by the cost test). It is **redundant in the protective direction and binding in the harmful one.**

**Why this is the finding that matters most operationally.** There are TWO independent locks on the book, and every organ and document — the principal page included — names only the first:
1. the ruin rail (F3/F6) — Tier-3, principal-only;
2. `_MIN_FUNDING` — ordinary engineering, and it alone rejects 245/245.

Even if the principal answers (A) or (B) tomorrow and the rail is re-baselined, `_rebalance` will compute `cands = []` on the very next tick and the book will stay flat, the tape will stay frozen at 26.42 days (F2), and the desk will conclude the rail fix failed. **The rail decision should not be executed without fixing this in the same change.**

**Honest sizing, stated against the L1.5 T-bill test.** The four blocked names yield +1.13 to +2.16 bps per 24h rotation at this funding snapshot ≈ **4.1%–7.8%/yr**, equal-weight ≈ **5.2%/yr**, delta-neutral, before slippage in excess of the modelled round-trip and before funding variation. Against T-bills at ~4–5% this is **marginal, not a windfall** — on $4,500 of capital it is roughly $185–350/yr. The case for fixing it is therefore **not** the carry; it is that this is the only lever standing between the desk and a resumed forward track record (F2), and that at post-Gate-0 capital the same four names scale linearly while the illiquid alts do not. Recommended change is a one-line deletion of the absolute floor, leaving `_structurally_bleeding` + the cost test as the gate — *not* a lowering of the number, which would re-open the calibration argument on every regime shift.

---

### F12 (HIGH, INTERNAL/observability — CARRIED OVER from the 07-29 audit, still unfixed 21h later) — CI runs are still stamping phantom naked-leg incidents into the production error log.

The 07-29 audit's F1 documented this. Verified still live at this audit:
```
$ stat -c '%y  %n' data/cashcarry_error.log
2026-07-30 08:05:13.945225716 +0000  data/cashcarry_error.log
$ cat data/cashcarry_error.log
2026-07-30T08:05:13.945128+00:00 unfilled leg MOVEUSDT spot_ok=True fut_ok=False
  spot_res={'status': 'FILLED', 'executedQty': '47306.0'} fut_res={'status': 'REJECTED', 'executedQty': '0.0'}
```
Stamped ~7 minutes before I read it. The quantity 47306.0 is the fixture in `tests/execution/test_carry_churn_loop.py:136`, which monkeypatches `fut`, `spot` and `_MAKER` but **not** the module-level `_ERR` path:
```
$ grep -n "monkeypatch.setattr" tests/execution/test_carry_churn_loop.py
109:  monkeypatch.setattr(_MOD, "fut", f)     110: ... "spot", s)
133:  monkeypatch.setattr(_MOD, "_MAKER", False)   134: ... "fut", _FlatFut())   135: ... "spot", _EmptySpot())
   # no _ERR patch anywhere
```
The book is flat and no order was placed, so this is unambiguously the test. The hazard is the cry-wolf inversion: a phantom naked-leg line is byte-identical in shape to a real one, so when a genuine unhedged spot leg occurs it will be dismissed as "the known test artifact". Same latent class for `_KILL`, `_HB`, `_STATE`, `_TRADES` module constants in any test that reaches them unpatched — worth a single conftest-level redirect of all module path constants to `tmp_path` rather than five individual patches.

---

### F13 (**THE HEADLINE — SEVERITY: MAXIMUM**, INTERNAL/survival rail) — the Tier-3 dead-man ruin switch is SILENTLY DISARMED. `should_fire()` returns False at *every* equity, including a 99.5% loss. Nothing on the desk checks whether it is armed; the process is alive, the heartbeat is fresh, and every liveness signal is green.

The dead-man switch is the desk's Tier-3, "isolated, never-touch" last line of defence (L1.23 survival rails). `systemctl` reports it `active running`; `data/deadman_heartbeat` is 21 seconds old. It cannot fire.

```
$ .venv/bin/python -c "<load run_deadman_switch, read live data/deadman_state.json>"
  high_water   = 209.43368256
  _MIN_HW      = 500.0
  _RUIN_FACTOR = 0.65   _CONSECUTIVE = 5
  hw < _MIN_HW ? True  -> should_fire ALWAYS returns False

  equity=  209.43 -> should_fire=False  breaches=0
  equity=  100.00 -> should_fire=False  breaches=0
  equity=   50.00 -> should_fire=False  breaches=0
  equity=    1.00 -> should_fire=False  breaches=0
```
Mechanism (`scripts/run_deadman_switch.py:191-193`):
```python
    state["high_water"] = hw
    if hw < _MIN_HW:                 # _MIN_HW = 500.0  "ignore dust/empty accounts"
        state["breaches"] = 0
        return False                 # <-- unconditional, before any ruin comparison
```
The `_MIN_HW` dust guard is a reasonable idea. It has **no alarm, no log line, and no monitor**, so the rail's transition from ARMED to DISARMED is completely silent.

**How it got here — and why this is a live-capital bug, not a testnet artifact.** The chain runs straight out of F6:
1. `combined_equity()` reads `float(acct["totalMarginBalance"])` (line 125) — the same USDT-only field as F6, blind to the $5,000 USDC in the same wallet.
2. That put the measured equity at $209.43.
3. `NRestarts=12` on the service, plus the `_VERSION`-2 schema discard (`run_deadman_switch.py:271-272`: `if state.get("version") != _VERSION: state = {"version": _VERSION}` — "NEVER inherit foreign/legacy state"), re-anchors the high-water to whatever the book is worth *now*. The module's own `_write_state` docstring anticipates exactly this: *"the HIGH-WATER MARK is lost, so the equity anchor re-sets to whatever the book is worth now and the 35% fire line silently MOVES DOWN… at exactly the worst moment, with no signal that it happened."*
4. It anticipated the line moving DOWN. It did not anticipate the line moving below `_MIN_HW`, which does not lower the rail — **it switches it off entirely.**

A real book that fell from $5,000 to $499 would trip this identically: the ruin rail disarms *precisely* when a book is most at risk of ruin, and the failure is silent by construction. That is the inverse of what a survival rail is for.

**Nothing monitors it.** `max_audit.py:273` maps `"quant-deadman": "scripts/run_deadman_switch.py"` for a **process-liveness** check only. There is no comparison of `high_water` against `_MIN_HW` anywhere in the codebase:
```
$ grep -rn "_MIN_HW\|min_hw" --include=*.py scripts/ libs/ tests/ | grep -v rollback
scripts/run_deadman_switch.py:67:_MIN_HW = 500.0            # ignore dust/empty accounts
scripts/run_deadman_switch.py:191:    if hw < _MIN_HW:
```
Two references, both inside the rail itself. Zero tests, zero monitors, zero alarms.

**The rail is also journal-silent**, so there is no independent trace to catch this by eye:
```
$ journalctl -u quant-deadman.service --since "2026-07-01" | wc -l
1                          # "-- No entries --"
$ systemctl show quant-deadman.service -p NRestarts
NRestarts=12
```
Twelve restarts of a Tier-3 ruin rail, each one silent, each one a chance to re-anchor the high-water — and no journal record of any of them.

---

### F14 (CRITICAL, INTERNAL/false-green) — the dashboard publishes a fire line that does not exist, next to an equity of $0.00, and calls the state `"fired": false`.

`scripts/run_live_combined.py:305-322` writes `web/venue_equity.json`. Live content:
```
$ cat web/venue_equity.json
{ "updated": "2026-07-30T08:26:07Z", "equity": 0.0, "high_water": 209.43,
  "fire_line": 136.13, "breaches": 0, "fired": false,
  "kind": "dead-man measure: ... venue ground truth, immune to mark-based accounting blindness" }
```
Two independent falsehoods in seven fields:
1. **`fire_line: 136.13` is fiction.** It is computed as a literal `0.65 * hw` in the *display* code, not obtained from the rail. Per F13 the rail fires at no equity at all:
```
    equity= 136.12, 4 prior breaches -> should_fire=False
    equity=   1.00, 4 prior breaches -> should_fire=False
```
2. **`equity: 0.0` is a fallback masquerading as a reading.** The display does `dm.get("last_eq", 0.0)`, and `data/deadman_state.json` has no `last_eq` key at all:
```
$ python3 -c "sorted(json.load(open('data/deadman_state.json')).keys())"
['breaches', 'has_positions', 'high_water', 'hw_pending', 'legs_seen', 'usdt_baseline', 'version']
```
Mechanism: `run_deadman_switch.py:290` assigns `state["last_eq"] = eq` **only inside** `if eq is not None and state.get("has_positions"):`. With `has_positions: False` the key is never written, so the panel has shown $0.00 for the entire time the book has been flat. The same guard disables the stale-feed detector while flat — defensible on its own terms (no positions to protect), but it means the rail's *only* two live signals, equity and fire line, are both fictional exactly when the book is idle.

The panel was built after the 2026-07-16 incident precisely because *"the dead-man's independent measure was invisible outside its state file"* (its own comment). The cure for the invisibility is itself blind — and it renders equity ($0.00) *below* its own advertised fire line ($136.13) while reporting `"fired": false`, a self-contradiction sitting on the dashboard that no organ or human has flagged. This is the "self-greening guard" class the doctrine names as prime quarry, in its most consequential location.

---

### F15 (HIGH, INTERNAL/retries-hiding-problems) — the hedge reconciler retried a single symbol **2,334 times** with no circuit breaker, while both order paths were being rejected.

```
$ journalctl -u quant-cashcarry.service | grep -oE "RECONCILE-FAIL [A-Z0-9]+USDT x[0-9]+" | sed 's/.*x//' | sort -n | tail -3
808
2333
2334
$ journalctl -u quant-cashcarry.service -o short-iso | grep "CLOSE-FAIL" | cut -c1-10 | sort | uniq -c
    121 2026-07-24     30 2026-07-25     14 2026-07-26     83 2026-07-27
```
A representative tick:
```
2026-07-27T18:45:53 carries=4 net=$-811.27 funding=$113.04
 ['RECONCILE-FAIL COOKIEUSDT x36 (both market+limit rejected, see data/cashcarry_error.log)',
  'SPOT-EXCESS MOVEUSDT: wallet 600608 vs tracked 47306 (+553302) -- untracked naked long, verify/flatten by hand',
  'SPOT-EXCESS TSTUSDT: wallet 294255 vs tracked 74447 (+219808) -- untracked naked long, verify/flatten by hand',
  'CLOSE-FAIL COOKIEUSDT: spot_ok=False fut_ok=False -- kept tracked, retry next cycle',
  'RISK-PAUSE-OPENS drawdown -17.3%<=-15%: pausing new opens']
```
`_mkt_or_limit` (run_cashcarry_executor.py:382) is a good two-path design — market first, post-only limit on PERCENT_PRICE rejection — but when **both** paths fail there is no escalation: the counter increments and the loop retries forever. 2,334 attempts on one symbol is not a retry policy, it is a spin. The counter is visible in the action feed and rises monotonically, so the information was on screen the whole time; nothing consumed it. `data/cashcarry_positions.json` currently shows `reconcile_fail_counts: {'ONEUSDT': 1}` — the counters do persist, so a threshold check is cheap.

---

### F16 (HIGH, INTERNAL/emergency-procedure gap) — the executor emitted 284 demands for manual human intervention on unhedged naked longs, into a log nobody is paged from.

```
$ journalctl -u quant-cashcarry.service -o short-iso | grep -oE "SPOT-EXCESS [A-Z0-9]+USDT" | sort | uniq -c
     84 SPOT-EXCESS 1000CATUSDT
     72 SPOT-EXCESS MOVEUSDT
     66 SPOT-EXCESS TSTUSDT
     62 SPOT-EXCESS XVGUSDT
```
284 events across four symbols, each reading *"untracked naked long, verify/flatten by hand"* — an autonomous system detecting an unhedged directional position (MOVEUSDT: 600,608 held vs 47,306 tracked, a **12.7x** excess) and asking a human to act, via a journal line. There is no pager hook, no `PRINCIPAL_ACTION` write, no defect. The stranded $4,399.91 the principal is now being asked to adjudicate is the residue of exactly these events. The stranded-recovery tool exists (`scripts/run_deadman_stranded_sweep.py`) and has run in `execute` mode **once ever** (2026-07-20); its two subsequent runs (07-22, 07-29) were `dry_run` on dust-sized rows ($0.01). The detection works; the response path is a human who was never told.

---

### F17 (MEDIUM-HIGH, INTERNAL) — the desk's own viability tool contradicts its own entry gate by 150x, and nobody reconciled them.

`data/carry_viability.json` (produced 2026-07-27) computes, per symbol, the funding required per 8h period to clear the measured round-trip:
```
symbol          rt_bps  need_bps/period  viable
BTCUSDT           0.02            0.010    True
ETHUSDT           0.11            0.040    True
BNBUSDT           0.35            0.120    True
XRPUSDT           1.81            0.600    True
...
XLMUSDT           6.11            2.040    True
n_viable 16 of 30
```
`_MIN_FUNDING = 0.00015` = **1.5 bps/period**. The desk's own arithmetic says BTCUSDT needs **0.010** — the gate is **150x stricter**. Fifteen of the sixteen names this tool certifies as viable require *less* funding than the gate's floor demands. Two artifacts, both current, in direct numerical contradiction, with no organ comparing them. Independent corroboration of F11 from the desk's own tooling.

---

### F18 (HIGH, INTERNAL/delivery-break — same class as F1) — the desk's L1.5 T-bill test runs, produces an honest `FAILS`, and has ZERO consumers.

L1.5 requires that no alpha is valid until it "beats T-bills net of costs". The test exists and is honest:
```
$ cat data/hurdle_rate.json          # fresh: updated 2026-07-30T02:41:48
{ "days": 27.89, "desk_return": -0.123, "annualised": -0.8205,
  "risk_free": 0.00280, "btc_hold": 0.04350, "half_btc": 0.02315,
  "beats": {"risk_free": false, "btc_hold": false, "half_btc": false},
  "funding": 113.04, "legs": 0.0, "implied_costs": 1973.18,
  "verdict": "FAILS -- does not beat risk_free, btc_hold, half_btc" }
```
Nothing reads it:
```
$ grep -rn "hurdle_rate" --include=*.py --include=*.md . | grep -v rollback | grep -v "^./scripts/hurdle_rate.py"
scripts/daily_research_cycle.py:85:    ("hurdle_rate", "scripts/hurdle_rate.py", 90),   # producer only
$ grep -n "hurdle" scripts/max_audit.py
(no output)
```
One producer, zero consumers, no max_audit defect, no principal escalation. The single constitutional test that decides whether the desk's only live sleeve is worth running at all announces `FAILS` into a file nobody opens. Exactly the same delivery-break shape as `freeze_exit_status` (F1) — which is why it is listed separately rather than merged: **two independent instances of the same failure mode means it is a pattern, not an accident.** A one-line max_audit check covers both.

---

### F19 (MEDIUM, NEGATIVE SPACE) — 7 of 17 execution modules are reachable from no entry point, including the safe-retry helper the live path needed and the TCA engine the tape is starved for.

```
$ for m in ...; do grep -rl "execution.$m\b|execution import $m\b" scripts/ | wc -l; done
  engine                 scripts referencing: 0
  errors                 scripts referencing: 0
  journal                scripts referencing: 0
  retry                  scripts referencing: 0
  staging                scripts referencing: 0
  tca                    scripts referencing: 0
  binance_spot_live      scripts referencing: 0
  (used: binance_testnet 10, binance_spot_testnet 7, carry_accounting 2, execution_tape 2,
         maker 2, binance_live 2, algos/broker/ea_bridge/paper_broker 1 each)
```
Two of these are not idle code — they are **capabilities the desk demonstrably needed this month and did not use**:
- **`retry.py`** is a bounded, backoff-aware retry helper whose docstring reads *"Ambiguous timeouts are deliberately not retried blindly here; the engine reconciles instead."* The live reconciler retried one symbol **2,334 times, blindly** (F15). The desk wrote the correct policy, in the right package, and the live path never imported it.
- **`tca.py`** exports `PostTradeTCA` and `SlippageAttribution`. The desk's entire slippage evidence base is **four observations** (F4). The tape has 517 rows waiting and the analysis engine sits unimported.

`binance_spot_live` being unused is correct pre-Gate-0 and is not a defect. `engine`/`journal`/`staging`/`errors` need an explicit wire-or-retire decision on the record (max_audit already fires `orphan-code` for other packages; `libs/execution` is not in its list).

---

### F20 (LOW-MEDIUM, CONTRARIAN — checked, largely negative, reported per the empty-seam rule) — venue-relations pressure was real but has cleared; single-venue concentration remains unmitigated.

The 07-29 audit's F3 recorded three executor crashes on `HTTP 418: I'm a teapot` (Binance's auto-IP-ban) against mainnet `premiumIndex`. Re-tested this audit:
```
$ .venv/bin/python -c "urlopen('https://fapi.binance.com/fapi/v1/premiumIndex')"
OK rows: 854
sample: {'symbol': 'PLTRUSDT', 'markPrice': '122.96000000', ...}
```
The ban has lifted and the endpoint serves normally. The structural exposure is unchanged, though: one IP serves the executor, recorders, collectors and shadow books, and `libs/execution/` contains **no non-Binance venue connector** (`ls libs/execution/` → only `binance_*`), so an IP ban or venue outage is a total execution outage with no failover. `docs/research/BYBIT_SECOND_VENUE_SPEC.md:44` gates the second venue behind "Gate 0 completes on Binance" — which F1/F2 show cannot currently happen, so the dependency is circular. Worth noting rather than acting on: the fix is cheap only *after* F1/F2 are resolved.

Also checked and found clean: **no evidence of information leakage in the order path.** `_mkt_or_limit` cancels stale orders before re-placing (`conn.cancel_all(sym)`), so repeated reconcile ticks do not stack visible resting size; post-only limits rest at the near touch rather than crossing. Client order IDs are venue-generated. No finding.

**Latency: not measured, and not measurable.** `wait_s` exists on exactly 4 tape rows (F4, median 3.70s). There is no timing instrumentation on the venue round-trip, no percentile tracking, and no alert on degradation. Reported as an empty seam, not a clean bill of health.

---
---

# 1. WHAT WE KNOW — validated strengths, each with its proving command

**W1. The absorbing-state detector works end-to-end and IS delivered.** Built 2026-07-29 (`e234078`) after the book died silently. It fires on live state and reached the principal.
```
$ .venv/bin/python -c "import scripts.max_audit as M; d=[]; M.check_book_absorbing_state(d); print(d)"
FIRES: True -> book-absorbing-state: "BOOK DEAD, NOT IDLE: the carry book is flat (n_carries=0)
  while risk_controls still returns FLATTEN -- ruin-floor breach -37.2%<=-35% ..."
$ python3 -c "json.load(open('data/max_audit_report.json'))"   # ran: 2026-07-30T07:38:53
book-absorbing-state LIVE? True
$ grep -in "absorb" data/PRINCIPAL_ACTION.md
15:# 1. THE CARRY BOOK IS IN AN ABSORBING STATE (found 2026-07-29, STEP-0 integrity watch)
```
Notably it recomputes the verdict through the **same pure function** the executor calls rather than re-deriving a threshold — the right design, and the reason it agrees with the book about the book.

**W2. The pair cost model is genuinely good and correctly separates liquid from illiquid.** This is the single most valuable execution artifact the desk owns.
```
$ python3 -c "json.load(open('data/cost_model.json'))['symbols'][s]['pair']['500']"
  BTCUSDT     {"pair_roundtrip_bps": 0.018}      ETHUSDT  {"pair_roundtrip_bps": 0.104}
  XRPUSDT     {"pair_roundtrip_bps": 1.82}       SOLUSDT  {"pair_roundtrip_bps": 2.652}
  COOKIEUSDT  {"pair_roundtrip_bps": 131.38}
  (30 symbols measured)
```
A 7,300x cost spread, measured, per symbol. Everything good in the entry gate rests on this.

**W3. The cost-aware half of the entry gate is correct and is the fix for the churn loss.** Replayed against every open the book actually made:
```
$ .venv/bin/python  # _entry_gate over the 204 taped opens
of the 204 opens the book ACTUALLY made, the CURRENT gate would allow: 2 (1%)
  COOKIEUSDT n=21 med_f=2.40bps rt=131.38 net/24h=-124.18   <- correctly blocked
  GTCUSDT    n=13 med_f=6.74bps rt= 39.50 net/24h= -19.28   <- correctly blocked
```
The 2026-07-27 universe switch (rank by net, not gross funding) is validated by this replay.

**W4. The execution tape solved the truncation problem it was built for.** 517 permanent rows against a `log[-500:]` rolling buffer that was evicting real fills.
```
$ wc -l data/moat/execution_tape/cashcarry_trades.jsonl
517
$ .venv/bin/python -c "execution_tape.coverage()"
{'n': 517, 'days': 26.42, 'first': '2026-07-02T05:18:33Z', 'last': '2026-07-28T15:20:03Z'}
```
Its multiplicity-preserving dedupe is also correct-by-design (repeat top-ups are real events).

**W5. Loss attribution is complete — there is no unexplained loss.** The sleeve was not beaten by the market.
```
$ python3 -c "json.load(open('web/cashcarry_live.json'))"
  leak_attribution = {'basis': -222.53, 'fut_fees': 1750.65, 'residual': 0.0}
  bleed_verdict = 'BLEED: non-funding PnL -1973.18 is 1746% of +113.04 funding harvest'
```
`residual: 0.0` on a $1,973 loss is a strong accounting result: 88.7% commission, 11.3% basis.

**W6. The desk's hurdle test is honest and unflattering.** It reports its own primary sleeve as failing (see F18 for the delivery gap — the *measurement* is the strength).
```
$ cat data/hurdle_rate.json
"verdict": "FAILS -- does not beat risk_free, btc_hold, half_btc"   (annualised -82.05%)
```

**W7. `run_venue_reconcile` is read-only by construction and states its own lower-bound honestly** (`"LOWER BOUND: the trade log is a rolling window (500 rows)…"`), and never credits faucet junk as equity. Its verdict field is broken (F9) but its *body* is trustworthy.

**W8. `_mkt_or_limit`'s two-path design is sound** — market first, post-only limit at the near touch on PERCENT_PRICE rejection, with `cancel_all` first so reconcile ticks cannot stack duplicate resting size. The failure in F15 is the absence of a *bound*, not a flaw in the fallback itself.

---

# 2. WHAT WE DON'T KNOW — the ignorance ledger

**Known unknowns, with the reason each is unknown:**

| # | Unknown | Why we cannot answer it |
|---|---|---|
| U1 | Maker fill-rate at any usable confidence | n=9 real fills carry a mode field; 504/517 tape rows were backfilled without one (F4) |
| U2 | The slippage distribution — mean, tail, regime dependence | n=4 observations, all closes, all from a 2-day window (F4) |
| U3 | Whether BNB fee burn works at all | balance has been 0.00000000 for the entire life of the book; the discount has never once applied (F8) |
| U4 | Whether testnet funding credits match the mainnet rates the signal and `est_funding` assume | signal comes from `libs.data.crypto_source.current_funding` (mainnet fapi); fills and funding credits happen on `binance_testnet`. The fidelity of that pairing has never been tested |
| U5 | Whether the 4 net-positive majors survive *real* execution | their +1.13…+2.16 bps/24h edge is smaller than the one measured spot slippage observation (48.9 bps median, n=4). The margin is inside the error bar |
| U6 | Queue position, adverse selection, market impact | never instrumented, never modelled — no artifact exists |
| U7 | Venue round-trip latency and its distribution | no timing instrumentation anywhere (F20) |
| U8 | How far the 89 duplicate close rows propagate | they corrupt any winrate/held_hours/est_funding aggregate over the tape; which consumers are affected has not been traced (F5) |
| U9 | Whether `_MIN_HW` has silently disarmed the ruin rail before | the service writes nothing to the journal across 12 restarts, so there is no history to inspect (F13) |
| U10 | Real fill behaviour at any size above the tested notional | `sizes_usdt` in the cost model is keyed at "500"; capacity beyond that is extrapolation |

**Suspected unknown-unknowns.** The two most severe findings in this report (F13 disarmed rail, F1 unwired gate) were both *silent, green-reading* states in components everyone believed were working. The desk's monitoring is strong at "is the process alive" and weak at "is the mechanism armed / is the number real". I therefore expect **more inert levers of the same class** — my prior is that any config flag or threshold not covered by an outcome assertion is roughly a coin-flip to be inert. The BNB flag (F8), the fire line (F14), the freeze-exit criteria (F1), and the hurdle verdict (F18) were four independent instances found in one sweep; that hit rate suggests the population is not yet exhausted.

---

# 3. WHAT COULD MATTER MOST — ranked by impact × confidence / (cost × maintenance)

Ranked. **⚡ = compounding multiplier** (raises the value of every future improvement).

| # | Action | Impact | Conf | Cost | Why it ranks here |
|---|---|---|---|---|---|
| **1** | **Re-arm the Tier-3 dead-man rail** — make `account_summary()`/`combined_equity()` sum per-asset `marginBalance` (or enable multi-assets margin), and add a hard assertion that fires if `high_water < _MIN_HW` while the book is live (F13, F6) | ruin protection restored; currently ZERO | high | ~10 lines | The only finding where the downside is unbounded. Fixing the USDC undercount **also re-arms the rail automatically** (verified: 3 polls → `hw=5209.43, armed=True`). One change, two critical fixes. Nothing else on this list matters if the desk can be ruined while every light is green. |
| **2** | **Wire the S0→S1 gate to artifacts that exist** — point `_freeze_exit_met` at the execution tape, fix the inverted mtime test to compare oldest-ROW timestamp, and add a max_audit defect on `freeze_exit_status != all-true` (F1) ⚡ | unblocks the *only* path to deployed capital | high | ~15 lines | L1.2 puts compounded capital first; this is the gate. It is currently unbuildable as written and its failure is announced to no one. Highest ROI per line on the desk. |
| **3** | **Delete `_MIN_FUNDING`** (leave `_structurally_bleeding` + the cost test) (F11, F17) | restarts the book; unfreezes the Gate-0 clock | high | 1 line | The **second, unrecognised lock** on the book. Without it, answering the principal's A/B/C leaves the book flat and the rail fix will look like it failed. Carry value is honestly small (~5.2%/yr vs T-bills ~4–5%); the *evidence* value is the whole point. |
| **4** | **Add the missing outcome assertions as a class**, not one at a time: a max_audit check that every published verdict/threshold has a consumer, covering `freeze_exit_status`, `hurdle_rate.verdict`, `venue_equity.fire_line`, `feeBurn` (F1, F14, F18, F8) ⚡ | closes the dominant failure mode | high | ~40 lines | Four independent instances of "produced, never read" in one sweep. Fixing them individually leaves the generator intact. This is the compounding fix. |
| **5** | **Bound the reconcile retry** — cap `reconcile_fail_counts` at N, then escalate to `PRINCIPAL_ACTION`; import the existing `libs/execution/retry.py` instead of the bare loop (F15, F19) | stops 2,334-attempt spins | high | ~15 lines | The policy is already written and unused. Also removes the mechanism behind a large share of the 8,818 commission events. |
| **6** | **Persist state atomically per close** (`os.replace`, per-symbol, not at `_rebalance` end) (F5, 07-29 F2) | stops tape corruption at source | high | ~10 lines | 89 phantom close rows already in the "immutable" tape. Every day the book runs unfixed adds more, and the tape is the Gate-0 evidence base. The deadman already uses `os.replace` — copy that pattern. |
| **7** | **Wire `tca.py` to the tape** and backfill mode/slip/wait on every future fill (F4, F19) ⚡ | turns n=4 into a real cost model | med-high | ~30 lines | L1.11 names the Execution Reality Model as a moat component; it currently has nine observations. Unblocks U1, U2, U5, U10 simultaneously. |
| **8** | **Route CI file-writes to `tmp_path` at conftest level** for all module path constants (F12) | stops phantom incidents | high | ~5 lines | Carried from 07-29 unfixed. Cheap, and the cry-wolf inversion it creates is genuinely dangerous. |
| **9** | Fix the `NO_GAP` verdict to reflect stranded inventory; source the reconciler from the tape not the 500-row buffer (F9, F10) | tightens the number the Tier-3 decision rests on | high | ~10 lines | Directly improves the evidence quality of a pending principal decision. |
| **10** | Fund BNB or ledger the testnet limitation with a live-side validation plan (F8) | ~25% of the largest cost line | med | minutes | Blocked on a decision, not engineering. Overdue 123.6h. |

**Interactions that matter.** #1 and #3 are **both** required before the book restarts: #1 without #3 leaves the book flat; #3 without #1 restarts trading with the ruin rail disarmed — the worst possible ordering. **Do #1 first, then #3, in that order, in the same change window.** #2 and #7 compose: the gate is worthless if the tape it reads has n=4 execution quality.

**Opportunity cost of not fixing, 1 year.** The desk currently has **$0 deployed** and a deployment gate that cannot be satisfied. If F1+F2+F3+F11 stay unfixed, the 1-year cost is not "some alpha" — it is **100% of expected compounding**, because no capital can be deployed at all under the desk's own rules. Against the sleeve's own honest hurdle verdict (`FAILS`, annualised −82%) that is arguably protective *today*; but it is protective by accident, and it forecloses the correct sequence (fix execution → re-measure → deploy if it clears T-bills). The cost of F13 alone is unbounded and unquantifiable by construction: a disarmed ruin rail has no expected cost until it has a total one.

---

# 4. WHAT WE TEST NEXT — concrete experiments

**T1 — Prove the rail re-arms (do this before anything touches the book).**
Change `account_summary()` to sum per-asset `marginBalance`. Success: `deadman_state.high_water ≥ 500` within 3 polls and a new assertion fires a defect if it is not. Validation: replay `should_fire()` at 0.64×hw and confirm `True` after 5 consecutive breaches. Retirement condition: none — this is a survival rail assertion and stays forever. **Failure mode to watch:** if `multiAssetsMargin` is later enabled at the venue, the two paths must not double-count; assert against `totalWalletBalance` when the flag is True.

**T2 — Falsify F11 the cheap way before deleting anything.** Run the executor in `--dry` with `_MIN_FUNDING = 0` for 48h and record which names it *would* have opened and their realised 24h net. Success criterion: ≥3 of the 4 predicted names (BTC/ETH/XRP/BNB) show realised net > 0 bps over the hold. If realised net is negative, the floor was accidentally protective and the finding is retracted — **this is the pre-registered kill condition, stated before the change.**

**T3 — Measure the thing we cannot currently see.** Instrument every order path with mode, slip_bps, wait_s, and venue round-trip latency; wire `tca.py` over the tape. Success: ≥100 fills with complete execution fields within 30 days of the book restarting, and a maker fill-rate with a confidence interval narrower than ±10pp. This retires U1, U2, U7 and puts U5 in reach.

**T4 — Test the testnet/mainnet funding fidelity assumption (U4).** For each open position, compare `est_funding` (computed from the mainnet rate) against the actual `/fapi/v1/income` FUNDING_FEE rows credited on testnet. Success: median absolute divergence < 10%. If it is large, every funding number in the forward track record is a modelled quantity, not a measured one — which would materially change what the Gate-0 record actually proves.

**T5 — Sweep for the rest of the inert-lever population (the unknown-unknown probe).** Enumerate every boolean flag, threshold constant and published verdict in `libs/execution/`, `libs/risk/` and the executor, and for each one write down the artifact that would prove it is live. Success: an inventory where every entry has either a proving artifact or an open defect row. Given four independent inert levers found in one sweep (F1, F8, F14, F18), the prior that this finds more is high; the value is in the *systematic* pass, not the individual hits.

**T6 — Trace the duplicate-close blast radius (U8).** Recompute every downstream aggregate (winrate, held_hours, est_funding totals, TCA attribution) with and without the 89 phantom rows and publish the delta. Success: a written statement of which reported numbers were wrong and by how much. This is a prerequisite for treating the tape as Gate-0 evidence.

---

## SCORES

| metric | value | basis |
|---|---|---|
| **current_capability_pct** | **28%** | Cost model, tape, attribution and the absorbing-state detector are genuinely good (W1–W8). Against that: the Tier-3 ruin rail cannot fire, the deployment gate is unwired, the book cannot open a position, and the execution-quality evidence base is n=9. The *machinery* is well past 28%; the *working system* is not. |
| **practical_ceiling_estimate** | **80%** | Single-venue, testnet-only, pre-Gate-0. The remaining 20% needs multi-venue failover, a real impact/capacity model, and live-fill calibration — none reachable before Gate 0. |
| **ceiling_gap** | **52 pts** | Unusually large, and almost all of it is *recoverable by ~100 lines of code*, not by new capability. That is the striking fact of this sweep. |
| **opportunity_cost_1y** | **100% of expected compounding, plus unbounded tail** | $0 deployed and a gate that cannot be satisfied (F1/F2). The F13 component is unbounded by construction. |
| **confidence** | **high (0.9)** | Every load-bearing claim was executed, not read: live venue reads, the real pure functions on the real state files, journal counts, and a 2×2 over the live universe. The two judgement calls (F11 magnitude, the testnet caveat on F6) are flagged as such in-line. |
| **unknown_unknown_score** | **HIGH (0.75)** | Four independent inert levers in one sweep, all silent and all green-reading. The monitoring answers "is it alive", rarely "is it armed". I do not believe this population is exhausted (see T5). |
| **info_gain_if_investigated** | **very high** | T3 alone moves the execution model from n=9 to a real distribution and retires three ledger entries at once. |
| **expected_alpha_contribution** | **direct: LOW. indirect: VERY HIGH.** | Honestly: the carry itself is ~5.2%/yr against T-bills at ~4–5% on four names — marginal, and the desk's own hurdle test currently says `FAILS`. The contribution is not the carry; it is that execution is the gate through which *every* future alpha must pass to become capital. |
| **expected_compounding_contribution** | **VERY HIGH** | Items #2, #4 and #7 are compounding multipliers: they make every future execution improvement measurable and every future verdict deliverable. |

**CEILING EXPANSION — what defines the 80%, and what would move it.**
The ceiling is set by an **organisational** assumption, not a technological one: that execution capability is gated behind Gate 0, and Gate 0 is gated behind live fills. F1 shows that dependency is *not real* — it is a placeholder function that was never finished. The true blocker was never evidence; it was ~15 lines. Two further assumptions are worth naming: (a) *single venue* is treated as fixed, but `BYBIT_SECOND_VENUE_SPEC` gates the second venue behind Gate 0 completing on Binance — a **circular dependency** that dissolves the moment F1 is fixed; (b) *testnet fidelity* is assumed rather than measured (U4), and if it is poor the ceiling on what any pre-Gate-0 work can prove is much lower than 80%. The single highest-leverage ceiling-lifting act is fixing F1, because it is simultaneously the gate, the second-venue unblock, and the reason the desk believes it must wait.

---

## HEADLINE

**The Tier-3 dead-man ruin switch cannot fire at any equity — including a 99.5% loss — and nothing on this desk checks whether it is armed.** `high_water` ($209.43) fell below `_MIN_HW` ($500), which returns `False` unconditionally before any ruin comparison. The process is alive, the heartbeat is 21s fresh, and the dashboard publishes a **fire line of $136.13 that does not exist**, beside an equity of `$0.00` that is a `.get()` fallback, labelled `"fired": false`.

The cause chains to a single measurement bug: `account_summary()` reads `totalMarginBalance`, which is USDT-only when `multiAssetsMargin=False`, so **$5,000 of USDC sitting in the same futures wallet is valued at zero**. That one field drove the ruin rail to flatten (the book reads −37.2% when on assets actually owned it is **+62.8%**), froze the Gate-0 evidence clock at 26.42 of the required 28 days, and dropped the dead-man's high-water below its own dust floor. Fixing that one read re-arms the rail in three polls — *verified*.

Underneath it, **the S0→S1 deployment gate is unwired**: three of its five criteria read files no organ has ever written, and the fourth is an inverted staleness test that can only pass when the fill feed is dead. Its verdict is written to a key nothing reads. And a **second, unrecognised lock** holds the book flat — `_MIN_FUNDING` rejects 245/245 candidates, vetoing only the four names that are net-positive under the desk's own cost model, which the desk's own viability tool says need 150x less funding than the gate demands.

The pending Tier-3 decision (A/B/C) should not be executed as written: option (A) re-baselines to a number that is still $5,000 too low, and clearing the rail alone leaves the book flat and the rail disarmed. **Order matters: fix the equity read (re-arms the rail), then delete `_MIN_FUNDING`, then decide A/B/C.**

_Report complete. 20 findings, all command-verified. Auditor: weekly deep cold sweep, execution-growth, 2026-07-30._
