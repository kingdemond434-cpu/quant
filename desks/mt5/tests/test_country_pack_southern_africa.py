"""THE SOUTHERN AFRICA PACK, VALIDATED -- five jurisdictions, five calendars, THREE weekend rules.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A MULTI-JURISDICTION PACK THAT ANSWERS FOR ONE COUNTRY AND CLAIMS FIVE. `JURISDICTIONS` is
    what the parity fence counts, so the tests check that each of `zw`, `bw`, `mz`, `ao` and `na`
    owes at least three actors and two domains OF ITS OWN -- not five countries' worth of one
    country's mechanisms with four flags stapled on.
  * A REPEAT OF `za`. South Africa is the hub of all five and has its own pack. `za` must be
    named FIRST in INTERACTIONS and the pack's own instruments must be the ones `za` cannot
    reach from the inside: the Great Dyke's platinum, the diamond cycle, the LNG and oil
    provinces, and the CMA seen from the member that is not South Africa.
  * AN ENGLISH-ONLY CRAWL OF TWO LUSOPHONE COUNTRIES. English is official in three of the five,
    which is exactly the trap: an English crawl returns something for every query and reads
    complete. Mozambique and Angola publish their gazettes, their central-bank statistics and
    their entire press in PORTUGUESE, so the tests require Portuguese in every layer and require
    Shona, Ndebele, Setswana and Afrikaans in the terminology.
  * A TYPED WEEKEND RULE. Zimbabwe, Botswana and Namibia substitute a Sunday holiday onto the
    following Monday and Mozambique and Angola do not. That is derived here from the weekday,
    and the tests check it on dates a human can verify -- including 2026-10-05, the Monday a
    one-rule regional calendar would invent.
  * A SYMBOL THE BOX CANNOT TRADE. Every executable instrument and every edge target is checked
    against the broker's OWN registry. ZWG, BWP, MZN, AOA and NAD are absent and must stay
    transmission targets -- with NAD labelled EXACT, because a 1:1 peg is not a proxy.
  * A SINGLE-NAME EQUITY ON A DOCKET. This region is full of tempting names -- the Great Dyke
    operators, Debswana, De Beers, Sonangol, Mozal, Old Mutual -- and every one of them appears
    as an ACTOR or an observable only (two-lane order, 2026-09-06).
  * A PACK THAT REACHES THE FRAMEWORK BENT. `CountryPack` coerces every row; a coercion note is
    a field the framework could not read, and this pack must produce none.
  * A LAYER NOBODY LOOKED AT, and its opposite -- a layer declared absent that is not. The
    app-ecosystem layer here is MOBILE MONEY AND THE PAYMENT RAIL, which four of five central
    banks publish, so the tests require it sourced and require the per-jurisdiction refusals to
    be named in `NO_LAWFUL_GROUND` WITH THEIR LAWFUL SUBSTITUTE.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
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
from countries.southern_africa import pack as SA  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as F  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")
CODE = "southern_africa"


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it, resolved through `resolve_pack` so the test measures
    the same object the country lab runs and not a private construction."""
    got = CL.resolve_pack(CODE)
    assert got is not None, "no Southern Africa pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(SA.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == CODE
    assert str(get(built, "region_command")) == "africa"
    assert str(get(built, "currency")) == "ZWG"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    """A coercion note is a field `CountryPack` could not read. There must be none."""
    notes = list(getattr(built, "coercion_notes", ()) or ())
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on this pack: {fatal[:4]}"


def test_pack_reaches_parity_depth(built: Any) -> None:
    """The standing depth rule, measured by the framework and not claimed by the pack."""
    row = RP.pack_depth(built, CODE).as_row()
    assert row["score"] == 1.0, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_depth_counts_sit_above_a_five_country_floor() -> None:
    """Twelve actors is the floor for ONE country. A pack answering for five owes more, and the
    brief's own floor for this one is 20 actors, 14 domains, 12 edges and 18 datasets."""
    assert len(SA.ACTORS) >= 20
    assert len(SA.DOMAINS) >= 14
    assert len(SA.TRANSMISSION_EDGES_SEED) >= 12
    assert len(SA.DATASETS) >= 18
    assert len(SA.SOURCE_CLASSES) >= 24
    assert len(SA.POLICY_ERAS) >= 8
    assert len(SA.INTERACTIONS) >= 4
    assert SA.term_count() >= 150


# ----------------------------------------------------------------------- the five jurisdictions
def test_jurisdictions_are_exactly_the_five_claimed_and_all_are_on_the_roster() -> None:
    """`JURISDICTIONS` is what `check_regional_parity.jurisdictions_of` counts. A pack that
    answers for five countries and declares one is credited with one."""
    assert SA.JURISDICTIONS == ("zw", "bw", "mz", "ao", "na")
    assert set(SA.JURISDICTIONS) == {"zw", "bw", "mz", "ao", "na"}
    for code in SA.JURISDICTIONS:
        assert code == code.lower() and len(code) == 2, f"{code!r} is not a lowercase ISO-2 code"
    roster = {c.lower() for f in F.FORESTS.values() for c in f.countries}
    missing = sorted(set(SA.JURISDICTIONS) - roster)
    assert missing == [], f"{missing} are not on any forest's roster in libs/research/forests.py"
    assert CODE in F.forest("africa").packs, "the africa forest does not draw on this pack"
    for code in SA.JURISDICTIONS:
        assert F.forest_of_country(code) == "africa"


