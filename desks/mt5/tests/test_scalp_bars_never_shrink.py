"""The 15-minute scalp bar refresh is a rolling 20,000-bar window: it must never cut the head
off the file the forward engine needs (rebuilt from bundle cross-asset-bar-backfill-v2)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "research"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import shadow_cycle  # noqa: E402


def _bars(start: str, end: str) -> pd.DataFrame:
    idx = pd.date_range(start, end, freq="5min", tz="UTC", name="timestamp")
    v = np.linspace(1.0, 2.0, len(idx))
    return pd.DataFrame({"open": v, "high": v, "low": v, "close": v,
                         "tick_volume": np.ones(len(idx), dtype="int64")}, index=idx)


def test_the_scalp_refresh_keeps_the_head_it_used_to_cut(tmp_path: Path) -> None:
    path = tmp_path / "XAUUSD_M5.parquet"
    _bars("2026-06-01", "2026-09-01").to_parquet(path)
    pull = _bars("2026-08-15", "2026-10-20")
    pull["close"] = 5.0
    out = shadow_cycle._keep_older_history(path, pull)
    assert out.index.min() == pd.Timestamp("2026-06-01", tz="UTC")
    assert (out.loc[pull.index, "close"] == 5.0).all()
    assert out.index.is_unique and out.index.is_monotonic_increasing
    assert shadow_cycle._keep_older_history(tmp_path / "absent.parquet", pull) is pull


def test_the_old_files_half_formed_last_bar_is_never_kept(tmp_path: Path) -> None:
    path = tmp_path / "XAUUSD_M5.parquet"
    old = _bars("2026-08-01", "2026-08-10")
    old.loc[old.index.max(), "close"] = 99.0
    old.to_parquet(path)
    pull = _bars("2026-08-12", "2026-10-20")
    out = shadow_cycle._keep_older_history(path, pull)
    assert old.index.max() not in out.index
    assert not (out["close"] == 99.0).any()
    assert out.index.min() == old.index.min()


def test_an_unreadable_file_changes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "XAUUSD_M5.parquet"
    path.write_bytes(b"not a parquet")
    pull = _bars("2026-08-12", "2026-08-13")
    assert shadow_cycle._keep_older_history(path, pull) is pull


def test_the_refresh_calls_the_never_shrink_merge() -> None:
    src = (ROOT / "research" / "shadow_cycle.py").read_text(encoding="utf-8")
    body = src[src.index("def _refresh_scalp_bars"):]
    assert "_keep_older_history(out_dir / f\"XAUUSD_{label}.parquet\", frame)" in body
