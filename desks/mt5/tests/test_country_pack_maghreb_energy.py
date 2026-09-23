"""THE MAGHREB ENERGY PACK, VALIDATED -- four states, one European gas balance, one trial budget.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one is a way this pack could be wrong while
looking finished:

  * FOUR COUNTRIES CREDITED AS ONE. The parity fence reads `JURISDICTIONS` and nothing else.
  * ONE "MAGHREB" MECHANISM WITH FOUR FLAGS ON IT. Algeria's published pipeline flow, Libya's
    per-terminal force majeure, Tunisia's transit royalty and olive campaign, and Mauritania's
    ore and shared gas field are DIFFERENT machines, so every jurisdiction must own actors and
    domains of its own.
  * ONE WEEKEND FOR FOUR COUNTRIES. Tunisia rests Saturday-Sunday and the other three rest
    Friday-Saturday, so Sunday is a working day in three of the four; the split is pinned here.
  * A COMPUTED HIJRI DATE. Eid is an ANNOUNCEMENT by a named authority, not arithmetic; the
    lunar table is typed, every row names all four authorities, and 2026 must be PROJECTED.
  * HENRY HUB AS A PROXY FOR A EUROPEAN PRICE. The two benchmarks decoupled by an order of
    magnitude in 2022; the pack must register the US benchmark as a CONTROL and say so.
  * AN ENGLISH GLOSSARY OF AN ARABIC- AND FRENCH-SPEAKING REGION, or a Tamazight-free Algeria.
  * A SYMBOL THE BOX CANNOT TRADE, or a single name on a docket.
  * A PACK THAT REACHES THE FRAMEWORK BENT: `CountryPack` must coerce nothing.
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
from countries.maghreb_energy import pack as MGB  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as FORESTS  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")
#: The pack's own declared depth. Twelve actors and ten domains is the package floor; a
#: four-jurisdiction pack written to that floor is four countries half-read.
DECLARED_DEPTH = {"actors": 18, "domains": 13, "edges": 11, "sources": 20, "datasets": 17,
                  "eras": 5, "terms": 120, "cells": 60, "interactions": 4}


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it, resolved the way the country lab resolves it."""
    got = CL.resolve_pack("maghreb_energy")
    assert got is not None, "no Maghreb energy pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(MGB.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == "maghreb_energy"
    assert str(get(built, "region_command")) == "mea"
    assert str(get(built, "currency")) == "DZD"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    """A coercion note is a field `CountryPack` could not read. There must be none."""
    notes = list(getattr(built, "coercion_notes", ()) or [])
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on this pack: {fatal[:4]}"


def test_pack_reaches_parity_depth(built: Any) -> None:
    """The standing depth rule, measured by the framework and not claimed by the pack."""
    row = RP.pack_depth(built, "maghreb_energy").as_row()
    assert row["score"] == 1.0, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_depth_sits_above_the_packages_floor_because_four_states_share_one_pack() -> None:
    """Twelve actors is the floor for ONE country. Four jurisdictions owe four times the read."""
    assert len(MGB.ACTORS) >= DECLARED_DEPTH["actors"]
    assert len(MGB.DOMAINS) >= DECLARED_DEPTH["domains"]
    assert len(MGB.TRANSMISSION_EDGES_SEED) >= DECLARED_DEPTH["edges"]
    assert len(MGB.SOURCE_CLASSES) >= DECLARED_DEPTH["sources"]
    assert len(MGB.DATASETS) >= DECLARED_DEPTH["datasets"]
    assert len(MGB.POLICY_ERAS) >= DECLARED_DEPTH["eras"]
    assert MGB.term_count() >= DECLARED_DEPTH["terms"]


# ------------------------------------------------------------------- the four jurisdictions
def test_jurisdictions_are_declared_lowercase_and_on_the_desks_own_roster() -> None:
    """The parity fence counts THIS TUPLE. A multi-country pack that declares nothing is
    credited with one country, and three of its gaps stay unanswered."""
    assert MGB.JURISDICTIONS == ("dz", "ly", "tn", "mr")
    assert all(cc == cc.lower() and len(cc) == 2 for cc in MGB.JURISDICTIONS)
    # A country belongs to EXACTLY ONE forest. The mena roster row that adds DZ/LY/TN/MR and the
    # `maghreb_energy` pack name is a one-line anchored edit owned by the coordinator (several
    # builders write that file at once), so the invariant pinned here is the one this pack can
    # violate on its own: none of the four may be claimed by a DIFFERENT forest. An empty answer
    # means the registration is still pending; anything else is a roster collision.
    for cc in MGB.JURISDICTIONS:
        forest = FORESTS.forest_of_country(cc)
        assert forest in ("mena", ""), (
            f"{cc} is on the {forest!r} forest roster, not mena -- a roster collision")
    # the siblings this pack complements are NOT claimed here
    assert not {"ma", "eg", "sa", "ae", "il", "tr"} & set(MGB.JURISDICTIONS)


