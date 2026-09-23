"""THE CENTRAL EUROPE AND BALKANS PACK: is it eight countries, or one template with eight flags?

WHAT THESE TESTS ARE FOR. `cee_balkans` is the widest pack in the department -- Czechia, Hungary,
Romania, Bulgaria, Croatia, Serbia, Slovakia and Slovenia, nine languages, three scripts and
eight monetary regimes -- and breadth is exactly what makes a regional pack decorative. The
failure mode is not being wrong, it is being GENERIC: eight countries flattened into one central
bank, one calendar, one vocabulary and a list of websites nobody searched. So these tests check
depth and specificity as hard as they check correctness, and every one of them can fail.

THE LOAD-BEARING CHECKS, and why each exists.

  `test_pack_resolves_and_check_pack_returns_no_problems` and
  `test_pack_depth_is_a_full_score_with_no_unmapped_layers` are the department's own gates, run
  against this pack rather than trusted: `research.countries.check_pack` and
  `libs.research.regional_parity.pack_depth` are what the desk measures every country with, and
  a pack that has not been put through them is a claim (L1.49).

  `test_the_framework_drops_nothing_on_construction` reads `coercion_notes`. The framework folds
  a pack's unknown keys into `notes` where a row has one and DROPS them where it does not; a
  dropped `falsifier` or `control` is a negative control deleted on import, silently. Zero notes
  is the only pass.

  `test_every_executable_instrument_is_real_and_is_not_an_equity` and its edge-target sibling
  read the broker's own registry. A symbol the box cannot quote is a cell that can never be
  compiled, and a single-name share CFD breaches the two-lane order of 2026-09-06 and spends the
  desk's shared family-wise error budget on the asset class the method suits least.

  `test_eurpln_is_never_executable_here` is the boundary between this pack and `pl`. Poland has
  its own pack; borrowing EURPLN as a NEIGHBOUR CONTROL inside one domain is legitimate and
  listing it as executable would be two packs hunting the same cross and paying the trial cost
  twice.

  `test_terminology_carries_real_native_script` is the one a translated pack fails. A crawler
  asking a Czech board for "interest rate" finds nothing; the word is `úroková sazba`. A query
  for Bulgaria in Latin script returns analyst commentary; `валутен борд` returns the BNB. So the
  test demands real Cyrillic, real Czech carons and real Hungarian double acutes, in the
  terminology AND in the queries a crawler would actually send.

  `test_holiday_rules_reproduce_dates_a_human_can_check` pins two dates verifiable without any of
  this code: Czech statehood day on 2026-10-28 and Serbian Orthodox Christmas on 2026-01-07. Both
  are DERIVED -- the second from a Julian computus shifted thirteen days -- so the test checks
  arithmetic rather than somebody's copy-paste, and the 2025 Easter coincidence pins the placebo.

EVERYTHING IS READ FROM THE PACK MODULE'S OWN CONSTANTS where the subject is the country, and
from the framework's typed object only where the subject is the framework. The split is
deliberate: testing the coerced object for content would measure `country_lab`'s in-flight
coercion rather than central Europe.
"""
from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Mapping
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CODE = "cee_balkans"

#: The twenty-one fields every country pack owes, in the framework's order.
PACK_FIELDS: tuple[str, ...] = (
    "code", "name", "region_command", "currency", "executable_instruments", "central_bank",
    "fixing_conventions", "settlement_conventions", "exchanges", "holidays_rule",
    "fiscal_year_end", "positioning_sources", "native_languages", "terminology", "source_classes",
    "datasets", "actors", "domains", "custom_miners", "transmission_edges_seed", "policy_eras")

#: The eleven things a pack must be able to say about an actor.
ACTOR_FIELDS: tuple[str, ...] = (
    "holds", "forced_to", "when", "information", "constraints", "instruments", "counterparties",
    "observables", "impact", "persistence", "falsifier")

#: The ten source layers of the principal's depth rule (2026-09-17).
LAYERS: tuple[str, ...] = ("official", "institutional", "academic", "practitioner",
                           "retail_ecology", "app_ecosystem", "media", "archive",
                           "physical_economy", "source_graph")

#: The broker's own asset classes for single names. No pack may name one as executable.
EQUITY_CLASSES: frozenset[str] = frozenset({
    "equities", "equity", "shares", "share", "stock", "stocks", "share cfd", "share cfds",
    "us shares"})

#: The depth bar of `libs.research.regional_parity.DEPTH_TARGETS`, restated so a silent
#: loosening of the framework's targets cannot quietly lower this pack's floor.
MIN_ACTORS, MIN_DOMAINS, MIN_EDGES = 12, 10, 8
MIN_TERMS, MIN_DATASETS, MIN_ERAS, MIN_INSTRUMENTS = 40, 8, 4, 6

#: The eight jurisdictions this pack owes a calendar and an actor to.
JURISDICTION_NAMES: tuple[str, ...] = ("CZECHIA", "HUNGARY", "ROMANIA", "BULGARIA", "CROATIA",
                                       "SERBIA", "SLOVAKIA", "SLOVENIA", "THE REGION")

