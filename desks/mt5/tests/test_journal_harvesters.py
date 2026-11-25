"""The non-English paper readers: OAI-PMH, J-STAGE and OpenAlex parsing, the incremental walk,
the terms and robots stops, and the registry rows the yield rule funds."""
# ruff: noqa: RUF001, S105, S106 -- foreign-language fixtures; "token" is a resumption token
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK), str(DESK / "side_channels")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from side_channels import journal_harvesters as jh  # noqa: E402

from research import source_registry as sr  # noqa: E402

DAY = date(2026, 11, 25)
OAI = ('<?xml version="1.0"?><OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">'
       '<ListRecords>{records}{token}</ListRecords></OAI-PMH>')


def _rec(ident: str, title: str, subject: str = "", desc: str = "", prefix: str = "oai_dc",
         deleted: bool = False, extra: str = "") -> str:
    head = (f'<header{" status=" + chr(34) + "deleted" + chr(34) if deleted else ""}>'
            f"<identifier>{ident}</identifier><datestamp>2026-11-21</datestamp></header>")
    if deleted:
        return f"<record>{head}</record>"
    return (f"<record>{head}<metadata><{prefix}:dc xmlns:{prefix}=\"urn:x\" "
            f'xmlns:dc="http://purl.org/dc/elements/1.1/">{title}'
            f"<dc:creator>Kim</dc:creator><dc:subject>{subject}</dc:subject>"
            f"<dc:description>{desc}</dc:description>{extra}</{prefix}:dc></metadata></record>")


def _page(*records: str, token: str = "") -> str:
    tok = f"<resumptionToken>{token}</resumptionToken>" if token else ""
    return OAI.format(records="".join(records), token=tok)


def row(source, kind, title, url="", text="", symbols=None, **extra):
    return {"source": source, "kind": kind, "title": title, "url": url, "text": text,
            "symbols": symbols or [], **extra}


def allow(_name, _url):
    return True, "PUBLIC", "allowed"


class Net:
    """A scripted transport: each call pops the next answer and records the URL."""

    def __init__(self, *answers):
        self.answers, self.urls = list(answers), []

    def __call__(self, url):
        self.urls.append(url)
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a


def H(**kw):
    base = {"name": "kci", "region": "kr", "language": "ko", "route": "oai_pmh",
            "protocol": "oai_pmh", "base": "https://open.kci.go.kr/oai/request",
            "sets": ["ARTI"], "granularity": "day", "terms": "open", "terms_page_read": True,
            "max_requests": 4}
    return {**base, **kw}


# ------------------------------------------------------------------------------- parsing
def test_oai_reads_both_dc_prefixes_and_skips_deleted_records():
    kci = _rec("oai:kci.go.kr:ARTI/1", '<dc:title lang="original">환율 변동성</dc:title>'
               '<dc:title lang="english">Exchange rate volatility</dc:title>', "경제학",
               "We study the won.", extra='<dc:identifier type="artiId">ART1</dc:identifier>'
               '<dc:identifier type="doi">http://dx.doi.org/10.1/x</dc:identifier>')
    scielo = _rec("oai:scielo:S1", "<dc:title><![CDATA[Tipo de cambio y oro]]></dc:title>",
                  "<![CDATA[oro]]>", "<![CDATA[Resumen]]>", prefix="oai-dc",
                  extra="<dc:identifier>http://www.scielo.org.mx/scielo.php?pid=S1</dc:identifier>")
    page = jh.parse_oai(_page(kci, scielo, _rec("oai:x:2", "", deleted=True), token="T1"))
    assert page["token"] == "T1" and page["error"] is None and len(page["records"]) == 2
    a, b = page["records"]
    assert a["titles"] == [("original", "환율 변동성"), ("english", "Exchange rate volatility")]
    assert a["url"] == "http://dx.doi.org/10.1/x" and a["subjects"] == ["경제학"]
    assert b["url"].startswith("http://www.scielo.org.mx/") and b["titles"][0][1] == \
        "Tipo de cambio y oro"


