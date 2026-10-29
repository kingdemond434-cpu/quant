"""Broker-state, Amihud, swap-drift and options-state cells: point-in-time, registered, honest.

* the venue clock: `utc_to_server` is the exact inverse of `server_to_utc`, shoulder months too;
* N7: margin hikes/cuts and CLOSEONLY on/off are read off the hourly tape at the first record
  showing them, an unread field is never a change, and one dated instruction is one event;
* swaps: a change and a sign flip carry the sign of the differential's move, a mode change is a
  unit change (no event), and the VPS registry re-read rows never become events;
* the event families enter on the first bar OPENING at/after the knowable instant on the bars'
  broker clock, and `drift` and `reversal` take opposite sides;
* Amihud: the normalised impact and the family are strictly trailing, and refuse without
  tick_volume; share CFDs reach it only through the class book;
* options: z is computed against PRIOR vintages only, the unit-contaminated candidates are never
  used, and percent-era vintages are normalised;
* the triangle reader accepts `time_msc` where `ts` is missing;
* the organ: no tape -> UNMEASURED and no store written; a cell under the floor is
  SERIES_ACCRUING with its event count; a cell over it is donated once with declared_width 1;
* every family is registered with a mechanism, a cluster and a leg.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_amihud as fam  # noqa: E402
from mt5desk import family_broker_state as fbs  # noqa: E402
from mt5desk import family_options_state as fos  # noqa: E402

from libs.regime.session_clock import server_to_utc, utc_to_server  # noqa: E402
from research import broker_state_cells as bsc  # noqa: E402


def _bars(n: int = 24 * 200, seed: int = 1, start: str = "2026-01-05") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq="1h", tz="UTC")
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    open_ = np.r_[close[0], close[:-1]]
    vol = rng.integers(50, 500, n).astype(float)
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * 1.001,
                         "low": np.minimum(open_, close) * 0.999, "close": close,
                         "tick_volume": vol}, index=idx)


def _key(sigs):
    return [(pd.Timestamp(s.time).value, s.side, round(s.stop, 8), s.tag) for s in sigs]


# ------------------------------------------------------------------------------- clock ------
@pytest.mark.parametrize("utc", ["2026-07-01T12:00:00Z", "2026-01-15T03:30:00Z",
                                 "2026-10-14T09:00:00Z", "2026-03-10T21:00:00Z"])
def test_utc_to_server_inverts_server_to_utc(utc):
    stamp = utc_to_server(utc)
    assert stamp is not None
    back = server_to_utc(pd.DatetimeIndex([stamp]))[0]
    assert back == pd.Timestamp(utc)


def test_utc_to_server_offsets_and_refusal():
    assert utc_to_server("2026-07-01T12:00:00Z") == pd.Timestamp("2026-07-01T15:00:00Z")
    assert utc_to_server("2026-01-15T12:00:00Z") == pd.Timestamp("2026-01-15T14:00:00Z")
    assert utc_to_server(None) is None
    assert utc_to_server("not a time") is None


# ----------------------------------------------------------------------------- the tape -----
def _terms(rows):
    return pd.DataFrame([{c: r.get(c) for c in bsc.TERM_COLUMNS} for r in rows]).sort_values(
        ["symbol", "observed_at"]).reset_index(drop=True)


def _row(at, sym="XAUUSD", **kw):
    base = {"observed_at": at, "symbol": sym, "margin_initial": 100.0,
            "margin_maintenance": 50.0, "trade_mode": 4, "swap_long": -10.0,
            "swap_short": 5.0, "swap_mode": 1, "tick_value": 1.0, "tick_size": 0.01}
    base.update(kw)
    return base


def test_margin_and_trade_mode_events_are_read_at_the_first_record_showing_them():
    t = _terms([
        _row("2026-09-01T10:00:00+00:00"),
        _row("2026-09-01T11:00:00+00:00", margin_initial=None),           # unread, not a change
        _row("2026-09-01T12:00:00+00:00", margin_initial=150.0, margin_maintenance=75.0),
        _row("2026-09-01T13:00:00+00:00", margin_initial=150.0, margin_maintenance=75.0,
             trade_mode=3),
        _row("2026-09-01T14:00:00+00:00", margin_initial=120.0, margin_maintenance=75.0,
             trade_mode=4),
    ])
    ev = bsc.margin_events(t)
    kinds = [(e["kind"], e["knowable_at"][11:16]) for e in ev]
    # the hike moved BOTH fields in one record: one dated instruction, one event
    assert sorted(kinds) == sorted([("margin_hike", "12:00"), ("closeonly_on", "13:00"),
                                    ("closeonly_off", "14:00"), ("margin_cut", "14:00")])


def test_swap_change_flip_and_mode_change():
    t = _terms([
        _row("2026-09-01T10:00:00+00:00"),
        _row("2026-09-01T11:00:00+00:00", swap_long=-12.0),                # diff falls
        _row("2026-09-01T12:00:00+00:00", swap_long=2.0),                  # long flips to paid
        _row("2026-09-01T13:00:00+00:00", swap_long=1.0, swap_mode=5),     # unit change
    ])
    ev = bsc.swap_events(bsc.swap_series(t, {}))
    got = [(e["kind"], e["knowable_at"][11:16], e["direction"]) for e in ev]
    assert got == [("swap_change", "11:00", -1), ("swap_change", "12:00", 1),
                   ("swap_sign_flip", "12:00", 1)]


def test_registry_reread_panel_rows_never_become_events(tmp_path):
    panel = tmp_path / "broker_swaps"
    panel.mkdir()
    rows = [{"kind": "swap_table", "symbols": ["XAUUSD"], "found_at": f"2026-09-0{i}T00:00:00",
             "swap_long": -60.0 - (i % 2) * 5, "swap_short": 30.0} for i in range(1, 8)]
    (panel / "discoveries_1.json").write_text(json.dumps(rows), "utf-8")
    assert bsc._panel_rows(panel) == {}
    assert bsc._PANEL_SKIPPED["registry_reread_rows"] == 7
    rows[0]["captured_by"] = "mt5desk.tape --terms-only"
    (panel / "discoveries_1.json").write_text(json.dumps(rows), "utf-8")
    assert len(bsc._panel_rows(panel)["XAUUSD"]) == 1


def test_carry_rank_change_within_class(tmp_path):
    syms = [f"S{i}" for i in range(6)]
    reg = {s: {"asset_class": "Forex"} for s in syms}
    rows = []
    for day, flip in (("2026-09-01", False), ("2026-09-02", True)):
        for i, s in enumerate(syms):
            carry = float(i)
            if flip and s == "S0":
                carry = 10.0                                   # bottom -> top tercile
            rows.append(_row(f"{day}T21:00:00+00:00", sym=s, swap_mode=5, swap_long=carry,
                             swap_short=0.0))
    ev, status = bsc.carry_rank_events(_terms(rows), reg, tmp_path)
    assert status["status"] == "MEASURED"
    s0 = [e for e in ev if e["symbol"] == "S0"]
    assert len(s0) == 1 and s0[0]["direction"] == 1 and s0[0]["prev"] == 1 and s0[0]["new"] == 3
    assert all(e["kind"] == "carry_rank_change" for e in ev)


def test_no_tape_is_unmeasured_and_writes_nothing(tmp_path):
    store = tmp_path / "events.jsonl"
    rep = bsc.build_store(tmp_path / "none", tmp_path / "none", tmp_path, store=store)
    assert rep["tape"]["status"] == "UNMEASURED"
    assert rep["carry_rank"]["status"] == "UNMEASURED"
    assert rep["store_written"] is False and not store.exists()


# ----------------------------------------------------------------------- event families -----
def _store(tmp_path, monkeypatch, events):
    path = tmp_path / "events.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in events), "utf-8")
    monkeypatch.setenv("QUANT_BROKER_STATE_STORE", str(path))
    return path


def test_event_family_enters_on_the_broker_clock_and_modes_oppose(tmp_path, monkeypatch):
    df = _bars()
    knowable = "2026-02-02T10:20:00+00:00"            # winter: broker stamp = UTC + 2h
    _store(tmp_path, monkeypatch, [{"symbol": "XAUUSD", "kind": "margin_hike",
                                    "knowable_at": knowable, "direction": 0}])
    drift = fbs.family_broker_margin_event(df, symbol="XAUUSD", event="margin_hike",
                                           mode="drift", hold_bars=6)
    rev = fbs.family_broker_margin_event(df, symbol="XAUUSD", event="margin_hike",
                                         mode="reversal", hold_bars=6)
    assert len(drift) == len(rev) == 1
    # first bar OPENING at/after 12:20 broker time is the 13:00 bar, never the 12:00 one
    assert drift[0].time == pd.Timestamp("2026-02-02T13:00:00Z")
    assert drift[0].side == -rev[0].side
    assert fbs.family_broker_margin_event(df, symbol="XAGUSD", event="margin_hike") == []
    assert fbs.family_broker_margin_event(df, symbol="XAUUSD", event="nonsense") == []


def test_swap_family_follows_the_event_direction(tmp_path, monkeypatch):
    df = _bars()
    _store(tmp_path, monkeypatch, [
        {"symbol": "EURUSD", "kind": "swap_change", "knowable_at": "2026-03-02T08:00:00Z",
         "direction": -1},
        {"symbol": "EURUSD", "kind": "swap_change", "knowable_at": "2026-04-01T08:00:00Z",
         "direction": 1}])
    sig = fbs.family_carry_swap_drift(df, symbol="EURUSD", event="swap_change", mode="drift")
    assert [s.side for s in sig] == [-1, 1]
    rev = fbs.family_carry_swap_drift(df, symbol="EURUSD", event="swap_change",
                                      mode="reversal")
    assert [s.side for s in rev] == [1, -1]


def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    return df.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last",
         "tick_volume": "sum"}).dropna()


def test_event_families_speak_on_every_chart_with_a_wall_clock_hold(tmp_path, monkeypatch):
    """The event is a UTC instant, so it is placed on the first bar OPENING at/after it on ANY
    bar clock; only the hold is dated by the event, and it is the declared wall-clock count."""
    from mt5desk import families_orthogonal as fo
    from mt5desk.universe_registry import scale_bars
    ladder = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")
    for f in ("broker_margin_event", "carry_swap_drift", "crypto_options_state"):
        assert fo.timeframe_domain(f) == ladder, f
        assert fo.WALL_CLOCK_PARAMS[f] == ("hold_bars",), f
        assert fo.timeframe_overrides(f, "H1") == {}, f
    assert fo.timeframe_overrides("broker_margin_event", "M5") == {"hold_bars": 6 * 12}
    knowable = "2026-02-02T10:20:00+00:00"            # winter: broker stamp = UTC + 2h
    _store(tmp_path, monkeypatch, [{"symbol": "XAUUSD", "kind": "margin_hike",
                                    "knowable_at": knowable, "direction": 0}])
    h1 = _bars()
    m15 = h1.copy()
    m15 = pd.concat([m15.shift(freq=f"{15 * k}min") for k in range(4)]).sort_index()
    m15 = m15[~m15.index.duplicated()]
    for frame, tf, first in ((m15, "M15", "2026-02-02T12:30:00Z"),
                             (h1, "H1", "2026-02-02T13:00:00Z"),
                             (_resample(h1, "4h"), "H4", "2026-02-02T16:00:00Z")):
        hold = scale_bars(6, tf)
        sig = fbs.family_broker_margin_event(frame, symbol="XAUUSD", event="margin_hike",
                                             hold_bars=hold)
        assert len(sig) == 1, tf
        assert sig[0].time == pd.Timestamp(first), tf      # never a bar opening before 12:20
        assert sig[0].ttl_bars == hold, tf


def test_event_family_without_store_is_silent(tmp_path, monkeypatch):
    monkeypatch.setenv("QUANT_BROKER_STATE_STORE", str(tmp_path / "absent.jsonl"))
    assert fbs.family_carry_swap_drift(_bars(), symbol="EURUSD", event="swap_change") == []


# ----------------------------------------------------------------------------- Amihud -------
def test_normalised_impact_is_trailing():
    df = _bars(24 * 120)
    full = fam.normalised_impact(df)
    cut = 24 * 90
    part = fam.normalised_impact(df.iloc[:cut])
    assert full is not None and part is not None
    pd.testing.assert_series_equal(full.iloc[:cut], part)
    assert fam.normalised_impact(df.drop(columns=["tick_volume"])) is None


@pytest.mark.parametrize("mode", fam.MODES)
def test_amihud_family_has_no_lookahead(mode):
    df = _bars(24 * 400, seed=5)
    full = _key(fam.family_amihud_illiquidity(df, mode=mode, hold_bars=4))
    assert full, f"{mode} fired nothing on 400 days of bars"
    cut = df.index[int(len(df) * 0.75)]
    trunc = _key(fam.family_amihud_illiquidity(df[df.index < cut], mode=mode, hold_bars=4))
    before = [k for k in full if k[0] < cut.value]
    assert trunc == before or trunc == before[:-1]
    assert fam.family_amihud_illiquidity(df.drop(columns=["tick_volume"]), mode=mode) == []


def test_share_cfds_reach_amihud_only_through_the_class_book():
    from mt5desk import families_cross_sectional as xs

    from research import universe_policy as up
    assert "cross_sectional_class_illiquidity" in up.CROSS_SECTIONAL_FAMILIES
    assert set(up.CROSS_SECTIONAL_FAMILIES) == set(xs.CROSS_SECTIONAL_FAMILIES)
    equities = [s for s in json.loads((DESK / "data" / "universe" / "universe.json")
                                      .read_text("utf-8"))
                if up.is_equity(s)]
    assert equities
    sym = equities[0]
    assert up.may_hypothesise(sym, "cross_sectional_class_illiquidity")
    assert not up.may_hypothesise(sym, "amihud_illiquidity")


# ---------------------------------------------------------------------------- options -------
def test_options_z_is_trailing_and_contaminated_candidates_are_ignored(tmp_path, monkeypatch):
    rows = [{"kind": "vintage", "currency": "BTC", "ts": f"2026-08-0{i}T00:00:00+00:00",
             "atm_iv": 0.5 + 0.01 * (i % 2), "skew": -0.05, "term_slope": -0.01, "dvol": 0.45}
            for i in range(1, 7)]
    rows.append({"kind": "vintage", "currency": "BTC", "ts": "2026-08-09T00:00:00+00:00",
                 "atm_iv": 0.9, "skew": -0.05, "term_slope": -0.01, "dvol": 0.45})
    rows.append({"kind": "candidate", "currency": "BTC", "field": "skew", "z": 5.0,
                 "ts": "2026-08-08T00:00:00+00:00", "z_trusted": False})
    path = tmp_path / "v.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    monkeypatch.setenv("QUANT_OPTIONS_STATE_STORE", str(path))
    ev = fos.state_events("BTC", "atm_iv", z_threshold=1.5, min_prior=5)
    assert [ts for ts, _ in ev] == ["2026-08-09T00:00:00+00:00"] and ev[0][1] > 0
    assert fos.state_events("BTC", "skew", z_threshold=1.5, min_prior=5) == []
    df = _bars(24 * 60, start="2026-07-01")
    sig = fos.family_crypto_options_state(df, symbol="BTCUSD", field="atm_iv", mode="follow")
    con = fos.family_crypto_options_state(df, symbol="BTCUSD", field="atm_iv",
                                          mode="contrarian")
    assert len(sig) == len(con) == 1 and sig[0].side == -con[0].side
    assert sig[0].time >= utc_to_server("2026-08-09T00:00:00+00:00")
    assert fos.family_crypto_options_state(df, symbol="XAUUSD", field="atm_iv") == []
    assert fos.family_crypto_options_state(df, symbol="BTCUSD", field="iv_rv") == []


def test_percent_era_vintage_is_normalised():
    v = bsc.normalise_vintage({"currency": "ETH", "ts": "x", "atm_iv": 66.96, "skew": -16.99,
                               "term_slope": -1.4, "dvol": 0.519, "iv_rv": 2026.7}, "t")
    assert v is not None and v["unit_normalised"] is True
    assert v["atm_iv"] == pytest.approx(0.6696) and v["skew"] == pytest.approx(-0.1699)
    assert v["dvol"] == pytest.approx(0.519) and "iv_rv" not in v


def test_committed_options_store_has_no_trusted_candidate():
    rows = [json.loads(line) for line in fos.STORE.read_text("utf-8").splitlines()]
    assert rows and all(r.get("z_trusted") is False for r in rows if r["kind"] == "candidate")
    assert all(r["atm_iv"] is None or r["atm_iv"] < bsc.PERCENT_ERA_IV
               for r in rows if r["kind"] == "vintage")


# ---------------------------------------------------------------------------- triangle ------
def test_triangle_reads_time_msc_when_ts_is_missing(tmp_path, monkeypatch):
    from mt5desk import triangle_tape as tt
    ms = np.arange(1_760_000_000_000, 1_760_000_000_000 + 50 * 100, 100, dtype="int64")
    quotes = {"EURGBP": 0.85, "EURUSD": 1.10, "GBPUSD": 1.10 / 0.85,
              "AUDNZD": 1.08, "AUDUSD": 0.66, "NZDUSD": 0.66 / 1.08}
    for sym, px in quotes.items():
        d = tmp_path / sym
        d.mkdir()
        pd.DataFrame({"time_msc": ms, "bid": px * 0.9999, "ask": px * 1.0001,
                      "time": ms // 1000}).to_parquet(d / "2026-10-13.parquet")
    monkeypatch.setattr(tt, "TICKS", tmp_path)
    rows = tt.build()["rows"]
    assert [r["status"] for r in rows] == ["MEASURED_QUOTES_ONLY"] * 2
    assert rows[0]["aligned_quotes"] == 50 and rows[0]["positive_loops"] == 0


# ------------------------------------------------------------------------------ organ -------
def test_seed_accrues_under_floor_and_donates_once_with_width_one(tmp_path, monkeypatch):
    from research import proposer_common as pc
    uni = tmp_path / "universe"
    uni.mkdir()
    _bars(24 * 400, seed=9).to_parquet(uni / "US500_H1.parquet")
    _bars(24 * 400, seed=8).to_parquet(uni / "XAUUSD_H1.parquet")
    (uni / "universe.json").write_text(json.dumps({
        "US500": {"asset_class": "Indices"}, "XAUUSD": {"asset_class": "Commodities"}}), "utf-8")
    _store(tmp_path, monkeypatch, [{"symbol": "XAUUSD", "kind": "margin_hike",
                                    "knowable_at": "2026-03-02T08:00:00Z", "direction": 0}])
    monkeypatch.setenv("QUANT_OPTIONS_STATE_STORE", str(tmp_path / "none.jsonl"))
    donated: list[list[dict]] = []

    def fake_donate(source, rows, tests_run, suffix=""):
        donated.append(rows)
        assert source == bsc.SOURCE and tests_run == len(rows) and suffix
        return tmp_path / "x.json"

    monkeypatch.setattr(pc, "INTEL", tmp_path / "intel")
    monkeypatch.setattr(pc, "donate", fake_donate)
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": len(donated[-1])})
    state = tmp_path / "state.json"
    rep = bsc.seed(universe=uni, state_path=state)
    hike = [c for c in rep["cells"] if c["family"] == "broker_margin_event"
            and c["symbol"] == "XAUUSD" and c["params"]["event"] == "margin_hike"]
    assert hike and all(c["status"] == bsc.ACCRUING and c["n_events"] == 1 for c in hike)
    assert donated and all(r["declared_width"] == 1 for r in donated[0])
    assert {r["family"] for r in donated[0]} == {"amihud_illiquidity"}
    assert rep["by_item"]["N7_broker_risk"]["unmeasured_no_bars"] > 0     # no bars, named
    again = bsc.seed(universe=uni, state_path=state)
    assert again["donated_this_pass"] == 0 and len(donated) == 1         # never re-donated


def test_seed_settles_a_crashed_donation_and_stands_down_when_locked(tmp_path, monkeypatch):
    """A crash between the door and the state write is settled from the door's own file; a
    second concurrent pass holds no lock and touches nothing."""
    from research import proposer_common as pc
    uni = tmp_path / "universe"
    uni.mkdir()
    _bars(24 * 400, seed=9).to_parquet(uni / "US500_H1.parquet")
    (uni / "universe.json").write_text(json.dumps({"US500": {"asset_class": "Indices"}}),
                                       "utf-8")
    _store(tmp_path, monkeypatch, [])
    monkeypatch.setenv("QUANT_OPTIONS_STATE_STORE", str(tmp_path / "none.jsonl"))
    monkeypatch.setattr(pc, "INTEL", tmp_path / "intel")
    calls: list[int] = []

    def door(source, rows, tests_run, suffix=""):
        out = tmp_path / "intel" / source / f"discoveries_20261014_0000_{suffix}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"tests_run": tests_run}), "utf-8")
        calls.append(tests_run)
        raise RuntimeError("killed after the door")

    monkeypatch.setattr(pc, "donate", door)
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": 1})
    state = tmp_path / "state.json"
    with pytest.raises(RuntimeError):
        bsc.seed(universe=uni, state_path=state)
    assert len(calls) == 1
    rep = bsc.seed(universe=uni, state_path=state)
    assert len(calls) == 1 and rep["donation"]["recovered"] == {"landed": 1, "dropped": 0}
    st = json.loads(state.read_text("utf-8"))
    assert all(v.get("donated_at") for v in st["cells"].values()
               if v.get("status") == "DONATED")
    with pc.run_lock(state) as held:
        assert held
        locked = bsc.seed(universe=uni, state_path=state)
    assert locked["donation"]["status"] == "LOCKED" and len(calls) == 1


# ------------------------------------------------------------------------- registration -----
NEW = ("broker_margin_event", "carry_swap_drift", "amihud_illiquidity", "crypto_options_state",
       "cross_sectional_class_illiquidity")


@pytest.mark.parametrize("family", NEW)
def test_every_new_family_is_registered_with_a_mechanism_and_cluster(family):
    from mt5desk import families_orthogonal as fo

    from libs.research import alpha_clusters as ac
    from research import axis_registry as ax
    assert family in fo.ORTHOGONAL_FAMILIES
    mech, info, style = ax.FAMILY_TABLE[family]
    assert "UNKNOWN" not in (mech, info, style) and mech in ax.MECHANISM_ACTOR
    assert ac.FAMILY_CLUSTER[family]


def test_the_organ_is_an_hourly_leg_with_a_layer():
    from libs.research import layers
    from research import hourly_cycle as hc
    assert hc.LEG_DEPARTMENT["broker_state_cells"] == "discovery"
    assert hc.LEG_BUDGET_SEC["broker_state_cells"] > 600
    assert layers.LEG_LAYER["broker_state_cells"] == "prediction"
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"research/broker_state_cells.py"' in src
