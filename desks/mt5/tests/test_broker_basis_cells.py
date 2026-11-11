"""B3 broker-side signal cells and B10 CFD-vs-reference basis: series honest in time, cells through
existing families and the one intake door, every absent source named."""
from __future__ import annotations

import gzip
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.regime.session_clock import server_to_utc  # noqa: E402
from research import basis_cells as BC  # noqa: E402
from research import broker_signal_cells as B  # noqa: E402

SESSION = "s3cr3t-session-value"
NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)


def _bars(n: int = 2400, *, flat_spread: bool = False, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-06-01", periods=n, freq="h", tz="UTC")
    close = 100 + np.cumsum(rng.normal(0, 0.2, n))
    tv = rng.integers(800, 1200, n).astype(float)
    tv[-50] = 20_000.0                                   # one abnormal hour
    spread = np.zeros(n) if flat_spread else rng.integers(10, 20, n).astype(float)
    return pd.DataFrame({"open": close, "high": close + 0.3, "low": close - 0.3, "close": close,
                         "tick_volume": tv, "spread": spread, "real_volume": 0}, index=idx)


def _write_bars(d: Path, sym: str, df: pd.DataFrame) -> None:
    d.mkdir(parents=True, exist_ok=True)
    df.to_parquet(d / f"{sym}_H1.parquet")


def _panel(d: Path, sym: str, n: int = 40, flips: int = 3) -> None:
    d.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(n):
        lo = -5.0 + (1.0 if i >= n - flips * 5 and (i // 5) % 2 else 0.0)
        rows.append({"source": "broker_swaps", "kind": "swap_table", "symbols": [sym],
                     "swap_long": lo, "swap_short": 1.0,
                     "found_at": f"2026-09-{1 + i // 24:02d}T{i % 24:02d}:05:00+00:00"})
    (d / "discoveries_20260901_0000.json").write_text(json.dumps(rows[: n // 2]))
    with gzip.open(d / "rollup_20260902.jsonl.gz", "wt", encoding="utf-8") as fh:
        for r in rows[n // 2:]:
            fh.write(json.dumps(r) + "\n")


def _outlook(names: tuple[str, ...] = ("EURUSD", "XAUUSD"), long_pct: float = 60.0) -> str:
    return json.dumps({"error": False, "message": "", "symbols": [
        {"name": n, "longPercentage": long_pct, "shortPercentage": 100 - long_pct,
         "longPositions": 600, "shortPositions": 400} for n in names]})


# ------------------------------------------------------------------------------------ B3 ---
def test_activity_is_same_hour_abnormal_causal_and_stamped_true_utc_at_bar_close() -> None:
    bars = _bars()
    f, why = B.activity_frame(bars, "brk_act_EURUSD")
    assert f is not None and {"tickvol_abn", "spread_widen"} <= set(f.columns) and not why
    spike = int(np.argmax(f["tickvol_abn"].to_numpy()))
    assert f["tickvol_abn"].iloc[spike] > 2.0          # the abnormal hour reads as abnormal
    # THE BASELINE NEVER SEES THE BAR IT JUDGES: a spike at the END of the store is just as large.
    last = bars.copy()
    last.iloc[-1, last.columns.get_loc("tick_volume")] = 20_000.0
    g, _ = B.activity_frame(last, "x")
    assert g is not None and g["tickvol_abn"].iloc[-1] > 2.0
    # available_time is the bar's CLOSE in true UTC (broker stamp is New York + 7 h).
    want = server_to_utc(pd.DatetimeIndex([bars.index[-1] + pd.Timedelta(hours=1)]))[0]
    assert f["available_time"].iloc[-1] == want
    assert f["available_time"].iloc[-1] < bars.index[-1] + pd.Timedelta(hours=1)


def test_a_flat_spread_is_named_never_filled() -> None:
    f, why = B.activity_frame(_bars(flat_spread=True), "x")
    assert f is not None and "spread_widen" not in f.columns
    assert "flat or zero" in why["spread_widen"]


def test_swap_repricings_come_from_both_panel_stores_and_a_static_swap_mints_nothing(
        tmp_path: Path) -> None:
    _panel(tmp_path / "p", "AUDUSD", flips=3)
    _panel(tmp_path / "q", "EURUSD", flips=0)
    fr = B.swap_frames(tmp_path / "p")
    assert len(fr["AUDUSD"]) == 40                      # JSON files and gz rollups both read
    assert B.repricings(fr["AUDUSD"]) >= 2
    assert B.repricings(B.swap_frames(tmp_path / "q")["EURUSD"]) == 0


def test_crowd_is_official_api_hourly_robots_first_and_the_session_never_leaks(
        tmp_path: Path) -> None:
    raw = tmp_path / "raw.jsonl"
    calls: list[str] = []

    def get(url: str) -> tuple[int | None, str, str]:
        calls.append(url)
        return 200, _outlook(), ""

    st: dict = {}
    r = B.collect_crowd(st, now=NOW, offline=False, terms="OPEN", session=SESSION, get=get,
                        robots=lambda u: None, raw=raw)
    assert r["status"] == "COLLECTED" and len(calls) == 1
    assert calls[0].startswith(B.MYFXBOOK_URL)
    r = B.collect_crowd(st, now=NOW, offline=False, terms="OPEN", session=SESSION, get=get,
                        robots=lambda u: None, raw=raw)
    assert r["status"] == "NOT_DUE" and len(calls) == 1          # one call an hour at most
    assert SESSION not in raw.read_text() and SESSION not in json.dumps(st)
    fr = B.crowd_frames(raw)
    assert set(fr) == {"EURUSD", "XAUUSD"}
    assert fr["EURUSD"]["available_time"].iloc[0] == pd.Timestamp(NOW)
    assert fr["EURUSD"]["long_pos_pct"].iloc[0] == pytest.approx(60.0)


@pytest.mark.parametrize("answer,status", [
    ((403, "", "HTTP 403"), "HARD_STOP"),
    ((200, "<html>Just a moment...</html>", ""), "HARD_STOP"),
    ((200, json.dumps({"error": True, "message": "Invalid session."}), ""), "HARD_STOP"),
])
def test_a_refusal_is_a_hard_stop_that_holds(tmp_path: Path, answer, status) -> None:
    st: dict = {}
    calls: list[str] = []

    def get(url: str):
        calls.append(url)
        return answer

    r = B.collect_crowd(st, now=NOW, offline=False, terms="OPEN", session=SESSION, get=get,
                        robots=lambda u: None, raw=tmp_path / "r.jsonl")
    assert r["status"] == status and st["myfxbook"]["hard_stop"]
    later = NOW.replace(hour=20)
    r = B.collect_crowd(st, now=later, offline=False, terms="OPEN", session=SESSION, get=get,
                        robots=lambda u: None, raw=tmp_path / "r.jsonl")
    assert r["status"] == "HARD_STOP" and len(calls) == 1      # never fetched again


def test_robots_and_a_missing_session_are_named_and_fetch_nothing(tmp_path: Path) -> None:
    called: list[str] = []
    r = B.collect_crowd({}, now=NOW, offline=False, terms="OPEN", session=SESSION,
                        get=lambda u: called.append(u) or (200, "", ""),
                        robots=lambda u: "robots.txt unreadable (HTTP 503)",
                        raw=tmp_path / "r.jsonl")
    assert r["status"] == "REFUSED_BY_ROBOTS" and not called
    r = B.collect_crowd({}, now=NOW, offline=False, session=None, raw=tmp_path / "r.jsonl")
    assert r["status"] == "UNCONFIGURED"
    assert B.myfxbook_session({}, tmp_path / "absent.json") is None
    (tmp_path / "s.json").write_text(json.dumps({"session": SESSION}))
    assert B.myfxbook_session({}, tmp_path / "s.json") == SESSION


def _b3_world(tmp_path: Path) -> dict:
    uni = tmp_path / "uni"
    _write_bars(uni, "EURUSD", _bars())
    _write_bars(uni, "AUDUSD", _bars(flat_spread=True, seed=1))
    _panel(tmp_path / "panel", "AUDUSD", flips=3)
    raw = tmp_path / "raw.jsonl"
    with raw.open("w") as fh:
        for i in range(35):
            t = pd.Timestamp("2026-11-01T00:00:00Z") + pd.Timedelta(hours=i)
            fh.write(json.dumps({"symbol": "EURUSD", "long_pct": 50 + i % 7,
                                 "long_pos_pct": 55.0, "retrieval_time": t.isoformat()}) + "\n")
    return {"symbols": ["EURUSD", "AUDUSD"], "universe_dir": uni,
            "panel_dir": tmp_path / "panel", "series_root": tmp_path / "series",
            "state_path": tmp_path / "state.json", "raw": raw, "out": tmp_path / "out.json",
            "env": {}, "secrets": tmp_path / "none.json"}


def test_b3_build_mints_each_cell_once_through_registered_families(tmp_path: Path,
                                                                   monkeypatch) -> None:
    from mt5desk.families import get_family_func
    monkeypatch.setattr(B, "asset_class", lambda s: "forex")
    w = _b3_world(tmp_path)
    got: list[list[dict]] = []

    def donate(seat, rows, tests_run):
        assert seat == B.SEAT and tests_run == len(rows)
        got.append(rows)
        return tmp_path / "d.json"

    doc = B.build(now=NOW, donate=donate, counts=lambda: {"donated": len(got[-1])}, **w)
    rows = got[0]
    arms = {r["evidence"]["arm"].split(":")[0] for r in rows}
    assert arms == {"activity", "swap", "crowd"}
    for r in rows:
        assert get_family_func(r["family"]) is not None          # an existing family
        assert r["params"]["lag_hours"] == B.LAG_H == 3
        assert r["params"]["timeframe"] in ("H1", "H4")          # pinned: never re-sliced
        assert r["symbol"] in ("EURUSD", "AUDUSD")
    # AUDUSD's flat spread mints no spread cell; EURUSD's static (absent) swap mints none.
    assert not any(r["symbol"] == "AUDUSD" and r["params"].get("signal") == "spread_widen"
                   for r in rows)
    assert not any(r["symbol"] == "EURUSD" and r["family"] == "alt_series_momentum"
                   and r["params"]["signal"] == "swap_diff" for r in rows)
    assert "EURUSD" in doc["swaps"]["unmeasured"]
    assert doc["crowd"]["collective2"]["status"] == "UNMEASURED"
    assert (tmp_path / "series" / "brk_act_EURUSD.parquet").exists()
    # MINTED ONCE IN ITS LIFE: a second pass donates nothing new.
    doc2 = B.build(now=NOW, donate=donate, counts=lambda: {}, **w)
    assert len(got) == 1 and doc2["cells"]["cells_new"] == 0


def test_the_written_swap_series_fires_its_family_after_the_lag(tmp_path: Path,
                                                               monkeypatch) -> None:
    from mt5desk.family_alt_series import family_alt_series_momentum, momentum_z
    monkeypatch.setattr(B, "asset_class", lambda s: "forex")
    w = _b3_world(tmp_path)
    B.build(now=NOW, dry_run=False, donate=lambda *a, **k: None, counts=lambda: {}, **w)
    sf = pd.read_parquet(tmp_path / "series" / "brk_swap_AUDUSD.parquet")
    z = momentum_z("brk_swap_AUDUSD", "swap_diff", lookback=1, lag_hours=3,
                   root=tmp_path / "series")
    assert z is not None
    # every conditioner value is held back at least the lag behind the stamp it was known at
    assert z.index.min() >= sf["available_time"].min() + pd.Timedelta(hours=3)
    bars = pd.read_parquet(tmp_path / "uni" / "AUDUSD_H1.parquet")
    bars.index = pd.date_range("2026-08-20", periods=len(bars), freq="h", tz="UTC")
    sigs = family_alt_series_momentum(bars, source="brk_swap_AUDUSD", signal="swap_diff",
                                      lookback=1, threshold=1.0, side_when_up=1, lag_hours=3,
                                      series_root=tmp_path / "series")
    assert sigs and all(s.time >= sf["available_time"].min() for s in sigs)


def test_cells_reach_the_compiler_intake_stamped(tmp_path: Path, monkeypatch) -> None:
    """END TO END through the REAL door: proposer_common.donate writes the intake file, the
    compiler reads it with its own reader, every row is PIT-stamped and compiles to a docket cell
    with the family and params unchanged."""
    from libs.moat import registry as R
    from libs.ops import throughput as TP
    from libs.research import preregistration as PR
    from research import miner_candidate_compiler as MC
    from research import proposer_common as PC
    intel = tmp_path / "intel"
    monkeypatch.setattr(PC, "INTEL", intel)
    monkeypatch.setattr(PR, "LEDGER", tmp_path / "prereg.jsonl")
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    monkeypatch.setattr(TP, "SAMPLES", tmp_path / "throughput_samples.jsonl")
    monkeypatch.setattr(B, "asset_class", lambda s: "forex")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    try:
        doc = B.build(now=NOW, **_b3_world(tmp_path))
    finally:
        R.set_path(None)
    n = doc["cells"]["cells_planned"]
    assert n > 0 and doc["cells"]["donated"] == n
    files = sorted((intel / B.SEAT).glob("discoveries_*.json"))
    assert len(files) == 1
    assert json.loads(files[0].read_text())["tests_run"] == n          # every trial charged
    seen = 0
    for row in MC._iter_file_rows(files[0]):
        assert row["available_time"] and row["payload_hash"]
        produced, _disp = MC.compile_row(str(row["source"]), row, {"EURUSD", "AUDUSD"})
        assert produced, _disp
        for c in MC.expand_axes(produced):
            assert c["family"] == row["family"] and c["params"]["timeframe"]
            seen += 1
    assert seen == n                                 # no axis expansion added trials


# ----------------------------------------------------------------------------------- B10 ---
def _fred(dates: pd.DatetimeIndex, value: float = 70.0) -> str:
    return json.dumps({"observations": [{"date": d.strftime("%Y-%m-%d"), "value": str(value)}
                                        for d in dates] + [{"date": "2026-01-01", "value": "."}]})


def test_the_cfd_is_read_at_the_reference_minute_on_the_broker_clock() -> None:
    idx = pd.date_range("2026-07-01", "2026-07-04", freq="h", tz="UTC")
    bars = pd.DataFrame({"open": np.arange(len(idx), dtype=float) + 1.0}, index=idx)
    dates = pd.Series(["2026-07-01", "2026-07-02"])
    got = BC.cfd_at_reference(bars, dates, "14:30", "America/New_York")
    # 14:30 New York (EDT) = 21:30 broker -> the 21:00 bar's open.
    want = bars.loc[pd.Timestamp("2026-07-01 21:00", tz="UTC"), "open"]
    assert got.iloc[0] == want
    # Brent at 16:30 London (BST) = 11:30 New York = 18:30 broker -> the 18:00 bar.
    got = BC.cfd_at_reference(bars, dates, "16:30", "Europe/London")
    assert got.iloc[0] == bars.loc[pd.Timestamp("2026-07-01 18:00", tz="UTC"), "open"]


def test_basis_rows_are_available_only_once_fred_published_them() -> None:
    idx = pd.date_range("2026-07-01", periods=24 * 10, freq="h", tz="UTC")
    bars = pd.DataFrame({"open": np.full(len(idx), 71.0)}, index=idx)
    ref = pd.DataFrame({"date": ["2026-07-02", "2026-07-03"], "value": [70.0, -1.0]})
    f = BC.basis_frame("XTIUSD", ref, bars, BC.PAIRS[0])
    assert len(f) == 1                                    # a non-positive print is dropped
    assert f["basis_log"].iloc[0] == pytest.approx(np.log(71 / 70))
    # Thursday 2026-07-02's print is usable Friday 23:00 UTC, never on its own day.
    assert f["available_time"].iloc[0] == pd.Timestamp("2026-07-03 23:00", tz="UTC")


def _b10_world(tmp_path: Path) -> dict:
    uni = tmp_path / "uni"
    idx = pd.date_range("2026-07-01", "2026-11-10", freq="h", tz="UTC")
    rng = np.random.default_rng(3)
    for sym in ("XTIUSD", "NAS100"):
        _write_bars(uni, sym, pd.DataFrame({"open": 70 + rng.normal(0, 0.5, len(idx))},
                                           index=idx))
    return {"universe_dir": uni, "series_root": tmp_path / "series", "raw_dir": tmp_path / "raw",
            "state_path": tmp_path / "state.json", "out": tmp_path / "out.json",
            "env": {"FRED_API_KEY": "k3y"}, "universe": {"XTIUSD", "NAS100", "XAUUSD"}}


def test_b10_build_mints_live_pairs_once_and_names_every_other_pair(tmp_path: Path) -> None:
    from mt5desk.families import get_family_func
    days = pd.bdate_range("2026-07-01", "2026-11-09")
    fetched: list[str] = []

    def get(url: str):
        fetched.append(url)
        if "NASDAQ100" in url:
            return 403, "", "HTTP 403"
        return 200, _fred(days), ""

    got: list[list[dict]] = []

    def donate(seat, rows, tests_run):
        assert seat == BC.SEAT
        got.append(rows)
        return tmp_path / "d.json"

    w = _b10_world(tmp_path)
    doc = BC.build(now=NOW, get=get, robots=lambda u: None, donate=donate,
                   counts=lambda: {"donated": len(got[-1])}, **w)
    assert doc["pairs"]["XTIUSD"]["status"] == "LIVE"
    assert doc["pairs"]["NAS100"]["fetch"].startswith("HARD_STOP")
    assert doc["pairs"]["XBRUSD"]["status"] == "NOT_QUOTED"
    assert "XAUUSD" in doc["not_minted"] and "US500" in doc["not_minted"]
    rows = got[0]
    assert len(rows) == len(BC.TRANSFORMS) * len(BC.CHARTS)       # 4 distinct claims, one pair
    for r in rows:
        assert r["family"] == "exogenous_conditioner" and get_family_func(r["family"])
        assert r["params"]["side_when_high"] == -1 and r["params"]["lag_hours"] == 3
    assert all("k3y" not in json.dumps(x) for x in (doc, rows))  # the key is never written
    # second pass: nothing re-fetched inside the day, the hard stop holds, nothing re-minted
    n = len(fetched)
    doc2 = BC.build(now=NOW, get=get, robots=lambda u: None, donate=donate,
                    counts=lambda: {}, **w)
    assert len(fetched) == n and len(got) == 1 and doc2["cells"]["cells_new"] == 0
    assert "HARD_STOP" in doc2["pairs"]["NAS100"]["fetch"]


def test_b10_without_a_key_or_robots_fetches_nothing_and_is_unmeasured(tmp_path: Path) -> None:
    w = {**_b10_world(tmp_path), "env": {}}
    called: list[str] = []
    doc = BC.build(now=NOW, get=lambda u: called.append(u) or (200, "", ""),
                   robots=lambda u: None, donate=lambda *a, **k: None, counts=lambda: {}, **w)
    assert not called and doc["pairs"]["XTIUSD"]["status"] == BC.UNMEASURED
    assert doc["pairs"]["XTIUSD"]["fetch"].startswith("NEEDS_KEY")
    ref, why = BC.fetch_reference("DCOILWTICO", "k", get=lambda u: called.append(u),
                                  robots=lambda u: "robots.txt disallows this path")
    assert ref is None and why.startswith("REFUSED_BY_ROBOTS") and not called


def test_both_organs_are_legs_of_the_hourly_clock_with_a_layer() -> None:
    from libs.research import layers
    from research import hourly_cycle as HC
    src = (_DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    for leg, script in (("broker_signal_cells", "research/broker_signal_cells.py"),
                        ("basis_cells", "research/basis_cells.py")):
        assert leg in HC.CORE_LEGS
        assert f'"{leg}", "{script}"' in src
        assert layers.LEG_LAYER[leg] == "information"


def test_held_myfxbook_terms_fetch_nothing(tmp_path: Path) -> None:
    calls: list[str] = []

    def get(url: str) -> tuple[int | None, str, str]:
        calls.append(url)
        raise AssertionError("HELD terms must not fetch")

    r = B.collect_crowd({}, now=NOW, offline=False, session=SESSION, get=get,
                        robots=lambda u: calls.append(u) or None, raw=tmp_path / "r.jsonl")
    assert r["status"] == "TERMS_HELD" and calls == []
    assert B.MYFXBOOK_TERMS == "HELD"
