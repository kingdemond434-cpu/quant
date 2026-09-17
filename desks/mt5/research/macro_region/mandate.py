"""THE MACRO REGION MANDATE -- the constitution of the global-macro research department.

WHAT A MANDATE IS, AND WHY IT IS DATA. A department that keeps its scope in prose keeps it
nowhere: the prose is read once, by whoever wrote it, and every later session re-derives a
narrower version of it from whatever artifact happened to be open. So the scope is a STRUCTURE --
actors with eleven fields each, domains that must each name their controls, miner specs whose
entry points must import, a dataset catalogue whose rows must be complete -- and `validate()` is
the gate that refuses an incomplete one. A mandate that cannot be validated is a wish.

THE MISSION, in one sentence, because a department with two missions has none:

    continuously maximise the breadth of economically distinct, orthogonal, implementation-ready
    candidates drawn from global macro institutions, participants, calendars, policy, flows, data
    and research, and hand every one of them to the canonical gauntlet.

Breadth is the objective, not candidate count. Two sleeves of the same mechanism are one bet with
extra leverage (PROP_FIRM_E8: four correlated mechanisms take the pass probability from 92% to
77%), so "economically distinct" and "orthogonal" are load-bearing words and the registry's
independence factors are how they are cashed.

ELEVEN FIELDS PER ACTOR, and the eleventh is the one that stops a story. `actor` is a
participant, never a strategy; `constraint` is the rule, mandate or contract that removes their
discretion; `observable` is the public series or calendar that shows the constraint binding;
`observable_kind` says what kind of record that is; `cadence` says when it binds; `direction` says
which way; `instruments` are SELECTOR TOKENS resolved against MetaTrader's own registry (never a
hand-kept symbol list); `horizon` and `session` say where in time the reaction lives; `source` is
where the desk reads it; and `confidence` is a prior, not a result. A row missing any of them is a
hunch with an institution's name on it.

EVERY DOMAIN NAMES ITS CONTROLS. The failure mode of macro research is not a missing test, it is
a test with no control: "gold rose after the Fed" is true of days on which nothing happened too.
So `controls` is a required field of every domain -- matched non-event days, matched hour and
weekday, the untreated peer leg, the era split, the permutation null -- and `validate()` refuses a
domain that declares none.

CAPITAL AUTHORITY IS FALSE, PERMANENTLY. This department mints discoveries into the canonical
registry and nothing else. It does not size, promote, write a sleeve, touch the allocator, or
reduce anything -- GROWTH_GOVERNANCE Rule 1 means a risk reduction must prove it raises robust
forward E[log W], and a research department is in no position to prove that. The field is checked
by a test so that a later session cannot flip it while adding a feature.

THE FRAMEWORK IS IMPORTED LAZILY AND ON PURPOSE. `libs/research/region_mandate.py` owns the
shared dataclasses and the shared vocabularies (OPERATORS, DISPOSITIONS, LOOP_STEPS,
REQUIREMENTS). It is being written alongside this package, so every reference to it goes through
`_framework()`, which returns None when it is absent and lets the local fallback -- identical
field names, identical lengths -- carry the region until it lands. The fallback is not a
duplicate scope: it is the shape this region needs, which the framework supersedes the day it
imports.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any

REGION = "macro"
#: Every generator this department stamps: `macro:<miner>`; every payload carries region "macro".
TAG = f"{REGION}:"

#: The eleven fields every actor row must carry. The count is pinned by a test: a twelfth field
#: added without a decision, or a tenth left behind, changes what an actor IS.
ACTOR_FIELDS: tuple[str, ...] = (
    "actor", "constraint", "observable", "observable_kind", "cadence", "direction",
    "instruments", "horizon", "session", "source", "confidence",
)

#: The fourteen transformation operators. One disposition per operator, always: a discovery that
#: reaches this department and is not asked all fourteen questions has been silently narrowed,
#: which is the defect `transformation_miners` was written to end.
OPERATORS: tuple[str, ...] = (
    "asset_transfer", "horizon", "session", "regime", "residual", "interaction", "inverse",
    "execution", "cross_asset", "macro_condition", "failure_resurrection",
    "parameter_neighborhood", "information_substitution", "frequency_ladder",
)

#: The seven dispositions a discovery may hold -- the registry's own state machine. There is no
#: eighth called "nothing happened".
DISPOSITIONS: tuple[str, ...] = (
    "UNPROCESSED", "INTERPRETED", "EXPANDED", "COMPILED", "QUEUED", "TESTED", "BLOCKED",
)

#: The twenty steps of the department's loop. Each is a verb with an artifact on the other end.
LOOP_STEPS: tuple[str, ...] = (
    "read the standing law and this mandate",
    "measure what the box can actually reach today",
    "refresh the dataset catalogue and its PIT stamps",
    "scout new sources and widen the source graph",
    "harvest the institutional calendars into dated events",
    "harvest the public series into dated observations",
    "stamp every observation with its knowable_at",
    "run the domain miners inside their time box",
    "build matched controls before any effect is read",
    "measure the effect against its control leg",
    "split every effect by era and by regime",
    "charge every effect a permutation or bootstrap null",
    "name every axis that stayed UNMEASURED and why",
    "record each finding as ONE discovery with a disposition",
    "expand each discovery through the fourteen operators",
    "resurrect failures by class rather than re-running them",
    "residualise survivors against the macro factors",
    "hand compiled cells to the canonical gauntlet",
    "pay each miner by independent survivors, never by row count",
    "write the conversion debt back and leave nothing unexplained",
)

#: The twenty-five standing requirements this region is held to.
REQUIREMENTS: tuple[str, ...] = (
    "public or licensed sources only; no scraped paywall, no vendor terms breach",
    "no crypto-exchange universe is ever hunted (2026-08-18)",
    "no single-name equity is hunted for a statistical hypothesis (2026-09-06)",
    "routing is by asset class from MetaTrader's registry, never by a symbol list",
    "an unclassified symbol is hunted by nothing; absence is not a permission",
    "every claim names an actor, a constraint, an observable and a market impact",
    "every observation carries knowable_at; a row without one is NOT_PIT_SAFE",
    "no secret is ever printed, logged or written to an artifact",
    "every effect is measured against a named control leg",
    "every effect is split by era and reported per era",
    "every effect is charged a permutation or bootstrap null",
    "a sample below the floor is reported with its n, never as a verdict",
    "UNMEASURED is a verdict and is named by axis (L1.28a)",
    "an empty result is a measurement, never a silent zero",
    "every discovery holds one of the seven dispositions",
    "every discovery is asked all fourteen operators",
    "a refusal carries a reason; silence is not a disposition",
    "candidate quantity has no intrinsic value; the same rule twice is one candidate",
    "the department is paid in independent survivors, not in rows",
    "no organ here sizes, promotes or writes a sleeve",
    "no organ here adds a cap, veto or shrink (GROWTH_GOVERNANCE Rule 1)",
    "coverage floors ratchet up only (L1.50)",
    "a gate that never ran is a claim the desk cannot cash (L1.49)",
    "exhaustion requires per-axis evidence (L1.51)",
    "unwired or idle is a defect: every miner runs on a clock and leaves an artifact (III.16)",
)

#: The boundaries no session moves. They are repeated here rather than referenced because a
#: boundary that lives only in another document is one import away from being forgotten.
BOUNDARIES: tuple[str, ...] = (
    "MT5/Fusion executable universe only; macro data is reference, never a hunted universe",
    "no crypto-exchange-native ground, vocabulary, channel or query -- ever",
    "single-name equities belong to the event lane; this department never mints one",
    "public or licensed sources only, with the licence noted on every catalogue row",
    "data/secrets/** never leaves the box and no key is ever printed",
    "point-in-time or it does not count: a revised vintage read as the original is a lookahead",
    "this department has no capital authority and no allocator surface",
    "no risk reduction, cap, veto or shrink originates here",
)

#: The era split every stability claim is made against. A macro effect that exists in one of
#: these and not the others is a regime artefact wearing an effect's clothes.
ERAS: tuple[tuple[str, str | None, str | None], ...] = (
    ("pre_2015", None, "2015-01-01"),
    ("2015_2019", "2015-01-01", "2020-01-01"),
    ("covid_2020_2021", "2020-01-01", "2022-01-01"),
    ("hiking_2022_2023", "2022-01-01", "2024-01-01"),
    ("post_2024", "2024-01-01", None),
)

#: The G10 policy estate, each with the currency leg its decisions price.
G10_BANKS: tuple[tuple[str, str, str, str], ...] = (
    ("Fed", "Federal Reserve / FOMC", "USD", "en"),
    ("ECB", "European Central Bank", "EUR", "en"),
    ("BoE", "Bank of England / MPC", "GBP", "en"),
    ("SNB", "Swiss National Bank", "CHF", "de"),
    ("RBA", "Reserve Bank of Australia", "AUD", "en"),
    ("RBNZ", "Reserve Bank of New Zealand", "NZD", "en"),
    ("BoC", "Bank of Canada", "CAD", "en"),
    ("Riksbank", "Sveriges Riksbank", "SEK", "en"),
    ("Norges", "Norges Bank", "NOK", "en"),
)

#: The sub-beats of a policy cycle. Each is a separately dated, separately surprising record --
#: collapsing them into "the meeting" throws away three quarters of the observations.
CB_SUBBEATS: tuple[str, ...] = ("decision", "statement", "minutes", "projections", "speeches")

#: The macro release families, per economy, whose surprise the release engine measures.
RELEASE_FAMILIES: tuple[str, ...] = ("cpi", "nfp", "gdp", "pmi", "retail_sales",
                                     "jobless_claims", "trade_balance", "ppi")

#: The economies whose releases are read. An economy absent here is UNMEASURED, not absent.
ECONOMIES: tuple[str, ...] = ("US", "EA", "GB", "JP", "CA", "AU", "NZ", "CH", "SE", "NO", "CN")

#: The fixings whose windows are measured, with their local clocks.
FIXINGS: tuple[tuple[str, str, str, str], ...] = (
    ("wmr_london_1600", "WM/Refinitiv 4pm London fix", "Europe/London", "16:00"),
    ("ecb_reference_1415", "ECB euro reference rates", "Europe/Berlin", "14:15"),
    ("boc_noon", "Bank of Canada noon rate (historic) / indicative", "America/Toronto", "12:00"),
)

#: The languages the native intelligence lane reads. English is a language here, not a default.
LANGUAGES: tuple[str, ...] = ("en", "de", "fr", "it", "es", "pt", "ja", "zh")


# --------------------------------------------------------------------------- the framework shim
def _framework() -> Any:
    """`libs.research.region_mandate` when it exists, else None. Imported lazily on purpose."""
    try:
        return importlib.import_module("libs.research.region_mandate")
    except ImportError:
        return None


@dataclass(frozen=True)
class Actor:
    """One participant, the rule that removes their discretion, and where it shows."""

    actor: str
    constraint: str
    observable: str
    observable_kind: str
    cadence: str
    direction: str
    instruments: tuple[str, ...]
    horizon: str
    session: str
    source: str
    confidence: float


@dataclass(frozen=True)
class Domain:
    """One question this department asks continuously, with the controls it answers it under."""

    name: str
    question: str
    actors: tuple[str, ...]
    measures: tuple[str, ...]
    controls: tuple[str, ...]
    nulls: tuple[str, ...]
    horizons: tuple[str, ...]
    sessions: tuple[str, ...]
    instruments: tuple[str, ...]
    datasets: tuple[str, ...]
    unmeasured_when: tuple[str, ...]


@dataclass(frozen=True)
class DatasetSpec:
    """One public dataset, and everything that decides whether it may be used point-in-time."""

    dataset_id: str
    institution: str
    coverage: str
    frequency: str
    publication_lag: str
    revisions: str
    licence: str
    history: str
    pit_feasible: str
    assets: tuple[str, ...]
    mechanism_families: tuple[str, ...]
    how_to_fetch: str
    language: str = "en"
    url: str = ""


@dataclass(frozen=True)
class MinerSpec:
    """One miner: what it is called, where it is entered, and which domain it answers."""

    name: str
    snake: str
    entry: str
    domain: str
    cadence: str
    budget_s: float
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    why: str


@dataclass(frozen=True)
class Mandate:
    """The region's whole constitution, as one validated object."""

    region: str
    mission: str
    actors: tuple[Actor, ...]
    domains: tuple[Domain, ...]
    miners: tuple[MinerSpec, ...]
    datasets: tuple[DatasetSpec, ...]
    loop_steps: tuple[str, ...]
    boundaries: tuple[str, ...]
    requirements: tuple[str, ...]
    operators: tuple[str, ...]
    dispositions: tuple[str, ...]
    governing_law: str
    tag: str
    capital_authority: bool = False
    eras: tuple[tuple[str, str | None, str | None], ...] = field(default_factory=lambda: ERAS)

    def domain(self, name: str) -> Domain | None:
        return next((d for d in self.domains if d.name == name), None)

    def miner(self, snake: str) -> MinerSpec | None:
        return next((m for m in self.miners if m.snake == snake), None)


