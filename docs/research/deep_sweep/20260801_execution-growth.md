# DEEP COLD AUDIT — execution-growth — 2026-08-01

STATUS: COMPLETE

Auditor: weekly deep cold sweep, subsystem `execution-growth`.
Mode: READ-ONLY. Every claim carries its proving command + output.
Prior reports: `20260730_execution-growth.md`, `20260731_execution-growth.md` (read first; this
report states explicitly where a prior finding MOVED, STALLED, or REGRESSED).

---

## SCORES

_(placeholders — filled at close)_

| metric | value |
|---|---|
| current_capability_pct | TBD |
| practical_ceiling_estimate | TBD |
| ceiling_gap | TBD |
| opportunity_cost_1y | TBD |
| confidence | TBD |
| unknown_unknown_score | TBD |
| info_gain_if_investigated | TBD |
| expected_alpha_contribution | TBD |
| expected_compounding_contribution | TBD |

---

## FINDINGS LOG (raw, verified as discovered; synthesized into the four outputs below)

### E1 (**CRITICAL — THE HEADLINE**, INTERNAL + CONTRARIAN) — the maker path infers "my quote filled" from an *empty open-orders book*, and `_resting_quotes` returns an empty book on **any exception**. A venue read failure during the maker wait therefore reports a **fully-filled pair that does not exist**, sends zero orders, writes zero errors, and leaves two live post-only quotes resting at the venue.

`_maker_pair` is the DEFAULT path for opens (`_MAKER = True`, `run_cashcarry_executor.py:52`), with
`_MAKER_WAIT_OPEN = 240.0` seconds of resting time (line 965). Its fill test is an inference:

```
$ sed -n '1042,1053p;1100,1130p' scripts/run_cashcarry_executor.py
1042 def _resting_quotes(mod, sym):
1050     try:
1051         return [o for o in mod.open_orders(sym) if o.get("type") != "STOP_MARKET"]
1052     except Exception:
1053         return []                       # <-- outage is INDISTINGUISHABLE from "my quote filled"
...
1106             resting = _resting_quotes(mod, sym)
1107             if resting:  ...cancel + taker...
1128             elif modes.get(name) == "maker_pending":
1129                 modes[name] = "maker"
1130                 ok[name] = True         # <-- "left the book with no cancel -> filled"
```

**Repro (READ-ONLY; imports the real module, fakes only the connector objects, writes only to
/tmp).** The venue accepts both post-only quotes, then `open_orders` starts raising — exactly the
`418 IP banned` shape the desk hit on **2026-07-31**, cited by the executor's own kill-loop comment
at line 1443 (*"systemd respawn-hammer a banned endpoint every ~5min (2026-07-31 418 incident)"*):

```
$ .venv/bin/python /tmp/repro_maker.py
--- CONTROL: venue healthy, quote still resting -> should taker-fallback ---
  result: {'spot': 'taker_fallback', 'fut': 'taker_fallback', 'spot_ok': True, 'fut_ok': True}
  market orders sent: [('CANCEL', 12345), ('BTCUSDT','BUY',1.0)] [('CANCEL',12345), ('BTCUSDT','SELL',1.0)]
--- TEST: open_orders raises during the wait (418 ban / timeout) ---
  result: {'spot': 'maker', 'fut': 'maker', 'spot_ok': True, 'fut_ok': True}     <-- CLAIMS FILLED
  quotes actually resting UNFILLED at venue: [('BTCUSDT','BUY',1.0,100.0)] [('BTCUSDT','SELL',1.0,100.1)]
  market orders sent: [] []                                                       <-- nothing executed
  error log written: False                                                        <-- nothing logged
```

The wait loop is hit first and has the same blindness — `if not _resting_quotes(spot,sym) and not
_resting_quotes(fut,sym): break` (line 1102) breaks *immediately* when the venue is unreadable, so a
single outage collapses the whole 240 s protocol into a fabricated fill.

**Consequences, traced.** `_rebalance` then TRACKS a carry (`spot_qty`, `perp_entry`) that does not
exist at the venue → `_mark()` publishes P&L on a phantom position → the two orphaned quotes may
fill later, independently, at unknown times and prices, producing a **real naked leg of unbounded
duration**. This is precisely the class `_filled()`'s own docstring was written to kill (*"a
rejected/partial order looked identical to a successful one to every caller… stranding ~$2,150 of
real inventory"*, 2026-07-19 incident) — reintroduced on the path that is the default for every open.
`_filled()` guards the taker path; the maker path never calls it.

**Why nothing catches it.** `_reconcile` compares tracked vs venue positions, but its futures branch
would *re-short the deficit* (adding a second short beside the still-resting quote), and its spot
branch would *re-buy* — both while the original quotes may still fill. The failure is not merely
undetected, the healer amplifies it.

Fix (small, and the desk already owns both halves): make `_resting_quotes` distinguish *empty* from
*unreadable* (return `None` on exception) and treat unreadable as **unfilled, never filled**; and
verify maker fills against `_filled()`-grade evidence (order status / position delta), never against
book emptiness. Retirement condition: none — this is a permanent invariant.

---

### E2 (**CRITICAL**, ADJACENCY to E1) — when the maker quote **partially** fills, the taker fallback markets the **full** quantity, over-executing by the partial amount. Futures excess is auto-trimmed; **spot excess is never sold** — so the defect deposits a permanent, untracked, unhedged spot long every time it fires.

The fallback cancels the resting order and then markets `qty`, with no `executedQty` accounting:

```
$ sed -n '1113,1128p' scripts/run_cashcarry_executor.py
   canceler(sym, int(o.get("orderId", 0)))     # cancels the REMAINDER
   ...
   res = mod.place_market(sym, side, qty)      # markets the FULL qty, not qty - executedQty
```

**Repro** (post-only quote 70 % filled, remainder rests):
```
$ .venv/bin/python /tmp/repro_partial.py
wanted qty per leg: 1.0
maker quote already executed: 0.7
result: {'spot':'taker_fallback','fut':'taker_fallback','spot_ok':True,'fut_ok':True}
cancels: [999]  market top-ups sent: [('BUY',1.0)] [('SELL',1.0)]
TOTAL SPOT ACQUIRED = 0.7 (maker partial) + 1.0 (market) = 1.7   <-- target was 1.0
```
70 % over-execution, reported as a clean fill. With `_MAKER_WAIT_OPEN = 240 s` on thin alts, partial
fills are the *expected* case, not the tail.

