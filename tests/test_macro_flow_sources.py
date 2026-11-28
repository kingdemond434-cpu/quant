"""Macro-flow sources through alt_proxies: US Treasury auction demand (F1), the NY Fed Staff
Nowcast's revisions (F2), gold-ETF holdings and GDPNow (BLOCKED_ON_TERMS) and the BoC / CNB
policy decisions.

Every fixture is small and SYNTHETIC (tests/fixtures/alt_proxies, values illustrative, never the
publisher's); nothing here touches the network. The rows ride the organ's one hourly leg and its
exogenous_conditioner path; the rows whose own terms refuse commercial or automated reuse are
BLOCKED_ON_TERMS, never fetched, and each carries a missed-growth line.
"""
from __future__ import annotations

import io
import sys
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import alt_proxies as A  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "alt_proxies"
NOW = datetime(2026, 10, 14, 12, tzinfo=UTC)
LIVE = ("us_treasury_auctions", "us_nyfed_nowcast", "ca_boc_policy_rate", "cz_cnb_repo_rate")
HELD = ("us_atlfed_gdpnow", "us_spdr_gld_holdings", "us_ishares_iau_holdings")
FILES = {"us_treasury_auctions": "us_treasury_auctions.json",
         "us_nyfed_nowcast": "us_nyfed_nowcast.xlsx",
         "ca_boc_policy_rate": "ca_boc_policy_rate.json",
         "cz_cnb_repo_rate": "cz_cnb_repo_rate.txt"}


def _body(sid: str) -> bytes:
    return (FIX / FILES[sid]).read_bytes()


def _by(obs: list[A.Obs], series: str) -> dict[date, float]:
    return {o.period: o.value for o in obs if o.series == series}


# ============================================================================ F1 auctions
def _auction(d: str, term: str, hy: float, med: float, dealer: float = 0.1,
             kind: str = "Note", **kw: str) -> dict[str, Any]:
    return {"auction_date": d, "security_type": kind, "security_term": term,
            "inflation_index_security": "No", "floating_rate": "No", "high_yield": str(hy),
            "avg_med_yield": str(med), "bid_to_cover_ratio": "2.5", "comp_accepted": "100",
            "indirect_bidder_accepted": "60", "primary_dealer_accepted": str(dealer * 100), **kw}


def test_auction_tail_is_a_same_tenor_deviation_from_earlier_auctions_only() -> None:
    import json
    rows = [_auction(f"2026-0{m}-05", "10-Year", 4.0, 4.0 - t / 100, dealer=0.1)
            for m, t in zip((1, 2, 3, 4), (1.0, 2.0, 3.0, 5.0), strict=True)]
    rows += [_auction("2026-04-05", "30-Year", 4.5, 4.4, kind="Bond"),               # no base
             _auction("2026-04-05", "10-Year", 2.0, 1.0, inflation_index_security="Yes"),
             _auction("2026-04-05", "2-Year", 9.0, 1.0, floating_rate="Yes"),
             {"auction_date": "2026-04-05", "security_type": "Bill", "high_yield": "4"}]
    obs = A.parse_fiscal_auctions(json.dumps({"data": rows}).encode(), A.Ctx())
    tail = _by(obs, "ust_tail_dev_bp")
    assert list(tail) == [date(2026, 4, 5)]               # three earlier same-tenor auctions
    assert tail[date(2026, 4, 5)] == pytest.approx(5.0 - 2.0)          # 5bp over a 2bp run
    assert _by(obs, "ust_dealer_dev")[date(2026, 4, 5)] == pytest.approx(0.0)


def test_auction_fixture_skips_tips_bills_and_unreported_results() -> None:
    obs = A.parse_fiscal_auctions(_body("us_treasury_auctions"), A.Ctx())
    assert {o.series for o in obs} == {"ust_tail_dev_bp", "ust_dealer_dev", "ust_indirect_dev",
                                       "ust_btc_dev"}
    assert min(o.period for o in obs) == date(2025, 1, 28)        # 4th week: 3-auction base
    assert A.parse_fiscal_auctions(b'{"data": "x"}', A.Ctx()) == []