def _cls(kind: str, fallback: Any) -> Any:
    """The framework's dataclass when it has one, else this region's identical fallback."""
    fw = _framework()
    got = getattr(fw, kind, None) if fw is not None else None
    return got if got is not None else fallback


def _make(kind: str, fallback: Any, **fields: Any) -> Any:
    """Build a row through the framework's dataclass, falling back on any shape disagreement.

    A field-name disagreement between the framework and this region is a real defect, but it is
    the framework's to fix: the region must still validate and still run while it lands.
    """
    cls = _cls(kind, fallback)
    try:
        return cls(**fields)
    except TypeError:
        return fallback(**fields)


def _const(name: str, fallback: tuple[str, ...], expect: int) -> tuple[str, ...]:
    """A shared vocabulary from the framework when it is the right length, else the fallback."""
    fw = _framework()
    got = getattr(fw, name, None) if fw is not None else None
    if isinstance(got, (list, tuple)) and len(got) == expect:
        return tuple(str(x) for x in got)
    return fallback


# --------------------------------------------------------------------------- the actors
def _a(actor: str, constraint: str, observable: str, observable_kind: str, cadence: str,
       direction: str, instruments: tuple[str, ...], horizon: str, session: str, source: str,
       confidence: float) -> Actor:
    return _make("Actor", Actor, actor=actor, constraint=constraint, observable=observable,
                 observable_kind=observable_kind, cadence=cadence, direction=direction,
                 instruments=instruments, horizon=horizon, session=session, source=source,
                 confidence=confidence)


