"""THE EVENT ONTOLOGY -- what kinds of thing happen in the world, and which assets they reach.

THE PRINCIPAL'S ORDER (2026-09-17, permanent). News is an EVENT STREAM feeding the world model
and the allocator, never an LLM improvising trades. There is no rule anywhere on this desk of the
form WAR = BUY GOLD. What the machine estimates is

    p(R_i | event, location, energy exposure, rates, USD state, positioning, liquidity, regime)

and this module is the first half of that conditioning set: the KIND of thing that happened, WHO
it happened to, and WHICH assets are therefore in the transmission path. It says nothing about
direction. Gold rises on a war that threatens supply and falls on the same war when the dollar
funding squeeze that follows it forces liquidation of the winners -- both have happened, both are
"war", and a table that stored a sign would have been wrong half the time with total confidence.

FOUR THINGS THIS MODULE IS DELIBERATE ABOUT.

**A TRANSMISSION EDGE IS DIRECTION-AGNOSTIC AND CARRIES ITS OWN STATE VARIABLES.** Every edge
names an asset class or anchor, a typical HORIZON, and the state variables that DECIDE the sign
(`usd_state`, `real_yields`, `positioning`, `liquidity`, `energy_exposure`, `net_exporter`...).
The sign is the allocator's problem, computed from the state the desk measures; this table only
says where to look and when.

**CONFIDENCE IS A LADDER, NOT A FEELING.** An official statement outranks a major wire outranks
credible reporting outranks a social claim outranks a duplicate outranks a rumour outranks a
conflicting report, and the ladder is monotone by construction (`assert_ladder_monotone`).
Corroboration by an INDEPENDENT source raises confidence; a conflicting report lowers it. Both
directions exist on purpose: a ladder that could only subtract would make every fast reading
timid, and timid is not risk-aware (GROWTH_GOVERNANCE Rule 1).

**THE 200TH REPETITION IS NOT AN EVENT.** `novelty` collapses a claim that the corpus already
holds -- same entity, same kind, similar words inside the window -- towards zero, so a wire's
fourteen re-filings of one headline move the world state once. That is not a filter on
information; it is the difference between evidence and echo.

**AN ANALOGUE IS A PLACE TO LOOK, NEVER A FORECAST.** `analogues` returns prior events that share
kind and entities, with whatever reaction the event atlas measured for them. Nothing here assumes
a prior event repeats, and every returned row says so in its own `note`.

WHAT IT REUSES. `libs.research.polyglot` owns the desk's multilingual understanding, so concept
ids from `polyglot.CONCEPTS` are accepted directly by `classify` and mapped to kinds here; the
keyword tables below are the EVENT vocabulary polyglot does not carry (war, sanctions, tariffs,
default, cyclone) in the ten languages the desk's forests are written in. The entity graph is
SEEDED here and MERGED with MetaTrader's own registry by `seed_entity_graph`, so a symbol Fusion
lists tomorrow reaches the graph without an edit, and a symbol it does not list never appears.

Pure: it opens no file, fetches nothing, and decides nothing. numpy only.
"""
# ruff: noqa: RUF001 -- an event lexicon written in ten scripts is MADE of the characters
# these rules call ambiguous. Here they are the data, not a typo waiting to be found.
from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, NamedTuple

__all__ = [
    "ASSET_CLASSES",
    "COMMODITIES",
    "COUNTRIES",
    "HORIZONS",
    "KINDS",
    "ONTOLOGY",
    "SOURCE_LADDER",
    "STATE_VARS",
    "UNMEASURED",
    "Affected",
    "Analogue",
    "Commodity",
    "Country",
    "Edge",
    "EntityGraph",
    "EventGuess",
    "KindSpec",
    "Novelty",
    "Surprise",
    "affected",
    "analogues",
    "assert_ladder_monotone",
    "classify",
    "entities_in",
    "event_id",
    "event_key",
    "novelty",
    "novelty_of",
    "resolve_event_id",
    "seed_entity_graph",
    "source_confidence",
    "surprise",
    "surprise_of",
]

UNMEASURED = "UNMEASURED"

#: Typical transmission horizons. The realistic edge is seconds-to-minutes repricing, cross-asset
#: propagation and HOURS TO DAYS of transmission -- not the first millisecond, which belongs to
#: somebody with a microwave tower.
HORIZONS: tuple[str, ...] = ("minutes", "hours", "days", "weeks")

#: The state variables that decide an edge's SIGN. Every one is measured elsewhere on this desk.
STATE_VARS: tuple[str, ...] = (
    "usd_state", "real_yields", "rates_path", "energy_exposure", "net_exporter", "net_importer",
    "positioning", "liquidity", "regime", "risk_appetite", "inventory", "carry", "credit_spread",
    "term_of_trade", "already_priced",
)

#: MetaTrader's own asset-class vocabulary, as `data/universe/universe.json` writes it.
ASSET_CLASSES: tuple[str, ...] = ("Forex", "Forex Exotics", "Commodities", "Soft Commodity",
                                  "Energy", "Indices", "Bonds", "Crypto", "Equities")

#: Bound on how many symbols one edge may name once a universe is loaded. An edge that resolved
#: to every exotic would drown the resolve request it is supposed to describe.
MAX_ASSETS_PER_EDGE = 8
#: Bound on the returned analogues, and the floor a prior event must clear to be one.
MAX_ANALOGUES = 8
ANALOGUE_FLOOR = 0.35
#: Claim similarity at or above which two rows are the same claim told twice.
DUP_SIMILARITY = 0.60
#: A scheduled release whose actual the desk does not hold. A DECLARED prior, named UNMEASURED
#: everywhere it is used: absence is a verdict (L1.28a), and a zero would silently suppress the
#: deep lane on exactly the releases that move the book.
SCHEDULED_PRIOR = 0.5
#: |z| at which a consensus surprise is maximal.
SURPRISE_Z_CAP = 3.0


# ============================================================================= source confidence
#: THE LADDER, best to worst. `confidence` is P(the claim is substantially true AS STATED) given
#: nothing but who said it -- a prior the fast lane multiplies its nudge by, never a verdict.
SOURCE_LADDER: tuple[tuple[str, float, str], ...] = (
    ("official_statement", 0.95, "the principal itself: a ministry, a central bank, an exchange, "
                                 "a company's own filing or a government wire"),
    ("official_data_release", 0.93, "a statistical agency's scheduled print on its own schedule"),
    ("major_wire", 0.85, "Reuters/AP/AFP/Bloomberg/Xinhua/TASS-class agency carrying a byline"),
    ("credible_reporting", 0.70, "a named outlet with an editorial chain, reporting second-hand"),
    ("aggregator", 0.55, "a feed that republishes without adding reporting of its own"),
    ("social_claim", 0.35, "a post by an identified account with no editorial chain"),
    ("anonymous_claim", 0.22, "an unidentified account, or a claim with no attribution at all"),
    ("duplicate", 0.18, "a re-filing of a claim the corpus already holds"),
    ("rumour", 0.15, "explicitly unconfirmed, 'reports suggest', 'sources say' with no source"),
    ("conflicting", 0.10, "another source of equal or better standing states the opposite"),
)
_LADDER: dict[str, float] = {tier: conf for tier, conf, _why in SOURCE_LADDER}
#: What an unrecognised tier gets. Between anonymous and duplicate, and NAMED rather than zero.
UNKNOWN_TIER_CONFIDENCE = 0.20


def assert_ladder_monotone() -> None:
    """The ladder must fall, strictly, from official to conflicting. A test pins this."""
    values = [conf for _tier, conf, _why in SOURCE_LADDER]
    if values != sorted(values, reverse=True) or len(set(values)) != len(values):
        raise ValueError("SOURCE_LADDER is not strictly monotone: the ladder is the contract")


