"""Governance 2026-11-11 00:41Z: the Yahoo GC/CL curves propose ideas only, never trading cells.

The fence reads futures_state_sources.json and fails closed when a class is missing or the file is
unreadable; the collector's UA is an honest tool name and a refusal stops the whole pass."""
from __future__ import annotations

# ruff: noqa: E402 -- tests add the desk roots before importing standalone research modules.
import json
import sys
import urllib.error
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


def test_the_live_registry_keeps_the_curves_ideas_only() -> None:
    permit = screen.mint_permission()
    assert permit["mint"] is False
    assert permit["classes"] == {"yahoo_futures": "IDEAS_ONLY", "cme_settlements": "HELD"}


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


def test_the_collector_names_itself_honestly_and_carries_its_class() -> None:
    assert "Mozilla" not in fetcher.UA and fetcher.UA.startswith("quant-desk-")
    assert fetcher.source_class() == "IDEAS_ONLY"


def test_a_refusal_stops_the_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_a, **_k):
        raise urllib.error.HTTPError("u", 403, "Forbidden", None, None)  # type: ignore[arg-type]
    monkeypatch.setattr(fetcher.urllib.request, "urlopen", refuse)
    with pytest.raises(fetcher.HardStop):
        fetcher.fetch_contract("GCZ26.CMX")


def test_the_shanghai_exchanges_are_recorded_refused() -> None:
    doc = json.loads(screen.REGISTRY.read_text(encoding="utf-8"))
    row = next(r for r in doc["sources"] if r["id"] == "cn_exchanges")
    assert row["terms"] == "REFUSED"
    assert row["terms_evidence"]["terms_url"] == "https://www.shfe.com.cn/disclaimer/"


def test_the_sge_premium_is_stamped_ideas_only() -> None:
    import fetch_sge_premium as sge
    assert (sge.TERMS, sge.USE) == ("TO_CONFIRM", "IDEAS_ONLY")
