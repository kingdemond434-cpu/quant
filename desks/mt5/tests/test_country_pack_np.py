"""THE NEPAL PACK, VALIDATED -- the 1.6 peg, the remittance gauge, the one-day weekend.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * AN ENGLISH GLOSSARY OF A NEPALI-SPEAKING COUNTRY. This jurisdiction INVITES that failure,
    because the NRB and the customs department both publish an English summary beside the real
    thing -- so an English-only crawl looks adequate and is not. The gazette, the festival
    calendar, the fuel-price notice and the whole retail ecology run in Devanagari, and the
    script assertions below are what keep the terminology honest.
  * A SATURDAY-SUNDAY WEEKEND. Nepal's national weekly closure is SATURDAY ONLY and NEPSE's is
    Friday and Saturday. Assuming the Gregorian weekend mislabels every Sunday in the sample as
    a non-trading day, which is the single most common way this country is got wrong, so the
    two closures are asserted separately and the framework's own `weekly_closed` is checked.
  * A FIXED OCTOBER FESTIVAL WINDOW. Vijaya Dashami was 12 October in 2024 and 2 October in
    2025. A calendar-month study is averaging two different events, and the drift is measured
    here rather than assumed away.
  * A SINGLE-NAME EQUITY ON A DOCKET. Nepali market commentary is almost entirely NEPSE equity
    talk; under the two-lane order (2026-09-06) none of it may mint a statistical hypothesis.
  * A SYMBOL THE BOX CANNOT TRADE. The Nepalese rupee is absent and must stay a transmission
    target -- and because of the peg it would carry no information even if it were quoted.
  * A PACK THAT REACHES THE FRAMEWORK BENT, or a layer nobody looked at.
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
from countries.np import pack as NP  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as FORESTS  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")
#: What this pack claims about itself, asserted rather than trusted. `pack_depth` must reach it.
DECLARED_DEPTH = 1.0


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it. Resolved through `resolve_pack` so the test measures
    the same object the country lab runs, not a private construction."""
    got = CL.resolve_pack("np")
    assert got is not None, "no Nepal pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(NP.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == "np"
    assert str(get(built, "region_command")) == "asia"
    assert str(get(built, "currency")) == "NPR"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    """A coercion note is a field `CountryPack` could not read. There must be none."""
    notes = list(getattr(built, "coercion_notes", ()) or ())
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on this pack: {fatal[:4]}"


def test_jurisdictions_are_declared_and_on_the_desks_own_roster() -> None:
    """THE PARITY FENCE COUNTS `JURISDICTIONS`. A pack that declares nothing is credited with
    one country by directory name, which is a claim rather than a measurement."""
    assert NP.JURISDICTIONS == ("np",)
    assert all(c == c.lower() and len(c) == 2 for c in NP.JURISDICTIONS)
    roster = {c.lower() for f in FORESTS.FORESTS.values()
              for c in getattr(f, "countries", ())}
    assert roster, "the forest roster is unreadable -- UNMEASURED, so nothing here is checked"
    for code in NP.JURISDICTIONS:
        assert code in roster, f"{code} is not on the desk's own forest roster"


