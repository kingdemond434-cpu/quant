# DEEP COLD AUDIT — LAUNCH-READINESS (the money path AS WIRED)

STATUS: COMPLETE
Auditor: weekly deep cold sweep, subsystem = launch-readiness
Date: 2026-08-01
Method: outcome-not-config. Every claim carries its proving command + output. READ-ONLY audit.
Predecessor: `docs/research/deep_sweep/20260731_launch-readiness.md` (F1–F27, R1–R10). This sweep's
first duty is REGRESSION: which of yesterday's 27 findings actually moved (artifact evidence, not
claims), and its second is NEW ground — the launch-day-once failures nobody has looked at yet.

## THE ONE-SENTENCE VERDICT

**The documented launch procedure, executed perfectly tomorrow, places zero live orders, arms
nothing that can trade real money, and reports success at every step** — and if the one missing wire
were added without the other twelve fixes, the first live tick would deploy 4× the authorised
capital through an invalid key, with the ruin rail watching a different account.

## SCORES

- **current_capability_pct: 31%** (down from yesterday's 38%, and the drop is *information*, not
  decay — nothing regressed; the sweep found the launch is a no-op (L4/L9), the arming key is a stub
  (L1), and sizing 4×es itself at S1 (L19). Three defects that were invisible yesterday and each of
  which alone falsifies "ready".) What genuinely works: the halt/pager/refusal core, secret hygiene,
  the REST-only design, fail-closed sentinels, the guard→executor sizing bridge (the one thing that
  moved since yesterday).
- **practical_ceiling_estimate: 95%.** Unchanged and still right: every defect found is ordinary
  engineering — a factory, a filename, a validity check, three copied lines, a reset script. No
  external blocker exists beyond the deposit and real keys, both principal acts.
- **ceiling_gap: 64 points.** Larger than yesterday's 57 because the measurement got honest, not
  because the desk got worse. Still 3–5 focused days of work.
- **opportunity_cost_1y:** the largest on the desk and asymmetric in both directions.
  *Launching as-wired* costs the entire first-year live compounding stream **while believing it is
  being earned** — the L4 failure is silent, so the desk would paper-trade for days or weeks with
  real money idle, and every board would stay green (this is strictly worse than a loud failure).
  *Not launching* costs the same stream plus Gate-0's forward evidence, already frozen once.
  L1.13 dominant bottleneck, unchanged.
- **confidence: 0.9.** Every load-bearing claim was verified by running a command or reading the
  file this session; two sub-sweeps converged independently on L1/L4/L19 from different starting
  points; I downgraded one sub-sweep claim (the "naked short right now") after checking venue truth.
- **unknown_unknown_score: 0.3** (down from 0.35). The *wiring* unknowns are now close to
  enumerated — three independent passes converged rather than diverging, which is the signal that a
  space is nearing exhaustion. The residual is irreducibly behavioural: real slippage, partial
  fills, maintenance windows, key-permission surprises, and Binance error codes the desk has never
  seen.
- **info_gain_if_investigated: high, and now specifically directed.** The highest-information
  experiment available is no longer "launch" — it is the **cutover dress rehearsal on a copy of
  `data/`**, which would have caught L1, L4, L5, L6, L19 and L22 in one run, without money.
- **expected_alpha_contribution: decisive but wholly indirect.** Launch is the transmission
  mechanism for every validated edge. A silent paper-launch taxes all of them at 100%.
- **expected_compounding_contribution: the highest on the desk.** L1.20: research exists to improve
  deployed capital, and deployment is the binding constraint on compounding starting at all.
- **ceiling_expansion:** the 95% ceiling is defined by an **organisational** assumption — "launch =
  flip this stack as designed, by hand, once". That assumption is what produces every defect in this
  report: a one-shot hand procedure has no test surface, so nothing can fail before the day.
  Replacing it with *a rehearsable cutover* (clone state → run the script → assert the boards flip)
  moves the ceiling to ~99% and, more importantly, converts launch-readiness from a belief into a
  measurement that can be re-run nightly.

## 0. YESTERDAY'S FINDINGS — WHAT ACTUALLY MOVED

Outcome, not claims. Of yesterday's six CRITICALs: **zero fixed.**

| Yesterday | Status today | Proof |
|---|---|---|
| F1 phantom capital-event state file | **UNMOVED** | `_STATE = data/cashcarry_state.json`; `ls` → no such file; `--show` → `inception $0.00` |
| F2 false-green Gate-0 board | **UNMOVED** | `gate0_readiness.json` still `keys_present: READY — "4 live-venue credential file(s)"`, still counts `binance_testnet.example.json` |
| F3 signoff split-brain | **UNMOVED** | board reads `gate0_signoff.json` → READY; guard reads `stage_state.json["principal_signoff"]` → key absent → False |
| F4 drill evidence unbridged | **UNMOVED** | `drill_report.json` has `critical_drill_failures: 0`; nothing writes it into ramp/promo evidence; `drill_pass_streak_weeks` has a reader (`ramp_gate.py:68`) and no writer |
| F13 six equity numbers | **WORSE — now seven** | see L21 census, 3.3× spread |
| F14/F15 deadman testnet-pinned | **UNMOVED** | `_FUT_BASE = testnet…`, `usdt_baseline 105,914` vs a $200 planned book |
| F7 no connector flip | **UNMOVED, and under-scoped** | L9: it is a 14-module cutover, not 2 lines |
| F23 one-keypress arm | **UNMOVED, and worse** | L27 + L1: the third factor is now satisfied by a stub |
| F25 no minNotional check | **UNMOVED** | `grep -c min_notional run_cashcarry_executor.py` → 0 |
| F9/F22 `gate0_complete` owner | **UNMOVED, blast radius now measured** | L24: sole blocker on freeze-exit; manifest names a false writer |
| — | **MOVED (the one win)** | the guard's graded output is now consumed: `_refresh_guard` → `size_frac` → `capital` at `:661`. Yesterday it was computed-and-ignored. |

**The meta-finding is the important one.** Yesterday's report was written, filed, and 0/10 of its
critical items converted in 24 hours — while the desk's own L1.28b conversion law says a
found-unfixed defect is an unbooked loss aging at its stated ROI. An audit that repeats itself is
cheaper than one that doesn't, and this one is now repeating. **The bottleneck on launch-readiness
is no longer detection. It is conversion**, and this report should be read as evidence for that
rather than as new detection.

## 1. WHAT WE KNOW (validated strengths, each with its proving command)

1. **The halt core is real and was live-exercised.** KILL is checked every 60s mid-loop, close-all
   is idempotent and retried, exceptions defer rather than crash (`run_cashcarry_executor.py:1479-1500`).
   Today's artifact proves the whole chain ran: ladder escalated 60m→4h, `_freeze` wrote
   `CASHCARRY_KILL`, executor closed to `n_positions: 0`, and venue truth agrees
   (`fut.positions()` → `{}`).
2. **Secret hygiene on the launch path is clean.** `umask 077`, `chmod 700 data/secrets`,
   `chmod 600` on keyfiles, `read -rs` (never echoed), `git ls-files data/secrets/` → empty,
   `git check-ignore` → ignored. No env-var path for live credentials by design
   (`grep -n "environ\|getenv" libs/execution/binance_live.py` → no matches).
3. **The capability whitelist holds inside the connector.** `grep "^def " binance_live.py` shows
   only order/cancel/read functions — no withdrawal, transfer or key-management wrapper.
   (Caveat unchanged from yesterday: `sub_accounts.py` wraps a live `universalTransfer` one module
   over — and it is an orphan with zero callers, so it is dead weight carrying a live-money surface.)
4. **REST-only: an entire launch-failure class is structurally absent.** No listenKey, no user-data
   stream, no keepalive (`grep -rn "listenKey\|userDataStream" --include=*.py .` → zero). See L18.
5. **Host clock is healthy with measured margin.** `chronyc tracking` → 0.78 ms against a 5000 ms
   `recvWindow`; chrony active 2 days.
6. **Fail-closed sentinels hold where they were deliberately placed.** `staging.py:83`
   `critical_drill_failures` defaults to `-1` (found twice, independently, by mutation testing);
   `run_live_guard.py:119-122` never auto-lifts another writer's kill; `ramp_gate.next_step` snaps
   down, never up, on an unrecognised state; `capital_events.rebase` refuses $0 deposits, unsigned
   events, and short reasons.
7. **The guard→executor sizing bridge now works** (the single confirmed improvement since yesterday):
   `_refresh_guard` reads `effective_size_fraction` and `canary.mode` and applies both.
8. **`run_live_guard` genuinely never arms anything**, and it is AST-fenced —
   `tests/scripts/test_live_guard.py::TestItNeverArms` asserts against the source, not a run.
9. **The REARM reply path is correctly scoped in code**: `run_alerts.py:160-172` unlinks only a
   `live_guard freeze`-authored kill, preserving deadman-authored ones.
10. **Drills are order-inert by construction and honest about it**: 3 scenarios / 19 assertions,
    `critical_drill_failures: 0`, and `tests/ops/test_drills.py::test_no_drill_can_place_an_order`.

## 2. WHAT WE DON'T KNOW (the ignorance ledger)

1. **Every live-venue behaviour.** No live fill has ever occurred. Real slippage, maker-fill rates,
   partial fills, fee tier, transfer latency, and the *actual Binance error codes* this book
   provokes are all unmeasured — and L12 means the desk currently has no instrument to record them
   even when they happen.
2. **Whether the launch would fail loudly or silently.** L1 alone → loud (KILL). L4 alone →
   silent (paper-trading). Both together → **silent**, because with the executor on testnet the
   invalid key is never exercised on the trading path. Which branch the desk lands in depends
   entirely on the order the fixes are applied, and nothing currently sequences them.
3. **REARM end-to-end, still.** `data/principal_replies.jsonl` does not exist; the only un-freeze
   path remains unexercised while the book has been frozen ~18 hours.
4. **The venue-vs-book divergence shadow is still calibrated on a scope mismatch** (futures-scope
   venue vs total-scope book). On the principal page since 07-27, unresolved, and L21 shows the
   underlying equity-source sprawl grew rather than shrank.
5. **Per-symbol venue minimums against the actual launch universe.** I deliberately did not query
   the venue for live minNotional values — this box had a 429 latched during the audit (L15) and
   adding load to diagnose a rate-limit finding would be self-defeating. Must be measured before
   launch, from a low-load window.
6. **What the account-level settings actually are.** Position mode, margin type, leverage,
   multi-assets, futures-account existence, key permissions: all unread, all unverified, and all
   unreadable until arming (the L1 deadlock — you cannot probe a key without arming live trading).
7. **Watchdog vs systemd ownership at cutover**, unchanged from yesterday and untested; plus the new
   wrinkle that the `quant` user is denied `systemctl`, so any launch-day restart needs a sudo human
   who appears in no runbook.
8. **Second-family check: SOLO.** The GPT-family partner seat remains down. Every verdict here is
   single-family and labelled SOLO — explicitly *not* CONFIRMED (L1.33). Two independent Claude
   sub-sweeps converging is *style* corroboration, not cross-family evidence, and must never be
   cited later as the latter.

## 3. WHAT COULD MATTER MOST (ranked by impact × confidence ÷ cost × maintenance)

The ordering below is **a sequence, not a menu** — several of these are unsafe if applied alone.

