"""THE RED SEA PACK, VALIDATED -- five jurisdictions, two weekends, one strait.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A FIVE-COUNTRY PACK THAT ANSWERS FOR ONE AND CLAIMS FIVE. `JURISDICTIONS` is what the parity
    fence counts, so the tests check that each of `ye`, `dj`, `sd`, `er` and `so` owes at least
    three actors and two domains OF ITS OWN -- not one country's mechanisms with four flags on.
  * A CHOKEPOINT CLAIM WITH NO CONTROL. Bab el-Mandeb alone cannot tell a chokepoint effect from
    a Red Sea effect. PANAMA -- constrained in the same eighteen months by drought, counted
    daily by the same publisher -- must be named in the primary domain, in the edges and in the
    miners' rows, and the tests assert it in all three places.
  * A SATURDAY-SUNDAY WEEKEND. Four of these five work SUNDAY TO THURSDAY and Eritrea works
    MONDAY TO FRIDAY. The tests check that Friday is a working day in exactly one of the five,
    that Sunday is a working day in exactly four, and that Saturday is a working day in none.
  * A TYPED ORTHODOX CALENDAR. Eritrea's Fasika is the Julian computus, Ldet and Timket are
    fixed JULIAN dates, and Kudus Yohannes alternates on the Ge'ez leap rule. All four are
    COMPUTED here and checked on dates a human can verify; only the moon-sighted Islamic feasts
    are typed, and they carry their sighting authority.
  * AN ENGLISH GLOSSARY OF FOUR NON-ENGLISH GROUNDS. Arabic, French, Tigrinya and Somali all
    carry ground here, and Somali and French are LATIN-SCRIPT so a codepoint test would call
    them English. The detectors are vocabulary-based and the tests assert on them.
  * A SYMBOL THE BOX CANNOT TRADE. Every executable instrument and every edge target is checked
    against the broker's OWN registry. YER, DJF, SDG, ERN and SOS are absent and must stay
    transmission targets, and so must freight, war-risk premia, gum arabic and potash.
  * A DECLARED ABSENCE WITH NO SUBSTITUTE. Eritrea's six refusals are this pack's most valuable
    output and each one must name the lawful substitute that carries the information instead.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from countries import (  # type: ignore[import-not-found]  # noqa: E402
    check_pack,
    get,
    holiday_table,
    resolve,
    universe_symbols,
)
from countries.red_sea import pack as RS  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as F  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")
CODE = "red_sea"


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it, resolved through `resolve_pack` so the test measures
    the same object the country lab runs and not a private construction."""
    got = CL.resolve_pack(CODE)
    assert got is not None, "no Red Sea pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(RS.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == CODE
    assert str(get(built, "region_command")) == "mea"
    assert str(get(built, "currency")) == "YER"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    """A coercion note is a field `CountryPack` could not read. There must be none."""
    notes = list(getattr(built, "coercion_notes", ()) or ())
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on this pack: {fatal[:4]}"


def test_pack_reaches_parity_depth(built: Any) -> None:
    """The standing depth rule, measured by the framework and not claimed by the pack."""
    row = RP.pack_depth(built, CODE).as_row()
    assert row["score"] == 1.0, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_depth_counts_sit_above_a_five_country_floor() -> None:
    """Twelve actors is the floor for ONE country. A pack answering for five owes more, and the
    brief's own floor for this one is 20 actors, 14 domains, 12 edges and 18 datasets."""
    assert len(RS.ACTORS) >= 20
    assert len(RS.DOMAINS) >= 14
    assert len(RS.TRANSMISSION_EDGES_SEED) >= 12
    assert len(RS.DATASETS) >= 18
    assert len(RS.SOURCE_CLASSES) >= 28
    assert len(RS.POLICY_ERAS) >= 8
    assert len(RS.INTERACTIONS) >= 4
    assert RS.term_count() >= 150


# ----------------------------------------------------------------------- the five jurisdictions
def test_jurisdictions_are_exactly_the_five_claimed_and_all_are_on_the_roster() -> None:
    """`JURISDICTIONS` is what `check_regional_parity.jurisdictions_of` counts. A pack that
    answers for five countries and declares one is credited with one."""
    assert RS.JURISDICTIONS == ("ye", "dj", "sd", "er", "so")
    assert set(RS.JURISDICTIONS) == {"ye", "dj", "sd", "er", "so"}
    for code in RS.JURISDICTIONS:
        assert code == code.lower() and len(code) == 2, f"{code!r} is not a lowercase ISO-2 code"
    roster = {c.lower() for f in F.FORESTS.values() for c in f.countries}
    missing = sorted(set(RS.JURISDICTIONS) - roster)
    assert missing == [], f"{missing} are not on any forest's roster in libs/research/forests.py"
    assert CODE in F.forest("mena").packs, "the mena forest does not draw on this pack"
    for code in RS.JURISDICTIONS:
        assert F.forest_of_country(code) == "mena"


