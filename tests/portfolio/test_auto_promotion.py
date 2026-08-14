"""THE WIRE FROM EVIDENCE TO CAPITAL, AND EVERY REASON IT REFUSES.

L1.59 names the desk's measured deficit as "the clock between holding evidence and holding a
position". Stage-B publishes ELIGIBLE the moment the bar is met and the ladder then declares
`authority: NONE -- recommendations only`, so an edge that has EARNED capital waits for a human to
read a report. This module closes that gap.

Which makes its REFUSALS the load-bearing tests. A promotion path is only safe while it cannot be
talked into a trade by a strong-looking number, so every gate below is asserted to be a hard
requirement rather than a term in a score: no arming, no promotion; no rails, no promotion; label
disagreeing with its own arithmetic, no promotion.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.portfolio import auto_promotion as ap


def _armed(tmp: Path) -> Path:
    (tmp / "data").mkdir(parents=True, exist_ok=True)
    (tmp / ap.ARMED_MARKER).write_text(
        json.dumps({"armed": True, "armed_at": "2026-08-13T00:00:00Z"}), "utf-8")
    return tmp


def _cand(**kw) -> dict:
    base = {"axis": "dip_rebound_btcusdt", "verdict": "ELIGIBLE", "forward_days": 24,
            "need": 20, "nw_t": 3.10, "holm_bar": 2.39}
    base.update(kw)
    return base


class TestArmingIsThePrincipalsAct:
    def test_UNARMED_REFUSES_EVERYTHING(self, tmp_path: Path) -> None:
        """THE ONE THAT MATTERS MOST. A perfect candidate must not promote itself."""
        d = ap.decide(_cand(), live_count=0, rails_ok=True, root=tmp_path)
        assert d.refused and d.clip_frac == 0.0
        assert "NOT armed" in d.why

    def test_a_marker_that_does_not_say_armed_is_not_arming(self, tmp_path: Path) -> None:
        (tmp_path / "data").mkdir()
        (tmp_path / ap.ARMED_MARKER).write_text(json.dumps({"armed": "yes"}), "utf-8")
        assert ap.is_armed(tmp_path)[0] is False

    def test_a_corrupt_marker_is_not_arming(self, tmp_path: Path) -> None:
        (tmp_path / "data").mkdir()
        (tmp_path / ap.ARMED_MARKER).write_text("{not json", "utf-8")
        assert ap.is_armed(tmp_path)[0] is False

    def test_the_marker_never_travels_with_the_repo(self) -> None:
        """Under data/, which is gitignored -- otherwise a clone would believe it is armed."""
        assert ap.ARMED_MARKER.startswith("data/")


class TestEvidenceIsRequiredAndSoAreTheRails:
    def test_a_rail_outranks_the_evidence(self, tmp_path: Path) -> None:
        """A rail holding the book is a statement about SURVIVAL; a Stage-B verdict is a statement
        about one edge, and the first cannot be outvoted by the second."""
        d = ap.decide(_cand(), live_count=0, rails_ok=False, rails_why="drawdown rail firing",
                      root=_armed(tmp_path))
        assert d.refused and "drawdown rail firing" in d.why

    def test_anything_but_ELIGIBLE_refuses(self, tmp_path: Path) -> None:
        root = _armed(tmp_path)
        for v in ("ACCRUING", "UNTRACKED", "DEGENERATE", "", "FAILING FORWARD -> kill"):
            assert ap.decide(_cand(verdict=v), live_count=0, rails_ok=True, root=root).refused

    def test_A_LABEL_THAT_DISAGREES_WITH_ITS_OWN_ARITHMETIC_REFUSES(self, tmp_path: Path) -> None:
        """ELIGIBLE with t BELOW the bar is a defect to investigate, not a promotion to take.
        Re-checking rather than trusting the label is the reason both fields are read."""
        d = ap.decide(_cand(nw_t=1.80, holm_bar=2.39), live_count=0, rails_ok=True,
                      root=_armed(tmp_path))
        assert d.refused and "disagree" in d.why

    def test_unmeasured_statistics_refuse_rather_than_default(self, tmp_path: Path) -> None:
        root = _armed(tmp_path)
        assert ap.decide(_cand(nw_t=None), live_count=0, rails_ok=True, root=root).refused
        assert ap.decide(_cand(holm_bar=None), live_count=0, rails_ok=True, root=root).refused

    def test_short_of_the_required_observations_refuses(self, tmp_path: Path) -> None:
        d = ap.decide(_cand(forward_days=9, need=20), live_count=0, rails_ok=True,
                      root=_armed(tmp_path))
        assert d.refused and "short of the required" in d.why

    def test_the_concurrency_cap_binds(self, tmp_path: Path) -> None:
        d = ap.decide(_cand(), live_count=ap.MAX_LIVE_STRATEGIES, rails_ok=True,
                      root=_armed(tmp_path))
        assert d.refused and "already hold auto-promoted capital" in d.why


class TestItPromotesAndSizesSmall:
    def test_a_clean_candidate_promotes(self, tmp_path: Path) -> None:
        """POSITIVE CONTROL. A path that can only refuse has not closed the gap it exists for."""
        d = ap.decide(_cand(), live_count=0, rails_ok=True, root=_armed(tmp_path))
        assert d.promote and d.clip_frac > 0.0
        assert "FIRST CLIP" in d.why

    def test_NO_CANDIDATE_EVER_EXCEEDS_THE_CAP(self, tmp_path: Path) -> None:
        """A spectacular t must not buy a large first clip: the failure this guards against is a
        CORRECT edge with a broken implementation, which is invisible in every backtest."""
        root = _armed(tmp_path)
        for t in (2.40, 4.0, 12.0, 900.0):
            d = ap.decide(_cand(nw_t=t), live_count=0, rails_ok=True, root=root)
            assert d.promote
            assert d.clip_frac <= ap.MAX_FIRST_CLIP_FRAC + 1e-12, f"t={t} broke the cap"

    def test_the_clip_is_never_so_small_it_teaches_nothing(self, tmp_path: Path) -> None:
        d = ap.decide(_cand(nw_t=2.40, holm_bar=2.39), live_count=0, rails_ok=True,
                      root=_armed(tmp_path))
        assert d.clip_frac >= ap.MAX_FIRST_CLIP_FRAC * 0.25

    def test_stronger_evidence_does_not_size_smaller(self, tmp_path: Path) -> None:
        root = _armed(tmp_path)
        weak = ap.decide(_cand(nw_t=2.45), live_count=0, rails_ok=True, root=root)
        strong = ap.decide(_cand(nw_t=6.00), live_count=0, rails_ok=True, root=root)
        assert strong.clip_frac >= weak.clip_frac

    def test_THERE_IS_NO_CALENDAR_GATE(self, tmp_path: Path) -> None:
        """EVIDENCE DETERMINES SIZE; TIME DOES NOT (L1.48/L1.59). A candidate that reached the bar
        quickly must promote exactly like one that took months -- adding 'and at least N days'
        would reintroduce the grandma-time habit the evidence clock abolished."""
        root = _armed(tmp_path)
        fast = ap.decide(_cand(forward_days=20, need=20), live_count=0, rails_ok=True, root=root)
        slow = ap.decide(_cand(forward_days=400, need=20), live_count=0, rails_ok=True, root=root)
        assert fast.promote and slow.promote
        assert fast.clip_frac == pytest.approx(slow.clip_frac)


class TestReporting:
    def test_refusals_are_reported_as_first_class(self, tmp_path: Path) -> None:
        root = _armed(tmp_path)
        ds = [ap.decide(_cand(), live_count=0, rails_ok=True, root=root),
              ap.decide(_cand(axis="b", verdict="ACCRUING"), live_count=0, rails_ok=True,
                        root=root)]
        s = ap.summarise(ds)
        assert s["n_promoted"] == 1 and s["n_refused"] == 1
        assert s["refusals"][0]["why"]
        assert "indistinguishable from one that" in s["note"]


def _armed_root(tmp_path):
    import json

    from libs.portfolio.auto_promotion import ARMED_MARKER
    p = tmp_path / ARMED_MARKER
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"armed": True, "armed_at": "2026-08-14"}), "utf-8")
    return tmp_path


_ELIGIBLE = {"name": "carry", "verdict": "ELIGIBLE", "nw_t": 4.0, "holm_bar": 2.6,
             "forward_days": 40, "need": 30}


def test_A_CLIP_BELOW_VENUE_MINIMUM_IS_REFUSED_NOT_ROUNDED_UP(tmp_path) -> None:
    """FOUND THE MOMENT A REAL SMALL BOOK WAS PROPOSED (2026-08-14, $200 deployable). 2% of $200
    is $4 and venue minimum notional is ~$5-10 PER LEG, so the earned clip is unplaceable.

    Without this the module returns PROMOTE with a clip the executor cannot place, and the failure
    surfaces as a rejected order rather than a refused promotion -- a decision that looks taken, is
    logged as taken, and never happens.

    ROUNDING UP WOULD BE WORSE THAN REFUSING: it breaches the cap silently, in the one direction
    that puts more money on an unproven edge than the principal authorised."""
    from libs.portfolio.auto_promotion import decide

    d = decide(_ELIGIBLE, live_count=0, rails_ok=True, root=_armed_root(tmp_path),
               deployable_usd=200.0, min_notional_usd=10.0)
    assert d.refused and d.clip_frac == 0.0
    assert "BELOW the venue minimum" in d.why
    assert "too small to hold this position" in d.why


def test_THE_SAME_CANDIDATE_IS_PROMOTED_ON_A_BOOK_THAT_CAN_HOLD_IT(tmp_path) -> None:
    """The refusal is about the BOOK, not the edge -- so it must lift when the book grows."""
    from libs.portfolio.auto_promotion import decide

    d = decide(_ELIGIBLE, live_count=0, rails_ok=True, root=_armed_root(tmp_path),
               deployable_usd=2000.0, min_notional_usd=10.0)
    assert d.promote and d.clip_frac > 0


def test_OMITTING_THE_NOTIONAL_LEAVES_BEHAVIOUR_UNCHANGED(tmp_path) -> None:
    """A caller that cannot supply the venue minimum gets the pre-existing behaviour rather than a
    fabricated one: guessing a minimum here would refuse real promotions on an invented number."""
    from libs.portfolio.auto_promotion import decide

    d = decide(_ELIGIBLE, live_count=0, rails_ok=True, root=_armed_root(tmp_path))
    assert d.promote
