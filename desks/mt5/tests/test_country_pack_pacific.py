"""THE PACIFIC ISLANDS PACK, MEASURED RATHER THAN TRUSTED.

WHAT THESE TESTS ARE FOR. `research/countries/pacific` is ONE pack for SEVEN sovereigns -- Papua
New Guinea, Fiji, Solomon Islands, Vanuatu, New Caledonia, Samoa and Tonga -- and that is exactly
the shape of pack that rots into a regional blur: an actor that belongs to "the Pacific", a
holiday table that closes Suva for PNG Independence Day, a terminology table quietly folded into
English because Tok Pisin and French were harder to type. Every test below pins one of those.

THE SIX LOAD-BEARING TESTS.

`test_check_pack_returns_no_problems` and `test_depth_is_at_parity` are the framework's own two
gates: the twenty-one fields, the eleven actor fields, the negative controls, the broker fence,
and the eight depth targets in `regional_parity.DEPTH_TARGETS`. A score below 1.0 means this
region sits shallower than its siblings, which is the one thing the parity law forbids.

`test_no_instrument_anywhere_is_an_equity_or_absent` is the two-lane order (2026-09-06) at the
data layer. This pack names ExxonMobil, Santos, Newmont, Barrick, Glencore, Eramet and the Fiji
Sugar Corporation; every one of them is an ACTOR and none may reach an instrument tuple.

`test_every_source_layer_is_populated_or_declared_absent_with_a_reason` is the principal's
per-country depth rule. The Pacific genuinely HAS no market-data or trading app ecology, and the
honest form of that is a declared absence carrying its reason -- not a layer quietly filled with
mobile-money apps, and not a blank that looks identical to a layer nobody examined.

`test_terminology_carries_real_tok_pisin_fijian_and_french` is the reason the pack exists at all.
An English-only query reaches RNZ Pacific and stops; the landowner blockade is reported in Tok
Pisin, the cane dispute in Fijian and Fiji Hindi, and the nickel outage entirely in French.

`test_png_independence_day_2026_is_a_wednesday_closure` is one date a human can check by hand.
PNG Independence Day is 16 September and 2026-09-16 is a Wednesday, so it is a real weekday
closure in PNG and in no other jurisdiction here -- and Fiji Day 2026 falls on a Saturday and is
Mondayised, which PNG's calendar would never do. A shared "Pacific calendar" is wrong on both.

Nothing here writes a tracked file; the two filesystem tests use `tmp_path` and `monkeypatch`.
"""
from __future__ import annotations

import importlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CODE = "pacific"

#: The ELEVEN content fields every actor row must fill after its name. An actor missing one is
#: not an actor: without `constraints` there is no forcing, without `observables` no way to
#: check, and without `falsifier` it is a story rather than a research object.
ACTOR_FIELDS: tuple[str, ...] = (
    "holds", "forced_to", "when", "information", "constraints", "instruments",
    "counterparties", "observables", "impact", "persistence", "falsifier")

#: The ten source layers, spelled exactly as the principal's rule spells them.
SOURCE_LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology", "app_ecosystem",
    "media", "archive", "physical_economy", "source_graph")

#: The seven jurisdictions this one pack covers. Every actor, domain and dataset must name one
#: of these (or declare itself regional) so nothing in the pack is a blur.
COUNTRY_TOKENS: frozenset[str] = frozenset(
    {"PG", "FJ", "SB", "VU", "NC", "WS", "TO", "AU", "NZ", "regional"})

#: Real vocabulary, not transliterated English. Each of these is glossed in the pack's own
#: `NATIVE_GLOSSARY`, which is what makes the table checkable by a reader who speaks the language.
TOK_PISIN: tuple[str, ...] = ("mani", "kina", "gavman", "bisnis", "wok", "kaikai", "beng")
FIJIAN: tuple[str, ...] = ("ilavo", "veivakatorocaketaki", "vanua", "dovu", "cagilaba", "baqe")
FRENCH_NICKEL: tuple[str, ...] = ("usine du Sud", "minerai de nickel", "regie", "rouleurs")


def _pack_module() -> Any:
    return importlib.import_module(f"countries.{CODE}.pack")


def _universe() -> dict[str, dict[str, Any]]:
    path = _DESK / "data" / "universe" / "universe.json"
    if not path.exists():
        pytest.skip(f"broker registry absent at {path}; a missing file is not a wrong pack")
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): v for k, v in doc.items() if isinstance(v, dict)}


