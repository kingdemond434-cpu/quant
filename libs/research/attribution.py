"""ATTRIBUTION AT BIRTH -- the ONE producer/region stamp every cell, discovery and candidate
carries, written by the creating organ and never inferred by a later sweep.

THE DEFECT THIS CLOSES (measured 2026-09-23 on the trading box). `PRODUCTIVITY_CENSUS.json`
attributed 3,663 of 3,862 unique cells to nobody and 33 of 58 certificates to nobody, so the
regional scoreboard read `Europe: 1,973 sources visited, 0 unique cells` -- not because Europe
produced nothing, but because the cells it DID produce could not be traced back. The lineage was
never missing: 26,199 of 27,307 candidates carry a `source_id` and 23,239 a `discovery_id`, and
`sources.country` knows the ground. Nothing joined them, because every reader was expected to
re-derive the join and each one derived a different answer.

THE SHAPE IS `desks/mt5/research/certificate_truth.py`'s. That module names ONE canonical
identity (`symbol|family|selector`), makes every store carry it AT BIRTH, and fails the fence on
a row created after the obligation date without it. This is the same law on a different axis:

    IDENTITY   certificate_truth.IDENTITY_FIELD   what was judged
    ATTRIBUTION this module                        who produced it, and from which region

ONE HELPER, NOT A CONVENTION. `attribute()` is the only rule. `libs/moat/registry.py` calls it
inside `enqueue_candidate` and `record_discovery` -- the two doors every cell and discovery comes
through -- so a producer that lands next month inherits the stamp without its author having read
this file. A later sweep can only ever recover what the lineage still holds; the stamp is written
while the row's creator still knows the answer.

THREE REGION STATES, AND THE DIFFERENCE MATTERS (L1.28a):

    <a region>       the producer, or the ground its evidence came from, is regional
    NOT_REGIONAL     the producer is a method or a desk organ that belongs to no region -- a
                     DECLARED verdict (`math:topology` is mathematics, not Japan), never a gap
    UNATTRIBUTABLE   nothing in the row or its lineage names a producer or a ground, with the
                     reason recorded so the denominator is honest rather than quietly smaller

Readers: `desks/mt5/research/attribution_census.py` (the hourly organ that measures coverage and
backfills what lineage still holds), `desks/mt5/research/productivity_census.py` (the regional
scoreboard, whose `_region_for` delegates here so there is one rule), and
`scripts/check_birth_obligations.py` (the fence clause that fails on a row born unstamped).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: The columns a stamped row carries. Named here so a reader never spells them itself.
PRODUCER_FIELD = "producer"
REGION_FIELD = "region"
ROUTE_FIELD = "attribution_route"

#: A row that genuinely cannot be attributed is EXCLUDED BY DECLARATION, never by silence.
UNATTRIBUTABLE = "UNATTRIBUTABLE"
#: The producer belongs to no region by construction. A verdict, not a gap.
NOT_REGIONAL = "NOT_REGIONAL"
UNMEASURED = "UNMEASURED"

#: Rows created from this moment must carry the stamp at birth. Older rows are the one-time
#: backfill, not a standing breach -- the same cut `certificate_truth.BIRTH_OBLIGATION_FROM` uses.
BIRTH_OBLIGATION_FROM = "2026-09-23T00:00:00+00:00"

ATTRIBUTION_RULE = (
    "producer = the organ that CAUSED the row (its generator, else the discovery it compiled, "
    "else its origin), lowercased; region = that producer's regional ground token, else the "
    "country of the source its lineage names, else NOT_REGIONAL for a method/desk organ, else "
    "UNATTRIBUTABLE with the reason -- stamped by libs/research/attribution.attribute() at the "
    "two registry doors, never inferred by a later sweep")

# --------------------------------------------------------------------------- the region tables
#: The twelve regions plus the institutional bucket. A `global`/`institutional` ground is NOT
#: forced into a geography: pretending a BIS working paper is "Europe" corrupts the one table the
#: regional scoreboard exists to publish.
REGION_OF_CODE: dict[str, str] = {
    "jp": "Japan",
    "kr": "Korea",
    "cn": "China", "tw": "China", "hk": "China",
    "sg": "SEA", "vn": "SEA", "th": "SEA", "id": "SEA", "my": "SEA", "ph": "SEA",
    "ru": "Russia/CIS", "ua": "Russia/CIS",
    "in": "India", "pk": "India", "bd": "India", "lk": "India",
    "gb": "Europe", "de": "Europe", "fr": "Europe", "it": "Europe", "es": "Europe",
    "nl": "Europe", "se": "Europe", "dk": "Europe", "no": "Europe", "fi": "Europe",
    "pl": "Europe", "cz": "Europe", "hu": "Europe", "ch": "Europe", "at": "Europe",
    "ie": "Europe", "pt": "Europe", "gr": "Europe", "ro": "Europe", "be": "Europe",
    "us": "North America", "ca": "North America",
    "br": "LatAm", "mx": "LatAm", "cl": "LatAm", "co": "LatAm", "pe": "LatAm", "ar": "LatAm",
    "pa": "LatAm", "uy": "LatAm",
    "au": "Oceania", "nz": "Oceania",
    "sa": "MENA", "ae": "MENA", "tr": "MENA", "il": "MENA", "eg": "MENA", "ma": "MENA",
    "qa": "MENA", "kw": "MENA",
    "za": "Africa", "ng": "Africa", "ke": "Africa", "gh": "Africa", "tz": "Africa",
    "global": "Global/institutional", "institutional": "Global/institutional",
}
REGIONS: tuple[str, ...] = ("Japan", "Korea", "China", "SEA", "Russia/CIS", "India", "Europe",
                            "North America", "LatAm", "Oceania", "MENA", "Africa",
                            "Global/institutional")

#: Long-form names a producer, a department prefix or a source country may carry instead of the
#: two-letter ground code. Derived names only -- `japan:JapanDataScout` is a live generator.
NAME_TO_CODE: dict[str, str] = {
    "japan": "jp", "japanese": "jp", "nikkei": "jp",
    "korea": "kr", "korean": "kr",
    "china": "cn", "chinese": "cn", "taiwan": "tw", "hongkong": "hk",
    "russia": "ru", "russian": "ru", "cis": "ru", "ukraine": "ua",
    "india": "in", "indian": "in",
    "europe": "gb", "european": "gb", "uk": "gb", "britain": "gb", "germany": "de",
    "france": "fr", "italy": "it", "spain": "es", "nordics": "se", "switzerland": "ch",
    "usa": "us", "america": "us", "american": "us", "canada": "ca", "northamerica": "us",
    "brazil": "br", "mexico": "mx", "latam": "br", "latinamerica": "br",
    "australia": "au", "newzealand": "nz", "oceania": "au",
    "singapore": "sg", "vietnam": "vn", "thailand": "th", "indonesia": "id",
    "malaysia": "my", "philippines": "ph", "sea": "sg", "asean": "sg",
    "turkey": "tr", "israel": "il", "saudi": "sa", "uae": "ae", "mena": "ae", "egypt": "eg",
    "gulf": "ae", "africa": "za", "southafrica": "za", "nigeria": "ng", "kenya": "ke",
}

#: Producer name prefixes that are METHODS or desk organs by construction. A row from one of
#: these is NOT_REGIONAL, which is a verdict; it is never counted as an attribution gap.
NON_REGIONAL_PREFIXES: tuple[str, ...] = (
    "math:", "physics:", "seat:", "engine:", "moat:", "sim:", "exe:", "lab:", "desk:")

#: Whole producer names that are desk machinery: compilers, fan-outs, samplers and judges. They
#: produce cells from other producers' evidence and belong to no region themselves.
NON_REGIONAL_NAMES: frozenset[str] = frozenset({
    "discovery_compiler", "pack_cells", "pack_cells.world", "sandbox_runner",
    "independence_intake", "timeframe_fanout", "coverage_tensor", "moat_factory",
    "search_paradigm_census", "execution_alpha_miner", "missed_trade_archaeologist",
    "alpha_evolution", "representation_discovery", "math_lab", "physics_lab",
    "world_frontier", "hypothesis_factory", "combination_lab", "dislocation_lab",
})

#: Producer tokens that name nobody. Treated as absent so a placeholder never reads as a producer.
NULL_PRODUCERS: frozenset[str] = frozenset({
    "", "none", "null", "unknown", "unattributed", "_unattributed_generator",
    "_unattributed_source", "desk", "n/a", "na", UNATTRIBUTABLE.lower()})


def normalise_producer(name: object) -> str | None:
    """The canonical producer key, or None when the token names nobody.

    `exe:` prefixes and path shapes collapse onto the stem, exactly as the productivity census's
    own `_norm` does, so the two rosters cannot drift into disagreeing about who exists.
    """
    raw = str(name or "").strip()
    if raw.startswith("exe:"):
        raw = raw[4:]
    if "/" in raw or "\\" in raw or raw.endswith(".py"):
        raw = Path(raw.replace("\\", "/")).stem
    raw = raw.strip().lower()
    return None if raw in NULL_PRODUCERS else raw


def region_of(token: object) -> str | None:
    """The region a producer name, generator prefix or source country names, else None.

    None rather than a default: an unattributable token belongs in a named bucket, and silently
    filing it under "Global" inflates the row a reader is least able to check.
    """
    raw = str(token or "").strip().lower()
    if not raw or raw in NULL_PRODUCERS:
        return None
    seen: list[str] = []
    for part in (raw, raw.split(":")[0], raw.split("_")[0], raw.split("-")[0],
                 raw.replace(" ", ""), raw.split(".")[0]):
        if not part or part in seen:
            continue
        seen.append(part)
        if part in REGION_OF_CODE:
            return REGION_OF_CODE[part]
        code = NAME_TO_CODE.get(part)
        if code:
            return REGION_OF_CODE.get(code)
    return None


def is_non_regional(producer: str | None) -> bool:
    """True when the producer belongs to no region BY CONSTRUCTION (a method or desk organ)."""
    if not producer:
        return False
    return producer in NON_REGIONAL_NAMES or producer.startswith(NON_REGIONAL_PREFIXES)


@dataclass(frozen=True)
class Attribution:
    """One row's producer and region, with the route that reached each and why."""

    producer: str
    region: str
    route: str
    why: str = ""

    @property
    def attributed(self) -> bool:
        return self.producer != UNATTRIBUTABLE

    @property
    def regional(self) -> bool:
        return self.region in REGIONS

    def as_fields(self) -> dict[str, str]:
        """The three columns a stamped row carries."""
        return {PRODUCER_FIELD: self.producer, REGION_FIELD: self.region, ROUTE_FIELD: self.route}


