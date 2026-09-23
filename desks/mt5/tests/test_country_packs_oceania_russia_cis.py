"""THE SEVEN OCEANIA / RUSSIA-CIS / TURKEY PACKS, MEASURED RATHER THAN TRUSTED.

WHAT THESE TESTS ARE FOR. A country pack is DATA, and data that nothing checks rots in exactly
the ways that are hardest to see later: an instrument quietly disappears from the broker's
registry, a single name creeps into an instrument tuple, a holiday function drifts off the year
it was written for, a terminology table gets "tidied" into English, or a source layer is left
blank and looks identical to a layer somebody examined and found empty. Every test below pins one
of those, and each one is a defect that has actually happened somewhere in this repository.

THE FIVE LOAD-BEARING TESTS.

`test_no_pack_can_name_an_equity_as_executable` is the two-lane order (2026-09-06) enforced at
the data layer. Single names are traded on disclosures, never hunted statistically, and every
equity cell on the docket raises the multiplicity bar that the FX and metals cells must clear.

`test_every_transmission_edge_lands_on_a_real_broker_symbol` is L1.49: a gate that never ran is a
claim the desk cannot cash. An edge naming a symbol the box does not quote compiles a cell that
can never be filled, and the pack's own `TRANSMISSION_TARGETS` is where an absent instrument is
supposed to go instead.

`test_the_anzac_divergence_is_real_and_both_sides_are_declared` pins the single calendar fact
this region gets wrong most often. Anzac Day 2026 falls on Saturday 2026-04-25. New Zealand
Mondayises it and is CLOSED on 2026-04-27; New South Wales -- whose calendar the ASX follows --
does not, so AUS200 trades a normal session the same day. A shared "Oceania calendar" is a
one-sided book on that date.

`test_russia_declares_its_access_constraints_and_refuses_eurrub` pins the measurement that shapes
the whole Russian pack: EURRUB's tape on this box ends 2022-02-28, so it is a transmission target
and not an instrument. A pack that let a cell compile against it would be backtesting a world
that ended four years ago.

`test_every_layer_is_populated_or_named_absent` is the principal's depth rule (2026-09-17). A
blank layer and an examined-and-empty layer look identical in a table and mean opposite things;
`unexplained_missing` is the number that must stay at zero.

EVERY INPUT IS THE REAL PACK AND THE REAL BROKER REGISTRY. These are not fixture tests: they read
`desks/mt5/data/universe/universe.json` as it stands on this box, because the question they exist
to answer is whether these packs are true HERE and not whether they are internally consistent.
The one concession is that a missing registry SKIPS rather than fails -- absence of the file is a
different fact from a wrong pack, and conflating them would make the suite lie about which.
"""
from __future__ import annotations

import importlib
import json
import sys
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

import pytest

# ruff: noqa: RUF001, RUF002, RUF003
# RUF001-003 flag characters that resemble ASCII ones. This file asserts on Cyrillic,
# Georgian and Turkish tokens AS DATA -- proving the packs were not ASCII-folded is the
# whole point of several tests here. No identifier in this module is non-ASCII.

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: The seven packs this file owns. Oceania, Russia, Central Asia, the Caucasus and Turkey.
CODES: tuple[str, ...] = ("au", "nz", "ru", "kz", "ge", "az", "tr")

#: The ELEVEN content fields every actor row must fill, after its name. An actor missing one of
#: them is not an actor: without `constraints` there is no forcing, without `observables` there is
#: no way to check, and without `falsifier` it is a story rather than a research object.
ACTOR_FIELDS: tuple[str, ...] = (
    "holds", "forced_to", "when", "information", "constraints", "instruments",
    "counterparties", "observables", "impact", "persistence", "falsifier")

#: The ten source layers, spelled exactly as the principal's rule spells them.
SOURCE_LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology", "app_ecosystem",
    "media", "archive", "physical_economy", "source_graph")

ACCESS_LABELS: frozenset[str] = frozenset({
    "PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA", "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL",
    "USER_SUBMITTED", "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED"})
CREDIBILITY_LABELS: frozenset[str] = frozenset({
    "AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE", "CONTRADICTED", "UNKNOWN"})
PREDICTIVE_STATES: frozenset[str] = frozenset({
    "UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE", "NARRATIVE_FEATURE"})

#: Script ranges that prove a terminology table is in the country's own writing system rather
#: than in transliterated English. Turkish and Azerbaijani use a Latin alphabet, so for those two
#: the evidence is the DIACRITICS, which is why they are listed as explicit characters.
CYRILLIC = set(range(0x0400, 0x0500))
GEORGIAN = set(range(0x10A0, 0x1100))
TURKISH_DIACRITICS = set("ıİşŞğĞçÇöÖüÜ")
AZERBAIJANI_DIACRITICS = set("əƏıİşŞğĞçÇöÖüÜ")


