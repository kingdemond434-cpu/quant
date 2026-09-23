"""THE TAIWAN COUNTRY PACK -- and it opens with an absence, not an instrument.

USDTWD IS NOT IN THE BROKER UNIVERSE. The New Taiwan dollar is not deliverable offshore and
domestic corporates have been barred from non-deliverable forwards since 1998, so even the
offshore NDF market is thin. Taiwan is the only country in this package whose OWN_PRICE tuple is
EMPTY, and that is the first fact of the pack rather than an oversight: every Taiwanese mechanism
here has to arrive in somebody else's instrument to be tradable at all, and one whole domain
(`tw_nontradable_currency_routing`) and one whole transmission seed exist to MEASURE the proxy
error that routing inherits, instead of pretending a Korean instrument is a Taiwanese one.

WHY TAIWAN IS NOT KOREA WITH DIFFERENT NOUNS, despite both being semiconductor exporters:

  * THE WORLD'S EARLIEST DEMAND SIGNAL, TWICE A MONTH. 外銷訂單 -- export ORDERS, not shipments
    -- are published around the 20th and lead actual exports by one to three months. Then every
    listed company must publish MONTHLY REVENUE by the 10th of the following month, a
    fundamental disclosure with no equivalent in Korea, Japan or the United States. Aggregated
    to a sector, it is a mid-quarter read on the earnings of companies listed in New York.
  * A QUARTERLY CENTRAL BANK WITH MORE THAN ONE INSTRUMENT. The CBC meets four times a year, not
    eight, moves in 12.5 basis point steps almost nobody else uses, and routinely acts through
    the reserve requirement and selective property credit controls INSTEAD of the rate. A
    rate-only reading records the September 2024 meeting as a non-event when it was not.
  * A DIRTY FLOAT WITH A SIGNATURE IN THE LAST MINUTES OF THE DAY. The documented smoothing
    behaviour sits before the 16:00 Taipei close -- 尾盤 -- and the FX market stays open for two
    and a half hours after the equity market shuts. That test CANNOT BE RUN ON THIS BOX because
    USDTWD is not on the tape, and the pack records that as UNMEASURED by name.
  * THE THIRD WEDNESDAY, AND A SETTLEMENT WIDTH BETWEEN ITS NEIGHBOURS. TAIFEX settles on the
    third Wednesday from the TAIEX over the LAST THIRTY MINUTES of the cash session -- wider
    than Korea's ten-minute auction, narrower than Hong Kong's whole-day average. Three
    neighbours, three settlement widths, one cross-pack experiment.
  * TYPHOONS STILL CLOSE THE MARKET. Hong Kong stopped doing this on 2024-09-23 and Taiwan did
    not, which makes Taiwan the natural control for that change and a live source of unscheduled
    gap events no calendar predicts.
  * A LIFE-INSURANCE SECTOR TOO BIG FOR ITS OWN BOND MARKET. Taiwanese insurers hold enormous
    offshore portfolios against TWD liabilities and roll short-dated hedges against long-dated
    assets forever, with a regulatory FX valuation reserve acting as a dial on how much they are
    forced to hedge. The May 2025 appreciation shock is what that reflexivity looks like.

WHAT THIS PACK MAY NOT DO. The two-lane order (2026-09-06) binds harder here than anywhere else
in the package, because the Taiwanese index is dominated by a single company and the temptation
to hunt it is correspondingly large: the semiconductor complex is an OBSERVABLE, monthly revenue
is read ONLY in aggregate, and no single name is ever a symbol on a docket. No crypto-exchange
venue is named, subscribed or crawled anywhere in this pack (universe mandate, 2026-08-18).
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


CODE = "tw"
NAME = "Taiwan"
REGION_COMMAND = "asia"  # country_lab.REGION_COMMANDS; EAST ASIA is this package's own grouping
CURRENCY = "TWD"
NATIVE_LANGUAGES = ("zh-Hant",)

#: TAIWAN HAS NO OWN PRICE ON THIS BROKER. USDTWD is not in the registry, the TWD is not
#: deliverable offshore, and domestic corporates have been barred from NDFs since 1998. This tuple
#: is EMPTY on purpose and it is the first fact of the pack, not an oversight: every Taiwanese
#: mechanism here has to arrive in somebody else's instrument to be tradable at all.
OWN_PRICE: tuple[str, ...] = ()

#: What the TW department may place an order in. Every one of these is a CARRIER -- none of them
#: is Taiwanese. NAS100 and US500 carry the electronics demand cycle, USDKRW carries the regional
#: FX and semiconductor twin, JPN225 and HK50 carry the Asian session, XAUUSD carries the
#: geopolitical premium.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "NAS100", "US500", "US2000", "USDKRW", "USDJPY", "JPN225", "HK50", "USDSGD", "USDCNH",
    "XAUUSD", "XCUUSD", "XTIUSD")

ABSENT_INSTRUMENTS: tuple[dict[str, str], ...] = (
    {"instrument": "USDTWD",
     "why": "NOT IN desks/mt5/data/universe/universe.json. The New Taiwan dollar is not "
            "deliverable offshore; domestic corporates have been barred from non-deliverable "
            "forwards since 1998, so even the offshore NDF market is thin and is not a CFD "
            "anywhere in the registry",
     "carried_by": "USDKRW as the regional semiconductor-exporter FX twin, and USDJPY and "
                   "USDSGD as the broader Asian dollar legs. THE BASIS IS NOT ZERO and every "
                   "edge that routes this way says so: USDKRW is a proxy for TWD, not a "
                   "substitute, and the residual is a real risk rather than a rounding error"},
    {"instrument": "TAIEX (加權指數) and the electronics sub-index",
     "why": "no Taiwanese equity index CFD in the broker registry",
     "carried_by": "NAS100 for the semiconductor and technology beta, and JPN225 and HK50 for "
                   "the Asian session leg"},
    {"instrument": "TAIFEX TX index futures and weekly options",
     "why": "absent; the Taiwanese derivatives complex is not tradable here",
     "carried_by": "nothing directly. The pack's own miner measures whether the third-Wednesday "
                   "expiry SPILLS into the carriers, which is a weaker claim than measuring the "
                   "contract and is stated as such"},
    {"instrument": "TWD NDF and the TAIFX1-settled forward curve",
     "why": "not a CFD in the registry, and the onshore market is closed to domestic corporates "
            "by regulation",
     "carried_by": "nothing. The carry and hedging-cost leg of the life-insurer mechanism is "
                   "UNMEASURED BY NAME on this desk rather than proxied from another currency"},
    {"instrument": "Taiwanese government bonds",
     "why": "no Taiwanese rates instrument is quoted",
     "carried_by": "UST10Y as the global rates leg only; the Taiwan-specific term premium and "
                   "the domestic yield the life insurers cannot earn are left UNMEASURED"},
)


# --------------------------------------------------------------------------- central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Central Bank of the Republic of China (Taiwan)",
    "native_name": "中央銀行",
    "committee": "理監事聯席會議 (the Joint Board of Directors and Supervisors meeting)",
    "policy_rate": "重貼現率 (the discount rate), moved historically in unusually small steps -- "
                   "12.5 basis points is a normal Taiwanese increment and is seen almost nowhere "
                   "else",
    "meetings_per_year": 4,
    "schedule_rule": (
        "QUARTERLY, not eight times a year. The Joint Board meets in the last month of each "
        "quarter -- March, June, September and December -- usually on a Thursday, and the "
        "decision is announced AFTER the local market closes, at about 16:00 to 17:00 Taipei "
        "(08:00 to 09:00 UTC), followed by a press conference. The minutes (議事錄摘要) are "
        "published about three months later, alongside the NEXT meeting, which is the longest "
        "minutes lag in this package and makes them useless as a contemporaneous signal."),
    "minutes_rule": (
        "About three months, published with the following meeting. A dissent revealed then is "
        "news about a decision the market has already traded through a full quarter."),
    "timezone": "TST = UTC+8 all year; Taiwan observes NO daylight saving.",
    "fx_operations": (
        "THE DIRTY FLOAT IS THE MECHANISM. The CBC states that it smooths disorderly movements, "
        "and the documented signature is activity in the final minutes before the 16:00 Taipei "
        "close -- 尾盤 -- which is why the closing rate and the intraday path can tell different "
        "stories on the same day. Beyond the closing window the toolkit includes moral suasion "
        "on the banks, limits on non-resident TWD accounts, and reserve requirements. The US "
        "Treasury's monitoring list is a real constraint on how one-sided this can be."),
    "intervention_disclosure": (
        "Not disclosed as transactions. The monthly 外匯存底 print (about the 5th) and the "
        "quarterly balance of payments are the public traces, and the CBC also publishes a "
        "semi-annual net FX transaction figure under the US Treasury reporting arrangement -- "
        "far too slow and too aggregated to signal."),
    "other_instruments": (
        "The CBC uses the reserve requirement and SELECTIVE CREDIT CONTROLS on property lending "
        "as independent instruments. The September 2024 meeting is the canonical case: the "
        "policy rate was held and the reserve requirement was raised, so a study that reads only "
        "the rate records that meeting as a non-event when it was not."),
    "decision_dates": {
        2020: ("2020-03-19", "2020-06-18", "2020-09-17", "2020-12-17"),
        2021: ("2021-03-18", "2021-06-17", "2021-09-23", "2021-12-16"),
        2022: ("2022-03-17", "2022-06-16", "2022-09-22", "2022-12-15"),
        2023: ("2023-03-23", "2023-06-15", "2023-09-21", "2023-12-14"),
        2024: ("2024-03-21", "2024-06-13", "2024-09-19", "2024-12-19"),
        2025: ("2025-03-20", "2025-06-19", "2025-09-18", "2025-12-18"),
        2026: (),
    },
    "decision_dates_status": {
        2020: "RECONSTRUCTED_FROM_PUBLIC_RECORD -- 2020-03-19 is the pandemic cut to 1.125%",
        2021: "RECONSTRUCTED_FROM_PUBLIC_RECORD",
        2022: "RECONSTRUCTED_FROM_PUBLIC_RECORD -- the 12.5 basis point steps begin here",
        2023: "RECONSTRUCTED_FROM_PUBLIC_RECORD",
        2024: "RECONSTRUCTED_FROM_PUBLIC_RECORD -- 2024-03-21 is the surprise 12.5bp hike and "
              "2024-09-19 is the hold-plus-reserve-requirement meeting",
        2025: "RECONSTRUCTED_FROM_PUBLIC_RECORD",
        2026: "RULE_ONLY -- quarterly, in the last month of each quarter, usually the third "
              "Thursday, announced after the Taipei close. The CBC publishes the dates in "
              "advance; VERIFY against cbc.gov.tw before any 2026 event window, because a "
              "guessed decision date is a fabricated event.",
    },
    "verification": "Every date above must be re-read from the CBC's own 理監事會議 archive "
                    "before it anchors an event study. They are recorded here so a miner has a "
                    "starting grid, not so a study can skip the check.",
}


# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: dict[str, Any] = {
    "taifx1": {
        "name": "TAIFX1 -- the USD/TWD NDF fixing reference",
        "publisher": "台北外匯經紀公司 (Taipei Forex Inc)",
        "published_local": "11:00 Taipei",
        "published_utc": "03:00 UTC",
        "note": "The reference the offshore NDF settles against. THE INSTRUMENT IT PRICES IS NOT "
                "QUOTED BY THIS BROKER, which is why this pack's fixing row carries no "
                "instruments: recording a fixing whose asset the desk cannot trade is honest; "
                "attaching it to USDKRW would be a fabrication.",
    },
    "closing_rate": {
        "name": "the Taipei interbank closing rate",
        "published_local": "16:00 Taipei",
        "published_utc": "08:00 UTC",
        "note": "THE MOST IMPORTANT MINUTE IN THE TAIWANESE DAY. The onshore interbank session "
                "runs 09:00 to 16:00 Taipei, the cash equity market closes two and a half hours "
                "earlier at 13:30, and the documented smoothing signature sits in the final "
                "minutes before this print. The closing rate and the intraday path can therefore "
                "disagree, and which of the two a study uses changes its answer.",
    },
    "onshore_hours": {
        "session": "09:00-16:00 Taipei = 01:00-08:00 UTC for the interbank FX market",
        "note": "Note the ASYMMETRY with the cash equity market, which closes at 13:30 Taipei "
                "(05:30 UTC). For two and a half hours the currency trades with the equity "
                "market shut, and the foreign-investor flow print lands in that window.",
    },
    "ndf_restriction": {
        "rule": "Domestic corporates have been barred from non-deliverable forwards since 1998; "
                "access is restricted to offshore counterparties and offshore banking units, "
                "with limited domestic bank participation since 2014",
        "consequence": "the offshore expression of a TWD view is thin and expensive, which is "
                       "why a Taiwan view is usually expressed in KOREAN won or in the "
                       "technology indices instead -- and that substitution is itself the "
                       "reason this pack's edges terminate where they do",
    },
    "dst": "NONE. TST is UTC+8 year-round.",
}

SETTLEMENT_CONVENTIONS: dict[str, Any] = {
    "spot": "T+2 onshore",
    "deliverability": "the TWD is NOT deliverable offshore and the onshore market is tightly "
                      "regulated; non-resident TWD accounts are limited",
    "equity_settlement": "T+2 at the TWSE; foreign investors settle through custodians and the "
                         "FX leg follows, so the daily foreign net-buy print LEADS its own "
                         "currency flow",
    "life_insurer_rolls": "the single largest structural FX flow in Taiwan. Life insurers hold "
                          "enormous offshore bond portfolios against TWD liabilities and roll "
                          "SHORT-DATED hedges against LONG-DATED assets, permanently. The rolls "
                          "concentrate at month end and the hedge ratio is disclosed monthly",
    "fx_valuation_reserve": "外匯價格變動準備金 -- a regulatory reserve that lets insurers absorb "
                            "FX losses without taking them to earnings, expanded in 2022 and "
                            "again in 2024. It DAMPENS forced hedging exactly when the currency "
                            "moves most, which makes it a rule-based modifier of a forced flow "
                            "and a genuine research object",
    "monthly_revenue": "listed companies must publish MONTHLY revenue by the 10th of the "
                       "following month. There is no equivalent disclosure in Korea, Japan or "
                       "the United States, and aggregated to a sector it is the highest-frequency "
                       "public fundamental series in this package",
}

EXCHANGES: dict[str, Any] = {
    "cash": {
        "name": "Taiwan Stock Exchange (臺灣證券交易所, TWSE) and the Taipei Exchange (櫃買中心)",
        "hours_local": "09:00-13:30 Taipei",
        "hours_utc": "01:00-05:30 UTC",
        "closing_auction": "13:25-13:30 Taipei (05:25-05:30 UTC), a five-minute closing call "
                           "auction introduced on 2020-03-23; before that date the close was a "
                           "continuous-trading print and the two are not comparable",
        "after_hours": "14:00-14:30 Taipei fixed-price trading",
        "price_limit": "+/-10% daily, widened from +/-7% on 2015-06-01 -- a dated regime break "
                       "that changes the tail of every Taiwanese return distribution",
        "day_trading": "現股當沖 day-trade tax was halved in 2017 and the relief extended "
                       "repeatedly; retail day-trade share rose sharply afterwards and that is a "
                       "liquidity regime, not a detail",
        "disclosure": "TWSE publishes 三大法人買賣金額統計表 -- foreign and mainland investors, "
                      "investment trusts and dealers -- DAILY after the close, free",
    },
    "derivatives": {
        "name": "Taiwan Futures Exchange (臺灣期貨交易所, TAIFEX)",
        "contracts": "TX (TAIEX futures), TE and TF sector futures, TXO options including "
                     "weeklies, and single-stock futures",
        "hours_local": "08:45-13:45 Taipei day session, and a 15:00-05:00 after-hours session "
                       "introduced on 2017-05-15",
        "expiry_rule": "THIRD WEDNESDAY of the delivery month -- not Korea's second Thursday and "
                       "not Hong Kong's second-last business day. Weekly options expire each "
                       "Wednesday",
        "settlement_price": "the final settlement price is derived from the index during the "
                            "LAST THIRTY MINUTES of the cash session on the final settlement "
                            "day, which is a window between Korea's ten-minute auction and Hong "
                            "Kong's whole-day average -- three neighbours, three settlement "
                            "widths, and that contrast is a real cross-pack experiment",
        "disclosure": "TAIFEX publishes 三大法人未平倉 (open interest by institutional type) and "
                      "大額交易人未沖銷部位 (top-five and top-ten large-trader net positions) "
                      "DAILY -- a granular public positioning series that is rare anywhere",
    },
    "weather": {
        "rule": "TAIWAN STILL CLOSES FOR TYPHOONS. When the local government declares a typhoon "
                "day, the securities and futures markets close, and this happens several times "
                "in an active season",
        "why_it_is_here": "Hong Kong stopped doing this on 2024-09-23. Taiwan did not. That "
                          "makes Taiwan the NATURAL CONTROL for the Hong Kong rule change, and "
                          "it makes Taiwanese unscheduled closures a live source of gap events "
                          "that no calendar can predict",
    },
}

FISCAL_YEAR: dict[str, str] = {
    "government": "31 December. Taiwan moved from a July-to-June fiscal year to the calendar "
                  "year effective 2001, with a six-month transitional period in 2000 -- so any "
                  "fiscal series spanning that boundary has a stub period in it",
    "corporate": "31 December for listed companies, with MONTHLY revenue disclosure by the 10th "
                 "of the following month and quarterly financial statements",
    "budget_cycle": "the central government budget is submitted to the Legislative Yuan in "
                    "August and passed before the year begins",
}
#: The framework's field is a bare MM-DD; FISCAL_YEAR above is why it is this one.
FISCAL_YEAR_END = "12-31"


# --------------------------------------------------------------------------- holidays
_TW_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-01": "開國紀念日 Founding Day",
        "2024-02-06": "農曆春節休市 Lunar New Year market closure begins",
        "2024-02-07": "農曆春節休市 Lunar New Year market closure",
        "2024-02-08": "小年夜 Lunar New Year",
        "2024-02-09": "除夕 Lunar New Year's Eve",
        "2024-02-12": "春節 Lunar New Year day 3",
        "2024-02-13": "春節 Lunar New Year day 4",
        "2024-02-14": "春節彈性放假 Lunar New Year flexible holiday",
        "2024-02-28": "和平紀念日 Peace Memorial Day",
        "2024-04-04": "兒童節及清明節 Children's Day and Tomb Sweeping Day",
        "2024-04-05": "清明節 Tomb Sweeping Day",
        "2024-05-01": "勞動節 Labour Day",
        "2024-06-10": "端午節 Dragon Boat Festival",
        "2024-09-17": "中秋節 Mid-Autumn Festival",
        "2024-10-10": "國慶日 National Day",
    },
    2025: {
        "2025-01-01": "開國紀念日 Founding Day",
        "2025-01-24": "農曆春節休市 Lunar New Year market closure begins",
        "2025-01-27": "小年夜 the day before Lunar New Year's Eve",
        "2025-01-28": "除夕 Lunar New Year's Eve",
        "2025-01-29": "春節 Lunar New Year day 1",
        "2025-01-30": "春節 Lunar New Year day 2",
        "2025-01-31": "春節 Lunar New Year day 3",
        "2025-02-28": "和平紀念日 Peace Memorial Day",
        "2025-04-03": "兒童節彈性放假 Children's Day flexible holiday",
        "2025-04-04": "兒童節及清明節 Children's Day and Tomb Sweeping Day",
        "2025-05-01": "勞動節 Labour Day",
        "2025-05-30": "端午節前補假 Dragon Boat make-up holiday (31 May is a Saturday)",
        "2025-09-29": "教師節補假 Teachers' Day make-up (restored by the 2025 amendment, VERIFY)",
        "2025-10-06": "中秋節 Mid-Autumn Festival",
        "2025-10-10": "國慶日 National Day",
        "2025-10-24": "光復節補假 Retrocession Day make-up (restored by the 2025 amendment, "
                      "VERIFY)",
        "2025-12-25": "行憲紀念日 Constitution Day (restored by the 2025 amendment, VERIFY)",
    },
    2026: {
        "2026-01-01": "開國紀念日 Founding Day",
        "2026-01-02": "開國紀念日彈性放假 Founding Day flexible holiday",
        "2026-02-16": "除夕 Lunar New Year's Eve",
        "2026-02-17": "春節 Lunar New Year day 1",
        "2026-02-18": "春節 Lunar New Year day 2",
        "2026-02-19": "春節 Lunar New Year day 3",
        "2026-02-20": "春節彈性放假 Lunar New Year flexible holiday",
        "2026-02-27": "和平紀念日補假 Peace Memorial Day make-up (28 February is a Saturday)",
        "2026-04-03": "兒童節補假 Children's Day make-up (4 April is a Saturday)",
        "2026-04-06": "清明節補假 Tomb Sweeping make-up (5 April is a Sunday)",
        "2026-05-01": "勞動節 Labour Day",
        "2026-06-19": "端午節 Dragon Boat Festival",
        "2026-09-25": "中秋節 Mid-Autumn Festival",
        "2026-09-28": "教師節 Teachers' Day (restored by the 2025 amendment, VERIFY)",
        "2026-10-09": "國慶日補假 National Day make-up (10 October is a Saturday)",
        "2026-10-26": "光復節補假 Retrocession Day make-up (25 October is a Sunday, VERIFY)",
        "2026-12-25": "行憲紀念日 Constitution Day (restored by the 2025 amendment, VERIFY)",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": (
        "Taiwan's closures come from four layers and only the first is a weekday rule. "
        "(1) FIXED SOLAR DATES: 1 January (開國紀念日), 28 February (和平紀念日), 4 April "
        "(兒童節), 1 May (勞動節), 10 October (國慶日), and -- restored by the 2025 amendment to "
        "the 紀念日及節日實施條例 -- 28 September (教師節), 25 October (光復節) and 25 December "
        "(行憲紀念日). (2) LUNAR AND SOLAR-TERM DATES, tabulated here because they cannot be "
        "derived: 除夕 and 春節 (the lunar new year block, which in Taiwan uniquely includes "
        "小年夜, the day BEFORE the eve), 端午節 (the fifth of the fifth lunar month), 中秋節 "
        "(the fifteenth of the eighth), and 清明節, which follows the solar term and falls on "
        "4 or 5 April. (3) MAKE-UP AND FLEXIBLE HOLIDAYS (補假 and 彈性放假): a holiday on a "
        "weekend moves to an adjacent weekday, and the Executive Yuan bridges isolated days, "
        "sometimes designating a Saturday as a working day in exchange. (4) TWSE'S OWN CLOSURE, "
        "which around the lunar new year is LONGER than the statutory holiday by one or two "
        "settlement days. ON TOP OF ALL OF THAT: TAIWAN STILL CLOSES FOR TYPHOONS. When a local "
        "government declares a typhoon day the securities and futures markets shut, several "
        "times in an active season, with a day's notice at most. No rule predicts those and "
        "they are a dataset of their own."),
    "authority": "紀念日及節日實施條例 and the Directorate-General of Personnel Administration "
                 "(行政院人事行政總處) annual calendar, plus TWSE's own 行事曆; the securities "
                 "market calendar is the binding one and it differs from the public-holiday "
                 "calendar at the lunar new year",
    "table": _TW_HOLIDAYS,
    "status": {
        2024: "GAZETTED",
        2025: "GAZETTED_WITH_AMENDMENT_CAVEAT -- the 教師節, 光復節 and 行憲紀念日 entries come "
              "from the 2025 amendment to the 紀念日及節日實施條例 and their FIRST YEAR OF "
              "APPLICATION must be confirmed against the official calendar before any 2025 "
              "event window relies on them. They are marked VERIFY in the table itself.",
        2026: "DERIVED_FROM_RULE -- the lunar anchors (除夕 2026-02-16, 春節 2026-02-17, 端午節 "
              "2026-06-19, 中秋節 2026-09-25) are certain; the make-up placements follow the "
              "substitution law; the 彈性放假 bridges and the exact TWSE lunar-new-year block "
              "are the Executive Yuan's to decide and are NOT knowable from a rule. VERIFY "
              "against the official calendar.",
    },
    "market_effect": (
        "Taiwan's holidays reach this desk only through the carriers, because no Taiwanese "
        "instrument is quoted here. What they DO change is the information flow: the lunar new "
        "year closure is among the longest in Asia and it silences the world's most important "
        "electronics supply chain for over a week, while NAS100 and USDKRW keep trading. The "
        "monthly revenue disclosures due by the 10th are also pushed by it, which distorts "
        "January and February exactly as the Chinese calendar does. And because Taiwan still "
        "closes for typhoons, it generates unscheduled gaps that Hong Kong -- since 2024-09-23 "
        "-- no longer does, which is what makes Taiwan the control for that change."),
    "callable": "countries.tw.pack:holidays",
}


def holidays(year: int) -> dict[str, str]:
    """The Taiwanese market-closure table for one year. `{}` for an untabulated year."""
    return holiday_table(HOLIDAYS_RULE, year)


def _is_closed(day: date) -> bool:
    """True when the Taiwanese cash market is shut: a weekend or a tabulated closure.

    The 彈性放假 make-up WORKING Saturdays are NOT modelled: they turn a handful of Saturdays
    into trading days, they are decided year by year by the Executive Yuan, and guessing which
    ones would be worse than saying so. Typhoon closures are not modelled either -- no rule
    predicts them and they live in the `tw_typhoon_closures` dataset instead.
    """
    return day.weekday() >= 5 or day.isoformat() in holidays(day.year)


def tw_expiry_dates(year: int) -> tuple[dict[str, Any], ...]:
    """TAIEX futures expiries for a year, by the THIRD-WEDNESDAY rule.

    Code rather than a table because the rule is computable. A third Wednesday that is closed
    rolls FORWARD to the next open session, and this function reports the collision rather than
    silently moving the date: a study anchored on the nominal Wednesday when the market was shut
    is measuring a session that did not happen.
    """
    rows: list[dict[str, Any]] = []
    for month in range(1, 13):
        nominal = nth_weekday(year, month, 2, 3)  # Wednesday = 2
        day = nominal
        for _ in range(10):
            if not _is_closed(day):
                break
            day = date.fromordinal(day.toordinal() + 1)
        rows.append({
            "date": day.isoformat(), "nominal": nominal.isoformat(), "month": month,
            "rolled": day != nominal,
            "settlement": "derived from the TAIEX during the LAST THIRTY MINUTES of the cash "
                          "session (05:00-05:30 UTC) on the final settlement day",
        })
    return tuple(rows)


# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"id": "twse_three_institutions",
     "name": "TWSE 三大法人買賣金額統計表 -- daily net buy by institutional type",
     "covers": "foreign and mainland investors, domestic investment trusts, and dealers, in "
               "aggregate and per security",
     "frequency": "daily", "lag": "same day, after the 13:30 Taipei close",
     "root": "twse.com.tw", "licence": "free, public",
     "note": "THE flagship Taiwanese flow series and the closest public analogue to Korea's KRX "
             "investor file. Foreign net buying is the single most-watched number in the "
             "Taiwanese market."},
    {"id": "taifex_institutional_oi",
     "name": "TAIFEX 三大法人未平倉 -- daily futures and options open interest by investor type",
     "covers": "net open interest in TX futures and TXO options by institutional category",
     "frequency": "daily", "lag": "same day",
     "root": "taifex.com.tw", "licence": "free, public",
     "note": "Taiwan publishes institutional derivatives positioning daily and free. Combined "
             "with Korea's equivalent, the two give the region a positioning panel that the "
             "CFTC provides for no Asian currency at all."},
    {"id": "taifex_large_traders",
     "name": "TAIFEX 大額交易人未沖銷部位 -- top-five and top-ten large-trader net positions",
     "covers": "concentration of open interest among the largest traders, by contract",
     "frequency": "daily", "lag": "same day",
     "root": "taifex.com.tw", "licence": "free, public",
     "note": "A concentration measure with no Western equivalent at this frequency. It answers a "
             "question a COT report cannot: not just who is long, but how few of them there are."},
    {"id": "twse_margin_balances",
     "name": "TWSE and TPEx 融資融券餘額 -- margin and short-sale balances",
     "covers": "retail margin financing and securities lending outstanding",
     "frequency": "daily", "lag": "same day",
     "root": "twse.com.tw, tpex.org.tw", "licence": "free, public",
     "note": "Taiwanese margin is CAPPED BY REGULATION at a financing ratio set for listed and "
             "OTC securities, which makes this a bounded quantity rather than a free one -- a "
             "different regime from Korea's."},
    {"id": "cbc_fx_reserves",
     "name": "中央銀行 外匯存底 -- official FX reserves",
     "covers": "the headline reserve stock",
     "frequency": "monthly", "lag": "about five days",
     "root": "cbc.gov.tw", "licence": "free, public",
     "note": "Valuation effects dominate the monthly change, so the raw print is a weak "
             "intervention proxy; it is kept for ex-post attribution and labelled as such."},
    {"id": "fsc_life_insurer_hedging",
     "name": "金管會保險局 -- life insurers' foreign investment and hedge ratios",
     "covers": "offshore investment balances, hedged share, and the FX valuation reserve",
     "frequency": "monthly", "lag": "about one month",
     "root": "fsc.gov.tw, ib.gov.tw", "licence": "free, public",
     "note": "The disclosure that makes Taiwan's largest structural FX flow observable at all. "
             "The hedge ratio is a POLICY-MODIFIED quantity because the FX valuation reserve "
             "changes how much loss an insurer must recognise, and therefore how much it must "
             "hedge."},
    {"id": "moea_export_orders",
     "name": "經濟部 外銷訂單 -- export orders",
     "covers": "orders received by Taiwanese manufacturers, by product and by destination",
     "frequency": "monthly", "lag": "about twenty days",
     "root": "moea.gov.tw", "licence": "free, public",
     "note": "ORDERS, not shipments. This is the earliest public read on global electronics "
             "demand anywhere in the world and it leads actual exports by one to three months."},
    {"id": "cftc_cot_absent",
     "name": "CFTC Commitments of Traders -- NO TWD CONTRACT EXISTS",
     "covers": "nothing Taiwanese",
     "frequency": "n/a", "lag": "n/a",
     "root": "cftc.gov", "licence": "free, public",
     "note": "DECLARED ABSENT BY NAME, and doubly so here: there is no TWD futures contract at "
             "the CFTC AND no USDTWD on this broker, so Taiwan is the one country in this "
             "package with neither a positioning series for its currency nor a way to trade it. "
             "The TAIFEX tables above are positioning in the EQUITY complex and are not a "
             "substitute for currency positioning."},
)

# --------------------------------------------------------------------------- terminology
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "core": ("新台幣", "台幣", "匯率", "升值", "貶值", "美元兌新台幣", "外匯市場",
             "台北外匯經紀公司", "外匯存底"),
    "tw_cbc_reaction": ("中央銀行", "理監事會", "重貼現率", "楊金龍", "升息", "降息",
                        "選擇性信用管制", "存款準備率", "議事錄摘要", "央行理事"),
    "tw_close_smoothing": ("阻升", "阻貶", "尾盤", "尾盤拉升", "收盤價", "調節", "進場調節",
                           "熱錢", "匯市干預", "央行調節"),
    "tw_export_order_cycle": ("外銷訂單", "出口訂單", "接單", "海外生產比", "出口", "出口年增",
                              "財政部關務署", "貿易順差", "轉單效應"),
    "tw_semiconductor_cycle": ("半導體", "晶圓代工", "晶圓", "先進製程", "封裝測試", "記憶體",
                              "產能利用率", "資本支出", "月營收", "電子類指數", "供應鏈"),
    "tw_foreign_equity_flow": ("外資", "外資買超", "外資賣超", "三大法人", "投信", "自營商",
                               "外資持股比率", "摩根士丹利指數", "指數調整", "權值股"),
    "tw_index_expiry": ("台指期", "期貨結算日", "結算", "第三個星期三", "未平倉", "留倉",
                        "選擇權", "週選", "最大未平倉量", "正價差", "逆價差"),
    "tw_life_insurer_hedging": ("壽險業", "國外投資", "避險比率", "避險成本",
                                "外匯價格變動準備金", "傳統避險", "一籃子貨幣避險",
                                "匯損", "海外債"),
    "tw_retail_and_daytrade": ("散戶", "當沖", "現股當沖", "融資餘額", "融券餘額", "斷頭",
                               "券資比", "隔日沖", "主力"),
    "tw_microstructure_regimes": ("漲跌幅限制", "百分之十", "收盤前集合競價", "盤後定價",
                                  "颱風假", "停止交易", "休市", "逐筆交易"),
    "tw_supply_chain_transmission": ("供應鏈", "轉單", "拉貨", "庫存調整", "急單", "產業鏈", "上游",
                        "下游", "代工"),
    "tw_geopolitical": ("台海", "地緣政治", "軍演", "兩岸關係", "風險溢價", "台海緊張"),
    "tw_nontradable_currency_routing": ("無本金交割遠期外匯", "境外", "海外市場", "不可交割",
                                "資本管制", "非居民帳戶"),
    "tw_policy_and_fiscal": ("行政院", "金管會", "經濟部", "主計總處", "國發會", "景氣燈號",
                             "採購經理人指數"),
    "tw_energy_and_power": ("備轉容量率", "限電", "跳電", "水庫 蓄水率", "枯水期",
                            "台電", "用電量", "能源進口", "晶圓廠 用電", "缺水 危機"),
}


# --------------------------------------------------------------------------- source classes
#: GROUNDS THIS PACK REFUSES TO CRAWL, named rather than silently absent, and surfaced in the
#: `source_graph` layer because the edges a graph deliberately does not traverse are part of it.
REFUSED_SOURCES: tuple[dict[str, str], ...] = (
    {"ground": "crypto-exchange order books, venue APIs and venue-native feeds",
     "why": "MT5 universe mandate (2026-08-18): no crypto-exchange ground is ever hunted again"},
    {"ground": "paywalled vendor terminal content and its redistribution",
     "why": "licence; the desk holds no redistribution right"},
    {"ground": "single-name Taiwanese equity hypothesis mining",
     "why": "two-lane order (2026-09-06), and it binds harder here than anywhere else in the "
            "package because the Taiwanese index is dominated by one company and the temptation "
            "to hunt it is correspondingly large. Monthly revenue is read ONLY in aggregate"},
)

SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    source_class("tw_official", "The central bank, the statistics bureau, customs and the "
                                "ministries",
                 layer="official",
                 roots=("cbc.gov.tw", "dgbas.gov.tw", "moea.gov.tw", "mof.gov.tw",
                        "customs.gov.tw", "ndc.gov.tw", "fsc.gov.tw", "ib.gov.tw"),
                 queries=("理監事會議 決議", "議事錄摘要", "外匯存底", "外銷訂單統計",
                          "進出口貿易統計", "景氣對策信號", "選擇性信用管制",
                          "壽險業 國外投資", "外匯價格變動準備金"),
                 languages=("zh-Hant", "en"), access_label="OPEN_DATA",
                 credibility="AUTHORITATIVE", predictive_state="UNTESTED",
                 licence="free, public",
                 notes="moea.gov.tw is the highest-value root in the pack: 外銷訂單 around the "
                       "20th are ORDERS rather than shipments and lead actual exports by one to "
                       "three months, which makes them the earliest public read on global "
                       "electronics demand anywhere in the world."),
    source_class("tw_institutional", "TWSE, TPEx, TAIFEX and the disclosure system",
                 layer="institutional",
                 roots=("twse.com.tw", "tpex.org.tw", "taifex.com.tw", "mops.twse.com.tw",
                        "tdcc.com.tw (集保結算所)"),
                 queries=("三大法人買賣金額統計表", "外資及陸資買賣超彙總表",
                          "三大法人未平倉", "大額交易人未沖銷部位", "融資融券餘額",
                          "每月營業收入", "集保戶股權分散表", "結算價 計算"),
                 languages=("zh-Hant", "en"), access_label="OPEN_DATA",
                 credibility="AUTHORITATIVE", predictive_state="UNTESTED",
                 licence="free, public",
                 notes="TAIFEX publishes institutional open interest AND large-trader "
                       "concentration daily and free, which answers a question no COT report "
                       "does: not just who is long, but how few of them there are. MOPS carries "
                       "the monthly revenue disclosures, read here ONLY in aggregate."),
    source_class("tw_academic", "Taiwanese journals, theses and the policy institutes",
                 layer="academic",
                 roots=("airitilibrary.com", "ndltd.ncl.edu.tw", "econ.sinica.edu.tw",
                        "cier.edu.tw", "tier.org.tw", "papers.ssrn.com"),
                 queries=("台指期 結算日 效應", "外資買賣超 報酬", "央行 阻升 尾盤",
                          "壽險 避險 成本", "漲跌幅限制 放寬", "收盤前集合競價 影響",
                          "現股當沖 降稅 效果"),
                 languages=("zh-Hant", "en"), access_label="PUBLIC_WITH_TERMS",
                 credibility="RELIABLE", predictive_state="UNTESTED",
                 licence="Airiti and the national thesis repository are largely free; some "
                         "journals are licensed and only abstracts are read",
                 notes="The Taiwanese thesis literature is unusually rich on exactly this pack's "
                       "questions -- closing-auction effects, third-Wednesday settlement, "
                       "closing-rate smoothing -- and it is essentially invisible to an "
                       "English-language search. CIER's PMI and TIER's indicators are free and "
                       "are genuine leading series."),
    source_class("tw_practitioner", "Taiwanese systematic-trading communities, tools and code",
                 layer="practitioner",
                 roots=("github.com (FinMind, TWSE and TAIFEX wrappers)",
                        "cmoney.tw", "statementdog.com (財報狗)", "wearn.com",
                        "sinotrade.com.tw Shioaji API documentation and community"),
                 queries=("程式交易", "台指期 當沖 策略", "Shioaji API", "FinMind 資料",
                          "選擇權 賣方 策略", "回測 程式碼", "籌碼面 分析", "三大法人 籌碼"),
                 languages=("zh-Hant",), access_label="PUBLIC_WITH_TERMS",
                 credibility="UNRELIABLE", predictive_state="UNTESTED",
                 licence="per-repository and per-site; respect each licence",
                 notes="Taiwan has an unusually developed retail program-trading culture built "
                       "on broker APIs, and its public strategy write-ups state ENTRY AND EXIT "
                       "RULES explicitly. Credibility is UNRELIABLE and the rows are kept at low "
                       "weight rather than dropped: an exact rule is testable regardless of "
                       "whether the claimed equity curve is real."),
    source_class("tw_retail_ecology", "Taiwanese retail boards and their vernacular",
                 layer="retail_ecology",
                 roots=("ptt.cc (Stock 板)", "mobile01.com (投資理財)", "dcard.tw (股票)",
                        "cmoney.tw 社群"),
                 queries=("外資 買超", "台積電 撐盤", "尾盤 拉尾盤", "結算 作價", "當沖 被嘎",
                          "融資 斷頭", "航運 三雄", "存股"),
                 languages=("zh-Hant",), access_label="PUBLIC_SOCIAL",
                 credibility="FRINGE", predictive_state="UNTESTED",
                 licence="public web; VERBATIM CLAIMS only, never personal data, respecting "
                         "robots and rate limits",
                 notes="FRINGE AND KEPT AT LOW WEIGHT, never dropped. The PTT Stock board's "
                       "folklore about 結算作價 -- the claim that the third-Wednesday settlement "
                       "print is pushed -- is a dated, testable mechanism, and it is exactly the "
                       "claim this pack's custom miner exists to examine. That a board says it "
                       "is not evidence; that it says it on specific dates is data."),
    source_class("tw_app_ecosystem", "Taiwanese brokerage apps, quote apps and their ecosystem",
                 layer="app_ecosystem",
                 roots=("app listings and review text for the major Taiwanese brokerage and "
                        "quote apps", "cmoney.tw and moneydj.com mobile properties",
                        "sinotrade.com.tw and other broker API portals"),
                 queries=("券商 app 下單", "看盤 軟體", "API 下單 權限", "零股 交易 app",
                          "定期定額 app"),
                 languages=("zh-Hant",), access_label="ACCESS_UNCLEAR",
                 credibility="UNKNOWN", predictive_state="UNTESTED",
                 licence="app-store listing text is public; usage panels are vendor products "
                         "the desk does not subscribe to, and store terms restrict machine "
                         "extraction",
                 machine_use_allowed=True,
                 notes="REGISTERED AND NOT SCRAPED. The Taiwanese case is genuinely distinctive "
                       "even so: broker API access is retail-available, which is WHY the "
                       "practitioner layer above is as developed as it is. The app layer's "
                       "signal here is about program-trading participation rather than about "
                       "sentiment, and it remains unavailable to this desk."),
    source_class("tw_media", "The Taiwanese financial press",
                 layer="media",
                 roots=("ctee.com.tw (工商時報)", "money.udn.com (經濟日報)", "cnyes.com (鉅亨網)",
                        "moneydj.com", "news.cnyes.com", "technews.tw"),
                 queries=("央行 阻升", "新台幣 升值 壓力", "外資 大買", "外銷訂單 年增",
                          "月營收 創高", "壽險 匯損", "台股 萬八", "颱風 休市"),
                 languages=("zh-Hant",), access_label="PUBLIC_WITH_TERMS",
                 credibility="RELIABLE", predictive_state="NARRATIVE_FEATURE",
                 licence="public headlines and article text; respect robots and rate limits",
                 notes="NARRATIVE_FEATURE ON PURPOSE. The Chinese-language press reports the "
                       "closing-rate smoothing and the life-insurer hedging mechanics in "
                       "operational detail the English coverage summarises away -- and since "
                       "USDTWD is not on this desk's tape, press reporting is in several cases "
                       "the ONLY observable this pack has for its most important actor."),
    source_class("tw_archive", "Holiday calendars, rule notices and web archives",
                 layer="archive",
                 roots=("web.archive.org", "dgpa.gov.tw (行政院人事行政總處 annual calendar "
                        "archive)", "twse.com.tw and taifex.com.tw historical notices",
                        "cbc.gov.tw historical 理監事會議 releases"),
                 queries=("行事曆 公告", "颱風 停止交易 公告", "漲跌幅 放寬 公告",
                          "收盤前集合競價 上線", "盤後交易時段 開辦", "紀念日及節日實施條例"),
                 languages=("zh-Hant",), access_label="PUBLIC_ARCHIVE",
                 credibility="AUTHORITATIVE", predictive_state="UNTESTED",
                 licence="free, public",
                 notes="THE LAYER THIS PACK NEEDS MOST, because Taiwan's calendar is the least "
                       "derivable in the package: 補假 and 彈性放假 bridges are decided year by "
                       "year, TWSE's lunar-new-year closure is LONGER than the statutory "
                       "holiday, the 2025 amendment restored three holidays whose first year of "
                       "application must be confirmed, and typhoon closures are announced the "
                       "evening before. Every one of those is a primary notice sitting here."),
    source_class("tw_physical_economy", "Ports, power, water and the fabs that depend on both",
                 layer="physical_economy",
                 roots=("twport.com.tw (臺灣港務公司 container throughput)",
                        "taipower.com.tw (台灣電力公司 supply and reserve margin)",
                        "wra.gov.tw (水利署 reservoir levels)",
                        "moeaboe.gov.tw energy statistics",
                        "dgbas.gov.tw industrial production"),
                 queries=("貨櫃 吞吐量", "備轉容量率", "限電 風險", "水庫 蓄水率",
                          "工業生產指數", "半導體 用電", "跳電 影響"),
                 languages=("zh-Hant",), access_label="OPEN_DATA",
                 credibility="AUTHORITATIVE", predictive_state="UNTESTED",
                 licence="free, public",
                 notes="THE MOST UNDERUSED LAYER IN THE WHOLE PACKAGE. Advanced fabs are "
                       "power-hungry and water-hungry, Taiwan's reserve margin and reservoir "
                       "levels are published daily and free, and a genuine supply constraint on "
                       "the world's advanced logic capacity is an ENGINEERING fact that reaches "
                       "NAS100 before it reaches any financial series. tw_energy_and_power is "
                       "the domain that exists for this layer."),
    source_class("tw_source_graph", "How new Taiwanese grounds are found, and what is refused",
                 layer="source_graph",
                 roots=("github.com topic and dependency graphs for Taiwanese market-data "
                        "packages", "airitilibrary.com and NDLTD citation and reference graphs",
                        "ptt.cc board cross-reference structure",
                        "mops.twse.com.tw document cross-reference structure"),
                 queries=("台股 資料 API", "FinMind", "twstock", "期交所 資料 下載",
                          "爬蟲 證交所", "月營收 資料庫"),
                 languages=("zh-Hant", "en"), access_label="PUBLIC_WITH_TERMS",
                 credibility="UNKNOWN", predictive_state="UNTESTED",
                 licence="public web; used at human rates where terms restrict automation",
                 notes=f"THE META LAYER: it finds the next ground rather than data, and it "
                       f"matters more here than elsewhere because Taiwan's own price is absent "
                       f"and the pack's value therefore depends entirely on the breadth of its "
                       f"OBSERVABLES. Refused here: "
                       f"{'; '.join(r['ground'] for r in REFUSED_SOURCES)}. Reasons are in "
                       f"REFUSED_SOURCES and none of those grounds is named, subscribed or "
                       f"crawled anywhere in this pack."),
)


# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    dataset("tw_export_orders",
            source="經濟部統計處 外銷訂單統計",
            coverage="orders received by Taiwanese manufacturers, by product group and by "
                     "destination, with the overseas-production ratio",
            frequency="monthly",
            publication_lag_days=20.0,
            revisions="the prior month is revised with each release",
            licence="free, public",
            history_from="1993-01",
            pit_feasible=True,
            assets=("NAS100", "US500", "USDKRW", "JPN225"),
            mechanism_families=("export_cycle", "semiconductor_cycle", "global_tech_demand",
                                "macro_surprise"),
            how_to_fetch="moea.gov.tw, about the 20th of the following month at 16:00 Taipei "
                         "(08:00 UTC). ORDERS LEAD SHIPMENTS by one to three months, which is "
                         "what makes this series worth more than the customs print"),
    dataset("tw_customs_trade",
            source="財政部 進出口貿易統計",
            coverage="exports, imports and the balance, by product and by partner",
            frequency="monthly",
            publication_lag_days=7.0,
            revisions="minor",
            licence="free, public",
            history_from="1990-01",
            pit_feasible=True,
            assets=("NAS100", "USDKRW", "US500"),
            mechanism_families=("export_cycle", "semiconductor_cycle", "trade_cycle"),
            how_to_fetch="mof.gov.tw, about the 7th at 16:00 Taipei (08:00 UTC)"),
    dataset("tw_monthly_revenue",
            source="公開資訊觀測站 (MOPS) 每月營業收入",
            coverage="every listed company's monthly revenue, due by the 10th of the following "
                     "month",
            frequency="monthly",
            publication_lag_days=10.0,
            revisions="rare",
            licence="free, public",
            history_from="2000-01",
            pit_feasible=True,
            assets=("NAS100", "US500", "USDKRW"),
            mechanism_families=("semiconductor_cycle", "supply_chain", "global_tech_demand"),
            how_to_fetch="mops.twse.com.tw. A MONTHLY FUNDAMENTAL DISCLOSURE WITH NO EQUIVALENT "
                         "IN KOREA, JAPAN OR THE UNITED STATES. It is used here ONLY aggregated "
                         "to a sector observable -- a single company's revenue may inform an "
                         "index or FX hypothesis and may never be a symbol on a docket "
                         "(two-lane order, 2026-09-06)"),
    dataset("twse_institutional_flows",
            source="TWSE 三大法人買賣金額統計表",
            coverage="daily net buy and sell by foreign and mainland investors, investment "
                     "trusts and dealers",
            frequency="daily",
            publication_lag_days=0.4,
            revisions="none",
            licence="free, public",
            history_from="2004-01",
            pit_feasible=True,
            assets=("USDKRW", "NAS100", "HK50"),
            mechanism_families=("foreign_flow", "risk_appetite", "fx_conversion_lag"),
            how_to_fetch="twse.com.tw, published after the 13:30 Taipei close (05:30 UTC) -- "
                         "and note that the FX market stays open for another two and a half "
                         "hours after that print"),
    dataset("taifex_positions",
            source="TAIFEX 三大法人未平倉 and 大額交易人未沖銷部位",
            coverage="institutional open interest and large-trader concentration in TX futures "
                     "and TXO options",
            frequency="daily",
            publication_lag_days=0.4,
            revisions="none",
            licence="free, public",
            history_from="2007-01",
            pit_feasible=True,
            assets=("NAS100", "JPN225", "HK50"),
            mechanism_families=("positioning", "expiry", "crowding"),
            how_to_fetch="taifex.com.tw daily reports; the large-trader file answers a question "
                         "no COT report does, which is how FEW holders the open interest sits in"),
    dataset("twse_margin_balances",
            source="TWSE and TPEx 融資融券餘額",
            coverage="margin financing and short-sale balances, in aggregate and per security",
            frequency="daily",
            publication_lag_days=0.4,
            revisions="none",
            licence="free, public",
            history_from="2001-01",
            pit_feasible=True,
            assets=("NAS100", "USDKRW"),
            mechanism_families=("retail_leverage", "forced_liquidation"),
            how_to_fetch="twse.com.tw and tpex.org.tw; the financing ratio is CAPPED by "
                         "regulation, so the series is bounded in a way Korea's is not"),
    dataset("cbc_decisions",
            source="中央銀行 理監事聯席會議",
            coverage="the discount rate decision, the statement, the reserve requirement and any "
                     "selective credit control",
            frequency="quarterly",
            publication_lag_days=0.0,
            revisions="none",
            licence="free, public",
            history_from="2000-01",
            pit_feasible=True,
            assets=("USDKRW", "NAS100"),
            mechanism_families=("policy_surprise", "credit_control"),
            how_to_fetch="cbc.gov.tw, announced AFTER the Taipei close at about 16:00-17:00 "
                         "Taipei (08:00-09:00 UTC). READ THE RESERVE REQUIREMENT AND THE CREDIT "
                         "CONTROLS, not only the rate: the September 2024 meeting held the rate "
                         "and raised the reserve requirement, and a rate-only study records it "
                         "as a non-event"),
    dataset("cbc_minutes",
            source="中央銀行 理監事會議議事錄摘要",
            coverage="the minutes, including attributed dissent",
            frequency="quarterly",
            publication_lag_days=90.0,
            revisions="none",
            licence="free, public",
            history_from="2017-01",
            pit_feasible=True,
            assets=("USDKRW",),
            mechanism_families=("policy_surprise", "text_signal"),
            how_to_fetch="cbc.gov.tw, published about three months later ALONGSIDE THE NEXT "
                         "MEETING -- the longest minutes lag in this package, which makes them "
                         "a historical document rather than a signal"),
    dataset("cbc_fx_reserves",
            source="中央銀行 外匯存底",
            coverage="the monthly official reserve stock",
            frequency="monthly",
            publication_lag_days=5.0,
            revisions="none",
            licence="free, public",
            history_from="1990-01",
            pit_feasible=True,
            assets=("USDKRW",),
            mechanism_families=("intervention_proxy", "reserve_adequacy"),
            how_to_fetch="cbc.gov.tw, about the 5th. Valuation effects dominate the monthly "
                         "change, so this is a weak intervention proxy and is labelled as one"),
    dataset("tw_life_insurer_hedging",
            source="金管會保險局 statistics on insurers' foreign investment",
            coverage="offshore investment balances, hedged share, hedging cost commentary, and "
                     "the 外匯價格變動準備金 balance",
            frequency="monthly",
            publication_lag_days=30.0,
            revisions="occasional",
            licence="free, public",
            history_from="2012-01",
            pit_feasible=False,
            assets=("USDKRW", "USDJPY"),
            mechanism_families=("hedging_flow", "structural_fx_demand", "regulatory_modifier"),
            how_to_fetch="fsc.gov.tw and ib.gov.tw. pit_feasible is FALSE: the FSC restates "
                         "these tables IN PLACE and publishes no vintage archive, so a "
                         "point-in-time hedge ratio has to be snapshotted by the desk itself "
                         "from first publication. THE HEDGE RATIO IS ALSO POLICY-MODIFIED: the "
                         "FX valuation reserve changes how much loss must be recognised and "
                         "therefore how much must be hedged, so the series is a regulated "
                         "quantity and not a free market choice"),
    dataset("cier_pmi",
            source="中華經濟研究院 台灣採購經理人指數",
            coverage="Taiwan manufacturing and non-manufacturing PMI with sub-indices",
            frequency="monthly",
            publication_lag_days=1.0,
            revisions="seasonal factors re-estimated annually",
            licence="free, public",
            history_from="2012-07",
            pit_feasible=True,
            assets=("NAS100", "USDKRW", "US500"),
            mechanism_families=("macro_surprise", "global_tech_demand"),
            how_to_fetch="cier.edu.tw, first business day of the month at 09:00 Taipei "
                         "(01:00 UTC)"),
    dataset("tw_typhoon_closures",
            source="TWSE and TAIFEX closure notices, and local government typhoon-day "
                   "declarations",
            coverage="the dates of unscheduled weather closures",
            frequency="event",
            publication_lag_days=0.0,
            revisions="none",
            licence="free, public",
            history_from="2010-01",
            pit_feasible=True,
            assets=("NAS100", "JPN225", "HK50"),
            mechanism_families=("calendar", "liquidity_regime", "microstructure_regime"),
            how_to_fetch="twse.com.tw notices, usually the evening before. NO RULE PREDICTS "
                         "THESE, which is why they are a dataset and not a branch of the holiday "
                         "rule -- and why Taiwan is the natural control for Hong Kong's "
                         "2024-09-23 decision to stop closing for weather"),
    dataset("tw_expiry_calendar",
            source="derived from the TAIFEX rule and this pack's holiday table",
            coverage="TAIEX futures monthly expiries, 2024 to 2026, with roll collisions flagged",
            frequency="monthly",
            publication_lag_days=0.0,
            revisions="none",
            licence="derived on this desk",
            history_from="2024-01",
            pit_feasible=True,
            assets=("NAS100", "JPN225", "HK50"),
            mechanism_families=("expiry", "calendar"),
            how_to_fetch="tw_expiry_dates(); the third Wednesday rolls FORWARD off a closure and "
                         "the function reports the collision rather than hiding it"),
)


# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    actor("中央銀行 -- the Central Bank of the Republic of China (Taiwan)",
          holds="one of the largest FX reserve stocks in the world relative to the size of the "
                "economy, and a mandate that explicitly includes exchange-rate stability",
          forced_to=("smooth disorderly movements under a stated dirty-float mandate",
                     "keep exporters competitive against a Korean won it watches closely",
                     "avoid a pattern one-sided enough to attract a US Treasury designation"),
          when="in the onshore session, with the documented signature in the final minutes "
               "before the 16:00 Taipei close; quarterly at the Board meeting",
          information=("real-time onshore order flow no one else sees",
                       "the banks' positions through moral suasion"),
          constraints=("the US Treasury monitoring list, which makes persistent one-way "
                       "intervention costly",
                       "a quarterly meeting cadence that is slow relative to the shock frequency",
                       "an economy whose exporters lobby loudly against appreciation"),
          instruments=("USDTWD onshore spot, WHICH THIS DESK CANNOT TRADE",
                       "the reserve requirement", "selective credit controls on property lending",
                       "moral suasion on the banks"),
          counterparties=("Taiwanese banks", "life insurers", "foreign investors converting"),
          observables=("the 16:00 Taipei closing rate against the intraday path -- the gap is "
                       "the smoothing signature",
                       "monthly FX reserves, valuation-dominated",
                       "quarterly decisions and the three-month-late minutes"),
          impact="it suppresses realised volatility in a currency this desk cannot trade, and it "
                 "therefore displaces the volatility into the instruments that CAN be traded -- "
                 "which is why a Taiwanese shock shows up in USDKRW and NAS100 rather than in "
                 "its own price",
          persistence="the dirty float has been the framework for decades; the Treasury "
                      "monitoring constraint tightened it after 2020",
          falsifier="if the last thirty minutes of the Taipei FX session show no systematic "
                    "difference in drift or reversal from the rest of the session, after "
                    "controlling for the global dollar move, the closing-smoothing signature is "
                    "folklore -- and since USDTWD is not on this tape, that test cannot be run "
                    "here at all, which makes this actor UNMEASURED ON THIS BOX by construction",
          notes="The most important actor in the pack and the one this desk is least able to "
                "observe. That is stated plainly rather than proxied."),
    actor("壽險業 -- Taiwanese life insurers",
          holds="offshore bond portfolios of extraordinary size relative to the economy, held "
                "against long-dated TWD liabilities",
          forced_to=("hedge or not hedge a currency mismatch that dwarfs the domestic bond market",
                     "roll SHORT-DATED hedges against LONG-DATED assets, permanently",
                     "recognise FX losses unless the valuation reserve absorbs them"),
          when="hedge rolls cluster at month end; the hedge-ratio decision is reviewed as the "
               "currency moves and as the reserve is depleted",
          information=("their own hedge ladder and their own reserve balance before the monthly "
                       "disclosure"),
          constraints=("a domestic bond market far too small to match their liabilities, which "
                       "is WHY they are offshore at all",
                       "regulatory hedge and solvency rules",
                       "the FX valuation reserve, which is a policy lever on their forced flow"),
          instruments=("FX forwards and swaps, and proxy hedges in a currency basket",
                       "offshore bonds themselves"),
          counterparties=("Taiwanese and global bank swap desks", "the CBC indirectly"),
          observables=("monthly hedge ratios and offshore balances from the FSC",
                       "the FX valuation reserve balance",
                       "hedging cost commentary in the Taiwanese press"),
          impact="the largest structural FX exposure in Taiwan, and a REFLEXIVE one: when the "
                 "currency appreciates sharply their unhedged losses force more hedging, which "
                 "appreciates it further -- the May 2025 episode is the documented case",
          persistence="structural while the domestic bond market cannot absorb their liabilities",
          falsifier="if USDKRW and USDJPY show no abnormal behaviour around months in which "
                    "Taiwanese hedge ratios moved sharply, the regional spillover of this flow "
                    "is not measurable -- and the DIRECT leg cannot be tested at all, because "
                    "USDTWD is not on this tape",
          notes="The clearest case in the package of a mechanism that is enormous, "
                "well-documented, and untradable on this broker. The pack says so."),
    actor("外資 -- foreign institutional investors at the TWSE",
          holds="a large share of Taiwanese market capitalisation, concentrated in the index "
                "heavyweights",
          forced_to=("track global and emerging-market benchmarks through reviews",
                     "convert TWD proceeds back to dollars on redemption",
                     "settle equity T+2 with the FX leg following"),
          when="continuously; concentrated at index review effective dates and at global risk "
               "turns; the daily print lands at 05:30 UTC",
          information=("index-provider consultations and effective dates, published in advance"),
          constraints=("benchmark tracking error limits",
                       "foreign investor registration and custody requirements",
                       "a market dominated by a handful of names, which concentrates their flow"),
          instruments=("Taiwanese cash equities", "TAIFEX futures as the hedge",
                       "USDTWD conversion, WHICH THIS DESK CANNOT SEE"),
          counterparties=("domestic institutions and retail on the other side",
                          "custodian banks"),
          observables=("TWSE 三大法人 daily net buy, free and same-day",
                       "foreign shareholding ratios",
                       "index review calendars"),
          impact="the marginal price setter in the Taiwanese index and a driver of the "
                 "currency's conversion flow; the equity print LEADS the FX leg because "
                 "settlement is T+2",
          persistence="structural while Taiwan sits in global benchmarks",
          falsifier="if Taiwanese foreign net buying carries no information for USDKRW or NAS100 "
                    "at any lag out to five sessions, after controlling for global risk, then "
                    "the flow is not reaching any instrument this desk can trade",
          notes="Note the routing: the Taiwanese flow must be tested on KOREAN and US "
                "instruments, because nothing Taiwanese is quoted here."),
    actor("半導體與電子供應鏈 -- the semiconductor and electronics supply chain (OBSERVABLE)",
          holds="the majority of the world's advanced logic manufacturing capacity",
          forced_to=("build capacity years ahead of demand, because a fab cannot be hurried",
                     "disclose MONTHLY revenue by the 10th, which no comparable industry "
                     "anywhere else must do",
                     "import equipment and materials in dollars"),
          when="revenue disclosure by the 10th; export orders around the 20th; capex decisions "
               "quarterly",
          information=("their own order books and utilisation months before any public series"),
          constraints=("multi-year fab lead times",
                       "export controls and equipment licensing",
                       "customer concentration among a handful of global buyers"),
          instruments=("NONE ON THIS DESK. This actor is an OBSERVABLE only: the two-lane order "
                       "(2026-09-06) forbids hunting single-name equities statistically, and "
                       "Taiwan's index is dominated by one company, which makes the discipline "
                       "matter more here than anywhere else in the package. The expression is "
                       "NAS100 and US500"),
          counterparties=("global technology buyers", "equipment suppliers",
                          "Korean memory makers as complements and competitors"),
          observables=("aggregate monthly revenue for the electronics sector, by the 10th",
                       "export orders by product group, around the 20th",
                       "the electronics sub-index of the TAIEX"),
          impact="the single best public read on global technology demand, published monthly and "
                 "early -- and its executable expression is an American index, not a Taiwanese "
                 "instrument",
          persistence="the cycle is durable; its amplitude and period have both changed with the "
                      "capex wave and must be re-estimated rather than assumed",
          falsifier="if aggregate Taiwanese electronics revenue surprises carry no information "
                    "for NAS100 at any horizon out to one month, after controlling for the US "
                    "technology earnings calendar and the dollar, the transmission is absent",
          notes="NAMED AS AN ACTOR PRECISELY SO THE BOUNDARY IS EXPLICIT: the mechanism is real "
                "and enormous, and the instrument list is empty on purpose."),
    actor("出口商 -- Taiwanese exporters",
          holds="dollar receivables from the electronics and machinery export book",
          forced_to=("convert dollars to pay domestic costs",
                     "hedge forward order books within treasury policy bands",
                     "lobby against appreciation, publicly and effectively"),
          when="month end and quarter end; around the export-order and customs releases",
          information=("their own order books before the public series"),
          constraints=("board-set hedge ratios",
                       "thin forward market relative to their need",
                       "a central bank that will lean against appreciation, which reduces their "
                       "urgency to hedge and is itself a moral-hazard mechanism"),
          instruments=("onshore USDTWD spot and forwards, NOT TRADABLE HERE"),
          counterparties=("Taiwanese banks", "their global customers"),
          observables=("export orders and customs exports",
                       "the current-account surplus, persistently large",
                       "corporate FX deposit balances"),
          impact="a structural dollar supply that the central bank absorbs rather than letting "
                 "it appreciate the currency -- which is precisely how a huge current-account "
                 "surplus coexists with a currency that does not rise",
          persistence="structural while the export model holds",
          falsifier="if the Taiwanese current-account surplus shows no relation to reserve "
                    "accumulation, the absorption story is wrong and the currency is genuinely "
                    "floating -- which would change the interpretation of every edge in this pack",
          notes="Their flow is absorbed rather than priced, which is why Taiwan's edges are "
                "about the ABSORBER rather than about the flow."),
    actor("三大法人 -- the three institutional investor types at TAIFEX",
          holds="index futures and options positions disclosed daily by category",
          forced_to=("roll before the third Wednesday",
                     "hedge cash books through the settlement window",
                     "disclose open interest, which makes their crowding visible"),
          when="the third Wednesday of each month, and each Wednesday for the weeklies",
          information=("their own inventory; the aggregate is public the same evening"),
          constraints=("position limits",
                       "a settlement price derived from the last thirty minutes of the cash "
                       "session, which is wider than Korea's auction and narrower than Hong "
                       "Kong's day",
                       "daily disclosure, which makes a crowded position visible to everyone"),
          instruments=("TX futures and TXO options, NOT TRADABLE HERE"),
          counterparties=("retail day traders", "foreign investors hedging cash books"),
          observables=("三大法人未平倉 daily",
                       "大額交易人未沖銷部位 daily concentration",
                       "the futures basis into expiry"),
          impact="an expiry effect that, if it exists, should sit between Korea's and Hong "
                 "Kong's in strength -- and the only way this desk can look for it is as a spill "
                 "into JPN225, HK50 and NAS100",
          persistence="structural; the after-hours session added in 2017 redistributed some of "
                      "the pressure",
          falsifier="if the carriers show no abnormal Asian-session behaviour on Taiwanese "
                    "third Wednesdays relative to first and fourth Wednesdays, there is no "
                    "spill and the domain is empty on this box",
          notes="Daily public disclosure of institutional positioning AND of concentration is "
                "genuinely rare; Taiwan and Korea together give the region a positioning panel "
                "the CFTC provides for no Asian currency."),
    actor("散戶及當沖客 -- Taiwanese retail investors and day traders",
          holds="cash and margin-financed equity positions, with an unusually high day-trading "
                "share of turnover",
          forced_to=("close same-day positions before the 13:30 close, by definition",
                     "meet margin calls or be sold out",
                     "operate inside a regulator-set financing ratio"),
          when="intraday, concentrated into the close; margin calls execute at the open",
          information=("nothing the market does not have"),
          constraints=("a CAPPED financing ratio set by regulation, unlike Korea's "
                       "broker-determined limits",
                       "the +/-10% daily limit, widened from 7% in 2015",
                       "a day-trade tax whose rate has been cut and extended repeatedly"),
          instruments=("cash equities", "single-stock futures", "margin financing"),
          counterparties=("brokers as lenders", "institutions on the other side"),
          observables=("融資融券餘額 daily",
                       "day-trade turnover share, published",
                       "券資比 as a squeeze gauge"),
          impact="a large, fast, leveraged share of turnover that amplifies intraday moves and "
                 "concentrates them into the closing auction introduced in 2020",
          persistence="the day-trade regime depends on a tax relief that has been extended "
                      "repeatedly and could end",
          falsifier="if the 2020-03-23 introduction of the closing call auction produced no "
                    "measurable change in close-to-close versus intraday volatility, the "
                    "microstructure change did not bind and this actor's concentration story "
                    "is wrong",
          notes="Reachable here only through the carriers, which makes most of this actor's "
                "mechanics UNMEASURED on this box."),
    actor("能源及原物料進口商 -- Taiwanese energy and materials importers",
          holds="continuous dollar-denominated energy import obligations for an economy with "
                "almost no domestic energy",
          forced_to=("import energy continuously regardless of price",
                     "fund a power-hungry semiconductor industry whose demand is inelastic"),
          when="cargo payment dates through the month",
          information=("their own purchase schedule"),
          constraints=("energy security obligations",
                       "regulated domestic electricity pricing that limits pass-through",
                       "an industrial base whose power demand is growing faster than supply"),
          instruments=("USDTWD spot and forwards, NOT TRADABLE HERE", "energy swaps"),
          counterparties=("global energy suppliers", "Taiwanese banks"),
          observables=("customs import values by commodity",
                       "the terms of trade",
                       "electricity supply commentary, which is a live constraint on fab "
                       "expansion"),
          impact="a persistent dollar bid whose size scales with energy prices, and -- more "
                 "interestingly -- a POWER CONSTRAINT on semiconductor capacity that is a "
                 "genuine supply-side risk to global technology output",
          persistence="structural; the power constraint is tightening as fab demand grows",
          falsifier="if NAS100 shows no abnormal behaviour around documented Taiwanese power "
                    "disruptions, the supply-constraint channel is not priced",
          notes="The power-constraint leg is the unusual part and it is the one most likely to "
                "be mispriced, because it is an engineering fact rather than a financial one."),
    actor("政府四大基金 -- the government's four major funds",
          holds="labour insurance, labour pension, public service pension and postal savings "
                "assets, invested domestically and offshore",
          forced_to=("invest contributions on a schedule",
                     "support the domestic market when instructed, which is a documented and "
                     "openly discussed practice",
                     "convert currency for the offshore mandates"),
          when="contribution dates; discretionary domestic support at market stress",
          information=("their own mandate decisions before they are executed"),
          constraints=("public accountability for losses",
                       "allocation limits set by the supervising ministries",
                       "a domestic market too small for their size"),
          instruments=("Taiwanese equities", "offshore mandates", "FX conversion"),
          counterparties=("external managers", "the domestic market at stress points"),
          observables=("published fund statistics and allocation reports",
                       "press commentary on 國安基金 and the four funds entering the market",
                       "TWSE institutional flow, where their buying appears as investment trust "
                       "and dealer activity"),
          impact="a counter-cyclical domestic bid at stress points and a structural offshore "
                 "conversion flow; the domestic support role means Taiwanese drawdowns have a "
                 "state-backed floor that Korea's and Hong Kong's do not",
          persistence="structural; the practice is openly discussed and politically durable",
          falsifier="if Taiwanese index drawdowns show no asymmetric recovery relative to "
                    "matched regional drawdowns, the state-backed floor is not measurable and "
                    "this actor adds nothing",
          notes="A rare case where a government fund's market-support role is public policy "
                "rather than rumour."),
    actor("境外 NDF 參與者 -- the restricted offshore NDF market",
          holds="non-deliverable TWD forward positions, settled against TAIFX1",
          forced_to=("trade in a market deliberately kept thin by regulation",
                     "settle against a fixing struck in Taipei at 11:00 local time"),
          when="the offshore session; the market is small and episodic",
          information=("global risk sentiment before Taipei reopens"),
          constraints=("DOMESTIC CORPORATES HAVE BEEN BARRED SINCE 1998, which is why the market "
                       "is thin",
                       "no access to the onshore deliverable market",
                       "limited counterparty capacity"),
          instruments=("TWD NDFs, NOT TRADABLE HERE"),
          counterparties=("offshore banks", "offshore banking units of Taiwanese banks"),
          observables=("the NDF-implied rate where a public quote exists",
                       "commentary on offshore pressure in the Taiwanese press"),
          impact="small by design. The regulation that thinned this market is the reason a "
                 "Taiwan view is expressed in KOREAN won or in the technology indices instead, "
                 "and that substitution is the single most important routing fact in this pack",
          persistence="structural while the restriction stands",
          falsifier="if USDKRW shows no abnormal behaviour in windows where Taiwanese offshore "
                    "pressure was publicly reported, the substitution story is wrong and Taiwan "
                    "has no FX expression on this desk at all",
          notes="An actor defined by what it is PREVENTED from doing. The prevention is the "
                "mechanism."),
    actor("全球下游客戶 -- the global downstream customers of the supply chain",
          holds="orders placed with Taiwanese manufacturers, visible in the export-order series "
                "before they are visible anywhere else",
          forced_to=("place orders months ahead of shipment because capacity is scarce",
                     "build or cut inventory in response to their own end demand"),
          when="continuously; the order series turns before the shipment series by one to three "
               "months",
          information=("their own end demand before anyone sees the orders"),
          constraints=("fab capacity they cannot expand",
                       "long lead times that force them to commit early",
                       "export controls that restrict what can be shipped where"),
          instruments=("NAS100 and US500, which is where their own equity value sits"),
          counterparties=("Taiwanese manufacturers", "Korean memory suppliers"),
          observables=("Taiwanese export orders by destination, monthly",
                       "the overseas production ratio, which says how much of the order is even "
                       "made in Taiwan",
                       "aggregate monthly revenue"),
          impact="the Taiwanese order book is a forward-looking read on the earnings of "
                 "companies listed in the United States, published weeks before those companies "
                 "say anything -- which is the cleanest rationale in this pack for an edge whose "
                 "target is an American index",
          persistence="structural while the supply chain is concentrated in Taiwan",
          falsifier="if export orders by destination carry no information for NAS100 beyond the "
                    "US earnings calendar, the lead is already priced and the edge is absent",
          notes="This actor is why a Taiwanese pack legitimately holds American instruments."),
    actor("地緣政治風險持有者 -- holders of the Taiwan Strait risk premium",
          holds="exposure to a tail risk that is priced continuously and realised rarely",
          forced_to=("reprice on military, diplomatic and electoral events they cannot forecast",
                     "hedge a concentration risk in global semiconductor supply that has no "
                     "substitute"),
          when="around exercises, elections and diplomatic incidents; the events are dated but "
               "not scheduled",
          information=("nothing privileged; the events are public when they happen"),
          constraints=("no instrument that prices the tail directly",
                       "a risk whose realisation would make the hedge itself unsettleable"),
          instruments=("XAUUSD", "JPN225", "HK50", "USDKRW", "USDJPY"),
          counterparties=("each other"),
          observables=("abnormal returns in the carriers around dated strait events",
                       "commentary and official statements"),
          impact="episodic risk-premium repricing that reaches gold and the regional indices; n "
                 "is small by construction and no single episode can carry a study",
          persistence="structural and slow-moving; the premium has risen over the decade",
          falsifier="if abnormal returns in XAUUSD, JPN225 and HK50 around dated strait events "
                    "are indistinguishable from matched windows, the premium is not repriced by "
                    "these events and is instead a constant the market carries",
          notes="Deliberately last in the list. It is the most discussed Taiwanese risk and the "
                "least measurable, and a pack that led with it would be selling a story."),
)


# --------------------------------------------------------------------------- domains
_DEFAULT_CONTROLS: tuple[str, ...] = (
    "the same statistic on EURUSD and GBPUSD, where no Taiwanese mechanism can operate",
    "the same statistic on matched weekdays and days of the month",
    "the same statistic inside each era of POLICY_ERAS, never pooled across them",
    "THE ROUTING CONTROL, which is specific to this pack: every result here is measured on a "
    "CARRIER rather than on a Taiwanese instrument, so each one must also be tested against the "
    "carrier's own domestic drivers -- a NAS100 result that disappears once US technology "
    "earnings dates are conditioned on was never Taiwanese",
)


def _controls(*extra: str) -> tuple[str, ...]:
    """The four standing controls every Taiwanese domain runs, plus the domain's own."""
    return (*_DEFAULT_CONTROLS, *extra)


