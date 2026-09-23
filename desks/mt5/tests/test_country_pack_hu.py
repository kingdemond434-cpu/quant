"""THE HUNGARY PACK, VALIDATED -- six crosses, two policy rates and a decreed calendar.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A PACK THAT IS AN ENGLISH GLOSSARY OF A HUNGARIAN-SPEAKING COUNTRY. Hungarian is a Latin
    script with two letters almost nothing else has -- ő and ű -- which makes the failure
    invisible: a crawler handed de-accented terms searches "kamatdontes" and never finds
    "kamatdöntés". The script assertions below keep the terminology and every crawlable
    source's queries honest.
  * A PACK THAT POOLS ACROSS THE TWO-RATE REGIME. For eleven months the Hungarian policy rate
    was two numbers and the one that mattered for funding was the higher one. `TWO_RATE_REGIME`
    is a mask a study can apply, and the tests check it against its own dated boundaries.
  * A HOLIDAY TABLE SOMEBODY TYPED. All three Hungarian movable holidays -- including Whit
    Monday at Easter plus FIFTY days -- are derived with the anonymous Gregorian algorithm, and
    the tests check the algorithm against three known Easter Sundays.
  * AN INVENTED BRIDGE DAY. The work-schedule swaps follow no rule at all; they are gazetted
    each year. 2026 is deliberately empty and the tests assert that it stays empty.
  * A SYMBOL THE BOX CANNOT TRADE, or a single-name equity on a docket. OTP, MOL, Richter and
    Magyar Telekom are most of the BUX and every one of them is an ACTOR here and nothing else.
  * A PACK THAT REACHES THE FRAMEWORK BENT, or a source layer nobody looked at.
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
from countries.hu import pack as HU  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as F  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")
TUPLE_FIELDS = ("forced_to", "information", "constraints", "instruments", "counterparties",
                "observables")


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it, resolved through `resolve_pack`."""
    got = CL.resolve_pack("hu")
    assert got is not None, "no Hungary pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    assert check_pack(HU.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == "hu"
    assert str(get(built, "region_command")) == "europe"
    assert str(get(built, "currency")) == "HUF"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    """A coercion note is a field `CountryPack` could not read. There must be none."""
    notes = list(getattr(built, "coercion_notes", ()) or ())
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on this pack: {fatal[:4]}"


def test_jurisdictions_are_declared_and_on_the_desks_own_roster() -> None:
    """THE PARITY FENCE COUNTS THIS TUPLE: lowercase ISO-2, and every code on a forest roster."""
    assert HU.JURISDICTIONS == ("hu",)
    assert all(c == c.lower() and len(c) == 2 for c in HU.JURISDICTIONS)
    roster = {g.lower() for f in F.FORESTS.values() for g in (f.grounds or ())}
    roster |= {c.lower() for f in F.FORESTS.values() for c in (f.countries or ())}
    for code in HU.JURISDICTIONS:
        assert code in roster, f"{code} is on no forest's roster in libs/research/forests.py"
    assert F.forest_of_country("hu") == "europe"


def test_pack_reaches_parity_depth(built: Any) -> None:
    row = RP.pack_depth(built, "hu").as_row()
    assert row["score"] == 1.0, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_depth_counts_sit_above_the_floor_and_not_on_it() -> None:
    assert len(HU.ACTORS) >= 14
    assert len(HU.DOMAINS) >= 13
    assert len(HU.TRANSMISSION_EDGES_SEED) >= 10
    assert len(HU.SOURCE_CLASSES) >= 20
    assert len(HU.DATASETS) >= 14
    assert len(HU.POLICY_ERAS) >= 5
    assert len(HU.INTERACTIONS) >= 4
    assert HU.term_count() >= 100


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    for row in HU.ACTORS:
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
    ids = set()
    for row in HU.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert row["conditions"], f"domain {row['id']} names no conditioning state"
        assert row["mechanism_family"], f"domain {row['id']} names no mechanism family"
        assert row["horizon"], f"domain {row['id']} names no horizon"
        assert row["id"] not in ids, f"domain {row['id']} declared twice"
        ids.add(row["id"])