def source_confidence(tier: str, *, corroborations: int = 0, conflicts: int = 0) -> float:
    """The tier's prior, raised by INDEPENDENT corroboration and lowered by conflicting reports.

    Two-sided on purpose (GROWTH_GOVERNANCE Rule 2): three independent wires carrying the same
    claim are better evidence than one, and a reading that could only ever subtract would make
    the fast lane systematically timid about exactly the events that matter most.
    """
    base = _LADDER.get(str(tier).strip().lower(), UNKNOWN_TIER_CONFIDENCE)
    gap = 1.0 - base
    up = gap * (1.0 - math.exp(-0.55 * max(0, int(corroborations))))
    down = (base + up) * (1.0 - math.exp(-0.70 * max(0, int(conflicts))))
    return float(max(0.01, min(0.99, base + up - down)))


# ============================================================================= the kinds
@dataclass(frozen=True)
class Edge:
    """One direction-agnostic transmission edge: WHICH assets, WHEN, and what decides the sign."""

    asset_class: str
    horizon: str
    state_vars: tuple[str, ...]
    anchors: tuple[str, ...] = ()
    note: str = ""

    def __post_init__(self) -> None:
        if self.horizon not in HORIZONS:
            raise ValueError(f"unknown horizon {self.horizon!r}")
        for var in self.state_vars:
            if var not in STATE_VARS:
                raise ValueError(f"unknown state variable {var!r}")


@dataclass(frozen=True)
class KindSpec:
    """One event kind: what it is, whether the world knows it is coming, and where it transmits."""

    gloss: str
    scheduled: bool
    edges: tuple[Edge, ...]
    concepts: tuple[str, ...] = ()
    #: DECLARED base rates for the scenario tree (escalate / hold / de-escalate). Priors, not
    #: measurements: the deep lane publishes them with that word attached and the falsifier is
    #: the atlas's own realised distribution once the desk has counted enough of this kind.
    scenario_prior: tuple[float, float, float] = (0.25, 0.55, 0.20)


def _e(cls: str, horizon: str, state: str, anchors: str = "", note: str = "") -> Edge:
    return Edge(asset_class=cls, horizon=horizon, state_vars=tuple(state.split()),
                anchors=tuple(a for a in anchors.split() if a), note=note)


ONTOLOGY: dict[str, KindSpec] = {
    "war_escalation": KindSpec(
        "an armed conflict opens or widens", False,
        (_e("Energy", "minutes", "energy_exposure liquidity already_priced", "XTIUSD XBRUSD XNGUSD",
            "supply risk premium, largest where the belligerent is a producer or a chokepoint"),
         _e("Commodities", "minutes", "real_yields usd_state positioning", "XAUUSD XAGUSD XPTUSD",
            "the safe-asset bid competes with a funding squeeze; real yields decide which wins"),
         _e("Forex", "minutes", "usd_state risk_appetite carry", "USDJPY USDCHF",
            "funding currencies unwind before the story is understood"),
         _e("Indices", "hours", "risk_appetite positioning regime"),
         _e("Bonds", "hours", "rates_path real_yields risk_appetite"),
         _e("Forex Exotics", "days", "net_importer net_exporter term_of_trade credit_spread",
            "", "the belligerents' neighbours reprice on trade and energy exposure")),
        ("central_bank_action",), (0.35, 0.45, 0.20)),
    "ceasefire": KindSpec(
        "a conflict pauses, de-escalates or settles", False,
        (_e("Energy", "minutes", "energy_exposure already_priced inventory", "XTIUSD XBRUSD"),
         _e("Commodities", "hours", "real_yields positioning", "XAUUSD XAGUSD"),
         _e("Indices", "hours", "risk_appetite positioning"),
         _e("Forex Exotics", "days", "credit_spread term_of_trade net_importer")),
        (), (0.15, 0.50, 0.35)),
    "sanctions": KindSpec(
        "a state restricts trade, finance or shipping with another", False,
        (_e("Energy", "hours", "energy_exposure net_exporter inventory", "XTIUSD XBRUSD XNGUSD"),
         _e("Commodities", "hours", "net_exporter inventory term_of_trade",
            "XPDUSD XALUSD XNIUSD XCUUSD", "the metals a sanctioned producer supplies"),
         _e("Forex Exotics", "hours", "credit_spread net_exporter liquidity", "USDRUB EURRUB"),
         _e("Forex", "days", "usd_state carry rates_path"),
         _e("Indices", "days", "risk_appetite regime")),
        (), (0.30, 0.55, 0.15)),
    "tariffs": KindSpec(
        "an import duty, quota or export control is imposed, raised or lifted", False,
        (_e("Indices", "minutes", "risk_appetite regime term_of_trade", "US500 NAS100 CHINAH HK50"),
         _e("Forex", "minutes", "usd_state term_of_trade net_exporter", "USDCNH AUDUSD USDCAD"),
         _e("Soft Commodity", "hours", "term_of_trade inventory net_exporter",
            "SOYBEAN CORN WHEAT COTTON"),
         _e("Commodities", "hours", "term_of_trade inventory", "XALUSD XCUUSD"),
         _e("Bonds", "days", "rates_path real_yields")),
        (), (0.30, 0.50, 0.20)),
    "central_bank_surprise": KindSpec(
        "a policy decision, guidance or minutes away from what was priced", True,
        (_e("Forex", "minutes", "rates_path usd_state carry positioning already_priced"),
         _e("Bonds", "minutes", "rates_path real_yields positioning", "UST05Y UST10Y UKGILT"),
         _e("Indices", "minutes", "rates_path risk_appetite regime"),
         _e("Commodities", "hours", "real_yields usd_state", "XAUUSD XAGUSD"),
         _e("Forex Exotics", "hours", "carry credit_spread liquidity")),
        ("central_bank_action",), (0.20, 0.60, 0.20)),
    "inflation_surprise": KindSpec(
        "a price index prints away from consensus", True,
        (_e("Bonds", "minutes", "rates_path real_yields already_priced", "UST05Y UST10Y"),
         _e("Forex", "minutes", "rates_path usd_state positioning"),
         _e("Commodities", "hours", "real_yields usd_state inventory", "XAUUSD"),
         _e("Indices", "hours", "rates_path risk_appetite regime")),
        (), (0.15, 0.70, 0.15)),
    "labour_surprise": KindSpec(
        "an employment, wage or claims print away from consensus", True,
        (_e("Forex", "minutes", "rates_path usd_state positioning already_priced"),
         _e("Bonds", "minutes", "rates_path real_yields", "UST05Y UST10Y"),
         _e("Indices", "minutes", "rates_path risk_appetite"),
         _e("Commodities", "hours", "real_yields usd_state", "XAUUSD")),
        (), (0.15, 0.70, 0.15)),
    "supply_disruption": KindSpec(
        "a mine, field, refinery, port, pipeline or strait stops or restarts", False,
        (_e("Energy", "minutes", "energy_exposure inventory net_exporter", "XTIUSD XBRUSD XNGUSD"),
         _e("Commodities", "minutes", "inventory net_exporter term_of_trade",
            "XCUUSD XALUSD XNIUSD XZNUSD XPDUSD XPTUSD"),
         _e("Soft Commodity", "hours", "inventory net_exporter term_of_trade",
            "COFARA COFROB SUGAR UKCOCOA WHEAT CORN SOYBEAN"),
         _e("Forex Exotics", "hours", "net_exporter term_of_trade", "USDNOK USDCAD USDZAR"),
         _e("Indices", "days", "regime risk_appetite")),
        (), (0.25, 0.55, 0.20)),
    "sovereign_default": KindSpec(
        "a state misses, restructures or is downgraded towards missing a payment", False,
        (_e("Forex Exotics", "minutes", "credit_spread liquidity carry net_importer"),
         _e("Bonds", "minutes", "credit_spread rates_path real_yields"),
         _e("Forex", "hours", "usd_state risk_appetite carry", "USDJPY USDCHF"),
         _e("Indices", "hours", "risk_appetite credit_spread regime"),
         _e("Commodities", "hours", "real_yields usd_state", "XAUUSD")),
        (), (0.30, 0.55, 0.15)),
    "natural_disaster": KindSpec(
        "an earthquake, cyclone, flood, drought, freeze or volcanic event", False,
        (_e("Soft Commodity", "hours", "inventory net_exporter term_of_trade",
            "COFARA COFROB SUGAR CORN WHEAT SOYBEAN OJ UKCOCOA"),
         _e("Energy", "hours", "energy_exposure inventory", "XNGUSD XTIUSD"),
         _e("Indices", "hours", "regime risk_appetite", "JPN225 US500"),
         _e("Forex", "days", "term_of_trade net_importer", "USDJPY")),
        (), (0.20, 0.60, 0.20)),
    "corporate_shock": KindSpec(
        "a single name's earnings, guidance, fraud, failure or takeover", False,
        (_e("Equities", "minutes", "positioning liquidity already_priced", "",
            "the event lane's own ground: single names are traded on news, never hypothesised"),
         _e("Indices", "minutes", "regime risk_appetite positioning", "NAS100 US500"),
         _e("Bonds", "hours", "credit_spread risk_appetite")),
        (), (0.20, 0.65, 0.15)),
    "fx_intervention": KindSpec(
        "a monetary authority transacts, or credibly threatens to, in its own currency", False,
        (_e("Forex", "minutes", "usd_state positioning liquidity carry", "USDJPY USDCHF"),
         _e("Forex Exotics", "minutes", "liquidity credit_spread carry",
            "USDCNH USDKRW USDTRY USDINR USDBRL"),
         _e("Bonds", "hours", "rates_path real_yields"),
         _e("Indices", "hours", "regime risk_appetite", "JPN225")),
        ("central_bank_action",), (0.25, 0.55, 0.20)),
    "election": KindSpec(
        "a vote, referendum, coalition collapse or leadership change", True,
        (_e("Forex Exotics", "minutes", "credit_spread liquidity positioning"),
         _e("Indices", "minutes", "regime risk_appetite positioning"),
         _e("Bonds", "hours", "credit_spread rates_path"),
         _e("Forex", "hours", "usd_state rates_path", "EURUSD GBPUSD"),
         _e("Commodities", "days", "real_yields usd_state", "XAUUSD")),
        (), (0.20, 0.60, 0.20)),
    "political_instability": KindSpec(
        "a coup, mass unrest, emergency rule or a state losing control of territory", False,
        (_e("Forex Exotics", "minutes", "credit_spread liquidity net_exporter"),
         _e("Energy", "hours", "energy_exposure net_exporter", "XTIUSD XBRUSD"),
         _e("Commodities", "hours", "net_exporter inventory real_yields", "XAUUSD XPTUSD XPDUSD"),
         _e("Indices", "hours", "risk_appetite regime")),
        (), (0.35, 0.50, 0.15)),
    "strike": KindSpec(
        "organised labour stops work at a port, mine, railway, refinery or carrier", False,
        (_e("Commodities", "hours", "inventory net_exporter", "XCUUSD XALUSD XNIUSD"),
         _e("Energy", "hours", "energy_exposure inventory", "XTIUSD XBRUSD"),
         _e("Soft Commodity", "hours", "inventory term_of_trade", "COFARA SUGAR UKCOCOA"),
         _e("Indices", "days", "regime risk_appetite"),
         _e("Forex Exotics", "days", "net_exporter term_of_trade")),
        (), (0.25, 0.60, 0.15)),
    "cyber_attack": KindSpec(
        "an intrusion or outage disabling an exchange, pipeline, bank or grid", False,
        (_e("Indices", "minutes", "liquidity risk_appetite regime"),
         _e("Energy", "minutes", "energy_exposure inventory", "XTIUSD XNGUSD"),
         _e("Forex", "hours", "liquidity usd_state"),
         _e("Bonds", "hours", "credit_spread liquidity")),
        (), (0.25, 0.60, 0.15)),
    "pandemic": KindSpec(
        "an outbreak, quarantine, border closure or public-health emergency", False,
        (_e("Indices", "hours", "regime risk_appetite positioning"),
         _e("Energy", "hours", "energy_exposure inventory", "XTIUSD XBRUSD"),
         _e("Forex", "days", "usd_state risk_appetite carry", "USDJPY USDCHF"),
         _e("Soft Commodity", "days", "inventory term_of_trade"),
         _e("Bonds", "days", "rates_path real_yields")),
        (), (0.30, 0.55, 0.15)),
    "other": KindSpec(
        "a document the ontology cannot classify -- a verdict, never a silent drop", False,
        (), (), (0.0, 1.0, 0.0)),
}

