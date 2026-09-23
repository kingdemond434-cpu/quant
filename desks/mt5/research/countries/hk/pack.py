"""THE HONG KONG COUNTRY PACK -- a currency board, and therefore a different object entirely.

WHY HONG KONG IS NOT KOREA OR CHINA WITH DIFFERENT NOUNS. Korea has a customs print and a
second-Thursday expiry. China has a managed fix and a currency with two prices. Hong Kong has
something neither of them has and that almost no market anywhere has:

  * A PRICE WITH TWO HARD BARRIERS. USDHKD lives between 7.7500 and 7.8500 because the HKMA is
    OBLIGED to buy or sell at those levels. It is a bounded random variable with two reflecting
    barriers, not a random walk, so its tails are truncated by construction and the informative
    coordinate is DISTANCE TO THE BARRIER rather than return. `peg_band_position` computes that
    number and every domain in this pack conditions on it.
  * INTERVENTION DISCLOSED THE DAY IT HAPPENS. Korea publishes its FX transactions quarterly and
    three months late. China does not publish them at all. Taiwan publishes an aggregate reserve
    number. Hong Kong announces each Convertibility Undertaking triggering on the day, with the
    amount, and publishes the resulting Aggregate Balance the same afternoon. That is the reason
    this pack can run event studies the others cannot.
  * A TRANSMISSION CHAIN WHOSE EVERY LINK IS PUBLIC AND DAILY. Undertaking triggers, Aggregate
    Balance moves with T+2 settlement, HIBOR responds at the 03:15 UTC fixing, carry changes,
    equity and mortgages follow. Four links, all published, all daily -- and ONE of them, the
    HIBOR leg, is not tradable on this broker, which is named in `ABSENT_INSTRUMENTS` rather
    than proxied.
  * NO MONETARY POLICY OF ITS OWN. The Base Rate is a formula over the federal funds target and
    a HIBOR average. `CENTRAL_BANK["decision_dates"]` is EMPTY on purpose: copying the Fed's
    calendar into a Hong Kong pack would claim a domestic event where there is an imported one,
    and the generic central-bank miner reporting UNMEASURED here is the correct answer.
  * A MONTH-END EXPIRY. HSI and HSCEI settle on the business day immediately preceding the last
    business day of the month, so the expiry MOVES with the holiday calendar rather than the
    weekday calendar -- and settlement is an all-day five-minute average, which is an expensive
    thing to push. The contrast with Korea's ten-minute closing auction is a real test.

WHAT THIS PACK MAY NOT DO. Hong Kong single names are OBSERVABLES and never hypothesis ground
(two-lane order, 2026-09-06). No crypto-exchange venue is named, subscribed or crawled anywhere
in this pack (universe mandate, 2026-08-18).

WHAT IS EXECUTABLE. USDHKD is Hong Kong's own price, and HK50 and CHINAH make HKEX the ONLY
exchange in this package whose indices this broker actually quotes -- which is why the
framework's generic expiry miner has something to run on here and nothing in Korea, China or
Taiwan. HIBOR, the Hang Seng TECH index and the A/H premium index are all absent and are named.
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


CODE = "hk"
NAME = "Hong Kong"
REGION_COMMAND = "asia"  # country_lab.REGION_COMMANDS; EAST ASIA is this package's own grouping
CURRENCY = "HKD"
NATIVE_LANGUAGES = ("zh-Hant", "en")

#: Hong Kong's own price, and the only one in this package that is BOUNDED BY LAW.
OWN_PRICE: tuple[str, ...] = ("USDHKD",)

#: The strong-side and weak-side Convertibility Undertakings. These two numbers are the pack.
STRONG_SIDE_CU = 7.7500
WEAK_SIDE_CU = 7.8500
#: One pip on a five-decimal HKD quote. The band is 1,000 pips wide at this scale, which is what
#: makes "distance to the undertaking" a number a strategy can actually condition on.
PIP = 0.0001

EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDHKD", "HK50", "CHINAH", "EURHKD", "HKDJPY", "USDCNH", "XAUUSD", "US500", "NAS100",
    "UST10Y")

ABSENT_INSTRUMENTS: tuple[dict[str, str], ...] = (
    {"instrument": "HIBOR, or any Hong Kong interest-rate instrument",
     "why": "no HKD rates future or FRA is in desks/mt5/data/universe/universe.json",
     "carried_by": "UST10Y for the imported US rate leg, and USDHKD FORWARD POINTS as the only "
                   "market-priced expression of the HIBOR-SOFR spread -- which this broker does "
                   "not quote either, so the carry leg is UNMEASURED by name"},
    {"instrument": "Hang Seng TECH index",
     "why": "absent from the broker registry",
     "carried_by": "HK50 with an explicit sector-composition caveat, and NAS100 for the global "
                   "technology beta"},
    {"instrument": "the Hang Seng Stock Connect China AH Premium Index (HSAHP)",
     "why": "an index level, not a tradable instrument, and absent from the registry",
     "carried_by": "the CHINAH-versus-HK50 relative, which is a DIFFERENT object and is stated "
                   "as such: HSCEI and HSI are not the two legs of the A/H pair"},
    {"instrument": "HKD deposit and money-market instruments",
     "why": "absent; the Aggregate Balance transmits to rates through a market this desk cannot "
            "trade",
     "carried_by": "nothing. The chain Aggregate Balance -> HIBOR -> carry is READ here and the "
                   "middle link is not tradable, which is recorded rather than papered over"},
)


# --------------------------------------------------------------------------- central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Hong Kong Monetary Authority",
    "native_name": "香港金融管理局",
    "committee": "NONE. The HKMA is a currency board operator, not a rate-setting committee, and "
                 "the absence of a committee is the single most important fact in this pack.",
    "policy_rate": "the Base Rate, which is not chosen. It is set by FORMULA: the higher of the "
                   "US federal funds target lower bound plus 50 basis points, and the recent "
                   "moving average of overnight and one-month HIBOR.",
    "meetings_per_year": 0,
    "schedule_rule": (
        "HONG KONG HAS NO MONETARY POLICY CALENDAR OF ITS OWN. The Base Rate changes when the "
        "Federal Reserve changes the federal funds target, and the HKMA announces it in the "
        "early morning Hong Kong time, hours after the FOMC. So the decision dates of this "
        "country are the FOMC's, and they are NOT listed here: a Hong Kong pack that copied the "
        "Fed's calendar into its own central-bank row would be claiming a domestic event where "
        "there is an imported one. `decision_dates` is deliberately EMPTY and the generic "
        "central-bank miner will report UNMEASURED for this country, which is the correct "
        "answer and not a gap."),
    "minutes_rule": (
        "No minutes, because no decision. The HKMA publishes a Monetary and Financial Stability "
        "Report twice a year and a Quarterly Bulletin; neither is a policy signal in the sense "
        "the other packs' minutes are."),
    "timezone": "HKT = UTC+8 all year; Hong Kong observes NO daylight saving. The FOMC does move "
                "with US daylight saving, so the LAG from the US announcement to the HKMA's is "
                "an hour longer in the northern winter -- one of the very few DST effects "
                "anywhere in this package, and it is on the US side.",
    "convertibility_undertakings": (
        "The mechanism, established in its current two-sided form on 2005-05-18. The STRONG-SIDE "
        "undertaking at 7.7500 obliges the HKMA to sell Hong Kong dollars and buy US dollars "
        "when the market bids HKD to that level; the WEAK-SIDE undertaking at 7.8500 obliges it "
        "to buy Hong Kong dollars and sell US dollars. Between the two is the Convertibility "
        "Zone, inside which the HKMA may but need not operate. USDHKD is therefore a BOUNDED "
        "RANDOM VARIABLE WITH TWO REFLECTING BARRIERS, and that is a different object from every "
        "other currency in this package: its unconditional distribution is not a random walk's, "
        "its tails are truncated by construction, and the informative variable is DISTANCE TO "
        "THE BARRIER rather than return."),
    "aggregate_balance": (
        "總結餘. The sum of clearing balances the licensed banks hold at the HKMA, published "
        "DAILY. Every triggering of a Convertibility Undertaking changes it with T+2 settlement: "
        "weak-side buying of HKD shrinks it, strong-side selling expands it. A smaller Aggregate "
        "Balance means scarcer interbank liquidity, which pushes HIBOR up, which restores the "
        "carry that was pulling the currency to the weak side. THAT CHAIN IS THE WHOLE "
        "TRANSMISSION and every link of it is public, daily, and observable the day it happens "
        "-- which is true of no intervention anywhere else in this package."),
    "fx_operations": (
        "The undertakings are automatic and are announced as they happen. There is no discretion "
        "to infer and no quarterly disclosure to wait for. In addition the HKMA issues Exchange "
        "Fund Bills and Notes, which drains the Aggregate Balance without touching the "
        "undertakings, and that issuance is scheduled and published."),
    "intervention_disclosure": (
        "IMMEDIATE AND COMPLETE, uniquely in this package. Korea discloses intervention "
        "quarterly and three months late; China does not disclose it at all; Taiwan discloses it "
        "in aggregate reserve numbers. Hong Kong announces each triggering on the day, with the "
        "amount, and publishes the resulting Aggregate Balance forecast the same afternoon."),
    "decision_dates": {},
    "decision_dates_status": {
        2020: "NOT_APPLICABLE -- the Base Rate follows the FOMC by formula",
        2021: "NOT_APPLICABLE", 2022: "NOT_APPLICABLE", 2023: "NOT_APPLICABLE",
        2024: "NOT_APPLICABLE", 2025: "NOT_APPLICABLE",
        2026: "NOT_APPLICABLE -- and the empty row is the measurement. Any Hong Kong rate study "
              "must be built on the FOMC calendar and must SAY that it is measuring an imported "
              "decision, because the transmission lag and the DST-dependent announcement time "
              "are part of the mechanism",
    },
    "verification": "The formula above must be re-read from the HKMA's own Discount Window "
                    "circular before it is used to construct a Base Rate series; the precise "
                    "averaging window of the HIBOR leg has been described in more than one way "
                    "in public commentary and the circular is the authority.",
}


# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: dict[str, Any] = {
    "hibor": {
        "name": "HIBOR / 香港銀行同業拆息",
        "publisher": "the Hong Kong Association of Banks, calculated by the Treasury Markets "
                     "Association (香港財資市場公會)",
        "tenors": "overnight to twelve months",
        "published_local": "about 11:15 Hong Kong on each business day",
        "published_utc": "03:15 UTC",
        "note": "HIBOR is the OUTPUT of the Aggregate Balance, not an input to policy. That "
                "direction of causation is what makes the Aggregate Balance the leading series "
                "and HIBOR the confirming one.",
    },
    "cnh_hibor": {
        "name": "CNH HIBOR",
        "publisher": "Treasury Markets Association",
        "published_local": "about 11:15 Hong Kong",
        "published_utc": "03:15 UTC",
        "note": "Fixed in Hong Kong for a Chinese currency, at the same minute as HKD HIBOR. The "
                "two share a funding market and not a mechanism, which makes each a natural "
                "control for the other.",
    },
    "usd_hkd": {
        "name": "USDHKD spot",
        "bounds": "7.7500 to 7.8500 by the two Convertibility Undertakings",
        "note": "There is no daily fixing. The band itself is the reference, and the observable "
                "is POSITION WITHIN IT: `peg_band_position` returns that number and the regime "
                "label that goes with it.",
    },
    "dst": "NONE on the Hong Kong side. HKT is UTC+8 year-round. The US side DOES shift, so the "
           "interval between an FOMC announcement and the HKMA's Base Rate announcement is an "
           "hour longer in the northern winter.",
}

SETTLEMENT_CONVENTIONS: dict[str, Any] = {
    "spot": "T+2 through the HKD CHATS real-time gross settlement system",
    "cu_settlement": "a Convertibility Undertaking triggering settles T+2, so the Aggregate "
                     "Balance the market reads today reflects operations from two days ago -- a "
                     "SHORT BUT REAL LAG that any event study on the balance must respect",
    "equity_settlement": "T+2 at CCASS",
    "connect_settlement": "southbound settles on the Hong Kong cycle; the mainland leg settles "
                          "on its own, and the mismatch is funded in HKD",
    "ipo_subscription": "historically the largest recurring HKD liquidity event: a heavily "
                        "oversubscribed listing froze subscription money for days, drained the "
                        "Aggregate Balance and spiked HIBOR. THE FINI PLATFORM, introduced in "
                        "November 2023, replaced full prefunding with a much smaller "
                        "pre-committed amount and structurally shrank that squeeze -- so any "
                        "IPO-to-HIBOR study must be split at that date",
    "dividend_season": "mainland companies listed in Hong Kong pay dividends in HKD converted "
                       "from renminbi, concentrated in the northern summer; this is a recurring "
                       "HKD demand with a published per-company calendar",
}

EXCHANGES: dict[str, Any] = {
    "cash": {
        "name": "The Stock Exchange of Hong Kong (香港聯合交易所), part of HKEX",
        "hours_local": "09:30-12:00 and 13:00-16:00 Hong Kong",
        "hours_utc": "01:30-04:00 and 05:00-08:00 UTC",
        "pre_opening": "09:00-09:30 Hong Kong (01:00-01:30 UTC)",
        "closing_auction": "16:00-16:10 Hong Kong (08:00-08:10 UTC), reintroduced in 2017 after "
                           "being withdrawn in 2009",
        "price_limit": "NONE on the cash market. Hong Kong has no daily price limit, unlike the "
                       "mainland and unlike Korea -- which makes it the cleanest venue in the "
                       "region for measuring a shock's full size on the day it lands",
        "vcm": "a Volatility Control Mechanism applies to selected securities and index futures: "
               "a five-minute cooling-off period after a move beyond a threshold from a "
               "reference price. It is a pause, not a limit, and it does not truncate the move",
    },
    "derivatives": {
        "name": "Hong Kong Futures Exchange (香港期貨交易所), part of HKEX",
        "contracts": "Hang Seng Index (HSI) and Hang Seng China Enterprises Index (HSCEI) "
                     "futures and options; Hang Seng TECH futures",
        "hours_local": "09:15-12:00 and 13:00-16:30 day session, plus a T+1 after-hours session "
                       "roughly 17:15-03:00 Hong Kong",
        "expiry_rule": "THE BUSINESS DAY IMMEDIATELY PRECEDING THE LAST BUSINESS DAY OF THE "
                       "MONTH -- the second-last business day. Not Korea's second Thursday, not "
                       "Taiwan's third Wednesday, not the third Friday. It is the only "
                       "month-end-anchored expiry in this package, which means it moves with the "
                       "holiday calendar rather than with the weekday calendar",
        "settlement_price": "the average of quotations of the index taken at FIVE-MINUTE "
                            "INTERVALS through the expiry day. A whole-day average is an "
                            "extremely expensive thing to push, which is the honest prior "
                            "against a pinning effect here",
        "after_hours": "the T+1 session is where a US move is first priced into HSI, hours "
                       "before the Hong Kong cash market opens",
    },
    "connect": {
        "name": "Stock Connect (滬港通, 深港通, 港股通)",
        "role": "Hong Kong is the pipe. Northbound is foreign money into the mainland; "
                "southbound is mainland money into Hong Kong, and southbound has become the "
                "marginal bid for the Hong Kong market",
        "disclosure": "southbound turnover and CCASS holdings remain fully published; NORTHBOUND "
                      "REAL-TIME FLOW ENDED ON 2024-08-19, so the better-instrumented half of "
                      "the link is now the Hong Kong half",
    },
    "severe_weather": {
        "rule": "SINCE 2024-09-23 THE HONG KONG MARKET NO LONGER CLOSES FOR TYPHOON SIGNAL 8 OR "
                "BLACK RAINSTORM. Before that date a signal 8 hoisted in the morning closed the "
                "market for the session, which produced unscheduled, weather-driven closures "
                "several times a year",
        "why_it_is_here": "this is a hard microstructure break. Any intraday or gap study "
                          "spanning 2024-09-23 is pooling a market that could vanish for a day "
                          "at short notice with one that cannot, and Taiwan -- which still "
                          "closes for typhoons -- is the natural control for it",
    },
    "short_selling": {
        "rule": "designated securities only, with a tick rule; naked shorting prohibited",
        "disclosure": "the SFC publishes Aggregated Reportable Short Positions WEEKLY, as at "
                      "Friday and published the following Friday -- a one-week lag that makes it "
                      "a state variable rather than a signal",
    },
}

FISCAL_YEAR: dict[str, str] = {
    "government": "31 MARCH. Hong Kong is the only economy in this package with a non-calendar "
                  "fiscal year, and it shares 31 March with the United Kingdom and with Japan's "
                  "corporate year rather than with any of its neighbours",
    "corporate": "31 December for most listed companies, though mainland-incorporated issuers "
                 "follow the mainland calendar",
    "budget_cycle": "the Financial Secretary delivers the Budget (財政預算案) in late February, "
                    "conventionally on the last Wednesday of the month, for the fiscal year "
                    "beginning 1 April",
}
#: The framework's field is a bare MM-DD; FISCAL_YEAR above is why it is this one.
FISCAL_YEAR_END = "03-31"


# --------------------------------------------------------------------------- holidays
_HK_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-01": "一月一日 New Year's Day",
        "2024-02-10": "農曆年初一 Lunar New Year day 1",
        "2024-02-12": "農曆年初三 Lunar New Year day 3",
        "2024-02-13": "農曆年初四 Lunar New Year day 4",
        "2024-03-29": "耶穌受難節 Good Friday",
        "2024-04-01": "復活節星期一 Easter Monday",
        "2024-04-04": "清明節 Ching Ming Festival",
        "2024-05-01": "勞動節 Labour Day",
        "2024-05-15": "佛誕 Buddha's Birthday",
        "2024-06-10": "端午節 Tuen Ng Festival",
        "2024-07-01": "香港特別行政區成立紀念日 HKSAR Establishment Day",
        "2024-09-18": "中秋節翌日 the day after Mid-Autumn Festival",
        "2024-10-01": "國慶日 National Day",
        "2024-10-11": "重陽節 Chung Yeung Festival",
        "2024-12-25": "聖誕節 Christmas Day",
        "2024-12-26": "聖誕節後第一個周日 the first weekday after Christmas",
    },
    2025: {
        "2025-01-01": "一月一日 New Year's Day",
        "2025-01-29": "農曆年初一 Lunar New Year day 1",
        "2025-01-30": "農曆年初二 Lunar New Year day 2",
        "2025-01-31": "農曆年初三 Lunar New Year day 3",
        "2025-04-04": "清明節 Ching Ming Festival",
        "2025-04-18": "耶穌受難節 Good Friday",
        "2025-04-21": "復活節星期一 Easter Monday",
        "2025-05-01": "勞動節 Labour Day",
        "2025-05-05": "佛誕 Buddha's Birthday",
        "2025-07-01": "香港特別行政區成立紀念日 HKSAR Establishment Day",
        "2025-10-01": "國慶日 National Day",
        "2025-10-07": "中秋節翌日 the day after Mid-Autumn Festival",
        "2025-10-29": "重陽節 Chung Yeung Festival",
        "2025-12-25": "聖誕節 Christmas Day",
        "2025-12-26": "聖誕節後第一個周日 the first weekday after Christmas",
    },
    2026: {
        "2026-01-01": "一月一日 New Year's Day",
        "2026-02-17": "農曆年初一 Lunar New Year day 1",
        "2026-02-18": "農曆年初二 Lunar New Year day 2",
        "2026-02-19": "農曆年初三 Lunar New Year day 3",
        "2026-04-03": "耶穌受難節 Good Friday",
        "2026-04-06": "復活節星期一 Easter Monday",
        "2026-04-07": "清明節 Ching Ming Festival observed (5 April is a Sunday and 6 April is "
                      "already Easter Monday)",
        "2026-05-01": "勞動節 Labour Day",
        "2026-05-25": "佛誕 Buddha's Birthday observed (24 May is a Sunday)",
        "2026-06-19": "端午節 Tuen Ng Festival",
        "2026-07-01": "香港特別行政區成立紀念日 HKSAR Establishment Day",
        "2026-10-01": "國慶日 National Day",
        "2026-10-19": "重陽節 Chung Yeung Festival observed (18 October is a Sunday)",
        "2026-12-25": "聖誕節 Christmas Day",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": (
        "Hong Kong's general holidays come from three sources and the interaction is what makes "
        "them impossible to compute from a weekday rule. (1) FIXED SOLAR DATES: 1 January, "
        "1 May (勞動節), 1 July (香港特別行政區成立紀念日), 1 October (國慶日), 25 and 26 "
        "December. (2) LUNAR AND SOLAR-TERM DATES, tabulated here because they cannot be "
        "derived: 農曆年初一 to 初三 (the first three days of the first lunar month), 佛誕 (the "
        "eighth day of the fourth lunar month), 端午節 (the fifth of the fifth), 中秋節翌日 (the "
        "day AFTER the fifteenth of the eighth -- Hong Kong takes the day after, not the day "
        "itself), 重陽節 (the ninth of the ninth), and 清明節, which follows the solar term and "
        "falls on 4 or 5 April. (3) THE CHRISTIAN MOVEABLE FEASTS: 耶穌受難節 (Good Friday), the "
        "day after, and 復活節星期一 (Easter Monday), which follow the Western ecclesiastical "
        "calendar. On top of that, when a general holiday falls on a Sunday the following day "
        "that is not already a holiday becomes one -- which in 2026 pushes 清明節 past Easter "
        "Monday to 7 April. NOTE ALSO WHAT IS NO LONGER A RULE: before 2024-09-23 a typhoon "
        "signal 8 or black rainstorm closed the market for the session, and since that date it "
        "does not."),
    "authority": "the General Holidays Ordinance (公眾假期條例) and the HKEX trading calendar; "
                 "the two coincide for the cash market",
    "table": _HK_HOLIDAYS,
    "status": {2024: "GAZETTED", 2025: "GAZETTED",
               2026: "DERIVED_FROM_RULE -- the lunar anchors (農曆年初一 2026-02-17, 佛誕 "
                     "2026-05-24, 中秋節 2026-09-25, 重陽節 2026-10-18), the Easter dates "
                     "(Easter Sunday 2026-04-05) and the Sunday-substitution law are applied "
                     "here. The 清明節 placement on 7 April in particular is a DERIVATION from "
                     "the substitution rule colliding with Easter Monday and must be confirmed "
                     "against the gazette before any 2026 event window relies on it"},
    "market_effect": (
        "USDHKD keeps trading offshore through these closures, but the peg means the closure "
        "barely matters for it: a bounded variable with two hard barriers cannot gap far. Where "
        "the Hong Kong holiday calendar DOES matter is the expiry rule -- because HSI and HSCEI "
        "settle on the second-last BUSINESS day of the month, every holiday at a month end "
        "moves the expiry, and a study anchored on a weekday would silently measure the wrong "
        "session. It also matters for Stock Connect, which closes the link when either market is "
        "shut, on a calendar of its own."),
    "callable": "countries.hk.pack:holidays",
}


def holidays(year: int) -> dict[str, str]:
    """The Hong Kong market-closure table for one year. `{}` for an untabulated year."""
    return holiday_table(HOLIDAYS_RULE, year)


def _is_closed(day: date) -> bool:
    """True when the Hong Kong cash market is shut: a weekend or a gazetted general holiday."""
    return day.weekday() >= 5 or day.isoformat() in holidays(day.year)


def hk_expiry_dates(year: int) -> tuple[dict[str, Any], ...]:
    """HSI and HSCEI expiries for a year, by the SECOND-LAST-BUSINESS-DAY rule.

    This is code and not a table because the rule is month-end anchored: it MOVES with the
    holiday calendar rather than with the weekday calendar, so a Christmas or a Lunar New Year
    landing near a month end shifts the expiry in a way no weekday rule can express. A study
    that anchored on "the second-last weekday" would be measuring the wrong session several
    times a year, and that is exactly the error this function exists to prevent.
    """
    rows: list[dict[str, Any]] = []
    for month in range(1, 13):
        last = date(year + (month == 12), month % 12 + 1, 1).toordinal() - 1
        opens: list[int] = []
        ordinal = last
        while len(opens) < 2 and ordinal > last - 20:
            day = date.fromordinal(ordinal)
            if not _is_closed(day):
                opens.append(ordinal)
            ordinal -= 1
        if len(opens) < 2:
            continue
        rows.append({"date": date.fromordinal(opens[1]).isoformat(), "month": month,
                     "last_business_day": date.fromordinal(opens[0]).isoformat(),
                     "settlement": "the average of index quotations taken at five-minute "
                                   "intervals through the expiry day"})
    return tuple(rows)


# --------------------------------------------------------------------------- the peg mechanic
def peg_band_position(spot: float) -> dict[str, Any]:
    """Where USDHKD sits inside the Convertibility Zone, and what that regime is called.

    THE ONE NUMBER EVERY HONG KONG DOMAIN CONDITIONS ON. USDHKD is not a random walk: it is a
    bounded variable with two hard barriers that a public institution is obliged to defend, so
    the informative coordinate is not the return but the DISTANCE TO THE BARRIER. This function
    returns that distance in pips on both sides, the position as a fraction of the band, and a
    regime label -- and it refuses to silently normalise a spot outside the band, because a print
    outside 7.7500 to 7.8500 is either a bad tick or the end of the peg, and those must never be
    confused with each other.

    Regime labels are deliberately coarse: STRONG_SIDE and WEAK_SIDE mean the undertaking is at
    or through its trigger; STRONG_APPROACH and WEAK_APPROACH mean within 100 pips of it, which
    is where the HKMA has historically begun to operate; MID_ZONE is everything else.
    """
    try:
        px = float(spot)
    except (TypeError, ValueError):
        return {"measured": False, "why": f"spot {spot!r} is not a number", "regime": "UNMEASURED"}
    if px != px or px <= 0:  # NaN (which is never equal to itself) or nonsense
        return {"measured": False, "why": f"spot {spot!r} is not a usable price",
                "regime": "UNMEASURED"}
    width = WEAK_SIDE_CU - STRONG_SIDE_CU
    to_strong = (px - STRONG_SIDE_CU) / PIP
    to_weak = (WEAK_SIDE_CU - px) / PIP
    position = (px - STRONG_SIDE_CU) / width
    if px < STRONG_SIDE_CU or px > WEAK_SIDE_CU:
        regime = "OUTSIDE_BAND"
    elif to_strong <= 0.5:
        regime = "STRONG_SIDE"
    elif to_weak <= 0.5:
        regime = "WEAK_SIDE"
    elif to_strong <= 100.0:
        regime = "STRONG_APPROACH"
    elif to_weak <= 100.0:
        regime = "WEAK_APPROACH"
    else:
        regime = "MID_ZONE"
    return {"measured": True, "spot": px, "strong_side": STRONG_SIDE_CU,
            "weak_side": WEAK_SIDE_CU, "pips_to_strong": round(to_strong, 2),
            "pips_to_weak": round(to_weak, 2), "band_position": round(position, 6),
            "regime": regime,
            "note": ("OUTSIDE_BAND is never normalised away: a print outside 7.7500-7.8500 is "
                     "either a bad tick or the end of the currency board, and a function that "
                     "clipped it would hide the only observation that would ever matter."
                     if regime == "OUTSIDE_BAND" else
                     "distance to the undertaking, not the return, is the informative "
                     "coordinate for a bounded variable with two reflecting barriers")}


# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"id": "hkma_aggregate_balance",
     "name": "HKMA 總結餘 -- the Aggregate Balance, daily",
     "covers": "the sum of licensed banks' clearing balances at the HKMA, plus the next day's "
               "forecast",
     "frequency": "daily", "lag": "the forecast is published the same afternoon; the outturn "
                                  "the next morning",
     "root": "hkma.gov.hk", "licence": "free, public",
     "note": "THE FLAGSHIP SERIES OF THIS PACK and the best intervention data anywhere in this "
             "package. Every Convertibility Undertaking triggering shows up here with a T+2 lag "
             "and no discretion about whether it is disclosed."},
    {"id": "hkma_cu_triggers",
     "name": "HKMA Convertibility Undertaking triggerings",
     "covers": "each operation, its side and its size, announced on the day",
     "frequency": "event", "lag": "same day",
     "root": "hkma.gov.hk", "licence": "free, public",
     "note": "Korea discloses intervention quarterly and three months late; China not at all. "
             "Hong Kong announces it the same day, with the amount. That asymmetry is why the "
             "HK pack can run event studies the KR and CN packs cannot."},
    {"id": "hkex_index_futures_oi",
     "name": "HKEX HSI and HSCEI futures and options open interest",
     "covers": "daily open interest and turnover by contract and expiry month",
     "frequency": "daily", "lag": "same day after the close",
     "root": "hkex.com.hk", "licence": "free, public",
     "note": "The expiry-month distribution of open interest is what tells you whether a "
             "second-last-business-day effect has anything behind it."},
    {"id": "sfc_short_positions",
     "name": "SFC Aggregated Reportable Short Positions",
     "covers": "aggregate short interest in reportable securities",
     "frequency": "weekly", "lag": "one week -- as at Friday, published the following Friday",
     "root": "sfc.hk", "licence": "free, public",
     "note": "A one-week lag makes this a state variable and never a signal, and it is recorded "
             "as such rather than used as though it were current."},
    {"id": "ccass_holdings",
     "name": "CCASS shareholding search",
     "covers": "holdings of every listed security by clearing participant, daily",
     "frequency": "daily", "lag": "one business day",
     "root": "hkex.com.hk", "licence": "free, public",
     "note": "The southbound participant's holdings are visible here by name, which makes "
             "mainland ownership of Hong Kong equity one of the most granular free flow series "
             "in Asia."},
    {"id": "connect_southbound",
     "name": "Stock Connect southbound turnover and quota",
     "covers": "mainland buying and selling of Hong Kong shares",
     "frequency": "daily", "lag": "same day",
     "root": "hkex.com.hk", "licence": "free, public",
     "note": "Unaffected by the 2024-08-19 northbound disclosure change, which makes the Hong "
             "Kong half of the link the better-instrumented one."},
    {"id": "hkma_monetary_base",
     "name": "HKMA Monetary Base components and Exchange Fund Bills and Notes outstanding",
     "covers": "certificates of indebtedness, notes in circulation, the Aggregate Balance and "
               "outstanding Exchange Fund paper",
     "frequency": "daily and monthly", "lag": "one business day",
     "root": "hkma.gov.hk", "licence": "free, public",
     "note": "Exchange Fund Bill issuance drains the Aggregate Balance WITHOUT any Convertibility "
             "Undertaking, so a fall in the balance is not always an intervention -- separating "
             "the two is required before any event study on the balance means anything."},
    {"id": "cftc_cot_absent",
     "name": "CFTC Commitments of Traders -- NO HKD CONTRACT EXISTS",
     "covers": "nothing from Hong Kong",
     "frequency": "n/a", "lag": "n/a",
     "root": "cftc.gov", "licence": "free, public",
     "note": "DECLARED ABSENT BY NAME. No Hong Kong dollar futures contract exists in the CFTC's "
             "reports. It matters less here than in the other packs: the Aggregate Balance is a "
             "better positioning proxy than a COT report would be, because it measures the "
             "consequence of the flow rather than a survey of who holds what."},
)

# --------------------------------------------------------------------------- terminology
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "core": ("港元", "港幣", "聯繫匯率", "聯匯制度", "匯率", "美元", "貨幣發行局",
             "Hong Kong dollar", "linked exchange rate", "currency board"),
    "hk_peg_band": ("強方兌換保證", "弱方兌換保證", "兌換範圍", "七點七五", "七點八五",
                    "觸發", "保衛港元", "脫鈎", "聯匯受壓",
                    "strong-side convertibility undertaking", "weak-side convertibility "
                    "undertaking"),
    "hk_aggregate_balance": ("總結餘", "銀行體系結餘", "貨幣基礎", "外匯基金票據",
                             "流動性收緊", "注資", "回籠", "aggregate balance",
                             "exchange fund bills"),
    "hk_hibor_carry": ("香港銀行同業拆息", "拆息", "隔夜拆息", "一個月拆息", "息差",
                       "套息交易", "資金成本", "最優惠利率", "HIBOR", "carry trade"),
    "hk_cu_intervention": ("金管局入市", "承接港元", "沽出港元", "干預", "接錢",
                           "銀行體系結餘下降", "HKMA intervention"),
    "hk_connect_flows": ("港股通", "滬港通", "深港通", "北水", "南下資金", "淨買入",
                         "額度", "成交額", "southbound", "northbound"),
    "hk_index_expiry": ("期指結算", "結算日", "月結", "未平倉合約", "高水", "低水",
                        "夜期", "恒指期貨", "國企指數期貨", "settlement day"),
    "hk_ah_premium": ("A股", "H股", "AH股溢價", "折讓", "同股不同價", "兩地上市",
                      "A/H premium"),
    "hk_ipo_liquidity": ("新股", "招股", "孖展", "認購", "超額認購", "凍結資金", "暗盤",
                         "上市首日", "FINI", "margin subscription"),
    "hk_china_transmission": ("內地政策", "刺激措施", "中央", "人民銀行", "內房股",
                              "中資股", "國企股", "政策紅利"),
    "hk_microstructure_regimes": ("收市競價時段", "市場波動調節機制", "沽空", "沽空比率",
                          "八號風球", "黑色暴雨", "惡劣天氣交易", "停市", "closing auction"),
    "hk_us_rate_import": ("聯儲局", "加息", "減息", "基本利率", "議息", "輸入式緊縮",
                          "美息", "FOMC", "base rate"),
    "hk_property_rates": ("樓市", "按揭", "供樓", "封頂息", "地產股", "住宅成交",
                          "負資產", "辣招", "mortgage"),
    "hk_fiscal_confound": ("財政預算案", "財政儲備", "外匯基金", "財政司司長", "赤字",
                           "發債", "庫房 存款", "外匯基金票據 發行", "budget",
                           "fiscal reserves"),
}


# --------------------------------------------------------------------------- source classes
#: GROUNDS THIS PACK REFUSES TO CRAWL, named rather than silently absent, and surfaced in the
#: `source_graph` layer because the edges a graph deliberately does not traverse are part of it.
REFUSED_SOURCES: tuple[dict[str, str], ...] = (
    {"ground": "crypto-exchange order books, venue APIs and venue-native feeds",
     "why": "MT5 universe mandate (2026-08-18): no crypto-exchange ground is ever hunted again"},
    {"ground": "paywalled vendor terminal content and its redistribution",
     "why": "licence; the desk holds no redistribution right"},
    {"ground": "single-name Hong Kong equity hypothesis mining",
     "why": "two-lane order (2026-09-06): single names are traded on news and never hunted for "
            "statistical hypotheses"},
)

SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    source_class("hk_official", "The HKMA, the statistics department and the fiscal authority",
                 layer="official",
                 roots=("hkma.gov.hk", "hkma.gov.hk open data API", "censtatd.gov.hk",
                        "info.gov.hk/gia", "budget.gov.hk", "rvd.gov.hk", "sfc.hk"),
                 queries=("總結餘", "弱方兌換保證", "強方兌換保證", "外匯基金票據", "基本利率",
                          "貨幣基礎", "半年度貨幣與金融穩定報告", "財政儲備", "差餉物業估價署"),
                 languages=("zh-Hant", "en"), access_label="OPEN_DATA",
                 credibility="AUTHORITATIVE", predictive_state="UNTESTED",
                 licence="free, public, with open data APIs",
                 notes="THE MOST TRANSPARENT MONETARY AUTHORITY IN THIS PACKAGE. The HKMA "
                       "publishes the Aggregate Balance daily with a next-day forecast, and it "
                       "announces every Convertibility Undertaking triggering on the day with "
                       "the amount. Korea discloses intervention quarterly and three months "
                       "late; China not at all. That asymmetry is why this pack can run event "
                       "studies the others cannot."),
    source_class("hk_institutional", "HKEX, the TMA, CCASS and the clearing infrastructure",
                 layer="institutional",
                 roots=("hkex.com.hk", "hkexnews.hk", "tma.org.hk", "hsi.com.hk",
                        "hkex.com.hk CCASS shareholding search"),
                 queries=("香港銀行同業拆息", "港股通 每日額度", "中央結算系統 持股紀錄",
                          "期指未平倉", "恒生 AH股溢價指數", "新股 招股", "沽空 報告",
                          "市場波動調節機制"),
                 languages=("zh-Hant", "en"), access_label="OPEN_DATA",
                 credibility="AUTHORITATIVE", predictive_state="UNTESTED",
                 licence="free, public",
                 notes="tma.org.hk is the authoritative HIBOR and CNH HIBOR root; CCASS is the "
                       "most granular free flow series in Asia, showing mainland ownership of "
                       "Hong Kong equity by clearing participant, by security, daily."),
    source_class("hk_academic", "The HKIMR literature and the university repositories",
                 layer="academic",
                 roots=("hkimr.org", "papers.ssrn.com", "hub.hku.hk", "repository.hkust.edu.hk",
                        "repository.lib.cuhk.edu.hk"),
                 queries=("聯繫匯率制度 研究", "linked exchange rate currency board",
                          "aggregate balance HIBOR transmission", "A/H premium capital controls",
                          "Hong Kong dollar peg speculative attack", "港元 聯匯 壓力測試"),
                 languages=("en", "zh-Hant"), access_label="PUBLIC",
                 credibility="RELIABLE", predictive_state="UNTESTED",
                 licence="free working papers and open repositories",
                 notes="Unusually good and unusually SPECIFIC: the HKIMR literature models the "
                       "exact Aggregate-Balance-to-HIBOR transmission this pack measures, which "
                       "means the prior here is better informed than anywhere else in the "
                       "package -- and that is why several HK edges carry MEASURED_ELSEWHERE "
                       "rather than HYPOTHESIS."),
    source_class("hk_practitioner", "Hong Kong practitioner writing, newsletters and code",
                 layer="practitioner",
                 roots=("github.com (HKEX and CCASS data wrappers)", "gitee.com mirrors",
                        "aastocks.com and etnet.com.hk analysis pages",
                        "webb-site.com (David Webb's corporate-governance database)"),
                 queries=("港股 量化", "恒指 期貨 策略", "CCASS 分析", "窩輪 牛熊證 對沖",
                          "孖展 息率", "拆息 上升 影響", "webb-site 數據"),
                 languages=("zh-Hant", "en"), access_label="PUBLIC_WITH_TERMS",
                 credibility="UNRELIABLE", predictive_state="UNTESTED",
                 licence="per-repository and per-site; respect each licence",
                 notes="Credibility is UNRELIABLE and every row is KEPT AT LOW WEIGHT rather "
                       "than dropped: a published strategy write-up states entry and exit rules, "
                       "and an exact rule is testable regardless of whether the claimed equity "
                       "curve is real. CCASS and Connect endpoints change without notice, so an "
                       "existing wrapper is cheaper to read than to rediscover, and webb-site is "
                       "a genuinely unusual asset -- a long-running independent structured "
                       "database of Hong Kong corporate relationships with no counterpart "
                       "elsewhere in Asia."),
    source_class("hk_retail_ecology", "Hong Kong retail forums and their vernacular",
                 layer="retail_ecology",
                 roots=("lihkg.com (財經台)", "discuss.com.hk", "uwants.com",
                        "forum.hkgolden.com"),
                 queries=("北水 掃貨", "抽新股", "孖展 抽飛", "期指 夜期", "大時代",
                          "供股 供唔供", "拆息 抽高", "聯匯 爆煲"),
                 languages=("zh-Hant",), access_label="PUBLIC_SOCIAL",
                 credibility="FRINGE", predictive_state="UNTESTED",
                 licence="public web; VERBATIM CLAIMS only, never personal data, respecting "
                         "robots and rate limits",
                 notes="FRINGE AND KEPT AT LOW WEIGHT, never dropped. 聯匯爆煲 -- the recurring "
                       "claim that the peg is about to break -- has been wrong every single time "
                       "since 1983 and is exactly the kind of CONTRADICTED material worth "
                       "keeping: the dates on which it spikes are a sentiment observable even "
                       "though the claim itself has never once been right."),
    source_class("hk_app_ecosystem", "Hong Kong brokerage and market-data apps",
                 layer="app_ecosystem",
                 roots=("app listings and review text for the major Hong Kong brokerage and "
                        "quote apps", "aastocks.com and etnet.com.hk mobile properties"),
                 queries=("港股 交易 app", "免佣 證券 app", "新股 認購 app", "報價 app 延遲"),
                 languages=("zh-Hant", "en"), access_label="ACCESS_UNCLEAR",
                 credibility="UNKNOWN", predictive_state="UNTESTED",
                 licence="app-store listing text is public; usage panels are vendor products "
                         "the desk does not subscribe to, and the store terms restrict machine "
                         "extraction",
                 machine_use_allowed=True,
                 notes="REGISTERED AND NOT SCRAPED, and it is the THINNEST layer in this pack. "
                       "Hong Kong's retail broking has consolidated into cross-border platforms "
                       "whose user bases are mostly mainland, so an app signal here measures a "
                       "mainland population rather than a Hong Kong one -- which would make it "
                       "a misattributed variable even if the data were available."),
    source_class("hk_media", "The Hong Kong financial press, Chinese and English",
                 layer="media",
                 roots=("hkej.com (信報)", "hket.com (香港經濟日報)", "mpfinance.com (明報財經)",
                        "scmp.com", "inmediahk.net", "news.now.com/home/finance"),
                 queries=("金管局 入市", "承接港元", "拆息 抽升", "聯匯 保衛戰", "北水 南下",
                          "新股 凍資", "期指 結算 日", "八號風球 停市"),
                 languages=("zh-Hant", "en"), access_label="PUBLIC_WITH_TERMS",
                 credibility="RELIABLE", predictive_state="NARRATIVE_FEATURE",
                 licence="public headlines and article text; respect robots and rate limits",
                 notes="THE CHINESE-LANGUAGE PRESS IS NOT A TRANSLATION OF THE ENGLISH ONE. "
                       "信報 and 香港經濟日報 carry the HIBOR, mortgage-cap and IPO-margin "
                       "mechanics in operational detail that the English coverage summarises "
                       "away, and those mechanics are precisely what this pack's domains need."),
    source_class("hk_archive", "Gazettes, rule-change notices and web archives",
                 layer="archive",
                 roots=("web.archive.org", "gld.gov.hk (公眾假期 gazette)",
                        "hkex.com.hk historical circulars and trading-calendar notices",
                        "hkma.gov.hk historical press releases and Quarterly Bulletins"),
                 queries=("公眾假期 憲報", "惡劣天氣 交易 安排", "收市競價交易時段 實施",
                          "FINI 新股結算平台", "兌換保證 觸發 紀錄", "市場波動調節機制 推出"),
                 languages=("zh-Hant", "en"), access_label="PUBLIC_ARCHIVE",
                 credibility="AUTHORITATIVE", predictive_state="UNTESTED",
                 licence="free, public",
                 notes="THE LAYER THAT MAKES THIS PACK'S ERA TABLE CHECKABLE, and Hong Kong has "
                       "more dated microstructure breaks than any other country here: the 2017 "
                       "closing auction, the 2023 FINI platform, the 2024-09-23 end of weather "
                       "closures, every Convertibility Undertaking triggering since 2005. Each "
                       "has a primary notice with a date, and an era boundary taken from memory "
                       "instead of from the notice is how an era table goes quietly wrong."),
    source_class("hk_physical_economy", "Port, air cargo, retail footfall and the real economy",
                 layer="physical_economy",
                 roots=("mardep.gov.hk (海事處 port container throughput)",
                        "hongkongairport.com air cargo statistics",
                        "censtatd.gov.hk retail sales and visitor arrivals",
                        "immd.gov.hk cross-boundary passenger traffic"),
                 queries=("貨櫃 吞吐量", "機場 貨運量", "訪港旅客 人次", "零售業 銷貨額",
                          "過境 人次", "北上消費"),
                 languages=("zh-Hant", "en"), access_label="OPEN_DATA",
                 credibility="AUTHORITATIVE", predictive_state="UNTESTED",
                 licence="free, public",
                 notes="Hong Kong's physical economy is a SERVICES one, so the useful series are "
                       "cross-boundary passenger traffic, visitor arrivals and air cargo rather "
                       "than blast-furnace rates. Cross-boundary traffic in particular is a "
                       "daily, free, high-frequency read on the integration this pack's "
                       "southbound and A/H domains are about."),
    source_class("hk_source_graph", "How new Hong Kong grounds are found, and what is refused",
                 layer="source_graph",
                 roots=("github.com topic and dependency graphs for HKEX data packages",
                        "hkimr.org and SSRN citation graphs",
                        "hkexnews.hk document cross-reference structure",
                        "webb-site.com relationship graph"),
                 queries=("HKEX API", "港交所 數據 下載", "CCASS 爬蟲", "恒指 成份股 歷史",
                          "hkma api 總結餘"),
                 languages=("zh-Hant", "en"), access_label="PUBLIC_WITH_TERMS",
                 credibility="UNKNOWN", predictive_state="UNTESTED",
                 licence="public web; used at human rates where terms restrict automation",
                 notes=f"THE META LAYER: it finds the next ground rather than data. webb-site's "
                       f"relationship graph is itself a source graph over Hong Kong corporate "
                       f"structure, which is unusual enough to belong in this layer rather than "
                       f"among the practitioner rows. Refused here: "
                       f"{'; '.join(r['ground'] for r in REFUSED_SOURCES)}. Reasons are in "
                       f"REFUSED_SOURCES and none of those grounds is named, subscribed or "
                       f"crawled anywhere in this pack."),
)


# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    dataset("hkma_aggregate_balance",
            source="HKMA 總結餘 / Aggregate Balance",
            coverage="the daily Aggregate Balance and the next-day forecast, plus the full "
                     "Monetary Base decomposition",
            frequency="daily",
            publication_lag_days=0.5,
            revisions="the forecast is superseded by the outturn; both vintages matter and the "
                      "desk must store the forecast, because that is what the market traded on",
            licence="free, public",
            history_from="2005-05",
            pit_feasible=True,
            assets=("USDHKD", "HK50", "CHINAH"),
            mechanism_families=("intervention", "liquidity", "carry"),
            how_to_fetch="hkma.gov.hk open data API; the forecast lands in the Hong Kong "
                         "afternoon and the outturn the next morning"),
    dataset("hkma_cu_triggers",
            source="HKMA Convertibility Undertaking announcements",
            coverage="each triggering, its side (strong or weak) and its size in HKD",
            frequency="event",
            publication_lag_days=0.0,
            revisions="none",
            licence="free, public",
            history_from="2005-05",
            pit_feasible=True,
            assets=("USDHKD", "HK50"),
            mechanism_families=("intervention", "peg_stress", "liquidity"),
            how_to_fetch="hkma.gov.hk press releases, same day. THE ONLY SAME-DAY DISCLOSED "
                         "INTERVENTION IN THIS PACKAGE"),
    dataset("tma_hibor",
            source="Treasury Markets Association HIBOR fixings",
            coverage="overnight to twelve-month HKD HIBOR, and CNH HIBOR on the same page",
            frequency="daily",
            publication_lag_days=0.0,
            revisions="none",
            licence="free, public",
            history_from="2006-01",
            pit_feasible=True,
            assets=("USDHKD", "HK50", "USDCNH"),
            mechanism_families=("carry", "liquidity", "funding"),
            how_to_fetch="tma.org.hk, about 11:15 Hong Kong = 03:15 UTC"),
    dataset("hk_peg_band_position",
            source="derived from the broker's own USDHKD tape and the two Convertibility "
                   "Undertakings",
            coverage="distance to each undertaking in pips, the band position and the regime "
                     "label, per bar",
            frequency="intraday",
            publication_lag_days=0.0,
            revisions="none",
            licence="the desk's own tape",
            history_from="whatever USDHKD history this box holds",
            pit_feasible=True,
            assets=("USDHKD", "HK50"),
            mechanism_families=("peg_stress", "bounded_process", "carry"),
            how_to_fetch="computed here by peg_band_position(); the two barriers are constants "
                         "fixed in 2005 and need no external source at all, which makes this the "
                         "single most point-in-time-safe series in the whole package"),
    dataset("hkex_connect_southbound",
            source="HKEX Stock Connect southbound statistics and CCASS holdings",
            coverage="daily southbound turnover, quota use and per-security holdings",
            frequency="daily",
            publication_lag_days=0.5,
            revisions="none",
            licence="free, public",
            history_from="2014-11",
            pit_feasible=True,
            assets=("HK50", "CHINAH", "USDHKD"),
            mechanism_families=("foreign_flow", "capital_account", "risk_appetite"),
            how_to_fetch="hkex.com.hk; unaffected by the 2024-08-19 northbound change"),
    dataset("hkex_derivatives_oi",
            source="HKEX daily market report for HSI and HSCEI futures and options",
            coverage="open interest and turnover by contract month",
            frequency="daily",
            publication_lag_days=0.5,
            revisions="none",
            licence="free, public",
            history_from="2000-01",
            pit_feasible=True,
            assets=("HK50", "CHINAH"),
            mechanism_families=("positioning", "expiry", "hedging_flow"),
            how_to_fetch="hkex.com.hk daily market reports"),
    dataset("sfc_short_positions",
            source="SFC Aggregated Reportable Short Positions",
            coverage="aggregate short interest in reportable securities",
            frequency="weekly",
            publication_lag_days=7.0,
            revisions="none",
            licence="free, public",
            history_from="2012-06",
            pit_feasible=True,
            assets=("HK50", "CHINAH"),
            mechanism_families=("positioning", "crowding"),
            how_to_fetch="sfc.hk; as at Friday, published the following Friday -- the lag is the "
                         "defining property and the series must never be aligned to its as-at "
                         "date in a backtest"),
    dataset("hk_ah_premium",
            source="Hang Seng Indexes: the Stock Connect China AH Premium Index (HSAHP)",
            coverage="the average premium of A shares over their H-share lines, daily",
            frequency="daily",
            publication_lag_days=0.5,
            revisions="none",
            licence="free headline level, published daily",
            history_from="2014-11",
            pit_feasible=True,
            assets=("CHINAH", "HK50", "USDCNH"),
            mechanism_families=("capital_control_stress", "relative_value", "risk_appetite"),
            how_to_fetch="hsi.com.hk index pages. THE PREMIUM CANNOT BE ARBITRAGED AWAY: the two "
                         "lines are not fungible and the capital account stands between them, "
                         "which is why a persistent gap is information rather than a free lunch"),
    dataset("hk_ipo_pipeline",
            source="HKEX new listings and the FINI platform",
            coverage="listing dates, deal sizes, subscription multiples and the prefunding regime",
            frequency="event",
            publication_lag_days=0.0,
            revisions="none",
            licence="free, public",
            history_from="2010-01",
            pit_feasible=True,
            assets=("USDHKD", "HK50"),
            mechanism_families=("liquidity", "funding", "microstructure_regime"),
            how_to_fetch="hkexnews.hk. SPLIT AT 2023-11: FINI replaced full prefunding with a "
                         "pre-committed model and structurally shrank the IPO HIBOR squeeze, so "
                         "an IPO-to-HIBOR estimate pooled across that date is an average of two "
                         "different market designs"),
    dataset("censtatd_macro",
            source="Census and Statistics Department",
            coverage="CPI, retail sales, trade, GDP and the labour market",
            frequency="monthly and quarterly",
            publication_lag_days=30.0,
            revisions="standard national-accounts revisions",
            licence="free, public",
            history_from="1990-01",
            pit_feasible=False,
            assets=("HK50",),
            mechanism_families=("macro_state",),
            how_to_fetch="censtatd.gov.hk. pit_feasible is FALSE because the archive is restated "
                         "in place and the desk would have to build its own vintage store"),
    dataset("hk_severe_weather_regime",
            source="HKEX and Hong Kong Observatory announcements",
            coverage="the dates of weather-driven market closures, and the 2024-09-23 rule change",
            frequency="event",
            publication_lag_days=0.0,
            revisions="none",
            licence="free, public",
            history_from="2010-01",
            pit_feasible=True,
            assets=("HK50", "CHINAH"),
            mechanism_families=("microstructure_regime", "liquidity", "calendar"),
            how_to_fetch="hkex.com.hk notices. Before 2024-09-23 a signal 8 closed the market "
                         "for the session; since then it does not, and TAIWAN -- which still "
                         "closes for typhoons -- is the natural control for the change"),
    dataset("hk_expiry_calendar",
            source="derived from the HKEX rule and this pack's holiday table",
            coverage="HSI and HSCEI monthly expiries, 2024 to 2026",
            frequency="monthly",
            publication_lag_days=0.0,
            revisions="none",
            licence="derived on this desk",
            history_from="2024-01",
            pit_feasible=True,
            assets=("HK50", "CHINAH"),
            mechanism_families=("expiry", "calendar"),
            how_to_fetch="hk_expiry_dates(); the second-last BUSINESS day moves with the holiday "
                         "calendar, so a weekday anchor is wrong several times a year"),
)


# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    actor("香港金融管理局 -- the HKMA as currency board operator",
          holds="the Exchange Fund, whose foreign reserves back the entire monetary base at a "
                "ratio it publishes",
          forced_to=("buy or sell Hong Kong dollars whenever a Convertibility Undertaking is hit "
                     "-- it is an OBLIGATION, not a choice",
                     "let the Aggregate Balance and therefore HIBOR absorb the adjustment",
                     "accept whatever policy rate the Federal Reserve sets"),
          when="automatically, at 7.7500 and at 7.8500, at any hour the market trades",
          information=("the size of the order flow hitting the undertaking before it is "
                       "announced, which is a lead of minutes rather than days"),
          constraints=("the two undertakings, which are public commitments it has never broken",
                       "no independent interest-rate instrument at all",
                       "a backing ratio it publishes and must maintain"),
          instruments=("USDHKD spot at the two undertakings",
                       "Exchange Fund Bills and Notes, which drain the balance without touching "
                       "the undertakings"),
          counterparties=("the licensed banks, which are the only eligible counterparties"),
          observables=("每日總結餘, daily",
                       "each triggering, announced the same day with its size",
                       "Exchange Fund paper outstanding"),
          impact="it converts an exchange-rate pressure into an interest-rate adjustment, every "
                 "time, mechanically. The currency cannot move past the barrier, so the pressure "
                 "has to come out somewhere else, and HIBOR is where",
          persistence="the linked rate has held since 1983 and the two-sided band since 2005; a "
                      "break would be the single largest regime change in this package and "
                      "nothing in the current mechanism suggests one",
          falsifier="if Aggregate Balance changes carry no information for subsequent HIBOR "
                    "moves, the transmission chain this pack is built on does not operate and "
                    "every HK domain downstream of it is empty",
          notes="The only actor in this package whose intervention is disclosed on the day it "
                "happens, with the amount."),
    actor("持牌銀行 -- the licensed banks as the undertakings' counterparties",
          holds="clearing balances at the HKMA that in aggregate ARE the Aggregate Balance",
          forced_to=("quote in HKD under their licences",
                     "fund a loan book whose marginal cost is HIBOR",
                     "manage capital and liquidity ratios against a balance they do not control"),
          when="continuously; the funding squeeze concentrates at quarter end, at year end and "
               "around large IPO settlements",
          information=("their own client flow, which is the earliest read on HKD demand"),
          constraints=("regulatory liquidity ratios",
                       "a deposit base that is finite and that the Aggregate Balance bounds",
                       "prime-rate stickiness: they change the best lending rate slowly even "
                       "when HIBOR moves fast, which is itself a documented asymmetry"),
          instruments=("HKD interbank lending", "USDHKD spot and forwards",
                       "Exchange Fund paper as collateral"),
          counterparties=("the HKMA", "each other", "corporate and mortgage borrowers"),
          observables=("HIBOR at 03:15 UTC across tenors",
                       "the gap between HIBOR and the best lending rate",
                       "deposit growth in the monthly statistics"),
          impact="they transmit the Aggregate Balance into the price of money, with a lag and an "
                 "asymmetry -- HIBOR rises faster than it falls when the balance shrinks",
          persistence="structural; the asymmetry has been stable across peg cycles",
          falsifier="if HIBOR shows no relation to the level or the change of the Aggregate "
                    "Balance, after controlling for US rates, the banks are not the transmission "
                    "and the chain breaks at its second link",
          notes="The second link of the chain, and the one this desk cannot trade."),
    actor("南下資金 -- mainland southbound investors in Hong Kong equity",
          holds="Hong Kong-listed shares bought with renminbi converted at settlement",
          forced_to=("convert renminbi into Hong Kong dollars to settle every purchase",
                     "operate within the daily southbound quota",
                     "buy only the eligible list, which concentrates the flow"),
          when="continuously; surges when mainland yields fall and when the A/H premium is wide",
          information=("mainland sentiment before it appears in mainland prices"),
          constraints=("the RMB 42bn daily quota",
                       "eligibility rules on which Hong Kong names may be bought",
                       "a dividend tax treatment that differs from the A line"),
          instruments=("Hong Kong-listed shares through the link", "HKD at settlement"),
          counterparties=("Hong Kong market makers", "foreign holders selling to them"),
          observables=("daily southbound turnover and quota use",
                       "CCASS holdings by the southbound participant, per security, daily",
                       "the A/H premium index"),
          impact="the marginal buyer of Hong Kong equity in recent years, and a structural HKD "
                 "purchase at settlement that pushes USDHKD toward the STRONG side",
          persistence="structural and growing while mainland domestic yields stay low",
          falsifier="if southbound turnover has no relation to HK50 and CHINAH returns and none "
                    "to the USDHKD band position, the mainland bid is not marginal in either "
                    "market and this actor is decoration",
          notes="The mechanical link between the CN and HK packs. Both packs carry the edge, "
                "deliberately, rather than either claiming it alone."),
    actor("套息交易者 -- HKD carry traders",
          holds="short HKD, long USD positions funded at HIBOR when HIBOR is below US rates",
          forced_to=("close the position when the carry inverts or the funding cost jumps",
                     "accept a bounded profit: the currency cannot move past 7.8500, so the "
                     "trade's upside is capped by law and its carry is the whole return"),
          when="whenever the HIBOR-SOFR spread is wide enough to pay; unwinds when the Aggregate "
               "Balance shrinks and HIBOR spikes",
          information=("nothing privileged; the carry is public and the barrier is published"),
          constraints=("the weak-side undertaking at 7.8500, which caps the trade",
                       "funding cost that rises exactly as the trade crowds",
                       "a squeeze risk that grows as the Aggregate Balance falls"),
          instruments=("USDHKD spot and forwards", "HKD funding"),
          counterparties=("the licensed banks as lenders", "the HKMA at the barrier"),
          observables=("the HIBOR-SOFR spread",
                       "USDHKD forward points, which price the carry directly",
                       "the persistence of spot at the weak side"),
          impact="the crowd that PUSHES the currency to the weak side, and the crowd that gets "
                 "squeezed when the HKMA's buying shrinks the Aggregate Balance -- a textbook "
                 "self-limiting trade whose limit is a published number",
          persistence="recurs in every US tightening cycle; the 2022-2023 episode is the most "
                      "recent and largest",
          falsifier="if USDHKD time spent at the weak side shows no relation to the HIBOR-SOFR "
                    "spread, the carry is not what drives the currency to the barrier and the "
                    "central causal story of this pack is wrong",
          notes="The forward-points leg is UNMEASURED on this desk: the broker quotes USDHKD "
                "spot and no forward curve, and that gap is named in ABSENT_INSTRUMENTS."),
    actor("新股孖展認購者 -- IPO margin subscribers and their lenders",
          holds="leveraged subscription applications for new listings, funded by brokers in HKD",
          forced_to=("fund the full subscription amount up front under the old regime, for the "
                     "days between application and allocation",
                     "repay the margin immediately at allocation"),
          when="at each large listing; historically the single largest recurring HKD liquidity "
               "event of the year",
          information=("their own demand, aggregated by the sponsor before the market sees it"),
          constraints=("prefunding requirements, which FINI changed structurally in November 2023",
                       "broker margin limits",
                       "an allocation they cannot predict"),
          instruments=("HKD margin loans", "the new shares themselves"),
          counterparties=("brokers as lenders", "the banking system whose balance is drained"),
          observables=("subscription multiples, published",
                       "HIBOR spikes in the subscription window",
                       "the Aggregate Balance dip and recovery around the settlement"),
          impact="a temporary, predictable, dated drain on HKD liquidity that pushed HIBOR up "
                 "and USDHKD toward the strong side -- and whose amplitude was cut structurally "
                 "by FINI, which makes the change itself a natural experiment",
          persistence="the mechanism is much weaker after November 2023 and the pack says so "
                      "rather than carrying a pre-FINI estimate forward",
          falsifier="if HIBOR and the Aggregate Balance show no abnormal behaviour around large "
                    "pre-2023 listings, relative to matched weeks, the IPO squeeze was folklore "
                    "and the FINI split is measuring nothing",
          notes="One of the few places where a regulatory change gives a clean before-and-after "
                "on a flow mechanism."),
    actor("恒指期貨結算參與者 -- HSI and HSCEI derivatives settlement participants",
          holds="index futures and options inventory settled against a whole-day average",
          forced_to=("hold or hedge through the expiry day, because settlement is an average of "
                     "quotations taken every five minutes across the session",
                     "roll positions before the second-last business day of the month"),
          when="the second-last business day of each month, which MOVES with the holiday calendar",
          information=("their own inventory and the published open-interest distribution"),
          constraints=("a settlement price that is an all-day average and therefore extremely "
                       "expensive to influence",
                       "position limits",
                       "the T+1 after-hours session, which prices overnight moves before the "
                       "cash market opens"),
          instruments=("HSI and HSCEI futures and options", "the cash basket as the hedge"),
          counterparties=("Korean and mainland structured-product issuers hedging HSCEI-linked "
                          "notes", "index funds", "each other"),
          observables=("open interest by contract month, daily",
                       "the futures basis into expiry",
                       "turnover on expiry days against ordinary days"),
          impact="an expiry effect here should be WEAKER than Korea's, because the settlement "
                 "window is a day rather than ten minutes -- and testing that contrast across "
                 "two packs is worth more than testing either alone",
          persistence="structural; the settlement method has been stable",
          falsifier="if expiry-day turnover, range and basis on the second-last business day are "
                    "indistinguishable from matched days, there is no Hong Kong expiry mechanism",
          notes="HSCEI is where Korean ELS and mainland structured products hedge, which is why "
                "this actor appears in three packs at once."),
    actor("A/H 套戥者 -- the A/H arbitrageurs who cannot arbitrage",
          holds="positions in both lines of a dual-listed mainland company, at different prices",
          forced_to=("accept that the two lines are NOT fungible and cannot be converted into "
                     "each other",
                     "fund each leg in a different currency across a closed capital account"),
          when="continuously; the premium widens and narrows with sentiment and with policy",
          information=("nothing privileged; the premium is published daily"),
          constraints=("non-fungibility, which is the whole reason the premium exists",
                       "the capital account between the two markets",
                       "different dividend tax treatment on the two lines"),
          instruments=("A shares", "H shares", "CHINAH and HK50 as the liquid proxies"),
          counterparties=("southbound and northbound investors", "index funds on both sides"),
          observables=("the Hang Seng Stock Connect China AH Premium Index, daily",
                       "per-pair premia for the large dual listings",
                       "Connect flow in both directions"),
          impact="the premium is a PRICE OF THE CAPITAL ACCOUNT rather than a mispricing, so its "
                 "level carries information about policy and sentiment that neither market's "
                 "price carries alone",
          persistence="structural while the capital account is closed; the premium has been "
                      "persistently positive for a decade",
          falsifier="if the A/H premium carries no information for CHINAH or HK50 returns, or "
                    "for USDCNH, beyond what the two markets' own prices carry, it is a "
                    "derived quantity with no incremental content",
          notes="Named as an actor who CANNOT do the thing their name implies, because that "
                "impossibility is the mechanism."),
    actor("香港地產商及按揭借款人 -- Hong Kong developers and mortgage borrowers",
          holds="property assets and HIBOR-linked mortgage debt, most of it capped at a spread "
                "over the best lending rate",
          forced_to=("service debt whose rate moves with HIBOR up to the cap",
                     "refinance on schedule",
                     "sell inventory when funding costs rise"),
          when="continuously; the pain concentrates when HIBOR rises through the cap",
          information=("their own project pipeline and their own funding position"),
          constraints=("the mortgage cap, which transfers rate risk back to the banks above a "
                       "threshold and creates a KINK in the transmission",
                       "loan-to-value rules the government adjusts",
                       "a property market that has fallen for years"),
          instruments=("HKD mortgage and corporate debt", "property itself"),
          counterparties=("the licensed banks", "households as buyers"),
          observables=("HIBOR against the best lending rate and the cap",
                       "RVD property price indices, monthly",
                       "residential transaction volumes"),
          impact="the real-economy end of the peg's transmission: a US rate rise becomes a Hong "
                 "Kong mortgage rate rise with no domestic decision anywhere in the chain",
          persistence="structural while the peg holds and while the cap convention persists",
          falsifier="if Hong Kong property prices and transaction volumes show no relation to "
                    "HIBOR beyond what the global cycle explains, the domestic leg of the "
                    "transmission is not operating",
          notes="The kink at the cap is a genuine non-linearity and a study that fits a linear "
                "HIBOR sensitivity across it will fit neither side."),
    actor("美國聯邦公開市場委員會 -- the FOMC as Hong Kong's actual rate setter",
          holds="the federal funds target, which Hong Kong imports by construction",
          forced_to=("set US policy for US conditions, with no mandate to consider Hong Kong"),
          when="eight scheduled meetings a year on the US calendar, announced in the Hong Kong "
               "small hours",
          information=("its own reaction function"),
          constraints=("a US dual mandate that has nothing to do with Hong Kong's cycle"),
          instruments=("the federal funds target", "US monetary policy generally"),
          counterparties=("the HKMA, which follows by formula",
                          "every HKD borrower and lender"),
          observables=("FOMC decisions and the dot plot",
                       "the HKMA Base Rate announcement hours later",
                       "HIBOR's response the following Hong Kong morning"),
          impact="Hong Kong's monetary policy is made in Washington. The interesting question is "
                 "not whether the rate follows -- it does, by formula -- but how much of the "
                 "move is already in HIBOR before the HKMA announces anything",
          persistence="structural while the peg holds",
          falsifier="if HIBOR shows no response to FOMC surprises beyond what is already priced "
                    "before the announcement, the imported-rate channel is fully anticipated and "
                    "there is nothing to trade in it",
          notes="Named as an actor in a Hong Kong pack on purpose. The DST asymmetry -- the gap "
                "from the FOMC to the HKMA announcement is an hour longer in the northern "
                "winter -- is one of the few daylight-saving effects in this package."),
    actor("香港特區政府及外匯基金 -- the government and the Exchange Fund",
          holds="fiscal reserves held in the Exchange Fund, and a bond programme",
          forced_to=("fund a deficit after years of surplus",
                     "publish a budget every February for a fiscal year beginning 1 April",
                     "keep the Exchange Fund's backing ratio intact"),
          when="the Budget in late February; bond issuance on a published calendar",
          information=("its own fiscal position before the Budget"),
          constraints=("the Basic Law's fiscal-balance expectation",
                       "the backing requirement on the monetary base",
                       "a narrow revenue base that depends on land sales and stamp duty"),
          instruments=("government bonds", "fiscal reserves placed with the Exchange Fund",
                       "stamp duty and property measures"),
          counterparties=("the HKMA as fund manager", "bond investors"),
          observables=("the Budget and its deficit projection",
                       "monthly fiscal reserve balances",
                       "government bond issuance"),
          impact="fiscal reserve movements into and out of the Exchange Fund change the "
                 "Aggregate Balance without any Convertibility Undertaking, which is a "
                 "CONFOUND that any intervention study must remove first",
          persistence="structural; the deficit era began in 2019 and has not ended",
          falsifier="if Aggregate Balance changes attributable to fiscal flows carry no "
                    "information for HIBOR, the confound is immaterial and can be ignored -- "
                    "which is a useful negative result and not a null",
          notes="Named because it is the main reason a fall in the Aggregate Balance is not "
                "automatically an intervention."),
    actor("香港交易所 -- HKEX as market operator",
          holds="the rules of the market: the auction, the volatility mechanism, the expiry "
                "convention and, until 2024, the weather closure",
          forced_to=("run a market whose microstructure it periodically changes",
                     "publish every change in advance"),
          when="at each rule change; the ones this pack tracks are the 2017 closing auction "
               "reintroduction, the 2023 FINI platform and the 2024-09-23 severe-weather change",
          information=("its own rule pipeline"),
          constraints=("regulatory approval", "competitive pressure from other listing venues"),
          instruments=("the market's own rules"),
          counterparties=("every participant"),
          observables=("rule-change notices",
                       "the measurable discontinuity in the data on each effective date"),
          impact="every one of these changes is a structural break in a price series, announced "
                 "in advance, with an exact date -- which makes them the cleanest natural "
                 "experiments in the pack",
          persistence="permanent once made",
          falsifier="if closing-auction volume share, intraday volatility shape and gap "
                    "behaviour show no discontinuity at the announced effective dates, the rule "
                    "changes did not bind and the microstructure-regime domain is empty",
          notes="An operator is an actor when its decisions change the data-generating process, "
                "and here they demonstrably do."),
    actor("環球宏觀基金 -- global macro funds testing the peg",
          holds="short HKD or long HKD volatility positions taken as a bet on the band breaking",
          forced_to=("pay carry for as long as the position is open, which the band makes "
                     "expensive and the payoff asymmetric",
                     "close when the funding cost exceeds the option value"),
          when="in every stress episode; the positions are usually expressed in forwards and "
               "options rather than spot",
          information=("nothing privileged; this is a public bet against a public commitment"),
          constraints=("the two undertakings, which cap the payoff unless the board breaks",
                       "a carry cost that rises as the Aggregate Balance falls, which is exactly "
                       "when the bet looks best",
                       "an authority with reserves many times the monetary base"),
          instruments=("USDHKD forwards and options", "HK50 as the risk expression"),
          counterparties=("the licensed banks", "ultimately the HKMA at the barrier"),
          observables=("forward points at the far end of the curve",
                       "implied volatility where a public quote exists",
                       "public commentary on peg pressure"),
          impact="they supply the pressure that takes the currency to the weak side and they are "
                 "the crowd that funds the squeeze when the balance shrinks; every episode so "
                 "far has ended the same way",
          persistence="recurs; each episode has been smaller relative to the reserves backing "
                      "the board",
          falsifier="if USDHKD behaviour at the weak side is indistinguishable from its "
                    "behaviour in the mid-zone once the carry is controlled for, this actor adds "
                    "nothing beyond the carry trader already in this list and should retire "
                    "into it",
          notes="Kept separate from the carry trader because the payoff structure differs: one "
                "is paid to wait, the other pays to wait."),
    actor("強積金及本地機構 -- MPF schemes and local institutions",
          holds="mandatory pension contributions invested across Hong Kong, mainland and global "
                "equities and bonds",
          forced_to=("invest contributions monthly, whatever the market level",
                     "rebalance to target allocations",
                     "convert between HKD and foreign currency to do so"),
          when="monthly contributions on payroll dates; rebalancing at scheme intervals",
          information=("nothing privileged"),
          constraints=("mandatory contribution rules",
                       "scheme mandates and allocation limits",
                       "a member base whose switching behaviour is slow and procyclical"),
          instruments=("Hong Kong, mainland and global equity and bond funds",
                       "HKD conversion at the fund level"),
          counterparties=("fund managers", "the market at large"),
          observables=("MPF scheme asset statistics, published quarterly",
                       "monthly contribution aggregates"),
          impact="a small but genuinely mandatory monthly bid, and a procyclical switching flow "
                 "that amplifies at turning points",
          persistence="structural while the scheme is mandatory",
          falsifier="if HK50 returns around payroll and contribution dates are indistinguishable "
                    "from matched days, the mandatory bid is too small to reach price",
          notes="The smallest-prior actor in the pack. Kept because the flow is genuinely forced "
                "and dated, which is rare enough to be worth one test."),
)


# --------------------------------------------------------------------------- domains
_DEFAULT_CONTROLS: tuple[str, ...] = (
    "the same statistic on EURUSD and USDSGD, where no Hong Kong mechanism can operate",
    "the same statistic on matched weekdays and days of the month",
    "the same statistic inside each era of POLICY_ERAS, never pooled across them",
    "the same statistic conditioned on the US rate path alone -- because Hong Kong imports its "
    "policy rate, any HK result that survives US conditioning is the only one that is Hong "
    "Kong's own",
)


def _controls(*extra: str) -> tuple[str, ...]:
    """The four standing controls every Hong Kong domain runs, plus the domain's own."""
    return (*_DEFAULT_CONTROLS, *extra)


