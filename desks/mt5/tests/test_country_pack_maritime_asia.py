"""THE MARITIME AND HIMALAYAN ASIA PACK, VALIDATED -- five single-factor economies, four
calendar systems, five scripts, and every absent layer named with its lawful substitute.

WHAT THESE TESTS REFUSE TO LET THROUGH, and each one is a failure this desk has had:

  * A PROXY DRESSED AS AN EXACT EXPRESSION. The Brunei dollar is at par with the Singapore
    dollar by treaty and the ngultrum at par with the rupee by statute, so USDSGD and USDINR
    ARE those two economies' external value with zero basis. That is a much stronger claim than
    a correlation and it is asserted here as arithmetic, not as prose.
  * AN ENGLISH-ONLY CRAWL OF FIVE NON-ENGLISH GROUNDS. Malay in Jawi AND Rumi, Tetum and
    Portuguese, Dhivehi in Thaana, Dzongkha in Tibetan, Dari and Pashto in Arabic. All five are
    counted here, per script, so the pack cannot quietly become an English glossary.
  * ONE CALENDAR ASSUMED FOR FIVE JURISDICTIONS. Four systems run here and no rule computes more
    than one: the Catholic feasts and Nowruz are DERIVED, the Islamic and Tibetan rows are TYPED
    with their authority. All four are checked across 2024, 2025 and 2026.
  * A PADDED SOURCE LIST HIDING A BLIND COUNTRY. Afghanistan is missing most layers outright;
    the test counts NO_LAWFUL_GROUND rows per jurisdiction and insists each names a substitute.
  * AN OBSERVABLE WITH NO EXECUTABLE LEG PRETENDING OTHERWISE. Opium, LNG contracts, arrivals
    and hydro generation are not broker symbols; each is routed with its control and its
    declared strength, and the opium row must say NONE_DIRECT.
  * A SINGLE-NAME EQUITY ON A DOCKET, or a symbol the box cannot quote, anywhere in the pack.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
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
from countries.maritime_asia import pack as MA  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as FORESTS  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")
#: What this pack claims about itself, asserted rather than trusted. `pack_depth` must reach it.
DECLARED_DEPTH = 1.0
#: The five, and the pack owes each of them actors, domains and ground of its own.
FIVE = ("bn", "tl", "mv", "bt", "af")


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it, resolved through `resolve_pack` so the test measures
    the same object the country lab runs and not a private construction."""
    got = CL.resolve_pack("maritime_asia")
    assert got is not None, "no maritime_asia pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(MA.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == "maritime_asia"
    assert str(get(built, "region_command")) == "asia"
    assert str(get(built, "currency")) == "BND"
    assert MA.FOREST == "south_asia"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    """A coercion note is a field `CountryPack` could not read. There must be none."""
    notes = list(getattr(built, "coercion_notes", ()) or ())
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    assert CL.fatal_problems(CL.validate_pack(built)) == []


def test_jurisdictions_are_exactly_the_five_this_pack_claims() -> None:
    """The parity fence counts this tuple. Five lowercase ISO-2 codes, no more and no less."""
    assert MA.JURISDICTIONS == FIVE
    assert all(j == j.lower() and len(j) == 2 for j in MA.JURISDICTIONS)
    assert len(set(MA.JURISDICTIONS)) == 5
    assert set(MA.ROSTER_JURISDICTIONS) | set(MA.BEYOND_ROSTER) == set(MA.JURISDICTIONS)
    assert not set(MA.ROSTER_JURISDICTIONS) & set(MA.BEYOND_ROSTER)


def test_every_jurisdiction_is_on_the_roster_or_declared_beyond_it_with_a_reason() -> None:
    """NONE OF THE FIVE IS ON `forests.py` AS THIS PACK IS WRITTEN, and the pack says so rather
    than implying a coverage the fence cannot cash. The forest file is the coordinator's and is
    not edited from here, so this test MEASURES the roster instead of asserting a fixed answer:
    a code moving onto the roster later must not red the gate, it only means the two tuples want
    re-splitting.
    """
    named = {c.lower() for f in FORESTS.FORESTS.values() for c in getattr(f, "countries", ())}
    assert named, "the forest roster is unreadable -- UNMEASURED, so nothing here is checked"
    for code in MA.ROSTER_JURISDICTIONS:
        assert code in named, f"{code} is declared on-roster and is not on the forest roster"
    for code, why in MA.BEYOND_ROSTER.items():
        assert len(why) > 80, f"{code} is claimed beyond the roster with no real reason"
    for code in MA.JURISDICTIONS:
        assert code in named or code in MA.BEYOND_ROSTER, (
            f"{code} is neither on the roster nor declared beyond it")
    # The forest this pack asks to be registered on must exist, whatever it currently holds.
    assert MA.FOREST in FORESTS.FORESTS, f"{MA.FOREST} is not a forest"


