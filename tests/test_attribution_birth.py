"""ATTRIBUTION AT BIRTH: the one helper, the two registry doors, the census and the fence clause.

The property under test is the one the gap was made of: a cell compiled by a pass-through organ
must still carry the REGION its parent discovery's source sat on. Everything else here is the
honesty discipline -- an unreachable lineage is DECLARED `UNATTRIBUTABLE` and never guessed at.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "desks" / "mt5" / "research") not in sys.path:
    sys.path.insert(0, str(ROOT / "desks" / "mt5" / "research"))

from libs.research import attribution as A  # noqa: E402


# ------------------------------------------------------------------------------- the one rule
def test_region_of_reads_codes_names_and_prefixes() -> None:
    assert A.region_of("japan:academic_scout") == "Japan"
    assert A.region_of("de") == "Europe"
    assert A.region_of("africa") == "Africa"
    assert A.region_of("institutional") == "Global/institutional"
    assert A.region_of("discovery_compiler") is None


def test_normalise_producer_collapses_paths_and_rejects_placeholders() -> None:
    assert A.normalise_producer("exe:desks/mt5/research/math_lab.py") == "math_lab"
    assert A.normalise_producer("  Japan:DataScout ") == "japan:datascout"
    for null in ("", "  ", "unknown", "_unattributed_generator", "UNATTRIBUTABLE"):
        assert A.normalise_producer(null) is None


def test_method_organ_is_not_regional_not_a_gap() -> None:
    a = A.attribute(generator="math:topology")
    assert (a.producer, a.region) == ("math:topology", A.NOT_REGIONAL)
    assert a.attributed and not a.regional
    # the SUB-producer of a desk organ counts too, or the gap is overstated by its whole output
    assert A.attribute(generator="discovery_compiler:interaction").region == A.NOT_REGIONAL


def test_nothing_reachable_is_declared_never_guessed() -> None:
    a = A.attribute()
    assert a.producer == A.UNATTRIBUTABLE and a.region == A.UNATTRIBUTABLE
    assert a.why == A.NO_PRODUCER_WHY and not a.attributed


def test_region_routes_in_order_and_records_which_fired() -> None:
    parent = A.attribute(generator="europe:bund_scout")
    assert parent.region == "Europe"
    child = A.attribute(generator="discovery_compiler", parent=parent)
    assert child.producer == "discovery_compiler"      # credit the organ that made the cell
    assert child.region == "Europe"                    # but the ground its lineage reached
    assert "region:lineage" in child.route
    by_source = A.attribute(generator="discovery_compiler", source_country="cz", source_id="s1")
    assert by_source.region == "Europe" and "source_country" in by_source.route


def test_coverage_keeps_the_two_declared_verdicts_apart() -> None:
    cov = A.coverage([{A.PRODUCER_FIELD: "japan:x", A.REGION_FIELD: "Japan"},
                      {A.PRODUCER_FIELD: "math:topology", A.REGION_FIELD: A.NOT_REGIONAL},
                      {A.PRODUCER_FIELD: A.UNATTRIBUTABLE, A.REGION_FIELD: A.UNATTRIBUTABLE}])
    assert cov["rows"] == 3 and cov["attributed"] == 2 and cov["regional"] == 1
    assert cov["not_regional"] == 1 and cov["unattributable_region"] == 1
    assert cov["producer_coverage"] == pytest.approx(2 / 3, abs=1e-4)


# ------------------------------------------------------------------------ the two birth doors
@pytest.fixture()
def registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> object:
    from libs.moat import registry as R
    monkeypatch.setattr(R, "_PATH", tmp_path / "alpha_registry.sqlite")
    monkeypatch.setattr(R, "BACKUP", tmp_path / "backup.sqlite")
    return R


def test_registry_stamps_both_doors_and_the_compiler_inherits_the_ground(registry: object) -> None:
    R = registry
    conn = R.connect()                                            # type: ignore[attr-defined]
    conn.execute("insert into sources(source_id,url,kind,country) "
                 "values('s1','http://x','web','cz')")
    conn.commit()
    did, _ = R.record_discovery(                                  # type: ignore[attr-defined]
        source_id="s1", source_type="web", mechanism="m", origin="EXTERNAL",
        generator="evidence_router")
    row = conn.execute("select producer, region from discoveries where discovery_id=?",
                       (did,)).fetchone()
    assert (row["producer"], row["region"]) == ("evidence_router", "Europe")

    cid, _ = R.enqueue_candidate(                                 # type: ignore[attr-defined]
        family="f", symbol="EURUSD", params={"a": 1}, origin="DESK",
        generator="discovery_compiler", discovery_id=did)
    got = conn.execute("select producer, region, attribution_route from research_candidates "
                       "where id=?", (cid,)).fetchone()
    # THE JOIN THAT WAS MISSING: the compiler is credited, the GROUND is Europe's.
    assert got["producer"] == "discovery_compiler"
    assert got["region"] == "Europe"
    assert "lineage" in got["attribution_route"]
    conn.close()


def test_registry_declares_when_nothing_names_a_producer(registry: object) -> None:
    R = registry
    conn = R.connect()                                            # type: ignore[attr-defined]
    cid, _ = R.enqueue_candidate(                                 # type: ignore[attr-defined]
        family="f", symbol="GBPUSD", params={"z": 9}, origin="")
    row = conn.execute("select producer, region from research_candidates where id=?",
                       (cid,)).fetchone()
    assert row["producer"] == A.UNATTRIBUTABLE and row["region"] == A.UNATTRIBUTABLE
    conn.close()


# ----------------------------------------------------------------------------- the census
def _seed(db: Path) -> None:
    from libs.moat import registry as R
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    R._evolve(conn)
    conn.execute("insert into sources(source_id,url,kind,country) values('s1','u','web','jp')")
    conn.execute("insert into discoveries(discovery_id,created_at,source_id,generator,state) "
                 "values('d1','2026-09-01T00:00:00+00:00','s1','japan:scout','UNPROCESSED')")
    for i, (gen, disc) in enumerate((("discovery_compiler", "d1"),
                                     ("math:topology", None), ("", None))):
        conn.execute(
            "insert into research_candidates(id,created_at,family,symbol,params_json,"
            "content_hash,status,generator,discovery_id,grid_cell) values(?,?,?,?,?,?,?,?,?,?)",
            (f"c{i}", "2026-09-01T00:00:00+00:00", "f", "EURUSD", "{}", f"h{i}", "queued",
             gen, disc, f"cell{i}"))
    conn.commit()
    conn.close()


def test_census_backfills_from_lineage_and_declares_the_rest(tmp_path: Path) -> None:
    import attribution_census as AC
    db = tmp_path / "alpha_registry.sqlite"
    _seed(db)
    doc = AC.run(budget_s=30.0, db=db)
    assert doc["available"] is True
    before, after = doc["before"]["candidates"], doc["after"]["candidates"]
    assert before["unstamped"] == 3 and before["attributed"] == 0
    assert after["attributed"] == 2 and after["unattributable_producer"] == 1
    # the compiled cell inherits Japan from the discovery's source; the method is NOT_REGIONAL
    regions = doc["unique_cells_by_region"]["by_region"]
    assert regions.get("Japan") == 1
    assert regions.get(A.NOT_REGIONAL) == 1
    assert doc["producer_region"]["regions"]["discovery_compiler"] == "Japan"


def test_census_is_idempotent_and_terminates(tmp_path: Path) -> None:
    import attribution_census as AC
    db = tmp_path / "alpha_registry.sqlite"
    _seed(db)
    first = AC.run(budget_s=30.0, db=db)
    second = AC.run(budget_s=30.0, db=db)
    # the second pass finds nothing left to stamp and reaches the same answer
    assert second["backfill"]["candidates"] == 1        # only the declared-unattributable row
    assert second["after"]["candidates"]["attributed"] == \
        first["after"]["candidates"]["attributed"]


def test_census_on_an_absent_registry_is_unmeasured_not_empty(tmp_path: Path) -> None:
    import attribution_census as AC
    doc = AC.run(budget_s=5.0, db=tmp_path / "missing.sqlite")
    assert doc["available"] is False and A.UNMEASURED in doc["why"]


def test_census_writes_its_artifact(tmp_path: Path) -> None:
    import attribution_census as AC
    db = tmp_path / "alpha_registry.sqlite"
    _seed(db)
    out = AC.write(AC.run(budget_s=30.0, db=db), path=tmp_path / "ATTRIBUTION_COVERAGE.json")
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["law"].startswith("EVERY CELL CARRIES ITS PRODUCER")
    assert doc["consumers"] and doc["birth_obligation_from"] == A.BIRTH_OBLIGATION_FROM


# ------------------------------------------------------------------------- the fence clause
def test_birth_obligation_axis_exists_and_reads_the_registry(tmp_path: Path) -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "cbo", ROOT / "scripts" / "check_birth_obligations.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cbo"] = mod          # @dataclass resolves annotations through sys.modules
    spec.loader.exec_module(mod)
    assert "attribution" in {ax.name for ax in mod.AXES}
    objects, ok, why = mod._attribution(tmp_path)
    assert not objects and mod.UNMEASURED in why          # absent registry is a verdict, not zero

    (tmp_path / "data").mkdir()
    db = tmp_path / "data" / "alpha_registry.sqlite"
    _seed(db)
    objects, ok, why = mod._attribution(tmp_path)
    # every seeded row predates the obligation cut, so none of them is an ARRIVAL
    assert not objects and mod.UNMEASURED in why

    conn = sqlite3.connect(str(db))
    conn.execute("insert into research_candidates(id,created_at,family,symbol,params_json,"
                 "content_hash,status,generator) values('new','2026-09-24T00:00:00+00:00','f',"
                 "'EURUSD','{}','hn','queued','x')")
    conn.commit()
    conn.close()
    objects, ok, why = mod._attribution(tmp_path)
    assert objects == {"cell:new"} and not ok            # born after the cut with no stamp
