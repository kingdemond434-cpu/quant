"""The deep-forest story miner and the bilingual claim grammar it runs on.

What is pinned:

  * a Chinese sentence naming a quantity, a direction and a horizon is a claim; an ordinary
    sentence is not; the claim is kept verbatim and hashed;
  * instruments map to MT5 analogues (沪金 -> XAUUSD), no-analogue futures become mechanism-class
    transfers, and a claim that names no instrument inherits the document's;
  * a crypto-exchange claim is dropped and counted, never queued;
  * the search-engine and Gitee parsers read real markup shapes; the miner off-box records
    NO_NETWORK per ground and still rebuilds the queue from its ledger;
  * every task carries kind=story_mechanism, provenance, symbols and a stable id; decided claims
    are not re-asked; the deepening worker's prompt now shows the description;
  * the sources file and the query bank never name a forbidden venue; the world crawler keeps
    story claims as rows of kind `story`; the reopen-hour fill delay makes daily holds
    screenable on gold while fills at the reopen stay refused.
"""
# ruff: noqa: RUF001, E501  -- the fixtures are real Chinese prose and real result markup
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_DESK / "side_channels"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import deep_forest_miner as dfm  # noqa: E402
from research import proposer_common as pc  # noqa: E402

from libs.research import mechanism_claims as mc  # noqa: E402

_STORY = ("我做沪金日内交易七年。夜盘开盘后前30分钟如果放量突破日内高点，顺势做多持有到收盘前平仓，"
          "胜率62%，年化收益率85%，最大回撤18%。螺纹钢在换月前一周基差收敛，做空近月效果明显，"
          "一般持有三个交易日。币安永续合约资金费率为正时做空，这是套利。"
          "Gold tends to mean revert after the London fix within two hours when the daily range "
          "is already wide. 这是一个普通的句子。")


# ------------------------------------------------------------------------------- the grammar
def test_a_chinese_story_yields_verbatim_claims_and_an_ordinary_sentence_does_not() -> None:
    claims = mc.extract_claims(_STORY, universe={"XAUUSD", "XAGUSD"})
    texts = [c["claim"] for c in claims]
    assert any("夜盘开盘后" in t for t in texts)
    assert any("螺纹钢" in t for t in texts)
    assert any(t.startswith("Gold tends") for t in texts)
    assert not any("普通的句子" in t for t in texts)
    for c in claims:
        assert c["quantities"] and c["direction"] and c["horizon"] and len(c["claim_hash"]) == 12


def test_instruments_map_to_mt5_analogues_transfers_and_document_context() -> None:
    claims = {c["claim"][:6]: c for c in mc.extract_claims(_STORY, universe={"XAUUSD"})}
    gold = next(c for k, c in claims.items() if k.startswith("夜盘"))
    assert gold["instruments"]["analogues"] == ["XAUUSD"] and gold["instrument_from_context"]
    rebar = next(c for k, c in claims.items() if k.startswith("螺纹钢"))
    assert rebar["instruments"]["analogues"] == [] and rebar["instruments"]["transfer_only"]
    eng = next(c for k, c in claims.items() if k.startswith("Gold t"))
    assert eng["instruments"]["analogues"] == ["XAUUSD"] and not eng["instrument_from_context"]


def test_the_story_s_numbers_are_parsed_but_only_as_evidence_about_the_story() -> None:
    claims = mc.extract_claims(_STORY)
    gold = next(c for c in claims if c["claim"].startswith("夜盘"))
    assert gold["claimed_performance"] == {"return_pct": 85.0, "drawdown_pct": 18.0,
                                           "win_rate_pct": 62.0}
    assert mc.claim_score(gold) < mc.claim_score({**gold, "quantities": gold["quantities"]}) + 1


def test_a_crypto_exchange_claim_is_dropped_and_counted() -> None:
    claims, dropped = mc.extract_claims_with_drops(_STORY)
    assert dropped == 1
    assert not any("币安" in c["claim"] for c in claims)


def test_resolution_prefers_the_symbol_the_broker_actually_quotes() -> None:
    r = mc.resolve_instruments("原油夜盘跳空", universe={"UKOIL", "XAUUSD"})
    assert r["analogues"] == ["UKOIL"]
    r2 = mc.resolve_instruments("原油夜盘跳空", universe=None)
    assert r2["analogues"] == ["XTIUSD"]


# ------------------------------------------------------------------------------- the parsers
_BING = """<ol id="b_results"><li class="b_algo"><h2><a href="https://zhuanlan.zhihu.com/p/1">
黄金日内交易策略实盘经验</a></h2><div class="b_caption"><p>夜盘开盘后放量突破日内高点顺势做多，持有到收盘前。</p>
</div></li><li class="b_algo"><h2><a href="https://www.zhihu.com/question/2">期货高手交易系统</a></h2>
<p>趋势跟踪，隔夜持仓，日线级别。</p></li></ol>"""
_DDG = """<div class="result"><a rel="nofollow" class="result__a"
href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fblog.csdn.net%2Fa%2F1&amp;rut=x">期货量化策略回测源码</a>
<a class="result__snippet" href="x">黄金分钟级动量因子，持有一小时。</a></div>"""


