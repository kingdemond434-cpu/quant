"""Crowd-venue parsers against captured-shape fixtures, plus the two stop rules (429, walls).
No network: a live assertion fails when a site has a bad afternoon."""
# ruff: noqa: E501  (captured-shape fixtures are kept on one line each)
from __future__ import annotations

import io
import json
import urllib.error

import pytest

from libs.data import crowd_sources as C


@pytest.fixture(autouse=True)
def _fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    C.reset()
    monkeypatch.setattr(C.time, "sleep", lambda s: None)


def _stub(monkeypatch: pytest.MonkeyPatch, body: str) -> list[str]:
    calls: list[str] = []

    def get(url: str, **kw: object) -> str:
        calls.append(url)
        return body
    monkeypatch.setattr(C, "_get", get)
    return calls


def test_niconico_reads_title_description_and_tags(monkeypatch) -> None:
    _stub(monkeypatch, json.dumps({"meta": {"status": 200}, "data": [
        {"contentId": "sm1", "title": "金価格 仲値トレード", "description": "<b>検証</b>", "tags": "ゴールド FX"}]}))
    arts, err = C.niconico("金価格")
    assert err is None and arts[0].url.endswith("/sm1")
    assert "#ゴールド" in arts[0].snippet and "<b>" not in arts[0].snippet


def test_guba_jsonp_is_unwrapped_shape_tolerantly(monkeypatch) -> None:
    _stub(monkeypatch, 'cb({"result":{"gubaArticleWeb":[{"title":"黄金 夜盘 规律","content":"沪金 夜盘 开盘 后 回落",'
                       '"postId":"99","code":"au"}]}})')
    arts, err = C.guba("黄金")
    assert err is None and arts[0].title == "黄金 夜盘 规律" and "99" in arts[0].url


def test_tieba_parses_result_blocks(monkeypatch) -> None:
    _stub(monkeypatch, '<div class="s_post"><span class="p_title"><a href="/p/123?pid=4">黄金 日内</a></span>'
                       '<div class="p_content">伦敦金 美盘 开盘</div><a class="p_forum">黄金吧</a></div></div>')
    arts, err = C.tieba("黄金")
    assert err is None and arts[0].url == "https://tieba.baidu.com/p/123?pid=4"


def test_naver_board_titles(monkeypatch) -> None:
    _stub(monkeypatch, '<td class="title"><a href="/item/board_read.naver?code=132030&amp;nid=55&amp;st=" '
                       'title="금 선물 야간 갭">x</a></td>')
    arts, err = C.naver_board("132030")
    assert err is None and arts[0].title == "금 선물 야간 갭" and "nid=55" in arts[0].url


def test_fivech_subject_list(monkeypatch) -> None:
    _stub(monkeypatch, '<a href="1700000000/l50">1: 金先物スレ (512)</a>')
    arts, err = C.fivech("egg.5ch.net/stock")
    assert err is None and arts[0].title == "金先物スレ"
    assert arts[0].url == "https://egg.5ch.net/test/read.cgi/stock/1700000000/"


def test_discourse_search_json(monkeypatch) -> None:
    _stub(monkeypatch, json.dumps({"topics": [{"id": 7, "title": "Gold MCX expiry", "slug": "gold"}],
                                   "posts": [{"id": 1, "topic_id": 7, "post_number": 2, "blurb": "roll week"}]}))
    arts, err = C.discourse("tradingqna.com::gold")
    assert err is None and arts[0].url == "https://tradingqna.com/t/gold/7/2"
    assert C.discourse("nohost")[1]


def test_access_wall_stops_the_source_for_the_run(monkeypatch) -> None:
    calls = _stub(monkeypatch, "<html>百度安全验证</html>")
    arts, err = C.tieba("黄金")
    assert arts == [] and "access wall" in str(err)
    arts, err = C.tieba("白银")
    assert "stopped for this run" in str(err) and len(calls) == 1       # never retried


def test_http_429_stops_the_source_and_never_touches_another(monkeypatch) -> None:
    calls: list[str] = []

    def get(url: str, **kw: object) -> str:
        calls.append(url)
        raise urllib.error.HTTPError(url, 429, "Too Many", None, io.BytesIO(b""))  # type: ignore[arg-type]
    monkeypatch.setattr(C, "_get", get)
    assert C.discourse("a.test::gold")[0] == []
    assert "stopped for this run" in str(C.discourse("a.test::silver")[1])
    C.discourse("b.test::gold")                                           # another forum still tried
    assert len(calls) == 2


def test_charset_decoding_handles_shift_jis_and_euc_kr() -> None:
    assert C._decode("金".encode("cp932"), "text/html; charset=Shift_JIS") == "金"
    assert C._decode("금".encode("cp949"), "text/html; charset=EUC-KR") == "금"
