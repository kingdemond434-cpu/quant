"""The crawler named ONLINE as an instrument and spent its hour on broker directories.

    python -m pytest desks/mt5/tests/test_crawler_targeting.py -q

THE MEASUREMENT THAT DROVE THIS, from `miner_candidates.per_source` on 2026-09-03 --
evidence rows in, executable candidates out:

    broker_swaps         248 -> 248     structured data
    forexfactory          44 -> 107     structured calendar
    cot                   11 ->   7     structured positioning
    ff_calendar_vintage  113 ->   6     structured, point-in-time
    ------------------------------------------------------------------
    reddit, github, quant_se, bis_speeches, amarkets, world_crawler
                         341 ->   0     PROSE

Prose converts at ZERO, and it is not a tuning failure: the compiler's own rule is
"exact recipe or structured causal data only; no prose-to-family guessing", so an
article cannot supply a registered family with exact params. A crawler pointed at
articles is spending its whole budget on the one input class that provably cannot
produce a candidate.

TWO DEFECTS THIS PINS:

  1. `_SYM` is six capital letters, so the crawler's own output named ONLINE 50
     times, POINTS 27 and AVISOS 8 -- more than every real instrument combined.
     "Resolved later by the compiler" meant nothing ever resolved it.

  2. `score` ranked on `candidates + 0.25*leads`, and candidates were zero
     everywhere, so it ranked purely on LINKS. The two biggest frontier
     expansions were forexfactory.com/brokers (247 pages) and
     quantt.co.uk/quant-firms (116) -- a broker directory and a firm directory,
     neither able to hold a testable claim, both excellent at emitting links.
"""
from __future__ import annotations

import sys
from pathlib import Path

SIDE = Path(__file__).resolve().parent.parent / "side_channels"
sys.path.insert(0, str(SIDE))

import world_crawler as wc  # noqa: E402
import world_frontier as wf  # noqa: E402

# ------------------------------------------------- 1. only instruments Fusion quotes

def test_a_six_letter_word_is_not_an_instrument() -> None:
    """ONLINE was the single most-extracted 'symbol' the crawler produced."""
    body = (b"<html><title>t</title><body>ONLINE POINTS AVISOS GLOBEX FOGAIN "
            b"USDCAD XAUUSD momentum H1</body></html>")
    page = wc.read_page(body, "https://x.test/a")
    if not wc._fusion_symbols():
        import pytest
        pytest.skip("no universe registry in this tree -- filter is a no-op by design")
    assert "ONLINE" not in page["symbols"]
    assert "AVISOS" not in page["symbols"]
    assert "XAUUSD" in page["symbols"]
    assert page["symbols_rejected"] >= 3


def test_losing_the_registry_filters_nothing_rather_than_everything(monkeypatch) -> None:
    """An unreadable universe must not blank the symbol column -- that would read
    as 'this page mentions no instruments', which is a different claim (L1.28a)."""
    monkeypatch.setattr(wc, "_fusion_symbols", lambda: set())
    page = wc.read_page(b"<html><body>ONLINE XAUUSD</body></html>", "https://x.test/a")
    assert "XAUUSD" in page["symbols"] and "ONLINE" in page["symbols"]
    assert page["symbols_rejected"] == 0


def test_the_universe_predicate_is_broader_than_the_replay_one() -> None:
    """A page naming XAUUSD is a claim about gold whether or not THIS machine has
    gold bars cached. Filtering on the replay predicate returned 24 symbols on a
    thin checkout and would have discarded most real mentions."""
    syms = wc._fusion_symbols()
    if not syms:
        import pytest
        pytest.skip("no universe registry in this tree")
    assert len(syms) > 100, f"expected the broker's full quoted set, got {len(syms)}"


# --------------------------------------------- 2. hunt data, not opinions about data

def test_data_hubs_are_recognised_across_languages() -> None:
    for url in ("https://tushare.pro/document/2",
                "https://www.shfe.com.cn/statements/dataview.html",
                "https://data.eastmoney.com/cjsj/",
                "https://akshare.akfamily.xyz/data/index.html",
                "https://www.cftc.gov/MarketReports/CommitmentsofTraders/"
                "HistoricalCompressed/index.htm",
                "https://fred.stlouisfed.org/categories"):
        assert wc.is_data_source(url), url