# ------------------------------------------------------------------------------ the universe
def test_all_six_huf_crosses_are_executable() -> None:
    """THE STRUCTURAL REASON THIS PACK EXISTS. Six simultaneous prices of one currency is the
    substitute for a COT report that does not exist, and it only works if all six are quoted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing is checked"
    six = ("EURHUF", "USDHUF", "AUDHUF", "CHFHUF", "GBPHUF", "NZDHUF")
    assert set(six) <= set(registry), f"missing from the registry: {set(six) - set(registry)}"
    assert set(six) <= set(HU.EXECUTABLE_INSTRUMENTS)
    assert HU.six_cross_panel() == six
    assert len(HU.six_cross_panel()) == 6


def test_executable_instruments_are_in_the_brokers_registry() -> None:
    split = resolve(HU.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")


def test_every_domain_instrument_is_executable_so_every_cell_can_be_filled() -> None:
    execs = set(HU.EXECUTABLE_INSTRUMENTS)
    for row in HU.DOMAINS:
        missing = [s for s in row["instruments"] if s not in execs]
        assert missing == [], f"domain {row['id']} names non-executable {missing}"
        assert resolve(row["instruments"])["equities"] == []


def test_every_transmission_seed_names_tradable_targets() -> None:
    for seed in HU.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"


def test_the_national_champions_appear_as_actors_and_never_as_instruments() -> None:
    """OTP, MOL, Richter and Magyar Telekom are most of the BUX. The two-lane order (2026-09-06)
    forbids hunting any of them statistically, and the pack must obey it everywhere."""
    registry = set(universe_symbols())
    assert not {"BUX", "OTP", "MOL", "BUBOR"} & registry
    named = " ".join(str(t["name"]) for t in HU.TRANSMISSION_TARGETS)
    for must in ("BUX", "BUBOR", "MAP Plusz", "HUDEX"):
        assert must in named, f"the pack does not name {must!r} as an absent instrument"
    actors = " ".join(str(a["name"]) for a in HU.ACTORS)
    assert "MOL" in actors and "MVM" in actors
    for row in HU.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == []


def test_the_interactions_name_real_packs_and_tradable_targets() -> None:
    """The desk stops testing each country in isolation here."""
    from countries import codes
    on_disk = set(codes())
    assert len(HU.INTERACTIONS) >= 4
    for row in HU.INTERACTIONS:
        assert row["with"] in on_disk, f"interaction names unknown pack {row['with']!r}"
        assert row["mechanism"] and row["observable"] and row["control"]
        assert resolve(row["targets"])["absent"] == []
        assert resolve(row["targets"])["equities"] == []
    assert {"cz", "pl", "ea", "ru"} <= {r["with"] for r in HU.INTERACTIONS}


# ------------------------------------------------------------------------------ the language
def test_terminology_is_written_in_hungarian_and_not_in_de_accented_mush() -> None:
    assert len(HU.TERMINOLOGY) >= 13
    assert HU.term_count() >= 100
    for group, terms in HU.TERMINOLOGY.items():
        assert any(HU.has_hungarian(t) for t in terms), f"{group} carries no Hungarian accent"
    unique = [t for t in HU.hungarian_terms() if HU.has_hungarian_unique(t)]
    assert len(unique) >= 25, f"only {len(unique)} terms carry ő or ű"
    flat = {t for group in HU.TERMINOLOGY.values() for t in group}
    for must in ("Magyar Nemzeti Bank", "kamatdöntés", "egynapos betéti gyorstender",
                 "forintosítás", "rezsicsökkentés", "államkötvény aukció",
                 "Budapesti Értéktőzsde", "áthelyezett pihenőnap"):
        assert must in flat, f"the Hungary pack does not carry {must!r}"
    assert HU.has_hungarian("forint gyengult") is False
    assert HU.has_hungarian_unique("pihenőnap") and not HU.has_hungarian_unique("nemzeti")


def test_every_layers_queries_are_written_in_hungarian() -> None:
    terms = HU.layer_terms()
    hun_layers = [layer for layer, qs in terms.items() if any(HU.has_hungarian(q) for q in qs)]
    assert len(hun_layers) >= 9, f"only {hun_layers} carry a Hungarian query"
    native = sum(1 for row in HU.SOURCE_CLASSES if row["machine_use_allowed"]
                 for q in row["queries"] if HU.has_hungarian(q))
    assert native >= 60, f"only {native} Hungarian-script queries across crawlable sources"


def test_query_territories_cover_all_ten_layers_in_hungarian() -> None:
    assert set(HU.QUERY_TERRITORIES) == set(HU.SOURCE_LAYERS)
    for layer, phrases in HU.QUERY_TERRITORIES.items():
        assert len(phrases) >= 3, f"{layer} has only {len(phrases)} query territories"
        native = [p for p in phrases if HU.has_hungarian(p)]
        assert len(native) >= 3, f"{layer} has only {len(native)} HUNGARIAN query territories"


def test_every_source_carries_three_independent_labels_and_a_query() -> None:
    for row in HU.SOURCE_CLASSES:
        assert row["access_label"] in HU.ACCESS_LABELS
        assert row["credibility"] in HU.CREDIBILITY_LABELS
        assert row["predictive_state"] in HU.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no native-language query"
        assert row["roots"], f"{row['id']} has no crawlable root"


def test_all_ten_source_layers_are_populated_and_none_is_silently_blank() -> None:
    counts = HU.layer_counts()
    assert set(counts) == set(HU.SOURCE_LAYERS)
    blank = [layer for layer, n in counts.items() if not n]
    assert blank == [], f"blank layers: {blank}"
    coverage = HU.source_layer_coverage()
    assert coverage["n_layers_covered"] == 10
    assert coverage["unexplained_missing"] == []
    assert HU.LAYER_ABSENCES == {}, (
        "Hungary publishes a digitised gazette, an open statistical database and a public "
        "central-bank time-series library; declaring a layer absent would be a false "
        "measurement")
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible for a country "
        "whose refining-margin advantage lives behind a price-reporting-agency paywall")
    assert coverage["low_weight_kept"], "no fringe ground is kept at all, so it was dropped"


# ------------------------------------------------------------------------------ the calendars
def test_easter_and_whit_monday_are_computed_and_not_typed() -> None:
    """Whit Monday is Easter plus FIFTY days, which is the offset a typed table gets wrong."""
    assert HU.easter_sunday(2024) == date(2024, 3, 31)
    assert HU.easter_sunday(2025) == date(2025, 4, 20)
    assert HU.easter_sunday(2026) == date(2026, 4, 5)
    for year, whit in ((2024, date(2024, 5, 20)), (2025, date(2025, 6, 9)),
                       (2026, date(2026, 5, 25))):
        assert HU.easter_sunday(year) + timedelta(days=50) == whit
        assert whit in HU.national_holidays(year), f"Punkosdhetfo missing from {year}"


def test_the_holiday_table_resolves_for_all_three_years_and_stays_in_its_year() -> None:
    for year in (2024, 2025, 2026):
        table = holiday_table(HU.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        assert f"{year}-03-15" in table, "15 March is a fixed national holiday"
        assert f"{year}-10-23" in table, "23 October is a fixed national holiday"
        assert f"{year}-08-20" in table, "20 August is a fixed national holiday"
    assert "2025-04-18" in holiday_table(HU.HOLIDAYS_RULE, 2025)   # Nagypentek
    assert "2026-04-06" in holiday_table(HU.HOLIDAYS_RULE, 2026)   # Husvethetfo
    assert len(HU.national_holidays(2026)) == 11, "eight fixed days plus the Easter trio"


def test_good_friday_did_not_exist_before_2017() -> None:
    """A closed day that arrived in 2017 is a regime break a pooled study will silently miss."""
    assert HU.GOOD_FRIDAY_FROM == 2017
    assert HU.easter_sunday(2016) - timedelta(days=2) not in HU.national_holidays(2016)
    assert HU.easter_sunday(2017) - timedelta(days=2) in HU.national_holidays(2017)


def test_the_decreed_swaps_are_declared_never_computed_and_2026_stays_empty() -> None:
    """THE PACK'S SECOND MECHANISM FUNCTION. No rule produces a Hungarian bridge day; the
    ministry gazettes them. An invented 2026 row would be exactly the fabrication L1.28a bans."""
    assert HU.SWAPPED_DAYS[2026] == (), "a 2026 work-schedule decree cannot already be known"
    assert "NOT_DECLARED" in HU.SWAPPED_DAYS_STATUS[2026]
    assert HU.bridge_rest_days(2026) == {}
    assert HU.working_saturdays(2026) == {}
    rest_2025 = HU.bridge_rest_days(2025)
    sat_2025 = HU.working_saturdays(2025)
    assert len(rest_2025) == len(sat_2025) == 3, "2025 carries three declared swaps"
    assert date(2025, 12, 24) in rest_2025, "24 December 2025 was a decreed rest day"
    assert date(2025, 12, 13) in sat_2025, "13 December 2025 was worked to pay for it"
    assert all(d.weekday() == 5 for d in sat_2025), "a working Saturday must be a Saturday"
    assert all(st == "DECREE_DECLARED" for _r, _w, st in HU.SWAPPED_DAYS[2025])
    # the decreed rest days are NOT statutory holidays and must never be filed as such
    assert date(2025, 12, 24) not in HU.national_holidays(2025)
    assert date(2025, 12, 24) in HU.rest_days(2025)
    assert date(2025, 12, 24) in HU.market_holidays(2025)


def test_weekend_holidays_are_lost_and_counted_as_such() -> None:
    """The Labour Code grants no substitute day, so a Saturday holiday closes nothing."""
    assert HU.WEEKEND_SUBSTITUTION is False
    lost = HU.lost_weekend_holidays(2025)
    assert lost, "2025 has statutory days at the weekend and they must be named"
    assert all(d.weekday() >= 5 for d in lost)
    assert not (set(lost) & set(HU.market_holidays(2025)))


def test_the_release_clock_moves_in_utc_and_the_pack_computes_it() -> None:
    """THE KSH ORDERING ADVANTAGE. 08:30 local is 07:30 UTC in winter -- half an hour before the
    German 08:00 CET prints -- and 06:30 UTC in summer, when the two move together."""
    assert HU.utc_offset_hours(date(2025, 1, 15)) == 1
    assert HU.utc_offset_hours(date(2025, 7, 15)) == 2
    assert HU.dst_start(2025) == date(2025, 3, 30)
    assert HU.dst_end(2025) == date(2025, 10, 26)
    assert HU.release_minute_utc(date(2025, 1, 15)) == "07:30"
    assert HU.release_minute_utc(date(2025, 7, 15)) == "06:30"
    windows = {w["name"]: w for w in HU.SESSION_WINDOWS}
    assert windows["hu_ksh_release"]["start_utc"] == "07:30"
    assert windows["hu_mnb_decision_cet"]["start_utc"] == "12:30"
    assert windows["hu_mnb_decision_cest"]["start_utc"] == "11:30"


def test_the_two_rate_regime_is_a_mask_a_study_can_actually_apply() -> None:
    """THE PACK'S FIRST MECHANISM FUNCTION. For eleven months the policy rate was two numbers."""
    assert HU.TWO_RATE_REGIME["peak_rate_pct"] == 18.0
    assert HU.TWO_RATE_REGIME["base_rate_at_peak_pct"] == 13.0
    assert HU.TWO_RATE_REGIME["introduced"] == date(2022, 10, 14)
    assert HU.TWO_RATE_REGIME["converged"] == date(2023, 9, 26)
    assert HU.in_two_rate_regime(date(2023, 3, 1)) is True
    assert HU.in_two_rate_regime(date(2022, 10, 14)) is True
    assert HU.in_two_rate_regime(date(2023, 9, 26)) is False
    assert HU.in_two_rate_regime(date(2022, 9, 27)) is False
    days = HU.two_rate_days(date(2023, 1, 1), date(2023, 1, 31))
    assert days and all(d.weekday() < 5 for d in days)
    assert len(HU.TWO_RATE_REGIME["what_it_invalidates"]) >= 4
    # the decision list must carry the extraordinary introduction day, which is NOT a Tuesday
    assert "2022-10-14" in HU.CENTRAL_BANK["decision_dates"]
    assert date(2022, 10, 14).weekday() == 4, "the 18% tender was introduced on a Friday"


