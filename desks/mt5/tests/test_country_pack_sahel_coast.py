"""THE SAHEL COAST PACK, VALIDATED -- eight jurisdictions, eight calendars, three FX regimes.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A MULTI-JURISDICTION PACK THAT ANSWERS FOR TWO COUNTRIES AND CLAIMS EIGHT. `JURISDICTIONS` is
    what the parity fence counts, so the tests check that each of the eight owes at least two
    actors and one domain OF ITS OWN, and that NE, LR, TG, BJ and SL -- the five that carry the
    pack's real mechanisms -- owe three or more.
  * A FRENCH-AND-ENGLISH CRAWL WEARING EIGHT FLAGS. Guinea-Bissau and Cabo Verde live in
    PORTUGUESE and the Nigerien interior trades in HAUSA; a crawl that reads neither returns
    something for every query and looks complete. The assertions below require French AND
    Portuguese AND Hausa in every source layer.
  * A TYPED EASTER, AND A TYPED LIBERIAN CALENDAR. Easter is the anonymous Gregorian algorithm
    and Liberia carries THREE weekday-rule holidays that a typed table gets wrong.
  * A SYMBOL THE BOX CANNOT TRADE. Every executable instrument and every edge target is checked
    against the broker's OWN registry. XOF, SLE, LRD, GMD and CVE are absent and stay
    transmission targets; uranium, rutile, cashew, iron ore, rubber and registry tonnage are not
    instruments at all and each is routed explicitly.
  * A SINGLE-NAME EQUITY ON A DOCKET. This region is full of tempting names -- the uranium
    operator, the registry administrator, the iron-ore concessionaire, the rutile miner -- and
    every one appears as an ACTOR only (two-lane order, 2026-09-06).
  * A LAYER NOBODY LOOKED AT, and its opposite. Eight jurisdictions of very different
    statistical capacity share ten layers, so the refusals are PER JURISDICTION and every one
    must name a LAWFUL SUBSTITUTE.
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
from countries.sahel_coast import pack as SC  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as F  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")
CODE = "sahel_coast"
EIGHT = {"ne", "tg", "bj", "sl", "lr", "gm", "gw", "cv"}


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it, resolved through `resolve_pack` so the test measures
    the same object the country lab runs and not a private construction."""
    got = CL.resolve_pack(CODE)
    assert got is not None, "no Sahel Coast pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(SC.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == CODE
    assert str(get(built, "region_command")) == "africa"
    assert str(get(built, "currency")) == "XOF"
    assert SC.FOREST == "africa"


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


def test_depth_counts_sit_above_an_eight_country_floor() -> None:
    """Twelve actors is the floor for ONE country. The brief's floor for this one is 22 actors,
    15 domains, 13 edges and 19 datasets."""
    assert len(SC.ACTORS) >= 22
    assert len(SC.DOMAINS) >= 15
    assert len(SC.TRANSMISSION_EDGES_SEED) >= 13
    assert len(SC.DATASETS) >= 19
    assert len(SC.SOURCE_CLASSES) >= 28
    assert len(SC.POLICY_ERAS) >= 8
    assert len(SC.INTERACTIONS) >= 4
    assert SC.term_count() >= 150


# ------------------------------------------------------------------------ the eight jurisdictions
def test_jurisdictions_are_exactly_the_eight_claimed() -> None:
    """`JURISDICTIONS` is what `check_regional_parity.jurisdictions_of` counts. A pack that
    answers for eight countries and declares one is credited with one."""
    assert SC.JURISDICTIONS == ("ne", "tg", "bj", "sl", "lr", "gm", "gw", "cv")
    assert set(SC.JURISDICTIONS) == EIGHT
    for code in SC.JURISDICTIONS:
        assert code == code.lower() and len(code) == 2, f"{code!r} is not a lowercase ISO-2 code"
    assert set(SC.CURRENCIES) == EIGHT
    assert set(SC.CENTRAL_BANKS) == EIGHT
    assert set(SC.JURISDICTION_HOLIDAY_FN) == EIGHT
    assert set(SC.FISCAL_YEAR_ENDS) == EIGHT
    assert set(SC.SIGHTING_AUTHORITIES) == EIGHT