def _pack(code: str) -> Any:
    return importlib.import_module(f"countries.{code}.pack")


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
    """Every query and terminology token a pack carries, folded for matching.

    `str.lower()` is WRONG for Turkish: "VİOP".lower() is "vi̇op", because the dotted
    capital I lowercases to an i plus a combining dot. `casefold` plus an NFKD pass that drops
    combining marks is what actually matches the way a reader expects, and getting this wrong is
    the single commonest bug in Turkish text handling."""
    raw = [q for group in mod.layer_terms().values() for q in group]
    raw += [t for group in mod.TERMINOLOGY.values() for t in group]
    folded = [unicodedata.normalize("NFC", term.casefold()) for term in raw]
    decomposed = [unicodedata.normalize("NFKD", term.casefold()) for term in raw]
    stripped = ["".join(c for c in term if not unicodedata.combining(c))
                for term in decomposed]
    return " | ".join(sorted(set(raw) | set(folded) | set(decomposed) | set(stripped)))


def _get(obj: Any, name: str) -> Any:
    """Read a field from whichever container `pack()` returned. The packs construct a real
    `country_lab.CountryPack` when the framework has landed and degrade to a plain mapping when
    it has not, and BOTH must satisfy these tests -- otherwise the suite silently stops checking
    anything on a tree where the framework is absent, which is exactly when checking matters."""
    return obj[name] if isinstance(obj, dict) else getattr(obj, name)


# --------------------------------------------------------------------------- shape
@pytest.mark.parametrize("code", CODES)
def test_the_pack_builds_in_whichever_container_is_available(code: str) -> None:
    mod = _pack(code)
    built = mod.pack()
    assert built is not None
    for field in ("code", "name", "region_command", "currency", "executable_instruments",
                  "actors", "domains", "policy_eras"):
        assert _get(built, field), f"{code}: {field} is empty on the built pack"
    assert str(_get(built, "code")).upper() == mod.CODE
    # `as_dict` must carry the things the frozen dataclass has no slot for, or they vanish.
    data = mod.as_dict()
    for extra in ("transmission_targets", "access_constraints", "region_desk", "cot_currency",
                  "source_layers", "layer_absences", "layer_terms", "source_layer_coverage"):
        assert data.get(extra) is not None, f"{code}: as_dict drops {extra}"


@pytest.mark.parametrize("code", CODES)
def test_identity_fields_are_canonical(code: str) -> None:
    mod = _pack(code)
    assert code.upper() == mod.CODE
    assert len(mod.CURRENCY) == 3
    assert mod.REGION_COMMAND in {"oceania", "russia_cis", "mea"}, mod.REGION_COMMAND
    assert len(mod.FISCAL_YEAR_END) == 5 and mod.FISCAL_YEAR_END[2] == "-"
    assert mod.NATIVE_LANGUAGES, f"{code}: native-language mining is not optional"


# --------------------------------------------------------------------------- actors
@pytest.mark.parametrize("code", CODES)
def test_twelve_actors_each_filling_all_eleven_fields(code: str) -> None:
    actors = _pack(code).ACTORS
    assert len(actors) >= 12, f"{code}: {len(actors)} actors, the floor is 12"
    for actor in actors:
        name = str(actor.get("name") or "").strip()
        assert name, f"{code}: an actor with no name"
        for field in ACTOR_FIELDS:
            value = actor.get(field)
            assert value, f"{code}/{name}: field {field!r} is empty"
            if isinstance(value, tuple):
                assert all(str(v).strip() for v in value), f"{code}/{name}: blank in {field!r}"
            else:
                assert str(value).strip(), f"{code}/{name}: blank {field!r}"


@pytest.mark.parametrize("code", CODES)
def test_every_actor_names_a_falsifier_long_enough_to_be_one(code: str) -> None:
    """An actor whose falsifier is a word is not falsifiable. This is a crude proxy for a real
    control and it catches the failure it is aimed at: a field filled to satisfy a test."""
    for actor in _pack(code).ACTORS:
        falsifier = str(actor["falsifier"])
        assert len(falsifier) > 60, f"{code}/{actor['name']}: falsifier is a stub: {falsifier!r}"


# --------------------------------------------------------------------------- domains
@pytest.mark.parametrize("code", CODES)
def test_ten_domains_each_with_objects_conditions_and_controls(code: str) -> None:
    domains = _pack(code).DOMAINS
    assert len(domains) >= 10, f"{code}: {len(domains)} domains, the floor is 10"
    seen: set[str] = set()
    for dom in domains:
        did = str(dom.get("id") or "")
        assert did.startswith(f"{code.upper()}-"), f"{code}: domain id {did!r} is not prefixed"
        assert did not in seen, f"{code}: duplicate domain id {did}"
        seen.add(did)
        assert dom.get("title"), f"{code}/{did}: no title"
        assert dom.get("objects"), f"{code}/{did}: no research objects"
        assert dom.get("conditions"), f"{code}/{did}: no conditions"
        controls = dom.get("controls") or ()
        assert len(controls) >= 2, (
            f"{code}/{did}: {len(controls)} negative controls. An effect with no control cannot "
            f"be told from its own selection")


