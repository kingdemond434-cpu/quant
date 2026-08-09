# CAPABILITY HUNT PROPOSALS 20260731 slot 5

LENS: STALE-CONSUMER -- find code reading an artifact without checking its age, so a frozen producer silently feeds yesterday's number into today's decision.

## A -- Claude family

Hunt complete. The lens produced one deep proposal with a live compound instance on the money path, plus a wide brainstorm. Everything below is propose-only (read-only run honored).

---

## MISSING CAPABILITY

**Consumption-time freshness contracts: every decision-path read of a produced artifact declares its max tolerated age at the read site, feeding a self-building registry that joins {artifact age × consumer contract × producer liveness} into a blast-radius verdict — which live decisions are consuming frozen inputs right now.**

## WHY IT IS INVISIBLE TODAY

The desk has **five separate producer-side max-age registries** — `max_audit.py` (organ→glob,max_age_hours), `check_ratchets.py` (metric→max_age), `check_miner_runway.py` (seat→max_age_h), `check_exploration.py` (organ→max_age), `data_health.py` (datasets) — all hand-enumerated, all answering *"did the producer run?"* None knows **who reads what**. So a dead producer surfaces as one line among 25 in `scheduler_cadence: 22/47 organs ran in 48h — IDLE-EXPLAINED`, an *idleness* stat, while its frozen artifact keeps being consumed downstream as if current. Severity is set by the consumer, and no consumer mapping exists anywhere. Each instance gets discovered by hand, in an audit, after the fact — the desk's record shows at least five (below), each fixed individually, the class never named.

## MECHANISM

- `libs/ops/fresh.py` — one helper: `read_fresh(path, max_age_h, kind='measurement'|'state', mode='fallback'|'strict')` → returns `(data, age_h, fresh)`. On stale: `fallback` returns None + records, `strict` raises (executor-grade, mirrors `lawful.guard(strict=True)` semantics). Every call appends its contract `(path, max_age_h, caller, kind)` to `data/freshness_contracts.jsonl` (TTL-marker throttled, same cheapness trick as `lawful.guard`). **The registry builds itself from actual reads** — no sixth hand list to rot.
- `kind='state'` (e.g. `stage_state.json` — valid-until-changed) swaps the mtime check for a **guardian-liveness contract**: the read is fresh iff the named guardian organ (`run_live_guard.py`) has produced within ITS cadence. This distinction is what keeps the fence from crying wolf on legitimately-old state files (L1.43).
- `scripts/check_freshness.py` (fence; L1.41 five conditions): walks the registry + statted mtimes + `check_organ_liveness` output. States: `OK` / `STALE-CONSUMED` (older than contract AND read since going stale — the smoking gun, with caller) / `STALE-UNREAD` / `UNCONTRACTED-READ` (decision-path read with no declared contract) / `UNMEASURABLE` (refusal path — never silent-OK). Fails on STALE-CONSUMED; feeds `run_max_push.py`.
- Freshness reads the artifact's **content `generated` field when present, mtime only as fallback** — the 10-minute auto-deploy and the puller's revert path rewrite files, so mtime can lie *fresh* after a deploy; all five existing registries are mtime-based and share this hole.
- Bootstrap migration (~6 read sites found this run): executor `_structurally_bleeding` (web/trade_forensics.json — **no age check**), `_rt_bps` (data/cost_model.json — **no age check**; stale falls back to per-symbol stale numbers silently, should degrade to the pessimistic `_DEFAULT_RT_BPS`), `_stage` read (354h-old `stage_state.json`, `kind='state'` guardian=live_guard), `run_cadence.py`'s stage read, the Holm-slot snapshot consumer, max_push queue consumers.

**The compound this run found, live, on the money path:** `run_live_guard.py` is simultaneously the size-fraction governor and the stage-demotion tripwire evaluator. If it dies: the executor's guard read degrades to *neutral full size, takers allowed* — fail-open **by documented design** ("stale guard is no guard"), on the bet that the KILL file covers freezes — but the KILL file is written *by the guard* (`run_alerts.py:167`), so a dead guard can never write its own freeze; simultaneously stage demotion stops being evaluated, so S1/S2 authorization persists unguarded. Both degradations point toward **more aggressive execution**, and no watcher pages on `live_guard.json` age (`run_alerts` covers the executor + recorder heartbeats only; grep confirmed). During launch week this is a detection gap on the money path — L1.38 classifies building detection for it as repair-adjacent, not a frozen improvement.

## WHAT IT WOULD HAVE CAUGHT

