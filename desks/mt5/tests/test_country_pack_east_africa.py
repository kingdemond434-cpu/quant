"""THE EAST AFRICA PACK, VALIDATED -- three jurisdictions, three calendars, one physical system.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A MULTI-JURISDICTION PACK THAT ANSWERS FOR ONE COUNTRY AND CLAIMS THREE. `JURISDICTIONS` is
    what the parity fence counts, so the tests check that each of `et`, `tz` and `ug` owes at
    least five actors and three domains OF ITS OWN -- not three countries' worth of one
    country's mechanisms with two flags stapled on.
  * AN ENGLISH GLOSSARY OF THREE NON-ENGLISH GROUNDS. English is co-official in all three, which
    is exactly the trap: an English crawl returns something for every query and reads complete.
    The assertions below require Ge'ez script for Ethiopia and Swahili words for Tanzania in
    every layer, and they check Luganda and Oromo too.
  * A TYPED ETHIOPIAN CALENDAR. Enkutatash alternates between 11 and 12 September on the Ge'ez
    leap rule, Genna and Timkat are Julian feasts, and Fasika is the Julian computus -- all four
    are COMPUTED here and the tests check them on dates a human can verify.
  * A SYMBOL THE BOX CANNOT TRADE. Every executable instrument and every edge target is checked
    against the broker's OWN registry. ETB, TZS and UGX are absent and must stay transmission
    targets.
  * A SINGLE-NAME EQUITY ON A DOCKET. This region is full of tempting national champions -- the
    gold miners' operating companies, the mobile-money operators, the airline -- and every one
    of them appears as an ACTOR only (two-lane order, 2026-09-06).
  * A PACK THAT REACHES THE FRAMEWORK BENT. `CountryPack` coerces every row; a coercion note is
    a field the framework could not read, and this pack must produce none.
  * A LAYER NOBODY LOOKED AT, and its opposite -- a layer declared absent that is not. The
    app-ecosystem layer here is MOBILE MONEY and its statistics are published monthly by two
    central banks, so the tests require it sourced and require the per-jurisdiction refusals to
    be named in `NO_LAWFUL_GROUND` instead.
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
from countries.east_africa import pack as EA  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as F  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")
CODE = "east_africa"


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it, resolved through `resolve_pack` so the test measures
    the same object the country lab runs and not a private construction."""
    got = CL.resolve_pack(CODE)
    assert got is not None, "no East Africa pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(EA.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == CODE
    assert str(get(built, "region_command")) == "africa"
    assert str(get(built, "currency")) == "ETB"


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


def test_depth_counts_sit_above_a_three_country_floor() -> None:
    """Twelve actors is the floor for ONE country. A pack answering for three owes more, and the
    brief's own floor for this one is 18 actors, 13 domains, 11 edges and 17 datasets."""
    assert len(EA.ACTORS) >= 18
    assert len(EA.DOMAINS) >= 13
    assert len(EA.TRANSMISSION_EDGES_SEED) >= 11
    assert len(EA.DATASETS) >= 17
    assert len(EA.SOURCE_CLASSES) >= 24
    assert len(EA.POLICY_ERAS) >= 8
    assert len(EA.INTERACTIONS) >= 4
    assert EA.term_count() >= 150


# ------------------------------------------------------------------------ the three jurisdictions
def test_jurisdictions_are_exactly_the_three_claimed_and_all_are_on_the_roster() -> None:
    """`JURISDICTIONS` is what `check_regional_parity.jurisdictions_of` counts. A pack that
    answers for three countries and declares one is credited with one."""
    assert EA.JURISDICTIONS == ("et", "tz", "ug")
    assert set(EA.JURISDICTIONS) == {"et", "tz", "ug"}
    for code in EA.JURISDICTIONS:
        assert code == code.lower() and len(code) == 2, f"{code!r} is not a lowercase ISO-2 code"
    roster = {c.lower() for f in F.FORESTS.values() for c in f.countries}
    missing = sorted(set(EA.JURISDICTIONS) - roster)
    assert missing == [], f"{missing} are not on any forest's roster in libs/research/forests.py"
    assert CODE in F.forest("africa").packs, "the africa forest does not draw on this pack"
    for code in EA.JURISDICTIONS:
        assert F.forest_of_country(code) == "africa"