#: What a kind IS. `other` is a real answer and is counted, never discarded (L1.28a, WS-005).
KINDS: tuple[str, ...] = tuple(ONTOLOGY)

#: Polyglot concept ids that IMPLY a kind. The concept tables are polyglot's; the mapping is the
#: ontology's, so a concept added there never silently becomes an event kind here.
CONCEPT_KIND: dict[str, str] = {
    "central_bank_action": "central_bank_surprise",
    "forced_liquidation": "sovereign_default",
    "capitulation": "sovereign_default",
}


# ============================================================================= the vocabulary
#: THE EVENT VOCABULARY, one row per (kind, language): `kind lang term|term|term`, continued on
#: the next line with a leading `+`. Terms are matched as SUBSTRINGS of a lowercased body -- CJK
#: has no word boundaries to lean on, and a latin term short enough to collide is not in the
#: table. Ten languages because the desk's forests are written in them; a language with no row
#: for a kind is a MEASURED GAP in the vocabulary, not a claim that the kind never happens there.
_KW_TABLE = """war_escalation ar غزو|غارة جوية|ضربة صاروخية|قصف|إعلان الحرب|تصعيد
war_escalation de invasion|luftangriff|raketenangriff|beschuss|offensive|kriegserklärung
+eskalation
war_escalation en invasion|invaded|air strike|airstrike|missile strike|shelling|offensive launched
+declares war|troops crossed|drone attack|bombardment|escalation of the conflict|state of war
+mobilisation|mobilization
war_escalation es invasión|ataque aéreo|bombardeo|ofensiva|declara la guerra
+escalada del conflicto
war_escalation fr invasion|frappe aérienne|bombardement|offensive|déclare la guerre|escalade
war_escalation ja 侵攻|空爆|ミサイル攻撃|砲撃|宣戦|軍事作戦|エスカレート|ドローン攻撃
war_escalation ko 침공|공습|미사일 공격|포격|선전포고|군사작전|무인기 공격
war_escalation pt invasão|ataque aéreo|bombardeio|ofensiva|declara guerra|escalada
war_escalation ru вторжение|авиаудар|ракетный удар|обстрел|наступление|мобилизац|боевые действия
war_escalation zh 入侵|空袭|导弹袭击|炮击|宣战|军事行动|升级冲突|无人机袭击|动员
ceasefire ar وقف إطلاق النار|هدنة|اتفاق سلام|انسحاب القوات
ceasefire de waffenruhe|waffenstillstand|friedensabkommen|truppenabzug|deeskalation
ceasefire en ceasefire|cease-fire|truce|peace deal|peace agreement|withdrawal of troops
+de-escalation|armistice|halt to hostilities
ceasefire es alto el fuego|tregua|acuerdo de paz|retirada de tropas
ceasefire ja 停戦|休戦|和平合意|撤退|緊張緩和
ceasefire ko 휴전|정전|평화협정|철군|긴장 완화
ceasefire ru прекращение огня|перемирие|мирное соглашение|вывод войск|деэскалац
ceasefire zh 停火|休战|和平协议|撤军|缓和局势
sanctions ar عقوبات|حظر|تجميد الأصول|القائمة السوداء
sanctions de sanktion|embargo|ausfuhrverbot|einfrieren von vermögen|preisdeckel
sanctions en sanction|sanctions package|export ban|import ban|embargo|asset freeze|swift
+blacklisted|secondary sanctions|price cap
sanctions es sanciones|embargo|prohibición de exportación|congelación de activos
sanctions ja 制裁|禁輸|輸出禁止|資産凍結|ブラックリスト|価格上限
sanctions ko 제재|금수|수출 금지|자산 동결|블랙리스트
sanctions ru санкци|эмбарго|запрет на экспорт|заморозка активов|потолок цен
sanctions zh 制裁|禁运|出口禁令|资产冻结|列入黑名单|限价
tariffs de zoll|zölle|antidumping|handelskrieg|ausfuhrkontrolle
tariffs en tariff|tariffs on|duty on imports|countervailing duty|anti-dumping|trade war
+export control|quota on imports|section 301
tariffs es arancel|antidumping|guerra comercial|control de exportaciones
tariffs ja 関税|反ダンピング|貿易戦争|輸出規制|輸入割当
tariffs ko 관세|반덤핑|무역전쟁|수출 통제|수입 쿼터
tariffs ru пошлин|антидемпинг|торговая война|экспортный контроль|квота на импорт
tariffs zh 关税|反倾销|贸易战|出口管制|进口配额|加征
central_bank_surprise ar سعر الفائدة|رفع الفائدة|خفض الفائدة|البنك المركزي
central_bank_surprise de leitzins|zinserhöhung|zinssenkung|notenbank|geldpolitik
central_bank_surprise en rate decision|raises rates|cuts rates|rate hike|rate cut|policy rate|fomc
+unchanged at|hawkish|dovish|quantitative tightening|yield curve control|forward guidance
+emergency meeting
central_bank_surprise es tipos de interés|subida de tipos|recorte de tipos|banco central
+tasa de política
central_bank_surprise ja 利上げ|利下げ|政策金利|日銀決定会合|タカ派|ハト派
+イールドカーブ・コントロール
central_bank_surprise ko 금리 인상|금리 인하|기준금리|통화정책|매파|비둘기파
central_bank_surprise ru ставк|повышение ставки|снижение ставки|заседание цб|ключевая ставка
central_bank_surprise zh 加息|降息|议息|政策利率|央行决议|鹰派|鸽派|降准
inflation_surprise de verbraucherpreisindex|inflation|kerninflation|erzeugerpreise
inflation_surprise en consumer price index|cpi came in|inflation rose to|inflation slowed to
+core inflation|producer price index|ppi|deflation|hotter than expected
inflation_surprise es índice de precios al consumo|inflación|inflación subyacente
inflation_surprise ja 消費者物価指数|インフレ|コアcpi|企業物価指数|デフレ
inflation_surprise ko 소비자물가|물가상승|근원물가|생산자물가|디플레이션
inflation_surprise ru индекс потребительских цен|инфляц|базовая инфляц|дефляц
inflation_surprise zh 消费者物价指数|通胀|通货膨胀|核心通胀|生产者价格指数|通缩
labour_surprise de arbeitsmarktbericht|arbeitslosenquote|beschäftigung ausserhalb
labour_surprise en nonfarm payrolls|non-farm payrolls|unemployment rate|jobless claims
+employment report|average hourly earnings|payrolls rose|payrolls fell
labour_surprise es nóminas no agrícolas|tasa de desempleo|informe de empleo
labour_surprise ja 雇用統計|失業率|新規失業保険申請|非農業部門雇用者数
labour_surprise ko 고용지표|실업률|비농업 고용|신규 실업수당
labour_surprise ru занятость вне сельского|уровень безработицы|заявки на пособие
labour_surprise zh 非农|失业率|就业报告|初请失业金
supply_disruption ar خط أنابيب|مصفاة|توقف الإنتاج|قوة قاهرة|إغلاق الميناء|مضيق
supply_disruption de pipeline|raffinerie|förderstopp|höhere gewalt|hafen geschlossen|meerenge
+produktionskürzung
supply_disruption en pipeline shut|refinery fire|mine halted|force majeure|port closed|strait
+shipping disrupted|output cut|production halted|export terminal|supply disruption|blockade
+drought hit the crop|smelter
supply_disruption es oleoducto|refinería|producción detenida|fuerza mayor|puerto cerrado|estrecho
+recorte de producción
supply_disruption ja パイプライン停止|製油所|生産停止|不可抗力|港湾閉鎖|海峡|減産|供給途絶
supply_disruption ko 송유관|정유소|생산 중단|불가항력|항만 폐쇄|해협|감산|공급 차질
supply_disruption ru трубопровод остановл|нпз|добыча приостановл|форс-мажор|порт закрыт|пролив
+сокращение добычи|перебои с поставками
supply_disruption zh 管道中断|炼厂|停产|不可抗力|港口关闭|海峡|减产|出口终端|供应中断
sovereign_default de zahlungsausfall|umschuldung|herabstufung|kapitalverkehrskontroll
sovereign_default en default on its debt|missed a coupon|debt restructuring|downgraded to junk
+imf bailout|capital controls|moratorium on payments|credit rating cut
sovereign_default es impago de su deuda|reestructuración de deuda|rebaja de calificación
+control de capitales
sovereign_default ja デフォルト|債務再編|格下げ|imf支援|資本規制
sovereign_default ko 채무 불이행|채무 재조정|신용등급 강등|자본 통제
sovereign_default ru дефолт|реструктуризация долга|понижение рейтинга|валютные ограничен
sovereign_default zh 债务违约|重组债务|评级下调|国际货币基金组织救助|资本管制
natural_disaster de erdbeben|hurrikan|taifun|überschwemmung|dürre|frost|waldbrand|vulkanausbruch
+tsunami
natural_disaster en earthquake|magnitude quake|hurricane|typhoon|cyclone|flooding hit|drought
+frost damaged|wildfire|volcano erupt|tsunami|heatwave
natural_disaster es terremoto|huracán|tifón|inundación|sequía|helada|incendio forestal|erupción
+tsunami
natural_disaster ja 地震|ハリケーン|台風|洪水|干ばつ|霜害|山火事|噴火|津波|熱波
natural_disaster ko 지진|허리케인|태풍|홍수|가뭄|서리 피해|산불|화산 분화|쓰나미
natural_disaster ru землетрясение|ураган|тайфун|наводнение|засуха|заморозки|лесные пожары
+извержение|цунами
natural_disaster zh 地震|飓风|台风|洪水|干旱|霜冻|山火|火山喷发|海啸|热浪
corporate_shock en profit warning|guidance cut|accounting fraud|files for bankruptcy|takeover bid
+earnings beat|earnings miss|ceo resigns|product recall|delisting
corporate_shock ja 業績予想の下方修正|粉飾|破綻|買収提案|決算|上場廃止
corporate_shock ko 실적 경고|가이던스 하향|분식회계|파산|인수 제안|상장폐지
corporate_shock ru предупреждение о прибыли|банкротств|поглощен|отчетность
corporate_shock zh 业绩预警|下调指引|财务造假|破产|收购要约|财报|退市
fx_intervention en intervened in the currency market|currency intervention|verbal intervention
+will take decisive action|smoothing operation|bought yen|sold yen|defend the peg|fixing set
fx_intervention es intervención cambiaria|intervención verbal|defender el tipo
fx_intervention ja 為替介入|円買い介入|口先介入|断固たる措置|仲値
fx_intervention ko 외환시장 개입|구두 개입|환율 방어
fx_intervention ru валютная интервенц|вербальная интервенц|защита курса
fx_intervention zh 干预汇市|外汇干预|口头干预|中间价|保卫汇率
election de bundestagswahl|präsidentschaftswahl|referendum|misstrauensvotum
election en general election|presidential election|referendum|exit poll|coalition collapsed
+snap election|no-confidence vote|sworn in as president
election es elecciones generales|elecciones presidenciales|referéndum|moción de censura
election ja 総選挙|大統領選|国民投票|出口調査|連立崩壊|不信任決議
election ko 총선|대선|국민투표|출구조사|연립 붕괴|불신임
election ru всеобщие выборы|президентские выборы|референдум|экзитпол|вотум недоверия
election zh 大选|总统选举|公投|出口民调|联合政府破裂|不信任投票
political_instability ar انقلاب|حالة الطوارئ|الأحكام العرفية|احتجاجات واسعة
political_instability en coup|military took power|state of emergency|martial law|mass protests
+government collapsed|president ousted|junta
political_instability es golpe de estado|estado de emergencia|ley marcial|protestas masivas
political_instability ja クーデター|軍が権力|非常事態|戒厳令|大規模デモ|政権崩壊
political_instability ko 쿠데타|계엄|비상사태|대규모 시위|정권 붕괴
political_instability ru переворот|чрезвычайное положение|военное положение|массовые протесты
+правительство пало
political_instability zh 政变|军方接管|紧急状态|戒严|大规模抗议|政府垮台
strike de streik|arbeitsniederlegung|hafenstreik
strike en strike action|workers walked out|union strike|industrial action|dockworkers strike
+rail strike|walkout at
strike es huelga|paro de trabajadores|huelga portuaria
strike ja ストライキ|スト突入|労組スト|港湾スト
strike ko 파업|노조 파업|항만 파업
strike ru забастовк|стачка|профсоюз объявил
strike zh 罢工|工会罢工|工人停工|码头罢工
cyber_attack en cyber attack|cyberattack|ransomware|hacked|breach of its systems
+outage at the exchange|systems down|ddos
cyber_attack es ciberataque|ransomware|hackeo|caída de sistemas
cyber_attack ja サイバー攻撃|ランサムウェア|ハッキング|システム障害
cyber_attack ko 사이버 공격|랜섬웨어|해킹|시스템 장애
cyber_attack ru кибератак|программа-вымогатель|взлом|сбой в системе
cyber_attack zh 网络攻击|勒索软件|黑客|系统故障|交易所宕机
pandemic en outbreak of|quarantine|lockdown|border closed|public health emergency|epidemic
+new variant|who declared
pandemic es brote de|cuarentena|confinamiento|frontera cerrada|emergencia sanitaria
pandemic ja 感染拡大|隔離|ロックダウン|国境閉鎖|緊急事態宣言|変異株
pandemic ko 감염 확산|격리|봉쇄|국경 폐쇄|공중보건 비상
pandemic ru вспышка|карантин|локдаун|границы закрыт|штамм
pandemic zh 疫情|隔离|封城|边境关闭|突发公共卫生事件|变异株
"""