def test_each_jurisdiction_owes_its_own_actors_and_domains() -> None:
    """Three actors and two EXCLUSIVELY OWNED domains each, so the pack cannot be one country
    wearing five hats. Exclusive ownership is the strict reading: a regional domain that names
    all five would otherwise credit every jurisdiction for work none of them owns."""
    assert len(SA.ACTOR_JURISDICTION) == len(SA.ACTORS)
    for code in SA.JURISDICTIONS:
        actors = [a for a, j in zip(SA.ACTORS, SA.ACTOR_JURISDICTION, strict=True) if j == code]
        assert len(actors) >= 3, f"{code}: only {len(actors)} actors of its own"
        own = [d for d in SA.DOMAINS
               if SA.DOMAIN_JURISDICTION.get(str(d["id"]), ()) == (code,)]
        assert len(own) >= 2, f"{code}: only {len(own)} domains it exclusively owns"
    assert set(SA.DOMAIN_JURISDICTION) == {str(d["id"]) for d in SA.DOMAINS}
    for did, owners in SA.DOMAIN_JURISDICTION.items():
        assert set(owners) <= set(SA.JURISDICTIONS), f"{did} names a jurisdiction not claimed"
    assert set(SA.CURRENCIES) == set(SA.JURISDICTIONS)
    assert set(SA.CENTRAL_BANKS) == set(SA.JURISDICTIONS)
    assert set(SA.FISCAL_YEAR_ENDS) == set(SA.JURISDICTIONS)
    assert set(SA.JURISDICTION_HOLIDAY_FN) == set(SA.JURISDICTIONS)


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    for row in SA.ACTORS:
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
    for row in SA.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert row["conditions"], f"domain {row['id']} names no conditioning state"
        assert row["instruments"], f"domain {row['id']} names no instrument"
        assert str(row["id"]) in SA.DOMAIN_MECHANISM
        assert str(row["id"]) in SA.DOMAIN_HORIZON


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(SA.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert set(SA.EXECUTABLE_INSTRUMENTS) <= set(registry)
    # the five mechanisms that earn the trial budget each need their own symbol on the docket
    for must in ("XPTUSD", "XPDUSD", "XAUUSD", "XNGUSD", "XBRUSD", "USDZAR", "XALUSD", "XCUUSD"):
        assert must in SA.EXECUTABLE_INSTRUMENTS, f"{must} is not executable in this pack"
    for row in SA.DOMAINS:
        assert resolve(row["instruments"])["equities"] == [], f"domain {row['id']} names an equity"
        assert set(row["instruments"]) <= set(SA.EXECUTABLE_INSTRUMENTS), (
            f"domain {row['id']} names an instrument the pack never declared executable")


def test_every_transmission_seed_names_tradable_targets() -> None:
    """A seed that terminates in a symbol the box cannot quote can never compile a cell."""
    for seed in SA.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"
    for row in SA.INTERACTIONS:
        assert resolve(row["targets"])["absent"] == [], f"interaction {row['with']}: absent target"
        assert resolve(row["targets"])["equities"] == []
    # the corridor and reservoir claims cannot be established alone and must say so
    siblings = {str(s.get("needs_sibling_pack") or "") for s in SA.TRANSMISSION_EDGES_SEED}
    assert "copperbelt" in siblings, (
        "the corridor and Kariba edges are joint measurements with `copperbelt` and must name it")


def test_the_five_currencies_are_named_absent_and_nad_is_labelled_exact() -> None:
    """ZWG, BWP, MZN, AOA and NAD are not quoted here and the pack says so five times. NAD is
    the one case where the carrier IS the thing carried: a 1:1 peg is not an approximation, and
    labelling it PROXY would invite a later reader to add a basis that does not exist."""
    registry = universe_symbols()
    assert not {"ZWG", "BWP", "MZN", "AOA", "NAD", "USDZWG", "USDBWP", "USDNAD"} & set(registry)
    named = " ".join(str(t["name"]) for t in SA.TRANSMISSION_TARGETS)
    for code in ("ZWG", "BWP", "MZN", "AOA", "NAD"):
        assert code in named, f"{code} is not named in TRANSMISSION_TARGETS"
    # diamonds, uranium and LNG are not broker symbols either and are routed, not dropped
    for must in ("DIAMOND", "URANIUM", "LNG", "LITHIUM"):
        assert must in named.upper(), f"{must} is not routed in TRANSMISSION_TARGETS"
    for row in SA.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == []
        assert resolve(row["proxies"])["equities"] == []
        assert row["regime"] and row["route"] and row["why"] and row["exactness"]
    nad = [r for r in SA.TRANSMISSION_TARGETS if str(r["name"]).startswith("NAD")]
    assert len(nad) == 1 and nad[0]["exactness"] == "EXACT", (
        "the Namibia dollar is pegged 1:1 to the rand inside the CMA, so USDZAR is an EXACT "
        "expression of Namibian FX and must not be labelled a proxy")
    others = [r for r in SA.TRANSMISSION_TARGETS
              if str(r["name"])[:3] in ("ZWG", "BWP", "MZN", "AOA")]
    assert len(others) == 4 and all("PROXY" in str(r["exactness"]) for r in others), (
        "the other four currencies are PROXIES and their controls must be named, never the "
        "currency")


def test_cot_and_retail_flow_are_declared_absent_rather_than_silently_missing() -> None:
    """No COT contract and no retail margin statistic exists for any of the five. An absence a
    study can trip over must be named -- including the one case where a substitute DOES exist."""
    absent = [r for r in SA.POSITIONING_SOURCES if not r["available"]]
    assert len(absent) >= 2, "the COT and retail-flow questions are not both answered"
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in absent)
    blob = " ".join(f"{r['name']} {r['why']} {r['pit_warning']}" for r in absent)
    for must in ("ZWG", "BWP", "MZN", "AOA", "NAD", "retail margin", "NBFIRA"):
        assert must in blob, f"the declared absences never mention {must!r}"
    assert "EXACT" in blob, (
        "the ZAR COT is an EXACT substitute for NAD positioning by the 1:1 peg and the pack must "
        "say so rather than quietly borrowing `za`'s series")