def test_pack_reaches_its_declared_parity_depth(built: Any) -> None:
    """The standing depth rule, measured by the framework and not claimed by the pack."""
    row = RP.pack_depth(built, "maritime_asia").as_row()
    assert row["score"] >= DECLARED_DEPTH, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_a_five_jurisdiction_pack_is_sized_for_five() -> None:
    """Five jurisdictions owe five jurisdictions' worth of work, not twelve actors total."""
    assert len(MA.ACTORS) >= 20
    assert len(MA.DOMAINS) >= 14
    assert len(MA.TRANSMISSION_EDGES_SEED) >= 12
    assert len(MA.DATASETS) >= 18
    assert len(MA.SOURCE_CLASSES) >= 20
    assert len(MA.POLICY_ERAS) >= 8
    assert len(MA.INTERACTIONS) >= 4
    assert MA.term_count() >= 120


def test_every_jurisdiction_owes_its_own_actors_and_domains() -> None:
    """THREE ACTORS AND TWO DOMAINS APIECE, COUNTED. A multi-jurisdiction pack that credits
    itself with a country it did not write is worse than a missing pack, because the parity
    fence then reads the gap as closed."""
    coverage = MA.jurisdiction_coverage()
    for code in FIVE:
        assert coverage[code]["actors"] >= 3, f"{code}: {coverage[code]['actors']} actors"
        assert coverage[code]["domains"] >= 2, f"{code}: {coverage[code]['domains']} domains"
        assert coverage[code]["n_sourced"] >= 4, f"{code}: only {coverage[code]['n_sourced']} "
    # and every jurisdiction is actually named by at least one source root
    for code in FIVE:
        assert any(code in tuple(s.get("jurisdictions") or ()) for s in MA.SOURCE_CLASSES), code


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    for row in MA.ACTORS:
        for f in ACTOR_FIELDS:
            assert row.get(f), f"actor {row.get('name')!r} has an empty {f}"
        # a one-element tuple written without its trailing comma silently becomes a string, and
        # `tuple("abc")` is then three characters -- this catches that class of typo
        for f in ("forced_to", "information", "constraints", "instruments", "counterparties",
                  "observables"):
            value = row[f]
            assert isinstance(value, tuple), f"actor {row.get('name')!r}.{f} is not a tuple"
            assert all(len(str(v)) > 2 for v in value), (
                f"actor {row.get('name')!r}.{f} looks like a string split into characters")
        assert set(row["jurisdictions"]) <= set(FIVE), row["name"]


def test_every_domain_has_objects_and_two_negative_controls() -> None:
    """Without a control an effect cannot be told from the desk's own sampling."""
    ids = set()
    for row in MA.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert row["conditions"], f"domain {row['id']} names no conditioning state"
        assert row["id"] not in ids, f"domain {row['id']} declared twice"
        ids.add(row["id"])
        assert set(row["jurisdictions"]) <= set(FIVE), row["id"]


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing is checked"
    split = resolve(MA.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], f"{split['equities']} is a single-name equity"
    assert len(MA.EXECUTABLE_INSTRUMENTS) == len(set(MA.EXECUTABLE_INSTRUMENTS))
    for must in ("USDSGD", "USDINR", "XNGUSD", "XAUUSD", "US500"):
        assert must in MA.EXECUTABLE_INSTRUMENTS


def test_no_single_name_equity_anywhere_in_the_pack() -> None:
    """Every symbol pool in the pack, against the broker's OWN registry and equity classifier."""
    pools: list[tuple[str, tuple[str, ...]]] = [("executables", MA.EXECUTABLE_INSTRUMENTS)]
    pools += [(f"domain {d['id']}", tuple(d["instruments"])) for d in MA.DOMAINS]
    pools += [(f"edge {e['id']}", tuple(e["targets"])) for e in MA.TRANSMISSION_EDGES_SEED]
    pools += [(f"interaction {r['with']}", tuple(r["targets"])) for r in MA.INTERACTIONS]
    pools += [(f"target {t['name'][:30]}", tuple(t["proxies"])) for t in MA.TRANSMISSION_TARGETS]
    pools += [(f"route {r['observable'][:30]}", tuple(r["route"])) for r in MA.NO_EXECUTABLE_LEG]
    pools += [(f"dataset {d['name'][:30]}", tuple(d["assets"])) for d in MA.DATASETS]
    pools += [(f"actor {a['name'][:30]}", tuple(a["instruments"])) for a in MA.ACTORS]
    for where, symbols in pools:
        split = resolve(symbols)
        assert split["equities"] == [], f"{where}: {split['equities']} is a single-name equity"
        assert split["absent"] == [], f"{where}: {split['absent']} is not in the registry"


