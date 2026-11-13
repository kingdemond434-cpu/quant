"""`release_surprise` (ideas N4 N6 N7 N8): four scheduled releases, first prints, no look-ahead.

  0. each parser reads its publisher's layout, and REFUSES BY NAME a layout it was not written
     for (PARSE_UNVERIFIED with a sample) instead of guessing a column;
  1. the release clocks are never early: holiday weeks move LATER, and every backfilled row's
     knowable instant is on or after the publisher's release;
  2. the axis keeps FIRST PRINTS: a later fetch never overwrites a value, it records a revision,
     and a period first seen after seeding is stamped `first_print` at the moment it was seen;
  3. the robots gate fails closed (Disallow and unreadable robots both refuse);
  4. each basis fires on a constructed surprise, on the named side, after the release instant;
     its baseline uses only rows knowable before the scored row; a revised (`backfill_latest`)
     row never reaches a cell; an absent basis refuses by name (a TypeError the builder names);
  5. the family, its proposer, the hourly leg and the capability graph are wired.
All inputs are synthetic; nothing touches the network.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_release_surprise as F  # noqa: E402

from research import release_surprise_ingest as RI  # noqa: E402


def _bars(n: int = 24 * 365 * 4, end: str = "2026-10-30 23:00", seed: int = 3) -> pd.DataFrame:
    idx = pd.date_range(end=end, periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(seed)
    close = pd.Series(3.0 * np.exp(np.cumsum(rng.normal(0, 0.001, n))), index=idx)
    return pd.DataFrame({"open": close.shift(1).fillna(close.iloc[0]), "high": close * 1.002,
                         "low": close * 0.998, "close": close, "tick_volume": 100.0}, index=idx)


# ----------------------------------------------------------------------------- fixtures
def _eia_html(levels: list[tuple[date, float]]) -> str:
    by_month: dict[tuple[int, int], list[tuple[date, float]]] = {}
    for d, v in levels:
        by_month.setdefault((d.year, d.month), []).append((d, v))
    rows = []
    for (y, m), pts in sorted(by_month.items()):
        mon = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
               "Dec"][m - 1]
        cells = "".join(f"<td class='B5'>{d:%m/%d}&nbsp;&nbsp;</td><td class='B3'>{v:,.0f}</td>"
                        for d, v in pts)
        rows.append(f"<tr><td class='B6'>&nbsp;&nbsp;{y}-{mon}</td>{cells}</tr>")
    return "<html><table class='FloatTitle'>" + "".join(rows) + "</table></html>"


def _eia_levels(start: date = date(2018, 1, 5), weeks: int = 460, shock: date | None = None,
                seed: int = 1) -> list[tuple[date, float]]:
    rng = np.random.default_rng(seed)
    out, lvl = [], 3000.0
    for k in range(weeks):
        d = start + timedelta(weeks=k)
        seasonal = 60.0 * np.sin(2 * np.pi * (d.timetuple().tm_yday / 365.25 - 0.3))
        chg = seasonal + rng.normal(0, 8)
        if shock is not None and d == shock:
            chg += 120.0
        lvl += chg
        out.append((d, round(lvl)))
    return out


def _usda_html(pts: list[tuple[date, float]]) -> str:
    hdr = ("<tr><th>Week Ending</th><th>Weekly Exports</th><th>Accumulated Exports</th>"
           "<th>Net Sales</th><th>Outstanding Sales</th><th>Next MY Net Sales</th></tr>")
    body = "".join(f"<tr><td>{d:%m/%d/%Y}</td><td>1,000</td><td>9,000</td><td>{v:,.1f}</td>"
                   f"<td>5,000</td><td>10.0</td></tr>" for d, v in pts)
    return f"<html><table>{hdr}{body}</table></html>"


def _tic_txt(months: list[tuple[date, float]]) -> str:
    hdr = ("Country Name\tCountry Code\tDate\tGross Purchases of Domestic US Treasury Bonds & "
           "Notes\tGross Sales of Domestic US Treasury Bonds & Notes\tGross Purchases of "
           "Domestic US Gov Agency Bonds\tGross Sales of Domestic US Gov Agency Bonds\t"
           "Gross Purchases of Domestic US Corporate Bonds\tGross Sales of Domestic US "
           "Corporate Bonds\tGross Purchases of Domestic US Corporate Stocks\tGross Sales of "
           "Domestic US Corporate Stocks\n")
    lines = []
    for d, net in months:
        lines.append(f"Grand Total\t99996\t{d:%Y-%m}\t{1000 + net}\t1000\t500\t500\t300\t300\t"
                     "200\t200")
        lines.append(f"Japan\t42609\t{d:%Y-%m}\t10\t5\t1\t1\t1\t1\t1\t1")
    return "U.S. Transactions with Foreign Residents\n\n" + hdr + "\n".join(lines) + "\n"


_BOJ_PAGE = """<html><body><h2>Outright Purchases of Japanese Government Bonds</h2>
<p>(Remaining Maturity of more than 5 years and up to 10 years)</p>
<table><tr><td>Planned amount of purchase</td><td>425.0 billion yen</td></tr>
<tr><td>Amount of competitive offers</td><td>1,402.3 billion yen</td></tr>
<tr><td>Amount of successful competitive offers</td><td>425.0 billion yen</td></tr></table>
<h2>Outright Purchases of Japanese Government Bonds</h2>
<p>(Remaining Maturity of more than 1 year and up to 3 years)</p>
<table><tr><td>Amount of competitive offers</td><td>1,100.0 billion yen</td></tr>
<tr><td>Amount of successful competitive offers</td><td>300.0 billion yen</td></tr></table>
</body></html>"""


# ----------------------------------------------------------------------------- 0. parsers
def test_eia_parser_reads_the_dnav_weekly_layout_and_year_rollover():
    levels = _eia_levels(start=date(2024, 12, 27), weeks=20)
    got = RI.parse_eia_storage(_eia_html(levels))
    assert got == [(d, float(v)) for d, v in levels]


def test_eia_parser_refuses_a_layout_it_was_not_written_for():
    with pytest.raises(RI.ParseUnverified) as exc:
        RI.parse_eia_storage("<html><p>Service moved</p></html>")
    assert "dnav" in exc.value.expected and "Service moved" in exc.value.sample


def test_usda_parser_sums_current_and_next_my_net_sales():
    pts = [(date(2026, 9, 4) + timedelta(weeks=k), 500.0 + k) for k in range(8)]
    got = RI.parse_usda_history(_usda_html(pts))
    assert got[0] == (date(2026, 9, 4), 510.0)
    assert len(got) == 8
    with pytest.raises(RI.ParseUnverified):
        RI.parse_usda_history("<table><tr><td>Week</td></tr></table>")


def test_tic_parser_reads_grand_total_net_of_four_domestic_classes():
    months = [(date(2024, 1, 1) + pd.DateOffset(months=k), 50.0 * k) for k in range(14)]
    months = [(m.date() if hasattr(m, "date") else m, v) for m, v in months]
    got = RI.parse_tic_s1(_tic_txt(months))
    assert got[3] == (date(2024, 4, 1), 150.0)
    assert len(got) == 14
    with pytest.raises(RI.ParseUnverified):
        RI.parse_tic_s1("Country\tDate\n")


def test_boj_parser_reads_each_operation_and_its_plan():
    ops = RI.parse_boj_results(_BOJ_PAGE, date(2026, 11, 10))
    assert [o["bucket"] for o in ops] == ["5_10Y", "1_3Y"]
    assert ops[0] == {"bucket": "5_10Y", "op_day": "2026-11-10", "offered_bn": 1402.3,
                      "purchased_bn": 425.0, "planned_bn": 425.0}
    assert ops[1]["planned_bn"] is None
    assert RI.parse_boj_results("<p>Funds-supplying operation</p>", date(2026, 1, 5)) == []
    with pytest.raises(RI.ParseUnverified):
        RI.parse_boj_results("<h2>Outright Purchases of JGBs</h2><p>more than 1 year and up to "
                             "3 years</p><p>Results to follow</p>", date(2026, 1, 5))


def test_boj_links_are_dated():
    body = '<a href="stat/of261110.htm">r</a><a href="about.htm">x</a>'
    links = RI.boj_result_links(body, "https://www3.boj.or.jp/market/en/menu_o.htm")
    assert links == [("https://www3.boj.or.jp/market/en/stat/of261110.htm", date(2026, 11, 10))]


# ----------------------------------------------------------------------------- 1. clocks
def test_release_clocks_are_never_early():
    ordinary = RI.eia_release_utc(date(2026, 10, 30))         # Fri -> Thu 5 Nov 10:30 ET
    assert ordinary == datetime(2026, 11, 5, 15, 30, tzinfo=UTC)
    thanksgiving = RI.eia_release_utc(date(2026, 11, 20))     # holiday Thu 26 Nov -> Fri noon
    assert thanksgiving == datetime(2026, 11, 27, 17, 0, tzinfo=UTC)
    assert RI.usda_release_utc(date(2026, 10, 29)) == datetime(2026, 11, 5, 13, 30, tzinfo=UTC)
    # Veterans Day (Wed 11 Nov 2026) in release week -> Friday 08:30 ET
    assert RI.usda_release_utc(date(2026, 11, 5)) == datetime(2026, 11, 13, 13, 30, tzinfo=UTC)
    assert RI.tic_backfill_utc(date(2026, 9, 1)) == datetime(2026, 11, 20, 21, 0, tzinfo=UTC)
    assert RI.boj_backfill_utc(date(2026, 11, 10)) == datetime(2026, 11, 10, 6, 0, tzinfo=UTC)


# ----------------------------------------------------------------------------- 2. first prints
def _getter(pages: dict[str, str], robots: str = "User-agent: *\nAllow: /\n"):
    def get(url: str) -> RI.Fetched:
        if url.endswith("/robots.txt"):
            return RI.Fetched(url, 200, robots)
        if url in pages:
            return RI.Fetched(url, 200, pages[url])
        return RI.Fetched(url, 404, "", "HTTP 404")
    return get


@pytest.fixture(autouse=True)
def _fresh_robots():
    RI._ROBOTS.clear()
    yield
    RI._ROBOTS.clear()


def test_axis_never_overwrites_and_stamps_new_periods_as_first_prints(tmp_path):
    url = RI.SOURCES["eia_gas_storage"]["urls"][0]
    levels = _eia_levels(start=date(2025, 1, 3), weeks=40)
    axis = tmp_path / "release_surprise.json"
    t0 = datetime(2025, 10, 20, tzinfo=UTC)
    rep = RI.run(apply=True, only=["eia_gas_storage"], now=t0,
                 getter=_getter({url: _eia_html(levels)}), axis_path=axis, report_path=None)
    assert rep["sources"]["eia_gas_storage"]["state"] == RI.OK
    doc = json.loads(axis.read_text())
    assert {r["vintage"] for r in doc["rows"]} == {RI.BACKFILL_STABLE}
    first = doc["rows"][0]
    assert datetime.fromisoformat(first["knowable_at"]) >= RI.eia_release_utc(
        date.fromisoformat(first["period"]))
    # a week later: one revision of an old week, one new week
    revised = [(d, v + (7 if k == 0 else 0)) for k, (d, v) in enumerate(levels)]
    new_d = levels[-1][0] + timedelta(weeks=1)
    revised.append((new_d, levels[-1][1] + 10))
    t1 = RI.eia_release_utc(new_d) + timedelta(minutes=12)
    RI.run(apply=True, force=True, only=["eia_gas_storage"], now=t1,
           getter=_getter({url: _eia_html(revised)}), axis_path=axis, report_path=None)
    doc = json.loads(axis.read_text())
    rows = {r["period"]: r for r in doc["rows"]}
    old = rows[levels[0][0].isoformat()]
    assert old["value"] == levels[0][1] and old["revisions"][0]["value"] == levels[0][1] + 7
    new = rows[new_d.isoformat()]
    assert new["vintage"] == RI.FIRST_PRINT
    assert datetime.fromisoformat(new["knowable_at"]) == t1


def test_robots_disallow_and_unreadable_robots_both_refuse(tmp_path):
    url = RI.SOURCES["tic_flow"]["urls"][0]
    res = RI.ingest_tic(datetime(2026, 1, 1, tzinfo=UTC),
                        _getter({url: "x"}, robots="User-agent: *\nDisallow: /\n"))
    assert res.state == RI.UNMEASURED and RI.REFUSED in res.why
    RI._ROBOTS.clear()

    def broken(u: str) -> RI.Fetched:
        return RI.Fetched(u, 500, "", "HTTP 500")
    res = RI.ingest_tic(datetime(2026, 1, 1, tzinfo=UTC), broken)
    assert res.state == RI.UNMEASURED and "unreadable" in res.why


def test_a_source_is_fetched_only_when_due():
    last = datetime(2026, 11, 5, 16, 0, tzinfo=UTC)               # after Thu's release
    st = {"last_ok_at": last.isoformat()}
    assert not RI.due("eia_gas_storage", st, last + timedelta(hours=5))
    assert RI.due("eia_gas_storage", st, last + timedelta(hours=25))
    assert RI.due("eia_gas_storage", {}, last)


# ----------------------------------------------------------------------------- 4. the family
def _eia_rows(shock: date | None, vintage: str = RI.BACKFILL_STABLE) -> list[dict]:
    lv = _eia_levels(start=date(2018, 1, 5), weeks=460, shock=shock)
    now = datetime(2027, 1, 1, tzinfo=UTC)
    return [RI._row("eia_gas_storage", "R48_WORKING_GAS_BCF", d, float(v),
                    RI.eia_release_utc(d), vintage, now) for d, v in lv]


def test_eia_basis_fires_after_release_on_the_named_side():
    shock = date(2018, 1, 5) + timedelta(weeks=440)
    rows = _eia_rows(shock)
    z = F.reading("eia_gas_storage", window=52, rows=rows)
    rel = pd.Timestamp(RI.eia_release_utc(shock))
    assert z.idxmax() == rel and z.max() > 4
    df = _bars()
    sig = F.family_release_surprise(df, basis="eia_gas_storage", move="up", min_abs=4.0,
                                    direction="short", rows=rows)
    assert sig and all(s.side == -1 for s in sig)
    assert any(s.time >= rel + pd.Timedelta(hours=2) and s.time <= rel + pd.Timedelta(hours=5)
               for s in sig)
    assert all("release_surprise:eia_gas_storage" in s.tag for s in sig)


def test_eia_baseline_uses_only_rows_knowable_before_the_scored_row():
    shock = date(2018, 1, 5) + timedelta(weeks=440)
    rows = _eia_rows(shock)
    base = F.eia_surprise(rows)
    # Poison every row knowable AFTER the shock's release: the shock's surprise must not move.
    rel = RI.eia_release_utc(shock)
    poisoned = [dict(r, value=r["value"] * (1 if datetime.fromisoformat(r["knowable_at"]) <= rel
                                            else 3)) for r in rows]
    again = F.eia_surprise(poisoned)
    assert again[pd.Timestamp(rel)] == pytest.approx(base[pd.Timestamp(rel)])


def test_a_revised_frame_never_reaches_a_cell():
    rows = _eia_rows(None, vintage=RI.BACKFILL_LATEST)
    with pytest.raises(F.ReleaseSurpriseUnavailable) as exc:
        F.family_release_surprise(_bars(), basis="eia_gas_storage", rows=rows)
    assert isinstance(exc.value, TypeError) and F.ABSENT in str(exc.value)


def test_usda_tic_and_boj_bases_score_against_their_own_baselines():
    now = datetime(2027, 1, 1, tzinfo=UTC)
    rng = np.random.default_rng(7)
    weeks = [date(2024, 1, 4) + timedelta(weeks=k) for k in range(120)]
    usda = [RI._row("usda_export_sales", "CORN_NET_SALES_KMT", d,
                    1000.0 + rng.normal(0, 50) + (900 if k == 100 else 0),
                    RI.usda_release_utc(d), RI.BACKFILL_STABLE, now, symbol="CORN")
            for k, d in enumerate(weeks)]
    z = F.reading("usda_export_sales", crop="CORN", window=52, rows=usda)
    assert z.idxmax() == pd.Timestamp(RI.usda_release_utc(weeks[100]))
    assert F.family_release_surprise(_bars(), basis="usda_export_sales", crop="COFFEE",
                                     rows=usda) == []

    months = [date(2023, 1, 1) + pd.DateOffset(months=k) for k in range(40)]
    tic_fp = [RI._row("tic_flow", "NET_FOREIGN_PURCHASES_LT_USD_MN", m.date(),
                      100.0 + rng.normal(0, 20) + (300 if k == 35 else 0),
                      RI.tic_backfill_utc(m.date()), RI.FIRST_PRINT, now)
              for k, m in enumerate(months)]
    z = F.reading("tic_flow", window=12, rows=tic_fp)
    assert z.idxmax() == pd.Timestamp(RI.tic_backfill_utc(months[35].date()))
    tic_latest = [dict(r, vintage=RI.BACKFILL_LATEST) for r in tic_fp]
    with pytest.raises(F.ReleaseSurpriseUnavailable):
        F.reading("tic_flow", window=12, rows=tic_latest)

    days = [date(2026, 1, 5) + timedelta(days=k) for k in range(80)]
    boj = []
    for k, d in enumerate(days):
        bought = 425.0 + rng.normal(0, 5) + (200.0 if k == 70 else 0.0)
        boj.append(RI._row("boj_rinban", "JGB_PURCHASE_5_10Y", d, bought,
                           RI.boj_backfill_utc(d), RI.BACKFILL_STABLE, now,
                           offered_bn=1200.0 + rng.normal(0, 60), planned_bn=425.0,
                           bucket="5_10Y"))
    z = F.reading("boj_rinban_size", window=40, rows=boj)
    assert z.idxmax() == pd.Timestamp(RI.boj_backfill_utc(days[70]))
    cover = F.reading("boj_rinban_cover", window=40, rows=boj)
    assert len(cover) > 20


def test_absent_basis_refuses_by_name():
    with pytest.raises(F.ReleaseSurpriseUnavailable):
        F.reading("boj_rinban_size", rows=[])
    assert F.family_release_surprise(_bars(), basis="nope", rows=[]) == []


# ----------------------------------------------------------------------------- 5. wiring
def test_family_proposer_leg_and_graph_are_wired():
    from mt5desk import families_orthogonal as FO
    assert FO.ORTHOGONAL_FAMILIES["release_surprise"] is F.family_release_surprise
    assert "release_surprise" in FO.FAMILY_INPUTS
    hc = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"research/release_surprise_proposer.py", "--once"' in hc
    assert '"release_surprise_proposer": rsp' in hc
    cg = (ROOT / "libs" / "ops" / "capability_graph.py").read_text("utf-8")
    assert "desks/mt5/research/release_surprise_proposer.py" in cg
    assert "desks/mt5/data/intelligence/release_surprise/" in cg
    from libs.research import layers
    assert layers.LEG_LAYER["release_surprise_proposer"] == "prediction"


def test_proposer_parks_every_basis_by_name_without_rows(tmp_path, monkeypatch):
    from research import release_surprise_proposer as P
    monkeypatch.setattr(P, "REPORT", tmp_path / "R.json")
    monkeypatch.setattr(F, "AXIS", tmp_path / "absent.json")
    monkeypatch.setattr(P.pc, "universe_meta", lambda: {
        s: {"asset_class": "Forex"} for s in ("USDJPY", "EURJPY", "EURUSD")})
    rep = P.run(ingest=False, donate=False)
    assert rep["status"] == P.UNMEASURED
    assert rep["bases"]["tic_flow"]["parked_reason"] == F.ABSENT
    assert json.loads((tmp_path / "R.json").read_text())["status"] == P.UNMEASURED