def _is_equity(row: dict[str, Any]) -> bool:
    klass = " ".join(str(row.get("asset_class") or "").lower().replace("_", " ").split())
    return klass in {"equities", "equity", "equities us", "shares", "share", "stock", "stocks",
                     "us shares"}


def _vocabulary(mod: Any) -> str:
    """Every query and terminology token the pack carries, folded into one haystack."""
    raw = [q for group in mod.layer_terms().values() for q in group]
    raw += [t for group in mod.TERMINOLOGY.values() for t in group]
    return " | ".join(sorted(set(raw)))


# --------------------------------------------------------------------------- shape
def test_the_pack_resolves_and_carries_its_extra_fields() -> None:
    from libs.research import country_lab as CL

    mod = _pack_module()
    built = mod.pack()
    assert built is not None
    resolved = CL.resolve_pack(CODE)
    assert resolved is not None, "country_lab.resolve_pack found no pacific pack"
    for field in ("code", "name", "region_command", "currency", "executable_instruments",
                  "actors", "domains", "policy_eras", "terminology"):
        assert getattr(resolved, field), f"{field} is empty on the resolved pack"
    assert str(resolved.code) == CODE
    assert resolved.region_command == "oceania"
    data = mod.as_dict()
    for extra in ("transmission_targets", "access_constraints", "region_desk", "cot_currency",
                  "source_layers", "layer_absences", "layer_terms", "source_layer_coverage",
                  "currencies", "other_central_banks", "native_glossary"):
        assert data.get(extra) is not None, f"as_dict drops {extra}"
    assert mod.CODE == "PACIFIC" and len(mod.CURRENCY) == 3
    assert len(mod.FISCAL_YEAR_END) == 5 and mod.FISCAL_YEAR_END[2] == "-"
    assert set(mod.NATIVE_LANGUAGES) >= {"en", "tpi", "ho", "fj", "hif", "fr"}


def test_check_pack_returns_no_problems() -> None:
    from research.countries import check_pack  # type: ignore[import-not-found]

    problems = check_pack(_pack_module().as_dict())
    assert problems == [], f"check_pack refused the pacific pack: {problems[:8]}"


def test_the_framework_validator_finds_nothing_fatal_and_coerces_nothing() -> None:
    from libs.research import country_lab as CL

    built = CL.resolve_pack(CODE)
    assert built is not None
    assert list(built.coercion_notes) == [], (
        "the pack handed CountryPack a field it has no slot for; a coercion note means data was "
        f"folded or dropped on import: {list(built.coercion_notes)[:4]}")
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on the pacific pack: {fatal[:4]}"


def test_depth_is_at_parity() -> None:
    from libs.research import country_lab as CL
    from libs.research import regional_parity as RP

    built = CL.resolve_pack(CODE)
    assert built is not None
    row = RP.pack_depth(built, CODE).as_row()
    assert row["score"] == 1.0, f"depth score {row['score']} < 1.0; targets {RP.DEPTH_TARGETS}"
    assert row["layers_unmapped"] == 0, "a layer nobody looked at is not a measured absence"
    assert row["untagged_sources"] == 0, "a source reaching the framework UNTAGGED is pack work"
    for field, floor in (("actors", 12), ("domains", 10), ("edges", 8), ("terms", 40),
                         ("datasets", 8), ("eras", 4), ("instruments", 6)):
        assert row[field] >= floor, f"{field}={row[field]} is below the parity floor {floor}"


