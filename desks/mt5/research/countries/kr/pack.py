"""THE SOUTH KOREA COUNTRY PACK -- Korea's own mechanics, held as data and checked against MT5.

WHY KOREA IS NOT JAPAN WITH DIFFERENT NOUNS. Japan's calendar edge is the gotobi settlement day
and the 09:55 TTM fix. Korea has neither. What Korea has instead, and nowhere else in the region
does, is:

  * A CUSTOMS PRINT THREE TIMES A MONTH. The 관세청 publishes exports and imports for the first
    ten days, the first twenty days and the full month. The 1st-20th figure lands on the 21st at
    about 09:00 KST -- 00:00 UTC, the same minute the onshore FX market opens -- and it is the
    world's earliest hard read on global semiconductor and shipping demand. No other economy
    publishes trade data at that frequency with that lag.
  * THE SECOND THURSDAY. KOSPI200 futures and options expire on the SECOND Thursday of the
    contract month, not the third Friday and not Taiwan's third Wednesday. Four times a year
    (March, June, September, December) index futures, index options, single-stock futures and
    single-stock options expire together -- the 네 마녀의 날. The settlement price comes out of
    the 15:20-15:30 closing call auction, so the mechanism, if it exists, lives in a ten-minute
    window, not a day.
  * A RETAIL BASE MEASURED DAILY. 금융투자협회 publishes 신용융자잔고 (margin loans) and 예탁금
    (cash parked at brokers) every business day with a one-day lag. Very few markets publish
    household leverage daily; Korea does, and the 동학개미 wave of 2020-2021 is the regime where
    that series stopped being a footnote.
  * A PENSION FUND BIG ENOUGH TO BE AN FX ACTOR. The NPS holds well over a trillion dollars of
    assets, most of it offshore, and its strategic FX hedging is RULE-BASED and DISCLOSED -- and
    its swap line with the Bank of Korea exists precisely so that the hedge does not have to be
    executed in the spot market. That is a forced flow with a published trigger.

WHAT THIS PACK MAY NOT DO. The semiconductor complex is the loudest mechanism in Korea and it
enters here as an INDEX and FX transmission only: 반도체 수출 is an observable, the two chipmakers
are named in terminology so a Korean-language miner recognises the words, and neither is ever a
symbol on a docket (two-lane order, 2026-09-06). The kimchi premium is a real KRW and risk-
appetite observable and it is carried as PUBLIC COMMENTARY with `pit_feasible=False`: no crypto
venue is subscribed, named or crawled anywhere in this pack (universe mandate, 2026-08-18). The
executable leg of that domain is the broker's own BTCUSD CFD, which is inside the MT5 universe.

WHAT IS EXECUTABLE. USDKRW is in the broker's registry, so Korea is the only pack in this package
whose own currency trades directly. KOSPI200 and KOSDAQ150 are NOT, and they are named in
`ABSENT_INSTRUMENTS` rather than quietly dropped -- their economics route through JPN225, HK50 and
NAS100 by the seeds in `TRANSMISSION_EDGES_SEED`.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- the local adapter
# NOTHING IN THIS FILE IMPORTS ANOTHER MODULE OF THIS PACKAGE, AND THAT IS DELIBERATE. Several
# country departments are being written into `research/countries/` at the same time, by different
# builders, against different row vocabularies. A pack that depends on a shared helper module is
# a pack that breaks the hour a sibling rewrites that module -- so the small adapter below is
# carried here, and this file is readable, testable and runnable entirely on its own.

#: The twenty-one fields of `libs.research.country_lab.CountryPack`, in the framework's order.
PACK_FIELDS: tuple[str, ...] = (
    "code", "name", "region_command", "currency", "executable_instruments", "central_bank",
    "fixing_conventions", "settlement_conventions", "exchanges", "holidays_rule",
    "fiscal_year_end", "positioning_sources", "native_languages", "terminology", "source_classes",
    "datasets", "actors", "domains", "custom_miners", "transmission_edges_seed", "policy_eras")

#: Section 2 of the region mandate: the eleven things a pack must be able to say about an actor
#: before the chain Actor -> Constraint -> Observable -> Flow -> MarketImpact -> Candidate can be
#: walked without inventing a link. An actor whose FALSIFIER is blank is a story.
ACTOR_FIELDS: tuple[str, ...] = ("holds", "forced_to", "when", "information", "constraints",
                                 "instruments", "counterparties", "observables", "impact",
                                 "persistence", "falsifier")

#: The ten fields every dataset entry owes. `pit_feasible` is the one the catalogue exists for: a
#: dataset whose vintage cannot be reconstructed can only ever produce NOT_PIT_SAFE cells.
DATASET_FIELDS: tuple[str, ...] = (
    "name", "source", "coverage", "frequency", "publication_lag_days", "revisions", "licence",
    "history_from", "pit_feasible", "assets", "mechanism_families", "how_to_fetch")


def _seq(value: object) -> tuple[str, ...]:
    """A field that must be a sequence of strings, from either a sequence or a bare string.

    THIS EXISTS BECAUSE OF A REAL BUG IN THIS PACKAGE. A one-element tuple written `("...")` is
    a STRING, not a tuple, and `tuple()` on a string yields ONE ENTRY PER CHARACTER. An actor's
    `counterparties` silently became forty-one single letters, every non-empty check still
    passed, and the row read as complete. Coercing here is the only place that can catch it:
    by the time any caller sees the row, a character explosion and a deliberate list of
    one-character strings are indistinguishable. The tests pin it from the other side by
    refusing any entry shorter than two characters.
    """
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(x) for x in value)


def actor(name: str, *, holds: str, forced_to: Sequence[str], when: str,
           information: Sequence[str], constraints: Sequence[str], instruments: Sequence[str],
           counterparties: Sequence[str], observables: Sequence[str], impact: str,
           persistence: str, falsifier: str, notes: str = "") -> dict[str, Any]:
    """One economic actor with all eleven fields filled."""
    return {"name": name, "holds": holds, "forced_to": _seq(forced_to), "when": when,
            "information": _seq(information), "constraints": _seq(constraints),
            "instruments": _seq(instruments), "counterparties": _seq(counterparties),
            "observables": _seq(observables), "impact": impact, "persistence": persistence,
            "falsifier": falsifier, "notes": notes}


def domain(did: str, title: str, *, objects: Sequence[str], conditions: Sequence[str],
            instruments: Sequence[str], controls: Sequence[str],
            notes: str = "") -> dict[str, Any]:
    """One research domain. `controls` is never optional: without a negative control an effect
    cannot be told apart from the desk's own sampling."""
    return {"id": did, "title": title, "objects": _seq(objects), "conditions": _seq(conditions),
            "instruments": _seq(instruments), "controls": _seq(controls), "notes": notes}


def dataset(name: str, *, source: str, coverage: str, frequency: str,
             publication_lag_days: float, revisions: str, licence: str, history_from: str,
             pit_feasible: bool, assets: Sequence[str], mechanism_families: Sequence[str],
             how_to_fetch: str) -> dict[str, Any]:
    """One catalogue entry of the data-discovery swarm."""
    return {"name": name, "source": source, "coverage": coverage, "frequency": frequency,
            "publication_lag_days": float(publication_lag_days), "revisions": revisions,
            "licence": licence, "history_from": history_from, "pit_feasible": bool(pit_feasible),
            "assets": _seq(assets), "mechanism_families": _seq(mechanism_families),
            "how_to_fetch": how_to_fetch}


#: THE TEN SOURCE LAYERS (principal's per-country depth rule, 2026-09-17). Every source carries
#: EXACTLY ONE, and every pack must name at least one source in each layer or declare the layer
#: ABSENT with a reason. A country is never "covered" by five obvious sources: five official
#: roots is one layer done and nine layers missing, and the missing nine are where a mechanism
#: nobody has tested is still lying around.
SOURCE_LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology", "app_ecosystem",
    "media", "archive", "physical_economy", "source_graph")

#: How the desk is allowed to reach a source. Three INDEPENDENT labels travel with every source
#: and this is the first: what the terms permit, which is a legal fact and not a quality one.
ACCESS_LABELS: tuple[str, ...] = (
    "PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA", "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL",
    "USER_SUBMITTED", "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")

#: The second label: how much the desk believes the source, which is independent of what it is
#: allowed to read. FRINGE and CONTRADICTED material is KEPT as an evidence object at low weight
#: and never dropped -- a claim that looks false is still a dated, testable claim, and deleting
#: it destroys the only record that it was ever made.
CREDIBILITY_LABELS: tuple[str, ...] = (
    "AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE", "CONTRADICTED", "UNKNOWN")

#: The third label, and the only one the desk can EARN: whether anything from this source has
#: ever predicted anything. UNTESTED is the honest default and it is not a criticism.
#: NARRATIVE_FEATURE means the text is useful as a conditioning variable even though its claims
#: do not forecast, which is a real and separate finding.
PREDICTIVE_STATES: tuple[str, ...] = (
    "UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE", "NARRATIVE_FEATURE")


def source_class(sid: str, label: str, *, layer: str, roots: Sequence[str],
                 queries: Sequence[str], languages: Sequence[str], access_label: str,
                 credibility: str, predictive_state: str, licence: str,
                 machine_use_allowed: bool = True, notes: str = "") -> dict[str, Any]:
    """One class of source, with the roots a crawler can start from and its three labels.

    `queries` are NATIVE-SCRIPT search terms and slang, never translated English: a miner that
    searches an English phrase on a Chinese, Korean or Taiwanese ground finds the small
    English-speaking corner of that ground and then reports the result as if it were the ground.

    `machine_use_allowed=True` registers a source whose terms forbid machine extraction. It is
    NEVER scraped and NEVER omitted: the row stays so the desk knows the ground exists, knows it
    was considered, and knows exactly why it is not being read.
    """
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"source {sid}: layer {layer!r} not one of {list(SOURCE_LAYERS)}")
    if access_label not in ACCESS_LABELS:
        raise ValueError(f"source {sid}: access_label {access_label!r} not one of "
                         f"{list(ACCESS_LABELS)}")
    if credibility not in CREDIBILITY_LABELS:
        raise ValueError(f"source {sid}: credibility {credibility!r} not one of "
                         f"{list(CREDIBILITY_LABELS)}")
    if predictive_state not in PREDICTIVE_STATES:
        raise ValueError(f"source {sid}: predictive_state {predictive_state!r} not one of "
                         f"{list(PREDICTIVE_STATES)}")
    return {"id": sid, "label": label, "layer": layer, "roots": _seq(roots),
            "queries": _seq(queries), "languages": _seq(languages),
            "access_label": access_label, "credibility": credibility,
            "predictive_state": predictive_state,
            "machine_use_allowed": bool(machine_use_allowed), "licence": licence, "notes": notes}


def absent_layer(layer: str, reason: str) -> dict[str, Any]:
    """A layer this country has nothing in, declared BY NAME with the reason.

    A blank layer and an absent layer look identical in a table and mean opposite things: one is
    work not done, the other is a measurement. This row makes the second one visible (L1.28a).
    """
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"absent layer {layer!r} not one of {list(SOURCE_LAYERS)}")
    return {"id": f"absent_{layer}", "label": f"NO SOURCE IN THIS LAYER: {layer}", "layer": layer,
            "roots": (), "queries": (), "languages": (), "access_label": "ACCESS_UNCLEAR",
            "credibility": "UNKNOWN", "predictive_state": "UNTESTED",
            "machine_use_allowed": False, "licence": "n/a",
            "notes": f"DECLARED ABSENT, NOT BLANK: {reason}"}


def layer_counts(classes: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """How many real sources this pack names in each of the ten layers. A zero is a hole, and an
    `absent_*` row does not count toward it -- declaring a layer absent is honest, not coverage.
    """
    out = dict.fromkeys(SOURCE_LAYERS, 0)
    for sc in classes:
        layer = str(sc.get("layer") or "")
        if layer in out and not str(sc.get("id") or "").startswith("absent_"):
            out[layer] += 1
    return out


def edge(eid: str, *, source: str, mechanism: str, targets: Sequence[str], sign: str,
          horizon: str, lag: str, control: str, evidence: str = "HYPOTHESIS",
          notes: str = "") -> dict[str, Any]:
    """One transmission seed. `targets` are BROKER SYMBOLS and the tests refuse any that are not
    in `desks/mt5/data/universe/universe.json`, or that are single-name equities."""
    return {"id": eid, "source": source, "mechanism": mechanism, "targets": _seq(targets),
            "sign": sign, "horizon": horizon, "lag": lag, "control": control,
            "evidence": evidence, "notes": notes}


def era(eid: str, *, start: str, end: str | None, label: str, what_changed: str,
         invalidates: str, notes: str = "") -> dict[str, Any]:
    """One policy or market-design regime. `invalidates` names what a study pooled ACROSS this
    boundary is actually measuring, which is the only reason an era table earns its keep."""
    return {"id": eid, "start": start, "end": end, "label": label, "what_changed": what_changed,
            "invalidates": invalidates, "notes": notes}


def miner(name: str, *, domain_ids: Sequence[str], kind: str, entry: str,
           cadence_s: float = 3600.0, steerable: bool = True,
           notes: str = "") -> dict[str, Any]:
    """One named specialist. `entry` is a dotted module:function that must actually resolve."""
    return {"name": name, "domain_ids": _seq(domain_ids), "kind": kind, "entry": entry,
            "cadence_s": float(cadence_s), "steerable": bool(steerable), "notes": notes}


def holiday_table(rule: Mapping[str, Any], year: int) -> dict[str, str]:
    """One year of a holidays rule's resolved closure table. An absent year returns an empty dict
    rather than an invented one."""
    got = dict(rule.get("table") or {}).get(year) or {}
    return {str(k): str(v) for k, v in dict(got).items()}


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th `weekday` (Monday = 0) of a month."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return date(year, month, 1 + offset + 7 * (n - 1))


# --------------------------------------------------------------------------- the broker registry
DESK = Path(__file__).resolve().parents[3]
UNIVERSE_JSON: Path = DESK / "data" / "universe" / "universe.json"
#: The broker's own classes for a single name. No pack may name one as executable (two-lane
#: order, 2026-09-06).
EQUITY_CLASSES: frozenset[str] = frozenset({"equities", "equity", "shares", "share cfd"})


def resolve(symbols: Sequence[str], path: Path | None = None) -> dict[str, list[str]]:
    """Split a symbol list into what the box can trade, what is an equity and what is absent.

    An unreadable registry returns everything as ABSENT rather than as tradable: absence is never
    permission (L1.28a), and a silent pass here would let an unquotable symbol reach a docket.
    """
    target = Path(path) if path is not None else UNIVERSE_JSON
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    reg = raw if isinstance(raw, dict) else {}
    out: dict[str, list[str]] = {"tradable": [], "equities": [], "absent": []}
    for sym in symbols:
        row = reg.get(str(sym))
        if not isinstance(row, dict):
            out["absent"].append(str(sym))
            continue
        klass = " ".join(str(row.get("asset_class") or "").lower().replace("_", " ").split())
        out["equities" if klass in EQUITY_CLASSES else "tradable"].append(str(sym))
    return out


CODE = "kr"
NAME = "South Korea"
REGION_COMMAND = "asia"  # country_lab.REGION_COMMANDS; EAST ASIA is this package
CURRENCY = "KRW"
NATIVE_LANGUAGES = ("ko",)

#: Korea's OWN price on this broker. One symbol, and it is the reason this pack can be tested at
#: all: every other Korean mechanism has to be carried by something else.
OWN_PRICE: tuple[str, ...] = ("USDKRW",)

#: What the KR department may place an order in. USDKRW is Korea's own price; the rest are the
#: carriers its transmission seeds terminate in, and every one is in the broker's registry and is
#: not a single-name equity.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDKRW", "USDJPY", "USDSGD", "JPN225", "HK50", "NAS100", "US500", "XAUUSD", "XTIUSD",
    "XNGUSD", "BTCUSD")

#: The instruments a Korean desk would reach for that THIS broker does not quote. Named, with what
#: carries them instead, because a silently dropped instrument becomes a silently dropped
#: mechanism.
ABSENT_INSTRUMENTS: tuple[dict[str, str], ...] = (
    {"instrument": "KOSPI200 index (or its future)",
     "why": "no Korean equity index CFD in desks/mt5/data/universe/universe.json",
     "carried_by": "JPN225 and HK50 for the Asian session leg, NAS100 for the semiconductor leg"},
    {"instrument": "KOSDAQ150 index",
     "why": "absent from the broker registry",
     "carried_by": "NAS100 (the small-cap technology beta) with an explicit basis caveat"},
    {"instrument": "KRW/JPY cross (KRWJPY)",
     "why": "absent; the broker quotes USDKRW and USDJPY separately",
     "carried_by": "a synthetic USDKRW / USDJPY ratio, which carries two spreads and is stated "
                   "as a cost, not assumed away"},
    {"instrument": "3-year Korean Treasury Bond future (KTB3)",
     "why": "absent; no Korean rates instrument is quoted",
     "carried_by": "UST05Y and UST10Y as the global rates leg, with the Korea-specific term "
                   "premium left UNMEASURED by name"},
)


