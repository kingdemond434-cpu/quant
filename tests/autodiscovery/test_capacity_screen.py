"""The §42 pre-scoring capacity screen and the retirement path through the store's own API.

Proves the three boundary behaviours the screen exists for -- FILLABLE passes through to the
store, UNFILLABLE is banked (full mechanism) and never stored, UNKNOWN (capacity 0.0) passes
through because unmeasured is not unfillable (R0080) -- and that `CandidateStore.retire` marks
without deleting: dedup, trial counts and family priors still see the row, while every
population reader (`all`, `survivors`, `rejects`) stops carrying it.

Thresholds are never restated here: expected requirements come from the capacity policy itself
(`capacity_required`), so a ThresholdBook retune cannot silently turn these into tests of stale
constants.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from libs.autodiscovery.capacity_screen import (
    RESURRECT_CONDITION,
    bank_append,
    banked_hashes,
    banked_ids,
    build_bank_record,
    screen_reason,
)
from libs.autodiscovery.memory import (
    CandidateSeries,
    CandidateStore,
    bar_epoch,
    content_hash,
)
from libs.autodiscovery.models import (
    CandidateStatus,
    Family,
    Hypothesis,
    ValidationMetrics,
)
from libs.autodiscovery.orchestrator import AutoDiscoveryLab
from libs.data.timeframe import Timeframe
from libs.research.capacity_policy import capacity_required
from libs.store.connection import Database
from libs.validation.economic_prior import MechanismType

# Small-book figures on purpose (nothing fund-shaped): the policy is a ratio, so the absolute
# numbers only need to sit on the right side of the requirement the policy itself computes.
_BOOK = 9_600.0
_SLEEVES = 8


def _hyp(subtype: str = "capacity_screen_unit") -> Hypothesis:
    return Hypothesis(
        family=Family.CARRY, subtype=subtype, symbol="UNITUSD",
        params={"lookback": 24.0}, mechanism=MechanismType.STRUCTURAL,
        edge_source="unit-test funding-clock edge", failure_modes=["regime break"],
    )


def _lab(db: Database, bank: Path) -> AutoDiscoveryLab:
    return AutoDiscoveryLab(db, lambda _s: None, bar=Timeframe.D1, capacity_bank=bank)


def _series() -> CandidateSeries:
    """The evidence every scored candidate now carries (m0007) -- required, never optional."""
    return CandidateSeries(net=np.array([0.001, -0.002, 0.003], dtype="float64"),
                           stressed=np.array([0.000, -0.003, 0.002], dtype="float64"),
                           epoch_key=bar_epoch("UNITUSD", np.linspace(1.0, 1.1, 4)))


def _required() -> float:
    """The policy's own equal-weight headroom requirement for this book/sleeve split."""
    return capacity_required(_BOOK, _SLEEVES)


# --------------------------------------------------------------------- the decision function
def test_screen_reason_fillable_unfillable_unknown() -> None:
    req = _required()
    assert screen_reason(req * 4.0, "s", book_usd=_BOOK, n_sleeves=_SLEEVES) is None
    assert screen_reason(req * 0.5, "s", book_usd=_BOOK,
                         n_sleeves=_SLEEVES) == "unfillable-at-scoring"
    # UNKNOWN IS NOT UNFILLABLE: 0.0 means nobody measured (R0080), never "too small".
    assert screen_reason(0.0, "s", book_usd=_BOOK, n_sleeves=_SLEEVES) is None
    assert screen_reason(-1.0, "s", book_usd=_BOOK, n_sleeves=_SLEEVES) is None


# ------------------------------------------------------------------- the factory boundary
def test_fillable_passes_through_to_store(db: Database, tmp_path: Path) -> None:
    bank = tmp_path / "bank.jsonl"
    lab = _lab(db, bank)
    banked = lab._record_scored(
        campaign_id="camp_t", hyp=_hyp(), status=CandidateStatus.REJECTED,
        metrics=ValidationMetrics(capacity_usd=_required() * 4.0), survived=False,
        reason="failed: dsr", book_usd=_BOOK, n_sleeves=_SLEEVES, series=_series())
    assert banked is None
    assert lab.store.total() == 1
    assert not bank.exists()
    # ... and the verdict brought its evidence with it (m0007), rejected or not.
    stored = lab.store.returns_for(lab.store.all()[0].id)
    assert stored is not None and stored.n_obs == 3


