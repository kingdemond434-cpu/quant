"""THE CENTRAL AMERICA PACK, VALIDATED -- the canal constraint, the coffee belt, six monies.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A SPANISH-ONLY GLOSSARY OF A FOUR-LANGUAGE GROUND. K'iche', Q'eqchi' and Kaqchikel are the
    languages of the Guatemalan highlands, which is where the coffee grows and where the
    land-and-labour disputes that interrupt a harvest are decided in assembly and reported
    first. A crawler handed only Spanish reads the capital's account of the altiplano, so the
    vocabulary assertions below check all four languages by name.
  * A CURRENCY DESCRIBED AS A PROXY WHEN IT IS AN IDENTITY. PAB and SVC ARE the United States
    dollar -- 1:1 by statute with no banknote of its own, and withdrawn from circulation
    respectively -- and the pack must say so rather than treating either as an EM peg with a
    devaluation premium that cannot exist.
  * A SYMBOL THE BOX CANNOT TRADE. Every executable instrument, every domain instrument, every
    edge target and every interaction target is checked against the broker's OWN registry.
  * A SINGLE-NAME EQUITY ON A DOCKET. The two-lane order (2026-09-06) forbids hunting one
    statistically, and this pack is full of tempting names -- the mine's operator, the sugar
    mills, the apparel groups, the liner operators -- every one of which appears only as an ACTOR.
  * A CRYPTO-EXCHANGE GROUND SMUGGLED IN THROUGH A SOVEREIGN POLICY. El Salvador's Bitcoin Law is
    a fiscal and legal observable routed into the broker's own CFD; no venue, order book or
    exchange feed may appear anywhere in this pack and the test greps for them by name.
  * A MULTI-JURISDICTION PACK THAT IS REALLY ONE COUNTRY WITH FIVE FOOTNOTES. Every one of the
    six owes at least three actors and two domains OF ITS OWN, and the tests count the maps
    rather than trusting the prose.
  * A DECLARED ABSENCE THAT IS DECORATIVE. Every `NO_LAWFUL_GROUND` row of kind "layer" is
    checked against the actual source count for that jurisdiction, so an absence cannot be
    claimed for a layer the pack in fact populated.
  * A HOLIDAY TABLE SOMEBODY TYPED. Semana Santa, the Honduran Feriado Morazanico and the Costa
    Rican Monday shift are all DERIVED, and 15 September is asserted as one date and five
    closures with Panama open beside it.
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
from countries.central_america import pack as CA  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as F  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")
JURISDICTIONS = ("pa", "gt", "hn", "cr", "ni", "sv")


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it. Resolved through `resolve_pack` so the test measures
    the same object the country lab runs, not a private construction."""
    got = CL.resolve_pack("central_america")
    assert got is not None, "no Central America pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(CA.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == "central_america"
    assert str(get(built, "region_command")) == "latam"
    assert str(get(built, "currency")) == "PAB"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    """A coercion note is a field `CountryPack` could not read. There must be none."""
    notes = list(getattr(built, "coercion_notes", ()) or ())
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on this pack: {fatal[:4]}"


def test_jurisdictions_are_the_six_and_all_on_the_desks_own_roster() -> None:
    """THE PARITY FENCE COUNTS THIS TUPLE (`check_regional_parity.jurisdictions_of`). Six
    countries on the desk's own latam roster that no sibling pack answers for."""
    assert CA.JURISDICTIONS == JURISDICTIONS
    assert all(c == c.lower() and len(c) == 2 for c in CA.JURISDICTIONS)
    assert len(set(CA.JURISDICTIONS)) == 6
    roster = {c.lower() for forest in F.FORESTS.values() for c in forest.countries}
    for code in CA.JURISDICTIONS:
        assert code in roster, f"{code} is not on the forest roster in libs/research/forests.py"
    assert "central_america" in F.FORESTS["latam"].packs
    assert CA.CODE == "central_america"
    # the siblings this pack must not duplicate are all still registered on the same forest
    for sibling in ("mx", "br", "cl", "co", "ar", "pe", "bo", "atlantic_energy"):
        assert sibling in F.FORESTS["latam"].packs, f"{sibling} left the latam forest"


def test_pack_reaches_its_declared_parity_depth(built: Any) -> None:
    """The standing depth rule, MEASURED by the framework and not claimed by the pack."""
    row = RP.pack_depth(built, "central_america").as_row()
    assert row["score"] >= CA.DECLARED_DEPTH, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_a_six_jurisdiction_pack_is_sized_for_six_jurisdictions() -> None:
    """Twelve actors and ten domains is the single-country floor; a pack answering for six
    countries written to that floor is five countries half-read."""
    assert len(CA.ACTORS) >= 20
    assert len(CA.DOMAINS) >= 14
    assert len(CA.TRANSMISSION_EDGES_SEED) >= 12
    assert len(CA.DATASETS) >= 18
    assert len(CA.SOURCE_CLASSES) >= 30
    assert len(CA.POLICY_ERAS) >= 6
    assert len(CA.INTERACTIONS) >= 4
    assert CA.term_count() >= 150


