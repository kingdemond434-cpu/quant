# CAPABILITY HUNT PROPOSALS 20260805 slot 5

LENS: STALE-CONSUMER -- find code reading an artifact without checking its age, so a frozen producer silently feeds yesterday's number into today's decision.

## A -- Claude family

Both sweeps are in. The second found a **higher-severity instance of the same missing capability** than my own, and it sharpens the mechanism. I verified its top claims directly rather than relaying them.

## Correction and upgrade to the deep proposal

**The worst instance is not stale evidence — it is *absent* evidence published as a measurement.** Verified by me just now:

- `data/ramp_state.json` **does not exist** (`ls` → no such file).
- `scripts/run_live_guard.py:167-168`: `state = _load(_RAMP, {})` → `current = float(state.get("size_fraction", ramp_gate.SIZE_STEPS[0]))` = **0.10, a hardcoded ladder constant** (`libs/execution/ramp_gate.py:28`).
- `run_live_guard.py:236`: the entire S1/Gate-0 promotion-evidence dict is `{}` from that same absent file.
- Stamp at `:272` is `"ts": datetime.now(UTC)`, **unconditional**.
- The published artifact renders this as `"ramp": {"size_fraction": 0.1, "why": "blocked by: a_cost_le_1_25x, b_live_sharpe…", "checks": {six keys, all false}}` — six checks presented as *evaluated* that were evaluated against an empty dict from a file that has never existed.
- Consumer: `run_cashcarry_executor.py:1487`, `read_fresh(max_age_h=0.25, min_rows=1)` → **FRESH**, and it sizes the book.

The scope boundary matters, so I'll state it precisely: *that the ramp is pinned at 0.10 with no producer* is *already known* — L1.45 names it in the constitution and `run_cost_identification.py` was built to produce those inputs. What is **new, and squarely in my lens**, is the consumer side: the absence is laundered into a confident, fresh-stamped measurement with six false-looking checks and passes a freshness contract, instead of reading `UNMEASURED`. L1.45 fixed *"nothing computes the input"*; nobody fixed *"the reader publishes a fabricated default as if computed."*

**So MECHANISM piece 1 upgrades.** Not just an evidence window — an `inputs` block per artifact: `[{path, age_h, status: READ | STALE | DEFAULTED | ABSENT}]`. `DEFAULTED` and `ABSENT` are the states that make a fresh stamp a lie, and they subsume the stale case. **Cost drops**: the fix template already exists in-repo — `scripts/check_ratchets.py:210-241` `_row()` carries `age_h`/`max_age_h` and degrades the *output's* verdict to `STALE`; `check_organ_liveness.py:158-185` emits `age_h` + `tolerance_h`. Three producers do this correctly; ~87 do not.

**Scale, measured:** 90 files write a `"generated"` key; **7** contain any input-provenance token, and 3 of those record *presence*, not age.

**One correction to the sweep, on my own check:** it flagged `check_replacement_rate.py:79-80` (missing `docs/graveyard.md` → `deaths = 0` → the complacent direction its own docstring names). `docs/graveyard.md` **exists** (64KB), and today's artifact reads `deaths_graveyard: 1`. That defect is **latent, not live** — real code path, not currently firing. Reporting it as live would have been wrong.

### Brainstorm, continued (27–37)

27. **`run_live_guard._ramp()` publishes a hardcoded ladder constant as a measurement** from an absent file, fresh-stamped, executor-consumed. Should read `UNMEASURED`, not `0.10`. — **S** — money path.
28. **`run_max_push._refresh()` makes every producer failure invisible**: `check=False`, `capture_output=True`, `except (OSError, TimeoutExpired): return`. A producer that crashes, exits non-zero, or blows the 300s timeout is silently skipped; `build()` reads whatever stale file is on disk and stamps the merged queue `generated: now`. Widest blast radius on the desk — this is the *daily work queue*. — **S** — ledger.
29. **`check_idle_cost.py:198` defaults `entries_allowed` to `True`** — an unreadable `live_guard.json` reads "entries allowed" and **erases the ladder clamp**, i.e. fails in the loosening direction, in the fence L1.51 built specifically to price clamps. — **S** — fence.
30. **`check_excitation.py:59-69` returns `[]` on unreadable forensics** and publishes `execution_denylist: []`, breaking its own docstring promise at `:65-67` that "the fence and the gate can never disagree about who is blocked." — **S** — fence.
31. **`check_conversion.py` age-checks nothing on the recommendation ledger**, and `run_max_push` weights `conversion_debt` at **0.95 — the highest leverage in the queue**. A frozen ledger publishes stale `backlog`/`past_due` under a fresh stamp. — **A** — fence.
32. **`check_calibration.py`: unreadable and genuinely-empty forecast logs are indistinguishable** (`_load()` → `{"forecasts": {}}` → `UNFORECASTING`). L1.29's own fence cannot tell "no forecasts" from "cannot read forecasts." — **A** — fence.
33. **`check_utilisation._forward_queue_depth()` under-counts silently**: two `except: pass` blocks, then `measured = bool(sources)` — one of two staging registers failing still reports `measured=True` with a low number. Under-reported utilisation is an L1.28a idleness *false alarm*, which is how a fence gets ignored. — **A** — fence.
34. **The stamp-key zoo**: `generated` / `ts` / `checked` / `measured` / `updated` — five conventions across decision artifacts, and `_age_of` recognises exactly one. This is the mechanical root of item 1 and of 4-of-5 contracts resolving from mtime. Declare one key, fence the rest. — **S** — `fresh.py` + fence.
35. **`run_cost_identification.py:353` stamps `_generated` *into* the `ramp_evidence` payload** merged into `ramp_state.json` — the producer's run time presented as the currency of the fills behind `cost_ratio`. The ramp steps the book up on that. — **A** — money path.
36. **Generalise: every `.get(key, default)` on a decision path is an unrecorded assumption.** The defaults found are all in the loosening direction (`entries_allowed=True`, `frac=1.0`, `denylist=[]`, `size_fraction=0.10`-as-measured). Static-sweep decision-path defaults and require each to declare its degrade direction, the way `read_fresh` already requires `mode=`. — **S** — new fence.
37. **Rank the fences by which direction they fail.** L1.43 classifies fences as FIRED/QUIET/NEVER-RUN; nothing classifies them as fail-open vs fail-closed. Four of the five above fail *open*. A quiet fail-open fence is indistinguishable from a healthy desk — which is the whole class. — **A** — fence.

Next run resumes at: sweeping decision-path `.get(k, default)` sites for degrade direction (item 36), and checking whether `web/` artifacts consumed by the pager and the public dashboards share the same stamp-key and default-direction defects.


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 400: Bad Request. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