def _parse_kw_table(table: str) -> tuple[tuple[str, str, str], ...]:
    """The table above as (kind, language, terms), joining every `+` continuation line."""
    rows: list[list[str]] = []
    for raw in table.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("+"):
            if not rows:
                raise ValueError("the keyword table opens with a continuation line")
            rows[-1][2] = rows[-1][2] + "|" + line[1:]
            continue
        kind, lang, terms = line.split(" ", 2)
        rows.append([kind, lang, terms])
    return tuple((k, la, t) for k, la, t in rows)


#: The parsed table. A test asserts every kind here is a kind the ontology declares.
_KW: tuple[tuple[str, str, str], ...] = _parse_kw_table(_KW_TABLE)


def _build_keywords() -> dict[str, dict[str, tuple[str, ...]]]:
    out: dict[str, dict[str, tuple[str, ...]]] = {}
    for kind, lang, terms in _KW:
        if kind not in ONTOLOGY:
            raise ValueError(f"keyword table names an unknown kind {kind!r}")
        out.setdefault(kind, {})[lang] = tuple(t.strip().lower() for t in terms.split("|")
                                               if t.strip())
    return out


#: kind -> language -> terms. Built once at import; the table above is the source of truth.
KEYWORDS: dict[str, dict[str, tuple[str, ...]]] = _build_keywords()
LANGUAGES: tuple[str, ...] = tuple(sorted({lang for _k, lang, _t in _KW}))


