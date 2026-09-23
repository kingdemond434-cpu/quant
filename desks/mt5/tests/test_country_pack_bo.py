"""THE BOLIVIA PACK, VALIDATED -- the peg, the premium, the gold statute, the bloqueo.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A SPANISH-ONLY GLOSSARY OF A FOUR-LANGUAGE COUNTRY. Article 5 of the 2009 constitution makes
    Spanish and thirty-six indigenous languages official; three of them carry economic weight
    here. The cooperative miners of Potosi and Oruro organise in Quechua and Aymara and the
    Chaco gas royalties are negotiated in Guarani, so the vocabulary assertions check all four.
  * A SYMBOL THE BOX CANNOT TRADE. Every executable instrument, every edge target and every
    interaction target is checked against the broker's OWN registry. The boliviano is absent and
    so is TIN -- which matters, because tin is this country's signature metal and a pack that
    quietly dropped it would lose the mechanism instead of routing it.
  * A CONSTANT MISTAKEN FOR A SERIES. The official rate has been 6.96 since 2011-11-02 and
    carries exactly zero information; the tests pin that, and pin that the PREMIUM is the
    variable half and that it is read into a DECLARED bucket rather than a fitted one.
  * A PACK THAT REACHES THE FRAMEWORK BENT. `CountryPack` coerces every row; a coercion note is
    a field the framework could not read, and this pack must produce none.
  * A LAYER NOBODY LOOKED AT, and equally a layer declared absent that is not. All ten layers
    carry a real source here; what is absent in Bolivia is two specific SERIES, and both are
    declared with `available=False` in POSITIONING_SOURCES rather than left as a hole.
  * A COUNTRY QUIETLY CLAIMED. `bo` is NOT on the desk's own forest roster, so the parity fence
    cannot credit this pack for it. The tests assert that the gap is DECLARED in ROSTER_STATE
    and stay green whichever way the roster later moves.
  * A HOLIDAY TABLE SOMEBODY TYPED. Both Carnaval days, Good Friday and Corpus Christi are
    DERIVED from Easter with the anonymous Gregorian algorithm, and the 2010 plurinational break
    -- two new national feriados -- is asserted.
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
from countries.bo import pack as BO  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as F  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it, resolved through `resolve_pack` so the test measures
    the same object the country lab runs."""
    got = CL.resolve_pack("bo")
    assert got is not None, "no Bolivia pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    assert check_pack(BO.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == "bo"
    assert str(get(built, "region_command")) == "latam"
    assert str(get(built, "currency")) == "BOB"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    notes = list(getattr(built, "coercion_notes", ()) or ())
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on this pack: {fatal[:4]}"


def test_jurisdictions_are_exactly_bolivia_and_the_roster_gap_is_declared() -> None:
    """THE HONEST VERSION OF THE PARITY CLAIM (L1.28a). `bo` is not on the desk's own forest
    roster, so the fence cannot credit this pack for it. That is a MEASUREMENT and it is
    declared in ROSTER_STATE; this test stays green whichever way the roster later moves, and
    fails if a jurisdiction is ever claimed that is neither on the roster nor explained."""
    assert BO.JURISDICTIONS == ("bo",)
    assert all(c == c.lower() and len(c) == 2 for c in BO.JURISDICTIONS)
    assert BO.CODE == "bo"
    roster = {c.lower() for forest in F.FORESTS.values() for c in forest.countries}
    for code in BO.JURISDICTIONS:
        assert code in roster or code in BO.ROSTER_STATE, (
            f"{code} is neither on the forest roster nor declared in ROSTER_STATE")
    for code, why in BO.ROSTER_STATE.items():
        assert len(why) > 60, f"ROSTER_STATE[{code}] does not say WHY"
    # the neighbours this pack interacts with ARE on the roster, which is what makes the
    # interaction rows cashable the moment those packs run
    for neighbour in ("pe", "cl", "ar", "br"):
        assert neighbour in roster, f"{neighbour} is not on the roster after all"