#: The five miners this pack's own clocks need. Both registrations must name the same five.
MINER_NAMES: tuple[str, ...] = ("cnb_mnb_decision_windows", "czk_floor_regime_break",
                                "mnb_quick_tender_era", "orthodox_vs_western_easter",
                                "transmission_seeds")

_UNIVERSE_JSON = _DESK / "data" / "universe" / "universe.json"


# --------------------------------------------------------------------------- fixtures/helpers
def _get(obj: Any, field: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(field, default)
    return getattr(obj, field, default)


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (tuple, list, dict, set, frozenset)):
        return len(value) > 0
    return True


def _has_cyrillic(text: str) -> bool:
    return any("Ѐ" <= ch <= "ӿ" for ch in text)


#: Characters no ASCII-folded glossary can produce. `ě š č ř ž ů` are Czech, `ő ű` Hungarian,
#: `ș ț â` Romanian, `ć đ` Croatian and Serbian Latin, `ľ ŕ ä` Slovak.
CZECH_MARKS = "ěščřžýáíéůú"
HUNGARIAN_MARKS = "őűáéíóöüú"


@pytest.fixture(scope="module")
def universe() -> dict[str, dict[str, Any]]:
    """The broker registry, read directly rather than through the framework's cached accessor.

    An unreadable registry SKIPS: an absent input is UNMEASURED, never a clean pass (L1.28a).
    """
    if not _UNIVERSE_JSON.exists():
        pytest.skip(f"{_UNIVERSE_JSON} is absent -- symbol validation is UNMEASURED, not passed")
    raw = json.loads(_UNIVERSE_JSON.read_text(encoding="utf-8"))
    rows = {str(k): dict(v) for k, v in raw.items() if isinstance(v, Mapping)}
    if not rows:
        pytest.skip("the broker registry is empty -- symbol validation is UNMEASURED")
    return rows


def _asset_class(universe: Mapping[str, Any], symbol: str) -> str:
    row = universe.get(str(symbol))
    if row is None:
        return "ABSENT"
    raw = str(row.get("asset_class") or "").lower().replace("_", " ")
    return " ".join(raw.split()) or "UNCLASSIFIED"


@pytest.fixture(scope="module")
def mod() -> Any:
    """The pack module itself: the country's own constants, which are the subject here."""
    return importlib.import_module(f"countries.{CODE}.pack")


@pytest.fixture(scope="module")
def built(mod: Any) -> Any:
    """The pack as the framework builds it, which is what every miner downstream sees."""
    return mod.pack()


# --------------------------------------------------------------------------- the department gates
def test_pack_resolves_and_check_pack_returns_no_problems(mod: Any) -> None:
    """`research.countries.check_pack` is the department's own gate; an empty list is the pass."""
    # Imported dynamically: `research.countries` is a desk package outside the checker's
    # file set, and a static import would need an ignore that reads as unused whenever the
    # pack module is checked alongside this file. The department gate is the same either way.
    countries = importlib.import_module("research.countries")

    problems = countries.check_pack(mod.as_dict())
    assert problems == [], f"{CODE}: check_pack found {len(problems)} problems: {problems[:8]}"


def test_the_pack_builds_and_carries_all_twenty_one_fields(built: Any, mod: Any) -> None:
    """Every one of the twenty-one framework fields is non-empty and the command is `europe`."""
    assert built is not None
    for field in PACK_FIELDS:
        assert _nonempty(_get(built, field)), f"{CODE}: pack field {field!r} is empty"
    assert str(_get(built, "region_command")) == "europe", (
        "a central European pack files under the europe command or it is funded by nobody")
    assert str(_get(built, "code")) == CODE, "the framework's canonical token must be the code"
    assert _nonempty(mod.CUSTOM_MINERS), "no named specialist miners"


def test_pack_depth_is_a_full_score_with_no_unmapped_layers(built: Any) -> None:
    """`regional_parity.pack_depth` must score 1.0 with every layer declared and none untagged.

    The score is the mean of eight capped ratios against DEPTH_TARGETS. Scoring 1.0 is not the
    same as being deep -- it is the floor the principal's parity rule sets -- so the counts are
    asserted individually as well, and each one is aimed at the department's reference pack
    rather than at the bar.
    """
    from libs.research import regional_parity as RP

    row = RP.pack_depth(built, CODE).as_row()
    assert row["score"] == 1.0, f"depth score {row['score']}; targets {RP.DEPTH_TARGETS}"
    assert row["layers_unmapped"] == 0, "a layer nobody mapped is not a covered layer"
    assert row["layers_declared"] == len(LAYERS), "all ten layers must carry a source or a reason"
    assert row["untagged_sources"] == 0, "a source with no layer is work, not coverage"
    assert not row["fatal"], f"validate_pack fatal problems: {row['fatal']}"
    assert row["actors"] >= MIN_ACTORS and row["domains"] >= MIN_DOMAINS
    assert row["edges"] >= MIN_EDGES and row["terms"] >= MIN_TERMS
    assert row["datasets"] >= MIN_DATASETS and row["eras"] >= MIN_ERAS
    assert row["instruments"] >= MIN_INSTRUMENTS
    assert row["languages"] >= 8, "eight jurisdictions cannot be mined in fewer than eight tongues"