DOMAINS: tuple[dict[str, Any], ...] = (
    domain("tw_export_order_cycle", "Orders around the 20th as the world's earliest demand read",
           objects=("外銷訂單 by product group and destination",
                    "the overseas production ratio",
                    "customs exports around the 7th as the confirming series"),
           conditions=("lunar new year timing, which shifts working days between January and "
                       "February exactly as it does in China",
                       "the overseas production ratio, which says how much of the order is even "
                       "made in Taiwan",
                       "tariff deadlines, which pull shipments forward"),
           instruments=("NAS100", "US500", "USDKRW", "JPN225"),
           controls=_controls(
               "Korean 1st-20th customs exports for the same month, which read the same global "
               "cycle from a different economy: a result present in only one of the two is that "
               "country's, a result present in both is global technology demand",
               "the US technology earnings calendar alone")),
    domain("tw_semiconductor_cycle", "Monthly revenue aggregated to a sector observable",
           objects=("aggregate electronics-sector monthly revenue, due by the 10th",
                    "the electronics sub-index",
                    "capacity and utilisation commentary"),
           conditions=("the phase of the capex cycle",
                       "export-control news flow",
                       "whether the month contained a lunar new year distortion"),
           instruments=("NAS100", "US500", "USDKRW"),
           controls=_controls(
               "Korean semiconductor exports for the same month, the independent second read",
               "NAS100 conditioned on the US earnings calendar alone, to test whether the "
               "Taiwanese series adds anything the US calendar does not already carry"),
           notes="NO SINGLE NAME MAY ENTER THIS DOMAIN AS AN INSTRUMENT, and the discipline "
                 "binds harder here than anywhere else in the package because the Taiwanese "
                 "index is dominated by one company."),
    domain("tw_foreign_equity_flow", "Foreign net buying and the currency flow it leads",
           objects=("TWSE 三大法人 daily net buy",
                    "foreign shareholding ratios",
                    "index review effective dates"),
           conditions=("global risk appetite measured outside Taiwan",
                       "whether the flow is index-driven or discretionary",
                       "the two-and-a-half-hour window after the equity close in which the FX "
                       "market is still open"),
           instruments=("USDKRW", "NAS100", "HK50"),
           controls=_controls(
               "Korean foreign net buying on the same dates, where the settlement convention "
               "differs and the currency IS tradable -- the contrast identifies what is "
               "Taiwanese",
               "the flow-to-carrier relation at lags zero through five, since a settlement "
               "mechanism predicts a specific lag")),
    domain("tw_cbc_reaction", "A quarterly central bank with more than one instrument",
           objects=("quarterly decisions and statements",
                    "reserve requirement changes",
                    "selective credit controls on property lending",
                    "the three-month-late minutes"),
           conditions=("whether the meeting moved the rate, the reserve requirement, the credit "
                       "controls, or several at once",
                       "the US Treasury monitoring status at the time",
                       "the announcement lands AFTER the Taipei close"),
           instruments=("USDKRW", "NAS100"),
           controls=_controls(
               "meetings that changed nothing, which are the placebo for a quarterly calendar",
               "a rate-only reading of the same meetings, which would score the September 2024 "
               "reserve-requirement meeting as a non-event -- the difference between the two "
               "readings IS the finding")),
    domain("tw_close_smoothing", "The last thirty minutes of the Taipei FX session",
           objects=("the 16:00 Taipei closing rate against the intraday path",
                    "the gap between the closing print and the session's own range",
                    "reserve accumulation as the cumulative trace"),
           conditions=("the size and direction of the day's move",
                       "whether the US Treasury monitoring list named Taiwan",
                       "month end and quarter end"),
           instruments=("USDKRW",),
           controls=_controls(
               "the same statistic on USDKRW's own Seoul close, which has a comparable authority "
               "with a comparable mandate and a tradable instrument",
               "the same window on USDSGD, managed against a basket with a different technique"),
           notes="UNMEASURABLE ON THIS BOX BY CONSTRUCTION: USDTWD is not on this tape, so the "
                 "direct test cannot be run here at all. The domain is carried so that the gap "
                 "is recorded by name rather than quietly dropped (L1.28a)."),
    domain("tw_index_expiry", "The third Wednesday, and whether it spills into the carriers",
           objects=("TAIEX futures expiries from tw_expiry_dates()",
                    "三大法人未平倉 into expiry",
                    "大額交易人 concentration",
                    "the last-thirty-minutes settlement window"),
           conditions=("whether the nominal Wednesday rolled off a closure",
                       "open interest concentration",
                       "whether a Korean or Hong Kong expiry falls in the same week"),
           instruments=("NAS100", "JPN225", "HK50"),
           controls=_controls(
               "the FIRST and FOURTH Wednesday of the same month, the honest placebo for a "
               "third-Wednesday effect",
               "Korea's second Thursday and Hong Kong's second-last business day -- three "
               "settlement widths in three neighbouring markets, which is the actual experiment")),
    domain("tw_life_insurer_hedging", "A structural flow with a regulatory dial on it",
           objects=("monthly hedge ratios and offshore balances",
                    "the FX valuation reserve balance and its rule changes",
                    "hedging cost commentary"),
           conditions=("whether the reserve is depleted, which forces recognition and therefore "
                       "hedging",
                       "the size and speed of the currency move",
                       "month end, when rolls concentrate"),
           instruments=("USDKRW", "USDJPY"),
           controls=_controls(
               "Korean insurer hedging, a comparable structural flow in a tradable currency",
               "the same months with no reserve rule change, which separates the regulatory "
               "modifier from the flow itself"),
           notes="The DIRECT leg cannot be measured here -- USDTWD is absent and no TWD forward "
                 "curve is quoted. What can be measured is the regional spillover, and the pack "
                 "says which is which."),
    domain("tw_supply_chain_transmission", "Taiwan, Korea and Japan as one electronics chain",
           objects=("Taiwanese export orders and Korean semiconductor exports",
                    "Japanese equipment exports",
                    "the overseas production ratio"),
           conditions=("which link of the chain the shock enters at",
                       "inventory phase",
                       "export-control events that redirect the chain"),
           instruments=("NAS100", "USDKRW", "JPN225", "US500"),
           controls=_controls(
               "each country's series entered alone, to test whether the chain adds anything "
               "beyond the strongest single link",
               "a non-electronics export series from the same countries as a placebo")),
    domain("tw_microstructure_regimes", "Auctions, limits, day-trade tax and typhoons",
           objects=("the 2020-03-23 closing call auction",
                    "the 2015-06-01 widening of the price limit from 7% to 10%",
                    "the day-trade tax relief and its extensions",
                    "typhoon closures, which no rule predicts"),
           conditions=("which regime the date falls in",
                       "whether a typhoon closure fell in the window",
                       "the 2017-05-15 introduction of the TAIFEX after-hours session"),
           instruments=("NAS100", "JPN225", "HK50"),
           controls=_controls(
               "HONG KONG, which stopped closing for typhoons on 2024-09-23 while Taiwan did "
               "not -- the two together are a genuine difference-in-differences on weather "
               "closures",
               "the same statistics either side of each effective date with a structural-break "
               "test reported rather than a pooled mean")),
    domain("tw_nontradable_currency_routing", "What it costs to have no price of your own",
           objects=("the NDF restriction and its history",
                    "the correlation between USDTWD and USDKRW where a public TWD series exists",
                    "the residual that the substitution leaves behind"),
           conditions=("whether the episode was Taiwan-specific or regional",
                       "whether Korean idiosyncratic news contaminated the proxy",
                       "the level of regional risk"),
           instruments=("USDKRW", "USDJPY", "USDSGD"),
           controls=_controls(
               "Korean-specific events, which should move USDKRW WITHOUT any Taiwanese content "
               "-- the size of that contamination is the cost of the routing",
               "USDSGD as a second proxy, since two proxies disagreeing tells you the residual "
               "is large"),
           notes="THE DOMAIN THAT EXISTS BECAUSE OF AN ABSENCE. It quantifies the proxy error "
                 "every other domain in this pack inherits, which is the honest thing to do "
                 "when a country's own price is not quoted."),
    domain("tw_geopolitical", "A tail risk priced continuously and realised rarely",
           objects=("dated military exercises, diplomatic incidents and elections",
                    "abnormal returns in the carriers around them"),
           conditions=("event severity, which is a judgement and must be pre-registered",
                       "whether global risk was already elevated",
                       "election cycles"),
           instruments=("XAUUSD", "JPN225", "HK50", "USDKRW", "USDJPY"),
           controls=_controls(
               "matched windows with equivalent global risk moves and no strait event",
               "the same event list applied a year earlier as a placebo"),
           notes="n IS TINY BY CONSTRUCTION and the event list is a judgement call, so this "
                 "domain must be pre-registered before it is run or it will find whatever it "
                 "is asked to find."),
    domain("tw_retail_and_daytrade", "A capped-leverage retail base with a high day-trade share",
           objects=("融資融券餘額 daily",
                    "day-trade turnover share",
                    "券資比 as a squeeze gauge"),
           conditions=("the regulatory financing ratio in force",
                       "whether the day-trade tax relief was active",
                       "the closing auction regime after 2020-03-23"),
           instruments=("NAS100", "USDKRW"),
           controls=_controls(
               "Korea's margin balance series, where the leverage is broker-determined rather "
               "than regulator-capped -- the contrast tests whether the cap changes the "
               "liquidation dynamic",
               "the same statistic conditioned on index drawdown alone")),
    domain("tw_energy_and_power", "The power constraint on global semiconductor output",
           objects=("energy import values and the terms of trade",
                    "electricity supply commentary and documented disruptions",
                    "fab expansion announcements against power availability"),
           conditions=("summer peak demand",
                       "documented outages or restrictions",
                       "the oil and gas price level"),
           instruments=("NAS100", "XTIUSD", "USDKRW"),
           controls=_controls(
               "documented power disruptions elsewhere in the chain, which should move NAS100 "
               "similarly if the channel is about semiconductors rather than about Taiwan",
               "energy prices alone, with no Taiwanese conditioning"),
           notes="The least-explored domain in the pack and the one most likely to be mispriced, "
                 "because it is an engineering constraint rather than a financial one."),
)

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("tw_export_orders_to_nasdaq",
         source="經濟部 外銷訂單, released around the 20th at 08:00 UTC",
         mechanism="orders placed with Taiwanese manufacturers are a forward-looking read on "
                   "the revenue of companies listed in the United States, published weeks "
                   "before those companies say anything",
         targets=("NAS100", "US500"),
         sign="export-order surprise UP -> NAS100 UP",
         horizon="same session to ten sessions",
         lag="08:00 UTC publication, which is after the Taipei close and before the US open",
         control="the US technology earnings calendar alone; and Korean semiconductor exports "
                 "for the same month, which read the same global cycle from another economy",
         evidence="HYPOTHESIS",
         notes="The highest-prior edge in this pack: an early, public, forward-looking series "
               "with an exact release minute and a clearly identified target."),
    edge("tw_monthly_revenue_to_tech",
         source="aggregate electronics-sector monthly revenue, due by the 10th",
         mechanism="a monthly fundamental disclosure that exists nowhere else, aggregated to a "
                   "sector, gives a mid-quarter read on technology demand",
         targets=("NAS100", "US500"),
         sign="aggregate revenue surprise UP -> NAS100 UP",
         horizon="one to fifteen sessions",
         lag="by the 10th of the following month; the timing WITHIN the window is a company "
             "choice, so the event is a window rather than a minute",
         control="the same statistic excluding January and February, which the lunar new year "
                 "distorts exactly as it distorts the Chinese data; and the US earnings calendar",
         evidence="HYPOTHESIS",
         notes="AGGREGATED ONLY. A single company's revenue may inform this edge and may never "
               "be a symbol on a docket."),
    edge("tw_foreign_flow_to_korea",
         source="TWSE 三大法人 foreign net buy, published at 05:30 UTC",
         mechanism="foreign allocation decisions across Asian technology exporters are made "
                   "together, so the Taiwanese print carries information about the Korean flow "
                   "and therefore about the won",
         targets=("USDKRW", "HK50", "NAS100"),
         sign="Taiwanese foreign net BUY -> USDKRW DOWN, HK50 UP",
         horizon="one to five sessions",
         lag="05:30 UTC print; the Korean equivalent lands at 09:00 UTC the same day",
         control="the Korean print itself entered first -- if the Taiwanese one adds nothing "
                 "incremental, this edge retires into the KR pack; and global risk beta removed",
         evidence="HYPOTHESIS"),
    edge("tw_cbc_to_won",
         source="quarterly CBC decisions, announced after the Taipei close at 08:00-09:00 UTC",
         mechanism="a Taiwanese policy move is read as a signal about regional export "
                   "competitiveness, and the won is the tradable expression of that read",
         targets=("USDKRW", "NAS100"),
         sign="hawkish CBC surprise -> USDKRW DOWN (regional currencies firmer)",
         horizon="hours to five sessions",
         lag="08:00-09:00 UTC, after the Taipei close and during the European morning",
         control="meetings that changed nothing; and a rate-only reading versus a full reading "
                 "including the reserve requirement and credit controls",
         evidence="HYPOTHESIS",
         notes="A weak-prior edge carried honestly: the direct instrument is absent and the "
               "regional read-through is an assumption this edge exists to test."),
    edge("tw_semis_cycle_to_korea_and_nasdaq",
         source="Taiwanese export orders and aggregate electronics revenue together",
         mechanism="Taiwan and Korea are the two halves of the same global semiconductor cycle "
                   "-- logic and memory -- so a turn in one is information about the other and "
                   "about the demand behind both",
         targets=("USDKRW", "NAS100", "JPN225"),
         sign="Taiwanese semis cycle UP -> USDKRW DOWN, NAS100 UP, JPN225 UP",
         horizon="one to three months",
         lag="monthly series",
         control="each country's series entered alone: if the pair adds nothing beyond the "
                 "stronger single link, the chain story is decoration",
         evidence="HYPOTHESIS"),
    edge("tw_expiry_to_carrier_variance",
         source="TAIEX futures expiry on the third Wednesday",
         mechanism="hedge unwinds into the last-thirty-minutes settlement window spill into the "
                   "regional session through correlated index hedges",
         targets=("JPN225", "HK50", "NAS100"),
         sign="third Wednesday -> elevated Asian-session intraday range",
         horizon="intraday",
         lag="05:00-05:30 UTC settlement window",
         control="the first and fourth Wednesday of the same month; and Korea's second Thursday "
                 "and Hong Kong's second-last business day, which give three settlement widths "
                 "to compare",
         evidence="HYPOTHESIS",
         notes="This is the pack's custom miner. The claim is deliberately weak -- a SPILL, not "
               "the settlement itself -- because the contract is not tradable here."),
    edge("tw_life_insurer_hedge_to_regional_fx",
         source="monthly life-insurer hedge ratios and FX valuation reserve changes",
         mechanism="a forced increase in hedging by the largest structural FX holder in Taiwan "
                   "is a dollar sale large enough to move regional currencies with it",
         targets=("USDKRW", "USDJPY"),
         sign="hedge ratio UP -> USDKRW DOWN, USDJPY DOWN",
         horizon="days to weeks",
         lag="monthly disclosure with about a month's lag, so the flow precedes the data",
         control="the same months with no reserve rule change; and Korean insurer hedging, a "
                 "comparable flow in a tradable currency",
         evidence="HYPOTHESIS",
         notes="The May 2025 episode is the documented case and it is ONE observation. This edge "
               "will be sized accordingly or not at all."),
    edge("tw_pmi_to_tech",
         source="CIER Taiwan PMI, first business day at 01:00 UTC",
         mechanism="the earliest monthly read on Taiwanese manufacturing, published before the "
                   "Asian session is fully underway",
         targets=("NAS100", "USDKRW", "US500"),
         sign="PMI surprise UP -> NAS100 UP, USDKRW DOWN",
         horizon="same session to five sessions",
         lag="01:00 UTC on the first business day",
         control="the Chinese official PMI at the same hour on the preceding day, which shares "
                 "the global cycle and not the Taiwanese content",
         evidence="HYPOTHESIS"),
    edge("tw_strait_event_to_haven",
         source="dated Taiwan Strait military, diplomatic and electoral events",
         mechanism="a geopolitical shock to the world's concentrated semiconductor supply "
                   "reprices both a haven and the regional equity complex",
         targets=("XAUUSD", "JPN225", "HK50", "USDKRW"),
         sign="strait event -> XAUUSD UP, JPN225 DOWN, HK50 DOWN, USDKRW UP",
         horizon="hours to ten sessions",
         lag="event timestamp, frequently outside Asian hours",
         control="matched windows with equivalent global risk and no strait event; and the same "
                 "event list shifted a year earlier as a placebo",
         evidence="HYPOTHESIS",
         notes="n is tiny and the event list is a judgement call. PRE-REGISTER the list before "
               "running this or it will find whatever it is asked to find."),
    edge("tw_typhoon_closure_to_gap",
         source="unscheduled Taiwanese market closures declared for typhoons",
         mechanism="a session removed at a day's notice from the world's most concentrated "
                   "electronics market leaves the information to arrive at the reopen",
         targets=("NAS100", "JPN225", "HK50"),
         sign="typhoon closure -> elevated reopening range in the carriers and in Taiwan's own "
              "reopening session",
         horizon="the closure plus one session",
         lag="a day's notice at most",
         control="HONG KONG, which stopped closing for weather on 2024-09-23 while Taiwan did "
                 "not -- the pair is a genuine difference-in-differences",
         evidence="HYPOTHESIS"),
    edge("tw_power_constraint_to_tech",
         source="documented Taiwanese electricity disruptions and supply constraints",
         mechanism="fab output is power-constrained, so a supply disruption is a real "
                   "constraint on global semiconductor output rather than a financial event",
         targets=("NAS100", "US500", "XCUUSD"),
         sign="documented disruption -> NAS100 DOWN",
         horizon="hours to ten sessions",
         lag="event timestamp",
         control="documented power disruptions elsewhere in the chain, which should move NAS100 "
                 "similarly if the channel is about semiconductors rather than about Taiwan",
         evidence="HYPOTHESIS",
         notes="The least-explored edge in the pack and the one most likely to be mispriced, "
               "because it is an engineering fact rather than a financial one."),
    edge("tw_proxy_residual_cost",
         source="the correlation between Taiwanese-specific news and USDKRW",
         mechanism="Taiwan has no price here, so every edge routes through a proxy; the "
                   "CONTAMINATION of that proxy by Korean idiosyncratic news is a measurable "
                   "cost and this edge measures it",
         targets=("USDKRW", "USDSGD", "USDJPY"),
         sign="a NULL is the good outcome: Korean-specific events should move USDKRW WITHOUT "
              "Taiwanese content, and the size of that movement is the routing cost every other "
              "edge in this pack inherits",
         horizon="event windows",
         lag="event timestamps",
         control="USDSGD as a second proxy -- two proxies disagreeing is direct evidence that "
                 "the residual is large",
         evidence="HYPOTHESIS",
         notes="This edge exists to QUANTIFY A COST rather than to find an effect, which is the "
               "honest thing to carry when a country's own price is not quoted."),
)