def test_each_jurisdiction_owes_its_own_actors_and_domains() -> None:
    """Five actors and three domains EACH, so the pack cannot be one country wearing three hats."""
    assert len(EA.ACTOR_JURISDICTION) == len(EA.ACTORS)
    for code in EA.JURISDICTIONS:
        actors = [a for a, j in zip(EA.ACTORS, EA.ACTOR_JURISDICTION, strict=True) if j == code]
        assert len(actors) >= 5, f"{code}: only {len(actors)} actors of its own"
        domains = [d for d in EA.DOMAINS
                   if code in EA.DOMAIN_JURISDICTION.get(str(d["id"]), ())]
        assert len(domains) >= 3, f"{code}: only {len(domains)} domains of its own"
    assert set(EA.DOMAIN_JURISDICTION) == {str(d["id"]) for d in EA.DOMAINS}
    assert set(EA.CURRENCIES) == set(EA.JURISDICTIONS)
    assert set(EA.CENTRAL_BANKS) == set(EA.JURISDICTIONS)
    assert set(EA.JURISDICTION_HOLIDAY_FN) == set(EA.JURISDICTIONS)


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    for row in EA.ACTORS:
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
    for row in EA.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert row["conditions"], f"domain {row['id']} names no conditioning state"
        assert row["instruments"], f"domain {row['id']} names no instrument"


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(EA.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert set(EA.EXECUTABLE_INSTRUMENTS) <= set(registry)
    for row in EA.DOMAINS:
        assert resolve(row["instruments"])["equities"] == [], f"domain {row['id']} names an equity"
        assert set(row["instruments"]) <= set(EA.EXECUTABLE_INSTRUMENTS), (
            f"domain {row['id']} names an instrument the pack never declared executable")


def test_every_transmission_seed_names_tradable_targets() -> None:
    """A seed that terminates in a symbol the box cannot quote can never compile a cell."""
    for seed in EA.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"
    for row in EA.INTERACTIONS:
        assert resolve(row["targets"])["absent"] == [], f"interaction {row['with']}: absent target"
        assert resolve(row["targets"])["equities"] == []


def test_the_three_shillings_are_named_absent_rather_than_quietly_dropped() -> None:
    """ETB, TZS and UGX are not quoted here and the pack says so three times, with carriers."""
    registry = universe_symbols()
    assert not {"ETB", "TZS", "UGX", "USDETB", "USDTZS", "USDUGX"} & set(registry)
    named = " ".join(str(t["name"]) for t in EA.TRANSMISSION_TARGETS)
    for code in ("ETB", "TZS", "UGX"):
        assert code in named, f"{code} is not named in TRANSMISSION_TARGETS"
    assert "ECX" in named and "TEA" in named
    for row in EA.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == []
        assert row["regime"] and row["route"] and row["why"]


def test_cot_and_retail_flow_are_declared_absent_rather_than_silently_missing() -> None:
    """No COT contract and no retail margin statistic exists for any of the three. An absence a
    study can trip over must be named."""
    absent = [r for r in EA.POSITIONING_SOURCES if not r["available"]]
    assert len(absent) >= 2, "the COT and retail-flow questions are not both answered"
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in absent)
    blob = " ".join(f"{r['name']} {r['why']} {r['pit_warning']}" for r in absent)
    for must in ("ETB", "TZS", "UGX", "retail margin", "CMSA"):
        assert must in blob, f"the declared absences never mention {must!r}"


