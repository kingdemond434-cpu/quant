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

import json
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
    "else its origin), lowercased and read THROUGH its filing namespace (miner:/seat:/src:/"
    "ground:); region = that producer's regional ground token, else the country of the source its "
    "lineage names, else the country its own DECLARED source URL stands in (asia_sources.json), "
    "else its parent's region, else NOT_REGIONAL for a method, a desk organ or a declared seat, "
    "else UNATTRIBUTABLE with the reason -- stamped by libs/research/attribution.attribute() at "
    "the two registry doors, never inferred by a later sweep")

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
    # THE CODES THE DESK'S OWN GROUNDS CARRY AND THIS TABLE DID NOT NAME (measured 2026-09-23 on
    # the trading box: 29 of the 92 distinct `sources.country` values reached no region, so every
    # ground standing on them was UNATTRIBUTABLE for want of a row here). Adding a code only ever
    # ADDS a region a cell can be counted in; no code is ever removed and no region is ever
    # dropped from REGIONS, because a coverage ratio improved by shrinking its denominator is a
    # lie (LAWS: never improve a ratio by removing rows from the denominator).
    "by": "Russia/CIS", "md": "Russia/CIS", "kz": "Russia/CIS", "kg": "Russia/CIS",
    "uz": "Russia/CIS", "tm": "Russia/CIS", "tj": "Russia/CIS", "az": "Russia/CIS",
    "am": "Russia/CIS", "ge": "Russia/CIS",
    "is": "Europe", "ee": "Europe", "lv": "Europe", "lt": "Europe", "sk": "Europe",
    "si": "Europe", "hr": "Europe", "rs": "Europe", "ba": "Europe", "mk": "Europe",
    "al": "Europe", "bg": "Europe", "cy": "Europe", "mt": "Europe", "lu": "Europe",
    "me": "Europe", "li": "Europe",
    "ec": "LatAm", "bo": "LatAm", "gy": "LatAm", "sr": "LatAm", "py": "LatAm",
    "ve": "LatAm", "cr": "LatAm", "gt": "LatAm", "hn": "LatAm", "ni": "LatAm",
    "sv": "LatAm", "do": "LatAm", "cu": "LatAm", "jm": "LatAm", "tt": "LatAm",
    "bs": "LatAm", "bz": "LatAm",
    "dz": "MENA", "tn": "MENA", "ly": "MENA", "iq": "MENA", "ye": "MENA", "jo": "MENA",
    "lb": "MENA", "om": "MENA", "bh": "MENA", "ir": "MENA", "sy": "MENA", "ps": "MENA",
    "et": "Africa", "cd": "Africa", "ci": "Africa", "ne": "Africa", "zw": "Africa",
    "zm": "Africa", "ug": "Africa", "sn": "Africa", "cm": "Africa", "ml": "Africa",
    "bf": "Africa", "mu": "Africa", "mz": "Africa", "ao": "Africa", "bw": "Africa",
    "na": "Africa", "rw": "Africa",
    "mm": "SEA", "bn": "SEA", "kh": "SEA", "la": "SEA", "tl": "SEA",
    "np": "India", "bt": "India", "mv": "India", "af": "India",
    "pg": "Oceania", "fj": "Oceania", "nc": "Oceania",
    "mo": "China",
    "eu": "Europe", "ea": "Europe",
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

#: THE SECOND REGION VOCABULARY, CROSSWALKED RATHER THAN COLLAPSED. The 75 country packs under
#: `desks/mt5/research/countries/` each declare a `REGION_COMMAND`, and `pack_cells.py` publishes
#: its whole world lane in that vocabulary (14 buckets) while this module publishes in its own
#: (13). Two tables with no join is how one artifact could read `EUROPE: 281 grounds` while the
#: other read `Europe: 0 cells` on the same hour and neither was wrong. The crosswalk is consulted
#: for a WHOLE declared token only -- never for a name fragment -- so `miner:asia:rba_tables` can
#: never become "SEA" by splitting on a colon. Both vocabularies keep every bucket they had.
REGION_COMMAND_TO_REGION: dict[str, str] = {
    "ASIA": "China", "CHINA": "China", "JAPAN": "Japan", "KOREA": "Korea",
    "SOUTHEAST_ASIA": "SEA", "SEA": "SEA", "ASEAN": "SEA",
    "SOUTH_ASIA": "India", "INDIA": "India",
    "RUSSIA_CIS": "Russia/CIS", "CIS": "Russia/CIS",
    "EUROPE": "Europe", "UK": "Europe", "CEE": "Europe", "CEE_BALKANS": "Europe",
    "NORDIC": "Europe", "BLACK_SEA": "Europe", "EA": "Europe", "EAST_EU": "Europe",
    "NORTH_AMERICA": "North America", "LATAM": "LatAm",
    "OCEANIA": "Oceania", "ANZ": "Oceania",
    "MIDDLE_EAST": "MENA", "MENA": "MENA", "GULF": "MENA",
    "AFRICA": "Africa", "MEA": "Africa",
    "GLOBAL": "Global/institutional", "INSTITUTIONAL": "Global/institutional",
}

