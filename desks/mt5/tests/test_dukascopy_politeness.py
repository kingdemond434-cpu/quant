"""The Dukascopy backfill asks the host's rules first, names itself honestly and stops when asked."""

from __future__ import annotations

import json
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

import pytest

from research import dukascopy_backfill as db
from research import fetch_dukascopy as fd

NOW = datetime(2026, 11, 11, 12, tzinfo=UTC)


def _gate(code: int, text: str = "") -> dict:
    return fd.robots_gate(fetch=lambda url: (code, text))


def test_robots_rules_decide() -> None:
    assert _gate(200, "User-agent: *\nAllow: /\n")["verdict"] == "ALLOWED"
    assert _gate(200, "User-agent: *\nDisallow: /datafeed/\n")["verdict"] == "DISALLOWED"
    # no rules published is the convention's permission; an unreadable host is not
    assert _gate(404)["verdict"] == "ALLOWED"
    assert _gate(503)["verdict"] == "UNREACHABLE"
    assert _gate(403)["verdict"] == "UNREACHABLE"


def test_the_client_names_itself_honestly() -> None:
    assert fd.USER_AGENT.startswith("quant-desk-research/")
    assert "Mozilla" not in fd.USER_AGENT and "@" not in fd.USER_AGENT
    assert fd.MIN_INTERVAL_S >= 0.25


@pytest.mark.parametrize("verdict", ["DISALLOWED", "UNREACHABLE"])
def test_nothing_is_fetched_unless_the_host_allows(tmp_path: Path, monkeypatch, verdict) -> None:
    calls: list = []
    monkeypatch.setattr(db, "fetch_day", lambda *a, **k: calls.append(a) or {})
    report = db.run(root=tmp_path / "t", state_path=tmp_path / "s.json",
                    report_path=tmp_path / "r.json", symbol_days=4, now=NOW,
                    robots={"verdict": verdict, "why": "test"})
    assert calls == [] and report["attempted_symbol_days"] == 0
    on_disk = json.loads((tmp_path / "r.json").read_text())
    assert on_disk["client"]["robots"]["verdict"] == verdict


def test_a_429_ends_the_pass_and_keeps_the_cursor(tmp_path: Path, monkeypatch) -> None:
    def slow_down(*a, **k):
        raise fd.FeedSaysStop("http 429")
    monkeypatch.setattr(db, "fetch_day", slow_down)
    state = tmp_path / "s.json"
    report = db.run(root=tmp_path / "t", state_path=state, report_path=tmp_path / "r.json",
                    symbol_days=4, now=NOW, robots={"verdict": "ALLOWED"})
    assert report["attempted_symbol_days"] == 0
    assert "429" in report["client"]["stopped_by_vendor"]
    cursors = json.loads(state.read_text())["next_date"]
    assert set(cursors.values()) == {"2026-11-10"}   # nothing advanced


def test_fetch_hour_raises_on_429(monkeypatch) -> None:
    def refuse(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many", None, None)  # type: ignore[arg-type]
    monkeypatch.setattr(fd.urllib.request, "urlopen", refuse)
    monkeypatch.setattr(fd, "MIN_INTERVAL_S", 0.0)
    with pytest.raises(fd.FeedSaysStop):
        fd.fetch_hour("EURUSD", datetime(2026, 11, 10, 10, tzinfo=UTC))