def test_the_framework_drops_nothing_on_construction(built: Any) -> None:
    """Zero coercion notes. A dropped key is a negative control deleted on import, silently."""
    notes = tuple(getattr(built, "coercion_notes", ()) or ())
    assert notes == (), f"{len(notes)} coercion notes, first: {notes[:3]}"


def test_validate_pack_reports_no_fatal_problems(built: Any) -> None:
    """The framework's own validator must find nothing that means DO NOT RUN THIS PACK."""
    from libs.research import country_lab as CL

    problems = CL.validate_pack(built)
    assert CL.fatal_problems(problems) == [], f"fatal: {CL.fatal_problems(problems)[:5]}"


# --------------------------------------------------------------------------- instruments
def test_every_executable_instrument_is_real_and_is_not_an_equity(
        mod: Any, universe: dict[str, dict[str, Any]]) -> None:
    """Every executable symbol exists in the broker registry and none is a single-name equity."""
    execs = tuple(mod.EXECUTABLE_INSTRUMENTS)
    assert len(execs) >= MIN_INSTRUMENTS, f"only {len(execs)} executable instruments"
    assert len(set(execs)) == len(execs), "duplicate executable instruments"
    for symbol in execs:
        klass = _asset_class(universe, symbol)
        assert klass != "ABSENT", (
            f"{symbol} is not in the broker universe; it belongs in TRANSMISSION_TARGETS, named")
        assert klass not in EQUITY_CLASSES, (
            f"{symbol} is a single-name equity ({klass}); the two-lane order forbids hunting one")
    hu_legs = {s for s in execs if s.endswith("HUF")}
    cz_legs = {s for s in execs if s.endswith("CZK")}
    assert len(hu_legs) >= 4 and len(cz_legs) >= 2, (
        "the HUF and CZK crosses are this region's own executable ground and must carry the "
        f"weight; got {sorted(hu_legs)} and {sorted(cz_legs)}")


def test_eurpln_is_never_executable_here(mod: Any) -> None:
    """Poland has its own pack. EURPLN is a NEIGHBOUR CONTROL here and nothing else.

    Two packs hunting the same cross pay the desk's shared multiple-testing cost twice for one
    hypothesis, so the boundary is a test rather than a convention. It must still appear as a
    control, because "is this the forint or is it CEE beta?" cannot be asked without it.
    """
    assert "EURPLN" not in set(mod.EXECUTABLE_INSTRUMENTS), (
        "EURPLN belongs to the `pl` pack; naming it executable here duplicates Poland")
    controls = " ".join(c for d in mod.DOMAINS for c in d["controls"])
    assert "EURPLN" in controls, (
        "EURPLN must still be named as the neighbour control, or the pack cannot separate a "
        "forint effect from CEE beta")


def test_transmission_seeds_name_symbols_the_box_can_actually_trade(
        mod: Any, universe: dict[str, dict[str, Any]]) -> None:
    """At least eight seeds, every target real, never an equity, each with its own control."""
    edges = tuple(mod.TRANSMISSION_EDGES_SEED)
    assert len(edges) >= MIN_EDGES, f"{len(edges)} transmission seeds < {MIN_EDGES}"
    ids = [str(e["id"]) for e in edges]
    assert len(set(ids)) == len(ids), "an edge id is declared twice"
    for row in edges:
        eid = row["id"]
        assert row["targets"], f"{eid}: names no executable target"
        assert row["target"] == row["targets"][0], (
            f"{eid}: the primary target must be copied into `target` so the framework's "
            f"one-asset TransmissionSeed is useful after coercion")
        for symbol in row["targets"]:
            klass = _asset_class(universe, symbol)
            assert klass != "ABSENT", f"{eid}: target {symbol} is not in the universe"
            assert klass not in EQUITY_CLASSES, f"{eid}: target {symbol} is an equity"
        for field in ("source", "mechanism", "sign", "horizon", "lag_days", "control",
                      "falsifier", "evidence"):
            assert _nonempty(row.get(field)), f"{eid}: edge field {field!r} is empty"
        assert row["evidence"] in {"HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED"}


def test_absent_instruments_are_named_rather_than_dropped(
        mod: Any, universe: dict[str, dict[str, Any]]) -> None:
    """The leu, the lev, the kuna, the dinar and the CEE indices are NAMED, never dropped."""
    targets = tuple(mod.TRANSMISSION_TARGETS)
    assert len(targets) >= 6, f"only {len(targets)} named transmission targets"
    for row in targets:
        for field in ("name", "venue", "why", "proxies"):
            assert _nonempty(row.get(field)), f"transmission target missing {field!r}"
        assert _asset_class(universe, row["name"]) == "ABSENT", (
            f"{row['name']!r} is in the broker registry and should be executable, not a target")
        for proxy in row["proxies"]:
            assert _asset_class(universe, proxy) != "ABSENT", (
                f"{row['name']!r} routes through {proxy}, which the box cannot quote either")


