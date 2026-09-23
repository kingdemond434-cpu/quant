"""THE WEST AFRICA PACK, VALIDATED -- five jurisdictions, one peg, one floating control.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A MULTI-JURISDICTION PACK THAT ANSWERS FOR ONE COUNTRY AND CLAIMS FIVE. `JURISDICTIONS` is
    what the parity fence counts, so the tests check that each of `ci`, `gn`, `ml`, `bf` and `sn`
    owes at least three actors and two domains OF ITS OWN -- not five countries' worth of Ivorian
    cocoa with four flags stapled on.
  * A FRENCH-ONLY GLOSSARY OF A GROUND THAT ARGUES IN FIVE LANGUAGES. French is official in all
    five and it is the trap in the other direction from an anglophone pack: a French crawl reads
    the STATE completely and the FARMGATE not at all. The assertions below require French in
    every layer AND require Manding, Wolof, Pular and Moore to be present where those grounds
    are actually argued.
  * A TYPED EASTER. The Christian movable feasts are COMPUTED from the Gregorian computus here
    and the tests check them on dates a human can verify; the Islamic feasts and the Magal are
    TYPED with their sighting authority, because six announcing bodies across five countries
    cannot be reproduced by a rule and a wrong rule is worse than an honest table.
  * A SYMBOL THE BOX CANNOT TRADE. Every executable instrument and every edge target is checked
    against the broker's OWN registry. XOF and GNF are absent and must stay transmission targets,
    and so must bauxite, alumina, iron ore, cashew and the BRVM.
  * A SINGLE-NAME EQUITY ON A DOCKET. This region is full of tempting single names -- the cocoa
    grinders, the bauxite consortia, the gold operators, the Moroccan-owned banks -- and every
    one of them appears as an ACTOR only (two-lane order, 2026-09-06).
  * A PACK THAT REACHES THE FRAMEWORK BENT. `CountryPack` coerces every row; a coercion note is
    a field the framework could not read, and this pack must produce none.
  * A LAYER NOBODY LOOKED AT, and its opposite -- a refusal that is really just work not done.
    The per-jurisdiction refusals here (Mali's and Burkina's academic grounds, Guinea's
    securities layer) must each NAME A LAWFUL SUBSTITUTE, because an absent ground with a named
    mirror is a measurable jurisdiction and an absent ground with nothing behind it is not.
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
from countries.west_africa import pack as WA  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as F  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")
CODE = "west_africa"


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it, resolved through `resolve_pack` so the test measures
    the same object the country lab runs and not a private construction."""
    got = CL.resolve_pack(CODE)
    assert got is not None, "no West Africa pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(WA.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == CODE
    assert str(get(built, "region_command")) == "africa"
    assert str(get(built, "currency")) == "XOF"


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
    assert len(WA.ACTORS) >= 20
    assert len(WA.DOMAINS) >= 14
    assert len(WA.TRANSMISSION_EDGES_SEED) >= 12
    assert len(WA.DATASETS) >= 18
    assert len(WA.SOURCE_CLASSES) >= 26
    assert len(WA.POLICY_ERAS) >= 8
    assert len(WA.INTERACTIONS) >= 4
    assert WA.term_count() >= 150


# ------------------------------------------------------------------------ the five jurisdictions
def test_jurisdictions_are_exactly_the_five_claimed_and_all_are_on_the_roster() -> None:
    """`JURISDICTIONS` is what `check_regional_parity.jurisdictions_of` counts. A pack that
    answers for five countries and declares one is credited with one."""
    assert WA.JURISDICTIONS == ("ci", "gn", "ml", "bf", "sn")
    assert set(WA.JURISDICTIONS) == {"ci", "gn", "ml", "bf", "sn"}
    for code in WA.JURISDICTIONS:
        assert code == code.lower() and len(code) == 2, f"{code!r} is not a lowercase ISO-2 code"
    roster = {c.lower() for f in F.FORESTS.values() for c in f.countries}
    missing = sorted(set(WA.JURISDICTIONS) - roster)
    assert missing == [], f"{missing} are not on any forest's roster in libs/research/forests.py"
    assert CODE in F.forest("africa").packs, "the africa forest does not draw on this pack"
    for code in WA.JURISDICTIONS:
        assert F.forest_of_country(code) == "africa"