def test_each_jurisdiction_owes_its_own_actors_and_domains() -> None:
    """Three actors and two domains EACH, so the pack cannot be one country wearing five hats."""
    assert len(RS.ACTOR_JURISDICTION) == len(RS.ACTORS)
    for code in RS.JURISDICTIONS:
        actors = [a for a, j in zip(RS.ACTORS, RS.ACTOR_JURISDICTION, strict=True) if j == code]
        assert len(actors) >= 3, f"{code}: only {len(actors)} actors of its own"
        domains = [d for d in RS.DOMAINS
                   if code in RS.DOMAIN_JURISDICTION.get(str(d["id"]), ())]
        assert len(domains) >= 2, f"{code}: only {len(domains)} domains of its own"
    assert set(RS.DOMAIN_JURISDICTION) == {str(d["id"]) for d in RS.DOMAINS}
    assert set(RS.CURRENCIES) == set(RS.JURISDICTIONS)
    assert set(RS.CENTRAL_BANKS) == set(RS.JURISDICTIONS)
    assert set(RS.JURISDICTION_HOLIDAY_FN) == set(RS.JURISDICTIONS)
    assert set(RS.WEEKEND_DAYS) == set(RS.JURISDICTIONS)
    assert set(RS.SIGHTING_AUTHORITIES) == set(RS.JURISDICTIONS)


def test_both_yemeni_central_banks_are_carried(built: Any) -> None:
    """ONE COUNTRY, TWO MONETARY AUTHORITIES, TWO ROOTS. A crawl that takes one of them and calls
    the result 'the Central Bank of Yemen' produces a rial series that is half a country."""
    roots = {r for s in RS.SOURCE_CLASSES for r in s["roots"]}
    assert any("cby-ye.com" in r for r in roots), "the Aden central bank root is missing"
    assert any("centralbank.gov.ye" in r for r in roots), "the Sana'a root is missing"
    aden = next(s for s in RS.SOURCE_CLASSES if s["id"] == "rs_ye_cby_aden")
    sanaa = next(s for s in RS.SOURCE_CLASSES if s["id"] == "rs_ye_cby_sanaa")
    assert aden["credibility"] == "AUTHORITATIVE"
    assert sanaa["credibility"] == "RELIABLE", (
        "the Sana'a authority's standing is contested and the label must say so rather than "
        "either dropping the source or promoting it")
    assert "second_authority" in RS.CENTRAL_BANKS["ye"]
    assert str(get(built, "central_bank").framework) == "managed_float"


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    for row in RS.ACTORS:
        for f in ACTOR_FIELDS:
            assert row.get(f), f"actor {row.get('name')!r} has an empty {f}"
        # a one-element tuple written without its trailing comma silently becomes a string, and
        # `tuple("abc")` is then three characters -- this catches that class of typo
        for f in ("forced_to", "information", "constraints", "instruments", "counterparties",
                  "observables"):
            value = row[f]
            assert isinstance(value, tuple), f"actor {row.get('name')!r}.{f} is not a tuple"
            assert all(len(str(v)) > 2 for v in value), (
                f"actor {row.get('name')!r}.{f} looks like a string split into characters -- a "
                f"single-element tuple needs its trailing comma")


def test_every_domain_has_objects_and_two_negative_controls() -> None:
    """Without a control an effect cannot be told from the desk's own sampling."""
    for row in RS.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert row["conditions"], f"domain {row['id']} names no conditioning state"
        assert row["instruments"], f"domain {row['id']} names no instrument"


# ------------------------------------------------------------------------ the chokepoint object
def test_the_chokepoint_is_the_primary_domain_and_panama_is_its_control() -> None:
    """Two chokepoints constrained in the same eighteen months by completely unrelated causes is
    the cleanest identification available, and it must be IN the pack rather than in its prose."""
    primary = next(d for d in RS.DOMAINS if d["id"] == "RS-A")
    assert "BAB EL-MANDEB" in primary["title"].upper()
    assert any("PANAMA" in c.upper() for c in primary["controls"]), (
        "the primary chokepoint domain does not name Panama as a control")
    assert RS.PANAMA_CONTROL["chokepoint"] == "Panama Canal"
    assert "DROUGHT" in str(RS.PANAMA_CONTROL["cause"]).upper()
    assert RS.PANAMA_CONTROL["start"] < RS.CRISIS_START < RS.PANAMA_CONTROL["end"], (
        "the two constraints must OVERLAP in time or Panama is not a contemporaneous control")
    # the control reaches the edges and the datasets, not just one domain's prose
    assert any("PANAMA" in str(e["control"]).upper() for e in RS.TRANSMISSION_EDGES_SEED)
    assert any("PANAMA" in str(d["name"]).upper() for d in RS.DATASETS), (
        "the Panama transit series is not a dataset, so no collector would ever fetch it")


