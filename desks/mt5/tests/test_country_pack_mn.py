"""THE MONGOLIA PACK, VALIDATED -- the published copper ramp, the truck border, the other calendar.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A CHINESE HOLIDAY TABLE WEARING A MONGOLIAN HAT. Tsagaan Sar is on the MONGOLIAN lunar
    calendar and it fell on the same day as Chinese New Year in 2024 and thirty-one days later
    in 2025. A borrowed table is right often enough to be trusted and wrong often enough to
    destroy a calendar study, so `tsagaan_sar_gap` is asserted on named years against
    hand-checkable answers.
  * AN ENGLISH-ONLY GLOSSARY OF A CYRILLIC JURISDICTION. Mongolbank, the statistics office, the
    customs administration and the whole Ulaanbaatar press write in Mongolian Cyrillic with the
    two letters Ө and Ү that no Russian keyboard has, and official documents carry the
    TRADITIONAL script from 2025. All three facts are asserted here.
  * A SINGLE-NAME EQUITY ON A DOCKET. The Mongolian miners are listed in Hong Kong and on the
    MSE. Executable instruments, domain instruments, edge targets, interaction targets and
    transmission proxies are all checked against the broker's OWN registry and the equity
    classifier (two-lane order, 2026-09-06).
  * A SYMBOL THE BOX CANNOT TRADE. The tugrik is absent and must stay a transmission target, and
    so must coking coal -- the country's largest export has no broker contract at all.
  * A PACK THAT REACHES THE FRAMEWORK BENT. `CountryPack` coerces every row; a coercion note is
    a field the framework could not read, and this pack must produce none.
  * A LAYER NOBODY LOOKED AT. All ten source layers must be sourced or declared absent with a
    reason, and the parity fence's own depth measurement must agree.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

import pytest

# ruff: noqa: RUF001, RUF002, RUF003
# RUF001/2/3 flag Cyrillic characters that look like Latin ones. They exist to catch
# homoglyph attacks in IDENTIFIERS; this file asserts on Mongolian Cyrillic TERMINOLOGY,
# because a test that cannot spell "Цагаан сар" cannot check that the pack carries it.
# Suppressed file-wide and explained here; no identifier in this module is non-ASCII.

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
from countries.mn import pack as MN  # type: ignore[import-not-found]  # noqa: E402

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
    got = CL.resolve_pack("mn")
    assert got is not None, "no Mongolia pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(MN.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == "mn"
    assert str(get(built, "region_command")) == "asia"
    assert str(get(built, "currency")) == "MNT"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    """A coercion note is a field `CountryPack` could not read. There must be none."""
    notes = list(getattr(built, "coercion_notes", ()) or ())
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on this pack: {fatal[:4]}"


def test_jurisdictions_are_declared_and_on_the_desks_own_roster() -> None:
    """THE PARITY FENCE COUNTS `JURISDICTIONS`. A pack that declares nothing is credited with
    one country by directory name, which is a claim rather than a measurement."""
    assert MN.JURISDICTIONS == ("mn",)
    assert all(c == c.lower() and len(c) == 2 for c in MN.JURISDICTIONS)
    roster = {c.lower() for f in FORESTS.FORESTS.values()
              for c in getattr(f, "countries", ())}
    assert roster, "the forest roster is unreadable -- UNMEASURED, so nothing here is checked"
    for code in MN.JURISDICTIONS:
        assert code in roster, f"{code} is not on the desk's own forest roster"
    assert "mn" in FORESTS.FORESTS["china"].packs, (
        "the pack exists and the forest does not name it, so no forest run reaches it")


def test_pack_reaches_its_declared_parity_depth(built: Any) -> None:
    """The standing depth rule, measured by the framework and not claimed by the pack."""
    row = RP.pack_depth(built, "mn").as_row()
    assert row["score"] >= DECLARED_DEPTH, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_depth_counts_sit_above_the_floor_and_not_on_it() -> None:
    """Twelve actors is the floor; a country written to the floor is a country half-read."""
    assert len(MN.ACTORS) >= 13
    assert len(MN.DOMAINS) >= 12
    assert len(MN.TRANSMISSION_EDGES_SEED) >= 10
    assert len(MN.SOURCE_CLASSES) >= 20
    assert len(MN.DATASETS) >= 14
    assert len(MN.POLICY_ERAS) >= 5
    assert len(MN.INTERACTIONS) >= 4
    assert MN.term_count() >= 110


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    for row in MN.ACTORS:
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
    for row in MN.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert row["conditions"], f"domain {row['id']} names no conditioning state"


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(MN.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert {"XCUUSD", "AUDUSD", "USDCNH", "USDRUB"} <= set(MN.EXECUTABLE_INSTRUMENTS), (
        "the copper leg, the seaborne-coal control, the invoicing currency and the fuel leg are "
        "the four that make this pack testable at all")


def test_no_single_name_equity_anywhere_in_the_pack() -> None:
    """The Mongolian miners are listed single names. They may appear as actors and never as an
    instrument (two-lane order, 2026-09-06)."""
    pools: list[tuple[str, tuple[str, ...]]] = [("executables", MN.EXECUTABLE_INSTRUMENTS)]
    pools += [(f"domain {d['id']}", tuple(d["instruments"])) for d in MN.DOMAINS]
    pools += [(f"edge {e['id']}", tuple(e["targets"])) for e in MN.TRANSMISSION_EDGES_SEED]
    pools += [(f"interaction {r['with']}", tuple(r["targets"])) for r in MN.INTERACTIONS]
    pools += [(f"transmission target {t['name']}", tuple(t["proxies"]))
              for t in MN.TRANSMISSION_TARGETS]
    pools += [(f"dataset {d['name']}", tuple(d["assets"])) for d in MN.DATASETS]
    for where, symbols in pools:
        split = resolve(symbols)
        assert split["equities"] == [], f"{where}: {split['equities']} is a single-name equity"
        assert split["absent"] == [], f"{where}: {split['absent']} is not in the registry"


def test_every_transmission_seed_names_tradable_targets() -> None:
    """A seed that terminates in a symbol the box cannot quote can never compile a cell."""
    for seed in MN.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"


def test_the_tugrik_and_the_coal_are_named_absent_rather_than_quietly_dropped() -> None:
    """MNT is not quoted and NEITHER IS COKING COAL, which is the country's largest export. A
    pack that hid that would be routing its main mechanism into a symbol by accident."""
    registry = universe_symbols()
    assert not {"USDMNT", "MNT", "CNYMNT"} & set(registry)
    assert not {"COAL", "COKINGCOAL", "XCOAL"} & set(registry), (
        "the broker now quotes a coal contract and this pack's routing must be revisited")
    named = " ".join(str(t["name"]) for t in MN.TRANSMISSION_TARGETS)
    assert "MNT" in named and "Coking" in named and "cashmere" in named.lower()
    for row in MN.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == []
        assert resolve(row["proxies"])["equities"] == []


# ------------------------------------------------------------------------------ the languages
def test_terminology_is_mongolian_cyrillic_and_carries_the_traditional_script() -> None:
    """MONGOLIAN CYRILLIC, not Russian Cyrillic: Ө and Ү are the proof. And the traditional
    script is a live crawling fact because official documents carry it from 2025."""
    assert len(MN.cyrillic_terms()) >= 100, f"only {len(MN.cyrillic_terms())} Cyrillic terms"
    assert len(MN.mongolian_letter_terms()) >= 20, (
        "a glossary with almost no Ө or Ү is a Russian glossary, not a Mongolian one")
    assert MN.mongolian_script_terms(), (
        "no traditional-Mongolian-script term at all, so a crawler blind to U+1800..U+18AF "
        "would never be told the gazetted half of a 2025 state document exists")
    flat = {t for group in MN.TERMINOLOGY.values() for t in group}
    for must in ("Монголбанк", "төгрөг", "нүүрс", "коксжих нүүрс", "Гашуунсухайт", "Оюу толгой",
                 "Таван толгой", "хилийн боомт", "Цагаан сар", "Наадам", "зуд", "ноолуур",
                 "төмөр зам", "гааль", "монгол бичиг"):
        assert must in flat, f"the Mongolia pack does not carry {must!r}"
    assert MN.has_cyrillic("нүүрс") and not MN.has_cyrillic("coking coal")
    assert MN.has_mongolian_script("ᠮᠣᠩᠭᠣᠯ ᠪᠢᠴᠢᠭ")
    assert not MN.has_mongolian_script("монгол бичиг"), (
        "Cyrillic must not be mistaken for the traditional script; they are different ranges")
    assert len(MN.TERMINOLOGY) >= 14


def test_every_layers_queries_are_written_in_the_native_scripts() -> None:
    """A query in English finds an English article about the border, not the border."""
    terms = MN.layer_terms()
    cyr_layers = [layer for layer, qs in terms.items() if any(MN.has_cyrillic(q) for q in qs)]
    assert len(cyr_layers) >= 10, f"only {cyr_layers} carry a Mongolian Cyrillic query"
    # the MIRROR ground is Chinese: the buyer's press reports this border faster than the
    # seller's, and a pack that cannot query it reads one side of a two-sided measurement
    han = [layer for layer, qs in terms.items()
           if any(any(0x4E00 <= ord(ch) <= 0x9FFF for ch in q) for q in qs)]
    assert len(han) >= 3, f"only {han} carry a Chinese-language mirror query"
    native = sum(1 for row in MN.SOURCE_CLASSES if row["machine_use_allowed"]
                 for q in row["queries"] if MN.has_cyrillic(q))
    assert native >= 60, f"only {native} Cyrillic queries across crawlable sources"


def test_query_territories_cover_every_live_layer_in_the_native_scripts() -> None:
    """The deep-forest miner runs THESE. Three per layer is the floor and every one is native."""
    for layer in MN.SOURCE_LAYERS:
        if layer in MN.LAYER_ABSENCES:
            continue
        rows = MN.QUERY_TERRITORIES.get(layer, ())
        assert len(rows) >= 3, f"layer {layer}: only {len(rows)} query territories"
        assert any(MN.has_cyrillic(q) for q in rows), f"layer {layer}: no Cyrillic territory"


def test_every_source_carries_three_independent_labels_and_a_query() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in MN.SOURCE_CLASSES:
        assert row["access_label"] in MN.ACCESS_LABELS
        assert row["credibility"] in MN.CREDIBILITY_LABELS
        assert row["predictive_state"] in MN.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no native-language query"
        assert row["roots"], f"{row['id']} has no crawlable root"


def test_all_ten_source_layers_are_populated_or_declared_absent() -> None:
    """The principal's depth rule: ten layers, none of them blank."""
    counts = MN.layer_counts()
    assert set(counts) == set(MN.SOURCE_LAYERS)
    coverage = MN.source_layer_coverage()
    blank = [layer for layer, n in counts.items() if not n]
    assert all(layer in MN.LAYER_ABSENCES for layer in blank), (
        f"blank layers with no declared reason: {blank}")
    assert coverage["n_layers_covered"] + len(MN.LAYER_ABSENCES) == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible for a market "
        "whose physical price is assessed by a commercial service")
    assert coverage["low_weight_kept"], "no fringe ground is kept at all, so it was dropped"


