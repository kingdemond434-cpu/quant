"""THE COPPERBELT PACK, VALIDATED -- two jurisdictions, one orebody, two calendars.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A MULTI-JURISDICTION PACK THAT ANSWERS FOR ONE COUNTRY AND CLAIMS TWO. `JURISDICTIONS` is
    what the parity fence counts, so the tests check that each of `cd` and `zm` owes at least six
    actors and four domains OF ITS OWN -- not two countries' worth of one country's mechanisms
    with a second flag stapled on.
  * AN ENGLISH GLOSSARY OF A FRANCOPHONE STATE AND A BEMBA-SPEAKING MINING PROVINCE. The DRC
    governs, legislates and reports in FRENCH and works in Swahili in Katanga and Lingala in
    Kinshasa; Zambia legislates in English, which is the opposite trap, because an English crawl
    returns something for every Zambian query and reads complete. The assertions below require a
    French phrase in every layer and native vocabulary in all four grounds.
  * A TYPED CALENDAR. Zambia's Easter days come from the anonymous Gregorian algorithm, Heroes'
    Day, Unity Day and Farmers' Day come from weekday rules, the general election day comes from
    the constitutional second-Thursday-of-August rule, and the Sunday substitution is applied --
    all COMPUTED here and checked on dates a human can verify. The DRC's list is solar-only with
    no Easter and no substitution, which is a real asymmetry and is asserted as one.
  * A SYMBOL THE BOX CANNOT TRADE. Every executable instrument and every edge target is checked
    against the broker's OWN registry. CDF and ZMW are absent and must stay transmission targets,
    and COBALT -- the pack's headline mechanism -- has no contract at all and must be routed
    through copper and nickel with the by-product mechanism named.
  * A PROXY PRETENDING TO BE A CURRENCY. The ZAR complex is the executable carrier of Southern
    African risk and the tests require it labelled a PROXY with its control wherever it is used.
  * A SINGLE-NAME EQUITY ON A DOCKET. This region is full of tempting names -- the Katangan
    operators, the Zambian mines, two state holding companies, one of them listed -- and every
    one of them appears as an ACTOR only (two-lane order, 2026-09-06).
  * A PACK THAT REACHES THE FRAMEWORK BENT. `CountryPack` coerces every row; a coercion note is a
    field the framework could not read, and this pack must produce none.
  * A LAYER NOBODY LOOKED AT, and its opposite -- a layer declared absent that is not. The
    app-ecosystem layer here is MOBILE MONEY and two regulators publish its statistics, so the
    tests require it sourced and require the per-jurisdiction refusals to be named in
    `NO_LAWFUL_GROUND` instead.
  * A PACK THAT FORGETS ITS OWN LAWFULNESS. `ACCESS_CONSTRAINTS` must say, in terms, that the
    pack reads public material only, bypasses no access control, and neither collects nor seeks
    personal data about any individual miner.
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
from countries.copperbelt import pack as CB  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as F  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")
CODE = "copperbelt"


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it, resolved through `resolve_pack` so the test measures
    the same object the country lab runs and not a private construction."""
    got = CL.resolve_pack(CODE)
    assert got is not None, "no Copperbelt pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(CB.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == CODE
    assert str(get(built, "region_command")) == "africa"
    assert str(get(built, "currency")) == "CDF"
    assert str(get(built, "fiscal_year_end")) == "12-31"


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


def test_depth_counts_sit_above_a_two_country_floor() -> None:
    """Twelve actors is the floor for ONE country. A pack answering for two owes more, and the
    brief's own floor for this one is 16 actors, 12 domains, 10 edges and 16 datasets."""
    assert len(CB.ACTORS) >= 16
    assert len(CB.DOMAINS) >= 12
    assert len(CB.TRANSMISSION_EDGES_SEED) >= 10
    assert len(CB.DATASETS) >= 16
    assert len(CB.SOURCE_CLASSES) >= 22
    assert len(CB.POLICY_ERAS) >= 8
    assert len(CB.INTERACTIONS) >= 4
    assert CB.term_count() >= 120


# ------------------------------------------------------------------------ the two jurisdictions
def test_jurisdictions_are_exactly_the_two_claimed_and_both_are_on_the_roster() -> None:
    """`JURISDICTIONS` is what `check_regional_parity.jurisdictions_of` counts. A pack that
    answers for two countries and declares one is credited with one."""
    assert CB.JURISDICTIONS == ("cd", "zm")
    assert set(CB.JURISDICTIONS) == {"cd", "zm"}
    for code in CB.JURISDICTIONS:
        assert code == code.lower() and len(code) == 2, f"{code!r} is not a lowercase ISO-2 code"
    roster = {c.lower() for f in F.FORESTS.values() for c in f.countries}
    missing = sorted(set(CB.JURISDICTIONS) - roster)
    assert missing == [], f"{missing} are not on any forest's roster in libs/research/forests.py"
    assert CODE in F.forest("africa").packs, "the africa forest does not draw on this pack"
    for code in CB.JURISDICTIONS:
        assert F.forest_of_country(code) == "africa"


