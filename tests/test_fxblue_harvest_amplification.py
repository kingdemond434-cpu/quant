"""FX Blue harvest: staging must not republish prior runs, and the artifact must stay bounded.

Measured live 2026-09-04: the miner staged into ONE fixed filename opened in append mode, then
published by appending the WHOLE staging file to the tracked artifact. Run N therefore
republished every row from runs 1..N -- quadratic growth. 57 timer runs of 60 handles produced
60*(1+2+...+57) = 99,180 rows for 4,805 distinct handles and 4.0 GB on a disk with 2.7 GB free.
Nothing errored, and every per-run log line reported the correct 60.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

MINER = Path(__file__).resolve().parents[1] / "desks/mt5/scripts/fxblue_track_record_miner.py"


def _load(path: Path) -> list[dict[str, object]]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def test_staging_path_is_per_run_not_a_fixed_name() -> None:
    """A fixed staging name + append mode is the amplification; the name must vary per run."""
    src = MINER.read_text()
    assert 'stage_path = stage_dir / f"{out_path.name}.staging"' not in src, (
        "fixed staging filename restored -- run N will republish runs 1..N (quadratic growth)"
    )
    assert "os.getpid()" in src, "staging filename must be unique per run"


def test_compaction_keeps_only_the_newest_record_per_handle(tmp_path: Path) -> None:
    """Compaction bounds the artifact at one lap and is lossless for the reader."""
    sys.path.insert(0, str(MINER.parent))
    from fxblue_track_record_miner import compact_latest

    art = tmp_path / "track_records_auto.jsonl"
    art.write_text(
        "\n".join(
            json.dumps({"user": u, "harvested_utc": t})
            for u, t in [("a", "1"), ("b", "1"), ("a", "2"), ("c", "1"), ("a", "3"), ("b", "2")]
        )
        + "\n"
    )
    rows_in, rows_out, bytes_in, bytes_out = compact_latest(art)
    assert (rows_in, rows_out) == (6, 3)
    assert bytes_out < bytes_in
    got = {r["user"]: r["harvested_utc"] for r in _load(art)}
    assert got == {"a": "3", "b": "2", "c": "1"}, "compaction must keep the NEWEST row per handle"


def test_compaction_is_idempotent_and_survives_a_corrupt_line(tmp_path: Path) -> None:
    sys.path.insert(0, str(MINER.parent))
    from fxblue_track_record_miner import compact_latest

    art = tmp_path / "a.jsonl"
    art.write_text('{"user": "a", "v": 1}\nnot json at all\n{"user": "a", "v": 2}\n')
    compact_latest(art)
    assert _load(art) == [{"user": "a", "v": 2}]
    assert compact_latest(art)[1] == 1


def test_compact_only_mode_runs_without_a_harvest(tmp_path: Path) -> None:
    art = tmp_path / "t.jsonl"
    art.write_text('{"user": "a", "v": 1}\n{"user": "a", "v": 2}\n')
    proc = subprocess.run(
        [sys.executable, str(MINER), "--compact-only", "--out", str(art)],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert _load(art) == [{"user": "a", "v": 2}]
