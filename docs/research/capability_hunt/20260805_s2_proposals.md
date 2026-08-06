# CAPABILITY HUNT PROPOSALS 20260805 slot 2

LENS: UNMEASURED-REPORTED-AS-OK -- find a check or metric that returns a PASS/zero when its input was absent. Unmeasured must never read as fine (L1.28a); both fences built today shipped with this bug in their first run.

## A -- Claude family

All three sweeps are back. **The deep proposal is stronger than I argued it: the same defect is in all three of the desk's liveness instruments, independently found.**

```
1. max_audit.check_organs:388      8 organs → 1 shared artifact; mtime written by git; `continue` = silent health   [mine]
2. check_organ_liveness:168-173    age = min(fresh) over SURVIVING artifacts — one live file hides every absent
                                   sibling in the same block → FRESH → OK. Feeds capability_ratchet ops_autonomy.
3. check_exploration:131-138       n = len(_FAMILY); if n == 0, `len(fresh) < n/2` is `0 < 0` = False → status OK,
                                   n_organs 0. _FAMILY is mutated at import from a dynamically exec'd module with
                                   `except: _secondary = {}` — and it is already missing blindrediscovery (5 of 6).
```

Not one bug — the liveness layer. Every instrument certifies an organ from evidence the organ does not own, and each fails to a green verdict. That is the capability gap, and the triple is the argument for building it once, centrally, rather than patching three files.

Also confirmed by hand: `screen_admission.py:296` `g in gates` — an absent structural gate cannot appear in `blocked_list`, so it cannot block; `break_even_win_rate` is declared structural at `:70` and **written by nothing anywhere in the repo** (grep returns only its own definition, the tuple, and a label table) — a structural gate that has never once evaluated. And `measure_admission_power.py:143` uses `all(gates.get(g, True) …)`, so the harness that produced the "structural gates pass 73–100% of true alphas" evidence *reproduces the bug it would have caught*. `run_alerts.py:297` reads `generated` from `live_guard.json`; the guard writes `ts` (`run_live_guard.py:297`) — measured live: `lg_age` = **56.6 years**, fires every run, feeds the derisk ladder that froze the book on 2026-07-31, while a genuinely dead guard is indistinguishable from the permanent alarm.

## BRAINSTORM (continued)

**Money path — highest dollars at risk**
- Risk-rail block wrapped in `_safe()` (`run_cashcarry_executor.py:1077`, `__exit__ → return True`): one signed-endpoint raise deletes ruin switch + DD breaker + exposure + concentration + fee-burn for the tick, `risk=None`, `cands` uncleared → **new carries open**, and `web/index.html:338` renders `(rk&&rk.action)||"ok"` as green "OK". The file's own `:651` comment says this. — **S** — ledger, money path
- `_reconcile` returns `[]` on venue read failure (`:693`), which is byte-identical to "already hedged" — the delta-neutrality healer runs first each tick as "survival #1". — **S** — ledger
- ADL check: `force_orders` returns `{}` on error (`binance_live.py:293`), so `sym in forced` is False and the code **re-shorts into the squeeze** — the exact action the `:680` review comment forbids, on the endpoint most likely rate-limited during an ADL. — **S** — ledger
- Dead-man switch: `combined_equity` → `None` on missing keys makes `should_fire` return False forever, *and* the stale-feed pager is gated on `eq is not None`, so the blindness disables its own alarm — while the heartbeat keeps writing and `watchdog.py:34` reports alive. Armedness ≠ liveness, R0053 all over again. — **S** — ledger
- `_mark`: `funding` and `fut_commission` get None-on-failure; `fut_pnl` (declared one line above) does not → publishes `fut_leg_net: 0.00`, and `reconcile_futures_leg`'s UNMEASURED guard cannot fire, emitting PHANTOM instead. — **S** — ledger
- Protective stops: `state["protective_stops"] = plan` written **outside** the `_safe()` that swallows `place_stop_market` → state records stops that were never placed, on the host-death rail. — **S** — ledger
- `risk_controls.py:301`: absent inception clamps `start` to `1e-9` → `dd_start` hugely positive (ruin rail unbreachable) and `dd_peak = 0.0` published as "at high-water mark". — **S** — ledger
- `run_live_combined.py:208`: an unreadable `crypto_shadow.json` flips `m_start` 15000→10000, **wipes the equity curve**, republishes `max_dd_pct 0.00`. — **A**
- `live_book.py:163`: `funding_measured=bool(cc.get("funding_measured", True))` — the field whose entire purpose is distinguishing absence from zero **defaults to measured**. — **A**