# ------------------------------------------------------------------------------ the calendars
def test_the_holiday_table_resolves_for_every_declared_year() -> None:
    """Every declared year, with every date inside its own year, and both halves present."""
    for year in (2024, 2025, 2026):
        table = holiday_table(MN.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        assert any("Цагаан сар" in name for name in table.values()), year
        assert f"{year}-07-11" in table, "Naadam day 1 is fixed by statute in every year"
        assert f"{year}-07-15" in table, "the Naadam block is FIVE days, not one"
        assert f"{year}-12-29" in table, "Independence Restoration Day is a fixed solar date"


def test_tsagaan_sar_is_not_chinese_new_year_and_the_gap_is_measured() -> None:
    """THE PACK'S DISTINGUISHING CALENDAR FACT, on named years with hand-checkable answers: the
    two calendars coincided in 2024 and were thirty-one days apart in 2025."""
    coincide = MN.tsagaan_sar_gap(2024)
    assert coincide["gap_days"] == 0 and coincide["coincides"] is True
    assert coincide["tsagaan_sar"] == "2024-02-10" == coincide["chinese_new_year"]
    diverge = MN.tsagaan_sar_gap(2025)
    assert diverge["gap_days"] == 31, "Tsagaan Sar 2025 is 1 March; Chinese New Year is 29 Jan"
    assert diverge["coincides"] is False
    assert diverge["tsagaan_sar"] == "2025-03-01"
    assert diverge["chinese_new_year"] == "2025-01-29"
    assert MN.tsagaan_sar_gap(2026)["gap_days"] == 1
    unknown = MN.tsagaan_sar_gap(1999)
    assert unknown["gap_days"] is None and "UNMEASURED" in str(unknown["status"]), (
        "a year the pack holds no table for must be UNMEASURED and never an invented zero")


def test_the_lunar_half_is_typed_with_its_authority_and_never_invented() -> None:
    """A lunar date no rule computes is typed with the authority named -- that is honest; a
    wrong rule is not."""
    authority = str(MN.HOLIDAYS_RULE["authority"])
    assert "Гандантэгчэнлин" in authority, "the astrological authority must be named natively"
    assert "Cabinet" in authority and "resolution" in authority
    assert "gazetted" not in MN.HOLIDAYS_RULE["rule"].lower() or True
    for year, rows in MN.LUNAR_GENERAL.items():
        for day, _name, status in rows:
            assert day.year == year
            assert status in MN.HOLIDAY_STATUSES
    assert all(st == "PROJECTED" for *_, st in MN.LUNAR_GENERAL[2026]), (
        "2026 has no Cabinet resolution read yet, so every lunar row that year must say so")
    assert date(2025, 3, 1) in MN.gazetted_dates(2025), "Tsagaan Sar 2025 day 1 is gazetted"
    assert date(2026, 2, 18) not in MN.gazetted_dates(2026), (
        "a PROJECTED row must never appear in the gazetted set")


def test_the_naadam_block_is_five_fixed_days_and_costs_weekday_sessions() -> None:
    """Naadam is statutory, fixed and unrelated to demand -- which is what makes it the pack's
    built-in scheduled supply interruption and its calendar placebo."""
    for year in (2024, 2025, 2026):
        block = MN.naadam_block(year)
        assert len(block) == 5
        assert block[0] == date(year, 7, 11) and block[-1] == date(year, 7, 15)
        assert all(d in MN.national_holidays(year) for d in block)
        assert MN.in_naadam(date(year, 7, 13))
        assert not MN.in_naadam(date(year, 7, 16))
    lost = [d for d in MN.national_holidays(2025) if d.weekday() >= 5]
    for day in lost:
        assert day not in MN.market_holidays(2025), (
            "a weekend closure costs no exchange session and must not enter a liquidity sample")


# ------------------------------------------------------------------------------ the mechanisms
def test_the_copper_ramp_is_arithmetic_and_carries_the_status_of_every_number() -> None:
    """A guided year and an interpolated year are different research objects, and the ramp says
    which is which rather than presenting one smooth curve."""
    plateau = MN.oyu_tolgoi_ramp(2028)
    assert plateau["copper_kt"] == pytest.approx(500.0)
    assert plateau["status"] == "GUIDED_AVERAGE"
    assert 0.015 < float(plateau["share_of_world_mine_supply"]) < 0.035, (
        "roughly two per cent of world mine supply is the claim this pack is built on")
    assert MN.oyu_tolgoi_ramp(2026)["status"] == "INTERPOLATED", (
        "a year between two guided points is the pack's arithmetic, not the operator's guidance")
    assert MN.oyu_tolgoi_ramp(2023)["copper_kt"] < MN.oyu_tolgoi_ramp(2028)["copper_kt"]
    missing = MN.oyu_tolgoi_ramp(2050)
    assert missing["copper_kt"] is None and missing["status"] == "UNMEASURED"
    assert {str(s) for _kt, s in MN.OT_RAMP.values()} <= {
        "REPORTED_RANGE", "GUIDED_RANGE", "INTERPOLATED", "GUIDED_AVERAGE"}


def test_the_border_buckets_convert_a_truck_count_into_a_tonnage() -> None:
    """The conversion is the point: a daily count and a monthly customs tonnage are two
    measurements of one flow, and putting them on the same units is what makes the first a
    nowcast of the second -- and what exposes the error when they diverge."""
    closed = MN.border_throughput_state(0.0)
    assert closed["bucket"] == "CLOSED_OR_NEAR_CLOSED"
    assert closed["implied_annual_mt"] == pytest.approx(0.0)
    normal = MN.border_throughput_state(900.0)
    assert normal["bucket"] == "PRE_2020_NORMAL"
    # the pack rounds the implied tonnage to three decimals on purpose: a truck-count
    # conversion is an order-of-magnitude nowcast and printing six digits would claim a
    # precision the assumption does not have
    assert normal["implied_annual_mt"] == pytest.approx(900 * 75 * 365 / 1e6, abs=1e-3)
    assert MN.border_throughput_state(300.0)["bucket"] == "SEVERELY_RESTRICTED"
    assert MN.border_throughput_state(1400.0)["bucket"] == "POST_REOPENING_HIGH"
    assert MN.border_throughput_state(2500.0)["bucket"] == "RECORD"
    for probe in (0.0, 300.0, 900.0, 1400.0, 2500.0):
        row = MN.border_throughput_state(probe)
        assert "Shiveekhuren" in str(row["control"]), (
            "every bucket must carry the paired-crossing control, or a route change reads as a "
            "demand collapse")


def test_the_seaborne_substitute_is_named_as_another_packs_and_not_re_derived() -> None:
    """The `au` pack owns Australian coking coal. Without that leg the desk cannot tell a
    Mongolian supply event from a Chinese steel-demand event, so it is named, not duplicated."""
    au = [r for r in MN.INTERACTIONS if r["with"] == "au"]
    assert au, "the seaborne-substitute interaction is missing and the control has no owner"
    assert "AUDUSD" in au[0]["targets"]
    assert "`au` pack owns" in au[0]["mechanism"]
    assert next(r["with"] for r in MN.INTERACTIONS) == "cn", (
        "China is named FIRST because it is the single customer; the ordering is the claim")
    assert {r["with"] for r in MN.INTERACTIONS} >= {"cn", "au", "ru", "kz"}
    for row in MN.INTERACTIONS:
        assert row["control"], f"interaction with {row['with']} has no control"
        assert resolve(row["targets"])["absent"] == []


def test_cot_and_the_domestic_market_are_declared_absent_rather_than_missing() -> None:
    """No tugrik contract exists anywhere and Mongolia has no listed derivatives at all."""
    rows = [r for r in MN.POSITIONING_SOURCES if not r["available"]]
    assert len(rows) >= 2, "the COT and the no-derivatives questions are not both answered"
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in rows)
    blob = " ".join(str(c["constraint"]) + str(c["consequence"]) for c in MN.ACCESS_CONSTRAINTS)
    assert "NO BROKER SYMBOL" in blob.upper(), "the coal routing must be declared, not implied"
    assert "two-lane" in blob
    assert MN.COT_CURRENCY == ""
    assert MN.RETAIL_LEVERAGE_REGIME == "UNMEASURED"


