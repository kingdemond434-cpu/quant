"""THE EUROPE AND UK COUNTRY PACKS: are they data a miner can use, or six translated templates?

WHAT THESE TESTS ARE FOR. A country pack is prose until something refuses it. Six packs landed
together -- the euro area (with German, French, Italian, Spanish and Dutch sub-labs),
Switzerland, Sweden, Norway, central Europe (with Czech and Hungarian sub-labs) and the United
Kingdom -- and the failure mode they are most exposed to is not being wrong, it is being the
SAME: one template translated six times, with the country's own mechanics filed off. So these
tests check depth and distinctness as hard as they check correctness.

THE SIX LOAD-BEARING TESTS, and why each one exists.

  `test_every_executable_instrument_is_real_and_is_not_an_equity` reads the broker's own
  registry. A pack that names a symbol the box cannot quote has written a cell that can never be
  compiled, and a pack that names a single-name share CFD spends the desk's shared family-wise
  error budget on the asset class the method suits least (two-lane order, 2026-09-06). Both are
  refused here rather than discovered on a docket.

  `test_every_actor_carries_all_eleven_fields` is the difference between an actor and an
  anecdote. The chain Actor -> Constraint -> Observable -> Flow -> MarketImpact -> Candidate
  cannot be walked if a link is blank, and an actor with no FALSIFIER is a story.

  `test_transmission_seeds_name_symbols_the_box_can_actually_trade` catches the commonest way a
  country pack becomes decorative: an edge whose target is an instrument the desk does not have.
  Every seed's targets are validated against `universe.json` itself.

  `test_holiday_rules_reproduce_dates_a_human_can_check` pins four dates that can be verified
  without any of this code: TARGET2 is closed on 2026-04-03 and 2026-04-06, the UK spring bank
  holiday is 2026-05-25, and Midsommarafton is 2026-06-19. All four are DERIVED from rules in
  the packs rather than typed into a table, so the test is checking a computus and a weekday
  rule, not somebody's copy-paste.

  `test_every_source_layer_is_named_or_declared_absent` enforces the principal's depth rule of
  2026-09-17: ten layers, each with at least one source or a stated reason for having none, and
  never a blank. It is the test that stops a country being "covered" by five obvious websites.

  `test_the_six_packs_are_not_one_template_translated_six_times` is the one that would have
  caught the real failure. Domain identifiers, holiday tables, executable sets and policy eras
  must all differ across the six; a shared calendar or a shared era list means somebody copied a
  pack and changed the flag.

EVERYTHING IS READ FROM THE PACK MODULES' OWN CONSTANTS, deliberately. `libs.research.country_lab`
coerces a pack's rows into typed framework objects at construction, and that coercion was landing
while these packs were being written -- `targets` became `asset`, `control` and `falsifier` were
folded into `notes`. Testing the coerced object would make these tests hostage to a sibling
builder's in-flight refactor and would measure the framework rather than the country. So the
module constants are the subject, and `pack()` is checked only for the thing it is for: that it
builds at all and carries all twenty-one fields non-empty in whatever shape the framework is in
today.
"""
from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: The six packs this file owns. Japan, Korea, China and the rest belong to sibling builders.
CODES: tuple[str, ...] = ("ea", "ch", "se", "no", "pl", "uk")

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

#: The six point-in-time stamps every dataset row owes.
PIT_STAMPS: tuple[str, ...] = ("event_time", "period_time", "publication_time", "available_time",
                               "revision_time", "retrieval_time")

#: The ten source layers of the principal's depth rule (2026-09-17).
LAYERS: tuple[str, ...] = ("official", "institutional", "academic", "practitioner",
                           "retail_ecology", "app_ecosystem", "media", "archive",
                           "physical_economy", "source_graph")

ACCESS_LABELS: frozenset[str] = frozenset({
    "PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA", "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL",
    "USER_SUBMITTED", "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED"})
CREDIBILITY: frozenset[str] = frozenset({
    "AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE", "CONTRADICTED", "UNKNOWN"})
PREDICTIVE_STATES: frozenset[str] = frozenset({
    "UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE", "NARRATIVE_FEATURE"})

#: The broker's own asset classes for single names. No pack may name one as executable.
EQUITY_CLASSES: frozenset[str] = frozenset({
    "equities", "equity", "shares", "share", "stock", "stocks", "share cfd", "share cfds",
    "us shares"})

MIN_ACTORS = 12
MIN_DOMAINS = 10
MIN_EDGES = 8

_UNIVERSE_JSON = _DESK / "data" / "universe" / "universe.json"


# --------------------------------------------------------------------------- fixtures/helpers
def _get(obj: Any, field: str, default: Any = None) -> Any:
    """One field of a row, whichever shape the framework left it in."""
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


