"""THE CHINA COUNTRY PACK -- China's own mechanics, held as data and checked against MT5.

WHY CHINA IS NOT JAPAN OR KOREA WITH DIFFERENT NOUNS. Japan's calendar edge is the gotobi
settlement day; Korea's is a customs print three times a month and a second-Thursday expiry.
China has neither, and what it has instead exists nowhere else:

  * A PRICE THAT IS ANNOUNCED BEFORE IT IS TRADED. CFETS publishes the CNY central parity at
    09:15 Beijing -- 01:15 UTC -- and the onshore market does not open until 09:30. For fifteen
    minutes the offshore market can act on a Chinese policy number that the onshore market
    cannot yet trade. No other economy in this package hands the desk a window like that.
  * ONE CURRENCY WITH TWO PRICES. Onshore CNY moves inside a 2% band around that fix; offshore
    CNH has no band and no fix. The gap between them is not a rounding difference -- it is the
    capital account, priced, daily, and it widens exactly when the state is leaning on the fix.
  * A WEEK WHEN ONLY HALF THE MARKET EXISTS. At Spring Festival and National Day the fix, the
    onshore spot and the A-share book all stop for a week or more while USDCNH, HK50 and CHINAH
    keep trading. Offshore price discovery runs unopposed for days and one session reconciles it.
  * A SETTLEMENT RULE THAT SHAPES THE PRICE PATH. A shares settle T+1: nothing bought today can
    be sold today. Combined with a hard daily price limit, an imbalance becomes a QUEUE rather
    than a price, and the information arrives at the next open. The mainland overnight gap is a
    settlement rule before it is a news effect.
  * A POLICY CALENDAR WITH NO DATES. The Politburo's economic meetings, which move CHINAH and
    HK50 more than any data release, are announced by MONTH and not by date. That is recorded
    here as a point-in-time fact, because an event study cannot be built from a calendar that
    does not exist.

WHAT THIS PACK MAY NOT DO. Mainland single names are OBSERVABLES and never hypothesis ground
(two-lane order, 2026-09-06) -- developers, chipmakers and banks are read through sector and
national series and never put on a docket. No crypto-exchange venue is named, subscribed or
crawled anywhere in this pack (universe mandate, 2026-08-18).

WHAT IS EXECUTABLE. USDCNH is China's own price on this broker and it is the OFFSHORE one; the
onshore price is not quoted anywhere in the registry. CHINAH and HK50 carry the equity leg,
AUDUSD and AUS200 carry Chinese physical demand, and the metals and energy complex carries the
rest. CSI300, the mainland futures contracts, iron ore and Chinese government bonds are ALL
absent from the universe and are named in `ABSENT_INSTRUMENTS` with what stands in for them,
because a silently dropped instrument becomes a silently dropped mechanism.
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


CODE = "cn"
NAME = "China"
REGION_COMMAND = "asia"  # country_lab.REGION_COMMANDS; EAST ASIA is this package's own grouping
#: The CURRENCY is the renminbi. It has TWO PRICES -- onshore CNY inside a band around a managed
#: fix, and offshore CNH with no band -- and the gap between them is one of this pack's primary
#: observables rather than a rounding difference.
CURRENCY = "CNY"
NATIVE_LANGUAGES = ("zh-Hans",)

#: China's own price on this broker is the OFFSHORE one. Onshore USDCNY is not quoted anywhere in
#: the registry, so every onshore mechanism has to be read through USDCNH and the gap between the
#: two is a measurement the desk must make itself.
OWN_PRICE: tuple[str, ...] = ("USDCNH",)

#: What the CN department may place an order in: the offshore currency, the two China equity
#: expressions this broker quotes, and the demand-side carriers Chinese activity reaches.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDCNH", "HK50", "CHINAH", "AUDUSD", "AUS200", "USDSGD", "USDKRW", "USDHKD", "XCUUSD",
    "XALUSD", "XZNUSD", "XNIUSD", "XAUUSD", "XTIUSD", "XBRUSD", "SOYBEAN", "US500", "NAS100")

ABSENT_INSTRUMENTS: tuple[dict[str, str], ...] = (
    {"instrument": "onshore USDCNY",
     "why": "the broker quotes the offshore CNH only; the onshore price is behind a capital "
            "account and is not a CFD anywhere in the registry",
     "carried_by": "USDCNH, with the CNH-CNY basis treated as an UNOBSERVED state variable that "
                   "the desk can only proxy from public CFETS closes"},
    {"instrument": "CSI300, SSE Composite, ChiNext and STAR indices",
     "why": "no mainland equity index CFD in desks/mt5/data/universe/universe.json",
     "carried_by": "CHINAH (Hong Kong-listed mainland enterprises) and HK50; the A-H basis is "
                   "the error term and is itself an observable"},
    {"instrument": "iron ore (DCE or SGX)",
     "why": "absent from the broker registry; the metals complex here is copper, aluminium, "
            "zinc and nickel",
     "carried_by": "AUDUSD and AUS200, which are the liquid market-traded expressions of "
                   "Chinese iron-ore demand"},
    {"instrument": "China government bond futures (CFFEX T, TF)",
     "why": "no Chinese rates instrument is quoted",
     "carried_by": "UST10Y as the global rates leg only; the China-specific term premium is "
                   "left UNMEASURED by name rather than proxied"},
    {"instrument": "CFFEX IF/IH/IC/IM index futures",
     "why": "absent; the mainland derivatives complex is not tradable here",
     "carried_by": "CHINAH and HK50 for the equity leg, and the pack's own miner measures the "
                   "third-Friday expiry on those carriers rather than on the contract itself"},
)


# --------------------------------------------------------------------------- central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "People's Bank of China",
    "native_name": "中国人民银行",
    "committee": "货币政策委员会 is ADVISORY. The operative decisions are administrative and are "
                 "taken by the PBOC and the State Council, which is why this pack has an "
                 "OPERATIONS calendar rather than a meeting calendar.",
    "policy_rate": "the 7-day reverse repo rate (7天逆回购利率) has been the primary policy rate "
                   "since 2024-07-22; before that the 1-year MLF rate (中期借贷便利) carried "
                   "that role and the LPR was quoted off it",
    "meetings_per_year": 0,
    "schedule_rule": (
        "THERE IS NO RATE DECISION DATE IN THE WESTERN SENSE. What China has instead is a "
        "recurring OPERATIONS calendar: the CNY central parity (中间价) at 09:15 Beijing "
        "(01:15 UTC) every business day; the open-market operation result (公开市场操作) at "
        "about 09:20 Beijing (01:20 UTC) every business day; the Loan Prime Rate (贷款市场报价 "
        "利率) on the 20th of each month at 09:15 Beijing, rolled forward when the 20th is "
        "closed; the MLF on the 15th of each month until July 2024 and on the 25th after it; "
        "and reserve-requirement (存款准备金率) changes announced ad hoc, usually after the "
        "close and effective ten to fifteen days later. The LPR dates are what this pack uses "
        "as decision anchors because they are the only scheduled, pre-announced, rate-setting "
        "moments China publishes."),
    "minutes_rule": (
        "There are no minutes. The nearest equivalent is the quarterly 货币政策执行报告, "
        "published about two months after quarter end, whose LANGUAGE shifts (稳健中性, "
        "灵活适度, 适度宽松) are the policy signal the domestic market actually trades."),
    "timezone": "CST = UTC+8 all year; China observes NO daylight saving, so 09:15 Beijing is "
                "01:15 UTC in January and in July alike.",
    "fx_operations": (
        "The fix itself IS the operation. The daily central parity is set from the previous "
        "close plus a basket move plus 逆周期因子 (the counter-cyclical factor), introduced "
        "2017-05, suspended 2018-01 and reintroduced 2018-08. A fix persistently stronger than "
        "the model-implied value is state guidance, and the GAP is the observable. Beyond the "
        "fix the toolkit is: state-bank dollar selling in the onshore session, raising the "
        "offshore CNH funding cost (a CNH HIBOR squeeze), the FX risk reserve requirement on "
        "forward sales (外汇风险准备金率, moved between 0% and 20%), and the FX deposit reserve "
        "ratio (外汇存款准备金率)."),
    "intervention_disclosure": (
        "Not disclosed as transactions. The monthly 外汇储备 print (about the 7th) and the "
        "monthly 银行结售汇 balance from SAFE (about three weeks later) are the closest public "
        "measurements, and both are far too slow and too netted to signal."),
    "band": "the onshore spot may move +/-2% around the central parity in a session, widened "
            "from +/-1% on 2014-03-17. The band is on the ONSHORE price, which this broker does "
            "not quote -- so the band constrains USDCNH only indirectly and that indirection is "
            "part of what makes the CNH-CNY gap informative.",
    "decision_dates": {},
    "decision_dates_status": {
        2020: "RULE_ONLY -- LPR on the 20th at 01:15 UTC, rolled forward off closures",
        2021: "RULE_ONLY", 2022: "RULE_ONLY", 2023: "RULE_ONLY", 2024: "RULE_ONLY",
        2025: "RULE_ONLY",
        2026: "RULE_ONLY -- the rule is stable and the dates are derived by cn_lpr_dates(); "
              "there is no published calendar to verify them against because the PBOC does not "
              "publish one, which is itself the fact this pack records",
    },
    "verification": "The LPR anchors are DERIVED, not transcribed. Any event study on them must "
                    "confirm each date against the PBOC's own announcement archive, because a "
                    "roll off a closure that this pack computed differently from the PBOC is a "
                    "one-session error in every window.",
}


# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: dict[str, Any] = {
    "central_parity": {
        "name": "人民币汇率中间价 / CNY central parity",
        "publisher": "中国外汇交易中心 (CFETS)",
        "definition": "set from the previous onshore close, the overnight move of a currency "
                      "basket, and the counter-cyclical factor; the formula is described but the "
                      "factor is not published, which is exactly why the residual is the signal",
        "published_local": "09:15 Beijing",
        "published_utc": "01:15 UTC",
        "note": "The fix is published FIFTEEN MINUTES BEFORE the onshore market opens at 09:30 "
                "Beijing. That gap is the cleanest natural experiment in the pack: the offshore "
                "market can react to the fix while the onshore one cannot yet trade.",
    },
    "onshore_close": {
        "name": "CFETS 收盘价 / the onshore closing rate",
        "published_local": "16:30 Beijing for the reference close; the onshore session itself "
                           "runs to 23:30 Beijing since the 2016 extension",
        "published_utc": "08:30 UTC",
        "note": "The 16:30 close is what feeds the next morning's fix formula, NOT the 23:30 "
                "close. A study that uses the wrong one of the two is modelling a fix input "
                "that does not exist.",
    },
    "cnh_hibor": {
        "name": "CNH HIBOR",
        "publisher": "Treasury Markets Association, Hong Kong",
        "published_local": "about 11:15 Hong Kong",
        "published_utc": "03:15 UTC",
        "note": "The offshore funding cost. A spike here is the classic defence of the currency: "
                "it makes a short CNH position expensive to carry, and it is visible the same "
                "day while intervention is not.",
    },
    "onshore_hours": {
        "session": "09:30-23:30 Beijing = 01:30-15:30 UTC since the 2016-01-04 extension "
                   "(previously a 16:30 Beijing close)",
        "break": "THE 2016 EXTENSION IS A MICROSTRUCTURE BREAK for any onshore/offshore overlap "
                 "statistic: before it, the offshore market traded for eight hours a day with no "
                 "onshore counterpart at all.",
    },
    "offshore": {
        "name": "CNH",
        "venue": "Hong Kong and offshore centres, 24/5, no band, no official fixing",
        "note": "USDCNH is what this broker quotes. It is the same currency under different "
                "rules, and the difference in rules is the mechanism.",
    },
    "dst": "NONE. CST is UTC+8 year-round.",
}

SETTLEMENT_CONVENTIONS: dict[str, Any] = {
    "spot": "T+2 for CNH; the onshore market also trades T+0 and T+1",
    "convertibility": "the capital account is not open. 结售汇 (FX settlement and sales) is "
                      "conducted against documented trade and investment need, which is why a "
                      "corporate's dollar conversion decision is a POLICY-CONSTRAINED choice "
                      "rather than a free one, and why it clusters.",
    "corporate_conversion": "exporters' 结汇 (converting dollars to renminbi) clusters at month "
                            "end, at quarter end and before the Spring Festival wage and bonus "
                            "season, which is the single largest seasonal renminbi demand of "
                            "the year",
    "connect_settlement": "Stock Connect northbound settles securities on T and cash on T+1, a "
                          "mismatch foreign investors fund in Hong Kong dollars and offshore "
                          "renminbi -- so a large northbound day is an offshore CNH demand event",
    "holiday_asymmetry": "THE MOST IMPORTANT ROW IN THIS TABLE. During the Spring Festival and "
                         "National Day closures the onshore market, the fix and the A-share "
                         "book are ALL shut for a week or more while USDCNH, HK50 and CHINAH "
                         "keep trading. Offshore price discovery runs unopposed for days, and "
                         "the reopening session is where the two prices reconcile.",
}

EXCHANGES: dict[str, Any] = {
    "cash": {
        "name": "Shanghai Stock Exchange (上海证券交易所), Shenzhen Stock Exchange (深圳证券 "
                "交易所), Beijing Stock Exchange",
        "hours_local": "09:30-11:30 and 13:00-15:00 Beijing",
        "hours_utc": "01:30-03:30 and 05:00-07:00 UTC",
        "auctions": "opening call 09:15-09:25 Beijing (01:15-01:25 UTC), which runs INSIDE the "
                    "fixing minute; closing call 14:57-15:00 Beijing (06:57-07:00 UTC)",
        "settlement": "T+1 for A shares: stock bought today cannot be sold until tomorrow. This "
                      "is not a detail -- it removes intraday mean reversion from the A-share "
                      "book by construction and makes the OPEN the only exit for yesterday's buyer",
        "price_limit": "+/-10% on the main boards, +/-20% on ChiNext (创业板) and the STAR market "
                       "(科创板), +/-5% on ST-flagged names; newly listed names are unconstrained "
                       "for their first five sessions on ChiNext and STAR",
        "halts": "停牌 individual suspensions are common and can last weeks; a suspended "
                 "constituent keeps its last price in the index, so an index return during a "
                 "suspension wave is a stale-price artefact and must be conditioned on",
        "circuit_breaker": "熔断 existed for FOUR TRADING DAYS in January 2016 and was abolished. "
                           "It is kept here because it is the cleanest regime break in the "
                           "sample and because its removal, not its existence, is the durable fact",
    },
    "derivatives": {
        "name": "China Financial Futures Exchange (中国金融期货交易所, CFFEX)",
        "contracts": "IF (CSI300), IH (SSE50), IC (CSI500), IM (CSI1000) index futures and "
                     "options; T and TF government bond futures",
        "expiry_rule": "THIRD FRIDAY of the contract month -- not Korea's second Thursday and "
                       "not Taiwan's third Wednesday",
        "settlement_price": "the arithmetic average of the underlying index over the LAST TWO "
                            "HOURS of the cash session on the final trading day, which is a much "
                            "wider settlement window than Korea's ten-minute auction and "
                            "therefore a much harder target to push",
        "hours_local": "09:30-15:00 Beijing, aligned to the cash market since 2016",
    },
    "commodities": {
        "name": "Shanghai Futures Exchange (上期所), Dalian (大商所), Zhengzhou (郑商所), "
                "Shanghai International Energy Exchange (上海国际能源交易中心, INE)",
        "why_here": "the mainland commodity complex is where Chinese physical demand is priced "
                    "first. None of it is quoted by this broker, so it is an OBSERVABLE set and "
                    "its executable expressions are XCUUSD, XALUSD, XZNUSD, XNIUSD, XTIUSD and "
                    "the Australian pair",
        "disclosure": "each exchange publishes daily top-20 member long and short positions "
                      "(持仓排名) and weekly warehouse stocks (库存) -- a free, daily positioning "
                      "series with no Western equivalent",
    },
    "connect": {
        "name": "Stock Connect (沪港通, 深港通, 港股通)",
        "quotas": "northbound RMB 52bn/day and southbound RMB 42bn/day since 2018-05-01; the "
                  "aggregate quota was abolished on 2016-08-16",
        "disclosure_break": "REAL-TIME NORTHBOUND FLOW DISCLOSURE ENDED ON 2024-08-19. Before "
                            "that date intraday northbound net buying was published live and was "
                            "one of the most-watched series in Asian equities; after it only "
                            "end-of-day turnover totals remain, with holdings quarterly. ANY "
                            "STUDY USING NORTHBOUND FLOW MUST STOP AT THAT DATE or change its "
                            "input, and a backtest that silently continues is using data that no "
                            "longer exists in real time",
    },
}

FISCAL_YEAR: dict[str, str] = {
    "government": "31 December (calendar year)",
    "corporate": "31 December for mainland-listed companies; there is no March fiscal year here "
                 "and no Japanese fiscal-year-end repatriation seasonal to import",
    "budget_cycle": "the budget is approved at the National People's Congress (全国人民代表大会) "
                    "each March, which also sets the growth target and the local-government "
                    "special-bond (专项债) quota; issuance of that quota front-loads into the "
                    "first and third quarters and is a genuine fiscal-impulse calendar",
}
#: The framework's field is a bare MM-DD; FISCAL_YEAR above is why it is this one.
FISCAL_YEAR_END = "12-31"


# --------------------------------------------------------------------------- holidays
_CN_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-01": "元旦 New Year's Day",
        "2024-02-09": "除夕 Spring Festival eve (exchanges closed)",
        "2024-02-12": "春节 Spring Festival",
        "2024-02-13": "春节 Spring Festival",
        "2024-02-14": "春节 Spring Festival",
        "2024-02-15": "春节 Spring Festival",
        "2024-02-16": "春节 Spring Festival",
        "2024-04-04": "清明节 Qingming Festival",
        "2024-04-05": "清明节 Qingming Festival",
        "2024-05-01": "劳动节 Labour Day",
        "2024-05-02": "劳动节 Labour Day",
        "2024-05-03": "劳动节 Labour Day",
        "2024-06-10": "端午节 Dragon Boat Festival",
        "2024-09-16": "中秋节 Mid-Autumn Festival",
        "2024-09-17": "中秋节 Mid-Autumn Festival",
        "2024-10-01": "国庆节 National Day (Golden Week)",
        "2024-10-02": "国庆节 National Day (Golden Week)",
        "2024-10-03": "国庆节 National Day (Golden Week)",
        "2024-10-04": "国庆节 National Day (Golden Week)",
        "2024-10-07": "国庆节 National Day (Golden Week)",
    },
    2025: {
        "2025-01-01": "元旦 New Year's Day",
        "2025-01-28": "除夕 Spring Festival eve",
        "2025-01-29": "春节 Spring Festival (lunar new year day 1)",
        "2025-01-30": "春节 Spring Festival",
        "2025-01-31": "春节 Spring Festival",
        "2025-02-03": "春节 Spring Festival",
        "2025-02-04": "春节 Spring Festival",
        "2025-04-04": "清明节 Qingming Festival",
        "2025-05-01": "劳动节 Labour Day",
        "2025-05-02": "劳动节 Labour Day",
        "2025-05-05": "劳动节 Labour Day",
        "2025-06-02": "端午节 Dragon Boat Festival",
        "2025-10-01": "国庆节 National Day (Golden Week)",
        "2025-10-02": "国庆节 National Day (Golden Week)",
        "2025-10-03": "国庆节 National Day (Golden Week)",
        "2025-10-06": "中秋节 Mid-Autumn Festival, merged into Golden Week",
        "2025-10-07": "国庆节 National Day (Golden Week)",
        "2025-10-08": "国庆节 National Day (Golden Week)",
    },
    2026: {
        "2026-01-01": "元旦 New Year's Day",
        "2026-01-02": "元旦 New Year holiday",
        "2026-02-16": "除夕 Spring Festival eve",
        "2026-02-17": "春节 Spring Festival (lunar new year day 1)",
        "2026-02-18": "春节 Spring Festival",
        "2026-02-19": "春节 Spring Festival",
        "2026-02-20": "春节 Spring Festival",
        "2026-04-06": "清明节 Qingming Festival observed (5 April is a Sunday)",
        "2026-05-01": "劳动节 Labour Day",
        "2026-05-04": "劳动节 Labour Day",
        "2026-05-05": "劳动节 Labour Day",
        "2026-06-19": "端午节 Dragon Boat Festival",
        "2026-09-25": "中秋节 Mid-Autumn Festival",
        "2026-10-01": "国庆节 National Day (Golden Week)",
        "2026-10-02": "国庆节 National Day (Golden Week)",
        "2026-10-05": "国庆节 National Day (Golden Week)",
        "2026-10-06": "国庆节 National Day (Golden Week)",
        "2026-10-07": "国庆节 National Day (Golden Week)",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": (
        "China's closures are GAZETTED ANNUALLY, not derived. The State Council (国务院办公厅) "
        "publishes the next year's arrangement, usually in the preceding autumn, and that notice "
        "is the authority. It fixes seven statutory holidays -- 元旦, 春节, 清明节, 劳动节, "
        "端午节, 中秋节, 国庆节 -- and then EXTENDS them with 调休: adjacent weekends are "
        "declared working days so that the holiday runs as an unbroken block. That means two "
        "things no weekday rule can express: a Saturday or Sunday inside the block is a holiday, "
        "and a Saturday or Sunday just outside it is a TRADING DAY. The lunar anchors (春节 is "
        "the first day of the first lunar month, 端午节 the fifth of the fifth, 中秋节 the "
        "fifteenth of the eighth) and the solar term 清明 cannot be computed from a weekday "
        "rule and are tabulated here. The exchanges publish their own 休市安排 from the State "
        "Council notice and it may differ by a session at the edges."),
    "authority": "国务院办公厅关于节假日安排的通知, plus the SSE and SZSE 休市安排 notices and the "
                 "HKEX Stock Connect trading calendar, which closes northbound trading around "
                 "mainland closures on a schedule of its own",
    "table": _CN_HOLIDAYS,
    "status": {2024: "GAZETTED", 2025: "GAZETTED",
               2026: "DERIVED_FROM_THE_PUBLISHED_ARRANGEMENT -- the lunar anchors (春节 "
                     "2026-02-17, 端午节 2026-06-19, 中秋节 2026-09-25) are certain and the "
                     "block boundaries follow the State Council's usual 调休 pattern. VERIFY "
                     "the exact block against the notice before any event window touches 2026; "
                     "the make-up working weekends in particular cannot be guessed"},
    "market_effect": (
        "USDCNH, HK50 and CHINAH trade THROUGH every mainland closure while the fix, the onshore "
        "spot and the A-share book are shut. This is the pack's single most distinctive "
        "structural fact: for a week at Spring Festival and a week at National Day, the offshore "
        "price of the renminbi is discovered with no onshore counterparty and no fix to anchor "
        "it, and the first mainland session afterwards is where the two reconcile. The closure "
        "is not an absence of data -- it is a REGIME, and the reopening is an event."),
    "callable": "countries.cn.pack:holidays",
}


def holidays(year: int) -> dict[str, str]:
    """The mainland market-closure table for one year. `{}` for an untabulated year."""
    return holiday_table(HOLIDAYS_RULE, year)


def _is_closed(day: date) -> bool:
    """True when the mainland cash market is shut: a weekend or a tabulated closure.

    The 调休 make-up working weekends are NOT modelled -- they would turn a handful of Saturdays
    into trading days, and guessing which ones would be worse than saying so. Any study that
    needs them must read the State Council notice; this function is deliberately conservative.
    """
    return day.weekday() >= 5 or day.isoformat() in holidays(day.year)


def cn_lpr_dates(year: int) -> tuple[str, ...]:
    """The Loan Prime Rate announcement dates for a year, by the 20th-of-the-month rule.

    The LPR is published at 09:15 Beijing (01:15 UTC) on the 20th, and rolled FORWARD to the next
    open day when the 20th is closed. These are the only scheduled, pre-announced, rate-setting
    moments China publishes, so they are what this pack hands the framework as decision anchors.
    A rolled date computed differently from the PBOC's own is a one-session error in every event
    window, which is why `CENTRAL_BANK["verification"]` says to confirm each one.
    """
    out: list[str] = []
    for month in range(1, 13):
        day = date(year, month, 20)
        for _ in range(14):
            if not _is_closed(day):
                break
            day = date.fromordinal(day.toordinal() + 1)
        out.append(day.isoformat())
    return tuple(out)


def cn_long_closures(year: int) -> tuple[dict[str, str], ...]:
    """Every mainland closure of three consecutive days or more, with the session that reopens it.

    This is the object the pack's custom miner measures. A two-day weekend is not a regime; a
    nine-day Spring Festival block during which USDCNH, HK50 and CHINAH trade freely is.
    """
    if not holidays(year):
        return ()
    runs: list[dict[str, str]] = []
    day = date(year, 1, 1)
    end = date(year, 12, 31)
    while day <= end:
        if not _is_closed(day):
            day = date.fromordinal(day.toordinal() + 1)
            continue
        start = day
        while day <= end and _is_closed(day):
            day = date.fromordinal(day.toordinal() + 1)
        length = day.toordinal() - start.toordinal()
        if length >= 3:
            names = {holidays(year).get(date.fromordinal(o).isoformat(), "")
                     for o in range(start.toordinal(), day.toordinal())}
            label = "; ".join(sorted(n for n in names if n)) or "weekend block"
            runs.append({"start": start.isoformat(),
                         "end": date.fromordinal(day.toordinal() - 1).isoformat(),
                         "reopen": day.isoformat(), "days": str(length), "name": label})
    return tuple(runs)


# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"id": "cffex_member_positions",
     "name": "CFFEX 持仓排名 -- top-20 member long and short open interest in IF, IH, IC and IM",
     "covers": "institutional index-futures positioning by clearing member",
     "frequency": "daily", "lag": "same day after the close",
     "root": "cffex.com.cn", "licence": "free, public",
     "note": "A daily institutional positioning series with no Western equivalent. It is by "
             "MEMBER, not by beneficial owner, so a concentrated member is a broker's whole "
             "client book and not one fund -- which is a limitation and not a defect."},
    {"id": "commodity_member_positions",
     "name": "SHFE, DCE, ZCE and INE 持仓排名 -- top-20 member positions, plus 库存 stocks",
     "covers": "copper, aluminium, zinc, nickel, crude, iron ore, soybean positioning and "
               "physical warehouse inventory",
     "frequency": "daily for positions, weekly (Friday) for warehouse stocks",
     "lag": "same day for positions",
     "root": "shfe.com.cn, dce.com.cn, czce.com.cn, ine.cn", "licence": "free, public",
     "note": "THE demand-side positioning read for XCUUSD, XALUSD, XZNUSD, XNIUSD and, through "
             "iron ore, for AUDUSD. Warehouse stocks are the physical-tightness leg."},
    {"id": "margin_financing_balance",
     "name": "融资融券余额 -- margin financing and securities lending balances",
     "covers": "the mainland retail and institutional leverage stock, by exchange and by name",
     "frequency": "daily", "lag": "one business day",
     "root": "sse.com.cn, szse.cn", "licence": "free, public",
     "note": "China's household-leverage gauge. It is RESTRICTED leverage: only eligible "
             "securities may be financed and only qualified investors may do it, so the series "
             "is a policy-bounded quantity and its ceiling moves when the eligible list does."},
    {"id": "connect_flows",
     "name": "Stock Connect northbound and southbound turnover and quota balance",
     "covers": "cross-boundary equity flow between the mainland and Hong Kong",
     "frequency": "daily", "lag": "same day",
     "root": "hkex.com.hk", "licence": "free, public",
     "note": "BROKEN ON 2024-08-19. Real-time northbound flow disclosure ended on that date and "
             "only end-of-day turnover survives, with holdings quarterly. This is the largest "
             "point-in-time break in the pack and it is recorded as a date, not as a caveat."},
    {"id": "safe_fx_settlement",
     "name": "SAFE 银行结售汇 -- bank FX settlement and sales",
     "covers": "the netted corporate and household conversion flow",
     "frequency": "monthly", "lag": "about three weeks",
     "root": "safe.gov.cn", "licence": "free, public",
     "note": "The closest China publishes to an FX flow series. Netted and late, so it is an "
             "ex-post attribution tool and never a signal."},
    {"id": "pboc_reserves",
     "name": "外汇储备 -- official FX reserves",
     "covers": "the headline reserve stock, valuation effects included",
     "frequency": "monthly", "lag": "about seven days",
     "root": "pbc.gov.cn, safe.gov.cn", "licence": "free, public",
     "note": "Valuation moves dominate the monthly change, so the raw print is close to useless "
             "without a currency and duration adjustment the desk would have to build itself."},
    {"id": "ccass_southbound_holdings",
     "name": "CCASS shareholding search -- southbound holdings of Hong Kong names",
     "covers": "mainland ownership of HK-listed shares, by name, daily",
     "frequency": "daily", "lag": "one business day",
     "root": "hkex.com.hk", "licence": "free, public",
     "note": "Survived the 2024 northbound disclosure change; southbound remains observable, "
             "which makes HK50 and CHINAH the better-instrumented half of the Connect story."},
    {"id": "cftc_cot_absent",
     "name": "CFTC Commitments of Traders -- NO CNY OR CNH CONTRACT EXISTS",
     "covers": "nothing Chinese",
     "frequency": "n/a", "lag": "n/a",
     "root": "cftc.gov", "licence": "free, public",
     "note": "DECLARED ABSENT BY NAME. There is no renminbi futures contract in the CFTC's "
             "reports, so a Chinese study has no speculative-positioning series of the kind a "
             "JPY or AUD study takes for granted. The exchange member tables above are the "
             "honest substitute and they measure a different thing."},
)


# --------------------------------------------------------------------------- terminology
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "core": ("人民币", "在岸人民币", "离岸人民币", "汇率", "升值", "贬值", "美元兑人民币",
             "外汇市场", "结汇", "购汇"),
    "cn_fix_and_ccf": ("中间价", "逆周期因子", "一篮子货币", "中国外汇交易中心", "波动区间",
                       "涨跌幅", "定价机制", "破七", "中间价偏离", "指导价"),
    "cn_cnh_cny_basis": ("离岸在岸价差", "香港离岸人民币", "掉期点", "远期汇率", "拆借利率",
                         "流动性收紧", "国有大行", "抛售美元", "外汇风险准备金"),
    "cn_liquidity_ops": ("公开市场操作", "逆回购", "中期借贷便利", "存款准备金率", "降准",
                         "降息", "贷款市场报价利率", "政策利率", "货币政策执行报告",
                         "稳健中性", "适度宽松", "净投放", "净回笼"),
    "cn_credit_impulse": ("社会融资规模", "新增人民币贷款", "信贷脉冲", "居民中长期贷款",
                          "企业中长期贷款", "票据融资", "广义货币", "社融存量同比"),
    "cn_commodity_demand": ("铁矿石", "沪铜", "电解铝", "原油进口", "港口库存", "螺纹钢",
                            "开工率", "采购经理指数", "财新PMI", "制造业PMI", "基建投资",
                            "大宗商品"),
    "cn_connect_flows": ("北向资金", "南向资金", "沪股通", "深股通", "港股通", "陆股通",
                         "外资流入", "外资流出", "额度", "成交额"),
    "cn_property_cycle": ("房地产", "七十城房价", "商品房销售面积", "土地出让金", "保交楼",
                          "三条红线", "按揭利率", "房企违约", "去库存"),
    "cn_policy_calendar": ("中央政治局会议", "全国人民代表大会", "两会", "中央经济工作会议",
                           "政府工作报告", "增长目标", "专项债", "财政赤字率", "国务院常务会议",
                           "政策组合拳"),
    "cn_holiday_asymmetry": ("春节", "国庆黄金周", "清明节", "端午节", "中秋节", "休市安排",
                             "调休", "节后开盘", "跳空", "假期效应"),
    "cn_exchange_microstructure": ("涨停", "跌停", "停牌", "复牌", "集合竞价", "尾盘",
                                   "融资融券", "熔断", "科创板", "创业板", "北交所",
                                   "雪球产品", "两融余额"),
    "cn_state_bank_fx": ("国有大行", "中间价维稳", "干预", "口头引导", "窗口指导",
                         "外汇存款准备金率", "稳汇率"),
    "cn_export_prices": ("出口价格", "生产者价格指数", "产能过剩", "内卷", "出口退税",
                         "转口贸易", "关税", "贸易摩擦"),
    "cn_offshore_funding": ("离岸人民币资金池", "CNH HIBOR", "香港人民币存款", "拆借成本",
                            "流动性收紧", "空头 成本", "远期 掉期点", "离岸 拆息 飙升"),
    "cn_trade_cycle": ("海关总署", "进出口", "贸易顺差", "出口同比", "进口同比", "集装箱运价",
                       "一月二月合并", "春节错位"),
}


# --------------------------------------------------------------------------- source classes
#: GROUNDS THIS PACK REFUSES TO CRAWL, named rather than silently absent, and surfaced in the
#: `source_graph` layer because the edges a graph deliberately does not traverse are part of it.
REFUSED_SOURCES: tuple[dict[str, str], ...] = (
    {"ground": "crypto-exchange order books, venue APIs and venue-native feeds",
     "why": "MT5 universe mandate (2026-08-18): no crypto-exchange ground is ever hunted again"},
    {"ground": "CSMAR (国泰安), RESSET and Wind terminal data",
     "why": "LICENSED and not subscribed on this desk. Named so the gap is visible: these are "
            "the standard Chinese academic panels and every paper this pack reads was built on "
            "one of them, which the desk cannot replicate"},
    {"ground": "CNKI and Wanfang full text behind the paywall",
     "why": "licence; abstracts and figures are free and are what this pack reads"},
    {"ground": "single-name mainland equity hypothesis mining",
     "why": "two-lane order (2026-09-06): single names are traded on news and never hunted for "
            "statistical hypotheses"},
)

SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    source_class("cn_official", "The PBOC, CFETS, SAFE, the statistics bureau and customs",
                 layer="official",
                 roots=("pbc.gov.cn", "chinamoney.com.cn", "safe.gov.cn", "stats.gov.cn",
                        "data.stats.gov.cn", "customs.gov.cn", "mof.gov.cn", "ndrc.gov.cn"),
                 queries=("人民币汇率中间价", "公开市场业务交易公告", "贷款市场报价利率",
                          "存款准备金率", "货币政策执行报告", "社会融资规模", "银行结售汇",
                          "进出口商品总值", "采购经理指数", "外汇风险准备金率"),
                 languages=("zh-Hans", "en"), access_label="OPEN_DATA",
                 credibility="AUTHORITATIVE", predictive_state="UNTESTED",
                 licence="free, public",
                 notes="chinamoney.com.cn is the authoritative root for the central parity and "
                       "the CFETS closes -- the two inputs the fix formula actually uses. Note "
                       "that the January and February trade and activity data are published "
                       "COMBINED, which is two missing observations a year by design."),
    source_class("cn_institutional", "The exchanges, the Connect operator and the industry bodies",
                 layer="institutional",
                 roots=("sse.com.cn", "szse.cn", "cffex.com.cn", "shfe.com.cn", "dce.com.cn",
                        "czce.com.cn", "ine.cn", "hkex.com.hk", "chinaclear.cn",
                        "amac.org.cn (中国证券投资基金业协会)"),
                 queries=("持仓排名", "库存日报", "融资融券余额", "沪股通 深股通 成交额",
                          "港股通 持股", "期货持仓龙虎榜", "交割结算价", "私募基金备案"),
                 languages=("zh-Hans", "zh-Hant", "en"), access_label="OPEN_DATA",
                 credibility="AUTHORITATIVE", predictive_state="UNTESTED",
                 licence="free, public",
                 notes="The daily 持仓排名 member tables and the weekly 库存 stocks are the "
                       "highest-value free positioning data anywhere in this package. Since "
                       "2024-08-19 the northbound real-time flow is gone and only end-of-day "
                       "turnover survives -- the row records where the series stops being live."),
    source_class("cn_academic", "Chinese journals, theses and the working-paper literature",
                 layer="academic",
                 roots=("cnki.net", "wanfangdata.com.cn", "cqvip.com", "papers.ssrn.com",
                        "nber.org China working papers", "pbcsf.tsinghua.edu.cn"),
                 queries=("人民币汇率中间价 逆周期因子", "涨跌停 流动性", "T+1 交易制度 效应",
                          "北向资金 定价效率", "社会融资规模 领先指标", "雪球产品 敲入",
                          "股指期货 基差"),
                 languages=("zh-Hans", "en"), access_label="LICENSED",
                 credibility="RELIABLE", predictive_state="UNTESTED",
                 licence="CNKI and Wanfang full text is LICENSED and the desk holds no licence; "
                         "abstracts, figures and titles are free and are what is read",
                 notes="The Chinese microstructure literature on T+1 and the price limit is far "
                       "deeper than the English one and it is almost entirely invisible to an "
                       "English-language search. The standard panels it is built on (CSMAR, "
                       "RESSET) are in REFUSED_SOURCES because the desk cannot licence them."),
    source_class("cn_practitioner", "The deep-forest practitioner ground (principal's standing "
                                    "order, 2026-09-04)",
                 layer="practitioner",
                 roots=("qhrb.com.cn (期货日报)", "7hcn.com (七禾网)", "simuwang.com (私募排排网)",
                        "joinquant.com (聚宽)", "uqer.io (优矿)", "ricequant.com (米筐)",
                        "bigquant.com", "gitee.com", "csdn.net"),
                 queries=("期货日报实盘大赛", "蓝海密剑", "七禾网 访谈", "私募排排网 排名",
                          "聚宽 策略", "米筐 回测", "BigQuant 因子", "量化交易 策略源码",
                          "多因子模型 代码", "日内 波段 策略"),
                 languages=("zh-Hans",), access_label="PUBLIC_WITH_TERMS",
                 credibility="UNRELIABLE", predictive_state="UNTESTED",
                 licence="public web and per-repository licences; mined for VERBATIM CLAIMS "
                         "only, respecting robots and rate limits",
                 notes="THE GROUND THE PRINCIPAL NAMED BY NAME. 期货日报实盘大赛 and 蓝海密剑 "
                       "are competition records with dated track records and named instruments; "
                       "七禾网 and 私募排排网 carry trader interviews in which a mechanism is "
                       "stated plainly. Credibility is UNRELIABLE and every row is kept at LOW "
                       "WEIGHT rather than dropped -- even a dubious trader story names a "
                       "testable mechanism, which is the entire reason to mine it."),
    source_class("cn_retail_ecology", "The mainland retail boards and their vernacular",
                 layer="retail_ecology",
                 roots=("xueqiu.com (雪球)", "zhihu.com (知乎)", "jisilu.cn (集思录)",
                        "guba.eastmoney.com (股吧)", "tieba.baidu.com (股市吧)"),
                 queries=("北向资金 流入", "牛市 来了", "割韭菜", "抄底", "跌停 板上",
                          "两融 爆仓", "雪球 敲入", "国家队 进场", "小作文"),
                 languages=("zh-Hans",), access_label="PUBLIC_SOCIAL",
                 credibility="FRINGE", predictive_state="UNTESTED",
                 licence="public web; VERBATIM CLAIMS only, never personal data, respecting "
                         "robots and rate limits",
                 notes="FRINGE AND KEPT AT LOW WEIGHT, never dropped. 小作文 -- the unverified "
                       "policy rumour that circulates before an announcement -- is the clearest "
                       "case in this package of material that is frequently FALSE and still "
                       "worth recording, because the DATE it appeared is itself the observable."),
    source_class("cn_app_ecosystem", "Mainland trading and information apps, and 微信 公众号",
                 layer="app_ecosystem",
                 roots=("weixin.sogou.com (微信公众号 search)",
                        "app listings and review text for the major mainland brokerage apps",
                        "questmobile.com.cn and analysys.cn app panels"),
                 queries=("同花顺 使用", "东方财富 app", "券商 开户 数", "微信公众号 量化",
                          "股票 app 日活", "开户 数量 激增"),
                 languages=("zh-Hans",), access_label="ACCESS_UNCLEAR",
                 credibility="UNKNOWN", predictive_state="UNTESTED",
                 licence="搜狗微信 search results are public; the app panels are VENDOR products "
                         "the desk does not subscribe to, and several app stores restrict "
                         "machine extraction",
                 machine_use_allowed=True,
                 notes="REGISTERED AND NOT SCRAPED. 微信 via 搜狗 is named in the principal's "
                       "deep-forest order and is genuinely the only public window onto the "
                       "公众号 corpus, where a great deal of mainland practitioner writing "
                       "lives. The terms are restrictive and the panels are licensed, so this "
                       "row records the ground, the reason, and the refusal -- rather than "
                       "leaving a hole that looks like the layer does not exist."),
    source_class("cn_media", "The mainland financial press",
                 layer="media",
                 roots=("caixin.com (财新)", "yicai.com (第一财经)", "stcn.com (证券时报)",
                        "cnstock.com (上海证券报)", "cs.com.cn", "jiemian.com",
                        "xinhuanet.com (policy readouts)"),
                 queries=("中央政治局会议", "中央经济工作会议", "政府工作报告 增长目标",
                          "稳健中性", "适度宽松", "逆周期调节", "稳汇率", "政策组合拳"),
                 languages=("zh-Hans",), access_label="PUBLIC_WITH_TERMS",
                 credibility="RELIABLE", predictive_state="NARRATIVE_FEATURE",
                 licence="public headlines and article text; respect robots and rate limits",
                 notes="NARRATIVE_FEATURE ON PURPOSE. The policy-language shifts the domestic "
                       "market trades -- 稳健中性 to 适度宽松 -- appear in the state readouts "
                       "carried here before the quarterly report restates them. The words are a "
                       "conditioning variable and not a forecast."),
    source_class("cn_archive", "Historical notices, gazettes and web archives",
                 layer="archive",
                 roots=("web.archive.org", "gov.cn 国务院办公厅 节假日安排 notice archive",
                        "sse.com.cn and szse.cn historical 休市安排 and rule notices",
                        "pbc.gov.cn historical 货币政策执行报告"),
                 queries=("国务院办公厅 节假日安排 通知", "休市安排 公告", "调休 安排",
                          "熔断机制 暂停", "涨跌幅 调整", "沪深港通 交易日历"),
                 languages=("zh-Hans",), access_label="PUBLIC_ARCHIVE",
                 credibility="AUTHORITATIVE", predictive_state="UNTESTED",
                 licence="free, public",
                 notes="THE LAYER THAT MAKES THIS PACK'S HOLIDAY TABLE CHECKABLE. China's "
                       "closures are gazetted annually and the 调休 make-up working weekends "
                       "cannot be derived from any rule -- so the only way to be right about a "
                       "Chinese calendar is to read the notice for that year, and this is where "
                       "the old ones live. The 2016 four-day circuit breaker is here too."),
    source_class("cn_physical_economy", "Ports, power, freight and the physical demand machine",
                 layer="physical_economy",
                 roots=("sse.net.cn (上海航运交易所, SCFI and CCFI freight indices)",
                        "shfe.com.cn and dce.com.cn 库存 warehouse stocks",
                        "cec.org.cn (中国电力企业联合会 power generation)",
                        "chineseport.cn and the major port authority pages",
                        "stats.gov.cn 工业增加值 and 发电量"),
                 queries=("港口 铁矿石 库存", "集装箱运价指数", "发电量 同比", "高炉开工率",
                          "水泥 出货率", "螺纹钢 表观消费", "原油 到港量"),
                 languages=("zh-Hans",), access_label="PUBLIC_WITH_TERMS",
                 credibility="RELIABLE", predictive_state="UNTESTED",
                 licence="the exchange stocks and the official series are free; Mysteel and the "
                         "commercial port trackers are LICENSED and are not subscribed here",
                 notes="THE LAYER THAT MATTERS MOST FOR THIS PACK'S EXECUTABLE EDGES. AUDUSD, "
                       "AUS200 and XCUUSD are moved by Chinese physical demand, and port stocks "
                       "and blast-furnace rates lead the monthly customs data by weeks. The "
                       "licensed trackers (Mysteel above all) are the standard tool and the desk "
                       "does not have them, which is a named gap rather than a silent one."),
    source_class("cn_source_graph", "How new Chinese grounds are found, and what is refused",
                 layer="source_graph",
                 roots=("cnki.net citation graph", "gitee.com and github.com topic graphs for "
                        "Chinese market-data packages", "weixin.sogou.com result graph",
                        "xueqiu.com and zhihu.com link structure"),
                 queries=("量化 数据接口", "A股 数据 下载", "tushare", "akshare",
                          "期货 数据 接口", "爬虫 财经 数据"),
                 languages=("zh-Hans",), access_label="PUBLIC_WITH_TERMS",
                 credibility="UNKNOWN", predictive_state="UNTESTED",
                 licence="public web; several of these restrict automated querying and are used "
                         "at human rates or not at all",
                 notes=f"THE META LAYER: it finds the next ground rather than data. Open-source "
                       f"Chinese market-data packages are the fastest route to a new endpoint, "
                       f"because a package that already reads a series is a map of where that "
                       f"series lives. This layer also carries what the graph REFUSES to "
                       f"traverse: {'; '.join(r['ground'] for r in REFUSED_SOURCES)}. Reasons "
                       f"are in REFUSED_SOURCES and none of those grounds is named, subscribed "
                       f"or crawled anywhere in this pack."),
)


# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    dataset("cfets_central_parity",
            source="中国外汇交易中心 (CFETS) 人民币汇率中间价",
            coverage="the daily USD/CNY central parity and the CFETS basket indices",
            frequency="daily",
            publication_lag_days=0.0,
            revisions="none",
            licence="free, public",
            history_from="2006-01",
            pit_feasible=True,
            assets=("USDCNH", "HK50", "CHINAH"),
            mechanism_families=("fixing", "policy_guidance", "band"),
            how_to_fetch="chinamoney.com.cn, published 09:15 Beijing = 01:15 UTC, fifteen "
                         "minutes before the onshore market opens"),
    dataset("cfets_onshore_close",
            source="CFETS 收盘价",
            coverage="the 16:30 Beijing onshore closing rate that feeds the next day's fix",
            frequency="daily",
            publication_lag_days=0.0,
            revisions="none",
            licence="free, public",
            history_from="2006-01",
            pit_feasible=True,
            assets=("USDCNH",),
            mechanism_families=("fixing", "onshore_offshore_basis"),
            how_to_fetch="chinamoney.com.cn; 08:30 UTC. Do NOT substitute the 23:30 Beijing "
                         "close: the fix formula uses the 16:30 one"),
    dataset("cn_cnh_cny_basis",
            source="derived: the CFETS onshore close against the broker's own USDCNH tape",
            coverage="the offshore-minus-onshore spread in pips, daily",
            frequency="daily",
            publication_lag_days=0.0,
            revisions="none",
            licence="free (the onshore leg) plus the desk's own tape (the offshore leg)",
            history_from="2010-08",
            pit_feasible=True,
            assets=("USDCNH", "HK50", "CHINAH"),
            mechanism_families=("onshore_offshore_basis", "intervention_proxy",
                                "capital_control_stress"),
            how_to_fetch="computed on this desk; both legs are held here, which makes this one "
                         "of the few China observables that is genuinely point-in-time safe"),
    dataset("pboc_omo_daily",
            source="中国人民银行 公开市场业务交易公告",
            coverage="the daily reverse-repo operation size, tenor and rate, and the net "
                     "injection or drain after maturities",
            frequency="daily",
            publication_lag_days=0.0,
            revisions="none",
            licence="free, public",
            history_from="2013-01",
            pit_feasible=True,
            assets=("USDCNH", "HK50", "CHINAH"),
            mechanism_families=("liquidity", "policy_rate"),
            how_to_fetch="pbc.gov.cn announcements at about 09:20 Beijing = 01:20 UTC"),
    dataset("pboc_lpr",
            source="全国银行间同业拆借中心 贷款市场报价利率",
            coverage="the 1-year and 5-year Loan Prime Rate",
            frequency="monthly",
            publication_lag_days=0.0,
            revisions="none",
            licence="free, public",
            history_from="2019-08",
            pit_feasible=True,
            assets=("USDCNH", "HK50", "CHINAH", "XCUUSD"),
            mechanism_families=("policy_rate", "policy_surprise"),
            how_to_fetch="09:15 Beijing (01:15 UTC) on the 20th, rolled forward off closures; "
                         "cn_lpr_dates() computes the grid and the PBOC archive confirms it"),
    dataset("pboc_mlf_and_rrr",
            source="中国人民银行 中期借贷便利 and 存款准备金率 announcements",
            coverage="MLF operation size and rate; reserve-requirement changes and their "
                     "effective dates",
            frequency="monthly for MLF, event for RRR",
            publication_lag_days=0.0,
            revisions="none",
            licence="free, public",
            history_from="2014-09",
            pit_feasible=True,
            assets=("USDCNH", "HK50", "CHINAH", "AUDUSD"),
            mechanism_families=("liquidity", "policy_surprise"),
            how_to_fetch="pbc.gov.cn. NOTE THE BREAK: the MLF moved from the 15th to the 25th in "
                         "July 2024 and was demoted when the 7-day reverse repo became the "
                         "primary policy rate on 2024-07-22 -- an MLF event study pooled across "
                         "that date is pooling a policy rate with a liquidity operation"),
    dataset("nbs_pmi",
            source="国家统计局 制造业和非制造业采购经理指数",
            coverage="official manufacturing and non-manufacturing PMI with sub-indices",
            frequency="monthly",
            publication_lag_days=0.0,
            revisions="none to the headline; seasonal factors are re-estimated annually",
            licence="free, public",
            history_from="2005-01",
            pit_feasible=True,
            assets=("AUDUSD", "AUS200", "XCUUSD", "HK50", "CHINAH", "USDCNH"),
            mechanism_families=("macro_surprise", "commodity_demand", "growth_nowcast"),
            how_to_fetch="stats.gov.cn at 09:00 Beijing (01:00 UTC) on the last day of the "
                         "month; the Caixin manufacturing PMI follows at 09:45 Beijing "
                         "(01:45 UTC) on the first business day and is a LICENSED series whose "
                         "headline is reported publicly"),
    dataset("cn_customs_trade",
            source="海关总署 进出口商品总值",
            coverage="exports, imports and the trade balance, by product and by partner",
            frequency="monthly, with JANUARY AND FEBRUARY PUBLISHED COMBINED",
            publication_lag_days=9.0,
            revisions="minor",
            licence="free, public",
            history_from="1995-01",
            pit_feasible=True,
            assets=("AUDUSD", "AUS200", "XCUUSD", "XTIUSD", "USDCNH"),
            mechanism_families=("trade_cycle", "commodity_demand", "global_growth"),
            how_to_fetch="customs.gov.cn between the 7th and the 13th. THE COMBINED JANUARY AND "
                         "FEBRUARY RELEASE IS A PIT TRAP: two monthly observations are missing "
                         "every year by design and interpolating them invents data"),
    dataset("pboc_tsf_credit",
            source="中国人民银行 金融统计数据报告 (社会融资规模, 新增人民币贷款)",
            coverage="total social financing, new loans, M2 and the credit aggregates",
            frequency="monthly",
            publication_lag_days=12.0,
            revisions="the TSF stock series has been restated when its definition widened",
            licence="free, public",
            history_from="2002-01",
            pit_feasible=False,
            assets=("AUDUSD", "AUS200", "XCUUSD", "HK50", "CHINAH"),
            mechanism_families=("credit_impulse", "growth_nowcast", "commodity_demand"),
            how_to_fetch="pbc.gov.cn between the 9th and the 15th with NO PRE-ANNOUNCED TIME. "
                         "pit_feasible is FALSE for two reasons: the release minute is unknown "
                         "in advance, and the definition of TSF has widened more than once so "
                         "the historical series is not the series that was published then"),
    dataset("cn_property",
            source="国家统计局 七十个大中城市住宅销售价格 and 房地产开发投资",
            coverage="new and second-hand home prices in 70 cities, sales area, starts, and "
                     "developer investment",
            frequency="monthly",
            publication_lag_days=16.0,
            revisions="minor",
            licence="free, public",
            history_from="2011-01",
            pit_feasible=True,
            assets=("AUDUSD", "XCUUSD", "HK50", "CHINAH"),
            mechanism_families=("property_cycle", "commodity_demand", "credit_impulse"),
            how_to_fetch="stats.gov.cn, around the 15th to the 17th"),
    dataset("connect_flows",
            source="HKEX Stock Connect daily statistics",
            coverage="northbound and southbound turnover, quota balance, and southbound holdings",
            frequency="daily",
            publication_lag_days=0.4,
            revisions="none",
            licence="free, public",
            history_from="2014-11",
            pit_feasible=True,
            assets=("HK50", "CHINAH", "USDCNH"),
            mechanism_families=("foreign_flow", "capital_account", "risk_appetite"),
            how_to_fetch="hkex.com.hk. BROKEN 2024-08-19: real-time northbound flow disclosure "
                         "ended on that date and only end-of-day turnover survives, with "
                         "holdings quarterly. A northbound-flow strategy backtested across that "
                         "date is using an input that no longer exists live"),
    dataset("cn_commodity_positions",
            source="SHFE, DCE, ZCE and INE 持仓排名 and 库存",
            coverage="top-20 member long and short open interest, and weekly warehouse stocks",
            frequency="daily for positions, weekly for stocks",
            publication_lag_days=0.5,
            revisions="none",
            licence="free, public",
            history_from="2010-01",
            pit_feasible=True,
            assets=("XCUUSD", "XALUSD", "XZNUSD", "XNIUSD", "AUDUSD", "SOYBEAN"),
            mechanism_families=("positioning", "physical_tightness", "commodity_demand"),
            how_to_fetch="each exchange's daily bulletin pages; by MEMBER rather than by "
                         "beneficial owner, which is a limitation to state, not to hide"),
    dataset("cn_policy_calendar",
            source="新华社 and 国务院 announcements",
            coverage="Politburo economic meetings (中央政治局会议), the NPC (两会) each March, "
                     "the Central Economic Work Conference (中央经济工作会议) each December, and "
                     "State Council executive meetings",
            frequency="event",
            publication_lag_days=0.0,
            revisions="none",
            licence="free, public",
            history_from="2010-01",
            pit_feasible=False,
            assets=("HK50", "CHINAH", "AUDUSD", "XCUUSD"),
            mechanism_families=("policy_event", "text_signal", "risk_appetite"),
            how_to_fetch="state media readouts. pit_feasible is FALSE for the April, July and "
                         "December Politburo economic meetings because the DATE is not announced "
                         "in advance -- only the month is -- so the event window itself is not "
                         "knowable ex ante and a study must condition on the announcement time"),
    dataset("cn_fx_risk_reserve",
            source="中国人民银行 外汇风险准备金率 and 外汇存款准备金率 announcements",
            coverage="the reserve requirement on bank forward FX sales (moved between 0% and "
                     "20%) and on FX deposits",
            frequency="event",
            publication_lag_days=0.0,
            revisions="none",
            licence="free, public",
            history_from="2015-10",
            pit_feasible=True,
            assets=("USDCNH",),
            mechanism_families=("intervention_proxy", "forward_points", "policy_surprise"),
            how_to_fetch="pbc.gov.cn. These are the cleanest DATED interventions China publishes "
                         "-- a rule change with an announcement minute and a stated effect on "
                         "the cost of hedging, which is what an event study needs"),
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    actor("中国人民银行 -- the People's Bank of China as the price setter",
          holds="the largest official FX reserve stock in the world and the authority to set the "
                "daily reference rate the onshore market must trade around",
          forced_to=("publish a central parity every business day at 09:15 Beijing, whatever the "
                     "overnight move was",
                     "defend the credibility of the band without appearing to target a level",
                     "reconcile an exchange-rate objective with a domestic-liquidity objective "
                     "that frequently points the other way"),
          when="every business day at 01:15 UTC for the fix; monthly on the 20th for the LPR; "
               "ad hoc for RRR and the FX reserve requirements",
          information=("the true onshore order flow before anyone else sees it",
                       "state-bank instructions it has itself issued",
                       "the counter-cyclical factor it applies and does not publish"),
          constraints=("a 2% band on the onshore price, which is a commitment it has never broken",
                       "a capital account it must not be seen to tighten abruptly",
                       "the political cost of a visible devaluation"),
          instruments=("the central parity itself", "reverse repos and the MLF",
                       "the reserve requirement ratio", "the FX risk reserve on forward sales",
                       "guidance to the large state banks"),
          counterparties=("the large state commercial banks", "the offshore CNH market",
                          "exporters and importers through 结售汇"),
          observables=("the fix against a model of previous close plus basket move -- the "
                       "RESIDUAL is the guidance",
                       "the daily OMO net injection or drain",
                       "the monthly reserve print, dominated by valuation"),
          impact="the fix anchors the onshore session and bounds it; the offshore price is free "
                 "but tethered by arbitrage and by the state banks, so the fix propagates into "
                 "USDCNH within minutes of 01:15 UTC",
          persistence="the managed-float framework has been stable since 2015-08-11 in form, "
                      "though the counter-cyclical factor has been switched on and off twice",
          falsifier="if the residual between the actual fix and a previous-close-plus-basket "
                    "model carries no information for the USDCNH return over the following "
                    "session, the guidance is either absent or fully anticipated, and the "
                    "central mechanism of this pack is not tradable",
          notes="This is the only actor in the package that sets a price by announcement. "
                "Everything else in China reacts to it."),
    actor("国有大型商业银行 -- the large state commercial banks",
          holds="the onshore dollar book of the state, and the ability to transact in size "
                "without disclosing a principal",
          forced_to=("act on window guidance when it is given",
                     "intermediate the entire onshore corporate conversion flow",
                     "manage their own regulatory FX positions while doing so"),
          when="in the onshore session, most visibly in the minutes after the fix and into the "
               "16:30 Beijing close on stressed days",
          information=("guidance from the authorities before the market sees its effects",
                       "aggregate client conversion demand"),
          constraints=("regulatory net open position limits",
                       "the requirement not to look like the central bank",
                       "their own funding costs offshore"),
          instruments=("onshore USDCNY spot and swaps", "offshore CNH through their HK branches",
                       "forward sales to corporates"),
          counterparties=("the PBOC", "exporters and importers", "offshore banks in the CNH "
                          "market"),
          observables=("a sharp reversal in the onshore rate with no news, late in the session",
                       "the CNH-CNY gap closing abruptly",
                       "offshore CNH funding costs jumping"),
          impact="they are the operational hands of the intervention that is never announced; "
                 "their footprint is visible as a price pattern and never as a disclosure",
          persistence="structural while the state owns the banking system",
          falsifier="if USDCNH shows no distinguishable reversal behaviour in the final onshore "
                    "hour on days when the currency has weakened sharply, relative to matched "
                    "days with the same morning move, the state-bank channel is not detectable "
                    "from price alone and this actor is UNMEASURED rather than absent",
          notes="Detectable only as a pattern. The pack says so rather than claiming a data "
                "source it does not have."),
    actor("出口企业 -- Chinese exporters",
          holds="dollar receivables from the world's largest goods export book",
          forced_to=("convert dollars into renminbi to pay domestic costs, under 结售汇 rules "
                     "that require documented trade need",
                     "decide how much to hold in dollar deposits instead of converting -- a "
                     "decision that is itself a view on the currency"),
          when="month end, quarter end, and heavily before the Spring Festival when wages and "
               "bonuses are paid",
          information=("their own order books before they appear in customs data"),
          constraints=("documentation requirements on conversion",
                       "domestic cost obligations in renminbi that cannot be deferred",
                       "limits on holding foreign currency deposits"),
          instruments=("onshore spot conversion", "forward sales, whose cost the PBOC changes "
                       "directly through the FX risk reserve"),
          counterparties=("the large state banks", "their overseas customers"),
          observables=("SAFE 银行结售汇 monthly",
                       "the foreign-currency deposit stock at banks",
                       "customs export values, monthly with January and February combined"),
          impact="a structural renminbi bid that is elastic to the exchange-rate LEVEL: when "
                 "exporters expect depreciation they hold dollars, which removes the bid exactly "
                 "when it is most needed, and that reflexivity is the mechanism worth testing",
          persistence="structural; the elasticity changes with expectations and with the "
                      "documentation regime",
          falsifier="if changes in the bank foreign-currency deposit stock carry no information "
                    "for the following month's USDCNH path, after controlling for the dollar and "
                    "the rate differential, the withheld-conversion channel is not reaching price",
          notes="The Spring Festival cluster is the largest single seasonal renminbi demand of "
                "the year and it MOVES, because the festival is lunar."),
    actor("北向资金 -- foreign investors through Stock Connect northbound",
          holds="mainland A-share positions held through the Hong Kong link",
          forced_to=("fund purchases in offshore renminbi obtained in Hong Kong",
                     "track global benchmarks through index reviews",
                     "settle securities on T and cash on T+1, a mismatch they must bridge"),
          when="continuously in the mainland session; concentrated at index review effective "
               "dates and at global risk turns",
          information=("index-provider consultations and effective dates, published in advance"),
          constraints=("a daily quota of RMB 52bn",
                       "Connect trading is closed on days when either market is shut, on a "
                       "calendar of its own",
                       "SINCE 2024-08-19 THEY CAN NO LONGER SEE EACH OTHER'S INTRADAY FLOW, "
                       "which changed the crowding dynamic they were part of"),
          instruments=("A shares through the link", "offshore CNH for the funding leg",
                       "HK50 and CHINAH as the liquid hedge"),
          counterparties=("mainland investors on the other side", "HKEX as the operator"),
          observables=("daily northbound turnover (real-time flow ended 2024-08-19)",
                       "quota balance", "quarterly holdings"),
          impact="a marginal price setter in the largest A-share names and a persistent offshore "
                 "CNH demand; the 2024 disclosure change is a natural experiment in whether "
                 "watching a flow makes the flow matter",
          persistence="structural while the link exists; the observability is NOT persistent and "
                      "has already broken once",
          falsifier="if northbound turnover has no relation to CHINAH or HK50 returns at any lag "
                    "out to five sessions, after controlling for the global equity move, the "
                    "flow is not marginal and the series is decoration",
          notes="The cleanest dated observability break in the package."),
    actor("南向资金 -- mainland investors buying Hong Kong through southbound",
          holds="Hong Kong-listed shares bought with renminbi converted at the link",
          forced_to=("convert renminbi into Hong Kong dollars to settle",
                     "operate within a daily quota",
                     "accept the A-H price difference as given, because the two lines are not "
                     "fungible"),
          when="continuously; surges when mainland yields fall and when the A-H premium is wide",
          information=("mainland retail and institutional sentiment before it shows in A shares"),
          constraints=("the RMB 42bn daily quota",
                       "eligibility rules on which HK names may be bought",
                       "a dividend tax treatment that differs from the A line"),
          instruments=("HK-listed shares through the link", "HKD conversion at settlement"),
          counterparties=("Hong Kong market makers", "foreign holders selling to them"),
          observables=("daily southbound turnover and holdings, both still published",
                       "CCASS shareholding by participant",
                       "the Hang Seng A-H premium index"),
          impact="the marginal buyer of Hong Kong equity in recent years, and a structural HKD "
                 "demand that pushes USDHKD toward the strong side of the peg",
          persistence="structural and growing while mainland domestic yields stay low",
          falsifier="if southbound turnover carries no information for HK50 or CHINAH returns "
                    "and no relation to the USDHKD band position, the mainland bid is not "
                    "marginal in either market",
          notes="This actor is the mechanical link between the CN pack and the HK pack, and it "
                "is the reason the two packs share edges rather than merely correlate."),
    actor("地方政府和融资平台 -- local governments and their financing vehicles",
          holds="the land-sale revenue base and the infrastructure investment programme, funded "
                "by special bonds and off-balance-sheet vehicles",
          forced_to=("issue within an annual quota set at the NPC",
                     "front-load issuance when instructed",
                     "fund committed projects even as land revenue falls"),
          when="the special-bond quota is set in March and issuance front-loads into the first "
               "and third quarters",
          information=("their own project pipeline and their own fiscal stress"),
          constraints=("the annual quota", "debt-resolution rules that have tightened repeatedly",
                       "a land market that no longer funds them"),
          instruments=("special bonds (专项债)", "infrastructure contracts that become steel, "
                       "copper and cement demand"),
          counterparties=("policy banks and commercial banks as buyers",
                          "construction and materials suppliers"),
          observables=("monthly special-bond issuance",
                       "fixed-asset investment in infrastructure",
                       "land-sale revenue in the fiscal data"),
          impact="the transmission from a policy announcement to physical commodity demand runs "
                 "through this actor, with a lag of one to two quarters -- which is why a "
                 "stimulus headline moves XCUUSD immediately and the physical data much later",
          persistence="structural, but the funding model is under active reform and the "
                      "elasticity of commodity demand to a quota has fallen",
          falsifier="if special-bond issuance has no relation to XCUUSD or AUDUSD returns at any "
                    "lag out to two quarters, after controlling for the global cycle, the "
                    "fiscal-to-commodity channel is not measurable at this frequency",
          notes="This is the actor most responsible for the AUDUSD and AUS200 edges."),
    actor("房地产开发商 -- property developers",
          holds="land banks, pre-sold unfinished housing obligations and offshore dollar debt",
          forced_to=("complete pre-sold projects under 保交楼 obligations",
                     "service or default on offshore bonds",
                     "sell inventory into a falling market to raise cash"),
          when="bond maturity dates; quarterly reporting; the spring and autumn selling seasons",
          information=("their own liquidity position well before a default"),
          constraints=("the 三条红线 leverage thresholds, introduced 2020-08",
                       "pre-sale escrow rules that trap cash at the project level",
                       "no access to offshore refinancing once distressed"),
          instruments=("offshore dollar bonds", "domestic bonds and trust products",
                       "physical land and housing"),
          counterparties=("offshore bond holders", "mainland banks", "local governments as "
                          "land sellers", "households as pre-buyers"),
          observables=("70-city price index, monthly",
                       "sales area and starts, monthly",
                       "offshore high-yield property bond prices, where a public quote exists"),
          impact="the property cycle is the largest single determinant of Chinese steel, copper "
                 "and cement demand, so a developer credit event transmits to AUDUSD and XCUUSD "
                 "through an expectation channel long before it shows in physical data",
          persistence="the deleveraging is structural and multi-year; the ACUTE credit-event "
                      "regime began in 2021 and its end is a live question",
          falsifier="if AUDUSD and XCUUSD show no abnormal move around dated developer credit "
                    "events, relative to matched days, the expectation channel is not operating "
                    "and only the physical data matters",
          notes="Single-name developers are OBSERVABLES here and never hypothesis ground."),
    actor("中国大宗商品买家 -- Chinese commodity importers and stockpilers",
          holds="the world's largest import requirement in iron ore, copper, soybeans and crude",
          forced_to=("import continuously because domestic resources do not meet demand",
                     "build strategic reserves when policy directs",
                     "hedge or not hedge against a domestic futures curve rather than a "
                     "Western one"),
          when="continuously; stockpiling is opportunistic and price-elastic, which is why "
               "Chinese buying puts a FLOOR under commodity prices rather than a trend",
          information=("port inventories and domestic demand weeks before the monthly data"),
          constraints=("port and warehouse capacity",
                       "state reserve policy they do not set",
                       "domestic price controls on some inputs"),
          instruments=("physical cargoes", "SHFE, DCE and INE futures",
                       "the offshore benchmarks these price against"),
          counterparties=("Australian and Brazilian miners", "global oil producers",
                          "American and Brazilian farmers"),
          observables=("customs import volumes, monthly with January and February combined",
                       "port stocks and exchange warehouse inventory, weekly",
                       "the daily member position tables at the four exchanges"),
          impact="Chinese demand is the price-setting marginal buyer in iron ore and copper, and "
                 "the executable expressions are AUDUSD, AUS200 and XCUUSD rather than anything "
                 "Chinese",
          persistence="structural, though the intensity of commodity demand per unit of GDP is "
                      "falling as the economy shifts away from construction",
          falsifier="if monthly Chinese import volumes and weekly port stocks carry no "
                    "information for AUDUSD or XCUUSD after controlling for the dollar and the "
                    "global cycle, the demand channel is priced entirely in advance",
          notes="This actor is why an Australian instrument belongs in a Chinese pack."),
    actor("中国散户投资者 -- mainland retail investors",
          holds="the majority of A-share turnover, financed partly by 融资融券 margin",
          forced_to=("close positions when a margin call arrives",
                     "wait a full session before selling anything bought today, because "
                     "settlement is T+1"),
          when="the T+1 rule concentrates exits at the OPEN; margin calls execute in the morning "
               "session",
          information=("nothing the market does not have; constraint-rich and information-poor, "
                       "which is what makes the behaviour predictable"),
          constraints=("T+1 settlement, which forbids intraday round trips",
                       "the +/-10% limit, which queues rather than clears an imbalance",
                       "an eligible-securities list that bounds what may be financed at all"),
          instruments=("A shares", "margin financing", "structured products sold to them"),
          counterparties=("brokers as lenders", "institutional investors on the other side"),
          observables=("融资融券余额 daily",
                       "new account openings, monthly",
                       "turnover concentration in small caps"),
          impact="T+1 plus a price limit means an imbalance is expressed as a QUEUE rather than "
                 "a price, so the information arrives at the next open -- the mainland market's "
                 "overnight gap is a settlement rule, not a news effect",
          persistence="structural while T+1 and the limit remain; both have been debated and "
                      "neither has changed",
          falsifier="if the distribution of A-share overnight gaps is indistinguishable from "
                    "that of a T+0 market with the same volatility, the settlement rule is not "
                    "shaping the price path and this actor's mechanism is absent",
          notes="Mainland indices are not quoted here, so this actor reaches the book only "
                "through CHINAH, HK50 and the southbound flow."),
    actor("雪球产品发行商 -- issuers of snowball-style autocall structures",
          holds="short-volatility, path-dependent books referencing CSI500 and CSI1000, hedged "
                "in index futures",
          forced_to=("delta-hedge into falling markets as knock-in barriers approach",
                     "unwind hedges abruptly when a barrier breaks",
                     "roll futures hedges at each expiry"),
          when="continuously, with violent concentration near the modal knock-in level and at "
               "the third-Friday futures expiry",
          information=("their own aggregate barrier map, which the market infers and cannot see"),
          constraints=("regulatory limits on issuance, tightened after past episodes",
                       "hedge execution limited to the liquid index futures",
                       "margin on the futures leg"),
          instruments=("CSI500 and CSI1000 index futures", "the structured notes themselves"),
          counterparties=("wealthy retail and private-bank clients as note buyers",
                          "the futures market as the hedging venue"),
          observables=("outstanding notional, reported periodically by the regulator and the "
                       "industry",
                       "the index-futures basis, which turns deeply negative when hedges unwind",
                       "small-cap index behaviour relative to large-cap"),
          impact="range compression while barriers are far, then a convex accelerant when they "
                 "break -- the January 2024 small-cap episode is the documented case",
          persistence="issuance is cyclical and regulated; the mechanism recurs whenever "
                      "outstanding notional rebuilds",
          falsifier="if CSI500 realised volatility and the futures basis show no relation to "
                    "reported outstanding snowball notional or to proximity to the modal "
                    "barrier, the hedging flow is too small or too diversified to reach price",
          notes="The mainland twin of Korea's ELS actor. Neither is tradable here directly; both "
                "reach the book through the Hong Kong carriers."),
    actor("中央政治局和国务院 -- the Politburo and the State Council as the policy calendar",
          holds="the authority to change the growth target, the fiscal stance and the property "
                "rules by announcement",
          forced_to=("meet on a recurring rhythm: the NPC each March, economic Politburo "
                     "meetings in April, July and December, the Central Economic Work Conference "
                     "each December",
                     "publish a readout whose LANGUAGE is the signal"),
          when="the months are known and the DATES are not announced in advance, which is itself "
               "the point-in-time problem this pack records",
          information=("the decision, hours to days before the readout"),
          constraints=("a growth target announced publicly once a year",
                       "the political cost of an explicit stimulus after years of restraint"),
          instruments=("fiscal quota changes", "property policy", "regulatory direction"),
          counterparties=("local governments as implementers", "the PBOC as executor",
                          "global markets as the audience"),
          observables=("the readout text and its formulaic shifts",
                       "the NPC growth target and deficit ratio, announced in early March",
                       "the December CEWC language on next year's stance"),
          impact="the largest single-day repricings of CHINAH and HK50 in the sample are policy "
                 "announcements, not data; 2024-09-24 is the canonical case",
          persistence="the rhythm is stable; the content is not, and the market's sensitivity to "
                      "the same words has fallen as promises accumulated without delivery",
          falsifier="if CHINAH and HK50 returns on readout days are indistinguishable from "
                    "matched non-readout days in the same month, the policy calendar is fully "
                    "anticipated and only surprise content matters -- which is a different and "
                    "much harder study",
          notes="Because the dates are not pre-announced, an event study here must condition on "
                "the announcement TIME and cannot be built from a calendar."),
    actor("中国出口价格 -- the Chinese export price channel (an OBSERVABLE actor)",
          holds="the price level of the world's manufactured goods supply",
          forced_to=("compete on price when domestic demand is weak and capacity is idle",
                     "export deflation when 内卷 forces margins down"),
          when="continuously; intensifies when domestic demand falls and capacity does not",
          information=("its own capacity utilisation before the PPI shows it"),
          constraints=("overcapacity that cannot be removed quickly",
                       "tariffs and trade measures that redirect rather than reduce the flow",
                       "export rebate policy the state adjusts"),
          instruments=("NONE DIRECTLY. This actor is read through PPI and export prices and "
                       "expressed in US500, NAS100 and the dollar"),
          counterparties=("importers everywhere", "competing manufacturers in other economies"),
          observables=("PPI, monthly",
                       "export price indices",
                       "container freight rates as a shipping-cost control"),
          impact="Chinese goods deflation is a disinflationary impulse to the rest of the world "
                 "with a lag of one to two quarters, which reaches the book through global rate "
                 "expectations rather than through any Chinese instrument",
          persistence="tied to the overcapacity cycle; the current episode is policy-recognised "
                      "and policy-resisted, which makes its end a policy question",
          falsifier="if Chinese PPI and export prices carry no information for US or European "
                    "goods inflation at any lag out to four quarters, after controlling for "
                    "commodity prices and freight, the export-deflation channel is not "
                    "measurable at this frequency",
          notes="The weakest-prior actor in the pack and it is labelled as such rather than "
                "dropped: the mechanism is widely asserted and rarely tested."),
    actor("离岸人民币市场参与者 -- the offshore CNH market",
          holds="offshore renminbi deposits and the only freely tradable price of the currency",
          forced_to=("fund positions in a deposit pool that is finite and can be squeezed",
                     "trade through every mainland closure with no fix to anchor to",
                     "close arbitrage against an onshore price they may not access"),
          when="24 hours a day, five days a week, including the whole of Spring Festival and "
               "Golden Week",
          information=("global risk sentiment hours before the mainland opens"),
          constraints=("a finite offshore deposit pool, which is what makes a squeeze possible "
                       "at all",
                       "no access to the onshore market for most participants",
                       "counterparty limits in a smaller market than the onshore one"),
          instruments=("USDCNH spot, forwards and options",
                       "CNH funding through the offshore deposit base"),
          counterparties=("the state banks' Hong Kong branches", "global macro funds",
                          "corporates hedging China exposure"),
          observables=("the CNH-CNY spread",
                       "CNH HIBOR at 03:15 UTC, and its spikes",
                       "USDCNH behaviour during mainland closures, on this desk's own tape"),
          impact="offshore is where a China view is expressed when the onshore market is shut or "
                 "constrained, and it is the only leg of the whole Chinese complex this broker "
                 "quotes -- so every CN mechanism in this pack has to arrive here to be tradable",
          persistence="structural while the capital account stays closed; the offshore pool's "
                      "size determines how squeezable it is and that has varied by a factor of "
                      "several",
          falsifier="if USDCNH returns during mainland closures are indistinguishable in "
                    "volatility and autocorrelation from returns on mainland trading days, the "
                    "closure is not a regime and the pack's holiday-asymmetry domain is empty",
          notes="The actor whose instrument this desk actually holds. Everything else is read "
                "through it."),
    actor("中国人民银行货币政策的境外接收者 -- global rate markets receiving Chinese policy",
          holds="positions in commodity currencies and mining equity that price Chinese demand",
          forced_to=("reprice growth expectations on a Chinese policy announcement whose date "
                     "was not published",
                     "hold or hedge exposure to a growth story they cannot observe directly"),
          when="within minutes of a State Council or Politburo readout, and within hours of the "
               "monthly data",
          information=("nothing Chinese; they are the receiving end, and their information "
                       "disadvantage is exactly why the transmission is worth measuring"),
          constraints=("no access to the mainland market at the moment of the announcement, "
                       "because it is frequently shut",
                       "a Chinese data calendar with unannounced release times"),
          instruments=("AUDUSD", "AUS200", "XCUUSD", "XAUUSD", "HK50", "CHINAH"),
          counterparties=("each other, and the mainland market when it reopens"),
          observables=("the abnormal return on those instruments in the announcement window",
                       "the gap between the announcement and the next mainland session"),
          impact="the whole executable content of this pack lives here: a Chinese fact becomes a "
                 "trade only when a non-Chinese instrument reprices",
          persistence="structural while China is the marginal buyer of industrial commodities",
          falsifier="if abnormal returns in AUDUSD, AUS200 and XCUUSD around Chinese policy and "
                    "data announcements are not distinguishable from matched windows, then "
                    "nothing in this pack is tradable on this broker and the honest verdict is "
                    "that China is a research subject and not a trade",
          notes="Named explicitly so the pack cannot pretend that a domestic Chinese mechanism "
                "is automatically an edge here."),
)


# --------------------------------------------------------------------------- domains
_DEFAULT_CONTROLS: tuple[str, ...] = (
    "the same statistic on EURUSD and GBPUSD, where no Chinese mechanism can operate",
    "the same statistic on matched weekdays and days of the month, to separate a Chinese effect "
    "from a calendar artefact",
    "the same statistic inside each era of POLICY_ERAS, never pooled across them",
    "the same statistic with the Spring Festival shift removed, because a lunar new year that "
    "moves between January and February makes almost every Chinese year-on-year series a "
    "calendar artefact before it is anything else",
)


def _controls(*extra: str) -> tuple[str, ...]:
    """The four standing controls every Chinese domain runs, plus the domain's own."""
    return (*_DEFAULT_CONTROLS, *extra)