# ============================================================================ F2 nowcast
def _xlsx(rows: list[list[Any]]) -> bytes:
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rns = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    xml_rows = []
    for i, row in enumerate(rows, 1):
        cells = "".join(
            (f'<c r="{chr(65 + j)}{i}" t="inlineStr"><is><t>{x}</t></is></c>'
             if isinstance(x, str) else f'<c r="{chr(65 + j)}{i}"><v>{x}</v></c>')
            for j, x in enumerate(row) if x is not None)
        xml_rows.append(f'<row r="{i}">{cells}</row>')
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("xl/workbook.xml", f'<workbook {ns} {rns}><sheets><sheet name="S" '
                   'sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
                   'relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
                   "</Relationships>")
        z.writestr("xl/worksheets/sheet1.xml",
                   f'<worksheet {ns}><sheetData>{"".join(xml_rows)}</sheetData></worksheet>')
    return b.getvalue()


def test_nowcast_revision_is_the_current_quarters_change_between_updates() -> None:
    obs = A.parse_nyfed_nowcast(_body("us_nyfed_nowcast"), A.Ctx())
    lv, rev = _by(obs, "nowcast_level"), _by(obs, "nowcast_revision_pp")
    assert len(lv) == 30 and len(rev) == 28
    days = sorted(lv)
    # the first update has no prior; the update where a new quarter first appears has no prior
    # value FOR THAT quarter, so neither is a revision
    assert days[0] not in rev
    assert sum(1 for d in days if d not in rev) == 2


def test_nowcast_reads_a_wide_layout_by_header_name_and_refuses_an_unknown_one() -> None:
    wide = _xlsx([["note"], ["Date", "2026:Q3", "2026:Q4"], ["2026-09-04", 2.0, None],
                  ["2026-09-11", 2.5, 1.0], ["2026-09-18", 2.25, 1.5]])
    obs = A.parse_nyfed_nowcast(wide, A.Ctx())
    assert _by(obs, "nowcast_level") == {date(2026, 9, 4): 2.0, date(2026, 9, 11): 1.0,
                                         date(2026, 9, 18): 1.5}
    # 09-11 is the first print of 2026:Q4, so its first revision is the next update's
    assert _by(obs, "nowcast_revision_pp") == {date(2026, 9, 18): pytest.approx(0.5)}
    odd = _xlsx([["Week", "GDP"], ["2026-09-04", 2.0], ["2026-09-11", 2.5]])
    assert A.parse_nyfed_nowcast(odd, A.Ctx()) == []                  # UNMEASURED, not a guess
    assert A.parse_nyfed_nowcast(b"PK\x03\x04garbage", A.Ctx()) == []


# ============================================================================ policy decisions
def test_policy_decisions_are_changes_only_and_never_reach_back_before_the_window() -> None:
    cnb = _by(A.parse_cnb_repo(_body("cz_cnb_repo_rate"), A.Ctx()), "policy_rate_change_bp")
    assert date(2000, 1, 28) not in cnb                   # the in-window baseline, not a -3375bp
    assert cnb[date(2000, 7, 26)] == pytest.approx(75.0)
    assert all(d.year >= 2000 for d in cnb) and len(cnb) == 16
    assert A.parse_cnb_repo(b"20260619|3,75\n20260801|4,00\n", A.Ctx())[0].value == 25.0
    boc = _by(A.parse_boc_valet(_body("ca_boc_policy_rate"), A.Ctx()), "policy_rate_change_bp")
    assert boc and all(v != 0 for v in boc.values()) and len(boc) < 20


