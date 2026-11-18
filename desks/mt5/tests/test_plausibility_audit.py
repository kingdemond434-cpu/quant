"""The plausibility audit: flags never refuse, proven leaks are listed, the book rotates."""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
import plausibility_audit as pa  # noqa: E402


@dataclasses.dataclass(frozen=True)
class S:
    time: pd.Timestamp
    side: int
    stop: float
    target: float
    trigger: float | None = None


def _bars(n: int = 2400) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    c = 100 + np.cumsum(np.random.default_rng(5).normal(0, 0.2, n))
    return pd.DataFrame({"close": c}, index=idx)


def _leak(f: pd.DataFrame) -> list[S]:
    c = f["close"].to_numpy()
    return [S(f.index[i], 1 if c[i + 2] > c[i + 1] else -1, c[i] - 1, c[i] + 0.2)
            for i in range(0, len(f) - 3, 7)]


def _daily(df, sigs, _costs):
    """A toy judge: each signal earns +1 when its side matches the next 2 bars, else -1."""
    c = df["close"]
    rows = {}
    for s in sigs:
        p = c.index.get_loc(s.time)
        if p + 2 >= len(c):
            continue
        r = 1.0 if (c.iloc[p + 2] - c.iloc[p + 1]) * s.side > 0 else -1.0
        rows[s.time.normalize()] = rows.get(s.time.normalize(), 0.0) + r
    return pd.Series(rows, dtype=float).sort_index()


def test_a_peek_ahead_cell_is_proven_and_listed(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(pa, "OUT_DIR", tmp_path)
    df = _bars()
    cell = {"df": df, "sigs": _leak(df), "costs": None}
    row = pa.examine(cell, lambda frame: {"sigs": _leak(frame)}, _daily)
    assert row["screen"]["suspect"] is True
    assert row["verdict"] == "LEAK_PROVEN"
    pa._write_lists([{"certificate": "c1", **row}], {"c1"})
    listed = json.loads((tmp_path / "LEAK_PROVEN.json").read_text())["cells"]
    assert listed[0]["certificate"] == "c1"


def test_rotation_wraps_and_lists_keep_other_certificates(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(pa, "OUT_DIR", tmp_path)
    monkeypatch.setattr(pa, "CURSOR", tmp_path / "cursor.json")
    runs = [{"certificate": f"c{i}"} for i in range(5)]
    take, nxt = pa._rotate(runs, 3)
    assert [r["certificate"] for r in take] == ["c0", "c1", "c2"] and nxt == 3
    (tmp_path / "cursor.json").write_text(json.dumps({"next": nxt}))
    take, nxt = pa._rotate(runs, 3)
    assert [r["certificate"] for r in take] == ["c3", "c4", "c0"] and nxt == 1
    pa._merge(tmp_path / "FAST_TRACK.json", [{"certificate": "a"}], {"a"}, "t", "r")
    pa._merge(tmp_path / "FAST_TRACK.json", [{"certificate": "b"}], {"b"}, "t", "r")
    cells = json.loads((tmp_path / "FAST_TRACK.json").read_text())["cells"]
    assert {c["certificate"] for c in cells} == {"a", "b"}


@pytest.mark.parametrize("sharpe_like", [0.03])
def test_an_ordinary_cell_is_not_examined(sharpe_like: float) -> None:
    df = _bars(600)
    r = np.random.default_rng(1).normal(sharpe_like, 1.0, 200)
    row = pa.examine({"df": df, "sigs": [], "costs": None}, lambda f: {"sigs": []},
                     lambda *_: pd.Series(r))
    assert row["verdict"] == "PLAUSIBLE"


def test_no_synced_row_carries_an_exception_message(tmp_path, monkeypatch) -> None:
    """Synced files go to a public repo: an exception's TYPE may cross, its free text never."""
    planted = "C:\\opt\\quant\\data\\secrets\\token-in-a-path"
    monkeypatch.setattr(pa, "OUT_DIR", tmp_path)
    df = _bars(600)

    def _boom(*_a, **_k):
        raise RuntimeError(planted)

    hot = np.abs(np.random.default_rng(2).normal(0.5, 0.2, 300))
    calls = {"n": 0}

    def _daily_then_boom(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:  # the cell's own series; every forensic arm then fails
            return pd.Series(hot)
        return _boom()

    row = pa.examine({"df": df, "sigs": _leak(df), "costs": None}, _boom, _daily_then_boom)
    pa._write_lists([{"certificate": "x", **row}], {"x"})
    blob = json.dumps(row, default=str) + "".join(
        p.read_text() for p in tmp_path.iterdir() if p.is_file())
    assert "RuntimeError" in blob
    assert planted not in blob and "token-in-a-path" not in blob


def test_the_synced_organs_never_format_an_exception_message() -> None:
    import re
    root = DESK.parent.parent
    for rel in ("desks/mt5/research/loss_learner.py",
                "desks/mt5/research/plausibility_audit.py", "libs/validation/plausibility.py"):
        src = (root / rel).read_text(encoding="utf-8")
        assert not re.search(r"\{exc(!r)?\}|str\(exc\)|repr\(exc\)", src), rel
