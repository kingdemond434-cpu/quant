"""THE DENMARK PACK, VALIDATED -- the treaty band, the spread, the auctions and a deleted Friday.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A PACK THAT IS AN ENGLISH GLOSSARY OF A DANISH-SPEAKING COUNTRY. Denmark's mortgage
    vocabulary -- rentetilpasning, konvertering, bidragssats, balanceprincippet -- has no English
    equivalent a search engine will match, and the Nationalbank publishes in Danish first. The
    script assertions below are what keep the terminology and every source class's queries honest.
  * A SYMBOL THE BOX CANNOT TRADE. Every executable instrument and every edge target is checked
    against the broker's OWN registry, not against a list somebody typed.
  * A SINGLE-NAME EQUITY ON A DOCKET. The two-lane order (2026-09-06) forbids hunting one
    statistically, and this pack is full of tempting national champions which appear only as
    ACTORS.
  * A HOLIDAY TABLE SOMEBODY TYPED. Denmark abolished Store Bededag from 2024 by Lov nr. 214 af
    07/03/2023. The pack COMPUTES the date in every year -- so the abolition is a measurable
    regime break with its own control day -- and these tests check both halves.
  * A BAND NOBODY CHECKED. The ERM II edges are arithmetic on 7.46038 and +/-2.25%; the corridor
    actually operated is a tenth of that. A study that conditions on the treaty edge conditions
    on a state that has never been visited, and the pack must say so in code.
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
from countries.dk import pack as DK  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as F  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")


class FakeCtx:
    """The smallest thing that looks like a `country_lab.LabCtx` to a pack miner: it collects
    what a miner would have emitted so the test can assert on it WITHOUT a registry."""

    def __init__(self) -> None:
        self.code = "dk"
        self.dry_run = True
        self.unmeasured: list[str] = []
        self.transmission_seeds: list[dict[str, Any]] = []
        self.bars = None

    def note(self, what: str, why: str) -> None:
        self.unmeasured.append(f"{what}: {why}")

    def seed_transmission(self, **row: Any) -> None:
        self.transmission_seeds.append(dict(row))


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it, resolved through `resolve_pack` so the test measures
    the same object the country lab runs and not a private construction."""
    got = CL.resolve_pack("dk")
    assert got is not None, "no Denmark pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(DK.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == "dk"
    assert str(get(built, "region_command")) == "europe"
    assert str(get(built, "currency")) == "DKK"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    """A coercion note is a field `CountryPack` could not read. There must be none."""
    notes = list(getattr(built, "coercion_notes", ()) or [])
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on this pack: {fatal[:4]}"


def test_jurisdictions_are_declared_and_on_the_desks_own_roster() -> None:
    """THE PARITY FENCE COUNTS THIS. Denmark is one of the twenty-six countries the fence names
    as unanswered, and the pack must declare the code the fence reads."""
    assert DK.JURISDICTIONS == ("dk",)
    assert all(c == c.lower() and len(c) == 2 for c in DK.JURISDICTIONS)
    roster = {c.lower() for f in F.FORESTS.values() for c in f.countries}
    for code in DK.JURISDICTIONS:
        assert code in roster, f"{code} is not on any Forest.countries roster"


def test_pack_reaches_parity_depth(built: Any) -> None:
    """The standing depth rule, measured by the framework and not claimed by the pack."""
    row = RP.pack_depth(built, "dk").as_row()
    assert row["score"] == 1.0, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_depth_counts_sit_above_the_floor_and_not_on_it() -> None:
    """Twelve actors is the floor; a country written to the floor is a country half-read."""
    assert len(DK.ACTORS) >= 15
    assert len(DK.DOMAINS) >= 15
    assert len(DK.TRANSMISSION_EDGES_SEED) >= 12
    assert len(DK.SOURCE_CLASSES) >= 24
    assert len(DK.DATASETS) >= 14
    assert len(DK.POLICY_ERAS) >= 7
    assert DK.term_count() >= 110


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    for row in DK.ACTORS:
        for f in ACTOR_FIELDS:
            assert row.get(f), f"actor {row.get('name')!r} has an empty {f}"
        # a one-element tuple written without its trailing comma silently becomes a string, and
        # tuple("abc") is then three characters -- this catches that class of typo
        for f in ("forced_to", "information", "constraints", "instruments", "counterparties",
                  "observables"):
            value = row[f]
            assert isinstance(value, tuple), f"actor {row.get('name')!r}.{f} is not a tuple"
            assert all(len(str(v)) > 2 for v in value), (
                f"actor {row.get('name')!r}.{f} looks like a string split into characters -- a "
                f"single-element tuple needs its trailing comma")


