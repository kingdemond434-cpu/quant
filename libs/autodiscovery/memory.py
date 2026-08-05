"""Candidate store + checkpoint — durable research memory and resumable lab state.

Persists every tested candidate (family/subtype/params/metrics/rejection/status) to the
append-only ``research_candidates`` table, deduplicates by content hash (no repeated testing of a
known idea), and reads/writes the ``lab_checkpoint`` so the lab resumes after any interruption.

THE VERDICT WAS KEPT, THE EVIDENCE WAS THROWN AWAY (fixed 2026-08-05, m0007). Until migration 7
this store wrote SCALARS ONLY. Every candidate the desk ever tested — 420+ price hypotheses, 129
mechanisms, 44 pooled — had its net return series computed inside the orchestrator, carried through
validation in memory, and then dropped on the floor. That made the standing weak-edge order
unenforceable, because a weak candidate's entire value is what it contributes IN COMBINATION (N
mutually-uncorrelated edges of Sharpe s give s*sqrt(N)) and NOTHING about combination — pairwise
correlation, orthogonality, any ensemble weighting — can be recovered from a Sharpe and a
rejection string. ``record_returns`` / :meth:`CandidateStore.record` (``series=``) now persist the
series for survivors AND rejects; the rejects especially, since they are the weak-edge pool.

NO BACKFILL IS POSSIBLE, AND NONE IS FAKED. Series for candidates recorded before m0007 applied are
GONE — they were never written anywhere, and the only way to obtain them is to re-run those
backtests against the same data. This module therefore does not synthesise, approximate or
zero-fill them, and it never lets absence read as a series of zeros: absent is a distinct,
first-class state. :meth:`CandidateStore.returns_availability` separates
``PREDATES_RETENTION`` (recorded before the m0007 retention boundary — expected, unrecoverable)
from ``MISSING`` (recorded after it and still absent — a real defect worth chasing) from
``UNKNOWN_CANDIDATE`` (no such candidate id at all), and :meth:`CandidateStore.returns_matrix`
reports every excluded id with its reason instead of quietly narrowing the matrix.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

import numpy as np

from libs.autodiscovery.errors import AutoDiscoveryError
from libs.autodiscovery.models import (
    CandidateRecord,
    CandidateStatus,
    Hypothesis,
    ValidationMetrics,
)
from libs.core.ids import generate_id
from libs.core.time import from_iso8601, to_iso8601, utcnow
from libs.store.connection import Database
from libs.store.hashchain import canonical_json, sha256_hex

_COLS = (
    "id, created_at, updated_at, campaign_id, family, subtype, symbol, params_json, content_hash, "
    "status, mechanism, annual_sharpe, dsr, pbo, reality_p, oos_sharpe, capacity_usd, fragility, "
    "survived, rejection_reason"
)

_RETURNS_COLS = (
    "candidate_id, kind, epoch_key, n_obs, dtype, timeframe, checksum, series_blob, recorded_at"
)

#: On-disk encoding of a stored return series: little-endian IEEE-754 float64, C-contiguous, no
#: header. BLOB rather than JSON because float64 -> bytes -> float64 is the identity map (JSON
#: round-trips through a decimal rendering), because NaN/inf have no standard JSON encoding and a
#: silent coercion to 0.0 would corrupt the evidence, and because ``length(blob) = n_obs * 8`` is a
#: CHECK the database enforces on every write. Full argument: migrations/m0007_candidate_returns.
_DTYPE = "<f8"
_ITEMSIZE = 8

#: The m0007 row in ``schema_migrations``. Its ``applied_at`` is the RETENTION BOUNDARY: candidates
#: created before it cannot have a stored series and never will (see the module docstring).
_RETENTION_VERSION = 7
_RETENTION_NAME = "candidate_returns"


class SeriesKind(StrEnum):
    """Which series a stored row holds. NET is the one every downstream reader means."""

    NET = "net"          # net of the calibrated per-turnover cost — the candidate's own returns
    STRESSED = "stressed"  # same positions, cost multiplied to the conservative live estimate


class ReturnsAvailability(StrEnum):
    """Why a candidate's series is or is not readable. ABSENT IS NEVER ZERO."""

    AVAILABLE = "available"
    #: Candidate predates the m0007 retention boundary. Its series was never persisted by anyone
    #: and cannot be recovered without re-running the backtest. Expected, not a defect.
    PREDATES_RETENTION = "predates_retention"
    #: Candidate is newer than the boundary and STILL has no series — a real gap in the writer.
    MISSING = "missing"
    #: No candidate row with that id at all (typo, wrong database, banked-not-stored candidate).
    UNKNOWN_CANDIDATE = "unknown_candidate"


