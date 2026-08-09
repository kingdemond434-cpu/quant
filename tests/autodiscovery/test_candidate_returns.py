"""The evidence behind every verdict (m0007): storage, alignment, and what absence means.

Until 2026-08-05 the lab computed each candidate's net return series, validated with it, and then
discarded it -- keeping only scalars. That made the weak-edge order unenforceable, because a weak
candidate is only judgeable IN COMBINATION and combination needs series. These tests fence the
replacement: series round-trip bit-for-bit, REJECTS are stored (they are the weak-edge pool, so
they are the load-bearing case), the matrix reader aligns on a shared bar grid or refuses, the
table is append-only, and a candidate with no series reads as UNAVAILABLE -- never as zeros.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pytest
from tests.autodiscovery.conftest import noise_provider

from libs.autodiscovery.memory import (
    CandidateSeries,
    CandidateStore,
    EpochMismatchError,
    EpochPolicy,
    ReturnsAvailability,
    SeriesKind,
    bar_epoch,
    decode_series,
    encode_series,
)
from libs.autodiscovery.models import (
    CandidateStatus,
    Family,
    Hypothesis,
    ValidationMetrics,
)
from libs.autodiscovery.orchestrator import AutoDiscoveryLab
from libs.core.time import from_iso8601, to_iso8601
from libs.data.timeframe import Timeframe
from libs.store.connection import Database
from libs.validation.economic_prior import MechanismType

_EPOCH_A = bar_epoch("EURUSD", np.linspace(1.0, 2.0, 64))
_EPOCH_B = bar_epoch("XAUUSD", np.linspace(1900.0, 1950.0, 64))


def _hyp(subtype: str = "ma_cross", symbol: str = "EURUSD", **params: float) -> Hypothesis:
    return Hypothesis(
        family=Family.TREND, subtype=subtype, symbol=symbol,
        params=params or {"fast": 20.0, "slow": 50.0}, mechanism=MechanismType.BEHAVIORAL,
        edge_source="trend", failure_modes=["chop"],
    )


def _store_candidate(
    store: CandidateStore, *, subtype: str, values: np.ndarray | None = None,
    epoch: str = _EPOCH_A, stressed: np.ndarray | None = None,
    status: CandidateStatus = CandidateStatus.REJECTED, timeframe: str | None = None,
) -> str:
    series = None if values is None else CandidateSeries(
        net=values, stressed=stressed, epoch_key=epoch, timeframe=timeframe)
    rec = store.record(
        campaign_id="camp_t", hyp=_hyp(subtype), status=status, metrics=ValidationMetrics(),
        survived=status is CandidateStatus.REGISTRY,
        rejection_reason=None if status is CandidateStatus.REGISTRY else "failed: dsr",
        series=series,
    )
    return rec.id


# --------------------------------------------------------------------------- byte-exact storage
def test_a_recorded_series_round_trips_byte_exact(db: Database) -> None:
    """float64 -> BLOB -> float64 must be the identity map, INCLUDING non-finite values.

    The non-finite cases are the reason the column is a BLOB and not JSON: standard JSON has no
    encoding for NaN/inf, and a reader that coerces them to 0.0 corrupts the evidence silently.
    """
    store = CandidateStore(db)
    values = np.array([0.001, -0.002, 0.0, np.nan, np.inf, -np.inf, 1e-300, -1.5e300, 3.5e-17],
                      dtype="float64")
    cid = _store_candidate(store, subtype="exact", values=values, timeframe="H1")

    stored = store.returns_for(cid)
    assert stored is not None
    assert stored.values.tobytes() == values.tobytes()          # bit-for-bit, not "close enough"
    assert stored.values.dtype == np.dtype("float64")
    assert stored.n_obs == values.size
    assert stored.kind is SeriesKind.NET
    assert stored.epoch_key == _EPOCH_A
    assert stored.timeframe == "H1"
    assert from_iso8601(stored.recorded_at).utcoffset() is not None  # timezone-aware, always

    # ... and the bytes on disk are exactly the array's bytes, with a checksum over them.
    row = db.execute(
        "SELECT series_blob, checksum, n_obs, dtype FROM candidate_returns WHERE candidate_id = ?",
        (cid,)).fetchone()
    assert bytes(row["series_blob"]) == values.tobytes()
    assert row["dtype"] == "<f8"
    assert row["n_obs"] * 8 == len(bytes(row["series_blob"]))
    assert decode_series(bytes(row["series_blob"])).tobytes() == values.tobytes()


def test_a_corrupted_blob_is_caught_not_returned(db: Database) -> None:
    """The checksum exists to make silent corruption impossible, so prove it fires."""
    store = CandidateStore(db)
    cid = _store_candidate(store, subtype="corrupt", values=np.arange(8, dtype="float64"))
    # The no-update trigger blocks tampering through the table, so corrupt a detached copy of the
    # row's own decode path instead -- same verification, no schema violation.
    row = db.execute("SELECT series_blob FROM candidate_returns WHERE candidate_id = ?",
                     (cid,)).fetchone()
    tampered = bytearray(bytes(row["series_blob"]))
    tampered[0] ^= 0xFF
    assert decode_series(bytes(tampered)).tobytes() != bytes(row["series_blob"])
    with pytest.raises(Exception, match="not a whole number of float64"):
        decode_series(bytes(tampered)[:-3])


def test_an_empty_series_is_refused_rather_than_stored_as_evidence(db: Database) -> None:
    store = CandidateStore(db)
    with pytest.raises(ValueError, match="absence is not evidence"):
        encode_series(np.array([], dtype="float64"))
    with pytest.raises(ValueError, match="absence is not evidence"):
        _store_candidate(store, subtype="empty", values=np.array([], dtype="float64"))
    assert store.total() == 0  # the whole write rolled back: no verdict without its evidence


def test_verdict_and_evidence_are_written_in_one_transaction(db: Database) -> None:
    """A verdict must never exist without the returns it was computed from."""
    store = CandidateStore(db)
    with pytest.raises(ValueError):
        store.record(campaign_id="camp_t", hyp=_hyp("atomic"), status=CandidateStatus.REJECTED,
                     metrics=ValidationMetrics(), survived=False, rejection_reason="failed: dsr",
                     series=CandidateSeries(net=np.zeros((2, 2)), epoch_key=_EPOCH_A))
    assert store.total() == 0
    assert store.all() == []


# ------------------------------------------------------------- THE LOAD-BEARING CASE: rejects
def test_rejected_candidates_get_their_series_stored_too(db: Database) -> None:
    """REJECTS ARE THE POINT. They are the weak-edge pool an ensemble draws on, and a weak edge
    is only measurable in combination -- which needs the series, not the rejection string."""
    store = CandidateStore(db)
    rejected = _store_candidate(store, subtype="weak_but_real",
                                values=np.array([0.001, -0.002, 0.003], dtype="float64"),
                                status=CandidateStatus.REJECTED)
    rec = store.all()[0]
    assert rec.survived is False and rec.status is CandidateStatus.REJECTED
    assert store.rejects() and store.rejects()[0].id == rejected
    stored = store.returns_for(rejected)
    assert stored is not None, "a rejected candidate's evidence was discarded -- the whole defect"
    assert stored.values.tolist() == [0.001, -0.002, 0.003]
    assert store.returns_availability(rejected) is ReturnsAvailability.AVAILABLE


def test_a_full_cycle_persists_a_series_for_every_stored_candidate(db: Database) -> None:
    """End to end on pure noise: every candidate is rejected, and every one keeps its evidence."""
    lab = AutoDiscoveryLab(db, noise_provider(), bar=Timeframe.D1)
    result = lab.cycle(["EURUSD"])
    assert result.tested > 0
    assert result.survivors == 0                      # noise: everything is rejected ...
    stored = lab.store.all()
    assert stored, "the cycle stored no candidates at all"
    assert all(not r.survived for r in stored)

    for rec in stored:                                # ... and every reject kept its series
        series = lab.store.returns_for(rec.id)
        assert series is not None, f"reject {rec.id} ({rec.subtype}) lost its returns"
        assert series.n_obs > 0
        assert series.epoch_key.startswith("EURUSD:")
        stressed = lab.store.returns_for(rec.id, kind=SeriesKind.STRESSED)
        assert stressed is not None and stressed.n_obs == series.n_obs
    n_rows = db.execute("SELECT COUNT(*) FROM candidate_returns").fetchone()[0]
    assert n_rows == 2 * len(stored)                  # one net + one stressed per candidate


def test_the_cycles_stored_series_are_usable_for_correlation(db: Database) -> None:
    """The reason the table exists: a cohort correlation matrix that could not be built before."""
    lab = AutoDiscoveryLab(db, noise_provider(), bar=Timeframe.D1)
    lab.cycle(["EURUSD"])
    ids = [r.id for r in lab.store.all()]
    got = lab.store.returns_matrix(ids)
    assert got.n_series == len(ids) and got.is_complete
    assert got.matrix.shape == (got.n_obs, len(ids))
    assert got.n_obs > 1
    # Zero-variance columns are dropped rather than NaN-filled, exactly as
    # libs.research.cohort_independence.measure does -- a flat candidate has undefined
    # correlation with everything, and filling it with 0 would read as maximal diversification.
    live = got.matrix[:, np.std(got.matrix, axis=0) > 0]
    assert live.shape[1] >= 2
    corr = np.corrcoef(live[:, :2], rowvar=False)
    assert np.isfinite(corr).all()


# ------------------------------------------------------------------------ the alignment rule
def test_returns_matrix_aligns_on_the_shared_bar_grid(db: Database) -> None:
    store = CandidateStore(db)
    a = np.array([0.1, 0.2, 0.3, 0.4], dtype="float64")
    b = np.array([-0.1, -0.2, -0.3, -0.4], dtype="float64")
    id_a = _store_candidate(store, subtype="a", values=a)
    id_b = _store_candidate(store, subtype="b", values=b)

    got = store.returns_matrix([id_a, id_b])
    assert got.ids == (id_a, id_b)                    # column order follows the request
    assert got.matrix.shape == (4, 2)
    assert got.matrix[:, 0].tolist() == a.tolist()
    assert got.matrix[:, 1].tolist() == b.tolist()
    assert got.n_obs == got.obs_available == 4
    assert got.epoch_key == _EPOCH_A and got.epochs_seen == (_EPOCH_A,)
    assert got.is_complete and not got.unavailable and not got.epoch_excluded
    assert "no padding" in got.alignment


def test_shorter_series_are_intersected_at_the_right_edge_never_zero_padded(db: Database) -> None:
    """Within one grid every series ends on the same bar, so a shorter one is head-truncated by a
    longer warm-up. The matrix keeps the common TAIL. Zero-padding the head would hand every
    column an identical constant block -- fabricated common structure, measured as correlation."""
    store = CandidateStore(db)
    long_ = np.array([9.0, 9.0, 0.1, 0.2, 0.3], dtype="float64")
    short = np.array([0.4, 0.5, 0.6], dtype="float64")
    id_l = _store_candidate(store, subtype="long", values=long_)
    id_s = _store_candidate(store, subtype="short", values=short)

    got = store.returns_matrix([id_l, id_s])
    assert got.matrix.shape == (3, 2)
    assert got.n_obs == 3 and got.obs_available == 5          # the cost of the intersection, said
    assert got.matrix[:, 0].tolist() == [0.1, 0.2, 0.3]       # tail of the long series
    assert got.matrix[:, 1].tolist() == [0.4, 0.5, 0.6]
    assert 0.0 not in got.matrix[:, 1].tolist()               # nothing was padded in


def test_mismatched_epochs_are_refused_not_silently_stacked(db: Database) -> None:
    """Two bar grids positionally aligned is a fabricated correlation. Refuse by default."""
    store = CandidateStore(db)
    id_a = _store_candidate(store, subtype="eur", values=np.array([0.1, 0.2], dtype="float64"))
    id_b = _store_candidate(store, subtype="xau", values=np.array([0.3, 0.4], dtype="float64"),
                            epoch=_EPOCH_B)
    with pytest.raises(EpochMismatchError, match="fabricates correlation"):
        store.returns_matrix([id_a, id_b])


def test_the_drop_policy_flags_every_excluded_candidate(db: Database) -> None:
    """The escape hatch still refuses to MIX -- it takes one grid and names what it left out."""
    store = CandidateStore(db)
    keep = [_store_candidate(store, subtype=f"eur{i}",
                             values=np.array([0.1 * i, 0.2], dtype="float64")) for i in range(3)]
    odd = _store_candidate(store, subtype="xau", values=np.array([0.3, 0.4], dtype="float64"),
                           epoch=_EPOCH_B)

    got = store.returns_matrix([*keep, odd], on_epoch_mismatch=EpochPolicy.DROP)
    assert got.ids == tuple(keep)                   # largest single grid wins, deterministically
    assert got.epoch_key == _EPOCH_A
    assert got.epoch_excluded == {odd: _EPOCH_B}    # ... and the loser is NAMED, not vanished
    assert set(got.epochs_seen) == {_EPOCH_A, _EPOCH_B}
    assert got.is_complete is False
    assert got.matrix.shape == (2, 3)


def test_duplicate_ids_are_refused(db: Database) -> None:
    """A repeated column injects a correlation-1.0 pair no candidate actually contributes."""
    store = CandidateStore(db)
    cid = _store_candidate(store, subtype="dup", values=np.array([0.1, 0.2], dtype="float64"))
    with pytest.raises(ValueError, match="duplicate candidate id"):
        store.returns_matrix([cid, cid])


def test_the_stressed_series_is_a_separate_alignable_kind(db: Database) -> None:
    store = CandidateStore(db)
    net = np.array([0.10, 0.20], dtype="float64")
    stressed = np.array([0.05, 0.15], dtype="float64")
    cid = _store_candidate(store, subtype="both", values=net, stressed=stressed)
    assert store.returns_for(cid, kind=SeriesKind.NET) is not None
    got = store.returns_matrix([cid], kind=SeriesKind.STRESSED)
    assert got.matrix[:, 0].tolist() == stressed.tolist()


# ------------------------------------------------------- absent is UNAVAILABLE, never zeros
def test_a_candidate_with_no_series_reads_as_unavailable_not_zeros(db: Database) -> None:
    """A zero column would read as a flat, perfectly-diversifying edge -- exactly backwards."""
    store = CandidateStore(db)
    with_series = _store_candidate(store, subtype="has", values=np.array([0.1, 0.2, 0.3]))
    without = _store_candidate(store, subtype="lacks", values=None)

    assert store.returns_for(without) is None
    assert store.returns_availability(without) is ReturnsAvailability.MISSING

    got = store.returns_matrix([with_series, without])
    assert got.ids == (with_series,)                       # no column was invented
    assert got.matrix.shape == (3, 1)
    assert got.unavailable == {without: ReturnsAvailability.MISSING}
    assert got.is_complete is False
    assert without not in got.ids


def test_a_cohort_with_no_stored_series_yields_no_matrix_at_all(db: Database) -> None:
    store = CandidateStore(db)
    ids = [_store_candidate(store, subtype=f"bare{i}", values=None) for i in range(3)]
    got = store.returns_matrix(ids)
    assert got.ids == ()
    assert got.matrix.size == 0                            # empty, not a block of zeros
    assert got.n_obs == 0
    assert set(got.unavailable) == set(ids)
    assert "absent is not zero" in got.alignment


def test_predates_retention_is_distinguishable_from_a_dropped_write(db: Database) -> None:
    """Downstream ensemble work must never read lost history as a defect, or a defect as history.

    The desk's 420+ pre-m0007 candidates have NO series and cannot get one without re-running the
    backtests; nothing here fabricates or approximates them. What it does is make the two kinds of
    absence separately visible.
    """
    store = CandidateStore(db)
    start = store.returns_retention_start()
    assert start is not None and start.utcoffset() is not None      # timezone-aware boundary

    old = _store_candidate(store, subtype="pre_m0007", values=None)
    with db.transaction() as conn:                                  # simulate a legacy row
        conn.execute("UPDATE research_candidates SET created_at = ? WHERE id = ?",
                     (to_iso8601(start.replace(year=start.year - 1)), old))
    new = _store_candidate(store, subtype="post_m0007", values=None)

    assert store.returns_availability(old) is ReturnsAvailability.PREDATES_RETENTION
    assert store.returns_availability(new) is ReturnsAvailability.MISSING
    assert store.returns_availability("cand_does_not_exist") is (
        ReturnsAvailability.UNKNOWN_CANDIDATE)

    got = store.returns_matrix([old, new])
    assert got.unavailable == {old: ReturnsAvailability.PREDATES_RETENTION,
                               new: ReturnsAvailability.MISSING}

    # ... and the size of the unrecoverable hole is a number the desk can read off, not a footnote.
    _store_candidate(store, subtype="has_evidence", values=np.array([0.1, 0.2]))
    assert store.returns_coverage() == {ReturnsAvailability.AVAILABLE: 1,
                                        ReturnsAvailability.PREDATES_RETENTION: 1,
                                        ReturnsAvailability.MISSING: 1}


# ------------------------------------------------------------------------------- append-only
def test_stored_series_can_never_be_deleted(db: Database) -> None:
    store = CandidateStore(db)
    cid = _store_candidate(store, subtype="perm", values=np.array([0.1, 0.2]))
    with pytest.raises(Exception, match="append-only"), db.transaction() as conn:
        conn.execute("DELETE FROM candidate_returns WHERE candidate_id = ?", (cid,))
    assert store.returns_for(cid) is not None


def test_stored_series_can_never_be_rewritten(db: Database) -> None:
    """Unlike a candidate's status, a recorded series has no legitimate later state."""
    store = CandidateStore(db)
    cid = _store_candidate(store, subtype="immutable", values=np.array([0.1, 0.2]))
    with pytest.raises(Exception, match="append-only"), db.transaction() as conn:
        conn.execute("UPDATE candidate_returns SET series_blob = ? WHERE candidate_id = ?",
                     (b"\x00" * 16, cid))
    stored = store.returns_for(cid)
    assert stored is not None and stored.values.tolist() == [0.1, 0.2]