**The asymmetric heal is what makes it permanent.** In `_reconcile`:
```
$ sed -n '557,594p' scripts/run_cashcarry_executor.py
elif have > want * 1.02:                      # FUTURES excess -> auto-trimmed
    how = _do(fut, sym, "BUY", round(have - want, 8))        # "trim-excess"
...
elif want > 0 and held > want * 1.02:         # SPOT excess -> REPORT ONLY
    acts.append(f"SPOT-EXCESS {sym}: ... untracked naked long, verify/flatten by hand")
```
So the futures leg is trimmed back to tracked size while the spot over-fill stays — converting a
symmetric over-execution into a **net naked long**, silently, on every partial-fill open. The code
comment even records the historical outcome (*"which is how it accumulated to multiples of the
tracked size"*) — the 2026-07-26 fix made the accumulation *visible* rather than removing the
mechanism that creates it. Treating the symptom left the generator running.

**And nothing pages on the symptom either** (see E3).

---

### E3 (**HIGH**, OUTCOME-NOT-CONFIG) — every execution-failure signal the executor emits is written to a file with **zero production readers**, and the log is written with `write_text` so it holds exactly one line, forever.

```
$ grep -n "_ERR" scripts/run_alerts.py
46:_ERR = Path("data/cashcarry_error.log")          # <-- declared, and that is the ONLY occurrence
$ grep -rn "SPOT-EXCESS\|OPEN-FAIL\|TOPUP-FAIL\|orphan-CIRCUIT" --include=*.py scripts/ libs/ \
      | grep -v __pycache__ | grep -v run_cashcarry_executor
(no output)
$ grep -rn "CLOSE-FAIL" --include=*.py scripts/ libs/ | grep -v __pycache__ | grep -v run_cashcarry_executor
scripts/max_audit.py:3609:  ... if isinstance(a,str) and a.startswith("CLOSE-FAIL")
```
One of six failure classes (`CLOSE-FAIL`) has a consumer, in a daily audit. `SPOT-EXCESS` — the line
E2 deposits, describing a naked directional long — has **none**. `run_alerts.py` declares `_ERR` and
never reads it: the pager knows the filename and nothing else.

Compounding it, all five writers use `write_text` (truncate), not append:
```
$ grep -n "_ERR.write_text" scripts/run_cashcarry_executor.py
479:  ... reconcile fail x{n} ...
1133: ... unfilled leg (maker path) ...
1250: ... maker fail ...
1265: ... unfilled leg ...
1525: ... cycle error ...
$ wc -l data/cashcarry_error.log
1 data/cashcarry_error.log
```
The incident history of the money path is one line deep. Every prior naked-leg event is
unrecoverable by construction.

**Cry-wolf inversion, still live (3rd sweep in a row).** The single line currently in that file is a
CI artifact — `tests/execution/test_carry_churn_loop.py` calls the real `_execute_pair` with the
module-level `_ERR` unpatched, so every 30-min CI run stamps a phantom naked-leg incident into the
production log:
```
$ cat data/cashcarry_error.log
2026-08-01T00:56:36.819935+00:00 unfilled leg MOVEUSDT spot_ok=True fut_ok=False
  spot_res={'status':'FILLED','executedQty':'47306.0'} fut_res={'status':'REJECTED','executedQty':'0.0'}
```
First reported **2026-07-29** (`20260729_execution-growth.md`), re-reported 07-31 and by the 08-01
infrastructure sweep. Three days, four reports, unfixed. When a real naked leg fires it will be
dismissed as the known fixture — and E1/E2 are the mechanisms that will produce it.

---

### E4 (**CRITICAL**, EXTERNAL/OUTCOME-NOT-CONFIG) — the Gate-0 launch board reads `keys_present: READY` off a **filename glob** that counts two testnet keys, a committed `.example` template, and an **18-character placeholder**. The criterion cannot fail.

```
$ sed -n '46,53p' scripts/check_gate0_ready.py
def _keys_present():
    have = sorted(p.name for p in d.glob("*"))
    live = [k for k in have if "binance" in k.lower() or "api" in k.lower()]
    return _row("keys_present", bool(live), f"{len(live)} live-venue credential file(s) ...")
```
It never opens a file, never checks a key's shape, and never distinguishes live from testnet:
```
$ .venv/bin/python  # enumerate what the criterion counts, structure only, no secret values
files the criterion counts as 'live-venue credential':
    binance_live.json                {'key': 18, 'secret': 18}      <-- real Binance keys are 64
    binance_spot_testnet.json        {'key': 64, 'secret': 64}      <-- TESTNET
    binance_testnet.example.json     {'_comment':169,'key':20,'secret':23}  <-- COMMITTED TEMPLATE
    binance_testnet.json             {'key': 64, 'secret': 64}      <-- TESTNET
-> bool(live)=True => keys_present READY
counterfactual: delete data/secrets/binance_live.json -> remaining=[...] -> STILL READY
```
Zero of the four are live venue credentials, and deleting the live file entirely leaves the
criterion green. `has_keys()` is no better — `return bool(k and s)` (`binance_live.py:63-65`), so the
18-char placeholder authenticates as "keyed":
```
$ .venv/bin/python -c "import libs.execution.binance_live as bl; print(bl.has_keys())"
True
```
This is a **welded gate** (accepts 100 %, carries zero information) on the board whose entire job is
"can this desk reach the venue that will hold real money" — the exact defect class the gate-optimality
duty names, sitting on the launch path.

---

### E5 (**CRITICAL**, INTERNAL/two-evaluators — prior F4 STALLED and now materialized) — the two Gate-0 evaluators now both produce artifacts, and they **disagree on 4 of the 5 shared criteria**. Each is false-green on a different pair. The board a human reads is the loose one.

```
$ .venv/bin/python   # data/gate0_readiness.json vs data/live_guard.json stage_gate.why
criterion                    check_gate0_ready      run_live_guard
principal_signoff            READY                  False       <-- DISAGREE
capital_fraction_le_010      READY                  True
symbol_count_4_5             READY                  False       <-- DISAGREE
keys_present                 READY                  False       <-- DISAGREE
connector_verified           READY                  False       <-- DISAGREE
ruin_rail_clear              BLOCKED-UNKNOWN        (absent)    <-- 6th criterion missing entirely
```
Resolving each:
- **principal_signoff** — the principal DID sign (`data/gate0_signoff.json`, `2026-07-30T22:28:24Z`,
  *"I agree to sign off"*). `run_live_guard.py:239` reads `data/stage_state.json.principal_signoff`,
  a key that file does not contain (`{"stage":"S0","note":"..."}`). **live_guard is wrong.**
- **symbol_count_4_5** — absent from `promo_evidence` entirely (line 234-241), so `s1_entry_met`
  reads its default 0. **live_guard is wrong.**
- **keys_present** — live_guard tests `venue is not None` (did the connector actually arm);
  check_gate0_ready globs filenames (E4). **check_gate0_ready is the false-green.**
- **connector_verified** — live_guard tests `can.last_ok_ts is not None` (a real canary round-trip);
  check_gate0_ready counts 523 **testnet** tape fills. **check_gate0_ready is the false-green.**

So the failure is not "one is right": **check_gate0_ready is falsely green on the two criteria that
test reality, and live_guard is falsely red on the two that test paperwork.** The board a human
reads publishes `"n_ready": 5, "n_criteria": 6, "desk_owes": ["ruin_rail_clear"]` — one criterion
from live — while the outcome-tested view is that the live connector has never successfully placed a
single order and holds an 18-character key.

Second-order: live_guard's only escalation hook (`if gate_met and not _PRINCIPAL.exists(): write
PRINCIPAL_ACTION`) can never fire while two of its inputs are hard-wired False.

---

### E6 (**CRITICAL**, INTERNAL/measured-economics — the number that decides whether this strategy should exist at all) — the desk's only executed strategy has paid **$1,750.87 in futures commission to harvest $113.06 of funding — 15.5× — and no organ computes that ratio, no rail gates on it, and the alarm that sits on top of it is driven by a term in which the fee leak is invisible.**

Both numbers are published, adjacent, in the live feed:
```
$ .venv/bin/python  # web/cashcarry_live.json
funding_harvested      =     113.06
fut_commission (fees)  =   1,750.87
FEES / FUNDING         =      15.49x     <-- computed by nothing, alerted by nothing
net of fees            =  -1,637.81      (the carry's realised economics)
$ grep -rn "fut_commission" --include=*.py scripts/ libs/ | grep -v __pycache__
  (writers only: run_cashcarry_executor 1291/1318/1322/1341/1367, carry_accounting 119/129/139,
   run_deadman_reconciliation; NO consumer computes fees ÷ funding)
```
L1.5 (execution physics) says no alpha is valid until it survives realistic fees. On the realised
tape, this one does not: it is **−$1,637.81 net of its own commission bill**.

**Why the existing alarm cannot see it.** `harvest_eaten_frac` is defined as
`max(0, -non_funding)/funding` where `non_funding = (spot_pnl + fut_pnl) - funding`
(`carry_accounting.py:180-182`). `fut_pnl` is the futures-equity delta, which already nets
commission — so the fee bill is buried inside the same term as everything else, and because
`non_funding` is currently **+3,573.23** (an accounting echo), the metric publishes:
```
harvest_eaten_frac = 0.0
```
Zero, beside a 15.5× fee-to-harvest ratio. The desk *built the attribution that names the leak*
(`leak_attribution.fut_fees: 1750.87`) and then alarmed on a different quantity.

**And the attribution itself does not close.** `residual` is 74 % of the total attributed magnitude:
```
leak_attribution: {'basis': -226.15, 'fut_fees': 1750.87, 'residual': 5550.25}
  residual share of |attribution| = 74%
```
An attribution whose unexplained term is 3× its largest named term satisfies the "attribute every
cycle" duty in form and explains roughly a quarter of the leak in substance.

---

### E7 (**CRITICAL — the launch clock is now open on falsified evidence**) — the S0→S1 freeze-exit criterion `fills_4wk` ("≥4 weeks of **live** fills") flipped **FAIL → PASS yesterday**, and what flipped it was the **kill-switch flatten**. It is now the only S0 criterion the desk itself can satisfy, and it is false three separate ways.

Yesterday's sweep recorded `fills_4wk=False` at "tape frozen at 26.42/28 days". Today:
```
$ .venv/bin/python -c "...run_cadence._freeze_exit_met()"
(False, 'gate0=False, fills_4wk=True, cost_model=True, calib_10=True, no_criticals=True')
```
What moved it:
```
$ .venv/bin/python   # last 8 tape rows + before/after the 07-31 freeze
  2026-07-28T15:20:03  close  TSTUSDT
  2026-07-31T07:13:39  open   BTCUSDT      <- book re-opened 3 carries
  2026-07-31T07:15:45  open   BNBUSDT
  2026-07-31T07:20:42  open   FILUSDT
  2026-07-31T08:36:24  close  BTCUSDT      <- CASHCARRY_KILL freeze flattened them 76 min later
  2026-07-31T08:36:28  close  BNBUSDT
  2026-07-31T08:36:30  close  FILUSDT
  BEFORE the 07-31 flatten: days=26.42  -> fills_4wk FAIL
  AFTER  the 07-31 flatten: days=29.14  -> fills_4wk PASS
```
**Six rows from a 76-minute round trip that an emergency halt terminated are what satisfied the
desk's four-weeks-of-trading-history criterion.**

It is false in three independent ways, any one of which is disqualifying:

1. **The clock measures a stamp for a fill the tape does not hold.** `execution_tape.coverage()`
   pools **both** `closed` and `opened` keys, and `opened` on a *close* row is a back-reference:
```
$ .venv/bin/python -c "from libs.execution.execution_tape import coverage; print(coverage())"
{'n': 523, 'days': 29.14, 'first': '2026-07-02T05:18:33+00:00', 'last': '2026-07-31T08:36:30+00:00'}
$ .venv/bin/python   # each row's OWN event timestamp
earliest OWN event : 2026-07-07T10:50:50+00:00
REAL taped fill coverage = 23.91 d ;  coverage() reports 29.14 d -> OVERSTATEMENT 5.23 d
rows whose `opened` predates 2026-07-07: 15  (all CLOSE rows; own-event ts before 07-07: 0)
GATE-0 BAR = 28 days. reported 29.14 -> PASS ; actual 23.91 -> FAIL
```
2. **Every one of those fills is TESTNET**, on a criterion whose text says *live*:
```
$ grep -n "_BASE" libs/execution/binance_spot_testnet.py libs/execution/binance_testnet.py
binance_spot_testnet.py:21: _BASE = "https://testnet.binance.vision"      # PINNED -- never live
binance_testnet.py:22:      _BASE = "https://testnet.binancefuture.com"  # PINNED -- never live
$ tail -1 data/nav_attestation.jsonl   ->  "mode":"PAPER (testnet) -- pre-Gate-0"
```
3. **The tape is frozen, so the criterion is a one-way latch.** Last row 2026-07-31T08:36; the book
   is under `CASHCARRY_KILL` with `positions: {}`. `days = last − first` on a static file is
   constant, so `fills_4wk` now reads True **forever, without another fill ever landing**. A
   criterion that cannot revert is not a gate.

`check_freeze_exit_sources()` cannot see any of it — it only asserts the writer FILE exists on disk:
```
$ .venv/bin/python -c "...run_cadence.check_freeze_exit_sources()"
[]        # all green
```
That is prior-sweep F10's named limitation with a concrete consequence attached.

---

### E8 (**HIGH**, prior F10 STALLED) — the sole remaining freeze-exit blocker `gate0` reads a file with **zero writers**, so the rewrite that existed to eliminate unsatisfiable criteria left one behind — in the criterion whose own `_FREEZE_SOURCES` entry names its writer.

```
$ grep -rn "gate0_complete" --include=*.py scripts/ libs/ | grep -v __pycache__
scripts/max_audit.py:1266:    if not (ROOT / "data/gate0_complete").exists():      # READS
scripts/run_cadence.py:160:    "gate0": ("data/gate0_complete", "scripts/max_audit.py"),  # claims max_audit WRITES it
scripts/run_cadence.py:214:    checks["gate0"] = Path("data/gate0_complete").exists()    # READS
$ ls -la data/gate0_complete
ls: cannot access 'data/gate0_complete': No such file or directory
```
`max_audit.py` only ever reads the file. `check_freeze_exit_sources()` passes because it asserts the
*writer file* (`scripts/max_audit.py`) exists, not that it writes anything. Net state of the S0
freeze: **four criteria True (one of them falsified per E7), one criterion False and unsatisfiable.**
The gate carries no information in either direction.

---

### E9 (**HIGH**, INTERNAL/measured — the fee lever is ON in state and INERT in outcome) — BNB fee-burn is enabled and the BNB balance is **zero**, so the ~25 % discount has never applied to a single commission.

```
$ grep -n "_enable_fee_burn" scripts/run_cashcarry_executor.py
1423:    _enable_fee_burn()           # called from main() -- correctly WIRED
1540: def _enable_fee_burn() -> None:
$ .venv/bin/python   # /fapi/v2/balance, read-only
non-zero futures balances: [('BTC', 0.01, 0.087), ('USDT', 208.87, 5760.61), ('USDC', 5000.0, 5643.44)]
BNB balance: 0 / ABSENT  -> the ~25% burn discount is INERT
```
The desk already owns the detector (`max_audit.check_bnb_funded`, written 2026-07-24, whose docstring
says *"balance 0 → the whole commission line was paid at rack rate while the desk believed the ~25 %
discount was active"*) — and the condition it detects is still true a week later. Against E6's
$1,750.87 commission bill this is ~$438 of pure, riskless, un-taken cost reduction. It is also the
single cheapest compounding lever on the execution path: one funded balance, no risk surface.

Note the detector's own scope defect: `check_bnb_funded` imports `binance_testnet`, so the check for
a **live** fee lever measures the **testnet** wallet.

---

### E10 (**HIGH**, INTERNAL/measurement — the fee-saving lever is judged on n=11) — maker fill rate is unrecorded on **96.6 % of opens**, and the 53.1 % the desk publishes is computed over a denominator that includes legs on which **no order was ever sent**.

```
$ .venv/bin/python   # census of spot_mode by event over the 523-row tape
 OPENS:  207 total, 7 carry a non-null spot_mode (3.38%)   UNRECORDED = 200
 TOPUPS:  51 total, 4 (7.84%)      CLOSES: 265 total, 8 (3.02%)
 ENTRIES (open+topup): 258 total, 11 instrumented (4.26%)
 spot maker rate on the RECORDED SUBSET: 5/11 = 45.5%
$ .venv/bin/python   # reproduce the published figure
 web/trade_forensics.json -> maker_share: 0.531, n_legs: 32
 DESK-STYLE pooled : 17/38 = 44.7%   (11 of 38 legs are 'already-flat' = NO ORDER SENT)
 CLEAN (orders sent): 17/27 = 63.0%  -> spot 5/15 = 33.3% ; futures 12/12 = 100%
```
Pooling spot with futures produces a headline that describes neither leg: **the futures leg rests
maker essentially always; the spot leg — the one that pays the fee that matters — rests maker a
third of the time.** And `run_trade_forensics.py:244` counts `already-flat` legs, i.e. legs where the
close path found nothing to do, as maker successes.

Worse, the two fill-rate numbers the desk quotes to itself are **unsourced**:
```
$ grep -n "75.8%" scripts/run_cashcarry_executor.py
961: ... "75.8% taker fills paying 96.5% of all commissions"
$ grep -n "24.2%" docs/research/recommendation_ledger.json     # R0219: "maker fill-rate (24.2% paying 96.5% of fees)"
```
Neither is derivable from the tape; both trace to a one-off 2026-07-23 venue commission read that was
never persisted. The desk is steering a fee-reduction programme on a number it cannot reproduce.

---

### E11 (**HIGH**, INTERNAL/measurement — 40 % of the recorded slippage is fabricated) — TCA covers 1.9 % of the tape, and 4 of the 10 instrumented rows are half-spreads computed on legs that **never traded**.

```
$ .venv/bin/python   # rows carrying spot_slip_bps / fut_slip_bps / wait_s / *_fill / *_mid
 10 / 523 rows = 1.91%
 spot_slip_bps: p50=10.392  mean=19.95  max=59.88
 4 of the 10 have spot_mode == 'already-flat' (no order sent). For each:
   COOKIEUSDT  slip=59.880bps  implied full spread=119.8bps -> slip == HALF-SPREAD: True
   1000CATUSDT slip=38.610bps  implied full spread= 77.2bps -> slip == HALF-SPREAD: True
   MOVEUSDT    slip=59.172bps  implied full spread=118.3bps -> slip == HALF-SPREAD: True
   TSTUSDT     slip=13.806bps  implied full spread= 27.6bps -> slip == HALF-SPREAD: True
```
When the leg is already flat, `avg_fill()` returns `None` and the mark falls back to the ticker
(`run_cashcarry_executor.py:778`), so `_tca` differences a ticker print against a book mid and calls
the result slippage. Those four are the **four largest values in the distribution** and they drag the
mean from 7.0 to 19.95 bps. Real fills only:
```
 n=6 rows (1.15% of tape), $376.04 of notional
 notional-weighted PAIR slippage: +5.738 bps
 maker spot legs (n=2): mean -0.043 bps   |   taker/fallback spot legs (n=4): mean +7.029 bps
```
The desk's realised slippage is measured on **$376 of notional**. `_tca` must refuse to emit a number
when the leg mode is `already-flat` — an unmeasurable is not a zero and it is not a half-spread.

---

### E12 (**HIGH**, INTERNAL/data-integrity on the money path) — the execution tape records **successes only**, and it records a third of its closes **more than once**. Any consumer summing `notional` overstates by 31 %.

```
$ .venv/bin/python
 event types: close 265 (50.7%) | open 207 (39.6%) | topup 51 (9.8%)  -- TOTAL 523
 rows containing fail/partial/reject/unfilled/cancel/error: 0 each
 spot_ok / fut_ok fields present in the tape: 0 / 523
 close rows 265, distinct (symbol,opened) 176, keys closed >1x: 50
 redundant close rows: 89 = 33.6% of close rows
 notional double-counted by repeats: $41,240.17 of $131,519.41 = 31.4%
 worst: XVGUSDT / DEXEUSDT / KITEUSDT / TSTUSDT / BNBUSDT each closed 4x off ONE `opened`
```
`OPEN-FAIL`, `CLOSE-FAIL`, `TOPUP-FAIL`, thin-book skips and `limit_only_unfilled` all `continue`
*before* `_log_trade` (lines 787, 843, 903), so the denominator of every fill-rate statistic the desk
can ever compute is unknowable by construction. The duplicates are the close-retry-loop fingerprint
(2026-07-28 incident) written permanently into the record and left **unmarked** — indistinguishable
from real activity to every downstream reader, including the Gate-0 clock in E7 which counts `n=523`.

---

### E13 (**MEDIUM-HIGH**, INTERNAL/measurement) — the naked-leg window, the single quantity that prices E1 and E2, has **no per-leg timestamps anywhere** and is unmeasurable.

```
$ .venv/bin/python   # time fields in the tape
 timestamp-ish fields: ['_taped','closed','opened','wait_s']   -- one `opened`/`closed` per PAIR
 per-leg fields (spot_mode/spot_fill/spot_mid/spot_slip_bps, fut_*): TIME fields = NONE
 wait_s present on 10/523 rows; observed: FILUSDT 247.02s (spot taker_fallback / fut maker)
                                          BNBUSDT 125.02s, BTCUSDT 14.38s
```
`_maker_pair` quotes the legs in a sequential loop and takes the fallbacks in a **second** sequential
loop, so a pair where one leg rests and the other needs a taker fallback is delta-exposed for an
unbounded fraction of a 240 s window. `wait_s` bounds the worst observed open at ≤247 s but never
locates the exposure inside it. Fix is one line per leg: stamp the fill time inside `_maker_pair`.

---

### E14 (**MEDIUM-HIGH**, INTERNAL/churn economics) — median hold is **12.2 h against an 8 h funding cycle**, and 70.5 % of carries close inside a day; the fee bill is the direct consequence.

```
$ .venv/bin/python   # 176 deduped round trips over a 23.9-day span
 held_hours: p10=1.38  p25=4.05  MEDIAN=12.20  p75=29.41  p90=42.19  max=194.13
   <1h: 11/176 = 6.2%  |  <4h: 44/176 = 25.0%  |  <1d: 124/176 = 70.5%  |  >=7d: 1
 7.36 realised round trips/day
 176 deduped round trips, notional $90,279.24
   sum price_pnl -$224.66 (-24.89 bps) | sum est_funding +$55.71 (+6.17 bps) | net -$169.04 (-18.72 bps)
```
A quarter of the book closes inside a single funding period — earning at most one settlement while
paying two full cost legs. `_MIN_HOLD_H = 24.0` and `hold_top = 3000` were the churn fixes; the
realised median is still half the minimum hold, which means the hold floor is not binding on the path
that actually closes positions (the close path reads `pos`, not funding — line 618).

Note the funding number is an **estimate**, not a settlement: `est_funding = rate × notional × h/8`,
never reconciled against venue funding income. So E6's 15.5× fee-to-harvest ratio and this −18.72 bps
per round trip are computed on the two most reliable numbers available and both say the same thing.

---

### E15 (**CRITICAL — the guard is inert in the process that holds the book**; prior F7 fixed on disk, REGRESSED in production) — `run_live_guard` orders a **total stand-down** (`effective_size_fraction: 0.0`, `canary.mode: limit_only`); the running executor reads **full size, takers allowed**, because the deployed code looks for a JSON key the guard file does not write.

The fix for prior-F7 is real and works at HEAD. The process holding the book does not have it:
```
$ ps -o pid,lstart,etime,cmd -p 1626623
1626623 Fri Jul 31 16:44:27 2026  08:38:49  .../python scripts/run_cashcarry_executor.py --live ...
$ git log --format="%h %cI %s" -2 -- scripts/run_cashcarry_executor.py
97967d6  2026-07-31T17:53:32Z  L1.44 consumption-time freshness ...      <- 69 min AFTER the process started
963df91  2026-07-31T13:52:27Z  cycle 2026-07-31 pm: freeze-incident fixes ...  <- the code in the process
$ git show 963df91:scripts/run_cashcarry_executor.py | grep -A 8 "def _refresh_guard"
1044:  g = json.loads((Path("data/live_guard.json")).read_text("utf-8"))
1045:  at = datetime.fromisoformat(str(g.get("generated", "1970-01-01T00:00:00+00:00")))
1046:  if (datetime.now(tz=UTC) - at).total_seconds() > 900:
1047:      return                                          # stale guard is no guard
```
`data/live_guard.json` writes `ts`, never `generated`:
```
$ .venv/bin/python -c "import json;print(list(json.load(open('data/live_guard.json')))[:3])"
['ts', 'stage', 'armed']          # has 'generated'? False
```
Replayed against the live file:
```
$ .venv/bin/python /tmp/replay_guard.py
guard file says      : effective_size_fraction = 0.0 | canary.mode = limit_only
deployed code parses : g.get('generated', ...) -> 1970-01-01T00:00:00+00:00   (key ABSENT)
                       age_s = 1,785,547,429  > 900 -> stale -> RETURN EARLY
RUNNING PROCESS effective guard : {'size_frac': 1.0, 'limit_only': False}   <-- full size, takers allowed
GUARD ACTUALLY ORDERS           : {'size_frac': 0.0, 'limit_only': True}    <-- total stand-down
--- HEAD, for contrast ---
HEAD _refresh_guard -> {'size_frac': 0.0, 'limit_only': True}
```
Today this is masked by `CASHCARRY_KILL`. **The masking ends at REARM**: clearing the kill file resumes
trading in a process that ignores a guard demanding zero size and limit-only execution — and the
canary reason for `limit_only` is *"no successful canary on record — unproven execution path"*, i.e.
precisely the state in which taker-chasing is most expensive. Two independent brakes (E15 removes the
size governor; E1/E2 are the fill defects) release together on the first post-REARM tick.

Fail direction is documented as OPEN (*"stale guard is no guard"*) — defensible when the guard is
genuinely dead, indefensible here, because the guard is **alive and writing every 5 minutes**
(`data/live_guard.json` mtime 01:20) and only the *key name* disagrees. The degradation is not
"stale", it is a schema mismatch masquerading as staleness. `read_fresh` at HEAD falls back to mtime
when no `generated` stamp exists (`libs/ops/fresh.py:99-100`), which is why HEAD is correct.

**Fix: restart `quant-cashcarry` — and do it BEFORE clearing the kill file, not after.**

---

### E16 (**HIGH** — the one check designed to catch E15 is measurement-broken) — `check_stale_daemons` uses the `/proc/<pid>` **directory mtime** as its process-start proxy, and that mtime advances with process activity, so it reads *newer* than any code change and reports zero defects forever.

```
$ .venv/bin/python   # true start from /proc/<pid>/stat field 22 + /proc/stat btime
TRUE process start   : 2026-07-31T16:44:27.130000+00:00
/proc dir mtime      : 2026-08-01T00:52:32.688390+00:00   <- the proxy the check uses (8h forward)
executor source mtime: 2026-07-31T17:59:42.839027+00:00
SOURCE IS NEWER THAN PROCESS: True
```
Against the true start, four import-closure files are newer than the running executor — including the
executor itself. Against the proxy, none are. The check therefore returns clean **precisely in the
case it exists to detect**, and E15 is the case. This is prior-F12 built and inert: the capability was
added, the measurement was never validated against a known-positive, and it has been reporting
"no drift" through an actual drift for ~9 hours.

---

### E17 (**HIGH**, GREENFIELD/CONTRARIAN — simulation-production parity) — the executor's futures connector **lacks `place_stop_market` and `cancel_order` entirely**, so three safety paths take the *other* branch in all 523 taped fills and all flip to a never-once-executed branch on the first live tick.

```
$ .venv/bin/python -c "...executor's fut module + capability probe"
executor futures connector : libs.execution.binance_testnet
  has place_stop_market    : False
  has cancel_order         : False
  -> _reconcile_protective_stops returns [] every tick : True
  state has 'protective_stops' key : False        # never planned, never placed
$ for f in binance_live binance_testnet; do grep -oP "^def \K\w+" libs/execution/$f.py; done
live   : ... place_market place_post_only place_stop_market open_orders cancel_all cancel_order flatten_all
testnet: ... place_market place_post_only              open_orders cancel_all              flatten_all
```
Three behaviours change **simultaneously** the instant the live connector is swapped in, none of them
ever exercised against a venue:
1. `_reconcile_protective_stops` goes from a guaranteed no-op to placing real venue-side
   STOP_MARKET orders — the rail that is supposed to survive host death, first-run on live capital.
2. `_maker_pair`'s cancel path goes from `cancel_all(sym)` to per-id `cancel_order`.
3. `_resting_quotes`' STOP_MARKET filter goes from filtering nothing to filtering real stops — and
   that filter is the load-bearing assumption of **E1**.

The code comment justifying `cancel_all` on the fallback path reads *"testnet spot, where no stops
rest"* — true, but **only because stops cannot be placed there at all**. The safety argument is
circular: the risky cancel is safe today because the protective rail is dead today. Both facts change
together at Gate 0. This is the `simulation_prod_parity` row of `TIER1_BENCHMARK.md` (graded T2,
HRT/Jump exemplar) failing at the most basic level — the sim venue and the prod venue do not expose
the same order types, and nothing measures the difference.

---

### E18 (**MEDIUM-HIGH**, prior F1 PARTIAL — writer shipped, reader untouched) — the executor now persists `last_combined_equity`, and **both** readers still point at a file that does not exist.

```
$ .venv/bin/python -c "import json;d=json.load(open('data/cashcarry_positions.json'));print(d['last_combined_equity'], d['last_combined_equity_at'])"
8685.52 2026-08-01T01:10:01.367247+00:00              # writer half: SHIPPED
$ grep -n "_STATE = " scripts/record_capital_event.py; ls data/cashcarry_state.json
scripts/record_capital_event.py:40:_STATE = _ROOT / "data/cashcarry_state.json"
ls: cannot access 'data/cashcarry_state.json': No such file or directory
$ grep -n "cashcarry_state" scripts/check_gate0_ready.py
156:  return _row("ruin_rail_clear", None, "state unreadable on this box", DESK, "data/cashcarry_state.json", ...)
```
Live consequence on the launch board, right now:
```
$ cat data/gate0_readiness.json | grep -A 3 ruin_rail_clear
"criterion": "ruin_rail_clear", "status": "BLOCKED-UNKNOWN",
"detail": "state unreadable on this box", "artifact": "data/cashcarry_state.json"
```
The one criterion the board says the **desk** owes is blocked by a path typo, while the number it
needs sits in a different file being refreshed every 60 seconds. The `$0.00` default did become an
explicit refusal (a real improvement — an unmeasurable no longer reads as zero), so the *dangerous*
half is closed; the *inert* half is not. Two files, three sweeps, one `sed`.

---

### E19 (**MEDIUM-HIGH**, CONVERSION/L1.28b) — the execution backlog is not being converted, and one closure is **false**.

From the ledger (`docs/research/recommendation_ledger.json`, 223 rows):
- **R0071 `implemented`** with `commit: "pending-this-commit"` never back-filled, while its own summary
  names two legs that did not ship: *"record_capital_event + check_gate0_ready read
  cashcarry_positions.json"* (E18 — both still read the phantom path) and *"copy the 3-line equity fix
  to binance_live.py:188"* (E20 — unchanged). The `reason` field claims *"all four repo legs closed"*.
  A false `implemented` is worse than an open row: it removes the item from the queue permanently.
- **R0074** (the class fix: a read-implies-writer census) — **open, undisposed, 21.6 h**. No census
  artifact exists. E7/E8/E18 are all instances of exactly the class it would have caught.
- **R0089** ("dispose the 8-item carried execution table") — **open, undisposed**; 7 of 8 still stalled.
- **87 undisposed rows** desk-wide; no ledger row exists for prior F2, F4, F6, F10 or F11 individually.

Per §33/L1.28b: 7 of this subsystem's 16 prior findings are STALLED with no ledger row at all, so
they owe a disposition that no organ is tracking. Detection is running at ~16 findings/sweep against
a repair rate near zero on this subsystem.

---

### E20 (**HIGH**, prior F2 STALLED — unfixed on the file that will carry money) — `binance_live.py:188` still reads USDT-only `totalMarginBalance`, and the account demonstrably holds non-USDT collateral.

```
$ grep -n "totalMarginBalance\|marginBalance" libs/execution/binance_live.py libs/execution/binance_testnet.py
binance_live.py:188:   "equity": float(a.get("totalMarginBalance", 0.0)),        <- UNFIXED
binance_testnet.py:181-183: eq = max(sum(marginBalance across assets), totalMarginBalance)   <- fixed
$ .venv/bin/python   # /fapi/v2/balance, read-only
non-zero futures balances: [('BTC', 0.01, 0.087), ('USDT', 208.87, 5760.61), ('USDC', 5000.0, 5643.44)]
```
The account holds **$5,000 USDC and 0.01 BTC** beside $208 USDT. Under `multiAssetsMargin=False`,
`totalMarginBalance` is USDT-only — the exact read that valued a solvent book at near-zero, flattened
it, and silently disarmed the dead-man rail on 2026-07-30. The fix was applied to the testnet
connector and the dead-man switch; the live connector, modified the same day, kept the old read. It
is the equity input to the executor's ruin rail once connectors are swapped, and it compounds with
E18 in the opposite direction on the same rail.

---

### E21 (empty seams — checked, found empty, reported per the exhaustion mandate)

- **Order amend / WS order entry / user-data stream** — `grep -rn "listenKey\|userDataStream\|wss://\|amend" libs/execution/ scripts/run_cashcarry_executor.py` → **zero matches**. The whole execution path is REST-polling on a 600 s beat with ±15 % jitter. Correctly ranked behind the wiring defects above; named so it is on the register.
- **Canary** — `data/canary_state.json`: `{"last_attempt_ts": null, "last_ok_ts": null, "history": []}`. **Never probed once.** `live_guard` reports *"due, but connector not armed — skipped"*.
- **`data/ramp_state.json`** — no writer anywhere (`grep -rn "ramp_state" scripts/ libs/` → one hit, a *read* at `run_live_guard.py:51`), so every ramp criterion reads False by absence, not by evidence.
- **`web/tca.json`** — absent; only an existence check at `research_cycle.py:125`. TCA has no writer.
- **`web/venue_reconcile.json`** — 56 h stale; `stranded_uncredited_value 4399.91` against
  `unexplained_residual -4399.91` and `explained_share: null`.
- **Venue field on the tape** — `0/523` rows carry a `venue` field, so testnet and (future) mainnet
  fills will be indistinguishable in the permanent record. This is a five-character fix that must
  land **before** the first live fill or the track record is permanently ambiguous.
- **Third 418 episode** — `journalctl -u quant-cashcarry` logs `2026-07-31 08:58:04 HTTP Error 418:
  I'm a teapot` on `/fapi/v1/premiumIndex`. E1's trigger condition is not hypothetical; it has
  occurred at least three times, most recently 41 hours ago.

---

## RATCHET TABLE — the 2026-07-31 sweep's 16 findings, re-verified by outcome

| prior | verdict | evidence |
|---|---|---|
| R-CHECK deadman | **FIXED** | replay vs live state: `high_water 6257.59`, `disarmed_live False`, fires at 64 % HW |
| R-CHECK freeze-exit | **PARTIAL → WORSE** | 4/5 now True but `fills_4wk` is falsified (E7); `gate0` unsatisfiable (E8) |
| F1 capital trigger phantom file/key | **PARTIAL** | writer shipped; both readers still on `cashcarry_state.json` (E18) |
| F2 `binance_live` USDT-only equity | **STALLED** | `binance_live.py:188` unchanged (E20) |
| F3 `_MIN_FUNDING` floor | **FIXED** | constant DELETED per R0057; `_entry_gate` is cost-test-only |
| F4 two Gate-0 evaluators | **STALLED → materialized** | 4 of 5 shared criteria now disagree in artifacts (E5) |
| F5 crontab ≠ manifest | **FIXED** | `check_scheduler_manifest.py` → `scheduler-manifest: OK` |
| F6 two false greens on the board | **STALLED** | `keys_present` welded (E4); `connector_verified` on testnet fills |
| F7 guard computes, nothing consumes | **FIXED on disk, REGRESSED in production** | E15 |
| F8 `place_stop_market` zero callers | **PARTIAL → inert** | caller exists; connector lacks the method (E17) |
| F9 S1 rail driver never executed | **FIXED (one gap)** | live_guard/canary/derisk artifacts fresh; `ramp_state.json` still has no writer |
| F10 `gate0_complete` phantom writer | **STALLED, now more severe** | it is the sole remaining freeze blocker (E8) |
| F11 capital fraction ÷ paper equity | **STALLED** | denominator grew $13,155 → $18,676, still the molded curve |
| F12 process-vs-disk drift | **PARTIAL — check built, measurement broken** | E16 |
| F13 (8-item carried table) | **7 STALLED / 1 PARTIAL** | E3, E9, E12, E19 |
| F14 drill coverage | **STALLED** | still 3 drills; none would catch E1, E15 or E18 |
| F15 REST-only | **STALLED** | zero WS/amend matches (E21) |
| F16 empty seams | **STALLED** | canary never probed; no venue field; no TCA writer (E21) |

**Ratchet verdict: 4 FIXED, 4 PARTIAL, 10 STALLED, 1 REGRESSED-IN-PRODUCTION.** The fixes are real
and the regression is the important one: the desk's build capability is outrunning its deploy and
conversion capability, which is exactly the L1.28b diagnosis applied to this subsystem.

---

### E22 (**THE LARGEST FINDING IN THIS SWEEP** — CONTRARIAN/EXTERNAL/L2.10 reality gap) — the strategy the desk is about to fund **loses money in every hold bucket on its own realised tape**, the desk's own forensics organ says so in writing, and **not one Gate-0 or freeze-exit criterion reads any of it.** The launch gate is orthogonal to whether the strategy is profitable.

The claim the desk validated on:
```
$ cat web/cashcarry_backtest.json
  ann_sharpe 3.77   max_dd -0.037   gates 10/10   pbo 0.044   reality_p 0.0   survived True
  verdict: "UPGRADE: higher Sharpe / lower variance than perp-only carry ..."
```
What the desk actually realised, from its own forensics organ (`web/trade_forensics.json`, written
2026-07-31T08:35, one minute before the freeze):
```
$ .venv/bin/python   # hold_buckets_net_of_fees
     <2h  n=  5  notional=$  2,035.21  fee=$    2.96  net=$    -7.11     -34.92 bps
    2-8h  n= 16  notional=$  6,366.64  fee=$    5.91  net=$   -46.09     -72.39 bps
   8-24h  n= 28  notional=$ 16,690.31  fee=$   22.21  net=$   -99.63     -59.70 bps
    >24h  n= 37  notional=$ 26,544.40  fee=$1,572.18  net=$-1,684.58    -634.63 bps
  baseline_funding_class: n=52  net=$-80.90  -> -42.14 bps
  fee_bps_of_logged_notional = 314.62 bps   (futures commission ONLY -- spot fees invisible -> LOWER BOUND)
```
**Every hold class is negative. Every one.** And the organ's own flags say it plainly:
```
  * hold-class 2-8h bleeding: -63.11 bps over 16 trades
  * hold-class 8-24h bleeding: -46.39 bps over 28 trades
  * hold-class >24h bleeding: -42.34 bps over 37 trades
  * FEE INTENSITY hold-class >24h: $1572.18 on $26544 = 592 bps, 59x the ~10 bps a futures
    round-trip should bill -- the venue is charging for fills this book did not intend
  * ENTRY-GATE REGRESSION: 2 open(s) at baseline funding 0.0001 AFTER the gate shipped
  * maker fill-rate 53.1% below the 60% target -- fees are the dominant carry cost, so this
    is the primary unit-economics lever
```
A Sharpe-3.77 / max-DD-3.7 % / 10-of-10-gates backtest against a realised book bleeding 42–635 bps
per hold class is the widest reality gap this desk has on record, and **L1.4 is explicit that reality
outranks simulation.**

**Now the gate-optimality half, which is the part that makes this structural rather than a bad
month.** The six Gate-0 criteria are `principal_signoff`, `capital_fraction_le_010`,
`symbol_count_4_5`, `keys_present`, `connector_verified`, `ruin_rail_clear`
(`check_gate0_ready.py:160-161`). The five freeze-exit criteria are `gate0`, `fills_4wk`,
`cost_model`, `calib_10`, `no_criticals` (`run_cadence.py:213-233`). **Not one of the eleven reads
profitability, slippage, fee intensity, or `trade_forensics.flags`.** The nearest thing is
`cost_model`, and it is a file-existence test:
```
$ sed -n '224p' scripts/run_cadence.py
    checks["cost_model"] = Path("data/cost_model.json").exists()
```
So the desk can pass every launch gate it owns while its own execution-forensics organ is screaming
that the strategy does not survive its own fee bill — which is L1.5 (execution physics: *no alpha is
valid until it survives realistic slippage, fees and impact AND beats T-bills net of costs*)
unenforced at the exact boundary L1.5 exists to guard.

**This reframes the whole subsystem.** E1/E2/E15 are severe, but they are defects in *how* the desk
executes. E22 says the thing being executed does not currently clear its own costs, and the machinery
built to decide that question does not ask it. Fixing the wiring and launching would deploy capital
into a measured negative expectancy faster and more reliably.

**The honest counter-argument, stated because L1.25 requires it:** these are testnet fills, the
>24h bucket's $1,572 fee is dominated by the close-retry loop (a *defect*, not the strategy), and
`_MIN_HOLD_H`/`hold_top` shipped after most of this tape. All true — which is precisely why the
correct action is **not** "kill the carry" and **not** "launch anyway", but a Gate-0 criterion that
requires a post-fix window of fills clearing costs. The diagnosis L1.25 demands runs *while* the
hunt continues; it does not replace it.

---

## 1. WHAT WE KNOW — validated strengths, each with its proving command

1. **The Tier-3 dead-man rail is armed, correct, and fires.** Replayed against the live state:
   `high_water 6257.59`, `_MIN_HW 500.0`, `disarmed_live False`; fires at 64 % of high-water after 5
   consecutive breach polls, and at $1.00 equity. Its `fut_eq` is `max(sum(per-asset marginBalance),
   totalMarginBalance)` (`run_deadman_switch.py:131-133`) — the multi-asset fix E20 still lacks on the
   live connector. **This is the one rail I would trust today.**
2. **The entry gate is now economically correct.** `_MIN_FUNDING` is DELETED (not lowered) per R0057;
   `_entry_gate` is `funding × periods > _rt_bps(sym)` with a per-symbol measured round-trip and a
   pessimistic default (`_DEFAULT_RT_BPS = 39.5`). `_structurally_bleeding` denies proven money-losers
   and its stale-degrade direction is correct (*a stale denylist still denies*).
3. **The scheduler is single-sourced and matches its manifest.** `check_scheduler_manifest.py` →
   `scheduler-manifest: OK`; `run_live_guard` at `*/5`, `check_gate0_ready` hourly, drills daily.
   Prior F5 genuinely closed.
4. **The S1 rail driver now runs and produces artifacts.** `live_guard.json` / `canary_state.json` /
   `derisk_state.json` all refreshed at 01:20. Prior F9 largely closed (`ramp_state.json` still
   writer-less).
5. **The close path is market-only and reduce-only.** `_CLOSE_IS_MARKET_ONLY = spot_side == "SELL"`
   and `_reduce_only_leg` (lines 1240, 1255) — the fix for the COOKIEUSDT/1000CATUSDT
   bought-a-short-through-zero incidents. Correct, and correctly reasoned in the code
   (*"a close is a CERTAINTY problem, not a fee problem"*).
6. **Unmeasurables are increasingly refused rather than zeroed.** `funding=None` produces an explicit
   `UNMEASURED` verdict instead of an `inf%` bleed (`carry_accounting.py:171-178`);
   `check_gate0_ready` emits `BLOCKED-UNKNOWN` rather than READY; `record_capital_event --show` now
   refuses instead of printing `$0.00`. This is the single healthiest pattern in the subsystem — and
   E1, E11 and E17 are the three places it has **not** been applied.
7. **The desk's own forensics organ correctly diagnosed E22 before this sweep did.**
   `web/trade_forensics.json` flags every bleeding hold class, the 59× fee intensity, the entry-gate
   regression and the maker-fill shortfall. **The detection is excellent; the conversion is zero** —
   nothing consumes those flags, which is the L1.28b defect in one artifact.

## 2. WHAT WE DON'T KNOW — the ignorance ledger

**Known unknowns (named, with why they are unmeasurable today):**
- **Realised slippage.** 6 real-fill rows, $376 of notional (E11). Everything the desk believes about
  its own market impact rests on that.
- **Maker fill rate.** 11 instrumented entries of 258 (E10). The two figures quoted in the executor's
  own comments and in R0219 have no reproducible source.
- **Fees per fill.** No fee field on the tape (E12). Only a 14-day futures-only rolling snapshot, a
  declared lower bound.
- **Funding actually settled.** `est_funding = rate × notional × h/8`, never reconciled to venue
  income. Both of E6's terms are therefore one estimate and one venue truth.
- **Naked/half-legged exposure time.** No per-leg timestamps (E13). This is the quantity that prices
  E1 and E2, and it does not exist.
- **The denominator of every fill statistic.** Failures never reach the tape (E12), so all rates are
  computed over successes only.
- **Whether protective stops work at all.** Zero end-to-end evidence; the connector lacks the method
  (E17). First stop placement will be on live capital.
- **Whether the live connector can authenticate.** 18-char credentials, `is_armed()` False, canary
  never probed once (E4, E21).
- **`web/venue_reconcile.json`**: `stranded_uncredited_value 4399.91` vs `unexplained_residual
  -4399.91`, `explained_share: null`, 56 h stale. $4,400 the desk cannot account for either way.

**Suspected unknown-unknowns (where my confidence is lowest, therefore where I would probe next):**
- **Everything transfers from testnet.** 100 % of fills are `testnet.binance.vision` /
  `testnet.binancefuture.com`. Testnet has no real counterparties: queue position, maker-rest
  probability, adverse selection and partial-fill distribution are all synthetic. E2 (partial-fill
  over-execution) is *rare on testnet and probably common on mainnet* — the defect's frequency is
  drawn from the wrong distribution.
- **The `_safe()` swallow surface.** Every venue call is wrapped; I verified the fill-verification
  paths, not the full set. Given that two of this sweep's findings (E1, E17) are "an exception or an
  absent method silently changes behaviour", I would expect more of this class.
- **Concentration in the venue's thinnest listings.** The book's top names by round trip are COOKIE,
  GTC, XVG, MOVE, TST, 1000CAT — HHI 0.053, top-5 43.9 % of notional. Whether the funding edge and the
  cost model behave the same in liquid names is untested, because the book has barely traded any.

## 3. WHAT COULD MATTER MOST — ranked by impact × confidence / (cost × maintenance)

| # | opportunity | impact | conf | cost | why it ranks here |
|---|---|---|---|---|---|
| **1** | **Restart `quant-cashcarry` BEFORE clearing the kill file** (E15) | CRITICAL | 1.00 | ~0 | The guard orders `size_frac 0.0 / limit_only`; the live process reads `1.0 / takers`. One restart. Doing REARM first releases the size governor and the E1/E2 fill defects on the same tick. |
| **2** | **Add a profitability criterion to Gate 0** (E22) | CRITICAL | 0.95 | low | Eleven launch criteria, none of which asks whether the strategy clears its costs, while the desk's own forensics flags every hold class bleeding. This is L1.5 unenforced at the boundary L1.5 exists for. Compounding multiplier: it makes every future strategy's launch honest, not just this one. |
| **3** | **`_resting_quotes` must distinguish empty from unreadable** (E1) | CRITICAL | 1.00 | ~1 h | Return `None` on exception; treat unreadable as UNFILLED. Verify maker fills against `_filled()`-grade evidence, not book emptiness. Repro'd; trigger observed 3× (most recently 41 h ago). |
| **4** | **Partial-fill accounting in the taker fallback** (E2) | CRITICAL | 1.00 | ~2 h | Market `qty − executedQty`, not `qty`. Without it every partial fill deposits a permanent untracked naked long, because spot excess is report-only. |
| **5** | **Fix the two Gate-0 evaluators into one** (E4, E5) | CRITICAL | 1.00 | ~2 h | 4 of 5 criteria disagree; each evaluator is false-green on a different pair; the board a human reads is the loose one. `keys_present` must open the file and check the key, not glob filenames. |
| **6** | **`coverage()` must count own-event stamps only** (E7) | CRITICAL | 1.00 | ~15 min | The launch clock reads 29.14 d on 23.91 d of rows, was flipped to PASS by the emergency flatten, is 100 % testnet, and is a one-way latch on a frozen file. |
| **7** | **Page on `SPOT-EXCESS` / `OPEN-FAIL` / naked-leg lines; append, don't truncate** (E3) | HIGH | 1.00 | ~1 h | Five failure classes, one consumer. `_ERR` is declared in the pager and never read; the log is one line deep forever. Fix the CI fixture leak in the same commit or the pager cries wolf on day one. |
| **8** | **Fund a BNB balance** (E9) | HIGH | 0.90 | ~$50 | ~25 % off the commission line, riskless, detector already built and firing for 7 days. Against a $1,750 fee bill this is the cheapest lever on the board. |
| **9** | **Stamp `venue` and per-leg fill times on every tape row** (E13, E21) | HIGH | 1.00 | ~2 h | **Must land before the first live fill** or the track record can never distinguish testnet from mainnet, and the naked window stays permanently unmeasurable. Compounding multiplier: every future execution statistic depends on it. |
| **10** | **`_tca` must refuse to emit on `already-flat` legs** (E11) | HIGH | 1.00 | ~30 min | 40 % of recorded slippage is a half-spread on legs that never traded; they are the 4 largest values and they treble the mean. |
| **11** | **Copy the 3-line equity fix to `binance_live.py:188`** (E20) | HIGH | 1.00 | ~10 min | Already proven in `binance_testnet.py:181-183`. The account holds $5,000 USDC; this is the read that flattened a solvent book once already. |
| **12** | **Point both readers at `cashcarry_positions.json`** (E18) | HIGH | 1.00 | ~5 min | One `sed`. Unblocks the only criterion the board says the desk owes. |
| **13** | **Fix `check_stale_daemons` to use true process start** (E16) | HIGH | 1.00 | ~30 min | The check that exists to catch #1 is measurement-broken and has reported clean through a live 9-hour drift. Compounding: it guards every money-path deploy from here on. |
| **14** | **Mark duplicate closes in the tape; record failures** (E12) | HIGH | 1.00 | ~2 h | 33.6 % of close rows are repeats, 31.4 % of notional double-counted, unmarked. Every consumer that sums notional is wrong, including the Gate-0 row count. |
| **15** | **Connector parity suite** (E17) | HIGH | 0.85 | ~1 d | Three safety paths flip to never-executed branches simultaneously at Gate 0. Assert both connectors expose the same surface; fail CI on divergence. Maps to `simulation_prod_parity` (T2, HRT/Jump). |
| **16** | **A read-implies-writer census** (R0074, open 21.6 h) | HIGH | 0.90 | ~4 h | E7, E8 and E18 are all instances. The class fix was raised, never disposed, and would have caught three of this sweep's findings for free. |
| 17 | Per-leg WS user-data stream + order amend (E21) | MEDIUM | 0.7 | ~1 w | Correctly ranked *behind* everything above: it makes a broken protocol faster. Revisit once #1–#15 land. |

**Interactions that matter:** #1 and #3/#4 must land together — restarting into HEAD activates a
correct guard but also the maker path whose fill inference is broken. #2 supersedes the urgency of
#1–#15 in one sense: if E22's verdict holds after the churn fixes, the correct action is not to
launch at all, and the wiring work becomes preparation rather than a launch blocker.

**Opportunity cost of not fixing, 1 year:** the direct execution defects (E1, E2, E15) are bounded by
the book — at the configured $200 launch capital, small; at the $4,500 the running process was
launched with, a single E1 event can strand the whole allocation in an untracked position. The
*unbounded* cost is E22 + E10/E11: launching into a measured negative expectancy and being unable to
tell, for another year, whether it was the strategy or the execution — because the instruments that
would answer it cover 1.15 % of the tape. **That is the compounding loss: not the money, the year of
un-attributable evidence.**

## 4. WHAT WE TEST NEXT — concrete experiments with success criteria

1. **Positive control on the maker protocol.** Inject a connector whose `open_orders` raises, and one
   whose quote partially fills, into the executor's test suite. *Success:* both produce
   `spot_ok=False` and an error-log line. *Retirement:* never — these become permanent regression
   pins. (Fails today: E1 and E2 repros.)
2. **Restart-and-verify the guard.** Restart `quant-cashcarry`; assert `_GUARD == {'size_frac': 0.0,
   'limit_only': True}` in the running process's own log line. *Success:* the executor prints the
   `live_guard: sizing scaled to 0%` note. *This must precede REARM.*
3. **Gate-0 profitability criterion.** Add `costs_cleared`: over the most recent N ≥ 30 round trips
   *after* the churn fixes, net-of-fee bps > 0 and fee intensity < 3× the theoretical round trip.
   *Success:* the criterion reads NOT-READY today (it must — that is the point) and becomes readable
   from `trade_forensics.hold_buckets_net_of_fees` without new plumbing. *Retirement:* when a live
   cost model with ≥ 90 % TCA coverage supersedes it.
4. **Welded-gate audit of all eleven launch criteria.** For each, construct the counterfactual that
   should flip it and check that it does. *Success:* every criterion has at least one input state that
   makes it fail. `keys_present` fails this today (E4); `fills_4wk` fails it too (E7 — it cannot
   revert). *This is the gate-optimality duty applied to the launch board.*
5. **Connector parity test.** Assert `set(dir(binance_live)) ⊇ set(dir(binance_testnet))` for the
   order-placement surface, and that every `hasattr`-guarded branch in the executor has a test
   exercising **both** sides. *Success:* CI fails on the current tree (it should — E17).
6. **Instrument-then-measure, in that order.** Land the `venue` field, per-leg fill timestamps, per-fill
   fees and mode-on-every-row; then re-run the E6/E10/E11/E14 measurements after 100 fills. *Success:*
   TCA coverage > 90 %, maker rate computable on spot alone, fees ÷ funding computable from the tape
   without a venue call. *Retirement condition for E22's verdict:* only this dataset can overturn it.
7. **Replay the 2026-07-31 418 ban against the full rebalance loop**, not just `_maker_pair`, and
   record every state divergence. *Success:* no phantom tracked position, no un-cancelled quote.

---

## SCORES

| metric | value | basis |
|---|---|---|
| current_capability_pct | **31 %** | rails and gates exist and several are genuinely good (dead-man, entry gate, scheduler); the paths that carry orders have two repro'd correctness defects, the size governor is inert in production, and 96–99 % of the fill statistics are unmeasured |
| practical_ceiling_estimate | **85 %** | at this capacity band, with REST-only execution and one venue, ~85 % is reachable: full TCA, measured maker rate, per-leg timestamps, a parity suite, a profitability gate. The last 15 % needs WS order entry, a second venue, and a live cost model |
| ceiling_gap | **54 pts** | dominated by measurement (E10–E14), not by architecture |
| opportunity_cost_1y | **HIGH — one year of un-attributable live evidence** | direct loss bounded by book size; the real cost is being unable to tell strategy failure from execution failure for a year, because the instruments cover 1.15 % of the tape |
| confidence | **0.90** | every finding carries a command; E1, E2 and E15 are replayed against the real module and the live state files; the two I relied on a subagent for (tape economics, ratchet) I re-verified independently, and one of its claims (tape dedupe) was **wrong** and is corrected here |
| unknown_unknown_score | **0.75 (HIGH)** | 100 % testnet fills means the *distribution* every statistic is drawn from is synthetic; `_safe()` wraps every venue call and I audited a subset; two of six findings this sweep were "an absent method or a swallowed exception silently changes behaviour" |
| info_gain_if_investigated | **VERY HIGH** | instrumenting the tape (item 6) converts nine "unmeasurable" ledger entries into numbers, at ~2 days of work |
| expected_alpha_contribution | **NEGATIVE TODAY, HIGH IF FIXED** | E22: the realised tape says the executed strategy does not clear its own fees. The execution fixes are what would let it — or would prove it cannot |
| expected_compounding_contribution | **VERY HIGH** | items 2, 9, 13, 15, 16 are all multipliers: a profitability gate, a `venue` field, a working staleness check, a parity suite and a read-implies-writer census each raise the value of every future execution change |

**CEILING EXPANSION — is the 85 % artificially low?** It is bounded *methodologically*, not
technologically: the constraint is that the desk measures execution on a venue with no real
counterparties. A mainnet sub-account funded with $100 and traded at minimum size would produce a
*different kind* of evidence than 523 testnet fills — real queue position, real adverse selection,
real partial-fill distribution. That single change would move the ceiling more than any code in this
report, and it is blocked only by E4 (no valid live credentials). **The binding constraint on
execution capability is not engineering; it is that the desk has never once traded for real.**

---

## APPENDIX — perspective coverage

| perspective | status | where |
|---|---|---|
| 1 INTERNAL (measured, not configured) | ✅ 22 findings | E1–E22; every claim command-cited; ratchet table re-verifies all 16 priors by outcome |
| 2 EXTERNAL (tier-1 cohort) | ✅ | E17 → `simulation_prod_parity` (T2, HRT/Jump) fails at connector-surface level; E22 → no tier-1 firm's process launches capital while its own TCA flags every hold class bleeding; E3 → Jane Street/Optiver-class desks page on every unfilled leg, this one pages on none; E9 → DRW/Wintermute `inventory_treasury` (T3): the fee-asset policy is the exemplar and the BNB balance is zero. **Negative-exemplar control:** the rail that would have stopped Alameda/Archegos is position-vs-collateral truth — E20 shows the live connector cannot see $5,000 of it, and E15 shows the size governor is inert in the running process. Two of our three relevant rails would not have fired. |
| 3 FUTURE (2–3 y compute/AI/data) | ✅ | The whole measurement layer (E10–E14) is a solved problem the moment fills are streamed rather than polled: a user-data WebSocket gives per-leg fill times, fees and partials for free, and makes E1's inference problem disappear entirely (fills are *pushed*, never inferred from an empty book). Ranked #17 today only because it optimises a protocol that is currently incorrect. |
| 4 CONTRARIAN | ✅ | **E22 is the contrarian finding and it inverts the subsystem's premise:** the question is not "how do we execute this better" but "does this clear its costs at all". Also E9's inversion — the desk believed a 25 % discount was active for a week while paying rack rate — and E17's circular safety argument (the risky cancel path is safe only because the protective rail is dead). |
| 5 GREENFIELD | ✅ | Rebuilt today: one connector interface with an enforced parity contract (E17); fills recorded as *events* with venue, leg, time, fee and mode — never inferred (E1, E12, E13); one Gate-0 evaluator, not two (E5); every gate carrying a counterfactual test proving it can fail (E4, E7). The current design's baggage is that the tape was retrofitted from a rolling buffer (504 of 523 rows are one backfill) and the gates were written against files chosen before the writers existed. |
| 6 FRONTIER | ✅ | Nothing newly public is the binding constraint here, and saying so is the finding: the gap is instrumentation the desk can build this week, not a capability that recently became available. The one genuinely new-ish lever is venue-native `POST /fapi/v1/order` amend semantics (avoids cancel-replace races that E2 exploits) — ranked #17, correctly behind the wiring. |
| NEGATIVE SPACE | ✅ | E21: no WS/user-data/amend anywhere; canary **never probed once**; `ramp_state.json` has no writer; `web/tca.json` has no writer; `venue` field on 0/523 rows; `venue_reconcile.json` 56 h stale with $4,400 unexplained both ways; no drill covers the kill-honoured path, the deadman replay, or `record_capital_event --show ≠ $0`; **no gate anywhere asks whether the strategy makes money.** |

---

## HEADLINE

**Three things, in order.**

1. **`quant-cashcarry` must be restarted before the kill file is cleared.** The guard is ordering a
   total stand-down (`effective_size_fraction: 0.0`, `limit_only`) and the process holding the book
   reads full size with takers allowed, because the deployed code looks for a `generated` key the
   guard writes as `ts`. The check built to catch exactly this reports clean because it measures
   process age from a `/proc` mtime that advances. (E15, E16)

2. **The default order path can report a filled pair that does not exist.** `_maker_pair` infers
   fills from an empty open-orders book, and the book reads empty on any exception — a condition
   observed three times, most recently 41 hours ago. When the quote instead fills partially, the
   fallback markets the full quantity and the resulting spot excess is never sold. Both repro'd
   against the real module. (E1, E2)

3. **And the strategy those orders serve does not currently clear its own fees.** Every hold bucket
   is negative net of fees (−34.92 / −72.39 / −59.70 / −634.63 bps); fees run 314.62 bps of logged
   notional against a backtest claiming Sharpe 3.77; the desk's own forensics organ says so in
   writing — and **none of the eleven Gate-0 and freeze-exit criteria reads any of it.** The launch
   gate is orthogonal to profitability. Meanwhile the criterion that *did* flip to PASS yesterday
   (`fills_4wk`) was flipped by the kill-switch flatten, measures 5.23 days of fills the tape does
   not contain, counts 100 % testnet fills as "live", and can never revert. (E22, E7)

The fixes in #1 and #2 are hours of work. **#3 is the one that decides whether any of it should be
deployed**, and the honest next step is a Gate-0 criterion that fails today.

STATUS: COMPLETE

---

## APPENDIX — perspective coverage

| perspective | status |
|---|---|
| 1 INTERNAL | pending |
| 2 EXTERNAL (tier-1 cohort) | pending |
| 3 FUTURE | pending |
| 4 CONTRARIAN | pending |
| 5 GREENFIELD | pending |
| 6 FRONTIER | pending |
| NEGATIVE SPACE | pending |
