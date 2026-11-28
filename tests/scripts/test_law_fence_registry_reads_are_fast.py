"""THE THREE REGISTRY FENCES READ WITHOUT THE WRITE PATH AND THROUGH THE INDEX (LG2, 2026-11-11).

Profiled on the trading box: check_producer_yield spent 305 s of 453 s in two full scans of an
8.4 GB research_candidates because its time predicate wrapped `created_at` in a function, and
check_family_evaluability / check_regional_parity count in 7 s / 17 s on a read-only connection
yet reached the law gate's 600 s timeout through `registry.connect()`, which evolves and commits
on every open. These pin: the window query uses `ix_candidates_created_at` and still counts both
timestamp separator forms; `connect_readonly` never writes and returns a real Connection; and
both fences open the registry through it.
"""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"_fence_{name}", ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _registry(path: Path, stamps: list[str]) -> None:
    con = sqlite3.connect(path)
    con.execute("create table discoveries (discovery_id text primary key, generator text)")
    con.execute("create table research_candidates (id text primary key, generator text, "
                "content_hash text, grid_cell text, status text, donated_cell text, "
                "family text, symbol text, horizon text, discovery_id text, created_at text)")
    con.execute("create index ix_candidates_created_at on research_candidates(created_at)")
    for i, at in enumerate(stamps):
        con.execute("insert into research_candidates values (?,?,?,?,?,?,?,?,?,?,?)",
                    (f"c{i}", "gen_a", f"h{i}", f"g{i}", "judged", None, "formula", "EURUSD",
                     "h1", None, at))
    con.commit()
    con.close()


def test_the_window_query_counts_both_separators_and_excludes_old_rows(tmp_path: Path) -> None:
    py = _load("check_producer_yield")
    now = datetime.now(UTC)
    recent = (now - timedelta(minutes=30))
    old = (now - timedelta(days=3))
    db = tmp_path / "reg.sqlite"
    _registry(db, [recent.strftime("%Y-%m-%dT%H:%M:%S"), recent.strftime("%Y-%m-%d %H:%M:%S"),
                   old.strftime("%Y-%m-%dT%H:%M:%S"), old.strftime("%Y-%m-%d %H:%M:%S")])
    out = py._window_cells(2.0, db=db)
    assert out["available"] is True, out["why"]
    assert out["per"]["gen_a"]["cells_emitted"] == 2


def test_the_window_predicate_reaches_the_created_at_index(tmp_path: Path) -> None:
    db = tmp_path / "reg.sqlite"
    _registry(db, [])
    src = (ROOT / "scripts" / "check_producer_yield.py").read_text("utf-8")
    assert "created_at >= ? and replace(substr(created_at,1,19),' ','T') >= ?" in src
    con = sqlite3.connect(db)
    plan = " ".join(str(r[-1]) for r in con.execute(
        "explain query plan select count(*) from research_candidates c "
        "where c.created_at >= ? and replace(substr(c.created_at,1,19),' ','T') >= ?",
        ("2026-11-11", "2026-11-11T00:00:00")))
    con.close()
    assert "ix_candidates_created_at" in plan, plan


def test_connect_readonly_never_writes_and_is_a_real_connection(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.moat import registry as R
    db = tmp_path / "alpha_registry.sqlite"
    _registry(db, ["2026-11-11T00:00:00"])
    before = db.read_bytes()
    monkeypatch.setattr(R, "_PATH", db)
    conn = R.connect_readonly()
    try:
        assert isinstance(conn, sqlite3.Connection)
        assert conn.execute("select count(*) from research_candidates").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("create table x (a int)")
    finally:
        conn.close()
    assert db.read_bytes() == before
    assert not (tmp_path / "alpha_registry.sqlite-wal").exists()


def test_connect_readonly_raises_on_a_missing_registry(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.moat import registry as R
    monkeypatch.setattr(R, "_PATH", tmp_path / "absent.sqlite")
    with pytest.raises(sqlite3.OperationalError):
        R.connect_readonly()
    assert not (tmp_path / "absent.sqlite").exists()


@pytest.mark.parametrize("script", ["check_family_evaluability", "check_regional_parity"])
def test_the_counting_fences_open_the_registry_read_only(script: str) -> None:
    src = (ROOT / "scripts" / f"{script}.py").read_text("utf-8")
    assert "connect_readonly()" in src
    assert "R.connect()" not in src and "conn = connect()" not in src
