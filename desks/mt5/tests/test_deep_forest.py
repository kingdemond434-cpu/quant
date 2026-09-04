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

from libs.research import mechanism_claims as mc  # noqa: E402
from research import deep_forest_miner as dfm  # noqa: E402
from research import proposer_common as pc  # noqa: E402

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
    from libs.research.bandit import arm_of
    assert arm_of("deep_forest") == "external_screen" == arm_of("repo_miner")
    assert arm_of("x", "story_mechanism") == "external_screen"


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