def _bank_actor(code: str, long_name: str, ccy: str) -> Actor:
    return _a(
        f"{long_name} ({code})",
        "a published reaction function and an inflation/employment mandate it must be seen to "
        "follow; the decision is taken on a fixed calendar it cannot move",
        f"{code} policy rate path, statement, minutes, projections and speeches; BIS CBPOL for "
        f"the realised {ccy} policy rate",
        "policy_publication",
        "scheduled decisions plus unscheduled speeches",
        "two_sided",
        (f"fx:{ccy}", "prefix:XAU", "class:Bonds", "class:Indices"),
        "sub_1d",
        "all",
        f"{code} website, BIS CBPOL (data/axes/bis.json)",
        0.8,
    )


ACTORS: tuple[Actor, ...] = (
    *(_bank_actor(code, long, ccy) for code, long, ccy, _lang in G10_BANKS),
    _a("sovereign treasuries and debt management offices",
       "a funding requirement set by the fiscal year that must be raised on an announced "
       "calendar regardless of the level of yields",
       "auction calendars, quarterly refunding announcements, issuance sizes, bid-to-cover",
       "issuance_calendar",
       "weekly to quarterly, announced in advance",
       "sell",
       ("class:Bonds", "fx:USD", "fx:EUR", "fx:GBP"),
       "sub_1d", "ny_open",
       "US Treasury auction results, DMO/Bundesrepublik/AOFM calendars, "
       "desks/mt5/data/forced_flow_calendar.json (bond_auction)",
       0.75),
    _a("sovereign wealth funds",
       "a statutory inflow (commodity revenue, reserves transfer) and a strategic asset "
       "allocation band that forces rebalancing when the band is breached",
       "published SAA bands, quarterly holdings and transfer reports",
       "disclosure_report",
       "quarterly, with month-end concentration",
       "two_sided",
       ("class:Indices", "fx:NOK", "fx:USD", "prefix:XAU"),
       "multi_day", "london",
       "NBIM/GIC/ADIA/PIF public reporting",
       0.5),
    _a("FX reserve managers",
       "a reserve adequacy rule and a currency composition target; intervention and "
       "sterilisation are executed regardless of price",
       "IMF COFER composition, monthly reserve levels, intervention disclosures",
       "official_statistics",
       "monthly, with disclosed intervention days",
       "two_sided",
       ("fx:USD", "fx:JPY", "fx:CHF", "prefix:XAU"),
       "multi_day", "all",
       "IMF COFER, central bank reserve releases, MoF intervention records",
       0.55),
    _a("pension funds and insurers",
       "liability-driven mandates with duration and solvency limits; a funding-ratio move "
       "forces hedge rebalancing inside a stated window",
       "regulatory funding ratios, hedge ratio disclosures, month-end rebalancing flow notes",
       "regulatory_filing",
       "month-end and quarter-end",
       "two_sided",
       ("class:Bonds", "class:Indices", "fx:USD", "fx:EUR", "fx:JPY"),
       "sub_1d", "london",
       "DNB/EIOPA/PPF statistics, dealer month-end notes, "
       "desks/mt5/data/forced_flow_calendar.json (month_end)",
       0.6),
    _a("CTAs and trend followers",
       "a volatility target: realised volatility rising forces de-gearing whether or not the "
       "manager's view has changed",
       "realised volatility of the traded contract, published program volatility targets, "
       "managed futures indices",
       "derived_series",
       "daily, concentrated after volatility jumps",
       "two_sided",
       ("class:Indices", "class:Forex", "class:Energy", "prefix:XAU"),
       "multi_day", "all",
       "SG CTA index, exchange volume, desk-measured realised volatility",
       0.6),
    _a("options dealers",
       "a hedged book: a dealer short gamma must buy strength and sell weakness to stay "
       "delta-neutral, and expiry removes the hedge on a fixed date",
       "open interest by strike, expiry calendars, published gamma estimates",
       "exchange_statistics",
       "monthly and quarterly expiries, daily near large strikes",
       "volatility",
       ("class:Indices", "prefix:XAU", "class:Forex"),
       "sub_1d", "ny_open",
       "CME/ICE public open interest, "
       "desks/mt5/data/forced_flow_calendar.json (option_expiry)",
       0.6),
    _a("commodity producers, consumers and refiners",
       "a hedging programme mandated by the board and a physical delivery cycle that cannot "
       "be deferred; the barrels and bushels exist",
       "COT commercial category, inventory reports, refinery maintenance and delivery notices",
       "positioning_and_inventory",
       "weekly inventories, monthly roll, seasonal maintenance",
       "two_sided",
       ("class:Energy", "class:Soft Commodity", "prefix:XAG", "prefix:XCU"),
       "multi_day", "ny_open",
       "CFTC COT (data/axes/cot.json), EIA, USDA, LME",
       0.7),
    _a("commercial hedgers and speculators (COT categories)",
       "reportable position limits and a weekly disclosure they cannot opt out of; a crowded "
       "speculative book is forced out by margin, not by opinion",
       "CFTC Commitments of Traders: net non-commercial, net commercial, open interest",
       "regulatory_disclosure",
       "weekly, Friday for Tuesday, knowable with a 4-day lag",
       "two_sided",
       ("class:Forex", "prefix:XAU", "prefix:XAG", "class:Energy", "class:Soft Commodity"),
       "multi_day", "all",
       "CFTC COT (desks/mt5/data/axes/cot.json, knowable_lag_days=4)",
       0.75),
    _a("passive and index funds",
       "a tracking-error mandate: the index changes on an announced date and the fund must "
       "own the new weights at that close, at whatever price clears",
       "index rebalance and reconstitution calendars, announced weight changes",
       "index_calendar",
       "quarterly reconstitution, monthly rebalance",
       "two_sided",
       ("class:Indices", "fx:USD"),
       "sub_1d", "ny_open",
       "index provider calendars, "
       "desks/mt5/data/forced_flow_calendar.json (index_rebalance)",
       0.7),
    _a("corporate treasuries",
       "dividend and coupon payment dates, repatriation windows and fiscal year ends that fix "
       "when foreign cash must be converted",
       "dividend calendars, fiscal year ends, repatriation tax windows, TTM-style fixings",
       "corporate_calendar",
       "seasonal: fiscal year end, dividend season, quarter end",
       "two_sided",
       ("fx:JPY", "fx:EUR", "fx:GBP", "fx:USD"),
       "multi_day", "asia",
       "exchange dividend calendars, tax authority repatriation rules",
       0.5),
    _a("banks and dealers",
       "a month-end balance sheet that must be reported small, and fixing obligations they "
       "have contracted to meet",
       "month-end balance sheet reporting dates, fixing windows, repo and SOFR prints",
       "regulatory_and_market",
       "month-end, quarter-end, daily fixings",
       "two_sided",
       ("class:Forex", "class:Bonds", "prefix:XAU"),
       "sub_1d", "london",
       "BIS statistics, SOFR/EFFR prints, "
       "desks/mt5/data/forced_flow_calendar.json (month_end, fixing)",
       0.7),
    _a("global macro funds",
       "risk limits and investor liquidity terms; a drawdown forces position reduction on a "
       "timetable the manager does not choose",
       "HFR/BarclayHedge style indices, prime broker leverage statistics, 13F-adjacent filings",
       "industry_statistics",
       "monthly, with quarter-end redemption concentration",
       "two_sided",
       ("class:Forex", "class:Indices", "class:Bonds"),
       "multi_day", "all",
       "HFR macro index, BIS leverage statistics",
       0.45),
    _a("retail traders",
       "margin: a retail book is liquidated by the broker at a threshold the trader does not "
       "control, and the positioning is published weekly in several jurisdictions",
       "broker positioning percentages where published, CFTC non-reportable category",
       "broker_disclosure",
       "weekly, continuous where a broker publishes live",
       "two_sided",
       ("class:Forex", "prefix:XAU", "class:Indices"),
       "sub_1d", "all",
       "public broker sentiment pages, CFTC non-reportable positions",
       0.4),
    _a("governments (fiscal calendars and intervention)",
       "a fiscal calendar fixed in law (tax dates, budget, debt ceiling) and, for some, a "
       "declared exchange-rate policy they must defend",
       "budget and tax calendars, debt ceiling episodes, declared floors, bands and fixings "
       "(SNB, BoJ/MoF, RBA, MAS, PBoC)",
       "policy_declaration",
       "annual fiscal dates; intervention is episodic and disclosed after the fact",
       "two_sided",
       ("fx:CHF", "fx:JPY", "fx:AUD", "fx:SGD", "fx:USD"),
       "multi_day", "asia",
       "treasury/ministry calendars, MAS band statements, PBoC daily fixing, MoF records",
       0.55),
)


