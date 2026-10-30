# Gateway: refuse a placement on one symbol's stale quote (MONEY PATH, desktop pass)

Owner: the Live control room thread. Target: the desktop "Growth allocator overhaul" session.
Base: LIVE 67946bd5a. The recovery scorecard grades `stale_quote` FAIL until this lands, from the drill fault `stale_tick` in `libs/tiers/gateway_drill.py`.

## The defect

The pass-level feed check in `desks/mt5/mt5desk/gateway.py` (around line 3998, `age_sec > 1800`) reads ONE reference tick. `place_bracket` (around line 1220) reads `_t = mt5.symbol_info_tick(symbol)` for the freeze-band check and never asks how old it is. A symbol whose feed stopped while the terminal stays connected and the reference symbol keeps ticking is therefore traded at its last price.

Measured in the sandbox drill: with `symbol_info_tick` returning a quote stamped two hours old and the terminal connected, `place_bracket` sent both legs (`NO_SEND_STALE: 2 order(s) sent on a quote two hours old`).

## The fix (read only, no new sends)

1. Add `STALE_QUOTE_S = 300` beside the other gateway constants.
2. In `place_bracket`, right after `_t = mt5.symbol_info_tick(symbol)`:
   - Measure the age against the pass's own reference tick, not the wall clock, so the broker's UTC offset cancels out. Store the reference as `st["placement_pass"]` (it is set from `tnow` in the main pass). In `place_bracket` read `ref = pd.Timestamp(st.get("placement_pass"))` when present, else `datetime.now(tz=UTC)`.
   - Compute `age = (ref - pd.Timestamp(_t.time, unit="s", tz="UTC")).total_seconds()`.
   - If `_t is None` or `age > STALE_QUOTE_S`:
     - log `NOT SENT [{sleeve}] stale quote {symbol} age={age:.0f}s`;
     - call `_record_decision(..., taken=False, reason="stale_quote", detail=f"age {age:.0f}s")` once per side;
     - return `{"ok": False, "stage": "stale_quote", "why": ...}` before any `order_send`.
3. Do not change open-position management: closes and stop moves still run on a stale quote, because refusing to manage exposure is worse than managing it on the last price.

## Proof

`python -c "from libs.tiers import gateway_drill as g; print(g.run_fault('stale_tick'))"` must show `breaches: []`, and `healthy` must still send two legs. The scorecard row `stale_quote` then reads PASS on the box's next hourly pass.