# ------------------------------------------------------------------------------ the languages
def test_terminology_carries_geez_swahili_luganda_and_oromo() -> None:
    """Four native grounds, because English is co-official in all three and an English-only
    crawl reads the English corner of each and reports the corner as the ground."""
    assert len(EA.ethiopic_terms()) >= 40, f"only {len(EA.ethiopic_terms())} Ge'ez terms"
    assert len(EA.swahili_terms()) == len(EA.SWAHILI_MARKERS), (
        f"missing Swahili vocabulary: "
        f"{sorted(set(EA.SWAHILI_MARKERS) - set(EA.swahili_terms()))}")
    assert len(EA.oromo_terms()) == len(EA.OROMO_MARKERS)
    flat = {t for group in EA.TERMINOLOGY.values() for t in group}
    for must in ("ብሔራዊ ባንክ", "የውጭ ምንዛሪ", "ቡና", "ወርቅ", "ታላቁ የሕዳሴ ግድብ", "እንቁጣጣሽ", "ጳጉሜ"):
        assert must in flat, f"the East Africa pack does not carry {must!r}"
    for must in ("dhahabu", "kahawa", "bandari", "korosho", "Tume ya Madini", "pesa za simu"):
        assert must in flat, f"the East Africa pack does not carry {must!r}"
    assert any(EA.has_luganda(t) for t in flat), "no Luganda vocabulary at all"
    assert EA.has_ethiopic("ብሔራዊ ባንክ") and not EA.has_ethiopic("National Bank")
    assert EA.has_swahili("bei ya dhahabu leo") and not EA.has_swahili("Kenya Airways")
    assert EA.has_luganda("emmwanyi bbeeyi") and not EA.has_luganda("coffee price")
    assert len(EA.TERMINOLOGY) >= 15
    assert set(EA.TERMINOLOGY) == {str(d["id"]) for d in EA.DOMAINS}


def test_every_layer_is_queried_in_geez_and_in_swahili() -> None:
    """A query in English finds an English article about the release, not the release."""
    terms = EA.layer_terms()
    assert set(terms) == set(EA.SOURCE_LAYERS)
    geez = [layer for layer, qs in terms.items() if any(EA.has_ethiopic(q) for q in qs)]
    swahili = [layer for layer, qs in terms.items() if any(EA.has_swahili(q) for q in qs)]
    assert len(geez) == 10, f"only {geez} carry a Ge'ez query"
    assert len(swahili) == 10, f"only {swahili} carry a Swahili query"
    native = sum(1 for row in EA.SOURCE_CLASSES if row["machine_use_allowed"]
                 for q in row["queries"] if EA.has_native(q))
    assert native >= 80, f"only {native} native-language queries across crawlable sources"


def test_every_source_declaring_a_native_language_actually_queries_in_it() -> None:
    """A source that lists `am` or `sw` and queries only in English is an English source wearing
    a flag, and it is how a crawl reads the wrong half of a bilingual country."""
    for row in EA.SOURCE_CLASSES:
        if set(row["languages"]) & {"am", "sw", "lg", "om", "ti"}:
            assert any(EA.has_native(q) for q in row["queries"]), (
                f"{row['id']} declares {row['languages']} and every query is in English")


def test_every_source_carries_three_independent_labels_and_a_query() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in EA.SOURCE_CLASSES:
        assert row["access_label"] in EA.ACCESS_LABELS
        assert row["credibility"] in EA.CREDIBILITY_LABELS
        assert row["predictive_state"] in EA.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no query"
        assert row["roots"], f"{row['id']} has no crawlable root"
        assert row["notes"], f"{row['id']} has no note saying why it is here"