# --------------------------------------------------------------------------- actors + domains
def test_every_actor_carries_all_eleven_fields_and_names_its_country(mod: Any) -> None:
    """Twelve actors minimum, all eleven fields non-empty, and each one says whose law binds it.

    Eight jurisdictions in one pack is exactly how a region becomes a blur. An actor whose row
    cannot be read without already knowing which state forces it is an anecdote, and an actor
    with no FALSIFIER is a story.
    """
    actors = tuple(mod.ACTORS)
    assert len(actors) >= MIN_ACTORS, f"{len(actors)} actors < {MIN_ACTORS}"
    names = [str(a["name"]) for a in actors]
    assert len(set(names)) == len(names), "an actor is declared twice"
    for row in actors:
        name = row["name"]
        for field in ACTOR_FIELDS:
            assert _nonempty(row.get(field)), f"{name}: actor field {field!r} is empty"
        assert len(str(row["falsifier"])) >= 60, (
            f"{name}: the falsifier is too short to be one -- it must name the measurement that "
            f"would kill the claim")
        assert any(j in name.upper() for j in JURISDICTION_NAMES), (
            f"{name}: names no country; in an eight-jurisdiction pack that is unreadable")
    covered = {j for j in JURISDICTION_NAMES for n in names if j in n.upper()}
    assert len(covered) >= 7, f"only {sorted(covered)} carry an actor of their own"


def test_every_domain_names_its_negative_controls(mod: Any,
                                                  universe: dict[str, dict[str, Any]]) -> None:
    """Ten domains minimum, each with objects, conditions, instruments and three controls."""
    domains = tuple(mod.DOMAINS)
    assert len(domains) >= MIN_DOMAINS, f"{len(domains)} domains < {MIN_DOMAINS}"
    ids = [str(d["id"]) for d in domains]
    assert len(set(ids)) == len(ids), "a domain id is declared twice"
    for row in domains:
        did = row["id"]
        assert did.startswith("CEE-"), f"{did}: a domain id must name the region and the country"
        for field in ("title", "objects", "conditions", "instruments", "controls"):
            assert _nonempty(row.get(field)), f"{did}: domain field {field!r} is empty"
        assert len(row["controls"]) >= 3, (
            f"{did}: {len(row['controls'])} controls; one control is a gesture")
        for symbol in row["instruments"]:
            assert _asset_class(universe, symbol) not in EQUITY_CLASSES, (
                f"{did}: instrument {symbol} is a single-name equity")


def test_policy_eras_are_dated_ordered_and_one_is_open(mod: Any) -> None:
    """Every era parses, they do not overlap, and exactly the present one is OPEN."""
    eras = tuple(mod.POLICY_ERAS)
    assert len(eras) >= MIN_ERAS, f"{len(eras)} policy eras < {MIN_ERAS}"
    last_end: date | None = None
    for row in eras:
        start, end = date.fromisoformat(row["start"]), date.fromisoformat(row["end"])
        assert end >= start, f"{row['name']}: era ends before it starts"
        if last_end is not None:
            assert start > last_end, f"{row['name']}: overlaps the era before it"
        last_end = end
        for field in ("regime", "markers", "why_it_matters", "status"):
            assert _nonempty(row.get(field)), f"{row['name']}: era field {field!r} is empty"
    assert sum(1 for e in eras if e["status"] == "OPEN") == 1, (
        "exactly one era must be OPEN; zero claims the desk knows the present regime ended")


def test_every_dataset_carries_its_pit_answer(mod: Any) -> None:
    """A dataset whose vintage cannot be reconstructed can only produce NOT_PIT_SAFE cells."""
    datasets = tuple(mod.DATASETS)
    assert len(datasets) >= MIN_DATASETS, f"{len(datasets)} datasets < {MIN_DATASETS}"
    names = [d["name"] for d in datasets]
    assert len(set(names)) == len(names), "a dataset is declared twice"
    for row in datasets:
        for field in ("source", "coverage", "frequency", "revisions", "licence", "history_from",
                      "assets", "mechanism_families", "how_to_fetch"):
            assert _nonempty(row.get(field)), f"{row['name']}: dataset field {field!r} is empty"
        assert float(row["publication_lag_days"]) >= 0
        assert isinstance(row["pit_feasible"], bool)
    assert any(not d["pit_feasible"] for d in datasets), (
        "every dataset PIT-feasible is a claim, not a measurement: the CHF loan stock is a "
        "quarter stale by construction and the pack must say so")


