"""No test writes the real lineage store or ack log (2026-11-05, caught on #759)."""
from __future__ import annotations

from pathlib import Path

from libs.ops.control_plane import edges, lease, watermarks

DATA = Path(__file__).resolve().parents[1] / "data"


def test_the_control_plane_defaults_point_outside_the_desk_during_tests() -> None:
    for p in (lease.ACK_LOG, edges.LINEAGE_DB, watermarks.WATERMARK_DIR):
        assert DATA not in p.parents, p


def test_a_default_store_write_lands_in_tmp_not_the_desk() -> None:
    real_db = DATA / "lineage.sqlite"
    before = real_db.stat().st_mtime_ns if real_db.exists() else None
    conn = edges.connect()
    assert conn is not None
    conn.close()
    assert edges.LINEAGE_DB.exists()
    after = real_db.stat().st_mtime_ns if real_db.exists() else None
    assert before == after