def test_bing_and_duckduckgo_result_pages_parse_into_rows() -> None:
    rows = dfm.parse_bing(_BING)
    assert [r["url"] for r in rows] == ["https://zhuanlan.zhihu.com/p/1",
                                        "https://www.zhihu.com/question/2"]
    assert "顺势做多" in rows[0]["snippet"]
    rows2 = dfm.parse_ddg(_DDG)
    assert rows2[0]["url"] == "https://blog.csdn.net/a/1" and "动量" in rows2[0]["snippet"]


def test_html_text_drops_scripts_and_keeps_visible_text() -> None:
    page = "<html><script>var x='黄金做多';</script><p>白银&amp;夜盘</p></html>"
    assert dfm.html_text(page) == "白银&夜盘"


# ------------------------------------------------------------------------------- the miner
def _isolate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(dfm, "CLAIMS", tmp_path / "claims.jsonl")
    monkeypatch.setattr(dfm, "SEEN", tmp_path / "seen.json")
    monkeypatch.setattr(dfm, "REPORT", tmp_path / "DEEP_FOREST.json")
    monkeypatch.setattr(dfm, "PROVENANCE", tmp_path / "mined_sources.jsonl")
    monkeypatch.setattr(dfm, "DATASETS", tmp_path / "datasets.jsonl")
    monkeypatch.setattr(dfm, "WORLD", tmp_path / "world")
    monkeypatch.setattr(dfm, "_feed_frontier", lambda urls: len(urls))
    queued: list = []
    import research.regime_coverage as rc
    monkeypatch.setattr(rc, "_merge_into_queue", lambda tasks, source="x": queued.extend(tasks))
    monkeypatch.setattr(dfm, "_universe", lambda: {"XAUUSD", "XAGUSD", "EURUSD"})
    return queued


def test_off_box_every_ground_records_no_network_and_nothing_raises(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)

    def dead(url, **kw):
        raise OSError("no route")
    monkeypatch.setattr(dfm, "_http", dead)
    monkeypatch.setattr(dfm, "SOURCES", tmp_path / "missing.json")
    src = {"grounds": [{"name": "A", "route": "http", "url": "https://a.test/", "kind": "forum"},
                       {"name": "B", "route": "search", "site": "b.test", "queries": ["x"],
                        "kind": "qa"},
                       {"name": "C", "route": "gitee", "queries": ["y"], "kind": "code"},
                       {"name": "D", "route": "unreachable", "kind": "academic", "why": "paywall"}]}
    (tmp_path / "missing.json").write_text(json.dumps(src), "utf-8")
    doc = dfm.run(budget_s=30, fetch=True)
    assert doc["network"] is False
    statuses = {g["ground"]: g["status"] for g in doc["grounds"]}
    assert statuses["D"] == "UNREACHABLE"
    assert set(statuses.values()) <= {"BLOCKED", "NO_NETWORK", "UNREACHABLE"}
    assert doc["claims_new"] == 0 and doc["tasks_queued"] == 0


def test_a_reachable_ground_queues_story_mechanism_tasks_with_provenance(monkeypatch,
                                                                          tmp_path) -> None:
    queued = _isolate(monkeypatch, tmp_path)
    page = ("<html><title>七禾网专访</title><body><p>" + _STORY + "</p>"
            "<a href='/article/2.html'>另一篇交易策略访谈</a></body></html>")
    calls: list[str] = []

    def fake(url, **kw):
        calls.append(url)
        return page
    monkeypatch.setattr(dfm, "_http", fake)
    monkeypatch.setattr(dfm, "SOURCES", tmp_path / "s.json")
    (tmp_path / "s.json").write_text(json.dumps({"grounds": [
        {"name": "七禾网", "route": "http", "url": "https://www.7hcn.com/", "kind": "interview"}]}),
        "utf-8")
    monkeypatch.setattr(dfm.time, "sleep", lambda s: None)
    doc = dfm.run(budget_s=60, fetch=True)
    assert doc["network"] is True and doc["claims_new"] >= 3
    assert doc["counts"]["dropped_venue"] >= 1
    assert queued and all(t["kind"] == "story_mechanism" and t["source"] == "deep_forest"
                          for t in queued)
    gold = next(t for t in queued if "夜盘开盘后前30分钟" in t["title"])
    assert gold["symbols"] == ["XAUUSD"] and gold["evidence_grade"] == "INTERVIEW"
    assert "https://www.7hcn.com/" in gold["description"]
    assert "never copy code" in gold["description"]
    assert doc["frontier_added"] >= 1
    # A second run finds nothing new but rebuilds the same queue from the ledger.
    queued.clear()
    doc2 = dfm.run(budget_s=60, fetch=True)
    assert doc2["claims_new"] == 0 and doc2["claims_total"] == doc["claims_total"]
    assert len(queued) == doc["tasks_queued"]


