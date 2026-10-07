"""PERISHABILITY (L1.65's missing half) -- for an observable the desk does NOT record, does
delay cost DELAY, or does it cost THE DATA?

THE GAP THIS CLOSES. Three correct instruments exist and the join between them exists nowhere:

  ``check_unwired_capability.py``   scores 256 uncalled capabilities as ONE class -- latent value.
                                    It has no column for "is this input backfillable?", so a
                                    recorder of a perishable stream and a dormant report rank the
                                    same. One of those is a CLOCK.
  ``libs/research/recoverability``  (L1.65) is denominated in STREAMS THAT EXIST. Zero rows
                                    recorded => zero span => zero loss => no alarm. It cannot see
                                    a stream that was never opened. WS-005 one level up.
  ``scripts/asymmetry_ledger.py``   HAS a PERISHABLE class, verified 2026-08-03 -- before the
                                    2026-08-18 MT5 mandate. Both of its PERISHABLE rows are
                                    crypto-exchange observables the desk may never hunt again, so
                                    it returns a full ranking that is green and empty of anything
                                    actionable.

Recoverability asks "did the desk LOSE span, and can it be bought back?". This asks the strictly
earlier question: "is the desk ACCRUING span at all, and if not, is that recoverable?" A stream
never opened cannot lose span, so it is invisible to every gauge the desk owns.

WHY THE DISTINCTION IS THE WHOLE POINT. Most unbuilt things cost their delay and nothing more --
build it later and you have the same thing. A perishable observable is different in kind: the
broker publishes ``swap_long`` for today and will never tell you what it was last Tuesday. Every
night without a recorder is a night permanently unbuyable at any price. Ranking those two classes
together is how a clock ends up queued behind a report.

THE STATUSES, and the reason each exists:

  RECORDING        the store is fresh and interpretable. Nothing owed.
  BACKFILLABLE     not recording, but a named route reconstructs the history. Delay costs DELAY.
                   This is a real pass: it is the class where waiting is genuinely cheap.
  UNINTERPRETABLE  rows exist, but a field WITHOUT WHICH THE VALUE CANNOT BE READ is absent.
                   Recorded and useless. The desk's live instance: 244 symbols of broker swap
                   captured five times with no ``swap_mode``, and swap is quoted in POINTS on
                   some symbols and PROFIT CURRENCY on others -- a 100x difference on JPY pairs.
                   A number whose unit was never recorded is not data, and L1.67 was paid for
                   exactly once already.
  PERISHING        in-mandate, no backfill route, not recording. Delay costs THE DATA. Pages.
  NO-RECORDER      the same, and nothing in the repo even attempts it. Strictly worse: PERISHING
                   is an unwired build, this is an unmade one.
  UNMEASURED       this host cannot see the store. NEVER folded into a real verdict -- a verdict
                   about the HOST is not a verdict about the DESK (L1.28a, WS-005).

HOST HONESTY. The recorders that matter run on the box holding the MT5 terminal, and this repo is
checked out on more than one machine. So "the directory is absent here" has two causes with
opposite meanings: never recorded ANYWHERE, or recorded elsewhere and not synced. This module
separates them with git history -- a store path that has never appeared in any commit was never
recorded on any box, which is a verdict about the desk. A path git knows about but disk does not
is UNMEASURED, which is a verdict about this host and is reported as one.

THE SECOND PERISHABLE GOOD (2026-09-05): THE EDGE ITSELF.

    "Monitoring loop: prediction decay, PnL decay, state decay, cost drift, fill drift, factor
     drift, feature drift, relationship drift; hazard_i(t) = P(edge breaks next horizon |
     history); allocation changes BEFORE the formal retirement threshold."   -- the principal

An observable perishes because nobody recorded it; an EDGE perishes because the market stopped
paying for it. Same question one level up, and the same discipline answers it: name the evidence,
say n, and refuse to fold an unmeasured component into a pass. So the hazard machinery lives
beside the register rather than in a new file -- both halves of this module answer "what is this
desk losing while it waits, and can it be bought back".

WHY PRESSURES AND NOT EIGHT PROBABILITIES. Each monitored channel is a SYMPTOM of one process
(the edge being competed, drifted or regime-shifted away), measured on its own scale: a t-drop,
a z, a ratio of costs, a sign-agreement fraction. Each is mapped to a PRESSURE in [0, 1] -- the
fraction of the way from "unchanged" to "fully gone" -- and the measured pressures are AVERAGED,
not multiplied, for the reason `crowding_hazard.microstructure_pressure` gives: a product lets
one unchanged component silence five that moved. The mean pressure then becomes a probability
through the SAME exponential hazard and the SAME declared 120-day scale that
`libs.research.crowding_hazard` already uses, so the desk carries one decay scale rather than
two that can disagree.

THE SCALE IS A LABELLED PRIOR THE RETIREMENT HISTORY UPDATES (2026-10-06). Until this date the
120 days were DECLARED and never confronted with the desk's own record. `retirement_history`
now reads every record the desk keeps of a sleeve or clock leaving (the shadow ledger's
RETIRED_* rows, GOLD_RETIRED and its voids, decay_monitor's append-only actions, the clock
retirement file, the identity-broken registry archive, the roster's STANDBY parking), labels
each exit with its CAUSE, and `calibrate_scale` fits a censored exponential survival model to
the MECHANISM-DECAY exits alone -- every other exit is censored at its own date (competing
risks), because a clock that stopped when its data source vanished tells you nothing about how
long the edge would have lasted. The fit is a conjugate Gamma update whose prior IS the declared
scale, worth `HAZARD_SCALE_PRIOR_EVENTS` pseudo-events, so a thin history moves it a little and a
long one overrules it -- never silently: the published block carries d, the exposure, the prior's
weight and both scales.

WHY THE HISTORY CAN ONLY SHORTEN THE SCALE. What a survival fit measures is the POPULATION break
rate, lambda_bar = E[pressure] / scale. Mean pressure is at most 1, so scale <= 1 / lambda_bar:
the history bounds the full-pressure scale from ABOVE. A history in which edges die faster than
120 days says the declared scale is too long and replaces it; a history in which they live
longer is consistent with any scale up to that bound and cannot lengthen it. That is the
arithmetic of the bound, not a thumb on the scale.

CAUSES ARE SEPARATE CHANNELS, AND ONLY ONE OF THEM IS DECAY (2026-10-06). An edge stops paying
for six different reasons and they cost the book in different currencies. `hazard_by_cause`
splits the nine channels into labelled causes and names where each is allowed to go:

  mechanism_decay       prediction decay and P&L decay -- THIS sleeve's own forward evidence
                        against its certificate and its own past. The world-level decay draw.
  signal_expiry         a declared signal lifetime running out, on its OWN horizon. Joins the
                        decay draw as a separate event: P = 1 - (1 - mech)(1 - expiry).
  regime_mismatch       feature, factor, relationship and state drift. TEMPORARY: it reverts,
                        so it must not erase the edge; the regime posterior already prices it.
  execution_cost_decay  cost drift, fill drift, crowding (built from the same spread/fill/slip
                        ratios). Flows to the COST the sleeve is charged, never to its decay.
  data_failure          a stale or absent ledger. An integrity condition -- no NEW risk on a
                        number the desk cannot see -- never a decay verdict.
  displacement          a better eligible sleeve exists. Not decay of the displaced sleeve at
                        all: the allocator settles it by comparing feasible BOOKS.

ONE FACT ENTERS ONCE. Before this split every one of the nine channels averaged into the one
hazard that became `decay_prob_i`, while cost drift was ALSO priced through the cost surface and
regime drift through the regime posterior -- the same measurement charged two or three times.

AN UNMEASURED COMPONENT IS NOT A ZERO. A channel with no ledger on this host contributes nothing
to the mean and is listed by name in `unmeasured` with its reason (L1.28a). A sleeve where every
channel is unmeasured gets no hazard at all -- `None` and the reasons -- because a confident 0.0
built out of eight absences is the single most dangerous number this file could return.

AND A MEAN OVER ONE CHANNEL IS NOT A HAZARD EITHER. Measured on the desk's own tree 2026-09-05:
the only readable channel off-box was `state_decay`, which is a property of the BOOK's
conditioning and identical for every sleeve. Averaging it alone put 23 sleeves at 52.8% and the
verdict BREAKING -- a book-level fact wearing 23 per-edge costumes, and exactly the number that
would have shrunk 23 allocations for no per-edge reason at all. So two floors, both declared:

    HAZARD_MIN_CHANNELS   measured channels before the mean is a hazard rather than one symptom
    at least one SLEEVE-scoped channel -- a hazard built only from book-level channels is a
    statement about the book, and it is returned as UNMEASURED with that sentence

Below either floor the pressures are still reported, per channel, with their n. The hazard is
`None` and the verdict UNMEASURED, because the consumer of this number shrinks capital with it.
"""