DOMAINS: tuple[dict[str, Any], ...] = (
    domain("cn_fix_and_ccf", "The central parity, the counter-cyclical factor and the band",
           objects=("the daily fix at 01:15 UTC",
                    "the residual of the fix against previous close plus basket move",
                    "the onshore spot's position inside the 2% band",
                    "the fifteen-minute gap between the fix and the onshore open"),
           conditions=("whether the counter-cyclical factor was active in that era",
                       "the size of the overnight dollar move the fix has to absorb",
                       "how close the onshore price sits to a round level such as 7.30"),
           instruments=("USDCNH", "HK50", "CHINAH"),
           controls=_controls(
               "the same residual computed on days when the overnight dollar move was near zero, "
               "where a model and a guided fix cannot be distinguished",
               "the same window applied to USDSGD, which trades the session with no Chinese fix")),
    domain("cn_cnh_cny_basis", "Two prices of one currency as a state observable",
           objects=("the CNH minus CNY spread in pips", "CNH HIBOR and its spikes",
                    "the forward points and the cost of a short CNH carry"),
           conditions=("whether the spread is wider than its own trailing distribution",
                       "whether the offshore deposit pool is large or squeezed",
                       "mainland closure versus open session"),
           instruments=("USDCNH", "HK50"),
           controls=_controls(
               "the same spread statistic on days with no CNH HIBOR move, which separates a "
               "funding squeeze from a directional view",
               "USDSGD and USDKRW as regional Asian-currency controls with no onshore twin")),
    domain("cn_liquidity_ops", "The operations calendar: OMO, MLF, RRR and the LPR",
           objects=("daily net injection or drain", "LPR announcements on the 20th",
                    "MLF operations and their rate", "RRR changes and their effective dates"),
           conditions=("before and after 2024-07-22, when the 7-day reverse repo became the "
                       "policy rate and the MLF was demoted",
                       "quarter-end and Spring Festival funding pressure",
                       "whether the move was expected by the onshore repo market"),
           instruments=("USDCNH", "HK50", "CHINAH", "XCUUSD"),
           controls=_controls(
               "the same event study on ROUTINE OMO days with no rate change, which is the only "
               "honest placebo for an operations calendar that publishes something daily",
               "the same statistic on the 20th in months when the LPR was left unchanged")),
    domain("cn_credit_impulse", "Total social financing and the credit impulse",
           objects=("monthly TSF and new loans", "the credit impulse as a change in flow over "
                    "GDP", "the household and corporate long-term loan split"),
           conditions=("the release window, which is announced only as 'between the 9th and the "
                       "15th' and therefore cannot be an ex-ante event",
                       "whether the definition of TSF changed in that vintage",
                       "the phase of the property cycle"),
           instruments=("AUDUSD", "AUS200", "XCUUSD", "HK50", "CHINAH"),
           controls=_controls(
               "the same statistic with the January and February observations excluded, since "
               "the Spring Festival distorts both beyond repair",
               "a global credit-impulse control built from the same transformation applied to a "
               "non-Chinese aggregate")),
    domain("cn_commodity_demand", "Chinese physical demand as a price in Australian and metals "
                                  "markets",
           objects=("iron ore, copper, crude and soybean import volumes",
                    "port and exchange warehouse stocks",
                    "the official and Caixin PMIs",
                    "daily member position tables at the four commodity exchanges"),
           conditions=("the phase of the property cycle",
                       "whether stockpiling is opportunistic or policy-directed",
                       "the level of the dollar, which moves every commodity independently"),
           instruments=("AUDUSD", "AUS200", "XCUUSD", "XALUSD", "XZNUSD", "XNIUSD", "SOYBEAN",
                        "XTIUSD", "XBRUSD"),
           controls=_controls(
               "the same statistic with the dollar index removed first, since a dollar move "
               "produces the same sign in every commodity and in AUDUSD simultaneously",
               "the same statistic on a commodity China barely imports, where the Chinese demand "
               "channel cannot operate")),
    domain("cn_connect_flows", "Northbound, southbound, and the day the flow stopped being visible",
           objects=("daily northbound and southbound turnover", "quota utilisation",
                    "southbound holdings from CCASS",
                    "THE 2024-08-19 DISCLOSURE BREAK itself as a research object"),
           conditions=("before and after 2024-08-19, never pooled",
                       "index review effective dates",
                       "whether the Connect calendar closed the link that day"),
           instruments=("HK50", "CHINAH", "USDCNH"),
           controls=_controls(
               "the same statistic estimated separately either side of 2024-08-19 with a "
               "structural-break test reported, not a pooled mean",
               "southbound, which remained fully observable across the break, as the within-pack "
               "control for the northbound change")),
    domain("cn_property_cycle", "The property cycle and its commodity shadow",
           objects=("70-city prices", "sales area and new starts", "land-sale revenue",
                    "dated developer credit events"),
           conditions=("the policy regime: before and after 三条红线 in August 2020",
                       "whether the event was a default, a restructuring or a rescue",
                       "the level of mortgage rates"),
           instruments=("AUDUSD", "XCUUSD", "HK50", "CHINAH", "XAUUSD"),
           controls=_controls(
               "matched days with equivalent global risk moves and no Chinese property news",
               "the same event windows applied to a property market outside China")),
    domain("cn_policy_calendar", "Politburo, NPC and the Central Economic Work Conference",
           objects=("readout text and its formulaic shifts",
                    "the NPC growth target and deficit ratio",
                    "the December CEWC stance for the following year",
                    "State Council executive meeting announcements"),
           conditions=("whether the date was knowable in advance, which for the economic "
                       "Politburo meetings it is NOT",
                       "the market's prior on stimulus, which decays as promises accumulate",
                       "whether the mainland market was open at the announcement"),
           instruments=("HK50", "CHINAH", "AUDUSD", "XCUUSD"),
           controls=_controls(
               "matched days in the same month with no readout",
               "the same text-shift statistic applied to routine ministry announcements, which "
               "carry the same vocabulary and none of the authority")),
    domain("cn_holiday_asymmetry",
           "A week of offshore price discovery with the onshore market shut",
           objects=("USDCNH, HK50 and CHINAH paths during mainland closures of three days or more",
                    "the reopening session and the gap it prices",
                    "the first fix after a closure, which must absorb the whole offshore move"),
           conditions=("closure length, which ranges from three days to more than a week",
                       "whether a global risk event landed inside the closure",
                       "whether Hong Kong was also closed, which differs by holiday"),
           instruments=("USDCNH", "HK50", "CHINAH"),
           controls=_controls(
               "ordinary weekends, which are closures of two days and should show the same "
               "mechanism at smaller amplitude if the mechanism is real",
               "the same statistic on USDSGD across Chinese closures, where the instrument is "
               "open and the mechanism is absent")),
    domain("cn_exchange_microstructure", "T+1, the limit, the halt and the abolished breaker",
           objects=("the A-share overnight gap distribution under T+1",
                    "limit-up and limit-down queues",
                    "suspension waves and the stale prices they leave in an index",
                    "the four-day January 2016 circuit-breaker episode"),
           conditions=("which board, since ChiNext and STAR carry a 20% limit and the main "
                       "boards 10%",
                       "whether the name is ST-flagged and therefore on a 5% limit",
                       "the era, because the breaker existed for four sessions and never again"),
           instruments=("CHINAH", "HK50"),
           controls=_controls(
               "the same gap statistic on the Hong Kong lines of dual-listed mainland companies, "
               "which trade T+0 with no limit -- the cleanest available control for a settlement "
               "rule anywhere in this package",
               "the same statistic on a T+0 market with similar volatility")),
    domain("cn_state_bank_fx", "Intervention that is never announced, read from price",
           objects=("sharp late-session onshore reversals with no news",
                    "abrupt closing of the CNH-CNY gap",
                    "CNH funding spikes",
                    "FX risk reserve and FX deposit reserve changes, which ARE announced"),
           conditions=("how far the currency has moved that morning",
                       "proximity to a round level the market treats as a line",
                       "whether an announced reserve change had just landed"),
           instruments=("USDCNH",),
           controls=_controls(
               "matched days with the same morning move and no reversal, which is the only way "
               "to separate an intervention footprint from mean reversion",
               "the announced FX risk reserve changes, which are DATED interventions and "
               "therefore calibrate what an unannounced one should look like")),
    domain("cn_export_prices", "Chinese goods deflation as a global disinflationary impulse",
           objects=("PPI", "export price indices", "container freight rates",
                    "capacity utilisation commentary"),
           conditions=("the phase of the overcapacity cycle",
                       "tariff regime, which redirects rather than reduces the flow",
                       "the freight cost, which can reverse the sign at the border"),
           instruments=("US500", "NAS100", "USDCNH"),
           controls=_controls(
               "the same statistic with commodity prices and freight removed first, because "
               "both move Chinese PPI and global goods prices simultaneously",
               "a non-Chinese manufacturing exporter's PPI as a placebo"),
           notes="The weakest-prior domain in the pack, labelled as such. It is kept because the "
                 "claim is made constantly in public commentary and almost never tested."),
    domain("cn_trade_cycle", "Customs data and the calendar that corrupts it",
           objects=("monthly exports, imports and the balance",
                    "the combined January and February release",
                    "export and import composition by partner and product"),
           conditions=("Spring Festival timing, which is the single largest distortion in "
                       "Chinese monthly data",
                       "working-day count",
                       "front-running of tariff deadlines, which pulls shipments forward"),
           instruments=("AUDUSD", "AUS200", "XCUUSD", "USDCNH", "XTIUSD"),
           controls=_controls(
               "the same statistic computed on a combined January-February basis for EVERY year, "
               "which is the only comparison the data supports",
               "Korean and Taiwanese trade data for the same months, which are published "
               "monthly and can cross-check the Chinese calendar effect")),
    domain("cn_offshore_funding", "The finite offshore pool and the squeeze that defends the fix",
           objects=("CNH HIBOR at 03:15 UTC and its term structure",
                    "offshore renminbi deposit balances in Hong Kong, monthly",
                    "forward points and the cost of carrying a short CNH position"),
           conditions=("the size of the offshore pool relative to its own history",
                       "whether the authorities have signalled discomfort",
                       "whether a squeeze coincides with a fix residual"),
           instruments=("USDCNH", "HK50"),
           controls=_controls(
               "HKD HIBOR on the same days, which shares the Hong Kong funding market and not "
               "the Chinese mechanism",
               "the same statistic in periods when the offshore pool was at its largest, where a "
               "squeeze should be mechanically harder")),
)


# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("cn_fix_residual_to_cnh",
         source="the residual of the 01:15 UTC central parity against previous close plus basket",
         mechanism="a fix stronger than the model implies is state guidance, and the offshore "
                   "market can act on it for fifteen minutes before the onshore market opens",
         targets=("USDCNH",),
         sign="fix STRONGER than model -> USDCNH DOWN in the following hour",
         horizon="minutes to one session",
         lag="01:15 UTC publication, 01:30 UTC onshore open",
         control="days with a near-zero overnight dollar move, where a model fix and a guided "
                 "fix cannot be told apart; and the same window on USDSGD",
         evidence="HYPOTHESIS",
         notes="The highest-prior edge in this pack: an announced number, an exact minute, a "
               "fifteen-minute window in which only one of the two markets can trade."),
    edge("cnh_funding_squeeze_to_cnh",
         source="CNH HIBOR spiking at the 03:15 UTC fixing",
         mechanism="raising the offshore funding cost makes a short CNH position expensive to "
                   "carry and forces it to be closed",
         targets=("USDCNH", "HK50"),
         sign="CNH HIBOR UP sharply -> USDCNH DOWN",
         horizon="one to three sessions",
         lag="03:15 UTC",
         control="HKD HIBOR on the same days, which shares the funding market and not the "
                 "mechanism; and days with a wide CNH-CNY gap and no funding move",
         evidence="HYPOTHESIS"),
    edge("cn_credit_impulse_to_australia",
         source="monthly total social financing and new loans",
         mechanism="Chinese credit funds construction, which is the marginal demand for iron "
                   "ore, copper and steel, and Australia is the marginal supplier",
         targets=("AUDUSD", "AUS200", "XCUUSD"),
         sign="credit impulse UP -> AUDUSD UP, XCUUSD UP, AUS200 UP",
         horizon="one to three months",
         lag="release between the 9th and the 15th with no announced time",
         control="January and February excluded entirely; and the same transformation applied to "
                 "a non-Chinese credit aggregate as a global-cycle placebo",
         evidence="HYPOTHESIS"),
    edge("cn_pmi_surprise_to_carriers",
         source="the official manufacturing PMI at 01:00 UTC and Caixin at 01:45 UTC",
         mechanism="the earliest monthly read on Chinese industrial activity, released while "
                   "Asian markets are open and Western ones are not",
         targets=("AUDUSD", "XCUUSD", "HK50", "CHINAH", "AUS200"),
         sign="PMI surprise UP -> AUDUSD UP, XCUUSD UP, HK50 UP",
         horizon="same session",
         lag="01:00 UTC for the official series; the Caixin print 45 minutes later is a SECOND "
             "event and must be stamped separately",
         control="the two releases against each other -- if the Caixin surprise adds nothing "
                 "after the official one, the second event is redundant; and matched days of "
                 "the month with no release",
         evidence="HYPOTHESIS"),
    edge("cn_import_volumes_to_metals",
         source="customs import volumes and exchange warehouse stocks",
         mechanism="Chinese physical demand is the price-setting marginal bid in iron ore and "
                   "copper; falling port stocks with rising imports is a tightening signal",
         targets=("XCUUSD", "XALUSD", "XZNUSD", "XNIUSD", "AUDUSD"),
         sign="imports UP with stocks DOWN -> metals UP",
         horizon="two weeks to two months",
         lag="customs monthly around the 7th to the 13th; stocks weekly on Friday",
         control="the dollar index removed first, since a dollar move produces the same sign in "
                 "every leg at once; and a commodity China barely imports",
         evidence="HYPOTHESIS"),
    edge("cn_depreciation_to_regional_riskoff",
         source="USDCNH breaking through a level the market treats as a line, such as 7.30",
         mechanism="a visibly weaker renminbi is read as a policy signal about Chinese growth "
                   "and as a competitive pressure on every Asian exporter",
         targets=("USDKRW", "USDSGD", "HK50", "XAUUSD", "CHINAH"),
         sign="USDCNH UP through the level -> USDKRW UP, USDSGD UP, HK50 DOWN, XAUUSD UP",
         horizon="one to ten sessions",
         lag="continuous",
         control="equivalent-sized USDCNH moves that do NOT cross a round level, which separates "
                 "a level effect from a return effect; and matched global risk-off days with no "
                 "renminbi move",
         evidence="HYPOTHESIS",
         notes="USDKRW is in the Korean pack's executable list and is reached here as a target; "
               "the two packs share the edge on purpose rather than each claiming it alone."),
    edge("cn_closure_to_offshore_discovery",
         source="mainland closures of three days or more, computed by cn_long_closures()",
         mechanism="for a week at Spring Festival and Golden Week the offshore price of the "
                   "renminbi is discovered with no onshore counterparty and no fix to anchor it",
         targets=("USDCNH", "HK50", "CHINAH"),
         sign="closure -> changed volatility and autocorrelation offshore, then a reopening gap "
              "that reconciles the two prices",
         horizon="the closure window plus the first session after it",
         lag="known years in advance from the State Council notice",
         control="ordinary weekends, which are two-day closures and should show the same "
                 "mechanism at smaller amplitude; and USDSGD across the same dates",
         evidence="HYPOTHESIS",
         notes="The pack's custom miner measures exactly this edge."),
    edge("cn_southbound_to_hongkong",
         source="daily southbound Stock Connect turnover and CCASS holdings",
         mechanism="mainland money buying Hong Kong equity is a marginal bid for HK50 and CHINAH "
                   "and a structural HKD demand at settlement",
         targets=("HK50", "CHINAH", "USDHKD"),
         sign="southbound surge -> HK50 UP, CHINAH UP, USDHKD toward the strong side",
         horizon="one to ten sessions",
         lag="same day for turnover, one session for holdings",
         control="northbound over the same window, which is the other direction of the same "
                 "link; and global equity beta removed first",
         evidence="HYPOTHESIS"),
    edge("cn_policy_readout_to_equity",
         source="Politburo, CEWC and State Council readouts and their language shifts",
         mechanism="a stance change is priced immediately in the offshore China expressions, "
                   "which are open when the mainland frequently is not",
         targets=("CHINAH", "HK50", "XCUUSD", "AUDUSD"),
         sign="stimulus language -> CHINAH UP, HK50 UP, XCUUSD UP",
         horizon="minutes to two sessions",
         lag="announcement time, which is NOT pre-announced for the economic Politburo meetings",
         control="matched days in the same month with no readout; and the same vocabulary "
                 "applied to routine ministry announcements",
         evidence="HYPOTHESIS"),
    edge("cn_rrr_cut_to_risk",
         source="reserve-requirement ratio cuts and their effective dates",
         mechanism="an RRR cut releases base money and is read as an easing signal, with an "
                   "announcement effect and a separate effective-date effect",
         targets=("USDCNH", "HK50", "CHINAH", "XCUUSD"),
         sign="RRR cut -> HK50 UP, XCUUSD UP; the USDCNH sign is AMBIGUOUS because easing is "
              "both growth-positive and rate-negative, and that ambiguity is the finding",
         horizon="announcement day and the effective date, measured separately",
         lag="announcement usually after the close; effective ten to fifteen days later",
         control="the effective date measured on its own, which should carry nothing if the "
                 "announcement was the news; and matched days with no announcement",
         evidence="HYPOTHESIS"),
    edge("cn_property_distress_to_commodities",
         source="dated developer credit events and the 70-city price series",
         mechanism="property is the largest single driver of Chinese metals demand, so distress "
                   "transmits through an expectation channel long before the physical data",
         targets=("AUDUSD", "XCUUSD", "XAUUSD", "HK50"),
         sign="distress -> AUDUSD DOWN, XCUUSD DOWN, XAUUSD UP",
         horizon="one to twenty sessions",
         lag="event timestamp",
         control="matched days with equivalent global risk moves and no Chinese property news; "
                 "and the physical data releases themselves, which should carry LESS if the "
                 "expectation channel is doing the work",
         evidence="HYPOTHESIS"),
    edge("cn_fx_risk_reserve_to_forwards",
         source="changes to the FX risk reserve requirement on bank forward sales",
         mechanism="the requirement raises the cost of selling renminbi forward, which is a "
                   "DATED, announced intervention with a stated mechanism",
         targets=("USDCNH",),
         sign="reserve requirement RAISED -> USDCNH DOWN",
         horizon="one to ten sessions",
         lag="announcement timestamp",
         control="matched days with the same prior depreciation and no announcement; and the "
                 "unannounced state-bank episodes, which this edge calibrates",
         evidence="HYPOTHESIS",
         notes="The cleanest dated Chinese intervention available, and therefore the yardstick "
               "for the undated ones."),
)

