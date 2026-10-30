"""Deterministic deepening: a claim's text -> a registered family, instruments and parameters.

    no key, no model, no network -- a missing seat never means zero output

WHY (six-event trace, 2026-09-30). `deepening_worked.jsonl` held 28,686 decided rows and ZERO
candidates; 18,676 of them were BLOCKED_SEAT_UNAVAILABLE because no LLM key reached the worker.
Those rows are not undecidable. A great many of them already say, in words, which instrument and
which mechanism they are about -- "黄金夜盘开盘后的假突破", "ドル円の仲値に向けた上昇",
"пробой азиатского диапазона по золоту" -- and the desk already owns the vocabulary to read them:
`mechanism_claims` resolves instruments in two dozen languages and `miner_candidate_compiler`'s
phrase table maps English mechanism names to price-only families. What was missing was a
multilingual FAMILY lexicon and a door from a match to the compiler.

WHAT THIS EMITS, AND WHY IT IS STILL NOT INVENTING A RULE. A match produces a
`{"kind": "hypothesis", "family": ..., "symbols": [...]}` row -- the STRUCTURED_HYPOTHESIS shape
the compiler already admits from the seats -- labelled `fidelity: rule_based`, carrying the
verbatim span that matched and the phrase that decided the family. The family is only ever one
the compiler's own price-only vocabulary lists AND the registry has; the symbols only ever ones
the universe prices; the parameters only ever the family defaults plus a session or month the
text itself names. The compiler then applies every guard it applies to anything else, and the
ten gates decide. A rule-based cell is a HYPOTHESIS, weaker than a seat's reading and labelled
so; it is never a claim.

TWO FAMILY BASES, NAMED ON EVERY ROW (`family_basis`):
  * `phrase:<phrase>` -- the text names the mechanism (突破, 窓埋め, 평균회귀, пробой ...);
  * `mechanism_class:<class>` -- no mechanism phrase, but `mechanism_claims.extract` found a full
    claim (quantity + direction + horizon) whose class and direction pin a generic family
    (momentum + continuation -> momentum_volgate; reversion -> range_reversion). Weaker, and
    labelled weaker, but a sentence that states quantity, direction and horizon on a priced
    instrument is exactly what the gauntlet exists to falsify.

CULTURE ON EVERY ROW (principal 2026-09-30, final schema): `source_culture` as
"<jurisdiction>/<language>", `participant_structure`, `failure_mode_hypothesis`, `crowding_prior`
-- inferred from the row and the text, UNMEASURED where the evidence is absent, never guessed.
"""
# ruff: noqa: RUF001, E501 -- a multilingual lexicon is made of the characters RUF001 flags, and
# E501 counts a double-width CJK glyph as two columns, so the tables are wrapped by eye.
from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from libs.research import mechanism_claims as mc

#: Bump when the lexicon changes: a row the lexicon could not read is re-offered to it only
#: under a NEW version, so an unchanged lexicon never re-reads the same miss every hour.
LEXICON_VERSION = "2026-09-30.2"

FIDELITY = "rule_based"

