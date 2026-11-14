"""The GC/CL curve fence. Governance 2026-11-11 00:41Z: the curves never mint trading cells. Audit
HOLD on #898, 2026-11-14: Yahoo is REFUSED on terms, so the collector opens no socket at all.

The mint fence reads futures_state_sources.json and fails closed when a class is missing or the
file is unreadable; the collector writes a BLOCKED_ON_TERMS record and leaves held panels alone."""
from __future__ import annotations

# ruff: noqa: E402 -- tests add the desk roots before importing standalone research modules.
import json
import sys
import socket
import urllib.request
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for path in (DESK, DESK / "research", DESK.parent.parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import curve_strategy_screen as screen
import fetch_futures_curves as fetcher


def _registry(tmp_path: Path, **terms: str) -> Path:
    rows = [{"id": sid, "terms": t} for sid, t in terms.items()]
    path = tmp_path / "futures_state_sources.json"
    path.write_text(json.dumps({"sources": rows}), encoding="utf-8")
    return path


def test_the_live_registry_refuses_yahoo_and_mints_nothing() -> None:
    permit = screen.mint_permission()
    assert permit["mint"] is False
    assert permit["classes"] == {"yahoo_futures": "REFUSED", "cme_settlements": "HELD"}


@pytest.mark.parametrize("terms", [
    {"yahoo_futures": "IDEAS_ONLY", "cme_settlements": "OPEN"},
    {"yahoo_futures": "OPEN", "cme_settlements": "HELD"},
    {"yahoo_futures": "OPEN"},                       # a missing row is not a permission
    {},
])
def test_any_class_but_open_refuses_to_mint(tmp_path: Path, terms: dict) -> None:
    assert screen.mint_permission(_registry(tmp_path, **terms))["mint"] is False


def test_an_unreadable_registry_fails_closed(tmp_path: Path) -> None:
    bad = tmp_path / "futures_state_sources.json"
    bad.write_text("{not json", encoding="utf-8")
    permit = screen.mint_permission(bad)
    assert permit["mint"] is False and set(permit["classes"].values()) == {"UNREADABLE"}
    assert screen.mint_permission(tmp_path / "absent.json")["mint"] is False


def test_only_every_source_open_mints(tmp_path: Path) -> None:
    reg = _registry(tmp_path, yahoo_futures="OPEN", cme_settlements="OPEN")
    assert screen.mint_permission(reg)["mint"] is True


def test_the_collector_carries_the_refused_class() -> None:
    assert fetcher.source_class() == "REFUSED"
    doc = json.loads(fetcher.REGISTRY.read_text(encoding="utf-8"))
    row = next(r for r in doc["sources"] if r["id"] == "yahoo_futures")
    assert row["terms_evidence"]["recorded_in"].startswith("Audit HOLD on PR #898")


def test_the_fetch_is_removed_not_switched_off() -> None:
    src = Path(fetcher.__file__).read_text(encoding="utf-8")
    assert not hasattr(fetcher, "fetch_contract")
    assert "urllib" not in src and "query1.finance.yahoo.com/v8" not in src


def test_main_opens_no_socket_and_keeps_held_panels(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    def no_network(*_a, **_k):
        raise AssertionError("a socket was opened")
    monkeypatch.setattr(socket, "socket", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    out = tmp_path / "futures_curves"
    out.mkdir()
    held = out / "GC_curve.parquet"
    import pandas as pd
    pd.DataFrame({"date": pd.to_datetime(["2026-11-01"], utc=True), "close": [1.0],
                  "source_class": ["IDEAS_ONLY"]}).to_parquet(held, index=False)
    before = held.read_bytes()
    report = tmp_path / "futures_curve_coverage.json"
    monkeypatch.setattr(fetcher, "OUT", out)
    monkeypatch.setattr(fetcher, "REPORT", report)
    assert fetcher.main([]) == 0
    doc = json.loads(report.read_text(encoding="utf-8"))
    assert doc["status"] == "BLOCKED_ON_TERMS" and doc["requests_made"] == 0
    assert doc["missed_growth"]["verdict"] == "a gap, not a zero"
    assert doc["held_panels"] == [{"file": "GC_curve.parquet", "rows": 1,
                                   "last_date": "2026-11-01 00:00:00+00:00",
                                   "source_class": "IDEAS_ONLY"}]
    assert held.read_bytes() == before


def test_the_shanghai_exchanges_are_recorded_refused() -> None:
    doc = json.loads(screen.REGISTRY.read_text(encoding="utf-8"))
    row = next(r for r in doc["sources"] if r["id"] == "cn_exchanges")
    assert row["terms"] == "REFUSED"
    assert row["terms_evidence"]["terms_url"] == "https://www.shfe.com.cn/disclaimer/"


def test_the_sge_premium_is_stamped_ideas_only() -> None:
    import fetch_sge_premium as sge
    assert (sge.TERMS, sge.USE) == ("TO_CONFIRM", "IDEAS_ONLY")
