"""Two families the judge could only ever call never_fires, and why one of them stays that way.

event_reaction: no BAR_CLOCK.json meant `to_bar_time` dropped every event, and the calendar reader
saw the last 60 vintage files only (one week; the gzip rollups unparsed). The clock is now also
MEASURED from the desk's own release calendar against the bars' range spike
(`libs/research/bar_clock_release.py`), never guessed; and the reader reads every vintage.

lvc_asia_london: the M5 ATR basis is the pinned source's own (`InpATRTimeframe = PERIOD_M5`), so
its never_fires is a true verdict and is not touched here.
"""
from __future__ import annotations

import gzip
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[3]
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_ROOT), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import bar_clock as bc  # noqa: E402
from libs.research import bar_clock_release as rel  # noqa: E402

#: Twelve releases inside summer 2026: seven USD, five CAD, stamped as the calendar stamps them.
_USD = [pd.Timestamp(f"2026-07-{d:02d}T08:30:00-04:00") for d in (2, 7, 9, 14, 16, 21, 23)]
_CAD = [pd.Timestamp(f"2026-07-{d:02d}T10:00:00-04:00") for d in (3, 8, 10, 15, 17)]
_RELEASES = _USD + _CAD
#: Three USD-quoted voters and one cross that reads only the CAD releases.
_VOTERS = ("EURUSD", "GBPUSD", "USDJPY", "AUDCAD")


def _calendar(root: Path, rows: list[tuple[str, str]]) -> None:
    base = root / Path(*rel.CALENDAR_REL.split("/"))
    base.mkdir(parents=True, exist_ok=True)
    doc = [{"kind": "calendar_vintage", "title": "release", "symbols": [ccy],
            "impact": "High", "event_date": stamp} for stamp, ccy in rows]
    (base / "discoveries_20260729_0000.json").write_text(json.dumps(doc), encoding="utf-8")


def _rows(usd=_USD, cad=_CAD) -> list[tuple[str, str]]:
    return [(t.isoformat(), "USD") for t in usd] + [(t.isoformat(), "CAD") for t in cad]


