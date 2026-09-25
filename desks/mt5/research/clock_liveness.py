#!/usr/bin/env python3
"""CLOCK LIVENESS -- every forward clock is ADVANCING, or it is repaired in the same pass.

THE PRINCIPAL'S ORDER (2026-09-23): "ensure no clocks are ever frozen or stale and always run
24/7 forward clocks", sharpened the same day into a standing law -- A REPORT IS NOT A REMEDY.
An organ that can close a gap closes it on its own clock. So this organ does not publish lag: it
MEASURES lag against the venue's own calendar, REPAIRS what it finds, and proves the repair by
the only fact that counts -- the clock's own stamp moving.

HOW A CLOCK FREEZES WITH NOTHING FAILING, which is the defect this exists for. MEASURED on the
trading box 2026-09-23: `shadow_forward` advances exactly the rows in its `enrolled` roster, and
that roster is rebuilt every pass from `certified_sleeves()`. The ledger it writes is keyed by
`sleeve_key` and is NEVER pruned. So when an identity leaves the certificate canon -- the canon
oscillates, an admission rule tightens, a gauntlet sweep re-mints a different id -- its row stays
in `shadow_state.json` reading `status: ACTIVE`, and the engine simply stops visiting it. Nothing
raises, nothing exits non-zero, no organ reports a miss: the lane's own health file says
`missing_sleeves: []` because from the roster's point of view nothing is missing. Measured that
day: 483 state rows against a 119-key roster, 364 rows off the roster, and 35 of them still
claiming ACTIVE with their newest attempt 50.8 h old. A stopped clock counted as forward evidence
is worse than no clock, because at day 14 the verdict rule fires on ancient trades.

ACCRUAL IS DEFINED AGAINST THE VENUE, NOT THE WALL CLOCK. A gold clock does not accrue while
Fusion is closed and a weekend gap is not a freeze. `expected_bars` is the number of bars of the
clock's OWN timeframe that the venue actually printed between its last advance and now, counted
from the market constitution the desk already compiles -- `data/market_constraints.json` when the
box has compiled one, else `libs.research.market_constitution.venue_fusion()`, which is the same
rule set in code. Weekends, holidays, the metals break and the share-CFD cash session all come
out of that count, so DORMANT_BY_SESSION is a measured state and never an excuse.

THE VERDICTS, one per clock, each with the organ that owns it:

    ACCRUING            lag within two cadences of the lane that advances it
    BEHIND              lag past that, inside the clock's own freeze window
    FROZEN              lag past the freeze window -- a DEFECT, repaired this pass
    DORMANT_BY_SESSION  the venue printed no bar at all since the last advance
    RETIRED             a terminal status: the desk decided it stops, so it is not expected to
                        advance (calling that DORMANT_BY_SESSION would blame the calendar for a
                        decision the desk made)
    UNMEASURED          no readable stamp, no lane state, or a lane only the trading box can see

THE REPAIRS, raised through the control plane that already owns repair proof
(`libs.ops.control_plane.actuators`), each with `clock_advanced` as its postcondition -- the
SAME clocks' stamps later than they were before the act, never a return code:

    off_roster       the identity is not on the lane engine's roster. REPAIR: re-enrol it
                     DIRECTLY -- `shadow_forward.main(rows=...)` is parameterised for exactly
                     this (the pre-certification lane already reuses it that way) -- so the
                     engine visits the frozen keys in this pass instead of the next canon.
    engine_stopped   the lane's task is disabled or its resident is dead. REPAIR: enable and
                     run it. A lane that only runs inside one session is not 24/7.
    no_bars          the bar supply is down (terminal IPC, a stale H1 source). REPAIR: the bar
                     supply's own boot task, then the lane.
    instrument_gone  the symbol is not in the broker registry any more. REPAIR: retire the clock
                     with that reason -- the ONE legitimate retirement, and evidence is kept.

NOTHING HERE CAPS ENROLMENT. Re-enrolment is uncapped by principal order (forward clocks gather
evidence and deploy no capital); this organ adds no quota, no ranking and no waiting queue, and
retires only an instrument the broker no longer lists.

Clock: hourly leg `clock_liveness` (department forward, `--once --budget-s 300`).
Artifact: `desks/mt5/reports/CLOCK_LIVENESS.json` + `docs/research/CLOCK_LIVENESS.md`.
Consumers: `scripts/check_clock_liveness.py` (the fence: fails while any clock is FROZEN past its
own window, when the frozen count rises above the ratchet, or when this report is stale/absent).
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import socket
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import clock_certificate as cc  # type: ignore[import-not-found]  # noqa: E402

REPORT = DESK / "reports" / "CLOCK_LIVENESS.json"
DOC = ROOT / "docs" / "research" / "CLOCK_LIVENESS.md"
RATCHET = DESK / "data" / "clock_liveness_ratchet.json"
SHADOW_DIR = DESK / "reports" / "shadow"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
CONSTRAINTS = DESK / "data" / "market_constraints.json"
REGISTRY = DESK / "data" / "sleeve_registry.json"

ACCRUING, BEHIND, FROZEN = "ACCRUING", "BEHIND", "FROZEN"
DORMANT, RETIRED, UNMEASURED = "DORMANT_BY_SESSION", "RETIRED", "UNMEASURED"
VERDICTS = (ACCRUING, BEHIND, FROZEN, DORMANT, RETIRED, UNMEASURED)

#: Two cadences is the desk's standing rule for an hourly organ (`lease.TTL_BY_CLASS["hourly"]`
#: is 7200 s for the same reason): one missed pass is a hiccup, two is a stop.
STALL_CADENCES = 2

#: Terminal statuses. A row carrying one is not expected to advance.
TERMINAL_PREFIXES = ("RETIRED", "VOID", "REFUSED", "QUARANT", "KILLED", "DEAD")

TF_SECONDS: dict[str, int] = {
    "M1": 60, "M5": 300, "M10": 600, "M15": 900, "M20": 1200, "M30": 1800,
    "H1": 3600, "H2": 7200, "H3": 10800, "H4": 14400, "H6": 21600, "H8": 28800,
    "H12": 43200, "D1": 86400, "W1": 604800,
}

#: How far back accrual is counted. A clock that has not moved in six weeks is FROZEN however the
#: remaining bars are counted, and an unbounded walk is how a census becomes a budget hole.
MAX_LOOKBACK_DAYS = 45


# ------------------------------------------------------------------------------------- utils
#: The scheduler read succeeded. Any other value is a REASON the task list is short or empty,
#: and `host_kind` must not turn any of them into a claim about the tasks themselves.
TASKS_OK = "OK"

#: Why the last `scheduled_tasks()` returned what it did. Module state rather than a return
#: field because `scheduled_tasks()` has callers that only want the mapping; the status is read
#: through `scheduled_tasks_status()` by the one caller that decides what kind of host this is.
_TASKS_STATUS: str = TASKS_OK


def scheduled_tasks_status() -> str:
    """`TASKS_OK`, or why the last scheduler read came back short."""
    return _TASKS_STATUS


def now_utc() -> datetime:
    return datetime.now(UTC)


def mt5_installed() -> bool:
    """`find_spec` rather than `import`: importing MetaTrader5 on a box with a terminal can
    block on the terminal itself, and this organ must never be the thing that hangs the cycle."""
    try:
        import importlib.util
        return importlib.util.find_spec("MetaTrader5") is not None
    except (ImportError, ValueError):  # pragma: no cover
        return False


def host_kind(tasks: Mapping[str, dict[str, Any]],
              read_status: str = TASKS_OK) -> tuple[str, str]:
    """`trading_box` / `box_clocks_off` / `host_unmeasured` / `build_box`, and why.

    A HOST WITH NOTHING SCHEDULED TO ADVANCE A CLOCK CANNOT HAVE A FROZEN ONE. Calling this
    build box's ledger copies FROZEN would blame `shadow_forward` for not running where nothing
    was ever going to run it, and would train the desk to ignore the report. A host with MT5
    tasks of which one is DISABLED is the opposite case: that IS the defect, and it is repaired.

    `read_status` IS THE HALF THAT WAS MISSING, AND ITS ABSENCE SILENTLY DISABLED A LAW.
    `scheduled_tasks()` returned `{}` both when this host has no scheduler and when the
    `schtasks` call FAILED -- and `subprocess.TimeoutExpired` is a subclass of `SubprocessError`,
    so a timeout took the same silent path. An empty mapping then made `enabled` empty, and this
    function announced `box_clocks_off` because "all 0 MT5-* scheduled task(s) are disabled" --
    a VACUOUS TRUTH, true of every host in the world, printed as a measurement.

    MEASURED ON THE TRADING BOX 2026-09-24, and the cost was not cosmetic. `CLOCK_LIVENESS.json`
    carried `host: box_clocks_off`, `host_why: "... all 0 MT5-* scheduled task(s) are disabled"`
    on `vmi3571445`, a host running 98 enabled MT5/E8 tasks. Every one of its 153 clocks was
    stamped UNMEASURED, so `clock_certificate.audit` took its "the clock itself is UNMEASURED on
    this host" branch for all 153 and reported `BACKED 0, BREACHED 0, RETIRED 0`. CLOCK IF AND
    ONLY IF CERTIFICATE -- the law that retired 95 unbacked clocks the day before -- was
    enforcing nothing at all, and the artifact said so in a field nobody reads as an outage.
    The read takes 8-9 s idle and was measured at 121 s under load against a 90 s timeout.

    An unreadable scheduler is UNMEASURED (L1.28a): a real answer, never a pass, and never the
    claim that the host's clocks are switched off.
    """
    if not mt5_installed():
        return "build_box", ("no MetaTrader5 package here: no terminal, no bars, nothing "
                             "scheduled to advance a forward clock")
    if read_status != TASKS_OK:
        return "host_unmeasured", (
            f"the scheduler could not be read on this host ({read_status}), so whether anything "
            f"advances a clock here is UNMEASURED. This is NOT `box_clocks_off`: an unreadable "
            f"task list is not evidence that the tasks are disabled, and reading it as one "
            f"stamped every clock UNMEASURED and left CLOCK IF AND ONLY IF CERTIFICATE "
            f"enforcing nothing")
    enabled = [n for n, t in tasks.items()
               if str(t.get("state", "")).strip().lower() == "enabled"]
    if not enabled:
        return "box_clocks_off", (f"the MetaTrader5 package is installed and all "
                                  f"{len(tasks)} MT5-* scheduled task(s) are disabled: nothing "
                                  f"is scheduled to advance a clock on this host")
    return "trading_box", (f"MetaTrader5 installed and {len(enabled)} of {len(tasks)} MT5-* "
                           f"task(s) enabled: this host advances clocks")


def hostname() -> str:
    try:
        return socket.gethostname() or UNMEASURED
    except OSError:  # pragma: no cover - a host without a name is not a case we can provoke
        return UNMEASURED


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None


def parse_ts(value: Any) -> datetime | None:
    """Every stamp shape this desk writes: ISO with T or with a space, Z or offset or naive."""
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    if " " in text and "T" not in text:
        text = text.replace(" ", "T", 1)
    try:
        ts = datetime.fromisoformat(text)
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def is_terminal(status: Any) -> bool:
    s = str(status or "").upper()
    return any(s.startswith(p) for p in TERMINAL_PREFIXES)


def tf_seconds(timeframe: str) -> int:
    return TF_SECONDS.get(str(timeframe or "H1").upper(), 3600)


# --------------------------------------------------------------- the venue's session calendar
class SessionCalendar:
    """Open bars per instrument class, from the market constitution the desk already compiles.

    `data/market_constraints.json` when the box has compiled one (its rows carry each symbol's
    instrument class under the broker's rules in force); otherwise `venue_fusion()`, which is the
    SAME rule set in code rather than a calendar invented here. Either way the answer to "how
    many bars should this clock have seen" is the venue's, not the wall clock's.
    """

    def __init__(self, constraints: Path | None = None) -> None:
        self._venue: Any | None = None
        self._by_symbol: dict[str, str] = {}
        self._source = UNMEASURED
        self._per_day: dict[tuple[str, int, int], int] = {}
        self._open_min: dict[tuple[str, int], frozenset[int]] = {}
        self._closed: dict[date, bool] = {}
        try:
            from libs.research import market_constitution as mc
            self._mc: Any = mc
            self._venue = mc.venue_fusion()
            self._source = "libs/research/market_constitution.py venue_fusion()"
        except Exception as exc:  # pragma: no cover - the import failing IS the measurement
            self._mc = None
            self._source = f"UNMEASURED: market constitution unimportable ({exc!r})"
        doc = read_json(constraints or CONSTRAINTS)
        rows = doc.get("symbols") if isinstance(doc, dict) else None
        if isinstance(rows, list):
            for r in rows:
                if isinstance(r, dict) and r.get("symbol"):
                    self._by_symbol[str(r["symbol"])] = str(r.get("instrument_class") or "")
            self._source += f" + data/market_constraints.json ({len(self._by_symbol)} symbols)"

    @property
    def source(self) -> str:
        return self._source

    def instrument_class(self, symbol: str, asset_class: Any = None) -> str:
        cls = self._by_symbol.get(symbol)
        if cls and cls != UNMEASURED:
            return cls
        if self._mc is not None and asset_class is not None:
            try:
                return str(self._mc.instrument_class_of(asset_class)) or "forex"
            except Exception:
                pass
        return "forex"

    def _open_minutes(self, cls: str, weekday: int) -> frozenset[int]:
        """The minutes of a weekday the venue is CONTINUOUS for this instrument class."""
        key = (cls, weekday)
        hit = self._open_min.get(key)
        if hit is not None:
            return hit
        mins: set[int] = set()
        if self._venue is not None and self._mc is not None:
            # A date with the wanted weekday and no holiday: the template is the weekly rule.
            probe = date(2026, 1, 5) + timedelta(days=weekday)   # 2026-01-05 is a Monday
            try:
                rows = self._mc.rules_in_force(self._venue, probe, cls)
                for m in range(1440):
                    _, state, _ = self._mc._window_of(rows, m, weekday)
                    if state == "CONTINUOUS":
                        mins.add(m)
            except Exception:
                mins = set()
        out = frozenset(mins)
        self._open_min[key] = out
        return out

    def closed_day(self, day: date) -> bool:
        if self._venue is None or self._mc is None:
            return False
        hit = self._closed.get(day)
        if hit is not None:
            return hit
        try:
            out = bool(self._mc.closed_day_state(self._venue, day))
        except Exception:
            out = False
        self._closed[day] = out
        return out

    def bars_per_day(self, cls: str, tf: str, weekday: int) -> int:
        key = (cls, weekday, tf_seconds(tf))
        hit = self._per_day.get(key)
        if hit is not None:
            return hit
        step = max(1, tf_seconds(tf) // 60)
        mins = self._open_minutes(cls, weekday)
        n = sum(1 for m in range(0, 1440, step) if m in mins)
        self._per_day[key] = n
        return n

    def open_span(self, cls: str, tf: str, start: datetime,
                  end: datetime) -> tuple[int, int]:
        """(bars of `tf` the venue printed, minutes the venue was open) over [start, end).

        BOTH, and the second is not decoration. A clock whose last advance was 30 minutes ago
        has seen ZERO new H1 bars and the venue was open the whole time -- that is ACCRUING, not
        DORMANT, and counting only bars cannot tell the two apart. Whole days come from the
        weekly template; the two partial days are walked, holidays and weekends removed.
        """
        if self._venue is None or self._mc is None or end <= start:
            return 0, 0
        step = max(1, tf_seconds(tf) // 60)
        try:
            lo = self._mc.local_time(start, self._venue.tz)
            hi = self._mc.local_time(end, self._venue.tz)
        except Exception:
            return 0, 0
        bars = open_minutes = 0
        d, last = lo.date(), hi.date()
        while d <= last:
            if self.closed_day(d):
                d += timedelta(days=1)
                continue
            mins = self._open_minutes(cls, d.weekday())
            if d != lo.date() and d != last:
                bars += self.bars_per_day(cls, tf, d.weekday())
                open_minutes += len(mins)
            else:
                first_min = lo.hour * 60 + lo.minute if d == lo.date() else 0
                last_min = hi.hour * 60 + hi.minute if d == last else 1440
                window = range(first_min, last_min)
                open_minutes += sum(1 for m in window if m in mins)
                bars += sum(1 for m in range(0, 1440, step)
                            if first_min <= m < last_min and m in mins)
            d += timedelta(days=1)
        return bars, open_minutes

    def open_bars(self, cls: str, tf: str, start: datetime, end: datetime) -> int:
        return self.open_span(cls, tf, start, end)[0]


# ------------------------------------------------------------------------------------- lanes
class Lane:
    """One forward lane: its state file, the organ that advances it, and how often."""

    def __init__(self, name: str, state: str, organ: str, mechanism: str, cadence_s: int,
                 nested: str | None = None, health: str | None = None,
                 symbol_prefixed: bool = False, symbol_at: str | None = None,
                 task: str | None = None) -> None:
        self.name, self.state, self.organ = name, state, organ
        self.mechanism, self.cadence_s, self.nested = mechanism, cadence_s, nested
        #: Does this lane key its rows `SYMBOL.<...>`? The scalp lane keys by strategy name.
        self.symbol_prefixed = symbol_prefixed
        #: A dotted path inside the lane's own state file naming the one symbol it trades, when
        #: the lane declares one (the scalp lane publishes `source.symbol`). Measured, never
        #: assumed: an absent path leaves every row's symbol UNRESOLVED.
        self.symbol_at = symbol_at
        self.symbol = ""
        #: The scheduled task that RUNS this lane, so a repair can run the lane itself rather
        #: than only the thing the lane was waiting for.
        self.task = task
        #: The file the lane's own cycle writes its `errors` into, when that is a different file
        #: from the ledger (shadow_cycle writes reports/shadow/shadow_health.json, and the bar
        #: supply failing shows up ONLY there -- the ledger has no room to say so).
        self.health = health

    @property
    def path(self) -> Path:
        return SHADOW_DIR / self.state

    @property
    def health_path(self) -> Path | None:
        return None if self.health is None else SHADOW_DIR / self.health

    def rows(self) -> dict[str, dict[str, Any]]:
        doc = read_json(self.path)
        if not isinstance(doc, dict):
            return {}
        if self.symbol_at:
            node: Any = doc
            for part in self.symbol_at.split("."):
                node = node.get(part) if isinstance(node, dict) else None
            self.symbol = str(node) if node else ""
        src = doc.get(self.nested) if self.nested else doc
        if not isinstance(src, dict):
            return {}
        fields = ("last_attempt_at", "forward_start", "n", "last_entry", "status")
        return {k: v for k, v in src.items()
                if isinstance(v, dict) and any(f in v for f in fields)}


LANES: tuple[Lane, ...] = (
    Lane("main", "shadow_state.json", "shadow_forward",
         "MT5-Shadow (hourly, research/shadow_cycle.py) + leg enrol_clocks inside "
         "MT5-Dept-Forward (resident, every 10 min)", 3600, health="shadow_health.json",
         symbol_prefixed=True, task="MT5-Shadow"),
    Lane("qquant", "qquant_shadow_state.json", "qquant_shadow",
         "MT5-QQuantShadow (every 30 min, research/qquant_shadow.py)", 1800,
         task="MT5-QQuantShadow"),
    Lane("scalp", "scalp_shadow_state.json", "scalp_shadow",
         "MT5-Shadow (hourly) -> the scalp lane inside research/shadow_cycle.py", 3600,
         nested="sleeves", health="shadow_health.json", symbol_at="source.symbol",
         task="MT5-Shadow"),
    Lane("precert", "precert_shadow_state.json", "precert_shadow",
         "leg precert_shadow inside MT5-Dept-Forward (resident, every 10 min)", 3600),
)
LANE_BY_NAME = {ln.name: ln for ln in LANES}


def last_advance(row: Mapping[str, Any]) -> tuple[datetime | None, str]:
    """The freshest fact that proves the ENGINE touched this clock.

    The engine touch, never the trade: a clock whose signal did not fire is still accruing
    evidence (the absence of a signal IS the evidence), while a clock the engine stopped
    visiting is stopped however many trades sit frozen in its row.
    """
    for field in ("last_attempt_at", "last_evaluated_bar", "last_entry", "bars_freshest",
                  "status_at"):
        ts = parse_ts(row.get(field))
        if ts is not None:
            return ts, field
    return None, ""


# ------------------------------------------------------------------------------------ roster
def engine_roster() -> tuple[set[str] | None, str]:
    """The keys `shadow_forward` will actually visit on its next pass.

    Imported rather than inferred: the roster is a function of the certificate canon and the key
    is computed by the engine's own `sleeve_key`, so re-deriving it here would be a second
    implementation that drifts. Off the trading box the import has no canon to read, which is
    UNMEASURED and not an empty roster.
    """
    cwd = os.getcwd()
    try:
        os.chdir(str(DESK))
        import shadow_forward as sf  # type: ignore[import-not-found]
        rows = ([(s, w, dict(sf.WINDOWS.get(w, {})), "session_range_breakout", "LONG")
                 for s, w in sf.SLEEVES] + sf.certified_sleeves())
        keys = set()
        for row in rows:
            fam = row[3] if len(row) > 3 else "session_range_breakout"
            side = row[4] if len(row) > 4 else "LONG"
            keys.add(sf.sleeve_key(row[0], row[1], row[2], fam, side))
        return keys, f"shadow_forward.certified_sleeves() -> {len(keys)} key(s)"
    except Exception as exc:
        return None, f"UNMEASURED: shadow_forward roster unreadable ({type(exc).__name__}: {exc})"
    finally:
        os.chdir(cwd)


def universe_symbols() -> tuple[dict[str, Any], bool]:
    doc = read_json(UNIVERSE)
    if not isinstance(doc, dict):
        return {}, False
    rows = doc.get("symbols") if isinstance(doc.get("symbols"), dict) else doc
    return (rows if isinstance(rows, dict) else {}), True


def symbol_of(lane: Lane, key: str, row: Mapping[str, Any]) -> tuple[str, str]:
    """(symbol, how it was resolved). NEVER guessed from a key shape the lane does not use.

    The scalp lane keys its rows by STRATEGY name (`xau_m5_anti_breakout_overlap`), not by
    symbol, so splitting on the first dot there yields a string that is in no registry -- and
    the honest-looking conclusion "the broker delisted it" would have RETIRED four live XAUUSD
    clocks. A symbol is therefore taken from a declared field, or from the key only on a lane
    that declares its keys are symbol-prefixed; anything else is UNRESOLVED.
    """
    for field in ("symbol", "instrument"):
        val = row.get(field)
        if val:
            return str(val), f"row.{field}"
    if lane.symbol:
        return lane.symbol, f"lane source ({lane.state})"
    if lane.symbol_prefixed:
        return str(key).split(".", 1)[0].split("@", 1)[0].split("#", 1)[0], "key prefix"
    return "", "UNRESOLVED"


def timeframe_of_key(key: str, row: Mapping[str, Any]) -> str:
    tf = str(row.get("timeframe") or "").upper()
    if tf in TF_SECONDS:
        return tf
    if "@" in key:
        tail = key.split("@", 1)[1].split("#", 1)[0].split(".", 1)[0].upper()
        if tail in TF_SECONDS:
            return tail
    return "H1"


# --------------------------------------------------------------------------------- the census
def judge_clock(lane: Lane, key: str, row: Mapping[str, Any], cal: SessionCalendar,
                uni: Mapping[str, Any], roster: set[str] | None, now: datetime, *,
                host: str = "trading_box", host_why: str = "",
                lane_mtime: datetime | None = None) -> dict[str, Any]:
    sym, sym_how = symbol_of(lane, key, row)
    tf = timeframe_of_key(key, row)
    meta = uni.get(sym) if isinstance(uni.get(sym), dict) else {}
    cls = cal.instrument_class(sym, (meta or {}).get("asset_class"))
    ts, field = last_advance(row)
    if ts is None and lane_mtime is not None:
        # A LANE THAT WRITES NO PER-ROW STAMP STILL PROVES IT VISITED ITS ROWS. The scalp lane's
        # rows carry `forward_start` and nothing else that moves, so keying accrual on the row
        # alone would call four live XAUUSD clocks FROZEN for ever however often the engine ran.
        # The ledger's own mtime is the engine's receipt for every row in it.
        ts, field = lane_mtime, f"{lane.state} mtime (the lane writes no per-row stamp)"
    bars_day = max(1, cal.bars_per_day(cls, tf, 2))     # a Wednesday: a full venue day
    cadence_bars = max(1, math.ceil(lane.cadence_s / tf_seconds(tf)))
    tolerance = STALL_CADENCES * cadence_bars
    freeze_bars = max(tolerance, bars_day)
    out: dict[str, Any] = {
        "lane": lane.name, "key": key, "symbol": sym, "symbol_from": sym_how, "timeframe": tf,
        "instrument_class": cls, "status": row.get("status"), "n": row.get("n"),
        "organ": lane.organ, "mechanism": lane.mechanism,
        "last_advance": None if ts is None else ts.isoformat(),
        "last_advance_field": field or None,
        "cadence_bars": cadence_bars, "tolerance_bars": tolerance,
        "freeze_bars": freeze_bars, "window_s": freeze_bars * tf_seconds(tf),
        "on_roster": None if roster is None else (key in roster),
    }
    if host != "trading_box":
        out |= {"expected_bars": None, "actual_bars": None, "lag_bars": None,
                "verdict": UNMEASURED,
                "why": (f"this clock needs a host that advances it; measured on a `{host}` -- "
                        f"{host_why}. Absence here is not a freeze (L1.28a: UNMEASURED is the "
                        f"answer, never a zero and never a pass)")}
        return out
    if is_terminal(row.get("status")):
        out |= {"expected_bars": 0, "actual_bars": 0, "lag_bars": 0, "verdict": RETIRED,
                "why": (f"status {row.get('status')!r} is terminal: the desk decided this clock "
                        f"stops, so it is not expected to advance")}
        return out
    if ts is None:
        out |= {"expected_bars": None, "actual_bars": None, "lag_bars": None,
                "verdict": UNMEASURED,
                "why": ("the row carries no readable stamp, so whether it advanced is "
                        "UNMEASURED -- a verdict, not a zero")}
        return out
    since = max(ts, now - timedelta(days=MAX_LOOKBACK_DAYS))
    expected, open_minutes = cal.open_span(cls, tf, since, now)
    actual = 0        # the row's own stamp did not move since `ts`: that IS the measurement
    lag = max(0, expected - actual)
    out |= {"expected_bars": expected, "actual_bars": actual, "lag_bars": lag,
            "open_minutes": open_minutes,
            "age_s": round((now - ts).total_seconds(), 1), "session_source": cal.source}
    if expected == 0 and open_minutes == 0:
        out |= {"verdict": DORMANT,
                "why": (f"the venue was CLOSED for every minute since {ts.isoformat()}: a "
                        f"{cls} instrument printed no {tf} bar to accrue -- closed, not frozen")}
    elif lag <= tolerance:
        out |= {"verdict": ACCRUING,
                "why": (f"{expected} venue {tf} bar(s) since its last advance, inside the "
                        f"{tolerance}-bar tolerance ({STALL_CADENCES} cadences of "
                        f"`{lane.organ}` at {lane.cadence_s}s)")}
    elif lag <= freeze_bars:
        out |= {"verdict": BEHIND,
                "why": (f"{lag} {tf} bar(s) behind, past the {tolerance}-bar tolerance but "
                        f"inside its own {freeze_bars}-bar freeze window")}
    else:
        out |= {"verdict": FROZEN,
                "why": (f"{lag} venue {tf} bar(s) with no advance, past its own "
                        f"{freeze_bars}-bar window -- DEFECT owned by `{lane.organ}`")}
    return out


def diagnose(clock: Mapping[str, Any], uni: Mapping[str, Any], uni_known: bool,
             health: Mapping[str, Any]) -> tuple[str, str]:
    """Why this clock froze, in the vocabulary the repairs are keyed by."""
    sym = str(clock.get("symbol"))
    how = str(clock.get("symbol_from") or "")
    if how == "UNRESOLVED":
        return "symbol_unresolved", ("this lane does not declare which instrument the row trades "
                                     "and its key is not symbol-prefixed, so whether the "
                                     "instrument still exists is UNMEASURED -- never guessed")
    if uni_known and uni and sym and sym not in uni:
        return "instrument_gone", (f"{sym} (from {how}) is not in the broker registry "
                                   f"(data/universe/universe.json) any more")
    lane_row = health.get(str(clock.get("lane"))) or {}
    if lane_row.get("engine_stopped"):
        return "engine_stopped", str(lane_row.get("engine_why")
                                     or "the lane's engine is not scheduled")
    if lane_row.get("bars_down"):
        return "no_bars", str(lane_row.get("bars_why") or "the lane's bar supply is down")
    if clock.get("on_roster") is False:
        return "off_roster", ("the identity is not on `shadow_forward`'s roster, so the engine "
                              "never visits it: the ledger row outlived the canon that minted it")
    if clock.get("on_roster") is None:
        return "unmeasured_roster", ("the engine roster is unreadable on this host, so the cause "
                                     "is UNMEASURED and no repair can be aimed")
    return "engine_skipped", ("the identity IS on the roster and the engine still has not "
                              "advanced it: the pass is dying before it reaches this key")


# ------------------------------------------------------------------------------- lane health
def scheduled_tasks() -> dict[str, dict[str, Any]]:
    """Every MT5-* scheduled task with its state and last result. Windows only; elsewhere {}.

    THE STATUS IS PUBLISHED, NOT SWALLOWED. `_TASKS_STATUS` records why this returned few or no
    rows, because `{}` used to mean three different things -- no scheduler, a failed call, and a
    genuinely empty task list -- and `host_kind` read all three as "every task is disabled".
    A timeout is the case that actually fires: `TimeoutExpired` subclasses `SubprocessError`, the
    read costs 8-9 s idle and was measured at 121 s under load, and the ceiling here is 90 s.
    """
    global _TASKS_STATUS
    _TASKS_STATUS = TASKS_OK
    if os.name != "nt":
        _TASKS_STATUS = "NOT_WINDOWS"
        return {}
    try:
        raw = subprocess.run(["schtasks", "/Query", "/FO", "CSV", "/V"], capture_output=True,
                             text=True, timeout=90, check=False).stdout
    except subprocess.TimeoutExpired:
        # NAMED SEPARATELY BECAUSE IT IS THE ONE THAT HAPPENS. Caught before the broader clause
        # below, which would otherwise absorb it -- that inheritance is the whole defect.
        _TASKS_STATUS = "TIMEOUT after 90s: the scheduler query did not return in time"
        return {}
    except (OSError, subprocess.SubprocessError) as exc:
        _TASKS_STATUS = f"READ_FAILED: {type(exc).__name__}: {exc}"
        return {}
    rows = list(csv.reader(io.StringIO(raw)))
    if not rows:
        _TASKS_STATUS = "EMPTY_OUTPUT: schtasks returned no rows at all"
        return {}
    head = [c.strip().lower() for c in rows[0]]

    def col(name: str) -> int | None:
        return head.index(name) if name in head else None

    i_n, i_s, i_st = col("taskname"), col("scheduled task state"), col("status")
    i_l, i_r, i_x = col("last run time"), col("last result"), col("next run time")
    i_rep, i_typ = col("repeat: every"), col("schedule type")
    out: dict[str, dict[str, Any]] = {}
    for r in rows[1:]:
        if i_n is None or len(r) <= i_n:
            continue
        name = r[i_n].lstrip("\\")
        if not name.upper().startswith("MT5-"):
            continue

        def g(i: int | None, row: list[str] = r) -> str:
            return row[i] if i is not None and len(row) > i else ""

        row = {"state": g(i_s), "status": g(i_st), "last_run": g(i_l),
               "last_result": g(i_r), "next_run": g(i_x), "repeat": g(i_rep),
               "schedule_type": g(i_typ)}
        # `schtasks /V` prints ONE ROW PER TRIGGER, and only one of them carries the repetition.
        # Keeping the first row alone read `repeat: N/A` for a task that does repeat every ten
        # minutes -- which would have called a live 24/7 resident SINGLE_SESSION and "repaired"
        # a schedule that was already right. So later rows merge in the fields the first lacked.
        if name in out:
            for k, v in row.items():
                if v and not _informative(out[name].get(k)):
                    out[name][k] = v
        else:
            out[name] = row
    return out


def _informative(value: Any) -> bool:
    return bool(value) and str(value).strip().upper() not in ("N/A", "", "DISABLED")


def repeats_all_day(task: Mapping[str, Any]) -> bool:
    """Does this task fire around the clock, or only inside one session?

    A repetition interval means 24/7 by construction. A DAILY/ONCE trigger with no repetition
    is a lane that runs in ONE window a day -- which is exactly "a clock lane that only runs
    inside one session", and it is repaired rather than noted.
    """
    if _informative(task.get("repeat")):
        return True
    kind = str(task.get("schedule_type") or "").strip().upper()
    return kind in ("HOURLY", "MINUTE", "ONLOGON", "ONSTART", "ONIDLE", "ONEVENT")


def lane_health(lanes: Sequence[Lane],
                tasks: Mapping[str, dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    """Is each lane's mechanism actually running, and is its bar supply up?

    24/7 IS A PROPERTY OF THE MACHINE, NOT A HOPE. A lane whose task is DISABLED has not been
    slow, it has been off, and no amount of re-enrolment moves its clocks.
    """
    all_tasks = scheduled_tasks() if tasks is None else dict(tasks)
    out: dict[str, dict[str, Any]] = {}
    for ln in lanes:
        row: dict[str, Any] = {"lane": ln.name, "mechanism": ln.mechanism,
                               "state_file": ln.path.name, "state_mtime": None,
                               "engine_stopped": False, "bars_down": False}
        try:
            row["state_mtime"] = datetime.fromtimestamp(ln.path.stat().st_mtime, UTC).isoformat()
        except OSError:
            row["state_mtime"] = None
        # AN ERROR BELONGS TO THE LANE ITS KEY NAMES. `shadow_cycle` writes ONE health file for
        # several lanes, so attaching every row of it to every lane blamed the main lane's
        # orphaned clocks on `scalp_bar_refresh` -- a true error about a different lane, which
        # would have sent 39 clocks to the terminal-boot repair instead of re-enrolment.
        others = [x.name for x in lanes if x.name != ln.name]
        errs: dict[str, Any] = {}
        for doc in (read_json(ln.path), read_json(ln.health_path) if ln.health_path else None):
            found = doc.get("errors") if isinstance(doc, dict) else None
            if not isinstance(found, dict):
                continue
            for k, v in found.items():
                name = str(k).lower()
                if ln.name in name or not any(o in name for o in others):
                    errs[k] = v
        if errs:
            joined = " | ".join(f"{k}: {v}" for k, v in errs.items())
            row["lane_errors"] = joined[:400]
            if "IPC" in joined or "no MT5 history source" in joined or "no bars" in joined:
                row["bars_down"] = True
                row["bars_why"] = joined[:240]
        for tname, t in all_tasks.items():
            if tname in ln.mechanism:
                row.setdefault("tasks", {})[tname] = t
                if str(t.get("state", "")).strip().lower() == "disabled":
                    row["engine_stopped"] = True
                    row["disabled_task"] = tname
                    row["engine_why"] = (f"scheduled task {tname} is DISABLED: this lane is not "
                                         f"running 24/7, it is not running at all")
        out[ln.name] = row
    return out


# ------------------------------------------------------------------------- 24/7 is a property
#: Every task that must fire around the clock for a forward clock to advance: the lane engines,
#: the forward resident that carries `enrol_clocks` and this organ's own leg, and the core hourly
#: pass that carries `forward_reconcile`. Named here so the audit is a LIST, not a guess.
CLOCK_TASKS: tuple[tuple[str, str], ...] = (
    ("MT5-Shadow", "runs shadow_cycle -> shadow_forward, the main and scalp lanes"),
    ("MT5-QQuantShadow", "runs qquant_shadow, the qquant lane"),
    ("MT5-Dept-Forward", "the forward department resident: legs enrol_clocks and clock_liveness"),
    ("MT5-HourlyCore", "the core hourly pass: leg forward_reconcile"),
    ("MT5-ForwardReconcile", "the standalone forward reconciler"),
)

#: The repetition a clock lane is put on when it is found firing once a day. 60 minutes is the
#: main lane's own cadence, so this never makes a lane run more often than its engine expects.
REPAIR_INTERVAL_MIN = 60


def ensure_24x7(tasks: Mapping[str, dict[str, Any]], *, apply: bool = True,
                runner: Any = None) -> list[dict[str, Any]]:
    """24/7 IS A PROPERTY OF THE MACHINE, NOT A HOPE -- so it is ENFORCED, not reported.

    A task that advances clocks and is DISABLED is enabled and run; one that fires in a single
    daily window is put on a repetition that covers the day. Both are done unconditionally, on
    every pass, whether or not a clock has frozen yet: waiting for the freeze is waiting for the
    evidence to be lost (LAWS 7, A REPORT IS NOT A REMEDY).
    """
    run = runner or (lambda argv: subprocess.run(list(argv), capture_output=True, text=True,
                                                 timeout=120, check=False).returncode)
    out: list[dict[str, Any]] = []
    for name, why in CLOCK_TASKS:
        t = tasks.get(name)
        if t is None:
            out.append({"task": name, "role": why, "verdict": "ABSENT", "acted": [],
                        "why": f"{name} is not registered on this host: nothing here runs it"})
            continue
        state = str(t.get("state") or "").strip().lower()
        row: dict[str, Any] = {"task": name, "role": why, "state": t.get("state"),
                               "repeat": t.get("repeat"), "schedule_type": t.get("schedule_type"),
                               "last_run": t.get("last_run"), "last_result": t.get("last_result"),
                               "next_run": t.get("next_run"), "acted": []}
        if state == "disabled":
            row["verdict"] = "DISABLED"
            row["why"] = f"{name} is DISABLED: {why} -- this lane is not running at all"
            if apply:
                rc = run(("schtasks", "/Change", "/TN", name, "/ENABLE"))
                row["acted"].append({"enable": rc})
                if rc == 0:
                    row["acted"].append({"run": run(("schtasks", "/Run", "/TN", name))})
                    row["verdict"] = "ENABLED_AND_RUN"
        elif not repeats_all_day(t):
            row["verdict"] = "SINGLE_SESSION"
            row["why"] = (f"{name} fires on a {t.get('schedule_type')} trigger with no "
                          f"repetition: {why} runs in ONE window a day, so a clock that stops "
                          f"between windows stays stopped all day")
            if apply:
                rc = run(("schtasks", "/Change", "/TN", name,
                          "/RI", str(REPAIR_INTERVAL_MIN), "/DU", "24:00"))
                row["acted"].append({"add_repetition_min": REPAIR_INTERVAL_MIN, "rc": rc})
                if rc == 0:
                    row["verdict"] = "REPEATING_24X7"
        else:
            row["verdict"] = "RUNNING_24X7"
            row["why"] = f"{name} repeats ({t.get('repeat') or t.get('schedule_type')}): {why}"
        out.append(row)
    return out


# -------------------------------------------------------------------------------- the repairs
def _stamp_of(lane_name: str, key: str) -> datetime | None:
    ln = LANE_BY_NAME.get(lane_name)
    if ln is None:
        return None
    row = ln.rows().get(key)
    return None if row is None else last_advance(row)[0]


def clock_advanced_postcondition(targets: Sequence[tuple[str, str, datetime | None]]) -> Any:
    """The only proof this organ accepts: the SAME clocks' own stamps are later than they were.

    `shadow_forward` has exited zero while being killed partway through the same prefix every
    hour, so a return code proves nothing about the clock the repair was aimed at.
    """
    from libs.ops.control_plane.actuators import Postcondition

    def check(_ctx: Mapping[str, Any]) -> tuple[bool | None, str]:
        if not targets:
            return None, "no clock was aimed at, so the repair's effect is UNMEASURED"
        moved, still, unknown = [], [], []
        for lane_name, key, before in targets:
            after = _stamp_of(lane_name, key)
            if after is None:
                unknown.append(key)
            elif before is None or after > before:
                moved.append(key)
            else:
                still.append(key)
        if unknown and not moved:
            return None, (f"{len(unknown)} aimed clock(s) have no readable stamp after the "
                          f"repair: UNMEASURED, which is not a pass")
        if moved:
            return True, (f"{len(moved)} of {len(targets)} aimed clock(s) advanced "
                          f"(e.g. {moved[0][:70]}); {len(still)} did not")
        return False, (f"none of the {len(targets)} aimed clock(s) advanced: the action ran and "
                       f"the clocks are where they were")

    return Postcondition("clock_advanced", check)


def _with_postcondition(act: Any, pc: Any) -> Any:
    from dataclasses import replace
    return replace(act, postconditions=(pc,))


def reenrol_actuator(keys: Sequence[str], budget_s: float) -> Any:
    """Re-enrol frozen main-lane keys DIRECTLY, through `shadow_forward.main(rows=...)`.

    The engine is parameterised for exactly this -- `precert_shadow.py` already passes its own
    rows -- so the frozen identities are visited in THIS pass rather than waiting for a canon
    that may never mint them again. It caps nothing: every frozen key that can be reconstructed
    from the lane's own ledger is handed over.
    """
    from libs.ops.control_plane.actuators import Actuator
    payload = DESK / "data" / "clock_liveness_reenrol.json"
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_text(json.dumps(sorted(keys), indent=1), encoding="utf-8")
    window = int(max(60.0, budget_s))
    return Actuator(
        name="clock_reenrol",
        argv=(sys.executable, "-W", "ignore", str(DESK / "research" / "clock_reenrol.py"),
              "--keys-file", str(payload), "--budget-s", str(window)),
        window_s=window, timeout_s=window + 60, cwd=str(DESK),
        component_id="leg:clock_liveness",
        notes=("re-enrols the frozen identities into shadow_forward's own engine; the proof is "
               "their own stamps moving, never the exit code"))


def task_actuator(name: str, task: str, enable: bool, budget_s: float) -> Any:
    from libs.ops.control_plane.actuators import Actuator
    argv = (("schtasks", "/Change", "/TN", task, "/ENABLE") if enable
            else ("schtasks", "/Run", "/TN", task))
    return Actuator(name=name, argv=argv, window_s=int(max(30.0, budget_s)), timeout_s=120,
                    task=task,
                    notes=("a lane that only runs inside one session is not 24/7; enabling and "
                           "running the task is the repair, its clocks advancing is the proof"))


def retire_gone(clocks: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The ONE legitimate retirement: the broker does not list the instrument any more.

    Evidence is never destroyed -- `n`, `cum_r`, `max_dd_r` and every ledger stay exactly as they
    are, and the row records who retired it and why, so it can never claim it was never retired.
    """
    done: list[dict[str, Any]] = []
    by_lane: dict[str, list[str]] = {}
    for c in clocks:
        by_lane.setdefault(str(c["lane"]), []).append(str(c["key"]))
    stamp = now_utc().isoformat()
    for lane_name, keys in by_lane.items():
        ln = LANE_BY_NAME.get(lane_name)
        if ln is None or not ln.path.exists():
            continue
        doc = read_json(ln.path)
        if not isinstance(doc, dict):
            continue
        target = doc.get(ln.nested) if ln.nested else doc
        if not isinstance(target, dict):
            continue
        changed = 0
        for k in keys:
            row = target.get(k)
            if not isinstance(row, dict) or is_terminal(row.get("status")):
                continue
            row["status"] = "RETIRED_INSTRUMENT_GONE"
            row["status_why"] = ("the broker registry no longer lists this symbol, so no venue "
                                 "bar can ever advance this clock (clock_liveness)")
            row["status_at"] = stamp
            row["retired_by"] = "research/clock_liveness.py"
            changed += 1
        if changed:
            tmp = ln.path.with_suffix(".clockliveness.tmp")
            tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
            os.replace(tmp, ln.path)
        done.append({"lane": lane_name, "retired": changed, "keys": keys[:20]})
    return done


def repair(frozen: Sequence[Mapping[str, Any]], budget_s: float, *,
           apply: bool = True) -> list[dict[str, Any]]:
    """Every FROZEN clock leaves this pass with a repair attempted and PROVEN or named UNPROVEN.

    A REPORT IS NOT A REMEDY (LAWS 7): the organ that can close the gap closes it on its own
    clock, and the postcondition is the clock advancing.
    """
    from libs.ops.control_plane.actuators import run_actuator
    acts: list[dict[str, Any]] = []
    if not frozen:
        return acts
    t0 = time.monotonic()
    by_cause: dict[str, list[Mapping[str, Any]]] = {}
    for c in frozen:
        by_cause.setdefault(str(c.get("cause")), []).append(c)

    def aim(rows: Sequence[Mapping[str, Any]]) -> list[tuple[str, str, datetime | None]]:
        return [(str(c["lane"]), str(c["key"]), parse_ts(c.get("last_advance")))
                for c in rows][:400]

    gone = by_cause.pop("instrument_gone", [])
    if gone:
        acts.append({"actuator": "retire_instrument_gone",
                     "result": "REPAIRED" if apply else "DRY_RUN", "repaired": bool(apply),
                     "cause": "instrument_gone", "clocks": len(gone),
                     "detail": retire_gone(gone) if apply else [],
                     "why": ("the broker no longer lists the instrument: retired with its "
                             "reason, evidence kept")})

    engine = by_cause.pop("engine_stopped", [])
    if engine:
        tasks = sorted({str(c.get("disabled_task")) for c in engine if c.get("disabled_task")})
        for task in tasks:
            mine = [c for c in engine if str(c.get("disabled_task")) == task]
            act = _with_postcondition(task_actuator(f"enable:{task}", task, True, 120.0),
                                      clock_advanced_postcondition(aim(mine)))
            acts.append({**run_actuator(act, {}, apply=apply), "cause": "engine_stopped",
                         "clocks": len(mine)})
        if not tasks:
            acts.append({"actuator": "none:engine_stopped", "result": "UNMEASURED",
                         "repaired": False, "cause": "engine_stopped", "clocks": len(engine),
                         "why": "the lane is stopped and no scheduled task names it here"})

    bars = by_cause.pop("no_bars", [])
    if bars:
        # TWO STEPS, BECAUSE THE FIRST ONE ALONE IS NOT THE REPAIR. Booting the terminal restores
        # the bar supply and leaves every clock exactly where it was: the lane has to RUN again
        # for the rows to move. Measured 2026-09-23 -- the terminal was already up and the lane's
        # `no MT5 history source` error was three hours stale, so `boot_bar_supply` proved
        # nothing and four scalp clocks stayed frozen behind an error that had already cleared.
        pc = clock_advanced_postcondition(aim(bars))
        lane_tasks = sorted({str(LANE_BY_NAME[str(c["lane"])].task) for c in bars
                             if LANE_BY_NAME.get(str(c["lane"]))
                             and LANE_BY_NAME[str(c["lane"])].task})
        for name, task in (("boot_bar_supply", "MT5-TerminalBoot"),
                           *[(f"run_lane:{x}", x) for x in lane_tasks]):
            left = max(30.0, min(240.0, budget_s - (time.monotonic() - t0)))
            act = _with_postcondition(task_actuator(name, task, False, left), pc)
            out = {**run_actuator(act, {}, apply=apply), "cause": "no_bars",
                   "clocks": len(bars)}
            acts.append(out)
            if out.get("repaired"):
                break

    # EVERY GAP THIS PASS CAN CLOSE IS CLOSED IN THIS PASS. A clock can be off the roster AND
    # sitting behind a stopped task: the two repairs are independent and cheap, so the frozen
    # main-lane clocks that are off the roster are re-enrolled whichever cause won the diagnosis.
    named = by_cause.pop("off_roster", []) + by_cause.pop("engine_skipped", [])
    off = [c for c in frozen
           if c.get("on_roster") is False and str(c.get("lane")) == "main"]
    seen_keys = {str(c.get("key")) for c in named}
    reenrol = [c for c in named if str(c.get("lane")) == "main"]
    reenrol += [c for c in off if str(c.get("key")) not in seen_keys]
    if reenrol:
        left = max(60.0, budget_s - (time.monotonic() - t0))
        act = _with_postcondition(reenrol_actuator([str(c["key"]) for c in reenrol], left),
                                  clock_advanced_postcondition(aim(reenrol)))
        acts.append({**run_actuator(act, {}, apply=apply), "cause": "off_roster",
                     "clocks": len(reenrol)})

    for cause, rows in by_cause.items():
        acts.append({"actuator": f"none:{cause}", "result": "UNMEASURED", "repaired": False,
                     "cause": cause, "clocks": len(rows),
                     "why": (str(rows[0].get("cause_why")) if rows else "")
                            or f"no repair is defined for cause {cause!r} on this host"})
    return acts


# -------------------------------------------------------------------------------------- build
def census(cal: SessionCalendar, roster: set[str] | None, now: datetime,
           tasks: Mapping[str, dict[str, Any]] | None = None, *,
           host: str = "trading_box", host_why: str = "") -> list[dict[str, Any]]:
    uni, uni_known = universe_symbols()
    health = lane_health(LANES, tasks)
    rows: list[dict[str, Any]] = []
    for ln in LANES:
        lane_rows = ln.rows()
        if not lane_rows:
            rows.append({"lane": ln.name, "key": f"<{ln.name} lane>", "symbol": "",
                         "timeframe": "H1", "organ": ln.organ, "mechanism": ln.mechanism,
                         "verdict": UNMEASURED, "expected_bars": None, "actual_bars": None,
                         "lag_bars": None, "status": None, "on_roster": None,
                         "last_advance": (health.get(ln.name) or {}).get("state_mtime"),
                         "why": (f"{ln.path.name} holds no clock row here: only the trading box "
                                 f"runs `{ln.organ}`, so this lane is UNMEASURED, not empty")})
            continue
        use_roster = roster if ln.name == "main" else None
        mtime = parse_ts((health.get(ln.name) or {}).get("state_mtime"))
        for key, row in lane_rows.items():
            c = judge_clock(ln, key, row, cal, uni, use_roster, now,
                            host=host, host_why=host_why, lane_mtime=mtime)
            if c["verdict"] == FROZEN:
                cause, why = diagnose(c, uni, uni_known, health)
                c["cause"], c["cause_why"] = cause, why
                if cause == "engine_stopped":
                    c["disabled_task"] = (health.get(ln.name) or {}).get("disabled_task")
            rows.append(c)
    return rows


def ratchet_read(path: Path | None = None) -> dict[str, Any]:
    doc = read_json(path or RATCHET)
    return doc if isinstance(doc, dict) else {}


def ratchet_write(frozen_after: int, path: Path | None = None) -> dict[str, Any]:
    """The frozen ratchet may only FALL (L1.50 inverted: a defect ceiling never rises)."""
    p = path or RATCHET
    cur = ratchet_read(p)
    lowest = cur.get("lowest_frozen")
    low = frozen_after if not isinstance(lowest, int) else min(int(lowest), frozen_after)
    doc = {"lowest_frozen": low, "last_frozen": frozen_after, "at": now_utc().isoformat(),
           "rule": ("the enforced ceiling is the lowest frozen count ever measured on this box; "
                    "it may fall and never rise")}
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        pass
    return doc


def _counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {v: sum(1 for c in rows if c.get("verdict") == v) for v in VERDICTS}


def build(budget_s: float = 300.0, *, apply: bool = True) -> dict[str, Any]:
    t0 = time.monotonic()
    now = now_utc()
    cal = SessionCalendar()
    tasks = scheduled_tasks()
    # THE READ'S STATUS TRAVELS WITH THE ROWS. Without it an unreadable scheduler became the
    # claim "all 0 MT5-* tasks are disabled", which stamped every clock UNMEASURED and left the
    # certificate law judging nothing on the box that trades. See `host_kind`.
    host, host_why = host_kind(tasks, scheduled_tasks_status())
    roster, roster_why = engine_roster()
    # THE MACHINE FIRST. A frozen clock behind a disabled task cannot be repaired by re-enrolment,
    # and a lane that fires once a day is a lane whose clocks stop for 23 hours at a time -- so
    # the schedule is made right BEFORE the census, on every pass, frozen or not.
    schedule = (ensure_24x7(tasks, apply=apply) if host == "trading_box"
                else [{"task": n, "role": w, "verdict": UNMEASURED, "acted": [],
                       "why": f"measured on a `{host}`: {host_why}"} for n, w in CLOCK_TASKS])
    if apply and host == "trading_box" and any(r["acted"] for r in schedule):
        tasks = scheduled_tasks()
    before = census(cal, roster, now, tasks, host=host, host_why=host_why)
    counts_before = _counts(before)
    frozen = [c for c in before if c["verdict"] == FROZEN]
    repairs = repair(frozen, max(30.0, budget_s - (time.monotonic() - t0)), apply=apply)
    after = (census(cal, engine_roster()[0], now_utc(), tasks, host=host, host_why=host_why)
             if (repairs and apply) else before)
    counts_after = _counts(after)
    rat = ratchet_write(counts_after[FROZEN]) if apply else ratchet_read()
    # CLOCK IMPLIES CERTIFICATE (principal 2026-09-23). Liveness and legality are two different
    # questions about the same clock: a clock can be ACCRUING beautifully and be running on no
    # certificate at all, which is a breach of a standing law. The audit traces every clock to
    # its backing certificate, pushes each breached CELL to the front of the judge's queue, and
    # takes a clock away only on the judge's own rejection -- never to make the count smaller.
    cert = cc.audit(after, roster=roster, now=now_utc(), apply=apply)
    cert["unbacked_found"] = len(cert.get("retire") or [])
    if apply and cert.get("retire"):
        # STRICT (principal 2026-09-23): every clock without a canonical certificate is retired on
        # the pass it is found. The cell keeps the front of the judge's queue -- `cc.audit` has
        # already submitted it -- but it gathers no forward evidence until it earns a certificate,
        # and if it later does it starts a NEW clock from zero. The accrued days are the stated
        # cost: forward evidence on a cell that never certifies can never be cashed.
        n_retired = cc.retire_unbacked(cert["retire"], LANE_BY_NAME)
        after = census(cal, roster, now_utc(), tasks, host=host, host_why=host_why)
        counts_after = _counts(after)
        cert = cc.audit(after, roster=roster, now=now_utc(), apply=False)
        cert["retired_now"] = n_retired
        cert["unbacked_found"] = n_retired
    cert_ratchet = (cc.ratchet(int(cert["breached"])) if apply and host == "trading_box"
                    else cc.read_ratchet())
    if apply:
        cc.publish_docket(cert)
    still = [c for c in after if c["verdict"] == FROZEN]
    by_cause: dict[str, int] = {}
    for c in still:
        name = str(c.get("cause") or "unclassified")
        by_cause[name] = by_cause.get(name, 0) + 1
    health = lane_health(LANES, tasks)
    return {
        "at": now.isoformat(), "hostname": hostname(),
        "host": host, "host_why": host_why,
        "budget_s": budget_s, "applied": bool(apply),
        "session_source": cal.source, "roster": roster_why,
        "clocks_total": len(after),
        "counts_before": counts_before, "counts": counts_after,
        "frozen_before": counts_before[FROZEN], "frozen_after": counts_after[FROZEN],
        "ratchet": rat, "frozen_by_cause": by_cause, "repairs": repairs,
        "certificate": {**{k: v for k, v in cert.items() if k != "rows"},
                        "ratchet": cert_ratchet,
                        "oldest_breach_age_s": cc.oldest_breach_age_s(cert),
                        "rows": [r for r in cert["rows"]
                                 if r.get("backing") in (cc.BREACHED, cc.AWAITING,
                                                         cc.UNMEASURED)][:400]},
        "schedule": schedule,
        "schedule_verdicts": {v: sum(1 for r in schedule if r.get("verdict") == v)
                              for v in sorted({str(r.get("verdict")) for r in schedule})},
        "lanes": [{"lane": ln.name, "organ": ln.organ, "mechanism": ln.mechanism,
                   "cadence_s": ln.cadence_s,
                   "clocks": sum(1 for c in after if c["lane"] == ln.name),
                   "accruing": sum(1 for c in after
                                   if c["lane"] == ln.name and c["verdict"] == ACCRUING),
                   "frozen": sum(1 for c in after
                                 if c["lane"] == ln.name and c["verdict"] == FROZEN),
                   **{k: v for k, v in (health.get(ln.name) or {}).items()
                      if k in ("state_mtime", "engine_stopped", "engine_why", "bars_down",
                               "bars_why", "lane_errors", "tasks")}}
                  for ln in LANES],
        "frozen": [{k: c.get(k) for k in
                    ("lane", "key", "symbol", "timeframe", "status", "organ", "last_advance",
                     "expected_bars", "actual_bars", "lag_bars", "freeze_bars", "window_s",
                     "cause", "cause_why", "why")} for c in still[:300]],
        # EVERY CLOCK CARRIES THE MECHANISM THAT ADVANCES IT AND WHEN IT LAST DID. A reader who
        # finds one row of this file must not have to join it against anything to know who was
        # supposed to move this clock and when it last moved (principal 2026-09-23).
        "clocks": [{k: c.get(k) for k in
                    ("lane", "key", "symbol", "timeframe", "instrument_class", "status",
                     "organ", "mechanism", "last_advance", "last_advance_field",
                     "expected_bars", "actual_bars", "lag_bars",
                     "freeze_bars", "verdict", "on_roster")} for c in after],
        "elapsed_s": round(time.monotonic() - t0, 2),
        "rule": ("accrual is counted in the VENUE'S bars, never the wall clock; a FROZEN clock "
                 "is repaired in the same pass and the postcondition is its own stamp moving, "
                 "never a zero exit code (LAWS 7: A REPORT IS NOT A REMEDY)"),
    }


# ------------------------------------------------------------------------------------- render
def render(doc: Mapping[str, Any]) -> str:
    c = doc.get("counts") or {}
    b = doc.get("counts_before") or {}
    lines = [
        "# CLOCK LIVENESS -- every forward clock advancing, or repaired in the same pass",
        "",
        "> DERIVED. Regenerate with `python desks/mt5/research/clock_liveness.py --once`;",
        "> never edit this file. Source: `desks/mt5/reports/CLOCK_LIVENESS.json`.",
        "",
        f"Measured {doc.get('at')} on **{doc.get('host')}** (`{doc.get('hostname')}`) over "
        f"**{doc.get('clocks_total')} forward clocks**. "
        f"FROZEN **{doc.get('frozen_before')} -> {doc.get('frozen_after')}** this pass "
        f"(ratchet floor {(doc.get('ratchet') or {}).get('lowest_frozen')}).",
        "",
        "| verdict | before | after |",
        "|---|---:|---:|",
    ]
    for v in VERDICTS:
        lines.append(f"| {v} | {b.get(v, 0)} | {c.get(v, 0)} |")
    lines += ["", "## What advances each lane", "",
              "| lane | clocks | accruing | frozen | mechanism | lane state last written |",
              "|---|---:|---:|---:|---|---|"]
    for ln in doc.get("lanes") or []:
        lines.append(f"| `{ln.get('lane')}` | {ln.get('clocks')} | {ln.get('accruing')} | "
                     f"{ln.get('frozen')} | {ln.get('mechanism')} | "
                     f"{str(ln.get('state_mtime'))[:19]} |")
    ct = doc.get("certificate") or {}
    cn = ct.get("counts") or {}
    lines += ["", "## CLOCK IMPLIES CERTIFICATE", "",
              f"Canon: **{(ct.get('canon') or {}).get('n')}** certificate(s) -- "
              f"{(ct.get('canon') or {}).get('why')} (read, never written).", "",
              "| backing | clocks |", "|---|---:|"]
    for s in cc.BACKING_STATES:
        lines.append(f"| {s} | {cn.get(s, 0)} |")
    lines += ["",
              f"**backed {ct.get('backed')}**, retired {ct.get('retired')}, "
              f"unbacked still live **{ct.get('unbacked_live')}** (zero by construction: an "
              f"unbacked clock is retired the pass it is found); "
              f"{ct.get('unbacked_found', 0)} retired on this pass for want of a certificate. "
              f"Breach ratchet floor {(ct.get('ratchet') or {}).get('lowest_breached')}.",
              "", f"Judge's queue: {(ct.get('queue') or {}).get('why')}",
              "", f"Cost: {ct.get('cost')}",
              "", f"Enrolment: {ct.get('enrolment_note')}", ""]
    lines += ["", "## 24/7: the tasks that advance clocks", "",
              "| task | verdict | repeat | last run | rc | what it advances |",
              "|---|---|---|---|---|---|"]
    for s in doc.get("schedule") or []:
        lines.append(f"| `{s.get('task')}` | {s.get('verdict')} | "
                     f"{s.get('repeat') or s.get('schedule_type') or '--'} | "
                     f"{str(s.get('last_run') or '--')[:19]} | {s.get('last_result') or '--'} | "
                     f"{s.get('role')} |")
    lines += ["", "## Repairs raised this pass", ""]
    if not doc.get("repairs"):
        lines.append("No clock was FROZEN, so no repair was raised.")
    for r in doc.get("repairs") or []:
        lines.append(f"- `{r.get('actuator')}` -> **{r.get('result')}** over "
                     f"{r.get('clocks')} clock(s): {r.get('why') or 'postcondition proved'}")
    lines += ["", "## Still frozen, and why", ""]
    if not doc.get("frozen"):
        lines.append("Nothing is frozen.")
    for f in (doc.get("frozen") or [])[:20]:
        lines.append(f"- `{f.get('lane')}` / `{str(f.get('key'))[:66]}` ({f.get('timeframe')}): "
                     f"{f.get('lag_bars')} bar(s) past a {f.get('freeze_bars')}-bar window -- "
                     f"**{f.get('cause')}**: {f.get('cause_why')}")
    if len(doc.get("frozen") or []) > 20:
        lines.append(f"- ... and {len(doc['frozen']) - 20} more, in the JSON.")
    lines += ["", f"Host: {doc.get('host_why')}",
              f"Sessions from: {doc.get('session_source')}",
              f"Roster: {doc.get('roster')}", "", f"_{doc.get('rule')}_", ""]
    return "\n".join(lines)


def publish(doc: Mapping[str, Any], *, report: Path | None = None,
            markdown: Path | None = None) -> tuple[Path, Path]:
    r, m = report or REPORT, markdown or DOC
    r.parent.mkdir(parents=True, exist_ok=True)
    r.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    m.parent.mkdir(parents=True, exist_ok=True)
    m.write_text(render(doc), encoding="utf-8")
    try:
        from libs.ops import events
        events.emit("CLOCKS_ENROLLED", organ="clock_liveness",
                    clocks=doc.get("clocks_total"), frozen_before=doc.get("frozen_before"),
                    frozen_after=doc.get("frozen_after"),
                    repairs=[a.get("result") for a in (doc.get("repairs") or [])])
    except Exception:      # an event log must never take the organ down
        pass
    return r, m


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and repair nothing; writes the report only")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, apply=not a.dry_run)
    publish(doc)
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    c = doc["counts"]
    print(f"clock liveness on {doc['hostname']}: {doc['clocks_total']} clocks -- "
          f"{c[ACCRUING]} ACCRUING, {c[BEHIND]} BEHIND, {c[FROZEN]} FROZEN, "
          f"{c[DORMANT]} DORMANT_BY_SESSION, {c[RETIRED]} RETIRED, {c[UNMEASURED]} UNMEASURED; "
          f"frozen {doc['frozen_before']} -> {doc['frozen_after']}")
    for r in doc["repairs"]:
        print(f"  REPAIR {r.get('actuator')}: {r.get('result')} over {r.get('clocks')} clock(s)"
              + (f" -- {r.get('why')}" if r.get("why") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