def test_the_chokepoint_phases_are_dated_and_ordered() -> None:
    """Five phases, because the mechanism changed three times and the announced truce did NOT
    restore transits -- which is the most informative boundary of the four."""
    assert RS.chokepoint_phase(date(2023, 11, 18)) == "PRE_CRISIS"
    assert RS.chokepoint_phase(date(2023, 11, 19)) == "ATTACKS_BEGIN"
    assert RS.chokepoint_phase(date(2023, 12, 15)) == "CARRIER_SUSPENSION"
    assert RS.chokepoint_phase(date(2024, 1, 12)) == "SUSTAINED_DIVERSION"
    assert RS.chokepoint_phase(date(2025, 5, 6)) == "ANNOUNCED_TRUCE_LOW_RETURN"
    assert RS.panama_constrained(date(2023, 12, 1)), "the control constraint must be live here"
    assert not RS.panama_constrained(date(2023, 1, 1))
    assert not RS.panama_constrained(date(2025, 6, 1))
    assert RS.war_risk_regime(date(2023, 11, 18)) == "BASELINE"
    assert RS.war_risk_regime(date(2024, 6, 1)) == "PLATEAU"
    assert all(st in ("OFFICIAL", "PRESS_REPORTED") for *_rest, st in RS.CHOKEPOINT_EVENTS), (
        "a chokepoint date is either OFFICIAL or PRESS_REPORTED and never presented as a "
        "citation it is not")
    days = [d for d, *_ in RS.CHOKEPOINT_EVENTS]
    assert days == sorted(days), "the dated event table is out of order"


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(RS.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert set(RS.EXECUTABLE_INSTRUMENTS) <= set(registry)
    for row in RS.DOMAINS:
        assert resolve(row["instruments"])["equities"] == [], f"domain {row['id']} names an equity"
        assert set(row["instruments"]) <= set(RS.EXECUTABLE_INSTRUMENTS), (
            f"domain {row['id']} names an instrument the pack never declared executable")


def test_every_transmission_seed_names_tradable_targets() -> None:
    """A seed that terminates in a symbol the box cannot quote can never compile a cell."""
    for seed in RS.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"
    for row in RS.INTERACTIONS:
        assert resolve(row["targets"])["absent"] == [], f"interaction {row['with']}: absent target"
        assert resolve(row["targets"])["equities"] == []


def test_the_five_currencies_and_the_freight_complex_are_named_absent() -> None:
    """Five currencies, one of them quoted twice; freight, war risk, gum arabic and potash. Every
    one is absent from the broker and every one is routed explicitly with a carrier named."""
    registry = universe_symbols()
    assert not {"YER", "DJF", "SDG", "ERN", "SOS", "USDYER", "USDSDG"} & set(registry)
    named = " ".join(str(t["name"]) for t in RS.TRANSMISSION_TARGETS)
    for code in ("YER", "DJF", "SDG", "ERN", "SOS"):
        assert code in named, f"{code} is not named in TRANSMISSION_TARGETS"
    for thing in ("FREIGHT", "WAR-RISK", "GUM ARABIC", "POTASH"):
        assert thing in named.upper(), f"{thing} is not named in TRANSMISSION_TARGETS"
    for row in RS.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == []
        assert row["regime"] and row["route"] and row["why"]
    freight = next(r for r in RS.TRANSMISSION_TARGETS
                   if "FREIGHT" in str(r["name"]).upper())
    assert "TRANSMISSION" in str(freight["route"]).upper(), (
        "the pack must say that freight is the TRANSMISSION and the commodity is the leg")


def test_cot_and_retail_flow_are_declared_absent_rather_than_silently_missing() -> None:
    """No COT contract, no retail margin statistic, and for Eritrea no national statistic at all.
    An absence a study can trip over must be named."""
    absent = [r for r in RS.POSITIONING_SOURCES if not r["available"]]
    assert len(absent) >= 3, "the COT, retail-flow and Eritrean questions are not all answered"
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in absent)
    blob = " ".join(f"{r['name']} {r['why']} {r['pit_warning']}" for r in absent)
    for must in ("YER", "DJF", "SDG", "ERN", "SOS", "retail margin", "MIRROR CUSTOMS"):
        assert must in blob, f"the declared absences never mention {must!r}"


# ------------------------------------------------------------------------------ the languages
def test_terminology_carries_arabic_geez_somali_and_french() -> None:
    """Four native grounds, two of them LATIN-SCRIPT. A codepoint test would call every Somali
    and French phrase English and quietly conclude those grounds do not exist."""
    assert len(RS.arabic_terms()) >= 60, f"only {len(RS.arabic_terms())} Arabic terms"
    assert len(RS.geez_terms()) >= 20, f"only {len(RS.geez_terms())} Ge'ez terms"
    flat = {t for group in RS.TERMINOLOGY.values() for t in group}
    for marker in RS.SOMALI_MARKERS:
        assert any(marker in RS._words(t) for t in flat), f"no Somali term carries {marker!r}"
    for marker in RS.FRENCH_MARKERS:
        assert any(marker in RS._words(t) for t in flat), f"no French term carries {marker!r}"
    for must in ("باب المندب", "البحر الأحمر", "الريال اليمني", "الصمغ العربي", "قناة السويس"):
        assert must in flat, f"the Red Sea pack does not carry {must!r}"
    for must in ("ባንክ ኤርትራ", "ናቕፋ", "ወደብ ምጽዋዕ"):
        assert must in flat, f"the Red Sea pack does not carry {must!r}"
    assert RS.has_arabic("سعر الصرف") and not RS.has_arabic("exchange rate")
    assert RS.has_geez("ናቕፋ ሸርፊ") and not RS.has_geez("nakfa")
    assert RS.has_somali("dekedda Berbera") and not RS.has_somali("Berbera port")
    assert RS.has_french("trafic portuaire conteneurs") and not RS.has_french("container traffic")
    assert not RS.has_french("Panama Canal transit route"), (
        "words spelled the same in English must never be French markers, or an English query "
        "passes as native ground -- which is the exact failure the detector exists to catch")
    assert len(RS.TERMINOLOGY) >= 15
    assert set(RS.TERMINOLOGY) == {str(d["id"]) for d in RS.DOMAINS}


