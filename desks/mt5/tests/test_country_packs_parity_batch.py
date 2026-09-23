"""THE PARITY BATCH -- Pakistan, Bangladesh, the United States and Canada, at EQUAL depth.

WHY THESE FOUR ARE TESTED TOGETHER. They are the packs the regional-parity build landed or
completed in one pass, and the point of the pass was not "four more countries": it was that the
United States and Pakistan must reach the SAME depth, measured by the same instrument. That is
the principal's standing order of 2026-09-19 (LAWS 5n) and it is the one claim a per-country test
cannot make, because a per-country test can only say "this pack is good" and never "this pack is
as good as that one". So the assertions here are comparative wherever a comparison is meaningful.

THE FIVE THAT ARE LOAD-BEARING, and why each earns its place:

  1. DEPTH 1.0 ON THE FRAMEWORK'S OWN RULER. `regional_parity.pack_depth` counts what
     `country_lab.CountryPack` actually carries AFTER coercion -- not what the pack's module-level
     tables claim. A pack whose rows are dropped on the way into the dataclass would still look
     rich when read as source and would score low here, which is the difference between testing
     the pack and testing the pack's own opinion of itself.

  2. ZERO COERCION NOTES. A coercion note is the framework saying "you handed me a field I have no
     slot for, and I dropped it". Every dropped field is a table nobody will ever read again. Four
     packs at depth 1.0 with fifty silently dropped fields between them is not parity, it is four
     brochures, so the count must be exactly zero.

  3. ALL TEN SOURCE LAYERS, NONE UNMAPPED, NONE UNTAGGED. The depth rule's half that a scout
     cannot fake by typing. `layers_unmapped == 0` says every layer is either populated or
     DECLARED ABSENT with a reason; `untagged_sources == 0` says no source reached the framework
     without its layer, which would make the coverage number a description of this test's charity.

  4. EVERY DECLARED CUSTOM MINER RESOLVES. A custom miner that silently never runs is a country
     the desk believes it is mining and is not -- `country_lab.load_custom_miners` returns the
     failures by name and this test refuses any. It also asserts the pack directory's own
     `miners.py MINERS` mapping is a SUPERSET of the dotted entries, because those are the two
     registrations that must be one set.

  5. EVERY SYMBOL IS THE BROKER'S. `executable_instruments` and every transmission-edge target
     exist in `data/universe/universe.json` and are not single-name equities (the two-lane order
     of 2026-09-06). A pack that promises USDPKR compiles cells that can never be filled, and an
     equity ticker in the list spends the programme's shared family-wise error budget on the asset
     class the method suits least.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.countries import is_equity, universe_symbols  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

#: The four this file owns. Other builders own the rest and a shared test that fails because a
#: sibling's pack is mid-landing tells nobody anything about either.
CODES: tuple[str, ...] = ("pk", "bd", "us", "ca")
#: The fields the research chain is walked through; an actor missing one is a narrative.
#: These are the framework's OWN `ActorRow` names, not the pack module's. The two sibling
#: schemas differ
#: (`observables`/`impact` here, `observable`/`market_impact` in the pack directory's helper), and
#: a test that asserts the pack's spelling is testing the adapter rather than the country.
ACTOR_FIELDS: tuple[str, ...] = ("name", "holds", "forced_to", "when", "information",
                                 "constraints", "observables", "impact", "falsifier")


@pytest.fixture(scope="module")
def packs() -> dict[str, Any]:
    got = {code: CL.resolve_pack(code) for code in CODES}
    missing = [c for c, p in got.items() if p is None]
    assert not missing, f"these packs do not resolve at all: {missing}"
    return got


@pytest.fixture(scope="module")
def depths(packs: dict[str, Any]) -> dict[str, RP.PackDepth]:
    return {code: RP.pack_depth(pack, code) for code, pack in packs.items()}


# --------------------------------------------------------------------------- 1. equal depth
@pytest.mark.parametrize("code", CODES)
def test_every_pack_reaches_the_standing_depth_rule(code: str,
                                                    depths: dict[str, RP.PackDepth]) -> None:
    d = depths[code]
    assert d.resolved, d.why
    assert d.score == 1.0, (
        f"{code} scores {d.score} against DEPTH_TARGETS={RP.DEPTH_TARGETS}: {d.why}")


def test_the_four_are_at_equal_depth_not_merely_all_above_a_floor(
        depths: dict[str, RP.PackDepth]) -> None:
    scores = {c: d.score for c, d in depths.items()}
    assert len(set(scores.values())) == 1, (
        f"parity means the SAME depth, not four different numbers above a bar: {scores}")


@pytest.mark.parametrize("code", CODES)
def test_no_table_is_merely_at_the_minimum(code: str, depths: dict[str, RP.PackDepth]) -> None:
    """A pack that hits every target exactly is a pack written to the test. Each of the four
    clears at least one target by a real margin, which is what "a country, not a checklist"
    looks like when it is measured."""
    d = depths[code]
    have = {"actors": d.actors, "domains": d.domains, "edges": d.edges,
            "terms": d.terms, "datasets": d.datasets, "eras": d.eras,
            "instruments": d.instruments}
    clear = [k for k, v in have.items() if v >= RP.DEPTH_TARGETS[k] * 1.2]
    assert len(clear) >= 3, f"{code} sits at the bar on almost everything: {have}"


# --------------------------------------------------------------------------- 2. no coercion
@pytest.mark.parametrize("code", CODES)
def test_nothing_the_pack_declares_is_silently_dropped(code: str,
                                                       packs: dict[str, Any]) -> None:
    notes = list(getattr(packs[code], "coercion_notes", ()) or ())
    assert notes == [], (
        f"{code}: {len(notes)} field(s) were dropped on the way into CountryPack and will never "
        f"be read again: {notes[:5]}")


@pytest.mark.parametrize("code", CODES)
def test_the_framework_finds_no_fatal_problem(code: str, packs: dict[str, Any]) -> None:
    fatal = list(CL.fatal_problems(CL.validate_pack(packs[code])))
    assert fatal == [], f"{code}: {fatal[:4]}"


# --------------------------------------------------------------------------- 3. ten layers
@pytest.mark.parametrize("code", CODES)
def test_all_ten_source_layers_are_mapped_or_declared_absent(
        code: str, depths: dict[str, RP.PackDepth]) -> None:
    d = depths[code]
    assert d.layers_unmapped == 0, (
        f"{code}: {d.layers_unmapped} of the ten source layers have neither a source nor a "
        f"declared absence; a blank layer is indistinguishable from a country nobody looked at")
    assert d.layers_declared == len(CL.SOURCE_LAYERS)
    assert d.untagged_sources == 0, (
        f"{code}: {d.untagged_sources} source(s) reach the framework with no layer -- work for "
        f"the pack's author, not coverage")


@pytest.mark.parametrize("code", CODES)
def test_the_native_language_ground_is_declared(code: str, packs: dict[str, Any]) -> None:
    pack = packs[code]
    assert pack.native_languages, f"{code}: native-language mining is not optional"
    terms = {t for words in dict(pack.terminology).values() for t in words}
    assert len(terms) >= RP.DEPTH_TARGETS["terms"], f"{code}: {len(terms)} terms"
    for domain, words in dict(pack.terminology).items():
        assert words, f"{code}: terminology[{domain}] is empty"


def test_the_two_south_asian_packs_carry_non_latin_script(packs: dict[str, Any]) -> None:
    """Urdu and Bangla, actually written. A miner searching Pakistani boards for the Urdu for
    'policy rate' finds material; one searching for 'policy rate' finds nothing, and finding
    nothing is indistinguishable from never having asked."""
    for code, lo, hi in (("pk", 0x0600, 0x06FF), ("bd", 0x0980, 0x09FF)):
        blob = "".join(t for words in dict(packs[code].terminology).values() for t in words)
        assert any(lo <= ord(ch) <= hi for ch in blob), (
            f"{code}: the terminology table is an English glossary, not the country's own words")


# --------------------------------------------------------------------------- 4. the miners
@pytest.mark.parametrize("code", CODES)
def test_every_declared_custom_miner_resolves(code: str, packs: dict[str, Any]) -> None:
    got, problems = CL.load_custom_miners(packs[code])
    assert problems == [], f"{code}: {problems[:4]}"
    assert got, f"{code}: the pack declares no custom miner at all"


@pytest.mark.parametrize("code", CODES)
def test_the_dotted_entries_and_the_miners_module_are_one_set(code: str,
                                                              packs: dict[str, Any]) -> None:
    module = _DESK / "research" / "countries" / code / "miners.py"
    assert module.exists(), f"{code}: no miners.py beside the pack"
    mapping = _load_miners(module, code)
    assert isinstance(mapping, dict) and mapping, f"{code}: miners.py exposes no MINERS mapping"
    declared = {str(e).partition(":")[2] for e in packs[code].custom_miners}
    assert declared <= set(mapping), (
        f"{code}: declared in CUSTOM_MINERS, absent from MINERS: "
        f"{sorted(declared - set(mapping))}")
    for name, fn in mapping.items():
        assert callable(fn), f"{code}: MINERS[{name}] is not callable"


@pytest.mark.parametrize("code", CODES)
def test_every_miner_domain_reference_exists(code: str, packs: dict[str, Any]) -> None:
    ids = {d.id for d in packs[code].domains}
    for miner, wanted in dict(packs[code].miner_domains).items():
        unknown = [w for w in wanted if w not in ids]
        assert not unknown, f"{code}: miner_domains[{miner}] names unknown domain(s) {unknown}"


def _load_miners(path: Path, code: str) -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location(f"parity_batch_{code}_miners", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return getattr(mod, "MINERS", None)


# --------------------------------------------------------------------------- 5. the symbols
@pytest.mark.parametrize("code", CODES)
def test_every_executable_instrument_is_in_the_broker_universe(code: str,
                                                               packs: dict[str, Any]) -> None:
    known = universe_symbols()
    assert known, "the broker universe is unreadable -- no symbol here has been checked (L1.28a)"
    for sym in packs[code].executable_instruments:
        assert sym in known, (
            f"{code}: {sym} is not in data/universe/universe.json; it belongs in "
            f"transmission_targets, named")
        assert not is_equity(sym), (
            f"{code}: {sym} is a single-name equity; the two-lane order (2026-09-06) forbids "
            f"hunting it for statistical hypotheses")


@pytest.mark.parametrize("code", CODES)
def test_every_transmission_edge_reaches_an_executable_target(code: str,
                                                              packs: dict[str, Any]) -> None:
    known = universe_symbols()
    edges = packs[code].transmission_edges_seed
    assert len(edges) >= RP.DEPTH_TARGETS["edges"], f"{code}: {len(edges)} edges"
    for edge in edges:
        # `TransmissionSeed.asset` is the coerced single target; `targets`/`assets` are the pack
        # directory's plural spellings, kept in `notes` after coercion. All three are read.
        targets = [str(t) for t in (getattr(edge, "assets", None) or ()) if t]
        targets += [str(t) for t in (getattr(edge, "targets", None) or ()) if t]
        for attr in ("asset", "target"):
            got = getattr(edge, attr, "")
            if got:
                targets.append(str(got))
        assert targets, f"{code}: an edge names no executable target at all"
        for sym in targets:
            assert sym in known, f"{code}: edge target {sym} is not in the broker universe"
            assert not is_equity(sym), f"{code}: edge target {sym} is a single-name equity"


# --------------------------------------------------------------------------- the actors
@pytest.mark.parametrize("code", CODES)
def test_every_actor_carries_every_field_including_its_falsifier(code: str,
                                                                 packs: dict[str, Any]) -> None:
    actors = packs[code].actors
    assert len(actors) >= RP.DEPTH_TARGETS["actors"], f"{code}: {len(actors)} actors"
    seen: set[str] = set()
    for a in actors:
        name = str(getattr(a, "name", "") or "").strip()
        assert name, f"{code}: an actor with no name"
        assert name not in seen, f"{code}: actor {name} declared twice"
        seen.add(name)
        for field in ACTOR_FIELDS:
            assert str(getattr(a, field, "") or "").strip() or getattr(a, field, None), (
                f"{code}: actor {name}: {field} is empty -- the chain actor -> constraint -> "
                f"observable -> flow -> market impact -> candidate cannot be walked through a gap")


@pytest.mark.parametrize("code", CODES)
def test_every_domain_has_objects_and_negative_controls(code: str,
                                                        packs: dict[str, Any]) -> None:
    domains = packs[code].domains
    assert len(domains) >= RP.DEPTH_TARGETS["domains"], f"{code}: {len(domains)} domains"
    for d in domains:
        assert d.objects, f"{code}: domain {d.id} has no research objects"
        assert d.controls, (
            f"{code}: domain {d.id} has no negative controls; an effect with no control cannot "
            f"be told from its own selection")


# --------------------------------------------------------------------------- the calendar
@pytest.mark.parametrize("code", CODES)
def test_the_holiday_rule_carries_both_a_derivation_and_a_resolved_table(
        code: str) -> None:
    """A table with no rule cannot be extended past the years somebody typed; a rule with no
    table cannot be checked against a date a human knows. The four packs carry both, and pk and
    bd DERIVE theirs from their own `market_holidays` on import rather than retyping it, so the
    two views cannot drift."""
    from research.countries import holiday_table

    mod = _pack_module(code)
    rule = mod.HOLIDAYS_RULE
    assert str(rule.get("rule") or "").strip(), f"{code}: holidays_rule carries no derivation"
    for year in (2024, 2025, 2026):
        table = holiday_table(rule, year)
        assert table, f"{code}: no resolved holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{code}: {iso} is not in {year}"


def test_the_two_south_asian_calendars_reproduce_a_date_a_human_can_check() -> None:
    """Pakistan Day and Bangladesh's Independence Day: fixed, statutory, and checkable without
    a table. A holiday rule that cannot reproduce a date a human knows is a rule nobody read."""
    from research.countries import holiday_table

    pk = holiday_table(_pack_module("pk").HOLIDAYS_RULE, 2026)
    assert "2026-03-23" in pk, f"Pakistan Day 2026 is absent: {sorted(pk)[:6]}"
    bd = holiday_table(_pack_module("bd").HOLIDAYS_RULE, 2026)
    assert "2026-03-26" in bd, f"Bangladesh Independence Day 2026 is absent: {sorted(bd)[:6]}"


def _pack_module(code: str) -> Any:
    import importlib

    return importlib.import_module(f"research.countries.{code}.pack")
