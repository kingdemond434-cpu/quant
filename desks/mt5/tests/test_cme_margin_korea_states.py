"""CME margin events stay fenced on CME's terms; the USDKRW expiry state is calendar-exact."""
from __future__ import annotations

import json
import socket
import sys
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.countries.kr import pack as kr  # noqa: E402

from libs.data.refused_hosts import refusal  # noqa: E402
from libs.regime.event_state import ASIA_EVENT_RULES, asia_schedule  # noqa: E402
from research import cme_margin_events as cme  # noqa: E402


@pytest.fixture
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("network contacted")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def test_cme_is_fenced_and_never_fetched(no_network, tmp_path: Path) -> None:
    doc = cme.write(tmp_path / "cme.json", now=datetime(2026, 11, 18, tzinfo=UTC))
    assert doc["status"] == "TERMS_BLOCKED" and doc["cells"] == [] and doc["fetched"] == 0
    assert doc["verdict"].startswith("TERMS_BLOCKED")
    assert refusal(cme.ADVISORY_ROOT) and doc["source"]["refused_host"] != "NOT_LISTED"
    assert any("systematic retrieval" in t["clause"] for t in doc["source"]["terms"])
    assert set(doc["targets"]) == {"XAUUSD", "XTIUSD", "XBRUSD", "US500", "NAS100", "US30"}
    assert doc["channel"] == "forced_flow" and doc["cell_schema"]["channel"] == "forced_flow"
    assert json.loads((tmp_path / "cme.json").read_text())["status"] == "TERMS_BLOCKED"


def test_krx_is_fenced() -> None:
    fence = kr.KRX_RETAIL_OPTIONS_FLOW_FENCE
    assert fence["status"] == "TERMS_BLOCKED" and "prior permission of KRX" in fence["clause"]
    assert refusal("https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd")
    assert any("data.krx.co.kr" in r["ground"] for r in kr.REFUSED_SOURCES)


def test_expiry_matches_the_event_engine() -> None:
    def closed(d: date) -> bool:
        return d.weekday() >= 5 or d.isoformat() in kr.holidays(d.year)
    rule = [r for r in ASIA_EVENT_RULES if r.rule == "kr_kospi200_expiry"]
    rows = asia_schedule(date(2024, 1, 1), date(2026, 12, 31), {"kr_closed": closed}, rule)
    engine = [r["event_date"][:10] for r in rows]
    mine = [kr.kospi200_expiry(y, m)["date"].isoformat()
            for y in (2024, 2025, 2026) for m in range(1, 13)]
    assert engine == mine


def test_holiday_collision_rolls_back() -> None:
    # 2025-10-09 is the second Thursday and Hangeul Day; 3-8 October are closed too.
    e = kr.kospi200_expiry(2025, 10)
    assert e["nominal"] == date(2025, 10, 9) and e["date"] == date(2025, 10, 2) and e["rolled"]


@pytest.mark.parametrize("asof, phase", [
    (date(2026, 12, 10), "EXPIRY_DAY_QUAD"),
    (date(2026, 12, 7), "EXPIRY_WEEK_QUAD"),
    (date(2026, 11, 12), "EXPIRY_DAY"),
    (date(2026, 11, 13), "POST_EXPIRY"),
    (date(2026, 11, 18), "NEUTRAL"),
])
def test_usdkrw_phase(asof: date, phase: str) -> None:
    st = kr.usdkrw_expiry_state(asof)
    assert st["phase"] == phase and st["symbols"] == ("USDKRW",)


def test_untabulated_year_is_unmeasured_not_guessed() -> None:
    st = kr.usdkrw_expiry_state(date(2027, 1, 4))
    assert st["calendar"] == "UNTABULATED"
    assert st["kr_sessions_to_next"] == "UNMEASURED"


def test_report_is_usdkrw_only(no_network) -> None:
    doc = kr.kr_options_state_report(datetime(2026, 11, 18, tzinfo=UTC))
    assert doc["symbols"] == ("USDKRW",) and doc["fetched"] == 0
    assert doc["upcoming_expiries"][0]["date"] == "2026-12-10"