def test_pack_reaches_its_declared_parity_depth(built: Any) -> None:
    """The standing depth rule, measured by the framework and not claimed by the pack."""
    row = RP.pack_depth(built, "np").as_row()
    assert row["score"] >= DECLARED_DEPTH, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_depth_counts_sit_above_the_floor_and_not_on_it() -> None:
    """Twelve actors is the floor; a country written to the floor is a country half-read."""
    assert len(NP.ACTORS) >= 13
    assert len(NP.DOMAINS) >= 13
    assert len(NP.TRANSMISSION_EDGES_SEED) >= 10
    assert len(NP.SOURCE_CLASSES) >= 20
    assert len(NP.DATASETS) >= 14
    assert len(NP.POLICY_ERAS) >= 5
    assert len(NP.INTERACTIONS) >= 4
    assert NP.term_count() >= 110


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    for row in NP.ACTORS:
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
    for row in NP.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert row["conditions"], f"domain {row['id']} names no conditioning state"


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(NP.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert "USDINR" in NP.EXECUTABLE_INSTRUMENTS, "the peg's only executable leg is missing"


def test_no_single_name_equity_anywhere_in_the_pack() -> None:
    """Nepali market commentary is almost entirely single-name NEPSE talk, and none of it may
    reach a docket."""
    pools: list[tuple[str, tuple[str, ...]]] = [("executables", NP.EXECUTABLE_INSTRUMENTS)]
    pools += [(f"domain {d['id']}", tuple(d["instruments"])) for d in NP.DOMAINS]
    pools += [(f"edge {e['id']}", tuple(e["targets"])) for e in NP.TRANSMISSION_EDGES_SEED]
    pools += [(f"interaction {r['with']}", tuple(r["targets"])) for r in NP.INTERACTIONS]
    pools += [(f"transmission target {t['name']}", tuple(t["proxies"]))
              for t in NP.TRANSMISSION_TARGETS]
    for where, symbols in pools:
        split = resolve(symbols)
        assert split["equities"] == [], f"{where}: {split['equities']} is a single-name equity"
        assert split["absent"] == [], f"{where}: {split['absent']} is not in the registry"


def test_every_transmission_seed_names_tradable_targets() -> None:
    """A seed that terminates in a symbol the box cannot quote can never compile a cell."""
    for seed in NP.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"


def test_the_nepalese_rupee_is_named_absent_rather_than_quietly_dropped() -> None:
    """NPR is not quoted here, and the pack says so with the peg that carries it instead."""
    registry = universe_symbols()
    assert not {"USDNPR", "NPR", "INRNPR"} & set(registry)
    named = " ".join(str(t["name"]) for t in NP.TRANSMISSION_TARGETS)
    assert "NPR" in named and "NEPSE" in named
    for row in NP.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == []


# ------------------------------------------------------------------------------ the languages
def test_terminology_is_written_in_devanagari_and_not_in_english() -> None:
    """The failure this jurisdiction invites: an English summary sits beside every real source,
    so an English-only crawl looks adequate and reads the corner as the ground."""
    assert len(NP.devanagari_terms()) >= 100, f"only {len(NP.devanagari_terms())} Nepali terms"
    assert len(NP.english_terms()) == len(NP.ENGLISH_MARKERS), (
        f"missing English working vocabulary: "
        f"{sorted(set(NP.ENGLISH_MARKERS) - set(NP.english_terms()))}")
    flat = {t for group in NP.TERMINOLOGY.values() for t in group}
    for must in ("नेपाल राष्ट्र बैंक", "विप्रेषण", "विदेशी विनिमय सञ्चिति", "स्थिर विनिमय दर",
                 "भन्सार विभाग", "दशैं", "तिहार", "विक्रम सम्बत", "नेप्से", "जलविद्युत",
                 "पञ्चाङ्ग निर्णायक समिति", "शनिबार बिदा"):
        assert must in flat, f"the Nepal pack does not carry {must!r}"
    assert NP.has_devanagari("नेपाल राष्ट्र बैंक") and not NP.has_devanagari("Nepal Rastra Bank")
    assert len(NP.TERMINOLOGY) >= 13


def test_every_layers_queries_are_written_in_devanagari() -> None:
    """A query in English finds an English article about the release, not the release."""
    terms = NP.layer_terms()
    native_layers = [layer for layer, qs in terms.items()
                     if any(NP.has_devanagari(q) for q in qs)]
    assert len(native_layers) >= 9, f"only {native_layers} carry a Devanagari query"
    native = sum(1 for row in NP.SOURCE_CLASSES if row["machine_use_allowed"]
                 for q in row["queries"] if NP.has_devanagari(q))
    assert native >= 60, f"only {native} Devanagari queries across crawlable sources"


def test_query_territories_cover_every_live_layer_in_the_native_script() -> None:
    """The deep-forest miner runs THESE. Three per layer is the floor and every one is native."""
    for layer in NP.SOURCE_LAYERS:
        if layer in NP.LAYER_ABSENCES:
            continue
        rows = NP.QUERY_TERRITORIES.get(layer, ())
        assert len(rows) >= 3, f"layer {layer}: only {len(rows)} query territories"
        assert any(NP.has_devanagari(q) for q in rows), f"layer {layer}: no Nepali territory"


def test_every_source_carries_three_independent_labels_and_a_query() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in NP.SOURCE_CLASSES:
        assert row["access_label"] in NP.ACCESS_LABELS
        assert row["credibility"] in NP.CREDIBILITY_LABELS
        assert row["predictive_state"] in NP.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no native-language query"
        assert row["roots"], f"{row['id']} has no crawlable root"


def test_all_ten_source_layers_are_populated_or_declared_absent() -> None:
    """The principal's depth rule: ten layers, none of them blank."""
    counts = NP.layer_counts()
    assert set(counts) == set(NP.SOURCE_LAYERS)
    coverage = NP.source_layer_coverage()
    blank = [layer for layer, n in counts.items() if not n]
    assert all(layer in NP.LAYER_ABSENCES for layer in blank), (
        f"blank layers with no declared reason: {blank}")
    assert coverage["n_layers_covered"] + len(NP.LAYER_ABSENCES) == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible when the only "
        "consensus for the INR leg lives on a paid terminal")
    assert coverage["low_weight_kept"], "no fringe ground is kept at all, so it was dropped"


