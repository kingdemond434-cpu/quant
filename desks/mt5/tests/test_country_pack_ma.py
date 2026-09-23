"""THE MOROCCO PACK, VALIDATED -- the basket, the band, the phosphate and the Ramadan clock.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A PACK THAT IS A FRENCH GLOSSARY OF AN ARABIC-SPEAKING COUNTRY. Morocco's decrees and its
    popular press are in Arabic, its central bank and its bourse work in French, and Tamazight
    is an official language with its own national holiday since 2024. A crawler handed only one
    of the three reads one third of the country, so the script assertions below are what keep
    the terminology honest in all three.
  * A SYMBOL THE BOX CANNOT TRADE. Every executable instrument and every transmission target is
    checked against the broker's OWN registry, not against a list somebody typed. The dirham is
    absent and must stay a transmission target.
  * A SINGLE-NAME EQUITY ON A DOCKET. The two-lane order (2026-09-06) forbids hunting one
    statistically, and this pack is full of tempting national champions (OCP, COSUMAR,
    Attijariwafa) which appear only as ACTORS.
  * A PACK THAT REACHES THE FRAMEWORK BENT. `CountryPack` coerces every row; a coercion note is
    a field the framework could not read, and this pack must produce none.
  * A LAYER NOBODY LOOKED AT. The principal's depth rule requires all ten source layers sourced
    or declared absent with a reason, and `regional_parity.pack_depth` must score 1.0.
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
    resolve,
    universe_symbols,
)
from countries.ma import pack as MA  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it. Resolved through `resolve_pack` so the test measures
    the same object the country lab runs, not a private construction."""
    got = CL.resolve_pack("ma")
    assert got is not None, "no Morocco pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(MA.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == "ma"
    assert str(get(built, "region_command")) == "mea"
    assert str(get(built, "currency")) == "MAD"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    """A coercion note is a field `CountryPack` could not read. There must be none."""
    notes = list(getattr(built, "coercion_notes", ()) or ())
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on this pack: {fatal[:4]}"


def test_pack_reaches_parity_depth(built: Any) -> None:
    """The standing depth rule, measured by the framework and not claimed by the pack."""
    row = RP.pack_depth(built, "ma").as_row()
    assert row["score"] == 1.0, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_depth_counts_sit_at_the_regions_parity_and_not_at_the_floor() -> None:
    """Twelve actors is the floor; a country written to the floor is a country half-read."""
    assert len(MA.ACTORS) >= 13
    assert len(MA.DOMAINS) >= 13
    assert len(MA.TRANSMISSION_EDGES_SEED) >= 9
    assert len(MA.SOURCE_CLASSES) >= 19
    assert len(MA.DATASETS) >= 12
    assert len(MA.POLICY_ERAS) >= 5
    assert MA.term_count() >= 120


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
                f"actor {row.get('name')!r}.{f} looks like a string split into characters -- a "
                f"single-element tuple needs its trailing comma")


