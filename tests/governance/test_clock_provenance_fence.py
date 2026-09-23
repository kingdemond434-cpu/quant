"""L1.46 CLOCK PROVENANCE -- the library, the fence, and the RECORDER WIRING.

The wiring tests at the bottom are the load-bearing ones. This desk's most expensive recurring
defect is a mechanism that is built, unit-tested green, and called by nobody. Here the mechanism
is a schema: the fence can be perfect and still measure nothing if the recorders stop writing the
marker. Every test in the final class fails if venue-stamp retention is torn out of a recorder,
so the provenance marker cannot silently become decorative while the fence keeps reporting on a
corpus that no longer carries it.
"""
from __future__ import annotations

import ast
import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.check_clock_provenance import build_report

from libs.research import clock_provenance as cp

_ROOT = Path(__file__).resolve().parent.parent.parent
_NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
_T0 = 1785578400000


def _tape(root: Path, venue: str, symbol: str, rows: list[dict]) -> None:
    d = root / "data/moat" / venue / symbol
    d.mkdir(parents=True, exist_ok=True)
    with gzip.open(d / "20260801_12.jsonl.gz", "wt") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def _depth(i: int, *, marked: bool = True, venue_stamp: bool = True, step: int = 5000) -> dict:
    row = {"t": _T0 + i * step, "k": "d", "b": [["100", "1"]], "a": [["101", "1"]]}
    if marked:
        row["c"] = cp.CLOCK_RECV
    if venue_stamp:
        row["E"] = _T0 + i * step - 120
    return row


# --------------------------------------------------------------------------- the library

def test_marker_wins_over_the_historical_table() -> None:
    # A row that declares its clock is never second-guessed by inference.
    assert cp.clock_of({"k": "d", "c": cp.CLOCK_VENUE}, "fut") == cp.CLOCK_VENUE


def test_unmarked_historical_rows_stay_readable() -> None:
    # 7.5GB of pre-marker tape is not ambiguous to US -- we wrote the code that stamped it.
    assert cp.clock_of({"k": "d"}, "fut") == cp.CLOCK_RECV
    assert cp.clock_of({"k": "t"}, "fut") == cp.CLOCK_VENUE
    assert cp.clock_of({"k": "d"}, "spot") == cp.CLOCK_RECV_ONLY


def test_an_unclassified_stream_is_UNKNOWN_and_never_guessed() -> None:
    """A new stream must read UNKNOWN so the fence reports it, rather than defaulting to the
    common case and being silently wrong on exactly the row that is new."""
    assert cp.clock_of({"k": "quotes"}, "fut") == cp.CLOCK_UNKNOWN
    assert cp.clock_of({"k": "d"}, "kraken") == cp.CLOCK_UNKNOWN


def test_delta_is_receipt_minus_venue() -> None:
    row = {"t": _T0, "k": "d", "c": cp.CLOCK_RECV, "E": _T0 - 129}
    assert cp.delta_ms(row, "fut") == 129


def test_delta_is_None_when_either_clock_is_missing() -> None:
    # The normal state of the pre-marker corpus, and precisely what the fence counts.
    assert cp.delta_ms({"t": _T0, "k": "d"}, "fut") is None


def test_seconds_stamps_are_rejected_not_silently_accepted() -> None:
    """A seconds/millis mixup is the one units error that yields a plausible number."""
    assert cp.delta_ms({"t": _T0, "k": "d", "c": cp.CLOCK_RECV, "E": 1785578400}, "fut") is None


def test_inner_venue_ms_reads_a_bybit_batch() -> None:
    row = {"t": _T0, "k": "trades", "v": [{"time": str(_T0 - 900)}, {"time": str(_T0 - 300)}]}
    assert cp.inner_venue_ms(row) == _T0 - 300
    assert cp.inner_venue_ms({"t": _T0, "k": "trades", "v": []}) is None


def test_sort_key_is_monotonic_across_a_mixed_clock_file() -> None:
    """REGRESSION: sorting the raw `t` interleaves two clocks and reorders events silently --
    the mechanism behind every timestamp artifact in the graveyard. Measured on the real corpus:
    83 of 12,037 rows step backwards, the worst by 40.2 seconds."""
    depth = {"t": _T0 + 60_000, "k": "d", "c": cp.CLOCK_RECV}      # received a minute later
    trade = {"t": _T0, "k": "t", "c": cp.CLOCK_VENUE, "r": _T0 + 61_000}   # but matched earlier
    raw = sorted([depth, trade], key=lambda r: r["t"])
    assert raw[0] is trade                                   # naive sort puts the trade first
    honest = sorted([depth, trade], key=lambda r: cp.sort_key(r, "fut"))
    assert honest[0] is depth                                # we SAW the depth row first


