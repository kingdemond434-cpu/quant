"""THE MACAU PACK, VALIDATED -- the first-working-day clock, the peg on a peg, the dual calendar.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A CHINESE-ONLY GLOSSARY OF A BILINGUAL JURISDICTION. Portuguese is co-official in Macau, the
    Boletim Oficial is published in both languages, and the gaming law, the concession contracts
    and the gazetted holiday table are read in Portuguese or not at all. A crawler handed only
    Traditional Chinese reads the numbers and misses the statute that changed them, so both
    scripts are asserted here.
  * A SINGLE-NAME EQUITY ON A DOCKET. Every concessionaire is listed in Hong Kong or New York,
    which makes this the most tempting pack in the package for the two-lane order (2026-09-06)
    to be quietly broken in. Executable instruments, domain instruments and edge targets are all
    checked against the broker's OWN registry and against the equity classifier.
  * A SYMBOL THE BOX CANNOT TRADE. The pataca is absent and must stay a transmission target.
  * A PACK THAT REACHES THE FRAMEWORK BENT. `CountryPack` coerces every row; a coercion note is
    a field the framework could not read, and this pack must produce none.
  * A RELEASE STAMPED TO THE FIRST OF THE MONTH. The DICJ publishes on the first WORKING day,
    which two religious calendars jointly set -- January opens on a general holiday and October
    on two. `first_working_day` is asserted on named months against hand-checkable answers.
  * A LAYER NOBODY LOOKED AT. All ten source layers must be sourced or declared absent with a
    reason, and the parity fence's own depth measurement must agree.
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
from countries.mo import pack as MO  # type: ignore[import-not-found]  # noqa: E402

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
    got = CL.resolve_pack("mo")
    assert got is not None, "no Macau pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(MO.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == "mo"
    assert str(get(built, "region_command")) == "asia"
    assert str(get(built, "currency")) == "MOP"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    """A coercion note is a field `CountryPack` could not read. There must be none."""
    notes = list(getattr(built, "coercion_notes", ()) or ())
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on this pack: {fatal[:4]}"


def test_jurisdictions_are_declared_and_on_the_desks_own_roster() -> None:
    """THE PARITY FENCE COUNTS `JURISDICTIONS`. A pack that declares nothing is credited with
    one country by directory name, which is a claim rather than a measurement."""
    assert MO.JURISDICTIONS == ("mo",)
    assert all(c == c.lower() and len(c) == 2 for c in MO.JURISDICTIONS)
    roster = {c.lower() for f in FORESTS.FORESTS.values()
              for c in getattr(f, "countries", ())}
    assert roster, "the forest roster is unreadable -- UNMEASURED, so nothing here is checked"
    for code in MO.JURISDICTIONS:
        assert code in roster, f"{code} is not on the desk's own forest roster"


def test_pack_reaches_its_declared_parity_depth(built: Any) -> None:
    """The standing depth rule, measured by the framework and not claimed by the pack."""
    row = RP.pack_depth(built, "mo").as_row()
    assert row["score"] >= DECLARED_DEPTH, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_depth_counts_sit_above_the_floor_and_not_on_it() -> None:
    """Twelve actors is the floor; a country written to the floor is a country half-read."""
    assert len(MO.ACTORS) >= 13
    assert len(MO.DOMAINS) >= 13
    assert len(MO.TRANSMISSION_EDGES_SEED) >= 10
    assert len(MO.SOURCE_CLASSES) >= 20
    assert len(MO.DATASETS) >= 14
    assert len(MO.POLICY_ERAS) >= 5
    assert len(MO.INTERACTIONS) >= 4
    assert MO.term_count() >= 120


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    for row in MO.ACTORS:
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
    for row in MO.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert row["conditions"], f"domain {row['id']} names no conditioning state"


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(MO.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert set(MO.EXECUTABLE_INSTRUMENTS) <= set(registry)


def test_no_single_name_equity_anywhere_in_the_pack() -> None:
    """THE MOST TEMPTING PACK IN THE PACKAGE TO BREAK THIS IN: every Macau concessionaire is a
    listed single name. They may appear as actors and never as an instrument."""
    pools: list[tuple[str, tuple[str, ...]]] = [("executables", MO.EXECUTABLE_INSTRUMENTS)]
    pools += [(f"domain {d['id']}", tuple(d["instruments"])) for d in MO.DOMAINS]
    pools += [(f"edge {e['id']}", tuple(e["targets"])) for e in MO.TRANSMISSION_EDGES_SEED]
    pools += [(f"interaction {r['with']}", tuple(r["targets"])) for r in MO.INTERACTIONS]
    pools += [(f"transmission target {t['name']}", tuple(t["proxies"]))
              for t in MO.TRANSMISSION_TARGETS]
    for where, symbols in pools:
        split = resolve(symbols)
        assert split["equities"] == [], f"{where}: {split['equities']} is a single-name equity"
        assert split["absent"] == [], f"{where}: {split['absent']} is not in the registry"


def test_every_transmission_seed_names_tradable_targets() -> None:
    """A seed that terminates in a symbol the box cannot quote can never compile a cell."""
    for seed in MO.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"


def test_the_pataca_is_named_absent_rather_than_quietly_dropped() -> None:
    """MOP is not quoted here and the pack says so with what carries it instead."""
    registry = universe_symbols()
    assert not {"USDMOP", "MOP", "HKDMOP"} & set(registry)
    named = " ".join(str(t["name"]) for t in MO.TRANSMISSION_TARGETS)
    assert "MOP" in named and "MOX" in named
    for row in MO.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == []


# ------------------------------------------------------------------------------ the languages
def test_terminology_carries_traditional_chinese_and_portuguese() -> None:
    """TWO OFFICIAL LANGUAGES. A Chinese-only crawl gets the numbers and misses the statute."""
    assert len(MO.han_terms()) >= 90, f"only {len(MO.han_terms())} Han terms"
    assert len(MO.portuguese_terms()) == len(MO.PORTUGUESE_MARKERS), (
        f"missing Portuguese working vocabulary: "
        f"{sorted(set(MO.PORTUGUESE_MARKERS) - set(MO.portuguese_terms()))}")
    flat = {t for group in MO.TERMINOLOGY.values() for t in group}
    for must in ("博彩毛收入", "博彩監察協調局", "澳門金融管理局", "港元掛鈎", "財政儲備",
                 "入境旅客", "關閘", "貴賓廳", "澳門特別行政區公報", "粵港澳大灣區"):
        assert must in flat, f"the Macau pack does not carry {must!r}"
    for must in ("receitas brutas dos jogos", "Boletim Oficial da RAEM", "pataca",
                 "reserva financeira", "concessionaria"):
        assert must in flat, f"the Macau pack does not carry {must!r}"
    assert MO.has_han("博彩毛收入") and not MO.has_han("receitas brutas")
    assert len(MO.TERMINOLOGY) >= 13


def test_every_layers_queries_are_written_in_the_native_scripts() -> None:
    """A query in English finds an English article about the release, not the release."""
    terms = MO.layer_terms()
    han_layers = [layer for layer, qs in terms.items() if any(MO.has_han(q) for q in qs)]
    assert len(han_layers) >= 9, f"only {han_layers} carry a Traditional Chinese query"
    pt_markers = ("receitas", "Boletim", "estatisticas", "relatorio", "visitantes", "segundo",
                  "arquivo", "jogo", "trafego", "previsao", "pagamentos", "concessoes",
                  "anuario", "filas", "carteira", "associacao", "estudos", "procura",
                  "estimativa", "Governo", "dados")
    pt_layers = [layer for layer, qs in terms.items()
                 if any(m in q for q in qs for m in pt_markers)]
    assert len(pt_layers) >= 7, f"only {pt_layers} carry a Portuguese query"
    native = sum(1 for row in MO.SOURCE_CLASSES if row["machine_use_allowed"]
                 for q in row["queries"] if MO.has_han(q))
    assert native >= 60, f"only {native} Han-script queries across crawlable sources"


def test_query_territories_cover_every_live_layer_in_the_native_scripts() -> None:
    """The deep-forest miner runs THESE. Three per layer is the floor and every one is native."""
    for layer in MO.SOURCE_LAYERS:
        if layer in MO.LAYER_ABSENCES:
            continue
        rows = MO.QUERY_TERRITORIES.get(layer, ())
        assert len(rows) >= 3, f"layer {layer}: only {len(rows)} query territories"
        assert any(MO.has_han(q) for q in rows), f"layer {layer}: no Han-script territory"


def test_every_source_carries_three_independent_labels_and_a_query() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in MO.SOURCE_CLASSES:
        assert row["access_label"] in MO.ACCESS_LABELS
        assert row["credibility"] in MO.CREDIBILITY_LABELS
        assert row["predictive_state"] in MO.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no native-language query"
        assert row["roots"], f"{row['id']} has no crawlable root"


def test_all_ten_source_layers_are_populated_or_declared_absent() -> None:
    """The principal's depth rule: ten layers, none of them blank."""
    counts = MO.layer_counts()
    assert set(counts) == set(MO.SOURCE_LAYERS)
    coverage = MO.source_layer_coverage()
    blank = [layer for layer, n in counts.items() if not n]
    assert all(layer in MO.LAYER_ABSENCES for layer in blank), (
        f"blank layers with no declared reason: {blank}")
    assert coverage["n_layers_covered"] + len(MO.LAYER_ABSENCES) == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible for a market "
        "whose only true consensus number lives on a paid terminal")
    assert coverage["low_weight_kept"], "no fringe ground is kept at all, so it was dropped"


