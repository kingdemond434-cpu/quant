"""THE GATE LEDGER, READ ONCE: an incremental index with a byte watermark (2026-10-14).

WHY THIS EXISTS. `judge_coverage` asked the same append-only file -- `gate_verdict_ledger.jsonl`,
864k rows on the box on 2026-10-13 -- six separate questions per pass, and answered each with its
own full parse: `judged_index`, `measured_capacity`, `sustained_rate`, `realised_pass_rates`
(a whole-file `readlines()`), `fired_pairs` and `learn_priors` (another `readlines()`), and
`order_docket` asked `judged_index` a second time. Every one of those parses re-read rows that had
not changed since the previous pass, so the leg's cost grew with the ledger's LIFETIME, not with
what the judge wrote since it last looked -- and the leg stopped finishing inside its 300 s cap
(`staleness_2026-10-14.md`: three writes in ten days).

WHAT IT DOES. One pass over the ledger's NEW BYTES (from a persisted byte offset) folds each row
into the aggregates those six readers need, and the aggregates persist beside the watermark. Each
reader is then a lookup: O(rows appended since the last pass), not O(ledger).

  * `judged_cells`, `judged_total`, `passed_total` -- the all-time judged set and counts, under
    `judge_coverage.judged_index`'s rule (a named terminal gate or a pass; never NOT_RUN_*,
    never UNKNOWN);
  * `buckets` -- per verdict stamp (the sealed writer stamps ONE `at` per append, so one bucket
    per sweep): all rows, UNKNOWN rows, judged rows, judged rows per family. Every rolling window
    the readers use (1 h, 24 h, 168 h, the per-hour peak) is an EXACT sum over these, because a
    bucket's key is the row's own timestamp, not a rounded hour;
  * `fired_pairs` -- (family, symbol) pairs holding a named gate, under `fired_pairs`'s own
    line-level rule.

EXACTNESS, NOT APPROXIMATION. `tests/test_judge_rate.py` builds randomized ledgers (UNKNOWN rows,
NOT_RUN rows, string `passed`, missing stamps, malformed lines, non-dict rows, empty families) and
asserts every reader returns exactly what the old full-scan code returned, before and after an
incremental append.

A REWRITTEN LEDGER IS RE-READ FROM ZERO. The watermark carries a digest of the first and of the
last 4 KiB it consumed; a file that shrank, or whose bytes under the watermark changed, is
re-indexed from the start. A partial line at EOF (a writer mid-append) is left for the next pass.

A DEADLINE IS HONOURED BETWEEN CHUNKS (`catch_up(deadline=...)`): work not done stays in the file
past the watermark, and the next pass resumes there -- nothing is skipped, only deferred.
`complete` and `behind_bytes` say which.

Nothing here decides a verdict, reorders the judge or drops a cell. It is a faster way to read
what the sealed judge already wrote.
"""
from __future__ import annotations

import contextlib
import gc
import hashlib
import json
import os
import pickle
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: 2: naive stamps read as UTC (merge resolution 2026-10-22); an index persisted at 1 rebuilds.
#: 3: `max_ts` never passes the wall clock plus FUTURE_SKEW_S, and pruning is bounded by the wall
#:    clock too (audit of 2f28cf7de, MF1); an index persisted at 2 may hold a future-poisoned
#:    max_ts and pruned buckets, so it rebuilds from the ledger.
SCHEMA = 3
#: Bytes folded between two deadline checks. One chunk of ~8 MiB is ~40k ledger rows.
CHUNK_BYTES = 8 << 20
#: Bytes digested at the head of the file and just under the watermark to detect a rewrite.
FP_BYTES = 4096
#: Buckets older than this before the PRUNE REFERENCE are dropped: the newest stamp seen, but never
#: later than the wall clock plus FUTURE_SKEW_S. Every window the readers use is at most 168 h and
#: is measured back from the wall clock, so this keeps them exact with four weeks of margin.
KEEP_BUCKET_S = 35 * 86400.0
#: A stamp further than this past the wall clock is a clock fault or a forged row, not the newest
#: verdict. It is still counted in its own bucket (every window reader sees exactly the rows it
#: saw before), but it never becomes `max_ts` and never moves the prune line. Without this bound a
#: single row stamped 35+ days ahead pruned every real bucket for good (audit of 2f28cf7de: 31
#: verdicts in 24 h read 1). The same tolerance as the desk's other future-stamp refusals.
FUTURE_SKEW_S = 300.0
#: Wall clock, a module hook so a test can move it.
_wall = time.time
NOT_JUDGED_PREFIX = "NOT_RUN"