@pytest.mark.parametrize("code", CODES)
def test_every_declared_miner_points_at_a_domain_that_exists(code: str) -> None:
    mod = _pack(code)
    known = {str(d["id"]) for d in mod.DOMAINS}
    for miner in mod.CUSTOM_MINERS:
        assert ":" in str(miner["entry"]), f"{code}/{miner['name']}: entry is not module:function"
        assert miner["domain_ids"], f"{code}/{miner['name']}: serves no domain"
        for did in miner["domain_ids"]:
            assert did in known, f"{code}/{miner['name']}: unknown domain {did!r}"
        assert miner.get("wired") is False, (
            f"{code}/{miner['name']}: wired must be False. On this desk 'built' is not a status "
            f"(III.16) -- a miner is done when it runs on a clock and leaves an artifact")


# --------------------------------------------------------------------------- the universe fence
@pytest.mark.parametrize("code", CODES)
def test_no_pack_can_name_an_equity_as_executable(code: str) -> None:
    """THE TWO-LANE ORDER (2026-09-06), at the data layer.

    Single names are traded on news, financial reports and earnings reaction, never hunted for
    statistical hypotheses. Trial count is a SHARED cost: every equity cell on the docket raises
    the deflated-Sharpe bar that each FX and metals cell must clear. These packs name plenty of
    companies -- BHP, Fonterra, Nornickel, Kazatomprom, SOCAR, TBC -- and every one of them is an
    ACTOR. None may appear in an instrument tuple.
    """
    universe = _universe()
    mod = _pack(code)
    tuples: list[tuple[str, tuple[str, ...]]] = [
        ("executable_instruments", tuple(mod.EXECUTABLE_INSTRUMENTS))]
    tuples += [(f"actor:{a['name'][:40]}", tuple(a["instruments"])) for a in mod.ACTORS]
    tuples += [(f"domain:{d['id']}", tuple(d["instruments"])) for d in mod.DOMAINS]
    for where, symbols in tuples:
        for sym in symbols:
            row = universe.get(sym)
            assert row is not None, f"{code}/{where}: {sym} is not in the broker registry"
            assert not _is_equity(row), (
                f"{code}/{where}: {sym} is a single-name equity; the two-lane order forbids "
                f"hunting it for statistical hypotheses")


@pytest.mark.parametrize("code", CODES)
def test_every_transmission_edge_lands_on_a_real_broker_symbol(code: str) -> None:
    """L1.49: a gate that never ran is a claim the desk cannot cash.

    An edge whose target the box does not quote compiles a cell nothing can fill. An absent
    instrument belongs in `TRANSMISSION_TARGETS` with the symbols its mechanism actually reaches,
    which is where every one of these packs puts iron ore, the KASE index, IMOEX and the rest.
    """
    universe = _universe()
    mod = _pack(code)
    edges = mod.TRANSMISSION_EDGES_SEED
    assert len(edges) >= 8, f"{code}: {len(edges)} transmission seeds, the floor is 8"
    for edge in edges:
        target = str(edge["target"])
        row = universe.get(target)
        assert row is not None, (
            f"{code}: edge {edge['source'][:50]!r} -> {target} is not a broker symbol; it belongs "
            f"in TRANSMISSION_TARGETS")
        assert not _is_equity(row), f"{code}: edge target {target} is a single-name equity"
        for field in ("mechanism", "condition", "control", "falsifier"):
            assert str(edge.get(field) or "").strip(), f"{code}: edge -> {target} has no {field}"


@pytest.mark.parametrize("code", CODES)
def test_transmission_targets_name_the_symbols_they_reach(code: str) -> None:
    """An absent instrument is only useful if the pack says what it reaches INSTEAD."""
    universe = _universe()
    mod = _pack(code)
    assert mod.TRANSMISSION_TARGETS, f"{code}: no transmission targets declared"
    for target in mod.TRANSMISSION_TARGETS:
        assert target.get("why"), f"{code}: transmission target {target['name']!r} has no reason"
        proxies = target.get("proxies") or ()
        assert proxies, f"{code}: {target['name']!r} names no proxy it reaches"
        for sym in proxies:
            assert sym in universe, f"{code}: {target['name']!r} proxies unknown symbol {sym}"


# --------------------------------------------------------------------------- native terminology
@pytest.mark.parametrize(
    ("code", "script", "label"),
    [("ru", CYRILLIC, "Cyrillic"), ("kz", CYRILLIC, "Cyrillic"), ("ge", GEORGIAN, "Georgian")])