# --------------------------------------------------------------------------- source layers
def test_every_source_layer_is_named_or_declared_absent(mod: Any) -> None:
    """Ten layers, each with a source or a stated reason. A blank is never an answer."""
    assert tuple(mod.SOURCE_LAYERS) == LAYERS, "the layer vocabulary has drifted"
    coverage = mod.source_layer_coverage()
    counts = coverage["layer_counts"]
    assert set(counts) == set(LAYERS), "coverage does not cover the ten layers"
    for layer, n in counts.items():
        assert n >= 1, f"{layer}: no source and the pack declares no reason for having none"
    assert coverage["unexplained_missing"] == [], coverage["unexplained_missing"]
    assert coverage["machine_use_forbidden"], (
        "every source machine-readable is not true of any European media layer; a pack that "
        "found none did not read the terms")
    assert coverage["low_weight_kept"], (
        "nothing carried at low weight means nothing was kept rather than cut")


def test_every_source_carries_three_independent_labels(mod: Any) -> None:
    """Access, credibility and predictive state are three axes and are labelled separately."""
    sources = tuple(mod.SOURCE_CLASSES)
    assert len(sources) >= 10, f"{len(sources)} source classes"
    ids = [s["id"] for s in sources]
    assert len(set(ids)) == len(ids), "a source id is declared twice"
    for row in sources:
        sid = row["id"]
        assert row["layer"] in LAYERS, f"{sid}: layer {row['layer']!r} unknown"
        assert row["access_label"] in mod.ACCESS_LABELS, f"{sid}: bad access_label"
        assert row["credibility"] in mod.CREDIBILITY_LABELS, f"{sid}: bad credibility"
        assert row["predictive_state"] in mod.PREDICTIVE_STATES, f"{sid}: bad predictive_state"
        assert row["roots"], f"{sid}: no concrete roots"
        assert len(row["queries"]) >= 2, f"{sid}: a source with no way in is a bookmark"
        assert isinstance(row["machine_use_allowed"], bool)
        assert _nonempty(row.get("notes")), f"{sid}: no note saying why it is here"
    assert any(s["credibility"] == "FRINGE" for s in sources), (
        "no FRINGE source means the low-credibility ground was never searched; fringe PUBLIC "
        "material is kept at low weight, never dropped")
    assert any(s["predictive_state"] == "NARRATIVE_FEATURE" for s in sources), (
        "nothing labelled a narrative feature means attention data is being read as forecast data")
    for row in sources:
        if not row["machine_use_allowed"]:
            assert "NEVER SCRAPED" in str(row["notes"]).upper(), (
                f"{row['id']}: registered machine-forbidden without saying so in the note")


def test_source_class_builder_refuses_an_unknown_label(mod: Any) -> None:
    """The builder validates its own vocabulary, so a typo cannot become a silent layer."""
    for bad in ({"layer": "gossip"}, {"access_label": "SEMI_PUBLIC"},
                {"credibility": "PROBABLY"}, {"predictive_state": "MAYBE"}):
        kwargs: dict[str, Any] = {"layer": "official", "roots": ("https://example.invalid",),
                                  "queries": ("x",), "languages": ("cs",),
                                  "access_label": "PUBLIC", "credibility": "RELIABLE",
                                  "predictive_state": "UNTESTED", "licence": "free"}
        kwargs.update(bad)
        with pytest.raises(ValueError):
            mod.source_class("probe", "probe", **kwargs)
    with pytest.raises(ValueError):
        mod.absent_layer("gossip", "no reason")


# --------------------------------------------------------------------------- language
def test_terminology_carries_real_native_script(mod: Any) -> None:
    """Cyrillic, Czech carons and Hungarian double acutes, in the terminology itself.

    An accent-folded glossary cannot match the source it exists to match, and a Bulgarian or
    Serbian query written in Latin script returns a different internet from the one the BNB and
    the NBS publish on. Both alphabets are demanded, and specific phrases are pinned so that a
    later edit cannot quietly translate the pack into English.
    """
    terminology = dict(mod.TERMINOLOGY)
    assert len(terminology) >= 10, f"{len(terminology)} terminology groups"
    flat = {term for terms in terminology.values() for term in terms}
    assert len(flat) >= MIN_TERMS, f"only {len(flat)} distinct terms"

    probes = ("úroková sazba", "dvoutýdenní repo sazba", "kurzový závazek", "inflace",
              "alapkamat", "egynapos betéti gyorstender", "infláció", "forint",
              "rata dobânzii de politică monetară", "leu", "inflație",
              "основен лихвен процент", "валутен борд", "инфлация",
              "kamatna stopa", "динар", "инфлација",
              "úroková sadzba", "obrestna mera")
    missing = [p for p in probes if p not in flat]
    assert not missing, f"native vocabulary missing {missing}"

    cyrillic = {t for t in flat if _has_cyrillic(t)}
    assert len(cyrillic) >= 20, (
        f"{len(cyrillic)} Cyrillic terms; Bulgarian and Serbian cannot be searched in Latin")
    czech = {t for t in flat if any(ch in CZECH_MARKS for ch in t)}
    hungarian = {t for t in flat if any(ch in HUNGARIAN_MARKS for ch in t)}
    assert len(czech) >= 12, f"{len(czech)} terms carry Czech diacritics"
    assert len(hungarian) >= 12, f"{len(hungarian)} terms carry Hungarian diacritics"
    assert any("ő" in t or "ű" in t for t in flat), (
        "no Hungarian double acute anywhere; `pihenőnap` and `betéti` are not the same word "
        "without it")

    langs = tuple(mod.NATIVE_LANGUAGES)
    for lang in ("cs", "hu", "ro", "bg", "hr", "sr", "sk", "sl"):
        assert lang in langs, f"{lang} is not declared a native language of this pack"


