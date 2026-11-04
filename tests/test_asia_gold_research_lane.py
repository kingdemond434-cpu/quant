"""Asian retail gold-demand RESEARCH doors for gold_asia (2026-11-04): the Vietnam SJC bar at
Vietcombank's dollar and India's IBJA 999 at the RBI reference rate. Fixtures only.

Fixtures (tests/fixtures/alt_proxies/, UTF-8 text, built from each page's layout as read with
WebFetch on 2026-11-04 because the cloud proxy refuses every host to curl; live shape UNMEASURED
from here): vn_sjc_premium.json (existing board fixture), vn_sjc_premium.vcb.xml (Vietcombank's
XML, the published 2026-11-03 USD row re-dated), in_ibja_premium.ibja.html (AM/PM previous-dates
tables; 02/11, 30/10, 29/10 published, 03/11 SYNTHETIC) and in_ibja_premium.rbi.html (RBI's
Current Rates block, the published 2026-11-03 USD rate).
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import polite_fetch as pf  # noqa: E402
from libs.data import terms_fence as tf  # noqa: E402
from research import alt_proxies as A  # noqa: E402
from research import asia_gold_physical as G  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "alt_proxies"
NOW = datetime(2026, 11, 4, 13, tzinfo=UTC)
XAU = 4300.0


def _fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


def _xau_parquet(universe: Path, days: list[str], px: float = XAU) -> None:
    universe.mkdir(parents=True, exist_ok=True)
    idx = pd.DatetimeIndex([pd.Timestamp(f"{d} {h:02d}:00", tz="UTC") for d in days
                            for h in range(24)])
    pd.DataFrame({"close": [px] * len(idx)}, index=idx).to_parquet(
        universe / "XAUUSD_H1.parquet")


DAYS = ["2026-10-28", "2026-10-29", "2026-10-30", "2026-11-02", "2026-11-03"]


# ---------------------------------------------------------------------------------- parsers --
def test_vcb_xml_is_read_with_its_own_vietnam_time_stamp() -> None:
    rows = G.parse_vcb_rates(_fx("vn_sjc_premium.vcb.xml"))
    assert rows == [{"date": "2026-10-28", "vnd_per_usd": 25590.0, "vnd_per_usd_sell": 25970.0,
                     "published_utc": datetime(2026, 10, 28, 1, 30, 31, tzinfo=UTC)}]
    pm = b"<ExrateList><DateTime>1/5/2027 1:05:00 PM</DateTime><Exrate CurrencyCode=\"USD\" " \
         b"Transfer=\"25,600.00\" Sell=\"25,980.00\" /></ExrateList>"
    assert G.parse_vcb_rates(pm)[0]["published_utc"] == datetime(2027, 1, 5, 6, 5, tzinfo=UTC)
    assert G.parse_vcb_rates(pm.replace(b"25,600.00", b"9.00")) == []      # not a VND rate
    assert G.parse_vcb_rates(b"<html>maintenance</html>") == []


def test_sjc_board_is_stamped_at_its_own_print_in_utc() -> None:
    assert G.sjc_print_instant(_fx("vn_sjc_premium.json")) == datetime(2026, 10, 28, 9, 5,
                                                                        tzinfo=UTC)
    obs = A.parse_vn_sjc(_fx("vn_sjc_premium.json"), A.Ctx(part="sjc"))
    assert {o.series for o in obs} == {"sjc_buy_vnd", "sjc_sell_vnd"}
    assert all(o.published_at == datetime(2026, 10, 28, 9, 5, tzinfo=UTC) for o in obs)
    vcb = A.parse_vn_sjc(_fx("vn_sjc_premium.vcb.xml"), A.Ctx(part="vcb"))
    assert [(o.series, o.value) for o in vcb] == [("vcb_vnd_per_usd", 25590.0)]


def test_ibja_am_and_pm_tables() -> None:
    rows = G.parse_ibja_rates(_fx("in_ibja_premium.ibja.html"))
    got = {(r["date"], r["session"]): r["gold_999"] for r in rows}
    assert len(rows) == 8
    assert got[("2026-11-02", "am")] == 137772.0 and got[("2026-11-02", "pm")] == 137524.0
    assert got[("2026-10-29", "pm")] == 142255.0
    # no panel ids: the first table is AM and the second PM (the page's tab order)
    bare = _fx("in_ibja_premium.ibja.html").replace(b'id="tab-am"', b"").replace(
        b'id="tab-pm"', b"")
    assert {(r["date"], r["session"]): r["gold_999"] for r in G.parse_ibja_rates(bare)} == got
    # a 999 below its own 995, or outside a gold-shaped band, is refused
    bad = b"<table><tr><td>01/11/2026</td><td>100</td><td>200</td></tr></table>"
    assert G.parse_ibja_rates(bad) == []


def test_rbi_reference_rate_block() -> None:
    assert G.parse_rbi_reference_rate(_fx("in_ibja_premium.rbi.html")) == [
        {"date": "2026-11-03", "inr_per_usd": 94.8606}]
    assert G.parse_rbi_reference_rate(b"<p>INR / 1 USD : 94.86</p>") == []    # no date: none
    obs = A.parse_in_ibja(_fx("in_ibja_premium.rbi.html"), A.Ctx(part="rbi"))
    assert [(o.series, o.period, o.value) for o in obs] == [
        ("rbi_inr_per_usd", date(2026, 11, 3), 94.8606)]


# --------------------------------------------------------------------------------------- PIT --
def test_india_legs_are_stamped_after_the_pm_poll_and_the_reference_rate() -> None:
    src = A.BY_ID[G.IN_ID]
    store: dict[str, Any] = {}
    obs = (A.parse_in_ibja(_fx("in_ibja_premium.ibja.html"), A.Ctx(part="ibja"))
           + A.parse_in_ibja(_fx("in_ibja_premium.rbi.html"), A.Ctx(part="rbi")))
    A.merge_vintages(store, src, obs, NOW)
    pm = store["ibja_pm_999_inr|2026-11-03"]
    # 18:00 IST: after the ~17:00 IST PM poll and the ~13:30 IST reference rate, never before
    assert pm["published_time"] == "2026-11-03T12:30:00+00:00"
    assert pm["published_basis"] == "release_rule"
    assert store["rbi_inr_per_usd|2026-11-03"]["published_time"] == "2026-11-03T12:30:00+00:00"
    assert G.in_publication(date(2026, 11, 3)) > datetime(2026, 11, 3, 11, 30, tzinfo=UTC)


def test_premiums_are_knowable_only_when_their_last_leg_and_bar_are(tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")
    _xau_parquet(paths.universe, DAYS)
    # Vietnam: board printed 16:05 ICT (09:05 UTC), Vietcombank 08:30 ICT, last closed bar 09:00
    vn = A.BY_ID[G.VN_ID]
    st: dict[str, Any] = {}
    A.merge_vintages(st, vn, A.parse_vn_sjc(_fx("vn_sjc_premium.json"), A.Ctx(part="sjc"))
                     + A.parse_vn_sjc(_fx("vn_sjc_premium.vcb.xml"), A.Ctx(part="vcb")), NOW)
    pts = A.research_points(paths, vn, st)
    p = pts["premium_pct"][-1]
    local = G.usd_per_oz((148_500_000 + 150_500_000) / 2, G.TAEL_G, G.SJC_PURITY, 25590.0)
    assert p["d"] == "2026-10-28" and p["value"] == pytest.approx((local / XAU - 1) * 100)
    assert p["available_time"] == "2026-10-28T09:05:00+00:00"
    assert pts["premium_usd_oz"][-1]["value"] == pytest.approx(local - XAU)
    assert pts["buy_sell_gap_pct"][-1]["value"] > 0
    # India: PM premium on the reference rate's date only (inner join), knowable 12:30 UTC
    ind = A.BY_ID[G.IN_ID]
    si: dict[str, Any] = {}
    A.merge_vintages(si, ind, A.parse_in_ibja(_fx("in_ibja_premium.ibja.html"), A.Ctx(part="ibja"))
                     + A.parse_in_ibja(_fx("in_ibja_premium.rbi.html"), A.Ctx(part="rbi")), NOW)
    ip = A.research_points(paths, ind, si)
    assert [x["d"] for x in ip["premium_pct"]] == ["2026-11-03"]
    u = G.usd_per_oz(138400.0, 10.0, 0.999, 94.8606)
    assert ip["premium_pct"][0]["value"] == pytest.approx((u / XAU - 1) * 100)
    assert ip["premium_pct"][0]["available_time"] == "2026-11-03T12:30:00+00:00"
    assert ip["premium_usd_oz"][0]["value"] == pytest.approx(u - XAU)
    assert "premium_am_pct" in ip
    # no XAUUSD bar on this box: no premium (UNMEASURED), never a zero
    (paths.universe / "XAUUSD_H1.parquet").unlink()
    assert "premium_pct" not in A.research_points(paths, ind, si)


def test_bar_before_never_reads_a_bar_still_open_at_the_print() -> None:
    h = {"2026-10-28T08": 1.0, "2026-10-28T09": 2.0}
    assert G.bar_before(h, datetime(2026, 10, 28, 9, 5, tzinfo=UTC)) == (
        1.0, datetime(2026, 10, 28, 9, tzinfo=UTC))
    assert G.bar_before(h, datetime(2026, 10, 28, 10, 0, tzinfo=UTC))[0] == 2.0
    assert G.bar_before(h, datetime(2026, 10, 29, 10, 0, tzinfo=UTC)) is None   # no carry


# --------------------------------------------------------------- access labels + hard stop --
def _resp(url: str, body: bytes = b"", *, label: str = "PUBLIC", note: str = "",
          status: int | None = 200, verdict: str = "", error: str = "") -> pf.Response:
    return pf.Response(url=url, status=status, body=body, access_label=label, terms_note=note,
                       verdict=verdict, error=error)


def _serving(calls: list[dict[str, Any]], **resp_kw: Any) -> Any:
    bodies = {A.SJC_PRICE_URL: _fx("vn_sjc_premium.json"),
              A.VCB_XML_URL: _fx("vn_sjc_premium.vcb.xml"),
              A.IBJA_URL: _fx("in_ibja_premium.ibja.html"),
              A.RBI_HOME_URL: _fx("in_ibja_premium.rbi.html")}

    def get(url: str, **kw: Any) -> pf.Response:
        calls.append({"url": url, **kw})
        return _resp(url, bodies[url], **resp_kw)
    return get


def test_robots_is_a_label_and_the_research_fetch_is_never_live_input(tmp_path: Path) -> None:
    paths, state, calls = A.Paths(tmp_path / "desk"), {}, []
    get = _serving(calls, label="PUBLIC_WITH_TERMS",
                   note="robots.txt Disallow for quant-mt5-research-desk on /")
    rec = A.research_collect(paths, A.BY_ID[G.IN_ID], state, NOW, fetch=True, fixtures=None,
                             deadline=1e18, get=get)
    assert [c["url"] for c in calls] == [A.IBJA_URL, A.RBI_HOME_URL]
    assert all("live_input" not in c and c["leg"] == A.RESEARCH_LEG for c in calls)
    assert rec["parsed"] > 0 and rec["state"] == "GREEN"            # the Disallow did not stop it
    lab = rec["access"]["ibja"]
    assert lab["access_label"] == "PUBLIC_WITH_TERMS" and "Disallow" in lab["terms_note"]
    assert lab["redistribute_allowed"] is False
    assert "in_rbi_reference_rate" in rec["policy_rows"]
    # robots allowing never erases the publisher's reserved rights
    calls.clear()
    rec = A.research_collect(paths, A.BY_ID[G.VN_ID], state, NOW, fetch=True, fixtures=None,
                             deadline=1e18, get=_serving(calls))
    assert rec["access"]["sjc"]["access_label"] == "PUBLIC_WITH_TERMS"
    assert rec["access"]["vcb"]["redistribute_allowed"] is False
    unclear = A.research_collect(paths, A.BY_ID[G.VN_ID], state, NOW, fetch=True, fixtures=None,
                                 deadline=1e18, get=_serving([], label="ACCESS_UNCLEAR"))
    assert unclear["access"]["sjc"]["access_label"] == "ACCESS_UNCLEAR" and unclear["parsed"] > 0


def test_a_401_403_429_or_waf_is_a_hard_stop_held_for_a_person(tmp_path: Path) -> None:
    paths, state, calls = A.Paths(tmp_path / "desk"), {}, []

    def blocked(url: str, **kw: Any) -> pf.Response:
        calls.append(url)
        return _resp(url, status=403, verdict="METHOD_BLOCKED", error="METHOD_BLOCKED: HTTP 403")
    rec = A.research_collect(paths, A.BY_ID[G.IN_ID], state, NOW, fetch=True, fixtures=None,
                             deadline=1e18, get=blocked)
    assert calls == [A.IBJA_URL] and rec["state"] == "HARD_STOP"     # no second request
    assert rec["hard_stop"]["waits_for"] == "a person" and rec["hard_stop"]["released_by"] is None
    rec = A.research_collect(paths, A.BY_ID[G.IN_ID], state, NOW + timedelta(hours=1),
                             fetch=True, fixtures=None, deadline=1e18, get=blocked)
    assert calls == [A.IBJA_URL] and rec["state"] == "HARD_STOP" and rec["requests"] == 0
    assert A.research_report({G.IN_ID: rec})["red_doors"] == [G.IN_ID]


# ---------------------------------------------------------------------------------- liveness --
def test_liveness_is_red_after_more_than_two_empty_runs_and_names_itself(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths, state = A.Paths(tmp_path / "desk"), {}

    def empty(url: str, **kw: Any) -> pf.Response:
        return _resp(url, status=None, error="URLError: timed out")
    seen = []
    for k in range(3):
        rec = A.research_collect(paths, A.BY_ID[G.VN_ID], state, NOW + timedelta(hours=k),
                                 fetch=True, fixtures=None, deadline=1e18, get=empty)
        seen.append(rec["state"])
    assert seen == ["AMBER", "AMBER", "RED"]                    # RED above 2, not at 2
    assert rec["empty_streak"] == 3 and "timed out" in state["research_lane"][G.VN_ID][
        "fail_reason"]
    # a fixture pass never moves the streak (it is not a reading of the source)
    A.research_collect(paths, A.BY_ID[G.VN_ID], state, NOW, fetch=True, fixtures=FIX,
                       deadline=1e18)
    assert state["research_lane"][G.VN_ID]["empty_streak"] == 3
    # the whole pass names the RED door in the organ's own status (health_board reads it)
    monkeypatch.setattr(A, "SOURCES", ())
    monkeypatch.setattr(pf, "get", empty)
    A._atomic(paths.state, state)
    rep = A.run(paths, donate=False, now=NOW + timedelta(hours=4))
    assert rep["status"].startswith("RED") and G.VN_ID in rep["status"]
    assert rep["research_lane"]["doors"][G.VN_ID]["state"] == "RED"
    # a landing clears it
    monkeypatch.setattr(pf, "get", _serving([]))
    rep = A.run(paths, donate=False, now=NOW + timedelta(hours=5))
    assert rep["research_lane"]["doors"][G.VN_ID]["state"] == "GREEN" and "status" not in rep


# ------------------------------------------------------------------- features -> cell path --
def test_features_reach_the_exogenous_conditioner_cell_path_on_the_asia_window(
        tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")
    _xau_parquet(paths.universe, DAYS)
    rep = A.run(paths, fixtures=FIX, donate=False, now=NOW)
    lane = rep["research_lane"]["doors"]
    assert lane[G.VN_ID]["series"]["premium_pct"] == 1
    assert lane[G.IN_ID]["series"]["premium_pct"] == 1
    for sid in G.RESEARCH_IDS:
        f = paths.series / f"alt_{sid}__premium_pct.csv"
        df = pd.read_csv(f)
        assert {"available_time", "event_time", "value", "surprise_z"} <= set(df.columns)
        assert (pd.to_datetime(df["available_time"], utc=True)
                >= pd.to_datetime(df["event_time"]).dt.tz_localize("UTC")).all()
    # the family reads the lake file on its own available_time clock
    from mt5desk.family_exogenous_conditioner import conditioner
    s = conditioner(f"alt_{G.IN_ID}__ibja_pm_999_inr", "value", "delta", lag_hours=24,
                    root=paths.series)
    assert s is not None and s.index.min() >= pd.Timestamp("2026-10-30 12:30", tz="UTC")
    # a PASSING gain test mints an exogenous_conditioner cell on XAUUSD, gold_asia selector
    gains = {f"{G.IN_ID}|premium_pct|XAUUSD": {"verdict": "PASS", "ic": -0.12, "n": 400},
             f"{G.VN_ID}|premium_pct|XAUUSD": {"verdict": "FAIL", "ic": 0.01, "n": 400}}
    cells = A.direct_cells(gains, NOW)
    assert len(cells) == 1
    c = cells[0]
    assert c["family"] == "exogenous_conditioner" and c["symbols"] == ["XAUUSD"]
    assert c["params"]["selector"] == "asia" and c["params"]["side_when_high"] == -1
    assert c["params"]["source"] == f"alt_{G.IN_ID}__premium_pct"
    assert c["provenance"]["research_only"] is True
    assert c["provenance"]["live_sizing_allowed"] is False
    # the research doors are judged, never read as live state or allocation intel
    assert f"{G.IN_ID}|premium_pct|XAUUSD" in rep["gain_tests"]
    intel = json.loads(paths.allocation_intel.read_text("utf-8"))
    comps = [x["source"] for v in intel["instruments"].values() for x in v["components"]]
    assert G.IN_ID not in comps and G.VN_ID not in comps
    st = json.loads((paths.desk / "reports" / G.STATE_FILE).read_text("utf-8"))
    assert st["states"][G.VN_ID]["verdict"] == G.UNMEASURED            # the LIVE state
    assert st["research_lane"][G.IN_ID]["live_sizing_allowed"] is False
    # the live lane still never fetches them as live input
    assert rep["sources"][G.IN_ID]["requests"] == 0
    assert rep["sources"][G.VN_ID]["requests"] == 0


# ------------------------------------------------------------------------------------- terms --
def test_terms_rows_are_research_only_with_their_clauses_quoted() -> None:
    for key in ("in_ibja_premium", "in_rbi_reference_rate", "vn_vcb_fx", "vn_sjc_premium"):
        row = tf.SOURCE_POLICY[key]
        assert row["status"] == tf.IDEAS_ONLY and row["research_only"] is True, key
        assert tf.terms_verdict(key) == "to_confirm" and tf.input_source(key) == key, key
    ibja = tf.SOURCE_POLICY["in_ibja_premium"]["terms"]
    assert ibja["checked_at"] == "2026-11-04"
    assert "only through OFFICIAL IBJA API" in ibja["clauses"]["api"]
    assert "prohibited" in tf.SOURCE_POLICY["in_rbi_reference_rate"]["terms"]["clauses"][
        "caching"]
    assert tf.terms_state("vn_vcb_fx") == tf.UNREAD
    # the research routes are refused to any live-input organ by URL as well as by name
    assert tf.input_source(A.IBJA_URL) == "in_ibja_premium"
    assert tf.input_source(A.RBI_HOME_URL) == "in_rbi_reference_rate"
    assert tf.input_source(A.VCB_XML_URL) == "vn_vcb_fx"
    assert tf.input_source("https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx") is None
    lines = G.research_missed_growth()
    assert {ln["source"] for ln in lines} == {"vn_sjc_premium", "vn_vcb_fx", "in_ibja_premium",
                                              "in_rbi_reference_rate"}
    assert all(ln["delta_elogw"] == "UNMEASURED" for ln in lines)
    assert A.TERMS[G.IN_ID][0] == "to_confirm" == A.BY_ID[G.IN_ID].terms


# ---------------------------------------------------------------------------------- footprint --
def test_footprint_rows_and_frame(tmp_path: Path) -> None:
    from research import jp_retail_flow as J
    shape = set(J.FOOTPRINT_ROWS[0]) - {"also_class"}
    for row in G.FOOTPRINT_ROWS:
        assert shape <= set(row) and row["class"] == "retail" and row["targets"] == ["XAUUSD"]
        assert row["live_sizing_allowed"] is False and row["session"] == "asia"
    assert {r["region"] for r in G.FOOTPRINT_ROWS} == {"VN", "IN"}
    paths = A.Paths(tmp_path / "desk")
    _xau_parquet(paths.universe, DAYS)
    A.run(paths, fixtures=FIX, donate=False, now=NOW)
    fr = G.footprint_frame(G.IN_ID, paths.series)
    assert set(G.RESEARCH_SERIES[G.IN_ID]) <= set(fr.columns) and "available_utc" in fr.columns
    assert str(fr["available_utc"].dt.tz) == "UTC" and fr.index.is_monotonic_increasing
    assert fr.loc["2026-11-03", "available_utc"] == pd.Timestamp("2026-11-03 12:30", tz="UTC")
    assert G.footprint_frame(G.VN_ID, tmp_path / "nothing").empty
    with pytest.raises(KeyError):
        G.footprint_frame("nope")