def test_each_jurisdiction_owes_its_own_actors_and_domains() -> None:
    """Three actors and two domains EACH, so the pack cannot be one country wearing five hats."""
    assert len(WA.ACTOR_JURISDICTION) == len(WA.ACTORS)
    for code in WA.JURISDICTIONS:
        actors = [a for a, j in zip(WA.ACTORS, WA.ACTOR_JURISDICTION, strict=True) if j == code]
        assert len(actors) >= 3, f"{code}: only {len(actors)} actors of its own"
        domains = [d for d in WA.DOMAINS
                   if code in WA.DOMAIN_JURISDICTION.get(str(d["id"]), ())]
        assert len(domains) >= 2, f"{code}: only {len(domains)} domains of its own"
    assert set(WA.DOMAIN_JURISDICTION) == {str(d["id"]) for d in WA.DOMAINS}
    assert set(WA.CURRENCIES) == set(WA.JURISDICTIONS)
    assert set(WA.CENTRAL_BANKS) == set(WA.JURISDICTIONS)
    assert set(WA.JURISDICTION_HOLIDAY_FN) == set(WA.JURISDICTIONS)
    assert set(WA.FISCAL_YEAR_ENDS) == set(WA.JURISDICTIONS)


def test_four_of_the_five_share_one_currency_and_the_fifth_is_the_control() -> None:
    """The institutional fact this pack is built on: one central bank for four of the five, and
    a floating fifth that makes the peg a measurable regime rather than a background fact."""
    assert [WA.CURRENCIES[c] for c in ("ci", "ml", "bf", "sn")] == ["XOF"] * 4
    assert WA.CURRENCIES["gn"] == "GNF"
    assert WA.CENTRAL_BANK["framework"] == "peg"
    assert WA.CENTRAL_BANKS["gn"]["framework"] == "managed_float"
    assert all(WA.CENTRAL_BANKS[c]["framework"] == "peg" for c in ("ci", "ml", "bf", "sn"))
    assert pytest.approx(655.957) == WA.XOF_PER_EUR


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    for row in WA.ACTORS:
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
    for row in WA.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert len(row["conditions"]) >= 2, f"domain {row['id']} names too few conditions"
        assert row["instruments"], f"domain {row['id']} names no instrument"
    assert set(WA.DOMAIN_MECHANISM) == {str(d["id"]) for d in WA.DOMAINS}
    assert set(WA.DOMAIN_HORIZON) == {str(d["id"]) for d in WA.DOMAINS}


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(WA.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert set(WA.EXECUTABLE_INSTRUMENTS) <= set(registry)
    for must in ("UKCOCOA", "USCOCOA", "XAUUSD", "XALUSD", "COTTON", "EURUSD"):
        assert must in WA.EXECUTABLE_INSTRUMENTS, f"{must} is the pack's own mechanism"
    for row in WA.DOMAINS:
        assert resolve(row["instruments"])["equities"] == [], f"domain {row['id']} names an equity"
        assert set(row["instruments"]) <= set(WA.EXECUTABLE_INSTRUMENTS), (
            f"domain {row['id']} names an instrument the pack never declared executable")


def test_every_transmission_seed_names_tradable_targets() -> None:
    """A seed that terminates in a symbol the box cannot quote can never compile a cell."""
    for seed in WA.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"
    for row in WA.INTERACTIONS:
        assert resolve(row["targets"])["absent"] == [], f"interaction {row['with']}: absent target"
        assert resolve(row["targets"])["equities"] == []


def test_the_two_currencies_and_the_four_minerals_are_named_absent() -> None:
    """XOF, GNF, bauxite, alumina, iron ore and cashew are not quoted here and the pack says so,
    each with the carrier its economics route into."""
    registry = universe_symbols()
    assert not {"XOF", "GNF", "EURXOF", "USDXOF", "USDGNF"} & set(registry)
    named = " ".join(str(t["name"]) for t in WA.TRANSMISSION_TARGETS)
    for token in ("XOF", "GNF", "BAUXITE", "IRON ORE", "CASHEW", "BRVM", "UMOA-Titres"):
        assert token in named, f"{token} is not named in TRANSMISSION_TARGETS"
    for row in WA.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == []
        assert row["regime"] and row["route"] and row["why"]
    # the iron-ore row must hand the price leg to the packs that own it rather than proxy it
    iron = [r for r in WA.TRANSMISSION_TARGETS if "IRON ORE" in str(r["name"])]
    assert iron and "`au`" in str(iron[0]["route"]) and "`cn`" in str(iron[0]["route"])


def test_cot_and_retail_flow_are_declared_absent_rather_than_silently_missing() -> None:
    """No COT contract and no retail margin statistic exists for either currency. An absence a
    study can trip over must be named."""
    absent = [r for r in WA.POSITIONING_SOURCES if not r["available"]]
    assert len(absent) >= 2, "the COT and retail-flow questions are not both answered"
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in absent)
    blob = " ".join(f"{r['name']} {r['why']} {r['pit_warning']}" for r in absent)
    for must in ("XOF", "GNF", "retail margin", "CREPMF"):
        assert must in blob, f"the declared absences never mention {must!r}"
    # the euro leg must NOT be offered as a substitute for XOF positioning
    assert "not a proxy" in blob.lower() or "NOT a proxy" in blob


