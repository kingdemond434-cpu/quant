"""THE PERU PACK, VALIDATED -- the conflict calendar, the published intervention, the metals.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A SPANISH-ONLY GLOSSARY OF A THREE-LANGUAGE COUNTRY. Quechua and Aymara are official
    languages under article 48 of the 1993 constitution wherever they predominate -- which is
    exactly where the mines and the blocked roads are. The community assembly that votes a
    blockade sits in Quechua. A crawler handed only Spanish reads the reaction and never the
    decision, so the vocabulary assertions below check all three languages by name.
  * A SYMBOL THE BOX CANNOT TRADE. Every executable instrument, every edge target and every
    interaction target is checked against the broker's OWN registry, not against a list somebody
    typed. The sol is absent and must stay a transmission target; so is the Chilean peso, which
    matters because USDCLP is the obvious control leg and it does not exist here.
  * A SINGLE-NAME EQUITY ON A DOCKET. The two-lane order (2026-09-06) forbids hunting one
    statistically and this pack is full of tempting national champions (Southern Copper,
    Buenaventura, Credicorp, Exalmar), every one of which appears only as an ACTOR.
  * A PACK THAT REACHES THE FRAMEWORK BENT. `CountryPack` coerces every row; a coercion note is
    a field the framework could not read, and this pack must produce none.
  * A LAYER NOBODY LOOKED AT. All ten source layers must be sourced or declared absent with a
    reason, and `regional_parity.pack_depth` must score at least the pack's declared depth.
  * A CELL COUNT THAT IS A CARTESIAN TRICK. `cells()` is checked for real conditions, for
    instruments that actually belong to the domain that minted them, and for the absence of any
    declared instrument that no domain ever uses.
  * A HOLIDAY TABLE SOMEBODY TYPED. Jueves and Viernes Santo are DERIVED from Easter with the
    anonymous Gregorian algorithm, and the Ley 31968 break of 2024 -- four new national feriados
    at once -- is asserted, because a pooled study that misses it mislabels four days a year.
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
from countries.pe import pack as PE  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as F  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it. Resolved through `resolve_pack` so the test measures
    the same object the country lab runs, not a private construction."""
    got = CL.resolve_pack("pe")
    assert got is not None, "no Peru pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(PE.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == "pe"
    assert str(get(built, "region_command")) == "latam"
    assert str(get(built, "currency")) == "PEN"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    """A coercion note is a field `CountryPack` could not read. There must be none."""
    notes = list(getattr(built, "coercion_notes", ()) or ())
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on this pack: {fatal[:4]}"


def test_jurisdictions_are_exactly_peru_and_on_the_desks_own_roster() -> None:
    """THE PARITY FENCE COUNTS THIS TUPLE. Peru is one of the countries the fence named as
    unanswered: `cl` is titled 'Chile (with Peru)' and declares no JURISDICTIONS, so it is
    credited with `cl` alone and `pe` was nobody's."""
    assert PE.JURISDICTIONS == ("pe",)
    assert all(c == c.lower() and len(c) == 2 for c in PE.JURISDICTIONS)
    roster = {c.lower() for forest in F.FORESTS.values() for c in forest.countries}
    for code in PE.JURISDICTIONS:
        assert code in roster, f"{code} is not on the forest roster in libs/research/forests.py"
    # the pack directory name and the declared jurisdiction agree, which is what stops the
    # fence from crediting one pack with a country another pack already answers for
    assert PE.CODE == "pe"