# ------------------------------------------------------------------------------ the calendars
def test_the_dual_calendar_resolves_for_every_declared_year() -> None:
    """BOTH religious calendars, in every year, with every date inside its own year."""
    for year in (2024, 2025, 2026):
        table = holiday_table(MO.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        # the Chinese half and the Catholic half are both present in every year
        assert any("農曆正月初一" in name for name in table.values()), year
        assert any("Sexta-feira Santa" in name for name in table.values()), year
        assert f"{year}-12-20" in table, "SAR Establishment Day is a fixed solar date"
        assert f"{year}-11-02" in table, "All Souls' Day is a fixed Catholic date"


def test_easter_is_computed_and_good_friday_falls_two_days_before_it() -> None:
    """The Catholic half of Macau's calendar is DERIVABLE and is therefore derived."""
    assert MO.easter(2024) == date(2024, 3, 31)
    assert MO.easter(2025) == date(2025, 4, 20)
    assert MO.easter(2026) == date(2026, 4, 5)
    for year, good_friday in ((2024, date(2024, 3, 29)), (2025, date(2025, 4, 18)),
                              (2026, date(2026, 4, 3))):
        movable = MO.catholic_movable(year)
        assert good_friday in movable, f"Good Friday {year} is {good_friday}"
        assert (MO.easter(year) - date.fromisoformat(good_friday.isoformat())).days == 2
        assert len(movable) == 2, "Good Friday AND the day before Easter"


def test_the_lunar_half_is_typed_with_its_authority_and_never_invented() -> None:
    """A lunar date no rule computes is typed with the gazette named -- that is honest; a wrong
    rule is not."""
    authority = str(MO.HOLIDAYS_RULE["authority"])
    assert "Government Printing Bureau" in authority
    assert "Imprensa Oficial" in authority, "the authority must be named in BOTH languages"
    assert "gazetted" in MO.HOLIDAYS_RULE["rule"].lower()
    for year, rows in MO.LUNAR_GENERAL.items():
        for day, _name, status in rows:
            assert day.year == year
            assert status in MO.HOLIDAY_STATUSES
    assert all(st == "GAZETTED" for *_, st in MO.LUNAR_GENERAL[2024])
    assert any(st == "PROJECTED" for *_, st in MO.LUNAR_GENERAL[2026]), (
        "a 2026 lunar row the Bureau's table has not been read for must say PROJECTED")
    assert date(2025, 1, 29) in MO.gazetted_dates(2025), "Lunar New Year 2025 day 1"


def test_the_first_working_day_clock_is_what_the_dicj_actually_publishes_on() -> None:
    """THE PACK'S MOST LOAD-BEARING FUNCTION. The release is NOT the 1st: January opens on a
    general holiday, October opens on two, and each answer below is hand-checkable."""
    assert MO.first_working_day(2025, 1) == date(2025, 1, 2), "1 Jan is a general holiday"
    assert MO.first_working_day(2025, 2) == date(2025, 2, 3), "1-2 Feb 2025 is a weekend"
    assert MO.first_working_day(2025, 10) == date(2025, 10, 3), "1-2 Oct are National Day"
    assert MO.first_working_day(2024, 4) == date(2024, 4, 1), "1 Apr 2024 is a plain Monday"
    for year in (2024, 2025, 2026):
        days = MO.ggr_release_days(year)
        assert len(days) == 12
        assert all(d.weekday() < 5 for d in days), "a release day is never a weekend"
        assert all(not MO.is_market_holiday(d) for d in days)
        assert all(d.month == m for m, d in zip(range(1, 13), days, strict=True))


def test_macau_does_not_substitute_a_weekend_holiday_the_way_hong_kong_does() -> None:
    """The distinguishing calendar fact against the sibling SAR: a holiday at the weekend is
    LOST here, so the two closed sets diverge in weeks that look identical on a lunar calendar."""
    assert "no weekend substitution" in MO.HOLIDAYS_RULE["rule"].lower()
    lost = [d for d in MO.national_holidays(2024) if d.weekday() >= 5]
    assert lost, "no 2024 general holiday fell at a weekend, which is implausible"
    for day in lost:
        assert day not in MO.market_holidays(2024), (
            "a weekend closure costs no session and must not enter a liquidity sample as one")


# ------------------------------------------------------------------------------ the mechanisms
def test_the_double_peg_is_computed_and_not_asserted() -> None:
    """MOP 1.03 = HKD 1.00, and the HKD inside 7.7500/7.8500: the corridor is arithmetic."""
    mid = MO.peg_chain(7.8000)
    assert mid["usdmop"] == pytest.approx(8.034, abs=1e-9)
    assert mid["band_position"] == pytest.approx(0.5, abs=1e-12)
    strong = MO.peg_chain(7.7500)
    weak = MO.peg_chain(7.8500)
    assert strong["band_position"] == pytest.approx(0.0, abs=1e-12)
    assert weak["band_position"] == pytest.approx(1.0, abs=1e-12)
    assert strong["usdmop"] == pytest.approx(mid["usdmop_strong"], abs=1e-12)
    assert weak["usdmop"] == pytest.approx(mid["usdmop_weak"], abs=1e-12)
    assert mid["usdmop_strong"] < mid["usdmop"] < mid["usdmop_weak"]
    assert mid["mop_band_low"] < MO.MOP_PER_HKD < mid["mop_band_high"]


def test_the_hong_kong_band_is_named_as_another_packs_and_not_re_derived() -> None:
    """The `hk` pack owns the band. Duplicating it would be two packs measuring one mechanism."""
    hk = [r for r in MO.INTERACTIONS if r["with"] == "hk"]
    assert hk, "the double peg's own sibling interaction is missing"
    assert "hk` pack owns the band" in hk[0]["mechanism"] or "owns the band" in hk[0]["mechanism"]
    assert resolve(hk[0]["targets"])["absent"] == []
    assert {r["with"] for r in MO.INTERACTIONS} >= {"hk", "cn"}


def test_cot_and_the_domestic_market_are_declared_absent_rather_than_missing() -> None:
    """No pataca contract exists anywhere and Macau has no securities exchange at all."""
    rows = [r for r in MO.POSITIONING_SOURCES if not r["available"]]
    assert len(rows) >= 2, "the COT and the no-exchange questions are not both answered"
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in rows)
    blob = " ".join(str(c["constraint"]) + str(c["consequence"]) for c in MO.ACCESS_CONSTRAINTS)
    assert "NO SECURITIES EXCHANGE" in blob.upper()
    assert "two-lane" in blob