# ------------------------------------------------------------------------------ the languages
def test_terminology_carries_portuguese_shona_ndebele_setswana_and_afrikaans() -> None:
    """Five native grounds, because English is official in three of the five and an English-only
    crawl reads the English corner of those three and NONE of the other two."""
    assert len(SA.portuguese_terms()) >= 40, f"only {len(SA.portuguese_terms())} Portuguese terms"
    assert len(SA.shona_terms()) >= 8
    assert len(SA.ndebele_terms()) >= 5
    assert len(SA.setswana_terms()) >= 8
    assert len(SA.afrikaans_terms()) >= 6
    flat = {t for group in SA.TERMINOLOGY.values() for t in group}
    for must in ("goridhe", "mari", "hurumende", "igolide", "diamane", "madi", "puso"):
        assert must in flat, f"the Southern Africa pack does not carry {must!r}"
    for must in ("petróleo", "kwanza", "barragem", "dívida", "corredor", "leilão"):
        assert must in flat, f"the Southern Africa pack does not carry {must!r}"
    for must in ("uraan", "myn", "oshimaliwa", "epangelo"):
        assert must in flat, f"the Namibian vocabulary does not carry {must!r}"
    assert SA.has_portuguese("leilão de divisas") and not SA.has_portuguese("first LNG cargo")
    assert SA.has_shona("mutengo wegoridhe nhasi") and not SA.has_shona("gold price today")
    assert SA.has_ndebele("intengo yegolide") and not SA.has_ndebele("price of gold")
    assert SA.has_setswana("tlhwatlhwa ya diamane") and not SA.has_setswana("diamond price")
    assert SA.has_afrikaans("goud prys vandag") and not SA.has_afrikaans("gold price today")
    assert SA.has_oshiwambo("oshimaliwa shoshilongo")
    assert any(SA.has_changana(t) for t in flat), "no Changana vocabulary at all"
    assert any(SA.has_umbundu(t) for t in flat), "no Umbundu vocabulary at all"
    assert len(SA.TERMINOLOGY) >= 15
    assert set(SA.TERMINOLOGY) == {str(d["id"]) for d in SA.DOMAINS}


def test_every_layer_is_queried_in_portuguese_and_in_a_bantu_or_afrikaans_ground() -> None:
    """A query in English finds an English article about the release, not the release. Portuguese
    is required in EVERY layer because it is the whole of two of the five countries."""
    terms = SA.layer_terms()
    assert set(terms) == set(SA.SOURCE_LAYERS)
    lusophone = [layer for layer, qs in terms.items() if any(SA.has_portuguese(q) for q in qs)]
    assert len(lusophone) == 10, f"only {lusophone} carry a Portuguese query"
    native = [layer for layer, qs in terms.items() if any(SA.has_native(q) for q in qs)]
    assert len(native) == 10, f"only {native} carry any native-language query"
    crawlable = sum(1 for row in SA.SOURCE_CLASSES if row["machine_use_allowed"]
                    for q in row["queries"] if SA.has_native(q))
    assert crawlable >= 80, f"only {crawlable} native-language queries across crawlable sources"


def test_every_source_declaring_a_native_language_actually_queries_in_it() -> None:
    """A source that lists `pt` or `sn` and queries only in English is an English source wearing
    a flag, and it is how a crawl reads the wrong half of a multilingual region."""
    for row in SA.SOURCE_CLASSES:
        if set(row["languages"]) & {"pt", "sn", "nd", "tn", "af", "ng", "ts", "umb"}:
            assert any(SA.has_native(q) for q in row["queries"]), (
                f"{row['id']} declares {row['languages']} and every query is in English")


def test_every_source_carries_three_independent_labels_and_a_query() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in SA.SOURCE_CLASSES:
        assert row["access_label"] in SA.ACCESS_LABELS
        assert row["credibility"] in SA.CREDIBILITY_LABELS
        assert row["predictive_state"] in SA.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no query"
        assert row["roots"], f"{row['id']} has no crawlable root"
        assert row["notes"], f"{row['id']} has no note saying why it is here"


