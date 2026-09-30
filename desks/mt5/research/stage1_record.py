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

STAGE 1 ONLY REORDERS (audit 2026-09-30). No cell is parked or demoted to a "reject" tier: a
low score sorts later, and every cell stays on the docket and is judged when the order reaches it.
The rank every consumer uses is a (group, -score) pair, lower first:

  group 0  named priority  -- v4 re-mint cells (`priority_remint.json`), evicted re-judges
                              (`priority_rejudge.json`), the rollover re-judge queue and the
                              zero-spread stress re-judge list: other queues keep precedence.
  group 1  SCORED          -- every cell stage 1 TESTED, by its training-window t-statistic,
                              DESCENDING (BH survivors and non-survivors alike: the score orders,
                              the BH verdict is reported). A cell forwarded with basis
                              UNSCREENABLE_TRAIN_WINDOW (enough history, too little of it before
                              the boundary -- mostly RECENT intraday cells) ranks here at the
                              NEUTRAL score t = 0: stage 1 has no evidence either way, so it sits
                              behind every positive-t cell and ahead of every negative-t one,
                              never behind the cells the screen measured as losing (audit R2).
  group 2  NOT_YET_RULED   -- cells stage 1 has not reached.
  group 3  UNTESTED        -- ruled but not testable on the training window (too few training
                              days, no signals, under 60 days): judged after every scored cell.
  group 4  UNBUILDABLE     -- a named build cause; last, never dropped.
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
PRIORITY_FILES = (HYP / "priority_remint.json", HYP / "priority_rejudge.json",
                  HYP / "priority_rollover_rejudge.json", HYP / "priority_rejudge_zero_spread.json")

PASS = "PASS_TO_STAGE2"  # noqa: S105 -- a verdict name, not a credential
REJECT = "REJECT_STAGE1"
UNBUILDABLE = "UNBUILDABLE"
VERDICTS = (PASS, REJECT, UNBUILDABLE)

TIER_PRIORITY = 0
TIER_SCORED = 1
TIER_UNRULED = 2
TIER_UNTESTED = 3
TIER_UNBUILDABLE = 4
#: Bases that forward a cell with no training-window statistic because the screen could not test
#: it, not because it failed: they rank at the neutral score (t = 0) inside group 1.
NEUTRAL_BASES = ("UNSCREENABLE_TRAIN_WINDOW",)
NEUTRAL_SCORE = 0.0
TIER_NAMES = {TIER_PRIORITY: "named_priority", TIER_SCORED: "scored_by_stage1_t",
              TIER_UNRULED: "not_yet_ruled", TIER_UNTESTED: "untested_on_training_window",
              TIER_UNBUILDABLE: "unbuildable_named_cause"}
#: The rank of a cell the record does not know: exactly where every cell sat before stage 1.
UNRULED_RANK = (TIER_UNRULED, 0.0)

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
  score REAL,
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
    # a record written before the score column: add it (NULL = untested), never rebuild
    with contextlib.suppress(sqlite3.Error):
        con.execute("ALTER TABLE cells ADD COLUMN score REAL")
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
    cols = ("cid", "verdict", "basis", "cause", "score", "n_bars", "first_bar", "family_ver",
            "ruled_at", "times_ruled")
    have = {r[1] for r in con.execute("PRAGMA table_info(cells)")}
    sel = [c if c in have else "NULL" for c in cols]
    for part in _chunks(ids):
        # Column names are this module's constants and the ids are bound parameters.
        q = (f"SELECT {', '.join(sel)} FROM cells WHERE cid IN "  # noqa: S608
             f"({','.join('?' * len(part))})")
        for row in con.execute(q, part):
            out[row[0]] = dict(zip(cols, row, strict=True))
    return out


def tier_of_state(state: dict[str, Any] | None) -> int:
    """The group: scored when stage 1 tested it (a score), untested when ruled without one,
    unbuildable for a named build cause. Never a "reject" group: a score only orders."""
    if not state:
        return TIER_UNRULED
    if state.get("verdict") == UNBUILDABLE:
        return TIER_UNBUILDABLE
    if state.get("score") is not None or state.get("basis") in NEUTRAL_BASES:
        return TIER_SCORED
    return TIER_UNTESTED


