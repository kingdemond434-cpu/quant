"""Macro event states: the per-source terms switch, refused hosts and robots fail closed, the stop
codes halt a source, every parser reads its synthetic page, available_time is never earlier than
the release, the surprise maths reads strictly earlier prints, the store is idempotent and
append-only, and cells / event rows land only on admitted symbols. No network: every request is
served by a synthetic fake."""
from __future__ import annotations

import json
import sys
import urllib.parse
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import macro_event_states as me  # noqa: E402

T0 = datetime(2026, 11, 18, 15, tzinfo=UTC)          # a Wednesday, 10:00 New York
ROBOTS_OK = (200, b"User-agent: *\nDisallow: /private/\n")


# ------------------------------------------------------------------------- synthetic pages
def eia_page(weeks: list[tuple[date, float]]) -> bytes:
    by_month: dict[tuple[int, int], list[tuple[date, float]]] = {}
    for d, v in weeks:
        by_month.setdefault((d.year, d.month), []).append((d, v))
    rows = ["<tr><th>Year-Month</th><th>Week 1</th></tr>"]
    for (y, m), items in sorted(by_month.items()):
        cells = [f"<td>{y}-{date(y, m, 1).strftime('%b')}</td>"]
        for d, v in items:
            cells.append(f"<td>{d:%m/%d}</td><td>{v:,.0f}</td>")
        cells += ["<td>&nbsp;</td><td></td>"] * (5 - len(items))
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return ("<html><body><table>" + "".join(rows) + "</table></body></html>").encode()


def eia_weeks(n: int, end: date, seasonal: bool = True) -> list[tuple[date, float]]:
    """Fridays back from `end`; the level rises by a week-of-year pattern plus a trend."""
    out: list[tuple[date, float]] = []
    level = 2000.0
    for i in range(n, -1, -1):
        d = end - timedelta(days=7 * i)
        level += (d.isocalendar()[1] % 7) * 3.0 if seasonal else 1.0
        out.append((d, level))
    return out


def usda_page(rel: date, corn: str = "685,800", wheat: str = "243,000",
              soy: str = "407,100", soy_red: bool = False) -> bytes:
    red = " reductions" if soy_red else ""
    return (f"<html><body><h2>Highlights</h2><p>{rel:%B} {rel.day}, {rel.year}</p>"
            f"<p><b>Wheat:</b> Net sales of {wheat} metric tons (MT) for 2025/2026 were down."
            f"</p><p><b>Corn:</b> Net sales of {corn} MT for 2025/2026 were down 53 percent.</p>"
            f"<p><b>Soybeans:</b> Net sales{red} of {soy} MT for 2025/2026 were down.</p>"
            "<p><b>Soybean cake and meal:</b> Net sales of 1 MT.</p></body></html>").encode()


def tic_page(months: list[tuple[str, float]]) -> bytes:
    lines = ["Table 1: U.S. Long-Term Securities Held by Foreign Residents", "Millions of dollars",
             "\t\t", "\t\t\tTotal U.S. Securities",
             "Country\tCountry Code\tDate\tHoldings\tNet U.S. Sales\tValuation Change",
             "country\tcountry_code\tdate\tfor_lt_tot_pos\tfor_lt_tot_net\tfor_lt_tot_valchg"]
    for per, v in months:
        lines.append(f"Austria\t10189\t{per}\t53564\t189\t1694")
        lines.append(f"Grand Total\t99996\t{per}\t9000000\t{v}\t0")
    return "\n".join(lines).encode()


def months_back(n: int, last: str) -> list[str]:
    y, m = int(last[:4]), int(last[5:7])
    out: list[str] = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return out[::-1]


class Fake:
    """Serves robots.txt and each source's data URL; records every URL asked for."""

    def __init__(self, pages: dict[str, bytes], *, robots: tuple[int, bytes] = ROBOTS_OK,
                 stop: dict[str, int] | None = None) -> None:
        self.pages, self.robots, self.stop = pages, robots, stop or {}
        self.urls: list[str] = []

    def data(self) -> list[str]:
        return [u for u in self.urls if not u.endswith("/robots.txt")]

    def __call__(self, url: str) -> tuple[int, bytes]:
        self.urls.append(url)
        parts = urllib.parse.urlsplit(url)
        if parts.path == "/robots.txt":
            return self.robots
        for sid, code in self.stop.items():
            if url.startswith(me.SOURCES[sid].url.split("?")[0]):
                return code, b""
        base = f"{parts.scheme}://{parts.netloc}{parts.path}"
        for sid, body in self.pages.items():
            if (base == me.EIA_API) if sid == "eia_api" else (base == me.SOURCES[sid].url):
                return 200, body
        return 404, b""


