"""THE ATLANTIC HYDROCARBON PROVINCE PACK, VALIDATED -- four sovereigns, one basin, one gauntlet.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A FOUR-COUNTRY PACK THAT IS REALLY A ONE-COUNTRY PACK WITH FOUR FLAGS. The parity fence
    counts `JURISDICTIONS`, so a pack that claims four and answers for one would be credited with
    four. `test_every_jurisdiction_owns_its_own_actors_domains_and_cells` counts actors, domains
    and CELLS per jurisdiction and fails if any of the four is decorative.
  * AN ENGLISH GLOSSARY OF A FOUR-LANGUAGE PROVINCE. English is the OFFICIAL language of Guyana
    and Trinidad, so it is the native ground there and is used as such -- but Venezuela is
    Spanish, Suriname is Dutch and Sranan Tongo, and the Guyanese interior economy is discussed
    in Creolese. All four vocabularies are asserted by name.
  * A SYMBOL THE BOX CANNOT TRADE. Every executable instrument, every domain instrument, every
    edge target and every interaction target is checked against the broker's OWN registry. All
    four local currencies are absent and all four must stay transmission targets.
  * A SINGLE-NAME EQUITY ON A DOCKET. This province is made of national champions -- the
    operators, the state oil companies, the petrochemical producers, the miners -- and the
    two-lane order (2026-09-06) forbids hunting any of them. They appear only as ACTORS.
  * HENRY HUB PRETENDING TO BE ATLANTIC LNG. The single most dangerous substitution in this pack
    has its own test: the basis risk must be stated in the transmission target, in the domain,
    in the edge and in `ACCESS_CONSTRAINTS`.
  * AN UNLAWFULNESS LEFT TO INFERENCE. Venezuela is under a sanctions regime and the pack must
    say in `ACCESS_CONSTRAINTS` exactly what it does and does not touch.
  * A HOLIDAY TABLE SOMEBODY TYPED. Everything Christian and movable is DERIVED from Easter with
    the anonymous Gregorian algorithm; Guyana's four-faith lunar calendar is TYPED with its
    gazetting authority, which is honest, and a computed guess would not be.
  * A CELL COUNT THAT IS A CARTESIAN TRICK. `cells()` is checked for real conditions, for
    instruments that belong to the domain that minted them, and for declared instruments no
    domain ever uses.
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
    DATASET_FIELDS,
    check_pack,
    get,
    holiday_table,
    resolve,
    universe_symbols,
)
from countries.atlantic_energy import pack as AE  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as F  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")
#: Which jurisdiction owns which domain. The pack carries the same mapping in
#: `cells_by_jurisdiction`; asserting it here means the two cannot drift apart silently.
DOMAIN_OWNER = {"AE-A": "gy", "AE-B": "gy", "AE-C": "gy",
                "AE-D": "tt", "AE-E": "tt", "AE-F": "tt",
                "AE-G": "ve", "AE-H": "ve", "AE-I": "ve",
                "AE-J": "sr", "AE-K": "sr",
                "AE-L": "province", "AE-M": "province"}


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it. Resolved through `resolve_pack` so the test measures
    the same object the country lab runs, not a private construction."""
    got = CL.resolve_pack("atlantic_energy")
    assert got is not None, "no Atlantic-energy pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(AE.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == "atlantic_energy"
    assert str(get(built, "region_command")) == "latam"
    assert str(get(built, "currency")) == "GYD"
    assert AE.CODE == "ATLANTIC_ENERGY"
    assert AE.FOREST == "latam"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    """A coercion note is a field `CountryPack` could not read. There must be none, and
    `validate_pack` must be clean rather than merely non-fatal."""
    notes = list(getattr(built, "coercion_notes", ()) or ())
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    problems = CL.validate_pack(built)
    assert problems == [], f"validate_pack: {problems[:4]}"
    assert CL.fatal_problems(problems) == []


def test_jurisdictions_are_the_four_and_all_are_on_the_desks_own_roster() -> None:
    """THE PARITY FENCE COUNTS THIS TUPLE. Guyana, Trinidad, Venezuela and Suriname are four
    countries on the latam roster that no sibling pack answers for: `br`, `mx`, `cl`, `co`,
    `ar`, `pe` and `bo` are each written around a domestic policy object none of these has."""
    assert AE.JURISDICTIONS == ("gy", "tt", "ve", "sr")
    assert all(c == c.lower() and len(c) == 2 for c in AE.JURISDICTIONS)
    roster = {c.lower() for forest in F.FORESTS.values() for c in forest.countries}
    for code in AE.JURISDICTIONS:
        assert code in roster, f"{code} is not on the forest roster in libs/research/forests.py"
    assert "atlantic_energy" in F.FORESTS["latam"].packs
    # the four currencies are declared and NOT ONE of them is a broker symbol
    assert set(AE.CURRENCIES) == set(AE.JURISDICTIONS)
    registry = universe_symbols()
    for cc, row in AE.CURRENCIES.items():
        assert row["broker_quoted"] is False, f"{cc} claims to be quoted"
        assert row["code"] not in registry, f"{row['code']} is in the registry after all"
        assert row["regime"] and row["authority"] and row["fact"]


