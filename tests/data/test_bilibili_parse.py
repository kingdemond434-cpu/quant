"""Bilibili search parsing -- the text that reaches the ranker must be the text on the page.

Bilibili is the widest Chinese source the desk has (24 queries returning 50-80 results each) and
its parser had NO test coverage. `_strip` existed to remove the `<em>` highlight tags Bilibili
wraps around matched terms, and it never decoded HTML entities.

WHY THAT IS A RANKING BUG AND NOT A COSMETIC ONE. `Video.searchable` is what video_triage scores,
and it is built from the stripped title, description and tags. An entity the scorer cannot read is
a keyword the scorer cannot see. `&quot;` merely looks wrong; a NUMERIC entity is the hazard,
because `&#x91CF;&#x5316;` is one of the ways `量化` arrives -- and a title encoded that way
contains no Chinese as far as the ranker is concerned, so a directly relevant video scores zero
and is dropped without any error being reported anywhere.

That is the CJK word-boundary bug's failure mode reached through a different door: a real edge
made INVISIBLE to the gate rather than rejected by it. Those are the expensive ones, because
nothing in the pipeline registers a complaint.
"""
from __future__ import annotations

from libs.data.bilibili import Video, _strip


def test_em_highlight_tags_are_removed() -> None:
    """The original job, pinned so the entity fix cannot regress it."""
    assert _strip("胜率80%的<em class=\"keyword\">布林带</em>挤压策略") == "胜率80%的布林带挤压策略"


def test_named_entities_are_decoded() -> None:
    assert _strip("经典策略范例&quot;布林带Z量化策略&quot;") == '经典策略范例"布林带Z量化策略"'
    assert _strip("A &amp; B") == "A & B"


def test_numeric_entities_are_decoded_so_the_ranker_can_see_the_chinese() -> None:
    """The expensive case. Encoded CJK is unscoreable, and an unscoreable title is a candidate
    discarded silently rather than reported."""
    assert _strip("&#x91CF;&#x5316;&#x56DE;&#x6D4B;") == "量化回测"
    assert _strip("&#37327;&#21270;") == "量化"


def test_decoding_happens_after_tag_stripping_not_before() -> None:
    """ORDER IS LOAD-BEARING, and getting it backwards is the natural mistake: unescape first and
    an encoded `&lt;em&gt;` becomes a REAL tag that this stripper then eats, deleting the text
    between two angle brackets that were never markup on the page."""
    assert _strip("&lt;em&gt;量化&lt;/em&gt;") == "<em>量化</em>"


def test_the_searchable_text_the_ranker_scores_carries_no_markup() -> None:
    """The end-to-end contract: whatever _strip leaves is what gets scored."""
    v = Video(bvid="BV1", title=_strip("&#x91CF;&#x5316;<em>回测</em>"),
              description=_strip("样本外&quot;检验&quot;"), tags=("量化", "回测"))
    s = v.searchable
    assert "量化回测" in s and "样本外\"检验\"" in s
    for artefact in ("&#x", "&#", "&quot;", "<em>", "</em>"):
        assert artefact not in s, f"{artefact!r} reached the ranker's input"


def test_stripping_is_lossless_on_ordinary_text() -> None:
    """A parser that mangles clean input is worse than one that leaves entities alone."""
    # The fullwidth exclamation mark below is deliberate and RUF001 is silenced rather than
    # obeyed: these are real Bilibili titles, and the assertion is precisely that CJK
    # punctuation survives the parse unchanged. "Correcting" it to ASCII would delete the
    # very case the test exists for.
    for plain in ("量化交易 策略回测", "walk forward analysis",
                  "年化 24%！最大回撤仅 5.5%"):  # noqa: RUF001
        assert _strip(plain) == plain