DOMAINS: tuple[dict[str, Any], ...] = (
    domain("hk_peg_band", "USDHKD as a bounded process with two reflecting barriers",
           objects=("band position and distance to each undertaking, per bar",
                    "time spent in each regime label from peg_band_position()",
                    "the shape of the return distribution near a barrier versus in the mid-zone"),
           conditions=("which regime the bar is in",
                       "the HIBOR-SOFR carry, which is what drives the currency across the band",
                       "the level of the Aggregate Balance"),
           instruments=("USDHKD", "HK50"),
           controls=_controls(
               "the same statistics on USDSGD, a managed but UNBOUNDED Asian currency, which is "
               "the closest available control for a band effect",
               "a simulated bounded random walk with the same volatility, which is what the "
               "distribution should look like if the barrier is the ONLY mechanism")),
    domain("hk_aggregate_balance", "The balance as the intervention record and the liquidity state",
           objects=("the daily Aggregate Balance and its forecast",
                    "changes attributable to Convertibility Undertakings",
                    "changes attributable to Exchange Fund paper and fiscal flows"),
           conditions=("whether the change came from an undertaking or from issuance -- these "
                       "must be separated before anything else",
                       "the level relative to its own multi-year range",
                       "quarter end and year end"),
           instruments=("USDHKD", "HK50", "CHINAH"),
           controls=_controls(
               "days when the balance changed with NO undertaking triggering, which isolates the "
               "issuance and fiscal confound",
               "the T+2 settlement lag: an effect that appears before it could have settled is "
               "anticipation and not transmission")),
    domain("hk_hibor_carry", "HIBOR, the imported rate and the carry that moves the currency",
           objects=("HIBOR across tenors at 03:15 UTC",
                    "the HIBOR-SOFR spread",
                    "the gap between HIBOR and the best lending rate"),
           conditions=("the Aggregate Balance level",
                       "whether an IPO or a quarter end is draining liquidity",
                       "before and after the November 2023 FINI change"),
           instruments=("USDHKD", "HK50", "UST10Y"),
           controls=_controls(
               "CNH HIBOR, fixed at the same minute in the same city by the same body, which "
               "shares the funding market and not the mechanism",
               "SOFR alone, since the imported component must be removed before anything can be "
               "called Hong Kong's")),
    domain("hk_cu_intervention", "Same-day disclosed intervention as an event study",
           objects=("each triggering, its side and its size",
                    "the Aggregate Balance path afterwards",
                    "HIBOR and USDHKD in the following sessions"),
           conditions=("strong side versus weak side, which are different mechanisms and must "
                       "never be pooled",
                       "the size of the operation relative to the balance",
                       "whether it was the first of an episode or the twentieth"),
           instruments=("USDHKD", "HK50"),
           controls=_controls(
               "days at the same band position with NO triggering, which is the only honest "
               "placebo for an automatic mechanism",
               "the equivalent Korean and Chinese episodes, where intervention is not disclosed "
               "-- a Hong Kong result that does not reproduce there may simply be a disclosure "
               "effect")),
    domain("hk_connect_flows", "Southbound as the marginal bid and as an HKD demand",
           objects=("daily southbound turnover and quota use",
                    "CCASS holdings by the southbound participant",
                    "the settlement-driven HKD conversion"),
           conditions=("the A/H premium level",
                       "mainland domestic yields",
                       "whether the Connect calendar closed the link that day"),
           instruments=("HK50", "CHINAH", "USDHKD"),
           controls=_controls(
               "northbound over the same window, the other direction of the same link",
               "global equity beta removed first, since southbound buys most when the world is "
               "buying")),
    domain("hk_index_expiry", "The second-last business day, and a settlement nobody can push",
           objects=("HSI and HSCEI expiries from hk_expiry_dates()",
                    "open interest by contract month into expiry",
                    "expiry-day range, turnover and basis"),
           conditions=("whether a holiday moved the expiry that month",
                       "open interest concentration",
                       "whether a Korean or mainland expiry falls in the same week"),
           instruments=("HK50", "CHINAH"),
           controls=_controls(
               "the LAST business day and the third-last, which bracket the expiry and share "
               "every month-end effect with it",
               "Korea's second Thursday, where the settlement window is ten minutes rather than "
               "a day -- the contrast between the two is the actual test of whether settlement "
               "window width matters")),
    domain("hk_ah_premium", "The price of a closed capital account",
           objects=("the AH premium index, daily",
                    "its relation to Connect flow in both directions",
                    "its relation to USDCNH"),
           conditions=("the level and the direction of the premium",
                       "mainland policy news",
                       "whether either market was closed"),
           instruments=("CHINAH", "HK50", "USDCNH"),
           controls=_controls(
               "the CHINAH-versus-HK50 relative, which is a DIFFERENT object and must not be "
               "substituted for the premium",
               "dual-listed pairs in markets with open capital accounts, where the premium "
               "should be near zero")),
    domain("hk_ipo_liquidity", "Prefunding, HIBOR spikes, and the rule change that ended them",
           objects=("large listings and their subscription multiples",
                    "HIBOR in the subscription window",
                    "the Aggregate Balance dip and recovery"),
           conditions=("before and after the November 2023 FINI platform, NEVER pooled",
                       "deal size relative to the Aggregate Balance",
                       "whether the market was in a strong-side or weak-side regime"),
           instruments=("USDHKD", "HK50"),
           controls=_controls(
               "matched weeks with no listing",
               "post-FINI listings of comparable size, which is the within-domain control for "
               "the pre-FINI estimate")),
    domain("hk_china_transmission", "Mainland policy arriving in the only open China market",
           objects=("mainland policy announcements and data releases",
                    "CHINAH and HK50 reaction",
                    "the mainland session's own state -- frequently closed"),
           conditions=("whether the mainland market was open",
                       "whether the announcement was a scheduled release or an unscheduled "
                       "readout",
                       "the size of the southbound flow that day"),
           instruments=("CHINAH", "HK50", "USDCNH"),
           controls=_controls(
               "matched days with no mainland news",
               "the mainland reopening session, which prices the same news later: a Hong Kong "
               "reaction that is fully reversed when the mainland reopens was a liquidity "
               "effect and not information")),
    domain("hk_microstructure_regimes", "Auctions, volatility mechanisms and the weather",
           objects=("the 2017 closing auction reintroduction",
                    "the Volatility Control Mechanism",
                    "weather closures before 2024-09-23 and their absence after",
                    "the T+1 after-hours futures session"),
           conditions=("which regime the date falls in",
                       "whether a signal 8 was actually hoisted on the day",
                       "whether the move was large enough to trigger the VCM"),
           instruments=("HK50", "CHINAH"),
           controls=_controls(
               "TAIWAN, which still closes for typhoons and is therefore the natural control "
               "for the 2024-09-23 change",
               "the same statistics estimated separately either side of each effective date, "
               "with a structural-break test reported rather than a pooled mean")),
    domain("hk_us_rate_import", "A monetary policy made in Washington",
           objects=("FOMC decisions and the HKMA Base Rate announcement hours later",
                    "HIBOR's response the following Hong Kong morning",
                    "the DST-dependent gap between the two announcements"),
           conditions=("northern winter versus summer, because the US clock shifts and Hong "
                       "Kong's does not",
                       "whether the FOMC was a surprise against the market-implied path",
                       "the Aggregate Balance level, which determines how much HIBOR can move"),
           instruments=("USDHKD", "HK50", "UST10Y"),
           controls=_controls(
               "the HKMA announcement alone, which should carry NOTHING if the formula is fully "
               "anticipated -- and if it does carry something, the formula is not what the "
               "market thinks it is",
               "the same FOMC event measured on USDSGD, which has no formulaic link")),
    domain("hk_property_rates", "The real-economy end of an imported rate",
           objects=("RVD property price indices",
                    "residential transaction volumes",
                    "HIBOR against the best lending rate and the mortgage cap"),
           conditions=("whether HIBOR is above or below the cap, which is a genuine kink",
                       "loan-to-value policy in force",
                       "mainland buyer participation"),
           instruments=("HK50",),
           controls=_controls(
               "the same statistic fitted separately either side of the cap, since a linear "
               "sensitivity across a kink fits neither side",
               "a property market with a domestic policy rate, where the imported-rate channel "
               "cannot operate")),
    domain("hk_fiscal_confound",
           "Why a falling Aggregate Balance is not automatically intervention",
           objects=("fiscal reserve movements into and out of the Exchange Fund",
                    "Exchange Fund Bill and Note issuance",
                    "government bond issuance"),
           conditions=("the Budget cycle and the 1 April fiscal year start",
                       "the issuance calendar, which is published",
                       "whether an undertaking triggered in the same window"),
           instruments=("USDHKD", "HK50"),
           controls=_controls(
               "days with issuance and no undertaking, and days with an undertaking and no "
               "issuance -- the two-by-two is the whole design",
               "the announced issuance calendar as a placebo, since a scheduled drain should be "
               "priced in advance"),
           notes="This domain exists to protect the others: without it, every Aggregate Balance "
                 "result is contaminated by a flow that has nothing to do with the peg."),
)

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("hk_weak_side_to_hibor_and_equity",
         source="USDHKD at or through the weak-side undertaking at 7.8500",
         mechanism="the HKMA must buy Hong Kong dollars, which shrinks the Aggregate Balance "
                   "with T+2 settlement, which raises HIBOR, which tightens local financial "
                   "conditions",
         targets=("USDHKD", "HK50"),
         sign="weak-side triggering -> Aggregate Balance DOWN, HIBOR UP, HK50 DOWN over one to "
              "ten sessions",
         horizon="two to ten sessions",
         lag="T+2 on the balance; HIBOR responds at the 03:15 UTC fixing",
         control="days at the same band position with no triggering; and balance changes caused "
                 "by Exchange Fund issuance or fiscal flows, which move the balance without any "
                 "peg mechanism at all",
         evidence="MEASURED_ELSEWHERE",
         notes="The most documented mechanism in this package -- the 2018-2019 and 2022-2023 "
               "episodes are both public and both well described. MEASURED_ELSEWHERE means the "
               "desk has NOT reproduced it and must."),
    edge("hk_strong_side_to_carry",
         source="USDHKD at or through the strong-side undertaking at 7.7500",
         mechanism="the HKMA sells Hong Kong dollars, the Aggregate Balance expands, HIBOR "
                   "collapses toward zero and the local carry turns deeply negative",
         targets=("USDHKD", "HK50"),
         sign="strong-side triggering -> Aggregate Balance UP, HIBOR DOWN, HK50 UP",
         horizon="two to twenty sessions",
         lag="T+2 on the balance",
         control="the weak-side episodes, which are the same mechanism with the sign reversed "
                 "and must be estimated SEPARATELY rather than pooled into one absolute effect",
         evidence="HYPOTHESIS",
         notes="The 2025 strong-side episode is the recent case: the balance rose sharply and "
               "HIBOR fell to near zero within weeks."),
    edge("hk_hibor_spread_to_band_position",
         source="the HIBOR minus SOFR spread",
         mechanism="a negative carry pays traders to be short HKD, which pushes spot toward the "
                   "weak side until the HKMA's buying reverses the funding condition",
         targets=("USDHKD",),
         sign="HIBOR-SOFR spread MORE NEGATIVE -> USDHKD toward 7.8500",
         horizon="days to months",
         lag="HIBOR at 03:15 UTC",
         control="CNH HIBOR, fixed at the same minute in the same city, which shares the funding "
                 "market and not the mechanism; and SOFR alone",
         evidence="MEASURED_ELSEWHERE"),
    edge("fomc_to_hk_rate_and_equity",
         source="FOMC decisions, imported by the Base Rate formula",
         mechanism="Hong Kong has no domestic policy rate; the Base Rate is the higher of the "
                   "fed funds lower bound plus 50bp and a HIBOR average, so a US decision is a "
                   "Hong Kong decision with a lag of hours",
         targets=("USDHKD", "HK50", "UST10Y"),
         sign="hawkish FOMC surprise -> HIBOR UP, HK50 DOWN",
         horizon="hours to five sessions",
         lag="the FOMC announcement, then the HKMA hours later -- an hour longer in the northern "
             "winter because the US clock shifts and Hong Kong's does not",
         control="the HKMA announcement measured alone, which should carry nothing if the "
                 "formula is fully anticipated; and USDSGD over the same windows",
         evidence="HYPOTHESIS"),
    edge("hk_southbound_to_equity_and_peg",
         source="daily southbound Stock Connect turnover and CCASS holdings",
         mechanism="mainland buying of Hong Kong shares is a marginal equity bid and a "
                   "structural HKD purchase at settlement",
         targets=("HK50", "CHINAH", "USDHKD"),
         sign="southbound surge -> HK50 UP, CHINAH UP, USDHKD toward the strong side",
         horizon="one to ten sessions",
         lag="same day for turnover, one session for holdings",
         control="northbound over the same window; and global equity beta removed first",
         evidence="HYPOTHESIS",
         notes="Shared deliberately with the CN pack: one mechanism, two departments, and the "
               "two readings should agree."),
    edge("hk_expiry_to_index_variance",
         source="HSI and HSCEI expiry on the second-last business day of the month",
         mechanism="settlement against an all-day five-minute average concentrates hedging "
                   "through the session rather than into a closing print",
         targets=("HK50", "CHINAH"),
         sign="expiry day -> elevated intraday turnover, with a WEAKER pinning effect than in "
              "Korea because the settlement window is a day rather than ten minutes",
         horizon="intraday",
         lag="the expiry session itself",
         control="the last and third-last business days of the same month, which bracket it and "
                 "share every month-end effect; and Korea's second-Thursday expiry, whose "
                 "ten-minute settlement is the contrast that makes this test informative",
         evidence="HYPOTHESIS"),
    edge("hk_ah_premium_to_relative",
         source="the Hang Seng Stock Connect China AH Premium Index",
         mechanism="the premium prices the closed capital account; when it is extreme, Connect "
                   "flow and sentiment have historically moved to close part of it",
         targets=("CHINAH", "HK50", "USDCNH"),
         sign="premium at an extreme -> CHINAH outperforms or underperforms HK50 depending on "
              "the direction, and USDCNH responds to the implied capital-account stress",
         horizon="five to forty sessions",
         lag="daily index publication",
         control="the CHINAH-versus-HK50 relative alone, with no premium conditioning -- if the "
                 "premium adds nothing incremental, this edge retires",
         evidence="HYPOTHESIS"),
    edge("hk_ipo_squeeze_to_hibor",
         source="large IPO subscriptions, split at the November 2023 FINI change",
         mechanism="prefunding froze HKD for days, drained the Aggregate Balance and spiked "
                   "HIBOR; FINI replaced full prefunding with a pre-committed model",
         targets=("USDHKD", "HK50"),
         sign="large pre-FINI listing -> HIBOR UP, USDHKD toward the strong side; post-FINI the "
              "same listing should produce a much smaller effect",
         horizon="the subscription window plus a week",
         lag="the subscription period, which is published in advance",
         control="post-FINI listings of comparable size, which is the within-mechanism control; "
                 "and matched weeks with no listing",
         evidence="HYPOTHESIS",
         notes="A rare case where a regulatory change gives a clean before-and-after on the SAME "
               "flow mechanism."),
    edge("cn_policy_to_hk_equity",
         source="mainland policy announcements and data, arriving when the mainland market is "
                "frequently shut",
         mechanism="Hong Kong is the only continuously open China equity market, so it prices "
                   "mainland news first and sometimes alone",
         targets=("CHINAH", "HK50", "USDCNH"),
         sign="mainland stimulus -> CHINAH UP, HK50 UP",
         horizon="minutes to five sessions",
         lag="announcement time",
         control="the mainland reopening session, which prices the same news later: a Hong Kong "
                 "move fully reversed on the mainland reopen was liquidity and not information",
         evidence="HYPOTHESIS"),
    edge("hk_weather_regime_to_gaps",
         source="the 2024-09-23 end of weather-driven market closures",
         mechanism="before that date a typhoon signal could remove a whole session at short "
                   "notice, which created unscheduled gaps and a distinctive pre-closure rush",
         targets=("HK50", "CHINAH"),
         sign="post-2024-09-23 -> fewer unscheduled gaps and a changed intraday shape on severe "
              "weather days",
         horizon="intraday",
         lag="the effective date, announced in advance",
         control="TAIWAN, which still closes for typhoons and therefore should show the OLD "
                 "behaviour throughout; and the same statistics either side of the effective "
                 "date with a structural-break test",
         evidence="HYPOTHESIS",
         notes="The cross-pack control makes this one of the better-identified microstructure "
               "questions in the package."),
    edge("hk_peg_stress_to_haven",
         source="sustained time at the weak side with a falling Aggregate Balance",
         mechanism="peg stress is read as a regional capital-account signal and raises demand "
                   "for a haven that no capital control reaches",
         targets=("XAUUSD", "USDCNH", "HK50"),
         sign="sustained weak-side regime -> XAUUSD UP, HK50 DOWN",
         horizon="ten to sixty sessions",
         lag="continuous",
         control="periods of equivalent US rate tightening with NO weak-side regime, which is "
                 "the only way to separate peg stress from the dollar cycle that causes it",
         evidence="HYPOTHESIS",
         notes="The weakest-prior edge here and labelled as such: the carry that drives the "
               "currency to the barrier is also what drives gold, so the confound is severe."),
    edge("hk_fiscal_drain_to_balance",
         source="Exchange Fund Bill issuance and fiscal reserve movements",
         mechanism="these change the Aggregate Balance with NO Convertibility Undertaking, and "
                   "are therefore the main confound in every balance-based study",
         targets=("USDHKD", "HK50"),
         sign="scheduled drain -> balance DOWN with no peg signal; the expected effect on "
              "USDHKD is NONE and finding one would mean the market misreads the cause",
         horizon="days",
         lag="the issuance calendar, published in advance",
         control="undertaking-driven balance changes of the same size, which should behave "
                 "differently if the market distinguishes the two causes",
         evidence="HYPOTHESIS",
         notes="A NULL is the expected and useful result here. The edge exists to quantify a "
               "confound rather than to find an effect."),
)

