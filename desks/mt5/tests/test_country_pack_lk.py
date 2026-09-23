"""THE SRI LANKA COUNTRY PACK: is it a research object, or a brochure?

WHAT THIS FILE IS FOR. `research/countries/lk` is DATA, and data that nothing checks rots in a
specific and predictable way: an actor loses its falsifier and becomes a story, a domain loses
its controls and becomes a correlation, an instrument the broker does not quote creeps into the
executable list and compiles cells that can never be filled, a terminology table quietly becomes
an English glossary, and a twenty-source layer map shrinks to the five obvious websites. Every
assertion below is aimed at one of those.

THE SIX THAT ARE LOAD-BEARING HERE, and why each earns its place for THIS country:

  1. EVERY SYMBOL IS CHECKED AGAINST THE BROKER'S OWN REGISTRY. The rupee is not quoted, the
     ASPI has no CFD, the restructured bonds are OTC and there is NO TEA CONTRACT ANYWHERE. So
     the whole pack routes outward through softs, energy, metals, the regional crosses and the
     frontier rate, and a test that did not check the registry would let it promise USDLKR and
     produce nothing. The two-lane order (2026-09-06) also forbids any single-name equity, and
     Sri Lankan market commentary is company-heavy enough that this is a live risk.

  2. ELEVEN FIELDS PER ACTOR, AND THE FALSIFIER IS ONE OF THEM. The chain actor -> constraint ->
     observable -> flow -> market impact -> candidate cannot be walked through a gap.

  3. SINHALA AND TAMIL, IN ACTUAL SCRIPT. Both are official languages and they do not cover the
     same ground: the plantation districts and the north read Tamil, the south reads Sinhala,
     and English reaches only the Colombo professional corner. A miner searching for "fuel
     price" finds Daily FT; one searching for "ඉන්ධන මිල" finds the queue. Both scripts are
     asserted in the terminology AND in at least one source layer's queries, because a pack can
     have a bilingual glossary and a monolingual crawler.

  4. TEN SOURCE LAYERS, EACH POPULATED. The principal's depth rule of 2026-09-17: a country is
     never "covered" by five obvious sources. This pack declares NO layer absent, so all ten
     must actually carry a source.

  5. DEPTH IS THE FRAMEWORK'S VERDICT, NOT THE PACK'S. `regional_parity.pack_depth` measures
     what `CountryPack` carries AFTER coercion, and `coercion_notes` must be empty -- a pack
     that hands the framework a field it has no slot for is silently losing that field.

  6. ONE HOLIDAY DATE A HUMAN CAN CHECK. Sinhala and Tamil New Year Day 2026 is 14 April, with
     the 13th as the day prior. Sri Lanka's calendar is the pack's own mechanism -- a lunar
     MONTHLY market closure exists nowhere else in the desk's book -- so the table is asserted
     by value rather than by shape.

NOTHING HERE WRITES A TRACKED FILE. The pack is pure data and the miners are resolved but never
run, so this file needs no fixture beyond the ones pytest hands it.
"""
from __future__ import annotations

import sys
from datetime import date
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.countries import (  # noqa: E402
    ACTOR_FIELDS,
    DATASET_FIELDS,
    EDGE_EVIDENCE,
    PACK_FIELDS,
    check_pack,
    holiday_table,
    is_equity,
    resolve,
    universe_symbols,
)

CODE = "lk"

#: The ten source layers of the principal's depth rule (2026-09-17).
LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology",
    "app_ecosystem", "media", "archive", "physical_economy", "source_graph")
ACCESS_LABELS: frozenset[str] = frozenset({
    "PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA", "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL",
    "USER_SUBMITTED", "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED"})
CREDIBILITY: frozenset[str] = frozenset({
    "AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE", "CONTRADICTED", "UNKNOWN"})
PREDICTIVE: frozenset[str] = frozenset({
    "UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE", "NARRATIVE_FEATURE"})