# --------------------------------------------------------------------------- the domains
def _d(name: str, question: str, actors: tuple[str, ...], measures: tuple[str, ...],
       controls: tuple[str, ...], nulls: tuple[str, ...], horizons: tuple[str, ...],
       sessions: tuple[str, ...], instruments: tuple[str, ...], datasets: tuple[str, ...],
       unmeasured_when: tuple[str, ...]) -> Domain:
    return _make("Domain", Domain, name=name, question=question, actors=actors, measures=measures,
                 controls=controls, nulls=nulls, horizons=horizons, sessions=sessions,
                 instruments=instruments, datasets=datasets, unmeasured_when=unmeasured_when)


_MATCHED = ("matched non-event days at the same hour of day",
            "the same weekday in adjacent weeks",
            "an untreated peer leg from the same asset class",
            "the era split (pre_2015 / 2015_2019 / covid / hiking / post_2024)")
_NULLS = ("permutation of the conditioning label across days",
          "stationary block bootstrap of the response series")

DOMAINS: tuple[Domain, ...] = (
    _d("central_bank_surprise",
       "for each G10 bank and each sub-beat, what does the executable universe do when the "
       "DECISION differs from what was expected, as against when it does not",
       tuple(f"{long} ({code})" for code, long, _c, _l in G10_BANKS),
       ("Surprise = Actual - Expected, with the consensus when it was captured and the prior "
        "otherwise, and the basis stamped on every row",
        "reaction at 15m/1h/4h/1d on the bank's currency leg, gold, its bond and its index",
        "separation of the reaction carried by the surprise from the reaction carried by the "
        "level of the actual, by joint regression",
        "language change between consecutive statements",
        "per-era stability of the reaction coefficient"),
       (*_MATCHED, "the same bank's non-decision days inside the same month"),
       _NULLS,
       ("15m", "1h", "4h", "1d"), ("all", "london", "ny_open"),
       ("fx:USD", "fx:EUR", "fx:GBP", "fx:CHF", "fx:AUD", "fx:NZD", "fx:CAD", "fx:SEK",
        "fx:NOK", "prefix:XAU", "class:Bonds", "class:Indices"),
       ("bis_cbpol", "fred", "forced_flow_calendar", "cb_publications"),
       ("no consensus was captured for the decision -- the basis falls back to the prior and "
        "says so",
        "the statement text was not archived, so language change is UNMEASURED",
        "fewer than the event floor of decisions inside an era")),
    _d("macro_release_surprise",
       "what does a CPI, payrolls, GDP, PMI, retail sales or claims surprise do to the "
       "executable universe, and does it depend on positioning and regime",
       ("commercial hedgers and speculators (COT categories)", "global macro funds",
        "banks and dealers"),
       ("surprise vs consensus when captured, vs prior otherwise, in units of the release's own "
        "historical surprise dispersion",
        "revision of the previous print, measured separately from the new print",
        "reaction at 15m/1h/4h/1d",
        "interaction of the surprise with the COT positioning extreme and the volatility regime"),
       (*_MATCHED, "releases of the same family with a near-zero surprise"),
       _NULLS,
       ("15m", "1h", "4h", "1d"), ("all", "london", "ny_open"),
       ("class:Forex", "prefix:XAU", "class:Indices", "class:Bonds"),
       ("fred", "alfred", "bls_bea", "eurostat", "ons", "abs", "statcan"),
       ("no actual is stored for the release -- the desk's vintages carry forecast and previous "
        "only, so the surprise is UNMEASURED and the realised first bar is used as a proxy and "
        "labelled as one",
        "the economy is outside the captured set")),
    _d("positioning",
       "does an extreme or fast-changing COT position precede a different forward distribution "
       "than a neutral one",
       ("commercial hedgers and speculators (COT categories)",
        "commodity producers, consumers and refiners", "retail traders"),
       ("net non-commercial and net commercial as a share of open interest",
        "week-on-week change and its z-score",
        "extreme by trailing percentile (<=20th, >=80th)",
        "crowding: the joint state of speculative extreme and rising open interest",
        "forward return and forward volatility by state"),
       (*_MATCHED, "the same symbol's neutral-positioning weeks",
        "the 4-day knowable lag applied to every read"),
       _NULLS,
       ("1d", "5d", "20d"), ("all",),
       ("class:Forex", "prefix:XAU", "prefix:XAG", "class:Energy", "class:Soft Commodity"),
       ("cftc_cot",),
       ("the symbol is not in the COT mapping (497 markets are unmapped)",
        "fewer than the week floor inside an era")),
    _d("rates_complexes",
       "how does a move in the 2s/5s/10s/30s complex, in real rates, and in rate differentials "
       "transmit into FX, gold, indices and energy",
       ("sovereign treasuries and debt management offices", "banks and dealers",
        "pension funds and insurers"),
       ("daily change in each nominal and real tenor",
        "slope (10y-2y), curvature (2x5y - 2y - 10y), breakeven",
        "policy-rate differential per pair from BIS CBPOL",
        "transmission beta of each instrument on each rate factor, with the other factors held",
        "sign and magnitude stability per era"),
       (*_MATCHED, "a shuffled-date rate series as a placebo regressor",
        "Benjamini-Hochberg across every instrument x factor pair tested"),
       _NULLS,
       ("1d", "5d"), ("all",),
       ("class:Forex", "prefix:XAU", "class:Indices", "class:Energy", "class:Bonds"),
       ("fred", "ecb_sdw", "boe_database", "bis_cbpol"),
       ("the FRED axis is empty on this box -- every tenor it owns is UNMEASURED by name",
        "Bund and Gilt tenors are not in the desk's captured series")),
    _d("fiscal_auction_calendars",
       "does the announced issuance calendar move the bond and the currency before and after "
       "the auction, and does quarterly refunding differ from a routine tap",
       ("sovereign treasuries and debt management offices", "banks and dealers",
        "governments (fiscal calendars and intervention)"),
       ("pre-auction concession over the 1-3 days into the auction",
        "post-auction reversal over the 1-3 days out",
        "difference between refunding weeks and routine weeks",
        "tax date and debt-ceiling episode windows"),
       (*_MATCHED, "non-auction weeks in the same quarter",
        "the same weekday in weeks with no issuance"),
       _NULLS,
       ("1d", "3d", "5d"), ("all", "ny_open"),
       ("class:Bonds", "fx:USD", "fx:EUR", "fx:GBP"),
       ("us_treasury_auctions", "forced_flow_calendar"),
       ("auction dates are a PATTERN in the desk's calendar, labelled VERIFY_SCHEDULE, and a "
        "year absent from the table produces no events rather than a silent zero",)),
    _d("intervention_states",
       "when a government or central bank has declared a floor, band, fixing or intervention "
       "stance, is the conditional distribution of the pair asymmetric",
       ("governments (fiscal calendars and intervention)", "FX reserve managers",
        "Swiss National Bank (SNB)"),
       ("declared-state windows (SNB floor and verbal, BoJ/MoF, RBA, MAS band, PBoC fixing)",
        "skew and downside truncation of the pair inside the state versus outside",
        "realised volatility inside the state",
        "distance of spot from the declared level where one is published"),
       (*_MATCHED, "the same pair outside the declared state",
        "a peer pair with no declared state over the same dates"),
       _NULLS,
       ("1d", "5d", "20d"), ("all", "asia"),
       ("fx:CHF", "fx:JPY", "fx:AUD", "fx:SGD", "fx:CNH"),
       ("cb_publications", "bis_cbpol", "mof_intervention"),
       ("CNH is not in the executable registry on this box, so the PBoC fixing lane is "
        "UNMEASURED for want of an instrument",
        "intervention days are disclosed with a lag and some are never disclosed")),
    _d("cross_asset_propagation",
       "along USD -> rates -> vol -> equities -> gold -> carry -> commodities -> credit, which "
       "edges carry information, at what lag, and under which state",
       ("banks and dealers", "global macro funds", "CTAs and trend followers"),
       ("lead-lag correlation at lags 1..3 on daily returns",
        "partial correlation with every other node's lag-1 conditioned out",
        "conditional beta by volatility and risk regime",
        "event transmission: the same shock measured on each downstream node",
        "state dependence of each edge"),
       (*_MATCHED, "Benjamini-Hochberg across every edge tested",
        "a lag-reversed placebo edge"),
       _NULLS,
       ("1d", "5d"), ("all",),
       ("class:Forex", "prefix:XAU", "class:Indices", "class:Energy", "class:Bonds"),
       ("fred", "ecb_sdw", "desk_universe_bars"),
       ("credit is UNMEASURED without the HY OAS series; the node is named and left empty",)),
    _d("fixing_flows",
       "is there a measurable, repeatable move into and out of the WMR 16:00 London, the ECB "
       "14:15 CET reference and the BoC noon windows, and does month-end amplify it",
       ("passive and index funds", "banks and dealers", "corporate treasuries"),
       ("return over the fix window and the two windows either side",
        "month-end versus non-month-end amplification",
        "reversal in the hour after the window",
        "per-era stability"),
       (*_MATCHED, "the same clock hour on non-fixing-relevant days",
        "a placebo window one hour earlier"),
       _NULLS,
       ("15m", "1h"), ("london", "ny_open"),
       ("class:Forex", "prefix:XAU", "class:Indices"),
       ("forced_flow_calendar", "desk_universe_bars", "ecb_sdw"),
       ("the desk's finest chart for the symbol is H1, so a 30-minute fix window is measured at "
        "bar resolution and the coarseness is stamped on the row",)),
    _d("commodity_fundamentals",
       "do inventory surprises, roll cycles and the published fundamental calendars move the "
       "executable energy, metal and soft contracts",
       ("commodity producers, consumers and refiners",
        "commercial hedgers and speculators (COT categories)"),
       ("inventory surprise versus expectation where captured, versus the seasonal norm "
        "otherwise",
        "roll-cycle windows and their return and volatility",
        "OPEC and USDA publication days",
        "interaction with the COT commercial position"),
       (*_MATCHED, "non-report Wednesdays in the same season",
        "the seasonal norm for the same week of year"),
       _NULLS,
       ("1h", "4h", "1d"), ("ny_open",),
       ("class:Energy", "class:Soft Commodity", "prefix:XAG", "prefix:XCU"),
       ("eia", "usda", "opec_momr", "lme", "forced_flow_calendar"),
       ("no expectation series is captured for EIA crude stocks, so the surprise is measured "
        "against the seasonal norm and labelled as such",)),
    _d("risk_regimes",
       "which regime is the world in -- by vol-of-vol, by a credit proxy, by term structure -- "
       "and does any macro effect survive being asked per regime",
       ("CTAs and trend followers", "global macro funds", "options dealers"),
       ("realised volatility and the volatility of volatility",
        "credit proxy state where a spread series exists",
        "term-structure state (steep, flat, inverted)",
        "regime transition dates and the distribution inside each regime"),
       (*_MATCHED, "the unconditional distribution over the same span",
        "regime labels built only from information knowable before the bar"),
       _NULLS,
       ("1d", "5d", "20d"), ("all",),
       ("class:Indices", "class:Forex", "prefix:XAU", "class:Bonds"),
       ("fred", "desk_universe_bars"),
       ("without VIXCLS and BAMLH0A0HYM2 the vol-of-vol and credit states are derived from the "
        "desk's own bars and the substitution is stamped on the row",)),
    _d("calendar_mismatches",
       "when one venue in the executable universe is shut and another is open, what happens to "
       "liquidity, gaps and cross-venue relationships",
       ("banks and dealers", "passive and index funds"),
       ("holiday map across the venues the universe touches",
        "return and range on mismatch days versus matched normal days",
        "gap at the reopening of the shut venue",
        "cross-venue lead-lag on mismatch days"),
       (*_MATCHED, "the same weekday with both venues open",
        "the week before and after the holiday"),
       _NULLS,
       ("1d", "3d"), ("all", "asia", "london", "ny_open"),
       ("class:Indices", "class:Forex", "class:Bonds"),
       ("forced_flow_calendar", "desk_universe_bars"),
       ("the desk's holiday map covers US, UK and Japan; other venues are UNMEASURED by name",)),
    _d("native_language_intelligence",
       "what are the macro institutions saying in their own languages, in terms the desk can "
       "search for, before a translation appears",
       ("Federal Reserve / FOMC (Fed)", "European Central Bank (ECB)",
        "Swiss National Bank (SNB)", "governments (fiscal calendars and intervention)"),
       ("terminology dictionaries per language for policy, rates, intervention, positioning, "
        "fixings and auctions",
        "native queries per domain and language",
        "claims extracted verbatim with their knowable_at",
        "source-graph expansion edges from each institution's own publication index"),
       ("the claim is stored verbatim with its language and its publication stamp",
        "a translation is a derived field, never the record",
        "a claim is a lead until it is measured against the tape"),
       ("the claim is tested by the same nulls as any other hypothesis once compiled",),
       ("multi_day",), ("all",),
       ("class:Forex", "prefix:XAU", "class:Indices", "class:Bonds"),
       ("cb_publications",),
       ("this box has no outbound crawl budget in a unit test; the scouts register sources and "
        "queries and mark the fetch itself UNMEASURED",)),
    _d("dataset_catalogue",
       "which public macro datasets exist, what each covers, how late it publishes, whether it "
       "revises, and whether it can be used point-in-time",
       ("sovereign treasuries and debt management offices", "FX reserve managers",
        "commercial hedgers and speculators (COT categories)"),
       ("one DatasetSpec per dataset with coverage, frequency, publication lag, revision "
        "behaviour, licence, history, PIT feasibility, assets, mechanism families and how to "
        "fetch it",
        "the PIT stamp of every row the desk reads",
        "the gap list: datasets named but not yet reachable from this box"),
       ("a dataset is PIT-feasible only when a vintage or a publication timestamp exists",
        "a current-vintage series used as history is NOT_PIT_SAFE and is stamped so"),
       ("none -- this domain is a catalogue, and its claim is completeness, not significance",),
       ("multi_day",), ("all",),
       ("class:Forex", "prefix:XAU", "class:Indices", "class:Bonds", "class:Energy"),
       ("fred", "alfred", "ecb_sdw", "boe_database", "ons", "eurostat", "bls_bea", "abs",
        "statcan", "rba_statistics", "rbnz_statistics", "boc_statistics", "snb_statistics",
        "cftc_cot", "eia", "usda", "opec_momr", "us_treasury_auctions", "lbma",
        "cme_ice_volumes", "bis_cbpol"),
       ("a row whose licence cannot be established is carried as UNKNOWN_LICENCE and is not "
        "fetched",)),
    _d("research_and_code_provenance",
       "what has the academic and open-source world already measured about these mechanisms, "
       "and which of it is reproducible from public data",
       ("global macro funds", "banks and dealers"),
       ("papers and working papers naming a macro mechanism and an instrument",
        "public repositories implementing a named macro mechanism",
        "the claim's own reported sample, and whether the desk can reach that sample",
        "duplication against what the desk has already tested"),
       ("a published result is a hypothesis, never a privileged prior (anti-timid)",
        "the desk re-measures on its own data before anything is promoted"),
       ("the re-measurement is charged the same nulls as any other cell",),
       ("multi_day",), ("all",),
       ("class:Forex", "prefix:XAU", "class:Indices", "class:Bonds"),
       ("bis_statistics", "cb_publications"),
       ("no fetch budget in this pass: sources and queries are registered and the retrieval is "
        "named UNMEASURED",)),
    _d("conversion_and_transformation",
       "what did this department's own failures, residuals and untried operators leave on the "
       "table, and is every discovery asked all fourteen questions",
       ("global macro funds",),
       ("failure classes of every judged macro cell, routed by the graveyard's own table",
        "residual of macro survivors against the USD, rates, gold and equity factors",
        "one disposition per operator for every parent, with a reason when nothing is produced",
        "conversion debt: possible minus generated minus blocked"),
       ("a resurrection is a NEW cell with its own trial, never a re-read of the old one",
        "no_edge and redundant lower the prior instead of spawning",
        "the residual is measured against the same era split"),
       ("the resurrected cell is charged the full gauntlet, not a lighter one",),
       ("1d", "5d"), ("all",),
       ("class:Forex", "prefix:XAU", "class:Indices"),
       ("alpha_registry",),
       ("with no judged macro cells in the registry the failure lane is UNMEASURED and says so",
        "an operator with no implementation registered is BLOCKED by name, never omitted")),
)


