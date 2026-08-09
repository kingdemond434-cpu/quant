"""R0006: the daily regime fingerprint must accumulate, not be overwritten.

scripts/classify_regime.py wrote only data/crypto_regime.json, which it OVERWRITES each run --
so the desk could never answer "what regime was it when this trade opened / this screen ran".
Unlike the bars themselves, that dated reading is unrecoverable once lost: Binance will serve
BTC klines again, but not the desk's own classification of them on a given day.

The append is idempotent per UTC day because the executor calls this script repeatedly, and a
history that stacks one row per invocation would silently over-weight busy days in any later
regime-conditioned analysis.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.classify_regime import _append_history


def _row(ts: str, regime: str = "trend:bull / vol:low_vol") -> dict[str, object]:
    return {"updated": ts, "regime": regime, "trend": "bull", "vol": "low_vol",
            "btc_60d_mom": 0.1, "rv14_ann": 0.5}


def _read(p: Path) -> list[dict[str, object]]:
    return [json.loads(ln) for ln in p.read_text("utf-8").splitlines() if ln.strip()]


def test_history_accumulates_across_days(tmp_path: Path) -> None:
    h = tmp_path / "hist.jsonl"
    now = datetime.now(tz=UTC)
    for d in (2, 1, 0):
        _append_history(_row((now - timedelta(days=d)).isoformat()), path=h)
    assert len(_read(h)) == 3, "each UTC day must leave its own fingerprint"


def test_same_day_reruns_supersede_rather_than_stack(tmp_path: Path) -> None:
    """The executor calls this many times a day; stacking would over-weight busy days."""
    h = tmp_path / "hist.jsonl"
    now = datetime.now(tz=UTC)
    _append_history(_row(now.isoformat(), "trend:bear / vol:high_vol"), path=h)
    _append_history(_row((now + timedelta(minutes=5)).isoformat()), path=h)
    rows = _read(h)
    assert len(rows) == 1
    assert rows[0]["regime"] == "trend:bull / vol:low_vol", "the later run must win"


def test_unparseable_lines_are_never_dropped(tmp_path: Path) -> None:
    """History is evidence: a corrupt line is a thing to investigate, not to silently delete."""
    h = tmp_path / "hist.jsonl"
    h.write_text("{not json\n", "utf-8")
    _append_history(_row(datetime.now(tz=UTC).isoformat()), path=h)
    lines = [ln for ln in h.read_text("utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2 and lines[0] == "{not json"


def test_a_missing_history_file_is_created_not_fatal(tmp_path: Path) -> None:
    h = tmp_path / "nested" / "hist.jsonl"
    _append_history(_row(datetime.now(tz=UTC).isoformat()), path=h)
    assert len(_read(h)) == 1


class TestBackfillIsCausal:
    """The backfill's whole value is that a reconstructed row equals what the live run WOULD
    have written that day. If it peeked at later bars it would label history with knowledge the
    desk did not have, and every regime-conditioned analysis built on it would be look-ahead.
    """

    def _bars(self, n: int = 500):
        import numpy as np
        import pandas as pd
        rng = np.random.default_rng(3)
        close = 30_000.0 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, n)))
        ts = pd.date_range("2025-01-01", periods=n, freq="D", tz="UTC")
        return pd.DataFrame({"timestamp": ts, "close": close})

    def test_a_backfilled_row_equals_the_live_row_for_that_day(self, tmp_path: Path) -> None:
        import scripts.classify_regime as cr
        df = self._bars()
        h = tmp_path / "hist.jsonl"
        cr.backfill(df, days=30, path=h)
        rows = {str(r["updated"])[:10]: r for r in _read(h)}
        close_all = df["close"].astype(float).to_numpy()
        # recompute one middle day the way the LIVE script would have, on that day's prefix only
        i = len(df) - 15
        day = str(df["timestamp"].tolist()[i])[:10]
        live = cr.classify(close_all[:i + 1], str(df["timestamp"].tolist()[i]))
        assert rows[day]["regime"] == live["regime"]
        assert rows[day]["btc_60d_mom"] == live["btc_60d_mom"]

    def test_backfill_never_overwrites_a_live_reading(self, tmp_path: Path) -> None:
        import scripts.classify_regime as cr
        df = self._bars()
        h = tmp_path / "hist.jsonl"
        day_ts = str(df["timestamp"].tolist()[-5])
        cr._append_history(_row(day_ts, "trend:LIVE / vol:LIVE"), path=h)
        cr.backfill(df, days=30, path=h)
        rows = {str(r["updated"])[:10]: r for r in _read(h)}
        assert rows[day_ts[:10]]["regime"] == "trend:LIVE / vol:LIVE", (
            "a reconstruction must never displace a genuinely-live reading")

    def test_backfill_is_idempotent(self, tmp_path: Path) -> None:
        import scripts.classify_regime as cr
        df = self._bars()
        h = tmp_path / "hist.jsonl"
        first = cr.backfill(df, days=40, path=h)
        n_after_first = len(_read(h))
        second = cr.backfill(df, days=40, path=h)
        assert first > 0 and second == 0
        assert len(_read(h)) == n_after_first