#: Derived, never hand-maintained. OWN_PRICE is empty for Taiwan, so EVERY target here is a
#: transmission target -- which is the pack's central structural fact expressed as data.
TRANSMISSION_TARGETS: tuple[str, ...] = tuple(sorted(
    {t for e in TRANSMISSION_EDGES_SEED for t in e["targets"]} - set(OWN_PRICE)))


# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("tw_limit_widened", start="2015-06-01", end="2020-03-22",
        label="The daily price limit widened from 7% to 10%",
        what_changed="the TWSE limit moved from plus or minus 7% to plus or minus 10%, which "
                     "changes the truncation point of every Taiwanese return distribution",
        invalidates="a tail or volatility estimate pooled across this date is an average over "
                    "two different truncations and is not an estimate of either"),
    era("tw_pandemic_and_semis_boom", start="2020-03-19", end="2021-12-31",
        label="The pandemic cut and the semiconductor boom",
        what_changed="the discount rate was cut to 1.125% while the export cycle ran at record "
                     "levels and the currency appreciated against the central bank's preference",
        invalidates="an export-to-currency elasticity fitted here is fitted during a global "
                    "supply shock and does not generalise"),
    era("tw_closing_auction", start="2020-03-23", end=None,
        label="The five-minute closing call auction introduced",
        what_changed="the TWSE close became a call auction rather than a continuous-trading "
                     "print, which relocated a large share of daily volume into five minutes",
        invalidates="close-to-close statistics before and after this date are computed on "
                    "different objects; an intraday shape estimated across it is an average of "
                    "two microstructures"),
    era("tw_treasury_monitoring", start="2020-12-01", end="2023-06-30",
        label="The US Treasury monitoring list and its constraint on smoothing",
        what_changed="Taiwan was named in the Treasury's currency reports, which raised the "
                     "political cost of one-sided intervention and visibly changed the "
                     "smoothing signature",
        invalidates="an intervention-detection statistic calibrated outside this window will "
                    "mis-specify the reaction function inside it, and vice versa"),
    era("tw_small_step_tightening", start="2022-03-17", end="2023-03-23",
        label="The 12.5 basis point tightening cycle",
        what_changed="the CBC raised in unusually small increments and used the reserve "
                     "requirement alongside the rate",
        invalidates="a policy-surprise study that reads only the rate misses half of what these "
                    "meetings did"),
    era("tw_surprise_hike", start="2024-03-21", end="2024-09-18",
        label="The surprise March 2024 hike",
        what_changed="a 12.5bp increase the market had not priced, on inflation rather than on "
                     "the currency",
        invalidates="it is one observation and a policy-surprise estimate dominated by it is an "
                     "estimate of one meeting"),
    era("tw_credit_control_channel", start="2024-09-19", end=None,
        label="The hold-plus-reserve-requirement meeting and the credit-control channel",
        what_changed="the rate was held while the reserve requirement was raised and property "
                     "credit controls were tightened, making the rate a partial description of "
                     "policy",
        invalidates="every rate-only Taiwanese policy series from this point forward "
                    "understates what the central bank did"),
    era("tw_twd_shock", start="2025-05-01", end="2025-12-31",
        label="The May 2025 appreciation shock and the insurer hedging problem",
        what_changed="the largest two-day appreciation of the New Taiwan dollar in decades "
                     "turned life-insurer FX losses into a systemic question and made the "
                     "reflexive hedging mechanism visible",
        invalidates="an unconditional Taiwanese FX volatility estimate that includes this window "
                    "without conditioning on it is dominated by one episode"),
    era("tw_hk_weather_divergence", start="2024-09-23", end=None,
        label="Hong Kong stops closing for typhoons and Taiwan does not",
        what_changed="two neighbouring markets with the same weather adopted opposite closure "
                     "policies, which is a difference-in-differences that did not exist before",
        invalidates="nothing by itself; it CREATES an identification that earlier windows do not "
                    "have, which is the rarer and more useful kind of era boundary"),
)


