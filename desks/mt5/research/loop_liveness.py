"""THE LOOP LIVENESS PROVER -- is the research loop ALIVE, stage by stage, from the artifacts.

    sources -> discoveries -> conversion -> compiled cells -> TEN GATES -> certificates
            -> forward clocks -> accrual -> promoter -> allocator

Every one of those arrows is an organ with a clock. Any one of them can stop while the nine
others keep running and every report stays green, because each organ reports on ITSELF: the
gauntlet says "judged 0 cells" and is telling the truth, the compiler says "compiled 0" and is
telling the truth, and nowhere does anything say WHICH arrow broke. That is the failure this
organ exists for. A stage with INPUT WAITING AND NO OUTPUT is STALLED, and STALLED is a DEFECT
published with the exact organ that owns it and when that organ last ran.

NOTHING HERE IS READ FROM A LABEL. Every count comes from the canonical registry
(`libs/moat/registry.py` at ROOT data/alpha_registry.sqlite) or from the artifact the stage's
organ actually writes. `desks/mt5/scripts/external_gauntlet.py` is the sealed judge: its gate
names are imported from `desks/mt5/research/gate_policy.GATES` and its verdict rows are read out
of the gate ledger it writes. This organ never edits it and never re-implements it.

THE HOST IS MEASURED, NOT ASSUMED, AND THE DIFFERENCE IS PUBLISHED. A host with no MetaTrader5
package has no terminal, no gateway and no live account, so its forward clocks legitimately do
not accrue and its promoter legitimately does not run; calling those STALLED would be a lie that
trains the desk to ignore the report. MEASURED 2026-09-23, the third case is the one that
matters: this host HAS the package, the gateway state file and 26 MT5-* scheduled tasks, and
every one of those tasks is DISABLED. "Package installed" would have read as `trading_box` and
blamed `shadow_forward` for not advancing clocks nothing was scheduled to advance. So the host
is one of `trading_box` (package AND an enabled clock), `box_clocks_off` (package, no enabled
clock) or `build_box` (no package), and a stage declared `host="trading_box"` is UNMEASURED
anywhere else -- an absence, which is a real answer (L1.28a), never a zero and never a pass.

Artifacts: desks/mt5/reports/LOOP_LIVENESS.json and docs/research/LOOP_LIVENESS.md.
Clock: hourly leg `loop_liveness` (department validate).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import socket
import sqlite3
import sys
import time
from collections.abc import Callable, Mapping
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT = DESK / "reports" / "LOOP_LIVENESS.json"
DOC = ROOT / "docs" / "research" / "LOOP_LIVENESS.md"

ALIVE, SLOW, STALLED, UNMEASURED = "ALIVE", "SLOW", "STALLED", "UNMEASURED"
VERDICTS = (ALIVE, SLOW, STALLED, UNMEASURED)

#: A stage is ALIVE while its newest output is inside this many cadences. Two is the desk's
#: standing rule for an hourly organ (lease.TTL_BY_CLASS["hourly"] = 7200 s for the same reason):
#: one missed pass is a hiccup, two is a stop.
STALL_CADENCES = 2.0
HOUR_S = 3600.0
DAY_S = 86400.0


# ------------------------------------------------------------------------------------- host
def hostname() -> str:
    try:
        return socket.gethostname() or UNMEASURED
    except OSError:  # pragma: no cover
        return UNMEASURED


def _mt5_installed() -> bool:
    """`find_spec` rather than `import`: importing MetaTrader5 on a box with a terminal can block
    on the terminal itself, and this organ must never be the thing that hangs the cycle."""
    try:
        return importlib.util.find_spec("MetaTrader5") is not None
    except (ImportError, ValueError):  # pragma: no cover - a broken sys.path entry
        return False


#: Where Windows keeps a scheduled task's definition. Read directly rather than through
#: `schtasks /query`, which MEASURED 2026-09-23 takes over 60 s on this box (it enumerates every
#: task on the machine) against 0.16 s for 26 XML files. An organ inside an hourly cycle does
#: not get to spend a minute answering "which host am I on".
TASKS_DIR = Path("C:/Windows/System32/Tasks")


def _enabled_box_clocks(tasks_dir: Path | None = None) -> int | None:
    """How many MT5-* scheduled tasks are ENABLED. None where the question cannot be answered.

    MEASURED 2026-09-23 AND THIS IS WHY THE FIELD EXISTS: this host carries the MetaTrader5
    package, the gateway state file and 26 MT5-* tasks, and EVERY ONE OF THEM IS DISABLED.
    A package check alone would have called it the trading box and then called the forward
    clocks STALLED -- blaming `shadow_forward` for not running when nothing was scheduled to run
    it. Installed is not scheduled, and scheduled is not enabled.
    """
    d = tasks_dir if tasks_dir is not None else (TASKS_DIR if sys.platform == "win32" else None)
    if d is None or not d.is_dir():
        return None
    enabled = 0
    seen = 0
    for p in sorted(d.glob("MT5-*")):
        if not p.is_file():
            continue
        text = ""
        for enc in ("utf-16", "utf-8-sig"):
            try:
                text = p.read_text(encoding=enc, errors="replace")
                break
            except (OSError, UnicodeError, LookupError):
                continue
        if not text:
            continue
        seen += 1
        if "<Enabled>true</Enabled>" in text:
            enabled += 1
    return enabled if seen else None


def host_facts() -> dict[str, Any]:
    """WHERE this was measured and whether the box's clocks are live. Never assumed.

    kind:
      `trading_box`   the terminal package is here AND at least one MT5 clock is enabled
      `box_clocks_off` the terminal package is here and NO MT5 clock is enabled -- box-only
                      stages are UNMEASURED, because nothing is scheduled to advance them
      `vps`           the research VPS checkout: POSIX, at /home/quant/quant-platform
      `build_box`     none of the above: no terminal, no gateway, no live account

    `check_no_staleness.py` reads this too. ONE detector for both organs, deliberately: two
    host detectors are two things that can disagree about which machine they are on, and the
    disagreement would show up as a stale-artifact verdict nobody could reproduce.
    """
    mt5 = _mt5_installed()
    clocks = _enabled_box_clocks() if mt5 else None
    if not mt5 and sys.platform != "win32" and ROOT.as_posix().endswith("quant-platform"):
        kind, why = "vps", f"POSIX checkout at {ROOT.as_posix()}: the research VPS"
    elif not mt5:
        kind, why = "build_box", "no MetaTrader5 package: no terminal, no gateway, no live account"
    elif clocks is None:
        kind, why = "trading_box", "MetaTrader5 present; the task scheduler could not be read"
    elif clocks == 0:
        kind, why = ("box_clocks_off",
                     "MetaTrader5 present but 0 MT5-* scheduled tasks are enabled -- the box's "
                     "clocks are OFF, so a box-only stage has nothing scheduled to advance it")
    else:
        kind, why = "trading_box", f"MetaTrader5 present and {clocks} MT5-* task(s) enabled"
    return {"kind": kind, "hostname": hostname(), "mt5_package": mt5,
            "enabled_box_clocks": clocks, "why": why}


def host_kind() -> str:
    return str(host_facts()["kind"])


# --------------------------------------------------------------------------------- utilities
def _parse(stamp: Any) -> float | None:
    """A timestamp -> epoch seconds. Unreadable is None (UNMEASURED), never 0 (1970)."""
    if isinstance(stamp, (int, float)) and not isinstance(stamp, bool):
        return float(stamp) if 1e8 < float(stamp) < 4e9 else None
    s = str(stamp or "").strip()
    if not s:
        return None
    s = s.replace("Z", "+00:00").replace(" ", "T", 1) if "T" not in s else s.replace("Z", "+00:00")
    try:
        t = datetime.fromisoformat(s)
    except ValueError:
        return None
    return (t if t.tzinfo else t.replace(tzinfo=UTC)).timestamp()


def _age(stamp: Any, now: float) -> float | None:
    t = _parse(stamp)
    return None if t is None else max(0.0, now - t)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _tail_jsonl(path: Path, limit: int = 40_000) -> list[dict[str, Any]]:
    """The last `limit` rows of a jsonl ledger. Bounded: the gate ledger is hundreds of MB on a
    busy week and this organ has a wall-clock budget it must respect."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in text.splitlines()[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


