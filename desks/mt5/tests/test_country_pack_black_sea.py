"""THE BLACK SEA PACK, VALIDATED -- the corridor, the potash route and two absent currencies.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A TWO-COUNTRY PACK THAT ANSWERS FOR ONE. `JURISDICTIONS` is what the parity fence counts, so
    it is checked against the desk's OWN forest roster and against the fence's own reader -- not
    against a list somebody typed here -- and each jurisdiction must own at least six actors and
    four domains of its own rather than borrowing the other's.
  * A UKRAINIAN PACK READ ONLY IN UKRAINIAN, OR ONLY IN ENGLISH. Ukraine's grain trade writes in
    Ukrainian AND Russian, Belarus's statute book is Belarusian and its state wire is Russian.
    The script assertions below are what keep all three honest, and they use LETTERS THAT EXIST
    IN ONLY ONE of the three (yi/ye/ghe for Ukrainian, u-short for Belarusian) rather than a
    language guess.
  * A SYMBOL THE BOX CANNOT TRADE. Every executable instrument and every edge target is checked
    against the broker's OWN registry. UAH and BYN are absent and must stay transmission targets.
  * A SINGLE-NAME EQUITY ON A DOCKET. The two-lane order (2026-09-06) forbids hunting one
    statistically, and this pack is full of tempting national champions -- Kernel, MHP,
    Belaruskali, Naftan, ArcelorMittal Kryvyi Rih -- which appear only as ACTORS.
  * A PACK THAT REACHES THE FRAMEWORK BENT. `CountryPack` coerces every row; a coercion note is
    a field the framework could not read, and this pack must produce none.
  * A CALENDAR SOMEBODY TYPED. Ukraine rewrote its holiday law in 2023 and Belarus keeps a
    movable Orthodox feast; the tests check that the break is in the table and that Radunitsa is
    DERIVED from the paschalion rather than typed.
  * CELLS THAT ARE A CARTESIAN BLOW-UP OF NOTHING. Every cell must name a real condition the
    pack's own data plane can evaluate, on a symbol the box can quote.
"""
from __future__ import annotations