def test_unfillable_is_banked_not_stored(db: Database, tmp_path: Path) -> None:
    bank = tmp_path / "bank.jsonl"
    lab = _lab(db, bank)
    hyp = _hyp()
    banked = lab._record_scored(
        campaign_id="camp_t", hyp=hyp, status=CandidateStatus.REJECTED,
        metrics=ValidationMetrics(capacity_usd=_required() * 0.5), survived=False,
        reason="failed: dsr", book_usd=_BOOK, n_sleeves=_SLEEVES, series=_series())
    assert banked == "unfillable-at-scoring"
    assert lab.store.total() == 0                      # never persisted as a scored candidate
    # ... and no series either: a returns row with no candidate row is an orphan, not evidence.
    assert db.execute("SELECT COUNT(*) FROM candidate_returns").fetchone()[0] == 0
    rows = [json.loads(ln) for ln in bank.read_text("utf-8").splitlines()]
    assert len(rows) == 1
    rec = rows[0]
    # The FULL mechanism is preserved (L1.17) with a named way back (L1.16a).
    assert rec["band"] == "UNFILLABLE"
    assert rec["reason"] == "unfillable-at-scoring"
    assert rec["resurrect_condition"] == RESURRECT_CONDITION
    assert rec["content_hash"] == content_hash(hyp)
    assert rec["params"] == {"lookback": 24.0}
    assert rec["mechanism"] == "structural"
    assert rec["hypothesis"] == "unit-test funding-clock edge"
    assert rec["failure_modes"] == ["regime break"]
    assert rec["runway"] < 1.0
    assert rec["retired_ts"] and rec["name"] == "carry/capacity_screen_unit/UNITUSD"
    # ... and the bank now deduplicates the hypothesis for future cycles.
    assert content_hash(hyp) in banked_hashes(bank)


def test_unknown_capacity_passes_through(db: Database, tmp_path: Path) -> None:
    bank = tmp_path / "bank.jsonl"
    lab = _lab(db, bank)
    banked = lab._record_scored(
        campaign_id="camp_t", hyp=_hyp(), status=CandidateStatus.REJECTED,
        metrics=ValidationMetrics(capacity_usd=0.0), survived=False,
        reason="failed: dsr | UNMEASURED: capacity", book_usd=_BOOK, n_sleeves=_SLEEVES,
        series=_series())
    assert banked is None
    assert lab.store.total() == 1
    assert not bank.exists()


# ---------------------------------------------------------------- retirement via the store API
def test_retire_marks_without_deleting(db: Database, tmp_path: Path) -> None:
    store = CandidateStore(db)
    kept, gone = _hyp("kept_subtype"), _hyp("gone_subtype")
    for h in (kept, gone):
        store.record(campaign_id="camp_t", hyp=h, status=CandidateStatus.REJECTED,
                     metrics=ValidationMetrics(capacity_usd=_required() * 0.5),
                     survived=False, rejection_reason="failed: dsr")
    gone_id = next(r.id for r in store.all() if r.subtype == "gone_subtype")

    assert store.retire(gone_id) is True
    assert store.retire(gone_id) is False              # idempotent: second mark changes nothing
    assert store.retire("cand_never_existed") is False

    assert [r.subtype for r in store.all()] == ["kept_subtype"]        # population reader
    assert len(store.all(include_retired=True)) == 2                   # history reader
    assert [r.subtype for r in store.rejects()] == ["kept_subtype"]    # shadow input
    assert store.survivors() == []
    retired = next(r for r in store.all(include_retired=True) if r.id == gone_id)
    assert retired.status is CandidateStatus.ARCHIVED
    assert retired.rejection_reason == "failed: dsr"   # gate history untouched by retirement
    # The trials still happened: dedup, trial counts and deflation priors all keep the row.
    assert store.exists(gone) is True
    assert store.total() == 2
    assert store.family_counts() == {"carry": 2}
    assert store.status_counts() == {"rejected": 1, "archived": 1}


def test_bank_append_and_id_dedup(tmp_path: Path) -> None:
    bank = tmp_path / "bank.jsonl"
    rec = build_bank_record(
        candidate_id="cand_x", family="carry", subtype="s", symbol="UNITUSD",
        params={"k": 1.0}, content_hash="h" * 8, mechanism="structural",
        capacity_usd=_required() * 0.5, book_usd=_BOOK, n_sleeves=_SLEEVES,
        metrics=ValidationMetrics().model_dump(), campaign_id="camp_t",
        status_at_retirement="rejected", survived=False,
        rejection_reason="failed: dsr", reason="unfillable")
    bank_append(rec, bank=bank)
    assert banked_ids(bank) == frozenset({"cand_x"})
    assert banked_hashes(bank) == frozenset({"h" * 8})
    # A malformed line must not blind the readers to the rest (append-only history).
    with bank.open("a", encoding="utf-8") as fh:
        fh.write("not json\n")
    assert banked_ids(bank) == frozenset({"cand_x"})