#: `research.countries.has_script` knows han, hangul and kana -- the East Asia builder's three.
#: Sri Lanka writes in two the shared module has never needed, so they are declared here rather
#: than by editing a module three other builders are working in.
SCRIPTS: dict[str, tuple[tuple[int, int], ...]] = {
    "sinhala": ((0x0D80, 0x0DFF),),
    "tamil": ((0x0B80, 0x0BFF),),
}

#: The five miners the pack registers. Both registrations -- `CUSTOM_MINERS[*]["entry"]` and
#: `MINERS` -- must name the same five, or a miner the pack believes it runs never runs.
MINER_NAMES: tuple[str, ...] = (
    "cbsl_policy_windows", "poya_closure_eves", "tea_auction_week", "fuel_formula_month",
    "transmission_seeds")


def has_script(text: str, script: str) -> bool:
    """True when `text` carries at least one codepoint of the named script."""
    ranges = SCRIPTS[script]
    return any(any(lo <= ord(ch) <= hi for lo, hi in ranges) for ch in str(text))


def pack_module() -> Any:
    return import_module(f"research.countries.{CODE}.pack")


def fields() -> dict[str, Any]:
    """The pack as WRITTEN. Content is asserted against this rather than against the coerced
    `CountryPack`, because the framework's row classes do not carry `control`, `falsifier` or
    `condition` by those names and a test that read the adapter would be testing the adapter."""
    out = pack_module().as_dict()
    assert isinstance(out, dict)
    return out


def country_lab() -> Any:
    return import_module("libs.research.country_lab")


def built_pack() -> Any:
    """The pack through the framework's own resolver -- the object every miner actually sees."""
    got = country_lab().resolve_pack(CODE)
    assert got is not None, "libs.research.country_lab.resolve_pack found no pack for 'lk'"
    return got


# --------------------------------------------------------------------------- shape
def test_pack_resolves_and_carries_every_field() -> None:
    data = fields()
    for field in PACK_FIELDS:
        assert data.get(field), f"{field}: empty; every country pack owes all twenty-one fields"
    assert data["code"] == "LK"
    assert data["region_command"] == "asia"
    assert data["currency"] == "LKR"
    built = built_pack()
    assert built.code == "lk"
    assert built.name == "Sri Lanka"


def test_check_pack_is_clean() -> None:
    problems = check_pack(fields())
    assert problems == [], f"check_pack found {len(problems)} problem(s): {problems[:8]}"


def test_no_coercion_notes() -> None:
    """A note here means the pack handed `CountryPack` a field it has no slot for, and that
    field is then silently absent from everything the framework's miners read."""
    notes = list(getattr(built_pack(), "coercion_notes", ()) or ())
    assert notes == [], f"{len(notes)} coercion note(s): {notes[:6]}"


def test_validate_pack_has_no_fatal_problem() -> None:
    lab = country_lab()
    fatal = list(lab.fatal_problems(lab.validate_pack(built_pack())))
    assert fatal == [], f"validate_pack FATAL: {fatal[:6]}"


# --------------------------------------------------------------------------- depth
def test_depth_score_is_one() -> None:
    parity = import_module("libs.research.regional_parity")
    row = parity.pack_depth(built_pack(), CODE).as_row()
    assert row["score"] == 1.0, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0, "a layer nobody mapped is not coverage"
    assert row["untagged_sources"] == 0, "a source that reaches the framework untagged is a hole"
    for key, target in parity.DEPTH_TARGETS.items():
        if key == "layers":
            continue
        assert row[key] >= target, f"{key}: {row[key]} < {target}"


def test_parity_with_the_template_pack() -> None:
    """Equal depth, not minimally over the bar. Pakistan is the validated reference on this
    desk; Sri Lanka is measured against it rather than against the floor."""
    parity = import_module("libs.research.regional_parity")
    lk = parity.pack_depth(built_pack(), CODE).as_row()
    for key, floor in (("actors", 13), ("domains", 13), ("edges", 9), ("datasets", 12),
                       ("eras", 5), ("instruments", 14), ("terms", 120)):
        assert lk[key] >= floor, f"{key}: {lk[key]} < the reference pack's {floor}"