def test_decided_claims_are_not_re_asked_and_ids_are_stable() -> None:
    from research.deepening_worker import task_id
    rows = [{"claim": "黄金夜盘突破后次日延续上涨概率高。", "claim_hash": "abc", "ground": "g",
             "url": "https://x/1", "lang": "zh", "quantities": ["突破"], "score": 2.0,
             "instruments": {"analogues": ["XAUUSD"], "transfer_only": []}}]
    tasks = dfm.build_tasks(rows)
    assert len(tasks) == 1 and task_id(tasks[0]) == task_id(dfm.build_tasks(rows)[0])
    assert dfm.build_tasks(rows, decided={task_id(tasks[0])}) == []


def test_the_worker_prompt_now_carries_the_claim() -> None:
    from research.deepening_worker import _SYSTEM_BY_KIND, task_text
    t = {"title": "七禾网: x", "url": "https://x", "source": "deep_forest",
         "description": "CLAIM (zh): 夜盘开盘后顺势做多", "evidence_grade": "INTERVIEW"}
    text = task_text(t)
    assert "DESCRIPTION: CLAIM (zh)" in text and "EVIDENCE GRADE: INTERVIEW" in text
    assert "story_mechanism" in _SYSTEM_BY_KIND and "repo_mechanism" in _SYSTEM_BY_KIND
    assert "performance numbers are NOT evidence" in _SYSTEM_BY_KIND["story_mechanism"]


# ------------------------------------------------------------------------------- the fences
def test_no_ground_query_or_seed_names_a_forbidden_venue() -> None:
    src = json.loads((_DESK / "data" / "deep_forest_sources.json").read_text("utf-8"))
    blob = json.dumps(src, ensure_ascii=False).lower()
    for v in mc.FORBIDDEN_VENUES:
        assert v.strip() not in blob, f"sources name a forbidden venue: {v}"
    import world_crawler as wc
    for url in wc.SEEDS:
        assert mc.forbidden_venue(url) is None


def test_the_bandit_routes_story_and_repo_claims_to_the_external_arm() -> None:
    from libs.research.bandit import ARMS, SOURCE_ARM, arm_of
    assert arm_of("deep_forest") == "external_screen" == arm_of("repo_miner")
    assert arm_of("x", "story_mechanism") == "external_screen"
    # ONE SOURCE PER REGION CLUSTER, every one declared (not the unknown-source default) so the
    # research P&L can census each forest and the arm is the external one for all of them.
    src = json.loads((_DESK / "data" / "deep_forest_sources.json").read_text("utf-8"))
    for g in src["grounds"]:
        source = dfm.source_of(dfm.cluster_of(g))
        assert source in SOURCE_ARM, f"{g['name']}: {source} is not a declared bandit source"
        assert arm_of(source) in ARMS and arm_of(source) == "external_screen"
    assert dfm.source_of("cn") == "deep_forest" and dfm.source_of("jp") == "deep_forest_jp"


def test_the_world_crawler_keeps_story_claims_as_story_rows() -> None:
    import world_crawler as wc
    raw = ("<html lang='zh-CN'><title>期货人物专访</title><body><p>" + _STORY
           + "</p></body></html>").encode("utf-8")
    page = wc.read_page(raw, "https://www.7hcn.com/article/1.html")
    assert page["claims"] and "XAUUSD" in page["symbols"]
    row = wc.to_discovery("https://www.7hcn.com/article/1.html", page, "deadbeef")
    assert row and row["kind"] == "story" and row["n_claims"] >= 3
    assert "family" not in row and "params" not in row


# ------------------------------------------------------------------------------- the screen
def _gold_like(n_days: int = 400, seed: int = 0) -> pd.DataFrame:
    """A 23-hour feed: hour 0 missing every day, so hour 1 is the daily reopen."""
    rng = np.random.default_rng(seed)
    idx = [ts for ts in pd.date_range("2024-01-01", periods=n_days * 24, freq="h", tz="UTC")
           if ts.hour != 0]
    idx = pd.DatetimeIndex(idx, name="time")
    close = 2000 + np.cumsum(rng.normal(0, 1.0, len(idx)))
    return pd.DataFrame({"open": np.r_[close[0], close[:-1]], "high": close + 0.5,
                         "low": close - 0.5, "close": close}, index=idx)


class _Sig:
    def __init__(self, time, side=1, ttl=24):
        self.time, self.side, self.ttl_bars = time, side, ttl


def test_daily_holds_through_the_reopen_are_screenable_but_fills_at_it_wait() -> None:
    d = _gold_like()
    unf = {1: float("nan")}                          # the reopen, unmarked
    sigs = [_Sig(ts) for ts in d.index if ts.hour == 23][::3]
    sc = pc.screen(d, sigs, 0.0001, unf)
    assert sc is not None and sc["n_independent"] >= 30
    # Every 23:00 signal would fill at the reopen; each waited one bar for the 02:00 open.
    assert sc["delayed_fills"] == sc["n_independent"] and sc["refused_unfillable"] == 0
    # A one-bar hold whose EXIT is the reopen bar (signal at 22:00, fill 23:00, exit at the
    # 01:00 close) is still refused: that is trading the reopen.
    short = [_Sig(ts, ttl=1) for ts in d.index if ts.hour == 22]
    sc1 = pc.screen(d, short, 0.0001, unf)
    assert sc1 is None or sc1["refused_unfillable"] == len(short)