#: Derived, never hand-maintained: the executable symbols this pack's economics reach that are
#: NOT China's own offshore price.
TRANSMISSION_TARGETS: tuple[str, ...] = tuple(sorted(
    {t for e in TRANSMISSION_EDGES_SEED for t in e["targets"]} - set(OWN_PRICE)))


# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("cn_fix_reform", start="2015-08-11", end="2017-04-30",
        label="The 2015 fixing reform and the two devaluation shocks",
        what_changed="the central parity was tied to the previous close, which turned the fix "
                     "from an anchor into a follower and produced two disorderly episodes",
        invalidates="any fix-residual study pooled with the pre-2015 period is measuring two "
                    "different formulas under one name"),
    era("cn_ccf_era", start="2017-05-26", end="2018-01-08",
        label="The counter-cyclical factor introduced",
        what_changed="a discretionary term was added to the fix formula, making the residual "
                     "between model and actual the state's own signal",
        invalidates="a fix-residual statistic estimated when the factor was switched off has no "
                    "reason to hold when it is on, and the switch dates are known"),
    era("cn_trade_war", start="2018-03-22", end="2020-01-15",
        label="The trade war and the first break of 7.00",
        what_changed="tariff announcements became the dominant driver, and USDCNY traded through "
                     "7.00 on 2019-08-05 for the first time since 2008",
        invalidates="volatility and tail estimates from this window are about tariff headlines "
                    "and not about the managed-float mechanism"),
    era("cn_covid_export_boom", start="2020-03-01", end="2021-12-31",
        label="The pandemic export boom and renminbi strength",
        what_changed="an enormous goods trade surplus produced a persistent conversion bid and "
                     "took USDCNY toward 6.30",
        invalidates="a trade-balance-to-currency elasticity fitted here is fitted on a supply "
                    "shock in the rest of the world and does not generalise"),
    era("cn_divergence_and_defence", start="2022-03-01", end="2023-12-31",
        label="Policy divergence, the 7.30 defence and the state-bank era",
        what_changed="US tightening against Chinese easing opened the widest rate differential "
                     "of the sample; the authorities defended through fix guidance, state-bank "
                     "selling and the FX risk reserve rather than through reserves",
        invalidates="an intervention study that looks for reserve changes finds nothing in this "
                    "era, because the defence deliberately did not use them"),
    era("cn_policy_rate_change", start="2024-07-22", end=None,
        label="The 7-day reverse repo becomes the primary policy rate",
        what_changed="the MLF was demoted and moved from the 15th to the 25th; the LPR was "
                     "re-anchored on the short rate",
        invalidates="an MLF event study pooled across this date is pooling a policy rate with a "
                    "liquidity operation, and an LPR study is pooling two different anchors"),
    era("cn_northbound_dark", start="2024-08-19", end=None,
        label="Real-time northbound flow disclosure ends",
        what_changed="intraday northbound net buying stopped being published; only end-of-day "
                     "turnover survives and holdings are quarterly",
        invalidates="EVERY northbound-flow strategy backtested before this date uses an input "
                    "that does not exist live afterwards. This is a DATA era, and it belongs in "
                    "a policy table because it silently changes what any earlier study can be "
                    "replicated on"),
    era("cn_stimulus_repricing", start="2024-09-24", end="2025-12-31",
        label="The coordinated stimulus package and its half-life",
        what_changed="a joint PBOC, CSRC and regulator package produced the largest single-day "
                     "repricing of CHINAH and HK50 in the sample, followed by a long decay as "
                     "delivery lagged announcement",
        invalidates="a policy-announcement event study that includes this date without "
                    "conditioning on it is dominated by one observation"),
    era("cn_tariff_era", start="2025-01-01", end=None,
        label="The renewed tariff regime",
        what_changed="trade measures again became the dominant driver of the currency and of "
                     "export front-running in the customs data",
        invalidates="a trade-cycle model fitted here is fitted on shipment timing decisions "
                    "driven by announced deadlines, not on demand"),
)