def test_all_ten_source_layers_are_populated_and_the_refusals_name_a_substitute() -> None:
    """The depth rule: ten layers, none blank. The app layer here is MOBILE MONEY AND THE PAYMENT
    RAIL and declaring it absent because there is no MetaTrader ecology would read the wrong
    countries. And a refusal with no substitute is a hole rather than a measurement."""
    counts = SA.layer_counts()
    assert set(counts) == set(SA.SOURCE_LAYERS)
    blank = [layer for layer, n in counts.items() if not n]
    assert blank == [], f"blank layers: {blank}"
    coverage = SA.source_layer_coverage()
    assert coverage["n_layers_covered"] == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible for a region whose "
        "diamond, lithium and uranium prices live behind price-reporting-agency terms")
    assert coverage["low_weight_kept"], "no fringe ground is kept at all, so it was dropped"
    assert counts["app_ecosystem"] >= 1
    mobile = [s for s in SA.SOURCE_CLASSES if s["layer"] == "app_ecosystem"
              and "MOBILE MONEY" in str(s["label"]).upper()]
    assert mobile, "the app layer does not name mobile money, which IS the app layer here"
    # the measured refusals are per JURISDICTION and per layer, not whole-pack
    assert SA.LAYER_ABSENCES == {}
    assert len(SA.NO_LAWFUL_GROUND) >= 6
    seen = set()
    for row in SA.NO_LAWFUL_GROUND:
        assert row["jurisdiction"] in SA.JURISDICTIONS
        assert row["layer"] in SA.SOURCE_LAYERS
        assert len(row["reason"]) > 60, f"{row['jurisdiction']}/{row['layer']}: reason too thin"
        assert len(row["substitute"]) > 60, (
            f"{row['jurisdiction']}/{row['layer']}: a refusal with no lawful substitute named is "
            f"a hole, not a measurement")
        assert row["scope"], f"{row['jurisdiction']}/{row['layer']}: no scope declared"
        seen.add(row["jurisdiction"])
    assert seen == set(SA.JURISDICTIONS), (
        f"every jurisdiction owes at least one measured refusal; "
        f"missing {sorted(set(SA.JURISDICTIONS) - seen)}")
    # the three the brief named by hand
    pairs = {(r["jurisdiction"], r["layer"]) for r in SA.NO_LAWFUL_GROUND}
    assert ("zw", "official") in pairs, "Zimbabwe's broken inflation series is not declared"
    assert ("ao", "retail_ecology") in pairs, "Angola's absent retail ecology is not declared"
    assert ("mz", "academic") in pairs, "Mozambique's absent academic literature is not declared"


def test_query_territories_give_the_deep_forest_miner_three_phrases_per_layer() -> None:
    assert set(SA.QUERY_TERRITORIES) == set(SA.SOURCE_LAYERS)
    for layer, phrases in SA.QUERY_TERRITORIES.items():
        assert len(phrases) >= 3, f"{layer}: only {len(phrases)} query territories"
        assert any(SA.has_native(p) for p in phrases), f"{layer}: no native-language phrase"


# ------------------------------------------------------------------------------ the calendars
def test_easter_is_computed_and_everything_hangs_off_it() -> None:
    """The anonymous Gregorian algorithm, checked on three years a human can verify, plus the
    four feasts derived from it -- Botswana's Holy Saturday and Ascension and Angola's Carnaval
    are each observed by SOME of the five and not others."""
    assert SA.western_easter(2024) == date(2024, 3, 31)
    assert SA.western_easter(2025) == date(2025, 4, 20)
    assert SA.western_easter(2026) == date(2026, 4, 5)
    assert SA.good_friday(2025) == date(2025, 4, 18)
    assert SA.holy_saturday(2025) == date(2025, 4, 19)
    assert SA.easter_monday(2025) == date(2025, 4, 21)
    assert SA.ascension_day(2025) == date(2025, 5, 29)
    assert SA.carnival_tuesday(2025) == date(2025, 3, 4)
    # Botswana closes for Holy Saturday and Ascension; Zimbabwe for Easter Saturday but not
    # Ascension; Mozambique for NONE of them
    assert SA.holy_saturday(2025) in SA.botswanan_holidays(2025)
    assert SA.ascension_day(2025) in SA.botswanan_holidays(2025)
    assert SA.ascension_day(2025) in SA.namibian_holidays(2025)
    assert SA.ascension_day(2025) not in SA.zimbabwean_holidays(2025)
    assert SA.good_friday(2025) not in SA.mozambican_holidays(2025), (
        "Mozambique is secular and has no Good Friday; its 25 December is the Dia da Família")
    assert SA.carnival_tuesday(2025) in SA.angolan_holidays(2025)


def test_the_weekday_rules_are_derived_and_not_typed() -> None:
    """Zimbabwe's Heroes' Day is the SECOND MONDAY of August and Botswana's President's Day the
    THIRD MONDAY of July. '11-12 August' is a 2025 fact, not a date: in 2024 it was 12-13 and in
    2026 it is 10-11, and a typed table gets every other year wrong."""
    assert SA.nth_weekday(2024, 8, 0, 2) == date(2024, 8, 12)
    assert SA.nth_weekday(2025, 8, 0, 2) == date(2025, 8, 11)
    assert SA.nth_weekday(2026, 8, 0, 2) == date(2026, 8, 10)
    for year, heroes in ((2024, date(2024, 8, 12)), (2025, date(2025, 8, 11)),
                         (2026, date(2026, 8, 10))):
        table = SA.zimbabwean_holidays(year)
        assert "Heroes' Day" in table[heroes]
        assert "Defence Forces Day" in table[heroes + timedelta(days=1)]
    assert SA.nth_weekday(2025, 7, 0, 3) == date(2025, 7, 21)
    assert "President's Day" in SA.botswanan_holidays(2025)[date(2025, 7, 21)]
    assert "President's Day Holiday" in SA.botswanan_holidays(2025)[date(2025, 7, 22)]