from __future__ import annotations

import json
import math
import statistics
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]

RECORDING = "RECORDING"
BACKFILLABLE = "BACKFILLABLE"
UNINTERPRETABLE = "UNINTERPRETABLE"
PERISHING = "PERISHING"
NO_RECORDER = "NO-RECORDER"
UNMEASURED = "UNMEASURED"

#: Statuses that do NOT fail the build. BACKFILLABLE passes because its whole meaning is that
#: waiting is cheap; UNMEASURED does not appear here -- it fails, because an unmeasured thing must
#: never read as fine (L1.28a).
PASSING = (RECORDING, BACKFILLABLE)


@dataclass(frozen=True)
class Observable:
    """One thing the desk could record, and what it costs to not be recording it.

    ``backfill_route`` is the load-bearing field and it is deliberately a STRING OR NONE rather
    than a bool: a route has to be nameable to count. "probably reconstructable" is not a route,
    and the honest value there is None -- which grades the row PERISHING and makes someone either
    find the route or start the recorder.
    """

    key: str
    what: str
    store: str                          # repo-relative dir or file the recorder writes
    recorder: str | None                # "module:function" that records it, or None
    backfill_route: str | None          # named, verified route -- or None if the data is gone
    max_staleness_h: float
    interpretive_fields: tuple[str, ...] = ()   # absent => the recorded value cannot be read
    in_mandate: bool = True
    why: str = ""


@dataclass
class Row:
    key: str
    status: str
    what: str
    store: str
    recorder: str | None
    backfill_route: str | None
    n_files: int
    newest: str | None
    age_h: float | None
    missing_interpretive: list[str] = field(default_factory=list)
    detail: str = ""


@dataclass
class Report:
    generated_at: str
    status: str
    rows: list[Row]
    n_perishing: int
    n_uninterpretable: int
    n_unmeasured: int
    n_recording: int
    notes: list[str] = field(default_factory=list)


#: THE REGISTER. Every row is an observable inside the MT5/Fusion mandate (LAWS section 1) that
#: this desk can reach today. It is a SEED, never a boundary (LAWS anti-hardcode): rows are added
#: as observables are identified, and a row is removed only when the observable leaves the
#: mandate. Nothing here is scoped to a symbol list.
REGISTER: tuple[Observable, ...] = (
    Observable(
        key="financing_leg",
        what="broker swap_long/swap_short + swap_mode + triple-swap day, per symbol, per night",
        store="desks/mt5/data/tape/contract_terms",
        recorder="desks.mt5.mt5desk.tape:record_contract_terms",
        backfill_route=None,
        max_staleness_h=30.0,
        # `swap_mode` + `point` + `contract_size` ARE the unit. CORRECTED 2026-08-29 against the
        # tape itself: this comment previously said "in mode 0 (POINTS) ... in any other mode it
        # is already currency", and both halves are wrong. MT5 mode 0 is DISABLED and mode 1 is
        # POINTS; mode 5 (INTEREST_CURRENT) is an ANNUAL PERCENT of notional, not currency.
        # Measured on desks/mt5/data/tape/contract_terms: 110 symbols are mode 1 and 138 are
        # mode 5, so the "already currency" reading was wrong on 55% of the universe -- a
        # DIMENSION error, not a factor, and always in the direction that makes a candidate look
        # cheaper. Without all three fields a JPY cross reads 100x off a 5-digit major, and the
        # error hides on exactly the majors a spot-check would try first (point*contract_size ==
        # 1.0 there). The resolver is desks/mt5/research/carry_state.money_per_lot_night.
        interpretive_fields=("swap_mode", "point", "contract_size", "currency_profit"),
        why="MT5 symbol_info reports TODAY's swap only. There is no endpoint, archive or vendor "
            "for this broker's swap on a past date, so an unrecorded night is unbuyable. It is "
            "also the second price on every CFD the desk trades: the spot quote is recorded 197 "
            "times over and the financing leg is the half nobody kept.",
    ),
    Observable(
        key="tick_tape",
        what="bid/ask/last tick stream per symbol",
        store="desks/mt5/data/tape/ticks",
        recorder="desks.mt5.mt5desk.tape:record_ticks",
        backfill_route=None,
        max_staleness_h=30.0,
        why="copy_ticks_from serves a shallow rolling window; past that the ticks are gone. "
            "Pre-recorder tick data is not purchasable at this broker at any price.",
    ),
    Observable(
        key="execution_constraints",
        what="stops_level / freeze_level per symbol -- the MINIMUM achievable stop distance",
        store="desks/mt5/data/tape/execution_constraints",
        recorder=None,
        backfill_route=None,
        max_staleness_h=30.0,
        why="A hard bound on every backtested stop the desk has ever run, it moves with "
            "volatility, and symbol_info reports only the current value. Nothing records it, so "
            "every stop-distance assumption in the book is unfalsifiable after the fact.",
    ),
)


