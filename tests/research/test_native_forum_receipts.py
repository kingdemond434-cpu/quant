"""Native search parsing must distinguish receipts, empty results and blocked routes."""
import json
from urllib.error import HTTPError

import pytest

from libs.data import foreign_sources as fs


@pytest.fixture(autouse=True)
def isolated_transport(monkeypatch):
    monkeypatch.setattr(fs, "_pace", lambda _: None)
    monkeypatch.setattr(fs, "_BACKED_OFF", set())


@pytest.mark.parametrize("name", ["note", "velog", "vcru", "coinpan", "smartlab",
                                  "tinhte", "eksisozluk"])
def test_rate_limit_stops_subsequent_requests(name, monkeypatch):
    calls = []

    def denied(*args):
        calls.append(args)
        raise HTTPError("https://fixture.invalid", 429, "rate limited", {}, None)

    monkeypatch.setattr(fs, "_get", denied)
    monkeypatch.setattr(fs, "_post", denied)
    rows, error = getattr(fs, name)("MT5")
    assert rows == [] and error
    assert name in fs._BACKED_OFF
    assert getattr(fs, name)("USDJPY")[0] == []
    assert len(calls) == 1


@pytest.mark.parametrize("name", ["note", "velog", "vcru"])
@pytest.mark.parametrize("raw", ["not json", "[]", "{}"])
def test_json_failure_is_not_measured_empty(name, raw, monkeypatch):
    monkeypatch.setattr(fs, "_get", lambda _: raw)
    monkeypatch.setattr(fs, "_post", lambda *_: raw)
    rows, error = getattr(fs, name)("MT5")
    assert rows == [] and error


@pytest.mark.parametrize("envelope", ["contents", "list"])
def test_note_native_title_and_original_receipt(envelope, monkeypatch):
    rows = [None, {}, {"name": "<b>先読み</b> &amp; 検証", "key": "n123",
                      "user": {"urlname": "botter"}, "description": "x" * 400},
            {"name": "EA", "id": 9, "noteUrl": "https://note.com/original", "user": None}]
    payload = {"data": {"notes": {"contents": rows} if envelope == "contents" else rows}}
    monkeypatch.setattr(fs, "_get", lambda _: json.dumps(payload))
    articles, error = fs.note("MT5", limit=3)
    assert error is None and len(articles) == 2
    assert articles[0].title == "先読み & 検証"
    assert articles[0].url == "https://note.com/botter/n/n123"
    assert articles[0].author == "botter" and len(articles[0].snippet) == 360
    assert articles[1].url == "https://note.com/original"


def test_velog_graphql_request_and_fallback_receipt(monkeypatch):
    requests = []

    def response(url, body):
        requests.append((url, json.loads(body)))
        return json.dumps({"data": {"searchPosts": {"posts": [None, {},
            {"id": "1", "title": "<b>검증</b>", "url_slug": "mt5",
             "user": {"username": "quant"}, "short_description": "&amp;"},
            {"id": "2", "title": "EA", "user": None}]}}})

    monkeypatch.setattr(fs, "_post", response)
    articles, error = fs.velog("MT5 EA", limit=7)
    assert error is None and len(articles) == 2
    assert requests[0][1]["variables"] == {"keyword": "MT5 EA", "offset": 0, "limit": 7}
    assert articles[0].url == "https://velog.io/@quant/mt5"
    assert articles[0].title == "검증" and articles[0].snippet == "&"
    assert articles[1].url.endswith("q=MT5%20EA")
    monkeypatch.setattr(fs, "_post", lambda *_: '{"errors":[{"message":"denied"}]}')
    assert "GraphQL errors" in fs.velog("MT5")[1]


@pytest.mark.parametrize("envelope", ["items", "result_dict", "result_list"])
def test_vcru_envelopes_preserve_native_identifiers(envelope, monkeypatch):
    rows = [None, {}, {"data": {"id": 17, "title": "<b>Проверка</b>", "intro": "&amp;"}},
            {"id": 18, "title": "MT5", "url": "https://vc.ru/custom", "data": None}]
    doc = {"items": rows} if envelope == "items" else {
        "result": {"items": rows} if envelope == "result_dict" else rows}
    monkeypatch.setattr(fs, "_get", lambda _: json.dumps(doc))
    articles, error = fs.vcru("MT5")
    assert error is None and [a.ident for a in articles] == ["17", "18"]
    assert articles[0].title == "Проверка" and articles[0].snippet == "&"
    assert articles[1].url == "https://vc.ru/custom"


@pytest.mark.parametrize("name,href,title,empty", [
    ("coinpan", "/free?document_srl=17", "검증", "검색결과 내용이 없습니다"),
    ("smartlab", "https://smart-lab.ru/blog/17.php", "Проверка", "ничего не найдено"),
    ("tinhte", "/threads/mt5.17/", "kiểm tra", "không có kết quả"),
    ("eksisozluk", "/mt5--17", "doğrulama", None),
])
def test_html_receipts_deduplicate_and_do_not_hide_route_failure(
        name, href, title, empty, monkeypatch):
    html = f'<a href="{href}"><b>{title}</b> &amp; MT5</a>'
    html += html + f'<a href="{href.replace("17", "18")}"></a>'
    monkeypatch.setattr(fs, "_get", lambda _: html)
    articles, error = getattr(fs, name)("MT5")
    assert error is None and len(articles) == 1
    assert articles[0].ident == "17" and articles[0].title == f"{title} & MT5"
    assert articles[0].url.startswith("https://")
    monkeypatch.setattr(fs, "_get", lambda _: "<html>challenge</html>")
    assert getattr(fs, name)("MT5")[1]
    if empty:
        monkeypatch.setattr(fs, "_get", lambda _: empty)
        assert getattr(fs, name)("MT5") == ([], None)


def test_promoted_smartlab_sidebar_is_not_a_search_result(monkeypatch):
    monkeypatch.setattr(fs, "_get", lambda _: (
        '<a href="https://smart-lab.ru/company/promo/blog/17.php">MT5</a>'))
    articles, error = fs.smartlab("MT5")
    assert articles == [] and "ROUTING" in error


def test_probe_health_delivers_three_distinct_postures(monkeypatch):
    def raises(_):
        raise ValueError("broken parser")

    article = fs.Article("receipt", "17", "MT5", "https://fixture.invalid/17")
    monkeypatch.setattr(fs, "SOURCES", {
        "receipt": (lambda _: ([article], None), "ja"),
        "empty": (lambda _: ([], None), "ja"),
        "walled": (lambda _: ([], "403"), "ja"),
        "broken": (raises, "ja"),
    })
    records = {r["source"]: r for r in fs.probe_all()}
    assert records["receipt"]["posture"] == fs.POSTURE_OK
    assert records["receipt"]["ok"] and records["receipt"]["n"] == 1
    assert records["empty"]["posture"] == fs.POSTURE_EMPTY
    for name in ("walled", "broken"):
        assert records[name]["posture"] == fs.POSTURE_WALLED
        assert not records[name]["ok"] and records[name]["error"]