#: Namespaces a producer string may be filed under before its own name begins. `miner:` is the
#: hypothesis graph's scientist vocabulary (`libs/research/lead_schema.py:318`,
#: `miner_candidate_compiler.py:416`), `seat:`/`src:`/`ground:` the source registry's
#: (`source_registry._resolve`). MEASURED 2026-09-23: 216,641 of 323,542 candidates on the trading
#: box carried a `miner:` prefix, and because neither `region_of` nor `is_non_regional` looked past
#: it, `miner:discovery_compiler` (190,766 rows of the desk's own compiler) read UNATTRIBUTABLE
#: instead of NOT_REGIONAL and `miner:asia:rba_tables` (the Reserve Bank of Australia) read
#: UNATTRIBUTABLE instead of Oceania. One prefix, two thirds of the desk's output.
NAMESPACE_PREFIXES: tuple[str, ...] = ("miner:", "seat:", "src:", "ground:", "exe:", "author:")

#: Producer name prefixes that are METHODS or desk organs by construction. A row from one of
#: these is NOT_REGIONAL, which is a verdict; it is never counted as an attribution gap.
NON_REGIONAL_PREFIXES: tuple[str, ...] = (
    "math:", "physics:", "seat:", "engine:", "moat:", "sim:", "exe:", "lab:", "desk:",
    # the sandbox's expression families (`sandbox:alpha101`, `sandbox:alphacrafter`, ...) are a
    # method library run by `sandbox_runner`, not a regional ground: 3,300 of their cells read as
    # an attribution gap until they were named, which overstated the gap by more than every
    # region put together.
    "sandbox:")

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


def strip_namespace(name: object) -> list[str]:
    """`miner:asia:rba_tables` -> that name and every suffix its namespace hides.

    The whole string first, so a producer that IS its own answer is never overtaken by a fragment
    of itself. Only the declared namespaces are peeled: `discovery_compiler:interaction` keeps its
    sub-producer, because that colon separates a lane from its organ and not a filing prefix.
    """
    raw = str(name or "").strip().lower()
    out = [raw] if raw else []
    while True:
        hit = next((p for p in NAMESPACE_PREFIXES if raw.startswith(p)), None)
        if not hit:
            break
        raw = raw[len(hit):]
        if raw and raw not in out:
            out.append(raw)
    return out


def region_of(token: object) -> str | None:
    """The region a producer name, generator prefix or source country names, else None.

    None rather than a default: an unattributable token belongs in a named bucket, and silently
    filing it under "Global" inflates the row a reader is least able to check.
    """
    raw = str(token or "").strip().lower()
    if not raw or raw in NULL_PRODUCERS:
        return None
    seen: list[str] = []
    for base in strip_namespace(raw) or [raw]:
        # A TWO-LETTER MATCH IS NEVER TAKEN FROM AN UNDERSCORE SPLIT. `is`, `na`, `no` and `in`
        # are ISO codes AND the first word of ordinary producer names, so `is_regional` would read
        # as Iceland. The head of a `:`, `-` or `.` filing IS a code position; the head of a
        # `snake_case` name is a word. This narrows nothing that ever resolved: no producer on the
        # desk's roster has a two-letter underscore head.
        for part, code_ok in ((base, True), (base.split(":")[0], True),
                              (base.split("_")[0], False), (base.split("-")[0], True),
                              (base.replace(" ", ""), True), (base.split(".")[0], True)):
            if not part or part in seen or part in NULL_PRODUCERS:
                continue
            seen.append(part)
            if part in REGION_OF_CODE and (code_ok or len(part) > 2):
                return REGION_OF_CODE[part]
            code = NAME_TO_CODE.get(part)
            if code:
                return REGION_OF_CODE.get(code)
    return None


