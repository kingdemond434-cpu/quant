"""THE MEKONG PACK, VALIDATED -- three jurisdictions, three scripts, and a measured vacuum.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A THREE-COUNTRY PACK THAT ANSWERS FOR ONE. `JURISDICTIONS` is what the parity fence counts,
    so it is asserted against the forest roster, and the actor count, the script coverage and
    the per-jurisdiction gap table are all checked so that "mm, kh, la" is a measurement rather
    than a claim.
  * AN ENGLISH-ONLY CRAWL OF THREE WRITING SYSTEMS. Burmese, Khmer and Lao occupy three separate
    Unicode blocks and the Lao block sits immediately after the Thai one. All three are asserted
    present, and Lao is asserted NOT to be matched as Thai.
  * A PADDED ROW WHERE A HOLE SHOULD BE. Myanmar's statistics stopped in 2021, Laos has no
    domestic academic economics ground and none of the three has a retail trading ecology. Each
    gap must be declared per jurisdiction WITH a lawful substitute named beside it.
  * A SPLICED TWO-RATE SERIES. An administered rate and a parallel rate are two objects that
    coexist; `parallel_spread` is asserted on named inputs and the pack must say so in prose.
  * A SYMBOL THE BOX CANNOT TRADE. Three currencies, rare earths, rice and electricity are all
    absent and must stay transmission targets with their controls named.
  * A PACK THAT REACHES THE FRAMEWORK BENT. `CountryPack` coerces every row; a coercion note is
    a field the framework could not read, and this pack must produce none -- which is why
    REGION_COMMAND is the framework's canonical token and not this pack's own grouping.
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
from countries.mekong import pack as MK  # type: ignore[import-not-found]  # noqa: E402

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
    got = CL.resolve_pack("mekong")
    assert got is not None, "no Mekong pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass.
    A multi-jurisdiction pack owes ~6 actors per country, so the floors are raised here."""
    assert check_pack(MK.as_dict(), min_actors=16, min_domains=13, min_edges=11) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == "mekong"
    assert str(get(built, "region_command")) == "asia"
    assert str(get(built, "currency")) == "MMK"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    """A coercion note is a field `CountryPack` could not read. There must be none -- which is
    why REGION_COMMAND carries the framework's canonical token and not "southeast_asia"."""
    notes = list(getattr(built, "coercion_notes", ()) or ())
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on this pack: {fatal[:4]}"
    assert MK.REGION_COMMAND in CL.REGION_COMMANDS
    assert CL.canonical_command("southeast_asia") == MK.REGION_COMMAND, (
        "this pack's own grouping must map onto the token it declares, or the framework "
        "would file it somewhere nobody reads")


def test_three_jurisdictions_are_declared_and_all_on_the_desks_own_roster() -> None:
    """THE PARITY FENCE COUNTS `JURISDICTIONS`. A multi-country pack that declares nothing is
    credited with ONE country by directory name, which would lose two of these three."""
    assert set(MK.JURISDICTIONS) == {"mm", "kh", "la"}
    assert all(c == c.lower() and len(c) == 2 for c in MK.JURISDICTIONS)
    roster = {c.lower() for f in FORESTS.FORESTS.values()
              for c in getattr(f, "countries", ())}
    assert roster, "the forest roster is unreadable -- UNMEASURED, so nothing here is checked"
    for code in MK.JURISDICTIONS:
        assert code in roster, f"{code} is not on the desk's own forest roster"
    assert "mekong" in FORESTS.FORESTS["asean"].packs, (
        "the pack exists and the forest does not name it, so no forest run reaches it")