def test_the_five_local_currencies_are_named_absent_rather_than_dropped() -> None:
    """BND, MVR, BTN and AFN are not quoted and Timor-Leste has no currency at all."""
    registry = universe_symbols()
    assert not {"USDBND", "BND", "USDMVR", "MVR", "USDBTN", "BTN", "USDAFN", "AFN"} & set(registry)
    named = " ".join(str(t["name"]) for t in MA.TRANSMISSION_TARGETS)
    for iso in ("BND", "BTN", "MVR", "AFN"):
        assert iso in named, f"{iso} is absent from the broker and is not named as a target"
    for row in MA.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == []
    assert set(MA.CURRENCIES) == set(FIVE)


def test_the_two_par_links_are_declared_exact_and_not_proxies() -> None:
    """THE PACK'S FIRST AND STRONGEST CLAIM. A treaty or statutory par at 1:1 is not a
    correlation: USDSGD IS Brunei's external value and USDINR IS Bhutan's."""
    bn = MA.par_expression("bn", 1.3500)
    assert bn["is_exact"] is True and bn["basis_risk"] == 0.0
    assert bn["symbol"] == "USDSGD" and bn["par_with"] == "SGD" and bn["par_rate"] == 1.0
    assert bn["local_per_usd"] == pytest.approx(1.3500, abs=1e-12)
    assert bn["since"] == "1967-06-12"
    bt = MA.par_expression("bt", 84.50)
    assert bt["is_exact"] is True and bt["symbol"] == "USDINR"
    assert bt["local_per_usd"] == pytest.approx(84.50, abs=1e-12)
    assert bt["since"] == "1974-04-01"
    # the other three are NOT par links and must not claim to be
    for code in ("tl", "mv", "af"):
        assert MA.par_expression(code, 1.0)["is_exact"] is False, code
    assert MA.CURRENCIES["tl"]["iso"] == "USD", "Timor-Leste IS the dollar"
    with pytest.raises(ValueError):
        MA.par_expression("zz", 1.0)


# ------------------------------------------------------------------------------ the languages
def test_terminology_carries_all_five_native_scripts() -> None:
    """FIVE SCRIPTS. An English-only crawl of these five grounds reads none of them."""
    counts = MA.languages_present()
    assert counts["arabic_script"] >= 25, counts   # Jawi plus Dari/Pashto
    assert counts["thaana"] >= 12, counts          # Dhivehi, right-to-left
    assert counts["tibetan"] >= 5, counts          # Dzongkha
    assert counts["jawi_markers"] >= 8, counts
    assert counts["malay_rumi"] >= 12, counts
    assert counts["tetum"] >= 8, counts
    assert counts["portuguese"] >= 10, counts
    flat = {t for group in MA.TERMINOLOGY.values() for t in group}
    for must in ("ރުފިޔާ", "ފަތުރުވެރިކަން", "འབྲུག་ཡུལ།", "དངུལ་ཀྲམ།", "د افغانستان بانک",
                 "تریاک", "بروني دارالسلام", "تيتح", "Fundo Petrolifero",
                 "Rendimento Sustentavel Estimado", "Perjanjian Pertukaran Mata Wang"):
        assert must in flat, f"the pack does not carry {must!r}"
    assert MA.has_thaana("ރުފިޔާ") and not MA.has_thaana("rufiyaa")
    assert MA.has_tibetan("འབྲུག་ཡུལ།") and not MA.has_tibetan("Druk Yul")
    assert MA.has_arabic("تيتح") and not MA.has_arabic("titah")
    assert len(MA.TERMINOLOGY) >= 15
    with pytest.raises(ValueError):
        MA.has_script("x", "devanagari")


def test_every_layers_queries_are_written_in_the_native_scripts() -> None:
    """A query in English finds an English article about the release, not the release."""
    terms = MA.layer_terms()
    scripted = [layer for layer, qs in terms.items()
                if any(MA.has_arabic(q) or MA.has_thaana(q) or MA.has_tibetan(q) for q in qs)]
    assert len(scripted) >= 8, f"only {scripted} carry a non-Latin query"
    latin_markers = ("Fundo", "relatorio", "Jornal", "minyak", "warta", "Perjanjian",
                     "Restauracao", "Orcamento", "kemaskini", "arkib")
    latin_layers = [layer for layer, qs in terms.items()
                    if any(m in q for q in qs for m in latin_markers)]
    assert len(latin_layers) >= 4, f"only {latin_layers} carry a Malay/Portuguese query"
    native = sum(1 for row in MA.SOURCE_CLASSES if row["machine_use_allowed"]
                 for q in row["queries"]
                 if MA.has_arabic(q) or MA.has_thaana(q) or MA.has_tibetan(q))
    assert native >= 35, f"only {native} native-script queries across crawlable sources"