def region_of_command(token: object) -> str | None:
    """A pack's own `REGION_COMMAND` (`EUROPE`, `RUSSIA_CIS`, `MEA`, ...) -> this module's region.

    WHOLE TOKEN ONLY. The crosswalk is never applied to a fragment, so nothing in a producer name
    can reach it by accident; `pack_cells.py` and the country packs speak it and this is the join.
    """
    raw = str(token or "").strip().upper().replace(" ", "_").replace("-", "_")
    if not raw or raw in ("UNMAPPED", "UNMEASURED", UNATTRIBUTABLE, NOT_REGIONAL):
        return None
    return REGION_COMMAND_TO_REGION.get(raw)


# ------------------------------------------------------------ the ground the producer stands on
#: THE JOIN THAT EXISTED AND WAS NEVER MADE. `miner:asia:<pack>` names a row of
#: `desks/mt5/data/asia_sources.json`, every one of which declares the URL it is fetched from, and
#: the host's country code IS the ground -- `rba.gov.au` is Oceania, `boj.or.jp` is Japan,
#: `riksbank.se` is Europe. That is the same rule `pack_cells.resolve_ground` already applies to a
#: crawled ground's documents; this is it applied to the producer's own declared source. DERIVED,
#: never typed: adding a row to that registry attributes its cells with nobody editing this file.
#: Measured 2026-09-23 on the trading box: 1,873 of 2,558 `miner:asia:*` candidates resolve, across
#: Europe, Japan, China, Oceania, LatAm, Africa, Russia/CIS, SEA and Korea.
_GROUND_INDEX: dict[str, str] | None = None
_SEATS: frozenset[str] | None = None
#: Registries read to build the index. A missing file is UNMEASURED and contributes nothing; it
#: never raises and never turns a resolvable producer into a wrong answer.
_ROOT = Path(__file__).resolve().parents[2]
GROUND_REGISTRIES: tuple[Path, ...] = (
    _ROOT / "desks" / "mt5" / "data" / "asia_sources.json",
)
#: Seat donation roots. A `miner:<seat>` whose name is a declared seat directory is desk
#: machinery, not a gap -- the seats are the desk's own producers (`data/intelligence/<seat>/`).
SEAT_ROOTS: tuple[Path, ...] = (
    _ROOT / "desks" / "mt5" / "data" / "intelligence",
    _ROOT / "data" / "intelligence",
)


def host_of(url: object) -> str:
    """The bare host of a URL. Shared with `pack_cells._host_of` in shape so the two agree."""
    raw = str(url or "").strip()
    if "://" in raw:
        raw = raw.split("://", 1)[1]
    return raw.split("/", 1)[0].split("@")[-1].split(":")[0].strip().lower()


def region_of_url(url: object) -> str | None:
    """The region a URL's host stands in, when its last label IS a country code.

    A generic top-level domain has no jurisdiction and returns None, which is a measurement about
    the host rather than a guess about the ground.
    """
    host = host_of(url)
    label = host.rsplit(".", 1)[-1] if "." in host else ""
    if len(label) != 2 or not label.isalpha():
        return None
    return REGION_OF_CODE.get(label)


def ground_index() -> dict[str, str]:
    """Every source id the desk declares -> the region its declared URL stands in. Cached."""
    global _GROUND_INDEX
    if _GROUND_INDEX is not None:
        return _GROUND_INDEX
    idx: dict[str, str] = {}
    for path in GROUND_REGISTRIES:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue                                  # UNMEASURED: contributes nothing, never a 0
        rows = doc.get("sources") if isinstance(doc, dict) else doc
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            sid = str(row.get("id") or row.get("source_id") or "").strip().lower()
            where = (region_of(row.get("country")) or region_of_command(row.get("region"))
                     or region_of(row.get("region")) or region_of_url(row.get("url")))
            if sid and where:
                idx.setdefault(sid, where)
                idx.setdefault(f"asia:{sid}", where)
    _GROUND_INDEX = idx
    return idx


def seats() -> frozenset[str]:
    """The seat names the desk declares on disk. A seat is desk machinery, never a region."""
    global _SEATS
    if _SEATS is not None:
        return _SEATS
    found: set[str] = set()
    for root in SEAT_ROOTS:
        try:
            found.update(p.name.strip().lower() for p in root.iterdir() if p.is_dir())
        except OSError:
            continue
    _SEATS = frozenset(found)
    return _SEATS


def region_of_ground(producer: object) -> str | None:
    """The region the producer's own declared source stands on, else None.

    Namespace-aware: `miner:asia:rba_tables`, `asia:rba_tables` and `rba_tables` are one producer
    filed three ways, and all three reach the same ground.
    """
    for base in strip_namespace(producer):
        hit = ground_index().get(base)
        if hit:
            return hit
    return None