def test_pack_reaches_its_declared_parity_depth(built: Any) -> None:
    row = RP.pack_depth(built, "bo").as_row()
    assert row["score"] >= BO.DECLARED_DEPTH, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_depth_counts_sit_above_the_floor_and_not_at_it() -> None:
    assert len(BO.ACTORS) >= 15
    assert len(BO.DOMAINS) >= 13
    assert len(BO.TRANSMISSION_EDGES_SEED) >= 11
    assert len(BO.SOURCE_CLASSES) >= 20
    assert len(BO.DATASETS) >= 14
    assert len(BO.POLICY_ERAS) >= 6
    assert len(BO.INTERACTIONS) >= 4
    assert BO.term_count() >= 150


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    for row in BO.ACTORS:
        for f in ACTOR_FIELDS:
            assert row.get(f), f"actor {row.get('name')!r} has an empty {f}"
        # a one-element tuple written without its trailing comma silently becomes a string
        for f in ("forced_to", "information", "constraints", "instruments", "counterparties",
                  "observables"):
            value = row[f]
            assert isinstance(value, tuple), f"actor {row.get('name')!r}.{f} is not a tuple"
            assert all(len(str(v)) > 2 for v in value), (
                f"actor {row.get('name')!r}.{f} looks like a string split into characters -- a "
                f"single-element tuple needs its trailing comma")