# --------------------------------------------------------------------------- the miners
def _m(name: str, snake: str, module: str, domain: str, cadence: str, budget_s: float,
       inputs: tuple[str, ...], outputs: tuple[str, ...], why: str) -> MinerSpec:
    return _make("MinerSpec", MinerSpec, name=name, snake=snake,
                 entry=f"desks.mt5.research.macro_region.{module}:mine_{snake}", domain=domain,
                 cadence=cadence, budget_s=budget_s, inputs=inputs, outputs=outputs, why=why)


MINER_SPECS: tuple[MinerSpec, ...] = (
    _m("MacroCentralBankMiner", "central_bank", "miners", "central_bank_surprise",
       "hourly", 90.0,
       ("events(central_bank) with actual/expected/prior per bank sub-beat",
        "bars(symbol, H1) for the bank's currency leg, gold, its bond and its index",
        "series(bis:<CCY>) for the realised policy path"),
       ("one discovery per bank x sub-beat x instrument that clears the floor",
        "the surprise-vs-actual separation on every row", "per-era coefficients"),
       "a policy decision is the one macro event whose actor, constraint and clock are all "
       "public years in advance"),
    _m("MacroReleaseMiner", "release", "miners", "macro_release_surprise", "hourly", 90.0,
       ("events(macro_release) per economy and family", "bars(symbol, H1)",
        "series(cot:<symbol>) for the positioning conditioner"),
       ("one discovery per family x economy x instrument", "revision measured separately",
        "the positioning and regime interaction"),
       "the release is the scheduled shock the whole estate is positioned into"),
    _m("MacroPositioningMiner", "positioning", "miners", "positioning", "hourly", 60.0,
       ("series(cot:<symbol>) with the 4-day knowable lag", "bars(symbol, D1 or H1)"),
       ("extreme, change and crowding states with forward distributions",
        "one discovery per symbol x state that clears the floor"),
       "a crowded book is forced out by margin, which is a mechanism and not a pattern"),
    _m("MacroRatesMiner", "rates", "miners", "rates_complexes", "hourly", 90.0,
       ("series(fred:DGS2|DGS5|DGS10|DGS30|DFII10|T10YIE)", "series(bis:<pair>)",
        "bars(symbol, H1)"),
       ("transmission beta per instrument x factor with BH across the family",
        "per-era sign stability"),
       "rates are the macro estate's transmission line into everything else"),
    _m("MacroCurveMiner", "curve", "miners", "rates_complexes", "hourly", 60.0,
       ("series(fred:DGS2|DGS5|DGS10)", "bars(symbol, H1)"),
       ("slope, curvature and real-rate states with forward distributions per state",),
       "the shape of the curve is a different state variable from its level"),
    _m("MacroFiscalAuctionMiner", "fiscal_auction", "miners", "fiscal_auction_calendars",
       "hourly", 60.0,
       ("events(bond_auction)", "bars(symbol, H1)"),
       ("pre-auction concession and post-auction reversal against matched non-auction days",),
       "issuance is supply on an announced date and cannot be postponed"),
    _m("MacroInterventionMiner", "intervention", "miners", "intervention_states",
       "daily", 60.0,
       ("events(intervention) or declared-state windows", "bars(symbol, H1)"),
       ("conditional skew and truncation inside the declared state versus outside",),
       "a declared floor or band is a promise to transact at a price, which is the strongest "
       "constraint a market has"),
    _m("MacroPropagationMiner", "propagation", "miners", "cross_asset_propagation",
       "hourly", 120.0,
       ("bars(symbol, H1) across the eight nodes", "series(fred:*) for the rate and vol nodes"),
       ("the edge list with lag, partial correlation, regime beta and a BH verdict",),
       "the propagation chain is how one shock becomes eight different trades"),
    _m("MacroFixingMiner", "fixing", "miners", "fixing_flows", "hourly", 60.0,
       ("bars(symbol, H1)", "events(fixing) where the calendar supplies them"),
       ("window return, month-end amplification and reversal, against a placebo window",),
       "a fund benchmarked to a fix must transact at the fix or carry tracking error"),
    _m("MacroCommodityFundamentalsMiner", "commodity_fundamentals", "miners",
       "commodity_fundamentals", "daily", 60.0,
       ("events(inventory) and events(usda)", "bars(symbol, H1)"),
       ("inventory surprise reaction against matched non-report days",),
       "the barrels exist and somebody must store them"),
    _m("MacroRiskRegimeMiner", "risk_regime", "miners", "risk_regimes", "hourly", 60.0,
       ("bars(symbol, H1)", "series(fred:VIXCLS|BAMLH0A0HYM2) when present"),
       ("regime labels knowable before the bar and the distribution inside each",),
       "an effect that lives in one regime is a regime bet, and should be sold as one"),
    _m("MacroCalendarMismatchMiner", "calendar_mismatch", "miners", "calendar_mismatches",
       "daily", 45.0,
       ("events(holiday_liquidity)", "bars(symbol, H1)"),
       ("mismatch-day return, range and reopening gap against matched both-open days",),
       "a shut venue is a constraint on everyone who needed it open"),
    _m("MacroDataScout", "data_scout", "intelligence", "dataset_catalogue", "daily", 45.0,
       ("the catalogue", "the registry's sources table"),
       ("registered sources with language and licence", "the reachability gap list"),
       "a dataset nobody can reach produces a hypothesis nobody can test (L1.49)"),
    _m("MacroAcademicScout", "academic_scout", "intelligence", "research_and_code_provenance",
       "daily", 45.0,
       ("the institutional source roots", "the terminology dictionaries"),
       ("registered academic sources and the queries that reach them",),
       "a published result is a hypothesis; the desk re-measures it"),
    _m("MacroNativeWebScout", "native_web_scout", "intelligence", "native_language_intelligence",
       "daily", 45.0,
       ("the terminology dictionaries", "the deep-forest region index"),
       ("registered native sources with language stamped", "deep-forest and frontier steering"),
       "the institution says it first in its own language"),
    _m("MacroCodeScout", "code_scout", "intelligence", "research_and_code_provenance",
       "weekly", 45.0,
       ("the institutional and repository roots",),
       ("registered code sources and expansion edges",),
       "somebody has already implemented the mechanism, and their assumptions are readable"),
    _m("MacroFailureMiner", "failure", "miners", "conversion_and_transformation",
       "hourly", 60.0,
       ("the registry's judged macro candidates and their rejection reasons",),
       ("a failure class per judged cell and a routed descendant per repairable class",),
       "every failure generates questions; no_edge and redundant lower the prior instead"),
    _m("MacroResidualMiner", "residual", "miners", "conversion_and_transformation",
       "hourly", 60.0,
       ("bars(symbol, H1)", "series(fred:*) for the factor panel"),
       ("residual structure by session and era with a permutation null",),
       "actual minus model is the research target"),
    _m("MacroTransferMiner", "transfer", "miners", "conversion_and_transformation",
       "hourly", 90.0,
       ("the registry's macro discoveries as parents", "transformation_miners"),
       ("one disposition per operator per parent -- fourteen, always",),
       "whichever dimension is reasoned about first crowds out the rest unless all fourteen "
       "are asked independently"),
)


