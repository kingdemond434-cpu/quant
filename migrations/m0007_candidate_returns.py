"""Migration 0007 — per-candidate return series (the EVIDENCE behind every verdict).

Every candidate the lab has ever tested had its net return series computed and then THROWN AWAY:
``research_candidates`` (m0005) stores scalars only — sharpe, dsr, pbo, survived, rejection_reason.
The verdict was kept, the evidence was discarded. That makes the standing weak-edge order
unenforceable: a weak candidate's whole value is what it contributes IN COMBINATION (N uncorrelated
edges of Sharpe s give s*sqrt(N)), and cross-candidate correlation, orthogonality and any ensemble
method need the SERIES, not the summary. Nothing can be measured retroactively from a scalar.

This table closes that. One row per (candidate, series kind), written in the SAME transaction as the
scalar row so the two can never diverge, for SURVIVORS AND REJECTS ALIKE — the rejects are the
weak-edge pool the ensemble path exists to mine, so they are the load-bearing case, not the
afterthought.

STORAGE IS A BLOB OF LITTLE-ENDIAN FLOAT64 (``'<f8'``), NOT JSON. Three reasons, in order:
  1. BYTE-EXACT. float64 -> 8 bytes -> float64 is the identity map. JSON round-trips through a
     decimal text rendering; the evidence must come back bit-for-bit or it is not evidence.
  2. NON-FINITE VALUES SURVIVE. A return series can legitimately contain NaN/inf. Standard JSON
     has no encoding for them — Python emits bare ``NaN``/``Infinity`` tokens that are not valid
     JSON and that other readers reject or silently coerce. Silent coercion of a NaN to 0.0 is
     exactly the class of corruption this whole table exists to stop.
  3. SELF-CHECKING. ``length(series_blob) = n_obs * 8`` is a CHECK the database itself enforces,
     so a truncated write cannot commit, and the sha256 in ``checksum`` catches anything subtler.
Size was never the argument: ~420 candidates x ~1400 bars x 8 bytes is ~5 MB.

``epoch_key`` IS THE ALIGNMENT CONTRACT. It names the exact bar grid a series lives on (see
``libs.autodiscovery.memory.bar_epoch``). Two series may be placed side by side in a matrix ONLY if
their epoch keys are equal; the reader refuses or flags a mismatch rather than padding, because
misaligning two series manufactures correlation out of arithmetic — the same failure
``libs.research.cohort_independence.demeaning_floor`` documents for cross-sectional demeaning.

APPEND-ONLY AND IMMUTABLE. Both a no-delete and a no-update trigger: unlike a candidate's status,
a recorded series has no legitimate later state. It is what the backtest produced, forever.
"""

from __future__ import annotations

from libs.store.migrations import Migration

_KINDS = "'net', 'stressed'"

STATEMENTS: tuple[str, ...] = (
    f"""
    CREATE TABLE candidate_returns (
        seq          INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id TEXT NOT NULL REFERENCES research_candidates(id),
        kind         TEXT NOT NULL CHECK (kind IN ({_KINDS})),
        epoch_key    TEXT NOT NULL,
        n_obs        INTEGER NOT NULL CHECK (n_obs > 0),
        dtype        TEXT NOT NULL CHECK (dtype = '<f8'),
        timeframe    TEXT,
        checksum     TEXT NOT NULL,
        series_blob  BLOB NOT NULL CHECK (length(series_blob) = n_obs * 8),
        recorded_at  TEXT NOT NULL,
        UNIQUE (candidate_id, kind)
    )
    """,
    """
    CREATE TRIGGER candidate_returns_no_delete
    BEFORE DELETE ON candidate_returns
    BEGIN
        SELECT RAISE(ABORT, 'candidate_returns is append-only');
    END
    """,
    """
    CREATE TRIGGER candidate_returns_no_update
    BEFORE UPDATE ON candidate_returns
    BEGIN
        SELECT RAISE(ABORT, 'candidate_returns is append-only');
    END
    """,
    "CREATE INDEX idx_candidate_returns_epoch ON candidate_returns(epoch_key, kind)",
)

MIGRATION = Migration(version=7, name="candidate_returns", statements=STATEMENTS)