def test_every_domain_has_objects_and_two_negative_controls() -> None:
    for row in BO.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert len(row["conditions"]) >= 3, f"domain {row['id']} names too few conditions"
        assert row["instruments"], f"domain {row['id']} names no instrument"
        assert row["id"] in BO.DOMAIN_CELL_SPEC, f"{row['id']} mints cells with no family"


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(BO.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert set(BO.EXECUTABLE_INSTRUMENTS) <= set(registry)


def test_every_transmission_seed_and_interaction_names_tradable_targets() -> None:
    for seed in BO.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"
    for row in BO.INTERACTIONS:
        split = resolve(row["targets"])
        assert split["absent"] == [], f"interaction with {row['with']} -> {split['absent']}"
        assert split["equities"] == [], f"interaction with {row['with']} -> {split['equities']}"
        assert row["control"] and row["observable"] and row["mechanism"]
    named = {str(row["with"]) for row in BO.INTERACTIONS}
    assert {"pe", "cl", "ar", "br"} <= named, f"missing the sibling packs: {sorted(named)}"


def test_domain_instruments_are_tradable_and_never_single_names() -> None:
    for row in BO.DOMAINS:
        split = resolve(row["instruments"])
        assert split["absent"] == [], f"domain {row['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"domain {row['id']} -> equity {split['equities']}"


def test_the_boliviano_and_tin_are_named_absent_rather_than_dropped() -> None:
    """BOB is not quoted here and neither is TIN -- and the second absence is the one that would
    quietly cost a mechanism, because tin is this country's signature metal."""
    registry = universe_symbols()
    assert not {"USDBOB", "BOB", "TIN", "XSNUSD"} & set(registry)
    named = " ".join(str(t["name"]) for t in BO.TRANSMISSION_TARGETS)
    assert "BOB" in named and "TIN" in named and "LITHIUM" in named
    for row in BO.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert row["route"], f"{row['name']} is named absent with no route"
        assert row["regime"], f"{row['name']} is named absent with no regime"
        assert resolve(row["proxies"])["absent"] == []
    # the tin row must route into the metals co-produced from the same concentrates
    tin = next(r for r in BO.TRANSMISSION_TARGETS if "TIN" in str(r["name"]))
    assert set(tin["proxies"]) <= set(BO.EXECUTABLE_INSTRUMENTS)
    assert "XZNUSD" in tin["proxies"]


def test_the_national_champions_appear_only_as_actors() -> None:
    actor_names = " ".join(str(a["name"]) for a in BO.ACTORS)
    for who in ("YPFB", "COMIBOL", "San Cristobal", "Petrobras", "ANAPO"):
        assert who in actor_names, f"{who} is not carried as an actor"
    every_symbol: set[str] = set(BO.EXECUTABLE_INSTRUMENTS)
    for row in BO.DOMAINS:
        every_symbol |= set(row["instruments"])
    for seed in BO.TRANSMISSION_EDGES_SEED:
        every_symbol |= set(seed["targets"])
    assert resolve(sorted(every_symbol))["equities"] == []


# ------------------------------------------------------------------------------ the cells
def test_cells_are_real_and_every_declared_instrument_is_used() -> None:
    rows = BO.cells()
    assert 60 <= len(rows) <= 260, f"{len(rows)} cells is outside the honest range"
    by_domain = {d["id"]: d for d in BO.DOMAINS}
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
    unused = [s for s, n in BO.cells_by_symbol().items() if n == 0]
    assert unused == [], f"declared executable but no domain uses it: {unused}"


def test_mine_reports_the_cell_count_and_emits_nothing_without_a_ctx() -> None:
    report = BO.mine(None)
    assert report["code"] == "bo"
    assert report["cells_emitted"] == len(BO.cells())
    assert report["emitted"] > 0
    assert report["rows"] and all(r.get("miner") for r in report["rows"])
    assert report["jurisdictions"] == ("bo",)
    assert report["roster_state"] == BO.ROSTER_STATE
    assert "pe" in report["interactions"]
    assert any("UNMEASURED" in u or "not loaded" in u or "NO OFFICIAL PUBLISHER" in u
               or "no row carries" in u or "no episode carries" in u
               for u in report["unmeasured"]), report["unmeasured"][:3]
    assert "recorded" not in report


def test_every_custom_miner_entry_resolves(built: Any) -> None:
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {f"custom:{name}" for name in BO.MINERS}
    assert all(callable(fn) for fn in got.values())
    ids = {d["id"] for d in BO.DOMAINS}
    for row in BO.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.bo.pack", row["entry"]
        assert func in BO.MINERS, f"{row['entry']} is not in the MINERS table"
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    for domains in BO.MINER_DOMAINS.values():
        assert set(domains) <= ids


# ------------------------------------------------------------------------------ the languages
def test_terminology_carries_spanish_quechua_aymara_and_guarani() -> None:
    """Four languages, because the mine and the gas field answer to two different peoples."""
    assert len(BO.accented_terms()) >= 40, (
        f"only {len(BO.accented_terms())} terms carry a Spanish diacritic -- this reads like an "
        f"English glossary of Bolivia")
    assert len(BO.spanish_terms()) == len(BO.SPANISH_MARKERS), (
        f"missing Spanish working vocabulary: "
        f"{sorted(set(BO.SPANISH_MARKERS) - set(BO.spanish_terms()))}")
    assert len(BO.quechua_terms()) >= 8, "Quechua vocabulary is too thin to crawl with"
    assert len(BO.aymara_terms()) >= 8, "Aymara vocabulary is too thin to crawl with"
    assert len(BO.guarani_terms()) >= 5, "no usable Guarani vocabulary at all"
    flat = {t for group in BO.TERMINOLOGY.values() for t in group}
    for must in ("tipo de cambio oficial", "dólar paralelo", "reservas internacionales netas",
                 "Ley del Oro", "cooperativas mineras", "Salar de Uyuni", "exportación de gas",
                 "subvención", "cupo de exportación", "bloqueo de caminos", "Carnaval de Oruro"):
        assert must in flat, f"the Bolivia pack does not carry {must!r}"
    for metal in ("qullqi", "quri", "titi"):
        assert any(metal in t for t in flat), f"Quechua metal term {metal!r} is missing"
    assert BO.has_spanish_diacritic("minería") and not BO.has_spanish_diacritic("mining")
    assert BO.has_quechua("ayllu asamblea") and not BO.has_quechua("community assembly")
    assert BO.has_aymara("thakhi bloqueo") and not BO.has_aymara("road blockade")
    assert BO.has_guarani("ñemboati Itika Guasu") and not BO.has_guarani("Chaco assembly")
    assert len(BO.TERMINOLOGY) >= 13


def test_every_layers_queries_are_written_in_the_languages_of_the_ground() -> None:
    terms = BO.layer_terms()
    accented = [layer for layer, qs in terms.items()
                if any(BO.has_spanish_diacritic(q) for q in qs)]
    assert len(accented) >= 9, f"only {accented} carry an accented Spanish query"
    indigenous = [layer for layer, qs in terms.items()
                  if any(BO.has_quechua(q) or BO.has_aymara(q) or BO.has_guarani(q) for q in qs)]
    assert len(indigenous) >= 2, f"only {indigenous} carry an indigenous-language query"
    native = sum(1 for row in BO.SOURCE_CLASSES if row["machine_use_allowed"]
                 for q in row["queries"] if BO.has_spanish_diacritic(q))
    assert native >= 50, f"only {native} accented queries across crawlable sources"
    # the indigenous wire must be reachable in Guarani, or the Chaco gas royalties are invisible
    wire = next(r for r in BO.SOURCE_CLASSES if r["id"] == "bo_indigenous_media")
    assert "gn" in wire["languages"] and any(BO.has_guarani(q) for q in wire["queries"])


def test_query_territories_cover_every_layer_natively() -> None:
    assert set(BO.QUERY_TERRITORIES) == set(BO.SOURCE_LAYERS)
    for layer, phrases in BO.QUERY_TERRITORIES.items():
        assert len(phrases) >= 3, f"{layer} has only {len(phrases)} query territories"
        assert any(BO.has_spanish_diacritic(p) for p in phrases), (
            f"{layer}'s query territory carries no accented Spanish at all")
    media = BO.QUERY_TERRITORIES["media"]
    assert any(BO.has_aymara(p) or BO.has_quechua(p) for p in media)
    assert any(BO.has_guarani(p) for p in media)


def test_every_source_carries_three_independent_labels_and_a_query() -> None:
    for row in BO.SOURCE_CLASSES:
        assert row["access_label"] in BO.ACCESS_LABELS
        assert row["credibility"] in BO.CREDIBILITY_LABELS
        assert row["predictive_state"] in BO.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no native-language query"
        assert row["roots"], f"{row['id']} has no crawlable root"
        assert row["notes"], f"{row['id']} says nothing about why it is here"


def test_all_ten_source_layers_are_populated_and_the_real_absences_are_series() -> None:
    """All ten layers carry a real source. What IS absent in Bolivia is two specific SERIES,
    and both are declared with `available=False` rather than left as a hole."""
    counts = BO.layer_counts()
    assert set(counts) == set(BO.SOURCE_LAYERS)
    assert [layer for layer, n in counts.items() if not n] == []
    coverage = BO.source_layer_coverage()
    assert coverage["n_layers_covered"] == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], (
        "nothing is machine-use-forbidden, which is implausible for a country whose signature "
        "metal's price data is behind a subscription")
    assert coverage["low_weight_kept"], "no fringe ground is kept at all, so it was dropped"
    assert BO.LAYER_ABSENCES == {}
    unavailable = [r for r in BO.POSITIONING_SOURCES if not r["available"]]
    assert len(unavailable) >= 2, "the two structural data absences are not both declared"
    assert all("DOES NOT EXIST" in str(r["pit_warning"]) for r in unavailable)


