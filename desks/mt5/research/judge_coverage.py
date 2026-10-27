"""JUDGE COVERAGE -- the judge tests 100% of what this desk mines, every hour, by BACKLOG.

    "the judge should test 100 percent of what this desk ever mines, every hour, 24/7, always"
    "all families should be hunted, all mechanisms, all unknowns, for maximum breadth -- not
     fixed like these six, every time"                                -- the principal, 2026-09-23

WHAT WAS MEASURED, AND WHY ORDER IS THE WHOLE PROBLEM. From 120,000 recent gate verdicts on the
trading box, 60 families were judged -- and the judged distribution had almost nothing to do with
the mined one. The docket's five largest populations were `cross_asset_residual` 55,190,
`overnight_drift` 26,721, `discovered` 24,052, `clock_transition` 20,081 and `execution_state`
13,660; the judged counts were `discovered` 22,009 (18% of the judge's whole recent capacity, on
a family BANNED from live capital, passing 0), then `orderflow_imbalance` 5,654, `vol_transition`
4,869, `liquidity_regime` 3,785, `session_range_breakout` 3,723. So the scarce judge re-tested a
handful of families every hour while the largest mined populations waited, and spent a fifth of
itself on cells that could never reach the book.

That is not a gauntlet defect. `external_gauntlet` is SEALED and takes the docket it is handed
under a bar budget, so **the order of the docket IS the selection**: a family at the tail is not
"lower priority", it is never judged at all. This organ therefore does its whole job at INTAKE,
upstream of the sealed judge, and changes nothing about how a cell is judged once it arrives.

COVERAGE, NOT ROTATION. Rotation asks "whose turn is it"; coverage asks "what has never been
answered". The quantity this organ drives to zero is the UNJUDGED BACKLOG, per family:

    backlog(family) = docket rows of that family carrying NO verdict in the gate ledger

Every family holding backlog is given a quota of the hour -- a FLOOR first, so a family of nine
cells is reached at all, and then THE REMAINDER GOES BY EXPECTED VALUE PER JUDGE-SECOND, not by
who mined hardest. The floor is the breadth mandate and never moves; the remainder is where the
return is, and spending it in proportion to backlog spends it on the desk's own output rather
than on what an hour of judge is worth. The ranking is
`p_optimistic x net-of-cost value if it passes x (1 + marginal breadth) / (seconds per cell x the
family's bar cost)`, every term measured by an organ that already exists -- the decayed Beta
posterior in `libs/research/research_priors` (which THIS organ also feeds, see `learn_priors`),
`reports/NET_EDGE.json`, `reports/EFFECTIVE_BREADTH.json` cluster occupancy, and the bar ratios
the sealed gauntlet budgets in. A family with no record yet ranks on the UPPER credible bound, so
it is explored rather than buried. The docket is then emitted as a weighted
interleave of the families, which makes EVERY PREFIX of it family-balanced: whatever slice of the
docket the gauntlet's budget actually reaches this hour, that slice contains every family with
backlog, at its quota. Nothing is truncated, nothing is deleted, nothing is deferred by this
organ -- the whole corpus still ships, in an order that spends the budget on coverage.

WHAT IT NEVER DOES (GROWTH_GOVERNANCE Rule 1). It removes no cell, lowers no bar, caps no book
and shrinks no budget. Reordering is the one intervention that cannot cost throughput: the same
rows reach the same judge under the same budget, and the only thing that changes is which
question the hour answers first. Mining stays unrestricted; a family's population may grow as
fast as the miners can grow it.

THE RATCHET, AND WHY IT IS ON THE CARRIED COHORT. `data/judge_backlog_ratchet.json` records, per
family, the backlog at each reading. Raw backlog RISES whenever miners outrun the judge, which is
mining working, not intake failing -- a fence on the raw number would punish the desk for mining
and would be switched off inside a week. So the ratcheted quantity is the CARRIED cohort: rows
that were already in the backlog at the previous reading and are still unjudged now. A cell
leaves that cohort exactly one way, by being judged, so the carried count can only fall, and any
family whose carried count fails to fall while it held backlog was starved -- which is the defect
this organ exists to make impossible. `scripts/check_judge_coverage.py` is that fence.

WHAT IT PUBLISHES -- `reports/JUDGE_COVERAGE.json`, per family:
`mined`, `queued` (this hour's realised quota in the head window), `judged_window`,
`unjudged`, `oldest_unjudged_age_h`, `carried`, `drained`, `window_h`, plus the full
`value_ranking` so the remainder's choice is inspectable and the fence can check it was followed.

AND THE OPPORTUNITY COST, which is what makes this ROI rather than bookkeeping: `value_at_risk`
(expected value sitting unjudged), `value_deferred` (the part this hour cannot reach),
`value_forgone_per_hour` and `capacity_short`. Those go to `research/judging_throughput.py`,
which is the organ that can answer them -- when the hour cannot reach the value at risk the box
raises workers and cadence. The answer to a valuable backlog is always MORE JUDGE, never a
smaller docket: nothing here throttles a miner to make a number look green.

THE BANNED FAMILY IS ALREADY OUT, AND THIS ORGAN DOES NOT RE-DO IT. `merge_hypotheses` routes
every row of a family banned from live capital (`mt5desk.live_policy.DEFAULT_BANNED_FAMILIES`)
into `data/hypotheses/study_bank.json` with the ban as the recorded reason, before the docket is
written; `external_gauntlet` sets banned cells aside again at its own door. Those rows are kept
forever and the miners keep producing them -- what stops is the SPENDING. This organ reads the
study bank only to report `mined` honestly: a family's mined population is what the desk mined,
not what it chose to judge.

NO FIXED FAMILY SET. The family universe here is `mt5desk.families.live_family_names()` -- the
union of every registered population the forward engine can actually resolve -- unioned with
whatever the docket and the ledger name. A family invented tomorrow is queued and judged the hour
it first appears in the docket, with no edit to this file.
"""
from __future__ import annotations

import argparse
import contextlib
import gc
import json
import math
import os
import sys
import threading
import time
import uuid
import weakref
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
HYP = BASE / "data" / "hypotheses"
DOCKET = HYP / "external_survivors.json"
STUDY_BANK = HYP / "study_bank.json"
GATE_LEDGER = HYP / "gate_verdict_ledger.jsonl"
REPORTS = BASE / "reports"
REPORT = REPORTS / "JUDGE_COVERAGE.json"
#: Written ONLY by a pass that stopped at its budget, and cleared by the next completed pass's
#: commit. It never touches REPORT, which keeps its own `at` and ages out under the fence's lease.
TIMEOUT_REPORT = REPORTS / "JUDGE_COVERAGE_TIMEOUT.json"
#: research/occupancy_map.py's hourly artifact: target cells and per-candidate orthogonality.
OCCUPANCY_REPORT = REPORTS / "OCCUPANCY_MAP.json"
RATCHET = BASE / "data" / "judge_backlog_ratchet.json"

#: The judging window every family is measured against: one hour, because the principal's order
#: is "every hour, 24/7". A family's OWN window widens from here by how long its own quota needs
#: to drain its own backlog -- a family of 55,190 cells is not starved for being large.
WINDOW_H = 1.0

#: The share of the hour handed out as an equal FLOOR before anything is proportional. A floor is
#: what makes a nine-cell family reachable at all; without it proportional allocation is a
#: winner-take-all rule that rediscovers the exact starvation this organ was built to end.
FLOOR_SHARE = 0.25
#: The share of the measured hour handed to TAPE families (`tape_families`, derived from code)
#: AFTER the breadth floor and BEFORE the value remainder. Bounded: the 25% floor is untouched
#: (every family keeps its floor) and the value walk keeps at least
#: 1 - FLOOR_SHARE - TAPE_PRIORITY_SHARE of the hour.
TAPE_PRIORITY_SHARE = 0.20

#: The judge's capacity is MEASURED from its own ledger (the busiest recent hour), never assumed
#: off a machine size -- CLAUDE.md's 8 GB/96 GB note is the standing lesson about inventing one.
#: The floor exists only so a cold tree with no ledger still produces a usable allocation.
CAPACITY_FLOOR = 500
CAPACITY_LOOKBACK_H = 168.0

#: Ledger rows whose downstream status begins with this were never actually judged -- the sweep's
#: build budget ran out before the cell was computed. Counting them as judged is precisely the
#: trap `external_gauntlet._stamped_but_unjudged` documents: it starved 1,544 cells forever.
NOT_JUDGED_PREFIX = "NOT_RUN"

#: NOT TESTABLE, NOT UNJUDGED (2026-10-07). A cell parked in the unrunnable bank for a reason
#: classed `not_testable` below WAS put through the judge and came back with fewer than the 60
#: daily observations CPCV and walk-forward need. It is not work the judge owes this hour, and
#: counting it as backlog forever is what made a box with 1.39M "unjudged" cells read GROWING while
#: the judge ran: the count could only ever rise. It is now its own named class -- `not_testable`
#: per family and per reason -- and it RE-ENTERS the backlog the moment `readmit_due` re-admits it
#: (its history grew enough to reach 60 observations, or READMIT_MAX_DAYS passed). Nothing is
#: deleted, no gate moves, and every cell stays in the docket and the bank.
#:
#: ONE TABLE, READ BY BOTH ORGANS (audit of PR #290, 2026-10-13). `judging_burndown` kept its own
#: set and the two disagreed in both directions: the burn-down booked drain for cells this organ
#: kept in the backlog, and this organ parked `no_series` and a BLANK reason as "never_fires" --
#: absence parked as scarcity. Every UNKNOWN reason either organ can see is mapped here to exactly
#: one class, and a reason not in the table is a DEFECT: only POSITIVE evidence of scarcity (a
#: series that was built and is short, or signals that never became trades on bars that exist)
#: may take a cell out of the backlog. `no_series`, an unnamed reason, the writer's generic
#: `observations_under_60_days` fallback and `no_terminal_gate_recorded` name no cause, so they
#: stay owed. Keys: the sealed judge's `classify_unknown` / `unknown_row_reason` vocabulary, then
#: the names `name_unknowns` derives from it. A test enumerates the table against both organs.
NOT_TESTABLE = "not_testable"
DEFECT = "defect"
UNKNOWN_REASON_CLASS: dict[str, str] = {
    # the sealed judge's own words (external_gauntlet.classify_unknown / unknown_row_reason)
    "no_signals": NOT_TESTABLE,
    "signals_no_trades": NOT_TESTABLE,
    "no_trades": NOT_TESTABLE,
    "too_rare": NOT_TESTABLE,
    "lockbox_consumed_history": NOT_TESTABLE,
    "short_history_after_cut": NOT_TESTABLE,
    "series_exception": DEFECT,
    "no_series": DEFECT,
    "observations_under_60_days": DEFECT,
    "no_terminal_gate_recorded": DEFECT,
    # the names `name_unknowns` gives a bank row
    "never_fires": NOT_TESTABLE,
    # a never-firing cell whose family PROVABLY emits nothing for want of a named input
    # (`research/fire_inputs.py`): parked like never_fires, re-admitted when the input appears
    "needs_data": NOT_TESTABLE,
    "missing_bars": DEFECT,
    "missing_identity_input": DEFECT,
    "unnamed": DEFECT,
}


def unknown_reason_class(reason: Any) -> str:
    """`not_testable` or `defect` for one UNKNOWN reason. Unlisted or blank is a defect."""
    return UNKNOWN_REASON_CLASS.get(str(reason or ""), DEFECT)


NOT_TESTABLE_REASONS: frozenset[str] = frozenset(
    r for r, c in UNKNOWN_REASON_CLASS.items() if c == NOT_TESTABLE)

#: THE BACKLOG'S UNIT, stamped on every published reading (the `unknown_share_basis` pattern).
#: `unjudged` stopped counting not-testable cells in PR #290; a prior reading on the old unit is
#: no baseline, because the difference between the two is the whole parked stock and would read
#: as one hour of drain -- DRAINING where the judge did nothing, and `judging_throughput` stands
#: workers down on a drain status. Across a basis change, drain is UNMEASURED for that pass.
BACKLOG_BASIS = "unjudged_excl_not_testable"


#: ONE READ OF THE SEALED JUDGE'S REPORT PER PASS (2026-10-14). `universal_gates_external.json`
#: is ~625 MB on the box and six readers inside one `build` each parsed it afresh. While `build`
#: runs this memo holds that ONE file, keyed on its size and mtime, and is dropped when the pass
#: ends -- so nothing stays resident between passes and no other file (the bank is rewritten
#: mid-pass) is ever served from it.
_GATES_MEMO: dict[tuple[str, int, int], Any] | None = None


def _read(path: Path) -> Any:
    memo = _GATES_MEMO
    key: tuple[str, int, int] | None = None
    if memo is not None and path.name == GATES_REPORT.name:
        try:
            st = path.stat()
            key = (str(path), st.st_mtime_ns, st.st_size)
        except OSError:
            key = None
        if key is not None and key in memo:
            return memo[key]
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        doc = None
    if memo is not None and key is not None:
        memo.clear()
        memo[key] = doc
    return doc


#: ONE PASS READS EACH INPUT ONCE (2026-10-21). On the box the hourly leg timed out three times
#: in one day against its 120 s budget, and JUDGE_COVERAGE.json then went stale. The cost was not
#: the arithmetic. The same inputs were parsed again and again in one pass: the 273 MB gate ledger
#: five times (and read whole twice), the 900,500-verdict gauntlet report seven times, and the
#: 530k-row unrunnable bank three times. Inside `build` (and `order_docket`) a PASS MEMO now holds
#: each parse, keyed by the file's path, mtime_ns and size, so a file that changes mid-pass is read
#: again. Outside a pass nothing is cached and every reader behaves as it always did. The memo
#: never outlives the pass, so a later pass in the same process (a test, or `order_docket` called
#: twice) re-reads everything from disk.
_PASS: dict[Any, Any] | None = None


@contextlib.contextmanager
def _pass_memo() -> Iterator[dict[Any, Any]]:
    """Open a pass memo, or join the one already open (`order_docket` -> `build`)."""
    global _PASS
    if _PASS is not None:
        yield _PASS
        return
    # THE CYCLE COLLECTOR IS PAUSED FOR THE PASS. A pass holds ~40M live containers (the 1.6M
    # docket rows and their params); every full collection walks all of them and finds nothing,
    # because a pass builds no reference cycles worth collecting. Measured at box scale: ~20 s of
    # a ~100 s pass. Reference counting still frees everything; the collector's state is restored.
    gc_was = gc.isenabled()
    gc.disable()
    _PASS = {}
    try:
        yield _PASS
    finally:
        _PASS = None
        if gc_was:
            gc.enable()


def _stat_key(path: Path) -> tuple[str, int, int, int, int] | None:
    """The memo's identity for a file. Inode and ctime are in it as well as mtime and size,
    because a same-size rewrite that preserves mtime (`scp -p`, `cp -p`, an rsync of the same
    length) was served stale within a pass on mtime and size alone (audit of c5390bc6a). A
    rename over the path changes the inode; an in-place rewrite changes ctime."""
    try:
        st = path.stat()
    except OSError:
        return None
    return (str(path), st.st_mtime_ns, st.st_size, st.st_ino, st.st_ctime_ns)


def _read_memo(path: Path) -> Any:
    """`_read`, served from the pass memo when one is open. Callers must not mutate the result."""
    if _PASS is None:
        return _read(path)
    staged = _PASS.get(("staged_json", str(path)))
    if staged is not None:
        return staged                  # this pass's own uncommitted write of the file
    key = _stat_key(path)
    if key is None:
        return _read(path)
    slot = ("json", *key)
    if slot not in _PASS:
        _PASS[slot] = _read(path)
    return _PASS[slot]


def _pass_value(name: str, fn: Any) -> Any:
    """A value computed once per pass (and on every call outside one)."""
    if _PASS is None:
        return fn()
    slot = ("value", name)
    if slot not in _PASS:
        _PASS[slot] = fn()
    return _PASS[slot]


#: THE GATE LEDGER IS READ THROUGH `ledger_index` (merge resolution, 2026-10-22). Coverage v2.3
#: gathered every ledger reader into one streamed scan per pass (`_LedgerScan`); judge-rate
#: replaced the same six readers with one incremental index caught up from a persisted byte
#: watermark (`research/gate_ledger_index.py`), so a pass costs what the judge wrote since the
#: last one rather than one full scan. The index answers every reader the scan did, so the scan
#: is gone; its naive-stamp rule (a stamp with no offset is UTC) is restated in the index.


#: ONE PASS PERSISTS AS ONE TRANSACTION (2026-10-21). A pass writes six things: the learned
#: priors, the unrunnable bank, the readmission log, the conversion handoff, the report (with the
#: k_eff order) and the ratchet. The ratchet carries the cursor (`priors_cursor`) that says which
#: verdicts the priors already hold, and the re-admissions (`readmitted_to_next`) that the next
#: reading's cohort is measured against. The priors and the bank used to be written mid-pass and
#: the ratchet at the end, so a pass killed in between (the cycle's timeout) left the posterior
#: taught and the cursor not advanced. The next pass then taught the same verdicts AGAIN, and the
#: bank and readmission log moved while the ratchet did not.
#:
#: Now every write inside a pass is STAGED beside its target (`<name>.jc-txn-<id>`) and committed
#: together: a manifest naming every (staged, final) pair is written atomically -- the COMMIT
#: POINT -- and the staged files are renamed over their targets. A kill before the manifest leaves
#: every target exactly as it was (the staged orphans are swept later). A kill after it is ROLLED
#: FORWARD by the next pass before it reads anything. Either way all six move together or none do.
TXN_TAG = ".jc-txn-"
TXN_MANIFEST_PREFIX = "judge_coverage_txn-"
#: A staged file older than this with no manifest naming it belongs to a killed pass.
TXN_ORPHAN_AGE_S = 3600.0
#: os.replace onto a file another process holds open fails on Windows; a reader holds it briefly.
TXN_REPLACE_TRIES = 25
#: A manifest recovery cannot parse is renamed with this suffix: kept, named, never applied.
TXN_GARBAGE_SUFFIX = ".garbage"
TXN_REPLACE_WAIT_S = 0.2


def _replace_retry(src: Path, dst: Path) -> None:
    """`src.replace(dst)`, retrying a PermissionError (a reader holding `dst` open on Windows).

    THE ONE DEFINITION (merge of v2.3 with dead families v4.4, 2026-10-21): both carried one,
    and the later def silently replaced the earlier for every caller. `Path.replace` IS
    `os.replace`; it is spelled through `Path` so v4.4's tests, which patch `Path.replace`,
    reach the sidecar and bank writes; v2.3's tests patch `_replace_retry` itself."""
    for attempt in range(TXN_REPLACE_TRIES):
        try:
            Path(src).replace(dst)
            return
        except PermissionError:
            if attempt == TXN_REPLACE_TRIES - 1:
                raise
            time.sleep(TXN_REPLACE_WAIT_S)


def _atomic_write_text(target: Path, text: str) -> None:
    """`target.write_text(text)` that a reader never sees half-written: the bytes go to a
    sibling and are renamed over the target (Windows-safe, see `_replace_retry`). Raises
    OSError as the plain write would, and leaves no sibling behind when it does."""
    tmp = target.with_name(f"{target.name}.tmp-{os.getpid()}")
    try:
        tmp.write_text(text, "utf-8")
        _replace_retry(tmp, target)
    except OSError:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise


def _fstat(path: Path) -> list[int] | None:
    """(mtime_ns, size) of a file, or None when it is absent: what a manifest records."""
    try:
        st = path.stat()
    except OSError:
        return None
    return [st.st_mtime_ns, st.st_size]


class TxnRecoveryRefused(RuntimeError):
    """A committed manifest that cannot be rolled forward without clobbering or half-applying.
    The manifest is KEPT; every pass refuses to read on until it is resolved by hand."""


def _apply_ops(ops: list[list[Any]], *, checked: bool = False) -> None:
    """Apply a committed manifest. Idempotent: a staged file already renamed is simply absent.

    `checked` is recovery's mode (audit of v2.1). Every op is classified BEFORE any is applied:
    PENDING (staged present, target as it was at the commit point), APPLIED (staged gone, target
    is the staged file renamed: same mtime and size), or a refusal -- the target changed since
    the commit point (another writer; rolling forward would clobber it) or the staged file is
    missing and the target is not it (rolling the rest forward would half-apply the pass). A
    refusal raises `TxnRecoveryRefused` and applies NOTHING. Two recoveries racing on one
    manifest meet a file the other already moved; that is suppressed, never raised.
    """
    if checked:
        bad: list[str] = []
        for entry in ops:
            op, final, staged = entry[0], entry[1], entry[2]
            pre = entry[3] if len(entry) > 3 else None
            post = entry[4] if len(entry) > 4 else None
            if op != "replace":
                continue
            dst_now = _fstat(Path(final))
            if Path(staged).exists():
                if len(entry) > 3 and dst_now != pre:
                    bad.append(f"{Path(final).name}: changed since the commit point")
            elif len(entry) > 4 and dst_now != post:
                bad.append(f"{Path(final).name}: staged file missing and target is not it")
        if bad:
            raise TxnRecoveryRefused("; ".join(bad))
    for entry in ops:
        op, final, staged = entry[0], entry[1], entry[2]
        dst = Path(final)
        if op == "replace":
            src = Path(staged)
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                with contextlib.suppress(FileNotFoundError):
                    _replace_retry(src, dst)
        elif op == "delete":
            with contextlib.suppress(FileNotFoundError):
                dst.unlink()


class _Txn:
    """The staged writes of one pass, committed together at `write` (or at the end of `build`)."""

    def __init__(self, manifest_dir: Path) -> None:
        self.id = f"{os.getpid()}-{time.time_ns()}"
        self.manifest_dir = manifest_dir
        self.ops: dict[str, list[Any]] = {}
        self.staged_dirs: list[Path] = []
        # THE BANK'S LOCK IS HELD UNTIL THIS PASS'S COMMIT (audit of the judge speed train
        # a5847f82a, R9 MUST-FIX). `update_unrunnable_bank` reads, changes and stages the bank and
        # the sidecar under `_outstanding_lock`; they land only at `commit`. Releasing the lock
        # in between let a second pass read the pre-commit bank and commit over this one -- the
        # probe lost this pass's park and its readmission line. So the lock is ADOPTED here and
        # released only once the staged writes have landed (`commit`) or been dropped
        # (`discard`). `guarded` names the writes made under each lock: if the lock was lost
        # before the commit they are dropped, as v4.4's "lost the lock mid-pass: write nothing".
        self.locks: dict[str, _SidecarLock] = {}
        self.guarded: dict[str, set[str]] = {}
        # Lines appended to a log AT THE COMMIT, under that log's lock (see `append_line`).
        self.appends: list[tuple[Path, str, Path, str, str]] = []
        # A txn dropped without commit or discard (a test's simulated kill, an unhandled path)
        # must not keep the lock for the 15-minute stale window: release it when it is collected
        # or at interpreter exit. A real kill takes the beat thread with it, and the stale rule
        # (OUTSTANDING_LOCK_STALE_S) frees the lock exactly as it did before.
        self._release_at_gc = weakref.finalize(self, _release_locks, self.locks)

    def adopt_lock(self, path: Path, lock: _SidecarLock) -> None:
        """Keep `lock` (held, guarding `path`) until this txn commits or discards."""
        self.locks[str(path)] = lock

    def held_lock(self, path: Path) -> _SidecarLock | None:
        return self.locks.get(str(path))

    def guard(self, path: Path, final: Path) -> None:
        """`final` was staged under the lock guarding `path`; it lands only while that holds."""
        self.guarded.setdefault(str(path), set()).add(str(final))

    def append_line(self, final: Path, line: str, *, lock_path: Path, at: str,
                    if_lost: str) -> None:
        """Append `line` to `final` AT THE COMMIT, under the lock guarding `lock_path`.

        The whole log is still staged (old bytes + the line) and renamed with the rest, which
        is idempotent under roll-forward (v2.3). What moved is WHEN the old bytes are read: at
        the commit, under the lock, so a second pass cannot read the log before this pass's
        line lands and then rename its own copy over it. `if_lost` replaces the line when the
        lock this pass held was lost before the commit (its bank update is then dropped)."""
        self.appends.append((final, line, lock_path, at, if_lost))

    def staged_path(self, final: Path) -> Path:
        return final.with_name(f"{final.name}{TXN_TAG}{self.id}")

    def put_staged(self, final: Path, staged: Path) -> None:
        self.ops[str(final)] = ["replace", str(final), str(staged)]

    def put_text(self, final: Path, text: str) -> None:
        """`final.write_text(text, "utf-8")`, staged. Raises OSError as the write would."""
        final.parent.mkdir(parents=True, exist_ok=True)
        staged = self.staged_path(final)
        staged.write_text(text, "utf-8")
        self.put_staged(final, staged)

    def delete(self, final: Path) -> None:
        self.ops[str(final)] = ["delete", str(final), None]

    def staged_dir(self, final_dir: Path) -> Path:
        d = final_dir / f"{TXN_TAG}{self.id}"
        self.staged_dirs.append(d)
        return d

    def manifest(self) -> Path:
        return self.manifest_dir / f"{TXN_MANIFEST_PREFIX}{self.id}.json"

    def write_manifest(self) -> Path:
        """THE COMMIT POINT: once this file exists, the pass's writes WILL all land.

        The writes guarded by a lock this pass lost are dropped first, and the pending log lines
        are staged onto the logs as they stand now, under their lock (R9), so the manifest
        names them like every other write."""
        self._drop_lost()
        self._land_appends()
        path = self.manifest()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        # Each replace records the target's (mtime_ns, size) at the commit point and the staged
        # file's, so recovery can tell "not yet moved", "moved" and "someone else wrote it".
        ops = [[op, final, staged, _fstat(Path(final)), _fstat(Path(staged))]
               if op == "replace" else [op, final, staged]
               for op, final, staged in self.ops.values()]
        tmp.write_text(json.dumps({"id": self.id, "ops": ops}), "utf-8")
        _replace_retry(tmp, path)
        return path

    def commit(self) -> None:
        try:
            if self.ops or self.appends:
                manifest = self.write_manifest()
                _apply_ops(list(self.ops.values()))
                # A concurrent recovery may have rolled this manifest forward and removed it.
                with contextlib.suppress(FileNotFoundError):
                    manifest.unlink()
            self._drop_dirs()
        finally:
            _release_locks(self.locks)

    def discard(self) -> None:
        try:
            for op, _final, staged in self.ops.values():
                if op == "replace" and staged:
                    with contextlib.suppress(OSError):
                        Path(staged).unlink()
            self.ops.clear()
            self.appends.clear()
            self._drop_dirs()
        finally:
            _release_locks(self.locks)

    def _drop_lost(self) -> None:
        """A lock this pass adopted and no longer owns: its guarded writes do not land."""
        for key, lk in list(self.locks.items()):
            if lk.owned():
                continue
            for final in self.guarded.pop(key, set()):
                entry = self.ops.pop(final, None)
                if entry and entry[0] == "replace" and entry[2]:
                    with contextlib.suppress(OSError):
                        Path(entry[2]).unlink()
            self.appends = [(f, (alt if str(lp) == key else ln), lp, at, alt)
                            for f, ln, lp, at, alt in self.appends]
            print(f"judge coverage: lost {lk.path.name} before the commit; the bank and sidecar "
                  f"this pass staged are dropped (re-asked next pass)", file=sys.stderr,
                  flush=True)
            self.locks.pop(key, None)
            lk.release()               # unlinks only a file that still carries our token

    def _land_appends(self) -> None:
        """Stage each pending log line onto the log AS IT IS NOW, under the log's lock.

        A pass that adopted the lock (it held the bank) already holds it. One that did not (its
        bank update was LOCKED) tries once, without waiting, so the commit is never delayed: if
        another pass holds it, the LOCKED line is not written rather than risk renaming a stale
        copy over the holder's line. A LOCKED line is no reading -- the burn-down neither counts
        it nor takes freshness from it -- so nothing measured is lost."""
        import shutil
        pending, self.appends = self.appends, []
        for final, line, lock_path, at, _alt in pending:
            if self.held_lock(lock_path) is None:
                lk = _SidecarLock(lock_path, at)
                if not lk.acquire(wait_s=0.0):
                    print(f"judge coverage: {lk.path.name} held by another pass at the commit; "
                          f"this pass's LOCKED line to {final.name} is not written",
                          file=sys.stderr, flush=True)
                    continue
                self.adopt_lock(lock_path, lk)
            dest = self.staged_path(final)
            try:
                final.parent.mkdir(parents=True, exist_ok=True)
                if final.exists():
                    shutil.copyfile(final, dest)
                with dest.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except OSError:
                with contextlib.suppress(OSError):
                    dest.unlink(missing_ok=True)
                continue           # a failed log write is caught by the log's staleness rule
            self.put_staged(final, dest)

    def _drop_dirs(self) -> None:
        import shutil
        for d in self.staged_dirs:
            shutil.rmtree(d, ignore_errors=True)
        self.staged_dirs = []


def _release_locks(locks: dict[str, Any]) -> None:
    """Release every lock a txn adopted (commit, discard, or the txn's collection)."""
    for key in list(locks):
        lk = locks.pop(key, None)
        if lk is not None and lk.held:
            lk.release()


def _txn_dirs(ratchet: Path | None = None) -> list[Path]:
    """Every directory a pass stages into, for recovery and the orphan sweep."""
    dirs = [(ratchet or RATCHET).parent, RATCHET.parent, UNRUNNABLE_BANK.parent,
            CONVERSION_HANDOFF.parent, REPORT.parent]
    with contextlib.suppress(Exception):
        root = str(BASE.parents[1])
        if root not in sys.path:
            sys.path.insert(0, root)
        from libs.research import research_priors
        dirs.append(Path(research_priors.STATE_DIR))
    out: list[Path] = []
    for d in dirs:
        if d not in out:
            out.append(d)
    return out


def recover_transactions(ratchet: Path | None = None) -> int:
    """Roll forward every committed manifest a killed pass left, then sweep staged orphans.

    Runs before a pass reads anything, so a pass never reads a half-moved state. Returns how
    many manifests were rolled forward. A manifest that cannot be applied raises: reading on
    from a half-moved state would be the inconsistency this exists to prevent.
    """
    rolled = 0
    dirs = _txn_dirs(ratchet)
    for d in dirs:
        for m in sorted(d.glob(f"{TXN_MANIFEST_PREFIX}*.json")) if d.is_dir() else []:
            try:
                doc = json.loads(m.read_text("utf-8"))
            except FileNotFoundError:
                continue                         # a concurrent recovery finished it
            except (OSError, ValueError):
                doc = None
            if not (isinstance(doc, dict) and isinstance(doc.get("ops"), list)
                    and all(isinstance(o, list) and len(o) >= 3 for o in doc["ops"])):
                # NOT A COMMIT ANYONE CAN READ: set aside under a name that says so, never
                # deleted without trace and never applied.
                aside = m.with_name(m.name + TXN_GARBAGE_SUFFIX)
                with contextlib.suppress(OSError):
                    _replace_retry(m, aside)
                print(f"judge coverage: unreadable transaction manifest set aside as "
                      f"{aside.name}", file=sys.stderr, flush=True)
                continue
            try:
                _apply_ops(doc["ops"], checked=True)
            except TxnRecoveryRefused as exc:
                raise TxnRecoveryRefused(f"{m.name} kept, nothing applied: {exc}") from None
            rolled += 1
            with contextlib.suppress(FileNotFoundError):
                m.unlink()
    # Staged files a kept or set-aside manifest names are evidence, not orphans.
    named: set[str] = set()
    for d in dirs:
        for m in d.glob(f"{TXN_MANIFEST_PREFIX}*") if d.is_dir() else []:
            with contextlib.suppress(OSError, ValueError, TypeError, AttributeError):
                for o in json.loads(m.read_text("utf-8")).get("ops") or []:
                    if isinstance(o, list) and len(o) >= 3 and o[2]:
                        named.add(str(o[2]))
    cutoff = time.time() - TXN_ORPHAN_AGE_S
    for d in dirs:
        for p in d.glob(f"*{TXN_TAG}*") if d.is_dir() else []:
            if str(p) in named or any(n.startswith(str(p) + os.sep) for n in named):
                continue
            with contextlib.suppress(OSError):
                if p.stat().st_mtime >= cutoff:
                    continue                     # possibly a live pass's; swept next time
                if p.is_dir():
                    import shutil
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    p.unlink()
    return rolled