# --------------------------------------------------------------------------- framework fields
MISSION = ("Mine the Chinese economic system to exhaustion for forced flows that reach a symbol "
           "this broker quotes -- the offshore currency, the Hong Kong China expressions, the "
           "Australian pair and the metals complex -- and name every leg that cannot be measured "
           "on this box rather than proxying it.")
#: There is no renminbi futures contract in the CFTC's reports, so there is no COT row for this
#: country. Empty is the MEASUREMENT; the exchange member tables are the named substitute.
COT_CURRENCY = ""
EXPORT_ECONOMY = "manufacturing_exporter"
#: Margin financing is available only on an eligible-securities list, to qualified investors,
#: with a regulator-set ceiling on the list itself. That is a restricted regime by construction.
RETAIL_LEVERAGE_REGIME = "restricted"
OPEN_ERA_END = "2030-12-31"
#: Recurring solar closures as MM-DD. The lunar holidays (春节, 端午节, 中秋节) and the solar
#: term 清明 CANNOT appear here and are tabulated instead; the 调休 make-up working weekends
#: cannot be expressed in any rule at all.
HOLIDAY_FIXED_MD: tuple[str, ...] = ("01-01", "05-01", "10-01", "10-02", "10-03")

SESSION_WINDOWS: tuple[dict[str, str], ...] = (
    {"name": "cn_fix_window", "start_utc": "01:10", "end_utc": "01:35",
     "notes": "the central parity at 01:15 UTC and the fifteen minutes before the onshore market "
              "opens at 01:30 -- the only window in the pack where the offshore market can act "
              "on a Chinese announcement that the onshore market cannot yet trade"},
    {"name": "cn_morning_session", "start_utc": "01:30", "end_utc": "03:30",
     "notes": "the A-share morning session and the OMO announcement at 01:20"},
    {"name": "cn_afternoon_session", "start_utc": "05:00", "end_utc": "07:00",
     "notes": "the A-share afternoon session, ending with the 06:57-07:00 closing call"},
    {"name": "cn_onshore_fx_close", "start_utc": "08:00", "end_utc": "08:45",
     "notes": "the 16:30 Beijing reference close that feeds the next day's fix; state-bank "
              "activity on stressed days concentrates here"},
    {"name": "cn_offshore_only", "start_utc": "15:30", "end_utc": "23:59",
     "notes": "after the extended onshore session ends at 23:30 Beijing, USDCNH trades alone"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "cn_official_pmi", "cadence": "monthly", "time_utc": "01:00",
     "source": "国家统计局", "notes": "last day of the month; the earliest monthly read on "
                                    "Chinese industry anywhere"},
    {"name": "cn_caixin_pmi", "cadence": "monthly", "time_utc": "01:45",
     "source": "Caixin and S&P Global", "notes": "first business day; a SEPARATE event from the "
                                                 "official print 45 minutes earlier"},
    {"name": "cn_trade", "cadence": "monthly", "time_utc": "03:00",
     "source": "海关总署", "notes": "between the 7th and the 13th; January and February are "
                                   "published COMBINED"},
    {"name": "cn_tsf_credit", "cadence": "monthly", "time_utc": "",
     "source": "中国人民银行", "notes": "between the 9th and the 15th with NO announced time, "
                                       "which is why this class carries no time_utc and why its "
                                       "dataset is not point-in-time feasible"},
    {"name": "cn_activity_data", "cadence": "monthly", "time_utc": "02:00",
     "source": "国家统计局", "notes": "industrial production, retail sales and fixed-asset "
                                     "investment, around the 15th to the 17th"},
    {"name": "cn_cpi_ppi", "cadence": "monthly", "time_utc": "01:30",
     "source": "国家统计局", "notes": "around the 9th; PPI is the export-deflation leg"},
    {"name": "cn_lpr", "cadence": "monthly", "time_utc": "01:15",
     "source": "全国银行间同业拆借中心", "notes": "the 20th, rolled forward off closures"},
)

INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "CFFEX 持仓排名 (daily top-20 member index-futures positions, cffex.com.cn)",
    "SHFE, DCE, ZCE and INE 持仓排名 and 库存 (daily member positions, weekly warehouse stocks)",
    "融资融券余额 (daily margin financing balances, sse.com.cn and szse.cn)",
    "Stock Connect northbound and southbound turnover (hkex.com.hk; northbound real-time flow "
    "ended 2024-08-19)",
    "CCASS shareholding search (daily southbound holdings by participant, hkex.com.hk)",
    "SAFE 银行结售汇 (monthly netted FX settlement and sales, safe.gov.cn)",
)


# --------------------------------------------------------------------------- typed row builders
def _central_bank_row(lab: Any) -> Any:
    """The PBOC as `country_lab.CentralBank`, anchored on the LPR grid.

    There is no rate-decision calendar to transcribe, so the anchors are DERIVED from the
    20th-of-the-month rule. That is stated in the notes rather than hidden: an event study built
    on a derived grid is only as good as the roll convention behind it.
    """
    dates: list[str] = []
    for year in range(2020, 2027):
        dates.extend(cn_lpr_dates(year))
    return lab.CentralBank(
        name="People's Bank of China (中国人民银行)",
        framework="managed_float",
        decision_dates=tuple(sorted(dates)),
        decision_calendar_rule=str(CENTRAL_BANK["schedule_rule"]),
        decision_time_utc="01:15",
        publication_classes=("人民币汇率中间价 (01:15 UTC daily)",
                             "公开市场业务交易公告 (01:20 UTC daily)",
                             "贷款市场报价利率 (01:15 UTC on the 20th)",
                             "货币政策执行报告 (quarterly, about two months in arrears)"),
        policy_rate_series="cn_7d_reverse_repo",
        expected_rate_series="",
        notes=f"{CENTRAL_BANK['fx_operations']} BAND: {CENTRAL_BANK['band']} "
              f"DERIVED ANCHORS: {CENTRAL_BANK['verification']}")


