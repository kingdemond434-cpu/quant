"""Allocator proof suite leg (ALLOC-10/16/20/21): runs on a synthetic matrix, keeps a prospective
ledger, scores it only after the horizon, and is on the hourly clock."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

aps = pytest.importorskip("research.allocator_proof_suite", reason="ships with the desk")


def _daily(n: int, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-01", periods=n, freq="D").strftime("%Y-%m-%d")
    mus = (0.15, 0.05, 0.0, -0.1)
    return pd.DataFrame({f"s{i}": mu + rng.normal(0, 1, n) for i, mu in enumerate(mus)},
                        index=idx)


def test_a_pass_publishes_every_section_and_scores_only_matured_rows(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aps, "LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(aps, "OUT", tmp_path / "out.json")
    monkeypatch.setattr(aps, "DATA", tmp_path)
    alloc = {"book": {"s0": 0.12, "s1": 0.08}}
    now = datetime(2026, 11, 11, tzinfo=UTC)
    d = _daily(300)
    first = aps.run(daily=d.iloc[:260], alloc=alloc, now=now)
    assert first["status"] == "MEASURED" and first["attribution"]["n_scored"] == 0
    assert first["dro"]["status"] == "MEASURED" and first["no_trade_band"]["status"] == "MEASURED"
    assert first["disagreement"]["n_sleeves"] == 2
    assert first["release"]["status"] == "UNMEASURED"           # no calendar under tmp
    again = aps.run(daily=d.iloc[:260], alloc=alloc, now=now)
    assert again["attribution"]["appended"] == 0                 # one row per cutoff
    later = aps.run(daily=d, alloc=alloc, now=now)
    att = later["attribution"]
    assert att["n_scored"] == 1 and att["n_ledger"] == 2
    assert set(att["aggregate"]) == {"selection", "sizing", "cost", "net_vs_baseline"}
    assert json.loads((tmp_path / "out.json").read_text())["authority"].startswith("none")


def test_an_absent_matrix_is_unmeasured_not_a_crash(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aps, "OUT", tmp_path / "out.json")
    from research import pf_allocator as pa

    def refuse(**_k: object) -> None:
        raise SystemExit("REFUSING to project")

    monkeypatch.setattr(pa, "build_evidence", refuse)
    doc = aps.run(alloc={"book": {"s0": 0.1}})
    assert doc["status"] == "UNMEASURED" and "SystemExit" in doc["why"]


def test_the_leg_is_on_the_hourly_clock() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '"research/allocator_proof_suite.py"' in src and '"allocator_proof_suite": aps' in src
    from libs.research import layers
    assert layers.LEG_LAYER["allocator_proof_suite"] == "portfolio"


def test_an_exhausted_budget_skips_sections_but_keeps_attribution(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aps, "LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(aps, "OUT", tmp_path / "out.json")
    monkeypatch.setattr(aps, "DATA", tmp_path)
    monkeypatch.setattr(aps, "WALL_BUDGET_S", -1.0)
    doc = aps.run(daily=_daily(300), alloc={"book": {"s0": 0.12}},
                  now=datetime(2026, 11, 11, tzinfo=UTC), write=False)
    assert "n_scored" in doc["attribution"]
    assert set(doc["skipped_for_budget"]) == {"dro", "release", "disagreement", "no_trade_band"}
    assert doc["no_trade_band"]["status"] == "SKIPPED_BUDGET"
