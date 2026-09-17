"""THE SOUTH AND SOUTHEAST ASIA COUNTRY PACKS: is each one a research object, or a brochure?

WHAT THESE TESTS ARE FOR. Seven country packs -- India, Singapore, Indonesia, Malaysia, Thailand,
the Philippines and Vietnam -- are DATA, and data that nothing checks rots in a specific and
predictable way: an actor loses its falsifier and becomes a story, a domain loses its controls and
becomes a correlation, an instrument that the broker does not quote creeps into the executable
list and compiles cells that can never be filled, a terminology table quietly becomes an English
glossary, and a source list shrinks to the five obvious websites. Every test below is aimed at one
of those.

THE FIVE ASSERTIONS THAT ARE LOAD-BEARING, and why each one earns its place:

  1. EVERY SYMBOL IS CHECKED AGAINST THE BROKER'S OWN REGISTRY. `executable_instruments` and every
     `transmission_edges_seed` target must exist in `data/universe/universe.json` and must not be
     a single-name equity (the two-lane order, 2026-09-06). Three of these seven currencies --
     the ringgit, the peso and the dong -- are NOT on the registry, which is why those packs
     carry no domestic instrument at all and route everything through `transmission_targets`.
     A test that did not check this would let a pack promise USDMYR and produce nothing.

  2. ELEVEN FIELDS PER ACTOR, AND THE FALSIFIER IS ONE OF THEM. The chain actor -> constraint ->
     observable -> flow -> market impact -> candidate cannot be walked through a gap, and an
     actor whose falsifier is blank is a narrative rather than a research object.

  3. NATIVE SCRIPT, NOT TRANSLATED ENGLISH. A miner searching Thai boards for the Thai for "gold
     shop" finds material; one searching for "gold shop" finds nothing, and finding nothing is
     indistinguishable from never having asked. So the terminology and the per-layer source
     queries are checked for actual Devanagari, Thai, Vietnamese diacritics, Han characters and
     Malay/Indonesian/Filipino marker vocabulary -- per country, against what that country
     actually writes in.

  4. TEN SOURCE LAYERS, EACH POPULATED OR NAMED ABSENT. The principal's depth rule of 2026-09-17:
     a country is never "covered" by five obvious sources. Every layer is present or its absence
     is stated with a reason, every source carries three INDEPENDENT labels, a page whose terms
     forbid machine extraction is registered with `machine_use_allowed=False` rather than omitted,
     and at least one FRINGE source is kept per country with low weight rather than dropped.

  5. THE HOLIDAY RULES PRODUCE DATES SOMEBODY CAN CHECK. Diwali Muhurat 2025, Songkran 2026,
     Tet 2026 and Hari Raya 2026 are the four anchors, and they are asserted by value. A holiday
     table that cannot reproduce a date a human knows is a table nobody has read.

WHY THE TESTS READ `fields()` AND NOT `pack()`. Two sibling frameworks landed with different row
schemas: `research.countries` builds edges as {id, source, mechanism, targets, sign, horizon, lag,
control, evidence} and `libs.research.country_lab.CountryPack` coerces whatever it is handed into
its own `TransmissionSeed` / `HolidayRule` / `Era` shapes, which do not carry those names. So the
CONTENT is asserted against `fields()`, which is the data as written, and `pack()` is exercised
separately to prove it still constructs on whichever framework is on the tree. That is not a
workaround around a failing check -- it is the difference between testing the pack and testing
somebody else's adapter.
"""
from __future__ import annotations

import sys
from datetime import date
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.countries import (  # noqa: E402
    ACTOR_FIELDS,
    DATASET_FIELDS,
    EDGE_EVIDENCE,
    PACK_FIELDS,
    check_pack,
    holiday_table,
    is_closed,
    is_equity,
    resolve,
    universe_symbols,
)

#: The seven packs this file owns. The East Asia builder owns `kr`, `cn`, `hk` and `tw` and they
#: are deliberately NOT tested here: a shared test that fails because a sibling's pack is
#: mid-landing tells nobody anything about either.
CODES: tuple[str, ...] = ("ind", "sg", "idn", "my", "th", "ph", "vn")

#: The ten source layers of the principal's depth rule (2026-09-17).
LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology",
    "app_ecosystem", "media", "archive", "physical_economy", "source_graph")
ACCESS_LABELS: frozenset[str] = frozenset({
    "PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA", "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL",
    "USER_SUBMITTED", "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED"})
CREDIBILITY: frozenset[str] = frozenset({
    "AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE", "CONTRADICTED", "UNKNOWN"})
PREDICTIVE: frozenset[str] = frozenset({
    "UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE", "NARRATIVE_FEATURE"})

#: Codepoint ranges per script. `research.countries.has_script` knows han, hangul and kana -- the
#: East Asia builder's three -- and this file adds the ones South and Southeast Asia is written
#: in rather than editing a shared module a sibling is still writing.
SCRIPTS: dict[str, tuple[tuple[int, int], ...]] = {
    "devanagari": ((0x0900, 0x097F),),
    "thai": ((0x0E00, 0x0E7F),),
    "han": ((0x3400, 0x4DBF), (0x4E00, 0x9FFF)),
    # Vietnamese is written in a Latin alphabet with tone and vowel marks: Latin Extended
    # Additional carries most of them, and d-with-stroke, o-horn and u-horn live in Latin
    # Extended-A and -B. An unaccented "ty gia" is a DIFFERENT search string from the accented
    # one, which is exactly why this is checked rather than assumed.
    "vietnamese": ((0x1EA0, 0x1EF9), (0x0110, 0x0111), (0x01A0, 0x01B0), (0x00C0, 0x00FF)),
}