# --------------------------------------------------------------------------- framework fields
MISSION = ("Mine the Taiwanese economic system to exhaustion for forced flows that reach a "
           "symbol this broker quotes -- and since NONE of them is Taiwanese, measure and report "
           "the proxy error that every one of those routes inherits, rather than pretending a "
           "Korean instrument is a Taiwanese one.")
#: There is no TWD futures contract at the CFTC AND no USDTWD on this broker. Taiwan is the one
#: country in this package with neither a positioning series for its currency nor a way to trade
#: it, and both absences are recorded rather than proxied.
COT_CURRENCY = ""
EXPORT_ECONOMY = "semiconductor_exporter"
#: Margin financing ratios are set by regulation for listed and OTC securities, which makes
#: Taiwanese retail leverage a CAPPED quantity rather than a broker-determined one.
RETAIL_LEVERAGE_REGIME = "capped"
OPEN_ERA_END = "2030-12-31"
#: Recurring solar closures as MM-DD, including the three holidays restored by the 2025
#: amendment. The lunar dates (除夕, 春節, 端午節, 中秋節), the solar term 清明節, every 補假 and
#: 彈性放假 bridge, and typhoon closures CANNOT appear here and are tabulated or datasetted.
HOLIDAY_FIXED_MD: tuple[str, ...] = ("01-01", "02-28", "04-04", "05-01", "09-28", "10-10",
                                     "10-25", "12-25")