def test_terminology_is_in_the_native_script(code: str, script: set[int], label: str) -> None:
    """A transliterated terminology table finds the English-speaking corner of a ground and then
    reports that corner as if it were the ground. Кириллица and ქართული are the evidence that the
    table was written for the primary sources rather than for the reader."""
    terms = _pack(code).TERMINOLOGY
    assert len(terms) >= 10, f"{code}: {len(terms)} terminology domains, the floor is 10"
    hits = sum(1 for group in terms.values() for term in group
               if any(ord(ch) in script for ch in term))
    assert hits >= 20, f"{code}: only {hits} {label}-script terms; this table is transliterated"


@pytest.mark.parametrize(
    ("code", "marks"), [("tr", TURKISH_DIACRITICS), ("az", AZERBAIJANI_DIACRITICS)])
def test_latin_script_terminology_keeps_its_diacritics(code: str, marks: set[str]) -> None:
    """Turkish and Azerbaijani use a Latin alphabet, so the script test cannot apply -- the
    evidence is the DIACRITICS. A query stripped of them ("kur korumali mevduat", "ucot deracasi")
    finds materially less than it appears to, and a table without them was written by somebody
    typing on an English keyboard rather than reading the sources."""
    terms = _pack(code).TERMINOLOGY
    assert len(terms) >= 10, f"{code}: {len(terms)} terminology domains, the floor is 10"
    hits = sum(1 for group in terms.values() for term in group
               if any(ch in marks for ch in term))
    assert hits >= 15, f"{code}: only {hits} terms carry diacritics; this table is ASCII-folded"


@pytest.mark.parametrize("code", CODES)
def test_terminology_keys_are_domains_that_exist(code: str) -> None:
    mod = _pack(code)
    known = {str(d["id"]) for d in mod.DOMAINS}
    for key in mod.TERMINOLOGY:
        assert key in known, f"{code}: terminology keyed on unknown domain {key!r}"
        assert mod.TERMINOLOGY[key], f"{code}: terminology[{key}] is empty"


def test_the_russian_trading_ecosystem_vocabulary_is_present() -> None:
    """The Russian-language retail and algorithmic ground is invisible from English, and these are
    the tokens that reach it. `автоследование` is a REGULATED brokerage product with no close
    Western analogue; `стакан` is the order book; `советник` is an MT4/MT5 expert advisor; `ЛЧИ`
    is the exchange's own public trading competition. Missing any of them means a crawler would
    search the small English-speaking corner of this market and report it as the market."""
    mod = _pack("ru")
    blob = _vocabulary(mod)
    for token in ("автоследование", "алготрейдинг", "робот", "советник", "стакан", "арбитраж",
                  "скальпинг", "habr", "smart-lab", "смартлаб", "лчи", "quik", "mql5",
                  "кодобаза", "тестер стратегий", "маржинколл", "плечо"):
        assert token in blob, f"ru: the vocabulary is missing {token!r}"


@pytest.mark.parametrize(
    ("code", "tokens"),
    [("kz", ("алготрейдинг", "торговый робот", "базалық мөлшерлеме", "ұлттық қор", "наурыз")),
     ("tr", ("kur korumalı mevduat", "gram altın", "uzman danışman", "kapalıçarşı", "viop",
             "faiz kararı")),
     ("az", ("uçot dərəcəsi", "dövlət neft fondu", "novruz", "alqoritmik ticarət")),
     ("ge", ("ფულადი გზავნილები", "მონეტარული პოლიტიკის განაკვეთი", "интервенция"))])
def test_each_country_carries_its_own_trading_vocabulary(
        code: str, tokens: tuple[str, ...]) -> None:
    """Every country's own words, not a translated English list. Kazakhstan borrows the Russian
    algorithmic ecosystem and must carry BOTH languages; Turkey has its own terminal ecosystem
    and its own bullion vocabulary; Azerbaijan's is Latin-with-diacritics; Georgia's is a script
    no other pack in this department uses."""
    mod = _pack(code)
    blob = _vocabulary(mod)
    for token in tokens:
        assert token in blob, f"{code}: the vocabulary is missing {token!r}"


# --------------------------------------------------------------------------- the ten layers
@pytest.mark.parametrize("code", CODES)
def test_every_layer_is_populated_or_named_absent(code: str) -> None:
    """THE PRINCIPAL'S DEPTH RULE (2026-09-17). A country is never "covered" by five obvious
    sources: five official roots is one layer done and nine missing, and the missing nine are
    where an untested mechanism is still lying around. A blank layer and an examined-and-empty
    layer look identical in a table and mean opposite things, so `unexplained_missing` -- a layer
    with no source AND no reason -- is the number that must stay at zero (L1.28a)."""
    mod = _pack(code)
    assert tuple(mod.SOURCE_LAYERS) == SOURCE_LAYERS, f"{code}: the ten layers are misspelled"
    coverage = mod.source_layer_coverage()
    assert coverage["unexplained_missing"] == [], (
        f"{code}: layers with neither a source nor a reason: "
        f"{coverage['unexplained_missing']}")
    assert coverage["n_layers_covered"] + len(coverage["missing"]) == len(SOURCE_LAYERS)
    assert coverage["n_sources"] >= 20, f"{code}: only {coverage['n_sources']} sources"


