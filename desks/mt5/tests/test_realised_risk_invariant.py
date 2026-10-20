"""The realised-risk-in-EUR invariant: an order risks what the allocator intended, no more.

INTENDED = the sleeve's resolved fraction x leg_mult x macro_mult x equity (the modifiers' upside
is intent and is never clipped); REALISED = final lot x stop distance x EUR per price unit.
Pre-order: over 1.10x is floored to the venue step, below volume_min refused, unmeasurable
refused. Post-fill: over 1.5x at the fill price and real stop halts THAT sleeve's new entries.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _path in (str(_DESK), str(_DESK.parent.parent), str(Path(__file__).resolve().parent)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import mt5desk  # noqa: E402
import test_gateway_adapter as adapter  # noqa: E402
from mt5desk import risk_intent as ri  # noqa: E402

_UNIT = 1.0 / 0.00001          # EUR per 1.0 of price per lot on the harness symbol


# ------------------------------------------------------------------------- pure arithmetic
def test_a_two_step_rounding_overshoot_is_floored_to_the_largest_step_under_the_bound():
    # 1% of 1000 EUR = 10 EUR intended; 100 EUR per lot at this stop -> 0.10 lot is exact.
    # Two steps of rounding up (0.12 = 12 EUR, 1.2x) is floored to 0.11 (11 EUR = 1.10x).
    out = ri.enforce(0.12, 0.01, 1000.0, 0.001, 100_000.0, 0.01, 0.01)
    assert out["ok"] and out["floored"]
    assert out["lot"] == pytest.approx(0.11)
    assert out["realised_eur"] <= ri.PRE_TOL * out["intended_eur"] + 1e-9
    assert out["pre_lot"] == pytest.approx(0.12)


def test_one_step_inside_the_tolerance_is_left_exactly_as_resolved():
    out = ri.enforce(0.105, 0.01, 1000.0, 0.001, 100_000.0, 0.005, 0.01)
    assert out["ok"] and not out["floored"] and out["lot"] == pytest.approx(0.105)


def test_min_lot_above_intent_is_refused_never_lifted():
    # 0.5 EUR intended; the 0.01 minimum risks 1 EUR (2x) and cannot be sized down.
    out = ri.enforce(0.01, 0.0005, 1000.0, 0.001, 100_000.0, 0.01, 0.01)
    assert not out["ok"] and out["stage"] == "risk_intent" and out["lot"] == 0.0
    assert "never lifted" in out["why"]


def test_under_the_revert_switch_the_minimum_lift_stands_and_is_named():
    out = ri.enforce(0.01, 0.0005, 1000.0, 0.001, 100_000.0, 0.01, 0.01, sovereign=False)
    assert out["ok"] and out["lot"] == pytest.approx(0.01)


@pytest.mark.parametrize("field,value", [
    ("dist", float("nan")), ("dist", 0.0), ("unit", float("inf")), ("vstep", None),
    ("vmin", -0.01), ("equity", 0.0), ("frac", float("nan")),
])
def test_unmeasurable_inputs_raise_and_never_pass_silently(field, value):
    args = {"lot": 0.1, "frac": 0.01, "equity": 1000.0, "dist": 0.001, "unit": 100_000.0,
            "vstep": 0.01, "vmin": 0.01}
    args[field] = value
    with pytest.raises(ri.Unmeasured):
        ri.enforce(args["lot"], args["frac"], args["equity"], args["dist"], args["unit"],
                   args["vstep"], args["vmin"])


def test_a_conversion_that_raises_is_unmeasured_on_the_venue_path():
    def boom() -> float:
        raise RuntimeError("tick value unreadable")
    with pytest.raises(ri.Unmeasured):
        ri.enforce_on_venue(0.1, 0.01, 1000.0, 0.001,
                            SimpleNamespace(volume_step=0.01, volume_min=0.01), boom)


def test_fill_risk_is_priced_from_the_fill_to_the_real_stop():
    assert ri.fill_risk_eur(0.1, 1.1100, 1.1050, 1, _UNIT) == pytest.approx(50.0)
    assert ri.fill_risk_eur(0.1, 1.1000, 1.1050, -1, _UNIT) == pytest.approx(50.0)
    assert ri.fill_risk_eur(0.1, 1.1100, 1.1150, 1, _UNIT) == 0.0   # stop in profit
    row = ri.measure_fill(sleeve="a", symbol="EURUSD", side=1, volume=0.1, fill_price=1.11,
                          sl=0.0, unit=_UNIT, intended_eur=50.0, lane="family_market")
    assert row["status"] == "UNMEASURED" and row["breach"] is False


# ---------------------------------------------------------------------- the family resolver
def _resolve(tmp_path, monkeypatch, *, macro=1.0, fraction=0.03, equity=1000.0, info=None):
    rows = adapter._rows()
    venue = adapter._fake_mt5(rows)
    sym = info or SimpleNamespace(volume_min=0.01, volume_step=0.01, volume_max=100.0,
                                  trade_tick_size=0.00001, trade_tick_value=1.0)
    venue.symbol_info = lambda symbol: sym
    ns = adapter._family_ns(tmp_path, venue, monkeypatch, armed_file=False,
                            sig_hour=adapter._sig_hour(rows))
    ns["promoted_lot"] = adapter.dc.promoted_lot
    monkeypatch.setattr(adapter.dc, "allocator_sovereign", lambda: True)
    fake_leg = SimpleNamespace(multiplier=lambda *a, **k: (1.0, "neutral"),
                               already_held=lambda *a, **k: 0)
    fake_macro = SimpleNamespace(multiplier=lambda *a, **k: (macro, "synthetic"))
    for name, module in (("leg_balance", fake_leg), ("macro_view", fake_macro)):
        monkeypatch.setitem(sys.modules, f"mt5desk.{name}", module)
        monkeypatch.setattr(mt5desk, name, module, raising=False)
    sleeve = adapter._sleeve(risk_frac=fraction, sized_by="allocator_book")
    return ns["resolve_family_order"]({"armed": False}, sleeve, equity)


def test_the_modifiers_upside_is_intent_and_is_not_clipped(tmp_path, monkeypatch):
    plain = _resolve(tmp_path, monkeypatch, macro=1.0)
    boosted = _resolve(tmp_path, monkeypatch, macro=1.4)
    assert plain["ok"] and boosted["ok"]
    assert boosted["intended_eur"] == pytest.approx(1.4 * plain["intended_eur"])
    assert boosted["intended_eur"] == pytest.approx(0.03 * 1.4 * 1000.0)
    assert not boosted["risk_intent_floored"]
    assert boosted["lot"] > plain["lot"], "the boost must reach the venue"
    assert boosted["realised_eur"] > plain["intended_eur"], "risk above the un-boosted intent"
    assert boosted["realised_eur"] <= ri.PRE_TOL * boosted["intended_eur"] + 1e-9


def test_a_damped_order_lifted_to_the_minimum_is_refused_by_the_intent(tmp_path, monkeypatch):
    # 200 EUR x 3% -> 0.01 lot; macro 0.3 damps to 0.003, which the leg block lifts to the 0.01
    # minimum. That minimum risks ~3x the damped intent: refused, never sent at the floor.
    out = _resolve(tmp_path, monkeypatch, macro=0.3, equity=200.0)
    assert not out["ok"] and out["stage"] == "risk_intent"
    assert out["mark"] is True
    assert out["realised_eur"] > ri.PRE_TOL * out["intended_eur"]


def test_a_symbol_that_does_not_state_its_step_refuses_by_name(tmp_path, monkeypatch):
    info = SimpleNamespace(volume_min=0.01, volume_max=100.0, trade_tick_size=0.00001,
                           trade_tick_value=1.0)                       # no volume_step
    out = _resolve(tmp_path, monkeypatch, info=info)
    assert not out["ok"] and out["stage"] == "risk_intent"
    assert "unmeasured" in out["why"] and "volume_step" in out["why"]
    assert out["mark"] is False


# --------------------------------------------------------------------------- post-fill halt
def _two_sleeve_pass(tmp_path, monkeypatch, *, breach_symbol: str):
    rows = adapter._rows()
    venue = adapter._fake_mt5(rows)
    venue.symbol_info = lambda symbol: SimpleNamespace(
        volume_min=0.01, volume_step=0.01, volume_max=100.0,
        trade_tick_size=0.00001, trade_tick_value=1.0)

    def send(req):
        venue.sent.append(req)
        # A fill far above the quote on one symbol: its stop is ~3x further than planned.
        px = 1.1210 if req["symbol"] == breach_symbol else 1.1103
        return SimpleNamespace(retcode=10009, order=9, deal=77, comment="done", price=px,
                               volume=req["volume"])
    venue.order_send = send
    ns = adapter._family_ns(tmp_path, venue, monkeypatch, armed_file=True,
                            sig_hour=adapter._sig_hour(rows))
    ns["RISK_FILLS"] = tmp_path / "fills.jsonl"
    ns["RISK_BREACHES"] = tmp_path / "breaches.jsonl"
    sleeves = [adapter._sleeve(), adapter._sleeve(name="gbpusd_fam", symbol="GBPUSD")]
    st: dict = {"armed": True}
    adapter._run_family(ns, st, sleeves, 10_000.0)
    return ns, venue, st, sleeves


def test_a_2x_post_fill_breach_halts_only_that_sleeve_and_closes_nothing(tmp_path, monkeypatch):
    ns, venue, st, sleeves = _two_sleeve_pass(tmp_path, monkeypatch, breach_symbol="EURUSD")
    assert len(venue.sent) == 2
    assert set(st.get("risk_halt") or {}) == {adapter._NAME}
    halt = st["risk_halt"][adapter._NAME]
    assert halt["ratio"] > 2.0
    assert ns["_closes"] == [], "a breach never closes the position"
    fills = [json.loads(x) for x in (tmp_path / "fills.jsonl").read_text().splitlines()]
    breaches = [json.loads(x) for x in (tmp_path / "breaches.jsonl").read_text().splitlines()]
    assert len(fills) == 2 and {f["sleeve"] for f in fills} == {adapter._NAME, "gbpusd_fam"}
    assert [b["sleeve"] for b in breaches] == [adapter._NAME]
    assert all(f["status"] == "MEASURED" for f in fills)
    # The next signal: the halted sleeve is refused, the other sleeve resolves as normal.
    for s in sleeves:
        st["generic"][s["name"]].pop("last_signal_bar", None)
    halted = ns["resolve_family_order"](st, sleeves[0], 10_000.0)
    other = ns["resolve_family_order"](st, sleeves[1], 10_000.0)
    assert halted["stage"] == "risk_halt" and not halted["ok"]
    assert other["ok"], other


def test_a_clean_fill_halts_nothing(tmp_path, monkeypatch):
    _, venue, st, _ = _two_sleeve_pass(tmp_path, monkeypatch, breach_symbol="NONE")
    assert len(venue.sent) == 2 and "risk_halt" not in st
    assert not (tmp_path / "breaches.jsonl").exists()


def _halted_state() -> dict:
    return {"risk_halt": {"a": {"breach_id": "a:1:t", "symbol": "EURUSD",
                                "at": "2026-10-20T12:00:00+00:00",
                                "intended_eur": 50.0, "ratio": 2.4}}}


def test_an_acknowledged_breach_lifts_the_halt(tmp_path):
    st = _halted_state()
    ack = tmp_path / "ack.json"
    ack.write_text(json.dumps({"acknowledged": ["a:1:t"]}), "utf-8")
    notes = ri.review_halts(st, ri.read_acks(ack), lambda *a: [], lambda s: _UNIT)
    assert "risk_halt" not in st and "acknowledged" in notes[0]


def test_a_held_position_re_measured_within_bound_lifts_the_halt():
    st = _halted_state()
    pos = SimpleNamespace(volume=0.1, price_open=1.1100, sl=1.1050, type=0)   # 50 EUR = 1.0x
    ri.review_halts(st, {}, lambda *a: [pos], lambda s: _UNIT)
    assert "risk_halt" not in st


@pytest.mark.parametrize("positions", [[], [SimpleNamespace(volume=0.1, price_open=1.11, sl=0.0,
                                                            type=0)]])
def test_nothing_to_re_measure_is_unmeasured_and_the_halt_stands(positions):
    st = _halted_state()
    notes = ri.review_halts(st, {}, lambda *a: positions, lambda s: _UNIT)
    assert "a" in st["risk_halt"] and "UNMEASURED" in notes[0]


def test_a_held_position_still_over_the_bound_keeps_the_halt():
    st = _halted_state()
    pos = SimpleNamespace(volume=0.1, price_open=1.1250, sl=1.1050, type=0)   # 200 EUR = 4x
    ri.review_halts(st, {}, lambda *a: [pos], lambda s: _UNIT)
    assert "a" in st["risk_halt"]


# ------------------------------------------------------------------- the board and the bill
def _ph(monkeypatch, fills, intents):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "process_health_ri", _DESK.parent.parent / "ops" / "process_health.py")
    assert spec and spec.loader
    ph = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ph)
    monkeypatch.setattr(ph, "RISK_FILLS", fills)
    monkeypatch.setattr(ph, "ORDER_INTENTS", intents)
    return ph


def _now_iso(seconds_ago: float = 60.0) -> str:
    from datetime import UTC, datetime, timedelta
    return (datetime.now(tz=UTC) - timedelta(seconds=seconds_ago)).isoformat()


def _intent(sleeve="eurusd_fam", deal=77, lane="family_market", retcode=10009, ago=60.0):
    return {"time": _now_iso(ago), "sleeve": sleeve, "lane": lane, "retcode": retcode,
            "deal_ticket": deal, "fill_price": 1.1103}


def _write(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")


def test_the_health_row_reads_no_fills_then_p50_p95(tmp_path, monkeypatch):
    fills, intents = tmp_path / "fills.jsonl", tmp_path / "intents.jsonl"
    _write(intents, [_intent(lane=None), _intent(retcode=10019)])      # gold / rejected: not ours
    ph = _ph(monkeypatch, fills, intents)
    assert ph._realised_risk_row()["verdict"] == "NO_FILLS"          # both sources agree: none
    fills.write_text(json.dumps({"status": "UNMEASURED", "why": "no stop"}) + "\n", "utf-8")
    assert ph._realised_risk_row()["verdict"] == "UNMEASURED"        # filled, not priceable
    _write(fills, [{"status": "MEASURED", "ratio": r, "sl_source": "position via deal"}
                   for r in (1.0, 1.0, 1.05, 0.9)])
    row = ph._realised_risk_row()
    assert row["verdict"] == "OK" and row["metric"]["p50"] == pytest.approx(1.0)
    with fills.open("a", encoding="utf-8") as fh:
        for _ in range(4):
            fh.write(json.dumps({"status": "MEASURED", "ratio": 2.5}) + "\n")
    row = ph._realised_risk_row()
    assert row["verdict"] == "RISK_BREACH" and row["metric"]["n_breaches"] == 4


@pytest.mark.parametrize("ledger", ["absent", "empty", "other_fill"])
def test_a_journalled_fill_missing_from_the_ledger_is_unmeasured_and_named(
        tmp_path, monkeypatch, ledger):
    fills, intents = tmp_path / "fills.jsonl", tmp_path / "intents.jsonl"
    _write(intents, [_intent(sleeve="eurusd_fam", deal=77)])
    if ledger == "empty":
        fills.write_text("", "utf-8")
    elif ledger == "other_fill":
        _write(fills, [{"status": "MEASURED", "ratio": 1.0, "deal": 12, "sleeve": "x",
                        "at": _now_iso()}])
    ph = _ph(monkeypatch, fills, intents)
    row = ph._realised_risk_row()
    assert row["verdict"] == "UNMEASURED"
    assert "eurusd_fam deal 77" in row["why"] and "no realised-risk row" in row["why"]
    doc = ph.build()
    assert doc["status"] == "ATTENTION", "a fill the ledger missed must page"


@pytest.mark.parametrize("journal", ["absent", "corrupt"])
def test_an_unreadable_witness_is_unmeasured_never_no_fills(tmp_path, monkeypatch, journal):
    fills, intents = tmp_path / "fills.jsonl", tmp_path / "intents.jsonl"
    if journal == "corrupt":
        intents.write_text('{"time": "x", "lane": "family_market"\n', "utf-8")
    row = _ph(monkeypatch, fills, intents)._realised_risk_row()
    assert row["verdict"] == "UNMEASURED" and "cannot cross-check" in row["why"]


def test_a_journalled_fill_with_its_row_is_measured_and_old_fills_fall_out_of_the_window(
        tmp_path, monkeypatch):
    fills, intents = tmp_path / "fills.jsonl", tmp_path / "intents.jsonl"
    _write(intents, [_intent(deal=77), _intent(deal=None, sleeve="s2"),
                     _intent(deal=5, ago=8 * 86400.0)])                 # 8 days old: outside
    _write(fills, [{"status": "MEASURED", "ratio": 1.0, "deal": 77, "sleeve": "eurusd_fam",
                    "at": _now_iso(), "sl_source": "position via deal"},
                   {"status": "MEASURED", "ratio": 1.0, "deal": None, "sleeve": "s2",
                    "at": _now_iso(30), "sl_source": "position via order"}])
    row = _ph(monkeypatch, fills, intents)._realised_risk_row()
    assert row["verdict"] == "OK", row["why"]
    assert row["metric"]["cross_check"] == {"journal_fills": 2, "missing": 0}


def test_a_high_share_of_requested_stop_fallbacks_is_a_finding(tmp_path, monkeypatch):
    fills, intents = tmp_path / "fills.jsonl", tmp_path / "intents.jsonl"
    _write(intents, [])
    rows = [{"status": "MEASURED", "ratio": 1.0, "sl_source": "position via deal"}] * 3
    rows += [{"status": "MEASURED", "ratio": 1.0,
              "sl_source": "requested (position SL unreadable: LookupError)"}]
    _write(fills, rows)
    row = _ph(monkeypatch, fills, intents)._realised_risk_row()
    assert row["verdict"] == "FINDING" and row["metric"]["sl_fallback_share"] == 0.25
    assert ri.SL_FALLBACK_FINDING == 0.20 and "20%" in row["why"]


def test_the_gateway_stamps_the_lane_on_both_measured_lanes():
    src = (_DESK / "mt5desk" / "gateway.py").read_text("utf-8")
    assert 'lane="family_market",' in src and 'lane="scalp_market",' in src


def test_both_rails_have_a_missed_growth_line(tmp_path, monkeypatch):
    from research import missed_growth as mg
    for name in mg.RISK_INTENT_RAILS:
        assert f"measure_{name}" in mg.MEASURES
    monkeypatch.setattr(mg, "RISK_FILLS", tmp_path / "f.jsonl")
    monkeypatch.setattr(mg, "RISK_BREACHES", tmp_path / "b.jsonl")
    monkeypatch.setattr(mg, "REFUSED_ORDERS", tmp_path / "r.jsonl")
    r = SimpleNamespace(name="realised_risk_halt")
    # No ledger at all is an absence, never a clean verdict (L1.28a).
    assert mg.measure_realised_risk_halt(r, {}, {})["verdict"] == mg.UNMEASURED
    assert mg.measure_risk_intent_floor(r, {}, {})["verdict"] == mg.UNMEASURED
    (tmp_path / "b.jsonl").write_text(json.dumps({"sleeve": "a", "at": "t"}) + "\n", "utf-8")
    (tmp_path / "r.jsonl").write_text(json.dumps({"stage": "risk_halt"}) + "\n"
                                      + json.dumps({"stage": "risk_intent"}) + "\n", "utf-8")
    halt = mg.measure_realised_risk_halt(r, {}, {})
    assert halt["verdict"] == mg.UNMEASURED and halt["n_refused_entries"] == 1
    floor = mg.measure_risk_intent_floor(r, {}, {})
    assert floor["verdict"] == mg.UNMEASURED and floor["n_refused"] == 1


# ------------------------------------------------------------- audit 2026-10-20 (HOLD fixes)
def _ack(tmp_path, *entries) -> dict:
    path = tmp_path / "ack.json"
    path.write_text(json.dumps({"acknowledged": list(entries)}), "utf-8")
    return ri.read_acks(path)


def test_a_bare_sleeve_name_is_not_an_acknowledgement(tmp_path):
    st = _halted_state()
    acks = _ack(tmp_path, "a")
    notes = ri.review_halts(st, acks, lambda *a: [], lambda s: _UNIT)
    assert "a" in st["risk_halt"], "a never-expiring sleeve ack would lift every later breach"
    assert acks["ignored"] == ["a"] and "UNMEASURED" in notes[0]


def test_a_sleeve_ack_dated_after_the_halt_lifts_it_and_a_stale_one_does_not(tmp_path):
    st = _halted_state()
    stale = _ack(tmp_path, {"sleeve": "a", "at": "2026-10-20T11:59:00+00:00"})
    ri.review_halts(st, stale, lambda *a: [], lambda s: _UNIT)
    assert "a" in st["risk_halt"], "an ack older than the breach must not lift it"
    fresh = _ack(tmp_path, {"sleeve": "a", "at": "2026-10-20T12:30:00+00:00"})
    notes = ri.review_halts(st, fresh, lambda *a: [], lambda s: _UNIT)
    assert "risk_halt" not in st and "acknowledged" in notes[0]


def test_the_same_dated_ack_does_not_lift_a_later_breach(tmp_path):
    st = _halted_state()
    st["risk_halt"]["a"]["at"] = "2026-10-21T09:00:00+00:00"
    acks = _ack(tmp_path, {"sleeve": "a", "at": "2026-10-20T12:30:00+00:00"}, "a:1:t-old")
    ri.review_halts(st, acks, lambda *a: [], lambda s: _UNIT)
    assert "a" in st["risk_halt"]


def test_the_halt_rail_is_not_binding_only_when_fills_were_measured(tmp_path, monkeypatch):
    from research import missed_growth as mg
    monkeypatch.setattr(mg, "RISK_FILLS", tmp_path / "f.jsonl")
    monkeypatch.setattr(mg, "RISK_BREACHES", tmp_path / "b.jsonl")
    monkeypatch.setattr(mg, "REFUSED_ORDERS", tmp_path / "r.jsonl")
    r = SimpleNamespace(name="x")
    assert mg.measure_realised_risk_halt(r, {}, {})["verdict"] == mg.UNMEASURED
    (tmp_path / "f.jsonl").write_text(json.dumps({"status": "MEASURED", "ratio": 1.0}) + "\n")
    assert mg.measure_realised_risk_halt(r, {}, {})["verdict"] == mg.NOT_BINDING
    # The floor needs BOTH ledgers: fills alone cannot show a refusal.
    floor = mg.measure_risk_intent_floor(r, {}, {})
    assert floor["verdict"] == mg.UNMEASURED and floor["missing"] == ["r.jsonl"]
    (tmp_path / "r.jsonl").write_text(json.dumps({"stage": "symbol_side_cap"}) + "\n")
    assert mg.measure_risk_intent_floor(r, {}, {})["verdict"] == mg.NOT_BINDING


def test_the_revert_lifts_to_the_desk_venue_minimum_helper():
    out = ri.enforce(0.01, 0.0005, 1000.0, 0.001, 100_000.0, 0.01, 0.01, sovereign=False,
                     revert_min=0.02)
    assert out["ok"] and out["lot"] == pytest.approx(0.02)
    out = ri.enforce_on_venue(0.01, 0.0005, 1000.0, 0.001,
                              SimpleNamespace(volume_step=0.01, volume_min=0.01),
                              lambda: 100_000.0, sovereign=False, revert_min_fn=lambda: 0.02)
    assert out["lot"] == pytest.approx(0.02)
    # Sovereign: the helper is never consulted and the refusal stands.
    out = ri.enforce_on_venue(0.01, 0.0005, 1000.0, 0.001,
                              SimpleNamespace(volume_step=0.01, volume_min=0.01),
                              lambda: 100_000.0, revert_min_fn=lambda: 1 / 0)
    assert not out["ok"]


def test_the_gateway_passes_venue_min_lot_on_both_lanes():
    src = (_DESK / "mt5desk" / "gateway.py").read_text("utf-8")
    assert src.count("revert_min_fn=lambda: float(_core.venue_min_lot(s[\"symbol\"], sym))") == 2


def _family_quiet(tmp_path, monkeypatch, signals):
    rows = adapter._rows()
    venue = adapter._fake_mt5(rows)
    ns = adapter._family_ns(tmp_path, venue, monkeypatch, armed_file=False,
                            sig_hour=adapter._sig_hour(rows), signals=signals)
    ns["REFUSALS"] = tmp_path / "refused.jsonl"
    ns["now"] = lambda: "2026-10-20T12:00:00+00:00"     # journal_refusal stamps with it
    st = {"armed": False, "risk_halt": {adapter._NAME: {"breach_id": "x:1:t", "at": "t",
                                                        "symbol": "EURUSD"}}}
    return ns, st


def _refusals(tmp_path) -> list[dict]:
    path = tmp_path / "refused.jsonl"
    return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []


def test_a_halted_family_sleeve_without_a_signal_journals_nothing(tmp_path, monkeypatch):
    ns, st = _family_quiet(tmp_path, monkeypatch, signals=lambda closed, side: [])
    out = ns["resolve_family_order"](st, adapter._sleeve(), 10_000.0)
    assert out["stage"] == "no_signal"
    assert _refusals(tmp_path) == []


def test_a_halted_family_sleeve_with_a_signal_journals_the_halt_once(tmp_path, monkeypatch):
    ns, st = _family_quiet(tmp_path, monkeypatch, signals=None)
    out = ns["resolve_family_order"](st, adapter._sleeve(), 10_000.0)
    assert out["stage"] == "risk_halt" and out["mark"] is True
    assert [r["stage"] for r in _refusals(tmp_path)] == ["risk_halt"]


def test_an_unmeasured_family_intent_is_journalled(tmp_path, monkeypatch):
    rows = adapter._rows()
    venue = adapter._fake_mt5(rows)
    venue.symbol_info = lambda symbol: SimpleNamespace(
        volume_min=0.01, volume_max=100.0, trade_tick_size=0.00001, trade_tick_value=1.0)
    ns = adapter._family_ns(tmp_path, venue, monkeypatch, armed_file=False,
                            sig_hour=adapter._sig_hour(rows))
    ns["REFUSALS"] = tmp_path / "refused.jsonl"
    ns["now"] = lambda: "2026-10-20T12:00:00+00:00"     # journal_refusal stamps with it
    out = ns["resolve_family_order"]({"armed": False}, adapter._sleeve(), 10_000.0)
    assert out["stage"] == "risk_intent" and out["mark"] is False
    (row,) = _refusals(tmp_path)
    assert row["stage"] == "risk_intent" and "unmeasured" in row["why"]


def _scalp():
    import test_scalp_promotion as sp
    return sp


def test_scalp_intent_refusals_are_journalled(tmp_path):
    sp = _scalp()
    bars = sp._with_forming(sp._bars(recent=True))
    venue = sp._fake_mt5(bars)
    venue.symbol_info = lambda symbol: SimpleNamespace(volume_min=0.01)     # no volume_step
    ns = sp._ns(tmp_path, venue, armed_file=True)
    sp._run_scalp(ns, {"armed": True}, [sp._sleeve()], 10_000.0)
    assert venue.sent == []
    refused = [b for b in ns["_book"] if b[0] == "refusal"]
    assert [b[4] for b in refused] == ["risk_intent"]


@pytest.mark.parametrize("breakout,expect", [(False, []), (True, ["risk_halt"])])
def test_a_halted_scalp_sleeve_journals_only_when_an_entry_is_due(tmp_path, breakout, expect):
    sp = _scalp()
    bars = sp._with_forming(sp._bars(breakout=breakout, recent=True))
    venue = sp._fake_mt5(bars)
    ns = sp._ns(tmp_path, venue, armed_file=True)
    st = {"armed": True, "risk_halt": {sp._NAME: {"breach_id": "x:1:t", "at": "t"}}}
    sp._run_scalp(ns, st, [sp._sleeve()], 10_000.0)
    assert venue.sent == []
    assert [b[4] for b in ns["_book"] if b[0] == "refusal"] == expect


def _armed_family(tmp_path, monkeypatch, position_sl, *, deal=None, order=9,
                  position_id=None, via="deal"):
    """One armed family pass whose send returns `deal`/`order`, on a venue where that deal (or
    order) resolves to `position_id`, and `positions_get(ticket=position_id)` holds
    `position_sl`. Nothing answers for `positions_get(ticket=order)` unless order is the
    position: the code must not assume it is."""
    rows = adapter._rows()
    venue = adapter._fake_mt5(rows)
    venue.symbol_info = lambda symbol: SimpleNamespace(
        volume_min=0.01, volume_step=0.01, volume_max=100.0,
        trade_tick_size=0.00001, trade_tick_value=1.0)

    def send(req):
        venue.sent.append(req)
        return SimpleNamespace(retcode=10009, order=order, deal=deal, comment="done",
                               price=1.1103, volume=req["volume"])
    venue.order_send = send

    def history_deals_get(*a, ticket=None, **k):
        if via == "deal" and ticket is not None and ticket == deal and position_id:
            return [SimpleNamespace(ticket=deal, order=order, position_id=position_id)]
        return []

    def history_orders_get(*a, ticket=None, **k):
        if via == "order" and ticket is not None and ticket == order and position_id:
            return [SimpleNamespace(ticket=order, position_id=position_id)]
        return []
    venue.history_deals_get = history_deals_get
    venue.history_orders_get = history_orders_get

    def positions_get(*a, **k):
        if "ticket" not in k:
            return []
        if position_id is not None and k["ticket"] == position_id and position_sl is not None:
            return [SimpleNamespace(ticket=position_id, sl=position_sl)]
        if k["ticket"] == order and order != position_id:
            # A DECOY: some other position that happens to carry the order's number. Reading
            # it would be the ticket == order assumption the audit forbade.
            return [SimpleNamespace(ticket=order, sl=1.1040)]
        return []
    venue.positions_get = positions_get
    ns = adapter._family_ns(tmp_path, venue, monkeypatch, armed_file=True,
                            sig_hour=adapter._sig_hour(rows))
    ns["RISK_FILLS"] = tmp_path / "fills.jsonl"
    ns["RISK_BREACHES"] = tmp_path / "breaches.jsonl"
    st: dict = {"armed": True}
    adapter._run_family(ns, st, [adapter._sleeve()], 10_000.0)
    (row,) = [json.loads(x) for x in (tmp_path / "fills.jsonl").read_text().splitlines()]
    return st, row


def test_post_fill_risk_reads_the_stop_back_from_the_opened_position(tmp_path, monkeypatch):
    # The venue holds the stop 3x further away than requested: that is the risk carried.
    st, row = _armed_family(tmp_path, monkeypatch, position_sl=1.0950, deal=77,
                            position_id=9)
    assert row["sl_source"] == "position via deal" and row["sl"] == pytest.approx(1.0950)
    assert row["breach"] is True and adapter._NAME in st["risk_halt"]


def test_netting_the_position_is_found_through_the_deal_not_the_order(tmp_path, monkeypatch):
    # Netting: the deal lands on the symbol's existing position 4242, not on order 9.
    st, row = _armed_family(tmp_path, monkeypatch, position_sl=1.0950, deal=77, order=9,
                            position_id=4242)
    assert row["sl_source"] == "position via deal" and row["sl"] == pytest.approx(1.0950)


def test_without_a_deal_the_position_is_found_through_the_order(tmp_path, monkeypatch):
    st, row = _armed_family(tmp_path, monkeypatch, position_sl=1.0950, deal=None, order=9,
                            position_id=4242, via="order")
    assert row["sl_source"] == "position via order" and row["sl"] == pytest.approx(1.0950)


def test_an_unreadable_position_falls_back_to_the_requested_stop_by_name(tmp_path, monkeypatch):
    st, row = _armed_family(tmp_path, monkeypatch, position_sl=None, deal=77,
                            position_id=4242)
    assert row["sl_source"].startswith("requested (position SL unreadable")
    assert row["sl"] == pytest.approx(1.1050) and row["breach"] is False
    assert "risk_halt" not in st


def test_an_unresolvable_position_falls_back_by_name_and_never_reads_the_order_ticket(
        tmp_path, monkeypatch):
    # position_id unknown: nothing in history. A position that happens to carry the ORDER's
    # ticket must not be read as this fill's.
    st, row = _armed_family(tmp_path, monkeypatch, position_sl=1.0950, deal=77, order=9,
                            position_id=None)
    assert row["sl_source"].startswith("requested (position SL unreadable: LookupError")