import importlib
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from countries import (  # type: ignore[import-not-found]  # noqa: E402
    check_pack,
    get,
    holiday_table,
    resolve,
    universe_symbols,
)
from countries.black_sea import pack as BS  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as FO  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")
TUPLE_FIELDS = ("forced_to", "information", "constraints", "instruments", "counterparties",
                "observables")


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it, resolved through `resolve_pack` so the test measures
    the same object the country lab runs and not a private construction."""
    got = CL.resolve_pack("black_sea")
    assert got is not None, "no Black Sea pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(BS.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == "black_sea"
    assert str(get(built, "region_command")) == "russia_cis"
    assert str(get(built, "currency")) == "UAH"
    assert BS.CURRENCIES == {"ua": "UAH", "by": "BYN"}, (
        "both currencies must be declared; the framework carries one field and the pack may not "
        "let one jurisdiction be silently represented by the other's money")


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    """A coercion note is a field `CountryPack` could not read. There must be none."""
    notes = list(getattr(built, "coercion_notes", ()) or ())
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on this pack: {fatal[:4]}"
    assert CL.validate_pack(built) == [], "validate_pack found non-fatal problems too"


# ------------------------------------------------------------------------------ jurisdictions
def test_jurisdictions_are_exactly_the_two_countries_claimed() -> None:
    """`JURISDICTIONS` is what the parity fence counts, so it is checked against the desk's own
    forest roster rather than against a list typed in this test file."""
    assert BS.JURISDICTIONS == ("ua", "by")
    assert all(c == c.lower() and len(c) == 2 for c in BS.JURISDICTIONS)
    assert len(set(BS.JURISDICTIONS)) == len(BS.JURISDICTIONS)
    for code in BS.JURISDICTIONS:
        assert FO.forest_of_country(code) == "russia_cis", (
            f"{code} is not on the russia_cis forest's roster in libs/research/forests.py")


def test_the_parity_fence_reads_both_jurisdictions_from_this_pack() -> None:
    """The fence's own reader, not a reimplementation of it: a pack that declares nothing is
    credited with ONE country, which is exactly the hole this pack exists to close."""
    crp = importlib.import_module("scripts.check_regional_parity")
    codes, how = crp.jurisdictions_of("black_sea")
    assert set(codes) == {"ua", "by"}, f"the fence reads {codes} from this pack"
    assert "JURISDICTIONS" in how, f"the fence fell back to {how!r} instead of the declaration"


def test_each_jurisdiction_owns_its_own_actors_and_domains() -> None:
    """A multi-country pack that answers for one country and borrows the other's evidence is a
    single-country pack with a longer name."""
    actors = Counter(str(a["jurisdiction"]) for a in BS.ACTORS)
    domains = Counter(str(d["jurisdiction"]) for d in BS.DOMAINS)
    for code in BS.JURISDICTIONS:
        assert actors[code] >= 6, f"{code} owns only {actors[code]} actors"
        assert domains[code] >= 4, f"{code} owns only {domains[code]} domains"
    assert actors["joint"] >= 2 and domains["joint"] >= 2, (
        "a two-country pack with no JOINT domain is two packs in one file")
    assert set(actors) | set(domains) <= {"ua", "by", "joint"}


# ------------------------------------------------------------------------------ depth
def test_pack_reaches_parity_depth(built: Any) -> None:
    """The standing depth rule, measured by the framework and not claimed by the pack."""
    row = RP.pack_depth(built, "black_sea").as_row()
    assert row["score"] == 1.0, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_depth_counts_sit_at_the_multi_jurisdiction_size_and_not_at_the_floor() -> None:
    """Twelve actors is the single-country floor; a two-country pack written to it is one
    country read twice."""
    assert len(BS.ACTORS) >= 16
    assert len(BS.DOMAINS) >= 12
    assert len(BS.TRANSMISSION_EDGES_SEED) >= 10
    assert len(BS.DATASETS) >= 16
    assert len(BS.SOURCE_CLASSES) >= 20
    assert len(BS.POLICY_ERAS) >= 6
    assert BS.term_count() >= 120


def test_all_ten_source_layers_are_populated_or_declared_absent() -> None:
    """The principal's depth rule: ten layers, none of them blank."""
    counts = BS.layer_counts()
    assert set(counts) == set(BS.SOURCE_LAYERS)
    blank = [layer for layer, n in counts.items() if not n]
    assert blank == [], f"blank layers: {blank}"
    coverage = BS.source_layer_coverage()
    assert coverage["n_layers_covered"] == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], (
        "nothing is registered machine-use-forbidden, which is implausible for a pack whose "
        "potash and Black Sea FOB prices live behind price-reporting-agency paywalls")
    assert coverage["low_weight_kept"], "no fringe or unreliable ground is kept at all"
    gaps = {(g["jurisdiction"], g["layer"]) for g in BS.JURISDICTION_LAYER_GAPS}
    assert len(gaps) >= 3, "a two-country pack with no per-jurisdiction gap has not looked"
    for juris, layer in gaps:
        assert juris in BS.JURISDICTIONS
        assert layer in BS.SOURCE_LAYERS
    for row in BS.JURISDICTION_LAYER_GAPS:
        assert len(str(row["reason"])) > 80, "a declared gap with no reason is a blank"


