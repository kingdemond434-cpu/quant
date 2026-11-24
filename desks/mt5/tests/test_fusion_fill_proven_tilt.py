"""Fusion reads the same FILL_PROVEN.json as E8 and FTMO, as a heat-neutral two-sided tilt."""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pf_allocator as pfa  # type: ignore[import-not-found]  # noqa: E402

from libs.portfolio import allocator_evidence as ae  # noqa: E402
from libs.portfolio.robust_elog import SleeveEvidence  # noqa: E402

NOW = datetime(2026, 11, 24, 18, 0, tzinfo=UTC)
NAMES = ["P_proven_asia", "N_negative_asia", "U_unjudged_asia", "T_thin_asia"]


def _doc(age_h: float = 0.5, schema: str = "fill-proven/1") -> dict[str, Any]:
    table = [{"sleeve": "P_proven_asia", "n_out": 50, "adjR_out": 0.4},
             {"sleeve": "N_negative_asia", "n_out": 50, "adjR_out": -0.3},
             {"sleeve": "T_thin_asia", "n_out": 5, "adjR_out": 2.0}]
    return {"schema": schema, "generated_at": (NOW - timedelta(hours=age_h)).isoformat(),
            "sleeves": [{"sleeve": "P_proven_asia", "n_out": 50, "adjR_out": 0.4}],
            "table": table}


def test_proven_leans_up_negative_leans_down_rest_neutral_and_book_mean_is_one():
    f, why = ae.fill_proven_factors(NAMES, _doc(), now=NOW)
    assert set(f) == {"P_proven_asia", "N_negative_asia"}, why
    assert f["P_proven_asia"] > 1.0 > f["N_negative_asia"]
    # heat-neutral: with the unjudged names at 1.0 / mean, the book averages 1.0
    mean = (f["P_proven_asia"] + f["N_negative_asia"]) / 4 + 2 * (1.0 / 1.0) / 4
    assert abs(mean - 1.0) < 1e-9


def test_a_positive_sleeve_that_failed_fdr_is_not_raised():
    d = _doc()
    d["sleeves"] = []
    f, _ = ae.fill_proven_factors(NAMES, d, now=NOW)
    assert "P_proven_asia" not in f and f["N_negative_asia"] < 1.0


def test_stale_foreign_undated_or_future_reads_neutral():
    for d in (_doc(age_h=4), _doc(schema="fill-proven/0"), _doc(age_h=-1),
              {**_doc(), "generated_at": "nope"},
              {**_doc(), "generated_at": "2026-11-24T17:00:00"}):
        assert ae.fill_proven_factors(NAMES, d, now=NOW)[0] == {}


def test_the_tilt_reaches_the_solve_inputs(monkeypatch: Any):
    monkeypatch.setattr(ae, "fill_proven_factors",
                        lambda names, **k: ({"A": 1.3, "B": 0.7}, "test"))
    rng = np.random.default_rng(3)
    ev = [SleeveEvidence(n, rng.normal(0.1, 1.0, 400), family=f"f{i}", symbol=f"S{i}",
                         forward_days=60) for i, n in enumerate(("A", "B", "C"))]
    before = {e.name: float(np.nanmean(e.daily_r)) for e in ev}
    meta = pfa.apply_allocator_evidence(ev, None, None)
    after = {e.name: float(np.nanmean(e.daily_r)) for e in ev}
    assert meta["fill_proven"] == "test" and meta["n_fill_proven_tilted"] == 2
    assert after["A"] > before["A"] and after["B"] < before["B"]
    assert meta["by_sleeve"]["A"]["fill_proven_factor"] == 1.3