class EpochPolicy(StrEnum):
    """What :meth:`CandidateStore.returns_matrix` does when the requested ids span bar grids."""

    RAISE = "raise"  # default: refuse to build a matrix that would be a lie
    DROP = "drop"    # keep the largest single-epoch group, and report every id dropped


class EpochMismatchError(AutoDiscoveryError):
    """Requested candidates do not share one bar grid, so they cannot be aligned."""


class SeriesCorruptionError(AutoDiscoveryError):
    """A stored series does not match its own checksum or declared length."""


@dataclass(frozen=True)
class CandidateSeries:
    """The evidence to persist alongside a candidate's scalar verdict, in ONE transaction.

    ``epoch_key`` names the bar grid ``net``/``stressed`` were computed on (see :func:`bar_epoch`);
    ``timeframe`` is the bar interval when the caller knows it and ``None`` when it does not.

    THE LAB NOW KNOWS IT (R0086, 2026-08-05). This used to read "the lab's ``MarketSeries`` carries
    no interval field, so it records NULL rather than a guess" — true at the time, and the same
    hole that let ``validate()`` annualise every series with an hourly constant.
    ``AutoDiscoveryLab`` takes a required ``bar`` and passes it here, so a NULL timeframe on a
    lab-written row now means the row PREDATES that fix and its ``annual_sharpe`` is inflated
    (4.135x on daily bars). See the module docstring of ``libs/autodiscovery/validation.py``.
    """

    net: np.ndarray
    epoch_key: str
    stressed: np.ndarray | None = None
    timeframe: str | None = None


@dataclass(frozen=True)
class StoredSeries:
    """One recorded series, read back and checksum-verified."""

    candidate_id: str
    kind: SeriesKind
    values: np.ndarray
    epoch_key: str
    n_obs: int
    timeframe: str | None
    checksum: str
    recorded_at: str


@dataclass(frozen=True)
class ReturnsMatrix:
    """An aligned (observations x candidates) matrix plus a full account of what is NOT in it.

    ``matrix[:, i]`` is ``ids[i]``. Every requested id is in exactly one of ``ids``,
    ``unavailable`` or ``epoch_excluded``, so a caller can always tell a narrow matrix from a
    complete one — silently dropping a candidate would read downstream as "it contributed nothing".
    """

    matrix: np.ndarray
    ids: tuple[str, ...]
    requested: tuple[str, ...]
    epoch_key: str | None
    n_obs: int
    obs_available: int
    unavailable: dict[str, ReturnsAvailability]
    epoch_excluded: dict[str, str]
    epochs_seen: tuple[str, ...]
    alignment: str

    @property
    def n_series(self) -> int:
        return len(self.ids)

    @property
    def is_complete(self) -> bool:
        """True iff every requested candidate contributed a column."""
        return len(self.ids) == len(self.requested)


def bar_epoch(symbol: str, closes: np.ndarray) -> str:
    """Identity of the BAR GRID a return series lives on. Equality here licenses alignment.

    Keyed on the symbol plus a digest of the exact float64 close array the backtest ran on, so two
    series share an epoch only if they were produced from bit-identical price data. That is
    deliberately strict: it means candidates from two campaigns that pulled data a bar apart do NOT
    share an epoch, and :meth:`CandidateStore.returns_matrix` will refuse to stack them. Refusing is
    correct — index i of one series and index i of the other would be different bars, and lining
    them up anyway shifts one series against the other by an unknown lag, which fabricates
    correlation (or destroys real correlation) out of pure bookkeeping. The honest fix is per-bar
    timestamps in the data provider; ``MarketSeries`` has none today, so identity of the source
    array is the strongest true statement available.
    """
    digest = hashlib.sha256(np.ascontiguousarray(closes, dtype=_DTYPE).tobytes()).hexdigest()
    return f"{symbol}:{digest}"


