"""Mechanism claims out of text in the languages the desk mines -- English and Chinese first.

    a CLAIM  =  a sentence that names a market QUANTITY, a DIRECTION and a HORIZON

That is the whole grammar, and it is deliberately shallow. A trader's interview, a competition
write-up, a forum reply or a README does not state a family and parameters; it states that
"gold usually reverses after the night-session open when the day range is already wide", and
the value of the sentence is that it is FALSIFIABLE on bars the desk already holds. Everything
richer than this -- the exact rule, the parameters, the instrument mapping -- is the deepening
worker's job, through the compiler's existing contract, so nothing here can invent a family.

WHY CHINESE VOCABULARY IS FIRST-CLASS. The deep Chinese web (七禾网 and 期货日报 interviews,
competition records, 聚宽/优矿/米筐 communities, 知乎/CSDN/雪球, Gitee, Bilibili transcripts,
the quant forums) holds a large practitioner literature the English-speaking crowd never reads,
and even a dubious trading story names a testable mechanism. A claim extractor that only speaks
English would report that forest as empty, which is the L1.28a failure: absence indistinguishable
from emptiness.

INSTRUMENTS ARE MAPPED, NEVER INVENTED. A story about 沪金 is a story about gold; the desk trades
XAUUSD. Chinese futures with no MT5 analogue (螺纹钢, 铁矿石, 豆粕 ...) are kept as MECHANISM-CLASS
transfers -- the mechanism is the fuel, the instrument is whatever the desk can actually quote --
and the row says so. Crypto-EXCHANGE claims are dropped at the door (standing order 2026-08-18);
Fusion's crypto CFDs remain reachable through their own aliases.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

# --------------------------------------------------------------------------- the vocabulary
QUANTITY_EN: tuple[str, ...] = (
    "momentum", "reversal", "mean reversion", "carry", "swap", "breakout", "range",
    "volatility", "spread", "order flow", "imbalance", "positioning", "cot", "seasonal",
    "session", "open", "close", "fix", "rollover", "gap", "correlation", "cointegration",
    "pairs", "lead", "lag", "surprise", "cpi", "nfp", "rate", "yield", "factor", "residual",
    "skew", "kurtosis", "liquidity", "flow", "inventory", "basis", "term structure", "premium",
    "drawdown", "trend", "pullback", "stop hunt", "sweep", "vwap", "volume",
)
QUANTITY_ZH: tuple[str, ...] = (
    "动量", "反转", "均值回归", "均值回复", "趋势", "突破", "假突破", "套利", "基差", "价差",
    "持仓",
    "成交量", "量能", "波动率", "跳空", "缺口", "隔夜", "夜盘", "开盘", "收盘", "换月", "展期",
    "升水", "贴水", "利差", "掉期", "隔夜利息", "季节性", "时段", "资金流", "主力", "库存",
    "期限结构", "相关性", "协整", "领先", "滞后", "非农", "通胀", "加息", "降息", "利率",
    "美元指数", "流动性", "订单流", "盘口", "委托", "止损", "日内", "波段", "高频", "做市",
    "滑点", "冲击成本", "量价", "放量", "缩量", "振幅", "均线", "布林", "回撤", "回调", "反弹",
    "跨期", "跨品种", "跨市", "内外盘", "沪伦比", "金银比", "金油比", "持仓量", "多空比",
    "黄金", "白银", "原油", "铜", "股指", "外汇", "美元", "欧元", "英镑", "日元", "澳元", "恒指",
    "纳指", "标普", "道指", "德指", "日经", "汇率", "点差", "atr", "rsi", "macd", "kdj",
)
DIRECTION_EN: tuple[str, ...] = (
    "long", "short", "buy", "sell", "fade", "follow", "revert", "continue", "increase",
    "decrease", "predict", "forecast", "outperform", "underperform", "positive", "negative",
    "rally", "sell-off", "selloff", "bounce", "reverse", "expand", "contract", "widen", "narrow",
)
DIRECTION_ZH: tuple[str, ...] = (
    "做多", "做空", "买入", "卖出", "反向", "顺势", "逆势", "回归", "延续", "上涨", "下跌", "预测",
    "跑赢", "跑输", "正相关", "负相关", "追涨", "杀跌", "抄底", "摸顶", "止盈", "加仓", "减仓",
    "多头", "空头", "看多", "看空", "走强", "走弱", "收敛", "扩大", "反弹", "回落", "冲高", "跳水",
    "涨", "跌", "收窄", "拉升", "砸盘", "平仓", "开仓", "入场", "出场",
)
HORIZON_EN: tuple[str, ...] = (
    "minute", "minutes", "hour", "hours", "hourly", "daily", "day", "days", "week", "weekly",
    "month", "monthly", "intraday", "overnight", "bar", "bars", "h1", "h4", "d1", "m5", "m15",
    "session", "open", "close", "tick",
)
HORIZON_ZH: tuple[str, ...] = (
    "分钟", "小时", "日内", "隔夜", "当日", "次日", "每日", "日线", "周线", "月线", "开盘后",
    "收盘前", "夜盘", "早盘", "尾盘", "根k线", "交易日", "一周", "一个月", "tick", "秒级",
    "分钟级", "小时级", "日级", "周", "月",
)

_CJK = re.compile(r"[一-鿿]")

# SIBLING FORESTS (JP / KR / RU), same grammar, smaller seed vocabularies. The crawler already
# reads these languages for LINKS; without claim vocabulary their stories were being carried as
# prose and never reached the worker. Seeds, never boundaries: a region's frontier seat extends
# its own list (docs/research/search_operator_library.md OP-041).
QUANTITY_JA: tuple[str, ...] = (
    "モメンタム", "逆張り", "順張り", "トレンド", "ブレイク", "裁定", "スプレッド",
    "ボラティリティ", "窓", "ギャップ", "スワップ", "キャリー", "出来高", "建玉", "季節", "時間帯",
    "仲値", "ゴールド",
    "金", "原油", "ドル円", "ユーロドル", "日経", "ロンドン", "ニューヨーク", "指標", "雇用統計",
)
DIRECTION_JA: tuple[str, ...] = (
    "買い", "売り", "ロング", "ショート", "上昇", "下落", "反発", "反落", "続伸", "続落", "戻る",
    "上抜け", "下抜け", "利確", "損切り",
)
HORIZON_JA: tuple[str, ...] = ("分", "時間", "日", "週", "月", "デイトレ", "スイング", "足", "寄り",
                               "引け", "オーバーナイト", "日中")
QUANTITY_KO: tuple[str, ...] = (
    "모멘텀", "추세", "돌파", "역추세", "평균회귀", "차익", "스프레드", "변동성", "갭", "스왑",
    "캐리",
    "거래량", "포지션", "계절", "세션", "금", "골드", "원유", "달러", "엔", "지수", "고용",
)
DIRECTION_KO: tuple[str, ...] = ("매수", "매도", "롱", "숏", "상승", "하락", "반등", "급락", "돌파",
                                 "이탈", "익절", "손절")
HORIZON_KO: tuple[str, ...] = ("분", "시간", "일", "주", "월", "데이", "스윙", "봉", "장초",
                               "장마감", "오버나잇", "장중")
QUANTITY_RU: tuple[str, ...] = (
    "моментум", "импульс", "разворот", "возврат к среднему", "тренд", "пробой", "арбитраж",
    "спред", "волатильност", "гэп", "своп", "кэрри", "объем", "объём", "позици", "сезонн",
    "сесси", "золот", "нефт", "доллар", "евро", "индекс", "фиксинг", "ставк", "нонфарм",
)
DIRECTION_RU: tuple[str, ...] = ("лонг", "шорт", "покуп", "прода", "рост", "падени", "отскок",
                                 "продолж", "пробит", "фиксац", "стоп")
HORIZON_RU: tuple[str, ...] = ("минут", "час", "дне", "день", "недел", "месяц", "интрадей",
                               "свинг", "свеч", "открыти", "закрыти", "овернайт")

_KANA = re.compile(r"[\u3040-\u30ff]")
_HANGUL = re.compile(r"[\uac00-\ud7af]")
_CYRILLIC = re.compile(r"[\u0400-\u04ff]")


def language_of(text: str) -> str:
    """zh / ja / ko / ru / en by script; Japanese wins over zh when kana is present."""
    if _KANA.search(text or ""):
        return "ja"
    if _HANGUL.search(text or ""):
        return "ko"
    if _CJK.search(text or ""):
        return "zh"
    if _CYRILLIC.search(text or ""):
        return "ru"
    return "en"


#: Crypto-exchange-native ground is never hunted (principal, 2026-08-18). Any claim naming one of
#: these is dropped and COUNTED; the count is on the report so the fence is visible, not silent.
FORBIDDEN_VENUES: tuple[str, ...] = (
    "binance", "bybit", "okx", "okex", "huobi", "htx", "hyperliquid", "bitget", "gate.io",
    "kucoin", "deribit", "coinbase", "kraken", "币安", "欧易", "火币", "抹茶", "资金费率",
    "funding rate", "永续合约", "perpetual", "perp ", "合约爆仓", "现货杠杆", "u本位", "币本位",
)

#: Chinese / English instrument aliases -> MT5 candidate symbols, most likely broker name first.
#: Resolved against the live universe at run time; the FIRST candidate is the analogue when the
#: universe is unknown. An empty tuple means "no MT5 analogue -- mechanism-class transfer only".
INSTRUMENT_ALIASES: tuple[tuple[tuple[str, ...], tuple[str, ...], str], ...] = (
    (("黄金", "沪金", "au9999", "au(t+d)", "伦敦金", "金价", "gold", "xauusd", "comex黄金"),
     ("XAUUSD",), "metals"),
    (("白银", "沪银", "伦敦银", "银价", "silver", "xagusd"), ("XAGUSD",), "metals"),
    (("铂金", "platinum", "xptusd"), ("XPTUSD",), "metals"),
    (("钯金", "palladium", "xpdusd"), ("XPDUSD",), "metals"),
    (("铜", "沪铜", "伦铜", "copper", "xcuusd"), ("XCUUSD", "COPPER", "HG"), "metals"),
    (("原油", "布油", "美原油", "sc原油", "wti", "brent", "crude"),
     ("XTIUSD", "USOIL", "WTI", "XBRUSD", "UKOIL", "BRENT"), "energy"),
    (("天然气", "natural gas", "natgas"), ("XNGUSD", "NATGAS", "NGAS"), "energy"),
    (("沪深300", "if合约", "股指期货", "a股", "上证", "中证500", "ic合约", "ih合约", "im合约",
      "a50", "富时中国", "china a50"), ("CN50", "CHINA50", "CHINAA50", "CHINA A50"), "indices"),
    (("恒指", "恒生", "港股", "hsi"), ("HK50", "HSI", "HK50USD"), "indices"),
    (("纳指", "纳斯达克", "nasdaq", "nas100", "ustec"), ("NAS100", "USTEC", "NDX100"), "indices"),
    (("标普", "s&p", "spx", "us500", "美股"), ("US500", "SPX500"), "indices"),
    (("道指", "dow", "us30"), ("US30", "DJ30"), "indices"),
    (("德指", "dax", "ger40", "de40"), ("GER40", "DE40", "GER30"), "indices"),
    (("日经", "nikkei", "jp225", "日股"), ("JPN225", "JP225"), "indices"),
    (("富时", "ftse", "uk100"), ("UK100",), "indices"),
    (("欧元", "欧美", "eurusd"), ("EURUSD",), "fx"),
    (("英镑", "镑美", "gbpusd"), ("GBPUSD",), "fx"),
    (("日元", "美日", "usdjpy"), ("USDJPY",), "fx"),
    (("澳元", "澳美", "audusd"), ("AUDUSD",), "fx"),
    (("加元", "美加", "usdcad"), ("USDCAD",), "fx"),
    (("瑞郎", "美瑞", "usdchf"), ("USDCHF",), "fx"),
    (("纽元", "nzdusd"), ("NZDUSD",), "fx"),
    (("美元指数", "dxy", "dollar index", "usdx"), ("DXY", "USDX", "USDOLLAR"), "fx"),
    (("人民币", "离岸人民币", "usdcnh", "cnh"), ("USDCNH",), "fx"),
    (("比特币", "bitcoin", "btcusd"), ("BTCUSD",), "crypto_cfd"),
    (("以太坊", "ethereum", "ethusd"), ("ETHUSD",), "crypto_cfd"),
    # JP / KR / RU aliases for the same instruments
    (("ゴールド", "金相場", "골드", "золот"), ("XAUUSD",), "metals"),
    (("ドル円", "달러엔", "доллар иена", "usdjpy"), ("USDJPY",), "fx"),
    (("ユーロドル", "유로달러", "евродоллар", "eurusd"), ("EURUSD",), "fx"),
    (("日経225", "日経平均", "닛케이"), ("JPN225", "JP225"), "indices"),
    (("코스피", "kospi"), (), "cn-equities-only"),
    (("нефть", "브렌트", "브렌트유", "wti"), ("XTIUSD", "USOIL", "XBRUSD", "UKOIL"), "energy"),
    (("大豆", "soybean"), ("SOYBEAN", "SOYBEANS", "ZS"), "softs"),
    (("玉米", "corn"), ("CORN", "ZC"), "softs"),
    (("白糖", "sugar"), ("SUGAR", "SB"), "softs"),
    (("棉花", "cotton"), ("COTTON", "CT"), "softs"),
    (("咖啡", "coffee"), ("COFFEE", "KC"), "softs"),
    (("小麦", "wheat"), ("WHEAT", "ZW"), "softs"),
    (("可可", "cocoa"), ("COCOA",), "softs"),
    # NO MT5 ANALOGUE: the mechanism transfers to the class, the instrument does not.
    (("螺纹钢", "螺纹", "热卷", "铁矿石", "铁矿", "焦炭", "焦煤", "动力煤"), (), "metals/energy"),
    (("甲醇", "pta", "乙二醇", "纯碱", "玻璃", "尿素", "沥青", "橡胶", "pvc", "pp", "塑料"),
     (), "energy"),
    (("豆粕", "菜油", "菜粕", "棕榈油", "豆油", "鸡蛋", "生猪", "苹果", "红枣", "花生"), (),
     "softs"),
    (("碳酸锂", "工业硅", "氧化铝", "沪镍", "沪锌", "沪铝", "沪锡", "沪铅"), (), "metals"),
    (("国债期货", "十债", "五债", "二债"), (), "rates->fx carry"),
    (("可转债", "转债", "打新", "涨停", "跌停", "龙虎榜", "北向资金"), (), "cn-equities-only"),
)

# Sentence enders: ASCII plus the full-width ideographic stop, bang, question and semicolon
# (U+3002, U+FF01, U+FF1F, U+FF1B), written as escapes so the linter does not read them as typos.
_SPLIT = re.compile("(?<=[.!?\u3002\uff01\uff1f\uff1b;])\\s*|\\n+")
_PERF: tuple[tuple[str, str], ...] = (
    ("return_pct", r"(?:收益率?|年化(?:收益)?|盈利|return(?:s)?|annual(?:ised|ized)?)"
                   r"\D{0,12}?(-?\d+(?:\.\d+)?)\s*%"),
    ("drawdown_pct", r"(?:最大回撤|回撤|drawdown)\D{0,12}?(-?\d+(?:\.\d+)?)\s*%"),
    ("sharpe", r"(?:夏普(?:比率)?|sharpe)\D{0,12}?(-?\d+(?:\.\d+)?)"),
    ("win_rate_pct", r"(?:胜率|win rate)\D{0,12}?(\d+(?:\.\d+)?)\s*%"),
    ("profit_factor", r"(?:盈亏比|profit factor)\D{0,12}?(\d+(?:\.\d+)?)"),
)


def is_cjk(text: str) -> bool:
    return bool(_CJK.search(text or ""))


def _hits_en(words: tuple[str, ...], low: str) -> list[str]:
    return [w for w in words if re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", low)]


def _hits_zh(words: tuple[str, ...], low: str) -> list[str]:
    return [w for w in words if w in low]


def forbidden_venue(text: str) -> str | None:
    """The first crypto-exchange token the text names, or None."""
    low = (text or "").lower()
    for v in FORBIDDEN_VENUES:
        if v in low:
            return v
    return None


def performance(text: str) -> dict[str, float]:
    """Stated performance numbers. A STORY'S NUMBERS ARE EVIDENCE ABOUT THE STORY, NOT ABOUT THE
    MECHANISM -- they are kept so the reader can weigh the claim, never used as a prior."""
    out: dict[str, float] = {}
    low = (text or "").lower()
    for name, rx in _PERF:
        m = re.search(rx, low)
        if m:
            try:
                out[name] = float(m.group(1))
            except ValueError:
                continue
    return out


def resolve_instruments(text: str, universe: set[str] | None = None) -> dict[str, Any]:
    """MT5 analogues for every instrument the text names, and the transfer-only classes."""
    low = (text or "").lower()
    analogues: list[str] = []
    mentioned: list[str] = []
    transfer: list[str] = []
    uni = {u.upper() for u in (universe or set())}
    for aliases, cands, cls in INSTRUMENT_ALIASES:
        hit = next((a for a in aliases if a in low), None)
        if hit is None:
            continue
        mentioned.append(hit)
        if not cands:
            transfer.append(f"{hit}->{cls}")
            continue
        chosen = next((c for c in cands if c.upper() in uni), None) if uni else cands[0]
        if chosen is None and not uni:
            chosen = cands[0]
        if chosen and chosen not in analogues:
            analogues.append(chosen)
        elif chosen is None:
            transfer.append(f"{hit}->{cls} (not quoted here)")
    return {"analogues": analogues, "mentioned": mentioned, "transfer_only": transfer}


#: Per-language (quantity, direction, horizon) seeds; English is always searched as well.
_VOCAB: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    "zh": (QUANTITY_ZH, DIRECTION_ZH, HORIZON_ZH),
    "ja": (QUANTITY_JA + QUANTITY_ZH, DIRECTION_JA + DIRECTION_ZH, HORIZON_JA + HORIZON_ZH),
    "ko": (QUANTITY_KO, DIRECTION_KO, HORIZON_KO),
    "ru": (QUANTITY_RU, DIRECTION_RU, HORIZON_RU),
}


def extract_claims(text: str, *, max_claims: int = 40,
                   universe: set[str] | None = None) -> list[dict[str, Any]]:
    """Sentences naming a quantity, a direction and a horizon -- verbatim, never paraphrased.

    Returns the claims and nothing else; the venue drops are available through
    `extract_claims_with_drops` for a report that must show the fence working.
    """
    return extract_claims_with_drops(text, max_claims=max_claims, universe=universe)[0]


def extract_claims_with_drops(text: str, *, max_claims: int = 40,
                              universe: set[str] | None = None
                              ) -> tuple[list[dict[str, Any]], int]:
    out: list[dict[str, Any]] = []
    dropped = 0
    seen: set[str] = set()
    # THE DOCUMENT NAMES THE INSTRUMENT ONCE. "I have traded Shanghai gold for seven years" is
    # sentence one; the mechanism is sentence three and says "it". A claim that names no
    # instrument inherits the document's, marked as context so the reader knows it was inherited.
    doc_inst = resolve_instruments((text or "").lower(), universe)
    for raw in _SPLIT.split(text or ""):
        s = re.sub(r"\s+", " ", raw).strip()
        if not s:
            continue
        lang = language_of(s)
        cjk = lang in ("zh", "ja", "ko")
        lo, hi = (10, 400) if cjk else (20, 400)
        if not (lo <= len(s) <= hi):
            continue
        low = s.lower()
        if forbidden_venue(low):
            dropped += 1
            continue
        qv, dv, hv = _VOCAB.get(lang, (QUANTITY_EN, DIRECTION_EN, HORIZON_EN))
        q = _hits_zh(qv, low) + _hits_en(QUANTITY_EN, low)
        d = _hits_zh(dv, low) + _hits_en(DIRECTION_EN, low)
        h = _hits_zh(hv, low) + _hits_en(HORIZON_EN, low)
        if not (q and d and h):
            continue
        digest = hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]
        if digest in seen:
            continue
        seen.add(digest)
        inst = resolve_instruments(low, universe)
        inherited = False
        if not inst["analogues"] and not inst["transfer_only"] and (
                doc_inst["analogues"] or doc_inst["transfer_only"]):
            inst = {**doc_inst, "from_context": True}
            inherited = True
        out.append({"claim": s, "lang": lang, "quantities": q[:4],
                    "direction": d[:2], "horizon": h[:2], "instruments": inst,
                    "instrument_from_context": inherited,
                    "claimed_performance": performance(s), "claim_hash": digest})
        if len(out) >= max_claims:
            break
    return out, dropped


def claim_score(c: dict[str, Any]) -> float:
    """How much a claim is worth reading FIRST. Resolved instrument and a stated horizon beat a
    vague story; stated numbers add a little, because they at least make the story checkable."""
    s = 1.0
    if c.get("instruments", {}).get("analogues"):
        s += 1.0
    if c.get("instruments", {}).get("transfer_only"):
        s += 0.25
    if len(c.get("quantities") or []) >= 2:
        s += 0.5
    if c.get("claimed_performance"):
        s += 0.25
    return s
