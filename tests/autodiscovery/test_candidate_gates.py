"""Per-gate verdicts survive the write (m0008 / R0586), and absence stays distinguishable.

WHAT WAS LOST AND WHY IT MATTERED. ``validate()`` returns a ``ValidationVerdict`` carrying
``gates: dict[str, bool]`` and ``unmeasured: tuple[str, ...]``. The orchestrator read
``survived`` and ``rejection_reason`` off it and dropped the rest, and ``CandidateStore.record``
was never given the verdict at all -- so the per-gate outcome existed only in memory. The only
surviving trace was the prose in ``rejection_reason``, and string-parsing that decayed from
1,353/1,654 rows (82%, 2026-08-13) to 12,536/25,039 (50.1%, 2026-08-20): the denominator of every
gate statistic the desk computes, shrinking silently as the store grew (L1.60).

THE LOAD-BEARING CASE IS THE THIRD TEST. A pre-m0008 row has NULL in the new column and must read
back as ``gates is None`` -- "no verdict was ever recorded" -- and never as ``{}``, which would
say a verdict WAS recorded and contained no failing gate. 25,039 unrecorded candidates reading as
"nothing failed" is absence resolving to a clean verdict (L1.28a, WS-005), in the direction that
flatters the desk.
"""

from __future__ import annotations

import json
import sqlite3

import numpy as np
import pytest

from libs.autodiscovery.memory import CandidateSeries, CandidateStore
from libs.autodiscovery.models import (
    CandidateStatus,
    Family,
    Hypothesis,
    ValidationMetrics,
)
from libs.autodiscovery.validation import _CPCV_MIN_POSITIVE, validate
from libs.store.connection import Database
from libs.validation.economic_prior import MechanismType

_GATES = {"dsr": False, "pbo": True, "economic_mechanism": True}
_UNMEASURED = ("stationary",)


def _hyp() -> Hypothesis:
    return Hypothesis(
        family=Family.TREND, subtype="ma_cross", symbol="EURUSD",
        params={"fast": 20.0, "slow": 50.0}, mechanism=MechanismType.BEHAVIORAL,
        edge_source="trend", failure_modes=["chop"],
    )


def _record(store: CandidateStore, **kw: object) -> str:
    rec = store.record(
        campaign_id="camp_t", hyp=_hyp(), status=CandidateStatus.REJECTED,
        metrics=kw.pop("metrics", None) or ValidationMetrics(),
        survived=False, rejection_reason="failed: dsr",
        series=CandidateSeries(net=np.linspace(0.0, 1.0, 32), stressed=None,
                               epoch_key="EURUSD:32", timeframe="D1"),
        **kw,  # type: ignore[arg-type]
    )
    return rec.id


def test_gates_round_trip_through_the_store(db: Database) -> None:
    """The dict the verdict carried is the dict a later reader gets back."""
    store = CandidateStore(db)
    cid = _record(store, gates=_GATES, unmeasured=_UNMEASURED)

    (rec,) = [r for r in store.all() if r.id == cid]
    assert rec.gates == _GATES
    assert rec.unmeasured == _UNMEASURED


def test_dropped_numerics_are_persisted(db: Database) -> None:
    """``expected_value`` and the cpcv positive-fraction reach disk instead of round-tripping to 0.

    Both were computed by ``validate()`` and then not bound at the INSERT, so every readback
    returned the field default. A metric that always reads 0.0 is worse than an absent one: it is
    an unmeasured value wearing a measurement's clothes.
    """
    store = CandidateStore(db)
    metrics = ValidationMetrics(expected_value=0.0123, cpcv_positive_frac=0.8, dsr=1.4)
    cid = _record(store, metrics=metrics, gates=_GATES)

    (rec,) = [r for r in store.all() if r.id == cid]
    assert rec.metrics.expected_value == pytest.approx(0.0123)
    assert rec.metrics.cpcv_positive_frac == pytest.approx(0.8)


def test_unrecorded_gates_read_as_none_not_as_an_empty_pass(db: Database) -> None:
    """NULL means "never recorded", NOT "no gate failed" -- the whole point of the column.

    This is the pre-m0008 row's shape, reproduced by recording without a verdict. If this ever
    returns ``{}`` the store has started asserting a clean gate sheet for candidates nobody
    scored, which is exactly the reading the column was added to make impossible.
    """
    store = CandidateStore(db)
    cid = _record(store)                      # no gates= -> SQL NULL, the legacy shape

    (rec,) = [r for r in store.all() if r.id == cid]
    assert rec.gates is None
    assert rec.gates != {}
    assert rec.unmeasured == ()


def test_corrupt_gates_json_degrades_to_none_never_to_a_verdict(db: Database) -> None:
    """A column we cannot parse is UNMEASURED, not a pass. Fails closed on garbage."""
    store = CandidateStore(db)
    cid = _record(store, gates=_GATES)
    with db.transaction() as conn:
        conn.execute("UPDATE research_candidates SET gates_json = ? WHERE id = ?",
                     ("{not json", cid))

    (rec,) = [r for r in store.all() if r.id == cid]
    assert rec.gates is None


def test_column_holds_both_halves_separately(db: Database) -> None:
    """``unmeasured`` is stored beside ``gates``, never folded into it as True.

    ``beats_baselines`` read as a passed gate for months while protecting nothing (models.py
    records it). Flattening the two here would rebuild that defect one layer down, in the store,
    where it would be permanent.
    """
    store = CandidateStore(db)
    cid = _record(store, gates=_GATES, unmeasured=_UNMEASURED)

    with db.transaction() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT gates_json FROM research_candidates WHERE id = ?", (cid,)).fetchone()
    blob = json.loads(row[0])
    assert blob["gates"] == _GATES
    assert blob["unmeasured"] == list(_UNMEASURED)
    assert "stationary" not in blob["gates"]


def test_validate_retains_the_cpcv_fraction_it_used_to_discard() -> None:
    """The gate stays a comparison against the SAME float that is now also recorded.

    Guards the refactor: if a future edit re-inlines ``_cpcv_positive_fraction`` into the gate,
    ``cpcv_positive_frac`` silently reverts to its 0.0 default while the gate keeps working, and
    nothing else in the suite would notice.
    """
    rng = np.random.default_rng(7)
    m = rng.normal(0.0004, 0.01, (600, 6))
    sh = np.array([m[:, i].mean() / m[:, i].std() for i in range(m.shape[1])])

    verdict = validate(m[:, 0], hypothesis=_hyp(), periods_per_year=365.0,
                       n_trials=m.shape[1], sharpe_estimates=sh, returns_matrix=m)

    assert 0.0 <= verdict.metrics.cpcv_positive_frac <= 1.0
    # The gate is that fraction against its threshold -- same number, same decision.
    assert verdict.gates["cpcv"] == (verdict.metrics.cpcv_positive_frac >= _CPCV_MIN_POSITIVE)
