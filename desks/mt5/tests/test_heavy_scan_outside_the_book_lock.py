"""The heavy clock publishes the book, then scans outside the book's lock (idea 604).

Measured 2026-11-11 05:36Z: the heavy pass held the one allocator lock through its candidate
scan (~50 min to 2 h), every 15-minute fast pass stood down behind it, and the live book aged to
123 minutes against a 90-minute contract. The book is now published under the lock with the
carried scan; the scan runs after, under its own lock, and the next pass of any clock carries it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, sample_worlds  # noqa: E402
from research import pf_allocator as pa  # noqa: E402


def test_the_deferred_scan_writes_a_scan_the_next_pass_carries(tmp_path: Path) -> None:
    rng = np.random.default_rng(1)
    ev = [SleeveEvidence(name=f"s{i}", daily_r=rng.normal(0.03 * (i + 1), 0.4, 300),
                         family="f", symbol=f"S{i}", forward_days=40, n_trials=5)
          for i in range(3)]
    cfg = WorldConfig(seed=2, n_worlds=48, n_rows=100)
    worlds = sample_worlds(ev, cfg)
    pa._SCAN_CONTEXT.clear()
    assert pa.deferred_scan(tmp_path / "scan.json") is None          # no context, no scan
    pa._SCAN_CONTEXT.update(ev=ev, worlds=worlds, cfg=cfg, funded={"s0": 0.1, "s1": 0.1},
                            bounds={e.name: 0.2 for e in ev}, total_heat=0.2, order={},
                            prev={}, seed=0)
    doc = pa.deferred_scan(tmp_path / "scan.json")
    pa._SCAN_CONTEXT.clear()
    assert doc is not None and doc["status"] == "MEASURED"
    on_disk = json.loads((tmp_path / "scan.json").read_text("utf-8"))
    assert on_disk["measured_utc"] == doc["measured_utc"]
    older = {"status": "MEASURED", "measured_utc": "2026-01-01T00:00:00+00:00"}
    assert pa.newest_scan(older, tmp_path / "scan.json")["measured_utc"] == doc["measured_utc"]
    newer = {"status": "MEASURED", "measured_utc": "2999-01-01T00:00:00+00:00"}
    assert pa.newest_scan(newer, tmp_path / "scan.json") is newer
    assert pa.newest_scan(older, tmp_path / "absent.json") is older


def test_the_heavy_clock_publishes_under_the_book_lock_and_scans_under_its_own() -> None:
    src = (_DESK / "research" / "pf_allocator.py").read_text(encoding="utf-8")
    main = src[src.index("def main() -> int:"):]
    assert 'run(args.mode, seed=args.seed, scan_inline=args.mode != "heavy")' in main
    i_book = main.index('with exclusive_job("pf_allocator", need_mb=need,')
    i_scan = main.index('with exclusive_job("pf_allocator_scan", need_mb=0,')
    assert i_book < i_scan and "deferred_scan()" in main[i_scan:]
    run_src = src[src.index("def run(mode"):]
    assert "prev_admission = newest_scan(prev_admission)" in run_src
    assert "if heavy and scan_inline:" in run_src
