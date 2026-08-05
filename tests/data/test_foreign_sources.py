"""Non-Chinese foreign forests: Japanese, Korean, Russian.

WHY THESE EXIST AT ALL. The desk's Chinese lane was justified by an argument that is
language-agnostic -- large, practitioner-authored, invisible to English search -- and that
argument was being applied to exactly one language. Korean is the sharpest omission: this desk
MEASURES the Upbit/Bithumb premium as a mechanism class (`capital_control_barrier_rent`) and had
never read a word written by the people creating it.

WHAT THESE TESTS GUARD, and it is not the HTTP. Network parsers are tested against captured
payload shapes because a live assertion is a test that fails when a site has a bad afternoon, and
a suite that fails for reasons outside the repo gets muted. What must not regress:

  * ENTITY DECODING. Hatena's RSS returns titles as numeric character references (`&#x306B;` for
    に). Undecoded, the triage ranker sees no Japanese at all and scores every row zero -- a real
    edge made INVISIBLE to the gate rather than rejected by it. Identical failure to the CJK
    word-boundary bug and to the CN entity bug fixed the same day; third instance of one class.
  * THE STRIP/DECODE ORDER, which is the natural thing to get backwards.
  * ERRORS RETURNED, NEVER RAISED. One bad keyword in a sweep of ~85 requests must not abort the
    other 84 -- the same rule every other miner on this desk follows.
  * SHAPE COMPATIBILITY with cn_sources.Article, because the ranker, the queue writer and the
    dedupe key all already speak that shape. A second parallel article type is how a desk ends up
    indexing four languages and ranking one.
"""
from __future__ import annotations

import json
import urllib.error

import pytest

from libs.data import cn_sources
from libs.data import foreign_sources as F


def _stub(monkeypatch: pytest.MonkeyPatch, body: str) -> None:
    monkeypatch.setattr(F, "_get", lambda *a, **k: body)