def test_all_ten_source_layers_are_populated_and_the_refusals_are_named() -> None:
    """The depth rule: ten layers, none blank. The app layer here is MOBILE MONEY and declaring
    it absent because there is no trading-app ecology would be reading the wrong country."""
    counts = EA.layer_counts()
    assert set(counts) == set(EA.SOURCE_LAYERS)
    blank = [layer for layer, n in counts.items() if not n]
    assert blank == [], f"blank layers: {blank}"
    coverage = EA.source_layer_coverage()
    assert coverage["n_layers_covered"] == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible for a region "
        "whose cashew, sesame and cobalt prices live behind price-reporting-agency paywalls")
    assert coverage["low_weight_kept"], "no fringe ground is kept at all, so it was dropped"
    assert counts["app_ecosystem"] >= 1
    mobile = [s for s in EA.SOURCE_CLASSES if s["layer"] == "app_ecosystem"
              and "MOBILE MONEY" in str(s["label"]).upper()]
    assert mobile, "the app layer does not name mobile money, which IS the app layer here"
    # the measured refusals are per JURISDICTION and per layer, not whole-pack
    assert EA.LAYER_ABSENCES == {}
    assert len(EA.NO_LAWFUL_GROUND) >= 5
    for row in EA.NO_LAWFUL_GROUND:
        assert row["jurisdiction"] in EA.JURISDICTIONS
        assert row["layer"] in EA.SOURCE_LAYERS
        assert len(row["reason"]) > 60, f"{row['jurisdiction']}/{row['layer']}: reason too thin"


def test_query_territories_give_the_deep_forest_miner_three_phrases_per_layer() -> None:
    assert set(EA.QUERY_TERRITORIES) == set(EA.SOURCE_LAYERS)
    for layer, phrases in EA.QUERY_TERRITORIES.items():
        assert len(phrases) >= 3, f"{layer}: only {len(phrases)} query territories"
        assert any(EA.has_native(p) for p in phrases), f"{layer}: no native-language phrase"


# ------------------------------------------------------------------------------ the calendars
def test_the_geez_new_year_alternates_by_the_ethiopian_leap_rule() -> None:
    """ENKUTATASH is 11 September, or 12 September in the year following an Ethiopian leap year
    (Ethiopian year N is leap when N mod 4 == 3). Computed, never typed -- the alternation is
    exactly what a typed table gets wrong."""
    assert EA.enkutatash(2022) == date(2022, 9, 11)
    assert EA.enkutatash(2023) == date(2023, 9, 12), "2015 EC was a leap year; Pagume had 6 days"
    assert EA.enkutatash(2024) == date(2024, 9, 11)
    assert EA.enkutatash(2025) == date(2025, 9, 11)
    assert EA.enkutatash(2026) == date(2026, 9, 11)
    assert EA.enkutatash(2027) == date(2027, 9, 12)
    assert EA.is_ethiopian_leap(2015) and not EA.is_ethiopian_leap(2016)
    # Meskerem 1 of Ethiopian 2017 is 11 September 2024, the anchor the whole converter rests on
    assert EA.ethiopic_to_gregorian(2017, 1, 1) == date(2024, 9, 11)
    assert EA.ethiopian_year_starting_in(2024) == 2017
    # Meskel is Meskerem 17, sixteen days after the new year, so it alternates too
    assert EA.meskel(2023) == date(2023, 9, 28)
    assert EA.meskel(2024) == date(2024, 9, 27)
    assert EA.meskel(2026) == date(2026, 9, 27)
    assert len(EA.ETHIOPIC_MONTHS) == 13
    assert all(EA.has_ethiopic(geez) for _name, geez in EA.ETHIOPIC_MONTHS)


def test_genna_timkat_and_fasika_come_from_the_julian_calendar() -> None:
    """Genna is 25 December JULIAN and Timkat is 6 January Julian, so both are fixed in the
    Gregorian this century; Fasika is Orthodox Easter by MEEUS' JULIAN algorithm."""
    for year in (2024, 2025, 2026):
        assert EA.genna(year) == date(year, 1, 7)
        assert EA.timkat(year) == date(year, 1, 19)
    assert EA.julian_to_gregorian(2024, 12, 25) == date(2025, 1, 7)
    assert EA.orthodox_easter(2024) == date(2024, 5, 5)
    assert EA.orthodox_easter(2025) == date(2025, 4, 20)
    assert EA.orthodox_easter(2026) == date(2026, 4, 12)
    # Tanzania and Uganda close for the WESTERN Easter, which is usually weeks away from Fasika
    assert EA.western_easter(2024) == date(2024, 3, 31)
    assert EA.western_easter(2025) == date(2025, 4, 20)
    assert EA.western_easter(2026) == date(2026, 4, 5)
    assert EA.orthodox_easter(2024) != EA.western_easter(2024), (
        "in 2024 the two Easters were five weeks apart and a pooled regional holiday study "
        "mislabels two countries")
    assert EA.orthodox_easter(2025) == EA.western_easter(2025), (
        "in 2025 the two computus rules happened to agree, which is the case that makes a "
        "naive 'they are always different' rule wrong too")


