"""TAPE -> BARS: the missing link between 8.2GB of recorded L2 and every screen on this desk.

WHY THE TESTS ARE SHAPED THIS WAY. This module converts the desk's only unreplicable asset into
the form every downstream consumer eats. A quiet defect here does not fail -- it produces bars that
look fine and are wrong, under every screen, permanently. So the suite is mostly about the ways
that could happen silently: reading one recorder schema and not the other, inventing prices where
nothing traded, and averaging a level that should be sampled.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.build_bars as B

T0 = 1767225600000          # 2026-01-01T00:00:00Z in ms


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


@pytest.fixture
def tape(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "MOAT", tmp_path / "moat")
    monkeypatch.setattr(B, "OUT", tmp_path / "bars")
    monkeypatch.setattr(B, "REPORT", tmp_path / "r.json")
    return tmp_path / "moat"


# ------------------------------------------------------------------ both schemas or silent loss


def test_BOTH_recorder_schemas_are_read() -> None:
    """THE LOAD-BEARING TEST. Binance stamps trades k='t' with flat p/q; Bybit stamps k='trades'
    with a NESTED list under v. A reader handling one returns clean, plausible, HALF-EMPTY bars
    over the other venue's archive -- the same class of bug that made moat_mine blind to 4.4GB
    until DEPTH_KINDS was added, and equally invisible."""
    binance = {"t": T0, "k": "t", "a": 1, "p": "100.5", "q": "0.5", "m": False}
    bybit = {"t": T0, "k": "trades", "v": [{"T": T0, "p": "100.5", "v": "0.3"}]}
    assert B.trades_from(binance) == [(T0, 100.5, 0.5)]
    assert B.trades_from(bybit) == [(T0, 100.5, 0.3)]


def test_bybit_size_under_either_key_is_accepted() -> None:
    """Bybit labels size `v` on some payloads and `size` on others. A missed quantity becomes
    zero volume -- a bar that looks real and weighs nothing, which every volume-scaled feature
    downstream then inherits."""
    r = {"t": T0, "k": "trades", "v": [{"T": T0, "p": "100", "size": "2.5"}]}
    assert B.trades_from(r) == [(T0, 100.0, 2.5)]


def test_depth_rows_never_become_prices() -> None:
    """Nothing trades at the book mid. Resampling depth into OHLC would put a synthetic price
    series under every screen on the desk, and the resulting IC would be a fact about the book
    rather than about executable prices."""
    depth = {"t": T0, "k": "d", "b": [["100", "1"]], "a": [["101", "1"]]}
    assert B.trades_from(depth) == []
    assert B.trades_from({"t": T0, "k": "depth", "b": [], "a": []}) == []


def test_a_corrupt_line_is_skipped_not_guessed(tape) -> None:
    """A fabricated bar is worse than a missing one: it cannot be detected downstream."""
    p = tape / "fut" / "BTCUSDT" / "20260101_00.jsonl.gz"
    p.parent.mkdir(parents=True)
    with gzip.open(p, "wt", encoding="utf-8") as f:
        f.write(json.dumps({"t": T0, "k": "t", "p": "100", "q": "1"}) + "\n")
        f.write("{not json at all\n")
        f.write(json.dumps({"t": T0 + 1000, "k": "t", "p": "101", "q": "1"}) + "\n")
    _, diag = B.build([p])
    assert diag["trades"] == 2


# ------------------------------------------------------------------ what must not be invented


def test_empty_buckets_are_DROPPED_not_forward_filled(tape) -> None:
    """A bar carried from the previous close is a price nothing traded at. Screens would read the
    flat stretch as genuine low volatility, and every vol-scaled feature downstream would be wrong
    in the same direction -- optimistically."""
    p = tape / "fut" / "BTCUSDT" / "20260101_00.jsonl.gz"
    _write(p, [{"t": T0, "k": "t", "p": "100", "q": "1"},
               {"t": T0 + 3 * 3600_000, "k": "t", "p": "110", "q": "1"}])   # 3h gap
    bars, _ = B.build([p])
    assert len(bars) == 2, "the empty buckets between the two trades were filled"
    assert (bars["trades"] > 0).all()


def test_open_interest_is_SAMPLED_not_summed(tape) -> None:
    """OI is a LEVEL, not a flow. Summing or averaging it invents a quantity the venue never
    reported -- and oi_flush, the one crypto-native detector with a mechanical basis, reads it."""
    rows = [{"t": T0 + i * 1000, "k": "t", "p": "100", "q": "1"} for i in range(10)]
    rows += [{"t": T0 + i * 1000, "k": "meta", "oi": str(1_000_000 + i)} for i in range(10)]
    p = tape / "bybit" / "BTCUSDT" / "20260101_00.jsonl.gz"
    _write(p, rows)
    bars, _ = B.build([p])
    assert bars["open_interest"].iloc[0] == pytest.approx(1_000_009)   # last in bucket
    assert bars["open_interest"].iloc[0] < 1_000_100                   # not a sum


# ------------------------------------------------------------------ honest empty


def test_no_tape_names_the_recorders_not_this_organ(tape) -> None:
    assert B.main() == 0
    rep = json.loads((tape.parent / "r.json").read_text("utf-8"))
    assert rep["state"] == "NO TAPE"
    assert "recorders" in rep["next"]


def test_tape_with_no_TRADES_is_distinguished_from_no_tape(tape) -> None:
    """Depth-only tape is a real and different state: the recorders ARE running, but aggTrades are
    not being captured. Reporting it as 'no tape' would send anyone at the wrong problem."""
    p = tape / "fut" / "BTCUSDT" / "20260101_00.jsonl.gz"
    _write(p, [{"t": T0, "k": "d", "b": [["100", "1"]], "a": [["101", "1"]]}])
    assert B.main() == 0
    rep = json.loads((tape.parent / "r.json").read_text("utf-8"))
    assert rep["state"] == "NO TRADES"
    assert "never from book mid" in rep["reason"]


# ------------------------------------------------------------------ end to end


def test_bars_feed_the_ICT_screen_end_to_end(tape, monkeypatch, tmp_path) -> None:
    """THE POINT OF THE WHOLE MODULE. Tape in, bars out, fourteen detectors screened -- the chain
    that reported NO BARS before this existed."""
    import scripts.screen_ict as S
    rng = np.random.default_rng(2)
    px, rows = 100.0, []
    for i in range(20000):
        px = max(1.0, px + rng.normal(0, 0.05))
        rows.append({"t": T0 + i * 15000, "k": "trades",
                     "v": [{"T": T0 + i * 15000, "p": f"{px:.4f}", "v": "0.3"}]})
    _write(tape / "bybit" / "BTCUSDT" / "20260101_00.jsonl.gz", rows)
    assert B.main() == 0
    monkeypatch.setattr(S, "BARS", tmp_path / "bars")
    monkeypatch.setattr(S, "REPORT", tmp_path / "s.json")
    monkeypatch.setattr(S, "HISTORY", tmp_path / "s.jsonl")
    assert S.main() == 0
    rep = json.loads((tmp_path / "s.json").read_text("utf-8"))
    assert rep["screened"] == 14, rep.get("state")
    assert rep["bars"] > 100
    assert rep["interesting"] == [], "a random walk must yield no interesting signal"
