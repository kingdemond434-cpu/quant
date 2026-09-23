"""THE CAUCASUS AND CENTRAL ASIA PACK, VALIDATED -- five jurisdictions, one corridor.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A MULTI-JURISDICTION PACK THAT CREDITS ITSELF WITH COUNTRIES IT DID NOT WRITE. The parity
    fence counts `JURISDICTIONS`, so a pack that declares five and answers three closes a gap
    that is still open -- which is worse than a missing pack, because the fence then stops
    reporting it. Every jurisdiction here must own at least three actors, two domains and one
    source class with a root of its own, and the tests count them.
  * A REGIONAL AVERAGE THAT HIDES THE ONE COUNTRY NOBODY CAN SEE. All ten source layers are
    covered regionally AND Turkmenistan has four of them missing entirely. Both facts must be
    visible at once, which is what `NO_LAWFUL_GROUND` is for, and the tests assert that every
    declared absence names a substitute.
  * A LATIN-ONLY READING OF A CYRILLIC REGION -- or the reverse. Uzbek is written in BOTH
    scripts and the two are disjoint corpora; Armenian shares an alphabet with nobody; the
    Turkmen gas numbers exist only in Chinese. A crawler handed one script reads one corner.
  * A REGIONAL HOLIDAY MODEL THAT GIVES ARMENIA A NOWRUZ. Armenia keeps no Nowruz and no Eid
    and its Christmas is 6 JANUARY. Getting that wrong mislabels about a dozen ordinary
    Armenian trading days a year as closures -- and throws away the best control in the pack,
    which is that Armenia is OPEN on the days the other four are shut.
  * A SYMBOL THE BOX CANNOT TRADE. Every executable instrument and every edge target is checked
    against the broker's OWN registry. None of the five currencies is in it and all five must
    stay transmission targets.
  * A PACK THAT REACHES THE FRAMEWORK BENT. `CountryPack` coerces every row; a coercion note is
    a field the framework could not read, and this pack must produce none.
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
from countries.caucasus_central_asia import (  # type: ignore[import-not-found]  # noqa: E402
    pack as CCA,
)

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as F  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

# ruff: noqa: RUF001
# RUF001 flags Armenian, Cyrillic and Uzbek-Latin characters that look like Latin ASCII.
# The rule exists to catch homoglyphs in IDENTIFIERS; this file carries the pack's own
# native-script vocabulary as DATA, and asserting on it is the whole point of the language
# tests below. Suppressed file-wide for the same reason `countries/ru/pack.py` does it.

CODE = "caucasus_central_asia"
ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")
#: The four sibling packs of this command. This pack is their COMPLEMENT and must name them.
SIBLINGS = ("ru", "kz", "az", "ge")


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it. Resolved through `resolve_pack` so the test measures
    the same object the country lab runs, not a private construction."""
    got = CL.resolve_pack(CODE)
    assert got is not None, "no Caucasus/Central Asia pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(CCA.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == CODE
    assert str(get(built, "region_command")) == "russia_cis"
    assert str(get(built, "currency")) == "UZS"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    """A coercion note is a field `CountryPack` could not read. There must be none."""
    notes = list(getattr(built, "coercion_notes", ()) or ())
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on this pack: {fatal[:4]}"
    assert CL.validate_pack(built) == [], f"validate_pack: {CL.validate_pack(built)[:4]}"


# ------------------------------------------------------------------------------ jurisdictions
def test_jurisdictions_are_exactly_the_five_this_pack_claims() -> None:
    """The parity fence counts this tuple. Five lowercase ISO-2 codes, no more and no less."""
    assert CCA.JURISDICTIONS == ("am", "uz", "kg", "tj", "tm")
    assert all(j == j.lower() and len(j) == 2 for j in CCA.JURISDICTIONS)
    assert len(set(CCA.JURISDICTIONS)) == 5
    assert set(CCA.ROSTER_JURISDICTIONS) | set(CCA.BEYOND_ROSTER) == set(CCA.JURISDICTIONS)
    assert not set(CCA.ROSTER_JURISDICTIONS) & set(CCA.BEYOND_ROSTER)