def test_every_domain_has_objects_and_two_negative_controls() -> None:
    """Without a control an effect cannot be told from the desk's own sampling."""
    for row in MA.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert row["conditions"], f"domain {row['id']} names no conditioning state"


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(MA.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert set(MA.EXECUTABLE_INSTRUMENTS) <= set(registry)


def test_every_transmission_seed_names_tradable_targets() -> None:
    """A seed that terminates in a symbol the box cannot quote can never compile a cell."""
    for seed in MA.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"


def test_the_dirham_is_named_absent_rather_than_quietly_dropped() -> None:
    """MAD is not quoted here and the pack says so with what carries it instead."""
    registry = universe_symbols()
    assert not {"USDMAD", "EURMAD", "MAD"} & set(registry)
    named = " ".join(str(t["name"]) for t in MA.TRANSMISSION_TARGETS)
    assert "MAD" in named and "MASI" in named
    for row in MA.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == []


# ------------------------------------------------------------------------------ the languages
def test_terminology_carries_arabic_french_and_tamazight() -> None:
    """Three scripts, because Morocco is read in three languages and a crawler handed one of
    them reads one third of the country."""
    assert len(MA.arabic_terms()) >= 60, f"only {len(MA.arabic_terms())} Arabic terms"
    assert len(MA.french_terms()) == len(MA.FRENCH_MARKERS), (
        f"missing French working vocabulary: "
        f"{sorted(set(MA.FRENCH_MARKERS) - set(MA.french_terms()))}")
    assert len(MA.tifinagh_terms()) >= 4, "no Tifinagh vocabulary at all"
    flat = {t for group in MA.TERMINOLOGY.values() for t in group}
    for must in ("سعر الفائدة", "التضخم", "بنك المغرب", "الدرهم", "الفوسفاط", "سلة العملات",
                 "القمح اللين"):
        assert must in flat, f"the Morocco pack does not carry {must!r}"
    for must in ("taux directeur", "dirham", "campagne agricole", "barrage", "restitution"):
        assert must in flat, f"the Morocco pack does not carry {must!r}"
    assert MA.has_arabic("بنك المغرب") and not MA.has_arabic("Bank Al-Maghrib")
    assert MA.has_tifinagh("ⴰⴽⴰⵍ") and not MA.has_tifinagh("akal")
    assert len(MA.TERMINOLOGY) >= 13


def test_at_least_one_layers_queries_are_written_in_arabic_and_in_french() -> None:
    """A query in English finds an English article about the release, not the release."""
    terms = MA.layer_terms()
    arabic_layers = [layer for layer, qs in terms.items() if any(MA.has_arabic(q) for q in qs)]
    french_layers = [layer for layer, qs in terms.items()
                     if any(m in q for q in qs for m in ("cours de reference", "taux directeur",
                                                         "barrage", "Bulletin Officiel",
                                                         "adjudication", "campagne agricole"))]
    assert len(arabic_layers) >= 6, f"only {arabic_layers} carry an Arabic query"
    assert french_layers, "no layer carries a French working query"
    native = sum(1 for row in MA.SOURCE_CLASSES if row["machine_use_allowed"]
                 for q in row["queries"] if MA.has_arabic(q))
    assert native >= 25, f"only {native} Arabic-script queries across crawlable sources"


def test_every_source_carries_three_independent_labels_and_a_query() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in MA.SOURCE_CLASSES:
        assert row["access_label"] in MA.ACCESS_LABELS
        assert row["credibility"] in MA.CREDIBILITY_LABELS
        assert row["predictive_state"] in MA.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no native-language query"
        assert row["roots"], f"{row['id']} has no crawlable root"


def test_all_ten_source_layers_are_populated() -> None:
    """The principal's depth rule: ten layers, none of them blank."""
    counts = MA.layer_counts()
    assert set(counts) == set(MA.SOURCE_LAYERS)
    blank = [layer for layer, n in counts.items() if not n]
    assert blank == [], f"blank layers: {blank}"
    coverage = MA.source_layer_coverage()
    assert coverage["n_layers_covered"] == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible for a country "
        "whose phosphate price lives behind a price-reporting-agency paywall")
    assert coverage["low_weight_kept"], "no fringe ground is kept at all, so it was dropped"


# ------------------------------------------------------------------------------ the calendars
def test_throne_day_is_a_fixed_solar_date_a_human_can_check() -> None:
    """30 July is Fete du Trone in every year, and 2026-07-30 is in the resolved table."""
    from countries import holiday_table
    table = holiday_table(MA.HOLIDAYS_RULE, 2026)
    assert "2026-07-30" in table, "Throne Day missing from the 2026 table"
    assert "Trone" in table["2026-07-30"] or "العرش" in table["2026-07-30"]
    for year in (2024, 2025, 2026):
        assert date(year, 7, 30) in MA.national_holidays(year)
        assert holiday_table(MA.HOLIDAYS_RULE, year), f"no holiday table for {year}"


def test_the_moon_sighted_feasts_are_declared_with_their_status() -> None:
    """A Hijri date is an ESTIMATE until the sighting, and Morocco often lands a day after the
    Gulf -- so the pack must label rather than compute them."""
    assert "sighting" in MA.HOLIDAYS_RULE["rule"].lower()
    assert "ESTIMATE" in str(MA.HOLIDAYS_RULE["status"][2026]).upper()
    announced_2025 = MA.announced_dates(2025)
    assert date(2025, 3, 31) in announced_2025, "Aid al-Fitr 2025 day 1 is 2025-03-31"
    assert all(st in ("ANNOUNCED", "PROJECTED")
               for rows in MA.LUNAR_HOLIDAYS.values() for *_, st in rows)
    assert all(st == "PROJECTED" for *_, st in MA.LUNAR_HOLIDAYS[2026]), (
        "a 2026 sighting cannot already be announced")