UNIVERSE = {"CORN": "Soft Commodity", "WHEAT": "Soft Commodity", "SOYBEAN": "Soft Commodity",
            "XNGUSD": "Energy", "USDJPY": "Forex", "EURUSD": "Forex", "US500": "Indices",
            "EURCHF": "Forex", "Boeing": "Equities"}


def _paths(tmp_path: Path, universe: dict[str, str] | None = None) -> me.Paths:
    (tmp_path / "data" / "universe").mkdir(parents=True)
    uni = {s: {"asset_class": c} for s, c in (universe or UNIVERSE).items()}
    (tmp_path / "data" / "universe" / "universe.json").write_text(json.dumps(uni), "utf-8")
    return me.Paths(desk=tmp_path)


@pytest.fixture(autouse=True)
def _policy(monkeypatch: pytest.MonkeyPatch) -> None:
    """A deterministic lane policy: share CFDs (asset_class Equities) are never hypothesis lane."""
    from research import universe_policy
    monkeypatch.setattr(universe_policy, "may_hypothesise",
                        lambda sym, family=None: sym != "Boeing")


def _run(paths: me.Paths, fake: Fake, now: datetime = T0, minted: list[Any] | None = None,
         key: str = "", **kw: Any) -> dict[str, Any]:
    def donate(seat: str, cands: list[dict[str, Any]], n: int) -> dict[str, Any]:
        if minted is not None:
            minted.extend(cands)
        return {"donated": len(cands)}
    return me.run(paths, get=fake, now=now, sleep=lambda _s: None, donate=donate,
                  key=lambda: key, **kw)


def _pages(n_eia: int = 320, n_tic: int = 60) -> dict[str, bytes]:
    return {"eia_gas_storage": eia_page(eia_weeks(n_eia, date(2026, 11, 13))),
            "usda_export_sales": usda_page(date(2026, 11, 13)),
            "tic_foreign_flows": tic_page([(p, 1000.0 + 10 * i) for i, p in
                                           enumerate(months_back(n_tic, "2026-09"))])}


# ------------------------------------------------------------------------------ gates
def test_blocked_sources_make_no_request(tmp_path: Path) -> None:
    fake = Fake(_pages())
    doc = _run(_paths(tmp_path), fake)
    for sid in ("snb_sight_deposits", "boj_rinban"):
        assert doc["sources"][sid]["status"] == "BLOCKED_ON_TERMS"
        assert doc["sources"][sid]["missed_growth"]
        assert doc["missed_growth"][sid]
    hosts = {urllib.parse.urlsplit(u).netloc for u in fake.urls}
    assert not hosts & {"data.snb.ch", "www.snb.ch", "www.boj.or.jp"}


def test_terms_switch_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for sid in ("usda_export_sales", "eia_gas_storage", "tic_foreign_flows"):
        monkeypatch.setitem(me.TERMS_EVIDENCE[sid], "machine_use_allowed", False)
    fake = Fake(_pages())
    doc = _run(_paths(tmp_path), fake)
    assert fake.urls == []
    assert all(r["status"] == "BLOCKED_ON_TERMS" for r in doc["sources"].values())
    assert doc["cells"]["grid"] == 0


def test_refused_host_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.data import refused_hosts
    monkeypatch.setitem(refused_hosts.REFUSED_HOSTS, "eia.gov", "test refusal")
    fake = Fake(_pages())
    doc = _run(_paths(tmp_path), fake)
    assert doc["sources"]["eia_gas_storage"]["status"] == "BLOCKED_ON_TERMS"
    assert not any("eia.gov" in u for u in fake.urls)


def test_robots_disallow_stops_before_data(tmp_path: Path) -> None:
    fake = Fake(_pages(), robots=(200, b"User-agent: *\nDisallow: /\n"))
    doc = _run(_paths(tmp_path), fake)
    assert fake.data() == []
    for sid in ("usda_export_sales", "eia_gas_storage", "tic_foreign_flows"):
        assert doc["sources"][sid]["status"] == "ROBOTS_REFUSED"
        assert doc["sources"][sid]["missed_growth"]


