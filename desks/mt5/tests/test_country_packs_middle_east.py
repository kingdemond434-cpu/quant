"""THE MIDDLE EAST PACKS, VALIDATED -- Saudi Arabia, the Emirates and Israel.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has actually
had in some form:

  * A PACK THAT IS AN ENGLISH GLOSSARY. Terminology is the one part of a pack that cannot be
    written in English -- a miner reading Gulf boards for `نقاط البيع` finds nothing if the pack
    spells it "point of sale", and one reading Hebrew for `שער יציג` finds nothing if the pack
    says "representative rate". The script assertions below are what keep that honest.
  * A SYMBOL THE BOX CANNOT TRADE. Every executable instrument and every transmission target is
    checked against the broker's OWN registry, not against a list somebody typed.
  * A SINGLE-NAME EQUITY ON A DOCKET. The two-lane order (2026-09-06) forbids hunting one
    statistically, and the Gulf packs are full of national champions that would be tempting.
  * A CALENDAR THAT SPLIT THE DIFFERENCE. The Hijri dates in the Saudi and UAE tables are fixed by
    a crescent SIGHTING and the pack must SAY SO; the Hebrew dates in the Israeli table are
    computable and the pack must not hedge them. Both are asserted, in both directions.
  * A LAYER NOBODY LOOKED AT. The principal's depth rule (2026-09-17) requires all ten source
    layers to be sourced or declared absent with a reason, each source carrying its three
    independent labels, and each carrying NATIVE-LANGUAGE queries.

The packs are validated in their DICT form (`FIELDS`). `libs.research.country_lab.CountryPack` is
being written by another builder and coerces every row into its own shape -- on 2026-09-17 that
coercion dropped `id` and `targets` from every pack's edges and all twenty-three packs on disk
reported problems. A pack whose validity depends on the hour it is read is not a pack, so the
department's own vocabulary is what is checked here and `pack()` is checked separately for the
one thing it owes: that it builds at all.
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

from countries import check_pack, get, resolve, universe_symbols  # noqa: E402
from countries.ae import pack as AE  # noqa: E402
from countries.il import pack as IL  # noqa: E402
from countries.sa import pack as SA  # noqa: E402

PACKS = {"sa": SA, "ae": AE, "il": IL}
ARABIC = ("sa", "ae")
HEBREW = ("il",)


# ------------------------------------------------------------------------------ the pack shape
@pytest.mark.parametrize("code", sorted(PACKS))
def test_pack_validates_against_the_broker_registry(code: str) -> None:
    """`check_pack` finds NOTHING. It is the validator the whole package shares."""
    problems = check_pack(PACKS[code].FIELDS)
    assert problems == [], f"{code}: {problems}"


@pytest.mark.parametrize("code", sorted(PACKS))
def test_pack_builds_through_the_framework(code: str) -> None:
    """`pack()` returns SOMETHING with this country's code, whatever shape the framework is in."""
    built = PACKS[code].pack()
    assert built is not None
    assert str(get(built, "code")) == code


@pytest.mark.parametrize("code,min_actors,min_domains,min_edges,min_sources",
                         [("sa", 12, 10, 8, 10), ("ae", 12, 10, 8, 10), ("il", 12, 10, 8, 10)])
def test_depth_counts(code: str, min_actors: int, min_domains: int, min_edges: int,
                      min_sources: int) -> None:
    """A country is never covered by five obvious sources and twelve is the actor floor."""
    mod = PACKS[code]
    assert len(mod.ACTORS) >= min_actors
    assert len(mod.DOMAINS) >= min_domains
    assert len(mod.TRANSMISSION_EDGES_SEED) >= min_edges
    assert len(mod.SOURCE_CLASSES) >= min_sources
    assert len(mod.DATASETS) >= 10
    assert len(mod.POLICY_ERAS) >= 4