# ============================================================================= the entity graph
@dataclass(frozen=True)
class Commodity:
    """A physical good, its MT5 anchors, and the industries that consume it."""

    commodity_id: str
    names: tuple[str, ...]
    asset_class: str
    anchors: tuple[str, ...]
    industries: tuple[str, ...] = ()


@dataclass(frozen=True)
class Country:
    """A jurisdiction and everything the desk can reach it through."""

    code: str
    names: tuple[str, ...]
    currency: str
    exports: tuple[str, ...] = ()
    imports: tuple[str, ...] = ()
    indices: tuple[str, ...] = ()
    rates: tuple[str, ...] = ()
    industries: tuple[str, ...] = ()


def _m(cid: str, names: str, cls: str, anchors: str, industries: str = "") -> Commodity:
    return Commodity(cid, tuple(names.split("|")), cls, tuple(anchors.split()),
                     tuple(i for i in industries.split() if i))


def _k(code: str, names: str, ccy: str, exports: str = "", imports: str = "", indices: str = "",
       rates: str = "", industries: str = "") -> Country:
    return Country(code, tuple(names.split("|")), ccy, tuple(exports.split()),
                   tuple(imports.split()), tuple(indices.split()), tuple(rates.split()),
                   tuple(i for i in industries.split() if i))


COMMODITIES: tuple[Commodity, ...] = (
    _m("crude", "crude|oil|petroleum|wti|brent|石油|原油|нефть|نفط|petróleo|erdöl|pétrole",
       "Energy", "XTIUSD XBRUSD", "refining transport airlines chemicals"),
    _m("natgas", "natural gas|lng|天然气|天然ガス|газ|غاز|gas natural|erdgas", "Energy", "XNGUSD",
       "utilities chemicals fertiliser"),
    _m("gold", "gold|bullion|黄金|黃金|ゴールド|золото|ذهب|oro|gold bullion",
       "Commodities",
       "XAUUSD XAUEUR XAUAUD", "jewellery"),
    _m("silver", "silver|白银|白銀|シルバー|серебро|فضة|plata|silber", "Commodities",
       "XAGUSD XAGEUR",
       "solar electronics"),
    _m("copper", "copper|铜价|銅価|медь|نحاس|cobre|kupfer|cuivre", "Commodities", "XCUUSD",
       "construction grid electronics"),
    _m("platinum", "platinum|铂金|プラチナ|платина|platino|platin", "Commodities",
       "XPTUSD", "autos"),
    _m("palladium", "palladium|钯金|パラジウム|палладий|paladio", "Commodities",
       "XPDUSD", "autos"),
    _m("aluminium", "aluminium|aluminum|铝价|アルミ|алюминий|aluminio", "Commodities",
       "XALUSD",
       "autos packaging aerospace"),
    _m("nickel", "nickel|镍价|ニッケル|никель|níquel", "Commodities", "XNIUSD", "steel batteries"),
    _m("zinc", "zinc|锌价|亜鉛|цинк", "Commodities", "XZNUSD", "steel construction"),
    _m("lead", "lead metal|铅价|鉛価|свинец", "Commodities", "XPBUSD", "batteries"),
    _m("wheat", "wheat|小麦|пшениц|قمح|trigo|weizen|blé", "Soft Commodity", "WHEAT",
       "food"),
    _m("corn", "corn|maize|玉米|とうもろこし|кукуруза|ذرة|maíz|mais", "Soft Commodity", "CORN",
       "food ethanol livestock"),
    _m("soybean", "soybean|soy|大豆|соя|فول الصويا|soja", "Soft Commodity", "SOYBEAN",
       "food livestock"),
    _m("coffee", "coffee|arabica|robusta|咖啡|コーヒー|кофе|قهوة|café|kaffee", "Soft Commodity",
       "COFARA COFROB", "food"),
    _m("sugar", "sugar|白糖|砂糖|сахар|سكر|azúcar|zucker", "Soft Commodity", "SUGAR SUGARRAW",
       "food ethanol"),
    _m("cocoa", "cocoa|可可|カカオ|какао|كاكاو|cacao|kakao", "Soft Commodity", "UKCOCOA USCOCOA",
       "food"),
    _m("cotton", "cotton|棉花|綿花|хлопок|قطن|algodón|baumwolle", "Soft Commodity", "COTTON",
       "textiles"),
    _m("orange_juice", "orange juice|橙汁|オレンジジュース|zumo de naranja", "Soft Commodity", "OJ",
       "food"),
)

