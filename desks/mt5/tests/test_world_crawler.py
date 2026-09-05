"""The world crawler: it must grow its own ground, in every language, and never invent a family.

The forty miners set the desk's coverage to the ceiling of human attention -- a ground nobody
thought of is one the desk can never reach, and its absence is indistinguishable from emptiness
(L1.28a). These tests fence the three properties that make this different: it discovers sources
recursively, it does not privilege English, and it emits LEADS rather than guessed strategies.
"""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "side_channels")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import world_crawler as wc  # noqa: E402
import world_frontier as wf  # noqa: E402

_PAGE = b"""<html lang="zh-CN"><head><title>EURUSD \xe7\xaa\x81\xe7\xa0\xb4\xe7\xad\x96\xe7\x95\xa5</title></head>
<body><p>EURUSD H4 breakout strategy, also XAUUSD</p>
<a href="/zh/code/mt5">\xe4\xba\xa4\xe6\x98\x93\xe7\xad\x96\xe7\x95\xa5</a>
<a href="/login">login</a>
<script>var x = "GBPUSD momentum";</script>
</body></html>"""  # noqa: E501


# --------------------------------------------------------------------------- language neutrality

def test_trading_vocabulary_is_recognised_in_many_languages() -> None:
    """Filtering to English deletes most of the world's retail quant writing, which is exactly
    the ground the principal asked to cover."""
    for url, anchor in (
        ("https://x.test/strategy", "backtest"),
        ("https://x.test/a", "交易策略"),
        ("https://x.test/b", "システムトレード 手法"),
        ("https://x.test/c", "백테스트"),
        ("https://x.test/d", "стратегия форекс"),
        ("https://x.test/e", "estrategia de divisas"),
        ("https://x.test/f", "استراتيجية تداول"),
    ):
        assert wf.worth_following(url, anchor), f"{anchor} was not recognised"


def test_obvious_non_ground_is_skipped() -> None:
    assert not wf.worth_following("https://x.test/login", "login")
    assert not wf.worth_following("javascript:void(0)", "trading")
    assert not wf.worth_following("mailto:a@b.c", "strategy")


def test_a_non_ascii_url_is_fetchable() -> None:
    """MEASURED on the first live crawl: a Japanese hub died with UnicodeEncodeError and was
    charged to that source as a failure, indistinguishable from a dead host."""
    out = wc._ascii_url("https://note.com/hashtag/システムトレード")
    out.encode("ascii")
    assert out.startswith("https://note.com/hashtag/%")


def test_an_ascii_url_is_left_exactly_alone() -> None:
    url = "https://a.test/path?x=1&y=2#frag"
    assert wc._ascii_url(url) == url


# ------------------------------------------------------------------------------------ extraction

def test_a_page_yields_symbols_timeframes_and_mechanisms() -> None:
    page = wc.read_page(_PAGE, "https://mql5.test/zh/code")
    assert "EURUSD" in page["symbols"] and "XAUUSD" in page["symbols"]
    assert "H4" in page["timeframes"]
    assert "breakout" in page["patterns"]
    assert page["lang"] == "zh-CN"


def test_script_contents_are_not_read_as_claims() -> None:
    """A symbol inside a <script> is code, not an assertion the page makes."""
    page = wc.read_page(_PAGE, "https://mql5.test/zh/code")
    assert "GBPUSD" not in page["symbols"]


def test_links_are_absolutised_so_the_frontier_can_use_them() -> None:
    page = wc.read_page(_PAGE, "https://mql5.test/zh/code")
    assert any(u == "https://mql5.test/zh/code/mt5" for u, _a in page["links"])


def test_the_crawler_never_emits_a_family_or_params() -> None:
    """THE COMPILER'S OWN LAW. A family guessed from a buzzword is the failure
    miner_candidate_compiler exists to prevent; this crawler reads prose and cannot know that a
    page states a registered family's exact rule."""
    row = wc.to_discovery("https://x.test/a", wc.read_page(_PAGE, "https://x.test/a"), "deadbeef")
    assert row is not None
    assert "family" not in row and "params" not in row


def test_a_page_claiming_nothing_produces_no_row() -> None:
    empty = wc.read_page(b"<html><body><p>hello world</p></body></html>", "https://x.test/")
    assert wc.to_discovery("https://x.test/", empty, "abc") is None


