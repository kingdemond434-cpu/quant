"""THE STAGE-1 RECORD: one row per backlog cell the two-stage judge has ruled on, and its history.

`research/stage1_judge.py` writes it; the judge's feeders read it. It is stdlib-only (sqlite3,
json) on purpose, so the sealed gauntlet's sort key can read a cell's tier through a patch
(`/mnt/project-files/patches/two_stage_judge/`) without importing numpy or the organ.

WHY SQLITE AND NOT A JSON FILE. The trading box's backlog is ~1.4M cells. A JSON map of that many
ids is ~100 MB that every reader would decode whole -- the defect that makes
`gauntlet_backpressure` and `judging_throughput` time out on the box today. SQLite answers a point
lookup without reading the rest, appends a history row in O(1), and is bounded in memory for
every reader. The file is gitignored like `data/alpha_registry.sqlite`: it is box state.

A CELL IS NEVER DELETED. A stage-1 REJECT is a row with `verdict = 'REJECT_STAGE1'`; the cell
stays on the docket and in this record, and `due_for_rescreen` makes it eligible again when its
bars grow materially or its family's code changes. Every ruling also lands in `rulings` (append
only), which is the per-cell logged verdict.

TIERS, the one order every consumer uses (lower first):

  0  named priority     -- v4 re-mint cells (`priority_remint.json`) and evicted re-judges
                           (`priority_rejudge.json`): other agents' queues keep precedence.
  1  STAGE1_PASS        -- BH survivors of the training-window screen.
  2  STAGE1_FORWARD     -- forwarded UNSCREENED: the cell has >= 60 days but its training window
                           is too short to test, so it goes to the full judge rather than being
                           rejected without evidence.
  3  NOT_YET_RULED      -- the rest of the never-judged backlog, oldest first.
  4  STAGE1_REJECT      -- ruled against (or UNBUILDABLE); judged last, never dropped.
"""
from __future__ import annotations

import contextlib
import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
DB = DESK / "data" / "stage1" / "stage1_record.sqlite"
HYP = DESK / "data" / "hypotheses"
#: Other agents' priority queues, read only (never written here).
PRIORITY_FILES = (HYP / "priority_remint.json", HYP / "priority_rejudge.json")

PASS = "PASS_TO_STAGE2"  # noqa: S105 -- a verdict name, not a credential
REJECT = "REJECT_STAGE1"
UNBUILDABLE = "UNBUILDABLE"
VERDICTS = (PASS, REJECT, UNBUILDABLE)

TIER_PRIORITY = 0
TIER_PASS = 1
TIER_FORWARD = 2
TIER_UNRULED = 3
TIER_REJECT = 4
TIER_NAMES = {TIER_PRIORITY: "named_priority", TIER_PASS: "stage1_pass",
              TIER_FORWARD: "stage1_forward_unscreened", TIER_UNRULED: "not_yet_ruled",
              TIER_REJECT: "stage1_reject_or_unbuildable"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cells(
  cid TEXT PRIMARY KEY,
  sym TEXT, family TEXT, tf TEXT,
  verdict TEXT NOT NULL,
  basis TEXT,
  reason TEXT,
  cause TEXT,
  p REAL, t REAL, mean_r REAL, mean_r_x3 REAL,
  n_days_full INTEGER, n_days_train INTEGER, train_end TEXT,
  n_bars INTEGER, first_bar TEXT, family_ver TEXT,
  first_seen TEXT,
  run_id TEXT, ruled_at TEXT NOT NULL,
  times_ruled INTEGER NOT NULL DEFAULT 1,
  forwarded_at TEXT
);
CREATE INDEX IF NOT EXISTS cells_verdict ON cells(verdict, basis);
CREATE TABLE IF NOT EXISTS rulings(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cid TEXT NOT NULL, run_id TEXT, ruled_at TEXT NOT NULL,
  verdict TEXT NOT NULL, basis TEXT, reason TEXT, cause TEXT, family TEXT,
  p REAL, cost_s REAL
);
CREATE INDEX IF NOT EXISTS rulings_at ON rulings(ruled_at);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    p = Path(path or DB)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p), timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.executescript(_SCHEMA)
    return con


