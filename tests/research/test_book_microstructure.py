"""Six order-book constructions, charged as ONE family -- and the refusals that keep it honest.

The principal supplied 175 candidate alphas. Items 7-14 and 26-55 are not thirty-eight mechanisms;
they are thirty-eight constructions of `orderbook_microstructure_state`. 175 hypotheses at
alpha=0.05 is ~9 false positives by construction, and the family partition does not exempt
constructions of the SAME claim from paying for each other.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.discretionary.tape import BookState
from libs.research import book_microstructure as B


def _books(n: int, *, lead: float = 0.0, seed: int = 7) -> list[BookState]:
    """A book where the CHANGE in imbalance leads the mid by the screen's own horizon."""
    rng = np.random.default_rng(seed)
    mid, prev, pending, out = 100.0, 0.0, [], []
    for i in range(n):
        imb = float(np.clip(0.5 * prev + rng.normal(0, 0.25), -1, 1))
        pending.append(imb - prev)
        drift = lead * pending.pop(0) if len(pending) > 12 else 0.0
        mid *= 1 + drift + rng.normal(0, 0.0003)
        out.append(BookState(ts=i * 5000, mid=mid, spread_bps=2.0, imbalance=imb,
                             slope=1000.0, depth_usd=1e6))
        prev = imb
    return out


def test_IT_FINDS_A_LEAD_THE_CONSTRUCTIONS_CAN_EXPRESS() -> None:
    """The screen must be capable of a positive. A machine that refutes everything is
    indistinguishable from a broken one, and both produce a clean-looking report."""
    rep = B.screen(_books(1400, lead=0.0009))
    assert rep["status"] == "RUN"
    assert rep["n_survivors"] >= 1
    top = rep["results"][0]
    assert top["verdict"] == "SURVIVES-STAGE-A" and abs(top["t"]) >= top["bh_bar"]


def test_IT_REFUTES_A_BOOK_THAT_LEADS_NOTHING() -> None:
    """A rule that fires on both is a rule that fires on anything."""
    rep = B.screen(_books(1400, lead=0.0))
    assert rep["n_survivors"] == 0
    assert all(r["verdict"] in {"REFUTED", "DEGENERATE"} for r in rep["results"])


def test_THE_BAR_TIGHTENS_WITH_THE_NUMBER_OF_CONSTRUCTIONS() -> None:
    """THE WHOLE POINT OF CHARGING THEM TOGETHER. The strongest faces alpha/m, not alpha -- six
    constructions is not six free trials, and the uncorrected bar is published beside it so the
    cost is visible rather than asserted."""
    rep = B.screen(_books(1400, lead=0.0009))
    ranked = sorted(rep["results"], key=lambda r: r["rank"])
    assert ranked[0]["bh_bar"] > B.uncorrected_bar()
    # BH bars are t-thresholds: rank 1 faces alpha/m (the HIGHEST t) and rank m faces alpha (the
    # lowest). So the sequence DESCENDS with rank -- it loosens as more discoveries are made.
    bars = [r["bh_bar"] for r in ranked]
    assert bars == sorted(bars, reverse=True), "the bar must loosen with rank, never tighten"
    assert bars[0] > bars[-1], "the strongest construction faces the tightest bar"


def test_A_SHORT_SAMPLE_IS_UNDERPOWERED_AND_NEVER_REFUTED() -> None:
    """A null on a sample too small to detect the effect is a statement about the sample."""
    rep = B.screen(_books(150, lead=0.0009))
    assert rep["status"] == "UNDERPOWERED" and rep["verdict"] == "UNMEASURED"
    assert rep["results"] == []


def test_THE_UNSUPPORTED_CONSTRUCTIONS_ARE_NAMED_NOT_SILENTLY_DROPPED() -> None:
    """A snapshot cannot reconstruct order-level adds and cancels: two snapshots with equal depth
    are consistent with no activity AND with a thousand adds matched by a thousand cancels.
    Computing them anyway would produce a number instead of a refusal, which is the more expensive
    error -- so the refusal is on the record."""
    assert "cancellation_pressure" in B.UNSUPPORTED
    assert "iceberg_inference" in B.UNSUPPORTED
    for why in B.UNSUPPORTED.values():
        assert len(why) > 40, "an unsupported construction must say WHY, not just be absent"
    assert not set(B.UNSUPPORTED) & {n for n, _ in B.CONSTRUCTIONS}


def test_NON_FINITE_PAIRS_ARE_DROPPED_NOT_ZEROED() -> None:
    """A zero enters the sample as a real observation of no relationship and drags the estimate
    toward the null with fabricated data."""
    ic, n = B._ic([1.0, float("nan"), 2.0, 3.0], [1.0, 5.0, 2.0, 3.0])
    assert n == 3 and ic == pytest.approx(1.0)


def test_A_DEGENERATE_SERIES_IS_NOT_A_KILL() -> None:
    ic, n = B._ic([1.0] * 50, list(range(50)))
    assert ic is None and n == 50


def test_EVERY_CONSTRUCTION_CITES_THE_ITEM_IT_IMPLEMENTS() -> None:
    """Six of 175 were built. Which six, and why those, must be readable from the module rather
    than reconstructed from a chat log."""
    for name, claim in B.CONSTRUCTIONS:
        assert "item " in claim, f"{name} does not cite the candidate it implements"
        assert len(claim) > 80, f"{name} carries no mechanism statement"
    assert B.N_CONSTRUCTIONS == len(B.CONSTRUCTIONS) == 6
