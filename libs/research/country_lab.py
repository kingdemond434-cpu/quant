"""THE COUNTRY LAB -- the generic miner set every country runs, from its own mandate as DATA.

THE PRINCIPAL'S ORDER (2026-09-17): GLOBAL RESEARCH OS -> REGIONAL COMMANDS -> COUNTRY LABS ->
LOCAL MECHANISM DEPARTMENTS -> CELL COMPILER -> ONE GAUNTLET. Every country gets the same DEPTH
as Japan and the same PRIORITY. Countries are not disconnected copies of one another: the
universal frame Country x Actor x Constraint x Institution x Calendar x Information x Flow x
Asset x Horizon x Regime is shared, and each country DISCOVERS its own axes inside it -- when a
country exposes something the ontology has no word for, the ontology grows (that half lives in
`desks/mt5/research/transmission_engine.py`, which owns the axis-extension write).

WHAT THIS MODULE IS, AND WHAT IT DELIBERATELY IS NOT. It is the GENERIC HALF: fifteen miners that
need to know nothing about any particular country because everything country-specific reaches
them as DATA on a `CountryPack` -- the central bank and its decision dates, the fixing and
settlement conventions, the holiday table, the exchange and its expiry rule, the fiscal year end,
the positioning source, the native languages and the native terminology, the datasets, the actors
and domains, and the transmission channels the country already declares. A country pack is
therefore DATA PLUS OPTIONAL CUSTOM MINERS, and a new country costs a pack, not a fork of this
file. It is NOT a place where any country's name may ever appear: a `grep` for a country here
returning a hit is the defect.

WHY THE INPUTS ARRIVE THROUGH THE CONTEXT. `LabCtx` carries a `bars_loader` and a `series_loader`
rather than reading the desk's parquet estate itself, for three reasons that each cost something
once. (1) This module is `libs/`, checked under mypy strict, and the bar estate is pandas; the
loaders keep the import surface numpy-only and the measurement code array-shaped. (2) A test can
plant a tape with a KNOWN effect in it and assert the miner recovered exactly that, which is the
only way to know a miner measures rather than reports. (3) The trading box has 8 GB and holds the
live terminal: one loader with one cache is the difference between fifteen miners opening the
same parquet fifteen times and opening it once. `default_bars_loader` supplies the real thing,
importing pandas LAZILY so the module still imports where pandas does not.

UNMEASURED IS A VERDICT, BY NAME (L1.28a). Every miner here reports what it could not measure and
WHY -- the dataset that is not on this box, the calendar the pack does not declare, the symbol
with no bars, the currency absent from `cot.json`. None of those is a zero, none of them is a
clean pass, and a miner that found nothing to measure says which input was missing rather than
returning an empty result that reads like a negative finding.

TWO OUTPUTS, ALWAYS. A country lab produces DOMESTIC candidates (what its own actors are forced
to do, in its own instruments) and TRANSMISSION seeds (the channel by which that forcing reaches
somebody else's instrument). The second is not a by-product: a country whose only executable
instrument is a thin exotic is still worth mining if what happens there moves an index that is
liquid, and the transmission engine is what turns that seed into a measured edge.

    from libs.research import country_lab as CL
    problems = CL.validate_pack(pack, CL.universe())
    report   = CL.run_lab(pack, CL.LabCtx(code=pack.code, conn=conn), budget_s=180)
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import math
import re
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from dataclasses import fields as dataclass_fields
from dataclasses import replace as dataclass_replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from libs.moat import registry as R

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
#: Module-level so a test can point them somewhere else.
UNIVERSE_JSON: Path = DESK / "data" / "universe" / "universe.json"
BARS_DIR: Path = DESK / "data" / "universe"
COT_JSON: Path = DESK / "data" / "axes" / "cot.json"

# --------------------------------------------------------------------------- the vocabularies
#: The nine regional commands. A country belongs to exactly one; the command is what the global
#: OS groups by and what every discovery this lab writes carries in its payload.
REGION_COMMANDS: tuple[str, ...] = ("asia", "oceania", "russia_cis", "europe", "uk",
                                    "north_america", "latam", "mea", "africa")

#: Central-bank frameworks. The similarity table in the transmission engine reads this field: a
#: mechanism that lives on a BAND does not transfer to a free float, however alike the two
#: economies look, and `UNMEASURED` is a declaration that the pack has not said.
CB_FRAMEWORKS: tuple[str, ...] = ("inflation_targeter", "dual_mandate", "band", "peg",
                                  "crawling_peg", "ycc", "managed_float", "monetary_aggregate",
                                  "UNMEASURED")

#: What the country SELLS. The single most transferable institution there is: two commodity
#: exporters share a terms-of-trade mechanism whatever their politics.
EXPORT_TYPES: tuple[str, ...] = ("commodity_exporter", "energy_exporter", "metals_exporter",
                                 "agricultural_exporter", "manufacturing_exporter",
                                 "semiconductor_exporter", "services_exporter", "net_importer",
                                 "UNMEASURED")

#: Retail leverage regimes -- a real institution, not a footnote: a capped regime changes who is
#: on the other side of a stop cascade and therefore whether a microstructure mechanism exists.
LEVERAGE_REGIMES: tuple[str, ...] = ("restricted", "capped", "open", "UNMEASURED")

#: Settlement/fixing convention kinds the generic calendar miner can turn into windows.
SETTLEMENT_KINDS: tuple[str, ...] = ("day_of_month", "month_end", "quarter_end",
                                     "fiscal_year_end", "fiscal_quarter_end", "weekday",
                                     "week_of_month")

#: Asset-class spellings that may never be hunted for a statistical hypothesis (two-lane mandate,
#: 2026-09-06). Single names are traded on disclosures, in the event lane, by another organ.
EQUITY_CLASSES: frozenset[str] = frozenset({
    "equities", "equity", "equities us", "shares", "share", "stock", "stocks", "us shares"})

#: The instruments every country's shock is asked about in addition to its own, so a domestic
#: mechanism is measured against the global tape rather than only against itself. Filtered by the
#: broker universe at run time: a symbol this box cannot execute is never in a reaction set.
GLOBAL_REACTION_SET: tuple[str, ...] = ("US500", "NAS100", "GER40", "XAUUSD", "XAGUSD", "XTIUSD",
                                        "EURUSD", "USDJPY", "AUDUSD", "UST10Y")

#: The eight measurable outcomes of a generic miner. `UNMEASURED` is one of them.
OK, SKIPPED, UNMEASURED, FAILED = "ok", "skipped", "UNMEASURED", "failed"

#: Which region-framework miner kind each generic miner is, so `mandate_of` can hand the region
#: department a mandate whose miners route to the right loop step.
MINER_KIND: dict[str, str] = {
    "central_bank_surprise": "calendar", "release_surprise": "calendar",
    "calendar_settlement": "calendar", "holiday_liquidity": "calendar",
    "derivatives_expiry": "calendar", "session_microstructure": "mechanism",
    "positioning": "mechanism", "carry_funding": "mechanism", "corporate_flow": "mechanism",
    "institutional_flow": "mechanism", "equity_mechanics": "mechanism",
    "failure": "failure", "residual": "residual", "transfer": "transfer", "scouts": "scout",
}
#: The registry's `information` axis value each miner's discoveries carry.
MINER_INFORMATION: dict[str, str] = {
    "central_bank_surprise": "event", "release_surprise": "event",
    "calendar_settlement": "event", "holiday_liquidity": "event", "derivatives_expiry": "event",
    "session_microstructure": "price_only", "positioning": "positioning",
    "carry_funding": "carry", "corporate_flow": "macro", "institutional_flow": "macro",
    "equity_mechanics": "cross_asset", "failure": "price_only", "residual": "price_only",
    "transfer": "cross_asset", "scouts": "macro",
}

#: Measurement constants. Stated once so a reader and a test read the same numbers.
MIN_EVENTS = 6                  # below this an event study is POORLY_MEASURED, never a verdict
MIN_EVENT_DAYS = 2              # a null that resamples DATES needs at least two dates to resample
MIN_BARS = 200                  # below this a tape cannot carry a matched-control comparison
N_PERM = 200                    # permutation draws; the null randomises DATES, never returns
MAX_BARS = 200_000              # the box holds the live terminal: a miner never loads more
P_MAX = 0.05
#: Per-miner floors of the pool, and the protected cold share (section 27/28 of the region
#: framework: exploration and exploitation, permanently, and cold ground is protected AS A CLASS).
MINER_FLOOR = 0.04
COLD_SHARE = 0.10
MINER_FLOOR_S = 1.0

RULE = ("a country lab produces DOMESTIC and TRANSMISSION candidates from its mandate as data; "
        "an input the pack does not declare is UNMEASURED by name, never an empty finding")


# --------------------------------------------------------------------------- the pack's objects
@dataclass(frozen=True)
class CentralBank:
    """The country's rate-setting institution, enough of it to mine a surprise.

    `decision_dates` are what the miner actually uses; `decision_calendar_rule` is the prose that
    says how they are derived so a later pass can extend them. Both may be given: dates win, the
    rule is the provenance. `expected`/`actual`/`prior` name SERIES the context can load -- when
    the expectation is not on this box the surprise is measured against the PRIOR and the result
    says which of the two it was, because a surprise against a prior is a different quantity.
    """

    name: str = ""
    framework: str = "UNMEASURED"
    decision_dates: tuple[str, ...] = ()
    decision_calendar_rule: str = ""
    decision_time_utc: str = ""
    publication_classes: tuple[str, ...] = ()
    policy_rate_series: str = ""
    expected_rate_series: str = ""
    notes: str = ""


@dataclass(frozen=True)
class Fixing:
    """One published benchmark rate and the minutes it is struck in."""

    name: str = ""
    time_utc: str = ""
    dst_rule: str = "none"
    instruments: tuple[str, ...] = ()
    window_minutes: int = 60
    notes: str = ""


@dataclass(frozen=True)
class SettlementRule:
    """One settlement convention as a RULE, not a list of dates -- gotobi-like day-of-month
    conventions, month/quarter/fiscal ends, weekday conventions. `roll` says what happens when
    the convention day is closed: the preceding or the following open day, or nothing."""

    name: str = ""
    kind: str = "day_of_month"
    days: tuple[int, ...] = ()
    months: tuple[int, ...] = ()
    weekday: int = -1
    week_of_month: int = 0
    roll: str = "previous"
    window_utc: tuple[str, str] = ("", "")
    instruments: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class Exchange:
    """The country's exchange, its index symbols on THIS broker, and its expiry rule."""

    name: str = ""
    index_symbols: tuple[str, ...] = ()
    expiry_rule: str = ""
    expiry_dates: tuple[str, ...] = ()
    open_utc: str = ""
    close_utc: str = ""
    notes: str = ""


@dataclass(frozen=True)
class ReleaseClass:
    """One class of scheduled national statistic (CPI, trade balance, employment, PMI)."""

    name: str = ""
    cadence: str = "monthly"
    time_utc: str = ""
    dates: tuple[str, ...] = ()
    actual_series: str = ""
    expected_series: str = ""
    source: str = ""
    notes: str = ""


@dataclass(frozen=True)
class SessionWindow:
    """A named window of the country's own trading day, in UTC, on the tape the desk holds."""

    name: str = ""
    start_utc: str = ""
    end_utc: str = ""
    notes: str = ""


@dataclass(frozen=True)
class HolidayRule:
    """The country's closed days -- an explicit table, recurring month-day rules, or both. The
    weekly closure is declared rather than assumed: not every market rests on Saturday."""

    dates: tuple[str, ...] = ()
    fixed_md: tuple[str, ...] = ()
    weekly_closed: tuple[int, ...] = (5, 6)
    notes: str = ""


@dataclass(frozen=True)
class Era:
    """A policy era. Every measurement here is reported per era as well as pooled: an effect that
    exists only under a regime that ended is a historical fact, not a live edge."""

    name: str = ""
    start: str = ""
    end: str = ""
    notes: str = ""


@dataclass(frozen=True)
class TransmissionSeed:
    """A DECLARED channel out of this country: who is forced, by what, into which flow, landing
    on which foreign asset. A seed is a hypothesis about structure, never evidence -- the
    transmission engine measures it, and an unmeasurable leg is named."""

    to_country: str = "global"
    asset: str = ""
    actor: str = ""
    constraint: str = ""
    flow: str = ""
    source_series: str = ""
    source_symbol: str = ""
    lag_days: float = 1.0
    era: str = ""
    notes: str = ""


@dataclass(frozen=True)
class ActorRow:
    """Mirrors `region_mandate.Actor` field for field so `mandate_of` is a copy and this module
    needs no import of the region framework to be usable or testable."""

    name: str = ""
    holds: str = ""
    forced_to: tuple[str, ...] = ()
    when: str = ""
    information: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    instruments: tuple[str, ...] = ()
    counterparties: tuple[str, ...] = ()
    observables: tuple[str, ...] = ()
    impact: str = ""
    persistence: str = ""
    falsifier: str = ""
    notes: str = ""


@dataclass(frozen=True)
class DomainRow:
    """Mirrors `region_mandate.Domain`. `controls` is never optional: a domain that cannot name
    its negative control cannot tell an effect from its own selection."""

    id: str = ""
    title: str = ""
    objects: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ()
    instruments: tuple[str, ...] = ()
    controls: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class DatasetRow:
    """Mirrors `region_mandate.DatasetSpec`. `pit_feasible` is the field it exists for."""

    name: str = ""
    source: str = ""
    coverage: str = ""
    frequency: str = ""
    publication_lag_days: float = 0.0
    revisions: str = ""
    licence: str = ""
    history_from: str = ""
    pit_feasible: bool = False
    assets: tuple[str, ...] = ()
    mechanism_families: tuple[str, ...] = ()
    how_to_fetch: str = ""


#: Rows a pack may declare as PLAIN MAPPINGS, BARE STRINGS or under their own field names.
#: Sixteen country departments were written against this contract in parallel, each with its
#: own small adapter that emits dicts precisely so the department depends on no shared helper
#: module. So the framework meets them where they are: a row is COERCED once, at construction,
#: and every consumer downstream sees the same typed object.
#:
#: NOTHING IS LOST SILENTLY. A key the row does not have is folded into `notes` when the row
#: has one (a pack's `control` and `falsifier` are the most valuable fields it wrote), else it
#: is recorded DROPPED; a row that cannot be built at all is recorded FAILED and
#: `validate_pack` then refuses the pack -- a pack claiming a settlement convention the
#: framework could not construct would otherwise be mined as if it had none.
_ROW_CLASSES: tuple[tuple[str, type], ...] = ()      # bound below, after the classes exist


#: HOW A PACK'S OWN SPELLING REACHES THE FRAMEWORK'S FIELD. Sixteen country departments were
#: written in parallel against this contract and each one named its rows slightly differently --
#: `target` for the asset, `mechanism` for the flow, `id` or `label` for the name. The data is
#: the deliverable and the container is not, so the aliases are here rather than in sixteen packs.
_ROW_ALIASES: dict[str, dict[str, str]] = {
    "TransmissionSeed": {"target": "asset", "symbol": "asset", "instrument": "asset",
                         "to": "to_country", "country": "to_country", "dest": "to_country",
                         "destination": "to_country", "mechanism": "flow",
                         "source": "source_series", "series": "source_series",
                         "lag": "lag_days", "note": "notes"},
    "Era": {"id": "name", "label": "name", "era": "name", "start_date": "start",
            "end_date": "end", "from": "start", "to": "end", "note": "notes"},
    "SettlementRule": {"id": "name", "label": "name", "type": "kind", "day": "days",
                       "window": "window_utc", "note": "notes"},
    "Fixing": {"id": "name", "label": "name", "time": "time_utc", "utc": "time_utc",
               "dst": "dst_rule", "note": "notes"},
    "Exchange": {"id": "name", "label": "name", "indices": "index_symbols",
                 "index": "index_symbols", "expiry": "expiry_rule", "note": "notes"},
    "ReleaseClass": {"id": "name", "label": "name", "time": "time_utc", "note": "notes"},
    "SessionWindow": {"id": "name", "label": "name", "start": "start_utc", "end": "end_utc",
                      "note": "notes"},
    "CentralBank": {"id": "name", "label": "name", "bank": "name", "regime": "framework",
                    "policy_framework": "framework", "dates": "decision_dates",
                    "rule": "decision_calendar_rule", "note": "notes"},
    "HolidayRule": {"table": "dates", "holidays": "dates", "recurring": "fixed_md",
                    "weekend": "weekly_closed", "note": "notes"},
    "ActorRow": {"id": "name", "label": "name", "actor": "name", "note": "notes"},
    "DomainRow": {"domain": "id", "name": "title", "label": "title", "note": "notes"},
    "DatasetRow": {"id": "name", "label": "name", "url": "how_to_fetch", "note": "notes"},
    "SourceRow": {"name": "label", "source_id": "id", "kind": "layer", "class": "layer",
                  "root": "roots", "url": "roots", "urls": "roots", "language": "languages",
                  "lang": "languages", "terms": "query_terms", "absent": "absent_reason",
                  "note": "notes"},
}
#: A row given as a BARE STRING lands on this field. `("month_end", "quarter_end")` is a perfectly
#: readable settlement declaration and refusing it would cost the framework five packs' calendars.
_ROW_FROM_STRING: dict[str, str] = {
    "TransmissionSeed": "asset", "SettlementRule": "kind", "Fixing": "name", "Exchange": "name",
    "ReleaseClass": "name", "SessionWindow": "name", "Era": "name", "ActorRow": "name",
    "DomainRow": "id", "DatasetRow": "name", "SourceRow": "id",
}
#: The nine commands are the framework's; a pack's own finer grouping maps into one of them and
#: the remap is RECORDED, never silent -- a country filed under a command nobody reads is a
#: country nobody funds.
REGION_COMMAND_ALIASES: dict[str, str] = {
    "east_asia": "asia", "northeast_asia": "asia", "north_asia": "asia", "greater_china": "asia",
    "southeast_asia": "asia", "sea": "asia", "south_asia": "asia", "asia_pacific": "asia",
    "apac": "asia", "eu": "europe", "eurozone": "europe", "euro_area": "europe",
    "nordics": "europe", "scandinavia": "europe", "east_eu": "europe",
    "eastern_europe": "europe", "central_europe": "europe", "emea": "europe",
    "middle_east": "mea", "mena": "mea", "gulf": "mea", "gcc": "mea",
    "sub_saharan_africa": "africa", "saharan_africa": "africa",
    "anz": "oceania", "australasia": "oceania", "pacific": "oceania",
    "cis": "russia_cis", "eurasia": "russia_cis", "ru": "russia_cis",
    "south_america": "latam", "central_america": "latam", "latin_america": "latam",
    "namerica": "north_america", "nafta": "north_america", "usa": "north_america",
    "united_kingdom": "uk", "britain": "uk", "gb": "uk",
}