def _bars(root: Path, symbol: str, offset_of, seed: int, skip=()) -> None:
    """H1 bars on a broker clock; each release's spike sits on the bar `offset_of(release)` hours
    ahead of UTC. Bars at `skip` (labels) are deleted, as a gap in the history would."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-06-25", "2026-08-05", freq="1h")
    close = 1.0 + np.cumsum(rng.normal(0, 1e-4, len(idx)))
    width = np.abs(rng.normal(1e-3, 2e-4, len(idx)))
    frame = pd.DataFrame({"open": close, "high": close + width, "low": close - width,
                          "close": close}, index=idx)
    for t in _RELEASES:
        label = (t.tz_convert("UTC").tz_localize(None)
                 + pd.Timedelta(hours=offset_of(t))).floor("1h")
        frame.loc[label, "high"] = frame.loc[label, "close"] + 0.02
    frame = frame.drop(index=[x for x in skip if x in frame.index])
    base = root / Path(*rel.UNIVERSE_REL.split("/"))
    base.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(base / f"{symbol}_H1.parquet")


def _tree(tmp_path: Path, offsets: dict[str, int], rows=None) -> Path:
    rel._CACHE.clear()
    _calendar(tmp_path, rows if rows is not None else _rows())
    for i, (sym, off) in enumerate(offsets.items()):
        _bars(tmp_path, sym, lambda t, o=off: o, seed=i)
    return tmp_path


def _july(h: int = 12) -> datetime:
    return datetime(2026, 7, 1, h, 30, tzinfo=UTC)


def test_the_release_spike_measures_the_offset_the_bars_were_built_on(tmp_path):
    for true in (3, 2):
        root = _tree(tmp_path / str(true), dict.fromkeys(_VOTERS, true))
        assert rel.offsets(root) == {"summer": true}
        win = rel.windows(root)["summer"]
        assert win["instances"] == ["summer-2026"] and win["n_releases"] == 12
        assert win["non_usd_instruments"] == ["AUDCAD"]
        assert bc.offsets(root, fallback=True) == {"summer": true}
        assert bc.sources(root) == {"summer": "release_spike"}
        got, status, why = bc.to_bar_time(_july(), root, fallback=True)
        assert status == bc.OK_RELEASE and got.hour == 12 + true
        assert "release_spike" in why and "summer-2026" in why


def test_without_opting_in_a_caller_sees_the_old_behaviour(tmp_path):
    """The three consumers that read UNMEASURED before (event_response_atlas, analyst_views,
    family_forced_flow) do not opt in, so with no BAR_CLOCK.json they still read UNMEASURED."""
    root = _tree(tmp_path, dict.fromkeys(_VOTERS, 3))
    assert rel.offsets(root) == {"summer": 3}
    assert bc.offsets(root) == {}
    got, status, _ = bc.to_bar_time(_july(), root)
    assert got is None and status == bc.UNMEASURED
    for path in ("desks/mt5/research/event_response_atlas.py", "libs/research/analyst_views.py",
                 "desks/mt5/mt5desk/family_forced_flow.py"):
        src = (_ROOT / path).read_text(encoding="utf-8")
        assert "to_bar_time(" in src and "fallback=True" not in src, path


def test_a_clock_measured_on_2026_says_nothing_about_2024_or_2025(tmp_path):
    root = _tree(tmp_path, dict.fromkeys(_VOTERS, 3))
    for when in (datetime(2024, 6, 14, 12, 30, tzinfo=UTC), datetime(2025, 7, 3, 12, 30,
                                                                      tzinfo=UTC)):
        got, status, why = bc.to_bar_time(when, root, fallback=True)
        assert got is None and status == bc.UNMEASURED, when
        assert "outside that window" in why
    assert bc.to_bar_time(datetime(2026, 8, 5, 12, 30, tzinfo=UTC), root,
                          fallback=True)[1] == bc.OK_RELEASE


def test_the_fallback_answers_only_near_the_releases_it_was_measured_on(tmp_path):
    """Measured on 2026-07-02..07-23: it answers 14 days either side, not all of summer 2026."""
    root = _tree(tmp_path, dict.fromkeys(_VOTERS, 3))
    win = rel.windows(root)["summer"]
    assert win["first"].startswith("2026-07-02") and win["last"].startswith("2026-07-23")
    for when, ok in ((datetime(2026, 6, 18, 12, 30, tzinfo=UTC), True),
                     (datetime(2026, 6, 17, 12, 0, tzinfo=UTC), False),
                     (datetime(2026, 8, 6, 12, 0, tzinfo=UTC), True),
                     (datetime(2026, 8, 7, 13, 0, tzinfo=UTC), False),
                     (datetime(2026, 5, 4, 12, 0, tzinfo=UTC), False)):
        _got, status, why = bc.to_bar_time(when, root, fallback=True)
        assert (status == bc.OK_RELEASE) is ok, (when, status, why)
        if not ok:
            assert "outside that window" in why and "+/-14 days" in why


def test_a_late_release_is_excluded_at_any_distance_and_the_rest_resolve(tmp_path):
    """A release whose own peak is LATER than the winner would be entered before its news if
    converted at the winner -- one hour out or three. That RELEASE is excluded and named; the
    instrument resolves on the rest. Over MAX_EXCLUDED_SHARE (3 of 10) it refuses. An EARLIER
    minority is placed late, never early, and resolves with nothing excluded."""
    times = _RELEASES[:10]
    cases = ((1, 4, True), (2, 4, True), (1, 5, True), (1, 6, True), (3, 4, False),
             (2, 2, True), (3, 2, True), (1, 1, True))
    for n_off, minority, resolves in cases:
        root = tmp_path / f"{n_off}_{minority}"
        odd = set(times[:n_off])
        _bars(root, "EURUSD", lambda t, o=odd, m=minority: m if t in o else 3, seed=3)
        got = rel._instrument(rel._bars(root, "EURUSD"), list(times))
        assert (got["offset_h"] == 3) is resolves, (n_off, minority, got.get("why"))
        late = minority > 3
        named = got["late_release_excluded"]
        assert [x["release"] for x in named] == ([t.isoformat() for t in sorted(odd)]
                                                 if late else [])
        assert all(x["peak_h"] == minority and x["winning_h"] == 3 for x in named)
        assert got["late_minority"] == (n_off if late else 0)
        assert got["early_minority"] == (0 if late else n_off)
        if resolves:
            supported = set(got["releases"])
            assert not supported & {x["release"] for x in named}   # an excluded one never votes
        else:
            assert "over the 20%" in got["why"]


def test_a_tie_with_a_later_hour_is_excluded_as_late(tmp_path):
    """An exact tie between the winner and a later hour is read as the later hour, so that
    release is EXCLUDED (named, never converted) and the instrument still resolves."""
    times = _RELEASES[:10]
    for tie in (False, True):
        root = tmp_path / str(tie)
        _bars(root, "EURUSD", lambda t: 3, seed=3)
        path = root / Path(*rel.UNIVERSE_REL.split("/")) / "EURUSD_H1.parquet"
        frame = pd.read_parquet(path)
        if tie:
            at3 = (times[0].tz_convert("UTC").tz_localize(None)
                   + pd.Timedelta(hours=3)).floor("1h")
            frame.loc[at3 + pd.Timedelta(hours=1)] = frame.loc[at3].to_numpy()
            frame.to_parquet(path)
        got = rel._instrument(rel._bars(root, "EURUSD"), list(times))
        assert got["offset_h"] == 3, got.get("why")
        assert got["late_release_excluded"] == ([{"release": times[0].isoformat(), "peak_h": 4,
                                                  "winning_h": 3}] if tie else [])


def _bars_at(root: Path, symbol: str, times, offset_of, seed: int = 0) -> None:
    """H1 bars spanning `times`, each release's spike on the bar `offset_of(t)` hours ahead."""
    rng = np.random.default_rng(seed)
    lo = min(times).tz_convert("UTC").tz_localize(None).floor("D") - pd.Timedelta(days=5)
    hi = max(times).tz_convert("UTC").tz_localize(None).floor("D") + pd.Timedelta(days=5)
    idx = pd.date_range(lo, hi, freq="1h")
    close = 1.0 + np.cumsum(rng.normal(0, 1e-4, len(idx)))
    width = np.abs(rng.normal(1e-3, 2e-4, len(idx)))
    frame = pd.DataFrame({"open": close, "high": close + width, "low": close - width,
                          "close": close}, index=idx)
    for t in times:
        label = (t.tz_convert("UTC").tz_localize(None)
                 + pd.Timedelta(hours=offset_of(t))).floor("1h")
        frame.loc[label, "high"] = frame.loc[label, "close"] + 0.02
    base = root / Path(*rel.UNIVERSE_REL.split("/"))
    base.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(base / f"{symbol}_H1.parquet")