def test_each_jurisdiction_owes_its_own_actors_and_domains() -> None:
    """Six actors and four domains EACH, so the pack cannot be one country wearing two hats."""
    assert len(CB.ACTOR_JURISDICTION) == len(CB.ACTORS)
    for code in CB.JURISDICTIONS:
        actors = [a for a, j in zip(CB.ACTORS, CB.ACTOR_JURISDICTION, strict=True) if j == code]
        assert len(actors) >= 6, f"{code}: only {len(actors)} actors of its own"
        domains = [d for d in CB.DOMAINS
                   if code in CB.DOMAIN_JURISDICTION.get(str(d["id"]), ())]
        assert len(domains) >= 4, f"{code}: only {len(domains)} domains of its own"
    assert set(CB.DOMAIN_JURISDICTION) == {str(d["id"]) for d in CB.DOMAINS}
    assert set(CB.CURRENCIES) == set(CB.JURISDICTIONS)
    assert set(CB.CENTRAL_BANKS) == set(CB.JURISDICTIONS)
    assert set(CB.JURISDICTION_HOLIDAY_FN) == set(CB.JURISDICTIONS)
    assert set(CB.FISCAL_YEAR_ENDS) == set(CB.JURISDICTIONS)
    assert CB.jurisdiction_of_domain("CB-K") == ("cd", "zm")
    assert CB.jurisdiction_of_domain("CB-A") == ("cd",)


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    for row in CB.ACTORS:
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
    for row in CB.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert len(row["conditions"]) >= 3, f"domain {row['id']} names too few conditions"
        assert row["instruments"], f"domain {row['id']} names no instrument"
        assert row["id"] in CB.DOMAIN_MECHANISM and row["id"] in CB.DOMAIN_HORIZON


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(CB.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert "XCUUSD" in CB.EXECUTABLE_INSTRUMENTS, "a Copperbelt pack that cannot trade copper"
    for row in CB.DOMAINS:
        assert resolve(row["instruments"])["equities"] == [], f"domain {row['id']} names an equity"
        assert set(row["instruments"]) <= set(CB.EXECUTABLE_INSTRUMENTS), (
            f"domain {row['id']} names an instrument the pack never declared executable")
    # every declared instrument earns its place: something in the pack actually uses it
    used = {s for d in CB.DOMAINS for s in d["instruments"]}
    unused = sorted(set(CB.EXECUTABLE_INSTRUMENTS) - used)
    assert unused == [], f"declared executable and used by no domain: {unused}"


def test_every_transmission_seed_names_tradable_targets() -> None:
    """A seed that terminates in a symbol the box cannot quote can never compile a cell."""
    for seed in CB.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"
    for row in CB.INTERACTIONS:
        assert resolve(row["targets"])["absent"] == [], f"interaction {row['with']}: absent target"
        assert resolve(row["targets"])["equities"] == []


def test_the_two_currencies_are_named_absent_rather_than_quietly_dropped() -> None:
    """CDF and ZMW are not quoted here and the pack says so twice, with carriers."""
    registry = universe_symbols()
    assert not {"CDF", "ZMW", "USDCDF", "USDZMW"} & set(registry)
    named = " ".join(str(t["name"]) for t in CB.TRANSMISSION_TARGETS)
    for code in ("CDF", "ZMW"):
        assert code in named, f"{code} is not named in TRANSMISSION_TARGETS"
    for row in CB.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == []
        assert row["regime"] and row["route"] and row["why"]


def test_cobalt_has_no_contract_and_is_routed_through_copper_and_nickel() -> None:
    """THE PACK'S HEADLINE MECHANISM HAS NO SYMBOL. Cobalt is a copper and nickel BY-PRODUCT and
    the route has to be stated, not implied, with the competing-supply control named."""
    registry = universe_symbols()
    assert not {"COBALT", "XCOUSD", "CO"} & set(registry)
    row = next(t for t in CB.TRANSMISSION_TARGETS if str(t["name"]).startswith("COBALT"))
    assert set(row["proxies"]) == {"XCUUSD", "XNIUSD"}
    assert "BY-PRODUCT" in str(row["route"]).upper()
    assert "INDONESIA" in str(row["control"]).upper(), (
        "the competing nickel-cobalt supply is the control that decides whether a Congolese "
        "intervention moved the price, and it must be named on the routing row itself")
    edge = next(e for e in CB.TRANSMISSION_EDGES_SEED if e["id"] == "CB-E1")
    assert set(edge["targets"]) == {"XCUUSD", "XNIUSD"}
    assert "INDONESIAN" in str(edge["control"]).upper()


def test_the_zar_complex_is_labelled_a_proxy_wherever_it_carries_something() -> None:
    """A carrier is never a substitute. The rand holds South African idiosyncratic risk that
    neither of these economies has, and every row that routes through it must say so."""
    zar = {"USDZAR", "EURZAR", "GBPZAR", "ZARJPY"}
    assert zar <= set(CB.EXECUTABLE_INSTRUMENTS)
    for row in CB.TRANSMISSION_TARGETS:
        if zar & set(row["proxies"]):
            assert row.get("proxy_warning"), f"{row['name']} routes through the rand silently"
    carriers = [e for e in CB.TRANSMISSION_EDGES_SEED if zar & set(e["targets"])]
    assert carriers, "no edge uses the carrier at all, which cannot be right"
    for edge in carriers:
        assert "SARB" in str(edge["control"]).upper(), (
            f"edge {edge['id']} routes through the rand without naming the SARB calendar")
    za = next(r for r in CB.INTERACTIONS if r["with"] == "za")
    assert "CARRIER IS NOT A SUBSTITUTE" in str(za["control"]).upper()


def test_cot_and_retail_flow_are_declared_absent_rather_than_silently_missing() -> None:
    """No COT contract and no retail margin statistic exists for either. An absence a study can
    trip over must be named."""
    absent = [r for r in CB.POSITIONING_SOURCES if not r["available"]]
    assert len(absent) >= 2, "the COT and retail-flow questions are not both answered"
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in absent)
    blob = " ".join(f"{r['name']} {r['why']} {r['pit_warning']}" for r in absent)
    for must in ("CDF", "ZMW", "retail margin", "Securities and Exchange Commission"):
        assert must in blob, f"the declared absences never mention {must!r}"