def _fixing_rows(lab: Any) -> tuple[Any, ...]:
    """China's three published references, in UTC. CST never shifts, so `dst_rule` is 'none'."""
    return (
        lab.Fixing(name="人民币汇率中间价 (CFETS central parity)", time_utc="01:15",
                   dst_rule="none", instruments=("USDCNH",), window_minutes=25,
                   notes=str(FIXING_CONVENTIONS["central_parity"]["note"])),
        lab.Fixing(name="CNH HIBOR (TMA, Hong Kong)", time_utc="03:15", dst_rule="none",
                   instruments=("USDCNH", "HK50"), window_minutes=60,
                   notes=str(FIXING_CONVENTIONS["cnh_hibor"]["note"])),
        lab.Fixing(name="CFETS 收盘价 (the 16:30 Beijing reference close)", time_utc="08:30",
                   dst_rule="none", instruments=("USDCNH",), window_minutes=45,
                   notes=str(FIXING_CONVENTIONS["onshore_close"]["note"])),
    )


def _settlement_rows(lab: Any) -> tuple[Any, ...]:
    """China's conventions as RULES. There is no gotobi here and none is invented."""
    return (
        lab.SettlementRule(name="cn_lpr_day", kind="day_of_month", days=(20,), months=(),
                           weekday=-1, week_of_month=0, roll="next",
                           window_utc=("01:10", "02:00"),
                           instruments=("USDCNH", "HK50", "CHINAH"),
                           notes="the LPR is published on the 20th and rolled FORWARD when the "
                                 "20th is closed, because the announcement moves with the "
                                 "working calendar rather than being brought forward"),
        lab.SettlementRule(name="cn_mlf_day", kind="day_of_month", days=(15, 25), months=(),
                           weekday=-1, week_of_month=0, roll="next",
                           window_utc=("01:10", "02:00"), instruments=("USDCNH",),
                           notes="the 15th until July 2024 and the 25th afterwards; BOTH are "
                                 "listed because the series spans the change and a single day "
                                 "would silently drop half the sample"),
        lab.SettlementRule(name="cn_month_end_conversion", kind="month_end", days=(), months=(),
                           weekday=-1, week_of_month=0, roll="previous",
                           window_utc=("01:30", "08:30"), instruments=("USDCNH",),
                           notes=str(SETTLEMENT_CONVENTIONS["corporate_conversion"])),
        lab.SettlementRule(name="cn_quarter_end_funding", kind="quarter_end", days=(), months=(),
                           weekday=-1, week_of_month=0, roll="previous",
                           window_utc=("01:30", "08:30"), instruments=("USDCNH", "HK50"),
                           notes="onshore funding tightens into quarter end and the PBOC "
                                 "routinely injects against it, so a quarter-end liquidity "
                                 "statistic is measuring the injection as much as the tightness"),
        lab.SettlementRule(name="cn_cffex_expiry", kind="week_of_month", days=(), months=(),
                           weekday=4, week_of_month=3, roll="previous",
                           window_utc=("05:00", "07:00"), instruments=("CHINAH", "HK50"),
                           notes="CFFEX index futures settle on the THIRD FRIDAY against the "
                                 "average of the index over the last two hours of the cash "
                                 "session -- a far wider settlement window than Korea's "
                                 "ten-minute auction and therefore much harder to push"),
    )