#: Derived, never hand-maintained.
TRANSMISSION_TARGETS: tuple[str, ...] = tuple(sorted(
    {t for e in TRANSMISSION_EDGES_SEED for t in e["targets"]} - set(OWN_PRICE)))


# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("hk_two_sided_cu", start="2005-05-18", end="2008-09-14",
        label="The two-sided Convertibility Undertakings established",
        what_changed="the strong side was set at 7.7500 and the weak side at 7.8500, creating "
                     "the Convertibility Zone that defines every observable in this pack",
        invalidates="any USDHKD distributional statistic estimated before this date is "
                    "estimated on a different, one-sided commitment"),
    era("hk_strong_side_flood", start="2008-09-15", end="2015-12-31",
        label="The post-crisis strong-side era",
        what_changed="repeated strong-side triggerings expanded the Aggregate Balance to "
                     "several hundred billion Hong Kong dollars and pinned HIBOR near zero for "
                     "years",
        invalidates="a HIBOR-to-balance elasticity fitted here is fitted at a corner where the "
                    "balance was so large that further additions did almost nothing"),
    era("hk_first_weak_side", start="2018-04-12", end="2019-12-31",
        label="The first weak-side era since 2005",
        what_changed="US tightening opened a negative HKD carry; the HKMA bought Hong Kong "
                     "dollars repeatedly and the Aggregate Balance fell by most of its level",
        invalidates="this is the first window in which the weak-side mechanism can be estimated "
                    "at all; nothing before it contains a weak-side observation"),
    era("hk_pandemic_strong_side", start="2020-04-01", end="2021-12-31",
        label="The pandemic strong-side era",
        what_changed="capital inflow and a heavy listing pipeline pushed spot to 7.7500 "
                     "repeatedly and took the Aggregate Balance back to record levels",
        invalidates="an IPO-to-HIBOR estimate from this window is contaminated by an Aggregate "
                    "Balance so large that no listing could move it"),
    era("hk_second_weak_side", start="2022-05-01", end="2023-05-31",
        label="The second weak-side era and the great balance drain",
        what_changed="dozens of weak-side triggerings took the Aggregate Balance down by an "
                     "order of magnitude and finally let HIBOR rise",
        invalidates="the cleanest window for estimating the weak-side transmission, and the one "
                    "that shows the balance must fall a long way before HIBOR responds at all "
                    "-- a NON-LINEARITY that a pooled linear fit will miss"),
    era("hk_fini", start="2023-11-01", end=None,
        label="FINI replaces IPO prefunding",
        what_changed="subscription money is no longer frozen in full, which structurally shrank "
                     "the recurring IPO liquidity squeeze",
        invalidates="every pre-2023 IPO-to-HIBOR estimate; the mechanism still exists but its "
                    "amplitude is a fraction of what it was"),
    era("hk_severe_weather_trading", start="2024-09-23", end=None,
        label="The market stops closing for typhoons",
        what_changed="signal 8 and black rainstorm no longer close the market, ending "
                     "unscheduled weather closures that had happened several times a year",
        invalidates="intraday and gap statistics pooled across this date mix a market that could "
                    "vanish for a day with one that cannot"),
    era("hk_northbound_dark", start="2024-08-19", end=None,
        label="Northbound real-time flow disclosure ends",
        what_changed="the mainland half of Stock Connect stopped publishing intraday flow, "
                     "leaving southbound as the better-instrumented direction",
        invalidates="cross-boundary flow studies that used both directions symmetrically before "
                    "this date cannot be replicated after it"),
    era("hk_2025_strong_side", start="2025-05-01", end=None,
        label="The 2025 strong-side episode and the HIBOR collapse",
        what_changed="heavy inflows took spot to 7.7500, the HKMA sold Hong Kong dollars in "
                     "size, the Aggregate Balance multiplied and HIBOR fell toward zero before "
                     "the weak side returned within months",
        invalidates="a carry-to-band-position estimate that includes this round trip without "
                    "conditioning on it is averaging a full cycle into a single coefficient"),
)