#: Latin-script languages cannot be identified by codepoint, so they are identified by MARKER
#: VOCABULARY: words that exist in that language and in no English glossary of the same subject.
#: A pack that translated its terminology into English would lose every one of these.
MARKERS: dict[str, tuple[str, ...]] = {
    "malay": ("kadar", "eksport", "dasar monetari", "minyak sawit", "cukai", "pelabur",
              "belanjawan", "rizab", "pengeluaran", "duti", "subsidi", "saham", "niaga",
              "kecairan", "tahun baru cina", "hari raya", "penukaran", "pertukaran"),
    "bahasa": ("suku bunga", "rupiah", "cadangan devisa", "ekspor", "impor", "lelang",
               "batu bara", "minyak sawit", "nikel", "kurs", "pungutan", "aliran modal",
               "dividen", "libur", "saham", "neraca perdagangan", "intervensi", "devisa"),
    "filipino": ("padala", "bigas", "palay", "sahod", "presyo", "pista opisyal", "piso",
                 "pamahalaan", "implasyon", "pamilihan", "minahan", "tag-ulan", "sweldo",
                 "kinsenas", "katapusan", "pasko", "badyet", "salapi"),
}

#: What each country must actually be written in. India is checked for Devanagari because the
#: pack claims Hindi sources; Singapore and Malaysia for Han because their Chinese-language press
#: is a named source class; Indonesia, Malaysia and the Philippines for their Latin-script
#: marker vocabulary; Thailand for Thai; Vietnam for Vietnamese diacritics.
REQUIRED_SCRIPTS: dict[str, tuple[str, ...]] = {
    "ind": ("devanagari",),
    "sg": ("han",),
    "idn": (),
    "my": ("han",),
    "th": ("thai",),
    "ph": (),
    "vn": ("vietnamese",),
}
REQUIRED_MARKERS: dict[str, tuple[str, ...]] = {
    "ind": (), "sg": ("malay",), "idn": ("bahasa",), "my": ("malay",),
    "th": (), "ph": ("filipino",), "vn": (),
}

#: The four holiday anchors the principal named, by value. Each is (country, iso, substring the
#: entry's name must contain, case-insensitively). Diwali is handled separately because the
#: Muhurat session is a closure AND a one-hour session and the tithi straddled two days.
ANCHORS: tuple[tuple[str, str, str], ...] = (
    ("th", "2026-04-13", "songkran"),
    ("th", "2026-04-14", "songkran"),
    ("th", "2026-04-15", "songkran"),
    ("vn", "2026-02-17", "tet"),
    ("my", "2026-03-20", "aidilfitri"),
    ("sg", "2026-03-20", "hari raya"),
    ("idn", "2026-03-20", "idul fitri"),
    ("ph", "2026-03-20", "eid"),
)


def _mod(code: str) -> Any:
    return import_module(f"research.countries.{code}.pack")


def _has_script(text: str, script: str) -> bool:
    ranges = SCRIPTS[script]
    return any(any(lo <= ord(ch) <= hi for lo, hi in ranges) for ch in text)


def _all_terms(mod: Any) -> list[str]:
    return [t for terms in mod.TERMINOLOGY.values() for t in terms]


def _all_queries(mod: Any) -> list[str]:
    return [q for s in mod.SOURCE_CLASSES for q in s.get("queries", ())]


# ---------------------------------------------------------------- the pack is a pack at all
@pytest.mark.parametrize("code", CODES)
def test_every_pack_exposes_all_twenty_one_mandate_fields(code: str) -> None:
    """`fields()` is the lossless form and must carry every field the mandate declares.

    A pack missing one of these is not a smaller pack. It is a pack whose consumers will read a
    None and treat it as an empty tuple, which is the L1.28a failure in miniature: absence
    resolving silently to a clean answer.
    """
    data = _mod(code).fields()
    missing = [f for f in PACK_FIELDS if f not in data]
    assert not missing, f"{code}: missing mandate fields {missing}"
    for field in PACK_FIELDS:
        if field == "custom_miners":
            continue
        assert data[field], f"{code}: {field} is empty"


@pytest.mark.parametrize("code", CODES)
def test_every_pack_passes_the_frameworks_own_validator(code: str) -> None:
    """`check_pack` is the shared gate and an empty problem list is the only pass.

    It is run against `fields()` rather than against `pack()` deliberately: `pack()` returns
    whatever the sibling framework's dataclass coerces the rows into, and a test that asserted on
    the coerced shape would be testing the adapter rather than the country.
    """
    problems = check_pack(_mod(code).fields())
    assert problems == [], f"{code}:\n  " + "\n  ".join(problems)