def test_the_roster_half_is_on_the_desks_own_roster_and_the_rest_is_declared() -> None:
    """THREE of the five are on `forests.py`; TWO are not, and the pack says which and why.

    A pack that quietly claimed tj and tm as roster countries would make the parity fence
    report a coverage it cannot cash; a pack that refused to write them would leave the
    corridor's two largest physical legs unmined. Declaring both halves is the only honest
    option and it is what the fence can act on.
    """
    named = {c.lower() for f in F.FORESTS.values() for c in f.countries}
    for code in CCA.ROSTER_JURISDICTIONS:
        assert code in named, f"{code} is declared on-roster and is not on the forest roster"
    for code, why in CCA.BEYOND_ROSTER.items():
        assert len(why) > 80, f"{code} is claimed beyond the roster with no real reason"
    # A code moving from BEYOND_ROSTER onto the roster is the FOREST OWNER'S call and must not
    # red this gate; it only means the tuples should be re-split. Asserted as a hint, not a ban.
    assert set(CCA.ROSTER_JURISDICTIONS) <= named
    russia_cis = F.forest("russia_cis")
    assert {"AM", "UZ", "KG"} <= set(russia_cis.countries)
    for sib in SIBLINGS:
        assert sib in russia_cis.packs, f"{sib} is not a russia_cis pack any more"
    # UNWIRED IS A DEFECT (III.16). The parity fence enumerates `Forest.packs`, not the
    # directory, so a pack that is on disk and not in its forest's tuple answers for nobody --
    # the fence keeps reporting am, uz and kg as gaps while this file sits there fully written.
    assert "caucasus_central_asia" in russia_cis.packs, (
        "this pack is not registered in libs/research/forests.py::russia_cis.packs, so the "
        "parity fence cannot see it and the three roster countries stay unanswered")


def test_every_jurisdiction_owes_its_own_actors_domains_and_ground() -> None:
    """Three actors, two domains and a source root apiece -- counted, not asserted."""
    marks = {"am": ("Armenia", "Armenian", "CBA", "Zangezur", "dram"),
             "uz": ("Uzbek", "CBU", "Navoi", "UzEX", "som"),
             "kg": ("Kyrgyz", "NBKR", "Kumtor", "Dordoi"),
             "tj": ("Tajik", "TALCO", "Rogun", "NBT", "somoni"),
             "tm": ("Turkmen", "CNPC", "Galkynys", "manat", "CBT")}
    counts = dict.fromkeys(CCA.JURISDICTIONS, 0)
    for row in CCA.ACTORS:
        text = " ".join(str(row[f]) for f in ("name", "holds", "impact", "notes"))
        for j, words in marks.items():
            if any(w in text for w in words):
                counts[j] += 1
    for j, n in counts.items():
        assert n >= 3, f"{j} owes at least three actors of its own and has {n}"
    for j in ("am", "uz", "kg", "tj", "tm"):
        own = [d for d in CCA.DOMAINS if d["id"].startswith(f"CCA-{j.upper()}-")]
        assert len(own) >= 2, f"{j} owes at least two domains of its own and has {len(own)}"
    for j in CCA.JURISDICTIONS:
        roots = [s for s in CCA.SOURCE_CLASSES if s["id"].startswith(f"cca_{j}_")]
        assert roots, f"{j} has no source class of its own"
        assert all(r["roots"] for r in roots), f"{j}'s own source class has no crawlable root"