# --------------------------------------------------------------------------- framework fields
MISSION = ("Mine the Hong Kong currency board to exhaustion: a bounded price with two published "
           "barriers, an intervention disclosed the day it happens, and a liquidity chain whose "
           "every link is public and daily -- and name the one link, the HIBOR leg, that this "
           "desk cannot trade.")
#: No Hong Kong dollar futures contract exists at the CFTC. Empty is the MEASUREMENT, and the
#: Aggregate Balance is a better positioning proxy than a COT report would be anyway.
COT_CURRENCY = ""
EXPORT_ECONOMY = "services_exporter"
#: Margin financing is broadly available and lightly restricted; IPO margin subscription in
#: particular was, until FINI, one of the largest retail leverage events in any market.
RETAIL_LEVERAGE_REGIME = "open"
OPEN_ERA_END = "2030-12-31"
#: Recurring solar closures as MM-DD. The lunar dates (農曆年初一 to 初三, 佛誕, 端午節,
#: 中秋節翌日, 重陽節), the solar term 清明節 and the Christian moveable feasts CANNOT appear
#: here and are tabulated instead.
HOLIDAY_FIXED_MD: tuple[str, ...] = ("01-01", "05-01", "07-01", "10-01", "12-25", "12-26")

SESSION_WINDOWS: tuple[dict[str, str], ...] = (
    {"name": "hk_pre_open", "start_utc": "01:00", "end_utc": "01:30",
     "notes": "the pre-opening session; the overnight US move and the T+1 futures session are "
              "already in the price by here"},
    {"name": "hk_morning", "start_utc": "01:30", "end_utc": "04:00",
     "notes": "the cash morning session; the HIBOR fixing lands at 03:15 inside it"},
    {"name": "hk_hibor_fix", "start_utc": "03:05", "end_utc": "03:30",
     "notes": "HKD and CNH HIBOR are both fixed here, which makes this the funding minute for "
              "two currencies at once"},
    {"name": "hk_afternoon", "start_utc": "05:00", "end_utc": "08:00",
     "notes": "the cash afternoon session, ending in the 08:00-08:10 closing auction"},
    {"name": "hk_closing_auction", "start_utc": "08:00", "end_utc": "08:10",
     "notes": "reintroduced in 2017 after being withdrawn in 2009; index rebalances execute here"},
    {"name": "hk_t1_futures", "start_utc": "09:15", "end_utc": "19:00",
     "notes": "the HSI and HSCEI after-hours session, where a European or US move reaches Hong "
              "Kong hours before the cash market reopens"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "hk_aggregate_balance_forecast", "cadence": "daily", "time_utc": "08:30",
     "source": "HKMA", "notes": "the next-day forecast, published in the Hong Kong afternoon; "
                                "this is what the market trades on and it must be stored as its "
                                "own vintage"},
    {"name": "hk_hibor_fixing", "cadence": "daily", "time_utc": "03:15",
     "source": "Treasury Markets Association", "notes": "HKD and CNH HIBOR across tenors"},
    {"name": "hk_cpi", "cadence": "monthly", "time_utc": "08:30",
     "source": "Census and Statistics Department", "notes": "about the 20th"},
    {"name": "hk_trade", "cadence": "monthly", "time_utc": "08:30",
     "source": "Census and Statistics Department", "notes": "about the 25th"},
    {"name": "hk_gdp", "cadence": "quarterly", "time_utc": "08:30",
     "source": "Census and Statistics Department", "notes": "advance estimate about six weeks "
                                                            "after quarter end"},
    {"name": "hk_budget", "cadence": "annual", "time_utc": "03:00",
     "source": "Financial Secretary", "notes": "late February, conventionally the last Wednesday, "
                                               "for the fiscal year beginning 1 April"},
)

INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "HKMA 總結餘 Aggregate Balance and its next-day forecast (daily, hkma.gov.hk)",
    "HKMA Convertibility Undertaking triggerings (event, same-day disclosed with amounts)",
    "HKEX Stock Connect southbound turnover and quota (daily, hkex.com.hk)",
    "CCASS shareholding search (daily holdings by clearing participant)",
    "HKEX HSI and HSCEI futures and options open interest (daily)",
    "SFC Aggregated Reportable Short Positions (weekly, one-week lag)",
    "HKMA Monetary Base and Exchange Fund Bills and Notes outstanding (daily and monthly)",
)


# --------------------------------------------------------------------------- typed row builders
def _central_bank_row(lab: Any) -> Any:
    """The HKMA as `country_lab.CentralBank`, with NO decision dates.

    The empty tuple is the measurement. Hong Kong's Base Rate follows the FOMC by formula, so a
    pack that copied the Fed's calendar into this row would be claiming a domestic event where
    there is an imported one -- and the generic central-bank miner correctly reports UNMEASURED
    for this country as a result.
    """
    return lab.CentralBank(
        name="Hong Kong Monetary Authority (香港金融管理局)",
        framework="peg",
        decision_dates=(),
        decision_calendar_rule=str(CENTRAL_BANK["schedule_rule"]),
        decision_time_utc="",
        publication_classes=("Convertibility Undertaking triggerings (same day, with amounts)",
                             "Aggregate Balance and its next-day forecast (daily)",
                             "Base Rate announcements (after each FOMC)",
                             "Half-Yearly Monetary and Financial Stability Report"),
        policy_rate_series="hk_base_rate",
        expected_rate_series="",
        notes=f"{CENTRAL_BANK['convertibility_undertakings']} "
              f"AGGREGATE BALANCE: {CENTRAL_BANK['aggregate_balance']} "
              f"VERIFY THE FORMULA: {CENTRAL_BANK['verification']}")


