"""A model-named (scouted) source is a suggestion, not a declared source (audit of 538cb964,
SF9): unconfirmed terms stay closed, the port is pinned, robots.txt is re-read each pass."""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = str(Path(__file__).resolve().parents[1])
if _DESK not in sys.path:
    sys.path.insert(0, _DESK)

from research import asia_collector as ac  # noqa: E402


def _row(sid: str, url: str, terms: str = "confirmed") -> dict:
    return {"id": sid, "url": url, "terms": terms, "probe": "REACHABLE"}


def test_only_confirmed_public_robots_allowed_rows_are_collected() -> None:
    rows = [_row("ok", "https://stat.example.go.jp/a.csv"),
            _row("unconfirmed", "https://stat.example.go.jp/b.csv", terms="to_confirm"),
            _row("port", "https://stat.example.go.jp:8443/c.csv"),
            _row("private", "https://intranet.example/d.csv"),
            _row("robots", "https://stat.example.go.jp/private/e.csv"),
            _row("norobots", "https://quiet.example.go.jp/f.csv")]

    def public(url: str) -> str:
        return "private address" if "intranet" in url else ""

    def robots(url: str) -> tuple[bool, str]:
        if "quiet" in url:
            return True, "robots.txt unreadable (URLError); treated as allowing"
        return ("/private/" not in url), "robots.txt consulted"

    ok, held = ac.scouted_admissible(rows, public, robots)
    assert [r["id"] for r in ok] == ["ok"]
    assert set(held) == {"unconfirmed", "port", "private", "robots", "norobots"}
    assert "unconfirmed terms stay closed" in held["unconfirmed"]