def encode_series(values: np.ndarray) -> bytes:
    """Encode a 1-D return series to its on-disk bytes (little-endian float64, C-contiguous)."""
    arr = np.ascontiguousarray(values, dtype=_DTYPE)
    if arr.ndim != 1:
        raise ValueError(f"a return series must be 1-D, got shape {arr.shape}")
    if arr.size == 0:
        raise ValueError("refusing to store an empty return series -- absence is not evidence")
    return arr.tobytes()


def decode_series(blob: bytes) -> np.ndarray:
    """Decode on-disk bytes back to a writable native float64 array (byte-exact round trip)."""
    if len(blob) % _ITEMSIZE != 0:
        raise SeriesCorruptionError(
            f"series blob of {len(blob)} bytes is not a whole number of float64 values"
        )
    return np.frombuffer(blob, dtype=_DTYPE).astype("float64", copy=True)


def content_hash(hyp: Hypothesis) -> str:
    """Stable identity of a hypothesis (family+subtype+symbol+params) for dedup."""
    payload = [hyp.family.value, hyp.subtype, hyp.symbol, sorted(hyp.params.items())]
    return sha256_hex(canonical_json(payload))


def _row_to_record(row: sqlite3.Row) -> CandidateRecord:
    return CandidateRecord(
        id=row["id"], created_at=row["created_at"], updated_at=row["updated_at"],
        campaign_id=row["campaign_id"], family=row["family"], subtype=row["subtype"],
        symbol=row["symbol"], params=json.loads(row["params_json"]),
        content_hash=row["content_hash"], status=CandidateStatus(row["status"]),
        mechanism=row["mechanism"] or "",
        metrics=ValidationMetrics(
            annual_sharpe=row["annual_sharpe"] or 0.0, oos_sharpe=row["oos_sharpe"] or 0.0,
            dsr=row["dsr"] or 0.0, pbo=row["pbo"] or 0.0, reality_p=row["reality_p"] or 1.0,
            capacity_usd=row["capacity_usd"] or 0.0, fragility=row["fragility"] or 0.0,
        ),
        survived=bool(row["survived"]), rejection_reason=row["rejection_reason"],
    )


def _row_to_series(row: sqlite3.Row) -> StoredSeries:
    """Decode one ``candidate_returns`` row, verifying it against its own checksum and length."""
    blob = bytes(row["series_blob"])
    n_obs = int(row["n_obs"])
    dtype = str(row["dtype"])
    if dtype != _DTYPE:
        raise SeriesCorruptionError(
            f"stored series declares dtype {dtype!r}, this reader only decodes {_DTYPE!r}"
        )
    if len(blob) != n_obs * _ITEMSIZE:
        raise SeriesCorruptionError(
            f"stored series declares {n_obs} observations but holds {len(blob)} bytes"
        )
    checksum = str(row["checksum"])
    if hashlib.sha256(blob).hexdigest() != checksum:
        raise SeriesCorruptionError(
            f"stored series for {row['candidate_id']} does not match its checksum {checksum}"
        )
    timeframe = row["timeframe"]
    return StoredSeries(
        candidate_id=str(row["candidate_id"]), kind=SeriesKind(str(row["kind"])),
        values=decode_series(blob), epoch_key=str(row["epoch_key"]), n_obs=n_obs,
        timeframe=None if timeframe is None else str(timeframe),
        checksum=checksum, recorded_at=str(row["recorded_at"]),
    )


def _insert_series(
    conn: sqlite3.Connection, *, candidate_id: str, kind: SeriesKind, values: np.ndarray,
    epoch_key: str, timeframe: str | None, now: str,
) -> str:
    """INSERT one series row on an open transaction. Returns its checksum.

    Takes the connection rather than opening its own transaction so the evidence can be written
    atomically with the verdict it belongs to (``Database.transaction`` is not reentrant).
    """
    if not epoch_key:
        raise ValueError("epoch_key is required: a series with no bar grid cannot be aligned")
    blob = encode_series(values)
    checksum = hashlib.sha256(blob).hexdigest()
    conn.execute(
        f"INSERT INTO candidate_returns ({_RETURNS_COLS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (candidate_id, kind.value, epoch_key, len(blob) // _ITEMSIZE, _DTYPE, timeframe,
         checksum, blob, now),
    )
    return checksum