@pytest.mark.parametrize("code", sorted(PACKS))
def test_every_actor_has_all_eleven_fields_and_a_falsifier(code: str) -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    fields = ("holds", "forced_to", "when", "information", "constraints", "instruments",
              "counterparties", "observables", "impact", "persistence", "falsifier")
    for row in PACKS[code].ACTORS:
        for f in fields:
            assert row.get(f), f"{code}: actor {row.get('name')!r} has an empty {f}"
        # a one-element tuple written without its trailing comma silently becomes a string, and
        # `tuple("abc")` is then three characters -- this catches that class of typo
        for f in ("forced_to", "information", "constraints", "instruments", "counterparties",
                  "observables"):
            value = row[f]
            assert isinstance(value, tuple), f"{code}: actor {row.get('name')!r}.{f} is not a tuple"
            assert all(len(str(v)) > 2 for v in value), (
                f"{code}: actor {row.get('name')!r}.{f} looks like a string split into characters "
                f"-- a single-element tuple needs its trailing comma")


@pytest.mark.parametrize("code", sorted(PACKS))
def test_every_domain_has_negative_controls(code: str) -> None:
    """Without a control an effect cannot be told from the desk's own sampling."""
    for row in PACKS[code].DOMAINS:
        assert row["controls"], f"{code}: domain {row['id']} has no negative control"
        assert len(row["controls"]) >= 2, f"{code}: domain {row['id']} has only one control"
        assert row["objects"], f"{code}: domain {row['id']} has no research objects"


# ------------------------------------------------------------------------------ the universe
@pytest.mark.parametrize("code", sorted(PACKS))
def test_executable_instruments_are_in_the_brokers_registry(code: str) -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(PACKS[code].EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"{code}: not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{code}: {split['equities']} is a single-name equity and the two-lane order forbids "
        f"hunting one statistically")
    assert set(PACKS[code].EXECUTABLE_INSTRUMENTS) <= set(registry)


@pytest.mark.parametrize("code", sorted(PACKS))
def test_every_transmission_seed_names_tradable_targets(code: str) -> None:
    """A seed that terminates in a symbol the box cannot quote is a cell that can never compile."""
    for seed in PACKS[code].TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"{code}: edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"{code}: edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"{code}: edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"{code}: edge {seed['id']} has no control"


def test_the_pegs_are_named_absent_rather_than_quietly_dropped() -> None:
    """USDSAR and USDAED are NOT quoted here, and the packs say so with what carries them."""
    registry = universe_symbols()
    assert "USDSAR" not in registry and "USDAED" not in registry
    sa_absent = " ".join(r["instrument"] for r in SA.ABSENT_INSTRUMENTS)
    ae_absent = " ".join(r["instrument"] for r in AE.ABSENT_INSTRUMENTS)
    assert "USDSAR" in sa_absent and "USDAED" in ae_absent
    for row in SA.ABSENT_INSTRUMENTS + AE.ABSENT_INSTRUMENTS + IL.ABSENT_INSTRUMENTS:
        assert row["carried_by"], f"{row['instrument']} is named absent with no carrier"
    # Israel is the exception that makes the civilization work: its own price IS quoted.
    assert set(IL.OWN_PRICE) <= set(registry)
    assert SA.OWN_PRICE == () and AE.OWN_PRICE == ()


def test_the_pegs_carry_their_rates() -> None:
    """3.75 and 3.6725 are the two numbers the Gulf's whole policy stance hangs on."""
    assert SA.FIXING_CONVENTIONS["peg"]["rate"] == pytest.approx(3.75)
    assert AE.FIXING_CONVENTIONS["peg"]["rate"] == pytest.approx(3.6725)
    for mod in (SA, AE):
        assert "forward" in mod.FIXING_CONVENTIONS["peg"]["what_a_break_looks_like"].lower()
    assert "float" in IL.FIXING_CONVENTIONS["float"]["regime"]


# ------------------------------------------------------------------------------ the languages
@pytest.mark.parametrize("code", ARABIC)
def test_terminology_is_written_in_arabic(code: str) -> None:
    """A Gulf pack in English is a Gulf pack no Arabic-language miner can use."""
    mod = PACKS[code]
    terms = mod.arabic_terms(mod.TERMINOLOGY) if code == "sa" else AE.arabic_terms(
        mod.TERMINOLOGY)
    assert len(terms) >= 80, f"{code}: only {len(terms)} Arabic terms"
    flat = {t for group in mod.TERMINOLOGY.values() for t in group}
    for must in ("سعر الفائدة", "السيولة"):
        assert must in flat, f"{code}: the pack does not carry {must!r}"
    assert len(mod.TERMINOLOGY) >= 10