def test_every_domain_has_objects_and_two_negative_controls() -> None:
    """Without a control an effect cannot be told from the desk's own sampling."""
    ids = set()
    for row in DK.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert row["conditions"], f"domain {row['id']} names no conditioning state"
        assert row["id"] not in ids, f"domain {row['id']} declared twice"
        ids.add(row["id"])


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(DK.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert set(DK.EXECUTABLE_INSTRUMENTS) <= set(registry)
    assert {"EURDKK", "USDDKK", "CHFDKK", "GBPDKK"} <= set(DK.EXECUTABLE_INSTRUMENTS)


def test_every_transmission_seed_names_tradable_targets() -> None:
    """A seed that terminates in a symbol the box cannot quote can never compile a cell."""
    for seed in DK.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"


def test_domain_instruments_are_tradable_and_never_a_single_name() -> None:
    for row in DK.DOMAINS:
        split = resolve(row["instruments"])
        assert split["absent"] == [], f"domain {row['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"domain {row['id']} -> equity {split['equities']}"


def test_absent_instruments_are_named_rather_than_quietly_dropped() -> None:
    """The OMXC25, the DGB curve and CITA are not quoted, and the pack says what carries them."""
    registry = universe_symbols()
    assert not {"OMXC25", "DKKCITA", "CIBOR"} & set(registry)
    named = " ".join(str(t["name"]) for t in DK.TRANSMISSION_TARGETS)
    assert "OMXC25" in named and "CITA" in named and "Realkredit" in named
    for row in DK.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert resolve(row["proxies"])["absent"] == []


# ------------------------------------------------------------------------------ the language
def test_terminology_is_danish_and_not_an_english_glossary() -> None:
    """Denmark is read in Danish; a crawler handed English reads the English corner of it."""
    flat = {t for group in DK.TERMINOLOGY.values() for t in group}
    assert len(DK.TERMINOLOGY) >= 15
    assert DK.term_count() >= 110
    assert set(flat) == set(DK.danish_terms()), (
        "some terminology rows are neither Danish-lettered nor Danish market vocabulary: "
        f"{sorted(set(flat) - set(DK.danish_terms()))[:6]}")
    diacritic = [t for t in flat if DK.has_danish_letter(t)]
    assert len(diacritic) >= 28, f"only {len(diacritic)} terms carry a Danish letter"
    for must in ("fastkurspolitik", "realkredit", "refinansieringsauktion", "foliorente",
                 "rentetilpasningslån", "store bededag", "konvertering",
                 "vindproduktion", "svinenotering", "bidragssats"):
        assert must in flat, f"the Denmark pack does not carry {must!r}"
    assert DK.has_danish_letter("rentetilpasningslån")
    assert not DK.has_danish_letter("mortgage auction")
    assert DK.is_danish("obligationsmarkedet") and not DK.is_danish("quarterly earnings")


def test_every_source_carries_three_labels_a_root_and_a_danish_query() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in DK.SOURCE_CLASSES:
        assert row["access_label"] in DK.ACCESS_LABELS
        assert row["credibility"] in DK.CREDIBILITY_LABELS
        assert row["predictive_state"] in DK.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["queries"], f"{row['id']} has no native-language query"
        assert row["roots"], f"{row['id']} has no crawlable root"
        assert any(DK.is_danish(q) for q in row["queries"]), (
            f"{row['id']} carries no Danish query at all -- it reads the English corner")


def test_all_ten_source_layers_are_populated() -> None:
    """The principal's depth rule: ten layers, none of them blank."""
    counts = DK.layer_counts()
    assert set(counts) == set(DK.SOURCE_LAYERS)
    blank = [layer for layer, n in counts.items() if not n]
    assert blank == [], f"blank layers: {blank}"
    coverage = DK.source_layer_coverage()
    assert coverage["n_layers_covered"] == 10
    assert coverage["unexplained_missing"] == []
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible for a country "
        "whose exchange tape and whose trade press are both behind terms that forbid it")
    assert coverage["low_weight_kept"], "no fringe ground is kept at all, so it was dropped"