def test_every_source_carries_three_independent_labels_a_root_and_a_query() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in BS.SOURCE_CLASSES:
        assert row["access_label"] in BS.ACCESS_LABELS
        assert row["credibility"] in BS.CREDIBILITY_LABELS
        assert row["predictive_state"] in BS.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no native-language query"
        assert row["roots"], f"{row['id']} has no crawlable root"
        assert row["layer"] in BS.SOURCE_LAYERS
        assert all(str(r).startswith("http") for r in row["roots"]), row["id"]


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(BS.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert set(BS.EXECUTABLE_INSTRUMENTS) <= set(registry)
    assert len(BS.EXECUTABLE_INSTRUMENTS) >= 18


def test_every_domain_and_edge_terminates_in_a_tradable_symbol() -> None:
    """A domain or seed that terminates in a symbol the box cannot quote can never compile."""
    execs = set(BS.EXECUTABLE_INSTRUMENTS)
    for dom in BS.DOMAINS:
        split = resolve(dom["instruments"])
        assert split["absent"] == [], f"domain {dom['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"domain {dom['id']} -> equity {split['equities']}"
        assert set(dom["instruments"]) <= execs, dom["id"]
    for seed in BS.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"
        assert str(seed["target"]) in seed["targets"]


def test_the_hryvnia_and_the_belarusian_ruble_are_named_absent() -> None:
    """Neither currency is quoted here and the pack says so with what carries each instead."""
    registry = universe_symbols()
    assert not {"USDUAH", "EURUAH", "UAH", "USDBYN", "EURBYN", "BYN"} & set(registry)
    named = " ".join(str(t["name"]) for t in BS.TRANSMISSION_TARGETS)
    for must in ("UAH", "BYN", "Potash", "TTF"):
        assert must in named, f"the pack does not name {must} as an absent leg"
    for row in BS.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == [], row["name"]
    assert len(BS.TRANSMISSION_TARGETS) >= 10


def test_no_single_name_equity_appears_anywhere_a_cell_could_reach() -> None:
    """The national champions are all over this pack as ACTORS and must reach no instrument."""
    blob = " ".join(str(a["name"]) for a in BS.ACTORS)
    assert "Belaruskali" in blob and "Kernel" in blob, (
        "the champions should be present AS ACTORS; if they are gone the test is measuring "
        "nothing")
    everywhere = set(BS.EXECUTABLE_INSTRUMENTS)
    for dom in BS.DOMAINS:
        everywhere |= set(dom["instruments"])
    for seed in BS.TRANSMISSION_EDGES_SEED:
        everywhere |= set(seed["targets"])
    for actor in BS.ACTORS:
        everywhere |= set(actor["instruments"])
    for row in BS.CELLS:
        everywhere.add(str(row["symbol"]))
    assert resolve(sorted(everywhere))["equities"] == []
    assert resolve(sorted(everywhere))["absent"] == []


# ------------------------------------------------------------------------------ the languages
def test_terminology_carries_ukrainian_belarusian_and_russian() -> None:
    """Three orthographies, detected by letters that exist in only one of them."""
    assert len(BS.terms_for(BS.has_ukrainian)) >= 12, "too little Ukrainian-only vocabulary"
    assert len(BS.terms_for(BS.has_belarusian)) >= 10, "too little Belarusian-only vocabulary"
    assert len(BS.terms_for(BS.has_russian)) >= 8, (
        "Russian is declared a native language of BOTH jurisdictions and the pack must carry it")
    assert len(BS.terms_for(BS.has_cyrillic)) >= 140
    flat = {t for group in BS.TERMINOLOGY.values() for t in group}
    for must in ("зерновий коридор", "облікова ставка", "морський коридор",
                 "калійныя ўгнаенні", "кошык валют", "Радуніца", "транзит газу"):
        assert must in flat, f"the Black Sea pack does not carry {must!r}"
    assert BS.has_ukrainian("Національний банк України")
    assert not BS.has_ukrainian("official rate") and not BS.has_ukrainian("курс")
    assert BS.has_belarusian("калійныя ўгнаенні") and not BS.has_belarusian("potash")
    assert BS.has_cyrillic("экспорт") and not BS.has_cyrillic("export")
    assert set(BS.TERMINOLOGY) == {d["id"] for d in BS.DOMAINS}, (
        "every domain owes a vocabulary and no vocabulary may name a domain that does not exist")


def test_the_layers_are_queried_in_the_scripts_their_ground_is_written_in() -> None:
    """A query in English finds an English article about the release, not the release."""
    terms = BS.layer_terms()
    cyr = [layer for layer, qs in terms.items() if any(BS.has_cyrillic(q) for q in qs)]
    assert len(cyr) == 10, f"only {cyr} carry a Cyrillic query"
    uk = [layer for layer, qs in terms.items() if any(BS.has_ukrainian(q) for q in qs)]
    be = [layer for layer, qs in terms.items() if any(BS.has_belarusian(q) for q in qs)]
    assert len(uk) >= 6, f"only {uk} carry a Ukrainian-only query"
    assert len(be) >= 4, f"only {be} carry a Belarusian-only query"
    native = sum(1 for row in BS.SOURCE_CLASSES if row["machine_use_allowed"]
                 for q in row["queries"] if BS.has_cyrillic(q))
    assert native >= 100, f"only {native} Cyrillic queries across the crawlable sources"


def test_query_territories_give_the_deep_forest_miner_three_phrases_per_layer() -> None:
    """The addendum's native search territories: every live layer, at least three phrases."""
    assert set(BS.QUERY_TERRITORIES) == set(BS.SOURCE_LAYERS)
    for layer, phrases in BS.QUERY_TERRITORIES.items():
        assert len(phrases) >= 3, f"{layer}: only {len(phrases)} phrases"
        assert any(BS.has_cyrillic(p) for p in phrases), f"{layer}: no native-script phrase"
    be = [name for name, v in BS.QUERY_TERRITORIES.items()
          if any(BS.has_belarusian(p) for p in v)]
    assert len(be) >= 4, f"only {be} carry a Belarusian-only search phrase"


# ------------------------------------------------------------------------------ the calendars
def test_the_holiday_table_resolves_for_three_years_and_every_date_is_in_its_year() -> None:
    for year in (2024, 2025, 2026):
        table = holiday_table(BS.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        assert all(("UA:" in label or "BY:" in label) for label in table.values()), (
            "every union row must say WHICH jurisdiction closes")
    assert str(BS.HOLIDAYS_RULE["rule"]).strip(), "a table with no rule cannot be extended"
    assert "3258" in str(BS.HOLIDAYS_RULE["authority"]) + str(BS.HOLIDAYS_RULE["rule"])


def test_ukraine_moved_christmas_to_25_december_in_2023() -> None:
    """The dated fact a pack exists to hold: Law No. 3258-IX of 2023-07-14 rewrote Article 73."""
    for year in (2024, 2025, 2026):
        ua = BS.ua_national_holidays(year)
        assert date(year, 12, 25) in ua, f"25 December missing from the {year} Ukrainian table"
        assert date(year, 1, 7) not in ua, (
            f"7 January is NOT a Ukrainian statutory holiday in {year}; it was abolished in 2023")
        assert date(year, 3, 8) not in ua and date(year, 5, 1) not in ua, (
            "the Soviet-era 8 March and 1 May were abolished by the same law")
        assert date(year, 5, 8) in ua and date(year, 9, 5) not in ua
        assert date(year, 7, 15) in ua, "Statehood Day moved from 28 July to 15 July"
        assert date(year, 10, 1) in ua, "Defenders' Day moved from 14 October to 1 October"
    pre = BS.ua_national_holidays(2022)
    assert date(2022, 1, 7) in pre and date(2022, 3, 8) in pre and date(2022, 5, 9) in pre, (
        "the pre-2023 calendar must survive, or the break cannot be dated from the pack")
    assert BS.orthodox_easter(2022) in pre, "Easter was a Ukrainian non-working day before 2023"


def test_belarus_kept_its_calendar_and_radunitsa_is_derived_not_typed() -> None:
    """Radunitsa is the ninth day after Orthodox Pascha and is always a Tuesday."""
    for year, easter, rad in ((2024, date(2024, 5, 5), date(2024, 5, 14)),
                              (2025, date(2025, 4, 20), date(2025, 4, 29)),
                              (2026, date(2026, 4, 12), date(2026, 4, 21))):
        assert BS.orthodox_easter(year) == easter
        assert BS.radunitsa(year) == rad
        assert rad.weekday() == 1, "Radunitsa falls on a Tuesday by construction"
        by = BS.by_national_holidays(year)
        assert rad in by and date(year, 1, 7) in by and date(year, 12, 25) in by
        assert date(year, 9, 17) in by, "Day of People's Unity is non-working from 2024"
    assert date(2023, 9, 17) not in BS.by_national_holidays(2023), (
        "17 September was not yet a non-working day in 2023")
    with pytest.raises(ValueError, match="1900-2099"):
        BS.orthodox_easter(2200)


def test_the_two_calendars_now_coincide_on_almost_nothing() -> None:
    """The measurement that makes XX-C a domain: since 2023 the two share two closed days."""
    joint = sorted(BS.joint_closure_days(2026))
    assert joint == [date(2026, 1, 1), date(2026, 12, 25)], joint
    asym = BS.asymmetric_closure_days(2026)
    assert len(asym) >= 12, "the asymmetry is the sample and it must be large enough to study"
    assert date(2026, 1, 7) in asym and date(2026, 7, 15) in asym
    assert not (set(joint) & set(asym)), "a day cannot be both joint and asymmetric"
    assert BS.is_market_holiday(date(2026, 1, 7)) and not BS.is_market_holiday(date(2026, 1, 8))


# ------------------------------------------------------------------- the mechanism functions
def test_the_corridor_regime_state_dates_every_black_sea_era() -> None:
    """Mechanism function one: which export regime was in force on a date."""
    assert BS.corridor_regime(date(2021, 6, 1)) == "PREWAR"
    assert BS.corridor_regime(date(2022, 3, 15)) == "PORTS_CLOSED"
    assert BS.corridor_regime(date(2022, 9, 1)) == "BSGI"
    assert BS.corridor_regime(date(2023, 7, 17)) == "BSGI", "the termination day is still BSGI"
    assert BS.corridor_regime(date(2023, 8, 1)) == "GAP"
    assert BS.corridor_regime(date(2024, 3, 1)) == "UKRAINIAN_CORRIDOR"
    assert BS.corridor_regime(date(1990, 1, 1)) == "UNMEASURED", (
        "outside the declared span the answer is UNMEASURED, never a guess (L1.28a)")
    assert BS.corridor_regime_note(date(2022, 9, 1)).startswith("the Black Sea Grain")
    events = BS.bsgi_event_dates("SETTLED")
    assert len(events) == 8 and events == sorted(events)
    assert date(2022, 10, 29) in events and date(2023, 7, 17) in events
    assert all(BS.corridor_regime(d) in ("BSGI", "PORTS_CLOSED") for d in events)


def test_the_hryvnia_regime_returns_the_fix_so_a_study_can_refuse_it() -> None:
    """Mechanism function two: a fixed number is not a price, and the function says which."""
    assert BS.uah_regime(date(2021, 6, 1)) == ("FLOATING_MANAGED", None)
    assert BS.uah_regime(date(2022, 3, 1)) == ("FIXED_PREDEVALUATION", 29.2549)
    assert BS.uah_regime(date(2022, 7, 20)) == ("FIXED_PREDEVALUATION", 29.2549)
    assert BS.uah_regime(date(2022, 7, 21)) == ("FIXED_POSTDEVALUATION", 36.5686)
    assert BS.uah_regime(date(2023, 10, 3)) == ("MANAGED_FLEXIBILITY", None)
    assert BS.uah_regime(date(1990, 1, 1)) == ("UNMEASURED", None)
    pre, post = BS.uah_regime(date(2022, 7, 20))[1], BS.uah_regime(date(2022, 7, 21))[1]
    assert pre is not None and post is not None
    assert 0.24 < (post - pre) / pre < 0.26, "the 2022-07-21 step is about a 25% devaluation"


def test_the_belarusian_basket_weights_are_published_and_sum_to_one() -> None:
    """The pack's central Belarusian claim: the coefficients are announced, not estimated."""
    for lo, _hi, weights, status in BS.BASKET_ERAS:
        assert abs(sum(weights.values()) - 1.0) < 1e-9, f"{lo}: weights do not sum to 1"
        assert status in ("SETTLED", "DECLARED_VERIFY")
        assert "RUB" in weights, f"{lo}: a basket with no rouble leg is not this basket"
    assert BS.byn_basket_weights(date(2019, 1, 1)) == {"RUB": 0.50, "USD": 0.30, "EUR": 0.20}
    assert BS.implied_rub_beta(date(2019, 1, 1)) == 0.50
    assert BS.implied_rub_beta(date(2023, 1, 1)) == 0.60
    assert "CNY" in BS.byn_basket_weights(date(2023, 1, 1))
    assert BS.byn_basket_status(date(2023, 1, 1)) == "DECLARED_VERIFY", (
        "the 2022 recomposition carries no NBRB resolution number and must stay unpromotable")
    assert BS.byn_basket_weights(date(1990, 1, 1)) == {}
    assert BS.implied_rub_beta(date(1990, 1, 1)) == 0.0


def test_kyiv_and_minsk_run_on_different_clocks_for_five_months_a_year() -> None:
    """Kyiv keeps EU summer time; Minsk has been fixed UTC+3 since 2014."""
    assert BS.utc_offset_hours("by", date(2025, 1, 15)) == 3
    assert BS.utc_offset_hours("by", date(2025, 7, 15)) == 3
    assert BS.utc_offset_hours("ua", date(2025, 1, 15)) == 2
    assert BS.utc_offset_hours("ua", date(2025, 7, 15)) == 3
    assert BS.utc_offset_hours("zz", date(2025, 7, 15)) == 0
    assert BS.utc_offset_hours("ua", date(2025, 3, 29)) == 2, "the Saturday before the switch"
    assert BS.utc_offset_hours("ua", date(2025, 3, 30)) == 3, "the last Sunday of March"
    assert BS.utc_offset_hours("ua", date(2025, 10, 26)) == 2, "the last Sunday of October"
    days = BS.clock_divergence_days(2025)
    assert 90 <= len(days) <= 130, f"{len(days)} divergence weekdays is not five months"
    assert all(d.weekday() < 5 for d in days)
    assert all(d.month in (1, 2, 3, 10, 11, 12) for d in days)
    windows = {w["name"]: w for w in BS.SESSION_WINDOWS}
    assert windows["bs_kyiv_morning_winter"]["start_utc"] == "06:00"
    assert windows["bs_kyiv_morning_summer"]["start_utc"] == "05:00"


def test_the_import_ban_dates_are_press_reported_and_unpromotable() -> None:
    """The desk may generate hypotheses off an unverified date and may never promote one."""
    assert all(st == "PRESS_REPORTED" for *_rest, st in BS.IMPORT_BAN_EVENTS)
    dates = BS.import_ban_dates()
    assert len(dates) == len(BS.IMPORT_BAN_EVENTS) and dates == sorted(dates)
    assert date(2023, 5, 2) in dates and date(2023, 9, 15) in dates
    blob = " ".join(str(c["constraint"]) + str(c["measured"]) + str(c["consequence"])
                    for c in BS.ACCESS_CONSTRAINTS)
    assert "PRESS_REPORTED" in blob
    assert "may PROMOTE nothing" in blob


# ------------------------------------------------------------------------------ the cells
def test_cells_are_real_conditions_on_symbols_the_box_can_quote() -> None:
    """The addendum: maximise CELLS, honestly. A cell must name a condition this pack's own
    data plane can evaluate, on a symbol the broker quotes."""
    rows = BS.cells()
    assert rows == BS.CELLS
    assert 60 <= len(rows) <= 260, f"{len(rows)} cells is outside the honest range"
    assert len({r["cell_id"] for r in rows}) == len(rows), "duplicate cell ids"
    domain_ids = {d["id"] for d in BS.DOMAINS}
    for row in rows:
        for field in ("cell_id", "domain", "symbol", "condition", "mechanism_family", "horizon",
                      "control", "why"):
            assert str(row[field]).strip(), f"{row['cell_id']}: {field} is empty"
        assert row["domain"] in domain_ids
        assert row["cell_id"].startswith("black_sea:")
    assert resolve(sorted({str(r["symbol"]) for r in rows}))["absent"] == []
    per_domain = BS.cells_by_domain()
    assert set(per_domain) == domain_ids, "a domain that mints no cell is decorative"
    assert min(per_domain.values()) >= 6


def test_datasets_carry_every_field_a_collector_needs() -> None:
    """The addendum asks for >= 14 datasets, each fetchable by somebody who was not here."""
    assert len(BS.DATASETS) >= 16
    names = [str(d["name"]) for d in BS.DATASETS]
    assert len(set(names)) == len(names), "a dataset declared twice"
    for row in BS.DATASETS:
        for field in ("name", "source", "coverage", "frequency", "revisions", "licence",
                      "history_from", "assets", "mechanism_families", "how_to_fetch"):
            assert row[field], f"{row['name']}: {field} is empty"
        assert float(row["publication_lag_days"]) >= 0.0
        assert isinstance(row["pit_feasible"], bool)
        assert len(str(row["how_to_fetch"])) > 60, (
            f"{row['name']}: how_to_fetch must be concrete enough for a collector")
        assert resolve(row["assets"])["absent"] == [], row["name"]
    layers_named = " ".join(str(d["source"]) for d in BS.DATASETS)
    assert "UN" in layers_named and "USDA" in layers_named and "Comtrade" in layers_named


def test_interactions_name_real_sibling_packs_and_tradable_seams() -> None:
    """This is how the desk stops testing each country in isolation."""
    assert len(BS.INTERACTIONS) >= 4
    here = Path(BS.__file__).resolve().parent.parent
    for row in BS.INTERACTIONS:
        code = str(row["with"])
        assert (here / code / "pack.py").is_file(), (
            f"interaction names a pack that is not on disk: {code}")
        assert code != "black_sea"
        for field in ("mechanism", "observable", "control"):
            assert len(str(row[field])) > 60, f"{code}: {field} is a stub"
        assert row["targets"], code
        assert resolve(row["targets"])["absent"] == [], code
        assert resolve(row["targets"])["equities"] == [], code
    named = {str(r["with"]) for r in BS.INTERACTIONS}
    assert {"ru", "pl", "cee_balkans", "tr"} <= named, (
        f"the neighbouring packs this one must not duplicate are missing from {named}")


# ------------------------------------------------------------------------------ actors/domains
def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    seen: set[str] = set()
    for row in BS.ACTORS:
        name = str(row["name"])
        assert name not in seen, f"actor {name} declared twice"
        seen.add(name)
        for f in ACTOR_FIELDS:
            assert row.get(f), f"actor {name!r} has an empty {f}"
        # a one-element tuple written without its trailing comma silently becomes a string, and
        # `tuple("abc")` is then three characters -- this catches that class of typo
        for f in TUPLE_FIELDS:
            value = row[f]
            assert isinstance(value, tuple), f"actor {name!r}.{f} is not a tuple"
            assert all(len(str(v)) > 2 for v in value), (
                f"actor {name!r}.{f} looks like a string split into characters -- a "
                f"single-element tuple needs its trailing comma")
        assert resolve(row["instruments"])["equities"] == [], name
        assert len(str(row["falsifier"])) > 60, f"actor {name!r} has a stub falsifier"


def test_every_domain_has_objects_two_controls_and_a_conditioning_state() -> None:
    """Without a control an effect cannot be told from the desk's own sampling."""
    ids = [str(d["id"]) for d in BS.DOMAINS]
    assert len(set(ids)) == len(ids)
    for row in BS.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert row["conditions"], f"domain {row['id']} names no conditioning state"
        assert row["instruments"], f"domain {row['id']} names no instrument"
        assert str(row["family"]).strip() and str(row["horizon"]).strip()


def test_policy_eras_are_dated_ordered_and_named() -> None:
    for era in BS.POLICY_ERAS:
        lo = date.fromisoformat(str(era["start"]))
        hi = date.fromisoformat(str(era["end"]))
        assert lo < hi, era["name"]
        assert era["markers"] and era["why_it_matters"]
        assert era["status"] in ("SETTLED", "OPEN")
    names = [str(e["name"]) for e in BS.POLICY_ERAS]
    assert len(set(names)) == len(names)


def test_access_constraints_state_the_lawfulness_position_in_the_packs_own_data() -> None:
    """The sanctions position is DATA a miner can read, not prose in a docstring."""
    blob = " ".join(str(c["constraint"]) + str(c["measured"]) + str(c["consequence"])
                    for c in BS.ACCESS_CONSTRAINTS)
    assert "SANCTIONS CONSTRAIN TRANSACTIONS" in blob
    assert "broker symbols only" in blob
    for must in ("machine_use_allowed=false", "UNMEASURED", "Comtrade", "TTF"):
        assert must in blob, f"the pack does not state {must!r} in its access constraints"
    assert len(BS.ACCESS_CONSTRAINTS) >= 8
    for row in BS.ACCESS_CONSTRAINTS:
        for field in ("constraint", "measured", "consequence"):
            assert len(str(row[field])) > 30, row["constraint"]


def test_cot_is_declared_absent_rather_than_silently_missing() -> None:
    """No UAH or BYN contract exists anywhere. An absence a study can trip over must be named."""
    rows = [r for r in BS.POSITIONING_SOURCES if not r["available"]]
    assert rows, "the COT question is not answered anywhere in the pack"
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in rows)
    assert BS.COT_CURRENCY == ""
    for row in BS.POSITIONING_SOURCES:
        assert str(row["why"]).strip() and str(row["pit_warning"]).strip()


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {"custom:bsgi_event_windows", "custom:corridor_regime_split",
                        "custom:import_ban_events", "custom:uah_regime_break",
                        "custom:byn_basket_residual", "custom:potash_route_break",
                        "custom:calendar_asymmetry", "custom:transmission_seeds"}
    assert all(callable(fn) for fn in got.values())


def test_custom_miner_rows_name_known_domains_and_match_the_miners_module() -> None:
    """The two registrations -- CUSTOM_MINERS and MINERS -- must be one set."""
    from countries.black_sea import miners as M
    ids = {d["id"] for d in BS.DOMAINS}
    entries = set()
    for row in BS.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.black_sea.miners", row["entry"]
        assert callable(getattr(M, func)), f"{row['entry']} does not resolve"
        entries.add(func)
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    assert entries == set(M.MINERS)
    for dids in BS.MINER_DOMAINS.values():
        assert set(dids) <= ids


def test_mine_returns_a_report_and_emits_nothing_without_a_ctx() -> None:
    """The department entry: pure Python, no network, and NOTHING recorded when ctx is None."""
    report = BS.mine(None)
    assert report["code"] == "black_sea"
    assert tuple(report["jurisdictions"]) == ("ua", "by")
    assert report["emitted"] == 0, "mine(None) must record nothing anywhere"
    assert report["cells_emitted"] == len(BS.CELLS) >= 60
    assert len(report["rows"]) == len(BS.TRANSMISSION_EDGES_SEED)
    assert all(r["kind"] == "transmission_seed" for r in report["rows"])
    assert report["unmeasured"] and all(len(u) > 40 for u in report["unmeasured"])
    assert date.fromisoformat(str(report["at"])[:10]).year >= 2024
    assert report["n_actors"] == len(BS.ACTORS)
    assert report["n_interactions"] == len(BS.INTERACTIONS)


def test_mine_records_one_row_per_edge_when_a_ctx_is_handed_in() -> None:
    """With a ctx it goes through `record` and nowhere else, once per declared edge."""
    calls: list[dict[str, Any]] = []

    class _Ctx:
        def record(self, **fields: Any) -> tuple[str, bool]:
            calls.append(fields)
            return "dry-run", False

    report = BS.mine(_Ctx())
    assert report["emitted"] == len(BS.TRANSMISSION_EDGES_SEED)
    assert len(calls) == len(BS.TRANSMISSION_EDGES_SEED)
    for call in calls:
        assert call["mechanism"].startswith("black_sea_transmission:")
        assert call["source_id"] == "black_sea:edges"
        assert resolve(call["assets"])["absent"] == []
        assert call["falsifier"]