def rank_of_state(state: dict[str, Any] | None) -> tuple[int, float]:
    """(group, -score): lower sorts first, so a higher score comes first inside group 1. An
    unscreenable-train-window cell reads the neutral score (t = 0), whatever its row holds."""
    g = tier_of_state(state)
    if g == TIER_SCORED:
        if state.get("score") is None:  # type: ignore[union-attr]
            return (g, -NEUTRAL_SCORE)
        try:
            return (g, -float(state["score"]))  # type: ignore[index]
        except (TypeError, ValueError):
            return (TIER_UNTESTED, 0.0)
    return (g, 0.0)


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
          priority: set[str] | None = None) -> dict[str, tuple[int, float]]:
    """{cid: (group, -score)} for every cid given. No record yet: every cell reads NOT_YET_RULED
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
    return {c: ((TIER_PRIORITY, 0.0) if c in pri else rank_of_state(known.get(c)))
            for c in ids}


def stage1_rank_for_specs(specs: list[dict], cell_id_fn, path: Path | None = None
                          ) -> dict[int, tuple[int, float]]:
    """{id(spec): (group, -score)} for docket specs, computing each cell id with the judge's own
    `cell_id` (passed in so this module never imports the sealed file). Unidentifiable specs
    read NOT_YET_RULED, which is where they already were."""
    cids: dict[int, str] = {}
    for sp in specs:
        try:
            cids[id(sp)] = str(cell_id_fn({"sym": sp.get("sym"), "family": sp.get("family"),
                                           "params": sp.get("params") or {}}))
        except Exception:
            cids[id(sp)] = ""
    t = tiers([c for c in cids.values() if c], path)
    return {k: t.get(c, UNRULED_RANK) if c else UNRULED_RANK for k, c in cids.items()}


#: THE DESK'S STAGE-1 TRIAL COUNT in `EXPERIMENT_LEDGER.json` (`libs.research.experiment_ledger`):
#: the sum of `cells_screened` over every stage-1 run and family -- the FULL UNION of screened
#: cells, the population stage 1 ranked every judged cell out of.
LEDGER_UNION_KEY = "stage1_cells"


def dsr_charge(campaign: int, family: str, lifetime: dict[str, Any]) -> tuple[int, str]:
    """THE COUNT THE SEALED DEFLATED SHARPE CHARGES a cell, once the two-stage patch lands:
    max(campaign charge, the family's lifetime trials, stage 1's union of screened cells).

    WHY THE UNION AND NOT THE FAMILY (audit 2026-09-30). Stage 1 ranks every judged cell out of
    ONE population -- every cell it screened, across families -- so the selection a judged cell
    survived is over that union. Charging max(campaign, family) under-charges by union/family:
    measured at 975k screened a day, 3.1x for exit_operated, 11.5x for htf_anchor and ~208x for
    turn_of_month. `lifetime` is the sealed `lifetime_trial_report` dict; its
    `stage1_union_trials` field is the ledger's `stage1_cells`. A tightening only: never below the
    campaign charge or the family's own count. THE SEALED EDIT is written once, by
    /mnt/project-files/patches/union_lifetime_trials/ (charged_lifetime_trials = max(campaign,
    family, union)); this is the unsealed statement of the same rule, which the branch tests pin
    and that patch's tests can compare against. What that patch READS is published here:
    EXPERIMENT_LEDGER.json `stage1_cells` = the sum of STAGE1_TRIALS.jsonl `cells_screened` = the
    sum of every run's union `m_charged` (`stage1_judge.trial_charge`).
    """
    n = int(campaign)
    parts = [f"campaign {n}"]
    fam_n = (lifetime.get("family_trials") or {}).get(family) if isinstance(lifetime, dict) \
        else None
    if isinstance(fam_n, int) and not isinstance(fam_n, bool) and fam_n > 0:
        n = max(n, fam_n)
        parts.append(f"lifetime family trials {fam_n}")
    else:
        parts.append(f"family {family or '?'} absent from the lifetime ledger")
    union = lifetime.get("stage1_union_trials") if isinstance(lifetime, dict) else None
    if isinstance(union, int) and not isinstance(union, bool) and union > 0:
        n = max(n, union)
        parts.append(f"stage-1 union of screened cells {union}")
    else:
        parts.append("stage-1 union UNMEASURED")
    return n, "; ".join(parts)


def stage1_union_from_trials(path: Path | None = None) -> int | None:
    """The union read straight from STAGE1_TRIALS.jsonl, for the sealed fallback when the
    experiment ledger is unreadable: never silently dropped. None when the file is unreadable."""
    p = Path(path) if path else DESK / "data" / "STAGE1_TRIALS.jsonl"
    total = 0
    try:
        with p.open(encoding="utf-8") as fh:
            for ln in fh:
                try:
                    row = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(row, dict) and not row.get("dry_run"):
                    with contextlib.suppress(TypeError, ValueError):
                        total += int(row.get("cells_screened") or 0)
    except OSError:
        return None
    return total