#: family -> phrases in every language the desk mines. Every family here is in the compiler's
#: price-only vocabulary (`_FAMILY_VOCAB`); the English phrases are the compiler's own, reused.
FAMILY_LEXICON: dict[str, tuple[str, ...]] = {
    "session_range_breakout": (
        "开盘区间突破", "区间突破", "亚盘突破", "早盘突破", "開盤區間突破", "區間突破",
        "レンジブレイク", "レンジブレイクアウト", "オープニングレンジ", "東京レンジ",
        "레인지 돌파", "시가 범위 돌파", "박스권 돌파", "пробой диапазона", "пробой азиатского",
        "пробой утреннего диапазона", "range breakout", "opening range", "asian range breakout",
        "london breakout", "session breakout", "rompimento de faixa", "ruptura de rango",
        "cassure de range", "range-ausbruch"),
    "failed_breakout": (
        "假突破", "假摔", "诱多", "诱空", "假突破回落", "假突破反转", "假跌破", "誘多", "誘空",
        "ダマシ", "だまし", "フェイクアウト", "가짜 돌파", "거짓 돌파", "휩쏘", "ложный пробой",
        "ложного пробоя", "failed breakout", "false breakout", "fakeout", "bull trap",
        "bear trap", "falso rompimento", "falsa ruptura", "faux breakout", "fehlausbruch"),
    "level_breakout": (
        "突破前高", "突破阻力", "跌破支撑", "突破压力", "突破阻力位", "高値ブレイク", "抵抗線ブレイク",
        "支持線割れ", "저항선 돌파", "지지선 이탈", "пробой уровня", "пробой сопротивления",
        "пробой поддержки", "resistance breakout", "support breakout", "break of structure",
        "breakout above resistance", "rompimento de resistência", "ruptura de resistencia",
        "direnç kırılımı"),
    "monday_gap": ("周一跳空", "週一跳空", "月曜の窓", "月曜日の窓", "월요일 갭", "гэп понедельника",
                   "monday gap", "weekend gap", "sunday gap", "gap de segunda"),
    "overnight_gap_decay": (
        "跳空回补", "缺口回补", "补缺口", "回补缺口", "填补缺口", "回補缺口", "窓埋め", "窓を埋める",
        "갭 메우기", "갭메우기", "갭 하락 후 회복", "закрытие гэпа", "закрытие гэпов",
        "гэп закрывается", "gap fill", "gap fade", "overnight gap", "fading the gap",
        "fechamento de gap", "cierre del gap", "comblement du gap", "gap-schließung"),
    "overnight_drift": ("隔夜收益", "隔夜漂移", "隔夜效应", "オーバーナイトリターン", "오버나잇 수익",
                        "ночной дрейф", "overnight drift", "overnight return", "close to open"),
    "dow_effect": ("星期效应", "周内效应", "曜日効果", "曜日アノマリー", "요일 효과",
                   "эффект дня недели", "day of the week", "day-of-week", "monday effect",
                   "friday effect", "weekday effect", "efeito dia da semana"),
    "turn_of_month": ("月末效应", "月初效应", "月末月初", "月末リバランス", "五十日", "ゴトー日",
                      "월말 효과", "월초 효과", "эффект конца месяца", "turn of the month",
                      "turn-of-the-month", "month-end rebalancing", "month end rebalancing",
                      "virada do mês", "fin de mes"),
    "calendar_month": ("季节性", "季節性", "季節アノマリー", "계절성", "сезонность", "сезонный",
                       "seasonality", "seasonal pattern", "seasonal tendency", "sazonalidade",
                       "historically bullish in month", "historically bearish in month",
                       "estacionalidad", "saisonnalité", "saisonalität", "mevsimsellik"),
    "mean_reversion_rsi": ("rsi超卖", "rsi超买", "rsi背离", "rsi逆張り", "rsi 과매도", "rsi 과매수",
                           "перепроданность rsi", "rsi oversold", "rsi overbought",
                           "rsi divergence", "relative strength index"),
    "mean_reversion_bollinger": ("布林带", "布林線", "布林通道", "ボリンジャーバンド", "볼린저 밴드",
                                 "볼린저밴드", "полосы боллинджера", "боллинджер",
                                 "bollinger band", "bollinger bands", "bandas de bollinger"),
    "volatility_squeeze": ("波动率收缩", "收敛三角", "窄幅整理", "盘整突破", "スクイーズ",
                           "ボラティリティ収縮", "변동성 수축", "스퀴즈", "сжатие волатильности",
                           "volatility squeeze", "bollinger squeeze", "volatility contraction",
                           "narrow range", "inside bar breakout", "compressão de volatilidade"),
    "trend_ma_cross": ("均线金叉", "均线死叉", "金叉", "死叉", "均线交叉", "均線交叉", "ゴールデンクロス",
                       "デッドクロス", "移動平均線のクロス", "골든크로스", "데드크로스", "이동평균 교차",
                       "золотой крест", "пересечение скользящих", "moving average crossover",
                       "ma crossover", "ema crossover", "golden cross", "death cross",
                       "cruzamento de médias", "cruce de medias"),
    "london_close_momentum": ("伦敦收盘", "倫敦收盤", "ロンドンフィックス", "ロンドン引け", "런던 마감",
                              "лондонское закрытие", "london close", "london fix momentum"),
    "asia_momentum": ("亚盘动量", "亚洲盘动量", "東京時間の順張り", "아시아 세션 모멘텀",
                      "азиатская сессия импульс", "asian session momentum", "tokyo momentum"),
    "momentum_volgate": ("动量策略", "动量效应", "順張り", "モメンタム", "모멘텀", "추세추종",
                         "импульсная стратегия", "моментум", "momentum with volatility filter",
                         "volatility-gated momentum", "estratégia de momentum"),
    "range_reversion": ("区间震荡", "箱体震荡", "高抛低吸", "均值回归", "均值回复", "區間震盪", "逆張り",
                        "レンジ相場", "平均回帰", "박스권 매매", "평균회귀", "평균 회귀", "торговля в канале",
                        "возврат к среднему", "флэт", "range trading", "range-bound", "range bound",
                        "mean reversion in a range", "reversão à média", "reversión a la media"),
    "volume_spike": ("放量突破", "成交量激增", "天量", "出来高急増", "出来高急増", "거래량 급증",
                     "всплеск объема", "всплеск объёма", "volume spike", "volume surge",
                     "climax volume", "unusual volume"),
    "pullback_entry": ("回调买入", "回踩", "逢低买入", "回调做多", "回檔買進", "押し目買い", "押し目",
                       "눌림목", "눌림 매수", "покупка на откате", "откат", "pullback entry",
                       "buy the dip", "buy the pullback", "fibonacci retracement",
                       "compra na correção", "comprar en retroceso"),
    "pin_bar_reversal": ("锤子线", "上吊线", "射击之星", "长下影线", "ピンバー", "カラカサ", "핀바",
                         "망치형", "пин-бар", "пинбар", "молот", "pin bar", "pinbar",
                         "hammer candle", "shooting star", "rejection wick"),
    "engulfing_reversal": ("吞没形态", "看涨吞没", "看跌吞没", "包み足", "抱き線", "장악형",
                           "поглощение", "engulfing candle", "bullish engulfing",
                           "bearish engulfing", "engulfing pattern"),
    "ict_fvg": ("流动性猎取", "扫止损", "订单块", "オーダーブロック", "ストップ狩り", "오더블록",
                "유동성 사냥", "охота за стопами", "ордер блок", "fair value gap", "order block",
                "liquidity sweep", "liquidity grab", "smart money concept", "stop hunt"),
    "retail_overlap_reversal": ("散户反向", "散户情绪", "多空比", "個人投資家の逆", "ポジション比率",
                                "개미 반대", "개인 순매수", "позиции розничных трейдеров",
                                "retail sentiment", "contrarian retail", "fade retail",
                                "fade the crowd", "retail positioning", "position ratio"),
    "vol_mean_reversion": ("波动率回归", "ボラティリティの平均回帰", "변동성 평균회귀",
                           "возврат волатильности", "volatility mean reversion", "vol crush",
                           "volatility risk premium"),
    "vol_transition": ("波动率切换", "波动率体制", "ボラティリティ・レジーム", "변동성 국면",
                       "режим волатильности", "volatility regime", "vol regime",
                       "volatility expansion"),
    "drawdown_conditional": ("大跌后买入", "暴跌后反弹", "急落後の買い", "폭락 후 매수",
                             "покупка после падения", "after a drawdown", "buy after decline",
                             "after a selloff"),
    "spread_state": ("点差扩大", "点差收窄", "スプレッド拡大", "스프레드 확대", "расширение спреда",
                     "spread widening", "spread regime", "spread compression"),
    "comex_settlement": ("comex结算", "纽约金结算", "comex settlement", "comex close",
                         "gold settlement"),
}