def test_queries_are_written_in_the_source_languages(mod: Any) -> None:
    """The crawler's own strings are native too, and at least one layer's are Cyrillic.

    Terminology a miner never sends is decoration. These are the strings that actually reach a
    Bulgarian or Czech search box, so the script test is applied to them directly and per layer.
    """
    per_layer = mod.layer_terms()
    assert set(per_layer) == set(LAYERS)
    for layer, queries in per_layer.items():
        assert len(queries) >= 2, f"{layer}: {len(queries)} queries"
    all_queries = [q for qs in per_layer.values() for q in qs]
    assert len(all_queries) >= 60, f"only {len(all_queries)} queries across ten layers"

    cyrillic_layers = [ly for ly, qs in per_layer.items() if any(_has_cyrillic(q) for q in qs)]
    assert len(cyrillic_layers) >= 3, (
        f"only {cyrillic_layers} carry a Cyrillic query; Bulgaria and Serbia are not searchable "
        f"from a Latin keyboard")
    czech_layers = [ly for ly, qs in per_layer.items()
                    if any(any(ch in CZECH_MARKS for ch in q) for q in qs)]
    hungarian_layers = [ly for ly, qs in per_layer.items()
                        if any(any(ch in HUNGARIAN_MARKS for ch in q) for q in qs)]
    assert len(czech_layers) >= 3 and len(hungarian_layers) >= 3, (
        f"czech in {czech_layers}, hungarian in {hungarian_layers}")


# --------------------------------------------------------------------------- holidays
def test_holiday_rules_reproduce_dates_a_human_can_check(mod: Any) -> None:
    """Two dates verifiable without any of this code, both DERIVED rather than typed.

    Czech statehood day is 28 October and 2026-10-28 is a Wednesday, so it costs the Prague
    market a session. Serbian Orthodox Christmas is 7 January by the Julian calendar, which lands
    on 2026-01-07 and on no other market's calendar in this pack.
    """
    table = mod.market_holidays(2026)
    cz_day, rs_day = date(2026, 10, 28), date(2026, 1, 7)
    assert cz_day in table and "cz:" in table[cz_day], table.get(cz_day)
    assert "československého" in table[cz_day], (
        "the Czech statehood day must be named in Czech, with its diacritics")
    assert rs_day in table and "rs:" in table[rs_day], table.get(rs_day)
    assert _has_cyrillic(table[rs_day]), "Serbian Orthodox Christmas must be named in Cyrillic"
    assert cz_day.weekday() < 5 and rs_day.weekday() < 5, (
        "both pinned dates must be weekdays, or they cost the tape nothing")

    assert mod.national_holidays("cz", 2026).get(cz_day) is not None
    assert rs_day not in mod.national_holidays("cz", 2026), (
        "Prague does not close for the Orthodox Christmas; the asymmetry is the research object")
    assert cz_day not in mod.national_holidays("rs", 2026)


def test_the_two_easters_are_computed_and_2025_is_the_placebo_year(mod: Any) -> None:
    """The Gregorian and Julian computations, and the coincidence that makes 2025 the placebo."""
    assert mod.western_easter(2024) == date(2024, 3, 31)
    assert mod.western_easter(2025) == date(2025, 4, 20)
    assert mod.western_easter(2026) == date(2026, 4, 5)
    assert mod.orthodox_easter(2024) == date(2024, 5, 5)
    assert mod.orthodox_easter(2025) == date(2025, 4, 20)
    assert mod.orthodox_easter(2026) == date(2026, 4, 12)
    assert mod.easter_divergence_days(2024) == 35
    assert mod.easter_divergence_days(2025) == 0, (
        "2025 is the coinciding year and therefore the natural placebo for CEE-XX-B")
    assert mod.easter_divergence_days(2026) == 7
    for code in ("ro", "bg", "rs"):
        assert mod.easter_for(code, 2026) == date(2026, 4, 12)
    for code in ("cz", "hu", "hr", "sk", "si"):
        assert mod.easter_for(code, 2026) == date(2026, 4, 5)
    with pytest.raises(ValueError):
        mod.easter_for("de", 2026)


def test_the_calendar_asymmetry_is_real_in_both_directions(mod: Any) -> None:
    """Both halves of the divergence exist as weekdays, and the Easter half shrinks in 2025."""
    east26, west26 = mod.orthodox_only_days(2026), mod.western_only_days(2026)
    assert east26 and west26, "an eight-calendar region with no asymmetry cannot be right"
    for day in list(east26) + list(west26):
        assert day.weekday() < 5, f"{day} is a weekend and is not an asymmetric session"
    assert set(east26) & set(west26) == set(), "a day cannot be in both halves"
    assert date(2026, 4, 13) in east26, "Orthodox Easter Monday 2026 is a divergence weekday"
    assert date(2026, 4, 6) in west26, "Western Easter Monday 2026 is the mirror image"
    assert len(mod.orthodox_only_days(2025)) < len(east26), (
        "the coinciding year must lose the Easter half of the sample; that is the placebo")