# --------------------------------------------------------------------------- the universe fence
def test_no_instrument_anywhere_is_an_equity_or_absent() -> None:
    """THE TWO-LANE ORDER (2026-09-06) at the data layer, on every instrument tuple in the pack.

    Trial count is a SHARED cost: every equity cell on the docket raises the deflated-Sharpe bar
    each FX and metals cell must clear. This pack names ExxonMobil, Santos, Newmont, Barrick,
    Glencore, Eramet, BSP and the Fiji Sugar Corporation, and every one of them is an ACTOR.
    """
    universe = _universe()
    mod = _pack_module()
    tuples: list[tuple[str, tuple[str, ...]]] = [
        ("executable_instruments", tuple(mod.EXECUTABLE_INSTRUMENTS))]
    tuples += [(f"actor:{a['name'][:40]}", tuple(a["instruments"])) for a in mod.ACTORS]
    tuples += [(f"domain:{d['id']}", tuple(d["instruments"])) for d in mod.DOMAINS]
    tuples += [(f"fixing:{f['name'][:40]}", tuple(f["instruments"]))
               for f in mod.FIXING_CONVENTIONS]
    tuples += [(f"target:{t['name'][:40]}", tuple(t["proxies"]))
               for t in mod.TRANSMISSION_TARGETS]
    for where, symbols in tuples:
        assert symbols, f"{where}: names no instrument at all"
        for sym in symbols:
            row = universe.get(sym)
            assert row is not None, f"{where}: {sym} is not in the broker registry"
            assert not _is_equity(row), (
                f"{where}: {sym} is a single-name equity; the two-lane order forbids hunting it")


def test_every_transmission_edge_lands_on_a_real_broker_symbol() -> None:
    """L1.49: a gate that never ran is a claim the desk cannot cash. An edge naming a symbol the
    box does not quote compiles a cell nothing can ever fill -- PGK, FJD, JKM, the JCC index and
    every tuna contract belong in `TRANSMISSION_TARGETS`, which is where this pack puts them."""
    universe = _universe()
    mod = _pack_module()
    edges = mod.TRANSMISSION_EDGES_SEED
    assert len(edges) >= 8, f"{len(edges)} transmission seeds, the floor is 8"
    for edge in edges:
        eid = str(edge["id"])
        assert eid.startswith("PAC-"), f"edge id {eid!r} is not prefixed for this pack"
        for sym in (str(edge["target"]), *edge["targets"]):
            row = universe.get(sym)
            assert row is not None, f"edge {eid}: target {sym} is not a broker symbol"
            assert not _is_equity(row), f"edge {eid}: target {sym} is a single-name equity"
        assert str(edge.get("country") or "").strip(), f"edge {eid}: names no jurisdiction"
        for field in ("mechanism", "condition", "control", "falsifier", "evidence"):
            assert str(edge.get(field) or "").strip(), f"edge {eid}: has no {field}"