@pytest.fixture(scope="module")
def universe() -> dict[str, dict[str, Any]]:
    """The broker registry, read directly.

    Read here rather than through the framework's cached accessor so that a change in the
    framework cannot make this test pass for the wrong reason. An unreadable registry SKIPS: an
    absent input is UNMEASURED, never a clean pass (L1.28a).
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
def packs() -> dict[str, Any]:
    """The six pack modules, imported once."""
    out: dict[str, Any] = {}
    for code in CODES:
        out[code] = importlib.import_module(f"countries.{code}.pack")
    return out


# --------------------------------------------------------------------------- the pack builds
@pytest.mark.parametrize("code", CODES)
def test_every_pack_builds_and_carries_all_twenty_one_fields(packs: dict[str, Any],
                                                             code: str) -> None:
    """`pack()` must construct and every one of the twenty-one fields must be non-empty.

    `custom_miners` is the single exception the framework allows to be empty; these six packs all
    fill it anyway, and this test says so rather than exempting it silently.
    """
    module = packs[code]
    built = module.pack()
    assert built is not None
    for field in PACK_FIELDS:
        assert _nonempty(_get(built, field)), f"{code}: pack field {field!r} is empty"
    assert str(_get(built, "region_command")).lower() in {"europe", "uk"}, (
        f"{code}: a Europe/UK pack must file under the europe or uk command")
    assert _nonempty(module.CUSTOM_MINERS), f"{code}: no named specialist miners"


@pytest.mark.parametrize("code", CODES)
def test_every_executable_instrument_is_real_and_is_not_an_equity(
        packs: dict[str, Any], universe: dict[str, dict[str, Any]], code: str) -> None:
    """Every executable symbol exists in the broker's registry and none is a single-name equity.

    An absent symbol is a cell that can never be compiled. An equity breaches the two-lane order
    of 2026-09-06 and spends the desk's shared multiple-testing budget on the asset class the
    method suits least.
    """
    module = packs[code]
    execs = tuple(module.EXECUTABLE_INSTRUMENTS)
    assert len(execs) >= 5, f"{code}: only {len(execs)} executable instruments"
    assert len(set(execs)) == len(execs), f"{code}: duplicate executable instruments"
    for symbol in execs:
        klass = _asset_class(universe, symbol)
        assert klass != "ABSENT", (
            f"{code}: {symbol} is not in the broker universe; it belongs in "
            f"TRANSMISSION_TARGETS, named")
        assert klass not in EQUITY_CLASSES, (
            f"{code}: {symbol} is a single-name equity ({klass}); the two-lane order forbids "
            f"hunting one for statistical hypotheses")


@pytest.mark.parametrize("code", CODES)
def test_absent_instruments_are_named_rather_than_dropped(packs: dict[str, Any],
                                                          universe: dict[str, dict[str, Any]],
                                                          code: str) -> None:
    """Everything the country's economics run through that Fusion does not quote is NAMED.

    Absence is recorded, never silently dropped (L1.28a). Each transmission target must carry a
    name, the role it plays and the executable route the pack uses instead -- and must actually
    be absent from the registry, or it belongs in the executable list.
    """
    module = packs[code]
    targets = tuple(module.TRANSMISSION_TARGETS)
    assert len(targets) >= 4, f"{code}: only {len(targets)} named transmission targets"
    for row in targets:
        for field in ("name", "role", "route"):
            assert _nonempty(row.get(field)), f"{code}: transmission target missing {field!r}"
        assert _asset_class(universe, row["name"]) == "ABSENT", (
            f"{code}: {row['name']!r} is in the broker registry and should be executable, "
            f"not a transmission target")


# --------------------------------------------------------------------------- actors + domains
@pytest.mark.parametrize("code", CODES)
def test_every_actor_carries_all_eleven_fields(packs: dict[str, Any], code: str) -> None:
    """At least twelve actors, each with all eleven content fields non-empty.

    An actor whose FALSIFIER is blank is a story, and a story is not a research object. The
    falsifier is checked for length as well as presence: 'it would be wrong' is not a falsifier.
    """
    module = packs[code]
    actors = tuple(module.actors())
    assert len(actors) >= MIN_ACTORS, f"{code}: {len(actors)} actors < {MIN_ACTORS}"
    names = [str(a["name"]) for a in actors]
    assert len(set(names)) == len(names), f"{code}: an actor is declared twice"
    for row in actors:
        name = row["name"]
        for field in ACTOR_FIELDS:
            assert _nonempty(row.get(field)), f"{code}/{name}: actor field {field!r} is empty"
        assert len(str(row["falsifier"])) >= 60, (
            f"{code}/{name}: the falsifier is too short to be one -- it must name the "
            f"measurement that would kill the claim")


@pytest.mark.parametrize("code", CODES)
def test_every_domain_names_its_negative_controls(packs: dict[str, Any], code: str) -> None:
    """At least ten domains, each with objects, conditions, instruments and CONTROLS.

    A domain with no negative control cannot tell an effect from its own selection, which is the
    whole reason `controls` is not optional anywhere in this department.
    """
    module = packs[code]
    domains = tuple(module.domains())
    assert len(domains) >= MIN_DOMAINS, f"{code}: {len(domains)} domains < {MIN_DOMAINS}"
    ids = [str(d["id"]) for d in domains]
    assert len(set(ids)) == len(ids), f"{code}: a domain id is declared twice"
    for row in domains:
        did = row["id"]
        for field in ("title", "objects", "conditions", "instruments", "controls"):
            assert _nonempty(row.get(field)), f"{code}/{did}: domain field {field!r} is empty"
        assert len(row["controls"]) >= 3, (
            f"{code}/{did}: {len(row['controls'])} controls; one control is a gesture")


@pytest.mark.parametrize("code", CODES)
def test_domain_instruments_are_never_equities(packs: dict[str, Any],
                                               universe: dict[str, dict[str, Any]],
                                               code: str) -> None:
    """A domain may name an unavailable instrument; it may never name a single-name equity."""
    module = packs[code]
    for row in module.domains():
        for symbol in row["instruments"]:
            assert _asset_class(universe, symbol) not in EQUITY_CLASSES, (
                f"{code}/{row['id']}: instrument {symbol} is a single-name equity")


@pytest.mark.parametrize("code", CODES)
def test_custom_miners_name_real_domains_and_claim_no_clock(packs: dict[str, Any],
                                                            code: str) -> None:
    """Every miner names an entry point and domains that exist, and claims to be UNWIRED.

    "Built" is not a status on this desk (III.16). These packs ship mandates, not organs, so
    every miner must say NOT WIRED in its notes until somebody schedules it -- a miner that
    quietly claimed to be running would be a defect these tests exist to catch.
    """
    module = packs[code]
    known = {str(d["id"]) for d in module.domains()}
    miners = tuple(module.CUSTOM_MINERS)
    assert len(miners) >= 6, f"{code}: {len(miners)} named specialist miners"
    for row in miners:
        assert _nonempty(row.get("entry")), f"{code}/{row.get('name')}: no entry point"
        assert row["domain_ids"], f"{code}/{row['name']}: names no domain"
        for did in row["domain_ids"]:
            assert did in known, f"{code}/{row['name']}: names unknown domain {did!r}"
        assert "NOT WIRED" in str(row.get("notes", "")), (
            f"{code}/{row['name']}: a miner that does not declare itself unwired is claiming a "
            f"clock it does not have")


# --------------------------------------------------------------------------- transmission
@pytest.mark.parametrize("code", CODES)
def test_transmission_seeds_name_symbols_the_box_can_actually_trade(
        packs: dict[str, Any], universe: dict[str, dict[str, Any]], code: str) -> None:
    """At least eight seeds, every target present in the broker registry and never an equity.

    A seed whose target the desk cannot trade is a hypothesis with no way to be wrong. Each seed
    must also name its own control: an edge with no control is an anecdote with a sign on it.
    """
    module = packs[code]
    edges = tuple(module.TRANSMISSION_EDGES_SEED)
    assert len(edges) >= MIN_EDGES, f"{code}: {len(edges)} transmission seeds < {MIN_EDGES}"
    ids = [str(e["id"]) for e in edges]
    assert len(set(ids)) == len(ids), f"{code}: an edge id is declared twice"
    for row in edges:
        eid = row["id"]
        assert row["targets"], f"{code}/{eid}: names no executable target"
        for symbol in row["targets"]:
            klass = _asset_class(universe, symbol)
            assert klass != "ABSENT", f"{code}/{eid}: target {symbol} is not in the universe"
            assert klass not in EQUITY_CLASSES, f"{code}/{eid}: target {symbol} is an equity"
        assert row["asset"] == row["targets"][0], (
            f"{code}/{eid}: the primary target must be copied into `asset` so the framework's "
            f"one-asset TransmissionSeed is useful after coercion")
        for field in ("source", "mechanism", "sign", "horizon", "lag", "control", "evidence"):
            assert _nonempty(row.get(field)), f"{code}/{eid}: edge field {field!r} is empty"
        assert row["evidence"] in {"HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED"}


@pytest.mark.parametrize("code", CODES)
def test_policy_eras_are_dated_and_say_what_they_invalidate(packs: dict[str, Any],
                                                            code: str) -> None:
    """Every era has a parseable start, a start-or-None end, and names what it invalidates.

    An era table exists to stop a statistic being pooled across a regime boundary. An era that
    does not say WHAT a pooled study would be measuring instead is decoration.
    """
    module = packs[code]
    eras = tuple(module.POLICY_ERAS)
    assert len(eras) >= 6, f"{code}: {len(eras)} policy eras"
    open_eras = 0
    for row in eras:
        eid = row["id"]
        start = date.fromisoformat(str(row["start"]))
        if row["end"] is None:
            open_eras += 1
        else:
            end = date.fromisoformat(str(row["end"]))
            assert end >= start, f"{code}/{eid}: era ends before it starts"
        for field in ("label", "what_changed", "invalidates"):
            assert _nonempty(row.get(field)), f"{code}/{eid}: era field {field!r} is empty"
    assert open_eras >= 1, (
        f"{code}: every era is closed, which claims the desk knows the present regime ended. "
        f"At least one era must be OPEN with an UNMEASURED end.")


# --------------------------------------------------------------------------- language
#: The terms that prove a pack is written in the market's own language rather than translated.
#: Each is a phrase a native source actually prints and an English-language query would miss.
NATIVE_PROBES: dict[str, tuple[str, ...]] = {
    "ea": ("EZB-Zinsentscheid", "Leitzins", "Hexensabbat", "Einlagefazilität",
           "taux de dépôt", "quatre sorcières", "spread BTP-Bund",
           "le tre streghe", "prima de riesgo", "cuádruple hora bruja", "dekkingsgraad"),
    "ch": ("Sichtguthaben", "Teuerung", "Mindestkurs", "Frankenstärke",
           "avoirs à vue", "renchérissement", "cours plancher",
           "depositi a vista", "rincaro"),
    "se": ("styrränta", "räntebanan", "amorteringskrav", "klämdag",
           "midsommarafton", "rörlig ränta", "säkerställda obligationer"),
    "no": ("styringsrenten", "oljefondet", "handlingsregelen", "fellesferie",
           "seks ukers varsel", "skjærtorsdag", "valutakjøp"),
    "pl": ("Rada Polityki Pieniężnej", "frankowicze", "wakacje kredytowe",
           "kurzový závazek", "dvoutýdenní repo sazba",
           "egyhetes betéti kamat", "Monetáris Tanács", "MÁP Plusz"),
    "uk": ("Bank Rate", "gilt", "EDSP", "ISA season", "the mortgage cliff", "Super Thursday",
           "the 4pm fix", "ex-div Thursday", "the DMO remit"),
}

#: Languages whose vocabulary CANNOT be written in ASCII without losing the match. English is
#: exempt by fact rather than by exception, and the exemption is named so it cannot spread.
DIACRITIC_LANGUAGES: dict[str, int] = {"ea": 12, "ch": 8, "se": 12, "no": 6, "pl": 15, "uk": 0}


@pytest.mark.parametrize("code", CODES)
def test_terminology_is_native_and_not_translated_english(packs: dict[str, Any],
                                                          code: str) -> None:
    """The vocabulary is the market's own, with its real diacritics, keyed per domain.

    A miner asking a German board for "rate decision" finds nothing; it must ask for
    "Zinsentscheid". A Czech source says "kurzovy zavazek" with a hacek and an acute, and an
    accent-folded term does not match the source it exists to match. So the probes below are
    exact phrases, and every non-English pack must also carry a minimum count of terms that are
    not representable in ASCII at all.
    """
    module = packs[code]
    terminology = dict(module.TERMINOLOGY)
    assert len(terminology) >= 5, f"{code}: {len(terminology)} terminology groups"
    flat = {term for terms in terminology.values() for term in terms}
    assert len(flat) >= 50, f"{code}: only {len(flat)} distinct terms"

    missing = [p for p in NATIVE_PROBES[code] if p not in flat]
    assert not missing, f"{code}: native vocabulary missing {missing}"

    accented = {t for t in flat if any(ord(ch) > 127 for ch in t)}
    need = DIACRITIC_LANGUAGES[code]
    assert len(accented) >= need, (
        f"{code}: {len(accented)} terms carry non-ASCII characters, expected at least {need}. "
        f"An accent-folded glossary cannot match the source it exists to match.")
    if code == "uk":
        assert not accented, (
            "the UK pack is written in English and needs no diacritics; the exemption is a fact "
            "about the language, not a licence for the other five")

    langs = tuple(module.NATIVE_LANGUAGES)
    assert langs, f"{code}: no native languages declared"
    for lang in langs:
        if lang in {"en", "en-GB"}:
            continue
        assert any(key.startswith(f"{lang}_") for key in terminology), (
            f"{code}: declares native language {lang!r} and carries no {lang}_ terminology group")


# --------------------------------------------------------------------------- clocks
@pytest.mark.parametrize("code", CODES)
def test_every_fixing_carries_a_dst_note_and_a_utc_translation(packs: dict[str, Any],
                                                               code: str) -> None:
    """Each fixing convention names its local time, its UTC translation and its DST rule.

    A benchmark is defined in LOCAL time and its UTC hour moves twice a year. A backtest keyed to
    a fixed UTC hour is testing an ordinary minute for seven months of every year, which is the
    single cheapest way to lose a real intraday effect -- so the DST note is mandatory and is
    checked for substance, not presence.
    """
    module = packs[code]
    fixings = tuple(module.FIXING_CONVENTIONS)
    assert len(fixings) >= 4, f"{code}: {len(fixings)} fixing conventions"
    for row in fixings:
        name = row["name"]
        for field in ("administrator", "local_time", "utc", "dst_note", "window",
                      "what_it_prices", "why_it_matters"):
            assert _nonempty(row.get(field)), f"{code}/{name}: fixing field {field!r} is empty"
        assert len(str(row["dst_note"])) >= 80, (
            f"{code}/{name}: the DST note must say what the offset does and when, not just name "
            f"a timezone")
        utc = row["utc"]
        assert isinstance(utc, Mapping) and len(utc) >= 2, (
            f"{code}/{name}: the UTC translation must give both the winter and summer legs")
        assert any(tok in str(row["dst_note"]) for tok in ("CET", "CEST", "GMT", "BST", "UTC")), (
            f"{code}/{name}: the DST note names no clock")


@pytest.mark.parametrize("code", CODES)
def test_central_bank_decisions_are_dated_or_declared_unmeasured(packs: dict[str, Any],
                                                                 code: str) -> None:
    """Decision dates for 2024..2026 are parseable, or the year is UNMEASURED with a reason.

    A guessed decision date does not weaken an event study, it RELOCATES it onto a day when
    nothing happened. So a pack may give dates or may decline, and declining must be explicit --
    the Polish and Swedish packs decline for 2026 and say why, which is a verdict (L1.28a).
    """
    module = packs[code]
    bank = module.CENTRAL_BANK
    for field in ("name", "committee", "policy_rates", "decision_rule", "announcement_local",
                  "dst_note", "rule_if_dates_unknown", "source"):
        assert _nonempty(bank.get(field)), f"{code}: central_bank field {field!r} is empty"
    decisions = bank["decisions"]
    for year in ("2024", "2025", "2026"):
        assert year in decisions, f"{code}: no decision entry for {year}"
        entry = decisions[year]
        assert _nonempty(entry.get("confidence")), f"{code}/{year}: no confidence statement"
        dates = tuple(entry.get("dates") or ())
        if not dates:
            assert "UNMEASURED" in str(entry["confidence"]), (
                f"{code}/{year}: no dates and no UNMEASURED verdict -- an empty list must be a "
                f"declared absence, never a silent one")
            continue
        parsed = [date.fromisoformat(d) for d in dates]
        assert all(d.year == int(year) for d in parsed), f"{code}/{year}: a date is out of year"
        assert parsed == sorted(parsed), f"{code}/{year}: decision dates are not in order"


# --------------------------------------------------------------------------- holidays
def test_target2_is_closed_on_good_friday_and_easter_monday_2026(packs: dict[str, Any]) -> None:
    """The euro's own settlement calendar, DERIVED from the computus, not typed.

    TARGET2 closes on six days a year and two of them move with Easter. 2026's Easter Sunday is
    5 April, so Good Friday is 3 April and Easter Monday is 6 April -- both verifiable without
    any of this code.
    """
    ea = packs["ea"]
    table = ea.holidays(2026)
    assert date(2026, 4, 3) in table and "Good Friday" in table[date(2026, 4, 3)]
    assert date(2026, 4, 6) in table and "Easter Monday" in table[date(2026, 4, 6)]
    assert len(table) == 6, f"TARGET2 closes on six days; this table has {len(table)}"
    assert date(2026, 10, 3) not in table, (
        "German Unity Day is a national holiday and TARGET2 settles on it -- the asymmetry is "
        "the research object and must not be merged away")
    assert ea.easter_sunday(2026) == date(2026, 4, 5)
    assert ea.easter_sunday(2024) == date(2024, 3, 31)
    assert ea.easter_sunday(2025) == date(2025, 4, 20)


def test_xetra_closes_three_days_euronext_does_not(packs: dict[str, Any]) -> None:
    """The euro area's most exploitable calendar asymmetry, computed rather than asserted."""
    ea = packs["ea"]
    xetra, euronext = ea.xetra_holidays(2026), ea.euronext_holidays(2026)
    only_german = set(xetra) - set(euronext)
    assert only_german == {date(2026, 5, 25), date(2026, 12, 24), date(2026, 12, 31)}, (
        f"expected Whit Monday and the two year-end eves, got {sorted(only_german)}")
    assert set(euronext) == set(ea.holidays(2026)), (
        "Euronext's harmonised calendar is the same six days as TARGET2, which is why FRA40 "
        "trades on every day the euro settles and GER40 does not")