def test_no_crypto_exchange_ground_is_hunted() -> None:
    """Mandate 2026-08-18: no venue order book, no exchange feed, no exchange as a source."""
    blob = " ".join(str(r["label"]) + " ".join(r["roots"]) + " ".join(r["queries"])
                    for r in BO.SOURCE_CLASSES).lower()
    for venue in ("binance", "bybit", "okx", "hyperliquid", "coinbase", "kraken"):
        assert venue not in blob, f"{venue} is named as ground, which the mandate forbids"


# ------------------------------------------------------------------------------ the calendars
def test_the_holiday_table_resolves_for_all_three_years_inside_their_years() -> None:
    for year in (2024, 2025, 2026):
        table = holiday_table(BO.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        assert f"{year}-08-06" in table, "Dia de la Independencia missing"
        assert f"{year}-11-02" in table, "Todos Santos missing"
        assert f"{year}-06-21" in table, "Willkakuti missing"
    assert BO.HOLIDAYS_RULE["rule"].strip()
    assert "anonymous Gregorian" in BO.HOLIDAYS_RULE["rule"]


def test_easter_carnaval_and_corpus_christi_are_computed() -> None:
    """MECHANISM FUNCTION ONE. FOUR of Bolivia's national closures are Easter-derived, so they
    are computed with the anonymous Gregorian algorithm and never typed."""
    assert BO.easter(2024) == date(2024, 3, 31)
    assert BO.easter(2025) == date(2025, 4, 20)
    assert BO.easter(2026) == date(2026, 4, 5)
    assert BO.carnaval(2024) == (date(2024, 2, 12), date(2024, 2, 13))
    assert BO.carnaval(2025) == (date(2025, 3, 3), date(2025, 3, 4))
    assert BO.carnaval(2026) == (date(2026, 2, 16), date(2026, 2, 17))
    assert BO.corpus_christi(2024) == date(2024, 5, 30)
    assert BO.corpus_christi(2025) == date(2025, 6, 19)
    for year in (2024, 2025, 2026):
        lunes, martes = BO.carnaval(year)
        assert lunes.weekday() == 0 and martes.weekday() == 1
        table = BO.national_holidays(year)
        # BOTH Carnaval days are national here, unlike Peru, where they are regional
        assert lunes in table and martes in table
        assert BO.corpus_christi(year) in table
        assert BO.easter(year) - __import__("datetime").timedelta(days=2) in table


def test_the_plurinational_settlement_added_two_feriados_in_2010() -> None:
    """A closed day that did not exist before 2010 is a regime break a pooled study will miss."""
    added = {(m, d) for m, d, _ in BO.new_holidays_since_2010()}
    assert added == {(1, 22), (6, 21)}
    for month, day in added:
        assert date(2024, month, day) in BO.national_holidays(2024)
        assert date(2008, month, day) not in BO.national_holidays(2008)


def test_the_mining_departments_keep_their_own_days() -> None:
    """Oruro on 10 February (Huanuni tin, the Carnaval de Oruro) and Potosi on 10 November
    (Cerro Rico) close MINES, not the bourse -- so they are a separate table."""
    for year in (2024, 2025, 2026):
        mining = BO.mining_department_days(year)
        assert set(mining) == {date(year, 2, 10), date(year, 11, 10)}
        assert set(mining) <= set(BO.departmental_days(year))
        # and they are NOT national closures, which is the whole reason they are separate
        assert not (set(mining) & set(BO.national_holidays(year)))
    assert len(BO.DEPARTMENTAL_DAYS) >= 8


def test_market_holidays_drop_weekend_feriados_because_no_session_is_lost() -> None:
    for year in (2024, 2025, 2026):
        assert all(d.weekday() < 5 for d in BO.market_holidays(year))
        assert set(BO.market_holidays(year)) <= set(BO.national_holidays(year))


# ------------------------------------------------------------------------------ the mechanisms
def test_the_peg_is_a_constant_and_the_premium_is_the_variable_half() -> None:
    """MECHANISM FUNCTION TWO, and the state variable of this pack. `parallel_premium` is pure
    arithmetic on two published numbers and `peg_stress_state` reads it into a DECLARED bucket,
    so a study using either is using a rule somebody wrote down in advance."""
    assert BO.OFFICIAL_SELL == 6.96
    assert BO.OFFICIAL_BUY == 6.86
    assert date(2011, 11, 2) == BO.PEG_SINCE
    assert BO.CENTRAL_BANK["framework"] == "peg"
    # the peg holding means a zero premium
    assert BO.parallel_premium(6.96, 6.96) == 0.0
    assert BO.peg_stress_state(0.0) == "PEG_HOLDING"
    # a 50% premium and a 100% premium, exactly
    assert round(BO.parallel_premium(6.96, 10.44), 10) == 0.5
    assert round(BO.parallel_premium(6.96, 13.92), 10) == 1.0
    assert BO.peg_stress_state(0.5) == "SEVERE"
    assert BO.peg_stress_state(1.0) == "DISLOCATED"
    assert BO.peg_stress_state(0.05) == "RATIONING"
    assert BO.peg_stress_state(0.20) == "STRESS"
    # a corrupt input must not raise: the caller's UNMEASURED path handles it
    assert BO.parallel_premium(0.0, 10.0) == 0.0
    # the buckets are declared, in order, and exhaustive
    edges = [edge for edge, _label in BO.PREMIUM_BUCKETS]
    assert edges == sorted(edges)
    assert BO.PREMIUM_EXTREME not in [label for _e, label in BO.PREMIUM_BUCKETS]


def test_the_bcb_has_no_meeting_calendar_and_the_pack_refuses_to_invent_one() -> None:
    """The exchange rate IS the policy; inventing twelve meeting dates a year here would be
    inventing an institution (L1.28a). What the pack offers instead is the publication rhythm."""
    assert BO.CENTRAL_BANK["decision_dates"] == ()
    assert "DECLARED ABSENT" in BO.CENTRAL_BANK["dates_status"]
    months = BO.reserve_report_months(2025)
    assert len(months) == 12
    assert months[0] == date(2025, 1, 31)
    assert months[1] == date(2025, 2, 28)
    assert months[11] == date(2025, 12, 31)
    assert BO.reserve_report_months(2024)[1] == date(2024, 2, 29), "2024 is a leap year"
    assert all(d.year == 2025 for d in months)


def test_the_gold_authority_is_dated_and_carries_its_status() -> None:
    """Ley 1503 turns a reserve decision into a dated, lawful, published XAUUSD observable."""
    assert len(BO.GOLD_AUTHORITY) >= 3
    first = BO.GOLD_AUTHORITY[0]
    assert first[0] == date(2023, 5, 8)
    assert "1503" in first[1]
    assert all(st == "PRESS_REPORTED" for *_rest, st in BO.GOLD_AUTHORITY), (
        "no row may claim a Gaceta citation it does not have")
    blob = " ".join(str(c["constraint"]) + str(c["measured"]) + str(c["consequence"])
                    for c in BO.ACCESS_CONSTRAINTS)
    assert "PRESS_REPORTED" in blob
    # the pack must declare the size honestly rather than implying a large flow
    mission_and_notes = BO.MISSION + " ".join(str(a["notes"]) for a in BO.ACTORS)
    assert "tens of tonnes" in mission_and_notes


def test_the_blockade_calendar_is_a_dated_logistics_series() -> None:
    """The 2022 Santa Cruz paro ran 36 days and closed the country's export department."""
    assert len(BO.BLOCKADE_EPISODES) >= 6
    assert BO.is_blockade_day(date(2022, 11, 1)) is True
    assert BO.is_blockade_day(date(2024, 10, 20)) is True
    assert BO.is_blockade_day(date(2023, 5, 15)) is False
    days = BO.blockade_days(date(2022, 10, 1), date(2022, 12, 31))
    assert len(days) >= 30, f"only {len(days)} disrupted days in the Santa Cruz paro window"
    assert all(BO.is_blockade_day(d) for d in days)
    assert all(st == "PRESS_REPORTED" for *_rest, st in BO.BLOCKADE_EPISODES)
    assert len(BO.blockade_episodes("GAZETTE_VERIFIED")) == 0


def test_the_gas_and_lithium_milestones_are_dated_with_their_status() -> None:
    """A structural decline with a schedule, a pipeline that reversed, and a decade of lithium
    agreements that produced nothing -- all dated, all PRESS_REPORTED."""
    assert len(BO.GAS_MILESTONES) >= 5
    assert len(BO.LITHIUM_MILESTONES) >= 4
    reversal = [row for row in BO.GAS_MILESTONES if "REVERSAL" in row[1]]
    assert reversal and reversal[0][0].year == 2024
    assert all(st == "PRESS_REPORTED" for *_rest, st in BO.GAS_MILESTONES)
    assert all(st == "PRESS_REPORTED" for *_rest, st in BO.LITHIUM_MILESTONES)
    dates = [row[0] for row in BO.GAS_MILESTONES]
    assert dates == sorted(dates), "the gas milestones must be in chronological order"


def test_cot_and_foreign_holdings_are_declared_absent_for_the_boliviano() -> None:
    rows = {r["name"]: r for r in BO.POSITIONING_SOURCES}
    cot = [r for r in rows.values() if not r["available"]]
    assert len(cot) >= 2
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in cot)
    assert BO.COT_CURRENCY == ""


def test_every_dataset_carries_all_twelve_fields_and_a_fetchable_route() -> None:
    from countries import DATASET_FIELDS  # type: ignore[import-not-found]
    assert len(BO.DATASETS) >= 14
    for row in BO.DATASETS:
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
    not_pit = [row["name"] for row in BO.DATASETS if not row["pit_feasible"]]
    assert len(not_pit) >= 4, (
        "almost every dataset claims to be point-in-time reconstructible, which is not true of "
        "a country that publishes spreadsheets rather than endpoints and whose most important "
        "series -- the parallel rate -- has no official publisher at all")