def _late_season(days: tuple[int, ...], month: int = 8) -> list[pd.Timestamp]:
    return [pd.Timestamp(f"2026-{month:02d}-{d:02d}T08:30:00-04:00") for d in days]


def test_late_releases_clustered_on_a_season_boundary_refuse(tmp_path):
    """Two late releases within a week of the summer window's end (2026-09-15), with an on-time
    release after them so it is not an edge run: the offset is wrong for that span, and the
    instrument refuses. The same two late releases mid-season are isolated and excluded."""
    times = _late_season((17, 19, 21, 24, 26, 28)) + _late_season((2, 9, 11, 15), month=9)
    for late_days, refuses in ((((9, 9), (9, 11)), True), (((8, 19), (8, 24)), False)):
        late = {pd.Timestamp(f"2026-{m:02d}-{d:02d}T08:30:00-04:00") for m, d in late_days}
        root = tmp_path / str(refuses)
        _bars_at(root, "EURUSD", times, lambda t, o=late: 5 if t in o else 3)
        got = rel._instrument(rel._bars(root, "EURUSD"), list(times))
        assert len(got["late_release_excluded"]) == 2
        if refuses:
            assert got["offset_h"] is None
            assert "within 7 days of the summer window end (2026-09-15)" in got["why"]
        else:
            assert got["offset_h"] == 3, got.get("why")


def test_a_run_of_late_releases_at_the_edge_of_the_sample_refuses(tmp_path):
    """The last two releases both late: the offset changed part-way (a changeover the window
    did not catch), so the instrument refuses rather than excluding them one by one."""
    times = _late_season((3, 5, 7, 10, 12, 14, 17, 19, 21, 24))
    root = tmp_path
    _bars_at(root, "EURUSD", times, lambda t: 4 if t in set(times[-2:]) else 3)
    got = rel._instrument(rel._bars(root, "EURUSD"), list(times))
    assert got["offset_h"] is None and "unbroken run at the end" in got["why"]


