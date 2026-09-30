"""Part B: keyword routing, mood, the bot filter, PIT gating and the delta computation."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from libs.research import social_mood as sm

T0 = datetime(2026, 9, 1, 3, tzinfo=UTC)


def _p(i: int, title: str, at: datetime, author: str = "", source: str = "s") -> sm.Post:
    return sm.Post(source=source, ident=f"i{i}", title=title, first_seen_at=at, author=author)


def test_keywords_route_each_language_to_its_instruments() -> None:
    assert "jp_equity" in sm.topics_of("日経平均が上昇")
    assert "jpy" in sm.topics_of("円安が進む")
    assert set(sm.topics_of("삼성전자 반도체")) >= {"semis"}
    assert "krw" in sm.topics_of("환율 급등")
    assert {"cn_equity", "hk_equity", "cny"} <= set(sm.topics_of("A股 港股 人民币"))


def test_mood_is_signed_and_topic_words_are_on_the_instrument_axis() -> None:
    assert sm.mood_of("日経平均が爆上げ") == 1.0
    assert sm.mood_of("코스피 폭락 손절") == -1.0
    assert sm.mood_of("今日はランチ") == 0.0
    assert sm.mood_of("円安が止まらない", "jpy") == 1.0      # yen weaker = USDJPY up
    assert sm.mood_of("人民币升值", "cny") == -1.0          # CNY stronger = USDCNH down


def test_bot_filter_drops_duplicates_near_duplicates_and_burst_accounts() -> None:
    posts = [
        _p(1, "日経平均が暴落して損切りした、もう無理", T0, "a"),
        _p(2, "日経平均が暴落して損切りした、もう無理", T0 + timedelta(minutes=5), "b"),
        _p(3, "日経平均が暴落して損切りした、もう無理!! http://x.y/z 123",
           T0 + timedelta(minutes=6), "c"),                           # same after normalising
        _p(4, "日経平均が暴落して損切りした、もう無理だ", T0 + timedelta(minutes=7), "d"),
        _p(5, "円安で含み益が増えた、ドル円はまだ上がる", T0 + timedelta(minutes=8), "e"),
    ]
    burst = [_p(10 + k, f"코스피 떡상 가즈아 광고 {k} 번째 {'가' * k}", T0 + timedelta(minutes=k),
                "spam") for k in range(sm.BURST_MAX + 2)]
    kept, rep = sm.bot_filter(posts + burst)
    idents = {p.ident for p in kept}
    assert idents == {"i1", "i5"}
    assert rep.dropped["duplicate_text"] == 2
    assert rep.dropped["near_duplicate"] == 1
    assert rep.dropped["burst_account"] == sm.BURST_MAX + 2
    assert rep.n_in == len(posts) + len(burst) and rep.n_kept == 2


def test_an_account_posting_slowly_is_not_a_burst() -> None:
    words = ("円安", "決算", "配当", "半導体", "銀行株", "指数", "先物", "為替介入")
    slow = [_p(k, f"今日の{words[k]}メモ", T0 + timedelta(hours=2 * k), "slow")
            for k in range(len(words))]
    kept, rep = sm.bot_filter(slow)
    assert rep.dropped["burst_account"] == 0 and len(kept) == len(slow)


def _days(n: int) -> list[str]:
    return [(T0 + timedelta(days=d)).date().isoformat() for d in range(n)]


def test_pit_a_post_counts_on_its_first_seen_day_and_never_before() -> None:
    late = _p(1, "日経平均が上昇", T0 + timedelta(days=2, hours=5))
    rows = sm.daily_index([late], observed_days=_days(4))
    jpn = {r.day: r for r in rows if r.instrument == "JPN225"}
    assert jpn[_days(4)[2]].n_posts == 1 and jpn[_days(4)[1]].n_posts == 0
    assert jpn[_days(4)[2]].available_time == (T0 + timedelta(days=3)).date().isoformat() + \
        "T00:00:00+00:00"
    # Decision time before the post was first seen: the post does not exist yet.
    asof = sm.daily_index([late], observed_days=_days(4), asof=T0 + timedelta(days=2, hours=1))
    assert all(r.n_posts == 0 for r in asof)
    assert max(r.day for r in asof) == _days(4)[2]           # nothing past the decision day


def test_an_unobserved_day_is_absent_not_a_quiet_zero() -> None:
    rows = sm.daily_index([_p(1, "円安", T0)], observed_days=[_days(3)[0], _days(3)[2]])
    assert {r.day for r in rows} == {_days(3)[0], _days(3)[2]}


def test_deltas_use_only_prior_days_and_a_spike_reads_as_a_positive_z() -> None:
    posts = []
    n = 0
    for d in range(20):
        k = 2 + (d % 2)                                        # a steady crowd of 2-3 posts
        if d == 19:
            k = 30                                             # the spike
        for j in range(k):
            n += 1
            mood = "爆上げ" if d == 19 else ("上昇" if j % 2 else "下落")
            posts.append(_p(n, f"日経平均 {mood} {n} {'x' * (n % 7)}",
                            T0 + timedelta(days=d, minutes=j), author=f"u{n}"))
    rows = [r for r in sm.daily_index(posts, observed_days=_days(20)) if r.instrument == "JPN225"]
    assert all(math.isnan(r.attention_delta_z) for r in rows[: sm.TRAIL_MIN])
    last = rows[-1]
    assert last.attention_delta_z > 3.0
    assert last.mood_delta > 0 and last.attention_shock_signed > 3.0
    # A day's delta never uses the day itself: recomputing without the spike day leaves day 18
    # unchanged.
    rows_18 = [r for r in sm.daily_index([p for p in posts if p.first_seen_at < T0 +
                                          timedelta(days=19)], observed_days=_days(19))
               if r.instrument == "JPN225"]
    assert rows_18[-1].attention_delta_z == rows[-2].attention_delta_z


def _pub(i: int, title: str, published: datetime, seen: datetime, author: str,
         source: str) -> sm.Post:
    return sm.Post(source=source, ident=f"b{i}", title=title, first_seen_at=seen,
                   author=author, published_at=published)


def _distinct(k: int) -> str:
    words = ("円安", "決算", "配当", "半導体", "銀行株", "指数", "先物", "為替介入", "金利",
             "原油", "金価格", "日銀", "米国債", "雇用統計", "物価", "新興株", "商社", "自動車",
             "海運", "不動産")
    return f"{words[k % len(words)]}について{'の' * (k // len(words))}メモ"


def test_a_blog_feed_of_twenty_posts_over_twenty_days_in_one_fetch_survives() -> None:
    fetched = T0 + timedelta(days=21)                          # ONE fetch returns the whole feed
    for source in ("hatena_bookmark_search_rss", "ameblo_user_rss"):
        feed = [_pub(k, _distinct(k), T0 + timedelta(days=k), fetched, "kabu_blogger", source)
                for k in range(20)]
        kept, rep = sm.bot_filter(feed)
        assert rep.dropped["burst_account"] == 0 and len(kept) == 20, source


def test_a_real_burst_by_post_time_is_still_filtered() -> None:
    seen = [T0 + timedelta(hours=h) for h in range(sm.BURST_MAX + 2)]   # spread across fetches
    burst = [_pub(k, _distinct(k), T0 + timedelta(minutes=k), seen[k], "spam",
                  "dcinside_stock_gallery") for k in range(sm.BURST_MAX + 2)]
    kept, rep = sm.bot_filter(burst)
    assert rep.dropped["burst_account"] == sm.BURST_MAX + 2 and not kept


def test_single_author_feed_sources_are_the_configured_per_blog_sources() -> None:
    from libs.data import blog_social_sources as bss
    per_blog = {s.id for s in bss.SOURCES if "{id}" in s.url}
    assert per_blog == set(sm.SINGLE_AUTHOR_FEED_SOURCES)
    # exempt: a configured blog posting many times inside an hour is still one blog
    feed = [_pub(k, _distinct(k), T0 + timedelta(minutes=k), T0 + timedelta(hours=1),
                 "one_blog", "livedoor_user_rss") for k in range(20)]
    kept, rep = sm.bot_filter(feed)
    assert rep.dropped["burst_account"] == 0 and len(kept) == 20
