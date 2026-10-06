

class TestLedgerLockSerializesWriters:
    """R0623: two concurrent read-modify-writes must both survive (measured 2026-08-19:
    interleaved sessions destroyed three rows and reverted two dispositions in one day)."""

    def test_parallel_adds_both_land(self, tmp_path, monkeypatch):
        import json
        import subprocess
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        ledger = tmp_path / "ledger.json"
        ledger.write_text(json.dumps({"recommendations": []}), "utf-8")
        driver = (
            "import sys;from pathlib import Path;"
            f"sys.path.insert(0,{str(root)!r});"
            "from scripts import recommendations as r;"
            f"r.LEDGER=Path({str(ledger)!r});"
            f"r._LOCK=Path({str(tmp_path / '.lock')!r});"
            f"r.SWEEPS=Path({str(tmp_path / 'sweeps.jsonl')!r});"
            "r._forecast_add=lambda *a:None;r._settle_forecasts=lambda *a:None;"
            "sys.argv=['recommendations.py','add','--source','cycle','--summary',"
            "'concurrency probe row '+sys.argv[1]+' '+'x'*30];r.main()"
        )
        procs = [subprocess.Popen([sys.executable, "-c", driver, str(i)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, cwd=root) for i in range(4)]
        try:
            for proc in procs:
                out, err = proc.communicate(timeout=30)
                assert proc.returncode == 0, out + err
        finally:
            for proc in procs:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=10)
                if proc.stdout is not None:
                    proc.stdout.close()
                if proc.stderr is not None:
                    proc.stderr.close()
        rows = json.loads(ledger.read_text("utf-8"))["recommendations"]
        assert len(rows) == 4, (
            f"{len(rows)}/4 adds survived -- a lost row is the exact last-writer-wins "
            "race the flock exists to close")
        assert len({r["id"] for r in rows}) == 4, "duplicate ids: the id race is back"

    def test_lock_refuses_loudly_when_wedged(self, tmp_path, monkeypatch):
        import pytest as _pytest

        from scripts import recommendations as reco

        monkeypatch.setattr(reco, "_LOCK", tmp_path / ".lock")
        holder = (tmp_path / ".lock").open("w")
        reco._flock_exclusive(holder)
        try:
            with _pytest.raises(SystemExit, match="REFUSING: could not lock"):
                reco._locked(timeout_s=0.3)
        finally:
            holder.close()