def test_saudi_terminology_carries_the_principals_words() -> None:
    """The words the principal named, in the script a crawler types."""
    flat = {t for group in SA.TERMINOLOGY.values() for t in group}
    for must in ("ساما", "الاحتياطي", "تداول", "أرامكو", "نقاط البيع", "المعروض النقدي",
                 "ربط الريال"):
        assert must in flat, f"the Saudi pack does not carry {must!r}"
    assert all(SA.has_arabic(t) for t in flat if t not in {"USDSAR"})


def test_hebrew_terminology_is_written_in_hebrew() -> None:
    """Same rule, other alphabet."""
    terms = IL.hebrew_terms(IL.TERMINOLOGY)
    assert len(terms) >= 80, f"only {len(terms)} Hebrew terms"
    flat = {t for group in IL.TERMINOLOGY.values() for t in group}
    for must in ("בנק ישראל", "ריבית", "שער הדולר", "התערבות", "מדד"):
        assert must in flat, f"the Israeli pack does not carry {must!r}"
    assert not IL.has_hebrew("Bank of Israel")
    assert IL.has_hebrew("בנק ישראל")
    assert not SA.has_arabic("SAMA") and SA.has_arabic("ساما")


# ------------------------------------------------------------------------------ the calendars
def test_saudi_national_day_and_founding_day() -> None:
    """23 September is solar and certain, in every tabulated year."""
    for year in (2024, 2025, 2026):
        table = SA.holidays(year)
        assert f"{year}-09-23" in table, f"Saudi National Day missing in {year}"
        assert "اليوم الوطني" in table[f"{year}-09-23"]
    assert "2026-09-23" in SA.holidays(2026)
    assert any("التأسيس" in v for v in SA.holidays(2026).values())


def test_uae_national_day_and_commemoration_day() -> None:
    """2 December, with Commemoration Day the day before -- and the UAE keeps 1 January too."""
    table = AE.holidays(2026)
    assert "2026-12-02" in table and "اليوم الوطني" in table["2026-12-02"]
    assert "2026-12-01" in table and "الشهيد" in table["2026-12-01"]
    assert "2026-01-01" in table, (
        "the UAE observes the Gregorian New Year and Saudi Arabia does not")
    assert "2026-01-01" not in SA.holidays(2026)


def test_eid_al_fitr_2026_is_declared_with_the_sighting_rule() -> None:
    """A Hijri date is an ESTIMATE until the crescent is sighted, and the pack must say so."""
    for mod in (SA, AE):
        table = mod.holidays(2026)
        eid = [iso for iso, name in table.items() if "عيد الفطر" in name]
        assert eid, "no Eid al-Fitr row for 2026"
        assert any(iso in ("2026-03-19", "2026-03-20", "2026-03-21", "2026-03-22", "2026-03-23")
                   for iso in eid), f"Eid al-Fitr 2026 is tabulated at {eid}"
        assert "2026-03-20" in eid, "the 1 Shawwal 1447 anchor is 2026-03-20"
        rule = mod.HOLIDAYS_RULE["rule"]
        assert "sighting" in rule.lower(), "the sighting rule is not stated"
        status = str(mod.HOLIDAYS_RULE["status"][2026])
        assert "ESTIMATE" in status.upper(), "a sighting-fixed date is presented as certain"
    windows = SA.hijri_windows(2026)
    assert windows["certainty"] == "ESTIMATE"
    assert windows["tolerance_days"] >= 1
    assert SA.hijri_windows(2024)["certainty"] == "ANNOUNCED"
    assert SA.hijri_windows(2031)["certainty"] == "UNMEASURED", (
        "an untabulated Hijri year must be UNMEASURED, never invented")


def test_yom_kippur_2026_is_computed_not_estimated() -> None:
    """The Hebrew calendar is arithmetic, not a sighting: 10 Tishrei 5787 is 2026-09-21, exactly."""
    table = IL.holidays(2026)
    assert "2026-09-21" in table
    assert "יום כיפור" in table["2026-09-21"]
    assert "5787" in table["2026-09-21"]
    status = str(IL.HOLIDAYS_RULE["status"][2026])
    assert "COMPUTED" in status.upper() and "ESTIMATE" not in status.upper(), (
        "the Hebrew calendar is computable and must not be hedged like a Hijri date")
    assert any("ראש השנה" in v for v in table.values())
    assert any("פסח" in v for v in table.values())
    assert "2026-04-02" in table, "15 Nisan 5786 is 2026-04-02"