def _exchange_rows(lab: Any) -> tuple[Any, ...]:
    """The mainland exchanges. `index_symbols` is EMPTY for every one of them and that is the
    finding: this broker quotes no mainland index, so the generic expiry miner has nothing to run
    and the Chinese equity mechanisms reach the book only through CHINAH and HK50."""
    dates = tuple(nth_weekday(y, m, 4, 3).isoformat()
                  for y in (2024, 2025, 2026) for m in range(1, 13))
    return (
        lab.Exchange(name="Shanghai and Shenzhen Stock Exchanges", index_symbols=(),
                     expiry_rule="", expiry_dates=(), open_utc="01:30", close_utc="07:00",
                     notes=f"T+1 settlement, {EXCHANGES['cash']['price_limit']}. NO MAINLAND "
                           f"INDEX IS QUOTED BY THIS BROKER; CSI300 and the rest are in "
                           f"ABSENT_INSTRUMENTS with the carriers that stand in for them."),
        lab.Exchange(name="China Financial Futures Exchange (CFFEX)", index_symbols=(),
                     expiry_rule="third Friday of the contract month; settlement is the "
                                 "arithmetic average of the index over the last two hours of the "
                                 "cash session on the final trading day",
                     expiry_dates=dates, open_utc="01:30", close_utc="07:00",
                     notes="the expiry grid is computable and is expanded here for 2024-2026; "
                           "with no executable mainland index the pack's own miner measures the "
                           "spill on CHINAH and HK50 instead"),
        lab.Exchange(name="Mainland commodity exchanges (SHFE, DCE, ZCE, INE)", index_symbols=(),
                     expiry_rule="", expiry_dates=(), open_utc="01:00", close_utc="07:00",
                     notes=str(EXCHANGES["commodities"]["disclosure"])),
    )


def _release_rows(lab: Any) -> tuple[Any, ...]:
    return tuple(lab.ReleaseClass(name=r["name"], cadence=r["cadence"], time_utc=r["time_utc"],
                                  dates=(), actual_series="", expected_series="",
                                  source=str(r["source"]), notes=str(r["notes"]))
                 for r in RELEASE_CLASSES)


# --------------------------------------------------------------------------- the custom miner
def cn_closure_asymmetry(pack_in: Any, ctx: Any) -> dict[str, Any]:
    """Offshore price discovery while the mainland is shut, and the session that reconciles it.

    WHY THIS IS NOT THE GENERIC HOLIDAY MINER. `country_lab.generic_holiday_liquidity` asks what
    happens to a country's OWN instrument when its market closes. China's own instrument is not
    closed: USDCNH, HK50 and CHINAH trade through every mainland closure. The object here is the
    ASYMMETRY -- a week in which the offshore price moves with no onshore counterparty, no fix to
    anchor to and no A-share book to arbitrage against, followed by one session in which the two
    prices reconcile. That is a different question from "is the tape thinner", and it needs the
    closure runs computed first, which is what `cn_long_closures` does.

    The reading is deliberately two-sided: the closure window itself, and the REOPENING session
    as an event. A mechanism that shows up in one and not the other is telling you which of the
    two stories is true.
    """
    lab = _lab()
    out: dict[str, Any] = {"miner": "cn_closure_asymmetry", "country": CODE,
                           "readings": [], "measured": 0}
    if lab is None:
        out["outcome"] = "UNMEASURED"
        out["why"] = "libs.research.country_lab is absent on this tree"
        return out
    runs: list[dict[str, str]] = []
    for year in sorted({int(y) for y in HOLIDAYS_RULE["table"]}):
        runs.extend(cn_long_closures(year))
    if not runs:
        ctx.note("closures", "no mainland closure of three days or more is tabulated")
        out["outcome"] = "UNMEASURED"
        out["why"] = "no closure runs"
        return out
    reopen = lab.parse_days(tuple(r["reopen"] for r in runs))
    out["closures"] = tuple(runs)
    for sym in ("USDCNH", "HK50", "CHINAH"):
        bars = ctx.bars(sym, "H1")
        if bars is None:
            ctx.note(f"bars:{sym}", "no H1 tape on this box, so the reopening event cannot be "
                                    "measured for this carrier")
            continue
        try:
            got = lab.event_effect(bars, reopen, horizon=1, rng=ctx.rng(f"reopen:{sym}"))
        except Exception as exc:  # pragma: no cover -- a framework signature change
            ctx.note(f"event_effect:{sym}", f"{type(exc).__name__}: {exc}")
            continue
        out["readings"].append({
            "symbol": sym, "role": "own_price" if sym in OWN_PRICE else "carrier",
            "reopening_session": got, "n_closures": len(runs),
            "claim": "the first session after a mainland closure of three days or more prices "
                     "the offshore move the onshore market could not react to; the matched "
                     "weekday control inside event_effect is what separates that from an "
                     "ordinary Monday"})
        out["measured"] += int(got.get("verdict") == "MEASURED")
    out["outcome"] = "OK" if out["measured"] else "UNMEASURED"
    if not out["measured"]:
        out["why"] = "no carrier produced a measurable reopening study"
    return out


CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("cn_closure_asymmetry",
          domain_ids=("cn_holiday_asymmetry", "cn_cnh_cny_basis"),
          kind="calendar",
          entry="countries.cn.pack:cn_closure_asymmetry",
          cadence_s=86400.0,
          steerable=False,
          notes="A fixed cost: the closure grid is known years in advance from the State Council "
                "notice and must be read every pass, because a reopening session mislabelled as "
                "an ordinary one contaminates both sides of the comparison."),
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