# --------------------------------------------------------------------------- the broker
def test_every_executable_instrument_is_a_real_non_equity_symbol() -> None:
    known = universe_symbols()
    assert known, "the broker universe is unreadable -- UNMEASURED, so nothing has been checked"
    split = resolve(fields()["executable_instruments"])
    assert split["absent"] == [], f"not in the broker universe: {split['absent']}"
    assert split["equities"] == [], (
        f"single-name equities in executable_instruments: {split['equities']}; the two-lane "
        f"order (2026-09-06) forbids hunting them for statistical hypotheses")
    assert len(split["tradable"]) >= 6


def test_every_edge_target_is_a_real_non_equity_symbol() -> None:
    for edge in fields()["transmission_edges_seed"]:
        targets = tuple(edge["targets"])
        assert targets, f"edge {edge['id']}: names no executable target"
        split = resolve(targets)
        assert split["absent"] == [], f"edge {edge['id']}: absent target(s) {split['absent']}"
        assert split["equities"] == [], f"edge {edge['id']}: equity target(s) {split['equities']}"
        assert edge["evidence"] in EDGE_EVIDENCE
        for key in ("mechanism", "control", "falsifier", "actor", "sign"):
            assert str(edge.get(key) or "").strip(), f"edge {edge['id']}: {key} is empty"


def test_no_domain_or_actor_names_an_equity() -> None:
    data = fields()
    for row in tuple(data["domains"]) + tuple(data["actors"]):
        for sym in row["instruments"]:
            assert not is_equity(sym), f"{row.get('id') or row.get('name')}: {sym} is an equity"


def test_the_absent_instruments_are_named_rather_than_promised() -> None:
    """LKR, the ASPI and the tea auction have no symbol here. The pack must carry each as a
    TRANSMISSION TARGET with the broker symbols its mechanism reaches -- an absent instrument
    produces a hypothesis, never a cell that can never be filled (L1.49)."""
    targets = fields()["transmission_targets"]
    assert len(targets) >= 8
    text = " ".join(str(t["name"]) for t in targets)
    for absent in ("LKR", "ASPI", "Tea Auction"):
        assert absent in text, f"{absent} is unquotable and must be a named transmission target"
    known = universe_symbols()
    for row in targets:
        assert row["proxies"], f"transmission target {row['name']}: no proxy named"
        for sym in row["proxies"]:
            assert sym in known, f"transmission target {row['name']}: proxy {sym} is not quoted"
            assert not is_equity(sym), f"transmission target {row['name']}: {sym} is an equity"


# --------------------------------------------------------------------------- actors, domains
def test_every_actor_carries_all_eleven_fields() -> None:
    actors = fields()["actors"]
    assert len(actors) >= 12
    seen: set[str] = set()
    for a in actors:
        name = str(a["name"]).strip()
        assert name and name not in seen, f"actor {name!r}: missing or duplicated"
        seen.add(name)
        for field in ACTOR_FIELDS:
            assert a.get(field), (
                f"actor {name}: {field} is empty; an actor missing one breaks the research chain")


def test_every_domain_has_objects_and_controls() -> None:
    domains = fields()["domains"]
    assert len(domains) >= 10
    ids: set[str] = set()
    for d in domains:
        did = str(d["id"]).strip()
        assert did and did not in ids, f"domain {did!r}: missing or duplicated"
        ids.add(did)
        assert d["objects"], f"domain {did}: no research objects"
        assert len(d["controls"]) >= 2, (
            f"domain {did}: fewer than two negative controls; an effect with no control cannot "
            f"be told from the desk's own selection")
        assert d["instruments"], f"domain {did}: no instruments"
    for miner in fields()["custom_miners"]:
        for did in miner["domain_ids"]:
            assert did in ids, f"miner {miner['name']}: names unknown domain {did!r}"


