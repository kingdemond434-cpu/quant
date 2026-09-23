"""THE ICELAND PACK, VALIDATED -- a water year, a fish quota, a capital control and a volcano.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A KRONA THAT IS QUIETLY PROXIED. ISK is absent from the broker registry. EURNOK and EURSEK
    are in this pack as CONTROLS for a North Atlantic factor, and the tests check that the pack
    says so rather than treating them as stand-ins for a currency the desk cannot trade.
  * A POOLED ISK STUDY. `capital_controls_state(day)` returns the regime and
    `controls_invalidate(start, end)` names the boundaries a sample spans. A krona series that
    crosses 2008-11-28 or 2017-03-14 is two different objects with one name.
  * A PACK THAT IS AN ENGLISH GLOSSARY OF AN ICELANDIC-SPEAKING COUNTRY. Icelandic fisheries
    science, the met office, the statute book and the whole official record are published in
    Icelandic first. The script assertions below are what keep the terminology and every source
    class's queries honest.
  * A PADDED LAYER. A country of 390,000 people has no retail margin-statistics ecology. The
    pack DECLARES that layer absent with the reason, and these tests check the declaration
    exists, is the only one, and still leaves parity depth at 1.0 -- because a measured refusal
    is worth more than a padded row (L1.28a).
  * A CALENDAR SOMEBODY TYPED. Iceland's two weekday rules -- the first Thursday AFTER 18 April
    and the first Monday of August -- exist in no other country's statute, and 2024 is the year
    the first of them is most often got wrong because 18 April was itself a Thursday.
"""
from __future__ import annotations

import importlib
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

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as F  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

#: `is` IS A PYTHON KEYWORD, so this department cannot be reached with an import statement and
#: is loaded the way the framework itself loads it. The directory name is the ISO-2 code and the
#: parity fence reads it, so renaming the package to dodge the keyword would break the fence.
IS: Any = importlib.import_module("countries.is.pack")

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")


class FakeCtx:
    """The smallest thing that looks like a `country_lab.LabCtx` to a pack miner: it collects
    what a miner would have emitted so the test can assert on it WITHOUT a registry."""

    def __init__(self) -> None:
        self.code = "is"
        self.dry_run = True
        self.unmeasured: list[str] = []
        self.transmission_seeds: list[dict[str, Any]] = []
        self.bars = None

    def note(self, what: str, why: str) -> None:
        self.unmeasured.append(f"{what}: {why}")

    def seed_transmission(self, **row: Any) -> None:
        self.transmission_seeds.append(dict(row))


@pytest.fixture(scope="module")
def built() -> Any:
    got = CL.resolve_pack("is")
    assert got is not None, "no Iceland pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    assert check_pack(IS.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == "is"
    assert str(get(built, "region_command")) == "europe"
    assert str(get(built, "currency")) == "ISK"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    notes = list(getattr(built, "coercion_notes", ()) or [])
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on this pack: {fatal[:4]}"


def test_jurisdictions_are_declared_and_the_off_roster_gap_is_measured() -> None:
    """THE PARITY FENCE READS `JURISDICTIONS`. Iceland is NOT on any Forest.countries roster --
    which is a measurement about the desk's own machinery, not an error in this pack, and it is
    recorded here rather than fixed by editing another department's roster from a country pack."""
    assert IS.JURISDICTIONS == ("is",)
    assert all(c == c.lower() and len(c) == 2 for c in IS.JURISDICTIONS)
    roster = {c.lower() for f in F.FORESTS.values() for c in f.countries}
    for code in IS.JURISDICTIONS:
        if code in roster:
            continue
        assert code in IS.OFF_ROSTER_JURISDICTIONS, (
            f"{code} is neither on the forests roster nor declared OFF_ROSTER with a reason")
        assert len(IS.OFF_ROSTER_JURISDICTIONS[code]) > 80, (
            "an off-roster declaration with no reason is a blank, not a measurement")
    assert set(IS.OFF_ROSTER_JURISDICTIONS) <= set(IS.JURISDICTIONS)
    assert "forests" in IS.OFF_ROSTER_JURISDICTIONS["is"]