**Validation — closest to promoting fiction to capital**
- `screen_admission.admit`: `g in gates` + `capacity`/`sample_adequacy` omitted-when-unmeasured (`autodiscovery/validation.py:783,810`) + `n_bars is None` → note, not block. `MIN_ADMISSION_BARS=1460` bypassed by omitting a field. Fix template already in-repo: `check_promotion_gate` tri-state, `promotion_gate.py:62` `bool(x is True)`. — **S**
- `promote_moat_survivors.py:249`: missing screen artifact → `_suspect({})` → empty set → SUSPECT-LOOKAHEAD can never fire; *plus* key mismatch (`split("@")` on build, not on lookup) makes it a no-op even when healthy. — **S**
- `run_leakage_test`: `_sample_points` returns `[]` when `min_periods >= n` → `n_leaked == 0` → **"no future leakage"**, and `assert_causal` ("fail closed by design") passes it. Same shape as the known OHLC bug, on the length axis. — **S**
- `leakage_detector.py:105`: bare `except Exception` around the *decisive* proof → `"unavailable"` in notes, no flag, verdict **CLEAN**. — **S**
- `lookahead_audit.audit_many`: raising indicators go to `errored`, are **removed from `results`**, then `f"all {len(results)} audited indicators are causal"` — denominator deletion in a summary line. — **A**
- `gauntlet.py:203`: no lockbox → no stage appended → `all([])` → the final OOS confirmation is vacuously PASS; `:102` `ledger=None` → `n_trials=2` → near-zero deflation by *default constructor*; `:150` `1e-6` variance sentinel makes DSR collapse to PSR against a zero benchmark while keeping the name "deflated_sharpe". — **S**
- `stress_costs.py:63`: an all-zero cost vector "survives 3× stress" identically at BASE/X2/X3/X5. Pair with `generators.net_returns(cost=0.0003)` flat 3bps + `run_real_campaign.py:221` declaring `cost_basis: "net"`, which suppresses `GROSS_TURNOVER_PENALTY` — a constant sold as a measurement. — **S**
- `slot_admission.py:170` / `paper_sleeves.py:159,245`: `decontam_passed` **defaults True**, so an unmeasured cell out-ranks a measured-contaminated one for a scarce forward slot, and `as_dict()` republishes the fabricated True as a measurement. — **S**
- `fusion_search.py:397`: `pf.get("pass", True)` against a callee that emits `verdict`, not `pass` — every REJECT discarded. Latent until someone wires the obvious callee, then silent. — **A**
- `variation_blocker.py:99`: missing ledger → `Verdict(True, "novel mechanism fingerprint")` — a *reason string asserting a measurement that never happened*; same in `hypothesis_novelty` (`nearest_sim 0.0 → novelty 1.0`). — **A**
- `revalidation.py:135`: empty splits → `oos_sharpe 0.0 >= min 0.0` True. `autodiscovery/validation.py:363`: CPCV failure falls through to a contiguous split its own docstring calls "systematically optimistic". — **A**

**Governance fences**
- `check_enforcement_execution.py:266,274`: unparseable module and unrecognised citation both publish **EXECUTED ("conservative pass")** — a law whose only enforcer is a broken file reads fully enforced, exit 0. Laws with an empty cite list never enter `per_law` at all. — **S**
- `check_mypy_ratchet.py:89`: uncheckable files **popped from the denominator** → mypy uninstalled ⇒ `total_errors: 0`, `n_files_checked: 0`, no regressions, exit 0; and a file that becomes uncheckable can never regress again. Feeds `check_ratchets` and `capability_ratchet.engineering_standard`. — **S**
- `check_fence_yield.py:131`: a deleted artifact with history reads **QUIET "only ever OK"**; `doc.get(key,"?")` turns schema drift into a permanent non-firing verdict — live proof: `_FENCES` reads `utilisation.status`, which `check_utilisation` **never emits** (`status = None`), so it only reads FIRED from a hardcoded seed. — **S**
- `check_scheduler_manifest.py:214`: unreadable live crontab → no diff → `exit_code 0` → `verdict OK`; the JSON consumer (`capability_ratchet`) reads `readable` correctly, but `run_law_gate.py:77`, `daily_research_cycle.py:119` and `finish_setup.sh:96` consume the **exit code**. — **S**
- `check_utilisation.py:548`: `rep["unmeasured"]` is built and **never consulted** in the exit expression; `:70` unmeasured → `utilisation 0.0`; `:522` `mean_utilisation` blends unmeasured zeros with real zeros; `:243` invents `limit 1.0` for an absent log dir. — **A**
- `check_readiness.py:25`: the fence **creates and migrates its own missing database**, then `verify_audit_chain` returns True over an empty `audit_log` (loop body is the only failure path) → prints READY on a fresh box. — **A**
- `check_coverage_floors.py:128`: `--update` writes the record and returns 0 **before** the breach block — an update run converts a real money-path coverage breach into exit 0. — **A**
- `check_funding_capture.py:161`: malformed rows `continue` before `n += 1` → `n=0` → `mismark_frac 0.0` → status OK, detail "0 closes differenced against venue truth", exit 0, while the UNREADABLE breach is recorded and ignored. — **A**
- `check_strategy_breadth.py:110`: `--surfaces-only` writes `state: NOT-RUN` but `status: OK` **and persists it**, so later readers see a green breadth verdict from a run that did not measure breadth. — **A**
- `check_timidity_language.py:319`: `prompt_surfaces_scanned` is published but **not in the failure expression** — an empty surface list passes vacuously; `audit_doctrine`'s `present: False` is never read. — **A**
- `check_sizing_derivation.py:134`: only scans `tree.body`, so refactoring money-path constants into a dataclass/dict/function body removes them from scope and reports OK over zero constants. — **A**
- `check_llm_routing.py`: **no failing path at all** (`return 0` unconditionally) — an empty scan is indistinguishable from full compliance. — **B**
- `check_calendar_gates.py:116`: prints CLEAN with no `n_files_scanned` — cannot distinguish 900 files clean from `rglob` matching nothing. — **B**
- `check_return_targeting.py:126`: `errors="ignore"` means a corrupt governed surface never lands in `unreadable` and contributes zero hits toward OK. — **B**