NO_PRODUCER_WHY = ("no generator, no origin, no discovery and no source on the row or in its "
                   "lineage names an organ this desk knows; recorded so the row is auditable "
                   "later and excluded from the attribution denominator by declaration rather "
                   "than by silence")
NO_REGION_WHY = ("the producer carries no regional ground token and its lineage reaches no "
                 "source with a country")


def attribute(*, producer: object = None, generator: object = None, origin: object = None,
              department: object = None, region: object = None,
              source_country: object = None, source_id: object = None,
              parent: Attribution | None = None) -> Attribution:
    """THE ONE RULE. Returns the producer and region for a row about to be created.

    Producer, in order: an explicit producer, the generator that wrote it, the attribution its
    parent row already carries, the origin, the department. Region, in order: an explicit region,
    the region the producer's own name names, the country of the source the lineage reaches, the
    parent's region, NOT_REGIONAL for a method/desk organ, and UNATTRIBUTABLE otherwise.

    Nothing is guessed. A route that did not fire is not recorded, and an absent answer is a
    named verdict rather than a zero (L1.28a).
    """
    who: str | None = None
    route_p = ""
    for cand, name in ((producer, "declared"), (generator, "generator"),
                       (parent.producer if parent and parent.attributed else None, "lineage"),
                       (origin, "origin"), (department, "department")):
        who = normalise_producer(cand)
        if who:
            route_p = name
            break
    where: str | None = None
    route_r = ""
    explicit = str(region or "").strip()
    if explicit in REGIONS or explicit in (NOT_REGIONAL, UNATTRIBUTABLE):
        where, route_r = explicit, "declared"
    elif explicit:
        where = region_of(explicit)
        route_r = "declared" if where else ""
    if where is None:
        where = region_of(who)
        route_r = "producer_name" if where else ""
    if where is None and source_country is not None:
        where = region_of(source_country)
        route_r = "source_country" if where else ""
    if where is None and parent is not None and parent.regional:
        where, route_r = parent.region, "lineage"
    if where is None and department is not None:
        where = region_of(department)
        route_r = "department" if where else ""
    why = ""
    if who is None:
        who, route_p = UNATTRIBUTABLE, "none"
        why = NO_PRODUCER_WHY
    if where is None:
        if is_non_regional(who):
            where, route_r = NOT_REGIONAL, "method_or_desk_organ"
        else:
            where, route_r = UNATTRIBUTABLE, "none"
            why = why or NO_REGION_WHY
    route = f"producer:{route_p}|region:{route_r}"
    if source_id and route_r == "source_country":
        route += f"|source:{source_id}"
    return Attribution(producer=who, region=where, route=route, why=why)