def test_the_monday_substitution_is_derived_and_applies_to_only_three_of_the_five() -> None:
    """THE RULE MOST LIKELY TO SILENTLY MISALIGN AN EVENT STUDY. Zimbabwe, Botswana and Namibia
    move a Sunday holiday onto the following Monday; Mozambique and Angola do not. Applying one
    rule to all five invents closures in two countries and loses them in three."""
    assert set(SA.MONDAY_SUBSTITUTION) == {"zw", "bw", "na"}
    assert set(SA.SUBSTITUTION_STATUS) == set(SA.JURISDICTIONS)
    # Zimbabwe: Unity Day 2024-12-22 was a Sunday, so the Monday closed
    assert date(2024, 12, 22).weekday() == 6
    zw24 = SA.zimbabwean_holidays(2024)
    assert "Sunday substitution" in zw24[date(2024, 12, 23)]
    # Zimbabwe and Namibia both close for Africa Day, and 2025-05-25 was a Sunday
    assert date(2025, 5, 25).weekday() == 6
    assert "Sunday substitution" in SA.zimbabwean_holidays(2025)[date(2025, 5, 26)]
    assert "Sunday substitution" in SA.namibian_holidays(2025)[date(2025, 5, 26)]
    # Namibia: Cassinga Day 2025-05-04 was a Sunday
    assert "Sunday substitution" in SA.namibian_holidays(2025)[date(2025, 5, 5)]
    # Mozambique: Peace Day 2026-10-04 IS a Sunday and Monday 2026-10-05 is an ORDINARY SESSION
    assert date(2026, 10, 4).weekday() == 6
    mz26 = SA.mozambican_holidays(2026)
    assert date(2026, 10, 4) in mz26
    assert date(2026, 10, 5) not in mz26, (
        "Mozambique has no weekend substitution and a one-rule regional calendar invents this "
        "closure -- it is the exact misalignment this derivation exists to prevent")
    # the substitution steps past a day already taken: Botswana's 26 December 2027 is a Sunday
    # and 27 December is free, but the paired-holiday case is what makes the step necessary
    assert date(2027, 12, 26).weekday() == 6
    bw27 = SA.botswanan_holidays(2027)
    assert "Sunday substitution" in bw27[date(2027, 12, 27)]
    # and the pack reports which Mondays exist only because of the rule
    subs = SA.substituted_mondays(2025)
    assert subs[date(2025, 5, 26)] == ("na", "zw")
    assert subs[date(2025, 5, 5)] == ("na",)
    assert SA.substituted_mondays(2026) == {}, (
        "no fixed holiday in any of the three substituting jurisdictions fell on a Sunday in "
        "2026, which is a measurement and not a bug")