def canonical_command(value: Any) -> str:
    """One of the nine REGION_COMMANDS, or the token itself when nothing maps it."""
    tok = _tok(value)
    if tok in REGION_COMMANDS:
        return tok
    return REGION_COMMAND_ALIASES.get(tok, tok)


def _coerce_row(cls: type, value: Any, where: str, notes: list[str]) -> Any:
    names = {f.name for f in dataclass_fields(cls)}
    alias = _ROW_ALIASES.get(cls.__name__, {})
    if isinstance(value, cls):
        return value
    if isinstance(value, str):
        field_name = _ROW_FROM_STRING.get(cls.__name__, "")
        if field_name in names:
            return cls(**{field_name: value})
        notes.append(f"FAILED {where}: a bare string cannot become a {cls.__name__}")
        return None
    if not isinstance(value, Mapping):
        notes.append(f"FAILED {where}: expected a {cls.__name__}, a mapping or a string, got "
                     f"{type(value).__name__}")
        return None
    kw: dict[str, Any] = {}
    spare: list[str] = []
    for k, v in value.items():
        key = alias.get(str(k), str(k))
        if key in names and key not in kw:
            kw[key] = tuple(v) if isinstance(v, list) else v
        elif "notes" in names:
            # NEVER DROPPED. A pack's `control`, `falsifier`, `sign` and `condition` are the most
            # valuable fields it wrote; folding them into `notes` keeps them readable by a human
            # and by the deepening worker instead of deleting the negative control on import.
            spare.append(f"{k}={v}")
        else:
            notes.append(f"DROPPED {where}.{k}: {cls.__name__} has no such field and no notes")
    if spare and "notes" in names:
        kw["notes"] = " | ".join([str(kw.get("notes") or ""), *spare]).strip(" |")
    for key, val in list(kw.items()):
        if key in _DATE_FIELDS:
            kw[key] = _flatten_dates(val)
        elif key in _TIME_FIELDS and isinstance(val, Mapping):
            # A DST-SPLIT FIXING TIME. `{"winter": "15:00Z", "summer": "14:00Z"}` is the honest
            # way to write a benchmark struck at a local hour, and the WINTER leg is the anchor
            # this desk has always used (the gold_asia window's measured +2 is the winter
            # anchor, CLAUDE.md). The other leg is kept in `notes`, never thrown away.
            winter = str(val.get("winter") or next(iter(val.values()), ""))
            kw[key] = winter.replace("Z", "").strip()[:5]
            if "notes" in names:
                kw["notes"] = " | ".join(x for x in [str(kw.get("notes") or ""),
                                                     f"{key} by season: {dict(val)}"] if x)
    try:
        row = cls(**kw)
    except (TypeError, ValueError) as exc:
        notes.append(f"FAILED {where}: {cls.__name__}({type(exc).__name__}: {exc})")
        return None
    if "name" in names and not str(getattr(row, "name", "") or "").strip():
        row = dataclass_replace(row, name=_tok(where))
        notes.append(f"DROPPED {where}: the row carried no name; it is filed as {_tok(where)!r}")
    return row


#: Fields whose value is a COLLECTION OF DATES however the pack chose to nest it -- a flat list,
#: a {year: [dates]} table, or a {date: label} table. All three are readable declarations and all
#: three appear in the shipped packs.
_DATE_FIELDS: frozenset[str] = frozenset({"decision_dates", "dates", "expiry_dates", "fixed_md"})
_TIME_FIELDS: frozenset[str] = frozenset({"time_utc", "start_utc", "end_utc", "open_utc",
                                          "close_utc", "decision_time_utc"})


def _flatten_dates(value: Any) -> tuple[str, ...]:
    """Every date in a nested declaration, in order, with no label mistaken for a date.

    A mapping whose KEYS all parse as dates is a {date: label} table and its keys are the answer;
    any other mapping (a {year: [dates]} table) is walked through its VALUES. Getting that
    backwards silently turns a holiday table into a list of holiday NAMES, which then matches no
    bar on any tape and reads as "the country has no closures".
    """
    out: list[str] = []

    def walk(v: Any) -> None:
        if v is None:
            return
        if isinstance(v, str):
            out.append(v)
            return
        if isinstance(v, Mapping):
            keys = list(v)
            if keys and all(parse_day(k) is not None for k in keys):
                out.extend(str(k) for k in keys)
            else:
                for sub in v.values():
                    walk(sub)
            return
        if isinstance(v, (list, tuple, set)):
            for sub in v:
                walk(sub)
            return
        out.append(str(v))

    walk(value)
    return tuple(out)


def _str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        return tuple(str(k) for k in value)
    return tuple(str(v) for v in value)


@dataclass(frozen=True)
class CountryPack:
    """ONE COUNTRY'S WHOLE STANDING ORDER AS DATA.

    Everything a generic miner needs to mine this country and nothing that names it in code. A
    field left at its default is a DECLARATION THAT THE COUNTRY HAS NOT SAID, and every miner
    that needs it reports UNMEASURED naming the field -- which is how a half-written pack shows
    up as a measurement rather than as a quiet absence.
    """

    code: str
    name: str
    region_command: str
    currency: str
    executable_instruments: tuple[str, ...] = ()
    central_bank: CentralBank = CentralBank(name="")
    fixing_conventions: tuple[Fixing, ...] = ()
    settlement_conventions: tuple[SettlementRule, ...] = ()
    exchanges: tuple[Exchange, ...] = ()
    release_classes: tuple[ReleaseClass, ...] = ()
    session_windows: tuple[SessionWindow, ...] = ()
    holidays_rule: HolidayRule = HolidayRule()
    fiscal_year_end: str = ""
    policy_eras: tuple[Era, ...] = ()
    positioning_sources: tuple[str, ...] = ()
    cot_currency: str = ""
    export_economy: str = "UNMEASURED"
    retail_leverage_regime: str = "UNMEASURED"
    native_languages: tuple[str, ...] = ()
    terminology: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    source_classes: tuple[str, ...] = ()
    sources: tuple[Any, ...] = ()
    absent_layers: Mapping[str, str] = field(default_factory=dict)
    institutional_flow_sources: tuple[str, ...] = ()
    series: Mapping[str, str] = field(default_factory=dict)
    datasets: tuple[DatasetRow, ...] = ()
    actors: tuple[ActorRow, ...] = ()
    domains: tuple[DomainRow, ...] = ()
    miner_domains: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    custom_miners: tuple[str, ...] = ()
    transmission_edges_seed: tuple[TransmissionSeed, ...] = ()
    mission: str = ""
    notes: str = ""
    coercion_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Accept a pack written as PLAIN DATA and hand every consumer a typed one."""
        notes: list[str] = list(self.coercion_notes)
        put = object.__setattr__
        if _tok(self.code) != str(self.code):
            notes.append(f"DROPPED code: {self.code!r} is filed under the canonical token "
                         f"{_tok(self.code)!r}; every row this lab writes is tagged with it")
            put(self, "code", _tok(self.code))
        command = canonical_command(self.region_command)
        if command != str(self.region_command):
            notes.append(f"DROPPED region_command: {self.region_command!r} is this pack's own "
                         f"grouping; the framework files it under {command!r}")
        put(self, "region_command", command)
        for name in ("executable_instruments", "positioning_sources", "native_languages",
                     "source_classes", "institutional_flow_sources", "custom_miners"):
            put(self, name, _str_tuple(getattr(self, name)))
        cb = _coerce_row(CentralBank, self.central_bank, "central_bank", notes)
        put(self, "central_bank", cb if cb is not None else CentralBank(name=""))
        hol = _coerce_row(HolidayRule, self.holidays_rule, "holidays_rule", notes)
        put(self, "holidays_rule", hol if hol is not None else HolidayRule())
        for name, cls in _ROW_CLASSES:
            rows = []
            for i, item in enumerate(getattr(self, name) or ()):
                got = _coerce_row(cls, item, f"{name}[{i}]", notes)
                if got is not None:
                    rows.append(got)
            put(self, name, tuple(rows))
        put(self, "terminology", {str(k): _str_tuple(v)
                                  for k, v in dict(self.terminology or {}).items()})
        put(self, "miner_domains", {str(k): _str_tuple(v)
                                    for k, v in dict(self.miner_domains or {}).items()})
        put(self, "series", {str(k): str(v) for k, v in dict(self.series or {}).items()})
        put(self, "absent_layers", {_tok(k): str(v)
                                    for k, v in dict(self.absent_layers or {}).items()})
        rows = []
        for i, item in enumerate(self.sources or ()):
            got = _coerce_row(SourceRow, item, f"sources[{i}]", notes)
            if got is not None:
                rows.append(got)
        put(self, "sources", tuple(rows))
        for row in rows:
            if row.layer and row.layer not in SOURCE_LAYERS:
                notes.append(f"DROPPED sources[{row.id}].layer: {row.layer!r} is not one of the "
                             f"ten SOURCE_LAYERS; the source reads as UNTAGGED")
        put(self, "coercion_notes", tuple(notes))


_ROW_CLASSES = (("fixing_conventions", Fixing), ("settlement_conventions", SettlementRule),
                ("exchanges", Exchange), ("release_classes", ReleaseClass),
                ("session_windows", SessionWindow), ("policy_eras", Era),
                ("transmission_edges_seed", TransmissionSeed), ("datasets", DatasetRow),
                ("actors", ActorRow), ("domains", DomainRow))


# ------------------------------------------------------------------- the ten source layers
#: THE PRINCIPAL'S PER-COUNTRY DEPTH RULE (2026-09-17). A country is not "covered" because five
#: obvious sources were added to it. Coverage is TWO conditions at once, and both are measured:
#:
#:   (1) EVERY LAYER THAT EXISTS FOR THAT COUNTRY IS MAPPED -- the pack names at least one
#:       verified source in the layer, or names the layer ABSENT WITH A REASON. A layer nobody
#:       has looked at is UNMAPPED, which is a third state and never a quiet zero.
#:   (2) AUTOMATIC DISCOVERY IS STILL ADDING SOURCES -- a non-zero rate of new rows for that
#:       country in the registry's `sources` table over the trailing window. A country whose
#:       every layer is mapped and whose discovery has stopped is STALLED, not covered: it means
#:       the scouts ran out of ideas, not that the ground ran out of sources.
#:
#: The ten layers are the vocabulary every country pack tags its sources with. They are ordered
#: from the most official to the most derived, and the last two are the ones a desk that only
#: reads press releases never reaches: PHYSICAL_ECONOMY (ports, power, freight, satellite,
#: tenders) and SOURCE_GRAPH (what the other nine cite, follow and argue with).
SOURCE_LAYERS: tuple[str, ...] = (
    "official",            # the state: central bank, statistics office, customs, treasury
    "institutional",       # exchanges, clearers, banks, funds, industry associations, SOEs
    "academic",            # universities, working papers, theses, conference proceedings
    "practitioner",        # broker research, trader blogs, prop desks, newsletters, podcasts
    "retail_ecology",      # forums, chat groups, margin/retail-flow statistics, brokers' own data
    "app_ecosystem",       # the trading and data apps a local actually uses, and their APIs
    "media",               # native-language financial press, TV transcripts, wire services
    "archive",             # historical records, gazettes, digitised ledgers, discontinued series
    "physical_economy",    # ports, power, freight, tenders, satellite, inventories, shipping
    "source_graph",        # what the other nine cite, link and reply to -- the expansion edges
)
#: How long a "trailing window" is for the discovery-rate half of coverage.
DISCOVERY_WINDOW_DAYS = 14
#: The states a country's coverage can be in. Four, and three of them are not "covered".
COVERAGE_STATES: tuple[str, ...] = ("COVERED", "MAPPING", "STALLED", "UNMEASURED")
COVERAGE_RULE = (
    "a country is COVERED only when every source layer is mapped or declared absent WITH A "
    "REASON and automatic discovery is still adding sources in the trailing window; five obvious "
    "sources is not coverage, and a mapped country whose discovery rate has fallen to zero is "
    "STALLED rather than finished")


@dataclass(frozen=True)
class SourceRow:
    """One source, tagged with the ONE layer it belongs to.

    `verified` is the field that stops a wish list from counting as coverage: a root somebody
    typed is not a source until something fetched it. `absent_reason` is the other half -- a
    layer a country genuinely does not have (no retail margin statistics, no native app
    ecosystem) is DECLARED absent with the reason, which counts as mapped, and a layer nobody
    looked at is neither.
    """

    id: str = ""
    layer: str = ""
    label: str = ""
    roots: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    licence: str = ""
    verified: bool = False
    absent_reason: str = ""
    query_terms: tuple[str, ...] = ()
    notes: str = ""


_LAYER_RE = re.compile(r"\blayer\s*[:=]\s*([a-z_]+)", re.IGNORECASE)


def parse_source_layer(text: str) -> tuple[str, str]:
    """(layer, id) for a source declared as a STRING, or ("", text) when it carries no tag.

    The shipped packs write a source class as `"<id> :: <label> :: roots=... :: languages=..."`,
    and the layer arrives either as a `layer=<name>` token anywhere in that line or as a
    `::`-delimited field that happens to be one of the ten. Both are accepted; a line with
    neither is UNTAGGED, which is reported rather than guessed -- guessing a layer would make the
    coverage number a description of this parser instead of of the country.
    """
    raw = str(text or "")
    hit = _LAYER_RE.search(raw)
    if hit and _tok(hit.group(1)) in SOURCE_LAYERS:
        layer = _tok(hit.group(1))
    else:
        layer = next((_tok(p) for p in raw.split("::") if _tok(p) in SOURCE_LAYERS), "")
    first = raw.split("::", 1)[0].strip() or raw.strip()
    return layer, first


def source_rows(pack: CountryPack) -> list[SourceRow]:
    """Every source this pack declares, structured, whichever way it declared it."""
    out: list[SourceRow] = [s for s in pack.sources if isinstance(s, SourceRow)]
    have = {s.id for s in out}
    for text in pack.source_classes:
        layer, sid = parse_source_layer(text)
        if sid in have:
            continue
        have.add(sid)
        out.append(SourceRow(id=sid, layer=layer, label=str(text),
                             languages=tuple(pack.native_languages), verified=False))
    for layer, reason in dict(pack.absent_layers).items():
        out.append(SourceRow(id=f"absent:{_tok(layer)}", layer=_tok(layer),
                             absent_reason=str(reason)))
    return out


def layer_inventory(cc: str | CountryPack, *, pack: CountryPack | None = None
                    ) -> dict[str, list[dict[str, Any]]]:
    """{layer: [sources]} for one country, every one of the ten layers present as a key.

    An empty list is a layer NOBODY HAS MAPPED, and it is present in the answer for exactly that
    reason: a dictionary that only carries the layers with sources in it cannot be used to count
    what is missing. The eleventh key, `UNTAGGED`, holds the sources whose layer the pack did not
    say -- work for the pack's author, not a silent bucket.
    """
    got = pack if pack is not None else resolve_pack(cc)
    out: dict[str, list[dict[str, Any]]] = {layer: [] for layer in SOURCE_LAYERS}
    out["UNTAGGED"] = []
    if got is None:
        return out
    for row in source_rows(got):
        key = row.layer if row.layer in SOURCE_LAYERS else "UNTAGGED"
        out[key].append({"id": row.id, "label": row.label, "roots": list(row.roots),
                         "languages": list(row.languages), "licence": row.licence,
                         "verified": bool(row.verified),
                         "absent_reason": row.absent_reason,
                         "query_terms": list(row.query_terms)})
    return out


def discovery_rate(cc: str, conn: Any = None, *, window_days: int = DISCOVERY_WINDOW_DAYS
                   ) -> dict[str, Any]:
    """New sources per day for one country over the trailing window, from the registry.

    This is the half of coverage that cannot be faked by typing: it counts rows that the SCOUTS
    added to `sources`, not rows a pack declares. An unreadable table answers UNMEASURED, which
    blocks COVERED -- absence of evidence about discovery is never evidence that discovery is
    healthy.
    """
    code = _tok(cc if isinstance(cc, str) else getattr(cc, "code", ""))
    out: dict[str, Any] = {"country": code, "window_days": int(window_days),
                           "new_sources": None, "total_sources": None, "per_day": None,
                           "measured": False, "why": ""}
    c = conn
    close = c is None
    if c is None:
        try:
            c = R.connect()
        except Exception as exc:
            out["why"] = f"the registry is unreachable: {type(exc).__name__}: {exc}"
            return out
    try:
        cutoff = (datetime.now(tz=UTC) - timedelta(days=int(window_days))).isoformat()
        row = c.execute("SELECT COUNT(*) AS n FROM sources WHERE country=? AND first_seen>=?",
                        (code, cutoff)).fetchone()
        total = c.execute("SELECT COUNT(*) AS n FROM sources WHERE country=?", (code,)).fetchone()
    except Exception as exc:
        out["why"] = f"sources unreadable: {type(exc).__name__}: {exc}"
        return out
    finally:
        if close and c is not None:
            c.close()
    n = int(row["n"] if row is not None else 0)
    out.update({"new_sources": n, "total_sources": int(total["n"] if total is not None else 0),
                "per_day": round(n / max(1, int(window_days)), 4), "measured": True})
    return out


def coverage_state(cc: str | CountryPack, conn: Any = None, *,
                   pack: CountryPack | None = None,
                   window_days: int = DISCOVERY_WINDOW_DAYS) -> dict[str, Any]:
    """The country's coverage, as the principal's two conditions and nothing else."""
    got = pack if pack is not None else resolve_pack(cc)
    code = _tok(getattr(got, "code", cc) if got is not None else cc)
    inventory = layer_inventory(code, pack=got)
    layers: dict[str, dict[str, Any]] = {}
    for layer in SOURCE_LAYERS:
        rows = inventory[layer]
        verified = [r for r in rows if r["verified"]]
        declared_absent = [r for r in rows if r["absent_reason"]]
        if declared_absent:
            state, why = "ABSENT_DECLARED", str(declared_absent[0]["absent_reason"])
        elif verified:
            state, why = "MAPPED", f"{len(verified)} verified source(s)"
        elif rows:
            state, why = ("DECLARED_UNVERIFIED",
                          f"{len(rows)} declared source(s), none fetched yet")
        else:
            state, why = "UNMAPPED", "no source and no declared absence for this layer"
        layers[layer] = {"state": state, "sources": len(rows), "verified": len(verified),
                         "why": why}
    mapped = [k for k, v in layers.items() if v["state"] in ("MAPPED", "ABSENT_DECLARED")]
    unmapped = [k for k, v in layers.items() if v["state"] == "UNMAPPED"]
    unverified = [k for k, v in layers.items() if v["state"] == "DECLARED_UNVERIFIED"]
    disc = discovery_rate(code, conn, window_days=window_days)
    if got is None:
        state, why = "UNMEASURED", f"no country pack resolves for {code!r}"
    elif not disc["measured"]:
        state, why = "UNMEASURED", f"the discovery rate is unmeasured: {disc['why']}"
    elif unmapped or unverified:
        state = "MAPPING"
        why = (f"{len(mapped)}/{len(SOURCE_LAYERS)} layers mapped; unmapped={unmapped}; "
               f"declared but never fetched={unverified}")
    elif float(disc["per_day"] or 0.0) <= 0.0:
        state = "STALLED"
        why = (f"every layer is mapped but no new source was discovered for {code} in the last "
               f"{window_days} days; the scouts ran out of ideas, not the country out of sources")
    else:
        state = "COVERED"
        why = (f"all {len(SOURCE_LAYERS)} layers mapped or declared absent, and discovery is "
               f"still adding {disc['per_day']}/day")
    return {"country": code, "state": state, "why": why, "layers": layers,
            "layers_mapped": len(mapped), "layers_total": len(SOURCE_LAYERS),
            "layers_unmapped": unmapped, "layers_unverified": unverified,
            "untagged_sources": len(inventory["UNTAGGED"]), "discovery": disc,
            "rule": COVERAGE_RULE}


def native_query_seeds(cc: str | CountryPack, layer: str = "", *,
                       pack: CountryPack | None = None) -> list[dict[str, Any]]:
    """Native queries for one country and one layer, in the country's OWN script.

    THE ORDER IS THE POINT: native queries -> native sources -> native terminology -> native
    authors -> native code and community, and TRANSLATION ONLY AFTER RETRIEVAL. An English query
    against an English index cannot reach the forum where a local desk explains its own
    settlement convention, so nothing here is translated and nothing is generated from English.
    The terms come from the pack's own terminology (keyed by the layer when the pack tags it that
    way, else from every domain), and each is also emitted site-scoped to the layer's declared
    roots so a crawler can go straight at the ground rather than at a search engine's idea of it.
    """
    got = pack if pack is not None else resolve_pack(cc)
    if got is None:
        return []
    want = _tok(layer) if layer else ""
    inventory = layer_inventory(getattr(got, "code", ""), pack=got)
    terms: list[tuple[str, str]] = []
    vocab = dict(got.terminology)
    if want and want in vocab:
        terms.extend((want, t) for t in vocab[want])
    else:
        for domain, words in vocab.items():
            terms.extend((domain, t) for t in words)
    roots: list[str] = []
    extra: list[str] = []
    for row in inventory.get(want, []) if want else []:
        roots.extend(str(r) for r in row.get("roots") or [])
        extra.extend(str(t) for t in row.get("query_terms") or [])
    terms.extend((want or "layer", t) for t in extra)
    langs = list(got.native_languages) or ["UNMEASURED"]
    out: list[dict[str, Any]] = []
    for domain, term in terms:
        out.append({"country": getattr(got, "code", ""), "layer": want or "all",
                    "domain": domain, "query": term, "languages": langs,
                    "site_scoped": [f"site:{r} {term}" for r in roots[:6]],
                    "translate": "after retrieval only"})
    return out


#: A resolver the desk installs so `layer_inventory("kr")` works from a code alone. Module-level
#: so the coverage-tensor organ can point it at a loaded pack table instead of the filesystem.
PACK_RESOLVER: Callable[[str], CountryPack | None] | None = None
_PACK_CACHE: dict[str, CountryPack | None] = {}


def resolve_pack(cc: str | CountryPack) -> CountryPack | None:
    """One country's pack from its code: the installed resolver, then the desk's pack directory.

    Two export shapes are accepted, `PACK` and `pack()`, because the country departments ship the
    second: they build the dataclass through a LAZY import of this module so the department stays
    importable on a tree where this framework has not landed.
    """
    if isinstance(cc, CountryPack):
        return cc
    code = _tok(cc)
    if code in _PACK_CACHE:
        return _PACK_CACHE[code]
    got: CountryPack | None = None
    if PACK_RESOLVER is not None:
        try:
            got = PACK_RESOLVER(code)
        except Exception:
            got = None
    if got is None:
        got = _load_pack_file(code)
    _PACK_CACHE[code] = got
    return got


def _load_pack_file(code: str) -> CountryPack | None:
    path = DESK / "research" / "countries" / code / "pack.py"
    if not path.exists():
        return None
    for p in (str(DESK), str(DESK / "research"), str(ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    mod: Any = None
    try:
        mod = importlib.import_module(f"research.countries.{code}.pack")
    except Exception:
        try:
            spec = importlib.util.spec_from_file_location(f"country_{code}_pack", path)
            if spec is None or spec.loader is None:
                return None
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)
        except Exception:
            return None
    got = getattr(mod, "PACK", None)
    if not isinstance(got, CountryPack):
        factory = getattr(mod, "pack", None)
        if callable(factory):
            try:
                got = factory()
            except Exception:
                return None
    return got if isinstance(got, CountryPack) else None


# --------------------------------------------------------------------------- the tape objects
@dataclass(frozen=True)
class Bars:
    """One instrument's tape as arrays. `times` is UTC datetime64[ns], strictly increasing."""

    symbol: str
    timeframe: str
    times: np.ndarray
    close: np.ndarray
    high: np.ndarray | None = None
    low: np.ndarray | None = None
    volume: np.ndarray | None = None
    spread: np.ndarray | None = None

    def __len__(self) -> int:
        return int(self.close.size)


