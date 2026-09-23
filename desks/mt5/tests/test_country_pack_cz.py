"""THE CZECHIA PACK, VALIDATED -- the floor, the hedged reserves and the German limb.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A PACK THAT IS AN ENGLISH GLOSSARY OF A CZECH-SPEAKING COUNTRY. Czech is a Latin script
    with its own letters, which makes the failure invisible: a crawler handed de-accented terms
    reads "kurzovy zavazek" and never finds "kurzový závazek", and a crawler handed English
    reads the Reuters summary of a CNB decision and never the decision. The script assertions
    below are what keep the terminology and every crawlable source's queries honest.
  * A SYMBOL THE BOX CANNOT TRADE. Every executable instrument, every domain instrument and
    every transmission target is checked against the broker's OWN registry, not against a list
    somebody typed.
  * A SINGLE-NAME EQUITY ON A DOCKET. The two-lane order (2026-09-06) forbids hunting one
    statistically, and this pack is full of tempting national champions -- Škoda, ČEZ, Komerční
    banka, Erste -- which appear only as ACTORS.
  * A PACK THAT REACHES THE FRAMEWORK BENT. `CountryPack` coerces every row; a coercion note is
    a field the framework could not read, and this pack must produce none.
  * A LAYER NOBODY LOOKED AT. The depth rule requires all ten source layers sourced or declared
    absent with a reason, and `regional_parity.pack_depth` must score 1.0.
  * A HOLIDAY TABLE SOMEBODY TYPED. Both Czech Easter holidays are DERIVED with the anonymous
    Gregorian algorithm, and the tests check the algorithm against three known Easter Sundays
    rather than against the table it produced.
  * A CELL COUNT THAT IS A CARTESIAN BLOW-UP. Every minted cell must name a domain, an
    executable symbol and a condition that domain actually declares.
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
from countries.cz import pack as CZ  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as F  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")
TUPLE_FIELDS = ("forced_to", "information", "constraints", "instruments", "counterparties",
                "observables")


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it, resolved through `resolve_pack` so the test measures
    the same object the country lab runs and not a private construction."""
    got = CL.resolve_pack("cz")
    assert got is not None, "no Czechia pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(CZ.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == "cz"
    assert str(get(built, "region_command")) == "europe"
    assert str(get(built, "currency")) == "CZK"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    """A coercion note is a field `CountryPack` could not read. There must be none."""
    notes = list(getattr(built, "coercion_notes", ()) or ())
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on this pack: {fatal[:4]}"


def test_jurisdictions_are_declared_and_on_the_desks_own_roster() -> None:
    """THE PARITY FENCE COUNTS THIS TUPLE. It must be lowercase ISO-2 and every code must be a
    country the desk's own forest roster names -- never a claim about a country nobody hunts."""
    assert CZ.JURISDICTIONS == ("cz",)
    assert all(c == c.lower() and len(c) == 2 for c in CZ.JURISDICTIONS)
    roster = {g.lower() for f in F.FORESTS.values() for g in (f.grounds or ())}
    roster |= {c.lower() for f in F.FORESTS.values() for c in (f.countries or ())}
    for code in CZ.JURISDICTIONS:
        assert code in roster, f"{code} is on no forest's roster in libs/research/forests.py"
    assert F.forest_of_country("cz") == "europe"


def test_pack_reaches_parity_depth(built: Any) -> None:
    """The standing depth rule, measured by the framework and not claimed by the pack."""
    row = RP.pack_depth(built, "cz").as_row()
    assert row["score"] == 1.0, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_depth_counts_sit_above_the_floor_and_not_on_it() -> None:
    """Twelve actors is the floor; a country written to the floor is a country half-read."""
    assert len(CZ.ACTORS) >= 14
    assert len(CZ.DOMAINS) >= 13
    assert len(CZ.TRANSMISSION_EDGES_SEED) >= 10
    assert len(CZ.SOURCE_CLASSES) >= 20
    assert len(CZ.DATASETS) >= 14
    assert len(CZ.POLICY_ERAS) >= 5
    assert len(CZ.INTERACTIONS) >= 4
    assert CZ.term_count() >= 100


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    for row in CZ.ACTORS:
        for f in ACTOR_FIELDS:
            assert row.get(f), f"actor {row.get('name')!r} has an empty {f}"
        # a one-element tuple written without its trailing comma silently becomes a string, and
        # `tuple("abc")` is then three characters -- this catches that class of typo
        for f in TUPLE_FIELDS:
            value = row[f]
            assert isinstance(value, tuple), f"actor {row.get('name')!r}.{f} is not a tuple"
            assert all(len(str(v)) > 2 for v in value), (
                f"actor {row.get('name')!r}.{f} looks like a string split into characters -- a "
                f"single-element tuple needs its trailing comma")