def test_no_other_forest_already_claims_these_eight() -> None:
    """A country belongs to exactly ONE forest. None of the eight may already be on another
    forest's roster, or this pack is competing for ground somebody else answers for."""
    for code in SC.JURISDICTIONS:
        where = F.forest_of_country(code)
        assert where in ("", None, "africa"), f"{code} is already on the {where} forest"


@pytest.mark.xfail(strict=False, reason=(
    "PENDING COORDINATOR REGISTRATION: nine builders share libs/research/forests.py today, so "
    "this pack does not edit it. The africa forest must gain NE, TG, BJ, SL, LR, GM, GW and CV "
    "in `countries` and 'sahel_coast' in `packs`. Until then this is UNMEASURED, not passing."))
def test_the_africa_forest_roster_answers_for_these_eight() -> None:
    roster = {c.lower() for f in F.FORESTS.values() for c in f.countries}
    missing = sorted(set(SC.JURISDICTIONS) - roster)
    assert missing == [], f"{missing} are not on any forest's roster"
    assert CODE in F.forest("africa").packs, "the africa forest does not draw on this pack"


def test_each_jurisdiction_owes_its_own_actors_and_domains() -> None:
    """Two actors and one domain EACH, and three actors and three domains for the five that
    carry the pack's mechanisms -- so it cannot be two countries wearing eight hats."""
    assert len(SC.ACTOR_JURISDICTION) == len(SC.ACTORS)
    carriers = {"ne", "lr", "tg", "bj", "sl"}
    for code in SC.JURISDICTIONS:
        actors = [a for a, j in zip(SC.ACTORS, SC.ACTOR_JURISDICTION, strict=True) if j == code]
        domains = [d for d in SC.DOMAINS
                   if code in SC.DOMAIN_JURISDICTION.get(str(d["id"]), ())
                   and len(SC.DOMAIN_JURISDICTION.get(str(d["id"]), ())) < 4]
        floor_a, floor_d = (3, 3) if code in carriers else (2, 1)
        assert len(actors) >= floor_a, f"{code}: only {len(actors)} actors of its own"
        assert len(domains) >= floor_d, f"{code}: only {len(domains)} domains of its own"
    assert set(SC.DOMAIN_JURISDICTION) == {str(d["id"]) for d in SC.DOMAINS}
    assert SC.jurisdiction_of_domain("SC-A") == ("ne",)
    assert set(SC.jurisdiction_of_domain("SC-U")) == EIGHT


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    for row in SC.ACTORS:
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
    for row in SC.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert len(row["conditions"]) >= 2, f"domain {row['id']} names too few states"
        assert row["instruments"], f"domain {row['id']} names no instrument"
        assert row["id"] in SC.DOMAIN_MECHANISM and row["id"] in SC.DOMAIN_HORIZON


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(SC.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert len(SC.EXECUTABLE_INSTRUMENTS) >= 20
    for row in SC.DOMAINS:
        assert resolve(row["instruments"])["equities"] == [], f"domain {row['id']} names an equity"
        assert set(row["instruments"]) <= set(SC.EXECUTABLE_INSTRUMENTS), (
            f"domain {row['id']} names an instrument the pack never declared executable")


def test_every_transmission_seed_names_tradable_targets() -> None:
    """A seed that terminates in a symbol the box cannot quote can never compile a cell."""
    for seed in SC.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"
    for row in SC.INTERACTIONS:
        assert resolve(row["targets"])["absent"] == [], f"interaction {row['with']}: absent target"
        assert resolve(row["targets"])["equities"] == []


def test_the_six_currencies_and_the_unquoted_commodities_are_named_absent() -> None:
    """XOF, SLE, LRD, GMD and CVE are not quoted here, and neither are uranium, rutile, cashew,
    iron ore, rubber or registry tonnage. Each is named with a route, and the two euro pegs are
    declared EXACT rather than proxied."""
    registry = universe_symbols()
    assert not {"XOF", "SLE", "LRD", "GMD", "CVE", "GNF", "EURXOF", "USDXOF"} & set(registry)
    named = " ".join(str(t["name"]) for t in SC.TRANSMISSION_TARGETS)
    for code in ("XOF", "CVE", "SLE", "LRD", "GMD", "GNF"):
        assert code in named, f"{code} is not named in TRANSMISSION_TARGETS"
    for thing in ("URANIUM", "IRON ORE", "RUTILE", "CASHEW", "RUBBER", "REGISTRY TONNAGE"):
        assert thing in named.upper(), f"{thing} is not named in TRANSMISSION_TARGETS"
    for row in SC.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == []
        assert row["regime"] and row["route"] and row["why"]
    # the two euro pegs are an IDENTITY and the pack says so rather than calling EURUSD a proxy
    pegs = [t for t in SC.TRANSMISSION_TARGETS if "EXACT" in str(t["route"]).upper()]
    assert len(pegs) >= 2, "the XOF and CVE pegs must both be declared EXACT, not proxied"


def test_cot_retail_and_national_reserves_are_declared_absent() -> None:
    """Three absences a study can trip over, each named: no COT contract, no retail flow, and no
    national reserve series at all for the four WAEMU members."""
    absent = [r for r in SC.POSITIONING_SOURCES if not r["available"]]
    assert len(absent) >= 3, "the COT, retail-flow and pooled-reserve questions are not answered"
    assert all("DOES NOT EXIST" in str(r["pit_warning"]) for r in absent)
    blob = " ".join(f"{r['name']} {r['why']} {r['pit_warning']}" for r in absent)
    for must in ("XOF", "SLE", "LRD", "GMD", "CVE", "retail margin", "POOLED"):
        assert must in blob, f"the declared absences never mention {must!r}"


# ------------------------------------------------------------------------------ the languages
def test_terminology_carries_french_portuguese_hausa_and_the_minor_grounds() -> None:
    """Four grounds, because Guinea-Bissau and Cabo Verde live in Portuguese and the Nigerien
    interior trades in Hausa -- and a French-and-English crawl reads neither."""
    assert len(SC.french_terms()) >= 20, f"only {len(SC.french_terms())} French markers present"
    assert len(SC.portuguese_terms()) >= 10
    assert len(SC.hausa_terms()) >= 10
    flat = {t for group in SC.TERMINOLOGY.values() for t in group}
    for must in ("uranium", "oleoduc", "campagne cotonniere", "noix de cajou", "hivernage",
                 "pavillon de complaisance", "redenomination"):
        assert must in flat, f"the Sahel Coast pack does not carry {must!r}"
    for must in ("castanha de caju", "preco de referencia", "escudo", "remessas dos emigrantes"):
        assert must in flat, f"the Portuguese ground does not carry {must!r}"
    for must in ("farashin", "hatsi", "ma'adinai", "ruwan sama"):
        assert must in flat, f"the Hausa ground does not carry {must!r}"
    assert any(SC.has_krio(t) for t in flat), "no Krio vocabulary at all"
    assert any(SC.has_mande(t) for t in flat), "no Mandinka/Wolof/Zarma vocabulary at all"
    assert any(SC.has_african_script(t) for t in flat), "no Latin-Extended African orthography"
    # the word tests must be WORD tests: 'Kenya' must not read as a particle
    assert SC.has_french("campagne cotonniere 2025") and not SC.has_french("cotton campaign")
    assert SC.has_portuguese("preco de referencia") and not SC.has_portuguese("reference price")
    assert SC.has_hausa("farashin hatsi a kasuwa") and not SC.has_hausa("grain market price")
    assert SC.has_krio("wetin de apin na makit") and not SC.has_krio("what is in the market")
    assert SC.has_african_script("gomɛnt") and not SC.has_african_script("government")
    assert len(SC.TERMINOLOGY) >= 15
    assert set(SC.TERMINOLOGY) == {str(d["id"]) for d in SC.DOMAINS}


def test_every_layer_is_queried_in_french_and_portuguese_and_hausa() -> None:
    """A query in English finds an English article about the release, not the release. The three
    grounds a default crawl misses here are French, Portuguese and Hausa, and every one of the
    ten layers must carry all three."""
    terms = SC.layer_terms()
    assert set(terms) == set(SC.SOURCE_LAYERS)
    for layer, qs in terms.items():
        assert any(SC.has_french(q) for q in qs), f"{layer} carries no French query"
        assert any(SC.has_portuguese(q) for q in qs), f"{layer} carries no Portuguese query"
        assert any(SC.has_hausa(q) for q in qs), f"{layer} carries no Hausa query"
    native = sum(1 for row in SC.SOURCE_CLASSES if row["machine_use_allowed"]
                 for q in row["queries"] if SC.has_native(q))
    assert native >= 80, f"only {native} native-language queries across crawlable sources"


def test_every_source_declaring_a_native_language_actually_queries_in_it() -> None:
    """A source that lists `fr`, `pt` or `ha` and queries only in English is an English source
    wearing a flag, and it is how a crawl reads the wrong half of a multilingual region."""
    native_codes = {"fr", "pt", "ha", "kri", "ee", "kbp", "fon", "yo", "mnk", "wo", "dje",
                    "kea", "pov"}
    for row in SC.SOURCE_CLASSES:
        if set(row["languages"]) & native_codes:
            assert any(SC.has_native(q) for q in row["queries"]), (
                f"{row['id']} declares {row['languages']} and every query is in English")


def test_every_source_carries_three_independent_labels_and_a_query() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in SC.SOURCE_CLASSES:
        assert row["access_label"] in SC.ACCESS_LABELS
        assert row["credibility"] in SC.CREDIBILITY_LABELS
        assert row["predictive_state"] in SC.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no query"
        assert row["roots"], f"{row['id']} has no crawlable root"
        assert row["notes"], f"{row['id']} has no note saying why it is here"


def test_all_ten_layers_are_populated_and_the_refusals_name_a_substitute() -> None:
    """The depth rule: ten layers, none blank. With eight jurisdictions the REAL refusals are
    per jurisdiction, and each must name the LAWFUL SUBSTITUTE -- a refusal with no substitute
    is a shrug rather than a route."""
    counts = SC.layer_counts()
    assert set(counts) == set(SC.SOURCE_LAYERS)
    assert [layer for layer, n in counts.items() if not n] == []
    coverage = SC.source_layer_coverage()
    assert coverage["n_layers_covered"] == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], (
        "nothing is registered machine-use-forbidden, which is implausible for a region whose "
        "uranium, rutile and cashew prices live behind price-reporting-agency terms")
    assert coverage["low_weight_kept"], "no fringe ground is kept at all, so it was dropped"
    assert SC.LAYER_ABSENCES == {}
    assert len(SC.NO_LAWFUL_GROUND) >= 10
    for row in SC.NO_LAWFUL_GROUND:
        assert row["jurisdiction"] in SC.JURISDICTIONS
        assert row["layer"] in SC.SOURCE_LAYERS
        assert len(row["reason"]) > 80, f"{row['jurisdiction']}/{row['layer']}: reason too thin"
        assert "SUBSTITUTE" in row["reason"].upper(), (
            f"{row['jurisdiction']}/{row['layer']}: a refusal with no named lawful substitute")
    # the asymmetry is the measurement: gw and ne must carry more gaps than cv
    gaps = SC.JURISDICTION_LAYER_GAPS
    assert set(gaps) == EIGHT
    assert len(gaps["gw"]) >= 3, "Guinea-Bissau's real statistical holes are not declared"
    assert len(gaps["ne"]) >= 2, "Niger's post-2023 narrowing is not declared"


