"""asia_collector obeys robots.txt and fails closed (Governance with the Auditor, 2026-11-13)."""
from __future__ import annotations

import io
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import asia_collector as AC  # noqa: E402

URL = "https://stats.example.org/data/series.csv"


class _Resp(io.BytesIO):
    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *a: object) -> None:
        return None


def _robots(monkeypatch: pytest.MonkeyPatch, answer: Any) -> list[str]:
    calls: list[str] = []

    def opener(req: Any, *a: Any, **k: Any) -> Any:
        calls.append(req.full_url)
        if not req.full_url.endswith("/robots.txt"):
            raise AssertionError("the page was fetched past a robots refusal")
        if isinstance(answer, int):
            raise urllib.error.HTTPError(req.full_url, answer, "x", {}, io.BytesIO(b""))  # type: ignore[arg-type]
        if isinstance(answer, Exception):
            raise answer
        return _Resp(answer)

    monkeypatch.setattr(urllib.request, "urlopen", opener)
    return calls


@pytest.mark.parametrize("answer", [500, 503, 401, 403, 429, 451, TimeoutError("t"),
                                    b"<!DOCTYPE html><html>x</html>",
                                    b"User-agent: *\nDisallow: /data/\n"])
def test_a_disallow_or_an_unreadable_robots_is_never_fetched(
        monkeypatch: pytest.MonkeyPatch, answer: Any) -> None:
    calls = _robots(monkeypatch, answer)
    rec = AC.collect_one({"id": "x", "url": URL, "expect": "csv"})
    assert rec["status"] == AC.ROBOTS_STATUS and rec["robots_disallows"] is True
    assert "UNMEASURED" in rec["missed_growth"]
    assert calls == ["https://stats.example.org/robots.txt"]


@pytest.mark.parametrize("answer", [404, 410, b"User-agent: *\nDisallow: /private/\n", b""])
def test_no_robots_file_or_an_allow_lets_the_fetch_through(
        monkeypatch: pytest.MonkeyPatch, answer: Any) -> None:
    _robots(monkeypatch, answer)
    allowed, why = AC._robots_allows(URL)
    assert allowed, why