def _git_knows(path: str) -> bool:
    """Has this store path EVER appeared in a commit, on any box?

    The question separates 'never recorded anywhere' from 'recorded elsewhere, not synced here'.
    A failure to run git is not evidence either way and is reported as such by the caller.
    """
    try:
        out = subprocess.run(
            ["git", "log", "--oneline", "-1", "--", path],
            cwd=_ROOT, capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(out.stdout.strip())


def _git_available() -> bool:
    try:
        out = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=_ROOT,
                             capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return out.returncode == 0


def _scan_store(root: Path, obs: Observable) -> tuple[int, datetime | None, list[str]]:
    """Count rows-bearing files, find the newest, and report which interpretive fields are absent.

    Interpretive fields are checked against the CONTENT of the newest readable file rather than
    against the schema declaration, because the defect this exists to catch is a producer that
    drops a field a schema still advertises.
    """
    p = root / obs.store
    if not p.exists():
        return 0, None, []
    files = sorted(f for f in p.rglob("*") if f.is_file())
    if not files:
        return 0, None, []
    newest_f = max(files, key=lambda f: f.stat().st_mtime)
    newest = datetime.fromtimestamp(newest_f.stat().st_mtime, tz=UTC)
    missing: list[str] = []
    if obs.interpretive_fields:
        cols = _columns(newest_f)
        if cols is None:
            missing = list(obs.interpretive_fields)
        else:
            missing = [f for f in obs.interpretive_fields if f not in cols]
    return len(files), newest, missing


def _columns(path: Path) -> set[str] | None:
    """Field names in a recorded file, or None if this host cannot read it.

    None is NOT an empty set: an unreadable file means the interpretive check did not run, which
    the caller must not render as "every field present".
    """
    try:
        if path.suffix == ".parquet":
            import pyarrow.parquet as pq
            # REQUIRED on the pinned pyarrow (>=24,<25); mypy reports it unused on 25.x,
            # and deleting it there is what reds the deploy gate (pyproject:219).
            return set(pq.read_schema(path).names)  # type: ignore[no-untyped-call]
        if path.suffix in (".json", ".jsonl"):
            txt = path.read_text("utf-8")
            raw: Any = (json.loads(txt) if path.suffix == ".json"
                        else [json.loads(ln) for ln in txt.splitlines() if ln.strip()])
            rows = raw if isinstance(raw, list) else [raw]
            cols: set[str] = set()
            for r in rows:
                if isinstance(r, dict):
                    cols |= set(r)
            return cols
    except Exception:
        return None
    return None


def grade(obs: Observable, root: Path, now: datetime, git_ok: bool) -> Row:
    """One observable -> one status. The whole module is this function; the rest is plumbing."""
    n_files, newest, missing = _scan_store(root, obs)
    age_h = None if newest is None else (now - newest).total_seconds() / 3600.0
    row = Row(key=obs.key, status=UNMEASURED, what=obs.what, store=obs.store,
              recorder=obs.recorder, backfill_route=obs.backfill_route, n_files=n_files,
              newest=None if newest is None else newest.isoformat(timespec="seconds"),
              age_h=None if age_h is None else round(age_h, 2),
              missing_interpretive=missing)

    if n_files and missing:
        # Recorded, and unreadable. Reported ahead of freshness on purpose: a fresh store of
        # uninterpretable numbers is worse than a stale one, because it looks healthy to every
        # consumer and to every gauge that counts rows.
        row.status = UNINTERPRETABLE
        row.detail = (f"{n_files} file(s) recorded, but {', '.join(missing)} absent -- the "
                      f"recorded value cannot be converted to money without it")
        return row

    if n_files and age_h is not None and age_h <= obs.max_staleness_h:
        row.status = RECORDING
        row.detail = f"{n_files} file(s), newest {age_h:.1f}h old"
        return row

    # Nothing fresh on this disk. Before grading the DESK, establish whether this HOST can see
    # the store at all -- the two have opposite meanings and only one is a defect here.
    if n_files == 0:
        if not git_ok:
            row.detail = "git unavailable; cannot distinguish never-recorded from not-synced"
            return row
        if _git_knows(obs.store):
            row.status = UNMEASURED
            row.detail = ("store is in git history but absent on this host -- recorded on another "
                          "box and not synced here; this is a verdict about the host, not the desk")
            return row

    if obs.backfill_route:
        row.status = BACKFILLABLE
        row.detail = f"not recording; delay costs delay -- route: {obs.backfill_route}"
        return row

    if obs.recorder is None:
        row.status = NO_RECORDER
        row.detail = ("no recorder exists in this repo and the observable is point-in-time only; "
                      "every interval that passes is permanently unbuyable")
        return row

    row.status = PERISHING
    row.detail = (f"recorder {obs.recorder} exists and is not producing"
                  + (f" (store {age_h:.1f}h stale)" if age_h is not None else " (store empty)")
                  + "; no backfill route -- delay costs the data, not the delay")
    return row


def build_report(root: Path | None = None, now: datetime | None = None,
                 register: tuple[Observable, ...] = REGISTER) -> Report:
    root = _ROOT if root is None else root
    now = datetime.now(UTC) if now is None else now
    git_ok = _git_available()
    rows = [grade(o, root, now, git_ok) for o in register if o.in_mandate]
    n_per = sum(1 for r in rows if r.status in (PERISHING, NO_RECORDER))
    n_uni = sum(1 for r in rows if r.status == UNINTERPRETABLE)
    n_unm = sum(1 for r in rows if r.status == UNMEASURED)
    n_rec = sum(1 for r in rows if r.status == RECORDING)
    notes: list[str] = []
    if not git_ok:
        notes.append("git unavailable: never-recorded and not-synced could not be separated")
    if not rows:
        # L1.57: a verdict over an empty population is vacuous, never a pass.
        return Report(now.isoformat(timespec="seconds"), UNMEASURED, rows, 0, 0, 0, 0,
                      [*notes, "register is empty -- nothing was graded"])
    # Worst status wins. Order encodes what the desk loses, not how loud the word is.
    for bad in (NO_RECORDER, PERISHING, UNINTERPRETABLE, UNMEASURED):
        if any(r.status == bad for r in rows):
            return Report(now.isoformat(timespec="seconds"), bad, rows,
                          n_per, n_uni, n_unm, n_rec, notes)
    return Report(now.isoformat(timespec="seconds"), RECORDING, rows,
                  n_per, n_uni, n_unm, n_rec, notes)


def to_dict(rep: Report) -> dict[str, Any]:
    return {
        "generated_at": rep.generated_at,
        "status": rep.status,
        "n_observables": len(rep.rows),
        "n_perishing": rep.n_perishing,
        "n_uninterpretable": rep.n_uninterpretable,
        "n_unmeasured": rep.n_unmeasured,
        "n_recording": rep.n_recording,
        "notes": rep.notes,
        "observables": [
            {
                "key": r.key, "status": r.status, "what": r.what, "store": r.store,
                "recorder": r.recorder, "backfill_route": r.backfill_route,
                "n_files": r.n_files, "newest": r.newest, "age_h": r.age_h,
                "missing_interpretive": r.missing_interpretive, "detail": r.detail,
            }
            for r in rep.rows
        ],
    }


# =========================================================================== EDGE HAZARD
#: The eight monitored channels the principal named, plus crowding -- the one leading indicator
#: the desk already owns (`libs.research.crowding_hazard`), which had no importer until this.
#: Order is the reading order: what the edge PREDICTED, what it PAID, what it was CONDITIONED on,
#: what it COST to trade, and what the world around it did.
HAZARD_COMPONENTS: tuple[str, ...] = (
    "prediction_decay", "pnl_decay", "state_decay", "cost_drift", "fill_drift",
    "factor_drift", "feature_drift", "relationship_drift", "crowding",
)

#: Days at FULL pressure for one e-folding of the edge -- THE PRIOR. Taken verbatim from
#: `crowding_hazard.hazard` (rate = pressure / 120.0) so the desk has ONE decay scale: a second
#: scale here would let two organs disagree about the same edge and be equally defensible.
#: Since 2026-10-06 this is the PRIOR of `calibrate_scale`, not the answer: the drift monitor
#: publishes the history-updated scale beside it and uses that one. Kept at 120 because the
#: crowding channel inverts `crowding_hazard`'s own probability through exactly this number.
HAZARD_SCALE_DAYS = 120.0
#: What the prior is WORTH, in pseudo-retirements. One: the declared scale counts as one edge
#: observed to break after 120 full-pressure days -- enough to stand when the desk has no
#: history, little enough that three real mechanism retirements outvote it.
HAZARD_SCALE_PRIOR_EVENTS = 1.0
#: The horizon the question is asked over. "Next horizon" in the principal's sentence -- one
#: quarter, the shortest window over which a forward clock can carry a verdict at all.
HAZARD_HORIZON_DAYS = 90.0
#: Paired observations before a channel's trend is a trend rather than noise with a direction.
HAZARD_MIN_N = 10
#: Measured channels before their mean is called a hazard. Three of nine is a low bar and a real
#: one: it is the difference between "several symptoms agree" and "one number moved".
HAZARD_MIN_CHANNELS = 3
#: Channel scopes. A BOOK channel (the conditioning, the covariance, the driver graph) is the
#: same number for every sleeve; a hazard made only of those is a fact about the book.
SLEEVE, BOOK = "sleeve", "book"

#: Verdict lines, stated as PROBABILITIES so they do not move when the scale is re-derived.
#: Full pressure over the horizon is 1 - exp(-90/120) = 0.528, so these sit at roughly a
#: quarter and two thirds of the most this hazard can ever say.
HAZARD_AT_RISK = 0.15
HAZARD_BREAKING = 0.35
HOLDING, AT_RISK, BREAKING = "HOLDING", "AT_RISK", "BREAKING"


@dataclass(frozen=True)
class Pressure:
    """One monitored channel's reading: how far toward gone, on what evidence.

    `value is None` is the load-bearing state and the reason this is not a bare float -- it means
    the channel HAS NO LEDGER on this host, which must never average in as a calming zero.
    """

    name: str
    value: float | None
    n: int = 0
    why: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    #: SLEEVE (this edge's own evidence) or BOOK (shared by every sleeve). Defaults to SLEEVE
    #: because a channel that has not said otherwise is being offered as this edge's evidence.
    scope: str = SLEEVE


def book_scope(p: Pressure) -> Pressure:
    """Mark a channel as the BOOK's, so a hazard cannot be built out of shared numbers alone."""
    return Pressure(p.name, p.value, p.n, p.why, p.detail, BOOK)


def _clip01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else float(x))


