"""Daily research miner: discover candidate quant sources, rank them, queue what to read.

WHAT IT DOES AND WHAT IT CANNOT, both measured from this box on 2026-08-01 rather than assumed.

    YouTube channel listings   REACHABLE -- video ids + titles parse out of the page (23/23 for
                               one channel)
    YouTube captions           BLOCKED -- no `captionTracks` in the watch page, api/timedtext
                               returns 0 bytes, youtube-transcript-api raises RequestBlocked.
                               Datacenter-IP block; retrying does not fix it.
    Xueqiu (雪球)              REACHABLE -- 110KB of real content with an embedded JSON payload
    Baidu                      BLOCKED -- returns a 1.5KB anti-bot shell, not results
    Zhihu (知乎)               BLOCKED -- HTTP 403
    Bilibili search API        BLOCKED -- HTTP 412 (WBI request signing required)
    JoinQuant / BigQuant /     REACHABLE but JS-rendered shells; the listings need a browser.
    RiceQuant / MyQuant        Chromium is available in this environment for that.

So this miner does NOT fetch transcripts and does not pretend to. It solves the part that is
actually expensive for a human: deciding WHICH of several hundred videos is worth reading. One
channel in this batch had 559 videos and the desk's own record shows most of them would convert
nothing.

EVERY SOURCE RECORDS ITS OWN STATUS. A source that fails is written into the report as BLOCKED
with the reason, never skipped silently -- the 2026-08-01 batch produced a report saying "OKX
BLOCKED, HTTP 403" that turned out to be a User-Agent bot-filter, and an honestly recorded WRONG
diagnosis outlives the outage it describes (lesson L0052).

THE LEDGER MAKES IT DAILY. Seen video ids are appended, so each run surfaces only what is NEW.
Without it a daily job re-reports the same backlog forever and gets ignored within a week.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.data import bilibili, cn_sources, foreign_sources, papers
from libs.research import conversion_ledger, source_health
from libs.research.video_triage import SURFACE_THRESHOLD, score_title, triage

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "reports" / "research_queue.json"
_LEDGER = _ROOT / "data" / "research_queue_seen.json"

_UA = {"User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
       "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8"}

#: Channels whose output has actually converted on this desk, plus near neighbours. Ordered by
#: measured conversion: neurotrader and Algovibes produced essentially everything that shipped
#: from the 2026-08-01 batch.
YOUTUBE_CHANNELS = (
    "@neurotrader888",
    "@Algovibes",
    "@quantprogram",
    "@TheTransparentTrader",
    "@PartTimeLarry",
    "@quantopian",
)

#: Chinese-language sources. Only the ones measured reachable are enabled; the rest are declared
#: here WITH their block reason so the next reader does not re-diagnose them.
CN_SOURCES: tuple[dict[str, str], ...] = (
    {"name": "xueqiu", "url": "https://xueqiu.com/", "status": "enabled"},
    {"name": "baidu", "url": "https://www.baidu.com/s?wd=%E9%87%8F%E5%8C%96%E4%BA%A4%E6%98%93",
     "status": "blocked", "reason": "returns a ~1.5KB anti-bot shell rather than results"},
    {"name": "zhihu", "url": "https://www.zhihu.com/search?q=%E9%87%8F%E5%8C%96",
     "status": "blocked", "reason": "HTTP 403 to unauthenticated requests"},
    {"name": "bilibili", "url": "https://api.bilibili.com/x/web-interface/search/type",
     "status": "blocked", "reason": "HTTP 412 -- search API requires WBI request signing"},
    {"name": "joinquant", "url": "https://www.joinquant.com/", "status": "needs_browser",
     "reason": "reachable but JS-rendered; listings require Chromium"},
    {"name": "bigquant", "url": "https://bigquant.com/", "status": "needs_browser",
     "reason": "reachable but JS-rendered; listings require Chromium"},
    {"name": "ricequant", "url": "https://www.ricequant.com/", "status": "needs_browser",
     "reason": "reachable but JS-rendered; listings require Chromium"},
)


def _get(url: str, *, timeout: float = 30.0) -> str:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        body: str = fh.read().decode("utf8", errors="ignore")
    return body


def fetch_channel(handle: str) -> tuple[list[tuple[str, str]], str | None]:
    """(video_id, title) pairs from a channel's /videos page, or (…, error).

    IDS AND TITLES COME FROM THE SAME BLOCK, never from two independent lists. A misaligned
    pairing would attach the wrong title to every id and the queue would rank nonsense while
    looking perfectly healthy -- the worst class of bug this miner could have, because the output
    stays plausible.

    PARSES `lockupViewModel`, which is the CURRENT layout. YouTube previously emitted
    `videoRenderer` blocks and this parser was written against those; on 2026-08-01 the page
    served zero of them and 24 lockupViewModels, so an earlier version reported every channel as
    blocked. Both shapes are tried, newest first, and a page that yields neither is reported as a
    LAYOUT CHANGE rather than a network failure -- they need completely different fixes and
    conflating them wastes the next reader's time.
    """
    try:
        html = _get(f"https://www.youtube.com/{handle}/videos", timeout=40)
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:140]}"
    return _parse_listing(html)


def _parse_listing(html: str) -> tuple[list[tuple[str, str]], str | None]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    # Current layout: {"lockupViewModel":{"contentId":"<id>", ... "title":{"content":"<title>"}}}
    for block in re.split(r'"lockupViewModel":', html)[1:]:
        # NO WINDOW. An earlier version searched only the first 4,000 chars of each block and
        # found nothing: a lockup carries several thumbnail URLs before it reaches contentId, so
        # the id routinely sits past that. The split already bounds each block to one video.
        vid = re.search(r'"contentId":"([\w-]{11})"', block)
        title = re.search(r'"title":\{"content":"((?:[^"\\]|\\.)*)"', block)
        if vid and title and vid.group(1) not in seen:
            seen.add(vid.group(1))
            out.append((vid.group(1), _unescape(title.group(1))))

    if not out:  # Legacy layout, kept so an older cached page still parses.
        for block in re.findall(r'"videoRenderer":\{(.*?)"navigationEndpoint"', html, flags=re.S):
            vid = re.search(r'"videoId":"([\w-]{11})"', block)
            title = re.search(r'"title":\{"runs":\[\{"text":"((?:[^"\\]|\\.)*)"\}\]', block)
            if vid and title and vid.group(1) not in seen:
                seen.add(vid.group(1))
                out.append((vid.group(1), _unescape(title.group(1))))

    if not out:
        return [], ("LAYOUT CHANGE: page fetched but neither lockupViewModel nor videoRenderer "
                    "blocks parsed. This is a parser fix, not a network problem.")
    return out, None


def _unescape(raw: str) -> str:
    try:
        decoded: str = json.loads(f'"{raw}"')
        return decoded
    except json.JSONDecodeError:
        return raw


#: Search queries run EVERY day so the miner is not limited to a hand-picked channel list. The
#: desk's whole problem with a fixed list is that it can only ever re-find what someone already
#: knew about; search is what makes the miner exploratory. Multilingual on purpose -- the
#: Chinese-language quant scene publishes to YouTube too, and those results never surface from
#: English queries.
#: WIDENED 6 -> 24 on 2026-08-05. Bilibili is the ONLY mined source clearing its weight: on the
#: 2026-08-05 sweep it produced 15 of the 31 new above-threshold rows, while Juejin returned 0 new
#: from 80 fetched. So depth and breadth go HERE rather than into more frequency everywhere -- the
#: other sources are publication-rate-limited (arXiv announces once a weekday; polling it four
#: times cannot mint papers), whereas B站 has a genuinely deep back-catalogue that query breadth,
#: not poll rate, is what reaches.
#: The terms are deliberately spread across STRATEGY CLASS (arb/HFT/market-making/CTA/
#: trend/mean-reversion/options), VALIDATION vocabulary (out-of-sample, walk-forward, overfit),
#: FACTOR work, the MT5 UNIVERSE (gold/XAU, FX, metals, indices, energy), the MT5-NATIVE
#: MECHANISM register (COT positioning, carry/swap, session structure, SMC/ICT liquidity), and
#: PRACTITIONER framing (live-traded, fund-side) -- because a query set clustered in one register
#: returns one corpus repeatedly, which is the same redundancy trap L1.49 names for candidates:
#: breadth of SEARCH, not volume of fetching, is what finds something new.
#:
#: MT5 UNIVERSE MANDATE (2026-08-18). The desk's market is the full MT5/Fusion universe, and NO
#: crypto-exchange universe (Binance/Bybit/OKX/Hyperliquid) is hunted any longer. Every
#: crypto-exchange-native query (perpetual funding, on-chain, cross-exchange arb, liquidation
#: cascades, miner sell-pressure) was removed here on that date; what stayed is universe-neutral
#: (validation, microstructure, factor work transfer to any market) and what replaced them targets
#: gold, FX, metals, indices, energy and the MT5-native mechanisms.
BILIBILI_QUERIES = (
    "量化交易 策略",
    "量化 回测 python",
    "量化投资 因子",
    "程序化交易 策略",
    "期货 量化 策略",
    # validation vocabulary -- the desk's highest-converting register (L0038)
    "量化 样本外 测试",
    "量化 过拟合",
    "策略 回测 陷阱",
    "walk forward 量化",
    # strategy classes (universe-neutral -- these transfer to any market)
    "网格交易 策略",
    "统计套利 策略",
    "高频交易 策略",
    "做市 策略",
    "CTA 趋势跟踪",
    "均值回归 策略",
    "期权 波动率 策略",
    # factor / alpha work
    "多因子模型 选股",
    "因子 有效性 检验",
    # practitioner framing
    "量化 实盘 复盘",
    "私募 量化 研究",
    # microstructure and execution, where cost decides the verdict
    "订单簿 深度 分析",            # order-book depth -- the desk records L2 and never searched it
    "滑点 冲击成本 实测",          # measured slippage / impact cost
    "波动率 择时 模型",            # vol timing
    "回测 幸存者偏差",             # survivorship bias -- VALIDATION register
    # MT5 UNIVERSE (2026-08-18). Replaces the crypto-exchange-native block (perp funding, cross-
    # exchange arb, liquidation cascades, on-chain, miner sell-pressure) removed on that date.
    # Territory, not synonyms: gold, FX, metals, indices, energy, and the MT5-native mechanisms.
    "黄金 交易 策略 回测",          # gold strategy, backtested
    "黄金 xauusd 分析",            # gold / XAUUSD
    "外汇 交易 策略 回测",          # forex strategy, backtested
    "外汇 ea 智能交易系统",         # forex expert advisors
    "mt5 智能交易 编写",           # writing MT5 EAs
    "贵金属 白银 交易 策略",        # silver / precious metals
    "股指期货 交易 策略",          # equity-index futures
    "原油 期货 交易 策略",          # crude / energy
    "ict 流动性 交易 结构",         # ICT liquidity / market structure
    "订单块 公允价值缺口 交易",     # order block / FVG
    "cot 持仓 报告 分析",          # COT positioning -- the whale-tracking analogue for MT5
    "套息 交易 利差 策略",          # carry trade / rate differential -- the funding analogue
    "外汇 隔夜利息 掉期 策略",      # swap / rollover carry
    "期货 基差 收敛 交易",          # futures basis convergence (gold/index futures, generic)
    "外汇 时段 伦敦 纽约 策略",     # session structure -- first-class in a non-24/7 universe
    "非农 数据 外汇 交易",          # NFP / macro-event reaction
    "美元指数 交易 策略",          # DXY
    # SECRET-SAUCE REVEALS (2026-08-20, principal: "mine strategies not bs"). Validation-vocabulary
    # queries above convert on volume but mostly BLOCKED_PENDING_DATA in practice -- they surface
    # commentary ABOUT testing, not a reproducible rule to test. This block targets titles that name
    # a specific, codeable system: parameters, entry/exit rules, source code, or a named trader's
    # disclosed method -- the highest-value class edge_intake.classify() can actually convert.
    "ea 参数 设置 详解",            # EA parameter settings, explained in detail
    "策略 源码 公开",              # strategy source code, made public
    "交易系统 完整 规则",           # complete trading system rules
    "跟单 高手 策略 拆解",          # top copy-trader's strategy, broken down
    "顶级 交易员 策略 揭秘",        # top trader's strategy, revealed
    "ea 回测 参数 优化",            # EA backtest, parameter optimisation
    "黄金 ea 参数 公开",            # gold EA, parameters disclosed
    "mql5 信号源 策略 分析",        # MQL5 Signals -- a public copy-trading leaderboard
)

# 4 -> 22 (2026-08-05). THE HIGHEST-YIELDING FAMILY HAD THE NARROWEST SWEEP, which is exactly
# backwards. Bilibili carried 24 queries while the ARTICLE sources carried 4 -- and on 2026-08-05
# WeChat/Juejin supplied 3 of the 5 new rows INCLUDING THE TOP THREE BY SCORE (18.0/13.0/9.0).
# Article sources also carry what video cannot: a procedure written down, which is the form the
# desk's own conversion record says actually converts.
#
# WIDTH HERE IS TERRITORY, NOT SYNONYMS. Four rephrasings of "quant backtest" return one forest
# four times; each line below is a DIFFERENT economic or operational subject, chosen so a single
# platform's SEO cluster cannot satisfy several at once. The order runs from the desk's confirmed
# edge outward toward material it has never indexed.
#
# PACED, because breadth that kills a lane is not breadth. Sogou rate-limits hard and answers an
# anti-bot page when pushed; cn_sources.sogou_weixin already reports that verdict rather than
# mistaking it for an empty result, and the loop's inter-query sleep is raised alongside this so
# 22 queries do not arrive faster than 4 did. L1.54: the point is to keep the door open, not to
# prove it can be slammed.
CN_ARTICLE_QUERIES = (
    # -- validation and self-deception: the class the desk's own record says converts
    "量化 回测 陷阱",
    "量化策略 过拟合",
    "样本外 检验 失效",
    "幸存者偏差 回测",
    "未来函数 前视偏差",
    # -- factor work
    "因子 挖掘 回测",
    "因子 失效 衰减",
    "多因子 组合 优化",
    # -- MT5 universe (2026-08-18): replaces the crypto-exchange-native edge block (funding-rate
    # arb, perp mechanics, cross-exchange arb) with the desk's real market and its analogues.
    "黄金 交易 策略 实盘",          # gold, live-traded
    "外汇 套息 利差 交易",          # FX carry -- the funding-rate analogue
    "期货 基差 收敛 套利",          # futures basis (gold/index), generic
    "cot 持仓 报告 交易 信号",      # COT positioning as a signal
    # -- microstructure and execution, where cost decides the verdict
    "做市 策略 库存 风险",
    "高频 交易 撮合 机制",
    "滑点 冲击成本 测算",
    "限价单 排队 优先级",
    # -- mechanisms the taxonomy names and the miner never asked about
    "止损 猎杀 流动性 扫单",        # stop-hunt / liquidity sweep -- the MT5 forced-flow analogue
    "期权 波动率 曲面 套利",
    "外汇 时段 波动 结构",          # session-structured volatility
    "央行 利率 决议 交易",          # central-bank rate decisions -- the macro-event desk
    # -- the honest failure literature, which is where the graveyard entries live
    "网格 马丁 爆仓 复盘",
    "实盘 与 回测 差异",
    # -- SECRET-SAUCE REVEALS (2026-08-20): named, reproducible systems, not validation commentary
    "ea 源码 策略 详解",
    "交易系统 入场 出场 规则",
    "跟单 策略 拆解 分析",
)

SEARCH_QUERIES = (
    # universe-neutral methodology -- the desk's highest-converting register, transfers to any market
    "quantitative trading backtest python",
    "algorithmic trading strategy tested",
    "backtested trading strategies statistical",
    "walk forward analysis trading",
    "monte carlo permutation test trading",
    "overfitting trading strategy validation",
    # MT5 universe (2026-08-18): "crypto quant strategy research" removed -- the desk hunts FX,
    # gold, metals, indices, energy now, and crypto-exchange research is no longer a target.
    "XAUUSD gold trading strategy backtest",
    "forex algorithmic trading walk forward",
    "MT5 expert advisor strategy backtest",
    "COT report positioning trading strategy",
    "gold silver trading strategy statistical",
    # multilingual, MT5 universe
    "黄金 外汇 量化 策略 回测",
    "外汇 ea 智能交易 策略",
    "ゴールド 為替 バックテスト 検証",
    "форекс золото стратегия бэктест",
)


def search_youtube(query: str) -> tuple[list[tuple[str, str]], str | None]:
    """(video_id, title) pairs from a YouTube search, using the same parser as a channel page.

    THE SAME PARSER ON PURPOSE. Search results and channel listings share the lockupViewModel
    layout, so one parser fix repairs both -- and if they ever diverge, the channel path fails
    loudly rather than the search path failing silently.
    """
    from urllib.parse import quote
    try:
        html = _get(f"https://www.youtube.com/results?search_query={quote(query)}", timeout=40)
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:140]}"
    return _parse_listing(html)


def probe_cn() -> list[dict[str, Any]]:
    """Reachability of each Chinese source, re-measured every run.

    RE-MEASURED RATHER THAN TRUSTED because a block is a fact about today. The desk has already
    been burned once by treating a recorded HTTP failure as permanent when it was a header
    problem, so the declared status is the PRIOR and the probe is the evidence.
    """
    rows: list[dict[str, Any]] = []
    for src in CN_SOURCES:
        row: dict[str, Any] = {"name": src["name"], "declared": src["status"],
                               "reason": src.get("reason")}
        try:
            body = _get(src["url"], timeout=25)
            row["reachable"] = True
            row["bytes"] = len(body)
            # A tiny body from a search endpoint is an anti-bot shell, not content.
            row["looks_like_content"] = len(body) > 20_000
        except urllib.error.HTTPError as exc:
            row["reachable"] = False
            row["http_status"] = exc.code
        except Exception as exc:
            row["reachable"] = False
            row["error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
        rows.append(row)
        time.sleep(0.4)
    return rows


def _load_seen() -> set[str]:
    if not _LEDGER.exists():
        return set()
    try:
        return set(json.loads(_LEDGER.read_text("utf-8")).get("seen", []))
    except Exception:
        return set()


def _save_seen(seen: set[str]) -> None:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    _LEDGER.write_text(json.dumps({"seen": sorted(seen)}, indent=0), "utf-8")


#: R0088's missing instrument. "Should this miner run more often?" was an OPINION for as long as
#: nobody logged what a run actually returned, and opinions default to "more" because more feels
#: like effort. One run measured by hand on 2026-08-05 settled it instantly: Juejin fetched 80 rows
#: across four queries and produced ZERO new candidates (108 already in the seen-ledger) while
#: Bilibili produced 15 of the 31 new rows. Six-times-a-day was re-reading the same corpus six
#: times. This makes that arithmetic automatic and per-source, so cadence is READ rather than
#: argued -- and so a source that quietly saturates shows up as a falling new/fetched ratio instead
#: of as a full-looking report.
_YIELD_LOG = _ROOT / "data" / "miner_yield.jsonl"

#: Which report key holds the per-query fetch counts for each source group.
#: source GROUP -> the queue-channel prefixes its producers actually write. A group whose name is
#: not itself a producer needs an entry here or its `new_above_threshold` is structurally ZERO
#: forever: the count matches on channel prefix, and "foreign" never appears in a channel because
#: the producers are qiita/zenn/hatena/dcinside/habr. `cn` was special-cased for exactly this and
#: `foreign` was not, so its first three surfaced rows logged as 0 new against 1,601 fetched --
#: a yield of 0.0 on a source that had just produced. This is the instrument CADENCE is read off,
#: so a producing lane reporting zero would argue for cutting the one sweep worth keeping.
def _foreign_producers() -> tuple[str, ...]:
    """The foreign group's producers, READ FROM THE SOURCE REGISTRY rather than restated here.

    This list was hardcoded, and that is precisely how the yield instrument reported a structural
    ZERO for the whole foreign lane once: `foreign` is a GROUP whose queue rows carry per-source
    channels, so a producer missing from the list is a producer whose rows are never counted. The
    lane logged 1,601 fetched / 0 new on a run that had just surfaced three rows, and a producing
    lane reporting nothing forever is an argument to cut the one sweep worth keeping.

    Restating the list was the fix LAST time and it did not survive contact with growth: the moment
    seven more forests were added the copy went stale again. Deriving it means a forest added
    tomorrow is counted the day it is added, with nothing to remember.
    """
    try:
        from libs.data.foreign_sources import SOURCES as _FS
        return tuple(sorted(_FS))
    except Exception:
        return ("qiita", "zenn", "hatena", "dcinside", "habr")


_GROUP_PRODUCERS: dict[str, tuple[str, ...]] = {
    "cn": ("juejin", "wechat"),
    "foreign": _foreign_producers(),
}

_FETCH_KEYS = {"bilibili": "bilibili_discovered", "cn": "cn_article_discovered",
               "search": "search_discovered", "academic": "academic_discovered",
               "youtube": "channels_scanned", "foreign": "foreign_discovered"}


#: Channel-label prefix -> the host a route hunt would actually target. Derived where possible and
#: stated where not: a hunt aimed at "hatena:some query" is aimed at nothing, while one aimed at
#: hatena.ne.jp has named routes (render path, RSS, mirrors, regional hosts).
_CHANNEL_HOSTS: dict[str, str] = {
    "bilibili": "bilibili.com", "juejin": "juejin.cn", "wechat": "weixin.qq.com",
    "qiita": "qiita.com", "zenn": "zenn.dev", "hatena": "hatena.ne.jp",
    "dcinside": "dcinside.com", "habr": "habr.com", "note": "note.com",
    "velog": "velog.io", "coinpan": "coinpan.com", "smartlab": "smart-lab.ru",
    "tinhte": "tinhte.vn", "eksisozluk": "eksisozluk.com", "vcru": "vc.ru",
    "search": "duckduckgo.com",
}


def _open_route_hunts(blocked: dict[str, str]) -> list[dict[str, Any]]:
    """One route-hunt row per blocked HOST. Never raises -- a sweep must survive its bookkeeping."""
    try:
        from libs.data.paywall import record as _record
    except Exception:
        return []
    by_host: dict[str, str] = {}
    for label, reason in (blocked or {}).items():
        host = _CHANNEL_HOSTS.get(str(label).split(":")[0], "")
        if not host:
            continue
        by_host.setdefault(host, str(reason))            # first reason per host is enough
    opened: list[dict[str, Any]] = []
    for host, reason in sorted(by_host.items()):
        # `declared=False` on purpose: a miner block is a ROUTING problem by default, and calling
        # it a paywall would put a WAF into the paid-vendor registry -- the exact pollution the
        # 402/403 split exists to prevent.
        row = _record(f"https://{host}/", status=403,
                      unlocks=f"mined research rows from {host} (blocked: {reason[:90]})")
        opened.append({"host": host, "verdict": row["verdict"], "reason": reason[:120]})
    return opened


def _yield_row(doc: dict[str, Any], *, seen: set[str], only: list[str]) -> dict[str, Any]:
    """Per-source fetched / new-above-threshold for THIS run.

    `new` counts queue rows whose channel carries the source prefix, so it is the number that
    matters -- rows that survived BOTH the seen-ledger and the score threshold. A source can look
    busy on `fetched` and still be worth nothing, which is exactly Juejin's shape and exactly what
    a fetch-count-only report would hide.
    """
    per: dict[str, dict[str, Any]] = {}
    for src, key in _FETCH_KEYS.items():
        counts = doc.get(key) or {}
        if not isinstance(counts, dict):
            continue
        fetched = sum(int(v) for v in counts.values() if isinstance(v, int | float))
        # A GROUP is not a producer. Queue channels are prefixed by whoever wrote the row, so a
        # multi-producer group must name its members or it counts none of them (see
        # _GROUP_PRODUCERS). Falls back to the source's own name, which is correct for the
        # single-producer groups (bilibili, search, academic, youtube).
        prefixes = _GROUP_PRODUCERS.get(src, (src,))
        new = sum(1 for r in doc.get("queue", [])
                  if str(r.get("channel", "")).split(":")[0] in prefixes)
        if fetched == 0 and new == 0 and src not in only and only != ["all"]:
            continue                 # not run this invocation -- absent, not zero (L1.41)
        per[src] = {"fetched": fetched, "new_above_threshold": new,
                    "yield": round(new / fetched, 4) if fetched else None}
    return {"ts": datetime.now(tz=UTC).isoformat(), "only": only,
            "threshold": doc.get("threshold"), "seen_ledger_size": len(seen),
            "n_new_total": len(doc.get("queue", [])), "per_source": per}


def _append_yield(row: dict[str, Any], path: Path | None = None) -> None:
    """Append-only; a reporting failure must never take down the miner that produced the data."""
    p = path if path is not None else _YIELD_LOG
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channels", default=",".join(YOUTUBE_CHANNELS))
    ap.add_argument("--threshold", type=float, default=SURFACE_THRESHOLD)
    ap.add_argument("--all", action="store_true", help="ignore the seen-ledger (full backlog)")
    ap.add_argument("--out", default=str(_OUT))
    # SOURCE SELECTOR (2026-08-05). Sources do NOT deserve equal cadence, because they do not
    # publish at equal rates. arXiv announces once a weekday, so polling it four times cannot
    # mint papers; B站 has a deep back-catalogue that query breadth reaches. Without this flag a
    # dedicated Bilibili run would drag every other source along at Bilibili's cadence, which is
    # exactly the over-polling that took Juejin to 0 new from 80 fetched.
    ap.add_argument("--only", default="", metavar="SRC[,SRC...]",
                    help="restrict to sources: bilibili, cn, foreign, youtube, "
                         "academic, search (default: all)")
    # 3 -> 1, and the number is READ off a like-for-like measurement rather than argued.
    #
    # Bilibili throttles on REQUEST COUNT, and depth is what spends the budget. Measured 2026-08-06
    # on two runs of the same 34 queries, an hour apart:
    #
    #   4 pages/query  ->  ~136 requests, 17 queries productive, 17 SILENTLY REFUSED,   7 new
    #   1 page/query   ->   ~34 requests, 34 queries productive,  0 refused,           43 new
    #
    # The 1-page run went SECOND, against a seen-ledger the 4-page run had already fed, so it faced
    # the strictly harder job -- and still returned 25x more new candidates per request. Three of
    # its queries (因子 有效性 检验, 私募 量化 研究, 回测 幸存者偏差) were among the ones the deep
    # run had refused, and they produced candidates the desk would otherwise never have seen.
    #
    # WHY DEPTH LOSES, and it is not close. Pages 2-4 are the deep tail of ONE query's ranking --
    # mostly the same corpus the seen-ledger already holds, since the ledger is fed by that same
    # query every run. Page 1 of a query the sweep has NOT run is unindexed territory. This is the
    # identical argument BILIBILI_QUERIES already makes for its own width ("breadth of SEARCH, not
    # volume of fetching"), and the depth setting was quietly contradicting it.
    #
    # FALSIFIER: if a 1-page sweep's new-per-request falls below a 2-page sweep's on a like-for-
    # like pair, raise it. Depth is not forbidden, it is currently just the worse buy.
    ap.add_argument("--bili-pages", type=int, default=1, metavar="N",
                    help="Bilibili search pages per query (20 rows/page). Default 1: measured "
                         "25x more new candidates per request than 4, because the source "
                         "throttles on request count and breadth outbuys depth")
    args = ap.parse_args(argv)

    _valid = {"bilibili", "cn", "youtube", "academic", "search", "foreign"}
    only = {s.strip().lower() for s in str(args.only).split(",") if s.strip()}
    unknown = only - _valid
    if unknown:                      # fail loud: a typo'd source must not silently mine nothing
        ap.error(f"unknown --only source(s): {sorted(unknown)}; valid: {sorted(_valid)}")

    def _runs(src: str) -> bool:
        return not only or src in only

    seen = set() if args.all else _load_seen()
    channels = [c.strip() for c in str(args.channels).split(",") if c.strip()]

    queue: list[dict[str, Any]] = []
    blocked: dict[str, str] = {}
    counts: dict[str, int] = {}
    all_ids: set[str] = set()

    # --- Bilibili (B站): WBI-signed search. Scores title+description+tags, which is several
    # times more signal per candidate than a YouTube title alone.
    bili: dict[str, int] = {}
    # BACK OFF FOR THE REST OF THE RUN once the source refuses, exactly as the foreign lane already
    # does for hatena's 429. The 2026-08-06 06:33 sweep pushed 17 further queries into a source
    # that had already started declining -- 68 more signed requests that returned nothing and could
    # only deepen the throttle. Continuing to push a rate limit is how a temporary refusal becomes
    # a durable block (source_health says so in its own threshold comment), and the queries lost
    # here are the TAIL of the list, which is where the newest territory sits.
    bili_refused = ""
    for kw in BILIBILI_QUERIES if _runs("bilibili") else ():
        if bili_refused:
            blocked[f"bilibili:{kw}"] = (
                "bilibili soft-refused earlier in this run -- backed off for the rest of it rather "
                f"than hammering a source that declined ({bili_refused[:90]})")
            continue
        # PAGED. Search returns 20 rows a page and its ranking rotates, so one page re-sampled
        # often is mostly the same corpus seen again; three pages is depth rather than repetition.
        vids: list = []
        err = None
        for pg in range(1, max(1, int(args.bili_pages)) + 1):
            got, e = bilibili.search(kw, page=pg)
            if e:
                # A refusal on page 1 costs the whole query and must be recorded. A refusal on a
                # LATER page keeps the rows already in hand -- but it is still the source declining,
                # so it still arms the backoff. Treating "I got page 1 then it stopped" as a clean
                # run is how the silent-zero defect survived: partial success is not consent.
                err = e if not vids else None
                if "SOFT REFUSAL" in e or "code=" in e:
                    bili_refused = e
                break
            vids.extend(got)
            time.sleep(0.4)
        if err:
            blocked[f"bilibili:{kw}"] = err
            continue
        bili[kw] = len(vids)
        all_ids.update(v.bvid for v in vids)
        for v in vids:
            if v.bvid in seen:
                continue
            s, hits = score_title(v.searchable)
            if s >= args.threshold:
                queue.append({"channel": f"bilibili:{kw}", "video_id": v.bvid,
                              "title": v.title[:160], "score": round(s, 1), "url": v.url,
                              "author": v.author, "views": v.views, "why": hits})
        time.sleep(0.5)

    # --- Chinese article sources: Juejin (掘金) and WeChat via Sogou.
    cn_hits: dict[str, int] = {}
    for kw in CN_ARTICLE_QUERIES if _runs("cn") else ():
        for name, fn in (("juejin", cn_sources.juejin), ("wechat", cn_sources.sogou_weixin)):
            arts, e = fn(kw)
            if e:
                blocked[f"{name}:{kw}"] = e
                continue
            cn_hits[f"{name}:{kw}"] = len(arts)
            for a in arts:
                key = f"{a.source}:{a.ident}"
                all_ids.add(key)
                if key in seen:
                    continue
                s, hits = score_title(a.searchable)
                if s >= args.threshold:
                    queue.append({"channel": f"{a.source}:{kw}", "video_id": key,
                                  "title": a.title[:160], "score": round(s, 1), "url": a.url,
                                  "author": a.author, "why": hits})
            # 1.2s, raised from 0.5 when CN_ARTICLE_QUERIES went 4 -> 22. Sogou rate-limits hard
            # and serves an anti-bot page when pushed, so widening the sweep without slowing it
            # would trade the desk's best-scoring lane for coverage of it.
            time.sleep(1.2)

    # --- NON-CHINESE FOREIGN FORESTS: Japanese, Korean, Russian.
    #
    # A SIBLING OF THE CHINESE LOOP, NOT A SPECIAL CASE. The argument for a Chinese lane -- large,
    # practitioner-authored, invisible to English search -- is language-agnostic, and it was being
    # made for exactly one language while three other crypto-native communities went unindexed.
    # Korean is the sharpest omission: this desk MEASURES the Upbit/Bithumb premium as a mechanism
    # class and had never read a word written by the people creating it.
    #
    # Driven by foreign_sources.SOURCES and .LANGUAGES rather than a hardcoded list, so a fourth
    # language is a table entry and its queries -- never a new branch here.
    foreign_hits: dict[str, int] = {}
    for name, (fn, lang) in (foreign_sources.SOURCES.items() if _runs("foreign") else ()):
        for kw in foreign_sources.LANGUAGES[lang]:
            arts, e = fn(kw)
            if e:
                blocked[f"{name}:{kw}"] = e
                continue
            foreign_hits[f"{name}:{kw}"] = len(arts)
            for a in arts:
                key = f"{a.source}:{a.ident}"
                all_ids.add(key)
                if key in seen:
                    continue
                s_, hits = score_title(a.searchable)
                if s_ >= args.threshold:
                    queue.append({"channel": f"{a.source}:{kw}", "video_id": key,
                                  "title": a.title[:160], "score": round(s_, 1), "url": a.url,
                                  "author": a.author, "why": hits})
            # 1.2s, matching the CN loop. Five sources x ~17 queries is ~85 requests; paced so
            # breadth does not cost the desk a lane it just opened.
            time.sleep(1.2)

    # --- Academic + code. The only sources whose CONTENT is readable: abstracts come back in the
    # API response, so these can produce a finding rather than only a queue entry.
    acad: dict[str, int] = {}
    paper_calls = ([(f"arxiv:{c}", (lambda c=c: papers.arxiv("", category=c, limit=25)))
                    for c in papers.ARXIV_CATEGORIES]
                   + [("ssrn:fin-econ", lambda: papers.ssrn(count=40)),
                      ("openreview", lambda: papers.openreview("quantitative trading")),
                      ("hn", lambda: papers.hackernews("quant trading backtest"))])
    for label, call in paper_calls if _runs("academic") else ():
        items, e = call()
        if e:
            blocked[label] = e
            continue
        acad[label] = len(items)
        for a in items:
            key = f"{a.source}:{a.ident}"
            all_ids.add(key)
            if key in seen:
                continue
            s, hits = score_title(a.searchable)
            if s >= args.threshold:
                queue.append({"channel": label, "video_id": key, "title": a.title[:180],
                              "score": round(s, 1), "url": a.url, "why": hits,
                              "abstract": a.abstract[:400]})
        time.sleep(0.4)

    discovered: dict[str, int] = {}
    for q in SEARCH_QUERIES if _runs("search") else ():
        vids, err = search_youtube(q)
        if err:
            blocked[f"search:{q}"] = err
            continue
        discovered[q] = len(vids)
        all_ids.update(v for v, _ in vids)
        fresh = [(v, t2) for v, t2 in vids if v not in seen]
        for c in triage(fresh, channel=f"search:{q}", threshold=args.threshold):
            queue.append({"channel": f"search:{q}", "video_id": c.video_id, "title": c.title,
                          "score": round(c.score, 1), "url": c.url, "why": list(c.hits)})
        time.sleep(0.8)

    for handle in channels if _runs("youtube") else ():
        vids, err = fetch_channel(handle)
        if err:
            blocked[handle] = err
            continue
        counts[handle] = len(vids)
        all_ids.update(v for v, _ in vids)
        fresh = [(v, t) for v, t in vids if v not in seen]
        for c in triage(fresh, channel=handle, threshold=args.threshold):
            queue.append({"channel": handle, "video_id": c.video_id, "title": c.title,
                          "score": round(c.score, 1), "url": c.url, "why": list(c.hits)})
        time.sleep(0.6)

    # A video can surface from several queries; keep its best-scoring row only.
    best: dict[str, dict[str, Any]] = {}
    for row in queue:
        vid = str(row["video_id"])
        if vid not in best or float(row["score"]) > float(best[vid]["score"]):
            best[vid] = row
    queue = sorted(best.values(), key=lambda r: -float(r["score"]))
    doc = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "status": "MEASURED" if counts else "BLOCKED",
        "captions": {
            "available": False,
            "reason": ("every caption path is blocked from this IP: no captionTracks in the watch "
                       "page, api/timedtext returns 0 bytes, youtube-transcript-api raises "
                       "RequestBlocked. Discovery and ranking work; reading does not."),
            "implication": "the queue names what to paste in; it cannot read it",
        },
        "channels_scanned": counts,
        "search_discovered": discovered,
        "bilibili_discovered": bili,
        "cn_article_discovered": cn_hits,
        "foreign_discovered": foreign_hits,
        "foreign_source_probe": foreign_sources.probe_all() if _runs("foreign") else [],
        "cn_source_probe": cn_sources.probe_all(),
        "academic_discovered": acad,
        "academic_probe": papers.probe_all(),
        "github_token_present": papers.github_token() is not None,
        "ranker_calibration": conversion_ledger.calibration(),
        "channels_blocked": blocked,
        # EVERY BLOCK IS ROUTED TO THE ROUTE-HUNT LEDGER, not just printed. A blocked channel that
        # only ever appears in this run's report is a source the desk wanted, could not reach, and
        # then forgot -- which is how a temporary block quietly becomes an accepted loss (L1.54).
        # `unresolved_blocks()` turns each into owed work and max_audit's `blocked-routes` fence
        # escalates it once it outlives a miner cycle. Recorded per HOST, so seventeen blocked
        # queries against one site are one routing problem rather than seventeen.
        "route_hunts_opened": _open_route_hunts(blocked),
        "threshold": args.threshold,
        "n_new_surfaced": len(queue),
        "queue": queue,   # NOT capped: a cap silently hides the tail of a daily backlog
        "cn_sources": probe_cn(),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False), "utf-8")

    yield_row = _yield_row(doc, seen=seen, only=sorted(only) or ["all"])
    _append_yield(yield_row)

    # SOURCE HEALTH. This report already knows which sources worked and which did not; until
    # 2026-08-05 that knowledge died with the file it was written into, so a source could be
    # blocked for weeks, be re-probed every run, report the same failure every run, and never
    # accumulate into anything the desk could act on. One call folds this run's blocked/ok status
    # into an append-only per-source ledger; scripts/hunt_source_alternatives.py reads it and goes
    # looking for in-class substitutes for whatever has been dead N runs running. Purely additive
    # -- it reads the finished report and changes nothing about what was mined.
    source_health.record_from_report(doc)

    # EDGE INTAKE (2026-08-20 port from claude/wonderful-darwin-7uiobi -- was built there and never
    # reached this branch, so this branch's runs produced NEXT_BATCH_TEST/BLOCKED_PENDING_DATA
    # dispositions nowhere: every discovered row aged out of the queue file on the next sweep with
    # no record it had ever existed, gate items 30/34's exact failure mode). NEVER FATAL -- the
    # queue file and seen ledger are already written by this point, and losing the sweep to a
    # ledger error would cost far more than the missing stamps it is complaining about.
    try:
        from libs.research import edge_intake
        stamped = edge_intake.stamp_queue(out)
        print(f"edge intake: {stamped.get('status')} n={stamped.get('n_stamped')} "
              f"{stamped.get('by_disposition') or ''}")
    except Exception as exc:                     # reported, never fatal
        print(f"edge intake FAILED (non-fatal, queue already written): "
              f"{type(exc).__name__}: {exc}")

    if not args.all:
        _save_seen(seen | all_ids)

    print(f"scanned {sum(counts.values())} videos across {len(counts)} channel(s); "
          f"{len(queue)} new above threshold {args.threshold}")
    for r in queue[:12]:
        print(f"  {r['score']:>5.1f}  {r['channel']:<18} {r['title'][:64]}")
    if blocked:
        print(f"BLOCKED channels: {blocked}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