def test_the_changeover_dates_are_the_real_ones():
    """EU last Sunday of October 2026 is 10-25 and US first Sunday of November is 11-01 -- the
    gap week the probe must read."""
    got = {name: day.isoformat() for day, name in rel.boundaries(2026)}
    assert got["EU autumn changeover"] == "2026-10-25"
    assert got["US autumn changeover"] == "2026-11-01"
    assert got["EU spring changeover"] == "2026-03-29"
    assert got["US spring changeover"] == "2026-03-08"
    near = [pd.Timestamp("2026-10-22T12:30:00Z"), pd.Timestamp("2026-10-28T12:30:00Z")]
    every = [pd.Timestamp("2026-10-01T12:30:00Z"), *near, pd.Timestamp("2026-11-20T12:30:00Z")]
    assert "EU autumn changeover" in rel._cluster(near, every)
    assert rel._cluster(near[:1], every) == ""                 # one late release is isolated


def test_an_excluded_release_is_never_converted_and_the_rest_convert_unchanged(tmp_path):
    """EURUSD reads one USD release at +5 against +3: that release is excluded, the season still
    resolves, and `to_bar_time` refuses THAT instant while converting its neighbours at +3 exactly
    as before. The excluded instant supports nothing in the season window."""
    rel._CACHE.clear()
    _calendar(tmp_path, _rows())
    odd = _USD[2]
    for i, sym in enumerate(_VOTERS):
        _bars(tmp_path, sym, (lambda t: 5 if t == odd else 3) if sym == "EURUSD" else
              (lambda t: 3), seed=i)
    assert rel.offsets(tmp_path) == {"summer": 3}
    win = rel.windows(tmp_path)["summer"]
    assert win["excluded_releases"] == [{"release": odd.tz_convert("UTC").isoformat(),
                                         "peak_h": 5, "instruments": ["EURUSD"]}]
    assert win["n_releases"] == 11                             # 12 minus the excluded one
    got, status, why = bc.to_bar_time(odd.tz_convert("UTC").to_pydatetime(), tmp_path,
                                      fallback=True)
    assert got is None and status == bc.EXCLUDED_LATE and "never converted" in why
    for t in (_USD[1], _USD[3], _CAD[0]):
        u = t.tz_convert("UTC").to_pydatetime()
        moved, status, _ = bc.to_bar_time(u, tmp_path, fallback=True)
        assert status == bc.OK_RELEASE and moved == u + pd.Timedelta(hours=3)
    batch = bc.convert_many([t.tz_convert("UTC").to_pydatetime() for t in _RELEASES],
                            tmp_path, fallback=True)
    assert batch["n_kept"] == 11 and batch["dropped"][bc.EXCLUDED_LATE] == 1


def test_an_unreadable_exclusion_list_converts_nothing(tmp_path, monkeypatch):
    """Fail closed: a window whose excluded_releases is not a list, or names an unparseable
    instant, cannot say which instants are excluded, so the release clock converts none."""
    root = _tree(tmp_path, dict.fromkeys(_VOTERS, 3))
    win = dict(rel.windows(root)["summer"])
    for bad in ("x", [{"release": "not a time"}]):
        monkeypatch.setattr(bc, "_release", lambda _r, b=bad: (
            {"summer": 3}, {"summer": {**win, "excluded_releases": b}}))
        got, status, _ = bc.to_bar_time(_july(), root, fallback=True)
        assert got is None and status == bc.UNMEASURED, bad


def test_the_exclusion_is_billed_two_sided_on_the_missed_growth_ledger(tmp_path, monkeypatch):
    """The cost side names each excluded release; the growth side counts the releases that
    convert because the instrument resolved instead of refusing whole (the v4.3 rule)."""
    from research import missed_growth as mg
    rel._CACHE.clear()
    _calendar(tmp_path, _rows())
    odd = _USD[2]
    for i, sym in enumerate(_VOTERS):
        _bars(tmp_path, sym, (lambda t: 5 if t == odd else 3) if sym == "EURUSD" else
              (lambda t: 3), seed=i)
    monkeypatch.setattr(mg, "ROOT", tmp_path)
    assert "measure_late_release_excluded" in mg.MEASURES
    got = mg.measure_late_release_excluded(None, {}, {})
    assert got["verdict"] == mg.UNMEASURED and got["n_excluded"] == 1
    assert got["excluded"][0]["instrument"] == "EURUSD" and got["excluded"][0]["peak_h"] == 5
    assert got["instruments_kept"] == ["summer:EURUSD"] and got["n_admitted"] == 6
    clean = tmp_path / "clean"
    _tree(clean, dict.fromkeys(_VOTERS, 3))
    monkeypatch.setattr(mg, "ROOT", clean)
    got = mg.measure_late_release_excluded(None, {}, {})
    assert got["verdict"] == mg.NOT_BINDING and got["n_excluded"] == 0