def test_pack_reaches_parity_depth_with_one_layer_declared_absent(built: Any) -> None:
    """A DECLARED ABSENCE COUNTS AS MAPPED. That is the whole point: naming the layer Iceland
    does not have must not cost the pack its depth score."""
    row = RP.pack_depth(built, "is").as_row()
    assert row["score"] == 1.0, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    assert row["layers_mapped"] >= 1, "the declared absence must reach the framework as MAPPED"
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_depth_counts_sit_above_the_floor_and_not_on_it() -> None:
    assert len(IS.ACTORS) >= 14
    assert len(IS.DOMAINS) >= 13
    assert len(IS.TRANSMISSION_EDGES_SEED) >= 11
    assert len(IS.SOURCE_CLASSES) >= 20
    assert len(IS.DATASETS) >= 14
    assert len(IS.POLICY_ERAS) >= 8
    assert IS.term_count() >= 100


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    for row in IS.ACTORS:
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
    ids = set()
    for row in IS.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert row["conditions"], f"domain {row['id']} names no conditioning state"
        assert row["id"] not in ids, f"domain {row['id']} declared twice"
        ids.add(row["id"])


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(IS.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert set(IS.EXECUTABLE_INSTRUMENTS) <= set(registry)
    assert "XALUSD" in IS.EXECUTABLE_INSTRUMENTS, (
        "aluminium is the symbol Iceland's whole power economy reaches")


def test_the_krona_is_named_absent_and_is_never_proxied() -> None:
    """ISK IS NOT A BROKER SYMBOL. The pack routes it and says what EURNOK and EURSEK are FOR."""
    registry = universe_symbols()
    assert not {"EURISK", "USDISK", "GBPISK", "ISK"} & set(registry)
    first = IS.TRANSMISSION_TARGETS[0]
    assert "ISK" in str(first["name"])
    assert "never proxied" in str(first["why"]).lower()
    for row in IS.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == []
    named = " ".join(str(t["name"]) for t in IS.TRANSMISSION_TARGETS)
    assert "OMXI15" in named and "aflandskronur" in named


def test_every_transmission_seed_names_tradable_targets() -> None:
    for seed in IS.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"


def test_domain_instruments_are_tradable_and_never_a_single_name() -> None:
    for row in IS.DOMAINS:
        split = resolve(row["instruments"])
        assert split["absent"] == [], f"domain {row['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"domain {row['id']} -> equity {split['equities']}"


# ------------------------------------------------------------------------------ the language
def test_terminology_is_icelandic_and_not_an_english_glossary() -> None:
    flat = {t for group in IS.TERMINOLOGY.values() for t in group}
    assert len(IS.TERMINOLOGY) >= 13
    assert IS.term_count() >= 100
    assert set(flat) == set(IS.icelandic_terms()), (
        "some terminology rows are neither Icelandic-lettered nor Icelandic vocabulary: "
        f"{sorted(set(flat) - set(IS.icelandic_terms()))[:6]}")
    special = [t for t in flat if IS.has_icelandic_letter(t)]
    assert len(special) >= 60, f"only {len(special)} terms carry an Icelandic letter"
    for must in ("loðna", "loðnukvóti", "þorskkvóti", "fjármagnshöft", "sérstök bindiskylda",
                 "miðlunarlón", "Þórisvatn", "Hálslón", "verðtrygging", "eldgos",
                 "gengisvísitala", "lífeyrissjóðir"):
        assert must in flat, f"the Iceland pack does not carry {must!r}"
    assert IS.has_icelandic_letter("þorskur") and IS.has_icelandic_letter("Hálslón")
    assert not IS.has_icelandic_letter("aluminium smelter")
    assert IS.is_icelandic("aflamark") and not IS.is_icelandic("quarterly earnings")


def test_every_source_carries_three_labels_a_root_and_an_icelandic_query() -> None:
    for row in IS.SOURCE_CLASSES:
        assert row["access_label"] in IS.ACCESS_LABELS
        assert row["credibility"] in IS.CREDIBILITY_LABELS
        assert row["predictive_state"] in IS.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        if str(row["id"]).startswith("absent_"):
            assert "DECLARED ABSENT" in str(row["notes"])
            continue
        assert row["queries"], f"{row['id']} has no native-language query"
        assert row["roots"], f"{row['id']} has no crawlable root"
        assert any(IS.is_icelandic(q) for q in row["queries"]), (
            f"{row['id']} carries no Icelandic query at all -- it reads the English corner")


def test_nine_layers_are_sourced_and_one_is_declared_absent_with_its_reason() -> None:
    """A BLANK LAYER IS WORK NOT DONE; A DECLARED ABSENCE IS A MEASUREMENT (L1.28a)."""
    counts = IS.layer_counts()
    assert set(counts) == set(IS.SOURCE_LAYERS)
    blank = [layer for layer, n in counts.items() if not n]
    assert blank == ["retail_ecology"], f"unexpected blank layers: {blank}"
    coverage = IS.source_layer_coverage()
    assert coverage["n_layers_covered"] == 9
    assert coverage["n_layers_declared"] == 10
    assert coverage["unexplained_missing"] == [], (
        "a blank layer with no reason is the one thing the depth rule forbids")
    assert coverage["declared_absent"] == ["retail_ecology"]
    reason = IS.LAYER_ABSENCES["retail_ecology"]
    for marker in ("no Iceland-domiciled CFD", "retail-leverage", "2017-03-14"):
        assert marker in reason, f"the absence reason does not name {marker!r}"
    # and the absence must reach the framework as a row, not as a silence
    absent_rows = [s for s in IS.SOURCE_CLASSES if str(s["id"]).startswith("absent_")]
    assert len(absent_rows) == 1
    assert absent_rows[0]["layer"] == "retail_ecology"
    assert absent_rows[0]["machine_use_allowed"] is False


def test_query_territories_cover_every_sourced_layer_in_icelandic() -> None:
    """Three phrases per layer, in Icelandic, for every layer that is not declared absent."""
    expected = set(IS.SOURCE_LAYERS) - set(IS.LAYER_ABSENCES)
    assert set(IS.QUERY_TERRITORIES) == expected, (
        f"missing: {sorted(expected - set(IS.QUERY_TERRITORIES))}; "
        f"unexpected: {sorted(set(IS.QUERY_TERRITORIES) - expected)}")
    assert "retail_ecology" not in IS.QUERY_TERRITORIES, (
        "there is no ground to search in a layer the pack declared absent")
    for layer, phrases in IS.QUERY_TERRITORIES.items():
        assert len(phrases) >= 3, f"{layer} has only {len(phrases)} query phrases"
        assert all(IS.is_icelandic(p) for p in phrases), (
            f"{layer} carries a non-Icelandic phrase: "
            f"{[p for p in phrases if not IS.is_icelandic(p)]}")


def test_machine_use_forbidden_ground_is_registered_and_never_dropped() -> None:
    coverage = IS.source_layer_coverage()
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible for a country "
        "whose exchange tape and professional data product both forbid it")
    for sid in coverage["machine_use_forbidden"]:
        row = next(s for s in IS.SOURCE_CLASSES if s["id"] == sid)
        assert row["roots"] or str(sid).startswith("absent_"), (
            "a registered-but-unfetched source still needs its root recorded")