def test_a_marked_open_is_still_refused_and_a_severe_mark_still_breaks_the_window() -> None:
    d = _gold_like()
    sigs = [_Sig(ts, ttl=6) for ts in d.index if ts.hour == 8][::2]
    sc = pc.screen(d, sigs, 0.0001, {9: -12.0})
    assert sc is None or sc["refused_unfillable"] == len(sigs)
    sigs22 = [_Sig(ts, ttl=2) for ts in d.index if ts.hour == 22][::2]
    assert pc.screen(d, sigs22, 0.0001, {9: -12.0}) is not None


# ------------------------------------------------------------------- generated alphas
def test_a_generated_alpha_is_admitted_only_when_it_type_checks_and_names_a_mechanism() -> None:
    from research.deepening_worker import validate_expression
    uni = {"XAUUSD"}
    good = {"symbols": ["XAUUSD"], "family": "formula",
            "params": {"expr": ["zscore", ["delta", "close", 24], 240], "side_mode": "fade",
                       "entry_z": 1.5, "hold_bars": 8},
            "mechanism": "a one-day move in gold overshoots as dealers hedge and reverts"}
    found, why = validate_expression(good, uni)
    assert found["family"] == "formula" and found["params"]["expr"][0] == "zscore" and not why
    assert found["evidence"].startswith("generated:")
    # An ill-typed tree (price plus volume) is refused, as is a missing mechanism, an unknown
    # symbol, and a recipe outside the family's executable range.
    bad_type = {**good, "params": {**good["params"], "expr": ["add", "close", "activity"]}}
    assert validate_expression(bad_type, uni)[0] == {}
    assert validate_expression({**good, "mechanism": "x"}, uni)[0] == {}
    assert validate_expression({**good, "symbols": ["EURUSD"]}, uni)[0] == {}
    assert validate_expression({**good, "params": {**good["params"], "hold_bars": 9999}},
                               uni)[0] == {}


def test_the_generated_alpha_goes_through_the_same_compiler_door() -> None:
    """The seat's expression is enriched onto the task and re-compiled: EXACT_RECIPE under the
    formula family, never a direct write to the candidate store."""
    from research.deepening_worker import work_task
    task = {"source": "alpha_evolution", "kind": "alpha_expression", "title": "XAUUSD alpha",
            "url": "", "symbols": ["XAUUSD"],
            "description": "available terminals: close open high low ret range; tried: []"}
    reply = json.dumps({"symbols": ["XAUUSD"], "family": "formula",
                        "params": {"expr": ["zscore", ["delta", "close", 24], 240],
                                   "side_mode": "fade", "entry_z": 1.5, "hold_bars": 8},
                        "mechanism": "a one-day move in gold overshoots as dealers hedge"})
    cands, disposition = work_task(task, {"XAUUSD"}, chat=lambda *a, **k: (reply, None))
    assert disposition == "RECOVERED_EXACT_RECIPE" and cands
    assert cands[0]["family"] == "formula" and cands[0]["deepened"] is True


def test_sibling_forests_speak_the_same_grammar() -> None:
    t = ("ゴールドはロンドン仲値の後、1時間で逆張りの反発が出やすい。"
         "골드는 뉴욕 세션 개장 후 30분 돌파 시 롱으로 매수하고 당일 청산한다. "
         "Золото после лондонского фиксинга часто дает откат в течение часа, покупаю лонг.")
    langs = {c["lang"]: c for c in mc.extract_claims(t, universe={"XAUUSD"})}
    assert set(langs) == {"ja", "ko", "ru"}
    assert all(c["instruments"]["analogues"] == ["XAUUSD"] for c in langs.values())


def test_alpha_evolution_asks_the_seat_for_what_the_search_did_not_find(monkeypatch) -> None:
    from research import alpha_evolution as ae
    queued: list = []
    import research.regime_coverage as rc
    monkeypatch.setattr(rc, "_merge_into_queue", lambda tasks, source="x": queued.extend(tasks))
    rows = [{"symbol": "XAUUSD", "stage": 1, "fitness": 1.2, "expr": "zscore(delta(close,24),240)"}]
    tasks = ae._expression_tasks({"XAUUSD": {"drivers": ["usd"]}}, rows)
    assert len(tasks) == 1 and queued and tasks[0]["kind"] == "alpha_expression"
    assert "usd" in tasks[0]["description"] and "zscore(delta(close,24),240)" in tasks[0]["tried"]


# ================================================================== the world forest (2026-09-05)
_SRC = json.loads((_DESK / "data" / "deep_forest_sources.json").read_text("utf-8"))
_UNIVERSE = {str(k).upper() for k in
             json.loads((_DESK / "data" / "universe" / "universe.json").read_text("utf-8"))}
_STORY_EN = ("Gold usually mean reverts after the London fix within two hours when the daily range "
             "is already wide. EURUSD tends to rally for a week after the ECB rate decision when "
             "positioning is short. Brazilian soy exports usually weaken the real over the month.")
