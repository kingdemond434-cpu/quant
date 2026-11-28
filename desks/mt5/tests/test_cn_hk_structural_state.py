"""Build-check rows 107 and 108: the China/HK structural state.

The fix gap and band edge are built from the BIS republication of the parity, stamped no earlier
than the 09:15 Beijing fix, with the CNH leg taken from a bar that closed before it. The Golden
Week cells come from the pack's own closure table. HKEX Stock Connect and SSE limit-breadth are
fenced on their terms with the clause verbatim and are never contacted. The PBOC site is read
only for its robots.txt, never for data."""
from __future__ import annotations

# ruff: noqa: E402 -- tests add the desk roots before importing standalone research modules.
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for path in (DESK, DESK / "research", DESK.parent.parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from research.countries.cn import pack as cn
from research.countries.hk import pack as hk

from research import cn_hk_structural_state as m


def _fence(fid: str) -> dict[str, Any]:
    return next(f for f in m.FENCES if f["id"] == fid)


def test_hkex_and_sse_are_terms_blocked_with_the_clause_verbatim() -> None:
    hkex = _fence("hkex_stock_connect_flows")
    assert hkex["status"] == "TERMS_BLOCKED" and hkex["row"] == 108
    assert "programmatic, scripted or other mechanical means" in hkex["clause"]
    sse = _fence("sse_limit_breadth")
    assert sse["status"] == "TERMS_BLOCKED" and "电子抓取系统" in sse["clause"]
    assert _fence("pboc_central_parity")["status"] == "HELD"
    assert _fence("cfets_central_parity")["status"] == "TERMS_BLOCKED"


def test_the_packs_carry_the_rows() -> None:
    row = next(r for r in hk.POSITIONING_SOURCES if r["id"] == "connect_daily_net_flows")
    assert row["terms_status"] == "TERMS_BLOCKED"
    assert any("HKEX" in r["ground"] for r in hk.REFUSED_SOURCES)
    assert cn.STRUCTURAL_STATE["organ"].endswith("cn_hk_structural_state.py")
    assert any(d["name"] == "bis_republished_central_parity" for d in cn.DATASETS)


@pytest.mark.parametrize(("use", "level"), [(0.1, 0.0), (0.6, 1.0), (-0.8, -2.0), (0.95, 3.0)])
def test_band_edge_level(use: float, level: float) -> None:
    assert m.band_level(use) == level


def _broker_bars(days: int = 60) -> pd.DataFrame:
    # Broker stamps are New York + 7h, i.e. UTC+2 in winter: a 03:00 broker bar starts 01:00 UTC.
    idx = pd.date_range("2025-01-06", periods=24 * days, freq="h")
    close = 7.30 + 0.0001 * np.arange(len(idx))
    bars = pd.DataFrame({"close": close}, index=idx)
    # a spike in the bar starting 01:00 UTC (broker 03:00): it closes AFTER the fix, never used
    bars.loc[bars.index.hour == 3, "close"] = 99.0
    return bars


def test_cnh_leg_closes_before_the_fix() -> None:
    cnh = m.cnh_before_fix(_broker_bars())
    assert len(cnh) >= 50
    assert float(cnh.max()) < 50.0


def _bis_csv(days: pd.DatetimeIndex) -> str:
    lines = ["FREQ,REF_AREA,CURRENCY,COLLECTION,TIME_PERIOD,OBS_VALUE"]
    lines += [f"D,CN,CNY,A,{d:%Y-%m-%d},{7.20 + 0.0002 * i:.4f}" for i, d in enumerate(days)]
    return "\n".join(lines) + "\n"


def test_parity_frame_is_stamped_at_the_fix() -> None:
    cnh = m.cnh_before_fix(_broker_bars())
    parity = m.parse_bis_xru(_bis_csv(pd.DatetimeIndex(cnh.index)))
    f = m.parity_frame(parity, cnh)
    assert len(f) == len(cnh)
    at = pd.DatetimeIndex(f["available_time"])
    assert (at.hour == 1).all() and (at.minute == 30).all()
    assert (pd.DatetimeIndex(f["event_time"]).normalize() == at.normalize()).all()
    assert {"dev_pips", "band_use", "band_edge_level"} <= set(f.columns)


def test_golden_week_counts_to_and_from_the_national_day_block() -> None:
    gw = m.golden_week_frame([2025], cn.holidays, cn.cn_long_closures)
    by = gw.set_index(pd.DatetimeIndex(gw["event_time"]).date)
    assert by.loc[date(2025, 9, 30), "gw_days_to"] == 1.0
    assert by.loc[date(2025, 10, 1), "mainland_closed_weekday"] == 1.0
    assert by.loc[date(2025, 10, 9), "gw_days_since"] == 1.0
    assert np.isnan(by.loc[date(2025, 6, 2), "gw_days_to"])


class _Net:
    """Records every URL asked for and answers BIS and robots only."""

    def __init__(self, bis: str, robots: str = "User-agent: *\nAllow: /\n"):
        self.bis, self.robots = bis, robots
        self.urls: list[str] = []

    def __call__(self, url: str) -> str:
        self.urls.append(url)
        if url.endswith("/robots.txt"):
            return self.robots
        if "stats.bis.org" in url:
            return self.bis
        raise AssertionError(f"contacted {url}")


def _isolate(monkeypatch: pytest.MonkeyPatch, tmp: Path) -> None:
    monkeypatch.setattr(m, "STATE_DIR", tmp / "state")
    monkeypatch.setattr(m, "RAW_PARITY", tmp / "state" / "parity.parquet")
    monkeypatch.setattr(m, "STATE", tmp / "state" / "state.json")
    monkeypatch.setattr(m, "SERIES", tmp / "series")
    monkeypatch.setattr(m, "OUT", tmp / "OUT.json")
    monkeypatch.setattr(m, "_universe", lambda: frozenset({"USDCNH", "HK50", "CHINAH"}))


def test_a_pass_mints_once_and_never_touches_a_fenced_host(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    bars = _broker_bars()
    days = pd.DatetimeIndex(m.cnh_before_fix(bars).index)
    net = _Net(_bis_csv(days))
    seen: list[dict[str, Any]] = []

    def enqueue(**kw: Any) -> tuple[str, bool]:
        seen.append(kw)
        return "id", True

    now = datetime(2026, 11, 18, 6, tzinfo=UTC)
    doc = m.build(get_text=net, bars=lambda s: bars if s == "USDCNH" else None,
                  enqueue=enqueue, now=now)
    assert doc["status"] == "MEASURED"
    assert set(doc["series"]) == {"cn_parity_dev", "cn_golden_week"}
    assert seen and {k["family"] for k in seen} == {"exogenous_conditioner"}
    assert {k["symbol"] for k in seen} <= {"USDCNH", "HK50", "CHINAH"}
    assert doc["cells"]["unquoted_targets"] == ["CN50"]
    for url in net.urls:
        assert "hkex" not in url and "sse.com.cn" not in url and "chinamoney" not in url
        assert "pbc.gov.cn" not in url or url.endswith("/robots.txt")
    assert doc["pboc_robots"]["data_fetched"] is False
    assert (tmp_path / "series" / "cn_parity_dev.parquet").exists()
    first = len(seen)
    again = m.build(get_text=net, bars=lambda s: bars if s == "USDCNH" else None,
                    enqueue=enqueue, now=now)
    assert len(seen) == first and again["cells"]["cells_minted_this_pass"] == 0


def test_a_robots_disallow_fetches_nothing(monkeypatch: pytest.MonkeyPatch,
                                           tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    net = _Net("", robots="User-agent: *\nDisallow: /\n")
    doc = m.build(get_text=net, bars=lambda s: None, enqueue=lambda **k: ("id", True),
                  now=datetime(2026, 11, 18, 6, tzinfo=UTC))
    assert not any("stats.bis.org/api" in u for u in net.urls)
    assert doc["pboc_robots"]["robots_allows"] is False
    assert any(n.get("series") == "cn_parity_dev" and n["status"] == "UNMEASURED"
               for n in doc["notes"])
    assert "cn_golden_week" in doc["series"]


def test_the_user_agent_names_no_person_or_address() -> None:
    assert m.UA == m.HONEST_UA == "quant-desk-research/1.0 (automated research; honours robots.txt)"
    low = m.UA.lower()
    assert "github.com/" not in low and "kingdemond" not in low and "@" not in m.UA


@pytest.mark.parametrize("body", [
    "<html><body>Access denied</body></html>",
    "   <!DOCTYPE html><html></html>",
    "\n<?xml version='1.0'?><error/>",
    "User-agent: *\nDisallow:\n" + " " * 10 + "<HTML>",
])
def test_an_html_robots_body_is_unread_never_an_allow(body: str) -> None:
    ok, why = m.robots_verdict("https://example.org/data.csv", lambda u: body)
    assert ok is False and "unread" in why


@pytest.mark.parametrize("code", [404, 410])
def test_a_missing_robots_file_allows(code: int) -> None:
    def gone(url: str) -> str:
        raise m.FetchError(code, url, f"HTTP {code}")
    assert m.robots_verdict("https://example.org/data.csv", gone)[0] is True


def test_a_plain_robots_file_is_still_read() -> None:
    ok, _ = m.robots_verdict("https://example.org/data.csv",
                             lambda u: "User-agent: *\nDisallow: /private/\n")
    assert ok is True


def test_a_429_is_a_timed_hold_and_a_refusal_is_not(monkeypatch: pytest.MonkeyPatch,
                                                    tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    t0 = datetime(2026, 11, 18, 6, tzinfo=UTC)
    for code, released_after_a_day in ((429, True), (403, False), (451, False), (401, False)):
        state: dict[str, Any] = {}

        def stop(url: str, code: int = code) -> str:
            if url.endswith("/robots.txt"):
                return "User-agent: *\nAllow: /\n"
            raise m.HardStop(code, url)

        m.collect_parity(stop, state, [], t0)
        assert state["hard_stops"]["bis_xru_cny"]["code"] == code
        asked: list[str] = []

        def ok(url: str, asked: list[str] = asked) -> str:
            asked.append(url)
            return "User-agent: *\nAllow: /\n" if url.endswith("/robots.txt") else ""

        m.collect_parity(ok, state, [], t0 + timedelta(hours=23))
        assert asked == []
        m.collect_parity(ok, state, [], t0 + timedelta(hours=25))
        assert bool(asked) is released_after_a_day
        assert ("bis_xru_cny" in state["hard_stops"]) is not released_after_a_day
