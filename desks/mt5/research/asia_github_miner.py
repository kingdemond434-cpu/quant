"""ASIAN RETAIL AND SMALL-SHOP QUANTS ON GITHUB: their strategies, factor ideas and data sources.

    py -3 desks/mt5/research/asia_github_miner.py            # argless: one pass
    py -3 desks/mt5/research/asia_github_miner.py --dry-run  # search and extract, donate nothing

zuck, 2026-11-18 01:55Z: "we need alot of clues on chinese n asian retail shops on our level ...
they scrape net like us aswell whole world anyth fr edge all info ugly or wtv". The deep forest
miner covers their forums from the box. This organ covers the other half, the code they publish:
vn.py strategy folders, JoinQuant / RiceQuant notebooks pushed to GitHub, Japanese FX EA logic,
Korean and Taiwanese futures bots, Indian Nifty algos.

Access: the GitHub REST API only (search/repositories and repos/{o}/{r}/readme), which is
GitHub's documented interface and is how this desk already reads GitHub. No forum, no scrape.

Per repository it extracts:
  * MECHANISMS, by a multilingual vocabulary (CN/JP/KR/TW/EN) mapped onto the compiler's
    registered price-only families. Classic Chinese intraday systems (R-Breaker, Dual Thrust,
    菲阿里四价, 空中花园, 海龟) map to their breakout families.
  * INSTRUMENTS, through the translation rule: the exact MT5 analogue where one exists
    (沪金 -> XAUUSD, 沪铜 -> XCUUSD, 原油 -> XTIUSD, 豆粕 -> SOYBEAN, ドル円 -> USDJPY, 日経 ->
    JPN225, 恒生 -> HK50 ...). No analogue (螺纹钢, KOSPI, Nifty) means the row is an IDEA, kept
    with its mechanism for the deepening path, never forced onto an unrelated symbol.
  * DATA-SOURCE CLUES: the libraries and sites their code reads (akshare, tushare, jqdata,
    J-Quants, kiteconnect ...). Their scrape list is a map of where retail edge data lives.

Every hypothesis row is a `{"kind": "hypothesis", "family", "symbols"}` row donated through
`proposer_common.donate` (stamped, blinded, preregistered, charged as trials). The judge decides.
Writes reports/ASIA_GITHUB.json and data/asia_github/seen.json (repos already read).
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT = DESK / "reports" / "ASIA_GITHUB.json"
STATE = DESK / "data" / "asia_github" / "seen.json"
CLUES = DESK / "data" / "asia_github" / "data_source_clues.jsonl"
IDEAS = DESK / "data" / "asia_github" / "ideas.jsonl"
SOURCE = "asia_github"

#: (region, query). Repository search, newest-pushed and most-starred both, so a pass reaches
#: the living small shops and not only the famous frameworks.
QUERIES: tuple[tuple[str, str], ...] = (
    ("cn", "期货 策略"), ("cn", "CTA 策略 回测"), ("cn", "商品期货 量化"),
    ("cn", "vnpy 策略"), ("cn", "聚宽 策略"), ("cn", "米筐 策略"), ("cn", "量化 因子"),
    ("cn", "黄金 量化 交易"), ("cn", "日内 交易 策略"), ("cn", "R-Breaker"),
    ("cn", "Dual Thrust"), ("cn", "海龟 交易"), ("cn", "外汇 策略"), ("cn", "期货 跨期 套利"),
    ("jp", "FX 自動売買"), ("jp", "システムトレード FX"), ("jp", "ドル円 戦略"),
    ("jp", "日経225 先物 戦略"), ("kr", "자동매매 전략"), ("kr", "선물 자동매매"),
    ("kr", "퀀트 전략 백테스트"), ("tw", "台指期 策略"), ("tw", "期貨 程式交易"),
    ("in", "nifty algo trading strategy"), ("in", "banknifty strategy backtest"),
    ("sea", "vn30 trading strategy"), ("sea", "saham trading strategi"),
)
PER_QUERY = 8

#: phrase (lower-cased) -> registered family. Ordered most specific first.
MECHANISMS: tuple[tuple[str, str], ...] = (
    ("r-breaker", "failed_breakout"), ("rbreaker", "failed_breakout"),
    ("dual thrust", "session_range_breakout"), ("dualthrust", "session_range_breakout"),
    ("菲阿里", "session_range_breakout"), ("空中花园", "session_range_breakout"),
    ("开盘区间", "session_range_breakout"), ("opening range", "session_range_breakout"),
    ("海龟", "level_breakout"), ("turtle", "level_breakout"), ("唐奇安", "level_breakout"),
    ("donchian", "level_breakout"), ("通道突破", "level_breakout"), ("突破", "level_breakout"),
    ("돌파", "level_breakout"), ("ブレイクアウト", "level_breakout"),
    ("breakout", "level_breakout"),
    ("双均线", "trend_ma_cross"), ("均线", "trend_ma_cross"), ("金叉", "trend_ma_cross"),
    ("ゴールデンクロス", "trend_ma_cross"), ("移動平均", "trend_ma_cross"),
    ("이동평균", "trend_ma_cross"), ("골든크로스", "trend_ma_cross"),
    ("moving average cross", "trend_ma_cross"), ("ma cross", "trend_ma_cross"),
    ("布林", "mean_reversion_bollinger"), ("ボリンジャー", "mean_reversion_bollinger"),
    ("볼린저", "mean_reversion_bollinger"), ("bollinger", "mean_reversion_bollinger"),
    ("rsi", "mean_reversion_rsi"), ("逆張り", "mean_reversion_rsi"),
    ("均值回归", "range_reversion"), ("mean reversion", "range_reversion"),
    ("震荡", "range_reversion"), ("レンジ", "range_reversion"),
    ("跳空", "overnight_gap_decay"), ("gap", "overnight_gap_decay"),
    ("窓埋め", "overnight_gap_decay"),
    ("隔夜", "overnight_drift"), ("overnight", "overnight_drift"),
    ("动量", "momentum_volgate"), ("momentum", "momentum_volgate"), ("모멘텀", "momentum_volgate"),
    ("波动率", "vol_transition"), ("volatility breakout", "volatility_squeeze"),
    ("변동성 돌파", "volatility_squeeze"), ("squeeze", "volatility_squeeze"),
    ("月初", "turn_of_month"), ("turn of the month", "turn_of_month"),
    ("星期效应", "dow_effect"), ("曜日", "dow_effect"), ("day of week", "dow_effect"),
    ("仲値", "london_close_momentum"), ("東京時間", "asia_momentum"),
    ("asian session", "asia_momentum"),
)

#: phrase (lower-cased) -> MT5 analogue(s). The translation rule: exact analogue or nothing.
INSTRUMENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("沪金", ("XAUUSD",)), ("黄金", ("XAUUSD",)), ("gold", ("XAUUSD",)), ("金先物", ("XAUUSD",)),
    ("沪银", ("XAGUSD",)), ("白银", ("XAGUSD",)), ("silver", ("XAGUSD",)),
    ("沪铜", ("XCUUSD",)), ("铜", ("XCUUSD",)), ("copper", ("XCUUSD",)),
    ("沪铝", ("XALUSD",)), ("沪锌", ("XZNUSD",)), ("沪镍", ("XNIUSD",)), ("沪铅", ("XPBUSD",)),
    ("原油", ("XTIUSD", "XBRUSD")), ("crude", ("XTIUSD", "XBRUSD")), ("wti", ("XTIUSD",)),
    ("天然气", ("XNGUSD",)), ("natural gas", ("XNGUSD",)),
    ("豆粕", ("SOYBEAN",)), ("大豆", ("SOYBEAN",)), ("玉米", ("CORN",)), ("棉花", ("COTTON",)),
    ("白糖", ("SUGAR",)), ("小麦", ("WHEAT",)), ("咖啡", ("COFARA",)),
    ("恒生", ("HK50",)), ("恒指", ("HK50",)), ("hang seng", ("HK50",)), ("国企", ("CHINAH",)),
    ("日经", ("JPN225",)), ("日経", ("JPN225",)), ("nikkei", ("JPN225",)),
    ("标普", ("US500",)), ("s&p", ("US500",)), ("纳指", ("NAS100",)), ("nasdaq", ("NAS100",)),
    ("ドル円", ("USDJPY",)), ("usdjpy", ("USDJPY",)), ("美元日元", ("USDJPY",)),
    ("ユーロ円", ("EURJPY",)), ("eurjpy", ("EURJPY",)), ("ポンド円", ("GBPJPY",)),
    ("gbpjpy", ("GBPJPY",)), ("豪ドル円", ("AUDJPY",)), ("audjpy", ("AUDJPY",)),
    ("ユーロドル", ("EURUSD",)), ("eurusd", ("EURUSD",)), ("欧元", ("EURUSD",)),
    ("gbpusd", ("GBPUSD",)), ("audusd", ("AUDUSD",)), ("usdcnh", ("USDCNH",)),
    ("离岸人民币", ("USDCNH",)), ("xauusd", ("XAUUSD",)),
)
#: A price-only mechanism named on NO instrument is instrument-agnostic by construction; it is
#: ported onto the markets that region's retail actually trades and that MT5 lists exactly
#: (zuck 2026-11-18: exact ports where they map; country pairing is an ordering, not a filter).
#: Regions whose home markets have no MT5 analogue (KR, TW, IN, SEA) stay ideas.
REGION_DEFAULT: dict[str, tuple[str, ...]] = {
    "cn": ("XAUUSD", "XCUUSD", "XTIUSD", "SOYBEAN", "HK50"),
    "jp": ("USDJPY", "EURJPY", "JPN225"),
}

#: Named with no MT5 analogue: the row is an idea, never a cell on a substitute.
NO_ANALOGUE = ("螺纹", "铁矿", "焦炭", "焦煤", "甲醇", "pta", "沪深300", "中证500", "上证50",
               "kospi", "코스피", "台指", "加权指数", "nifty", "banknifty", "sensex", "vn30")

DATA_CLUES: tuple[str, ...] = (
    "akshare", "tushare", "baostock", "jqdatasdk", "jqdata", "rqdatac", "rqalpha", "efinance",
    "easyquotation", "pytdx", "通达信", "东方财富", "新浪财经", "同花顺", "wind", "choice",
    "qlib", "vnpy", "tqsdk", "天勤", "ctp", "openctp", "futu", "富途", "雪球", "xueqiu",
    "j-quants", "jquants", "kabu", "kabusapi", "oanda", "mt4", "mt5", "metatrader", "rakuten",
    "楽天", "sbi", "pykiwoom", "키움", "kis api", "한국투자", "creon", "shioaji", "永豐",
    "kiteconnect", "zerodha", "nsepy", "nsetools", "upstox", "angel one", "smartapi",
    "yfinance", "investpy", "ccxt", "binance", "twitter", "weibo", "微博", "百度指数",
    "google trends", "news", "新闻", "研报", "公告", "龙虎榜", "北向资金", "融资融券", "持仓",
    "cot", "期货持仓", "仓单", "基差", "库存",
)

_GH_HEADERS = ("-H", "Accept: application/vnd.github+json")


def _gh(path: str) -> Any:
    """One GitHub REST GET through the `gh` CLI (authenticated, rate-limited by GitHub)."""
    out = subprocess.run(["gh", "api", "-X", "GET", *_GH_HEADERS, path], capture_output=True,
                         text=True, timeout=60, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise RuntimeError(f"gh api {path.split('?')[0]} rc={out.returncode}")
    return json.loads(out.stdout or "null")


def search(query: str, per_page: int = PER_QUERY) -> list[dict[str, Any]]:
    from urllib.parse import quote
    q = quote(query)
    rows: dict[str, dict[str, Any]] = {}
    for sort in ("stars", "updated"):
        try:
            doc = _gh(f"search/repositories?q={q}&sort={sort}&order=desc&per_page={per_page}")
        except (RuntimeError, ValueError, subprocess.SubprocessError):
            continue
        for it in (doc or {}).get("items", []):
            rows[str(it.get("full_name"))] = it
        time.sleep(2.1)                          # search API: 30 requests / minute
    return list(rows.values())


def readme(full_name: str) -> str:
    try:
        doc = _gh(f"repos/{full_name}/readme")
    except (RuntimeError, ValueError, subprocess.SubprocessError):
        return ""
    try:
        return base64.b64decode(str((doc or {}).get("content", ""))).decode("utf-8", "replace")
    except (ValueError, TypeError):
        return ""


#: Code searches over the frameworks these traders publish strategies in. The FILE NAME of a
#: vn.py CTA strategy names its mechanism (DualThrustStrategy, KingKeltnerStrategy,
#: TurtleSignalStrategy, AtrRsiStrategy), so the path alone is a mechanism record.
CODE_QUERIES: tuple[tuple[str, str], ...] = (
    ("cn", "CtaTemplate language:python"), ("cn", "rqalpha handle_bar language:python"),
    ("cn", "jqdata initialize handle_data language:python"), ("cn", "tqsdk TargetPosTask"),
    ("jp", "OnTick ドル円 language:MQL4"), ("jp", "OnTick 日経 language:MQL5"),
)
#: A repository must be about trading before its words are read as a mechanism: a search hit on
#: "突破" in an unrelated repo is not a breakout strategy.
_TRADING = re.compile(r"策略|量化|交易|回测|期货|trading|strategy|backtest|quant|売買|トレード|"
                      r"매매|퀀트|백테스트|程式交易")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def code_hits(query: str, per_page: int = 30) -> list[dict[str, Any]]:
    from urllib.parse import quote
    try:
        doc = _gh(f"search/code?q={quote(query)}&per_page={per_page}")
    except (RuntimeError, ValueError, subprocess.SubprocessError):
        return []
    time.sleep(6.5)                              # code search: 10 requests / minute
    out = []
    for it in (doc or {}).get("items", []):
        repo = it.get("repository") or {}
        out.append({"full_name": repo.get("full_name"), "html_url": it.get("html_url"),
                    "path": it.get("path"), "stargazers_count": None,
                    "pushed_at": None})
    return out


def path_text(path: str) -> str:
    """'strategies/dual_thrust_strategy.py' and 'DualThrustStrategy.py' both read as words."""
    stem = Path(path).stem
    return " ".join([path, _CAMEL.sub(" ", stem).replace("_", " ")])


def _snippet(text: str, phrase: str, width: int = 90) -> str:
    i = text.lower().find(phrase)
    if i < 0:
        return ""
    s = text[max(0, i - width // 2): i + len(phrase) + width // 2]
    return re.sub(r"\s+", " ", s).strip()[:200]


def extract(text: str) -> dict[str, Any]:
    low = text.lower()
    fams: dict[str, str] = {}
    for phrase, fam in MECHANISMS:
        if fam in fams:
            continue
        if phrase.isascii() and phrase.isalpha() and len(phrase) <= 4:
            hit = re.search(rf"\b{re.escape(phrase)}\b", low) is not None
        else:
            hit = phrase in low
        if hit:
            fams[fam] = phrase
    syms: dict[str, str] = {}
    for phrase, targets in INSTRUMENTS:
        hit = (re.search(rf"\b{re.escape(phrase)}\b", low) is not None if phrase.isascii()
               else phrase in low)
        if hit:
            for t in targets:
                syms.setdefault(t, phrase)
    no_analogue = sorted({p for p in NO_ANALOGUE if p in low})
    clues = sorted({c for c in DATA_CLUES
                    if (re.search(rf"\b{re.escape(c)}\b", low) is not None if c.isascii()
                        else c in low)})
    return {"families": fams, "symbols": syms, "no_analogue": no_analogue, "clues": clues}


def rows_for(repo: dict[str, Any], region: str, text: str, ex: dict[str, Any], at: str
             ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(hypothesis rows, idea rows). A mechanism with an MT5 analogue becomes one row per
    (family, symbol); a mechanism on an instrument with no analogue is an idea."""
    url = str(repo.get("html_url") or "")
    name = str(repo.get("full_name") or "")
    hyps: list[dict[str, Any]] = []
    ideas: list[dict[str, Any]] = []
    for fam, phrase in ex["families"].items():
        quote = _snippet(text, phrase)
        targets = list(ex["symbols"].items())[:6]
        translation = "exact_analogue"
        if not targets and not ex["no_analogue"] and region in REGION_DEFAULT:
            targets = [(s, f"{region} home market") for s in REGION_DEFAULT[region]]
            translation = "instrument_agnostic_region_market"
        if targets:
            for sym, sym_phrase in targets:
                hyps.append({"kind": "hypothesis", "family": fam, "symbols": [sym],
                             "title": f"{fam.replace('_', ' ')} on {sym} from {name}",
                             "mechanism": f"{region} retail repo names '{phrase}' on "
                                          f"'{sym_phrase}': {quote}",
                             "url": url, "region": region, "repo": name,
                             "stars": repo.get("stargazers_count"),
                             "pushed_at": repo.get("pushed_at"), "translation": translation})
        else:
            ideas.append({"at": at, "region": region, "repo": name, "url": url, "family": fam,
                          "phrase": phrase, "quote": quote,
                          "no_analogue": ex["no_analogue"],
                          "why": "mechanism named on no instrument with an MT5 analogue"})
    return hyps, ideas


