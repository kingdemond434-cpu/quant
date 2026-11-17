"""alt_proxies, cn_nbs_retail: the source URL is NBS's release LISTING, so a pass follows the
retail release links on it, reads the release's own year-less body sentence dated by its title,
and walks the paginated listing back for history.

Measured on the box 2026-11-11: the store stayed `{}` because the listing page was fetched and
parsed as if it were the release. Every page here is SYNTHETIC, shaped like the publisher's.
"""
from __future__ import annotations

import sys
import urllib.error
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import alt_proxies as A  # noqa: E402

NOW = datetime(2026, 11, 11, 3, tzinfo=UTC)
LISTING = "https://www.stats.gov.cn/sj/zxfb/"
NBS = ROOT / "tests" / "fixtures" / "alt_proxies" / "nbs_follow"

LIST_HTML = (NBS / "listing.html").read_bytes()
RELEASE_OCT = (NBS / "release_2026_10.html").read_bytes()
RELEASE_SEP = (NBS / "release_2026_09.html").read_bytes()


def test_the_release_body_is_read_with_the_year_its_title_gives() -> None:
    obs = {(o.series, o.period): o for o in A.parse_nbs_retail(RELEASE_OCT, A.Ctx())}
    assert obs[("retail_yoy", date(2026, 10, 31))].value == pytest.approx(2.9)
    assert obs[("retail_level_100m_cny", date(2026, 10, 31))].value == pytest.approx(46291)
    assert obs[("retail_yoy", date(2026, 10, 31))].published_at == datetime(2026, 11, 14, 2,
                                                                             tzinfo=UTC)
    assert len(obs) == 2                       # the 1—10月份 cumulative figure is never read


def test_a_year_to_date_title_dates_the_monthly_sentence_and_a_fall_is_negative() -> None:
    # the title form the box's 11-09 listing carries: `2026年1—9月份...`
    obs = {(o.series, o.period): o for o in A.parse_nbs_retail(RELEASE_SEP, A.Ctx())}
    assert obs[("retail_yoy", date(2026, 9, 30))].value == pytest.approx(-0.4)
    assert len(obs) == 2


def test_a_body_with_no_titled_year_is_not_guessed() -> None:
    untitled = (NBS / "release_2026_10.html").read_bytes().split(b"<p>10", 1)[1]
    untitled = b"<p>10" + untitled.split(b"</p>", 1)[0] + b"</p>"
    assert A.parse_nbs_retail(untitled, A.Ctx()) == []


def test_the_listing_itself_parses_nothing_and_names_the_retail_releases() -> None:
    assert A.parse_nbs_retail(LIST_HTML, A.Ctx()) == []
    links = A.follow_nbs_retail(LIST_HTML, LISTING)
    assert links == ["https://www.stats.gov.cn/sj/zxfb/202611/t20261114_1961768.html",
                     "https://www.stats.gov.cn/sj/zxfb/202610/t20261019_1965614.html"]


def test_follow_is_capped_and_never_leaves_the_listing_host() -> None:
    many = "".join(f'<a href="./r{i}.html">社会消费品零售总额 {i}</a>'
                   for i in range(10)).encode()
    assert len(A.follow_nbs_retail(many, LISTING)) == A.FOLLOW_MAX
    assert all(u.startswith("https://www.stats.gov.cn/") for u in A.follow_nbs_retail(
        LIST_HTML, LISTING))


def test_a_pass_follows_the_listing_into_the_store(tmp_path: Path) -> None:
    src = A.BY_ID["cn_nbs_retail"]
    assert src.terms == "confirmed" and src.follow is A.follow_nbs_retail
    pages = {
        src.url: LIST_HTML,
        "https://www.stats.gov.cn/sj/zxfb/202611/t20261114_1961768.html": RELEASE_OCT,
        "https://www.stats.gov.cn/sj/zxfb/202610/t20261019_1965614.html": RELEASE_SEP,
    }
    calls: list[str] = []

    def getter(url: str) -> tuple[bytes, str]:
        calls.append(url)
        if url.endswith("/robots.txt"):
            return b"User-agent: *\nDisallow: /admin/\n", "text/plain"
        return pages.get(url, b"<html><body>no releases here</body></html>"), "text/html"

    state: dict[str, object] = {}
    rec = A.collect(A.Paths(tmp_path / "desk"), src, state, NOW, fetch=True, fixtures=None,
                    deadline=1e18, getter=getter)
    assert rec["followed"] == 2 and rec["parsed"] == 4 and rec["errors"] == []
    assert rec["store_rows"] > 0
    # the listing, robots.txt once for the host, the two releases it named, then its first three
    # history pages
    assert calls == ([src.url, "https://www.stats.gov.cn/robots.txt", *list(pages)[1:]]
                     + [f"{LISTING}index_{k}.html" for k in (1, 2, 3)])
    assert rec["robots_skipped"] == 0
    assert state["sources"]["cn_nbs_retail"]["backfill_to"] == 3   # type: ignore[index]