def test_every_jurisdiction_owns_three_actors_and_two_domains_of_its_own() -> None:
    """A multi-jurisdiction pack earns its trial budget only if every country in it is actually
    read. The maps are COUNTED here rather than trusted."""
    for cc in CA.JURISDICTIONS:
        own_actors = CA.actors_of(cc)
        own_domains = CA.domains_of(cc)
        assert len(own_actors) >= 3, f"{cc} owns only {len(own_actors)} actor(s)"
        assert len(own_domains) >= 2, f"{cc} owns only {len(own_domains)} domain(s)"
    names = {a["name"] for a in CA.ACTORS}
    assert set(CA.ACTOR_JURISDICTIONS) == names, "the actor map and the actor list disagree"
    ids = {d["id"] for d in CA.DOMAINS}
    assert set(CA.DOMAIN_JURISDICTIONS) == ids, "the domain map and the domain list disagree"
    known = set(CA.JURISDICTIONS) | {"ca"}
    for codes in CA.ACTOR_JURISDICTIONS.values():
        assert set(codes) <= known
    for codes in CA.DOMAIN_JURISDICTIONS.values():
        assert set(codes) <= set(CA.JURISDICTIONS)


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    for row in CA.ACTORS:
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
    for row in CA.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert len(row["conditions"]) >= 3, f"domain {row['id']} names too few conditions"
        assert row["instruments"], f"domain {row['id']} names no instrument"
        assert row["id"] in CA.DOMAIN_CELL_SPEC, f"{row['id']} mints cells with no family"


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(CA.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert set(CA.EXECUTABLE_INSTRUMENTS) <= set(registry)
    # the brief's executable list, in full
    for must in ("CORN", "WHEAT", "SOYBEAN", "SUGAR", "COFARA", "COFROB", "COTTON", "XCUUSD",
                 "XAUUSD", "XBRUSD", "XTIUSD", "XNGUSD", "USDMXN", "USDBRL", "USDCNH", "US500",
                 "US30", "BTCUSD"):
        assert must in CA.EXECUTABLE_INSTRUMENTS, f"{must} is not executable in this pack"


def test_every_transmission_seed_and_interaction_names_tradable_targets() -> None:
    """A seed that terminates in a symbol the box cannot quote can never compile a cell."""
    for seed in CA.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"
    for row in CA.INTERACTIONS:
        split = resolve(row["targets"])
        assert split["absent"] == [], f"interaction with {row['with']} -> {split['absent']}"
        assert split["equities"] == [], f"interaction with {row['with']} -> {split['equities']}"
        assert row["control"] and row["observable"] and row["mechanism"]
    # the brief names these two explicitly: the maquila, remittance and nearshoring chains run
    # straight into both, and the FOMC is literally the central bank of two of the six
    partners = {row["with"] for row in CA.INTERACTIONS}
    assert {"mx", "us"} <= partners, f"the mx and us edges are missing: {sorted(partners)}"


def test_domain_instruments_are_tradable_and_never_single_names() -> None:
    for row in CA.DOMAINS:
        split = resolve(row["instruments"])
        assert split["absent"] == [], f"domain {row['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"domain {row['id']} -> equity {split['equities']}"


def test_the_balboa_and_the_colon_are_labelled_the_dollar_and_not_a_proxy_for_it() -> None:
    """THE PACK'S SHARPEST CURRENCY FACT. PAB is 1:1 by the 1904 Convenio Monetario with no
    banknote of its own and SVC was withdrawn in 2001; both ARE the dollar. A pack that called
    either a proxy would invite a search for a devaluation premium that cannot exist."""
    from countries import asset_class
    registry = universe_symbols()
    for absent in ("PAB", "GTQ", "HNL", "CRC", "SVC", "USDGTQ", "USDCRC", "USDHNL", "USDNIO"):
        assert absent not in registry, f"{absent} unexpectedly appeared in the broker registry"
    # NIO IS IN THE REGISTRY AND IS NOT THE CORDOBA: it is a single-name share CFD on a Chinese
    # electric-vehicle maker. A naive currency-code lookup would buy that company, and the
    # two-lane order forbids hunting it besides. This assertion pins the collision.
    assert asset_class("NIO") == "equities", (
        "NIO is a single-name equity on this broker, not the Nicaraguan cordoba")
    assert "NIO" not in CA.EXECUTABLE_INSTRUMENTS
    assert set(CA.CURRENCIES) == set(CA.JURISDICTIONS)
    assert all(not row["broker_quoted"] for row in CA.CURRENCIES.values())
    for cc in ("pa", "sv"):
        assert "DOLLAR" in CA.CURRENCIES[cc]["regime"].upper()
        assert CA.dollarised(cc) is True
    for cc in ("gt", "hn", "cr", "ni"):
        assert CA.dollarised(cc) is False
    named = " ".join(str(t["name"]) for t in CA.TRANSMISSION_TARGETS)
    for code in ("PAB", "SVC", "GTQ", "HNL", "CRC", "NIO"):
        assert code in named, f"{code} is absent from the broker and is not named as a target"
    for row in CA.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert row["route"], f"{row['name']} is named absent with no route"
        assert resolve(row["proxies"])["absent"] == []
    # the non-currency absences the brief names must be routed too
    for must in ("slot", "freight", "LPG"):
        assert any(must.lower() in str(t["name"]).lower() for t in CA.TRANSMISSION_TARGETS), (
            f"no transmission target covers {must}")


def test_the_national_champions_appear_only_as_actors() -> None:
    """The mine's operator, the sugar mills, the apparel groups and the liner operators are the
    loudest mechanisms here and the two-lane order forbids hunting any of them."""
    actor_names = " ".join(str(a["name"]) for a in CA.ACTORS)
    for who in ("Minera Panama", "ASAZGUA", "maquila", "liner operators"):
        assert who in actor_names, f"{who} is not carried as an actor"
    every_symbol: set[str] = set(CA.EXECUTABLE_INSTRUMENTS)
    for row in CA.DOMAINS:
        every_symbol |= set(row["instruments"])
    for seed in CA.TRANSMISSION_EDGES_SEED:
        every_symbol |= set(seed["targets"])
    for row in CA.INTERACTIONS:
        every_symbol |= set(row["targets"])
    assert resolve(sorted(every_symbol))["equities"] == []


# ------------------------------------------------------------------------------ the cells
def test_cells_are_real_and_every_declared_instrument_is_used() -> None:
    """THE POINT OF A PACK IS CELLS REACHING THE GAUNTLET. They must also be honest: each cell
    names a condition its own domain declared, on an instrument that domain owns."""
    rows = CA.cells()
    assert 150 <= len(rows) <= 420, f"{len(rows)} cells is outside the honest range"
    by_domain = {d["id"]: d for d in CA.DOMAINS}
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
        assert set(row["jurisdictions"]) <= set(CA.JURISDICTIONS)
    unused = [s for s, n in CA.cells_by_symbol().items() if n == 0]
    assert unused == [], f"declared executable but no domain uses it: {unused}"
    # a jurisdiction with no cells is a country this pack claimed and never tested
    per_country = CA.cells_by_jurisdiction()
    assert set(per_country) == set(CA.JURISDICTIONS)
    assert all(n > 0 for n in per_country.values()), per_country


def test_mine_reports_the_cell_count_and_emits_nothing_without_a_ctx() -> None:
    """`mine(None)` is a MEASUREMENT of what the pack would emit and writes nowhere."""
    report = CA.mine(None)
    assert report["code"] == "central_america"
    assert report["cells_emitted"] == len(CA.cells())
    assert report["emitted"] > 0
    assert report["rows"] and all(r.get("miner") for r in report["rows"])
    assert report["jurisdictions"] == JURISDICTIONS
    assert "mx" in report["interactions"] and "us" in report["interactions"]
    # UNMEASURED is a real answer: the miners that need a series this box does not carry say so
    assert any("not loaded" in u or "UNMEASURED" in u or "not in this pack" in u
               for u in report["unmeasured"]), report["unmeasured"][:3]
    # nothing reached a registry: there is no connection and no ctx, so no discovery id exists
    assert "recorded" not in report


def test_every_custom_miner_entry_resolves(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {f"custom:{name}" for name in CA.MINERS}
    assert all(callable(fn) for fn in got.values())
    ids = {d["id"] for d in CA.DOMAINS}
    for row in CA.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.central_america.pack", row["entry"]
        assert func in CA.MINERS, f"{row['entry']} is not in the MINERS table"
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    for domains in CA.MINER_DOMAINS.values():
        assert set(domains) <= ids


# ------------------------------------------------------------------------------ the languages
def test_terminology_carries_spanish_and_the_three_mayan_languages() -> None:
    """Four languages, because the decision that interrupts a Guatemalan harvest is taken in a
    Mayan language. Latin script is shared, so this is a VOCABULARY test, not a codepoint one."""
    assert len(CA.accented_terms()) >= 60, (
        f"only {len(CA.accented_terms())} terms carry a Spanish diacritic -- this reads like an "
        f"English glossary of Central America")
    assert len(CA.spanish_terms()) == len(CA.SPANISH_MARKERS), (
        f"missing Spanish working vocabulary: "
        f"{sorted(set(CA.SPANISH_MARKERS) - set(CA.spanish_terms()))}")
    assert len(CA.kiche_terms()) >= 8, "K'iche' vocabulary is too thin to crawl with"
    assert len(CA.qeqchi_terms()) >= 4, "no usable Q'eqchi' vocabulary"
    assert len(CA.kaqchikel_terms()) >= 3, "no usable Kaqchikel vocabulary"
    flat = {t for group in CA.TERMINOLOGY.values() for t in group}
    for must in ("calado máximo autorizado", "subasta de cupos", "lago Gatún",
                 "exportaciones de café", "roya del café", "remesas familiares",
                 "deslizamiento cambiario", "Corredor Seco", "zafra", "maquila",
                 "Cobre Panamá", "Feriado Morazánico", "Ley Bitcoin", "dolarización"):
        assert must in flat, f"the Central America pack does not carry {must!r}"
    assert CA.has_spanish_diacritic("minería") and not CA.has_spanish_diacritic("mining")
    assert CA.has_kiche("ixim ulew") and not CA.has_kiche("maize and land")
    assert CA.has_qeqchi("ch'och' k'anjel") and not CA.has_qeqchi("land and work")
    assert CA.has_kaqchikel("samaj ruwach'ulew") and not CA.has_kaqchikel("work on the land")
    assert CA.has_mayan("ixim") and not CA.has_mayan("maize")
    assert len(CA.TERMINOLOGY) >= 14


def test_every_layers_queries_are_written_in_the_languages_of_the_ground() -> None:
    """A query in English finds an English article about the release, not the release."""
    terms = CA.layer_terms()
    accented = [layer for layer, qs in terms.items()
                if any(CA.has_spanish_diacritic(q) for q in qs)]
    assert len(accented) >= 9, f"only {accented} carry an accented Spanish query"
    mayan = [layer for layer, qs in terms.items() if any(CA.has_mayan(q) for q in qs)]
    assert len(mayan) >= 3, f"only {mayan} carry a Mayan-language query"
    native = sum(1 for row in CA.SOURCE_CLASSES if row["machine_use_allowed"]
                 for q in row["queries"] if CA.has_spanish_diacritic(q))
    assert native >= 50, f"only {native} accented queries across crawlable sources"


def test_query_territories_cover_every_layer_natively() -> None:
    """The deep-forest miner's own search space, per layer, in the language of the ground."""
    assert set(CA.QUERY_TERRITORIES) == set(CA.SOURCE_LAYERS)
    for layer, phrases in CA.QUERY_TERRITORIES.items():
        assert len(phrases) >= 3, f"{layer} has only {len(phrases)} query territories"
        assert any(CA.has_spanish_diacritic(p) for p in phrases), (
            f"{layer}'s query territory carries no accented Spanish at all")
    assert any(CA.has_mayan(p) for p in CA.QUERY_TERRITORIES["media"]), (
        "the media territory must reach the highland community press in its own language")


def test_every_source_carries_three_independent_labels_and_a_query() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in CA.SOURCE_CLASSES:
        assert row["access_label"] in CA.ACCESS_LABELS
        assert row["credibility"] in CA.CREDIBILITY_LABELS
        assert row["predictive_state"] in CA.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no native-language query"
        assert row["roots"], f"{row['id']} has no crawlable root"
        assert row["notes"], f"{row['id']} says nothing about why it is here"


def test_all_ten_source_layers_are_populated_and_every_absence_is_true() -> None:
    """The principal's depth rule: ten layers, none of them blank -- and a DECLARED absence that
    is checked against the actual source count, so it cannot be decorative."""
    counts = CA.layer_counts()
    assert set(counts) == set(CA.SOURCE_LAYERS)
    blank = [layer for layer, n in counts.items() if not n]
    assert blank == [], f"blank layers: {blank}"
    coverage = CA.source_layer_coverage()
    assert coverage["n_layers_covered"] == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible for a pack whose "
        "freight indices and coffee differentials both live behind a paywall")
    assert coverage["low_weight_kept"], "no fringe ground is kept at all, so it was dropped"
    assert CA.LAYER_ABSENCES == {}, "a pack-level absence declared here must carry a reason"
    # every jurisdiction owes an official ground and a media ground OF ITS OWN
    assert CA.jurisdiction_gaps() == [], f"unexplained gaps: {CA.jurisdiction_gaps()}"
    for cc in CA.JURISDICTIONS:
        own = CA.jurisdiction_layer_counts(cc)
        for layer in CA.REQUIRED_PER_JURISDICTION:
            assert own[layer] >= 1, f"{cc} has no {layer} ground of its own"


def test_the_measured_refusals_are_declared_with_a_lawful_substitute() -> None:
    """PANAMA HAS NO CENTRAL BANK, EL SALVADOR'S HAS NO INSTRUMENT, AND NICARAGUA'S PRESS IS IN
    EXILE. Each is a FACT ABOUT THE COUNTRY rather than a hole, and each must name what stands
    in for it. A layer row is checked against the real source count so it cannot be invented."""
    assert len(CA.NO_LAWFUL_GROUND) >= 5
    for row in CA.NO_LAWFUL_GROUND:
        assert row["jurisdiction"] in CA.JURISDICTIONS
        assert row["kind"] in ("layer", "object")
        assert row["what"] and row["reason"] and row["substitute"] and row["status"]
        if row["kind"] == "layer":
            assert row["what"] in CA.SOURCE_LAYERS, f"{row['what']} is not a source layer"
            counted = CA.jurisdiction_layer_counts(row["jurisdiction"])[row["what"]]
            assert counted == 0, (
                f"{row['jurisdiction']} declares {row['what']} absent but the pack names "
                f"{counted} source(s) in it -- a declaration that is not true is worse than none")
    by_cc = {(r["jurisdiction"], r["kind"], r["what"]) for r in CA.NO_LAWFUL_GROUND}
    assert any(cc == "pa" and kind == "object" and "central bank" in what
               for cc, kind, what in by_cc), "Panama's missing central bank is not declared"
    assert any(cc == "sv" and kind == "object" for cc, kind, _w in by_cc)
    assert any(cc == "ni" for cc, _k, _w in by_cc)
    # the substitutes the brief names, by name
    blob = " ".join(r["substitute"] for r in CA.NO_LAWFUL_GROUND)
    for must in ("Superintendencia de Bancos", "Article IV", "MIRROR CUSTOMS", "FEDERAL OPEN"):
        assert must in blob, f"the lawful substitute {must!r} is not named"
    # and Panama's absence is the same fact in the central-bank table
    assert CA.CENTRAL_BANKS["pa"]["exists"] is False
    assert CA.CENTRAL_BANKS["sv"]["exists"] is True
    assert "NO MONETARY INSTRUMENT" in CA.CENTRAL_BANKS["sv"]["framework"].upper()


def test_no_crypto_exchange_ground_is_hunted() -> None:
    """Mandate 2026-08-18: no venue order book, no exchange feed, no exchange as a source. The
    Salvadoran bitcoin material is a SOVEREIGN POLICY observable routed into the broker's CFD."""
    blob = " ".join(str(r["label"]) + " ".join(r["roots"]) + " ".join(r["queries"])
                    for r in CA.SOURCE_CLASSES).lower()
    for venue in ("binance", "bybit", "okx", "hyperliquid", "coinbase", "kraken", "bitfinex"):
        assert venue not in blob, f"{venue} is named as ground, which the mandate forbids"
    territory = " ".join(p for ps in CA.QUERY_TERRITORIES.values() for p in ps).lower()
    for venue in ("binance", "bybit", "okx", "coinbase"):
        assert venue not in territory
    # the boundary is stated in the pack itself, not only in this test
    constraints = " ".join(str(c["constraint"]) + str(c["measured"]) + str(c["consequence"])
                           for c in CA.ACCESS_CONSTRAINTS)
    assert "crypto-exchange" in constraints.lower()
    assert "order book" in constraints.lower()
    assert "BTCUSD" in constraints


# ------------------------------------------------------------------------------ the calendars
def test_the_holiday_table_resolves_for_all_three_years_inside_their_years() -> None:
    for year in (2024, 2025, 2026):
        table = holiday_table(CA.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        assert f"{year}-01-01" in table and f"{year}-12-25" in table
        assert f"{year}-09-15" in table, "15 September missing from the union table"
        assert f"{year}-11-28" in table, "Panama's independence day missing"
    assert CA.HOLIDAYS_RULE["rule"].strip()
    assert "anonymous Gregorian" in CA.HOLIDAYS_RULE["rule"]


def test_semana_santa_is_derived_and_closes_all_six_at_once() -> None:
    """MECHANISM FUNCTION ONE. Easter is computed with the anonymous Gregorian algorithm, so the
    one block that shuts the whole isthmus extends to any year without anybody editing it."""
    assert CA.easter(2024) == date(2024, 3, 31)
    assert CA.easter(2025) == date(2025, 4, 20)
    assert CA.easter(2026) == date(2026, 4, 5)
    assert set(CA.semana_santa(2025)) == {date(2025, 4, 17), date(2025, 4, 18)}
    for year in (2024, 2025, 2026):
        for day in CA.semana_santa(year):
            for cc in CA.JURISDICTIONS:
                assert CA.is_closed_in(cc, day), f"{cc} is open on {day} in Semana Santa"
        shared = CA.shared_closures(year, 6)
        assert set(CA.semana_santa(year)) <= set(shared), (
            "Semana Santa must appear as a six-country shared closure")
    # Panama's statutory Carnaval Tuesday is Easter minus 47 and Monday is not statutory
    lunes, martes = CA.carnaval(2025)
    assert (lunes, martes) == (date(2025, 3, 3), date(2025, 3, 4))
    assert lunes.weekday() == 0 and martes.weekday() == 1
    assert CA.is_closed_in("pa", martes)
    assert not CA.is_closed_in("pa", lunes), (
        "Carnaval Monday is NOT statutory in Panama; the pack must not claim it is")


def test_one_date_five_closures_and_panama_open_beside_them() -> None:
    """MECHANISM FUNCTION TWO, and the most distinctive calendar fact in the region: Guatemala,
    Honduras, El Salvador, Nicaragua and Costa Rica all left Spain in one act in 1821 and all
    five close on 15 September. PANAMA DOES NOT -- it left Colombia in 1903 -- so the control is
    free and inside the same isthmus."""
    for year in (2024, 2025, 2026):
        closures = CA.independence_day_closures(year)
        assert set(closures) == {"gt", "hn", "cr", "ni", "sv"}, closures
        assert all(d == date(year, 9, 15) for d in closures.values())
        assert not CA.is_closed_in("pa", date(year, 9, 15)), (
            "Panama must be OPEN on 15 September; that is the control")
        assert CA.shared_closures(year, 5).get(date(year, 9, 15)) == 5
        # Panama's own national days, which nobody else keeps
        for month, day in ((1, 9), (11, 3), (11, 28)):
            assert CA.is_closed_in("pa", date(year, month, day))
            for cc in ("gt", "hn", "cr", "ni", "sv"):
                assert not CA.is_closed_in(cc, date(year, month, day))


def test_the_feriado_morazanico_and_the_monday_shift_are_derived_not_typed() -> None:
    """Honduras replaced three fixed October days with one movable Wednesday-to-Saturday block in
    the week containing 3 October, and Costa Rica moves several days to the nearest Monday under
    the Ley de Traslado. Both are RULES and both are computed here."""
    for year in (2023, 2024, 2025, 2026):
        block = CA.morazanico(year)
        assert len(block) == 4
        assert block[0].weekday() == 2 and block[-1].weekday() == 5, "Wednesday to Saturday"
        assert all((b - block[0]).days == i for i, b in enumerate(block))
        # the block is anchored on the ISO week that contains 3 October
        anchor = date(year, 10, 3)
        assert abs((anchor - block[0]).days) <= 4, f"{year}: the block is not on 3 October's week"
        for day in block:
            if day.year == year:
                assert CA.is_closed_in("hn", day)
    assert CA.morazanico(2024)[0] == date(2024, 10, 2)
    assert CA.morazanico(2025)[0] == date(2025, 10, 1)
    # the three old fixed dates are NOT carried as Honduran closures any more
    for month, day in ((10, 3), (10, 12), (10, 21)):
        assert (month, day) not in {(m, d) for m, d, _n in CA.FIXED_HOLIDAYS["hn"]}
    # Costa Rica's Ley de Traslado, derived: Tue/Wed back to Monday, Thu-Sun forward to Monday
    assert CA.monday_shift(date(2025, 4, 14)) == date(2025, 4, 14)          # already a Monday
    assert CA.monday_shift(date(2025, 7, 22)) == date(2025, 7, 21)          # Tuesday -> back
    assert CA.monday_shift(date(2025, 7, 23)) == date(2025, 7, 21)          # Wednesday -> back
    assert CA.monday_shift(date(2025, 7, 25)) == date(2025, 7, 28)          # Friday -> forward
    assert CA.monday_shift(date(2025, 7, 27)) == date(2025, 7, 28)          # Sunday -> forward
    assert all(CA.monday_shift(date(2025, 7, d)).weekday() == 0 for d in range(21, 28))
    for year in (2024, 2025, 2026):
        moved = {CA.monday_shift(date(year, m, d)) for m, d in CA.MONDAY_MOVED["cr"]}
        for day in moved:
            assert day.weekday() == 0
            assert CA.is_closed_in("cr", day), f"{day} is not in the Costa Rican table"
        # the un-shifted date must NOT be a closure when the rule moved it
        for m, d in CA.MONDAY_MOVED["cr"]:
            raw = date(year, m, d)
            if raw.weekday() != 0:
                assert not CA.is_closed_in("cr", raw), f"{raw} was moved and is still closed"
    assert "9875" in CA.HOLIDAYS_RULE["authority"] or "Traslado" in CA.HOLIDAYS_RULE["authority"]
    assert CA.HOLIDAYS_RULE["unresolved"], "the unresolved membership must be declared, not hidden"


def test_market_holidays_drop_weekend_feriados_because_no_session_is_lost() -> None:
    """None of the six substitutes a weekend holiday onto the Monday as a general rule, and the
    one Monday rule that does exist is Costa Rica's and is already applied."""
    for year in (2024, 2025, 2026):
        assert all(d.weekday() < 5 for d in CA.market_holidays(year))
        assert set(CA.market_holidays(year)) <= set(CA.region_holidays(year))


# ------------------------------------------------------------------------------ the mechanisms
def test_the_canal_constraint_is_a_published_dated_step_series() -> None:
    """THE PACK'S REASON TO EXIST. The operator publishes its own binding constraint: the draft
    and the bookable slots are step functions with effective dates, and 2023-2024 took the slots
    from 36 a day to 22."""
    assert CA.TRANSIT_BASELINE == 36
    assert CA.bookable_slots(date(2023, 1, 1)) == 36
    assert CA.bookable_slots(date(2023, 12, 15)) == 22
    assert CA.bookable_slots(date(2025, 1, 1)) == 36
    assert CA.is_canal_constrained(date(2023, 12, 15)) is True
    assert CA.is_canal_constrained(date(2022, 6, 1)) is False
    assert CA.is_canal_constrained(date(2025, 1, 1)) is False
    assert CA.constraint_severity(date(2023, 12, 15)) == "EXTREME"
    assert CA.constraint_severity(date(2023, 8, 1)) == "MILD"
    assert CA.constraint_severity(date(2025, 1, 1)) == "NONE"
    assert CA.authorised_draft(date(2022, 1, 1)) == CA.DRAFT_DESIGN_MAX_FT
    assert CA.authorised_draft(date(2023, 8, 1)) == 44.0
    assert CA.authorised_draft(date(2025, 6, 1)) == 50.0
    days = CA.constraint_days(date(2023, 1, 1), date(2024, 12, 31))
    assert len(days) >= 300, f"only {len(days)} constrained days in the 2023-2024 episode"
    assert all(CA.is_canal_constrained(d) for d in days)
    # every step is hypothesis-grade until its advisory number is attached
    assert all(s == "PRESS_REPORTED" for _d, _v, s in CA.SLOT_STEPS[1:])
    assert all(s == "PRESS_REPORTED" for _d, _v, s in CA.DRAFT_STEPS[1:])
    assert max(p for _d, p, _w, _s in CA.AUCTION_PRINTS) >= 3_000_000.0
    assert CA.GATUN_BAND_FT_PLD[0] < CA.GATUN_BAND_FT_PLD[1]


def test_the_substitution_control_is_named_and_is_not_optional() -> None:
    """When one chokepoint closes, the other's traffic is the counterfactual. 2023-2024
    constrained BOTH for unrelated reasons, which makes the pair a control only if both series
    are carried -- so the pack must name Suez and Bab el-Mandeb explicitly."""
    named = " ".join(str(r["name"]) for r in CA.CHOKEPOINT_CONTROLS)
    assert "Suez" in named and "Bab el-Mandeb" in named and "Cape" in named
    assert len(CA.CHOKEPOINT_CONTROLS) >= 3
    for row in CA.CHOKEPOINT_CONTROLS:
        assert row["observable"] and row["why"] and row["status"]
    canal = {d["id"]: d for d in CA.DOMAINS}["CA-A"]
    controls = " ".join(canal["controls"])
    assert "Suez" in controls and "Bab el-Mandeb" in controls
    sub = {d["id"]: d for d in CA.DOMAINS}["CA-D"]
    assert "both-constrained" in " ".join(sub["controls"]).lower()
    report = CA.chokepoint_substitution(None, None)
    assert any("PortWatch" in u for u in report["unmeasured"]), (
        "the control miner must say UNMEASURED by name when the counterfactual series is absent")


def test_the_coffee_harvest_year_is_the_sampling_frame_and_brazil_is_the_control() -> None:
    """All five origins run 1 October to 30 September, and the Brazilian shock rows are kept
    SEPARATE so a study cannot pool the two origins into one weather story."""
    assert CA.coffee_harvest_year(date(2024, 10, 1)) == 2024
    assert CA.coffee_harvest_year(date(2024, 9, 30)) == 2023
    assert CA.coffee_harvest_year(date(2025, 3, 1)) == 2024
    assert CA.harvest_phase(date(2024, 11, 15)) == "harvest_opening"
    assert CA.harvest_phase(date(2025, 3, 1)) == "export_peak"
    assert CA.harvest_phase(date(2025, 7, 1)) == "lean"
    assert CA.harvest_phase(date(2025, 9, 1)) == "flowering_and_filling"
    assert set(CA.COFFEE_INSTITUTES) == set(CA.JURISDICTIONS) - {"pa"}
    for cc, row in CA.COFFEE_INSTITUTES.items():
        assert row["name"] and row["root"].startswith("https://") and row["series"]
        assert row["note"], f"{cc} institute has no note"
    controls = [r for r in CA.COFFEE_SHOCKS if "CONTROL" in r[2]]
    origins = [r for r in CA.COFFEE_SHOCKS if "CONTROL" not in r[2]]
    assert controls and origins, "the two-origin substitution needs both sides declared"
    assert all(r[2].startswith("br") for r in controls)
    # a Brazilian control window must never be counted as an isthmus shock day
    brazil_days = CA.origin_shock_days(date(2021, 7, 1), date(2021, 8, 31))
    assert brazil_days == [], "the 2021 Brazilian frost is a CONTROL and not an isthmus shock"
    roya = CA.origin_shock_days(date(2013, 1, 1), date(2013, 1, 31))
    assert len(roya) == 31, "the roya epidemic window must read as an isthmus shock"
    assert all(s == "PRESS_REPORTED" for *_rest, s in CA.COFFEE_SHOCKS)
    assert CA.coffee_shocks_in(date(2021, 7, 25), date(2021, 7, 26))


def test_the_monetary_experiment_has_six_arms_and_two_dollarised_replicates() -> None:
    """Six neighbours, one trade structure, four monetary regimes -- and the sharpest pair is
    Panama and El Salvador: the same money, with and without a central bank attached."""
    assert set(CA.FX_REGIMES) == set(CA.JURISDICTIONS)
    arms = CA.regime_groups()
    assert len(arms) == 6, f"the arms collapsed: {arms}"
    assert CA.fx_regime("pa") == "DOLLAR_NO_CENTRAL_BANK"
    assert CA.fx_regime("sv") == "DOLLAR_WITH_TOOTHLESS_BANK"
    assert CA.fx_regime("ni") == "CRAWL_AT_ZERO"
    assert CA.fx_regime("zz") == "UNMEASURED"
    receivers = [cc for cc in CA.JURISDICTIONS if CA.remittance_regime(cc) == "RECEIVER"]
    assert set(receivers) == {"gt", "hn", "ni", "sv"}, receivers
    assert CA.remittance_regime("cr") == "SENDER_OR_TRANSIT"
    assert CA.remittance_regime("pa") == "SENDER_OR_TRANSIT"
    assert CA.remittance_regime("zz") == "UNMEASURED"
    # five Mother's Days, and Honduras's is DERIVED from the second-Sunday rule
    assert CA.mothers_day("gt", 2025) == date(2025, 5, 10)
    assert CA.mothers_day("cr", 2025) == date(2025, 8, 15)
    assert CA.mothers_day("pa", 2025) == date(2025, 12, 8)
    for year in (2024, 2025, 2026):
        got = CA.mothers_day("hn", year)
        assert got is not None and got.weekday() == 6 and got.month == 5
        assert 8 <= got.day <= 14, "the second Sunday in May is always the 8th to the 14th"
    assert CA.mothers_day("zz", 2025) is None
    peaks = CA.remittance_peaks(2025)
    assert len(peaks) >= 5 and date(2025, 12, 20) in peaks


def test_positioning_declares_the_absent_cot_rather_than_silently_missing_it() -> None:
    """No contract exists for any of the six currencies, and two of them are the dollar and
    cannot have one by construction. An absence a study can trip over must be named."""
    rows = {r["name"]: r for r in CA.POSITIONING_SOURCES}
    missing = [r for r in rows.values() if not r["available"]]
    assert missing, "the COT question is not answered anywhere in the pack"
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in missing)
    assert CA.COT_CURRENCY == ""
    for row in CA.POSITIONING_SOURCES:
        if row["available"]:
            assert row["root"].startswith("http") and row["fields"] and row["pit_warning"]


def test_every_dataset_carries_all_twelve_fields_and_a_fetchable_route() -> None:
    from countries import DATASET_FIELDS
    assert len(CA.DATASETS) >= 18
    for row in CA.DATASETS:
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
        assert resolve(row["assets"])["absent"] == [], f"{row['name']}: unknown asset"
    assert any(not row["pit_feasible"] for row in CA.DATASETS), (
        "every dataset claims to be point-in-time reconstructible, which is not true of a pack "
        "whose primary source supersedes its own advisories in place")
    assert any(row["pit_feasible"] for row in CA.DATASETS), (
        "no dataset is point-in-time reconstructible at all, which would make every cell "
        "NOT_PIT_SAFE by construction")