SECTION_47 = """SECTION 47 -- THE GOVERNING LAW OF THE MACRO REGION

47.1  SCOPE. This department hunts the global macro estate: institutions, participants,
      calendars, policy, flows, public data and public research. It hunts them for MECHANISMS
      that reach a Fusion-executable instrument, and for nothing else.

47.2  THE UNIVERSE IS NOT WIDENED HERE. Macro data is reference data. FRED, ECB SDW, BIS, CFTC,
      EIA, USDA and every other source named in the catalogue informs an MT5 instrument and is
      never itself a hunted universe. No crypto-exchange ground is hunted, in any language,
      through any query, ever (2026-08-18).

47.3  THE TWO LANES HOLD. Routing is by asset class from MetaTrader's own registry. A
      single-name equity is never minted as a statistical hypothesis by this department; an
      unclassified symbol is hunted by nothing until somebody classifies it.

47.4  SURPRISE IS NOT ACTUAL. Every reaction measured here separates the part carried by the
      SURPRISE from the part carried by the LEVEL of the release, and stamps which basis the
      expectation came from -- the captured consensus, or the prior print. A row that cannot
      make the separation says so and is not read as if it had.

47.5  NO EFFECT WITHOUT A CONTROL. Every domain declares its control leg and every measurement
      uses one. An unconditional mean after an event is not a finding; it is the sample mean of
      the market plus a date filter.

47.6  ERAS AND NULLS. Every effect is split across pre_2015 / 2015_2019 / covid_2020_2021 /
      hiking_2022_2023 / post_2024 and charged a permutation or bootstrap null. An effect that
      survives only one era is reported as a regime bet with that era named.

47.7  POINT IN TIME OR IT DOES NOT COUNT. Every observation carries knowable_at. A current
      vintage read as history is a lookahead, and `pit_stamp` marks it NOT_PIT_SAFE rather than
      letting it flatter a backtest.

47.8  UNMEASURED IS A VERDICT. Every miner names, by axis, what it could not measure and why.
      An absent input is never reported as a clean zero (L1.28a, WS-005).

47.9  ONE DISPOSITION PER OPERATOR. Every discovery is asked all fourteen operators. A silent
      omission is the defect; a named refusal is a disposition.

47.10 NO CAPITAL AUTHORITY. This department writes discoveries and reports. It does not size,
      promote, allocate, or reduce. It adds no cap, veto, shrink or conditional exception: under
      GROWTH_GOVERNANCE Rule 1 a risk reduction must prove it raises robust forward E[log W],
      and a research organ is not the place that proof is made.

47.11 SOURCES ARE PUBLIC OR LICENSED, the licence is recorded on the catalogue row, and no key,
      token or credential is ever printed, logged or written into an artifact.

47.12 THE DEPARTMENT IS PAID IN INDEPENDENT SURVIVORS. Rows are not an output. Generator yield
      is measured by the registry and a miner that produces volume without independent survivors
      is a cost, not a contribution.
"""

