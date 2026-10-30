"""The SRB uncorrelated sweep: the producer `srb_basket_judge` reads, pinned without a terminal.

It must cluster instruments into correlation blocks, keep what the live book already holds out of
the mint, leave short histories unblocked (never a block of their own), publish rows in the shape
the basket judge keys on, carry legs it could not reach, and never overwrite a measured pass with
an unmeasured one.
"""
from __future__ import annotations

import json
import sys
import zlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

BASE = Path(__file__).resolve().parents[3]
for _p in (str(BASE), str(BASE / "desks" / "mt5")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

sw = pytest.importorskip("research.srb_uncorrelated_sweep")
sbj = pytest.importorskip("research.srb_basket_judge")


def _frames(days: int = 400, short: int = 100) -> dict[str, pd.DataFrame]:
    """A and A2 move together; B is independent; LIVE is the live book's instrument and moves
    with C; SHORT has too little history to be clustered."""
    rng = np.random.default_rng(11)
    idx = pd.date_range("2024-01-01", periods=days * 24, freq="h", tz="UTC")
    n = len(idx)
    base_a = rng.normal(0, 1e-3, n)
    base_c = rng.normal(0, 1e-3, n)
    walks = {
        "A": base_a + rng.normal(0, 2e-4, n),
        "A2": base_a + rng.normal(0, 2e-4, n),
        "B": rng.normal(0, 1e-3, n),
        "C": base_c + rng.normal(0, 2e-4, n),
        "LIVE": base_c + rng.normal(0, 2e-4, n),
    }
    out = {s: pd.DataFrame({"close": 100 * np.exp(np.cumsum(w))}, index=idx)
           for s, w in walks.items()}
    out["SHORT"] = pd.DataFrame({"close": 100 * np.exp(np.cumsum(rng.normal(0, 1e-3,
                                                                           short * 24)))},
                                index=idx[: short * 24])
    return out


def _leg(sym: str, params: dict, meta: dict) -> tuple[pd.Series, pd.Series]:
    rng = np.random.default_rng(zlib.crc32(f"{sym}|{json.dumps(params, sort_keys=True)}".encode()))
    idx = pd.date_range("2024-01-01", periods=120, freq="D")
    s1 = pd.Series(rng.normal(0.01, 1.0, 120), index=idx)
    return s1, s1 - 0.02


def _run(frames, **kw):
    return sw.build(budget_s=kw.pop("budget_s", 60.0), meta={s: {} for s in frames},
                    symbols=[s for s in frames if s != "LIVE"], bars_for=frames.get,
                    leg_for=kw.pop("leg_for", _leg), live=["LIVE"], **kw)


def test_session_windows_match_the_compiler() -> None:
    mcc = pytest.importorskip("research.miner_candidate_compiler")
    assert sw.SESSIONS == mcc._SESSION_PARAMS


def test_blocks_join_correlated_split_independent_and_leave_short_history_unblocked() -> None:
    frames = _frames()
    rets = {s: sw.daily_returns(f) for s, f in frames.items()}
    blocks, dropped = sw.correlation_blocks(rets)
    assert blocks["A"] == blocks["A2"]
    assert blocks["A"] != blocks["B"]
    assert dropped == ["SHORT"] and blocks["SHORT"] is None


def test_the_live_book_is_measured_and_kept_out_of_the_mint() -> None:
    doc = _run(_frames())
    assert doc["measured"] is True
    held = {d["symbol"] for d in doc["correlated_to_live"]}
    assert held == {"C"}
    minted = {r["symbol"] for r in doc["cells"]}
    assert "C" not in minted and "LIVE" not in minted
    assert {"A", "A2", "B", "SHORT"} <= minted
    assert doc["coverage"]["cells"] == len(minted) * len(sw.SESSIONS)


def test_rows_are_in_the_shape_the_basket_judge_keys_on() -> None:
    doc = _run(_frames())
    for r in doc["cells"]:
        assert {"arm", "symbol", "params", "sharpe_is", "days", "block"} <= set(r)
        assert sbj._leg_key(r) == sw.leg_key(r["arm"], r["symbol"], r["params"])
    short = [r for r in doc["cells"] if r["symbol"] == "SHORT"]
    assert short and all(r["block"] is None for r in short)


def test_an_exhausted_budget_carries_the_previous_legs_rather_than_shrinking() -> None:
    frames = _frames()
    first = _run(frames)
    again = _run(frames, budget_s=-1.0, previous=first)
    assert again["coverage"]["built"] == 0
    assert again["coverage"]["carried"] == len(first["cells"])
    assert all(r.get("carried") for r in again["cells"])


def test_no_bars_is_unmeasured_and_never_overwrites_a_measured_pass(tmp_path, monkeypatch) -> None:
    out = tmp_path / "SRB_UNCORRELATED_SWEEP.json"
    old = {"measured": True, "cells": [{"x": 1}],
           "generated_at": (datetime.now(UTC) - timedelta(days=2)).isoformat()}
    out.write_text(json.dumps(old), "utf-8")
    monkeypatch.setattr(sw, "build", lambda **_k: {"measured": False, "why": "UNMEASURED: x"})
    assert sw.main(["--once", "--out", str(out)]) == 0
    assert json.loads(out.read_text("utf-8")) == old
    empty = sw.build(meta={"Z": {}}, symbols=["Z"], bars_for=lambda s: None, leg_for=_leg,
                     live=[])
    assert empty["measured"] is False and empty["why"].startswith("UNMEASURED")


def test_a_fresh_pass_is_kept(tmp_path, monkeypatch) -> None:
    out = tmp_path / "SRB_UNCORRELATED_SWEEP.json"
    out.write_text(json.dumps({"measured": True,
                               "generated_at": datetime.now(UTC).isoformat()}), "utf-8")

    def boom(**_k):
        raise AssertionError("a fresh sweep must not be rebuilt")

    monkeypatch.setattr(sw, "build", boom)
    assert sw.main(["--once", "--out", str(out), "--max-age-h", "20"]) == 0


def test_the_basket_judge_reads_the_sweeps_cells(tmp_path, monkeypatch) -> None:
    sweep = tmp_path / "SRB_UNCORRELATED_SWEEP.json"
    sweep.write_text(json.dumps({"cells": []}), "utf-8")
    monkeypatch.setattr(sbj, "SWEEP", sweep)
    seen = {}

    class _G:
        UNI = tmp_path

    (tmp_path / "universe.json").write_text("{}", "utf-8")

    def fake_build_legs(rows, meta, deadline):
        seen["rows"] = rows
        return {}, {}

    monkeypatch.setattr(sbj, "G", _G)
    monkeypatch.setattr(sbj, "build_legs", fake_build_legs)
    row = {"arm": "session_asia", "symbol": "EURUSD", "params": {"range_start": 7}}
    sweep.write_text(json.dumps({"cells": [row]}), "utf-8")
    doc = sbj.build(budget_s=1.0)
    assert seen["rows"] == [row] and doc["measured"] is False