@dataclass(frozen=True)
class DataSeries:
    """One dated macro/positioning series. `dates` is datetime64[D]; `values` is float."""

    name: str
    dates: np.ndarray
    values: np.ndarray

    def __len__(self) -> int:
        return int(self.values.size)


# --------------------------------------------------------------------------- small helpers
def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _tok(value: Any) -> str:
    text = " ".join(str(value or "").strip().lower().replace("-", " ").replace("_", " ").split())
    return text.replace(" ", "_") or "unknown"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


_UNIVERSE_CACHE: dict[str, Any] = {}


def universe() -> dict[str, dict[str, Any]]:
    """The broker's own registry, or {} when it is not on this box. ABSENCE IS NOT PERMISSION and
    it is not a refusal: `validate_pack` reports which of the two it measured against."""
    path = Path(UNIVERSE_JSON)
    try:
        st = path.stat()
        key = f"{path}|{st.st_size}|{int(st.st_mtime)}"
    except OSError:
        _UNIVERSE_CACHE.clear()
        return {}
    if _UNIVERSE_CACHE.get("key") == key:
        cached: dict[str, dict[str, Any]] = _UNIVERSE_CACHE["doc"]
        return cached
    doc = _read_json(path)
    out: dict[str, dict[str, Any]] = ({str(k): v for k, v in doc.items() if isinstance(v, dict)}
                                      if isinstance(doc, dict) else {})
    _UNIVERSE_CACHE.clear()
    _UNIVERSE_CACHE.update({"key": key, "doc": out})
    return out


_DESK_MODULES: dict[str, Any] = {}


def desk_module(name: str) -> Any:
    """Lazily import one desk research organ, or None when it is not on this box.

    A `libs/` module may not DEPEND on the desk tree -- but the twelve transformation miners, the
    graveyard and the residual engine already exist there and reimplementing them here would be
    two machines answering one question differently. So they are reached optionally: absent, the
    miner that wanted one reports UNMEASURED naming the module, which is a measurement of this
    box rather than a silent branch.
    """
    if name in _DESK_MODULES:
        return _DESK_MODULES[name]
    mod: Any = None
    if (DESK / "research" / f"{name}.py").exists():
        for p in (str(DESK), str(DESK / "research"), str(ROOT)):
            if p not in sys.path:
                sys.path.insert(0, p)
        try:
            mod = importlib.import_module(name)
        except Exception:
            mod = None
    _DESK_MODULES[name] = mod
    return mod


def region_mandate_module() -> Any:
    """`libs.research.region_mandate` when a sibling builder has landed it, else None."""
    try:
        return importlib.import_module("libs.research.region_mandate")
    except Exception:
        return None


# --------------------------------------------------------------------------- calendar maths
def parse_day(text: Any) -> np.datetime64 | None:
    """One ISO date as datetime64[D], or None. Never raises: a malformed pack row is counted."""
    s = str(text or "").strip()[:10]
    if len(s) != 10:
        return None
    try:
        return np.datetime64(s, "D")
    except ValueError:
        return None


def parse_days(values: Sequence[Any]) -> np.ndarray:
    """A pack's date list as a sorted unique datetime64[D] array; unparseable rows are dropped
    by the caller's count, never by silence (`validate_pack` names them)."""
    out = [d for d in (parse_day(v) for v in values) if d is not None]
    if not out:
        return np.empty(0, dtype="datetime64[D]")
    return np.unique(np.array(out, dtype="datetime64[D]"))


def parse_hhmm(text: Any) -> tuple[int, int] | None:
    s = str(text or "").strip()
    if len(s) < 4 or ":" not in s:
        return None
    hh, _, mm = s.partition(":")
    try:
        h, m = int(hh), int(mm[:2])
    except ValueError:
        return None
    return (h, m) if 0 <= h < 24 and 0 <= m < 60 else None


def day_of_month(days: np.ndarray) -> np.ndarray:
    delta = (days.astype("datetime64[D]")
             - days.astype("datetime64[M]").astype("datetime64[D]")).astype("int64")
    out: np.ndarray = delta + 1
    return out


def month_of(days: np.ndarray) -> np.ndarray:
    return days.astype("datetime64[M]").astype("int64") % 12 + 1


def weekday_of(days: np.ndarray) -> np.ndarray:
    """Monday=0 .. Sunday=6. 1970-01-01 was a Thursday, hence the +3."""
    return (days.astype("datetime64[D]").astype("int64") + 3) % 7


def calendar_span(lo: np.datetime64, hi: np.datetime64) -> np.ndarray:
    if hi < lo:
        return np.empty(0, dtype="datetime64[D]")
    return np.arange(lo, hi + np.timedelta64(1, "D"), dtype="datetime64[D]")


def holiday_days(rule: HolidayRule, lo: np.datetime64, hi: np.datetime64) -> np.ndarray:
    """Every CLOSED day in [lo, hi] -- the explicit table, the recurring month-days, and the
    declared weekly closure. The weekly closure is declared per country, never assumed."""
    span = calendar_span(lo, hi)
    if span.size == 0:
        return span
    closed = np.zeros(span.size, dtype=bool)
    if rule.weekly_closed:
        wd = weekday_of(span)
        closed |= np.isin(wd, np.array(list(rule.weekly_closed), dtype="int64"))
    table = parse_days(rule.dates)
    if table.size:
        closed |= np.isin(span, table)
    if rule.fixed_md:
        md = np.array([f"{int(m):02d}-{int(d):02d}"
                       for m, d in zip(month_of(span), day_of_month(span), strict=True)])
        closed |= np.isin(md, np.array([str(x).strip() for x in rule.fixed_md]))
    return span[closed]


def _roll(day: int, closed: set[int], how: str) -> int | None:
    """One convention day moved off a closure, in DAYS-SINCE-EPOCH integers.

    Integers rather than datetime64 scalars on purpose: `np.ndarray.tolist()` on a datetime64[D]
    array yields `datetime.date` objects, so a set built that way silently never matches a
    datetime64 lookup -- the roll then appears to work and quietly never fires, which is the
    failure mode this function exists to prevent.
    """
    if how not in ("previous", "next"):
        return None if day in closed else day
    step = -1 if how == "previous" else 1
    cur = int(day)
    for _ in range(10):
        if cur not in closed:
            return cur
        cur += step
    return None