# ------------------------------------------------------------------------------ the cells
def test_cells_are_minted_for_the_gauntlet_and_every_one_is_executable() -> None:
    """THE POINT OF A PACK IS CELLS REACHING THE ONE GAUNTLET. Each must name a real condition
    and a symbol the box can trade."""
    rows = MO.cells()
    assert 60 <= len(rows) <= 200, f"{len(rows)} cells is outside the honest range"
    assert len(rows) == len(MO.CELLS)
    ids = {r["cell_id"] for r in rows}
    assert len(ids) == len(rows), "a duplicated cell_id is a double-counted trial"
    domain_ids = {d["id"] for d in MO.DOMAINS}
    execs = set(MO.EXECUTABLE_INSTRUMENTS)
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
    assert len(MO.DATASETS) >= 14
    layers_assets = set()
    for ds in MO.DATASETS:
        assert len(str(ds["how_to_fetch"])) > 40, f"{ds['name']}: fetch route is too vague"
        assert ds["assets"], f"{ds['name']}: names no asset"
        assert resolve(ds["assets"])["absent"] == [], f"{ds['name']}: absent asset"
        assert resolve(ds["assets"])["equities"] == [], f"{ds['name']}: equity asset"
        layers_assets |= set(ds["assets"])
    assert len(layers_assets) >= 6, "the catalogue reaches too few instruments"
    assert any(not ds["pit_feasible"] for ds in MO.DATASETS), (
        "every dataset claims point-in-time feasibility, which is implausible for a market "
        "whose only consensus is edited in place")


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {f"custom:{name}" for name in MO.MINERS}
    assert all(callable(fn) for fn in got.values())