#: Session words -> the ONE forward engine's window names (compiler `_SESSION_VOCAB`), rendered
#: back into the English phrase the compiler's `_text_params` reads.
SESSION_LEXICON: dict[str, tuple[str, ...]] = {
    "asia": ("亚盘", "亚洲盘", "早盘", "东京时段", "亞洲盤", "東京時間", "東京市場", "アジア時間",
             "아시아 세션", "도쿄 세션", "азиатск", "токийск",
             "asian session", "asia session", "tokyo session", "tokyo open", "asian open"),
    "london_am": ("欧盘", "伦敦开盘", "歐盤", "倫敦開盤", "ロンドン時間", "欧州時間", "ロンドンオープン",
                  "런던 세션", "유럽 세션", "런던 개장", "лондонск", "европейск", "открытие лондона", "london open", "london session", "european open",
                  "european session", "frankfurt open"),
    "ny_open": ("美盘", "纽约开盘", "美盤", "紐約開盤", "ニューヨーク時間", "nyオープン", "뉴욕 세션",
                "미국장 개장", "американская сессия", "нью-йорк", "new york open",
                "ny open", "us open", "new york session", "wall street open"),
    "afternoon": ("尾盘", "午盘", "引け", "후장", "вечерняя сессия", "afternoon session",
                  "late session", "us afternoon"),
}
_SESSION_EN: dict[str, str] = {"asia": "asian session", "london_am": "london open",
                               "ny_open": "new york open", "afternoon": "afternoon session"}

