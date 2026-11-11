# Gateway: placement_pass is broker time labelled UTC; the stale-tick check is 3h blind (MONEY PATH, desktop pass)

Owner: the Live control room thread (ledger row L3). Target: the desktop "Growth allocator overhaul" session.
Base: LIVE eeda61a17. Readers are already fixed in cloud PR #328 (`libs/ops/gateway_clock.py`); this is the source.

## The defect

`desks/mt5/mt5desk/gateway.py` `main` (around line 4130):

```python
tnow = pd.Timestamp(tick.time, unit="s", tz="UTC")
...
st["placement_pass"] = tnow.isoformat()
age_sec = (datetime.now(tz=UTC) - tnow).total_seconds()
if age_sec > 1800: ... idle: tick stale
```

MetaTrader's `tick.time` counts the BROKER's wall clock (the venue clock is New York wall time + 7h: +3 while New York is on daylight time, +2 from 2026-11-01, NOT the EU date of 10-25), not UTC. So:

1. `placement_pass` carries broker time under `+00:00`. Measured: at 15:35 UTC the published file read `2026-10-13T18:35:02+00:00`, with `last_reconcile` (real UTC) at `15:34:14`.
2. The stale-tick gate subtracts a broker stamp from real UTC, so the age reads 3h too YOUNG. A reference tick up to about 3.5h old passes as fresh and the pass trades. This is the likely root of the earlier "gateway trades a 2h-stale quote" finding.

`today`, `hour`, `day_key` and `CLOSE_HOUR` are deliberately in broker time, matching the bars and the certified session windows. **Do not change those.**

## The fix

In `main`, right after `tnow` is built:

```python
from libs.regime.session_clock import server_to_utc, utc_offset_h   # the desk's one venue-clock rule
tick_utc = server_to_utc([tnow.tz_localize(None)])[0].tz_localize("UTC")
st["placement_pass"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
st["placement_pass_clock"] = "utc"
st["placement_tick_broker"] = tnow.tz_localize(None).isoformat()   # naive: broker wall clock
st["broker_utc_offset_h"] = utc_offset_h()
```

Do NOT use `session_phase.broker_utc_offset_h()`: it answers 0 on every host (`h1_source` pins the offset to 0.0 and `data/broker_clock.json` records 0), so subtracting it changes nothing. `session_clock` is a calendar rule measured on the desk's own bars and needs no live terminal.

Then replace the stale-tick age with `age_sec = (datetime.now(tz=UTC) - tick_utc).total_seconds()`.

`note_placement` only compares `placement_pass` for equality within a pass, and one value per pass still holds.

## Amends `gateway_stale_quote_gate.md`, step 2

The per-symbol stale-quote reference becomes `ref = pd.Timestamp(st["placement_tick_broker"])` against `pd.Timestamp(_t.time, unit="s")`. Both are naive broker clock, so the offset still cancels. It must NOT read `placement_pass`, which is now real UTC.

## Proof

- Pass-level stale check: `python -c "from libs.tiers import gateway_drill as g; print(g.run_fault('stale_tick'))"` must show `breaches: []`, and `healthy` must still send two legs.
- Readers: after one pass, `python -c "import json; d=json.load(open('desks/mt5/data/gateway_state.json')); print(d['placement_pass'], d['placement_pass_clock'], d['last_reconcile'])"` shows `placement_pass` within a minute of `last_reconcile`.
- `tests/ops/test_gateway_clock.py` (PR #328) already accepts the `utc` mark.