def test_a_broker_directory_is_not_a_data_source() -> None:
    """It emitted 247 pages into the frontier and cannot hold a testable claim."""
    for url in ("https://www.forexfactory.com/brokers",
                "https://www.quantt.co.uk/quant-firms",
                "https://www.quantstart.com/articles/",
                "https://www.reddit.com/r/algotrading/top/?t=week"):
        assert not wc.is_data_source(url), url


def test_the_seeds_now_include_free_data_ground() -> None:
    n_data = sum(1 for s in wc.SEEDS if wc.is_data_source(s))
    assert n_data >= 10, f"only {n_data} of {len(wc.SEEDS)} seeds are data hubs"
    joined = " ".join(wc.SEEDS)
    assert "tushare" in joined and "akshare" in joined, "Chinese open data is missing"
    assert "cftc.gov" in joined and "stlouisfed" in joined


def test_a_dataset_page_is_carried_even_with_no_mechanism_prose() -> None:
    """An API index names no 'momentum' and is exactly the class that converts.
    The old rule discarded the only pages that could ever pay."""
    page = wc.read_page(b"<html><title>API</title><body>nothing here</body></html>",
                        "https://tushare.pro/document/2")
    assert page["symbols"] == [] and page["patterns"] == []
    row = wc.to_discovery("https://tushare.pro/document/2", page, "sha")
    assert row is not None and row["kind"] == "dataset"


def test_an_empty_prose_page_is_still_dropped() -> None:
    page = wc.read_page(b"<html><title>hi</title><body>nothing</body></html>",
                        "https://www.quantstart.com/articles/")
    assert wc.to_discovery("https://www.quantstart.com/articles/", page, "sha") is None


def test_every_row_declares_which_class_it_is() -> None:
    """A consumer that cannot tell a CSV endpoint from a blog post must treat them
    as the same evidence."""
    page = wc.read_page(b"<html><body>XAUUSD momentum</body></html>", "https://x.test/a")
    assert wc.to_discovery("https://x.test/a", page, "s")["kind"] == "prose"
    assert wc.to_discovery("https://x.test/api/v1", page, "s")["kind"] == "dataset"


def test_a_dataset_outranks_a_prose_page_asserting_the_same_things() -> None:
    page = wc.read_page(b"<html><body>XAUUSD momentum H1</body></html>", "https://x.test/a")
    prose = wc.to_discovery("https://blog.test/post", page, "s")
    data = wc.to_discovery("https://blog.test/api/v1", page, "s")
    assert data["confidence"] > prose["confidence"]


# ---------------------------------------------------- 3. link farms stop winning

def test_a_lead_is_worth_far_less_than_a_candidate() -> None:
    """Candidates were zero everywhere, so ranking on leads ranked on LINKS."""
    hosts: dict[str, tuple[float, float]] = {}
    # One candidate is now worth twenty leads, not four. 30 leads must not beat 2
    # candidates; under the old 0.25 weight 30 leads scored 7.5 and buried them.
    farm = wf.Source(url="https://farm.test/dir", host="farm.test", fetches=10,
                     candidates=0, leads=30)
    payer = wf.Source(url="https://payer.test/x", host="payer.test", fetches=10,
                      candidates=2, leads=0)
    assert wf.score(payer, hosts, 0.05) > wf.score(farm, hosts, 0.05)


def test_a_data_hub_is_tried_before_an_equivalent_prose_page() -> None:
    hosts: dict[str, tuple[float, float]] = {}
    prose = wf.Source(url="https://a.test/articles", host="a.test", fetches=0)
    data = wf.Source(url="https://a.test/api/v1", host="a.test", fetches=0)
    assert wf.score(data, hosts, 0.05) > wf.score(prose, hosts, 0.05)


def test_measured_yield_still_beats_the_data_preference() -> None:
    """The preference decides who is TRIED while evidence is thin. It must never
    outrank a page that has actually paid."""
    hosts: dict[str, tuple[float, float]] = {}
    proven_prose = wf.Source(url="https://a.test/blog", host="a.test", fetches=20,
                             candidates=15)
    barren_data = wf.Source(url="https://b.test/api/", host="b.test", fetches=20,
                            candidates=0, leads=0)
    assert wf.score(proven_prose, hosts, 0.05) > wf.score(barren_data, hosts, 0.05)


def test_ranking_never_breaks_the_crawl() -> None:
    """A scoring import that throws must not take down the hour."""
    hosts: dict[str, tuple[float, float]] = {}
    s = wf.Source(url="not a url at all", host="", fetches=1)
    assert isinstance(wf.score(s, hosts, 0.05), float)