_MONTHS_EN = ("january", "february", "march", "april", "may", "june", "july", "august",
              "september", "october", "november", "december")
_MONTHS_RU = ("январ", "феврал", "март", "апрел", "ма", "июн", "июл", "август", "сентябр",
              "октябр", "ноябр", "декабр")
_CJK_MONTH = re.compile(r"(1[0-2]|[1-9])\s*[月월]")
_CJK_NUM_MONTH = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
                  "十": 10, "十一": 11, "十二": 12}
_CJK_WORD_MONTH = re.compile(r"(十[一二]?|[一二三四五六七八九])月")

#: A generic family a FULL claim may pin when no mechanism phrase does: (class, dir bucket).
CLASS_FALLBACK: dict[tuple[str, str], str] = {
    ("momentum", "continue"): "momentum_volgate", ("momentum", "long"): "momentum_volgate",
    ("momentum", "short"): "momentum_volgate", ("reversion", "revert"): "range_reversion",
    ("reversion", "long"): "range_reversion", ("reversion", "short"): "range_reversion",
    ("microstructure", "revert"): "range_reversion",
}

#: When the claim's class is not one of the two generic ones, its QUANTITY words still pin a
#: family: a breakout claim is a breakout whatever class the sentence was filed under.
QUANTITY_FALLBACK: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("breakout", ("breakout", "突破", "ブレイク", "돌파", "пробой", "rompimento", "ruptura",
                  "cassure", "ausbruch", "kırılım")),
    ("reversion", ("reversal", "mean reversion", "反转", "反轉", "均值回归", "均值回复", "逆張り",
                   "反転", "평균회귀", "반전", "разворот", "возврат к среднему", "reversão",
                   "reversión")),
    ("momentum", ("momentum", "trend", "动量", "趋势", "趨勢", "順張り", "モメンタム", "トレンド",
                  "모멘텀", "추세", "тренд", "импульс", "моментум", "tendência", "tendencia")),
)

_MAX_SYMBOLS = 4
_MAX_FAMILIES = 2

# ------------------------------------------------------------------------------------ culture
#: Language -> the jurisdiction a language's practitioner web overwhelmingly belongs to. Used only
#: when the row names no country or region of its own. English maps to nothing: an English page
#: could be from anywhere, and "US" would be a guess.
LANG_JURISDICTION: dict[str, str] = {
    "zh": "CN", "zh-Hant": "TW", "ja": "JP", "ko": "KR", "ru": "RU", "uk": "UA", "vi": "VN",
    "th": "TH", "id": "ID", "hi": "IN", "de": "DE", "fr": "FR", "it": "IT", "pt": "BR",
    "ar": "AE", "tr": "TR", "he": "IL", "pl": "PL", "nl": "NL", "sv": "SE", "da": "DK",
    "no": "NO", "fi": "FI", "sw": "KE",
}
_LANG_SHORT: dict[str, str] = {"zh-Hant": "zh"}

