"""Options-implied positioning from the CFTC: combined minus futures-only, robots first."""
from __future__ import annotations

import json
import sys
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import free_stack as fs  # noqa: E402
from libs.data import free_stack_cftc as C  # noqa: E402

NOW = datetime(2026, 11, 13, 22, 0, tzinfo=UTC)
ROW = {"id": "cftc_options_combined", "kind": "cftc_options"}


def _rows(oi: float, ncl: float, ncs: float, cl: float, cs: float) -> list[dict[str, str]]:
    return [{"report_date_as_yyyy_mm_dd": f"2026-11-{d:02d}T00:00:00.000",
             "open_interest_all": str(oi), "noncomm_positions_long_all": str(ncl),
             "noncomm_positions_short_all": str(ncs), "comm_positions_long_all": str(cl),
             "comm_positions_short_all": str(cs)} for d in (3, 10)]


def _fake(sent: list[tuple[str, str]]):
    def fetch(url, headers, body):
        sent.append((url, (headers or {}).get("User-Agent", "")))
        ds = "comb" if C.COMBINED in url else "fut"
        rows = (_rows(1000, 400, 100, 200, 500) if ds == "comb"
                else _rows(800, 300, 100, 200, 400))
        return json.dumps(rows).encode()
    return fetch


def test_options_book_is_combined_minus_futures(monkeypatch) -> None:
    monkeypatch.setattr(C, "ROBOTS", lambda u: None)
    sent: list[tuple[str, str]] = []
    h = C.fetch_cftc_options(_fake(sent), ROW, {}, NOW)
    assert h.status == "OK" and h.cursor == {"backfilled": True}
    got = {(o["key"], o["period_end"]): o["value"] for o in h.obs}
    assert got[("XAUUSD_spec_net_comb", "2026-11-10")] == pytest.approx(0.3)
    assert got[("XAUUSD_spec_opt_delta", "2026-11-10")] == pytest.approx((300 - 200) / 1000)
    assert got[("XAUUSD_comm_opt_delta", "2026-11-10")] == pytest.approx((-300 + 200) / 1000)
    assert got[("XAUUSD_opt_oi_share", "2026-11-10")] == pytest.approx(0.2)
    # JPY futures are inverted for USDJPY; the OI share is not a direction and is never flipped
    assert got[("USDJPY_spec_opt_delta", "2026-11-10")] == pytest.approx(-0.1)
    assert got[("USDJPY_opt_oi_share", "2026-11-10")] == pytest.approx(0.2)
    assert "USDJPY" in h.columns["US500_comm_opt_delta"]["hypothesis"]
    assert {ua for _, ua in sent} == {C.AGENT}
    assert len(sent) == 2 * len(C.CONTRACTS)


def test_robots_refusal_sends_nothing(monkeypatch) -> None:
    monkeypatch.setattr(C, "ROBOTS", lambda u: "robots.txt disallows this path")
    sent: list[tuple[str, str]] = []
    h = C.fetch_cftc_options(_fake(sent), ROW, {}, NOW)
    assert sent == [] and not h.obs and h.status == "BLOCKED"
    assert "ROBOTS_REFUSED" in h.detail


def test_missing_fields_read_unmeasured_never_zero(monkeypatch) -> None:
    monkeypatch.setattr(C, "ROBOTS", lambda u: None)

    def fetch(url, headers, body):
        return json.dumps([{"report_date_as_yyyy_mm_dd": "2026-11-10",
                            "open_interest_all": "5"}]).encode()
    h = C.fetch_cftc_options(fetch, ROW, {}, NOW)
    assert not h.obs and h.status == "EMPTY" and "rows lack" in h.detail


def test_after_backfill_only_the_recent_window_is_reread(monkeypatch) -> None:
    monkeypatch.setattr(C, "ROBOTS", lambda u: None)
    sent: list[tuple[str, str]] = []
    C.fetch_cftc_options(_fake(sent), ROW, {"backfilled": True}, NOW)
    where = urllib.parse.parse_qs(urllib.parse.urlparse(sent[0][0]).query)["$where"][0]
    assert ">= '2026-10-16'" in where


def test_the_kind_is_routed_and_the_roster_row_loads() -> None:
    from free_stack_hunter import load_roster
    assert fs.FETCHERS["cftc_options"] is C.fetch_cftc_options
    rows, bad = load_roster()
    assert not bad
    row = next(r for r in rows if r["id"] == "cftc_options_combined")
    assert row["kind"] == "cftc_options" and row["terms"] == "confirmed"
    assert float(row["lag_hours"]) >= 90           # Tuesday as-of, published Friday