def test_pack_reaches_its_declared_parity_depth(built: Any) -> None:
    """The standing depth rule, MEASURED by the framework and not claimed by the pack."""
    row = RP.pack_depth(built, "pe").as_row()
    assert row["score"] >= PE.DECLARED_DEPTH, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_depth_counts_sit_above_the_floor_and_not_at_it() -> None:
    """Twelve actors is the floor; a country written to the floor is a country half-read."""
    assert len(PE.ACTORS) >= 16
    assert len(PE.DOMAINS) >= 13
    assert len(PE.TRANSMISSION_EDGES_SEED) >= 12
    assert len(PE.SOURCE_CLASSES) >= 22
    assert len(PE.DATASETS) >= 14
    assert len(PE.POLICY_ERAS) >= 6
    assert len(PE.INTERACTIONS) >= 4
    assert PE.term_count() >= 150


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    for row in PE.ACTORS:
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
    for row in PE.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert len(row["conditions"]) >= 3, f"domain {row['id']} names too few conditions"
        assert row["instruments"], f"domain {row['id']} names no instrument"
        assert row["id"] in PE.DOMAIN_CELL_SPEC, f"{row['id']} mints cells with no family"


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(PE.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert set(PE.EXECUTABLE_INSTRUMENTS) <= set(registry)


def test_every_transmission_seed_and_interaction_names_tradable_targets() -> None:
    """A seed that terminates in a symbol the box cannot quote can never compile a cell."""
    for seed in PE.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"
    for row in PE.INTERACTIONS:
        split = resolve(row["targets"])
        assert split["absent"] == [], f"interaction with {row['with']} -> {split['absent']}"
        assert split["equities"] == [], f"interaction with {row['with']} -> {split['equities']}"
        assert row["control"] and row["observable"] and row["mechanism"]


def test_domain_instruments_are_tradable_and_never_single_names() -> None:
    for row in PE.DOMAINS:
        split = resolve(row["instruments"])
        assert split["absent"] == [], f"domain {row['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"domain {row['id']} -> equity {split['equities']}"


def test_the_sol_and_the_chilean_peso_are_named_absent_rather_than_dropped() -> None:
    """PEN is not quoted here and neither is CLP -- and the second absence is the one that bites,
    because USDCLP is the natural 'Chile versus Peru' control and it cannot be traded."""
    registry = universe_symbols()
    assert not {"USDPEN", "PEN", "USDCLP", "CLP"} & set(registry)
    named = " ".join(str(t["name"]) for t in PE.TRANSMISSION_TARGETS)
    assert "PEN" in named and "CLP" in named and "CDR" in named
    for row in PE.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert row["route"], f"{row['name']} is named absent with no route"
        assert resolve(row["proxies"])["absent"] == []


def test_the_national_champions_appear_only_as_actors() -> None:
    """Southern Copper, Antamina, Las Bambas and the fishmeal processors are the loudest
    mechanisms in this economy and the two-lane order forbids hunting any of them."""
    actor_names = " ".join(str(a["name"]) for a in PE.ACTORS)
    for who in ("Las Bambas", "Southern Copper", "Antamina", "AFP"):
        assert who in actor_names, f"{who} is not carried as an actor"
    every_symbol: set[str] = set(PE.EXECUTABLE_INSTRUMENTS)
    for row in PE.DOMAINS:
        every_symbol |= set(row["instruments"])
    for seed in PE.TRANSMISSION_EDGES_SEED:
        every_symbol |= set(seed["targets"])
    assert resolve(sorted(every_symbol))["equities"] == []


# ------------------------------------------------------------------------------ the cells
def test_cells_are_real_and_every_declared_instrument_is_used() -> None:
    """THE POINT OF A PACK IS CELLS REACHING THE GAUNTLET. They must also be honest: each cell
    names a condition its own domain declared, on an instrument that domain owns."""
    rows = PE.cells()
    assert 60 <= len(rows) <= 260, f"{len(rows)} cells is outside the honest range"
    by_domain = {d["id"]: d for d in PE.DOMAINS}
    seen_ids: set[str] = set()
    for row in rows:
        for field in ("cell_id", "domain", "symbol", "condition", "mechanism_family",
                      "horizon", "control", "why"):
            assert row.get(field), f"cell {row.get('cell_id')} has an empty {field}"
        assert row["cell_id"] not in seen_ids, f"duplicate cell {row['cell_id']}"
        seen_ids.add(row["cell_id"])
        dom = by_domain[row["domain"]]
        assert row["symbol"] in dom["instruments"], (
            f"{row['cell_id']} names a symbol its own domain does not own")
        assert row["condition"] in dom["conditions"], (
            f"{row['cell_id']} names a condition its own domain never declared")
    unused = [s for s, n in PE.cells_by_symbol().items() if n == 0]
    assert unused == [], f"declared executable but no domain uses it: {unused}"


def test_mine_reports_the_cell_count_and_emits_nothing_without_a_ctx() -> None:
    """`mine(None)` is a MEASUREMENT of what the pack would emit and writes nowhere."""
    report = PE.mine(None)
    assert report["code"] == "pe"
    assert report["cells_emitted"] == len(PE.cells())
    assert report["emitted"] > 0
    assert report["rows"] and all(r.get("miner") for r in report["rows"])
    assert report["jurisdictions"] == ("pe",)
    assert "cl" in report["interactions"]
    # UNMEASURED is a real answer: the miners that need a series this box does not carry say so
    assert any("UNMEASURED" in u or "not loaded" in u or "not in this pack" in u
               for u in report["unmeasured"]), report["unmeasured"][:3]
    # nothing reached a registry: there is no connection and no ctx, so no discovery id exists
    assert "recorded" not in report


def test_every_custom_miner_entry_resolves(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {f"custom:{name}" for name in PE.MINERS}
    assert all(callable(fn) for fn in got.values())
    ids = {d["id"] for d in PE.DOMAINS}
    for row in PE.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.pe.pack", row["entry"]
        assert func in PE.MINERS, f"{row['entry']} is not in the MINERS table"
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    for domains in PE.MINER_DOMAINS.values():
        assert set(domains) <= ids


# ------------------------------------------------------------------------------ the languages
def test_terminology_carries_spanish_quechua_and_aymara() -> None:
    """Three languages, because Peru's conflicts are decided in two of them and reported in the
    third. Latin script is shared, so this is a VOCABULARY test rather than a codepoint one."""
    assert len(PE.accented_terms()) >= 40, (
        f"only {len(PE.accented_terms())} terms carry a Spanish diacritic -- this reads like an "
        f"English glossary of Peru")
    assert len(PE.spanish_terms()) == len(PE.SPANISH_MARKERS), (
        f"missing Spanish working vocabulary: "
        f"{sorted(set(PE.SPANISH_MARKERS) - set(PE.spanish_terms()))}")
    assert len(PE.quechua_terms()) >= 12, "Quechua vocabulary is too thin to crawl with"
    assert len(PE.aymara_terms()) >= 6, "no usable Aymara vocabulary at all"
    flat = {t for group in PE.TERMINOLOGY.values() for t in group}
    for must in ("tasa de referencia", "intervención cambiaria", "conflicto social",
                 "bloqueo de vías", "Corredor Vial Minero del Sur", "comunidad campesina",
                 "boletín estadístico minero", "anchoveta", "canon minero",
                 "vacancia presidencial"):
        assert must in flat, f"the Peru pack does not carry {must!r}"
    # the four metals this desk trades, named in the language the mining communities speak
    for metal in ("anta", "qullqi", "quri", "titi"):
        assert any(metal in t for t in flat), f"Quechua metal term {metal!r} is missing"
    assert PE.has_spanish_diacritic("minería") and not PE.has_spanish_diacritic("mining")
    assert PE.has_quechua("ayllu asamblea") and not PE.has_quechua("community assembly")
    assert PE.has_aymara("thakhi bloqueo") and not PE.has_aymara("road blockade")
    assert len(PE.TERMINOLOGY) >= 13


def test_every_layers_queries_are_written_in_the_languages_of_the_ground() -> None:
    """A query in English finds an English article about the release, not the release."""
    terms = PE.layer_terms()
    accented = [layer for layer, qs in terms.items()
                if any(PE.has_spanish_diacritic(q) for q in qs)]
    assert len(accented) >= 9, f"only {accented} carry an accented Spanish query"
    indigenous = [layer for layer, qs in terms.items()
                  if any(PE.has_quechua(q) or PE.has_aymara(q) for q in qs)]
    assert len(indigenous) >= 3, f"only {indigenous} carry a Quechua or Aymara query"
    native = sum(1 for row in PE.SOURCE_CLASSES if row["machine_use_allowed"]
                 for q in row["queries"] if PE.has_spanish_diacritic(q))
    assert native >= 50, f"only {native} accented queries across crawlable sources"


def test_query_territories_cover_every_layer_natively() -> None:
    """The deep-forest miner's own search space, per layer, in the language of the ground."""
    assert set(PE.QUERY_TERRITORIES) == set(PE.SOURCE_LAYERS)
    for layer, phrases in PE.QUERY_TERRITORIES.items():
        assert len(phrases) >= 3, f"{layer} has only {len(phrases)} query territories"
        assert any(PE.has_spanish_diacritic(p) for p in phrases), (
            f"{layer}'s query territory carries no accented Spanish at all")
    media = PE.QUERY_TERRITORIES["media"]
    assert any(PE.has_quechua(p) or PE.has_aymara(p) for p in media), (
        "the media territory must reach the indigenous wire in its own language")


def test_every_source_carries_three_independent_labels_and_a_query() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in PE.SOURCE_CLASSES:
        assert row["access_label"] in PE.ACCESS_LABELS
        assert row["credibility"] in PE.CREDIBILITY_LABELS
        assert row["predictive_state"] in PE.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no native-language query"
        assert row["roots"], f"{row['id']} has no crawlable root"
        assert row["notes"], f"{row['id']} says nothing about why it is here"


def test_all_ten_source_layers_are_populated() -> None:
    """The principal's depth rule: ten layers, none of them blank."""
    counts = PE.layer_counts()
    assert set(counts) == set(PE.SOURCE_LAYERS)
    blank = [layer for layer, n in counts.items() if not n]
    assert blank == [], f"blank layers: {blank}"
    coverage = PE.source_layer_coverage()
    assert coverage["n_layers_covered"] == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible for a country "
        "whose concentrate TC/RC and fishmeal price both live behind a PRA paywall")
    assert coverage["low_weight_kept"], "no fringe ground is kept at all, so it was dropped"
    assert PE.LAYER_ABSENCES == {}, "an absence declared here must carry a reason"


def test_no_crypto_exchange_ground_is_hunted() -> None:
    """Mandate 2026-08-18: no venue order book, no exchange feed, no exchange as a source."""
    blob = " ".join(str(r["label"]) + " ".join(r["roots"]) + " ".join(r["queries"])
                    for r in PE.SOURCE_CLASSES).lower()
    for venue in ("binance", "bybit", "okx", "hyperliquid", "coinbase", "kraken"):
        assert venue not in blob, f"{venue} is named as ground, which the mandate forbids"


# ------------------------------------------------------------------------------ the calendars
def test_the_holiday_table_resolves_for_all_three_years_inside_their_years() -> None:
    for year in (2024, 2025, 2026):
        table = holiday_table(PE.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        assert f"{year}-07-28" in table, "Fiestas Patrias missing"
        assert f"{year}-12-25" in table, "Navidad missing"
    assert PE.HOLIDAYS_RULE["rule"].strip()
    assert "anonymous Gregorian" in PE.HOLIDAYS_RULE["rule"] or "Easter" in \
        PE.HOLIDAYS_RULE["rule"]


def test_easter_is_computed_and_holy_week_follows_from_it() -> None:
    """MECHANISM FUNCTION ONE. Easter is derived with the anonymous Gregorian algorithm, so the
    two Easter-derived national feriados and the sierra's Carnaval extend to any year."""
    assert PE.easter(2024) == date(2024, 3, 31)
    assert PE.easter(2025) == date(2025, 4, 20)
    assert PE.easter(2026) == date(2026, 4, 5)
    assert set(PE.holy_week(2025)) == {date(2025, 4, 17), date(2025, 4, 18)}
    assert PE.carnaval(2025) == (date(2025, 3, 3), date(2025, 3, 4))
    assert PE.carnaval(2026) == (date(2026, 2, 16), date(2026, 2, 17))
    for year in (2024, 2025, 2026):
        lunes, martes = PE.carnaval(year)
        assert lunes.weekday() == 0 and martes.weekday() == 1, "Carnaval is Monday and Tuesday"
        assert lunes in PE.regional_days(year), "the sierra calendar must carry Carnaval"


def test_ley_31968_added_four_feriados_in_2024_and_the_pack_carries_the_break() -> None:
    """A closed day that did not exist before 2024 is a regime break a pooled study will miss."""
    added = {(m, d) for m, d, _ in PE.new_holidays_since_2024()}
    assert added == {(6, 7), (7, 23), (8, 6), (12, 9)}
    for month, day in added:
        assert date(2024, month, day) in PE.national_holidays(2024)
        assert date(2023, month, day) not in PE.national_holidays(2023)
    assert "31968" in PE.HOLIDAYS_RULE["rule"]


def test_market_holidays_drop_weekend_feriados_because_no_session_is_lost() -> None:
    """Peru does NOT substitute a weekend holiday -- the day is simply lost."""
    for year in (2024, 2025, 2026):
        assert all(d.weekday() < 5 for d in PE.market_holidays(year))
        assert set(PE.market_holidays(year)) <= set(PE.national_holidays(year))


# ------------------------------------------------------------------------------ the mechanisms
def test_the_blockade_calendar_is_a_dated_supply_series() -> None:
    """MECHANISM FUNCTION TWO, and the reason this pack exists. The Las Bambas occupation ran
    from mid-April to mid-June 2022 -- roughly fifty days of a ~2%-of-world-supply unit."""
    assert len(PE.BLOCKADE_EPISODES) >= 8
    assert PE.is_blockade_day(date(2022, 5, 1)) is True
    assert PE.is_blockade_day(date(2022, 5, 20)) is True
    assert PE.is_blockade_day(date(2022, 9, 15)) is False
    assert PE.is_blockade_day(date(2018, 1, 15)) is False
    days = PE.blockade_days(date(2022, 4, 1), date(2022, 7, 1))
    assert len(days) >= 45, f"only {len(days)} disrupted days in the 2022 occupation window"
    assert all(PE.is_blockade_day(d) for d in days)
    # every row is hypothesis-grade until a gazette or company citation is attached
    assert all(st == "PRESS_REPORTED" for *_rest, st in PE.BLOCKADE_EPISODES)
    assert len(PE.blockade_episodes("GAZETTE_VERIFIED")) == 0, (
        "no episode may claim a gazette citation it does not have")
    blob = " ".join(str(c["constraint"]) + str(c["measured"]) + str(c["consequence"])
                    for c in PE.ACCESS_CONSTRAINTS)
    assert "PRESS_REPORTED" in blob


def test_the_anchoveta_seasons_and_the_cancelled_one() -> None:
    """A CANCELLED season is the tradable row: the world's largest fishmeal source stops and the
    ration substitutes toward soymeal."""
    assert PE.in_anchoveta_season(date(2024, 5, 15)) is True
    assert PE.in_anchoveta_season(date(2024, 9, 15)) is False
    assert PE.anchoveta_season(date(2024, 5, 15))[:2] == (2024, 1)
    assert (2023, 1) in PE.cancelled_seasons()
    assert PE.in_anchoveta_season(date(2023, 6, 1)) is False, (
        "a cancelled season must read as CLOSED, never as a zero-length open one")


def test_the_bcrp_calendar_is_a_declared_lattice_and_not_an_invented_table() -> None:
    """The bank publishes its calendar a year ahead; this pack refuses to invent it (L1.28a)."""
    assert PE.CENTRAL_BANK["decision_dates"] == ()
    assert "NOT LISTED" in PE.CENTRAL_BANK["dates_status"]
    assert PE.CENTRAL_BANK["framework"] == "inflation_targeter"
    lattice = PE.policy_thursdays(2025)
    assert len(lattice) == 24
    assert all(d.weekday() == 3 for d in lattice)
    assert all(d.year == 2025 for d in lattice)
    assert date(2025, 1, 2) in lattice and date(2025, 1, 9) in lattice
    # Peru has no daylight saving, so the announcement minute never moves
    assert PE.CENTRAL_BANK["decision_time_utc"] == "23:00"
    assert "daylight saving" in PE.CENTRAL_BANK["dst_rule"].lower()


def test_cot_is_declared_absent_for_the_sol_rather_than_silently_missing() -> None:
    """No PEN contract exists anywhere. An absence a study can trip over must be named."""
    rows = {r["name"]: r for r in PE.POSITIONING_SOURCES}
    cot = [r for r in rows.values() if not r["available"]]
    assert cot, "the COT question is not answered anywhere in the pack"
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in cot)
    assert PE.COT_CURRENCY == ""


def test_every_dataset_carries_all_twelve_fields_and_a_fetchable_route() -> None:
    from countries import DATASET_FIELDS  # type: ignore[import-not-found]
    assert len(PE.DATASETS) >= 14
    for row in PE.DATASETS:
        for field in DATASET_FIELDS:
            if field == "pit_feasible":
                assert isinstance(row[field], bool)
                continue
            if field == "publication_lag_days":
                assert float(row[field]) >= 0.0
                continue
            assert row.get(field), f"dataset {row.get('name')!r} has an empty {field}"
        assert len(str(row["how_to_fetch"])) > 40, (
            f"dataset {row['name']!r} has a how_to_fetch a collector cannot act on")
    assert any(not row["pit_feasible"] for row in PE.DATASETS), (
        "every dataset claims to be point-in-time reconstructible, which is not true of any "
        "country whose ministries overwrite their statistics pages in place")