# ------------------------------------------------------------------------------ the languages
def test_terminology_carries_french_manding_wolof_fula_and_moore() -> None:
    """Five languages, because French reads the STATE completely and the FARMGATE not at all."""
    assert len(WA.french_terms()) >= 100, f"only {len(WA.french_terms())} French terms"
    assert len(WA.manding_terms()) >= 3, "no Dioula/Bambara vocabulary at all"
    assert len(WA.wolof_terms()) >= 5, "no Wolof vocabulary at all"
    assert len(WA.fula_terms()) >= 2, "no Pular vocabulary at all"
    assert len(WA.moore_terms()) >= 2, "no Moore vocabulary at all"
    flat = {t for group in WA.TERMINOLOGY.values() for t in group}
    for must in ("prix bord champ garanti", "arrivées cumulées", "franc CFA", "655,957",
                 "Grand Magal de Touba", "code minier", "Simandou", "Sangomar"):
        assert must in flat, f"the West Africa pack does not carry {must!r}"
    for must in ("sanu", "wari", "xaalis", "njëg", "ceede", "luumo", "ligdi", "raaga"):
        assert must in flat, f"the West Africa pack does not carry {must!r}"
    assert WA.has_french("prix bord champ garanti") and not WA.has_french("National Bank")
    assert not WA.has_french("bauxite exports rise"), (
        "an English sentence must not test as French, or the language assertions measure nothing")
    assert WA.has_wolof("njëg ceeb") and not WA.has_wolof("coffee price")
    assert WA.has_manding("sanu songo Bamako") and not WA.has_manding("gold price")
    assert WA.has_fula("coggu ceede") and WA.has_moore("ligdi raaga")
    assert len(WA.TERMINOLOGY) >= 14
    assert set(WA.TERMINOLOGY) == {str(d["id"]) for d in WA.DOMAINS}


def test_every_layer_is_queried_in_french_and_the_trade_languages_reach_their_own_grounds() -> None:
    """A query in English finds an English article about the decree, not the decree. And a query
    in French finds the ministry, not the market -- which is why the retail, media and official
    layers must also carry Manding, Wolof, Pular or Moore."""
    terms = WA.layer_terms()
    assert set(terms) == set(WA.SOURCE_LAYERS)
    french = [layer for layer, qs in terms.items() if any(WA.has_french(q) for q in qs)]
    assert len(french) == 10, f"only {french} carry a French query"
    other = [layer for layer, qs in terms.items()
             if any(WA.has_native(q) and not WA.has_french(q) for q in qs)]
    assert len(other) >= 4, (
        f"only {other} carry a non-French native query; the farmgate, the corridor and the cash "
        f"market are not argued in French and a French-only crawl reads the state instead")
    for layer in ("retail_ecology", "media", "official"):
        assert layer in other, f"{layer} has no query in a trade language"
    native = sum(1 for row in WA.SOURCE_CLASSES if row["machine_use_allowed"]
                 for q in row["queries"] if WA.has_native(q))
    assert native >= 120, f"only {native} native-language queries across crawlable sources"


def test_every_source_declaring_a_native_language_actually_queries_in_it() -> None:
    """A source that lists `wo` or `bm` and queries only in French is a French source wearing a
    flag, and it is how a crawl reads the state's half of a bilingual country."""
    for row in WA.SOURCE_CLASSES:
        if set(row["languages"]) & {"fr", "wo", "bm", "dyu", "ff", "mos"}:
            assert any(WA.has_native(q) for q in row["queries"]), (
                f"{row['id']} declares {row['languages']} and every query is in English")


def test_every_source_carries_three_independent_labels_and_a_query() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in WA.SOURCE_CLASSES:
        assert row["access_label"] in WA.ACCESS_LABELS
        assert row["credibility"] in WA.CREDIBILITY_LABELS
        assert row["predictive_state"] in WA.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no query"
        assert row["roots"], f"{row['id']} has no crawlable root"
        assert row["notes"], f"{row['id']} has no note saying why it is here"