def test_every_domain_has_objects_and_two_negative_controls() -> None:
    """Without a control an effect cannot be told from the desk's own sampling."""
    ids = set()
    for row in CZ.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert row["conditions"], f"domain {row['id']} names no conditioning state"
        assert row["mechanism_family"], f"domain {row['id']} names no mechanism family"
        assert row["horizon"], f"domain {row['id']} names no horizon"
        assert row["id"] not in ids, f"domain {row['id']} declared twice"
        ids.add(row["id"])


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(CZ.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert {"EURCZK", "USDCZK"} <= set(CZ.EXECUTABLE_INSTRUMENTS), (
        "the koruna IS directly quoted by this broker and both legs must be executable -- that "
        "is what makes this pack high-yield")


def test_every_domain_instrument_is_executable_so_every_cell_can_be_filled() -> None:
    """A domain instrument outside the executable list mints a cell nothing can ever compile."""
    execs = set(CZ.EXECUTABLE_INSTRUMENTS)
    for row in CZ.DOMAINS:
        missing = [s for s in row["instruments"] if s not in execs]
        assert missing == [], f"domain {row['id']} names non-executable {missing}"
        assert resolve(row["instruments"])["equities"] == []


def test_every_transmission_seed_names_tradable_targets() -> None:
    """A seed that terminates in a symbol the box cannot quote can never compile a cell."""
    for seed in CZ.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"


def test_absent_instruments_are_named_rather_than_quietly_dropped() -> None:
    """The PX, the state bonds, PRIBOR and the day-ahead power price are not quoted here and the
    pack says so with what carries each of them instead."""
    registry = set(universe_symbols())
    assert not {"PX", "PRIBOR", "CZGB"} & registry
    named = " ".join(str(t["name"]) for t in CZ.TRANSMISSION_TARGETS)
    for must in ("PX", "PRIBOR", "OTE", "state bonds"):
        assert must in named, f"the pack does not name {must!r} as an absent instrument"
    for row in CZ.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == []


def test_the_interactions_name_real_packs_and_tradable_targets() -> None:
    """The desk stops testing each country in isolation here: every interaction names another
    pack on disk, a mechanism, an observable, a control and EXECUTABLE targets."""
    from countries import codes
    on_disk = set(codes())
    assert len(CZ.INTERACTIONS) >= 4
    for row in CZ.INTERACTIONS:
        assert row["with"] in on_disk, f"interaction names unknown pack {row['with']!r}"
        assert row["mechanism"] and row["observable"] and row["control"]
        assert resolve(row["targets"])["absent"] == []
        assert resolve(row["targets"])["equities"] == []
    assert {"pl", "ea", "ru", "uk"} <= {r["with"] for r in CZ.INTERACTIONS}


# ------------------------------------------------------------------------------ the language
def test_terminology_is_written_in_czech_and_not_in_de_accented_mush() -> None:
    """Czech is a Latin script with its own letters, which makes this failure invisible unless
    it is asserted: every domain group must carry at least one genuinely Czech term."""
    assert len(CZ.TERMINOLOGY) >= 13
    assert CZ.term_count() >= 100
    for group, terms in CZ.TERMINOLOGY.items():
        assert any(CZ.has_czech(t) for t in terms), f"{group} carries no Czech diacritic at all"
    unique = [t for t in CZ.czech_terms() if CZ.has_czech_unique(t)]
    assert len(unique) >= 25, f"only {len(unique)} terms carry ř, ě or ů"
    flat = {t for group in CZ.TERMINOLOGY.values() for t in group}
    for must in ("Česká národní banka", "kurzový závazek", "devizové rezervy",
                 "průmyslová produkce", "index spotřebitelských cen", "Velký pátek",
                 "aukce státních dluhopisů", "denní trh s elektřinou"):
        assert must in flat, f"the Czechia pack does not carry {must!r}"
    assert CZ.has_czech("koruna oslabila") is False
    assert CZ.has_czech("měnová politika") and CZ.has_czech_unique("přeshraniční")


def test_every_layers_queries_are_written_in_czech() -> None:
    """A query in English finds an English article about the release, not the release."""
    terms = CZ.layer_terms()
    czech_layers = [layer for layer, qs in terms.items() if any(CZ.has_czech(q) for q in qs)]
    assert len(czech_layers) >= 9, f"only {czech_layers} carry a Czech query"
    native = sum(1 for row in CZ.SOURCE_CLASSES if row["machine_use_allowed"]
                 for q in row["queries"] if CZ.has_czech(q))
    assert native >= 60, f"only {native} Czech-script queries across crawlable sources"


def test_query_territories_cover_all_ten_layers_in_czech() -> None:
    """The deep-forest miner expands a layer with these, which is the half of discovery a fixed
    root list cannot do. Three per layer is the floor and every one must be Czech."""
    assert set(CZ.QUERY_TERRITORIES) == set(CZ.SOURCE_LAYERS)
    for layer, phrases in CZ.QUERY_TERRITORIES.items():
        assert len(phrases) >= 3, f"{layer} has only {len(phrases)} query territories"
        czech = [p for p in phrases if CZ.has_czech(p)]
        assert len(czech) >= 3, f"{layer} has only {len(czech)} CZECH query territories"


def test_every_source_carries_three_independent_labels_and_a_query() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in CZ.SOURCE_CLASSES:
        assert row["access_label"] in CZ.ACCESS_LABELS
        assert row["credibility"] in CZ.CREDIBILITY_LABELS
        assert row["predictive_state"] in CZ.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no native-language query"
        assert row["roots"], f"{row['id']} has no crawlable root"


def test_all_ten_source_layers_are_populated_and_none_is_silently_blank() -> None:
    """The depth rule: ten layers, each with a source or named ABSENT with a reason."""
    counts = CZ.layer_counts()
    assert set(counts) == set(CZ.SOURCE_LAYERS)
    blank = [layer for layer, n in counts.items() if not n]
    assert blank == [], f"blank layers: {blank}"
    coverage = CZ.source_layer_coverage()
    assert coverage["n_layers_covered"] == 10
    assert coverage["unexplained_missing"] == []
    assert CZ.LAYER_ABSENCES == {}, (
        "Czechia is an open-data EU member state with a digitised gazette and a public "
        "statistical API; declaring a layer absent here would be a false measurement")
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible for a country "
        "whose forward power and carbon curves live behind a price-reporting-agency paywall")
    assert coverage["low_weight_kept"], "no fringe ground is kept at all, so it was dropped"