# ------------------------------------------------------------------------------ the languages
def test_terminology_carries_french_swahili_lingala_and_bemba_nyanja() -> None:
    """Four native grounds. The DRC is a FRANCOPHONE state whose gazette, mining code and central
    bank all publish in French; Katanga works in Swahili and Kinshasa in Lingala; and Zambia
    legislates in English while its Copperbelt argues in Bemba and Nyanja."""
    assert len(CB.french_terms()) == len(CB.FRENCH_MARKERS), (
        f"missing French vocabulary: {sorted(set(CB.FRENCH_MARKERS) - set(CB.french_terms()))}")
    assert len(CB.swahili_terms()) == len(CB.SWAHILI_MARKERS), (
        f"missing Swahili vocabulary: {sorted(set(CB.SWAHILI_MARKERS) - set(CB.swahili_terms()))}")
    assert len(CB.lingala_terms()) == len(CB.LINGALA_MARKERS)
    assert len(CB.bemba_nyanja_terms()) == len(CB.BEMBA_NYANJA_MARKERS)
    flat = {t for group in CB.TERMINOLOGY.values() for t in group}
    for must in ("cuivre", "cobalt", "redevance minière", "code minier", "délestage",
                 "Journal Officiel", "creuseur artisanal"):
        assert must in flat, f"the Copperbelt pack does not carry {must!r}"
    for must in ("shaba", "wachimbaji", "umukuba", "magetsi", "mbongo"):
        assert must in flat, f"the Copperbelt pack does not carry {must!r}"
    assert CB.has_french("redevance minière") and not CB.has_french("mineral royalty")
    assert CB.has_swahili("bei ya dola leo") and not CB.has_swahili("copper output")
    assert CB.has_lingala("sango ya mbongo") and not CB.has_lingala("news about money")
    assert CB.has_bemba_nyanja("umukuba na indalama") and not CB.has_bemba_nyanja("copper price")
    assert len(CB.TERMINOLOGY) >= 12
    assert set(CB.TERMINOLOGY) == {str(d["id"]) for d in CB.DOMAINS}


