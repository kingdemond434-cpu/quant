# Gap #32 — Guarded Resize-Up (capital-utilization) — SPEC, TESTED, QUEUED FOR POST-GATE-0

**Status:** implementation written + unit-tested (7 tests) + full execution suite green on
2026-07-19, then **reverted from live to honor the freeze** (operator instruction 2026-07-19:
"Queue implementation for post-Gate-0"). Re-apply verbatim at Gate-0. Do NOT deploy during the
freeze — this is a structural change to the ruin-incident sizing function and must not perturb the
calibration rows Gate 0 depends on.

## Problem
`_rebalance` sizes opens from FREE capital only and never resizes a held carry
(`if sym in pos: continue`). A carry opened during a low-free-capital window (e.g. while the
contaminated leverage optimizer capped the book) stays frozen small forever unless it rotates out.
On 2026-07-18 this left the book at ~20-25% of the authorized $4,500 with 8 carries frozen at ~$29.
The `_dynamic_capital` quarantine (committed) removed the hard cap but does NOT resize held carries,
so the book only creeps up via rotation and plateaus well below target.

## Fix (the SAFE direction only)
Top each held carry UP toward its funding-weighted share of the FULL capital, through the EXISTING
guarded open path. Invariants (all unit-tested):
1. **Never levers past `capital`** — aggregate adds bounded by free headroom (`capital - deployed`).
2. **Concentration rail intact** — each name held under `0.35 * capital` (the 2026-07-13 cap).
3. **Never sizes DOWN** — only positive shortfalls; closes remain the target-set's job (no churn).
4. **Hysteresis** — only material shortfalls (`>= max(0.02*capital, $20)`) top up.
5. **Thin-book depth guard** — each increment checked against `_DEPTH_MULT` on both legs.
6. **Risk-rail aware** — skipped entirely while a risk rail is flattening/pausing.

## Implementation (re-apply at Gate-0)

Pure, unit-testable planner inserted after `_alloc`:

```python
def _topup_plan(pos: dict[str, dict], capital: float, *, cap_frac: float = 0.35,
                min_frac: float = 0.02, min_usd: float = 20.0) -> dict[str, float]:
    if not pos:
        return {}
    funded = [(sym, max(float(p.get("funding", 0.0)), 0.0)) for sym, p in pos.items()]
    tgt = _alloc(funded, capital, cap_frac=cap_frac)
    deployed = sum(float(p["spot_qty"]) * float(p["spot_cost"]) for p in pos.values())
    room = max(0.0, capital - deployed)
    floor = max(min_frac * capital, min_usd)
    plan: dict[str, float] = {}
    for sym in sorted(pos, key=lambda k: max(float(pos[k].get("funding", 0.0)), 0.0), reverse=True):
        if room <= 0.0:
            break
        cur = float(pos[sym]["spot_qty"]) * float(pos[sym]["spot_cost"])
        add = min(min(tgt.get(sym, 0.0), cap_frac * capital) - cur, room)
        if add < floor:
            continue
        plan[sym] = add
        room -= add
    return plan
```

Top-up pass inserted at the end of `_rebalance`'s open loop (before `state["positions"] = pos`),
gated on `risk is None or risk.action == "none"`, iterating `_topup_plan(pos, capital)`, rounding
via `_round`, checking `min_qty` + the `_DEPTH_MULT` depth guard on `qty*px`, then `_execute_pair(
sym, qty, "BUY", "SELL")`, blending the cost basis (`spot_cost`/`perp_entry` weighted-average),
updating `spot_qty`/`perp_qty`, logging an `event: "topup"` trade. (Full diff preserved in
`data/patches/gap32_topup.patch` if generated; otherwise reconstruct from this spec — it is exact.)

## Tests (tests/execution/test_topup_plan.py — re-add at Gate-0)
`empty_book_no_plan`, `tops_up_undersized_carries`, `never_levers_past_capital`,
`never_sizes_down_when_over_target`, `hysteresis_skips_immaterial_shortfall`,
`concentration_cap_with_few_names`, `converges_after_repeated_application`. All passed 2026-07-19;
full `tests/execution/` (85 tests) green with the change applied.

## Gate-0 re-apply checklist
1. Re-apply the two insertions above; re-add the test file.
2. `py_compile` + `ruff` + `pytest tests/execution/` green.
3. Controlled restart (wait out the 150s single-instance heartbeat guard).
4. Verify the book climbs toward ~$4,500 at ~$450/carry, no concentration breach, no deadman event.
5. Note: full deployment matters at LIVE capital and is governed by proven-edge shrunk-Kelly — do
   not deploy 100% into an unvalidated/negative-Sharpe carry just because capital is authorized.
