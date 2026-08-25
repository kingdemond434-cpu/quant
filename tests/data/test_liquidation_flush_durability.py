"""The liquidation flush must never destroy live events to protect an unreadable archive.

WHAT THESE PIN, AND WHAT IT COST. `_flush()` cleared the buffer BEFORE reading the previous
archive, so once `data/liquidations.parquet` was truncated by an interrupted write the listener
destroyed every buffered liquidation on a 60s cycle for 41 days while its heartbeat stayed
seconds-fresh. No REST liquidation history exists on any venue, so the span is unrecoverable.

Each test fails against the original implementation:
  * `test_corrupt_archive_does_not_destroy_buffer` -- the original raises out of `_flush` with
    `_BUF` already emptied.
  * `test_write_is_atomic` -- the original hands the live path to `to_parquet`, so a kill
    mid-write truncates the archive itself.
  * `test_buffer_survives_write_failure` -- the original clears unconditionally.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from pyarrow.lib import ArrowInvalid

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def listener(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Import the listener with its archive paths redirected into a temp dir."""
    mod = importlib.import_module("scripts.liquidation_listener")
    monkeypatch.setattr(mod, "_OUT", tmp_path / "liquidations.parquet")
    # `raising=False` deliberately: against an implementation with no `_STATUS` these tests must
    # still fail ON THE BEHAVIOUR (a destroyed buffer, a truncated archive), never on a missing
    # constant. A test that errors because a name is absent proves the name exists and nothing
    # about what the code does.
    monkeypatch.setattr(mod, "_STATUS", tmp_path / "liquidation_status.json", raising=False)
    mod._BUF.clear()
    return mod


def _row() -> dict[str, object]:
    return {"ts": pd.Timestamp("2026-08-19T00:00:00Z"), "symbol": "BTCUSDT",
            "side": "Buy", "qty": 1.0, "price": 100.0, "notional": 100.0}


def test_corrupt_archive_does_not_destroy_buffer(listener: Any) -> None:
    """A truncated archive must not cost us the events in hand -- the 41-day defect."""
    listener._OUT.write_bytes(b"PAR1" + b"\x00" * 500)      # truncated: no footer, no end magic
    with pytest.raises(ArrowInvalid):
        pd.read_parquet(listener._OUT)                       # the archive really is unreadable

    listener._BUF.append(_row())
    listener._flush()

    assert listener._BUF == [], "buffer should be cleared only after a durable write"
    df = pd.read_parquet(listener._OUT)
    assert len(df) == 1, "the live event must survive a corrupt archive"
    quarantined = list(listener._OUT.parent.glob("liquidations.corrupt-*.parquet"))
    assert quarantined, "the unreadable archive must be quarantined, never silently overwritten"


def test_write_is_atomic(listener: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A kill mid-write must damage only a temp file, never the live archive."""
    listener._BUF.append(_row())
    listener._flush()
    assert len(pd.read_parquet(listener._OUT)) == 1

    real_to_parquet = pd.DataFrame.to_parquet

    def die_mid_write(self: pd.DataFrame, path: Any, *a: Any, **k: Any) -> None:
        real_to_parquet(self, path, *a, **k)                 # bytes land...
        raise KeyboardInterrupt("OOM killer")                # ...then the process dies

    monkeypatch.setattr(pd.DataFrame, "to_parquet", die_mid_write)
    listener._BUF.append(_row())
    with pytest.raises(KeyboardInterrupt):
        listener._flush()

    df = pd.read_parquet(listener._OUT)                      # must still be readable
    assert len(df) == 1, "an interrupted write must leave the archive intact"


def test_buffer_survives_write_failure(listener: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """If the write fails, the events stay buffered for the next tick rather than vanishing."""
    monkeypatch.setattr(pd.DataFrame, "to_parquet",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    listener._BUF.append(_row())
    with pytest.raises(OSError):
        listener._flush()
    assert len(listener._BUF) == 1, "a failed write must not discard the buffer"


def test_status_distinguishes_data_liveness_from_loop_liveness(listener: Any) -> None:
    """The second signal: a payload reaching disk, not merely a loop tick."""
    listener._BUF.append(_row())
    listener._flush()
    import json
    status = json.loads(listener._STATUS.read_text())
    assert status["archive_status"] == "OK"
    assert status["rows_total"] == 1
    assert status["last_payload_utc"], "a payload write must stamp its own clock"