**P0 — the three that must land together, in this order, or not at all.**

**A1. Surface Binance error codes** (L12). Catch `HTTPError`, read the body, put `{code,msg}` into
the return dict and an *appended* error log. ~15 lines. It is first because it converts L11, L13,
L14, L16, L17 and L26 from silent failures into self-diagnosing ones — **nothing else on this list
is debuggable on launch day without it**, and it is the cheapest item here.
*Validation:* inject a mocked 400 with a Binance error body; assert the code appears in `_ERR`.
*Retirement:* never.

**A2. Key validity + an unarmed probe** (L1). Shape-validate in `finish_setup.sh`, change the skip
test from `-s` to a shape test, and add `--verify-keys` that permits exactly one read-only signed
call on `has_keys()` alone. This breaks the arm-to-test deadlock and delivers yesterday's F24
(permission probe) for free. *Failure mode if done alone:* none — this one is safe in isolation, so
it should go first in wall-clock terms too. *Validation:* the current stub must be rejected.

**A3. The connector factory + live-connector parity** (L4, L8, L9). `libs/execution/venue.py`,
the 14-module census as its work-list, `my_trades`/`commission_events` added to the live connectors
first, and a grep-fence in CI. **Doing A3 without A1/A2 turns a silent paper-launch into an immediate
KILL; doing A2 without A3 leaves the desk silently paper-trading.** This is the single largest item
(1–2 days) and the one that makes launch mean anything.

**P1 — the money-arithmetic fixes, all before the first order.**

**A4. Gate `_compounded_capital` on a live-inception boundary** (L19). Highest severity-to-effort
ratio on the list after A1: today it deploys 4× the authorised capital on the first live tick, and
the Gate-0 cap is evaluated on the pre-multiplied number. Ship with the NAV cutover record (L5) so
the boundary exists in one place. *Validation:* seed `stage: S1`, assert `_compounded_capital(200)
== 200`; it returns 800 today.

**A5. Copy three lines for multi-assets equity** (L10). `binance_testnet.py:181-183` →
`binance_live.py:186`. Three lines, prevents replaying the entire $5,000-blind-rail incident on
mainnet, where the default is the dangerous one. Ranked priority-#2 desk-wide on 07-31 and still
undone — **the cheapest CRITICAL on the desk.**

**A6. `min_notional` on both futures connectors + a pre-flight size check** (L13, L26). Kills the
one-legged-fill class *pre-flight* instead of discovering it 20 minutes later via the orphan
reconciler. Then compute the actual product of `_compounded_capital` × `effective_size_fraction` on
launch parameters — today it is 4× up then 0.05× down and nobody has ever multiplied them.

**A7. Live deadman + cutover state reset** (L6, and the reset list). One script,
`scripts/cutover_to_live.py`, all-or-nothing with a dry-run: re-init `deadman_state.json`, reset
`cashcarry_positions.json` (`start_futures_equity`, `realized_spot_pnl`, `peak_combined_equity` are
all testnet and all feed the ruin rail *and* A4), partition the execution tape by venue, and assert
the deadman observes deposit-scale equity for 3 polls **before** `LIVE_ENABLE` is touched.

**P2 — rails that are wired wrong rather than missing.**

**A8. Make the 60-minute rung actually de-risk** (L2) — give it `entries_allowed=False` so it writes
KILL, and rename the rungs to what they do. 2 lines. **A9. Cancel resting orders on escalation**
(L3) and replace the tautological drill. **A10. Fix the unarmed-reconcile fail direction** (L23):
`n_positions=None`/UNMEASURED, never 0, and rewrite the stand-down instruction to
`touch data/CASHCARRY_KILL`. **A11. Route the order path through `BINANCE_BAN_UNTIL`, stop
re-paginating income from inception every 60s, build the reserved kill budget** the spec already
mandates (L15).

**P3 — gates and boards that lie.**

**A12. Unweld the S1 gate** (L22): supply `symbol_count` into `promo_evidence`, and make `_ramp`
write `ramp_state.json` unconditionally rather than only on transition. **A13. Bridge drill evidence
into ramp evidence** (F4, unmoved) — the 8-week streak has a reader and no writer, so the ramp clock
has never started and every week it stays unwired is a week added to the earliest possible ramp-up
date. Start the streak at 0 from the bridge commit; backfilling from 3 existing runs would fake it.
**A14. One board, honest inputs** (F2/F4/L24): component-wise `keys_present` from the probe (A2),
`connector_verified` from live-tape rows only, `capital_fraction` from the *deployed* number (A4),
and either a writer for `gate0_complete` or its removal from the freeze-exit criteria.

**P4 — the procedure itself.** **A15.** Rewrite `go_live.md` around the *actual* dependency graph,
including the eleven acts the code requires that no document mentions (delete the stub key, clear
KILL *and* `--rearm`, reset deadman/positions/tape, fund BNB, set venue account options, verify key
permissions, restart the service — which needs sudo). **A16.** Write the abort procedure that does
not exist. **A17.** `set -e` and real exit-code checks in `finish_setup.sh` step 7 (L28).
**A18.** Correct `GO_LIVE_CHECKLIST.md` item E, which currently describes the opposite of the code
(L30).

**Compounding-multiplier flags:** A1 (error visibility) and A3 (the factory) are multipliers — A1
raises the diagnostic yield of every future incident, and A3 converts every future venue addition
and stage transition from a hand ritual into tested code. A7's dress rehearsal is the largest
multiplier of all: it turns launch-readiness from an opinion into a nightly measurement.

## 4. WHAT WE TEST NEXT (concrete, with success criteria and retirement)

1. **The cutover dress rehearsal, on a copy of `data/`** (needs A7; the single highest-value
   experiment available). Clone `data/`, run the cutover script, then assert: deadman re-inits with
   a live-scale baseline; `_compounded_capital(200) == 200`; change-window reads 0 live fills;
   freeze-exit `fills_4wk` goes False; the Gate-0 board's `connector_verified` goes NOT-READY;
   `keys_present` fails on the stub. **Success = all six flip correctly with zero manual edits.**
   This run alone would have caught L1, L4, L5, L6, L19 and L22. *Retirement:* after the first clean
   live week — and not before, because it is also the regression test for every fix above.
2. **Key-validity probe against the real key, before arming** (needs A2). `--verify-keys` →
   `GET /sapi/v1/account/apiRestrictions`. **Success = the endpoint answers, withdrawals are
   disabled, an IP whitelist is present.** Any red = stop. This is also the first-ever test of
   whether the desk's keys work at all.
3. **The order-error taxonomy drill** (needs A1). Mock each of `-2010`, `-2019`, `-2022`, `-4061`,
   `-4164`, `-1021`, `429` and assert each surfaces distinctly in `_ERR` and pages differently.
   **Success = a human reading `_ERR` can tell a benign reduceOnly rejection from a stranded leg**
   — the exact ambiguity that made today's MOVEUSDT record uninterpretable without a venue query.
4. **60-minute-rung effect drill** (needs A8). Seed `oldest_unacked_ts` at 61 minutes with a fake
   open position, run the guard *exactly as cron runs it*. **Success = positions closed or KILL
   written.** It fails today, which is the point.
5. **Resting-order cancellation drill** (needs A9). Seed a resting post-only order, escalate the
   ladder, assert it is cancelled. Replaces the tautological flag-check drill.
6. **REARM end-to-end** (unchanged from yesterday, still unexercised, and the frozen book is waiting
   on it right now). Inject a synthetic titleless reply; assert PAGE_ACK written, ladder cleared,
   live_guard-authored KILL unlinked, deadman-authored KILL preserved.
7. **First-live-day canary sequence, written into the runbook as gated steps**: keys placed →
   `--verify-keys` green → deadman observes deposit-scale equity for 3 polls → account preconditions
   probed (position mode, margin type, leverage, futures account exists) → capital event recorded
   against real state → `LIVE_VPS_VERIFIED` → (pause) → `LIVE_ENABLE` → **one minimum-notional
   canary round-trip** → verify the fill lands in the LIVE tape partition and a venue-side stop
   appears in `open_orders` within one guard tick → only then `top=4`. **Success criteria at every
   arrow; any red = stop, page, stay flat.** Step 5 of this sequence is the first execution of
   `place_stop_market` in the desk's history (L7), so it deserves its own explicit go/no-go.
8. **Minimum-viability arithmetic, measured not assumed**: query live per-symbol `minNotional`
   for the actual top-N funding universe from a low-load window, and compute
   `_compounded_capital × effective_size_fraction × cap_frac ÷ top` against it. **Success = every
   planned leg clears its venue minimum**, or the launch tranche is resized until it does.

## PERSPECTIVE COVERAGE TABLE

