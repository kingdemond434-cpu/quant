"""The free stack's one honest User-Agent and its robots gate (hard rule, 2026-11-11).

Every fetcher goes out under `fs.UA` -- named, no browser string, not replaceable by a fetcher's
own headers -- and passes the robots gate first. A host that refuses the honest agent becomes a
REFUSED_BY_ROBOTS verdict on the yield artifact; nothing retries it under another identity.
"""
from __future__ import annotations

import sys
import types
from datetime import UTC, datetime
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import free_stack as fs  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _gate(status: int, text: str = "") -> fs.RobotsGate:
    return fs.RobotsGate(get_text=lambda url: (status, text))


def test_the_ua_names_the_organ_and_impersonates_no_browser() -> None:
    assert fs.UA.startswith("quant-research/1.0") and "free_stack_hunter" in fs.UA
    for word in ("Mozilla", "Chrome", "Safari", "AppleWebKit", "Gecko"):
        assert word not in fs.UA


def test_gate_takes_the_stricter_rule() -> None:
    assert _gate(404).refusal("https://a.example/x") is None
    assert _gate(403).refusal("https://a.example/x")
    for st in (0, 429, 500):
        assert "unreadable" in str(_gate(st).refusal("https://a.example/x"))
    g = _gate(200, "User-agent: quant-research\nDisallow: /api\n")
    assert g.refusal("https://a.example/api/v1") and g.refusal("https://a.example/ok") is None
    assert g.consulted == {"a.example": "robots.txt read"}


def test_a_refused_url_is_never_requested(monkeypatch) -> None:
    monkeypatch.setattr(fs, "GATE", _gate(200, "User-agent: *\nDisallow: /\n"))

    def boom(*a, **k):
        raise AssertionError("urlopen must not be reached for a refused URL")
    monkeypatch.setattr(fs.urllib.request, "urlopen", boom)
    with pytest.raises(fs.FetchError) as exc:
        fs.http_fetch("https://a.example/data.json")
    assert exc.value.reason == fs.ROBOTS_REFUSED


def test_no_fetcher_header_can_replace_the_ua(monkeypatch) -> None:
    monkeypatch.setattr(fs, "GATE", _gate(404))
    seen: dict = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            return b"ok"

    def fake(req, timeout=None):
        seen.update({k.lower(): v for k, v in req.header_items()})
        return _Resp()
    monkeypatch.setattr(fs.urllib.request, "urlopen", fake)
    assert fs.http_fetch("https://a.example/x",
                         {"User-Agent": "Mozilla/5.0 Chrome", "Referer": "r"}) == b"ok"
    assert seen["user-agent"] == fs.UA and seen["referer"] == "r"


def test_the_akshare_package_is_never_used(monkeypatch) -> None:
    def boom(*a, **k):
        raise AssertionError("the akshare package sends browser UAs; it must not be called")
    monkeypatch.setitem(sys.modules, "akshare",
                        types.SimpleNamespace(stock_zh_index_daily=boom))
    called: list[str] = []
    monkeypatch.setattr(fs, "fetch_akshare_direct",
                        lambda fetch, row, cursor, now: called.append("direct") or fs.Harvest("x"))
    h = fs.fetch_akshare_package(lambda *a: b"", {"id": "akshare"}, {}, NOW)
    assert called == ["direct"] and any("impersonates" in n for n in h.notes)


def test_a_refusing_host_is_a_fail_closed_verdict_on_the_artifact(tmp_path) -> None:
    import json

    from free_stack_hunter import Store, run
    doc = json.loads((_DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({**doc, "sources": [r for r in doc["sources"]
                                                     if r["id"] == "app_rank_apple"]}), "utf-8")
    st = Store(tmp_path)
    (tmp_path / "data" / "universe").mkdir(parents=True)
    (tmp_path / "data" / "universe" / "universe.json").write_text("{}", "utf-8")

    def refusing(url, headers=None, body=None):
        raise fs.FetchError(fs.ROBOTS_REFUSED, f"robots.txt disallows this path: {url}")
    rep = run(budget_s=60, fetch=refusing, store=st, roster=roster,
              now=NOW, live=False)
    assert rep["per_source"]["app_rank_apple"]["status"] == "REFUSED_BY_ROBOTS"
    assert rep["refused_by_robots"] == ["app_rank_apple"]
    assert rep["user_agent"] == fs.UA