1. **L1.28c(b)'s own proving instance** — max_push queue built 00:41/06:41/12:41/18:41, consumed 2h stale by brain slots at 02:45/08:45/14:45/20:45 (measured 2026-07-31). STALE-CONSUMED fires on first read.
2. **Idle Holm slot via stale snapshot** (alpha-discovery audit 2026-07-31: "idle Holm slot, m=11, snapshot stale") — a forward slot's evidence never accrued; L1.28a idleness caused by exactly this class.
3. **panel_verdicts.jsonl 189h stale** while the adaptive review consumed it, pinning payload at its 40k floor (GAP #89 context) — 8 symptom-defects, one frozen producer; the blast-radius join reports the cause with its radius.
4. **GAP #60(c)** — the ADL branch's 2h force-order window "has no staleness bound, so a stale read keeps firing after the condition passed": live-ammo, named in the register as an instance; `read_fresh(strict)` is the standard fix it lacks a standard for.
5. **The equity 13,155/4,500 two-sources defect** (L1.28a first run) — `UNCONTRACTED-READ` makes any second reader of an authoritative number visible by construction; the third equity source in `research_state` (research-engine audit 07-31) likewise.

## ROI

Direct: closes three unguarded money-path reads plus the guard-death fail-open compound during the live-capital window. Cascade: the registry **is the producer→consumer edge list** that L1.28c names as the scheduler's end-state ("event-driven firing is the end state") — you cannot fire consumers on producer updates without knowing the edges; this builds them as a side effect. It also converts organ-liveness from an idleness stat into a ranked blast-radius list (which of the 25 silent organs is feeding a live decision *now*), and can absorb the five hand registries into one measured surface (L1.12 deletion of dead weight).

## COST

~2h helper + ~3h fence + ~2h bootstrap migration of the 6 read sites; near-zero maintenance (self-building). Competes with the 112-row repair-mode backlog — but it is itself a defect-closer class (T1 under §33 pricing), and the guard-death page alone (one line in `run_alerts.py`) is shippable in minutes if the builder wants a partial.

## FALSIFIER

Sweep every decision-path read site: if each already carries an inline age check (as `_refresh_guard`'s 900s does), the class is covered instance-wise and only the blast-radius join remains. Then instrument the next 3 real producer deaths: if producer-side alarms empirically page **before** any consumer's first stale read in all 3, consumption-time checking adds no latency advantage and the fence is decoration — retire the proposal on that record.

NOVELTY-CHECK: `grep -rn "read_fresh\|freshness\|max_age" --include="*.py" libs/ scripts/` → only producer-side checkers (max_audit, check_ratchets, check_miner_runway, check_exploration, data_health/vitals, organ_liveness); `grep -ri "stale" docs/GAP_REGISTER.md` + ledger scan → instance-level rows only (#60 ADL window, #82 NAV 7d fallback, R0021/R0085); no consumer-side helper, no contract registry, no blast-radius join exists.

---

## BRAINSTORM (raw generation, one line each — builder rows the strongest; screen-on-discovery governs)

1. **IDEA: Page on `live_guard.json` age >15min in `run_alerts.py`** — the size-governor/tripwire-evaluator's death is currently invisible while the executor fail-opens to full size; one-line fence, ship-today partial of the main proposal — **S** — ledger.
2. **IDEA: `calibration_status.json` has no `generated` timestamp** — the calibration fence's own output can't be age-checked from content; its producer freezing would feed a frozen "calibrated" verdict forever (UNMEASURED-REPORTED-AS-OK, the L1.40 defect class both 07-31 fences shipped with) — **A** — ledger.
3. **IDEA: Consume the measured under-confidence bias (−0.197) in the UP direction** — L1.29(c): a bias term nobody consumes is decoration; desk is *under*-confident, meaning EV rankings and Kelly-shrunk sizes are systematically timid — wire `calibrated_confidence` into the sizing/priority path and measure the shift — **S** — ledger.
4. **IDEA: Promotion-date ledger to make births countable** — `replacement_rate.json` reads UNMEASURED-BIRTHS for want of dated promotion history; stamp Stage-B transitions into a dated promotion ledger and L1.30 becomes measurable in one commit — **A** — ledger.
5. **IDEA: Stale-denylist fail direction** — executor's `_structurally_bleeding` returns False on ANY read error (`except → False`), so a corrupt/missing forensics file silently re-opens proven bleeders (NOMUSDT −149bps class); stale/corrupt should keep the last good denylist or refuse new opens — **A** — ledger.
6. **IDEA: Min-content contracts (empty-producer detection)** — a producer that runs but emits zero rows (forensics with empty `worst_symbols`, label_factory's crash-as-NO-INPUT from memory) passes every mtime check; contracts need min_bytes/min_rows like `max_audit` already has, generalized — **A** — ledger.
7. **IDEA: Move `web/trade_forensics.json` money-path input out of the publish directory** — a dashboard regeneration path can clobber the executor's denylist source; money-path inputs belong in `data/` with web copies derived — **B** — ledger.
8. **IDEA: flock-skip observability for all ~40 cron lines** — `flock -n` silently skips when a lock leaks, so an organ "runs" per cron forever while executing never; R0136 fixed this for CI only (adjacency: same failure shape everywhere) — count skips per lock file and page on streaks — **A** — ledger.
9. **IDEA: Deploy-epoch mtime guard** — after each auto-deploy/puller revert, write `data/deploy_epoch`; freshness checks treat mtime older than epoch-adjacent rewrites as suspect, closing the mtime-lies-fresh-after-deploy hole in all five existing registries — **B** — folds into main proposal.
10. **IDEA: Producer/consumer schema-version field in contracts** — `_rt_bps` hardcodes depth key `"500"`; a recorder bucket change silently defaults every symbol to 39.5bps; contracts carrying a schema version turn silent drift into a fence fire — **B** — ledger.
11. **IDEA: NAV-chain freshness tightening** — capacity_policy tolerates 7d-stale NAV for `live_book_usd`, the number every capacity ratio divides by; at current compounding a 7d-old book materially mis-sizes bands; tighten to 48h with the constant fallback unchanged — **B** — ledger.
12. **IDEA: Two-writer audit on `live_guard.json`** — cron (flock-guarded) and `run_alerts --rearm` (subprocess, lock status unverified) can both write it; verify atomic write + shared lock, else the executor can read torn JSON on the guard path — **A** — ledger.
13. **IDEA: Guardian-liveness contracts for ALL `kind=state` files** — `stage_state.json` (354h) is safe only while its guardian lives; enumerate every valid-until-changed state file (`cashcarry_positions.json`, stage, kill files) and bind each to its guardian's cadence — **A** — folds into main proposal.
14. **IDEA: Silent-except sweep of the executor** — `_refresh_guard` swallows bare `Exception`; L1.40 names SILENT-EXCEPT as the desk's most expensive class (the $2,150 stranded-inventory instance); grep-audit `except.*:.*return\|pass` on money-path files specifically — **A** — ledger.
15. **IDEA: Unify the five producer-side registries into the contract registry** — five hand lists with five maintenance burdens and identical mtime logic; one measured surface, L1.12 deletion of the rest — **B** — folds into main proposal.
16. **IDEA: `.bak-20260716` files in scripts/ and libs/execution/** — dead weight on the import-graph surface, 15 days old, L1.12 ruthless-deletion candidates (verify unreferenced first) — **B** — ledger.
17. **IDEA: Blast-radius-ranked organ liveness** — re-sort `check_organ_liveness` output by consumer count from the contract registry so "size governor dead" never again ranks equal with "idle research seat" — **A** — folds into main proposal.
18. **IDEA: Stale-read telemetry as research data** — log every STALE-CONSUMED event with the decision it fed; over weeks this measures which decisions actually tolerate staleness (evidence to *loosen* contracts too — gate-optimality duty applies to freshness bars as much as validation bars) — **B** — ledger.
19. **IDEA: Funding-snapshot age contract at carry-selection time** — if the executor's symbol selection consumes any file-based funding snapshot (vs live fetch), it needs the same contract; unverified this run, one grep to settle — **B** — ledger (verify first).
20. **IDEA: Kill-file authority inversion test** — the freeze path assumes the guard writes the kill file, but a dead guard writes nothing; add a dead-man-style "guard must affirm aliveness or executor tightens" (inverse of current fail-open), mirroring the existing dead-man switch pattern one layer down — **S** — ledger.

Context remains, but substantiated seam from this run's reads is drained; next lines I would generate require fresh evidence: (a) whether `run_cadence.py`'s stage-gated firing mis-fires on the 354h stage file, (b) which of the 23 PROPOSE-state wiring scripts are freshness producers whose absence already breaks a contract, (c) whether the Holm snapshot consumer re-reads per-evaluation or caches per-day. The following run should resume generating there.

**Routing note (L1.39):** this is a hunter seat in a read-only run — the deep proposal + brainstorm lines route to the builder for `scripts/recommendations.py add` rows; none are dispositioned here. The guard-death page (#1/#20) is the highest-urgency partial: it protects the live book during launch week and is minutes of work.


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 400: Bad Request. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
