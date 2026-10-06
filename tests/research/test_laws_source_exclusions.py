"""LAWS §5e carries the principal's 2026-09-30 source exclusions without growing the five acts.

The ruling: no Reddit or StockTwits at all, no paid X and no Discord user token; Wikipedia
pageviews and GDELT replace their attention signal; the terms gate fails closed. Before this
test the law text said "there is no sixth" while the ruling and the Reddit fence said otherwise,
so a session reading only LAWS could re-derive a Reddit route from silence.
"""

from __future__ import annotations

import re
from pathlib import Path

from libs.research import access_classifier as ac

ROOT = Path(__file__).resolve().parents[2]
LAWS = (ROOT / "docs" / "LAWS.md").read_text("utf-8")


def _section_5e() -> str:
    m = re.search(r"^## 5e\..*?(?=^## 5f\.)", LAWS, flags=re.S | re.M)
    assert m, "LAWS §5e is missing"
    return m.group(0)


def test_5e_names_every_excluded_source_and_both_substitutes() -> None:
    text = _section_5e()
    assert "NAMED SOURCE EXCLUSIONS" in text and "2026-09-30" in text
    for name in ("Reddit, all of it", "StockTwits, all of it", "paid X/Twitter",
                 "Discord user token", "Wikipedia", "GDELT", "BLOCKED_ON_TERMS",
                 "fails closed", "libs/data/terms_fence.py"):
        assert name in text, name


def test_the_five_acts_stay_five() -> None:
    """The exclusions are sources the principal named, not a sixth refused act."""
    assert len(ac.HARD_BOUNDARY) == 5 and ac.HARD_BOUNDARY_COUNT == 5
    assert "the one standing amendment" in _section_5e()


def test_no_routing_test_uses_an_excluded_host_as_a_researchable_example() -> None:
    src = (ROOT / "tests" / "research" / "test_access_routing.py").read_text("utf-8")
    assert not re.search(r"reddit|stocktwits", src, flags=re.I)
