

class TestLedgerLockSerializesWriters:
    """R0623: two concurrent read-modify-writes must both survive (measured 2026-08-19:
    interleaved sessions destroyed three rows and reverted two dispositions in one day)."""

    def test_parallel_adds_both_land(self, tmp_path, monkeypatch):
        import json
        import multiprocessing as mp
        import sys


        ledger = tmp_path / "ledger.json"
        ledger.write_text(json.dumps({"recommendations": []}), "utf-8")

        def worker(n: int) -> None:
            from scripts import recommendations as r
            r.LEDGER = ledger
            r._LOCK = tmp_path / ".lock"
            r.SWEEPS = tmp_path / "sweeps.jsonl"
            sys.argv = ["recommendations.py", "add", "--source", "cycle",
                        "--summary", f"concurrency probe row {n} " + "x" * 30]
            try:
                r.main()
            except SystemExit as e:
                if e.code not in (None, 0):
                    raise

        procs = [mp.Process(target=worker, args=(i,)) for i in range(4)]
        for p in procs:
            p.start()
        for p in procs:
            p.join(30)
        rows = json.loads(ledger.read_text("utf-8"))["recommendations"]
        assert len(rows) == 4, (
            f"{len(rows)}/4 adds survived -- a lost row is the exact last-writer-wins "
            "race the flock exists to close")
        assert len({r["id"] for r in rows}) == 4, "duplicate ids: the id race is back"

    def test_lock_refuses_loudly_when_wedged(self, tmp_path, monkeypatch):
        import fcntl

        import pytest as _pytest

        from scripts import recommendations as reco

        monkeypatch.setattr(reco, "_LOCK", tmp_path / ".lock")
        holder = (tmp_path / ".lock").open("w")
        fcntl.flock(holder, fcntl.LOCK_EX)
        try:
            with _pytest.raises(SystemExit, match="REFUSING: could not lock"):
                reco._locked(timeout_s=0.3)
        finally:
            holder.close()