COUNTRIES: tuple[Country, ...] = (
    _k("US", "united states|u.s.|america|washington|federal reserve|the fed|fomc|美国|"
       "米国|アメリカ|連邦準備|сша|фрс|أمريكا|estados unidos|vereinigte staaten", "USD",
       "natgas corn soybean wheat", "crude", "US500 NAS100 US30 US2000 USDX", "UST05Y UST10Y",
       "technology banks energy autos"),
    _k("EU", "european union|eurozone|euro area|brussels|european central bank|ecb|欧盟|"
       "欧州連合|欧州中央銀行|ецб|unión europea|europäische union", "EUR", "", "crude natgas",
       "EUSTX50 E35 NETH25", "", "autos banks chemicals"),
    _k("DE", "germany|german|berlin|德国|ドイツ|германия|ألمانيا|alemania|deutschland", "EUR",
       "", "natgas crude", "GER40", "", "autos chemicals machinery"),
    _k("FR", "france|french|paris|法国|フランス|франция|فرنسا|francia|frankreich", "EUR", "wheat",
       "crude natgas", "FRA40", "", "luxury aerospace nuclear"),
    _k("GB", "united kingdom|britain|british|london|bank of england|英国|イギリス|британ|"
       "بريطانيا|reino unido|grossbritannien", "GBP", "", "natgas crude", "UK100", "UKGILT",
       "banks energy"),
    _k("JP", "japan|japanese|tokyo|bank of japan|boj|日本|日銀|日本銀行|япони|اليابان|"
       "japón|japan", "JPY", "",
       "crude natgas copper", "JPN225", "", "autos electronics shipping"),
    _k("CN", "china|chinese|beijing|people's bank of china|pboc|中国|中國|人民银行|"
       "китай|الصين|chine", "CNH",
       "aluminium", "crude natgas copper soybean", "CHINAH HK50", "",
       "manufacturing property steel"),
    _k("RU", "russia|russian|moscow|kremlin|俄罗斯|ロシア|росси|руси|روسيا|rusia|"
       "russland", "RUB",
       "crude natgas palladium aluminium nickel wheat", "", "", "", "energy mining"),
    _k("UA", "ukraine|ukrainian|kyiv|kiev|乌克兰|ウクライナ|украин|أوكرانيا|ucrania",
       "UAH",
       "wheat corn", "", "", "", "agriculture"),
    _k("IL", "israel|israeli|tel aviv|以色列|イスラエル|израиль|إسرائيل", "ILS", "", "crude",
       "", "", "technology defence"),
    _k("IR", "iran|iranian|tehran|伊朗|イラン|иран|إيران|irán", "IRR", "crude natgas",
       "", "", "", "energy"),
    _k("SA", "saudi arabia|saudi|riyadh|沙特|サウジ|саудовск|السعودية|arabia saudí", "SAR",
       "crude", "", "", "", "energy"),
    _k("AE", "united arab emirates|uae|dubai|abu dhabi|阿联酋|uae|оаэ|الإمارات", "AED", "crude",
       "", "", "", "energy logistics"),
    _k("VE", "venezuela|caracas|委内瑞拉|ベネズエラ|венесуэл|فنزويلا", "VES", "crude", "", "",
       "", "energy"),
    _k("NG", "nigeria|nigerian|lagos|尼日利亚|ナイジェリア|нигери|نيجيريا", "NGN",
       "crude", "", "", "", "energy"),
    _k("AU", "australia|australian|canberra|sydney|澳大利亚|オーストラリア|австрали|أستراليا|"
       "australien", "AUD", "nickel aluminium copper wheat natgas", "crude", "AUS200", "",
       "mining"),
    _k("NZ", "new zealand|wellington|新西兰|ニュージーランド|новая зеландия", "NZD", "", "crude",
       "", "", "agriculture"),
    _k("CA", "canada|canadian|ottawa|加拿大|カナダ|канад|كندا|canadá|kanada", "CAD",
       "crude natgas wheat nickel", "", "CA60", "", "energy mining"),
    _k("NO", "norway|norwegian|oslo|挪威|ノルウェー|норвег|النرويج|noruega|norwegen", "NOK",
       "crude natgas", "", "", "", "energy shipping"),
    _k("CH", "switzerland|swiss|zurich|bern|瑞士|スイス|швейцар|سويسرا|suiza|schweiz", "CHF",
       "gold", "", "", "", "banks pharma"),
    _k("TR", "turkey|turkish|ankara|istanbul|土耳其|トルコ|турци|تركيا|turquía|türkei", "TRY",
       "", "crude natgas", "", "", "manufacturing"),
    _k("IN", "india|indian|delhi|mumbai|印度|インド|инди|الهند|india|indien", "INR", "cotton",
       "crude gold natgas", "", "", "technology refining"),
    _k("KR", "south korea|korea|seoul|韩国|韓国|한국|коре|كوريا|corea del sur|südkorea",
       "KRW", "",
       "crude natgas copper", "", "", "electronics shipbuilding autos"),
    _k("ZA", "south africa|johannesburg|pretoria|南非|南アフリカ|юар|جنوب أفريقيا|sudáfrica",
       "ZAR", "platinum palladium gold", "crude", "", "", "mining"),
    _k("BR", "brazil|brazilian|brasilia|sao paulo|巴西|ブラジル|бразили|البرازيل|brasil", "BRL",
       "soybean coffee sugar corn crude", "", "", "", "agriculture mining"),
    _k("MX", "mexico|mexican|mexico city|墨西哥|メキシコ|мексик|المكسيك|méxico", "MXN",
       "crude silver", "corn", "", "", "autos manufacturing"),
    _k("TW", "taiwan|taipei|台湾|台灣|тайвань|تايوان|taiwán", "TWD", "", "crude natgas", "", "",
       "semiconductors electronics"),
)

_BY_COMMODITY: dict[str, Commodity] = {c.commodity_id: c for c in COMMODITIES}
_BY_COUNTRY: dict[str, Country] = {c.code: c for c in COUNTRIES}
_ENTITY_TERMS: tuple[tuple[str, str], ...] = tuple(
    sorted(([(n.lower(), c.code) for c in COUNTRIES for n in c.names]
            + [(n.lower(), c.commodity_id) for c in COMMODITIES for n in c.names]),
           key=lambda pair: -len(pair[0])))


