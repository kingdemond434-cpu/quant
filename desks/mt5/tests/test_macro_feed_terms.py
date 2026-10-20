"""The macro collector's RSS feeds are fetched only on a quoted terms clearance. Fail closed.

`data/macro_feed_terms.json` (PR #262) holds one terms row per `_OFFICIAL_FEEDS` id. The network
is replaced here by a recorder: any request for a feed that is not CLEARED is a failure, and every
held feed must be reported HOLD by name.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from macro import sources  # noqa: E402

_RSS = (b"<?xml version='1.0'?><rss><channel><item><title>Policy statement</title>"
        b"<link>https://example.invalid/a</link></item></channel></rss>")


class _Resp:
    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *a: object) -> None:
        return None

    def read(self) -> bytes:
        return _RSS


@pytest.fixture
def network(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every URL any code path asks the network for. Nothing leaves the process."""
    asked: list[str] = []

    def urlopen(req: object, *a: object, **k: object) -> _Resp:
        asked.append(req.full_url if isinstance(req, urllib.request.Request) else str(req))
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return asked


def _feeds() -> dict[str, str]:
    return {sid: url for sid, url, _ in sources._OFFICIAL_FEEDS}


def test_every_feed_has_a_terms_row_and_only_quoted_rows_clear() -> None:
    doc = json.loads(sources.TERMS_FILE.read_text("utf-8"))
    for sid, url in _feeds().items():
        row = doc[sid]
        assert row["status"] in (sources.CLEARED, sources.HOLD)
        assert {"status", "terms_url", "terms_quote", "by", "checked_at"} <= set(row)
        assert row["feed_url"] == url
        if row["status"] == sources.CLEARED:
            assert row["terms_url"].startswith("https://") and row["terms_quote"].strip()


def test_held_feeds_are_never_requested_and_are_reported_hold(network: list[str]) -> None:
    srcs = sources.default_sources()
    held = {s.url for s in srcs if s.terms_status != sources.CLEARED}
    cleared = {s.url for s in srcs if s.terms_status == sources.CLEARED}
    assert held and cleared, "the record holds some feeds and clears others"
    for s in srcs:
        s.fetch()
    assert not held & set(network), f"held feeds were requested: {sorted(held & set(network))}"
    assert set(network) == cleared
    cov = sources.coverage(srcs)
    assert {r["url"] for r in cov["terms_held"]} == held
    assert {r["id"] for r in cov["sources"] if r["terms"] == sources.HOLD} == {
        r["id"] for r in cov["terms_held"]}


def test_an_absent_record_holds_every_feed(network: list[str], tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sources, "TERMS_FILE", tmp_path / "missing.json")
    srcs = sources.default_sources()
    for s in srcs:
        assert s.fetch() == []
    assert network == []
    assert len(sources.coverage(srcs)["terms_held"]) == len(srcs)
    assert sources.coverage(srcs)["domains_covered"] == []


@pytest.mark.parametrize("row", [
    {"status": "CLEARED", "terms_url": "https://x.invalid/terms", "terms_quote": ""},
    {"status": "CLEARED", "terms_url": "", "terms_quote": "may be copied"},
    {"status": "CLEARED", "terms_url": "https://x.invalid/terms", "terms_quote": "may be copied",
     "feed_url": "https://elsewhere.invalid/rss"},
    {"status": "HOLD", "terms_url": "https://x.invalid/terms", "terms_quote": "may be copied"},
])
def test_an_unquoted_or_misdirected_clearance_admits_nothing(
        row: dict[str, str], network: list[str], tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    sid, url = next(iter(_feeds().items()))
    row = {"feed_url": url, **row}
    path = tmp_path / "terms.json"
    path.write_text(json.dumps({sid: row}), "utf-8")
    monkeypatch.setattr(sources, "TERMS_FILE", path)
    src = next(s for s in sources.default_sources() if s.source_id == sid)
    assert src.terms_status == sources.HOLD
    assert src.fetch() == []
    assert network == []


def test_a_hand_built_source_without_a_verdict_is_held(network: list[str]) -> None:
    src = sources.RssSource(source_id="ANY", url="https://example.invalid/rss")
    assert src.fetch() == [] and network == []