@pytest.mark.parametrize("code", CODES)
def test_pack_constructs_on_whichever_framework_is_on_this_tree(code: str) -> None:
    """`pack()` must return something with the mandate's fields, dataclass or dict.

    The brief was explicit: import the framework lazily and degrade to a plain mapping if it has
    not landed. This asserts the degradation actually works rather than trusting the try/except.
    """
    built = _mod(code).pack()
    assert built is not None
    for field in ("code", "name", "executable_instruments", "actors", "domains"):
        got = built.get(field) if isinstance(built, dict) else getattr(built, field, None)
        assert got, f"{code}: pack() lost {field}"


# ---------------------------------------------------------------- actors
@pytest.mark.parametrize("code", CODES)
def test_at_least_twelve_actors_each_with_eleven_non_empty_fields(code: str) -> None:
    """Twelve participants minimum, and every one of the eleven content fields filled.

    THE FALSIFIER IS THE FIELD THAT MATTERS. An actor with `holds`, `forced_to` and `impact` but
    no falsifier is a plausible story about an economy, and a plausible story is exactly what this
    department is built to refuse: it cannot be wrong, so it cannot be research.
    """
    actors = _mod(code).ACTORS
    assert len(actors) >= 12, f"{code}: {len(actors)} actors, need 12"
    names = [str(a["name"]).strip() for a in actors]
    assert all(names), f"{code}: an actor with no name"
    assert len(set(names)) == len(names), f"{code}: duplicate actor names"
    for actor in actors:
        for field in ACTOR_FIELDS:
            assert actor.get(field), f"{code}: actor {actor['name']!r} has empty {field}"


@pytest.mark.parametrize("code", CODES)
def test_actor_instruments_are_tradable_and_never_single_names(code: str) -> None:
    """An actor may BE a listed company; the instruments it moves may never be one.

    This is the two-lane order at the actor level. An oil marketing company, a plantation group
    and a broker are all named as actors in these packs -- correctly, because they are forced
    participants -- and each one's `instruments` must be FX, metals, energy, softs, indices or
    bonds, because those are the only things a hypothesis may be minted about.
    """
    for actor in _mod(code).ACTORS:
        split = resolve(actor.get("instruments", ()))
        assert not split["equities"], (
            f"{code}: actor {actor['name']!r} names single-name equities {split['equities']}")
        assert not split["absent"], (
            f"{code}: actor {actor['name']!r} names symbols absent from the broker universe "
            f"{split['absent']}; they belong in transmission_targets")


# ---------------------------------------------------------------- domains
@pytest.mark.parametrize("code", CODES)
def test_at_least_ten_domains_each_with_objects_conditions_instruments_and_controls(
        code: str) -> None:
    """Ten research domains, and CONTROLS are never optional.

    A domain without a negative control cannot tell an effect from the desk's own sampling. That
    is not a quality gradient -- a measured number with no control is not a weaker finding, it is
    a finding about the sample -- so the assertion is on presence, not on count.
    """
    domains = _mod(code).DOMAINS
    assert len(domains) >= 10, f"{code}: {len(domains)} domains, need 10"
    ids = [str(d["id"]) for d in domains]
    assert len(set(ids)) == len(ids), f"{code}: duplicate domain ids"
    for dom in domains:
        for field in ("objects", "conditions", "instruments", "controls"):
            assert dom.get(field), f"{code}: domain {dom['id']} has no {field}"
        assert len(dom["controls"]) >= 2, (
            f"{code}: domain {dom['id']} has {len(dom['controls'])} control(s); one control is a "
            f"gesture, and the point of the table is that a generic and a country-specific "
            f"control disagree")


@pytest.mark.parametrize("code", CODES)
def test_every_miner_names_a_domain_that_exists(code: str) -> None:
    """A miner pointing at a domain id nobody declared is wiring to nowhere."""
    mod = _mod(code)
    ids = {str(d["id"]) for d in mod.DOMAINS}
    for spec in mod.CUSTOM_MINERS:
        assert spec.get("entry"), f"{code}: miner {spec.get('name')!r} has no entry point"
        for did in spec.get("domain_ids", ()):
            assert did in ids, f"{code}: miner {spec['name']!r} names unknown domain {did!r}"


# ---------------------------------------------------------------- the universe
@pytest.mark.parametrize("code", CODES)
def test_executable_instruments_all_exist_and_none_is_a_single_name_equity(code: str) -> None:
    """Every executable symbol is in the broker's own registry, and none is a share CFD.

    THIS IS THE ASSERTION THAT KEEPS THE PACKS HONEST ABOUT THREE MISSING CURRENCIES. USDMYR,
    USDPHP and USDVND are not on this registry -- the ringgit because Bank Negara prohibits
    offshore trading, the other two because their offshore markets are too thin for a retail
    liquidity provider -- and the Malaysian, Philippine and Vietnamese packs therefore carry NO
    domestic instrument. Without this test a pack could promise them and compile cells that can
    never be filled.
    """
    symbols = tuple(_mod(code).EXECUTABLE_INSTRUMENTS)
    assert symbols, f"{code}: no executable instruments at all"
    known = universe_symbols()
    assert known, "the broker universe is unreadable -- UNMEASURED, so nothing has been checked"
    absent = [s for s in symbols if s not in known]
    assert not absent, f"{code}: {absent} are not in the broker universe"
    equities = [s for s in symbols if is_equity(s)]
    assert not equities, (
        f"{code}: {equities} are single-name equities; the two-lane order (2026-09-06) forbids "
        f"minting statistical hypotheses on them")


