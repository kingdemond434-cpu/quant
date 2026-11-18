"""B14: the BoJ Tankan assumed USDJPY rate, spot over it, as exogenous-conditioner cells.

Pinned on what makes the cell honest: the series is found by NAME (never a typed code), an
ambiguous name is UNMEASURED, no close ever sees a survey released after it, an undated release
is stamped at a conservative bound, future releases are never invented, the source is read at
most once a day through robots, and the cells are the few the mechanism asks -- level_z on H4/D1
with the mechanism's sign -- minted once.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path
from typing import Any

import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import futures_state as fs  # noqa: E402

CODE = "TKFIXTURE01"
NAME = ("Exchange Rates Projected by Enterprises (Yen/U.S. dollar) Large Enterprises "
        "Manufacturing Fiscal Year")


@pytest.fixture()
def tmp_desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(fs, "RAW", tmp_path / "raw")
    monkeypatch.setattr(fs, "SERIES", tmp_path / "series")
    monkeypatch.setattr(fs, "CALENDAR_BACKFILL", tmp_path / "calendar_backfill")
    return tmp_path


def _surveys(n: int) -> list[str]:
    return [p.strftime("%Y%m") for p in pd.date_range("2016-03-01", periods=n, freq="3MS")]


def _meta() -> dict[str, Any]:
    return {"STATUS": 200, "RESULTSET": [
        {"SERIES_CODE": CODE, "NAME_OF_TIME_SERIES": NAME},
        {"SERIES_CODE": "TKX02", "NAME_OF_TIME_SERIES": NAME.replace("Fiscal Year", "First Half")},
        {"SERIES_CODE": "TKX03", "NAME_OF_TIME_SERIES": NAME.replace("U.S. dollar", "Euro")},
        {"SERIES_CODE": "TKX04",
         "NAME_OF_TIME_SERIES": "Business Conditions DI Large Manufacturing"},
    ]}


def _data(n: int) -> dict[str, Any]:
    vals = [100.0 + 1.5 * i for i in range(n)]
    return {"STATUS": 200, "RESULTSET": [{"SERIES_CODE": CODE, "NAME_OF_TIME_SERIES": NAME,
                                          "VALUES": {"SURVEY_DATES": _surveys(n), "VALUES": vals}}]}


INDEX_HTML = """<html><body><ul>
<li>Oct. 1, 2026 <a href="x">Short-term Economic Survey of Enterprises in Japan (September 2026
Survey)</a></li>
<li>Oct 2, 2026 Tankan: The Comprehensive Data Set of the September 2026 Survey</li>
<li>Jul. 1, 2026 TANKAN Summary (June 2026 Survey)</li>
<li>Jun. 2, 2026 Planned revisions (March 2026 Survey)</li>
<li>Apr. 1, 2026 TANKAN Summary (March 2026 Survey)</li>
</ul></body></html>"""


def _getters(n: int, robots: str = "User-agent: *\nAllow: /\n"):
    calls: list[str] = []

    def get(url: str) -> Any:
        calls.append(url)
        if "getMetadata" in url:
            return _meta()
        if "getDataCode" in url:
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            assert q["code"] == [CODE] and q["db"] == ["CO"]
            return _data(n)
        raise AssertionError(url)

    def get_text(url: str) -> str:
        calls.append(url)
        if url.endswith("/robots.txt"):
            return robots
        return INDEX_HTML

    return get, get_text, calls


def _bars(start: str = "2016-01-01", days: int = 3900) -> pd.DataFrame:
    idx = pd.date_range(start, periods=days * 24, freq="h", tz="UTC")
    close = 110.0 + np.sin(np.arange(len(idx)) / 2000.0) * 10.0
    return pd.DataFrame({"open": close, "high": close + 0.1, "low": close - 0.1, "close": close},
                        index=idx)


def _src(**over: Any) -> dict[str, Any]:
    reg = json.loads(fs.REGISTRY.read_text(encoding="utf-8"))
    row = next(s for s in reg["sources"] if s["id"] == "boj_tankan")
    return {**row, **over}


def test_registry_row_is_open_on_the_read_notice_low_frequency_and_names_no_code() -> None:
    """OPEN only on the BoJ API notice read verbatim on the box, cited by URL and sha256."""
    row = _src()
    assert row["terms"] == "OPEN" and row["adapter"] == "boj_tankan"
    assert "api_notice_en.pdf" in row["note"] and "7773abb22c8a8630" in row["note"]
    assert "boj_api_notice_20261111T1051Z.md" in row["note"]
    assert row["series_code"] is None, "the code is found by name on the box, never typed"
    assert row["refresh_hours"] >= 24
    assert row["transforms"] == ["level_z"] and "H1" not in row["charts"]


def test_series_is_found_by_name_and_ambiguity_is_unmeasured() -> None:
    req, exc = _src()["name_require"], _src()["name_exclude"]
    c = fs.tankan_series_candidates(_meta(), req, exc)
    assert [r["code"] for r in c] == [CODE]
    two = {"RESULTSET": [*_meta()["RESULTSET"],
                         {"SERIES_CODE": "TKX05", "NAME_OF_TIME_SERIES": NAME + " (Plan)"}]}
    assert len(fs.tankan_series_candidates(two, req, exc)) == 2


def test_points_parse_quarter_and_month_codes() -> None:
    p = fs.tankan_points(_data(8), CODE)
    assert len(p) == 8 and p["survey"].iloc[0] == pd.Timestamp("2016-03-01")
    assert fs.tankan_survey_month("2026Q3") == pd.Timestamp("2026-09-01")
    assert fs.tankan_survey_month("2026/12") == pd.Timestamp("2026-12-01")
    assert fs.tankan_survey_month("FY2026") is None


def test_release_dates_are_read_from_the_page_and_never_invented() -> None:
    r = fs.tankan_release_dates(INDEX_HTML)
    assert r["2026-09"] == "2026-10-01"          # the comprehensive set's Oct 2 is not a release
    assert r["2026-06"] == "2026-07-01"
    assert r["2026-03"] == "2026-04-01"          # the Jun 2 revisions notice is not a release
    assert "2026-12" not in r and "2027-03" not in r


def test_known_at_is_0850_tokyo_or_a_conservative_bound() -> None:
    at, rule = fs.tankan_known_at(pd.Timestamp("2026-09-01"), {"2026-09": "2026-10-01"})
    assert str(at) == "2026-09-30 23:50:00+00:00" and rule == "published_release_date"
    at, rule = fs.tankan_known_at(pd.Timestamp("2026-12-01"), {})
    assert rule == "conservative_bound" and at > pd.Timestamp("2027-01-31", tz="UTC")


def test_no_close_sees_a_survey_released_after_it() -> None:
    assumed = fs.tankan_points(_data(40), CODE)
    releases = {"2025-09": "2025-10-01"}
    day, rel, facts = fs.tankan_gap_frames(assumed, releases, _bars())
    assert len(day) > 1000 and len(rel) >= 30
    assert facts["stamped_by"]["published_release_date"] == 1
    # recompute the assumption each daily row used and check it was public before the close
    known = sorted(fs.tankan_known_at(s, releases)[0] for s in assumed["survey"])
    for t in day["available_time"].iloc[::97]:
        usable = [k for k in known if k <= pd.Timestamp(t) - fs.BROKER_AHEAD]
        assert usable, "a row before the first survey was emitted"
    assert (rel["available_time"] > rel["event_time"]).all()
    # adding a later survey never changes an earlier row
    day2, _r, _f = fs.tankan_gap_frames(fs.tankan_points(_data(39), CODE), releases, _bars())
    n = len(day2)
    cut = day2["available_time"] < pd.Timestamp(known[38])
    pd.testing.assert_series_equal(day["gap_pct"].iloc[:n][cut.to_numpy()].reset_index(drop=True),
                                   day2["gap_pct"][cut].reset_index(drop=True))


def test_collect_reads_once_a_day_through_robots(tmp_desk: Path) -> None:
    get, get_text, calls = _getters(40)
    state: dict[str, Any] = {}
    notes: list[dict[str, Any]] = []
    now = pd.Timestamp("2026-11-11 10:00", tz="UTC").to_pydatetime()
    a, _r, f = fs.tankan_collect(_src(terms="OPEN"), get, get_text, state, notes, now)
    assert len(a) == 40 and state["boj_tankan"]["code"] == CODE
    assert any(c.endswith("/robots.txt") for c in calls)
    assert f["next_release"].startswith("UNMEASURED")
    n = len(calls)
    later = pd.Timestamp("2026-11-11 20:00", tz="UTC").to_pydatetime()
    a2, _r, _f = fs.tankan_collect(_src(terms="OPEN"), get, get_text, state, notes, later)
    assert len(calls) == n and len(a2) == 40, "a second read inside refresh_hours fetches nothing"


def test_robots_refusal_fetches_nothing_and_is_unmeasured(tmp_desk: Path) -> None:
    get, get_text, calls = _getters(40, robots="User-agent: *\nDisallow: /\n")
    notes: list[dict[str, Any]] = []
    a, _r, _f = fs.tankan_collect(_src(terms="OPEN"), get, get_text, {}, notes)
    assert a.empty and not any("getMetadata" in c or "getDataCode" in c for c in calls)
    assert any(n.get("why") == "robots disallows" for n in notes)


def test_hard_stop_is_recorded(tmp_desk: Path) -> None:
    def get(url: str) -> Any:
        raise fs.HardStop(429, url)

    state: dict[str, Any] = {}
    fs.tankan_collect(_src(terms="OPEN"), get, lambda u: "User-agent: *\nAllow: /\n", state, [])
    assert state["hard_stops"]["boj_tankan"]["code"] == 429


def test_tankan_mints_few_distinct_signed_exogenous_cells(tmp_desk: Path) -> None:
    get, get_text, _calls = _getters(40)
    reg = {"sources": [_src(terms="OPEN")]}
    built, frames, _notes = fs.build_market_series(
        reg, get=get, state={}, bars=lambda s: _bars() if s == "USDJPY" else None,
        get_text=get_text)
    assert {"boj_tankan_usdjpy_gap", "boj_tankan_usdjpy_release"} <= set(built)
    uni = frozenset({"USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "JPN225"})
    plan = [p for p in fs.cell_plan(built, frames, uni) if p[0].startswith("boj_tankan")]
    assert {p[2] for p in plan} == {"level_z"} and {p[4] for p in plan} == {"H4", "D1"}
    assert len(plan) == len(set(plan)) == 2 * 5 * 2
    got: list[dict[str, Any]] = []

    def enqueue(**kw: Any) -> tuple[str, bool]:
        got.append(kw)
        return "c", True

    state: dict[str, Any] = {}
    fs.mint(built, frames, uni, state, dry_run=False, enqueue=enqueue)
    tk = [g for g in got if g["source_id"].startswith("boj_tankan")]
    assert len(tk) == 20
    assert all(g["family"] == "exogenous_conditioner" and g["params"]["side_when_high"] == -1
               for g in tk)
    got.clear()
    fs.mint(built, frames, uni, state, dry_run=False, enqueue=enqueue)
    assert not got, "a cell is minted once in its life"


def test_no_history_is_unmeasured_not_silent(tmp_desk: Path) -> None:
    reg = {"sources": [_src(terms="OPEN")]}
    built, _frames, notes = fs.build_market_series(reg, get=None, state={},
                                                   bars=lambda s: None)
    assert not any(k.startswith("boj_tankan") for k in built)
    assert any(n.get("source") == "boj_tankan_usdjpy_gap" and n["status"] == "UNMEASURED"
               for n in notes)


def test_the_conditioner_reads_the_lake_series(tmp_desk: Path) -> None:
    from mt5desk.family_exogenous_conditioner import conditioner
    get, get_text, _c = _getters(40)
    _built, frames, _n = fs.build_market_series(
        {"sources": [_src(terms="OPEN")]}, get=get, state={}, bars=lambda s: _bars(), get_text=get_text)
    for sid, f in frames.items():
        fs._write_series(sid, f)
    s = conditioner("boj_tankan_usdjpy_gap", "gap_pct", "level_z", root=fs.SERIES)
    assert s is not None and len(s) > 100


def test_a_held_row_fetches_nothing(tmp_desk: Path) -> None:
    calls: list[str] = []

    def get(url: str) -> Any:
        calls.append(url)
        raise AssertionError("a HELD source must not be fetched")

    notes: list[dict[str, Any]] = []
    fs.tankan_collect(_src(terms="HELD"), get, lambda u: calls.append(u) or "", {}, notes)
    assert calls == []
