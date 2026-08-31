# MT5 Execution EA — `QuantPlatformExecutor.mq5`

A **hardened execution & safety layer only**. Python is the sole brain (alpha, portfolio, risk,
hedging, sizing). The EA never generates signals, never makes alpha decisions, never overrides a
Python decision. It executes what Python sends, reports back, heartbeats, and enforces last-resort
safety floors.

## Architecture
```
Python (brain)                         MT5 Terminal
  EABridge  ──writes──►  <common>/Files/quant_ea/commands/<id>.cmd ──►  EA reads & executes
  EABridge  ◄──reads───  .../responses/<id>.resp                  ◄──  EA writes fill/ack
                          .../state/{account,positions,ea_heartbeat}◄──  EA snapshots
  EABridge  ──writes──►  .../state/py_heartbeat , EMERGENCY_STOP   ──►  EA safety inputs
```
Transport is **atomic `key=value` files** in the MT5 *common files* folder — no DLLs, no sockets,
no MQL networking. Idempotent by command id; fail-closed (ambiguous timeout → reconcile).

## Wire protocol (key=value, one record per file)
**Command** `commands/<id>.cmd` (written by Python): `id, type, symbol, side, volume, order_type,
price, sl, tp, ticket, magic, ts`. `type ∈ {MARKET, PENDING, MODIFY, CLOSE, FLATTEN_ALL, PING}`.
**Response** `responses/<id>.resp` (written by EA): `id, status, ticket, fill_price, fill_volume,
message, ts`. `status ∈ {filled, pending, ack, modified, closed, flat, duplicate, rejected, blocked,
error}`.
**State** (EA → Python): `state/account.state`, `state/positions.state` (`SYMBOL|qty|avg` per line),
`state/ea_heartbeat`. **Safety** (Python → EA): `state/py_heartbeat`, `EMERGENCY_STOP` flag file.

## Safety layer (floors, NOT sizing — Python still sizes everything)
- `EMERGENCY_STOP` flag present → **flatten all** + block new risk.
- Daily loss ≥ `MaxDailyLossPct` of day-start equity → flatten all + block new risk.
- `MaxOpenPositions` cap → block new entries.
- Python heartbeat silent > `PyHeartbeatTimeoutSec` → block **new** risk (no auto-flatten).
- Broker disconnected → defer commands; resume on reconnect.
- Terminal restart → responses persist; positions carry the command id in their comment, so a
  command that already produced a position is acknowledged as `duplicate` (no double execution).
- Every command always gets a response (fail-safe acknowledgement). Every action is appended to
  `state/execution_audit.log`.

## Deployment (fresh Windows machine)
1. Install MetaTrader 5 and log into a **DEMO** account (e.g., FusionMarkets-Demo).
2. Copy `ea/QuantPlatformExecutor.mq5` to `<MT5 data folder>/MQL5/Experts/`
   (MT5 → File → Open Data Folder).
3. Open MetaEditor → open the file → **Compile** (F7). Fix nothing; it is self-contained
   (`#include <Trade/Trade.mqh>` only).
4. In MT5: Tools → Options → Expert Advisors → enable "Allow Algo Trading"; allow file access to the
   common folder. Drag the EA onto any chart; enable **Algo Trading** (the toolbar button).
   Inputs: set `MagicNumber`, `MaxDailyLossPct`, `MaxOpenPositions`, `PyHeartbeatTimeoutSec`.
5. Point Python at the same comm dir: `<MT5 common>/Files/quant_ea` (Open Data Folder is per-
   terminal; the *common* folder is `C:\Users\<you>\AppData\Roaming\MetaQuotes\Terminal\Common\Files`).
6. Run the brain: see `scripts/run_live_demo.py --venue ea --comm-dir "<common>/Files/quant_ea"`.

## Verification
- Python side (this repo): `pytest tests/execution/test_ea_bridge.py` — 8 integration tests pass
  against a faithful in-process EA simulator (`FakeEA`) covering market round-trip, idempotency,
  fail-closed timeout, risk-approval requirement, flatten/emergency, heartbeat, cancel/modify, and
  ExecutionEngine driving the bridge.
- EA side (manual, in the terminal): compile clean; attach to a chart; drop a `PING` command and
  confirm an `ack` response; confirm `state/*` files refresh; confirm `EMERGENCY_STOP` flattens.
  The `.mq5` cannot be compiled or executed from this Python sandbox — that step is performed once
  in MetaEditor on the deployment machine.

## v1.10 hardening (2026-08-31)
- Heartbeat timeout compares GMT to GMT (was `TimeCurrent()` server-time mix).
- `DONE_PARTIAL` fills reported as `filled` (partial), never as `rejected`.
- Restart-safe idempotency via `state/processed_ids.log` journal; order comments are secondary.
- Magic-scoped `FlattenAll` and positions cap (`FlattenAccountWide=false` default).
- `MODIFY` (de-risk) always allowed, even under a kill flag / daily stop.
- Emergency states auto-recover: kill flag → on flag removal; daily stop → next day; heartbeat → when fresh.
- Order validation: volume step/min/max, margin pre-check, stops-level distance, explicit error text.
- `WriteFileAtomic` retries on Windows reader contention; audit log rotates at ~4MB.
- `positions.state` rows are `SYMBOL|qty|avg|magic` with per-symbol digit precision.
- New inputs: `DeviationPoints` (slippage), `FlattenAccountWide`.
