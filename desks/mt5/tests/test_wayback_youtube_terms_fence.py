"""The Internet Archive and YouTube are refused for automated desk use (Governance,
wayback-youtube-ruling-2026-11-14): every fenced door refuses them and none opens a socket."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK / "side_channels"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import seed_miners as sm  # noqa: E402
from research.archaeology import snapshots as snap  # noqa: E402

from libs.research import public_strategy_hunter as psh  # noqa: E402
from research import acquire_datasets as AD  # noqa: E402
from research import source_fixer as sf  # noqa: E402


def _boom(*_a, **_k):
    raise AssertionError("a terms-refused host was requested")


@pytest.mark.parametrize("url", ["https://web.archive.org/web/*/kase.kz*",
                                 "https://archive.org/wayback/available?url=x",
                                 "https://www.youtube.com/@x", "https://youtu.be/abcdefghijk"])
def test_the_acquirer_refuses_archive_and_youtube_pack_roots(url: str) -> None:
    assert AD.terms_refusal(url)


def test_seed_miners_never_ask_the_archive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sm.requests, "get", _boom)
    with pytest.raises(PermissionError):
        sm.fetch("http://web.archive.org/cdx/search/cdx?url=forex-tsd.com*")
    for name in ("darwinex", "forextsd_cdx"):
        wall = sm.SOURCE_WALLS[name]
        assert wall["verdict"] == "TERMS_REFUSED" and "missed_growth" in wall["evidence"]
        lifted, note = sm._probe_wall(name, wall)       # the probe is the terms, not a request
        assert lifted is False and "terms" in note


def test_the_source_fixer_records_the_refusal_and_asks_nothing() -> None:
    assert sf._wayback("https://dead.example/x") is None
    assert sf.WAYBACK_TERMS.startswith("BLOCKED_ON_TERMS") and "missed_growth" in sf.WAYBACK_TERMS


def test_the_archaeology_table_forbids_the_archive() -> None:
    assert snap.BY_NAME["wayback"].machine_use_allowed == snap.FORBIDDEN
    assert not any("archive.org" in g.url for g in snap.ARCHIVE_LAYER)


@pytest.mark.parametrize("url", ["https://www.youtube.com/watch?v=abc",
                                 "https://www.youtube.com/feeds/videos.xml?channel_id=UCx",
                                 "https://r1.googlevideo.com/x", "https://web.archive.org/web/x"])
def test_the_strategy_hunter_never_contacts_youtube_or_the_archive(
        url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(psh.urllib.request, "urlopen", _boom)
    with pytest.raises(psh.TermsRefused):
        psh.fetch(url)