def test_the_holidays_rule_carries_a_derivation_and_three_resolved_years(mod: Any) -> None:
    """A table with no rule cannot be extended; a rule with no table cannot be checked."""
    rule = mod.HOLIDAYS_RULE
    for field in ("calendar", "rule", "function", "table", "asymmetries", "status", "verified",
                  "authority", "weekend"):
        assert _nonempty(rule.get(field)), f"holidays_rule field {field!r} is empty"
    assert rule["status"] == "DERIVED_FROM_RULE"
    assert rule["function"].startswith(f"countries.{CODE}.pack:")
    for year in (2024, 2025, 2026):
        table = rule["table"][year]
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
    assert set(mod.JURISDICTIONS) == set(mod.FIXED_HOLIDAYS) == set(mod.MOVING_FEASTS)
    for code in mod.JURISDICTIONS:
        assert mod.national_holidays(code, 2026), f"{code}: an empty national calendar"
    with pytest.raises(ValueError):
        mod.national_holidays("pl", 2026)


def test_only_bulgaria_and_serbia_substitute_a_weekend_holiday(mod: Any) -> None:
    """The substitution rule is the law's, not a convenience, and it exempts the Easter block.

    Two cases a human can check. Bulgarian Liberation Day 2024-03-03 was a Sunday and Monday
    4 March was a non-working day in Bulgaria; Serbian Statehood Day 2025-02-15/16 fell on a
    Saturday and Sunday and 17-18 February were non-working in Serbia. Czechia and Hungary have
    no substitution in law, so 1 May 2027 and 15 March 2025 -- both Saturdays -- cost their
    markets nothing. And substituting the Orthodox Easter Saturday and Sunday would invent two
    closures a year that no Bulgarian or Serbian market ever took, which is why the block is
    exempt by name in both statutes.
    """
    bg = mod.national_holidays("bg", 2024)
    assert date(2024, 3, 3).weekday() == 6 and date(2024, 3, 3) in bg
    assert "(substituted)" in bg.get(date(2024, 3, 4), ""), (
        "Bulgaria moves a weekend holiday to the next working day; 4 March 2024 was one")
    rs = mod.national_holidays("rs", 2025)
    assert date(2025, 2, 15).weekday() == 5 and date(2025, 2, 16) in rs
    for day in (date(2025, 2, 17), date(2025, 2, 18)):
        assert "(substituted)" in rs.get(day, ""), (
            f"Serbia substitutes both Statehood days; {day} was one")
    assert date(2027, 5, 1).weekday() == 5
    assert date(2027, 5, 3) not in mod.national_holidays("cz", 2027), (
        "Czechia has no weekend substitution in law and must not invent one")
    assert date(2025, 3, 15).weekday() == 5
    assert date(2025, 3, 17) not in mod.national_holidays("hu", 2025), (
        "Hungary rearranges rest days by decree and does not substitute weekend holidays")
    for year in (2024, 2025, 2026):
        easter = mod.orthodox_easter(year)
        for code in ("bg", "rs"):
            table = mod.national_holidays(code, year)
            for offset in (-1, 0):
                day = easter + timedelta(days=offset)
                assert "(substituted)" not in str(table.get(day, "")), (
                    f"{code} {year}: the Easter block was substituted, which the law exempts")


# --------------------------------------------------------------------------- miners
def test_all_five_custom_miners_resolve_through_the_framework(built: Any, mod: Any) -> None:
    """`load_custom_miners` must resolve every entry; an unresolved miner never runs.

    A custom miner that silently never runs is a country the desk believes it is mining and is
    not (III.16). Both registrations -- the pack's `CUSTOM_MINERS` entries and the miners
    module's own `MINERS` map -- must name the same five functions, or one of them is fiction.
    """
    from libs.research import country_lab as CL

    resolved, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution problems: {problems}"
    assert sorted(resolved) == sorted(f"custom:{n}" for n in MINER_NAMES), sorted(resolved)

    miners_module = importlib.import_module(f"countries.{CODE}.miners")
    assert sorted(miners_module.MINERS) == sorted(MINER_NAMES)
    for name, fn in miners_module.MINERS.items():
        assert callable(fn), f"{name} is not callable"
        assert resolved[f"custom:{name}"] is fn, (
            f"{name}: the pack's entry and the module's map resolve to different objects")