def test_each_jurisdiction_declares_its_own_currency_and_fiscal_year() -> None:
    """The framework carries ONE currency and ONE fiscal year end; three countries do not share
    either, and a pack that published one for three would mis-time two treasuries."""
    assert MK.CURRENCIES == {"mm": "MMK", "kh": "KHR", "la": "LAK"}
    assert MK.CURRENCY in MK.CURRENCIES.values()
    assert set(MK.FISCAL_YEAR_ENDS) == set(MK.JURISDICTIONS)
    assert MK.FISCAL_YEAR_ENDS["mm"] == "03-31", "Myanmar's fiscal year runs April to March"
    assert MK.FISCAL_YEAR_ENDS["kh"] == MK.FISCAL_YEAR_ENDS["la"] == "12-31"
    assert {r["jurisdiction"] for r in MK.CENTRAL_BANKS} == set(MK.JURISDICTIONS), (
        "three jurisdictions, three central banks; a miner steered at Cambodia must not read "
        "Myanmar's peg row and conclude Cambodia has one")


def test_pack_reaches_its_declared_parity_depth(built: Any) -> None:
    """The standing depth rule, measured by the framework and not claimed by the pack."""
    row = RP.pack_depth(built, "mekong").as_row()
    assert row["score"] >= DECLARED_DEPTH, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_depth_counts_are_sized_for_three_jurisdictions() -> None:
    """Twelve actors is the single-country floor; a three-country pack owes about six each."""
    assert len(MK.ACTORS) >= 16
    assert len(MK.DOMAINS) >= 13
    assert len(MK.TRANSMISSION_EDGES_SEED) >= 11
    assert len(MK.DATASETS) >= 17
    assert len(MK.SOURCE_CLASSES) >= 24
    assert len(MK.POLICY_ERAS) >= 5
    assert len(MK.INTERACTIONS) >= 4
    assert MK.term_count() >= 80


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    for row in MK.ACTORS:
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
    for row in MK.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert row["conditions"], f"domain {row['id']} names no conditioning state"


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(MK.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert "USDTHB" in MK.EXECUTABLE_INSTRUMENTS, (
        "Thailand is the downstream of all three; without USDTHB the pack has no primary leg")


def test_no_single_name_equity_anywhere_in_the_pack() -> None:
    """The region's listed companies are illiquid domestic names and a few foreign parents.
    Under the two-lane order (2026-09-06) none may appear as an instrument."""
    pools: list[tuple[str, tuple[str, ...]]] = [("executables", MK.EXECUTABLE_INSTRUMENTS)]
    pools += [(f"domain {d['id']}", tuple(d["instruments"])) for d in MK.DOMAINS]
    pools += [(f"edge {e['id']}", tuple(e["targets"])) for e in MK.TRANSMISSION_EDGES_SEED]
    pools += [(f"interaction {r['with']}", tuple(r["targets"])) for r in MK.INTERACTIONS]
    pools += [(f"transmission target {t['name']}", tuple(t["proxies"]))
              for t in MK.TRANSMISSION_TARGETS]
    pools += [(f"dataset {d['name']}", tuple(d["assets"])) for d in MK.DATASETS]
    pools += [(f"actor {a['name']}", tuple(a["instruments"])) for a in MK.ACTORS]
    for where, symbols in pools:
        split = resolve(symbols)
        assert split["equities"] == [], f"{where}: {split['equities']} is a single-name equity"
        assert split["absent"] == [], f"{where}: {split['absent']} is not in the registry"


def test_every_transmission_seed_names_tradable_targets() -> None:
    """A seed that terminates in a symbol the box cannot quote can never compile a cell."""
    for seed in MK.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"


def test_all_three_currencies_and_the_untraded_commodities_are_named_absent() -> None:
    """THREE CURRENCIES, NONE QUOTED -- and neither are rare earths, rice or electricity. A pack
    that hid any of them would be routing its main mechanisms into a symbol by accident."""
    registry = universe_symbols()
    assert not {"USDMMK", "USDKHR", "USDLAK", "MMK", "KHR", "LAK"} & set(registry)
    assert not {"RICE", "ROUGHRICE", "DYSPROSIUM", "POWER"} & set(registry)
    named = " ".join(str(t["name"]) for t in MK.TRANSMISSION_TARGETS)
    for must in ("MMK", "KHR", "LAK", "rare earth", "hydroelectricity", "rice"):
        assert must.lower() in named.lower(), f"{must} is not named as a transmission target"
    for row in MK.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == []
        assert resolve(row["proxies"])["equities"] == []


# ------------------------------------------------------------------------------ the languages
def test_all_three_domestic_scripts_are_carried_and_lao_is_not_read_as_thai() -> None:
    """THREE WRITING SYSTEMS. The Lao block sits immediately after the Thai one, and a crawler
    that conflates them reads Vientiane's ground with Bangkok's vocabulary and finds nothing."""
    coverage = MK.script_coverage()
    for script in ("burmese", "khmer", "lao"):
        assert coverage[script] >= 15, f"only {coverage[script]} terms in {script}"
    assert coverage["thai"] >= 4, "the Thai mirror vocabulary is how the buyer's books are read"
    assert coverage["han"] >= 4, "the Chinese mirror is the only measurement of the Kachin flow"
    assert MK.has_script("ကျပ်", "burmese") and not MK.has_script("ကျပ်", "khmer")
    assert MK.has_script("រៀល", "khmer") and not MK.has_script("រៀល", "lao")
    assert MK.has_script("ກີບ", "lao"), "the kip must be matched as Lao"
    assert not MK.has_script("ກີບ", "thai"), (
        "Lao must NOT be matched as Thai -- the two blocks are adjacent and the confusion is "
        "the single commonest script error about this jurisdiction group")
    assert not MK.has_script("ข้าว", "lao"), "and Thai must not be matched as Lao either"
    assert set(MK.JURISDICTION_SCRIPTS) == set(MK.JURISDICTIONS)
    for code, script in MK.JURISDICTION_SCRIPTS.items():
        assert MK.script_terms(script), f"{code} has no terminology in its own script"


def test_every_layers_queries_are_written_in_the_native_scripts() -> None:
    """A query in English finds an English article about the border, not the border."""
    terms = MK.layer_terms()
    native = [layer for layer, qs in terms.items()
              if any(any(MK.has_script(q, s) for s in ("burmese", "khmer", "lao")) for q in qs)]
    assert len(native) >= 9, f"only {native} carry a Burmese, Khmer or Lao query"
    mirror = [layer for layer, qs in terms.items()
              if any(any(MK.has_script(q, s) for s in ("thai", "han")) for q in qs)]
    assert len(mirror) >= 3, f"only {mirror} carry a Thai or Chinese mirror query"
    counted = sum(1 for row in MK.SOURCE_CLASSES if row["machine_use_allowed"]
                  for q in row["queries"]
                  if any(MK.has_script(q, s) for s in ("burmese", "khmer", "lao")))
    assert counted >= 40, f"only {counted} native-script queries across crawlable sources"


def test_query_territories_cover_every_live_layer_in_the_native_scripts() -> None:
    """The deep-forest miner runs THESE. Three per layer is the floor and every one is native."""
    for layer in MK.SOURCE_LAYERS:
        if layer in MK.LAYER_ABSENCES:
            continue
        rows = MK.QUERY_TERRITORIES.get(layer, ())
        assert len(rows) >= 3, f"layer {layer}: only {len(rows)} query territories"
        assert any(any(MK.has_script(q, s) for s in ("burmese", "khmer", "lao", "thai", "han"))
                   for q in rows), f"layer {layer}: no native or mirror-script territory"


def test_every_source_carries_three_independent_labels_and_a_query() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in MK.SOURCE_CLASSES:
        assert row["access_label"] in MK.ACCESS_LABELS
        assert row["credibility"] in MK.CREDIBILITY_LABELS
        assert row["predictive_state"] in MK.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no native-language query"
        assert row["roots"], f"{row['id']} has no crawlable root"


def test_all_ten_layers_are_sourced_and_every_gap_names_a_lawful_substitute() -> None:
    """THE PACK'S MOST VALUABLE TABLE. A layer covered by Cambodia is not coverage of Myanmar,
    so the refusals are PER JURISDICTION and each one names what stands in for it."""
    counts = MK.layer_counts()
    assert set(counts) == set(MK.SOURCE_LAYERS)
    coverage = MK.source_layer_coverage()
    blank = [layer for layer, n in counts.items() if not n]
    assert all(layer in MK.LAYER_ABSENCES for layer in blank), (
        f"blank layers with no declared reason: {blank}")
    assert coverage["n_layers_covered"] + len(MK.LAYER_ABSENCES) == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], "no licensed ground is registered at all"
    assert coverage["low_weight_kept"], "no fringe ground is kept at all, so it was dropped"
    assert len(MK.NO_LAWFUL_GROUND) >= 6, "three frontier economies with fewer than six holes "\
                                          "is a padded table, not a measurement"
    for row in MK.NO_LAWFUL_GROUND:
        assert row["jurisdiction"] in MK.JURISDICTIONS
        assert row["layer"] in MK.SOURCE_LAYERS
        assert len(row["reason"]) > 40, f"{row['jurisdiction']}/{row['layer']}: reason too thin"
        assert len(row["substitute"]) > 30, (
            f"{row['jurisdiction']}/{row['layer']}: a declared absence with no lawful substitute "
            f"is a blank with a note on it")
    gaps = {r["jurisdiction"] for r in MK.NO_LAWFUL_GROUND}
    assert gaps == set(MK.JURISDICTIONS), "every jurisdiction owes an honest gap list"
    assert MK.jurisdiction_gaps("mm"), "Myanmar's statistical vacuum must be declared by name"
    assert any("2021" in r["reason"] for r in MK.jurisdiction_gaps("mm"))
    assert any(r["layer"] == "academic" for r in MK.jurisdiction_gaps("la"))