def test_every_dataset_declares_its_vintage() -> None:
    datasets = fields()["datasets"]
    assert len(datasets) >= 8
    for ds in datasets:
        for field in DATASET_FIELDS:
            if field in ("pit_feasible", "publication_lag_days"):
                continue
            assert ds.get(field), f"dataset {ds.get('name')!r}: {field} is empty"
        assert float(ds["publication_lag_days"]) >= 0.0
        assert isinstance(ds["pit_feasible"], bool)


# --------------------------------------------------------------------------- the ten layers
def test_all_ten_source_layers_are_populated() -> None:
    mod = pack_module()
    counts = mod.layer_counts()
    assert set(counts) == set(LAYERS)
    missing = [layer for layer, n in counts.items() if not n]
    assert missing == [], f"unpopulated layer(s): {missing}; this pack declares none absent"
    assert mod.LAYER_ABSENCES == {}, "a declared absence needs a reason and a test that reads it"


def test_every_source_carries_three_independent_labels() -> None:
    for sc in fields()["source_classes"]:
        sid = sc["id"]
        assert sc["layer"] in LAYERS, f"source {sid}: layer {sc['layer']!r}"
        assert sc["access_label"] in ACCESS_LABELS, f"source {sid}: access_label"
        assert sc["credibility"] in CREDIBILITY, f"source {sid}: credibility"
        assert sc["predictive_state"] in PREDICTIVE, f"source {sid}: predictive_state"
        assert sc["roots"], f"source {sid}: no root a crawler can start from"
        assert sc["queries"], f"source {sid}: no query terms"
        assert sc["licence"], f"source {sid}: no licence stated"


def test_forbidden_ground_is_registered_and_fringe_ground_is_kept() -> None:
    """A page whose terms forbid extraction is registered, never scraped and never omitted; a
    FRINGE source is kept at low weight rather than dropped, because a claim that looks false is
    still a dated, testable claim."""
    coverage = pack_module().source_layer_coverage()
    assert coverage["machine_use_forbidden"], (
        "no source registered machine_use_allowed=False -- the licensed terminals and the AIS "
        "aggregators both forbid extraction and omitting them loses the fact that they exist")
    creds = {sc["credibility"] for sc in fields()["source_classes"]}
    assert "FRINGE" in creds, "at least one FRINGE source is kept at low weight"
    assert coverage["unexplained_missing"] == []


# --------------------------------------------------------------------------- native script
def test_terminology_carries_real_sinhala_and_tamil() -> None:
    """Sinhala AND Tamil, in script. Both are official languages of Sri Lanka and they reach
    different halves of the island; a transliterated glossary reaches neither."""
    terminology = fields()["terminology"]
    assert len(terminology) >= 10
    terms = [t for words in terminology.values() for t in words]
    assert len(set(terms)) >= 40
    sinhala = [t for t in terms if has_script(t, "sinhala")]
    tamil = [t for t in terms if has_script(t, "tamil")]
    assert len(sinhala) >= 20, f"only {len(sinhala)} Sinhala-script terms"
    assert len(tamil) >= 20, f"only {len(tamil)} Tamil-script terms"
    for anchor in ("මහ බැංකුව", "පෝය දිනය", "තේ වෙන්දේසිය", "ඉන්ධන මිල"):
        assert any(anchor in t for t in sinhala), f"the Sinhala term {anchor!r} is absent"
    for anchor in ("வட்டி விகிதம்", "பணவீக்கம்", "தேயிலை ஏலம்"):
        assert any(anchor in t for t in tamil), f"the Tamil term {anchor!r} is absent"
    for dom, words in terminology.items():
        assert words, f"terminology[{dom}]: empty"