def test_all_five_currencies_are_declared_absent_with_their_regimes() -> None:
    """None of AMD, UZS, KGS, TJS or TMT is a broker symbol, and each is routed somewhere real."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing is checked"
    for iso in ("UZS", "KGS", "TJS", "TMT", "USDAMD", "USDUZS", "USDKGS", "USDTJS", "USDTMT"):
        assert iso not in registry, f"{iso} is in the registry now -- make it executable"
    # THE TICKER COLLISION, MEASURED AND REFUSED. `AMD` IS in the registry and it is NOT the
    # dram: it is Advanced Micro Devices, a single-name share CFD. A pack that wrote it into
    # its executable list would break the two-lane order AND believe it was trading a currency
    # the broker does not quote. Both halves are asserted so the trap cannot reappear quietly.
    assert "AMD" in registry, "AMD left the registry; re-read this test's reasoning"
    assert resolve(["AMD"])["equities"] == ["AMD"], (
        "AMD is no longer classed as a single-name equity -- re-check before trusting it")
    assert "AMD" not in set(CCA.EXECUTABLE_INSTRUMENTS)
    assert not any("AMD" in tuple(d["instruments"]) for d in CCA.DOMAINS)
    assert not any("AMD" in tuple(e["targets"]) for e in CCA.TRANSMISSION_EDGES_SEED)
    assert not any("AMD" in tuple(t["proxies"]) for t in CCA.TRANSMISSION_TARGETS)
    collision = " ".join(f"{c['constraint']} {c['measured']} {c['consequence']}"
                         for c in CCA.ACCESS_CONSTRAINTS)
    assert "Advanced Micro Devices" in collision, (
        "the AMD ticker collision is not declared in ACCESS_CONSTRAINTS")
    assert set(CCA.CURRENCIES) == set(CCA.JURISDICTIONS)
    for j, row in CCA.CURRENCIES.items():
        assert row["iso"] and row["regime"] and row["state"], f"{j}: an under-declared currency"
        assert "ABSENT" in row["broker"]
    named = " ".join(str(t["name"]) for t in CCA.TRANSMISSION_TARGETS)
    for iso in ("AMD", "UZS", "KGS", "TJS", "TMT"):
        assert iso in named, f"{iso} is not named in TRANSMISSION_TARGETS"
    for row in CCA.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == [], row["name"]


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    split = resolve(CCA.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert set(CCA.EXECUTABLE_INSTRUMENTS) <= set(universe_symbols())


def test_every_transmission_seed_names_tradable_targets() -> None:
    """A seed that terminates in a symbol the box cannot quote can never compile a cell."""
    seen: set[str] = set()
    for seed in CCA.TRANSMISSION_EDGES_SEED:
        assert seed["id"] not in seen, f"edge {seed['id']} declared twice"
        seen.add(seed["id"])
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"


def test_no_domain_instrument_is_an_equity_and_all_are_executable() -> None:
    """A domain that names a symbol the pack cannot compile mints an uncashable cell."""
    execset = set(CCA.EXECUTABLE_INSTRUMENTS)
    for row in CCA.DOMAINS:
        assert row["instruments"], f"domain {row['id']} names no instrument"
        assert resolve(row["instruments"])["equities"] == [], row["id"]
        assert set(row["instruments"]) <= execset, (
            f"domain {row['id']} names {set(row['instruments']) - execset}, not executable here")


# ------------------------------------------------------------------------------ depth
def test_pack_reaches_parity_depth(built: Any) -> None:
    """The standing depth rule, measured by the framework and not claimed by the pack."""
    row = RP.pack_depth(built, CODE).as_row()
    assert row["score"] == 1.0, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_the_pack_meets_its_own_declared_depth() -> None:
    """A five-jurisdiction pack written to the framework's floor is five countries at a fifth
    of the depth each. The pack declares what it owes and the test measures it."""
    have = CCA.declared_depth()
    for key, floor in CCA.DECLARED_DEPTH.items():
        assert have[key] >= floor, f"{key}: {have[key]} < declared {floor}"
    assert have["actors"] >= 20 and have["domains"] >= 14
    assert have["edges"] >= 12 and have["datasets"] >= 18


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    names: set[str] = set()
    for row in CCA.ACTORS:
        assert row["name"] not in names, f"actor {row['name']!r} declared twice"
        names.add(row["name"])
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
    ids: set[str] = set()
    for row in CCA.DOMAINS:
        assert row["id"] not in ids, f"domain {row['id']} declared twice"
        ids.add(row["id"])
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert row["conditions"], f"domain {row['id']} names no conditioning state"
    assert set(CCA.TERMINOLOGY) == ids, (
        "every domain owes a terminology entry and every terminology key owes a domain")


# ------------------------------------------------------------------------------ the languages
def test_terminology_carries_armenian_cyrillic_latin_and_han() -> None:
    """Six writing systems for five countries, and a crawler handed one reads one corner."""
    assert len(CCA.armenian_terms()) >= 30, f"only {len(CCA.armenian_terms())} Armenian terms"
    assert len(CCA.cyrillic_terms()) >= 80, f"only {len(CCA.cyrillic_terms())} Cyrillic terms"
    assert len(CCA.han_terms()) >= 4, "no Chinese vocabulary, and the Turkmen gas data is there"
    assert len(CCA.uzbek_latin_terms()) == len(CCA.UZBEK_LATIN_MARKERS), (
        f"missing Uzbek Latin vocabulary: "
        f"{sorted(set(CCA.UZBEK_LATIN_MARKERS) - set(CCA.uzbek_latin_terms()))}")
    assert len(CCA.turkmen_latin_terms()) == len(CCA.TURKMEN_LATIN_MARKERS), (
        f"missing Turkmen Latin vocabulary: "
        f"{sorted(set(CCA.TURKMEN_LATIN_MARKERS) - set(CCA.turkmen_latin_terms()))}")
    flat = {t for group in CCA.TERMINOLOGY.values() for t in group}
    for must in ("դրամական փոխանցումներ", "վերաարտահանում", "Սուրբ Ծնունդ"):
        assert must in flat, f"the pack does not carry the Armenian term {must!r}"
    for must in ("qayta eksport", "олтин", "қайта экспорт", "Кумтөр", "сомонӣ", "Роғун"):
        assert must in flat, f"the pack does not carry {must!r}"
    for must in ("tebigy gaz", "Türkmengaz", "manat"):
        assert must in flat, f"the pack does not carry the Turkmen term {must!r}"
    assert CCA.has_armenian("դրամ") and not CCA.has_armenian("dram")
    assert CCA.has_cyrillic("сўм") and not CCA.has_cyrillic("so'm")
    assert CCA.has_han("天然气") and not CCA.has_han("tebigy gaz")


def test_the_uzbek_script_split_is_carried_in_both_directions() -> None:
    """Uzbek in Latin and Uzbek in Cyrillic are DISJOINT CORPORA with the same meaning, and the
    split is itself a crawling fact. A pack that carries one carries half the country."""
    flat = {t for group in CCA.TERMINOLOGY.values() for t in group}
    pairs = (("qayta eksport", "қайта экспорт"), ("oltin", "олтин"),
             ("markaziy bank", "марказий банк"), ("so'm", "сўм"),
             ("paxta tolasi", "пахта толаси"), ("valyuta kursi", "валюта курси"))
    for latin, cyrillic in pairs:
        assert latin in flat, f"the Latin half {latin!r} is missing"
        assert cyrillic in flat, f"the Cyrillic half {cyrillic!r} is missing"
    uz_source = next(s for s in CCA.SOURCE_CLASSES if s["id"] == "cca_uz_official")
    assert any(CCA.has_cyrillic(q) for q in uz_source["queries"])
    assert any(not CCA.has_cyrillic(q) and not CCA.has_armenian(q)
               for q in uz_source["queries"]), "no Latin-script Uzbek query"


def test_every_source_carries_three_independent_labels_and_a_native_query() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in CCA.SOURCE_CLASSES:
        assert row["access_label"] in CCA.ACCESS_LABELS
        assert row["credibility"] in CCA.CREDIBILITY_LABELS
        assert row["predictive_state"] in CCA.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no query at all"
        assert row["roots"], f"{row['id']} has no crawlable root"
        assert row["languages"], f"{row['id']} declares no language"
    native = sum(1 for row in CCA.SOURCE_CLASSES if row["machine_use_allowed"]
                 for q in row["queries"]
                 if CCA.has_armenian(q) or CCA.has_cyrillic(q) or CCA.has_han(q))
    assert native >= 60, f"only {native} native-script queries across crawlable sources"
    scripted = [row["id"] for row in CCA.SOURCE_CLASSES
                if any(CCA.has_armenian(q) or CCA.has_cyrillic(q) or CCA.has_han(q)
                       for q in row["queries"])]
    assert len(scripted) >= 15, f"only {len(scripted)} sources carry a native-script query"


def test_query_territories_cover_every_layer_in_native_script() -> None:
    """The deep-forest miner types these. Three per layer, and not an English-only layer."""
    assert set(CCA.QUERY_TERRITORIES) == set(CCA.SOURCE_LAYERS)
    for layer, qs in CCA.QUERY_TERRITORIES.items():
        assert len(qs) >= 3, f"{layer} carries only {len(qs)} query territories"
        assert any(CCA.has_armenian(q) or CCA.has_cyrillic(q) or CCA.has_han(q)
                   or any(ch in q for ch in "ʻ'äňöüýşçž") for q in qs), (
            f"{layer} is an English-only territory, which reads the English corner of a "
            f"non-English ground and reports the corner as the ground")


# ------------------------------------------------------------------------------ the layers
def test_all_ten_source_layers_are_populated() -> None:
    """The principal's depth rule: ten layers, none of them blank."""
    counts = CCA.layer_counts()
    assert set(counts) == set(CCA.SOURCE_LAYERS)
    assert [layer for layer, n in counts.items() if not n] == []
    coverage = CCA.source_layer_coverage()
    assert coverage["n_layers_covered"] == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible for a region "
        "whose gas border price and concentrate treatment charge both sit behind PRA terms")
    assert coverage["low_weight_kept"], "no fringe or unreliable ground is kept at all"