@pytest.mark.parametrize("code", CODES)
def test_every_source_carries_three_independent_labels(code: str) -> None:
    """Three labels, independent on purpose. A PUBLIC source can be FRINGE; an AUTHORITATIVE one
    can be NOT_PREDICTIVE. Collapsing them into a single quality score is how a desk quietly
    deletes the fringe material that turns out to carry the mechanism, and how it lends authority
    to an official series that has never predicted anything."""
    mod = _pack(code)
    seen: set[str] = set()
    for src in mod.SOURCE_CLASSES:
        sid = str(src["id"])
        assert sid not in seen, f"{code}: duplicate source id {sid}"
        seen.add(sid)
        assert src["layer"] in SOURCE_LAYERS, f"{code}/{sid}: layer {src['layer']!r}"
        assert src["access_label"] in ACCESS_LABELS, f"{code}/{sid}: {src['access_label']!r}"
        assert src["credibility"] in CREDIBILITY_LABELS, f"{code}/{sid}: {src['credibility']!r}"
        assert src["predictive_state"] in PREDICTIVE_STATES, f"{code}/{sid}: predictive_state"
        assert isinstance(src["machine_use_allowed"], bool), f"{code}/{sid}: machine_use_allowed"
        assert str(src.get("notes") or "").strip(), f"{code}/{sid}: no notes"
        if not sid.startswith("absent_"):
            assert src["roots"], f"{code}/{sid}: no roots for a crawler to start from"
            assert src["queries"], f"{code}/{sid}: no queries"
            assert src["languages"], f"{code}/{sid}: no language declared"


@pytest.mark.parametrize("code", CODES)
def test_fringe_material_is_kept_and_no_scrape_sources_are_registered(code: str) -> None:
    """Two rules that pull in opposite directions and are both load-bearing.

    Fringe, unreliable and contradicted PUBLIC material is KEPT as a low-weight evidence object,
    never dropped: a claim that looks false is still a dated, testable claim, and deleting it
    destroys the only record that it was ever made. Turkey is the clearest case -- its inflation
    print is publicly contested and BOTH series are carried.

    And a page whose terms forbid automated extraction is REGISTERED with machine_use_allowed
    False: never scraped, and never omitted either, so the desk knows the ground exists and knows
    exactly why it is not being read.
    """
    mod = _pack(code)
    coverage = mod.source_layer_coverage()
    assert coverage["low_weight_kept"], (
        f"{code}: no fringe or unreliable source is kept. A pack whose sources are all "
        f"authoritative has not looked at the retail or app ground")
    assert coverage["machine_use_forbidden"], (
        f"{code}: no source is registered machine_use_allowed=False. Every country in this "
        f"region has paywalled or terms-restricted ground that must be named rather than omitted")
    for src in mod.SOURCE_CLASSES:
        if src["credibility"] in {"FRINGE", "CONTRADICTED"}:
            assert src["access_label"] in {"PUBLIC", "PUBLIC_SOCIAL", "PUBLIC_WITH_TERMS",
                                           "PUBLIC_ARCHIVE", "USER_SUBMITTED"}, (
                f"{code}/{src['id']}: fringe material is kept only where it is PUBLIC")


def test_no_pack_sources_anything_it_should_not() -> None:
    """The bright line. Nothing in these packs may be sourced from stolen material or from
    anything the desk would hold as inside information, in any country, for any mechanism."""
    for code in CODES:
        for src in _pack(code).SOURCE_CLASSES:
            assert src["access_label"] not in {"STOLEN_UNAUTHORIZED", "CONFIDENTIAL_MNPI"}, (
                f"{code}/{src['id']}: {src['access_label']} is never an acceptable source")


def test_sanctions_sources_are_registered_as_official_public_data() -> None:
    """Sanctions lists are published by governments, carry exact dates, and are the best record of
    WHEN a channel closed. They are data, and the packs that need them say so."""
    for code in ("ru", "kz", "ge"):
        rows = [s for s in _pack(code).SOURCE_CLASSES
                if "sanction" in s["id"] or "sanction" in s["label"].lower()]
        assert rows, f"{code}: the corridor mechanics need the designation lists as a source"
        for row in rows:
            assert row["layer"] == "official", f"{code}/{row['id']}: sanctions data is official"
            assert row["access_label"] in {"OPEN_DATA", "PUBLIC"}, f"{code}/{row['id']}"