def test_query_territories_give_the_deep_forest_miner_three_phrases_per_layer() -> None:
    assert set(SC.QUERY_TERRITORIES) == set(SC.SOURCE_LAYERS)
    for layer, phrases in SC.QUERY_TERRITORIES.items():
        assert len(phrases) >= 3, f"{layer}: only {len(phrases)} query territories"
        assert any(SC.has_native(p) for p in phrases), f"{layer}: no native-language phrase"


# ------------------------------------------------------------------------------ the calendars
def test_easter_is_computed_and_everything_hangs_off_it() -> None:
    """The ANONYMOUS GREGORIAN ALGORITHM, not a typed table: a typed Easter is right for the
    three years somebody checked and silently wrong afterwards."""
    assert SC.western_easter(2024) == date(2024, 3, 31)
    assert SC.western_easter(2025) == date(2025, 4, 20)
    assert SC.western_easter(2026) == date(2026, 4, 5)
    assert SC.western_easter(2030) == date(2030, 4, 21)
    assert SC.good_friday(2025) == date(2025, 4, 18)
    assert SC.easter_monday(2025) == date(2025, 4, 21)
    assert SC.ascension(2025) == date(2025, 5, 29)
    assert SC.whit_monday(2025) == date(2025, 6, 9)
    # Carnival Tuesday is Easter minus 47 days and is THE Cabo Verdean closure
    assert SC.carnival_tuesday(2025) == date(2025, 3, 4)
    assert SC.carnival_tuesday(2024) == date(2024, 2, 13)