def test_every_row_carries_provenance_back_to_the_vaulted_bytes() -> None:
    """A candidate must be traceable to the exact bytes that proposed it, not to a live URL the
    source can edit afterwards."""
    row = wc.to_discovery("https://x.test/a", wc.read_page(_PAGE, "https://x.test/a"), "deadbeef")
    assert row is not None
    assert row["vault_sha"] == "deadbeef"
    assert row["url"] == "https://x.test/a"
    assert set(row) >= {"source", "title", "url", "published", "symbols", "timeframes",
                        "patterns", "confidence"}, "the miner-discovery contract must hold"


def test_confidence_counts_what_the_page_actually_asserted() -> None:
    """Not a feeling: a page naming a symbol, a timeframe and a mechanism is worth more than one
    naming a symbol."""
    rich = wc.to_discovery("https://x.test/a", wc.read_page(_PAGE, "https://x.test/a"), "h")
    thin = wc.read_page(b"<html><body>breakout</body></html>", "https://x.test/b")
    lean = wc.to_discovery("https://x.test/b", thin, "h")
    assert rich is not None and lean is not None
    assert rich["confidence"] > lean["confidence"]


# --------------------------------------------------------------------------------- ROI scheduling

def _src(url: str, **kw: object) -> wf.Source:
    return wf.Source(url=url, **kw)  # type: ignore[arg-type]


def test_a_lucky_first_fetch_does_not_capture_the_budget() -> None:
    """Shrinkage toward the host and then the global mean, exactly as the allocator shrinks a
    sleeve. Otherwise every hour is spent re-fetching whichever page got lucky once."""
    lucky = _src("https://a.test/1", host="a.test", fetches=1, candidates=1)
    proven = _src("https://b.test/1", host="b.test", fetches=200, candidates=60)
    sources = {s.url: s for s in (lucky, proven)}
    hosts = wf.host_yield(sources)
    gmean = 0.1
    assert wf.score(proven, hosts, gmean) > wf.score(lucky, hosts, gmean)


def test_never_fetched_ground_stays_reachable() -> None:
    """A frontier that collapses onto what it already understands has stopped being wide."""
    fresh = _src("https://new.test/1", host="new.test")
    dead = _src("https://d.test/1", host="d.test", fetches=40, candidates=0)
    sources = {s.url: s for s in (fresh, dead)}
    hosts = wf.host_yield(sources)
    assert wf.score(fresh, hosts, 0.1) > wf.score(dead, hosts, 0.1)


def test_a_repeatedly_failing_source_is_starved_but_never_deleted() -> None:
    """Deleting loses the evidence it was tried, which is how a dead source is rediscovered and
    re-crawled forever."""
    bad = _src("https://x.test/1", host="x.test", fetches=10, candidates=2,
               consecutive_failures=9)
    ok = _src("https://y.test/1", host="y.test", fetches=10, candidates=2)
    sources = {s.url: s for s in (bad, ok)}
    hosts = wf.host_yield(sources)
    assert wf.score(bad, hosts, 0.1) < wf.score(ok, hosts, 0.1)
    assert bad.url in sources


def test_an_unchanged_page_decays_so_the_hour_moves_on() -> None:
    stale = _src("https://x.test/1", host="x.test", fetches=20, candidates=5, unchanged_streak=6)
    live = _src("https://y.test/1", host="y.test", fetches=20, candidates=5)
    sources = {s.url: s for s in (stale, live)}
    hosts = wf.host_yield(sources)
    assert wf.score(stale, hosts, 0.1) < wf.score(live, hosts, 0.1)


def test_one_host_cannot_own_the_hour() -> None:
    """Depth bought by giving up width is not a trade this crawler may make."""
    sources = {}
    for i in range(40):
        s = _src(f"https://big.test/{i}", host="big.test", fetches=50, candidates=40)
        sources[s.url] = s
    for i in range(10):
        s = _src(f"https://small{i}.test/x", host=f"small{i}.test")
        sources[s.url] = s
    picked = wf.due(sources, budget=20)
    from collections import Counter
    per_host = Counter(s.host for s in picked)
    assert per_host["big.test"] <= max(2, 20 // 8)
    assert len(per_host) > 1, "the whole budget went to one host"


def test_discovery_records_where_it_came_from() -> None:
    """Provenance for a source is the same requirement as provenance for a candidate."""
    sources: dict[str, wf.Source] = {}
    assert wf.add(sources, "https://x.test/a", via="https://hub.test/")
    assert sources["https://x.test/a"].discovered_via == "https://hub.test/"
    assert not wf.add(sources, "https://x.test/a", via="other"), "a known source is not re-added"