def settlement_days(rule: SettlementRule, pack: CountryPack, lo: np.datetime64,
                    hi: np.datetime64) -> np.ndarray:
    """One settlement/fixing convention turned into the DAYS it falls on, rolled off closures.

    This is the generic form of a gotobi: a day-of-month convention that must land on an open
    day, so the convention's economic force appears on the rolled day and NOT on the nominal one.
    A miner that tested the nominal day would measure the roll, not the flow.
    """
    span = calendar_span(lo, hi)
    if span.size == 0:
        return span
    closed = {int(v) for v in holiday_days(pack.holidays_rule, lo, hi).astype("int64")}
    kind = str(rule.kind or "").strip().lower()
    if kind == "day_of_month":
        want = np.array(list(rule.days) or [], dtype="int64")
        picked = span[np.isin(day_of_month(span), want)] if want.size else span[:0]
    elif kind in ("month_end", "quarter_end", "fiscal_year_end", "fiscal_quarter_end"):
        months = month_of(span)
        nxt = span + np.timedelta64(1, "D")
        is_last = month_of(nxt) != months
        if kind == "quarter_end":
            is_last &= np.isin(months, np.array([3, 6, 9, 12], dtype="int64"))
        elif kind in ("fiscal_year_end", "fiscal_quarter_end"):
            md = str(pack.fiscal_year_end or "").strip()
            fm = int(md[:2]) if len(md) == 5 and md[:2].isdigit() else 0
            if fm == 0:
                return span[:0]
            want_m = ([fm] if kind == "fiscal_year_end"
                      else [((fm - 1 + 3 * k) % 12) + 1 for k in range(4)])
            is_last &= np.isin(months, np.array(want_m, dtype="int64"))
        picked = span[is_last]
    elif kind == "weekday" and rule.weekday >= 0:
        picked = span[weekday_of(span) == int(rule.weekday)]
    elif kind == "week_of_month" and rule.weekday >= 0 and rule.week_of_month > 0:
        wd = weekday_of(span) == int(rule.weekday)
        nth = ((day_of_month(span) - 1) // 7) + 1 == int(rule.week_of_month)
        picked = span[wd & nth]
    else:
        return span[:0]
    if rule.months:
        picked = picked[np.isin(month_of(picked), np.array(list(rule.months), dtype="int64"))]
    rolled = [d for d in (_roll(int(x), closed, str(rule.roll or "none"))
                          for x in picked.astype("int64")) if d is not None]
    if not rolled:
        return span[:0]
    return np.unique(np.array(rolled, dtype="int64").astype("datetime64[D]"))


def era_masks(pack: CountryPack, days: np.ndarray) -> dict[str, np.ndarray]:
    """One boolean mask per declared policy era. A pack with no eras gets one `all` era, and the
    report SAYS the country declared none rather than pretending its history is homogeneous."""
    if days.size == 0:
        return {}
    out: dict[str, np.ndarray] = {}
    for era in pack.policy_eras:
        lo, hi = parse_day(era.start), parse_day(era.end)
        if lo is None or hi is None:
            continue
        out[str(era.name)] = (days >= lo) & (days <= hi)
    if not out:
        out["all"] = np.ones(days.size, dtype=bool)
    return out


# --------------------------------------------------------------------------- the lab context
@dataclass
class LabCtx:
    """What a generic miner is handed: the loaders, the registry door, its own clock and box.

    `record` is the ONE door a miner writes discoveries through, and it stamps the country tag
    (`generator = "<code>:<miner>"`), `payload.region = code` and `payload.region_command` -- so
    every row is findable again by the region framework's `is_region_row` and by the global OS's
    per-country registers without any miner having to remember to do it.
    """

    code: str
    region_command: str = ""
    conn: Any = None
    budget_s: float = 60.0
    deadline: float = 0.0
    dry_run: bool = False
    miner: str = ""
    seed: int = 20260917
    bars_loader: Callable[[str, str], Bars | None] | None = None
    series_loader: Callable[[str], DataSeries | None] | None = None
    recorded: list[str] = field(default_factory=list)
    unmeasured: list[str] = field(default_factory=list)
    transmission_seeds: list[dict[str, Any]] = field(default_factory=list)
    axis_proposals: list[dict[str, Any]] = field(default_factory=list)
    _bars: dict[tuple[str, str], Bars | None] = field(default_factory=dict)
    _series: dict[str, DataSeries | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.deadline <= 0.0:
            self.deadline = time.monotonic() + float(self.budget_s)

    @property
    def tag(self) -> str:
        return f"{_tok(self.code)}:"

    def remaining_s(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def rng(self, salt: str = "") -> np.random.Generator:
        """A seeded generator per miner+salt: two runs of one miner draw the same null, and two
        different miners never share one, so a permutation p is reproducible and not correlated
        across tests by accident."""
        h = abs(hash((self.seed, self.code, self.miner, salt))) % (2**32)
        return np.random.default_rng(h)

    def bars(self, symbol: str, timeframe: str = "H1") -> Bars | None:
        key = (str(symbol).upper(), str(timeframe).upper())
        if key in self._bars:
            return self._bars[key]
        out: Bars | None = None
        if self.bars_loader is not None:
            try:
                out = self.bars_loader(key[0], key[1])
            except Exception as exc:
                self.note(f"bars:{key[0]}:{key[1]}", f"{type(exc).__name__}: {exc}")
                out = None
        self._bars[key] = out
        return out

    def series(self, name: str) -> DataSeries | None:
        key = str(name)
        if not key:
            return None
        if key in self._series:
            return self._series[key]
        out: DataSeries | None = None
        if self.series_loader is not None:
            try:
                out = self.series_loader(key)
            except Exception as exc:
                self.note(f"series:{key}", f"{type(exc).__name__}: {exc}")
                out = None
        self._series[key] = out
        return out

    def note(self, what: str, why: str) -> None:
        """UNMEASURED, by name. The first argument is WHAT could not be measured; the second is
        which input was missing. Both, always -- `unmeasured: ["positioning"]` tells nobody
        whether the currency has no COT row or the file is not on this box."""
        row = f"{self.miner or 'lab'}/{what}: {why}"
        if row not in self.unmeasured:
            self.unmeasured.append(row)

    def seed_transmission(self, **row: Any) -> None:
        self.transmission_seeds.append({"from_country": self.code, "miner": self.miner, **row})

    def propose_axis(self, axis_id: str, name: str, definition: str, **evidence: Any) -> None:
        """A coordinate this country exposed that the desk's ontology has no word for. Recorded
        as a PROPOSAL; the transmission engine owns the write into the axis extension file."""
        self.axis_proposals.append({"axis_id": _tok(axis_id), "name": name,
                                    "definition": definition, "country": self.code,
                                    "miner": self.miner, "evidence": dict(evidence)})

    def record(self, *, mechanism: str, source_id: str = "", source_type: str = "claim",
               **fields: Any) -> tuple[str, bool]:
        """Record one discovery for this country. Returns (discovery_id, created)."""
        sid = str(source_id or self.miner or "unattributed")
        if not sid.lower().startswith(self.tag):
            sid = f"{self.tag}{sid}"
        payload = dict(fields.pop("payload", None) or {})
        payload.setdefault("region", self.code)
        payload.setdefault("country", self.code)
        payload.setdefault("region_command", self.region_command)
        payload.setdefault("miner", self.miner)
        fields.setdefault("information", MINER_INFORMATION.get(self.miner, "macro"))
        origin = str(fields.pop("origin", "EXTERNAL"))
        if self.dry_run or self.conn is None:
            return "dry-run", False
        did, created = R.record_discovery(
            source_id=sid, source_type=source_type, mechanism=mechanism, origin=origin,
            generator=f"{self.tag}{self.miner or 'unnamed'}", payload=payload, conn=self.conn,
            **fields)
        self.recorded.append(did)
        return did, created


# --------------------------------------------------------------------------- default loaders
def default_bars_loader(symbol: str, timeframe: str = "H1") -> Bars | None:
    """The desk's parquet estate, read LAZILY through pandas so this module imports without it.

    Returns None -- never raises and never a partial frame -- when the file is absent, unreadable
    or shorter than the measurement floor; the caller reports which symbol that was.
    """
    path = Path(BARS_DIR) / f"{str(symbol).upper()}_{str(timeframe).upper()}.parquet"
    if not path.exists():
        return None
    try:
        import pandas as pd

        frame = pd.read_parquet(path)
    except Exception:
        return None
    if frame is None or len(frame) == 0 or "close" not in frame.columns:
        return None
    frame = frame.tail(MAX_BARS)
    idx = frame.index
    try:
        times = np.asarray(idx.tz_convert("UTC").tz_localize(None).values, dtype="datetime64[ns]")
    except (AttributeError, TypeError):
        times = np.asarray(idx.values, dtype="datetime64[ns]")

    def col(name: str) -> np.ndarray | None:
        if name not in frame.columns:
            return None
        return np.asarray(frame[name].to_numpy(), dtype="float64")

    close = col("close")
    if close is None:
        return None
    return Bars(symbol=str(symbol).upper(), timeframe=str(timeframe).upper(), times=times,
                close=close, high=col("high"), low=col("low"), volume=col("tick_volume"),
                spread=col("spread"))


def cot_series(currency_or_symbol: str) -> DataSeries | None:
    """`data/axes/cot.json` as a dated net-positioning series, or None when the symbol has no row.

    The COT axis is keyed by the FUSION SYMBOL the CFTC market maps to (AUDUSD, XAUUSD, US500 ...)
    and stamped with `knowable_at`, not `as_of` -- so the series is point-in-time by construction
    and a country whose currency the CFTC does not publish is UNMEASURED, not zero.
    """
    doc = _read_json(COT_JSON)
    if not isinstance(doc, dict):
        return None
    want = str(currency_or_symbol).upper()
    rows = [r for r in (doc.get("rows") or [])
            if isinstance(r, dict) and str(r.get("symbol") or "").upper() == want]
    if not rows:
        return None
    pairs = [(parse_day(r.get("knowable_at")), r.get("net_pct_oi")) for r in rows]
    keep = [(d, float(v)) for d, v in pairs if d is not None and isinstance(v, (int, float))]
    if not keep:
        return None
    keep.sort(key=lambda t: t[0])
    return DataSeries(name=f"cot:{want}",
                      dates=np.array([d for d, _ in keep], dtype="datetime64[D]"),
                      values=np.array([v for _, v in keep], dtype="float64"))


# --------------------------------------------------------------------------- validation
def validate_pack(pack: CountryPack, reg: Mapping[str, Mapping[str, Any]] | None = None
                  ) -> list[str]:
    """Every way this pack is not yet a pack, named. An empty list is the only pass.

    THE TWO-LANE MANDATE IS ENFORCED HERE (2026-09-06). A country lab mints STATISTICAL
    hypotheses, so a single-name equity in its instrument list is not breadth: it spends the
    program's shared multiple-testing budget on the asset class least suited to the method, and
    every FX and metals cell in the program pays for it. An instrument the broker registry does
    not know is REFUSED too -- absence is not permission (universe policy).
    """
    known: Mapping[str, Mapping[str, Any]] = reg if reg is not None else universe()
    problems: list[str] = [f"pack row: {n}" for n in pack.coercion_notes
                           if n.startswith("FAILED")]
    if not str(pack.code).strip():
        problems.append("code: empty; every row this lab writes is tagged with it")
    elif _tok(pack.code) != str(pack.code):
        problems.append(f"code {pack.code!r}: must be the canonical token {_tok(pack.code)!r}")
    if not str(pack.name).strip():
        problems.append("name: empty")
    if pack.region_command not in REGION_COMMANDS:
        problems.append(f"region_command {pack.region_command!r}: not one of "
                        f"{list(REGION_COMMANDS)}")
    if len(str(pack.currency).strip()) != 3:
        problems.append(f"currency {pack.currency!r}: expected a 3-letter code")
    if not pack.executable_instruments:
        problems.append("executable_instruments: empty; the lab can compile no cell")
    for sym in pack.executable_instruments:
        row = known.get(sym)
        if known and row is None:
            problems.append(f"instrument {sym}: not in the broker universe at {UNIVERSE_JSON}")
            continue
        klass = " ".join(str((row or {}).get("asset_class") or "").lower()
                         .replace("_", " ").split())
        if klass in EQUITY_CLASSES:
            problems.append(f"instrument {sym}: single-name equity; the two-lane mandate "
                            f"(2026-09-06) forbids hunting it for statistical hypotheses")
    if pack.central_bank.framework not in CB_FRAMEWORKS:
        problems.append(f"central_bank.framework {pack.central_bank.framework!r}: not one of "
                        f"{list(CB_FRAMEWORKS)}")
    if pack.central_bank.decision_dates:
        bad = [d for d in pack.central_bank.decision_dates if parse_day(d) is None]
        if bad:
            problems.append(f"central_bank.decision_dates: unparseable {bad[:3]}")
    if pack.export_economy not in EXPORT_TYPES:
        problems.append(f"export_economy {pack.export_economy!r}: not one of {list(EXPORT_TYPES)}")
    if pack.retail_leverage_regime not in LEVERAGE_REGIMES:
        problems.append(f"retail_leverage_regime {pack.retail_leverage_regime!r}: not one of "
                        f"{list(LEVERAGE_REGIMES)}")
    for fx in pack.fixing_conventions:
        if parse_hhmm(fx.time_utc) is None:
            problems.append(f"fixing {fx.name}: time_utc {fx.time_utc!r} is not HH:MM")
    for sr in pack.settlement_conventions:
        if sr.kind not in SETTLEMENT_KINDS:
            problems.append(f"settlement {sr.name}: kind {sr.kind!r} not one of "
                            f"{list(SETTLEMENT_KINDS)}")
        if sr.kind == "day_of_month" and not sr.days:
            problems.append(f"settlement {sr.name}: day_of_month with no days")
        if any(not 1 <= int(d) <= 31 for d in sr.days):
            problems.append(f"settlement {sr.name}: days outside 1..31")
        if sr.kind in ("fiscal_year_end", "fiscal_quarter_end") and not pack.fiscal_year_end:
            problems.append(f"settlement {sr.name}: needs fiscal_year_end on the pack")
    if pack.fiscal_year_end and len(str(pack.fiscal_year_end)) != 5:
        problems.append(f"fiscal_year_end {pack.fiscal_year_end!r}: expected MM-DD")
    execset = {s.upper() for s in pack.executable_instruments}
    for ex in pack.exchanges:
        for sym in ex.index_symbols:
            if known and sym not in known:
                problems.append(f"exchange {ex.name}: index symbol {sym} not in the universe")
            elif sym.upper() not in execset:
                problems.append(f"exchange {ex.name}: index symbol {sym} is not declared "
                                f"executable on this pack")
    for win in pack.session_windows:
        if parse_hhmm(win.start_utc) is None or parse_hhmm(win.end_utc) is None:
            problems.append(f"session_window {win.name}: start/end must be HH:MM UTC")
    for era in pack.policy_eras:
        lo, hi = parse_day(era.start), parse_day(era.end)
        if lo is None or hi is None or hi < lo:
            problems.append(f"policy_era {era.name}: start/end unparseable or reversed")
    if not pack.native_languages:
        problems.append("native_languages: empty; native-language mining is not optional "
                        "(native queries -> native sources -> native terminology)")
    for dom, terms in dict(pack.terminology).items():
        if not terms:
            problems.append(f"terminology[{dom}]: empty")
    for entry in pack.custom_miners:
        if ":" not in str(entry):
            problems.append(f"custom_miner {entry!r}: expected a dotted 'module:function' entry")
    domain_ids = {d.id for d in pack.domains}
    for d in pack.domains:
        if not d.objects:
            problems.append(f"domain {d.id}: no research objects")
        if not d.controls:
            problems.append(f"domain {d.id}: no negative controls; an effect with no control "
                            f"cannot be told from its own selection")
    for miner, ids in dict(pack.miner_domains).items():
        for did in ids:
            if did not in domain_ids:
                problems.append(f"miner_domains[{miner}]: unknown domain {did!r}")
    for a in pack.actors:
        if not str(a.name).strip():
            problems.append("actor: an actor with no name")
        elif not str(a.falsifier).strip():
            problems.append(f"actor {a.name}: falsifier is empty; an actor with no falsifier is "
                            f"a story, and a story is not a research object")
    for seed in pack.transmission_edges_seed:
        if known and seed.asset not in known:
            problems.append(f"transmission seed -> {seed.to_country}: asset {seed.asset} is not "
                            f"in the broker universe")
        if not str(seed.to_country).strip():
            problems.append("transmission seed: no to_country")
    return problems


#: The problems that must STOP a pack from running, as opposed to the ones a miner reports and
#: works around. The split matters: refusing to mine a whole country because one of its five
#: fixings has no pinned minute would cost the desk that country, while running a pack whose
#: instruments the broker cannot execute -- or which names a single-name equity -- puts cells on
#: the docket that spend the program's shared multiple-testing budget on ground the mandate
#: excludes. So the first kind is fatal and the second kind is UNMEASURED by name.
FATAL_PREFIXES: tuple[str, ...] = ("instrument ", "executable_instruments", "region_command",
                                   "code", "currency", "pack row: FAILED", "exchange ")


def fatal_problems(problems: Sequence[str]) -> list[str]:
    """The subset of `validate_pack`'s answer that means DO NOT RUN THIS PACK."""
    return [p for p in problems if p.startswith(FATAL_PREFIXES)]


def mandate_of(pack: CountryPack) -> Any:
    """This pack as a `region_mandate.Mandate`, so the region framework's registers, frontier and
    saturation measure a COUNTRY with no new code. Returns None when the framework is absent."""
    rm = region_mandate_module()
    if rm is None:
        return None
    all_domains = tuple(d.id for d in pack.domains)
    miners = tuple(
        rm.MinerSpec(name=name, kind=MINER_KIND.get(name, "mechanism"),
                     domain_ids=tuple(pack.miner_domains.get(name) or all_domains),
                     entry=f"libs.research.country_lab:generic_{name}",
                     steerable=name not in ("central_bank_surprise", "calendar_settlement"),
                     notes=f"generic country miner for {pack.code}")
        for name in GENERIC_MINERS)
    custom = tuple(
        rm.MinerSpec(name=f"custom_{i}", kind="mechanism",
                     domain_ids=tuple(pack.miner_domains.get(f"custom_{i}") or all_domains),
                     entry=entry, notes=f"{pack.code} custom miner")
        for i, entry in enumerate(pack.custom_miners))
    return rm.Mandate(
        region=pack.code,
        mission=pack.mission or f"mine {pack.name} to exhaustion under one mandate held as data",
        actors=tuple(rm.Actor(**{f.name: getattr(a, f.name) for f in _ACTOR_FIELDS})
                     for a in pack.actors),
        domains=tuple(rm.Domain(**{f.name: getattr(d, f.name) for f in _DOMAIN_FIELDS})
                      for d in pack.domains),
        instruments=tuple(pack.executable_instruments),
        native_languages=tuple(pack.native_languages),
        terminology=dict(pack.terminology),
        source_classes=tuple(pack.source_classes),
        datasets=tuple(rm.DatasetSpec(**{f.name: getattr(ds, f.name) for f in _DATASET_FIELDS})
                       for ds in pack.datasets),
        miners=miners + custom,
        capital_authority=False,
        controls_default=("matched days", "randomised dates", "adjacent days",
                          "other currencies"),
    )


# --------------------------------------------------------------------------- measurement kernel
def log_returns(close: np.ndarray) -> np.ndarray:
    """Bar-to-bar log returns, first element 0. Non-positive prices give 0, never a nan that
    silently poisons a mean three functions later."""
    c = np.asarray(close, dtype="float64")
    out = np.zeros(c.size, dtype="float64")
    if c.size < 2:
        return out
    prev, cur = c[:-1], c[1:]
    ok = (prev > 0) & (cur > 0) & np.isfinite(prev) & np.isfinite(cur)
    step = np.zeros(cur.size, dtype="float64")
    step[ok] = np.log(cur[ok] / prev[ok])
    out[1:] = step
    return out


def forward_returns(close: np.ndarray, horizon: int = 1) -> np.ndarray:
    """log(close[i+h] / close[i]); the last h entries are nan and are DROPPED by every caller,
    never zero-filled -- a zero at the end of a series is an invented observation."""
    c = np.asarray(close, dtype="float64")
    out = np.full(c.size, np.nan, dtype="float64")
    h = max(1, int(horizon))
    if c.size <= h:
        return out
    a, b = c[:-h], c[h:]
    ok = (a > 0) & (b > 0) & np.isfinite(a) & np.isfinite(b)
    vals = np.full(a.size, np.nan, dtype="float64")
    vals[ok] = np.log(b[ok] / a[ok])
    out[:-h] = vals
    return out


def bar_days(bars: Bars) -> np.ndarray:
    return np.asarray(bars.times, dtype="datetime64[ns]").astype("datetime64[D]")


def bar_hours(bars: Bars) -> np.ndarray:
    """Minutes since UTC midnight for every bar -- the hour-of-day coordinate every matched
    control and every session window is measured on."""
    t = np.asarray(bars.times, dtype="datetime64[ns]")
    out: np.ndarray = ((t.astype("datetime64[m]") - t.astype("datetime64[D]"))
                       .astype("timedelta64[m]").astype("int64"))
    return out


def permutation_p(observed: float, draws: np.ndarray, two_sided: bool = True) -> float:
    """(1 + #{draw at least as extreme}) / (1 + n). The +1 is not decoration: with 200 draws the
    smallest p a permutation test can honestly report is 1/201, and reporting 0 claims a
    precision the draw count does not have."""
    d = np.asarray(draws, dtype="float64")
    d = d[np.isfinite(d)]
    if d.size == 0 or not math.isfinite(observed):
        return 1.0
    hit = np.abs(d) >= abs(observed) if two_sided else d >= observed
    return float((1.0 + float(hit.sum())) / (1.0 + d.size))


def _matched_control_mask(days: np.ndarray, hours: np.ndarray, event: np.ndarray) -> np.ndarray:
    """Bars that are NOT event bars but share the event bars' (weekday, hour) profile.

    THIS IS THE CONTROL THAT MAKES A CALENDAR RESULT MEAN ANYTHING. Settlement days cluster on
    particular weekdays and fixings on particular hours, so comparing them with the unconditional
    mean measures the day-of-week and hour-of-day shape of the tape. The matched control holds
    both fixed and leaves only the convention.
    """
    if event.size == 0 or not event.any():
        return np.zeros(event.shape, dtype=bool)
    wd = weekday_of(days)
    profile = {(int(a), int(b)) for a, b in zip(wd[event], hours[event], strict=True)}
    keys = np.array([(int(a) << 16) | (int(b) & 0xFFFF)
                     for a, b in zip(wd, hours, strict=True)], dtype="int64")
    want = np.array([(a << 16) | (b & 0xFFFF) for a, b in profile], dtype="int64")
    out: np.ndarray = np.isin(keys, want) & ~event
    return out


def event_effect(bars: Bars, event_dates: np.ndarray, *, horizon: int = 1,
                 hours: tuple[int, int] | None = None, rng: np.random.Generator | None = None,
                 n_perm: int = N_PERM, eras: Mapping[str, np.ndarray] | None = None,
                 min_events: int = MIN_EVENTS) -> dict[str, Any]:
    """The one event study every calendar miner here runs, with its controls attached.

    Returns the signed mean forward return on the event bars, the MATCHED control mean (same
    weekday and hour, other days), the difference, a permutation p from randomised dates, the
    absolute-move ratio (a liquidity/volatility effect that a signed mean cannot see), the
    ADJACENT-day placebo, and the per-era split. An input too short or an event set too small
    returns `verdict: POORLY_MEASURED` with the counts -- never a p-value nobody should read.
    """
    out: dict[str, Any] = {"verdict": "POORLY_MEASURED", "n_events": 0, "n_control": 0,
                           "symbol": bars.symbol, "chart": bars.timeframe,
                           "horizon_bars": int(max(1, horizon))}
    n = len(bars)
    if n < MIN_BARS:
        out["why"] = f"{bars.symbol} {bars.timeframe}: {n} bars < {MIN_BARS}"
        return out
    days, hrs = bar_days(bars), bar_hours(bars)
    fwd = forward_returns(bars.close, horizon)
    finite = np.isfinite(fwd)
    in_window = np.ones(n, dtype=bool)
    if hours is not None:
        lo_m, hi_m = hours
        in_window = (hrs >= int(lo_m)) & (hrs <= int(hi_m))
    ev = np.isin(days, np.asarray(event_dates, dtype="datetime64[D]")) & in_window & finite
    n_ev = int(ev.sum())
    out["n_events"] = n_ev
    if n_ev < int(min_events):
        out["why"] = f"{n_ev} event bars < {min_events}"
        return out
    ctrl = _matched_control_mask(days, hrs, ev) & finite & in_window
    out["n_control"] = int(ctrl.sum())
    if int(ctrl.sum()) < int(min_events):
        out["why"] = f"{int(ctrl.sum())} matched control bars < {min_events}"
        return out
    mean_ev, mean_ct = float(fwd[ev].mean()), float(fwd[ctrl].mean())
    abs_ev, abs_ct = float(np.abs(fwd[ev]).mean()), float(np.abs(fwd[ctrl]).mean())
    diff = mean_ev - mean_ct
    # THE NULL RANDOMISES DATES, NEVER BARS. A calendar effect lives on DAYS: resampling
    # individual bars from inside the same event days gives a null that has already seen the
    # effect, so it is far too tight and every convention looks significant. Drawing k random
    # DAYS asks the question the miner is actually making -- are THESE dates special among all
    # dates -- and it is why a two-decision-date study honestly reports a weak p.
    gen = rng if rng is not None else np.random.default_rng(0)
    pool_bar = ctrl | ev
    pool_days = np.unique(days[pool_bar])
    ev_days = np.unique(days[ev])
    k = int(ev_days.size)
    out["n_event_days"] = k
    if k < MIN_EVENT_DAYS:
        out["why"] = (f"{k} distinct event date(s) < {MIN_EVENT_DAYS}: a randomised-date"
                      f" null cannot be drawn")
        return out
    draws = np.full(int(n_perm), np.nan, dtype="float64")
    if pool_days.size > k:
        for i in range(int(n_perm)):
            pick = gen.choice(pool_days, size=k, replace=False)
            mask = np.isin(days, pick) & pool_bar
            rest = pool_bar & ~mask
            if mask.any() and rest.any():
                draws[i] = float(fwd[mask].mean()) - float(fwd[rest].mean())
    p = permutation_p(diff, draws)
    adj = np.isin(days, np.asarray(event_dates, dtype="datetime64[D]")
                  + np.timedelta64(1, "D")) & finite & in_window & ~ev
    adjacent = float(fwd[adj].mean() - fwd[ctrl].mean()) if int(adj.sum()) >= min_events else None
    per_era: dict[str, Any] = {}
    for name, mask in (eras or {}).items():
        m = ev & mask
        c = ctrl & mask
        if int(m.sum()) >= min_events and int(c.sum()) >= min_events:
            per_era[name] = {"n": int(m.sum()),
                             "diff": round(float(fwd[m].mean() - fwd[c].mean()), 8)}
        else:
            per_era[name] = {"n": int(m.sum()), "diff": None, "why": "too few bars in this era"}
    out.update({
        "verdict": "MEASURED", "mean_event": round(mean_ev, 8), "mean_control": round(mean_ct, 8),
        "diff": round(diff, 8), "p_perm": round(p, 6),
        "abs_event": round(abs_ev, 8), "abs_control": round(abs_ct, 8),
        "abs_ratio": round(abs_ev / abs_ct, 6) if abs_ct > 0 else None,
        "adjacent_day_placebo": None if adjacent is None else round(adjacent, 8),
        "eras": per_era, "n_perm": int(n_perm),
        "significant": bool(p <= P_MAX),
        "controls": ["matched weekday+hour", "randomised dates (permutation)", "adjacent day"],
    })
    return out


def window_effect(bars: Bars, start_utc: str, end_utc: str, *,
                  eras: Mapping[str, np.ndarray] | None = None) -> dict[str, Any]:
    """One intraday window against the REST OF THE SAME DAYS: mean return, absolute move, and the
    share of the day's absolute move the window carries. The control is the same day's other
    bars, so a result cannot be a property of the days the window happens to fall on."""
    out: dict[str, Any] = {"verdict": "POORLY_MEASURED", "window": f"{start_utc}-{end_utc}",
                           "symbol": bars.symbol, "chart": bars.timeframe}
    lo, hi = parse_hhmm(start_utc), parse_hhmm(end_utc)
    if lo is None or hi is None:
        out["why"] = "window is not HH:MM-HH:MM UTC"
        return out
    n = len(bars)
    if n < MIN_BARS:
        out["why"] = f"{bars.symbol} {bars.timeframe}: {n} bars < {MIN_BARS}"
        return out
    mins = bar_hours(bars)
    lo_m, hi_m = lo[0] * 60 + lo[1], hi[0] * 60 + hi[1]
    inside = ((mins >= lo_m) & (mins < hi_m)) if lo_m <= hi_m else ((mins >= lo_m) | (mins < hi_m))
    rets = log_returns(bars.close)
    ok = np.isfinite(rets)
    if int((inside & ok).sum()) < MIN_BARS // 4 or int((~inside & ok).sum()) < MIN_BARS // 4:
        out["why"] = "too few bars inside or outside the window"
        return out
    a, b = rets[inside & ok], rets[~inside & ok]
    abs_a, abs_b = float(np.abs(a).mean()), float(np.abs(b).mean())
    per_era: dict[str, Any] = {}
    for name, mask in (eras or {}).items():
        m = inside & ok & mask
        per_era[name] = ({"n": int(m.sum()), "mean": round(float(rets[m].mean()), 8)}
                         if int(m.sum()) >= MIN_BARS // 10
                         else {"n": int(m.sum()), "mean": None, "why": "too few bars in this era"})
    out.update({"verdict": "MEASURED", "n_inside": int(a.size), "n_outside": int(b.size),
                "mean_inside": round(float(a.mean()), 8),
                "mean_outside": round(float(b.mean()), 8),
                "abs_inside": round(abs_a, 8), "abs_outside": round(abs_b, 8),
                "abs_ratio": round(abs_a / abs_b, 6) if abs_b > 0 else None,
                "eras": per_era,
                "controls": ["the same days' bars outside the window"]})
    return out


def align_daily(series: DataSeries, bars: Bars, horizon: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """A dated series against an instrument's forward return on the SAME day, aligned by day.

    The series' own stamp is taken as knowable at that day's close, which is why every caller
    passes a point-in-time series (`knowable_at`, not `as_of`): this function cannot repair a
    series that was stamped with its reference date instead of its publication date.
    """
    if len(series) == 0 or len(bars) == 0:
        return np.empty(0), np.empty(0)
    days = bar_days(bars)
    fwd = forward_returns(bars.close, horizon)
    uniq = np.unique(days)
    daily = np.full(uniq.size, np.nan, dtype="float64")
    order = np.argsort(days, kind="stable")
    sd, sf = days[order], fwd[order]
    idx = np.searchsorted(sd, uniq, side="right") - 1
    ok = (idx >= 0) & np.isfinite(sf[np.clip(idx, 0, sf.size - 1)])
    daily[ok] = sf[np.clip(idx, 0, sf.size - 1)][ok]
    pos = np.searchsorted(uniq, np.asarray(series.dates, dtype="datetime64[D]"))
    valid = (pos < uniq.size) & (pos >= 0)
    pos = np.clip(pos, 0, max(0, uniq.size - 1))
    good = valid & np.isfinite(daily[pos]) & np.isfinite(series.values)
    return np.asarray(series.values, dtype="float64")[good], daily[pos][good]


def corr_with_null(x: np.ndarray, y: np.ndarray, *, rng: np.random.Generator | None = None,
                   n_perm: int = N_PERM, block: int = 5) -> dict[str, Any]:
    """Pearson correlation with a CIRCULAR-BLOCK permutation null.

    Blocks, not an i.i.d. shuffle: shuffling an autocorrelated regressor destroys its persistence
    and manufactures significance for exactly the class of variable a macro series is. The null
    rolls x by a random offset, which keeps x's own structure and destroys only its alignment
    with y -- the hypothesis actually under test.
    """
    a = np.asarray(x, dtype="float64")
    b = np.asarray(y, dtype="float64")
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    if a.size < 30:
        return {"verdict": "POORLY_MEASURED", "n": int(a.size), "why": "fewer than 30 pairs"}
    a = a - a.mean()
    b = b - b.mean()
    den = float(np.sqrt((a * a).sum() * (b * b).sum()))
    r = float((a * b).sum() / den) if den > 0 else 0.0
    gen = rng if rng is not None else np.random.default_rng(0)
    draws = np.empty(int(n_perm), dtype="float64")
    for i in range(int(n_perm)):
        shift = int(gen.integers(block, max(block + 1, a.size - block)))
        rolled = np.roll(a, shift)
        d = float(np.sqrt((rolled * rolled).sum() * (b * b).sum()))
        draws[i] = float((rolled * b).sum() / d) if d > 0 else 0.0
    return {"verdict": "MEASURED", "n": int(a.size), "corr": round(r, 6),
            "p_perm": round(permutation_p(r, draws), 6),
            "significant": bool(permutation_p(r, draws) <= P_MAX),
            "null": "circular block shift of x (keeps x's autocorrelation)"}


# --------------------------------------------------------------------------- the generic miners
def _reaction_set(pack: CountryPack, reg: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """The pack's own instruments plus the global set, filtered by what this box can execute.

    Both halves, always: a domestic shock measured only against domestic instruments cannot tell
    a local mechanism from a global risk day, and measured only against the global set cannot
    find the mechanism at all.
    """
    out = [s.upper() for s in pack.executable_instruments]
    for sym in GLOBAL_REACTION_SET:
        if sym in out:
            continue
        if not reg or sym in reg:
            out.append(sym)
    return out


def _eras_for(pack: CountryPack, bars: Bars) -> dict[str, np.ndarray]:
    return era_masks(pack, bar_days(bars))


def generic_central_bank_surprise(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """Rate decisions: the surprise, and what it moved -- domestically and globally.

    Surprise = actual - expected where an expectation series is on this box, else actual - prior,
    and the discovery SAYS WHICH: a surprise against a prior is a different economic quantity
    (it contains the whole expected path) and reading the two as one is how a central-bank study
    quietly becomes a momentum study.
    """
    cb = pack.central_bank
    if not str(cb.name).strip():
        ctx.note("central_bank", "the pack declares no central bank")
        return {"outcome": UNMEASURED, "why": "no central bank on the pack"}
    dates = parse_days(cb.decision_dates)
    if dates.size == 0:
        ctx.note("decision_dates", f"{cb.name}: no decision dates on the pack"
                                   f" (rule: {cb.decision_calendar_rule or 'none declared'})")
        return {"outcome": UNMEASURED, "why": "no decision dates"}
    actual = ctx.series(cb.policy_rate_series) if cb.policy_rate_series else None
    expected = ctx.series(cb.expected_rate_series) if cb.expected_rate_series else None
    basis = "vs_expected" if expected is not None else ("vs_prior" if actual is not None
                                                        else "date_only")
    if actual is None:
        ctx.note("policy_rate_series",
                 f"{cb.policy_rate_series or 'not declared'}: no rate series on this box; the "
                 f"study measures the DECISION DAY, not the surprise")
    reg = universe()
    rows: list[dict[str, Any]] = []
    for sym in _reaction_set(pack, reg):
        if ctx.remaining_s() <= 0:
            break
        bars = ctx.bars(sym, "H1")
        if bars is None:
            ctx.note(f"bars:{sym}", "no H1 tape on this box")
            continue
        res = event_effect(bars, dates, horizon=4, rng=ctx.rng(sym), eras=_eras_for(pack, bars))
        res["symbol"] = sym
        rows.append(res)
    measured = [r for r in rows if r.get("verdict") == "MEASURED"]
    hits = [r for r in measured if r.get("significant")]
    n = 0
    for r in hits:
        did, created = ctx.record(
            mechanism=f"{pack.code}_central_bank_decision_reaction",
            source_id=f"central_bank:{_tok(cb.name)}", source_type="calendar",
            actor=f"{pack.name} central bank ({cb.name}) and the desks positioned into its "
                  f"decisions",
            constraint=f"the {cb.framework} framework binds the decision to a published calendar; "
                       f"whoever is wrong on the day must reprice within hours",
            economic_rationale=f"a {cb.framework} decision on a known date reprices the {sym_of(r)}"
                               f" leg; the surprise basis here is {basis}",
            assets=[sym_of(r)], horizons=["intraday"], sessions=["all"],
            regimes=["unconditional"],
            required_data=[cb.policy_rate_series or "policy rate (absent)",
                           cb.expected_rate_series or "expectation (absent)"],
            pit_requirements=["decision timestamp", "publication time of the expectation"],
            novelty=0.5, confidence=0.5,
            falsifier=f"the decision-day effect on {sym_of(r)} does not survive the matched "
                      f"weekday+hour control or the randomised-date null",
            payload={"basis": basis, "reading": r, "framework": cb.framework,
                     "publication_classes": list(cb.publication_classes)})
        n += int(created or did != "dry-run")
    return {"outcome": OK if measured else UNMEASURED, "discoveries": n, "basis": basis,
            "n_symbols": len(rows), "measured": len(measured), "significant": len(hits),
            "why": "" if measured else "no instrument carried a measurable decision-day study",
            "readings": measured[:12]}


def sym_of(row: Mapping[str, Any]) -> str:
    return str(row.get("symbol") or "")


def generic_release_surprise(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """The country's scheduled statistics: each release class as its own event study."""
    if not pack.release_classes:
        ctx.note("release_classes", "the pack declares no national release calendar")
        return {"outcome": UNMEASURED, "why": "no release classes"}
    out: list[dict[str, Any]] = []
    n = 0
    for rc in pack.release_classes:
        if ctx.remaining_s() <= 0:
            break
        dates = parse_days(rc.dates)
        if dates.size == 0:
            ctx.note(f"release:{rc.name}",
                     f"no dates on the pack (cadence {rc.cadence}, source {rc.source or 'none'})")
            continue
        for sym in [s.upper() for s in pack.executable_instruments][:6]:
            bars = ctx.bars(sym, "H1")
            if bars is None:
                ctx.note(f"bars:{sym}", "no H1 tape on this box")
                continue
            res = event_effect(bars, dates, horizon=2, rng=ctx.rng(f"{rc.name}:{sym}"),
                               eras=_eras_for(pack, bars))
            res.update({"release": rc.name, "symbol": sym})
            out.append(res)
            if res.get("significant"):
                did, created = ctx.record(
                    mechanism=f"{pack.code}_release_{_tok(rc.name)}_reaction",
                    source_id=f"release:{_tok(rc.name)}", source_type="calendar",
                    actor=f"{pack.name} hedgers and macro books that must mark to the "
                          f"{rc.name} print",
                    constraint=f"the {rc.name} print lands on a published {rc.cadence} calendar "
                               f"and cannot be traded before it",
                    economic_rationale=f"scheduled {rc.name} releases reprice {sym}",
                    assets=[sym], horizons=["intraday"], sessions=["all"],
                    regimes=["unconditional"],
                    required_data=[rc.actual_series or f"{rc.name} actual (absent)",
                                   rc.expected_series or f"{rc.name} expectation (absent)"],
                    pit_requirements=["release timestamp", "revision history"],
                    novelty=0.5, confidence=0.5,
                    falsifier=f"the {rc.name} reaction on {sym} does not clear the matched "
                              f"weekday+hour control",
                    payload={"reading": res, "release": rc.name, "source": rc.source})
                n += int(created or did != "dry-run")
    measured = [r for r in out if r.get("verdict") == "MEASURED"]
    return {"outcome": OK if measured else UNMEASURED, "discoveries": n,
            "releases": len(pack.release_classes), "measured": len(measured),
            "why": "" if measured else "no release class produced a measurable study",
            "readings": measured[:12]}


def generic_calendar_settlement(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """Settlement and fixing conventions as WINDOWS, with four negative controls.

    The controls are the whole point and they are named in the result: non-convention days (the
    matched control), randomised dates (the permutation null), adjacent days (the placebo that
    catches a roll), and OTHER CURRENCIES -- the same window on an instrument that does not carry
    this country's currency, which is the control that separates a settlement flow from a
    time-of-day effect the whole tape shares.
    """
    if not pack.settlement_conventions and not pack.fixing_conventions:
        ctx.note("settlement_conventions", "the pack declares no settlement or fixing convention")
        return {"outcome": UNMEASURED, "why": "no conventions declared"}
    reg = universe()
    cur = str(pack.currency).upper()
    own = [s.upper() for s in pack.executable_instruments if cur in s.upper()]
    other = [s for s in _reaction_set(pack, reg) if cur not in s.upper()][:3]
    if not own:
        own = [s.upper() for s in pack.executable_instruments]
    rows: list[dict[str, Any]] = []
    n = 0
    for rule in pack.settlement_conventions:
        if ctx.remaining_s() <= 0:
            break
        for sym in own[:4]:
            bars = ctx.bars(sym, "H1")
            if bars is None:
                ctx.note(f"bars:{sym}", "no H1 tape on this box")
                continue
            days = bar_days(bars)
            lo, hi = days.min(), days.max()
            conv = settlement_days(rule, pack, lo, hi)
            if conv.size == 0:
                ctx.note(f"settlement:{rule.name}",
                         f"the rule produced no day inside {lo}..{hi}")
                continue
            win = parse_hhmm(rule.window_utc[0]), parse_hhmm(rule.window_utc[1])
            hours = ((win[0][0] * 60 + win[0][1], win[1][0] * 60 + win[1][1])
                     if win[0] is not None and win[1] is not None else None)
            res = event_effect(bars, conv, horizon=1, hours=hours,
                               rng=ctx.rng(f"{rule.name}:{sym}"), eras=_eras_for(pack, bars))
            res.update({"convention": rule.name, "symbol": sym,
                        "n_convention_days": int(conv.size)})
            placebos: dict[str, Any] = {}
            for alt in other:
                ab = ctx.bars(alt, "H1")
                if ab is None:
                    continue
                pl = event_effect(ab, conv, horizon=1, hours=hours,
                                  rng=ctx.rng(f"{rule.name}:{alt}"),
                                  n_perm=max(50, N_PERM // 4))
                placebos[alt] = {"diff": pl.get("diff"), "p_perm": pl.get("p_perm"),
                                 "verdict": pl.get("verdict")}
            res["other_currency_placebo"] = placebos
            res["controls"] = ["non-convention matched days", "randomised dates",
                               "adjacent days", "other currencies"]
            rows.append(res)
            if res.get("significant"):
                did, created = ctx.record(
                    mechanism=f"{pack.code}_{_tok(rule.name)}_settlement_flow",
                    source_id=f"settlement:{_tok(rule.name)}", source_type="calendar",
                    actor=f"{pack.name} corporates and their settlement banks",
                    constraint=f"the {rule.name} convention forces the transaction on a dated "
                               f"calendar ({rule.kind}), rolled {rule.roll} off closures",
                    economic_rationale=f"a dated settlement convention concentrates {cur} demand "
                                       f"into {rule.window_utc[0] or 'the day'}",
                    assets=[sym], horizons=["intraday"], sessions=["all"],
                    regimes=["unconditional"],
                    required_data=["the national holiday table", "the convention's roll rule"],
                    pit_requirements=["the calendar is knowable in advance"],
                    novelty=0.55, confidence=0.5,
                    falsifier=f"the {rule.name} effect survives on an instrument carrying no "
                              f"{cur} leg, which would make it a time-of-day effect",
                    payload={"reading": res, "convention": rule.name, "kind": rule.kind})
                n += int(created or did != "dry-run")
    for fx in pack.fixing_conventions:
        if ctx.remaining_s() <= 0:
            break
        hhmm = parse_hhmm(fx.time_utc)
        if hhmm is None:
            ctx.note(f"fixing:{fx.name}", f"time_utc {fx.time_utc!r} is not HH:MM")
            continue
        for sym in (list(fx.instruments) or own)[:3]:
            bars = ctx.bars(str(sym).upper(), "M15") or ctx.bars(str(sym).upper(), "H1")
            if bars is None:
                ctx.note(f"bars:{sym}", "no M15 or H1 tape on this box")
                continue
            end_m = (hhmm[0] * 60 + hhmm[1] + max(5, int(fx.window_minutes))) % (24 * 60)
            res = window_effect(bars, fx.time_utc, f"{end_m // 60:02d}:{end_m % 60:02d}",
                                eras=_eras_for(pack, bars))
            res.update({"fixing": fx.name, "symbol": str(sym).upper(), "dst_rule": fx.dst_rule})
            rows.append(res)
    measured = [r for r in rows if r.get("verdict") == "MEASURED"]
    return {"outcome": OK if measured else UNMEASURED, "discoveries": n,
            "conventions": len(pack.settlement_conventions),
            "fixings": len(pack.fixing_conventions), "measured": len(measured),
            "why": "" if measured else "no convention produced a measurable window",
            "readings": measured[:12]}


def generic_holiday_liquidity(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """What the country's OWN closure does to instruments that stay open.

    MECHANISM REQUIRED, and this one has it: when the local market is shut, the participants who
    normally absorb local flow are absent, so the same order meets a thinner book. The claim is
    therefore about ABSOLUTE MOVE and spread, not about direction -- a signed holiday effect is
    almost always a calendar artefact, and this miner does not record one.
    """
    closed = pack.holidays_rule
    if not closed.dates and not closed.fixed_md:
        ctx.note("holidays_rule", "the pack declares no holiday table or recurring rule")
        return {"outcome": UNMEASURED, "why": "no holiday table"}
    rows: list[dict[str, Any]] = []
    n = 0
    for sym in [s.upper() for s in pack.executable_instruments][:6]:
        if ctx.remaining_s() <= 0:
            break
        bars = ctx.bars(sym, "H1")
        if bars is None:
            ctx.note(f"bars:{sym}", "no H1 tape on this box")
            continue
        days = bar_days(bars)
        hol = holiday_days(closed, days.min(), days.max())
        weekly = set(closed.weekly_closed)
        hol = hol[~np.isin(weekday_of(hol), np.array(list(weekly) or [-1], dtype="int64"))]
        if hol.size == 0:
            ctx.note(f"holidays:{sym}", "no non-weekend closure inside the tape's span")
            continue
        res = event_effect(bars, hol, horizon=1, rng=ctx.rng(sym), eras=_eras_for(pack, bars))
        res["symbol"] = sym
        res["mechanism_claim"] = ("the local absorbers are absent, so the same order meets a "
                                  "thinner book: the claim is on |move| and spread, not direction")
        rows.append(res)
        ratio = res.get("abs_ratio")
        if res.get("verdict") == "MEASURED" and isinstance(ratio, float) and ratio > 1.0:
            did, created = ctx.record(
                mechanism=f"{pack.code}_domestic_holiday_thin_book",
                source_id="holidays", source_type="calendar",
                actor=f"{pack.name} domestic market makers and banks, absent on national closures",
                constraint="a national closure removes the local absorbers while the instrument "
                           "keeps trading offshore",
                economic_rationale="fewer absorbers means a larger price impact per unit of "
                                   "order flow; the observable is the absolute move, not a sign",
                assets=[sym], horizons=["intraday"], sessions=["all"], regimes=["unconditional"],
                required_data=["the national holiday table"],
                pit_requirements=["the holiday calendar is knowable in advance"],
                novelty=0.5, confidence=0.45,
                falsifier="the absolute-move ratio on closures is not above 1 against the "
                          "matched weekday+hour control",
                payload={"reading": res, "n_holidays": int(hol.size)})
            n += int(created or did != "dry-run")
    measured = [r for r in rows if r.get("verdict") == "MEASURED"]
    return {"outcome": OK if measured else UNMEASURED, "discoveries": n,
            "measured": len(measured),
            "why": "" if measured else "no instrument carried a measurable closure study",
            "readings": measured[:8]}


def generic_session_microstructure(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """The country's own session windows, in UTC, on the tape the desk already holds."""
    windows = list(pack.session_windows)
    if not windows:
        for ex in pack.exchanges:
            if parse_hhmm(ex.open_utc) and parse_hhmm(ex.close_utc):
                windows.append(SessionWindow(name=f"{ex.name}_cash", start_utc=ex.open_utc,
                                             end_utc=ex.close_utc))
    if not windows:
        ctx.note("session_windows", "the pack declares no session window and no exchange hours")
        return {"outcome": UNMEASURED, "why": "no session windows"}
    rows: list[dict[str, Any]] = []
    n = 0
    for win in windows:
        if ctx.remaining_s() <= 0:
            break
        for sym in [s.upper() for s in pack.executable_instruments][:5]:
            bars = ctx.bars(sym, "H1")
            if bars is None:
                ctx.note(f"bars:{sym}", "no H1 tape on this box")
                continue
            res = window_effect(bars, win.start_utc, win.end_utc, eras=_eras_for(pack, bars))
            res.update({"session": win.name, "symbol": sym})
            rows.append(res)
            ratio = res.get("abs_ratio")
            if res.get("verdict") == "MEASURED" and isinstance(ratio, float) and ratio > 1.2:
                did, created = ctx.record(
                    mechanism=f"{pack.code}_{_tok(win.name)}_session_concentration",
                    source_id=f"session:{_tok(win.name)}", source_type="microstructure",
                    actor=f"{pack.name} onshore participants, active only in their own session",
                    constraint="an onshore book can only transact while its own market is open",
                    economic_rationale=f"the {win.name} window carries a disproportionate share "
                                       f"of {sym}'s daily absolute move",
                    assets=[sym], horizons=["intraday"], sessions=[_tok(win.name)],
                    regimes=["unconditional"], required_data=["H1 bars"],
                    pit_requirements=["bar timestamps in UTC"],
                    novelty=0.4, confidence=0.5,
                    falsifier=f"the {win.name} window's absolute move is not above the same "
                              f"days' other bars",
                    payload={"reading": res, "window_utc": [win.start_utc, win.end_utc]})
                n += int(created or did != "dry-run")
    measured = [r for r in rows if r.get("verdict") == "MEASURED"]
    return {"outcome": OK if measured else UNMEASURED, "discoveries": n,
            "windows": len(windows), "measured": len(measured),
            "why": "" if measured else "no window produced a measurable reading",
            "readings": measured[:12]}


def generic_positioning(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """Speculative positioning against the country's own instruments.

    COT when the CFTC publishes this currency, and the pack says under which symbol. When it does
    not, the answer is UNMEASURED plus a DATASET DISCOVERY naming the local positioning source
    the pack declares -- an absent series is a thing to acquire, not a question to drop.
    """
    key = str(pack.cot_currency or "").upper()
    series = cot_series(key) if key else None
    if series is None:
        ctx.note("positioning",
                 f"cot_currency {key or 'not declared'}: no row in {COT_JSON.name}; the local "
                 f"sources the pack names are {list(pack.positioning_sources) or 'none'}")
        n = 0
        for src in pack.positioning_sources:
            did, created = ctx.record(
                mechanism=f"{pack.code}_positioning_dataset_gap",
                source_id=f"dataset:{_tok(src)}", source_type="dataset",
                actor=f"{pack.name} leveraged and commercial participants",
                constraint="crowded positioning must be unwound into the same liquidity that "
                           "absorbed it",
                economic_rationale=f"{src} publishes the country's own positioning; it is not on "
                                   f"this box, so the mechanism is unaskable until it is",
                assets=list(pack.executable_instruments[:3]), horizons=["multi_day"],
                sessions=["all"], regimes=["unconditional"], required_data=[src],
                pit_requirements=["publication date, not reference date"],
                novelty=0.6, confidence=0.3,
                falsifier="once acquired, positioning extremes do not precede reversals",
                payload={"acquire": src, "why": "the country has no CFTC row"})
            n += int(created or did != "dry-run")
        return {"outcome": UNMEASURED, "discoveries": n,
                "why": f"no COT row for {key or 'an undeclared currency'}",
                "dataset_discoveries": n}
    rows: list[dict[str, Any]] = []
    n = 0
    for sym in [s.upper() for s in pack.executable_instruments][:5]:
        if ctx.remaining_s() <= 0:
            break
        bars = ctx.bars(sym, "D1") or ctx.bars(sym, "H1")
        if bars is None:
            ctx.note(f"bars:{sym}", "no D1 or H1 tape on this box")
            continue
        x, y = align_daily(series, bars, horizon=5)
        res = corr_with_null(x, y, rng=ctx.rng(sym))
        res.update({"symbol": sym, "series": series.name})
        rows.append(res)
        if res.get("significant"):
            did, created = ctx.record(
                mechanism=f"{pack.code}_positioning_extreme_reversal",
                source_id=f"positioning:{_tok(series.name)}", source_type="positioning",
                actor=f"{pack.name} leveraged speculative accounts",
                constraint="a crowded book must be unwound into the liquidity that absorbed it",
                economic_rationale=f"net speculative positioning in {sym} predicts its forward "
                                   f"return",
                assets=[sym], horizons=["multi_day"], sessions=["all"],
                regimes=["unconditional"], required_data=[series.name],
                pit_requirements=["knowable_at, never as_of"], novelty=0.45, confidence=0.5,
                falsifier=f"the positioning-forward-return correlation on {sym} does not clear "
                          f"a circular-block null",
                payload={"reading": res})
            n += int(created or did != "dry-run")
    measured = [r for r in rows if r.get("verdict") == "MEASURED"]
    return {"outcome": OK if measured else UNMEASURED, "discoveries": n,
            "series": series.name, "measured": len(measured),
            "why": "" if measured else "the COT series aligned with no instrument's tape",
            "readings": measured[:8]}


def generic_carry_funding(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """The rate differential, when the pack names both legs and this box holds them."""
    dom = str(pack.series.get("policy_rate") or pack.central_bank.policy_rate_series or "")
    foreign = str(pack.series.get("foreign_policy_rate") or "")
    a = ctx.series(dom) if dom else None
    b = ctx.series(foreign) if foreign else None
    if a is None or b is None:
        ctx.note("carry", f"rate differential needs both legs: domestic "
                          f"{dom or 'not declared'} "
                          f"({'present' if a is not None else 'absent'}), foreign "
                          f"{foreign or 'not declared'} "
                          f"({'present' if b is not None else 'absent'})")
        return {"outcome": UNMEASURED, "why": "one or both rate legs absent"}
    common = np.intersect1d(a.dates, b.dates)
    if common.size < 60:
        ctx.note("carry", f"only {int(common.size)} common dated observations across the two legs")
        return {"outcome": UNMEASURED, "why": "too few common observations"}
    diff = DataSeries(
        name=f"carry:{dom}-{foreign}", dates=common,
        values=(a.values[np.searchsorted(a.dates, common)]
                - b.values[np.searchsorted(b.dates, common)]))
    rows: list[dict[str, Any]] = []
    n = 0
    for sym in [s.upper() for s in pack.executable_instruments][:5]:
        bars = ctx.bars(sym, "D1") or ctx.bars(sym, "H1")
        if bars is None:
            ctx.note(f"bars:{sym}", "no D1 or H1 tape on this box")
            continue
        x, y = align_daily(diff, bars, horizon=20)
        res = corr_with_null(x, y, rng=ctx.rng(sym))
        res.update({"symbol": sym, "series": diff.name})
        rows.append(res)
        if res.get("significant"):
            did, created = ctx.record(
                mechanism=f"{pack.code}_rate_differential_carry",
                source_id=f"carry:{_tok(dom)}", source_type="macro",
                actor=f"{pack.name} hedged foreign investors and the banks funding them",
                constraint="a hedged position pays the differential every roll, whatever the "
                           "spot view",
                economic_rationale=f"the {dom} - {foreign} differential prices the forward and "
                                   f"therefore the hedged return on {sym}",
                assets=[sym], horizons=["multi_day"], sessions=["all"],
                regimes=["unconditional"], required_data=[dom, foreign],
                pit_requirements=["series publication dates"], novelty=0.4, confidence=0.5,
                falsifier=f"the differential's correlation with {sym}'s forward return does not "
                          f"clear a circular-block null",
                payload={"reading": res})
            n += int(created or did != "dry-run")
    measured = [r for r in rows if r.get("verdict") == "MEASURED"]
    return {"outcome": OK if measured else UNMEASURED, "discoveries": n,
            "series": diff.name, "measured": len(measured),
            "why": "" if measured else "the differential aligned with no instrument's tape",
            "readings": measured[:8]}


_FLOW_KEYS: tuple[str, ...] = ("trade_balance", "exports", "imports", "current_account", "pmi",
                               "industrial_production")


def generic_corporate_flow(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """The export/import cycle against the currency, with a CAUSAL CARD per reading.

    The card is not decoration: a trade-balance correlation with no actor, no constraint and no
    counterparty is a statistic, and the desk's compiler refuses a discovery that cannot say who
    was forced to do what. Every row here names the exporter, the invoice, and the bank.
    """
    loaded = {k: ctx.series(str(pack.series.get(k) or "")) for k in _FLOW_KEYS
              if pack.series.get(k)}
    have: dict[str, DataSeries] = {k: v for k, v in loaded.items() if v is not None}
    missing = [k for k in _FLOW_KEYS if k not in have]
    if not have:
        ctx.note("corporate_flow",
                 f"none of {list(_FLOW_KEYS)} is declared on the pack's `series` and present on "
                 f"this box")
        return {"outcome": UNMEASURED, "why": "no trade or export series"}
    for k in missing:
        ctx.note("corporate_flow", f"{k}: not declared or not on this box")
    cur = str(pack.currency).upper()
    syms = [s.upper() for s in pack.executable_instruments if cur in s.upper()][:4] or \
           [s.upper() for s in pack.executable_instruments][:4]
    rows: list[dict[str, Any]] = []
    n = 0
    for key, series in have.items():
        if ctx.remaining_s() <= 0:
            break
        for sym in syms:
            bars = ctx.bars(sym, "D1") or ctx.bars(sym, "H1")
            if bars is None:
                ctx.note(f"bars:{sym}", "no D1 or H1 tape on this box")
                continue
            x, y = align_daily(series, bars, horizon=20)
            res = corr_with_null(x, y, rng=ctx.rng(f"{key}:{sym}"))
            res.update({"symbol": sym, "series": series.name, "flow": key})
            rows.append(res)
            if res.get("significant"):
                did, created = ctx.record(
                    mechanism=f"{pack.code}_{_tok(key)}_repatriation_flow",
                    source_id=f"flow:{_tok(key)}", source_type="macro",
                    actor=f"{pack.name} exporters and importers, and the banks that settle their "
                          f"invoices",
                    constraint="an invoice denominated in a foreign currency must be converted; "
                               "the conversion is not discretionary and follows the shipment",
                    counterparty=f"the {pack.name} banking system's corporate desks",
                    economic_rationale=f"the {key} cycle is the size of the conversion that must "
                                       f"pass through {sym}",
                    assets=[sym], horizons=["multi_day"], sessions=["all"],
                    regimes=["unconditional"], required_data=[series.name],
                    pit_requirements=["publication lag of the national statistic"],
                    novelty=0.5, confidence=0.5,
                    falsifier=f"the {key} correlation with {sym} does not clear a circular-block "
                              f"null, or reverses in another era",
                    payload={"reading": res, "causal_card": {
                        "actor": "exporters and importers", "constraint": "invoice conversion",
                        "observable": series.name, "flow": key, "asset": sym}})
                n += int(created or did != "dry-run")
    measured = [r for r in rows if r.get("verdict") == "MEASURED"]
    return {"outcome": OK if measured else UNMEASURED, "discoveries": n,
            "series": sorted(have), "missing": missing, "measured": len(measured),
            "why": "" if measured else "no flow series aligned with an instrument's tape",
            "readings": measured[:8]}


def generic_institutional_flow(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """Public allocation evidence: the country's own reserve, pension and insurance managers.

    Nothing here is measured from a price. A sovereign fund's rebalancing band is PUBLISHED, and
    the discovery this miner records is the SOURCE plus the constraint it documents -- a lead for
    the deepening worker and the acquisition lane, honestly marked as unmeasured until the series
    lands, rather than a correlation invented to fill the slot.
    """
    if not pack.institutional_flow_sources:
        ctx.note("institutional_flow",
                 "the pack declares no public allocation source (reserve manager, pension fund, "
                 "insurer)")
        return {"outcome": UNMEASURED, "why": "no institutional sources declared"}
    n = 0
    for src in pack.institutional_flow_sources:
        did, created = ctx.record(
            mechanism=f"{pack.code}_institutional_allocation_band",
            source_id=f"institution:{_tok(src)}", source_type="institutional",
            actor=f"{src}, a {pack.name} public allocator with a published mandate",
            constraint="a published allocation band forces a rebalance when a market move takes "
                       "the portfolio outside it, on the fund's own calendar and not on a view",
            counterparty="the dealers who must warehouse the rebalance",
            economic_rationale=f"{src}'s band and reporting calendar are public, so the DATE of "
                               f"the forced transaction is knowable in advance",
            assets=list(pack.executable_instruments[:3]), horizons=["multi_day"],
            sessions=["all"], regimes=["unconditional"],
            required_data=[f"{src} holdings or allocation disclosures"],
            pit_requirements=["disclosure date, never the reference quarter"],
            novelty=0.6, confidence=0.4,
            falsifier="the fund's disclosures show no band and no calendar, so nothing is forced",
            payload={"source": src, "status": "lead: the series is not on this box"})
        n += int(created or did != "dry-run")
        ctx.note("institutional_flow", f"{src}: holdings series not on this box; recorded as a "
                                       f"lead for acquisition")
    return {"outcome": OK, "discoveries": n, "sources": list(pack.institutional_flow_sources),
            "why": "recorded as acquisition leads; no holdings series is on this box"}


def generic_equity_mechanics(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """The country's index: its open, its close, its gap, and what it inherits from abroad.

    The inheritance half is a TRANSMISSION SEED as well as a domestic reading -- the overnight
    gap of an Asian index is largely the US session it slept through, and saying so out loud is
    how the transmission engine gets a channel to measure instead of a correlation to admire.
    """
    idx = [s.upper() for ex in pack.exchanges for s in ex.index_symbols]
    if not idx:
        ctx.note("equity_mechanics", "the pack declares no exchange index symbol")
        return {"outcome": UNMEASURED, "why": "no index symbol"}
    reg = universe()
    rows: list[dict[str, Any]] = []
    n = 0
    for sym in idx[:3]:
        if ctx.remaining_s() <= 0:
            break
        bars = ctx.bars(sym, "H1")
        if bars is None:
            ctx.note(f"bars:{sym}", "no H1 tape on this box")
            continue
        eras = _eras_for(pack, bars)
        for ex in pack.exchanges:
            if sym not in {s.upper() for s in ex.index_symbols}:
                continue
            if parse_hhmm(ex.open_utc) and parse_hhmm(ex.close_utc):
                res = window_effect(bars, ex.open_utc, ex.close_utc, eras=eras)
                res.update({"symbol": sym, "leg": "cash_session", "exchange": ex.name})
                rows.append(res)
        for lead in ("US500", "GER40"):
            if reg and lead not in reg:
                continue
            lb = ctx.bars(lead, "H1")
            if lb is None:
                ctx.note(f"bars:{lead}", "no H1 tape for the offshore lead")
                continue
            res = _lead_reading(lb, bars, ctx.rng(f"{lead}:{sym}"))
            res.update({"symbol": sym, "lead": lead, "leg": "offshore_inheritance"})
            rows.append(res)
            if res.get("significant"):
                ctx.seed_transmission(to_country=pack.code, asset=sym, source_symbol=lead,
                                      actor="offshore index investors and the local open auction",
                                      constraint="the local cash market cannot trade while it is "
                                                 "shut, so the offshore session arrives at once "
                                                 "in the open",
                                      flow="overnight inheritance", lag_days=1.0,
                                      evidence=res)
                did, created = ctx.record(
                    mechanism=f"{pack.code}_index_offshore_inheritance",
                    source_id=f"equity:{sym}", source_type="cross_asset",
                    actor=f"{pack.name} index participants at the open auction",
                    constraint="the local cash market is shut while the offshore session trades; "
                               "everything it missed arrives in one auction",
                    economic_rationale=f"{lead}'s session predicts {sym}'s next local session",
                    assets=[sym], horizons=["overnight"], sessions=["all"],
                    regimes=["unconditional"], required_data=[f"{lead} H1", f"{sym} H1"],
                    pit_requirements=["bar timestamps in UTC"], novelty=0.35, confidence=0.55,
                    falsifier=f"{lead}'s session carries no predictive content for {sym} once "
                              f"{sym}'s own lags are held fixed",
                    payload={"reading": res, "lead": lead})
                n += int(created or did != "dry-run")
    measured = [r for r in rows if r.get("verdict") == "MEASURED"]
    return {"outcome": OK if measured else UNMEASURED, "discoveries": n,
            "indices": idx, "measured": len(measured),
            "why": "" if measured else "no index carried a measurable reading",
            "readings": measured[:8]}


def _lead_reading(lead: Bars, target: Bars, rng: np.random.Generator) -> dict[str, Any]:
    """One offshore lead against one local target on a shared daily grid."""
    ld, td = bar_days(lead), bar_days(target)
    lr, tr = log_returns(lead.close), forward_returns(target.close, 1)
    uniq = np.intersect1d(np.unique(ld), np.unique(td))
    if uniq.size < 60:
        return {"verdict": "POORLY_MEASURED", "n": int(uniq.size),
                "why": "fewer than 60 common days"}
    lead_daily = np.array([float(np.nansum(lr[ld == d])) for d in uniq], dtype="float64")
    tgt_daily = np.array([float(np.nansum(tr[td == d])) for d in uniq], dtype="float64")
    return corr_with_null(lead_daily[:-1], tgt_daily[1:], rng=rng)


def generic_derivatives_expiry(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """Expiry days as an event study, from the exchange's declared rule or its date list."""
    rules = [ex for ex in pack.exchanges if ex.expiry_dates or ex.expiry_rule]
    if not rules:
        ctx.note("derivatives_expiry", "no exchange declares an expiry rule or date list")
        return {"outcome": UNMEASURED, "why": "no expiry rule"}
    rows: list[dict[str, Any]] = []
    n = 0
    for ex in rules:
        dates = parse_days(ex.expiry_dates)
        if dates.size == 0:
            ctx.note(f"expiry:{ex.name}",
                     f"rule {ex.expiry_rule!r} declared with no dates; the rule is not yet "
                     f"expanded into a calendar on this pack")
            continue
        for sym in [s.upper() for s in ex.index_symbols][:2]:
            bars = ctx.bars(sym, "H1")
            if bars is None:
                ctx.note(f"bars:{sym}", "no H1 tape on this box")
                continue
            res = event_effect(bars, dates, horizon=1, rng=ctx.rng(f"{ex.name}:{sym}"),
                               eras=_eras_for(pack, bars))
            res.update({"exchange": ex.name, "symbol": sym, "rule": ex.expiry_rule})
            rows.append(res)
            if res.get("significant"):
                did, created = ctx.record(
                    mechanism=f"{pack.code}_{_tok(ex.name)}_expiry_pin",
                    source_id=f"expiry:{_tok(ex.name)}", source_type="calendar",
                    actor="option and futures books that must settle against the expiry print",
                    constraint=f"{ex.expiry_rule or 'the expiry rule'} fixes the settlement "
                               f"moment; a hedge must be unwound into it",
                    economic_rationale=f"expiry concentrates hedging flow into {sym}",
                    assets=[sym], horizons=["intraday"], sessions=["all"],
                    regimes=["unconditional"], required_data=["the exchange expiry calendar"],
                    pit_requirements=["the expiry calendar is knowable in advance"],
                    novelty=0.5, confidence=0.5,
                    falsifier="the expiry effect does not clear the matched weekday+hour control",
                    payload={"reading": res})
                n += int(created or did != "dry-run")
    measured = [r for r in rows if r.get("verdict") == "MEASURED"]
    return {"outcome": OK if measured else UNMEASURED, "discoveries": n,
            "measured": len(measured),
            "why": "" if measured else "no expiry calendar produced a measurable study",
            "readings": measured[:8]}


def generic_failure(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """This country's own deaths, routed into the descendant the death JUSTIFIES.

    A death is exploited, not filed: WRONG_DIRECTION justifies an inverse, COST_KILLED an
    execution variant, REGIME_SPECIFIC a conditioned child. NO_EDGE and REDUNDANT justify
    nothing, and inventing a descendant for them is search waste wearing a lineage -- so they are
    counted and left alone. `graveyard_resurrection` is asked first when it is on this box.
    """
    if ctx.conn is None:
        return {"outcome": UNMEASURED, "why": "no registry connection"}
    route = {"wrong_direction": "INVERSE", "cost_killed": "EXECUTION_VARIANT",
             "regime_specific": "REGIME_CONDITION", "wrong_horizon": "HORIZON_TRANSFER",
             "wrong_asset": "ASSET_TRANSFER", "execution_killed": "EXECUTION_VARIANT",
             "unstable": "RESIDUALIZATION"}
    tag = ctx.tag
    rows = [r for r in R.candidates(status="judged", limit=400, conn=ctx.conn)
            if str(r.get("generator") or "").lower().startswith(tag)
            or str(r.get("symbol") or "").upper() in {s.upper()
                                                      for s in pack.executable_instruments}]
    barren = 0
    n = 0
    for r in rows[:40]:
        cls = str(r.get("failure_class") or "").lower()
        op = route.get(cls)
        if op is None:
            barren += 1
            continue
        did, created = ctx.record(
            mechanism=f"{pack.code}_descendant_{_tok(op)}",
            source_id=f"failure:{r.get('id')}", source_type="failure",
            parent_ids=[str(r.get("discovery_id") or r.get("id") or "")],
            actor=str(r.get("economic_actor") or f"{pack.name} participants"),
            constraint=str(r.get("constraint_text") or "the parent's constraint, unchanged"),
            economic_rationale=f"the parent died {cls}, which JUSTIFIES {op} and nothing else",
            assets=[str(r.get("symbol") or "")], horizons=[str(r.get("horizon") or "intraday")],
            sessions=[str(r.get("session") or "all")],
            regimes=[str(r.get("regime") or "unconditional")],
            required_data=["the parent's own inputs"], pit_requirements=["unchanged"],
            novelty=0.4, confidence=0.4,
            falsifier=f"the {op} descendant dies of the same cause as its parent",
            payload={"parent": r.get("id"), "failure_class": cls, "operator": op})
        n += int(created or did != "dry-run")
    mod = desk_module("graveyard_resurrection")
    if mod is None:
        ctx.note("graveyard_resurrection", "the organ is not on this box; only the registry's own "
                                           "judged rows were routed")
    return {"outcome": OK if rows else UNMEASURED, "discoveries": n, "judged_rows": len(rows),
            "barren": barren, "graveyard_organ": mod is not None,
            "why": "" if rows else "the registry holds no judged row for this country"}


def generic_residual(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """What the desk's model does not explain, for this country's instruments.

    Delegated to `shadow_discovery` when it is on this box -- actual minus model is its question
    and two answers to one question is how two organs come to disagree. Absent, the miner says
    so; it does NOT substitute a home-grown residual that nothing else would recognise.
    """
    mod = desk_module("shadow_discovery")
    if mod is None:
        ctx.note("shadow_discovery", "the organ is not on this box; the country's residual is "
                                     "unmeasured rather than re-derived here")
        return {"outcome": UNMEASURED, "why": "shadow_discovery is not on this box"}
    fn = getattr(mod, "residual_inputs", None)
    if not callable(fn):
        ctx.note("shadow_discovery", "residual_inputs is absent from the organ's surface")
        return {"outcome": UNMEASURED, "why": "no residual_inputs entry point"}
    try:
        doc = fn()
    except Exception as exc:
        ctx.note("shadow_discovery", f"{type(exc).__name__}: {exc}")
        return {"outcome": UNMEASURED, "why": f"{type(exc).__name__}"}
    syms = {s.upper() for s in pack.executable_instruments}
    rows = [r for v in (doc or {}).values() if isinstance(v, list) for r in v
            if isinstance(r, dict) and str(r.get("sym") or r.get("symbol") or "").upper() in syms]
    n = 0
    for r in rows[:20]:
        did, created = ctx.record(
            mechanism=f"{pack.code}_unexplained_residual",
            source_id="residual:shadow_discovery", source_type="residual",
            actor=f"{pack.name} participants the desk's factor model does not represent",
            constraint="a recurring residual means a real constraint the model has no term for",
            economic_rationale="actual minus model is the research target",
            assets=[str(r.get("sym") or r.get("symbol") or "")], horizons=["intraday"],
            sessions=["all"], regimes=["unconditional"],
            required_data=["the shadow ledger"], pit_requirements=["trade timestamps"],
            novelty=0.55, confidence=0.4,
            falsifier="the residual does not recur in a second window",
            payload={"row": r})
        n += int(created or did != "dry-run")
    return {"outcome": OK if rows else UNMEASURED, "discoveries": n, "rows": len(rows),
            "why": "" if rows else "the residual engine holds no row for this country's symbols"}


def generic_transfer(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """The twelve transformation miners applied to this country's own discoveries."""
    mod = desk_module("transformation_miners")
    if mod is None:
        ctx.note("transformation_miners", "the twelve are not on this box; the country's closure "
                                          "is unexpanded this pass")
        return {"outcome": UNMEASURED, "why": "transformation_miners is not on this box"}
    if ctx.conn is None:
        return {"outcome": UNMEASURED, "why": "no registry connection"}
    parents = [r for r in R.discoveries(state="INTERPRETED", limit=200, conn=ctx.conn)
               if str(r.get("generator") or "").lower().startswith(ctx.tag)]
    if not parents:
        return {"outcome": UNMEASURED, "why": "no INTERPRETED discovery for this country"}
    reg = universe()
    instruments: dict[str, list[str]] = {}
    for sym in pack.executable_instruments:
        klass = str((reg.get(sym) or {}).get("asset_class") or "unknown")
        instruments.setdefault(klass, []).append(sym.upper())
    try:
        tctx = mod.Context(instruments=instruments, conn=ctx.conn,
                           bars_available=lambda s, c: ctx.bars(s, c) is not None)
    except Exception as exc:
        ctx.note("transformation_miners", f"Context: {type(exc).__name__}: {exc}")
        return {"outcome": UNMEASURED, "why": f"Context {type(exc).__name__}"}
    children = 0
    for parent in parents[:20]:
        if ctx.remaining_s() <= 0:
            break
        try:
            out = mod.run_all(parent, tctx)
        except Exception as exc:
            ctx.note("transformation_miners", f"run_all: {type(exc).__name__}: {exc}")
            continue
        children += sum(len(v) for v in out.values())
    return {"outcome": OK, "parents": len(parents), "children": children, "discoveries": 0,
            "why": "children are compiled by the discovery compiler, not enqueued here"}


def generic_scouts(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """THE TEN SOURCE LAYERS, one scout each, and the country's coverage measured rather than
    asserted.

    NATIVE-LANGUAGE MINING IS REAL HERE, and the order is the point: NATIVE QUERIES built from
    the pack's own terminology, pointed at NATIVE SOURCE ROOTS, so what comes back is written by
    NATIVE AUTHORS in native terms -- translation happens AFTER retrieval, never before. An
    English query against an English index cannot reach the forum where a local desk explains its
    own settlement convention, and that is exactly the ground worth mining.

    AND A LAYER NOBODY HAS MAPPED IS A DISCOVERY OF ITS OWN. The ten layers are asked of every
    country whether or not anybody has thought about that country yet, so an UNMAPPED layer is
    recorded as an acquisition lead naming what is missing -- which is how coverage rises through
    the two conditions (`coverage_state`) rather than through five obvious sources being added.

    This miner STEERS; it does not crawl. `deep_forest_miner --region <cc>` when the forest knows
    this country, `world_frontier` otherwise, and the steer is recorded so the next pass can see
    whether it was taken.
    """
    if not pack.native_languages or not pack.terminology:
        ctx.note("scouts", "the pack declares no native language or no terminology; a native "
                           "query cannot be built from an empty dictionary")
        return {"outcome": UNMEASURED, "why": "no native terminology"}
    forest = desk_module("deep_forest_miner")
    supported = bool(forest is not None
                     and str(pack.code) in getattr(forest, "REGION_CLUSTER", {}))
    steer = (f"deep_forest_miner.py --region {pack.code}" if supported
             else "world_frontier (the forest does not know this country)")
    if forest is None:
        ctx.note("deep_forest_miner", "the organ is not on this box; the steer is recorded and "
                                      "not executed")
    coverage = coverage_state(pack.code, ctx.conn, pack=pack)
    inventory = layer_inventory(pack.code, pack=pack)
    n = 0
    queries = 0
    for layer in SOURCE_LAYERS:
        if ctx.remaining_s() <= 0:
            ctx.note("scouts", f"the miner's budget was spent before the {layer} layer")
            break
        rows = inventory[layer]
        state = coverage["layers"][layer]["state"]
        seeds = native_query_seeds(pack.code, layer, pack=pack)
        queries += len(seeds)
        if state == "ABSENT_DECLARED":
            ctx.note(f"scout:{layer}", f"declared ABSENT for {pack.name}: "
                                       f"{coverage['layers'][layer]['why']}")
            continue
        if state == "UNMAPPED":
            ctx.note(f"scout:{layer}", "no source and no declared absence; the layer is UNMAPPED "
                                       "and the country cannot be covered while it is")
        roots = [r for row in rows for r in (row.get("roots") or [])]
        did, created = ctx.record(
            mechanism=f"{pack.code}_scout_{layer}",
            source_id=f"scout:{layer}", source_type="scout",
            actor=f"the {pack.name} {layer.replace('_', ' ')} layer and the people who write it",
            constraint="a claim written in the native language of the market it describes is not "
                       "reachable by an English query against an English index",
            economic_rationale=f"native {layer} ground for {pack.name}: {len(rows)} declared "
                               f"source(s), state {state}, steered by {steer}",
            assets=list(pack.executable_instruments[:3]), horizons=["multi_day"],
            sessions=["all"], regimes=["unconditional"],
            required_data=[f"{layer} roots: {roots[:4] or 'none declared'}"],
            pit_requirements=["retrieval time and publication time of every document"],
            novelty=0.6, confidence=0.35,
            falsifier=f"the {layer} layer yields no claim naming a testable mechanism after a "
                      f"full crawl of its declared roots",
            payload={"layer": layer, "state": state, "roots": roots[:12], "steer": steer,
                     "languages": list(pack.native_languages),
                     "queries": [q["query"] for q in seeds[:20]],
                     "site_scoped": [q for row in seeds[:6] for q in row["site_scoped"]][:12],
                     "translate": "after retrieval only",
                     "expansion": "register every followed link as a source with its language"})
        n += int(created or did != "dry-run")
    untagged = inventory["UNTAGGED"]
    if untagged:
        ctx.note("scouts", f"{len(untagged)} declared source(s) carry no layer tag; they are "
                           f"UNTAGGED and count toward no layer")
    sf = desk_module("source_frontier")
    registered = 0
    if sf is not None and hasattr(sf, "register_source") and not ctx.dry_run:
        for layer in SOURCE_LAYERS:
            for row in inventory[layer][:4]:
                try:
                    sf.register_source(f"{ctx.tag}{layer}:{_tok(row['id'])}",
                                       url=(row.get("roots") or [""])[0], kind=layer,
                                       language=(pack.native_languages or ("",))[0],
                                       country=pack.code, conn=ctx.conn)
                    registered += 1
                except Exception as exc:
                    ctx.note("source_frontier", f"{type(exc).__name__}: {exc}")
                    break
    elif sf is None:
        ctx.note("source_frontier", "the organ is not on this box; sources are recorded as "
                                    "discoveries only")
    return {"outcome": OK, "discoveries": n, "steer": steer, "queries": queries,
            "layers": {k: coverage["layers"][k]["state"] for k in SOURCE_LAYERS},
            "coverage_state": coverage["state"], "coverage_why": coverage["why"],
            "layers_mapped": coverage["layers_mapped"], "untagged_sources": len(untagged),
            "sources_registered": registered, "forest_supports_country": supported}


#: Every generic miner, by name. A country pack is DATA PLUS OPTIONAL CUSTOM MINERS; this table
#: is what "the same depth as Japan" means operationally -- fifteen questions asked of every
#: country, whether or not anybody has thought about that country yet.
GENERIC_MINERS: dict[str, Callable[[CountryPack, LabCtx], dict[str, Any]]] = {
    "central_bank_surprise": generic_central_bank_surprise,
    "release_surprise": generic_release_surprise,
    "calendar_settlement": generic_calendar_settlement,
    "holiday_liquidity": generic_holiday_liquidity,
    "session_microstructure": generic_session_microstructure,
    "positioning": generic_positioning,
    "carry_funding": generic_carry_funding,
    "corporate_flow": generic_corporate_flow,
    "institutional_flow": generic_institutional_flow,
    "equity_mechanics": generic_equity_mechanics,
    "derivatives_expiry": generic_derivatives_expiry,
    "failure": generic_failure,
    "residual": generic_residual,
    "transfer": generic_transfer,
    "scouts": generic_scouts,
}

_ACTOR_FIELDS = tuple(ActorRow.__dataclass_fields__.values())
_DOMAIN_FIELDS = tuple(DomainRow.__dataclass_fields__.values())
_DATASET_FIELDS = tuple(DatasetRow.__dataclass_fields__.values())


# --------------------------------------------------------------------------- budgets and the run
def miner_budgets(names: Sequence[str], pool_s: float, yields: Sequence[Mapping[str, Any]],
                  tag: str, fixed: Sequence[str] = ()) -> dict[str, dict[str, Any]]:
    """Seconds per miner by MEASURED downstream yield, under two floors.

    Jeffreys rather than a raw ratio -- (independent_survivors + 0.5) / (generated + 1) -- so a
    miner that has produced nothing is not assumed useless and one lucky survivor does not crown
    a miner. Then the floors, and the order between them matters: every miner keeps at least
    MINER_FLOOR, and the miners with NO success ever keep COLD_SHARE *as a class*. A warm miner
    pushed below its floor still ran last pass; cold ground defunded to zero is never measured
    again, and therefore never stops looking worthless.
    """
    out: dict[str, dict[str, Any]] = {}
    if not names:
        return out
    by_gen = {str(r.get("generator") or "").lower(): r for r in yields}
    fixed_set = {n for n in fixed if n in names}
    steer = [n for n in names if n not in fixed_set]
    fixed_share = min(1.0, len(fixed_set) / float(len(names)))
    share_left = max(0.0, 1.0 - fixed_share)
    prior: dict[str, float] = {}
    cold: list[str] = []
    for name in names:
        row = by_gen.get(f"{tag}{name}".lower(), {})
        gen = float(row.get("generated") or 0.0)
        indep = float(row.get("independent_survivors") or 0.0)
        prior[name] = (indep + 0.5) / (gen + 1.0)
        if indep <= 0:
            cold.append(name)
    weight: dict[str, float] = ({n: fixed_share / len(fixed_set) for n in fixed_set}
                                if fixed_set else {})
    if steer:
        floor = min(MINER_FLOOR, share_left / len(steer))
        free = max(0.0, share_left - floor * len(steer))
        total = sum(prior[n] for n in steer)
        for n in steer:
            frac = (prior[n] / total) if total > 0 else (1.0 / len(steer))
            weight[n] = floor + free * frac
    cold_steer = [n for n in cold if n in weight and n not in fixed_set]
    warm = [n for n in weight if n not in cold_steer]
    have = sum(weight[n] for n in cold_steer)
    want = COLD_SHARE * sum(weight.values())
    if cold_steer and have < want:
        for n in cold_steer:
            weight[n] = (weight[n] * want / have) if have > 0 else want / len(cold_steer)
        rest = max(0.0, sum(weight.values()) - want)
        warm_have = sum(weight[n] for n in warm)
        for n in warm:
            weight[n] = (rest * weight[n] / warm_have) if warm_have > 0 else (
                rest / len(warm) if warm else 0.0)
    total_w = sum(weight.values()) or 1.0
    for name in names:
        w = weight.get(name, 0.0) / total_w
        out[name] = {"weight": round(w, 6),
                     "budget_s": round(max(MINER_FLOOR_S, pool_s * w), 3),
                     "prior": round(prior[name], 6), "cold": name in cold,
                     "fixed": name in fixed_set,
                     "why": (f"jeffreys prior {prior[name]:.3f} on generator_yield[{tag}{name}]"
                             + ("; COLD (no independent survivor ever), protected by the "
                                f"{COLD_SHARE:.0%} cold share" if name in cold else "")
                             + ("; fixed cost, not steerable" if name in fixed_set else ""))}
    return out


def load_custom_miners(pack: CountryPack) -> tuple[dict[str, Callable[[CountryPack, LabCtx],
                                                                     dict[str, Any]]], list[str]]:
    """The pack's `module:function` entries, resolved. An entry that does not resolve is NAMED
    and counted, never skipped: a custom miner that silently never runs is a country the desk
    believes it is mining and is not."""
    out: dict[str, Callable[[CountryPack, LabCtx], dict[str, Any]]] = {}
    problems: list[str] = []
    for entry in pack.custom_miners:
        mod_name, _, fn_name = str(entry).partition(":")
        if not mod_name or not fn_name:
            problems.append(f"custom miner {entry!r}: not a 'module:function' entry")
            continue
        try:
            mod = importlib.import_module(mod_name)
        except Exception as exc:
            problems.append(f"custom miner {entry!r}: import failed "
                            f"({type(exc).__name__}: {exc})")
            continue
        fn = getattr(mod, fn_name, None)
        if not callable(fn):
            problems.append(f"custom miner {entry!r}: {fn_name} is absent or not callable")
            continue
        out[f"custom:{fn_name}"] = fn
    return out, problems


def run_lab(pack: CountryPack, ctx: LabCtx, budget_s: float = 300.0,
            extra: Mapping[str, Callable[[CountryPack, LabCtx], dict[str, Any]]] | None = None
            ) -> dict[str, Any]:
    """One country's pass: the fifteen generic miners, then its own, inside `budget_s`.

    The generic set runs FIRST and always. That is what "every country gets the same depth" means
    in code: a country nobody has written a custom miner for still has its central bank, its
    settlement conventions, its holidays, its sessions, its positioning, its carry, its trade
    cycle, its index and its native-language ground asked about on every pass. Custom miners are
    the country's own additions on top, budgeted by the same measured ROI as the generic ones.
    """
    started = time.monotonic()
    ctx.deadline = started + float(budget_s)
    ctx.region_command = ctx.region_command or pack.region_command
    custom, custom_problems = load_custom_miners(pack)
    for row in custom_problems:
        ctx.note("custom_miners", row)
    # `extra` is the pack directory's own `miners.py MINERS`, handed in by the global OS. It is
    # merged UNDER the dotted entries so a pack that names the same miner both ways gets one.
    for name, fn in dict(extra or {}).items():
        custom.setdefault(f"custom:{name}", fn)
    names = [*GENERIC_MINERS, *custom]
    yields: Sequence[Mapping[str, Any]] = []
    if ctx.conn is not None:
        try:
            yields = R.generator_yields(conn=ctx.conn)
        except Exception as exc:
            ctx.note("generator_yields", f"{type(exc).__name__}: {exc}")
    budgets = miner_budgets(names, float(budget_s) * 0.95, yields, ctx.tag,
                            fixed=("central_bank_surprise", "calendar_settlement"))
    rows: list[dict[str, Any]] = []
    before = len(ctx.recorded)
    for name in names:
        chosen: Callable[[CountryPack, LabCtx], dict[str, Any]] | None = (
            GENERIC_MINERS.get(name) or custom.get(name))
        if chosen is None:
            continue
        fn = chosen
        share = float(budgets.get(name, {}).get("budget_s") or MINER_FLOOR_S)
        left = max(0.0, ctx.deadline - time.monotonic())
        rec: dict[str, Any] = {"miner": name, "budget_s": round(share, 3),
                               "why": str(budgets.get(name, {}).get("why") or ""),
                               "cold": bool(budgets.get(name, {}).get("cold"))}
        if left <= 0.0:
            rec.update({"outcome": SKIPPED, "seconds": 0.0, "discoveries": 0,
                        "note": f"the pass budget of {budget_s:.0f}s was spent first"})
            rows.append(rec)
            continue
        box = max(MINER_FLOOR_S, min(share, left))
        saved_deadline, saved_miner = ctx.deadline, ctx.miner
        ctx.miner = name
        ctx.deadline = time.monotonic() + box
        mark = len(ctx.recorded)
        t0 = time.monotonic()
        try:
            result = fn(pack, ctx)
            rec.update({k: v for k, v in dict(result).items() if k != "readings"})
            rec.setdefault("outcome", OK)
            rec["readings"] = list(dict(result).get("readings") or [])[:4]
        except Exception as exc:
            rec.update({"outcome": FAILED, "why": f"{type(exc).__name__}: {str(exc)[:300]}"})
            ctx.note(name, f"{type(exc).__name__}: {str(exc)[:200]}")
        rec["seconds"] = round(time.monotonic() - t0, 3)
        rec["recorded"] = len(ctx.recorded) - mark
        rec["overran_s"] = round(max(0.0, rec["seconds"] - box), 3)
        ctx.deadline, ctx.miner = saved_deadline, saved_miner
        rows.append(rec)
    seeds = list(ctx.transmission_seeds) + [
        {"from_country": pack.code, "to_country": s.to_country, "asset": s.asset,
         "actor": s.actor, "constraint": s.constraint, "flow": s.flow, "lag_days": s.lag_days,
         "source_series": s.source_series, "source_symbol": s.source_symbol, "era": s.era,
         "declared": True, "notes": s.notes}
        for s in pack.transmission_edges_seed]
    return {
        "at": _now(), "country": pack.code, "name": pack.name,
        "region_command": pack.region_command,
        "domestic": len(ctx.recorded) - before,
        "transmission_seeds": seeds,
        "unmeasured": list(ctx.unmeasured),
        "axis_proposals": list(ctx.axis_proposals),
        "miners": rows,
        "budgets": budgets,
        "seconds": round(time.monotonic() - started, 3),
        "budget_s": float(budget_s),
        "custom_miners": sorted(custom),
        "generic_miners": list(GENERIC_MINERS),
        "rule": RULE,
    }