def test_the_holiday_tables_resolve_for_three_years_and_stay_inside_them() -> None:
    for year in (2024, 2025, 2026):
        table = holiday_table(SA.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        assert f"{year}-01-01" in table, "New Year's Day is missing"
        assert f"{year}-05-01" in table, "Workers'/Labour Day is missing"
        for code in SA.JURISDICTIONS:
            assert SA.JURISDICTION_HOLIDAY_FN[code](year), f"{code} has no {year} table"
    # the union rows are TAGGED, because a day that closes Gaborone is a session in Luanda
    t25 = holiday_table(SA.HOLIDAYS_RULE, 2025)
    assert "[ZW]" in t25["2025-02-21"], "Youth Day closes Zimbabwe alone"
    assert "[BW]" in t25["2025-09-30"], "Botswana Day closes Botswana alone"
    assert "[MZ]" in t25["2025-06-25"], "Mozambican Independence Day closes Mozambique alone"
    assert "[AO]" in t25["2025-11-11"], "Angolan Independence Day closes Angola alone"
    assert "[NA]" in t25["2025-03-21"], "Namibian Independence Day closes Namibia alone"
    assert SA.closed_in("zw", date(2025, 2, 21))
    assert not SA.closed_in("ao", date(2025, 2, 21))
    # 2025-03-04 is Angola's Carnaval and closes exactly one of the five; 2025-03-05 is the day
    # after and closes none, which is the pair a "Southern African holiday" flag would conflate
    assert SA.closed_in("ao", date(2025, 3, 4)) and SA.is_market_holiday(date(2025, 3, 4))
    assert not any(SA.closed_in(c, date(2025, 3, 4)) for c in ("zw", "bw", "mz", "na"))
    assert not SA.is_market_holiday(date(2025, 3, 5))
    # only three days close all five, which is worth knowing before anyone builds a regional
    # holiday sample out of the union table
    assert SA.all_five_closed(2025) == (date(2025, 1, 1), date(2025, 5, 1), date(2025, 12, 25))
    # a double holiday is ONE lost session and the table says so rather than overwriting
    assert SA.zimbabwean_holidays(2025)[date(2025, 4, 18)].count("+") == 1, (
        "Independence Day fell on Good Friday in 2025: one session, two statutory holidays")


def test_no_jurisdiction_observes_daylight_saving() -> None:
    """CAT is UTC+2 year-round in four of the five and WAT is UTC+1 in Angola; Namibia abolished
    its winter-time switch in 2017. Every session window in this pack is therefore stable in UTC
    all year, unlike every pre-2018 Namibian series."""
    assert "no daylight saving" in SA.HOLIDAYS_RULE["rule"].lower()
    windows = {w["name"]: w for w in SA.SESSION_WINDOWS}
    assert windows["sa_luanda_auction"]["start_utc"] == "09:00", (
        "Luanda is UTC+1 and is one hour behind the other four, which is a real offset")
    for fx in SA.FIXING_CONVENTIONS:
        if "LBMA" not in fx["name"] and "LME" not in fx["name"]:
            assert fx["time_utc"] == fx["time_utc_dst"], f"{fx['name']} moves with a DST rule"


# ------------------------------------------------------------------------------ the mechanisms
def test_zimbabwe_is_six_currency_regimes_and_the_pack_knows_which_one_it_is_in() -> None:
    """THE PACK'S SINGLE MOST IMPORTANT PARTITION. Pooling a Zimbabwean series across any of
    these boundaries measures two monetary systems and calls the difference volatility."""
    assert SA.zim_currency_era(date(2008, 1, 1)) == "ZWD_HYPERINFLATION"
    assert SA.zim_currency_era(date(2015, 1, 1)) == "MULTICURRENCY_DOLLARISED"
    assert SA.zim_currency_era(date(2019, 2, 19)) == "MULTICURRENCY_DOLLARISED"
    assert SA.zim_currency_era(date(2019, 2, 20)) == "RTGS_DOLLAR"
    assert SA.zim_currency_era(date(2024, 4, 4)) == "RTGS_DOLLAR"
    assert SA.zim_currency_era(date(2024, 4, 5)) == "ZIG"
    assert SA.ZIG_LAUNCH.isoformat() == "2024-04-05"
    assert SA.ZIG_DEVALUATION.isoformat() == "2024-09-27"
    assert SA.zig_state(date(2024, 4, 4)) == "PRE_ZIG"
    assert SA.zig_state(date(2024, 4, 5)) == "ZIG_AS_LAUNCHED"
    assert SA.zig_state(date(2024, 9, 26)) == "ZIG_AS_LAUNCHED"
    assert SA.zig_state(date(2024, 9, 27)) == "ZIG_POST_DEVALUATION"
    assert SA.DE_DOLLARISATION < SA.RE_DOLLARISATION
    eras = {str(e["name"]) for e in SA.POLICY_ERAS}
    assert any("ZiG" in n for n in eras)
    assert any(str(e["start"]) == "2024-04-05" for e in SA.POLICY_ERAS)


def test_the_beneficiation_orders_separate_a_gazette_from_a_press_report() -> None:
    """A policy can be reported, real and inoperative at the same time. The lithium ban was
    GAZETTED in December 2022; the platinum concentrate restriction has been announced, deferred
    and re-stated and is PRESS_REPORTED throughout, and the pack never presents one as the other."""
    assert SA.beneficiation_state(date(2022, 12, 19), "lithium") == "NONE"
    assert SA.beneficiation_state(date(2022, 12, 20), "lithium") == "GAZETTED"
    assert SA.beneficiation_state(date(2026, 1, 1), "lithium") == "GAZETTED"
    assert SA.beneficiation_state(date(2022, 12, 31), "pgm") == "NONE"
    assert SA.beneficiation_state(date(2023, 6, 1), "pgm") == "PRESS_REPORTED"
    assert SA.beneficiation_state(date(2025, 6, 1), "pgm") == "PRESS_REPORTED"
    assert all(status in ("GAZETTED", "PRESS_REPORTED")
               for *_rest, status in SA.BENEFICIATION_ORDERS), (
        "a beneficiation date is either gazetted or PRESS_REPORTED and never presented as a "
        "citation it is not")
    assert {m for _d, m, _w, _s in SA.BENEFICIATION_ORDERS} == {"lithium", "pgm"}
    assert all(status in ("GAZETTED", "PRESS_REPORTED")
               for *_rest, status in SA.GOLD_POLICY_EVENTS)


def test_angola_left_opec_on_a_date_and_the_pack_carries_all_three_states() -> None:
    """The announcement and the effect are eleven days apart and they are different events: one
    is the information, the other is when the OPEC production table starts measuring a different
    group of countries."""
    assert SA.OPEC_EXIT_ANNOUNCED.isoformat() == "2023-12-21"
    assert SA.OPEC_EXIT_EFFECTIVE.isoformat() == "2024-01-01"
    assert SA.opec_membership(date(2023, 12, 20)) == "MEMBER"
    assert SA.opec_membership(date(2023, 12, 21)) == "WITHDRAWAL_ANNOUNCED"
    assert SA.opec_membership(date(2023, 12, 31)) == "WITHDRAWAL_ANNOUNCED"
    assert SA.opec_membership(date(2024, 1, 1)) == "NON_MEMBER"
    assert SA.opec_membership(date(2026, 1, 1)) == "NON_MEMBER"
    assert any(str(e["start"]) == "2024-01-01" for e in SA.POLICY_ERAS)


def test_the_pula_basket_is_published_so_the_rand_beta_is_arithmetic() -> None:
    """The rarest thing in frontier FX: an official, numeric, published currency weight. The
    measurement is the RESIDUAL to the published rule, and a crawl rate the pack cannot cite is
    UNMEASURED rather than a plausible number."""
    assert SA.PULA_BASKET == {"SDR": 0.60, "ZAR": 0.40}
    assert SA.pula_zar_beta() == pytest.approx(0.40)
    assert sum(SA.PULA_BASKET.values()) == pytest.approx(1.0)
    rate, status = SA.pula_crawl_rate(2023)
    assert rate == pytest.approx(-1.51) and status.startswith("PUBLISHED")
    assert SA.pula_crawl_rate(2026)[0] is None
    assert "UNMEASURED" in SA.pula_crawl_rate(2026)[1]
    assert SA.pula_crawl_rate(1999)[0] is None
    # Botswana is in SACU and NOT in the Common Monetary Area, and conflating them invents a peg
    assert "bw" in SA.SACU_MEMBERS and "bw" not in SA.CMA_MEMBERS
    assert SA.cma_parity("bw") == "PUBLISHED_BASKET_40_PCT_ZAR"
    assert SA.cma_parity("na") == "EXACT_1_1"
    assert SA.cma_parity("zw") == "NONE" and SA.cma_parity("mz") == "NONE"
    assert SA.is_exact_expression("na")
    assert not SA.is_exact_expression("bw")
    assert not any(SA.is_exact_expression(c) for c in ("zw", "bw", "mz", "ao"))


def test_the_diamond_cycle_and_the_energy_clocks_have_their_own_phases() -> None:
    """Ten cycles a year, labelled APPROXIMATE because De Beers publishes the real calendar; and
    three energy provinces whose phases are dated facts rather than narrative."""
    assert SA.DIAMOND_CYCLES_PER_YEAR == 10
    assert "APPROXIMATE" in SA.DIAMOND_CYCLE_STATUS
    windows = [SA.diamond_cycle_window(2025, n) for n in range(1, 11)]
    assert len(windows) == 10
    for start, end in windows:
        assert start.year == 2025 and end.year == 2025 and start < end
    assert all(windows[i][1] < windows[i + 1][0] for i in range(9)), "cycle windows overlap"
    with pytest.raises(ValueError):
        SA.diamond_cycle_window(2025, 11)
    assert SA.diamond_cycle_index(date(2025, 1, 1)) == 1
    assert SA.diamond_cycle_index(date(2025, 2, 5)) == 2
    assert SA.diamond_cycle_index(date(2025, 12, 31)) == 0, "the year's tail is between cycles"
    # Mozambique's LNG is a supply SCHEDULE and its phases are dated
    assert SA.lng_phase(date(2021, 1, 1)) == "PRE_FORCE_MAJEURE"
    assert SA.lng_phase(date(2021, 5, 1)) == "FORCE_MAJEURE_NO_PRODUCTION"
    assert SA.lng_phase(date(2023, 1, 1)) == "CORAL_SOUTH_ONLY"
    assert SA.lng_phase(date(2026, 1, 1)) == "FORCE_MAJEURE_LIFTED"
    assert SA.MZ_CORAL_FIRST_CARGO.year == 2022 and SA.MZ_CORAL_FIRST_CARGO.month == 11
    # Namibia has no PRODUCTION phase and will not for years -- saying so is the measurement
    assert SA.orange_basin_phase(date(2021, 1, 1)) == "PRE_DISCOVERY"
    assert SA.orange_basin_phase(date(2023, 1, 1)) == "APPRAISAL"
    assert SA.orange_basin_phase(date(2025, 6, 1)) == "APPRAISAL_WITH_IMPAIRMENT"
    assert "PRODUCTION" not in {SA.orange_basin_phase(date(y, 6, 1))
                                for y in (2022, 2023, 2024, 2025, 2026)}


# ------------------------------------------------------------------------------ the cells
def test_the_pack_mints_cells_inside_its_domains_and_not_as_a_cartesian_blow_up() -> None:
    """A cell is only worth a trial if this pack's own data plane can evaluate its CONDITION on
    that SYMBOL, so the cross product is taken INSIDE each domain."""
    rows = SA.cells()
    assert 60 <= len(rows) <= 200, f"{len(rows)} cells is outside the honest range"
    assert len(rows) == len(SA.CELLS)
    assert len({r["cell_id"] for r in rows}) == len(rows), "duplicate cell_id"
    domain_ids = {str(d["id"]) for d in SA.DOMAINS}
    for row in rows:
        for field in ("cell_id", "domain", "symbol", "condition", "mechanism_family",
                      "horizon", "control", "why"):
            assert row[field], f"{row['cell_id']}: {field} is empty"
        assert row["domain"] in domain_ids
        assert row["symbol"] in SA.EXECUTABLE_INSTRUMENTS
        assert set(row["jurisdictions"]) <= set(SA.JURISDICTIONS)
    assert resolve(sorted({r["symbol"] for r in rows}))["equities"] == []
    # every domain mints at least one cell, so no domain is decorative
    assert {r["domain"] for r in rows} == domain_ids
    # and the five headline mechanisms each reach a symbol of their own
    by_symbol = {r["symbol"] for r in rows}
    for must in ("XPTUSD", "XPDUSD", "XAUUSD", "XNGUSD", "XBRUSD", "USDZAR", "XALUSD", "XCUUSD"):
        assert must in by_symbol, f"no cell in this pack reaches {must}"


def test_every_dataset_carries_all_twelve_fields_and_a_fetchable_route() -> None:
    from countries import DATASET_FIELDS
    for ds in SA.DATASETS:
        for field in DATASET_FIELDS:
            if field in ("pit_feasible", "publication_lag_days"):
                continue
            assert ds[field], f"dataset {ds.get('name')!r}: {field} is empty"
        assert float(ds["publication_lag_days"]) >= 0.0
        assert len(str(ds["how_to_fetch"])) > 40, (
            f"dataset {ds['name']!r}: how_to_fetch is not concrete enough for a collector")
        assert resolve(ds["assets"])["equities"] == []
        assert resolve(ds["assets"])["absent"] == []
        assert set(ds) == set(DATASET_FIELDS), (
            f"dataset {ds['name']!r} carries a thirteenth key; `DatasetRow` has no notes slot "
            f"and it would arrive as a coercion note rather than as information")
    # the overwriting pages must be honest about their point-in-time feasibility
    not_pit = {str(d["name"]) for d in SA.DATASETS if not d["pit_feasible"]}
    assert any("Reserve Bank of Zimbabwe" in n for n in not_pit), (
        "the RBZ rate page overwrites in place and cannot be pit_feasible")
    assert any("parallel-market" in n for n in not_pit)


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {f"custom:{name}" for name in SA.MINERS}
    assert all(callable(fn) for fn in got.values())
    ids = {str(d["id"]) for d in SA.DOMAINS}
    entries = set()
    for row in SA.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.southern_africa.pack", row["entry"]
        assert callable(getattr(SA, func)), f"{row['entry']} does not resolve"
        entries.add(func)
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    assert entries == set(SA.MINERS)
    for did in SA.MINER_DOMAINS.values():
        assert set(did) <= ids


def test_mine_returns_a_report_and_emits_nothing_without_a_context() -> None:
    """`mine(None)` is how a test and a fresh session check the pack with nothing wired: it must
    return a report and must not try to record anywhere."""
    report = SA.mine(None)
    assert report["code"] == CODE
    assert tuple(report["jurisdictions"]) == SA.JURISDICTIONS
    assert report["emitted"] == 0, "mine(None) emitted to a registry that does not exist"
    assert report["rows"], "mine(None) produced no rows at all"
    assert report["cells_emitted"] == len(SA.cells())
    assert report["at"].endswith("+00:00"), "the stamp must be timezone-aware UTC"
    assert set(report["miners"]) == set(SA.MINERS)
    assert report["layers_covered"] == 10
    assert report["datasets"] == len(SA.DATASETS)
    assert report["interactions"][0] == "za", (
        "South Africa is the hub of all five and must be the first interaction named")
    assert report["unmeasured"], "no miner declared anything UNMEASURED, which is implausible"
    for row in report["rows"]:
        assert row["kind"] == "hypothesis"
        assert row["symbols"], "a donated row with no instrument compiles to nothing"
        assert resolve(row["symbols"])["absent"] == []
        assert resolve(row["symbols"])["equities"] == []


def test_mine_emits_through_a_context_when_one_is_given() -> None:
    """The same call with a Ctx must hand every row over and count what was taken."""
    class _Ctx:
        def __init__(self) -> None:
            self.rows: list[dict[str, Any]] = []

        def record(self, row: dict[str, Any]) -> None:
            self.rows.append(row)

    ctx = _Ctx()
    report = SA.mine(ctx)
    assert report["emitted"] == len(ctx.rows) == len(report["rows"])
    assert report["emitted"] > 0


def test_the_interactions_name_real_sibling_packs_and_za_comes_first() -> None:
    """An edge whose control lives in a pack nobody runs is an edge nobody can falsify -- and a
    Southern Africa pack that does not name South Africa first has misunderstood the region."""
    from countries import codes
    present = set(codes())
    for row in SA.INTERACTIONS:
        assert row["with"] in present, f"interaction names {row['with']!r}, which is not a pack"
        assert row["mechanism"] and row["observable"] and row["control"]
        assert row["targets"]
    assert SA.INTERACTIONS[0]["with"] == "za", (
        "South Africa is the refining, port, power and financial hub of all five and the ZAR is "
        "the executable proxy for the whole bloc; this pack is its COMPLEMENT and `za` belongs "
        "first")
    named = {r["with"] for r in SA.INTERACTIONS}
    assert "copperbelt" in named, (
        "Beira, Nacala and Lobito carry Copperbelt metal and Kariba powers the Zambian smelters; "
        "neither the routing nor the smelting claim can be made without that pack")
    # THE SIBLINGS THAT ALREADY ANSWER FOR AFRICA MUST NOT BE DUPLICATED. Every country already
    # covered by za, ng, ke, gh, eg, east_africa or copperbelt is NAMED as an interaction or left
    # alone, and none of them is claimed as a jurisdiction of this pack.
    already_answered = {"za", "ng", "ke", "gh", "eg", "et", "tz", "ug", "cd", "zm"}
    assert not (already_answered & set(SA.JURISDICTIONS)), (
        f"this pack claims {sorted(already_answered & set(SA.JURISDICTIONS))}, which a sibling "
        f"pack already answers for")