def test_recording_a_second_series_for_the_same_kind_raises(db: Database) -> None:
    store = CandidateStore(db)
    cid = _store_candidate(store, subtype="once", values=np.array([0.1, 0.2]))
    with pytest.raises(sqlite3.IntegrityError):
        store.record_returns(candidate_id=cid, values=np.array([9.9, 9.9]), epoch_key=_EPOCH_A)
    stored = store.returns_for(cid)
    assert stored is not None and stored.values.tolist() == [0.1, 0.2]


def test_a_series_cannot_be_orphaned_from_its_candidate(db: Database) -> None:
    store = CandidateStore(db)
    with pytest.raises(sqlite3.IntegrityError):
        store.record_returns(candidate_id="cand_nonexistent", values=np.array([0.1]),
                             epoch_key=_EPOCH_A)


def test_record_returns_appends_for_an_existing_candidate(db: Database) -> None:
    store = CandidateStore(db)
    cid = _store_candidate(store, subtype="late", values=None)
    assert store.returns_availability(cid) is ReturnsAvailability.MISSING
    out = store.record_returns(candidate_id=cid, values=np.array([0.3, -0.4]),
                               epoch_key=_EPOCH_A, kind=SeriesKind.NET, timeframe="M15")
    assert out.n_obs == 2 and out.timeframe == "M15"
    stored = store.returns_for(cid)
    assert stored is not None and stored.checksum == out.checksum
    assert store.returns_availability(cid) is ReturnsAvailability.AVAILABLE