PARTICIPANT_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("settlement_constrained", ("t+1", "t+0", "交割", "结算", "結算", "満期", "sq", "만기", "экспирац",
                                "settlement", "expiry", "delivery", "liquidación")),
    ("policy_driven", ("央行", "干预", "干預", "政策", "日銀", "介入", "한은", "개입", "цб", "интервенц",
                       "central bank", "intervention", "policy rate", "fomc", "ecb", "boj",
                       "capital control", "banco central")),
    ("physical_flow", ("库存", "现货", "升水", "贴水", "进口", "出口", "現物", "在庫", "재고", "현물",
                       "запас", "физическ", "inventory", "physical", "premium", "import",
                       "export", "shipping", "freight", "harvest")),
    ("tax_driven", ("税", "納税", "nisa", "세금", "양도세", "налог", "tax", "imposto", "impuesto")),
    ("retail_heavy", ("散户", "散戶", "个人投资者", "個人投資家", "개미", "개인투자자", "개인 투자자",
                      "розничн", "частные инвесторы", "retail", "small traders", "varejo")),
    ("broker_specific", ("点差", "掉期", "スプレッド", "スワップ", "브로커", "스왑", "брокер", "своп",
                         "broker", "swap", "spread")),
    ("institutional", ("基金", "机构", "機構", "機関投資家", "기관", "외국인", "институцион", "фонд",
                       "institutional", "fund flows", "rebalancing", "pension")),
)
_STRUCTURAL_CLASSES = frozenset({"policy", "calendar", "positioning", "inventory", "flow",
                                 "carry", "cross_asset", "microstructure"})
_GENERIC_FAMILIES = frozenset({"trend_ma_cross", "mean_reversion_rsi", "mean_reversion_bollinger",
                               "momentum_volgate", "range_reversion", "level_breakout",
                               "pullback_entry", "pin_bar_reversal", "engulfing_reversal"})
_PARTICIPANT_WHY: dict[str, str] = {
    "settlement_constrained": "a settlement or expiry constraint that forces trading on a date",
    "policy_driven": "a local policy authority whose reaction function is its own",
    "physical_flow": "physical supply and import/export flow rather than positioning",
    "tax_driven": "a local tax calendar that dictates when positions are realised",
    "retail_heavy": "a retail-dominated crowd whose risk limits and habits are local",
    "broker_specific": "a venue's own quoting, spread and swap practice",
    "institutional": "local institutional mandates and rebalancing rules",
}


def _rx(phrases: Iterable[str]) -> re.Pattern[str]:
    return mc._alias_rx(tuple(sorted({p.lower() for p in phrases if p})))


def _first(phrases: Iterable[str], low: str) -> str | None:
    m = _rx(phrases).search(low)
    return m.group(0) if m else None


def culture(row: Mapping[str, Any], text: str, lang: str, mclass: str,
            family: str | None) -> dict[str, str]:
    """The four culture fields, inferred from the row first and the text second."""
    low = (text or "").lower()
    lang_s = _LANG_SHORT.get(lang, lang or "")
    jur = ""
    for k in ("country", "jurisdiction", "country_code"):
        v = row.get(k)
        if isinstance(v, str) and 2 <= len(v.strip()) <= 3 and v.strip().isalpha():
            jur = v.strip().upper()
            break
    if not jur and lang in LANG_JURISDICTION:
        jur = LANG_JURISDICTION[lang]
    source_culture = f"{jur}/{lang_s}" if jur and lang_s else "UNMEASURED"
    part, evidence = "UNMEASURED", ""
    for name, terms in PARTICIPANT_TERMS:
        hit = _first(terms, low)
        if hit:
            part, evidence = name, hit
            break
    if lang_s and lang_s != "en":
        crowd = "low" if mclass in _STRUCTURAL_CLASSES else "medium"
    elif lang_s == "en":
        crowd = "high" if (family in _GENERIC_FAMILIES or mclass in ("momentum", "reversion")) \
            else "medium"
    else:
        crowd = "UNMEASURED"
    if part == "UNMEASURED" or source_culture == "UNMEASURED":
        fmh = "UNMEASURED"
    else:
        fmh = (f"The {source_culture} version is driven by "
               f"{_PARTICIPANT_WHY[part]} ('{evidence}'), so it should fail when that local "
               f"constraint changes rather than when the crowded Western "
               f"{family or 'standard'} variant de-leverages.")
    return {"source_culture": source_culture, "participant_structure": part,
            "failure_mode_hypothesis": fmh, "crowding_prior": crowd}


