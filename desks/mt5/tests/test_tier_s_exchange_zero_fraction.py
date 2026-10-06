"""An exchange ZERO zeroes the sleeve's FRACTION in the final book, not only its posterior mean.

Until 2026-09-30 the Tier S tilt took a zeroed sleeve's mean to 0 and stopped there: the solve,
the floor fill (which relaxes the bounds), a NO CHANGE hold, the explore lend and the baseline
books the gateway falls back to could each fund it again. These tests drive a small fixture
through the same functions `pf_allocator.run` chains -- the evidence tilt, the bounded solve, the
final-book refill, the contest's baseline books and the gateway's fallback sizing -- and pin that
the zeroed sleeve holds 0 everywhere while the total heat the heat law resolved is unchanged.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pf_allocator as pfa  # type: ignore[import-not-found]  # noqa: E402

from libs.portfolio import allocator_evidence as ae  # noqa: E402
from libs.portfolio.robust_elog import (  # noqa: E402
    SleeveEvidence,
    WorldConfig,
    optimise,
    sample_worlds,
)

FLOOR = 0.20


def _ev() -> list[SleeveEvidence]:
    rng = np.random.default_rng(7)
    # Z is the BEST sleeve on its own evidence, so anything that funds it on merit will.
    spec = (("A", 0.10), ("Z", 0.20), ("N", 0.08))
    return [SleeveEvidence(n, rng.normal(mu, 1.0, 500), family=f"fam{i}", symbol=f"S{i}",
                           forward_days=60)
            for i, (n, mu) in enumerate(spec)]


def test_exchange_zero_reaches_every_path_with_the_heat_refilled(monkeypatch: Any,
                                                                  tmp_path: Path) -> None:
    monkeypatch.setattr(ae, "tier_s_factors",
                        lambda **k: ({"A": 1.2, "Z": 0.0, "N": 1.2}, "test"))
    ev = _ev()
    meta = pfa.apply_allocator_evidence(ev, None, None)
    assert meta["tier_s_zeroed"] == ["Z"], "the exchange's zero is named, not only applied"
    zero = frozenset(meta["tier_s_zeroed"])

    # THE SOLVE: bounded at 0 for Z even though the bounds did not name it (inf by default)
    cfg = WorldConfig(seed=0, n_worlds=64, n_rows=128)
    worlds = sample_worlds(ev, cfg)
    bounds = pfa.exchange_zero_bounds({"A": 0.15, "N": 0.15}, zero)
    assert bounds["Z"] == 0.0
    book = optimise(ev, hard_cap=1.0, target=FLOOR, cfg=cfg, worlds=worlds,
                    max_per_sleeve=bounds)
    assert book.heat.get("Z", 0.0) <= 1e-9
    assert book.total_heat == pytest.approx(FLOOR, abs=1e-4), "the floor is still filled"

    # THE FINAL BOOK: a hold / floor fill that carried Z is refilled at the same total
    held = {"A": 0.06, "Z": 0.10, "N": 0.04}
    out, why = pfa.exchange_zero(held, zero, bounds=bounds, eligible=[e.name for e in ev])
    assert "Z" not in out and why["status"] == "REFILLED"
    assert sum(out.values()) == pytest.approx(FLOOR)
    assert out["A"] == pytest.approx(0.12) and out["N"] == pytest.approx(0.08)

    # THE CONTEST'S BOOKS: equal weight and the bench are built over the whole universe
    from libs.portfolio.allocator_proof import contest
    funded = {k: v for k, v in book.heat.items() if v > 1e-5}
    proof = contest(ev, funded, None, cfg=cfg, worlds=worlds, root=tmp_path)
    before = {k: sum(b.values()) for k, b in proof["books"].items()}
    assert proof["books"]["equal_weight"].get("Z", 0.0) > 0.0, "the fixture exercises the leak"
    res = pfa.zero_contested_books(proof, zero, eligible=[e.name for e in ev])
    assert "equal_weight" in res["books_changed"]
    for k, b in proof["books"].items():
        assert b.get("Z", 0.0) == 0.0, k
        assert sum(b.values()) == pytest.approx(before[k]), f"{k} kept its total heat"

    # THE GATEWAY'S FALLBACK SIZING reads those books: Z sizes at zero, the total is intact
    from mt5desk.decision_core import book_from_allocation
    sized, _why = book_from_allocation(
        FLOOR, funded, {"name": "equal_weight", "book": proof["books"]["equal_weight"]},
        certified=False, why="proof stale", zeroed={"Z": "exchange zero"})
    assert sized is not None
    assert sized.get("Z", 0.0) == 0.0
    assert sum(sized.values()) == pytest.approx(FLOOR, abs=5e-3)


def test_refill_spills_past_bounds_rather_than_cut_heat() -> None:
    z = frozenset({"Z"})
    out, why = pfa.exchange_zero({"A": 0.06, "Z": 0.10, "N": 0.04}, z,
                                 bounds={"A": 0.07, "N": 0.07})
    assert "Z" not in out and sum(out.values()) == pytest.approx(0.20)
    assert why["spilled_past_bounds"] == pytest.approx(0.06)


def test_a_book_of_only_zeroed_sleeves_is_refilled_across_the_universe() -> None:
    z = frozenset({"Z"})
    out, why = pfa.exchange_zero({"Z": 0.20}, z, eligible=["A", "Z", "N"])
    assert out == pytest.approx({"A": 0.10, "N": 0.10})
    assert why["basis"].startswith("equally")
    same, why2 = pfa.exchange_zero({"Z": 0.20}, z, eligible=["Z"])
    assert same == {"Z": 0.20} and why2["status"] == "UNREFILLABLE", "heat is never cut"


def test_nothing_changes_without_a_zero() -> None:
    book = {"A": 0.12, "N": 0.08}
    out, why = pfa.exchange_zero(book, frozenset({"Z"}))
    assert out == book and why["status"] == "NOTHING_HELD"
    proof: dict[str, Any] = {"books": {"equal_weight": {"A": 0.1, "N": 0.1}}}
    assert pfa.zero_contested_books(proof, frozenset())["status"] == "NONE"


def test_run_binds_the_zero_on_every_solve_and_the_published_book() -> None:
    src = (DESK / "research" / "pf_allocator.py").read_text("utf-8")
    run_src = src[src.index("def run(mode"):]
    assert "per_sleeve_bounds(dd," not in run_src, "every solve's bounds carry the zero"
    assert "exchange_zero(funded, ts_zero" in run_src
    assert "zero_contested_books(" in run_src
    assert run_src.index("zero_contested_books(") < run_src.index("certify(proof")
    assert '"exchange_zero": exchange_zero_meta' in run_src