# --------------------------------------------------------------------------- calendars
def test_the_anzac_divergence_is_real_and_both_sides_are_declared() -> None:
    """ANZAC DAY 2026 IS A SATURDAY, AND THE TASMAN DISAGREES ABOUT IT.

    New Zealand Mondayises it under the Holidays Act, so the New Zealand market is CLOSED on
    Monday 2026-04-27. New South Wales -- whose calendar the ASX and ASX 24 follow -- does not
    substitute, so AUS200 trades a normal session the same day. Western Australia and the
    Northern Territory do take the Monday, which is why the Australian pack keeps the NATIONAL
    calendar and the MARKET calendar as two separate functions.

    An AUDNZD study that assumes one Oceania calendar is measuring a one-sided book on that date,
    and the substitution rule is DECLARED in both packs rather than inferred.
    """
    au, nz = _pack("au"), _pack("nz")
    anzac, substitute = date(2026, 4, 25), date(2026, 4, 27)
    assert anzac.weekday() == 5, "the premise of this test is that 2026-04-25 is a Saturday"

    assert anzac in au.national_holidays(2026)
    assert substitute in au.state_substitutions(2026), "AU must declare the substitute Monday"
    assert substitute not in au.market_holidays(2026), (
        "the ASX follows the NSW calendar and NSW does not substitute: AUS200 trades 2026-04-27")
    assert set(au.ANZAC_SUBSTITUTING_STATES) == {"WA", "NT"}
    assert au.ANZAC_UNMEASURED_STATES, "QLD and ACT practice has varied and must be UNMEASURED"

    assert substitute in nz.market_holidays(2026), "NZ Mondayises Anzac Day"
    divergence = nz.tasman_calendar_divergence(2026)
    assert substitute in divergence and "NZ closed" in divergence[substitute]


def test_the_holiday_rules_reproduce_the_dates_the_region_is_known_for() -> None:
    """Five dated facts, one per calendar system, each one a thing an imported table gets wrong."""
    # Russia: the New Year block is EIGHT consecutive days, the longest closure in the department.
    ru_2026 = _pack("ru").national_holidays(2026)
    assert all(date(2026, 1, d) in ru_2026 for d in range(1, 9))
    assert date(2026, 1, 7) in ru_2026, "Orthodox Christmas sits inside the block"

    # Kazakhstan: Nauryz is 21-23 March, and two of the three fall at the weekend in 2026.
    kz = _pack("kz")
    assert kz.nauryz(2026) == (date(2026, 3, 21), date(2026, 3, 22), date(2026, 3, 23))
    kz_2026 = kz.national_holidays(2026)
    assert all(d in kz_2026 for d in kz.nauryz(2026))

    # Turkey: Kurban Bayramı begins 2026-05-27, preceded by a HALF-DAY arife.
    tr = _pack("tr")
    assert date(2026, 5, 27) in tr.national_holidays(2026)
    assert date(2026, 5, 26) in tr.half_days(2026), "the arife is a half session, not a closure"
    assert date(2026, 5, 26) not in tr.national_holidays(2026)

    # Azerbaijan: Qurban falls on the same day, so three markets close together.
    assert date(2026, 5, 27) in _pack("az").national_holidays(2026)

    # New Zealand: Matariki is LEGISLATED, not computed. 2026 is 10 July.
    assert _pack("nz").MATARIKI[2026] == date(2026, 7, 10)
    assert date(2026, 7, 10) in _pack("nz").national_holidays(2026)


def test_georgia_uses_the_orthodox_easter_and_says_how_far_it_diverges() -> None:
    """Georgia keeps the Julian reckoning: Orthodox Easter 2026 is 12 April against the Western
    5 April, and in 2024 the gap was five weeks. A screen using the Western date puts the whole
    Georgian Easter block in the wrong week, every year the two disagree."""
    ge = _pack("ge")
    assert ge.easter_divergence(2026)["orthodox"] == date(2026, 4, 12)
    assert ge.easter_divergence(2026)["western"] == date(2026, 4, 5)
    assert ge.easter_divergence(2024)["orthodox"] == date(2024, 5, 5)
    holidays = ge.national_holidays(2026)
    assert date(2026, 4, 12) in holidays and date(2026, 1, 7) in holidays
    assert date(2026, 4, 5) not in holidays, "the Western date is not a Georgian holiday"


