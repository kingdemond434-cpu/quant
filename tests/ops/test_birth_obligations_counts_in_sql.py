"""The attribution axis gives the same verdict while the database does the counting.

Desk health, 2026-11-06: on the box check_birth_obligations.py ran past its 600 s law-gate
clock. The attribution axis built a Python string for every row born since the cut, across two
tables holding 2.9M rows; now SQL counts them and Python names only the unstamped ones. The old
derivation is kept below as the oracle, and the whole measurement is compared with it.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


NEW = _load("cbo_new", ROOT / "scripts" / "check_birth_obligations.py")


def _reference(root: Path) -> tuple[set[str], set[str]]:
    """The pre-2026-11-06 row walk: every row in the window named, stamped ones kept in ok."""
    from libs.research.attribution import BIRTH_OBLIGATION_FROM, PRODUCER_FIELD

    conn = sqlite3.connect(str(root / "data" / "alpha_registry.sqlite"))
    objects: set[str] = set()
    ok: set[str] = set()
    for table, idcol, prefix in (("research_candidates", "id", "cell"),
                                 ("discoveries", "discovery_id", "discovery")):
        rows = conn.execute(
            f"select {idcol}, coalesce({PRODUCER_FIELD},'') from {table} "  # noqa: S608
            f"where replace(substr(created_at,1,19),' ','T') >= ? "
            f"and replace(substr(created_at,1,19),' ','T') <= ?",
            (BIRTH_OBLIGATION_FROM[:19], "9999")).fetchall()
        for rid, who in rows:
            objects.add(f"{prefix}:{rid}")
            if str(who or "").strip():
                ok.add(f"{prefix}:{rid}")
    conn.close()
    return objects, ok


def _seed(root: Path) -> None:
    (root / "data").mkdir()
    conn = sqlite3.connect(str(root / "data" / "alpha_registry.sqlite"))
    conn.execute("create table research_candidates(id text, created_at text, producer text)")
    conn.execute("create table discoveries(discovery_id text, created_at text, producer text)")
    rows = [("old", "2026-01-01T00:00:00", ""), ("a", "2026-10-01T00:00:00", "fred_miner"),
            ("b", "2026-10-01 12:00:00", ""), ("c", "2026-10-02T00:00:00", "  \t"),
            ("d", "2026-10-03T00:00:00", None), ("e", "2026-10-04T00:00:00", "UNATTRIBUTABLE"),
            ("dup", "2026-10-05T00:00:00", ""), ("dup", "2026-10-05T00:00:01", "late_stamp"),
            ("nodate", None, "")]  # fmt: skip
    conn.executemany("insert into research_candidates values(?,?,?)", rows)
    conn.executemany("insert into discoveries values(?,?,?)",
                     [("x", "2026-10-01T00:00:00", ""), ("y", "2026-10-01T00:00:00", "p")])
    conn.commit()
    conn.close()


def test_the_counted_axis_equals_the_row_walk(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT))
    _seed(tmp_path)
    objects, ok, why = NEW._attribution(tmp_path)
    ref_objects, ref_ok = _reference(tmp_path)
    assert len(objects) == len(ref_objects) == 8
    assert sorted(objects - ok) == sorted(ref_objects - ref_ok)
    assert sorted(objects - ok) == ["cell:b", "cell:c", "cell:d", "discovery:x"]
    assert why.startswith(f"{len(ref_ok)}/{len(ref_objects)} cells and discoveries")
    assert bool(objects) is True