def unmeasured_pressure(name: str, why: str, n: int = 0, **detail: Any) -> Pressure:
    """A channel that could not be read. Carries the reason so the report can print it."""
    return Pressure(name, None, n, why, detail)


def decay_pressure(name: str, forward: float | None, reference: float | None, n: int,
                   *, min_n: int = HAZARD_MIN_N, **detail: Any) -> Pressure:
    """Forward performance against the number the edge was certified on.

    THE SHORTFALL IS A FRACTION OF THE CLAIM, not of the forward reading, so an edge certified at
    0.4R that now delivers 0.2R and one certified at 0.05R that now delivers 0.025R read the same
    -- both have lost half of what they promised. Delivering AT or ABOVE the claim is zero
    pressure, never negative: an edge doing better than advertised is not evidence it will last,
    and letting it subtract would let one strong sleeve mask a book that is breaking.
    """
    if forward is None or reference is None:
        return unmeasured_pressure(name, "no forward or reference expectancy on this host", n,
                                   **detail)
    if n < min_n:
        return unmeasured_pressure(name, f"{n} observation(s), need {min_n}", n, **detail)
    if abs(reference) < 1e-12:
        return unmeasured_pressure(
            name, "the certified expectancy is zero: there is no claim to fall short of", n,
            **detail)
    shortfall = (reference - forward) / abs(reference)
    return Pressure(name, _clip01(shortfall), n,
                    ("" if shortfall > 0 else "forward is at or above the reference"),
                    {"forward": forward, "reference": reference,
                     "shortfall_frac": round(shortfall, 6), **detail})


def drift_pressure(name: str, z: float | None, n: int, *, watch: float = 1.0,
                   broken: float = 3.0, **detail: Any) -> Pressure:
    """A z-scored drift (feature, factor) mapped onto the same [0, 1] ruler.

    Below the WATCH line the statistic is inside its own historical dispersion and carries no
    pressure; at BROKEN it is as far out as the desk is willing to call gone. The two lines are
    the drift monitor's own (WATCH_Z, and DRIFT_Z one step further) so a reader who has seen
    DRIFT.json's verdict does not meet a second, private set of thresholds here.
    """
    if z is None:
        return unmeasured_pressure(name, "no z on this host", n, **detail)
    if n < HAZARD_MIN_N:
        return unmeasured_pressure(name, f"{n} window(s), need {HAZARD_MIN_N}", n, **detail)
    span = max(broken - watch, 1e-9)
    return Pressure(name, _clip01((abs(z) - watch) / span), n, "",
                    {"z": z, "watch": watch, "broken": broken, **detail})


def ratio_pressure(name: str, now: float | None, baseline: float | None, n: int,
                   *, worse_is_higher: bool = True, doubling_is_gone: bool = True,
                   **detail: Any) -> Pressure:
    """A cost or a fill rate now against what it was when the edge was validated.

    Denominated in the BASELINE, so "costs doubled" is full pressure whatever the currency. When
    `worse_is_higher` is False the channel is a rate that should stay high (fill rate), and the
    pressure is the fraction of it that has been lost.
    """
    if now is None or baseline is None:
        return unmeasured_pressure(name, "no now/baseline pair on this host", n, **detail)
    if n < HAZARD_MIN_N:
        return unmeasured_pressure(name, f"{n} observation(s), need {HAZARD_MIN_N}", n, **detail)
    if abs(baseline) < 1e-15:
        return unmeasured_pressure(name, "baseline is zero: no ratio to take", n, **detail)
    if worse_is_higher:
        moved = (now - baseline) / abs(baseline)
        scale = 1.0 if doubling_is_gone else 2.0
    else:
        moved = (baseline - now) / abs(baseline)
        scale = 1.0
    return Pressure(name, _clip01(moved / scale), n, "",
                    {"now": now, "baseline": baseline, "moved_frac": round(moved, 6), **detail})