def test_azerbaijan_handles_the_novruz_bayram_collision() -> None:
    """The lunar calendar drifts about eleven days earlier each solar year, so Ramazan bayramı
    walks THROUGH the five-day Novruz block. In 2026 it lands on 20-21 March, inside Novruz, and
    Azerbaijani labour law transfers the coincident days forward. A calendar that does not handle
    the collision silently loses or duplicates days in exactly the years the closure is longest."""
    az = _pack("az")
    assert az.novruz(2026)[0] == date(2026, 3, 20) and len(az.novruz(2026)) == 5
    assert az.RAMAZAN_BAYRAMI[2026] == date(2026, 3, 20), "the collision year is the premise"
    holidays = az.national_holidays(2026)
    ramazan = {d: v for d, v in holidays.items() if "Ramazan" in v}
    assert ramazan, "both Ramazan days must survive the collision somewhere"
    assert all("transferred" in v for v in ramazan.values()), (
        "a feast coinciding with Novruz transfers to the next working day")
    assert all(d > date(2026, 3, 24) for d in ramazan), "it must land after the Novruz block"


@pytest.mark.parametrize("code", CODES)
def test_the_holiday_rule_is_declared_and_computable_for_2024_to_2026(code: str) -> None:
    mod = _pack(code)
    rule = mod.HOLIDAYS_RULE
    assert tuple(rule["years"]) == (2024, 2025, 2026)
    assert rule.get("known_dates"), f"{code}: no worked dates in the holiday rule"
    for iso in rule["known_dates"]:
        date.fromisoformat(iso)
        assert str(rule["known_dates"][iso]).strip(), f"{code}: {iso} has a blank explanation"
    for year in (2024, 2025, 2026):
        produced = mod.market_holidays(year)
        assert produced, f"{code}: no market holidays computed for {year}"
        assert all(d.year in (year, year + 1) for d in produced), f"{code}: {year} leaked"


# --------------------------------------------------------------------------- access constraints
def test_russia_declares_its_access_constraints_and_refuses_eurrub() -> None:
    """THE MEASUREMENT THAT SHAPES THE RUSSIAN PACK, taken on this box 2026-09-17.

    EURRUB_H1.parquet holds 15,199 hourly bars ending 2022-02-28 and nothing after -- the tape
    stops on the day the modern regime begins. The pack therefore puts EURRUB in
    TRANSMISSION_TARGETS and refuses it as an instrument, because a cell compiled against it would
    be backtesting a world that ended four years ago.

    USDRUB is quoted and is kept, with the cost stated: a median H1 spread over the last sixty
    days of 137,509 points -- about 164bp -- against 453 points in 2021, and 30.6% of recent bars
    frozen at open = high = low = close.
    """
    mod = _pack("ru")
    assert "EURRUB" not in mod.EXECUTABLE_INSTRUMENTS
    assert "USDRUB" in mod.EXECUTABLE_INSTRUMENTS
    targets = {t["name"] for t in mod.TRANSMISSION_TARGETS}
    assert any("EURRUB" in name for name in targets), "EURRUB must be named as a target"
    blob = " ".join(f"{c['constraint']} {c['measured']} {c['consequence']}"
                    for c in mod.ACCESS_CONSTRAINTS)
    for token in ("2022-02-28", "137,509", "30.6", "frozen", "COT"):
        assert token in blob, f"ru: the access constraints do not state {token!r}"
    assert mod.COT_CURRENCY == "", "rouble positioning ended in 2022 and has no successor"


def test_turkey_states_the_direction_dependent_cost_floor() -> None:
    """Turkey's tape is healthy and its CARRY is not: the broker charges -10,921 points a night to
    hold long USDTRY and pays +1,481 short, about 7.4 to one. A symmetric cost assumption flatters
    the depreciation trade enormously, so the asymmetry is stated as an access constraint rather
    than buried in a footnote."""
    mod = _pack("tr")
    blob = " ".join(f"{c['constraint']} {c['measured']} {c['consequence']}"
                    for c in mod.ACCESS_CONSTRAINTS)
    for token in ("10,921", "1,481", "405", "1,587", "2,405", "COT"):
        assert token in blob, f"tr: the access constraints do not state {token!r}"
    assert mod.COT_CURRENCY == "", "there is no COT series for the lira"


@pytest.mark.parametrize("code", ("kz", "ge", "az"))
def test_transmission_only_countries_quote_none_of_their_own_instruments(code: str) -> None:
    """KZT, GEL and AZN are absent from this broker, so those three packs are TRANSMISSION-ONLY by
    construction: every domain terminates in a foreign symbol. A pack that pretended otherwise
    would compile cells nothing can fill, and AZN carries a second reason -- it has been pegged at
    1.7000 since 2017, so a statistical test on it reports a variance near zero and a Sharpe that
    is an artefact of the denominator."""
    universe = _universe()
    mod = _pack(code)
    home = {"kz": ("USDKZT", "KZT"), "ge": ("USDGEL", "GEL"), "az": ("USDAZN", "AZN")}[code]
    for sym in home:
        assert sym not in universe, f"{code}: {sym} unexpectedly quoted; revisit this pack"
        assert sym not in mod.EXECUTABLE_INSTRUMENTS
    assert mod.COT_CURRENCY == "", f"{code}: no positioning series exists for this currency"
    named = " ".join(t["name"] for t in mod.TRANSMISSION_TARGETS)
    assert home[1] in named or home[0] in named, f"{code}: the home currency must be named"