def test_every_layer_is_queried_in_arabic_and_the_other_three_reach_most_of_them() -> None:
    """A query in English finds an English article about the release, not the release. Arabic is
    the basin's lingua franca and must reach every layer; the other three reach their own."""
    terms = RS.layer_terms()
    assert set(terms) == set(RS.SOURCE_LAYERS)
    arabic = [layer for layer, qs in terms.items() if any(RS.has_arabic(q) for q in qs)]
    assert len(arabic) == 10, f"only {arabic} carry an Arabic query"
    for detector, floor, label in ((RS.has_geez, 6, "Ge'ez"), (RS.has_somali, 6, "Somali"),
                                   (RS.has_french, 6, "French")):
        hit = [layer for layer, qs in terms.items() if any(detector(q) for q in qs)]
        assert len(hit) >= floor, f"only {hit} carry a {label} query"
    native = sum(1 for row in RS.SOURCE_CLASSES if row["machine_use_allowed"]
                 for q in row["queries"] if RS.has_native(q))
    assert native >= 100, f"only {native} native-language queries across crawlable sources"


def test_every_source_declaring_a_native_language_actually_queries_in_it() -> None:
    """A source that lists `ar`, `fr`, `ti` or `so` and queries only in English is an English
    source wearing a flag, and it is how a crawl reads the wrong half of a bilingual country."""
    for row in RS.SOURCE_CLASSES:
        if set(row["languages"]) & {"ar", "fr", "ti", "so"}:
            assert any(RS.has_native(q) for q in row["queries"]), (
                f"{row['id']} declares {row['languages']} and every query is in English")


def test_every_source_carries_three_independent_labels_and_a_query() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in RS.SOURCE_CLASSES:
        assert row["access_label"] in RS.ACCESS_LABELS
        assert row["credibility"] in RS.CREDIBILITY_LABELS
        assert row["predictive_state"] in RS.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no query"
        assert row["roots"], f"{row['id']} has no crawlable root"
        assert row["notes"], f"{row['id']} has no note saying why it is here"


def test_all_ten_layers_are_populated_and_the_refusals_name_their_substitutes() -> None:
    """The depth rule: ten layers, none blank. The refusals here are PER JURISDICTION, and this
    is the pack where each one must also name the lawful substitute that carries the
    information instead -- a refusal with no substitute is a shrug."""
    counts = RS.layer_counts()
    assert set(counts) == set(RS.SOURCE_LAYERS)
    blank = [layer for layer, n in counts.items() if not n]
    assert blank == [], f"blank layers: {blank}"
    coverage = RS.source_layer_coverage()
    assert coverage["n_layers_covered"] == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible for a region whose "
        "freight indices and vessel-tracking portals both forbid automated extraction")
    assert coverage["low_weight_kept"], "no fringe ground is kept at all, so it was dropped"
    assert counts["app_ecosystem"] >= 1
    mobile = [s for s in RS.SOURCE_CLASSES if s["layer"] == "app_ecosystem"
              and "MOBILE MONEY" in str(s["label"]).upper()]
    assert mobile, "the app layer does not name mobile money, which IS the app layer here"
    assert RS.LAYER_ABSENCES == {}
    assert len(RS.NO_LAWFUL_GROUND) >= 10
    for row in RS.NO_LAWFUL_GROUND:
        assert row["jurisdiction"] in RS.JURISDICTIONS
        assert row["layer"] in RS.SOURCE_LAYERS
        assert len(row["reason"]) > 60, f"{row['jurisdiction']}/{row['layer']}: reason too thin"
        assert len(row["substitute"]) > 60, (
            f"{row['jurisdiction']}/{row['layer']}: a refusal with no named lawful substitute is "
            f"a shrug, not a measurement")
    assert set(RS.JURISDICTIONS) == {r["jurisdiction"] for r in RS.NO_LAWFUL_GROUND}, (
        "every one of the five has at least one genuine layer refusal and the pack must say so")