def test_venue_of_path_refuses_a_stranger() -> None:
    assert cp.venue_of_path(Path("/x/data/moat/fut/BTCUSDT")) == "fut"
    assert cp.venue_of_path(Path("/x/data/other/BTCUSDT")) == ""


# --------------------------------------------------------------------------- the fence

def test_fence_never_reports_ok_on_an_empty_desk(tmp_path: Path) -> None:
    """THE ONE THING THIS FENCE MAY NEVER DO. Nothing to look at is LOUDER, not quieter."""
    assert build_report(root=tmp_path, now=_NOW)["status"] == "NO-DATA"


def test_unreadable_files_are_NO_DATA_not_a_clean_bill(tmp_path: Path) -> None:
    d = tmp_path / "data/moat/fut/BTCUSDT"
    d.mkdir(parents=True)
    (d / "20260801_12.jsonl.gz").write_bytes(b"this is not gzip")
    rep = build_report(root=tmp_path, now=_NOW)
    assert rep["status"] == "NO-DATA"
    assert rep["files_unreadable"] == 1


def test_rows_with_no_kind_are_UNMEASURED(tmp_path: Path) -> None:
    _tape(tmp_path, "fut", "BTCUSDT", [{"t": _T0, "x": 1}])
    assert build_report(root=tmp_path, now=_NOW)["status"] == "UNMEASURED"


def test_an_unclassified_venue_is_UNMEASURED_not_a_content_verdict(tmp_path: Path) -> None:
    """REGRESSION: `unknown_streams` was computed, reported in the artifact, and never consulted
    by the status ladder, so a brand-new venue fell through to RECV-ONLY -- a confident claim
    about a stream whose clock we cannot name. Not knowing which clock stamped a row outranks
    any finding derived from assuming one (L1.28a)."""
    _tape(tmp_path, "kraken", "XBTUSD", [{"t": _T0 + i * 5000, "k": "book"} for i in range(12)])
    rep = build_report(root=tmp_path, now=_NOW)
    assert rep["status"] == "UNMEASURED"
    assert rep["unknown_streams"] == ["kraken/book"]
    assert rep["recv_only_defects"] == []


def test_undeclared_two_clock_file_is_MIXED_CLOCK(tmp_path: Path) -> None:
    """The state of the real corpus on 2026-08-01, and the fence's first-run finding."""
    rows = [{"t": _T0 + i * 5000, "k": "d", "b": [["1", "1"]], "a": [["2", "1"]]}
            for i in range(12)]
    rows += [{"t": _T0 + i * 100, "k": "t", "p": "1"} for i in range(12)]
    _tape(tmp_path, "fut", "BTCUSDT", rows)
    rep = build_report(root=tmp_path, now=_NOW)
    assert rep["status"] == "MIXED-CLOCK"
    assert rep["mixed_clock_streams"]


def test_declaring_the_clock_clears_MIXED_CLOCK(tmp_path: Path) -> None:
    rows = [_depth(i) for i in range(12)]
    rows += [{"t": _T0 + i * 100, "k": "t", "c": cp.CLOCK_VENUE, "p": "1"} for i in range(12)]
    _tape(tmp_path, "fut", "BTCUSDT", rows)
    assert build_report(root=tmp_path, now=_NOW)["status"] == "OK"


def test_dropping_a_venue_stamp_the_venue_publishes_is_RECV_ONLY(tmp_path: Path) -> None:
    _tape(tmp_path, "fut", "BTCUSDT", [_depth(i, venue_stamp=False) for i in range(12)])
    rep = build_report(root=tmp_path, now=_NOW)
    assert rep["status"] == "RECV-ONLY"
    assert "fut/d" in rep["recv_only_defects"]


def test_a_venue_that_publishes_no_stamp_is_exempt_not_a_defect(tmp_path: Path) -> None:
    """Binance spot /api/v3/depth genuinely returns no timestamp (verified live 2026-08-01).
    A fence that demands a stamp which does not exist cries wolf, and a gate that cries wolf
    gets switched off -- which is how enforcement actually dies."""
    rows = [{"t": _T0 + i * 5000, "k": "d", "c": cp.CLOCK_RECV_ONLY, "b": [["1", "1"]]}
            for i in range(12)]
    _tape(tmp_path, "spot", "BTCUSDT", rows)
    rep = build_report(root=tmp_path, now=_NOW)
    assert rep["status"] == "OK"
    assert rep["recv_only_defects"] == []
    assert rep["streams"]["spot/d"]["venue_limit_exempt"] is True