@pytest.mark.parametrize("robots", [(500, b""), (200, b"<!DOCTYPE html><p>hi</p>")])
def test_unreadable_robots_refuses(tmp_path: Path, robots: tuple[int, bytes]) -> None:
    fake = Fake(_pages(), robots=robots)
    doc = _run(_paths(tmp_path), fake)
    assert fake.data() == []
    assert doc["sources"]["tic_foreign_flows"]["status"] == "ROBOTS_REFUSED"


def test_robots_404_means_no_rules(tmp_path: Path) -> None:
    fake = Fake(_pages(), robots=(404, b""))
    doc = _run(_paths(tmp_path), fake)
    assert doc["sources"]["tic_foreign_flows"]["status"] == "OK"


@pytest.mark.parametrize("code", [401, 403, 429, 451])
def test_stop_codes_hard_stop_the_source(tmp_path: Path, code: int) -> None:
    paths = _paths(tmp_path)
    fake = Fake(_pages(), stop={"eia_gas_storage": code})
    doc = _run(paths, fake, key="SECRETKEY")
    rec = doc["sources"]["eia_gas_storage"]
    assert rec["status"] == "HARD_STOP"
    assert rec["missed_growth"]
    assert not any("api.eia.gov" in u for u in fake.urls), "a stop is never routed round"
    # the other sources are unaffected
    assert doc["sources"]["tic_foreign_flows"]["status"] == "OK"
    state = json.loads(paths.state.read_text("utf-8"))["sources"]["eia_gas_storage"]
    assert state["hard_stop"]["code"] == code
    assert (state["hard_stop"]["until"] is None) == (code == 451)
    # next pass, a day later (due): still held for 451, released after HARD_STOP_H otherwise
    fake2 = Fake(_pages())
    doc2 = _run(paths, fake2, now=T0 + timedelta(hours=me.HARD_STOP_H + 1))
    want = "HARD_STOP" if code == 451 else "OK"
    assert doc2["sources"]["eia_gas_storage"]["status"] == want
    if code == 451:
        assert not any("eia.gov/dnav" in u for u in fake2.urls)


def test_request_budget_is_a_hard_bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(me, "MAX_REQUESTS", 2)
    fake = Fake(_pages())
    doc = _run(_paths(tmp_path), fake)
    assert len(fake.urls) <= 2
    assert doc["requests"] <= 2
    assert any(r["status"] == "BUDGET" for r in doc["sources"].values())


def test_eia_key_fallback_only_on_shape_and_never_leaks(tmp_path: Path) -> None:
    pages = _pages()
    pages["eia_gas_storage"] = b"<html><p>redesigned page</p></html>"
    api = {"response": {"data": [{"period": d.isoformat(), "value": v}
                                 for d, v in eia_weeks(320, date(2026, 11, 13))]}}
    pages["eia_api"] = json.dumps(api).encode()
    paths = _paths(tmp_path)
    doc = _run(paths, Fake(pages), key="SECRETKEY")
    assert doc["sources"]["eia_gas_storage"]["fetch"]["route"] == "keyed_api"
    for p in (paths.report, paths.state, paths.clock):
        assert "SECRETKEY" not in p.read_text("utf-8")
    # without a key the fallback names the missing credential and fails closed
    doc2 = _run(_paths(tmp_path / "b"), Fake(pages), key="")
    assert "BLOCKED_AUTH:EIA_API_KEY" in doc2["sources"]["eia_gas_storage"]["why"]


# ------------------------------------------------------------------------------ parsers
def test_usda_parser_reads_net_sales_and_reductions() -> None:
    obs = {o.series: o for o in me.parse_usda_highlights(
        usda_page(date(2026, 2, 26), soy="12,500", soy_red=True))}
    assert obs["usda_esr_corn_net"].value == 685800
    assert obs["usda_esr_wheat_net"].value == 243000
    assert obs["usda_esr_soybeans_net"].value == -12500          # reductions are negative
    assert obs["usda_esr_corn_net"].period == "2026-02-26"
    # 08:30 New York on the page's own release date (EST: 13:30 UTC)
    assert obs["usda_esr_corn_net"].rule_time == datetime(2026, 2, 26, 13, 30, tzinfo=UTC)