def _txn_current() -> _Txn | None:
    return _PASS.get(("txn",)) if _PASS is not None else None


class JudgeCoverageTimeout(Exception):
    """The pass reached its stop before committing: nothing it staged is written."""

    def __init__(self, phase: str, elapsed_s: float) -> None:
        super().__init__(f"budget reached at {phase} after {elapsed_s:.1f}s")
        self.phase = phase
        self.elapsed_s = elapsed_s


def _check_budget(phase: str) -> None:
    """Stop the pass, uncommitted, when its deadline has passed (see `main`)."""
    if _PASS is None:
        return
    deadline = _PASS.get(("deadline",))
    if deadline is not None and time.monotonic() > deadline[1]:
        raise JudgeCoverageTimeout(phase, time.monotonic() - deadline[0])


def _ts(raw: object) -> datetime | None:
    """Every stamp this organ reads, parsed one way. A stamp with no offset is UTC -- the desk's
    writers stamp UTC -- never this machine's local time, which shifted naive stamps by the
    box's offset (audit of v2.1; every reader since v2.3: capacity, judged index, sustained
    rate, the bank's ages, the docket's first_seen, the ratchet, the priors)."""
    txt = str(raw or "").strip()
    if not txt:
        return None
    try:
        t = datetime.fromisoformat(txt.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (t.replace(tzinfo=UTC) if t.tzinfo is None else t).astimezone(UTC)


#: THE LEDGER IS READ ONCE, INCREMENTALLY (2026-10-14, `research/gate_ledger_index.py`). Six
#: readers here each re-parsed the whole append-only gate ledger on every pass; they now answer
#: from one index caught up from a persisted byte watermark, so a pass costs what the judge wrote
#: since the last one. The desk's own ledger persists its index under reports/ (gitignored, a
#: cache); any other path (a test's ledger) is indexed in-process only.
LEDGER_INDEX_STATE = REPORTS / "judge_ledger_index.pkl"
_DEFAULT_LEDGER = GATE_LEDGER
_LEDGER_INDEXES: dict[str, Any] = {}
#: The monotonic deadline the ledger catch-up honours while a budgeted `build` runs (`main`).
_LEDGER_DEADLINE: list[float] = []


def ledger_index(path: Path | None = None) -> Any:
    """The gate ledger's index, caught up to EOF (or to the pass's ledger deadline)."""
    desk = str(BASE)
    if desk not in sys.path:
        sys.path.insert(0, desk)
    from research.gate_ledger_index import LedgerIndex

    p = Path(path or GATE_LEDGER)
    persist = p == _DEFAULT_LEDGER and GATE_LEDGER == _DEFAULT_LEDGER
    key = str(p)
    idx = _LEDGER_INDEXES.get(key)
    if idx is None:
        idx = LedgerIndex.load(p, LEDGER_INDEX_STATE if persist else None)
        _LEDGER_INDEXES[key] = idx
    done = idx.catch_up(deadline=_LEDGER_DEADLINE[0] if _LEDGER_DEADLINE else None)
    if persist and (done.get("consumed_bytes") or done.get("rebuilt")):
        idx.save(LEDGER_INDEX_STATE)
    return idx


def _tail_lines(path: Path, limit: int) -> list[str]:
    """`open(path).readlines()[-limit:]`, read from the END of the file: O(limit), not O(file).

    Same text semantics as the text-mode read it replaces (UTF-8, errors replaced, universal
    newlines), so `learn_priors` sees exactly the rows it saw before.
    """
    if limit <= 0:
        return []
    with path.open("rb") as fh:
        fh.seek(0, 2)
        pos, data = fh.tell(), b""
        # Enough bytes for `limit` complete lines plus the one cut at the front.
        while pos > 0 and max(data.count(b"\n"), data.count(b"\r")) <= limit:
            step = min(pos, 1 << 20)
            pos -= step
            fh.seek(pos)
            data = fh.read(step) + data
    if pos > 0:
        cut = data.find(b"\n")
        if cut < 0:
            cut = data.find(b"\r")
        data = data[cut + 1:] if cut >= 0 else b""
    text = data.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    out = [ln + "\n" for ln in lines[:-1]]
    if lines[-1]:
        out.append(lines[-1])
    return out[-limit:]


def _cell_id(row: dict[str, Any]) -> str | None:
    """The gauntlet's OWN identity function, imported, never re-implemented.

    Two implementations of an identity are two identities, and the whole measurement here turns
    on matching a docket row to the verdict the sealed judge recorded for it.
    """
    fn = _cell_id_fn()
    if fn is None:
        return None
    try:
        return str(fn(row))
    except Exception:
        return None


def _cell_id_fn() -> Any:
    """`frontier_identity.docket_cell_id`, imported once per pass instead of once per row."""
    def _load() -> Any:
        try:
            desk = str(BASE)
            if desk not in sys.path:
                sys.path.insert(0, desk)
            from research.frontier_identity import docket_cell_id
        except Exception:
            return None
        return docket_cell_id
    return _pass_value("cell_id_fn", _load)


def live_families() -> frozenset[str]:
    """The live family registry, read once per pass (see `_live_families`)."""
    return frozenset(_pass_value("live_families", _live_families))


def _live_families() -> frozenset[str]:
    """Every family the desk can actually resolve -- the registry's live set, never a literal.

    An unreadable registry returns EMPTY and the caller then falls back to the docket's own
    families: losing this import must never narrow what gets judged (L1.28a).
    """
    try:
        desk = str(BASE)
        if desk not in sys.path:
            sys.path.insert(0, desk)
        from mt5desk.families import live_family_names
        return frozenset(live_family_names())
    except Exception:
        return frozenset()


def banned_from_capital() -> frozenset[str]:
    """The live-capital ban list, read once per pass (see `_banned_from_capital`)."""
    return frozenset(_pass_value("banned_from_capital", _banned_from_capital))


def _banned_from_capital() -> frozenset[str]:
    """Families the desk has forbidden from live capital, read from the policy that enforces it.

    `merge_hypotheses` already routes these rows OUT of the judging docket and into the study
    bank, and `external_gauntlet` sets them aside again at its own door. This is the same answer
    at the allocator: a family that cannot reach the book is given no quota, so no hour of the
    scarce judge is allocated to an outcome the desk has already refused. The rows are still
    counted as MINED -- mining is unrestricted and stays so -- and they still ship in the docket,
    behind every family that can actually repay a gate-second.
    """
    try:
        desk = str(BASE)
        if desk not in sys.path:
            sys.path.insert(0, desk)
        from research.merge_hypotheses import live_banned_families
        return frozenset(live_banned_families())
    except Exception:
        return frozenset()


def judged_index(path: Path | None = None, *, now: datetime | None = None,
                 window_h: float = WINDOW_H) -> tuple[set[str], dict[str, int], dict[str, int]]:
    """(cells carrying a real verdict, judged-per-family all-time, judged-per-family in window).

    A row is JUDGED only when the ledger recorded a real terminal gate or a successful pass.
    `UNKNOWN` is the sealed evaluator's unmeasured path, even when it carries passed=False.
    Neither that path nor a `NOT_RUN_*` deferral clears the backlog or earns judge capacity.
    """
    # ONE INCREMENTAL INDEX, not a full parse per call (2026-10-14, `ledger_index`): the same
    # rule, folded once per appended row. Returns copies, so a caller can never edit the index.
    cutoff = (now or datetime.now(tz=UTC)).timestamp() - window_h * 3600.0
    idx = ledger_index(path)
    return set(idx.judged_cells), dict(idx.judged_total), idx.window_judged(cutoff)


def not_testable_index(bank: dict[str, dict[str, Any]] | None = None
                       ) -> dict[str, str]:
    """cell id -> reason, for every cell the unrunnable bank holds as NOT TESTABLE right now.

    Read from the bank as it stands BEFORE this pass parks or re-admits anything, so a cell
    re-admitted this pass is backlog again on the next reading -- never held out longer than the
    bank's own re-admission rule says. An unreadable bank reads as empty: every cell is then
    counted as backlog, exactly as before this class existed."""
    rows = unrunnable_bank() if bank is None else bank
    return {str(c): str(r.get("reason")) for c, r in rows.items()
            if isinstance(r, dict) and r.get("reason") in NOT_TESTABLE_REASONS}


def measured_capacity(judged_total: dict[str, int], ledger: Path | None = None,
                      *, now: datetime | None = None) -> int:
    """Cells the judge demonstrably rules on in ONE hour -- its busiest recent hour, measured.

    Measured and never assumed: the allocation below divides THIS number, so inventing it off a
    machine size would size the hour for a machine the code is not on.
    """
    best = 0
    cutoff = (now or datetime.now(tz=UTC)).timestamp() - CAPACITY_LOOKBACK_H * 3600.0
    per_hour = ledger_index(ledger).judged_per_hour(cutoff)
    if per_hour:
        best = max(per_hour.values())
    return max(best, CAPACITY_FLOOR, sum(judged_total.values()) // 24)


def sustained_rate(ledger: Path | None = None, *, now: datetime | None = None) -> dict[str, Any]:
    """Cells the judge ACTUALLY rules on per hour, averaged over 24 h and 7 d. The drain meter.

    WHY THE PEAK HOUR CANNOT BE THE DRAIN RATE (measured 2026-09-30 on the box). The sweep stamps
    every verdict of one pass with ONE `at`, so a single large pass lands in a single hour and
    `measured_capacity` reads that hour as the judge's hourly speed. JUDGE_COVERAGE then published
    `hours_to_drain 25.1` on 1,398,253 unjudged cells while the same box's JUDGING_RATE counted
    ~220 verdicts/hour -- a true drain of ~265 days, and in fact no drain at all, because the desk
    creates ~8,300 cells a day against ~5,300 verdicts. The peak stays the ALLOCATION size (how far
    down the docket one pass can reach); the drain is the average, and it is net of creation.
    """
    t = now or datetime.now(tz=UTC)
    cuts = {"24h": t.timestamp() - 24 * 3600.0, "7d": t.timestamp() - 168 * 3600.0}
    counts = {"24h": 0, "7d": 0}
    # THE SAME WINDOW'S UNKNOWN ROWS, counted beside it (2026-09-30). The ledger holds only the
    # verdicts `run_gauntlet` emitted -- judged cells and its unmeasured branch, never a NOT_RUN
    # row -- so UNKNOWN / rows here is the share of cells that REACHED the judge and got no
    # ruling. That is what the 7-day "43%" was; it is published here so it is never again set
    # against a per-sweep figure computed over a different denominator (see `unknown_breakdown`).
    unknown = {"24h": 0, "7d": 0}
    if not Path(ledger or GATE_LEDGER).is_file():
        return {"status": "UNMEASURED", "why": "gate ledger unreadable"}
    idx = ledger_index(ledger)
    for w, cut in cuts.items():
        counts[w], unknown[w], _ = idx.window_rows(cut)
    return {"status": "MEASURED", "counts": counts,
            "per_hour_24h": round(counts["24h"] / 24.0, 3),
            "per_hour_7d": round(counts["7d"] / 168.0, 3),
            "unknown_counts": unknown,
            # None, never 0.0, on an empty window: no verdicts is UNMEASURED (L1.28a).
            "unknown_share_24h": (round(unknown["24h"] / counts["24h"], 6)
                                  if counts["24h"] else None),
            "unknown_share_7d": (round(unknown["7d"] / counts["7d"], 6)
                                 if counts["7d"] else None),
            # The drain rate above counts an UNKNOWN as judged; this is the rate of RULINGS.
            "named_per_hour_24h": round((counts["24h"] - unknown["24h"]) / 24.0, 3)}


#: THE JUDGING RATE THE DESK OWES (principal, 2026-10-14 06:21Z: "judging speed and quantity per
#: day should be maximised using every way possible to maximum so it judges even 100-200k cells a
#: day"). The floor is the middle of that range. `scripts/check_judge_coverage.py` fails the box
#: below it; nothing here throttles a miner or moves a gate to reach it.
JUDGING_RATE_TARGET_PER_DAY = 150_000


def judging_rate(ledger: Path | None = None, *, now: datetime | None = None) -> dict[str, Any]:
    """VERDICTS PER DAY, from the judge's own verdict ledger: rolling 24 h and the hourly series.

    A verdict is `judged_index`'s unit -- a ledger row with a named terminal gate or a pass. The
    sealed writer appends one row per CHANGED verdict, so a re-judge that lands on the same gate
    is not counted again: this is the rate of new rulings, which is the rate the backlog drains
    at. UNKNOWN rows (the judge's unmeasured path) are counted beside it, never in it.
    An absent ledger is UNMEASURED, never zero. An index the pass's deadline stopped short of
    EOF is PARTIAL: its count is a lower bound, and the unread bytes are named.
    """
    t = now or datetime.now(tz=UTC)
    p = Path(ledger or GATE_LEDGER)
    out: dict[str, Any] = {"target_per_day": JUDGING_RATE_TARGET_PER_DAY,
                           "basis": ("gate_verdict_ledger.jsonl rows with a named terminal gate "
                                     "or a pass, stamped in the last 24 h (one row per changed "
                                     "verdict; NOT_RUN and UNKNOWN excluded)")}
    if not p.is_file():
        out.update(status="UNMEASURED", why=f"{p.name} absent: verdicts/day is UNMEASURED")
        return out
    idx = ledger_index(ledger)
    now_ts = t.timestamp()
    rows, unknown, judged = idx.window_rows(now_ts - 86400.0, now_ts)
    first = (now_ts // 3600.0) * 3600.0 - 23 * 3600.0
    series = [{"hour": datetime.fromtimestamp(h, UTC).strftime("%Y-%m-%dT%H"),
               "verdicts": j, "unknown": u, "rows": a}
              for h, a, u, j in idx.hourly(first, 24)]
    catch = idx.last_catch_up or {}
    status = "MEASURED" if idx.complete else "PARTIAL"
    out.update(
        status=status,
        verdicts_24h=judged, unknown_24h=unknown, rows_24h=rows,
        verdicts_per_day=judged,
        verdicts_per_hour_24h=round(judged / 24.0, 3),
        needed_per_hour=round(JUDGING_RATE_TARGET_PER_DAY / 24.0, 1),
        meets_target=judged >= JUDGING_RATE_TARGET_PER_DAY,
        shortfall_per_day=max(0, JUDGING_RATE_TARGET_PER_DAY - judged),
        share_of_target=round(judged / float(JUDGING_RATE_TARGET_PER_DAY), 6),
        last_verdict_at=(datetime.fromtimestamp(idx.max_ts, UTC).isoformat(timespec="seconds")
                         if idx.max_ts else None),
        per_hour=series,
        ledger_index={"complete": idx.complete, "behind_bytes": idx.behind_bytes,
                      "offset": idx.offset, "rows_indexed": idx.rows_read,
                      "consumed_bytes": catch.get("consumed_bytes"),
                      "rebuilt": catch.get("rebuilt"), "seconds": catch.get("seconds")})
    if status == "PARTIAL":
        out["why"] = (f"the pass's deadline stopped the ledger index {idx.behind_bytes} bytes "
                      "short of EOF: the count is a lower bound and the next pass resumes there")
    return out


def drain(backlog_now: int, per_hour: float | None, *, prior_backlog: int | None,
          prior_at: datetime | None, now: datetime, parked: int = 0,
          rebased: str | None = None) -> dict[str, Any]:
    """Hours to drain on the SUSTAINED rate, and whether the backlog is falling at all.

    The backlog's own movement between two readings is the net of judging and creation, so it
    needs no separate creation meter: growing means no finite ETA exists, and saying so is the
    measurement (a large finite number would be a lie of a different size).
    """
    out: dict[str, Any] = {"sustained_per_hour": per_hour}
    growth = None
    # PARKING IS NOT DRAIN: a cell moved to the not-testable class since the prior reading left
    # the count without a ruling, so it is added back before the movement is read. Without this
    # every new parking reads as judging, and an overstated drain flips GROWING to DRAINING --
    # the status `judging_throughput` raises workers on.
    if prior_backlog is not None and prior_at is not None:
        hours = (now.timestamp() - prior_at.timestamp()) / 3600.0
        if hours >= 0.25:
            growth = (backlog_now + max(0, int(parked)) - prior_backlog) / hours
    out["backlog_growth_per_hour"] = round(growth, 3) if growth is not None else None
    out["parked_since_prior"] = max(0, int(parked))
    if not per_hour or per_hour <= 0:
        out.update(status="UNMEASURED", hours=None,
                   why="no judged verdicts in the last 24 h: the drain rate is unmeasured")
        return out
    out["hours_at_zero_creation"] = round(backlog_now / per_hour, 1)
    if rebased:
        out.update(status="UNMEASURED", hours=None, rebased=True, why=rebased)
    elif backlog_now == 0:
        out.update(status="DRAINED", hours=0.0)
    elif growth is not None and growth >= 0:
        out.update(status="GROWING", hours=None,
                   net_per_day=round(growth * 24.0, 1),
                   why="the backlog rose since the last reading: creation outpaces the judge")
    elif growth is not None:
        out.update(status="DRAINING", hours=round(backlog_now / -growth, 1))
    else:
        out.update(status="DRAINING_GROSS", hours=out["hours_at_zero_creation"],
                   why="no prior reading: ETA ignores creation")
    return out


#: Judge cost is BUDGETED IN BARS, not in cells -- the sealed gauntlet says so in its own
#: docstring -- so one M5 cell costs about twelve H1 cells of the same hour. These are the bar
#: ratios against H1, which is what makes "per judge-second" a real denominator rather than a
#: constant that cancels out of the ranking.
_BAR_COST = {"M1": 60.0, "M5": 12.0, "M15": 4.0, "M30": 2.0, "H1": 1.0, "H4": 0.25, "D1": 0.042}


def _tf_of(row: dict[str, Any]) -> str:
    params = row.get("params") or {}
    tf = str(params.get("timeframe") or row.get("timeframe") or "H1").upper()
    return tf if tf in _BAR_COST else "H1"


def realised_pass_rates(path: Path | None = None) -> dict[str, dict[str, float]]:
    """WHAT EACH FAMILY ACTUALLY DID AT THE JUDGE, counted from the gate ledger itself.

    THE MEASUREMENT THAT MADE THIS NECESSARY (2026-09-23). The ranking below spends
    `p_optimistic`, and every family in the published ranking carried `prior_n: 0`,
    `prior_status: PRIOR`, `p_optimistic: 1.0` -- a flat pass probability, so the aim was being
    set by net value and breadth alone while 3,368 verdicts across 27 families sat in
    `gate_verdict_ledger.jsonl` saying exactly which families pass. `learn_priors` below feeds the
    stored posterior, but its cursor advances past rows it could not charge, so a verdict lost
    that way is lost for good. THE LEDGER IS THE EVIDENCE AND IT IS RE-READABLE: counting it here
    every pass cannot be made stale by a cursor, and the two numbers are published side by side so
    a disagreement between them is visible rather than silent.

    Returned per family: `judged`, `passed`, `pass_rate`, and the Beta(1+passed, 1+failed)
    posterior this evidence supports -- mean and 95% upper bound. A family with no verdicts gets
    Beta(1,1): mean 0.5, upper bound 1.0, which is how an unjudged family stays EXPLORED rather
    than being ranked below a family measured to fail.
    """
    if not Path(path or GATE_LEDGER).is_file():
        return {}
    # The index folds this exact rule once per appended row (`gate_ledger_index`), instead of the
    # whole-file `readlines()` this used to do on every pass.
    idx = ledger_index(path)
    judged: dict[str, int] = dict(idx.judged_total)
    passed: dict[str, int] = dict(idx.passed_total)
    out: dict[str, dict[str, float]] = {}
    for fam, n in judged.items():
        k = passed.get(fam, 0)
        a, b = 1.0 + k, 1.0 + (n - k)
        mean = a / (a + b)
        sd = math.sqrt(max(mean * (1.0 - mean) / (a + b + 1.0), 0.0))
        out[fam] = {"judged": float(n), "passed": float(k),
                    "pass_rate": (k / n) if n else 0.0,
                    "mean": mean, "hi": min(1.0, mean + 1.96 * sd)}
    return out


def family_priors(families: list[str],
                  realised: dict[str, dict[str, float]] | None = None
                  ) -> dict[str, dict[str, float]]:
    """The desk's OWN learned pass probability per family, with its optimism kept.

    `libs/research/research_priors.prior_for("family", fam)` is a decayed Beta posterior whose
    unseen state is Beta(1,1) -- mean 0.5, never zero. The ranking below uses the UPPER credible
    bound, not the mean, so a family with no record yet is EXPLORED rather than buried: optimism
    under uncertainty is the only rule that can discover that a new family is good. A family with
    a long record has a tight interval and is ranked on what it actually did.

    AND IT NOW USES THE EVIDENCE THAT IS ACTUALLY THERE. When the ledger holds MORE verdicts for a
    family than the stored posterior was ever taught -- which was true of every family on the desk
    the day this was written -- the realised counts are the better-informed posterior and they are
    the one the ranking spends. The stored number is still published beside it, so the gap between
    what the desk learned and what it recorded is inspectable rather than silently papered over.
    Optimism is unchanged in both directions: an unjudged family still ranks on 1.0.
    """
    out: dict[str, dict[str, float]] = {}
    seen = realised if realised is not None else realised_pass_rates()
    try:
        root = str(BASE.parents[1])
        if root not in sys.path:
            sys.path.insert(0, root)
        from libs.research.research_priors import prior_for
    except Exception:
        def prior_for(_dim: str, _key: str) -> Any:                  # type: ignore[misc]
            raise RuntimeError("research_priors unavailable")
    _staged_dir = _PASS.get(("priors_dir",)) if _PASS is not None else None
    for fam in families:
        row = {"p": 0.5, "p_optimistic": 1.0, "n": 0.0, "status": 0.0, "source": 0.0}
        try:
            pr = (prior_for("family", fam) if _staged_dir is None
                  else prior_for("family", fam, state_dir=_staged_dir))
            row = {"p": float(pr.mean), "p_optimistic": float(pr.interval()[1]),
                   "n": float(pr.n), "status": 1.0 if pr.status == "POSTERIOR" else 0.0,
                   "source": 0.0}
        except Exception:
            pass
        r = seen.get(fam)
        if r and float(r["judged"]) > float(row["n"]):
            row = {"p": float(r["mean"]), "p_optimistic": float(r["hi"]),
                   "n": float(r["judged"]), "status": 1.0, "source": 1.0,
                   "stored_n": float(row["n"]), "stored_p": float(row["p"])}
        out[fam] = row
    return out


#: How far past the pass's own clock a verdict's `at` may sit and still be a reading. Beyond
#: it the stamp is read as UNMEASURED: one future-dated row taught would carry the cursor to
#: its date and freeze learning until the wall clock got there. It is the desk's one clock-skew
#: tolerance (`dsr_inputs.FUTURE_SKEW_S`, 300 s), imported rather than restated (audit of v2.1).
if str(BASE.parents[1]) not in sys.path:
    sys.path.insert(0, str(BASE.parents[1]))
from libs.research.dsr_inputs import FUTURE_SKEW_S as PRIORS_FUTURE_SKEW_S  # noqa: E402


def learn_priors(ledger: Path | None = None, *, since: str = "",
                 limit: int = 20_000, state_dir: Path | None = None,
                 now: datetime | None = None) -> dict[str, Any]:
    """FEED THE PRIOR THE RANKING SPENDS. Every new gate verdict updates its family's posterior.

    THE LOOP WAS OPEN AND THE RANKING WOULD HAVE BEEN FLAT FOREVER. Measured when this was
    written: `data/research_priors/beta.json` held ZERO rows under the `family` dimension, so
    `prior_for("family", ...)` returned Beta(1,1) for every family on the desk -- an allocator
    ranking by a learned pass probability that nothing was teaching. Eight organs call
    `record_outcome` and not one of them passes a family, so the dimension existed and was never
    fed.

    Each verdict is classified by `research_priors.classify` from its terminal gate, because WHY
    a family failed is the part that matters: one killed by costs is not one with no edge, and
    the two should move the next hour's allocation opposite ways. `since` is the previous
    reading's high-water stamp, so a verdict is charged exactly once however often this runs --
    double-counting a ledger is how a posterior becomes confident about nothing.
    """
    out: dict[str, Any] = {"recorded": 0, "families": 0, "cursor": since, "status": "OK"}
    try:
        root = str(BASE.parents[1])
        if root not in sys.path:
            sys.path.insert(0, root)
        from libs.research.research_priors import load, record_outcome, save
    except Exception as exc:
        out.update(status="UNMEASURED", why=f"{type(exc).__name__}: {exc}")
        return out
    try:
        # The last `limit` lines, read from the END (`_tail_lines`): the same rows the old
        # whole-file `readlines()[-limit:]` kept, without reading the other 800k first.
        lines = _tail_lines(Path(ledger or GATE_LEDGER), limit)
    except OSError as exc:
        out.update(status="UNMEASURED", why=f"{type(exc).__name__}: {exc}")
        return out
    _clock = now or datetime.now(tz=UTC)
    _horizon = _clock.timestamp() + PRIORS_FUTURE_SKEW_S
    _since_ts = _ts(since) if since else None
    if since and _since_ts is not None and _since_ts.timestamp() > _horizon:
        # The same freeze, already stored: a cursor past this clock skips every verdict until
        # the clock reaches it. Named and kept, exactly as a cursor that is not a timestamp.
        out.update(status="UNMEASURED",
                   why=f"stored priors_cursor is in the future: {since[:80]!r}; kept as it is")
        return out
    if since and _since_ts is None:
        # A STORED CURSOR THAT IS NOT A TIMESTAMP FREEZES LEARNING SILENTLY (audit of
        # c5390bc6a): "garbage" sorts above every ISO stamp, so `at <= since` skipped every
        # verdict from then on and the pass still read OK. It is not a reading of where the
        # ledger was taught to, so nothing is taught against it -- teaching from the start
        # would double-count every verdict already in the posterior -- and the cursor is kept
        # as it is, named here, for whoever repairs it.
        out.update(status="UNMEASURED",
                   why=f"stored priors_cursor is not a timestamp: {since[:80]!r}; kept as it is")
        return out
    state = load(state_dir)
    taught = state.get("beta") if isinstance(state, dict) else None
    taught_fams = set((taught or {}).get("family") or {}) if isinstance(taught, dict) else set()
    untaught: set[str] = set()
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            fam_seen = str(json.loads(ln).get("family") or "")
        except (ValueError, AttributeError):
            continue
        if fam_seen and fam_seen not in taught_fams:
            untaught.add(fam_seen)
    out["backfilled_families"] = len(untaught)
    seen_fams: set[str] = set()
    high, high_ts = since, _since_ts
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        at = str(row.get("at") or "")
        fam = str(row.get("family") or "")
        if not fam or not at:
            continue
        # THE CURSOR SKIPS ROWS THE POSTERIOR NEVER GOT (measured 2026-09-23). `high` only
        # advances on a row that recorded, but a LATER row that records carries the cursor past
        # every row before it -- so one failure loses the whole block behind it, permanently. The
        # ledger held 3,368 verdicts across 27 families and the stored posterior held 2 families
        # and 9 updates, with the cursor already at the ledger's last stamp: unrecoverable by
        # `since` alone. A family with NO stored row has demonstrably never been taught, so it is
        # backfilled whatever the cursor says. It gains a row on the first such pass and is
        # cursor-governed from then on, so this cannot double-count a family twice.
        # PARSED, NOT LEXICAL (audit of v2.1): a `+05:30` cursor compared as a string skipped
        # about 5.5 h of later UTC rows. Equal-format stamps order the same either way.
        _at_ts = _ts(at)
        if (_since_ts is not None and _at_ts is not None and _at_ts <= _since_ts
                and fam not in untaught):
            continue
        if str(row.get("downstream_status") or "").startswith(NOT_JUDGED_PREFIX):
            continue
        if _at_ts is None or _at_ts.timestamp() > _horizon:
            # A VERDICT WHOSE `at` IS NOT A TIMESTAMP IS READ AS UNMEASURED, and never taught:
            # taught, it would either become the cursor (a garbage stamp sorts above every ISO
            # one and freezes learning) or be re-taught on every pass the cursor cannot pass it.
            # A stamp more than PRIORS_FUTURE_SKEW_S past this pass's clock is the same freeze.
            out["unmeasured_at"] = int(out.get("unmeasured_at") or 0) + 1
            continue
        passed = row.get("passed")
        survived = passed is True or str(passed).lower() == "true"
        gate = str(row.get("terminal_gate") or "")
        # AN UNMEASURED CELL IS NOT EVIDENCE AGAINST THE FAMILY, and charging it as one is the
        # exact mistake `record_outcome` documents: "charging it as a Beta failure would teach the
        # allocator that the thing does not work when what happened is that nobody looked."
        # `UNKNOWN` is the sealed judge's unmeasured path (see `unknown_breakdown`), so it is
        # recorded in the Dirichlet as `unmeasured` and moves no pass probability at all.
        outcome = ("survived" if survived
                   else ("unmeasured" if gate in ("", "UNKNOWN") else "REJECTED"))
        try:
            record_outcome(outcome, family=fam,
                           rejection_reason=gate, failure_class=gate, state=state,
                           state_dir=state_dir, persist=False)
        except Exception:
            continue
        seen_fams.add(fam)
        out["recorded"] = int(out["recorded"]) + 1
        if high_ts is None or _at_ts > high_ts:
            high, high_ts = at, _at_ts
    if out["recorded"]:
        try:
            txn = _txn_current()
            if txn is None:
                save(state, state_dir)
            else:
                # STAGED with the ratchet that carries this pass's cursor (see `_Txn`): the
                # posterior and the cursor land together or not at all, so a killed pass can
                # never leave verdicts taught that the next pass will teach again.
                from libs.research import research_priors as _rp
                final_dir = Path(state_dir or _rp.STATE_DIR)
                staged_dir = txn.staged_dir(final_dir)
                save(state, staged_dir)
                for _name in ("beta.json", "dirichlet.json"):
                    txn.put_staged(final_dir / _name, staged_dir / _name)
                if state_dir is None and _PASS is not None:
                    # The rest of this pass reads the posterior it just taught, as it did when
                    # the save landed in place (`family_priors`).
                    _PASS[("priors_dir",)] = staged_dir
        except Exception as exc:                                         # pragma: no cover
            out.update(status="UNMEASURED", why=f"save failed: {type(exc).__name__}: {exc}")
    out["families"] = len(seen_fams)
    out["cursor"] = high
    return out


#: The sealed judge's own artifact, read (never written) for the census below.
GATES_REPORT = REPORTS / "universal_gates_external.json"


#: What `unknown_share` is divided by. A share read under another basis is not comparable, so
#: the ratchet treats a basis change as a first reading (UNMEASURED) rather than a rise or a fall.
UNKNOWN_SHARE_BASIS = "judged_verdicts"


def unknown_breakdown(path: Path | None = None) -> dict[str, Any]:
    """WHAT `terminal_gate: UNKNOWN` ACTUALLY IS -- measured, not assumed.

    MEASURED ON THE BOX across 60,000 verdicts (2026-09-22T22:46 -> 2026-09-23T05:42): UNKNOWN
    44,432 (74%), in_sample_screen 13,915 (23%), deflated_sharpe 1,641 (2.7%), PASSED 4. So the
    multiple-testing charge everyone blames kills under 3%, and three quarters of the judge
    returned no named gate at all.

    IT IS NOT A MISSING GATE AND IT IS NOT MISSING BARS. `external_gauntlet._append_gate_ledger`
    writes `str(v.get("terminal_gate") or ("PASSED" if v.get("passed") else "UNKNOWN"))`, and
    exactly one verdict path omits `terminal_gate`: the UNMEASURED branch, which emits
    `{"passed": False, "unmeasured": True, "stages": {"observations": ...}}` for a cell whose
    signals produced fewer than the 60 daily observations CPCV needs. UNKNOWN IS THAT BRANCH.

    MEASURED ON THIS TREE, 748 unmeasured of 6,787 verdicts: 615 of them (82%) have days == 0 --
    the cell fired NOT ONCE -- and EVERY ONE of those symbols has its H1 parquet present, so the
    cause is not absent bars and nothing needs converting. They are specs that never fire,
    concentrated in four families (session_range_breakout 336, carry 140, discovered 79,
    event_reaction 56). The remaining 133 fire between 1 and 59 days: too rare to judge, which is
    a fact about the SEARCH that proposed them and not evidence against any edge.

    So the route is UPSTREAM, to whatever mints these specs, and this census is what it needs:
    per family, how many of its cells never fired at all. Nothing here removes a cell -- a
    never-firing spec on a short history can fire on a longer one, and an order is not a ban.
    """
    doc = _read_memo(path or GATES_REPORT)
    out: dict[str, Any] = {"status": "UNMEASURED", "source": str(path or GATES_REPORT)}
    verdicts = (doc or {}).get("verdicts") if isinstance(doc, dict) else None
    if not isinstance(verdicts, list) or not verdicts:
        out["why"] = "the sealed judge has written no verdicts here"
        return out
    never: dict[str, int] = {}
    too_rare: dict[str, int] = {}
    n_unmeasured = 0
    for v in verdicts:
        if not isinstance(v, dict) or not v.get("unmeasured"):
            continue
        n_unmeasured += 1
        fam = str(v.get("family") or "")
        if int(v.get("days") or 0) == 0:
            never[fam] = never.get(fam, 0) + 1
        else:
            too_rare[fam] = too_rare.get(fam, 0) + 1
    named = name_unknowns(path)
    by_reason: dict[str, int] = {}
    for row in named.values():
        r = str(row.get("reason") or "unnamed")
        by_reason[r] = by_reason.get(r, 0) + 1
    total = len(verdicts)
    # THE DENOMINATOR IS THE CELLS THAT REACHED THE JUDGE (2026-09-30). This divided by EVERY row
    # in the report, and the report also carries the cells the sweep never built -- NOT_RUN_*
    # (data missing, build failed, modifier refused, budget deferred, gate-1 prior rejections),
    # `passed: null`, none of which ever reached the gates. Measured on the box's noon sweep:
    # 20,247 of 29,466 rows were NOT_RUN, so the published 9.55% UNKNOWN (2,814 cells) was really
    # >=30.5% of the ~9,219 cells actually judged -- and it FELL whenever more cells failed to
    # build, which is the ratchet rewarding the wrong thing. The gate ledger has only ever held
    # `run_gauntlet`'s own verdicts, so its 7-day 43% (53,460 of 124,342) was the right basis all
    # along; this now uses the same one, and publishes the old ratio beside it by name.
    judged = sum(1 for v in verdicts if isinstance(v, dict) and (
        v.get("unmeasured") or (v.get("passed") is not None and not str(
            v.get("downstream_status") or "").startswith(NOT_JUDGED_PREFIX))))
    out.update({
        "by_reason": by_reason,
        "named_cells": len(named),
        "status": "OK",
        "verdicts": total,
        "judged_verdicts": judged,
        "not_run_rows": total - judged,
        "unknown_total": n_unmeasured,
        "unknown_share": (round(n_unmeasured / judged, 6) if judged else None),
        "unknown_share_basis": UNKNOWN_SHARE_BASIS,
        "unknown_share_of_all_rows": round(n_unmeasured / max(total, 1), 6),
        "causes": {
            "never_fires_days_0": {
                "cells": sum(never.values()),
                "by_family": dict(sorted(never.items(), key=lambda kv: -kv[1])),
                "route": ("the spec never fired on bars that ARE present -- upstream, to the "
                          "compiler that mints it; nothing to convert, no bars are missing"),
            },
            "too_rare_1_to_59_days": {
                "cells": sum(too_rare.values()),
                "by_family": dict(sorted(too_rare.items(), key=lambda kv: -kv[1])[:20]),
                "route": ("fires too rarely for CPCV's 60 observations -- a fact about the "
                          "search, recorded as `unmeasured` in the priors so it moves no pass "
                          "probability (nobody looked; that is not evidence against the edge)"),
            },
        },
        "why_unknown": ("external_gauntlet emits no `terminal_gate` on its UNMEASURED branch and "
                        "_append_gate_ledger defaults that to UNKNOWN; the judge is sealed, so "
                        "this is named here rather than fixed there"),
    })
    return out


#: The bank of cells the judge PROVED it cannot rule on, with the named reason and the bar file
#: size at the moment they were parked. Kept forever, never deleted, and re-admitted the moment
#: the symbol's bars grow -- a spec that never fired on a short history can fire on a longer one,
#: so this is a filter with a measured re-open condition, never a ban.
UNRUNNABLE_BANK = HYP / "unrunnable_specs.json"
UNIVERSE = BASE / "data" / "universe"


def _bar_bytes(sym: str, tf: str = "H1") -> int:
    """The symbol's bar file size on `tf` -- the cheap monotone proxy for "the history grew"."""
    try:
        return (UNIVERSE / f"{sym}_{tf or 'H1'}.parquet").stat().st_size
    except OSError:
        return 0


def _bar_bytes_pass(sym: str, tf: str = "H1") -> int:
    """`_bar_bytes`, measured once per chart per pass for the namers (one stat per verdict was
    ~50k stats a pass). Outside a pass it is `_bar_bytes`. `readmit_due` keeps its own snapshot."""
    if _PASS is None:
        return _bar_bytes(sym, tf)
    sizes = _PASS.setdefault(("bar_bytes",), {})
    k = (sym, tf)
    if k not in sizes:
        sizes[k] = _bar_bytes(sym, tf)
    return int(sizes[k])


#: THE OTHER HALF OF THE PERMANENT CELL LEAK (2026-09-30). A cell the judge could not BUILD --
#: its bars absent on its own chart, or its signal construction failing -- is recorded
#: `passed: None, downstream_status: NOT_RUN_*`, which `judged_index` rightly refuses to call
#: judged. So it stayed "never judged", which is the FIRST key of the docket order, and came back
#: at the head of every sweep to fail again: measured on the box, 20,247 of 29,466 pre-warm
#: builds failed on build/data in one sweep. Those cells are parked here with a named reason and
#: re-admitted on the one event that could change the outcome -- their bars appearing or growing,
#: or, for a construction failure, the passage of BUILD_FAILED_RETRY_DAYS (code ships in between).
#: Deferrals for budget (NOT_RUN_BUILD_BUDGET_DEFERRED) are work not yet done and are never parked.
PARKED_NOT_RUN = {"NOT_RUN_DATA_MISSING": "data_missing",
                  "NOT_RUN_BUILD_FAILED": "build_failed"}
BUILD_FAILED_RETRY_DAYS = 7.0


def _cost_fields_unmeasured(path: Path | None = None) -> dict[str, Any]:
    """Every registry symbol whose spread, swap or commission field is zero, missing or stale.

    A certificate or forward clock priced on one of these reads UNMEASURED and is queued for
    repricing (`research/entry_hour_cost.py` owns the rule and the staleness thresholds); this
    publishes the count and the symbol list by field so the queue is visible every hour. An
    unreadable registry is UNMEASURED by name, never an empty (clean) list.
    """
    try:
        reg = json.loads((path or (UNIVERSE / "universe.json")).read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": f"UNMEASURED: registry unreadable ({type(exc).__name__})",
                "n_symbols": None, "by_field": {}}
    try:
        from research.entry_hour_cost import unmeasured_fields
    except ImportError:  # pragma: no cover - path variant
        from desks.mt5.research.entry_hour_cost import (  # type: ignore[import-not-found,no-redef]
            unmeasured_fields,
        )
    block: dict[str, Any] = {"status": "MEASURED", **unmeasured_fields(reg)}
    # THE ENTRY-HOUR MISPRICING SWEEP: symbols whose flat charged scalar (registry, or the
    # surface's stored pooled value) is more than 2x off an hour's own charge, by hour.
    try:
        from research.entry_hour_cost import charged_vs_hour, load_surface
    except ImportError:  # pragma: no cover - path variant
        from desks.mt5.research.entry_hour_cost import (  # type: ignore[import-not-found,no-redef]
            charged_vs_hour,
            load_surface,
        )
    sweep = charged_vs_hour(load_surface(), reg)
    block["hour_mispriced"] = {k: v for k, v in sweep.items() if k != "by_symbol"}
    return block


def _prewarm_share(path: Path | None = None) -> float | None:
    """The share of the last sweep's pre-warm builds that failed on build or data."""
    doc = _read_memo(path or GATES_REPORT)
    pw = (doc or {}).get("prewarm") if isinstance(doc, dict) else None
    if not isinstance(pw, dict):
        return None
    sub = int(pw.get("submitted") or 0)
    fails = pw.get("failures") if isinstance(pw.get("failures"), dict) else {}
    bad = sum(int(v or 0) for k, v in fails.items()
              if str(k) in ("NOT_RUN_DATA_MISSING", "NOT_RUN_BUILD_FAILED", "FAIL_3X", "ERROR",
                            "SAVE_FAILED"))
    return round(bad / sub, 6) if sub else None


def name_not_run(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Every cell the judge could not build, with its named reason and the bars it needs."""
    doc = _read_memo(path or GATES_REPORT)
    out: dict[str, dict[str, Any]] = {}
    verdicts = (doc or {}).get("verdicts") if isinstance(doc, dict) else None
    if not isinstance(verdicts, list):
        return out
    for v in verdicts:
        if not isinstance(v, dict):
            continue
        reason = PARKED_NOT_RUN.get(str(v.get("downstream_status") or ""))
        cell = str(v.get("cell") or "")
        if not reason or not cell:
            continue
        sym = str(v.get("sym") or "")
        tf = _tf_of(v)
        why = str(v.get("why") or "")
        for cand in ("M1", "M5", "M15", "M30", "H4", "D1"):
            if f" {cand} parquet" in f" {why}":
                tf = cand
        out[cell] = {"reason": reason, "sym": sym, "family": v.get("family"), "tf": tf,
                     "days": 0, "bar_bytes": _bar_bytes_pass(sym, tf), "why": why[:200],
                     "route": ("bars absent on the cell's own chart: re-admitted the moment "
                               "they appear" if reason == "data_missing" else
                               "signal construction failed: re-admitted on bar growth or after "
                               f"{BUILD_FAILED_RETRY_DAYS:.0f} days of code changes")}
    return out


#: One probe per (family, symbol) per process pass: both probed families' answers depend on
#: the symbol alone (`fire_inputs.probe`). Cleared by `_fire_probe_reset` at each pass start.
_FIRE_MEMO: dict[tuple[str, str], dict[str, Any]] = {}


def _fire_probe_reset() -> None:
    _FIRE_MEMO.clear()


def _fire_probe(sym: str, family: str) -> dict[str, Any]:
    """`research.fire_inputs.probe`, or UNMEASURED when it cannot be imported (fail open)."""
    try:
        try:
            from fire_inputs import probe
        except ImportError:                                    # pragma: no cover - import context
            from research.fire_inputs import probe  # type: ignore[no-redef]
        return probe(sym, family, memo=_FIRE_MEMO)
    except Exception as exc:                                   # never costs the pass
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {str(exc)[:120]}"}


def name_unknowns(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """EVERY UNKNOWN GETS A NAMED REASON. The class stops existing as a category.

    An unnamed terminal state is the defect, whatever the cause turns out to be -- so this joins
    the sealed judge's own verdict rows to a reason per CELL, and the residue that cannot be
    joined is named too (`no_verdict_row`) rather than left inside a bucket. A new cause appears
    as its own name the day it appears.

    One pass names once: `build` reads this three times (directly, through `unknown_breakdown`
    and through `judging_failures`), so inside a pass memo the table is computed once per
    version of the report and each caller gets its own copy of the outer mapping.
    """
    key = _stat_key(path or GATES_REPORT) if _PASS is not None else None
    if _PASS is None or key is None:
        return _name_unknowns(path)
    slot = ("named_unknowns", *key)
    if slot not in _PASS:
        _PASS[slot] = _name_unknowns(path)
    return dict(_PASS[slot])


def _name_unknowns(path: Path | None = None) -> dict[str, dict[str, Any]]:
    doc = _read_memo(path or GATES_REPORT)
    out: dict[str, dict[str, Any]] = {}
    verdicts = (doc or {}).get("verdicts") if isinstance(doc, dict) else None
    if not isinstance(verdicts, list):
        return out
    for v in verdicts:
        if not isinstance(v, dict) or not v.get("unmeasured"):
            continue
        cell = str(v.get("cell") or "")
        if not cell:
            continue
        sym = str(v.get("sym") or "")
        fam = str(v.get("family") or "")
        days = int(v.get("days") or 0)
        why = str((((v.get("stages") or {}).get("observations")) or {}).get("why") or "")
        # THE CELL'S OWN CHART, not H1: an M15 cell with no M15 file read as "bars present" off
        # its H1 sibling and was parked as a spec that never fires.
        tf = _tf_of(v)
        _head = cell.split(".", 1)[0]
        if "@" in _head and _head.rsplit("@", 1)[1].upper() in _BAR_COST:
            tf = _head.rsplit("@", 1)[1].upper()          # `cell_id` writes `<sym>@<TF>.`
        bars = _bar_bytes_pass(sym, tf)
        # WHAT THE WRITER SAYS, WHEN IT SAYS IT (patch unknown_verdict_named): the judge names the
        # cause it saw -- an exception while building the series, a history the lockbox carve
        # consumed, signals that never became trades -- and that beats any inference made here.
        declared = str(v.get("unknown_reason") or "")
        params = v.get("params") if isinstance(v.get("params"), dict) else None
        need = REQUIRED_INPUT_KEY.get(fam)
        if declared == "series_exception":
            reason, route = "series_exception", (
                "the backtest raised while building this cell's daily series: a code defect, "
                f"re-admitted after {BUILD_FAILED_RETRY_DAYS:.0f} days like a build failure")
        elif params is not None and need and not params.get(need):
            reason, route = "missing_identity_input", (
                f"{fam} trades against a second instrument and this cell names no {need}, so it "
                "built with no input and fired nowhere. Its twin with the input named is minted "
                "by discovery_compiler.complete_inputs; this one is kept, never deleted")
        elif declared == "lockbox_consumed_history":
            reason, route = "lockbox_consumed_history", (
                "the cell fires, but its chart's history begins after the campaign lockbox cut, "
                "so the carve left under 60 development days: re-admitted as history grows")
        elif declared == "short_history_after_cut":
            reason, route = "short_history_after_cut", (
                "the cell traded, but on under 60 days, all of them after the lockbox cut, so the "
                "carve left no development window: re-admitted as history grows")
        elif days == 0 and bars == 0:
            reason, route = "missing_bars", ("no H1 bar file for this symbol: the conversion "
                                             "organ's bar supply (research/local_converter.py) "
                                             "owns it")
        elif unknown_reason_class(declared) != NOT_TESTABLE:
            # NO POSITIVE EVIDENCE OF SCARCITY (audit of PR #290). `no_series` (no daily series
            # was built at all), a blank reason and the writer's generic fallbacks name no cause,
            # and this branch used to fall through to "never_fires" -- absence parked as scarcity,
            # out of the backlog. It is named for what it is, classed a DEFECT, and stays owed.
            reason = declared if declared in UNKNOWN_REASON_CLASS else "unnamed"
            route = ("the judge named no scarcity for this cell (no series built, or no reason "
                     "given): a defect the desk owes a fix for, kept in the backlog and re-asked "
                     f"after {BUILD_FAILED_RETRY_DAYS:.0f} days like a build failure")
        elif days == 0 and (_fire := _fire_probe(sym, fam)).get("status") == "NEEDS_DATA":
            # NAMED FOR THE INPUT IT LACKS (2026-10-20). The family's own guard returns [] on the
            # inputs the judge hands it, on any bars, so this is not scarcity of signals: it is a
            # missing input, handed to the converter by name and re-admitted when it appears.
            reason, route = "needs_data", (
                f"the family cannot fire without {_fire.get('missing_input')}: "
                f"{_fire.get('why')}. Re-admitted the moment that input is present")
            out[cell] = {"reason": reason, "route": route, "sym": sym, "family": fam,
                         "tf": tf, "days": days, "bar_bytes": bars, "why": why[:200],
                         "missing_input": _fire.get("missing_input"),
                         "input_stamp": _fire.get("stamp"),
                         **({"detail": declared} if declared else {})}
            continue
        elif days == 0:
            reason, route = "never_fires", ("the spec produced not one daily observation on bars "
                                            "that ARE present: an unrunnable spec, filtered at "
                                            "intake so it never reaches the docket again until "
                                            "this symbol's history grows")
        else:
            reason, route = "too_rare", (f"fires on {days} days, under the 60 CPCV needs: a fact "
                                         "about the search, re-admitted when the history grows")
        out[cell] = {"reason": reason, "route": route, "sym": sym, "family": v.get("family"),
                     "tf": tf, "days": days, "bar_bytes": bars, "why": why[:200],
                     **({"detail": declared} if declared else {})}
    return out


#: The key that names a peer/driver/factor/triangle family's other instrument. Mirrors
#: `discovery_compiler.PEER_KEY_BY_FAMILY` + `FACTOR_FAMILIES` + the first key of
#: `LEG_FAMILIES` (a test pins them together).
REQUIRED_INPUT_KEY: dict[str, str] = {"relative_value": "peer_symbol",
                                      "correlation_regime": "peer_symbol",
                                      "lead_lag": "driver_symbol",
                                      "cross_asset_residual": "factor_symbols",
                                      "pca_residual": "factor_symbols",
                                      "triangle": "leg_b_symbol"}


def unrunnable_bank(path: Path | None = None) -> dict[str, dict[str, Any]]:
    # A fresh outer mapping every call: `update_unrunnable_bank` pops and assigns into its copy,
    # and the rows themselves are only ever replaced, never edited, so the parse can be shared.
    doc = _read_memo(path or UNRUNNABLE_BANK)
    if not isinstance(doc, dict):
        return {}
    return {str(k): v for k, v in doc.items() if isinstance(v, dict)}


#: HOW MUCH THE HISTORY MUST GROW BEFORE A PARKED CELL IS WORTH THE JUDGE AGAIN.
#:
#: THE DEFECT THIS REPLACES (2026-09-30). Re-admission fired on `bar_bytes > parked bar_bytes`,
#: and the bar refresh rewrites every H1 parquet many times a day (238 of 239 symbols fresh inside
#: 48 h on the box), so every parked cell was re-admitted within hours and judged again -- a spec
#: that fired on 0 of ~2,100 days does not reach 60 because one more hour of bars arrived. The box
#: meanwhile read 43% of a week's verdicts as UNKNOWN (53,460 of 124,342). The judge was paying
#: for the same never-firing cells over and over; the ledger's cell|key de-duplication hid the
#: repeats from the verdict count, not from the compute.
#:
#: The rule now: a never-firing cell returns when its history has grown by a quarter; a too-rare
#: cell that fired on d days returns when the history has grown by the factor that would carry d
#: to the 60 observations CPCV needs (capped, so nothing waits longer than tripling); and every
#: parked cell returns after READMIT_MAX_DAYS regardless, so a new regime is always re-asked.
READMIT_GROWTH = 1.25
READMIT_GROWTH_CAP = 3.0
READMIT_MAX_DAYS = 90.0
CPCV_MIN_DAYS = 60


def readmit_due(row: dict[str, Any], *, now: datetime | None = None,
                bar_sizes: dict[tuple[str, str], int] | None = None,
                memo: bool = False) -> bool:
    """True when a parked cell's history has grown enough, or it has waited long enough.

    `memo=True` (the bank update passes it when it can fingerprint the build code): a row
    `memoised` under a code identity (`_memoised`) is NOT re-admitted by the blind
    BUILD_FAILED_RETRY_DAYS timer -- a deterministic failure re-run on unchanged code and
    unchanged bars fails again. Its code changing is handled by the canary in
    `update_unrunnable_bank`; bar growth and READMIT_MAX_DAYS below still re-admit it.
    """
    parked_bytes = int(row.get("bar_bytes") or 0)
    key = (str(row.get("sym") or ""), str(row.get("tf") or "H1"))
    # A pass measures each chart once. Never retain this snapshot across passes: new
    # bars must re-admit every eligible sibling on the next reading.
    if bar_sizes is None:
        bars = _bar_bytes(*key)
    else:
        if key not in bar_sizes:
            bar_sizes[key] = _bar_bytes(*key)
        bars = bar_sizes[key]
    if row.get("reason") == "needs_data":
        # THE INPUT IS THE BINDING CAUSE: the family returns [] on any bars without it, so bar
        # growth cannot change the outcome. Back the moment the probe stops answering NEEDS_DATA
        # (the input appeared, or the probe can no longer say: fail open toward judging), and
        # after READMIT_MAX_DAYS regardless, like every parked cell.
        if _fire_probe(str(row.get("sym") or ""), str(row.get("family") or "")).get(
                "status") != "NEEDS_DATA":
            return True
        _pa = _ts(row.get("parked_at"))
        _tn = now or datetime.now(tz=UTC)
        return (_pa is not None
                and (_tn.timestamp() - _pa.timestamp()) / 86400.0 >= READMIT_MAX_DAYS)
    if parked_bytes <= 0:
        return bars > 0
    if row.get("reason") in ("build_failed", "series_exception", "no_series", "unnamed",
                             "observations_under_60_days", "no_terminal_gate_recorded") \
            and not (memo and _memoised(row)):
        _at = _ts(row.get("parked_at"))
        _t = now or datetime.now(tz=UTC)
        if _at is not None and (_t.timestamp() - _at.timestamp()) / 86400.0 \
                >= BUILD_FAILED_RETRY_DAYS:
            return True
    days = int(row.get("days") or 0)
    need = READMIT_GROWTH if days <= 0 else min(
        READMIT_GROWTH_CAP, max(READMIT_GROWTH, CPCV_MIN_DAYS / float(days)))
    if bars >= parked_bytes * need:
        return True
    parked_at = _ts(row.get("parked_at"))
    t = now or datetime.now(tz=UTC)
    return (parked_at is not None
            and (t.timestamp() - parked_at.timestamp()) / 86400.0 >= READMIT_MAX_DAYS)


#: MEMOISED BUILD FAILURES (2026-10-14). A cell whose build failed DETERMINISTICALLY is re-run by
#: the judge only when an input that could change the outcome changed: its bars (the growth rule
#: above, and READMIT_MAX_DAYS) or the code that builds it. Before this, every `build_failed` /
#: `no_series` / `series_exception` row came back after BUILD_FAILED_RETRY_DAYS whatever had
#: changed -- the raw COT families alone parked ~26k cells on one TypeError and re-paid the build
#: for all of them weekly, on code that had not moved (floor_starvation_2026-10-14.md).
#:
#: THE KEY IS (cell, input fingerprint). The data half is the bar file size already on the row;
#: the code half is `build_code_identity()` -- the sealed judge's own replay identity (the code
#: its series cache is keyed on) plus the other modules `build_cell` imports. A row parked under
#: identity A is `_memoised`; when the identity moves to B, ONE CANARY per failure signature
#: (family, symbol, chart, reason, the error text) is re-admitted, not the whole bank. If the
#: canary fails the same way under B, its siblings are re-stamped B and stay parked; if it is
#: judged, or fails differently, every sibling is re-admitted. A canary with no evidence after
#: BUILD_FAILED_RETRY_DAYS releases its siblings -- never worse than the old timer.
#:
#: WHICH CODE A REPORT RAN IS NOT WRITTEN IN IT, so the memo only trusts what it can bound: an
#: identity is CERTAIN once MEMO_CERTAIN_GENERATIONS distinct sealed reports have been seen
#: under it and MEMO_CERTAIN_H hours have passed (a sweep that spanned the release cannot be the
#: third report since). A row parked under an uncertain identity keeps the old weekly timer, and
#: canary evidence is read only from a report generation that began after the canary was set.
MEMO_REASONS = frozenset({"build_failed", "no_series", "series_exception"})
MEMO_CERTAIN_GENERATIONS = 3
MEMO_CERTAIN_H = 6.0
CANARIES_PER_SIGNATURE = 1
MEMO_STATE_NAME = "unrunnable_memo.json"
#: Modules `external_gauntlet.build_cell` imports beyond the sealed replay identity's own list.
BUILD_PATH_EXTRA = ("desks/mt5/mt5desk/family_inputs.py", "desks/mt5/mt5desk/family_call.py",
                    "desks/mt5/mt5desk/universe_registry.py", "desks/mt5/research/edge_search.py",
                    "desks/mt5/research/cost_surface.py", "desks/mt5/research/h1_source.py")


def sealed_replay_identity(root: Path | None = None) -> str | None:
    """`external_gauntlet._replay_code_identity()`, restated (a drift test pins the two equal).

    The sealed judge imports pandas and sizes a worker pool at import; this organ must not, so the
    file list and the digest are restated here verbatim. None when any file is unreadable.
    """
    import hashlib

    base = root or BASE.parent.parent
    desk = base / "desks" / "mt5"
    paths = [desk / "scripts" / "external_gauntlet.py",
             desk / "research" / "orthogonal_sweep.py"]
    paths.extend(desk / "mt5desk" / name for name in
                 ("engine.py", "cell_modifiers.py", "data.py", "legacy_family_inputs.py"))
    paths.extend((desk / "mt5desk").glob("famil*.py"))
    digest = hashlib.sha256()
    try:
        for path in sorted(set(paths)):
            name = path.relative_to(base).as_posix()
            digest.update(name.encode("utf-8") + b"\0"
                          + path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    except (OSError, ValueError):
        return None
    return digest.hexdigest()


def build_code_identity(root: Path | None = None) -> str | None:
    """The build path's code fingerprint: the sealed replay identity plus BUILD_PATH_EXTRA."""
    import hashlib

    base = root or BASE.parent.parent
    sealed = sealed_replay_identity(base)
    if sealed is None:
        return None
    digest = hashlib.sha256(sealed.encode("ascii"))
    for rel in BUILD_PATH_EXTRA:
        try:
            body = (base / rel).read_bytes().replace(b"\r\n", b"\n")
        except OSError:
            body = b"\0ABSENT"
        digest.update(rel.encode("utf-8") + b"\0" + body + b"\0")
    return digest.hexdigest()[:24]


def failure_signature(row: dict[str, Any]) -> str:
    """Cells that share this failed the same way on the same instrument and chart.

    Digits in the error text are folded (`#`) so a row count or a date in a message does not
    split a signature; the symbol stays in the key, because data is per symbol."""
    import re

    sym = str(row.get("sym") or "")
    why = str(row.get("why") or row.get("detail") or "")
    if sym:
        why = why.replace(sym, "<sym>")
    why = re.sub(r"\d+", "#", why)[:160]
    return "|".join((str(row.get("family") or ""), sym, str(row.get("tf") or ""),
                     str(row.get("reason") or ""), why))


def _memoised(row: dict[str, Any]) -> bool:
    """A bank row parked under a CERTAIN code identity for a deterministic build failure."""
    return bool(row.get("code_fp")) and row.get("reason") in MEMO_REASONS


def _memo_state(target: Path) -> dict[str, Any]:
    try:
        doc = json.loads((target.parent / MEMO_STATE_NAME).read_text("utf-8"))
    except (OSError, ValueError):
        return {"code": {}, "canaries": {}}
    if not isinstance(doc, dict):
        return {"code": {}, "canaries": {}}
    doc.setdefault("code", {})
    doc.setdefault("canaries", {})
    return doc


def _report_mtime(path: Path | None = None) -> float | None:
    try:
        return (path or GATES_REPORT).stat().st_mtime
    except OSError:
        return None


def _memo_pass(bank: dict[str, dict[str, Any]], named: dict[str, dict[str, Any]],
               state: dict[str, Any], *, code_fp: str, at: str, now_ts: datetime | None,
               report_mtime: float | None, judged: set[str] | None,
               excluded: set[str]) -> dict[str, Any]:
    """One pass of the memo: track the identity, resolve canaries, start new ones.

    Mutates `bank` (siblings released, canaries popped, siblings re-stamped) and `state`.
    Returns (stats, the cells re-admitted, the canary cells that must NOT be re-parked yet).
    """
    stats: dict[str, Any] = {"code_fp": code_fp, "certain": False, "canaries_started": 0,
                             "canaries_confirmed": 0, "canaries_released": 0,
                             "siblings_restamped": 0, "siblings_released": 0,
                             "canaries_waiting": 0}
    t = (now_ts or datetime.now(tz=UTC)).timestamp()
    code_raw = state.get("code")
    code: dict[str, Any] = code_raw if isinstance(code_raw, dict) else {}
    if code.get("fp") != code_fp:
        code = {"fp": code_fp, "since": at, "report_mtimes": []}
    gens = [float(m) for m in (code.get("report_mtimes") or [])]
    if report_mtime is not None and report_mtime not in gens:
        gens = [*gens, report_mtime][-MEMO_CERTAIN_GENERATIONS:]
    code["report_mtimes"] = gens
    since = _ts(code.get("since"))
    certain = (len(gens) >= MEMO_CERTAIN_GENERATIONS and since is not None
               and (t - since.timestamp()) / 3600.0 >= MEMO_CERTAIN_H)
    state["code"] = code
    stats["certain"] = certain
    readmit: set[str] = set()
    hold_out: set[str] = set()
    can_raw = state.get("canaries")
    canaries: dict[str, Any] = can_raw if isinstance(can_raw, dict) else {}

    def _siblings(sig: str) -> list[str]:
        return [c for c, r in bank.items()
                if _memoised(r) and r.get("signature") == sig and r.get("code_fp") != code_fp]

    for sig in list(canaries):
        rec = canaries[sig] if isinstance(canaries[sig], dict) else {}
        if rec.get("code_fp") != code_fp:
            del canaries[sig]                         # the code moved again: start over
            continue
        seen = [float(m) for m in (rec.get("report_mtimes") or [])]
        if report_mtime is not None and report_mtime not in seen:
            seen.append(report_mtime)
        rec["report_mtimes"] = seen[-4:]
        cells = [str(c) for c in (rec.get("cells") or [])]
        # Judged at any time since it was set: it built, so the failure did not persist.
        judged_now = bool(judged) and any(c in judged for c in cells)  # type: ignore[operator]
        # Evidence from a report is admissible only from the SECOND generation after the canary
        # was set: the first may come from a sweep that was already running when it was set.
        admissible = len(seen) >= 3
        named_sigs = {failure_signature(named[c]) for c in cells if c in named}
        if judged_now or (admissible and named_sigs and named_sigs != {sig}):
            for c in _siblings(sig):
                bank.pop(c, None)
                readmit.add(c)
                stats["siblings_released"] += 1
            del canaries[sig]
            stats["canaries_released"] += 1
            continue
        if admissible and named_sigs == {sig}:
            for c in _siblings(sig):
                bank[c]["code_fp"] = code_fp
                stats["siblings_restamped"] += 1
            del canaries[sig]
            stats["canaries_confirmed"] += 1
            continue
        set_at = _ts(rec.get("at"))
        if set_at is not None and (t - set_at.timestamp()) / 86400.0 >= BUILD_FAILED_RETRY_DAYS:
            for c in _siblings(sig):
                bank.pop(c, None)
                readmit.add(c)
                stats["siblings_released"] += 1
            del canaries[sig]
            stats["canaries_released"] += 1
            continue
        hold_out.update(c for c in cells if c in named)  # too early to read: judge it again
        stats["canaries_waiting"] += 1
    if certain:
        groups: dict[str, list[str]] = {}
        for c, r in bank.items():
            if c in excluded or not _memoised(r) or r.get("code_fp") == code_fp:
                continue
            groups.setdefault(str(r.get("signature") or failure_signature(r)), []).append(c)
        for sig, cells in groups.items():
            if sig in canaries:
                continue
            pick = sorted(cells, key=lambda c: (str(bank[c].get("parked_at") or ""), c))[
                :CANARIES_PER_SIGNATURE]
            for c in pick:
                bank.pop(c, None)
                readmit.add(c)
            canaries[sig] = {"code_fp": code_fp, "cells": pick, "at": at,
                             "report_mtimes": [report_mtime] if report_mtime is not None else []}
            stats["canaries_started"] += 1
    state["canaries"] = canaries
    stats["signatures_in_flight"] = len(canaries)
    stats["_readmit"] = readmit
    stats["_hold_out"] = hold_out
    return stats


#: WHEN NOT-TESTABLE CELLS RETURN TO THE BACKLOG, one line per pass that re-admitted any: the
#: burn-down's inflow reads it (`judging_burndown.inflow`), because a re-admitted cell is owed
#: again exactly like a newly minted one and leaving it out overstates the drain.
READMISSION_LOG = HYP / "not_testable_readmissions.jsonl"


#: NEEDS_DATA CELLS RE-ADMITTED BY THE CLOCK WHILE THEIR INPUT IS STILL MISSING (audit of
#: c72ecfc53). After READMIT_MAX_DAYS such a cell leaves the bank, and the handoff is written from
#: the bank, so its per-cell demand vanished (measured 1 -> 0) while the input it lacks was still
#: absent. This sidecar keeps the row -- beside the bank, rewritten every pass -- until the probe
#: stops answering NEEDS_DATA or the cell is parked again, and the handoff reads it.
NEEDS_DATA_OUTSTANDING = HYP / "needs_data_outstanding.json"


#: THE SIDECAR'S STATES (audits of 3857d4bcd and fcef73b92). An absent or torn sidecar is NOT an
#: empty one: the rows it held exist nowhere else (the bank popped them at readmit), so neither may
#: read as 0, and a file that could not be read is never overwritten.
#:
#:   MEASURED      read cleanly, nothing set aside, and this pass's write landed.
#:   FIRST         absent, and never born here (no `.born` marker): the one creation allowed.
#:   VANISHED      absent after it was born: its rows are lost to this organ. A named
#:                 `.vanished-<at>` marker is written; UNMEASURED until a person removes it.
#:   TORN          present but not JSON (ValueError): moved aside UNTOUCHED to a unique
#:                 `.torn-<at>[-n]`; UNMEASURED until a person removes it. If it cannot be moved,
#:                 nothing is written.
#:   UNREADABLE    an OSError (a Windows sharing violation, a permission) persisted through the
#:                 retries, on the read or on `exists`: UNMEASURED, the file is NOT moved, and no
#:                 row is readmitted into it this pass.
#:   SET_ASIDE     read cleanly, but an earlier torn/vanished file is still set aside: UNMEASURED.
#:   LOCKED        another pass holds the sidecar lock: UNMEASURED, untouched, nothing readmitted
#:                 into it.
#:   WRITE_FAILED  this pass's write did not land: UNMEASURED; the rows bound for it stay parked.
#:
#: Every file here is `needs_data_outstanding.json*`, one gitignore line (`.born`, `.torn-*`,
#: `.vanished-*`, `.tmp`, `.lock`): a committed marker would read VANISHED in every other checkout.
OUTSTANDING_MEASURED, OUTSTANDING_FIRST = "MEASURED", "FIRST"
OUTSTANDING_VANISHED, OUTSTANDING_TORN, OUTSTANDING_SET_ASIDE = "VANISHED", "TORN", "SET_ASIDE"
OUTSTANDING_UNREADABLE, OUTSTANDING_LOCKED = "UNREADABLE", "LOCKED"
OUTSTANDING_WRITE_FAILED = "WRITE_FAILED"
#: A transient read error is retried this many times, this far apart, before it is UNREADABLE.
OUTSTANDING_READ_TRIES = 3
OUTSTANDING_READ_PAUSE_S = 0.2
#: How long a pass waits for the sidecar lock, and when a lock left by a dead pass is broken.
OUTSTANDING_LOCK_WAIT_S = 30.0
OUTSTANDING_LOCK_STALE_S = 900.0
#: A held lock's mtime is refreshed this often, so a pass longer than the stale window keeps it;
#: only a lock whose holder stopped beating (a dead pass) ever reads as stale.
OUTSTANDING_LOCK_BEAT_S = 60.0


def _born_marker(path: Path) -> Path:
    return path.with_name(path.name + ".born")


def _set_aside(path: Path) -> list[str]:
    try:
        return sorted(p.name for p in path.parent.glob(path.name + ".torn-*")) + sorted(
            p.name for p in path.parent.glob(path.name + ".vanished-*"))
    except OSError:
        return [f"{path.name}.<unlistable>"]


def _aside_name(path: Path, kind: str, at: str) -> Path:
    """A name no earlier set-aside file holds, so two tears in one second never collide."""
    base = f"{path.name}.{kind}-{_stamp(at)}"
    cand, n = path.with_name(base), 0
    while cand.exists():
        n += 1
        cand = path.with_name(f"{base}-{n}")
    return cand


def read_needs_data_outstanding(path: Path | None = None
                                ) -> tuple[dict[str, dict[str, Any]], str]:
    """(rows, state). Rows are what could be read; the state says whether that is the truth."""
    target = path or NEEDS_DATA_OUTSTANDING
    staged = _PASS.get(("staged_json", str(target))) if _PASS is not None else None
    if isinstance(staged, dict):
        # This pass's own uncommitted (v2.3 transaction) write of the sidecar.
        return ({str(k): v for k, v in staged.items() if isinstance(v, dict)},
                OUTSTANDING_SET_ASIDE if _set_aside(target) else OUTSTANDING_MEASURED)
    try:
        exists = target.exists()
        born = _born_marker(target).exists()
    except OSError:
        return {}, OUTSTANDING_UNREADABLE
    if not exists:
        return {}, (OUTSTANDING_VANISHED if born else OUTSTANDING_FIRST)
    text: str | None = None
    for attempt in range(OUTSTANDING_READ_TRIES):
        try:
            text = target.read_text("utf-8")
            break
        except ValueError:                  # undecodable bytes: torn, not transient
            return {}, OUTSTANDING_TORN
        except OSError:
            if attempt + 1 < OUTSTANDING_READ_TRIES:
                time.sleep(OUTSTANDING_READ_PAUSE_S)
    if text is None:
        return {}, OUTSTANDING_UNREADABLE
    try:
        doc = json.loads(text)
    except ValueError:
        return {}, OUTSTANDING_TORN
    if not isinstance(doc, dict):
        return {}, OUTSTANDING_TORN
    rows = {str(k): v for k, v in doc.items() if isinstance(v, dict)}
    return rows, (OUTSTANDING_SET_ASIDE if _set_aside(target) else OUTSTANDING_MEASURED)


def needs_data_outstanding(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """The rows that could be read (for the handoff); `read_needs_data_outstanding` has the state."""
    return read_needs_data_outstanding(path)[0]


def _stamp(at: str) -> str:
    return "".join(ch for ch in str(at) if ch.isalnum()) or "unstamped"


class _SidecarLock:
    """One pass's hold on the sidecar's `.lock` (which also guards the unrunnable bank).

    THREE PROPERTIES (audit of 1fb3db5f1):
      * EXCLUSIVE CREATION: `O_CREAT | O_EXCL`, carrying this pass's random `token`.
      * A HEARTBEAT: a daemon thread refreshes the lock's mtime every OUTSTANDING_LOCK_BEAT_S, so
        a pass longer than OUTSTANDING_LOCK_STALE_S is never taken over; only a holder that
        stopped beating -- a dead pass -- leaves a stale lock.
      * ATOMIC TAKEOVER: a stale lock is RENAMED to a unique `.lock.stale-<hex>` (one renamer wins;
        the other sees it gone), and the moved file is checked to be the same stale lock that
        was read. If a live lock was moved instead, it is linked back (a link fails rather than
        overwrite). And because no move can be undone perfectly under every race, the holder
        re-checks `owned()` before every write: a pass that lost its lock writes nothing.
    """

    def __init__(self, path: Path, at: str) -> None:
        self.path = path.with_name(path.name + ".lock")
        self.at = at
        self.token = uuid.uuid4().hex
        self.held = False
        self.lost = False
        self._stop = threading.Event()
        self._beat: threading.Thread | None = None

    def __bool__(self) -> bool:
        return self.held

    def _read(self, p: Path) -> tuple[dict[str, Any] | None, float | None]:
        try:
            st = p.stat()
            doc = json.loads(p.read_text("utf-8") or "{}")
        except (OSError, ValueError):
            return None, None
        return (doc if isinstance(doc, dict) else {}), st.st_mtime

    def _token(self) -> tuple[str, Any]:
        """("OK", token) | ("ABSENT", None) | ("UNREADABLE", None), retrying a transient read
        (a Windows sharing violation while another process stats or beats the file)."""
        for attempt in range(OUTSTANDING_READ_TRIES):
            try:
                doc = json.loads(self.path.read_text("utf-8") or "{}")
                return "OK", (doc.get("token") if isinstance(doc, dict) else None)
            except FileNotFoundError:
                return "ABSENT", None
            except (OSError, ValueError):
                if attempt + 1 < OUTSTANDING_READ_TRIES:
                    time.sleep(OUTSTANDING_READ_PAUSE_S)
        return "UNREADABLE", None

    def owned(self) -> bool:
        """True only on a clean read of this pass's token. Unreadable is NOT owned: a write
        gated on it waits for the next pass rather than risk racing a new holder."""
        if not self.held or self.lost:
            return False
        state, token = self._token()
        return state == "OK" and token == self.token

    def _take_stale(self) -> bool:
        doc, mtime = self._read(self.path)
        if doc is None or mtime is None or time.time() - mtime <= OUTSTANDING_LOCK_STALE_S:
            return False
        aside = self.path.with_name(f"{self.path.name}.stale-{uuid.uuid4().hex}")
        try:
            os.rename(self.path, aside)
        except OSError:
            return False                          # another pass moved it first
        moved, moved_mtime = self._read(aside)
        if moved is not None and moved_mtime is not None \
                and moved.get("token") == doc.get("token") \
                and time.time() - moved_mtime > OUTSTANDING_LOCK_STALE_S:
            with contextlib.suppress(OSError):
                aside.unlink()
            return True
        # A LIVE lock replaced the stale one between the read and the move: put it back.
        with contextlib.suppress(OSError):
            os.link(aside, self.path)
        with contextlib.suppress(OSError):
            aside.unlink()
        return False

    def _beat_loop(self) -> None:
        while not self._stop.wait(OUTSTANDING_LOCK_BEAT_S):
            state, token = self._token()
            if state == "UNREADABLE":
                continue                  # transient: try again next beat, never declare lost
            if state == "ABSENT" or token != self.token:
                self.lost = True
                return
            with contextlib.suppress(OSError):
                os.utime(self.path)

    def acquire(self, wait_s: float | None = None) -> bool:
        """Take the lock, waiting up to `wait_s` (default OUTSTANDING_LOCK_WAIT_S)."""
        deadline = time.monotonic() + (OUTSTANDING_LOCK_WAIT_S if wait_s is None else wait_s)
        while True:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(json.dumps({"at": self.at, "pid": os.getpid(),
                                         "token": self.token}))
                self.held = True
                break
            except FileExistsError:
                if self._take_stale():
                    continue
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.5)
            except OSError:
                break
        if self.held:
            self._beat = threading.Thread(target=self._beat_loop, daemon=True,
                                          name="needs-data-outstanding-lock")
            self._beat.start()
        return self.held

    def release(self) -> None:
        self._stop.set()
        if self._beat is not None:
            self._beat.join(timeout=5)
        # Unlink whenever the file still carries OUR token, even after a beat flagged a loss: a
        # lock left behind would block every pass for the whole stale window.
        state, token = self._token()
        if state == "OK" and token == self.token:
            with contextlib.suppress(OSError):
                self.path.unlink()
        self.held = False


@contextlib.contextmanager
def _outstanding_lock(path: Path, at: str) -> Any:
    """Hold the sidecar's lock for the bank's and sidecar's read-modify-write. Yields the
    `_SidecarLock`, which is falsy when the lock was not taken."""
    lk = _SidecarLock(path, at)
    lk.acquire()
    try:
        yield lk
    finally:
        if lk.held:
            lk.release()


@contextlib.contextmanager
def _bank_lock(path: Path, at: str, txn: _Txn | None) -> Any:
    """`_outstanding_lock`, except that inside a pass (`txn`) the lock is handed to the txn and
    held until the pass's commit or discard (audit of a5847f82a, R9): the bank and sidecar it
    guards are staged here but land at the commit, so releasing it here let a second pass read
    the pre-commit bank and commit over this one. A pass that already holds it reuses it."""
    if txn is None:
        with _outstanding_lock(path, at) as lk:
            yield lk
        return
    held = txn.held_lock(path)
    if held is not None:
        yield held
        return
    lk = _SidecarLock(path, at)
    lk.acquire()
    if lk.held:
        txn.adopt_lock(path, lk)
    yield lk


def _still_needs_data(row: dict[str, Any]) -> bool:
    return _fire_probe(str(row.get("sym") or ""), str(row.get("family") or "")).get(
        "status") == "NEEDS_DATA"


def update_unrunnable_bank(named: dict[str, dict[str, Any]], *, at: str,
                           path: Path | None = None,
                           log: Path | None = None,
                           code_fp: str | None = None,
                           judged: set[str] | None = None,
                           report_mtime: float | None = None) -> dict[str, Any]:
    """Park every newly-named unrunnable cell, and RE-ADMIT any whose bars have since grown.

    A cell the latest report names AGAIN is updated in place and never re-admitted on the same
    pass (it would only be parked again a line later): its FIRST `parked_at` is kept, so a
    rename never restarts the READMIT_MAX_DAYS clock. `not_testable_since` is stamped when a row
    ENTERS the not-testable class (new, or re-named out of a defect), which is the moment it
    leaves the backlog -- the coverage table books that as PARKING, never as drain.

    `code_fp` (the build path's identity, `build_code_identity`) switches on the build-failure
    memo (MEMO_REASONS above): deterministic failures are keyed on (cell, bars, code) and re-run
    only when one of those moves. Without it the bank behaves exactly as before.
    """
    target = path or UNRUNNABLE_BANK
    now_ts = _ts(at)
    bar_sizes: dict[tuple[str, str], int] = {}
    parkable = {c for c, r in named.items() if r.get("reason") != "missing_bars"}
    memo_on = bool(code_fp)
    readmitted_nt: dict[str, int] = {}
    readmitted_nt_reason: dict[str, int] = {}

    def _count_readmit(old_row: dict[str, Any]) -> None:
        fam = str(old_row.get("family") or "")
        rsn = str(old_row.get("reason") or "")
        readmitted_nt[fam] = readmitted_nt.get(fam, 0) + 1
        readmitted_nt_reason[rsn] = readmitted_nt_reason.get(rsn, 0) + 1

    out_path = target.parent / NEEDS_DATA_OUTSTANDING.name
    out_written = False
    bank_write = "SKIPPED_LOCKED"
    txn = _txn_current()
    # THE BANK IS READ, CHANGED AND WRITTEN UNDER THE SAME LOCK AS THE SIDECAR (audit of
    # 1fb3db5f1): a bank read before the lock could be overwritten by a pass that read it
    # earlier, and a LOCKED pass that wrote its bank anyway raced the holder's write. Inside a
    # pass the lock is held on until the pass's commit (`_bank_lock`), where the staged writes
    # land (audit of a5847f82a, R9).
    with _bank_lock(out_path, at, txn) as locked:
        bank = unrunnable_bank(target)
        readmitted = ([cell for cell, row in bank.items() if cell not in parkable
                       and readmit_due(row, now=now_ts, bar_sizes=bar_sizes, memo=memo_on)]
                      if locked else [])
        # What the memo saved this pass: memoised rows the blind weekly timer would have re-run.
        _readmitted_set = set(readmitted)
        memo_held = (sum(1 for cell, row in bank.items()
                         if cell not in parkable and cell not in _readmitted_set
                         and _memoised(row) and readmit_due(row, now=now_ts, bar_sizes=bar_sizes))
                     if memo_on and locked else 0)
        if locked:
            outstanding, out_state = read_needs_data_outstanding(out_path)
        else:
            outstanding, out_state = {}, OUTSTANDING_LOCKED
        out_writable = out_state in (OUTSTANDING_MEASURED, OUTSTANDING_FIRST,
                                     OUTSTANDING_SET_ASIDE, OUTSTANDING_VANISHED)
        if out_state == OUTSTANDING_TORN:
            # NEVER OVERWRITE WHAT COULD NOT BE READ: set it aside untouched, under its own name.
            try:
                out_path.rename(_aside_name(out_path, "torn", at))
                out_writable = True
            except OSError:
                out_writable = False        # cannot move it: leave it exactly as found
        elif out_state == OUTSTANDING_VANISHED:
            with contextlib.suppress(OSError), _aside_name(out_path, "vanished", at).open(
                    "x", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": at, "why": "the sidecar was born here and is now "
                                     "absent; the rows it held are not recoverable"}))
        # A ROW BOUND FOR THE SIDECAR LEAVES THE BANK ONLY IF THE SIDECAR CAN TAKE IT: with the
        # sidecar locked, unreadable or unmovable it stays parked and is re-asked next pass.
        held_back: list[str] = []
        popped: dict[str, dict[str, Any]] = {}
        to_side: set[str] = set()
        for cell in readmitted:
            old = bank.get(cell)
            bound = (isinstance(old, dict) and old.get("reason") == "needs_data"
                     and _still_needs_data(old))
            if bound and not out_writable:
                held_back.append(cell)
                continue
            popped[cell] = bank.pop(cell)
            if bound:
                to_side.add(cell)
                outstanding[cell] = {**popped[cell], "readmitted_at": at}
        # THE BUILD-FAILURE MEMO (judge-rate), run under the same lock as the bank it mutates
        # (merge resolution onto coverage v2.3, 2026-10-22): its sibling releases and canary pops
        # ride in this pass's bank write and are discarded with it; its state lands only with it.
        memo: dict[str, Any] = {"status": "OFF", "why": "no build-code identity this pass"}
        hold_out: set[str] = set()
        memo_state: dict[str, Any] = {}
        if memo_on and not locked:
            memo = {"status": "SKIPPED_LOCKED",
                    "why": "the bank lock is held by another pass: nothing memoised here"}
        elif memo_on:
            memo_state = _memo_state(target)
            memo = _memo_pass(bank, named, memo_state, code_fp=str(code_fp), at=at,
                              now_ts=now_ts, report_mtime=report_mtime, judged=judged,
                              excluded=parkable)
            hold_out = memo.pop("_hold_out")
            memo_readmit = memo.pop("_readmit")
            memo["readmitted"] = len(memo_readmit)
            memo["held_by_memo"] = memo_held
            memo["status"] = "ON"
        certain = bool(memo.get("certain"))
        added = 0
        for cell, row in (named if locked else {}).items():
            if row.get("reason") == "missing_bars":
                continue                   # owned by the conversion organ, not filtered here
            if cell in hold_out:
                continue                   # a canary too early to read: judged once more
            prev = bank.get(cell)
            if prev is None:
                added += 1
            prev = prev if isinstance(prev, dict) else {}
            was_nt = prev.get("reason") in NOT_TESTABLE_REASONS
            is_nt = row.get("reason") in NOT_TESTABLE_REASONS
            entry = {**row, "parked_at": prev.get("parked_at") or at}
            if is_nt:
                entry["not_testable_since"] = ((prev.get("not_testable_since") or at)
                                               if was_nt else at)
            elif was_nt:
                _count_readmit(prev)        # re-named OUT of the class: owed again
            entry.pop("code_fp", None)
            entry.pop("signature", None)
            if memo_on and certain and row.get("reason") in MEMO_REASONS:
                # MEMOISED: parked under a code identity this desk is sure the report ran.
                entry["code_fp"] = code_fp
                entry["signature"] = failure_signature(row)
            bank[cell] = entry
        # Parked again (the bank holds it) or the input appeared: the sidecar row is done.
        outstanding = {c: r for c, r in outstanding.items()
                       if c not in bank and _still_needs_data(r)}
        if locked and not locked.owned():
            # THE LOCK WAS LOST MID-PASS (moved by a takeover race): write nothing at all.
            out_state, out_writable, locked_lost = OUTSTANDING_LOCKED, False, True
            for cell in to_side:
                bank[cell] = popped.pop(cell)
            held_back.extend(sorted(to_side))
            to_side = set()
        else:
            locked_lost = False
        # Inside a judge_coverage pass (v2.3 `_Txn`) the sidecar, its birth marker and the bank
        # are STAGED and renamed together at the pass's commit point, so a pass killed or timed
        # out before it changes none of them (merge resolution, 2026-10-21); outside a pass each
        # is written now, tmp + replace, under this lock, exactly as v4.4 writes it.
        if out_writable:
            tmp = out_path.with_name(out_path.name + ".tmp")
            try:
                if txn is None:
                    tmp.write_text(json.dumps(outstanding, indent=1, default=str), "utf-8")
                    _replace_retry(tmp, out_path)
                else:
                    txn.put_text(out_path, json.dumps(outstanding, indent=1, default=str))
                    txn.guard(out_path, out_path)
                out_written = True
            except OSError:
                out_written = False
            finally:
                # A WRITE THAT DID NOT LAND LEAVES NO .tmp BEHIND (audit of 1e2f27789): after a
                # replace the file is gone already; after a failure it is this pass's own debris.
                with contextlib.suppress(OSError):
                    tmp.unlink(missing_ok=True)
            if out_written and txn is not None and _PASS is not None:
                # Later reads in this pass see the staged sidecar (read_needs_data_outstanding).
                _PASS[("staged_json", str(out_path))] = outstanding
        if out_written:
            # BORN ON EVERY SUCCESSFUL WRITE THAT FINDS NO MARKER (audit of fcef73b92), not only
            # on FIRST: a failed marker write, or a sidecar older than the marker, would otherwise
            # read MEASURED forever and re-FIRST to 0 the day it vanished.
            with contextlib.suppress(OSError):
                if not _born_marker(out_path).exists():
                    born_text = json.dumps({"born_at": at})
                    if txn is None:
                        _born_marker(out_path).write_text(born_text, "utf-8")
                    else:
                        txn.put_text(_born_marker(out_path), born_text)
                        txn.guard(out_path, _born_marker(out_path))
        elif to_side:
            # The write did not land: the rows bound for it go back to the bank, unreadmitted.
            for cell in to_side:
                bank[cell] = popped.pop(cell)
            held_back.extend(sorted(to_side))
        if out_writable and not out_written:
            out_state = OUTSTANDING_WRITE_FAILED
        if locked and not locked_lost and locked.owned():
            # Inside a judge_coverage pass (v2.3 `_Txn`) the bank is STAGED here and renamed at
            # the pass's commit point, so a pass killed or timed out before it leaves the bank as
            # it was; outside one it is written now, tmp + replace, under this lock.
            tmp_bank = target.with_name(target.name + ".tmp")
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                if txn is None:
                    tmp_bank.write_text(json.dumps(bank, indent=1, default=str), "utf-8")
                    _replace_retry(tmp_bank, target)
                else:
                    txn.put_text(target, json.dumps(bank, indent=1, default=str))
                    txn.guard(out_path, target)
                bank_write = "WRITTEN"
            except OSError:
                bank_write = "WRITE_FAILED"
            finally:
                with contextlib.suppress(OSError):
                    tmp_bank.unlink(missing_ok=True)
            if bank_write == "WRITTEN" and memo.get("status") == "ON":
                # The memo's state is written only beside a bank write that landed (staged with
                # it inside a pass), so its canaries never describe a bank the disk never saw.
                memo_path = target.parent / MEMO_STATE_NAME
                memo_text = json.dumps(memo_state, indent=1, default=str)
                with contextlib.suppress(OSError):
                    if txn is None:
                        memo_path.write_text(memo_text, "utf-8")
                    else:
                        txn.put_text(memo_path, memo_text)
                        txn.guard(out_path, memo_path)
            if bank_write == "WRITTEN" and _PASS is not None:
                # The next read of the bank in this pass is of the file just written; its parse
                # is this mapping (every value here is a JSON value), so the pass does not parse
                # it back (v2.3).
                if txn is not None:
                    _PASS[("staged_json", str(target))] = bank
                else:
                    _wk = _stat_key(target)
                    if _wk is not None:
                        _PASS[("json", *_wk)] = bank
        if bank_write == "WRITTEN":
            # COUNTED ONLY ONCE THE BANK LANDED: a readmission the disk never saw is not one.
            for old in popped.values():
                if isinstance(old, dict) and old.get("reason") in NOT_TESTABLE_REASONS:
                    _count_readmit(old)
        else:
            # Not ours to write, or the write failed: nothing this pass changed is on disk, and
            # nothing counts.
            bank = unrunnable_bank(target)
            added, popped = 0, {}
            readmitted_nt.clear()
            readmitted_nt_reason.clear()
            if memo.get("status") == "ON":
                memo.update(status="NOT_PERSISTED",
                            why="the bank write did not land: the memo's pass went with it")
    if memo_on:
        memo["memoised_rows"] = sum(1 for r in bank.values() if _memoised(r))
    out_measured = (out_written and out_state in (OUTSTANDING_MEASURED, OUTSTANDING_FIRST)
                    and not _set_aside(out_path))
    n_re = sum(readmitted_nt.values())
    # ONE LINE EVERY PASS, ZEROS INCLUDED (audit of PR #290, M1): the burn-down reads a missing
    # or stale log as UNMEASURED, so a quiet pass must still say "0" by writing it.
    # A failed write is caught by that staleness rule rather than raised here.
    try:
        # Beside the bank it describes, so a test's bank never writes the desk's log.
        lp = log or target.parent / READMISSION_LOG.name
        lp.parent.mkdir(parents=True, exist_ok=True)
        # A pass that did not hold the bank says so: LOCKED is not a measured zero, and the
        # burn-down neither counts it nor takes freshness from it.
        locked_line = {"at": at, "state": "LOCKED"}
        line = (locked_line if bank_write == "SKIPPED_LOCKED" else
                {"at": at, "readmitted": n_re, "by_reason": readmitted_nt_reason,
                 **({"state": bank_write} if bank_write != "WRITTEN" else {})})
        if txn is not None:
            # The whole log is staged (old bytes + this line) and renamed at commit: a rename is
            # idempotent under roll-forward, where a second append would not be. The old bytes
            # are read AT THE COMMIT, under the bank's lock (`_Txn.append_line`), so no other
            # pass can rename a copy taken before this line landed over it (R9).
            txn.append_line(lp, json.dumps(line), lock_path=out_path, at=at,
                            if_lost=json.dumps(locked_line))
        else:
            with lp.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(line) + "\n")
    except OSError:
        pass
    return {"parked_this_pass": added, "readmitted_on_bar_growth": len(popped),
            "needs_data_readmit_held_back": len(held_back),
            "build_failure_memo": memo,
            "readmitted_not_testable": n_re,
            "readmitted_not_testable_by_family": readmitted_nt,
            "readmitted_not_testable_by_reason": readmitted_nt_reason,
            "bank_size": len(bank),
            "needs_data_outstanding": len(outstanding) if out_measured else "UNMEASURED",
            "needs_data_outstanding_state": out_state,
            "needs_data_outstanding_set_aside": _set_aside(out_path),
            "bank_write": bank_write,
            "path": str(target)}


def family_value(path: Path | None = None) -> tuple[dict[str, float], float]:
    """What one PASS of this family is worth, net of cost: `reports/NET_EDGE.json`.

    `forward_slot_ranking_by_net` is the desk's own net-of-cost slot value per (family, symbol),
    already through the cost surface, the impact lab and the fusion cost model -- so nothing is
    re-derived here. A family the ranker has never scored takes the MEDIAN of those it has, which
    is the honest "no reason to think it is worse than typical"; zero would be a claim.
    """
    doc = _read(path or (REPORTS / "NET_EDGE.json"))
    best: dict[str, float] = {}
    if isinstance(doc, dict):
        for row in doc.get("forward_slot_ranking_by_net") or []:
            if not isinstance(row, dict):
                continue
            fam = str(row.get("family") or "")
            try:
                v = float(row.get("net_slot_value") or 0.0)
            except (TypeError, ValueError):
                continue
            if fam and v > best.get(fam, 0.0):
                best[fam] = v
    vals = sorted(best.values())
    # An ABSENT or empty NET_EDGE is UNMEASURED, not a measured zero (L1.28a). Returning 0.0 here
    # multiplied every family's ev to 0, so the ranking fell back to alphabetical order and the
    # prior, breadth and bar-cost terms it publishes stopped steering anything. Unit value keeps
    # every family at par on the value axis and lets the measured terms order them.
    median = vals[len(vals) // 2] if vals else 1.0
    return best, median


def family_breadth(path: Path | None = None) -> dict[str, float]:
    """Marginal BREADTH per family, from the effective-breadth machinery's cluster occupancy.

    `reports/EFFECTIVE_BREADTH.json` already answers "how many independent bets does this book
    actually hold" by mapping every sleeve to a cluster; a family that occupies no cluster adds a
    genuinely new bet and a family that already occupies six adds a sixth correlated one. The
    gain is 1/(1+occupancy) -- the diminishing return the effective rank itself exhibits. An
    absent artifact returns {} and every family scores the full gain, because an unmeasured
    breadth must never quietly demote a family (L1.28a).
    """
    doc = _read(path or (REPORTS / "EFFECTIVE_BREADTH.json"))
    occ: dict[str, float] = {}
    if isinstance(doc, dict):
        for sleeve in (doc.get("sleeve_clusters") or {}):
            parts = str(sleeve).split("_")
            if len(parts) >= 3:
                fam = "_".join(parts[1:-1])
                occ[fam] = occ.get(fam, 0.0) + 1.0
    return occ


def certified_family_shares() -> tuple[dict[str, float], int]:
    """The certified canon's family occupancy, from the existing search fitness reader.

    A missing or unreadable canon leaves the ranking neutral. It never becomes evidence that all
    families are empty. The judge's family floor is independent of this optional priority input.
    """
    try:
        from libs.research.alpha_fitness import certified_family_shares as read_shares
        return read_shares()
    except Exception:
        return {}, 0


def judge_seconds_per_cell(capacity: int) -> float:
    """Measured seconds of judge per H1-equivalent cell: one hour divided by what it judges."""
    return 3600.0 / float(max(capacity, 1))


def producer_signals(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """The two measured per-producer signals from `orthogonality_yield`, or {} when unmeasured.

    Read as a published ARTIFACT rather than imported, for the reason `research_budget` reads
    every one of its factors that way: a missing or unmeasured report must leave every producer at
    par, and an import that raised would be an outage in the ranking instead of a par reading.
    """
    for mod in ("research.orthogonality_yield", "orthogonality_yield"):
        try:
            oy = __import__(mod, fromlist=["published_factors"])
            table = oy.published_factors(path)
            return {str(k): v for k, v in table.items() if isinstance(v, dict)}
        except Exception:
            continue
    return {}


def _docket_keff() -> Any:
    """The marginal-k_eff scorer (research/docket_keff.py), or None when it cannot import."""
    for mod in ("research.docket_keff", "docket_keff"):
        try:
            return __import__(mod, fromlist=["score"])
        except Exception:
            continue
    return None


def _keff_family_factor(rows: list[dict[str, Any]]) -> dict[str, float]:
    if not any("_keff" in r for r in rows):
        return {}
    dk = _docket_keff()
    return dk.family_factor(rows) if dk is not None else {}


def keff_stamp(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Stamp `_keff` (the cell's marginal-k_eff priority) on every row; return the evidence.

    Never raises and never removes a row: a failure leaves the rows unstamped, which ranks every
    one of them exactly as before, and the reason is published as UNMEASURED (L1.28a).
    """
    dk = _docket_keff()
    if dk is None:
        return {"status": "UNMEASURED", "why": "research/docket_keff.py did not import"}
    try:
        doc = dk.score(rows)
        doc["status"] = "MEASURED"
        return dict(doc)
    except Exception as exc:
        for r in rows:
            r.pop("_keff", None)
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"[:300]}


def _occupancy_map() -> Any:
    """The occupancy map + orthogonality scorer (research/occupancy_map.py), or None."""
    for mod in ("research.occupancy_map", "occupancy_map"):
        try:
            return __import__(mod, fromlist=["stamp"])
        except Exception:
            continue
    return None


def occupancy_stamp(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Stamp `_occ` (the row's cell is an EMPTY/UNDER-TRIED target next to proven ground) and
    `_orth` (its expected orthogonality to the LIVE book and the certified set, centred on par)
    on every row, plus the published `orthogonality` score, from reports/OCCUPANCY_MAP.json.

    Read as a published artifact, like `producer_signals`: an absent or stale map stamps nothing
    and every row ranks exactly as before. Never raises, never removes a row (L1.28a).
    """
    om = _occupancy_map()
    if om is None:
        return {"status": "UNMEASURED", "why": "research/occupancy_map.py did not import"}
    try:
        doc, why = om.load(OCCUPANCY_REPORT)
        if doc is None:
            return {"status": "UNMEASURED", "why": why, "rows": len(rows)}
        return dict(om.stamp(rows, doc))
    except Exception as exc:
        for r in rows:
            r.pop("_occ", None)
            r.pop("_orth", None)
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"[:300]}


def _keff_summary(keff: dict[str, Any]) -> dict[str, Any]:
    """The compact k_eff block JUDGE_COVERAGE.json carries; the full table has its own report."""
    if keff.get("status") != "MEASURED":
        return {k: keff.get(k) for k in ("status", "why")}
    dk = _docket_keff()
    out = dk.summary(keff) if dk is not None else {}
    out["status"] = "MEASURED"
    return out


def rank_by_value(backlog: dict[str, int], rows: list[dict[str, Any]],
                  capacity: int) -> list[dict[str, Any]]:
    """EXPECTED VALUE PER JUDGE-SECOND, per family, published so the choice is inspectable.

        ev_per_cell = p_optimistic * net_value_if_it_passes * (1 + marginal_breadth)
                                   * orthogonality_factor * certificate_factor
                                   * certified_breadth_factor * novelty_factor
        ev_per_s    = ev_per_cell / (seconds_per_cell * this family's bar cost)

    Every term is something the desk already measures -- the learned prior, the net-of-cost slot
    value, the cluster occupancy behind effective breadth, and the bar ratio the sealed gauntlet
    budgets in. Nothing here is a preference; a family that ranks low ranks low on its own record,
    and a family with NO record ranks on the optimistic bound, which is how it gets explored.

    THE LAST TWO TERMS ARE THE PRINCIPAL'S ORDER OF 2026-09-23 -- "compute should always go more to
    discovering things which produce orthogonality along with ones who produce the most certis."
    `orthogonality_yield` measures both per producer: the LEAVE-ONE-OUT drop in the candidate
    grid's effective rank when that producer's cells are removed, and certificates per judge-hour
    from the gate ledger. Both arrive as one-sided multipliers at or above 1.0, so they can lift a
    producer and can never demote one, and a producer no judge has reached sits at par on the
    certificate axis rather than being scored as a measured zero (L1.28a). Absent report, both are
    1.0 and this function is exactly what it was.
    """
    fams = [f for f, n in backlog.items() if n > 0]
    realised = realised_pass_rates()
    priors = family_priors(fams, realised)
    values, median = family_value()
    occ = family_breadth()
    certified_shares, certified_n = certified_family_shares()
    signals = producer_signals()
    # MARGINAL k_eff PER FAMILY (research/docket_keff.py): 1 + max(0, mean cell priority) over the
    # rows `build` stamped. One-sided like the two factors above, and exactly 1.0 for rows that
    # carry no stamp, so a caller that never scored is ranked as it always was.
    keff_f = _keff_family_factor(rows)
    # THE NOVELTY FACTOR (principal 2026-10-13: "hunt tons of unknown styles"). 1 + the family's
    # style novelty from research/style_novelty.py: the measured share of its certificates' P&L no
    # known style reproduces, else its declared genealogy (0 textbook, 0.5 adjacent, 1.0
    # discovered/generic/learned; an unclassified family is a neutral 0). One-sided like the
    # factors above (>= 1.0), so the floor is untouched and no family's ev is reduced; an import
    # failure is 1.0 for every family.
    try:
        from research import style_novelty as _sn
        _nov_measured = _sn.family_values()

        def novelty_factor(fam: str) -> float:
            return 1.0 + max(0.0, min(1.0, _sn.family_novelty(fam, _nov_measured)))

        def _nov_source(fam: str) -> str:
            if fam in _nov_measured:
                return "MEASURED"
            cls = _sn.genealogy(fam)[1]
            return "UNMEASURED" if cls.startswith("UNMEASURED") else "GENEALOGY"
    except Exception:
        _nov_measured = {}

        def novelty_factor(fam: str) -> float:
            return 1.0

        def _nov_source(fam: str) -> str:
            return "UNMEASURED"
    per_cell_s = judge_seconds_per_cell(capacity)
    cost_units: dict[str, list[float]] = {}
    for row in rows:
        fam = str(row.get("family") or "")
        if fam in backlog:
            cost_units.setdefault(fam, []).append(_BAR_COST[_tf_of(row)])
    out: list[dict[str, Any]] = []
    for fam in fams:
        pr = priors.get(fam) or {"p": 0.5, "p_optimistic": 1.0, "n": 0.0, "status": 0.0}
        units = cost_units.get(fam) or [1.0]
        bars = sum(units) / len(units)
        cost_s = max(1e-6, per_cell_s * bars)
        value = values.get(fam, median)
        breadth = 1.0 / (1.0 + occ.get(fam, 0.0))
        sig = signals.get(fam) or {}
        ortho_f = float(sig.get("orthogonality_factor") or 1.0)
        cert_f = float(sig.get("certificate_factor") or 1.0)
        kf = float(keff_f.get(fam, 1.0))
        cert_share = float(certified_shares.get(fam, 0.0)) if certified_n else None
        # A family absent from a readable certified canon gets the strongest discovery bonus;
        # an already dominant family gets less. This is a one-sided research-priority credit,
        # so neither the family floor nor any cell's eligibility is reduced. The candidate-level
        # scorer separately recognises a new session/chart/regime inside an incumbent family.
        cert_breadth = 2.0 - cert_share if cert_share is not None else 1.0
        nov_f = novelty_factor(fam)
        ev_cell = (float(pr["p_optimistic"]) * value * (1.0 + breadth) * ortho_f * cert_f
                   * kf * cert_breadth * nov_f)
        rl = realised.get(fam) or {}
        out.append({
            "family": fam, "unjudged": backlog[fam],
            "p": round(pr["p"], 6), "p_optimistic": round(pr["p_optimistic"], 6),
            "prior_n": int(pr["n"]), "prior_status": "POSTERIOR" if pr["status"] else "PRIOR",
            # THE AIM, INSPECTABLE. What the family actually did at the judge, beside the number
            # the ranking spent, and which of the two the spend came from.
            "realised_judged": int(rl.get("judged", 0)),
            "realised_passed": int(rl.get("passed", 0)),
            "realised_pass_rate": round(float(rl.get("pass_rate", 0.0)), 6) if rl else None,
            "prior_source": "LEDGER_REALISED" if pr.get("source") else "STORED_POSTERIOR",
            "stored_prior_n": int(pr.get("stored_n", pr["n"])),
            "net_value_if_pass": value, "value_source": "NET_EDGE" if fam in values else "median",
            "breadth_gain": round(breadth, 4), "cluster_occupancy": occ.get(fam, 0.0),
            "certified_family_share": round(cert_share, 6) if cert_share is not None else None,
            "certified_family_count": (round(cert_share * certified_n)
                                       if cert_share is not None else None),
            "certified_breadth_factor": round(cert_breadth, 6),
            "certified_breadth_status": "MEASURED" if certified_n else "UNMEASURED",
            # THE TWO SIGNALS THE PRINCIPAL ORDERED COMPUTE STEERED BY (2026-09-23), measured per
            # producer in `orthogonality_yield` and published here beside the number they moved.
            # `breadth_gain` above stays exactly as it was -- it reads the LIVE BOOK's clusters and
            # belongs to the effective-breadth lane -- but it is measured to be ANTI-correlated
            # with true marginal orthogonality, which is the defect these two factors correct.
            # Both are one-sided (>= 1.0), so no family's ev is ever REDUCED by them and the
            # 25% floor below is untouched: this re-orders the remainder, it never starves.
            "orthogonality_factor": round(ortho_f, 4), "certificate_factor": round(cert_f, 4),
            "keff_factor": round(kf, 4),
            "novelty_factor": round(nov_f, 4),
            "novelty_source": _nov_source(fam),
            "marginal_rank": sig.get("marginal_rank"),
            "certs_per_judge_hour": sig.get("certs_per_judge_hour"),
            # BANNED / UNMEASURED / UNDER_JUDGED / MEASURED_ZERO / CERTIFYING -- a zero pass rate
            # is not one thing, and an UNMEASURED producer is never scored as a failing one.
            "producer_state": sig.get("state") or "UNMEASURED",
            "bar_cost_units": round(bars, 3), "cost_s_per_cell": round(cost_s, 4),
            "ev_per_cell": ev_cell, "ev_per_judge_second": ev_cell / cost_s,
        })
    out.sort(key=lambda r: (-float(r["ev_per_judge_second"]), str(r["family"])))
    for i, row in enumerate(out):
        row["rank"] = i + 1
    return out


def allocate(backlog: dict[str, int], capacity: int,
             floor_share: float = FLOOR_SHARE,
             ranking: list[dict[str, Any]] | None = None, *,
             priority: frozenset[str] | set[str] | None = None,
             priority_share: float = TAPE_PRIORITY_SHARE,
             tranche_out: dict[str, int] | None = None) -> dict[str, int]:
    """Quota per family: an equal FLOOR for every family holding backlog, then BY VALUE.

    THE FLOOR IS THE BREADTH MANDATE AND IT NEVER MOVES. Every family holding an unjudged cell
    gets an equal share of the first `FLOOR_SHARE` of the hour, because starving a family is how
    this desk reached a six-family concentration in the first place, and a ranking that could
    zero a family would rebuild it inside a week.

    THE REMAINDER IS WHERE THE RETURN IS. Spending it in proportion to backlog spends it on
    whichever miner ran hardest, which is a measure of the desk's own output and not of what an
    hour of judge is worth. So the remainder goes down the published ranking -- expected value per
    judge-second, highest first -- each family capped at its own backlog, until the hour is gone.
    Passing no ranking falls back to proportional, so a caller that cannot measure value still
    allocates rather than stalling.

    Two properties are load-bearing and both are tested. EVERY family with backlog gets at least
    one cell of the hour, and no family is given more than its own backlog (a quota is a promise
    to drain, not a licence to re-judge).
    """
    live = {f: n for f, n in backlog.items() if n > 0}
    if not live or capacity <= 0:
        return {}
    floor_pool = int(capacity * max(0.0, min(1.0, floor_share)))
    per_family_floor = max(1, floor_pool // len(live))
    quota = {f: min(n, per_family_floor) for f, n in live.items()}
    spare = capacity - sum(quota.values())
    if spare <= 0:
        return quota
    # THE TAPE TRANCHE (principal 2026-10-14: the tick tape must produce certificates). After the
    # floor -- which every family has already received, so nothing here can starve anyone -- the
    # PRIORITY families (the derived tape families) share up to `priority_share` of the hour,
    # split evenly and each capped at its own backlog; what they cannot use flows on to the value
    # remainder below. Published per family as `tape_priority`, and kept OUT of `remainder`, so
    # the fence's remainder-follows-ranking check reads the value walk alone.
    pri = sorted(f for f in (priority or ()) if f in live)
    if pri and priority_share > 0:
        pool = min(spare, int(capacity * max(0.0, min(1.0, priority_share))))
        left = list(pri)
        while pool > 0 and left:
            each = max(1, pool // len(left))
            nxt = []
            for f in left:
                take = min(each, live[f] - quota[f], pool)
                if take > 0:
                    quota[f] += take
                    pool -= take
                    spare -= take
                    if tranche_out is not None:
                        tranche_out[f] = tranche_out.get(f, 0) + take
                if live[f] - quota[f] > 0:
                    nxt.append(f)
                if pool <= 0:
                    break
            if nxt == left and each == 0:
                break
            left = nxt
        if spare <= 0:
            return quota
    if ranking:
        for row in ranking:
            fam = str(row.get("family") or "")
            room = live.get(fam, 0) - quota.get(fam, 0)
            if room <= 0:
                continue
            take = min(room, spare)
            quota[fam] += take
            spare -= take
            if spare <= 0:
                break
        return quota
    room_by_size = {f: live[f] - quota[f] for f in live if live[f] > quota[f]}
    weight = sum(room_by_size.values())
    if weight > 0:
        for fam, r in sorted(room_by_size.items(), key=lambda kv: (-kv[1], kv[0])):
            take = min(r, int(spare * r / weight))
            quota[fam] += take
    return quota


def grid_cell(row: dict[str, Any]) -> str:
    """(family|symbol|horizon) -- THE SAME KEY the yield fence weighs orthogonality on.

    `scripts/check_producer_yield.py` measures the desk's orthogonality as the participation
    ratio of the producer x (family|symbol|horizon) indicator matrix, and `libs/moat/registry.py`
    pays its empty-cell bonus on the same key. Ordering intake on any other key would order it
    on something the desk is not paid for, so this is that key, spelled the same way.
    """
    params = row.get("params") or {}
    fam = str(row.get("family") or "?").strip().lower() or "?"
    sym = str(row.get("symbol") or row.get("sym") or "?").strip().lower() or "?"
    hor = str(row.get("horizon") or params.get("horizon") or "?").strip().lower() or "?"
    return f"{fam}|{sym}|{hor}"


def structural_cell(row: dict[str, Any]) -> str:
    """A family's distinct research condition within the existing coverage grid.

    The public grid key stays family|symbol|horizon for its established consumers. For ordering
    variants inside one family, chart, session, regime, direction and representation matter too.
    Threshold-only parameter changes do not, and no structural distinction certifies an edge.
    """
    return _grid_and_structural(row)[1]


def _axis(*values: Any) -> str:
    """The first value that is present and non-blank, lower-cased; `?` when none is."""
    for v in values:
        if v is not None:
            txt = str(v).strip()
            if txt:
                return txt.lower()
    return "?"


def _grid_and_structural(row: dict[str, Any]) -> tuple[str, str]:
    """(`grid_cell`, `structural_cell`) of one row, the grid key computed once for both."""
    params = row.get("params") or {}
    grid = grid_cell(row)
    get, pget = row.get, params.get
    return grid, "|".join((
        grid, _axis(pget("timeframe"), get("timeframe"), "H1"),
        _axis(get("session"), get("selector"), pget("session"), pget("selector")),
        _axis(get("regime"), get("condition"), pget("regime"), pget("condition")),
        _axis(get("direction"), get("side"), pget("direction"), pget("side")),
        _axis(get("representation"), pget("representation"), pget("feature")),
    ))


def variant_split(rows: list[dict[str, Any]],
                  unjudged_ids: set[str] | None = None) -> dict[str, Any]:
    """Mark each docket row UNSEEN MECHANISM or VARIANT, and say how many of each there are.

    Charge repeated parameter settings against their first structural cell. A different chart,
    session, regime, direction or representation remains a distinct experiment within the same
    family. The legacy family|symbol|horizon grid count is reported separately for its consumers.

    NOTHING IS DROPPED AND NOTHING IS CAPPED. The queue stays whole and uncapped; the variant is
    marked `_variant = 1` and ranks below an unseen mechanism inside its own family stream, after
    the never-judged test, so the family floors, the value ranking and the interleave are all
    untouched. First-claim is decided by the same (never-judged, oldest-first) order the stream
    itself uses, so the row that would have gone first still goes first.
    """
    ids = unjudged_ids or set()
    # The claim order is (never-judged first, then oldest `first_seen`, then docket position).
    # Built as two stable sorts on `first_seen` -- the never-judged rows, then the rest -- which
    # is the same order as one sort on that triple, and every row's keys are read in ONE
    # sequential walk: at box scale a random-order walk of 1.45M rows cost ~6 s in cache misses.
    n = len(rows)
    first = [""] * n
    cells: list[tuple[str, str]] = [("", "")] * n
    fresh_idx: list[int] = []
    stale_idx: list[int] = []
    for i, row in enumerate(rows):
        first[i] = str(row.get("first_seen") or "9999")
        cells[i] = _grid_and_structural(row)
        (fresh_idx if (not ids or str(row.get("_cell") or "") in ids) else stale_idx).append(i)
    key = first.__getitem__
    order = sorted(fresh_idx, key=key) + sorted(stale_idx, key=key)
    seen: set[str] = set()
    grid_seen: set[str] = set()
    marks = [0] * n
    for i in order:
        grid, cell = cells[i]
        if cell in seen:
            marks[i] = 1
        else:
            seen.add(cell)
        grid_seen.add(grid)
    for i, row in enumerate(rows):
        row["_variant"] = marks[i]
    variants = sum(marks)
    return {"rows": len(rows), "unseen_mechanisms": len(rows) - variants, "variants": variants,
            "distinct_grid_cells": len(grid_seen),
            "distinct_structural_cells": len(seen),
            "variant_share": round(variants / len(rows), 4) if rows else None,
            "collapse_raw_per_grid_cell": (round(len(rows) / len(grid_seen), 3)
                                           if grid_seen else None)}


def _unseen_in_prefix(rows: list[dict[str, Any]], n: int) -> int:
    """How many of the first `n` rows the judge will reach are unseen mechanisms."""
    return sum(1 for r in rows[:max(int(n), 0)] if not int(r.get("_variant") or 0))


def coverage_order(rows: list[dict[str, Any]], quota: dict[str, int],
                   unjudged_ids: set[str] | None = None, *,
                   demote_variants: bool = True,
                   use_keff: bool = True,
                   use_occupancy: bool = True,
                   limit: int | None = None) -> list[dict[str, Any]]:
    """Weighted interleave of the families, so EVERY PREFIX of the docket is family-balanced.

    Each family is emitted on its own virtual clock ticking at 1/quota, and the family whose next
    tick is earliest goes next -- classic weighted fair queueing. The result: in any first N rows
    the gauntlet's budget reaches, family f holds about N * quota[f] / sum(quota) of them. Within
    a family, NEVER-JUDGED rows go first, then DISTINCT STRUCTURAL CELLS before parameter variants
    of a rule already claiming the same chart/session/regime/direction/representation, then oldest.
    The head of a family's stream is exactly the backlog the ratchet measures, spent on independent
    ground rather than on the same rule's constants. `demote_variants=False` reproduces the
    pre-2026-09-23 order, which is how the freed-slot count below is measured.

    MARGINAL k_eff (2026-09-30): among rows tied on those two tests, the cell whose instrument and
    cluster add the most independent bets to the book goes first (`_keff`, stamped by
    `keff_stamp`), and only then the oldest. A row with no stamp scores 0 and keeps its old place;
    `use_keff=False` reproduces the order before this term existed.

    OCCUPANCY AND ORTHOGONALITY (2026-09-30): the same tie-break term also carries `_occ` (the
    row's cell is an empty or under-tried cell one axis from proven ground, research/
    occupancy_map.py) and `_orth` (the row's expected orthogonality to the LIVE book and the
    certified set, centred on par). Both are in the same effective-bet units as `_keff` and are
    simply added to it; unstamped rows score 0 and keep their place. `use_occupancy=False`
    reproduces the order before these two terms existed.

    No row is dropped. A family with no quota still ships, after the quota'd stream, because the
    docket this returns is the whole docket and the judge's budget -- not this order -- decides
    where the hour stops.

    `limit` returns only the first `limit` rows of that same order (a reader that measures the
    head, never one that ships a docket). The merge is a pure function of each stream's prefix,
    so stopping it early changes no row it has already emitted.
    """
    if not rows:
        return []
    ids = unjudged_ids or set()

    def rank(row: dict[str, Any]) -> tuple[int, int, float, str]:
        cid = str(row.get("_cell") or "")
        fresh = 0 if (not ids or cid in ids) else 1
        # A parameter variant of a rule already claiming this grid cell ranks below an unseen
        # mechanism -- inside the family stream, after the never-judged test. It is never
        # dropped and the stream is never shortened; only the order changes.
        variant = int(row.get("_variant") or 0) if demote_variants else 0
        keff = -float(row.get("_keff") or 0.0) if use_keff else 0.0
        if use_occupancy:
            keff -= float(row.get("_occ") or 0.0) + float(row.get("_orth") or 0.0)
        return (fresh, variant, keff, str(row.get("first_seen") or "9999"))

    streams: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        streams.setdefault(str(row.get("family") or ""), []).append(row)
    for fam in streams:
        streams[fam].sort(key=rank)

    # Virtual finish time of each family's next row; a family with no quota rides at weight 1 so
    # it is still interleaved rather than appended in a block.
    import heapq
    heap: list[tuple[float, str, int]] = []
    for fam in streams:
        w = float(max(quota.get(fam, 0), 1))
        heapq.heappush(heap, (1.0 / w, fam, 0))
    out: list[dict[str, Any]] = []
    stop = len(rows) if limit is None else max(int(limit), 0)
    while heap and len(out) < stop:
        vtime, fam, idx = heapq.heappop(heap)
        out.append(streams[fam][idx])
        nxt = idx + 1
        if nxt < len(streams[fam]):
            w = float(max(quota.get(fam, 0), 1))
            heapq.heappush(heap, (vtime + 1.0 / w, fam, nxt))
    return out


def _mined(docket: list[dict[str, Any]]) -> dict[str, int]:
    """Mined population per family: the docket PLUS the study bank.

    The study bank holds families banned from live capital. They are not judged -- a gate-second
    there buys an outcome the desk has already forbidden -- but they were mined, and a coverage
    report that hid them would be reporting the desk's choices as if they were its output.
    """
    mined: dict[str, int] = {}
    for row in docket:
        fam = str(row.get("family") or "")
        mined[fam] = mined.get(fam, 0) + 1
    bank = _read(STUDY_BANK)
    if isinstance(bank, list):
        for row in bank:
            if isinstance(row, dict):
                fam = str(row.get("family") or "")
                mined[fam] = mined.get(fam, 0) + 1
    return mined


#: NO CELL ENDS UNTESTABLE (principal, 2026-10-13 16:45Z: "all must always be converted to
#: testible cells ... or no bars all must self resovle"). Every way the judge can fail to rule on a
#: cell maps to ONE failure class here, and every class names its way out -- who resolves it and
#: by which conversion. Nothing in this table is terminal: a class with no route is the defect, and
#: a raw status no class recognises is published as `unrouted` so the hourly pass hunts it the day
#: it appears. Only a real verdict (pass or fail) ends a cell.
FAILURE_CLASS: dict[str, str] = {
    # the sweep's own NOT_RUN statuses and pre-warm failure kinds
    "NOT_RUN_DATA_MISSING": "no_bars",
    "NOT_RUN_BUILD_FAILED": "build_fail",
    "NOT_RUN_BUILD_BUDGET_DEFERRED": "budget_deferred",
    "NOT_RUN_MODIFIER": "modifier_refused",
    "NOT_RUN_UNTRADEABLE_SYMBOL": "untradeable_symbol",
    "FAIL_3X": "fail_3x",
    "ERROR": "build_fail",
    "SAVE_FAILED": "save_fail",
    # the bank's named reasons (`name_not_run`, `name_unknowns`)
    "data_missing": "no_bars",
    "missing_bars": "no_bars",
    "build_failed": "build_fail",
    "no_series": "no_series",
    "series_exception": "no_series",
    "observations_under_60_days": "short_history",
    "short_history_after_cut": "short_history",
    "lockbox_consumed_history": "short_history",
    "no_signals": "untestable_as_specified",
    "signals_no_trades": "untestable_as_specified",
    "no_trades": "untestable_as_specified",
    "too_rare": "untestable_as_specified",
    "never_fires": "untestable_as_specified",
    "needs_data": "needs_data",
    "missing_identity_input": "unnamed",
    "no_terminal_gate_recorded": "unnamed",
    "unnamed": "unnamed",
}

#: WHO RESOLVES EACH CLASS, AND HOW. `converter` is Breadth's conversion organ: the cell is handed
#: over with these axes and comes back as a testable cell in the judge's queue. `judge` is work
#: the judge itself still owes on its next sweep (ranked by UnlockValue), never a parking place.
FAILURE_ROUTES: dict[str, dict[str, Any]] = {
    "no_bars": {"owner": "converter",
                "axes": ["backfill_bars", "proxy_series", "coarser_timeframe"]},
    "no_series": {"owner": "converter",
                  "axes": ["proxy_series", "coarser_timeframe", "event_study"]},
    "build_fail": {"owner": "converter",
                   "axes": ["regime_child", "coarser_timeframe", "family_defect_report"]},
    "fail_3x": {"owner": "converter", "axes": ["coarser_timeframe", "regime_child"]},
    "modifier_refused": {"owner": "converter", "axes": ["base_spec_without_modifier"]},
    "untradeable_symbol": {"owner": "converter", "axes": ["cross_asset_transplant"]},
    "short_history": {"owner": "converter",
                      "axes": ["proxy_series", "cross_asset_transplant", "coarser_timeframe"]},
    "untestable_as_specified": {"owner": "converter",
                                "axes": ["event_study", "coarser_timeframe", "regime_child",
                                         "cross_asset_transplant"]},
    # `acquire_named_input` and `proxy_series` were listed here with no organ reading them (audit
    # of c72ecfc53); the named input itself rides in `missing_input`, which is what is read.
    "needs_data": {"owner": "converter", "axes": ["cross_asset_transplant"]},
    "budget_deferred": {"owner": "judge", "axes": ["next_sweep_by_unlock_value"]},
    "save_fail": {"owner": "judge", "axes": ["rebuild_next_sweep"]},
    "unnamed": {"owner": "judge", "axes": ["name_the_reason"]},
}

#: Where cells for the converter are handed over, rewritten every pass from the bank (the bank
#: stays the record; this file is the queue the converter consumes).
CONVERSION_HANDOFF = HYP / "conversion_handoff.json"


def failure_class(raw: Any) -> str | None:
    """The failure class for one raw status or bank reason; None means UNROUTED (a defect)."""
    return FAILURE_CLASS.get(str(raw or ""))


def judging_failures(path: Path | None = None,
                     bank: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Per-class counts of every way the judge failed to rule, last sweep and parked stock.

    `last_sweep` reads the sealed judge's own report (verdict rows that never reached the gates,
    UNKNOWN verdicts by named reason, and the pre-warm's failure kinds); `parked` reads the bank.
    An absent report is UNMEASURED for the sweep half -- never zero failures.
    """
    out: dict[str, Any] = {"routes": FAILURE_ROUTES, "terminal_classes": []}
    sweep: dict[str, int] = {}
    unrouted: dict[str, int] = {}

    def _book(raw: str, into: dict[str, int], n: int = 1) -> None:
        cls = failure_class(raw)
        if cls is None:
            unrouted[raw] = unrouted.get(raw, 0) + n
        else:
            into[cls] = into.get(cls, 0) + n

    doc = _read_memo(path or GATES_REPORT)
    verdicts = (doc or {}).get("verdicts") if isinstance(doc, dict) else None
    if isinstance(verdicts, list):
        for v in verdicts:
            if not isinstance(v, dict):
                continue
            st = str(v.get("downstream_status") or "")
            if st.startswith(NOT_JUDGED_PREFIX) and st not in (
                    "NOT_RUN_TERMINAL_GATE_1_REJECT", "NOT_RUN_NO_GATE_1_ELIGIBLE_CELLS"):
                _book(st, sweep)
        for row in name_unknowns(path).values():
            _book(str(row.get("reason") or "unnamed"), sweep)
        pw = doc.get("prewarm") if isinstance(doc, dict) else None
        fails = pw.get("failures") if isinstance(pw, dict) else None
        if isinstance(fails, dict):
            for k, n in fails.items():
                # NOT_RUN_* kinds are already booked once from the verdict rows.
                if not str(k).startswith(NOT_JUDGED_PREFIX):
                    _book(str(k), sweep, int(n or 0))
        out["last_sweep"] = dict(sorted(sweep.items()))
        out["last_sweep_status"] = "MEASURED"
    else:
        out["last_sweep"] = None
        out["last_sweep_status"] = "UNMEASURED"
        out["last_sweep_why"] = "the sealed judge has written no verdicts here"
    parked: dict[str, int] = {}
    for row in (unrunnable_bank() if bank is None else bank).values():
        _book(str(row.get("reason") or "unnamed"), parked)
    out["parked"] = dict(sorted(parked.items()))
    out["parked_to_converter"] = sum(n for c, n in parked.items()
                                     if FAILURE_ROUTES.get(c, {}).get("owner") == "converter")
    out["unrouted"] = dict(sorted(unrouted.items()))
    out["verdict"] = "UNROUTED" if unrouted else "ALL_ROUTED"
    return out


#: The handoff's contract with Breadth's converter. Bump on any field change.
CONVERSION_HANDOFF_SCHEMA = 1
#: The clock the universe bars are stamped on (CLAUDE.md: broker clock is NY+7).
BAR_CLOCK = "broker NY+7"


def _missing_input(cls: str, row: dict[str, Any]) -> dict[str, Any] | None:
    """What a no_bars / no_series cell lacks, so the converter can backfill or proxy it."""
    sym, tf = str(row.get("sym") or ""), str(row.get("tf") or "H1")
    if cls == "no_bars":
        return {"kind": "bars", "symbol": sym, "timeframe": tf,
                "file": f"universe/{sym}_{tf}.parquet", "clock": BAR_CLOCK}
    if cls == "no_series":
        return {"kind": "series", "symbol": sym, "timeframe": tf, "clock": BAR_CLOCK,
                "why": str(row.get("why") or "")[:200]}
    if cls == "needs_data":
        return {"kind": "input", "input": row.get("missing_input"), "symbol": sym,
                "family": row.get("family"), "timeframe": tf,
                "why": str(row.get("route") or "")[:300]}
    return None


def write_conversion_handoff(bank: dict[str, dict[str, Any]], *, at: str,
                             path: Path | None = None,
                             outstanding: dict[str, dict[str, Any]] | None = None) -> int:
    """Hand every parked cell the converter owns to the converter, with its class and axes.

    Written every pass, EMPTY included, so absence never reads as zero. `trial_family` is the
    family the sealed judge charges the cell's trials to: a conversion stays inside it and is
    never charged a second family. Attempts are the converter's own sidecar
    (`conversion_attempts.jsonl`); this writer never touches it.
    """
    rows = []
    # A NEEDS_DATA cell re-admitted by the clock while its input is still missing keeps its row
    # (`NEEDS_DATA_OUTSTANDING`); the bank's own row wins when the cell is parked again.
    merged = {**{c: {**r, "still_missing_after_readmit": True}
                 for c, r in (outstanding or {}).items()}, **bank}
    for cell, row in sorted(merged.items()):
        cls = failure_class(row.get("reason")) or "unnamed"
        route = FAILURE_ROUTES.get(cls, {})
        if route.get("owner") != "converter":
            continue
        fam = row.get("family")
        rows.append({"cell": cell, "family": fam, "trial_family": fam,
                     "symbol": row.get("sym"), "timeframe": row.get("tf") or "H1",
                     "reason": row.get("reason"), "class": cls, "axes": route.get("axes"),
                     "missing_input": _missing_input(cls, row), "why": row.get("why"),
                     "first_parked_utc": row.get("parked_at"),
                     **({"readmitted_at": row.get("readmitted_at"),
                         "still_missing_after_readmit": True}
                        if row.get("still_missing_after_readmit") else {})})
    target = path or CONVERSION_HANDOFF
    txn = _txn_current()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps({"schema_version": CONVERSION_HANDOFF_SCHEMA,
                           "generated_utc": at, "n": len(rows), "rows": rows},
                          indent=1, default=str)
        if txn is None:
            _atomic_write_text(target, text)
        else:
            txn.put_text(target, text)
    except OSError:
        # Never leave the previous pass's file to read as this pass's count.
        if txn is not None:
            txn.delete(target)
        else:
            with contextlib.suppress(OSError):
                target.unlink()
        return -1
    return len(rows)


#: A FAMILY THAT HAS NEVER BEEN JUDGED MAY NOT WAIT LONGER THAN THIS (2026-10-14). Measured on
#: the box 2026-10-13: `orderflow_imbalance` (49,108 mined, oldest 782 h) and `liquidity_regime`
#: (39,319) had judged_total 0 while each carried a 244-cell floor quota every hour, and the four
#: raw COT families (~30k mined) the same. Two days is generous against an hourly judge: a family
#: that cannot get ONE real verdict in 48 h is not queued, it is unreachable, and the fence
#: (`scripts/check_judge_coverage.py`) fails it on the box with the reasons published here.
NEVER_JUDGED_MAX_AGE_H = 48.0

TAPE_DIR = BASE / "data" / "tape" / "ticks"
#: THE TICK TAPE MUST PRODUCE CERTIFICATES, NOT CELLS (principal 2026-10-14 07:25Z: "Tick n moat
#: recorder must be mined 24/7 n if must produce cells n certis always make sure it does ... always
#: maximise it"). Which families are TAPE families is DERIVED FROM CODE, never listed: a family is
#: one when the branch that builds it calls a reader of `data/tape/ticks` -- in the sealed judge's
#: `build_cell` (`elif family ...:` whose body calls one of TAPE_READERS) or in the orthogonal
#: sweep's `kwargs_by_family` (a family handed a value `_tape_series` returned). A new tape family
#: is picked up the hour its builder lands; a family whose input is merely DERIVED from bars
#: (execution_state's surface is the H1 parquets' spread/tick_volume columns,
#: `microstructure_miner`) is not one, and the derivation says so by not finding a reader.
TAPE_READERS = frozenset({"_tape_series", "_tape_minutes"})
TAPE_SOURCES = (BASE / "scripts" / "external_gauntlet.py",
                BASE / "research" / "orthogonal_sweep.py")
#: A tape family's tape is stale (the recorder idle) when its newest day file is older than this.
TAPE_STALE_DAYS = 3
#: THE CERTIFICATE BAR FOR THE TAPE AS A WHOLE: tape families together judged past this many
#: cells, with the tape deep enough, and not one certificate -> the fence fails. At a 1% per-cell
#: pass rate (the low end of what producing families measure) P(0 of 500) = 0.99**500 = 0.66%, so
#: zero certificates past 500 judged is a defect to name, not bad luck.
TAPE_CERT_MIN_JUDGED = 500
UNIVERSAL_SURVIVORS = REPORTS / "UNIVERSAL_SURVIVORS.json"


def _family_test_names(test: Any) -> set[str]:
    """Family names an `if family == "x"` / `if family in {...}` test selects, else empty."""
    import ast
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return set()
    if not (isinstance(test.left, ast.Name) and test.left.id == "family"):
        return set()
    comp = test.comparators[0]
    if isinstance(test.ops[0], ast.Eq) and isinstance(comp, ast.Constant):
        return {str(comp.value)} if isinstance(comp.value, str) else set()
    if isinstance(test.ops[0], ast.In) and isinstance(comp, (ast.Set, ast.Tuple, ast.List)):
        return {str(e.value) for e in comp.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    return set()


def _calls_reader(nodes: list[Any]) -> bool:
    import ast
    for n in nodes:
        for sub in ast.walk(n):
            if isinstance(sub, ast.Call):
                f = sub.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                if name in TAPE_READERS:
                    return True
    return False


def derive_tape_families(sources: tuple[Path, ...] | None = None
                         ) -> tuple[frozenset[str], dict[str, Any]]:
    """(tape families, provenance) read from the builders' own source. See TAPE_READERS."""
    import ast
    fams: set[str] = set()
    by_source: dict[str, list[str]] = {}
    unreadable: list[str] = []
    for src in sources if sources is not None else TAPE_SOURCES:
        try:
            tree = ast.parse(Path(src).read_text("utf-8"))
        except (OSError, SyntaxError, ValueError):
            unreadable.append(str(src))
            continue
        found: set[str] = set()
        tape_vars: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and _calls_reader(node.body):
                found |= _family_test_names(node.test)
            if isinstance(node, ast.Assign) and _calls_reader([node.value]):
                for t in node.targets:
                    for el in ast.walk(t):
                        if isinstance(el, ast.Name):
                            tape_vars.add(el.id)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)):
                continue
            if not any(isinstance(t, ast.Name) and t.id == "kwargs_by_family"
                       for t in node.targets):
                continue
            for k, v in zip(node.value.keys, node.value.values, strict=False):
                if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                    continue
                names = {n.id for n in ast.walk(v) if isinstance(n, ast.Name)}
                if names & tape_vars or _calls_reader([v]):
                    found.add(k.value)
        by_source[Path(src).name] = sorted(found)
        fams |= found
    return frozenset(fams), {"readers": sorted(TAPE_READERS), "by_source": by_source,
                             "unreadable": unreadable,
                             "status": "MEASURED" if by_source else "UNMEASURED"}


_TAPE_FAMILY_CACHE: dict[str, Any] = {}


def tape_families() -> frozenset[str]:
    """The derived tape families, cached on the sources' mtimes (one parse per code change)."""
    key = []
    for src in TAPE_SOURCES:
        try:
            key.append(f"{src}:{src.stat().st_mtime_ns}")
        except OSError:
            key.append(f"{src}:absent")
    k = "|".join(key)
    if _TAPE_FAMILY_CACHE.get("key") != k:
        fams, prov = derive_tape_families()
        _TAPE_FAMILY_CACHE.update({"key": k, "fams": fams, "prov": prov})
    return frozenset(_TAPE_FAMILY_CACHE["fams"])


def tape_certificates(path: Path | None = None) -> tuple[dict[str, int] | None, str]:
    """Certified sleeves per family from UNIVERSAL_SURVIVORS (None when unreadable)."""
    p = path or UNIVERSAL_SURVIVORS
    try:
        doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None, f"{p.name} absent or unreadable"
    surv = doc.get("survivors") if isinstance(doc, dict) else None
    rows = surv.values() if isinstance(surv, dict) else (surv if isinstance(surv, list) else [])
    out: dict[str, int] = {}
    for c in rows:
        if not isinstance(c, dict):
            continue
        spec = c.get("shadow_spec") if isinstance(c.get("shadow_spec"), dict) else {}
        fam = (spec or {}).get("family") or c.get("family")
        if isinstance(fam, str) and fam:
            out[fam] = out.get(fam, 0) + 1
    return out, p.name
#: The held-out floor the sealed policy carves from every series (gate_policy.LOCKBOX_MIN_DAYS),
#: read from the policy when importable and never re-declared as authority here.
LOCKBOX_MIN_DAYS_FALLBACK = 40


def parked_in_bank(rows: list[dict[str, Any]], bank: dict[str, dict[str, Any]],
                   judged_cells: set[str], not_testable_ids: dict[str, str] | set[str],
                   banned: frozenset[str] | set[str]
                   ) -> tuple[dict[str, int], dict[str, dict[str, int]], dict[str, str]]:
    """Unjudged backlog rows the bank holds OUT of the shipped docket, per family and reason.

    These are exactly the rows `order_docket` removes before the gauntlet reads the file, so they
    can be given no share of the hour. Not-testable rows are already outside the backlog and are
    not counted twice. Returns (count per family, count per family per reason, one sample `why`
    per family)."""
    count: dict[str, int] = {}
    by_reason: dict[str, dict[str, int]] = {}
    why: dict[str, str] = {}
    if not bank:
        return count, by_reason, why
    for row in rows:
        cid = str(row.get("_cell") or "")
        if not cid or cid in judged_cells or cid in not_testable_ids:
            continue
        fam = str(row.get("family") or "")
        if fam in banned:
            continue
        b = bank.get(cid)
        if not isinstance(b, dict):
            continue
        reason = str(b.get("reason") or "unnamed")
        count[fam] = count.get(fam, 0) + 1
        slot = by_reason.setdefault(fam, {})
        slot[reason] = slot.get(reason, 0) + 1
        if fam not in why and b.get("why"):
            why[fam] = str(b.get("why"))[:200]
    return count, by_reason, why


def sweep_census_by_family(path: Path | None = None) -> dict[str, dict[str, dict[str, int]]]:
    """The last sweep's fate per family: downstream status and UNKNOWN reason counts.

    Read from the sealed judge's own report (memoised for the pass). An absent report is an empty
    census -- the caller says so -- never zero failures."""
    doc = _read(path or GATES_REPORT)
    verdicts = (doc or {}).get("verdicts") if isinstance(doc, dict) else None
    out: dict[str, dict[str, dict[str, int]]] = {}
    if not isinstance(verdicts, list):
        return out
    for v in verdicts:
        if not isinstance(v, dict):
            continue
        fam = str(v.get("family") or "")
        if not fam:
            continue
        slot = out.setdefault(fam, {"status": {}, "unknown_reason": {}, "terminal_gate": {}})
        st = str(v.get("downstream_status") or "")
        if st:
            slot["status"][st] = slot["status"].get(st, 0) + 1
        gate = str(v.get("terminal_gate") or ("PASSED" if v.get("passed") else "UNKNOWN"))
        slot["terminal_gate"][gate] = slot["terminal_gate"].get(gate, 0) + 1
        if v.get("unmeasured") or gate == "UNKNOWN":
            r = str(v.get("unknown_reason") or "")
            if r:
                slot["unknown_reason"][r] = slot["unknown_reason"].get(r, 0) + 1
    return out


def _lockbox_min_days() -> int:
    try:
        desk = str(BASE)
        if desk not in sys.path:
            sys.path.insert(0, desk)
        from research.gate_policy import LOCKBOX_MIN_DAYS
        return int(LOCKBOX_MIN_DAYS)
    except Exception:
        return LOCKBOX_MIN_DAYS_FALLBACK


def _tape_day(stem: str) -> str | None:
    """'2026-09-16' and '20260916' (the two tape writers) -> '2026-09-16'; else None."""
    d = stem.replace("-", "")
    if len(d) != 8 or not d.isdigit():
        return None
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def tape_depth(root: Path | None = None, *, now: datetime | None = None) -> dict[str, Any]:
    """How many TRADING days of tick tape the box holds per symbol -- the history a tape family
    can use -- and, when short, how long until the deepest symbol is judgeable.

    Counted from the day files themselves (`<SYM>/<DAY>.parquet`), cheap and never assumed. A day
    is a distinct date with a file (the recorder writes no file on a day without ticks), so the
    count IS trading days; the two writers' spellings of one date count once. The ETA assumes the
    recorder keeps writing one trading day per weekday (5 per 7 calendar days) and is withheld
    (None, with the reason) when the newest file is older than TAPE_STALE_DAYS -- an idle recorder
    has no ETA."""
    base = root or TAPE_DIR
    need = CPCV_MIN_DAYS + _lockbox_min_days()
    if not base.is_dir():
        return {"status": "UNMEASURED", "why": f"no tape store at {base}", "days_needed": need}
    days: list[int] = []
    last: str | None = None
    first: str | None = None
    for d in base.iterdir():
        if not d.is_dir():
            continue
        dates = {x for x in (_tape_day(f.stem) for f in d.glob("*.parquet")) if x}
        if not dates:
            continue
        days.append(len(dates))
        last = max(last or "", max(dates))
        first = min(first or "9999", min(dates))
    if not days:
        return {"status": "UNMEASURED", "why": "the tape store holds no symbol",
                "days_needed": need}
    days.sort()
    at = now or datetime.now(tz=UTC)
    out: dict[str, Any] = {
        "status": "MEASURED", "symbols": len(days), "max_days": days[-1],
        "median_days": days[len(days) // 2],
        "symbols_at_need": sum(1 for n in days if n >= need), "days_needed": need,
        "days_needed_rule": f"{CPCV_MIN_DAYS} development days + lockbox floor "
                            f"{need - CPCV_MIN_DAYS} (gate_policy.LOCKBOX_MIN_DAYS)",
        "first_day": first, "last_day": last}
    out["meets_need"] = out["symbols_at_need"] > 0
    try:
        idle = (at.date() - datetime.fromisoformat(str(last)).date()).days
    except ValueError:
        idle = None
    out["recorder_idle_days"] = idle
    short = max(0, need - days[-1])
    out["short_trading_days"] = short
    if short == 0:
        out["eta_days_to_judgeable"] = 0
        out["eta_rule"] = "the deepest symbol already holds the need"
    elif idle is None or idle > TAPE_STALE_DAYS:
        out["eta_days_to_judgeable"] = None
        out["eta_rule"] = (f"UNMEASURED: the newest tape day is {last} ({idle} days old, past "
                           f"{TAPE_STALE_DAYS}) -- the recorder is idle, so no date can be given")
    else:
        out["eta_days_to_judgeable"] = math.ceil(short * 7 / 5)
        out["eta_rule"] = (f"{short} trading days short on the deepest symbol, at 5 trading "
                           f"days per 7 calendar days")
    return out


def tape_tranche_gate(tape_fams: frozenset[str] | set[str], shippable: dict[str, int],
                      capacity: int, depth: dict[str, Any]) -> dict[str, Any]:
    """Which tape families may draw the tranche THIS hour, and the share returned to value.

    The tranche (principal 2026-10-14) is kept, but only for cells the judge can actually rule
    on: a tape family draws it when the tape holds the need (60 development days + lockbox on at
    least one symbol, `tape_depth.meets_need`) AND the family has shippable cells. Below the need
    every tape cell can only come back UNKNOWN (too short a series), so the whole share is handed
    back to the value remainder this hour (audit of ad7d4ac6a, must-fix 1)."""
    pool = int(max(capacity, 0) * max(0.0, min(1.0, TAPE_PRIORITY_SHARE)))
    ready = depth.get("status") == "MEASURED" and bool(depth.get("meets_need"))
    fams = sorted(f for f in tape_fams if ready and int(shippable.get(f, 0)) > 0)
    if not tape_fams:
        why = "no tape family derived from the builders' code"
    elif depth.get("status") != "MEASURED":
        why = f"tape depth UNMEASURED ({depth.get('why')}): no tape cell is known judgeable"
    elif not ready:
        why = (f"tape below its need ({depth.get('max_days')} trading days on the deepest symbol "
               f"vs {depth.get('days_needed')}; ETA {depth.get('eta_days_to_judgeable')}d): a "
               "tape cell can only return UNKNOWN, so the share goes back to value")
    elif not fams:
        why = "tape at need but no tape family has a shippable cell"
    else:
        why = "tape at need: the tape families with shippable cells draw the tranche"
    return {"in_force": bool(fams), "families": fams, "share": TAPE_PRIORITY_SHARE,
            "pool": pool if fams else 0, "returned_to_value": 0 if fams else pool, "why": why}


def tape_tranche_missed_growth(shippable: dict[str, int], capacity: int,
                               ranking: list[dict[str, Any]], quota: dict[str, int],
                               tranche: dict[str, int], rec: dict[str, Any], *,
                               at: datetime) -> dict[str, Any]:
    """The tranche's cost, measured: cells each non-tape family lost against the same allocation
    without the tranche, valued at the ranking's ev_per_cell. Unused pool is returned to value
    (`returned_to_value` grows by it). Every pass emits a line: zero when nothing was displaced
    (NOT_BINDING), never silence."""
    used = sum(tranche.values())
    out: dict[str, Any] = {"used": used}
    if rec.get("in_force"):
        out["returned_to_value"] = max(0, int(rec.get("pool") or 0) - used)
    plain = allocate(shippable, capacity, ranking=ranking)
    # AN UNKNOWN EV IS NEVER A ZERO (audit of 58765e3eb, should-fix). A family absent from the
    # ranking, or ranked with a missing or non-finite ev_per_cell, has no measured value per
    # cell; its displaced cells are counted, and the line's value reads UNMEASURED.
    ev: dict[str, float] = {}
    for r in ranking:
        raw = r.get("ev_per_cell")
        if isinstance(raw, (int, float)) and not isinstance(raw, bool) \
                and math.isfinite(float(raw)):
            ev[str(r.get("family"))] = float(raw)
    displaced = {f: n - quota.get(f, 0) for f, n in plain.items()
                 if f not in tranche and n - quota.get(f, 0) > 0}
    cells = sum(displaced.values())
    unvalued = {f: n for f, n in displaced.items() if f not in ev}
    priced = -sum(ev[f] * n for f, n in displaced.items() if f in ev)
    value: float | None = None if unvalued else round(priced, 10)
    line: dict[str, Any] = {
        "day": at.date().isoformat(), "at": at.isoformat(timespec="seconds"),
        "rail": "judge_tape_tranche", "kind": "opportunity_cost",
        "units": "expected value (ranking ev_per_cell x cells) of value-ranked judge cells the "
                 "tape tranche displaced this hour",
        "cells_displaced": cells, "by_family": dict(sorted(
            displaced.items(), key=lambda kv: -kv[1])[:20]),
        "tranche_cells": used, "value": value,
        "value_status": "UNMEASURED" if unvalued else "MEASURED",
        "unvalued_cells": sum(unvalued.values()),
        "value_priced_part": round(priced, 10),
        # BINDING IS KEYED ON CELLS, NOT ON VALUE: a displaced cell from a family valued at 0 or
        # not valued at all was still taken from the value walk, so it is never NOT_BINDING.
        "verdict": "COSTS_GROWTH" if cells > 0 else "NOT_BINDING",
        "why": ("the tape tranche (principal 2026-10-14) moves judge cells from the value "
                "remainder to the tape families; this is what that move forgoes at the "
                "ranking's own expected value. PUBLISHED in JUDGE_COVERAGE.json, never appended "
                "to data/missed_growth.jsonl (libs/portfolio/rails.py is sealed)")}
    if unvalued:
        line["why"] += (f"; {sum(unvalued.values())} displaced cells come from families with no "
                        "measured ev_per_cell, so the value is UNMEASURED (never a zero)")
    if not displaced and used == 0:
        line["why"] = f"tranche not in force this hour ({rec.get('why')}): nothing displaced"
    out["missed_growth_line"] = line
    return out


def tape_block(table: dict[str, dict[str, Any]], named_24h: dict[str, int],
               *, depth: dict[str, Any] | None = None,
               certs: tuple[dict[str, int] | None, str] | None = None) -> dict[str, Any]:
    """THE TAPE BLOCK of JUDGE_COVERAGE.json: does the tick tape produce certificates?

    Per derived tape family: mined, shippable, judged_total, named verdicts in the last 24 h,
    certificates and oldest unjudged age; the tape's depth in trading days against the need, with
    the ETA when short. UNMEASURED when the tape state (or the certificate canon) is absent --
    never a zero standing in for "nobody looked"."""
    fams = sorted(tape_families())
    depth = tape_depth() if depth is None else depth
    cert_counts, cert_src = tape_certificates() if certs is None else certs
    rows: dict[str, dict[str, Any]] = {}
    for f in fams:
        r = table.get(f) or {}
        rows[f] = {"mined": int(r.get("mined") or 0),
                   "shippable": int(r.get("shippable") or 0),
                   "quota": int(r.get("quota") or 0),
                   "tape_priority": int(r.get("tape_priority") or 0),
                   "judged_total": int(r.get("judged_total") or 0),
                   "named_verdicts_24h": int(named_24h.get(f, 0)),
                   "certificates": (int(cert_counts.get(f, 0)) if cert_counts is not None
                                    else None),
                   "oldest_unjudged_age_h": r.get("oldest_unjudged_age_h")}
    status = "MEASURED"
    why: list[str] = []
    if depth.get("status") != "MEASURED":
        status = "UNMEASURED"
        why.append(f"tape depth UNMEASURED: {depth.get('why')}")
    if cert_counts is None:
        status = "UNMEASURED"
        why.append(f"certificates UNMEASURED: {cert_src}")
    if not fams:
        status = "UNMEASURED"
        why.append("no tape family derived from the builders' code "
                   f"({(_TAPE_FAMILY_CACHE.get('prov') or {}).get('unreadable')})")
    return {"status": status, "why": "; ".join(why) or "measured",
            "families": rows,
            "derived_from": _TAPE_FAMILY_CACHE.get("prov"),
            "depth": depth,
            "certificate_source": cert_src,
            "certificates_total": (sum(int(v["certificates"] or 0) for v in rows.values())
                                   if cert_counts is not None else None),
            "judged_total": sum(v["judged_total"] for v in rows.values()),
            "named_verdicts_24h": sum(v["named_verdicts_24h"] for v in rows.values()),
            "priority_share": TAPE_PRIORITY_SHARE,
            "cert_min_judged": TAPE_CERT_MIN_JUDGED,
            "rule": ("tape families are DERIVED from the builders' source (a branch that calls "
                     f"{sorted(TAPE_READERS)}); after the {FLOOR_SHARE:.0%} breadth floor they "
                     "take "
                     f"up to {TAPE_PRIORITY_SHARE:.0%} of the hour before the value remainder, "
                     "which the sealed interleave reads as its WFQ weight (clamped there). "
                     "scripts/check_judge_coverage.py fails, armed, a tape family with mined cells "
                     "and no named verdict in 24 h once the tape meets the need, and tape families "
                     f"with 0 certificates past {TAPE_CERT_MIN_JUDGED} judged")}


def never_judged_families(table: dict[str, dict[str, Any]],
                          parked_by_reason: dict[str, dict[str, int]] | None = None,
                          parked_why: dict[str, str] | None = None,
                          census: dict[str, dict[str, dict[str, int]]] | None = None,
                          tape: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Every family with mined cells and judged_total 0, with its oldest wait and named reasons."""
    out: dict[str, dict[str, Any]] = {}
    hits = [f for f, r in table.items()
            if int(r.get("mined") or 0) > 0 and int(r.get("judged_total") or 0) == 0
            and r.get("judging_status") != "STUDY_ONLY"]
    if not hits:
        return out
    census = sweep_census_by_family() if census is None else census
    _tape_fams = tape_families()
    if tape is None and any(f in _tape_fams for f in hits):
        tape = tape_depth()
    for fam in sorted(hits, key=lambda f: -float(table[f].get("oldest_unjudged_age_h") or 0.0)):
        row = table[fam]
        parts: list[str] = []
        pk = (parked_by_reason or {}).get(fam) or {}
        if pk:
            parts.append("parked in the unrunnable bank (filtered from the docket): " + ", ".join(
                f"{k}={v}" for k, v in sorted(pk.items(), key=lambda kv: -kv[1])[:4])
                + (f" -- e.g. {(parked_why or {}).get(fam)}" if (parked_why or {}).get(fam)
                   else ""))
        cs = census.get(fam) or {}
        if cs:
            st = cs.get("status") or {}
            gates = cs.get("terminal_gate") or {}
            ur = cs.get("unknown_reason") or {}
            parts.append("last sweep: " + ", ".join(
                f"{k}={v}" for k, v in sorted({**gates, **st}.items(),
                                              key=lambda kv: -kv[1])[:5])
                + ((" ; UNKNOWN reasons " + ", ".join(
                    f"{k}={v}" for k, v in sorted(ur.items(), key=lambda kv: -kv[1])[:4]))
                   if ur else ""))
        elif census == {}:
            parts.append("last sweep: the sealed judge's report is absent here (UNMEASURED)")
        else:
            parts.append("last sweep: no verdict row for this family at all")
        if fam in _tape_fams and isinstance(tape, dict):
            if tape.get("status") == "MEASURED":
                parts.append(
                    f"input: conditions on the tick tape; median {tape.get('median_days')} / max "
                    f"{tape.get('max_days')} tape days per symbol against {tape.get('days_needed')}"
                    f" needed (60 development + lockbox floor); {tape.get('symbols_at_need')} of "
                    f"{tape.get('symbols')} symbols reach it")
            else:
                parts.append(f"input: conditions on the tick tape, {tape.get('why')}")
        if int(row.get("shippable") or 0) > 0 and int(row.get("quota") or 0) > 0:
            parts.append(f"{row.get('shippable')} cell(s) ship with quota {row.get('quota')}, so "
                         "the sealed judge receives them; its own build order decides reach")
        out[fam] = {"mined": int(row.get("mined") or 0),
                    "unjudged": int(row.get("unjudged") or 0),
                    "shippable": int(row.get("shippable") or 0),
                    "parked_unrunnable": int(row.get("parked_unrunnable") or 0),
                    "quota": int(row.get("quota") or 0),
                    "oldest_unjudged_age_h": row.get("oldest_unjudged_age_h"),
                    "reason": "; ".join(parts) if parts else "no published reason"}
    return out


#: Stages `build` may DEFER when its deadline has passed (`main --budget-s`). Each is a reading or
#: an ordering refinement whose input persists, so deferral is queueing, never loss: the priors'
#: cursor stays where it was, the k_eff/occupancy terms rank every row exactly as an unstamped
#: row does, and the never-judged census is re-derived next pass. The bank update, the backlog,
#: the quotas and the judging rate are never deferred.
DEFERRABLE_STAGES = ("learn_priors", "keff_stamp", "occupancy_stamp", "never_judged")
#: The share of the budget the ledger catch-up may use before the rest of the pass runs.
LEDGER_BUDGET_SHARE = 0.5


class _Budget:
    """A monotonic deadline checked between units of work; what is skipped is named."""

    def __init__(self, deadline: float | None) -> None:
        self.deadline = deadline
        self.deferred: list[str] = []

    def allow(self, stage: str) -> bool:
        if self.deadline is not None and time.monotonic() >= self.deadline:
            self.deferred.append(stage)
            return False
        return True


def build(docket: list[dict[str, Any]] | None = None, *, ledger: Path | None = None,
          ratchet: Path | None = None, now: datetime | None = None,
          defer: bool = False, deadline: float | None = None,
          ledger_deadline: float | None = None,
          stop: tuple[float, float] | None = None) -> dict[str, Any]:
    """The per-family coverage table, the quotas, and the carried-cohort ratchet.

    Run inside a pass memo, so each input file is parsed once however many readers need it.
    Every write the pass makes (priors, bank, readmission log, handoff) is staged in one
    transaction (`_Txn`). With `defer=False` it is committed when the table is built, exactly
    where those writes used to land. With `defer=True` it rides on the doc and `write` commits
    it TOGETHER with the report and the ratchet, so a pass killed before `write` changes nothing.

    TWO CLOCKS, ONE ORDER (merge resolution of judge-rate's budget with coverage v2.3's stop,
    2026-10-22). `deadline` / `ledger_deadline` are `time.monotonic()` instants (`main
    --budget-s`): the ledger catch-up stops at the second and leaves the rest of the file queued
    past its watermark; DEFERRABLE_STAGES are skipped past the first and named in `budget`, and
    the report is still written. `stop` is (start, stop) on the same clock, the later of the
    budget and the cycle's kill cap less the commit margin (`stop_after_s`): past it the pass
    raises `JudgeCoverageTimeout` and its staged writes are discarded. The deferral therefore
    always acts first; the stop is the backstop for a pass the deferral could not bring home.
    """
    global _GATES_MEMO
    outer = _GATES_MEMO is not None
    if not outer:
        _GATES_MEMO = {}
    _LEDGER_DEADLINE[:] = [ledger_deadline] if ledger_deadline is not None else []
    try:
        recover_transactions(ratchet)
        txn = _Txn((ratchet or RATCHET).parent)
        try:
            with _pass_memo() as memo:
                memo[("txn",)] = txn
                if stop is not None:
                    memo[("deadline",)] = stop
                doc = _build(docket, ledger=ledger, ratchet=ratchet, now=now,
                             budget=_Budget(deadline))
                memo.pop(("txn",), None)
        except BaseException:
            txn.discard()
            raise
    finally:
        _LEDGER_DEADLINE[:] = []
        if not outer:
            _GATES_MEMO = None
    if defer:
        doc["_txn"] = txn
    else:
        txn.commit()
    return doc


def _build(docket: list[dict[str, Any]] | None = None, *, ledger: Path | None = None,
           ratchet: Path | None = None, now: datetime | None = None,
           budget: _Budget | None = None) -> dict[str, Any]:
    at = now or datetime.now(tz=UTC)
    _fire_probe_reset()            # inputs are read afresh every pass, never across passes
    budget = budget or _Budget(None)
    rows = docket if docket is not None else (_read(DOCKET) or [])
    rows = [r for r in rows if isinstance(r, dict)]
    if not rows:
        return {"at": at.isoformat(timespec="seconds"), "verdict": "UNMEASURED",
                "why": "the judging docket is absent or empty -- nothing mined to cover",
                "families": {}, "totals": {}, "quota": {},
                "judging_rate": judging_rate(ledger, now=at)}

    _check_budget("docket_read")
    prior = _read(ratchet or RATCHET) or {}
    judged_cells, judged_total, judged_window = judged_index(ledger, now=at)
    _check_budget("ledger")
    bank_rows = unrunnable_bank()
    not_testable_ids = not_testable_index(bank_rows)
    _id_fn = _cell_id_fn()
    for row in rows:
        if _id_fn is None:
            row["_cell"] = None
            continue
        try:
            row["_cell"] = str(_id_fn(row))
        except Exception:
            row["_cell"] = None
    # `first_seen` parsed once per row: the backlog loop and the carried-cohort loop both read it.
    _seen_at: dict[Any, datetime | None] = {}

    def _first_seen(row: dict[str, Any]) -> datetime | None:
        raw = row.get("first_seen")
        k = (type(raw), raw)
        try:
            return _seen_at[k]
        except KeyError:
            v = _seen_at[k] = _ts(raw)
            return v
        except TypeError:                                   # an unhashable stamp: parse it
            return _ts(raw)

    _check_budget("cell_ids")
    mined = _mined(rows)
    banned = banned_from_capital()
    study_only: dict[str, int] = {}
    not_testable: dict[str, int] = {}
    not_testable_by_reason: dict[str, int] = {}
    backlog: dict[str, int] = {}
    oldest: dict[str, float | None] = {}
    unjudged_ids: set[str] = set()
    prior_fams = prior.get("families") if isinstance(prior, dict) else {}
    prior_fams = prior_fams if isinstance(prior_fams, dict) else {}
    prior_at_raw = _ts(prior.get("at") if isinstance(prior, dict) else None)
    # A PRIOR READING ON ANOTHER UNIT IS NO BASELINE (`BACKLOG_BASIS`). The first pass after the
    # not-testable class shipped would otherwise subtract a backlog that held the whole parked
    # stock from one that does not, and book the difference as an hour of drain. That pass
    # re-bases: carried, drained and the drain status are UNMEASURED, and the next pass ratchets.
    prior_basis = prior.get("backlog_basis") if isinstance(prior, dict) else None
    rebased = prior_at_raw is not None and prior_basis != BACKLOG_BASIS
    prior_at = None if rebased else prior_at_raw
    prior_ts = prior_at.timestamp() if prior_at is not None else None
    # THE CARRIED COHORT: rows already in the backlog at the previous reading and STILL unjudged.
    # It can only fall, because a cell leaves it exactly one way -- by being judged -- once the
    # two non-judging moves are booked by name: PARKED (the cell entered the not-testable class
    # since the prior reading, `not_testable_since`) leaves the cohort without a ruling, and
    # READMITTED (the prior pass's bank update returned it) joins it without being minted.
    # Counted in the SAME pass over the docket as the backlog (one walk of 1.6M rows, not two).
    carried: dict[str, int] = {}
    parked_since: dict[str, int] = {}
    for row in rows:
        fam = str(row.get("family") or "")
        cid = row.get("_cell")
        if cid and cid in judged_cells:
            continue
        if fam in banned:
            # NOT backlog: a cell that cannot reach the book is not work the judge owes. It is
            # counted, named and kept -- it is simply not something the hour is allocated to.
            study_only[fam] = study_only.get(fam, 0) + 1
            continue
        if prior_ts is not None:
            _seen = _first_seen(row)
            if _seen is not None and not _seen.timestamp() > prior_ts:
                if cid and cid in not_testable_ids:
                    _brow = bank_rows.get(str(cid)) or {}
                    _since = _ts(_brow.get("not_testable_since") or _brow.get("parked_at"))
                    if _since is not None and _since.timestamp() >= prior_ts:
                        parked_since[fam] = parked_since.get(fam, 0) + 1
                else:
                    carried[fam] = carried.get(fam, 0) + 1
        if cid and cid in not_testable_ids:
            # JUDGED TO THE LIMIT OF ITS DATA: named, counted, kept, and back in the backlog when
            # the bank re-admits it (`NOT_TESTABLE_REASONS`).
            not_testable[fam] = not_testable.get(fam, 0) + 1
            _r = not_testable_ids[cid]
            not_testable_by_reason[_r] = not_testable_by_reason.get(_r, 0) + 1
            continue
        backlog[fam] = backlog.get(fam, 0) + 1
        if cid:
            unjudged_ids.add(str(cid))
        seen = _first_seen(row)
        if seen is not None:
            age = max(0.0, (at.timestamp() - seen.timestamp()) / 3600.0)
            prev = oldest.get(fam)
            oldest[fam] = age if prev is None else max(prev, age)
        else:
            oldest.setdefault(fam, None)

    _check_budget("backlog")
    capacity = measured_capacity(judged_total, ledger, now=at)
    # TEACH THE PRIOR BEFORE SPENDING IT: every verdict since the last reading updates its
    # family's posterior, so the ranking below is spending a number this desk actually learned.
    _cursor = str((prior or {}).get("priors_cursor") or "")
    learned = (learn_priors(ledger, since=_cursor, now=at) if budget.allow("learn_priors") else
               {"status": "DEFERRED", "recorded": 0, "families": 0, "cursor": _cursor,
                "why": "the pass's --budget-s deadline passed: every row past the cursor waits"})
    realised_seen = realised_pass_rates(ledger)
    unknown = unknown_breakdown()
    named_unknowns = name_unknowns()
    not_run = name_not_run()
    unrunnable = update_unrunnable_bank({**named_unknowns, **not_run},
                                        at=at.isoformat(timespec="seconds"),
                                        code_fp=build_code_identity(), judged=judged_cells,
                                        report_mtime=_report_mtime())
    _bank_now = unrunnable_bank()
    failures = judging_failures(bank=_bank_now)
    _outstanding, _out_state = read_needs_data_outstanding()
    failures["handed_to_converter"] = write_conversion_handoff(
        _bank_now, at=at.isoformat(timespec="seconds"), outstanding=_outstanding)
    # The handoff count covers rows that could be READ; this says whether that is all of them.
    failures["needs_data_outstanding_state"] = _out_state
    bars_wanted: dict[str, int] = {}
    for _r in not_run.values():
        if _r.get("reason") == "data_missing":
            _k = f"{_r.get('sym')}_{_r.get('tf')}"
            bars_wanted[_k] = bars_wanted.get(_k, 0) + 1
    # MARGINAL k_eff, STAMPED BEFORE THE RANKING READS IT (research/docket_keff.py). Reorders
    # only: the family factor lifts a family's share of the remainder, the per-cell stamp orders
    # rows inside each family stream. Nothing is removed and the floor is untouched.
    _check_budget("bank")
    keff: dict[str, Any] = (keff_stamp(rows) if budget.allow("keff_stamp") else
                            {"status": "DEFERRED", "why": "the pass's --budget-s deadline passed"})
    # OCCUPANCY + ORTHOGONALITY, stamped beside k_eff (research/occupancy_map.py). Reorders only.
    occ: dict[str, Any] = (occupancy_stamp(rows) if budget.allow("occupancy_stamp") else
                           {"status": "DEFERRED", "why": "the pass's --budget-s deadline passed"})
    # THE QUOTA IS SPENT ON WHAT SHIPS (2026-10-14). `order_docket` removes every cell the
    # unrunnable bank holds before the docket is written, so a quota computed over the whole
    # backlog promised hours to cells the sealed judge never receives: measured on the box
    # 2026-10-13, 230,180 rows filtered from the docket while `queued` still claimed them, and the
    # raw COT families -- ranked first on an unlearned prior, each given its WHOLE backlog -- held
    # 0 judged. The backlog, the cohort and the drain are unchanged (a parked defect is still owed,
    # audit of PR #290); only the allocation and the shipped head now describe the docket the
    # judge reads, and every parked cell is published per family with its named reason.
    parked_unrunnable, parked_by_reason, parked_why = parked_in_bank(
        rows, _bank_now, judged_cells, not_testable_ids, banned)
    shippable = {f: max(0, n - parked_unrunnable.get(f, 0)) for f, n in backlog.items()}
    ranking = rank_by_value(backlog, rows, capacity)
    tape_fams = tape_families()
    tape_depth_now = tape_depth(now=at) if tape_fams else {"status": "UNMEASURED",
                                                           "why": "no tape family derived"}
    tape_tranche: dict[str, int] = {}
    tranche_rec = tape_tranche_gate(tape_fams, shippable, capacity, tape_depth_now)
    quota = allocate(shippable, capacity, ranking=ranking,
                     priority=frozenset(tranche_rec["families"]),
                     tranche_out=tape_tranche)
    tranche_rec.update(tape_tranche_missed_growth(
        shippable, capacity, ranking, quota, tape_tranche, tranche_rec, at=at))
    _check_budget("ranking")
    judgeable = [r for r in rows if str(r.get("family") or "") not in banned
                 and str(r.get("_cell") or "") not in _bank_now]
    study_rows = [r for r in rows if str(r.get("family") or "") in banned]
    # Mark the variants BEFORE the order is taken, so the head this table reports is the head
    # that actually ships (`order_docket` re-derives the same marks and measures what they freed).
    variant_split(judgeable, unjudged_ids)
    # Only the head is read here (the queued census and the k_eff head census both stop at
    # `capacity`), so the interleave stops there too; `order_docket` takes the whole order.
    ordered = coverage_order(judgeable, quota, unjudged_ids,
                             limit=max(int(capacity), 0)) + study_rows
    head = ordered[:capacity]
    _check_budget("order")
    if keff.get("status") == "MEASURED":
        dk = _docket_keff()
        if dk is not None:
            keff["head"] = {"shipped": dk.head_census(ordered, capacity, keff.get("_terms") or {})}
    queued: dict[str, int] = {}
    for row in head:
        fam = str(row.get("family") or "")
        queued[fam] = queued.get(fam, 0) + 1


    fams = sorted(set(mined) | set(backlog) | set(judged_window) | live_families())
    table: dict[str, dict[str, Any]] = {}
    for fam in fams:
        if not fam:
            continue
        back = backlog.get(fam, 0)
        q = quota.get(fam, 0)
        # A FAMILY'S OWN WINDOW: the hours its own quota needs to drain its own backlog. A family
        # of 55,190 cells is not starved for being large, and a family of nine is not excused for
        # being small -- each is held to the clock its own size implies, floored at the hour.
        window = WINDOW_H if q <= 0 else max(WINDOW_H, back / max(q, 1) * WINDOW_H)
        was = int(prior_fams.get(fam, {}).get("unjudged", 0)) if isinstance(
            prior_fams.get(fam), dict) else 0
        readm = int(prior_fams.get(fam, {}).get("readmitted_to_next", 0) or 0) if isinstance(
            prior_fams.get(fam), dict) else 0
        parked_f = parked_since.get(fam, 0)
        # The cohort the prior reading handed this one, on today's unit: what it held, plus what
        # its bank update re-admitted, minus what was parked since. Drain is measured against it.
        base = was + readm - parked_f
        table[fam] = {
            "mined": mined.get(fam, 0),
            "queued": queued.get(fam, 0),
            # What the docket actually carries for this family, and what the bank holds back
            # from it by named reason (`parked_in_bank`). unjudged = shippable + parked_unrunnable.
            "shippable": shippable.get(fam, 0),
            "parked_unrunnable": parked_unrunnable.get(fam, 0),
            "parked_by_reason": dict(sorted((parked_by_reason.get(fam) or {}).items())),
            "judged_window": judged_window.get(fam, 0),
            "judged_total": judged_total.get(fam, 0),
            "unjudged": back,
            "not_testable": not_testable.get(fam, 0),
            "oldest_unjudged_age_h": (round(float(oldest[fam] or 0.0), 2)
                                      if oldest.get(fam) is not None else None),
            "quota": q,
            "window_h": round(window, 2),
            "carried": carried.get(fam, 0) if prior_at is not None else None,
            "prior_unjudged": was if prior_at is not None else None,
            "parked_since_prior": parked_f if prior_at is not None else None,
            "readmitted_since_prior": readm if prior_at is not None else None,
            "cohort_base": base if prior_at is not None else None,
            # Re-admitted by THIS pass's bank update: backlog again from the next reading.
            "readmitted_to_next": int((unrunnable.get("readmitted_not_testable_by_family")
                                       or {}).get(fam, 0)),
            # The previous reading's oldest age, so the fence can ask the only question about an
            # age that a clock cannot answer for itself: is the oldest cell FALLING. An age rises
            # by the wall time between two readings whatever the desk does -- the coverage-drain
            # fence failed on exactly that and the lesson is written there -- so what is ratcheted
            # is movement, never the raw number.
            "prior_oldest_age_h": (prior_fams.get(fam, {}).get("oldest_unjudged_age_h")
                                   if isinstance(prior_fams.get(fam), dict) else None),
            "drained": ((base - carried.get(fam, 0)) if (prior_at is not None and base > 0)
                        else None),
        }
        if fam in banned:
            table[fam]["judging_status"] = "STUDY_ONLY"
            table[fam]["study_only"] = study_only.get(fam, 0)
            table[fam]["judging_reason"] = (
                f"family {fam!r} is banned from live capital (mt5desk/live_policy.py "
                "DEFAULT_BANNED_FAMILIES) and refused at both live doors, so it cannot reach "
                "the book even if it passes and is given no share of the scarce judge. Mining "
                "is unrestricted; the rows are kept in data/hypotheses/study_bank.json")

    # NO FIXED FAMILY SET. The table's rows come from the LIVE registry unioned with whatever the
    # docket and the ledger name, so a family registered tomorrow has a row the same hour -- with
    # `mined: 0` until a miner reaches it, which is a measurement of the miners and not of this
    # organ. It is published, never failed on: intake allocates the judge, it does not mine.
    unmined = sorted(f for f in live_families() if f and table.get(f, {}).get("mined", 0) == 0)
    # THE PREVIOUS READING'S UNKNOWN SHARE, so the fence can ratchet it: this quantity is a
    # SHARE and not a count, because a count rises with throughput and throughput rising is the
    # desk working. The share falls only when fewer never-firing specs reach the judge.
    # A PRIOR READ ON ANOTHER DENOMINATOR IS NO BASELINE: the move from all-rows to judged-only
    # lifts the share several-fold with nothing changing on the desk, and ratcheting across it
    # would fail the fence for a unit conversion. It re-enters as a first reading instead.
    prior_unknown_share = (prior.get("unknown_share")
                           if isinstance(prior, dict)
                           and prior.get("unknown_share_basis") == UNKNOWN_SHARE_BASIS
                           else None)
    # THE OPPORTUNITY COST, which is the number that makes this ROI rather than bookkeeping.
    # `value_at_risk` is the expected value sitting unjudged right now; `value_deferred` is the
    # part of it this hour cannot reach; `value_forgone_per_hour` is that deferred value spread
    # over the hours the current capacity needs to drain it -- the rate at which waiting costs
    # the desk. It is handed to `judging_throughput`, which is the organ that can DO something
    # about it: when the value at risk exceeds what an hour can judge, the box raises workers and
    # cadence. Nothing here throttles mining to make the number smaller.
    ev_cell = {str(r["family"]): float(r["ev_per_cell"]) for r in ranking}
    value_at_risk = sum(ev_cell.get(f, 0.0) * n for f, n in backlog.items())
    value_deferred = sum(ev_cell.get(f, 0.0) * max(0, n - quota.get(f, 0))
                         for f, n in backlog.items())
    total_backlog = sum(backlog.values())
    rate = sustained_rate(ledger, now=at)
    rate_doc = judging_rate(ledger, now=at)
    _ledger_catch = dict(rate_doc.get("ledger_index") or {})
    _prior_total = (sum(int(v.get("unjudged", 0)) for v in prior_fams.values()
                        if isinstance(v, dict)) if prior_at is not None else None)
    _parked_total = sum(parked_since.values()) if prior_at is not None else 0
    drain_eta = drain(total_backlog, rate.get("per_hour_24h"), prior_backlog=_prior_total,
                      prior_at=prior_at, now=at, parked=_parked_total,
                      rebased=(f"the prior reading's backlog basis is {prior_basis!r}, this "
                               f"one's {BACKLOG_BASIS!r}: re-based, drain unmeasured this pass"
                               if rebased else None))
    hours_to_drain = drain_eta.get("hours")
    _h_gross = drain_eta.get("hours_at_zero_creation")
    forgone_per_hour = (value_deferred / max(_h_gross or 1.0, 1.0) if _h_gross else 0.0)
    for row in ranking:
        fam = str(row["family"])
        row["quota"] = quota.get(fam, 0)
        row["shippable"] = shippable.get(fam, 0)
        row["floor"] = min(shippable.get(fam, 0), max(1, int(capacity * FLOOR_SHARE) // max(
            sum(1 for v in shippable.values() if v > 0), 1)))
        row["tape_priority"] = tape_tranche.get(fam, 0)
        row["remainder"] = max(0, row["quota"] - row["floor"] - row["tape_priority"])
        row["value_at_risk"] = row["ev_per_cell"] * row["unjudged"]
        row["value_deferred"] = row["ev_per_cell"] * max(0, row["unjudged"] - row["quota"])
    for fam, row in table.items():
        rk = next((r for r in ranking if r["family"] == fam), None)
        if rk is not None:
            row.update({"rank": rk["rank"], "ev_per_cell": rk["ev_per_cell"],
                        "ev_per_judge_second": rk["ev_per_judge_second"],
                        "p_optimistic": rk["p_optimistic"], "prior_status": rk["prior_status"],
                        "value_at_risk": rk["value_at_risk"],
                        "value_deferred": rk["value_deferred"],
                        "floor": rk["floor"], "remainder": rk["remainder"],
                        "tape_priority": rk["tape_priority"]})

    # NEVER JUDGED, NAMED (2026-10-14): every family that has mined cells and not one real
    # verdict, with the oldest wait and every reason this desk can read for it.
    for fam, row in table.items():
        row["tape_priority"] = tape_tranche.get(fam, 0)
    # A DEFERRED STEP IS NOT A ZERO (audit of 0bf4ce83e): when the budget skips this stage the
    # count is published as "DEFERRED", never `len({}) == 0` -- "no family is never-judged" is a
    # claim this pass did not measure. The fence keeps its own reading from the family table.
    never_judged_measured = budget.allow("never_judged")
    never_judged = (never_judged_families(table, parked_by_reason, parked_why)
                    if never_judged_measured else {})
    # THE TAPE BLOCK (2026-10-14): named verdicts per tape family in the last 24 h, read by the
    # same judged rule as `judged_index` (a real terminal gate or a pass; UNKNOWN never counts).
    _named_24h = judged_index(ledger, now=at, window_h=24.0)[2] if tape_fams else {}
    tape = tape_block(table, _named_24h, depth=tape_depth_now)
    tape["tranche"] = tranche_rec
    for fam, nj in never_judged.items():
        table[fam]["never_judged_reason"] = nj["reason"]
    # A family whose whole backlog is parked ships nothing and is given nothing: it is not
    # starved by the order, it is held by the bank with a named reason (and, if it has never
    # been judged at all, by the never-judged class above). Starvation is about SHIPPED cells.
    covered = sum(1 for f, r in table.items() if r["shippable"] > 0 and r["queued"] > 0)
    starved = sorted((f for f, r in table.items() if r["shippable"] > 0 and r["queued"] == 0),
                     key=lambda f: -table[f]["unjudged"])
    totals = {
        "docket_rows": len(rows),
        "mined": sum(mined.values()),
        "families_mined": sum(1 for r in table.values() if r["mined"] > 0),
        "families_live": len(live_families()),
        "families_unmined": len(unmined),
        "families_with_backlog": sum(1 for r in table.values() if r["unjudged"] > 0),
        "families_queued": covered,
        "families_starved": len(starved),
        "unjudged_total": sum(backlog.values()),
        "study_only_total": sum(study_only.values()),
        "study_only_families": sorted(study_only),
        "carried_total": sum(carried.values()) if prior_at is not None else None,
        "prior_unjudged_total": (sum(int(v.get("unjudged", 0)) for v in prior_fams.values()
                                     if isinstance(v, dict)) if prior_at is not None else None),
        "capacity_measured": capacity,
        "value_at_risk": value_at_risk,
        "value_deferred": value_deferred,
        "value_forgone_per_hour": forgone_per_hour,
        # capacity_measured above is the PEAK hour (the allocation size); these are the drain.
        "capacity_sustained_per_hour": rate.get("per_hour_24h"),
        "capacity_sustained_per_hour_7d": rate.get("per_hour_7d"),
        "drain_status": drain_eta.get("status"),
        "backlog_growth_per_hour": drain_eta.get("backlog_growth_per_hour"),
        "hours_to_drain": round(hours_to_drain, 3) if hours_to_drain else None,
        "hours_to_drain_at_zero_creation": drain_eta.get("hours_at_zero_creation"),
        "capacity_short": bool(drain_eta.get("status") in ("GROWING", "UNMEASURED")
                               or (hours_to_drain and hours_to_drain > 1.0)),
        # THE LARGEST SINGLE WASTE IN THE DESK, named and ratcheted: the share of the judge's own
        # verdicts that return no gate at all. Driven DOWN by the compiler that stops minting
        # never-firing specs, never by judging less.
        "unknown_share": unknown.get("unknown_share"),
        "unknown_share_basis": unknown.get("unknown_share_basis"),
        "unknown_share_of_all_rows": unknown.get("unknown_share_of_all_rows"),
        "unknown_total": unknown.get("unknown_total"),
        "judged_verdicts": unknown.get("judged_verdicts"),
        # The same class over the ledger's rolling windows -- the figure a git reading quotes.
        "unknown_share_24h": rate.get("unknown_share_24h"),
        "unknown_share_7d": rate.get("unknown_share_7d"),
        "unknown_counts_window": rate.get("unknown_counts"),
        "named_verdicts_per_hour_24h": rate.get("named_per_hour_24h"),
        "unknown_by_reason": unknown.get("by_reason"),
        "prior_unknown_share": prior_unknown_share,
        "never_fires_cells": ((unknown.get("causes") or {}).get("never_fires_days_0")
                              or {}).get("cells"),
        "unknown_unnamed": max(0, int(unknown.get("unknown_total") or 0)
                               - int(unknown.get("named_cells") or 0)),
        "not_run_named": len(not_run),
        "not_run_by_reason": dict(Counter(str(r.get("reason")) for r in not_run.values())),
        "prewarm_fail_share": _prewarm_share(),
        # ZERO / MISSING / STALE COST FIELDS (2026-10-13): priced as UNMEASURED, never as free.
        "cost_fields_unmeasured": _cost_fields_unmeasured(),
        "prior_prewarm_fail_share": (prior.get("prewarm_fail_share")
                                     if isinstance(prior, dict) else None),
        "prior_drain_status": (prior.get("drain_status") if isinstance(prior, dict) else None),
        "unrunnable_parked": unrunnable.get("parked_this_pass"),
        # THE BACKLOG'S UNIT and the non-judging moves, each its own figure, never drain.
        "backlog_basis": BACKLOG_BASIS,
        "backlog_rebased": rebased,
        "prior_backlog_basis": prior_basis if prior_at_raw is not None else None,
        "parked_not_testable_since_prior": (_parked_total if prior_at is not None else None),
        "readmitted_not_testable_since_prior": (
            sum(int(v.get("readmitted_to_next", 0) or 0) for v in prior_fams.values()
                if isinstance(v, dict)) if prior_at is not None else None),
        "readmitted_not_testable_to_next": unrunnable.get("readmitted_not_testable"),
        # OUT OF THE BACKLOG, NOT OUT OF THE RECORD: cells the judge ruled NOT TESTABLE (under 60
        # daily observations), per reason, until the bank re-admits them.
        "not_testable_total": sum(not_testable.values()),
        "not_testable_by_reason": not_testable_by_reason,
        "unrunnable_bank": unrunnable.get("bank_size"),
        "shippable_total": sum(shippable.values()),
        "parked_unrunnable_total": sum(parked_unrunnable.values()),
        "families_never_judged": len(never_judged) if never_judged_measured else "DEFERRED",
        # EVERY WAY THE JUDGE FAILED TO RULE, per class, each with its route out (no terminal
        # class exists): what the hourly pass reads to hunt judging's own unoptimalities.
        "judging_failures": failures,
        "oldest_unjudged_age_h": (round(max(v for v in oldest.values() if v is not None), 2)
                                  if any(v is not None for v in oldest.values()) else None),
        # THE RATE THE PRINCIPAL SET (150k verdicts/day), from the judge's own ledger.
        "verdicts_24h": rate_doc.get("verdicts_24h"),
        "judging_rate_target_per_day": JUDGING_RATE_TARGET_PER_DAY,
        "judging_rate_status": rate_doc.get("status"),
    }
    return {
        "at": at.isoformat(timespec="seconds"),
        "judging_rate": rate_doc,
        "budget": {"deadline_hit": bool(budget.deferred), "deferred_stages": budget.deferred,
                   "deferrable": list(DEFERRABLE_STAGES),
                   "ledger_index": _ledger_catch},
        "verdict": "COVERED" if not starved else "STARVED",
        "why": ("every family holding unjudged cells is in this hour's queue at its own quota"
                if not starved else
                f"{len(starved)} family(ies) hold unjudged cells and are absent from the queue: "
                f"{', '.join(starved[:5])}"),
        "rule": ("floor first (an equal share of "
                 f"{FLOOR_SHARE:.0%} of measured capacity to every family holding backlog), then "
                 "the remainder in proportion to backlog; the docket ships whole, interleaved, "
                 "so every prefix the judge's budget reaches is family-balanced"),
        "families": table,
        "totals": totals,
        "quota": quota,
        "starved": starved[:20],
        "never_judged": never_judged,
        "never_judged_status": "MEASURED" if never_judged_measured else "DEFERRED",
        "tape": tape,
        # THE TAPE TRANCHE'S MISSED-GROWTH LINE (audit of ad7d4ac6a): what the tranche took from
        # the value remainder, by family, at the ranking's own ev per cell. Published here in the
        # shape `research_departments` / `stop_geometry_derivation` use, never appended to
        # data/missed_growth.jsonl (that ledger is keyed by the sealed libs/portfolio/rails.RAILS).
        "missed_growth_lines": [tranche_rec["missed_growth_line"]],
        "never_judged_rule": (
            "a family with mined cells and judged_total 0 (no real terminal gate or pass ever "
            "recorded), with its oldest unjudged age and every reason published: cells parked "
            "in the unrunnable bank by reason, the last sweep's NOT_RUN / UNKNOWN status for the "
            "family, and any structural input the family's builder lacks. "
            "scripts/check_judge_coverage.py fails one older than "
            f"{NEVER_JUDGED_MAX_AGE_H:.0f}h on the box"),
        "unmined_live_families": unmined[:40],
        # THE RANKING IS PUBLISHED SO THE CHOICE IS INSPECTABLE -- and so the fence can check that
        # the remainder actually followed it, which is what stops a future session quietly
        # reverting this to round-robin.
        "priors_learned": learned,
        # THE AIM, BESIDE THE PRIOR THAT SET IT. Every family the judge has actually ruled on,
        # ordered by what it MEASURABLY did, so "the desk spent its largest block of judging on a
        # family that certified nothing" is a line anyone can read off the artifact instead of a
        # thing that has to be re-derived from 3,368 ledger rows.
        "realised_pass_rate": [
            {"family": f, "judged": int(r["judged"]), "passed": int(r["passed"]),
             "pass_rate": round(float(r["pass_rate"]), 6),
             "posterior_mean": round(float(r["mean"]), 6),
             "posterior_hi": round(float(r["hi"]), 6)}
            for f, r in sorted(realised_seen.items(),
                               key=lambda kv: (-float(kv[1]["pass_rate"]),
                                               -float(kv[1]["judged"]), kv[0]))],
        "realised_pass_rate_rule": (
            "counted from gate_verdict_ledger.jsonl every pass, so no cursor can make it stale; "
            "terminal_gate UNKNOWN is the sealed judge's UNMEASURED path and counts toward "
            "neither judged nor passed, because nobody looked is not a failure"),
        "unknown_reasons": unknown,
        "unrunnable": unrunnable,
        "keff_order": _keff_summary(keff),
        "_keff_detail": keff,
        "occupancy_order": occ,
        # THE BARS THE JUDGE ASKED FOR AND DID NOT HAVE, per symbol and chart: the demand the
        # bar refresh reads (research/refresh_bars.py) so a missing chart is fetched, not waited on.
        "bars_wanted": dict(sorted(bars_wanted.items(), key=lambda kv: -kv[1])),
        "value_ranking": ranking,
        "value_rule": ("remainder after every family's floor goes down expected value per "
                       "judge-second: p_optimistic (upper credible bound of the desk's own Beta "
                       "prior, so an unseen family is explored) x net-of-cost slot value "
                       "(NET_EDGE.json) x (1 + marginal breadth from EFFECTIVE_BREADTH cluster "
                       "occupancy) x keff_factor (1 + max(0, mean marginal-k_eff priority of the "
                       "family's cells, research/docket_keff.py)), divided by measured seconds "
                       "per cell x the family's bar cost"),
        "worst_backlog": [
            {"family": f, "unjudged": table[f]["unjudged"], "queued": table[f]["queued"],
             "oldest_unjudged_age_h": table[f]["oldest_unjudged_age_h"],
             "mined": table[f]["mined"]}
            for f in sorted(table, key=lambda f: -table[f]["unjudged"])[:10]
            if table[f]["unjudged"] > 0],
        "banned_routed_out": {
            "where": str(STUDY_BANK),
            "by": "research/merge_hypotheses.py (live_banned_families -> study bank)",
            "why": ("a family banned from live capital cannot reach the book even if it passes, "
                    "so the scarce judge is not spent on it; mining stays unrestricted and the "
                    "rows are kept, never deleted"),
        },
    }


#: A (family, symbol) pair whose parked cells include at least this many that NEVER fired, and
#: which has never produced one cell the judge could rule on, is a ground this family's rule
#: grammar does not reach on this instrument. Its remaining unseen cells go to the TAIL of the
#: docket -- still there, still judged whenever the head is exhausted, never dropped -- so the
#: hour's judge goes to cells that can fire first.
SIBLING_NEVER_FIRES_MIN = 20


def fired_pairs(path: Path | None = None) -> set[tuple[str, str]]:
    """(family, sym) pairs holding at least one verdict with a named gate -- they CAN fire."""
    return set(ledger_index(path).fired)


def never_fire_pairs(bank: dict[str, dict[str, Any]],
                     fired: set[tuple[str, str]]) -> set[tuple[str, str]]:
    counts: dict[tuple[str, str], int] = {}
    for row in bank.values():
        if row.get("reason") not in ("never_fires", "needs_data"):
            continue
        key = (str(row.get("family") or ""), str(row.get("sym") or ""))
        counts[key] = counts.get(key, 0) + 1
    return {k for k, n in counts.items() if n >= SIBLING_NEVER_FIRES_MIN and k not in fired}


def _row_sym(row: dict[str, Any]) -> str:
    return str(row.get("sym") or row.get("symbol") or "")


def fireability_order(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """THE INTAKE TAG: rows whose family provably cannot fire on today's inputs rank last.

    ORDER ONLY, the never_fire_ground rule applied before the first verdict instead of after the
    twentieth. Every row stays in the docket, minted and visible, and is judged -- and counted --
    by the sealed judge exactly as before whenever its turn comes; the published block names each
    held row's missing input. A NEEDS_DATA cell's family returns [] on any bars
    (`research/fire_inputs.py`), so its series is empty, adds no date to the lockbox union and
    enters no program matrix: moving it changes no other cell's verdict
    (`test_fire_prescreen_not_separable.py`). UNMEASURED probes are not tagged (fail open).
    """
    live: list[dict[str, Any]] = []
    tail: list[dict[str, Any]] = []
    by_family: dict[str, int] = {}
    by_input: dict[str, int] = {}
    probed = 0
    no_bars = 0
    for r in rows:
        fam, sym = str(r.get("family") or ""), _row_sym(r)
        res = _fire_probe(sym, fam)
        if res.get("status") != "UNMEASURED" or res.get("why") != "family not probed":
            probed += 1
        if res.get("status") == "NEEDS_DATA" and _bar_bytes(sym, _tf_of(r)) <= 0:
            # NO BARS EITHER (audit of c72ecfc53): 75 of 123 tagged cells had no bar file, so the
            # judge's build fails BY NAME and that failure is what asks for the bars. Tailing
            # such a row would defer the bar demand behind an input it does not yet bind on.
            live.append(r)
            no_bars += 1
        elif res.get("status") == "NEEDS_DATA":
            tail.append(r)
            by_family[fam] = by_family.get(fam, 0) + 1
            mi = str(res.get("missing_input") or "")
            by_input[mi] = by_input.get(mi, 0) + 1
        else:
            live.append(r)
    return live + tail, {
        "rows": len(rows), "rows_probed": probed, "rows_needs_data_to_tail": len(tail),
        "rows_needs_data_kept_no_bars": no_bars,
        "by_family": dict(sorted(by_family.items(), key=lambda kv: -kv[1])),
        "by_missing_input": dict(sorted(by_input.items(), key=lambda kv: -kv[1])[:40]),
        "rule": ("a row whose family's own input guard returns no signal on the inputs the "
                 "judge would hand it ranks after every other row; nothing dropped, nothing "
                 "skipped, every row still judged and counted by the sealed judge in its turn")}


def order_docket(rows: list[dict[str, Any]], *, publish: bool = True,
                 now: datetime | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """THE INTAKE CALL. Return the docket re-ordered for coverage, and the table it implies.

    `merge_hypotheses` calls this as the last thing it does before writing the file the sealed
    gauntlet reads, so the order the judge receives IS the allocation measured here -- the report
    describes the docket that actually shipped, not a plan for one. The rows are returned WHOLE:
    the same candidates, all of them, in an order where every prefix carries every family holding
    backlog. A failure here returns the rows untouched, because an ordering organ must never be
    able to cost the desk a docket (L1.28a).
    """
    with _pass_memo():
        return _order_docket(rows, publish=publish, now=now)


def _order_docket(rows: list[dict[str, Any]], *, publish: bool, now: datetime | None
                  ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    doc: dict[str, Any] | None = None
    try:
        doc = build(rows, now=now, defer=publish)
        if not doc.get("families"):
            _txn = doc.pop("_txn", None)
            if _txn is not None:
                _txn.commit()
            return rows, doc
        quota = {str(k): int(v) for k, v in (doc.get("quota") or {}).items()}
        banned = banned_from_capital()
        judged_cells, _, _ = judged_index(now=now)
        ids: set[str] = set()
        for row in rows:
            cid = row.get("_cell") or _cell_id(row)
            if cid and cid not in judged_cells:
                ids.add(str(cid))
        # THE UNRUNNABLE FILTER, at the one funnel every producer flows through (the principal,
        # 2026-09-23: "unrunnable specs back to the compiler's filter so they never reach the
        # docket again"). A cell the judge PROVED it cannot rule on is not re-submitted while
        # its symbol's history is unchanged; the moment those bars grow it is re-admitted
        # automatically. Nothing is deleted -- the bank keeps every row with its named reason.
        bank = unrunnable_bank()
        blocked = [r for r in rows if str(r.get("_cell") or "") in bank]
        rows = [r for r in rows if str(r.get("_cell") or "") not in bank]
        judgeable = [r for r in rows if str(r.get("family") or "") not in banned]
        study = [r for r in rows if str(r.get("family") or "") in banned]
        # CHARGE VARIANTS AGAINST THEIR PARENT. The split marks the rows; the two orders below
        # differ ONLY in whether that mark is read, so the difference in unseen mechanisms
        # inside the judge's measured capacity is exactly what the demotion freed. Nothing is
        # dropped in either order: both hold every row.
        split = variant_split(judgeable, ids)
        cap = int((doc.get("totals") or {}).get("capacity_measured") or 0)
        before = coverage_order(judgeable, quota, ids, demote_variants=False, use_keff=False,
                                use_occupancy=False)
        ordered_j = coverage_order(judgeable, quota, ids)
        # NEVER-FIRING GROUND TO THE TAIL (2026-09-30). Order only; every row stays.
        dead = never_fire_pairs(bank, fired_pairs())
        if dead:
            _live = [r for r in ordered_j
                     if (str(r.get("family") or ""), _row_sym(r)) not in dead]
            _tail = [r for r in ordered_j
                     if (str(r.get("family") or ""), _row_sym(r)) in dead]
            ordered_j = _live + _tail
            doc["never_fire_ground"] = {
                "pairs": len(dead), "rows_to_tail": len(_tail),
                "min_never_fires": SIBLING_NEVER_FIRES_MIN,
                "rule": ("a (family, symbol) with this many parked never-firing cells and no "
                         "verdict with a named gate ranks after every other row; nothing dropped")}
        ordered_j, doc["fireability"] = fireability_order(ordered_j)
        ordered = ordered_j + study
        was, now_ = _unseen_in_prefix(before, cap), _unseen_in_prefix(ordered_j, cap)
        # THE ORDERING EVIDENCE: what the judge's measured capacity head holds under the shipped
        # order against the legacy one (no variant demotion, no k_eff term). Same rows, same
        # quotas -- the difference is only which cells the hour reaches first.
        keff = doc.get("_keff_detail") or {}
        dk = _docket_keff()
        if keff.get("status") == "MEASURED" and dk is not None:
            terms = keff.get("_terms") or {}
            keff["head"] = {"capacity": cap,
                            "shipped": dk.head_census(ordered_j, cap, terms),
                            "legacy": dk.head_census(before, cap, terms)}
            doc["keff_order"] = _keff_summary(keff)
        occ = doc.get("occupancy_order") or {}
        om = _occupancy_map()
        if occ.get("status") == "MEASURED" and om is not None:
            occ["head"] = {"capacity": cap, "shipped": om.head_census(ordered_j, cap),
                           "legacy": om.head_census(before, cap)}
        doc["variant_demotion"] = {
            **split, "capacity": cap,
            "unseen_in_capacity_before": was, "unseen_in_capacity_after": now_,
            "slots_freed": now_ - was,
            "rule": ("a parameter variant of a rule already queued on the same family, symbol "
                     "and horizon ranks below an unseen mechanism inside its own family stream. "
                     "The queue is uncapped and no row is dropped; only the order changes"),
        }
        doc["unrunnable_filtered_from_docket"] = len(blocked)
        for _b in blocked:
            for _k in ("_cell", "_keff", "_occ", "_orth"):
                _b.pop(_k, None)
        # `orthogonality` (the published per-row score) is KEPT on the row; the ordering terms go.
        for row in ordered:
            for _k in ("_cell", "_variant", "_keff", "_occ", "_orth"):
                row.pop(_k, None)
        if publish:
            write(doc)
        return ordered, doc
    except Exception as exc:                                             # pragma: no cover
        # A deferred pass that failed after build must not leave its staging in live dirs.
        _left = doc.pop("_txn", None) if isinstance(doc, dict) else None
        if isinstance(_left, _Txn):
            _left.discard()
        return rows, {"verdict": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}


def write(doc: dict[str, Any], *, report: Path | None = None,
          ratchet: Path | None = None,
          deadline: tuple[float, float] | None = None) -> None:
    """Publish the table and advance the ratchet. A ratchet write is the NEXT reading's baseline.

    ONE COMMIT. The report, the k_eff order and the ratchet are staged with whatever the pass
    staged (`build(defer=True)`: priors, bank, readmission log, handoff) and committed together.
    A pass past its `deadline` raises `JudgeCoverageTimeout` here, before the commit point, and
    writes nothing.
    """
    txn = doc.pop("_txn", None)
    if not isinstance(txn, _Txn):
        recover_transactions(ratchet)
        txn = _Txn((ratchet or RATCHET).parent)
    try:
        _write_staged(doc, txn, report=report, ratchet=ratchet)
        if deadline is not None and time.monotonic() > deadline[1]:
            raise JudgeCoverageTimeout("commit", time.monotonic() - deadline[0])
    except BaseException:
        txn.discard()
        raise
    txn.commit()


def _write_staged(doc: dict[str, Any], txn: _Txn, *, report: Path | None,
                  ratchet: Path | None) -> None:
    target = report or REPORT
    target.parent.mkdir(parents=True, exist_ok=True)
    keff = doc.pop("_keff_detail", None)
    if isinstance(keff, dict) and keff.get("status") == "MEASURED" and report is None:
        dk = _docket_keff()
        if dk is not None:
            try:
                _kp = Path(dk.REPORT)
                _kp.parent.mkdir(parents=True, exist_ok=True)
                dk.publish(keff, path=txn.staged_path(_kp))
                txn.put_staged(_kp, txn.staged_path(_kp))
            except OSError as exc:
                doc.setdefault("keff_order", {})["publish_error"] = f"{type(exc).__name__}"
    txn.put_text(target, json.dumps(doc, indent=1, default=str))
    if report is None:
        # A completed pass clears the previous timeout's artifact in the same commit.
        txn.delete(TIMEOUT_REPORT)
    fams = doc.get("families") or {}
    state = {
        "at": doc.get("at"),
        "families": {f: {"unjudged": int(r.get("unjudged") or 0),
                         "queued": int(r.get("queued") or 0),
                         "oldest_unjudged_age_h": r.get("oldest_unjudged_age_h"),
                         "readmitted_to_next": int(r.get("readmitted_to_next") or 0)}
                     for f, r in fams.items()},
        "unjudged_total": (doc.get("totals") or {}).get("unjudged_total"),
        "backlog_basis": (doc.get("totals") or {}).get("backlog_basis"),
        "unknown_share": (doc.get("totals") or {}).get("unknown_share"),
        "unknown_share_basis": (doc.get("totals") or {}).get("unknown_share_basis"),
        "prewarm_fail_share": (doc.get("totals") or {}).get("prewarm_fail_share"),
        "drain_status": (doc.get("totals") or {}).get("drain_status"),
        "priors_cursor": (doc.get("priors_learned") or {}).get("cursor") or "",
        "why": ("the baseline the carried-cohort ratchet is measured against: rows already in "
                "this backlog and still unjudged at the next reading were STARVED, because a "
                "cell leaves a cohort exactly one way -- by being judged"),
    }
    rt = ratchet or RATCHET
    txn.put_text(rt, json.dumps(state, indent=1, default=str))


def render(doc: dict[str, Any]) -> list[str]:
    t = doc.get("totals") or {}
    jr = doc.get("judging_rate") or {}
    lines = [f"judge coverage: {doc.get('verdict')} -- {doc.get('why')}",
             f"  judging rate {jr.get('status')}: {jr.get('verdicts_24h')} verdicts in 24h vs "
             f"target {jr.get('target_per_day', JUDGING_RATE_TARGET_PER_DAY)}/day"
             + (f" (short {jr.get('shortfall_per_day')}/day)"
                if jr.get("meets_target") is False else ""),
             f"  families mined {t.get('families_mined')} / with backlog "
             f"{t.get('families_with_backlog')} / queued this hour {t.get('families_queued')}; "
             f"unjudged {t.get('unjudged_total')} on capacity {t.get('capacity_measured')}"]
    if t.get("unknown_share") is not None:
        _u = doc.get("unknown_reasons") or {}
        _w = t.get("unknown_share_7d")
        lines.append(f"  UNKNOWN {t.get('unknown_total')} of {_u.get('judged_verdicts')} judged "
                     f"({float(t.get('unknown_share') or 0):.1%}; "
                     f"{'n/a' if _w is None else f'{float(_w):.1%}'} over 7d), of which "
                     f"{t.get('never_fires_cells')} never fired at all; parked "
                     f"{(doc.get('unrunnable') or {}).get('parked_this_pass')}")
    lines.append(f"  value at risk {t.get('value_at_risk'):.3e} of which "
                 f"{t.get('value_deferred'):.3e} deferred; forgone "
                 f"{t.get('value_forgone_per_hour'):.3e}/h; drain "
                 f"{t.get('hours_to_drain')}h"
                 + ("  CAPACITY SHORT" if t.get("capacity_short") else ""))
    for row in (doc.get("value_ranking") or [])[:5]:
        lines.append(f"  #{row['rank']} {row['family']}: ev/judge-s "
                     f"{row['ev_per_judge_second']:.3e}"
                     f" p*={row['p_optimistic']:.3f} ({row['prior_status']}) quota {row['quota']}"
                     f" (floor {row['floor']} + {row['remainder']})")
    for row in (doc.get("worst_backlog") or [])[:5]:
        lines.append(f"  {row['family']}: mined {row['mined']} unjudged {row['unjudged']} "
                     f"queued {row['queued']} oldest {row['oldest_unjudged_age_h']}h")
    lines.append(render_tape(doc.get("tape")))
    # EVERY MISSED-GROWTH LINE IS PRINTED (audit of 58765e3eb, must-fix): a bill nobody reads
    # is not a bill. The tranche's own line is printed inside render_tape; any other line the
    # report carries is printed here, so the hourly leg's output shows all of them.
    tape_raw = doc.get("tape")
    tape: dict[str, Any] = tape_raw if isinstance(tape_raw, dict) else {}
    tranche_raw = tape.get("tranche")
    shown = tranche_raw.get("missed_growth_line") if isinstance(tranche_raw, dict) else None
    for ln in doc.get("missed_growth_lines") or []:
        if isinstance(ln, dict) and ln != shown:
            lines.append(render_missed_growth_line(ln))
    return lines


#: The exit code of a pass that stopped at its budget: a failure, never a verdict.
TIMEOUT_EXIT = 3
#: The exit code of a pass that met a committed manifest it could not safely roll forward.
RECOVERY_REFUSED_EXIT = 5
#: What a pass keeps in hand after its stop for the commit (renames, plus the report write).
COMMIT_MARGIN_S = 15.0


def stop_after_s(budget_s: float) -> tuple[float, float | None]:
    """(the second the pass stops itself at, the cycle's kill cap or None).

    THE PRODUCER NOW ENFORCES ITS BUDGET -- AND NEVER BELOW THE CAP THE CYCLE GRANTS. The hourly
    cycle tells the child its real kill cap in QUANT_LEG_BUDGET_S. That cap is at least
    `--budget-s` plus the write margin, because `_self_stop_floor_s` makes it so. Stopping at
    `--budget-s` itself would turn a pass that finishes inside the cap into a failure, opening a
    stale window the cycle never imposed. So the stop is the later of the declared budget and
    the cap minus the commit margin. Everything past that point is a kill the cycle would have
    made anyway, and the pass now meets it uncommitted and with a named TIMEOUT, never
    mid-write. Run by hand, with no cap given, the declared budget is the stop.
    """
    cap: float | None = None
    with contextlib.suppress(KeyError, TypeError, ValueError):
        cap = float(os.environ["QUANT_LEG_BUDGET_S"])
    if cap is None or cap <= 0:
        return float(budget_s), None
    return max(float(budget_s), cap - COMMIT_MARGIN_S), cap


def defer_deadline_s(budget_s: float | None, stop_s: float) -> float | None:
    """Seconds after start at which the pass DEFERS its deferrable stages (judge-rate's budget).

    It must fall before the hard stop with room to write, or the deferral never fires and the
    pass meets the stop as a TIMEOUT instead of publishing a deferred report (audit of
    2f28cf7de, SF1: run by hand with no QUANT_LEG_BUDGET_S, `stop_after_s` returns stop ==
    budget, so the two coincided). So it is the declared budget, but never later than the stop
    less COMMIT_MARGIN_S -- and never earlier than half the stop, so a tiny hand budget still
    leaves the pass time to work. No budget declared: no deferral (None), as before.
    """
    if not budget_s or budget_s <= 0:
        return None
    return min(float(budget_s), max(float(stop_s) - COMMIT_MARGIN_S, 0.5 * float(stop_s)))


def write_timeout(exc: JudgeCoverageTimeout, *, budget_s: float, stop_s: float,
                  cap_s: float | None, started: datetime,
                  path: Path | None = None) -> Path:
    """The TIMEOUT artifact: what stopped, where, and that nothing was committed. Atomic."""
    target = path or TIMEOUT_REPORT
    doc = {"at": started.isoformat(timespec="seconds"),
           "verdict": "TIMEOUT", "phase": exc.phase, "elapsed_s": round(exc.elapsed_s, 2),
           "budget_s": budget_s, "stop_s": round(stop_s, 2), "leg_cap_s": cap_s,
           "committed": False,
           "report_untouched": str(REPORT),
           "why": ("the pass reached its stop before its commit point; every staged write "
                   "(priors, bank, readmission log, handoff, report, ratchet) was discarded, so "
                   f"{REPORT.name} still carries the `at` of the pass it describes and the "
                   "fence's STALE_H lease ages it out -- it is never restamped as fresh")}
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1), "utf-8")
    _replace_retry(tmp, target)
    return target


#: The leg's verdict when it REUSES the coverage `merge_hypotheses` published this cycle.
REUSE_REPORT = REPORTS / "JUDGE_COVERAGE_REUSE.json"
#: The merge's own report: when it ran, for which cycle. Written after the docket, so a merge
#: that died before shipping its docket never leaves one stamped with this cycle.
MERGE_REPORT = HYP / "merge_report.json"
#: The exit of a leg that found no fresh same-cycle coverage to reuse. Non-zero: the cycle
#: books the leg FAILED, and the stale report stays stale under its own `at`.
REUSE_STALE_EXIT = 4
#: How far ahead of this clock a report's stamp may sit before it is read as not a reading.
REUSE_FUTURE_SKEW_S = 120.0


def _cycle_started_at() -> datetime | None:
    raw = os.environ.get("QUANT_PIPELINE_STARTED_AT", "").strip()
    return _ts(raw) if raw else None


def reuse_fresh(*, started_at: datetime | None = None, now: datetime | None = None,
                report: Path | None = None, ratchet: Path | None = None,
                merge_report: Path | None = None, docket: Path | None = None,
                out: Path | None = None) -> tuple[bool, dict[str, Any]]:
    """THE LEG'S SECOND COMPUTATION, REPLACED BY A CHECK OF THE FIRST.

    `merge_hypotheses` runs `order_docket` -> `build` -> `write` inside this same hourly cycle
    (`catch_up_intake`, before this leg), so the leg's own `build` + `write` was a second full
    computation of the same table, and on the box it is the one that was killed at its cap.
    This reads what the merge published and decides whether it IS this cycle's coverage. It
    never writes JUDGE_COVERAGE.json or the ratchet, so it cannot make an old table look new:
    the report keeps its own `at`, and `check_judge_coverage` ages it by that.

    FRESH means every one of these holds, and anything else FAILS CLOSED:
      * the cycle's start is known (QUANT_PIPELINE_STARTED_AT) -- with no cycle there is
        nothing to be fresh for;
      * the report parses, carries `variant_demotion` (only `order_docket` writes it, so this
        is the merge's table and not a hand run) and a non-empty `families`;
      * its `at` is a timestamp at or after the cycle's start, and not in the future;
      * the ratchet carries the same `at`, so both halves of that `write` landed;
      * `merge_report.json` names this cycle, started no later than the report, and was
        written after it -- so the docket the table describes is the docket that shipped.

    Returns (fresh, verdict); the verdict is also written to `out` (JUDGE_COVERAGE_REUSE.json)
    atomically, whichever way it goes.
    """
    t = now or datetime.now(tz=UTC)
    started = started_at if started_at is not None else _cycle_started_at()
    rp, rt = report or REPORT, ratchet or RATCHET
    mp, dp = merge_report or MERGE_REPORT, docket or DOCKET
    why: list[str] = []
    verdict: dict[str, Any] = {
        "at": t.isoformat(timespec="seconds"), "mode": "reuse_merge_coverage",
        "cycle_started_at": started.isoformat(timespec="seconds") if started else None,
        "report": str(rp), "report_untouched": True}

    def _load(path: Path) -> Any:
        try:
            return json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            return None

    def _mtime(path: Path) -> float | None:
        try:
            return path.stat().st_mtime
        except OSError:
            return None

    doc = _load(rp)
    rep_at = _ts(doc.get("at")) if isinstance(doc, dict) else None
    verdict["report_at"] = rep_at.isoformat(timespec="seconds") if rep_at else None
    if started is None:
        why.append("no cycle start (QUANT_PIPELINE_STARTED_AT unset or not a timestamp)")
    if not isinstance(doc, dict):
        why.append("JUDGE_COVERAGE.json missing or unreadable")
    else:
        if rep_at is None:
            why.append("report `at` missing or not a timestamp")
        if "variant_demotion" not in doc:
            why.append("report was not written by order_docket (no variant_demotion)")
        if not doc.get("families"):
            why.append("report holds no families")
    if rep_at is not None:
        if started is not None and rep_at < started.replace(microsecond=0):
            why.append("report predates this cycle")
        if (rep_at - t).total_seconds() > REUSE_FUTURE_SKEW_S:
            why.append("report `at` is in the future")
    rdoc = _load(rt)
    if rep_at is not None and (not isinstance(rdoc, dict) or _ts(rdoc.get("at")) != rep_at):
        why.append("ratchet does not carry the report's `at` (the write did not complete)")
    mdoc = _load(mp)
    m_cycle = _ts(mdoc.get("pipeline_started_at")) if isinstance(mdoc, dict) else None
    m_at = _ts(mdoc.get("merged_at")) if isinstance(mdoc, dict) else None
    if not isinstance(mdoc, dict):
        why.append("merge_report.json missing or unreadable")
    else:
        if started is None or m_cycle != started.replace(microsecond=0):
            why.append("merge_report.json is not this cycle's")
        if m_at is None or (rep_at is not None and m_at > rep_at):
            why.append("merge_report.json did not start before the report")
    r_m, m_m, d_m = _mtime(rp), _mtime(mp), _mtime(dp)
    if r_m is not None and (m_m is None or m_m < r_m or d_m is None or d_m < r_m):
        why.append("the docket or merge report was not written after the coverage report "
                   "(the merge that ordered it did not ship)")
    fresh = not why
    verdict["verdict"] = "REUSED" if fresh else "STALE"
    verdict["fresh"] = fresh
    if rep_at is not None:
        verdict["report_age_s"] = round((t - rep_at).total_seconds(), 1)
    if why:
        verdict["why"] = why
    target = out or REUSE_REPORT
    with contextlib.suppress(OSError):
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f"{target.name}.tmp-{os.getpid()}")
        tmp.write_text(json.dumps(verdict, indent=1), "utf-8")
        _replace_retry(tmp, target)
    return fresh, verdict


def render_missed_growth_line(line: dict[str, Any]) -> str:
    """One missed-growth line: rail, verdict, cells displaced, value (UNMEASURED, never 0)."""
    value = line.get("value")
    shown = ("UNMEASURED" if not isinstance(value, (int, float))
             else f"{float(value):.3e}")
    by = line.get("by_family") or {}
    top = ", ".join(f"{f} {n}" for f, n in list(by.items())[:3])
    return (f"  missed growth [{line.get('rail')}] {line.get('verdict')}: "
            f"{line.get('cells_displaced')} cells displaced"
            + (f" ({top})" if top else "")
            + f", value {shown}"
            + (f" ({line.get('unvalued_cells')} cells unvalued)"
               if line.get("unvalued_cells") else ""))


def render_tranche(tranche: Any) -> list[str]:
    """The tape tranche: share given, used, returned to value, displaced, and its bill."""
    if not isinstance(tranche, dict):
        return ["  tape tranche: UNMEASURED -- this report carries no tranche record"]
    line = tranche.get("missed_growth_line")
    displaced = line.get("cells_displaced") if isinstance(line, dict) else None
    value = line.get("value") if isinstance(line, dict) else None
    out = [f"  tape tranche [{'IN FORCE' if tranche.get('in_force') else 'RETURNED'}]: share "
           f"{tranche.get('share')} given (pool {tranche.get('pool')} cells), used "
           f"{tranche.get('used')}, returned to value {tranche.get('returned_to_value')}, "
           f"cells displaced {displaced}, value "
           f"{'UNMEASURED' if not isinstance(value, (int, float)) else f'{float(value):.3e}'}"
           f" -- {tranche.get('why')}"]
    if isinstance(line, dict):
        out.append(render_missed_growth_line(line))
    else:
        out.append("  missed growth [judge_tape_tranche] UNMEASURED: no line on this report")
    return out


def render_tape(tape: Any) -> str:
    """The tape block: depth vs need (ETA), judged, named 24 h, certificates; then the tranche
    (share given, used, returned, cells displaced, value) and its missed-growth line."""
    if not isinstance(tape, dict):
        return "  tape: UNMEASURED -- this report carries no tape block"
    d = tape.get("depth") or {}
    depth = (f"depth {d.get('max_days')} max / {d.get('median_days')} median trading days vs "
             f"{d.get('days_needed')} needed ({d.get('symbols_at_need')}/{d.get('symbols')} "
             f"symbols at need; ETA {d.get('eta_days_to_judgeable')}d)"
             if d.get("status") == "MEASURED" else f"depth UNMEASURED ({d.get('why')})")
    fams = ", ".join(f"{f} judged {r.get('judged_total')} / 24h {r.get('named_verdicts_24h')} / "
                     f"certs {r.get('certificates')}"
                     for f, r in sorted((tape.get("families") or {}).items()))
    head = (f"  tape [{tape.get('status')}]: {depth}; certificates "
            f"{tape.get('certificates_total')}; {fams or 'no tape family derived'}")
    return "\n".join([head, *render_tranche(tape.get("tranche"))])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="judge coverage by unjudged backlog, per family")
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg's mode)")
    ap.add_argument("--budget-s", type=float, default=120.0,
                    help="the pass stops itself, UNCOMMITTED, with reports/"
                         "JUDGE_COVERAGE_TIMEOUT.json and exit 3, at the later of this and the "
                         "cycle's kill cap (QUANT_LEG_BUDGET_S) minus the commit margin")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-write", action="store_true", help="measure without advancing the ratchet")
    ap.add_argument("--reuse-fresh", action="store_true",
                    help="compute nothing: verify that merge_hypotheses published this cycle's "
                         "coverage and exit 0, or exit 4 with JUDGE_COVERAGE_REUSE.json naming "
                         "why not. Never writes the report or the ratchet")
    args = ap.parse_args(argv)
    if args.reuse_fresh:
        fresh, verdict = reuse_fresh()
        print(json.dumps(verdict, indent=1) if args.json else
              f"judge coverage: {verdict['verdict']} report_at={verdict.get('report_at')} "
              f"cycle={verdict.get('cycle_started_at')}"
              + ("" if fresh else " -- " + "; ".join(verdict.get("why") or [])))
        return 0 if fresh else REUSE_STALE_EXIT
    t0 = time.time()
    # --budget-s IS ENFORCED (2026-10-14). It used to be stamped into the report and never read,
    # while the hourly_cycle comment said the leg "stops itself" at it; the leg ran into its 300 s
    # cap instead and the report, written only at the end, went stale for days. Now the ledger
    # catch-up stops at LEDGER_BUDGET_SHARE of the budget (the unread tail stays queued past the
    # watermark) and DEFERRABLE_STAGES are skipped past the budget, so the report is written.
    # The hard stop (`stop_after_s`, coverage v2.3) stays behind both as the backstop: a pass
    # still running at the later of the budget and the cycle's cap less the commit margin is
    # discarded whole, never committed half-written (merge resolution, 2026-10-22).
    stop_s, cap_s = stop_after_s(args.budget_s)
    m0 = time.monotonic()
    stop = (m0, m0 + stop_s)
    # The deferral deadline sits inside the stop with the commit margin in hand (SF1).
    budget_s = defer_deadline_s(args.budget_s, stop_s)
    try:
        # Always deferred: --no-write then DISCARDS the pass's staging, so it saves nothing of
        # its own (audit of v2.1: it used to commit priors, bank and handoff without the
        # cursor). Recovery of an earlier pass's committed manifest still runs first, as it
        # must before anything reads.
        doc = build(defer=True, stop=stop,
                    deadline=(m0 + budget_s) if budget_s else None,
                    ledger_deadline=(m0 + budget_s * LEDGER_BUDGET_SHARE) if budget_s else None)
        doc["elapsed_s"] = round(time.time() - t0, 2)
        doc["budget_s"] = args.budget_s
        doc["budget_enforced"] = budget_s is not None
        doc["defer_deadline_s"] = round(budget_s, 3) if budget_s else None
        if not args.no_write:
            write(doc, deadline=stop)
        else:
            _staged = doc.pop("_txn", None)
            if isinstance(_staged, _Txn):
                _staged.discard()
    except TxnRecoveryRefused as exc:
        print(f"judge coverage: RECOVERY REFUSED -- {exc}; nothing read or written. Resolve "
              f"the kept manifest by hand", file=sys.stderr, flush=True)
        return RECOVERY_REFUSED_EXIT
    except JudgeCoverageTimeout as exc:
        out = write_timeout(exc, budget_s=args.budget_s, stop_s=stop_s, cap_s=cap_s,
                            started=datetime.fromtimestamp(t0, tz=UTC))
        print(f"judge coverage: TIMEOUT -- {exc}; nothing committed, {REPORT.name} left as it "
              f"was (its own `at` ages it out); see {out.name}", flush=True)
        return TIMEOUT_EXIT
    if args.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        for line in render(doc):
            print(line)
    return 0


__all__ = [
    "allocate",
    "banned_from_capital",
    "build",
    "coverage_order",
    "family_breadth",
    "family_priors",
    "family_value",
    "grid_cell",
    "judge_seconds_per_cell",
    "judged_index",
    "learn_priors",
    "live_families",
    "main",
    "measured_capacity",
    "name_unknowns",
    "order_docket",
    "rank_by_value",
    "render",
    "render_missed_growth_line",
    "render_tape",
    "render_tranche",
    "reuse_fresh",
    "unknown_breakdown",
    "unrunnable_bank",
    "update_unrunnable_bank",
    "variant_split",
    "write",
]


if __name__ == "__main__":                                              # pragma: no cover
    sys.exit(main())