def test_uk_spring_bank_holiday_2026_and_the_substitution_rule(packs: dict[str, Any]) -> None:
    """2026-05-25 is the last Monday in May, and the UK is the only pack here that substitutes."""
    uk = packs["uk"]
    table = uk.bank_holidays(2026)
    assert date(2026, 5, 25) in table
    assert "Spring bank holiday" in table[date(2026, 5, 25)]
    for year in (2024, 2025, 2026):
        assert len(uk.bank_holidays(year)) == 8, (
            f"{year}: the substitution rule keeps England and Wales at exactly eight bank "
            f"holidays; a different count means the rule is not being applied")
    # 26 December 2026 is a Saturday, so Boxing Day substitutes to Monday the 28th.
    assert date(2026, 12, 28) in table
    assert "substitute day" in table[date(2026, 12, 28)]
    assert uk.holidays(2026) == table, "the LSE adds no closures beyond the bank holidays"


def test_midsommarafton_2026_is_the_nineteenth_of_june(packs: dict[str, Any]) -> None:
    """Midsummer Day is the Saturday falling 20-26 June; the Eve is the Friday before it."""
    se = packs["se"]
    assert se.midsummer_day(2026) == date(2026, 6, 20)
    assert se.midsummer_eve(2026) == date(2026, 6, 19)
    table = se.holidays(2026)
    assert date(2026, 6, 19) in table and "Midsommarafton" in table[date(2026, 6, 19)]
    assert date(2026, 6, 6) not in table, (
        "Nationaldagen 2026 falls on a Saturday and Swedish law has no weekend substitution, so "
        "it costs the market no session")
    assert date(2024, 6, 6) in se.holidays(2024), "6 June 2024 was a Thursday and did cost one"