@dataclass
class Measure:
    """One stage's numbers. `None` everywhere is UNMEASURED; 0 is a measured zero."""
    source_present: bool = False
    count_1h: int | None = None
    count_24h: int | None = None
    newest_age_s: float | None = None
    pending: int | None = None
    oldest_pending_age_s: float | None = None
    source: str = UNMEASURED
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"source_present": self.source_present, "count_1h": self.count_1h,
                "count_24h": self.count_24h,
                "newest_age_s": None if self.newest_age_s is None else round(self.newest_age_s, 1),
                "pending": self.pending,
                "oldest_pending_age_s": (None if self.oldest_pending_age_s is None
                                         else round(self.oldest_pending_age_s, 1)),
                "source": self.source, **self.detail}


@dataclass(frozen=True)
class Stage:
    """One arrow of the loop: who owns it, how often it should fire, and how to measure it."""
    name: str
    organ: str                       #: the leg / task that OWNS this arrow
    consumes: str                    #: what waits on its input, in words
    produces: str
    measure: Callable[[Path, float], Measure]
    cadence_s: float = HOUR_S
    host: str = "any"                #: "any" or "trading_box"

    @property
    def stall_window_s(self) -> float:
        return self.cadence_s * STALL_CADENCES


# ------------------------------------------------------------------------------ the registry
def _registry_conn(root: Path) -> sqlite3.Connection | None:
    """The CANONICAL registry at ROOT/data/alpha_registry.sqlite, read-only and never created.

    A missing database is UNMEASURED, not an empty desk: `registry.connect()` would evolve a
    schema and restore from backup, which is a WRITE, and a liveness prover that creates the
    thing it is measuring proves nothing.
    """
    p = root / "data" / "alpha_registry.sqlite"
    if not p.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=10)
    except sqlite3.Error:
        return None
    conn.row_factory = sqlite3.Row
    return conn