@dataclass(frozen=True)
class EntityGraph:
    """Country -> commodity -> industries -> currencies -> indices -> rates -> related assets.

    `universe` is MetaTrader's own registry when one is handed in, and the graph resolves ONLY to
    symbols it lists. With no universe the graph answers in the anchors and `class:` selectors the
    desk's other atlases already speak, so a caller with no broker book still gets a usable answer
    and can never be handed a symbol Fusion does not trade.
    """

    universe: dict[str, str] = field(default_factory=dict)
    actors: tuple[str, ...] = ()

    def symbols_of_class(self, asset_class: str) -> list[str]:
        want = " ".join(str(asset_class).lower().replace("_", " ").split())
        return sorted(s for s, cls in self.universe.items()
                      if " ".join(str(cls).lower().replace("_", " ").split()) == want)

    def known(self, symbol: str) -> bool:
        return not self.universe or symbol.upper() in self.universe

    def currency_pairs(self, ccy: str) -> list[str]:
        code = str(ccy).upper()
        if not self.universe:
            return []
        return sorted(s for s, cls in self.universe.items()
                      if code in s and str(cls).lower().startswith("forex"))

    def assets_for(self, entity: str) -> list[str]:
        """Every asset one entity reaches: its commodity anchors, currency pairs and indices."""
        out: list[str] = []
        commodity = _BY_COMMODITY.get(entity)
        if commodity is not None:
            out.extend(a for a in commodity.anchors if self.known(a))
        country = _BY_COUNTRY.get(entity)
        if country is not None:
            for cid in country.exports + country.imports:
                linked = _BY_COMMODITY.get(cid)
                if linked is not None:
                    out.extend(a for a in linked.anchors if self.known(a))
            out.extend(i for i in country.indices if self.known(i))
            out.extend(r for r in country.rates if self.known(r))
            out.extend(self.currency_pairs(country.currency)[:MAX_ASSETS_PER_EDGE])
        return sorted(dict.fromkeys(out))

    def industries_of(self, entity: str) -> list[str]:
        commodity = _BY_COMMODITY.get(entity)
        country = _BY_COUNTRY.get(entity)
        out = list(commodity.industries if commodity is not None else ())
        out.extend(country.industries if country is not None else ())
        return sorted(dict.fromkeys(out))

    def neighbours(self, entity: str) -> list[str]:
        """One hop: a country's commodities, a commodity's producing countries."""
        out: list[str] = []
        country = _BY_COUNTRY.get(entity)
        if country is not None:
            out.extend(country.exports + country.imports)
        if entity in _BY_COMMODITY:
            out.extend(c.code for c in COUNTRIES if entity in c.exports)
        return sorted(dict.fromkeys(out))


def seed_entity_graph(universe: Mapping[str, Mapping[str, Any]] | None = None,
                      actor_rows: Sequence[Mapping[str, Any]] | None = None) -> EntityGraph:
    """The declared graph, MERGED with the broker's registry and the actor atlas's own actors.

    The registry is the authority on what exists: a symbol it does not carry never leaves this
    graph, whatever the table above says. The actor atlas contributes the NAMES of participants,
    which the deep lane quotes when it says whose constraint an event is binding.
    """
    resolved: dict[str, str] = {}
    for sym, row in (universe or {}).items():
        if str(sym).startswith("_") or not isinstance(row, Mapping):
            continue
        cls = row.get("asset_class")
        resolved[str(sym).upper()] = "" if cls is None else str(cls)
    actors = tuple(dict.fromkeys(str(r.get("actor") or "") for r in (actor_rows or ())
                                 if str(r.get("actor") or "").strip()))
    return EntityGraph(universe=resolved, actors=actors)


def entities_in(text: str, limit: int = 12) -> list[str]:
    """Countries and commodities a body of text names, longest name first so 'south korea' wins."""
    low = " ".join(str(text or "").lower().split())
    out: list[str] = []
    for term, entity in _ENTITY_TERMS:
        if entity in out:
            continue
        if term in low:
            out.append(entity)
        if len(out) >= limit:
            break
    return out


# ============================================================================= classification
class Affected(NamedTuple):
    """One asset in the transmission path, when it moves, and what decides the sign."""

    asset: str
    horizon: str
    state_vars: tuple[str, ...]


@dataclass(frozen=True)
class EventGuess:
    """What the ontology reads off a piece of text. `other` is a verdict, never a silent drop."""

    kind: str
    entities: tuple[str, ...]
    confidence: float
    matched: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    scores: tuple[tuple[str, float], ...] = ()
    rule: str = ""


@dataclass(frozen=True)
class Novelty:
    """Whether this is a genuinely new escalation or the two-hundredth telling of one."""

    score: float
    repeats: int
    max_similarity: float
    nearest_id: str = ""
    basis: str = ""


@dataclass(frozen=True)
class Surprise:
    """Scheduled versus unscheduled, and the consensus z where the calendar carries one."""

    score: float
    basis: str
    measured: bool
    z: float | None = None


_TOKEN = re.compile(r"[a-z0-9]{2,}|[一-鿿぀-ヿ가-힯]")


def _tokens(text: str) -> frozenset[str]:
    return frozenset(_TOKEN.findall(str(text or "").lower()))