def test_the_2015_conversion_boundary_is_carried_rather_than_averaged_across() -> None:
    """CHFHUF before and after 2015-02-01 are not the same relationship."""
    assert HU.FX_LOAN_CONVERSION["announced"] == date(2014, 11, 7)
    assert HU.FX_LOAN_CONVERSION["effective"] == date(2015, 2, 1)
    assert HU.post_conversion(date(2015, 2, 1)) is True
    assert HU.post_conversion(date(2014, 12, 31)) is False
    assert len(HU.FX_LOAN_CONVERSION["what_it_removed"]) >= 3
    fam = {d["id"]: d for d in HU.DOMAINS}
    assert "CHFHUF" in fam["HU-F"]["instruments"]


def test_cot_is_declared_absent_and_the_panel_is_named_as_its_substitute() -> None:
    """No HUF contract exists anywhere, and the pack says what it uses instead."""
    rows = [r for r in HU.POSITIONING_SOURCES if not r["available"]]
    assert rows, "the COT question is not answered anywhere in the pack"
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in rows)
    assert any("SIX-CROSS" in str(r["pit_warning"]).upper() for r in rows), (
        "the pack declares the COT absent without naming what replaces it")
    assert HU.COT_CURRENCY == ""
    assert [r for r in HU.POSITIONING_SOURCES if r["available"]]