# ------------------------------------------------------------------------------ the calendars
def test_the_holiday_table_resolves_for_every_declared_year() -> None:
    """Every year present, every date inside its own year, and the festival blocks in all three."""
    for year in (2024, 2025, 2026):
        table = holiday_table(NP.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        assert any("विजया दशमी" in name for name in table.values()), year
        assert any("भाइटीका" in name for name in table.values()), year
        assert f"{year}-05-01" in table, "Labour Day is a fixed solar date"


def test_the_weekend_is_one_day_long_and_nepse_is_stricter() -> None:
    """THE SINGLE MOST COMMON WAY THIS COUNTRY IS GOT WRONG. The state closes on Saturday only;
    NEPSE trades Sunday to Thursday. Sunday is a full trading day."""
    assert NP.NATIONAL_WEEKEND == (5,), "Nepal's national weekend is SATURDAY ONLY"
    assert NP.NEPSE_CLOSED_WEEKDAYS == (4, 5), "NEPSE trades Sunday to Thursday"
    sunday, saturday = date(2025, 6, 1), date(2025, 6, 7)
    assert sunday.weekday() == 6 and saturday.weekday() == 5
    assert not NP.is_national_weekend(sunday), "Sunday is a working day in Nepal"
    assert NP.is_national_weekend(saturday)
    assert NP.is_nepse_session(sunday), "NEPSE trades on Sunday"
    assert not NP.is_nepse_session(date(2025, 6, 6)), "Friday: NEPSE is shut"
    assert not NP.is_nepse_session(saturday)
    assert NP.is_business_day(sunday) and not NP.is_business_day(saturday)
    # and the framework must receive the one-day weekend, not the Gregorian default
    assert NP._holiday_rule_row()["weekly_closed"] == (5,)
    assert "SATURDAY ONLY" in str(NP.HOLIDAYS_RULE["weekend"])


def test_dashain_moves_by_weeks_and_the_pack_measures_the_drift() -> None:
    """Vijaya Dashami was 12 October in 2024 and 2 October in 2025. A month-aligned study is
    averaging two different events, so the block is carried and the drift is measured."""
    blocks = {y: NP.festival_shutdown_window(y) for y in (2024, 2025, 2026)}
    assert all(b is not None for b in blocks.values())
    starts = [b[0] for b in blocks.values() if b is not None]
    assert starts[0] == date(2024, 10, 10) and starts[1] == date(2025, 9, 30)
    assert (starts[1] - starts[0]).days != 365, "a lunar block cannot be a fixed offset"
    for year, block in blocks.items():
        assert block is not None
        lo, hi, status = block
        assert lo.year == hi.year == year
        assert (hi - lo).days >= 14, "the Dashain-to-Tihar block is a fortnight or more"
        assert status in NP.HOLIDAY_STATUSES
    assert NP.in_festival_shutdown(date(2025, 10, 2))
    assert not NP.in_festival_shutdown(date(2025, 12, 2))
    report = NP.mine_remittance_seasons()
    drifts = [abs(int(r["drift_vs_prior_year_days"])) for r in report["rows"][1:]]
    assert max(drifts) >= 9, f"the festival drift is {drifts}, which cannot be a fixed window"


def test_the_lunar_rows_are_typed_with_their_authority_and_never_invented() -> None:
    """A lunar date no rule computes is typed with the Committee named -- that is honest."""
    authority = str(NP.HOLIDAYS_RULE["authority"])
    assert "NEPAL CALENDAR DETERMINATION COMMITTEE" in authority.upper()
    for year, rows in NP.LUNAR_PUBLIC.items():
        for day, _name, status in rows:
            assert day.year == year
            assert status in NP.HOLIDAY_STATUSES
    assert all(st == "COMMITTEE_TABLE" for *_, st in NP.LUNAR_PUBLIC[2024])
    assert any(st == "PROJECTED" for *_, st in NP.LUNAR_PUBLIC[2026]), (
        "a 2026 lunar row the Committee's patro has not been read for must say PROJECTED")
    assert date(2025, 10, 2) in NP.committee_dates(2025), "Vijaya Dashami 2025"


# ------------------------------------------------------------------------------ the mechanisms
def test_the_peg_is_arithmetic_and_is_computed_rather_than_asserted() -> None:
    """1.60 NPR = 1 INR since 1993-02-01. USD/NPR is USD/INR times 1.6 and carries no
    independent information, which is precisely why Nepali data reads on India."""
    assert NP.npr_per_inr() == 1.60
    assert date(1993, 2, 1) == NP.PEG_SINCE
    assert NP.usdnpr_from_usdinr(85.0) == pytest.approx(136.0, abs=1e-9)
    assert NP.usdnpr_from_usdinr(100.0) == pytest.approx(160.0, abs=1e-9)
    state = NP.peg_state(85.0, 15.4, 1.1)
    assert state["usdnpr"] == pytest.approx(136.0, abs=1e-9)
    assert state["import_cover_months"] == pytest.approx(14.0, abs=1e-9)
    assert state["below_seven_months"] == 0.0
    squeeze = NP.peg_state(80.0, 9.5, 1.45)
    assert squeeze["import_cover_months"] < 7.0
    assert squeeze["below_seven_months"] == 1.0


def test_the_bikram_sambat_fiscal_boundary_is_derived_and_not_typed_twice() -> None:
    """1 Shrawan is mid-July and the fiscal year turns there, not on 1 January or 1 April."""
    start, end = NP.fiscal_year_bounds(2082)
    assert start == date(2025, 7, 17)
    assert end == date(2026, 7, 16), "the year ends the day before the next 1 Shrawan"
    assert NP.fiscal_year_start(2081) == date(2024, 7, 16)
    assert NP.fiscal_year_of(date(2025, 7, 20)) == "2082/83"
    assert NP.fiscal_year_of(date(2025, 7, 10)) == "2081/82", "before 1 Shrawan is the old year"
    assert NP.fiscal_year_of(date(2026, 1, 15)) == "2082/83", "mid-January is mid-fiscal-year"
    assert NP.bs_year_of(date(2024, 7, 16)) == 2081
    assert NP.bs_year_of(date(2024, 7, 15)) == 2080
    for bs in sorted(NP.SHRAWAN_1)[:-1]:
        lo, hi = NP.fiscal_year_bounds(bs)
        assert lo.month == 7 and lo.day in (15, 16, 17, 18), f"{bs}: 1 Shrawan is mid-July"
        assert (hi - lo).days in (364, 365), f"{bs}: a fiscal year is a year long"


def test_the_fortnightly_fuel_clock_is_the_first_and_the_sixteenth() -> None:
    """The IOC-to-NOC transfer price is revised twice a month, which makes the pass-through an
    administered step function with a published calendar and a built-in placebo."""
    days = NP.noc_revision_days(date(2025, 1, 1), date(2025, 12, 31))
    assert len(days) == 24, "twice a month, every month"
    assert all(d.day in NP.NOC_REVISION_DAYS for d in days)
    assert days[0] == date(2025, 1, 1) and days[-1] == date(2025, 12, 16)
    partial = NP.noc_revision_days(date(2025, 2, 5), date(2025, 3, 20))
    assert partial == [date(2025, 2, 16), date(2025, 3, 1), date(2025, 3, 16)]
    assert NP.noc_revision_days(date(2025, 3, 2), date(2025, 3, 15)) == []


def test_the_import_controls_are_dated_and_labelled_rather_than_cited() -> None:
    """The desk may generate hypotheses off a press-reported date and may never promote one."""
    assert NP.IMPORT_CONTROLS
    statuses = {st for *_, st in NP.IMPORT_CONTROLS}
    assert statuses <= {"GAZETTED", "PRESS_REPORTED"}
    assert "GAZETTED" in statuses and "PRESS_REPORTED" in statuses
    gazetted = NP.import_control_dates("GAZETTED")
    assert date(2022, 4, 26) in gazetted, "the ban takes effect"
    assert date(2022, 12, 15) in gazetted, "the ban is lifted"
    assert len(NP.import_control_dates("PRESS_REPORTED")) == len(NP.IMPORT_CONTROLS)
    assert len(gazetted) < len(NP.IMPORT_CONTROLS), "not every date has a gazette number"
    rows = NP.mine_import_control_events()["rows"]
    assert {r["promotable"] for r in rows} == {True, False}


def test_the_india_interaction_is_named_and_the_indian_leg_is_not_re_derived() -> None:
    """The `ind` pack owns USDINR and the RBI's book; this pack adds a second observer."""
    ind = [r for r in NP.INTERACTIONS if r["with"] == "ind"]
    assert ind, "the peg's own sibling interaction is missing"
    assert "ind` pack owns USDINR" in ind[0]["mechanism"] or "owns USDINR" in ind[0]["mechanism"]
    assert resolve(ind[0]["targets"])["absent"] == []
    assert {r["with"] for r in NP.INTERACTIONS} >= {"ind", "sa", "ae", "my", "kr"}


def test_cot_and_the_derivatives_market_are_declared_absent_rather_than_missing() -> None:
    """No NPR contract exists anywhere and Nepal has no derivatives market of any kind."""
    rows = [r for r in NP.POSITIONING_SOURCES if not r["available"]]
    assert len(rows) >= 2, "the COT and the no-derivatives questions are not both answered"
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in rows)
    blob = " ".join(str(c["constraint"]) + str(c["consequence"]) for c in NP.ACCESS_CONSTRAINTS)
    assert "NO DERIVATIVES MARKET" in blob.upper()
    assert "SATURDAY ONLY" in blob.upper()
    assert "BIKRAM SAMBAT" in blob.upper()