def test_all_ten_source_layers_are_populated_and_the_refusals_name_a_substitute() -> None:
    """The depth rule: ten layers, none blank. And the per-jurisdiction refusals must each name a
    LAWFUL SUBSTITUTE -- an absent ground with a named mirror is a measurable jurisdiction."""
    counts = WA.layer_counts()
    assert set(counts) == set(WA.SOURCE_LAYERS)
    blank = [layer for layer, n in counts.items() if not n]
    assert blank == [], f"blank layers: {blank}"
    coverage = WA.source_layer_coverage()
    assert coverage["n_layers_covered"] == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible for a region whose "
        "alumina and physical-cocoa differentials live behind price-reporting-agency paywalls")
    assert coverage["low_weight_kept"], "no fringe ground is kept at all, so it was dropped"
    assert counts["app_ecosystem"] >= 1
    mobile = [s for s in WA.SOURCE_CLASSES if s["layer"] == "app_ecosystem"
              and "MOBILE MONEY" in str(s["label"]).upper()]
    assert mobile, "the app layer does not name mobile money, which IS the app layer here"
    # the measured refusals are per JURISDICTION and per layer, not whole-pack
    assert WA.LAYER_ABSENCES == {}
    assert len(WA.NO_LAWFUL_GROUND) >= 6
    for row in WA.NO_LAWFUL_GROUND:
        assert row["jurisdiction"] in WA.JURISDICTIONS
        assert row["layer"] in WA.SOURCE_LAYERS
        assert len(row["reason"]) > 80, f"{row['jurisdiction']}/{row['layer']}: reason too thin"
        assert row["substitute"], (
            f"{row['jurisdiction']}/{row['layer']} declares an absence with no lawful substitute, "
            f"which is a gap rather than a measurement")
    refused = {(r["jurisdiction"], r["layer"]) for r in WA.NO_LAWFUL_GROUND}
    for must in (("ml", "academic"), ("bf", "academic"), ("gn", "institutional")):
        assert must in refused, f"{must} is the brief's own named refusal and is not declared"


def test_query_territories_give_the_deep_forest_miner_three_phrases_per_layer() -> None:
    assert set(WA.QUERY_TERRITORIES) == set(WA.SOURCE_LAYERS)
    for layer, phrases in WA.QUERY_TERRITORIES.items():
        assert len(phrases) >= 3, f"{layer}: only {len(phrases)} query territories"
        assert any(WA.has_native(p) for p in phrases), f"{layer}: no native-language phrase"


# ------------------------------------------------------------------------------ the calendars
def test_the_christian_movable_feasts_are_computed_from_the_gregorian_computus() -> None:
    """Easter is arithmetic and is COMPUTED; Ascension and Whit Monday fall out of it."""
    assert WA.western_easter(2024) == date(2024, 3, 31)
    assert WA.western_easter(2025) == date(2025, 4, 20)
    assert WA.western_easter(2026) == date(2026, 4, 5)
    assert WA.easter_monday(2024) == date(2024, 4, 1), (
        "Lundi de Paques 2024 fell on 1 April, the SAME DAY the Ivorian mid-crop campaign opens "
        "-- a collision a naive event study attributes to the farmgate decree")
    assert WA.ascension(2025) == date(2025, 5, 29)
    assert WA.whit_monday(2025) == date(2025, 6, 9)
    # the asymmetry is real: Ascension closes CI, BF and SN and not Mali or Guinea
    assert WA.ascension(2025) in WA.ivorian_holidays(2025)
    assert WA.ascension(2025) in WA.burkinabe_holidays(2025)
    assert WA.ascension(2025) not in WA.malian_holidays(2025)
    assert WA.ascension(2025) not in WA.guinean_holidays(2025)


