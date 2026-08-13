"""2026-08-13, principal decision: YouTube (channel scan + search) is not attempted by
scripts/mine_research_queue.py by default any more -- assigned to a GPT-based hunter with
different network access than this box's datacenter-IP-blocked egress. @quantopian retired
(HTTP 404, the channel is gone, not merely blocked).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "mine_research_queue", _REPO / "scripts/mine_research_queue.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_quantopian_is_retired() -> None:
    mod = _load()
    assert "@quantopian" not in mod.YOUTUBE_CHANNELS


def test_youtube_and_search_excluded_by_default() -> None:
    mod = _load()
    only: set[str] = set()

    def _runs(src: str) -> bool:
        if not only:
            return src not in mod._YOUTUBE_SRCS
        return src in only

    assert _runs("youtube") is False
    assert _runs("search") is False
    assert _runs("cn") is True
    assert _runs("bilibili") is True
    assert _runs("academic") is True
    assert _runs("foreign") is True


def test_explicit_only_youtube_still_works() -> None:
    """A deliberate override must never be silently dropped."""
    mod = _load()
    only = {"youtube"}

    def _runs(src: str) -> bool:
        if not only:
            return src not in mod._YOUTUBE_SRCS
        return src in only

    assert _runs("youtube") is True
    assert _runs("search") is False   # only what was explicitly named runs
    assert _runs("cn") is False


def test_captions_block_names_the_new_policy() -> None:
    src = (_REPO / "scripts/mine_research_queue.py").read_text("utf-8")
    assert "GPT-based hunter" in src


def test_probe_cn_attempts_a_render_for_needs_browser_sources(monkeypatch) -> None:
    """joinquant/bigquant/ricequant are declared needs_browser -- probe_cn() must now call
    libs.data.render_fetch for each rather than leaving them untried."""
    mod = _load()
    monkeypatch.setattr(mod, "_get", lambda url, timeout=25: "x" * 100)
    calls: list[str] = []

    def _fake_render(url: str, *, timeout_s: float = 25.0):
        calls.append(url)
        return "<html>" + "y" * 30_000 + "</html>", ""

    monkeypatch.setattr("libs.data.render_fetch.render", _fake_render)
    monkeypatch.setattr("libs.data.render_fetch.render_available", lambda: (True, ""))
    rows = mod.probe_cn()
    browser_rows = [r for r in rows if r["declared"] == "needs_browser"]
    assert len(browser_rows) == 3
    assert len(calls) == 3
    for r in browser_rows:
        assert r["render"]["attempted"] is True
        assert r["render"]["looks_like_content"] is True


def test_probe_cn_reports_render_unavailable_honestly(monkeypatch) -> None:
    """This container's Chromium egress is network-blocked (render_fetch's own measurement) --
    probe_cn() must report that honestly, never crash, and never fabricate a render result."""
    mod = _load()
    monkeypatch.setattr(mod, "_get", lambda url, timeout=25: "x" * 100)
    monkeypatch.setattr("libs.data.render_fetch.render_available",
                        lambda: (False, "playwright not importable"))
    rows = mod.probe_cn()
    browser_rows = [r for r in rows if r["declared"] == "needs_browser"]
    assert len(browser_rows) == 3
    for r in browser_rows:
        assert r["render"]["attempted"] is False
        assert "playwright not importable" in r["render"]["why"]