# ------------------------------------------------------------------------------------ reading
def row_text(row: Mapping[str, Any]) -> str:
    """Every field a reader may quote, in order. The same fields the seat is shown."""
    parts: list[str] = []
    for k in ("title", "description", "claim", "text", "summary", "abstract", "body", "content",
              "snippet", "headline", "hypothesis", "mechanism", "notes", "testable_claim"):
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())
    for c in row.get("claims") or []:                 # the crawler's verbatim claim sentences
        if isinstance(c, Mapping) and isinstance(c.get("claim"), str):
            parts.append(c["claim"])
    for k in ("mechanism_tags", "tags", "keywords", "trading_terms"):
        v = row.get(k)
        if isinstance(v, list):
            parts.extend(str(x) for x in v if isinstance(x, (str, int, float)))
    return "\n".join(parts)[:20_000]


def _declared(row: Mapping[str, Any], universe: set[str]) -> list[str]:
    folded = {u.upper(): u for u in universe}
    raw: list[Any] = [row["symbol"]] if row.get("symbol") else []
    for k in ("symbols", "instruments"):
        v = row.get(k)
        if isinstance(v, list):
            raw.extend(v)
    out: list[str] = []
    for v in raw:
        hit = folded.get(str(v).upper().replace("/", "").replace("-", "").strip())
        if hit and hit not in out:
            out.append(hit)
    return out


def _symbols(row: Mapping[str, Any], text: str, universe: set[str]) -> list[str]:
    out = _declared(row, universe)
    folded = {u.upper(): u for u in universe}
    inst = mc.resolve_instruments(text.lower(), universe)
    for s in [*(inst.get("analogues") or []), *(inst.get("indirect") or [])]:
        hit = folded.get(str(s).upper())
        if hit and hit not in out:
            out.append(hit)
    for m in re.finditer(r"(?<![a-z0-9])([a-z]{6})(?![a-z0-9])", text.lower()):
        hit = folded.get(m.group(1).upper())
        if hit and hit not in out:
            out.append(hit)
    return out[:_MAX_SYMBOLS]


def _families(low: str, registered: Callable[[str], bool]) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for fam, phrases in FAMILY_LEXICON.items():
        ph = _first(phrases, low)
        if ph and registered(fam):
            hits.append((fam, ph))
    hits.sort(key=lambda fp: (-len(fp[1]), fp[0]))
    return hits[:_MAX_FAMILIES]


def _session(low: str) -> str | None:
    best: tuple[int, str] | None = None
    for sess, phrases in SESSION_LEXICON.items():
        ph = _first(phrases, low)
        if ph and (best is None or len(ph) > best[0]):
            best = (len(ph), sess)
    return best[1] if best else None


def _month(low: str) -> int | None:
    for i, name in enumerate(_MONTHS_EN, start=1):
        if re.search(rf"(?<![a-z]){name}(?![a-z])", low):
            return i
    m = re.search(r"(?<![a-z])month\s*(1[0-2]|[1-9])(?![0-9])", low)   # "bullish in month 9"
    if m:
        return int(m.group(1))
    m = _CJK_MONTH.search(low)
    if m:
        return int(m.group(1))
    m = _CJK_WORD_MONTH.search(low)
    if m:
        return _CJK_NUM_MONTH.get(m.group(1))
    for i, stem in enumerate(_MONTHS_RU, start=1):
        if stem != "ма" and re.search(rf"(?<![а-я]){stem}", low):
            return i
    return None


def _direction(low: str) -> str | None:
    """"up" / "down" from the claim vocabulary's direction buckets, or None when both/neither."""
    up = _first(mc._DIR_BUCKET_TERMS["long"], low) is not None
    down = _first(mc._DIR_BUCKET_TERMS["short"], low) is not None
    if up == down:
        return None
    return "up" if up else "down"


def _span(text: str, phrase: str) -> str:
    """The verbatim sentence that carries the matched phrase (the evidence), at most 400 chars."""
    low_phrase = phrase.lower()
    for raw in mc._SPLIT.split(text or ""):
        s = re.sub(r"\s+", " ", raw).strip()
        if low_phrase in s.lower():
            return s[:400]
    return phrase


