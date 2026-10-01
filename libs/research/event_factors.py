"""EVENT / POLICY FACTORS -- the SIGNED half the event ontology deliberately does not carry.

`libs.research.event_ontology` says WHAT KIND of thing happened and WHO it reached, and refuses on
principle to store a sign: gold rises on one war and falls on the next, so a table that stored
"war -> gold up" would be wrong half the time with total confidence. That refusal is about the
ASSET's response. It says nothing against measuring the TEXT's own pole -- whether a document
describes a rate HIKE or a rate CUT, a guidance RAISE or a guidance CUT, sanctions IMPOSED or
LIFTED. Those poles are properties of the words, not forecasts, and without them a daily panel
can count "monetary news" but cannot tell a hawkish week from a dovish one.

So this module is an EXTENSION, not a second ontology:

  * the event KINDS still come from `event_ontology.classify` (its ten-language vocabulary is
    reused, never copied) and bump the matching factor's COUNT with no sign;
  * the countries still come from `event_ontology.entities_in`, and the language from
    `polyglot.understand`;
  * what is new is `SIGNED_TABLE`: six factors, two poles each, in EN/JA/ZH/KO -- the four
    languages the desk's Asian lanes are written in.

THE FACTORS AND THEIR POLES (+ / -). Every pole is a property of the text:

    monetary_tone       tightening / hawkish        vs  easing / dovish
    fiscal_stimulus     stimulus / expansion        vs  austerity / consolidation
    export_controls     controls, sanctions imposed vs  lifted, relieved, trade deal
    supply_shock        disruption, halt, shortage  vs  restored, resumed, glut
    earnings_guidance   raised, beat                vs  cut, miss, warning
    geopolitical_risk   escalation                  vs  de-escalation, ceasefire

MATCHING IS LONGEST-FIRST WITH MASKING. `制裁解除` (sanctions lifted) contains `制裁` (sanctions);
counting both would score the lifting of sanctions as zero. Every term across every factor is
matched longest first and its span is blanked before shorter terms are tried, so a phrase is read
once, as the longest thing it is. Latin terms match on word boundaries (a bare substring would
find "war" inside "software"); CJK terms match as substrings because CJK has no boundaries.

THE PANEL IS POINT-IN-TIME BY CONSTRUCTION. A document enters the panel on the UTC DAY of its
`available_at` -- the moment the desk could first have read it, which a caller sets to its own
first-seen stamp (or a publication time plus a lag for a historical corpus). A day's row is
stamped `available_time = the following 00:00 UTC`, so no reader can use Tuesday's documents
before Tuesday is over. `panel_asof` enforces the same rule for a caller holding a decision time.

Pure: no file, no network, numpy/pandas-free. The desk organ is
`desks/mt5/research/nlp_event_factors.py`.
"""

# call ambiguous. Here they are the data.
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from libs.research import event_ontology as onto

__all__ = [
    "COUNTRY_INSTRUMENTS",
    "FACTORS",
    "KIND_FACTOR",
    "LANGS",
    "SIGNED_TABLE",
    "Doc",
    "FactorTag",
    "PanelRow",
    "agreement",
    "build_panel",
    "country_hint_for_currency",
    "orient",
    "panel_asof",
    "tag",
]

FACTORS: tuple[str, ...] = ("monetary_tone", "fiscal_stimulus", "export_controls",
                            "supply_shock", "earnings_guidance", "geopolitical_risk")
LANGS: tuple[str, ...] = ("en", "ja", "zh", "ko")