def test_the_floor_is_counted_at_the_winning_offset_not_the_largest_sample(tmp_path):
    """Audit probe: bars missing at the true offset for most releases must refuse, not resolve
    from the two that remain."""
    root = tmp_path
    rel._CACHE.clear()
    _calendar(root, _rows())
    for i, sym in enumerate(_VOTERS):
        ccy = "CAD" if sym == "AUDCAD" else "USD"
        mine = _CAD if ccy == "CAD" else _USD
        gaps = [(t.tz_convert("UTC").tz_localize(None) + pd.Timedelta(hours=3)).floor("1h")
                for t in mine[2:]]                    # only 2 releases keep a bar at +3
        _bars(root, sym, lambda t: 3, seed=i, skip=gaps)
        reading = rel._instrument(rel._bars(root, sym), list(mine))
        assert reading["offset_h"] is None, sym
        assert "winning" in reading["why"]
    assert rel.offsets(root) == {}


def test_a_mixed_history_is_refused_never_voted(tmp_path):
    """Under the winner's share, any split refuses; above it, later releases over the excluded
    share (2 of 7) refuse, one late release of seven is EXCLUDED and the season resolves, and an
    EARLIER minority resolves."""
    for n_usd, n_cad, minority, refused in ((5, 5, 2, True), (2, 1, 4, True), (1, 0, 4, False),
                                            (1, 1, 2, False)):
        root = tmp_path / f"{n_usd}_{n_cad}_{minority}"
        rel._CACHE.clear()
        _calendar(root, _rows())
        odd = set(_USD[:n_usd]) | set(_CAD[:n_cad])
        for i, sym in enumerate(_VOTERS):
            _bars(root, sym, lambda t, o=odd, m=minority: m if t in o else 3, seed=i)
        if refused:
            assert rel.offsets(root) == {}, (n_usd, n_cad, minority)
            assert "mixed history" in rel.reading(root)["per_season"]["summer"]["readings"][
                "EURUSD"]["why"]
        else:
            assert rel.offsets(root) == {"summer": 3}, rel.reading(root)["per_season"]


def test_usd_quoted_voters_alone_are_one_reading_and_refuse(tmp_path):
    root = _tree(tmp_path, {"EURUSD": 3, "GBPUSD": 3, "USDJPY": 3, "AUDUSD": 3},
                 rows=[(t.isoformat(), "USD") for t in _RELEASES])     # 12 instants, all USD
    block = rel.reading(root)["per_season"]["summer"]
    assert block["offset_h"] is None and "quotes USD" in block["why"]


def test_too_few_independent_release_instants_refuse(tmp_path):
    """Four instruments, but the CAD releases fall on the USD instants (as CAD employment does on
    NFP day): five instants read four times are five instants."""
    root = _tree(tmp_path, dict.fromkeys(_VOTERS, 3), rows=_rows(usd=_USD[:5], cad=_USD[:5]))
    block = rel.reading(root)["per_season"]["summer"]
    assert block["offset_h"] is None and "independent release instants" in block["why"]


def test_instruments_that_disagree_measure_nothing(tmp_path):
    root = _tree(tmp_path, {"EURUSD": 3, "GBPUSD": 2, "USDJPY": 3, "AUDCAD": 3})
    assert rel.offsets(root) == {}
    assert bc.to_bar_time(_july(), root, fallback=True)[1] == bc.UNMEASURED


def test_a_release_with_no_offset_of_its_own_is_never_a_reference(tmp_path):
    root = _tree(tmp_path, dict.fromkeys(_VOTERS, 3),
                 rows=[(t.tz_localize(None).isoformat(), c) for t, c in
                       [(x, "USD") for x in _USD] + [(x, "CAD") for x in _CAD]])
    assert rel.offsets(root) == {}