def is_non_regional(producer: str | None) -> bool:
    """True when the producer belongs to no region BY CONSTRUCTION (a method or desk organ).

    The SUB-PRODUCER counts too: `discovery_compiler:interaction` is the interaction lane of the
    compiler, not a regional department, and reporting its 3,691 cells as an attribution gap
    would overstate the gap by more than the whole of Europe. A department that IS regional never
    reaches this test -- `region_of()` matches its name first.

    THE FILING PREFIX COUNTS TOO, and that is two thirds of the desk's output: the hypothesis
    graph files the same compiler as `miner:discovery_compiler`, and reading the prefix as part of
    the name reported 190,766 rows of the desk's own compiler as an attribution GAP rather than as
    the NOT_REGIONAL verdict they are. A declared seat (`data/intelligence/<seat>/`) is desk
    machinery by the same argument -- it is one of the desk's own producers. A seat or organ whose
    name IS regional never reaches this test: `region_of()` matches `japan:gotobi` first.
    """
    if not producer:
        return False
    for base in strip_namespace(producer):
        stem = base.split(":")[0]
        if (base in NON_REGIONAL_NAMES or stem in NON_REGIONAL_NAMES
                or base.startswith(NON_REGIONAL_PREFIXES)):
            return True
        if base != producer and (base in seats() or stem in seats()):
            return True                       # filed under a namespace AND a declared seat name
    return False


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
        where = region_of_command(explicit) or region_of(explicit)
        route_r = "declared" if where else ""
    if where is None:
        where = region_of(who)
        route_r = "producer_name" if where else ""
    if where is None and source_country is not None:
        where = region_of(source_country) or region_of_command(source_country)
        route_r = "source_country" if where else ""
    if where is None:
        # THE GROUND THE PRODUCER STANDS ON. Consulted after the producer's own name and the
        # lineage's source country, before the parent: a producer that names a declared source is
        # answering about ITSELF, which outranks what it inherited.
        where = region_of_ground(who)
        route_r = "producer_ground" if where else ""
    if where is None and parent is not None and parent.regional:
        where, route_r = parent.region, "lineage"
    if where is None and department is not None:
        where = region_of(department) or region_of_command(department)
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


def region_spread(counts: dict[str, Any]) -> dict[str, Any]:
    """THE PRINCIPAL'S MEASURE: equal maximum depth, not a few strong regions and a tail of zeros.

    A total says nothing about whether every region is mined "like it's their native country
    quants". This publishes the SPREAD over the regions the desk names -- how many hold anything,
    the weakest, the strongest, and the ratio between them -- with the empty ones listed by name so
    a zero is a work order rather than a silence.

    `counts` is region -> n for any per-region number (unique cells, judged cells). Regions absent
    from it are counted as zero: the denominator is always every region the desk NAMES, because a
    ratio improved by dropping a region from the denominator is a lie (L1.50).
    """
    per = {r: int(counts.get(r) or 0) for r in REGIONS}
    vals = sorted(per.values())
    held = [r for r, n in per.items() if n > 0]
    empty = [r for r, n in per.items() if n <= 0]
    total = sum(vals)
    return {
        "regions_named": len(REGIONS),
        "regions_holding": len(held),
        "regions_empty": empty,
        "total": total,
        "min": vals[0] if vals else 0,
        "median": vals[len(vals) // 2] if vals else 0,
        "max": vals[-1] if vals else 0,
        # EVENNESS, so "equal maximum depth" is a number and not an adjective. 1.0 is every named
        # region equally deep; it falls as the distribution concentrates. Normalised Shannon
        # evenness over the named regions, UNMEASURED when nothing has been produced at all.
        "evenness": _evenness(vals) if total > 0 else UNMEASURED,
        "by_region": dict(sorted(per.items(), key=lambda kv: -kv[1])),
        "rule": ("the denominator is every region in attribution.REGIONS, always; an empty region "
                 "is listed by name so it reads as a work order and never as an absence"),
    }


def _evenness(vals: list[int]) -> float:
    """Normalised Shannon evenness of a per-region distribution, 0..1."""
    import math
    total = sum(vals)
    nz = [v for v in vals if v > 0]
    if total <= 0 or len(vals) < 2 or len(nz) < 2:
        return 0.0
    h = -sum((v / total) * math.log(v / total) for v in nz)
    return round(h / math.log(len(vals)), 4)
