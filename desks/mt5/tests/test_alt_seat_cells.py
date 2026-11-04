"""The alt seats' rows become exogenous_conditioner cells, or a named refusal, and the fence sees
a seat that holds convertible rows past one cycle.

* a reading becomes a PIT series point at its first sighting; a re-scraped identical reading is
  not a second point; a youtube video is counted once, on the day it was first seen, and a day
  the collector never ran carries no point;
* the compiler mints cells only once the column has history (SERIES_ACCRUING before), dedupes
  a thousand readings into one cell per instrument (one trial), and refuses the constant 13F
  notice, an impossible survey reading and a share CFD by name -- never deepening them;
* `check_conversion_debt.alt_seat_hold` is RED for a convertible row uncompiled past a cycle,
  OK for a fresh one, UNMEASURED with no report.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import alt_seat_cells as asc  # noqa: E402

NOW = datetime(2026, 10, 14, 12, tzinfo=UTC)
UNI = {"US500", "NAS100", "XAUUSD", "AUDUSD", "NZDUSD", "Apple", "XTIUSD"}


def _fg(score: float, at: datetime) -> dict:
    return {"source": "cnn_fear_greed", "type": "sentiment_reading", "score": score,
            "symbols": ["US500", "NAS100"], "available_time": at.isoformat(),
            "ingested_time": at.isoformat()}


def _series_root(tmp_path: Path, seat: str, column: str, n: int) -> Path:
    root = tmp_path / "series"
    pts = [{"event_time": (NOW - timedelta(days=n - i)).isoformat(),
            "available_time": (NOW - timedelta(days=n - i)).isoformat(), column: float(i % 7)}
           for i in range(n)]
    asc.write_series(seat, pts, root)
    return root


def test_readings_and_named_refusals() -> None:
    assert asc.readings("fear_greed", _fg(33.3, NOW)) == ({"score": 33.3}, None)
    assert asc.readings("fear_greed", {**_fg(133.0, NOW)})[1] == "IMPOSSIBLE_READING"
    # the measured AAII defect: 75% bull and 70.3% bear on one survey is two unrelated numbers
    bad = {"source": "aaii", "type": "extreme_sentiment", "bullish_pct": 75.0,
           "bearish_pct": 70.3}
    assert asc.readings("aaii", bad)[1] == "IMPOSSIBLE_READING"
    ok = {**bad, "bearish_pct": 20.0}
    assert asc.readings("aaii", ok)[0]["bull_bear_spread"] == 55.0
    assert asc.readings("aaii", {"source": "aaii_sentiment", "kind": "fetch_error"})[1] \
        == "OPERATIONAL_ROW"
    assert asc.readings("sec_edgar", {"type": "13f_filing", "fund": "Bridgewater"})[1] \
        == "NO_INFORMATION"
    assert asc.readings("shipping", {"type": "bdi", "value": 0})[1] == "IMPOSSIBLE_READING"
    assert asc.readings("fear_greed", {"type": "mystery"})[1] == "UNRECOGNISED_SHAPE"


def test_targets_apply_aliases_and_the_two_lane_mandate() -> None:
    syms, why = asc.targets({"symbols": ["USOIL", "XAUUSD"]}, UNI)
    assert why is None and syms == ["XTIUSD", "XAUUSD"]
    assert asc.targets({"symbols": ["NATGAS"]}, UNI) == ([], "NO_MT5_INSTRUMENT")
    # Apple is a share CFD in the registry: a statistical family may not mint on it
    assert asc.targets({"symbols": ["Apple"]}, UNI) == ([], "LANE_EVENT_ONLY")


def test_a_rescraped_reading_is_one_point_at_its_first_sighting() -> None:
    rows = [(_fg(33.3, NOW - timedelta(hours=h)), NOW - timedelta(hours=h))
            for h in (5, 4, 3)]                       # the same reading scraped three times
    rows.append((_fg(40.0, NOW - timedelta(hours=2)), NOW - timedelta(hours=2)))
    pts = asc.build_series("fear_greed", rows, UNI, NOW)
    assert [p["score"] for p in pts] == [33.3, 40.0]
    assert pts[0]["available_time"] == (NOW - timedelta(hours=5)).isoformat()


def test_youtube_counts_each_video_once_and_skips_days_the_seat_never_ran() -> None:
    d1, d3 = NOW - timedelta(days=3), NOW - timedelta(days=1)
    vid = {"source": "youtube", "url": "https://youtube.com/watch?v=a", "symbols": ["XAUUSD"]}
    rows = [(vid, d1), (dict(vid), d1 + timedelta(hours=3)),     # re-found next pass: same video
            ({**vid, "url": "https://youtube.com/watch?v=b"}, d1),
            ({**vid, "url": "https://youtube.com/watch?v=c"}, d3)]
    pts = asc.build_series("youtube", rows, UNI, NOW)
    assert [(p["event_time"], p["n_XAUUSD"]) for p in pts] == [
        (d1.date().isoformat(), 2), (d3.date().isoformat(), 1)]   # day 2 never ran: no point
    # a day's count is known at the END of that day, never during it
    assert pts[0]["available_time"] == (datetime(d1.year, d1.month, d1.day, tzinfo=UTC)
                                        + timedelta(days=1)).isoformat()


def test_cells_wait_for_history_then_mint_one_per_instrument(tmp_path: Path) -> None:
    short = _series_root(tmp_path, "fear_greed", "score", asc.MIN_POINTS - 1)
    assert asc.row_cells("fear_greed", _fg(20.0, NOW), UNI, short) == ([], asc.ACCRUING)
    long = _series_root(tmp_path / "b", "fear_greed", "score", asc.MIN_POINTS)
    made, why = asc.row_cells("fear_greed", _fg(20.0, NOW), UNI, long)
    assert why is None and [s for s, _p, _m in made] == ["US500", "NAS100"]
    params = made[0][1]
    assert params["source"] == "seat_fear_greed" and params["signal"] == "score"
    assert params["side_when_high"] == -1 and params["lag_hours"] == 24
    assert params["timeframe"] == "H1"       # one chart: one trial, not twelve
    # a different reading of the same survey is the SAME executable spec: charged once
    again, _ = asc.row_cells("fear_greed", _fg(80.0, NOW), UNI, long)
    assert {asc.identity(s, p) for s, p, _m in again} == \
        {asc.identity(s, p) for s, p, _m in made}


def test_the_compiler_mints_structured_alt_state_and_never_deepens_a_refusal(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import miner_candidate_compiler as mcc
    root = _series_root(tmp_path, "fear_greed", "score", asc.MIN_POINTS + 5)
    monkeypatch.setattr(asc, "SERIES_DIR", root)
    cands, disp = mcc.compile_row("cnn_fear_greed", _fg(20.0, NOW), UNI)
    assert disp == "STRUCTURED_ALT_STATE"
    assert {c["family"] for c in cands} == {"exogenous_conditioner"}
    assert {c["symbol"] for c in cands} == {"US500", "NAS100"}
    assert all(c["mechanism_status"] == "NAMED" for c in cands)
    assert mcc.compile_row("sec_edgar", {"source": "sec_edgar", "type": "13f_filing",
                                         "symbols": ["US500"]}, UNI)[1] \
        == "ALT_SEAT_NO_INFORMATION"
    assert mcc.compile_row("shipping", {"source": "shipping", "type": "bdi", "value": 3000,
                                        "symbols": ["AUDUSD"]}, UNI)[1] == "SERIES_ACCRUING"


def _report(age_h: float, unconverted: int) -> dict:
    seen = NOW - timedelta(hours=age_h)
    return {"generated_utc": NOW.isoformat(), "status": "OK",
            "seats": {"fear_greed": {"rows": 10, "convertible": 4, "converted": 4 - unconverted,
                                     "unconverted": unconverted, "series_accruing": 0,
                                     "unconvertible_by_reason": {},
                                     "cells_not_compiled": unconverted,
                                     "oldest_unconverted_first_seen":
                                         seen.isoformat() if unconverted else None}}}


def test_held_seats_measures_one_cycle_on_the_reports_own_clock() -> None:
    assert asc.held_seats(_report(0.5, 2)) == []                 # inside its cycle
    held = asc.held_seats(_report(2.0, 2))
    assert held and held[0]["seat"] == "fear_greed" and held[0]["unconverted"] == 2
    assert asc.held_seats(_report(5.0, 0)) == []


def _ccd():
    spec = importlib.util.spec_from_file_location(
        "check_conversion_debt", ROOT / "scripts" / "check_conversion_debt.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_fence_is_red_for_a_held_seat_and_unmeasured_without_a_report(
        tmp_path: Path) -> None:
    ccd = _ccd()
    assert ccd.alt_seat_hold(tmp_path / "absent.json")["status"] == "UNMEASURED"
    p = tmp_path / "ALT_SEAT_CELLS.json"
    p.write_text(json.dumps(_report(2.0, 3)), encoding="utf-8")
    red = ccd.alt_seat_hold(p, now=NOW)
    assert red["status"] == "BREACH" and "fear_greed" in red["why"]
    p.write_text(json.dumps(_report(0.5, 3)), encoding="utf-8")
    assert ccd.alt_seat_hold(p, now=NOW)["status"] == "OK"
    # on the desk's own host a report three cycles old is the organ not running
    p.write_text(json.dumps(_report(0.5, 0)), encoding="utf-8")
    later = NOW + timedelta(hours=ccd.ALT_SEAT_STALE_H + 1)
    assert ccd.alt_seat_hold(p, now=later)["status"] == "OK"
    assert ccd.alt_seat_hold(p, now=later, desk_host=True)["status"] == "BREACH"


def test_measure_counts_convertible_against_the_compilers_output(tmp_path: Path) -> None:
    root = _series_root(tmp_path, "fear_greed", "score", asc.MIN_POINTS)
    rows = [(_fg(20.0, NOW - timedelta(hours=3)), NOW - timedelta(hours=3)),
            ({"source": "cnn_fear_greed", "type": "sentiment_reading", "score": 500,
              "symbols": ["US500"]}, NOW)]
    made, _ = asc.row_cells("fear_greed", rows[0][0], UNI, root)
    one = {asc.identity(*made[0][:2])}
    m = asc.measure("fear_greed", rows, UNI, one, root)
    assert m["convertible"] == 1 and m["converted"] == 0 and m["unconverted"] == 1
    assert m["unconvertible_by_reason"] == {"IMPOSSIBLE_READING": 1}
    full = {asc.identity(s, p) for s, p, _m in made}
    assert asc.measure("fear_greed", rows, UNI, full, root)["converted"] == 1


def test_the_family_reads_the_seat_series_point_in_time(tmp_path: Path) -> None:
    """The cell the compiler mints runs on the family as written: a reading conditions bars
    only from a full publication day after it was first seen."""
    from mt5desk.family_exogenous_conditioner import family_exogenous_conditioner
    root = tmp_path / "series"
    start = datetime(2026, 6, 1, tzinfo=UTC)
    pts = [{"event_time": (start + timedelta(days=i)).isoformat(),
            "available_time": (start + timedelta(days=i)).isoformat(),
            "score": 50.0 + (40.0 if i == 60 else float(np.sin(i)))} for i in range(80)]
    asc.write_series("fear_greed", pts, root)
    idx = pd.date_range(start, start + timedelta(days=80), freq="1h", tz="UTC")
    close = 100 + np.cumsum(np.random.default_rng(1).normal(0, 0.1, len(idx)))
    df = pd.DataFrame({"open": close, "high": close + 0.2, "low": close - 0.2,
                       "close": close}, index=idx)
    sigs = family_exogenous_conditioner(df, source="seat_fear_greed", signal="score",
                                        transform="level_z", threshold=2.0,
                                        side_when_high=-1, lag_hours=24, series_root=root)
    spike = start + timedelta(days=60)
    assert sigs, "the extreme reading must fire"
    assert min(s.time for s in sigs) >= spike + timedelta(hours=24)
    assert all(s.side == -1 for s in sigs if s.time < spike + timedelta(days=2))


def test_a_youtube_row_without_a_video_is_a_claim_not_a_sighting() -> None:
    assert asc.readings("youtube", {"symbols": ["XAUUSD"], "patterns": ["scalping"]}) == (
        {}, "UNRECOGNISED_SHAPE")
    assert asc.readings("youtube", {"url": "https://youtube.com/watch?v=a",
                                    "symbols": ["XAUUSD"]}) == ({}, None)


# ------------------------------------------------------------------------------- audit 2026-10-14

def test_the_fence_judges_only_rows_inside_the_compilers_intake_window(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CNN F&G names XAUUSD only on its extreme-fear rows. Such a row written ten days ago lies
    outside the compiler's window: the compiler will never read it again, so it cannot hold the
    fence red. The same row inside the window is held, as it should be."""
    import os

    import miner_candidate_compiler as mcc
    uni_dir = tmp_path / "universe"
    uni_dir.mkdir()
    for s in ("US500", "NAS100", "XAUUSD"):
        (uni_dir / f"{s}_H1.parquet").write_bytes(b"")
    root = _series_root(tmp_path, "fear_greed", "score", asc.MIN_POINTS + 5)
    monkeypatch.setattr(asc, "SERIES_DIR", root)
    seat = tmp_path / "intel" / "fear_greed"
    seat.mkdir(parents=True)
    old_at = NOW - timedelta(days=mcc.WINDOW_DAYS + 3)
    fear = {**_fg(8.0, old_at), "type": "extreme_sentiment", "symbols": ["XAUUSD"]}
    old = seat / "discoveries_old.json"
    old.write_text(json.dumps([fear]), encoding="utf-8")
    os.utime(old, (old_at.timestamp(), old_at.timestamp()))
    recent_at = NOW - timedelta(hours=3)
    new = seat / "discoveries_new.json"
    new.write_text(json.dumps([_fg(40.0, recent_at)]), encoding="utf-8")
    os.utime(new, (recent_at.timestamp(), recent_at.timestamp()))
    made, _ = asc.row_cells("fear_greed", _fg(40.0, recent_at), {"US500", "NAS100"}, root)
    compiled = tmp_path / "miner_candidates.json"
    compiled.write_text(json.dumps({"compiled_at": NOW.isoformat(), "hypotheses": [
        {"symbol": s, "family": asc.FAMILY, "params": p} for s, p, _m in made]}),
        encoding="utf-8")
    cut = NOW - timedelta(days=mcc.WINDOW_DAYS)
    rep = asc.run(intel=tmp_path / "intel", universe_dir=uni_dir, compiled_path=compiled,
                  now=NOW, dry_run=True, intake_cutoff=cut)
    fg = rep["seats"]["fear_greed"]
    assert fg["rows_on_disk"] == 2 and fg["rows"] == 1
    assert fg["unconverted"] == 0 and asc.held_seats(rep) == []
    assert rep["intake_window"]["window_days"] == mcc.WINDOW_DAYS
    # the extreme-fear row INSIDE the window is judged, and held
    os.utime(old, (recent_at.timestamp(), recent_at.timestamp()))
    rep2 = asc.run(intel=tmp_path / "intel", universe_dir=uni_dir, compiled_path=compiled,
                   now=NOW, dry_run=True, intake_cutoff=cut)
    assert rep2["seats"]["fear_greed"]["unconverted"] == 1
    assert [h["seat"] for h in asc.held_seats(rep2)] == ["fear_greed"]


