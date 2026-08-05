"""The Sogou/WeChat parse, on FIXTURES rather than the live web.

Every defect this source has produced was a parse that succeeded on a healthy page and starved the
ranker -- the CJK word-boundary bug, the attribute-order bug, and now the dropped summary. All
three looked like "the source is weak" and none of them were, so these tests hold real markup
rather than mocking the fetch.
"""
from __future__ import annotations

from libs.data.cn_sources import sogou_weixin

# Real Sogou markup, trimmed. Two results: href BEFORE uigs (the shape that broke the first
# parser), <em> highlight tags inside both title and summary, and one summary carrying the method
# words the title lacks.
_SUM_A = "今天我们来扒一扒<em>回测</em>陷阱:前视偏差与过拟合"
_SUM_B = "因子挖掘结合深度学习:样本外夏普与最大回撤对比"

_HTML = f"""
<ul class="news-list">
<li id="sogou_vr_1">
 <div class="txt-box">
  <h3><a target="_blank" href="/link?url=AAA111" uigs="article_title_0">
      量化<em>回测</em>常见的陷阱</a></h3>
  <p class="txt-info" id="sogou_note_0">{_SUM_A}</p>
  <div class="s-p"><a class="account">某公众号</a></div>
 </div>
</li>
<li id="sogou_vr_2">
 <div class="txt-box">
  <h3><a target="_blank" href="/link?url=BBB222" uigs="article_title_1">模型重大升级</a></h3>
  <p class="txt-info" id="sogou_note_1">{_SUM_B}</p>
 </div>
</li>
</ul>
"""


def _fetch(html: str):
    return lambda *a, **k: html


# ------------------------------------------------------------------------- the summary is scored

def test_the_summary_is_captured(monkeypatch) -> None:
    """THE TEST THAT MATTERS. The page carried all ten summaries and the parser dropped every one,
    so WeChat reached the ranker as bare titles while Juejin arrived with brief_content and
    Bilibili with description plus tags. Measured 2026-08-01: 3 of 40 WeChat articles cleared the
    threshold (7.5%) against Juejin's 42% -- a source that looked weak and was being starved."""
    monkeypatch.setattr("libs.data.cn_sources._get", _fetch(_HTML))
    arts, err = sogou_weixin("量化")
    assert err is None and len(arts) == 2
    assert all(a.snippet for a in arts)
    assert "前视偏差" in arts[0].snippet


def test_searchable_is_title_plus_snippet(monkeypatch) -> None:
    """A Chinese title is often generic while the snippet carries the method words. The second
    fixture title says only '模型重大升级'; everything rankable about it is in the summary."""
    monkeypatch.setattr("libs.data.cn_sources._get", _fetch(_HTML))
    arts, _ = sogou_weixin("量化")
    assert "因子挖掘" in arts[1].searchable
    assert "因子挖掘" not in arts[1].title


def test_each_summary_stays_with_its_own_article(monkeypatch) -> None:
    """Block-wise parsing exists for this. Pairing two global regex passes by document order
    would mis-pair the moment one result lacked a summary, and scoring article A on article B's
    body is far worse than scoring A on its title alone."""
    monkeypatch.setattr("libs.data.cn_sources._get", _fetch(_HTML))
    arts, _ = sogou_weixin("量化")
    assert "前视偏差" in arts[0].snippet and "前视偏差" not in arts[1].snippet
    assert "因子挖掘" in arts[1].snippet and "因子挖掘" not in arts[0].snippet


def test_highlight_tags_never_reach_the_ranker(monkeypatch) -> None:
    """Sogou wraps matched terms in <em>. Unstripped markup would put '<em>' into the text the
    ranker scores and split the very keyword that matched."""
    monkeypatch.setattr("libs.data.cn_sources._get", _fetch(_HTML))
    arts, _ = sogou_weixin("量化")
    for a in arts:
        assert "<em>" not in a.searchable and "</em>" not in a.searchable
    assert arts[0].title == "量化回测常见的陷阱"


# ------------------------------------------------------------------------------- degradation

def test_href_before_uigs_still_parses(monkeypatch) -> None:
    """The attribute-order bug: a regex demanding uigs first matched nothing on ten present
    results and reported 'markup changed' while the page was perfectly healthy."""
    monkeypatch.setattr("libs.data.cn_sources._get", _fetch(_HTML))
    arts, _ = sogou_weixin("量化")
    assert arts[0].url.endswith("/link?url=AAA111")


def test_missing_blocks_fall_back_but_SAY_SO(monkeypatch) -> None:
    """A silent downgrade to title-only scoring is the original defect returning unnoticed, so the
    fallback path returns results AND a warning rather than a clean success."""
    flat = _HTML.replace('<div class="txt-box">', '<div class="other">')
    monkeypatch.setattr("libs.data.cn_sources._get", _fetch(flat))
    arts, err = sogou_weixin("量化")
    assert len(arts) == 2
    assert err and "title-only" in err
    assert not any(a.snippet for a in arts)


def test_a_block_without_a_title_anchor_is_skipped_not_guessed(monkeypatch) -> None:
    broken = _HTML.replace('uigs="article_title_1"', 'uigs="something_else"')
    monkeypatch.setattr("libs.data.cn_sources._get", _fetch(broken))
    arts, err = sogou_weixin("量化")
    assert len(arts) == 1 and err is None