def test_usda_parser_refuses_a_page_it_does_not_recognise() -> None:
    with pytest.raises(me.Refused, match="METADATA_MISMATCH"):
        me.parse_usda_highlights(b"<html>no date here</html>")
    with pytest.raises(me.Refused, match="METADATA_MISMATCH"):
        me.parse_usda_highlights(b"<html>March 5, 2026 nothing about grain</html>")


def test_eia_parser_reads_week_pairs() -> None:
    weeks = [(date(2026, 10, 2), 3500.0), (date(2026, 10, 9), 3567.0),
             (date(2026, 10, 16), 3644.0)]
    obs = me.parse_eia_history(eia_page(weeks))
    assert [(o.period, o.value) for o in obs] == [(d.isoformat(), v) for d, v in weeks]
    with pytest.raises(me.Refused):
        me.parse_eia_history(b"<html><table><tr><td>x</td></tr></table></html>")


def test_tic_parser_reads_grand_total_by_header() -> None:
    obs = me.parse_tic_table1(tic_page([("2026-07", -500.0), ("2026-08", 1234.0)]))
    assert [(o.period, o.value) for o in obs] == [("2026-07", -500.0), ("2026-08", 1234.0)]
    with pytest.raises(me.Refused, match="METADATA_MISMATCH"):
        me.parse_tic_table1(b"no header\nat all")


def test_snb_parser_kept_for_when_terms_allow() -> None:
    body = (b'"CubeId";"snbgwdchfsgw"\n"PublishingDate";"2026-11-16 10:00"\n\n'
            b'"Date";"D0";"Value"\n"2026-11-06";"TG";"460000"\n"2026-11-06";"GI";"1"\n'
            b'"2026-11-07";"TG";""\n"2026-11-13";"TG";"462500"\n')
    obs = me.parse_snb_cube(body)
    assert [(o.period, o.value) for o in obs] == [("2026-11-06", 460000.0),
                                                  ("2026-11-13", 462500.0)]
    ch = me.surprises([{"period": o.period, "value": o.value,
                        "available_time": me._iso(o.rule_time), "pit_quality": "x"}
                       for o in obs], "change", ("zero",), "zero")
    assert ch[0]["surprise"] == 2500.0 and ch[0]["method"] == "zero"


# --------------------------------------------------------------------- release rules (PIT)
def test_eia_release_rule() -> None:
    # week ending Fri 2026-11-13 -> Thu 2026-11-19 10:30 EST = 15:30 UTC
    assert me.eia_release_time(date(2026, 11, 13)) == datetime(2026, 11, 19, 15, 30, tzinfo=UTC)
    # Thanksgiving week (Thu 2026-11-26 holiday): stamped Friday, a late bound
    assert me.eia_release_time(date(2026, 11, 20)) == datetime(2026, 11, 27, 15, 30, tzinfo=UTC)
    # a Monday holiday in the release week (Labor Day 2026-09-07) also moves it to Friday
    assert me.eia_release_time(date(2026, 9, 4)).date() == date(2026, 9, 11)


def test_tic_release_bound_is_late() -> None:
    # August data is released mid-October; the bound is 31 October 16:00 EDT
    assert me.tic_release_bound("2026-08") == datetime(2026, 10, 31, 20, 0, tzinfo=UTC)
    assert me.tic_release_bound("2026-11") == datetime(2027, 1, 31, 21, 0, tzinfo=UTC)


def test_snb_release_rule_rolls_past_easter_monday() -> None:
    # Friday 2026-04-03 (Good Friday) -> Easter Monday 04-06 is a holiday -> Tuesday 10:00 CEST
    assert me.snb_release_time(date(2026, 4, 3)) == datetime(2026, 4, 7, 8, 0, tzinfo=UTC)
    assert me.snb_release_time(date(2026, 11, 13)) == datetime(2026, 11, 16, 9, 0, tzinfo=UTC)


def test_stamp_never_earlier_than_evidence() -> None:
    rule = datetime(2026, 11, 19, 15, 30, tzinfo=UTC)
    # backfill: the rule (a late bound)
    assert me.stamp(rule, rule + timedelta(days=30), None) == (rule, "backfill_rule")
    # previous read before the rule, this one after: the rule is bracketed
    assert me.stamp(rule, rule + timedelta(minutes=40), rule - timedelta(minutes=20)) == \
        (rule, "live_rule")
    # previous read was after the rule and did not hold it: a delayed release -> seen
    seen = rule + timedelta(hours=5)
    assert me.stamp(rule, seen, rule + timedelta(hours=1)) == (seen, "live_seen")