def _tables(conn: sqlite3.Connection) -> set[str]:
    try:
        return {str(r[0]) for r in
                conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    except sqlite3.Error:  # pragma: no cover
        return set()


def _stamp_counts(conn: sqlite3.Connection, table: str, column: str, now: float,
                  where: str = "") -> tuple[int, int, float | None]:
    """(rows in the last hour, in the last day, age of the newest row) for one timestamp column.

    Counted in PYTHON off the raw strings rather than in SQL, because the desk's timestamp
    columns carry three shapes ('...+00:00', '... ', bare ISO) and a SQL datetime() comparison
    silently drops the ones it cannot parse -- which would read as a quiet stage.
    """
    clause = f" WHERE {where}" if where else ""
    try:
        rows = conn.execute(
            f"SELECT {column} AS s FROM {table}{clause} "  # noqa: S608 - names are literals here
            f"ORDER BY {column} DESC LIMIT 20000").fetchall()
    except sqlite3.Error:
        return 0, 0, None
    n1 = n24 = 0
    newest: float | None = None
    for r in rows:
        a = _age(r["s"], now)
        if a is None:
            continue
        newest = a if newest is None else min(newest, a)
        if a <= HOUR_S:
            n1 += 1
        if a <= DAY_S:
            n24 += 1
    return n1, n24, newest


def _count(conn: sqlite3.Connection, sql: str) -> int | None:
    try:
        row = conn.execute(sql).fetchone()
    except sqlite3.Error:
        return None
    return None if row is None else int(row[0])


def _oldest_age(conn: sqlite3.Connection, sql: str, now: float) -> float | None:
    try:
        row = conn.execute(sql).fetchone()
    except sqlite3.Error:
        return None
    return None if row is None else _age(row[0], now)


# --------------------------------------------------------------------- the ten stage measures
def m_sources(root: Path, now: float) -> Measure:
    conn = _registry_conn(root)
    if conn is None:
        return Measure(source="data/alpha_registry.sqlite (absent)")
    with closing(conn), conn:
        if "sources" not in _tables(conn):
            return Measure(source="registry.sources (absent)")
        n1, n24, newest = _stamp_counts(conn, "sources", "first_seen", now)
        pending = _count(conn, "SELECT COUNT(*) FROM sources WHERE last_crawled IS NULL "
                               "OR last_crawled=''")
        oldest = _oldest_age(conn, "SELECT MIN(first_seen) FROM sources WHERE last_crawled IS "
                                   "NULL OR last_crawled=''", now)
        total = _count(conn, "SELECT COUNT(*) FROM sources")
    return Measure(True, n1, n24, newest, pending, oldest, "registry.sources.first_seen",
                   {"total_sources": total})


def m_discoveries(root: Path, now: float) -> Measure:
    conn = _registry_conn(root)
    if conn is None:
        return Measure(source="data/alpha_registry.sqlite (absent)")
    with closing(conn), conn:
        if "discoveries" not in _tables(conn):
            return Measure(source="registry.discoveries (absent)")
        n1, n24, newest = _stamp_counts(conn, "discoveries", "created_at", now)
        total = _count(conn, "SELECT COUNT(*) FROM discoveries")
    return Measure(True, n1, n24, newest, None, None, "registry.discoveries.created_at",
                   {"total_discoveries": total})


def m_conversion(root: Path, now: float) -> Measure:
    """CONVERSION DEBT: discoveries that have produced no candidate. The waiting input is the
    discovery; the output is a research_candidate carrying its discovery_id."""
    conn = _registry_conn(root)
    if conn is None:
        return Measure(source="data/alpha_registry.sqlite (absent)")
    with closing(conn), conn:
        tabs = _tables(conn)
        if not {"discoveries", "research_candidates"} <= tabs:
            return Measure(source="registry.{discoveries,research_candidates} (absent)")
        n1, n24, newest = _stamp_counts(conn, "research_candidates", "created_at", now,
                                        "discovery_id IS NOT NULL AND discovery_id<>''")
        debt = _count(conn, "SELECT COUNT(*) FROM discoveries d WHERE NOT EXISTS ("
                            "SELECT 1 FROM research_candidates c WHERE c.discovery_id="
                            "d.discovery_id)")
        oldest = _oldest_age(conn, "SELECT MIN(d.created_at) FROM discoveries d WHERE NOT EXISTS "
                                   "(SELECT 1 FROM research_candidates c WHERE c.discovery_id="
                                   "d.discovery_id)", now)
        converted = _count(conn, "SELECT COUNT(DISTINCT discovery_id) FROM research_candidates "
                                 "WHERE discovery_id IS NOT NULL AND discovery_id<>''")
    return Measure(True, n1, n24, newest, debt, oldest,
                   "registry.research_candidates.created_at WHERE discovery_id",
                   {"discoveries_converted": converted, "conversion_debt": debt})


def m_compiled(root: Path, now: float) -> Measure:
    conn = _registry_conn(root)
    if conn is None:
        return Measure(source="data/alpha_registry.sqlite (absent)")
    with closing(conn), conn:
        if "research_candidates" not in _tables(conn):
            return Measure(source="registry.research_candidates (absent)")
        n1, n24, newest = _stamp_counts(conn, "research_candidates", "created_at", now)
        queued = _count(conn, "SELECT COUNT(*) FROM research_candidates WHERE status='queued'")
        total = _count(conn, "SELECT COUNT(*) FROM research_candidates")
    return Measure(True, n1, n24, newest, None, None, "registry.research_candidates.created_at",
                   {"queued": queued, "total_candidates": total})


def m_gauntlet(root: Path, now: float) -> Measure:
    """THE TEN GATES. Judged rows come from the sealed judge's own verdict ledger; the waiting
    input is a queued candidate with no `judged_at`."""
    from desks.mt5.research.gate_policy import GATES

    ledger = root / "desks" / "mt5" / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
    rows = _tail_jsonl(ledger) if ledger.exists() else []
    n1 = n24 = 0
    newest: float | None = None
    passed_24h = 0
    by_gate: dict[str, int] = {}
    for r in rows:
        a = _age(r.get("at"), now)
        if a is None:
            continue
        newest = a if newest is None else min(newest, a)
        if a <= HOUR_S:
            n1 += 1
        if a <= DAY_S:
            n24 += 1
            gate = str(r.get("terminal_gate") or UNMEASURED)
            by_gate[gate] = by_gate.get(gate, 0) + 1
            if r.get("passed") is True:
                passed_24h += 1
    pending = oldest = None
    conn = _registry_conn(root)
    if conn is not None:
        with closing(conn), conn:
            if "research_candidates" in _tables(conn):
                pending = _count(conn, "SELECT COUNT(*) FROM research_candidates WHERE "
                                       "status='queued' AND (judged_at IS NULL OR judged_at='')")
                oldest = _oldest_age(conn, "SELECT MIN(created_at) FROM research_candidates WHERE "
                                           "status='queued' AND (judged_at IS NULL OR "
                                           "judged_at='')", now)
    if not ledger.exists():
        return Measure(False, None, None, None, pending, oldest,
                       "data/hypotheses/gate_verdict_ledger.jsonl (absent)",
                       {"gates": list(GATES), "n_gates": len(GATES)})
    return Measure(True, n1, n24, newest, pending, oldest,
                   "data/hypotheses/gate_verdict_ledger.jsonl",
                   {"gates": list(GATES), "n_gates": len(GATES),
                    "ten_gate_passes_24h": passed_24h,
                    "terminal_gate_24h": dict(sorted(by_gate.items(), key=lambda kv: -kv[1])[:8]),
                    "rows_scanned": len(rows)})


def m_certificates(root: Path, now: float) -> Measure:
    """Survivors certified: the sealed judge's UNIVERSAL_SURVIVORS sweep. The waiting input is a
    ten-gate pass in the verdict ledger that the sweep has not yet published."""
    p = root / "desks" / "mt5" / "reports" / "UNIVERSAL_SURVIVORS.json"
    doc = _read_json(p)
    if not isinstance(doc, dict):
        return Measure(source="reports/UNIVERSAL_SURVIVORS.json (absent or unreadable)")
    age = _age(doc.get("swept_at"), now)
    survivors = doc.get("survivors")
    n = int(doc.get("n") or (len(survivors) if isinstance(survivors, (list, dict)) else 0))
    ledger = root / "desks" / "mt5" / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
    passes = sum(1 for r in _tail_jsonl(ledger) if r.get("passed") is True) if ledger.exists() \
        else None
    fresh = 1 if (age is not None and age <= DAY_S) else 0
    return Measure(True, 1 if (age is not None and age <= HOUR_S) else 0, fresh, age,
                   None if passes is None else max(0, passes - n), None,
                   "reports/UNIVERSAL_SURVIVORS.json",
                   {"certificates": n, "ledger_ten_gate_passes": passes})


def _shadow_states(root: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    d = root / "desks" / "mt5" / "reports" / "shadow"
    for stem in ("shadow_state", "qquant_shadow_state", "scalp_shadow_state"):
        doc = _read_json(d / f"{stem}.json")
        if isinstance(doc, dict):
            for k, v in doc.items():
                if isinstance(v, dict):
                    out[f"{stem}:{k}"] = v
    return out


def m_enrolment(root: Path, now: float) -> Measure:
    """Certificates enrolled on forward clocks: a clock row exists per certificate."""
    rows = _shadow_states(root)
    if not rows:
        return Measure(source="reports/shadow/*shadow_state.json (absent)")
    ages = [a for a in (_age(v.get("forward_start") or v.get("first_entry"), now)
                        for v in rows.values()) if a is not None]
    certs = _read_json(root / "desks" / "mt5" / "reports" / "UNIVERSAL_SURVIVORS.json")
    n_cert = int(certs.get("n") or 0) if isinstance(certs, dict) else None
    live = sum(1 for v in rows.values() if str(v.get("status") or "").lower() not in
               ("retired", "void", "voided"))
    return Measure(True, sum(1 for a in ages if a <= HOUR_S), sum(1 for a in ages if a <= DAY_S),
                   min(ages) if ages else None,
                   None if n_cert is None else max(0, n_cert - live), None,
                   "reports/shadow/*shadow_state.json",
                   {"clock_rows": len(rows), "live_clock_rows": live, "certificates": n_cert})


def m_accrual(root: Path, now: float) -> Measure:
    """Clocks ACCRUING: a forward clock that is enrolled but never attempts is the exact defect
    this stage exists for. Needs the terminal -- UNMEASURED on a build box."""
    rows = _shadow_states(root)
    if not rows:
        return Measure(source="reports/shadow/*shadow_state.json (absent)")
    attempts = [a for a in (_age(v.get("last_attempt_at") or v.get("last_entry"), now)
                            for v in rows.values()) if a is not None]
    active = [k for k, v in rows.items()
              if str(v.get("status") or "").lower() not in ("retired", "void", "voided")]
    stale = sum(1 for k in active
                if (_age(rows[k].get("last_attempt_at") or rows[k].get("last_entry"), now)
                    or float("inf")) > DAY_S)
    n_total = sum(int(v.get("n") or 0) for v in rows.values())
    return Measure(True, sum(1 for a in attempts if a <= HOUR_S),
                   sum(1 for a in attempts if a <= DAY_S),
                   min(attempts) if attempts else None, stale, None,
                   "reports/shadow/*shadow_state.json.last_attempt_at",
                   {"active_clocks": len(active), "clocks_silent_24h": stale,
                    "forward_observations": n_total})


def m_promoter(root: Path, now: float) -> Measure:
    """The promoter READING the clocks: sleeves.json is what it writes on every pass."""
    p = root / "desks" / "mt5" / "data" / "sleeves.json"
    doc = _read_json(p)
    if doc is None:
        return Measure(source="desks/mt5/data/sleeves.json (absent or unreadable)")
    stamp = None
    if isinstance(doc, dict):
        stamp = doc.get("updated_at") or doc.get("at") or doc.get("generated_at")
    age = _age(stamp, now)
    if age is None:
        try:
            age = max(0.0, now - p.stat().st_mtime)
        except OSError:  # pragma: no cover
            age = None
    sleeves = doc.get("sleeves") if isinstance(doc, dict) else doc
    n_live = 0
    if isinstance(sleeves, list):
        n_live = sum(1 for s in sleeves
                     if isinstance(s, dict) and str(s.get("state") or s.get("status")
                                                    or "").upper() == "LIVE")
    return Measure(True, 1 if (age is not None and age <= HOUR_S) else 0,
                   1 if (age is not None and age <= DAY_S) else 0, age, None, None,
                   "desks/mt5/data/sleeves.json",
                   {"sleeves": len(sleeves) if isinstance(sleeves, list) else None,
                    "live_sleeves": n_live,
                    "stamp_source": "field" if stamp else "mtime"})


def m_allocator(root: Path, now: float) -> Measure:
    p = root / "desks" / "mt5" / "reports" / "pf_allocation.json"
    doc = _read_json(p)
    if not isinstance(doc, dict):
        return Measure(source="reports/pf_allocation.json (absent or unreadable)")
    age = _age(doc.get("at") or doc.get("generated_at") or doc.get("built_at"), now)
    if age is None:
        try:
            age = max(0.0, now - p.stat().st_mtime)
        except OSError:  # pragma: no cover
            age = None
    fr = doc.get("fractions") or doc.get("weights") or {}
    return Measure(True, 1 if (age is not None and age <= HOUR_S) else 0,
                   1 if (age is not None and age <= DAY_S) else 0, age, None, None,
                   "reports/pf_allocation.json",
                   {"sized_sleeves": len(fr) if isinstance(fr, (dict, list)) else None})


#: THE LOOP, DECLARED IN ORDER. The `organ` is the leg that owns the arrow; `check_component_
#: registry` and the reconciler both key off those names, so a stage naming an organ the desk
#: does not schedule is a finding, not a typo.
STAGES: tuple[Stage, ...] = (
    Stage("sources_ingested", "world_crawler", "the open web and the deep forests",
          "registry rows in `sources`", m_sources),
    Stage("discoveries_mined", "deep_forest", "sources", "registry rows in `discoveries`",
          m_discoveries),
    Stage("conversion", "miner_conversion", "discoveries",
          "research_candidates carrying a discovery_id", m_conversion),
    Stage("candidates_compiled", "compile_candidates", "candidates and the docket",
          "queued gauntlet cells", m_compiled),
    Stage("ten_gates_judged", "external_gauntlet", "queued cells",
          "verdict rows from the sealed ten-gate judge", m_gauntlet),
    Stage("survivors_certified", "external_gauntlet", "ten-gate passes",
          "certificates in UNIVERSAL_SURVIVORS.json", m_certificates),
    Stage("clocks_enrolled", "enrol_clocks", "certificates", "forward clock rows", m_enrolment),
    Stage("clocks_accruing", "shadow_forward", "forward clock rows",
          "forward observations", m_accrual, host="trading_box"),
    Stage("promoter_reading", "promoter", "forward clocks", "LIVE rows in sleeves.json",
          m_promoter, host="trading_box"),
    Stage("allocator_sizing", "pf_allocator", "LIVE sleeves", "fractions in pf_allocation.json",
          m_allocator),
)


# ------------------------------------------------------------------------------- the verdict
def judge(stage: Stage, m: Measure, *, here: str) -> tuple[str, str]:
    """(verdict, why). The ONE place a stage's verdict is decided.

    INPUT WAITING AND NO OUTPUT IS STALLED -- that is the whole point of the organ. A stage with
    no recent output and nothing waiting for it is idle for want of input, which is SLOW: the
    defect is upstream and will be named there.
    """
    if stage.host != "any" and here != stage.host:
        return UNMEASURED, (f"{stage.name} needs a live {stage.host}; measured on `{here}`, "
                            f"where nothing is scheduled to advance it -- absence here is not a "
                            f"stall (L1.28a: UNMEASURED is the answer, not zero)")
    if not m.source_present:
        return UNMEASURED, f"{stage.name}: {m.source} -- unmeasured, which is a verdict, not zero"
    w = stage.stall_window_s
    if m.newest_age_s is not None and m.newest_age_s <= w:
        return ALIVE, (f"{m.count_1h} in the last hour, {m.count_24h} in 24h; newest "
                       f"{m.newest_age_s / 60.0:.0f} min old, inside the {w / 60.0:.0f} min window")
    waiting = m.pending or 0
    if waiting > 0:
        oldest = ("" if m.oldest_pending_age_s is None
                  else f", oldest waiting {m.oldest_pending_age_s / 3600.0:.1f} h")
        newest = ("no output ever" if m.newest_age_s is None
                  else f"newest output {m.newest_age_s / 3600.0:.1f} h old")
        return STALLED, (f"{waiting} input row(s) waiting on `{stage.organ}` and {newest} "
                         f"(window {w / 60.0:.0f} min){oldest} -- DEFECT")
    if m.newest_age_s is None:
        return UNMEASURED, f"{stage.name}: {m.source} carries no readable timestamp"
    return SLOW, (f"nothing waiting, but newest output is {m.newest_age_s / 3600.0:.1f} h old "
                  f"against a {w / 60.0:.0f} min window")


# ------------------------------------------------------------------------- the organ's clock
def _last_runs(root: Path, window_days: int = 30) -> dict[str, dict[str, Any]]:
    """When each leg last ran, from the compute ledger. Missing is UNMEASURED, not "never".

    Thirty days is `compute_ledger.WINDOW_DAYS`, deliberately: a shorter window turned every
    organ into UNMEASURED on a box whose cycle has been down for a week, which hides the single
    most useful fact in the report -- WHEN the stalled organ last ran."""
    p = root / "desks" / "mt5" / "data" / "compute_ledger.jsonl"
    out: dict[str, dict[str, Any]] = {}
    if not p.exists():
        return out
    cut = time.time() - window_days * DAY_S
    for row in _tail_jsonl(p, 60_000):
        name = str(row.get("run") or "")
        t = _parse(row.get("at"))
        if not name or t is None or t < cut:
            continue
        prev = out.get(name)
        if prev is None or t > float(prev["_t"]):
            out[name] = {"_t": t, "at": row.get("at"), "outcome": row.get("outcome"),
                         "wall_s": row.get("wall_s")}
    for v in out.values():
        v.pop("_t", None)
    return out


# ------------------------------------------------------------------------------------ build
def build(root: Path | None = None, *, now: float | None = None,
          here: str | None = None, budget_s: float = 240.0) -> dict[str, Any]:
    base = root or ROOT
    t0 = time.monotonic()
    t = now if now is not None else time.time()
    facts = {"kind": here, "hostname": hostname(), "mt5_package": None,
             "enabled_box_clocks": None, "why": "host supplied by the caller"} \
        if here else host_facts()
    where = str(facts["kind"])
    runs = _last_runs(base)
    stages: list[dict[str, Any]] = []
    for st in STAGES:
        if time.monotonic() - t0 > budget_s:
            stages.append({"stage": st.name, "organ": st.organ, "verdict": UNMEASURED,
                           "why": f"budget of {budget_s:.0f}s exhausted before this stage ran",
                           "host": st.host, "measured_on": where})
            continue
        try:
            m = st.measure(base, t)
        except (OSError, ValueError, sqlite3.Error, KeyError, TypeError) as exc:
            m = Measure(source=f"{type(exc).__name__}: {exc}")
        verdict, why = judge(st, m, here=where)
        last = runs.get(st.organ)
        stages.append({
            "stage": st.name, "organ": st.organ, "verdict": verdict, "why": why,
            "consumes": st.consumes, "produces": st.produces,
            "cadence_s": st.cadence_s, "stall_window_s": st.stall_window_s,
            "host": st.host, "measured_on": where,
            "organ_last_run": last or {"at": UNMEASURED,
                                       "why": f"`{st.organ}` has no costed run in 30 days"},
            **m.to_dict(),
        })
    counts = {v: sum(1 for s in stages if s["verdict"] == v) for v in VERDICTS}
    defects = [{"stage": s["stage"], "organ": s["organ"], "why": s["why"],
                "organ_last_run": s.get("organ_last_run")}
               for s in stages if s["verdict"] == STALLED]
    first = next((s for s in stages if s["verdict"] == STALLED), None)
    return {
        "at": datetime.fromtimestamp(t, tz=UTC).isoformat(timespec="seconds"),
        "host": where, "hostname": facts["hostname"], "host_facts": facts,
        "loop_alive": counts[STALLED] == 0,
        "stage_counts": counts,
        "first_stalled_stage": None if first is None else first["stage"],
        "defects": defects,
        "stages": stages,
        "elapsed_s": round(time.monotonic() - t0, 2),
        "rule": ("a stage with input waiting and no output inside two cadences is STALLED and is "
                 "a DEFECT; a stage that needs the trading box is UNMEASURED off it, never "
                 "STALLED; an absent source is UNMEASURED, never zero"),
        "sources": {"registry": "data/alpha_registry.sqlite (libs/moat/registry.py)",
                    "judge": "desks/mt5/scripts/external_gauntlet.py (sealed; gate names from "
                             "desks/mt5/research/gate_policy.GATES)",
                    "clock": "desks/mt5/data/compute_ledger.jsonl"},
    }


# ----------------------------------------------------------------------------------- render
def render(doc: Mapping[str, Any]) -> str:
    mark = {ALIVE: "ALIVE ", SLOW: "SLOW  ", STALLED: "STALL ", UNMEASURED: "UNMEAS"}
    c = doc.get("stage_counts") or {}
    lines = [
        "# LOOP LIVENESS -- is the research loop alive, stage by stage",
        "",
        "> DERIVED. Regenerate with `python desks/mt5/research/loop_liveness.py --once`;",
        "> never edit this file. Source: `desks/mt5/reports/LOOP_LIVENESS.json`.",
        "",
        f"Measured {doc.get('at')} on **{doc.get('host')}** (`{doc.get('hostname')}`) -- "
        f"{c.get(ALIVE, 0)} ALIVE, {c.get(SLOW, 0)} SLOW, {c.get(STALLED, 0)} STALLED, "
        f"{c.get(UNMEASURED, 0)} UNMEASURED.",
        "",
        f"Host: {(doc.get('host_facts') or {}).get('why')}",
        "",
        f"**loop_alive: {doc.get('loop_alive')}**"
        + (f" -- first stalled stage: `{doc.get('first_stalled_stage')}`"
           if doc.get("first_stalled_stage") else ""),
        "",
        "| # | stage | verdict | organ | 1h | 24h | newest | waiting | organ last run |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, s in enumerate(doc.get("stages") or [], 1):
        newest = s.get("newest_age_s")
        newest_s = "--" if newest is None else f"{float(newest) / 3600.0:.1f}h"
        last = (s.get("organ_last_run") or {}).get("at") or "--"
        lines.append(
            f"| {i} | `{s.get('stage')}` | {mark.get(str(s.get('verdict')), '?')}"
            f" | `{s.get('organ')}` | {s.get('count_1h')} | {s.get('count_24h')} | {newest_s}"
            f" | {s.get('pending')} | {str(last)[:19]} |")
    lines += ["", "## Why each verdict", ""]
    for s in doc.get("stages") or []:
        lines.append(f"- **{s.get('stage')}** ({s.get('verdict')}): {s.get('why')}")
    defects = doc.get("defects") or []
    lines += ["", "## Defects", ""]
    if not defects:
        lines.append("No STALLED stage on this host.")
    for d in defects:
        lines.append(f"- `{d.get('stage')}` -- organ `{d.get('organ')}`, last run "
                     f"{(d.get('organ_last_run') or {}).get('at')}: {d.get('why')}")
    lines += ["", f"_{doc.get('rule')}_", ""]
    return "\n".join(lines)


def publish(doc: Mapping[str, Any], *, report: Path | None = None,
            markdown: Path | None = None) -> tuple[Path, Path]:
    r = report or REPORT
    m = markdown or DOC
    r.parent.mkdir(parents=True, exist_ok=True)
    r.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    m.parent.mkdir(parents=True, exist_ok=True)
    m.write_text(render(doc), encoding="utf-8")
    try:
        from libs.ops import events
        events.emit("loop_liveness", stage_counts=doc.get("stage_counts"),
                    loop_alive=doc.get("loop_alive"),
                    first_stalled=doc.get("first_stalled_stage"), host=doc.get("host"))
    except Exception:  # an event log must never take the organ down
        pass
    return r, m


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--json", action="store_true", help="print the document")
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s)
    publish(doc)
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    c = doc["stage_counts"]
    print(f"loop liveness on {doc['host']}: {c[ALIVE]} ALIVE, {c[SLOW]} SLOW, "
          f"{c[STALLED]} STALLED, {c[UNMEASURED]} UNMEASURED"
          + (f"; first stalled {doc['first_stalled_stage']}"
             if doc["first_stalled_stage"] else ""))
    for d in doc["defects"]:
        print(f"  DEFECT {d['stage']} <- {d['organ']}: {d['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