def share_pressure(name: str, share: float | None, n: int, **detail: Any) -> Pressure:
    """A channel that is already a fraction of a population gone (state dimensions buried, say).

    The identity map onto the ruler, given a name so callers do not reach for the private clip
    and so a reader of the report can tell "half the conditioning stopped predicting" from a
    pressure that came out of a z or a ratio.
    """
    if share is None:
        return unmeasured_pressure(name, "no share on this host", n, **detail)
    if n < HAZARD_MIN_N:
        return unmeasured_pressure(name, f"{n} observation(s), need {HAZARD_MIN_N}", n, **detail)
    return Pressure(name, _clip01(share), n, "", {"share": round(share, 6), **detail})


def agreement_pressure(name: str, agreement: float | None, n: int, **detail: Any) -> Pressure:
    """Cross-asset sign agreement: what fraction of the relationship still points the way it did.

    A coin flip (0.5) is FULL pressure, not half of it -- a relationship that agrees with itself
    half the time has no sign, and an edge built on it has nothing left to decay. Perfect
    agreement is zero pressure.
    """
    if agreement is None:
        return unmeasured_pressure(name, "no agreement measure on this host", n, **detail)
    if n < HAZARD_MIN_N:
        return unmeasured_pressure(name, f"{n} relationship(s), need {HAZARD_MIN_N}", n, **detail)
    return Pressure(name, _clip01(2.0 * (1.0 - agreement)), n, "",
                    {"agreement": agreement, **detail})


def hazard_probability(pressure: float, *, horizon_days: float = HAZARD_HORIZON_DAYS,
                       scale_days: float = HAZARD_SCALE_DAYS) -> float:
    """Pressure -> P(break within the horizon), the exponential hazard crowding_hazard declares."""
    return 1.0 - math.exp(-(pressure / scale_days) * horizon_days)


def pressure_from_hazard(p: float, *, horizon_days: float = HAZARD_HORIZON_DAYS,
                         scale_days: float = HAZARD_SCALE_DAYS) -> float:
    """The inverse, so a component that already speaks in probabilities joins the average.

    `crowding_hazard.hazard` returns P(competed away within the horizon) rather than a pressure.
    Averaging a probability with eight pressures would weight it by whatever the horizon happened
    to be; inverting it through the SAME scale recovers the pressure it was built from exactly,
    which is the only way the crowding channel can sit beside the other eight without silently
    changing weight when the horizon moves.
    """
    p = min(max(p, 0.0), 1.0 - 1e-12)
    return _clip01(-math.log(1.0 - p) * scale_days / max(horizon_days, 1e-9))


def edge_hazard(components: list[Pressure], *, horizon_days: float = HAZARD_HORIZON_DAYS,
                scale_days: float = HAZARD_SCALE_DAYS,
                min_channels: int = HAZARD_MIN_CHANNELS) -> dict[str, Any]:
    """hazard_i(t) = P(edge breaks next horizon | history), from the channels that HAVE a history.

    The mean is taken over MEASURED channels only and the count is published beside it: a hazard
    standing on one channel and a hazard standing on eight are different evidence, and the caller
    that shrinks an allocation on this number is entitled to know which it has.

    THE TWO FLOORS ARE WHY THIS RETURNS None SO OFTEN, AND THEY ARE THE POINT. Under
    `min_channels` measured, or with no SLEEVE-scoped channel among them, the pressures are all
    reported and the hazard is None: one book-level number repeated across fifty sleeves is not
    fifty per-edge verdicts, and capital must not move on it.
    """
    measured = [c for c in components if c.value is not None]
    unmeasured = [c for c in components if c.value is None]
    own = [c for c in measured if c.scope == SLEEVE]
    rows = {c.name: {"pressure": (None if c.value is None else round(c.value, 6)), "n": c.n,
                     "scope": c.scope, "why": c.why, **c.detail} for c in components}
    lines = {"at_risk": HAZARD_AT_RISK, "breaking": HAZARD_BREAKING, "scale_days": scale_days,
             "min_n": HAZARD_MIN_N, "min_channels": min_channels}
    base: dict[str, Any] = {
        "hazard": None, "verdict": UNMEASURED, "mean_pressure": None,
        "n_measured": len(measured), "n_sleeve_channels": len(own),
        "horizon_days": horizon_days, "components": rows,
        "unmeasured": [c.name for c in unmeasured], "lines": lines}
    if not measured:
        return {**base, "why": ("no monitored channel carries a ledger on this host; a 0.0 built "
                                "out of absences is the one number this must never return")}
    if len(measured) < min_channels:
        return {**base, "why": (f"{len(measured)} of {len(components)} channel(s) measured, need "
                                f"{min_channels}: one symptom is not several agreeing, and this "
                                "number moves capital")}
    if not own:
        return {**base, "why": ("every measured channel is BOOK-scoped "
                                f"({', '.join(sorted(c.name for c in measured))}): that is a "
                                "statement about the book's conditioning, covariance and driver "
                                "graph, not about this edge")}
    mean = statistics.fmean(float(c.value) for c in measured if c.value is not None)
    p = hazard_probability(mean, horizon_days=horizon_days, scale_days=scale_days)
    verdict = (BREAKING if p >= HAZARD_BREAKING else
               (AT_RISK if p >= HAZARD_AT_RISK else HOLDING))
    lead = max(measured, key=lambda c: c.value or 0.0)
    return {**base, "hazard": round(p, 6), "verdict": verdict, "mean_pressure": round(mean, 6),
            "leading_channel": lead.name,
            "why": (f"{len(measured)} of {len(components)} channel(s) measured ({len(own)} this "
                    f"sleeve's own), mean pressure {mean:.3f}, led by {lead.name}; P(break "
                    f"within {horizon_days:g}d) = {p:.1%}")}


# =========================================================================== CAUSES (2026-10-06)
#: The six reasons an edge stops paying, as labelled channels. See the module docstring: only the
#: first two are DECAY, and each of the others has its own destination in the allocator.
MECHANISM_DECAY = "mechanism_decay"
SIGNAL_EXPIRY = "signal_expiry"
REGIME_MISMATCH = "regime_mismatch"
EXECUTION_COST_DECAY = "execution_cost_decay"
DATA_FAILURE = "data_failure"
DISPLACEMENT = "displacement"
#: An exit that is none of the six -- a universe, jurisdiction or venue refusal. Recorded so the
#: history accounts for every exit, censored for the fit like every other non-decay exit.
POLICY = "policy"
CAUSES: tuple[str, ...] = (MECHANISM_DECAY, SIGNAL_EXPIRY, REGIME_MISMATCH,
                           EXECUTION_COST_DECAY, DATA_FAILURE, DISPLACEMENT)
#: The causes that may become the world-level edge-decay draw. Nothing else may.
DECAY_CAUSES: tuple[str, ...] = (MECHANISM_DECAY, SIGNAL_EXPIRY)