def test_pack_reaches_its_declared_parity_depth(built: Any) -> None:
    """The standing depth rule, MEASURED by the framework and not claimed by the pack."""
    row = RP.pack_depth(built, "atlantic_energy").as_row()
    assert row["score"] >= AE.DECLARED_DEPTH, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    assert row["fatal"] == []
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_depth_counts_sit_above_the_multi_jurisdiction_floor() -> None:
    """A FOUR-JURISDICTION PACK OWES MORE THAN A ONE-COUNTRY PACK. The framework's floors are
    twelve actors and ten domains; a province of four sovereigns written to those floors would
    be answering for four countries with one country's depth."""
    assert len(AE.ACTORS) >= 18
    assert len(AE.DOMAINS) >= 13
    assert len(AE.TRANSMISSION_EDGES_SEED) >= 11
    assert len(AE.DATASETS) >= 17
    assert len(AE.SOURCE_CLASSES) >= 22
    assert len(AE.POLICY_ERAS) >= 8
    assert len(AE.INTERACTIONS) >= 4
    assert len(AE.TRANSMISSION_TARGETS) >= 8
    assert AE.term_count() >= 150


def test_every_jurisdiction_owns_its_own_actors_domains_and_cells() -> None:
    """THE TEST THAT STOPS A ONE-COUNTRY PACK WEARING FOUR FLAGS. Every jurisdiction owes at
    least four actors and two domains of its OWN, and must mint real cells."""
    by_actor = AE.actors_by_jurisdiction()
    for cc in AE.JURISDICTIONS:
        assert by_actor.get(cc, 0) >= 4, (
            f"{cc} owes at least four actors of its own; it has {by_actor.get(cc, 0)}")
    assert sum(by_actor.values()) == len(AE.ACTORS), "an actor belongs to no jurisdiction"
    for actor in AE.ACTORS:
        assert str(actor["jurisdiction"]) in (*AE.JURISDICTIONS, "province"), (
            f"actor {actor['name']!r} declares an unknown jurisdiction")
    owned: dict[str, int] = {}
    for dom in AE.DOMAINS:
        owned[DOMAIN_OWNER[str(dom["id"])]] = owned.get(DOMAIN_OWNER[str(dom["id"])], 0) + 1
    for cc in AE.JURISDICTIONS:
        assert owned.get(cc, 0) >= 2, f"{cc} owes at least two domains of its own"
    by_cc = AE.cells_by_jurisdiction()
    for cc in AE.JURISDICTIONS:
        assert by_cc.get(cc, 0) >= 10, f"{cc} mints only {by_cc.get(cc, 0)} cells"


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    for row in AE.ACTORS:
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
    names = [str(a["name"]) for a in AE.ACTORS]
    assert len(names) == len(set(names)), "an actor is declared twice"


