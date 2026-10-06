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
     shrinks and a producer arriving outside the store fails
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


def test_macro_series_waits_the_declared_lag_not_the_constant(ortho) -> None:
    osw, root = ortho
    days = pd.date_range("2024-01-01", periods=400, freq="D", tz="UTC")
    rank = _write_fred(root, "DGS10", days)
    bars = pd.date_range("2024-01-01", periods=400 * 24, freq="h", tz="UTC")
    got = osw._macro_series(bars, "DGS10")
    assert got is not None
    hour = pd.Timedelta(hours=1)
    for prev, last in zip(days[300:-2], days[301:-1], strict=True):
        if rank[prev] == rank[last]:
            continue
        # 24-26h after its valid day the old 24h shift had already admitted it; the declared
        # 27h has not -- the bar still reads the previous print
        for h in (24, 25, 26):
            assert got.loc[last + h * hour] == rank[prev]
        assert got.loc[last + 27 * hour] == rank[last]


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
    assert ecb.index[0] == pd.Timestamp("2026-03-03 03:00", tz="UTC")
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
    assert pts[0].available_time == "2026-03-03T03:00:00+00:00"
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