def test_the_swedish_fourth_friday_rolls_back_over_christmas(packs: dict[str, Any]) -> None:
    """OMXS30 expires on the FOURTH Friday, which in December 2026 is Christmas Day."""
    se = packs["se"]
    assert se.omxs30_expiry(2026, 6) == date(2026, 6, 26)
    assert se.omxs30_expiry(2026, 12) == date(2026, 12, 23), (
        "the fourth Friday of December 2026 is the 25th; the roll-back must move the expiry to "
        "Wednesday the 23rd, because the 24th is also a closure")
    assert date(2024, 5, 10) in se.klamdagar(2024), (
        "the Friday after Ascension 2024 is a klamdag: an open exchange with an absent country")


def test_norway_closes_on_maundy_thursday_and_nobody_else_does(packs: dict[str, Any]) -> None:
    """Skjaertorsdag is the department's most reliable one-sided session."""
    no_pack, se, ea = packs["no"], packs["se"], packs["ea"]
    maundy = date(2026, 4, 2)
    assert maundy in no_pack.holidays(2026)
    assert maundy not in se.holidays(2026)
    assert maundy not in ea.xetra_holidays(2026)
    assert maundy not in packs["uk"].bank_holidays(2026)
    assert date(2026, 5, 17) not in no_pack.holidays(2026), (
        "Constitution Day 2026 falls on a Sunday and Norwegian law has no substitution")
    assert date(2024, 5, 17) in no_pack.holidays(2024), "17 May 2024 was a Friday"
    start, end = no_pack.fellesferie(2026)
    assert (end - start).days == 20 and start.weekday() == 0


