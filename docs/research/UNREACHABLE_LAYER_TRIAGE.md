# TRIAGE — the 48 unreachable modules (§9 complexity audit)

Measured by import-graph walk from every `scripts/` entry point, not by grep. 48 modules across
5 packages have **no path from any entry point**. Each gets a decision here; per §36(2), "no law"
must be a decision, never a default.

**A caveat that governs every row below:** unreachable proves only that nothing calls this code.
It says nothing about whether it *works*. No module here has been executed in this session. Every
WIRE decision therefore means "wire behind a self-test that proves it runs", never "assume it is
correct because it exists."

---

## Decisions

| Package | Mods | Decision | Reasoning |
|---|---|---|---|
| `libs/features` | 8 | **WIRE — first** | Contains the future-invariance leakage proof. Attacks 64% of the desk's historical failures (38% WRONG_TIMING + 26% DATA_QUALITY) by construction rather than heuristic. Bridged this session via `libs/features/causal_guard.py`; the registry/PIT modules follow once a screen needs versioned features. |
| `libs/monitoring` | 5 | **WIRE — second** | Durable metrics store + alerting. The desk currently has pager alerts but no durable metric time-series, so every "is this getting better?" question is answered from memory or ad-hoc JSON. Cheap, and it is the substrate the §6 efficiency ratios should read from instead of the commit-count proxy. |
| `libs/stage14_5` | 10 | **WIRE — third** | Concentration, correlation shock, crisis alpha, factor exposure, hedging, regime exposure. These are *portfolio risk* controls. Not needed at one live sleeve — but step 3 of the growth ladder gates on ≥3 orthogonal sleeves, and correlation shock is exactly the failure that makes "orthogonal" a lie under stress. Wire when sleeve count reaches 3, not before. |
| `libs/stage14` | 14 | **DEFER — gated on Gate 0** | Portfolio construction + allocation + attribution + capacity enforcement. Genuinely useful, genuinely premature: the desk is pre-Gate-0 with 12 of 12 forward slots idle. Constructing a portfolio from zero validated sleeves is ceremony. Revisit at Gate 0. |
| `libs/stage15` | 11 | **DEFER — overlaps live orchestration** | Research orchestrator, governance gate, kill switch, economic-mechanism engine. The cycle + cadence engine + `run_cadence` already orchestrate; a second orchestrator is a competing source of truth, which is worse than none. The **kill switch** and **economic-mechanism engine** are the two worth extracting individually rather than adopting the layer wholesale. |

**Net: 13 modules to wire now/next, 25 deferred with a named unlock condition, 10 conditional on sleeve count.**

---

## Why "defer" here is not the same as "ignore"

Each deferral has a **named unlock condition** — Gate 0 for `stage14`, sleeve-count ≥ 3 for
`stage14_5`, and extract-don't-adopt for `stage15`. That is the difference between a decision and
a default. `max_audit`'s `orphan-code` check will keep firing on all of them, which is correct:
the check should stay noisy until the condition is met or the code is retired on the record.

## What was explicitly NOT decided

Retirement. Nothing here is marked RETIRE, because retiring code requires proving nothing depends
on it *at runtime* — including dynamic imports, which a static import-graph walk cannot see. The
prior audit's near-miss (calling a live base layer "orphaned" from a one-hop grep) is the reason
that bar is set high. A retire decision needs a runtime-import trace, not a static one.

## The genuine risk of the WIRE decisions

Wiring unreachable code puts untested code on a live path. Mitigation, applied to `causal_guard`
already and required for the rest: every wired module ships with a `self_test()` that proves the
behaviour on synthetic data at import-time cost of zero, and is wired behind a fail-closed
assertion rather than a warning. A guard that warns and continues is the fail-open class this
codebase's own auditor prompt ranks first among its measured defects.
