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


# --------------------------------------------------------------- the silent-zero refusal
# THE DEFECT THIS PINS, measured on the 2026-08-06 06:33 sweep. 17 of 34 Bilibili queries -- the
# LAST 17, contiguous, after ~68 signed requests -- returned ([], None): no rows and no error. The
# miner recorded them as healthy zeros, so half the desk's highest-yielding source produced
# nothing while appearing in no blocked list, opening no route hunt, and reaching the source-health
# ledger as HEALTHY. Re-run standalone minutes later the same queries returned 19 rows each.
#
# The measurement that makes this unambiguous: Bilibili answers a keyword that cannot match
# anything (`zzqqxxjjvv不存在的关键词9182`) with numResults=1000 and 20 generic fallback rows. The
# API has NO empty state for a text query, so `code=0` with an empty result set is always a
# refusal and never an empty corpus.
#
# Same class as the two Chinese-lane bugs already fixed (the CJK word-boundary bug, the Sogou
# attribute-order bug): the FETCH was healthy and the desk was told there was nothing there.

def _fake_body(rows: object, *, code: int = 0, num_results: object = 1000) -> dict:
    return {"code": code, "data": {"result": rows, "numResults": num_results}}


def test_empty_result_set_is_reported_as_a_refusal_not_an_empty_corpus(monkeypatch) -> None:
    import libs.data.bilibili as bl
    monkeypatch.setattr(bl, "signed_get", lambda *a, **k: _fake_body([]))
    vids, err = bl.search("量化 过拟合")
    assert vids == []
    assert err, "code=0 with no rows returned as a clean empty -- this is the silent-zero defect"
    assert "SOFT REFUSAL" in err


def test_a_missing_result_key_is_also_a_refusal(monkeypatch) -> None:
    """`data` present but carrying no `result` at all -- the other shape a throttle takes."""
    import libs.data.bilibili as bl
    monkeypatch.setattr(bl, "signed_get", lambda *a, **k: {"code": 0, "data": {}})
    vids, err = bl.search("量化 回测")
    assert vids == [] and err and "SOFT REFUSAL" in err


def test_a_real_result_set_still_parses_clean(monkeypatch) -> None:
    """The refusal check must not swallow healthy responses."""
    import libs.data.bilibili as bl
    monkeypatch.setattr(bl, "signed_get", lambda *a, **k: _fake_body([
        {"bvid": "BV1xx", "title": "量化<em>回测</em>", "author": "a", "description": "d",
         "tag": "量化,回测", "duration": "12:30", "play": 100, "pubdate": 1},
    ]))
    vids, err = bl.search("量化 回测")
    assert err is None
    assert len(vids) == 1 and vids[0].bvid == "BV1xx" and vids[0].title == "量化回测"


def test_rows_without_a_bvid_do_not_masquerade_as_a_refusal(monkeypatch) -> None:
    """A page of unusable rows is a PARSE outcome, not a refusal -- the two must stay distinct or
    the backoff would fire on a healthy source and cost the rest of the run's queries."""
    import libs.data.bilibili as bl
    monkeypatch.setattr(bl, "signed_get", lambda *a, **k: _fake_body([{"title": "no bvid"}]))
    vids, err = bl.search("量化 回测")
    assert vids == [] and err is None