# --------------------------------------------------------------------------- central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Bank of Korea",
    "native_name": "한국은행",
    "committee": "금융통화위원회 (Monetary Policy Board), seven members including the Governor",
    "policy_rate": "기준금리 (Base Rate), the 7-day repo rate",
    "meetings_per_year": 8,
    "schedule_rule": (
        "Eight rate-setting meetings a year since 2017. The following year's dates are published "
        "in advance, normally in December. The decision is announced at about 09:55-10:00 KST "
        "(00:55-01:00 UTC) while the onshore FX market is already open, and the Governor's press "
        "conference follows at about 11:10 KST (02:10 UTC) -- so the decision and the "
        "explanation are two separate events in the same session and must be studied as two."),
    "minutes_rule": (
        "의사록 (minutes) are released about two weeks after each meeting, at 16:00 KST "
        "(07:00 UTC), after the onshore close. Dissent counts have moved USDKRW on release."),
    "timezone": "KST = UTC+9 all year; Korea observes NO daylight saving, so every UTC time in "
                "this pack is fixed and never shifts against the broker's UTC+2/UTC+3 server.",
    "fx_operations": (
        "한국은행 and 기획재정부 act jointly. The ladder is public and graded: 예의주시 "
        "(watching closely) -> 쏠림 (one-sided moves) language -> 구두개입 (explicit verbal "
        "intervention, often attributed to both bodies) -> actual smoothing operations. Only the "
        "language is observable in real time; the transactions are disclosed QUARTERLY."),
    "intervention_disclosure": (
        "외환당국 순거래 (net FX transactions) has been published quarterly since 2019Q1 with "
        "roughly a three-month lag. It is far too slow to signal and is useful only for ex-post "
        "attribution -- which is exactly why the verbal ladder above is the real-time observable."),
    "nps_swap": (
        "국민연금-한국은행 외환스와프. First agreed 2022-12 at USD 35bn, later raised to USD 65bn "
        "and repeatedly extended. MECHANISM: the NPS borrows dollars from the BOK's reserves "
        "instead of buying them in the spot market, so a scheduled hedging need that would "
        "otherwise be structural KRW selling never reaches the market. The swap's size, renewal "
        "and drawdown are announced; the drawdown timing is the flow observable."),
    "decision_dates": {
        2020: ("2020-01-17", "2020-02-27", "2020-03-16", "2020-04-09", "2020-05-28", "2020-07-16",
               "2020-08-27", "2020-10-14", "2020-11-26"),
        2021: ("2021-01-15", "2021-02-25", "2021-04-15", "2021-05-27", "2021-07-15", "2021-08-26",
               "2021-10-12", "2021-11-25"),
        2022: ("2022-01-14", "2022-02-24", "2022-04-14", "2022-05-26", "2022-07-13", "2022-08-25",
               "2022-10-12", "2022-11-24"),
        2023: ("2023-01-13", "2023-02-23", "2023-04-11", "2023-05-25", "2023-07-13", "2023-08-24",
               "2023-10-19", "2023-11-30"),
        2024: ("2024-01-11", "2024-02-22", "2024-04-12", "2024-05-23", "2024-07-11", "2024-08-22",
               "2024-10-11", "2024-11-28"),
        2025: ("2025-01-16", "2025-02-25", "2025-04-17", "2025-05-29", "2025-07-10", "2025-08-28",
               "2025-10-23", "2025-11-27"),
        2026: (),
    },
    "decision_dates_status": {
        2020: "RECONSTRUCTED_FROM_PUBLIC_RECORD -- includes the 2020-03-16 EMERGENCY meeting "
              "(-50bp to 0.75%), which is not part of the eight-meeting schedule",
        2021: "RECONSTRUCTED_FROM_PUBLIC_RECORD",
        2022: "RECONSTRUCTED_FROM_PUBLIC_RECORD -- 2022-07-13 and 2022-10-12 are the two 50bp "
              "빅스텝 moves",
        2023: "RECONSTRUCTED_FROM_PUBLIC_RECORD -- 2023-01-13 is the terminal 3.50% and the "
              "start of the long hold",
        2024: "RECONSTRUCTED_FROM_PUBLIC_RECORD -- 2024-10-11 is the first cut of the easing cycle",
        2025: "RECONSTRUCTED_FROM_PUBLIC_RECORD",
        2026: "RULE_ONLY -- the BOK publishes the following year's dates in December. Eight "
              "meetings, historically mid-January, late February, mid-April, late May, mid-July, "
              "late August, mid-October and late November. VERIFY against bok.or.kr before any "
              "event study touches 2026; a guessed decision date is a fabricated event window.",
    },
    "verification": "Every date above must be re-read from the BOK's own 통화정책방향 archive "
                    "before it is used as an event anchor. They are recorded here so a miner has "
                    "a starting grid, not so a study can skip the check.",
}


# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: dict[str, Any] = {
    "mar": {
        "name": "매매기준율 / Market Average Rate (MAR)",
        "publisher": "서울외국환중개 (Seoul Money Brokerage Services, SMBS)",
        "definition": "the transaction-weighted average of the PREVIOUS business day's interbank "
                      "USD/KRW spot (T+2) trades",
        "published_local": "about 09:00 KST",
        "published_utc": "00:00 UTC",
        "note": "It is a BACKWARD-LOOKING average published as a forward-looking reference. Any "
                "study that treats the MAR as a contemporaneous price is off by one session.",
    },
    "ndf_fix": {
        "name": "KRW NDF fixing",
        "reference": "the MAR of the fixing date",
        "convention": "non-deliverable, USD-settled, fixing T-1 against T+2 settlement",
        "why_it_matters": "the offshore NDF book is most active during the London and New York "
                          "afternoons, which is why the largest USDKRW gaps in the sample form "
                          "between the 06:30 UTC onshore close and the 00:00 UTC open rather "
                          "than inside either session",
    },
    "onshore_hours": {
        "legacy": "09:00-15:30 KST = 00:00-06:30 UTC",
        "extended": "from 2024-07-01 the onshore interbank market runs to 02:00 KST next day "
                    "= 17:00 UTC, and Registered Foreign Institutions (RFIs) were admitted",
        "break": "2024-07-01 IS A MICROSTRUCTURE BREAK. Any USDKRW intraday or overnight-gap "
                 "study that pools before and after it is pooling two market designs, and the "
                 "overnight gap it measures is defined differently on each side of the line.",
    },
    "broker_quote": {
        "symbol": "USDKRW",
        "asset_class_in_registry": "Forex Exotics",
        "what_it_is_outside_onshore_hours": "an offshore NDF-implied spot, not the onshore "
                                            "interbank price; the two can differ materially "
                                            "during a stress episode and that GAP is itself one "
                                            "of this pack's observables",
    },
    "dst": "NONE. KST is UTC+9 year-round. The venue's own clock moves (UTC+2 winter, UTC+3 "
           "summer) and Korea's does not, so every broker-hour mapping in a KR study must be "
           "recomputed per season even though the Korean times never change.",
}

SETTLEMENT_CONVENTIONS: dict[str, Any] = {
    "spot": "T+2, settled onshore through BOK-Wire+",
    "deliverability": "KRW is NOT deliverable offshore. The offshore expression is the NDF, and "
                      "that restriction is what creates the onshore/offshore basis this pack "
                      "treats as an observable rather than as noise.",
    "equity_settlement": "T+2 at KRX; foreign investors settle through custodians, and the "
                         "resulting FX conversion lands one to two sessions after the trade -- "
                         "so the KRX net-buy print LEADS its own FX flow.",
    "month_end": "수출업체 네고 (exporter conversion) concentrates in the last two to three "
                 "business days of the month and again around the customs release on the 21st.",
    "dividend_season": "April and May. Foreign holders of Korean equities repatriate won "
                       "dividends, which is the single largest documented seasonal KRW-selling "
                       "window of the year. December ex-dividend positioning is its mirror.",
    "year_end": "KRX closes for the final session of the calendar year (31 December or the last "
                "business day before it), which Japan does not and Hong Kong does not.",
}

EXCHANGES: dict[str, Any] = {
    "cash": {
        "name": "Korea Exchange (KRX): KOSPI, KOSDAQ, KONEX",
        "hours_local": "09:00-15:30 KST",
        "hours_utc": "00:00-06:30 UTC",
        "pre_open_auction": "08:30-09:00 KST (23:30-00:00 UTC)",
        "closing_auction": "15:20-15:30 KST (06:20-06:30 UTC), a ten-minute single-price call",
        "after_hours": "16:00-18:00 KST single-price and block sessions",
        "price_limit": "+/-30% daily on KOSPI and KOSDAQ since 2015-06-15 (previously +/-15%)",
        "circuit_breakers": "KOSPI halts at -8%, -15% and -20%; a 'sidecar' suspends program "
                            "trading orders for one minute on a 5% move in the lead KOSPI200 "
                            "future",
    },
    "derivatives": {
        "name": "KRX Derivatives Market",
        "hours_local": "09:00-15:45 KST for KOSPI200 futures and options",
        "hours_utc": "00:00-06:45 UTC",
        "night_session": "KOSPI200 options also trade on a linked overnight session, roughly "
                         "18:00-05:00 KST, which is where an offshore shock is first priced",
        "expiry_rule": "SECOND THURSDAY of the contract month for KOSPI200 futures and options. "
                       "Not the third Friday (US), not the third Wednesday (Taiwan), not the "
                       "second Friday SQ (Japan).",
        "settlement_price": "the KOSPI200 index computed from the closing prices struck in the "
                            "15:20-15:30 call auction on expiry day -- so any expiry effect is a "
                            "TEN-MINUTE object, and a daily-bar study cannot see it",
        "quadruple_witching": "네 마녀의 날: the second Thursday of March, June, September and "
                              "December, when index futures, index options, single-stock futures "
                              "and single-stock options all expire together",
        "weeklies": "Thursday weekly KOSPI200 options since 2019 and Monday weeklies since 2023 "
                    "-- a liquidity regime change that redistributes expiry pressure away from "
                    "the monthly date and must be conditioned on, not averaged over",
    },
    "short_selling": {
        "rule": "designated-security short selling with an uptick rule; naked shorting prohibited",
        "bans": (("2020-03-16", "2021-05-02", "full ban (pandemic)"),
                 ("2021-05-03", "2023-11-05", "partial: KOSPI200 and KOSDAQ150 constituents only"),
                 ("2023-11-06", "2025-03-30", "full ban"),
                 ("2025-03-31", None, "fully resumed")),
        "why_it_is_here": "these windows are HARD regime boundaries for any KOSPI or KRW "
                          "microstructure study; a pooled estimate across them is an average "
                          "over four different markets",
    },
}

FISCAL_YEAR: dict[str, str] = {
    "government": "31 December (calendar year)",
    "corporate": "31 December for the great majority of listed companies; a March year-end is "
                 "rare in Korea, unlike Japan where it is the norm -- so Korea has NO Japanese "
                 "fiscal-year-end repatriation seasonal and a study that assumes one is "
                 "importing Japan's calendar",
    "budget_cycle": "the government submits the budget to the National Assembly by 2 September "
                    "and it must be passed by 2 December; supplementary budgets (추경) are "
                    "announced ad hoc and are a fiscal-impulse event",
}
#: The framework's field is a bare MM-DD; FISCAL_YEAR above is why it is this one.
FISCAL_YEAR_END = "12-31"


# --------------------------------------------------------------------------- holidays
_KR_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-01": "신정 New Year's Day",
        "2024-02-09": "설날 연휴 Seollal eve",
        "2024-02-12": "설날 대체공휴일 Seollal substitute",
        "2024-03-01": "삼일절 Independence Movement Day",
        "2024-04-10": "제22대 국회의원선거 National Assembly election (temporary public holiday)",
        "2024-05-01": "근로자의 날 Labour Day (market closed)",
        "2024-05-06": "어린이날 대체공휴일 Children's Day substitute",
        "2024-05-15": "부처님오신날 Buddha's Birthday",
        "2024-06-06": "현충일 Memorial Day",
        "2024-08-15": "광복절 Liberation Day",
        "2024-09-16": "추석 연휴 Chuseok eve",
        "2024-09-17": "추석 Chuseok",
        "2024-09-18": "추석 연휴 Chuseok day after",
        "2024-10-03": "개천절 National Foundation Day",
        "2024-10-09": "한글날 Hangeul Day",
        "2024-12-25": "성탄절 Christmas Day",
        "2024-12-31": "연말 휴장일 year-end market closure",
    },
    2025: {
        "2025-01-01": "신정 New Year's Day",
        "2025-01-27": "임시공휴일 temporary public holiday",
        "2025-01-28": "설날 연휴 Seollal eve",
        "2025-01-29": "설날 Seollal (lunar new year day 1)",
        "2025-01-30": "설날 연휴 Seollal day after",
        "2025-03-03": "삼일절 대체공휴일 Independence Movement Day substitute",
        "2025-05-01": "근로자의 날 Labour Day (market closed)",
        "2025-05-05": "어린이날 / 부처님오신날 Children's Day and Buddha's Birthday coincide",
        "2025-05-06": "대체공휴일 substitute holiday",
        "2025-06-03": "제21대 대통령선거 presidential election (temporary public holiday)",
        "2025-06-06": "현충일 Memorial Day",
        "2025-08-15": "광복절 Liberation Day",
        "2025-10-03": "개천절 National Foundation Day",
        "2025-10-06": "추석 Chuseok (15th day of the 8th lunar month)",
        "2025-10-07": "추석 연휴 Chuseok day after",
        "2025-10-08": "추석 연휴 / 임시공휴일 extended Chuseok holiday",
        "2025-10-09": "한글날 Hangeul Day",
        "2025-12-25": "성탄절 Christmas Day",
        "2025-12-31": "연말 휴장일 year-end market closure",
    },
    2026: {
        "2026-01-01": "신정 New Year's Day",
        "2026-02-16": "설날 연휴 Seollal eve",
        "2026-02-17": "설날 Seollal (lunar new year day 1)",
        "2026-02-18": "설날 연휴 Seollal day after",
        "2026-03-02": "삼일절 대체공휴일 substitute (1 March is a Sunday)",
        "2026-05-01": "근로자의 날 Labour Day (market closed)",
        "2026-05-05": "어린이날 Children's Day",
        "2026-05-25": "부처님오신날 대체공휴일 Buddha's Birthday substitute (24 May is a Sunday)",
        "2026-06-03": "전국동시지방선거 local elections (temporary public holiday)",
        "2026-06-06": "현충일 Memorial Day (a Saturday; no substitute applies to this holiday)",
        "2026-08-17": "광복절 대체공휴일 Liberation Day substitute (15 August is a Saturday)",
        "2026-09-24": "추석 연휴 Chuseok eve",
        "2026-09-25": "추석 Chuseok",
        "2026-10-05": "개천절 대체공휴일 substitute (3 October is a Saturday)",
        "2026-10-09": "한글날 Hangeul Day",
        "2026-12-25": "성탄절 Christmas Day",
        "2026-12-31": "연말 휴장일 year-end market closure",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": (
        "Korea's market closures come from three layers and only the first is a weekday rule. "
        "(1) FIXED SOLAR DATES: 1 January, 1 March (삼일절), 1 May (근로자의 날 -- a labour-law "
        "holiday, and the securities market closes for it), 5 May (어린이날), 6 June (현충일), "
        "15 August (광복절), 3 October (개천절), 9 October (한글날), 25 December. "
        "(2) LUNAR DATES, which cannot be derived from a weekday rule and are tabulated here: "
        "설날 is the first day of the first lunar month and the holiday spans the day before, the "
        "day itself and the day after; 추석 is the fifteenth day of the eighth lunar month with "
        "the same three-day span; 부처님오신날 is the eighth day of the fourth lunar month. "
        "(3) SUBSTITUTION (대체공휴일): when 삼일절, 어린이날, 광복절, 개천절, 한글날, 성탄절, "
        "설날 or 추석 falls on a weekend the next non-holiday weekday becomes a holiday. 현충일 "
        "is NOT covered by the substitution rule. On top of these the government declares "
        "임시공휴일 ad hoc -- national election days and bridge days -- which no rule predicts. "
        "Finally KRX closes for the LAST SESSION of the calendar year, which is a market rule "
        "rather than a public holiday."),
    "authority": "관공서의 공휴일에 관한 규정 (the Presidential Decree on public holidays) plus "
                 "KRX's own 휴장일 notice; the calendar for year N is normally settled during "
                 "year N-1",
    "table": _KR_HOLIDAYS,
    "status": {2024: "GAZETTED", 2025: "GAZETTED",
               2026: "DERIVED_FROM_RULE -- the lunar anchors (설날 2026-02-17, 부처님오신날 "
                     "2026-05-24, 추석 2026-09-25) and the substitution law are applied here; "
                     "any 임시공휴일 the government declares later is NOT in this table and can "
                     "only be added when it is announced"},
    "market_effect": (
        "USDKRW keeps trading on the broker's tape through every one of these closures, priced "
        "offshore, while the onshore interbank market and KRX are shut. A Korean holiday is "
        "therefore a LIQUIDITY regime for USDKRW, not an absence of price -- and the reopening "
        "session after 설날 or 추석 is the single most reliable elevated-range window in the "
        "Korean year. That asymmetry is the tradable object; the closure itself is not."),
    "callable": "countries.kr.pack:holidays",
}


