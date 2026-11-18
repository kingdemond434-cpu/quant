"""A robots "no" STOPS civilization's automated page fetch (Auditor ruling 2026-11-18, #1335).

`run(fetch=True)` reads each reachable platform's robots.txt first. Disallowed, HTML (UNKNOWN),
403 and 429 each leave every page unrequested and record the reason in `robots_refused`; a real
allow still fetches. `moat_collectors.fetch_text` is a fake recorder; nothing touches the network.
"""
from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research"), str(_DESK / "side_channels")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import moat_collectors as mc  # type: ignore[import-not-found]  # noqa: E402
from archaeology import civilization as civ  # type: ignore[import-not-found]  # noqa: E402
from archaeology import snapshots as snap  # noqa: E402

from libs.moat import registry as R  # noqa: E402

PAGE = "<html><body><p>a page</p></body></html>"
ALLOW = "User-agent: *\nDisallow: /private\n"


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    monkeypatch.setattr(mc, "MOAT", tmp_path / "moat")
    monkeypatch.setattr(mc, "SLEEP_S", 0.0)
    monkeypatch.setattr(mc, "ROBOTS_BARRED", ())
    monkeypatch.setattr(snap, "POPULATION", tmp_path / "archaeology" / "population.jsonl")
    monkeypatch.setattr(civ, "REPORT", tmp_path / "reports" / "TRADING_ARCHAEOLOGY.json")
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    state: dict[str, Any] = {"robots": (ALLOW, 200, ""), "calls": []}

    def _fetch(url: str, lang: str = "") -> tuple[str, int, str]:
        state["calls"].append(url)
        if url.endswith("/robots.txt"):
            robots: tuple[str, int, str] = state["robots"]
            return robots
        return PAGE, 200, ""

    monkeypatch.setattr(mc, "fetch_text", _fetch)
    c = R.connect()
    state["conn"] = c
    yield state
    c.close()
    R.set_path(None)


def _pages(calls: list[str]) -> list[str]:
    return [u for u in calls if not u.endswith("/robots.txt")]


@pytest.mark.parametrize("robots", [
    ("User-agent: *\nDisallow: /\n", 200, ""),                       # disallowed outright
    ("<!DOCTYPE html><html><body>challenge</body></html>", 200, ""),  # HTML -> UNKNOWN
    ("", 403, "HTTPError 403"),                                       # hard stop
    ("", 429, "HTTPError 429"),                                       # hard stop
    ("", 0, "URLError: offline"),                                     # unread
], ids=["disallowed", "html", "403", "429", "unreachable"])
def test_a_robots_no_sends_no_page_request(desk: dict[str, Any],
                                           robots: tuple[str, int, str]) -> None:
    desk["robots"] = robots
    got = civ.run(budget_s=60.0, fetch=True, conn=desk["conn"], at="2026-11-18")
    assert desk["calls"], "the pass must at least read robots.txt"
    assert _pages(desk["calls"]) == [], "a robots 'no' must stop every page fetch"
    reachable = {p.name for p in snap.PLATFORMS if snap.may_fetch(p)[0]}
    assert {r["platform"] for r in got["robots_refused"]} == reachable
    assert all(r["why"].startswith("refused by robots") for r in got["robots_refused"])


def test_a_path_level_disallow_stops_that_page(desk: dict[str, Any]) -> None:
    desk["robots"] = ("User-agent: *\nDisallow: /en/signals\n", 200, "")
    assert civ._robots_stop("https://www.mql5.com/en/signals").startswith("refused by robots")
    assert civ._robots_stop("https://www.mql5.com/en/code") == ""


def test_a_real_allow_still_fetches(desk: dict[str, Any]) -> None:
    got = civ.run(budget_s=60.0, fetch=True, conn=desk["conn"], at="2026-11-18")
    assert got["robots_refused"] == []
    roots = {p.root for p in snap.PLATFORMS if snap.may_fetch(p)[0]}
    assert roots and roots <= set(_pages(desk["calls"]))