#: `factor pole lang term|term`, continued with a leading `+`. Pole is `+` or `-`.
SIGNED_TABLE = """monetary_tone + en rate hike|rate hikes|raises rates|raised rates|hikes rates
+hawkish
+tightening cycle|monetary tightening|policy tightening|quantitative tightening|higher for longer
+raise interest rates|raised interest rates|balance sheet reduction|tapering
monetary_tone + ja 利上げ|金融引き締め|引き締め|タカ派|政策金利引き上げ|国債買い入れ減額
+テーパリング
monetary_tone + zh 加息|收紧|紧缩|鹰派|上调利率|提高利率|缩表
monetary_tone + ko 금리 인상|금리인상|긴축|매파|기준금리 인상|양적긴축
monetary_tone - en rate cut|rate cuts|cuts rates|cut rates|lowers rates|lowered rates|dovish
+monetary easing|policy easing|easing cycle|quantitative easing|lower interest rates
+asset purchases|negative rates
monetary_tone - ja 利下げ|金融緩和|ハト派|政策金利引き下げ|量的緩和|マイナス金利|緩和姿勢
monetary_tone - zh 降息|降准|货币宽松|宽松政策|鸽派|下调利率|量化宽松
monetary_tone - ko 금리 인하|금리인하|통화 완화|금융 완화|비둘기파|기준금리 인하|양적완화
fiscal_stimulus + en fiscal stimulus|stimulus package|stimulus plan|infrastructure spending
+tax cut|tax cuts|spending package|supplementary budget|special bonds|fiscal expansion
fiscal_stimulus + ja 経済対策|財政出動|補正予算|景気刺激策|減税|給付金|財政拡大
fiscal_stimulus + zh 财政刺激|刺激计划|经济刺激|专项债|特别国债|减税|基建投资|财政扩张|稳增长
fiscal_stimulus + ko 경기부양|재정 부양|추경|추가경정예산|감세|재정 확대|부양책
fiscal_stimulus - en austerity|spending cuts|fiscal consolidation|tax hike|tax hikes|tax increase
+budget cuts
fiscal_stimulus - ja 緊縮財政|増税|歳出削減|財政再建
fiscal_stimulus - zh 财政紧缩|增税|削减开支|紧缩财政
fiscal_stimulus - ko 긴축 재정|긴축재정|증세|재정 건전화|지출 삭감
export_controls + en export control|export controls|export ban|sanctions|sanctioned|entity list
+chip curbs|tariffs|tariff hike|embargo|restrictions on exports|blacklisted
export_controls + ja 輸出規制|輸出管理|制裁|禁輸|エンティティリスト|関税引き上げ|追加関税
export_controls + zh 出口管制|制裁|实体清单|禁运|加征关税|芯片禁令|出口限制
export_controls + ko 수출 규제|수출 통제|제재|금수|관세 인상|추가 관세|반도체 규제
export_controls - en lifts sanctions|lifted sanctions|sanctions relief|eases export|tariff cut
+tariff cuts|tariff reduction|trade deal|trade truce|removed from the entity list
export_controls - ja 制裁解除|規制緩和|関税引き下げ|貿易合意|関税撤廃
export_controls - zh 解除制裁|放宽出口|取消关税|降低关税|贸易协议|暂停加征
export_controls - ko 제재 해제|규제 완화|관세 인하|무역 합의|관세 철폐
supply_shock + en supply disruption|supply shock|shortage|production halt|output cut|force majeure
+plant shutdown|port closure|blockade|outage
supply_shock + ja 供給不足|供給途絶|生産停止|減産|品不足|操業停止|不可抗力|工場停止
supply_shock + zh 供应中断|断供|停产|减产|短缺|缺货|不可抗力|停工
supply_shock + ko 공급 차질|공급 부족|생산 중단|감산|품귀|가동 중단
supply_shock - en supply restored|production resumed|output increase|capacity expansion
+port reopened|glut|oversupply
supply_shock - ja 生産再開|増産|供給回復|供給過剰|操業再開
supply_shock - zh 复产|增产|恢复供应|供应过剩|复工
supply_shock - ko 생산 재개|증산|공급 회복|공급 과잉|가동 재개
earnings_guidance + en raises guidance|raised guidance|raises forecast|raised its forecast
+beats estimates|earnings beat|record profit|upgrades outlook|raised outlook|guidance raised
earnings_guidance + ja 上方修正|増益|最高益|予想を上回|増配
earnings_guidance + zh 上调指引|业绩预增|超预期|净利润增长|创新高|预增
earnings_guidance + ko 가이던스 상향|실적 호조|어닝 서프라이즈|사상 최대 실적|흑자 전환
+영업이익 증가
earnings_guidance - en cuts guidance|cut guidance|lowers guidance|lowered guidance|profit warning
+misses estimates|earnings miss|downgrades outlook|lowered outlook|guidance cut
earnings_guidance - ja 下方修正|減益|赤字転落|予想を下回|減配
earnings_guidance - zh 下调指引|业绩预减|不及预期|净利润下降|亏损|预减|业绩预警
earnings_guidance - ko 가이던스 하향|실적 부진|어닝 쇼크|적자 전환|영업이익 감소
geopolitical_risk + en military escalation|missile|missiles|invasion|airstrike|air strike|war
+conflict escalates|military drills|tensions rise|nuclear test
geopolitical_risk + ja 軍事衝突|ミサイル|侵攻|空爆|軍事演習|緊張が高ま|地政学リスク|核実験
geopolitical_risk + zh 军事冲突|导弹|入侵|空袭|军演|局势紧张|地缘政治风险|核试验
geopolitical_risk + ko 군사 충돌|미사일|침공|공습|군사훈련|긴장 고조|지정학적 리스크|핵실험
geopolitical_risk - en ceasefire|peace talks|peace deal|truce|de-escalation|tensions ease
geopolitical_risk - ja 停戦|和平|緊張緩和|休戦
geopolitical_risk - zh 停火|和谈|和平协议|缓和局势|休战
geopolitical_risk - ko 휴전|평화 협상|평화 협정|긴장 완화
"""