#: Which cause each of the nine monitored channels is evidence OF.
#:
#: CROWDING IS COST, NOT MECHANISM, and that is the one-fact-once rule rather than a taxonomy
#: preference: `crowding_hazard` is built from the SAME spread, fill and slip ratios that
#: cost_drift and fill_drift read off the execution twin. Putting it in the decay group while
#: cost goes to cost_bias_r would charge one slip measurement twice in two currencies.
#: RELATIONSHIP DRIFT IS REGIME: the driver graph's signs flipping is the world around the edge
#: moving, which reverts, not the edge's own mechanism failing.
#: STATE DECAY IS REGIME TOO, and this one was measured: it is the BOOK's conditioning (which
#: admission dimensions still predict), one number for every sleeve. Left in the mechanism group
#: on 2026-10-06 it read 1.0 off-box and put every sleeve with one own channel at P = 31% and any
#: with a weak own channel into BREAKING -- the 2026-09-05 book-fact-in-per-edge-costumes defect
#: again, now able to charge MORE than the blanket. The state gauntlet already re-judges the
#: dimensions it conditions on; this sleeve's mechanism is what its own ledger says.
CAUSE_OF_CHANNEL: dict[str, str] = {
    "prediction_decay": MECHANISM_DECAY,
    "pnl_decay": MECHANISM_DECAY,
    "state_decay": REGIME_MISMATCH,
    "cost_drift": EXECUTION_COST_DECAY,
    "fill_drift": EXECUTION_COST_DECAY,
    "crowding": EXECUTION_COST_DECAY,
    "feature_drift": REGIME_MISMATCH,
    "factor_drift": REGIME_MISMATCH,
    "relationship_drift": REGIME_MISMATCH,
}
#: Where each cause is allowed to reach the allocator. One destination each, so one fact is
#: charged once: a cause routed to `cost_bias_r` never also shrinks the mean or the decay draw.
ROUTE_OF_CAUSE: dict[str, str] = {
    MECHANISM_DECAY: "decay_prob_i",
    SIGNAL_EXPIRY: "decay_prob_i",
    REGIME_MISMATCH: "none -- transient; the regime posterior and crisis overlay already price it",
    EXECUTION_COST_DECAY: "cost_bias_r",
    DATA_FAILURE: "integrity -- no new risk on an unseen number; never decay",
    DISPLACEMENT: "book comparison (robust_elog.score_book / marginal_delta_elog); never decay",
}
#: Measured channels before the MECHANISM mean is a hazard: BOTH of its two, which are this
#: sleeve's own (forward against the certificate, recent against its own past). One of them alone
#: is one symptom; the old three-of-nine bar cannot apply to a group two wide.
MECHANISM_MIN_CHANNELS = 2


def signal_expiry_hazard(age_days: float | None, ttl_days: float | None, *,
                         horizon_days: float = HAZARD_HORIZON_DAYS) -> float | None:
    """P(the signal's declared lifetime ends inside the horizon), on the signal's OWN clock.

    A signal with a declared lifetime (an event study valid for N days after the event, a
    certificate dated to a regime) does not decay -- it EXPIRES, deterministically, and the share
    of the horizon that lies past its expiry is the share of the horizon it is gone for. That is
    what joins the decay draw. No declared lifetime is None, never 0: an undeclared expiry is
    unknown, not infinite.
    """
    if age_days is None or ttl_days is None:
        return None
    try:
        age, ttl = float(age_days), float(ttl_days)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(age) and math.isfinite(ttl)) or ttl <= 0.0:
        return None
    return _clip01((age + horizon_days - ttl) / max(horizon_days, 1e-9))


def _side_cause(parts: list[Pressure], cause: str, **extra: Any) -> dict[str, Any]:
    """A non-decay cause: its pressure and evidence, and where it is routed. Never a hazard."""
    measured = [float(c.value) for c in parts if c.value is not None]
    mean = statistics.fmean(measured) if measured else None
    return {"routes_to": ROUTE_OF_CAUSE[cause],
            "pressure": None if mean is None else round(mean, 6),
            "n_measured": len(measured), "channels": [c.name for c in parts],
            "unmeasured": [c.name for c in parts if c.value is None], **extra}


def hazard_by_cause(components: list[Pressure], *, expiry: tuple[float, float] | None = None,
                    stale_why: str = "", horizon_days: float = HAZARD_HORIZON_DAYS,
                    scale_days: float = HAZARD_SCALE_DAYS) -> dict[str, Any]:
    """hazard_i(t) split by CAUSE: only mechanism decay and signal expiry become the decay hazard.

    The row keeps the shape every consumer already reads -- `hazard`, `verdict`, `components`,
    `n_measured`, `unmeasured` over all nine channels -- with one change of meaning: `hazard` is
    now P(the edge's MECHANISM breaks, or its signal expires, within the horizon), and `causes`
    carries the other four with their destinations. The two decay events are distinct, so they
    combine as a union, 1 - (1 - mech)(1 - expiry), not as a product of penalties. An unmeasured
    mechanism is a None hazard (the blanket covers it) whatever the expiry says -- the expiry is
    still published, and an expiry with no mechanism reading is a reason to measure the
    mechanism, not a licence to call the rest of the edge sound.
    """
    every = edge_hazard(components, horizon_days=horizon_days, scale_days=scale_days)
    by = {cause: [c for c in components if CAUSE_OF_CHANNEL.get(c.name) == cause]
          for cause in (MECHANISM_DECAY, EXECUTION_COST_DECAY, REGIME_MISMATCH)}
    mech = edge_hazard(by[MECHANISM_DECAY], horizon_days=horizon_days, scale_days=scale_days,
                       min_channels=MECHANISM_MIN_CHANNELS)
    age, ttl = expiry if expiry is not None else (None, None)
    e = signal_expiry_hazard(age, ttl, horizon_days=horizon_days)
    m = mech["hazard"]
    hazard = None if m is None else 1.0 - (1.0 - float(m)) * (1.0 - (e or 0.0))
    cost_part = next((c for c in by[EXECUTION_COST_DECAY]
                      if c.name == "cost_drift" and c.value is not None), None)
    slip_ratio = None
    if cost_part is not None:
        now, base = cost_part.detail.get("now"), cost_part.detail.get("baseline")
        if isinstance(now, (int, float)) and isinstance(base, (int, float)) and base:
            slip_ratio = round(float(now) / float(base), 6)
    causes: dict[str, Any] = {
        MECHANISM_DECAY: {"routes_to": ROUTE_OF_CAUSE[MECHANISM_DECAY], "hazard": m,
                          "verdict": mech["verdict"], "mean_pressure": mech["mean_pressure"],
                          "n_measured": mech["n_measured"],
                          "channels": [c.name for c in by[MECHANISM_DECAY]],
                          "unmeasured": mech["unmeasured"], "why": mech["why"]},
        SIGNAL_EXPIRY: {"routes_to": ROUTE_OF_CAUSE[SIGNAL_EXPIRY], "hazard": e,
                        "age_days": age, "ttl_days": ttl,
                        "why": ("" if e is not None else
                                "no declared signal lifetime for this sleeve: unknown, not "
                                "infinite, and never a zero")},
        REGIME_MISMATCH: _side_cause(
            by[REGIME_MISMATCH], REGIME_MISMATCH, transient=True,
            why=("the market around the edge moved; it reverts, so it does not erase the edge "
                 "and does not enter the decay draw")),
        EXECUTION_COST_DECAY: _side_cause(
            by[EXECUTION_COST_DECAY], EXECUTION_COST_DECAY, slip_ratio=slip_ratio,
            slip_n=(cost_part.n if cost_part is not None else 0),
            why=("realised execution against what the certificate was priced at; charged as "
                 "cost, once, never as decay")),
        DATA_FAILURE: {"routes_to": ROUTE_OF_CAUSE[DATA_FAILURE], "flag": bool(stale_why),
                       "why": stale_why or "ledger fresh on this host"},
        DISPLACEMENT: {"routes_to": ROUTE_OF_CAUSE[DISPLACEMENT], "flag": None,
                       "why": ("not measured here by design: whether a better eligible sleeve "
                               "exists is a property of the BOOK, settled by the allocator")},
    }
    verdict = (UNMEASURED if hazard is None else
               BREAKING if hazard >= HAZARD_BREAKING else
               AT_RISK if hazard >= HAZARD_AT_RISK else HOLDING)
    return {**every, "hazard": None if hazard is None else round(hazard, 6),
            "verdict": verdict, "mean_pressure": mech["mean_pressure"],
            "leading_channel": mech.get("leading_channel"),
            "lines": {**every["lines"], "min_channels": MECHANISM_MIN_CHANNELS},
            "decay_causes": list(DECAY_CAUSES), "causes": causes,
            "why": (mech["why"] if e is None else
                    f"{mech['why']}; signal expiry P={e:.1%} on its own clock")}