def test_the_compiler_publishes_its_intake_cutoff(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """The cutoff `recent_rows` itself uses: the saved cycle's, only while its resume file is
    still there; else the plain window."""
    import miner_candidate_compiler as mcc
    intel = tmp_path / "intel"
    (intel / "seat").mkdir(parents=True)
    resume = intel / "seat" / "discoveries_1.json"
    resume.write_text("[]")
    monkeypatch.setattr(mcc, "INTEL_ROOTS", (intel,))
    monkeypatch.setattr(mcc, "CURSOR", tmp_path / "absent.json")
    assert mcc.intake_cutoff(NOW) == NOW - timedelta(days=mcc.WINDOW_DAYS)
    saved = tmp_path / "cursor.json"
    saved.write_text(json.dumps({"next_path": str(resume), "row_offset": 0, "file_size": 0,
                                 "cycle_cutoff_utc": "2026-10-01T00:00:00"}))
    monkeypatch.setattr(mcc, "CURSOR", saved)
    assert mcc.intake_cutoff(NOW) == datetime(2026, 10, 1, tzinfo=UTC)
    resume.unlink()                                  # the resume file is gone: no stale window
    assert mcc.intake_cutoff(NOW) == NOW - timedelta(days=mcc.WINDOW_DAYS)
    import inspect
    assert "intake_cutoff(now" in inspect.getsource(mcc.recent_rows)


def test_a_duplicated_row_is_first_seen_in_its_earliest_file(tmp_path: Path) -> None:
    seat = tmp_path / "fear_greed"
    seat.mkdir()
    row = {"source": "cnn_fear_greed", "type": "sentiment_reading", "score": 30.0,
           "symbols": ["US500"]}
    (seat / "a_discoveries_20261010_1200.json").write_text(json.dumps([row]))
    (seat / "b_discoveries_20261001_0900.json").write_text(json.dumps([row]))
    [(got, seen, paths)] = list(asc.seat_rows_at("fear_greed", tmp_path))
    assert got == row and seen == datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    assert [p.name for p in paths] == ["b_discoveries_20261001_0900.json",
                                       "a_discoveries_20261010_1200.json"]


def test_the_lane_check_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import research.universe_policy as up

    def boom(*_a: object, **_k: object) -> bool:
        raise RuntimeError("registry unreadable")
    monkeypatch.setattr(up, "may_hypothesise", boom)
    assert asc._may_hypothesise("XAUUSD") is False


def test_first_seen_is_never_earlier_than_the_file_that_holds_the_row() -> None:
    early = NOW - timedelta(days=3)
    row = {"available_time": early.isoformat()}
    assert asc.first_seen(row, NOW) == NOW
    assert asc.first_seen({"available_time": NOW.isoformat()}, early) == NOW
    assert asc.first_seen({}, early) == early and asc.first_seen({}, None) is None