def _cosine(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return float(len(a & b) / math.sqrt(len(a) * len(b)))


def classify(text: str, concepts: Iterable[str] = ()) -> EventGuess:
    """Which kind of event a document describes, from keyword tables in ten languages.

    Concept ids from `polyglot.canonicalise` are accepted and weighted like a keyword hit, so a
    Japanese post saying 仲値 reaches the calendar vocabulary through polyglot and a post saying
    侵攻 reaches war through the table here. A document that matches nothing is `other` at zero
    confidence -- which is a MEASUREMENT of the frontier, not a failure to be hidden.
    """
    low = " ".join(str(text or "").lower().split())
    scores: dict[str, float] = {}
    matched: dict[str, list[str]] = {}
    langs: dict[str, set[str]] = {}
    for kind, by_lang in KEYWORDS.items():
        for lang, terms in by_lang.items():
            for term in terms:
                if term and term in low:
                    scores[kind] = scores.get(kind, 0.0) + 1.0
                    matched.setdefault(kind, []).append(term)
                    langs.setdefault(kind, set()).add(lang)
    for cid in concepts:
        implied = CONCEPT_KIND.get(str(cid))
        if implied is not None:
            scores[implied] = scores.get(implied, 0.0) + 0.8
            matched.setdefault(implied, []).append(f"concept:{cid}")
    if not scores:
        return EventGuess("other", tuple(entities_in(low)), 0.0, (), (), (),
                          "no kind vocabulary matched: UNMEASURED, and counted as `other`")
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    kind, best = ranked[0]
    total = sum(scores.values())
    hits = len(matched.get(kind, ()))
    confidence = (best / total) * min(1.0, 0.45 + 0.18 * hits)
    return EventGuess(kind=kind, entities=tuple(entities_in(low)),
                      confidence=round(float(confidence), 4),
                      matched=tuple(dict.fromkeys(matched.get(kind, [])))[:8],
                      languages=tuple(sorted(langs.get(kind, set()))),
                      scores=tuple((k, round(v, 3)) for k, v in ranked[:4]),
                      rule="the kind is the vocabulary that matched; the sign is never here")


def event_key(kind: str, entities: Iterable[str]) -> str:
    """The identity a FOLLOW-UP headline shares with the first one: kind plus entity set."""
    ents = ",".join(sorted({str(e).strip().upper() for e in entities if str(e).strip()}))
    return f"{str(kind).strip().lower()}|{ents or 'UNKNOWN'}"


def event_id(kind: str, entities: Iterable[str]) -> str:
    return "ev_" + hashlib.sha256(event_key(kind, entities).encode("utf-8")).hexdigest()[:14]


def resolve_event_id(kind: str, entities: Iterable[str],
                     recent: Sequence[Mapping[str, Any]]) -> str:
    """The id a FOLLOW-UP belongs to, or a fresh one when nothing running matches.

    `event_id` alone keys on the EXACT entity set, and a running story does not oblige: the first
    wire names Israel and Iran, the second names only Iran, the third names Iran and a strait. By
    the exact key those are three events, the novelty window never sees a repetition, and the same
    story walks the world state three times. So a candidate whose kind matches and whose entities
    INTERSECT an event already in the window adopts that event's id -- most recent first, because
    a story is continued from where it got to.
    """
    ents = {str(e).strip().upper() for e in entities if str(e).strip()}
    if ents:
        for row in reversed(list(recent)):
            if str(row.get("kind") or "") != str(kind):
                continue
            theirs = {str(e).strip().upper() for e in (row.get("entities") or ())}
            running = str(row.get("event_id") or row.get("id") or "")
            if running and theirs and (ents & theirs):
                return running
    return event_id(kind, ents)


def novelty_of(event: Mapping[str, Any], recent: Sequence[Mapping[str, Any]]) -> Novelty:
    """A genuinely new escalation scores 1.0; the two-hundredth repetition scores ~0.

    Dedupe is by ENTITY + KIND + claim similarity inside whatever window the caller passed. Two
    rows about different countries are two events however similar the wire's phrasing, and two
    rows about the same country with the same kind are one event however differently phrased --
    which is the whole reason the entity graph exists.
    """
    kind = str(event.get("kind") or "other")
    ents = {str(e).upper() for e in (event.get("entities") or ())}
    mine = _tokens(event.get("claim") or event.get("text") or event.get("title") or "")
    repeats, best, nearest = 0, 0.0, ""
    for row in recent:
        if str(row.get("kind") or "") != kind:
            continue
        theirs = {str(e).upper() for e in (row.get("entities") or ())}
        if ents and theirs and not (ents & theirs):
            continue
        sim = _cosine(mine, _tokens(row.get("claim") or row.get("text") or row.get("title") or ""))
        if sim > best:
            best, nearest = sim, str(row.get("event_id") or row.get("id") or "")
        if sim >= DUP_SIMILARITY or (ents and theirs and ents == theirs):
            repeats += 1
    score = 1.0 / (1.0 + float(repeats))
    if best > 0.0:
        score = min(score, max(0.0, 1.0 - best))
    basis = ("no prior row shares this kind and entity" if repeats == 0
             else f"{repeats} prior rows share kind+entity; nearest claim similarity {best:.2f}")
    return Novelty(round(float(score), 4), int(repeats), round(float(best), 4), nearest, basis)


def novelty(event: Mapping[str, Any], recent: Sequence[Mapping[str, Any]]) -> float:
    return novelty_of(event, recent).score


def surprise_of(event: Mapping[str, Any],
                expectations: Mapping[str, Any] | None = None) -> Surprise:
    """Scheduled versus unscheduled, and the consensus z where the calendar carries one.

    A release the desk holds no ACTUAL for gets the DECLARED prior with UNMEASURED in its basis
    (L1.28a). Not a zero: a zero would silently mute the deep lane on the scheduled prints that
    move the book most, which is a reduction in aggressiveness nobody voted for.
    """
    exp: Mapping[str, Any] = expectations or {}
    kind = str(event.get("kind") or "other")
    spec = ONTOLOGY.get(kind)
    scheduled = bool(exp.get("scheduled", spec.scheduled if spec is not None else False))
    if not scheduled:
        return Surprise(1.0, "unscheduled: the world did not know it was coming", True)
    actual, consensus, sigma = exp.get("actual"), exp.get("consensus"), exp.get("sigma")
    if isinstance(actual, int | float) and isinstance(consensus, int | float):
        sd = float(sigma) if isinstance(sigma, int | float) and float(sigma) > 0 else 1.0
        z = (float(actual) - float(consensus)) / sd
        return Surprise(round(min(1.0, abs(z) / SURPRISE_Z_CAP), 4),
                        f"consensus z over the release's own surprise sigma ({sd:g})", True, z)
    why = "no actual" if consensus is not None else "no consensus"
    return Surprise(SCHEDULED_PRIOR, f"scheduled, {why}: UNMEASURED, declared prior "
                                     f"{SCHEDULED_PRIOR}", False)


def surprise(event: Mapping[str, Any], expectations: Mapping[str, Any] | None = None) -> float:
    return surprise_of(event, expectations).score


def affected(event: Mapping[str, Any], graph: EntityGraph | None = None) -> list[Affected]:
    """Every asset the event's kind and entities put in the transmission path, with its horizon.

    DIRECTION-AGNOSTIC. An asset appears here because a mechanism connects it to the event, not
    because the desk thinks it goes up: the `state_vars` on each row are exactly the readings that
    decide the sign, and they are measured elsewhere.
    """
    g = graph if graph is not None else EntityGraph()
    kind = str(event.get("kind") or "other")
    spec = ONTOLOGY.get(kind)
    if spec is None or not spec.edges:
        # A kind with no declared edge claims NO transmission -- `other` included. Naming the
        # entity's assets anyway would turn "the desk could not classify this" into a statement
        # about which markets it reaches, which is the one thing an unclassified row cannot say.
        return []
    ents = [str(e) for e in (event.get("entities") or ())]
    entity_assets = {a for e in ents for a in g.assets_for(e)}
    out: dict[str, Affected] = {}
    for edge in spec.edges:
        # THE ANCHORS COME FIRST AND THE CLASS IS THE FALLBACK, in that order and never mixed by
        # alphabet. An edge that names XTIUSD is about crude; filling the row with the first
        # eight symbols of `Energy` sorted A-Z would bury the anchor under whatever the broker
        # happens to list, and the resolve request would describe an event nobody had.
        assets: list[str] = [a for a in edge.anchors if g.known(a)]
        assets.extend(a for a in sorted(entity_assets)
                      if a not in assets and _class_of(g, a) == edge.asset_class)
        if not assets:
            # No anchor and no entity reached this class: the WHOLE class is in the path and the
            # ontology cannot name a symbol inside it. `class:` is the actor atlas's own selector
            # vocabulary, so a consumer resolves it against the registry rather than guessing.
            assets.append(f"class:{edge.asset_class}")
        for asset in list(dict.fromkeys(assets))[:MAX_ASSETS_PER_EDGE]:
            if asset not in out:
                out[asset] = Affected(asset, edge.horizon, edge.state_vars)
    for asset in sorted(entity_assets):
        if asset not in out and len(out) < MAX_ASSETS_PER_EDGE * 4:
            out[asset] = Affected(asset, "days", ("term_of_trade", "net_exporter", "liquidity"))
    return list(out.values())


def _class_of(graph: EntityGraph, symbol: str) -> str:
    return graph.universe.get(str(symbol).upper(), "")


@dataclass(frozen=True)
class Analogue:
    """A prior event that shares this one's kind and entities. A place to look, never a forecast."""

    event_id: str
    kind: str
    at: str
    score: float
    entities: tuple[str, ...]
    reaction: dict[str, Any] = field(default_factory=dict)
    note: str = ("an analogue is a place to look. The desk never assumes a prior event repeats: "
                 "the reaction carried here is what the atlas MEASURED then, over its own n")


def analogues(event: Mapping[str, Any], history: Sequence[Mapping[str, Any]],
              limit: int = MAX_ANALOGUES) -> list[Analogue]:
    """Prior events scored on kind, entity overlap and claim similarity, best first."""
    kind = str(event.get("kind") or "other")
    ents = {str(e).upper() for e in (event.get("entities") or ())}
    mine = _tokens(event.get("claim") or event.get("text") or event.get("title") or "")
    rows: list[Analogue] = []
    for row in history:
        rkind = str(row.get("kind") or "")
        rents = {str(e).upper() for e in (row.get("entities") or ())}
        overlap = (len(ents & rents) / len(ents | rents)) if (ents or rents) else 0.0
        sim = _cosine(mine, _tokens(row.get("claim") or row.get("text") or row.get("title") or ""))
        score = 0.5 * float(rkind == kind) + 0.3 * overlap + 0.2 * sim
        if score < ANALOGUE_FLOOR:
            continue
        reaction = row.get("reaction")
        rows.append(Analogue(str(row.get("event_id") or row.get("id") or ""), rkind or "other",
                             str(row.get("at") or UNMEASURED), round(float(score), 4),
                             tuple(sorted(rents)),
                             dict(reaction) if isinstance(reaction, Mapping) else {}))
    rows.sort(key=lambda a: (-a.score, a.at))
    return rows[:limit]