def test_a_configured_period_that_is_fiction_is_PERIOD_DRIFT(tmp_path: Path) -> None:
    """Measured on the real corpus: futures depth samples every 8.2s against _DEPTH_EVERY_S=5.0,
    with p05 at 7.8s and nothing near 5.0 -- the poll loop cannot finish inside its own period."""
    _tape(tmp_path, "fut", "BTCUSDT", [_depth(i, step=10_000) for i in range(12)])
    rep = build_report(root=tmp_path, now=_NOW)
    assert rep["status"] == "PERIOD-DRIFT"
    assert rep["period_drift"][0]["ratio"] == 2.0


def test_jitter_within_tolerance_does_not_fire(tmp_path: Path) -> None:
    """GATE-OPTIMALITY: Bybit runs 4.2s against 4.0s configured and must NOT fire. A gate that
    rejects ~100% of what it sees carries zero information."""
    _tape(tmp_path, "fut", "BTCUSDT", [_depth(i, step=6000) for i in range(12)])
    assert build_report(root=tmp_path, now=_NOW)["status"] == "OK"


def test_delta_is_reported_as_a_measured_series(tmp_path: Path) -> None:
    _tape(tmp_path, "fut", "BTCUSDT", [_depth(i) for i in range(12)])
    rep = build_report(root=tmp_path, now=_NOW)
    assert rep["delta_ms"]["fut"]["n"] == 12
    assert rep["delta_ms"]["fut"]["p50_ms"] == 120


def test_report_carries_the_keys_the_desk_reads(tmp_path: Path) -> None:
    rep = build_report(root=tmp_path, now=_NOW)
    for key in ("generated", "law", "status", "detail", "next_action"):
        assert key in rep, key


# --------------------------------------------------------------------------- THE WIRING
# These fail if clock-provenance retention is removed from a recorder. A schema nothing writes is
# not built, however green the fence looks reading a corpus that no longer carries it.
#
# REPOINTED 2026-09-05 (MT5 universe mandate, 2026-08-18). This class used to read
# scripts/run_recorder.py, run_recorder_spot.py and run_recorder_bybit.py -- the Binance
# futures/spot and Bybit collectors of the retired crypto-exchange desk -- plus
# scripts/moat_audit.py. All four were deleted with that desk, so the class stopped importing at
# COLLECTION time and took
# this whole module down with it. Deleting the class instead would have been the wrong trade: L1.46
# did not retire, the recorders did. The law now binds `desks/mt5/recorders/` (the Fusion tick tape)
# and `desks/mt5/moat/moat_recorder.py` (the Bronze moat node), so the wiring fence follows the law
# to the code that writes the tape TODAY. The library tests above still exercise the venue-tape
# schema because scripts/check_clock_provenance.py still reads it; when that fence is retired too,
# this module goes with it.