**New, not from the sweeps**
- **The `_safe()` audit** — one context manager whose `__exit__` returns True wraps most of the executor. Enumerate every block it guards and classify each as *may-skip* vs *must-not-skip*; the rails are all in the second class. A single `_safe(critical=True)` variant that re-raises is a ~10-line change with the largest measured blast radius on this list. — **S**
- **Publish `n_scanned` on every fence, universally** — the common root of #7/#11/#14/#16 above is that a CLEAN/OK verdict is printed without its denominator. Make `fence_exit` refuse a passing status when the scanned count is zero or undeclared. One helper, closes ~six findings at once. — **S**
- **Key-contract test between every writer/reader pair** — `run_alerts` reads `generated`, guard writes `ts`; `fusion_search` reads `pass`, pre_filter writes `verdict`; `promote_moat_survivors` builds keys stripped and looks them up unstripped. Three independent instances of the same class in one sweep. A schema round-trip test per artifact catches all of them. — **S**
- **`.get(key, <permissive>)` census** — grep every dict `.get` whose default is the *passing* value (`True`, `0.0` for a cost, `"ok"`). The correct default for an absent measurement is always the failing one or `None`. Mechanical, high yield. — **S**
- **`all()` / `min()` / `max()` over possibly-empty iterables** — `all([])` is True, and `min(fresh)` masks siblings. A lint rule (`ruff` custom or a repo check) forbidding these without an explicit empty-case branch. — **A**
- **Welded-gate scan of the *validation* layer** — L1.43 turned this logic on governance fences; run it on the screening gates. `break_even_win_rate` (never once evaluated) is a 0%-fire gate; `capacity` fires only from one call site. The gate-optimality duty demands the accept/reject histogram per gate, and it does not exist for `admit()`. — **S**
- **Re-run `measure_admission_power` after fixing `:143`** — the desk's stated evidence for its own screen's power is contaminated. Until re-measured, every "the gate is calibrated" claim is unsupported. — **S**
- **Alert false-positive rate as a first-class metric** — `live_guard_dead` has fired every run for an unknown span and already froze the book once. Measure per-alert fire-rate; an alert firing ~100% carries zero information and is a welded gate that *actively costs money* through the derisk ladder. — **S**
- **Ladder inputs must be alert-*quality*-weighted** — `unacked_since` escalates on page age regardless of whether the page was ever true. An escalation path fed by an unvalidated detector converts a monitoring bug into a flatten. — **S**
- **Blindrediscovery has produced nothing observable and owes a §33 disposition** — it is scheduled by both cron (4×/wk) and systemd (monthly), which disagree; and it is the one L1.32 organ nothing measures. — **A**

Next to generate, resuming here: the "what does absence look like?" meter audit (L1.51's generalisation — every trade-driven meter reads flat-book and healthy-book identically, so a desk that stops trading generates no evidence of having stopped); and the inverse-lens pass — fences that fire ~100% rather than ~0%, of which `live_guard_dead` is now a confirmed member and which nothing on this desk currently counts.


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 400: Bad Request. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