#: Ontology kind -> (factor, implied sign). A kind the ontology recognises bumps the factor's
#: COUNT; only kinds whose name IS a pole (escalation, ceasefire) carry a sign.
KIND_FACTOR: dict[str, tuple[str, int]] = {
    "central_bank_surprise": ("monetary_tone", 0),
    "sanctions": ("export_controls", 0),
    "tariffs": ("export_controls", 0),
    "supply_disruption": ("supply_shock", 1),
    "strike": ("supply_shock", 1),
    "natural_disaster": ("supply_shock", 0),
    "corporate_shock": ("earnings_guidance", 0),
    "war_escalation": ("geopolitical_risk", 1),
    "political_instability": ("geopolitical_risk", 1),
    "ceasefire": ("geopolitical_risk", -1),
}

#: Country -> MT5 instrument -> CURRENCY-LEG orientation. +1 when a stronger home currency / home
#: market moves the instrument UP (the currency is the base, or the instrument is the home index),
#: -1 when the currency is the quote. It is a sign CONVENTION so a panel can be read on an
#: instrument's own axis -- never a forecast that a factor moves the instrument that way.
COUNTRY_INSTRUMENTS: dict[str, dict[str, int]] = {
    "JP": {"USDJPY": -1, "JPN225": 1},
    "US": {"USDJPY": 1, "EURUSD": -1, "US500": 1, "NAS100": 1, "XAUUSD": -1},
    "CN": {"USDCNH": -1, "CHINAH": 1, "HK50": 1},
    "KR": {"USDKRW": -1},
    "TW": {"TSMC": 1},
    "EU": {"EURUSD": 1},
    "DE": {"EURUSD": 1},
    "FR": {"EURUSD": 1},
    "GB": {"GBPUSD": 1},
    "AU": {"AUDUSD": 1},
    "NZ": {"NZDUSD": 1},
    "CA": {"USDCAD": -1},
    "CH": {"USDCHF": -1},
}

#: Script-implied home country when a document names none. English names nothing by default.
_LANG_HOME = {"ja": "JP", "ko": "KR", "zh": "CN"}
_CCY_HOME = {"USD": "US", "JPY": "JP", "EUR": "EU", "GBP": "GB", "CNY": "CN", "CNH": "CN",
             "KRW": "KR", "AUD": "AU", "NZD": "NZ", "CAD": "CA", "CHF": "CH", "TWD": "TW",
             "HKD": "CN"}
GLOBAL = "GLOBAL"

#: Institution and market names the ontology's country table does not carry (it has "the fed",
#: not "Fed"; "bank of japan", not "BoJ"). Latin names match on word bounds, so "fed" never
#: fires inside "federal" or "fedex" by accident of substring.
_EXTRA_ENTITY: tuple[tuple[str, str], ...] = (
    ("fed", "US"), ("fomc", "US"), ("powell", "US"), ("treasury", "US"), ("boj", "JP"),
    ("ueda", "JP"), ("nikkei", "JP"), ("yen", "JP"), ("pboc", "CN"), ("yuan", "CN"),
    ("renminbi", "CN"), ("hang seng", "CN"), ("bok", "KR"), ("kospi", "KR"), ("samsung", "KR"),
    ("sk hynix", "KR"), ("tsmc", "TW"), ("ecb", "EU"), ("lagarde", "EU"), ("boe", "GB"),
    ("rba", "AU"), ("rbnz", "NZ"), ("snb", "CH"), ("日銀", "JP"), ("日経", "JP"), ("円安", "JP"),
    ("円高", "JP"), ("人民银行", "CN"), ("人民币", "CN"), ("港股", "CN"), ("a股", "CN"),
    ("한국은행", "KR"), ("코스피", "KR"), ("원화", "KR"), ("삼성전자", "KR"),
)
_EXTRA_PATS = tuple((re.compile(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])")
                     if t.isascii() else None, t, c) for t, c in _EXTRA_ENTITY)


def _countries(low: str) -> list[str]:
    codes = {c.code for c in onto.COUNTRIES}
    out = [e for e in onto.entities_in(low) if e in codes]
    for pat, term, code in _EXTRA_PATS:
        if code in out:
            continue
        if (pat.search(low) if pat is not None else term in low):
            out.append(code)
    return out


