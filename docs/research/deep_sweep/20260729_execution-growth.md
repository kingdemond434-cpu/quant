# DEEP COLD AUDIT — EXECUTION-GROWTH — 2026-07-29

_Auditor: weekly deep cold sweep (execution-growth subsystem). READ-ONLY. Every claim carries its proving command. Prior auditor run died (BRAIN_AUTH_FAILED stub overwritten); this is the retry._

**STATUS: IN PROGRESS — skeleton first per completion contract; findings appended incrementally.**

## SCORES (placeholders, refined at end)

- current_capability_pct: TBD
- practical_ceiling_estimate: TBD
- ceiling_gap: TBD
- opportunity_cost_1y: TBD
- confidence: TBD
- unknown_unknown_score: TBD
- info_gain_if_investigated: TBD
- expected_alpha_contribution: TBD
- expected_compounding_contribution: TBD
- CEILING EXPANSION: TBD

## HEADLINE (filled at end)

- Context at audit open: `data/CASHCARRY_KILL` reads "DEADMAN ruin rail fired 2026-07-29T11:00:43Z" — fired DURING this audit's opening minutes. `data/DEADMAN_FIRED` latched since 2026-07-27T21:06:52Z (incident #6, true fire, 94.1% of loss was self-billed commission from a close-retry/reconciler loop). Book flat, sleeve halted, principal reset pending.

---

## 1. WHAT WE KNOW — validated strengths, each with proving command

(appended incrementally)

### FINDINGS LOG (raw, verified as discovered — synthesized into the four outputs at the end)

**F1 (CRITICAL, INTERNAL/observability) — CI tests write phantom incident fingerprints into the production error log.**
`tests/execution/test_carry_churn_loop.py:136` calls the real `_MOD._execute_pair("MOVEUSDT", 47306.0, "SELL", "BUY")` with faked venues; the fakes return spot FILLED / fut REJECTED, and `_execute_pair_impl` (run_cashcarry_executor.py:1086) writes `data/cashcarry_error.log` via the module-level relative `_ERR` path, which the test does NOT monkeypatch. CI runs with cwd=repo root (`crontab -l`: growth audit `*/30` → `[ci_gate]` pytest), so every CI run stamps `unfilled leg MOVEUSDT spot_ok=True fut_ok=False spot_res={'status': 'FILLED', 'executedQty': '47306.0'} ...` into the production log with a fresh timestamp.
Proof: observed the file content change during this audit from `2026-07-29T08:04:52` to `2026-07-29T11:05:43` (identical payload, `stat` mtime 11:05:43.735154); both timestamps fall inside `[ci_gate]` windows (journalctl: `[ci_gate] {'ok': False, 'rc': 'timeout'...}` at 08:06:04, growth-audit cron `*/30`); grep of tests shows the exact qty 47306 at test_carry_churn_loop.py:98,136,146,155,165. No venue order occurred (fakes fully substituted; positions state `{}` unchanged; no trade logged, tape unchanged at 517 rows).
Consequence: any organ or human reading `cashcarry_error.log` (max_audit's close-retry-loop check reads this fingerprint class; incident triage starts here) sees a "naked spot leg TODAY" that never happened. This audit burned its first hour disproving one. A phantom naked-leg line is also exactly what a REAL naked-leg line looks like — when a real one fires, it will be dismissed as the known test artifact (cry-wolf inversion). Same hazard class latent for `_KILL`, `_HB`, `_STATE`, `_TRADES` module constants in any test that reaches them unpatched.

**F2 (HIGH, INTERNAL/correctness) — closes are double-logged after a crash: state persist happens only at rebalance end.**
The close path logs the trade + `del pos[sym]` per symbol (run_cashcarry_executor.py:749-758), but `_STATE.write_text` runs only once at the END of `_rebalance` (:861-863). A crash between close-execution and state-write (observed class: `RuntimeError: GET failed after 4 ... HTTP Error 418` inside the SAME `_rebalance` at `_ranked()`; also any exception later in the topup/risk path) loses the deletions → next process re-reads the stale state and closes the same positions AGAIN.
Proof: execution tape holds BOTH `{"event":"close","symbol":"1000CATUSDT","qty":1138985.0,...,"closed":"2026-07-27T21:24:01"}` AND `...,"closed":"2026-07-28T15:19:54"}` for the SAME open `2026-07-26T12:44:04` (tail of data/moat/execution_tape/cashcarry_trades.jsonl); COOKIE/MOVE/TST closes at 07-28 15:19-15:20 all carry `spot_mode/fut_mode = "already-flat"` (they had genuinely closed earlier). journalctl shows the new PID 1055199 printing `KILL: closing all carries` at Jul 28 15:19:37 — a restart re-closing an already-closed book.
Consequence: winrate, held_hours, est_funding, price_pnl are double-counted per duplicated close in BOTH the rolling log and the "immutable" tape — the same tape Gate 0's ">=4 weeks of live fills" evidence and the cost model are built from. Also latent: `_STATE.write_text` is truncate-then-write (non-atomic); a crash mid-write leaves corrupt JSON, and `_rebalance`:610 `json.loads` would then raise on every subsequent tick → permanent crash loop (systemd restarts into the same corrupt read) until a human repairs the file.

**F3 (CRITICAL, INTERNAL/robustness+venue-relations) — the KILL/idle branch is unprotected and polls 10x harder than trading mode; it crash-looped the executor and coincided with a mainnet IP ban (HTTP 418).**
The KILL branch calls `rb = _rebalance(0, 0, 0.0, dry=dry)` (run_cashcarry_executor.py:1302) with NO try/except (the normal branch at :1309 has one), and the branch loops on `time.sleep(_HB_TICK)`=60s — so while HALTED the executor runs a full `_rebalance` (mainnet `premiumIndex` fetch via `current_funding()`, exchange_filters, prices, books on both venues) every 60s versus every 600s while trading.
Proof: journalctl -u quant-cashcarry.service 02:30-02:45 today shows three consecutive crashes with `RuntimeError: GET failed after 4: https://fapi.binance.com/fapi/v1/premiumIndex :: HTTP Error 418: I'm a teapot` at 02:30:52, 02:35:48, 02:42:21 (PIDs 1125806→1126141→1127144→1127475), each dying at `main` line 1302 → `_ranked` line 587. HTTP 418 is Binance's auto-IP-ban response to repeated 429 violations; `_get`'s 4 blind retries amplify the pressure. The desk shares ONE IP across executor, recorders, collectors, and shadow books — a ban starves all of them at once.
Consequence: while the ruin rail is latched (exactly when stability matters most) the executor is at its LEAST stable: crash → systemd respawn → 3-min standby handover (single-book invariant) → crash again. Each respawned process also re-runs `_enable_fee_burn` and startup venue reads, adding weight to a banned IP.

## 2. WHAT WE DON'T KNOW — ignorance ledger

(appended incrementally)

## 3. WHAT COULD MATTER MOST — ranked opportunities

(appended incrementally)

## 4. WHAT WE TEST NEXT — concrete experiments

(appended incrementally)
