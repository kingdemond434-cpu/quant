"""LAWS §5e carries the principal's 2026-09-30 source exclusions, and every route is fenced.

The ruling: no Reddit or StockTwits at all, no paid X and no Discord user token; Wikipedia
pageviews and GDELT replace their attention signal; the terms gate fails closed. Before this the
law text said "there is no sixth" while live still fetched Reddit through the free stack. These
tests pin the text AND each route the audit named: the fence itself, the free-stack fetch helper
and hunter, the proposer's minting, the side-channel schedule, the compiler's intake and the
credit lanes. No network: a fenced fetch must never reach the fetch callable at all.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import free_stack as fs  # noqa: E402
from libs.data import terms_fence as tf  # noqa: E402
from libs.research import access_classifier as ac  # noqa: E402

LAWS = (ROOT / "docs" / "LAWS.md").read_text("utf-8")
HOSTS = ("https://www.reddit.com/r/Gold/new.json", "https://old.reddit.com/r/x",
         "https://redd.it/abc", "https://stocktwits.com/symbol/XAUUSD",
         "https://api.stocktwits.com/api/2/streams/symbol/AAPL.json")


def _section_5e() -> str:
    m = re.search(r"^## 5e\..*?(?=^## 5f\.)", LAWS, flags=re.S | re.M)
    assert m, "LAWS §5e is missing"
    return m.group(0)


def test_5e_names_every_excluded_source_both_substitutes_and_the_fence() -> None:
    text = _section_5e()
    assert "NAMED SOURCE EXCLUSIONS" in text and "2026-09-30" in text
    for name in ("Reddit, all of it", "StockTwits, all of it", "paid X/Twitter",
                 "Discord user token", "Wikipedia", "GDELT", "fails closed",
                 tf.BLOCKED_WITH_SUBSTITUTE, tf.BLOCKED_TERMS, "libs/data/terms_fence.py"):
        assert name in text, name
    assert (ROOT / "libs" / "data" / "terms_fence.py").is_file()
    assert (ROOT / "tests" / "research" / "test_reddit_terms_fence.py").is_file()


def test_the_five_acts_stay_five() -> None:
    """The exclusions are sources the principal named, not a sixth refused act."""
    assert len(ac.HARD_BOUNDARY) == 5 and ac.HARD_BOUNDARY_COUNT == 5
    assert "the one standing amendment" in _section_5e()


@pytest.mark.parametrize("url", HOSTS)
def test_the_fence_refuses_every_named_host(url: str) -> None:
    assert tf.fenced_url(url)
    with pytest.raises(tf.TermsFenced):
        tf.check_url(url)


@pytest.mark.parametrize("url", HOSTS)
def test_the_free_stack_fetch_helper_never_calls_out_for_a_fenced_host(url: str) -> None:
    called: list[str] = []
    h = fs.Harvest("x")
    assert fs._get(lambda u, hd, b: called.append(u) or b"{}", h, url) is None
    assert called == [] and h.requests == 0
    assert sum(h.failures.values()) == 1


def test_the_free_stack_reddit_row_is_refused_before_its_fetcher() -> None:
    from research import free_stack_hunter as H
    roster = json.loads((DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    row = next(r for r in roster["sources"] if r.get("id") == "reddit")
    called: list[str] = []
    h, extra = H.run_source(row, None, lambda u, hd, b: called.append(u) or b"{}",  # type: ignore[arg-type]
                            {}, datetime(2026, 10, 6, tzinfo=UTC))
    assert called == [] and extra == {} and h.status == tf.BLOCKED_WITH_SUBSTITUTE
    assert not h.raw and not h.obs


def test_stored_fenced_series_mint_no_cell(monkeypatch: pytest.MonkeyPatch) -> None:
    from research import free_stack_proposer as P
    monkeypatch.setattr(P, "series_exists", lambda sid: True)
    cols = {"reddit": {"mentions": {"hypothesis": ["XAUUSD"], "why": "x"}},
            "stocktwits_x": {"bull": {"hypothesis": ["XAUUSD"], "why": "x"}}}
    roster = {"reddit": {"id": "reddit", "kind": "reddit", "url": "https://www.reddit.com/"},
              "stocktwits_x": {"id": "stocktwits_x", "kind": "x", "url": ""}}
    grid, skipped = P.build_grid(cols, roster)
    assert grid == []
    assert skipped == {"reddit": "terms-fenced: reddit", "stocktwits_x": "terms-fenced: stocktwits"}


def test_the_reddit_side_channel_is_unscheduled() -> None:
    src = (DESK / "side_channels" / "run_all_miners.py").read_text("utf-8")
    tree = ast.parse(src)
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                for a in n.names} | {n.module for n in ast.walk(tree)
                                     if isinstance(n, ast.ImportFrom) and n.module}
    assert "reddit_miner" not in imported
    miners = next(n for n in tree.body if isinstance(n, ast.Assign)
                  and getattr(n.targets[0], "id", "") == "ALL_MINERS")
    names = [e.elts[0].value for e in miners.value.elts]  # type: ignore[attr-defined]
    assert not any(tf.fenced_source(n) for n in names)


def test_intelligence_rows_from_fenced_platforms_are_refused_by_the_compiler() -> None:
    assert tf.fenced_row({"title": "gold squeeze"}, "reddit") == "reddit"
    assert tf.fenced_row({"url": "https://stocktwits.com/x"}, "world") == "stocktwits"
    assert tf.fenced_row({"title": "x"}, "ext_reddit_EURUSD_1") == "reddit"


def test_fenced_platforms_earn_no_external_claim_credit() -> None:
    from research import credit_assignment as CA
    for source in ("reddit", "ext_reddit_EURUSD_1", "miner:stocktwits"):
        assert CA._lane_of(source) == "terms_fenced", source


def test_no_routing_test_uses_an_excluded_host_as_a_researchable_example() -> None:
    src = (ROOT / "tests" / "research" / "test_access_routing.py").read_text("utf-8")
    assert not re.search(r"reddit|stocktwits", src, flags=re.I)