def test_the_pack_refuses_an_instrument_the_registry_does_not_know(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ABSENCE IS NOT PERMISSION. Point the checker at an empty registry and it must say so by
    name rather than pass a pack whose symbols were never checked against anything (L1.28a)."""
    import research.countries as C  # type: ignore[import-not-found]

    empty = tmp_path / "universe.json"
    empty.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(C, "_UNIVERSE_CACHE", {"path": None, "mtime": None, "rows": {}})
    problems = C.check_pack(_pack_module().as_dict(), path=empty)
    assert any("UNMEASURED" in p or "unreadable" in p for p in problems), (
        "an unreadable broker registry must be reported as UNMEASURED, never passed silently")


# --------------------------------------------------------------------------- actors and domains
def test_every_actor_fills_all_eleven_fields_and_names_its_country() -> None:
    actors = _pack_module().ACTORS
    assert len(actors) >= 12, f"{len(actors)} actors, the floor is 12"
    seen: set[str] = set()
    for actor in actors:
        name = str(actor.get("name") or "").strip()
        assert name, "an actor with no name"
        assert name not in seen, f"actor {name}: declared twice"
        seen.add(name)
        country = str(actor.get("country") or "")
        assert country, f"{name}: no country; one pack, seven sovereigns, no blurs"
        assert any(tok in country for tok in COUNTRY_TOKENS), (
            f"{name}: country {country!r} names no jurisdiction this pack covers")
        for field in ACTOR_FIELDS:
            value = actor.get(field)
            assert value, f"{name}: field {field!r} is empty"
            if isinstance(value, tuple):
                assert all(str(v).strip() for v in value), f"{name}: blank entry in {field!r}"
        assert len(str(actor["falsifier"])) > 60, (
            f"{name}: falsifier is a stub -- an actor whose falsifier is a phrase is a story")


def test_every_domain_has_objects_conditions_and_two_controls() -> None:
    domains = _pack_module().DOMAINS
    assert len(domains) >= 10, f"{len(domains)} domains, the floor is 10"
    seen: set[str] = set()
    for dom in domains:
        did = str(dom.get("id") or "")
        assert did.startswith("PAC-"), f"domain id {did!r} is not prefixed for this pack"
        assert did not in seen, f"duplicate domain id {did}"
        seen.add(did)
        assert str(dom.get("country") or "").strip(), f"{did}: names no jurisdiction"
        assert dom.get("title"), f"{did}: no title"
        assert dom.get("objects"), f"{did}: no research objects"
        assert dom.get("conditions"), f"{did}: no conditions"
        controls = dom.get("controls") or ()
        assert len(controls) >= 2, (
            f"{did}: {len(controls)} negative controls. An effect with no control cannot be "
            f"told from its own selection")


def test_every_dataset_names_its_country_and_fills_the_catalogue_fields() -> None:
    fields = ("name", "source", "coverage", "frequency", "revisions", "licence", "history_from",
              "assets", "mechanism_families", "how_to_fetch")
    datasets = _pack_module().DATASETS
    assert len(datasets) >= 8, f"{len(datasets)} datasets, the floor is 8"
    for ds in datasets:
        name = str(ds["name"])
        assert " -- " in name, f"dataset {name!r} does not name its jurisdiction before the dash"
        for field in fields:
            assert ds.get(field), f"dataset {name}: {field} is empty"
        assert float(ds["publication_lag_days"]) >= 0.0, f"dataset {name}: negative lag"
        assert isinstance(ds["pit_feasible"], bool), f"dataset {name}: pit_feasible is not a bool"


# --------------------------------------------------------------------------- the ten layers
def test_every_source_layer_is_populated_or_declared_absent_with_a_reason() -> None:
    mod = _pack_module()
    counts = mod.layer_counts()
    assert set(counts) == set(SOURCE_LAYERS), "the pack does not use the ten canonical layers"
    coverage = mod.source_layer_coverage()
    assert coverage["unexplained_missing"] == [], (
        f"a layer with no source and no reason is a blank, not a measurement: "
        f"{coverage['unexplained_missing']}")
    for layer, n in counts.items():
        reason = str(mod.LAYER_ABSENCES.get(layer, ""))
        assert n > 0 or len(reason) > 80, (
            f"layer {layer}: {n} sources and no substantive declared reason for the absence")
    absences = [s for s in mod.SOURCE_CLASSES if str(s["id"]).startswith("absent_")]
    for row in absences:
        assert "DECLARED ABSENT" in str(row["notes"]), f"{row['id']}: absence carries no reason"
        assert str(row["layer"]) in mod.LAYER_ABSENCES, (
            f"{row['id']}: declared absent in SOURCE_CLASSES but not in LAYER_ABSENCES, so the "
            f"framework would read the layer as unmapped rather than as a measured absence")
    assert coverage["machine_use_forbidden"], (
        "no source is registered machine_use_allowed=false; the licensed nickel and LNG "
        "assessments this region prices against must be registered and never scraped")
    assert coverage["low_weight_kept"], "no FRINGE or UNRELIABLE source is kept at low weight"


def test_the_app_ecosystem_absence_is_the_declared_one_and_is_argued() -> None:
    """The Pacific's thin ecologies are declared, not invented. `app_ecosystem` is genuinely
    absent -- no licensed retail broker, exchange control against outward margin, and mobile
    money registered where it belongs -- and the practitioner layer is present but says on its
    face that no domestic sell-side research industry exists, which is why PAC-PNG-A has no
    consensus to measure a surprise against."""
    mod = _pack_module()
    assert set(mod.LAYER_ABSENCES) == {"app_ecosystem"}, (
        f"unexpected declared absences: {sorted(mod.LAYER_ABSENCES)}")
    reason = mod.LAYER_ABSENCES["app_ecosystem"]
    assert "institutional" in reason and "exchange control" in reason, (
        "the absence must say where the mobile-money rails went and why they are not this layer")
    practitioner = [s for s in mod.SOURCE_CLASSES if s["layer"] == "practitioner"]
    assert practitioner, "the practitioner layer is thin here but it is not empty"
    assert any("sell-side" in str(s["notes"]) for s in practitioner), (
        "the practitioner layer must declare that this region has no sell-side research")


# --------------------------------------------------------------------------- native terminology
def test_terminology_carries_real_tok_pisin_fijian_and_french() -> None:
    """A terminology table folded into English finds the English-speaking corner of a ground and
    then reports that corner as if it were the ground. Tok Pisin is the lingua franca of nine
    million people, Fijian and Fiji Hindi split Fiji's ground in half, and New Caledonia's nickel
    industry is reported entirely in French."""
    mod = _pack_module()
    terms = mod.TERMINOLOGY
    assert len(terms) >= 10, f"{len(terms)} terminology domains, the floor is 10"
    distinct = {t for group in terms.values() for t in group}
    assert len(distinct) >= 40, f"{len(distinct)} distinct terms, the floor is 40"
    flat = {t.casefold() for t in distinct}
    for token in TOK_PISIN:
        assert token.casefold() in flat, f"Tok Pisin term {token!r} is absent from TERMINOLOGY"
    for token in FIJIAN:
        assert token.casefold() in flat, f"Fijian term {token!r} is absent from TERMINOLOGY"
    for token in FRENCH_NICKEL:
        assert token.casefold() in flat, f"French nickel term {token!r} is absent"
    glossary = mod.NATIVE_GLOSSARY
    for token in (*TOK_PISIN, *FIJIAN, *FRENCH_NICKEL):
        assert token in glossary, f"{token!r} is used but never glossed; a reader cannot check it"
        lang, gloss, why = glossary[token]
        assert lang in set(mod.NATIVE_LANGUAGES), f"{token!r}: language {lang!r} not declared"
        assert gloss.strip() and why.strip(), f"{token!r}: glossed with nothing"
    haystack = _vocabulary(mod)
    for token in ("kina", "ilavo", "minerai de nickel", "cagilaba"):
        assert token in haystack, f"{token!r} never reaches a source query or terminology row"


def test_the_source_queries_are_not_english_only() -> None:
    """Native queries -> native sources -> native terminology. A layer whose every query is in
    English has mapped the English-speaking corner of the Pacific, which is a small corner."""
    mod = _pack_module()
    by_layer = mod.layer_terms()
    native = {"kina", "mani", "gavman", "bisnis", "kaikai", "ilavo", "baqe", "matanitu",
              "dovu", "suka", "vulagi", "cagilaba", "guria", "usine du Sud", "minerai",
              "emeutes", "couvre-feu", "etat d'urgence", "veivakatorocaketaki"}
    hits = {layer for layer, queries in by_layer.items()
            if any(any(n in q for n in native) for q in queries)}
    assert len(hits) >= 4, (
        f"only {sorted(hits)} carry a native-language query; the official, media and "
        f"physical-economy layers at least must be reachable in the region's own words")


# --------------------------------------------------------------------------- the calendar
def test_png_independence_day_2026_is_a_wednesday_closure() -> None:
    """ONE DATE A HUMAN CAN CHECK. PNG Independence Day is 16 September; 2026-09-16 is a
    Wednesday, so it is a genuine weekday closure in PNG -- and in PNG alone, because no other
    jurisdiction in this pack keeps it and PNG substitutes nothing when a holiday falls at a
    weekend. Fiji Day 2026 falls on a SATURDAY and Fiji Mondayises it to 12 October, which PNG's
    calendar would never do; a shared "Pacific calendar" is wrong on both counts."""
    mod = _pack_module()
    day = date(2026, 9, 16)
    assert day.weekday() == 2, "2026-09-16 must be a Wednesday"
    png = mod.png_holidays(2026)
    assert png[day] == "Independence Day"
    assert day in mod.market_holidays(2026), "a Wednesday closure must survive the weekday filter"
    assert "PG" in mod.national_holidays(2026)[day], "the closure must be tagged to PNG"
    for other in ("FJ", "SB", "VU", "NC", "WS_TO"):
        assert day not in mod.jurisdiction_holidays(other, 2026), (
            f"{other} does not keep PNG Independence Day")
    # Fiji Mondayises, PNG does not.
    assert date(2026, 10, 10).weekday() == 5, "Fiji Day 2026 must fall on a Saturday"
    fiji = mod.fiji_holidays(2026)
    assert fiji.get(date(2026, 10, 12)) == "Fiji Day", "Fiji Day 2026 must be Mondayised"
    assert date(2026, 10, 10) not in fiji, "the Saturday itself is not the observed day"
    # The framework's table shape, which `check_pack` reads.
    table = mod.HOLIDAYS_RULE["table"]
    assert set(table) == {2024, 2025, 2026}
    assert "2026-09-16" in table[2026]
    assert "dateline" in mod.HOLIDAYS_RULE["rule"].casefold(), (
        "the rule text must state the dateline fact; it is part of the derivation, not a note")
    for year, rows in table.items():
        for iso in rows:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"


def test_easter_and_the_cyclone_season_are_computed_not_typed() -> None:
    mod = _pack_module()
    assert mod.easter_sunday(2024) == date(2024, 3, 31)
    assert mod.easter_sunday(2025) == date(2025, 4, 20)
    assert mod.easter_sunday(2026) == date(2026, 4, 5)
    assert mod.new_caledonia_holidays(2026)[date(2026, 7, 14)] == "Fete nationale"
    assert mod.new_caledonia_holidays(2026)[date(2026, 9, 24)] == "Fete de la Citoyennete"
    assert mod.solomon_holidays(2026)[date(2026, 7, 7)] == "Independence Day"
    assert mod.cyclone_season(2025) == (date(2025, 11, 1), date(2026, 4, 30))


# --------------------------------------------------------------------------- the miners
def test_all_five_custom_miners_resolve_through_the_framework() -> None:
    """UNWIRED OR IDLE IS A DEFECT (III.16) begins with RESOLVABLE. A custom miner that silently
    never runs is a region the desk believes it is mining and is not."""
    from libs.research import country_lab as CL

    built = CL.resolve_pack(CODE)
    assert built is not None
    loaded, problems = CL.load_custom_miners(built)
    assert problems == [], f"custom miners failed to resolve: {problems[:4]}"
    expected = {"custom:png_lng_loading_clock", "custom:nickel_supply_shock",
                "custom:fiji_crush_season", "custom:dateline_monday_open",
                "custom:transmission_seeds"}
    assert set(loaded) == expected, f"resolved {sorted(loaded)}, expected {sorted(expected)}"
    for name, fn in loaded.items():
        assert callable(fn), f"{name} resolved to something that is not callable"


def test_the_two_miner_registrations_are_one_set_and_none_claims_to_be_wired() -> None:
    mod = _pack_module()
    miners = importlib.import_module(f"countries.{CODE}.miners")
    known = {str(d["id"]) for d in mod.DOMAINS}
    entries = {str(m["entry"]).split(":")[-1] for m in mod.CUSTOM_MINERS}
    assert entries == set(miners.MINERS), (
        f"CUSTOM_MINERS entries {sorted(entries)} do not match MINERS {sorted(miners.MINERS)}")
    for spec in mod.CUSTOM_MINERS:
        assert str(spec["entry"]).startswith(f"countries.{CODE}.miners:")
        assert spec["domain_ids"], f"{spec['name']}: serves no domain"
        for did in spec["domain_ids"]:
            assert did in known, f"{spec['name']}: unknown domain {did!r}"
        assert spec["wired"] is False, (
            f"{spec['name']}: wired must be False -- on this desk 'built' is not a status "
            f"(III.16); a miner is done when it runs on a clock and leaves an artifact")
    for miner, ids in mod.MINER_DOMAINS.items():
        for did in ids:
            assert did in known, f"miner_domains[{miner}]: unknown domain {did!r}"


def test_the_disruption_rows_carry_a_status_so_reported_is_never_pooled_with_recorded() -> None:
    """L1.28a in the pack's own data: a press-dated interruption and a hard public one are
    different claims, and the miners carry the split into every payload."""
    mod = _pack_module()
    tables = (mod.LNG_DISRUPTIONS, mod.NICKEL_DISRUPTIONS, mod.MINE_DISRUPTIONS)
    for table in tables:
        assert table, "a disruption table with no rows cannot drive an event study"
        for iso, what, status in table:
            parsed = date.fromisoformat(iso)
            assert 2010 <= parsed.year <= 2026, f"{iso} is outside the pack's evidence window"
            assert status in {"RECORDED", "REPORTED"}, f"{iso}: unknown status {status!r}"
            assert len(what) > 30, f"{iso}: the row does not say what happened"
    flat = [row for table in tables for row in table]
    assert any(s == "RECORDED" for _i, _w, s in flat)
    assert any(s == "REPORTED" for _i, _w, s in flat)
    riots = tuple(i for i, _w, _s in mod.NICKEL_DISRUPTIONS if "riots begin" in _w)
    assert riots == ("2024-05-13",), (
        "the 13 May 2024 New Caledonia riots are the reference nickel event and must be dated")