def country_hint_for_currency(ccy: str) -> str:
    """The home country of a currency code, or '' -- used for a document whose SOURCE says whose
    it is (a central bank's own feed) when its words do not."""
    return _CCY_HOME.get(str(ccy or "").upper(), "")


def _parse(table: str) -> tuple[tuple[str, int, str, tuple[str, ...]], ...]:
    rows: list[list[str]] = []
    for raw in table.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("+"):
            if not rows:
                raise ValueError("signed table opens with a continuation line")
            rows[-1][3] += "|" + line[1:]
            continue
        factor, pole, lang, terms = line.split(" ", 3)
        if factor not in FACTORS or pole not in ("+", "-") or lang not in LANGS:
            raise ValueError(f"bad signed-table row: {line[:60]!r}")
        rows.append([factor, pole, lang, terms])
    return tuple((f, 1 if p == "+" else -1, la,
                  tuple(t.strip().lower() for t in terms.split("|") if t.strip()))
                 for f, p, la, terms in rows)


_ROWS = _parse(SIGNED_TABLE)


def _compile() -> tuple[tuple[str, str, int, re.Pattern[str] | None], ...]:
    """(term, factor, sign, regex-or-None), longest term first. Latin terms get word bounds."""
    seen: dict[str, tuple[str, int]] = {}
    for factor, sign, _lang, terms in _ROWS:
        for t in terms:
            seen.setdefault(t, (factor, sign))
    out = []
    for term in sorted(seen, key=lambda s: (-len(s), s)):
        factor, sign = seen[term]
        pat = (re.compile(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])")
               if term.isascii() else None)
        out.append((term, factor, sign, pat))
    return tuple(out)


_TERMS = _compile()


@dataclass(frozen=True)
class FactorTag:
    """What one document says, factor by factor. `signed[f]` is (+hits) - (-hits); `counts[f]` is
    every hit including the unsigned ontology-kind bumps. An empty tag is a measured zero."""

    lang: str
    countries: tuple[str, ...]
    counts: Mapping[str, int] = field(default_factory=dict)
    signed: Mapping[str, int] = field(default_factory=dict)
    kinds: tuple[str, ...] = ()
    matched: tuple[str, ...] = ()
    tier: str = "lexicon"

    def intensity(self, factor: str) -> float:
        """Signed share of the factor's POLED hits, in [-1, 1]; 0.0 when none carried a pole."""
        pos_neg = self.counts.get(factor, 0)
        s = self.signed.get(factor, 0)
        return max(-1.0, min(1.0, s / pos_neg)) if pos_neg else 0.0


def _lang_of(text: str) -> str:
    try:
        from libs.research.polyglot import understand
        return str(understand(text).lang)
    except Exception:                                     # pragma: no cover - polyglot is pure
        return "en"


def tag(text: str, *, country_hint: str = "", with_ontology: bool = True) -> FactorTag:
    """Tag one title/snippet. Deterministic, zero cost, no model."""
    low = " ".join(str(text or "").lower().split())
    lang = _lang_of(str(text or ""))
    counts: dict[str, int] = {}
    signed: dict[str, int] = {}
    matched: list[str] = []
    buf = low
    for term, factor, sign, pat in _TERMS:
        if pat is None:
            if term not in buf:
                continue
            n = buf.count(term)
            buf = buf.replace(term, " " * len(term))
        else:
            hits = list(pat.finditer(buf))
            if not hits:
                continue
            n = len(hits)
            buf = pat.sub(lambda m: " " * len(m.group(0)), buf)
        counts[factor] = counts.get(factor, 0) + n
        signed[factor] = signed.get(factor, 0) + sign * n
        matched.append(term)
    kinds: list[str] = []
    if with_ontology:
        guess = onto.classify(low)
        for kind, _score in guess.scores:
            mapped = KIND_FACTOR.get(kind)
            if mapped is None:
                continue
            kinds.append(kind)
            factor, sign = mapped
            if factor not in counts:
                # THE ONTOLOGY'S VOCABULARY COUNTS ONLY WHERE OURS SAID NOTHING, so one phrase
                # matched by both tables is one hit, not two.
                counts[factor] = 1
                signed[factor] = sign
    ents = _countries(low)
    if country_hint and country_hint not in ents:
        ents.insert(0, country_hint)
    if not ents:
        home = _LANG_HOME.get(lang)
        ents = [home] if home else [GLOBAL]
    return FactorTag(lang=lang, countries=tuple(dict.fromkeys(ents)), counts=counts,
                     signed=signed, kinds=tuple(kinds), matched=tuple(matched[:12]))