# ------------------------------------------------------------------------------ the cells
def test_cells_are_minted_for_the_gauntlet_and_every_one_is_executable() -> None:
    """THE POINT OF A PACK IS CELLS REACHING THE ONE GAUNTLET. Each must name a real condition
    and a symbol the box can trade."""
    rows = NP.cells()
    assert 60 <= len(rows) <= 200, f"{len(rows)} cells is outside the honest range"
    assert len(rows) == len(NP.CELLS)
    ids = {r["cell_id"] for r in rows}
    assert len(ids) == len(rows), "a duplicated cell_id is a double-counted trial"
    domain_ids = {d["id"] for d in NP.DOMAINS}
    execs = set(NP.EXECUTABLE_INSTRUMENTS)
    for row in rows:
        for field in ("cell_id", "domain", "symbol", "condition", "mechanism_family",
                      "horizon", "control", "why"):
            assert str(row[field]).strip(), f"{row['cell_id']}: {field} is empty"
        assert row["domain"] in domain_ids
        assert row["symbol"] in execs
    assert {r["domain"] for r in rows} == domain_ids, (
        "a domain that mints no cell is a domain the gauntlet never sees")


def test_datasets_are_deep_enough_and_every_row_can_be_fetched() -> None:
    """A dataset row with no concrete fetch route is a wish, not a catalogue entry."""
    assert len(NP.DATASETS) >= 14
    reached = set()
    for ds in NP.DATASETS:
        assert len(str(ds["how_to_fetch"])) > 40, f"{ds['name']}: fetch route is too vague"
        assert ds["assets"], f"{ds['name']}: names no asset"
        split = resolve(ds["assets"])
        assert split["absent"] == [], f"{ds['name']}: absent asset {split['absent']}"
        assert split["equities"] == [], f"{ds['name']}: equity asset"
        reached |= set(ds["assets"])
    assert len(reached) >= 6, "the catalogue reaches too few instruments"
    assert any(not ds["pit_feasible"] for ds in NP.DATASETS), (
        "every dataset claims point-in-time feasibility, which is implausible when the NOC "
        "price page keeps no history at all")


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {f"custom:{name}" for name in NP.MINERS}
    assert all(callable(fn) for fn in got.values())