def test_the_hebrew_cluster_counts_its_own_session_cost() -> None:
    """A Saturday closure costs no session in a Friday-Saturday weekend; a Sunday one does."""
    got = IL.tishrei_cluster(2026)
    assert got["n_closures"] >= 4
    assert got["sessions_lost"] >= 1
    for iso in got["sessions_lost_dates"]:
        assert date.fromisoformat(iso).weekday() not in (4, 5)


def test_israel_observes_dst_and_the_gulf_does_not() -> None:
    """The decision's UTC time moves twice a year in Israel and never in the Gulf."""
    summer = IL.boi_decision_window(date(2026, 6, 1))
    winter = IL.boi_decision_window(date(2026, 12, 1))
    assert summer["announcement_utc"] == "13:00"
    assert winter["announcement_utc"] == "14:00"
    assert "NO daylight saving" in SA.CENTRAL_BANK["timezone"] or \
           "NO DAYLIGHT" in SA.CENTRAL_BANK["timezone"].upper()
    assert "NO daylight saving" in AE.CENTRAL_BANK["timezone"] or \
           "NO DAYLIGHT" in AE.CENTRAL_BANK["timezone"].upper()


def test_the_uae_weekend_change_is_a_split_and_not_a_footnote() -> None:
    """2022-01-03 changed which days exist. A pooled day-of-week study is wrong on one side."""
    assert AE.trading_week_on(date(2021, 12, 1))["regime"] == "sun_thu"
    assert AE.trading_week_on(date(2022, 6, 1))["regime"] == "mon_fri"
    assert AE.WEEKEND_CHANGE.isoformat() == "2022-01-03"
    assert any("2022" in str(e["start"]) for e in AE.POLICY_ERAS)


def test_the_gulf_sunday_asymmetry_is_carried_by_the_right_packs() -> None:
    """Saudi Arabia and Israel trade Sunday; the UAE has not since 2022."""
    assert "SUNDAY" in SA.SETTLEMENT_CONVENTIONS["trading_week"].upper()
    assert "SUNDAY" in IL.SETTLEMENT_CONVENTIONS["trading_week"].upper()
    assert "MONDAY TO FRIDAY" in AE.SETTLEMENT_CONVENTIONS["trading_week"].upper()


# ------------------------------------------------------------------------------ positioning
@pytest.mark.parametrize("code", sorted(PACKS))
def test_cot_is_declared_rather_than_silently_absent(code: str) -> None:
    """No SAR, AED, QAR or KWD contract exists, and the ILS one exists and is unusable. Both are
    stated: an absence a study can trip over must be named (L1.28a)."""
    rows = {r["id"]: r for r in PACKS[code].POSITIONING_SOURCES}
    cot = [r for r in rows.values() if "cot" in r["id"]]
    assert cot, f"{code}: the COT question is not answered anywhere in the pack"
    note = " ".join(str(r["note"]) for r in cot)
    assert "DECLARED" in note or "declared" in note


def test_gulf_sections_carry_qatar_and_kuwait() -> None:
    """Two economies with no independent executable ground, kept as sections rather than dropped."""
    sections = AE.GULF_SECTIONS
    assert set(sections) == {"qa", "kw"}
    assert "3.64" in sections["qa"]["central_bank"]
    assert "basket" in sections["kw"]["central_bank"].lower()
    assert "UNDISCLOSED" in sections["kw"]["central_bank"].upper()
    for row in sections.values():
        assert row["observables"] and row["policy_eras"] and row["falsifier"]
        split = resolve(row["executable_carriers"])
        assert split["absent"] == [] and split["equities"] == []


# ------------------------------------------------------------------------------ the depth rule
@pytest.mark.parametrize("code", sorted(PACKS))
def test_every_source_layer_is_sourced_or_declared_absent(code: str) -> None:
    """The principal's depth rule (2026-09-17): ten layers, none of them blank."""
    mod = PACKS[code]
    problems = mod.check_sources(mod.SOURCE_CLASSES, mod.ABSENT_LAYERS)
    assert problems == [], f"{code}: {problems}"
    counts = mod.layer_counts(mod.SOURCE_CLASSES)
    declared = {str(a["layer"]) for a in mod.ABSENT_LAYERS}
    for layer in SA.LAYERS:
        assert counts[layer] > 0 or layer in declared, f"{code}: layer {layer} is blank"