def _ts(raw: object) -> float | None:
    """Same parse as `judge_coverage._ts`, as a POSIX timestamp.

    A stamp with no offset is UTC -- the desk's writers stamp UTC -- never this machine's local
    time (coverage v2.3's rule for every ledger reader; restated here when the index replaced
    those readers, merge resolution 2026-10-22). `astimezone` on a naive stamp would have read
    it as local time and shifted it by the box's offset."""
    txt = str(raw or "").strip()
    if not txt:
        return None
    try:
        t = datetime.fromisoformat(txt.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (t.replace(tzinfo=UTC) if t.tzinfo is None else t).astimezone(UTC).timestamp()


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class LedgerIndex:
    """Aggregates of one gate ledger up to a byte watermark. See the module docstring."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.reset()

    # ------------------------------------------------------------------ state
    def reset(self) -> None:
        self.offset = 0
        self.head_fp = ""
        self.tail_fp = ""
        self.rows_read = 0
        self.judged_cells: set[str] = set()
        self.judged_total: dict[str, int] = {}
        self.passed_total: dict[str, int] = {}
        # ts -> [all, unknown, judged, {family: judged}]
        self.buckets: dict[float, list[Any]] = {}
        self.fired: set[tuple[str, str]] = set()
        self.max_ts = 0.0
        # The newest stamp `max_ts` may take; refreshed from the wall clock per folded chunk.
        self._horizon = _wall() + FUTURE_SKEW_S
        self.complete = True
        self.behind_bytes = 0
        self.last_catch_up: dict[str, Any] = {}

    def _state(self) -> dict[str, Any]:
        return {"schema": SCHEMA, "path": str(self.path), "offset": self.offset,
                "head_fp": self.head_fp, "tail_fp": self.tail_fp, "rows_read": self.rows_read,
                # One newline-joined string, not a pickled set, which loads several times
                # faster; a set only if some cell id ever carried a newline.
                "judged_cells": (self.judged_cells
                                 if any("\n" in c for c in self.judged_cells)
                                 else "\n".join(self.judged_cells)),
                "judged_total": self.judged_total,
                "passed_total": self.passed_total, "buckets": self.buckets,
                "fired": self.fired, "max_ts": self.max_ts}

    @classmethod
    def load(cls, path: Path, state: Path | None = None) -> LedgerIndex:
        """The persisted index for `path`, or an empty one. Never raises."""
        idx = cls(path)
        if state is None:
            return idx
        gc_was = gc.isenabled()
        gc.disable()            # millions of small objects: the collector would re-walk them
        try:
            with state.open("rb") as fh:
                doc = pickle.load(fh)  # noqa: S301 -- a box-local cache this module wrote
        except Exception:
            return idx
        finally:
            if gc_was:
                gc.enable()
        if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
            return idx
        try:
            idx.offset = int(doc["offset"])
            idx.head_fp = str(doc["head_fp"])
            idx.tail_fp = str(doc["tail_fp"])
            idx.rows_read = int(doc.get("rows_read") or 0)
            cells = doc["judged_cells"]
            idx.judged_cells = (set(cells.split("\n")) - {""} if isinstance(cells, str)
                                else set(cells))
            idx.judged_total = dict(doc["judged_total"])
            idx.passed_total = dict(doc["passed_total"])
            idx.buckets = dict(doc["buckets"])
            idx.fired = set(doc["fired"])
            idx.max_ts = float(doc.get("max_ts") or 0.0)
        except Exception:
            idx.reset()
        return idx

    def save(self, state: Path) -> None:
        """Persist atomically. A failed save costs the next pass a longer catch-up, nothing else."""
        try:
            state.parent.mkdir(parents=True, exist_ok=True)
            tmp = state.with_name(f"{state.name}.{os.getpid()}.tmp")
            gc_was = gc.isenabled()
            gc.disable()
            try:
                with tmp.open("wb") as fh:
                    pickle.dump(self._state(), fh, protocol=pickle.HIGHEST_PROTOCOL)
            finally:
                if gc_was:
                    gc.enable()
            os.replace(tmp, state)
        except OSError:
            with contextlib.suppress(OSError, UnboundLocalError):
                tmp.unlink(missing_ok=True)

    # ------------------------------------------------------------------ folding
    def _fold_line(self, line: str) -> None:
        """One ledger line, under every reader's own rule (see the module docstring)."""
        if not line.strip():
            return
        unknown_text = '"UNKNOWN"' in line
        try:
            row = json.loads(line.strip())
        except ValueError:
            return
        if not isinstance(row, dict):
            return
        self.rows_read += 1
        # fired_pairs: line-level UNKNOWN skip, no NOT_RUN filter, a truthy terminal gate.
        if not unknown_text and row.get("terminal_gate"):
            self.fired.add((str(row.get("family") or ""), str(row.get("sym") or "")))
        if str(row.get("downstream_status") or "").startswith(NOT_JUDGED_PREFIX):
            return
        passed = row.get("passed")
        unk = passed is not True and str(row.get("terminal_gate") or "") in ("", "UNKNOWN")
        fam = str(row.get("family") or "")
        at = _ts(row.get("at"))
        b: list[Any] = []
        if at is not None:
            got = self.buckets.get(at)
            if got is None:
                got = self.buckets[at] = [0, 0, 0, {}]
            b = got
            b[0] += 1
            b[1] += int(unk)
            if self.max_ts < at <= self._horizon:
                self.max_ts = at
        if unk:
            return
        cell = str(row.get("cell") or "")
        if cell:
            self.judged_cells.add(cell)
        if at is not None:
            b[2] += 1
            if fam:
                b[3][fam] = b[3].get(fam, 0) + 1
        if not fam:
            return
        self.judged_total[fam] = self.judged_total.get(fam, 0) + 1
        if passed is True or str(passed).lower() == "true":
            self.passed_total[fam] = self.passed_total.get(fam, 0) + 1

    def _fold_bytes(self, data: bytes) -> None:
        self._horizon = _wall() + FUTURE_SKEW_S
        text = data.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
        for line in text.split("\n"):
            self._fold_line(line)

    def _prune(self) -> None:
        if not self.max_ts:
            return
        # Bounded by the wall clock as well as by max_ts: an index persisted before the bound
        # existed rebuilds (SCHEMA 3), and this keeps the prune line honest even so.
        cut = min(self.max_ts, _wall() + FUTURE_SKEW_S) - KEEP_BUCKET_S
        stale = [ts for ts in self.buckets if ts < cut]
        for ts in stale:
            del self.buckets[ts]

    def _still_valid(self, fh: Any, size: int) -> bool:
        if self.offset == 0:
            return True
        if size < self.offset:
            return False
        fh.seek(0)
        if _digest(fh.read(min(self.offset, FP_BYTES))) != self.head_fp:
            return False
        start = max(0, self.offset - FP_BYTES)
        fh.seek(start)
        return _digest(fh.read(self.offset - start)) == self.tail_fp

    def catch_up(self, *, deadline: float | None = None,
                 clock: Any = time.monotonic) -> dict[str, Any]:
        """Fold every byte past the watermark, chunk by chunk, until EOF or `deadline`.

        `deadline` is on `clock`'s scale (monotonic seconds by default). Returns what was done.
        An absent ledger is reported (`exists: False`) and leaves the index empty.
        """
        t0 = clock()
        out: dict[str, Any] = {"exists": self.path.exists(), "rebuilt": False,
                               "consumed_bytes": 0, "deadline_hit": False}
        try:
            fh = self.path.open("rb")
        except OSError:
            self.reset()
            out.update(complete=True, behind_bytes=0, seconds=round(clock() - t0, 3))
            self.last_catch_up = out
            return out
        with fh:
            size = os.fstat(fh.fileno()).st_size
            if not self._still_valid(fh, size):
                self.reset()
                out["rebuilt"] = True
            pos = self.offset
            fh.seek(pos)
            while pos < size:
                if deadline is not None and clock() >= deadline:
                    out["deadline_hit"] = True
                    break
                data = fh.read(min(CHUNK_BYTES, size - pos))
                if not data:
                    break
                cut = data.rfind(b"\n")
                if cut < 0 and pos + len(data) < size:
                    # A line longer than a chunk: read on to its end in one piece.
                    more = b""
                    while b"\n" not in more:
                        piece = fh.read(CHUNK_BYTES)
                        if not piece:
                            break
                        more += piece
                    data += more
                    cut = data.rfind(b"\n")
                if cut < 0:
                    # The EOF fragment: a complete JSON row a writer forgot to terminate is
                    # consumed; a half-written one waits for the rest of its bytes.
                    try:
                        whole = isinstance(json.loads(data.decode("utf-8", "replace")), dict)
                    except ValueError:
                        whole = not data.strip()
                    if not whole:
                        break
                    use = data
                else:
                    use = data[:cut + 1]
                self._fold_bytes(use)
                pos += len(use)
                fh.seek(pos)
                if cut >= 0 and pos >= size:
                    break
            if pos != self.offset or out["rebuilt"]:
                out["consumed_bytes"] = pos - (0 if out["rebuilt"] else self.offset)
                self.offset = pos
                fh.seek(0)
                self.head_fp = _digest(fh.read(min(pos, FP_BYTES)))
                start = max(0, pos - FP_BYTES)
                fh.seek(start)
                self.tail_fp = _digest(fh.read(pos - start))
        self._prune()
        self.behind_bytes = max(0, size - self.offset)
        # A trailing half-line is a writer mid-append, not work this pass skipped.
        self.complete = not out["deadline_hit"]
        out.update(complete=self.complete, behind_bytes=self.behind_bytes,
                   offset=self.offset, size=size, rows_read=self.rows_read,
                   seconds=round(clock() - t0, 3))
        self.last_catch_up = out
        return out

    # ------------------------------------------------------------------ readers
    def window_judged(self, cutoff: float) -> dict[str, int]:
        out: dict[str, int] = {}
        for ts, b in self.buckets.items():
            if ts >= cutoff:
                for fam, n in b[3].items():
                    out[fam] = out.get(fam, 0) + n
        return out

    def judged_per_hour(self, cutoff: float) -> dict[str, int]:
        """Judged rows per `%Y-%m-%dT%H` UTC hour, stamps at or after `cutoff`."""
        out: dict[str, int] = {}
        for ts, b in self.buckets.items():
            if ts >= cutoff and b[2]:
                key = datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H")
                out[key] = out.get(key, 0) + int(b[2])
        return out

    def hourly(self, first_hour: float, hours: int) -> list[tuple[float, int, int, int]]:
        """(hour start, all, UNKNOWN, judged) for `hours` clock hours from `first_hour`."""
        acc = {first_hour + 3600.0 * k: [0, 0, 0] for k in range(max(0, int(hours)))}
        last = first_hour + 3600.0 * max(0, int(hours))
        for ts, b in self.buckets.items():
            if first_hour <= ts < last:
                slot = acc[first_hour + 3600.0 * ((ts - first_hour) // 3600.0)]
                slot[0] += int(b[0])
                slot[1] += int(b[1])
                slot[2] += int(b[2])
        return [(h, v[0], v[1], v[2]) for h, v in sorted(acc.items())]

    def window_rows(self, cutoff: float, until: float | None = None) -> tuple[int, int, int]:
        """(all rows, UNKNOWN rows, judged rows) stamped in [cutoff, until]."""
        a = u = j = 0
        for ts, b in self.buckets.items():
            if ts >= cutoff and (until is None or ts <= until):
                a += int(b[0])
                u += int(b[1])
                j += int(b[2])
        return a, u, j


__all__ = ["CHUNK_BYTES", "FUTURE_SKEW_S", "KEEP_BUCKET_S", "SCHEMA", "LedgerIndex"]