def test_every_layer_is_queried_in_french_and_in_a_local_language() -> None:
    """A query in English finds an English article about the decree, not the decree."""
    terms = CB.layer_terms()
    assert set(terms) == set(CB.SOURCE_LAYERS)
    french = [layer for layer, qs in terms.items() if any(CB.has_french(q) for q in qs)]
    native = [layer for layer, qs in terms.items() if any(CB.has_native(q) for q in qs)]
    assert len(french) == 10, f"only {french} carry a French query"
    assert len(native) == 10, f"only {native} carry a native-language query"
    local = sum(1 for layer, qs in terms.items() for q in qs
                if CB.has_swahili(q) or CB.has_lingala(q) or CB.has_bemba_nyanja(q))
    assert local >= 30, f"only {local} queries in Swahili, Lingala, Bemba or Nyanja"
    crawlable = sum(1 for row in CB.SOURCE_CLASSES if row["machine_use_allowed"]
                    for q in row["queries"] if CB.has_native(q))
    assert crawlable >= 60, f"only {crawlable} native queries across crawlable sources"


def test_every_source_declaring_a_native_language_actually_queries_in_it() -> None:
    """A source that lists `fr` or `sw` and queries only in English is an English source wearing
    a flag, and it is how a crawl reads the wrong half of a bilingual country."""
    for row in CB.SOURCE_CLASSES:
        if set(row["languages"]) & {"fr", "sw", "ln", "bem", "ny"}:
            assert any(CB.has_native(q) for q in row["queries"]), (
                f"{row['id']} declares {row['languages']} and every query is in English")


def test_every_source_carries_three_independent_labels_and_a_query() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in CB.SOURCE_CLASSES:
        assert row["access_label"] in CB.ACCESS_LABELS
        assert row["credibility"] in CB.CREDIBILITY_LABELS
        assert row["predictive_state"] in CB.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no query"
        assert row["roots"], f"{row['id']} has no crawlable root"
        assert row["notes"], f"{row['id']} has no note saying why it is here"


def test_all_ten_source_layers_are_populated_and_the_refusals_are_named() -> None:
    """The depth rule: ten layers, none blank. The app layer here is MOBILE MONEY and declaring it
    absent because there is no trading-app ecology would be reading the wrong country."""
    counts = CB.layer_counts()
    assert set(counts) == set(CB.SOURCE_LAYERS)
    blank = [layer for layer, n in counts.items() if not n]
    assert blank == [], f"blank layers: {blank}"
    coverage = CB.source_layer_coverage()
    assert coverage["n_layers_covered"] == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible for a region whose "
        "cobalt price assessment and copper balance both live behind publishers' terms")
    assert coverage["low_weight_kept"], "no fringe ground is kept at all, so it was dropped"
    assert counts["app_ecosystem"] >= 1
    mobile = [s for s in CB.SOURCE_CLASSES if s["layer"] == "app_ecosystem"
              and "MOBILE MONEY" in str(s["label"]).upper()]
    assert mobile, "the app layer does not name mobile money, which IS the app layer here"
    # the measured refusals are per JURISDICTION and per layer, not whole-pack
    assert CB.LAYER_ABSENCES == {}
    assert len(CB.NO_LAWFUL_GROUND) >= 5
    for row in CB.NO_LAWFUL_GROUND:
        assert row["jurisdiction"] in CB.JURISDICTIONS
        assert row["layer"] in CB.SOURCE_LAYERS
        assert len(row["reason"]) > 60, f"{row['jurisdiction']}/{row['layer']}: reason too thin"
    # the DRC has no securities market at all and that is a measured refusal, not an omission
    inst = [r for r in CB.NO_LAWFUL_GROUND
            if r["jurisdiction"] == "cd" and r["layer"] == "institutional"]
    assert inst, "the absence of any Congolese securities market is not declared anywhere"


def test_query_territories_give_the_deep_forest_miner_three_phrases_per_layer() -> None:
    assert set(CB.QUERY_TERRITORIES) == set(CB.SOURCE_LAYERS)
    for layer, phrases in CB.QUERY_TERRITORIES.items():
        assert len(phrases) >= 3, f"{layer}: only {len(phrases)} query territories"
        assert any(CB.has_native(p) for p in phrases), f"{layer}: no native-language phrase"


def test_the_pack_states_its_lawfulness_and_its_refusal_to_collect_personal_data() -> None:
    """PUBLIC SOURCES ONLY, NO ACCESS CONTROL BYPASSED, AND NO PERSONAL DATA ABOUT ANY MINER.
    Artisanal mining and the cobalt chain carry well-documented human-rights concerns; the desk
    records what is PUBLISHED about production, flows and policy and nothing else."""
    blob = " ".join(f"{r['constraint']} {r['measured']} {r['consequence']}"
                    for r in CB.ACCESS_CONSTRAINTS).upper()
    assert "BYPASSES AN ACCESS CONTROL" in blob
    assert "PERSONAL DATA ABOUT ANY INDIVIDUAL MINER" in blob
    assert "PUBLIC" in blob
    assert len(CB.ACCESS_CONSTRAINTS) >= 6
    for row in CB.ACCESS_CONSTRAINTS:
        assert row["constraint"] and row["measured"] and row["consequence"]


