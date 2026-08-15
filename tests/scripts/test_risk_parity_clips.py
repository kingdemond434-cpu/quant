"""RISK-PARITY SLEEVE SIZING -- that it equalises RISK, and that it never reads a RETURN.

The second property is the legal one. L1.6 withholds from the backtest the authority to allocate
capital and the live exception did not restore it, so a sizing rule that touched the MEAN of a
backtest series would be the violation regardless of how well it performed. These tests pin the
distinction rather than trusting the docstring that claims it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import scripts.run_mechanism_sleeves as ms

_LEDGER = Path(__file__).resolve().parents[2] / "docs/research/LIVE_EXCEPTION_LEDGER.json"


class _Ser:
    def __init__(self, close: list[float]) -> None:
        self.close = np.asarray(close, dtype="float64")


def _walk(n: int, vol: float, *, seed: int = 0, drift: float = 0.0) -> list[float]:
    rng = np.random.default_rng(seed)
    r = rng.normal(drift, vol, n)
    return list(100.0 * np.exp(np.cumsum(r)))


class TestTheEnvelopeIsFixed:
    def test_shares_sum_to_one_across_ALL_sleeves(self) -> None:
        clips, _ = ms._risk_parity_clips({"a": 0.01, "b": 0.02, "c": 0.04})
        assert sum(clips.values()) == pytest.approx(1.0)

    def test_a_flat_sleeve_keeps_its_share_unspent_rather_than_donating_it(self) -> None:
        # Normalising over LIVE sleeves only would raise the book's gross exposure on exactly the
        # days fewest mechanisms found anything to trade.
        clips, _ = ms._risk_parity_clips({"a": 0.02, "b": 0.02, "c": 0.02})
        assert clips["a"] == pytest.approx(1 / 3)
        assert sum(clips.values()) == pytest.approx(1.0)

    def test_capping_preserves_the_sum(self) -> None:
        # One sleeve with a near-zero vol would otherwise take the whole book.
        clips, why = ms._risk_parity_clips({"a": 1e-9, "b": 0.05, "c": 0.05, "d": 0.05})
        assert sum(clips.values()) == pytest.approx(1.0)
        assert clips["a"] <= (1.0 / 4) * ms.MAX_CLIP_MULTIPLE + 1e-9
        assert "clipped" in why


class TestItEqualisesRisk:
    def test_the_quieter_sleeve_gets_the_bigger_clip(self) -> None:
        clips, _ = ms._risk_parity_clips({"quiet": 0.01, "wild": 0.04})
        assert clips["quiet"] > clips["wild"]

    def test_risk_contributions_are_closer_than_equal_dollars_would_give(self) -> None:
        vols = {"a": 0.01, "b": 0.02, "c": 0.03}
        clips, _ = ms._risk_parity_clips(vols)
        rp = [clips[k] * v for k, v in vols.items()]
        eq = [(1 / 3) * v for v in vols.values()]
        spread = lambda xs: max(xs) / min(xs)          # noqa: E731 - local, one use
        assert spread(rp) < spread(eq)


class TestUnmeasuredIsNotAnOpportunity:
    def test_an_unmeasurable_sleeve_gets_the_EQUAL_share_not_the_largest(self) -> None:
        # An unmeasured risk is not a licence to size up (L1.28a). Inverting `None` to a huge
        # weight is the failure this pins: it would hand the book to whichever sleeve had the
        # least data.
        clips, _ = ms._risk_parity_clips({"known_wild": 0.10, "known_wild2": 0.10, "unknown": None})
        assert clips["unknown"] == pytest.approx(clips["known_wild"], rel=0.35)
        assert clips["unknown"] < ms.MAX_CLIP_MULTIPLE / 3

    def test_all_unmeasurable_falls_back_to_equal_and_says_so(self) -> None:
        clips, why = ms._risk_parity_clips({"a": None, "b": None})
        assert clips == {"a": 0.5, "b": 0.5}
        assert "UNMEASURABLE" in why

    def test_no_sleeves_is_empty_not_a_division_by_zero(self) -> None:
        clips, _ = ms._risk_parity_clips({})
        assert clips == {}


class TestItNeverReadsAReturn:
    """III.15: a sleeve is never sized up for PERFORMING well. Same vol, same clip, whatever the
    P&L did -- this is the property that separates risk parity from progression."""

    def test_a_winning_and_a_losing_sleeve_with_equal_vol_get_equal_clips(self) -> None:
        frames = {"S": _Ser(_walk(400, 0.02, seed=1))}
        up = {"S": np.ones(400)}                  # long the whole way
        down = {"S": -np.ones(400)}               # short the whole way -- the exact opposite P&L
        v_up = ms._sleeve_vol(up, frames)
        v_down = ms._sleeve_vol(down, frames)
        assert v_up is not None and v_down is not None
        assert v_up == pytest.approx(v_down, rel=1e-9), (
            "the sizing rule can tell a winner from a loser -- that is progression, not parity")

    def test_vol_scales_with_position_size_not_with_direction(self) -> None:
        frames = {"S": _Ser(_walk(400, 0.02, seed=2))}
        small = ms._sleeve_vol({"S": np.full(400, 0.5)}, frames)
        big = ms._sleeve_vol({"S": np.full(400, 1.0)}, frames)
        assert small is not None and big is not None
        assert big == pytest.approx(2.0 * small, rel=1e-9)


class TestTheLedgerAndTheCodeAgree:
    """A declared exception whose TERMS have quietly moved is the failure the ledger exists to
    prevent. The sizing rule changed on 2026-08-15, so the record must carry the amendment and the
    amendment must describe what the code actually does -- checked, not assumed."""

    @staticmethod
    def _terms() -> dict[str, Any]:
        doc = json.loads(_LEDGER.read_text("utf-8"))
        row = next(r for r in doc["exceptions"] if r["id"] == "live-mechanism-sleeves")
        return dict(row["terms_fixed_before_the_first_fill"])

    def test_the_sizing_change_is_recorded_rather_than_silent(self) -> None:
        amend = self._terms().get("sizing_amendment")
        assert amend, ("clips are no longer equal dollars and the ledger does not say so -- the "
                       "terms of a declared exception moved without a record")
        for key in ("why", "what_it_reads", "why_that_is_not_the_suspended_rule",
                    "why_it_is_not_progression", "the_assumption_it_makes", "the_guard"):
            assert str(amend.get(key, "")).strip(), f"the amendment states no {key}"

    def test_the_recorded_cap_is_the_cap_the_code_applies(self) -> None:
        assert f"{ms.MAX_CLIP_MULTIPLE:g}x" in self._terms()["sizing_amendment"]["the_guard"]

    def test_the_recorded_envelope_is_the_envelope_the_code_uses(self) -> None:
        # The amendment's whole claim is that no risk limit moved. If clip_frac drifts from the
        # module, that claim is false and this is the only thing that would notice.
        assert self._terms()["clip_frac"] == pytest.approx(ms.EQUAL_CLIP_FRAC)

    def test_the_amendment_names_the_test_that_pins_it(self) -> None:
        # A guarantee that names no enforcement is prose. This class is the enforcement.
        assert "test_risk_parity_clips" in self._terms()["sizing_amendment"][
            "why_it_is_not_progression"]


class TestTheVolItself:
    def test_the_position_is_lagged_one_bar(self) -> None:
        # A position multiplied by the SAME bar's return is a sleeve trading on a close it could
        # not have seen, and the volatility of that series is not the volatility of anything
        # tradeable. Planted: a quiet walk with ONE 100% jump, and a sleeve that is flat going
        # INTO the jump and long everywhere else. Lagged correctly the jump contributes nothing;
        # read unlagged it dominates the estimate and the sleeve looks ten times riskier.
        close = _walk(60, 0.01, seed=7)
        close[21:] = [c * 2.0 for c in close[21:]]      # the jump lands in r[20]
        pos = np.ones(60)
        pos[20] = 0.0                                   # flat at the bar the jump is earned from
        v = ms._sleeve_vol({"S": pos}, {"S": _Ser(close)})
        assert v is not None
        assert v < 0.05, ("the jump was counted, so the position was multiplied by the return of "
                          "the bar it was entered on")

    def test_a_short_series_is_None_not_zero(self) -> None:
        assert ms._sleeve_vol({"S": np.ones(2)}, {"S": _Ser([100.0, 101.0])}) is None

    def test_a_never_traded_sleeve_is_None_rather_than_a_zero_vol(self) -> None:
        # Zero would invert to an infinite clip. None routes to the equal share instead.
        v = ms._sleeve_vol({"S": np.zeros(400)}, {"S": _Ser(_walk(400, 0.02, seed=3))})
        assert v is None

    def test_a_mismatched_length_is_skipped_rather_than_zipped(self) -> None:
        assert ms._sleeve_vol({"S": np.ones(10)}, {"S": _Ser(_walk(400, 0.02))}) is None
