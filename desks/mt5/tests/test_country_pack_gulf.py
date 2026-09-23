"""THE GULF PACK, VALIDATED -- four states, four mechanisms, one trial budget.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a way this particular pack
could be wrong while looking finished:

  * FOUR COUNTRIES CREDITED AS ONE. The parity fence reads `JURISDICTIONS` and nothing else, so
    a pack that answers for qa, kw, om and bh and forgets to say so leaves three of the fence's
    twenty-six unanswered with the work already on disk. The tuple is asserted against the
    desk's OWN roster in `libs/research/forests.py`, not against a list typed here.
  * ONE "GULF" MECHANISM WITH FOUR FLAGS ON IT. The whole claim of this pack is that Qatar's LNG
    schedule, Kuwait's undisclosed basket, Oman's non-OPEC quota and Bahrain's guaranteed peg are
    DIFFERENT machines. So every jurisdiction must own actors and domains of its own, and the
    Kuwaiti basket function must REFUSE to answer where the three hard pegs answer.
  * A EUROPEAN WEEKEND ON A GULF CALENDAR. These four trade Sunday to Thursday and rest Friday
    and Saturday. A holiday filter inherited from a sibling pack drops the wrong two days, and
    the assertions below pin weekday 4 and 5 as the closed pair.
  * A COMPUTED HIJRI DATE. Eid is an ANNOUNCEMENT by a named committee on the evening before, not
    an arithmetic result. The lunar table is typed, every row names the four sighting
    authorities, and 2026 must be PROJECTED throughout -- a 2026 sighting has not happened.
  * AN ENGLISH GLOSSARY OF AN ARABIC-SPEAKING REGION -- or an Arabic-only crawl that never
    reaches the prospectus. Both languages are official financial languages here and both are
    asserted, on the terminology and on the source classes' own queries.
  * A SYMBOL THE BOX CANNOT TRADE, or a single name on a docket. None of the four currencies is
    quoted; every one must stay a transmission target with a carrier that resolves.
  * A PACK THAT REACHES THE FRAMEWORK BENT. `CountryPack` coerces every row and a coercion note
    is a field it could not read; this pack must produce none, and `pack_depth` must score 1.0.
"""
from __future__ import annotations