@pytest.mark.parametrize("code", sorted(PACKS))
def test_every_source_carries_three_independent_labels(code: str) -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in PACKS[code].SOURCE_CLASSES:
        assert row["access_label"] in SA.ACCESS_LABELS
        assert row["credibility"] in SA.CREDIBILITY
        assert row["predictive_state"] in SA.PREDICTIVE_STATES
        assert row["access_label"] not in SA.FORBIDDEN_ACCESS, (
            f"{code}: {row['id']} is labelled with an access class the desk may never read")
        assert row["queries"], f"{code}: {row['id']} has no native-language query"


@pytest.mark.parametrize("code", sorted(PACKS))
def test_queries_are_native_and_not_translated_english(code: str) -> None:
    """A query in English finds an English article about the release, not the release."""
    script = SA.has_arabic if code in ARABIC else IL.has_hebrew
    native = 0
    for row in PACKS[code].SOURCE_CLASSES:
        if not row["machine_use_allowed"]:
            continue                      # a row that is never crawled owes no live query
        native += sum(1 for q in row["queries"] if script(q))
    assert native >= 25, f"{code}: only {native} native-script queries across crawlable sources"


@pytest.mark.parametrize("code", sorted(PACKS))
def test_fringe_material_is_kept_and_forbidden_ground_is_registered(code: str) -> None:
    """Fringe is kept at low weight; what may not be machine-read is REGISTERED, never omitted."""
    rows = PACKS[code].SOURCE_CLASSES
    fringe = [r for r in rows if r["credibility"] in ("FRINGE", "UNRELIABLE", "CONTRADICTED")]
    assert fringe, (
        f"{code}: no fringe or unreliable ground is kept at all, which means it was dropped -- "
        f"and a dropped source is indistinguishable from one nobody found")
    for row in fringe:
        assert row["kept_as_evidence"] is True
        assert row["evidence_weight"] <= 0.5, f"{code}: {row['id']} is fringe at full weight"
    blocked = [r for r in rows if not r["machine_use_allowed"]]
    assert blocked, f"{code}: nothing is registered as machine-use-forbidden, which is implausible"
    for row in blocked:
        assert row["refused_reason"] or "NEVER SCRAPED" in str(row["notes"]).upper()


@pytest.mark.parametrize("code", sorted(PACKS))
def test_the_standing_refusals_are_written_down(code: str) -> None:
    """Crypto-exchange ground and single-name hypothesis ground are refused IN WRITING."""
    blob = " ".join(str(r["refused_reason"]) + " " + str(r["notes"])
                    for r in PACKS[code].SOURCE_CLASSES).lower()
    assert "crypto" in blob and "2026-08-18" in blob
    assert "two-lane" in blob and "2026-09-06" in blob


# ------------------------------------------------------------------------------ the miners
@pytest.mark.parametrize("code", sorted(PACKS))
def test_custom_miner_entry_points_resolve(code: str) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    from importlib import import_module
    for row in PACKS[code].CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        module = import_module(module_path)
        assert callable(getattr(module, func)), f"{code}: {row['entry']} does not resolve"
        for did in row["domain_ids"]:
            assert did in {d["id"] for d in PACKS[code].DOMAINS}


def test_the_saudi_pos_calendar_flags_its_hijri_weeks() -> None:
    """A weekly study that mislabels a Ramadan week produces a confident wrong seasonal."""
    got = SA.pos_weeks(2026)
    assert got["n_weeks"] >= 52
    assert got["hijri_weeks"], "no Hijri overlap flagged in a year containing Ramadan and two Eids"
    for row in got["weeks"]:
        assert date.fromisoformat(row["week_end"]).weekday() == 5, "the POS week ends Saturday"
        assert row["regime"] in ("hijri", "ordinary")


@pytest.mark.parametrize("code", sorted(PACKS))
def test_instrument_report_is_measured_against_the_registry(code: str) -> None:
    """The report is a MEASUREMENT of what the box can trade, not a restatement of the list."""
    got: dict[str, Any] = PACKS[code].instrument_report()
    assert got["absent_from_universe"] == ()
    assert got["equities_refused"] == ()
    assert set(got["executable"]) == set(PACKS[code].EXECUTABLE_INSTRUMENTS)
    assert got["named_absent_instruments"]
