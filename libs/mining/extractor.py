"""Records -> typed cells: regex rules out of code and prose, mechanism claims out of any language.

Three readers, chosen by the source's `kind` in the roster:

    code       MQL5/MQL4/Pine/Python source or a code page: indicator calls with their
               arguments (iRSI, iMA, iBands ...), `input` declarations named like parameters,
               the chart constant, session hour filters, and the tells of a rule that reads the
               future (ZigZag / fractals repaint; a negative bar shift reads an unclosed bar)
    text       forum, social, article, video text: the same parameter grammar in prose
               ("RSI(14) below 30", "EMA 12/26 cross", "Bollinger 20, 2"), the named session
               patterns in several languages, and `libs.research.mechanism_claims` for the
               quantity / direction / horizon claims in 26 languages
    mechanics  broker specs, swap schedules, execution policies, prop-firm rules: numeric FACTS
               (swap long/short, commission, max daily loss %, drawdown %, profit target %,
               leverage), published to the mechanics feed for risk and cost models, not cells

Regex is the first pass because it is exact and free. The LLM pass is the existing deepening
worker (`story_mechanism`): a claim that names a mechanism the regex cannot compile is handed to
it verbatim rather than dropped, so the LLM seat reads what the grammar missed.

A record that yields no rule, no claim and no fact is killed at the extract stage with
NO_ECONOMIC_MECHANISM. That is the most common outcome by far, and it is recorded, not hidden.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from libs.research import mechanism_claims as mc

KINDS: frozenset[str] = frozenset({"code", "text", "mechanics"})

_I = re.IGNORECASE
# ------------------------------------------------------------------------------------ code
_IRSI = re.compile(r"\biRSI\s*\(\s*[^,()]*,\s*[^,()]*,\s*(\d{1,3})", _I)
_IMA = re.compile(r"\biMA\s*\(\s*[^,()]*,\s*[^,()]*,\s*(\d{1,3})", _I)
_IBANDS = re.compile(r"\biBands\s*\(\s*[^,()]*,\s*[^,()]*,\s*(\d{1,3})\s*,\s*[^,()]*,\s*"
                     r"(\d+(?:\.\d+)?)", _I)
_INPUT = re.compile(r"\b(?:input|extern)\s+(?:int|double|float|uint|long)\s+(\w+)\s*=\s*"
                    r"(-?\d+(?:\.\d+)?)", _I)
_PERIOD = re.compile(r"\bPERIOD_(M1|M5|M15|M30|H1|H4|D1)\b")
_HOUR = re.compile(r"\b(?:hour|Hour|TimeHour\([^)]*\)|\.hour)\s*(?:>=|==|<=|>|<)\s*(\d{1,2})\b")
_ZIGZAG = re.compile(r"zig\s*zag|\bfractals?\b|iFractals|repaint", _I)
_NEG_SHIFT = re.compile(r"\bi(?:Close|Open|High|Low|Time)\s*\([^)]*,\s*-\s*\d+\s*\)", _I)
# ------------------------------------------------------------------------------------ text
_T_RSI = re.compile(r"\bRSI\s*[\(\[]?\s*(\d{1,3})?\s*[\)\]]?[^.\n]{0,40}?(?:below|under|<|"
                    r"drops? (?:to|below)|oversold(?: at)?|ниже|以下|低于|未満)\s*(\d{1,2})", _I)
_T_RSI_HI = re.compile(r"\bRSI\s*[\(\[]?\s*\d{0,3}\s*[\)\]]?[^.\n]{0,40}?(?:above|over|>|"
                       r"overbought(?: at)?|выше|以上|高于|超え)\s*(\d{2})", _I)
_T_RSI_N = re.compile(r"\bRSI\s*[\(\[]\s*(\d{1,3})\s*[\)\]]|\bRSI\s*(\d{1,3})\b", _I)
_T_MA = re.compile(r"\b(?:EMA|SMA|MA|moving averages?)\s*[\(\[]?\s*(\d{1,3})\s*[\)\]]?\s*"
                   r"(?:/|and|&|x|,|и|和|と)\s*(?:(?:EMA|SMA|MA)\s*)?[\(\[]?\s*(\d{1,3})", _I)
_T_MA2 = re.compile(r"\b(\d{1,3})\s*/\s*(\d{1,3})\s*(?:EMA|SMA|MA)\b", _I)
_T_BB = re.compile(r"\bBollinger(?:\s*Bands?)?\s*[\(\[]?\s*(\d{1,3})\s*[,/ ]\s*"
                   r"(\d(?:\.\d+)?)", _I)
_T_BB_WORD = re.compile(r"\bBollinger|\bBB\b|布林|ボリンジャー|Боллинджер", _I)
_T_TF = re.compile(r"\b(M1|M5|M15|M30|H1|H4|D1)\b(?:\s*chart|\s*timeframe)?")

#: Named session/calendar patterns, multi-language, lowercase. Seeds, never boundaries.
PATTERNS: dict[str, tuple[str, ...]] = {
    "asian_range_breakout": ("asian range", "asia range", "asian session breakout",
                             "tokyo range", "亚盘突破", "亚洲盘区间", "アジア時間", "アジアレンジ",
                             "азиатск"),
    "session_breakout": ("london breakout", "london open breakout", "opening range breakout",
                         "orb ", "伦敦开盘突破", "ロンドンブレイク", "пробой лондон"),
    "monday_gap": ("monday gap", "weekend gap", "gap and go", "周一跳空", "窓埋め逆", "гэп"),
    "monday_gap_fade": ("gap fill", "fill the gap", "fade the gap", "回补缺口", "窓埋め",
                        "закрытие гэпа"),
    "day_of_week": ("day of week", "day-of-week", "monday effect", "friday effect",
                    "星期效应", "曜日", "день недели"),
    "london_close": ("london close", "london fix", "4pm fix", "伦敦收盘", "ロンドンフィックス"),
    "overnight": ("overnight drift", "overnight session", "隔夜", "オーバーナイト", "овернайт"),
    "volume_spike": ("volume spike", "volume surge", "tick volume", "放量", "出来高急増",
                     "всплеск объем"),
    "failed_breakout": ("false breakout", "failed breakout", "fakeout", "stop hunt",
                        "liquidity grab", "假突破", "ダマシ", "ложный пробой"),
    "squeeze": ("squeeze", "volatility contraction", "收窄", "スクイーズ", "сжатие"),
    "range_reversion": ("range trading", "range reversion", "mean reversion in range",
                        "区间震荡", "レンジ逆張り", "торговля в диапазоне"),
    "prev_day_breakout": ("previous day high", "prior day high", "pdh", "yesterday's high",
                          "前日高値", "昨日高点", "максимум прошлого дня"),
    "asia_momentum": ("asia momentum", "asian momentum", "tokyo momentum"),
    "momentum": ("time series momentum", "trend following", "momentum strategy", "动量",
                 "モメンタム", "моментум"),
}

# ------------------------------------------------------------------------------- mechanics
_FACTS: dict[str, re.Pattern[str]] = {
    "max_daily_loss_pct": re.compile(r"(?:max(?:imum)?\s+)?daily\s+(?:loss|drawdown)"
                                     r"[^0-9%]{0,40}(\d{1,2}(?:\.\d+)?)\s*%", _I),
    "max_drawdown_pct": re.compile(r"(?:max(?:imum)?|overall|total)\s+(?:loss|drawdown)"
                                   r"[^0-9%]{0,40}(\d{1,2}(?:\.\d+)?)\s*%", _I),
    "profit_target_pct": re.compile(r"profit\s+target[^0-9%]{0,40}(\d{1,2}(?:\.\d+)?)\s*%",
                                    _I),
    "leverage": re.compile(r"leverage[^0-9]{0,30}1\s*:\s*(\d{1,4})", _I),
    "swap_long": re.compile(r"swap\s*long[^0-9\-]{0,20}(-?\d+(?:\.\d+)?)", _I),
    "swap_short": re.compile(r"swap\s*short[^0-9\-]{0,20}(-?\d+(?:\.\d+)?)", _I),
    "commission_per_lot": re.compile(r"commission[^0-9$€£]{0,40}[$€£]?\s*(\d+(?:\.\d+)?)\s*"
                                     r"(?:per|/)\s*(?:standard\s+)?lot", _I),
    "min_trading_days": re.compile(r"minimum\s+(?:of\s+)?(\d{1,2})\s+trading\s+days", _I),
    "news_trading_restricted": re.compile(r"news\s+trading\s+(?:is\s+)?(?:not\s+allowed|"
                                          r"prohibited|restricted|forbidden)", _I),
    "weekend_holding_restricted": re.compile(r"(?:weekend|over\s*the\s*weekend)\s+holding\s+"
                                             r"(?:is\s+)?(?:not\s+allowed|prohibited)", _I),
}


@dataclass
class Extraction:
    """What one record yielded. Exactly one of rules / claims / facts is usually non-empty."""
    rules: list[dict[str, Any]] = field(default_factory=list)
    claims: list[dict[str, Any]] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)
    language: str = ""
    mechanism_family: str = "other"
    dropped: dict[str, int] = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        return not (self.rules or self.claims or self.facts)


def _f(s: str | None) -> float | None:
    try:
        return float(s) if s not in (None, "") else None
    except ValueError:
        return None


def _i(s: str | None) -> int | None:
    v = _f(s)
    return int(v) if v is not None else None


def _patterns(low: str) -> list[str]:
    return [name for name, words in PATTERNS.items() if any(w in low for w in words)]


def read_code(text: str) -> dict[str, Any]:
    """One rule descriptor from source code. Empty indicators and patterns = no rule."""
    ind: dict[str, dict[str, Any]] = {}
    inputs = {m.group(1).lower(): m.group(2) for m in _INPUT.finditer(text)}
    rsi_n = _IRSI.search(text)
    if rsi_n or any("rsi" in k for k in inputs):
        lo = next((_i(v) for k, v in inputs.items() if "rsi" in k and any(
            t in k for t in ("low", "oversold", "buy", "lower"))), None)
        hi = next((_i(v) for k, v in inputs.items() if "rsi" in k and any(
            t in k for t in ("high", "overbought", "sell", "upper"))), None)
        n = _i(rsi_n.group(1)) if rsi_n else next(
            (_i(v) for k, v in inputs.items() if "rsi" in k and "period" in k), None)
        ind["rsi"] = {"n": n, "lo": lo, "hi": hi}
    ma_periods = [int(m.group(1)) for m in _IMA.finditer(text)]
    fast = next((_i(v) for k, v in inputs.items() if "fast" in k and any(
        t in k for t in ("ma", "ema", "sma", "period"))), None)
    slow = next((_i(v) for k, v in inputs.items() if "slow" in k and any(
        t in k for t in ("ma", "ema", "sma", "period"))), None)
    if fast is None and slow is None and len(set(ma_periods)) >= 2:
        uniq = sorted(set(ma_periods))
        fast, slow = uniq[0], uniq[-1]
    if fast and slow:
        ind["ma"] = {"fast": fast, "slow": slow}
    bands = _IBANDS.search(text)
    if bands:
        ind["bb"] = {"n": _i(bands.group(1)), "k": _f(bands.group(2))}
    elif any("band" in k or k.startswith("bb") for k in inputs):
        ind["bb"] = {"n": next((_i(v) for k, v in inputs.items()
                                if ("band" in k or k.startswith("bb")) and "period" in k), None),
                     "k": next((_f(v) for k, v in inputs.items()
                                if ("band" in k or k.startswith("bb")) and "dev" in k), None)}
    periods = Counter(m.group(1) for m in _PERIOD.finditer(text))
    leaks = []
    if _ZIGZAG.search(text):
        leaks.append("repainting indicator (ZigZag/fractals) used as a signal")
    if _NEG_SHIFT.search(text):
        leaks.append("negative bar shift reads a bar that has not closed")
    return {"indicators": ind, "patterns": _patterns(text.lower()),
            "timeframe": periods.most_common(1)[0][0] if periods else "",
            "hours": sorted({int(h.group(1)) for h in _HOUR.finditer(text)
                             if int(h.group(1)) < 24}),
            "lookahead": leaks}


def read_text(text: str) -> dict[str, Any]:
    """One rule descriptor from prose, using the same grammar as `read_code`."""
    ind: dict[str, dict[str, Any]] = {}
    lo = _T_RSI.search(text)
    hi = _T_RSI_HI.search(text)
    n = _T_RSI_N.search(text)
    if lo or hi:
        ind["rsi"] = {"n": _i((n.group(1) or n.group(2)) if n else None),
                      "lo": _i(lo.group(2)) if lo else None,
                      "hi": _i(hi.group(1)) if hi else None}
    ma = _T_MA.search(text) or _T_MA2.search(text)
    if ma:
        a, b = int(ma.group(1)), int(ma.group(2))
        if a != b:
            ind["ma"] = {"fast": min(a, b), "slow": max(a, b)}
    bb = _T_BB.search(text)
    if bb:
        ind["bb"] = {"n": _i(bb.group(1)), "k": _f(bb.group(2))}
    elif _T_BB_WORD.search(text):
        ind["bb"] = {"n": None, "k": None}
    tfs = Counter(m.group(1) for m in _T_TF.finditer(text))
    leaks = ["repainting indicator (ZigZag/fractals) used as a signal"] \
        if _ZIGZAG.search(text) and ("signal" in text.lower() or "entry" in text.lower()) \
        else []
    return {"indicators": ind, "patterns": _patterns(text.lower()),
            "timeframe": tfs.most_common(1)[0][0] if tfs else "", "hours": [],
            "lookahead": leaks}


def read_facts(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, rx in _FACTS.items():
        m = rx.search(text)
        if not m:
            continue
        out[name] = True if not m.groups() else _f(m.group(1))
    return out


def _has_rule(rule: Mapping[str, Any]) -> bool:
    return bool(rule.get("indicators") or rule.get("patterns") or rule.get("lookahead"))


def extract(record: Mapping[str, Any], *, kind: str = "text",
            universe: set[str] | None = None) -> Extraction:
    """Read one stored record. `kind` comes from the source's roster row."""
    title = str(record.get("title") or "")
    body = str(record.get("body") or "")
    text = f"{title}\n{body}"
    lang = str(record.get("original_language") or "") or mc.language_of(text[:4000])
    out = Extraction(language=lang)
    if kind == "mechanics":
        out.facts = read_facts(text)
        return out
    rule = read_code(text) if kind == "code" else read_text(text)
    inst = mc.resolve_instruments(text.lower()[:20_000], universe)
    syms = list(inst.get("analogues") or []) or list(inst.get("indirect") or [])
    out.mechanism_family = mc.mechanism_class(text[:20_000])
    if _has_rule(rule):
        rule["symbols"] = syms[:3]
        rule["mechanism_family"] = out.mechanism_family
        out.rules.append(rule)
    got = mc.extract(text[:50_000], max_claims=20, universe=universe)
    out.claims = list(got.get("claims") or [])
    out.dropped = {"venue": int(got.get("dropped_venue") or 0),
                   "unmappable": int(got.get("dropped_unmappable") or 0),
                   "duplicate_claims": int(got.get("duplicate_mechanisms") or 0)}
    for c in out.claims:
        # A claim sentence may name its own rule ("RSI(2) below 10 on EURUSD H1, hold 1 day").
        sub = read_text(str(c.get("claim") or ""))
        if _has_rule(sub) and not out.rules:
            sub["symbols"] = list((c.get("instruments") or {}).get("analogues") or syms)[:3]
            sub["mechanism_family"] = str(c.get("mechanism_class") or out.mechanism_family)
            sub["claim"] = c.get("claim")
            out.rules.append(sub)
    return out


def cell_id_for(record_id: str, spec: Mapping[str, Any]) -> str:
    """Unique per (record, executable spec). Mechanism identity is the dedup hash, not this."""
    raw = f"{record_id}|{spec.get('family')}|{sorted((spec.get('params') or {}).items())}|" \
          f"{spec.get('sym')}|{spec.get('timeframe')}"
    return "mc_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
