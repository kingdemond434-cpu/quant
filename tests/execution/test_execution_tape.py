"""The execution tape is the desk's own fill history -- these tests pin the properties that make
it trustworthy: it never loses a record, it never double-counts on replay, and it can never take
down the live executor that feeds it."""
from __future__ import annotations

import json

from libs.execution import execution_tape


def _rec(sym: str = "BTCUSDT", event: str = "open", **kw) -> dict:
    r = {"event": event, "symbol": sym, "opened": "2026-07-02T05:18:33+00:00", "notional": 100.0}
    r.update(kw)
    return r


def test_append_then_read_roundtrip(tmp_path):
    p = tmp_path / "tape.jsonl"
    assert execution_tape.append(_rec(), path=p)
    got = execution_tape.read(path=p)
    assert len(got) == 1
    assert got[0]["symbol"] == "BTCUSDT"
    assert got[0]["_taped"]  # stamped on the way in


def test_backfill_is_idempotent(tmp_path):
    p = tmp_path / "tape.jsonl"
    recs = [_rec("AUSDT"), _rec("BUSDT"), _rec("CUSDT")]
    assert execution_tape.backfill(recs, path=p) == 3
    assert execution_tape.backfill(recs, path=p) == 0  # replay adds nothing
    assert len(execution_tape.read(path=p)) == 3


def test_backfill_preserves_genuine_duplicates(tmp_path):
    """The executor really does emit byte-identical records (a top-up logged 4x was observed).
    Set-based dedupe would collapse them and disagree with the live append path."""
    p = tmp_path / "tape.jsonl"
    dup = _rec("COOKIEUSDT", event="topup")
    recs = [dup, dict(dup), dict(dup), dict(dup)]
    assert execution_tape.backfill(recs, path=p) == 4
    assert len(execution_tape.read(path=p)) == 4
    assert execution_tape.backfill(recs, path=p) == 0  # still idempotent at multiplicity 4


def test_backfill_adds_only_the_shortfall(tmp_path):
    p = tmp_path / "tape.jsonl"
    dup = _rec("XUSDT", event="topup")
    execution_tape.backfill([dup, dict(dup)], path=p)
    # source later holds 4 copies -> only the 2 missing get taped
    assert execution_tape.backfill([dup, dict(dup), dict(dup), dict(dup)], path=p) == 2
    assert len(execution_tape.read(path=p)) == 4


def test_read_tolerates_torn_trailing_write(tmp_path):
    """A crash mid-append must cost the torn line only, never the tape."""
    p = tmp_path / "tape.jsonl"
    execution_tape.backfill([_rec("AUSDT"), _rec("BUSDT")], path=p)
    with p.open("a", encoding="utf-8") as fh:
        fh.write('{"event": "open", "symbol": "TOR')  # truncated mid-write
    got = execution_tape.read(path=p)
    assert len(got) == 2
    assert [r["symbol"] for r in got] == ["AUSDT", "BUSDT"]


def test_append_never_raises_on_bad_input(tmp_path):
    """The tape is an observer -- it must never propagate an exception into the executor."""
    class Unserializable:
        def __repr__(self):
            raise RuntimeError("boom")

    p = tmp_path / "tape.jsonl"
    execution_tape.append({"event": "open", "bad": Unserializable()}, path=p)  # must not raise


def test_coverage_reports_tape_depth(tmp_path):
    """Gate 0's '>=4 weeks of live fills' is measured against this number."""
    p = tmp_path / "tape.jsonl"
    execution_tape.backfill([
        _rec("AUSDT", opened="2026-07-01T00:00:00+00:00"),
        _rec("BUSDT", opened="2026-07-01T00:00:00+00:00", closed="2026-07-29T00:00:00+00:00"),
    ], path=p)
    cov = execution_tape.coverage(path=p)
    assert cov["n"] == 2
    assert cov["days"] == 28.0


def test_coverage_empty_tape(tmp_path):
    cov = execution_tape.coverage(path=tmp_path / "nope.jsonl")
    assert cov == {"n": 0, "days": 0.0, "first": None, "last": None}


def test_tape_outlives_the_rolling_cap(tmp_path):
    """The whole point: the rolling buffer caps at 500, the tape does not."""
    p = tmp_path / "tape.jsonl"
    rolling: list[dict] = []
    for i in range(600):
        rec = _rec(f"S{i}USDT", notional=float(i))
        rolling.append(rec)
        rolling = rolling[-500:]          # what run_cashcarry_executor does
        execution_tape.append(rec, path=p)
    assert len(rolling) == 500            # buffer evicted 100 fills
    assert len(execution_tape.read(path=p)) == 600  # tape kept every one
    assert json.loads(p.read_text("utf-8").splitlines()[0])["symbol"] == "S0USDT"