# ------------------------------------------------------------------------------ the calendars
def test_easter_is_computed_and_not_typed() -> None:
    """The anonymous Gregorian algorithm, checked against three Easter Sundays a human knows."""
    assert CZ.easter_sunday(2024) == date(2024, 3, 31)
    assert CZ.easter_sunday(2025) == date(2025, 4, 20)
    assert CZ.easter_sunday(2026) == date(2026, 4, 5)
    assert CZ.easter_sunday(2027) == date(2027, 3, 28)


def test_the_holiday_table_resolves_for_all_three_years_and_stays_in_its_year() -> None:
    """Every date the rule produces must parse and must sit inside the year it is filed under."""
    for year in (2024, 2025, 2026):
        table = holiday_table(CZ.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        assert f"{year}-11-17" in table, "Den boje za svobodu a demokracii is a fixed solar date"
        assert f"{year}-12-24" in table, "Stedry den is a statutory closed day in Czechia"
    assert "2024-03-29" in holiday_table(CZ.HOLIDAYS_RULE, 2024)   # Velky patek
    assert "2025-04-21" in holiday_table(CZ.HOLIDAYS_RULE, 2025)   # Velikonocni pondeli
    assert "2026-04-03" in holiday_table(CZ.HOLIDAYS_RULE, 2026)   # Velky patek
    assert len(CZ.national_holidays(2026)) == 13, "eleven fixed days plus the Easter pair"


def test_good_friday_did_not_exist_before_2016() -> None:
    """A closed day that arrived in 2016 is a regime break a pooled study will silently miss."""
    assert CZ.easter_sunday(2015) - date(2015, 4, 3) == date(2015, 4, 5) - date(2015, 4, 3)
    assert date(2015, 4, 3) not in CZ.national_holidays(2015)
    assert date(2016, 3, 25) in CZ.national_holidays(2016)
    assert CZ.GOOD_FRIDAY_FROM == 2016


def test_weekend_holidays_are_lost_and_counted_as_such() -> None:
    """Czech law grants NO substitute day, so a Saturday holiday closes nothing -- the half of
    the calendar a naive closed-day count invents."""
    assert CZ.WEEKEND_SUBSTITUTION is False
    lost_2025 = CZ.lost_weekend_holidays(2025)
    assert lost_2025, "2025 has statutory days at the weekend and they must be named"
    assert all(d.weekday() >= 5 for d in lost_2025)
    assert not (set(lost_2025) & set(CZ.market_holidays(2025)))
    assert len(CZ.market_holidays(2025)) < len(CZ.national_holidays(2025))


def test_the_fixed_local_decision_minute_moves_in_utc_and_the_pack_computes_it() -> None:
    """THE CNB'S OWN MECHANISM FUNCTION. 14:30 Europe/Prague is 13:30 UTC in CET and 12:30 UTC
    in CEST; a pooled UTC event window is two windows averaged into one."""
    assert CZ.utc_offset_hours(date(2025, 1, 15)) == 1
    assert CZ.utc_offset_hours(date(2025, 7, 15)) == 2
    assert CZ.dst_start(2025) == date(2025, 3, 30)
    assert CZ.dst_end(2025) == date(2025, 10, 26)
    assert CZ.decision_minute_utc(date(2025, 2, 6)) == "13:30"
    assert CZ.decision_minute_utc(date(2025, 5, 7)) == "12:30"
    windows = {w["name"]: w for w in CZ.SESSION_WINDOWS}
    assert windows["cz_cnb_decision_cet"]["start_utc"] == "13:00"
    assert windows["cz_cnb_decision_cest"]["start_utc"] == "12:00"


def test_the_floor_era_is_a_mask_a_study_can_actually_apply() -> None:
    """THE PACK'S SECOND MECHANISM FUNCTION. The floor truncated EURCZK's distribution on one
    side, so every statistic spanning it is estimated on two random variables glued together."""
    assert CZ.FLOOR_REGIME["level_czk_per_eur"] == 27.00
    assert CZ.FLOOR_REGIME["announced"] == date(2013, 11, 7)
    assert CZ.FLOOR_REGIME["exited"] == date(2017, 4, 6)
    assert CZ.in_floor_era(date(2015, 6, 1)) is True
    assert CZ.in_floor_era(date(2013, 11, 7)) is True
    assert CZ.in_floor_era(date(2017, 4, 6)) is False
    assert CZ.in_floor_era(date(2012, 6, 1)) is False
    days = CZ.floor_era_days(date(2016, 1, 1), date(2016, 1, 31))
    assert days == [d for d in days if d.weekday() < 5]
    assert days[0] == date(2016, 1, 1) and days[-1] == date(2016, 1, 29)
    assert len(CZ.FLOOR_REGIME["what_it_invalidates"]) >= 4


def test_single_country_closures_exclude_the_shared_european_holidays() -> None:
    """A shared 25 December tells the desk nothing about Czechia; only the solo closures can."""
    solo = CZ.single_country_closures(2025)
    assert date(2025, 12, 25) not in solo, "25 December closes Frankfurt too"
    assert date(2025, 1, 1) not in solo, "1 January closes Frankfurt too"
    assert date(2025, 11, 17) in solo, "17 November is a Czech-only weekday closure"
    assert date(2025, 10, 28) in solo, "28 October is a Czech-only weekday closure"
    assert date(2025, 7, 7) not in solo, (
        "6 July 2025 fell on a Sunday and Czech law grants NO substitute Monday -- inventing "
        "one is exactly the error this pack's lost-holiday series exists to prevent")
    assert date(2025, 7, 6) in CZ.lost_weekend_holidays(2025)
    assert all(d.weekday() < 5 for d in solo)


def test_cot_is_declared_absent_rather_than_silently_missing() -> None:
    """No CZK contract exists anywhere. An absence a study can trip over must be named."""
    rows = [r for r in CZ.POSITIONING_SOURCES if not r["available"]]
    assert rows, "the COT question is not answered anywhere in the pack"
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in rows)
    assert CZ.COT_CURRENCY == ""
    available = [r for r in CZ.POSITIONING_SOURCES if r["available"]]
    assert available, "no positioning source at all, which would make CZ-D unmeasurable"