def test_store_is_idempotent_and_revisions_are_stamped_when_seen(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    store: dict[tuple[str, str], dict[str, Any]] = {}
    rule = datetime(2026, 10, 31, 20, tzinfo=UTC)
    obs = [me.Obs("tic_net_lt", "2026-08", 100.0, rule)]
    assert me.merge(paths, "tic_foreign_flows", store, obs, T0, None)["added"] == 1
    assert me.merge(paths, "tic_foreign_flows", store, obs, T0, None) == {"added": 0,
                                                                          "revised": 0}
    later = T0 + timedelta(days=30)
    rev = [me.Obs("tic_net_lt", "2026-08", 140.0, rule)]
    assert me.merge(paths, "tic_foreign_flows", store, rev, later, T0)["revised"] == 1
    back = me.load_store(paths, "tic_foreign_flows")
    rec = back[("tic_net_lt", "2026-08")]
    assert rec["value"] == 100.0 and rec["last_value"] == 140.0 and rec["n_revisions"] == 1
    lines = [json.loads(x) for x in
             (paths.store / "tic_foreign_flows.jsonl").read_text("utf-8").splitlines()]
    assert lines[1]["revision"] is True and lines[1]["available_time"] == me._iso(later)
    # the point-in-time series reads the first-seen value
    assert me._points(back, "tic_net_lt")[0]["value"] == 100.0


# ------------------------------------------------------------------- expectation and surprise
def _pts(vals: list[float], periods: list[str]) -> list[dict[str, Any]]:
    """Each print public 12 hours after its period starts (strictly increasing stamps)."""
    out = []
    for p, v in zip(periods, vals, strict=True):
        d = date.fromisoformat(p if len(p) == 10 else p + "-01")
        out.append({"period": p, "value": v, "pit_quality": "t",
                    "available_time": me._iso(datetime(d.year, d.month, d.day, 12, tzinfo=UTC))})
    return out


def _weekly(n: int, start: date = date(2026, 1, 2)) -> list[str]:
    return [(start + timedelta(days=7 * i)).isoformat() for i in range(n)]


def test_expectation_reads_only_what_was_public_before_release() -> None:
    days = _weekly(6)
    pts = _pts([10, 20, 30, 40, 100, 0], days)
    rel = pts[4]["available_time"]
    assert me.expectation(pts, rel, "trailing_mean4", days[4]) == 25.0
    # a print stamped AFTER the release (a late revision, a delayed print) is invisible to it
    late = [dict(p) for p in pts]
    late[3]["available_time"] = me._iso(datetime(2027, 1, 1, tzinfo=UTC))
    assert me.expectation(late, rel, "trailing_mean4", days[4]) is None
    # the print being judged is never part of its own expectation
    assert me.expectation(pts, "2030-01-01T00:00:00+00:00", "trailing_mean4", days[4]) == 25.0


def test_every_method_is_named_and_unknown_methods_raise() -> None:
    pts = _pts([float(i) for i in range(30)], _weekly(30))
    for m in me.EXPECTATION_METHODS:
        me.expectation(pts, pts[-1]["available_time"], m, pts[-1]["period"])
    with pytest.raises(ValueError):
        me.expectation(pts, pts[-1]["available_time"], "consensus_we_bought", pts[-1]["period"])


def test_trailing_mean4_and_gappy_window() -> None:
    days = _weekly(6)
    out = me.surprises(_pts([10, 20, 30, 40, 100, 0], days), "level",
                       ("trailing_mean4",), "trailing_mean4")
    assert [o["period"] for o in out] == days[4:]
    assert out[0]["baseline"] == 25.0 and out[0]["surprise"] == 75.0
    assert out[1]["baseline"] == (20 + 30 + 40 + 100) / 4
    gappy = ["2026-01-02", "2026-03-06", "2026-03-13", "2026-03-20", "2026-03-27"]
    assert me.surprises(_pts([1, 2, 3, 4, 5], gappy), "level", ("trailing_mean4",),
                        "trailing_mean4") == []


def test_trailing_median12() -> None:
    per = months_back(14, "2026-09")
    vals = [float(i) for i in range(13)] + [1000.0]
    out = me.surprises(_pts(vals, per), "level", ("trailing_median12",), "trailing_median12")
    assert len(out) == 2
    assert out[0]["baseline"] == 5.5 and out[0]["surprise"] == 12 - 5.5
    assert out[1]["baseline"] == 6.5


def test_seasonal_naive_and_ar1() -> None:
    per = months_back(30, "2026-09")
    vals = [100.0 + 2.0 * i for i in range(30)]               # a straight line: AR(1) is exact
    pts = _pts(vals, per)
    rel = pts[-1]["available_time"]
    assert me.expectation(pts, rel, "seasonal_naive", per[-1]) == vals[-13]
    assert me.expectation(pts, rel, "ar1", per[-1]) == pytest.approx(vals[-1])
    assert me.expectation(pts[:5], pts[4]["available_time"], "ar1", per[4]) is None


def test_surprise_is_scaled_by_its_own_earlier_surprises() -> None:
    per = months_back(40, "2026-09")
    vals = [float((i * 7) % 11) for i in range(40)]
    out = me.surprises(_pts(vals, per), "level", ("trailing_median12", "ar1"),
                       "trailing_median12")
    hist = [o["surprise"] for o in out]
    for i, o in enumerate(out):
        prior = hist[:i][-me.SCALE_WINDOW["monthly"]:]
        if len(prior) < me.SCALE_MIN:
            assert o["surprise_z"] is None and o["value"] is None
        else:
            import statistics
            assert o["surprise_z"] == pytest.approx(o["surprise"] / statistics.pstdev(prior),
                                                    abs=1e-5)
        assert set(o["expectations"]) == {"trailing_median12", "ar1"}
        assert o["method"] == "trailing_median12"


def test_five_year_same_week_average_of_changes() -> None:
    weeks = eia_weeks(6 * 52 + 4, date(2026, 11, 13))
    pts = [{"period": d.isoformat(), "value": v, "pit_quality": "t",
            "available_time": me._iso(me.eia_release_time(d))} for d, v in weeks]
    out = me.surprises(pts, "change", ("seasonal_5y",), "seasonal_5y")
    assert out, "five years of history must yield surprises"
    last = out[-1]
    changes = {d: b - a for (_, a), (d, b) in pairwise(weeks)}
    d = date(2026, 11, 13)
    prior = []
    for k in range(1, 6):
        tgt = date(d.year - k, d.month, d.day)
        prior.append(next(v for dd, v in changes.items() if abs((dd - tgt).days) <= 3))
    assert last["actual"] == changes[d]
    assert last["baseline"] == pytest.approx(sum(prior) / 5)
    assert last["surprise"] == pytest.approx(changes[d] - sum(prior) / 5)
    assert date.fromisoformat(out[0]["period"]) >= weeks[0][0] + timedelta(days=5 * 365 - 10)


def test_weekly_change_skips_missing_weeks() -> None:
    pts = _pts([1, 2, 10], ["2026-01-02", "2026-01-09", "2026-01-23"])
    assert [c["period"] for c in me.weekly_changes(pts)] == ["2026-01-09"]


# ------------------------------------------------------------------------- the whole pass
def test_full_pass_cells_only_on_admitted_symbols(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    minted: list[dict[str, Any]] = []
    # read after the last synthetic week's release, as on the box
    doc = _run(paths, Fake(_pages()), minted=minted, now=datetime(2026, 11, 20, 12, tzinfo=UTC))
    assert doc["sources"]["eia_gas_storage"]["status"] == "OK"
    assert doc["sources"]["tic_foreign_flows"]["status"] == "OK"
    assert doc["sources"]["usda_export_sales"]["status"] == "OK"
    syms = {c["symbol"] for c in minted}
    # XNGUSD (EIA) and the TIC symbols the registry holds; US30/NAS100/US2000 are not in this
    # registry, the USDA series are too short, and nothing lands on a share CFD
    assert syms == {"XNGUSD", "USDJPY", "EURUSD", "US500"}
    assert all(c["family"] == "exogenous_conditioner" for c in minted)
    assert all(c["params"]["source"].startswith("mes_") for c in minted)
    assert doc["cells"]["minted"] == len(minted) == doc["cells"]["grid"]
    usda = doc["sources"]["usda_export_sales"]["states"]["usda_esr_corn_surprise_4w"]
    assert usda["status"] == me.UNMEASURED
    # lake series carry the PIT stamp
    lake = (paths.series / "mes_eia_ngs_surprise_5y.csv").read_text("utf-8").splitlines()
    assert lake[0].startswith("event_time,available_time,value")
    # event rows: readable by the atlas, at = available_time, never before the release rule
    clock = json.loads(paths.clock.read_text("utf-8"))
    assert clock["n_events"] > 0
    for e in clock["events"]:
        assert set(e["instruments"]) <= {"XNGUSD", "USDJPY", "EURUSD", "US500"}
        if e["source"] == "eia_gas_storage":
            rule = me.eia_release_time(date.fromisoformat(e["period"]))
            assert me._t(e["at"]) >= rule


def test_policy_failing_closed_mints_nothing(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins
    real = builtins.__import__

    def boom(name: str, *a: Any, **k: Any) -> Any:
        if name == "research.universe_policy":
            raise ImportError("gone")
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", boom)
    minted: list[dict[str, Any]] = []
    doc = _run(_paths(tmp_path), Fake(_pages()), minted=minted)
    assert minted == [] and doc["cells"]["grid"] == 0


def test_atlas_reads_the_clock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from research import event_response_atlas as A
    paths = _paths(tmp_path)
    _run(paths, Fake(_pages()))
    for name in ("CALENDAR", "MACRO_LEDGER", "ROOT_EVENTS"):
        monkeypatch.setattr(A, name, tmp_path / f"absent_{name}.json")
    monkeypatch.setattr(A, "MACRO_STATES_CLOCK", paths.clock)
    events, acc = A.load_events(3650, T0)
    assert acc["macro_event_states"]["status"] == "READ"
    assert acc["macro_event_states"]["unusable_rows"] == 0
    assert events and all(e["source"] == "macro_event_states" for e in events)
    assert any(e["consensus"] is not None for e in events)


def test_not_due_makes_no_request(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _run(paths, Fake(_pages()))
    fake = Fake(_pages())
    # Wednesday 10:20 NY, outside every fast window: nothing is due an hour later
    doc = _run(paths, fake, now=T0 + timedelta(minutes=20))
    assert fake.urls == []
    assert doc["sources"]["eia_gas_storage"]["status"] == "NOT_DUE"
    # a second pass with the same pages appends nothing to the store
    assert doc["store_rows"] > 0


def test_live_pass_stamps_new_print_at_bracketed_rule(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    weeks = eia_weeks(320, date(2026, 11, 13))
    pages = _pages()
    _run(paths, Fake(pages))                                    # backfill on Wednesday
    nxt = (date(2026, 11, 20), weeks[-1][1] + 12.0)
    pages["eia_gas_storage"] = eia_page([*weeks, nxt])
    # Thursday 2026-11-26 is Thanksgiving: stamp rule is Friday 11-27 10:30 ET; read at 11:00 ET
    seen = datetime(2026, 11, 27, 16, 0, tzinfo=UTC)
    # an earlier read at Friday 09:00 ET did not hold it
    _run(paths, Fake({**pages, "eia_gas_storage": eia_page(weeks)}),
         now=datetime(2026, 11, 27, 14, 0, tzinfo=UTC))
    _run(paths, Fake(pages), now=seen)
    rec = me.load_store(paths, "eia_gas_storage")[("eia_ngs_level", "2026-11-20")]
    assert rec["pit_quality"] == "live_rule"
    assert rec["available_time"] == me._iso(me.eia_release_time(date(2026, 11, 20)))


def test_every_emitted_family_has_a_registered_builder(tmp_path: Path) -> None:
    """The Judge's condition: a cell naming a family the registry cannot build lands as
    NO_REGISTERED_BUILDER and never gets a verdict."""
    from research.axis_registry import registered_families
    from research.family_policy import family_banned
    minted: list[dict[str, Any]] = []
    _run(_paths(tmp_path), Fake(_pages()), minted=minted,
         now=datetime(2026, 11, 20, 12, tzinfo=UTC))
    assert minted
    families = {c["family"] for c in minted}
    registry = registered_families()
    assert families <= registry, families - registry
    assert not any(family_banned(f) for f in families)