# ============================================================================ states and terms
def test_live_rows_are_confirmed_keyless_and_held_rows_are_blocked() -> None:
    for sid in LIVE:
        src = A.BY_ID[sid]
        assert src.terms == "confirmed" and not src.key_env, sid
        assert A.status_of(src, {}) == "UNMEASURED_LIVE_YIELD", sid
        ev = A.TERMS_EVIDENCE[sid]
        assert ev["terms_quote"] and not ev["terms_quote"].startswith("(not") and ev["credit"]
    for sid in HELD:
        src = A.BY_ID[sid]
        assert src.parse is None and src.terms in ("refused", "to_confirm"), sid
        assert A.status_of(src, {}) == f"BLOCKED_ON_TERMS:{src.terms}", sid
        assert "HELD, NEVER FETCHED" in src.note, sid
    assert "automated process" in A.TERMS_EVIDENCE["us_nyfed_nowcast"]["terms_quote"]
    assert "without restriction" in A.TERMS_EVIDENCE["us_treasury_auctions"]["terms_quote"]
    assert "freely use, copy" in A.TERMS_EVIDENCE["ca_boc_policy_rate"]["terms_quote"]
    assert "store, distribute and reproduce" in A.TERMS_EVIDENCE["cz_cnb_repo_rate"][
        "terms_quote"]
    assert "non-commercial" in A.TERMS_EVIDENCE["us_spdr_gld_holdings"]["terms_quote"]
    assert "robot, spider" in A.TERMS_EVIDENCE["us_ishares_iau_holdings"]["terms_quote"]


def test_held_rows_are_never_fetched(tmp_path: Path) -> None:
    def boom(url: str) -> tuple[bytes, str]:
        raise AssertionError(f"fetched {url}")

    for sid in HELD:
        rec = A.collect(A.Paths(tmp_path / "desk"), A.BY_ID[sid], {}, NOW, fetch=True,
                        fixtures=None, deadline=1e18, getter=boom)
        assert rec["requests"] == 0, sid


def test_requests_carry_no_key_and_hit_only_the_publishers_hosts() -> None:
    hosts = {"us_treasury_auctions": "https://api.fiscaldata.treasury.gov/",
             "us_nyfed_nowcast": "https://www.newyorkfed.org/",
             "ca_boc_policy_rate": "https://www.bankofcanada.ca/valet/",
             "cz_cnb_repo_rate": "https://www.cnb.cz/"}
    for sid, host in hosts.items():
        (req,) = A.requests_for(A.BY_ID[sid], NOW, {})
        assert req.url.startswith(host), sid
        assert "{" not in req.url and "key" not in req.url.lower(), sid


# ============================================================================ PIT + cells
def _points(paths: A.Paths, sid: str) -> dict[str, list[dict[str, Any]]]:
    src = A.BY_ID[sid]
    rec = A.collect(paths, src, {}, NOW, fetch=True, fixtures=None, deadline=1e18,
                    getter=lambda url: (_body(sid), "application/octet-stream"))
    assert rec["parsed"] > 0 and rec["merge"]["added"] > 0, sid
    store: dict[str, Any] = A._read_json(paths.obs_dir / f"{sid}.json", {})
    pts: dict[str, list[dict[str, Any]]] = A.build_points(src, store)
    return pts


@pytest.mark.parametrize(("sid", "series", "hour"), [
    ("us_treasury_auctions", "ust_tail_dev_bp", 19),     # results print after 13:00 ET
    ("us_nyfed_nowcast", "nowcast_revision_pp", 18),     # Fridays 11:45 ET
    ("ca_boc_policy_rate", "policy_rate_change_bp", 16),  # 09:45 ET
    ("cz_cnb_repo_rate", "policy_rate_change_bp", 16)])   # 14:30 CET
def test_points_are_available_only_after_publication(tmp_path: Path, sid: str, series: str,
                                                     hour: int) -> None:
    pts = _points(A.Paths(tmp_path / "desk"), sid)[series]
    assert pts
    for p in pts:
        avail = datetime.fromisoformat(p["available_time"])
        event = date.fromisoformat(p["d"])
        assert avail.weekday() < 5 and avail.date() >= event, (sid, p)
        if avail.date() == event:
            assert avail.hour >= hour, (sid, p)