# ------------------------------------------------------------------------------ the cells
def test_cells_are_minted_honestly_and_in_quantity() -> None:
    """THE POINT OF A PACK IS CELLS REACHING THE GAUNTLET. Every one must name a domain, an
    executable symbol and a condition that domain actually declares."""
    rows = CZ.cells()
    assert 60 <= len(rows) <= 260, f"{len(rows)} cells is outside the honest range"
    by_id = {r["cell_id"] for r in rows}
    assert len(by_id) == len(rows), "duplicate cell ids"
    execs = set(CZ.EXECUTABLE_INSTRUMENTS)
    conds = {d["id"]: set(d["conditions"]) for d in CZ.DOMAINS}
    for row in rows:
        assert row["symbol"] in execs, f"{row['cell_id']} names a non-executable symbol"
        assert row["condition"] in conds[row["domain"]], (
            f"{row['cell_id']} invents a condition its domain does not declare")
        for field in ("mechanism_family", "horizon", "control", "why"):
            assert row[field], f"{row['cell_id']} has an empty {field}"
    assert {r["domain"] for r in rows} == {d["id"] for d in CZ.DOMAINS}


def test_datasets_carry_every_field_a_collector_needs() -> None:
    """A dataset row with no `how_to_fetch` is a wish; fourteen of them is the addendum floor."""
    assert len(CZ.DATASETS) >= 14
    for row in CZ.DATASETS:
        assert row["how_to_fetch"] and len(str(row["how_to_fetch"])) > 30
        assert row["assets"] and resolve(row["assets"])["absent"] == []
        assert row["mechanism_families"]
        assert float(row["publication_lag_days"]) >= 0.0


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {"custom:cnb_decision_windows", "custom:floor_regime_break",
                        "custom:auction_calendar", "custom:holiday_session_clock",
                        "custom:power_outage_fuel", "custom:transmission_seeds"}
    assert all(callable(fn) for fn in got.values())


