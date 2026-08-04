"""THE CALIBRATOR MUST READ THE RECORDERS' ACTUAL SCHEMA AND REFUSE TO INVENT A BOOK.

A coefficient fitted on generated depth measures the generator, and it would then size every
strategy on the desk through capacity_allocation. That is the one output here where a plausible
fake is more dangerous than a crash.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.calibrate_impact as C  # noqa: E402


def _tape(root: Path, venue: str = "binance", sym: str = "BTCUSDT", n: int = 300) -> None:
    d = root / venue / sym
    d.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    with gzip.open(d / "20260101_00.jsonl.gz", "wt") as f:
        for i in range(n):
            mid = 30000 * np.exp(rng.normal(0, 0.001))
            b = [[f"{mid - 0.5 - j * 0.5:.2f}", f"{rng.lognormal(0, 0.6):.4f}"] for j in range(20)]
            a = [[f"{mid + 0.5 + j * 0.5:.2f}", f"{rng.lognormal(0, 0.6):.4f}"] for j in range(20)]
            f.write(json.dumps({"t": 1767225600000 + i * 15000, "k": "d",
                                "u": i, "b": b, "a": a}) + "\n")


def _run(tmp: Path, monkeypatch, **kw):
    monkeypatch.setattr(C, "MOAT", tmp / "moat")
    monkeypatch.setattr(C, "REPORT", tmp / "out.json")
    argv = ["calibrate_impact.py"]
    for k, v in kw.items():
        argv += [f"--{k.replace('_', '-')}", str(v)]
    monkeypatch.setattr(sys, "argv", argv)
    assert C.main() == 0
    return json.loads((tmp / "out.json").read_text("utf-8"))


def test_absent_tape_reports_rather_than_synthesising(tmp_path, monkeypatch) -> None:
    """A coefficient fitted on generated depth would enter the cost model wearing the same
    vocabulary as a real one, then size every strategy on the desk."""
    rep = _run(tmp_path, monkeypatch)
    assert rep["state"] == "NO TAPE"
    assert "NOT synthesised" in rep["note"]


def test_it_calibrates_from_the_recorders_exact_schema(tmp_path, monkeypatch) -> None:
    _tape(tmp_path / "moat")
    rep = _run(tmp_path, monkeypatch)
    row = rep["symbols"][0]
    assert row["symbol"] == "binance:BTCUSDT"
    assert np.isfinite(row["impact_k"]) and row["impact_k"] > 0
    assert row["capacity_at_budget"] > 0


def test_capacity_is_reported_at_p10_as_well_as_median(tmp_path, monkeypatch) -> None:
    """Sizing to the median means being wrong exactly when liquidity is gone. What the book
    carries on a BAD day is the number that binds."""
    _tape(tmp_path / "moat")
    row = _run(tmp_path, monkeypatch)["symbols"][0]
    assert row["capacity_p10"] <= row["capacity_at_budget"]


def test_a_tighter_budget_yields_less_capacity(tmp_path, monkeypatch) -> None:
    _tape(tmp_path / "moat")
    tight = _run(tmp_path, monkeypatch, max_bps=1.0)["symbols"][0]["capacity_at_budget"]
    loose = _run(tmp_path, monkeypatch, max_bps=20.0)["symbols"][0]["capacity_at_budget"]
    assert tight <= loose


def test_a_thin_symbol_is_reported_not_fitted(tmp_path, monkeypatch) -> None:
    """A number gets used because it exists."""
    _tape(tmp_path / "moat", sym="THINUSDT", n=3)
    rep = _run(tmp_path, monkeypatch)
    thin = next(r for r in rep["symbols"] if "THIN" in r["symbol"])
    assert thin["state"] == "TOO FEW SNAPSHOTS"
    assert "impact_k" not in thin


def test_the_report_disclaims_promotion_authority(tmp_path, monkeypatch) -> None:
    _tape(tmp_path / "moat")
    assert "NONE" in _run(tmp_path, monkeypatch)["authority"]