def test_oai_error_code_is_an_answer_and_html_is_not_data():
    doc = ('<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">'
           '<error code="noRecordsMatch">none</error></OAI-PMH>')
    assert jh.parse_oai(doc)["error"] == "noRecordsMatch"
    for wall in ("<!DOCTYPE html><html><title>Establishing a secure connection</title></html>",
                 "<html><body>challenge</body></html>", "Access denied", "<feed/>",
                 '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><OAI-PMH/>'):
        with pytest.raises(jh.NotData):
            jh.parse_oai(wall)


def test_jstage_entry_and_openalex_inverted_abstract():
    js = ('<feed xmlns="http://www.w3.org/2005/Atom" '
          'xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"><result><status>0</status>'
          "</result><opensearch:totalResults>569</opensearch:totalResults><entry>"
          "<article_title><en><![CDATA[Yen carry]]></en><ja><![CDATA[円キャリー]]></ja>"
          "</article_title><article_link><en>https://www.jstage.jst.go.jp/a</en></article_link>"
          "<author><ja><name>金子</name></ja></author><pubyear>2025</pubyear>"
          "<title>Yen carry</title></entry></feed>")
    page = jh.parse_jstage(js)
    assert page["total"] == 569 and page["records"][0]["titles"] == [("en", "Yen carry"),
                                                                     ("ja", "円キャリー")]
    assert page["records"][0]["url"] == "https://www.jstage.jst.go.jp/a"
    oa = json.dumps({"meta": {}, "results": [{
        "id": "https://openalex.org/W1", "doi": "https://doi.org/10.1/a", "title": "Курс рубля",
        "publication_date": "2026-11-02",
        "abstract_inverted_index": {"oil": [1], "Brent": [0], "prices": [2]},
        "primary_topic": {"display_name": "Monetary Policy"},
        "keywords": [{"display_name": "exchange rate"}],
        "primary_location": {"source": {"display_name": "Вопросы экономики"}}}]})
    rec = jh.parse_openalex(oa)
    assert rec["records"][0]["descriptions"] == ["Brent oil prices"]
    assert rec["records"][0]["subjects"] == ["Monetary Policy", "exchange rate"]
    with pytest.raises(jh.NotData):
        jh.parse_openalex("<html>wall</html>")


# ------------------------------------------------------------- topic screen and instruments
@pytest.mark.parametrize("text", [
    "Exchange rate pass-through", "Tipo de cambio real", "Taxa de câmbio e juros",
    "Taux de change et politique monétaire", "Валютный курс рубля", "為替レートの変動",
    "환율과 금리", "人民币汇率", "Wechselkurs und Zinsen"])
def test_market_terms_are_recognised_in_every_covered_language(text):
    assert jh.is_market(text)


@pytest.mark.parametrize("text", [
    "Linux cluster programming for high availability", "Acta botánica mexicana",
    "탈식민 해방 투쟁과 제국의 문화 정치", "Формирование правовой компетентности студентов",
    # everyday words that are market words only in a market phrase (measured on the first
    # live pass: 85 of 300 KCI records passed a bare-stem screen)
    "Black or white: a study", "El cambio climático y el mercado de trabajo", "Курс лекций",
    "선물 포장 디자인", "A Research on Iranian Tourism Resources and Culture",
    "Volatile organic compounds in coffee", "Student portfolio assessment"])
def test_other_disciplines_are_screened_out(text):
    assert not jh.is_market(text)