# ------------------------------------------------------------------------------ the calendars
def test_easter_comes_from_the_anonymous_gregorian_algorithm() -> None:
    """Three Zambian statutory days move with this one number, so it is computed and not typed."""
    assert CB.easter(2024) == date(2024, 3, 31)
    assert CB.easter(2025) == date(2025, 4, 20)
    assert CB.easter(2026) == date(2026, 4, 5)
    assert CB.easter(2027) == date(2027, 3, 28)
    zm2025 = CB.zambian_holidays(2025)
    assert date(2025, 4, 18) in zm2025, "Good Friday 2025"
    assert date(2025, 4, 19) in zm2025, "HOLY SATURDAY is a Zambian public holiday"
    assert date(2025, 4, 21) in zm2025, "Easter Monday 2025"
    # THE ASYMMETRY: the DRC's statutory list is solar-only and closes for no Easter day at all
    cd2025 = CB.congolese_holidays(2025)
    assert date(2025, 4, 18) not in cd2025
    assert date(2025, 4, 21) not in cd2025


def test_the_zambian_moveable_days_are_derived_from_their_weekday_rules() -> None:
    """Heroes' Day is the first Monday of July, Unity Day the Tuesday after it, Farmers' Day the
    first Monday of August -- derived, so the calendar extends past the years somebody typed."""
    assert CB.heroes_day(2024) == date(2024, 7, 1)
    assert CB.heroes_day(2025) == date(2025, 7, 7)
    assert CB.heroes_day(2026) == date(2026, 7, 6)
    assert CB.unity_day(2025) == date(2025, 7, 8)
    assert CB.unity_day(2025).weekday() == 1, "Unity Day is always the Tuesday"
    assert CB.farmers_day(2024) == date(2024, 8, 5)
    assert CB.farmers_day(2025) == date(2025, 8, 4)
    assert CB.farmers_day(2026) == date(2026, 8, 3)
    assert CB.nth_weekday(2026, 8, 3, 2) == date(2026, 8, 13)


def test_the_general_election_day_is_a_constitutional_rule_and_not_a_typed_date() -> None:
    """Zambia's President can declare a public holiday by statutory instrument, and the recurring
    case is the general election -- the SECOND THURSDAY OF AUGUST every fifth year from 2016."""
    assert CB.zambian_election_day(2016) == date(2016, 8, 11)
    assert CB.zambian_election_day(2021) == date(2021, 8, 12)
    assert CB.zambian_election_day(2026) == date(2026, 8, 13)
    assert CB.zambian_election_day(2024) is None
    assert CB.zambian_election_day(2011) is None, "before the anchor year, no derivation is made"
    assert CB.zambian_election_day(2026).weekday() == 3
    declared = CB.declared_closures(2026)
    assert date(2026, 8, 13) in declared
    assert "SCHEDULED" in declared[date(2026, 8, 13)], (
        "a date the law fixes and the instrument has not yet signed is SCHEDULED, never assumed")
    assert all(status in ("DECLARED", "SCHEDULED", "PRESS_REPORTED")
               for *_rest, status in CB.DECLARED_CLOSURES)


def test_the_sunday_substitution_is_zambian_and_the_drc_substitutes_nothing() -> None:
    """The Public Holidays Act moves a Sunday holiday to the Monday; the DRC moves nothing, so a
    Congolese holiday on a weekend costs no session at all. That asymmetry is a session count."""
    zm2024 = CB.zambian_holidays(2024)
    assert date(2024, 4, 28) in zm2024 and date(2024, 4, 28).weekday() == 6
    assert date(2024, 4, 29) in zm2024, "Kenneth Kaunda Day 2024 was a Sunday and moved"
    assert "observed" in zm2024[date(2024, 4, 29)]
    zm2026 = CB.zambian_holidays(2026)
    assert date(2026, 10, 19) in zm2026, "National Day of Prayer 2026 is a Sunday and moves"
    # the DRC: Independence Day 2024 fell on a Sunday and no Monday was substituted
    cd2024 = CB.congolese_holidays(2024)
    assert date(2024, 6, 30) in cd2024 and date(2024, 6, 30).weekday() == 6
    assert date(2024, 7, 1) not in cd2024
    assert "substitutes nothing" in CB.HOLIDAYS_RULE["substitution_rule"]