def test_a_result_with_no_summary_still_returns_with_an_empty_one(monkeypatch) -> None:
    partial = _HTML.replace(f'<p class="txt-info" id="sogou_note_1">{_SUM_B}</p>', "")
    monkeypatch.setattr("libs.data.cn_sources._get", _fetch(partial))
    arts, err = sogou_weixin("量化")
    assert len(arts) == 2 and err is None
    assert arts[0].snippet and not arts[1].snippet


def test_duplicate_hrefs_are_collapsed(monkeypatch) -> None:
    monkeypatch.setattr("libs.data.cn_sources._get", _fetch(_HTML + _HTML))
    arts, _ = sogou_weixin("量化")
    assert len(arts) == 2


def test_an_antibot_page_is_reported_not_parsed(monkeypatch) -> None:
    monkeypatch.setattr("libs.data.cn_sources._get", _fetch("<html>antispider</html>"))
    arts, err = sogou_weixin("量化")
    assert not arts and "anti-bot" in err


def test_a_transport_failure_returns_a_reason_rather_than_raising(monkeypatch) -> None:
    def boom(*a, **k):
        raise TimeoutError("read timed out")
    monkeypatch.setattr("libs.data.cn_sources._get", boom)
    arts, err = sogou_weixin("量化")
    assert not arts and "TimeoutError" in err


def test_a_genuinely_empty_page_says_so(monkeypatch) -> None:
    monkeypatch.setattr("libs.data.cn_sources._get", _fetch("<html><body></body></html>"))
    arts, err = sogou_weixin("量化")
    assert not arts and "markup changed or empty result" in err


# ------------------------------------------------------------------ HTML entities (2026-08-05)
#
# THE THIRD PARSE BUG ON THIS SOURCE, after the CJK word-boundary bug and the attribute-order bug,
# and it has the same shape as both: the fetch was healthy and the PARSE quietly degraded what
# reached the ranker. Entities were never decoded, which cost two different things.
#
#   1. EVERY WECHAT URL WAS DEAD. Sogou writes hrefs as `?url=...&amp;type=2&amp;query=...`
#      because an href is an HTML attribute. Taken literally that is a parameter named `amp;type`,
#      so the link does not resolve -- and it fails in the quiet way: the row looks complete, ranks
#      normally, and only breaks when a human finally clicks it.
#   2. ENTITIES REACHED THE SCORER. `&quot;` is untidy; a NUMERIC entity is the hazard, because
#      `&#x91CF;&#x5316;` is how `量化` arrives from some encoders. The ranker would find no
#      Chinese in the title at all and score a relevant article zero -- a real edge made invisible
#      to the gate rather than rejected by it, which is precisely the CJK `\b` failure again.

_ENTITY_HTML = (
    '<div class="txt-box">'
    '<a href="/link?url=ABC&amp;type=2&amp;query=%E9%87%8F%E5%8C%96&amp;token=XYZ" '
    'uigs="article_title_0">&#x91CF;&#x5316;&quot;&#x56DE;&#x6D4B;&quot;&#x9677;&#x9631;</a>'
    '<p class="txt-info">&#x8FC7;&#x62DF;&#x5408; &amp; &#x6837;&#x672C;&#x5916;</p>'
    "</div>"
)


def test_entities_in_the_href_are_decoded_so_the_link_resolves(monkeypatch) -> None:
    monkeypatch.setattr("libs.data.cn_sources._get", _fetch(_ENTITY_HTML))
    arts, err = sogou_weixin("量化")
    assert err is None and len(arts) == 1
    url = arts[0].url
    assert "&amp;" not in url, "an un-decoded href yields a parameter named 'amp;type'"
    assert "&type=2" in url and "&token=XYZ" in url


def test_numeric_entities_are_decoded_so_the_ranker_can_see_the_chinese(monkeypatch) -> None:
    """The expensive half. An encoded title is not merely ugly -- it is unscoreable, and an
    unscoreable title is a candidate the miner discards without ever reporting a problem."""
    monkeypatch.setattr("libs.data.cn_sources._get", _fetch(_ENTITY_HTML))
    arts, _ = sogou_weixin("量化")
    assert arts[0].title == '量化"回测"陷阱'
    assert "&#x" not in arts[0].searchable and "&quot;" not in arts[0].searchable
    assert "量化" in arts[0].searchable, "the keyword the ranker scores on must survive the parse"
    assert arts[0].snippet == "过拟合 & 样本外"


def test_decoding_happens_after_tag_stripping_not_before(monkeypatch) -> None:
    """ORDER IS LOAD-BEARING. Unescape first and an encoded `&lt;em&gt;` becomes a real tag that
    the stripper then eats, deleting text between two angle brackets that were never markup."""
    html_doc = (
        '<div class="txt-box">'
        '<a href="/link?url=A" uigs="article_title_0">'
        '&lt;em&gt;&#x91CF;&#x5316;&lt;/em&gt;</a>'
        '<p class="txt-info">x</p></div>'
    )
    monkeypatch.setattr("libs.data.cn_sources._get", _fetch(html_doc))
    arts, _ = sogou_weixin("量化")
    assert arts[0].title == "<em>量化</em>", (
        "decoding before stripping would have swallowed 量化 as if it were markup")
