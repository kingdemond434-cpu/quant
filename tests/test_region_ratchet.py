"""PER-REGION CELLS AND JUDGED CELLS: the ladder that finds them and the ratchet that holds them.

THE DEFECT THESE PIN (measured 2026-09-23 on the trading box). 216,641 of 323,542 cells carried a
`miner:` filing prefix; `attribution.region_of` and `attribution.is_non_regional` both read that
prefix as part of the producer's NAME, so `miner:discovery_compiler` (190,766 rows of the desk's
own compiler) could not be recognised as desk machinery and `miner:asia:rba_tables` (the Reserve
Bank of Australia) could not be recognised as Oceania. Every region but two read ZERO cells while
a third of a million cells sat in the registry. The cells were produced and lost on a join.

Two properties are under test and they are not the same property:

    THE LADDER   a producer filed under a namespace still reaches its ground, and a producer that
                 is desk machinery is NOT_REGIONAL (a verdict) rather than UNATTRIBUTABLE (a gap)
    THE RATCHET  per-region cells and per-region JUDGED cells go up and never down, and the count
                 of regions the desk NAMES never falls -- no ratio is improved by shrinking its
                 denominator
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "desks" / "mt5" / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import attribution as A  # noqa: E402
from scripts import check_region_ratchet as F  # noqa: E402


# --------------------------------------------------------------------------------- the ladder
def test_filing_namespace_does_not_hide_a_desk_organ() -> None:
    """`miner:discovery_compiler` is the desk's own compiler filed under the graph's vocabulary."""
    for name in ("miner:discovery_compiler", "seat:discovery_compiler", "src:pack_cells",
                 "miner:sandbox:alpha101"):
        a = A.attribute(generator=name)
        assert a.region == A.NOT_REGIONAL, name
        assert a.attributed and not a.regional, name
    # and the bare organ still works, so nothing that resolved before stopped resolving
    assert A.attribute(generator="discovery_compiler").region == A.NOT_REGIONAL


def test_filing_namespace_does_not_hide_a_region() -> None:
    assert A.attribute(generator="miner:japan:gotobi").region == "Japan"
    assert A.attribute(generator="seat:korea_scout").region == "Korea"


def test_producer_reaches_the_ground_its_own_registry_declares() -> None:
    """The join that existed and was never made: `miner:asia:<pack>` -> that pack's declared URL.

    Skipped rather than asserted-empty when the desk registry is absent: UNMEASURED is a real
    answer and a test that silently passes on an empty index measures nothing (L1.28a).
    """
    idx = A.ground_index()
    if not idx:
        import pytest
        pytest.skip(f"{A.UNMEASURED}: no ground registry on this host")
    # every entry resolves to a REAL region, never to a placeholder
    assert all(v in A.REGIONS for v in idx.values())
    hit = next(k for k in idx if not k.startswith("asia:"))
    assert A.attribute(generator=f"miner:asia:{hit}").region == idx[hit]
    assert A.attribute(generator=hit).region in A.REGIONS


def test_region_of_url_reads_a_cctld_and_refuses_a_generic_tld() -> None:
    assert A.region_of_url("https://www.rba.gov.au/statistics/") == "Oceania"
    assert A.region_of_url("https://www.riksbank.se/en-gb/") == "Europe"
    assert A.region_of_url("http://www.pbc.gov.cn/x/index.html") == "China"
    assert A.region_of_url("https://www.myfxbook.com/outlook") is None   # no jurisdiction
    assert A.region_of_url("") is None


def test_two_letter_code_is_never_taken_from_an_underscore_split() -> None:
    """`is_regional` is not Iceland and `in_sample` is not India -- a snake head is a word."""
    for name in ("is_regional", "in_sample", "at_risk", "no_trade", "by_symbol"):
        assert A.region_of(name) is None, name
    # the code position still works
    assert A.region_of("is") == "Europe"
    assert A.region_of("in") == "India"


def test_region_command_crosswalk_is_whole_token_only() -> None:
    """The pack vocabulary joins the census vocabulary, and cannot be reached by a name split."""
    assert A.region_of_command("RUSSIA_CIS") == "Russia/CIS"
    assert A.region_of_command("SOUTHEAST_ASIA") == "SEA"
    assert A.region_of_command("MEA") == "Africa"
    assert A.region_of_command("UNMAPPED") is None
    # the crosswalk must not leak into producer-name resolution
    assert A.region_of("miner:asia:tfx_open_interest") != "SEA"


def test_no_region_is_ever_removed_from_the_denominator() -> None:
    """Every code in the table names a region the desk declares; REGIONS is the denominator."""
    assert len(A.REGIONS) == len(set(A.REGIONS))
    assert set(A.REGION_OF_CODE.values()) <= set(A.REGIONS)
    assert set(A.REGION_COMMAND_TO_REGION.values()) <= set(A.REGIONS)
    for code in A.NAME_TO_CODE.values():
        assert code in A.REGION_OF_CODE, code


def test_unattributable_is_still_declared_and_never_swallowed_by_not_regional() -> None:
    """A producer the desk does not know stays a NAMED GAP; honesty is the point of the bucket."""
    a = A.attribute(generator="some_organ_nobody_declared")
    assert (a.region, a.producer) == (A.UNATTRIBUTABLE, "some_organ_nobody_declared")
    assert a.why


# -------------------------------------------------------------------------------- the spread
def test_region_spread_counts_every_named_region_including_the_empty_ones() -> None:
    sp = A.region_spread({"Japan": 10, "Europe": 5, "NOT_REGIONAL": 999})
    assert sp["regions_named"] == len(A.REGIONS)
    assert sp["regions_holding"] == 2
    assert sp["total"] == 15                      # NOT_REGIONAL is not a region and is excluded
    assert "China" in sp["regions_empty"]
    assert 0.0 < float(sp["evenness"]) < 1.0
    flat = A.region_spread(dict.fromkeys(A.REGIONS, 7))
    assert flat["evenness"] == 1.0 and not flat["regions_empty"]


def test_region_spread_of_nothing_is_unmeasured_not_zero() -> None:
    assert A.region_spread({})["evenness"] == A.UNMEASURED


# ------------------------------------------------------------------------------- the ratchet
def _ratchet(tmp: Path, current: dict[str, dict[str, int]]) -> dict[str, object]:
    from attribution_census import ratchet
    return ratchet(current, path=tmp / "REGION_RATCHET.json")


def test_high_water_never_falls_and_a_fall_to_zero_is_named(tmp_path: Path) -> None:
    first = _ratchet(tmp_path, {"unique_cells": {"Japan": 10, "Europe": 4},
                                "judged_cells": {"Japan": 2}})
    assert first["status"] == "OK"
    second = _ratchet(tmp_path, {"unique_cells": {"Japan": 12, "Europe": 0},
                                 "judged_cells": {"Japan": 2}})
    m = second["measures"]["unique_cells"]                          # type: ignore[index]
    assert m["high_water"]["Europe"] == 4 and m["high_water"]["Japan"] == 12
    assert m["fell_to_zero"] == ["Europe"]
    assert second["status"] == "FALLEN"


def test_a_non_zero_dip_is_reported_and_does_not_fail_the_fence(tmp_path: Path) -> None:
    _ratchet(tmp_path, {"unique_cells": {"Japan": 10}, "judged_cells": {}})
    doc = _ratchet(tmp_path, {"unique_cells": {"Japan": 9, "Europe": 3}, "judged_cells": {}})
    m = doc["measures"]["unique_cells"]                             # type: ignore[index]
    assert m["regressions"] == [{"region": "Japan", "high_water": 10, "now": 9}]
    assert not m["fell_to_zero"]
    v = F.verdict(doc, require_state=True)                          # type: ignore[arg-type]
    assert not v["failures"] and v["status"] == "OK"
    assert any("Japan" in r for r in v["reported"])


def test_fence_fails_on_a_region_at_zero_and_on_a_shrinking_denominator() -> None:
    doc = {"regions_named": len(A.REGIONS), "regions_named_high_water": len(A.REGIONS) + 1,
           "measures": {"unique_cells": {"fell_to_zero": ["Europe"], "total": 1,
                                         "total_high_water": 9, "total_fell": True,
                                         "regressions": [], "spread": {}},
                        "judged_cells": {"fell_to_zero": [], "total": 1, "total_high_water": 1,
                                         "total_fell": False, "regressions": [], "spread": {}}}}
    v = F.verdict(doc, require_state=True)
    assert v["status"] == "BREACH"
    joined = " ".join(v["failures"])
    assert "Europe" in joined and "FEWER REGIONS" in joined and "total" in joined


def test_absent_artifact_is_unmeasured_in_ci_and_fails_on_the_box() -> None:
    assert F.verdict({}, require_state=False)["status"] == A.UNMEASURED
    assert not F.verdict({}, require_state=False)["failures"]
    assert F.verdict({}, require_state=True)["failures"]


def test_the_fence_caps_nothing() -> None:
    """Pinned: this fence publishes a debt and never refuses, throttles or trims a denominator."""
    assert F.verdict({}, require_state=False)["caps_nothing"] is True
    src = (ROOT / "scripts" / "check_region_ratchet.py").read_text(encoding="utf-8")
    # READ-ONLY BY CONSTRUCTION: a fence that can rewrite the artifact it judges can clear itself.
    code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    for writer in ("write_text", "os.replace", "mkdir", "executemany", "commit()"):
        assert writer not in code, writer
    # and it neither measures the registry itself nor imports anything that could size a budget
    assert "sqlite3" not in code and "connect(" not in code


def test_the_fence_is_wired_into_the_law_gate_battery() -> None:
    """UNWIRED IS A DEFECT (III.16): a fence nothing runs is a claim the desk cannot cash."""
    gate = (ROOT / "scripts" / "run_law_gate.py").read_text(encoding="utf-8")
    assert '("check_region_ratchet.py", ())' in gate
    assert '("check_region_ratchet.py", ("--require-state",))' in gate


def test_the_census_publishes_both_ratcheted_measures() -> None:
    import attribution_census as C
    src = (ROOT / "desks" / "mt5" / "research" / "attribution_census.py").read_text("utf-8")
    assert "judged_cells_by_region" in src and "ratchet(" in src
    assert C.MEASURES_ARE == ("unique_cells", "judged_cells")
    assert set(F.MEASURES) == set(C.MEASURES_ARE)


def test_a_run_against_another_registry_never_touches_the_production_ratchet(
        tmp_path: Path) -> None:
    """R0748's hazard in a new place: a census pass over a FIXTURE must not rewrite the desk's
    real high-water file. It did, and a synthetic registry of three rows reported every region as
    having fallen to zero -- a red gate manufactured by its own test suite."""
    import attribution_census as C
    db = tmp_path / "fixture.sqlite"
    db.write_bytes(b"")                      # unopenable: run() returns before it measures
    before = C.RATCHET.read_bytes() if C.RATCHET.exists() else None
    C.run(budget_s=5.0, db=tmp_path / "missing.sqlite")
    C.run(budget_s=5.0, db=db)
    after = C.RATCHET.read_bytes() if C.RATCHET.exists() else None
    assert after == before, "a fixture run rewrote desks/mt5/reports/REGION_RATCHET.json"


def test_ratchet_artifact_round_trips_as_json(tmp_path: Path) -> None:
    doc = _ratchet(tmp_path, {"unique_cells": {"Japan": 3}, "judged_cells": {"Japan": 1}})
    on_disk = json.loads((tmp_path / "REGION_RATCHET.json").read_text(encoding="utf-8"))
    assert on_disk["measures"]["unique_cells"]["high_water"]["Japan"] == 3
    assert on_disk["regions"] == list(A.REGIONS) == list(doc["regions"])  # type: ignore[index]