@pytest.mark.parametrize(("sid", "series", "sym", "prior"), [
    ("us_treasury_auctions", "ust_tail_dev_bp", "NAS100", -1),
    ("us_treasury_auctions", "ust_dealer_dev", "USDJPY", 1),
    ("us_nyfed_nowcast", "nowcast_revision_pp", "XAUUSD", -1)])
def test_series_reach_their_instruments_as_conditioner_cells(
        tmp_path: Path, sid: str, series: str, sym: str, prior: int) -> None:
    from mt5desk.family_exogenous_conditioner import conditioner
    paths = A.Paths(tmp_path / "desk")
    src = A.BY_ID[sid]
    pts = _points(paths, sid)
    assert src.instruments_for(series)[sym] == prior
    gains = A.gain_tests(paths, {sid: pts})
    key = f"{sid}|{series}|{sym}"
    assert gains[key]["verdict"] == A.UNMEASURED                 # no bars here: never a zero
    A.write_lake_series(paths, src, pts)
    s = conditioner(A.lake_file(src, series), "surprise_z", "level_z", root=paths.series)
    assert s is not None and len(s) > 5
    assert s.index.min() >= pd.Timestamp(pts[series][0]["available_time"])
    cells = A.direct_cells({key: {"verdict": "PASS", "ic": 0.2}}, NOW)
    assert len(cells) == 1 and cells[0]["symbol"] == sym
    assert cells[0]["family"] == "exogenous_conditioner"
    assert cells[0]["params"]["side_when_high"] == 1                 # the MEASURED sign


def test_the_organs_fixture_pass_carries_the_new_rows(tmp_path: Path) -> None:
    rep = A.run(A.Paths(tmp_path / "desk"), fixtures=FIX, donate=False, now=NOW)
    for sid in LIVE:
        assert rep["sources"][sid]["series"], sid
    for sid in HELD:
        assert sid in rep["blocked_on_terms"] and rep["sources"][sid]["series"] == {}, sid


# ============================================================================ audit 2026-10-14
def test_nowcast_rows_before_the_2023_relaunch_never_become_observations() -> None:
    """MACRO_FLOW_SOURCES M1: rows dated before NOWCAST_SINCE are the model's reconstruction,
    not what was printed then, so they are dropped before levels and revisions are formed."""
    wide = _xlsx([["Date", "2023:Q3"], ["2019-06-07", 1.0], ["2023-09-01", 2.0],
                  ["2023-09-08", 2.5], ["2023-09-15", 3.0]])
    obs = A.parse_nyfed_nowcast(wide, A.Ctx())
    assert min(o.period for o in obs) == A.NOWCAST_SINCE
    assert _by(obs, "nowcast_revision_pp") == {date(2023, 9, 15): pytest.approx(0.5)}
    only_before = _xlsx([["Date", "2019:Q2"], ["2019-06-07", 1.0], ["2019-06-14", 1.5]])
    assert A.parse_nyfed_nowcast(only_before, A.Ctx()) == []


def test_a_reopening_shares_its_original_tenors_baseline() -> None:
    """MACRO_FLOW_SOURCES S1: a reopened 10y prints "9-Year 10-Month"; keyed on the original
    term it joins the 10-Year history instead of starting a bucket of its own."""
    import json
    rows = [_auction(f"2026-0{m}-05", "10-Year", 4.0, 4.0 - t / 100,
                     original_security_term="10-Year")
            for m, t in zip((1, 2, 3), (1.0, 2.0, 3.0), strict=True)]
    rows.append(_auction("2026-04-05", "9-Year 10-Month", 4.0, 3.95,
                         original_security_term="10-Year"))
    tail = _by(A.parse_fiscal_auctions(json.dumps({"data": rows}).encode(), A.Ctx()),
               "ust_tail_dev_bp")
    assert tail[date(2026, 4, 5)] == pytest.approx(5.0 - 2.0)
    assert "original_security_term" in A.FISCAL_AUCTIONS_URL