def open_readonly(path: Path | None = None) -> sqlite3.Connection | None:
    """A read-only handle, or None when no record exists (a reader must never create one)."""
    p = Path(path or DB)
    if not p.exists():
        return None
    try:
        return sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True, timeout=30)
    except sqlite3.Error:
        return None


def get_meta(con: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def set_meta(con: sqlite3.Connection, key: str, value: str) -> None:
    con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?,?)", (key, value))


def _chunks(seq: list[str], n: int = 900) -> Iterable[list[str]]:
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def states(con: sqlite3.Connection, cids: Iterable[str]) -> dict[str, dict[str, Any]]:
    """{cid: row} for the cids the record knows; the rest are absent (never ruled)."""
    out: dict[str, dict[str, Any]] = {}
    ids = [c for c in dict.fromkeys(cids) if c]
    cols = ("cid", "verdict", "basis", "cause", "n_bars", "first_bar", "family_ver",
            "ruled_at", "times_ruled")
    for part in _chunks(ids):
        # Column names are this module's constants and the ids are bound parameters.
        q = (f"SELECT {', '.join(cols)} FROM cells WHERE cid IN "  # noqa: S608
             f"({','.join('?' * len(part))})")
        for row in con.execute(q, part):
            out[row[0]] = dict(zip(cols, row, strict=True))
    return out


def tier_of_state(state: dict[str, Any] | None) -> int:
    if not state:
        return TIER_UNRULED
    v = state.get("verdict")
    if v == PASS:
        return TIER_FORWARD if state.get("basis") == "UNSCREENABLE_TRAIN_WINDOW" else TIER_PASS
    return TIER_REJECT


def priority_cells(files: Iterable[Path] | None = None) -> set[str]:
    """Cell ids other agents have queued first (v4 re-mint, evicted re-judges). Read only."""
    out: set[str] = set()
    for f in (files if files is not None else PRIORITY_FILES):
        try:
            doc = json.loads(Path(f).read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(doc, dict):
            for c in doc.get("cells") or []:
                if isinstance(c, str) and c:
                    out.add(c)
                elif isinstance(c, dict) and c.get("cell_id"):
                    out.add(str(c["cell_id"]))
            for r in doc.get("rows") or []:
                if isinstance(r, dict) and r.get("cell_id"):
                    out.add(str(r["cell_id"]))
    return out


def tiers(cids: Iterable[str], path: Path | None = None,
          priority: set[str] | None = None) -> dict[str, int]:
    """{cid: tier} for every cid given. No record yet: every cell reads NOT_YET_RULED (tier 3)
    except the named priorities -- the fail-open direction, which changes no order at all."""
    ids = [c for c in dict.fromkeys(cids) if c]
    pri = priority_cells() if priority is None else priority
    con = open_readonly(path)
    known: dict[str, dict[str, Any]] = {}
    if con is not None:
        try:
            known = states(con, ids)
        except sqlite3.Error:
            known = {}
        finally:
            with contextlib.suppress(Exception):
                con.close()
    return {c: (TIER_PRIORITY if c in pri else tier_of_state(known.get(c))) for c in ids}


def stage1_rank_for_specs(specs: list[dict], cell_id_fn, path: Path | None = None
                          ) -> dict[int, int]:
    """{id(spec): tier} for docket specs, computing each cell id with the judge's own
    `cell_id` (passed in so this module never imports the sealed file). Unidentifiable
    specs read tier 3, which is where they already were."""
    cids: dict[int, str] = {}
    for sp in specs:
        try:
            cids[id(sp)] = str(cell_id_fn({"sym": sp.get("sym"), "family": sp.get("family"),
                                           "params": sp.get("params") or {}}))
        except Exception:
            cids[id(sp)] = ""
    t = tiers([c for c in cids.values() if c], path)
    return {k: t.get(c, TIER_UNRULED) if c else TIER_UNRULED for k, c in cids.items()}