MISSION = (
    "continuously maximise the breadth of economically distinct, orthogonal, "
    "implementation-ready candidates drawn from global macro institutions, participants, "
    "calendars, policy, flows, data and research, and hand every one of them to the canonical "
    "gauntlet"
)


def _catalogue() -> tuple[Any, ...]:
    """The dataset catalogue, from the intelligence module, lazily and tolerantly."""
    mod = None
    # PACKAGE-RELATIVE FIRST, and that order is load-bearing. The sibling region packages carry
    # modules with the SAME basenames (japan/intelligence.py), so a bare `import intelligence`
    # resolves to whichever package a test happened to put on sys.path first -- a silent
    # cross-region import that would hand this mandate another region's catalogue.
    for name in (f"{__package__}.intelligence", "intelligence"):
        try:
            mod = importlib.import_module(name)
            break
        except ImportError:
            continue
    return tuple(getattr(mod, "CATALOGUE", ()) or ()) if mod is not None else ()


def build_mandate() -> Mandate:
    """The region's constitution, assembled once. Validated by `validate()`, never by belief."""
    cls = _cls("Mandate", Mandate)
    fields: dict[str, Any] = {
        "region": REGION, "mission": MISSION, "actors": ACTORS, "domains": DOMAINS,
        "miners": MINER_SPECS, "datasets": _catalogue(),
        "loop_steps": _const("LOOP_STEPS", LOOP_STEPS, 20),
        "boundaries": BOUNDARIES,
        "requirements": _const("REQUIREMENTS", REQUIREMENTS, 25),
        "operators": _const("OPERATORS", OPERATORS, 14),
        "dispositions": _const("DISPOSITIONS", DISPOSITIONS, 7),
        "governing_law": SECTION_47, "tag": TAG, "capital_authority": False, "eras": ERAS,
    }
    try:
        return cls(**fields)
    except TypeError:
        return Mandate(**fields)


