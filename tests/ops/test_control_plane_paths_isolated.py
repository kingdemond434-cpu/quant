"""A test never writes the box's control-plane ack log or lineage DB (2026-11-14, #1168)."""

from __future__ import annotations

from pathlib import Path

from libs.ops.control_plane import edges, lease

DATA = Path(__file__).resolve().parents[2] / "desks" / "mt5" / "data"


def test_the_ack_log_and_lineage_db_are_redirected_out_of_the_checkout() -> None:
    for p in (Path(lease.ACK_LOG), Path(edges.LINEAGE_DB)):
        assert not p.resolve().is_relative_to(DATA.resolve()), p
