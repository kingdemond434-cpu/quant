"""EVERY MACRO / ALT PRODUCER READS AS KNOWN AT THE DECISION TIME (Tier S AC3, 2026-10-06).

    python -m pytest desks/mt5/tests/test_bitemporal_producers.py -q

WHAT MUST NOT REGRESS:

  1. the three data_os doors (`known_series`, `known_as_of`, `pit_align`) answer through
     `BitemporalStore` and agree with the shift-then-ffill they replaced; a repeated valid stamp
     is a REVISION, admitted from its own knowledge time and never retroactively
  2. a reader's own lag constant can only LENGTHEN the declared lag (`effective_lag`)
  3. the certificate path: `orthogonal_sweep._macro_series` reads at the DECLARED fred_macro lag
     (27h, not the 24h constant) and a slow FRED series at its own cadence; `_cot_frame` serves
     exactly the release-lagged weekly series it always did
  4. fred/ecb axis points, stamped with the day they DESCRIBE, reach no reader on that day
  5. the producer census: the repo passes; a planted producer that joins a macro source by date
     with no PIT read FAILS; one reading through the store counts as routed; the floor only
     shrinks and a producer arriving outside the store fails; a store door NAMED in a comment,
     docstring or message string is not a store read (the census is AST, not text)
  6. release calendars (2026-10-07): the ECB axis waits for the next TARGET business day 12:00
     CET; H.15 / VIX / SOFR / DFF / OAS wait for the next US business day; DTWEXBGS 9 days; WTI
     its weekly EIA posting; every rule stays inside its declared worst-case `lag_s`
  7. the readers the audit named: macro_region's FRED/ECB points are KNOWLEDGE days;
     regime_allocation_contract reads each kernel state at its own series' timing;
     acquire_datasets places a frame on bars at its publisher's lag; dislocation_lab reads the
     axis's `d` key at VIXCLS's release timing; leg_factors holds no unpublished level
  8. certificates judged under a lag since lengthened are queued ONCE for re-judging through the
     gauntlet (`queue_cycle.pit_lag_rejudge`), never demoted
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(ROOT / "scripts"), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import check_known_by_date as kbd  # noqa: E402

from libs.tiers import data_os  # noqa: E402
from libs.tiers.bitemporal import BitemporalStore  # noqa: E402


# ------------------------------------------------------------------------------ 1 the doors
def _daily(n: int = 400, tz: str | None = "UTC") -> pd.Series:
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz=tz)
    return pd.Series(np.arange(n, dtype=float), index=idx)


def test_store_from_series_stamps_knowledge_and_revisions() -> None:
    s = pd.Series([1.0, 5.0], index=pd.to_datetime(["2026-03-02", "2026-03-02"], utc=True))
    store = data_os.store_from_series(s, source="fred_macro", entity="e", attribute="a")
    assert isinstance(store, BitemporalStore)
    assert [d.revision for d in store.rows] == [0, 1]
    assert store.rows[0].knowledge_time == "2026-03-03T03:00:00+00:00"


def test_known_series_matches_the_old_shift_and_keeps_the_clock() -> None:
    for tz in ("UTC", None):
        x = _daily(tz=tz)
        old = x.copy()
        old.index = old.index + pd.Timedelta(hours=27)
        assert data_os.known_series(x, "fred_macro").equals(old)


def test_known_series_takes_the_latest_revision_from_its_own_knowledge_time() -> None:
    s = pd.Series([1.0, 5.0], index=pd.to_datetime(["2026-03-02", "2026-03-02"], utc=True))
    got = data_os.known_series(s, "fred_macro")
    assert list(got.values) == [5.0] and len(got) == 1


def test_pit_align_is_latest_known_at_every_bar() -> None:
    x = _daily(30)
    bars = pd.date_range("2024-01-01", periods=30 * 24, freq="h", tz="UTC")
    got = data_os.pit_align(x, bars, source="fred_macro")
    old = x.copy()
    old.index = old.index + pd.Timedelta(hours=27)
    ref = old.reindex(old.index.union(bars)).ffill().reindex(bars)
    assert np.allclose(got.to_numpy(), ref.to_numpy(), equal_nan=True)
    assert np.isnan(got.loc["2024-01-02 02:00"])               # 26h after the first print
    assert got.loc["2024-01-02 03:00"] == 0.0                   # exactly at its knowledge time


def test_known_as_of_answers_through_the_store() -> None:
    s = pd.Series([1.0, 2.0], index=pd.to_datetime(["2026-03-02", "2026-03-03"], utc=True))
    got = data_os.known_as_of(s, "fred_macro", datetime(2026, 3, 4, 2, tzinfo=UTC))
    assert list(got.values) == [1.0]
    got = data_os.known_as_of(s, "fred_macro", datetime(2026, 3, 4, 3, tzinfo=UTC))
    assert list(got.values) == [1.0, 2.0]


# --------------------------------------------------------------------- 2 the lag only lengthens
def test_effective_lag_never_shortens_the_declaration() -> None:
    declared = data_os.lag_of("fred_macro")
    assert data_os.effective_lag("fred_macro", min_lag=timedelta(days=1)) == declared
    assert data_os.effective_lag("fred_macro", min_lag=timedelta(days=9)) == timedelta(days=9)
    assert data_os.effective_lag("fred_macro", "M2SL") > timedelta(days=50)
    assert data_os.effective_lag("fred_macro", "DTWEXBGS") >= timedelta(days=7)
    with pytest.raises(KeyError):
        data_os.effective_lag("no_such_source")


# ------------------------------------------------------------------- 3 the certificate path
@pytest.fixture()
def ortho(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import orthogonal_sweep as osw
    desk = tmp_path / "desks" / "mt5"
    (desk / "data").mkdir(parents=True)
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(osw, "BASE", desk)
    osw._cot_frame.cache_clear()
    yield osw, tmp_path
    osw._cot_frame.cache_clear()


def _write_fred(root: Path, key: str, days: pd.DatetimeIndex) -> pd.Series:
    """Writes a wandering series and returns the trailing rank `_macro_series` builds from it."""
    vals = np.random.default_rng(7).normal(size=len(days)).cumsum()
    rows = [[d.strftime("%Y-%m-%d"), float(v)] for d, v in zip(days, vals, strict=True)]
    (root / "data" / "fred_macro.json").write_text(json.dumps({"series": {key: rows}}), "utf-8")
    s = pd.Series(vals, index=days)
    return s.expanding(min_periods=250).rank(pct=True)


def test_macro_series_waits_the_series_own_release_calendar(ortho) -> None:
    osw, root = ortho
    days = pd.date_range("2024-01-01", periods=400, freq="D", tz="UTC")
    rank = _write_fred(root, "DGS10", days)
    bars = pd.date_range("2024-01-01", periods=420 * 24, freq="h", tz="UTC")
    got = osw._macro_series(bars, "DGS10")
    assert got is not None
    # the reference: each valid day at `data_os.knowledge_at` (H.15: the next US business day,
    # 23:00 UTC, plus the broker offset), the newest valid day winning at a shared instant
    known: dict[pd.Timestamp, float] = {}
    for d in days:
        if not np.isnan(rank[d]):
            known[pd.Timestamp(data_os.knowledge_at("fred_macro", d.to_pydatetime(), "DGS10"))] \
                = rank[d]
    ref = pd.Series(known).sort_index()
    ref = ref.reindex(ref.index.union(bars)).ffill().reindex(bars)
    assert np.allclose(got.to_numpy(), ref.to_numpy(), equal_nan=True)
    # a Friday print is NOT read over the weekend or on Monday: FRED posts it Monday evening
    fri = pd.Timestamp("2024-11-29", tz="UTC")          # Friday after Thanksgiving
    kt = pd.Timestamp(data_os.knowledge_at("fred_macro", fri.to_pydatetime(), "DGS10"))
    assert kt == pd.Timestamp("2024-12-03 02:00", tz="UTC")
    assert got.loc[kt - pd.Timedelta(hours=1)] != got.loc[kt] or rank[fri] == rank[
        pd.Timestamp("2024-12-01", tz="UTC")]


def test_macro_series_uses_a_slow_series_own_cadence(ortho) -> None:
    osw, root = ortho
    days = pd.date_range("2024-01-01", periods=400, freq="D", tz="UTC")
    _ = _write_fred(root, "DTWEXBGS", days)
    bars = pd.date_range("2024-01-01", periods=400 * 24, freq="h", tz="UTC")
    got = osw._macro_series(bars, "DTWEXBGS")
    assert got is not None
    lag = data_os.lag_of("fred_macro", "DTWEXBGS")
    first_known = got.first_valid_index()
    assert first_known is not None and first_known - days[0] >= lag


def test_cot_frame_is_the_release_lagged_weekly_series(ortho) -> None:
    osw, root = ortho
    days = pd.date_range("2024-01-02", "2026-03-31", freq="D")
    tuesdays = days[days.dayofweek == 1]
    daily = pd.Series(range(len(tuesdays)), index=tuesdays, dtype=float).reindex(days).ffill()
    pd.DataFrame({"XAUUSD": daily}).to_parquet(root / "data" / "cot_zcache.parquet")
    got = osw._cot_frame("XAUUSD")
    assert got is not None and list(got.columns) == ["net"]
    raw = daily.dropna().resample("W-FRI").last().dropna()
    raw.index = raw.index + pd.Timedelta(days=osw.COT_RELEASE_LAG_DAYS)
    assert got["net"].equals(raw.rename("net"))
    assert (got.index.dayofweek == 0).all()     # Monday 00:00, after Friday's release


# ------------------------------------------------------------------------ 4 the axis files
def test_axis_points_reach_no_reader_on_the_day_they_describe() -> None:
    s = pd.Series([1.0, 2.0], index=pd.to_datetime(["2026-03-02", "2026-03-03"], utc=True))
    ecb = data_os.known_axis_series("ecb", "eur_usd_ref", s)
    # next TARGET business day (Tuesday) at 12:00 CET = 11:00 UTC, plus the broker offset
    assert ecb.index[0] == pd.Timestamp("2026-03-03 14:00", tz="UTC")
    fred = data_os.known_axis_series("fred", "M2SL", s)
    assert fred.index[0] - s.index[0] >= timedelta(days=50)
    assert data_os.known_axis_series("cot", "x", s).equals(s)   # already knowable-stamped


def test_causal_lab_keys_an_axis_print_to_the_day_it_was_known() -> None:
    import causal_lab as cl
    got = cl._known_days("ecb", "eur_usd_ref", [("2026-03-02", 1.0)])
    assert got == [("2026-03-04", 1.0)]          # known 03-03 03:00 -> first whole day 03-04


def test_world_model_axis_point_waits_its_declared_lag() -> None:
    import world_model as wm
    pts = wm._points_from_rows([{"d": "2026-03-02", "v": 1.0}], "v", ("knowable_at", "d"),
                               described_lag=data_os.effective_lag("ecb_axis"))
    # a constant-lag reader of a rule-timed source takes the rule's WORST case (6 days)
    assert pts[0].available_time == "2026-03-08T00:00:00+00:00"
    stamped = wm._points_from_rows([{"knowable_at": "2026-03-02", "v": 1.0}], "v",
                                   ("knowable_at", "d"), described_lag=timedelta(days=9))
    assert stamped[0].available_time.startswith("2026-03-02T04:00")   # stamp IS knowledge


# ---------------------------------------------------------------------- 5 the producer census
def test_producer_census_passes_on_the_repo() -> None:
    doc = kbd.producer_census()
    assert doc["verdict"] == "OK", (doc["arrived"], doc["not_pit"])
    assert doc["not_pit"] == []
    assert doc["pit_routed"] + doc["not_pit_routed"] == doc["n"] > 0
    for rel in ("desks/mt5/research/orthogonal_sweep.py", "desks/mt5/research/edge_search.py",
                "desks/mt5/research/run_edges_macro_fusion_sweep.py",
                "desks/mt5/research/run_macro_conditioned_sweep.py",
                "desks/mt5/research/axis_proposer.py", "desks/mt5/research/causal_lab.py",
                "desks/mt5/research/standing_questions.py"):
        assert doc["producers"][rel]["class"] == "bitemporal", rel


def _plant(root: Path, name: str, body: str) -> None:
    d = root / "desks" / "mt5" / "research"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body, "utf-8")


def test_a_producer_joining_by_date_without_pit_fails(tmp_path: Path) -> None:
    _plant(tmp_path, "bad.py", "import pandas as pd\nFRED = 'fred_macro.json'\n"
                               "def f(s, idx):\n    return s.reindex(idx).ffill()\n")
    _plant(tmp_path, "good.py", "from libs.tiers import data_os\nFRED = 'fred_macro.json'\n"
                                "def f(s, idx):\n    return data_os.pit_align(s, idx, "
                                "source='fred_macro').reindex(idx)\n")
    doc = kbd.producer_census(tmp_path, floor=set())
    assert doc["producers"]["desks/mt5/research/bad.py"]["class"] == "not_pit"
    assert doc["producers"]["desks/mt5/research/good.py"]["class"] == "bitemporal"
    assert doc["verdict"] == "FAIL" and doc["not_pit"] == ["desks/mt5/research/bad.py"]
    assert doc["pit_routed"] == 1 and doc["not_pit_routed"] == 1


def test_the_producer_floor_only_shrinks(tmp_path: Path) -> None:
    _plant(tmp_path, "lagged.py", "COT = 'cot.json'\nRELEASE_LAG = 3\n"
                                  "def f(s, idx):\n    return s.reindex(idx)\n")
    arrived = kbd.producer_census(tmp_path, floor=set())
    assert arrived["arrived"] == ["desks/mt5/research/lagged.py"]
    assert arrived["verdict"] == "FAIL"                       # outside the store, not floored
    held = kbd.producer_census(tmp_path, floor={"desks/mt5/research/lagged.py",
                                                "desks/mt5/research/gone.py"})
    assert held["verdict"] == "OK" and held["healed"] == ["desks/mt5/research/gone.py"]
    path = tmp_path / "floor.json"
    kbd.write_producer_floor({"a.py"}, path)
    assert kbd.read_producer_floor(path) == {"a.py"}


def test_producer_counts_are_published_on_the_hourly_leg(tmp_path: Path) -> None:
    out, lag_out = tmp_path / "kbd.json", tmp_path / "lag.json"
    doc = kbd.publish(out=out, lag_out=lag_out)
    written = json.loads(out.read_text("utf-8"))["producers"]
    assert written["n"] == doc["producers"]["n"] > 0
    assert set(written["counts"]) == set(kbd.PRODUCER_CLASSES)
    assert written["pit_routed"] == written["counts"]["bitemporal"]


def test_a_store_door_named_only_in_comments_is_not_a_store_read(tmp_path: Path) -> None:
    _plant(tmp_path, "talk.py",
           '"""Reads through BitemporalStore.latest_known and data_os.pit_align."""\n'
           "# known_series(...) would be the door\nFRED = 'fred_macro.json'\n"
           "def f(s, idx):\n    print('pit_align is not called here')\n"
           "    return s.reindex(idx).ffill()\n")
    doc = kbd.producer_census(tmp_path, floor=set())
    assert doc["producers"]["desks/mt5/research/talk.py"]["class"] == "not_pit"
    assert doc["producers"]["desks/mt5/research/talk.py"]["store_calls"] == []


def test_the_census_reaches_the_allocator_libraries() -> None:
    assert {"libs/portfolio", "libs/regime"} <= set(kbd.PRODUCER_TREES)
    doc = kbd.producer_census()
    assert doc["producers"]["libs/portfolio/leg_factors.py"]["class"] == "bitemporal"
    for rel in ("desks/mt5/research/macro_region/miners.py",
                "desks/mt5/research/dislocation_lab.py", "desks/mt5/research/acquire_datasets.py",
                "desks/mt5/research/regime_allocation_contract.py"):
        assert doc["producers"][rel]["class"] == "bitemporal", rel


# ---------------------------------------------------------------------- 6 release calendars
def _at(src: str, day: str, sid: str | None = None) -> datetime:
    return data_os.knowledge_at(src, datetime.fromisoformat(day).replace(tzinfo=UTC), sid)


def test_ecb_axis_is_known_next_target_day_at_noon_cet() -> None:
    assert _at("ecb_axis", "2026-10-02") == datetime(2026, 10, 5, 14, tzinfo=UTC)   # Fri -> Mon
    assert _at("ecb_axis", "2026-04-02") == datetime(2026, 4, 7, 14, tzinfo=UTC)    # Easter
    assert _at("ecb_axis", "2026-12-24") == datetime(2026, 12, 28, 14, tzinfo=UTC)  # 25-26 shut


def test_fred_daily_series_are_weekend_and_holiday_aware() -> None:
    assert _at("fred_macro", "2026-10-02", "DGS10") == datetime(2026, 10, 6, 2, tzinfo=UTC)
    assert _at("fred_macro", "2026-07-02", "DGS10") == datetime(2026, 7, 7, 2, tzinfo=UTC)
    assert _at("fred_macro", "2026-10-02", "VIXCLS") == datetime(2026, 10, 5, 19, tzinfo=UTC)
    assert _at("fred_macro", "2026-10-02", "SOFR") == datetime(2026, 10, 5, 19, tzinfo=UTC)
    assert _at("fred_macro", "2026-10-01", "DFF") == datetime(2026, 10, 3, 2, tzinfo=UTC)
    assert _at("fred_macro", "2026-10-02", "BAMLH0A0HYM2") == datetime(2026, 10, 6, 2,
                                                                       tzinfo=UTC)
    # WTI: Monday's spot waits for the Wednesday-after-the-week release (+1 day of slack)
    assert _at("fred_macro", "2026-10-05", "DCOILWTICO") == datetime(2026, 10, 16, 2, tzinfo=UTC)
    assert data_os.lag_of("fred_macro", "DTWEXBGS") == timedelta(days=9)
    assert _at("fred_macro", "2026-10-05", "DTWEXBGS") == datetime(2026, 10, 14, tzinfo=UTC)


def test_every_rule_stays_inside_its_declared_worst_case() -> None:
    rules = [("ecb_axis", None)] + [("fred_macro", k) for k, e in data_os.FRED_SERIES_LAGS.items()
                                    if e.get("rule")]
    assert len(rules) >= 10
    for src, sid in rules:
        bound = data_os.lag_of(src, sid)
        day = datetime(2019, 1, 1, tzinfo=UTC)
        while day < datetime(2031, 1, 1, tzinfo=UTC):
            got = data_os.knowledge_at(src, day, sid)
            assert day < got <= day + bound, (src, sid, day, got)
            day += timedelta(days=1)


# ----------------------------------------------------------------- 7 the readers the audit named
def test_macro_region_points_are_knowledge_days_and_join_forward(tmp_path: Path,
                                                                  monkeypatch: pytest.MonkeyPatch
                                                                  ) -> None:
    from macro_region import miners as mm
    pts = [{"d": d, "v": float(i)} for i, d in enumerate(
        ["2026-10-01", "2026-10-02", "2026-10-05"])]           # Thu, Fri, Mon
    (tmp_path / "fred.json").write_text(json.dumps({"series": {"DGS10": {"points": pts}}}))
    monkeypatch.setattr(mm, "AXES_DIR", tmp_path)
    got = mm.default_series("fred:DGS10")
    # Thu -> known Sat 02:00 broker -> usable Sun; Fri -> Tue 02:00 -> Wed; Mon -> Wed 02:00 -> Thu
    assert got == [("2026-10-04", 0.0), ("2026-10-07", 1.0), ("2026-10-08", 2.0)]
    # no stamp is on or before the day the value DESCRIBES
    assert all(k > d["d"] for (k, _), d in zip(got, pts, strict=True))


def test_regime_contract_reads_each_state_at_its_own_series_timing(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import regime_allocation_contract as rac

    from libs.portfolio import macro_state as ms
    days = pd.date_range("2026-01-01", periods=60, freq="D")
    states = {d: {k.strftime("%Y-%m-%d"): 0.5 for k in days} for d in ms.KERNEL_DIMS}
    monkeypatch.setattr(ms, "daily_states", lambda *a, **k: {"states": states})
    seen: list[str | None] = []
    real = data_os.store_from_series

    def spy(*a, **k):
        seen.append(k.get("series_id"))
        return real(*a, **k)
    monkeypatch.setattr(data_os, "store_from_series", spy)
    rac.macro_weights(["2026-02-10"], "2026-02-20")
    assert seen == [ms.SERIES[d] for d in ms.KERNEL_DIMS]
    assert "DTWEXBGS" in seen


def test_acquired_series_reads_at_the_publishers_lag(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    import acquire_datasets as acq
    days = pd.date_range("2026-01-01", periods=60, freq="D")
    path = tmp_path / "x.parquet"
    pd.Series(np.arange(60, dtype=float), index=days, name="value").to_frame().to_parquet(path)
    reg = {"series": {"ecb_usd": {"path": str(path), "host": "data-api.ecb.europa.eu",
                                  "pit_authority": True},
                      "crawled": {"path": str(path), "host": "example.org",
                                  "pit_authority": True}}}
    (tmp_path / "registry.json").write_text(json.dumps(reg))
    monkeypatch.setattr(acq, "REGISTRY", tmp_path / "registry.json")
    bars = pd.date_range("2026-01-01", periods=60 * 24, freq="h", tz="UTC")
    got = acq.acquired_series(bars)
    # the old forward-fill handed 2026-01-05 its own value at midnight; the ECB rule waits for
    # the next TARGET day (01-06) at 14:00 UTC-with-offset
    assert got["ecb_usd"].loc["2026-01-05 00:00"] == 0.0          # Fri 01-02 waits for Monday
    assert got["ecb_usd"].loc["2026-01-06 13:00"] == 3.0
    assert got["ecb_usd"].loc["2026-01-06 14:00"] == 4.0
    # an unknown publisher waits the fallback 20 days
    assert np.isnan(got["crawled"].loc["2026-01-20 23:00"])
    assert got["crawled"].loc["2026-01-21 00:00"] == 0.0
    assert acq.acquired_series()["ecb_usd"].index[0] == days[0]   # no clock: valid-dated


def test_dislocation_lab_reads_the_axis_d_key_at_vix_timing() -> None:
    from types import SimpleNamespace

    import dislocation_lab as dl
    ctx = SimpleNamespace(fred={"series": {"VIXCLS": {"points": [{"d": "2026-10-01", "v": 20.0},
                                                                 {"d": "2026-10-02", "v": 30.0}]}}})
    pts = dl._vix_points(ctx)                                       # type: ignore[arg-type]
    assert [v for _, v in pts] == [20.0, 30.0]
    stamps, vals = dl._vix_known(pts)
    assert list(vals) == [20.0, 30.0]
    assert pd.Timestamp(stamps[1]) == pd.Timestamp("2026-10-05 19:00")   # Fri -> Mon 16:00+3


def test_leg_factors_hold_no_unpublished_level(tmp_path: Path) -> None:
    from libs.portfolio import leg_factors
    days = pd.date_range("2026-09-01", "2026-10-02", freq="D")
    doc = {"series": {"VIXCLS": [[d.strftime("%Y-%m-%d"), 20.0 + i] for i, d in enumerate(days)],
                      "DGS10": [[d.strftime("%Y-%m-%d"), 4.0] for d in days]}}
    p = tmp_path / "fred.json"
    p.write_text(json.dumps(doc))
    asof = datetime(2026, 10, 3, 12, tzinfo=UTC)   # Saturday: Thursday's VIX is out, Friday's not
    got = leg_factors._macro_changes(p, as_of=asof)
    assert got["d_vix"].index[-1] == "2026-10-01"


# ------------------------------------------------------------------ 8 the re-judge, not a veto
def test_certificates_under_a_lengthened_lag_are_queued_once(tmp_path: Path) -> None:
    from libs.ops import queue_cycle as qc
    from libs.ops.task_queue import TaskQueue
    (tmp_path / "desks" / "mt5" / "reports").mkdir(parents=True)
    canon = {"survivors": {
        "dollar": {"shadow_spec": {"family": "macro_conditional", "symbol": "EURUSD"},
                   "gated_at": "2026-09-01T00:00:00+00:00"},
        "vix": {"shadow_spec": {"family": "macro_conditional",
                                "params": {"input_source": "fred:VIXCLS"}},
                "gated_at": "2026-09-01T00:00:00+00:00"},
        "money": {"shadow_spec": {"family": "macro_conditional",
                                  "params": {"input_source": "fred:M2SL"}}},
        "breakout": {"shadow_spec": {"family": "session_range_breakout"}}}}
    (tmp_path / "desks" / "mt5" / "reports" / "UNIVERSAL_SURVIVORS.json").write_text(
        json.dumps(canon))
    q = TaskQueue(tmp_path / "q.jsonl")
    first = qc._pit_lag_rejudge(tmp_path, q)
    assert len(first["queued"]) == 1
    tasks = list(q.tasks().values())
    assert [t.kind for t in tasks] == ["recertify"]
    certs = tasks[0].payload["certificates"]
    assert certs == {"DTWEXBGS": ["dollar (gauntlet_default)"], "VIXCLS": ["vix (recorded)"]}
    assert "demoted" in tasks[0].payload["remedy"]                # says it demotes nothing
    q.complete(tasks[0].id, "w")
    again = qc._pit_lag_rejudge(tmp_path, q)                      # once per revision, ever
    assert again["queued"] == [] and len(q.tasks()) == 1
    assert "pit_lag_rejudge" in qc.PRODUCERS
    empty = qc._pit_lag_rejudge(tmp_path / "nowhere", TaskQueue(tmp_path / "q2.jsonl"))
    assert empty["status"] == "UNMEASURED"