def test_query_territories_cover_every_live_layer_natively() -> None:
    """The deep-forest miner runs THESE. Three per layer is the floor."""
    for layer in MA.SOURCE_LAYERS:
        if layer in MA.LAYER_ABSENCES:
            continue
        rows = MA.QUERY_TERRITORIES.get(layer, ())
        assert len(rows) >= 3, f"layer {layer}: only {len(rows)} query territories"
        assert any(MA.has_arabic(q) or MA.has_thaana(q) or MA.has_tibetan(q)
                   or any(m in q for m in ("Fundo", "minyak", "warta", "relatorio", "Jornal",
                                           "Orcamento", "arkib", "kemaskini"))
                   for q in rows), f"layer {layer}: no native-language territory"


def test_every_source_carries_three_independent_labels_and_a_query() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in MA.SOURCE_CLASSES:
        assert row["access_label"] in MA.ACCESS_LABELS
        assert row["credibility"] in MA.CREDIBILITY_LABELS
        assert row["predictive_state"] in MA.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no native-language query"
        assert row["roots"], f"{row['id']} has no crawlable root"
    with pytest.raises(ValueError):
        MA.source_class("x", "x", layer="nope", roots=(), queries=(), languages=(),
                        access_label="PUBLIC", credibility="RELIABLE",
                        predictive_state="UNTESTED", licence="")


def test_all_ten_layers_are_populated_and_the_holes_are_per_jurisdiction() -> None:
    """The depth rule regionally, AND the per-jurisdiction refusal beside it."""
    counts = MA.layer_counts()
    assert set(counts) == set(MA.SOURCE_LAYERS)
    coverage = MA.source_layer_coverage()
    assert coverage["n_layers_covered"] == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible for a pack whose "
        "LNG factor's only screen is a licensed assessment")
    assert coverage["low_weight_kept"], "no fringe or unreliable ground is kept at all"


def test_no_lawful_ground_names_every_absence_with_a_substitute() -> None:
    """A MEASURED NO_LAWFUL_GROUND ROW WITH A NAMED SUBSTITUTE IS THE POINT, and for Afghanistan
    it may be this pack's most valuable output."""
    assert len(MA.NO_LAWFUL_GROUND) >= 10
    seen: set[tuple[str, str]] = set()
    for row in MA.NO_LAWFUL_GROUND:
        key = (str(row["jurisdiction"]), str(row["layer"]))
        assert key not in seen, f"{key} declared twice"
        seen.add(key)
        assert row["jurisdiction"] in FIVE
        assert row["layer"] in MA.SOURCE_LAYERS
        assert len(str(row["reason"])) > 60, f"{key}: the reason is too thin to act on"
        assert len(str(row["substitute"])) > 40, f"{key}: no real substitute named"
        assert str(row["substitute_root"]).startswith("http"), key
    # the four named in the brief, by jurisdiction
    absent_by = {j: {lay for j2, lay in seen if j2 == j} for j in FIVE}
    assert "institutional" in absent_by["bn"], "Brunei's undisclosed sovereign fund"
    assert "academic" in absent_by["tl"] and "academic" in absent_by["mv"]
    assert "retail_ecology" in absent_by["bt"], "Bhutan has no retail ecology"
    assert len(absent_by["af"]) >= 4, "Afghanistan is missing most layers and must say so"
    with pytest.raises(ValueError):
        MA.jurisdiction_absence("zz", "official", reason="x", substitute="y", substitute_root="z")


def test_observables_with_no_executable_leg_are_routed_with_their_strength_declared() -> None:
    """LNG contracts, arrivals, hydro generation and OPIUM are not broker symbols. Each is
    routed with its control named, and where the transmission is weak the pack says so."""
    assert len(MA.NO_EXECUTABLE_LEG) >= 4
    strengths = {str(r["observable"]): str(r["strength"]) for r in MA.NO_EXECUTABLE_LEG}
    assert any("opium" in k.lower() for k in strengths), "the opium row is missing"
    opium = next(v for k, v in strengths.items() if "opium" in k.lower())
    assert opium == "NONE_DIRECT", "the opium observable must declare it has no executable leg"
    assert any(v == "WEAK" for v in strengths.values()), "no route is declared weak, implausibly"
    for row in MA.NO_EXECUTABLE_LEG:
        assert row["jurisdiction"] in FIVE
        assert row["route"] and resolve(row["route"])["absent"] == []
        assert len(str(row["control"])) > 40, f"{row['observable']}: no real control"
        assert len(str(row["why"])) > 60