# ------------------------------------------------------------------------------ the calendars
def test_the_holiday_table_resolves_for_all_three_years() -> None:
    assert "Sumardagurinn fyrsti" in IS.HOLIDAYS_RULE["rule"]
    for year in (2024, 2025, 2026):
        table = holiday_table(IS.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        assert f"{year}-01-01" in table and f"{year}-06-17" in table and f"{year}-05-01" in table


def test_easter_is_computed_and_hangs_seven_closures_off_itself() -> None:
    assert IS.easter_sunday(2024) == date(2024, 3, 31)
    assert IS.easter_sunday(2025) == date(2025, 4, 20)
    assert IS.easter_sunday(2026) == date(2026, 4, 5)
    for year in (2024, 2025, 2026):
        table = IS.national_holidays(year)
        easter = IS.easter_sunday(year)
        for offset in (-3, -2, 0, 1, 39, 49, 50):
            assert easter + timedelta(days=offset) in table, (
                f"Easter+{offset} missing from the {year} table")


# ------------------------------------------------------------------ MECHANISM FUNCTION ONE
def test_the_two_icelandic_weekday_rules_are_computed_not_typed() -> None:
    """Sumardagurinn fyrsti is the first Thursday AFTER 18 April -- 'after' is STRICT, which is
    why 2024 (when 18 April was itself a Thursday) lands on the 25th and not the 18th. Fridagur
    verslunarmanna is the first Monday of August. Neither rule exists in any other calendar on
    this desk."""
    assert IS.sumardagurinn_fyrsti(2024) == date(2024, 4, 25)
    assert IS.sumardagurinn_fyrsti(2025) == date(2025, 4, 24)
    assert IS.sumardagurinn_fyrsti(2026) == date(2026, 4, 23)
    for year in range(2020, 2036):
        got = IS.sumardagurinn_fyrsti(year)
        assert got.weekday() == 3, f"{year}: not a Thursday"
        assert got > date(year, 4, 18), f"{year}: 'after 18 April' is strict"
        assert (got - date(year, 4, 18)).days <= 7
        assert got in IS.national_holidays(year)
    assert IS.fridagur_verslunarmanna(2024) == date(2024, 8, 5)
    assert IS.fridagur_verslunarmanna(2025) == date(2025, 8, 4)
    assert IS.fridagur_verslunarmanna(2026) == date(2026, 8, 3)
    for year in range(2020, 2036):
        got = IS.fridagur_verslunarmanna(year)
        assert got.weekday() == 0 and got.day <= 7, f"{year}: not the first Monday of August"
        assert got in IS.national_holidays(year)


def test_iceland_keeps_no_daylight_saving_and_the_pack_says_so() -> None:
    """Every Icelandic session is FIXED IN UTC all year while every European counterpart's moves
    twice -- so there is deliberately no summer twin of the cash-session window."""
    names = {w["name"] for w in IS.SESSION_WINDOWS}
    assert "is_cash_session" in names
    assert not any(n.endswith("_summer") for n in names)
    assert "no daylight saving" in str(IS.CENTRAL_BANK["dst_rule"]).lower()
    assert "NO DAYLIGHT SAVING" in str(IS.HOLIDAYS_RULE["clock_note"]).upper()
    cash = next(w for w in IS.SESSION_WINDOWS if w["name"] == "is_cash_session")
    assert cash["start_utc"] == "09:30" and cash["end_utc"] == "15:30"


# ------------------------------------------------------------------ MECHANISM FUNCTION TWO
def test_the_hydrological_year_is_a_function_and_it_bounds_the_smelters() -> None:
    """The reservoirs fill on melt from May to September and trough in March and April; a
    calendar-year slice cuts every water year in half, and curtailment is the contractual
    mechanism by which a dry winter becomes less metal."""
    assert IS.hydrological_year_phase(date(2025, 7, 15)) == "FILLING"
    assert IS.hydrological_year_phase(date(2025, 5, 1)) == "FILLING"
    assert IS.hydrological_year_phase(date(2025, 9, 30)) == "FILLING"
    assert IS.hydrological_year_phase(date(2025, 11, 20)) == "DRAWDOWN"
    assert IS.hydrological_year_phase(date(2025, 1, 15)) == "DRAWDOWN"
    assert IS.hydrological_year_phase(date(2025, 3, 20)) == "TROUGH"
    assert IS.hydrological_year_phase(date(2025, 4, 30)) == "TROUGH"
    assert IS.hydrological_year_phase(date(2024, 2, 29)) == "DRAWDOWN", "a leap day is a date too"
    # the water year starts with the melt, not with January
    assert IS.hydrological_year(date(2025, 3, 1)) == "2024/2025"
    assert IS.hydrological_year(date(2025, 6, 1)) == "2025/2026"
    # and the curtailment episodes are dated, two of them recent
    assert IS.curtailment_state(date(2022, 2, 1)) == "CURTAILED"
    assert IS.curtailment_state(date(2024, 3, 1)) == "CURTAILED"
    assert IS.curtailment_state(date(2019, 3, 1)) == "NORMAL"
    assert len(IS.CURTAILMENT_EPISODES) >= 3
    assert {r["native"] for r in IS.HYDRO_RESERVOIRS} == {"Þórisvatn", "Hálslón"}


# ------------------------------------------------------------------ MECHANISM FUNCTION THREE
def test_the_capital_control_eras_are_a_function_that_invalidates_pooled_studies() -> None:
    """A krona series that crosses these boundaries is two different objects with one name, and
    `controls_invalidate` exists so a study has to LOOK rather than assume."""
    assert IS.capital_controls_state(date(2005, 1, 1)) == "FLOAT_INFLATION_TARGET"
    assert IS.capital_controls_state(date(2008, 10, 15)) == "COLLAPSE"
    assert IS.capital_controls_state(date(2010, 1, 1)) == "CONTROLS"
    assert IS.capital_controls_state(date(2016, 7, 1)) == "SRR_40"
    assert IS.capital_controls_state(date(2017, 6, 1)) == "CONTROLS_LIFTED"
    assert IS.capital_controls_state(date(2018, 12, 1)) == "SRR_20"
    assert IS.capital_controls_state(date(2020, 1, 1)) == "SRR_0"
    assert IS.capital_controls_state(date(1995, 1, 1)) == "PRE_FLOAT"
    # the special reserve requirement: a numeric, dated tax on carry inflows
    assert IS.srr_rate(date(2015, 1, 1)) is None
    assert IS.srr_rate(date(2016, 7, 1)) == pytest.approx(40.0)
    assert IS.srr_rate(date(2018, 12, 1)) == pytest.approx(20.0)
    assert IS.srr_rate(date(2019, 6, 1)) == pytest.approx(0.0)
    assert [r for _d, r, _s in IS.SRR_SCHEDULE] == [40.0, 20.0, 0.0]
    # and the boundary detector
    assert IS.controls_invalidate(date(2018, 1, 1), date(2018, 6, 1)) == []
    spanned = IS.controls_invalidate(date(2007, 1, 1), date(2020, 1, 1))
    assert "CONTROLS" in spanned and "CONTROLS_LIFTED" in spanned and len(spanned) >= 5
    assert IS.OFFSHORE_AUCTION[0] == date(2016, 6, 16)


def test_the_fishing_year_and_the_capelin_clock_are_computed() -> None:
    """1 September to 31 August, and four dated advisory windows inside a calendar year."""
    assert IS.fishing_year(date(2025, 9, 1)) == "2025/2026"
    assert IS.fishing_year(date(2025, 8, 31)) == "2024/2025"
    assert IS.fishing_year_start(2025) == date(2025, 9, 1)
    cal = IS.capelin_calendar(2025)
    assert len(cal) == 4
    assert [w["date"].month for w in cal] == [6, 10, 1, 2]
    decisions = [w for w in cal if w["is_decision"]]
    assert len(decisions) == 2, "the January survey and the February allocation are the decisions"
    assert IS.CAPELIN_ZERO_SEASONS == ("2018/2019", "2019/2020")
    assert "PRESS_REPORTED" in IS.CAPELIN_ZERO_STATUS


def test_the_eruption_record_carries_its_own_control() -> None:
    """ASH AND WIND ARE THE MECHANISM, NOT MAGNITUDE: 2011 was larger than 2010 and closed
    almost nothing, which is the control built into the domain."""
    assert IS.reykjanes_state(date(2020, 1, 1)) == "PRE_REYKJANES_SEQUENCE"
    assert IS.reykjanes_state(date(2024, 1, 1)) == "REYKJANES_ACTIVE"
    dates = [d for d, _w, _s in IS.ERUPTIONS]
    assert date(2010, 4, 14) in dates and date(2011, 5, 21) in dates
    assert date(2023, 11, 10) in dates, "the Grindavik evacuation is a dated event"
    assert len(IS.eruption_events(date(2021, 1, 1))) >= 4
    assert len(IS.eruption_events(date(2021, 1, 1))) < len(IS.ERUPTIONS)
    assert IS.AVIATION_COLOUR_CODES[-1] == "RED"


def test_tourism_is_seasonal_and_the_shocks_are_dated() -> None:
    assert IS.keflavik_season(date(2025, 7, 1)) == "PEAK"
    assert IS.keflavik_season(date(2025, 5, 1)) == "SHOULDER"
    assert IS.keflavik_season(date(2025, 11, 1)) == "LOW"
    assert IS.tourism_shock_state(date(2020, 6, 1)) == "SHOCK"
    assert IS.tourism_shock_state(date(2023, 6, 1)) == "NORMAL"


def test_cot_is_declared_absent_rather_than_silently_missing() -> None:
    absent = [r for r in IS.POSITIONING_SOURCES if not r["available"]]
    assert absent, "the COT question is not answered anywhere in the pack"
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in absent)
    assert IS.COT_CURRENCY == ""