SESSION_WINDOWS: tuple[dict[str, str], ...] = (
    {"name": "tw_cash_open", "start_utc": "01:00", "end_utc": "02:00",
     "notes": "the TWSE open at 09:00 Taipei; the CIER PMI lands at 01:00 on the first business "
              "day of the month, inside this window"},
    {"name": "tw_settlement_window", "start_utc": "05:00", "end_utc": "05:30",
     "notes": "the last thirty minutes of the cash session, from which the TAIFEX final "
              "settlement price is derived on the third Wednesday"},
    {"name": "tw_cash_close", "start_utc": "05:25", "end_utc": "05:30",
     "notes": "the five-minute closing call auction introduced on 2020-03-23; the institutional "
              "flow print follows shortly after"},
    {"name": "tw_fx_only", "start_utc": "05:30", "end_utc": "08:00",
     "notes": "THE ASYMMETRY: the interbank FX market runs to 16:00 Taipei, two and a half hours "
              "after the equity market shuts, and the documented closing-smoothing signature "
              "sits at the end of this window"},
    {"name": "tw_cbc_announcement", "start_utc": "08:00", "end_utc": "09:30",
     "notes": "quarterly Board decisions are announced after the Taipei close, during the "
              "European morning"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "tw_export_orders", "cadence": "monthly", "time_utc": "08:00",
     "source": "經濟部統計處", "notes": "about the 20th; ORDERS, which lead shipments by one to "
                                       "three months"},
    {"name": "tw_customs_trade", "cadence": "monthly", "time_utc": "08:00",
     "source": "財政部", "notes": "about the 7th"},
    {"name": "tw_monthly_revenue", "cadence": "monthly", "time_utc": "",
     "source": "公開資訊觀測站 (MOPS)", "notes": "due by the 10th, but the minute within the "
                                               "window is each company's choice, which is why "
                                               "this class carries no time_utc"},
    {"name": "tw_cier_pmi", "cadence": "monthly", "time_utc": "01:00",
     "source": "中華經濟研究院", "notes": "first business day of the month"},
    {"name": "tw_cpi", "cadence": "monthly", "time_utc": "08:00",
     "source": "主計總處", "notes": "about the 5th"},
    {"name": "tw_gdp", "cadence": "quarterly", "time_utc": "08:00",
     "source": "主計總處", "notes": "advance estimate about four weeks after quarter end"},
    {"name": "tw_fx_reserves", "cadence": "monthly", "time_utc": "08:00",
     "source": "中央銀行", "notes": "about the 5th; valuation-dominated"},
)

INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "TWSE 三大法人買賣金額統計表 (daily net buy by institutional type, twse.com.tw)",
    "TAIFEX 三大法人未平倉 (daily futures and options open interest by investor type)",
    "TAIFEX 大額交易人未沖銷部位 (daily top-five and top-ten large-trader concentration)",
    "TWSE and TPEx 融資融券餘額 (daily margin and short-sale balances, regulator-capped)",
    "金管會保險局 life-insurer offshore investment and hedge ratios (monthly)",
    "中央銀行 外匯存底 (monthly FX reserves, valuation-dominated)",
)


# --------------------------------------------------------------------------- typed row builders
def _central_bank_row(lab: Any) -> Any:
    """The CBC as `country_lab.CentralBank`, with the quarterly grid flattened."""
    dates: list[str] = []
    for year in sorted(CENTRAL_BANK["decision_dates"]):
        dates.extend(CENTRAL_BANK["decision_dates"][year])
    return lab.CentralBank(
        name="Central Bank of the Republic of China, Taiwan (中央銀行)",
        framework="managed_float",
        decision_dates=tuple(sorted(dates)),
        decision_calendar_rule=str(CENTRAL_BANK["schedule_rule"]),
        decision_time_utc="08:00",
        publication_classes=("理監事聯席會議 decision and statement (08:00-09:00 UTC)",
                             "press conference immediately after",
                             "議事錄摘要 (about three months later, with the NEXT meeting)",
                             "外匯存底 (monthly, about the 5th)"),
        policy_rate_series="tw_discount_rate",
        expected_rate_series="",
        notes=f"{CENTRAL_BANK['fx_operations']} MORE THAN ONE INSTRUMENT: "
              f"{CENTRAL_BANK['other_instruments']} 2026 IS RULE_ONLY: "
              f"{CENTRAL_BANK['decision_dates_status'][2026]}")