import sys
from datetime import date
from itertools import pairwise
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
from countries.gulf import pack as GULF  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as FORESTS  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")
#: The pack's own declared depth. Twelve actors and ten domains is the package floor; a
#: four-jurisdiction pack written to that floor is four countries half-read.
DECLARED_DEPTH = {"actors": 20, "domains": 14, "edges": 12, "sources": 20, "datasets": 18,
                  "eras": 5, "terms": 120, "cells": 60, "interactions": 4}


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it, resolved the way the country lab resolves it."""
    got = CL.resolve_pack("gulf")
    assert got is not None, "no Gulf pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(GULF.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == "gulf"
    assert str(get(built, "region_command")) == "mea"
    assert str(get(built, "currency")) == "QAR"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    """A coercion note is a field `CountryPack` could not read. There must be none."""
    notes = list(getattr(built, "coercion_notes", ()) or [])
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on this pack: {fatal[:4]}"


def test_pack_reaches_parity_depth(built: Any) -> None:
    """The standing depth rule, measured by the framework and not claimed by the pack."""
    row = RP.pack_depth(built, "gulf").as_row()
    assert row["score"] == 1.0, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_depth_sits_above_the_packages_floor_because_four_states_share_one_pack() -> None:
    """Twelve actors is the floor for ONE country. Four jurisdictions owe four times the read."""
    assert len(GULF.ACTORS) >= DECLARED_DEPTH["actors"]
    assert len(GULF.DOMAINS) >= DECLARED_DEPTH["domains"]
    assert len(GULF.TRANSMISSION_EDGES_SEED) >= DECLARED_DEPTH["edges"]
    assert len(GULF.SOURCE_CLASSES) >= DECLARED_DEPTH["sources"]
    assert len(GULF.DATASETS) >= DECLARED_DEPTH["datasets"]
    assert len(GULF.POLICY_ERAS) >= DECLARED_DEPTH["eras"]
    assert GULF.term_count() >= DECLARED_DEPTH["terms"]


# ------------------------------------------------------------------- the four jurisdictions
def test_jurisdictions_are_declared_lowercase_and_on_the_desks_own_roster() -> None:
    """The parity fence counts THIS TUPLE. A multi-country pack that declares nothing is
    credited with one country, and three of the twenty-six stay unanswered."""
    assert GULF.JURISDICTIONS == ("qa", "kw", "om", "bh")
    assert all(cc == cc.lower() and len(cc) == 2 for cc in GULF.JURISDICTIONS)
    for cc in GULF.JURISDICTIONS:
        assert FORESTS.forest_of_country(cc) == "mena", (
            f"{cc} is not on the mena forest roster in libs/research/forests.py")
    # and the two siblings this pack complements are NOT claimed here
    assert not {"sa", "ae"} & set(GULF.JURISDICTIONS)


def test_every_jurisdiction_owns_actors_and_domains_of_its_own() -> None:
    """A Gulf pack whose actors are all 'the Gulf' has erased the four different machines."""
    for cc in GULF.JURISDICTIONS:
        actors = [a for a in GULF.ACTORS if a.get("jurisdiction") == cc]
        domains = [d for d in GULF.DOMAINS if d.get("jurisdiction") == cc]
        assert len(actors) >= 3, f"{cc} owns only {len(actors)} actor(s)"
        assert len(domains) >= 2, f"{cc} owns only {len(domains)} domain(s)"
    shared = [a for a in GULF.ACTORS if a.get("jurisdiction") == "shared"]
    assert shared, "no shared-Gulf actor at all, which cannot be right for a peg cluster"
    assert len(GULF.CURRENCIES) == 4
    assert {v["jurisdiction"] for v in GULF.CURRENCIES.values()} == set(GULF.JURISDICTIONS)


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    for row in GULF.ACTORS:
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
    for row in GULF.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert row["conditions"], f"domain {row['id']} names no conditioning state"
        assert row["id"] in GULF.DOMAIN_CELL_SPEC, f"{row['id']} mints no cells"


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(GULF.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert set(GULF.EXECUTABLE_INSTRUMENTS) <= set(registry)
    for dom in GULF.DOMAINS:
        assert resolve(dom["instruments"])["equities"] == [], f"{dom['id']} names an equity"
        assert set(dom["instruments"]) <= set(GULF.EXECUTABLE_INSTRUMENTS), (
            f"{dom['id']} names an instrument the pack never declared executable")


def test_every_transmission_seed_names_tradable_targets() -> None:
    """A seed that terminates in a symbol the box cannot quote can never compile a cell."""
    for seed in GULF.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"
        assert seed["target"] in seed["targets"], f"edge {seed['id']} target/targets disagree"


def test_all_four_currencies_are_named_absent_rather_than_quietly_dropped() -> None:
    """QAR, KWD, OMR and BHD are not quoted here and the pack says so with what carries them."""
    registry = universe_symbols()
    for ccy in ("QAR", "KWD", "OMR", "BHD"):
        assert not {ccy, f"USD{ccy}", f"{ccy}USD"} & set(registry), f"{ccy} is quoted after all"
    named = " ".join(str(t["name"]) for t in GULF.TRANSMISSION_TARGETS)
    for must in ("QAR", "KWD", "OMR", "BHD", "Oman Crude", "QE Index"):
        assert must in named, f"the Gulf pack does not name {must!r} as an absent instrument"
    for row in GULF.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == [], f"{row['name']} has an unquotable carrier"
        assert row["why"] and row["peg"]


# ------------------------------------------------------------------------------ the languages
def test_terminology_carries_arabic_and_the_gulfs_english_working_vocabulary() -> None:
    """Both are official financial languages here: an Arabic-only crawl misses the prospectus
    and an English-only crawl misses the gazette, the sighting and the retail ground."""
    assert len(GULF.arabic_terms()) >= 90, f"only {len(GULF.arabic_terms())} Arabic terms"
    assert len(GULF.english_terms()) == len(GULF.ENGLISH_MARKERS), (
        f"missing English working vocabulary: "
        f"{sorted(set(GULF.ENGLISH_MARKERS) - set(GULF.english_terms()))}")
    flat = {t for group in GULF.TERMINOLOGY.values() for t in group}
    for must in ("حقل الشمال", "الدينار الكويتي", "سلة العملات", "خام عمان", "مضيق هرمز",
                 "صندوق الأجيال القادمة", "الدينار البحريني", "أوبك بلس", "الريال القطري"):
        assert must in flat, f"the Gulf pack does not carry {must!r}"
    for must in ("North Field expansion", "undisclosed basket", "DME Oman", "BHIBOR",
                 "Strait of Hormuz", "Future Generations Fund"):
        assert must in flat, f"the Gulf pack does not carry {must!r}"
    assert GULF.has_arabic("مصرف قطر المركزي") and not GULF.has_arabic("Qatar Central Bank")
    assert len(GULF.TERMINOLOGY) == len(GULF.DOMAINS)
    assert set(GULF.TERMINOLOGY) == {d["id"] for d in GULF.DOMAINS}


def test_every_source_carries_a_native_query_and_three_independent_labels() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate; and a
    query typed in English on an Arabic ground finds the English corner and reports it as the
    ground."""
    for row in GULF.SOURCE_CLASSES:
        assert row["access_label"] in GULF.ACCESS_LABELS
        assert row["credibility"] in GULF.CREDIBILITY_LABELS
        assert row["predictive_state"] in GULF.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no query at all"
        assert row["roots"], f"{row['id']} has no crawlable root"
        assert row["notes"], f"{row['id']} says nothing about why it is here"
    terms = GULF.layer_terms()
    arabic_layers = [layer for layer, qs in terms.items() if any(GULF.has_arabic(q) for q in qs)]
    assert len(arabic_layers) >= 9, f"only {arabic_layers} carry an Arabic query"
    native = sum(1 for row in GULF.SOURCE_CLASSES if row["machine_use_allowed"]
                 for q in row["queries"] if GULF.has_arabic(q))
    assert native >= 90, f"only {native} Arabic-script queries across crawlable sources"


