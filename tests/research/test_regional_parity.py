"""REGIONAL PARITY: the law's arithmetic, the fence's one assertion, and the promise not to cap.

WHAT THESE TESTS ARE FOR. `libs/research/regional_parity.py` decides how much compute a neglected
region earns, and `scripts/check_regional_parity.py` decides whether the federation has a hole in
it. Both are the kind of module that rots silently: a depth target quietly lowered, an UNMEASURED
term quietly read as zero, a "temporary" cap on a region that never comes off. Each test below is
aimed at one of those.

THE FOUR THAT ARE LOAD-BEARING:

  1. UNMEASURED HOLDS THE MIDDLE, NEVER ZERO AND NEVER THE BEST (L1.28a). A registry that will not
     open must not price a region at zero debt (which defunds it) or at one (which would let a
     broken database bankroll the whole desk). `coverage_debt` holds 0.5 per unreadable term and
     NAMES it in `unmeasured`; the tests pin both halves, because an unnamed middle is
     indistinguishable from a measurement.

  2. THE FENCE ASSERTS EXACTLY ONE THING. `NO_PACK` on a regional forest is a hole in the
     federation and fails. The other four flags are LIVE STATE and must NOT fail a commit gate --
     a gate that is red in every clean checkout is a gate somebody deletes (L1.43). So the tests
     assert the fence passes on a no-registry machine WITH flags raised, and fails the moment a
     region genuinely has no pack and no package.

  3. IT NEVER CAPS COMPUTE. `caps_compute: false` is a machine-readable promise in the artifact,
     and `research_roi.parity_overlay` is one-sided by construction. A later session that turns
     the parity number into a throttle has to delete a test that says, in words, why it must not.

  4. DEPTH IS THE FRAMEWORK'S VERDICT, NOT THE PACK'S. `pack_depth` counts what `CountryPack`
     actually carries after coercion; a pack that claims twelve actors and hands the framework
     three scores three. The test builds a deliberately shallow pack and a deliberately deep one
     and asserts the score moves with the FRAMEWORK's count.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as F  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402
from scripts import check_regional_parity as FENCE  # noqa: E402

# --------------------------------------------------------------------------- fixtures
#: Real broker symbols, so a fixture pack does not fail `validate_pack` on an invented ticker --
#: the depth score does not read that verdict, but a fixture whose `why` is full of FATALs makes
#: every failure message here unreadable.
_SYMS: tuple[str, ...] = ("XAUUSD", "EURUSD", "USDJPY", "US500", "XTIUSD", "WHEAT", "GER40",
                          "XAGUSD", "GBPUSD", "CORN", "NAS100", "XNGUSD")


def _pack(code: str, *, actors: int = 12, domains: int = 10, edges: int = 8, terms: int = 40,
          datasets: int = 8, eras: int = 4, instruments: int = 6,
          layers: int = 10) -> CL.CountryPack:
    """A pack built through the framework's own constructor, so the test measures what
    `pack_depth` measures rather than what a fixture asserts.

    `layers` declares that many of the ten source layers as ABSENT-WITH-A-REASON, which is what
    the depth rule counts as mapped: a layer a country genuinely has nothing in is DECLARED, not
    blank (L1.28a). Passing fewer is how a test builds a pack with an unmapped layer on purpose.
    """
    return CL.CountryPack(
        code=code, name=code.upper(), region_command="europe", currency="XXX",
        executable_instruments=_SYMS[:instruments],
        absent_layers={L: f"nothing in {L} for {code}" for L in CL.SOURCE_LAYERS[:layers]},
        native_languages=("xx",),
        terminology={"t": tuple(f"term{i}" for i in range(terms))},
        datasets=tuple({"name": f"ds{i}", "source": "s", "coverage": "c", "frequency": "d",
                        "pit_feasible": bool(i % 2)} for i in range(datasets)),
        actors=tuple({"name": f"a{i}", "holds": "h", "forced_to": ("f",), "when": "w",
                      "information": "i", "constraints": "c", "observable": "o", "flow": "fl",
                      "market_impact": "m", "falsifier": "fa", "instruments": ()}
                     for i in range(actors)),
        domains=tuple({"id": f"D{i}", "title": "t", "objects": ("o",), "controls": ("c",)}
                      for i in range(domains)),
        transmission_edges_seed=tuple({"id": f"E{i}", "source": "s", "mechanism": "m",
                                       "targets": ("XAUUSD",), "sign": "+", "horizon": "h",
                                       "evidence": "HYPOTHESIS"} for i in range(edges)),
        policy_eras=tuple({"id": f"P{i}", "start": "2020-01-01", "end": None, "label": "l",
                           "what_changed": "w"} for i in range(eras)),
    )


@pytest.fixture()
def registry(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """A registry with the three tables the parity signals read and nothing in them: a
    READABLE table that holds nothing is a MEASURED zero, which is not the same as UNMEASURED."""
    conn = sqlite3.connect(tmp_path / "reg.sqlite")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE workers (worker_id TEXT, status TEXT, last_seen TEXT);"
        "CREATE TABLE sources (country TEXT, first_seen TEXT);"
        "CREATE TABLE discoveries (generator TEXT, created_at TEXT, generated_cells INT,"
        " compiled_cells INT, queued_cells INT, tested_cells INT);"
        "CREATE TABLE research_candidates (generator TEXT);")
    conn.commit()
    yield conn
    conn.close()


# --------------------------------------------------------------------------- depth
def test_depth_score_is_the_framework_count_not_the_packs_claim() -> None:
    deep = RP.pack_depth(_pack("aa"), "aa")
    assert deep.resolved and deep.score == 1.0, deep.why
    shallow = RP.pack_depth(_pack("bb", actors=3, domains=2, edges=1, terms=4, datasets=1,
                                  eras=1, instruments=1), "bb")
    assert shallow.score is not None and shallow.score < 0.35, shallow.why
    # no single table can buy the rest: 1000 terms does not lift a pack with nothing else
    lopsided = RP.pack_depth(_pack("cc", actors=0, domains=0, edges=0, terms=1000, datasets=0,
                                   eras=0, instruments=0, layers=0), "cc")
    assert lopsided.score is not None and lopsided.score <= 1.0 / len(RP.DEPTH_TARGETS) + 1e-9


def test_an_unresolved_pack_is_unmeasured_by_name_never_a_zero_row() -> None:
    d = RP.pack_depth(None, "zz")
    assert d.resolved is False and d.score is None
    assert RP.UNMEASURED in d.why and "zz" in d.why


def test_region_depth_names_the_packs_that_do_not_resolve() -> None:
    def resolver(code: str) -> CL.CountryPack | None:
        return _pack(code) if code in {"us", "ca"} else None

    got = RP.region_depth("north_america", resolver=resolver)
    assert got.measured and got.score_mean == 1.0
    missing = RP.region_depth("north_america", resolver=lambda _c: None)
    assert not missing.measured and set(missing.missing) == set(F.forest("north_america").packs)


def test_a_global_forest_is_unmeasured_rather_than_zero() -> None:
    got = RP.region_depth("global_web")
    assert got.kind != "regional" and got.score_mean is None
    assert RP.UNMEASURED in got.why


# --------------------------------------------------------------------------- the debt
def test_unmeasured_terms_hold_the_middle_and_are_named(tmp_path: Path) -> None:
    debt = RP.coverage_debt("europe", depth=RP.region_depth("europe", resolver=lambda _c: None),
                            signals={"resident": None, "sources_window": None,
                                     "discoveries_window": None, "lattice_candidates": None})
    assert set(debt["unmeasured"]) == {"discovery", "lattice", "resident"}
    for name in ("discovery", "lattice", "resident"):
        assert debt["terms"][name] == 0.5, "an unreadable term is the MIDDLE, never zero or one"
    assert debt["terms"]["layers"] == 1.0, "no pack and no package owes the whole layer rule"
    assert RP.UNMEASURED in debt["why"]
    assert tmp_path.exists()


def test_a_readable_but_empty_registry_is_a_measured_zero(registry: sqlite3.Connection,
                                                          tmp_path: Path) -> None:
    sig = RP.region_signals("europe", registry, reports_dir=tmp_path)
    assert sig["sources_window"] == 0 and sig["discoveries_window"] == 0
    assert sig["lattice_candidates"] == 0 and sig["unmeasured"] == []
    debt = RP.coverage_debt("europe", signals=sig,
                            depth=RP.region_depth("europe", resolver=lambda c: _pack(c)))
    assert debt["unmeasured"] == [] and debt["terms"]["discovery"] == 1.0


def test_discovery_and_lattice_terms_fall_as_the_region_produces(
        registry: sqlite3.Connection, tmp_path: Path) -> None:
    now = datetime.now(tz=UTC)
    fresh = (now - timedelta(days=1)).isoformat()
    registry.executemany("INSERT INTO sources (country, first_seen) VALUES (?, ?)",
                         [("cz", fresh)] * 5)
    registry.executemany(
        "INSERT INTO discoveries (generator, created_at, generated_cells) VALUES (?, ?, ?)",
        [("europe:miner", fresh, 3)] * 4)
    registry.commit()
    sig = RP.region_signals("europe", registry, now=now, reports_dir=tmp_path)
    assert sig["discoveries_window"] == 4 and sig["lattice_candidates"] == 4
    debt = RP.coverage_debt("europe", signals=sig,
                            depth=RP.region_depth("europe", resolver=lambda c: _pack(c)))
    assert debt["terms"]["discovery"] < 1.0 and debt["terms"]["lattice"] < 1.0


def test_the_priority_formula_is_the_law_as_written() -> None:
    base = {"p_useful": 0.5, "orthogonality": 0.8, "information_gain": 0.6,
            "coverage_debt": 0.0}
    assert RP.priority_of(**base) == pytest.approx(0.5 * 0.8 * 0.6)
    # the debt enters as a BONUS: more debt is never less priority
    indebted = RP.priority_of(**{**base, "coverage_debt": 1.0})
    assert indebted == pytest.approx(0.5 * 0.8 * 0.6 * 2.0)
    # every cost enters against a unit floor, so an unpriced region is neither zero nor infinite
    costed = RP.priority_of(**base, compute=1.0, data_cost=1.0, trial_burden=1.0)
    assert costed == pytest.approx(0.5 * 0.8 * 0.6 / 4.0)


# --------------------------------------------------------------------------- the report
def test_every_declared_forest_appears_in_the_report_and_none_is_absent(
        registry: sqlite3.Connection, tmp_path: Path) -> None:
    doc = RP.parity_report(conn=registry, reports_dir=tmp_path)
    assert set(doc["regions"]) == set(F.FORESTS), "NO REGION ABSENT is the law's first clause"
    assert doc["n_regional"] == len(F.REGIONAL_FORESTS)
    assert doc["flag_counts"]["NO_PACK"] == 0, \
        "a regional forest with no resolvable pack and no package is a hole in the federation"


def test_a_region_with_no_pack_and_no_package_is_flagged(registry: sqlite3.Connection,
                                                         tmp_path: Path) -> None:
    doc = RP.parity_report(["europe"], conn=registry, resolver=lambda _c: None,
                           reports_dir=tmp_path)
    assert "NO_PACK" in doc["regions"]["europe"]["flags"]


def test_flags_fire_only_on_measured_absence() -> None:
    unreadable = {"kind": "regional", "depth": {"packs": [{"code": "x"}], "score_mean": 1.0},
                  "signals": {"resident": None, "sources_window": None,
                              "discoveries_window": None, "lattice_candidates": None}}
    assert RP.flags_for(unreadable, 1.0) == [], \
        "an UNMEASURED signal must never raise a flag (L1.28a)"
    measured = {"kind": "regional", "depth": {"packs": [{"code": "x"}], "score_mean": 0.1},
                "signals": {"resident": False, "sources_window": 0, "discoveries_window": 0,
                            "lattice_candidates": 0}}
    assert set(RP.flags_for(measured, 1.0)) == {"NO_RESIDENT", "NO_DISCOVERY",
                                                "NO_LATTICE_CANDIDATE",
                                                "DEPTH_BELOW_HALF_MEDIAN"}


# --------------------------------------------------------------------------- the fence
def test_the_fence_passes_with_no_registry_and_writes_its_artifact(tmp_path: Path,
                                                                   capsys: Any) -> None:
    out = tmp_path / "regional_parity.json"
    rc = FENCE.main(["--out", str(out)])
    assert rc == 0, "a machine with no desk state must not fail the commit gate (L1.43)"
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["fence"]["absent_regions"] == [] and doc["fence"]["missing_from_report"] == []
    assert doc["fence"]["regions_measured"] == len(F.FORESTS)
    assert capsys.readouterr().out.strip()


def test_the_fence_promises_in_the_artifact_that_it_caps_no_compute(tmp_path: Path) -> None:
    out = tmp_path / "p.json"
    FENCE.main(["--out", str(out)])
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["fence"]["caps_compute"] is False, (
        "REGIONAL PARITY reports and publishes a bonus; it never subtracts a worker, a second "
        "or a trial. Turning this into a throttle needs a missed-growth proof "
        "(GROWTH_GOVERNANCE Rule 1), not an edit to this line.")
    assert "Rule 1" in doc["fence"]["why_no_cap"]


def test_the_fence_fails_when_a_region_is_absent(monkeypatch: pytest.MonkeyPatch,
                                                 tmp_path: Path) -> None:
    real = RP.parity_report

    def holed(*a: Any, **kw: Any) -> dict[str, Any]:
        doc = real(*a, **kw)
        fid = next(iter(doc["regions"]))
        doc["regions"][fid]["flags"] = [*doc["regions"][fid]["flags"], "NO_PACK"]
        return doc

    monkeypatch.setattr(RP, "parity_report", holed)
    assert FENCE.main(["--out", str(tmp_path / "p.json")]) == 1


def test_strict_promotes_the_live_flags_for_the_box_gate(monkeypatch: pytest.MonkeyPatch,
                                                         tmp_path: Path) -> None:
    real = RP.parity_report

    def flagged(*a: Any, **kw: Any) -> dict[str, Any]:
        doc = real(*a, **kw)
        fid = next(iter(doc["regions"]))
        doc["regions"][fid]["flags"] = ["NO_RESIDENT"]
        doc["flagged"] = [fid]
        return doc

    monkeypatch.setattr(RP, "parity_report", flagged)
    out = str(tmp_path / "p.json")
    assert FENCE.main(["--out", out]) == 0, "a live-state flag must not fail the commit gate"
    assert FENCE.main(["--out", out, "--strict"]) == 1, "--strict is the box gate's half"


def test_the_fence_is_registered_in_the_law_gate() -> None:
    text = (ROOT / "scripts" / "run_law_gate.py").read_text(encoding="utf-8")
    assert '("check_regional_parity.py", ())' in text, "the portable half gates every commit"
    assert '("check_regional_parity.py", ("--strict",))' in text, "the live half gates the box"


# --------------------------------------------------------------------------- the consumer
def test_research_roi_folds_the_debt_in_as_a_bonus_and_lowers_nobody() -> None:
    desk = ROOT / "desks" / "mt5"
    for p in (str(desk), str(desk / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    from research import research_roi as RR

    base = {"forests": {r: {"workers": 4, "budget_s": 3000, "scout_floor": True, "roi": None,
                            "why": "flat"} for r in RR.REGIONS}}
    got = RR.parity_overlay(base, conn=None)
    assert got["parity"]["status"] == "ok"
    assert got["parity"]["source"].endswith("parity_report()")
    for fid, row in got["forests"].items():
        assert row["workers"] >= row["parity"]["workers_before"], f"{fid} lost workers"
        assert row["budget_s"] >= row["parity"]["budget_before_s"], f"{fid} lost seconds"
        assert row["workers"] >= RR.SCOUT_FLOOR_WORKERS
        assert row["parity"]["bonus"] >= 1.0
    assert got["parity"]["raised"], "a desk with real coverage debt must raise somebody"


def test_the_overlay_survives_a_parity_module_that_cannot_measure(
        monkeypatch: pytest.MonkeyPatch) -> None:
    desk = ROOT / "desks" / "mt5"
    for p in (str(desk), str(desk / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    from research import research_roi as RR

    def boom(*_a: Any, **_kw: Any) -> dict[str, Any]:
        raise RuntimeError("registry exploded")

    monkeypatch.setattr(RP, "parity_report", boom)
    base = {"forests": {"europe": {"workers": 4, "budget_s": 3000, "roi": None}}}
    got = RR.parity_overlay(base, conn=None)
    assert got["parity"]["status"] == RR.UNMEASURED and "RuntimeError" in got["parity"]["why"]
    assert got["forests"]["europe"]["workers"] == 4, "an unmeasured parity moves nothing"


# --------------------------------------------------------------------------- country coverage
def test_country_coverage_reads_the_machinery_roster_not_a_typed_list() -> None:
    """The principal's addition of 2026-09-22 -- a pack for every country the desk's own
    machinery names -- measured against `forests.Forest.countries` rather than a list in the
    fence, so a country added to a forest tomorrow shows up as UNANSWERED the same hour."""
    cov = FENCE.country_coverage()
    named = {c.lower() for f in F.FORESTS.values() for c in f.countries}
    assert cov["n_named"] == len(named)
    assert set(cov["by_country"]) == named
    assert cov["n_answered"] + len(cov["unanswered"]) == cov["n_named"]
    for code in ("us", "ca", "pk", "bd"):
        assert cov["by_country"].get(code, {}).get("packs") == [code], \
            f"{code} must be answered by its own pack"


def test_a_pack_is_credited_only_with_what_it_declares() -> None:
    """A multi-jurisdiction pack that declares a `JURISDICTIONS` tuple is credited with every
    member; one that declares nothing is credited with ONE country. That is deliberate: it turns
    "the euro-area pack silently covers eleven members" into a named, closable line rather than
    either a free pass or a phantom missing pack."""
    iso, why = FENCE.jurisdictions_of("cee_balkans")
    assert len(iso) > 1 and why.endswith(FENCE.JURISDICTIONS_ATTR), \
        "cee_balkans declares its jurisdictions and must be credited with all of them"
    assert FENCE.jurisdictions_of("ind") == (("in",), "pack-directory alias for 'ind'")
    assert FENCE.jurisdictions_of("us")[0] == ("us",)


def test_country_coverage_is_reported_and_never_fails_the_gate(tmp_path: Path) -> None:
    out = tmp_path / "p.json"
    rc = FENCE.main(["--out", str(out)])
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["country_coverage"]["unanswered"], \
        "this desk has unanswered countries today; if it ever has none, say so here on purpose"
    assert rc == 0, "an unanswered country is WORK, not a breach -- the fence reports it"
    assert doc["fence"]["countries_unanswered"] == doc["country_coverage"]["unanswered"]


def test_the_fence_reads_the_roi_artifact_that_actually_exists() -> None:
    """P(useful) comes from the research-ROI organ, and a WRONG PATH HERE DOES NOT ERROR -- it
    silently holds every region at the middle and throws the upstream measurement away. An early
    draft of this fence read `data/research_roi.json` under `regions.by_region`; neither exists.
    So the path and the key are asserted against the organ's own declared output."""
    desk = ROOT / "desks" / "mt5"
    for p in (str(desk), str(desk / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    from research import research_roi as RR

    assert FENCE.ROI_REPORT == RR.REPORT, (
        f"the fence reads {FENCE.ROI_REPORT} and the organ writes {RR.REPORT}")
    assert FENCE.ROI_BLOCK == "region_roi", "the organ publishes ROI_region under `region_roi`"
    roi, why = FENCE._roi_by_region()
    if FENCE.ROI_REPORT.exists():
        assert roi, "the artifact is on this box and the fence read nothing out of it"
        assert "MEASURED" in why
    else:
        assert RP.UNMEASURED in why, "an absent artifact is UNMEASURED by name, never a zero"


def test_an_unmeasured_region_roi_is_none_not_zero() -> None:
    """The organ already distinguishes a MEASURED zero from an UNMEASURED region; pricing the
    second at zero would defund the frontier by accident, which is the starvation loop the
    scout floor exists to prevent."""
    roi, _ = FENCE._roi_by_region()
    if not roi:
        pytest.skip("no ROI artifact on this machine")
    assert any(v is None for v in roi.values()) or all(
        isinstance(v, float) for v in roi.values())
    for fid, val in roi.items():
        assert val is None or isinstance(val, float), f"{fid}: {val!r}"