def _fixing_rows(lab: Any) -> tuple[Any, ...]:
    """Taiwan's two published references, in UTC.

    BOTH CARRY AN EMPTY INSTRUMENT LIST, and that is the honest answer: the asset they price is
    USDTWD, which this broker does not quote. Attaching them to USDKRW would turn a routing
    assumption into a recorded fact.
    """
    return (
        lab.Fixing(name="TAIFX1 (Taipei Forex Inc, the NDF fixing reference)", time_utc="03:00",
                   dst_rule="none", instruments=(), window_minutes=30,
                   notes=str(FIXING_CONVENTIONS["taifx1"]["note"])),
        lab.Fixing(name="the Taipei interbank closing rate", time_utc="08:00", dst_rule="none",
                   instruments=(), window_minutes=30,
                   notes=str(FIXING_CONVENTIONS["closing_rate"]["note"])),
    )


def _settlement_rows(lab: Any) -> tuple[Any, ...]:
    """Taiwan's conventions as RULES. The monthly-revenue day is unique to this pack."""
    return (
        lab.SettlementRule(name="tw_taifex_expiry", kind="week_of_month", days=(), months=(),
                           weekday=2, week_of_month=3, roll="next",
                           window_utc=("05:00", "05:30"),
                           instruments=("NAS100", "JPN225", "HK50"),
                           notes="TAIEX futures settle on the THIRD WEDNESDAY, derived from the "
                                 "index over the last thirty minutes of the cash session. A "
                                 "closed Wednesday rolls FORWARD; tw_expiry_dates() resolves it "
                                 "and flags the collision"),
        lab.SettlementRule(name="tw_monthly_revenue_day", kind="day_of_month", days=(10,),
                           months=(), weekday=-1, week_of_month=0, roll="next",
                           window_utc=("01:00", "08:00"), instruments=("NAS100", "US500"),
                           notes="every listed company must publish monthly revenue by the 10th "
                                 "of the following month -- a disclosure with no equivalent in "
                                 "Korea, Japan or the United States, read here ONLY aggregated "
                                 "to a sector"),
        lab.SettlementRule(name="tw_export_orders_day", kind="day_of_month", days=(20,),
                           months=(), weekday=-1, week_of_month=0, roll="next",
                           window_utc=("08:00", "09:00"), instruments=("NAS100", "USDKRW"),
                           notes="export ORDERS around the 20th at 16:00 Taipei: the earliest "
                                 "public read on global electronics demand anywhere"),
        lab.SettlementRule(name="tw_month_end_hedge_roll", kind="month_end", days=(), months=(),
                           weekday=-1, week_of_month=0, roll="previous",
                           window_utc=("01:00", "08:00"), instruments=("USDKRW", "USDJPY"),
                           notes=str(SETTLEMENT_CONVENTIONS["life_insurer_rolls"])),
        lab.SettlementRule(name="tw_quarter_end", kind="quarter_end", days=(), months=(),
                           weekday=-1, week_of_month=0, roll="previous",
                           window_utc=("01:00", "08:00"), instruments=("USDKRW",),
                           notes="quarter-end reporting concentrates insurer hedge decisions and "
                                 "coincides with the quarterly CBC meeting month"),
    )