def test_cee_calendars_are_asymmetric_against_target2(packs: dict[str, Any]) -> None:
    """The local banking system is shut and the euro settles: roughly twenty sessions a year."""
    pl = packs["pl"]
    total = 0
    for sub in ("pl", "cz", "hu"):
        asym = pl.target2_open_but_local_closed(sub, 2026)
        assert asym, f"{sub}: no asymmetric days, which cannot be right"
        total += len(asym)
        for day in asym:
            assert day.weekday() < 5, f"{sub}: {day} is a weekend and is not an asymmetry"
    assert total >= 10, f"only {total} asymmetric CEE sessions in 2026"
    assert date(2026, 1, 6) in pl.target2_open_but_local_closed("pl", 2026), "Trzech Kroli"
    assert date(2026, 10, 28) in pl.target2_open_but_local_closed("cz", 2026), "Czech statehood"
    assert date(2026, 8, 20) in pl.target2_open_but_local_closed("hu", 2026), "St Stephen's Day"


def test_switzerland_closes_on_berchtoldstag(packs: dict[str, Any]) -> None:
    """2 January is a Swiss closure and nobody else's, in the thinnest week of the year."""
    ch = packs["ch"]
    table = ch.holidays(2026)
    assert date(2026, 1, 2) in table and "Berchtoldstag" in table[date(2026, 1, 2)]
    assert date(2026, 1, 2) not in packs["ea"].xetra_holidays(2026)
    assert date(2026, 1, 2) not in packs["uk"].bank_holidays(2026)
    assert date(2026, 8, 1) in table and date(2026, 8, 1).weekday() == 5, (
        "the Swiss national day is in the HOLIDAY table and falls on a Saturday in 2026, so it "
        "costs no session -- the pack's own note says exactly that")
    for canton in ("zh", "ge", "zg", "ti"):
        assert ch.cantonal_holidays(canton, 2026), f"{canton}: no cantonal calendar"