@pytest.mark.parametrize("code", CODES)
def test_at_least_eight_transmission_seeds_each_naming_real_universe_symbols(code: str) -> None:
    """Eight seeds minimum, every target a symbol the desk can actually trade.

    A transmission edge whose target does not exist is a sentence, not a hypothesis. The seeds
    are where an absent instrument's economics are supposed to LAND, so this is the test that
    makes `transmission_targets` a routing decision rather than an apology.
    """
    edges = _mod(code).TRANSMISSION_EDGES_SEED
    assert len(edges) >= 8, f"{code}: {len(edges)} seeds, need 8"
    known = universe_symbols()
    ids = [str(e["id"]) for e in edges]
    assert len(set(ids)) == len(ids), f"{code}: duplicate edge ids"
    for e in edges:
        targets = tuple(e.get("targets", ()))
        assert targets, f"{code}: edge {e['id']} names no target"
        for sym in targets:
            assert sym in known, f"{code}: edge {e['id']} target {sym} is not in the universe"
            assert not is_equity(sym), f"{code}: edge {e['id']} target {sym} is an equity"
        assert e.get("evidence") in EDGE_EVIDENCE, f"{code}: edge {e['id']} has no evidence state"
        for field in ("source", "mechanism", "sign", "horizon", "lag", "control"):
            assert str(e.get(field, "")).strip() != "", (
                f"{code}: edge {e['id']} has empty {field}")


@pytest.mark.parametrize("code", CODES)
def test_absent_instruments_are_named_with_the_symbols_they_route_into(code: str) -> None:
    """Every instrument the pack is ABOUT but cannot trade is named, with its proxies.

    Absence recorded is a research object; absence omitted is a hole nobody can see. Each
    `transmission_targets` row must say what it is, where it trades, why it matters, and which
    real symbols carry its mechanism -- and those proxies must themselves exist.
    """
    mod = _mod(code)
    targets = mod.TRANSMISSION_TARGETS
    assert len(targets) >= 5, f"{code}: only {len(targets)} absent instruments named"
    known = universe_symbols()
    for row in targets:
        for field in ("name", "venue", "why"):
            assert str(row.get(field, "")).strip(), f"{code}: transmission target missing {field}"
        proxies = tuple(row.get("proxies", ()))
        assert proxies, f"{code}: {row['name']!r} names no proxy symbols"
        for sym in proxies:
            assert sym in known, f"{code}: {row['name']!r} proxy {sym} is not in the universe"


def test_the_three_currencies_this_broker_cannot_quote_are_named_as_absent() -> None:
    """MYR, PHP and VND are missing from the registry, and the packs say so out loud.

    This is the single most consequential fact about half of this department and it is asserted
    by name because it is the kind of fact a later session will assume away. If a USDMYR ever
    appears on the registry, this test fails and the Malaysian pack has to be rewritten from a
    transmission-only pack into an executable one -- which is exactly the notification the desk
    should get.
    """
    known = universe_symbols()
    for sym in ("USDMYR", "USDPHP", "USDVND"):
        assert sym not in known, (
            f"{sym} is now quotable: the transmission-only packs that route around it must be "
            f"revisited rather than left as they are")
    for code, sym in (("my", "USDMYR"), ("ph", "USDPHP"), ("vn", "USDVND")):
        named = " ".join(str(r["name"]) for r in _mod(code).TRANSMISSION_TARGETS)
        assert sym[3:] in named or sym in named.replace("/", ""), (
            f"{code}: {sym} is not named in transmission_targets")


# ---------------------------------------------------------------- native language
@pytest.mark.parametrize("code", CODES)
def test_terminology_is_written_in_the_script_the_country_uses(code: str) -> None:
    """A miner searching in English finds nothing, and nothing is not a measurement.

    Devanagari for India, Thai for Thailand, Vietnamese diacritics for Vietnam, Han for the
    Chinese-language press of Singapore and Malaysia. The Latin-script languages -- Malay, Bahasa
    Indonesia, Filipino -- cannot be identified by codepoint, so they are identified by marker
    vocabulary that no English glossary of the same subject would contain.
    """
    mod = _mod(code)
    terms = _all_terms(mod)
    assert len(terms) >= 40, f"{code}: only {len(terms)} terminology entries"
    assert len(mod.TERMINOLOGY) >= 10, f"{code}: terminology covers only "\
                                       f"{len(mod.TERMINOLOGY)} domains"
    for script in REQUIRED_SCRIPTS[code]:
        hits = [t for t in terms if _has_script(t, script)]
        assert len(hits) >= 10, f"{code}: only {len(hits)} terms in {script}"
    lowered = " ".join(terms).lower()
    for language in REQUIRED_MARKERS[code]:
        found = [m for m in MARKERS[language] if m in lowered]
        assert len(found) >= 6, f"{code}: only {len(found)} {language} marker terms: {found}"


