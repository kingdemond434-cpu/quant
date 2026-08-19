"""The ranker, and the silent bug that made an entire source look empty.

test_chinese_text_is_actually_scored is the one that matters. Every English pattern is anchored
with \\b, word boundaries are defined by non-word characters, and CJK text contains none -- so a
\\b-anchored pattern NEVER matches a Chinese title. The miner fetched 102 Bilibili videos and
scored every one of them at zero, which reads exactly like "that source has nothing" rather than
"the ranker cannot see it".
"""
from __future__ import annotations

from libs.research.video_triage import SURFACE_THRESHOLD, score_title, triage

# ------------------------------------------------------------------ the record it encodes

def test_large_n_measurement_ranks_high():
    """Every large-N source in the 2026-08-01 batch converted; no narrative source did."""
    s, _ = score_title("I Ran 133,461 Backtests to Find a Real Trading Edge")
    assert s >= 5.0


def test_method_words_rank_high():
    s, _ = score_title("How I Develop Trading Strategies | Permutation Tests and Walk Forward")
    assert s >= 5.0


def test_personal_profit_claims_rank_below_the_surface_threshold():
    """The strongest negative in the record. Not because such people lie -- because a claim about
    one person's returns contains no number this desk can check against its own data."""
    for title in ("I Reverse-Engineered a $102,000/Month Trader's Strategy",
                  "Turning $50k - $500k In 1 Year with AI Trading (My Progress So Far)",
                  "He Says One Strategy Made Him $1M"):
        s, _ = score_title(title)
        assert s < SURFACE_THRESHOLD, f"{title!r} scored {s}"


def test_ai_agent_content_is_suppressed():
    s, _ = score_title("8 Ways I Make Money With Claude")
    assert s < SURFACE_THRESHOLD


def test_the_hits_explain_the_score():
    """A ranking with no visible reason gets overridden by whatever the reader already believed."""
    s, hits = score_title("I tested 100,000 strategies with walk-forward and monte carlo")
    assert hits and any(h.startswith("+") for h in hits)
    assert abs(sum(float(h.split()[0]) for h in hits) - s) < 1e-9


# --------------------------------------------------------------- THE CJK BUG THIS FILE GUARDS

def test_chinese_text_is_actually_scored():
    """THE REGRESSION. \\b matches at a word/non-word boundary; CJK characters are all "word"
    characters with no separators, so a \\b-anchored alternation never fires on Chinese. Every
    Chinese pattern must therefore be written WITHOUT \\b."""
    s, hits = score_title("【因子实战7】Python因子回测：一个因子的诞生")  # noqa: RUF001
    assert s >= SURFACE_THRESHOLD, f"Chinese title scored {s} -- the CJK patterns are not firing"
    assert hits


def test_chinese_method_words_rank_high():
    s, _ = score_title("量化策略的置换检验与样本外回测：如何识别过拟合")  # noqa: RUF001
    assert s >= 8.0


def test_chinese_course_funnel_is_suppressed():
    """Bilibili quant search is dominated by course-funnel uploads. Same narrative/marketing
    category that converted zero times in the batch."""
    for title in ("量化交易教程 B站强推 零基础入门 整整108集 保姆级教程",
                  "全套教程 手把手教学 附源码 加微信领取资料"):
        s, _ = score_title(title)
        assert s < SURFACE_THRESHOLD, f"{title[:24]!r} scored {s}"


def test_chinese_profit_bait_is_suppressed():
    s, _ = score_title("量化交易 月入十万 稳赚 财富自由")
    assert s < 0


def test_a_real_chinese_study_outranks_a_chinese_tutorial():
    study, _ = score_title("10000个量化策略回测真相：你以为能赚钱的指标正在让你亏钱")  # noqa: RUF001
    tutorial, _ = score_title("Python量化交易零基础入门教程 保姆级 手把手")
    assert study > tutorial


# ------------------------------------------------------------------------------- triage()

