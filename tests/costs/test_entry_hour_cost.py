"""ENTRY-HOUR COST: the gauntlet and every forward clock charge the spread of the hour they trade.

Pins the four promises of `desks/mt5/research/entry_hour_cost.py` and the engine path it feeds:
the flat path is byte-identical, a long pays its ENTRY slot's full spread and a short its EXIT
slot's (bid bars: the ask is crossed there -- not half-and-half, which is the mid-bar rule), the
fallback ladder never reaches zero or a cheaper number, and a zero/missing/stale cost field is
named UNMEASURED rather than priced as free.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "desks" / "mt5"), str(_ROOT / "desks" / "mt5" / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk.engine import Costs, Signal, run_backtest, spread_at  # noqa: E402

from research import cost_surface as cs  # noqa: E402
from research import entry_hour_cost as ehc  # noqa: E402

META = {"contract_size": 100000.0, "tick_size": 0.00001, "tick_value": 1.0,
        "median_spread_pts": 10.0, "swap_long": -1.0, "swap_short": -1.0,
        "updated_at": datetime.now(UTC).isoformat()}


def _surface(hours: dict[str, dict], **extra) -> dict:
    row = {"hours": hours, **extra}
    return {"schema": "cost-surface-2", "schema_revision": 2,
            "built_at": datetime.now(UTC).isoformat(), "symbols": {"X": row}}


def _bars(n: int = 200, start: str = "2024-01-02 00:00") -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq="h", tz="UTC")
    px = [1.0 + 0.0001 * (i % 7) for i in range(n)]
    return pd.DataFrame({"open": px, "high": [p + 0.002 for p in px],
                         "low": [p - 0.002 for p in px], "close": px,
                         "spread": 0, "tick_volume": 100}, index=idx)


def test_flat_path_is_byte_identical_without_a_table():
    df = _bars()
    sig = [Signal(time=df.index[5], side=1, stop=0.99, target=1.01, ttl_bars=3, tag="t")]
    flat = Costs.from_symbol(META)
    assert flat.spread_per_lot_by_hour is None
    r1 = run_backtest(df, sig, flat).trades[0].r_multiple
    tab = Costs.from_symbol(META)
    from dataclasses import replace
    same = replace(tab, spread_per_lot_by_hour=tuple([flat.spread_per_lot] * 24))
    r2 = run_backtest(df, sig, same).trades[0].r_multiple
    assert r1 == pytest.approx(r2, abs=1e-12), "a constant table must equal the flat charge"


def test_a_long_pays_its_entry_slot_and_a_short_its_exit_slot():
    from dataclasses import replace
    base = Costs.from_symbol(META)
    tab = [1.0] * 24
    tab[1] = 101.0   # entry hour (signal 00:00 -> fill 01:00)
    c = replace(base, spread_per_lot_by_hour=tuple(tab))
    assert spread_at(c, pd.Timestamp("2024-01-02 01:30", tz="UTC")) == 101.0
    df = _bars()
    zero = replace(base, spread_per_lot_by_hour=tuple([0.0] * 24))
    for side, stop, target in ((1, 0.99, 5.0), (-1, 1.01, 0.5)):
        sig = [Signal(time=df.index[0], side=side, stop=stop, target=target, ttl_bars=3, tag="t")]
        tr = run_backtest(df, sig, c).trades[0]
        assert tr.entry_time.hour == 1
        paid = 101.0 if side > 0 else tab[tr.exit_time.hour]
        diff = run_backtest(df, sig, zero).trades[0].r_multiple - tr.r_multiple
        stop_dist = abs(tr.entry - stop)
        assert diff == pytest.approx(paid / base.contract_oz / stop_dist, rel=1e-9)


def test_stress_scales_the_table():
    from dataclasses import replace
    c = replace(Costs.from_symbol(META), spread_per_lot_by_hour=tuple([2.0] * 24))
    assert c.stressed(3.0).spread_per_lot_by_hour == tuple([6.0] * 24)


def test_ladder_measured_thin_unmeasured_absent_never_zero():
    surf = _surface(
        {"0": {"status": "MEASURED", "p50": 900.0, "p90": 2000.0, "n_nonzero": 500},
         "1": {"status": "UNMEASURED", "thin_p50": 300.0, "thin_p90": 600.0, "n_nonzero": 50},
         "2": {"status": "UNMEASURED", "n_nonzero": 0, "zero_frac": 1.0}},
        sessions={"asia": {"status": "MEASURED", "p50": 100.0, "p75": 140.0, "p90": 200.0}},
        symbol_level={"status": "MEASURED", "p50": 80.0, "p75": 120.0, "p90": 300.0})
    v0, i0 = ehc.hour_spread_pts(surf, "X", 0)
    assert v0 == 900.0 and i0["basis"] == "hour"
    v1, i1 = ehc.hour_spread_pts(surf, "X", 1)
    assert v1 == pytest.approx((50 * 300 + ehc.K_SHRINK * 100) / (50 + ehc.K_SHRINK))
    assert i1["n_eff"] == 50 + ehc.K_SHRINK and "session:asia" in i1["basis"]
    v2, _ = ehc.hour_spread_pts(surf, "X", 2)
    assert v2 == 140.0, "an unmeasured hour takes the parent's UPPER quantile, not its median"
    v2s, _ = ehc.hour_spread_pts(surf, "X", 2, q="p90")
    assert v2s == 200.0
    v9, _ = ehc.hour_spread_pts(surf, "X", 9)
    assert v9 == 120.0, "no session -> the symbol level's upper quantile"
    none, info = ehc.hour_spread_pts(surf, "MISSING", 1)
    assert none is None and info["basis"].startswith("UNMEASURED")
    tab, _ = ehc.spread_table_pts(surf, "X")
    assert tab is not None and len(tab) == 168 and min(tab) > 0


def test_dow_cell_shrinks_toward_its_hour():
    surf = _surface({"0": {"status": "MEASURED", "p50": 100.0, "p90": 200.0, "n_nonzero": 900}},
                    symbol_level={"status": "MEASURED", "p50": 50.0, "p75": 60.0, "p90": 90.0},
                    dow_hours={"0": {"0": [500.0, 900.0, 50]}})
    v, info = ehc.dow_hour_spread_pts(surf, "X", 0, 0)
    assert v == pytest.approx((50 * 500 + ehc.K_SHRINK * 100) / (50 + ehc.K_SHRINK))
    assert info["n_eff"] == 50 + ehc.K_SHRINK
    assert ehc.dow_hour_spread_pts(surf, "X", 1, 0)[0] == 100.0


def test_costs_at_entry_hour_attaches_the_table_and_never_prices_zero():
    surf = _surface({str(h): {"status": "MEASURED", "p50": 20.0 if h else 400.0,
                              "p90": 40.0, "n_nonzero": 999} for h in range(24)})
    zero_meta = {**META, "median_spread_pts": 0.0}
    c, basis = ehc.costs_at_entry_hour("X", zero_meta, surface=surf)
    assert basis == "fill_hour_surface_table"
    assert c.spread_per_lot_by_hour[0] == pytest.approx(400.0 * 1e-5 * 1e5)
    assert c.spread_per_lot_by_hour[1] == pytest.approx(20.0 * 1e-5 * 1e5)
    c2, basis2 = ehc.costs_at_entry_hour("ABSENT", zero_meta, surface=surf)
    assert basis2.startswith("UNMEASURED"), "a zero registry spread and no surface row is not free"
    assert c2 is None, "UNMEASURED returns no price -- never the 0.05 floor"
    _, basis3 = ehc.costs_at_entry_hour("ABSENT", META, surface=surf)
    assert basis3.startswith("REGISTRY_FALLBACK")


def test_field_status_names_zero_missing_and_stale():
    now = datetime.now(UTC)
    old = (now - timedelta(days=ehc.SPREAD_STALE_DAYS + 1)).isoformat()
    assert ehc.field_status({**META, "median_spread_pts": 0.0}, now)["spread"] == "ZERO"
    assert ehc.field_status({k: v for k, v in META.items() if k != "median_spread_pts"},
                            now)["spread"] == "MISSING"
    assert ehc.field_status({**META, "updated_at": old}, now)["spread"] == "STALE"
    assert ehc.field_status({**META, "swap_long": 0.0, "swap_short": 0.0}, now)["swap"] == "ZERO"
    assert ehc.field_status({k: v for k, v in META.items() if k != "swap_long"},
                            now)["swap"] == "MISSING"
    assert ehc.field_status(META, now) == {"spread": "MEASURED", "swap": "MEASURED",
                                           "commission": "MEASURED"}
    block = ehc.unmeasured_fields({"A": {**META, "median_spread_pts": 0.0}, "B": META}, now)
    assert block["n_symbols"] == 1 and block["by_field"]["spread"]["ZERO"] == ["A"]


def test_surface_cuts_the_fixed_spread_era_and_publishes_parents():
    # 2020: a placeholder 160 on every bar; 2021+: a priced book of 2 with a 40-pt rollover.
    idx = pd.date_range("2020-06-01", "2021-12-31 23:00", freq="h", tz="UTC")
    sp = [160 if t.year == 2020 else (40 if t.hour == 0 else 2) for t in idx]
    df = pd.DataFrame({"spread": sp, "tick_volume": 100}, index=idx)
    prof = cs.profile_symbol(df)
    assert prof is not None and prof["era_bars_dropped"] > 0
    assert prof["hours"]["10"]["p50"] == 2.0, "the 2020 placeholder must not reach a percentile"
    assert prof["hours"]["0"]["p50"] == 40.0
    assert prof["sessions"]["rollover"]["p50"] == 40.0
    assert prof["symbol_level"]["status"] == "MEASURED"
    assert prof["rollover_over_day_p50"] == 20.0
    assert "0" in prof["dow_hours"]


def test_collector_never_writes_a_zero_central_value(monkeypatch):
    from research import expand_universe as ex
    monkeypatch.setattr(ex, "_surface_symbol_p50", lambda sym: (13.0, "cost_surface_symbol_p50"))

    class _Info:
        name = "USDJPY"
        spread = 0

    out = ex._median_spread_write({"median_spread_pts": 0.0}, {"spread": [0, 0, 0, 1]},
                                  _Info(), datetime.now(UTC))
    assert out["median_spread_pts"] == 13.0
    assert out["_provenance"]["median_spread_pts"]["source"] == "cost_surface_symbol_p50"
    monkeypatch.setattr(ex, "_surface_symbol_p50", lambda sym: (None, "no priced level"))
    assert ex._median_spread_write({"median_spread_pts": 0.0}, {"spread": [0, 0]}, _Info(),
                                   datetime.now(UTC)) == {}


def test_judge_coverage_publishes_the_unmeasured_cost_fields(tmp_path):
    import json

    from research import judge_coverage as jc
    reg = tmp_path / "universe.json"
    reg.write_text(json.dumps({"USDJPY": {**META, "median_spread_pts": 0.0}, "EURUSD": META}))
    block = jc._cost_fields_unmeasured(reg)
    assert block["status"] == "MEASURED"
    assert block["n_symbols"] == 1 and block["n_symbols_zero_or_missing"] == 1
    assert block["by_field"]["spread"]["ZERO"] == ["USDJPY"]
    missing = jc._cost_fields_unmeasured(tmp_path / "absent.json")
    assert missing["status"].startswith("UNMEASURED") and missing["n_symbols"] is None


def test_accuracy_report_compares_the_fill_quote_to_the_modelled_charge():
    from research import cost_surface_accuracy as acc
    surf = _surface({str(h): {"status": "MEASURED", "p50": 20.0, "p90": 40.0, "n_nonzero": 999}
                     for h in range(24)})
    fills = [{"symbol": "X", "fill_price": 1.0, "quote_bid": 1.0, "quote_ask": 1.0004,
              "filled_at": "2026-09-16T04:45:53+00:00"} for _ in range(3)]
    doc = acc.build(fills=fills, registry={"X": META}, surface=surf)
    row = doc["symbols"]["X"]
    assert row["realized_spread_pts_p50"] == pytest.approx(40.0)
    assert row["modelled_spread_pts_p50"] == 20.0
    assert row["realized_over_modelled"] == pytest.approx(2.0)
    assert "X" in doc["undercharged_symbols"]
    assert acc.broker_slot("2026-09-16T04:45:53+00:00") == (2, 7), "summer: broker = UTC+3"
    empty = acc.build(fills=[], registry={}, surface=surf)
    assert empty["status"].startswith("UNMEASURED")


def test_recent_window_is_preferred_when_it_has_the_bars():
    surf = _surface({"0": {"status": "MEASURED", "p50": 42.0, "p90": 100.0, "n_nonzero": 2255,
                           "r365_n": 250, "r365_p50": 87.0, "r365_p90": 119.0},
                     "1": {"status": "MEASURED", "p50": 15.0, "p90": 18.0, "n_nonzero": 2255,
                           "r365_n": 20, "r365_p50": 99.0, "r365_p90": 99.0}})
    v, info = ehc.hour_spread_pts(surf, "X", 0)
    assert v == 87.0 and info["basis"] == "hour_recent365", "NZDJPY's rollover regime, not 8y"
    assert ehc.hour_spread_pts(surf, "X", 0, q="p90")[0] == 119.0
    assert ehc.hour_spread_pts(surf, "X", 1)[0] == 15.0, "too few recent bars: long-run cell"


def test_surface_pooled_is_its_own_median_and_registry_disagreement_is_named(tmp_path):
    idx = pd.date_range("2022-01-03", periods=24 * 400, freq="h", tz="UTC")
    df = pd.DataFrame({"spread": [42 if t.hour == 0 else 15 for t in idx],
                       "tick_volume": 100, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0},
                      index=idx)
    df.to_parquet(tmp_path / "NZDJPY_H1.parquet")
    (tmp_path / "universe.json").write_text('{"NZDJPY": {"median_spread_pts": 147.0}}')
    doc = cs.build(tmp_path)
    row = doc["symbols"]["NZDJPY"]
    assert row["pooled_median_spread_pts"] == 15.0
    assert row["registry_median_spread_pts"] == 147.0
    assert [m["symbol"] for m in doc["registry_pooled_mismatch"]] == ["NZDJPY"]
    assert row["hours"]["0"]["r365_p50"] == 42.0


def test_charged_vs_hour_names_the_rollover_undercharge():
    surf = _surface({str(h): {"status": "MEASURED", "p50": 42.0 if h == 0 else 15.0,
                              "p90": 100.0, "n_nonzero": 999} for h in range(24)},
                    pooled_median_spread_pts=147.0)
    out = ehc.charged_vs_hour(surf, {"X": {"median_spread_pts": 15.0}})
    assert out["undercharged_at_rollover"] == ["X"]
    assert out["by_symbol"]["X"]["registry"]["0"]["x"] == 2.8
    assert out["pooled_vs_hourly"][0]["stored_pooled_pts"] == 147.0


# --- measured entry slip: read-only helper (2026-10-14) -------------------------------------


def _mk(sym_mean, sym_n, cells):
    return {"slip_breakdown": {
        "by_symbol": {"XAUUSD": {"clean": {"pts": {"mean": sym_mean, "n": sym_n}}}},
        "by_symbol_hour": {"XAUUSD": {h: {"clean": {"pts": {"mean": m, "n": n}}}
                                      for h, (m, n) in cells.items()}}}}


def test_hour_slip_shrinks_a_thin_cell_toward_the_symbol_pool():
    doc = _mk(10.0, 50, {"7": (40.0, 2), "13": (20.0, 90)})
    v, info = ehc.hour_slip_pts(doc, "XAUUSD", 7)
    w = 2 / (2 + ehc.SLIP_K)
    assert v == pytest.approx(w * 40.0 + (1 - w) * 10.0)
    assert info["basis"] == "hour_shrunk_to_symbol" and info["n"] == 2
    v13, _ = ehc.hour_slip_pts(doc, "XAUUSD", 13)
    assert v13 == pytest.approx(0.9 * 20.0 + 0.1 * 10.0)


def test_hour_slip_empty_cell_is_the_symbol_pool():
    v, info = ehc.hour_slip_pts(_mk(-3.0, 12, {}), "XAUUSD", 5)
    assert v == pytest.approx(-3.0)          # measured improvement stays negative
    assert info["basis"] == "symbol_pooled"


def test_hour_slip_unmeasured_is_zero_and_says_so():
    for doc in (None, {}, _mk(None, 0, {})):
        v, info = ehc.hour_slip_pts(doc, "XAUUSD", 7)
        assert v == 0.0
        assert info["status"] == "UNMEASURED"


def test_hour_cost_is_spread_plus_slip_and_none_without_a_spread():
    surface = {"schema_revision": 2, "built_at": datetime.now(UTC).isoformat(),
               "symbols": {"XAUUSD": {"hours": {"7": {"status": "MEASURED", "p50": 15.0,
                                                       "n_nonzero": 500}}}}}
    v, info = ehc.hour_cost_pts(surface, _mk(10.0, 50, {}), "XAUUSD", 7)
    assert v == pytest.approx(25.0)
    assert info["slip"]["basis"] == "symbol_pooled"
    v2, info2 = ehc.hour_cost_pts(surface, None, "EURUSD", 7)
    assert v2 is None and info2["slip"]["status"] == "UNMEASURED"


# --- audit 2026-10-13 must-fixes -------------------------------------------------------------


def _full(**top):
    doc = _surface({str(h): {"status": "MEASURED", "p50": 20.0, "p90": 40.0, "n_nonzero": 999}
                    for h in range(24)})
    doc.update(top)
    return doc


def test_an_old_revision_or_stale_surface_prices_nothing():
    assert ehc.hour_spread_pts(_full(), "X", 3)[0] == 20.0
    for bad, why in ((_full(schema_revision=1), "revision 1"),
                     (_full(schema_revision=None), "revision 1"),
                     (_full(built_at=(datetime.now(UTC) - timedelta(hours=73)).isoformat()),
                      "h old"),
                     (_full(built_at=None), "built_at")):
        v, info = ehc.hour_spread_pts(bad, "X", 3)
        assert v is None and info["basis"].startswith("UNMEASURED") and why in info["basis"]
        c, basis = ehc.costs_at_entry_hour("X", {**META, "median_spread_pts": 0.0}, surface=bad)
        assert c is None and basis.startswith("UNMEASURED")
    ok, why = ehc.surface_usable(_full(), now=datetime.now(UTC) + timedelta(hours=71))
    assert ok, why
    assert ehc.surface_usable(None) == (False, "no cost surface")


def test_a_measured_hour_with_a_zero_median_is_not_a_price():
    surf = _surface({"5": {"status": "MEASURED", "p50": 0.0, "n_nonzero": 900}},
                    symbol_level={"status": "MEASURED", "p50": 50.0, "p75": 60.0, "p90": 90.0})
    v, info = ehc.hour_spread_pts(surf, "X", 5)
    assert v == 60.0 and info["basis"] == "symbol_upper_quantile"


def test_a_nan_registry_spread_is_unmeasured_not_nan_r():
    c, basis = ehc.costs_at_entry_hour("ABSENT", {**META, "median_spread_pts": float("nan")},
                                       surface=_full())
    assert c is None and "spread=MISSING" in basis


def test_the_gauntlet_keeps_its_pre_patch_flat_model_but_records_unmeasured(monkeypatch):
    monkeypatch.setattr(ehc, "load_surface", lambda path=None: None)
    costs, basis, _ = ehc.gauntlet_costs("ABSENT", {"ABSENT": {**META, "median_spread_pts": 0}})
    assert basis.startswith("UNMEASURED")
    assert costs is not None and costs.spread_per_lot_by_hour is None
    assert costs == Costs.from_symbol({**META, "median_spread_pts": 0})


def test_attach_table_discloses_a_flat_price_as_unmeasured():
    base = Costs.from_symbol({**META, "median_spread_pts": 0.0})
    c, basis = ehc.attach_table("X", {**META, "median_spread_pts": 0.0}, base,
                                surface=_full(schema_revision=1))
    assert c is base and basis.startswith("UNMEASURED(spread=ZERO)")
    c2, basis2 = ehc.attach_table("X", META, base, surface=_full())
    assert basis2 == "fill_hour_surface_table" and c2.spread_per_lot_by_hour


def test_surface_stamp_carries_sha_built_at_and_usability(tmp_path):
    p = tmp_path / "cs.json"
    import json as _json
    p.write_text(_json.dumps(_full()), "utf-8")
    ehc._SURFACE_CACHE.pop(str(p), None)
    st = ehc.surface_stamp(p)
    assert st["cost_surface_usable"] is True and len(st["cost_surface_sha"]) == 16
    assert st["cost_surface_built_at"]
    p2 = tmp_path / "crlf.json"
    p2.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    assert ehc.surface_stamp(p2)["cost_surface_sha"] == st["cost_surface_sha"]
    gone = ehc.surface_stamp(tmp_path / "absent.json")
    assert gone["cost_surface_usable"] is False and gone["cost_surface_sha"] is None


def test_cost_hash_includes_the_hour_table_and_flat_is_unchanged():
    import importlib
    from dataclasses import replace
    reg = importlib.import_module("sleeve_registry")
    flat = Costs.from_symbol(META)
    t1 = replace(flat, spread_per_lot_by_hour=tuple([1.0] * 168))
    t2 = replace(flat, spread_per_lot_by_hour=tuple([1.0] * 167 + [2.0]))
    assert reg.cost_hash(t1) != reg.cost_hash(flat)
    assert reg.cost_hash(t1) != reg.cost_hash(t2)
    import hashlib
    import json as _json
    legacy = {k: round(float(v), 6) for k, v in vars(flat).items()
              if isinstance(v, (int, float)) and not isinstance(v, bool)}
    assert reg.cost_hash(flat) == hashlib.sha256(
        _json.dumps(legacy, sort_keys=True).encode()).hexdigest()[:16], "flat hash moved"


def test_a_stale_surface_p50_stamp_yields_to_the_hourly_median():
    from mt5desk.universe_registry import may_write_median_spread
    fresh = datetime.now(UTC).isoformat()
    old = (datetime.now(UTC) - timedelta(hours=80)).isoformat()

    def row(at):
        return {"median_spread_pts": 13.0, "_provenance": {"median_spread_pts": {
            "source": "cost_surface_symbol_p50", "at": at}}}
    assert may_write_median_spread(row(fresh), "h1_spread_median")[0] is False
    ok, why = may_write_median_spread(row(old), "h1_spread_median")
    assert ok and "expired" in why
    assert may_write_median_spread(row("garbage"), "h1_spread_median")[0] is True
    assert may_write_median_spread(row(old), "cost_surface_symbol_p50")[0] is True


def test_expand_universe_refuses_a_stale_surface(tmp_path, monkeypatch):
    import json as _json

    from research import expand_universe as ex
    (tmp_path / "data").mkdir()
    doc = _full()
    doc["symbols"]["X"]["symbol_level"] = {"status": "MEASURED", "p50": 12.0}
    (tmp_path / "data" / "cost_surface.json").write_text(_json.dumps(doc), "utf-8")
    monkeypatch.setattr(ex, "BASE", tmp_path)
    assert ex._surface_symbol_p50("X") == (12.0, "cost_surface_symbol_p50")
    doc["schema_revision"] = 1
    (tmp_path / "data" / "cost_surface.json").write_text(_json.dumps(doc), "utf-8")
    v, why = ex._surface_symbol_p50("X")
    assert v is None and "revision 1" in why


def test_ledger_rows_say_when_the_surface_postdates_the_entry():
    from research import qquant_shadow as qq
    from research import shadow_forward as sf
    st = {"cost_surface_built_at": "2026-10-10T00:00:00+00:00"}
    for fn in (sf._surface_postdates, qq._postdates):
        assert fn(st, "2026-10-01 05:00:00+00:00") is True
        assert fn(st, pd.Timestamp("2026-10-11 05:00")) is False
    assert sf._surface_postdates({"spread_basis": "frozen_basis"}, "2026-10-01") is None
    assert qq._postdates({"cost_surface_built_at": "nonsense"}, "2026-10-01") is None