@pytest.mark.parametrize("code", CODES)
def test_every_domain_has_its_own_native_vocabulary(code: str) -> None:
    """Terminology is keyed BY DOMAIN, because a per-country word list is not a search plan.

    The whole point of keying terms to a domain id is that the monsoon miner searches for monsoon
    words and the expiry miner searches for expiry words. A flat list would be a glossary.
    """
    mod = _mod(code)
    ids = {str(d["id"]) for d in mod.DOMAINS}
    for key, terms in mod.TERMINOLOGY.items():
        assert key in ids, f"{code}: terminology key {key!r} is not a declared domain"
        assert len(terms) >= 4, f"{code}: domain {key} has only {len(terms)} terms"


# ---------------------------------------------------------------- the ten source layers
@pytest.mark.parametrize("code", CODES)
def test_all_ten_source_layers_are_populated_or_named_absent_with_a_reason(code: str) -> None:
    """The principal's depth rule: a country is never covered by five obvious sources.

    Ten layers, and a layer is either populated or NAMED in `ABSENT_SOURCE_LAYERS` with a reason.
    Blank is not permitted, because a blank layer is indistinguishable from a layer nobody looked
    at -- which is the same failure as an unmeasured control reported as a passed one.
    """
    mod = _mod(code)
    present = {str(s["layer"]) for s in mod.SOURCE_CLASSES}
    unknown = present - set(LAYERS)
    assert not unknown, f"{code}: source layers outside the vocabulary: {sorted(unknown)}"
    absent = dict(mod.ABSENT_SOURCE_LAYERS)
    for layer in LAYERS:
        assert layer in present or layer in absent, (
            f"{code}: layer {layer!r} is neither populated nor named absent")
        if layer in absent:
            assert str(absent[layer]).strip(), f"{code}: layer {layer!r} absent with no reason"


@pytest.mark.parametrize("code", CODES)
def test_every_source_carries_three_independent_labels_and_native_queries(code: str) -> None:
    """Access, credibility and predictive state are SEPARATE axes, and queries are native.

    They are independent on purpose. An AUTHORITATIVE archive is NOT_PREDICTIVE by construction;
    a FRINGE rumour channel can be a NARRATIVE_FEATURE worth carrying. Collapsing the three into
    one "quality" number is how a desk quietly stops reading the material that disagrees with it.
    """
    mod = _mod(code)
    sources = mod.SOURCE_CLASSES
    assert len(sources) >= 10, f"{code}: only {len(sources)} source classes"
    ids = [str(s["id"]) for s in sources]
    assert len(set(ids)) == len(ids), f"{code}: duplicate source ids"
    for s in sources:
        assert s["access_label"] in ACCESS_LABELS, f"{code}: {s['id']} bad access_label"
        assert s["credibility"] in CREDIBILITY, f"{code}: {s['id']} bad credibility"
        assert s["predictive_state"] in PREDICTIVE, f"{code}: {s['id']} bad predictive_state"
        assert isinstance(s["machine_use_allowed"], bool), f"{code}: {s['id']} bad machine flag"
        assert s["roots"], f"{code}: {s['id']} names no concrete root"
        assert all(str(r).startswith("http") for r in s["roots"]), (
            f"{code}: {s['id']} has a root that is not a fetchable address")
        assert str(s["notes"]).strip(), f"{code}: {s['id']} has no note saying why it is here"


@pytest.mark.parametrize("code", CODES)
def test_the_native_language_layers_query_in_native_language(code: str) -> None:
    """Queries are search strings, and a translated one returns nothing.

    Checked on the layers where the country's own language is what the material is written in:
    a Thai forum, an Indonesian ministry decree, a Vietnamese coffee board. The official and
    retail layers are the two that must never be searched in English alone.
    """
    mod = _mod(code)
    queries = _all_queries(mod)
    assert len(queries) >= 25, f"{code}: only {len(queries)} source queries across ten layers"
    scripts = REQUIRED_SCRIPTS[code]
    markers = REQUIRED_MARKERS[code]
    if not scripts and not markers:
        pytest.skip(f"{code}: no script or marker requirement declared")
    lowered = " ".join(queries).lower()
    for script in scripts:
        hits = [q for q in queries if _has_script(q, script)]
        assert len(hits) >= 4, f"{code}: only {len(hits)} source queries in {script}"
    for language in markers:
        found = [m for m in MARKERS[language] if m in lowered]
        assert len(found) >= 3, f"{code}: only {len(found)} {language} markers in the queries"