def test_every_domain_has_objects_conditions_and_two_negative_controls() -> None:
    """Without a control an effect cannot be told from the desk's own sampling."""
    for row in AE.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert len(row["conditions"]) >= 3, f"domain {row['id']} names too few conditions"
        assert row["instruments"], f"domain {row['id']} names no instrument"
        assert row["id"] in AE.DOMAIN_CELL_SPEC, f"{row['id']} mints cells with no family"
        assert row["id"] in DOMAIN_OWNER, f"{row['id']} belongs to no jurisdiction"


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(AE.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    for must in ("XBRUSD", "XTIUSD", "XNGUSD"):
        assert must in AE.EXECUTABLE_INSTRUMENTS, f"{must} is the province's own contract"


def test_every_transmission_seed_and_interaction_names_tradable_targets() -> None:
    """A seed that terminates in a symbol the box cannot quote can never compile a cell."""
    for seed in AE.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"
    for row in AE.INTERACTIONS:
        split = resolve(row["targets"])
        assert split["absent"] == [], f"interaction with {row['with']} -> {split['absent']}"
        assert split["equities"] == [], f"interaction with {row['with']} -> {split['equities']}"
        assert row["control"] and row["observable"] and row["mechanism"]
    # the brief's two REAL physical neighbours: the Colombian border and the Brazilian grid
    withs = {str(r["with"]) for r in AE.INTERACTIONS}
    assert {"co", "br"} <= withs, f"the border and the grid neighbours are missing: {withs}"
    assert "atlantic_energy" not in withs, "a pack cannot interact with itself"


def test_domain_instruments_are_tradable_and_never_single_names() -> None:
    for row in AE.DOMAINS:
        split = resolve(row["instruments"])
        assert split["absent"] == [], f"domain {row['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"domain {row['id']} -> equity {split['equities']}"


def test_all_four_currencies_are_named_absent_with_a_route_and_a_basis_risk() -> None:
    """GYD, TTD, VES and SRD are none of them quoted, and so are ammonia, methanol and LNG.
    Each must carry a carrier, a route AND the basis risk that carrier introduces."""
    registry = universe_symbols()
    assert not {"GYD", "TTD", "VES", "SRD", "USDGYD", "USDTTD"} & set(registry)
    named = " ".join(str(t["name"]) for t in AE.TRANSMISSION_TARGETS)
    for code in ("GYD", "TTD", "VES", "SRD"):
        assert code in named, f"{code} is absent from the broker and unnamed in the pack"
    for word in ("LNG", "Ammonia", "Methanol", "Merey"):
        assert word in named, f"{word} is not a broker symbol and must be routed explicitly"
    for row in AE.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert row["route"], f"{row['name']} is named absent with no route"
        assert row["basis_risk"], f"{row['name']} is routed with no basis risk stated"
        assert resolve(row["proxies"])["absent"] == []


def test_henry_hub_is_not_atlantic_lng_and_the_pack_says_so_three_times() -> None:
    """THE MOST DANGEROUS SUBSTITUTION IN THIS PACK. A study that swapped one for the other
    would measure the arbitrage rather than the shock, so the warning is in the transmission
    target, in the domain, in the edge and in the access constraints."""
    lng = [t for t in AE.TRANSMISSION_TARGETS if "LNG cargoes" in str(t["name"])]
    assert lng and "HENRY HUB IS NOT ATLANTIC LNG" in str(lng[0]["basis_risk"])
    dom = {d["id"]: d for d in AE.DOMAINS}["AE-D"]
    assert "HENRY HUB IS NOT ATLANTIC LNG" in str(dom["notes"])
    assert any("storage" in c for c in dom["controls"])
    edge = {e["id"]: e for e in AE.TRANSMISSION_EDGES_SEED}["AE-E3"]
    assert edge["sign"] == "?", "the sign of a Trinidadian gas outage on Henry Hub is ambiguous"
    assert "MEASURING AMERICA" in str(edge["condition"]).upper()
    blob = " ".join(str(c["constraint"]) + str(c["consequence"]) for c in AE.ACCESS_CONSTRAINTS)
    assert "HENRY HUB IS NOT ATLANTIC LNG" in blob


def test_the_national_champions_appear_only_as_actors() -> None:
    """The operators, the state oil companies, the petrochemical producers and the miners are
    the loudest mechanisms in this province and the two-lane order forbids hunting any."""
    actor_names = " ".join(str(a["name"]) for a in AE.ACTORS)
    for who in ("Stabroek", "Atlantic LNG", "PDVSA", "Staatsolie", "Point Lisas", "Gold Board"):
        assert who in actor_names, f"{who} is not carried as an actor"
    every_symbol: set[str] = set(AE.EXECUTABLE_INSTRUMENTS)
    for row in AE.DOMAINS:
        every_symbol |= set(row["instruments"])
    for seed in AE.TRANSMISSION_EDGES_SEED:
        every_symbol |= set(seed["targets"])
    for actor in AE.ACTORS:
        every_symbol |= set(actor["instruments"])
    assert resolve(sorted(every_symbol))["equities"] == []


def test_sanctions_lawfulness_is_stated_and_not_left_to_inference() -> None:
    """Venezuela is under a sanctions regime and the pack must say exactly what it touches."""
    rows = [c for c in AE.ACCESS_CONSTRAINTS if "SANCTIONS REGIME" in str(c["constraint"])]
    assert rows, "the sanctions boundary is not stated in ACCESS_CONSTRAINTS at all"
    blob = str(rows[0]["measured"]) + str(rows[0]["consequence"])
    for phrase in ("PRIVATE SYSTEMS", "ACCESS CONTROL", "TRANSACTIONS", "broker symbols"):
        assert phrase in blob, f"the lawfulness statement does not mention {phrase!r}"
    for source in ("OFAC", "Federal Register", "OPEC", "EIA", "court docket"):
        assert source in blob, f"the public-source list omits {source!r}"


# ------------------------------------------------------------------------------ the cells
def test_cells_are_real_and_every_declared_instrument_is_used() -> None:
    """THE POINT OF A PACK IS CELLS REACHING THE GAUNTLET. They must also be honest: each cell
    names a condition its own domain declared, on an instrument that domain owns."""
    rows = AE.cells()
    assert 60 <= len(rows) <= 260, f"{len(rows)} cells is outside the honest range"
    by_domain = {d["id"]: d for d in AE.DOMAINS}
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
    unused = [s for s, n in AE.cells_by_symbol().items() if n == 0]
    assert unused == [], f"declared executable but no domain uses it: {unused}"


def test_mine_reports_the_cell_count_and_emits_nothing_without_a_ctx() -> None:
    """`mine(None)` is a MEASUREMENT of what the pack would emit and writes nowhere."""
    report = AE.mine(None)
    assert report["code"] == "atlantic_energy"
    assert report["cells_emitted"] == len(AE.cells())
    assert report["emitted"] > 0
    assert report["rows"] and all(r.get("miner") for r in report["rows"])
    assert report["jurisdictions"] == ("gy", "tt", "ve", "sr")
    assert {"co", "br"} <= set(report["interactions"])
    # UNMEASURED is a real answer: the miners that need a series this box does not carry say so
    assert any("UNMEASURED" in u or "not loaded" in u or "not in this pack" in u
               for u in report["unmeasured"]), report["unmeasured"][:3]
    assert any("HENRY_HUB_BASIS" in u for u in report["unmeasured"]), (
        "the gas miner must carry the basis warning as an UNMEASURED row on every pass")
    # nothing reached a registry: there is no connection and no ctx, so no discovery id exists
    assert "recorded" not in report


def test_every_custom_miner_entry_resolves(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {f"custom:{name}" for name in AE.MINERS}
    assert all(callable(fn) for fn in got.values())
    ids = {d["id"] for d in AE.DOMAINS}
    for row in AE.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.atlantic_energy.pack", row["entry"]
        assert func in AE.MINERS, f"{row['entry']} is not in the MINERS table"
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    for domains in AE.MINER_DOMAINS.values():
        assert set(domains) <= ids


# ------------------------------------------------------------------------------ the languages
def test_terminology_carries_all_four_language_grounds() -> None:
    """FOUR GROUNDS. English is OFFICIAL in Guyana and Trinidad, so it is the native ground
    there rather than a shortcut -- and Spanish, Dutch, Sranan Tongo and Guyanese Creolese carry
    the other two jurisdictions and the physical economy of all four."""
    assert len(AE.spanish_terms()) == len(AE.SPANISH_MARKERS), (
        f"missing Spanish vocabulary: "
        f"{sorted(set(AE.SPANISH_MARKERS) - set(AE.spanish_terms()))}")
    assert len(AE.dutch_terms()) == len(AE.DUTCH_MARKERS), (
        f"missing Dutch vocabulary: {sorted(set(AE.DUTCH_MARKERS) - set(AE.dutch_terms()))}")
    assert len(AE.sranan_terms()) >= 5, "Sranan Tongo vocabulary is too thin to crawl with"
    assert len(AE.creolese_terms()) >= 5, "no usable Guyanese Creolese vocabulary at all"
    assert len(AE.accented_terms()) >= 15, (
        f"only {len(AE.accented_terms())} terms carry a Spanish diacritic")
    flat = {t for group in AE.TERMINOLOGY.values() for t in group}
    for must in ("Natural Resource Fund", "cost recovery ceiling", "Atlantic LNG",
                 "gas curtailment", "Point Lisas", "General Licence 44", "Faja del Orinoco",
                 "hiperinflación", "Block 58", "Staatsolie", "Essequibo", "backdam",
                 "ship-to-ship transfer"):
        assert must in flat, f"the province pack does not carry {must!r}"
    assert AE.has_spanish_diacritic("producción") and not AE.has_spanish_diacritic("production")
    assert AE.has_dutch("olieproductie kwartaal") and not AE.has_dutch("oil production quarter")
    assert AE.has_sranan("gowtu wroko") and not AE.has_sranan("gold work")
    assert AE.has_creolese("backdam dredge") and not AE.has_creolese("interior mining site")
    assert len(AE.TERMINOLOGY) >= 13
    assert set(AE.TERMINOLOGY) == {d["id"] for d in AE.DOMAINS}


def test_every_layers_queries_are_written_in_the_languages_of_the_ground() -> None:
    """A query in the wrong language finds an article about the release, not the release."""
    terms = AE.layer_terms()
    accented = [layer for layer, qs in terms.items()
                if any(AE.has_spanish_diacritic(q) for q in qs)]
    assert len(accented) >= 8, f"only {accented} carry an accented Spanish query"
    dutch = [layer for layer, qs in terms.items() if any(AE.has_dutch(q) for q in qs)]
    assert len(dutch) >= 5, f"only {dutch} carry a Dutch query"
    creole = [layer for layer, qs in terms.items()
              if any(AE.has_sranan(q) or AE.has_creolese(q) for q in qs)]
    assert len(creole) >= 3, f"only {creole} reach the Sranan or Creolese ground"


def test_query_territories_cover_every_layer_natively() -> None:
    """The deep-forest miner's own search space, per layer, in the languages of the ground."""
    assert set(AE.QUERY_TERRITORIES) == set(AE.SOURCE_LAYERS)
    for layer, phrases in AE.QUERY_TERRITORIES.items():
        assert len(phrases) >= 3, f"{layer} has only {len(phrases)} query territories"
    accented = [k for k, v in AE.QUERY_TERRITORIES.items()
                if any(AE.has_spanish_diacritic(p) for p in v)]
    assert len(accented) >= 7, f"only {accented} carry accented Spanish"
    dutch = [k for k, v in AE.QUERY_TERRITORIES.items() if any(AE.has_dutch(p) for p in v)]
    assert len(dutch) >= 5, f"only {dutch} carry Dutch"
    creole = [k for k, v in AE.QUERY_TERRITORIES.items()
              if any(AE.has_sranan(p) or AE.has_creolese(p) for p in v)]
    assert len(creole) >= 3, f"only {creole} reach the Sranan or Creolese ground"


def test_every_source_carries_three_independent_labels_and_a_query() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in AE.SOURCE_CLASSES:
        assert row["access_label"] in AE.ACCESS_LABELS
        assert row["credibility"] in AE.CREDIBILITY_LABELS
        assert row["predictive_state"] in AE.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no query"
        assert row["roots"], f"{row['id']} has no crawlable root"
        assert row["notes"], f"{row['id']} says nothing about why it is here"


def test_all_ten_source_layers_are_populated_and_the_real_absences_are_per_jurisdiction() -> None:
    """The principal's depth rule: ten layers, none of them blank. In a four-country pack the
    honest unit of absence is (jurisdiction, layer) -- a layer Guyana covers is not absent
    because Venezuela does not -- so the measured refusals live in `NO_LAWFUL_GROUND`."""
    counts = AE.layer_counts()
    assert set(counts) == set(AE.SOURCE_LAYERS)
    assert [layer for layer, n in counts.items() if not n] == []
    coverage = AE.source_layer_coverage()
    assert coverage["n_layers_covered"] == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible for a province "
        "whose ammonia, methanol and LNG assessments all sit behind agency terms")
    assert coverage["low_weight_kept"], "no unreliable ground is kept at all, so it was dropped"
    assert AE.LAYER_ABSENCES == {}, "a province-level absence would be false here"
    # the measured refusals, each with its LAWFUL SUBSTITUTE named
    assert len(AE.NO_LAWFUL_GROUND) >= 5
    for row in AE.NO_LAWFUL_GROUND:
        assert row["jurisdiction"] in AE.JURISDICTIONS
        assert row["layer"] in AE.SOURCE_LAYERS
        assert len(str(row["reason"])) > 60, f"{row['jurisdiction']}:{row['layer']} has no reason"
        assert len(str(row["substitute"])) > 60, (
            f"{row['jurisdiction']}:{row['layer']} declares an absence with no lawful substitute")
    ve = {r["layer"] for r in AE.no_lawful_ground("ve")}
    assert "official" in ve, (
        "Venezuela's broken statistical record is the most important absence in this pack and "
        "it must be declared by name")
    substitutes = " ".join(str(r["substitute"]) for r in AE.no_lawful_ground("ve"))
    for named in ("secondary sources", "finance observatory", "mirror", "tanker"):
        assert named in substitutes.lower(), f"the Venezuelan substitute list omits {named!r}"


def test_no_crypto_exchange_ground_is_hunted() -> None:
    """Mandate 2026-08-18: no venue order book, no exchange feed, no exchange as a source."""
    blob = " ".join(str(r["label"]) + " ".join(r["roots"]) + " ".join(r["queries"])
                    for r in AE.SOURCE_CLASSES).lower()
    for venue in ("binance", "bybit", "okx", "hyperliquid", "coinbase", "kraken"):
        assert venue not in blob, f"{venue} is named as ground, which the mandate forbids"


def test_every_dataset_carries_all_twelve_fields_and_a_fetchable_route() -> None:
    assert len(AE.DATASETS) >= 17
    for row in AE.DATASETS:
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
        assert set(row.keys()) == set(DATASET_FIELDS), (
            f"dataset {row['name']!r} carries a thirteenth key, which reaches the framework as "
            f"a coercion note because DatasetRow has no `notes` field")
    assert any(not row["pit_feasible"] for row in AE.DATASETS), (
        "every dataset claims to be point-in-time reconstructible, which is not true of a "
        "province whose ministries publish the current file over the same link")


# ------------------------------------------------------------------------------ the calendars
def test_the_holiday_table_resolves_for_all_three_years_inside_their_years() -> None:
    for year in (2024, 2025, 2026):
        table = holiday_table(AE.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        assert f"{year}-01-01" in table, "New Year's Day is missing"
        assert f"{year}-12-25" in table, "Christmas is missing"
        assert f"{year}-02-23" in table, "Guyana's Republic Day (Mashramani) is missing"
        assert f"{year}-08-31" in table, "Trinidad's Independence Day is missing"
        assert f"{year}-07-05" in table, "Venezuela's Independence Day is missing"
        assert f"{year}-11-25" in table, "Suriname's Independence Day is missing"
    assert "anonymous Gregorian" in AE.HOLIDAYS_RULE["rule"]
    assert "NO WEEKEND SUBSTITUTION" in AE.HOLIDAYS_RULE["rule"]


def test_easter_is_computed_and_carnival_follows_from_it() -> None:
    """MECHANISM FUNCTION ONE. Easter is derived with the anonymous Gregorian algorithm, so
    Carnival, Corpus Christi and the Holy Week days extend to any year with no editing."""
    assert AE.easter(2024) == date(2024, 3, 31)
    assert AE.easter(2025) == date(2025, 4, 20)
    assert AE.easter(2026) == date(2026, 4, 5)
    assert AE.carnival(2024) == (date(2024, 2, 12), date(2024, 2, 13))
    assert AE.carnival(2025) == (date(2025, 3, 3), date(2025, 3, 4))
    assert AE.carnival(2026) == (date(2026, 2, 16), date(2026, 2, 17))
    assert AE.ash_wednesday(2025) == date(2025, 3, 5)
    assert AE.corpus_christi(2024) == date(2024, 5, 30)
    assert AE.corpus_christi(2026) == date(2026, 6, 4)
    for year in (2024, 2025, 2026):
        monday, tuesday = AE.carnival(year)
        assert monday.weekday() == 0 and tuesday.weekday() == 1
        # STATUTORY in Venezuela, NOT statutory in Trinidad, and Trinidad is the one that shuts
        assert AE.is_closed_in("ve", monday), "Carnival is a Venezuelan public holiday"
        assert not AE.is_closed_in("tt", monday), (
            "Carnival Monday is NOT on the Trinidadian statutory list, and the pack must not "
            "pretend otherwise")
        assert monday in AE.carnival_shutdown(year)
        assert monday in AE.province_holidays(year)


def test_caricom_day_is_the_first_monday_of_july_and_is_derived() -> None:
    assert AE.caricom_day(2024) == date(2024, 7, 1)
    assert AE.caricom_day(2025) == date(2025, 7, 7)
    assert AE.caricom_day(2026) == date(2026, 7, 6)
    for year in (2024, 2025, 2026):
        assert AE.caricom_day(year).weekday() == 0
        assert AE.is_closed_in("gy", AE.caricom_day(year))


def test_guyanas_four_faith_calendar_is_the_packs_distinguishing_calendar_fact() -> None:
    """GUYANA CARRIES CHRISTIAN, HINDU AND ISLAMIC NATIONAL HOLIDAYS AT ONCE. None of the lunar
    ones can be computed from a weekday rule, so they are TYPED with the gazetting authority
    named -- which is honest, and a wrong computed rule would not be."""
    for year in (2024, 2025, 2026):
        table = AE.national_holidays("gy", year)
        names = " ".join(table.values())
        for faith in ("Good Friday", "Phagwah", "Eid-ul-Adha", "Youman Nabi", "Diwali"):
            assert faith in names, f"Guyana's {faith} is missing in {year}"
        for day in table:
            assert day.year == year
        # the typed lunar rows must land in their own year and carry an authority
        for iso, _name in AE.LUNAR_HOLIDAYS["gy"][year]:
            assert date.fromisoformat(iso).year == year
    assert "Ministry of Home Affairs" in AE.LUNAR_AUTHORITY["gy"]
    assert "TYPED HERE, NOT COMPUTED" in AE.LUNAR_AUTHORITY["gy"]
    assert AE.LUNAR_HOLIDAYS["ve"][2025] == (), "Venezuela carries no lunar national holiday"
    # Diwali 2024 closes three of the four jurisdictions on the same day
    assert AE.shared_closures(2024, 3).get(date(2024, 10, 31)) == 3


def test_market_holidays_drop_weekend_closures_and_shared_ones_are_rare() -> None:
    """A holiday on a Saturday costs no session, and the four calendars coincide rarely -- which
    is what makes a single-jurisdiction closure a natural CONTROL rather than a regime."""
    for year in (2024, 2025, 2026):
        assert all(d.weekday() < 5 for d in AE.market_holidays(year))
        assert set(AE.market_holidays(year)) <= set(AE.province_holidays(year))
        shared4 = AE.shared_closures(year, 4)
        shared3 = AE.shared_closures(year, 3)
        assert 1 <= len(shared4) <= 6, f"{len(shared4)} four-country closures in {year}"
        assert len(shared3) >= len(shared4)
        assert len(shared3) < len(AE.province_holidays(year)) / 2, (
            "if most closures were shared there would be no single-country control left")
        assert date(year, 1, 1) in shared4, "New Year closes all four"


# ------------------------------------------------------------------------------ the mechanisms
def test_the_fpso_ramp_is_a_dated_published_supply_curve() -> None:
    """MECHANISM FUNCTION TWO, and the reason this pack exists. Zero to roughly 650,000 b/d of
    nameplate in six years, in dated steps that were announced years in advance."""
    assert AE.sanctioned_capacity_on(date(2018, 1, 1)) == 0, "Guyana produced nothing before 2019"
    assert AE.sanctioned_capacity_on(date(2019, 12, 19)) == 0, "the day before first oil"
    assert AE.sanctioned_capacity_on(date(2019, 12, 20)) == 120_000, "Liza Phase 1 starts"
    assert AE.sanctioned_capacity_on(date(2022, 6, 1)) == 340_000, "the second vessel added"
    assert AE.sanctioned_capacity_on(date(2024, 1, 1)) == 560_000, "the third vessel added"
    assert AE.sanctioned_capacity_on(date(2026, 1, 1)) == 810_000, "the fourth vessel added"
    # the FORWARD curve is a different object and is kept apart on purpose
    assert AE.scheduled_capacity_on(date(2028, 12, 31), "gy") == 1_310_000
    assert AE.scheduled_capacity_on(date(2026, 1, 1), "gy") == 810_000, (
        "a sanctioned-but-not-started vessel is a schedule, never supply")
    assert AE.sanctioned_capacity_on(date(2026, 1, 1), "sr") == 0, "Suriname has no first oil yet"
    assert AE.scheduled_capacity_on(date(2029, 1, 1), "sr") == 220_000, "GranMorgu is scheduled"
    steps = AE.ramp_steps("gy")
    assert len(steps) >= 6
    assert [s[0] for s in steps] == sorted(s[0] for s in steps), "the steps must be in date order"
    assert steps[0][2] == "Liza Destiny" and steps[0][1] == 120_000
    # every row carries a separate confidence label on its DATE
    for row in AE.fpso_rows():
        assert row["status"] in ("PRODUCING", "SANCTIONED_TARGETED")
        assert row["date_status"] in ("OPERATOR_ANNOUNCED", "PRESS_REPORTED", "TARGET_ANNOUNCED")
        assert row["jurisdiction"] in ("gy", "sr")
        assert int(row["nameplate_bpd"]) > 0
    assert "nameplate" in AE.DEBOTTLENECK_NOTE


def test_the_stabroek_fiscal_formula_is_published_arithmetic() -> None:
    """MECHANISM FUNCTION THREE. Cost recovery capped at 75% of revenue, profit oil split 50/50,
    a 2% royalty on gross -- a sovereign revenue function a cell can evaluate from the price."""
    got = AE.government_take(1000.0, 800.0)
    assert got["cost_oil"] == 750.0, "the 75% ceiling must BIND when costs exceed it"
    assert got["profit_oil"] == 250.0
    assert got["royalty"] == 20.0
    assert got["government"] == 145.0
    assert got["contractor"] == 855.0
    assert round(got["government"] + got["contractor"], 6) == 1000.0, "the split must exhaust it"
    assert got["government_share_of_revenue"] == pytest.approx(0.145)
    # below the ceiling the cost stack is recovered in full and the ceiling does not bind
    loose = AE.government_take(1000.0, 400.0)
    assert loose["cost_oil"] == 400.0 and loose["profit_oil"] == 600.0
    assert loose["government"] == 320.0
    # the 2023 MODEL agreement is a DIFFERENT contract and applies to new blocks only
    model = AE.government_take(1000.0, 800.0, "model_2023")
    assert model["cost_oil"] == 650.0
    assert model["royalty"] == 100.0
    assert model["government"] > got["government"], "the 2023 terms take more, as published"
    assert "NOT to Stabroek" in str(AE.PSA_TERMS["model_2023"]["note"])
    assert AE.government_take(0.0, 100.0)["government_share_of_revenue"] == 0.0


def test_the_sanctions_calendar_is_a_dated_published_supply_switch() -> None:
    """MECHANISM FUNCTION FOUR. Which US licensing regime was in force on a given day, built
    only from dated, published, lawful-to-read administrative acts."""
    assert AE.sanctions_state(date(2017, 1, 1)) == "PRE_SANCTIONS"
    assert AE.sanctions_state(date(2018, 6, 1)) == "FINANCIAL_SANCTIONS"
    assert AE.sanctions_state(date(2020, 6, 1)) == "PDVSA_BLOCKED"
    assert AE.sanctions_state(date(2023, 1, 1)) == "NAMED_COUNTERPARTY"
    assert AE.sanctions_state(date(2023, 10, 18)) == "GL44_OPEN", "the general licence day"
    assert AE.sanctions_state(date(2024, 4, 16)) == "GL44_OPEN", "the last day of the window"
    assert AE.sanctions_state(date(2024, 4, 17)) == "GL44A_WINDDOWN", "the day it lapsed"
    assert AE.sanctions_state(date(2025, 6, 1)) == "SPECIFIC_LICENCES"
    assert all(s in AE.SANCTIONS_REGIMES
               for s in {AE.sanctions_state(date(y, 6, 1)) for y in range(2016, 2027)})
    published = AE.licence_events("PUBLISHED_ACT")
    press = AE.licence_events("PRESS_REPORTED")
    assert len(published) >= 5 and len(press) >= 2
    assert len(published) + len(press) == len(AE.SANCTIONS_ACTS)
    # the 2025 acts are PRESS_REPORTED and must not masquerade as published citations
    for when, _act, _effect in press:
        assert when.year >= 2023


def test_the_opec_two_series_gap_and_the_parallel_premium() -> None:
    """The two OPEC series disagree and the gap is the observable; the parallel premium runs the
    same arithmetic for Trinidad and Venezuela for opposite reasons."""
    gap = AE.opec_gap(850.0, 780.0)
    assert gap["gap"] == 70.0
    assert gap["gap_share"] == pytest.approx(70.0 / 780.0)
    assert "ABOVE" in str(gap["reading"])
    assert "SECONDARY" in str(gap["rule"])
    assert AE.opec_gap(700.0, 780.0)["gap"] == -80.0
    assert "BELOW" in str(AE.opec_gap(700.0, 780.0)["reading"])
    assert "agree" in str(AE.opec_gap(780.0, 780.0)["reading"])
    assert AE.opec_gap(700.0, 0.0)["gap_share"] == 0.0
    assert AE.parallel_premium(6.78, 8.475) == pytest.approx(0.25)
    assert AE.parallel_premium(0.0, 5.0) == 0.0, "a zero official rate is not a premium"


def test_the_essequibo_series_keeps_its_two_confidence_labels_apart() -> None:
    """A scheduled court step is an anticipated date; a naval incident is not, and the pack must
    not let the second borrow the first's credibility."""
    assert len(AE.ESSEQUIBO_EVENTS) >= 6
    labels = {st for _i, _e, st in AE.ESSEQUIBO_EVENTS}
    assert labels == {"COURT_RECORD", "PRESS_REPORTED"}
    for iso, event, _st in AE.ESSEQUIBO_EVENTS:
        assert date.fromisoformat(iso).year >= 2018
        assert len(event) > 20
    isos = [i for i, _e, _s in AE.ESSEQUIBO_EVENTS]
    assert isos == sorted(isos), "the event series must be in date order"
    assert "2023-12-03" in isos, "the Venezuelan referendum is the largest dated escalation"
    assert "2023-12-14" in isos, "the Argyle Declaration is missing"
    # the stake has grown with the ramp: this is what makes the series non-stationary
    assert AE.sanctioned_capacity_on(date(2018, 3, 29), "gy") == 0
    assert AE.sanctioned_capacity_on(date(2023, 12, 3), "gy") == 560_000


def test_the_gas_and_gold_fact_tables_carry_their_status_labels() -> None:
    """Every physical claim in this province is labelled with how well it is known."""
    assert len(AE.TRINIDAD_GAS_FACTS) >= 5
    for label, what, status in AE.TRINIDAD_GAS_FACTS:
        assert label and len(what) > 40
        assert status in ("OFFICIAL", "PRESS_REPORTED")
    assert any(label == "dragon" for label, _w, _s in AE.TRINIDAD_GAS_FACTS)
    assert len(AE.GOLD_FACTS) >= 3
    statuses = {s for _l, _w, s in AE.GOLD_FACTS}
    assert "MEASUREMENT_WARNING" in statuses, (
        "the declared-versus-mirror gold gap is the measurement problem that makes every gold "
        "cell WEAK, and it must be labelled as a warning rather than as a fact")


def test_positioning_declares_the_absence_of_any_local_series() -> None:
    """No futures contract, no COT and no forward market exists for any of the four currencies."""
    unavailable = [r for r in AE.POSITIONING_SOURCES if not r["available"]]
    assert unavailable, "the local-positioning question is not answered anywhere in the pack"
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in unavailable)
    assert AE.COT_CURRENCY == ""
    for row in AE.POSITIONING_SOURCES:
        if row["available"]:
            assert row["root"] and row["fields"] and row["pit_warning"]


def test_the_era_table_says_what_a_pooled_study_would_be_measuring() -> None:
    """An era table earns its place through `invalidates`, and three of these eras are CURRENCY
    redenominations that mechanically break every Venezuelan nominal series."""
    assert len(AE.POLICY_ERAS) >= 8
    for era in AE.POLICY_ERAS:
        lo = date.fromisoformat(str(era["start"]))
        hi = date.fromisoformat(str(era["end"]))
        assert hi >= lo, f"era {era['name']!r} is reversed"
        assert era["invalidates"] and era["regime"] and era["markers"]
        assert era["status"] in ("SETTLED", "LIVE")
    redenominations = [e for e in AE.POLICY_ERAS if "redenomination" in str(e["name"])]
    assert len(redenominations) == 3, "2008, 2018 and 2021 each break the series"
    gl44 = [e for e in AE.POLICY_ERAS if "GENERAL LICENCE WINDOW" in str(e["name"])]
    assert gl44 and gl44[0]["start"] == "2023-10-18" and gl44[0]["end"] == "2024-04-16"
    assert "NATURAL EXPERIMENT" in str(gl44[0]["why_it_matters"])