def test_the_history_walk_holds_its_place_when_a_page_fails(tmp_path: Path) -> None:
    src = A.BY_ID["cn_nbs_retail"]

    def getter(url: str) -> tuple[bytes, str]:
        if url.endswith("/robots.txt"):
            raise urllib.error.HTTPError(url, 404, "nf", None, None)  # type: ignore[arg-type]
        if url.endswith("index_2.html"):
            raise OSError("reset")
        return b"<html></html>", "text/html"

    state: dict[str, object] = {"sources": {"cn_nbs_retail": {"backfill_to": 0}}}
    rec = A.collect(A.Paths(tmp_path / "desk"), src, state, NOW, fetch=True, fixtures=None,
                    deadline=1e18, getter=getter)
    assert rec["errors"]
    assert state["sources"]["cn_nbs_retail"]["backfill_to"] == 0   # type: ignore[index]


def test_the_history_walk_stops_at_its_depth() -> None:
    src = A.BY_ID["cn_nbs_retail"]
    sst = {"backfill_to": A.NBS_BACKFILL_PAGES}
    reqs = A.requests_for(src, NOW, sst)
    assert [r.url for r in reqs] == [src.url] and "backfill_to_next" not in sst


def _robots_pass(tmp_path: Path, robots: bytes | int) -> tuple[dict, list[str]]:
    src = A.BY_ID["cn_nbs_retail"]
    pages = {src.url: LIST_HTML,
             "https://www.stats.gov.cn/sj/zxfb/202611/t20261114_1961768.html": RELEASE_OCT,
             "https://www.stats.gov.cn/sj/zxfb/202610/t20261019_1965614.html": RELEASE_SEP}
    calls: list[str] = []

    def getter(url: str) -> tuple[bytes, str]:
        calls.append(url)
        if url.endswith("/robots.txt"):
            if isinstance(robots, int):
                raise urllib.error.HTTPError(url, robots, "x", None, None)  # type: ignore[arg-type]
            return robots, "text/plain"
        return pages.get(url, b"<html></html>"), "text/html"

    state: dict[str, object] = {}
    rec = A.collect(A.Paths(tmp_path / "desk"), src, state, NOW, fetch=True, fixtures=None,
                    deadline=1e18, getter=getter)
    return rec, calls


def test_a_release_path_robots_disallows_is_skipped_and_counted(tmp_path: Path) -> None:
    rec, calls = _robots_pass(tmp_path, b"User-agent: *\nDisallow: /sj/zxfb/202611/\n")
    assert "https://www.stats.gov.cn/sj/zxfb/202611/t20261114_1961768.html" not in calls
    assert "https://www.stats.gov.cn/sj/zxfb/202610/t20261019_1965614.html" in calls
    assert rec["robots_skipped"] == 1 and rec["followed"] == 1


def test_robots_naming_this_organ_is_obeyed(tmp_path: Path) -> None:
    rec, calls = _robots_pass(tmp_path, b"User-agent: quant-desk-alt-proxies\nDisallow: /\n")
    assert calls[:2] == [A.BY_ID["cn_nbs_retail"].url, "https://www.stats.gov.cn/robots.txt"]
    assert len(calls) == 2 and rec["followed"] == 0 and rec["robots_skipped"] == 5


@pytest.mark.parametrize("code", [401, 403, 429, 451])
def test_a_refused_robots_file_stops_the_host_for_the_pass(tmp_path: Path, code: int) -> None:
    rec, calls = _robots_pass(tmp_path, code)
    assert len(calls) == 2 and rec["followed"] == 0
    assert any(e.startswith("robots stop") for e in rec["errors"])


@pytest.mark.parametrize("code", [500, 503])
def test_an_unreadable_robots_file_is_never_a_yes(tmp_path: Path, code: int) -> None:
    rec, calls = _robots_pass(tmp_path, code)
    assert len(calls) == 2 and any(e.startswith("robots unread") for e in rec["errors"])


@pytest.mark.parametrize("code", [404, 410])
def test_an_absent_robots_file_allows(tmp_path: Path, code: int) -> None:
    rec, _ = _robots_pass(tmp_path, code)
    assert rec["followed"] == 2 and rec["robots_skipped"] == 0 and rec["errors"] == []


@pytest.mark.parametrize("body", [
    b"<!DOCTYPE html><html><head><title>Just a moment...</title></head></html>",
    b"<html><body><script src='/cdn-cgi/challenge-platform/x.js'></script></body></html>",
    b"Please complete the CAPTCHA to continue"])
def test_a_challenge_page_served_as_robots_txt_is_never_a_yes(tmp_path: Path, body: bytes) -> None:
    rec, calls = _robots_pass(tmp_path, body)
    assert len(calls) == 2 and rec["followed"] == 0
    assert any(e.startswith("robots unread") for e in rec["errors"])