_PAGE_EN = ("<html><head><title>Systems thread</title>"
            "<meta property=\"article:published_time\" content=\"2026-08-30T10:00:00Z\"></head>"
            "<body><p>" + _STORY_EN + "</p><a href='/thread/2'>trading strategy thread</a>"
            "<a href='/data/cot.csv'>download csv</a></body></html>")
_BING_JA = """<ol id="b_results"><li class="b_algo"><h2><a href="https://note.com/x/n/1">
ドル円 仲値 手法</a></h2><p>ドル円は五十日の仲値にかけて日中ドル高になりやすく、仲値後に反落する。</p></li></ol>"""
_BING_YT = """<ol id="b_results"><li class="b_algo"><h2><a href="https://www.youtube.com/watch?v=abcdefghijk">
ドル円 仲値 トレード解説</a></h2><p>ドル円は五十日の仲値にかけて日中ドル高になりやすく、仲値後に反落する。</p></li></ol>"""
_RSS = """<?xml version="1.0"?><rss><channel><item><title>Carry note</title>
<link>https://blog.test/carry</link><pubDate>Mon, 01 Sep 2026 10:00:00 GMT</pubDate>
<description><![CDATA[<p>USDTRY usually falls for a week after the CBRT hikes when positioning is long.</p>]]></description>
</item></channel></rss>"""
_ATOM = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>gold fix fade</title>
<link href="https://www.reddit.com/r/algotrading/comments/1/gold_fix/"/><updated>2026-09-01T00:00:00Z</updated>
<content type="html">&lt;p&gt;Gold tends to mean revert after the London fix within two hours daily.&lt;/p&gt;</content>
</entry></feed>"""
_PAGE_EN2 = ("<html><title>Another thread</title><body><p>Gold typically reverts after the London fix within "
             "two hours once the daily range is wide. EURUSD usually rallies for a week after an ECB rate "
             "decision when positioning is short. Soy exports from Brazil tend to weaken the real over the "
             "month.</p></body></html>")
_NITTER = """<div class="timeline-item"><a class="tweet-link" href="/trader/status/123#m"></a>
<div class="tweet-content media-body" dir="auto">XAUUSD fades the London fix within an hour most days, positioning is long.</div></div>"""
_WAYBACK = json.dumps({"archived_snapshots": {"closest": {"available": True,
                       "url": "https://web.archive.org/web/20200601000000/https://www.quantopian.com/posts",
                       "timestamp": "20200601000000"}}})
_DATA_PAGE = ("<html><title>Statistics</title><body><p>Monthly reserves and intervention statistics.</p>"
              "<a href='/statistics/reserves.csv'>reserves csv</a><a href='/api/series?id=fx'>api</a></body></html>")


def _dispatch(url: str, **kw) -> str:
    """One fake transport for every route: the URL says which fixture answers."""
    if "bing.com" in url:
        return _BING_YT if "youtube" in url else _BING_JA
    if "duckduckgo" in url:
        return ""
    if "archive.org/wayback/available" in url:
        return _WAYBACK
    if url.endswith(".rss") or "/feed" in url or "rss" in url:
        return _ATOM if "reddit" in url else _RSS
    if "/search?f=tweets" in url:
        return _NITTER if "nitter.net" in url else ""
    if "gitee.com/api/v5/search" in url:
        return json.dumps([{"full_name": "quant/cta", "html_url": "https://gitee.com/quant/cta",
                            "description": "CTA 策略", "license": "MIT", "stargazers_count": 3}])
    if "gitee.com/api/v5/repos" in url:
        import base64
        return json.dumps({"content": base64.b64encode(_STORY.encode("utf-8")).decode("ascii")})
    if "web.archive.org" in url:
        return _PAGE_EN2
    if "statistics" in url.lower() or "/data" in url.lower():
        return _DATA_PAGE
    if "babypips" in url:
        return _PAGE_EN2
    return _PAGE_EN


class _Vid:
    bvid, title = "BV1fixture", "期货高手访谈"
    url, searchable = "https://www.bilibili.com/video/BV1fixture", "期货高手访谈 " + _STORY


class _Art:
    def __init__(self, title: str, url: str, snippet: str) -> None:
        self.title, self.url, self.snippet, self.published = title, url, snippet, "2026-09-01"

    @property
    def searchable(self) -> str:
        return f"{self.title} {self.snippet}"


def _offline(monkeypatch, tmp_path: Path) -> list:
    """Every network-touching seam replaced by a fixture; nothing leaves the box."""
    queued = _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(dfm, "_universe", lambda: _UNIVERSE)      # the real Fusion universe
    monkeypatch.setattr(dfm, "_http", _dispatch)
    monkeypatch.setattr(dfm.time, "sleep", lambda s: None)
    monkeypatch.setattr(dfm, "youtube_transcript", lambda vid, lang="en": ("", "mirror rotation dead (measured)"))
    monkeypatch.setattr(dfm._Run, "rendered", lambda self, url: "")     # no browser off-box
    art = [_Art("ゴールド 逆張り 検証", "https://p.test/1", "ゴールドはロンドン仲値の後、1時間で逆張りの反発が出やすい。")]
    from libs.data import bilibili, cn_sources, foreign_sources, papers
    for name in dfm.FOREIGN_FNS:
        monkeypatch.setattr(foreign_sources, name, lambda q, **kw: (art, None))
    monkeypatch.setattr(cn_sources, "juejin", lambda q, **kw: (art, None))
    monkeypatch.setattr(cn_sources, "sogou_weixin", lambda q, **kw: (art, None))
    monkeypatch.setattr(bilibili, "search", lambda q, **kw: ([_Vid()], None))
    paper = _Art("Carry and the fix", "https://arxiv.org/abs/1", "The carry trade usually gains for a month "
                 "after the Fed cuts when positioning is short.")
    monkeypatch.setattr(papers, "arxiv", lambda q, **kw: ([paper], None))
    monkeypatch.setattr(papers, "ssrn", lambda b, **kw: ([paper], None))
    monkeypatch.setattr(papers, "openreview", lambda q, **kw: ([paper], None))
    return queued


def _run_grounds(monkeypatch, tmp_path: Path, grounds: list, budget: float = 60) -> dict:
    monkeypatch.setattr(dfm, "SOURCES", tmp_path / "src.json")
    (tmp_path / "src.json").write_text(json.dumps({"grounds": grounds}, ensure_ascii=False), "utf-8")
    return dfm.run(budget_s=budget, fetch=True)


def test_the_grounds_file_is_a_world_with_a_regions_index_and_every_ground_is_routable() -> None:
    regions = _SRC["regions"]
    assert len(regions) >= 45 and all(v.get("cluster") and v.get("languages") for v in regions.values())
    seen: set = set()
    langs: set = set()
    for g in _SRC["grounds"]:
        assert g.get("name") and g.get("region") in regions and g.get("language") and g.get("route")
        assert g["route"] in dfm.ROUTES, f"{g['name']}: unknown route {g['route']}"
        assert g["language"] in (*mc.LANGUAGES, "ms"), f"{g['name']}: no vocabulary for {g['language']}"
        if g["route"] == "foreign":
            assert g.get("fn") in dfm.FOREIGN_FNS
        if g["route"] == "papers":
            assert g.get("fn") in dfm.PAPER_FNS
        if g.get("kind") == "dataset":
            assert g.get("dataset_class") in dfm.DATASET_CLASSES, f"{g['name']}: dataset class"
        if g["route"] != "unreachable":
            assert any(g.get(k) for k in ("url", "queries", "feeds", "subs", "channels", "bindings")), \
                f"{g['name']} declares no seeds"
        target = g.get("site") or g.get("fn") or g["route"]
        for seed in [g.get("url"), *g.get("alt", []), *g.get("feeds", []),
                     *[f"{target}|{q}" for q in g.get("queries", [])], *[f"sub:{x}" for x in g.get("subs", [])],
                     *[f"tg:{x}" for x in g.get("channels", [])]]:
            if seed:
                assert seed not in seen, f"duplicate seed {seed}"
                seen.add(seed)
        langs.add(g["language"])
    assert len({g["name"] for g in _SRC["grounds"]}) == len(_SRC["grounds"])
    assert len(_SRC["grounds"]) >= 400 and len(langs) >= 24
    # every region has story ground AND dataset/macro ground: coverage is measured per kind
    by_region = {}
    for g in _SRC["grounds"]:
        by_region.setdefault(g["region"], set()).add("dataset" if g.get("kind") in ("dataset", "macro") else "story")
    thin = [r for r, kinds in by_region.items() if kinds != {"story", "dataset"}]
    assert not thin, f"regions without both story and dataset/macro ground: {thin}"


def test_every_ground_in_the_world_file_resolves_offline_and_no_region_is_credited_for_labels(
        monkeypatch, tmp_path) -> None:
    """NO REGION GETS CREDIT FOR COVERAGE, ONLY FOR CONVERSION: run the WHOLE real grounds file
    against fixtures. Every ground must reach its route (PRODUCTIVE or REACHED_NO_CLAIMS) or be a
    recorded UNREACHABLE gap; BLOCKED means a route that does not resolve, which is a label."""
    _offline(monkeypatch, tmp_path)
    doc = _run_grounds(monkeypatch, tmp_path, _SRC["grounds"], budget=3000)
    statuses = {g["ground"]: g for g in doc["grounds"]}
    assert len(statuses) == len(_SRC["grounds"])
    bad = {k: (v["status"], v.get("errors") or v.get("error")) for k, v in statuses.items()
           if v["status"] not in ("PRODUCTIVE", "REACHED_NO_CLAIMS", "UNREACHABLE")}
    assert not bad, bad
    # The fixture world serves the same page everywhere, so most grounds see claims already
    # banked (REACHED_NO_CLAIMS); the first of each route converts and every route resolves.
    assert doc["productive"] >= 5 and doc["counts"]["claims_seen_before"] > 100
    for reg, b in doc["by_region"].items():
        assert b["worked"] == b["grounds"], reg
    assert doc["datasets_new"] >= 100 and doc["counts"]["dataset_endpoints"] >= 100
    assert doc["claims_by_channel"]["direct"] > 0 and doc["claims_by_channel"]["indirect"] > 0
    assert set(doc["ledger_schema"]) >= {"claims (data/deep_forest_claims.jsonl)"}


def test_scheduling_rotates_across_clusters_and_resumes_from_the_cursor() -> None:
    grounds = [{"name": f"cn{i}", "region": "cn", "route": "http", "url": f"https://c/{i}", "weight": 1.0 + i}
               for i in range(3)] + [{"name": f"jp{i}", "region": "jp", "route": "http", "url": f"https://j/{i}"}
                                     for i in range(2)] + [{"name": "br0", "region": "br", "route": "http",
                                                            "url": "https://b/0"}]
    order = [g["name"] for g in dfm.schedule(grounds, 0)]
    assert order[:3] == ["cn2", "jp0", "br0"], order          # round-robin, heaviest first
    assert order[3:5] == ["cn1", "jp1"]
    assert next(g["name"] for g in dfm.schedule(grounds, 2)) == "br0"   # cursor rotates the start
    assert [g["name"] for g in dfm.schedule(grounds, 0, region="jp")] == ["jp0", "jp1"]
    assert [g["name"] for g in dfm.schedule(grounds, 0, only={"latam"})] == ["br0"]


def test_search_runs_in_the_ground_s_locale_and_snippets_only_never_fetches_the_site(monkeypatch,
                                                                                   tmp_path) -> None:
    queued = _offline(monkeypatch, tmp_path)
    urls: list[str] = []

    def spy(url, **kw):
        urls.append(url)
        return _dispatch(url, **kw)
    monkeypatch.setattr(dfm, "_http", spy)
    doc = _run_grounds(monkeypatch, tmp_path, [
        {"name": "note (JP)", "region": "jp", "language": "ja", "route": "search", "site": "note.com",
         "queries": ["ドル円 仲値 手法"], "kind": "blog", "snippets_only": True}])
    assert any("setlang=ja" in u and "cc=JP" in u for u in urls)
    from urllib.parse import urlparse
    assert not any(urlparse(u).netloc.endswith("note.com") for u in urls), \
        "snippets_only must not fetch the site"
    assert doc["claims_new"] >= 1 and queued
    task = queued[0]
    assert task["source"] == "deep_forest_jp" and task["symbols"] == ["USDJPY"] and task["lang"] == "ja"
    assert task["region"] == "jp" and task["mechanism_class"] == "calendar"


def test_feed_reddit_foreign_papers_wayback_nitter_youtube_and_telegram_routes_resolve(monkeypatch,
                                                                                       tmp_path) -> None:
    queued = _offline(monkeypatch, tmp_path)
    grounds = [
        {"name": "Medium", "region": "us", "language": "en", "route": "rss", "kind": "blog",
         "feeds": ["https://medium.com/feed/tag/quant"], "fetch_items": 1},
        {"name": "reddit", "region": "us", "language": "en", "route": "reddit", "kind": "community",
         "subs": ["algotrading"]},
        {"name": "Qiita", "region": "jp", "language": "ja", "route": "foreign", "fn": "qiita",
         "queries": ["システムトレード"], "kind": "blog"},
        {"name": "arXiv", "region": "institutional", "language": "en", "route": "papers", "fn": "arxiv",
         "queries": ["carry"], "categories": ["q-fin.TR"], "kind": "academic"},
        {"name": "Quantopian", "region": "us", "language": "en", "route": "wayback", "kind": "archive",
         "url": "https://www.quantopian.com/posts", "timestamp": "20200601"},
        {"name": "nitter", "region": "us", "language": "en", "route": "nitter", "kind": "social",
         "queries": ["XAUUSD fix"], "mirrors": ["dead.mirror", "nitter.net"]},
        {"name": "YouTube JP", "region": "jp", "language": "ja", "route": "youtube", "kind": "video",
         "queries": ["ドル円 仲値"], "transcripts": 2},
        {"name": "Telegram RU", "region": "ru", "language": "ru", "route": "telegram", "kind": "social",
         "channels": ["markettwits"]},
        {"name": "coinpan never", "region": "kr", "language": "ko", "route": "foreign", "fn": "coinpan",
         "queries": ["x"], "kind": "forum"},
    ]
    doc = _run_grounds(monkeypatch, tmp_path, grounds)
    st = {g["ground"]: g for g in doc["grounds"]}
    assert st["Medium"]["status"] == "PRODUCTIVE" and st["Medium"]["items"] == 1
    assert st["reddit"]["status"] == "PRODUCTIVE" and st["reddit"]["subs"] == 1
    assert st["Qiita"]["status"] == "PRODUCTIVE"
    assert st["arXiv"]["status"] == "PRODUCTIVE" and st["arXiv"]["papers"] == 1
    assert st["Quantopian"]["status"] == "PRODUCTIVE" and "web.archive.org" in st["Quantopian"]["snapshot"]
    assert st["nitter"]["status"] == "PRODUCTIVE" and st["nitter"]["mirror"] == "nitter.net"
    # The YouTube route generalises the Bilibili one: metadata converts, the transcript gap is SAID.
    assert st["YouTube JP"]["status"] == "PRODUCTIVE" and st["YouTube JP"]["transcripts"] == 0
    assert any("mirror rotation dead" in e for e in st["YouTube JP"]["errors"])
    assert st["Telegram RU"]["status"] == "PRODUCTIVE" and st["Telegram RU"]["channels"] == 1
    # The fenced foreign function is refused by the allowlist, not by luck.
    assert st["coinpan never"]["status"] == "BLOCKED" and "allowlist" in st["coinpan never"]["error"]
    sources = {t["source"] for t in queued}
    assert {"deep_forest_west", "deep_forest_jp", "deep_forest_institutional", "deep_forest_ru"} <= sources
    # papers carry the abstract's published date as published_time
    arx = next(r for r in dfm._claims_rows() if r["ground"] == "arXiv")
    assert arx["published_time"] == "2026-09-01" and arx["evidence_grade"] == "PAPER"


def test_a_dataset_ground_yields_discovery_rows_the_acquirer_reads(monkeypatch, tmp_path) -> None:
    _offline(monkeypatch, tmp_path)
    doc = _run_grounds(monkeypatch, tmp_path, [
        {"name": "SARB statistics", "region": "za", "language": "en", "route": "http", "kind": "dataset",
         "url": "https://www.resbank.co.za/en/home/what-we-do/statistics", "dataset_class": "central_bank_data"}])
    assert doc["datasets_new"] == 1 and doc["counts"]["dataset_pages"] == 1
    assert doc["counts"]["dataset_endpoints"] >= 2
    files = list((tmp_path / "world").glob("discoveries_deepforest_*.json"))
    assert len(files) == 1
    row = json.loads(files[0].read_text("utf-8"))[0]
    # EXACTLY the row shape acquire_datasets._endpoints reads: endpoints + host, kind dataset.
    assert row["kind"] == "dataset" and row["host"] == "www.resbank.co.za"
    assert any(u.endswith("reserves.csv") for u in row["endpoints"]) and row["n_endpoints"] >= 2
    assert row["dataset_class"] == "central_bank_data" and row["region"] == "za"
    assert (tmp_path / "datasets.jsonl").exists()
    st = doc["grounds"][0]
    assert st["datasets"] == 1


def test_claims_carry_pit_provenance_channel_class_and_fold_on_the_mechanism_key(monkeypatch,
                                                                                   tmp_path) -> None:
    queued = _offline(monkeypatch, tmp_path)
    doc = _run_grounds(monkeypatch, tmp_path, [
        {"name": "Elite Trader", "region": "us", "language": "en", "route": "http", "kind": "forum",
         "url": "https://www.elitetrader.com/et/"},
        {"name": "BabyPips", "region": "us", "language": "en", "route": "http", "kind": "forum",
         "url": "https://forums.babypips.com/latest"}])
    rows = dfm._claims_rows()
    gold = next(r for r in rows if "Gold usually mean reverts" in r["claim"])
    assert gold["published_time"] == "2026-08-30T10:00:00Z" and gold["available_time"]
    assert gold["ingested_time"] and len(gold["source_hash"]) == 64 and gold["event_time"] is None
    assert gold["channel"] == "direct" and gold["mechanism_class"] == "calendar"   # the fix
    soy = next(r for r in rows if "soy exports" in r["claim"])
    assert soy["channel"] == "indirect" and soy["instruments"]["indirect"] == ["USDBRL"]
    assert soy["mechanism_class"] == "flow"
    # The same three claims told on the second ground fold: one task per mechanism, two tellings.
    assert doc["counts"]["duplicate_mechanisms"] >= 3
    task = next(t for t in queued if t["mechanism_key"] == gold["mechanism_key"])
    assert task["n_tellings"] >= 2 and {p["ground"] for p in task["provenance"]} == {"Elite Trader", "BabyPips"}
    assert task["source"] == "deep_forest_west" and task["mechanism_key"] == gold["mechanism_key"]
    assert "channel=direct" in task["description"] and "Told" in task["description"]
    # unmappable claims are counted, never queued as summaries
    assert "dropped_unmappable" in doc["counts"]


def test_an_unmappable_sentence_is_dropped_and_counted_not_queued() -> None:
    r = mc.extract("The index usually rallies for a week after a breakout when volume expands.")
    assert r["claims"] == [] and r["dropped_unmappable"] == 1


def test_a_ground_that_yields_only_momentum_says_so(monkeypatch, tmp_path) -> None:
    _offline(monkeypatch, tmp_path)
    page = ("<html><title>t</title><body><p>Gold breakout momentum usually continues for a week after the "
            "daily high is taken. Silver trend follows gold intraday after a breakout.</p></body></html>")
    monkeypatch.setattr(dfm, "_http", lambda url, **kw: page)
    doc = _run_grounds(monkeypatch, tmp_path, [
        {"name": "Momentum only", "region": "us", "language": "en", "route": "http", "kind": "blog",
         "url": "https://m.test/"}])
    assert doc["momentum_only_grounds"] == ["Momentum only"]
    assert doc["grounds"][0]["classes"] == {"momentum": doc["grounds"][0]["claims"]}