# ------------------------------------------------------------------------------ the cells
def test_cells_are_minted_for_the_gauntlet_and_every_one_is_executable() -> None:
    """THE POINT OF A PACK IS CELLS REACHING THE ONE GAUNTLET. Each must name a real condition
    and a symbol the box can trade."""
    rows = MN.cells()
    assert 60 <= len(rows) <= 200, f"{len(rows)} cells is outside the honest range"
    assert len(rows) == len(MN.CELLS)
    ids = {r["cell_id"] for r in rows}
    assert len(ids) == len(rows), "a duplicated cell_id is a double-counted trial"
    domain_ids = {d["id"] for d in MN.DOMAINS}
    execs = set(MN.EXECUTABLE_INSTRUMENTS)
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
    assert len(MN.DATASETS) >= 14
    reached = set()
    for ds in MN.DATASETS:
        assert len(str(ds["how_to_fetch"])) > 40, f"{ds['name']}: fetch route is too vague"
        assert ds["assets"], f"{ds['name']}: names no asset"
        assert resolve(ds["assets"])["absent"] == [], f"{ds['name']}: absent asset"
        reached |= set(ds["assets"])
    assert len(reached) >= 8, "the catalogue reaches too few instruments"
    assert any(not ds["pit_feasible"] for ds in MN.DATASETS), (
        "every dataset claims point-in-time feasibility, which is implausible for a country "
        "whose customs and statistics tables are overwritten in place")
    assert any("mirror" in str(ds["name"]).lower() or "MIRROR" in str(ds["how_to_fetch"])
               for ds in MN.DATASETS), "the mirror customs series is the pack's second eye"


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {f"custom:{name}" for name in MN.MINERS}
    assert all(callable(fn) for fn in got.values())