def test_lawfulness_is_a_field_and_names_the_afghan_measures(built: Any) -> None:
    """Sanctions constrain TRANSACTIONS, not the reading of published statistics."""
    blob = " ".join(str(c["constraint"]) + str(c["measured"]) + str(c["consequence"])
                    for c in MA.ACCESS_CONSTRAINTS)
    assert "SANCTIONS CONSTRAIN TRANSACTIONS" in blob.upper()
    assert "PERSONAL DATA" in blob.upper()
    assert "private systems" in blob.lower()
    assert "two-lane" in blob
    assert "NO SECURITIES" in blob.upper() or "no exchange at all" in blob.lower()
    assert len(MA.ACCESS_CONSTRAINTS) >= 8


# ------------------------------------------------------------------------------ the calendars
def test_four_calendar_systems_run_across_five_jurisdictions() -> None:
    """THE PACK'S DISTINGUISHING CALENDAR FACT, computed rather than asserted."""
    systems = {j: set(MA.calendar_systems(j)) for j in FIVE}
    assert "islamic_lunar" in systems["bn"] & systems["mv"] & systems["af"]
    assert "solar_hijri" in systems["af"] and "solar_hijri" not in systems["bt"]
    assert "tibetan_lunisolar" in systems["bt"]
    assert "gregorian_catholic_movable" in systems["tl"]
    assert "chinese_lunisolar" in systems["bn"]
    distinct = {s for row in systems.values() for s in row} - {"gregorian_civil"}
    assert len(distinct) >= 4, f"only {distinct}"
    rule = str(MA.HOLIDAYS_RULE["rule"])
    assert "FOUR DIFFERENT CALENDAR SYSTEMS" in rule
    assert "SOLAR HIJRI" in rule and "TIBETAN LUNISOLAR" in rule and "ISLAMIC LUNAR" in rule