def test_the_holiday_tables_resolve_for_three_years_and_stay_inside_them() -> None:
    for year in (2024, 2025, 2026):
        table = holiday_table(EA.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        assert f"{year}-01-07" in table, "Genna is missing"
        assert f"{year}-05-01" in table, "Labour/Workers' Day is missing"
        for code in EA.JURISDICTIONS:
            assert EA.JURISDICTION_HOLIDAY_FN[code](year), f"{code} has no {year} table"
    # the union rows are TAGGED, because a day that closes Addis is a session in Kampala
    table_2025 = holiday_table(EA.HOLIDAYS_RULE, 2025)
    assert "[ET]" in table_2025["2025-03-02"], "Adwa Victory Day closes Ethiopia alone"
    assert "[TZ]" in table_2025["2025-01-12"], "Zanzibar Revolution Day closes Tanzania alone"
    assert "[UG]" in table_2025["2025-01-26"], "NRM Liberation Day closes Uganda alone"
    assert EA.closed_in("et", date(2025, 3, 2))
    assert not EA.closed_in("ug", date(2025, 3, 2))
    assert not EA.is_market_holiday(date(2025, 3, 4))
    # market_holidays drops weekend closures: none of the three substitutes onto the Monday
    assert all(d.weekday() < 5 for d in EA.market_holidays(2025))


def test_the_moon_sighted_feasts_are_declared_with_their_sighting_authority() -> None:
    """Three authorities announce independently and need not agree. A rule would be a wrong
    rule, so each row is typed with its status and 2026 is PROJECTED throughout."""
    assert "sighting" in EA.HOLIDAYS_RULE["rule"].lower()
    assert "PROJECTED" in str(EA.HOLIDAYS_RULE["status"][2026]).upper()
    announced = EA.announced_dates(2025)
    assert date(2025, 3, 31) in announced, "Eid al-Fitr 2025 is 2025-03-31"
    assert all(st in ("ANNOUNCED", "PROJECTED")
               for rows in EA.LUNAR_HOLIDAYS.values() for *_, st in rows)
    assert all(st == "PROJECTED" for *_, st in EA.LUNAR_HOLIDAYS[2026]), (
        "a 2026 sighting cannot already be announced")
    # Uganda does not close for Mawlid and the other two do -- a real per-country asymmetry
    assert date(2025, 9, 5) in EA.ethiopian_holidays(2025)
    assert date(2025, 9, 5) in EA.tanzanian_holidays(2025)
    assert date(2025, 9, 5) not in EA.ugandan_holidays(2025)


def test_east_africa_time_never_moves() -> None:
    """No daylight saving anywhere in the three, so every session window is stable in UTC all
    year -- unlike Morocco's, which moves an hour for Ramadan."""
    assert "no daylight saving" in EA.HOLIDAYS_RULE["rule"].lower()
    windows = {w["name"]: w for w in EA.SESSION_WINDOWS}
    assert windows["ea_ecx_session"]["end_utc"] == "10:00", (
        "the ECX floor must close before the New York coffee session opens, which is the whole "
        "reason its daily print is a candidate lead")
    for fx in EA.FIXING_CONVENTIONS:
        if "LBMA" not in fx["name"]:
            assert fx["time_utc"] == fx["time_utc_dst"], f"{fx['name']} moves with a DST rule"


# ------------------------------------------------------------------------------ the mechanisms
def test_the_birr_float_is_one_boundary_and_the_pack_knows_which_side_it_is_on() -> None:
    """2024-07-29 partitions every Ethiopian series in this pack."""
    assert EA.BIRR_FLOAT_DATE.isoformat() == "2024-07-29"
    assert EA.birr_regime(date(2024, 7, 28)) == "CRAWLING_PEG_RATIONED"
    assert EA.birr_regime(date(2024, 7, 29)) == "MARKET_DETERMINED"
    assert EA.birr_regime(date(2019, 1, 1)) == "CRAWLING_PEG_RATIONED"
    assert EA.birr_regime(date(2026, 1, 1)) == "MARKET_DETERMINED"
    eras = {str(e["name"]) for e in EA.POLICY_ERAS}
    assert any("float" in n.lower() for n in eras)
    assert any(str(e["start"]) == "2024-07-29" for e in EA.POLICY_ERAS)


def test_the_two_gold_regimes_are_dated_and_pointed_in_opposite_directions() -> None:
    """Tanzania's mandated domestic OFFER and Uganda's export LEVY are the same mechanism --
    an administered change in where physical gold may lawfully go -- and each is the other's
    natural placebo."""
    assert EA.gold_offer_share(date(2023, 1, 1)) == 0.0
    assert EA.gold_offer_share(date(2024, 1, 1)) == 0.0
    assert EA.gold_offer_share(date(2025, 7, 1)) == pytest.approx(0.20)
    assert EA.gold_offer_share(date(2026, 1, 1)) == pytest.approx(0.20)
    assert EA.uganda_gold_levy(date(2021, 6, 30)) == "NONE"
    assert EA.uganda_gold_levy(date(2021, 7, 1)) == "IN_FORCE"
    assert EA.uganda_gold_levy(date(2022, 7, 1)) == "AMENDED"
    assert EA.GOLD_POLICY_EVENTS
    assert all(st in ("GAZETTED", "PRESS_REPORTED")
               for *_rest, st in EA.GOLD_POLICY_EVENTS), (
        "a gold-policy date is either gazetted or PRESS_REPORTED and never presented as a "
        "citation it is not")
    assert {j for _d, j, _w, _s in EA.GOLD_POLICY_EVENTS} == {"tz", "ug"}


def test_the_oil_ramp_and_the_crop_year_have_their_own_clocks() -> None:
    assert EA.oil_ramp_phase(date(2021, 1, 1)) == "PRE_FID"
    assert EA.oil_ramp_phase(date(2022, 2, 1)) == "CONSTRUCTION"
    assert EA.oil_ramp_phase(date(2024, 6, 1)) == "CONSTRUCTION"
    assert EA.oil_ramp_phase(date(2025, 6, 1)) == "FIRST_OIL_WINDOW"
    assert EA.oil_ramp_phase(date(2026, 6, 1)) == "RAMP"
    # a January session belongs to the crop year that opened the PREVIOUS October
    assert EA.coffee_crop_year(date(2025, 1, 15)) == (2024, "PEAK")
    assert EA.coffee_crop_year(date(2024, 10, 3)) == (2024, "OPENING")
    assert EA.coffee_crop_year(date(2025, 8, 1)) == (2024, "TAIL")
    # Ethiopia's seasons are BELG and KIREMT and they are NOT Kenya's long and short rains
    assert EA.rain_season(date(2025, 3, 15), "et") == "BELG"
    assert EA.rain_season(date(2025, 7, 15), "et") == "KIREMT"
    assert EA.rain_season(date(2025, 11, 15), "et") == "MEHER_HARVEST"
    assert EA.rain_season(date(2025, 1, 15), "tz") == "MSIMU"
    assert EA.gerd_filling_window(2025) == (date(2025, 7, 1), date(2025, 9, 30))


# ------------------------------------------------------------------------------ the cells
def test_the_pack_mints_cells_inside_its_domains_and_not_as_a_cartesian_blow_up() -> None:
    """A cell is only worth a trial if this pack's own data plane can evaluate its CONDITION on
    that SYMBOL, so the cross product is taken INSIDE each domain."""
    rows = EA.cells()
    assert 60 <= len(rows) <= 200, f"{len(rows)} cells is outside the honest range"
    assert len(rows) == len(EA.CELLS)
    assert len({r["cell_id"] for r in rows}) == len(rows), "duplicate cell_id"
    domain_ids = {str(d["id"]) for d in EA.DOMAINS}
    for row in rows:
        for field in ("cell_id", "domain", "symbol", "condition", "mechanism_family",
                      "horizon", "control", "why"):
            assert row[field], f"{row['cell_id']}: {field} is empty"
        assert row["domain"] in domain_ids
        assert row["symbol"] in EA.EXECUTABLE_INSTRUMENTS
        assert set(row["jurisdictions"]) <= set(EA.JURISDICTIONS)
    assert resolve(sorted({r["symbol"] for r in rows}))["equities"] == []
    # every domain mints at least one cell, so no domain is decorative
    assert {r["domain"] for r in rows} == domain_ids


def test_every_dataset_carries_all_twelve_fields_and_a_fetchable_route() -> None:
    from countries import DATASET_FIELDS
    for ds in EA.DATASETS:
        for field in DATASET_FIELDS:
            if field in ("pit_feasible", "publication_lag_days"):
                continue
            assert ds[field], f"dataset {ds.get('name')!r}: {field} is empty"
        assert float(ds["publication_lag_days"]) >= 0.0
        assert len(str(ds["how_to_fetch"])) > 40, (
            f"dataset {ds['name']!r}: how_to_fetch is not concrete enough for a collector")
        assert resolve(ds["assets"])["equities"] == []
    # the three overwriting pages must be honest about their point-in-time feasibility
    not_pit = {str(d["name"]) for d in EA.DATASETS if not d["pit_feasible"]}
    assert any("ECX" in n for n in not_pit), (
        "the ECX daily table overwrites in place and cannot be pit_feasible")


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {f"custom:{name}" for name in EA.MINERS}
    assert all(callable(fn) for fn in got.values())
    ids = {str(d["id"]) for d in EA.DOMAINS}
    entries = set()
    for row in EA.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.east_africa.pack", row["entry"]
        assert callable(getattr(EA, func)), f"{row['entry']} does not resolve"
        entries.add(func)
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    assert entries == set(EA.MINERS)
    for did in EA.MINER_DOMAINS.values():
        assert set(did) <= ids


def test_mine_returns_a_report_and_emits_nothing_without_a_context() -> None:
    """`mine(None)` is how a test and a fresh session check the pack with nothing wired: it must
    return a report and must not try to record anywhere."""
    report = EA.mine(None)
    assert report["code"] == CODE
    assert tuple(report["jurisdictions"]) == EA.JURISDICTIONS
    assert report["emitted"] == 0, "mine(None) emitted to a registry that does not exist"
    assert report["rows"], "mine(None) produced no rows at all"
    assert report["cells_emitted"] == len(EA.cells())
    assert report["at"].endswith("+00:00"), "the stamp must be timezone-aware UTC"
    assert set(report["miners"]) == set(EA.MINERS)
    assert report["layers_covered"] == 10
    assert report["datasets"] == len(EA.DATASETS)
    assert "ke" in report["interactions"], (
        "Kenya is the regional hub of all three and must be named as an interaction")
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
    report = EA.mine(ctx)
    assert report["emitted"] == len(ctx.rows) == len(report["rows"])
    assert report["emitted"] > 0


def test_the_interactions_name_real_sibling_packs_with_a_control(built: Any) -> None:
    """An edge whose control lives in a pack nobody runs is an edge nobody can falsify."""
    from countries import codes
    present = set(codes())
    for row in EA.INTERACTIONS:
        assert row["with"] in present, f"interaction names {row['with']!r}, which is not a pack"
        assert row["mechanism"] and row["observable"] and row["control"]
        assert row["targets"]
    assert EA.INTERACTIONS[0]["with"] == "ke", (
        "Kenya is the regional financial and logistics hub of all three and is the strongest "
        "interaction this pack has -- it belongs first")
