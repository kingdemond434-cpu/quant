"""The window query uses the created_at index and keeps every row the exact cut keeps."""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts import check_producer_yield as CPY


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "reg.sqlite"
    con = sqlite3.connect(db)
    con.execute("create table discoveries(discovery_id text primary key, generator text)")
    con.execute("create table research_candidates(id integer primary key, discovery_id text,"
                " generator text, family text, symbol text, horizon text, grid_cell text,"
                " content_hash text, donated_cell text, status text, created_at text)")
    con.execute("create index ix_candidates_created_at on research_candidates(created_at)")
    now = datetime.now(UTC)
    rows = []
    for i, hours in enumerate((1, 5, 23, 25, 30, 48, 400)):
        ts = now - timedelta(hours=hours)
        fmt = "%Y-%m-%dT%H:%M:%S" if i % 2 else "%Y-%m-%d %H:%M:%S"
        rows.append((f"d{i}", "g", "fam", "EURUSD", "h1", f"gc{i}", f"h{i}", None, "judged",
                     ts.strftime(fmt)))
    con.executemany("insert into research_candidates(discovery_id, generator, family, symbol,"
                    " horizon, grid_cell, content_hash, donated_cell, status, created_at)"
                    " values (?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()
    return db


def test_both_spellings_inside_the_window_are_kept(tmp_path):
    out = CPY._window_cells(24.0, db=_db(tmp_path))
    assert out["available"]
    assert out["per"]["g"]["cells_emitted"] == 3  # 1h, 5h, 23h; 25h+ are outside


def test_the_window_query_can_use_the_created_at_index(tmp_path):
    db = _db(tmp_path)
    con = sqlite3.connect(db)
    plan = " ".join(str(r) for r in con.execute(
        "explain query plan select count(*) from research_candidates c "
        "where c.created_at >= ? and replace(substr(c.created_at,1,19),' ','T') >= ?",
        ("2026-01-01", "2026-01-01T00:00:00")))
    con.close()
    assert "ix_candidates_created_at" in plan