def test_native_script_reaches_the_crawler_and_not_only_the_glossary() -> None:
    """A pack can carry a bilingual glossary and a monolingual crawler. The queries are what the
    miners actually search, so both scripts are asserted there, in more than one layer."""
    per_layer = pack_module().layer_terms()
    sinhala_layers = {layer for layer, qs in per_layer.items()
                      if any(has_script(q, "sinhala") for q in qs)}
    tamil_layers = {layer for layer, qs in per_layer.items()
                    if any(has_script(q, "tamil") for q in qs)}
    assert len(sinhala_layers) >= 3, f"Sinhala queries reach only {sorted(sinhala_layers)}"
    assert len(tamil_layers) >= 3, f"Tamil queries reach only {sorted(tamil_layers)}"
    assert "practitioner" in sinhala_layers and "practitioner" in tamil_layers, (
        "the native-language press is the practitioner layer; English-only queries there find "
        "the Colombo professional corner and report it as the ground")
    assert tuple(fields()["native_languages"]) == ("si", "ta", "en-LK")


# --------------------------------------------------------------------------- the calendar
def test_sinhala_and_tamil_new_year_2026_is_the_fourteenth_of_april() -> None:
    """The one date in this file a human can check without opening a gazette. The New Year is
    SOLAR -- the transit -- so it is 13-14 April in most years and was 12-13 April in 2024; the
    table must carry the two-day block and name it."""
    rule = fields()["holidays_rule"]
    table = holiday_table(rule, 2026)
    assert "2026-04-14" in table, "Sinhala and Tamil New Year Day 2026 is 14 April"
    assert "New Year" in table["2026-04-14"]
    assert "2026-04-13" in table, "the day prior to the New Year is a holiday in its own right"
    assert "2024-04-12" in holiday_table(rule, 2024), (
        "in 2024 the transit fell a day earlier and the block was 12-13 April, not 13-14")
    assert date(2026, 4, 14) in pack_module().national_holidays(2026)


def test_the_poya_clock_is_lunar_monthly_and_labelled() -> None:
    """Sri Lanka's own calendar mechanism: a market closure on EVERY full moon. Nothing else on
    this desk has a lunar MONTHLY closure, and the projected rows are never pooled with the
    gazetted ones."""
    mod = pack_module()
    for year in (2024, 2025, 2026):
        rows = mod.POYA_DAYS[year]
        assert len(rows) >= 12, f"{year}: {len(rows)} Poya rows; there are twelve or thirteen"
        months = {d.month for d, _n, _s in rows}
        assert len(months) >= 11, f"{year}: the full moon does not skip months"
        for day, name, status in rows:
            assert day.year == year
            assert status in ("ANNOUNCED", "PROJECTED"), f"{day}: status {status!r}"
            assert "Poya" in name
    assert len(mod.POYA_DAYS[2026]) == 14, (
        "2026 carries thirteen full moons plus the day after Vesak, so the Buddhist calendar "
        "inserts an intercalary Adhi Poya")
    assert {s for _d, _n, s in mod.POYA_DAYS[2024]} == {"ANNOUNCED"}
    assert {s for _d, _n, s in mod.POYA_DAYS[2026]} == {"PROJECTED"}
    assert mod.announced_poya(2026) == [], "a projected Poya is never in the announced sample"
    assert len(mod.announced_poya(2025)) >= 12


def test_bank_and_market_calendars_differ() -> None:
    """The 30 June and 31 December closings shut the banks and the money market and are not
    public holidays; a pack that used one calendar for both would mis-date the money market."""
    mod = pack_module()
    bank = mod.bank_holidays(2025)
    national = mod.national_holidays(2025)
    assert date(2025, 6, 30) in bank and date(2025, 6, 30) not in national
    assert date(2025, 12, 31) in bank and date(2025, 12, 31) not in national
    market = mod.market_holidays(2025)
    assert all(d.weekday() < 5 for d in market), "a weekend closure is not one the tape can see"
    assert set(market).issubset(set(bank))
    assert mod.is_market_holiday(date(2025, 5, 12)), "Vesak Poya 2025 is a Monday closure"