def stamp(**kwargs: Any) -> dict[str, str]:
    """`attribute(...)` as the three columns to write. The birth-stamp call site."""
    return attribute(**kwargs).as_fields()


def coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Attribution coverage over a set of stamped rows: the honest denominator.

    `attributed` counts rows with a real producer; `regional` counts rows whose region is one of
    the twelve; `not_regional` and `unattributable` are DECLARED verdicts and are reported apart
    so a reader never has to guess which of the three a missing number was.
    """
    total = len(rows)
    out: dict[str, Any] = {"rows": total, "attributed": 0, "unattributable_producer": 0,
                           "regional": 0, "not_regional": 0, "unattributable_region": 0,
                           "by_region": {}, "by_producer_top": {}}
    per_region: dict[str, int] = {}
    per_producer: dict[str, int] = {}
    for row in rows:
        who = str(row.get(PRODUCER_FIELD) or "") or UNATTRIBUTABLE
        where = str(row.get(REGION_FIELD) or "") or UNATTRIBUTABLE
        if who == UNATTRIBUTABLE:
            out["unattributable_producer"] += 1
        else:
            out["attributed"] += 1
            per_producer[who] = per_producer.get(who, 0) + 1
        if where in REGIONS:
            out["regional"] += 1
        elif where == NOT_REGIONAL:
            out["not_regional"] += 1
        else:
            out["unattributable_region"] += 1
        per_region[where] = per_region.get(where, 0) + 1
    out["by_region"] = dict(sorted(per_region.items(), key=lambda kv: -kv[1]))
    out["by_producer_top"] = dict(sorted(per_producer.items(), key=lambda kv: -kv[1])[:40])
    out["producer_coverage"] = round(out["attributed"] / total, 4) if total else UNMEASURED
    out["region_coverage"] = (round((out["regional"] + out["not_regional"]) / total, 4)
                              if total else UNMEASURED)
    return out