def test_query_territories_cover_every_layer_in_the_native_script() -> None:
    """The deep-forest miner reads THIS: at least three phrases per layer, Arabic present."""
    assert set(GULF.QUERY_TERRITORIES) == set(GULF.SOURCE_LAYERS)
    for layer, phrases in GULF.QUERY_TERRITORIES.items():
        assert len(phrases) >= 3, f"{layer} has only {len(phrases)} query phrases"
        assert any(GULF.has_arabic(p) for p in phrases), f"{layer} has no Arabic phrase"


def test_all_ten_source_layers_are_populated_and_the_refusals_are_named() -> None:
    """The depth rule: ten layers, none blank -- and where a SERIES does not lawfully exist,
    the pack names it rather than quietly working around it."""
    counts = GULF.layer_counts()
    assert set(counts) == set(GULF.SOURCE_LAYERS)
    assert [layer for layer, n in counts.items() if not n] == []
    coverage = GULF.source_layer_coverage()
    assert coverage["n_layers_covered"] == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible for a region "
        "whose sour-crude and LNG assessments live behind price-reporting-agency paywalls")
    assert coverage["low_weight_kept"], "no fringe ground is kept at all, so it was dropped"
    assert len(GULF.NO_LAWFUL_GROUND) >= 5
    blob = " ".join(row["why"] for row in GULF.NO_LAWFUL_GROUND)
    assert "47" in blob, "the Kuwaiti disclosure law is not named in NO_LAWFUL_GROUND"
    for row in GULF.NO_LAWFUL_GROUND:
        assert row["what"] and row["why"] and row["consequence"]


# ------------------------------------------------------------------------------ the calendars
def test_the_gulf_weekend_is_friday_and_saturday_not_saturday_and_sunday() -> None:
    """The single most commonly inverted fact about these four markets."""
    assert GULF.WEEKEND_WEEKDAYS == (4, 5)
    assert GULF.is_gcc_session_day(date(2025, 3, 2))       # a Sunday: OPEN
    assert GULF.is_gcc_session_day(date(2025, 3, 6))       # a Thursday: OPEN
    assert not GULF.is_gcc_session_day(date(2025, 3, 7))   # a Friday: closed
    assert not GULF.is_gcc_session_day(date(2025, 3, 8))   # a Saturday: closed
    days = GULF.gcc_session_days(date(2025, 3, 1), date(2025, 3, 31))
    assert days and all(d.weekday() not in (4, 5) for d in days)
    assert date(2025, 3, 30) not in days, "Eid al-Fitr day 1 is not a session"
    row = GULF._holiday_rule_row()
    assert row["weekly_closed"] == (4, 5)