@pytest.mark.parametrize("code", CODES)
def test_fringe_material_is_kept_and_forbidden_material_is_registered_not_omitted(
        code: str) -> None:
    """Two rules that both exist to stop a source silently disappearing.

    FRINGE, contradictory or false-looking PUBLIC material stays as a low-weight evidence object:
    a coordinated tip campaign is a real crowding event even when every claim inside it is false,
    and deleting it means the desk cannot see the crowding. A page whose terms FORBID machine
    extraction is registered with `machine_use_allowed=False` and never scraped -- visible, so a
    later session knows the material exists and knows why it has not been read.
    """
    sources = _mod(code).SOURCE_CLASSES
    fringe = [s for s in sources if s["credibility"] in {"FRINGE", "UNRELIABLE", "CONTRADICTED"}]
    assert fringe, (
        f"{code}: no low-credibility source at all. Either nobody looked at the retail ecology, "
        f"or somebody dropped it -- both are the same defect from the outside")
    for s in fringe:
        assert s["predictive_state"] in {"NARRATIVE_FEATURE", "UNTESTED", "NOT_PREDICTIVE"}, (
            f"{code}: {s['id']} is low-credibility and claims to be PREDICTIVE without a test")
    blocked = [s for s in sources if not s["machine_use_allowed"]]
    assert blocked, (
        f"{code}: no source is registered as machine-use-forbidden. Every one of these countries "
        f"has licensed assessment data that would be the ideal input and whose terms forbid "
        f"extraction; recording none of it means the substitution was never a decision")
    for s in blocked:
        assert "not scraped" in s["notes"].lower() or "never scraped" in s["notes"].lower(), (
            f"{code}: {s['id']} is machine-use-forbidden but its note does not say it is unread")


# ---------------------------------------------------------------- datasets and point-in-time
@pytest.mark.parametrize("code", CODES)
def test_every_dataset_carries_its_point_in_time_fields(code: str) -> None:
    """A dataset row exists to answer one question: when did this number become knowable?

    `publication_lag_days` is the field the catalogue is for. India's reserves are stamped to the
    PRECEDING Friday, the Philippine December remittance print does not exist until mid-February,
    and Indonesian CPI lands the next day: three lags spanning two orders of magnitude, and a
    backtest that uses reference dates instead of publication dates is wrong in all three.
    """
    datasets = _mod(code).DATASETS
    assert len(datasets) >= 10, f"{code}: only {len(datasets)} datasets catalogued"
    names = [str(d["name"]) for d in datasets]
    assert len(set(names)) == len(names), f"{code}: duplicate dataset names"
    for row in datasets:
        for field in DATASET_FIELDS:
            if field in {"pit_feasible", "publication_lag_days"}:
                continue
            assert row.get(field), f"{code}: dataset {row['name']!r} has empty {field}"
        assert isinstance(row["pit_feasible"], bool)
        assert float(row["publication_lag_days"]) >= 0.0


@pytest.mark.parametrize("code", CODES)
def test_the_central_bank_carries_a_decision_rule_and_a_utc_stamp(code: str) -> None:
    """A decision the desk cannot time is a decision it cannot trade.

    Vietnam is the interesting case and it is deliberately DIFFERENT: the SBV publishes no
    meeting calendar at all, so its `dates` are empty and its `dates_status` says why. An empty
    date table with a stated reason is a measurement; an empty one without is a gap.
    """
    bank = _mod(code).CENTRAL_BANK
    for field in ("name", "policy_instrument", "decision_rule", "announce_utc"):
        assert str(bank.get(field, "")).strip(), f"{code}: central bank missing {field}"
    assert "dates" in bank, f"{code}: central bank has no date table at all"
    assert str(bank.get("dates_status", "")).strip(), (
        f"{code}: the central bank date table has no status -- an empty or partial calendar "
        f"without a stated reason is indistinguishable from one nobody filled in")
    for year, days in bank["dates"].items():
        for day in days:
            parsed = date.fromisoformat(str(day))
            assert parsed.year == int(year), f"{code}: {day} filed under {year}"


@pytest.mark.parametrize("code", CODES)
def test_policy_eras_are_ordered_and_the_last_one_is_open(code: str) -> None:
    """Eras are cut at reaction-function changes, and exactly one is the present.

    A cell fitted across an era boundary is an average over two different markets. The open era
    is the one a live candidate is actually trading, and there must be exactly one.
    """
    eras = _mod(code).POLICY_ERAS
    assert len(eras) >= 4, f"{code}: only {len(eras)} policy eras"
    open_ended = [e for e in eras if not e.get("end")]
    assert len(open_ended) == 1, f"{code}: {len(open_ended)} open eras, need exactly one"
    starts = [date.fromisoformat(str(e["start"])) for e in eras]
    assert starts == sorted(starts), f"{code}: eras are not in chronological order"
    for e in eras:
        for field in ("label", "what_changed", "invalidates"):
            assert str(e.get(field, "")).strip(), f"{code}: era {e['id']} has empty {field}"


# ---------------------------------------------------------------- holidays
@pytest.mark.parametrize("code", CODES)
def test_the_holiday_rule_covers_2024_to_2026_with_valid_dates(code: str) -> None:
    """Three years, every entry an ISO date inside its own year, and a derivation text.

    A table with no rule beside it cannot be extended past the years somebody typed; a rule with
    no table cannot be evaluated, because none of these calendars is computable -- Indonesian
    collective leave comes from a ministerial decree, Philippine holidays from a presidential
    proclamation, and the Vietnamese Tet block from an annual government notification.
    """
    rule = _mod(code).HOLIDAYS_RULE
    assert str(rule.get("rule", "")).strip(), f"{code}: holiday rule has no derivation text"
    assert rule.get("status"), f"{code}: holiday rule does not say which years are confirmed"
    for year in (2024, 2025, 2026):
        table = holiday_table(rule, year)
        assert table, f"{code}: no holiday table for {year}"
        for iso, name in table.items():
            assert date.fromisoformat(iso).year == year, f"{code}: {iso} filed under {year}"
            assert str(name).strip(), f"{code}: {iso} has no name"