def test_every_jurisdiction_owns_actors_and_domains_of_its_own() -> None:
    """A Maghreb pack whose actors are all 'the Maghreb' has erased four different machines."""
    for cc in MGB.JURISDICTIONS:
        actors = [a for a in MGB.ACTORS if a.get("jurisdiction") == cc]
        domains = [d for d in MGB.DOMAINS if d.get("jurisdiction") == cc]
        assert len(actors) >= 4, f"{cc} owns only {len(actors)} actor(s)"
        assert len(domains) >= 2, f"{cc} owns only {len(domains)} domain(s)"
    shared = [a for a in MGB.ACTORS if a.get("jurisdiction") == "shared"]
    assert shared, "no shared actor at all, which cannot be right for one gas balance"
    assert len(MGB.CURRENCIES) == 4
    assert {v["jurisdiction"] for v in MGB.CURRENCIES.values()} == set(MGB.JURISDICTIONS)


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    for row in MGB.ACTORS:
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
    for row in MGB.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert row["conditions"], f"domain {row['id']} names no conditioning state"
        assert row["id"] in MGB.DOMAIN_CELL_SPEC, f"{row['id']} mints no cells"


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(MGB.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    for dom in MGB.DOMAINS:
        assert resolve(dom["instruments"])["equities"] == [], f"{dom['id']} names an equity"
        assert set(dom["instruments"]) <= set(MGB.EXECUTABLE_INSTRUMENTS), (
            f"{dom['id']} names an instrument the pack never declared executable")


def test_every_transmission_seed_names_tradable_targets() -> None:
    """A seed that terminates in a symbol the box cannot quote can never compile a cell."""
    for seed in MGB.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"
        assert seed["target"] in seed["targets"], f"edge {seed['id']} target/targets disagree"


def test_the_four_currencies_and_the_gas_hubs_are_named_absent_with_carriers() -> None:
    """DZD, LYD, TND, MRU, TTF, PSV and PVB are not quoted, and the pack says so with what
    carries each of them. HENRY HUB IS REGISTERED AS A CONTROL AND NOT A PROXY."""
    registry = universe_symbols()
    for ccy in ("DZD", "LYD", "TND", "MRU"):
        assert not {ccy, f"USD{ccy}", f"{ccy}USD", f"EUR{ccy}"} & set(registry), (
            f"{ccy} is quoted after all")
    named = " ".join(str(t["name"]) for t in MGB.TRANSMISSION_TARGETS)
    for must in ("DZD official", "DZD parallel", "LYD official", "TND", "MRU", "TTF", "PSV",
                 "PVB", "Henry Hub", "Olive oil", "Iron ore"):
        assert must in named, f"the pack does not name {must!r} as an absent instrument"
    for row in MGB.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == [], f"{row['name']} has an unquotable carrier"
        assert row["why"] and row["regime"]
    hub = [t for t in MGB.TRANSMISSION_TARGETS if "Henry Hub" in str(t["name"])]
    assert hub and "CONTROL" in str(hub[0]["name"]).upper()
    blob = " ".join(str(t["why"]) for t in MGB.TRANSMISSION_TARGETS).upper()
    assert "NEVER THE PROXY" in blob or "NOT A PROXY" in blob, (
        "the pack does not say on the record that Henry Hub is a control and not a proxy")


# ------------------------------------------------------------------------------ the languages
def test_terminology_carries_arabic_french_and_tifinagh() -> None:
    """Three writing systems: an Arabic-only crawl misses the central-bank bulletin, a
    French-only crawl misses the gazette and the street, and a pack with no Tifinagh in it has
    decided that an official language of Algeria is not a ground."""
    assert len(MGB.arabic_terms()) >= 90, f"only {len(MGB.arabic_terms())} Arabic terms"
    assert MGB.tifinagh_terms(), "no Tamazight term at all in a pack that includes Algeria"
    assert len(MGB.french_terms()) == len(MGB.FRENCH_MARKERS), (
        f"missing French working vocabulary: "
        f"{sorted(set(MGB.FRENCH_MARKERS) - set(MGB.french_terms()))}")
    flat = {t for group in MGB.TERMINOLOGY.values() for t in group}
    for must in ("سوناطراك", "المؤسسة الوطنية للنفط", "القوة القاهرة", "السوق الموازية",
                 "زيت الزيتون", "شركة فسفاط قفصة", "الأوقية", "حقل السلحفاة الكبرى أحميم"):
        assert must in flat, f"the pack does not carry {must!r}"
    for must in ("gazoduc Maghreb-Europe", "Medgaz", "Square Port Said", "campagne oleicole",
                 "minerai de fer", "hydrogene vert"):
        assert must in flat, f"the pack does not carry {must!r}"
    assert MGB.has_arabic("بنك الجزائر") and not MGB.has_arabic("Banque d'Algerie")
    assert MGB.has_tifinagh("ⵜⴰⵎⴰⵣⵉⵖⵜ") and not MGB.has_tifinagh("Tamazight")
    assert len(MGB.TERMINOLOGY) == len(MGB.DOMAINS)
    assert set(MGB.TERMINOLOGY) == {d["id"] for d in MGB.DOMAINS}


def test_every_source_carries_a_native_query_and_three_independent_labels() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate; and a
    query typed in English on an Arabic and French ground reports a corner as the ground."""
    for row in MGB.SOURCE_CLASSES:
        assert row["access_label"] in MGB.ACCESS_LABELS
        assert row["credibility"] in MGB.CREDIBILITY_LABELS
        assert row["predictive_state"] in MGB.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no query at all"
        assert row["roots"], f"{row['id']} has no crawlable root"
        assert row["notes"], f"{row['id']} says nothing about why it is here"
    terms = MGB.layer_terms()
    arabic_layers = [layer for layer, qs in terms.items() if any(MGB.has_arabic(q) for q in qs)]
    assert len(arabic_layers) >= 8, f"only {arabic_layers} carry an Arabic query"
    native = sum(1 for row in MGB.SOURCE_CLASSES if row["machine_use_allowed"]
                 for q in row["queries"] if MGB.has_arabic(q))
    assert native >= 80, f"only {native} Arabic-script queries across crawlable sources"


def test_query_territories_cover_every_layer_in_the_native_script() -> None:
    """The deep-forest miner reads THIS: at least three phrases per layer, Arabic present."""
    assert set(MGB.QUERY_TERRITORIES) == set(MGB.SOURCE_LAYERS)
    for layer, phrases in MGB.QUERY_TERRITORIES.items():
        assert len(phrases) >= 3, f"{layer} has only {len(phrases)} query phrases"
        assert any(MGB.has_arabic(p) for p in phrases), f"{layer} has no Arabic phrase"


def test_all_ten_layers_are_populated_and_every_refusal_is_named() -> None:
    """The depth rule: ten layers, none blank -- AND, because an aggregate that is full can hide
    a country that contributes nothing, the per-jurisdiction absences with their substitutes."""
    counts = MGB.layer_counts()
    assert set(counts) == set(MGB.SOURCE_LAYERS)
    assert [layer for layer, n in counts.items() if not n] == []
    coverage = MGB.source_layer_coverage()
    assert coverage["n_layers_covered"] == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible for a region whose "
        "crude differentials, gas hubs, fertiliser and iron-ore prices all live behind paywalls")
    assert coverage["low_weight_kept"], "no fringe ground is kept at all, so it was dropped"
    # the per-jurisdiction refusals: Libya and Mauritania owe several, each with a substitute
    per = MGB.jurisdiction_layer_coverage()
    assert set(per) == set(MGB.JURISDICTIONS)
    assert len(per["ly"]) >= 3, "Libya cannot plausibly populate every layer"
    assert len(per["mr"]) >= 2, "Mauritania cannot plausibly populate every layer"
    for row in MGB.JURISDICTION_ABSENCES:
        assert row["jurisdiction"] in MGB.JURISDICTIONS
        assert row["layer"] in MGB.SOURCE_LAYERS
        assert "DECLARED ABSENT" in str(row["notes"])
        assert len(str(row["substitute"])) > 30, f"{row['id']} names no lawful substitute"
    assert len(MGB.NO_LAWFUL_GROUND) >= 7
    blob = " ".join(row["why"] for row in MGB.NO_LAWFUL_GROUND)
    assert "2011" in blob, "the Libyan data void is not dated in NO_LAWFUL_GROUND"
    for row in MGB.NO_LAWFUL_GROUND:
        assert row["what"] and row["why"] and row["consequence"]


# ------------------------------------------------------------------------------ the calendars
def test_the_working_week_is_split_and_the_split_is_in_the_rule() -> None:
    """Tunisia rests Saturday-Sunday and the other three rest Friday-Saturday, so Sunday is a
    working day in three of the four. This is the first thing a Maghreb study gets wrong."""
    assert MGB.weekend_weekdays("tn") == (5, 6)
    for cc in ("dz", "ly", "mr"):
        assert MGB.weekend_weekdays(cc) == (4, 5), f"{cc} does not rest Friday-Saturday"
    sunday, friday = date(2025, 3, 2), date(2025, 3, 7)
    assert sunday.weekday() == 6 and friday.weekday() == 4
    assert MGB.is_session_day("dz", sunday) and not MGB.is_session_day("tn", sunday)
    assert MGB.is_session_day("tn", friday) and not MGB.is_session_day("dz", friday)
    shared = MGB.shared_session_days(date(2025, 3, 1), date(2025, 3, 31))
    assert shared, "no day in March 2025 is open in all four, which cannot be right"
    assert all(d.weekday() not in (4, 5, 6) for d in shared), (
        "a shared session day fell on somebody's weekend")
    assert date(2025, 3, 30) not in shared, "Eid al-Fitr day 1 is not a shared session"
    rule = str(MGB.HOLIDAYS_RULE["rule"])
    assert "SPLIT" in rule and "2009-08-14" in rule, (
        "the rule does not carry the split week or the dated Algerian weekend change")
    assert MGB._holiday_rule_row()["weekly_closed"] == (4, 5, 6)


def test_the_national_days_are_derived_and_yennayer_is_dated() -> None:
    """A fixed solar date is computed, never typed into a year table -- and Yennayer became a
    statutory ALGERIAN holiday in 2018, which is a calendar entry that did not exist before."""
    for year in (2024, 2025, 2026):
        assert date(year, 11, 1) in MGB.holidays_for("dz", year)     # Revolution Day
        assert date(year, 7, 5) in MGB.holidays_for("dz", year)      # Independence Day
        assert date(year, 2, 17) in MGB.holidays_for("ly", year)     # 17 February
        assert date(year, 12, 24) in MGB.holidays_for("ly", year)    # Independence Day
        assert date(year, 3, 20) in MGB.holidays_for("tn", year)     # Independence Day
        assert date(year, 7, 25) in MGB.holidays_for("tn", year)     # Republic Day
        assert date(year, 1, 14) in MGB.holidays_for("tn", year)     # Revolution Day
        assert date(year, 11, 28) in MGB.holidays_for("mr", year)    # Independence Day
        assert date(year, 1, 12) in MGB.holidays_for("dz", year)     # Yennayer, since 2018
    # DATED: before 2018 Yennayer was not a statutory Algerian closure
    assert date(2017, 1, 12) not in MGB.holidays_for("dz", 2017)
    assert MGB.YENNAYER_STATUTORY_FROM["dz"] == 2018
    # and it is NOT a Mauritanian day: claiming it would put a closure in a calendar with none
    assert date(2025, 1, 12) not in MGB.holidays_for("mr", 2025)
    assert "ly" in MGB.YENNAYER_OBSERVED_NOT_STATUTORY


def test_the_holiday_table_resolves_for_all_three_years_and_stays_inside_them() -> None:
    for year in (2024, 2025, 2026):
        table = holiday_table(MGB.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
    assert "2026-11-01" in holiday_table(MGB.HOLIDAYS_RULE, 2026)
    assert "2026-01-12" in holiday_table(MGB.HOLIDAYS_RULE, 2026)


def test_the_sighted_feasts_are_typed_with_their_authority_and_2026_is_projected() -> None:
    """A Hijri date is an ANNOUNCEMENT by a named authority, not an arithmetic result."""
    rule = str(MGB.HOLIDAYS_RULE["rule"]).lower()
    assert "sighting" in rule and "cannot be computed" in rule
    assert set(MGB.SIGHTING_AUTHORITIES) == set(MGB.JURISDICTIONS)
    assert all(MGB.has_arabic(v) for v in MGB.SIGHTING_AUTHORITIES.values())
    for year, rows in MGB.LUNAR_HOLIDAYS.items():
        assert rows, f"no lunar rows for {year}"
        for day, name, ccs, status in rows:
            assert day.year == year
            assert name and ccs and set(ccs) <= set(MGB.JURISDICTIONS)
            for cc in MGB.JURISDICTIONS:
                assert f"{cc}=" in status, f"{year} {name}: status does not name {cc}"
            if year == 2026:
                assert status.startswith("PROJECTED"), (
                    f"{name} 2026 cannot already be announced: no sighting has happened")
            else:
                assert status.startswith("ANNOUNCED")
    assert date(2024, 4, 10) in {d for d, *_ in MGB.LUNAR_HOLIDAYS[2024]}
    assert date(2025, 3, 30) in {d for d, *_ in MGB.LUNAR_HOLIDAYS[2025]}
    # Ashura closes ALGERIA ONLY of the four; a pooled Maghreb dummy gets it wrong three times
    ashura = [row for row in MGB.LUNAR_HOLIDAYS[2025] if "عاشوراء" in row[1]]
    assert ashura and all(row[2] == ("dz",) for row in ashura)
    assert date(2025, 7, 5) in MGB.holidays_for("dz", 2025)
    assert date(2025, 7, 5) not in MGB.holidays_for("tn", 2025)
    # the Ramadan window drifts about eleven days a year, which is the identification
    starts = [MGB.RAMADAN_WINDOWS[y][0] for y in (2024, 2025, 2026)]
    for lo, hi in pairwise(starts):
        drift = (lo.replace(year=lo.year + 1) - hi).days
        assert 9 <= drift <= 13, f"the Hijri drift should be about eleven days, got {drift}"
    assert MGB.in_ramadan(date(2025, 3, 10)) and not MGB.in_ramadan(date(2025, 5, 10))
    assert MGB.RAMADAN_WINDOWS[2026][2] == "PROJECTED"


# ---------------------------------------------------------------- the pack's own mechanisms
def test_pipeline_capacity_dates_the_2021_maghreb_europe_closure() -> None:
    """MECHANISM ONE, and the reason this pack names `ma` first: the Maghreb-Europe line carried
    a declared 12 bcm/y on 2021-10-31 and ZERO on 2021-11-01, because a transit contract was not
    renewed. A capacity that goes to zero on a dated political decision is a testable object."""
    assert MGB.pipeline_capacity("meg", date(2021, 10, 31)) == 12.0
    assert MGB.pipeline_capacity("meg", date(2021, 11, 1)) == 0.0
    assert MGB.pipeline_capacity("meg", date(1995, 1, 1)) == 0.0   # before first gas
    assert MGB.pipeline_capacity("meg", date(2000, 1, 1)) == 8.6
    assert MGB.pipeline_capacity("transmed", date(2021, 11, 1)) == 33.5
    assert MGB.pipeline_capacity("medgaz", date(2010, 1, 1)) == 0.0
    assert MGB.pipeline_capacity("medgaz", date(2015, 1, 1)) == 8.0
    assert MGB.pipeline_capacity("medgaz", date(2022, 1, 1)) == 10.16
    assert MGB.pipeline_capacity("no such pipe", date(2022, 1, 1)) == 0.0
    assert MGB.pipeline_state("meg", date(2022, 1, 1))["state"] == "CLOSED"
    assert MGB.pipeline_state("transmed", date(2022, 1, 1))["state"] == "OPEN"
    assert MGB.pipeline_state("medgaz", date(2005, 1, 1))["state"] == "NOT_YET_COMMISSIONED"
    # GALSI and the Trans-Saharan line are the placebo arm: announced, never built
    assert MGB.pipeline_state("galsi", date(2022, 1, 1))["state"] == "NEVER_BUILT"
    assert MGB.pipeline_state("tsgp", date(2023, 1, 1))["capacity_bcm"] == 0.0
    unknown = MGB.pipeline_state("some unlisted pipe", date(2022, 1, 1))
    assert unknown["known"] is False and unknown["state"] == "UNMEASURED"
    # the closure removed about 12 bcm/y of route capacity from the whole map
    before = MGB.maghreb_export_capacity(date(2021, 10, 31))
    after = MGB.maghreb_export_capacity(date(2021, 11, 2))
    assert before > after, "the route map did not change across the closure"
    assert abs((before - after) - (12.0 - 2.16)) < 1e-6, (before, after)


def test_libya_outage_state_is_a_dated_published_non_economic_switch() -> None:
    """MECHANISM TWO: the reason Libya is worth its trial budget. Every episode was declared
    publicly, by name, with named terminals, on a political rather than a price trigger."""
    inside = MGB.libya_outage_state(date(2020, 5, 1))
    assert inside["in_outage"] is True
    assert inside["kb_d_offline"] == 1100.0
    assert "Sharara" in inside["where"] and "Es Sider" in inside["where"]
    cbl = MGB.libya_outage_state(date(2024, 9, 10))
    assert cbl["in_outage"] is True and cbl["kb_d_offline"] == 700.0
    assert "governorship" in cbl["what"].lower()
    quiet = MGB.libya_outage_state(date(2019, 6, 1))
    assert quiet["in_outage"] is False and quiet["kb_d_offline"] == 0.0
    assert "not a claim" in quiet["why"], (
        "silence outside a declared episode must not be read as a claim of normal production")
    assert len(MGB.LIBYA_OUTAGES) >= 5
    for start, end, what, where, kbd, status in MGB.LIBYA_OUTAGES:
        assert end >= start and what and where and kbd > 0.0 and status == "HISTORICAL"
    assert "Es Sider" in MGB.LIBYAN_TERMINALS and "Sharara" in MGB.LIBYAN_FIELDS


def test_the_parallel_premium_carries_its_credibility_label_and_refuses_nonsense() -> None:
    """MECHANISM THREE: the second price of the dinar. No authority stands behind the parallel
    leg, so every answer carries UNRELIABLE and the premium is used only as a spread."""
    got = MGB.dzd_parallel_premium(135.0, 243.0)
    assert got["measured"] is True
    assert abs(float(got["premium_pct"]) - 80.0) < 1e-6, got
    assert got["band"] == "EXTREME" and got["credibility"] == "UNRELIABLE"
    assert MGB.dzd_parallel_premium(100.0, 140.0)["band"] == "STRESSED"
    assert MGB.dzd_parallel_premium(100.0, 115.0)["band"] == "ELEVATED"
    assert MGB.dzd_parallel_premium(100.0, 101.0)["band"] == "NORMAL"
    for bad in ((0.0, 200.0), (135.0, 0.0), (-1.0, 200.0)):
        out = MGB.dzd_parallel_premium(*bad)
        assert out["measured"] is False and "UNMEASURED" in out["why"]


def test_the_olive_campaign_year_is_the_unit_and_not_the_calendar_year() -> None:
    """MECHANISM FOUR: a calendar-year olive study cuts every harvest in half."""
    nov = MGB.olive_campaign_year(date(2024, 11, 15))
    jan = MGB.olive_campaign_year(date(2025, 1, 15))
    assert nov["campaign"] == jan["campaign"] == "2024/25", (nov, jan)
    assert nov["start"] == "2024-11-01" and nov["end"] == "2025-10-31"
    assert nov["phase"] == "harvest_and_crush" and jan["phase"] == "harvest_and_crush"
    assert MGB.olive_campaign_year(date(2025, 3, 1))["phase"] == "marketing"
    assert MGB.olive_campaign_year(date(2025, 8, 1))["phase"] == "carry_out_and_crop_formation"
    assert MGB.olive_campaign_year(date(2025, 10, 31))["campaign"] == "2024/25"
    assert MGB.olive_campaign_year(date(2025, 11, 1))["campaign"] == "2025/26"


def test_the_mauritanian_redenomination_is_applied_and_never_inferred() -> None:
    """MECHANISM FIVE: a LEVEL spliced across 2018-01-01 is wrong by a factor of ten while a
    RATIO is silently right, which is why the break survives every growth-rate sanity check."""
    old = MGB.mru_redenominate(1000.0, date(2017, 12, 31))
    new = MGB.mru_redenominate(1000.0, date(2018, 1, 1))
    assert old["unit_in"] == "MRO" and old["amount_mru"] == 100.0 and old["factor"] == 10.0
    assert new["unit_in"] == "MRU" and new["amount_mru"] == 1000.0 and new["factor"] == 1.0
    assert date(2018, 1, 1) == MGB.MRU_REDENOMINATION and MGB.MRU_FACTOR == 10.0
    assert MGB.mru_redenominate("not a number", date(2020, 1, 1))["measured"] is False


# ------------------------------------------------------------------------------ the cells
def test_the_pack_mints_cells_the_gauntlet_can_actually_compile() -> None:
    """The point of a pack is cells reaching the one gauntlet, and every one must name a real
    symbol, a real condition from its own domain, and a control it cannot travel without."""
    minted = MGB.cells()
    assert len(minted) >= DECLARED_DEPTH["cells"], f"only {len(minted)} cells"
    assert len(minted) == len({c["cell_id"] for c in minted}), "duplicate cell ids"
    domain_conditions = {d["id"]: set(d["conditions"]) for d in MGB.DOMAINS}
    registry = universe_symbols()
    for cell in minted:
        for field in ("cell_id", "domain", "symbol", "condition", "mechanism_family",
                      "horizon", "control", "why"):
            assert cell[field], f"{cell.get('cell_id')} has an empty {field}"
        assert cell["symbol"] in registry, f"{cell['cell_id']} names an unquotable symbol"
        assert cell["symbol"] in MGB.EXECUTABLE_INSTRUMENTS
        assert cell["condition"] in domain_conditions[cell["domain"]], (
            f"{cell['cell_id']} invents a condition its own domain never named")
    covered = {c["domain"] for c in minted}
    assert covered == {d["id"] for d in MGB.DOMAINS}, "a domain mints no cells at all"
    by_jur = {c["jurisdiction"] for c in minted}
    assert set(MGB.JURISDICTIONS) <= by_jur, "a jurisdiction mints no cells of its own"


def test_the_interactions_name_ma_first_and_west_africa_second() -> None:
    """`ma` is first because the Maghreb-Europe pipeline through Morocco IS the interaction, and
    `west_africa` is second because Mauritania and Senegal share one gas reservoir."""
    assert len(MGB.INTERACTIONS) >= DECLARED_DEPTH["interactions"]
    assert MGB.INTERACTIONS[0]["with"] == "ma"
    assert MGB.INTERACTIONS[1]["with"] == "west_africa"
    assert "2021-10-31" in str(MGB.INTERACTIONS[0]["mechanism"])
    assert "SENEGAL" in str(MGB.INTERACTIONS[1]["mechanism"]).upper()
    on_disk = {p.name for p in (_DESK / "research" / "countries").iterdir() if p.is_dir()}
    withs = {row["with"] for row in MGB.INTERACTIONS}
    assert {"ma", "west_africa", "au", "cn"} <= withs, (
        "the iron-ore controls and the two named siblings must all be interaction rows")
    for row in MGB.INTERACTIONS:
        assert row["with"] in on_disk, f"interaction with {row['with']!r} names no pack on disk"
        assert row["mechanism"] and row["observable"] and row["control"]
        assert resolve(row["targets"])["absent"] == [], f"{row['with']} -> unquotable target"


def test_the_datasets_are_fetchable_and_spread_across_the_layers() -> None:
    """A dataset whose `how_to_fetch` is a wish is a collector task nobody can start."""
    assert len(MGB.DATASETS) >= DECLARED_DEPTH["datasets"]
    for row in MGB.DATASETS:
        assert len(str(row["how_to_fetch"])) > 40, f"{row['name']}: how_to_fetch is too thin"
        assert float(row["publication_lag_days"]) >= 0.0
        assert resolve(row["assets"])["absent"] == [], f"{row['name']} names an absent asset"
        assert row["mechanism_families"]
    # three series are published on pages that overwrite in place, so they are NOT point-in-time
    assert sum(1 for r in MGB.DATASETS if not r["pit_feasible"]) >= 2, (
        "no dataset is declared non-point-in-time, which cannot be right for pages that "
        "overwrite in place")


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {f"custom:{name}" for name in MGB.MINERS}
    assert all(callable(fn) for fn in got.values())
    ids = {d["id"] for d in MGB.DOMAINS}
    for row in MGB.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.maghreb_energy.pack", row["entry"]
        assert func in MGB.MINERS, f"{row['entry']} is not in the MINERS registry"
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    for did in MGB.MINER_DOMAINS.values():
        assert set(did) <= ids


def test_mine_returns_a_report_and_records_nothing_without_a_context() -> None:
    """The department entry: pure python, no network, an artifact on every call, and a DRY RUN
    when nothing was handed to it to emit through (UNWIRED IS A DEFECT, III.16)."""
    report = MGB.mine(None)
    assert report["code"] == "maghreb_energy"
    assert tuple(report["jurisdictions"]) == MGB.JURISDICTIONS
    assert report["emitted"] == 0, "mine(None) must record nothing"
    assert report["dry_run"] is True
    assert report["cells_emitted"] == len(MGB.cells())
    assert report["rows"] and len(report["rows"]) == len(MGB.MINERS)
    assert report["unmeasured"], "a pack that reports nothing UNMEASURED is not being honest"
    assert sum(report["cells_by_domain"].values()) == report["cells_emitted"]
    assert report["at"].endswith("+00:00"), "the stamp must be timezone-aware UTC"

    class _Ctx:
        def __init__(self) -> None:
            self.lines: list[tuple[str, str]] = []

        def note(self, kind: str, text: str) -> None:
            self.lines.append((kind, text))

    ctx = _Ctx()
    wet = MGB.mine(ctx)
    assert wet["dry_run"] is False
    assert wet["emitted"] == len(ctx.lines) > 0
    assert {kind for kind, _ in ctx.lines} >= {"mgb_pipeline", "mgb_libya_outage",
                                               "mgb_currency", "mgb_calendar"}


def test_the_policy_eras_are_dated_and_name_what_pooling_across_them_destroys() -> None:
    """The Libyan institutional split and the 2021 closure are the two this pack exists to keep
    out of a pooled sample."""
    assert len(MGB.POLICY_ERAS) >= DECLARED_DEPTH["eras"]
    for row in MGB.POLICY_ERAS:
        lo = date.fromisoformat(str(row["start"]))
        hi = date.fromisoformat(str(row["end"]))
        assert hi >= lo, f"{row['name']}: reversed dates"
        assert row["why_it_matters"] and row["markers"] and row["regime"]
        assert row["status"] in ("SETTLED", "OPEN")
    closure = [r for r in MGB.POLICY_ERAS if "Maghreb-Europe" in str(r["name"])]
    assert closure and closure[0]["start"] == "2021-11-01"
    split = [r for r in MGB.POLICY_ERAS if "institutional split" in str(r["name"])]
    assert split and split[0]["start"] == "2014-09-01"
    assert any("2018-01-01" in " ".join(r["markers"]) for r in MGB.POLICY_ERAS), (
        "the Mauritanian redenomination is not a dated era marker")


def test_the_access_constraints_state_the_libya_lawfulness_position_on_the_record() -> None:
    """Libya has two administrations and its entities have been under UN measures; the pack must
    say in its own data that it touches no private system and bypasses no access control."""
    blob = " ".join(f"{r['constraint']} {r['measured']} {r['consequence']}"
                    for r in MGB.ACCESS_CONSTRAINTS)
    assert "TWO COMPETING ADMINISTRATIONS" in blob
    assert "NOTHING IN THIS PACK TOUCHES ANY ENTITY'S PRIVATE SYSTEMS" in blob
    assert "BYPASSES AN ACCESS CONTROL" in blob
    assert "only broker symbols" in blob.lower()
    for row in MGB.ACCESS_CONSTRAINTS:
        assert row["constraint"] and row["measured"] and row["consequence"]


def test_positioning_absences_are_declared_rather_than_silently_missing() -> None:
    """Three absences a study can trip over, all named: no COT for any of the four currencies,
    no Algerian retail flow, and no Libyan market to be positioned in at all."""
    unavailable = [r for r in MGB.POSITIONING_SOURCES if not r["available"]]
    assert len(unavailable) >= 3
    assert all("DOES NOT EXIST" in str(r["pit_warning"]) for r in unavailable)
    assert MGB.COT_CURRENCY == ""
    for row in MGB.POSITIONING_SOURCES:
        assert row["why"] and row["pit_warning"]
