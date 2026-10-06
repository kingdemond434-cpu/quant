"""Part A: the multilingual event/policy factor tagger, its PIT panel, and the LLM tier."""
# ruff: noqa: RUF001 -- the fixtures are Japanese, Chinese and Korean text.
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from libs.research import event_factors as ef
from libs.research import event_factors_llm as efl


@pytest.mark.parametrize(("text", "lang", "country", "factor", "sign"), [
    ("Fed signals a rate cut as inflation cools", "en", "US", "monetary_tone", -1),
    ("BoJ Ueda sounds hawkish; rate hike seen in October", "en", "JP", "monetary_tone", 1),
    ("日銀が利上げを決定、円高が進む", "ja", "JP", "monetary_tone", 1),
    ("政府が経済対策と補正予算を決定", "ja", "JP", "fiscal_stimulus", 1),
    ("トヨタが業績予想を下方修正", "ja", "JP", "earnings_guidance", -1),
    ("央行宣布降准，人民币走弱", "zh", "CN", "monetary_tone", -1),
    ("美国扩大芯片出口管制，实体清单新增企业", "zh", "US", "export_controls", 1),
    ("国务院出台财政刺激，发行特别国债", "zh", "CN", "fiscal_stimulus", 1),
    ("한국은행 기준금리 인상 단행", "ko", "KR", "monetary_tone", 1),
    ("삼성전자 어닝 쇼크, 영업이익 감소", "ko", "KR", "earnings_guidance", -1),
    ("반도체 공장 가동 중단으로 공급 차질", "ko", "KR", "supply_shock", 1),
])
def test_the_tagger_reads_each_language_with_its_pole(text: str, lang: str, country: str,
                                                      factor: str, sign: int) -> None:
    t = ef.tag(text)
    assert t.lang == lang
    assert country in t.countries
    assert t.counts.get(factor, 0) >= 1
    assert (t.signed.get(factor, 0) > 0) == (sign > 0)
    assert (t.signed.get(factor, 0) < 0) == (sign < 0)


def test_longest_match_masks_the_shorter_term_it_contains() -> None:
    # 制裁解除 (sanctions lifted) contains 制裁 (sanctions): read once, as a lifting.
    t = ef.tag("中国が制裁解除を発表")
    assert t.signed["export_controls"] == -1 and t.counts["export_controls"] == 1


def test_latin_terms_need_word_bounds_and_silence_is_a_measured_zero() -> None:
    t = ef.tag("A software update warns of nothing at FedEx")
    assert dict(t.counts) == {} and t.countries == (ef.GLOBAL,)
    assert ef.tag("A war of words").counts.get("geopolitical_risk") == 1


def test_a_country_hint_from_the_source_is_kept() -> None:
    assert ef.tag("Monetary policy statement", country_hint="GB").countries[0] == "GB"
    assert ef.country_hint_for_currency("jpy") == "JP"


def _doc(i: int, text: str, at: datetime) -> ef.Doc:
    return ef.Doc(doc_id=f"d{i}", text=text, available_at=at)


def test_the_panel_is_stamped_available_after_its_day_and_gated_by_decision_time() -> None:
    t0 = datetime(2026, 9, 28, 10, tzinfo=UTC)
    docs = [_doc(1, "日銀が利上げを決定", t0), _doc(2, "日銀がタカ派姿勢", t0 + timedelta(hours=2)),
            _doc(3, "日銀が利下げ", t0 + timedelta(days=1)), _doc(1, "日銀が利上げを決定", t0)]
    rows = [r for r in ef.build_panel(docs) if r.country == "JP" and r.factor == "monetary_tone"]
    assert [r.day for r in rows] == ["2026-09-28", "2026-09-29"]
    assert rows[0].n_docs == 2 and rows[0].intensity == 1.0      # duplicate doc counted once
    assert rows[1].intensity == -1.0
    assert rows[0].available_time == "2026-09-29T00:00:00+00:00"
    # PIT: at 23:59 on the 28th nothing is knowable; on the 29th only the 28th's row.
    assert ef.panel_asof(rows, datetime(2026, 9, 28, 23, 59, tzinfo=UTC)) == []
    got = ef.panel_asof(rows, datetime(2026, 9, 29, 12, tzinfo=UTC))
    assert [r.day for r in got] == ["2026-09-28"]


def test_orientation_is_the_currency_leg_convention() -> None:
    assert ef.orient("JP", "USDJPY") == -1 and ef.orient("US", "USDJPY") == 1
    assert ef.orient("JP", "EURUSD") == 0


def test_llm_tier_without_a_seat_is_unmeasured_and_the_lexicon_carries(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.ops import llm_seat
    monkeypatch.setattr(llm_seat, "primary_seat", lambda: None)
    docs = [_doc(1, "Fed rate cut", datetime(2026, 9, 29, tzinfo=UTC))]
    tags, status = efl.llm_tags(docs)
    assert tags == {} and status["state"] == efl.UNMEASURED and "seat" in status["why"]


def test_llm_tier_parses_an_injected_reply_and_caches_it() -> None:
    docs = [_doc(1, "Fed rate cut", datetime(2026, 9, 29, tzinfo=UTC)),
            _doc(2, "unparseable item", datetime(2026, 9, 29, tzinfo=UTC))]
    reply = ('noise [{"id": "d1", "country": "US", "factors": {"monetary_tone": -1, '
             '"bogus": 1}}] trailing')
    tags, status = efl.llm_tags(docs, chat=lambda prompt, system: (reply, None))
    assert status["state"] == "OK" and status["parsed"] == 1 and status["unparsed"] == 1
    assert tags["d1"].signed == {"monetary_tone": -1} and tags["d1"].tier == "llm"
    cache = {r["hash"]: r for r in status["new_cache"]}
    again, st2 = efl.llm_tags(docs[:1], cache=cache,
                              chat=lambda p, s: pytest.fail("a cached title is never re-asked"))
    assert again["d1"].signed == {"monetary_tone": -1} and st2["from_cache"] == 1