# ------------------------------------------------------------------------------ the cells
def test_cells_are_minted_honestly_and_in_quantity() -> None:
    rows = HU.cells()
    assert 60 <= len(rows) <= 260, f"{len(rows)} cells is outside the honest range"
    assert len({r["cell_id"] for r in rows}) == len(rows), "duplicate cell ids"
    execs = set(HU.EXECUTABLE_INSTRUMENTS)
    conds = {d["id"]: set(d["conditions"]) for d in HU.DOMAINS}
    for row in rows:
        assert row["symbol"] in execs, f"{row['cell_id']} names a non-executable symbol"
        assert row["condition"] in conds[row["domain"]], (
            f"{row['cell_id']} invents a condition its domain does not declare")
        for field in ("mechanism_family", "horizon", "control", "why"):
            assert row[field], f"{row['cell_id']} has an empty {field}"
    assert {r["domain"] for r in rows} == {d["id"] for d in HU.DOMAINS}
    panel = {r["symbol"] for r in rows if r["domain"] == "HU-D"}
    assert panel == set(HU.six_cross_panel()), "HU-D must mint a cell for every HUF cross"


def test_datasets_carry_every_field_a_collector_needs() -> None:
    assert len(HU.DATASETS) >= 14
    for row in HU.DATASETS:
        assert row["how_to_fetch"] and len(str(row["how_to_fetch"])) > 30
        assert row["assets"] and resolve(row["assets"])["absent"] == []
        assert row["mechanism_families"]
        assert float(row["publication_lag_days"]) >= 0.0


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {"custom:mnb_decision_windows", "custom:two_rate_regime",
                        "custom:six_cross_panel", "custom:auction_calendar",
                        "custom:decreed_calendar", "custom:transmission_seeds"}
    assert all(callable(fn) for fn in got.values())