# ------------------------------------------------------------------------------ the calendars
def test_the_union_holiday_table_resolves_for_every_declared_year() -> None:
    """Every declared year, with every date inside its own year, tagged by jurisdiction."""
    for year in (2024, 2025, 2026):
        table = holiday_table(MK.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        assert f"{year}-04-14" in table, "the mid-April block is fixed in every year"
        assert f"{year}-12-02" in table, "Lao National Day is a fixed solar date"
        assert f"{year}-01-04" in table, "Myanmar Independence Day is a fixed solar date"
        tagged = [n for n in table.values() if MK.jurisdictions_closed(n)]
        assert len(tagged) >= 15, f"{year}: too few rows carry a jurisdiction tag"


def test_the_mid_april_week_stops_all_three_at_once() -> None:
    """THE PACK'S DISTINGUISHING CALENDAR FACT: Thingyan, Chaul Chnam Thmey and Pi Mai in one
    week, with Thai Songkran next door -- one regional stoppage, not four coincidences."""
    for year in (2024, 2025, 2026):
        week = MK.new_year_week(year)
        assert week["window"] == (f"{year}-04-13", f"{year}-04-17")
        assert len(week["days"]) == 5
        assert week["max_simultaneous"] == 3, (
            "at the peak of the block all three jurisdictions must be closed together")
        assert 3 <= int(week["weekday_sessions_lost"]) <= 5
        assert "th" in str(week["thai_songkran"]).lower() or "Songkran" in str(
            week["thai_songkran"])
    assert MK.jurisdictions_closed("[mm|kh|la] Thingyan / Chaul Chnam Thmey / Pi Mai day 2") == (
        "mm", "kh", "la")
    assert MK.jurisdictions_closed("[mm] Martyrs' Day") == ("mm",)
    assert MK.jurisdictions_closed("something with no tag") == ()


def test_one_full_moon_closes_all_three_countries() -> None:
    """The three Theravada calendars share their full moons, so several closures are REGIONAL
    rather than national -- which a single-country holiday study cannot see."""
    for year in (2024, 2025, 2026):
        shared = [n for n in MK.national_holidays(year).values()
                  if len(MK.jurisdictions_closed(n)) == 3]
        assert len(shared) >= 4, f"{year}: only {len(shared)} three-country closures"
        assert any("Visak" in n or "Visakha" in n for n in shared), (
            "the Kason/Visak/Visakha full moon closes all three on one date and must be marked")


def test_the_lunisolar_half_is_typed_with_its_authority_and_never_claimed_as_notified() -> None:
    """A lunisolar date no rule computes is typed with the authority named. NOTIFIED is reserved
    for a row actually read in a government notification, and none has been -- which is a
    measurement of the desk's own coverage, not an omission."""
    authority = str(MK.HOLIDAYS_RULE["authority"])
    for must in ("Myanmar", "Cambodian", "Lao", "notification"):
        assert must in authority, f"the authority text does not name {must}"
    statuses = {st for rows in MK.LUNISOLAR.values() for *_, st in rows}
    assert statuses <= set(MK.HOLIDAY_STATUSES)
    assert "NOTIFIED" not in statuses, (
        "no row may claim NOTIFIED until the crawler has read the notification; claiming it "
        "would be the exact failure the status field exists to prevent")
    assert all(st == "PROJECTED" for *_, st in MK.LUNISOLAR[2026])
    assert all(st == "TYPED" for *_, st in MK.LUNISOLAR[2024])
    for year, rows in MK.LUNISOLAR.items():
        for day, _name, _st in rows:
            assert day.year == year
    assert MK.typed_dates(2024), "2024 must have typed rows"
    assert not MK.typed_dates(2026), "2026 is projected throughout and must have none"


def test_one_jurisdictions_calendar_can_be_filtered_out_of_the_union() -> None:
    """A miner steered at Cambodia must not treat Burmese Martyrs' Day as a Cambodian closure."""
    kh = MK.holidays_for("kh", 2025)
    mm = MK.holidays_for("mm", 2025)
    assert date(2025, 1, 7) in kh, "Victory over Genocide Day is Cambodian"
    assert date(2025, 1, 7) not in mm
    assert date(2025, 7, 19) in mm, "Martyrs' Day is Burmese"
    assert date(2025, 7, 19) not in kh
    assert date(2025, 4, 15) in kh and date(2025, 4, 15) in mm, "the April block is shared"
    lost = [d for d in MK.national_holidays(2025) if d.weekday() >= 5]
    for day in lost:
        assert day not in MK.market_holidays(2025), (
            "a weekend closure costs no factory shift and must not enter a sample as one")


# ------------------------------------------------------------------------------ the mechanisms
def test_the_two_rate_spread_is_arithmetic_and_the_rates_are_never_spliced() -> None:
    """An administered rate and a parallel rate are two objects that coexist. The GAP is the
    capital-control intensity measure and the pack must say so in prose as well as in code."""
    unified = MK.parallel_spread(2100.0, 2120.0)
    assert unified["bucket"] == "EFFECTIVELY_UNIFIED"
    # the pack rounds the spread to six decimals: the parallel leg is a changer's quote, not a
    # screen price, and printing more digits than the quote has would be a false precision
    assert unified["spread"] == pytest.approx((2120 - 2100) / 2100, abs=1e-6)
    assert MK.parallel_spread(2100.0, 2400.0)["bucket"] == "MILD_RATIONING"
    assert MK.parallel_spread(2100.0, 3000.0)["bucket"] == "WIDE_RATIONING"
    crisis = MK.parallel_spread(2100.0, 4500.0)
    assert crisis["bucket"] == "REGIME_STRESS"
    assert crisis["spread_pct"] > 100.0
    bad = MK.parallel_spread(0.0, 4500.0)
    assert bad["bucket"] == "UNMEASURED" and bad["spread"] is None
    blob = " ".join(str(d["notes"]) for d in MK.DOMAINS) + str(MK.CENTRAL_BANK)
    assert "splice" in blob.lower() or "SPLICE" in blob


def test_the_hydro_bound_is_a_ratio_and_the_two_tails_are_not_symmetric() -> None:
    """A metre reading means nothing without the station's datum, so the constraint is a ratio
    of that station's own seasonal median -- and low water binds while high water does not."""
    drought = MK.hydro_bound(0.40)
    assert drought["bucket"] == "SEVERE_DROUGHT" and drought["binds_generation"] is True
    assert MK.hydro_bound(0.65)["bucket"] == "BELOW_MEDIAN"
    assert MK.hydro_bound(0.65)["binds_generation"] is True
    normal = MK.hydro_bound(1.00)
    assert normal["bucket"] == "NORMAL" and normal["binds_generation"] is False
    assert MK.hydro_bound(1.35)["bucket"] == "ABOVE_MEDIAN"
    flood = MK.hydro_bound(1.80)
    assert flood["bucket"] == "FLOOD" and flood["binds_generation"] is False, (
        "high water does not raise a CONTRACTED volume beyond plant capacity; a symmetric "
        "specification would be wrong by construction")
    assert "gas" in str(normal["control"]).lower(), (
        "the Thai gas-burn substitution is the transmission and must be named on every row")
    assert MK.hydro_bound(0.9, "Pakse")["station"] == "Pakse"


def test_dollarisation_is_bucketed_with_its_two_neighbouring_controls_named() -> None:
    """The natural experiment only works if the controls are named: Laos, whose float collapsed,
    and Vietnam, whose managed rate did not, over the same decade and the same shocks."""
    heavy = MK.dollarisation_state(0.90)
    assert heavy["bucket"] == "EFFECTIVELY_DOLLARISED"
    assert MK.dollarisation_state(0.70)["bucket"] == "HEAVILY_DOLLARISED"
    assert MK.dollarisation_state(0.45)["bucket"] == "PARTIALLY_DOLLARISED"
    assert MK.dollarisation_state(0.10)["bucket"] == "MOSTLY_LOCAL"
    assert MK.dollarisation_state(1.5)["bucket"] == "UNMEASURED"
    controls = " ".join(str(c) for c in heavy["controls"])
    assert "la" in controls and "vn" in controls
    assert heavy["policy_tools"], "a dollarised central bank still has tools and they are named"


def test_the_downstream_packs_are_named_and_not_re_derived() -> None:
    """Every significant mechanism here terminates in a neighbour's grid, factory or customs
    table, so the sibling that owns the other end must be named."""
    assert next(r["with"] for r in MK.INTERACTIONS) == "th", (
        "Thailand is the downstream of all three and is named FIRST; the ordering is the claim")
    assert {r["with"] for r in MK.INTERACTIONS} >= {"th", "vn", "cn"}
    for row in MK.INTERACTIONS:
        assert row["control"], f"interaction with {row['with']} has no control"
        assert row["observable"], f"interaction with {row['with']} has no observable"
        assert resolve(row["targets"])["absent"] == []
    th = next(r for r in MK.INTERACTIONS if r["with"] == "th")
    assert "`th` pack owns" in th["mechanism"]


def test_positioning_and_the_domestic_markets_are_declared_absent_rather_than_missing() -> None:
    """No contract exists on any of the three currencies and no exchange has a usable tape."""
    rows = [r for r in MK.POSITIONING_SOURCES if not r["available"]]
    assert len(rows) >= 2, "the COT and the no-tape questions are not both answered"
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in rows)
    blob = " ".join(str(c["constraint"]) + str(c["consequence"]) for c in MK.ACCESS_CONSTRAINTS)
    assert "NO BROKER CONTRACT EXISTS" in blob.upper()
    assert "UTC+6:30" in blob, (
        "Myanmar's half-hour offset is the commonest conversion error about this jurisdiction "
        "and must be called out where a miner will read it")
    assert MK.COT_CURRENCY == ""
    assert MK.RETAIL_LEVERAGE_REGIME == "UNMEASURED"