def test_query_territories_cover_every_layer_in_danish() -> None:
    """The deep-forest miner needs phrases, not source names, and it needs them per layer."""
    assert set(DK.QUERY_TERRITORIES) == set(DK.SOURCE_LAYERS), (
        f"missing: {sorted(set(DK.SOURCE_LAYERS) - set(DK.QUERY_TERRITORIES))}")
    for layer, phrases in DK.QUERY_TERRITORIES.items():
        assert len(phrases) >= 3, f"{layer} has only {len(phrases)} query phrases"
        assert all(DK.is_danish(p) for p in phrases), (
            f"{layer} carries a non-Danish phrase: "
            f"{[p for p in phrases if not DK.is_danish(p)]}")


# ------------------------------------------------------------------------------ the calendars
def test_the_holiday_table_resolves_for_all_three_years() -> None:
    """A table with no rule cannot be extended; a rule with no table cannot be checked."""
    assert "store bededag" in DK.HOLIDAYS_RULE["rule"].lower()
    for year in (2024, 2025, 2026):
        table = holiday_table(DK.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        assert f"{year}-01-01" in table and f"{year}-12-25" in table
        assert f"{year}-06-05" in table, "Grundlovsdag is an exchange closure and must be there"


def test_easter_is_computed_and_hangs_eight_closures_off_itself() -> None:
    assert DK.easter_sunday(2024) == date(2024, 3, 31)
    assert DK.easter_sunday(2025) == date(2025, 4, 20)
    assert DK.easter_sunday(2026) == date(2026, 4, 5)
    for year in (2024, 2025, 2026):
        table = DK.national_holidays(year)
        easter = DK.easter_sunday(year)
        for offset in (-3, -2, 0, 1, 39, 49, 50):
            assert easter + timedelta(days=offset) in table, (
                f"Easter+{offset} missing from the {year} table")


# ------------------------------------------------------------------ MECHANISM FUNCTION ONE
def test_store_bededag_is_computed_and_was_abolished_from_2024() -> None:
    """THE FACT A PACK EXISTS TO HOLD. Lov nr. 214 af 07/03/2023 removed Great Prayer Day from
    2024. The date is still COMPUTED in every year, because after the abolition the same
    seasonal Friday is the control -- without it the break can only be measured against
    arbitrary Fridays."""
    assert DK.store_bededag(2023) == date(2023, 5, 5)
    assert DK.store_bededag(2024) == date(2024, 4, 26)
    assert DK.store_bededag(2025) == date(2025, 5, 16)
    assert DK.store_bededag(2026) == date(2026, 5, 1)
    assert all(DK.store_bededag(y).weekday() == 4 for y in range(2020, 2031)), (
        "Great Prayer Day is the fourth FRIDAY after Easter in every year")
    # the abolition itself
    assert date(2023, 5, 5) in DK.national_holidays(2023)
    for year in (2024, 2025, 2026):
        assert DK.store_bededag(year) not in DK.national_holidays(year), (
            f"Store Bededag is still a holiday in {year} -- the 2023 statute is not applied")
        assert DK.store_bededag(year).isoformat() not in holiday_table(DK.HOLIDAYS_RULE, year)
    assert DK.STORE_BEDEDAG_ABOLISHED_FROM == 2024
    assert "214" in DK.STORE_BEDEDAG_STATUTE and "2023" in DK.STORE_BEDEDAG_STATUTE


def test_denmark_does_not_substitute_a_weekend_holiday() -> None:
    """No substitution rule means the trading-day count of a Danish year genuinely varies."""
    lost = DK.lost_holidays(2025)
    assert lost, "2025 has Easter Sunday and Whit Sunday at the weekend by construction"
    assert all(d.weekday() >= 5 for d in lost)
    for day in lost:
        assert day not in DK.market_holidays(2025), (
            "a weekend closure costs no session and must not enter a holiday sample as one")


# ------------------------------------------------------------------ MECHANISM FUNCTION TWO
def test_the_erm_ii_band_is_a_function_and_its_edges_are_checkable() -> None:
    """The treaty number is 7.46038 with +/-2.25%, and the edges are arithmetic a human can
    check. The corridor actually operated is a tenth of that, and the GAP is the mechanism."""
    assert pytest.approx(7.46038) == DK.PEG_CENTRAL_RATE
    assert pytest.approx(0.0225) == DK.ERM2_BAND_PCT
    lo, hi = DK.band_edges()
    assert lo == pytest.approx(7.46038 - 7.46038 * 0.0225)
    assert hi == pytest.approx(7.46038 + 7.46038 * 0.0225)
    assert lo == pytest.approx(7.29252145, abs=1e-8)
    assert hi == pytest.approx(7.62823855, abs=1e-8)
    # the position is a signed state in [-1, +1] and it is NOT clipped outside the band
    assert DK.band_position(DK.PEG_CENTRAL_RATE) == pytest.approx(0.0)
    assert DK.band_position(hi) == pytest.approx(1.0)
    assert DK.band_position(lo) == pytest.approx(-1.0)
    assert DK.band_position(8.0) > 1.0, "a rate outside the band must not be silently clipped"
    assert DK.in_band(7.46) and not DK.in_band(8.0)
    # the operated corridor is much narrower than the treaty band, which is the whole point
    op_lo, op_hi = DK.operating_edges()
    assert lo < op_lo < DK.PEG_CENTRAL_RATE < op_hi < hi
    assert (op_hi - op_lo) < (hi - lo) / 5.0
    # the named states, including the two that have never been visited
    assert DK.band_state(7.4600) == "STRONG_SIDE_OF_CENTRAL"
    assert DK.band_state(7.4700) == "WEAK_SIDE_OF_CENTRAL"
    assert DK.band_state(7.2000) == "AT_OR_OUTSIDE_TREATY_EDGE"
    assert DK.band_state(7.4300) == "STRONG_KRONE_OUTSIDE_OPERATING_CORRIDOR"
    assert DK.band_state(7.4900) == "WEAK_KRONE_OUTSIDE_OPERATING_CORRIDOR"
    assert "re-measure" in DK.OPERATING_BAND_STATUS


# ------------------------------------------------------------------ MECHANISM FUNCTION THREE
def test_the_policy_spread_is_derived_from_the_table_and_never_typed_beside_it() -> None:
    """The DN-minus-ECB spread IS the defence instrument. It is computed, so it cannot disagree
    with itself, and the two signs of it are two different regimes."""
    assert DK.spread_bp(date(2000, 1, 1)) is None, "no spread before the first declared row"
    assert DK.spread_bp(date(2008, 11, 1)) == pytest.approx(175.0)
    assert DK.spread_regime(date(2008, 11, 1)) == "DN_TIGHTER_THAN_ECB"
    assert DK.spread_bp(date(2015, 2, 2)) == pytest.approx(-55.0)
    assert DK.spread_regime(date(2015, 2, 2)) == "DN_EASIER_THAN_ECB"
    assert DK.spread_bp(date(2012, 7, 6)) == pytest.approx(-20.0)
    assert "deposit facility" in DK.SPREAD_RULE.lower()


def test_the_refinancing_auction_windows_are_computed_and_november_is_the_largest() -> None:
    """Denmark's central bank publishes NO meeting calendar, so these four windows are the only
    pre-registrable domestic rates clock the country has."""
    windows = DK.refinancing_auction_windows(2025)
    assert [w["month"] for w in windows] == [2, 5, 8, 11]
    for w in windows:
        assert w["start"].weekday() == 0 and w["end"].weekday() == 4
        assert (w["end"] - w["start"]).days == 4
        assert w["end"].month == w["month"], "the window is anchored on the Friday"
    november = next(w for w in windows if w["month"] == 11)
    assert november["size_class"] == "LARGEST"
    assert november["reset"] == date(2026, 1, 1), "November refixes the 1 January reset"
    assert november["start"] == date(2025, 11, 24) and november["end"] == date(2025, 11, 28)
    days = DK.auction_week_days(2025)
    assert len(days) == 20 and all(d.weekday() < 5 for d in days)
    deadlines = DK.prepayment_notice_deadlines(2025)
    assert len(deadlines) == 4
    assert deadlines[0] == date(2025, 1, 31), "two months' notice before the 1 April term"


def test_the_intervention_record_is_dated_and_two_sided() -> None:
    assert DK.intervention_state(date(2015, 1, 25)) == "BUY_FX"
    assert DK.intervention_state(date(2008, 11, 1)) == "SELL_FX"
    assert DK.intervention_state(date(2018, 5, 1)) == "QUIET"
    assert len(DK.intervention_episodes("BUY_FX")) >= 2
    assert len(DK.intervention_episodes("SELL_FX")) >= 2
    assert "MONTHLY" in DK.INTERVENTION_PUBLICATION.upper()


def test_cot_is_declared_absent_rather_than_silently_missing() -> None:
    """No DKK contract exists anywhere. An absence a study can trip over must be named."""
    absent = [r for r in DK.POSITIONING_SOURCES if not r["available"]]
    assert absent, "the COT question is not answered anywhere in the pack"
    assert any("DOES NOT EXIST" in str(r["pit_warning"]) for r in absent)
    assert DK.COT_CURRENCY == ""


# ------------------------------------------------------------------------------ the cells
def test_the_pack_mints_a_real_cell_lattice() -> None:
    """THE POINT OF A PACK IS CELLS REACHING THE ONE GAUNTLET. Each one must name a real
    condition this pack's own data plane can evaluate."""
    cells = DK.cells()
    assert 60 <= len(cells) <= 400, f"{len(cells)} cells is outside the honest range"
    assert len(cells) == len(DK.CELLS)
    ids = [c["cell_id"] for c in cells]
    assert len(ids) == len(set(ids)), "duplicate cell ids"
    domain_ids = {d["id"] for d in DK.DOMAINS}
    for c in cells:
        assert set(c) == {"cell_id", "domain", "symbol", "condition", "mechanism_family",
                          "horizon", "control", "why"}
        assert c["domain"] in domain_ids
        assert c["symbol"] in DK.EXECUTABLE_SET
        assert c["condition"] and c["control"] and c["horizon"] and c["mechanism_family"]
    assert {c["domain"] for c in cells} == domain_ids, "a domain mints no cells at all"


def test_datasets_are_deep_and_fetchable() -> None:
    assert len(DK.DATASETS) >= 14
    for ds in DK.DATASETS:
        assert len(str(ds["how_to_fetch"])) > 40, (
            f"{ds['name']}: how_to_fetch is not concrete enough for a collector")
        assert ds["assets"] and resolve(ds["assets"])["absent"] == []
        assert ds["mechanism_families"]
        assert float(ds["publication_lag_days"]) >= 0.0
    assert any(ds["pit_feasible"] for ds in DK.DATASETS)
    assert any(not ds["pit_feasible"] for ds in DK.DATASETS), (
        "every dataset claims point-in-time feasibility, which is implausible")


def test_interactions_name_other_packs_with_a_mechanism_and_a_control() -> None:
    """This is how the desk stops testing each country in isolation."""
    assert len(DK.INTERACTIONS) >= 4
    withs = [row["with"] for row in DK.INTERACTIONS]
    assert len(withs) == len(set(withs))
    assert {"ea", "se", "no", "uk"} <= set(withs)
    for row in DK.INTERACTIONS:
        assert row["mechanism"] and row["observable"] and row["control"] and row["why"]
        assert row["targets"] and resolve(row["targets"])["absent"] == []


# ------------------------------------------------------------------------------ the miners
def test_every_custom_miner_resolves_through_the_country_lab(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert len(got) == len(DK.CUSTOM_MINERS)
    assert all(callable(fn) for fn in got.values())


def test_custom_miner_rows_name_known_domains_and_match_the_miners_table() -> None:
    ids = {d["id"] for d in DK.DOMAINS}
    entries = set()
    for row in DK.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.dk.pack", row["entry"]
        assert callable(getattr(DK, func)), f"{row['entry']} does not resolve"
        entries.add(func)
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    assert entries == set(DK.MINERS)
    for dids in DK.MINER_DOMAINS.values():
        assert set(dids) <= ids


def test_mine_returns_a_report_and_emits_nothing_without_a_context() -> None:
    """`mine(None)` must be pure: a report, no registry, no network, no side effect."""
    report = DK.mine(None)
    assert report["code"] == "DK"
    assert report["jurisdictions"] == ("dk",)
    assert report["dry_run"] is True
    assert report["cells_emitted"] == len(DK.cells())
    assert report["emitted"] == len(report["rows"]) > 0
    assert report["at"].endswith("+00:00"), "the stamp must be timezone-aware UTC"
    assert isinstance(report["unmeasured"], tuple)


def test_mine_emits_its_seeds_through_a_context_when_one_is_given() -> None:
    """The ONE door into the registry is the context; with one present the seeds go through it."""
    ctx = FakeCtx()
    report = DK.mine(ctx)
    assert report["emitted"] > 0
    assert len(ctx.transmission_seeds) == len(DK.TRANSMISSION_EDGES_SEED)
    assert {s["id"] for s in ctx.transmission_seeds} == {
        e["id"] for e in DK.TRANSMISSION_EDGES_SEED}
    assert ctx.unmeasured, "nothing was noted UNMEASURED, which hides the missing tape"