def test_every_held_source_carries_a_missed_growth_line(tmp_path: Path) -> None:
    """A terms hold is named as a growth cost in the hourly report, its size UNMEASURED, with
    what it forgoes, what stands in and what reopens it."""
    assert set(A.MACRO_FLOW_MISSED_GROWTH) == set(HELD)
    rep = A.run(A.Paths(tmp_path / "desk"), fixtures=FIX, donate=False, now=NOW)
    lines = {ln["source"]: ln for ln in rep["missed_growth_lines"]}
    assert set(lines) == set(rep["blocked_on_terms"])
    for sid in HELD:
        ln = lines[sid]
        assert ln["status"] == "BLOCKED_ON_TERMS:refused" and ln["delta_elogw"] == "UNMEASURED"
        assert ln["reason"] and ln["forgone"] and ln["stands_in"] and ln["reopens_when"], sid
        assert ln["instruments"], sid


# ============================================================================ terms re-read
def test_terms_were_reread_and_no_route_rides_fred() -> None:
    """Every macro-flow verdict carries the 2026-11-17 re-read; no route touches a host the
    desk's terms refuse (FRED / ALFRED / stlouisfed)."""
    for sid in (*LIVE, *HELD):
        ev = A.TERMS_EVIDENCE[sid]
        assert ev["checked_at"] == "2026-11-17" and ev["robots"], sid
        assert "stlouisfed" not in A.BY_ID[sid].url.lower(), sid
        assert "fred" not in A.BY_ID[sid].url.lower(), sid
    assert "commercial purposes" in A.TERMS_EVIDENCE["us_treasury_auctions"]["terms_quote"]
    assert "business purposes" in A.TERMS_EVIDENCE["us_nyfed_nowcast"]["terms_quote"]
    assert "commercial gain" in A.TERMS_EVIDENCE["us_atlfed_gdpnow"]["terms_quote"]


# ============================================================================ robots gate
def _reader(code: int, text: str = "") -> Any:
    return lambda url: (code, text)


@pytest.mark.parametrize(("code", "text", "ok"), [
    (200, "User-agent: *\nAllow: /\n", True),
    (200, "User-agent: *\nDisallow: /services/\n", False),
    (404, "", True),                                    # no file: allowed (RFC 9309)
    (403, "", False), (429, "", False), (503, "", False),  # hard stop / unreachable: closed
    (200, "<!DOCTYPE html><html>", False)])
def test_robots_gate_fails_closed(code: int, text: str, ok: bool) -> None:
    url = A.FISCAL_AUCTIONS_URL
    assert A.robots_allows(url, reader=_reader(code, text))[0] is ok


def test_a_robots_refusal_is_a_loud_error_never_a_fetch() -> None:
    calls: list[str] = []

    def getter(url: str) -> tuple[bytes, str]:
        calls.append(url)
        return b"{}", "application/json"

    gated = A.robots_gated(getter, lambda url: (False, "robots.txt Disallow covers this path"))
    with pytest.raises(PermissionError, match="robots gate"):
        gated(A.FISCAL_AUCTIONS_URL)
    assert calls == []
    assert frozenset(LIVE) == A.MACRO_FLOW_ROBOTS_GATED


def test_a_fetched_body_that_parses_nothing_fails_loud(tmp_path: Path) -> None:
    rec = A.collect(A.Paths(tmp_path / "desk"), A.BY_ID["us_nyfed_nowcast"], {}, NOW,
                    fetch=True, fixtures=None, deadline=1e18,
                    getter=lambda url: (b"PK\x03\x04garbage", "application/octet-stream"))
    assert rec["parsed"] == 0 and any("UNMEASURED" in e for e in rec["errors"])