def test_the_absent_layers_are_per_jurisdiction_and_name_a_substitute() -> None:
    """THE MEASURED REFUSAL. Turkmenistan publishes nothing usable; a regional coverage number
    that averaged it into Armenia would hide the one country the desk cannot see."""
    assert CCA.NO_LAWFUL_GROUND, "no absence is declared anywhere, which is implausible here"
    holes = CCA.source_layer_coverage()["jurisdiction_holes"]
    assert "tm" in holes and len(holes["tm"]) >= 3, (
        "Turkmenistan is declared fully covered, which it is not")
    for row in CCA.NO_LAWFUL_GROUND:
        assert row["jurisdiction"] in CCA.JURISDICTIONS
        assert row["layer"] in CCA.SOURCE_LAYERS
        assert len(row["reason"]) > 60, f"{row['id']}: an absence with no real reason"
        assert row["substitute"] and row["substitute_root"].startswith("http"), (
            f"{row['id']}: an absence with no lawful substitute named")
    assert set(CCA.source_layer_coverage()["jurisdictions_with_full_ground"]) == {"am", "kg", "uz"}
    tm_official = [r for r in CCA.NO_LAWFUL_GROUND
                   if r["jurisdiction"] == "tm" and r["layer"] == "official"]
    assert tm_official and "customs" in tm_official[0]["substitute_root"], (
        "the Turkmen official layer must substitute the CHINESE CUSTOMS mirror by name")