def test_eritrea_is_the_limit_case_and_declares_six_layers_absent() -> None:
    """The honest refusal is this pack's most valuable output. Eritrea publishes almost nothing,
    and that is a MEASUREMENT with a named substitute for every layer it costs."""
    er = [r for r in RS.NO_LAWFUL_GROUND if r["jurisdiction"] == "er"]
    assert len(er) >= 6, f"Eritrea declares only {len(er)} absent layers"
    layers = {r["layer"] for r in er}
    for must in ("official", "institutional", "academic", "retail_ecology", "app_ecosystem"):
        assert must in layers, f"Eritrea does not declare the {must} layer absent"
    blob = " ".join(r["substitute"] for r in er).upper()
    for must in ("MIRROR CUSTOMS", "EXCHANGE FILINGS", "IMF", "NIGHT-LIGHT"):
        assert must in blob, f"no Eritrean substitute names {must!r}"
    gaps = {g["id"] for g in RS.JURISDICTION_LAYER_GAPS}
    assert {f"er:{layer}" for layer in layers} <= gaps
    assert len(RS.JURISDICTION_LAYER_GAPS) == len(RS.NO_LAWFUL_GROUND)


def test_query_territories_give_the_deep_forest_miner_three_phrases_per_layer() -> None:
    assert set(RS.QUERY_TERRITORIES) == set(RS.SOURCE_LAYERS)
    for layer, phrases in RS.QUERY_TERRITORIES.items():
        assert len(phrases) >= 3, f"{layer}: only {len(phrases)} query territories"
        assert any(RS.has_native(p) for p in phrases), f"{layer}: no native-language phrase"


# ------------------------------------------------------------------------------ the calendars
def test_the_working_week_splits_four_ways_against_one() -> None:
    """THE PACK'S DISTINGUISHING CALENDAR FACT. Four of the five work Sunday to Thursday and
    Eritrea works Monday to Friday, so a Saturday-Sunday weekend assumption misaligns four."""
    friday, saturday, sunday, monday = (date(2025, 1, 3), date(2025, 1, 4), date(2025, 1, 5),
                                        date(2025, 1, 6))
    assert RS.working_jurisdictions(friday) == ("er",), (
        "Friday is a working day in Eritrea alone -- and a full trading day in London")
    assert set(RS.working_jurisdictions(sunday)) == {"ye", "dj", "sd", "so"}, (
        "Sunday is a full business day in four of the five and a weekend everywhere this desk "
        "executes")
    assert RS.working_jurisdictions(saturday) == (), "Saturday is closed in all five"
    assert len(RS.working_jurisdictions(monday)) == 5
    assert RS.WEEKEND_DAYS["er"] == (5, 6)
    for code in ("ye", "dj", "sd", "so"):
        assert RS.WEEKEND_DAYS[code] == (4, 5), f"{code} does not keep a Friday-Saturday weekend"
        assert RS.working_week(code) == "Sunday to Thursday"
    assert RS.working_week("er") == "Monday to Friday"
    assert RS.UNIVERSAL_CLOSED_WEEKDAY == 5
    assert "MONDAY TO FRIDAY" in RS.HOLIDAYS_RULE["rule"].upper()
    assert "SUNDAY TO THURSDAY" in RS.HOLIDAYS_RULE["rule"].upper()


def test_the_eritrean_orthodox_feasts_are_computed_and_not_typed() -> None:
    """Fasika is MEEUS' JULIAN computus; Ldet and Timket are fixed JULIAN dates and therefore
    land on 7 and 19 January Gregorian this century; Kudus Yohannes alternates on the Ge'ez leap
    rule. All four are arithmetic, so typing them would be a wrong table rather than an honest
    one."""
    assert RS.orthodox_easter(2024) == date(2024, 5, 5)
    assert RS.orthodox_easter(2025) == date(2025, 4, 20)
    assert RS.orthodox_easter(2026) == date(2026, 4, 12)
    assert RS.julian_to_gregorian(2024, 12, 25) == date(2025, 1, 7)
    for year in (2024, 2025, 2026):
        assert RS.ldet(year) == date(year, 1, 7)
        assert RS.timket(year) == date(year, 1, 19)
    # Kudus Yohannes is 12 September in the year FOLLOWING a Ge'ez leap year
    assert RS.geez_new_year(2022) == date(2022, 9, 11)
    assert RS.geez_new_year(2023) == date(2023, 9, 12)
    assert RS.geez_new_year(2024) == date(2024, 9, 11)
    assert RS.geez_new_year(2027) == date(2027, 9, 12)
    assert RS.meskel(2023) == date(2023, 9, 28)
    assert RS.meskel(2024) == date(2024, 9, 27)
    assert RS.orthodox_easter(2025) in RS.eritrean_holidays(2025)
    assert RS.geez_new_year(2025) in RS.eritrean_holidays(2025)