def holidays(year: int) -> dict[str, str]:
    """The Korean market-closure table for one year, `{"YYYY-MM-DD": name}`. `{}` if untabulated."""
    return holiday_table(HOLIDAYS_RULE, year)


# --------------------------------------------------------------------------- custom miner
def kr_expiry_dates(year: int) -> dict[str, Any]:
    """KOSPI200 futures and options expiries for a year, by the SECOND-THURSDAY rule.

    This is code rather than a table because the rule is computable and a table would rot. It
    returns every monthly expiry, flags the four quadruple-witching months (네 마녀의 날), and
    marks any expiry that collides with a Korean public holiday -- because when the second
    Thursday is closed the contract settles on the preceding business day, and an event study
    that anchors on the nominal date is then measuring the wrong session.
    """
    rows: list[dict[str, Any]] = []
    table = holidays(year)
    for month in range(1, 13):
        day = nth_weekday(year, month, 3, 2)  # Thursday = 3
        iso = day.isoformat()
        rows.append({
            "date": iso,
            "month": month,
            "quadruple_witching": month in (3, 6, 9, 12),
            "holiday_collision": table.get(iso),
            "settlement": "KOSPI200 from the 15:20-15:30 KST closing call auction "
                          "(06:20-06:30 UTC)",
        })
    return {"year": int(year), "rule": "second Thursday of the contract month",
            "expiries": tuple(rows),
            "unresolved": tuple(r["date"] for r in rows if r["holiday_collision"]),
            "note": "an expiry marked with a holiday_collision settles on the preceding business "
                    "day; this function reports the collision and refuses to guess the roll"}


# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"id": "krx_investor_flows",
     "name": "KRX 투자자별 거래실적 -- daily net buy and sell by investor type",
     "covers": "외국인 (foreign), 기관 (institution, split into pension, insurance, trust, "
               "bank and other), 개인 (retail), per market and per security",
     "frequency": "daily", "lag": "same day, about 18:00 KST (09:00 UTC)",
     "root": "data.krx.co.kr", "licence": "free, public",
     "note": "THE flagship Korean positioning series and the one most Korean studies use. It is "
             "a FLOW, not a stock: a large net buy tells you nothing about the level of foreign "
             "ownership, which is published separately and less often."},
    {"id": "krx_derivatives_positions",
     "name": "KRX 선물옵션 투자자별 미결제약정 -- open interest and net position by investor type",
     "covers": "KOSPI200 futures and options, single-stock futures",
     "frequency": "daily", "lag": "same day after the close",
     "root": "data.krx.co.kr", "licence": "free, public",
     "note": "This is Korea's substitute for a COT report, and it is better: daily rather than "
             "weekly, and by investor type rather than by reporting status."},
    {"id": "kofia_margin_and_deposits",
     "name": "금융투자협회 신용융자잔고, 예탁금, 미수금 -- retail leverage and dry powder",
     "covers": "margin loans outstanding, customer cash at brokers, unsettled receivables",
     "frequency": "daily", "lag": "one business day",
     "root": "freesis.kofia.or.kr", "licence": "free, public",
     "note": "Very few markets publish household leverage DAILY. Korea does, and this is the "
             "series that makes the 동학개미 regime measurable instead of anecdotal."},
    {"id": "bok_ecos",
     "name": "한국은행 경제통계시스템 (ECOS) -- reserves, BOP, resident FX deposits",
     "covers": "외환보유액 monthly, 국제수지 monthly, 거주자외화예금 monthly",
     "frequency": "monthly", "lag": "reserves about the 5th business day; BOP about T+55 days",
     "root": "ecos.bok.or.kr", "licence": "free, public, open API with a key",
     "note": "거주자외화예금 is an underused positioning proxy: it rises when exporters refuse to "
             "convert dollars, which is the corporate sector's own view on the won."},
    {"id": "mofe_bok_fx_transactions",
     "name": "외환당국 순거래 -- official net FX transactions",
     "covers": "the authorities' own spot intervention, netted",
     "frequency": "quarterly", "lag": "about three months",
     "root": "bok.or.kr", "licence": "free, public",
     "note": "The only official intervention series and USELESS AS A SIGNAL at this lag. It is "
             "kept for ex-post attribution and for calibrating what the verbal ladder implied."},
    {"id": "ksd_foreign_bond_holdings",
     "name": "한국예탁결제원 (KSD) foreign holdings of Korean Treasury Bonds",
     "covers": "foreign custody balances in KTBs and MSBs",
     "frequency": "daily and monthly", "lag": "one to two business days",
     "root": "seibro.or.kr", "licence": "free, public",
     "note": "Relevant from 2024 because of Korea's WGBI inclusion path: index-driven inflows are "
             "a SCHEDULED forced flow with a published effective date, which is the rarest kind."},
    {"id": "fss_foreign_investment_trend",
     "name": "금융감독원 외국인 증권투자 동향",
     "covers": "monthly foreign net investment in equities and bonds with nationality breakdown",
     "frequency": "monthly", "lag": "about two weeks",
     "root": "fss.or.kr", "licence": "free, public",
     "note": "The nationality split is the part KRX does not publish, and it separates index "
             "money from strategic money."},
    {"id": "cftc_cot_absent",
     "name": "CFTC Commitments of Traders -- NO KRW CONTRACT EXISTS",
     "covers": "nothing Korean",
     "frequency": "n/a", "lag": "n/a",
     "root": "cftc.gov", "licence": "free, public",
     "note": "DECLARED ABSENT BY NAME. The CFTC reports positioning in JPY, AUD, NZD, CAD, CHF, "
             "GBP, EUR, MXN and BRL -- there is no KRW, CNH, HKD or TWD futures contract, so "
             "there is no COT for any currency in this package. A Korean study that reaches for "
             "'speculative positioning' the way a JPY study does is reaching for a series that "
             "does not exist, and the KRX derivatives file above is the honest substitute."},
)


# --------------------------------------------------------------------------- terminology
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "core": ("환율", "원달러", "원/달러", "외환시장", "서울외환시장", "달러화", "원화",
             "절상", "절하", "고점", "저점"),
    "kr_fx_policy_reaction": ("금통위", "기준금리", "한국은행", "기획재정부", "외환당국",
                              "구두개입", "스무딩 오퍼레이션", "예의주시", "쏠림",
                              "시장 안정화 조치", "외환보유액", "통화정책방향", "의사록",
                              "금리 인하", "금리 인상", "빅스텝"),
    "kr_export_cycle": ("수출", "수입", "무역수지", "관세청", "통관", "일평균 수출액",
                        "이달 1~20일 수출", "반도체 수출", "자동차 수출", "선박 수출",
                        "경상수지", "수출 증가율", "산업통상자원부"),
    "kr_foreign_equity_flow": ("외국인 순매수", "외국인 순매도", "기관 순매수", "프로그램 매매",
                               "차익거래", "비차익거래", "외국인 지분율", "코스피", "코스닥",
                               "코스피200", "배당락", "배당 시즌"),
    "kr_retail_leverage": ("개인투자자", "동학개미", "서학개미", "신용융자잔고", "예탁금",
                           "미수금", "반대매매", "빚투", "증권사 담보", "레버리지"),
    "kr_derivatives_expiry": ("선물 옵션 만기", "만기일", "동시만기", "네 마녀의 날",
                              "쿼드러플 위칭데이", "미결제약정", "베이시스", "콘탱고",
                              "백워데이션", "옵션 만기", "위클리 옵션", "종가 단일가",
                              "동시호가"),
    "kr_ndf_onshore_basis": ("역외", "역외 NDF", "차액결제선물환", "스와프포인트",
                             "스와프 베이시스", "매매기준율", "서울외국환중개", "장 마감 환율",
                             "야간 거래", "역외 세력"),
    "kr_dividend_repatriation": ("배당금", "배당 송금", "외국인 배당", "4월 환전 수요",
                                 "역송금", "결산 배당", "중간 배당"),
    "kr_semis_index_transmission": ("반도체", "메모리 반도체", "디램", "낸드", "고대역폭 메모리",
                                    "반도체 사이클", "파운드리", "삼성전자", "에스케이 하이닉스",
                                    "반도체 장비", "설비투자"),
    "kr_pension_fx": ("국민연금", "국민연금공단", "해외투자", "환헤지", "전략적 환헤지",
                      "외환스와프", "한은 스와프", "기금운용위원회", "목표 비중", "리밸런싱"),
    "kr_risk_proxy_crypto_premium": ("김치 프리미엄", "김프", "역프리미엄", "가상자산",
                                     "투자자 예치금", "위험선호", "국내 프리미엄"),
    "kr_policy_regime_breaks": ("공매도 금지", "공매도 재개", "시장조성자", "서킷브레이커",
                                "사이드카", "비상계엄", "임시공휴일", "거래시간 연장",
                                "외국인 등록제"),
    "kr_session_microstructure": ("장 시작", "장 마감", "시간외 거래", "동시호가", "종가",
                                  "시가", "갭 상승", "갭 하락", "변동성", "거래대금"),
    "kr_energy_import": ("원유 도입", "정유사", "유가", "액화천연가스", "에너지 수입",
                         "교역조건", "수입물가"),
    "kr_shipbuilding_hedge": ("조선사", "수주", "선물환 매도", "헤지 물량", "달러 유입",
                              "인도 대금"),
}


# --------------------------------------------------------------------------- source classes
#: GROUNDS THIS PACK REFUSES TO CRAWL, named rather than silently absent. Kept out of
#: SOURCE_CLASSES' crawlable rows and surfaced in the `source_graph` layer, because the edges a
#: graph deliberately does not traverse are part of the graph.
REFUSED_SOURCES: tuple[dict[str, str], ...] = (
    {"ground": "Korean crypto-exchange order books, venue APIs and venue-native feeds",
     "why": "MT5 universe mandate (2026-08-18): no crypto-exchange ground is ever hunted again. "
            "The kimchi-premium observable is taken from public commentary and regulatory "
            "reporting only, is marked pit_feasible=False, and its executable leg is the "
            "broker's own crypto CFD"},
    {"ground": "paywalled vendor terminal content and its redistribution",
     "why": "licence; the desk holds no redistribution right and reading around a paywall is "
            "not a data-sourcing strategy"},
    {"ground": "DART-driven single-name equity hypothesis mining",
     "why": "two-lane order (2026-09-06): single names are traded on news and never hunted for "
            "statistical hypotheses. DART is read for EVENT context and never mints a cell"},
)

SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    source_class("kr_official", "Bank of Korea, the statistics office, customs and the ministries",
                 layer="official",
                 roots=("bok.or.kr", "ecos.bok.or.kr", "kostat.go.kr", "kosis.kr",
                        "customs.go.kr", "unipass.customs.go.kr", "motie.go.kr", "moef.go.kr",
                        "fsc.go.kr", "fss.or.kr"),
                 queries=("통화정책방향", "금융통화위원회 의사록", "외환보유액", "국제수지",
                          "수출입 실적", "이달 1~20일 수출", "반도체 수출", "구두개입",
                          "외환당국 순거래", "공매도 재개"),
                 languages=("ko", "en"), access_label="OPEN_DATA",
                 credibility="AUTHORITATIVE", predictive_state="UNTESTED",
                 licence="free, public; ECOS and KOSIS publish open APIs with a free key",
                 notes="The BOK Financial Stability Report is where household leverage, the "
                       "onshore-offshore basis and FX market structure are discussed with "
                       "numbers the BOK publishes nowhere else."),
    source_class("kr_institutional", "KRX, KOFIA, KSD and the industry research houses",
                 layer="institutional",
                 roots=("krx.co.kr", "data.krx.co.kr", "open.krx.co.kr", "freesis.kofia.or.kr",
                        "seibro.or.kr", "dart.fss.or.kr", "kcmi.re.kr", "kif.re.kr"),
                 queries=("투자자별 거래실적", "선물옵션 미결제약정", "신용융자잔고", "예탁금",
                          "프로그램 매매", "외국인 지분율", "자본시장연구원 보고서"),
                 languages=("ko", "en"), access_label="OPEN_DATA",
                 credibility="AUTHORITATIVE", predictive_state="UNTESTED",
                 licence="free, public; the KRX Open API needs a free key",
                 notes="KRX's daily investor-type file is Korea's substitute for a COT report "
                       "and it is better: daily rather than weekly, and by investor type rather "
                       "than by reporting status. DART is read for event context only."),
    source_class("kr_academic", "Korean journals, theses and the policy institutes",
                 layer="academic",
                 roots=("kci.go.kr", "riss.kr", "dbpia.co.kr", "kiss.kstudy.com", "kdi.re.kr",
                        "kiep.go.kr", "kiet.re.kr", "papers.ssrn.com"),
                 queries=("코스피200 만기일 효과", "외국인 순매수 환율", "원달러 환율 결정요인",
                          "역외 NDF 시장", "프로그램매매 차익거래", "신용융자 반대매매",
                          "한국은행 워킹페이퍼"),
                 languages=("ko", "en"), access_label="PUBLIC_WITH_TERMS",
                 credibility="RELIABLE", predictive_state="UNTESTED",
                 licence="KCI and RISS abstracts are free; DBpia and KISS full text is LICENSED "
                         "and the desk holds no licence -- abstracts and figures only, never a "
                         "paywall workaround",
                 notes="Korean-language finance journals carry KOSPI200 expiry and "
                       "program-trade studies that have no English equivalent, which is exactly "
                       "why an English-only literature search misses this ground entirely."),
    source_class("kr_practitioner", "Korean systematic-trading platforms, blogs and code",
                 layer="practitioner",
                 roots=("github.com (pykrx, FinanceDataReader, Korean backtesting repos)",
                        "cafe.naver.com systematic-trading groups", "blog.naver.com quant blogs",
                        "tistory.com and velog.io quant blogs", "yesstock.com",
                        "newsystock.com"),
                 queries=("퀀트 투자", "시스템트레이딩", "젠포트 전략", "백테스팅 코드",
                          "키움 오픈API", "자동매매", "알고리즘 트레이딩", "파이썬 주식 분석",
                          "예스트레이더 전략"),
                 languages=("ko",), access_label="PUBLIC_WITH_TERMS",
                 credibility="UNRELIABLE", predictive_state="UNTESTED",
                 licence="per-repository and per-site; respect each licence and never vendor "
                         "code without one",
                 notes="Korea's retail systematic-trading platforms publish STRATEGY LOGIC with "
                       "dated rules, which is a testable mechanism even when the claimed returns "
                       "are not. Credibility is UNRELIABLE and the rows are kept at low weight "
                       "rather than dropped: a rule is still a rule."),
    source_class("kr_retail_ecology", "Korean retail boards and their vernacular",
                 layer="retail_ecology",
                 roots=("finance.naver.com 종목토론실", "gall.dcinside.com (주식 갤러리)",
                        "clien.net (재테크)", "38.co.kr", "paxnet.co.kr",
                        "ppomppu.co.kr (재테크)", "fmkorea.com (주식)"),
                 queries=("동학개미", "빚투", "반대매매 당했다", "만기 주간 외국인",
                          "네 마녀의 날", "김치 프리미엄", "서학개미", "물타기", "존버"),
                 languages=("ko",), access_label="PUBLIC_SOCIAL",
                 credibility="FRINGE", predictive_state="UNTESTED",
                 licence="public web; mined for VERBATIM CLAIMS only, never for personal data, "
                         "respecting robots and rate limits",
                 notes="FRINGE by construction and KEPT AT LOW WEIGHT, never dropped. The value "
                       "is a mechanism stated in the vernacular with a date rule inside it -- "
                       "'만기 주간 외국인이 판다' is a hypothesis. The poster's confidence is "
                       "never scored and a claim that looks false is still a dated claim."),
    source_class("kr_app_ecosystem", "Korean brokerage and investing apps, and their telemetry",
                 layer="app_ecosystem",
                 roots=("mobileindex.com (app MAU and ranking panels)", "wiseapp.co.kr",
                        "play.google.com and apps.apple.com Korean finance category listings "
                        "and review text"),
                 queries=("토스증권", "카카오페이증권", "영웅문", "엠스탁", "증권 앱 순위",
                          "주식 앱 이용자 수", "MTS 점유율"),
                 languages=("ko",), access_label="ACCESS_UNCLEAR",
                 credibility="UNKNOWN", predictive_state="UNTESTED",
                 licence="app-store listing text is public; the MAU panels are VENDOR products "
                         "and the desk holds no subscription",
                 machine_use_allowed=True,
                 notes="REGISTERED AND NOT SCRAPED. The app layer is where Korea's retail "
                       "participation regime became visible in 2020 -- a broker app's user "
                       "growth is the 동학개미 wave before 신용융자잔고 shows it -- but the "
                       "panels are licensed and the store terms restrict machine extraction, so "
                       "the row exists to record that the ground was considered and refused."),
    source_class("kr_media", "The Korean financial press",
                 layer="media",
                 roots=("yna.co.kr", "hankyung.com", "mk.co.kr", "mt.co.kr", "edaily.co.kr",
                        "sedaily.com", "biz.chosun.com"),
                 queries=("환율 급등", "외환당국 구두개입", "쏠림 현상", "예의주시",
                          "반도체 수출 호조", "외국인 매도", "코스피 급락", "금통위 금리"),
                 languages=("ko",), access_label="PUBLIC_WITH_TERMS",
                 credibility="RELIABLE", predictive_state="NARRATIVE_FEATURE",
                 licence="public headlines and article text; respect robots and rate limits",
                 notes="PREDICTIVE_STATE IS NARRATIVE_FEATURE ON PURPOSE. The press does not "
                       "forecast the won, but the verbal-intervention vocabulary appears here "
                       "FIRST and the words themselves are the observable for "
                       "kr_fx_policy_reaction -- a conditioning variable rather than a signal."),
    source_class("kr_archive", "Korean web and news archives, and historical disclosure",
                 layer="archive",
                 roots=("bigkinds.or.kr (한국언론진흥재단 뉴스 아카이브)",
                        "oasis.nl.go.kr (국립중앙도서관 웹아카이브)", "web.archive.org",
                        "krx.co.kr historical 휴장일 and rule notices",
                        "dart.fss.or.kr historical filings"),
                 queries=("공매도 금지 조치", "임시공휴일 지정", "거래시간 연장", "휴장일 안내",
                          "서킷브레이커 발동", "사이드카 발동"),
                 languages=("ko",), access_label="PUBLIC_ARCHIVE",
                 credibility="AUTHORITATIVE", predictive_state="UNTESTED",
                 licence="free for research use; BigKinds requires registration",
                 notes="THE LAYER THAT MAKES AN ERA TABLE CHECKABLE. Every regime break in "
                       "POLICY_ERAS -- the four short-selling windows, the 2024 hours extension, "
                       "each 임시공휴일 -- has a dated primary notice here, and a break date "
                       "taken from memory instead of from the notice is the commonest way an "
                       "era table goes quietly wrong."),
    source_class("kr_physical_economy", "Ports, power, fuel and the physical export machine",
                 layer="physical_economy",
                 roots=("busanpa.com (부산항만공사 container throughput)",
                        "portmis.go.kr (해양수산부 항만물류)", "petronet.co.kr (한국석유공사)",
                        "home.kepco.co.kr (전력통계)", "kosis.kr industrial production series",
                        "unipass.customs.go.kr"),
                 queries=("부산항 물동량", "컨테이너 처리량", "석유 수입량", "전력 사용량",
                          "제조업 가동률", "반도체 재고", "수출 물량 지수"),
                 languages=("ko",), access_label="OPEN_DATA",
                 credibility="AUTHORITATIVE", predictive_state="UNTESTED",
                 licence="free, public",
                 notes="Busan is one of the world's largest container ports and its throughput "
                       "is published monthly and free. This layer is what separates an export "
                       "VALUE surprise (price times volume, and the price is the won) from an "
                       "export VOLUME surprise, which is the one that is about demand."),
    source_class("kr_source_graph", "How new Korean grounds are discovered, and what is refused",
                 layer="source_graph",
                 roots=("kci.go.kr citation graph", "github.com topic and dependency graph for "
                        "Korean market-data packages", "search.naver.com and search.daum.net "
                        "result graphs", "news.naver.com cluster structure"),
                 queries=("퀀트", "계량투자", "증권 데이터 API", "한국 주식 데이터",
                          "환율 데이터 수집", "크롤링 코드"),
                 languages=("ko",), access_label="PUBLIC_WITH_TERMS",
                 credibility="UNKNOWN", predictive_state="UNTESTED",
                 licence="public web; the Naver and Daum search pages restrict automated "
                         "querying and are used at human rates or not at all",
                 notes=f"THE META LAYER. It finds the next ground rather than data, and it also "
                       f"carries what this pack REFUSES to traverse -- the edges a graph does "
                       f"not follow are part of the graph. Refused here: "
                       f"{'; '.join(r['ground'] for r in REFUSED_SOURCES)}. Reasons are in "
                       f"REFUSED_SOURCES, and none of those grounds is named, subscribed or "
                       f"crawled anywhere in this pack."),
)


# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    dataset("kr_customs_exports_1_20",
            source="관세청 Korea Customs Service, 1st-20th of month trade release",
            coverage="exports and imports by value, with a by-product and by-destination split; "
                     "daily-average export value is the headline the market watches",
            frequency="three times a month (1st-10th, 1st-20th, full month)",
            publication_lag_days=1.0,
            revisions="the 1st-20th figure is never revised; it is SUPERSEDED by the full-month "
                      "figure, which is a different series -- storing only the latest value "
                      "destroys the vintage a PIT study needs",
            licence="free, public",
            history_from="2000-01",
            pit_feasible=True,
            assets=("USDKRW", "NAS100", "JPN225", "HK50", "US500"),
            mechanism_families=("export_cycle", "macro_surprise", "semiconductor_cycle",
                                "terms_of_trade"),
            how_to_fetch="customs.go.kr press release on the 21st at about 09:00 KST (00:00 UTC) "
                         "plus the KOSIS open API for history; store the release timestamp with "
                         "the value"),
    dataset("kr_semiconductor_exports",
            source="산업통상자원부 (MOTIE) monthly trade release",
            coverage="semiconductor export value and year-on-year growth, plus the fifteen major "
                     "export categories",
            frequency="monthly",
            publication_lag_days=1.0,
            revisions="minor, into the customs annual revision",
            licence="free, public",
            history_from="2000-01",
            pit_feasible=True,
            assets=("USDKRW", "NAS100", "US500"),
            mechanism_families=("semiconductor_cycle", "export_cycle", "global_tech_demand"),
            how_to_fetch="motie.go.kr release on the 1st of each month at about 09:00 KST "
                         "(00:00 UTC) for the preceding month"),
    dataset("krx_investor_flows",
            source="KRX 투자자별 거래실적",
            coverage="daily net buy and sell by investor type for KOSPI and KOSDAQ",
            frequency="daily",
            publication_lag_days=0.4,
            revisions="none once published",
            licence="free, public",
            history_from="1999-01",
            pit_feasible=True,
            assets=("USDKRW", "HK50", "JPN225"),
            mechanism_families=("foreign_flow", "risk_appetite", "fx_conversion_lag"),
            how_to_fetch="data.krx.co.kr statistics endpoints or the KRX Open API; published "
                         "about 18:00 KST (09:00 UTC)"),
    dataset("krx_derivatives_positions",
            source="KRX 선물옵션 투자자별 미결제약정",
            coverage="open interest and net position by investor type in KOSPI200 futures and "
                     "options",
            frequency="daily",
            publication_lag_days=0.4,
            revisions="none",
            licence="free, public",
            history_from="2004-01",
            pit_feasible=True,
            assets=("USDKRW", "HK50", "JPN225"),
            mechanism_families=("positioning", "expiry", "hedging_flow"),
            how_to_fetch="data.krx.co.kr derivatives statistics; this is the substitute for the "
                         "COT report Korea does not have"),
    dataset("kofia_margin_balance",
            source="금융투자협회 freesis 신용융자잔고, 예탁금, 미수금",
            coverage="retail margin loans, customer deposits at brokers, unsettled receivables",
            frequency="daily",
            publication_lag_days=1.0,
            revisions="none",
            licence="free, public",
            history_from="2005-01",
            pit_feasible=True,
            assets=("USDKRW", "HK50", "US500"),
            mechanism_families=("retail_leverage", "forced_liquidation", "risk_appetite"),
            how_to_fetch="freesis.kofia.or.kr statistical series, one business day in arrears"),
    dataset("bok_policy_decisions",
            source="한국은행 통화정책방향 결정문",
            coverage="the Base Rate decision, the statement text and the vote split",
            frequency="event, eight a year",
            publication_lag_days=0.0,
            revisions="none",
            licence="free, public",
            history_from="1999-05",
            pit_feasible=True,
            assets=("USDKRW", "USDJPY"),
            mechanism_families=("policy_surprise", "rate_differential"),
            how_to_fetch="bok.or.kr press releases at about 09:55-10:00 KST (00:55-01:00 UTC); "
                         "the press conference at 11:10 KST is a SEPARATE event and must be "
                         "stamped separately"),
    dataset("bok_minutes",
            source="한국은행 금융통화위원회 의사록",
            coverage="the minutes, including attributed dissent",
            frequency="event, about two weeks after each decision",
            publication_lag_days=14.0,
            revisions="none",
            licence="free, public",
            history_from="2005-01",
            pit_feasible=True,
            assets=("USDKRW",),
            mechanism_families=("policy_surprise", "text_signal"),
            how_to_fetch="bok.or.kr, released 16:00 KST (07:00 UTC) after the onshore close, "
                         "so the first price reaction is in the OFFSHORE session and not the "
                         "onshore one"),
    dataset("bok_ecos_macro",
            source="한국은행 ECOS",
            coverage="FX reserves, balance of payments, resident FX deposits, terms of trade",
            frequency="monthly and quarterly",
            publication_lag_days=30.0,
            revisions="BOP is revised for several vintages; ECOS does NOT keep vintages, so a "
                      "PIT study must snapshot the series itself from first publication",
            licence="free, public, open API with a free key",
            history_from="1960-01 for some series",
            pit_feasible=False,
            assets=("USDKRW",),
            mechanism_families=("macro_state", "reserve_adequacy"),
            how_to_fetch="ecos.bok.or.kr open API; pit_feasible is FALSE because the archive is "
                         "restated in place and the desk must build its own vintage store"),
    dataset("smbs_mar_fix",
            source="서울외국환중개 매매기준율",
            coverage="the daily USD/KRW Market Average Rate and the cross rates derived from it",
            frequency="daily",
            publication_lag_days=0.0,
            revisions="none",
            licence="free, public",
            history_from="1990-01",
            pit_feasible=True,
            assets=("USDKRW",),
            mechanism_families=("fixing", "ndf_settlement"),
            how_to_fetch="smbs.biz daily rate pages, published about 09:00 KST (00:00 UTC) and "
                         "referencing the PREVIOUS session's trades"),
    dataset("kr_short_sale_regime",
            source="금융위원회 and KRX announcements",
            coverage="the start and end date of every short-selling ban and partial resumption",
            frequency="event",
            publication_lag_days=0.0,
            revisions="none",
            licence="free, public",
            history_from="2008-10",
            pit_feasible=True,
            assets=("HK50", "JPN225", "USDKRW"),
            mechanism_families=("regime_break", "microstructure"),
            how_to_fetch="fsc.go.kr and krx.co.kr notices; this pack keeps the windows in "
                         "EXCHANGES['short_selling']['bans'] as the canonical copy"),
    dataset("kr_ndf_offshore_curve",
            source="offshore KRW NDF quotes (1M, 3M, 6M, 12M)",
            coverage="the offshore forward curve and the implied onshore/offshore basis",
            frequency="intraday",
            publication_lag_days=0.0,
            revisions="n/a",
            licence="VENDOR -- NOT SUBSCRIBED ON THIS DESK",
            history_from="n/a",
            pit_feasible=False,
            assets=("USDKRW",),
            mechanism_families=("onshore_offshore_basis", "carry"),
            how_to_fetch="NOT AVAILABLE. Declared as a GAP by name: the basis domain is "
                         "UNMEASURED until a public or licensed source is found, and the "
                         "second-best proxy is the gap between the broker's own USDKRW tape "
                         "inside and outside onshore hours, which this desk does hold"),
    dataset("kr_kimchi_premium_reported",
            source="public commentary and regulatory reporting (BOK Financial Stability Report, "
                   "금융위 statements, Korean press)",
            coverage="the reported premium of Korean-won crypto prices over international prices, "
                     "as a narrative-level percentage",
            frequency="irregular",
            publication_lag_days=1.0,
            revisions="n/a",
            licence="free, public commentary only",
            history_from="2017-01",
            pit_feasible=False,
            assets=("BTCUSD", "USDKRW"),
            mechanism_families=("risk_appetite", "capital_control_stress", "retail_flow"),
            how_to_fetch="TEXT ONLY. No crypto-exchange venue is subscribed, named or crawled "
                         "(universe mandate 2026-08-18). pit_feasible is FALSE and this dataset "
                         "may seed a hypothesis about USDKRW or BTCUSD but may never itself be "
                         "an input to a PIT-safe cell"),
    dataset("kr_election_and_temporary_holidays",
            source="행정안전부 and KRX 휴장일 notices",
            coverage="임시공휴일 declarations, election days and bridge days",
            frequency="event",
            publication_lag_days=0.0,
            revisions="none",
            licence="free, public",
            history_from="2010-01",
            pit_feasible=True,
            assets=("USDKRW",),
            mechanism_families=("calendar", "liquidity_regime"),
            how_to_fetch="government and KRX notices; NO RULE PREDICTS THESE, which is why they "
                         "are a dataset rather than a branch of the holiday rule"),
)


# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    actor("수출기업 -- Korean exporters (semiconductors, autos, ships, petrochemicals)",
          holds="USD receivables from shipped goods, booked at invoice and converted later",
          forced_to=("convert USD into KRW to pay domestic wages, taxes and suppliers",
                     "hedge a portion of forward order books with FX forwards",
                     "accelerate or delay conversion (네고) within a treasury policy band"),
          when="month end (the last two to three business days), quarter end, and around the "
               "customs release on the 21st; wage and tax dates concentrate the need",
          information=("their own order book weeks before it appears in customs data",
                       "the 매매기준율 and the onshore spot they must transact at",
                       "internal hedge ratios set annually, not tactically"),
          constraints=("board-set hedge ratio bands they may not breach",
                       "an accounting incentive to book conversions inside the quarter",
                       "they are price takers in size and must work orders through banks"),
          instruments=("USDKRW spot", "USDKRW forwards", "FX swaps for funding"),
          counterparties=("Korean commercial banks' FX desks", "the offshore NDF book",
                          "the FX authorities when a move is disorderly"),
          observables=("관세청 1st-20th and full-month export values",
                       "거주자외화예금 (resident FX deposits) -- when it RISES, exporters are "
                       "refusing to convert, which is a held-back supply of dollars",
                       "month-end USDKRW intraday shape"),
          impact="structural KRW demand that is lumpy in time rather than continuous; the "
                 "clustering, not the level, is what is tradable",
          persistence="decades; the invoicing currency and the tax calendar are both stable, and "
                      "this is the most durable actor in the pack",
          falsifier="if month-end and post-21st USDKRW returns are statistically "
                    "indistinguishable from an unconditional sample of the same days of the "
                    "week, and 거주자외화예금 changes carry no information about the following "
                    "month's month-end move, then the conversion flow is not reaching price and "
                    "this actor is a story",
          notes="The semiconductor share of the export book means this actor and the "
                "semiconductor cycle actor move together; their effects must be separated by "
                "conditioning, not assumed distinct."),
    actor("국민연금공단 -- the National Pension Service (NPS)",
          holds="a portfolio well above USD one trillion equivalent, the majority in offshore "
                "assets, against KRW-denominated liabilities",
          forced_to=("rebalance to published strategic asset-allocation targets",
                     "hedge a rule-based share of offshore FX exposure",
                     "fund offshore purchases with dollars it must obtain somewhere"),
          when="continuously for purchases; hedging decisions at 기금운용위원회 meetings and at "
               "policy review points; rebalancing clusters at month and quarter end",
          information=("its own future allocation path, published in advance as a target",
                       "its own hedge ratio policy and the trigger levels inside it"),
          constraints=("a published SAA the fund is accountable for",
                       "a strategic hedge ratio with a stated ceiling that rises when the won "
                       "weakens past internal thresholds",
                       "political scrutiny of anything that looks like FX policy"),
          instruments=("USDKRW spot", "FX forwards", "the BOK FX swap facility"),
          counterparties=("한국은행 through the FX swap line", "global custodian banks",
                          "the onshore interbank market"),
          observables=("the fund's published AUM and allocation reports",
                       "announcements of swap-line size, renewal and drawdown",
                       "기금운용위원회 decisions on hedge ratio"),
          impact="the single largest structural KRW-selling force in the economy when it buys "
                 "offshore unhedged, and a KRW-buying force when it raises the hedge ratio; the "
                 "BOK swap exists to keep the largest episodes off the spot market entirely",
          persistence="structural and growing while the fund accumulates; it will invert when "
                      "the fund turns net decumulator, which is a demographic certainty with an "
                      "uncertain date",
          falsifier="if USDKRW shows no measurable response to announced changes in the hedge "
                    "ratio or to swap-line drawdowns, in a window where nothing else changed, "
                    "then this flow is fully anticipated and carries no tradable information",
          notes="This is the clearest published-trigger forced flow in East Asia and the "
                "cleanest test of whether an anticipated flow still moves price."),
    actor("외환당국 -- the FX authorities (한국은행 and 기획재정부 acting jointly)",
          holds="official FX reserves in the low USD 400bn range, plus the NPS swap facility",
          forced_to=("respond to disorderly one-sided moves under a stated smoothing mandate",
                     "defend a reputation for not targeting a level",
                     "manage reserve adequacy optics against IMF metrics"),
          when="when the move is fast rather than when the level is high; historically clustered "
               "in the last hour of the onshore session and at the open after an offshore gap",
          information=("real-time interbank order flow the market cannot see",
                       "the size and timing of the NPS's hedging need",
                       "their own intended reaction function"),
          constraints=("the US Treasury FX report's monitoring list, which makes persistent "
                       "one-way intervention costly",
                       "reserve adequacy and the political cost of spending reserves",
                       "a mandate to smooth, not to target"),
          instruments=("USDKRW spot intervention", "FX swaps", "the NPS swap line",
                       "verbal intervention"),
          counterparties=("Korean banks' FX desks", "the offshore NDF book",
                          "the National Pension Service"),
          observables=("the verbal ladder: 예의주시 -> 쏠림 -> 구두개입",
                       "외환보유액 month-on-month change",
                       "외환당국 순거래, quarterly and three months late"),
          impact="a reflecting pressure against fast moves; it changes the SHAPE of the "
                 "distribution (fewer fast tails, more slow drift) rather than its mean",
          persistence="the mandate has been stable for two decades, but the tools rotate -- the "
                      "NPS swap is a 2022 innovation that did not exist in the prior sample",
          falsifier="if USDKRW realised volatility and tail frequency after a 구두개입 headline "
                    "are indistinguishable from matched days without one, the verbal ladder is "
                    "decoration and only the transactions matter -- and those are unobservable "
                    "in real time, which would make this domain UNMEASURED rather than negative",
          notes="The observable is the WORDS. That is unusual and it is why the media source "
                "class is load-bearing for this pack rather than colour."),
    actor("외국인 주식투자자 -- foreign equity investors at KRX",
          holds="roughly a third of KOSPI market capitalisation, concentrated in the largest "
                "index names",
          forced_to=("track benchmark indices through rebalances and reclassifications",
                     "convert KRW proceeds back to USD on redemption",
                     "hedge or not hedge according to a mandate set outside Korea"),
          when="index review effective dates, month end, and continuously with global risk "
               "appetite; dividend repatriation in April and May",
          information=("global index-provider consultations and effective dates, published "
                       "weeks ahead",
                       "their own redemption queues"),
          constraints=("benchmark tracking error limits",
                       "the foreign investor registration regime and custody requirements",
                       "the short-selling ban windows, which removed one leg of their toolkit "
                       "for years at a time"),
          instruments=("KOSPI and KOSDAQ cash equities", "KOSPI200 futures",
                       "USDKRW spot and forwards for the FX leg"),
          counterparties=("Korean securities houses", "custodian banks",
                          "domestic institutions taking the other side"),
          observables=("KRX 외국인 순매수, daily and free",
                       "외국인 지분율", "index-provider review calendars"),
          impact="the KRX net-buy print LEADS the FX conversion by one to two sessions because "
                 "equity settles T+2 and the FX leg follows -- which is the mechanism, and it is "
                 "a lag, not a coincidence",
          persistence="structural while Korea sits in global benchmarks; MSCI developed-market "
                      "reclassification would be a one-off regime change of the first order",
          falsifier="if the KRX foreign net-buy series has no predictive relation to USDKRW at "
                    "any lag from zero to five sessions, after controlling for the contemporaneous "
                    "move in a regional risk proxy, the settlement-lag mechanism is absent",
          notes="Not to be confused with the FX flow itself: the print is the equity leg and the "
                "conversion is a separate, later, unobserved event."),
    actor("개인투자자 / 동학개미 -- the leveraged Korean retail investor",
          holds="direct equity positions funded partly by 신용융자 margin loans, plus a large "
                "and growing offshore book (서학개미) concentrated in US technology",
          forced_to=("meet margin calls within a short window or be sold out (반대매매)",
                     "buy dollars to fund offshore purchases"),
          when="반대매매 executes at the open after a threshold breach, which makes the first "
               "thirty minutes of the session the forced window",
          information=("nothing the market does not have; this actor is INFORMATION-POOR and "
                       "constraint-rich, which is exactly what makes it predictable"),
          constraints=("broker maintenance-margin thresholds",
                       "a two-day settlement clock on the forced sale",
                       "no ability to hedge the FX leg of the offshore book in size"),
          instruments=("KOSPI and KOSDAQ cash equities", "US-listed equities and ETFs",
                       "USDKRW conversion at retail spreads"),
          counterparties=("Korean securities houses as lenders and as forced sellers",
                          "the market at large"),
          observables=("신용융자잔고, daily", "예탁금, daily", "미수금 and 반대매매 volumes",
                       "retail net buy in KRX 투자자별 거래실적"),
          impact="amplifies drawdowns through mechanical liquidation and adds a persistent "
                 "structural USD bid through the offshore book; both are one-directional under "
                 "stress, which is the definition of a forced flow",
          persistence="the 동학개미 regime began in 2020 and its durability is genuinely open; "
                      "the margin-loan series is the thing to watch for its end",
          falsifier="if KOSPI returns conditional on a large fall in 신용융자잔고 are "
                    "indistinguishable from unconditional returns after controlling for the "
                    "contemporaneous index move, mechanical liquidation is not reaching price",
          notes="The 서학개미 leg makes this actor a source of USDKRW demand that is "
                "UNCORRELATED with the export cycle, which is why it deserves its own domain."),
    actor("증권사 -- Korean securities houses and their ELS hedging desks",
          holds="issued equity-linked securities (ELS and DLS) referencing KOSPI200, HSCEI and "
                "global indices, hedged dynamically",
          forced_to=("delta-hedge a short-volatility, path-dependent book",
                     "buy back hedges near knock-in barriers, which is convex and "
                     "self-reinforcing",
                     "fund the USD leg of index-linked hedges"),
          when="continuously, with violent concentration when an underlying approaches a "
               "knock-in barrier and at autocall observation dates",
          information=("their own aggregate barrier map, which the market can only infer",
                       "issuance volumes, which are reported"),
          constraints=("regulatory capital and counterparty limits on hedging books",
                       "supervisory limits on ELS issuance introduced after past episodes",
                       "the hedge must be executed in liquid instruments"),
          instruments=("KOSPI200 futures and options", "HSCEI-linked hedges",
                       "USDKRW swaps for funding"),
          counterparties=("global investment banks as hedge counterparties",
                          "the KRX derivatives market", "retail buyers of the notes"),
          observables=("ELS issuance and outstanding balances, published by 예탁결제원",
                       "KOSPI200 and HSCEI option skew",
                       "KRX derivatives open interest by investor type"),
          impact="a hidden gamma position that dampens ranges while barriers are far and "
                 "amplifies moves when they are near; the HSCEI episodes of 2015-16 and 2024 "
                 "are the documented cases and both transmitted between Hong Kong and Seoul",
          persistence="issuance is regulated and cyclical; the mechanism recurs whenever "
                      "outstanding notional rebuilds",
          falsifier="if KOSPI200 realised volatility shows no relation to outstanding ELS "
                    "notional or to proximity to the modal knock-in level, the hedging flow is "
                    "too small or too diversified to reach price",
          notes="This is the one actor that links the Korean and Hong Kong packs MECHANICALLY "
                "rather than through correlation, because the notes reference HSCEI directly."),
    actor("역외 NDF 참가자 -- the offshore KRW NDF book",
          holds="non-deliverable forward positions in KRW, settled in USD against the 매매기준율",
          forced_to=("mark and settle against a fixing struck in Seoul",
                     "square positions before the fixing date",
                     "trade in the London and New York afternoons when Seoul is shut"),
          when="the offshore session, roughly 07:00-21:00 UTC; concentrated around the fixing "
               "date and at month end",
          information=("global risk sentiment and dollar funding conditions hours before Seoul "
                       "reopens"),
          constraints=("no access to onshore deliverable KRW",
                       "settlement against a fixing they cannot themselves transact at",
                       "counterparty credit limits offshore"),
          instruments=("KRW NDF outright and forwards", "NDF options", "proxy hedges in USDJPY "
                       "and USDCNH when KRW liquidity is thin"),
          counterparties=("global banks", "Korean banks' offshore branches",
                          "macro funds expressing an Asia view"),
          observables=("the gap between the broker's USDKRW tape outside onshore hours and the "
                       "next onshore open",
                       "NDF-implied points where a public quote exists",
                       "the size of the open-to-previous-close gap, which this desk CAN measure "
                       "from its own tape"),
          impact="Korea's overnight gap is manufactured offshore. The onshore open at 00:00 UTC "
                 "is a price-discovery event that imports a decision made while Seoul slept",
          persistence="structural while the won is non-deliverable; the 2024 market-hours "
                      "extension deliberately shrank the window and therefore the mechanism",
          falsifier="if the USDKRW open-to-previous-close gap is not predictable from the "
                    "offshore session's own move in USDJPY, USDCNH and a dollar index, then "
                    "offshore price formation carries no incremental information",
          notes="The 2024-07-01 hours extension is the natural experiment: the same mechanism "
                "with a shorter window should produce a smaller gap, and that is testable."),
    actor("정유 및 에너지 수입기업 -- Korean refiners and energy importers",
          holds="continuous USD-denominated crude, LNG and coal purchase obligations for an "
                "economy with almost no domestic hydrocarbon production",
          forced_to=("buy dollars every month regardless of the exchange rate",
                     "hedge cargo pricing windows",
                     "pass through or absorb costs under regulated domestic pricing"),
          when="cargo payment dates spread through the month; hedging at pricing-window fixes",
          information=("their own forward purchase schedule",
                       "refining margins before they are published"),
          constraints=("energy security obligations that make volume inelastic to price",
                       "domestic price regulation limiting pass-through",
                       "storage capacity"),
          instruments=("USDKRW spot and forwards", "crude and product swaps"),
          counterparties=("international oil majors and traders", "Korean banks"),
          observables=("관세청 import values by commodity",
                       "교역조건 (terms of trade), published monthly",
                       "the energy share of the import bill"),
          impact="a persistent structural USD bid whose SIZE is set by the oil price, so an oil "
                 "shock is a KRW shock through the current account with a one-to-two-month lag",
          persistence="structural; it weakens only as the energy mix shifts, which is a "
                      "decade-scale process",
          falsifier="if USDKRW monthly returns show no relation to the prior month's change in "
                    "the energy import bill, after controlling for the contemporaneous dollar "
                    "and the oil price itself, the terms-of-trade channel is not operating",
          notes="This is the actor that makes XTIUSD a legitimate control instrument in a "
                "Korean study rather than an unrelated market."),
    actor("보험사 및 자산운용사 -- Korean insurers and asset managers with offshore bonds",
          holds="large offshore fixed-income books held against long-dated KRW liabilities",
          forced_to=("roll short-dated FX hedges against long-dated assets, permanently",
                     "meet solvency capital rules that penalise unhedged currency risk",
                     "buy or sell the hedge at the roll whatever the basis costs"),
          when="hedge rolls cluster at month end and quarter end; solvency reporting dates "
               "concentrate the need",
          information=("their own hedge maturity ladder"),
          constraints=("K-ICS solvency capital requirements",
                       "duration matching against long liabilities",
                       "the cross-currency basis, which they pay and cannot avoid"),
          instruments=("FX swaps and forwards", "cross-currency basis swaps",
                       "offshore government and credit bonds"),
          counterparties=("Korean and global bank swap desks", "offshore bond markets"),
          observables=("the KRW cross-currency basis where a public quote exists",
                       "거주자외화예금", "insurers' offshore investment balances from FSS data"),
          impact="a permanent bid for dollars at the short end of the swap curve, which is why "
                 "the KRW basis can stay negative for years; the roll clustering is the "
                 "tradable part",
          persistence="structural while domestic long-dated assets are scarce relative to "
                      "liabilities",
          falsifier="if month-end and quarter-end USDKRW swap-point behaviour is not "
                    "distinguishable from mid-month behaviour, the roll clustering is not "
                    "reaching price",
          notes="The basis leg is UNMEASURED on this desk today: no public KRW basis series is "
                "subscribed, and that gap is recorded in the dataset catalogue rather than "
                "papered over."),
    actor("조선사 -- Korean shipbuilders",
          holds="multi-year USD-denominated order books with staged payment milestones",
          forced_to=("sell dollars forward against contracted future receipts, in size, at "
                     "order signature",
                     "unwind or roll those forwards if a contract slips"),
          when="at order announcement and at each construction milestone; the order cycle is "
               "lumpy and publicly announced",
          information=("their own order pipeline before announcement"),
          constraints=("hedge accounting rules that favour hedging at contract signature",
                       "bank credit lines limiting forward size",
                       "a multi-year gap between hedge and delivery"),
          instruments=("USDKRW forwards, typically one to three years",
                       "FX swaps to manage the roll"),
          counterparties=("Korean banks, which then hedge in the spot and swap markets",
                          "the offshore NDF book"),
          observables=("monthly order intake published by industry bodies and the companies",
                       "Clarksons-style newbuild order data, licensed",
                       "관세청 ship export values"),
          impact="a lumpy, ANNOUNCED forward sale of dollars: the announcement is public and the "
                 "hedge follows, which makes this one of the few forced flows with a public "
                 "trigger and a measurable lag",
          persistence="cyclical with the shipping cycle; the mechanism is stable but its size "
                      "swings by an order of magnitude across the cycle",
          falsifier="if USDKRW does not fall measurably in the days after a large order "
                    "announcement, relative to matched days, the hedge either precedes the "
                    "announcement or is too small to see -- and the first of those is testable "
                    "separately",
          notes="A rare case where the forced flow has a DATED public trigger, which makes it a "
                "better event study than most FX mechanisms."),
    actor("반도체 복합체 -- the Korean semiconductor complex (OBSERVABLE, NEVER TRADED)",
          holds="global memory production capacity and the capital expenditure cycle behind it",
          forced_to=("invest through the cycle because fab capacity takes years",
                     "import equipment and materials, mostly in dollars",
                     "repatriate or retain offshore earnings"),
          when="capex decisions at annual and quarterly planning; export shipments continuously; "
               "the cycle turns on inventory, not on quarters",
          information=("their own order books and inventory positions months before the market "
                       "sees them in customs data"),
          constraints=("fab lead times measured in years",
                       "export controls and equipment licensing",
                       "a memory price cycle they influence but do not set"),
          instruments=("NONE ON THIS DESK. This actor is an OBSERVABLE only: the two-lane order "
                       "(2026-09-06) forbids hunting single-name equities statistically, so the "
                       "complex is read through 반도체 수출 and expressed in USDKRW and NAS100"),
          counterparties=("global technology buyers", "equipment suppliers",
                          "the Korean export statistics that count them"),
          observables=("관세청 semiconductor export value and daily average",
                       "memory contract and spot price commentary",
                       "MOTIE monthly export composition"),
          impact="the dominant single driver of Korea's terms of trade and therefore of the won; "
                 "it is also the cleanest public read on global technology demand, which is why "
                 "the transmission target is NAS100 rather than any Korean instrument",
          persistence="the cycle itself is durable; its amplitude and period have both changed "
                      "with the AI capex wave and must be re-estimated, not assumed",
          falsifier="if semiconductor export surprises carry no information for USDKRW or NAS100 "
                    "at any horizon out to one month, after controlling for the contemporaneous "
                    "dollar and global equity move, the transmission is absent",
          notes="NAMED AS AN ACTOR PRECISELY SO THAT THE BOUNDARY IS EXPLICIT: the mechanism is "
                "real and large, and the instrument list is empty on purpose."),
    actor("KOSPI200 옵션 마켓메이커 -- index option market makers and prop desks",
          holds="short-dated KOSPI200 option inventory, hedged in the futures",
          forced_to=("delta-hedge into the 15:20-15:30 closing auction on expiry day",
                     "roll or close positions before the second Thursday",
                     "quote continuously under market-making obligations"),
          when="expiry week, and specifically the closing auction of the second Thursday; "
               "weekly expiries redistribute this across Mondays and Thursdays",
          information=("their own inventory and the order book they quote into",
                       "the aggregate open-interest picture, published daily by KRX"),
          constraints=("market-making quoting obligations",
                       "position and margin limits",
                       "settlement against the auction price, which they partly set"),
          instruments=("KOSPI200 options and futures", "single-stock futures"),
          counterparties=("retail option buyers, historically an unusually large share of this "
                          "market", "institutional hedgers", "arbitrage desks"),
          observables=("KRX open interest by strike and investor type, daily",
                       "the futures basis into expiry",
                       "closing-auction volume on expiry days versus ordinary days"),
          impact="pinning and range compression into expiry, then a release; the effect lives in "
                 "the ten-minute auction, so it is invisible at daily frequency and that is the "
                 "main reason it may still be there",
          persistence="the retail share of the Korean options market has fallen since the "
                      "post-2011 regulatory tightening, so the amplitude is regime-dependent",
          falsifier="if closing-auction volume and the futures basis on second Thursdays are "
                    "indistinguishable from first and third Thursdays of the same months, there "
                    "is no expiry mechanism to trade",
          notes="Korea has no index CFD on this broker, so any finding here must be expressed "
                "through JPN225, HK50 or USDKRW -- and the pack says so rather than pretending "
                "the finding is directly tradable."),
    actor("은행 외화자금부 -- Korean banks' FX funding desks",
          holds="the maturity mismatch between dollar assets and won funding for the whole "
                "banking system",
          forced_to=("roll short-dated dollar funding continuously",
                     "meet regulatory FX liquidity and loan-to-deposit ratios",
                     "intermediate every flow in this pack"),
          when="daily at the swap roll; regulatory ratio measurement dates concentrate it; "
               "year-end funding is structurally the tightest week",
          information=("aggregate client flow across exporters, insurers and the NPS",
                       "the true state of onshore dollar funding before it is visible in prices"),
          constraints=("FX liquidity coverage ratios and FX derivative position limits",
                       "counterparty credit lines offshore",
                       "the cross-currency basis they must pay"),
          instruments=("FX swaps", "USDKRW spot", "offshore dollar funding"),
          counterparties=("global banks", "the BOK's own swap facilities in stress",
                          "every other actor in this pack"),
          observables=("the swap point curve where a public quote exists",
                       "외환보유액 and BOK facility announcements",
                       "year-end and quarter-end spot and swap behaviour"),
          impact="the transmission channel through which every other forced flow reaches price; "
                 "when funding is tight, the same flow moves the spot further",
          persistence="structural; the regulatory framework has tightened since 2010 and the "
                      "amplitude of funding squeezes has fallen with it",
          falsifier="if USDKRW volatility conditional on quarter-end and year-end dates is "
                    "indistinguishable from mid-quarter dates, funding pressure is no longer "
                    "reaching spot and this actor is inert for trading purposes",
          notes="The public swap-point series is the missing input; it is recorded as a GAP in "
                "kr_ndf_offshore_curve rather than substituted with a guess."),
    actor("국내 리테일 위험선호 -- domestic retail risk appetite (the kimchi-premium actor)",
          holds="won-denominated speculative positions whose price premium over international "
                "levels is publicly commented on",
          forced_to=("transact only in won, because capital controls make cross-venue arbitrage "
                     "slow and legally constrained -- which is WHY a premium can persist at all"),
          when="episodic; it widens in retail manias and inverts in liquidations",
          information=("nothing informational; this actor is a sentiment gauge, not a forecaster"),
          constraints=("capital-account restrictions on moving won abroad",
                       "domestic real-name account rules",
                       "no ability to arbitrage the premium away at size"),
          instruments=("NONE ON THIS DESK. The observable is read from PUBLIC COMMENTARY only; "
                       "no crypto-exchange venue is subscribed, named or crawled (universe "
                       "mandate 2026-08-18). The executable leg is the broker's own BTCUSD CFD "
                       "and USDKRW"),
          counterparties=("other domestic retail participants"),
          observables=("the premium as REPORTED in the BOK Financial Stability Report, "
                       "regulatory statements and the Korean press",
                       "신용융자잔고 and 예탁금, which move with the same risk appetite"),
          impact="a proxy for domestic risk appetite and for the tightness of the capital "
                 "account; a wide premium has historically coincided with retail leverage highs "
                 "and with won weakness, and the CAUSAL direction is exactly what is untested",
          persistence="episodic and regulation-dependent; it has been compressed by rule changes "
                      "more than once and may not survive the next",
          falsifier="if reported premium episodes carry no information about subsequent USDKRW "
                    "or BTCUSD returns beyond what 신용융자잔고 already carries, this actor is "
                    "redundant with the retail-leverage actor and should be retired into it",
          notes="Carried at pit_feasible=False and hypothesis-only. The refusal is the point: a "
                "real observable whose only clean data source is off-limits is UNMEASURED, and "
                "that is a verdict rather than an excuse."),
)