def test_the_holiday_tables_resolve_for_three_years_and_stay_inside_them() -> None:
    for year in (2024, 2025, 2026):
        table = holiday_table(WA.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        assert f"{year}-01-01" in table, "Jour de l'An is missing"
        assert f"{year}-05-01" in table, "Fete du Travail is missing"
        assert f"{year}-12-25" in table, "Noel is missing"
        for code in WA.JURISDICTIONS:
            assert WA.JURISDICTION_HOLIDAY_FN[code](year), f"{code} has no {year} table"
    # the union rows are TAGGED, because five countries have five different national days
    table_2025 = holiday_table(WA.HOLIDAYS_RULE, 2025)
    assert "[CI]" in table_2025["2025-08-07"], "7 August closes Cote d'Ivoire alone"
    assert "[GN]" in table_2025["2025-10-02"], "2 October closes Guinea alone"
    assert "[ML]" in table_2025["2025-09-22"], "22 September closes Mali alone"
    assert "[BF]" in table_2025["2025-12-11"], "11 December closes Burkina Faso alone"
    assert "[SN]" in table_2025["2025-04-04"], "4 April closes Senegal alone"
    assert WA.closed_in("ci", date(2025, 8, 7)) and not WA.closed_in("sn", date(2025, 8, 7))
    assert not WA.is_market_holiday(date(2025, 3, 4))
    # market_holidays drops weekend closures: none of the five substitutes onto the Monday
    assert all(d.weekday() < 5 for d in WA.market_holidays(2025))


def test_the_regional_exchange_keeps_another_countrys_calendar() -> None:
    """THE CROSS-BORDER ASYMMETRY WITH NO ANALOGUE IN THE DESK'S BOOK: the BRVM sits in Abidjan
    and serves all eight UEMOA members, so an Ivorian holiday shuts the Senegalese and Malian
    investor's market and their own national days do not."""
    assert WA.brvm_closed(date(2025, 8, 7)), "the BRVM must close on the Ivorian national day"
    assert not WA.brvm_closed(date(2025, 9, 22)), (
        "Mali's national day is an ordinary session on the regional exchange")
    assert "IVORIAN CALENDAR" in WA.HOLIDAYS_RULE["market_rule"].upper()


def test_the_moon_sighted_feasts_are_declared_with_their_sighting_authorities() -> None:
    """Six announcing bodies across five countries and they need not agree. A rule would be a
    wrong rule, so each row is typed with its status and 2026 is PROJECTED throughout."""
    assert "sighting" in WA.HOLIDAYS_RULE["rule"].lower()
    assert "PROJECTED" in str(WA.HOLIDAYS_RULE["status"][2026]).upper()
    announced = WA.announced_dates(2025)
    assert date(2025, 3, 31) in announced, "Korite 2025 is 2025-03-31"
    assert all(st in ("ANNOUNCED", "PROJECTED")
               for rows in WA.LUNAR_HOLIDAYS.values() for *_, st in rows)
    assert all(st == "PROJECTED" for *_, st in WA.LUNAR_HOLIDAYS[2026]), (
        "a 2026 sighting cannot already be announced")
    # Tamkharit is a Senegalese public holiday and not an Ivorian or Burkinabe one
    assert date(2025, 7, 6) in WA.senegalese_holidays(2025)
    assert date(2025, 7, 6) not in WA.ivorian_holidays(2025)
    assert date(2025, 7, 6) not in WA.burkinabe_holidays(2025)
    # Cote d'Ivoire's Nuit du Destin is deliberately NOT typed, and the rule says why
    assert "Nuit du Destin" in str(WA.HOLIDAYS_RULE["laylat_al_qadr_note"])


def test_the_grand_magal_is_carried_and_is_unmeasured_outside_its_declared_years() -> None:
    """18 Safar shuts Senegal and slows Dakar's port clearance; it cannot be computed, so it is
    typed for the years the pack can cite and returns None for the ones it cannot."""
    assert WA.magal_de_touba(2024) == date(2024, 8, 23)
    assert WA.magal_de_touba(2025) == date(2025, 8, 13)
    assert WA.magal_de_touba(2026) == date(2026, 8, 2)
    assert WA.magal_de_touba(2030) is None, "an uncited Magal is UNMEASURED, never invented"
    assert WA.magal_de_touba(2025) in WA.senegalese_holidays(2025)
    assert WA.magal_de_touba(2025) not in WA.malian_holidays(2025)


def test_a_dated_fact_is_not_a_closed_market() -> None:
    """DECLARED_EVENTS carries the institutional milestones the domains condition on, and
    `market_holidays` keeps them out: a holiday-liquidity study that counts first oil as a closed
    session is measuring the researcher's own table."""
    assert date(2024, 6, 11) in WA.national_holidays(2024)
    assert date(2024, 6, 11) not in WA.market_holidays(2024)
    assert "NOT A CLOSURE" in WA.national_holidays(2024)[date(2024, 6, 11)]


def test_the_whole_bloc_is_on_gmt_all_year() -> None:
    """No daylight saving anywhere in the five, so every West African window is stable in UTC --
    while the London and New York legs it trades against are not, which widens the gap between
    the Abidjan close and the New York cocoa settlement by an hour every winter."""
    assert "no daylight saving" in WA.HOLIDAYS_RULE["rule"].lower()
    windows = {w["name"]: w for w in WA.SESSION_WINDOWS}
    assert windows["wa_gmt_morning"]["start_utc"] == "08:00"
    for fx in WA.FIXING_CONVENTIONS:
        local_desk = any(tok in fx["name"] for tok in ("BCEAO", "BRVM", "BCRG", "ICCO"))
        if local_desk:
            assert fx["time_utc"] == fx["time_utc_dst"], f"{fx['name']} moves with a DST rule"
    northern = [fx for fx in WA.FIXING_CONVENTIONS if fx["time_utc"] != fx["time_utc_dst"]]
    assert len(northern) >= 4, (
        "the London, New York and Frankfurt legs DO move and the pack must carry both times")


# ------------------------------------------------------------------------------ the mechanisms
def test_the_cocoa_campaign_and_the_decreed_farmgate_price() -> None:
    """The main crop opens 1 October and the mid-crop 1 April, so a January session belongs to
    the campaign that opened the PREVIOUS October -- the commonest off-by-one in cocoa work."""
    assert WA.cocoa_campaign(date(2024, 10, 3)) == (2024, "MAIN")
    assert WA.cocoa_campaign(date(2025, 1, 15)) == (2024, "MAIN")
    assert WA.cocoa_campaign(date(2025, 5, 1)) == (2024, "MID")
    assert WA.cocoa_campaign(date(2024, 4, 15)) == (2023, "MID")
    assert WA.farmgate_price_xof(date(2023, 11, 1)) == 1000
    assert WA.farmgate_price_xof(date(2024, 5, 1)) == 1500
    assert WA.farmgate_price_xof(date(2024, 11, 1)) == 1800
    assert WA.farmgate_price_xof(date(2025, 5, 1)) == 2200
    assert WA.farmgate_price_xof(date(2026, 1, 5)) is None, (
        "a campaign whose arrete this pack cannot cite is UNMEASURED; carrying the last decree "
        "forward would invent a price the Ivorian state has not announced")
    assert WA.farmgate_campaign_label(date(2024, 11, 1)) == "campagne principale 2024-2025"
    assert WA.farmgate_campaign_label(date(2026, 1, 5)) == "UNMEASURED"
    assert all(st in ("ANNOUNCED", "GAZETTED", "PRESS_REPORTED", "PROJECTED")
               for *_rest, st in WA.FARMGATE_PRICES)


def test_the_peg_is_one_rate_two_units_and_one_devaluation() -> None:
    """655.957 since 1999-01-01, which is the euro conversion of the 100-per-French-franc parity
    set at the only devaluation this currency has ever had."""
    assert pytest.approx(655.957) == WA.xof_per_eur(date(2025, 1, 1))
    assert WA.xof_per_eur(date(1995, 1, 1)) is None, (
        "the euro did not exist, which is a different answer from 'the rate was something else'")
    assert WA.cfa_regime(date(1990, 1, 1)) == "PEG_50_FRF"
    assert WA.cfa_regime(date(1994, 1, 12)) == "PEG_100_FRF"
    assert WA.cfa_regime(date(1998, 12, 31)) == "PEG_100_FRF"
    assert WA.cfa_regime(date(1999, 1, 1)) == "PEG_EUR_655_957"
    assert WA.cfa_regime(date(2026, 1, 1)) == "PEG_EUR_655_957"
    assert WA.eco_reform_phase(date(2019, 12, 20)) == "PRE_REFORM"
    assert WA.eco_reform_phase(date(2020, 6, 1)) == "REFORM_ANNOUNCED"
    assert WA.eco_reform_phase(date(2021, 1, 1)) == "REFORM_IN_FORCE"
    eras = {str(e["name"]) for e in WA.POLICY_ERAS}
    assert any("655.957" in n or "euro parity" in n for n in eras)
    assert any(str(e["start"]) == "1994-01-12" for e in WA.POLICY_ERAS)


def test_the_two_sahel_gold_regimes_are_dated_and_each_is_the_others_placebo() -> None:
    """Mali's export suspension and Burkina's state-share rewrite are the same mechanism with two
    issuers, which is what makes the pair a design rather than an anecdote."""
    assert WA.mali_gold_phase(date(2023, 1, 1)) == "PRE_CODE_2023"
    assert WA.mali_gold_phase(date(2024, 1, 1)) == "CODE_2023"
    assert WA.mali_gold_phase(date(2024, 12, 1)) == "DISPUTE_ESCALATION"
    assert WA.mali_gold_phase(date(2025, 3, 1)) == "EXPORTS_SUSPENDED"
    assert WA.mali_gold_phase(date(2025, 8, 1)) == "PROVISIONAL_ADMINISTRATION"
    assert WA.burkina_code_phase(date(2023, 1, 1)) == "PRE_SOPAMIB"
    assert WA.burkina_code_phase(date(2024, 1, 1)) == "SOPAMIB_TRANSFERS"
    assert WA.burkina_code_phase(date(2025, 1, 1)) == "CODE_2024"
    assert {j for _d, j, _w, _s in WA.SAHEL_GOLD_EVENTS} == {"ml", "bf"}
    assert all(st in ("GAZETTED", "PRESS_REPORTED", "PROJECTED")
               for *_rest, st in WA.SAHEL_GOLD_EVENTS), (
        "a gold-policy date is gazetted or PRESS_REPORTED and is never presented as a citation "
        "it is not")


def test_the_bloc_the_ramps_and_the_seasons_have_their_own_clocks() -> None:
    """They left the TRADE bloc and stayed in the CURRENCY union, which separates the two
    questions more cleanly than any deliberate experiment could."""
    assert WA.sahel_bloc_phase(date(2023, 1, 1)) == "ECOWAS_MEMBER"
    assert WA.sahel_bloc_phase(date(2023, 10, 1)) == "AES_FORMED"
    assert WA.sahel_bloc_phase(date(2024, 6, 1)) == "WITHDRAWAL_ANNOUNCED"
    assert WA.sahel_bloc_phase(date(2025, 6, 1)) == "WITHDRAWN"
    assert WA.sangomar_phase(date(2019, 1, 1)) == "PRE_FID"
    assert WA.sangomar_phase(date(2022, 1, 1)) == "DEVELOPMENT"
    assert WA.sangomar_phase(date(2024, 7, 1)) == "FIRST_OIL_YEAR"
    assert WA.sangomar_phase(date(2026, 1, 1)) == "PLATEAU"
    assert WA.gta_phase(date(2018, 1, 1)) == "PRE_FID"
    assert WA.gta_phase(date(2020, 1, 1)) == "CONSTRUCTION"
    assert WA.gta_phase(date(2025, 2, 1)) == "FIRST_GAS"
    assert WA.gta_phase(date(2025, 6, 1)) == "CARGOES"
    # the Ivorian belt's weather is a harmattan and a rainy season, not the Sahel's one season
    assert WA.ivorian_crop_season(date(2025, 1, 10)) == "HARMATTAN"
    assert WA.ivorian_crop_season(date(2025, 6, 10)) == "MAIN_RAINS"
    assert WA.ivorian_crop_season(date(2025, 10, 10)) == "LIGHT_RAINS"
    assert WA.sahel_season(date(2025, 7, 1)) == "HIVERNAGE"
    assert WA.sahel_season(date(2025, 11, 1)) == "HARVEST"
    assert WA.sahel_season(date(2025, 2, 1)) == "DRY_SEASON"
    assert WA.guinea_event_window(date(2023, 12, 20), days=10)
    assert WA.guinea_event_window(date(2019, 5, 1), days=10) == ()


def test_the_import_surge_leads_the_feast_rather_than_coinciding_with_it() -> None:
    """The methodological point of WA-P: the sugar, rice and livestock orders land six to ten
    weeks BEFORE the feast, so a study that uses the feast date as the event date is measuring
    the wrong window."""
    leads = WA.pre_feast_window(date(2025, 4, 15))
    assert any("Tabaski" in name for name in leads), (
        "15 April 2025 sits seven to eight weeks before Tabaski 2025 and must lead it")
    assert WA.pre_feast_window(date(2025, 6, 7)) == () or all(
        "Tabaski" not in n for n in WA.pre_feast_window(date(2025, 6, 7))), (
        "the feast day itself is not inside its own lead window")
    magal_lead = WA.pre_feast_window(date(2025, 6, 20))
    assert any("Magal" in name for name in magal_lead)


# ------------------------------------------------------------------------------ the cells
def test_the_pack_mints_cells_inside_its_domains_and_not_as_a_cartesian_blow_up() -> None:
    """A cell is only worth a trial if this pack's own data plane can evaluate its CONDITION on
    that SYMBOL, so the cross product is taken INSIDE each domain."""
    rows = WA.cells()
    assert 120 <= len(rows) <= 220, f"{len(rows)} cells is outside the honest range"
    assert len(rows) == len(WA.CELLS)
    assert len({r["cell_id"] for r in rows}) == len(rows), "duplicate cell_id"
    domain_ids = {str(d["id"]) for d in WA.DOMAINS}
    for row in rows:
        for field in ("cell_id", "domain", "symbol", "condition", "mechanism_family",
                      "horizon", "control", "why"):
            assert row[field], f"{row['cell_id']}: {field} is empty"
        assert row["domain"] in domain_ids
        assert row["symbol"] in WA.EXECUTABLE_INSTRUMENTS
        assert set(row["jurisdictions"]) <= set(WA.JURISDICTIONS)
    assert resolve(sorted({r["symbol"] for r in rows}))["equities"] == []
    # every domain mints at least one cell, so no domain is decorative
    assert {r["domain"] for r in rows} == domain_ids
    # and every jurisdiction owns cells of its own
    for code in WA.JURISDICTIONS:
        mine_rows = [r for r in rows if code in r["jurisdictions"]]
        assert len(mine_rows) >= 10, f"{code}: only {len(mine_rows)} cells"


def test_every_dataset_carries_all_twelve_fields_and_a_fetchable_route() -> None:
    from countries import DATASET_FIELDS
    for ds in WA.DATASETS:
        for field in DATASET_FIELDS:
            if field in ("pit_feasible", "publication_lag_days"):
                continue
            assert ds[field], f"dataset {ds.get('name')!r}: {field} is empty"
        assert float(ds["publication_lag_days"]) >= 0.0
        assert len(str(ds["how_to_fetch"])) > 40, (
            f"dataset {ds['name']!r}: how_to_fetch is not concrete enough for a collector")
        assert resolve(ds["assets"])["equities"] == []
    # the overwriting pages must be honest about their point-in-time feasibility
    not_pit = {str(d["name"]) for d in WA.DATASETS if not d["pit_feasible"]}
    assert any("arrivals" in n for n in not_pit), (
        "the CCC arrivals page overwrites in place and cannot be pit_feasible")
    # the Chinese mirror is the substitute for the thin Guinean print and must be carried
    names = {str(d["name"]) for d in WA.DATASETS}
    assert any("Chinese customs bauxite" in n for n in names)


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {f"custom:{name}" for name in WA.MINERS}
    assert all(callable(fn) for fn in got.values())
    ids = {str(d["id"]) for d in WA.DOMAINS}
    entries = set()
    for row in WA.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.west_africa.pack", row["entry"]
        assert callable(getattr(WA, func)), f"{row['entry']} does not resolve"
        entries.add(func)
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    assert entries == set(WA.MINERS)
    for did in WA.MINER_DOMAINS.values():
        assert set(did) <= ids


def test_mine_returns_a_report_and_emits_nothing_without_a_context() -> None:
    """`mine(None)` is how a test and a fresh session check the pack with nothing wired: it must
    return a report and must not try to record anywhere."""
    report = WA.mine(None)
    assert report["code"] == CODE
    assert tuple(report["jurisdictions"]) == WA.JURISDICTIONS
    assert report["emitted"] == 0, "mine(None) emitted to a registry that does not exist"
    assert report["rows"], "mine(None) produced no rows at all"
    assert report["cells_emitted"] == len(WA.cells())
    assert report["at"].endswith("+00:00"), "the stamp must be timezone-aware UTC"
    assert set(report["miners"]) == set(WA.MINERS)
    assert report["layers_covered"] == 10
    assert report["datasets"] == len(WA.DATASETS)
    assert "gh" in report["interactions"], (
        "Ghana and Cote d'Ivoire jointly set the Living Income Differential and are one pricing "
        "system; `gh` must be named as an interaction")
    assert report["unmeasured"], "no miner declared anything UNMEASURED, which is implausible"
    for row in report["rows"]:
        assert row["kind"] == "hypothesis"
        assert row["symbols"], "a donated row with no instrument compiles to nothing"
        assert resolve(row["symbols"])["absent"] == []


def test_mine_emits_through_a_context_when_one_is_given() -> None:
    """The same call with a Ctx must hand every row over and count what was taken."""
    class _Ctx:
        def __init__(self) -> None:
            self.rows: list[dict[str, Any]] = []

        def record(self, row: dict[str, Any]) -> None:
            self.rows.append(row)

    ctx = _Ctx()
    report = WA.mine(ctx)
    assert report["emitted"] == len(ctx.rows) == len(report["rows"])
    assert report["emitted"] > 0


def test_the_interactions_name_real_sibling_packs_with_a_control(built: Any) -> None:
    """An edge whose control lives in a pack nobody runs is an edge nobody can falsify."""
    from countries import codes
    present = set(codes())
    for row in WA.INTERACTIONS:
        assert row["with"] in present, f"interaction names {row['with']!r}, which is not a pack"
        assert row["mechanism"] and row["observable"] and row["control"]
        assert row["targets"]
    assert WA.INTERACTIONS[0]["with"] == "gh", (
        "Ghana and Cote d'Ivoire are together about 60% of world cocoa and set the Living Income "
        "Differential JOINTLY, so the two packs are one pricing system and `gh` belongs first")
    named = {r["with"] for r in WA.INTERACTIONS}
    for must in ("gh", "cn", "au"):
        assert must in named, (
            f"{must} owns a series this pack's own controls depend on and is not named")
    assert "repeat" in str(WA.INTERACTIONS[0]["mechanism"]).lower(), (
        "the Ghana row must say on its face that this pack COMPLEMENTS `gh` rather than "
        "duplicating it")