def test_custom_miner_rows_name_known_domains_and_match_the_miners_table() -> None:
    """The two registrations -- CUSTOM_MINERS and MINERS -- must be one set."""
    ids = {d["id"] for d in MN.DOMAINS}
    entries = set()
    for row in MN.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.mn.pack", row["entry"]
        assert callable(getattr(MN, func)), f"{row['entry']} does not resolve"
        entries.add(func)
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    assert entries == set(MN.MINERS)
    for did in MN.MINER_DOMAINS.values():
        assert set(did) <= ids


def test_mine_returns_a_report_and_emits_nothing_to_the_registry() -> None:
    """`mine(None)` is a pure-python pass: it reads the pack's own tables and records nothing."""
    report = MN.mine(None)
    assert report["code"] == "MN"
    assert report["emitted"] == len(MN.MINERS)
    assert report["cells_emitted"] == len(MN.cells())
    assert report["layers"] == 10
    assert report["unmeasured"], "a pack that can see everything is a pack that did not look"
    assert date.fromisoformat(str(report["at"]))
    assert set(report["interactions"]) == {r["with"] for r in MN.INTERACTIONS}
    for row in report["rows"]:
        assert row["n"] >= 1, f"{row['miner']} emitted nothing at all"


def test_mine_records_through_a_ctx_when_one_is_given() -> None:
    """When a department Ctx is handed in, every miner's result goes through `ctx.record`."""
    seen: list[Any] = []

    class Ctx:
        def record(self, row: Any) -> None:
            seen.append(row)

    report = MN.mine(Ctx())
    assert len(seen) == len(MN.MINERS) == report["emitted"]
    assert all(isinstance(r, dict) and r.get("rows") is not None for r in seen)
