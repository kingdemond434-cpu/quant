"""R0479 -- the pre-registered forward test of the narrower trail, pinned.

The in-sample evidence (capture ratio 0.335 over 14 closes, trail_sweep best 0.5R at n=9) is a
hypothesis-generator with zero authority; the deliverable was a PRE-REGISTERED forward test, not
a config edit. These tests pin the properties that make it one:

  * only trades ENTERED after the frozen registration instant count -- in-sample and unparseable
    stamps are excluded (the conservative direction),
  * the statistic is PAIRED (both widths on one trade's identical bars); a trade missing either
    width drops out rather than polluting the pairing,
  * every verdict state follows the frozen rule: nothing before n=25, adopt/refute at |t|>=1.7,
    hard stop at n=50,
  * the two candidate mechanisms stay separated: a forward sample where most closes never arm
    the trail says the LADDER is the binding lever, out loud.
"""
from __future__ import annotations

import math

from scripts.resolve_paper_book import (
    TRAIL_FWD_CHALLENGER,
    TRAIL_FWD_DECIDE_N,
    TRAIL_FWD_HARD_N,
    TRAIL_R,
    trail_forward,
)

_PAST = "2026-08-01T00:00:00+00:00"      # before registration: in-sample
_FWD = "2026-09-{d:02d}T00:00:00+00:00"  # after registration: forward


def _swept_pair(key: str, eq_challenger: float, eq_live: float) -> list[dict]:
    return [{"trail_r": TRAIL_FWD_CHALLENGER, "key": key, "realised_R": 0.0,
             "equity_return": eq_challenger},
            {"trail_r": TRAIL_R, "key": key, "realised_R": 0.0, "equity_return": eq_live}]


def _fwd_keys(n: int) -> list[str]:
    return [f"2026-09-01T{h:02d}:{m:02d}:00+00:00" for h in range(24) for m in range(60)][:n]


class TestForwardSplit:
    def test_in_sample_trades_are_excluded(self):
        swept = _swept_pair(_PAST, 0.05, 0.01)
        out = trail_forward(swept, [])
        assert out["state"] == "ACCRUING"
        assert out["n_paired_forward"] == 0, "a pre-registration trade must never count forward"

    def test_unparseable_key_cannot_prove_it_is_forward(self):
        out = trail_forward(_swept_pair("not-a-timestamp", 0.05, 0.01), [])
        assert out["n_paired_forward"] == 0

    def test_a_trade_missing_one_width_is_not_a_pair(self):
        swept = [{"trail_r": TRAIL_FWD_CHALLENGER, "key": _FWD.format(d=1),
                  "equity_return": 0.05}]
        out = trail_forward(swept, [])
        assert out["n_paired_forward"] == 0


class TestVerdictLadder:
    def _swept(self, n: int, eq_c: float, eq_l: float, jitter: float = 0.001) -> list[dict]:
        rows: list[dict] = []
        for i, k in enumerate(_fwd_keys(n)):
            # deterministic jitter so the paired sd is non-zero without an RNG
            rows += _swept_pair(k, eq_c + jitter * math.sin(i), eq_l)
        return rows

    def test_no_verdict_before_the_decision_point(self):
        out = trail_forward(self._swept(TRAIL_FWD_DECIDE_N - 1, 0.05, 0.01), [])
        assert out["state"] == "ACCRUING"
        assert "NO authority" in out["why"]

    def test_adopt_bar_met_on_strong_positive(self):
        out = trail_forward(self._swept(TRAIL_FWD_DECIDE_N, 0.05, 0.01), [])
        assert out["state"] == "ADOPT-BAR-MET"
        assert out["t_stat"] >= 1.7
        assert "authorised" in out["why"]

    def test_refuted_on_strong_negative(self):
        out = trail_forward(self._swept(TRAIL_FWD_DECIDE_N, 0.01, 0.05), [])
        assert out["state"] == "REFUTED"
        assert "NO EXTENSIONS" in out["why"]

    def test_indistinguishable_at_the_hard_stop(self):
        # mean difference ~0 with real spread: alternating sign, magnitude >> mean
        rows: list[dict] = []
        for i, k in enumerate(_fwd_keys(TRAIL_FWD_HARD_N)):
            rows += _swept_pair(k, 0.01 + (0.02 if i % 2 else -0.02), 0.01)
        out = trail_forward(rows, [])
        assert out["state"] == "INDISTINGUISHABLE"
        assert "retired" in out["why"]

    def test_continue_between_decide_and_hard_stop(self):
        rows: list[dict] = []
        for i, k in enumerate(_fwd_keys(TRAIL_FWD_DECIDE_N)):
            rows += _swept_pair(k, 0.01 + (0.02 if i % 2 else -0.02), 0.01)
        out = trail_forward(rows, [])
        assert out["state"] == "CONTINUE"


class TestMechanismSeparation:
    def _mark(self, key: str, stage: int, max_stage: int) -> dict:
        return {"kind": "conviction", "closed": True, "key": key,
                "stage_reached": stage, "max_stage": max_stage}

    def test_ladder_rarely_climbed_is_said_out_loud(self):
        marks = [self._mark(_FWD.format(d=i + 1), 0, 2) for i in range(8)]
        marks += [self._mark(_FWD.format(d=20), 2, 2)]
        out = trail_forward([], marks)
        assert out["share_reaching_trail"] is not None
        assert out["share_reaching_trail"] < 0.5
        assert "LADDER" in out["why"], "mechanism (b) must be named, not folded into the verdict"

    def test_in_sample_marks_do_not_count_toward_the_share(self):
        marks = [self._mark(_PAST, 0, 2)]
        out = trail_forward([], marks)
        assert out["share_reaching_trail"] is None
        assert out["n_forward_closed"] == 0