# =========================================================================== CALIBRATION
#: Trades before decay_monitor can retire a sleeve on evidence (`decay_monitor.N_MIN_VERDICT`,
#: mirrored rather than imported: that organ edits the roster). Exposure accrued below it could
#: not have ENDED in a mechanism retirement, so counting it as survival would credit the edge
#: with days on which the desk was blind -- the scale would lengthen on the desk's own deafness.
DETECT_MIN_N = 20


@dataclass(frozen=True)
class ExitRecord:
    """One sleeve or clock's life in the desk's record: how long it was watched, how it ended.

    `cause` None means it is still running (right-censored). Every non-decay exit is ALSO
    censored for the decay fit, at its own date (competing risks). `detectable` is False for
    exposure on which no decay retirement could have fired (under DETECT_MIN_N trades).
    """

    name: str
    exposure_days: float
    cause: str | None
    source: str
    in_mandate: bool = True
    detectable: bool = True
    at: str = ""
    why: str = ""


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _shadow_cause(status: str) -> str | None:
    """The CAUSE a shadow-ledger status records. Unknown retirements are named, never guessed."""
    s = status.upper()
    if s in ("ACTIVE", "PROMOTION CANDIDATE", "LIVE", ""):
        return None
    if "UNIVERSE" in s or "POLICY" in s or "JURISDICTION" in s:
        return POLICY
    if ("ORPHAN" in s or "UNRECONSTRUCT" in s or "NO_BARS" in s or "QUARANTIN" in s
            or "STALE" in s or "IDENTITY" in s):
        return DATA_FAILURE
    if "KILL" in s or "REFUTED" in s or "FAILING" in s or "DECAY" in s or s == "RETIRED":
        return MECHANISM_DECAY
    return "unclassified"


def retirement_history(root: Path = _ROOT) -> tuple[list[ExitRecord], list[str]]:
    """Every exit the desk has recorded, labelled by CAUSE. Read-only; the sources are append-only.

    Returns (records, notes). A source absent on this host is a NOTE, never a silent zero: the
    count of mechanism retirements is only as complete as the files this host can see. A voided
    retirement stays in the record as what it was found to be (a data failure); a recovered
    sleeve's past exit is never removed.
    """
    desk = root / "desks" / "mt5"
    out: list[ExitRecord] = []
    notes: list[str] = []

    shadow = _read(desk / "reports" / "shadow" / "shadow_state.json")
    if isinstance(shadow, dict):
        for k, v in shadow.items():
            if not isinstance(v, dict) or "status" not in v:
                continue
            try:
                days = max(0.0, float(v.get("days_active") or 0.0))
                n = int(v.get("n") or 0)
            except (TypeError, ValueError):
                continue
            st = str(v.get("status") or "")
            out.append(ExitRecord(str(k), days, _shadow_cause(st), "shadow_state",
                                  detectable=n >= DETECT_MIN_N,
                                  at=str(v.get("retired_at") or ""),
                                  why=str(v.get("retire_reason") or st)[:160]))
    else:
        notes.append("reports/shadow/shadow_state.json unreadable: no exposure on this host")

    voided_doc = _read(desk / "data" / "GOLD_RETIRED_VOIDED.json")
    voided: dict[str, Any] = voided_doc if isinstance(voided_doc, dict) else {}
    for k, v in voided.items():
        row = v if isinstance(v, dict) else {}
        out.append(ExitRecord(str(k), 0.0, DATA_FAILURE, "GOLD_RETIRED_VOIDED",
                              at=str(row.get("retired_at") or ""),
                              why=str(row.get("voided_why") or "")[:160]))
    gold = _read(desk / "data" / "GOLD_RETIRED.json")
    for k, v in (gold if isinstance(gold, dict) else {}).items():
        if k in voided:
            continue
        row = v if isinstance(v, dict) else {}
        out.append(ExitRecord(str(k), 0.0, MECHANISM_DECAY, "GOLD_RETIRED",
                              at=str(row.get("retired_at") or ""),
                              why=str(row.get("reason") or "")[:160]))

    try:
        lines = (desk / "data" / "decay_actions.jsonl").read_text("utf-8").splitlines()
    except OSError:
        lines = []
        notes.append("data/decay_actions.jsonl absent on this host: decay_monitor's retirements "
                     "(including the 2026-09-16 pooled `discovered` retirement, if it acted) "
                     "are not visible here")
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        act = str(row.get("action") or row.get("verdict") or "").upper()
        if "RETIRE" in act:
            out.append(ExitRecord(str(row.get("sleeve") or row.get("name") or "?"), 0.0,
                                  MECHANISM_DECAY, "decay_actions", at=str(row.get("at") or ""),
                                  why=str(row.get("why") or act)[:160]))

    clocks = _read(root / "docs" / "research" / "CLOCK_RETIREMENTS.json")
    for row in ((clocks.get("retirements") or []) if isinstance(clocks, dict) else []):
        if not isinstance(row, dict) or row.get("reversed"):
            continue
        v = str(row.get("verdict") or "").upper()
        cause = (MECHANISM_DECAY if "FAILING FORWARD" in v else
                 POLICY if "JURISDICTION" in v else DATA_FAILURE)
        try:
            obs = float(row.get("observations") or 0.0)
        except (TypeError, ValueError):
            obs = 0.0
        # Crypto-exchange era (closed 2026-08-18): OUT OF MANDATE, and `observations` is taken
        # as days -- an assumption, said here, which is why these never enter the primary fit.
        out.append(ExitRecord(str(row.get("clock")), obs, cause, "CLOCK_RETIREMENTS",
                              in_mandate=False, at=str(row.get("retired_at") or ""),
                              why=str(row.get("verdict") or "")[:160]))

    arch = _read(desk / "data" / "sleeve_registry_archive.json")
    arch_rows = (arch.get("rows") or {}) if isinstance(arch, dict) else {}
    for row in (arch_rows.values() if isinstance(arch_rows, dict) else arch_rows):
        if isinstance(row, dict) and str(row.get("status") or "") == "IDENTITY_BROKEN":
            ident = row.get("identity") or {}
            out.append(ExitRecord(str(ident.get("sleeve_id") or "?"), 0.0, DATA_FAILURE,
                                  "sleeve_registry_archive", at=str(row.get("archived_at") or ""),
                                  why=str(row.get("status_why") or "")[:160]))

    roster = _read(desk / "data" / "sleeves.json")
    for row in ((roster.get("sleeves") or []) if isinstance(roster, dict) else []):
        if isinstance(row, dict) and str(row.get("status") or "") == "STANDBY":
            # Parked by the allocator's own solve: DISPLACEMENT, never decay. No exposure here --
            # the sleeve's clock keeps running in shadow and is counted there, once.
            out.append(ExitRecord(str(row.get("name")), 0.0, DISPLACEMENT, "sleeves.json",
                                  at=str(row.get("demoted_at") or ""),
                                  why=str(row.get("demote_reason") or "")[:160]))
    return out, notes