def test_instruments_map_to_mt5_symbols_and_never_to_an_exotic():
    assert jh.symbols_named("Цена на золото и нефть") == ["XAUUSD", "XTIUSD", "XBRUSD"]
    assert jh.symbols_named("円安と日経平均") == ["USDJPY", "JPN225"]
    assert jh.symbols_named("금값과 엔화") == ["XAUUSD", "USDJPY"]
    assert jh.symbols_named("El precio del oro y el maíz") == ["XAUUSD", "CORN"]
    assert jh.symbols_named("Курс рубля и тенге") == []
    universe = json.loads((DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
    for _pat, syms in jh.INSTRUMENTS:
        for s in syms:
            assert s in universe, s
            assert "exotic" not in str(universe[s]).lower(), s


# ------------------------------------------------------------------------------ the walk
def test_first_pass_asks_from_the_lookback_and_persists_the_resumption_token():
    hit = _rec("oai:1", "<dc:title>Exchange rate and gold</dc:title>",
               extra="<dc:identifier>https://x/1</dc:identifier>")
    miss = _rec("oai:2", "<dc:title>Botany of ferns</dc:title>")
    net = Net(_page(hit, miss, token="T1"))
    st: dict = {}
    out = jh.harvest(st, net, row, allow, config=[H(max_requests=1, lookback_days=14)],
                     today=DAY)
    assert "from=2026-11-11" in net.urls[0] and "set=ARTI" in net.urls[0]
    assert [r["title"] for r in out] == ["Exchange rate and gold"]
    assert out[0]["source"] == "kci" and out[0]["symbols"] == ["XAUUSD"]
    assert out[0]["region"] == "kr" and out[0]["feed"] == "kci"
    assert st["jh_cursor"]["kci"]["token"] == "T1"
    assert st["jh_status"]["kci"] == {**st["jh_status"]["kci"], "status": "ok", "items": 2,
                                      "new": 1, "screened_out": 1, "resuming": True}
    # the next pass resumes from the token, and a finished walk restarts from the day it began
    net2 = Net(_page(hit))
    assert jh.harvest(st, net2, row, allow, config=[H()], today=DAY) == []     # seen: no repeat
    assert "resumptionToken=T1" in net2.urls[0] and "from=" not in net2.urls[0]
    cur = st["jh_cursor"]["kci"]
    assert cur["token"] is None and cur["from"] == "2026-11-23" and cur["began"] == "2026-11-25"


def test_second_granularity_and_an_expired_token_restarts_the_page():
    bad = ('<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">'
           '<error code="badResumptionToken"/></OAI-PMH>')
    net = Net(bad, _page())
    st = {"jh_cursor": {"kci": {"from": "2026-11-20", "token": "OLD", "began": "2026-11-24"}}}
    jh.harvest(st, net, row, allow, config=[H(granularity="second", sets=None)], today=DAY)
    assert "resumptionToken=OLD" in net.urls[0]
    assert "from=2026-11-20T00%3A00%3A00Z" in net.urls[1] and "set=" not in net.urls[1]


def test_journal_sets_are_chosen_by_name_cached_and_walked_in_turn():
    sets = ('<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><ListSets>'
            "<set><setSpec>1111-1111</setSpec><setName><![CDATA[Acta botánica]]></setName></set>"
            "<set><setSpec>2222-2222</setSpec><setName>El trimestre económico</setName></set>"
            "<set><setSpec>3333-3333</setSpec><setName>Contaduría y administración</setName>"
            "</set></ListSets></OAI-PMH>")
    h = H(name="scielo_mx", sets=None, set_name_match="econ|contad", max_requests=3)
    net = Net(sets, _page(), _page())
    st: dict = {}
    jh.harvest(st, net, row, allow, config=[h], today=DAY)
    assert "verb=ListSets" in net.urls[0]
    assert "set=2222-2222" in net.urls[1] and "set=3333-3333" in net.urls[2]
    assert st["jh_cursor"]["scielo_mx"]["sets"] == ["2222-2222", "3333-3333"]
    net2 = Net(_page(), _page())
    jh.harvest(st, net2, row, allow, config=[h], today=DAY)
    assert all("ListSets" not in u for u in net2.urls)              # cached for a week


def test_openalex_walks_by_language_by_page_number_with_no_key_and_no_cursor():
    h = H(name="openalex_ja", protocol="openalex", route="api", language="ja", region="jp",
          base="https://api.openalex.org/works", sets=None, max_requests=3, page_size=1)
    page = json.dumps({"meta": {"next_cursor": "C2"}, "results": [
        {"id": "W1", "title": "円安と為替介入の効果", "doi": "https://doi.org/10.1/a",
         "abstract_inverted_index": {"coffee": [0]}}]})
    net = Net(page, json.dumps({"meta": {}, "results": []}))
    st: dict = {}
    out = jh.harvest(st, net, row, allow, config=[h], today=DAY)
    assert "language:ja,primary_topic.field.id:20,from_publication_date:2026-10-26" in net.urls[0]
    assert "page=1" in net.urls[0] and "page=2" in net.urls[1] and len(net.urls) == 2
    joined = "".join(net.urls)                  # a cursor needs a key bound to an email address
    assert "cursor" not in joined and "api_key" not in joined and "mailto" not in joined
    assert out[0]["symbols"] == ["USDJPY"] and out[0]["source"] == "openalex_ja"
    assert st["jh_cursor"]["openalex_ja"]["token"] is None          # walk finished, restarts


def test_the_abstract_is_read_only_where_the_record_is_already_economics():
    plain = _rec("oai:1", "<dc:title>Festival tourism</dc:title>", "관광학",
                 "Visitors discuss the exchange rate and gold price.")
    econ = _rec("oai:2", "<dc:title>Household behaviour</dc:title>", "경제학",
                "We estimate the exchange rate pass-through to coffee prices.")
    out = jh.harvest({}, Net(_page(plain, econ)), row, allow, config=[H()], today=DAY)
    assert [r["title"] for r in out] == ["Household behaviour"]
    assert out[0]["symbols"] == []              # instruments come from title and keywords only


# ------------------------------------------------------------------------------ the stops
def test_a_source_whose_terms_are_not_open_is_never_fetched():
    net = Net()
    st: dict = {}
    for terms in ("refused", "unrecorded", None):
        assert jh.harvest(st, net, row, allow, config=[H(terms=terms)], today=DAY) == []
        assert st["jh_status"]["kci"]["status"] == "closed"
    assert net.urls == []


def test_open_on_terms_nobody_read_fails_closed_in_the_reader_and_the_registry(tmp_path):
    net = Net()
    st: dict = {}
    for unread in (False, None, "true", 1):
        assert jh.harvest(st, net, row, allow, config=[H(terms_page_read=unread)],
                          today=DAY) == []
        assert st["jh_status"]["kci"]["status"] == "closed"
        assert "never read" in st["jh_status"]["kci"]["why"]
    assert net.urls == []
    p = tmp_path / "feeds.json"
    p.write_text(json.dumps({"harvesters": [H(terms_page_read=False), H(name="ok")]}))
    rows: dict = {}
    sr._paper_rows(rows, p)
    assert rows["src:paper:kci"]["licence_note"].startswith("CLOSED (terms unread)")
    assert rows["src:paper:kci"]["paper_terms"] == "unread"
    assert rows["src:paper:ok"]["paper_terms"] == "open"


def test_no_shipped_harvester_is_open_without_a_terms_page_that_was_read():
    for h in jh.load_harvesters():
        if h["terms"] == "open":
            assert h["terms_page_read"] is True, h["name"]
            assert jh.is_open(h), h["name"]
        else:
            assert not jh.is_open(h), h["name"]


def test_a_robots_stop_makes_no_fetch_and_a_bot_wall_is_not_parsed_or_retried():
    net = Net()
    st: dict = {}

    def deny(_n, _u):
        return False, "DISALLOWED", "robots.txt disallows this exact path"
    assert jh.harvest(st, net, row, deny, config=[H()], today=DAY) == []
    assert net.urls == [] and st["jh_status"]["kci"]["status"] == "set_aside"
    wall = Net("<!DOCTYPE html><html><title>Establishing a secure connection</title></html>")
    out = jh.harvest(st, wall, row, allow, config=[H(name="scielo_br")], today=DAY)
    assert len(wall.urls) == 1 and st["jh_status"]["scielo_br"]["status"] == "not_data"
    assert out[0]["kind"] == "fetch_error" and out[0]["needs_selector_work"] is True


def test_a_403_or_429_stops_every_other_source_on_that_host_for_the_pass():
    class Refused(Exception):
        response = type("R", (), {"status_code": 429})()

    oa = {"protocol": "openalex", "route": "api", "sets": None,
          "base": "https://api.openalex.org/works"}
    cfg = [H(name="openalex_ja", language="ja", **oa), H(name="openalex_ko", **oa),
           H(name="kci")]
    net = Net(Refused("429 Too Many Requests"), _page())
    st: dict = {}
    jh.harvest(st, net, row, allow, config=cfg, today=DAY)
    assert st["jh_status"]["openalex_ja"]["status"] == "error"
    assert st["jh_status"]["openalex_ko"]["status"] == "deferred"
    assert st["jh_status"]["kci"]["status"] == "empty" and len(net.urls) == 2


def test_the_pass_deadline_defers_the_rest_visibly():
    ticks = iter([0.0, 0.0, 9999.0, 9999.0])
    net = Net(_page())
    st: dict = {}
    jh.harvest(st, net, row, allow, config=[H(), H(name="scielo_mx")], today=DAY,
               clock=lambda: next(ticks), deadline_s=600)
    assert st["jh_status"]["scielo_mx"]["status"] == "deferred"


def test_the_production_gate_bills_a_stop_and_counts_an_absent_robots(monkeypatch):
    from research import robots_gate
    calls: list = []
    labels = {"https://a.example/x": (robots_gate.DISALLOWED, "no"),
              "https://b.example/x": (robots_gate.ROBOTS_ABSENT, "404"),
              "https://c.example/x": (robots_gate.PUBLIC, "ok")}
    monkeypatch.setattr(robots_gate, "read", lambda url, agent, cache=None: labels[url])
    monkeypatch.setattr(robots_gate, "refuse", lambda *a, **k: calls.append(("refuse", a[1])))
    monkeypatch.setattr(robots_gate, "note_absent",
                        lambda *a, **k: calls.append(("absent", a[1])))
    gate = jh.robots_gate_for_pass()
    assert gate("s1", "https://a.example/x")[0] is False
    assert gate("s2", "https://b.example/x")[0] is True
    assert gate("s3", "https://c.example/x")[0] is True
    assert calls == [("refuse", "s1"), ("absent", "s2")]


# ------------------------------------------------------------------------ shipped config
def test_every_shipped_harvester_is_complete_and_a_refusal_carries_its_clause():
    hs = jh.load_harvesters()
    names = [h["name"] for h in hs]
    assert len(names) == len(set(names))
    for want in ("kci", "scielo_mx", "scielo_br", "repec_oai", "hal", "cyberleninka", "jstage",
                 "openalex_ja", "openalex_ru", "openalex_fr", "openalex_ko"):
        assert want in names, want
    for h in hs:
        assert h["region"] and h["language"] and h["base"].startswith("http"), h["name"]
        assert h["route"] in ("oai_pmh", "api") and h["protocol"] in ("oai_pmh", "jstage",
                                                                      "openalex")
        assert h["terms"] in ("open", "refused", "unrecorded") and h["terms_url"], h["name"]
        assert len(h["terms_note"]) > 40, h["name"]
        if h["terms"] == "refused":
            assert h["terms_page_read"] is True, h["name"]      # a refusal is never a guess
        assert "api_key" not in json.dumps(h) and "mailto" not in json.dumps(h)
    closed = {h["name"] for h in hs if h["terms"] != "open"}
    assert closed == {"hal", "cyberleninka", "jstage", "kci"}
    kci = next(h for h in hs if h["name"] == "kci")
    assert kci["terms"] == "unrecorded" and "NOT READ" in kci["terms_note"]


def test_each_harvester_is_a_registry_row_the_compiler_stamp_resolves_to():
    rows: dict = {}
    sr._paper_rows(rows)
    idx = sr._index(rows)
    for h in jh.load_harvesters():
        r = rows[f"src:paper:{h['name']}"]
        assert r["region"] == h["region"] and r["language"] == h["language"]
        assert r["route"] == h["route"] and r["kind"] == "scholarly"
        assert r["cost"] is not None and r["fetch_clock"] == sr.CLOCK_PAPERS
        assert sr._resolve(f"miner:{h['name']}", rows, idx) == f"src:paper:{h['name']}"
        assert r["licence_note"].startswith("CLOSED") == (h["terms"] != "open")
    assert sr.SEAT_KIND["global_journals"] == "scholarly"


def test_a_closed_source_closes_no_language_gap_and_an_open_one_does():
    rows: dict = {}
    sr._paper_rows(rows)
    only = lambda *names: {k: v for k, v in rows.items() if v["name"] in names}  # noqa: E731
    assert "ja" in sr.language_map(only("jstage"))[1]
    assert "ja" not in sr.language_map(only("jstage", "openalex_ja"))[1]


def test_the_miner_is_registered_and_on_the_paper_clock():
    import seed_miners
    assert "global_journals" in seed_miners.MINERS
    cmd = (ROOT / "ops" / "run_research_feeds.cmd").read_text("utf-8")
    assert "global_journals" in cmd
    manifest = (DESK / "ops" / "box_tasks.manifest").read_text("utf-8")
    assert "desks/mt5/side_channels/journal_harvesters.py" in manifest