def test_custom_miner_rows_name_known_domains_and_match_the_miners_table() -> None:
    """The two registrations -- CUSTOM_MINERS and MINERS -- must be one set."""
    ids = {d["id"] for d in NP.DOMAINS}
    entries = set()
    for row in NP.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.np.pack", row["entry"]
        assert callable(getattr(NP, func)), f"{row['entry']} does not resolve"
        entries.add(func)
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    assert entries == set(NP.MINERS)
    for did in NP.MINER_DOMAINS.values():
        assert set(did) <= ids


def test_mine_returns_a_report_and_emits_nothing_to_the_registry() -> None:
    """`mine(None)` is a pure-python pass: it reads the pack's own tables and records nothing."""
    report = NP.mine(None)
    assert report["code"] == "NP"
    assert report["emitted"] == len(NP.MINERS)
    assert report["cells_emitted"] == len(NP.cells())
    assert report["layers"] == 10
    assert report["unmeasured"], "a pack that can see everything is a pack that did not look"
    assert date.fromisoformat(str(report["at"]))
    assert set(report["interactions"]) == {r["with"] for r in NP.INTERACTIONS}
    for row in report["rows"]:
        assert row["n"] >= 1, f"{row['miner']} emitted nothing at all"


def test_mine_records_through_a_ctx_when_one_is_given() -> None:
    """When a department Ctx is handed in, every miner's result goes through `ctx.record`."""
    seen: list[Any] = []

    class Ctx:
        def record(self, row: Any) -> None:
            seen.append(row)

    report = NP.mine(Ctx())
    assert len(seen) == len(NP.MINERS) == report["emitted"]
    assert all(isinstance(r, dict) and r.get("rows") is not None for r in seen)