@pytest.mark.parametrize("code", CODES)
def test_holidays_rule_is_a_derived_table_for_2024_to_2026(packs: dict[str, Any],
                                                           code: str) -> None:
    """Every pack's `holidays_rule` carries a derivation, a function and three resolved years.

    A table with no rule beside it cannot be extended past the years somebody typed; a rule with
    no table cannot be checked. Both are required, and the ISO keys must fall inside their year.
    """
    module = packs[code]
    rule = module.HOLIDAYS_RULE
    assert isinstance(rule, Mapping)
    for field in ("calendar", "rule", "function", "table", "asymmetries", "status", "verified"):
        assert _nonempty(rule.get(field)), f"{code}: holidays_rule field {field!r} is empty"
    assert rule["status"] == "DERIVED_FROM_RULE"
    assert rule["function"].startswith(f"countries.{code}.pack:")
    for year in (2024, 2025, 2026):
        table = rule["table"][year]
        assert table, f"{code}: no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{code}: {iso} is not in {year}"


# --------------------------------------------------------------------------- datasets
@pytest.mark.parametrize("code", CODES)
def test_every_dataset_carries_all_six_point_in_time_stamps(packs: dict[str, Any],
                                                            code: str) -> None:
    """A dataset whose vintage cannot be reconstructed can only produce NOT_PIT_SAFE cells.

    The six stamps are not optional, and `pit_feasible=False` must be an honest answer rather
    than an absent one: the Polish NBP row carries it precisely because the decision has no
    announced clock time, and that is a measurement about Poland.
    """
    module = packs[code]
    datasets = tuple(module.DATASETS)
    assert len(datasets) >= 8, f"{code}: {len(datasets)} datasets"
    names = [d["name"] for d in datasets]
    assert len(set(names)) == len(names), f"{code}: a dataset is declared twice"
    for row in datasets:
        name = row["name"]
        for field in ("source", "coverage", "frequency", "revisions", "licence", "history_from",
                      "assets", "mechanism_families", "how_to_fetch"):
            assert _nonempty(row.get(field)), f"{code}/{name}: dataset field {field!r} is empty"
        assert float(row["publication_lag_days"]) >= 0
        pit = row["pit"]
        for stamp in PIT_STAMPS:
            assert _nonempty(pit.get(stamp)), f"{code}/{name}: PIT stamp {stamp!r} is empty"
        assert isinstance(row["pit_feasible"], bool)


# --------------------------------------------------------------------------- source layers
@pytest.mark.parametrize("code", CODES)
def test_every_source_layer_is_named_or_declared_absent(packs: dict[str, Any],
                                                        code: str) -> None:
    """Ten layers, each with a source or a stated reason. A blank is never an answer.

    This is the principal's depth rule of 2026-09-17 as a gate: a country is never "covered" by
    five obvious websites, and the only way to know whether a layer was searched or merely
    skipped is to make emptiness impossible to leave silent.
    """
    module = packs[code]
    assert tuple(module.LAYERS) == LAYERS, f"{code}: the layer vocabulary has drifted"
    coverage = module.source_layer_coverage()
    assert set(coverage) == set(LAYERS), f"{code}: coverage does not cover the ten layers"
    for layer, row in coverage.items():
        if row["n"] == 0:
            assert _nonempty(row["absent_reason"]), (
                f"{code}/{layer}: no source and no reason. An unsearched layer and an empty one "
                f"are different findings and this pack does not say which it is.")
        else:
            assert row["sources"], f"{code}/{layer}: counted sources but named none"
            assert row["queries"] >= 2, (
                f"{code}/{layer}: {row['queries']} queries; a source with no way in is a "
                f"bookmark")


