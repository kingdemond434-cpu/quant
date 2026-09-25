"""`batch()` MUST BIND EVERY WRITE DOOR THE DRAIN USES, AND THE DRAIN MUST OPEN ONE.

MEASURED ON THE TRADING BOX, 2026-09-24. `conversion_maximiser` examined 613 rows in 855 s of a
900 s budget. Its own classify-and-repair cost 0.7 ms a row -- 1.3 million rows' worth of
thinking inside that budget -- so 99.95% of the pass was not working, it was waiting for
SQLite's write lock: seven processes hold the registry open, and a no-op `BEGIN IMMEDIATE` probe
measured p50 0.1 ms with a 53.5 s tail. Against 16,967 debt arrivals an hour, 613 is a debt that
grows; the pass's own verdict read LOSING at 61,652 a pass.

`registry.batch` already existed for exactly this, and TWO THINGS KEPT IT OFF THE DRAIN.

  1. IT WAS BUILT FOR THE DONATION PATH AND ONLY THAT PATH. Its single caller is
     `proposer_common.py` (2026-09-23), and the three doors it binds -- `enqueue_candidate`,
     `record_discovery`, `set_discovery_state` -- are exactly the three that path writes. It
     worked perfectly there and was inert everywhere else; the drain never opened one.
  2. TWO OF THE DRAIN'S THREE DOORS COULD NOT BE BOUND AT ANY CHUNK SIZE. `mark_candidate` and
     `link` called `c.commit()` directly instead of `_commit`, so a repaired row -- enqueue,
     link, mark -- would still have taken the write lock twice per row even inside an open
     batch.

WHAT BATCHING ACTUALLY BUYS, MEASURED, BECAUSE THE OBVIOUS ANSWER IS WRONG. It is NOT fsync
amortisation. With no other writer in the way, this same three-write repair runs at 322 rows/s
committing per row and 276 rows/s batched -- batching is marginally SLOWER, because WAL at
synchronous=NORMAL does not fsync on commit and there is nothing to amortise. The live box runs
the identical code at 0.72 rows/s. The entire gap is the write LOCK: batching takes it about a
dozen times a pass instead of 1,839, so the 53.5 s tail is not drawn against once per row.


Neither half is a throttle, a cap or a refusal: they convert MORE rows inside the same budget
and discard none. These tests pin both, because the failure is invisible -- the drain keeps
working, it just never catches up, and the artifact reports it as a fact about the backlog.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from libs.moat import registry as R


@pytest.fixture
def reg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    p = tmp_path / "alpha_registry.sqlite"
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(p)
    yield p
    R.set_path(None)


def _seed(conn: sqlite3.Connection, n: int) -> list[str]:
    ids = []
    for i in range(n):
        cid, _ = R.enqueue_candidate(conn=conn, family="session_range_breakout",
                                     symbol=f"SYM{i}", params={"i": i}, origin="test")
        ids.append(cid)
    conn.commit()
    return ids


def _status(path: Path, cid: str) -> str | None:
    """Read through a SECOND connection: only COMMITTED state is visible to it."""
    other = sqlite3.connect(path, timeout=5)
    try:
        row = other.execute("SELECT status FROM research_candidates WHERE id=?", (cid,)).fetchone()
        return None if row is None else str(row[0])
    finally:
        other.close()


def test_mark_candidate_honours_an_open_batch(reg: Path) -> None:
    conn = R.connect()
    ids = _seed(conn, 3)
    try:
        with R.batch(conn, every=1000):          # chunk larger than the writes: nothing lands yet
            for cid in ids:
                R.mark_candidate(cid, "retired", conn=conn)
            assert _status(reg, ids[0]) != "retired", (
                "mark_candidate committed per row despite an open batch -- this is the door that "
                "made the conversion drain pay a write-lock acquisition it did not need")
        for cid in ids:
            assert _status(reg, cid) == "retired", "the batch must land everything on the way out"
    finally:
        conn.close()


def test_link_honours_an_open_batch(reg: Path) -> None:
    conn = R.connect()
    ids = _seed(conn, 2)
    try:
        with R.batch(conn, every=1000):
            R.link("cell", ids[0], "cell", ids[1], "conversion_repair", conn=conn)
            other = sqlite3.connect(reg, timeout=5)
            try:
                n = other.execute("SELECT COUNT(*) FROM provenance WHERE relation=?",
                                  ("conversion_repair",)).fetchone()[0]
            finally:
                other.close()
            assert n == 0, "link committed per edge despite an open batch"
        other = sqlite3.connect(reg, timeout=5)
        try:
            assert other.execute("SELECT COUNT(*) FROM provenance WHERE relation=?",
                                 ("conversion_repair",)).fetchone()[0] == 1
        finally:
            other.close()
    finally:
        conn.close()


def test_both_doors_commit_normally_with_no_batch_open(reg: Path) -> None:
    """`_commit` outside a batch IS `c.commit()`: every other caller is unchanged."""
    conn = R.connect()
    ids = _seed(conn, 1)
    try:
        R.mark_candidate(ids[0], "retired", conn=conn)
        assert _status(reg, ids[0]) == "retired", (
            "routing these doors through `_commit` must not defer a write for callers that "
            "never opened a batch")
    finally:
        conn.close()


def test_a_chunk_boundary_lands_the_chunk(reg: Path) -> None:
    conn = R.connect()
    ids = _seed(conn, 4)
    try:
        with R.batch(conn, every=2):
            R.mark_candidate(ids[0], "retired", conn=conn)
            R.mark_candidate(ids[1], "retired", conn=conn)      # chunk of 2 closes here
            assert _status(reg, ids[1]) == "retired", (
                "a closed chunk must be durable: the whole point of chunking is that the writer "
                "hands the write lock back, so other producers are never shut out")
    finally:
        conn.close()


def test_the_conversion_drain_opens_a_batch() -> None:
    """The organ that owes the debt must actually use the door. Source-level, because the
    alternative is a live registry and seven competing writers."""
    src = (Path(__file__).resolve().parents[2] / "desks" / "mt5" / "research"
           / "conversion_maximiser.py").read_text(encoding="utf-8")
    assert "R.batch(conn, every=BATCH_WRITES)" in src, (
        "conversion_maximiser must open a registry batch around its convert loop; without it "
        "every repaired row pays three write-lock acquisitions and the drain cannot scale")
    assert "BATCH_WRITES" in src
    head = src.index("supply = _Waves(")
    assert src.index("R.batch(conn, every=BATCH_WRITES)") > head, (
        "the batch must wrap the convert loop, not some earlier phase")


def test_batching_is_not_a_cap_a_veto_or_a_refusal() -> None:
    """GROWTH GOVERNANCE. This change converts MORE rows in the same budget and refuses none:
    no row cap was lowered, no budget shrunk, no blocker class newly parked."""
    src = (Path(__file__).resolve().parents[2] / "desks" / "mt5" / "research"
           / "conversion_maximiser.py").read_text(encoding="utf-8")
    assert "BUDGET_S = 900.0" in src, "the pass budget must not shrink"
    assert "MAX_CARRY = 20_000" in src, "the carry must not shrink"
    assert "POOL_CEILING = 20000" in src or "POOL_CEILING = 20_000" in src