# ------------------------------------------------------------------------------------ the panel
@dataclass(frozen=True)
class Doc:
    """One document as the panel sees it. `available_at` is the first moment the desk could have
    read it -- the caller's first-seen stamp, never a later re-fetch time."""

    doc_id: str
    text: str
    available_at: datetime
    country_hint: str = ""
    source: str = ""


@dataclass(frozen=True)
class PanelRow:
    day: str
    country: str
    factor: str
    n_docs: int
    count: int
    signed_sum: int
    intensity: float
    available_time: str
    tier: str = "lexicon"


def _utc(ts: datetime) -> datetime:
    return ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)


def build_panel(docs: Iterable[Doc], *, tags: Mapping[str, FactorTag] | None = None,
                tier: str = "lexicon") -> list[PanelRow]:
    """Daily (country, factor) rows from documents, stamped with when the day became knowable.

    `intensity` is the signed sum over the day's POLED hits divided by their count, in [-1, 1] --
    a hawkish day reads positive whether one document said so or forty. `count` is kept beside it
    so attention (how much was said) and tone (which way) stay separate facts. A document is
    counted once per day however many times it was re-read (`doc_id` dedupe).
    """
    agg: dict[tuple[str, str, str], list[int]] = {}
    seen: set[tuple[str, str]] = set()
    for d in docs:
        day = _utc(d.available_at).date().isoformat()
        if (d.doc_id, day) in seen:
            continue
        seen.add((d.doc_id, day))
        t = (tags or {}).get(d.doc_id) or tag(d.text, country_hint=d.country_hint)
        for country in t.countries:
            for factor, n in t.counts.items():
                if n <= 0:
                    continue
                cell = agg.setdefault((day, country, factor), [0, 0, 0])
                cell[0] += 1
                cell[1] += int(n)
                cell[2] += int(t.signed.get(factor, 0))
    out: list[PanelRow] = []
    for (day, country, factor), (n_docs, count, ssum) in sorted(agg.items()):
        known = (datetime.combine(date.fromisoformat(day), datetime.min.time(), tzinfo=UTC)
                 + timedelta(days=1)).isoformat()
        out.append(PanelRow(day=day, country=country, factor=factor, n_docs=n_docs, count=count,
                            signed_sum=ssum, intensity=round(ssum / count, 6) if count else 0.0,
                            available_time=known, tier=tier))
    return out


def panel_asof(rows: Iterable[PanelRow], decision_time: datetime) -> list[PanelRow]:
    """Only the rows the desk could have held at `decision_time`. The PIT gate, as a function."""
    cut = _utc(decision_time)
    return [r for r in rows if datetime.fromisoformat(r.available_time) <= cut]


def orient(country: str, instrument: str) -> int:
    """The currency-leg sign of a country's factor on an instrument's own axis; 0 = unrelated."""
    return int(COUNTRY_INSTRUMENTS.get(country, {}).get(instrument, 0))


# ------------------------------------------------------------------------------------ agreement
def _rank(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    out = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2.0
        i = j + 1
    return out


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys, strict=True))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    return sxy / (sxx * syy) ** 0.5 if sxx > 0 and syy > 0 else None


def agreement(ours: Mapping[Any, float], theirs: Mapping[Any, float], *,
              min_n: int = 20) -> dict[str, object]:
    """How far two panels over the SAME keys (country-days, days, months) agree.

    Used to measure this tagger against an outside news-analytics panel (GDELT tone / conflict
    share on the same country-days) and, by the alt-data organ, a free substitute against an
    overlapping series. Pearson, Spearman and the share of keys on which both sit on the same
    side of their own mean. Fewer than `min_n` shared keys is UNMEASURED with the count, never a
    number from a handful of points."""
    keys = [k for k in ours if k in theirs]
    xs = [float(ours[k]) for k in keys]
    ys = [float(theirs[k]) for k in keys]
    ok = [i for i in range(len(keys)) if xs[i] == xs[i] and ys[i] == ys[i]]
    xs, ys = [xs[i] for i in ok], [ys[i] for i in ok]
    n = len(xs)
    if n < min_n:
        return {"verdict": "UNMEASURED", "n": n,
                "why": f"{n} shared keys < {min_n}: no agreement number from so few points"}
    mx, my = sum(xs) / n, sum(ys) / n
    same = sum(1 for a, b in zip(xs, ys, strict=True) if (a - mx) * (b - my) > 0)
    p = _pearson(xs, ys)
    sp = _pearson(_rank(xs), _rank(ys))
    return {"verdict": "MEASURED", "n": n,
            "pearson": None if p is None else round(p, 4),
            "spearman": None if sp is None else round(sp, 4),
            "sign_agreement": round(same / n, 4)}