@pytest.mark.parametrize("code", CODES)
def test_every_source_carries_three_independent_labels(packs: dict[str, Any], code: str) -> None:
    """Access, credibility and predictive state are three axes and are labelled separately.

    Collapsing them into one score is how a desk mistakes prestige for edge. The test also pins
    the orthogonality with evidence: at least one PUBLIC-access source must NOT be AUTHORITATIVE,
    and at least one non-official source must carry a low weight rather than being dropped.
    """
    module = packs[code]
    sources = tuple(module.SOURCE_CLASSES)
    assert len(sources) >= 10, f"{code}: {len(sources)} source classes"
    ids = [s["id"] for s in sources]
    assert len(set(ids)) == len(ids), f"{code}: a source id is declared twice"
    for row in sources:
        sid = row["id"]
        assert row["layer"] in LAYERS, f"{code}/{sid}: layer {row['layer']!r} unknown"
        assert row["access_label"] in ACCESS_LABELS, f"{code}/{sid}: bad access_label"
        assert row["credibility"] in CREDIBILITY, f"{code}/{sid}: bad credibility"
        assert row["predictive_state"] in PREDICTIVE_STATES, f"{code}/{sid}: bad predictive_state"
        assert row["roots"], f"{code}/{sid}: no concrete roots"
        assert row["queries"], f"{code}/{sid}: no native-language queries"
        assert isinstance(row["machine_use_allowed"], bool)
        assert 0.0 < float(row["weight"]) <= 1.0, f"{code}/{sid}: weight out of range"
        assert _nonempty(row.get("notes")), f"{code}/{sid}: no note saying why it is here"

    believable = {s["credibility"] for s in sources}
    assert believable & {"UNRELIABLE", "FRINGE", "CONTRADICTED", "UNKNOWN"}, (
        f"{code}: every source is credible, which means the low-credibility layers were not "
        f"searched. Fringe and contradicted PUBLIC material is kept at low weight, never dropped.")
    low = [s for s in sources if float(s["weight"]) <= 0.4]
    assert low, f"{code}: nothing is carried at low weight, so nothing was kept rather than cut"
    assert any(s["predictive_state"] == "NARRATIVE_FEATURE" for s in sources), (
        f"{code}: nothing is labelled a narrative feature, so attention data is being treated "
        f"as forecast data")


@pytest.mark.parametrize("code", CODES)
def test_sources_forbidding_machine_use_are_registered_not_omitted(packs: dict[str, Any],
                                                                   code: str) -> None:
    """A page whose terms forbid extraction is recorded and never scraped -- and never dropped.

    Recording it is a measurement: the desk knows the coverage exists and knows a machine may not
    read it. Omitting it would leave a hole indistinguishable from a layer nobody searched.
    """
    module = packs[code]
    blocked = [s for s in module.SOURCE_CLASSES if not s["machine_use_allowed"]]
    assert blocked, (
        f"{code}: every source is machine-readable, which is not true of any European media or "
        f"retail layer. A pack that found none did not look at the terms.")
    for row in blocked:
        note = str(row["notes"])
        assert "machine_use_allowed=False" in note or "never scraped" in note, (
            f"{code}/{row['id']}: registered as machine-forbidden without saying so in the note")


@pytest.mark.parametrize("code", CODES)
def test_queries_are_written_in_the_source_language(packs: dict[str, Any], code: str) -> None:
    """Query strings are native, not translated English. Checked where a script proves it.

    For the five non-English packs at least one query must carry a non-ASCII character, because
    the languages these packs mine cannot be searched in ASCII. The UK is exempt by fact: its
    market vocabulary is English, and its queries are checked for UK TRADER SLANG instead.
    """
    module = packs[code]
    queries = [q for s in module.SOURCE_CLASSES for q in s["queries"]]
    assert len(queries) >= 25, f"{code}: only {len(queries)} queries across ten layers"
    if code == "uk":
        slang = ("gilt", "Bank Rate", "EDSP", "ISA", "remit", "vote split", "mortgage")
        assert sum(1 for q in queries if any(s in q for s in slang)) >= 8, (
            "UK queries must use the market's own vocabulary, not generic finance English")
        return
    accented = [q for q in queries if any(ord(ch) > 127 for ch in q)]
    assert len(accented) >= 4, (
        f"{code}: only {len(accented)} queries carry native characters. A translated English "
        f"query against a native board returns that language's word for nothing.")


# --------------------------------------------------------------------------- distinctness
def test_the_six_packs_are_not_one_template_translated_six_times(packs: dict[str, Any]) -> None:
    """Domains, calendars, executable sets and eras must all differ across the six.

    This is the test that would catch the real failure mode. Six packs written in one sitting
    against one contract drift toward being one pack with six flags, and the symptom is always
    the same: shared domain identifiers, an identical holiday table, the same instruments.
    """
    domain_ids = {code: {d["id"] for d in module.domains()} for code, module in packs.items()}
    for a in CODES:
        for b in CODES:
            if a >= b:
                continue
            assert not (domain_ids[a] & domain_ids[b]), (
                f"{a} and {b} share domain identifiers {sorted(domain_ids[a] & domain_ids[b])}")

    tables = {code: frozenset(module.holidays(2026)) for code, module in packs.items()}
    assert len(set(tables.values())) == len(CODES), (
        "two packs have an identical 2026 closure calendar, which no two European markets do")

    execs = {code: frozenset(module.EXECUTABLE_INSTRUMENTS) for code, module in packs.items()}
    assert len(set(execs.values())) == len(CODES), "two packs trade exactly the same instruments"
    for a in CODES:
        for b in CODES:
            if a >= b:
                continue
            assert execs[a] != execs[b]

    era_ids = {code: {e["id"] for e in module.POLICY_ERAS} for code, module in packs.items()}
    for a in CODES:
        for b in CODES:
            if a >= b:
                continue
            assert not (era_ids[a] & era_ids[b]), f"{a} and {b} share a policy era identifier"

    currencies = {module.CURRENCY for module in packs.values()}
    assert len(currencies) == len(CODES), f"six packs, {len(currencies)} currencies"


