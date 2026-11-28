"""Build-check row 72, Cboe put/call extremes x VIX regime: fenced on Cboe's terms (read
2026-11-18, s2 personal non-commercial use only). Nothing is fetched, no lake series and no cell
exist; the row is carried in the hourly futures_state gap list by name, never as a zero."""
from __future__ import annotations

# ruff: noqa: E402 -- tests add the desk roots before importing standalone research modules.
import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for path in (DESK, DESK / "research", DESK.parent.parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import futures_state
from libs.data.refused_hosts import refusal

REGISTRY = DESK / "research" / "futures_state_sources.json"


def _row() -> dict:
    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return next(r for r in doc["sources"] if r["id"] == "cboe_put_call_ratios")


def test_put_call_row_is_terms_blocked_with_its_reading() -> None:
    row = _row()
    assert row["terms"] == "TERMS_BLOCKED"
    assert row["adapter"] == "none"
    assert row["terms_url"] == "https://www.cboe.com/terms"
    assert "personal non-commercial use" in row["terms_clause"]
    assert row["terms_read"] == "2026-11-18"
    assert row["targets"] == ["US500", "NAS100"]


def test_put_call_url_is_refused_before_any_socket() -> None:
    assert refusal(_row()["url"]) is not None


def test_put_call_row_is_a_named_gap_never_fetched() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    out = futures_state.gaps(registry, {}, [])
    held = {h["id"]: h["terms"] for h in out["held_or_unconfirmed_venues"]}
    assert held["cboe_put_call_ratios"] == "TERMS_BLOCKED"