def test_the_amazigh_new_year_is_a_holiday_only_from_2024() -> None:
    """A closed day that did not exist before 2024 is a regime break a pooled study will miss."""
    assert (1, 14) in {(m, d) for m, d, _ in MA.FIXED_NATIONAL}
    assert any("ⵢⴻⵏⵏⴰⵢⴻⵔ" in name for _m, _d, name in MA.FIXED_NATIONAL)
    assert date(2024, 1, 14) in MA.DECLARED_CLOSURES


def test_the_ramadan_clock_moves_the_whole_moroccan_day() -> None:
    """Morocco keeps UTC+1 all year EXCEPT for Ramadan, when it returns to UTC+0."""
    assert MA.utc_offset_hours(date(2025, 1, 15)) == 1
    assert MA.utc_offset_hours(date(2025, 3, 10)) == 0, "2025-03-10 is inside the UTC+0 window"
    assert MA.utc_offset_hours(date(2025, 5, 10)) == 1
    lo, hi, status = MA.ramadan_clock_window(2025)
    assert lo == date(2025, 2, 23) and hi == date(2025, 4, 6) and status == "ANNOUNCED"
    assert MA.RAMADAN_CLOCK[2026][2] == "PROJECTED"
    assert all(lo.weekday() == 6 and hi.weekday() == 6
               for lo, hi, _ in MA.RAMADAN_CLOCK.values()), (
        "the clock decree runs Sunday to Sunday by construction")
    days = MA.gmt_window_weekdays(date(2025, 1, 1), date(2025, 12, 31))
    assert days and all(d.weekday() < 5 for d in days)
    assert all(MA.is_gmt_window(d) for d in days)
    # the two session windows are the same LOCAL hours an hour apart in UTC
    windows = {w["name"]: w for w in MA.SESSION_WINDOWS}
    assert windows["ma_bourse_standard"]["start_utc"] == "08:30"
    assert windows["ma_bourse_ramadan"]["start_utc"] == "09:30"


def test_the_duty_decrees_are_labelled_press_reported_and_not_cited() -> None:
    """The desk may generate hypotheses off an unverified date and may never promote one."""
    assert MA.DUTY_DECREES
    assert all(st == "PRESS_REPORTED" for *_, st in MA.DUTY_DECREES)
    assert len(MA.duty_switch_dates()) == len(MA.DUTY_DECREES)
    blob = " ".join(str(c["consequence"]) for c in MA.ACCESS_CONSTRAINTS)
    assert "PRESS_REPORTED" in " ".join(str(c["measured"]) + str(c["consequence"])
                                        for c in MA.ACCESS_CONSTRAINTS) or "BO" in blob
    boundary = MA.campaign_boundary_days(date(2023, 1, 1), date(2024, 12, 31))
    assert boundary and all(d.month in MA.CAMPAIGN_BOUNDARY_MONTHS for d in boundary)


def test_cot_is_declared_absent_rather_than_silently_missing() -> None:
    """No MAD contract exists anywhere. An absence a study can trip over must be named."""
    rows = {r["name"]: r for r in MA.POSITIONING_SOURCES}
    cot = [r for r in rows.values() if not r["available"]]
    assert cot, "the COT question is not answered anywhere in the pack"
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in cot)


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {"custom:bam_conseil_windows", "custom:basket_band_pressure",
                        "custom:advance_tender_week", "custom:cereal_duty_switch",
                        "custom:ramadan_clock_shift", "custom:transmission_seeds"}
    assert all(callable(fn) for fn in got.values())


def test_custom_miner_rows_name_known_domains_and_match_the_miners_module() -> None:
    """The two registrations -- CUSTOM_MINERS and MINERS -- must be one set."""
    from countries.ma import miners as M
    ids = {d["id"] for d in MA.DOMAINS}
    entries = set()
    for row in MA.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.ma.miners", row["entry"]
        assert callable(getattr(M, func)), f"{row['entry']} does not resolve"
        entries.add(func)
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    assert entries == set(M.MINERS)
    for did in MA.MINER_DOMAINS.values():
        assert set(did) <= ids