def _exchange_rows(lab: Any) -> tuple[Any, ...]:
    """TWSE and TAIFEX. `index_symbols` is EMPTY for both, which is the pack's founding fact:
    this broker quotes no Taiwanese instrument at all, so the generic expiry miner has nothing to
    run and the custom miner looks for a SPILL into the carriers instead."""
    dates = tuple(r["date"] for y in (2024, 2025, 2026) for r in tw_expiry_dates(y))
    return (
        lab.Exchange(name="Taiwan Stock Exchange (TWSE) and Taipei Exchange (TPEx)",
                     index_symbols=(), expiry_rule="", expiry_dates=(),
                     open_utc="01:00", close_utc="05:30",
                     notes=f"{EXCHANGES['cash']['price_limit']}. "
                           f"{EXCHANGES['cash']['closing_auction']}. NO TAIWANESE INDEX IS "
                           f"QUOTED BY THIS BROKER; TAIEX is in ABSENT_INSTRUMENTS with the "
                           f"carriers that stand in for it."),
        lab.Exchange(name="Taiwan Futures Exchange (TAIFEX)", index_symbols=(),
                     expiry_rule="third Wednesday of the delivery month; the final settlement "
                                 "price is derived from the TAIEX over the last thirty minutes "
                                 "of the cash session on the settlement day",
                     expiry_dates=dates, open_utc="00:45", close_utc="05:45",
                     notes="the expiry grid is computable and is expanded here for 2024-2026 "
                           "with roll collisions flagged; the settlement window sits between "
                           "Korea's ten-minute auction and Hong Kong's whole-day average, which "
                           "makes the three neighbours a real cross-pack experiment"),
    )


def _release_rows(lab: Any) -> tuple[Any, ...]:
    return tuple(lab.ReleaseClass(name=r["name"], cadence=r["cadence"], time_utc=r["time_utc"],
                                  dates=(), actual_series="", expected_series="",
                                  source=str(r["source"]), notes=str(r["notes"]))
                 for r in RELEASE_CLASSES)


# --------------------------------------------------------------------------- the custom miner
def tw_carrier_expiry_spill(pack_in: Any, ctx: Any) -> dict[str, Any]:
    """The third-Wednesday TAIEX expiry, measured where Taiwan can actually be traded.

    WHY THIS NEEDS ITS OWN MINER. `country_lab.generic_derivatives_expiry` iterates an exchange's
    `index_symbols` and measures the effect on the index itself. Taiwan has none: this broker
    quotes no Taiwanese instrument, so the generic miner correctly does nothing here. The only
    question that can be asked on this box is whether the expiry SPILLS into the carriers -- and
    that is a genuinely weaker claim than measuring the contract, which is why the reading says
    so in its own text rather than letting a reader assume otherwise.

    The placebo is the FIRST and FOURTH Wednesday of the same month: same weekday, same month,
    same macro calendar, no TAIFEX settlement. An effect present on all three is a Wednesday
    effect and has nothing to do with Taiwan.
    """
    lab = _lab()
    out: dict[str, Any] = {"miner": "tw_carrier_expiry_spill", "country": CODE,
                           "readings": [], "measured": 0,
                           "own_price": OWN_PRICE,
                           "caveat": "Taiwan has NO executable instrument on this broker. Every "
                                     "reading below is a spill into a carrier and inherits that "
                                     "carrier's own drivers; the routing control in "
                                     "_DEFAULT_CONTROLS is not optional here."}
    if lab is None:
        out["outcome"] = "UNMEASURED"
        out["why"] = "libs.research.country_lab is absent on this tree"
        return out
    years = sorted({int(y) for y in HOLIDAYS_RULE["table"]})
    events = [r["date"] for y in years for r in tw_expiry_dates(y)]
    placebo: list[str] = []
    for year in years:
        for month in range(1, 13):
            placebo.append(nth_weekday(year, month, 2, 1).isoformat())
            placebo.append(nth_weekday(year, month, 2, 4).isoformat())
    if not events:
        ctx.note("expiries", "no expiry grid could be built from the tabulated years")
        out["outcome"] = "UNMEASURED"
        out["why"] = "no expiry dates"
        return out
    ev = lab.parse_days(tuple(events))
    pb = lab.parse_days(tuple(placebo))
    rolled = [r["date"] for y in years for r in tw_expiry_dates(y) if r["rolled"]]
    out["rolled_expiries"] = tuple(rolled)
    for sym in ("JPN225", "HK50", "NAS100"):
        bars = ctx.bars(sym, "H1")
        if bars is None:
            ctx.note(f"bars:{sym}", "no H1 tape on this box, so the third-Wednesday spill cannot "
                                    "be measured for this carrier")
            continue
        try:
            got = lab.event_effect(bars, ev, horizon=1, rng=ctx.rng(f"expiry:{sym}"))
            ctrl = lab.event_effect(bars, pb, horizon=1, rng=ctx.rng(f"placebo:{sym}"))
        except Exception as exc:  # pragma: no cover -- a framework signature change
            ctx.note(f"event_effect:{sym}", f"{type(exc).__name__}: {exc}")
            continue
        out["readings"].append({
            "symbol": sym, "role": "carrier",
            "third_wednesday": got, "first_and_fourth_wednesday": ctrl,
            "claim": "a Taiwanese settlement spill must be present on the THIRD Wednesday and "
                     "absent on the first and fourth of the same month; present on all three is "
                     "a Wednesday effect and nothing Taiwanese"})
        out["measured"] += int(got.get("verdict") == "MEASURED"
                               and ctrl.get("verdict") == "MEASURED")
    out["outcome"] = "OK" if out["measured"] else "UNMEASURED"
    if not out["measured"]:
        out["why"] = "no carrier produced a measurable event and placebo pair"
    return out


CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("tw_carrier_expiry_spill",
          domain_ids=("tw_index_expiry", "tw_nontradable_currency_routing"),
          kind="calendar",
          entry="countries.tw.pack:tw_carrier_expiry_spill",
          cadence_s=86400.0,
          steerable=False,
          notes="A fixed cost: the third-Wednesday grid rolls off closures and typhoon days, so "
                "it must be recomputed every pass. A miner anchored on a nominal Wednesday when "
                "the market was shut produces a confident wrong number rather than nothing."),
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