def _check_actor(a: Any, problems: list[str]) -> None:
    for f in ACTOR_FIELDS:
        if not hasattr(a, f):
            problems.append(f"actor {getattr(a, 'actor', a)!r} has no field {f!r}")
            continue
        value = getattr(a, f)
        if f == "confidence":
            if not isinstance(value, (int, float)) or not 0.0 < float(value) <= 1.0:
                problems.append(f"actor {a.actor!r} confidence {value!r} is not in (0, 1]")
        elif f == "instruments":
            if not value:
                problems.append(f"actor {a.actor!r} names no instrument selector")
        elif not str(value or "").strip():
            problems.append(f"actor {a.actor!r} has an empty {f!r}")


def validate(mandate: Mandate | None = None) -> list[str]:
    """Every way this mandate can be incomplete, named. An empty list is the only pass."""
    m = mandate if mandate is not None else MANDATE
    problems: list[str] = []
    if m.region != REGION:
        problems.append(f"region is {m.region!r}, not {REGION!r}")
    if m.tag != TAG:
        problems.append(f"tag is {m.tag!r}, not {TAG!r}")
    if m.capital_authority:
        problems.append("capital_authority is True: this department may never size or promote")
    if not m.mission.strip():
        problems.append("mission is empty")
    for label, got, want in (("loop_steps", len(m.loop_steps), 20),
                             ("requirements", len(m.requirements), 25),
                             ("operators", len(m.operators), 14),
                             ("dispositions", len(m.dispositions), 7)):
        if got != want:
            problems.append(f"{label} is {got}, not {want}")
    if not m.boundaries:
        problems.append("boundaries is empty")
    if "47.10" not in m.governing_law:
        problems.append("governing law does not carry the no-capital-authority clause")

    seen_actors: set[str] = set()
    for a in m.actors:
        _check_actor(a, problems)
        name = str(getattr(a, "actor", ""))
        if name in seen_actors:
            problems.append(f"actor {name!r} is declared twice")
        seen_actors.add(name)

    names = {d.name for d in m.domains}
    for d in m.domains:
        if not d.controls:
            problems.append(f"domain {d.name!r} declares no controls")
        if not d.measures:
            problems.append(f"domain {d.name!r} declares no measures")
        if not d.question.strip():
            problems.append(f"domain {d.name!r} asks no question")
        if not d.instruments:
            problems.append(f"domain {d.name!r} names no instruments")
        if not d.unmeasured_when:
            problems.append(f"domain {d.name!r} never says when it is UNMEASURED")
        problems.extend(f"domain {d.name!r} names unknown actor {who!r}"
                        for who in d.actors if who not in seen_actors)
    for spec in m.miners:
        if spec.domain not in names:
            problems.append(f"miner {spec.name!r} names unknown domain {spec.domain!r}")
        if not spec.entry.startswith("desks.mt5.research.macro_region."):
            problems.append(f"miner {spec.name!r} entry {spec.entry!r} is outside the package")
        if f":mine_{spec.snake}" not in spec.entry:
            problems.append(f"miner {spec.name!r} entry does not point at mine_{spec.snake}")
        if spec.budget_s <= 0:
            problems.append(f"miner {spec.name!r} has no time box")
        if not spec.inputs or not spec.outputs:
            problems.append(f"miner {spec.name!r} declares no inputs or no outputs")
    covered = {spec.domain for spec in m.miners}
    problems.extend(f"domain {name!r} has no miner" for name in sorted(names - covered))
    known = {str(getattr(row, "dataset_id", "")) for row in m.datasets}
    if known:
        for d in m.domains:
            problems.extend(f"domain {d.name!r} names unknown dataset {ds!r}"
                            for ds in d.datasets if ds not in known)
    for row in m.datasets:
        for f in ("dataset_id", "institution", "coverage", "frequency", "publication_lag",
                  "revisions", "licence", "history", "pit_feasible", "how_to_fetch"):
            if not str(getattr(row, f, "") or "").strip():
                problems.append(f"dataset {getattr(row, 'dataset_id', row)!r} has empty {f!r}")
        if not getattr(row, "assets", ()):
            problems.append(f"dataset {getattr(row, 'dataset_id', row)!r} names no assets")
        if not getattr(row, "mechanism_families", ()):
            problems.append(f"dataset {getattr(row, 'dataset_id', row)!r} names no mechanisms")
    return problems


MANDATE: Mandate = build_mandate()


def summary() -> dict[str, Any]:
    """What this region is, in the numbers a session can check against the artifacts."""
    return {
        "region": MANDATE.region, "tag": MANDATE.tag, "mission": MANDATE.mission,
        "n_actors": len(MANDATE.actors), "n_domains": len(MANDATE.domains),
        "n_miners": len(MANDATE.miners), "n_datasets": len(MANDATE.datasets),
        "n_loop_steps": len(MANDATE.loop_steps), "n_requirements": len(MANDATE.requirements),
        "n_operators": len(MANDATE.operators), "n_dispositions": len(MANDATE.dispositions),
        "capital_authority": MANDATE.capital_authority,
        "domains": [d.name for d in MANDATE.domains],
        "miners": [m.snake for m in MANDATE.miners],
        "eras": [e[0] for e in MANDATE.eras],
        "framework": "libs.research.region_mandate" if _framework() is not None else "FALLBACK",
        "problems": validate(),
    }