def test_the_national_days_are_derived_and_the_sports_day_is_a_weekday_rule() -> None:
    """A fixed solar date is computed, never typed into a year table -- and Qatar's second
    national holiday is the SECOND TUESDAY OF FEBRUARY, which a rule can produce."""
    assert GULF.qatar_sports_day(2024) == date(2024, 2, 13)
    assert GULF.qatar_sports_day(2025) == date(2025, 2, 11)
    assert GULF.qatar_sports_day(2026) == date(2026, 2, 10)
    assert all(GULF.qatar_sports_day(y).weekday() == 1 for y in (2024, 2025, 2026))
    for year in (2024, 2025, 2026):
        assert date(year, 12, 18) in GULF.national_day("qa", year)    # Qatar National Day
        assert date(year, 2, 25) in GULF.national_day("kw", year)     # Kuwait National Day
        assert date(year, 2, 26) in GULF.national_day("kw", year)     # Liberation Day
        assert date(year, 11, 18) in GULF.national_day("om", year)    # Oman National Day
        assert date(year, 12, 16) in GULF.national_day("bh", year)    # Bahrain National Day
        assert date(year, 12, 17) in GULF.national_day("bh", year)
    # 1 January is NOT a statutory Qatari holiday; it is a bank closure, and the pack knows it
    assert date(2025, 1, 1) not in GULF.national_day("qa", 2025)
    assert date(2025, 1, 1) in GULF.national_day("kw", 2025)