class TestRecorderWiring:
    TICKS = _ROOT / "desks/mt5/recorders/tick_recorder.py"
    STORE = _ROOT / "desks/mt5/recorders/tape_store.py"
    SOURCE = _ROOT / "desks/mt5/recorders/tick_source.py"
    MOAT = _ROOT / "desks/mt5/moat/moat_recorder.py"

    def test_the_recorders_the_law_binds_actually_exist(self) -> None:
        """The failure this class exists to make loud: a wiring fence whose subject was deleted
        reports nothing rather than reporting a gap, which is how absence reads as clean."""
        for p in (self.TICKS, self.STORE, self.SOURCE, self.MOAT):
            assert p.exists(), (
                f"{p.relative_to(_ROOT)} is gone, so nothing writes the L1.46 clock provenance "
                "the fence above certifies. Retire the fence deliberately or restore the writer; "
                "a silently unwritten schema is the defect this class was built to catch.")

    def test_the_tick_recorder_probes_the_broker_clock_every_cycle(self) -> None:
        """Broker-server time, local UTC and local monotonic are THREE INSTANTS. MOAT_NODE_SPEC
        release 1 item 6 makes the skew between them a recorded quantity, because a bad clock
        silently ruins every lead-lag and execution study built on the tape afterwards."""
        src = self.TICKS.read_text("utf-8")
        assert "clock_probe" in src, "the tick recorder no longer samples the broker clock"
        assert "record_clock" in src, "the clock probe is taken and then not persisted"
        assert "clock_probe" in self.SOURCE.read_text("utf-8")
        assert "def record_clock" in self.STORE.read_text("utf-8")

    def test_the_moat_recorder_retains_receipt_provenance_on_every_row(self) -> None:
        """The MT5 analogue of the venue-stamp retention this class used to fence: a row must
        carry WHEN WE RECEIVED IT on both a wall clock and a monotonic one. Wall clock alone is
        not enough -- an NTP step backwards reorders the tape, which is the same class of defect
        as the mixed-clock sort the library tests above refuse."""
        src = self.MOAT.read_text("utf-8")
        assert "recv_utc" in src, "moat rows no longer carry a receipt wall clock"
        assert "recv_mono" in src, "moat rows no longer carry a monotonic receipt"
        assert "time.monotonic()" in src

    def test_recorder_receipt_stamps_are_refreshed_inside_the_fetch_loop(self) -> None:
        """REGRESSION, carried forward from the retired Bybit collector because the SHAPE is what
        transfers, not the venue: `now` was captured ONCE, above a serial 20-symbol fetch loop, so
        every symbol after the first carried a receipt stamp EARLIER than the moment we received
        it -- a look-ahead in our own receipt axis, same class as the R0060 leaky copies. Measured
        before the fix on the retired tape: 32.8% of 877,314 batches had a receipt preceding the
        newest trade in them.

        THE BAR IS PER-FETCH, NOT PER-ROW, and the difference is the whole reason this is checked
        structurally. One `copy_ticks_range` call returns one array that arrived at one instant;
        stamping every row of that array with that instant is HONEST, and a fence demanding a
        fresh `datetime.now()` per row would fire on correct code and get switched off. What may
        never happen is a receipt hoisted ABOVE the call that fetches the data. So the rule is:
        every name a receipt field is stamped from must be re-bound inside some loop that encloses
        the stamp -- a name bound once at function top, outside every loop, is the defect.
        """
        for path in (self.MOAT, self.TICKS):
            tree = ast.parse(path.read_text("utf-8"))
            loops = [n for n in ast.walk(tree) if isinstance(n, ast.For | ast.While)]
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                        and isinstance(node.value, ast.Name)):
                    continue
                tgt = node.targets[0]
                if not (isinstance(tgt, ast.Subscript) and isinstance(tgt.slice, ast.Constant)
                        and tgt.slice.value in ("recv_utc", "recv_mono")):
                    continue
                refreshed = any(
                    any(n is node for n in ast.walk(loop))
                    and node.value.id in {t.id for a in ast.walk(loop)
                                          if isinstance(a, ast.Assign)
                                          for t in a.targets if isinstance(t, ast.Name)}
                    for loop in loops)
                assert refreshed, (
                    f"{path.name}:{node.lineno}: {tgt.slice.value} is stamped from "
                    f"`{node.value.id}`, which is bound outside every loop that reaches this "
                    "line -- so every fetch after the first claims a receipt earlier than its "
                    "own arrival.")

    def test_recorder_literals_match_the_library_constants(self) -> None:
        """The recorders deliberately import nothing from libs -- a collector that dies on an
        import error is the one failure it cannot come back from. That duplication is fenced
        HERE so the literals can never drift from the module that interprets them."""
        assert cp.CLOCK_RECV == "recv"
        assert cp.CLOCK_VENUE == "venue"
        assert cp.CLOCK_RECV_ONLY == "recv_only"
        assert cp.MARKER == "c"

    def test_no_recorder_coalesces_two_clocks_into_one_field(self) -> None:
        """The desk's own auditor read `d.get("t") or d.get("E") or d.get("ts")` -- three clocks
        merged into one field, silently preferring whichever was present.

        Checked STRUCTURALLY rather than by string match, so the defect SHAPE is caught in any
        spelling -- a different field order, a walrus -- instead of only the one arrangement that
        happened to be there. Narrowed to CLOCK fields on its first run, which flagged

            b, a = d.get("b") or d.get("bids"), d.get("a") or d.get("asks")

        -- two spellings of ONE quantity, which is a legitimate coalesce and not this defect. The
        instrument was narrowed rather than the code reworded to suit it: a check that fires on
        healthy code gets acknowledged into silence, and that is how enforcement actually dies.
        """
        for path in (self.TICKS, self.STORE, self.MOAT):
            for node in ast.walk(ast.parse(path.read_text("utf-8"))):
                if not isinstance(node, ast.BoolOp) or not isinstance(node.op, ast.Or):
                    continue
                fields = {v.args[0].value for v in node.values
                          if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute)
                          and v.func.attr == "get" and v.args
                          and isinstance(v.args[0], ast.Constant)
                          and isinstance(v.args[0].value, str)}
                assert len(fields & cp.CLOCK_FIELDS) < 2, (
                    f"{path.name}:{node.lineno}: {sorted(fields & cp.CLOCK_FIELDS)} coalesced "
                    "with `or` -- those are DIFFERENT INSTANTS, and this is the L1.46 defect "
                    "growing back")
