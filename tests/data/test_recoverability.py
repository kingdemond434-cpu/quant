"""L1.65 -- span high-water and recoverability. Each test pins a way this could quietly lie.

The module exists because every other data gauge on this desk is denominated in what survives, so
destroying data improves the score. These tests hold the honesty rails that make it different:
UNMEASURED never becomes OK, an unprobed stream never becomes IRREPLACEABLE, a corrupt archive
never becomes an empty one, and the high-water mark only ever rises.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import recoverability as rec  # noqa: E402


def _tape(root: Path, source: str, symbol: str, hours: list[str]) -> None:
    d = root / "data/tape" / source / symbol
    d.mkdir(parents=True, exist_ok=True)
    for h in hours:
        (d / f"{h}.jsonl.gz").write_bytes(b"x" * 100)


# -- the refusal paths ---------------------------------------------------------------------------

def test_absent_tape_is_not_readable_here_and_never_zero(tmp_path: Path) -> None:
    """A checkout cannot measure a VPS-only tape. That is not 0% and it is not OK."""
    rep = rec.build_report(tmp_path)
    assert rep.status == rec.NOT_READABLE_HERE
    assert rep.status != rec.OK
    assert rep.n_streams == 0
    assert "gitignored" in " ".join(rep.notes)


def test_first_observation_is_unmeasured_not_ok(tmp_path: Path, monkeypatch) -> None:
    """No high-water history means a fall is undetectable -- so it cannot be reported healthy."""
    _tape(tmp_path, "eurusd", "EURUSD", ["20260819_01", "20260819_02"])
    monkeypatch.setattr(rec, "HIGH_WATER", tmp_path / "hw.jsonl")
    rep = rec.build_report(tmp_path)
    stream = next(s for s in rep.streams if s.key == "tape/eurusd")
    assert stream.status == rec.UNMEASURED
    assert stream.status not in rec.PASSING


def test_unmeasured_status_is_not_in_passing() -> None:
    """The refusal must be structurally unable to exit 0 (L1.28a)."""
    for bad in (rec.UNMEASURED, rec.LOSS_PERMANENT, rec.LOSS_RECOVERABLE, rec.CONTRADICTED):
        assert bad not in rec.PASSING


# -- the ratchet ---------------------------------------------------------------------------------

def test_high_water_only_rises(tmp_path: Path) -> None:
    """A fall is a fence failure, never a new baseline. A floor edited to fit is not a floor."""
    hw = tmp_path / "hw.jsonl"
    big = rec.Stream(key="k", kind="l2_depth_tape", span_now=100, unit="symbol-hours",
                     bytes_now=0, symbols=1, earliest=None, latest=None)
    assert rec.record_marks([big], hw) == 1
    small = rec.Stream(key="k", kind="l2_depth_tape", span_now=5, unit="symbol-hours",
                       bytes_now=0, symbols=1, earliest=None, latest=None)
    assert rec.record_marks([small], hw) == 0, "a fall must not append a mark"
    assert rec.load_high_water(hw)["k"][0] == 100, "the mark must not fall"


def test_fall_below_high_water_is_a_loss(tmp_path: Path) -> None:
    s = rec.Stream(key="k", kind="l2_depth_tape", span_now=10, unit="symbol-hours",
                   bytes_now=0, symbols=1, earliest=None, latest=None)
    rec.adjudicate(s, {"k": (100, "2026-08-17")})
    assert s.status == rec.LOSS_PERMANENT
    assert "90" in s.why and "unbuyable" in s.why


def test_recoverable_loss_emits_a_fetch(tmp_path: Path) -> None:
    """A loss with a verified path is an ACQUISITION instruction, not just an alarm."""
    s = rec.Stream(key="tape/eurusd", kind="l2_depth_tape", span_now=10, unit="symbol-hours",
                   bytes_now=0, symbols=1, earliest=None, latest=None, recovery=rec.RE_BUYABLE)
    rec.adjudicate(s, {"tape/eurusd": (100, "2026-08-17")})
    assert s.status == rec.LOSS_RECOVERABLE
    assert s.fetch_command, "a recoverable loss must name the command that recovers it"


# -- classification honesty ----------------------------------------------------------------------

def test_unprobed_stream_is_unmeasured_never_irreplaceable(tmp_path: Path) -> None:
    """'We have not looked' and 'no source exists' are different claims (L1.28a)."""
    s = rec.Stream(key="tape/somesource", kind="l2_depth_tape", span_now=1, unit="symbol-hours",
                   bytes_now=0, symbols=1, earliest=None, latest=None)
    rec.classify_recovery(s, tmp_path)
    assert s.recovery == rec.UNMEASURED_RECOVERY
    assert s.recovery != rec.IRREPLACEABLE


def test_corrupt_archive_is_not_an_empty_one(tmp_path: Path) -> None:
    """Row count -1, never 0. A 0 would let the ratchet accept the fall as 'no data yet'."""
    d = tmp_path / "data"
    d.mkdir(parents=True)
    (d / "liquidations.parquet").write_bytes(b"PAR1" + b"\x00" * 200)   # truncated
    (d / "liquidation_since").write_text("2026-07-09")
    streams = rec.measure_recorder_archives(tmp_path)
    s = next(x for x in streams if x.key == "recorder/liquidations")
    assert s.span_now == -1, "a corrupt archive must not read as empty"
    assert "UNREADABLE" in s.why
    rec.adjudicate(s, {})
    assert s.status == rec.LOSS_PERMANENT


def test_bootstrap_uses_unit_matched_field(tmp_path: Path) -> None:
    """REGRESSION. The first version read `cells_total` (symbol-DAYS) and compared it to a
    symbol-HOURS span -- two questions under one name, the L1.61 defect this module cites in its
    own header. `tape_files` is one file per symbol-hour and is the comparable series."""
    h = tmp_path / "data/tape_coverage_history.jsonl"
    h.parent.mkdir(parents=True)
    h.write_text(json.dumps({"cells_total": 23436, "tape_files": 40720}) + "\n")
    assert rec.bootstrap_marks(tmp_path)["tape/__desk_total__"] == 40720


def test_contradiction_is_detected(tmp_path: Path) -> None:
    """Doctrine says irreplaceable; a probe says reachable. Both honest, never compared."""
    s = rec.Stream(key="tape/eurusd", kind="l2_depth_tape", span_now=1, unit="symbol-hours",
                   bytes_now=0, symbols=1, earliest=None, latest=None,
                   recovery=rec.RE_BUYABLE, recovery_source="quote-saver.bycsi.com")
    notes = rec.detect_contradictions([s])
    assert notes and "cannot be bought" in notes[0]


def test_span_is_distinct_hours_not_endpoints(tmp_path: Path) -> None:
    """Endpoint arithmetic is what lets a left-truncation read as perfect continuity."""
    _tape(tmp_path, "eurusd", "EURUSD", ["20260101_00", "20260819_00"])   # 8 months apart
    streams = rec.measure_tape(tmp_path)
    assert streams[0].span_now == 2, "span must count hours HELD, not the range they span"


def test_skips_are_counted_not_invisible(tmp_path: Path) -> None:
    """L1.60: a file dropped from the walk must be visible in the denominator."""
    _tape(tmp_path, "eurusd", "EURUSD", ["20260819_01"])
    (tmp_path / "data/tape/eurusd/EURUSD/README.txt").write_text("not a tape file")
    s = rec.measure_tape(tmp_path)[0]
    assert s.attempted == 2 and s.skipped == 1


def test_quarantined_corpse_outlives_the_stream_that_recovered(tmp_path: Path) -> None:
    """REGRESSION on this module's OWN defect. Once the liquidation listener was repaired it began
    a fresh archive, span went -1 -> 10 rows, and the stream read OK -- the instrument built to
    catch a gauge denominated in what survives doing exactly that to itself. A quarantined
    predecessor is evidence of a loss and must survive the recovery of its own stream."""
    d = tmp_path / "data"
    d.mkdir(parents=True)
    import pandas as pd
    pd.DataFrame({"a": [1, 2, 3]}).to_parquet(d / "liquidations.parquet")   # healthy, fresh
    (d / "liquidations.corrupt-1787148705.parquet").write_bytes(b"PAR1" + b"\x00" * 50)
    (d / "liquidation_since").write_text("2026-07-09")

    s = next(x for x in rec.measure_recorder_archives(tmp_path)
             if x.key == "recorder/liquidations")
    assert s.span_now == 3, "the fresh archive really is readable"
    assert s.quarantined, "the corpse must be seen"
    rec.adjudicate(s, {})
    assert s.status == rec.LOSS_PERMANENT, "a recovered stream must not erase its loss event"
    assert s.status not in rec.PASSING
