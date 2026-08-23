> **RETIRED, DO NOT FOLLOW.** This arms LIVE CRYPTO trading (Binance futures/spot) on the Hetzner
> VPS, which is fully decommissioned (2026-08-23) and, independent of that, crypto-exchange-native
> trading is banned by the standing MT5 UNIVERSAL MANDATE in `CLAUDE.md` -- "no miner, hunter,
> query... may target crypto-exchange-native opportunities," which covers arming as much as
> hunting. The only live-arming path today is the MT5/Fusion desk's own gateway
> (`desks/mt5/mt5desk/gateway.py`), armed via its own documented process, never this runbook.

# Playbook — go-live (S0 -> S1 arming)

Frozen build spec: `docs/LIVE_CONNECTOR_SPEC.md`. Stage machine: `libs/execution/staging.py`
(`data/stage_state.json`). Connector modules: `libs/execution/binance_live.py` (futures),
`libs/execution/binance_spot_live.py` (spot). This runbook makes go-live a CONFIG FLIP, not a
rushed real-money coding session — the code ships and is tested well before the day it matters.

## What must be true before this runbook is even opened
- Gate 0 exit criteria met (`data/gate0_complete` exists) — see `scripts/run_cadence.py
  _freeze_exit_met()` for the exact checks (fills≥4wk, cost model populated, ≥10 calibration
  rows, no open criticals).
- GATE-0 PRE-MORTEM run: full 13-model panel (`PANEL_MISSION=premortem`) against the verified
  connector + breaker report + this arming plan. Zero unresolved critical findings.
- Property tests + mutation testing (≥90% mutants killed) green on `libs/execution/binance_live.py`,
  `binance_spot_live.py`, `libs/execution/staging.py` — see `tests/execution/test_binance_live.py`,
  `test_staging.py` for the current bar; a second model family has fuzzed the risk-path files and
  filed a breaker report with zero criticals (NOT YET DONE as of 2026-07-18 — do not proceed
  without it).
- Venue-side protective stops (`binance_live.place_stop_market`) wired into the executor's
  position-change path, with the no-naked-position reconcile invariant (>60s without a resting
  stop -> freeze new entries + page) — NOT YET BUILT as of 2026-07-18.
- Pager de-risk ladder (15m/60m/4h) and the 6h canary round-trip — NOT YET BUILT as of 2026-07-18.

## The one HUMAN step (forever-human, never automated)
Principal places trade-only, withdrawal-disabled, IP-whitelisted-to-VPS live keys via SSH:
```
scp -i <key> binance_live_keys.json quant@95.216.191.70:/home/quant/quant-platform/data/secrets/binance_live.json
scp -i <key> binance_live_spot_keys.json quant@95.216.191.70:/home/quant/quant-platform/data/secrets/binance_live_spot.json
```
Format: `{"key": "...", "secret": "..."}`. NEVER paste keys into chat. If the brain needs this
step taken, it writes `data/PRINCIPAL_ACTION.md` (first line = the page text) and clears the
file the moment the SSH copy is confirmed.

## Arming sequence (brain-executed once the human step + all gates above are done)
1. Verify keys landed: `libs/execution/binance_live.is_armed()` should report
   `keys_present=True, live_enable_flag=False, vps_verified=False` (armed is still False — two
   more explicit flags remain, deliberately separate from key placement).
2. VPS-stability precondition: confirm the host has been the durable deployment target (not a
   rebuild-in-progress box) — touch `data/LIVE_VPS_VERIFIED`.
3. Explicit arm switch, only after 1-2 are both true and the pre-mortem + fuzzing bar is clear:
   touch `data/LIVE_ENABLE`. `is_armed()` now reports all-True.
4. Stage transition: `libs.execution.staging.promote(evidence)` with `principal_signoff=True`
   (recorded from the principal's explicit go-ahead), `capital_fraction<=0.10`,
   `symbol_count` in {4,5}, `keys_present=True`, `connector_verified=True`. This flips
   `data/stage_state.json` S0 -> S1 and is logged to `state["history"]`. Cadence floors
   auto-tighten at S1 (canary floor added, generation cadence goes data-triggered-weekly).
5. Size per `data/live_deployment_policy.json` + `libs/risk/kelly_shrink.py` — S1 entry caps
   capital fraction at 0.10 of authorized live capital regardless of what Kelly alone would say.

## Any tripwire -> demote immediately
`libs.execution.staging.demote(reason)` — unlimited, instant, unit-tested, never gated. Demoting
from S1 does NOT delete `data/LIVE_ENABLE`; if the intent is to fully disarm (not just size back
down), also delete the flag file so a later promote() can't silently re-arm on stale state.

## Never do
- Skip a stage (S0 -> S2 directly). The machine physically prevents this (`staging.promote`
  only checks the NEXT stage's gate).
- Put live keys in an environment variable, a systemd unit file, or chat. Keyfile-only, by
  design (see `binance_live.py` module docstring for why).
- Treat "keys placed" as "armed". Three independent flags exist so no single mistake (an early
  key copy, a stale VPS marker) can trade real money.
