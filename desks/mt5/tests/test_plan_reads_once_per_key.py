"""The plan asks each per-symbol and per-chart question once, and answers it the same way.

Box plan profile 2026-10-29: over ~1.55M docket cells the plan stat'ed a symbol's H1 parquet,
loaded a whole off-H1 frame and re-read banned_families.json once or twice PER CELL, and the cache
prune stat'ed every cache file separately (787 s of a 1,753 s plan).
"""
import os
import sys
import time
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for p in (DESK, DESK / "scripts", DESK / "research"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import external_gauntlet as eg  # noqa: E402

META = {"AAA": {}, "BBB": {}, "CCC": {"tradeable": False, "trade_mode": 3}}


def _specs():
    out = []
    for i in range(60):
        sym = ("AAA", "BBB", "CCC", "ZZZ")[i % 4]
        params = {"n": i, **({"timeframe": "M5"} if i % 3 == 0 else {})}
        out.append({"sym": sym, "family": "session_range_breakout", "params": params})
    return out


@pytest.fixture
def counted(monkeypatch):
    calls = {"tradeable": [], "bars": []}
    real_t = eg.symbol_is_tradeable

    def tradeable(sym, meta):
        calls["tradeable"].append(sym)
        return real_t(sym, meta)

    def bars(sym, tf="H1"):
        calls["bars"].append((sym, tf))
        return None if sym == "BBB" else object()

    monkeypatch.setattr(eg, "symbol_is_tradeable", tradeable)
    monkeypatch.setattr(eg, "_bars_for", bars)
    monkeypatch.setattr(eg, "_live_h1_available", lambda s: s in {"AAA", "BBB", "CCC"})
    monkeypatch.setattr(eg, "economic_prior", lambda sp: {"passed": True})
    return calls


def test_each_symbol_and_chart_is_asked_once(counted) -> None:
    eligible, rejected = eg.partition_at_economic_prior(_specs(), META)
    assert sorted(counted["tradeable"]) == ["AAA", "BBB", "CCC", "ZZZ"]
    assert sorted(counted["bars"]) == [("AAA", "M5"), ("BBB", "M5")]
    assert len(eligible) + len(rejected) == 60


def test_the_answers_match_a_per_cell_reading(counted) -> None:
    eligible, rejected = eg.partition_at_economic_prior(_specs(), META)
    want_ok = [s for s in _specs()
               if s["sym"] == "AAA" or (s["sym"] == "BBB" and "timeframe" not in s["params"])]
    assert [s["params"]["n"] for s in eligible] == [s["params"]["n"] for s in want_ok]
    by = {r["cell"]: r for r in rejected}
    for s in _specs():
        cid = eg.cell_id(s)
        if s["sym"] == "CCC":
            assert "CLOSE_ONLY" in by[cid]["stages"]["symbol_eligibility"]["message"]
        elif s["sym"] == "ZZZ":
            assert "absent from the universe registry" in by[cid]["stages"][
                "symbol_eligibility"]["message"]
        elif s["sym"] == "BBB" and "timeframe" in s["params"]:
            assert "BBB_M5.parquet" in by[cid]["stages"]["symbol_eligibility"]["message"]


def test_the_cache_prune_removes_only_stale_npz(monkeypatch, tmp_path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    old = time.time() - 4 * 86400
    for name, stale in (("a.npz", True), ("b.npz", False), ("c.txt", True), ("d.NPZ.bak", True)):
        f = cache / name
        f.write_bytes(b"x")
        if stale:
            os.utime(f, (old, old))
    src = Path(eg.__file__).read_text(encoding="utf-8")
    start = src.index("    try:\n        import fnmatch as _fn")
    block = src[start:src.index("    except OSError:\n        pass\n", start)
                + len("    except OSError:\n        pass\n")]
    ns = {"os": os, "Path": Path, "CACHE_DIR": cache}
    exec(compile("def _prune():\n" + block, "prune", "exec"), ns)  # the sealed lines, verbatim
    ns["_prune"]()
    assert sorted(p.name for p in cache.iterdir()) == ["b.npz", "c.txt", "d.NPZ.bak"]
    ns["CACHE_DIR"] = tmp_path / "absent"
    ns["_prune"]()                                   # a missing cache dir is not an error