def _load(p: Path) -> dict[str, Any]:
    try:
        doc: dict[str, Any] = json.loads(p.read_text("utf-8"))
        return doc
    except (OSError, ValueError):
        return {}


def _append(p: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def run(dry_run: bool = False, queries: tuple[tuple[str, str], ...] = QUERIES,
        budget_s: float = 900.0) -> dict[str, Any]:
    t0 = time.monotonic()
    at = datetime.now(tz=UTC).isoformat()
    seen = _load(STATE).get("repos", {})
    per_region: dict[str, dict[str, int]] = {}
    hyps: list[dict[str, Any]] = []
    ideas: list[dict[str, Any]] = []
    clue_rows: list[dict[str, Any]] = []
    read = 0
    for region, q in queries:
        if time.monotonic() - t0 > budget_s:
            break
        stats = per_region.setdefault(region, {"repos_found": 0, "repos_read": 0,
                                               "hypotheses": 0, "ideas": 0, "clues": 0})
        for repo in search(q):
            name = str(repo.get("full_name"))
            stats["repos_found"] += 1
            pushed = str(repo.get("pushed_at") or "")
            if seen.get(name) == pushed:
                continue
            text = " ".join([str(repo.get("description") or ""), " ".join(
                repo.get("topics") or []), readme(name)])
            read += 1
            stats["repos_read"] += 1
            seen[name] = pushed
            if not _TRADING.search(text.lower()):
                stats.setdefault("not_trading", 0)
                stats["not_trading"] += 1
                continue
            ex = extract(text)
            h, i = rows_for(repo, region, text, ex, at)
            hyps += h
            ideas += i
            stats["hypotheses"] += len(h)
            stats["ideas"] += len(i)
            if ex["clues"]:
                stats["clues"] += 1
                clue_rows.append({"at": at, "region": region, "repo": name,
                                  "url": repo.get("html_url"), "clues": ex["clues"]})
    for region, q in CODE_QUERIES:
        if time.monotonic() - t0 > budget_s:
            break
        stats = per_region.setdefault(region, {"repos_found": 0, "repos_read": 0,
                                               "hypotheses": 0, "ideas": 0, "clues": 0})
        stats.setdefault("code_files", 0)
        for hit in code_hits(q):
            key = f"{hit['full_name']}/{hit['path']}"
            if seen.get(key):
                continue
            seen[key] = at
            stats["code_files"] += 1
            text = path_text(str(hit["path"]))
            ex = extract(text)
            h, i = rows_for({**hit, "full_name": key}, region, text, ex, at)
            hyps += h
            ideas += i
            stats["hypotheses"] += len(h)
            stats["ideas"] += len(i)
    # one row per (family, symbol) per pass: the best-starred repo carries it
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for row in hyps:
        k = (row["family"], row["symbols"][0])
        if k not in best or (row.get("stars") or 0) > (best[k].get("stars") or 0):
            best[k] = row
    cells = list(best.values())
    donated: dict[str, Any] = {"donated": 0}
    if not dry_run and cells:
        from research import proposer_common as pc
        pc.donate(SOURCE, cells, tests_run=len(cells))
        donated = pc.donation_counts()
        donated.pop("refusals", None)
        donated.pop("lane_refusals", None)
    if not dry_run:
        _append(IDEAS, ideas)
        _append(CLUES, clue_rows)
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({"at": at, "repos": seen}, ensure_ascii=False, indent=1),
                         "utf-8")
    clue_count: dict[str, int] = {}
    for r in clue_rows:
        for c in r["clues"]:
            clue_count[c] = clue_count.get(c, 0) + 1
    doc = {"at": at, "dry_run": dry_run, "repos_read": read, "per_region": per_region,
           "hypothesis_rows": len(hyps), "cells_after_dedup": len(cells),
           "ideas_no_analogue": len(ideas), "donation": donated,
           "families": sorted({c["family"] for c in cells}),
           "symbols": sorted({c["symbols"][0] for c in cells}),
           "top_data_clues": sorted(clue_count.items(), key=lambda kv: -kv[1])[:30],
           "elapsed_s": round(time.monotonic() - t0, 1)}
    if not dry_run:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, ensure_ascii=False, indent=1, default=str), "utf-8")
    return {**doc, "_cells": cells, "_ideas": ideas, "_clues": clue_rows}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(dry_run=a.dry_run)
    print(f"ASIA GITHUB  {doc['at']}  read {doc['repos_read']} repos; "
          f"{doc['cells_after_dedup']} cells, {doc['ideas_no_analogue']} ideas")
    for reg, s in doc["per_region"].items():
        print(f"  {reg:4s} {s}")
    print(f"  donation {doc['donation']}")
    print(f"  clues {doc['top_data_clues'][:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