def test_every_custom_miner_declares_itself_unwired_and_names_real_domains(mod: Any) -> None:
    """"Built" is not a status (III.16): a miner with no clock must say NOT WIRED."""
    known = {str(d["id"]) for d in mod.DOMAINS}
    miners = tuple(mod.CUSTOM_MINERS)
    assert len(miners) == len(MINER_NAMES), f"{len(miners)} declared miners"
    for row in miners:
        assert row["entry"].startswith(f"countries.{CODE}.miners:"), row["entry"]
        assert row["entry"].split(":")[1] in MINER_NAMES, row["entry"]
        assert row["domain_ids"], f"{row['name']}: names no domain"
        for did in row["domain_ids"]:
            assert did in known, f"{row['name']}: names unknown domain {did!r}"
        assert "NOT WIRED" in str(row.get("notes", "")), (
            f"{row['name']}: a miner that does not declare itself unwired claims a clock it "
            f"does not have")
        assert row["wired"] is False
    for miner, ids in mod.MINER_DOMAINS.items():
        for did in ids:
            assert did in known, f"MINER_DOMAINS[{miner}]: unknown domain {did!r}"


def test_the_miner_module_declares_the_regime_dates_it_measures(mod: Any) -> None:
    """The floor and quick-tender bounds live in the miners module as DECLARED dates.

    A regime break found by an algorithm is a change point; a regime break with a published
    decision date is a fact. Both of this pack's breaks are the second kind, so the dates are
    constants a human can check rather than parameters a search produced.
    """
    miners_module = importlib.import_module(f"countries.{CODE}.miners")
    declared = {"FLOOR_START": date(2013, 11, 7), "FLOOR_END": date(2017, 4, 6),
                "QUICK_TENDER_START": date(2022, 10, 14),
                "QUICK_TENDER_END": date(2023, 9, 26)}
    for name, expected in declared.items():
        assert getattr(miners_module, name) == expected, f"{name} is not the published date"
    era_bounds = {(e["start"], e["end"]) for e in mod.POLICY_ERAS}
    assert any(start == "2013-11-07" for start, _ in era_bounds), (
        "the floor's start must open a policy era, or a statistic can be pooled across it")
    assert any(end == "2017-04-05" for _, end in era_bounds), (
        "the floor's last day must close a policy era")


# --------------------------------------------------------------------------- hygiene
#: Every field in this pack whose value is a SEQUENCE of phrases, never a bare string.
SEQUENCE_FIELDS: tuple[str, ...] = (
    "forced_to", "information", "constraints", "instruments", "counterparties", "observables",
    "objects", "conditions", "controls", "assets", "mechanism_families", "roots", "languages",
    "queries", "targets", "domain_ids", "markers", "proxies", "needs")


def test_no_sequence_field_was_exploded_into_characters(mod: Any) -> None:
    """A one-element tuple written without its trailing comma is a STRING, and it is silent.

    `constraints=("a board mandate")` is not a tuple. `tuple(...)` explodes it into one entry per
    CHARACTER, every length check passes, the pack imports, the framework coerces it, and the
    actor's constraint is gone. This test is the guard: a one-character element, or a field that
    is a string at all, is a missing comma until proven otherwise.
    """
    rows: list[tuple[str, Any]] = []
    rows += [(f"actor {a['name']}", a) for a in mod.ACTORS]
    rows += [(f"domain {d['id']}", d) for d in mod.DOMAINS]
    rows += [(f"edge {e['id']}", e) for e in mod.TRANSMISSION_EDGES_SEED]
    rows += [(f"dataset {d['name']}", d) for d in mod.DATASETS]
    rows += [(f"source {s['id']}", s) for s in mod.SOURCE_CLASSES]
    rows += [(f"miner {m['name']}", m) for m in mod.CUSTOM_MINERS]
    rows += [(f"era {e['name']}", e) for e in mod.POLICY_ERAS]
    rows += [(f"target {t['name']}", t) for t in mod.TRANSMISSION_TARGETS]
    for label, row in rows:
        for field in SEQUENCE_FIELDS:
            if field not in row:
                continue
            value = row[field]
            assert not isinstance(value, str), (
                f"{label}: {field!r} is a STRING, not a sequence -- a one-element tuple is "
                f"missing its trailing comma")
            for item in value:
                assert isinstance(item, str) and len(item) > 1, (
                    f"{label}: {field!r} contains {item!r}, a single character")
    for name in ("EXECUTABLE_INSTRUMENTS", "NATIVE_LANGUAGES", "SOURCE_LAYERS", "JURISDICTIONS"):
        value = getattr(mod, name)
        assert not isinstance(value, str), f"{name} is a string, not a tuple"
        assert all(len(v) > 1 for v in value), f"{name} contains a single character"


def test_the_pack_writes_nothing_and_reads_no_state(mod: Any, tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    """A pack is DATA. Building it from an empty working directory must produce no file.

    Country packs are imported by the compiler, the parity fence and the global OS on every
    pass; one that writes a cache or reads an environment variable would make those passes
    order-dependent and would put a state path under two writers (the box-state rule).
    """
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.iterdir())
    built = mod.pack()
    assert built is not None
    assert mod.as_dict()["code"] == mod.CODE
    assert mod.lab_kwargs()["code"] == mod.CODE.lower()
    assert set(tmp_path.iterdir()) == before, "building the pack wrote a file"