def test_the_interaction_map_names_all_four_sibling_packs() -> None:
    """This pack is the COMPLEMENT of ru, kz, az and ge, and it must say how it touches each."""
    assert len(CCA.INTERACTIONS) >= 4
    withs = {str(row["with"]) for row in CCA.INTERACTIONS}
    assert set(SIBLINGS) <= withs, f"missing sibling interactions: {set(SIBLINGS) - withs}"
    for row in CCA.INTERACTIONS:
        assert row["mechanism"] and row["observable"] and row["control"], row["with"]
        assert row["targets"], f"interaction with {row['with']} names no target"
        assert resolve(row["targets"])["absent"] == [], row["with"]
        assert resolve(row["targets"])["equities"] == [], row["with"]


# ------------------------------------------------------------------------------ the calendars
def test_the_holiday_table_resolves_for_all_three_years() -> None:
    """A table with dates outside its own year is the commonest calendar bug there is."""
    for year in (2024, 2025, 2026):
        table = holiday_table(CCA.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            parsed = date.fromisoformat(iso)
            assert parsed.year == year, f"{iso} is not in {year}"
    assert "2026-04-24" in holiday_table(CCA.HOLIDAYS_RULE, 2026)
    assert "2024-01-06" in holiday_table(CCA.HOLIDAYS_RULE, 2024)


def test_armenian_christmas_is_the_sixth_of_january_and_armenia_keeps_no_nowruz() -> None:
    """The single most important calendar fact in this pack, and the source of its best control.

    Armenia's Christmas is 6 January (the unsplit Nativity-Epiphany of the Armenian Apostolic
    Church), NOT 25 December. And Armenia keeps no Nowruz and no Eid -- so on every one of
    those days four of the five are shut and Armenia is open, which is a treatment and a
    control on the same date inside the same region.
    """
    for year in (2024, 2025, 2026):
        am = CCA.national_holidays("am", year)
        assert date(year, 1, 6) in am, f"Armenian Christmas missing from {year}"
        assert "ARMENIAN CHRISTMAS" in am[date(year, 1, 6)].upper()
        assert date(year, 12, 25) not in am, "25 December is not an Armenian holiday"
        assert date(year, 3, 21) not in am, "Armenia does not observe Nowruz"
        assert date(year, 4, 24) in am, "Genocide Remembrance Day is fixed and certain"
    assert "am" not in CCA.NOWRUZ_DAYS
    assert CCA.nowruz_jurisdictions() == ("kg", "tj", "tm", "uz")
    assert "am" in CCA.NOWRUZ_ABSENT and len(CCA.NOWRUZ_ABSENT["am"]) > 80
    for year in (2024, 2025, 2026):
        for feast_day, _name, _status, where in CCA.ISLAMIC_FEASTS[year]:
            assert "am" not in where, "Armenia keeps no Eid"
            assert feast_day.year == year


def test_nowruz_closes_four_of_five_and_tajikistan_keeps_four_days() -> None:
    """Breadth, not a binary flag, is the state -- and the block is longer than the 21st."""
    for year in (2024, 2025, 2026):
        assert CCA.closure_breadth(date(year, 3, 21)) == 4
        for j in ("uz", "kg", "tj", "tm"):
            assert date(year, 3, 21) in CCA.national_holidays(j, year)
        assert date(year, 3, 24) in CCA.national_holidays("tj", year)
        assert date(year, 3, 24) not in CCA.national_holidays("uz", year)
        block = CCA.nowruz_block(year)
        assert block[0] == date(year, 3, 21) and block[-1] == date(year, 3, 24)


def test_the_2026_eid_lands_the_day_before_nowruz_and_the_pack_knows_it() -> None:
    """THE COLLISION YEAR. Eid al-Fitr drifts about eleven days earlier each solar year, so it
    walks into Nowruz roughly once a generation -- and 2026 is that year. Two separate closures
    become one multi-day block across four jurisdictions while Armenia trades through it."""
    assert CCA.eid_navruz_collision(2026) == -1, "projected Eid al-Fitr 2026 is 20 March"
    assert CCA.eid_navruz_collision(2025) == 9, "Eid al-Fitr 2025 was 30 March"
    assert CCA.collision_years() == (2026,)
    assert CCA.closure_breadth(date(2026, 3, 20)) == 4
    assert CCA.closure_breadth(date(2026, 3, 21)) == 4
    assert date(2026, 3, 20) not in CCA.national_holidays("am", 2026)
    statuses = {st for rows in CCA.ISLAMIC_FEASTS.values() for *_x, st, _w in
                [(r[0], r[1], r[2], r[3]) for r in rows]}
    assert statuses <= {"ANNOUNCED_BY_DECREE", "PROJECTED"}
    assert all(r[2] == "PROJECTED" for r in CCA.ISLAMIC_FEASTS[2026]), (
        "a 2026 decree has not been issued and cannot already be announced")
    assert set(CCA.FEAST_AUTHORITY) == set(CCA.JURISDICTIONS)
    assert "NOT OBSERVED" in CCA.FEAST_AUTHORITY["am"]


# ------------------------------------------------------------------------------ the mechanisms
def test_the_corridor_eras_are_dated_documents_and_not_change_points() -> None:
    """2022-02-24 and 2023-12-22 are public decisions with a date. Three eras, two boundaries."""
    assert CCA.corridor_era(date(2021, 6, 1)) == "PRE_CORRIDOR"
    assert CCA.corridor_era(date(2022, 2, 23)) == "PRE_CORRIDOR"
    assert CCA.corridor_era(date(2022, 2, 24)) == "SURGE"
    assert CCA.corridor_era(date(2023, 12, 21)) == "SURGE"
    assert CCA.corridor_era(date(2023, 12, 22)) == "ENFORCEMENT"
    assert CCA.corridor_era(date(2026, 1, 1)) == "ENFORCEMENT"
    days = CCA.corridor_era_days(date(2022, 2, 21), date(2022, 3, 4), "SURGE")
    assert days[0] == date(2022, 2, 24)
    assert all(d.weekday() < 5 for d in days)
    assert date(2022, 2, 23) not in days
    for era in CCA.CORRIDOR_ERAS:
        assert any(row["name"] for row in CCA.POLICY_ERAS), era


def test_the_remittance_window_is_the_month_end_boundary() -> None:
    """The last weekday of the month through the second weekday of the next -- the window the
    Russian pay cycle actually lands in, computed rather than typed."""
    last, second = CCA.remittance_window(2025, 3)
    assert last == date(2025, 3, 31) and second == date(2025, 4, 2)
    last, second = CCA.remittance_window(2024, 8)
    assert last == date(2024, 8, 30), "31 August 2024 was a Saturday"
    assert second == date(2024, 9, 3), "2 September 2024 is the second weekday"
    last, second = CCA.remittance_window(2025, 12)
    assert last == date(2025, 12, 31) and second.year == 2026
    days = CCA.transfer_release_days(date(2025, 1, 1), date(2025, 3, 31))
    assert days and all(d.weekday() < 5 for d in days)
    assert all(d.day >= 28 or d.month in (3, 12) for d in days)


def test_the_parallel_premium_is_the_state_where_the_official_rate_is_a_constant() -> None:
    """Turkmenistan's rate has not moved since 2015-01-01; the PREMIUM carries the information."""
    assert CCA.parallel_premium(3.5, 3.5) == 0.0
    assert abs(CCA.parallel_premium(3.5, 7.0) - 1.0) < 1e-12
    assert CCA.premium_state(3.5, 3.6) == "TIGHT"
    assert CCA.premium_state(3.5, 4.2) == "STRESSED"
    assert CCA.premium_state(3.5, 6.0) == "BROKEN"
    assert CCA.premium_state(3.5, 19.5) == "PARALLEL_IS_THE_MARKET"
    assert CCA.premium_state(0.0, 19.5) == "UNMEASURED", (
        "an unreadable official rate is UNMEASURED and must never look like a zero premium")
    assert CCA.premium_state(3.5, 0.0) == "UNMEASURED"


# ------------------------------------------------------------------------------ the cells
def test_the_pack_mints_real_cells_and_reports_how_many() -> None:
    """The point of a pack is CELLS REACHING THE ONE GAUNTLET, honestly minted."""
    rows = CCA.cells()
    assert 60 <= len(rows) <= 220, f"{len(rows)} cells is outside the honest range"
    assert rows == CCA.CELLS
    ids = [r["cell_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate cell ids"
    domain_ids = {d["id"] for d in CCA.DOMAINS}
    execset = set(CCA.EXECUTABLE_INSTRUMENTS)
    for r in rows:
        assert r["domain"] in domain_ids
        assert r["symbol"] in execset
        for field in ("condition", "mechanism_family", "horizon", "control", "why"):
            assert r[field], f"{r['cell_id']} has an empty {field}"
        assert r["cell_id"].startswith("caucasus_central_asia:")
    assert {r["domain"] for r in rows} == domain_ids, (
        "a domain that mints no cell is a domain the gauntlet never sees")


def test_datasets_carry_every_field_a_collector_needs() -> None:
    """`DatasetRow` has no notes slot, so a thirteenth key would be DROPPED on import."""
    from countries import DATASET_FIELDS
    assert len(CCA.DATASETS) >= 18
    for row in CCA.DATASETS:
        assert set(row) == set(DATASET_FIELDS), (
            f"{row.get('name')!r}: {set(row) ^ set(DATASET_FIELDS)}")
        assert float(row["publication_lag_days"]) >= 0.0
        assert len(str(row["how_to_fetch"])) > 40, (
            f"{row['name']!r}: how_to_fetch is not concrete enough for a collector")
        assert row["assets"] and resolve(row["assets"])["absent"] == [], row["name"]
    assert any(not r["pit_feasible"] for r in CCA.DATASETS), (
        "every dataset claims to be point-in-time feasible, which is not true of trade mirrors")


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {"custom:corridor_era_breaks", "custom:remittance_month_end",
                        "custom:regional_closure_breadth", "custom:sovereign_gold_supply",
                        "custom:transmission_seeds", "custom:emit_cells"}
    assert all(callable(fn) for fn in got.values())


def test_custom_miner_rows_name_known_domains_and_match_the_miners_module() -> None:
    """The two registrations -- CUSTOM_MINERS and MINERS -- must be one set."""
    from countries.caucasus_central_asia import miners as M
    ids = {d["id"] for d in CCA.DOMAINS}
    entries = set()
    for row in CCA.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.caucasus_central_asia.miners", row["entry"]
        assert callable(getattr(M, func)), f"{row['entry']} does not resolve"
        entries.add(func)
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    assert entries == set(M.MINERS)
    for dids in CCA.MINER_DOMAINS.values():
        assert set(dids) <= ids


def test_mine_returns_a_report_and_emits_nothing_without_a_ctx() -> None:
    """The department entry is pure python and safe to call from a test: no ctx, no emission."""
    report = CCA.mine(None)
    assert report["code"] == CODE
    assert report["dry_run"] is True
    assert report["emitted"] == 0, "mine(None) must not emit anything anywhere"
    assert report["cells_emitted"] == len(CCA.CELLS)
    assert report["rows"], "mine returned no rows at all"
    kinds = {r["kind"] for r in report["rows"]}
    assert kinds == {"transmission_seed", "cell"}
    assert len(report["rows"]) == len(CCA.CELLS) + len(CCA.TRANSMISSION_EDGES_SEED)
    assert tuple(report["jurisdictions"]) == CCA.JURISDICTIONS
    assert report["layers_covered"] == 10
    assert report["unmeasured"], "a pack with a fixed-rate state and no Turkmen data has holes"
    joined = " ".join(report["unmeasured"])
    assert "NO LAWFUL GROUND" in joined and "NOT_PIT_SAFE" in joined
    assert "UNMEASURED" in joined


def test_mine_emits_through_a_ctx_when_one_is_given() -> None:
    """With a Ctx it emits one row per edge and per cell, and notes every absence by name."""
    class _Ctx:
        def __init__(self) -> None:
            self.rows: list[dict[str, Any]] = []
            self.notes: list[tuple[str, str]] = []

        def record(self, **kw: Any) -> None:
            self.rows.append(dict(kw))

        def note(self, key: str, why: str) -> None:
            self.notes.append((key, why))

    ctx = _Ctx()
    report = CCA.mine(ctx)
    assert report["dry_run"] is False
    assert report["emitted"] == len(report["rows"])
    assert len(ctx.rows) == len(CCA.CELLS) + len(CCA.TRANSMISSION_EDGES_SEED)
    assert len(ctx.notes) == len(report["unmeasured"])
    assert all(k == f"{CODE}:unmeasured" for k, _ in ctx.notes)


# ------------------------------------------------------------------------------ the constraints
def test_the_access_constraints_name_the_ru_packs_measurement_of_the_rouble_legs() -> None:
    """USDRUB and EURRUB are in the registry and are EXPENSIVE; a corridor finding that does not
    survive the `ru` pack's measured cost is not a finding, and the pack says so on its face."""
    blob = " ".join(f"{c['constraint']} {c['measured']} {c['consequence']}"
                    for c in CCA.ACCESS_CONSTRAINTS)
    assert "EURRUB" in blob and "USDRUB" in blob
    assert "164" in blob or "basis points" in blob
    assert "NOT_PIT_SAFE" in blob, "the mirror-statistics PIT trap is not declared"
    assert "selection" in blob.lower(), "the NBKR auction's selection problem is not declared"
    assert "machine_use_allowed=false" in blob.lower()


def test_positioning_declares_the_two_absences_it_cannot_fill() -> None:
    """No COT for any of the five, and no Turkmen external position at all. Both are named."""
    absent = [r for r in CCA.POSITIONING_SOURCES if not r["available"]]
    assert len(absent) >= 2
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in absent)
    assert any(r["jurisdiction"] == "tm" for r in absent)
    for row in CCA.POSITIONING_SOURCES:
        if row["available"]:
            assert row["root"].startswith("http") and row["fields"], row["name"]
            assert row["pit_warning"], f"{row['name']} has no point-in-time warning"


def test_policy_eras_carry_the_two_boundaries_no_study_may_cross() -> None:
    """The 2017-09-05 Uzbek float and the 2023-12-22 enforcement order are hard boundaries."""
    assert len(CCA.POLICY_ERAS) >= 6
    starts = {row["start"] for row in CCA.POLICY_ERAS}
    assert "2017-09-05" in starts, "the Uzbek liberalisation is not an era boundary"
    assert "2022-02-24" in starts, "the corridor SURGE is not an era boundary"
    assert "2023-12-22" in starts, "the ENFORCEMENT era is not an era boundary"
    for row in CCA.POLICY_ERAS:
        lo = date.fromisoformat(str(row["start"]))
        hi = date.fromisoformat(str(row["end"]))
        assert hi >= lo, f"{row['name']}: reversed era"
        assert row["regime"] and row["why_it_matters"], row["name"]
        assert row["status"] in ("SETTLED", "OPEN")