def test_triage_filters_and_sorts():
    vids = [("a" * 11, "I tested 500,000 strategies with permutation tests"),
            ("b" * 11, "My trading journey and how I made $1M"),
            ("c" * 11, "Walk forward analysis in python")]
    out = triage(vids, channel="x")
    names = [c.video_id for c in out]
    assert "b" * 11 not in names
    assert out == sorted(out, key=lambda c: (-c.score, c.title))


def test_triage_records_the_channel():
    out = triage([("a" * 11, "permutation test walk forward backtest")], channel="@src")
    assert out and out[0].channel == "@src"
    assert out[0].url.endswith("a" * 11)


class TestCJKHomographTraps:
    """The third bug of this family, measured 2026-08-05 on a live Juejin pull.

    The CJK positives are deliberately bare substrings (Chinese has no word boundaries to
    anchor on -- that was bug one, where every \\b-anchored pattern silently scored 102
    Bilibili videos at zero). The cost of that correctness is that a term also matches inside
    unrelated compounds: 因子 (factor) sits inside 双因子认证 (two-FACTOR authentication), and
    an SSH/TOTP article scored 6.0 and would have surfaced into the research queue.

    These assertions are about SUBJECT, not quality: an authentication article is not a weak
    quant article, it is a different field. The paired positive cases are the load-bearing
    half -- a disambiguator that also suppresses real factor research would be a worse bug
    than the one it fixes.
    """

    def test_authentication_compounds_do_not_read_as_factor_research(self) -> None:
        trapped = "使用OATH Toolkit实现ssh登录时进行TOTP双因子认证"
        assert score_title(trapped)[0] < SURFACE_THRESHOLD

    def test_biology_compounds_do_not_read_as_factor_research(self) -> None:
        assert score_title("肿瘤转录因子表达量分析")[0] < SURFACE_THRESHOLD

    def test_real_factor_research_still_surfaces(self) -> None:
        """The half that matters: the fix must cost nothing on genuine rows."""
        # The fullwidth colon below is VERBATIM from the live Juejin row (hence the suppression
        # on that line). Normalising it to ASCII would make the fixture something the source
        # never emits, which is how a parser test passes on text the parser will never see.
        for title in ("数据库交易回测系列二：多因子Alpha策略回测",  # noqa: RUF001
                      "决策树特征筛选结果回测验证模板:从因子挖掘到策略实证",
                      "从计算、建模到回测:因子挖掘的最佳实践"):
            assert score_title(title)[0] >= SURFACE_THRESHOLD, title

    def test_plain_validation_language_is_not_blanket_killed(self) -> None:
        """验证 means 'authenticate' only in the auth compounds -- alone it is still the
        desk's highest-value word, so the disambiguator must be compound-scoped."""
        assert score_title("样本外验证")[0] >= SURFACE_THRESHOLD


def test_foreign_language_methodology_titles_surface():
    """THE THIRD INSTANCE of the CJK-\\b / Sogou failure class (2026-08-18). The foreign miner
    fetches Japanese/Korean/Russian/Vietnamese/Turkish forests, and the ranker had NO pattern in
    any of those scripts -- so a measured run fetched 1,601 rows and surfaced ZERO. A real
    methodology title in each language must now clear the threshold, or the lane is silently dead
    again."""
    for title in (
        "暗号資産 バックテスト 過学習 検証",              # JA: backtest / overfitting / validation
        "금 XAUUSD 백테스트 과최적화 검증",              # KO: gold backtest / over-optimization
        "золото стратегия бэктест переобучение",          # RU: gold strategy backtest / overfitting  # noqa: E501
        "vàng backtest quá khớp kiểm định ngoài mẫu",     # VI: gold overfit / oos  # noqa: RUF001, E501
        "altın geriye dönük test aşırı optimizasyon",     # TR: gold backtest / over-optimization  # noqa: RUF001, E501
    ):
        s, _ = score_title(title)
        assert s >= SURFACE_THRESHOLD, f"foreign methodology title scored {s}: {title}"