def _raise(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> None:
    def boom(*a: object, **k: object) -> str:
        raise exc
    monkeypatch.setattr(F, "_get", boom)


class TestEntityDecodingTheThirdInstanceOfThisBug:
    def test_hatena_numeric_references_are_decoded(self, monkeypatch) -> None:
        """THE CASE THAT MOTIVATED THIS FILE. Hatena really does serve titles this way, verified
        live. An undecoded title contains no Japanese for the ranker to score."""
        rss = ("<rdf:RDF><item><title>&#x6697;&#x53F7;&#x8CC7;&#x7523; "
               "&#x30D0;&#x30C3;&#x30AF;&#x30C6;&#x30B9;&#x30C8;</title>"
               "<link>https://example.jp/a</link><description>x</description></item></rdf:RDF>")
        _stub(monkeypatch, rss)
        arts, err = F.hatena("暗号資産")
        assert err is None and arts
        assert arts[0].title == "暗号資産 バックテスト"
        assert "&#x" not in arts[0].searchable, "encoded text reached the ranker's input"

    def test_named_entities_are_decoded_too(self, monkeypatch) -> None:
        _stub(monkeypatch, '<rss><item><title>A &amp; B &quot;C&quot;</title>'
                           "<link>https://x/1</link></item></rss>")
        assert F.habr("q")[0][0].title == 'A & B "C"'

    def test_tags_are_stripped_before_entities_are_decoded(self, monkeypatch) -> None:
        """ORDER IS LOAD-BEARING. Decode first and an encoded `&lt;b&gt;` becomes a real tag the
        stripper then eats, deleting text that was never markup on the page."""
        _stub(monkeypatch, "<rss><item><title>&lt;b&gt;криптовалюта&lt;/b&gt;</title>"
                           "<link>https://x/1</link></item></rss>")
        assert F.habr("q")[0][0].title == "<b>криптовалюта</b>"

    def test_cdata_wrappers_are_removed(self, monkeypatch) -> None:
        """Habr and vc.ru both wrap titles in CDATA; an unstripped wrapper puts `<![CDATA[` into
        the text the ranker scores."""
        _stub(monkeypatch, "<rss><item><title><![CDATA[криптовалюта бэктест]]></title>"
                           "<link>https://x/1</link></item></rss>")
        assert F.habr("q")[0][0].title == "криптовалюта бэктест"


class TestEachParserOnItsRealPayloadShape:
    def test_qiita_json(self, monkeypatch) -> None:
        _stub(monkeypatch, json.dumps([{
            "id": "abc123", "title": "暗号資産のバックテスト", "url": "https://qiita.com/x",
            "user": {"id": "someone"}, "tags": [{"name": "Python"}], "body": "本文"}]))
        arts, err = F.qiita("暗号資産")
        assert err is None and len(arts) == 1
        a = arts[0]
        assert (a.source, a.ident, a.author) == ("qiita", "abc123", "someone")
        assert "Python" in a.snippet, "tags carry method words and belong in the scored text"

    def test_zenn_json_builds_an_absolute_url(self, monkeypatch) -> None:
        """`path` is relative; a row whose url does not resolve is a candidate nobody can open."""
        _stub(monkeypatch, json.dumps({"articles": [
            {"id": 1, "title": "バックテスト", "path": "/u/articles/slug",
             "user": {"username": "u"}}]}))
        assert F.zenn("q")[0][0].url == "https://zenn.dev/u/articles/slug"

    def test_dcinside_html(self, monkeypatch) -> None:
        _stub(monkeypatch, '<div><a href="https://gall.dcinside.com/1" class="tit_txt">'
                           "퀀트 백테스트 과최적화</a></div>")
        arts, err = F.dcinside("퀀트")
        assert err is None and arts[0].title == "퀀트 백테스트 과최적화"

    def test_dcinside_tolerates_the_other_attribute_order(self, monkeypatch) -> None:
        """The Sogou parser lost a working source for a week to a regex that demanded one
        attribute order. That lesson is cheaper to reuse than to relearn."""
        _stub(monkeypatch, '<a class="tit_txt" href="https://gall.dcinside.com/2">퀀트 검증</a>')
        arts, err = F.dcinside("퀀트")
        assert err is None and arts and arts[0].title == "퀀트 검증"


class TestFailuresAreReportedNotRaisedAndNotFaked:
    @pytest.mark.parametrize("fn", [F.qiita, F.zenn, F.hatena, F.dcinside, F.habr])
    def test_a_transport_error_returns_a_reason(self, monkeypatch, fn) -> None:
        """One bad keyword in ~85 requests must not abort the other 84."""
        _raise(monkeypatch, TimeoutError("read timed out"))
        arts, err = fn("q")
        assert arts == [] and err and "TimeoutError" in err

    def test_a_fetched_but_unparseable_page_says_which(self, monkeypatch) -> None:
        """'markup changed' and 'the source is empty' are opposite facts with opposite fixes, and
        a parser that reports the second for the first sends the next reader nowhere."""
        _stub(monkeypatch, "<html><body>no results here</body></html>")
        for fn in (F.hatena, F.dcinside, F.habr):
            arts, err = fn("q")
            assert arts == [] and err and ("changed" in err or "parsed" in err)

    def test_a_shape_change_in_a_json_api_is_named(self, monkeypatch) -> None:
        _stub(monkeypatch, json.dumps({"unexpected": "shape"}))
        arts, err = F.qiita("q")
        assert arts == [] and err and "shape changed" in err

    def test_rows_missing_a_title_or_id_are_dropped_not_emitted_blank(self, monkeypatch) -> None:
        """A blank-titled row scores zero and reads to a human as 'nothing found in Japanese',
        which is a very different claim from 'the API changed'."""
        _stub(monkeypatch, json.dumps([{"id": "", "title": "", "url": "https://x"},
                                       {"id": "ok", "title": "有効", "url": "https://x/2"}]))
        assert [a.ident for a in F.qiita("q")[0]] == ["ok"]


class TestBreadthIsTerritoryAndParityWithChinese:
    def test_every_language_carries_a_real_query_set(self) -> None:
        for lang, qs in F.LANGUAGES.items():
            assert len(qs) >= 15, f"{lang} has {len(qs)} queries -- not parity with the CN lane"
            assert len(set(qs)) == len(qs), f"{lang} repeats a query"

    def test_the_queries_are_native_not_translated_english(self) -> None:
        """A translated English phrase finds translated English content, which is the one corpus
        already covered. Each set must be written in its own script."""
        assert any("぀" <= c <= "ヿ" for c in "".join(F.QUERIES_JA)), "no kana in ja"
        assert any("가" <= c <= "힯" for c in "".join(F.QUERIES_KO)), "no hangul in ko"
        assert any("Ѐ" <= c <= "ӿ" for c in "".join(F.QUERIES_RU)), "no cyrillic in ru"

    def test_the_korean_set_covers_the_premium_the_desk_already_screens(self) -> None:
        """capital_control_barrier_rent is measured against Upbit/Bithumb. Reading the community
        that creates that premium is the cheapest possible mechanism research on this desk."""
        joined = " ".join(F.QUERIES_KO)
        assert "김치프리미엄" in joined and "업비트" in joined

    def test_every_source_is_reachable_from_the_table(self) -> None:
        """The miner iterates SOURCES rather than a hardcoded list, so a source missing here is a
        source that silently never runs.

        STRUCTURAL, NOT A LITERAL SET. This asserted the exact five original names, which made it
        a change-detector: adding a forest broke it, and the only way to "fix" that is to paste
        the new name in, which tests nothing. What actually has to hold is that every source is
        callable, declares a language the query table covers, and is reachable by iteration --
        properties the NEXT forest inherits for free.
        """
        assert len(F.SOURCES) >= 5, "the foreign lane has lost sources"
        for name, (fn, lang) in F.SOURCES.items():
            assert callable(fn), f"{name} is not callable"
            assert lang in F.LANGUAGES, f"{name} declares language {lang!r} with no query set"
        # Every language with a query set must have at least one source that reads it, or the
        # territory was written and nothing ever walks it.
        covered = {lang for _, lang in F.SOURCES.values()}
        assert covered == set(F.LANGUAGES), (
            f"query territories with no source: {sorted(set(F.LANGUAGES) - covered)}; "
            f"sources with no territory: {sorted(covered - set(F.LANGUAGES))}")

    def test_every_language_has_a_candid_forum_lane_not_only_polished_venues(self) -> None:
        """THE ASYMMETRY THIS FILE EXISTS TO CLOSE. Qiita, Zenn, Habr and Velog are PUBLICATION
        venues: people write there to be seen being competent, so the failure literature -- the
        part actually worth mining -- is systematically under-represented. The Chinese lane already
        reaches the candid register through Bilibili comment culture; every non-Chinese lane was
        polished-only, which is a breadth gap dressed as coverage.
        """
        forums = {"note", "dcinside", "coinpan", "smartlab", "tinhte", "eksisozluk"}
        by_lang: dict[str, set[str]] = {}
        for name, (_fn, lang) in F.SOURCES.items():
            by_lang.setdefault(lang, set()).add(name)
        missing = [lang for lang, names in by_lang.items() if not (names & forums)]
        assert not missing, (
            f"languages with no candid-register lane: {missing}. A polished venue is not a "
            "substitute for a forum -- it is a change of subject.")

    def test_the_article_shape_matches_the_chinese_one(self) -> None:
        """Same shape means a new language costs a parser, not a pipeline. Diverge and every
        downstream consumer grows a branch per language."""
        fields = {"source", "ident", "title", "url", "author", "snippet"}
        assert fields <= set(F.Article.__dataclass_fields__)
        assert fields <= set(cn_sources.Article.__dataclass_fields__)
        assert F.Article(source="s", ident="i", title="t", url="u").searchable == "t "


class TestTheTwoDefectsTheFirstLiveSweepFound:
    """Both found by RUNNING it, not by reading it -- which is the point of shipping a first
    sweep before declaring a source family done."""

    def test_an_empty_korean_result_is_not_reported_as_a_broken_parser(self, monkeypatch) -> None:
        """4 of 17 Korean queries reported "markup changed" while the SAME parser worked on the
        other 13 -- the signature of a false diagnosis, not a real break. DCInside says "no
        results" on the page itself. The two verdicts send a reader to opposite places: one says
        rewrite the regex, the other says the query found nothing and the source is fine."""
        _stub(monkeypatch, "<html><body><div>검색 결과가 없습니다</div></body></html>")
        arts, err = F.dcinside("팩터 유효성 소멸")
        assert arts == []
        assert err is None, "an empty result set must not be reported as a parser failure"

    def test_a_genuinely_changed_markup_still_reports_as_such(self, monkeypatch) -> None:
        """The fix must not swallow real breakage -- a page with neither results NOR a
        no-results marker is exactly the case worth shouting about."""
        _stub(monkeypatch, "<html><body>totally different page</body></html>")
        arts, err = F.dcinside("q")
        assert arts == [] and err and "markup changed" in err

    def test_a_source_that_said_429_is_not_hammered_for_the_rest_of_the_run(
        self, monkeypatch,
    ) -> None:
        """Hatena answered 429 to EVERY one of 18 queries in the first sweep. Continuing to send
        seventeen more requests to a source that asked for a pause is how a temporary rate-limit
        becomes a durable block -- costing the LANE rather than the query."""
        monkeypatch.setattr(F, "_BACKED_OFF", set())
        err429 = urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None)  # type: ignore[arg-type]
        _raise(monkeypatch, err429)
        arts, err = F.hatena("q1")
        assert arts == [] and err and "429" in err

        calls: list[str] = []

        def _should_not_run(*a: object, **k: object) -> str:
            calls.append("fetched")
            return ""
        monkeypatch.setattr(F, "_get", _should_not_run)
        _, err2 = F.hatena("q2")
        assert calls == [], "a backed-off source must not be fetched again this run"
        assert err2 and "backed off" in err2

    def test_pacing_is_per_source_not_one_global_number(self) -> None:
        """A single pace either wastes time on the tolerant sources or keeps losing the strict
        one. Hatena was 429ing at the spacing Qiita and Habr were untroubled by."""
        assert F._MIN_INTERVAL_S["hatena"] > F._MIN_INTERVAL_S["qiita"]
        assert set(F._MIN_INTERVAL_S) >= set(F.SOURCES)
