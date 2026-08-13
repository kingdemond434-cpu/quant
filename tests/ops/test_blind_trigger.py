"""The blind-rediscovery trigger's actuator: stamp() must be refusable, and counts() is
the ONE rule both the detector and the actuator share.

The defect this pins: blind-rediscovery-due-by-state fired for weeks after runs 1 and 2
because nothing programmatic wrote the baseline -- the trigger diffed today's world
against a 2026-07-19 snapshot and demanded digs over ground fresh eyes had already seen.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from libs.ops.blind_trigger import ARTIFACT, BASELINE, STATE, counts, stamp


def _seed(root: Path, *, sources: int = 3, grave_rows: int = 2) -> None:
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "docs/research").mkdir(parents=True, exist_ok=True)
    (root / "data/data_universe_map.json").write_text(
        json.dumps({"sources": {f"s{i}": {} for i in range(sources)}}), "utf-8")
    (root / "docs/graveyard.md").write_text(
        "# graveyard\n" + "\n".join(f"| row{i} | dead |" for i in range(grave_rows)) + "\n",
        "utf-8")


def test_counts_reads_both_meters(tmp_path: Path) -> None:
    _seed(tmp_path, sources=5, grave_rows=7)
    assert counts(tmp_path) == (5, 7)


def test_counts_treats_unreadable_as_zero_the_loud_direction(tmp_path: Path) -> None:
    # No universe map, no graveyard: 0/0 makes the NEXT delta maximal, so the fence cries
    # rather than sleeps -- parity with the detector's default-{} reads.
    assert counts(tmp_path) == (0, 0)


def test_stamp_refuses_without_production(tmp_path: Path) -> None:
    _seed(tmp_path)
    out = stamp(tmp_path, min_artifact_ts=0.0)
    assert out.startswith("REFUSED") and "absent" in out
    assert not (tmp_path / BASELINE).exists()

    art = tmp_path / ARTIFACT
    art.parent.mkdir(parents=True, exist_ok=True)
    art.write_text("run 1\n", "utf-8")
    out = stamp(tmp_path, min_artifact_ts=time.time() + 3600)
    assert out.startswith("REFUSED") and "did not advance" in out
    assert not (tmp_path / BASELINE).exists()


def test_stamp_writes_both_files_and_preserves_state(tmp_path: Path) -> None:
    _seed(tmp_path, sources=4, grave_rows=3)
    (tmp_path / STATE).write_text(json.dumps({"unrelated_duty": "keep-me"}), "utf-8")
    art = tmp_path / ARTIFACT
    art.parent.mkdir(parents=True, exist_ok=True)
    art.write_text("run 2 findings\n", "utf-8")

    out = stamp(tmp_path, min_artifact_ts=0.0, ts="2026-08-11T21:23:18+00:00")
    assert out.startswith("stamped")

    state = json.loads((tmp_path / STATE).read_text("utf-8"))
    assert state["last_blind_rediscovery"] == "2026-08-11T21:23:18+00:00"
    assert state["unrelated_duty"] == "keep-me", "stamp clobbered a sibling's cadence state"

    base = json.loads((tmp_path / BASELINE).read_text("utf-8"))
    assert (base["sources"], base["graveyard"]) == (4, 3)
    assert base["stamped"] == "2026-08-11T21:23:18+00:00"