# ------------------------------------------------------------------------------ the cells
def test_the_pack_mints_a_real_cell_lattice() -> None:
    cells = IS.cells()
    assert 60 <= len(cells) <= 400, f"{len(cells)} cells is outside the honest range"
    assert len(cells) == len(IS.CELLS)
    ids = [c["cell_id"] for c in cells]
    assert len(ids) == len(set(ids)), "duplicate cell ids"
    domain_ids = {d["id"] for d in IS.DOMAINS}
    for c in cells:
        assert set(c) == {"cell_id", "domain", "symbol", "condition", "mechanism_family",
                          "horizon", "control", "why"}
        assert c["domain"] in domain_ids
        assert c["symbol"] in IS.EXECUTABLE_SET
        assert c["condition"] and c["control"] and c["horizon"] and c["mechanism_family"]
    assert {c["domain"] for c in cells} == domain_ids, "a domain mints no cells at all"
    assert any(c["symbol"] == "XALUSD" for c in cells), "the aluminium plane mints no cells"


def test_datasets_are_deep_and_fetchable() -> None:
    assert len(IS.DATASETS) >= 14
    for ds in IS.DATASETS:
        assert len(str(ds["how_to_fetch"])) > 40, (
            f"{ds['name']}: how_to_fetch is not concrete enough for a collector")
        assert ds["assets"] and resolve(ds["assets"])["absent"] == []
        assert ds["mechanism_families"]
        assert float(ds["publication_lag_days"]) >= 0.0
    assert any(ds["pit_feasible"] for ds in IS.DATASETS)
    assert any(not ds["pit_feasible"] for ds in IS.DATASETS), (
        "every dataset claims point-in-time feasibility, which is implausible")