class CandidateStore:
    """Reader/writer for the durable candidate ledger (append-only) and the lab checkpoint."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def exists(self, hyp: Hypothesis) -> bool:
        chash = content_hash(hyp)
        row = self.db.execute(
            "SELECT 1 FROM research_candidates WHERE content_hash = ?", (chash,)
        ).fetchone()
        return row is not None

    def record(
        self, *, campaign_id: str, hyp: Hypothesis, status: CandidateStatus,
        metrics: ValidationMetrics, survived: bool, rejection_reason: str | None,
        series: CandidateSeries | None = None,
    ) -> CandidateRecord:
        """Persist one scored candidate — verdict AND evidence, atomically.

        ``series`` is written in the SAME transaction as the scalar row, so the two cannot diverge:
        there is no window in which a verdict exists without the returns it was computed from. It
        stays optional only because callers that legitimately have no series (fixtures, backfills
        of scalar-only history) must not be forced to invent one — see the module docstring on why
        an invented series is worse than an absent one.
        """
        now = to_iso8601(utcnow())
        rec = CandidateRecord(
            id=generate_id("cand"), created_at=now, updated_at=now, campaign_id=campaign_id,
            family=hyp.family.value, subtype=hyp.subtype, symbol=hyp.symbol,
            params=dict(hyp.params),
            content_hash=content_hash(hyp), status=status, mechanism=hyp.mechanism.value,
            metrics=metrics, survived=survived, rejection_reason=rejection_reason,
        )
        with self.db.transaction() as conn:
            conn.execute(
                f"INSERT INTO research_candidates ({_COLS}) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    rec.id, now, now, campaign_id, rec.family, rec.subtype, rec.symbol,
                    json.dumps(rec.params), rec.content_hash, status.value, rec.mechanism,
                    metrics.annual_sharpe, metrics.dsr, metrics.pbo, metrics.reality_p,
                    metrics.oos_sharpe, metrics.capacity_usd, metrics.fragility,
                    int(survived), rejection_reason,
                ),
            )
            if series is not None:
                _insert_series(conn, candidate_id=rec.id, kind=SeriesKind.NET,
                               values=series.net, epoch_key=series.epoch_key,
                               timeframe=series.timeframe, now=now)
                if series.stressed is not None:
                    _insert_series(conn, candidate_id=rec.id, kind=SeriesKind.STRESSED,
                                   values=series.stressed, epoch_key=series.epoch_key,
                                   timeframe=series.timeframe, now=now)
        return rec

    # ------------------------------------------------------------------ return series (m0007)
    def record_returns(
        self, *, candidate_id: str, values: np.ndarray, epoch_key: str,
        kind: SeriesKind = SeriesKind.NET, timeframe: str | None = None,
    ) -> StoredSeries:
        """Append one candidate's return series. APPEND-ONLY: re-recording is an error, not an
        overwrite (``UNIQUE(candidate_id, kind)`` plus a no-update trigger enforce it in the
        schema, so a second write raises rather than quietly replacing the evidence).

        Prefer passing ``series=`` to :meth:`record`, which writes verdict and evidence in one
        transaction. This standalone writer exists for the cases where the candidate row already
        exists (re-scoring an old candidate against fresh data, tests).
        """
        now = to_iso8601(utcnow())
        with self.db.transaction() as conn:
            checksum = _insert_series(conn, candidate_id=candidate_id, kind=kind, values=values,
                                      epoch_key=epoch_key, timeframe=timeframe, now=now)
        arr = decode_series(encode_series(values))  # exactly what a later read will hand back
        return StoredSeries(
            candidate_id=candidate_id, kind=kind, values=arr, epoch_key=epoch_key,
            n_obs=int(arr.size), timeframe=timeframe, checksum=checksum, recorded_at=now,
        )

    def returns_for(
        self, candidate_id: str, *, kind: SeriesKind = SeriesKind.NET
    ) -> StoredSeries | None:
        """One candidate's stored series, checksum-verified, or ``None`` if there is none.

        ``None`` means NOT AVAILABLE and nothing else -- never an implied series of zeros. Call
        :meth:`returns_availability` to learn WHY it is absent (predates retention / missing /
        unknown candidate), which is a different fact with different consequences.
        """
        row = self.db.execute(
            f"SELECT {_RETURNS_COLS} FROM candidate_returns WHERE candidate_id = ? AND kind = ?",
            (candidate_id, kind.value),
        ).fetchone()
        return None if row is None else _row_to_series(row)

    def returns_retention_start(self) -> datetime | None:
        """When series retention began (m0007's ``applied_at``), or ``None`` if unrecorded.

        Everything the desk tested before this instant has NO series and never will: it was
        computed, used, and discarded. This is the boundary that lets a reader distinguish
        "the evidence predates retention" from "the writer dropped it".
        """
        row = self.db.execute(
            "SELECT applied_at FROM schema_migrations WHERE version = ? AND name = ?",
            (_RETENTION_VERSION, _RETENTION_NAME),
        ).fetchone()
        return None if row is None else from_iso8601(str(row["applied_at"]))

    def returns_availability(
        self, candidate_id: str, *, kind: SeriesKind = SeriesKind.NET
    ) -> ReturnsAvailability:
        """Whether a candidate's series is readable, and if not, which kind of absent it is."""
        row = self.db.execute(
            "SELECT 1 FROM candidate_returns WHERE candidate_id = ? AND kind = ?",
            (candidate_id, kind.value),
        ).fetchone()
        if row is not None:
            return ReturnsAvailability.AVAILABLE
        cand = self.db.execute(
            "SELECT created_at FROM research_candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
        if cand is None:
            return ReturnsAvailability.UNKNOWN_CANDIDATE
        start = self.returns_retention_start()
        if start is not None and from_iso8601(str(cand["created_at"])) < start:
            return ReturnsAvailability.PREDATES_RETENTION
        return ReturnsAvailability.MISSING

    def returns_coverage(
        self, *, kind: SeriesKind = SeriesKind.NET, include_retired: bool = True
    ) -> dict[ReturnsAvailability, int]:
        """How much of the ledger still HAS its evidence — i.e. the size of the pre-m0007 hole.

        Counts the whole candidate population by :class:`ReturnsAvailability` so the loss is a
        number the desk can see rather than a footnote. ``PREDATES_RETENTION`` is the unrecoverable
        backlog (those series were computed and discarded and only re-running them brings them
        back); any non-zero ``MISSING`` is a live writer defect, because everything recorded after
        the boundary should have arrived with its series in the same transaction.
        """
        where = "" if include_retired else \
            f" WHERE c.status != '{CandidateStatus.ARCHIVED.value}'"
        rows = self.db.execute(
            "SELECT c.created_at AS created_at, r.candidate_id AS stored "
            "FROM research_candidates c "
            "LEFT JOIN candidate_returns r ON r.candidate_id = c.id AND r.kind = ?"
            f"{where}",
            (kind.value,),
        ).fetchall()
        start = self.returns_retention_start()
        out = {
            ReturnsAvailability.AVAILABLE: 0,
            ReturnsAvailability.PREDATES_RETENTION: 0,
            ReturnsAvailability.MISSING: 0,
        }
        for row in rows:
            if row["stored"] is not None:
                out[ReturnsAvailability.AVAILABLE] += 1
            elif start is not None and from_iso8601(str(row["created_at"])) < start:
                out[ReturnsAvailability.PREDATES_RETENTION] += 1
            else:
                out[ReturnsAvailability.MISSING] += 1
        return out

    def returns_matrix(
        self, candidate_ids: Sequence[str], *, kind: SeriesKind = SeriesKind.NET,
        on_epoch_mismatch: EpochPolicy = EpochPolicy.RAISE,
    ) -> ReturnsMatrix:
        """Aligned (observations x candidates) matrix for correlation / ensemble work.

        THE ALIGNMENT RULE, in full, because a wrong one silently manufactures the very number the
        caller is trying to measure:

        1. SAME EPOCH OR NOTHING. Two series may share a matrix only if their ``epoch_key`` values
           are equal. An epoch key is symbol + digest of the exact close array the backtest ran on
           (:func:`bar_epoch`), so equality means index i of one series and index i of the other
           are THE SAME BAR. Series from different grids are never lined up by position: doing so
           shifts one against the other by an unknown lag, which invents correlation (or hides it)
           out of arithmetic alone -- the same class of error
           ``libs.research.cohort_independence.demeaning_floor`` documents, where cross-sectional
           demeaning pins mean pairwise correlation at -1/(N-1) with no data involved. Mixed
           epochs RAISE by default; ``EpochPolicy.DROP`` keeps the largest single-epoch group
           (ties broken by the lexicographically smallest key, so the choice is deterministic) and
           names every dropped id in ``epoch_excluded``.
        2. RIGHT-EDGE INTERSECTION, NEVER PADDING. Within one epoch every series ends on the same
           bar -- the backtest core emits one return per bar of the shared close array -- so
           differing lengths can only be head truncation from a longer warm-up. The matrix
           therefore takes the last ``min(n_obs)`` observations of each column: an exact
           intersection of real bars. Nothing is padded, zero-filled, interpolated or forward
           filled. A zero-padded head would be a block of identical constants shared by every
           column, i.e. fabricated common structure exactly where correlation is measured.
           ``n_obs`` vs ``obs_available`` reports what the intersection cost.
        3. ABSENT IS NOT ZERO. A candidate with no stored series contributes NO COLUMN and is
           listed in ``unavailable`` with its :class:`ReturnsAvailability` reason. It is never
           represented as zeros, which would read as a flat, perfectly-uncorrelated edge -- the
           most diversifying thing in the cohort -- which is precisely backwards.
        4. NO DUPLICATE IDS. A repeated id would put a perfectly correlated pair into the matrix;
           it raises ``ValueError`` instead.
        """
        requested = tuple(candidate_ids)
        seen: set[str] = set()
        for cid in requested:
            if cid in seen:
                raise ValueError(
                    f"duplicate candidate id {cid!r}: a repeated column would add a pair with "
                    "correlation 1.0 that no candidate actually contributes"
                )
            seen.add(cid)

        found: list[StoredSeries] = []
        unavailable: dict[str, ReturnsAvailability] = {}
        for cid in requested:
            stored = self.returns_for(cid, kind=kind)
            if stored is None:
                unavailable[cid] = self.returns_availability(cid, kind=kind)
            else:
                found.append(stored)

        epochs = sorted({s.epoch_key for s in found})
        epoch_excluded: dict[str, str] = {}
        if len(epochs) > 1:
            if on_epoch_mismatch is EpochPolicy.RAISE:
                counts = {e: sum(1 for s in found if s.epoch_key == e) for e in epochs}
                raise EpochMismatchError(
                    f"cannot align {len(found)} series across {len(epochs)} bar grids "
                    f"{counts}: positional alignment across grids fabricates correlation. "
                    "Pass on_epoch_mismatch=EpochPolicy.DROP to use the largest grid alone."
                )
            keep = min(epochs, key=lambda e: (-sum(1 for s in found if s.epoch_key == e), e))
            epoch_excluded = {s.candidate_id: s.epoch_key for s in found if s.epoch_key != keep}
            found = [s for s in found if s.epoch_key == keep]

        if not found:
            return ReturnsMatrix(
                matrix=np.empty((0, 0), dtype="float64"), ids=(), requested=requested,
                epoch_key=None, n_obs=0, obs_available=0, unavailable=unavailable,
                epoch_excluded=epoch_excluded, epochs_seen=tuple(epochs),
                alignment="no series available: 0 columns (absent is not zero)",
            )
        n_obs = min(s.n_obs for s in found)
        obs_available = max(s.n_obs for s in found)
        matrix = np.column_stack([s.values[-n_obs:] for s in found])
        epoch_key = found[0].epoch_key
        return ReturnsMatrix(
            matrix=matrix, ids=tuple(s.candidate_id for s in found), requested=requested,
            epoch_key=epoch_key, n_obs=n_obs, obs_available=obs_available,
            unavailable=unavailable, epoch_excluded=epoch_excluded, epochs_seen=tuple(epochs),
            alignment=(
                f"right-edge intersection within epoch {epoch_key}: {len(found)} series x "
                f"{n_obs} obs (longest available {obs_available}); no padding, no interpolation"
            ),
        )

    def all(self, *, include_retired: bool = False) -> list[CandidateRecord]:
        """The candidate population -- by default WITHOUT retired (``archived``) rows.

        RETIRED IS NOT A CANDIDATE (§42, 2026-08-05). A row archived by ``retire`` has left the
        population: it must not be ranked, promoted, shadow-tracked or counted as scored
        inventory, and every reader that means "the candidates" gets exactly that by default.
        Readers that mean "the full historical ledger" (rejection histograms, research-ROI spend
        accounting) pass ``include_retired=True`` -- history is never shrunk, it is filtered.
        """
        where = "" if include_retired else \
            f" WHERE status != '{CandidateStatus.ARCHIVED.value}'"
        rows = self.db.execute(
            f"SELECT {_COLS} FROM research_candidates{where} ORDER BY seq"
        ).fetchall()
        return [_row_to_record(r) for r in rows]

    def survivors(self) -> list[CandidateRecord]:
        rows = self.db.execute(
            f"SELECT {_COLS} FROM research_candidates WHERE survived = 1 "
            f"AND status != '{CandidateStatus.ARCHIVED.value}' ORDER BY seq"
        ).fetchall()
        return [_row_to_record(r) for r in rows]

    def rejects(self) -> list[CandidateRecord]:
        """The rejected candidates -- the input to the rejection-shadow audit (gate-calibration).

        A gate that has drifted over-strict silently leaks these; shadow-tracking a sample forward
        is pure recovery (no new data). This is the reject ledger MAX_SURVIVORS Part 1.2 calls for
        -- it already exists as ``survived = 0`` rows, so the audit reads it, never rebuilds it.

        Retired (``archived``) rows are excluded: an UNFILLABLE candidate leaks nothing a gate
        recalibration could recover -- the desk cannot fill it at ANY gate strictness -- and
        shadow-tracking it back to life would undo its retirement by the side door. Its mechanism
        lives in the retirement bank with a named way back (capacity_screen.RESURRECT_CONDITION).
        """
        rows = self.db.execute(
            f"SELECT {_COLS} FROM research_candidates WHERE survived = 0 "
            f"AND status != '{CandidateStatus.ARCHIVED.value}' ORDER BY seq"
        ).fetchall()
        return [_row_to_record(r) for r in rows]

    def retire(self, candidate_id: str) -> bool:
        """Mark one candidate retired (status -> ``archived``). Returns False if nothing changed.

        THE ONE SANCTIONED MUTATION. The table is append-only with a no-delete trigger
        (migrations/m0005: "Status may be updated as a candidate moves through the lifecycle;
        rows are never deleted"), so retirement is a status transition, never a DELETE. The row
        keeps its metrics, its original ``rejection_reason`` (the gate history the failure
        histograms are built from) and its ``survived`` flag untouched -- the WHY of the
        retirement, plus the full mechanism and the named resurrection condition, live in
        ``data/capacity_retired_bank.jsonl`` keyed by this id (L1.17).

        Dedup (``exists``), trial counts (``total``) and family deflation priors
        (``family_counts``) still see retired rows on purpose: the trials really ran, and a
        retirement must never quietly loosen the DSR wall or re-open a tested hypothesis.
        """
        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE research_candidates SET status = ?, updated_at = ? "
                "WHERE id = ? AND status != ?",
                (CandidateStatus.ARCHIVED.value, to_iso8601(utcnow()), candidate_id,
                 CandidateStatus.ARCHIVED.value),
            )
        return cur.rowcount == 1

    def status_counts(self) -> dict[str, int]:
        rows = self.db.execute(
            "SELECT status, COUNT(*) AS n FROM research_candidates GROUP BY status"
        ).fetchall()
        return {r["status"]: int(r["n"]) for r in rows}

    def family_counts(self) -> dict[str, int]:
        rows = self.db.execute(
            "SELECT family, COUNT(*) AS n FROM research_candidates GROUP BY family"
        ).fetchall()
        return {r["family"]: int(r["n"]) for r in rows}

    def total(self) -> int:
        return int(self.db.execute("SELECT COUNT(*) FROM research_candidates").fetchone()[0])

    # ----------------------------------------------------------------- checkpoint
    def get_checkpoint(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM lab_checkpoint WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_checkpoint(self, key: str, value: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO lab_checkpoint (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                "updated_at = excluded.updated_at",
                (key, value, to_iso8601(utcnow())),
            )