def test_the_three_liberian_weekday_rules_are_computed_not_typed() -> None:
    """Decoration Day is the SECOND WEDNESDAY of March, Fast and Prayer the SECOND FRIDAY of
    April and Thanksgiving the FIRST THURSDAY of November -- a typed table gets all three
    wrong every year."""
    assert SC.nth_weekday(2025, 3, 2, 2) == date(2025, 3, 12)
    assert SC.nth_weekday(2025, 4, 4, 2) == date(2025, 4, 11)
    assert SC.nth_weekday(2025, 11, 3, 1) == date(2025, 11, 6)
    lr = SC.liberian_holidays(2025)
    assert lr[date(2025, 3, 12)] == "Decoration Day"
    assert lr[date(2025, 4, 11)] == "National Fast and Prayer Day"
    assert lr[date(2025, 11, 6)] == "National Thanksgiving Day"
    assert date(2025, 7, 26) in lr, "Liberian Independence Day is 26 July"


def test_the_holiday_tables_resolve_for_three_years_and_stay_inside_them() -> None:
    for year in (2024, 2025, 2026):
        table = holiday_table(SC.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        assert f"{year}-01-01" in table
        assert f"{year}-05-01" in table, "Labour Day is missing"
        for code in SC.JURISDICTIONS:
            assert SC.JURISDICTION_HOLIDAY_FN[code](year), f"{code} has no {year} table"
    # the union rows are TAGGED, because with eight calendars most days are one-country days
    t25 = holiday_table(SC.HOLIDAYS_RULE, 2025)
    assert "[NE]" in t25["2025-12-18"], "Niger's Republic Day closes Niger alone"
    assert "[BJ]" in t25["2025-01-10"], "Benin's Vodun day closes Benin alone"
    assert "[GM]" in t25["2025-02-18"], "Gambian Independence Day closes The Gambia alone"
    assert "[GW]" in t25["2025-09-24"], "Bissau-Guinean Independence Day"
    assert "[CV]" in t25["2025-07-05"], "Cabo Verdean Independence Day"
    assert "[LR]" in t25["2025-07-26"], "Liberian Independence Day"
    assert SC.closed_in("ne", date(2025, 12, 18))
    assert not SC.closed_in("cv", date(2025, 12, 18))
    # LABOUR DAY CLOSES SEVEN OF THE EIGHT AND NOT LIBERIA, which has no 1 May holiday -- the
    # kind of asymmetry a pooled "West African holiday" dummy erases
    assert SC.closures_on(date(2025, 5, 1)) == tuple(sorted(EIGHT - {"lr"}))
    assert not SC.closed_in("lr", date(2025, 5, 1))
    assert SC.closures_on(date(2025, 7, 26)) == ("lr",)
    assert all(d.weekday() < 5 for d in SC.market_holidays(2025))
    assert not SC.is_market_holiday(date(2025, 3, 5))


def test_the_islamic_feasts_are_declared_with_five_sighting_authorities() -> None:
    """Five authorities announce independently and West African observance routinely runs a day
    later than the Gulf. A rule would be a wrong rule."""
    assert "sighting" in SC.HOLIDAYS_RULE["rule"].lower()
    assert "PROJECTED" in str(SC.HOLIDAYS_RULE["status"][2026]).upper()
    assert date(2025, 3, 31) in SC.announced_dates(2025), "Aid el-Fitr 2025 is 2025-03-31"
    assert all(st == "PROJECTED" for *_, st in SC.LUNAR_HOLIDAYS[2026])
    # Liberia does not close for Mouloud and Cabo Verde closes for no Islamic feast at all
    assert date(2025, 9, 5) in SC.nigerien_holidays(2025)
    assert date(2025, 9, 5) in SC.sierra_leonean_holidays(2025)
    assert date(2025, 9, 5) not in SC.liberian_holidays(2025)
    assert date(2025, 6, 7) not in SC.cabo_verdean_holidays(2025), "CV observes no Eid"
    assert date(2025, 6, 7) in SC.liberian_holidays(2025), "LR observes the two Eids"
    assert set(SC.MAWLID_OBSERVERS) < set(SC.EID_OBSERVERS) < EIGHT
    assert "NONE" in SC.SIGHTING_AUTHORITIES["cv"].upper()


def test_seven_of_the_eight_are_gmt_and_cabo_verde_is_not() -> None:
    """A pack that assumed one African offset would mis-stamp every Cabo Verdean row by an hour
    and every Liberian registry announcement by five."""
    assert "UTC-1" in SC.HOLIDAYS_RULE["timezone_rule"]
    windows = {w["name"]: w for w in SC.SESSION_WINDOWS}
    assert windows["sc_cv_session"]["start_utc"] == "10:00"
    assert windows["sc_lr_registry_session"]["start_utc"] == "14:00"
    for fx in SC.FIXING_CONVENTIONS:
        if "LBMA" not in fx["name"] and "ICE" not in fx["name"]:
            assert fx["time_utc"] == fx["time_utc_dst"], f"{fx['name']} moves with a DST rule"


# ------------------------------------------------------------------------------ the mechanisms
def test_the_niger_bloc_rupture_has_five_dates_and_four_states() -> None:
    assert SC.niger_bloc_state(date(2023, 7, 1)) == "PRE_SANCTIONS"
    assert SC.niger_bloc_state(date(2023, 8, 1)) == "SANCTIONED"
    assert SC.niger_bloc_state(date(2024, 6, 1)) == "LIFTED_WITHDRAWAL_ANNOUNCED"
    assert SC.niger_bloc_state(date(2025, 6, 1)) == "WITHDRAWN_AES"
    assert SC.ECOWAS_EXIT_EFFECTIVE.isoformat() == "2025-01-29"
    assert {st for *_r, st in SC.ECOWAS_EVENTS} <= {"ANNOUNCED", "PRESS_REPORTED", "PROJECTED"}
    assert any(str(e["start"]) == "2023-07-26" for e in SC.POLICY_ERAS)


def test_the_uranium_and_pipeline_clocks_are_separate_series() -> None:
    """Ownership and deliveries are DIFFERENT series; the pipeline has a political on/off switch."""
    assert SC.uranium_regime(date(2023, 1, 1)) == "OPERATOR_RUN"
    assert SC.uranium_regime(date(2023, 8, 1)) == "POST_COUP_UNCHANGED"
    assert SC.uranium_regime(date(2024, 7, 1)) == "IMOURAREN_PERMIT_WITHDRAWN"
    assert SC.uranium_regime(date(2025, 1, 1)) == "SOMAIR_CONTROL_LOST"
    assert SC.uranium_regime(date(2025, 12, 1)) == "SOMAIR_NATIONALISED"
    assert SC.pipeline_state(date(2024, 1, 1)) == "PRE_FIRST_EXPORT"
    assert SC.pipeline_state(date(2024, 5, 20)) == "FLOWING"
    assert SC.pipeline_state(date(2024, 6, 15)) == "INTERRUPTED"
    assert SC.pipeline_state(date(2025, 1, 1)) == "RESUMED"
    assert all(st in ("ANNOUNCED", "PRESS_REPORTED", "PROJECTED")
               for *_r, st in SC.URANIUM_EVENTS), (
        "a uranium date is announced, PRESS_REPORTED or projected and never presented as a "
        "citation it is not")


def test_the_three_fx_regimes_and_the_two_exact_parities() -> None:
    """Four XOF members, one CVE peg with a DIFFERENT guarantor, one dollarised float and two
    clean floats -- the natural experiment SC-U is built on."""
    assert SC.fx_regime("ne") == SC.fx_regime("gw") == "EURO_PEG_XOF"
    assert SC.fx_regime("cv") == "EURO_PEG_CVE"
    assert SC.fx_regime("lr") == "FLOAT_DOLLARISED"
    assert SC.fx_regime("sl") == SC.fx_regime("gm") == "FLOAT"
    assert SC.eur_parity("bj") == pytest.approx(655.957)
    assert SC.eur_parity("cv") == pytest.approx(110.265)
    assert SC.eur_parity("sl") == 0.0
    assert sum(1 for c in SC.JURISDICTIONS if SC.CURRENCIES[c] == "XOF") == 4, (
        "FOUR of the eight use the XOF; the other four WAEMU members belong to `west_africa`")


def test_the_leone_redenomination_is_a_unit_change_and_the_pack_knows_the_scale() -> None:
    assert SC.LEONE_REDENOMINATION.isoformat() == "2022-07-01"
    assert SC.leone_scale(date(2022, 6, 30)) == pytest.approx(1000.0)
    assert SC.leone_scale(date(2022, 7, 1)) == pytest.approx(1.0)
    assert SC.leone_scale(date(2026, 1, 1)) == pytest.approx(1.0)
    assert any("redenomination" in str(e["name"]).lower() for e in SC.POLICY_ERAS)


def test_the_agronomic_and_campaign_clocks() -> None:
    """The soudure sits INSIDE the rains, which a temperate intuition gets backwards."""
    assert SC.sahel_season(date(2025, 1, 15)) == "HARMATTAN"
    assert SC.sahel_season(date(2025, 4, 15)) == "HOT_DRY"
    assert SC.sahel_season(date(2025, 7, 15)) == "RAINY_SOUDURE"
    assert SC.sahel_season(date(2025, 10, 15)) == "HARVEST"
    assert SC.cotton_campaign_phase(date(2025, 6, 1)) == "SOWING"
    assert SC.cotton_campaign_phase(date(2025, 11, 1)) == "HARVEST"
    assert SC.cotton_campaign_phase(date(2025, 2, 1)) == "GINNING"
    assert SC.cashew_campaign_phase(date(2025, 4, 15)) == "OPENING"
    assert SC.cashew_campaign_phase(date(2025, 7, 15)) == "BUYING"
    assert SC.cashew_campaign_phase(date(2025, 12, 1)) == "CLOSED"
    # Tabaski drifts about eleven days earlier each solar year: free identification
    assert SC.days_to_tabaski(date(2025, 6, 1)) == 6
    assert SC.days_to_tabaski(date(2025, 6, 8)) == (date(2026, 5, 27) - date(2025, 6, 8)).days
    assert SC.days_to_tabaski(date(2027, 1, 1)) == -1, "past the table is UNMEASURED, not zero"


# ------------------------------------------------------------------------------ the cells
def test_the_pack_mints_cells_inside_its_domains_and_not_as_a_cartesian_blow_up() -> None:
    """A cell is only worth a trial if this pack's own data plane can evaluate its CONDITION on
    that SYMBOL, so the cross product is taken INSIDE each domain."""
    rows = SC.cells()
    assert 60 <= len(rows) <= 260, f"{len(rows)} cells is outside the honest range"
    assert len(rows) == len(SC.CELLS)
    assert len({r["cell_id"] for r in rows}) == len(rows), "duplicate cell_id"
    domain_ids = {str(d["id"]) for d in SC.DOMAINS}
    for row in rows:
        for field in ("cell_id", "domain", "symbol", "condition", "mechanism_family",
                      "horizon", "control", "why"):
            assert row[field], f"{row['cell_id']}: {field} is empty"
        assert row["domain"] in domain_ids
        assert row["symbol"] in SC.EXECUTABLE_INSTRUMENTS
        assert set(row["jurisdictions"]) <= EIGHT
    assert resolve(sorted({r["symbol"] for r in rows}))["equities"] == []
    assert {r["domain"] for r in rows} == domain_ids, "a domain that mints no cell is decorative"


def test_every_dataset_carries_all_twelve_fields_and_a_fetchable_route() -> None:
    from countries import DATASET_FIELDS
    for ds in SC.DATASETS:
        for field in DATASET_FIELDS:
            if field in ("pit_feasible", "publication_lag_days"):
                continue
            assert ds[field], f"dataset {ds.get('name')!r}: {field} is empty"
        assert float(ds["publication_lag_days"]) >= 0.0
        assert len(str(ds["how_to_fetch"])) > 40, (
            f"dataset {ds['name']!r}: how_to_fetch is not concrete enough for a collector")
        assert resolve(ds["assets"])["equities"] == []
        assert resolve(ds["assets"])["absent"] == []
    not_pit = {str(d["name"]) for d in SC.DATASETS if not d["pit_feasible"]}
    assert any("UMOA-Titres" in n for n in not_pit), (
        "the auction portal overwrites in place and cannot be pit_feasible")
    assert any("Registry" in n for n in not_pit), (
        "the registry fleet page keeps no history and cannot be pit_feasible")


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {f"custom:{name}" for name in SC.MINERS}
    ids = {str(d["id"]) for d in SC.DOMAINS}
    entries = set()
    for row in SC.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.sahel_coast.pack", row["entry"]
        assert callable(getattr(SC, func)), f"{row['entry']} does not resolve"
        entries.add(func)
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    assert entries == set(SC.MINERS)
    for did in SC.MINER_DOMAINS.values():
        assert set(did) <= ids


def test_mine_returns_a_report_and_emits_nothing_without_a_context() -> None:
    """`mine(None)` is how a test and a fresh session check the pack with nothing wired."""
    report = SC.mine(None)
    assert report["code"] == CODE
    assert tuple(report["jurisdictions"]) == SC.JURISDICTIONS
    assert report["emitted"] == 0, "mine(None) emitted to a registry that does not exist"
    assert report["rows"], "mine(None) produced no rows at all"
    assert report["cells_emitted"] == len(SC.cells())
    assert report["at"].endswith("+00:00"), "the stamp must be timezone-aware UTC"
    assert set(report["miners"]) == set(SC.MINERS)
    assert report["layers_covered"] == 10
    assert report["datasets"] == len(SC.DATASETS)
    assert "west_africa" in report["interactions"], (
        "`west_africa` owns the other half of this system and must be named as an interaction")
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
    report = SC.mine(ctx)
    assert report["emitted"] == len(ctx.rows) == len(report["rows"])
    assert report["emitted"] > 0


def test_the_interactions_name_real_sibling_packs_and_west_africa_is_first() -> None:
    """An edge whose control lives in a pack nobody runs is an edge nobody can falsify."""
    from countries import codes
    present = set(codes())
    for row in SC.INTERACTIONS:
        assert row["with"] in present, f"interaction names {row['with']!r}, which is not a pack"
        assert row["mechanism"] and row["observable"] and row["control"]
        assert row["targets"]
    assert SC.INTERACTIONS[0]["with"] == "west_africa", (
        "`west_africa` owns the BCEAO, the cocoa complex and the Sahel gold of Mali and Burkina; "
        "this pack is its declared COMPLEMENT and that interaction belongs first")
    assert SC.INTERACTIONS[0]["with"] not in {r["with"] for r in SC.INTERACTIONS[1:]}
