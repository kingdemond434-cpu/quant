# Playbook — cash-and-carry (the deployed book)

**What it is:** long spot (testnet.binance.vision) + short perp (testnet.binancefuture.com),
dollar-matched, top-10 positive-funding names, funding harvested every 8h. Delta-neutral: the legs
cancel; funding − fees is the edge. Deployed ~$4.5k target, 600s loop.

## Key files
- Executor: `scripts/run_cashcarry_executor.py` (launched by `scripts/watchdog.py` — args live THERE)
- State: `data/cashcarry_positions.json` (tracked legs + banked realized spot P&L)
- Heartbeat: `data/cashcarry_exec_heartbeat` (stale >240s → watchdog respawns)
- Kill switch: create `data/CASHCARRY_KILL` to stop it deliberately
- Feeds: `web/cashcarry_live.json`, `web/live_combined.json`

## Restart procedure (avoid unless necessary — restarts caused real friction losses)
1. Stop: kill the `pythonw` processes matching `run_cashcarry_executor` (kill by tree; the venv
   stub spawns a paired system-Python child — one logical process shows as two PIDs).
2. `del data\cashcarry_exec_heartbeat`
3. `.venv\Scripts\python.exe scripts\watchdog.py` → respawns with current args.
4. Verify: heartbeat fresh, `web/cashcarry_live.json` updating, hedge clean (no orphans).

## Known failure modes (all have guards — check these FIRST when P&L looks wrong)
- **Hedge drift / orphan shorts** on thin books → reconcile guard: market-first, post-only limit
  fallback (PERCENT_PRICE −4131), excess-short trim. Worst historic case: EDUUSDT.
- **Rate-tie churn**: never hysteresis on a rank cut through funding ties (159 closes/wk lottery);
  hold while funding > 0 (`--hold-top 3000`).
- **Accounting asymmetry**: spot realized must be BANKED at close or the book shows phantom loss.
- **Income truncation**: venue serves ≤1000 income rows — pagination required (done).
- **Venue 5xx mid-hedge** → one leg filled: reconcile self-heals next tick; don't panic-trade.

## Never do
- Edit the strategy spec mid-forward-clock (resets validation evidence).
- React to PnL without `web/root_cause.json` (expected variance → do NOTHING).
- Manual restarts for convenience — each one has historically cost real friction.

Risk rails: ruin flatten 35% · DD pause 15% · concentration 35% · ruin-cap leverage ≤5.7x (floored
until validated). Validation: fast-track day 40 (t≥1.65) → live at ½-Kelly per
`data/live_deployment_policy.json`.