# --------------------------------------------------------------------------- domains
_DEFAULT_CONTROLS: tuple[str, ...] = (
    "the same statistic on EURUSD and GBPUSD, where no Korean mechanism can operate",
    "the same statistic on matched days of the week and days of the month, to separate a Korean "
    "effect from a calendar artefact",
    "the same statistic inside each policy era of POLICY_ERAS, never pooled across them",
)

def _controls(*extra: str) -> tuple[str, ...]:
    """The three standing controls every Korean domain runs, plus the domain's own."""
    return (*_DEFAULT_CONTROLS, *extra)


DOMAINS: tuple[dict[str, Any], ...] = (
    domain("kr_fx_policy_reaction", "The FX authorities' reaction function and the verbal ladder",
           objects=("BOK decisions and statement text", "구두개입 headlines and their wording",
                    "외환보유액 monthly change", "the quarterly 순거래 disclosure"),
           conditions=("distance of USDKRW from recent multi-year highs",
                       "realised volatility and the speed of the move rather than its level",
                       "whether the US Treasury monitoring list currently names Korea"),
           instruments=("USDKRW", "USDJPY"),
           controls=_controls(
               "the same headline vocabulary applied to USDJPY around MOF Japan language, to "
               "test whether 'verbal intervention moves spot' is a Korean fact or a generic one",
               "placebo headlines: routine BOK commentary containing none of the ladder words")),
    domain("kr_export_cycle", "The customs print and the terms of trade",
           objects=("1st-10th, 1st-20th and full-month export and import values",
                    "daily-average export value, the market's preferred normalisation",
                    "semiconductor, auto and ship export components", "교역조건"),
           conditions=("working-day count in the window, which mechanically drives the headline",
                       "lunar new year timing, which shifts working days between January and "
                       "February every year",
                       "the level of the oil price for the import leg"),
           instruments=("USDKRW", "NAS100", "JPN225", "XTIUSD"),
           controls=_controls(
               "a working-day-adjusted version of the same statistic, because an unadjusted "
               "Korean trade series is largely a calendar",
               "the same statistic on Taiwan's export orders, which lead the same global cycle: "
               "if both react identically, the effect is global technology demand and not Korea")),
    domain("kr_foreign_equity_flow", "Foreign equity flow and its settlement-lagged FX leg",
           objects=("KRX 외국인 순매수 daily", "index review effective dates",
                    "외국인 지분율", "program and arbitrage trade splits"),
           conditions=("short-selling regime in force on the date",
                       "whether the flow is index-driven or discretionary",
                       "global risk appetite measured outside Korea"),
           instruments=("USDKRW", "HK50", "JPN225"),
           controls=_controls(
               "the same statistic with the FX leg lagged zero, one and two sessions: the "
               "settlement mechanism predicts a specific lag and a flat lag profile refutes it",
               "the same flow-to-FX relation in Taiwan, where the settlement convention differs")),
    domain("kr_retail_leverage", "Household leverage, forced liquidation and the offshore book",
           objects=("신용융자잔고", "예탁금", "미수금 and 반대매매",
                    "retail net buy by market", "the 서학개미 offshore flow"),
           conditions=("the level of leverage relative to its own trailing distribution",
                       "whether the index is within a drawdown deep enough to trigger calls",
                       "the first thirty minutes of the session, when forced sales execute"),
           instruments=("USDKRW", "HK50", "US500", "NAS100"),
           controls=_controls(
               "the same statistic conditioned on index drawdown ALONE, with leverage excluded: "
               "if drawdown explains it, the leverage series adds nothing",
               "the same statistic in the second half of the session, where no forced sale is "
               "executing")),
    domain("kr_derivatives_expiry", "The second Thursday, the closing auction and the witches",
           objects=("KOSPI200 futures and option expiries", "the 15:20-15:30 auction",
                    "open interest by investor type into expiry", "the futures basis"),
           conditions=("quadruple-witching months versus ordinary months",
                       "whether a weekly expiry falls in the same week",
                       "open interest concentration at nearby strikes"),
           instruments=("HK50", "JPN225", "USDKRW"),
           controls=_controls(
               "the FIRST and THIRD Thursday of the same month, which is the only honest "
               "placebo for a second-Thursday effect",
               "the same statistic on JPN225 and HK50 on Korean expiry days, to separate a "
               "Korean settlement effect from a regional session effect",
               "Japanese SQ Fridays and Taiwanese third Wednesdays as foreign-expiry placebos")),
    domain("kr_ndf_onshore_basis", "Offshore price formation and the 00:00 UTC open",
           objects=("the USDKRW open-to-previous-close gap on the broker tape",
                    "the offshore session's own path", "the 매매기준율 against the onshore open"),
           conditions=("before and after the 2024-07-01 hours extension, never pooled",
                       "whether a BOK decision or minutes fell in the offshore window",
                       "offshore session volatility in USDJPY and USDCNH"),
           instruments=("USDKRW", "USDJPY"),
           controls=_controls(
               "the same gap statistic on USDSGD, which trades the same session with no Korean "
               "mechanism",
               "the gap predicted by USDJPY and USDCNH alone: the Korea-specific residual is the "
               "only thing this domain may claim")),
    domain("kr_dividend_repatriation", "The April and May dividend conversion window",
           objects=("foreign-held dividend amounts", "record and payment dates",
                    "USDKRW behaviour in the last week of April"),
           conditions=("the size of the aggregate dividend pool that year",
                       "whether payment dates cluster or spread",
                       "the prevailing FX level, which affects hedging choices"),
           instruments=("USDKRW",),
           controls=_controls(
               "the same statistic in the last week of every OTHER month of the same year",
               "the same statistic in April on USDSGD and USDJPY, neither of which has a Korean "
               "dividend calendar")),
    domain("kr_semis_index_transmission", "The semiconductor cycle as an index and FX object",
           objects=("반도체 수출 value and growth", "memory price commentary",
                    "the technology share of the export book"),
           conditions=("the phase of the memory cycle", "the global technology equity regime",
                       "export-control news flow"),
           instruments=("NAS100", "US500", "USDKRW", "JPN225"),
           controls=_controls(
               "the same statistic on Taiwan's export orders: two independent reads on one global "
               "cycle, and a finding present in only one of them is probably about that country",
               "NAS100 conditioned on US technology earnings dates alone, to test whether the "
               "Korean series adds anything beyond the US calendar"),
           notes="NO SINGLE NAME MAY ENTER THIS DOMAIN AS AN INSTRUMENT. The two-lane order is "
                 "structural here, not incidental: the mechanism is a national export series and "
                 "the expression is an index."),
    domain("kr_pension_fx", "Pension hedging, the BOK swap line and the announced flow",
           objects=("NPS hedge-ratio decisions", "swap-line size, renewal and drawdown",
                    "the fund's published allocation path"),
           conditions=("whether the announced trigger level has been breached",
                       "month and quarter end",
                       "whether the swap facility is available and undrawn"),
           instruments=("USDKRW",),
           controls=_controls(
               "the same statistic on the announcement date versus the effective date: an "
               "anticipated flow should move price on ANNOUNCEMENT, and if it moves on neither "
               "the flow is fully absorbed",
               "matched month-ends in years before the swap line existed (pre-2022)")),
    domain("kr_risk_proxy_crypto_premium", "The kimchi premium as a risk and capital-account gauge",
           objects=("the premium as reported in public commentary and regulatory text",
                    "its co-movement with 신용융자잔고 and 예탁금"),
           conditions=("whether retail leverage is simultaneously elevated",
                       "regulatory changes to account and transfer rules",
                       "the direction of the premium: a discount is a different regime"),
           instruments=("BTCUSD", "USDKRW"),
           controls=_controls(
               "the same statistic with 신용융자잔고 included first: if the premium adds no "
               "incremental information, this domain retires into kr_retail_leverage",
               "the same statistic on BTCUSD alone, with no Korean conditioning at all"),
           notes="PIT-BLOCKED BY DESIGN. No crypto-exchange venue is subscribed, named or "
                 "crawled. This domain may seed a hypothesis and may never produce a PIT-safe "
                 "cell from the premium series itself -- UNMEASURED is the honest verdict and it "
                 "is recorded rather than worked around."),
    domain("kr_policy_regime_breaks", "The breaks that make a pooled Korean estimate meaningless",
           objects=("the four short-selling windows", "the 2024-07-01 hours extension",
                    "the 2024-12-03 martial-law episode and its reversal",
                    "weekly option introductions in 2019 and 2023"),
           conditions=("which regime the date falls in",
                       "whether the break was announced or a surprise"),
           instruments=("USDKRW", "HK50", "JPN225"),
           controls=_controls(
               "the same statistic estimated separately either side of each break, with a Chow "
               "test reported rather than a pooled mean",
               "the same break dates applied to a market with no Korean exposure, as a placebo")),
    domain("kr_session_microstructure", "The Korean trading day as a shape",
           objects=("the 00:00 UTC open", "the 06:20-06:30 UTC closing auction",
                    "the 06:45 UTC derivatives close", "the 17:00 UTC extended close since 2024"),
           conditions=("onshore hours versus offshore hours",
                       "whether a Korean holiday closes the onshore market while the broker tape "
                       "keeps quoting",
                       "the season, because KST never shifts and the broker's server clock does"),
           instruments=("USDKRW",),
           controls=_controls(
               "the same intraday shape on USDSGD and USDJPY, which share the session but not "
               "the mechanism",
               "Korean holidays versus ordinary days: if the intraday shape survives a day when "
               "Seoul is shut, it was never Korean")),
    domain("kr_energy_import", "Terms of trade through the energy bill",
           objects=("energy import values", "교역조건", "refining margins",
                    "the energy share of imports"),
           conditions=("the oil price level and its rate of change",
                       "the won level, which changes the domestic cost",
                       "seasonal heating and cooling demand"),
           instruments=("USDKRW", "XTIUSD", "XNGUSD"),
           controls=_controls(
               "the same statistic on a net energy EXPORTER's currency, where the sign should "
               "invert; a same-sign result means the effect is the dollar, not the terms of trade",
               "the oil price alone, with no Korean conditioning")),
    domain("kr_shipbuilding_hedge", "Announced order books and the forward sale that follows",
           objects=("shipbuilding order announcements and their dollar value",
                    "monthly order intake", "관세청 ship export values"),
           conditions=("order size relative to the recent distribution",
                       "the phase of the shipping cycle",
                       "whether the order was pre-announced or a surprise"),
           instruments=("USDKRW",),
           controls=_controls(
               "the same event window shifted forward by one month, as a placebo",
               "auto and petrochemical export announcements of similar size, where no multi-year "
               "forward hedge convention exists")),
)


# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("kr_semis_exports_to_krw",
         source="관세청 1st-20th semiconductor and total export daily-average growth",
         mechanism="a stronger export run rate raises expected dollar supply from exporters and "
                   "improves the terms of trade, which is won-positive; it also signals global "
                   "technology demand",
         targets=("USDKRW", "NAS100"),
         sign="export surprise UP -> USDKRW DOWN, NAS100 UP",
         horizon="same session to five sessions",
         lag="publication at 00:00 UTC on the 21st, which is the onshore open",
         control="the same statistic working-day adjusted, and the same statistic on Taiwanese "
                 "export orders; a result present only in Korea is Korean, a result present in "
                 "both is global technology demand",
         evidence="HYPOTHESIS",
         notes="The single highest-prior edge in this pack because the release time, the "
               "instrument and the mechanism are all unambiguous."),
    edge("kr_foreign_equity_flow_to_krw",
         source="KRX 외국인 순매수, daily",
         mechanism="foreign equity purchases require won, and the FX leg follows the T+2 equity "
                   "settlement, so the print LEADS the conversion",
         targets=("USDKRW", "HK50"),
         sign="foreign net BUY -> USDKRW DOWN at a lag of one to two sessions",
         horizon="one to five sessions",
         lag="print at 09:00 UTC, FX leg one to two sessions later",
         control="the contemporaneous relation (lag zero) should be WEAKER than the lagged one "
                 "if the settlement mechanism is real; a flat lag profile refutes it",
         evidence="HYPOTHESIS"),
    edge("bok_decision_surprise_to_krw",
         source="한국은행 기준금리 decision against the prior market-implied path",
         mechanism="a rate surprise repriced the front end and therefore the carry against the "
                   "dollar and the yen",
         targets=("USDKRW", "USDJPY"),
         sign="hawkish surprise -> USDKRW DOWN",
         horizon="minutes to two sessions",
         lag="00:55-01:00 UTC decision; 02:10 UTC press conference as a SEPARATE event",
         control="the same event study on the press conference alone, and on minutes releases at "
                 "07:00 UTC, which land after the onshore close",
         evidence="HYPOTHESIS"),
    edge("kr_verbal_intervention_to_krw",
         source="구두개입 vocabulary in official statements and the Korean press",
         mechanism="verbal intervention raises the perceived cost of a one-way position and "
                   "slows the move without changing the level",
         targets=("USDKRW",),
         sign="intervention language -> lower realised volatility and fewer fast tails, with an "
              "ambiguous effect on the mean",
         horizon="one to three sessions",
         lag="headline timestamp",
         control="matched days with the same prior move and no intervention language; and the "
                 "same vocabulary test on Japanese official language against USDJPY, which "
                 "separates a Korean effect from a generic official-language effect",
         evidence="HYPOTHESIS",
         notes="The claim under test is about the SHAPE of the distribution, not its mean, and "
               "an event study on returns alone will miss it."),
    edge("kr_expiry_to_regional_variance",
         source="KOSPI200 second-Thursday expiry and its 15:20-15:30 auction",
         mechanism="hedge unwinds in the closing auction spill into the regional session through "
                   "correlated index hedges and ELS books referencing HSCEI",
         targets=("HK50", "JPN225"),
         sign="expiry day -> elevated intraday range in the Asian session",
         horizon="intraday",
         lag="06:20-06:30 UTC auction",
         control="first and third Thursdays of the same month; Japanese SQ and Taiwanese third "
                 "Wednesdays as foreign-expiry placebos",
         evidence="HYPOTHESIS"),
    edge("kr_retail_deleveraging_to_risk",
         source="신용융자잔고 falling sharply with 미수금 rising",
         mechanism="mechanical 반대매매 liquidation at the open forces one-directional selling "
                   "and a simultaneous unwind of the 서학개미 offshore book",
         targets=("USDKRW", "US500", "XAUUSD"),
         sign="forced deleveraging -> USDKRW UP, US500 DOWN, XAUUSD UP",
         horizon="one to five sessions",
         lag="one business day to the data, but the liquidation itself is at the 00:00 UTC open",
         control="the same statistic conditioned on index drawdown alone, with leverage removed; "
                 "and the second half of the session, where no forced sale executes",
         evidence="HYPOTHESIS"),
    edge("kr_dividend_repatriation_to_krw",
         source="the April and May foreign dividend payment window",
         mechanism="foreign holders convert won dividends into dollars in a compressed window",
         targets=("USDKRW",),
         sign="late April -> USDKRW UP",
         horizon="five to fifteen sessions",
         lag="payment dates, which are published per company and aggregate to a known window",
         control="the last week of every other month in the same year; and April on USDSGD and "
                 "USDJPY, which have no Korean dividend calendar",
         evidence="HYPOTHESIS"),
    edge("kr_energy_bill_to_krw",
         source="the energy share of the monthly import bill and 교역조건",
         mechanism="an inelastic dollar-denominated energy import requirement is a structural "
                   "USD bid whose size scales with the oil price",
         targets=("USDKRW", "XTIUSD"),
         sign="oil UP -> USDKRW UP at a one to two month lag",
         horizon="one to three months",
         lag="customs monthly data, about one week after month end",
         control="a net energy exporter's currency, where the sign must invert; and the oil price "
                 "alone with no Korean conditioning",
         evidence="HYPOTHESIS"),
    edge("kr_risk_premium_to_crypto_cfd",
         source="the kimchi premium as reported in public commentary",
         mechanism="a domestic risk-appetite and capital-account-tightness gauge that has "
                   "historically coincided with retail leverage highs",
         targets=("BTCUSD", "USDKRW"),
         sign="premium widening -> elevated retail risk appetite; direction on USDKRW UNTESTED",
         horizon="days to weeks",
         lag="commentary is irregular and late; pit_feasible is FALSE",
         control="신용융자잔고 entered first -- if the premium adds nothing incremental this edge "
                 "retires; and BTCUSD alone with no Korean conditioning",
         evidence="HYPOTHESIS",
         notes="Carried because the observable is real and refused as a venue feed. UNMEASURED "
               "is the expected verdict and it will be recorded as one."),
    edge("kr_nps_swap_to_krw",
         source="announced NPS hedge-ratio changes and BOK swap-line drawdowns",
         mechanism="the swap removes a scheduled structural KRW sale from the spot market; a "
                   "hedge-ratio increase is an outright won purchase",
         targets=("USDKRW",),
         sign="hedge ratio UP or swap drawn -> USDKRW DOWN",
         horizon="days to weeks",
         lag="announcement date, with the flow executed over a longer window",
         control="the same statistic at matched month-ends before the swap line existed "
                 "(pre-2022), and announcement date versus effective date",
         evidence="HYPOTHESIS"),
    edge("kr_shipbuilding_orders_to_krw",
         source="announced shipbuilding orders and their dollar value",
         mechanism="Korean yards sell dollars forward at contract signature, in size, against "
                   "multi-year receivables",
         targets=("USDKRW",),
         sign="large order announcement -> USDKRW DOWN in the following sessions",
         horizon="one to ten sessions",
         lag="announcement timestamp",
         control="the same event window shifted forward one month; and similarly sized auto or "
                 "petrochemical export announcements, which carry no forward-hedge convention",
         evidence="HYPOTHESIS"),
    edge("kr_regional_stress_to_haven",
         source="Korean-specific political or security shocks (the 2024-12-03 episode is the "
                "canonical case)",
         mechanism="a domestic political shock raises the Korea risk premium and triggers both "
                   "foreign equity selling and a haven bid",
         targets=("USDKRW", "XAUUSD", "JPN225", "HK50"),
         sign="shock -> USDKRW UP, XAUUSD UP, JPN225 and HK50 DOWN",
         horizon="hours to five sessions",
         lag="headline timestamp, frequently outside onshore hours",
         control="regional shocks with no Korean component, which should move JPN225 and HK50 "
                 "without the USDKRW leg; and the same window in years with no such event",
         evidence="HYPOTHESIS",
         notes="n is tiny by construction. This edge exists to be SIZED honestly, and a single "
               "episode can never clear a gauntlet on its own."),
)

#: Derived, never hand-maintained: the executable symbols this pack's economics reach that are
#: NOT Korea's own price. Everything absent from the broker registry is in ABSENT_INSTRUMENTS.
TRANSMISSION_TARGETS: tuple[str, ...] = tuple(sorted(
    {t for e in TRANSMISSION_EDGES_SEED for t in e["targets"]} - set(OWN_PRICE)))


# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("kr_pandemic_easing", start="2020-03-16", end="2021-08-25",
        label="Emergency easing and the first short-selling ban",
        what_changed="two emergency cuts took the Base Rate to 0.50%; short selling was banned "
                     "outright from 2020-03-16; retail participation stepped up permanently",
        invalidates="any KOSPI microstructure estimate pooling this window with a period in "
                    "which short selling was legal is averaging two different market designs"),
    era("kr_hiking_cycle", start="2021-08-26", end="2023-01-12",
        label="The hiking cycle to 3.50%, including two 빅스텝 moves",
        what_changed="the Base Rate rose from 0.50% to 3.50% with 50bp steps in July and October "
                     "2022; the won weakened past 1,440 in that October",
        invalidates="carry-based USDKRW studies pooled across this and the subsequent hold "
                    "measure an average of a rising and a flat differential"),
    era("kr_long_hold", start="2023-01-13", end="2024-10-10",
        label="The terminal hold at 3.50%",
        what_changed="policy stopped being the driver; the export cycle and the dollar took over; "
                     "the second full short-selling ban began 2023-11-06",
        invalidates="policy-surprise event studies have almost no variation in this window and "
                    "will report a null that is about the sample, not the mechanism"),
    era("kr_fx_market_reform", start="2024-07-01", end=None,
        label="Extended onshore hours and Registered Foreign Institutions",
        what_changed="the onshore interbank session was extended to 02:00 KST (17:00 UTC) and "
                     "registered foreign institutions were admitted to it",
        invalidates="EVERY overnight-gap, open-auction and offshore-price-formation statistic. "
                    "The gap is literally a different object either side of this date and no "
                    "pooled estimate of it means anything"),
    era("kr_easing_under_fx_constraint", start="2024-10-11", end=None,
        label="Easing while the won is the constraint",
        what_changed="the first cut since 2020 arrived with USDKRW near multi-decade highs, so "
                     "the BOK's reaction function became visibly two-objective",
        invalidates="a single-equation policy rule fitted across this and the hiking cycle will "
                    "mis-specify the reaction function in both"),
    era("kr_political_shock", start="2024-12-03", end="2025-06-04",
        label="The martial-law episode and the political interregnum",
        what_changed="a domestic political shock produced the sharpest Korea-specific risk-"
                     "premium episode of the sample, followed by months of elevated uncertainty "
                     "and an early presidential election",
        invalidates="any unconditional volatility or tail estimate for USDKRW that includes this "
                    "window without conditioning on it"),
    era("kr_short_selling_resumed", start="2025-03-31", end=None,
        label="Full resumption of short selling",
        what_changed="the second full ban ended and short selling resumed across the market",
        invalidates="KOSPI momentum and reversal estimates from the ban years do not transfer "
                    "forward; the arbitrage channel they lacked is back"),
    era("kr_weekly_options", start="2023-01-01", end=None,
        label="Monday weekly KOSPI200 options added to the 2019 Thursday weeklies",
        what_changed="expiry pressure was redistributed across the week, diluting the monthly "
                     "second-Thursday concentration",
        invalidates="an expiry effect estimated before 2019 and applied after 2023 is estimated "
                    "on a market where all the open interest sat on one date"),
)


# --------------------------------------------------------------------------- framework fields
#: `country_lab.REGION_COMMANDS` has one Asian command; the EAST ASIA grouping is this package's
#: own and lives in the module docstring, not in a field the framework would refuse.
MISSION = ("Mine the Korean economic system to exhaustion for forced flows that reach a symbol "
           "this broker quotes, and report by name every one that cannot be measured on this box.")
#: There is no KRW futures contract at the CFTC, so there is no COT row for this country. Empty
#: is the MEASUREMENT, and the KRX derivatives file is the substitute this pack names instead.
COT_CURRENCY = ""
EXPORT_ECONOMY = "semiconductor_exporter"
#: Margin lending is broadly available to Korean households through brokers, with maintenance
#: ratios rather than a regulatory quota, and the balance is published DAILY -- which is what
#: makes the regime measurable at all.
RETAIL_LEVERAGE_REGIME = "open"
#: An open era still needs two parseable bounds for the framework's era masks. This stamp says
#: "not yet ended", it does not say the era ends here.
OPEN_ERA_END = "2030-12-31"
#: Recurring solar closures, as MM-DD, for years beyond the tabulated ones. The lunar holidays
#: (설날, 추석, 부처님오신날) CANNOT appear here and are tabulated instead.
HOLIDAY_FIXED_MD: tuple[str, ...] = ("01-01", "03-01", "05-01", "05-05", "06-06", "08-15",
                                     "10-03", "10-09", "12-25")

#: The Korean trading day in UTC. KST never shifts, so these are fixed all year -- which is
#: exactly why they must be re-mapped onto the broker's own UTC+2/UTC+3 server clock per season.
SESSION_WINDOWS: tuple[dict[str, str], ...] = (
    {"name": "kr_onshore_open", "start_utc": "00:00", "end_utc": "01:00",
     "notes": "the 09:00 KST open; the MAR is published into it and the overnight offshore gap "
              "is discovered here"},
    {"name": "kr_bok_decision", "start_utc": "00:45", "end_utc": "02:30",
     "notes": "decision at 09:55-10:00 KST and the Governor's press conference at 11:10 KST, "
              "which are two separate events in one window"},
    {"name": "kr_closing_auction", "start_utc": "06:20", "end_utc": "06:45",
     "notes": "the ten-minute KRX closing call auction and the derivatives close; KOSPI200 "
              "settlement is struck here on expiry days"},
    {"name": "kr_offshore", "start_utc": "07:00", "end_utc": "21:00",
     "notes": "the NDF session, where Korea's overnight gap is manufactured"},
    {"name": "kr_extended_onshore", "start_utc": "06:30", "end_utc": "17:00",
     "notes": "the session added on 2024-07-01; before that date this window did not exist and "
              "no statistic may be pooled across the boundary"},
)

#: Scheduled national statistics, with the minute each lands in UTC.
RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "kr_customs_20day", "cadence": "monthly", "time_utc": "00:00",
     "source": "관세청", "notes": "the 1st-20th trade print on the 21st, at the onshore open"},
    {"name": "kr_customs_full_month", "cadence": "monthly", "time_utc": "00:00",
     "source": "관세청 and 산업통상자원부", "notes": "the full-month trade print on the 1st"},
    {"name": "kr_cpi", "cadence": "monthly", "time_utc": "23:00",
     "source": "통계청", "notes": "released 08:00 KST, which is BEFORE the onshore open"},
    {"name": "kr_gdp_advance", "cadence": "quarterly", "time_utc": "23:00",
     "source": "한국은행", "notes": "advance estimate, released 08:00 KST"},
    {"name": "kr_bop", "cadence": "monthly", "time_utc": "23:00",
     "source": "한국은행", "notes": "balance of payments, about T+55 days"},
    {"name": "kr_fx_reserves", "cadence": "monthly", "time_utc": "23:00",
     "source": "한국은행", "notes": "about the fifth business day of the month"},
)

#: Institutional flow series, by name, for the framework's generic institutional-flow miner.
INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "KRX 투자자별 거래실적 (daily net buy by investor type, data.krx.co.kr)",
    "KRX 선물옵션 투자자별 미결제약정 (daily derivatives positions by investor type)",
    "금융투자협회 신용융자잔고 and 예탁금 (daily retail leverage, freesis.kofia.or.kr)",
    "한국예탁결제원 foreign KTB holdings (seibro.or.kr)",
    "금융감독원 외국인 증권투자 동향 (monthly, with nationality split)",
)


# --------------------------------------------------------------------------- typed row builders
def _central_bank_row(lab: Any) -> Any:
    """The BOK as `country_lab.CentralBank`, with every tabulated decision date flattened."""
    dates: list[str] = []
    for year in sorted(CENTRAL_BANK["decision_dates"]):
        dates.extend(CENTRAL_BANK["decision_dates"][year])
    return lab.CentralBank(
        name="Bank of Korea (한국은행)",
        framework="inflation_targeter",
        decision_dates=tuple(sorted(dates)),
        decision_calendar_rule=str(CENTRAL_BANK["schedule_rule"]),
        decision_time_utc="00:55",
        publication_classes=("통화정책방향 결정문", "총재 기자간담회 (02:10 UTC)",
                             "금융통화위원회 의사록 (07:00 UTC, about two weeks later)"),
        policy_rate_series="kr_base_rate",
        expected_rate_series="",
        notes=f"{CENTRAL_BANK['fx_operations']} INTERVENTION DISCLOSURE: "
              f"{CENTRAL_BANK['intervention_disclosure']} 2026 DATES ARE NOT PUBLISHED: "
              f"{CENTRAL_BANK['decision_dates_status'][2026]}")


def _fixing_rows(lab: Any) -> tuple[Any, ...]:
    """Korea's two published references, in UTC. KST never shifts, so `dst_rule` is 'none'."""
    return (
        lab.Fixing(name="매매기준율 (Market Average Rate, SMBS)", time_utc="00:00",
                   dst_rule="none", instruments=("USDKRW",), window_minutes=60,
                   notes=str(FIXING_CONVENTIONS["mar"]["note"])),
        lab.Fixing(name="KRW NDF fixing (settled on the MAR)", time_utc="00:00",
                   dst_rule="none", instruments=("USDKRW",), window_minutes=60,
                   notes=str(FIXING_CONVENTIONS["ndf_fix"]["why_it_matters"])),
        lab.Fixing(name="KRX closing call auction", time_utc="06:20", dst_rule="none",
                   instruments=("USDKRW",), window_minutes=10,
                   notes="the ten-minute single-price auction that also sets the KOSPI200 "
                         "settlement value on expiry days"),
    )