def test_bars_without_a_spike_give_no_clock(tmp_path):
    shifted = [(t + pd.Timedelta(days=1)).isoformat() for t in _RELEASES]
    root = _tree(tmp_path, dict.fromkeys(_VOTERS, 3),
                 rows=[(s, "USD") for s in shifted[:7]] + [(s, "CAD") for s in shifted[7:]])
    assert rel.offsets(root) == {}


def test_a_season_with_no_releases_stays_unmeasured_and_shoulders_stay_refused(tmp_path):
    root = _tree(tmp_path, dict.fromkeys(_VOTERS, 3))
    assert "winter" not in bc.offsets(root, fallback=True)
    assert bc.to_bar_time(datetime(2026, 1, 15, 12, 0, tzinfo=UTC), root,
                          fallback=True)[1] == bc.UNMEASURED
    assert bc.to_bar_time(datetime(2026, 10, 20, 12, 0, tzinfo=UTC), root,
                          fallback=True)[1] == bc.SHOULDER


def test_the_measured_file_wins_over_the_release_reading(tmp_path):
    root = _tree(tmp_path, dict.fromkeys(_VOTERS, 3))
    p = root / Path(*bc.CLOCK_REL.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"per_season": {
        "summer": {"offset_h": 2, "agrees_across_pairs": True}}}), encoding="utf-8")
    assert bc.offsets(root, fallback=True) == {"summer": 2}
    assert bc.sources(root) == {"summer": "BAR_CLOCK.json"}
    got, status, why = bc.to_bar_time(_july(), root, fallback=True)
    assert status == bc.OK and got.hour == 14 and why.startswith("BAR_CLOCK.json")


def test_the_event_family_counts_which_clock_placed_each_event(tmp_path, monkeypatch):
    from mt5desk import family_event_reaction as fer
    root = _tree(tmp_path, dict.fromkeys(_VOTERS, 3))
    monkeypatch.setattr(fer, "to_bar_time",
                        lambda when, root_=None, **kw: bc.to_bar_time(when, root, **kw))
    monkeypatch.setattr(fer, "_CONVERTED", {})
    monkeypatch.setattr(fer, "_DROPPED", {})
    events = [{"symbol": "X", "at": "2026-07-05T12:00:00+00:00"},
              {"symbol": "X", "at": "2025-07-05T12:00:00+00:00"}]
    times = fer._event_times(events, "X", clock="utc")
    assert len(times) == 1
    assert fer._CONVERTED == {bc.OK_RELEASE: 1} and fer._DROPPED == {bc.UNMEASURED: 1}


def test_the_calendar_reader_reads_every_vintage_including_gzip_rollups(tmp_path, monkeypatch):
    from research import orthogonal_sweep as inputs

    base = tmp_path / "data" / "intelligence" / "ff_calendar_vintage"
    base.mkdir(parents=True)
    stamps = pd.date_range("2026-06-01T12:30:00Z", periods=80, freq="1D")
    for t in stamps[:70]:                         # 70 snapshot files: more than the old 60
        (base / f"discoveries_{t:%Y%m%d}_0000.json").write_text(
            json.dumps([{"event_date": t.isoformat(), "impact": "High"}]), encoding="utf-8")
    with gzip.open(base / "rollup_20260901.jsonl.gz", "wt", encoding="utf-8") as fh:
        for t in stamps[70:]:
            fh.write(json.dumps({"event_date": t.isoformat()}) + "\n")
    monkeypatch.setattr(inputs, "BASE", tmp_path)
    inputs._event_index.cache_clear()
    try:
        idx = inputs._event_index()
    finally:
        inputs._event_index.cache_clear()
    assert len(idx) == 80
    assert idx.min() == stamps[0] and idx.max() == stamps[-1]


def test_lvc_defaults_are_the_pinned_sources_including_the_m5_atr():
    """The source's ATR is `iATR(_Symbol, PERIOD_M5, 14)` and its window 0.50..2.00. The port
    keeps both; a daily ATR would be a different hypothesis, not this one."""
    import inspect

    from mt5desk.families_orthogonal import family_lvc_asia_london
    sig = inspect.signature(family_lvc_asia_london).parameters
    assert sig["atr_n"].default == 14
    assert (sig["min_range_atr"].default, sig["max_range_atr"].default) == (0.50, 2.00)
    assert "atr_timeframe" not in sig          # the chart's own bars: the source's PERIOD_M5
    assert "InpATRTimeframe = PERIOD_M5" in (family_lvc_asia_london.__doc__ or "")