@pytest.mark.parametrize(("code", "iso", "needle"), ANCHORS)
def test_the_holiday_rules_reproduce_dates_a_human_already_knows(
        code: str, iso: str, needle: str) -> None:
    """Songkran 2026, Tet 2026 and Hari Raya 2026, asserted by value.

    These four anchors were named by the principal and they are the cheapest possible check that
    somebody actually read the calendar: Songkran 2026 falls on a Monday so the closure is 13-15
    April with no substitution, Tet Binh Ngo begins on 17 February 2026, and Eid al-Fitr 1447
    falls on 20 March 2026 -- which closes Malaysia, Singapore, Indonesia and the Philippines
    within the same two days.
    """
    rule = _mod(code).HOLIDAYS_RULE
    table = holiday_table(rule, int(iso[:4]))
    assert iso in table, f"{code}: {iso} is not in the holiday table"
    assert needle in table[iso].lower(), (
        f"{code}: {iso} is named {table[iso]!r}, which does not mention {needle!r}")
    assert is_closed(rule, date.fromisoformat(iso)), f"{code}: {iso} does not read as closed"


def test_diwali_muhurat_2025_is_a_closure_that_also_carries_a_one_hour_session() -> None:
    """The Indian Diwali day is neither a holiday nor a session, and the pack says both.

    The exchanges close for Laxmi Pujan and then open for a ONE-HOUR ceremonial Muhurat session.
    A day that is both cannot be represented as a boolean, so the pack carries the closure in the
    table and the session in `MUHURAT` -- and a cell that treats the day as a normal session is
    reading an hour of ceremonial volume as a full trading day. The Lakshmi Puja tithi straddled
    20 and 21 October 2025 and the exchanges settled on the 21st, so both are accepted.
    """
    mod = _mod("ind")
    table = holiday_table(mod.HOLIDAYS_RULE, 2025)
    hit = [iso for iso, name in table.items() if "muhurat" in name.lower()]
    assert hit, "no Muhurat day in the 2025 Indian holiday table"
    assert set(hit) <= {"2025-10-20", "2025-10-21"}, f"Muhurat 2025 recorded as {hit}"
    session = mod.MUHURAT[2025]
    assert session["date"] in {"2025-10-20", "2025-10-21"}
    assert session["confirmed"] is True
    assert session["session_utc"], "the Muhurat session has no UTC window"
    assert mod.MUHURAT[2026]["confirmed"] is False, (
        "the 2026 Muhurat session time is set by circular and must stay PROVISIONAL until it "
        "lands -- an invented session window is worse than an absent one")


def test_the_vietnamese_god_of_wealth_day_is_carried_and_is_not_a_closure() -> None:
    """Than Tai day is a TRADING day, which is exactly what makes it useful.

    It is the single largest day of retail gold buying in Vietnam and it falls ten days after Tet.
    Because the market is open, the closure and the physical demand can be separated -- which is
    impossible for almost every other festival seasonal in this department.
    """
    mod = _mod("vn")
    than_tai = mod.HOLIDAYS_RULE["than_tai"]
    assert than_tai[2026] == "2026-02-26"
    assert "2026-02-26" not in holiday_table(mod.HOLIDAYS_RULE, 2026), (
        "Than Tai is not a public holiday and must not appear in the closure table")
    assert not is_closed(mod.HOLIDAYS_RULE, date(2026, 2, 26))


def test_tet_and_chinese_new_year_shut_the_same_week_across_five_of_these_packs() -> None:
    """17 February 2026 closes Vietnam, Singapore, Malaysia, Indonesia and the Philippines.

    A regional liquidity statistic measured across that date is measuring most of Asia being shut,
    not anything about a single country -- which is why the Singaporean and Malaysian packs carry
    it as a stated regional note and why Thailand, which does NOT close, is this department's
    control condition for exactly this.
    """
    for code in ("vn", "sg", "my", "idn", "ph"):
        table = holiday_table(_mod(code).HOLIDAYS_RULE, 2026)
        assert "2026-02-17" in table, f"{code}: 2026-02-17 missing from the 2026 table"
    thai = holiday_table(_mod("th").HOLIDAYS_RULE, 2026)
    assert "2026-02-17" not in thai, (
        "Thailand does not close for the lunar new year, and that asymmetry is the regional "
        "control TH-J depends on")