# ------------------------------------------------------------------------------ the cells
def test_cells_are_minted_for_the_gauntlet_and_every_one_is_executable() -> None:
    """THE POINT OF A PACK IS CELLS REACHING THE ONE GAUNTLET. Each must name a real condition
    and a symbol the box can trade."""
    rows = MK.cells()
    assert 60 <= len(rows) <= 200, f"{len(rows)} cells is outside the honest range"
    assert len(rows) == len(MK.CELLS)
    ids = {r["cell_id"] for r in rows}
    assert len(ids) == len(rows), "a duplicated cell_id is a double-counted trial"
    domain_ids = {d["id"] for d in MK.DOMAINS}
    execs = set(MK.EXECUTABLE_INSTRUMENTS)
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
    assert len(MK.DATASETS) >= 17
    reached = set()
    for ds in MK.DATASETS:
        assert len(str(ds["how_to_fetch"])) > 40, f"{ds['name']}: fetch route is too vague"
        assert ds["assets"], f"{ds['name']}: names no asset"
        assert resolve(ds["assets"])["absent"] == [], f"{ds['name']}: absent asset"
        reached |= set(ds["assets"])
    assert len(reached) >= 9, "the catalogue reaches too few instruments"
    assert any(not ds["pit_feasible"] for ds in MK.DATASETS), (
        "every dataset claims point-in-time feasibility, which is implausible for three "
        "countries whose rate pages are overwritten daily")
    blob = " ".join(str(ds["how_to_fetch"]) + str(ds["source"]) for ds in MK.DATASETS)
    assert "Comtrade" in blob, "the partner-reported mirror is the declared substitute"
    assert "customs.gov.cn" in blob, "the Chinese mirror is the only count of the Kachin flow"


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {f"custom:{name}" for name in MK.MINERS}
    assert all(callable(fn) for fn in got.values())