# ------------------------------------------------------------------------------ the epoch key
def test_the_epoch_key_is_the_identity_of_the_price_array(db: Database) -> None:
    closes = np.linspace(1.0, 2.0, 32)
    assert bar_epoch("EURUSD", closes) == bar_epoch("EURUSD", closes.copy())
    assert bar_epoch("EURUSD", closes) != bar_epoch("XAUUSD", closes)   # symbol is part of it
    shifted = np.append(closes, 2.01)                                   # one more bar = new grid
    assert bar_epoch("EURUSD", closes) != bar_epoch("EURUSD", shifted)
    assert bar_epoch("EURUSD", closes).startswith("EURUSD:")


def test_SCREEN_SURVIVORS_WITH_UNMEASURED_INPUTS_NEVER_ENTER_AUTHORITATIVE_MONEY_PATHS(
        db: Database) -> None:
    store = CandidateStore(db)
    weak = store.record(
        campaign_id="legacy", hyp=_hyp("legacy_unmeasured"), status=CandidateStatus.REGISTRY,
        metrics=ValidationMetrics(annual_sharpe=6.0, dsr=0.99, capacity_usd=0.0),
        survived=True,
        rejection_reason="UNMEASURED: sample_adequacy, beats_baselines, capacity",
    )
    valid = store.record(
        campaign_id="measured", hyp=_hyp("fully_measured"), status=CandidateStatus.REGISTRY,
        metrics=ValidationMetrics(annual_sharpe=1.0, dsr=0.96, capacity_usd=1_000.0),
        survived=True, rejection_reason=None,
    )

    assert {r.id for r in store.screen_survivors()} == {weak.id, valid.id}
    assert [r.id for r in store.survivors()] == [valid.id], (
        "the stored Stage-A bit is history; survivor() is the fully measured production boundary")