def test_custom_miner_rows_name_known_domains_and_match_the_miners_module() -> None:
    from countries.hu import miners as M
    ids = {d["id"] for d in HU.DOMAINS}
    entries = set()
    for row in HU.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.hu.miners", row["entry"]
        assert callable(getattr(M, func)), f"{row['entry']} does not resolve"
        entries.add(func)
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    assert entries == set(M.MINERS)
    for did in HU.MINER_DOMAINS.values():
        assert set(did) <= ids


def test_mine_returns_a_report_and_emits_nothing_to_the_registry() -> None:
    got = HU.mine(None)
    assert got["code"] == "hu"
    assert got["emitted"] == 0, "mine(None) must not emit anywhere"
    assert got["rows"], "mine returned no rows at all"
    assert got["cells_emitted"] == len(HU.cells())
    assert got["datasets"] == len(HU.DATASETS)
    assert got["layers_covered"] == 10
    assert got["crosses"] == list(HU.six_cross_panel())
    assert got["unmeasured"], "a pack with no named unmeasured field is a pack that is lying"
    assert any("2026" in u for u in got["unmeasured"]), (
        "the undeclared 2026 work-schedule decree must be named as UNMEASURED")
    assert {r["kind"] for r in got["rows"]} == {"transmission_edge", "interaction"}


def test_mine_emits_through_a_ctx_when_it_is_given_one() -> None:
    recorded: list[Any] = []
    noted: list[tuple[str, str]] = []

    class Ctx:
        def record(self, **kw: Any) -> None:
            recorded.append(kw)

        def note(self, key: str, why: str) -> None:
            noted.append((key, why))

    got = HU.mine(Ctx())
    assert got["emitted"] == len(got["rows"]) > 0
    assert len(recorded) == got["emitted"]
    assert noted and all(k == "hu_pack:unmeasured" for k, _ in noted)