def test_custom_miner_rows_name_known_domains_and_match_the_miners_module() -> None:
    """The two registrations -- CUSTOM_MINERS and MINERS -- must be one set."""
    from countries.cz import miners as M
    ids = {d["id"] for d in CZ.DOMAINS}
    entries = set()
    for row in CZ.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.cz.miners", row["entry"]
        assert callable(getattr(M, func)), f"{row['entry']} does not resolve"
        entries.add(func)
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    assert entries == set(M.MINERS)
    for did in CZ.MINER_DOMAINS.values():
        assert set(did) <= ids


def test_mine_returns_a_report_and_emits_nothing_to_the_registry() -> None:
    """`mine(None)` is the department entry with no Ctx: pure python, no network, no writes."""
    got = CZ.mine(None)
    assert got["code"] == "cz"
    assert got["emitted"] == 0, "mine(None) must not emit anywhere"
    assert got["rows"], "mine returned no rows at all"
    assert got["cells_emitted"] == len(CZ.cells())
    assert got["datasets"] == len(CZ.DATASETS)
    assert got["layers_covered"] == 10
    assert got["unmeasured"], "a pack with no named unmeasured field is a pack that is lying"
    kinds = {r["kind"] for r in got["rows"]}
    assert kinds == {"transmission_edge", "interaction"}


def test_mine_emits_through_a_ctx_when_it_is_given_one() -> None:
    """With a Ctx it records through `ctx.record` and nowhere else, and notes the unmeasured."""
    recorded: list[Any] = []
    noted: list[tuple[str, str]] = []

    class Ctx:
        def record(self, **kw: Any) -> None:
            recorded.append(kw)

        def note(self, key: str, why: str) -> None:
            noted.append((key, why))

    got = CZ.mine(Ctx())
    assert got["emitted"] == len(got["rows"]) > 0
    assert len(recorded) == got["emitted"]
    assert noted and all(k == "cz_pack:unmeasured" for k, _ in noted)