@pytest.mark.parametrize("code", CODES)
def test_access_constraints_are_stated_with_a_measurement(code: str) -> None:
    mod = _pack(code)
    assert mod.ACCESS_CONSTRAINTS, f"{code}: no access constraints declared"
    for row in mod.ACCESS_CONSTRAINTS:
        for field in ("constraint", "measured", "consequence"):
            assert str(row.get(field) or "").strip(), f"{code}: an access constraint lacks {field}"


# --------------------------------------------------------------------------- eras
@pytest.mark.parametrize("code", CODES)
def test_policy_eras_are_dated_ordered_and_honest_about_the_tail(code: str) -> None:
    """Eras are cut at reaction-function changes, never at calendar years: a cell fitted across
    two of them is an average over two different markets and describes neither. And the LAST era
    must be marked UNVERIFIED_TAIL -- this desk's knowledge of 2025-2026 policy is not
    point-in-time, and saying so is a measurement rather than a disclaimer."""
    eras = _pack(code).POLICY_ERAS
    assert len(eras) >= 5, f"{code}: {len(eras)} policy eras is too coarse to condition on"
    previous: date | None = None
    for era in eras:
        start, end = date.fromisoformat(era["start"]), date.fromisoformat(era["end"])
        assert start < end, f"{code}: era {era['name']!r} is reversed"
        if previous is not None:
            assert start > previous, f"{code}: era {era['name']!r} overlaps its predecessor"
        previous = start
        assert era["status"] in {"SETTLED", "UNVERIFIED_TAIL"}, f"{code}: {era['status']!r}"
        assert str(era.get("why_it_matters") or "").strip(), f"{code}: {era['name']!r} says why"
    assert eras[-1]["status"] == "UNVERIFIED_TAIL", (
        f"{code}: the open era must be UNVERIFIED_TAIL; the desk's view of 2025-2026 is not "
        f"point-in-time and must be re-read from the primary source before a study uses it")


# --------------------------------------------------------------------------- conventions
@pytest.mark.parametrize("code", CODES)
def test_every_fixing_carries_a_parseable_utc_time(code: str) -> None:
    """A fixing whose UTC minute is wrong puts the whole event sample in the wrong bar. Three of
    these seven countries have no seasonal clock change at all -- Russia, Georgia, Azerbaijan and
    Turkey -- and the other three move twice a year in opposite hemispheres."""
    for fix in _pack(code).FIXING_CONVENTIONS:
        for field in ("time_utc", "time_utc_dst"):
            hhmm = str(fix[field])
            hours, _, minutes = hhmm.partition(":")
            assert hhmm.count(":") == 1 and 0 <= int(hours) < 24 and 0 <= int(minutes) < 60, (
                f"{code}/{fix['name']}: {field}={hhmm!r} is not HH:MM UTC")
        assert str(fix.get("dst_rule") or "").strip(), f"{code}/{fix['name']}: no DST rule"
        assert str(fix.get("why") or "").strip(), f"{code}/{fix['name']}: no reason to exist"


@pytest.mark.parametrize("code", CODES)
def test_exchange_index_symbols_are_executable_where_they_are_named(code: str) -> None:
    universe = _universe()
    mod = _pack(code)
    executable = set(mod.EXECUTABLE_INSTRUMENTS)
    for ex in mod.EXCHANGES:
        for sym in ex.get("index_symbols") or ():
            assert sym in universe, f"{code}/{ex['name']}: index symbol {sym} is not quoted"
            assert sym in executable, f"{code}/{ex['name']}: {sym} is not declared executable"


@pytest.mark.parametrize("code", CODES)
def test_datasets_declare_their_point_in_time_fields(code: str) -> None:
    """A dataset with no point-in-time field cannot be used without a look-ahead, and the packs in
    this region carry several that are stale by construction: Georgia's remittances by 15 to 45
    days, Turkey's weekly statistics by seven, every COT by three."""
    for row in _pack(code).DATASETS:
        for field in ("name", "source", "frequency", "revisions", "how_to_fetch"):
            assert str(row.get(field) or "").strip(), f"{code}/{row.get('name')}: no {field}"
        inaccessible = row.get("pit_feasible") is False and not row.get("fields")
        assert row.get("fields") or inaccessible, (
            f"{code}/{row['name']}: declares no fields and is not marked inaccessible. A "
            f"dataset the desk cannot reach is named with pit_feasible=False; a dataset it can "
            f"reach must say what is in it")
        assert "pit_fields" in row, f"{code}/{row['name']}: no point-in-time fields declared"
        assert isinstance(row["publication_lag_days"], float)