def test_the_holiday_table_resolves_for_all_three_years_and_stays_inside_them() -> None:
    for year in (2024, 2025, 2026):
        table = holiday_table(GULF.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
    assert "2026-12-18" in holiday_table(GULF.HOLIDAYS_RULE, 2026)
    assert "2026-02-10" in holiday_table(GULF.HOLIDAYS_RULE, 2026)     # derived Sports Day


def test_the_sighted_feasts_are_typed_with_their_authority_and_2026_is_projected() -> None:
    """A Hijri date is an ANNOUNCEMENT by a named committee, not an arithmetic result. The rule
    text must say so, every row must name the four authorities, and no 2026 sighting can
    already be announced."""
    rule = str(GULF.HOLIDAYS_RULE["rule"]).lower()
    assert "sighting" in rule and "cannot be computed" in rule
    assert set(GULF.SIGHTING_AUTHORITIES) == set(GULF.JURISDICTIONS)
    assert all(GULF.has_arabic(v) for v in GULF.SIGHTING_AUTHORITIES.values())
    for year, rows in GULF.LUNAR_HOLIDAYS.items():
        assert rows, f"no lunar rows for {year}"
        for day, name, ccs, status in rows:
            assert day.year == year
            assert name and ccs and set(ccs) <= set(GULF.JURISDICTIONS)
            for cc in GULF.JURISDICTIONS:
                assert f"{cc}=" in status, f"{year} {name}: status does not name {cc}"
            if year == 2026:
                assert status.startswith("PROJECTED"), (
                    f"{name} 2026 cannot already be announced: no sighting has happened")
            else:
                assert status.startswith("ANNOUNCED")
    # the dates the four states actually observed, which differ from Morocco's by a day
    assert date(2024, 4, 10) in {d for d, *_ in GULF.LUNAR_HOLIDAYS[2024]}
    assert date(2025, 3, 30) in {d for d, *_ in GULF.LUNAR_HOLIDAYS[2025]}
    # Ashura closes BAHRAIN ONLY, which a pooled GCC holiday dummy gets wrong three times in four
    ashura = [row for row in GULF.LUNAR_HOLIDAYS[2025] if "عاشوراء" in row[1]]
    assert ashura and all(row[2] == ("bh",) for row in ashura)
    assert date(2025, 7, 4) in GULF.holidays_for("bh", 2025)
    assert date(2025, 7, 4) not in GULF.holidays_for("qa", 2025)


def test_the_ramadan_window_is_a_session_change_and_not_only_a_closure() -> None:
    """The closure is Eid; the liquidity change is the whole month, and it drifts eleven days a
    year, which is the identification GULF-M is built on."""
    assert GULF.in_ramadan(date(2025, 3, 10))
    assert not GULF.in_ramadan(date(2025, 5, 10))
    assert GULF.ramadan_window(2026) is not None
    assert GULF.RAMADAN_WINDOWS[2026][2] == "PROJECTED"
    starts = [GULF.RAMADAN_WINDOWS[y][0] for y in (2024, 2025, 2026)]
    for lo, hi in pairwise(starts):
        drift = (lo.replace(year=lo.year + 1) - hi).days
        assert 9 <= drift <= 13, f"the Hijri drift should be about eleven days, got {drift}"


# ---------------------------------------------------------------- the pack's own mechanisms
def test_north_field_capacity_is_a_dated_published_supply_curve() -> None:
    """MECHANISM ONE: Qatar's announced LNG nameplate by year. The whole reason GULF-A exists."""
    assert GULF.north_field_capacity(2024) == 77.0
    assert GULF.north_field_capacity(2025) == 77.0
    assert GULF.north_field_capacity(2026) == 110.0
    assert GULF.north_field_capacity(2027) == 126.0
    assert GULF.north_field_capacity(2029) == 126.0
    assert GULF.north_field_capacity(2030) == 142.0
    assert GULF.north_field_capacity(2035) == 142.0
    assert GULF.north_field_capacity(1999) == 0.0, "no capacity is claimed before the schedule"
    assert all(st in ("HISTORICAL", "ANNOUNCED_SCHEDULE")
               for *_rest, st in GULF.NORTH_FIELD_SCHEDULE), (
        "a schedule step may never be labelled as delivered until it is")


def test_peg_band_state_answers_for_three_pegs_and_refuses_for_the_basket() -> None:
    """MECHANISM TWO: where a local rate sits in its declared corridor -- and the ONE currency
    that has no corridor to sit in, because its basket is a state secret."""
    assert GULF.peg_band_state("QAR", 3.6400)["state"] == "INSIDE"
    assert GULF.peg_band_state("QAR", 3.6385)["state"] == "AT_STRONG_EDGE"
    assert GULF.peg_band_state("QAR", 3.6415)["state"] == "AT_WEAK_EDGE"
    assert GULF.peg_band_state("QAR", 3.7000)["state"] == "OUTSIDE"
    # Bahrain's declared parity SITS AT THE STRONG EDGE of the CBB's own dealing range, which
    # is the asymmetry that makes it the weakest peg of the four: the dinar is only ever quoted
    # at par or weaker, never stronger.
    assert GULF.peg_band_state("BHD", 0.3760)["state"] == "AT_STRONG_EDGE"
    assert GULF.peg_band_state("BHD", 0.3770)["state"] == "AT_WEAK_EDGE"
    assert GULF.peg_band_state("BHD", 0.3750)["state"] == "OUTSIDE"
    assert GULF.peg_band_state("OMR", 0.384500)["state"] == "INSIDE"
    assert GULF.peg_band_state("OMR", 0.385000)["state"] == "AT_WEAK_EDGE"
    kwd = GULF.peg_band_state("KWD", 0.3070)
    assert kwd["state"] == "UNMEASURED" and "UNDISCLOSED" in kwd["why"]
    assert GULF.peg_band_state("MAD", 10.0)["state"] == "UNMEASURED"
    assert abs(GULF.peg_band_state("QAR", 3.6400)["distance_bp"]) < 1e-6


def test_the_kuwaiti_basket_beta_recovers_a_known_weight_and_refuses_a_short_sample() -> None:
    """MECHANISM THREE: the only Gulf FX question that is a question. Build a fixing series in
    which the dinar carries EXACTLY 30% of the euro's move and check the estimator finds it."""
    weight = 0.30
    eur = [1.1000, 1.1055, 1.0990, 1.1120, 1.1075, 1.1200]
    kwd = [0.3070 * (e / eur[0]) ** weight for e in eur]
    got = GULF.kwd_basket_beta(list(zip(kwd, eur, strict=True)))
    assert got["measured"] is True and got["n"] == len(eur) - 1
    assert abs(float(got["beta_eurusd"]) - weight) < 1e-6, got
    assert abs(float(got["implied_usd_weight"]) - (1.0 - weight)) < 1e-6
    short = GULF.kwd_basket_beta([(0.307, 1.10), (0.3071, 1.101)])
    assert short["measured"] is False and "UNMEASURED" in short["why"]
    flat = GULF.kwd_basket_beta([(0.307, 1.10)] * 6)
    assert flat["measured"] is False, "a regressor with no variance identifies no weight"


def test_hormuz_bypass_is_the_control_that_makes_the_chokepoint_testable() -> None:
    """MECHANISM FOUR: Oman's ports are the only major Gulf loading points outside the strait,
    and Mina al-Fahal is the WITHIN-COUNTRY control that holds the country constant."""
    assert GULF.hormuz_bypass_share("Duqm")["inside_hormuz"] is False
    assert GULF.hormuz_bypass_share("Ras Markaz")["inside_hormuz"] is False
    assert GULF.hormuz_bypass_share("Sohar")["inside_hormuz"] is False
    assert GULF.hormuz_bypass_share("Ras Laffan")["inside_hormuz"] is True
    assert GULF.hormuz_bypass_share("Mina al-Ahmadi")["inside_hormuz"] is True
    assert GULF.hormuz_bypass_share("Mina al-Fahal")["inside_hormuz"] is True
    unknown = GULF.hormuz_bypass_share("Some Unlisted Terminal")
    assert unknown["known"] is False and unknown["inside_hormuz"] is True, (
        "an unknown port must NOT be assumed to bypass the strait")


# ------------------------------------------------------------------------------ the cells
def test_the_pack_mints_cells_the_gauntlet_can_actually_compile() -> None:
    """The point of a pack is cells reaching the one gauntlet, and every one of them must name a
    real symbol, a real condition from its own domain, and a control it cannot travel without."""
    minted = GULF.cells()
    assert len(minted) >= DECLARED_DEPTH["cells"], f"only {len(minted)} cells"
    assert len(minted) == len({c["cell_id"] for c in minted}), "duplicate cell ids"
    domain_conditions = {d["id"]: set(d["conditions"]) for d in GULF.DOMAINS}
    registry = universe_symbols()
    for cell in minted:
        for field in ("cell_id", "domain", "symbol", "condition", "mechanism_family",
                      "horizon", "control", "why"):
            assert cell[field], f"{cell.get('cell_id')} has an empty {field}"
        assert cell["symbol"] in registry, f"{cell['cell_id']} names an unquotable symbol"
        assert cell["symbol"] in GULF.EXECUTABLE_INSTRUMENTS
        assert cell["condition"] in domain_conditions[cell["domain"]], (
            f"{cell['cell_id']} invents a condition its own domain never named")
    covered = {c["domain"] for c in minted}
    assert covered == {d["id"] for d in GULF.DOMAINS}, "a domain mints no cells at all"
    by_jur = {c["jurisdiction"] for c in minted}
    assert set(GULF.JURISDICTIONS) <= by_jur, "a jurisdiction mints no cells of its own"


def test_the_interactions_name_real_sibling_packs_and_tradable_targets() -> None:
    """This is how the desk stops testing each country in isolation. `sa` and `ae` must both be
    here: they are the two packs this one is the complement of."""
    assert len(GULF.INTERACTIONS) >= DECLARED_DEPTH["interactions"]
    withs = {row["with"] for row in GULF.INTERACTIONS}
    assert {"sa", "ae"} <= withs, "the two sibling Gulf packs are not named as interactions"
    on_disk = {p.name for p in (_DESK / "research" / "countries").iterdir() if p.is_dir()}
    for row in GULF.INTERACTIONS:
        assert row["with"] in on_disk, f"interaction with {row['with']!r} names no pack on disk"
        assert row["mechanism"] and row["observable"] and row["control"]
        assert resolve(row["targets"])["absent"] == [], f"{row['with']} -> unquotable target"


def test_the_datasets_are_fetchable_and_spread_across_the_layers() -> None:
    """A dataset whose `how_to_fetch` is a wish is a collector task nobody can start."""
    assert len(GULF.DATASETS) >= DECLARED_DEPTH["datasets"]
    for row in GULF.DATASETS:
        assert len(str(row["how_to_fetch"])) > 40, f"{row['name']}: how_to_fetch is too thin"
        assert float(row["publication_lag_days"]) >= 0.0
        assert resolve(row["assets"])["absent"] == [], f"{row['name']} names an absent asset"
        assert row["mechanism_families"]
    assert sum(1 for r in GULF.DATASETS if r["pit_feasible"]) >= len(GULF.DATASETS) - 3


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {f"custom:{name}" for name in GULF.MINERS}
    assert all(callable(fn) for fn in got.values())
    ids = {d["id"] for d in GULF.DOMAINS}
    for row in GULF.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.gulf.pack", row["entry"]
        assert func in GULF.MINERS, f"{row['entry']} is not in the MINERS registry"
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    for did in GULF.MINER_DOMAINS.values():
        assert set(did) <= ids


def test_mine_returns_a_report_and_records_nothing_without_a_context() -> None:
    """The department entry: pure python, no network, an artifact on every call, and a DRY RUN
    when nothing was handed to it to emit through (UNWIRED IS A DEFECT, III.16)."""
    report = GULF.mine(None)
    assert report["code"] == "gulf"
    assert tuple(report["jurisdictions"]) == GULF.JURISDICTIONS
    assert report["emitted"] == 0, "mine(None) must record nothing"
    assert report["dry_run"] is True
    assert report["cells_emitted"] == len(GULF.cells())
    assert report["rows"] and len(report["rows"]) == len(GULF.MINERS)
    assert report["unmeasured"], "a pack that reports nothing UNMEASURED is not being honest"
    assert sum(report["cells_by_domain"].values()) == report["cells_emitted"]
    assert report["at"].endswith("+00:00"), "the stamp must be timezone-aware UTC"

    class _Ctx:
        def __init__(self) -> None:
            self.lines: list[tuple[str, str]] = []

        def note(self, kind: str, text: str) -> None:
            self.lines.append((kind, text))

    ctx = _Ctx()
    wet = GULF.mine(ctx)
    assert wet["dry_run"] is False
    assert wet["emitted"] == len(ctx.lines) > 0
    assert {kind for kind, _ in ctx.lines} >= {"gulf_north_field", "gulf_peg", "gulf_hormuz"}


def test_the_policy_eras_are_dated_and_name_what_pooling_across_them_destroys() -> None:
    """The blockade is the case this pack exists to keep out of a pooled sample."""
    assert len(GULF.POLICY_ERAS) >= DECLARED_DEPTH["eras"]
    for row in GULF.POLICY_ERAS:
        lo = date.fromisoformat(str(row["start"]))
        hi = date.fromisoformat(str(row["end"]))
        assert hi >= lo, f"{row['name']}: reversed dates"
        assert row["why_it_matters"] and row["markers"]
        assert row["status"] in ("SETTLED", "OPEN")
    blockade = [r for r in GULF.POLICY_ERAS if "blockade" in str(r["name"]).lower()]
    assert blockade, "the 2017-2021 blockade is not a declared era"
    assert blockade[0]["start"] == "2017-06-05" and blockade[0]["end"] == "2021-01-05"
    assert any("2020-03-06" in " ".join(r["markers"]) for r in GULF.POLICY_ERAS), (
        "the DoC breakdown of 2020-03-06 is the largest dated oil event in the sample")


def test_cot_and_the_kuwaiti_fund_are_declared_absent_rather_than_silently_missing() -> None:
    """Two absences a study can trip over, both named: no COT exists for any of the four
    currencies, and the KIA may not disclose anything at all."""
    unavailable = [r for r in GULF.POSITIONING_SOURCES if not r["available"]]
    assert len(unavailable) >= 2
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in unavailable)
    assert any("47" in str(r["why"]) for r in unavailable), (
        "the Kuwaiti disclosure law is not named in the positioning sources")
    assert GULF.COT_CURRENCY == ""
    for row in GULF.POSITIONING_SOURCES:
        assert row["why"] and row["pit_warning"]