def test_the_holiday_tables_resolve_for_three_years_and_stay_inside_them() -> None:
    for year in (2024, 2025, 2026):
        table = holiday_table(RS.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        assert f"{year}-01-01" in table, "New Year is missing"
        assert f"{year}-01-07" in table, "Ldet is missing"
        for code in RS.JURISDICTIONS:
            assert RS.JURISDICTION_HOLIDAY_FN[code](year), f"{code} has no {year} table"
    # the union rows are TAGGED, because a day that closes Asmara is a business day in Aden
    table_2025 = holiday_table(RS.HOLIDAYS_RULE, 2025)
    assert "[ER]" in table_2025["2025-05-24"], "Independence Day closes Eritrea alone"
    assert "[YE]" in table_2025["2025-05-22"], "Unity Day closes Yemen alone"
    assert "[DJ]" in table_2025["2025-06-27"], "Independence Day closes Djibouti alone"
    assert RS.closed_in("er", date(2025, 2, 10)), "Fenkil Day, a Monday, closes Eritrea"
    assert not RS.closed_in("ye", date(2025, 2, 10)), "and it is a normal Monday in Yemen"
    assert RS.closed_in("ye", date(2025, 5, 22)), "Unity Day, a Thursday, closes Yemen"
    assert not RS.closed_in("er", date(2025, 5, 22)), "and it is a normal Thursday in Asmara"
    # closed_in folds in the LOCAL weekend, which differs between the five
    assert RS.closed_in("ye", date(2025, 1, 3)) and not RS.closed_in("er", date(2025, 1, 3))
    assert RS.closed_in("er", date(2025, 1, 5)) and not RS.closed_in("ye", date(2025, 1, 5))


def test_the_moon_sighted_feasts_are_declared_with_six_sighting_authorities() -> None:
    """Six authorities announce across five countries and Aden and Sana'a have declared Eid on
    DIFFERENT DAYS inside one country. A rule would be a wrong rule."""
    assert "sighting" in RS.HOLIDAYS_RULE["rule"].lower()
    assert "PROJECTED" in str(RS.HOLIDAYS_RULE["status"][2026]).upper()
    announced = RS.announced_dates(2025)
    assert date(2025, 3, 31) in announced, "Eid al-Fitr 2025 is 2025-03-31"
    assert date(2025, 6, 7) in announced, "Eid al-Adha 2025 is 2025-06-07"
    assert all(st in ("ANNOUNCED", "PROJECTED")
               for rows in RS.LUNAR_HOLIDAYS.values() for *_, st in rows)
    assert all(st == "PROJECTED" for *_, st in RS.LUNAR_HOLIDAYS[2026]), (
        "a 2026 sighting cannot already be announced")
    # Eritrea does NOT close for Ashura and the other four do -- a real per-country asymmetry
    assert date(2025, 7, 6) in RS.yemeni_holidays(2025)
    assert date(2025, 7, 6) in RS.somali_holidays(2025)
    assert date(2025, 7, 6) not in RS.eritrean_holidays(2025)
    assert "ANNOUNCE SEPARATELY" in RS.SIGHTING_AUTHORITIES["ye"].upper()
    assert "SOMALILAND" in RS.SIGHTING_AUTHORITIES["so"].upper()


def test_no_daylight_saving_anywhere_in_the_five() -> None:
    """None of the five observes DST, so every window is stable in UTC all year -- with the one
    exception of the London benchmarks, which are marked."""
    assert "no daylight saving" in RS.HOLIDAYS_RULE["rule"].lower()
    for fx in RS.FIXING_CONVENTIONS:
        if fx["dst_rule"] == "GMT/BST":
            assert fx["time_utc"] != fx["time_utc_dst"], f"{fx['name']} claims a DST rule it has"
        else:
            assert fx["time_utc"] == fx["time_utc_dst"], f"{fx['name']} moves with a DST rule"
    windows = {w["name"]: w for w in RS.SESSION_WINDOWS}
    assert windows["rs_transit_day"]["start_utc"] == "00:00", (
        "the AIS transit day is a UTC day and it is the only 24-hour window in this pack")


# ------------------------------------------------------------------------------ the mechanisms
def test_the_two_rial_regimes_are_dated_and_the_spread_only_exists_in_the_third() -> None:
    """One country, two banknote series, two published rates. A two-rate cell compiled before
    2019-12-18 is compiled on a series that did not exist."""
    assert RS.CBY_RELOCATION.isoformat() == "2016-09-18"
    assert RS.BANKNOTE_BAN.isoformat() == "2019-12-18"
    assert RS.rial_regime(date(2016, 9, 17)) == "UNIFIED"
    assert RS.rial_regime(date(2016, 9, 18)) == "SPLIT_ADMINISTRATION"
    assert RS.rial_regime(date(2019, 12, 17)) == "SPLIT_ADMINISTRATION"
    assert RS.rial_regime(date(2019, 12, 18)) == "TWO_BANKNOTE_SERIES"
    assert RS.rial_regime(date(2026, 1, 1)) == "TWO_BANKNOTE_SERIES"
    eras = {str(e["name"]) for e in RS.POLICY_ERAS}
    assert any("two banknote series" in n.lower() for n in eras)
    assert any(str(e["start"]) == "2019-12-18" for e in RS.POLICY_ERAS)
    assert RS.sudan_regime(date(2021, 2, 20)) == "MANAGED"
    assert RS.sudan_regime(date(2021, 2, 21)) == "FLOATED_PROGRAMME"
    assert RS.sudan_regime(date(2023, 4, 15)) == "WAR"


def test_the_djibouti_currency_board_is_the_packs_null() -> None:
    """A published rate that has not changed since 1973 is worth more as a control than any of
    the four moving rates is worth as a signal."""
    assert pytest.approx(177.721) == RS.DJF_PEG
    assert RS.djf_peg_deviation(177.721) == pytest.approx(0.0)
    assert RS.djf_peg_deviation(179.5) == pytest.approx(100.16, abs=0.5)
    assert RS.djf_peg_deviation(176.0) < 0.0
    assert RS.CENTRAL_BANKS["dj"]["framework"] == "peg"
    board = next(e for e in RS.POLICY_ERAS if "currency board" in str(e["name"]).lower())
    assert board["start"].startswith("1973")
    control = next(d for d in RS.DOMAINS if d["id"] == "RS-H")
    assert "CONTROL" in control["title"].upper()


def test_the_hajj_livestock_clock_moves_through_the_solar_calendar() -> None:
    """The Islamic year is about eleven days shorter, so the season WALKS BACKWARDS and a
    calendar-month seasonal adjustment removes the wrong thing."""
    assert RS.eid_al_adha(2024) == date(2024, 6, 16)
    assert RS.eid_al_adha(2025) == date(2025, 6, 7)
    assert RS.eid_al_adha(2026) == date(2026, 5, 27)
    assert RS.eid_al_adha(2030) is None, (
        "a moon sighting past the typed horizon must return None, not an invented date")
    w2024, w2025, w2026 = (RS.hajj_livestock_window(y) for y in (2024, 2025, 2026))
    assert w2024 is not None and w2025 is not None and w2026 is not None
    assert w2024[0] == date(2024, 4, 21) and w2024[1] == date(2024, 6, 19)
    assert w2025[0] == date(2025, 4, 12)
    assert w2026[0] == date(2026, 4, 1)
    # each season opens EARLIER than the last -- that is the whole mechanism
    assert ((w2026[0].month, w2026[0].day) < (w2025[0].month, w2025[0].day)
            < (w2024[0].month, w2024[0].day))
    assert RS.livestock_season_phase(date(2025, 5, 1)) == "PEAK_BUILD"
    assert RS.livestock_season_phase(date(2025, 6, 9)) == "POST_FEAST_TROUGH"
    assert RS.livestock_season_phase(date(2025, 1, 15)) == "OFF_SEASON"


def test_the_gum_arabic_season_has_its_own_crop_year() -> None:
    """Tapping opens in October, so a February session belongs to the season that opened the
    previous October and bucketing by calendar year splits every season in half."""
    assert RS.gum_arabic_season(date(2025, 10, 15)) == "TAPPING"
    assert RS.gum_arabic_season(date(2025, 1, 15)) == "MAIN_AUCTION"
    assert RS.gum_arabic_season(date(2025, 5, 15)) == "SHIPPING_TAIL"
    assert RS.gum_arabic_season(date(2025, 7, 15)) == "OFF_SEASON"
    assert RS.gum_season_year(date(2025, 2, 1)) == 2024
    assert RS.gum_season_year(date(2024, 11, 1)) == 2024


# ------------------------------------------------------------------------------ the cells
def test_the_pack_mints_cells_inside_its_domains_and_not_as_a_cartesian_blow_up() -> None:
    """Eighteen domains against twenty-one instruments would be 378 cells the data plane cannot
    fill. A cell is only worth a trial if this pack's own series can evaluate its CONDITION on
    that SYMBOL, so the cross product is taken INSIDE each domain."""
    rows = RS.cells()
    assert 60 <= len(rows) <= 200, f"{len(rows)} cells is outside the honest range"
    assert len(rows) == len(RS.CELLS)
    assert len({r["cell_id"] for r in rows}) == len(rows), "duplicate cell_id"
    domain_ids = {str(d["id"]) for d in RS.DOMAINS}
    for row in rows:
        for field in ("cell_id", "domain", "symbol", "condition", "mechanism_family",
                      "horizon", "control", "why"):
            assert row[field], f"{row['cell_id']}: {field} is empty"
        assert row["domain"] in domain_ids
        assert row["symbol"] in RS.EXECUTABLE_INSTRUMENTS
        assert set(row["jurisdictions"]) <= set(RS.JURISDICTIONS)
    assert resolve(sorted({r["symbol"] for r in rows}))["equities"] == []
    # every domain mints at least one cell, so no domain is decorative
    assert {r["domain"] for r in rows} == domain_ids
    # the chokepoint domain is the biggest single block, because it is the pack's primary object
    per_domain = {d: sum(1 for r in rows if r["domain"] == d) for d in domain_ids}
    assert per_domain["RS-A"] == max(per_domain.values())


def test_every_dataset_carries_all_twelve_fields_and_a_fetchable_route() -> None:
    from countries import DATASET_FIELDS
    for ds in RS.DATASETS:
        for field in DATASET_FIELDS:
            if field in ("pit_feasible", "publication_lag_days"):
                continue
            assert ds[field], f"dataset {ds.get('name')!r}: {field} is empty"
        assert float(ds["publication_lag_days"]) >= 0.0
        assert len(str(ds["how_to_fetch"])) > 40, (
            f"dataset {ds['name']!r}: how_to_fetch is not concrete enough for a collector")
        assert resolve(ds["assets"])["equities"] == []
        assert set(ds["assets"]) <= set(RS.EXECUTABLE_INSTRUMENTS)
    # the revised and overwriting series must be honest about point-in-time feasibility
    not_pit = {str(d["name"]) for d in RS.DATASETS if not d["pit_feasible"]}
    assert any("PortWatch" in n for n in not_pit), (
        "the PortWatch series is revised and cannot be pit_feasible")
    assert any("Aden and Sana'a" in n for n in not_pit), (
        "the exchange-house pages overwrite in place and cannot be pit_feasible")


# ------------------------------------------------------------------------------ law and access
def test_the_access_constraints_state_the_lawfulness_of_this_pack() -> None:
    """Several of the five are under sanctions and several are active conflict zones. The
    boundaries are written down rather than assumed."""
    blob = " ".join(f"{r['constraint']} {r['measured']} {r['consequence']}"
                    for r in RS.ACCESS_CONSTRAINTS).upper()
    for must in ("SANCTIONS", "TRANSACT", "PUBLIC", "PERSONAL DATA", "UNMEASURED"):
        assert must in blob, f"ACCESS_CONSTRAINTS never mentions {must!r}"
    assert "CASUALTY" in blob, (
        "the pack must say that conflict datasets are used for dated boundaries only")
    assert len(RS.ACCESS_CONSTRAINTS) >= 8
    for row in RS.ACCESS_CONSTRAINTS:
        assert row["constraint"] and row["measured"] and row["consequence"]


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {f"custom:{name}" for name in RS.MINERS}
    assert all(callable(fn) for fn in got.values())
    ids = {str(d["id"]) for d in RS.DOMAINS}
    entries = set()
    for row in RS.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.red_sea.pack", row["entry"]
        assert callable(getattr(RS, func)), f"{row['entry']} does not resolve"
        entries.add(func)
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    assert entries == set(RS.MINERS)
    for did in RS.MINER_DOMAINS.values():
        assert set(did) <= ids


def test_mine_returns_a_report_and_emits_nothing_without_a_context() -> None:
    """`mine(None)` is how a test and a fresh session check the pack with nothing wired: it must
    return a report and must not try to record anywhere."""
    report = RS.mine(None)
    assert report["code"] == CODE
    assert tuple(report["jurisdictions"]) == RS.JURISDICTIONS
    assert report["emitted"] == 0, "mine(None) emitted to a registry that does not exist"
    assert report["rows"], "mine(None) produced no rows at all"
    assert report["cells_emitted"] == len(RS.cells())
    assert report["at"].endswith("+00:00"), "the stamp must be timezone-aware UTC"
    assert set(report["miners"]) == set(RS.MINERS)
    assert report["layers_covered"] == 10
    assert report["datasets"] == len(RS.DATASETS)
    assert report["control_chokepoint"] == "Panama Canal"
    assert "eg" in report["interactions"], (
        "Egypt owns the other end of the same waterway and must be named as an interaction")
    assert report["unmeasured"], "no miner declared anything UNMEASURED, which is implausible"
    for row in report["rows"]:
        assert row["kind"] == "hypothesis"
        assert row["symbols"], "a donated row with no instrument compiles to nothing"
        assert resolve(row["symbols"])["absent"] == []
    # the chokepoint rows must carry the control on every row, not in a note somewhere
    choke = [r for r in report["rows"] if r.get("domain") == "RS-A"]
    assert choke and all("panama_constrained" in r for r in choke), (
        "a chokepoint row without the Panama flag is a Red Sea claim that cannot be told from a "
        "chokepoint claim")
    # Eritrea's refusals reach the registry as rows rather than living only in a table
    er_rows = [r for r in report["rows"] if r.get("jurisdiction") == "er"]
    assert len(er_rows) >= 6 and all(r.get("substitute") for r in er_rows)


def test_mine_emits_through_a_context_when_one_is_given() -> None:
    """The same call with a Ctx must hand every row over and count what was taken."""
    class _Ctx:
        def __init__(self) -> None:
            self.rows: list[dict[str, Any]] = []

        def record(self, row: dict[str, Any]) -> None:
            self.rows.append(row)

    ctx = _Ctx()
    report = RS.mine(ctx)
    assert report["emitted"] == len(ctx.rows) == len(report["rows"])
    assert report["emitted"] > 0


def test_the_interactions_name_real_sibling_packs_with_a_control() -> None:
    """An edge whose control lives in a pack nobody runs is an edge nobody can falsify."""
    from countries import codes
    present = set(codes())
    for row in RS.INTERACTIONS:
        assert row["with"] in present, f"interaction names {row['with']!r}, which is not a pack"
        assert row["mechanism"] and row["observable"] and row["control"]
        assert row["targets"]
    assert RS.INTERACTIONS[0]["with"] == "eg", (
        "Egypt owns the OTHER END of the same waterway and its canal revenue is the published "
        "measure of what this pack's disruption cost -- it belongs first")
    named = {r["with"] for r in RS.INTERACTIONS}
    for must in ("eg", "east_africa", "sa", "ae", "gulf"):
        assert must in named, f"the pack claims no interaction with {must!r}"
    assert "sa" in named and "gulf" in named, (
        "the Hajj livestock clock is a DEMAND series in the Gulf packs and a SUPPLY series here, "
        "and only both together identify it")