def test_custom_miner_rows_name_known_domains_and_match_the_miners_table() -> None:
    """The two registrations -- CUSTOM_MINERS and MINERS -- must be one set."""
    ids = {d["id"] for d in MK.DOMAINS}
    entries = set()
    for row in MK.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.mekong.pack", row["entry"]
        assert callable(getattr(MK, func)), f"{row['entry']} does not resolve"
        entries.add(func)
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    assert entries == set(MK.MINERS)
    for did in MK.MINER_DOMAINS.values():
        assert set(did) <= ids


def test_mine_returns_a_report_and_emits_nothing_to_the_registry() -> None:
    """`mine(None)` is a pure-python pass: it reads the pack's own tables and records nothing."""
    report = MK.mine(None)
    assert report["code"] == "MEKONG"
    assert report["emitted"] == len(MK.MINERS)
    assert report["cells_emitted"] == len(MK.cells())
    assert report["layers"] == 10
    assert tuple(report["jurisdictions"]) == MK.JURISDICTIONS
    assert len(report["unmeasured"]) >= len(MK.ACCESS_CONSTRAINTS) + len(MK.NO_LAWFUL_GROUND), (
        "the measured refusals are part of the report, not a footnote to it")
    assert date.fromisoformat(str(report["at"]))
    assert set(report["interactions"]) == {r["with"] for r in MK.INTERACTIONS}
    for row in report["rows"]:
        assert row["n"] >= 1, f"{row['miner']} emitted nothing at all"


def test_mine_records_through_a_ctx_when_one_is_given() -> None:
    """When a department Ctx is handed in, every miner's result goes through `ctx.record`."""
    seen: list[Any] = []

    class Ctx:
        def record(self, row: Any) -> None:
            seen.append(row)

    report = MK.mine(Ctx())
    assert len(seen) == len(MK.MINERS) == report["emitted"]
    assert all(isinstance(r, dict) and r.get("rows") is not None for r in seen)