def test_custom_miner_rows_name_known_domains_and_match_the_miners_table() -> None:
    """The two registrations -- CUSTOM_MINERS and MINERS -- must be one set."""
    ids = {d["id"] for d in MO.DOMAINS}
    entries = set()
    for row in MO.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.mo.pack", row["entry"]
        assert callable(getattr(MO, func)), f"{row['entry']} does not resolve"
        entries.add(func)
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    assert entries == set(MO.MINERS)
    for did in MO.MINER_DOMAINS.values():
        assert set(did) <= ids


def test_mine_returns_a_report_and_emits_nothing_to_the_registry() -> None:
    """`mine(None)` is a pure-python pass: it reads the pack's own tables and records nothing."""
    report = MO.mine(None)
    assert report["code"] == "MO"
    assert report["emitted"] == len(MO.MINERS)
    assert report["cells_emitted"] == len(MO.cells())
    assert report["layers"] == 10
    assert report["unmeasured"], "a pack that can see everything is a pack that did not look"
    assert date.fromisoformat(str(report["at"]))
    assert set(report["interactions"]) == {r["with"] for r in MO.INTERACTIONS}
    for row in report["rows"]:
        assert row["n"] >= 1, f"{row['miner']} emitted nothing at all"


def test_mine_records_through_a_ctx_when_one_is_given() -> None:
    """When a department Ctx is handed in, every miner's result goes through `ctx.record`."""
    seen: list[Any] = []

    class Ctx:
        def record(self, row: Any) -> None:
            seen.append(row)

    report = MO.mine(Ctx())
    assert len(seen) == len(MO.MINERS) == report["emitted"]
    assert all(isinstance(r, dict) and r.get("rows") is not None for r in seen)