def test_interactions_name_other_packs_with_a_mechanism_and_a_control() -> None:
    assert len(IS.INTERACTIONS) >= 4
    withs = [row["with"] for row in IS.INTERACTIONS]
    assert len(withs) == len(set(withs))
    assert {"no", "ca", "au"} <= set(withs), (
        "the aluminium and fisheries planes need Norway, Canada and Australia")
    for row in IS.INTERACTIONS:
        assert row["mechanism"] and row["observable"] and row["control"] and row["why"]
        assert row["targets"] and resolve(row["targets"])["absent"] == []


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert len(got) == len(IS.CUSTOM_MINERS)
    assert all(callable(fn) for fn in got.values())


def test_custom_miner_rows_name_known_domains_and_match_the_miners_table() -> None:
    ids = {d["id"] for d in IS.DOMAINS}
    entries = set()
    for row in IS.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.is.pack", row["entry"]
        assert callable(getattr(IS, func)), f"{row['entry']} does not resolve"
        entries.add(func)
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    assert entries == set(IS.MINERS)
    for dids in IS.MINER_DOMAINS.values():
        assert set(dids) <= ids


def test_mine_returns_a_report_and_emits_nothing_without_a_context() -> None:
    report = IS.mine(None)
    assert report["code"] == "IS"
    assert report["jurisdictions"] == ("is",)
    assert report["off_roster"] == ("is",)
    assert report["dry_run"] is True
    assert report["cells_emitted"] == len(IS.cells())
    assert report["emitted"] == len(report["rows"]) > 0
    assert report["at"].endswith("+00:00"), "the stamp must be timezone-aware UTC"
    assert report["layers_absent"] == ("retail_ecology",)
    assert any("DECLARED ABSENT" in u for u in report["unmeasured"]), (
        "the absent layer must be carried into the report as a measurement, not a silence")


def test_mine_emits_its_seeds_through_a_context_when_one_is_given() -> None:
    ctx = FakeCtx()
    report = IS.mine(ctx)
    assert report["emitted"] > 0
    assert len(ctx.transmission_seeds) == len(IS.TRANSMISSION_EDGES_SEED)
    assert {s["id"] for s in ctx.transmission_seeds} == {
        e["id"] for e in IS.TRANSMISSION_EDGES_SEED}
    assert ctx.unmeasured, "nothing was noted UNMEASURED, which hides the missing tape"