def _settlement_rows(lab: Any) -> tuple[Any, ...]:
    """Korea's conventions as RULES. There is no Japanese gotobi here and none is invented; what
    Korea has is a month-end conversion cluster, a customs-print cluster on the 21st, a dividend
    season and a year-end market closure."""
    return (
        lab.SettlementRule(name="kr_month_end_exporter_nego", kind="month_end", days=(),
                           months=(), weekday=-1, week_of_month=0, roll="previous",
                           window_utc=("00:00", "06:30"), instruments=("USDKRW",),
                           notes=str(SETTLEMENT_CONVENTIONS["month_end"])),
        lab.SettlementRule(name="kr_customs_20day_print", kind="day_of_month", days=(21,),
                           months=(), weekday=-1, week_of_month=0, roll="next",
                           window_utc=("00:00", "02:00"), instruments=("USDKRW",),
                           notes="the 1st-20th trade print lands at the onshore open; the day is "
                                 "rolled FORWARD when the 21st is closed because the release "
                                 "moves with the working calendar"),
        lab.SettlementRule(name="kr_quarter_end_funding", kind="quarter_end", days=(),
                           months=(), weekday=-1, week_of_month=0, roll="previous",
                           window_utc=("00:00", "06:30"), instruments=("USDKRW",),
                           notes="insurer and bank hedge rolls concentrate here; the year-end "
                                 "roll is structurally the tightest of the four"),
        lab.SettlementRule(name="kr_dividend_repatriation", kind="day_of_month", days=(25, 26,
                           27, 28, 29, 30), months=(4, 5), weekday=-1, week_of_month=0,
                           roll="previous", window_utc=("00:00", "06:30"),
                           instruments=("USDKRW",),
                           notes=str(SETTLEMENT_CONVENTIONS["dividend_season"])),
        lab.SettlementRule(name="kr_expiry_second_thursday", kind="week_of_month", days=(),
                           months=(), weekday=3, week_of_month=2, roll="previous",
                           window_utc=("06:20", "06:45"),
                           instruments=("HK50", "JPN225", "USDKRW"),
                           notes="KOSPI200 futures and options settle out of the closing auction "
                                 "on the second Thursday; the quadruple-witching months are "
                                 "March, June, September and December"),
    )


def _exchange_rows(lab: Any) -> tuple[Any, ...]:
    """KRX with its expiry calendar expanded. `index_symbols` is EMPTY and that is the finding:
    this broker quotes no Korean index, so the generic expiry miner has nothing to run on and the
    pack's own miner measures the effect on the carriers instead."""
    dates = tuple(r["date"] for y in (2024, 2025, 2026) for r in kr_expiry_dates(y)["expiries"])
    return (
        lab.Exchange(name="Korea Exchange (KRX)", index_symbols=(),
                     expiry_rule="second Thursday of the contract month for KOSPI200 futures and "
                                 "options; settlement struck in the 15:20-15:30 KST closing call "
                                 "auction (06:20-06:30 UTC)",
                     expiry_dates=dates, open_utc="00:00", close_utc="06:30",
                     notes="NO KOREAN INDEX IS QUOTED BY THIS BROKER. KOSPI200 and KOSDAQ150 are "
                           "in ABSENT_INSTRUMENTS with the carriers that stand in for them."),
    )


def _release_rows(lab: Any) -> tuple[Any, ...]:
    return tuple(lab.ReleaseClass(name=r["name"], cadence=r["cadence"], time_utc=r["time_utc"],
                                  dates=(), actual_series="", expected_series="",
                                  source=str(r["source"]), notes=str(r["notes"]))
                 for r in RELEASE_CLASSES)


# --------------------------------------------------------------------------- the custom miner
def kr_expiry_thursday_placebo(pack_in: Any, ctx: Any) -> dict[str, Any]:
    """The second-Thursday effect measured against the OTHER Thursdays of the same month.

    WHY THIS IS NOT THE GENERIC EXPIRY MINER. `country_lab.generic_derivatives_expiry` controls
    an event against matched weekday-and-hour days drawn from the whole sample. For Korea that
    control is too weak: every Thursday in the sample is a candidate control, and a second
    Thursday is also mid-month, which carries the customs print, the month's option roll and a
    different point in the settlement cycle. The honest placebo for "the SECOND Thursday" is the
    FIRST and THIRD Thursday of the SAME month -- same weekday, same month, same macro calendar,
    no KOSPI200 settlement. That control has to be built, so it is built here.

    AND KOREA HAS NO INDEX ON THIS BROKER, which is the second reason this miner exists: the
    effect can only be looked for in the carriers (HK50, JPN225) and in USDKRW, and the reading
    must SAY that it is measuring a spill rather than the settlement itself.
    """
    lab = _lab()
    out: dict[str, Any] = {"miner": "kr_expiry_thursday_placebo", "country": CODE,
                           "readings": [], "measured": 0}
    if lab is None:
        out["outcome"] = "UNMEASURED"
        out["why"] = "libs.research.country_lab is absent on this tree"
        return out
    years = sorted({int(y) for y in HOLIDAYS_RULE["table"]})
    events: list[str] = []
    placebo: list[str] = []
    for year in years:
        for month in range(1, 13):
            events.append(nth_weekday(year, month, 3, 2).isoformat())
            placebo.append(nth_weekday(year, month, 3, 1).isoformat())
            placebo.append(nth_weekday(year, month, 3, 3).isoformat())
    ev = lab.parse_days(tuple(events))
    pb = lab.parse_days(tuple(placebo))
    for sym in ("USDKRW", "HK50", "JPN225"):
        bars = ctx.bars(sym, "H1")
        if bars is None:
            ctx.note(f"bars:{sym}", "no H1 tape on this box, so the second-Thursday placebo "
                                    "cannot be run for this carrier")
            continue
        try:
            got = lab.event_effect(bars, ev, horizon=1, rng=ctx.rng(f"expiry:{sym}"))
            ctrl = lab.event_effect(bars, pb, horizon=1, rng=ctx.rng(f"placebo:{sym}"))
        except Exception as exc:  # pragma: no cover -- a framework signature change
            ctx.note(f"event_effect:{sym}", f"{type(exc).__name__}: {exc}")
            continue
        out["readings"].append({
            "symbol": sym, "role": "own_price" if sym in OWN_PRICE else "carrier",
            "second_thursday": got, "first_and_third_thursday": ctrl,
            "claim": "a Korean settlement effect must be present on the SECOND Thursday and "
                     "absent on the first and third of the same month; present on all three is "
                     "a Thursday effect and nothing Korean"})
        out["measured"] += int(got.get("verdict") == "MEASURED"
                               and ctrl.get("verdict") == "MEASURED")
    out["outcome"] = "OK" if out["measured"] else "UNMEASURED"
    if not out["measured"]:
        out["why"] = "no carrier produced a measurable event and placebo pair"
    return out


CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("kr_expiry_thursday_placebo",
          domain_ids=("kr_derivatives_expiry", "kr_session_microstructure"),
          kind="calendar",
          entry="countries.kr.pack:kr_expiry_thursday_placebo",
          cadence_s=86400.0,
          steerable=False,
          notes="A fixed cost, not a steerable one: the second-Thursday grid must be read every "
                "pass whatever it yielded last week, because a miner conditioning on the wrong "
                "session produces a confident wrong number rather than nothing."),
)


# ---------------------------------------------------------------- framework row conversion
# THE RICH STRUCTURES ABOVE ARE THE SOURCE OF TRUTH. `libs.research.country_lab` types every row
# it consumes, and its rows hold less than this pack knows -- a source class's crawl roots, an
# edge's negative control, an era's invalidation clause, a positioning series' publication lag.
# Nothing is dropped in translation: whatever a typed row has no field for is folded into its
# `notes`, so `country_lab.validate_pack` passes AND a reader still gets the reason. When the
# framework has not landed, `pack()` returns the rich dicts under the same twenty-one keys and
# every test in this package reads them through the same accessor.

#: Which economy an executable symbol belongs to, for `TransmissionSeed.to_country`. A symbol
#: with no home economy (metals, energy, the crypto CFD) is "global", which is a real answer.
DEST_BY_SYMBOL: dict[str, str] = {
    "USDKRW": "kr", "USDJPY": "jp", "JPN225": "jp", "HK50": "hk", "CHINAH": "hk",
    "USDCNH": "cn", "USDHKD": "hk", "EURHKD": "hk", "HKDJPY": "hk", "NAS100": "us",
    "US500": "us", "US30": "us", "US2000": "us", "UST05Y": "us", "UST10Y": "us",
    "AUDUSD": "au", "AUS200": "au", "NZDUSD": "nz", "USDSGD": "sg", "SGDJPY": "sg",
    "EURUSD": "eu", "GER40": "eu", "EUSTX50": "eu", "UK100": "uk", "USDCAD": "ca",
    "USDTHB": "th", "USDINR": "in", "USDIDR": "id", "USDX": "us",
}


def _lab() -> Any:
    """`libs.research.country_lab` when it has landed, else None. Imported lazily, on purpose."""
    try:
        from libs.research import country_lab
    except Exception:
        return None
    return country_lab


def dest_of(symbol: str) -> str:
    """The economy an executable symbol lands in. Unknown symbols answer "global", never ""."""
    return DEST_BY_SYMBOL.get(str(symbol).upper(), "global")


def holiday_dates() -> tuple[str, ...]:
    """Every tabulated closure date, flattened and sorted, for `HolidayRule.dates`."""
    out: set[str] = set()
    for tbl in dict(HOLIDAYS_RULE["table"]).values():
        out.update(str(k) for k in dict(tbl))
    return tuple(sorted(out))


def source_class_lines() -> tuple[str, ...]:
    """`source_classes` as the framework's strings, with the crawl roots kept inside them."""
    return tuple(
        f"{sc['id']} :: layer={sc['layer']} :: {sc['label']} :: "
        f"roots={'; '.join(sc['roots']) or 'NONE'} :: "
        f"queries={'; '.join(sc['queries']) or 'NONE'} :: "
        f"languages={','.join(sc['languages']) or 'NONE'} :: access={sc['access_label']} :: "
        f"credibility={sc['credibility']} :: predictive={sc['predictive_state']} :: "
        f"machine_use_allowed={sc['machine_use_allowed']} :: licence={sc['licence']}"
        for sc in SOURCE_CLASSES)


def positioning_lines() -> tuple[str, ...]:
    """`positioning_sources` as strings, with frequency, lag, root and licence kept inside."""
    return tuple(
        f"{p['id']} :: {p['name']} :: {p['frequency']}, lag {p['lag']} :: root={p['root']} :: "
        f"{p['licence']}" for p in POSITIONING_SOURCES)


def _era_rows(lab: Any) -> tuple[Any, ...]:
    """Policy eras as `country_lab.Era`. An open era gets a far end date and says so: the
    framework's validator needs two parseable bounds and `None` is not one."""
    rows = []
    for e in POLICY_ERAS:
        end = e["end"] or OPEN_ERA_END
        note = (f"{e['label']}. WHAT CHANGED: {e['what_changed']} INVALIDATES: {e['invalidates']}"
                + ("" if e["end"] else f" (open era; end stamped {OPEN_ERA_END} so the bound "
                                       f"parses, not because it is known)"))
        rows.append(lab.Era(name=e["id"], start=e["start"], end=end, notes=note))
    return tuple(rows)


def _seed_rows(lab: Any) -> tuple[Any, ...]:
    """Transmission seeds as `country_lab.TransmissionSeed`, ONE PER TARGET SYMBOL.

    An edge here names several executable targets because one mechanism reaches several books;
    the framework's seed names exactly one asset, which is the right grain for measurement. The
    sign, horizon, negative control and evidence label travel in `notes` so no leg is measured
    without the control that would refute it.
    """
    rows = []
    for e in TRANSMISSION_EDGES_SEED:
        for sym in e["targets"]:
            rows.append(lab.TransmissionSeed(
                to_country=dest_of(sym), asset=sym, actor=e["id"], constraint=e["mechanism"],
                flow=e["source"], source_series=e["source"], source_symbol="",
                lag_days=1.0, era="",
                notes=(f"SIGN: {e['sign']} HORIZON: {e['horizon']} LAG: {e['lag']} "
                       f"CONTROL: {e['control']} EVIDENCE: {e['evidence']}"
                       + (f" NOTE: {e['notes']}" if e["notes"] else ""))))
    return tuple(rows)


def _typed(lab: Any) -> dict[str, Any]:
    """Every field of the pack in the framework's own types."""
    return {
        "executable_instruments": EXECUTABLE_INSTRUMENTS,
        "central_bank": _central_bank_row(lab),
        "fixing_conventions": _fixing_rows(lab),
        "settlement_conventions": _settlement_rows(lab),
        "exchanges": _exchange_rows(lab),
        "release_classes": _release_rows(lab),
        "session_windows": tuple(lab.SessionWindow(name=w["name"], start_utc=w["start_utc"],
                                                   end_utc=w["end_utc"], notes=w["notes"])
                                 for w in SESSION_WINDOWS),
        "holidays_rule": lab.HolidayRule(dates=holiday_dates(), fixed_md=HOLIDAY_FIXED_MD,
                                         weekly_closed=(5, 6),
                                         notes=str(HOLIDAYS_RULE["rule"])),
        "fiscal_year_end": FISCAL_YEAR_END,
        "policy_eras": _era_rows(lab),
        "positioning_sources": positioning_lines(),
        "cot_currency": COT_CURRENCY,
        "export_economy": EXPORT_ECONOMY,
        "retail_leverage_regime": RETAIL_LEVERAGE_REGIME,
        "native_languages": NATIVE_LANGUAGES,
        "terminology": TERMINOLOGY,
        "source_classes": source_class_lines(),
        "institutional_flow_sources": INSTITUTIONAL_FLOW_SOURCES,
        "datasets": tuple(lab.DatasetRow(**d) for d in DATASETS),
        "actors": tuple(lab.ActorRow(**a) for a in ACTORS),
        "domains": tuple(lab.DomainRow(**d) for d in DOMAINS),
        "miner_domains": {m["name"]: m["domain_ids"] for m in CUSTOM_MINERS},
        "custom_miners": tuple(m["entry"] for m in CUSTOM_MINERS),
        "transmission_edges_seed": _seed_rows(lab),
        "mission": MISSION,
    }


def _rich() -> dict[str, Any]:
    """The pack's twenty-one fields as plain data: the shape used when the framework is absent,
    and the shape every structure above is authored in."""
    return {
        "code": CODE, "name": NAME, "region_command": REGION_COMMAND, "currency": CURRENCY,
        "executable_instruments": EXECUTABLE_INSTRUMENTS, "central_bank": CENTRAL_BANK,
        "fixing_conventions": FIXING_CONVENTIONS,
        "settlement_conventions": SETTLEMENT_CONVENTIONS, "exchanges": EXCHANGES,
        "holidays_rule": HOLIDAYS_RULE, "fiscal_year_end": FISCAL_YEAR_END,
        "positioning_sources": POSITIONING_SOURCES, "native_languages": NATIVE_LANGUAGES,
        "terminology": TERMINOLOGY, "source_classes": SOURCE_CLASSES, "datasets": DATASETS,
        "actors": ACTORS, "domains": DOMAINS, "custom_miners": CUSTOM_MINERS,
        "transmission_edges_seed": TRANSMISSION_EDGES_SEED, "policy_eras": POLICY_ERAS,
    }


def pack() -> Any:
    """This country pack: a `country_lab.CountryPack` when the framework has landed, else a plain
    dict carrying the same twenty-one keys. Both shapes are read by the same tests."""
    lab = _lab()
    if lab is None:
        return _rich()
    try:
        return lab.CountryPack(code=CODE, name=NAME, region_command=REGION_COMMAND,
                               currency=CURRENCY, **_typed(lab))
    except Exception:  # pragma: no cover -- a framework signature that moved under this pack
        return _rich()


def instrument_report(path: Any = None) -> dict[str, Any]:
    """What this pack can trade, what carries its economics and what is missing -- MEASURED
    against the broker registry rather than asserted."""
    split = resolve(EXECUTABLE_INSTRUMENTS, path)
    return {"code": CODE, "own_price": OWN_PRICE, "executable": tuple(split["tradable"]),
            "equities_refused": tuple(split["equities"]),
            "absent_from_universe": tuple(split["absent"]),
            "transmission_targets": TRANSMISSION_TARGETS,
            "named_absent_instruments": ABSENT_INSTRUMENTS}