def _fixing_rows(lab: Any) -> tuple[Any, ...]:
    """Hong Kong's references in UTC. HKT never shifts, so `dst_rule` is 'none' -- the daylight
    saving that matters to this pack is on the US side of the imported rate."""
    return (
        lab.Fixing(name="HIBOR (Hong Kong Association of Banks, calculated by the TMA)",
                   time_utc="03:15", dst_rule="none", instruments=("USDHKD", "HK50"),
                   window_minutes=25, notes=str(FIXING_CONVENTIONS["hibor"]["note"])),
        lab.Fixing(name="CNH HIBOR (TMA)", time_utc="03:15", dst_rule="none",
                   instruments=("USDCNH",), window_minutes=25,
                   notes=str(FIXING_CONVENTIONS["cnh_hibor"]["note"])),
        lab.Fixing(name="HKEX closing auction", time_utc="08:00", dst_rule="none",
                   instruments=("HK50", "CHINAH"), window_minutes=10,
                   notes="reintroduced in 2017; index rebalances execute here and it is the "
                         "reference for the cash close"),
    )


def _settlement_rows(lab: Any) -> tuple[Any, ...]:
    """Hong Kong's conventions as RULES. The expiry is month-end anchored rather than weekday
    anchored, which is unique in this package and is why the Exchange row carries an expanded
    date list rather than relying on a weekday convention."""
    return (
        lab.SettlementRule(name="hk_index_expiry", kind="month_end", days=(), months=(),
                           weekday=-1, week_of_month=0, roll="previous",
                           window_utc=("01:30", "08:30"), instruments=("HK50", "CHINAH"),
                           notes="HSI and HSCEI settle on the business day IMMEDIATELY PRECEDING "
                                 "the last business day of the month. This rule is recorded as "
                                 "month_end with a previous-day roll; the authoritative grid is "
                                 "hk_expiry_dates(), which resolves it against the holiday table"),
        lab.SettlementRule(name="hk_cu_settlement", kind="day_of_month",
                           days=tuple(range(1, 32)), months=(), weekday=-1, week_of_month=0,
                           roll="next", window_utc=("00:00", "23:59"), instruments=("USDHKD",),
                           notes="a Convertibility Undertaking triggering settles T+2, so the "
                                 "Aggregate Balance read today reflects operations from two days "
                                 "ago; the rule spans every day because the undertakings are "
                                 "automatic and hour-agnostic"),
        lab.SettlementRule(name="hk_quarter_end_funding", kind="quarter_end", days=(), months=(),
                           weekday=-1, week_of_month=0, roll="previous",
                           window_utc=("01:30", "08:30"), instruments=("USDHKD", "HK50"),
                           notes="HKD funding tightens into quarter end and year end; with a "
                                 "small Aggregate Balance the same pressure moves HIBOR much "
                                 "further, which is the non-linearity the 2022-2023 era exposed"),
        lab.SettlementRule(name="hk_fiscal_year_end", kind="fiscal_year_end", days=(), months=(),
                           weekday=-1, week_of_month=0, roll="previous",
                           window_utc=("01:30", "08:30"), instruments=("USDHKD",),
                           notes="31 March. Fiscal reserve movements into and out of the "
                                 "Exchange Fund change the Aggregate Balance with no peg signal "
                                 "at all, which is the main confound in this pack"),
    )


