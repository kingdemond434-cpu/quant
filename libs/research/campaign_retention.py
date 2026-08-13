"""CAMPAIGN OBSERVATION-RETENTION -- reading the `campaign_strata` audit row (R0270, L1.0/L2.0).

WHAT THIS EXISTS TO CATCH. `stratified_campaign_gates` replaced min-length truncation, which had
been discarding 82.9% of the observations on disk before a single test ran -- and history length is
THE binding constraint on this desk's discovery power (T=310->2500 moves power at true annualised
Sharpe 2.0 from 0.00% to 19.58%, while cohort size buys nothing). The orchestrator writes the whole
plan to the audit log as a `campaign_strata` row every campaign. Nothing read it. A regression to
truncation would restore the discard silently, and the desk would go on reporting healthy
campaigns over a fifth of its data.

THE SHARP FAILURE IS NOT THE ONE THE ROW EXPECTED, AND THE DIRECTION MATTERS. R0270 asked for a
fence that fires "when n_untested rises materially". That catches a partition getting stingier. But
`plan_strata`'s fallback -- the realistic failure, because it degrades quietly BY DESIGN -- moves
n_untested the OTHER WAY: when nothing clears the floors it emits ONE stratum at min-length holding
EVERY candidate, so n_untested drops to ZERO and n_tested rises to n_candidates. Read naively that
looks like the campaign got MORE inclusive. It is the 82.9%-discard coming back wearing the
costume of an improvement. So the fallback gets its OWN status, keyed on what the planner says
about itself and corroborated by shape -- never on a candidate count that inverts under the very
failure it is meant to catch. The untested share is published but NOT fenced; see the constant
below for why a band cannot honestly be set from one campaign shape.

WHY THE FLOOR IS MEASURED AND NOT THE ROW'S 92.0%. R0270 cites 92.0% (698,655/759,444) at k=24,
measured on a 420-candidate shape. The live campaign is a different shape -- 810 candidates, k=32,
1,259,957/1,468,341 = 85.8% -- because retention depends on the length distribution of whatever
was generated that day. Hardcoding 92% would have made this fence red from birth on a perfectly
healthy campaign, which is how a fence gets switched off (L1.43), and would have published a
CONSTANT dressed as a MEASUREMENT (L1.55). The floor comes from `data/ratchet_floors.json`, is
recorded from an observed run, and only ever rises (L1.0).

ABSENT IS NOT STALE IS NOT REGRESSED (L1.55). "No campaign has ever recorded a plan", "the last
one was too long ago" and "the last one kept less than the floor" demand different repairs, so
they are different statuses. Collapsing them would send the desk to debug the wrong organ.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import NamedTuple

from libs.validation.campaign_window import CAMPAIGN_ALPHA

_ROOT = Path(__file__).resolve().parent.parent.parent

#: The planner's own words when nothing cleared the floors and it truncated to min-length. It says
#: so deliberately ("a builder that silently produces no campaign is worse than one that produces a
#: weak campaign"), which makes this the authoritative signal -- the structural one corroborates.
_FALLBACK_MARK = "fell back to min-length"

#: NO UNTESTED-SHARE TOLERANCE IS DEFINED HERE, deliberately. Fencing that share needs its natural
#: day-to-day variance, and the desk has ONE distinct campaign shape on record -- a band picked
#: from n=1 is a fabricated constant (L1.55) and welds the gate open or shut (L1.43). The share is
#: computed and published on every run so the calibration becomes possible; R0435 rows it.


class Reading(NamedTuple):
    """One `campaign_strata` audit row, resolved into the quantities the fence judges."""

    db: str
    campaign_id: str
    created_at: str
    n_candidates: int
    n_tested: int
    n_untested: int
    obs_retained: int
    obs_available: int
    strata_alpha: float
    outcome: str

    @property
    def retained_fraction(self) -> float | None:
        """Share of available observations the campaign actually tested on. The headline metric."""
        return self.obs_retained / self.obs_available if self.obs_available > 0 else None

    @property
    def untested_fraction(self) -> float | None:
        return self.n_untested / self.n_candidates if self.n_candidates > 0 else None

    @property
    def k_strata(self) -> int | None:
        """Strata count, recovered from the per-family level the row records.

        `strata_alpha` is written as CAMPAIGN_ALPHA/k, so k is the only thing it can be. Recovered
        rather than stored because that is what the writer emits, and inventing a second field
        would let the two disagree.
        """
        if self.strata_alpha <= 0:
            return None
        return max(1, round(CAMPAIGN_ALPHA / self.strata_alpha))

    @property
    def is_fallback(self) -> bool:
        """Did the planner truncate to min-length because nothing cleared the floors?

        Primary signal is the planner's own `outcome` text -- self-reported, unambiguous, and
        written for exactly this purpose. The structural signal is the corroborator and the
        backstop for rows written before that text existed: the fallback emits ONE stratum holding
        EVERY candidate, so k==1 AND nothing is left untested. A legitimate single-stratum plan can
        also test everyone, so the structural form alone is suggestive rather than conclusive --
        which is why it is ANDed with a retention collapse at the call site, never used bare.
        """
        return _FALLBACK_MARK in (self.outcome or "")

    @property
    def structurally_single_stratum(self) -> bool:
        return self.k_strata == 1 and self.n_untested == 0 and self.n_candidates > 0


def audit_dbs(root: Path | None = None) -> list[Path]:
    """Every sqlite file under data/ that actually carries an `audit_log` table.

    DISCOVERED, NEVER LISTED (L1.57). A hardcoded db list is a count of what the author knew about,
    and it cannot fall when a store disappears -- so the one event it exists to reveal is the one
    it structurally cannot show. The desk runs several stores (crypto, research, lake, demo) and
    which one holds the live campaign has already changed once.
    """
    r = root or _ROOT
    out: list[Path] = []
    for p in sorted((r / "data").glob("*.sqlite")):
        try:
            con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        except sqlite3.Error:
            continue
        try:
            row = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'"
            ).fetchone()
            if row:
                out.append(p)
        except sqlite3.Error:
            continue          # unreadable store -- not an audit store as far as we can prove
        finally:
            con.close()
    return out


def _row_to_reading(db: Path, row: sqlite3.Row) -> Reading | None:
    try:
        inp = json.loads(row["inputs_json"])
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(inp, dict):
        return None
    try:
        return Reading(
            db=db.name,
            campaign_id=str(inp.get("campaign_id", "")),
            created_at=str(row["created_at"]),
            n_candidates=int(inp["n_candidates"]),
            n_tested=int(inp["n_tested"]),
            n_untested=int(inp["n_untested"]),
            obs_retained=int(inp["obs_retained"]),
            obs_available=int(inp["obs_available"]),
            strata_alpha=float(inp["strata_alpha"]),
            outcome=str(row["outcome"] or ""),
        )
    except (KeyError, TypeError, ValueError):
        # A row missing the fields this fence judges is NOT a healthy row we can skip past. It is
        # returned as None so the caller counts it as malformed rather than silently reading an
        # older, greener row underneath it (L2.4 -- no silent swallow).
        return None


#: The store this fence was BUILT to floor: the daily crypto factory, whose min-length truncation
#: was discarding 82.9% of the observations on disk. Named here because a subject that is only
#: implied by a docstring is a subject the code can silently change (R0435).
SUBJECT_DB = "sor_crypto.sqlite"


def series_by_db(root: Path | None = None) -> tuple[dict[str, list[Reading]], int, int, int]:
    """EVERY `campaign_strata` row, grouped by the store that wrote it.

    WHY THE PARTITION IS THE WHOLE POINT (R0435). `newest_reading` took the newest row across ALL
    stores, and the desk turned out to run two entirely different campaign populations under one
    `campaign_strata` name: the daily crypto factory (`sor_crypto`, k=32, 85.8% retention, 36.7%
    untested) and the research lake (`sor_research`, k=1, 100% retention, 0% untested, ~90 rows a
    day). Every read was honest and the SUBJECT silently changed -- the newest row is always a
    research-lake row, so the crypto factory's retention, the only quantity R0270 built this fence
    to floor, became structurally unreadable, and its 7-day silence read as a 23h-old healthy plan.

    Returns (by_db, n_dbs, n_rows_seen, n_malformed). Malformed rows are COUNTED, never skipped
    into invisibility (L1.60): a store whose rows stopped parsing must not read as a store with
    fewer campaigns.
    """
    dbs = audit_dbs(root)
    by_db: dict[str, list[Reading]] = {}
    seen = malformed = 0
    for db in dbs:
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row
        except sqlite3.Error:
            continue
        try:
            rows = con.execute(
                "SELECT created_at, outcome, inputs_json FROM audit_log "
                "WHERE decision_type='campaign_strata' ORDER BY created_at"
            ).fetchall()
        except sqlite3.Error:
            continue
        finally:
            con.close()
        for row in rows:
            seen += 1
            rd = _row_to_reading(db, row)
            if rd is None:
                malformed += 1
            else:
                by_db.setdefault(db.name, []).append(rd)
    return by_db, len(dbs), seen, malformed


class UntestedStats(NamedTuple):
    """The calibration input R0435 asks for, per POPULATION -- never pooled.

    Pooling is the trap the row half-saw. 92 of the desk's 95 recorded campaigns are research-lake
    plans whose untested share is 0.0 BY CONSTRUCTION (one stratum holding everyone), so a pooled
    standard deviation measures the mix of two populations, not the drift of either. A band set
    from it is a fabricated constant (L1.55) that fires on a change of campaign TYPE and is blind
    to the shape drift it was built for -- welded in both directions at once (L1.43).
    """

    n: int
    mean: float | None
    sd: float | None
    degenerate: bool          # every observation identical -- no variance to calibrate against

    @property
    def calibratable(self) -> bool:
        """R0435's own bar: ~10 campaigns AND real variance. Both, or the band is invented."""
        return self.n >= MIN_CAMPAIGNS_FOR_BAND and not self.degenerate

    @property
    def verdict(self) -> str:
        if self.n < MIN_CAMPAIGNS_FOR_BAND:
            return f"UNMEASURED-BAND ({self.n}/{MIN_CAMPAIGNS_FOR_BAND} campaigns)"
        if self.degenerate:
            return f"DEGENERATE ({self.n} campaigns, zero variance -- nothing to calibrate)"
        return f"CALIBRATABLE ({self.n} campaigns, sd {self.sd:.4f})"