def test_the_holiday_table_resolves_for_every_declared_year() -> None:
    """Every date inside its own year, in all three years, across all four calendars."""
    for year in (2024, 2025, 2026):
        table = holiday_table(MA.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        assert f"{year}-12-17" in table, "Bhutan's National Day is a fixed solar date"
        assert f"{year}-02-21" in table, "the King of Bhutan's birthday, 21 February"
        assert f"{year}-02-23" in table, "Brunei's National Day, 23 February"
        assert f"{year}-07-26" in table, "Maldivian Independence Day, 26 July"
        assert f"{year}-05-20" in table, "Timor-Leste Restoration of Independence"
        assert f"{year}-08-30" in table, "Timor-Leste Popular Consultation"
        assert f"{year}-11-28" in table, "Timor-Leste Proclamation of Independence"


def test_easter_is_computed_for_timor_leste_and_never_typed() -> None:
    """The Catholic half of Timor-Leste's calendar is DERIVABLE and is therefore derived."""
    assert MA.easter(2024) == date(2024, 3, 31)
    assert MA.easter(2025) == date(2025, 4, 20)
    assert MA.easter(2026) == date(2026, 4, 5)
    for year, good_friday in ((2024, date(2024, 3, 29)), (2025, date(2025, 4, 18)),
                              (2026, date(2026, 4, 3))):
        movable = MA.catholic_movable(year)
        assert good_friday in movable, f"Good Friday {year} is {good_friday}"
        assert MA.easter(year) in movable, "Easter Sunday itself is a Timorese holiday"
        assert len(movable) == 4, "Ash Wednesday, Good Friday, Holy Saturday and Easter"
        tl = MA.national_holidays("tl", year)
        assert good_friday in tl and MA.easter(year) in tl
        # and no other jurisdiction gets the Catholic feasts
        assert good_friday not in MA.national_holidays("bt", year)


def test_nowruz_is_derived_from_the_march_equinox_and_never_typed() -> None:
    """AFGHANISTAN'S FISCAL YEAR STARTS HERE, so the boundary is computed, not typed: it moves
    within the day and across years, and a fixed 21 March is wrong most years."""
    assert MA.nowruz(2024) == date(2024, 3, 20)
    assert MA.nowruz(2025) == date(2025, 3, 20)
    assert MA.nowruz(2026) == date(2026, 3, 20)
    assert MA.nowruz(2023) == date(2023, 3, 21), "the equinox crosses Kabul midnight in 2023"
    for year in (2024, 2025, 2026):
        inst = MA.march_equinox(year)
        assert inst.year == year and inst.month == 3 and 19 <= inst.day <= 21
        assert inst.tzinfo is not None, "a naive equinox instant is a DTZ bug waiting to happen"
        assert MA.nowruz_is_certain(year), year
        assert MA.afghan_fiscal_year_start(year) == MA.nowruz(year)
        assert MA.nowruz(year) in MA.national_holidays("af", year)
    # 2027's equinox lands within an hour of Kabul midnight: the pack refuses to be sure
    assert MA.nowruz_is_certain(2027) is False
    assert MA.afghan_fiscal_year_end(2025) == MA.nowruz(2026) - timedelta(days=1)


def test_the_islamic_dates_are_typed_with_three_divergent_sighting_authorities() -> None:
    """A sighting cannot be derived, so it is typed with its authority -- and the three
    authorities have produced DIFFERENT DATES IN THE SAME YEAR, which is the measurement."""
    for year, rows in MA.ISLAMIC_FEASTS.items():
        for day, _name, status, where in rows:
            assert day.year == year
            assert status in MA.HOLIDAY_STATUSES
            assert set(where) <= set(FIVE) and where
    # 2025: Afghanistan kept Eid al-Fitr a day before Brunei and the Maldives
    af25 = MA.national_holidays("af", 2025)
    bn25 = MA.national_holidays("bn", 2025)
    assert date(2025, 3, 30) in af25 and date(2025, 3, 30) not in bn25
    assert date(2025, 3, 31) in bn25 and date(2025, 3, 31) not in af25
    # Brunei alone keeps Isra Mikraj and Nuzul Al-Quran
    assert date(2025, 1, 27) in bn25 and date(2025, 1, 27) not in af25
    assert date(2025, 3, 17) in bn25
    # 2026 is PROJECTED throughout, because no 1447/1448 sighting has happened
    assert all(st == "PROJECTED" for _d, _n, st, _w in MA.ISLAMIC_FEASTS[2026])
    assert all(st == "ANNOUNCED" for _d, _n, st, _w in MA.ISLAMIC_FEASTS[2024])
    assert set(MA.SIGHTING_AUTHORITY) == set(FIVE)
    assert "NOT OBSERVED" in MA.SIGHTING_AUTHORITY["bt"], "Bhutan keeps no Islamic date"
    assert "Saudi" in MA.SIGHTING_AUTHORITY["af"] and "titah" in MA.SIGHTING_AUTHORITY["bn"]


def test_the_bhutanese_lunisolar_rows_name_pangrizampa_and_are_never_invented() -> None:
    """No rule in the pack computes the Bhutanese calendar, so every row is typed with the
    astrological institute that does compute it."""
    assert "pangrizampa" in str(MA.HOLIDAYS_RULE["authority"]).lower()
    assert "pangrizampa" in str(MA.HOLIDAYS_RULE["bhutan_authority"]).lower()
    for year, rows in MA.TIBETAN_LUNISOLAR.items():
        assert rows, year
        for day, name, status in rows:
            assert day.year == year
            assert status == "PROJECTED_PANGRIZAMPA", f"{name}: a typed lunisolar row must say so"
        assert any("Losar" in n for _d, n, _s in rows), year
        assert any("Tshechu" in n for _d, n, _s in rows), year
    bt = MA.national_holidays("bt", 2025)
    assert date(2025, 9, 23) in bt, "Blessed Rainy Day is a fixed Bhutanese civil date"
    assert date(2025, 12, 17) in bt and date(2025, 2, 21) in bt


def test_the_2026_eid_and_nowruz_collision_is_computed(built: Any) -> None:
    """Eid drifts eleven days earlier each solar year and walks into the equinox once a
    generation. In 2026 both land on the same Kabul day, in the week the fiscal year turns."""
    assert MA.eid_nowruz_collision(2026) == 0
    assert MA.collision_years() == (2026,)
    assert abs(MA.eid_nowruz_collision(2024) or 0) > 3
    assert MA.eid_nowruz_collision(2030) is None, "an undeclared year answers None, not a guess"
    assert MA.closure_breadth(date(2026, 3, 20)) >= 3, "the collision shuts several at once"


def test_closure_breadth_counts_how_many_of_the_five_are_shut() -> None:
    """One of five is noise; four of five is a genuinely different regional day."""
    for year in (2024, 2025, 2026):
        regional = MA.regional_holidays(year)
        assert regional
        for day, where in regional.items():
            assert day.year == year
            assert set(where) <= set(FIVE) and where
            assert MA.closure_breadth(day) == len(where)
        market = MA.market_holidays(year)
        assert all(d.weekday() < 5 for d in market), "a weekend closure costs no session"
        assert set(market) <= set(regional)
    assert MA.closure_breadth(date(2025, 6, 11)) == 0, "an ordinary Wednesday shuts nobody"
    assert MA.is_market_holiday(date(2025, 1, 1)), "New Year's Day is a Wednesday in 2025"


# ------------------------------------------------------------------------------ the mechanisms
def test_the_rufiyaa_band_is_computed_and_pinned_on_its_weak_edge() -> None:
    """April 2011: a band of plus or minus twenty per cent around 12.85, and the rate went
    straight to 15.42 and stayed."""
    assert pytest.approx((10.28, 15.42), abs=1e-9) == MA.MVR_BAND
    weak = MA.rufiyaa_band(15.42)
    assert weak["band_position"] == pytest.approx(1.0, abs=1e-9)
    assert weak["pinned_on_weak_edge"] == 1.0
    strong = MA.rufiyaa_band(10.28)
    assert strong["band_position"] == pytest.approx(0.0, abs=1e-9)
    mid = MA.rufiyaa_band(12.85)
    assert mid["band_position"] == pytest.approx(0.5, abs=1e-9)
    assert mid["pinned_on_weak_edge"] == 0.0
    assert MA.parallel_premium(15.42, 17.0) == pytest.approx(10.2464, abs=1e-3)
    with pytest.raises(ValueError):
        MA.parallel_premium(0.0, 17.0)


def test_the_petroleum_fund_depletion_path_is_arithmetic_on_a_published_rule() -> None:
    """Inflow stopped in 2023; the statutory three-per-cent ESI continued. That is a computable
    path, not a forecast."""
    assert MA.TL_ESI_RATE == 0.03
    rows = MA.fund_depletion_path(18.0, annual_withdrawal=1.5, years=5)
    assert len(rows) == 5
    assert rows[0]["esi"] == pytest.approx(0.54, abs=1e-9)
    assert rows[0]["excess_over_esi"] == pytest.approx(0.96, abs=1e-9)
    assert rows[0]["closing"] < rows[0]["opening"], "withdrawing above the return depletes"
    # a withdrawal at exactly the real return never exhausts the fund
    assert MA.years_to_exhaustion(18.0, annual_withdrawal=0.54, real_return=0.03) is None
    # a withdrawal well above it does, on a dated horizon
    fast = MA.years_to_exhaustion(18.0, annual_withdrawal=2.0, real_return=0.03)
    slow = MA.years_to_exhaustion(18.0, annual_withdrawal=1.2, real_return=0.03)
    assert fast is not None and slow is not None and fast < slow


def test_the_monsoon_flips_bhutans_trade_sign_twice_a_year() -> None:
    """Run-of-river plants follow rainfall, so Bhutan EXPORTS in summer and IMPORTS in winter."""
    assert MA.hydro_season(7)["net_export_sign"] == 1
    assert MA.hydro_season(8)["state"] == "high_flow_export"
    assert MA.hydro_season(1)["net_export_sign"] == -1
    assert MA.hydro_season(12)["state"] == "low_flow_import"
    assert MA.hydro_season(4)["net_export_sign"] == 0
    year = MA.hydro_year(2025)
    assert len(year) == 12
    assert sum(1 for m in year if m["net_export_sign"] == 1) == 4
    assert sum(1 for m in year if m["net_export_sign"] == -1) == 3
    with pytest.raises(ValueError):
        MA.hydro_season(13)


def test_the_single_factor_thesis_is_data_and_names_five_different_factors() -> None:
    """The pack's organising claim, readable by a miner rather than only by a human."""
    smap = MA.single_factor_map()
    assert set(smap) == set(FIVE)
    assert len({row["factor"] for row in smap.values()}) == 5, "five DIFFERENT factors"
    for code, row in smap.items():
        assert row["series"] and row["leg"], code
    assert "MAR-L" in {d["id"] for d in MA.DOMAINS}, "the thesis must itself be testable"


def test_the_named_siblings_are_in_the_interactions() -> None:
    """The brief names three; the pack must not test these five in isolation."""
    withs = {r["with"] for r in MA.INTERACTIONS}
    assert {"sg", "ind", "caucasus_central_asia"} <= withs
    for row in MA.INTERACTIONS:
        assert row["targets"] and resolve(row["targets"])["absent"] == []
        assert len(str(row["mechanism"])) > 80, row["with"]
        assert len(str(row["control"])) > 40, row["with"]
        assert row["observable"], row["with"]
    sg = next(r for r in MA.INTERACTIONS if r["with"] == "sg")
    assert "par" in sg["mechanism"].lower() and "USDSGD" in sg["targets"]


def test_every_transmission_seed_names_tradable_targets_and_a_falsifier() -> None:
    for seed in MA.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"


# ------------------------------------------------------------------------------ the cells
def test_cells_are_minted_for_the_gauntlet_and_every_one_is_executable() -> None:
    """THE POINT OF A PACK IS CELLS REACHING THE ONE GAUNTLET."""
    rows = MA.cells()
    assert 60 <= len(rows) <= 200, f"{len(rows)} cells is outside the honest range"
    assert len(rows) == len(MA.CELLS)
    ids = {r["cell_id"] for r in rows}
    assert len(ids) == len(rows), "a duplicated cell_id is a double-counted trial"
    domain_ids = {d["id"] for d in MA.DOMAINS}
    execs = set(MA.EXECUTABLE_INSTRUMENTS)
    for row in rows:
        for field in ("cell_id", "domain", "symbol", "condition", "mechanism_family",
                      "horizon", "control", "why"):
            assert str(row[field]).strip(), f"{row['cell_id']}: {field} is empty"
        assert row["domain"] in domain_ids
        assert row["symbol"] in execs
    assert {r["domain"] for r in rows} == domain_ids, (
        "a domain that mints no cell is a domain the gauntlet never sees")
    covered = {j for r in rows for j in r["jurisdictions"]}
    assert covered == set(FIVE), f"cells reach only {covered}"


def test_datasets_are_deep_enough_and_every_row_can_be_fetched() -> None:
    """A dataset row with no concrete fetch route is a wish, not a catalogue entry."""
    assert len(MA.DATASETS) >= 18
    assets_seen: set[str] = set()
    for ds in MA.DATASETS:
        assert len(str(ds["how_to_fetch"])) > 40, f"{ds['name']}: fetch route is too vague"
        assert ds["assets"], f"{ds['name']}: names no asset"
        assert resolve(ds["assets"])["absent"] == [], f"{ds['name']}: absent asset"
        assets_seen |= set(ds["assets"])
    assert len(assets_seen) >= 10, "the catalogue reaches too few instruments"
    assert any(not ds["pit_feasible"] for ds in MA.DATASETS), (
        "every dataset claims point-in-time feasibility, which is implausible for a pack whose "
        "Afghan half is read from other countries' revised customs tables")
    assert sum(1 for ds in MA.DATASETS if ds["frequency"] == "daily") >= 1


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {f"custom:{name}" for name in MA.MINERS}
    assert all(callable(fn) for fn in got.values())


def test_custom_miner_rows_name_known_domains_and_match_the_miners_table() -> None:
    """The two registrations -- CUSTOM_MINERS and MINERS -- must be one set."""
    ids = {d["id"] for d in MA.DOMAINS}
    entries = set()
    for row in MA.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.maritime_asia.pack", row["entry"]
        assert callable(getattr(MA, func)), f"{row['entry']} does not resolve"
        entries.add(func)
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    assert entries == set(MA.MINERS)
    for did in MA.MINER_DOMAINS.values():
        assert set(did) <= ids


def test_mine_returns_a_report_and_emits_nothing_to_the_registry() -> None:
    """`mine(None)` is a pure-python pass: it reads the pack's own tables and records nothing."""
    report = MA.mine(None)
    assert report["code"] == "MARITIME_ASIA"
    assert report["emitted"] == len(MA.MINERS)
    assert report["cells_emitted"] == len(MA.cells())
    assert report["layers"] == 10
    assert report["datasets"] == len(MA.DATASETS)
    assert report["no_lawful_ground"] == len(MA.NO_LAWFUL_GROUND)
    assert tuple(report["jurisdictions"]) == FIVE
    assert report["unmeasured"], "a pack that can see everything is a pack that did not look"
    assert date.fromisoformat(str(report["at"]))
    assert set(report["interactions"]) == {r["with"] for r in MA.INTERACTIONS}
    for row in report["rows"]:
        assert row["n"] >= 1, f"{row['miner']} emitted nothing at all"


def test_mine_records_through_a_ctx_when_one_is_given() -> None:
    """When a department Ctx is handed in, every miner's result goes through `ctx.record`."""
    seen: list[Any] = []

    class Ctx:
        def record(self, row: Any) -> None:
            seen.append(row)

    report = MA.mine(Ctx())
    assert len(seen) == len(MA.MINERS) == report["emitted"]
    assert all(isinstance(r, dict) and r.get("rows") is not None for r in seen)