def calibrate_scale(records: list[ExitRecord], *, prior_scale_days: float = HAZARD_SCALE_DAYS,
                    prior_events: float = HAZARD_SCALE_PRIOR_EVENTS,
                    include_out_of_mandate: bool = False,
                    horizon_days: float = HAZARD_HORIZON_DAYS,
                    mean_pressure: float | None = None) -> dict[str, Any]:
    """The decay scale, updated by the desk's own retirement history. Never silently the prior.

    Censored exponential survival on DECAY exits: d decay exits over T detectable days at risk
    (every other exit censored at its date). Conjugate Gamma: the prior is `prior_events`
    pseudo-exits over `prior_events x prior_scale_days` days, so the posterior mean time-scale is
    (prior_events x prior_scale + T) / (prior_events + d) -- the declared scale shrunk toward the
    history by exactly as much evidence as the history holds.

    TWO-SIDED (audit of PR #261, 2026-10-06). The history measures the rate E[pressure] / scale,
    so the full-pressure scale it implies is `mean_pressure x T / d` -- shrunk by the conjugate
    prior, `mean_pressure x posterior_scale`. That is used whichever side of the declared 120d it
    falls: a history of fast deaths shortens it, a long quiet history lengthens it. Taking
    min(prior, posterior) (the first version) could only ever shorten the scale, which is a
    one-sided ratchet the data could never relax. `mean_pressure` is the desk's measured mean
    mechanism pressure over the exposure; None means unmeasured and is taken as 1.0 (full
    pressure), which is said in the output, never assumed silently.
    """
    use = [r for r in records if r.in_mandate or include_out_of_mandate]
    d = sum(1 for r in use if r.cause in DECAY_CAUSES)
    t_at_risk = sum(r.exposure_days for r in use if r.detectable)
    t_blind = sum(r.exposure_days for r in use if not r.detectable)
    a = prior_events + d
    b = prior_events * prior_scale_days + t_at_risk
    posterior_scale = b / a
    rate = a / b
    mp_measured = mean_pressure is not None and math.isfinite(float(mean_pressure))
    mp = min(max(float(mean_pressure), 1e-6), 1.0) if mp_measured else 1.0
    scale = mp * posterior_scale
    counts: dict[str, int] = {}
    for r in use:
        key = r.cause or "censored_live"
        counts[key] = counts.get(key, 0) + 1
    status = "FITTED"
    direction = ("shorter" if scale < prior_scale_days - 1e-9 else
                 "longer" if scale > prior_scale_days + 1e-9 else "equal")
    prior_weight = 1.0 - t_at_risk / (t_at_risk + prior_events * prior_scale_days)
    thin = d < 3
    verdict_txt = (f"FITTED {direction} than the declared {prior_scale_days:g}d: using "
                   f"{scale:.1f}d (= mean pressure {mp:.3f}"
                   f"{'' if mp_measured else ' UNMEASURED, taken as full'} x posterior "
                   f"{posterior_scale:.1f}d)")
    return {
        "status": status, "scale_days": round(scale, 4), "direction": direction,
        "mean_pressure": round(mp, 6), "mean_pressure_measured": mp_measured,
        "prior_scale_days": prior_scale_days, "prior_events": prior_events,
        "posterior_scale_days": round(posterior_scale, 4),
        "posterior_shape": a, "posterior_rate_per_day": round(rate, 8),
        "n_decay_exits": d, "days_at_risk": round(t_at_risk, 2),
        "days_blind": round(t_blind, 2), "n_records": len(use),
        "exits_by_cause": dict(sorted(counts.items())),
        "prior_weight": round(prior_weight, 4),
        "base_rate_hazard": round(1.0 - math.exp(-rate * horizon_days), 6),
        "horizon_days": horizon_days, "include_out_of_mandate": include_out_of_mandate,
        "thin": thin,
        "why": (f"{d} decay exit(s) over {t_at_risk:.0f} detectable day(s) at risk "
                f"({t_blind:.0f} day(s) watched below {DETECT_MIN_N} trades, where no decay "
                f"retirement could fire, are not counted as survival); posterior scale "
                f"{posterior_scale:.1f}d against the {prior_scale_days:g}d prior -> {verdict_txt}"
                + (f". THIN: {d} decay exit(s), under three; the prior carries "
                   f"{prior_weight:.0%} of the weight" if thin else "")),
    }


def calibrate_from_history(root: Path = _ROOT) -> dict[str, Any]:
    """The primary (in-mandate) calibration, with the out-of-mandate fit beside it as sensitivity.

    The PRIMARY fit uses MT5/Fusion records only: the crypto-era clocks are a different universe
    and their exposure unit is assumed. They are fitted beside it so a reader sees how far the
    one real record of edges failing forward would move the scale.
    """
    records, notes = retirement_history(root)
    primary = calibrate_scale(records)
    primary["notes"] = notes
    primary["sensitivity_with_out_of_mandate"] = {
        k: v for k, v in calibrate_scale(records, include_out_of_mandate=True).items()
        if k in ("status", "scale_days", "posterior_scale_days", "n_decay_exits",
                 "days_at_risk", "base_rate_hazard", "why")}
    return primary