def test_the_holiday_rule_carries_both_a_derivation_and_a_table() -> None:
    rule = fields()["holidays_rule"]
    assert str(rule["rule"]).strip(), "a table with no rule cannot be extended past the years "\
                                     "somebody typed"
    for year in (2024, 2025, 2026):
        table = holiday_table(rule, year)
        assert len(table) >= 20, f"{year}: only {len(table)} closures"
        for iso in table:
            assert date.fromisoformat(iso).year == year


# --------------------------------------------------------------------------- the miners
def test_all_five_custom_miners_resolve() -> None:
    lab = country_lab()
    got, problems = lab.load_custom_miners(built_pack())
    assert problems == [], f"custom miner resolution: {problems[:4]}"
    assert sorted(got) == sorted(f"custom:{n}" for n in MINER_NAMES)
    for fn in got.values():
        assert callable(fn)


def test_both_miner_registrations_name_the_same_five() -> None:
    """`CUSTOM_MINERS[*]["entry"]` is what the framework loads and `MINERS` is what `run_lab`
    iterates. If the two drift, a miner the pack believes it runs never runs."""
    miners = import_module(f"research.countries.{CODE}.miners")
    assert sorted(miners.MINERS) == sorted(MINER_NAMES)
    entries = {str(m["entry"]) for m in fields()["custom_miners"]}
    assert entries == {f"countries.{CODE}.miners:{n}" for n in MINER_NAMES}
    for name, fn in miners.MINERS.items():
        assert callable(fn), f"miner {name} is not callable"
        assert (fn.__doc__ or "").strip(), f"miner {name}: no docstring saying what it measures"


def test_the_miners_own_sri_lankas_clocks_and_not_a_generic_one() -> None:
    """Each custom miner must build dates from a Sri Lankan table, not from a generic calendar.
    The Poya miner and the fuel miner are the two that carry a placebo, and the tea miner is the
    one that must declare its leg weak because no tea contract exists anywhere on the broker."""
    miners = import_module(f"research.countries.{CODE}.miners")
    assert "POYA" in (miners.poya_closure_eves.__doc__ or "").upper()
    assert "placebo" in (miners.poya_closure_eves.__doc__ or "").lower()
    assert "placebo" in (miners.fuel_formula_month.__doc__ or "").lower()
    assert "no tea contract" in (miners.tea_auction_week.__doc__ or "").lower()
    kit = miners.K
    for helper in ("event_study", "series_lead", "seed_edges", "month_days", "weekday_dates",
                   "shift", "tape_span"):
        assert callable(getattr(kit, helper)), f"the shared miner kit has no {helper}"


def test_the_policy_dates_are_verified_and_the_unverified_ones_are_separate() -> None:
    """UNMEASURED is a real answer (L1.28a). The rule says eight reviews a year and the desk has
    read four off a release, so the gap is carried as a SEPARATE arm rather than filled in."""
    mod = pack_module()
    cb = fields()["central_bank"]
    verified = tuple(cb["decision_dates"])
    reported = tuple(mod.REPORTED_DECISION_DATES)
    assert verified and reported
    assert not set(verified) & set(reported), "a date is verified or reported, never both"
    for iso in verified + reported:
        date.fromisoformat(iso)
    assert "VERIFIED" in cb["dates_status"]
    assert cb["decision_time_utc"] == "02:00", "07:30 Colombo is 02:00 UTC all year"
    assert cb["framework"] == "inflation_targeter"
    constraints = " ".join(str(c["constraint"]) for c in fields()["access_constraints"])
    assert "OPR transition" in constraints, (
        "the one fact stated two ways in the desk's sources must be registered as DISPUTED "
        "rather than settled by preference")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
