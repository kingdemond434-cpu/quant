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
"""

from __future__ import annotations

import json
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

