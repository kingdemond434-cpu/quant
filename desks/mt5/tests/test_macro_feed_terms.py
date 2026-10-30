"""The macro collector's RSS feeds: ONE policy table (`terms_fence.SOURCE_POLICY`), nothing LIVE
fetched stops (audit PR162_357 MF1).

#262 added a second, fail-closed table (`data/macro_feed_terms.json`) that never requested 11
public feeds. Those rows now live in SOURCE_POLICY: restricted-reuse feeds are IDEAS_ONLY (still
fetched, read for events and ideas), unread ones PUBLIC_PAGE. Only a METHOD_BLOCKED / NEEDS_KEY row
stops a fetch. The JSON keeps the quoted clearances as evidence. The network is a recorder here.
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
    # THE ONE FETCH DOOR (libs/data/terms_fence.guarded_urlopen) builds its own opener, so the
    # recorder stands in for it too; the fence's own pre-request check still runs first.
    from libs.data import terms_fence as tf

    def door(req: object, *a: object, **k: object) -> _Resp:
        url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
        tf.check_request(url)
        return urlopen(req)

    monkeypatch.setattr(tf, "guarded_urlopen", door)
    return asked


def _feeds() -> dict[str, str]:
    return {sid: url for sid, url, _ in sources._OFFICIAL_FEEDS}


RESTRICTED = {"BOJ", "BOE", "SNB", "IMF", "UN_NEWS", "SP_INDICES"}
UNREAD = {"OPEC", "USTR", "TREASURY_OFAC", "US_TREASURY", "IMO_SHIPPING"}


def test_every_feed_reads_its_status_from_the_one_table() -> None:
    from libs.data import terms_fence as tf
    feeds = _feeds()
    for sid, url in feeds.items():
        p = tf.feed_policy(sid, url)
        row = tf.SOURCE_POLICY.get(f"macro_feed:{sid}")
        assert p["status"] == (row["status"] if row else tf.PUBLIC_PAGE), sid
        if row:
            assert row["feed_url"] == url and row["why"]
    assert {sid for sid in feeds if tf.feed_policy(sid, feeds[sid])["status"] == tf.IDEAS_ONLY} \
        == RESTRICTED
    for sid in RESTRICTED:
        assert tf.SOURCE_POLICY[f"macro_feed:{sid}"]["terms"]["clauses"]["reuse"].strip()
    for sid in UNREAD:
        assert tf.SOURCE_POLICY[f"macro_feed:{sid}"]["status"] == tf.PUBLIC_PAGE


def test_the_evidence_record_quotes_only_cleared_feeds_and_gates_nothing() -> None:
    doc = json.loads(sources.TERMS_FILE.read_text("utf-8"))
    for sid, row in doc.items():
        if sid.startswith("_"):
            continue
        assert row["status"] == sources.CLEARED and row["terms_quote"].strip(), sid
        assert row["feed_url"] == _feeds()[sid]
    assert "gates nothing" in doc["_about"]


def test_every_feed_live_fetched_before_is_still_requested(network: list[str]) -> None:
    srcs = sources.default_sources()
    for s in srcs:
        s.fetch()
    assert set(network) == {s.url for s in srcs}, "no macro feed is held"
    cov = sources.coverage(srcs)
    assert cov["terms_held"] == []
    ideas = {s.source_id for s in srcs if s.terms_status == "IDEAS_ONLY"}
    assert ideas == RESTRICTED


def test_an_absent_evidence_record_stops_nothing(network: list[str], tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sources, "TERMS_FILE", tmp_path / "missing.json")
    srcs = sources.default_sources()
    for s in srcs:
        s.fetch()
    assert set(network) == {s.url for s in srcs}


def test_only_a_holding_row_stops_a_feed(network: list[str],
                                         monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.data import terms_fence as tf
    sid, url = "BOJ", _feeds()["BOJ"]
    monkeypatch.setitem(tf.SOURCE_POLICY, "macro_feed:BOJ",
                        {**tf.SOURCE_POLICY["macro_feed:BOJ"], "status": tf.METHOD_BLOCKED,
                         "reason": "login"})
    src = next(s for s in sources.default_sources() if s.source_id == sid)
    assert src.held and src.fetch() == [] and network == []
    assert {r["id"] for r in sources.coverage([src])["terms_held"]} == {sid}
    assert url


def test_a_hand_built_source_reads_its_policy_and_an_unlisted_feed_is_public(
        network: list[str]) -> None:
    src = sources.RssSource(source_id="ANY", url="https://example.invalid/rss")
    assert src.terms_status == "PUBLIC_PAGE" and not src.held
    src.fetch()
    assert network == ["https://example.invalid/rss"]