#: R0435's bar, stated as a COUNT of observations rather than a wait (L1.48 -- evidence is the
#: clock). Nothing here is gated on a date; the band becomes settable when the campaigns exist.
MIN_CAMPAIGNS_FOR_BAND = 10


def untested_stats(readings: list[Reading]) -> UntestedStats:
    """n / mean / sd of the untested share over one population, and whether it has any variance."""
    vals = [r.untested_fraction for r in readings if r.untested_fraction is not None]
    if not vals:
        return UntestedStats(0, None, None, degenerate=True)
    mean = sum(vals) / len(vals)
    sd = (sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5 if len(vals) > 1 else 0.0
    return UntestedStats(len(vals), mean, sd, degenerate=(sd == 0.0))


def newest_reading(root: Path | None = None) -> tuple[Reading | None, int, int]:
    """The most recent `campaign_strata` row across every audit store.

    KEPT AS-IS AND NO LONGER THE FENCE'S JUDGEMENT PATH. "Whatever wrote last" is a legitimate
    question and a useless subject: see `series_by_db` for what reading it across two campaign
    populations did to this fence.
    """
    by_db, n_dbs, seen, _malformed = series_by_db(root)
    best: Reading | None = None
    for readings in by_db.values():
        if readings and (best is None or readings[-1].created_at > best.created_at):
            best = readings[-1]
    return best, n_dbs, seen