| Perspective | Verdict |
|---|---|
| **1. Internal** | COVERED. Measured, not configured: the halt/pager/refusal core is genuinely strong and was live-exercised (WHAT WE KNOW 1–10). The launch-specific wiring is broken in 9 critical places (L1, L2, L4, L6, L7, L8, L9, L19, L22–L23), and the top-line measurement is that **the launch procedure as documented cannot place a live order at all** (L9 census: zero order-capable modules import a live connector). |
| **2. External — motive-similar Tier-1 cohort** | COVERED. The cohort practice this desk is furthest from is not sophistication, it is **rehearsal**: Jane Street / Optiver / IMC do not cut a venue over without a dress rehearsal against cloned state, and no serious desk lets a *gate* be satisfied by data from a *different venue* (L22's masked deadlock). XTX/HRT-class practice on the connector layer is a single venue-abstraction with conformance tests both directions — the two-way parity gap (L8) would not survive there a day. From the crypto-native tier (Wintermute/GSR/B2C2), the missing practice is the **pre-trade account-state assertion**: position mode, margin mode, leverage and key permissions asserted at arm time, every time, because those are the settings that silently differ between a testnet and a funded mainnet account (L11, L16, L17). **Negative exemplars:** the rail that would have caught an Alameda-class drawdown here is the deadman — and L6 shows at cutover it watches the wrong account, which is the control-group lesson stated exactly: *the rail existed, was running, was fresh, and was pointed elsewhere*. LTCM's lesson maps to L19: size derived from a number nobody re-anchored at a regime boundary. **RenTech/Medallion as the ceiling exemplar:** their equivalent of this subsystem is decades of one book, one accounting truth — the seven-equity-number census (L21) is the single furthest point from that exemplar on this desk, and it grew by one row this week rather than shrinking. **Grade movement:** rails *design* B+ (unchanged, it is genuinely good); rails *wiring* **D → F** (the deadman is pinned, the stop has never executed, the 60-min rung is inert, the stand-down blinds the watcher); board integrity **F** (unchanged; two boards, opposite verdicts, both published every few minutes). |
| **3. Future (~2–3y)** | COVERED. With cheap agentic compute this whole subsystem becomes continuously rehearsed rather than reviewed: a nightly clone-and-cutover against a venue mock, every board line property-tested with "can any input make this fail?" (which would have caught L22's welded criteria immediately), connector conformance generated from one interface spec so a two-way parity gap is impossible to express, and the reality-gap chain (L2.10) auto-attributing live-vs-backtest divergence from fill one. The boards should be *generated* from the gate code, never written twice. |
| **4. Contrarian** | COVERED, and it changed my conclusion. I tested "the arming interlock makes us safe" and found it **inverted**: the three-flag design is what made key validity unverifiable (you cannot probe a key without arming live trading — L1), and it collapses to one keypress anyway (L27). I tested "more gates = safer" and found three parallel gate implementations giving three different answers, with two lying green (F2/F3/L22). I tested "the rails protect us" and found the strongest rail watching another account (L6), the venue-side stop never once executed (L7), and the documented emergency stand-down *disarming the watcher rather than the book* (L23). **The contrarian conclusion is now stronger than yesterday's: this system's safety is over-layered and under-wired, and fewer single-sourced mechanisms would be strictly safer than the current redundancy.** L23 is the crispest evidence — two branches four lines apart disagreeing about which direction is safe. |
| **5. Greenfield** | COVERED. Rebuilt from validated knowledge only: **one** venue abstraction with conformance tests (kills L4/L7/L8/L9); **one** equity oracle, mode-aware, venue-read, imported by every consumer (kills L21's seven numbers and L19's contaminated base); `data/live/` vs `data/testnet/` artifact roots so testnet output *cannot* green a live gate (kills the entire tape/positions/deadman contamination class structurally); **one** board generated from `staging.py`; rails unchanged, because the rails are the validated part. Historical-baggage score: **HIGH** — `cashcarry_state` vs `cashcarry_positions`, three signoff artifacts, merged tapes, and a `gate0_complete` file with no writer are all accretion, not design. |
| **6. Frontier** | COVERED, and honestly thin: nothing newly public this quarter changes this subsystem's math, and I am not going to manufacture one. The two genuinely available free externals both remain unconsumed: Binance's `apiRestrictions` endpoint (free key-permission verification, still zero callers — now doubly valuable because it is also the natural home for A2's validity probe) and `/fapi/v1/positionSide/dual` + `/fapi/v1/marginType` as free arm-time assertions (L16, L11). The relevant frontier here is internal: the desk's own drill-harness pattern generalises to every wired path, and the cutover rehearsal is the highest-value instance of it. |

## NEGATIVE-SPACE SWEEP (questions never asked before this audit)

Asked for the first time here, each with what it produced:

- *Is the live API key actually a key?* → **L1**, the worst finding in the report. Nobody had ever
  looked at the file's contents, only at its existence. Eight months of gates testing `bool(k and s)`.
- *What does "ARM" actually arm?* → **L4/L9**. The word appears in the launcher, the spec and the
  runbook; nobody traced it to an import statement.
- *Does the rung named `flatten_to_neutral` flatten anything?* → **L2.** The name was trusted
  because it is a good name.
- *Does anything read `cancel_resting`?* → **L3**, plus a drill that asserts a constant is a constant.
- *What number does the executor deploy on its first live tick?* → **L19.** Nobody had ever run the
  arithmetic; I ran it and it printed $800 against a $200 deposit.
- *Does the parity gap run the other way too?* → **L8.** Everyone had checked what testnet lacks;
  nobody checked what live lacks.
- *Who writes `gate0_complete`?* → **L24.** Asked yesterday, unanswered; answered today: nobody, and
  the manifest names a false writer.
- *What happens if you run the documented stand-down with positions open?* → **L23.**
- *Can the S1 gate ever be met?* → **L22.** No — two criteria are welded off by plumbing.
- *Is there an abort procedure?* → **L29.** No.
- *Is the launch procedure tested?* → **L31.** No — zero test references to `finish_setup` or
  `go_live`.

**Documented empty seams** (checked, nothing found — recording so the next sweep does not re-spend
the budget): no websocket/listenKey surface anywhere on the money path; no hardcoded live URLs
outside the live connector pair; no env-var credential path for live; no order-capable module
lacking a `has_keys` gate; host clock genuinely healthy with 3 orders of magnitude of margin; secret
file permissions and gitignore coverage clean; drills genuinely order-inert.

**Still never asked by anyone, including me** (the honest residual): what the funding-cycle phase
will be at the planned first open, and whether the 8h funding boundary interacts with the 600s
rebalance cadence; whether Binance has a maintenance window on the launch date; what the ladder does
to an *open order* at a rung transition (undrilled); whether anything caps how many times the
orphan-cover circuit can fire across *days* rather than hours.

## PROACTIVE BATTERY (which moves ran, what each produced — a move that produced nothing says so)

1. **Contingency-before-failure** → named the missing live deadman (L6), the missing abort procedure
   (L29), and the sudo-human dependency for any launch-day service restart (no runbook names them).
2. **Adjacency — the highest-yield move this sweep.** Three shapes were swept for siblings and every
   sweep found more: the *phantom-file* shape (F1) → `gate0_complete` has no writer at all (L24);
   the *hasattr/getattr silent no-op* shape (L7) → `cancel_order` dead by the same mechanism, and
   then the whole two-way parity gap (L8); the *hardcoded-testnet-import* shape (L4) → the 14-module
   census (L9). **One instance is never one instance** — L9 exists only because I refused to stop at
   the executor.
3. **Config-vs-outcome** → ran `record_capital_event.py --show`, `is_armed()`, `fut.positions()`,
   `fut.account_summary()`, and reproduced `_compounded_capital` arithmetically rather than reading
   its comment. The comment (`:162-172`) is a careful, correct-sounding safety argument that is
   wrong; only running it exposed the $800.
4. **Regression sweep — what did this session's own work make worse?** Nothing on disk (read-only).
   But intellectually: this report *lowers* the capability score while nothing regressed, which
   risks reading as decay. Stated explicitly in the scores so it cannot be misread. Second: I
   downgraded a sub-sweep's "naked short right now" claim after checking venue truth — reporting the
   weaker true claim over the stronger false one.
5. **Cost-inversion** → `apiRestrictions`, `positionSide/dual` and `marginType` are all **free**
   venue probes the desk pays nothing for and consumes zero of, while the arm-to-test deadlock (L1)
   is treated as unavoidable. It is not; the free probe dissolves it.
6. **Generalise-the-rule** → the "unmeasured must never render as zero" rule was written for
   utilisation (L1.28a) and applies verbatim to `n_positions=0` on an unarmed connector (L23) and to
   `symbol_count` defaulting to 0 (L22). Same law, two organs that never heard it.
7. **Autonomy check** → REARM is still *configured, never seen to work*; the book has been frozen
   ~18h waiting on precisely that path. The venue-side stop (L7) is configured, tested, and has
   *never executed anywhere*. Both are "green by configuration" in exactly the way the doctrine
   forbids.
8. **Negative space** → section above; 11 questions asked for the first time, 10 produced findings.
9. **Scope-the-negative-result** → "the launch is a no-op" is a **wiring** failure, not a capability
   failure: `binance_live` is complete, tested and correct; nothing imports it. That distinction is
   what makes A3 a 1–2 day job rather than a rebuild, and getting it wrong in either direction would
   badly misprice the launch.
10. **Ratchet check** → two ratchets are stalled and one is falling. The **drill streak** (the 8-week
    ramp prerequisite) has a reader and no writer, so it has never started counting — every week
    unwired adds a week to the earliest possible ramp-up date. The **conversion ratchet** is the one
    falling: 0/10 of yesterday's criticals converted in 24h. And the **equity-source count** ratcheted
    the *wrong way*, 6 → 7.

## LEDGER OBLIGATIONS (owed by the synthesis seat — this audit ran READ-ONLY)

L1–L31 and experiments 1–8 each owe a `recommendations.py` row (L2.3 / L1.28b), and the P0/P1
sequencing above is load-bearing — **A1, A2 and A3 must be rowed with their ordering dependency
recorded**, because applying A3 alone converts a silent failure into an immediate KILL and applying
A2 alone leaves the desk silently paper-trading. Use `--expect` for id allocation (two sessions
collided on ids previously). Yesterday's R1–R10 should be re-checked for existing rows before new
ones are cut — several of this report's items are the same defects with better evidence, and
duplicate rows would corrupt the conversion denominator exactly as the doctrine forbids.

**One row this report specifically owes as a blind-spot entry** (`blind_spot.py`, tagged `self`):
the desk shipped an arming interlock whose design made its own primary input unverifiable, and no
fence, drill, board or audit noticed for the eight months the stub key would have sat there. That is
a *class* of blind spot — "the gate checks presence where only validity matters" — and
`keys_present` is unlikely to be its only instance.

## FINDINGS LOG (raw, discovery order)

Numbered `L#` this sweep, to keep them distinct from yesterday's `F1–F27`.

### L1 [CRITICAL — the single worst thing on the money path] The live futures "API key" on this box is the literal string `claude setup-token`, the launcher will never ask for the real one again, and `keys_present` reads TRUE

The file the LIVE futures connector reads for credentials contains a pasted instruction, not a key:

```
$ .venv/bin/python -c "import json; d=json.load(open('data/secrets/binance_live.json')); \
    print({k:len(v) for k,v in d.items()}); print(d['key']=='claude setup-token')"
{'key': 18, 'secret': 18}
True
```

Both fields are the 18-character string **`claude setup-token`**. A real Binance API key/secret is
64 characters. `stat` dates the file to **2026-07-31 00:01:25Z** — i.e. it was written during a
`deploy/finish_setup.sh` run, and `grep` proves no code in the repo writes that value:

```
$ stat -c '%n created=%w size=%s' data/secrets/binance_live.json
data/secrets/binance_live.json created=2026-07-31 00:01:25.982496187 +0000 size=62
```

**The causal mechanism is legible and it is a prompt-confusion trap in our own launcher.**
`deploy/finish_setup.sh` asks for the futures key at **step 3/7** and asks the operator to paste
the output of the `claude setup-token` command at **step 5/7**. The operator answered step 3 with
step 5's *instruction*. The script accepted it without a single validity check and printed
`futures key: written` (`deploy/finish_setup.sh:38-41`):

```sh
printf 'Futures API key (Enter to skip for now): '; IFS= read -r FK
if [ -n "${FK:-}" ]; then
    printf 'Futures API secret (typing hidden): '; IFS= read -rs FS; echo
    printf '{"key": "%s", "secret": "%s"}\n' "$FK" "$FS" > data/secrets/binance_live.json
    chmod 600 data/secrets/binance_live.json; echo "futures key: written"
```

**It is now a permanent trap, not a one-off typo.** Line 34 gates the whole prompt on file
*non-emptiness*, so every future run of the one-command launcher skips key placement forever:

```sh
if [ -s data/secrets/binance_live.json ]; then
    echo "futures key: already present -- skipping (delete data/secrets/binance_live.json to redo)"
```

Run it tomorrow morning and the operator is told the futures key is **already present**. There is
no prompt, no warning, no diff. The remedy (delete the file) is stated only in that same skipped
line, which a successful-looking run gives no reason to read.

**Every downstream gate reports it as satisfied**, because every one of them tests *existence and
truthiness*, never *validity*:

```
$ .venv/bin/python -c "from libs.execution import binance_live; print(binance_live.has_keys()); print(binance_live.is_armed())"
True
(False, 'keys_present=True, live_enable_flag=False, vps_verified=False')
```

`libs/execution/binance_live.py:61-63` — `has_keys()` is `bool(k and s)`. The Gate-0 board counts
the file toward `keys_present: READY` (`data/gate0_readiness.json`, "4 live-venue credential
file(s)"). Nothing on this desk has ever asked Binance whether the key works.

**The launch-day sequence this produces, in order:** operator runs `finish_setup.sh` → step 3
prints "already present -- skipping" (looks correct) → step 3's spot branch offers "Use the SAME
key for spot? [y/n]", and `y` **copies the placeholder to the spot leg too** (`:47-50`) → step 6
touches `LIVE_VPS_VERIFIED` + `LIVE_ENABLE` → `is_armed()` now returns **True on both legs** → step
7 prints a Gate-0 board that says keys are READY → the deposit is recorded → the next rebalance
fires the first live signed call → Binance answers `-2014 API-key format invalid` (HTTP 401) →
`urllib.request.urlopen` raises `HTTPError` out of `_signed()` (`binance_live.py:106-108`, no
retry/classify layer) → the venue becomes unreadable to `run_live_guard`, which by design treats an
unreadable venue as naked and writes `KILL` (prior sweep, `run_live_guard.py:132-137`).

Net: **launch day ends in a frozen book, a KILL file, a page, and an operator who was told at every
step that the keys were fine.** That is the good branch. The bad branch is subtler and worse: the
desk is now in `LIVE_ENABLE` state with a dead connector while `data/gate0_readiness.json`,
`live_guard.json` and the deposit record all say the launch happened — the reality-gap chain (L2.10)
starts its life with a fabricated first link.

**The deepest part of this finding is not the typo — it is that arming is the first key test.**
`_signed()` refuses to run unless `is_armed()` is all-true, and `is_armed()` requires
`LIVE_ENABLE`. So there is **no way to validate a live key without first arming live trading**.
The one act the whole three-flag interlock exists to make deliberate and rare is also the only
diagnostic available. That is a genuine design defect, not an oversight: the interlock made key
placement unverifiable.

**Fix (all four parts, none optional):**
1. `finish_setup.sh` validates before writing: reject anything that is not 64 chars of
   `[A-Za-z0-9]`, and re-prompt. Same for the secret. (~4 lines of shell; this alone would have
   caught the live instance.)
2. Change the skip test from `-s` (non-empty) to a *shape* test, so a malformed key re-prompts
   instead of being grandfathered forever.
3. Add an **unarmed key-validity probe**: allow one specific read-only signed call
   (`GET /fapi/v2/account`, or better `GET /sapi/v1/account/apiRestrictions`) to run on
   `has_keys()` alone, behind an explicit `--verify-keys` entry point that can place no order.
   This breaks the arm-to-test deadlock and simultaneously delivers yesterday's F24 (permission
   probe: withdrawal-enabled / IP-whitelist verification) for free.
4. `check_gate0_ready._keys_present()` must report the *probe result*, not a filename glob.

**Retirement condition:** none — key validity is checked at every placement, forever.
**Severity justification:** it is the first thing that happens on launch day, it fires exactly
once, it is silent, and it is *already broken on disk right now*.

### L2 [CRITICAL] The 60-minute absence rung is named `flatten_to_neutral` and flattens nothing — a live book gets a 3-hour window where the ladder believes it de-risked and the positions are 100% on

`libs/ops/derisk_ladder.py:8-9` states the contract:

```
    60 min unacked -> flatten to neutral
     4 h  unacked -> full flatten, entries DISABLED until manual re-arm
```

and `docs/GO_LIVE_CHECKLIST.md` section E sells it to the principal as *"unanswered pages de-risk
the book automatically."* Trace what actually executes at the 60-minute rung on a live, armed book:

1. `run_live_guard.py:249-260` — flatten is gated on `venue is not None and allow_flatten`.
   The **only** scheduled invocation passes neither flag:
   ```
   $ grep -n "run_live_guard" ops/crontab.manifest
   208:*/5 * * * * cd "$QUANT_ROOT" && flock -n data/.cron_live_guard.lock \
        .venv/bin/python scripts/run_live_guard.py >> data/cro_ai_logs/live_guard.log 2>&1
   ```
   No `--allow-flatten`. The module docstring (`:26-27`) is explicit that this is by design:
   *"gated on being armed AND on --allow-flatten, which the scheduled unit does not pass. Left to
   a human or to a deliberately configured unit."* **No such human step and no such unit exist**
   (the runbook never mentions `--allow-flatten`; the crontab has exactly one live_guard line).
2. `run_live_guard.py:247` — `freeze_needed = rep.freeze_entries or not rung.entries_allowed`.
   The 60-min rung is `Rung(name="flatten_to_neutral", cancel_resting=True, size_multiplier=0.0,
   flatten=True)` (`derisk_ladder.py:58-59`) and **`entries_allowed` defaults to `True`**
   (`:44`). So `freeze_needed` is False → **no `CASHCARRY_KILL` is written** at this rung.
3. The only surviving effect is `effective_size_fraction = 0.0`, which the executor consumes as
   `capital = capital * 0.0` (`run_cashcarry_executor.py:661`). That kills *opens* only.
   `target`/`hold_set` are computed from the funding ranking, not from capital
   (`:633-634 hold_set = {s for s, _ in ranked[:hold_top]}`), and the code comments confirm the
   intent: *"Held carries are never resized"* (`:694`) and *"OPENS ONLY -- target/hold_set are
   untouched"* (`:628`).

**Net behaviour of the rung called `flatten_to_neutral`: it stops the book growing. It does not
reduce a single position.** The book only actually de-risks at the **4-hour** rung, where
`requires_manual_rearm=True` becomes a tripwire → `entries_allowed=False` → `freeze_needed=True` →
`_freeze()` writes `CASHCARRY_KILL` → the executor's `_KILL` branch closes all carries
(`:1479-1489`, "KILL: closing all carries + idling until the kill file clears"). That path is real
and was exercised live yesterday.

So there is a **3-hour window (T+60min → T+4h) of an unattended live book carrying full exposure**
while every artifact reports the ladder as having flattened to neutral. Today's `live_guard.json`
prints the confession verbatim:

```
$ .venv/bin/python -c "import json;print(json.load(open('data/live_guard.json'))['flatten'])"
rung full_flatten_disarmed requires flatten -- NOT executed (armed=False, --allow-flatten=False)
```

Note the message names **two** blockers. `armed=False` disappears on launch day. `--allow-flatten=False`
**never does**, because it lives in a crontab line nobody plans to change. On launch day this line
will read `(armed=True, --allow-flatten=False)` and mean exactly the same thing.

**Why this is worse on a live book than the KILL-at-4h fallback suggests:** the whole point of a
graded ladder is that the intermediate rung is *cheap* (reduce exposure calmly, maker-first) and
the terminal rung is *expensive* (close everything at once). As wired, the desk skips the cheap
step entirely and takes the expensive one 3 hours later — the exact "safety layers amplifying"
pathology yesterday's F5 named, arrived at from the opposite direction.

**Fix (pick one, not both):** either (a) add `--allow-flatten` to the crontab line and make
`flatten_all()` maker-first, or (b) — better, and consistent with the module's own single-halt
principle — give the 60-min rung `entries_allowed=False` so it writes KILL like the 4h rung, and
rename the rungs to what they do (`stop_opens` / `close_all_disarmed`). Option (b) is 2 lines and
adds no new order path. Either way the drill must assert the *effect*, not the flag (see L3).
**Validation:** drill — seed `oldest_unacked_ts` at 61 minutes with a fake open position, run the
guard as cron runs it, assert positions closed or KILL written. It fails today.
**Retirement condition:** none (survival rail).

### L3 [HIGH] `cancel_resting` is a field that nothing reads, and the drill that "covers" it asserts the constant is the constant

```
$ grep -rn "cancel_resting" --include=*.py . | grep -v ./.venv
tests/ops/test_derisk_ladder.py:27:  assert r.cancel_resting and r.size_multiplier == 0.5 and r.entries_allowed
scripts/run_drills.py:143:  d.check(all(r.cancel_resting for r in LADDER if not r.is_floor), ...)
libs/ops/derisk_ladder.py:41:  cancel_resting: bool = False
libs/ops/derisk_ladder.py:57,59,61:  cancel_resting=True, ...
```

Four hits: one dataclass field, three assignments, one unit test, one drill. **Zero production
consumers.** `run_live_guard` never cancels an order; the executor never reads the flag.

The drill is the instructive part. `run_drills.py:143` asserts `all(r.cancel_resting for r in
LADDER if not r.is_floor)` — it verifies that a literal `True` written on line 57 is still `True`
on line 143. It can never fail for any reason connected to the desk's behaviour, and it counts
toward the 19/19 PASS the readiness board leans on. This is the desk's own named quarry
("self-greening guards") inside the drill harness itself.

**The live consequence is specific, not theoretical.** The executor's entry path rests **post-only
maker orders** and waits (`_maker_pair`, `:1085-1100`). If the ladder escalates while a maker quote
is resting, nothing cancels it. That order can fill minutes-to-hours later — *after* the desk
decided to de-risk — and because the pair legs are quoted independently, a one-sided fill creates a
**new naked leg after the de-risk decision**, on an unattended book, which is precisely the state
the naked-position tripwire exists to prevent.

**Fix:** `run_live_guard` calls `venue.cancel_all_open_orders()` on any rung with
`cancel_resting=True` (cancellation is not a live-money *exposure* action — it strictly reduces
risk, so it does not belong behind the `--allow-flatten` gate). Replace the tautological drill with
one that seeds a resting order and asserts it is gone.
**Retirement condition:** none.

### L4 [CRITICAL] The "ARM" step does not arm the executor — the launcher can report ARMED, the board can go green, the deposit can be recorded, and the book keeps trading testnet faucet money forever

This is yesterday's F7 (connector switch), unmoved, and its blast radius is larger than F7 stated.
The executor binds its venues at **module import**, unconditionally:

```
$ grep -n "binance" scripts/run_cashcarry_executor.py | head -3
28:from libs.execution import binance_spot_testnet as spot
29:from libs.execution import binance_testnet as fut
```

There is **no** mode switch of any kind — proven by exhaustion, not by inference:

```
$ grep -n "importlib\|sys.modules\|LIVE_ENABLE\|LIVE_VPS\|getenv\|environ" scripts/run_cashcarry_executor.py
(no output)
$ ls libs/execution/venue.py
ls: cannot access 'libs/execution/venue.py': No such file or directory
```

And `--live` does not mean live: `run_cashcarry_executor.py:1435` is `dry = not args.live`, and
`:1462` prints the mode as **`LIVE-PAPER`**. The flag separates dry-run from order-placing; both
place those orders on testnet.

**Therefore the three arming flags gate the wrong layer.** `data/LIVE_ENABLE` and
`data/LIVE_VPS_VERIFIED` are read only by `binance_live.py:49-50` and `binance_spot_live.py`, whose
importers are the *monitoring* layer — `run_live_guard` (venue reads), `record_capital_event`, the
canary — never the *trading* layer. `finish_setup.sh` step 6/7 is titled **"ARM"**, prints
**`ARMED (stand down instantly any time: rm data/LIVE_ENABLE)`**, and changes nothing about which
exchange the book trades on.

**The launch-day sequence this produces:** operator runs the one-command finisher → it prints ARMED
→ step 7 prints the Gate-0 board → operator deposits real money on Binance mainnet → operator runs
`record_capital_event.py --deposit 200` as instructed → the executor's next rebalance opens carries
**on testnet, with faucet money**, exactly as it has all month. Nothing errors. No page fires. The
execution tape keeps filling (and keeps feeding `connector_verified: 523 recorded fills` on the
board). `live_guard.json` will report `armed: true` because *its own* connector is armed, so even
the guard corroborates the illusion. The real deposit sits untouched on mainnet while the desk
compounds a paper book and calls it live.

**This defect and L1 interact in the worst way.** L1 (dead keys) is loud: the monitoring layer's
signed calls fail, the guard writes KILL, someone notices. L4 is *silent*, and L4 masks L1: with
the executor on testnet, the trading path never makes a live signed call, so the invalid key is
never exercised, so the loudest available symptom of L1 never fires. Fixing L1 alone leaves the
desk silently paper-trading; fixing L4 alone turns the launch into an immediate KILL. **They must
be fixed together, and the canary round-trip (which does make a signed live call) must run between
arming and the first executor tick.**

**Fix:** yesterday's R5 — `libs/execution/venue.py: get_connectors(mode)` reading one mode source,
imported by the executor and everything else; plus a grep-fence forbidding
`import binance_.*testnet` outside the factory. Until it exists, the launch requires hand-editing
lines 28-29 of the executor **inside the L1.38 change window** — i.e. the launch procedure as
written cannot be executed without violating the sterile-cockpit law. That is the strongest
possible argument for building the factory *before* the window opens, not during it.
**Validation:** run the executor in dry mode through the factory in both modes; assert testnet
behaviour is byte-identical; assert `get_connectors("live")` refuses when `is_armed()` is False.
**Retirement condition:** never — it *is* the flip.

### L5 [HIGH] The from-inception track record hardcodes `mode: "PAPER (testnet)"` and attests a simulated curve — it will keep doing both, hash-chained and tamper-evident, through and after launch

`docs/GO_LIVE_CHECKLIST.md` section D marks NAV attestation BLOCKING and calls it *"the single
largest lifetime lever this desk has"*, *"cannot be backfilled"*, *"ALREADY RUNNING on paper equity
— continuity through go-live is the point."* The script's own docstring agrees. Then:

```
$ grep -n "mode" scripts/run_nav_attest.py
72:        "mode": "PAPER (testnet) -- pre-Gate-0",
```

A string literal. No writer, no derivation, no cutover step in any runbook. And the equity it
attests is the molded curve, not an account balance (`:34-41 _equity()` reads
`data/live_combined_state.json` → `mcurve[-1][1]`), which today's record shows plainly:

```
$ tail -1 data/nav_attestation.jsonl
{"date":"2026-08-01",...,"molded_curve_usd":18811.04,"equity_marked":18811.04,
 "_note":"molded_curve_usd is a MOLDED/SIMULATED curve, not venue truth and not a track record;
  venue truth is the dead-man's combined_equity",...,"mode":"PAPER (testnet) -- pre-Gate-0",...}
```

So on live day 1 the allocator-grade chain will append `equity_marked: ~18,800`, `mode: PAPER`, for
a desk holding a real ~$200. Every subsequent day chains off that hash. The failure is not that the
record stops — it is that it **continues seamlessly while lying**, and the hash chain plus the git
push make the lie permanent, third-party-timestamped, and impossible to quietly correct later. An
allocator who ever audits this finds a record whose own `mode` field says PAPER across the entire
live period; the "100× lever" is not merely un-earned, it is actively poisoned.

The note is honest about where truth lives — *"venue truth is the dead-man's combined_equity"* —
but the deadman is still testnet-pinned (yesterday's F14/F15, verified unmoved below at L6), so at
cutover **there is no venue-truth source on the box at all** for the attestation to switch to. The
three defects compose: no live executor (L4) → no live venue reader (L6) → no honest NAV (L5).

**Fix:** derive `mode` from the same single mode source as the connector factory (L4); attest
`equity_marked` from venue truth (deadman combined_equity, once L6 makes it live) and keep
`molded_curve_usd` as a clearly separate key; on the cutover date write one explicit
`{"event":"cutover","from":"PAPER","to":"LIVE"}` record so the boundary is in the chain rather than
inferred. **Validation:** cutover dress-rehearsal on a copy of `data/` asserts the next appended
record reads `mode: LIVE` and `equity_marked` within a few percent of the deposit.
**Retirement condition:** none.

### L6 [CRITICAL — regression, unmoved] The deadman is still hard-pinned to testnet, by URL *and* by keyfile, and its baseline is 17× the live book

Yesterday's F14/F15, re-verified today, zero movement:

```
$ sed -n '32,36p' scripts/run_deadman_switch.py
_FUT_BASE  = "https://testnet.binancefuture.com"     # PINNED testnet -- never live
_SPOT_BASE = "https://testnet.binance.vision"        # PINNED testnet -- never live
_FUT_KEYS  = _ROOT / "data" / "secrets" / "binance_testnet.json"
_SPOT_KEYS = _ROOT / "data" / "secrets" / "binance_spot_testnet.json"

$ cat data/deadman_state.json
{"version":2,...,"usdt_baseline":105914.865,"high_water":6257.587,"breaches":0,
 "disarmed_live":false,"last_eq":6226.847}
```

The rail is alive and correct — *for the testnet account*. `usdt_baseline` 105,914 against a planned
live deposit of ~$200 is a factor of ~530. Even after the flip its high-water anchor is 6,257
testnet dollars, so the 0.65×HWM fire line sits at ~$4,067 — a line a $200 live book can never
cross, in either direction. The Tier-3 rail would be structurally incapable of firing on the live
book while reporting itself armed, fresh (`data/deadman_heartbeat` written 50s before this check)
and breach-free.

This is the control-group lesson stated exactly: the rail that would have caught an Alameda-class
loss **exists, is running, and is watching the wrong account.**

### L7 [CRITICAL] The venue-side protective stop — "the rail that survives host death" — has never executed once, by construction, and first executes on live money

`run_cashcarry_executor.py:1015`:

```python
if not fut.has_keys() or not hasattr(fut, "place_stop_market"):
    return []
```

`fut` is `binance_testnet`, and that module **has no `place_stop_market`**:

```
$ grep -c "^def place_stop_market" libs/execution/binance_testnet.py
0
$ grep -n "^def place_stop_market" libs/execution/binance_live.py
358:def place_stop_market(symbol: str, side: str, qty: float, stop_price: float) -> dict[str, Any]:
```

So `_reconcile_protective_stops` has returned `[]` on the first line for the entire life of this
desk. The same is true of the whole cancel/replace half of the function: `canceler =
getattr(fut, "cancel_order", None)` is `None` on testnet (`cancel_order` is also live-only), so
stop-orphan cancellation and drifted-stop replacement are dead code too.

The docstring names the gap honestly (*"No-op on connectors without stop support (testnet parity
gap, recorded)"*) — but recording a gap is not closing it, and the consequence is the sharpest
"fires exactly once, that day, wrong" instance in this whole subsystem: **the first time this
function does anything at all is against a real Binance mainnet account, holding real money, on
launch day, with an untested `"BUY"` side literal and an untested stop-price plan.** The naked-position
tripwire, the §3 stop invariant, and `live_guard`'s "all N position(s) carry an adequate venue-side
stop" summary all rest on a code path with zero execution history anywhere.

`tests/execution/test_binance_live_behaviour.py:44-64` mocks it and asserts the request shape — that
is worth something, and it is not evidence that the venue accepts the order.

### L8 [CRITICAL] The parity gap runs BOTH ways: five production scripts call functions the live connector does not have

The asymmetry is not "testnet is a subset". It is a genuine two-way divergence:

```
$ python - <<'EOF'   # (re-derivable; regex over "^def " in each module)
TESTNET-ONLY (live is missing these): ['commission_events', 'my_trades']
LIVE-ONLY   (never runs on testnet): ['cancel_order', 'is_armed', 'place_stop_market']
SPOT TESTNET-ONLY: ['my_trades']       SPOT LIVE-ONLY: ['is_armed']
EOF
```

`my_trades` and `commission_events` are the **fill-level reconciliation and fee-forensics
primitives**, and five production scripts call them:

```
scripts/run_deadman_reconciliation.py:100  spot.my_trades(...)
scripts/run_deadman_reconciliation.py:102  fut.my_trades(...)
scripts/run_stranded_recovery.py:62        spot.my_trades(...)
scripts/run_venue_reconcile.py:182         _f.commission_events(since)
scripts/run_trade_forensics.py:88          _fut.commission_events(since_ms)
```

Any connector factory (L4) that swaps these modules to live turns all five into `AttributeError` on
first call — including **stranded-inventory recovery**, which exists because a swallowed order error
once stranded ~$2,150 of real inventory. The live connector must gain `my_trades` and
`commission_events` *before* the flip, or the flip breaks reconciliation on day one.

### L9 [CRITICAL] The whole money path is welded to testnet: 13 production modules import a testnet connector, 3 import a live one, and none of the 3 trades

Full census (non-test importers):

```
$ grep -rn "execution import binance_..." --include=*.py . | grep -v ./.venv | grep -v ./tests
--- binance_testnet ---            --- binance_spot_testnet ---
libs/execution/maker.py            scripts/check_spot_testnet.py
scripts/check_testnet.py           scripts/run_cashcarry_executor.py
scripts/max_audit.py               scripts/run_cashcarry_testnet.py
scripts/run_cashcarry_executor.py  scripts/run_deadman_reconciliation.py
scripts/run_cashcarry_testnet.py   scripts/run_deadman_stranded_sweep.py
scripts/run_crypto_testnet.py      scripts/run_live_combined.py
scripts/run_deadman_reconciliation.py   scripts/run_stranded_recovery.py
scripts/run_live_combined.py
scripts/run_trade_forensics.py     --- binance_live ---            --- binance_spot_live ---
scripts/run_venue_reconcile.py     libs/execution/sub_accounts.py   scripts/run_live_guard.py
                                   scripts/record_capital_event.py
                                   scripts/run_live_guard.py
```

Read the right-hand column carefully. The **only** production importers of the live connectors are
a guard (reads), a capital-event recorder (reads), and `sub_accounts.py` — which has **zero
non-test callers at all** (`grep -rn "sub_accounts" --include=*.py . | grep -v ./.venv` returns only
`tests/execution/test_sub_accounts.py`), i.e. an orphan. **Nothing that can place an order imports a
live connector.**

Everything else — the executor, the maker algorithm library itself (`libs/execution/maker.py`), the
dashboard/molded-curve feed (`run_live_combined.py`), deadman reconciliation, stranded recovery,
venue reconciliation, trade forensics, and `max_audit`'s venue reads — is welded to testnet at
import time. Plus `run_deadman_switch.py`, pinned by URL constant rather than import (L6), which the
grep does not catch — worth noting because it means an import-graph fence alone would miss it.

**This reframes the launch.** The flip is not "set a flag" or even "edit two import lines in the
executor". It is a **14-module cutover** touching the executor, the maker library, four
reconciliation/recovery scripts, the dashboard feed, and the deadman — every one of them on the
money path, every one of them inside the L1.38 sterile-cockpit window, with no factory, no fence, no
dress rehearsal, and no document that lists them. Yesterday's R5 was scoped as "ship the connector
switch"; the census says its true scope is roughly triple that, and that under-scoping is itself the
finding — a launch plan sized against 2 of 14 files will run out of runway on the day.

**Fix:** `libs/execution/venue.py: get_connectors(mode)` as R5 specified, but with the census as its
work-list, live-connector parity closed first (L8), and a grep-fence
(`import binance_.*(testnet|live)` outside the factory → CI failure) so the census cannot silently
regrow. **Validation:** the fence is the validation — it enumerates violations by file and line.
**Retirement condition:** never.

---

## VENUE ACCOUNT-PRECONDITION FINDINGS (L10–L17)

Produced by a dedicated sub-sweep of the connector/executor code; **every claim below that I carry
forward I re-verified myself by direct read this session** (the verifying command is shown). Two of
the sub-sweep's claims I downgraded on verification and say so.

### L10 [CRITICAL] The multi-assets equity fix was applied to the testnet connector and NOT to the live one — the ruin rail goes blind on mainnet's default setting

Binance USD-M defaults to **single-asset margin**, under which `totalMarginBalance` counts **USDT
only**. The desk has already been bitten by this once (07-30 execution-growth F6: $5,000 of USDC
valued at zero → high-water below `_MIN_HW` → dead-man disarmed at every equity, plus a flatten of a
solvent book). The fix is present on testnet and absent on live:

```
$ sed -n '180,183p' libs/execution/binance_testnet.py     # FIXED
    eq = max(sum(float(x.get("marginBalance", 0.0)) for x in a.get("assets", [])
                 if x.get("asset") in _STABLE_COLLATERAL),
             float(a.get("totalMarginBalance", 0.0)))

$ sed -n '185,188p' libs/execution/binance_live.py        # UNFIXED
    a = _signed("/fapi/v2/account", {})
    return {
        "wallet": float(a.get("totalWalletBalance", 0.0)),
        "equity": float(a.get("totalMarginBalance", 0.0)),
```

Three lines, on the connector that will hold real money, on the setting whose mainnet default is the
dangerous one. The 07-31 execution-growth sweep ranked this **priority #2 of the entire desk** and it
is still undone. Deposit any USDC/FDUSD/BFUSD into the futures wallet on day one — a completely
ordinary thing to do — and the Tier-3 rail goes blind, silently, in the direction that looks safe.

**This is the cheapest CRITICAL fix on the desk: copy three lines.**

### L11 [CRITICAL] Venue leverage is never set on the open path, and the ruin stop sits *behind* the liquidation price at both the default and the desk's own chosen leverage

`/fapi/v1/marginType` is **never called anywhere** (`grep -rn "marginType" --include=*.py .` → zero
hits). `set_leverage` is wrapped but has exactly **one** production caller, and it is in the wrong
branch:

```
$ grep -n "_STOP_FRAC\|set_leverage" scripts/run_cashcarry_executor.py
553:                fut.set_leverage(sym, 3)      # <- inside _reconcile's RE-HEDGE branch only
979:_STOP_FRAC = 0.35                             # spec section 3: ruin-line distance
983:               *, frac: float = _STOP_FRAC) -> dict[str, dict[str, float]]:
```

The **open** path (`:817-864`) and the **topup** path (`:872-913`) never call it. So a symbol's first
short goes out at the account default — **CROSS margin, 20×** on a new mainnet account — and only
drops to 3× after that symbol has already broken a hedge once. The book converges to a
heterogeneous, unknown per-symbol leverage state that nothing records.

The consequence is arithmetic, not stylistic. `_STOP_FRAC = 0.35` places the protective stop 35%
adverse, and its docstring claims that sits *"comfortably inside the leverage-cap liquidation
band"*. At 20× the liquidation band is ~5% adverse; at the 3× the re-hedge branch sets, ~33%.
**In both cases the venue liquidates before the stop can fire.** The rail that L7 shows has never
executed is, when it finally does execute, placed where it cannot work. Cross margin compounds it:
all four shorts share one wallet, so one name's tail takes the whole futures leg.

(`risk_controls.evaluate(..., ruin_cap_lev=8.0)` at `:749` is a book-level gross/equity cap and does
not constrain the venue liquidation price — checked, it is not a mitigation.)

**Fix:** set `marginType=ISOLATED` and an explicit `leverage` **per symbol before the first open**
(idempotent, cheap), choose leverage so liquidation is strictly further than `_STOP_FRAC` (at 0.35
that means ≤2×), and assert `positionRisk.leverage` after. Today the derivation runs backwards: the
stop distance was chosen and the leverage was never chosen at all.

### L12 [CRITICAL] Binance error codes are destroyed at every order site — a benign rejection and a book-breaking one are byte-identical in the record

No connector distinguishes any HTTP status or any Binance error code. Every request is a bare
`urlopen` (`binance_live.py:107-108`), and every order site wraps the call in `_safe()`, so on any
`HTTPError` the result variable stays `None`:

```python
# run_cashcarry_executor.py:1256-1266
    with _safe():
        spot_res = spot.place_market(sym, spot_side, qty)
    with _safe():
        fut_res = fut.place_market(sym, fut_side, qty, reduce_only=_reduce_only_leg)
    ...
            _ERR.write_text(f"... unfilled leg {sym} spot_ok={spot_ok} fut_ok={fut_ok} "
                            f"spot_res={spot_res!r} fut_res={fut_res!r}\n")
```

So `-4061` (position-side mismatch), `-1021` (clock skew), `-2019` (insufficient margin), `-2010`
(insufficient balance), `-4164` (below min notional), `-2022` (reduceOnly on a flat position), a
`429`, and a dropped TCP connection **all render identically as `spot_res=None fut_res=None`**. Note
`write_text`, not append: only the last error of the session survives.

**A live instance was sitting on disk 40 minutes before this audit**, and it is the perfect
illustration:

```
$ cat data/cashcarry_error.log
2026-08-01T02:05:42 unfilled leg MOVEUSDT spot_ok=True fut_ok=False
  spot_res={'status':'FILLED','executedQty':'47306.0'} fut_res={'status':'REJECTED','executedQty':'0.0'}
```

Spot leg filled, futures leg rejected — the signature of a **naked leg**. I checked venue truth
rather than assume:

```
$ .venv/bin/python -c "from libs.execution import binance_testnet as f; print(f.positions())"
{}          # zero open futures positions -- the pair ended flat
```

**So this instance was benign** (almost certainly `-2022 reduceOnly rejected` because the short was
already closed — the KILL loop's close-all is idempotent and retries). I am downgrading the
sub-sweep's "naked short right now" claim accordingly. **But that is precisely the finding:** the
desk had a record showing the exact signature of a stranded leg and *no way to tell it from the
benign case without a manual venue query*. The ~$2,150 stranding incident of 2026-07-19 is the same
signature. On live money, with the operator asleep, "spot filled / futures rejected" must page
immediately if the code is `-2019`, and must be ignored if it is `-2022` — and today the desk cannot
tell, because the connector throws the code away before anyone sees it.

**This is the highest-leverage fix on the entire list**, above even L10: catch `HTTPError`, read
`.read()`, surface Binance's `{"code","msg"}` into the return dict and into an **appended** error
log. ~15 lines. It converts L11, L13, L14, L16 and L17 from silent failures into self-diagnosing
ones. Everything else on this list is undebuggable on launch day without it.

### L13 [CRITICAL] `MIN_NOTIONAL` is never checked on either leg, and the futures connectors do not even parse it — at the configured $50–70/name this manufactures one-legged fills

```
$ grep -n "min_notional" libs/execution/binance_live.py libs/execution/binance_testnet.py
(no output — the futures connectors do not parse it at all)
$ grep -n "min_notional" libs/execution/binance_spot_live.py | head -2
114:        notl = f.get("NOTIONAL", {}) or f.get("MIN_NOTIONAL", {})
119:            "min_notional": float(notl.get("minNotional", 0.0) or 0.0),
$ grep -c "min_notional" scripts/run_cashcarry_executor.py
0
```

Spot parses it; futures does not; **and the executor consumes it from neither.** Sizing checks
`stepSize` and `minQty` only (`:825-828`). At `capital: 200`, `top: 4`, per-name notional is
**$50–70**. Most USD-M perps clear their 5–20 USDT minimum — BTCUSDT futures does **not** (100 USDT,
yesterday's F25). For any symbol whose futures minimum exceeds the allocation, **the spot leg fills
and the futures leg is rejected**, leaving a naked long spot leg discovered only by the orphan
reconciler ~20 minutes later (`_ORPHAN_CONFIRM = 2`), after paying a full round-trip to undo.

`tests/execution/test_filter_parity.py:89-106` already documents that futures publishes this under
the key `notional`, not `minNotional` — the trap is known, written down, and the field was simply
never added. **Fix:** add `min_notional` to both futures connectors (guarded by that existing parity
test) and extend the sizing check to `qty*px < max(ffl["min_notional"], sfl["min_notional"])`. ~10
lines, kills the whole one-legged-fill class pre-flight.

### L14 [HIGH] The deposit instruction and the trading config contradict each other — as written, day one buys $200 of spot out of a $100 spot wallet

```
$ grep -n "Deposit" deploy/finish_setup.sh
102:echo '  1. Deposit $200 on Binance (~$100 spot wallet, ~$100 futures wallet)'
$ cat data/cashcarry_config.json
{ "top": 4, "hold_top": 3000, "capital": 200 }
```

`capital` is consumed as **total spot notional** (`_alloc(cands, free)` → `qty = alloc[sym]/px`,
`:701`, `:826-830`). The wallet split is stated in exactly one place — a shell `echo` — and it is
half of what the executor will try to spend. The failure is directional: futures shorts need ~$10 of
margin at the 20× default (L11) and **fill**; spot buys hit `-2010` on roughly half the book,
producing **filled, untracked, naked SHORT perps** on a book whose entire thesis is delta-neutrality.
`docs/playbooks/go_live.md` contains no wallet-split step at all. There is also no spot↔futures
transfer path in the codebase (deliberately — `LIVE_CONNECTOR_SPEC.md:90` puts capital movement
out of scope, principal-only), so the split cannot be corrected by the desk after the fact.

**Fix:** reconcile the two numbers (either `capital: 100` or a $400 deposit); make the wallet split a
numbered, verified step in the runbook (`spot free USDT >= capital` read back before arming); and add
a pre-flight refusal that skips a pair when free spot USDT is below its planned notional rather than
firing one leg of it.

### L15 [HIGH] The rate-limit budget is unmeasured, the ban latch does not cover the order path, and a 429 was latched on this box during this audit

```
$ cat data/BINANCE_BAN_UNTIL ; date -u +%s
1785551027 code=429 retry_after=14
1785552600                      # (the latch had expired ~26 min before this read)
```

The desk is already tripping 429s at *testnet* request volume. No connector reads
`X-MBX-USED-WEIGHT`, `X-MBX-ORDER-COUNT` or `Retry-After`. The `BINANCE_BAN_UNTIL` cross-process
latch is real and well-built (`libs/data/crypto_source.py:50-69`) but lives on the **public data
path only** — `binance_live._signed` never consults it.

The per-tick weight is not budgeted anywhere and grows monotonically with account history:
`_mark()` runs on **every 60s heartbeat** (`:1515`) and calls `fut.income_summary(start_ms)` with
`start_ms` = **inception, forever** (`:1315`), which paginates up to 50 pages at weight 30
(`binance_live.py:208`) and is retried 3× (`carry_accounting.py:35`). And the mitigation is one the
desk already specified and never built: `docs/LIVE_CONNECTOR_SPEC.md:16` — *"`kill` path keeps its
own reserved rate-limit budget (crisis = everyone else is hitting 429)."* There is no reserved
budget, no token bucket, no weight accounting. A 418 during a KILL close-all is the 2026-07-31
incident replayed on live money.

### L16 [MED] Position mode is correct only by luck, and one UI click makes every order fail

`grep -rn "positionSide\|dualSidePosition" --include=*.py .` → **zero hits repo-wide**. The code
omits `positionSide`, which is correct in ONE-WAY mode (the mainnet default) — so today it works.
But this strategy is *visibly* a hedge, and an operator looking at a long-spot/short-perp book has an
obvious reason to switch Hedge Mode on in the UI. The moment they do: `-4061` on every order, and
`-1106` on every `reduceOnly` — meaning the protective stop (`binance_live.py:364`) and every close
leg become unplaceable simultaneously. **Fix:** one signed `GET /fapi/v1/positionSide/dual` at arm
time; refuse to arm unless `dualSidePosition == false`. Pin one mode and fail loud; do not support
both.

### L17 [MED] Symbol tradability and futures-account existence are both assumed

`exchange_filters()` ingests **every** symbol in `exchangeInfo` regardless of `status`
(`TRADING`/`BREAK`/`PENDING_TRADING`/`SETTLING`), `contractType`, or spot `isSpotTradingAllowed`
(`grep -n "isSpotTradingAllowed\|contractType\|PERPETUAL" libs/execution/ scripts/run_cashcarry_executor.py`
→ zero hits). `_ranked()` filters only on `funding > 0`, `endswith("USDT")` and presence in both
filter dicts. A halted or delivery contract will be ranked, allocated and ordered. Meanwhile
`scripts/collect_announcements.py:71` already tracks delisting and leverage-tier announcements — the
intelligence exists and is not wired to the order path.

Separately: a brand-new Binance account is **spot-only** until the USD-M futures account is
separately opened (quiz + agreement). Nothing probes for it, and the failure is silent in the worst
way — the risk block at `:713-756` is wrapped in `with _safe():`, so if `/fapi/v2/*` raises, `risk`
stays `None`, **the ruin rail simply does not evaluate, and the book opens anyway.**

### L18 [GOOD — documented working paths]

Three things were checked hard and found genuinely sound; recording them so the next sweep does not
re-spend the budget:

- **No websocket/listenKey surface on the money path.** `grep -rn "listenKey\|userDataStream"
  --include=*.py .` → zero hits. All four Binance connectors are `urllib.request` only. The classic
  "listenKey expired, fills stopped arriving, book went blind" launch failure **cannot happen here**.
  (The only websocket in the repo is a public Bybit research feed, `liquidation_listener.py:36`.)
  Given the 14-day silent-websocket incident this codebase remembers, REST-only was the right call —
  and the desk pays for it in rate-limit weight instead (L15), which is an honest trade, not an
  oversight.
- **Host clock is healthy and the failure mode is bounded.** `timedatectl` → `System clock
  synchronized: yes`, `chrony` active 2 days, `chronyc tracking` → `0.000781 s fast of NTP`. That is
  0.78 ms against the connectors' 5000 ms `recvWindow`. Genuinely fine today. The residual is that
  nothing *notices* if it stops being fine (a `-1021` would surface as `spot_res=None` — see L12).
- **BNB fee burn is switched on idempotently from the first tick** (`_enable_fee_burn()`, called at
  `:1423`, first line of `main()`), for both futures and spot. The *verification* of the outcome is
  what is broken: `max_audit.py:1064` checks the **testnet** BNB balance and only the **futures**
  wallet, so post-cutover it greens on a dead paper account forever, while
  `GO_LIVE_CHECKLIST.md:29-31` marks BNB funding BLOCKING and unticked. Real cost: the desk's own
  ledger records `COMMISSION -47.10` against `FUNDING_FEE +16.27` — commissions ~3× the harvest.

---

## SIZING AND EQUITY FINDINGS (L19–L21)

### L19 [CRITICAL] The compounding re-anchor reads TESTNET realised P&L and deploys 4× the authorised capital on the first live tick — the Gate-0 capital cap is evaluated on a number the code immediately multiplies

`_dynamic_capital()` → `_compounded_capital()` (`run_cashcarry_executor.py:138-213`) is armed and
wired into the rebalance (`:1509`). It is inert today only because `_is_live()` requires
`stage_state.json` to read S1/S2, and the box is S0:

```
$ cat data/stage_state.json
{"stage": "S0", "note": "S1 flips at live-connector deployment (Gate 0); ..."}
```

**S1 is exactly what launch day flips.** The moment it does, this executes:

```python
# :206-212
def _compounded_capital(default: float) -> float:
    if not _is_live():
        return default
    grown = default + _realised_pnl() * _COMPOUND_FRACTION      # _COMPOUND_FRACTION = 1.0
    lo, hi = default * _COMPOUND_MIN_FACTOR, default * _COMPOUND_MAX_FACTOR   # 0.5x, 4.0x
    return float(min(max(grown, lo), hi))
```

`_realised_pnl()` (`:197-203`) reads the last line of `nav_attestation.jsonl` →
`realized_spot_pnl`. That figure is **testnet P&L accrued over the paper month**, and nothing in any
runbook, script or cutover step resets it. I ran the arithmetic (pure computation, no state
touched):

```
$ .venv/bin/python -  # reproduces _compounded_capital with the files as they are right now
config capital (authorised)      = $200.00
realized_spot_pnl from NAV chain = $2,930.43   <- accrued on TESTNET
grown = default + realised       = $3,130.43
clamp [0.5x, 4.0x]               = [$100.00, $800.00]
=> deployed spot notional on the FIRST live tick after S1 = $800.00
   i.e. 4.0x the authorised capital, against a $200 deposit
```

**On the first live rebalance the executor will try to deploy $800 of spot notional against a $200
deposit — of which, per the runbook's own split, ~$100 is in the spot wallet.** That is 8× the
available spot balance, so via L14's mechanism nearly every spot leg fails `-2010` while nearly
every futures short fills, producing a book of naked shorts. And the only thing between the desk and
**$3,130** (15.7×) is the clamp.

**Why the existing safety argument misses it.** The module comment (`:162-172`) names the hazards
and closes them one by one — *"NEVER raw equity. Testnet equity marks ~$10.8k because of faucet
bags, so anchoring to it would balloon the book. Only realized_spot_pnl from the NAV attestation is
used."* The reasoning is correct about the *equity* contamination path and completely blind to the
*realised-P&L* contamination path, because the author was defending against faucet bags, not against
paper profits. Realised P&L is honest — it is honestly testnet.

**And it defeats the one gate built to bound launch size.** `check_gate0_ready._capital_fraction()`
(`:95-112`) computes `cap = config capital` and reports `capital $200 / equity $18,676 = 1.1%
READY`. It measures the **authorised** number. The code multiplies that number by up to 4 the
instant the gate opens. A cap evaluated on a quantity the system is free to scale immediately
afterwards is not a cap.

**Fix:** (a) `_realised_pnl()` must only count P&L realised **at or after the cutover record** —
which requires the NAV chain to carry an explicit cutover boundary (L5's fix, so the two land
together); (b) until that exists, hard-gate `_compounded_capital` on a `live_inception_date` and
return `default` when realised P&L predates it; (c) the Gate-0 capital-fraction row must report
`_dynamic_capital(config capital)`, i.e. the number that will actually be deployed, not the
configured one. **Validation:** a test that seeds `stage: S1` plus the current NAV chain and asserts
`_compounded_capital(200) == 200`. It fails today, returning 800.
**Retirement condition:** none — the boundary is permanent.

### L20 [HIGH] The sizing knob fails OPEN: a corrupt or missing config silently restores the watchdog's `--capital 4500`, a 22.5× step-up

`_live_params` (`:1379-1393`) reads `data/cashcarry_config.json` each rebalance and, per its own
docstring, *"any error (missing/corrupt file, bad type) silently falls back to the argv values."*
The argv on the running process are:

```
$ pgrep -af run_cashcarry_executor
1626623 .../python scripts/run_cashcarry_executor.py --live --top 10 --hold-top 3000 --capital 4500 --interval 600
```

So the failure direction of an unreadable config is **capital 200 → 4500 and top 4 → 10**
simultaneously: 22.5× the notional across 2.5× the names, with no log line (the `except` is a bare
`pass`) and no page. On testnet that is yesterday's F18 as an abstraction; on a $200 live account it
is the whole account, several times over, on a truncated write or a disk-full moment.

This is the same fail-open shape as the guard read (`_refresh_guard`: stale guard → full size,
takers allowed), and both were justified by the same reasoning — "the KILL file is the freeze
authority". That reasoning holds only while something is alive to write the KILL file.
**Fix:** on config read failure hold the LAST-GOOD parsed params (or halt opens), never argv; and
strip `--capital 4500 --top 10` from the watchdog respawn line so the fallback is small, not large.

### L21 [HIGH — regression, quantified] "Six equity numbers" is now seven, measured in a single session, and they disagree by 3.3×

Yesterday's F13 named the class. Here is the census, every figure read this session:

| # | Source | Value | Scope / provenance |
|---|---|---|---|
| 1 | `gate0_readiness.json` capital-fraction row | **$18,676** | NAV chain via `_desk_equity_usd()` — the molded/simulated book |
| 2 | `nav_attestation.jsonl` (08-01) `equity_marked` | **$18,811** | molded curve, `mode: "PAPER (testnet)"` |
| 3 | `cashcarry_positions.json` `last_combined_equity` | **$8,687** | executor's combined futures+spot-legs persist |
| 4 | `deadman_state.json` `last_eq` / `high_water` | **$6,227** / $6,258 | testnet venue read, 60s cadence |
| 4b | `deadman_state.json` `usdt_baseline` | **$105,915** | testnet faucet baseline |
| 5 | `binance_testnet.account_summary()` — live read now | **$5,756** | testnet futures venue truth |
| 6 | `record_capital_event.py --show` | **$0.00** / UNVERIFIABLE | reads a phantom file (F1, unmoved) |
| 7 | `cashcarry_config.json` capital vs process argv | **$200** vs **$4,500** | authorised vs fallback (L20) |

Rows 4 and 5 are supposed to be the *same quantity from the same account* and differ by 8%
(a 60s-stale cache vs a live read — explicable, but it means the rail's fire-line arithmetic runs on
a number nobody reconciles). Rows 1–2 vs 3 vs 5 span **3.3×**. Every capacity band, every ruin
fraction, every `capital_fraction_le_010` verdict and every Kelly-adjacent decision is a ratio to
*one* of these seven, and no code agrees on which.

The desk already knows this class: the L1.28a proving instance was deployed capital reading
13,155/4,500 — over 100% — from exactly this split-source pattern. It has not been closed; it has
grown by one row.

**Fix:** the greenfield answer (one equity oracle module, mode-aware, venue-read, every consumer
imports it) is the only one that ends the class. The launch-blocking subset is narrower: rows 1, 2,
3 and 6 must all read venue truth for the LIVE account before the first order.

---

## GATE, RUNBOOK AND ABORT FINDINGS (L22–L30)

### L22 [CRITICAL] The S1 gate that `live_guard` publishes can never be met: `symbol_count` is supplied by nobody, and `ramp_state.json` has a writer that can never run

```
$ .venv/bin/python -c "import json;print(json.load(open('data/live_guard.json'))['stage_gate'])"
{'target':'S1','met':False,'why':"principal_signoff=False, capital_fraction_le_010=True,
  symbol_count_4_5=False, keys_present=False, connector_verified=False"}
```

`symbol_count_4_5=False` while `data/cashcarry_config.json` says `"top": 4`. Cause:
`staging.s1_entry_met` reads `int(evidence.get("symbol_count", 0))` (`staging.py:62`), and
`run_live_guard.py:234-241` assembles `promo_evidence` from `_load(_RAMP, {}).get("evidence", {})`
plus exactly four explicit keys — `keys_present`, `connector_verified`, `capital_fraction`,
`principal_signoff`. **`symbol_count` is in neither half.** It defaults to 0 forever.

The `_RAMP` half is worse, because it is a writer that cannot execute:

```
$ ls data/ramp_state.json
ls: cannot access 'data/ramp_state.json': No such file or directory

# run_live_guard.py:171-176 — the ONLY writer
    nxt, why = ramp_gate.next_step(current, evidence)
    if nxt != current:
        ...
        _RAMP.write_text(json.dumps(state, indent=2), "utf-8")
```

At the floor rung, `next_step` returns the current step, so `nxt == current`, so the file is never
created, so `evidence` is `{}` on every subsequent run, so every step-up condition fails, so the ramp
stays at the floor. **A closed loop with no entry point.** Its visible consequence is today's
artifact: `ramp.size_fraction: 0.1` blocked by all six checks, forever.

This composes into a second deadlock on top of L9's. `connector_verified` is defined as *"a real
round-trip against the venue was recorded — not that code exists"* (`check_gate0_ready.py:57`), and
L9 proved **nothing that can place an order imports a live connector**. So: the gate needs a live
fill; the live fill needs a code path that does not exist. Today that deadlock is *masked* because
the execution tape's 523 **testnet** fills make the board's row read READY — i.e. **the gate passes
only by measuring the wrong venue.** Fix the tape contamination without shipping the connector
factory and the gate becomes permanently, visibly unsatisfiable.

This is exactly the GATE-OPTIMALITY duty's quarry: a gate that rejects 100% of candidates carries
zero information. Two of its five criteria are welded off by plumbing, not by evidence.

### L23 [CRITICAL] The documented stand-down command blinds the rails and leaves the book open — and the "unarmed" branch fails OPEN four lines below a branch that correctly fails closed

`finish_setup.sh:91` tells the operator: `ARMED (stand down instantly any time: rm data/LIVE_ENABLE)`.
Here is what that does (`run_live_guard.py:126-137`):

```python
def _reconcile(venue, now):
    if venue is None:
        rep = stops.ReconcileReport(naked={}, breaches={}, n_positions=0)
        return rep, "connector not armed -- venue not read (no positions can exist)"     # FAIL-OPEN
    try:
        positions = venue.positions(); orders = venue.open_orders()
    except Exception as e:
        rep = stops.ReconcileReport(naked={"<unreadable>": 0.0},
                                    breaches={"<unreadable>": stops.NAKED_GRACE_S + 1},
                                    n_positions=-1)
        return rep, f"venue read FAILED ({e!r}) -- treating as naked, fail-closed"        # FAIL-CLOSED
```

**The two branches are four lines apart and disagree about the safe direction.** A venue read that
*errors* is correctly treated as naked. A connector that is *unarmed* is treated as "no positions can
exist" — which is an assumption, not a measurement. Positions at Binance do not disappear when a
local flag file is deleted.

So `rm data/LIVE_ENABLE` on a live book with open carries: the no-naked-position invariant reports
`all 0 position(s) carry an adequate venue-side stop`, the canary stops probing, `flatten_all`
becomes unreachable (`:252 if venue is not None and allow_flatten`), and the positions sit at the
venue unwatched and unstopped. **The documented emergency stand-down disarms the watcher, not the
book.**

**Fix:** the unarmed branch must return `n_positions=None`/UNKNOWN and be reported as UNMEASURED, not
zero (L1.28a: unmeasured counts as zero *utilisation*, never as zero *risk*). And the runbook's
stand-down must be `touch data/CASHCARRY_KILL` (which closes the book) with `rm data/LIVE_ENABLE`
named as what it is — a key-disarm for after the book is flat.

### L24 [HIGH] `data/gate0_complete` has no writer anywhere, the manifest names a false one, and this single phantom file is the sole blocker on the entire post-Gate-0 activation

```
$ grep -rn "gate0_complete" --include=*.py . | grep -v ./.venv | grep -v ./tests
scripts/run_cadence.py:160:  "gate0": ("data/gate0_complete", "scripts/max_audit.py"),
scripts/run_cadence.py:214:  checks["gate0"] = Path("data/gate0_complete").exists()
scripts/max_audit.py:1266:  if not (ROOT / "data/gate0_complete").exists():      # <- a READ
```

Two readers and a registry row. **Zero writers.** `docs/POST_GATE0_MANIFEST.md:16` states the
artifact is *"written by `scripts/max_audit.py`"* — `max_audit.py` only reads it. And the cost of
that phantom is total:

```
$ cat data/freeze_exit_status.json
{"met": false, "why": "gate0=False, fills_4wk=True, cost_model=True, calib_10=True, no_criticals=True"}
```

**Four of five freeze-exit criteria are satisfied. The fifth is a file nobody creates.** The entire
post-Gate-0 activation manifest — eight queued capability activations — hangs off it, and no
document says who creates it or when. This is yesterday's F9/F22 confirmed with the blast radius
now measured.

### L25 [HIGH] Nothing in any launch document tells the operator how to un-freeze the book, and the book is frozen right now

```
$ cat data/CASHCARRY_KILL
live_guard freeze 2026-07-31T08:35:24Z: pager ladder at 4h rung (disarmed)
$ .venv/bin/python -c "import json;print(json.load(open('data/derisk_state.json'))['reached'])"
full_flatten_disarmed
$ grep -rn "CASHCARRY_KILL\|--rearm" docs/playbooks/go_live.md deploy/finish_setup.sh
(no matches)
```

The book has been frozen for ~18 hours and `data/principal_replies.jsonl` still does not exist, so
the REARM path has **never fired end-to-end** (unchanged from yesterday). Recovery needs **two**
acts, in either order but both: `run_live_guard.py --rearm <who>` (clears the latch) *and* removal of
the kill file — because `_freeze(False, …)` deliberately never deletes it (`:119-122`, "Never
auto-lift"). Do only the first and the file remains; do only the second and `run_live_guard` rewrites
it within 5 minutes. Neither act appears in any launch document.

### L26 [HIGH] After a successful launch and rearm, the guard sizes the book below the venue minimum — the book cannot open at all

`effective_size_fraction = ramp × ladder × canary` (`run_live_guard.py:263`). Post-rearm the factors
are: ramp floor **0.10** (welded there by L22), ladder **1.0**, canary **0.5** (`limit_only` —
*"no successful canary on record — unproven execution path"*, today's artifact). Product = **0.05**.

`capital 200 × 0.05 = $10` across `top: 4` names = **$2.50 per name**, i.e. ~$1.25 per leg after the
pair splits. Binance minimums are $5–$20 per leg. Every order is rejected, no position ever opens,
and — because of L12 — **no code names the reason**. The desk would sit "live", armed, funded, and
silently unable to trade, with `min_notional` parsed on the spot connector and read by nobody (L13).

Note the interaction with L19: `_compounded_capital` runs *before* the guard multiplier
(`:1508-1510` computes `cap` then `_rebalance`, which applies `size_frac` at `:661`), so the two
distortions are multiplicative in opposite directions — 4× up then 0.05× down. Nobody has ever
computed the product on live parameters.

### L27 [HIGH] The three-flag interlock collapses to a single keypress, and there is no dual control, timer or second step anywhere

`binance_live.py:8-13` explains at length that key placement and arming are kept separate *"so
'keys exist' and 'trading is armed' are never the same moment"*, and `go_live.md:60-62` repeats it.
Then:

```sh
# deploy/finish_setup.sh:88-90
printf 'Is THIS host the durable production box (not a rebuild)? [y/n] '; IFS= read -r DUR
if [ "${DUR:-n}" = "y" ]; then
    touch data/LIVE_VPS_VERIFIED data/LIVE_ENABLE
```

One `y` sets both flags. Combined with L1 (the third flag is already satisfied by a stub), **the
entire three-factor interlock is one keypress.** There is no cooling-off timer, no second signature,
no mtime separation check, and no key-permission probe (`grep -rn apiRestrictions --include=*.py .`
→ zero) — so a key with withdrawals enabled and no IP whitelist arms exactly as easily as a correct
one. Yesterday's F23 named this; it has not moved, and the stub-key finding makes it strictly worse
than it was.

Related, and arguably the single most dangerous unguarded act on the box: the highest-blast-radius
change is not a `touch` at all — it is editing `"stage": "S0"` → `"S1"` in `data/stage_state.json`.
One line, no gate, no signature, no audit prompt, and per L19 it 4× the deployed notional.

### L28 [MED] `finish_setup.sh`'s verification step cannot fail

```
$ grep -n "set -" deploy/finish_setup.sh
15:set -uo pipefail
```

`-e` is absent, three of the four step-7 checks are piped (so their exit status is discarded by
`tail`/`head`), and `check_gate0_ready.py` returns 0 unconditionally (`:187`, `:197`). The step
prints reassuring output and proceeds to `DONE` regardless of what it found. A launch "verification"
that cannot return failure is a ceremony.

### L29 [MED] Two runbook steps have no executable command, including the one you need under stress

`docs/playbooks/go_live.md:44` instructs `libs.execution.staging.promote(evidence)`; `:51` instructs
`libs.execution.staging.demote(reason)`. Both are bare Python APIs with no CLI
(`grep -rn "add_argument.*demote\|--demote" --include=*.py scripts` → no matches; no non-test caller
of `staging.promote` exists). The operator must hand-assemble an evidence dict in a REPL to enter
S1 — and open a REPL under stress to abort.

Which leads to the gap that ought to be embarrassing: **there is no abort procedure.** A grep for
abort/rollback/stand-down/disarm across every launch document returns **one** line
(`go_live.md:52`). There is no "if it goes wrong at T+10 minutes" section anywhere. The de-facto
abort is `touch data/CASHCARRY_KILL`, documented only in `docs/playbooks/carry.md:11` and
`docs/institutional_knowledge.md:172` — neither linked from any launch doc — and per that same
institutional-knowledge entry it historically fought the 3-minute watchdog in a respawn storm.

### L30 [MED] `GO_LIVE_CHECKLIST.md`'s blocking item E is factually inverted and 8 days stale

Lines 57-68 declare the compounding re-anchor *"currently disconnected"* and *"Correctly NOT built
pre-live (2026-07-23 assessment)"*. It shipped: `run_cashcarry_executor.py:156-212`, wired at
`:1509`, and it is the mechanism of L19. An operator working the checklist tomorrow would either
build a second one or, worse, tick the box believing the risk is absent. A BLOCKING checklist line
that describes the opposite of the code is more dangerous than a missing line.

### L31 [LOW but structural] Nothing tests the launch procedure

`grep -rln "finish_setup\|go_live" tests/` → **no matches.** The one procedure that runs exactly once,
under time pressure, with real money, with no rollback, has zero rehearsal coverage. Every other
critical path on this desk has drills; this one has none.

