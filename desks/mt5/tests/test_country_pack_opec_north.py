"""THE NORTHERN GULF AND LEVANT PACK, VALIDATED -- five states, four weekends, one trial budget.

What these tests refuse to let through, each a way this pack could be wrong while looking done:

  * FIVE COUNTRIES CREDITED AS ONE. The parity fence reads `JURISDICTIONS` and nothing else.
  * ONE "LEVANT" MECHANISM WITH FIVE FLAGS ON IT. Every jurisdiction must own actors and domains.
  * A TYPED NOWRUZ. The Iranian year begins at the EQUINOX as observed in Tehran, so it is 20
    March in some years and 21 in others; a typed table gets 2025 wrong. It is DERIVED here.
  * ONE EASTER IN LEBANON. Lebanon keeps both computi and the gap was 35 days, then 0, then 7.
  * A EUROPEAN WEEKEND ON A REGIONAL CALENDAR -- or one weekend for five neighbours. Iraq,
    Jordan and Syria rest Friday-Saturday, Lebanon Saturday-Sunday, Iran Thursday-Friday, and
    only Monday to Wednesday is shared.
  * AN ARABIC-ONLY CRAWL OF A PERSIAN AND KURDISH GROUND.
  * A SYMBOL THE BOX CANNOT TRADE, or a single name on a docket. None of the five currencies is
    quoted; all five must stay transmission targets with carriers that resolve.
  * A BLANK LAYER PASSED OFF AS COVERAGE. Syria's missing layers are DECLARED with substitutes.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
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
from countries.opec_north import pack as ON  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as FORESTS  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")
#: The pack's own declared depth. Twelve actors is the package floor for ONE country; five
#: jurisdictions written to that floor would be five countries a fifth read.
DECLARED_DEPTH = {"actors": 20, "domains": 14, "edges": 12, "sources": 20, "datasets": 18,
                  "eras": 5, "terms": 120, "cells": 60, "interactions": 4}


@pytest.fixture(scope="module")
def built() -> Any:
    got = CL.resolve_pack("opec_north")
    assert got is not None, "no opec_north pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    assert check_pack(ON.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == "opec_north"
    assert str(get(built, "region_command")) == "mea"
    assert str(get(built, "currency")) == "IQD"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    notes = list(getattr(built, "coercion_notes", ()) or [])
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on this pack: {fatal[:4]}"


def test_pack_reaches_parity_depth(built: Any) -> None:
    row = RP.pack_depth(built, "opec_north").as_row()
    assert row["score"] == 1.0, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_depth_sits_above_the_floor_because_five_states_share_one_pack() -> None:
    assert len(ON.ACTORS) >= DECLARED_DEPTH["actors"]
    assert len(ON.DOMAINS) >= DECLARED_DEPTH["domains"]
    assert len(ON.TRANSMISSION_EDGES_SEED) >= DECLARED_DEPTH["edges"]
    assert len(ON.SOURCE_CLASSES) >= DECLARED_DEPTH["sources"]
    assert len(ON.DATASETS) >= DECLARED_DEPTH["datasets"]
    assert len(ON.POLICY_ERAS) >= DECLARED_DEPTH["eras"]
    assert ON.term_count() >= DECLARED_DEPTH["terms"]


# ------------------------------------------------------------------- the five jurisdictions
def test_jurisdictions_are_declared_lowercase_and_on_the_desks_own_roster() -> None:
    assert ON.JURISDICTIONS == ("iq", "ir", "jo", "lb", "sy")
    assert all(cc == cc.lower() and len(cc) == 2 for cc in ON.JURISDICTIONS)
    # REGISTRATION IS THE COORDINATOR'S EDIT, not this builder's: `libs/research/forests.py` is
    # shared and several builders write it at once. The invariant that holds BOTH before and
    # after that edit is that none of the five may be claimed by a DIFFERENT forest -- a country
    # belongs to exactly one, and a pack that answers for a country another forest owns is a
    # double-count. An empty answer means "not yet registered" and is recorded, never asserted
    # away (L1.28a).
    assert ON.FOREST == "mena"
    for cc in ON.JURISDICTIONS:
        got = FORESTS.forest_of_country(cc)
        assert got in ("mena", ""), (
            f"{cc} is on the {got!r} forest, not mena; registering it here would double-count it")
    # the siblings this pack complements are NOT claimed here
    assert not {"sa", "ae", "qa", "kw", "om", "bh", "tr", "il"} & set(ON.JURISDICTIONS)


def test_every_jurisdiction_owns_actors_and_domains_of_its_own() -> None:
    for cc in ON.JURISDICTIONS:
        actors = [a for a in ON.ACTORS if a.get("jurisdiction") == cc]
        domains = [d for d in ON.DOMAINS if d.get("jurisdiction") == cc]
        assert len(actors) >= 3, f"{cc} owns only {len(actors)} actor(s)"
        assert len(domains) >= 2, f"{cc} owns only {len(domains)} domain(s)"
    assert [a for a in ON.ACTORS if a.get("jurisdiction") == "shared"]
    assert len(ON.CURRENCIES) == 5
    assert {v["jurisdiction"] for v in ON.CURRENCIES.values()} == set(ON.JURISDICTIONS)


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    for row in ON.ACTORS:
        for f in ACTOR_FIELDS:
            assert row.get(f), f"actor {row.get('name')!r} has an empty {f}"
        for f in ("forced_to", "information", "constraints", "instruments", "counterparties",
                  "observables"):
            value = row[f]
            assert isinstance(value, tuple), f"actor {row.get('name')!r}.{f} is not a tuple"
            assert all(len(str(v)) > 2 for v in value), (
                f"actor {row.get('name')!r}.{f} looks like a string split into characters -- a "
                f"single-element tuple needs its trailing comma")


def test_every_domain_has_objects_and_two_negative_controls() -> None:
    for row in ON.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert row["conditions"], f"domain {row['id']} names no conditioning state"
        assert row["id"] in ON.DOMAIN_CELL_SPEC, f"{row['id']} mints no cells"


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(ON.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    for dom in ON.DOMAINS:
        assert resolve(dom["instruments"])["equities"] == [], f"{dom['id']} names an equity"
        assert set(dom["instruments"]) <= set(ON.EXECUTABLE_INSTRUMENTS), (
            f"{dom['id']} names an instrument the pack never declared executable")


def test_every_transmission_seed_names_tradable_targets() -> None:
    for seed in ON.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"] and seed["falsifier"]
        assert seed["target"] in seed["targets"], f"edge {seed['id']} target/targets disagree"


def test_all_five_currencies_are_named_absent_with_their_regimes_and_carriers() -> None:
    """IQD, IRR, JOD, LBP and SYP are unquotable here, and where TWO regimes exist BOTH are
    named -- a pack carrying only the official rate of a country with a parallel market has
    recorded the number the state publishes and lost the number the economy uses."""
    registry = universe_symbols()
    for ccy in ("IQD", "IRR", "JOD", "LBP", "SYP"):
        assert not {ccy, f"USD{ccy}", f"{ccy}USD"} & set(registry), f"{ccy} is quoted after all"
    named = " ".join(str(t["name"]) for t in ON.TRANSMISSION_TARGETS)
    for must in ("IQD official", "IQD parallel", "IRR official", "IRR free market", "JOD",
                 "LBP official", "LBP parallel", "SYP official", "Bahar Azadi", "Potash"):
        assert must in named, f"the pack does not name {must!r} as an absent instrument"
    for row in ON.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == [], f"{row['name']} has an unquotable carrier"
        assert row["why"] and row["regime"]


# ------------------------------------------------------------------------------ the languages
def test_terminology_carries_arabic_persian_kurdish_and_the_english_record() -> None:
    assert len(ON.arabic_terms()) >= 90, f"only {len(ON.arabic_terms())} Arabic-script terms"
    persian = ON.persian_terms()
    assert len(persian) >= 12, f"only {len(persian)} Persian-specific terms"
    assert len(ON.kurdish_terms()) >= 3, f"only {len(ON.kurdish_terms())} Kurdish terms"
    assert len(ON.english_terms()) == len(ON.ENGLISH_MARKERS), (
        f"missing English working vocabulary: "
        f"{sorted(set(ON.ENGLISH_MARKERS) - set(ON.english_terms()))}")
    flat = {t for group in ON.TERMINOLOGY.values() for t in group}
    for must in ("أسعار البيع الرسمية", "خام البصرة الثقيل", "مزاد العملة", "منصة صيرفة",
                 "مضيق هرمز", "خط الغاز العربي", "سکه بهار آزادی", "پارس جنوبی",
                 "هەرێمی کوردستان"):
        assert must in flat, f"the pack does not carry {must!r}"
    assert ON.has_arabic("البنك المركزي العراقي") and not ON.has_arabic("Central Bank of Iraq")
    assert ON.has_persian("پارس جنوبی") and not ON.has_persian("البنك المركزي")
    assert ON.has_kurdish("هەرێمی کوردستان")
    assert set(ON.TERMINOLOGY) == {d["id"] for d in ON.DOMAINS}


def test_every_source_carries_a_native_query_and_three_independent_labels() -> None:
    for row in ON.SOURCE_CLASSES:
        assert row["access_label"] in ON.ACCESS_LABELS
        assert row["credibility"] in ON.CREDIBILITY_LABELS
        assert row["predictive_state"] in ON.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["notes"], f"{row['id']} says nothing about why it is here"
        if str(row["id"]).startswith("absent_"):
            assert row["reason"] and row["substitute"], f"{row['id']} names no substitute"
            continue
        assert row["queries"], f"{row['id']} has no query at all"
        assert row["roots"], f"{row['id']} has no crawlable root"
    terms = ON.layer_terms()
    native = [layer for layer, qs in terms.items() if any(ON.has_arabic(q) for q in qs)]
    assert len(native) >= 9, f"only {native} carry an Arabic-script query"
    assert any(ON.has_persian(q) for qs in terms.values() for q in qs), "no Persian query at all"


def test_query_territories_cover_every_layer_in_the_native_script() -> None:
    assert set(ON.QUERY_TERRITORIES) == set(ON.SOURCE_LAYERS)
    for layer, phrases in ON.QUERY_TERRITORIES.items():
        assert len(phrases) >= 3, f"{layer} has only {len(phrases)} query phrases"
        assert any(ON.has_arabic(p) for p in phrases), f"{layer} has no Arabic-script phrase"


def test_layers_are_populated_and_the_refusals_name_their_substitutes() -> None:
    """The depth rule: ten layers, none blank -- and where a JURISDICTION genuinely has nothing
    in a layer, the row names the state, the reason and the LAWFUL SUBSTITUTE."""
    counts = ON.layer_counts()
    assert set(counts) == set(ON.SOURCE_LAYERS)
    assert [layer for layer, n in counts.items() if not n] == []
    coverage = ON.source_layer_coverage()
    assert coverage["n_layers_covered"] == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], "nothing is registered machine-use-forbidden"
    assert coverage["low_weight_kept"], "no low-credibility ground is kept at all, so it was "\
                                        "dropped -- and this region's parallel rates live there"
    absences = ON.declared_absences()
    assert len(absences) >= 5, f"only {len(absences)} declared layer absences"
    assert {a["jurisdiction"] for a in absences} >= {"sy", "ir"}
    assert len([a for a in absences if a["jurisdiction"] == "sy"]) >= 4
    for row in absences:
        assert row["reason"] and row["substitute"]
        assert row["layer"] in ON.SOURCE_LAYERS
    assert len(ON.NO_LAWFUL_GROUND) >= 5
    for row in ON.NO_LAWFUL_GROUND:
        assert row["what"] and row["why"] and row["consequence"]


def test_the_sanctions_lawfulness_statement_is_explicit() -> None:
    """Iran and Syria are comprehensively sanctioned; the pack must say in its own data that it
    reads only public material and executes only broker symbols."""
    blob = " ".join(f"{r['constraint']} {r['measured']} {r['consequence']}"
                    for r in ON.ACCESS_CONSTRAINTS)
    for must in ("SANCTIONS CONSTRAIN TRANSACTIONS", "Federal Register", "OFAC",
                 "Article IV", "never an Iraqi, Iranian, Jordanian, Lebanese or Syrian "
                               "instrument"):
        assert must in blob, f"ACCESS_CONSTRAINTS does not say {must!r}"
    assert "NO CREDENTIAL" in blob.upper() or "USES ANY CREDENTIAL" in blob


# ------------------------------------------------------------------------------ the calendars
def test_four_weekends_across_five_neighbours_and_three_shared_session_days() -> None:
    """The single most commonly flattened fact about these five markets."""
    assert ON.WEEKENDS["iq"] == (4, 5) and ON.WEEKENDS["jo"] == (4, 5)
    assert ON.WEEKENDS["sy"] == (4, 5)
    assert ON.WEEKENDS["lb"] == (5, 6), "Lebanon rests Saturday-Sunday, like a European market"
    assert ON.WEEKENDS["ir"] == (3, 4), "Iran rests Thursday-Friday"
    assert ON.common_session_weekdays() == (0, 1, 2), (
        "Lebanon's weekend and Iran's are disjoint, so only Monday to Wednesday is shared")
    assert ON.is_session_day("lb", date(2025, 5, 22))       # a Thursday: Beirut OPEN
    assert not ON.is_session_day("ir", date(2025, 5, 22))   # the same Thursday: Tehran closed
    assert ON.is_session_day("ir", date(2025, 5, 25))       # a Sunday: Tehran OPEN
    assert not ON.is_session_day("lb", date(2025, 5, 25))   # the same Sunday: Beirut closed
    days = ON.common_session_days(date(2025, 5, 1), date(2025, 5, 31))
    assert days and all(d.weekday() in (0, 1, 2) for d in days)


def test_nowruz_is_derived_from_the_equinox_and_not_typed() -> None:
    """MECHANISM ONE. The equinox fell at 06:37 Tehran in 2024 and 12:32 in 2025, so the year
    began on 20 March and then on 21 March -- the case a typed table gets wrong."""
    assert ON.nowruz(2024) == date(2024, 3, 20)
    assert ON.nowruz(2025) == date(2025, 3, 21)
    assert ON.nowruz(2026) == date(2026, 3, 21)
    assert ON.nowruz(2023) == date(2023, 3, 21)
    assert ON.march_equinox_utc(2025).month == 3
    # the Solar Hijri boundary is Nowruz, not 1 January and not a fixed 21 March
    assert ON.solar_hijri_year(date(2025, 3, 20)) == 1403
    assert ON.solar_hijri_year(date(2025, 3, 21)) == 1404
    assert ON.solar_hijri_year(date(2024, 3, 19)) == 1402
    assert ON.solar_hijri_year(date(2024, 3, 20)) == 1403
    assert ON.iran_fiscal_year_start(1404) == date(2025, 3, 21)
    assert ON.solar_hijri_to_gregorian(1403, 1, 1) == date(2024, 3, 20)
    # 22 Bahman is derived by day-count from the same anchor, never typed
    iran_2025 = ON.iran_national(2025)
    assert date(2025, 2, 10) in iran_2025
    assert date(2026, 2, 11) in ON.iran_national(2026)
    # the shutdown really is about a fortnight, ending with Sizdah Bedar
    assert date(2025, 4, 2) in iran_2025, "13 Farvardin (Sizdah Bedar) 1404"
    assert (date(2025, 4, 2) - ON.nowruz(2025)).days == 12


def test_lebanon_computes_both_easters_and_the_gap_is_not_a_constant() -> None:
    """MECHANISM TWO. 35 days apart in 2024, the SAME DAY in 2025, 7 days apart in 2026."""
    assert ON.western_easter(2024) == date(2024, 3, 31)
    assert ON.orthodox_easter(2024) == date(2024, 5, 5)
    assert ON.western_easter(2025) == ON.orthodox_easter(2025) == date(2025, 4, 20)
    assert ON.western_easter(2026) == date(2026, 4, 5)
    assert ON.orthodox_easter(2026) == date(2026, 4, 12)
    lb = ON.holidays_for("lb", 2024)
    assert date(2024, 3, 29) in lb and date(2024, 5, 3) in lb     # both Good Fridays
    assert date(2024, 3, 25) in lb, "the Annunciation, a shared Christian-Muslim holiday"
    assert date(2024, 3, 25) not in ON.holidays_for("jo", 2024)


def test_the_holiday_table_resolves_for_all_three_years_and_stays_inside_them() -> None:
    for year in (2024, 2025, 2026):
        table = holiday_table(ON.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
    assert "2026-03-21" in holiday_table(ON.HOLIDAYS_RULE, 2026)   # derived Nowruz
    assert "2025-05-25" in holiday_table(ON.HOLIDAYS_RULE, 2025)   # Jordanian Independence Day


def test_the_sighted_feasts_are_typed_with_five_authorities_and_2026_is_projected() -> None:
    rule = str(ON.HOLIDAYS_RULE["rule"]).lower()
    assert "sighting" in rule and "cannot be computed" in rule
    assert set(ON.SIGHTING_AUTHORITIES) == set(ON.JURISDICTIONS)
    assert all(ON.has_arabic(v) for v in ON.SIGHTING_AUTHORITIES.values())
    for year, rows in ON.LUNAR_HOLIDAYS.items():
        assert rows, f"no lunar rows for {year}"
        for day, name, ccs, status in rows:
            assert day.year == year
            assert name and ccs and set(ccs) <= set(ON.JURISDICTIONS)
            for cc in ON.JURISDICTIONS:
                assert f"{cc}=" in status, f"{year} {name}: status does not name {cc}"
            assert status.split(" :: ")[0].startswith("PROJECTED" if year == 2026 else "ANNOUNCED")
    # the one-day Iranian and Najaf split, which a Gulf calendar gets wrong
    assert date(2025, 3, 30) in ON.holidays_for("jo", 2025)
    assert date(2025, 3, 30) not in ON.holidays_for("ir", 2025)
    assert date(2025, 3, 31) in ON.holidays_for("ir", 2025)
    # Arbaeen closes Iraq and Iran and nobody else
    assert date(2025, 8, 14) in ON.holidays_for("iq", 2025)
    assert date(2025, 8, 14) not in ON.holidays_for("jo", 2025)


def test_the_syrian_calendar_changed_on_a_date_and_the_pack_knows_it() -> None:
    """The 2024-12-08 transition abolished holidays and added one. A single Syrian calendar
    across the whole sample is a calendar that no longer exists."""
    assert date(2024, 3, 8) in ON.holidays_for("sy", 2024)
    assert date(2025, 3, 8) not in ON.holidays_for("sy", 2025)
    assert date(2024, 10, 6) in ON.holidays_for("sy", 2024)
    assert date(2025, 12, 8) in ON.holidays_for("sy", 2025)
    assert date(2024, 12, 8) not in ON.holidays_for("sy", 2024)


# ---------------------------------------------------------------- the pack's own mechanisms
def test_the_lebanese_official_rate_is_a_dated_staircase() -> None:
    """MECHANISM THREE. Three administered numbers under one label in one sample."""
    assert ON.lbp_official_rate(date(2019, 1, 1))["official"] == 1507.5
    assert ON.lbp_official_rate(date(2023, 1, 31))["official"] == 1507.5
    assert ON.lbp_official_rate(date(2023, 2, 1))["official"] == 15000.0
    assert ON.lbp_official_rate(date(2023, 10, 31))["official"] == 15000.0
    assert ON.lbp_official_rate(date(2024, 6, 1))["official"] == 89500.0
    assert ON.lbp_official_rate(date(2019, 1, 1))["regime"] == "PEG_HELD"
    assert ON.lbp_official_rate(date(2024, 6, 1))["regime"] == "POST_DEVALUATION"


def test_parallel_premium_scales_the_regimes_and_pins_jordan_at_zero() -> None:
    """MECHANISM FOUR. JOD is the control BY CONSTRUCTION: one number, no premium."""
    jo = ON.parallel_premium("JOD", 0.709, 0.709)
    assert jo["measured"] is True and abs(float(jo["premium_pct"])) < 1e-9
    assert jo["state"] == "NO_PREMIUM"
    lb = ON.parallel_premium("LBP", 1507.5, 89500.0)
    assert lb["state"] == "REGIME_FAILURE" and float(lb["premium_pct"]) > 5000.0
    iq = ON.parallel_premium("IQD", 1320.0, 1500.0)
    assert iq["state"] == "FRICTION" and iq["jurisdiction"] == "iq"
    ir = ON.parallel_premium("IRR", 42000.0, 600000.0)
    assert ir["state"] == "REGIME_FAILURE"
    assert ON.parallel_premium("QAR", 3.64, 3.64)["measured"] is False
    assert ON.parallel_premium("IQD", 0.0, 1500.0)["measured"] is False


def test_the_kurdistan_pipeline_is_a_court_dated_supply_shock() -> None:
    """MECHANISM FIVE. Shut since 2023-03-25 on a published ICC award."""
    assert ON.kurdistan_pipeline_state(date(2023, 3, 24))["state"] == "FLOWING"
    assert ON.kurdistan_pipeline_state(date(2023, 3, 25))["shut"] is True
    assert ON.kurdistan_pipeline_state(date(2025, 1, 1))["kbd"] == 0.0
    late = ON.kurdistan_pipeline_state(date(2026, 1, 1))
    assert late["state"] == "PARTIAL_RESUMPTION"
    assert "PUBLIC_REPORTING" in late["evidence"], "a reported restart is never called measured"
    assert "PUBLISHED_RULING" in ON.kurdistan_pipeline_state(date(2024, 1, 1))["evidence"]


def test_the_sanctions_and_compensation_clocks_answer_or_say_unmeasured() -> None:
    assert ON.iran_policy_direction(date(2014, 1, 1))["measured"] is False
    assert ON.iran_policy_direction(date(2017, 1, 1))["direction"] == "+"
    assert ON.iran_policy_direction(date(2019, 6, 1))["direction"] == "-"
    assert ON.iran_policy_direction(date(2022, 6, 1))["direction"] == "+"
    assert ON.iraq_compensation_due(date(2023, 1, 1))["measured"] is False
    live = ON.iraq_compensation_due(date(2025, 6, 1))
    assert live["measured"] is True and live["pledged_kbd"] > 0
    coin = ON.coin_premium(coin_price=1000.0, gold_price=100.0)
    assert coin["measured"] is True and float(coin["premium_pct"]) > 0
    assert ON.coin_premium(coin_price=0.0, gold_price=100.0)["measured"] is False


# ------------------------------------------------------------------------------ the cells
def test_the_pack_mints_cells_the_gauntlet_can_actually_compile() -> None:
    minted = ON.cells()
    assert len(minted) >= DECLARED_DEPTH["cells"], f"only {len(minted)} cells"
    assert len(minted) == len({c["cell_id"] for c in minted}), "duplicate cell ids"
    domain_conditions = {d["id"]: set(d["conditions"]) for d in ON.DOMAINS}
    registry = universe_symbols()
    for cell in minted:
        for field in ("cell_id", "domain", "symbol", "condition", "mechanism_family",
                      "horizon", "control", "why"):
            assert cell[field], f"{cell.get('cell_id')} has an empty {field}"
        assert cell["symbol"] in registry, f"{cell['cell_id']} names an unquotable symbol"
        assert cell["symbol"] in ON.EXECUTABLE_INSTRUMENTS
        assert cell["condition"] in domain_conditions[cell["domain"]], (
            f"{cell['cell_id']} invents a condition its own domain never named")
    assert {c["domain"] for c in minted} == {d["id"] for d in ON.DOMAINS}
    assert set(ON.JURISDICTIONS) <= {c["jurisdiction"] for c in minted}


def test_the_interactions_name_real_sibling_packs_and_tradable_targets() -> None:
    """`gulf`, `sa`, `tr` and `il` are required; `dk` is the never-failed peg control that makes
    the Lebanese case an identification strategy rather than a story."""
    assert len(ON.INTERACTIONS) >= DECLARED_DEPTH["interactions"]
    withs = {row["with"] for row in ON.INTERACTIONS}
    assert {"gulf", "sa", "tr", "il"} <= withs
    assert "dk" in withs, "the Danish peg is the named control for Lebanon's failure"
    on_disk = {p.name for p in (_DESK / "research" / "countries").iterdir() if p.is_dir()}
    for row in ON.INTERACTIONS:
        assert row["with"] in on_disk, f"interaction with {row['with']!r} names no pack on disk"
        assert row["mechanism"] and row["observable"] and row["control"]
        assert resolve(row["targets"])["absent"] == [], f"{row['with']} -> unquotable target"
    gulf = next(r for r in ON.INTERACTIONS if r["with"] == "gulf")
    assert "BYPASS" in gulf["mechanism"], "the Hormuz bypass must be deferred to `gulf`"


def test_the_datasets_are_fetchable_and_spread_across_the_layers() -> None:
    assert len(ON.DATASETS) >= DECLARED_DEPTH["datasets"]
    names = [r["name"] for r in ON.DATASETS]
    assert len(names) == len(set(names)), "a dataset is declared twice"
    for row in ON.DATASETS:
        assert len(str(row["how_to_fetch"])) > 40, f"{row['name']}: how_to_fetch is too thin"
        assert float(row["publication_lag_days"]) >= 0.0
        assert resolve(row["assets"])["absent"] == [], f"{row['name']} names an absent asset"
        assert row["mechanism_families"]


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {f"custom:{name}" for name in ON.MINERS}
    assert all(callable(fn) for fn in got.values())
    ids = {d["id"] for d in ON.DOMAINS}
    for row in ON.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.opec_north.pack", row["entry"]
        assert func in ON.MINERS, f"{row['entry']} is not in the MINERS registry"
        assert row["domain_ids"]
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    for did in ON.MINER_DOMAINS.values():
        assert set(did) <= ids


def test_mine_returns_a_report_and_records_nothing_without_a_context() -> None:
    report = ON.mine(None)
    assert report["code"] == "opec_north"
    assert tuple(report["jurisdictions"]) == ON.JURISDICTIONS
    assert report["emitted"] == 0, "mine(None) must record nothing"
    assert report["dry_run"] is True
    assert report["cells_emitted"] == len(ON.cells())
    assert report["rows"] and len(report["rows"]) == len(ON.MINERS)
    assert report["unmeasured"], "a pack that reports nothing UNMEASURED is not being honest"
    assert sum(report["cells_by_domain"].values()) == report["cells_emitted"]
    assert report["at"].endswith("+00:00"), "the stamp must be timezone-aware UTC"

    class _Ctx:
        def __init__(self) -> None:
            self.lines: list[tuple[str, str]] = []

        def note(self, kind: str, text: str) -> None:
            self.lines.append((kind, text))

    ctx = _Ctx()
    wet = ON.mine(ctx)
    assert wet["dry_run"] is False
    assert wet["emitted"] == len(ctx.lines) > 0
    assert {kind for kind, _ in ctx.lines} >= {"opecn_pipeline", "opecn_calendar",
                                               "opecn_absence"}


def test_the_policy_eras_are_dated_and_name_what_pooling_across_them_destroys() -> None:
    assert len(ON.POLICY_ERAS) >= DECLARED_DEPTH["eras"]
    for row in ON.POLICY_ERAS:
        lo = date.fromisoformat(str(row["start"]))
        hi = date.fromisoformat(str(row["end"]))
        assert hi >= lo, f"{row['name']}: reversed dates"
        assert row["why_it_matters"] and row["markers"] and row["regime"]
        assert row["status"] in ("SETTLED", "OPEN")
    blob = " ".join(" ".join(r["markers"]) for r in ON.POLICY_ERAS)
    for must in ("2023-03-25", "2020-03-07", "2019-05-02", "2024-12-08", "2023-02-07"):
        assert must in blob, f"the era table does not carry the dated marker {must}"
    shut = [r for r in ON.POLICY_ERAS if "Kurdistan" in str(r["name"])]
    assert shut and shut[0]["start"] == "2023-03-25"


def test_positioning_absences_are_declared_rather_than_silently_missing() -> None:
    unavailable = [r for r in ON.POSITIONING_SOURCES if not r["available"]]
    assert len(unavailable) >= 3
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in unavailable)
    assert any("MIRROR" in str(r["pit_warning"]) for r in unavailable), (
        "the Syrian absence must name its lawful substitute")
    assert ON.COT_CURRENCY == ""
    for row in ON.POSITIONING_SOURCES:
        assert row["why"] and row["pit_warning"]


def test_the_ramadan_window_drifts_about_eleven_days_a_year() -> None:
    assert ON.in_ramadan(date(2025, 3, 10))
    assert not ON.in_ramadan(date(2025, 5, 10))
    assert ON.RAMADAN_WINDOWS[2026][2] == "PROJECTED"
    starts = [ON.RAMADAN_WINDOWS[y][0] for y in (2024, 2025, 2026)]
    for lo, hi in pairwise(starts):
        drift = (lo + timedelta(days=365)) - hi
        assert 9 <= drift.days <= 13, f"the Hijri drift should be about eleven days, got {drift}"