def _exchange_rows(lab: Any) -> tuple[Any, ...]:
    """HKEX, and it is the ONLY exchange in this package whose indices the broker actually
    quotes -- so the framework's generic expiry miner has something to run on here and nothing
    to run on in Korea, China or Taiwan."""
    dates = tuple(r["date"] for y in (2024, 2025, 2026) for r in hk_expiry_dates(y))
    return (
        lab.Exchange(name="Hong Kong Exchanges and Clearing (HKEX)",
                     index_symbols=("HK50", "CHINAH"),
                     expiry_rule="the business day immediately preceding the last business day "
                                 "of the month; settlement is the average of index quotations "
                                 "taken at five-minute intervals through the expiry day",
                     expiry_dates=dates, open_utc="01:30", close_utc="08:10",
                     notes=f"no daily price limit on the cash market. "
                           f"{EXCHANGES['severe_weather']['rule']}"),
    )


def _release_rows(lab: Any) -> tuple[Any, ...]:
    return tuple(lab.ReleaseClass(name=r["name"], cadence=r["cadence"], time_utc=r["time_utc"],
                                  dates=(), actual_series="", expected_series="",
                                  source=str(r["source"]), notes=str(r["notes"]))
                 for r in RELEASE_CLASSES)


# --------------------------------------------------------------------------- the custom miner
def hk_peg_band_position(pack_in: Any, ctx: Any) -> dict[str, Any]:
    """USDHKD conditioned on where it sits between the two Convertibility Undertakings.

    WHY THIS NEEDS CODE AT ALL. Every generic miner in the framework asks a question about
    RETURNS. For a currency board that is the wrong question: USDHKD cannot move past 7.7500 or
    7.8500 because a public institution is obliged to stop it, so its return distribution is
    truncated by construction and its informative coordinate is DISTANCE TO THE BARRIER. No
    generic miner computes that, because no other country in this package has one.

    What this measures is deliberately simple and hard to fool: the share of bars in each regime
    label, the forward return conditioned on the regime, and the two tails -- how often spot has
    printed OUTSIDE the band at all. That last number should be zero or near zero, and if it ever
    stops being zero the pack has found the only thing about Hong Kong that would really matter.
    """
    lab = _lab()
    out: dict[str, Any] = {"miner": "hk_peg_band_position", "country": CODE,
                           "strong_side": STRONG_SIDE_CU, "weak_side": WEAK_SIDE_CU,
                           "readings": [], "measured": 0}
    bars = ctx.bars("USDHKD", "H1")
    if bars is None:
        ctx.note("bars:USDHKD", "no H1 tape on this box; the band position cannot be measured "
                                "and the whole Hong Kong pack is UNMEASURED without it")
        out["outcome"] = "UNMEASURED"
        out["why"] = "no USDHKD tape"
        return out
    closes = [float(x) for x in bars.close if x == x and float(x) > 0]
    if not closes:
        ctx.note("bars:USDHKD", "the USDHKD tape holds no finite positive closes")
        out["outcome"] = "UNMEASURED"
        out["why"] = "no usable closes"
        return out
    counts: dict[str, int] = {}
    outside: list[float] = []
    for px in closes:
        row = peg_band_position(px)
        regime = str(row["regime"])
        counts[regime] = counts.get(regime, 0) + 1
        if regime == "OUTSIDE_BAND":
            outside.append(px)
    n = len(closes)
    out["n_bars"] = n
    out["regime_share"] = {k: round(v / n, 6) for k, v in sorted(counts.items())}
    out["outside_band_prints"] = len(outside)
    out["outside_band_extremes"] = (min(outside), max(outside)) if outside else ()
    out["current"] = peg_band_position(closes[-1])
    out["measured"] = 1
    out["outcome"] = "OK"
    out["claim"] = ("USDHKD is a bounded process with two reflecting barriers; the regime shares "
                    "above are the unconditional description that every other Hong Kong domain "
                    "conditions on. OUTSIDE_BAND prints are reported and never normalised away: "
                    "a print beyond 7.7500 or 7.8500 is either a bad tick or the end of the "
                    "currency board, and those must never be confused with each other.")
    if lab is not None and outside:
        ctx.note("outside_band", f"{len(outside)} USDHKD closes printed outside 7.7500-7.8500 on "
                                 f"this tape; treat as data quality until proven otherwise")
    return out


CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("hk_peg_band_position",
          domain_ids=("hk_peg_band", "hk_cu_intervention", "hk_hibor_carry"),
          kind="microstructure",
          entry="countries.hk.pack:hk_peg_band_position",
          cadence_s=3600.0,
          steerable=False,
          notes="A fixed cost, not a steerable one: the band position is the conditioning "
                "variable for every other Hong Kong domain, so it must be recomputed every pass "
                "whether or not it yielded a discovery last week."),
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