def test_the_holiday_tables_resolve_for_three_years_and_stay_inside_them() -> None:
    for year in (2024, 2025, 2026):
        table = holiday_table(CB.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        assert f"{year}-01-01" in table, "New Year is missing"
        assert f"{year}-05-01" in table, "Labour Day is missing"
        for code in CB.JURISDICTIONS:
            assert CB.JURISDICTION_HOLIDAY_FN[code](year), f"{code} has no {year} table"
    # the union rows are TAGGED, because a day that closes Lubumbashi is a session in Kitwe
    t25 = holiday_table(CB.HOLIDAYS_RULE, 2025)
    assert "[CD]" in t25["2025-06-30"], "Congolese Independence Day closes the DRC alone"
    assert "[ZM]" in t25["2025-10-24"], "Zambian Independence Day closes Zambia alone"
    assert "[CD+ZM]" in t25["2025-01-01"], "New Year closes both"
    assert CB.closed_in("cd", date(2025, 6, 30))
    assert not CB.closed_in("zm", date(2025, 6, 30))
    assert CB.both_closed(date(2025, 1, 1))
    assert not CB.both_closed(date(2025, 10, 24))
    assert not CB.is_market_holiday(date(2025, 3, 4))
    # market_holidays drops weekend closures, and the Sunday substitution has already moved the
    # Zambian ones onto the Monday where they cost a session
    assert all(d.weekday() < 5 for d in CB.market_holidays(2025))


def test_central_african_time_never_moves_and_the_drc_spans_two_zones() -> None:
    """No daylight saving anywhere, so every window is stable in UTC -- and the DRC's own two-zone
    split puts the central bank an hour behind the copper, which is easy to miss and real."""
    assert "NO DAYLIGHT SAVING" in CB.HOLIDAYS_RULE["rule"].upper()
    assert "UTC+1" in str(CB.CENTRAL_BANK["announce_local"])
    assert "UTC+2" in str(CB.CENTRAL_BANK["announce_local"])
    windows = {w["name"]: w for w in CB.SESSION_WINDOWS}
    assert windows["cb_shanghai_close"]["end_utc"] < windows["cb_lme_ring"]["start_utc"], (
        "the Shanghai close must precede the LME ring, which is the sequence any lead claim on "
        "XCUUSD needs")
    for fx in CB.FIXING_CONVENTIONS:
        if "LME" not in fx["name"] and "LBMA" not in fx["name"]:
            assert fx["time_utc"] == fx["time_utc_dst"], f"{fx['name']} moves with a DST rule"


# ------------------------------------------------------------------------------ the mechanisms
def test_the_cobalt_export_regime_has_three_states_and_two_dated_boundaries() -> None:
    """The February 2025 suspension and the October 2025 quota partition every Congolese
    cobalt series; a study pooled across them measures a free regime and an administered one."""
    assert CB.COBALT_BAN_DATE.isoformat() == "2025-02-22"
    assert CB.COBALT_QUOTA_DATE.isoformat() == "2025-10-16"
    assert CB.cobalt_export_regime(date(2025, 1, 1)) == "FREE"
    assert CB.cobalt_export_regime(date(2025, 2, 21)) == "FREE"
    assert CB.cobalt_export_regime(date(2025, 2, 22)) == "SUSPENDED"
    assert CB.cobalt_export_regime(date(2025, 9, 30)) == "SUSPENDED"
    assert CB.cobalt_export_regime(date(2025, 10, 16)) == "QUOTA"
    assert CB.cobalt_export_regime(date(2026, 6, 1)) == "QUOTA"
    assert {j for _d, j, _w, _s in CB.COBALT_POLICY_EVENTS} == {"cd"}
    assert all(st in ("GAZETTED", "PRESS_REPORTED") for *_r, st in CB.COBALT_POLICY_EVENTS), (
        "a cobalt-policy date is either gazetted or PRESS_REPORTED and is never presented as a "
        "citation it is not")


def test_the_kariba_hydrological_year_and_the_power_emergency_have_their_own_clocks() -> None:
    """The lake fills December to April, peaks May to August and is at its minimum September to
    November -- which is when the constraint actually binds."""
    assert CB.kariba_season(date(2025, 1, 15)) == "RAINS_INFLOW"
    assert CB.kariba_season(date(2025, 12, 20)) == "RAINS_INFLOW"
    assert CB.kariba_season(date(2025, 6, 15)) == "PEAK_STORAGE"
    assert CB.kariba_season(date(2025, 10, 15)) == "DRAWDOWN_MINIMUM"
    assert CB.DROUGHT_DISASTER_DATE.isoformat() == "2024-02-29"
    assert CB.load_shedding_phase(date(2024, 1, 1)) == "NORMAL"
    assert CB.load_shedding_phase(date(2024, 2, 29)) == "DECLARED_DISASTER"
    assert CB.load_shedding_phase(date(2024, 6, 1)) == "DEEP"
    assert CB.load_shedding_phase(date(2024, 12, 15)) == "DEEP"
    assert CB.load_shedding_phase(date(2025, 6, 1)) == "EASING"


def test_the_four_corridors_and_the_lobito_reopening() -> None:
    """Exactly four roads to the sea, each with its own chokepoint and its own failure mode, and
    only one of them has a dated reopening -- which is what makes the share a treatment."""
    assert len(CB.EXPORT_ROUTES) == 4
    routes = {r["route"] for r in CB.EXPORT_ROUTES}
    assert routes == {"durban", "dar_es_salaam", "beira_nacala", "lobito"}
    for row in CB.EXPORT_ROUTES:
        assert row["port"] and row["mode"] and row["chokepoint"] and row["failure_mode"]
        assert row["approx_km"] > 0
    siblings = {r["sibling_pack"] for r in CB.EXPORT_ROUTES if r["sibling_pack"]}
    assert siblings == {"za", "east_africa"}
    assert CB.lobito_phase(date(2022, 1, 1)) == "CLOSED_TO_COPPER"
    assert CB.lobito_phase(date(2023, 8, 1)) == "CONCESSION_SIGNED"
    assert CB.lobito_phase(date(2024, 6, 1)) == "FIRST_COPPER"
    assert CB.lobito_phase(date(2026, 1, 1)) == "RAMP"
    assert CB.corridor_state(date(2022, 1, 1))["lobito"] == "CLOSED_TO_COPPER"
    assert CB.corridor_state(date(2025, 6, 1))["lobito"] == "RAMP"
    assert CB.corridor_state(date(2025, 6, 1))["durban"] == "OPEN"


def test_the_zambian_fiscal_sequence_is_dated_on_both_halves() -> None:
    """Six sovereign states across five dated boundaries, and a royalty deductibility clause
    that was withdrawn in 2019 and restored in 2022."""
    assert CB.ZM_DEFAULT_DATE.isoformat() == "2020-11-13"
    assert CB.zambia_debt_phase(date(2020, 10, 1)) == "PRE_DEFAULT"
    assert CB.zambia_debt_phase(date(2020, 10, 20)) == "GRACE_PERIOD"
    assert CB.zambia_debt_phase(date(2020, 11, 13)) == "DEFAULT"
    assert CB.zambia_debt_phase(date(2022, 8, 31)) == "IMF_PROGRAMME"
    assert CB.zambia_debt_phase(date(2023, 9, 1)) == "OCC_AGREEMENT"
    assert CB.zambia_debt_phase(date(2025, 1, 1)) == "BONDS_EXCHANGED"
    assert CB.royalty_deductible(date(2018, 6, 1)) is True
    assert CB.royalty_deductible(date(2019, 1, 1)) is False
    assert CB.royalty_deductible(date(2021, 12, 31)) is False
    assert CB.royalty_deductible(date(2022, 1, 1)) is True
    eras = {str(e["name"]) for e in CB.POLICY_ERAS}
    assert any("default" in n.lower() for n in eras)
    assert any(str(e["start"]) == "2025-02-22" for e in CB.POLICY_ERAS), (
        "the cobalt intervention must have an era row of its own")


# ------------------------------------------------------------------------------ the cells
def test_the_pack_mints_cells_inside_its_domains_and_not_as_a_cartesian_blow_up() -> None:
    """A cell is only worth a trial if this pack's own data plane can evaluate its CONDITION on
    that SYMBOL, so the cross product is taken INSIDE each domain."""
    rows = CB.cells()
    assert 60 <= len(rows) <= 200, f"{len(rows)} cells is outside the honest range"
    assert len(rows) == len(CB.CELLS)
    assert len({r["cell_id"] for r in rows}) == len(rows), "duplicate cell_id"
    domain_ids = {str(d["id"]) for d in CB.DOMAINS}
    for row in rows:
        for field in ("cell_id", "domain", "symbol", "condition", "mechanism_family",
                      "horizon", "control", "why"):
            assert row[field], f"{row['cell_id']}: {field} is empty"
        assert row["domain"] in domain_ids
        assert row["symbol"] in CB.EXECUTABLE_INSTRUMENTS
        assert set(row["jurisdictions"]) <= set(CB.JURISDICTIONS)
    assert resolve(sorted({r["symbol"] for r in rows}))["equities"] == []
    # every domain mints at least one cell, so no domain is decorative
    assert {r["domain"] for r in rows} == domain_ids


def test_every_dataset_carries_all_twelve_fields_and_a_fetchable_route() -> None:
    from countries import DATASET_FIELDS
    for ds in CB.DATASETS:
        for field in DATASET_FIELDS:
            if field in ("pit_feasible", "publication_lag_days"):
                continue
            assert ds[field], f"dataset {ds.get('name')!r}: {field} is empty"
        assert float(ds["publication_lag_days"]) >= 0.0
        assert len(str(ds["how_to_fetch"])) > 40, (
            f"dataset {ds['name']!r}: how_to_fetch is not concrete enough for a collector")
        assert resolve(ds["assets"])["equities"] == []
        assert resolve(ds["assets"])["absent"] == []
    # the pages that overwrite in place must be honest about their point-in-time feasibility
    not_pit = {str(d["name"]) for d in CB.DATASETS if not d["pit_feasible"]}
    assert any("Kariba" in n for n in not_pit), (
        "the daily lake-level page overwrites in place and cannot be pit_feasible")


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {f"custom:{name}" for name in CB.MINERS}
    assert all(callable(fn) for fn in got.values())
    ids = {str(d["id"]) for d in CB.DOMAINS}
    entries = set()
    for row in CB.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.copperbelt.pack", row["entry"]
        assert callable(getattr(CB, func)), f"{row['entry']} does not resolve"
        entries.add(func)
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    assert entries == set(CB.MINERS)
    for did in CB.MINER_DOMAINS.values():
        assert set(did) <= ids


def test_mine_returns_a_report_and_emits_nothing_without_a_context() -> None:
    """`mine(None)` is how a test and a fresh session check the pack with nothing wired: it must
    return a report and must not try to record anywhere."""
    report = CB.mine(None)
    assert report["code"] == CODE
    assert tuple(report["jurisdictions"]) == CB.JURISDICTIONS
    assert report["emitted"] == 0, "mine(None) emitted to a registry that does not exist"
    assert report["rows"], "mine(None) produced no rows at all"
    assert report["cells_emitted"] == len(CB.cells())
    assert report["at"].endswith("+00:00"), "the stamp must be timezone-aware UTC"
    assert set(report["miners"]) == set(CB.MINERS)
    assert report["layers_covered"] == 10
    assert report["datasets"] == len(CB.DATASETS)
    assert "east_africa" in report["interactions"], (
        "the Dar es Salaam Central Corridor is this pack's export route and that pack's port")
    assert report["unmeasured"], "no miner declared anything UNMEASURED, which is implausible"
    for row in report["rows"]:
        assert row["kind"] == "hypothesis"
        assert row["symbols"], "a donated row with no instrument compiles to nothing"
        assert resolve(row["symbols"])["absent"] == []
        assert resolve(row["symbols"])["equities"] == []


def test_mine_emits_through_a_context_when_one_is_given() -> None:
    """The same call with a Ctx must hand every row over and count what was taken."""
    class _Ctx:
        def __init__(self) -> None:
            self.rows: list[dict[str, Any]] = []

        def record(self, row: dict[str, Any]) -> None:
            self.rows.append(row)

    ctx = _Ctx()
    report = CB.mine(ctx)
    assert report["emitted"] == len(ctx.rows) == len(report["rows"])
    assert report["emitted"] > 0


def test_the_interactions_name_real_sibling_packs_with_a_control() -> None:
    """An edge whose control lives in a pack nobody runs is an edge nobody can falsify."""
    from countries import codes
    present = set(codes())
    for row in CB.INTERACTIONS:
        assert row["with"] in present, f"interaction names {row['with']!r}, which is not a pack"
        assert row["mechanism"] and row["observable"] and row["control"]
        assert row["targets"]
    assert CB.INTERACTIONS[0]["with"] == "east_africa", (
        "the Dar es Salaam Central Corridor and the Tanzanian port are this pack's copper export "
        "route, so the two packs are ONE PHYSICAL SYSTEM and it belongs first")
    named = {r["with"] for r in CB.INTERACTIONS}
    assert {"cl", "pe"} <= named, (
        "Chile is the world's largest copper producer and Peru is the country the DRC overtook; "
        "both are the controls that decide whether a Copperbelt supply event is about the "
        "Copperbelt or about copper")
    # the sibling packs this one must NOT duplicate are answered elsewhere and not claimed here
    assert not ({"za", "ng", "ke", "gh", "eg", "et", "tz", "ug"} & set(CB.JURISDICTIONS))
