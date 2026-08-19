"""Rank quant-video candidates by the desk's MEASURED conversion record, not by taste.

WHAT THIS IS AND IS NOT. It is not a transcript miner -- it cannot be. Measured 2026-08-01 from
this box: the channel listing page is reachable and yields video IDs and titles (23 of 23 for one
channel), and EVERY caption path is blocked. The watch page carries no `captionTracks` block,
`api/timedtext` returns zero bytes, and `youtube-transcript-api` raises RequestBlocked. That is a
datacenter-IP block, not a bug, and no amount of retrying fixes it.

So this solves the half that is actually expensive for a human: not reading a transcript, but
deciding WHICH of several hundred videos is worth reading. A channel with 559 videos is not
scannable by hand, and the desk now has a measured record of what converts.

THE PRIOR IS A RECORD, NOT A MODEL. These weights are read off the 2026-08-01 batch, where
roughly thirty transcripts were mined and the outcome of each is known:

  CONVERTED into shipped, tested code or a measurement that changed a constant:
    neurotrader "permutation tests"        -> libs/validation/bar_permutation
    neurotrader "how I develop strategies" -> confirmed the construction defect + thresholds
    neurotrader "intramarket differences"  -> libs/research/intermarket
    neurotrader "trade dependence"         -> libs/research/overlays (conditional adoption)
    Algovibes  "350,000 BTC strategies"    -> the drawdown calibration landmine
    Algovibes  "regime detection tested"   -> libs/validation/lookahead_audit
    Algovibes  "volatility targeting"      -> the largest measured improvement in the batch
    Algovibes  "combined 51 strategies"    -> correlation-of-winners
    Kevin Davey book summaries             -> libs/validation/random_baseline, drawdown_metrics

  CONVERTED NOTHING, despite hours of runtime:
    IQ Capital trader profiles ("$102k/month trader", ex-hedge-fund scalper interview)
    IQ Capital 10,000-trader study (one corroboration, no code)
    AI-agent channels ("8 ways I make money with Claude", "$50k -> $500k with AI trading")

The separating feature is blunt and it is what the weights encode: a source that reports a
MEASUREMENT over many trials, or specifies a PROCEDURE, converts. A source that narrates what a
person does converts nothing. Personal-profit framing in a title is the single strongest negative
signal in the record -- not because such people are lying, but because a claim about one person's
returns contains no number this desk can check against its own data.

THE SCORE IS A QUEUE ORDER, NOT A VERDICT. It ranks what to spend attention on. A high score is
not a promise the video is good, and a low score is not proof it is worthless -- the books video
scored low on these features and still produced two useful pointers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Title/description patterns that PREDICT conversion, with weights from the record above.
#: Large-N measurement is weighted highest because every single large-N source in the batch
#: produced something, and no narrative source did.
POSITIVE = {
    r"\b\d{1,3}[,.]?\d{3,}\s*(back-?tests?|strategies|strategy|trades|accounts|simulations)": 5.0,
    r"\b(permutation|monte[- ]carlo|walk[- ]forward|out[- ]of[- ]sample)\b": 5.0,
    r"\b(deflated sharpe|multiple testing|multiplicity|p-?value|statistical(ly)? significan)": 4.0,
    r"\b(overfit|curve[- ]fit|look[- ]ahead|survivorship|selection bias|data mining bias)\b": 4.0,
    r"\b(i tested|i ran|i back-?tested|does it (actually )?work|fact[- ]check|tested)\b": 3.0,
    r"\b(robust|stability|parameter (sweep|space)|sensitivity)\b": 3.0,
    r"\b(volatility target|position sizing|risk parity|kelly|drawdown|risk of ruin)\b": 3.0,
    r"\b(regime|hidden markov|structural break|non[- ]?stationar)": 2.0,
    r"\b(entropy|hawkes|self[- ]exciting|granger|cointegrat|order flow|microstructure)\b": 2.0,
    r"\b(python|code|implementation|from scratch|walkthrough)\b": 1.0,
    # --- Chinese. NO \b: word boundaries are defined by non-word characters and CJK text has
    # none, so every \b-anchored pattern above silently never matches a Chinese title. That bug
    # scored 102 fetched Bilibili videos at exactly zero and made the source look empty.
    "(回测|樣本外|样本外|滚动回测|前推分析)": 5.0,
    "(置换检验|蒙特卡洛|蒙特卡羅|随机检验)": 5.0,
    "(过拟合|過擬合|曲线拟合|数据挖掘偏差|幸存者偏差)": 4.0,
    "(显著性|统计检验|夏普|夏普比率|信息比率|p值)": 4.0,
    "(实证|实测|测试了|我测试|验证|复现)": 3.0,
    "(回撤|波动率目标|风险平价|仓位管理|凯利)": 3.0,
    "(因子|多因子|阿尔法|alpha挖掘|截面)": 3.0,
    "(高频|微观结构|订单流|做市|套利)": 2.0,
    "(量化|程序化交易|算法交易)": 1.0,
    # --- MT5 / FX / metals / index universe (2026-08-18 mandate). The desk's market is now the
    # full MT5/Fusion universe -- FX, gold, metals, indices, energy, share CFDs -- not crypto. The
    # scorer stays METHODOLOGY-first (a gold walk-forward video already surfaces on the validation
    # terms above), so asset-name-alone is deliberately weak: 1.0 is below the 3.0 floor, so it
    # only LIFTS content that also carries the methodology vocabulary -- a gold study of
    # out-of-sample decay, never a gold hype reel. The MECHANISM terms score 2.0 because COT
    # positioning, carry/swap and session structure ARE the MT5-native economic signals the crypto
    # vocabulary (funding, on-chain, liquidations) never named, and an honest piece titled only
    # "COT positioning in gold" would otherwise score zero and never surface.
    r"\b(gold|xau ?usd|xau|silver|xag|forex|\bfx\b|dxy|dollar index|eur ?usd|gbp ?usd|"
    r"usd ?jpy|aud ?usd|usd ?cad|us500|nas100|us30|spx500|ger40|wti|crude oil|brent|"
    r"natural gas)\b": 1.0,
    r"\b(commitment of traders|\bcot\b|net positioning|positioning report|carry trade|"
    r"interest[- ]rate differential|swap rate|rollover|roll yield|forward points)\b": 2.0,
    r"\b(order block|fair value gap|\bfvg\b|liquidity sweep|market structure|"
    r"break of structure|\bsmc\b|\bict\b|london (open|session)|new york session|"
    r"asian session)\b": 1.0,
    r"\b(nfp|non[- ]?farm|fomc|\bcpi\b|central bank|rate decision|economic calendar|"
    r"metatrader|mt[45]\b|expert advisor|\bmql5\b)\b": 1.0,
    # --- Chinese, MT5 universe (same rationale; NO \b for CJK). Disambiguated to avoid the
    # homograph traps that bit the factor terms: 基差 (basis) / 利差 (differential) / 掉期 (swap)
    # are unambiguous trading compounds.
    "(黄金|外汇|贵金属|白银|股指|原油|美元指数|欧元美元|美元日元)": 1.0,
    "(持仓报告|cftc持仓|净持仓|套息|利差|隔夜利息|掉期|基差 收敛|远期点)": 2.0,
    "(订单块|流动性 扫|公允价值缺口|市场结构|伦敦时段|纽约时段|亚洲时段)": 1.0,
    "(智能交易|mt5|mt4|ea交易|非农|美联储|经济数据 日历)": 1.0,
    # --- Japanese / Korean / Russian / Vietnamese / Turkish (2026-08-18). THIRD instance of the
    # CJK-\b / Sogou failure class: the foreign miner fetches JA/KO/RU/VI/TR forests (1,601 rows in
    # one measured run) and the ranker had NO pattern in any of those scripts, so every title scored
    # 0 and the whole lane surfaced nothing -- a scorer blindspot read as an empty source. NO \b for
    # kana/hangul/cyrillic (no word boundaries, same as CJK); Latin VI/TR terms are the diacritic
    # ones English misses. Methodology (the desk's highest-converting register) weighted 4, market
    # and MT5-mechanism context 2.
    "(バックテスト|検証|検定|アウトオブサンプル|サンプル外|過学習)": 4.0,
    "(過剰最適化|ウォークフォワード|前進分析|生存者バイアス|モンテカルロ|有意性)": 4.0,
    "(ゴールド|為替|外国為替|貴金属|株価指数|原油)": 2.0,
    "(自動売買|スワップ|キャリー|金利差|建玉|セッション)": 2.0,
    "(백테스트|검증|검정|표본외|과최적화|과적합|워크포워드|생존편향|몬테카를로|유의성)": 4.0,
    "(골드|외환|환율|귀금속|주가지수|원유|자동매매|스왑|캐리|금리차|미결제약정|세션)": 2.0,
    "(бэктест|вне выборки|переобучение|переоптимизац)": 4.0,
    "(форвардный анализ|выживш|монте-карло|значимость)": 4.0,
    "(золото|форекс|валют|металл|индекс|нефть|советник|своп|кэрри|сессия|позиц)": 2.0,
    "(kiểm định|ngoài mẫu|quá khớp|tối ưu hóa quá mức|thiên lệch kẻ sống sót)": 4.0,
    "(vàng|ngoại hối|kim loại|chỉ số|vị thế|phiên giao dịch)": 2.0,
    "(örneklem dışı|aşırı optimizasyon|aşırı uyum|hayatta kalma yanlılığı|geriye dönük test)": 4.0,  # noqa: RUF001
    "(altın|döviz|endeks|emtia|pozisyon|seans)": 2.0,  # noqa: RUF001
    # --- Academic phrasing. Abstracts state what was measured and how, which is the category
    # with this desk's best conversion record -- but they say it in different words than a video
    # title does, so without these a paper feed ranks below a YouTube tutorial.
    r"\b(we (document|show|find|propose|develop|test)|this paper|we study)\b": 3.0,
    r"\b(sample of|cross[- ]section|panel of|we use .{0,20}(observations|firms|stocks))": 4.0,
    r"\b(statistical(ly)? (significan|test)|null hypothesis|bootstrap|t-statistic)\b": 4.0,
    r"\b(data snooping|multiple hypothesis|false discovery|reality check|white'?s)\b": 5.0,
    r"\b(transaction costs?|net of (fees|costs)|implementation shortfall|capacity)\b": 3.0,
    r"\b(leakage|lookahead|point[- ]in[- ]time|survivorship)\b": 4.0,
}

#: Patterns that predict NOTHING converts. The profit-claim family is weighted hardest because it
#: has a perfect zero-conversion record across the batch.
NEGATIVE = {
    r"(\$[\d,]+\s*(/|per\s*)?(month|day|year|week))|\b(\d+%\s*(a|per)\s*(month|week|day))\b": -6.0,
    r"\b(made (me|him|her|\$)|turned \$|profit|rich|millionaire|income|payout)\b": -4.0,
    r"\b(secret|guru|insane|crazy|shocking|nobody tells|they don'?t want)\b": -3.0,
    r"\b(course|masterclass|blueprint|mentorship|signals? group|discord)\b": -3.0,
    r"\b(ai agent|agents?|automat\w+ (income|money)|claude code|chatgpt|gpt-?\d)\b": -3.0,
    r"\b(prop firm|funded account|challenge|scalping strategy ever)\b": -2.0,
    r"\b(best|ultimate|only|#1|top \d+)\b.*\b(strategy|indicator)\b": -2.0,
    r"\b(my (journey|story)|how i (started|quit)|interview|reveals?)\b": -2.0,
    # --- Chinese negatives. The Bilibili quant results are dominated by course-funnel uploads
    # ("108集", "保姆级教程", "B站最全"), which is the same narrative/marketing category that
    # converted zero times in the 2026-08-01 batch.
    "(保姆级|零基础|入门教程|手把手|从入门到|全套教程|\\d+集)": -5.0,
    "(最全|天花板|强推|一条龙|白嫖|附源码|资料领取|私信)": -4.0,
    "(月入|暴富|翻倍|躺赚|稳赚|财富自由|割韭菜)": -6.0,
    "(培训|课程|报名|加微信|加群|领取)": -4.0,
    # --- CJK HOMOGRAPH TRAPS, third of this family (after the missing-\b bug and the Sogou
    # attribute-order bug). The CJK positives above are bare substrings, which is correct --
    # Chinese has no word boundaries to anchor on -- but it means a term scores wherever its
    # characters appear, including inside an unrelated compound. Measured 2026-08-05 on a live
    # Juejin pull: "使用OATH Toolkit实现ssh登录时进行TOTP双因子认证" scored 6.0 and would have
    # surfaced, because 因子 (factor) sits inside 双因子认证 (two-FACTOR authentication) and
    # 验证 (validate) reads as "authenticate" in that domain. Same shape for 生长因子/转录因子
    # in biology. These are domain disambiguators, not quality judgements: an authentication
    # or biology article is not a weak quant article, it is a different subject entirely.
    # Weighted to cancel the two positives it rides on (3+3) with margin, so the compound has to
    # be outscored by genuine quant terms elsewhere in the text rather than merely tied.
    "(双因子认证|双因素认证|二次验证|两步验证|身份验证|登录验证|otp|totp)": -8.0,
    "(转录因子|生长因子|凝血因子|遗传因子|致病因子)": -8.0,
}

#: Below this, the queue does not surface it. Set so the batch's known non-converters fall out
#: while its known converters stay in -- an in-sample threshold, and labelled as such.
SURFACE_THRESHOLD = 3.0


@dataclass(frozen=True)
class Candidate:
    video_id: str
    title: str
    channel: str = ""
    score: float = 0.0
    hits: tuple[str, ...] = field(default_factory=tuple)

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


def score_title(text: str) -> tuple[float, list[str]]:
    """Score one title/description. Returns (score, matched-pattern descriptions).

    HITS ARE RETURNED so the queue can show WHY something ranked, which is the difference between
    a list a human trusts and one they ignore. A ranking with no visible reason gets overridden by
    whatever the reader already believed.
    """
    t = text.lower()
    total = 0.0
    hits: list[str] = []
    for pat, w in POSITIVE.items():
        if re.search(pat, t):
            total += w
            hits.append(f"+{w:g} {_label(pat)}")
    for pat, w in NEGATIVE.items():
        if re.search(pat, t):
            total += w
            hits.append(f"{w:g} {_label(pat)}")
    return total, hits


def triage(
    videos: list[tuple[str, str]], *, channel: str = "", threshold: float = SURFACE_THRESHOLD
) -> list[Candidate]:
    """Score and rank (video_id, title) pairs, keeping only those above the threshold."""
    out = []
    for vid, title in videos:
        s, hits = score_title(title)
        if s >= threshold:
            out.append(Candidate(video_id=vid, title=title, channel=channel,
                                 score=s, hits=tuple(hits)))
    return sorted(out, key=lambda c: (-c.score, c.title))


def _label(pattern: str) -> str:
    """A short human tag for a regex, so the queue explains itself without printing regexes."""
    key = re.sub(r"[\\\\^$.|?*+()\[\]{}]", "", pattern)[:44]
    return key.replace(r"\b", "").replace("  ", " ").strip(" |")