# ---------------------------------------------------------------- conventions
@pytest.mark.parametrize("code", CODES)
def test_fixings_and_settlement_carry_utc_stamps(code: str) -> None:
    """A fixing without a UTC stamp cannot be joined to a bar.

    Every one of these countries is on a non-daylight-saving offset, which makes the UTC mapping
    constant all year -- the one convenience this region offers a backtest, and worth nothing if
    the stamp is not recorded.
    """
    mod = _mod(code)
    assert len(mod.FIXING_CONVENTIONS) >= 3, f"{code}: only {len(mod.FIXING_CONVENTIONS)} fixings"
    for fix in mod.FIXING_CONVENTIONS:
        for field in ("name", "administrator", "basis", "uses", "note"):
            assert str(fix.get(field, "")).strip(), f"{code}: fixing missing {field}"
        assert "publish_utc" in fix, f"{code}: fixing {fix['name']!r} has no UTC publication time"
    assert len(mod.SETTLEMENT_CONVENTIONS) >= 3
    for row in mod.SETTLEMENT_CONVENTIONS:
        for field in ("market", "cycle", "session_utc", "note"):
            assert str(row.get(field, "")).strip(), f"{code}: settlement row missing {field}"


@pytest.mark.parametrize("code", CODES)
def test_every_exchange_states_an_expiry_rule_even_when_it_has_none(code: str) -> None:
    """Four different expiry rules across this department, and one venue with none at all.

    Vietnam's third Thursday, Malaysia's 15th and last business day, Singapore's second-last
    business day, India's Tuesday since September 2025 -- and the Philippine exchange, which has
    no liquid listed derivative and therefore no expiry mechanism to study. That last one is
    stated explicitly rather than left blank, because a blank reads as an oversight and the
    absence is itself the useful fact: it makes the Philippines a negative control for any
    regional expiry claim.
    """
    for ex in _mod(code).EXCHANGES:
        for field in ("name", "code", "hours_utc", "expiry_rule", "settlement"):
            assert str(ex.get(field, "")).strip(), (
                f"{code}: exchange {ex.get('name')!r} has empty {field}")


@pytest.mark.parametrize("code", CODES)
def test_positioning_sources_state_their_publication_time_and_lag(code: str) -> None:
    """Positioning data is only a signal for the session AFTER it is published.

    NSE participant-wise open interest lands at 18:00 IST, so it is knowable for the next session
    and never for the one it describes. That single distinction is the difference between a flow
    edge and a look-ahead, and it lives in these two fields.
    """
    rows = _mod(code).POSITIONING_SOURCES
    assert len(rows) >= 4, f"{code}: only {len(rows)} positioning sources"
    for row in rows:
        for field in ("name", "root", "fields", "frequency", "licence", "why"):
            assert row.get(field), f"{code}: positioning source missing {field}"
        assert "publish_utc" in row and "lag_days" in row, (
            f"{code}: positioning source {row['name']!r} does not say when it becomes knowable")
        assert float(row["lag_days"]) >= 0.0


def test_the_regional_fixing_instant_is_shared_by_every_restricted_currency_pack() -> None:
    """03:00 UTC is not a country clock, it is Asia's, and five of these packs say so.

    The ABS/SFEMC Asian currency fixings settle the non-deliverable forwards of nine currencies at
    one instant. An apparent single-country fixing effect that has not been checked against the
    other eight is not a finding -- it is the whole region settling at once, and the packs that
    depend on it must name the same clock so a later session can join them.
    """
    for code in ("sg", "idn", "th", "ph", "vn"):
        stamps = [f.get("publish_utc") for f in _mod(code).FIXING_CONVENTIONS]
        assert "03:00" in stamps, (
            f"{code}: the 03:00 UTC regional fixing is not in the fixing table, so this pack "
            f"cannot be cross-checked against its neighbours")


def test_each_pack_is_about_its_own_country_and_not_a_translated_sibling() -> None:
    """Section 46: each country discovers its OWN mechanics rather than inheriting another's.

    The cheapest possible check that seven packs are seven packs: no two may share a domain id
    namespace, and every pack's domain ids must be prefixed with something specific to it. A
    department that produced the same seventeen domains seven times would pass every other test
    in this file.
    """
    seen: dict[str, str] = {}
    for code in CODES:
        ids = {str(d["id"]) for d in _mod(code).DOMAINS}
        for did in ids:
            assert did not in seen, f"domain {did} declared by both {seen[did]} and {code}"
            seen[did] = code
    titles: dict[str, str] = {}
    for code in CODES:
        for dom in _mod(code).DOMAINS:
            title = str(dom["title"]).strip().lower()
            assert title not in titles, (
                f"{code} and {titles[title]} share the domain title {title!r}, which means one "
                f"of them was translated from the other rather than discovered")
            titles[title] = code


def test_the_seven_packs_cover_seven_distinct_currencies_and_one_region_command() -> None:
    """Codes, currencies and the regional routing, asserted once so a copy-paste shows up."""
    codes = [_mod(c).CODE for c in CODES]
    assert codes == ["IN", "SG", "ID", "MY", "TH", "PH", "VN"]
    currencies = [_mod(c).CURRENCY for c in CODES]
    assert len(set(currencies)) == 7, f"duplicate currency across packs: {currencies}"
    commands = {_mod(c).REGION_COMMAND for c in CODES}
    assert commands == {"south_asia", "southeast_asia"}, commands
    fiscal = {c: _mod(c).FISCAL_YEAR_END for c in CODES}
    assert fiscal["ind"] == "03-31", "India's fiscal year ends 31 March"
    assert fiscal["th"] == "09-30", "Thailand's fiscal year ends 30 September"
    assert fiscal["idn"] == "12-31" and fiscal["vn"] == "12-31"