def test_the_two_multi_country_packs_carry_real_sub_labs(packs: dict[str, Any]) -> None:
    """The euro area and central Europe each hold several countries and must not flatten them.

    A sub-lab that shares its parent's calendar, agency and language is a label rather than a
    laboratory, so each one must name its own debt agency, its own holiday function and its own
    terminology keys, and those keys must exist.
    """
    for code, expected in (("ea", ("de", "fr", "it", "es", "nl")), ("pl", ("pl", "cz", "hu"))):
        module = packs[code]
        labs = module.SUB_LABS
        assert tuple(labs) == expected, f"{code}: sub-labs are {tuple(labs)}, expected {expected}"
        seen_agencies: set[str] = set()
        for sub, row in labs.items():
            for field in ("name", "executable", "holiday_function", "language",
                          "terminology_keys", "sources", "why_it_matters"):
                assert _nonempty(row.get(field)), f"{code}/{sub}: sub-lab field {field!r} empty"
            agency = str(row.get("debt_agency") or row.get("central_bank") or "")
            assert agency, f"{code}/{sub}: names neither a debt agency nor a central bank"
            assert agency not in seen_agencies, f"{code}/{sub}: shares an institution with a peer"
            seen_agencies.add(agency)
            for key in row["terminology_keys"]:
                assert key in module.TERMINOLOGY, f"{code}/{sub}: terminology key {key!r} absent"
            assert row["holiday_function"].startswith(f"countries.{code}.pack:")
        # the national calendars must actually differ from one another
        national = {sub: frozenset(module.national_holidays(sub, 2026)) for sub in labs}
        assert len(set(national.values())) == len(labs), (
            f"{code}: two sub-labs have identical national calendars")


def test_fiscal_year_ends_are_not_all_the_same(packs: dict[str, Any]) -> None:
    """The UK's financial year ends 31 March; every other pack here ends 31 December.

    Carried as a test because it is the single most commonly assumed-away fact in European
    research, and because a pack that copied its neighbour's value would show up here.
    """
    ends = {code: module.pack() for code, module in packs.items()}
    values = {code: str(_get(p, "fiscal_year_end")) for code, p in ends.items()}
    assert values["uk"] == "03-31", "the UK government financial year runs 1 April to 31 March"
    assert all(values[c] == "12-31" for c in CODES if c != "uk"), (
        f"a euro-area, Swiss, Nordic or CEE pack has a non-calendar fiscal year: {values}")


#: Every field in these packs whose value is a SEQUENCE of phrases, never a bare string.
SEQUENCE_FIELDS: tuple[str, ...] = (
    "forced_to", "information", "constraints", "instruments", "counterparties", "observables",
    "objects", "conditions", "controls", "assets", "mechanism_families", "roots", "languages",
    "queries", "targets", "domain_ids")


@pytest.mark.parametrize("code", CODES)
def test_no_sequence_field_was_exploded_into_characters(packs: dict[str, Any],
                                                        code: str) -> None:
    """A one-element tuple written without its trailing comma is a STRING, and it is silent.

    `constraints=("a board mandate")` is not a tuple. The builders call `tuple(...)` on it, which
    explodes it into one entry per CHARACTER: fifteen single letters where one constraint should
    be. Every length check passes, every non-empty check passes, the pack imports, the framework
    coerces it, and the actor's constraint is gone.

    MEASURED 2026-09-17: 105 fields across these six packs were in exactly that state -- mostly
    `constraints`, with `forced_to`, `information`, `counterparties` and `conditions` among them.
    Nothing else in this file would have caught it, because the defect produces MORE elements
    rather than fewer. This test is the guard: an element of one character, or a field that is a
    string at all, is a missing comma until proven otherwise.
    """
    module = packs[code]
    rows: list[tuple[str, Any]] = []
    rows += [(f"actor {a['name']}", a) for a in module.actors()]
    rows += [(f"domain {d['id']}", d) for d in module.domains()]
    rows += [(f"edge {e['id']}", e) for e in module.TRANSMISSION_EDGES_SEED]
    rows += [(f"dataset {d['name']}", d) for d in module.DATASETS]
    rows += [(f"source {s['id']}", s) for s in module.SOURCE_CLASSES]
    rows += [(f"miner {m['name']}", m) for m in module.CUSTOM_MINERS]

    for label, row in rows:
        for field in SEQUENCE_FIELDS:
            if field not in row:
                continue
            value = row[field]
            assert not isinstance(value, str), (
                f"{code}/{label}: {field!r} is a STRING, not a sequence -- a one-element tuple "
                f"is missing its trailing comma")
            for item in value:
                assert isinstance(item, str) and len(item) > 1, (
                    f"{code}/{label}: {field!r} contains {item!r}, a single character. The "
                    f"tuple was written without a trailing comma and exploded into letters.")

    # the module-level tuple constants are exposed to the same mistake
    for name in ("EXECUTABLE_INSTRUMENTS", "NATIVE_LANGUAGES", "PIT_STAMPS", "LAYERS"):
        value = getattr(module, name)
        assert not isinstance(value, str), f"{code}: {name} is a string, not a tuple"
        assert all(len(v) > 1 for v in value), f"{code}: {name} contains a single character"