def deepen(row: Mapping[str, Any], universe: set[str], *,
           registered: Callable[[str], bool] = lambda _f: True,
           allowed_families: Iterable[str] | None = None) -> dict[str, Any]:
    """Hypothesis rows the row's own text supports, or the reason it supports none.

    Returns {"hypotheses": [...], "why": str, "lang": str}. Never raises for a malformed row.
    """
    text = row_text(row)
    if not text.strip():
        return {"hypotheses": [], "why": "no text to read", "lang": ""}
    low = text.lower()
    lang = str(row.get("lang") or "") or mc.language_of(text)
    if mc.forbidden_venue(low):
        return {"hypotheses": [], "why": "crypto-exchange venue named (standing order)",
                "lang": lang}
    allow = set(allowed_families) if allowed_families is not None else set(FAMILY_LEXICON)
    symbols = _symbols(row, text, universe)
    if not symbols:
        return {"hypotheses": [], "why": "no instrument the universe prices", "lang": lang}
    fams = [(f, p) for f, p in _families(low, registered) if f in allow]
    basis_kind = "phrase"
    mclass = mc.mechanism_class(low)
    if not fams:
        claims = mc.extract_claims(text, universe=universe, max_claims=5)
        for c in claims:
            dbucket = mc._bucket(mc._DIR_BUCKET_TERMS, list(c.get("direction") or []))
            fam = CLASS_FALLBACK.get((str(c.get("mechanism_class")), dbucket))
            if fam is None and dbucket != "other":
                qlow = " ".join(str(q) for q in (c.get("quantities") or [])).lower()
                for kind, terms in QUANTITY_FALLBACK:
                    if _first(terms, qlow):
                        fam = {"breakout": ("session_range_breakout" if _session(low)
                                            else "level_breakout"),
                               "reversion": "range_reversion",
                               "momentum": "momentum_volgate"}[kind]
                        break
            if fam and fam in allow and registered(fam):
                fams = [(fam, str(c.get("claim") or ""))]
                basis_kind = "mechanism_class"
                mclass = str(c.get("mechanism_class"))
                break
    if not fams:
        return {"hypotheses": [], "lang": lang,
                "why": "instrument named but no mechanism phrase and no full claim"}
    session = _session(low)
    out: list[dict[str, Any]] = []
    tid = str(row.get("deepening_task_id") or "")
    for fam, phrase in fams:
        claim_bits = [f"{fam} on {', '.join(symbols)}"]
        if fam == "session_range_breakout" and session:
            claim_bits.append(f"session: {_SESSION_EN[session]}")
        if fam == "calendar_month":
            month, direction = _month(low), _direction(low)
            if month is None or direction is None:
                continue                                  # not a recipe without both
            claim_bits.append(f"month: {_MONTHS_EN[month - 1]}; bias: "
                              + ("rally" if direction == "up" else "decline"))
        evidence = (_span(text, phrase) if basis_kind == "phrase" else phrase)[:400]
        cult = culture(row, text, lang, mclass, fam)
        hyp: dict[str, Any] = {
            "source": "deepening_rule_based",
            "origin_source": str(row.get("source") or ""),
            "kind": "hypothesis",
            "family": fam,
            "symbols": list(symbols),
            # The compiler's `_text_params` reads the canonical claim (title + testable_claim);
            # the source's own words ride in `evidence` and `source_title`, which it does not read.
            "title": "rule-based deepening: " + "; ".join(claim_bits),
            "testable_claim": "; ".join(claim_bits),
            "source_title": str(row.get("title") or "")[:300],
            "evidence": evidence,
            "family_basis": f"{basis_kind}:{phrase[:80] if basis_kind == 'phrase' else mclass}",
            "fidelity": FIDELITY,
            "served_by": FIDELITY,
            "lexicon_version": LEXICON_VERSION,
            "lang": lang,
            "mechanism_class": mclass,
            **cult,
        }
        if tid:
            hyp["deepening_task_id"] = tid
        for k in ("source_url", "source_id", "ground", "retrieved_at", "content_hash",
                  "url", "region", "country"):
            v = row.get(k)
            if v not in (None, ""):
                hyp.setdefault(k, v)
        hyp["hypothesis_id"] = hashlib.sha256(
            f"{tid}|{fam}|{','.join(symbols)}|{LEXICON_VERSION}".encode()).hexdigest()[:16]
        out.append(hyp)
    if not out:
        return {"hypotheses": [], "lang": lang,
                "why": "calendar family named without both a month and a direction"}
    return {"hypotheses": out, "why": "", "lang": lang}
