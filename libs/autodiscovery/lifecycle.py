"""Automated promotion state machine — never allocates real capital.

    fail validation                  -> REJECTED   (archive)
    pass validation, fail shadow     -> SHADOW      (archive; reached shadow)
    pass shadow, fail paper          -> PAPER       (archive; reached paper)
    pass paper                       -> REGISTRY    (survivor; awaits HUMAN approval for live)

Shadow = positive on a held-out recent segment the validation never saw; paper = positive on an
even-more-recent segment. Both are accelerated stand-ins for wall-clock shadow/paper; real live
capital is never allocated automatically — REGISTRY only means "eligible for human review".
"""

from __future__ import annotations

import numpy as np

from libs.autodiscovery.models import CandidateStatus

_SHADOW_TAIL = 0.15
_PAPER_TAIL = 0.05


def segment_pass(returns: np.ndarray, *, tail: float) -> bool:
    """Whether the final ``tail`` fraction of the series has a positive mean return."""
    arr = np.asarray(returns, dtype="float64")
    cut = int(len(arr) * (1.0 - tail))
    seg = arr[cut:]
    return len(seg) > 1 and float(seg.mean()) > 0.0


def promote(returns: np.ndarray, *, validation_survived: bool) -> CandidateStatus:
    """Resolve the terminal lifecycle status from validation + accelerated shadow/paper segments."""
    if not validation_survived:
        return CandidateStatus.REJECTED
    if not segment_pass(returns, tail=_SHADOW_TAIL):
        return CandidateStatus.SHADOW   # reached shadow, failed it -> archived
    if not segment_pass(returns, tail=_PAPER_TAIL):
        return CandidateStatus.PAPER    # reached paper, failed it -> archived
    return CandidateStatus.REGISTRY     # full survivor (human approval still required for live)
