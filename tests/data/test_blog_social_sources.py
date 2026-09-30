"""Part B fetchers on fixtures: RSS/RDF/Atom, the DCInside list page, Weibo and Xueqiu JSON, and
the posture a fetch reports. No network: every getter here is a fixture."""
# ruff: noqa: RUF001 -- the fixtures are Japanese, Korean and Chinese text.
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from libs.data import blog_social_sources as bss

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "nlp_blog_social"
NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)


def _spec(sid: str) -> bss.SourceSpec:
    return bss.BY_ID[sid]


def test_hatena_rdf_is_decoded_with_author_and_date() -> None:
    posts = bss.parse_body(_spec("hatena_bookmark_search_rss"),
                           (FIX / "hatena_search.rdf").read_text("utf-8"), NOW)
    assert posts[0].title == "円安が止まらない、ドル円爆上げ"   # entities decoded
    assert posts[0].author == "fx_taro"
    assert posts[0].published_at == datetime(2026, 9, 29, 12, 15, tzinfo=UTC)
    assert all(p.first_seen_at == NOW for p in posts)         # the PIT clock is the fetch


def test_rss20_and_atom_parse() -> None:
    ame = bss.parse_body(_spec("ameblo_user_rss"), (FIX / "ameblo_rss20.xml").read_text("utf-8"),
                         NOW)
    assert ame[0].title == "日経225、反発で買い増し" and ame[0].author == "example-kabu"
    assert ame[0].published_at == datetime(2026, 9, 29, 3, 30, tzinfo=UTC)
    atom = bss.parse_rss((FIX / "atom_feed.xml").read_text("utf-8"), "x", "zh", NOW)
    assert atom[0].url == "https://note.example/n/abc123" and atom[0].author == "hk_trader"


def test_dcinside_list_keeps_writer_and_kst_time_and_skips_notices() -> None:
    posts = bss.parse_body(_spec("dcinside_stock_gallery"),
                           (FIX / "dcinside_list.html").read_text("utf-8"), NOW)
    assert [p.ident for p in posts] == ["1001", "1002"]
    assert posts[0].author == "개미@121.130" and posts[1].author == "stockbro77"
    assert posts[0].published_at == datetime(2026, 9, 30, 1, 15, 22, tzinfo=UTC)   # KST - 9h


def test_weibo_and_xueqiu_json() -> None:
    wb = bss.parse_body(_spec("weibo_mobile_search"),
                        (FIX / "weibo_search.json").read_text("utf-8"), NOW)
    assert len(wb) == 2 and "<a" not in wb[0].title and wb[1].author == "5550002"
    assert wb[0].published_at == datetime(2026, 9, 30, 1, 12, tzinfo=UTC)
    xq = bss.parse_body(_spec("xueqiu_status_search"),
                        (FIX / "xueqiu_search.json").read_text("utf-8"), NOW)
    assert [p.title for p in xq] == ["恒生指数反弹，港股看多", "沪指大跌，熊市来了"]


def test_fetch_reports_ok_walled_and_unconfigured_postures() -> None:
    body = (FIX / "hatena_search.rdf").read_text("utf-8")
    ok = bss.fetch(_spec("hatena_hotentry_economics_rss"), NOW, get=lambda url: body, pause_s=0)
    assert ok["posture"] == bss.POSTURE_OK and ok["n"] == 2

    def refuse(url: str) -> str:
        raise OSError("Tunnel connection failed: 403 Forbidden")

    walled = bss.fetch(_spec("weibo_mobile_search"), NOW, get=refuse, pause_s=0)
    assert walled["posture"] == bss.POSTURE_WALLED and "403" in walled["errors"][0]
    assert walled["calls"] == len(bss.KEYWORDS["zh"])
    none = bss.fetch(_spec("ameblo_user_rss"), NOW, get=lambda url: body, pause_s=0)
    assert none["posture"] == "UNCONFIGURED"
    fed = bss.fetch(_spec("ameblo_user_rss"), NOW, get=lambda url: body, feed_ids=["a", "b"],
                    pause_s=0)
    assert fed["calls"] == 2 and fed["posture"] == bss.POSTURE_OK


def test_every_source_carries_the_roster_schema() -> None:
    for s in bss.SOURCES:
        assert s.region in ("JP", "KR", "CN") and s.lang in ("ja", "ko", "zh")
        assert s.failure_mode_hypothesis and s.participant_structure
        assert s.crowding_prior in ("low", "medium", "high")
