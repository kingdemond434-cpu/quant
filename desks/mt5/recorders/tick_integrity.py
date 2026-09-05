"""Does the tape say what it claims to say? Per symbol, per day, with a number for every claim.

    py -3 -m recorders.tick_integrity                    # judge every sealed day, write the report
    py -3 -m recorders.tick_integrity --symbols XAUUSD   # probe one symbol
    py -3 -m recorders.tick_integrity --days 7           # only the last week

WHY A CHECKER AND NOT A HEARTBEAT. `moat/moat_fence.py` already watches whether the recorder is
BREATHING -- heartbeat freshness, symbol count, tick progress. That is a liveness check, and a
liveness check cannot see the failure that actually costs money: a recorder that runs perfectly
and captures a tape with holes in it. The desk has been here before in the other direction --
`moat_silver.py` records a converter that died while "the recorder recorded perfectly", and
nobody noticed for a day because nothing measured the OUTPUT. This measures the output.

The distinction matters because of what the tape is FOR. A feature built on an hour that is
silently absent reads the absence as calm: zero quote updates looks exactly like a quiet market,
a flat spread looks like a tight one, and a strategy conditioned on "low quote intensity" will
learn to trade the hours when this desk's recorder was down. That is not a data-quality nicety;
it is a mechanism for manufacturing an edge out of an outage.

WHAT IS MEASURED, and what each number is actually asking:

  n_ticks              how much is there
  coverage_frac        of the minutes this symbol NORMALLY quotes, how many did we capture
  unexplained_minutes  THE HEADLINE. Minutes inside the symbol's own session with no ticks AND
                       no gap row explaining why. Absence that nothing accounts for. Every other
                       number here can be argued about; this one is the tape lying by omission.
  stale_runs           the longest stretch with an unchanged quote, in seconds and in ticks. A
                       frozen feed and a calm market are the same bytes and different facts.
  crossed / locked     bid > ask, and bid == ask. Both are real on a retail CFD feed at session
                       roll and around news; a RATE that moves is a feed changing behaviour.
  monotonic_breaks     ticks the broker delivered out of order INSIDE one segment. Cross-segment
                       overlap is expected by design and is counted separately, not as a defect.
  dup_rate             the cost of the overlap policy, measured rather than assumed
  seal_ok              every segment hashes to what the manifest says it does
  post_seal_writes     a day declared complete that then grew -- the seal was premature or the
                       recorder was still catching up when it stamped it

THE SESSION CALENDAR IS THE SYMBOL'S OWN, AND THIS IS NOT A DETAIL. Coverage needs a denominator:
what SHOULD have been there. A hardcoded 24x5 FX calendar is wrong for the 74 US share CFDs in
this universe -- `research/cost_surface.py` documents the identical mistake costing that module
its entire equity coverage on its first run, because a 20-bar threshold calibrated on FX excluded
every 6.5-hour cash session and the artifact reported it as a clean build. So the denominator
here is measured per symbol from its OWN recorded history: a minute-of-day is IN this symbol's
session if it carried ticks on at least `SESSION_QUORUM` of the days observed. No asset-class
list exists anywhere in this file, and a symbol with too few days to establish a session is
UNMEASURED rather than assumed to trade around the clock.

IT FAILS LOUDLY. `main()` returns 2 on any FAIL verdict. The alternative -- a report that records
a hole and exits 0 -- is a report nobody reads twice, and this desk's own laws call an unread
alarm worse than no alarm because it suppresses the ones that matter.

UNMEASURED IS A VERDICT, NEVER A PASS (L1.28a). A day with too little history behind it to
establish a session, a symbol whose manifest cannot be read, a day whose segments are all
missing: each returns UNMEASURED with the reason attached. None of them counts toward OK.
"""
from __future__ import annotations

import argparse
import json
import sys
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_DESK = _HERE.parent
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from recorders.tape_store import GAP_COLD_START, GAP_RESOLVED, TapeStore  # noqa: E402

SCHEMA = "tick-integrity-1"
REPORT = _DESK / "reports" / "TICK_INTEGRITY.json"
#: The recorder's own in-repo status. Read so this report can tell "no tape because the recorder
#: has never run" from "no tape because it is paused on a disk floor" from "no tape and the
#: recorder says it is RECORDING", which is the loudest of the three: the process believes it is
#: working and the output disagrees.
RECORDER_STATUS = _DESK / "reports" / "TAPE_RECORDER.json"

OK, DEGRADED, FAIL, UNMEASURED = "OK", "DEGRADED", "FAIL", "UNMEASURED"

#: A minute-of-day is in a symbol's session if it carried ticks on at least this share of the
#: days observed. Deliberately loose: holidays, early closes and half-sessions should not shrink
#: the session, and a minute that quotes on two thirds of days is unambiguously a trading minute.
SESSION_QUORUM = 0.60

#: THE SESSION IS PER WEEKDAY, AND THE FIRST VERSION OF THIS FILE GOT IT WRONG. Pooling every day
#: into one mask made the desk's own Sunday fail at 12.5% coverage, because Sunday quotes from
#: 21:00 and was being judged against a Monday-to-Friday session. The same error fires on every
#: Friday close and on any instrument with a shortened session, and the consequence is not a
#: cosmetic false alarm: a checker that reds every weekend teaches its reader to stop reading it,
#: and then it is not there on the day a Tuesday goes missing. Sunday's denominator is Sunday.
MIN_WEEKDAY_OBS = 3

#: Until a weekday has MIN_WEEKDAY_OBS observations of its own -- three weeks for a Sunday -- a
#: Monday-to-Friday day may be judged against the POOLED weekday session, marked provisional, and
#: may only ever reach DEGRADED. Three weeks of blindness on a tape that starts today is worse
#: than a provisional verdict that says it is provisional; a FALSE FAIL in week one is worse than
#: both. Saturday and Sunday have no pooled fallback: they are UNMEASURED until measured.
MIN_SESSION_DAYS = 5

#: A quote unchanged for longer than this INSIDE the session is a staleness run worth naming.
#: Not an error: administered-spread symbols genuinely sit still. It is a number that MOVES when
#: a feed changes behaviour, which is what makes it useful.
STALE_RUN_S = 60.0

#: Verdict lines. Every one of them is a ratchet: they may be tightened, never loosened, and the
#: report carries the values it was judged at so a later reader can see which line applied.
COVERAGE_FAIL = 0.80          # below this share of the symbol's own session: FAIL
COVERAGE_DEGRADED = 0.95      # below this: DEGRADED
UNEXPLAINED_FAIL_MIN = 30     # unexplained minutes at or above this: FAIL
UNEXPLAINED_DEGRADED_MIN = 1  # ANY unexplained minute is at least DEGRADED
DUP_DEGRADED = 0.05           # >5% duplicate rows: the overlap policy costs more than it should
CROSSED_DEGRADED = 0.001      # >0.1% crossed quotes: the feed is not behaving as a feed


@dataclass
class DayVerdict:
    symbol: str
    day: str
    verdict: str
    reasons: list[str] = field(default_factory=list)
    n_ticks: int = 0
    n_segments: int = 0
    bytes: int = 0
    bytes_per_tick: float = 0.0
    sealed: bool = False
    seal_ok: bool | None = None
    post_seal_writes: int = 0
    orphans_recovered: int = 0
    corrupt_segments: int = 0
    missing_segments: int = 0
    session_basis: str = "none"
    session_obs: int = 0
    claimed_minutes: int = 0
    session_minutes: int = 0
    covered_minutes: int = 0
    coverage_frac: float | None = None
    missing_minutes: int = 0
    explained_minutes: int = 0
    unexplained_minutes: int = 0
    gap_rows: int = 0
    gap_seconds: float = 0.0
    gap_reasons: dict[str, int] = field(default_factory=dict)
    dup_rows: int = 0
    dup_rate: float = 0.0
    monotonic_breaks: int = 0
    segment_overlaps: int = 0
    crossed: int = 0
    crossed_rate: float = 0.0
    locked: int = 0
    locked_rate: float = 0.0
    stale_runs: int = 0
    longest_stale_s: float = 0.0
    longest_quote_gap_s: float = 0.0
    median_spread_pts: float | None = None
    point: float | None = None
    first_ms: int = 0
    last_ms: int = 0


@dataclass
class SessionModel:
    """What this symbol's trading day looks like, measured from its own tape, per weekday.

    NO ASSET-CLASS LIST EXISTS ANYWHERE IN THIS FILE, and that is the point. A 24x5 FX calendar
    applied to the 74 US share CFDs in this universe is the identical mistake `cost_surface` made
    on its first run -- a threshold calibrated on one asset class silently excluding another
    while the artifact read as a clean build. A 6.5-hour cash session, a 23-hour FX session, a
    metals break and a Sunday open all fall out of the same measurement with nothing to maintain.
    """

    symbol: str
    #: minutes-of-day, per weekday (Mon=0 .. Sun=6), that carried ticks on a quorum of that
    #: weekday's own observations.
    per_weekday: np.ndarray                 # shape (7, 1440), bool
    weekday_obs: np.ndarray                 # shape (7,), int -- days observed per weekday
    pooled_weekday: np.ndarray              # shape (1440,), bool -- Mon-Fri pooled
    pooled_obs: int = 0

    def mask_for(self, day: str) -> tuple[np.ndarray, str, int]:
        """(session mask, basis, observations behind it) for one calendar day.

        Basis is one of: `weekday` (this weekday's own history, the real answer), `pooled`
        (Mon-Fri pooled, PROVISIONAL -- may only ever reach DEGRADED), `none` (UNMEASURED).
        """
        wd = pd.Timestamp(day).weekday()
        n = int(self.weekday_obs[wd])
        if n >= MIN_WEEKDAY_OBS:
            return self.per_weekday[wd], "weekday", n
        if wd <= 4 and self.pooled_obs >= MIN_SESSION_DAYS:
            return self.pooled_weekday, "pooled", self.pooled_obs
        return np.zeros(1440, dtype=bool), "none", n


def observed_session(store: TapeStore, symbol: str, days: list[str],
                     quorum: float = SESSION_QUORUM) -> SessionModel:
    """Build the session model from this symbol's own recorded days."""
    counts = np.zeros((7, 1440), dtype=np.int64)
    obs = np.zeros(7, dtype=np.int64)
    pooled_counts = np.zeros(1440, dtype=np.int64)
    pooled_obs = 0
    for day in days:
        df = store.read_day(symbol, day)
        if df.empty:
            continue
        wd = pd.Timestamp(day).weekday()
        obs[wd] += 1
        day_start = int(pd.Timestamp(day, tz="UTC").timestamp() * 1000)
        minute = (np.asarray(df["time_msc"], dtype=np.int64) - day_start) // 60_000
        minute = np.unique(minute[(minute >= 0) & (minute < 1440)])
        counts[wd, minute] += 1
        if wd <= 4:
            pooled_obs += 1
            pooled_counts[minute] += 1
    per_wd = np.zeros((7, 1440), dtype=bool)
    for wd in range(7):
        if obs[wd] > 0:
            per_wd[wd] = counts[wd] >= max(1, int(np.ceil(quorum * obs[wd])))
    pooled = (pooled_counts >= max(1, int(np.ceil(quorum * pooled_obs)))
              if pooled_obs else np.zeros(1440, dtype=bool))
    return SessionModel(symbol=symbol, per_weekday=per_wd, weekday_obs=obs,
                        pooled_weekday=pooled, pooled_obs=pooled_obs)


def claim_window(store: TapeStore, symbol: str, day: str, now_ms: int) -> tuple[int, int]:
    """The part of `day` this desk actually CLAIMS to have recorded, in ms.

    Two boundaries, and both were missing from the first version of this checker, which then
    reported 1,226 "unexplained" minutes on the very day capture began.

      LEFT: the COLD_START boundary marker. Quotes before the instant this desk enrolled the
      symbol were never ours. Counting them as missing coverage bills the desk for an absence it
      never claimed, and would make the first day of every new symbol a permanent FAIL.

      RIGHT: now. Minutes that have not happened yet cannot be missing.
    """
    day_start = int(pd.Timestamp(day, tz="UTC").timestamp() * 1000)
    day_end = day_start + 86_400_000
    lo, hi = day_start, min(day_end, now_ms)
    for g in store.gaps(symbol, day):
        if g.reason == GAP_COLD_START:
            lo = max(lo, int(g.from_ms))
    return lo, max(lo, hi)


def _gap_minutes(store: TapeStore, symbol: str, day: str) -> tuple[np.ndarray, list[Any], float]:
    """Minutes of `day` that an OPEN gap row explains, plus the rows and their total seconds.

    Intervals are UNIONED, which is what makes the recorder's belt-and-braces gap writing safe:
    it records a quiet run when it starts AND again in full when it ends, and overlapping rows
    covering the same minute count once.
    """
    rows = store.gaps(symbol, day)
    resolved = {(g.from_ms, g.to_ms) for g in rows if g.reason == GAP_RESOLVED}
    day_start = int(pd.Timestamp(day, tz="UTC").timestamp() * 1000)
    mask = np.zeros(1440, dtype=bool)
    open_rows = []
    seconds = 0.0
    for g in rows:
        if g.reason in (GAP_RESOLVED, GAP_COLD_START):
            # COLD_START is a zero-length boundary marker, not a hole: it says capture BEGAN
            # here. Counting it as explained coverage would credit the desk for minutes it
            # never claimed, which is the opposite error but the same dishonesty.
            continue
        if (g.from_ms, g.to_ms) in resolved:
            continue
        open_rows.append(g)
        seconds += g.seconds
        lo = max(0, (g.from_ms - day_start) // 60_000)
        hi = min(1440, -(-(g.to_ms - day_start) // 60_000))     # ceil
        if hi > lo:
            mask[int(lo):int(hi)] = True
    return mask, open_rows, seconds


def judge_day(store: TapeStore, symbol: str, day: str, model: SessionModel,
              now_ms: int | None = None) -> DayVerdict:
    """Every claim this tape makes about one symbol-day, with the number behind it."""
    now_ms = int(datetime.now(tz=UTC).timestamp() * 1000) if now_ms is None else int(now_ms)
    session, basis, session_days = model.mask_for(day)
    v = DayVerdict(symbol=symbol, day=day, verdict=UNMEASURED, session_basis=basis,
                   session_obs=session_days)
    recon = store.reconcile(symbol, day)
    v.orphans_recovered = len(recon["orphans_recovered"])
    v.corrupt_segments = len(recon["corrupt"])
    v.missing_segments = len(recon["missing"])

    recs = store.manifest(symbol, day)
    v.n_segments = len(recs)
    v.bytes = store.day_bytes(symbol, day)
    written_rows = sum(r.rows for r in recs)
    if recs:
        v.point = recs[-1].point or None

    seal = store.seal(symbol, day)
    v.sealed = seal is not None
    if seal is not None:
        v.seal_ok = (v.corrupt_segments == 0 and v.missing_segments == 0)
        # A DAY THAT GREW AFTER IT WAS SEALED. Not fatal -- the segments are all still there and
        # all still valid -- but the seal's claim of completeness was false when it was made, and
        # a false completeness claim is exactly what the integrity report exists to surface.
        v.post_seal_writes = max(0, written_rows - seal.rows)

    gap_mask, open_gaps, gap_seconds = _gap_minutes(store, symbol, day)
    v.gap_rows = len(open_gaps)
    v.gap_seconds = round(gap_seconds, 1)
    for g in open_gaps:
        v.gap_reasons[g.reason] = v.gap_reasons.get(g.reason, 0) + 1

    df = store.read_day(symbol, day, verify=True)
    v.n_ticks = len(df)
    v.dup_rows = max(0, written_rows - v.n_ticks)
    v.dup_rate = round(v.dup_rows / written_rows, 6) if written_rows else 0.0
    v.bytes_per_tick = round(v.bytes / v.n_ticks, 3) if v.n_ticks else 0.0

    if v.n_ticks == 0:
        v.reasons.append("no ticks on disk for this day")
        if v.corrupt_segments or v.missing_segments:
            v.verdict = FAIL
            v.reasons.append(f"{v.corrupt_segments} corrupt, {v.missing_segments} missing "
                             f"segment(s) -- the day is not readable")
        return v

    # -- ORDERING. Inside a segment, an out-of-order tick is the BROKER delivering out of order,
    # which is a real property of the feed. Across segments, overlap is this recorder's own
    # deliberate policy and counting it as a defect would flag correct behaviour.
    breaks = 0
    overlaps = 0
    prev_last = None
    d = store.day_dir(symbol, day)
    for r in recs:
        p = d / r.filename
        if not p.exists():
            continue
        if prev_last is not None and r.first_ms <= prev_last:
            overlaps += 1
        prev_last = max(prev_last or r.last_ms, r.last_ms)
        try:
            from recorders.tape_store import decode_segment
            seg = decode_segment(p)
        except (OSError, ValueError):
            continue
        t = np.asarray(seg["time_msc"], dtype=np.int64)
        breaks += int(np.count_nonzero(np.diff(t) < 0))
    v.monotonic_breaks = breaks
    v.segment_overlaps = overlaps

    tms = np.asarray(df["time_msc"], dtype=np.int64)
    bid = np.asarray(df["bid"], dtype=np.float64)
    ask = np.asarray(df["ask"], dtype=np.float64)
    v.first_ms, v.last_ms = int(tms[0]), int(tms[-1])

    quoted = (bid > 0) & (ask > 0)
    v.crossed = int(np.count_nonzero(quoted & (bid > ask)))
    v.locked = int(np.count_nonzero(quoted & (bid == ask)))
    n_q = int(np.count_nonzero(quoted)) or 1
    v.crossed_rate = round(v.crossed / n_q, 6)
    v.locked_rate = round(v.locked / n_q, 6)
    if v.point and v.point > 0 and n_q:
        v.median_spread_pts = round(float(np.median((ask - bid)[quoted]) / v.point), 2)

    # -- STALENESS. A run of ticks with an unchanged two-sided quote. Measured in SECONDS, not
    # ticks: a hundred repeats in one second is a busy feed, one repeat over ten minutes is not.
    changed = np.ones(tms.size, dtype=bool)
    if tms.size > 1:
        changed[1:] = (bid[1:] != bid[:-1]) | (ask[1:] != ask[:-1])
    run_id = np.cumsum(changed)
    starts = tms[np.flatnonzero(changed)]
    ends = np.append(starts[1:], tms[-1])
    run_s = (ends - starts) / 1000.0
    v.stale_runs = int(np.count_nonzero(run_s >= STALE_RUN_S))
    v.longest_stale_s = round(float(run_s.max()) if run_s.size else 0.0, 1)
    del run_id

    # -- COVERAGE, against the symbol's own session, over the window this desk actually claims.
    if not session.any():
        v.verdict = UNMEASURED
        v.reasons.append(
            f"session for {pd.Timestamp(day).day_name()} not establishable: {session_days} "
            f"observation(s) of this weekday and {model.pooled_obs} pooled weekday(s); need "
            f"{MIN_WEEKDAY_OBS} of the weekday or {MIN_SESSION_DAYS} pooled. Coverage is "
            f"UNMEASURED rather than assumed 24h (L1.28a)")
        return v

    day_start = int(pd.Timestamp(day, tz="UTC").timestamp() * 1000)
    lo_ms, hi_ms = claim_window(store, symbol, day, now_ms)
    claimed = np.zeros(1440, dtype=bool)
    lo_min = max(0, int((lo_ms - day_start) // 60_000))
    hi_min = min(1440, int(-(-(hi_ms - day_start) // 60_000)))
    if hi_min > lo_min:
        claimed[lo_min:hi_min] = True
    v.claimed_minutes = int(np.count_nonzero(claimed))

    minute = ((tms - day_start) // 60_000)
    minute = minute[(minute >= 0) & (minute < 1440)]
    have = np.zeros(1440, dtype=bool)
    have[np.unique(minute)] = True
    session = session & claimed
    v.session_minutes = int(np.count_nonzero(session))
    v.covered_minutes = int(np.count_nonzero(session & have))
    v.coverage_frac = round(v.covered_minutes / v.session_minutes, 4) if v.session_minutes else None
    missing = session & ~have
    v.missing_minutes = int(np.count_nonzero(missing))
    v.explained_minutes = int(np.count_nonzero(missing & gap_mask))
    v.unexplained_minutes = int(np.count_nonzero(missing & ~gap_mask))

    v.verdict, v.reasons = _verdict(v)
    return v


def _verdict(v: DayVerdict) -> tuple[str, list[str]]:
    """Turn the numbers into a verdict, naming the line each one was judged at."""
    reasons: list[str] = []
    worst = OK
    if v.corrupt_segments or v.missing_segments:
        worst = FAIL
        reasons.append(f"{v.corrupt_segments} corrupt and {v.missing_segments} missing "
                       f"segment(s): part of this day cannot be read back")
    if v.unexplained_minutes >= UNEXPLAINED_FAIL_MIN:
        worst = FAIL
        reasons.append(f"{v.unexplained_minutes} session minutes are absent with NO gap row "
                       f"explaining them (fail at {UNEXPLAINED_FAIL_MIN}) -- a feature built on "
                       f"this day would read the hole as a calm market")
    elif v.unexplained_minutes >= UNEXPLAINED_DEGRADED_MIN:
        worst = DEGRADED if worst == OK else worst
        reasons.append(f"{v.unexplained_minutes} session minute(s) absent with no gap row")
    if v.coverage_frac is not None:
        if v.coverage_frac < COVERAGE_FAIL:
            worst = FAIL
            reasons.append(f"coverage {v.coverage_frac:.1%} of this symbol's own session "
                           f"(fail below {COVERAGE_FAIL:.0%})")
        elif v.coverage_frac < COVERAGE_DEGRADED:
            worst = DEGRADED if worst == OK else worst
            reasons.append(f"coverage {v.coverage_frac:.1%} (degraded below "
                           f"{COVERAGE_DEGRADED:.0%})")
    if v.dup_rate > DUP_DEGRADED:
        worst = DEGRADED if worst == OK else worst
        reasons.append(f"duplicate rows {v.dup_rate:.1%} above {DUP_DEGRADED:.0%}: the overlap "
                       f"re-pull is costing more than it needs to")
    if v.crossed_rate > CROSSED_DEGRADED:
        worst = DEGRADED if worst == OK else worst
        reasons.append(f"crossed quotes {v.crossed_rate:.3%} above {CROSSED_DEGRADED:.1%}")
    if v.post_seal_writes:
        worst = DEGRADED if worst == OK else worst
        reasons.append(f"{v.post_seal_writes} tick(s) arrived AFTER this day was sealed: the "
                       f"completeness claim was premature")
    if v.monotonic_breaks:
        reasons.append(f"{v.monotonic_breaks} out-of-order tick(s) inside a segment (the broker's "
                       f"own delivery order; recorded, not corrected)")
    if v.orphans_recovered:
        reasons.append(f"{v.orphans_recovered} segment(s) re-registered from their own metadata "
                       f"after an interrupted write -- recovered, no data lost")
    # A PROVISIONAL SESSION MAY NOT MINT A FAIL. The pooled Monday-to-Friday mask is a stand-in
    # used while this weekday builds its own history, and a stand-in that can red the gate is a
    # stand-in that will red it every Friday close. It reports, it degrades, it does not fail.
    if v.session_basis == "pooled" and worst == FAIL and not (v.corrupt_segments
                                                             or v.missing_segments):
        worst = DEGRADED
        reasons.append(f"held at DEGRADED: judged against the POOLED weekday session "
                       f"({v.session_obs} days) because this weekday has fewer than "
                       f"{MIN_WEEKDAY_OBS} observations of its own -- provisional, not a verdict "
                       f"this desk will fail a day on")
    return worst, reasons


def run(store: TapeStore, symbols: list[str] | None = None, days_back: int | None = None,
        include_unsealed: bool = True) -> dict[str, Any]:
    """Judge every symbol-day the tape holds. Returns the report document."""
    syms = symbols if symbols is not None else store.symbols()
    cutoff = ""
    if days_back:
        cutoff = (datetime.now(tz=UTC).date() - timedelta(days=int(days_back))).isoformat()
    rows: list[DayVerdict] = []
    per_symbol: dict[str, dict[str, Any]] = {}
    now_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
    for sym in syms:
        all_days = store.days(sym)
        model = observed_session(store, sym, all_days[-90:])
        judged = [d for d in all_days if (not cutoff or d >= cutoff)]
        if not include_unsealed:
            judged = [d for d in judged if store.seal(sym, d) is not None]
        sym_rows = []
        for d in judged:
            sym_rows.append(judge_day(store, sym, d, model, now_ms))
        rows.extend(sym_rows)
        ticks = sum(r.n_ticks for r in sym_rows)
        byts = sum(r.bytes for r in sym_rows)
        n_days = len([r for r in sym_rows if r.n_ticks > 0])
        per_symbol[sym] = {
            "days": len(sym_rows), "days_with_ticks": n_days, "ticks": ticks, "bytes": byts,
            # THE NUMBER THE RETENTION POLICY IS DEFENDED WITH, measured on this desk's own tape
            # rather than estimated from a compression ratio.
            "bytes_per_day": round(byts / n_days, 1) if n_days else 0.0,
            "ticks_per_day": round(ticks / n_days, 1) if n_days else 0.0,
            "bytes_per_tick": round(byts / ticks, 3) if ticks else 0.0,
            "session_minutes": (sym_rows[-1].session_minutes if sym_rows else 0),
            "weekday_observations": {str(i): int(n)
                                     for i, n in enumerate(model.weekday_obs.tolist())},
            "pooled_weekday_days": int(model.pooled_obs),
            "verdicts": _tally([r.verdict for r in sym_rows]),
        }

    recorder = _recorder_status()
    tally = _tally([r.verdict for r in rows])
    total_ticks = sum(r.n_ticks for r in rows)
    total_bytes = sum(r.bytes for r in rows)
    day_count = len({(r.symbol, r.day) for r in rows if r.n_ticks > 0})
    worst = FAIL if tally.get(FAIL) else (DEGRADED if tally.get(DEGRADED) else
                                          (OK if tally.get(OK) else UNMEASURED))
    return {
        "schema": SCHEMA,
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "tape_root": str(store.root),
        "verdict": worst,
        "thresholds": {
            "coverage_fail": COVERAGE_FAIL, "coverage_degraded": COVERAGE_DEGRADED,
            "unexplained_fail_min": UNEXPLAINED_FAIL_MIN,
            "unexplained_degraded_min": UNEXPLAINED_DEGRADED_MIN,
            "dup_degraded": DUP_DEGRADED, "crossed_degraded": CROSSED_DEGRADED,
            "session_quorum": SESSION_QUORUM, "min_session_days": MIN_SESSION_DAYS,
            "stale_run_s": STALE_RUN_S,
        },
        "totals": {
            "symbols": len(syms), "symbol_days": len(rows), "symbol_days_with_ticks": day_count,
            "ticks": total_ticks, "bytes": total_bytes,
            "bytes_per_tick": round(total_bytes / total_ticks, 3) if total_ticks else 0.0,
            "bytes_per_symbol_day": round(total_bytes / day_count, 1) if day_count else 0.0,
            "unexplained_minutes": sum(r.unexplained_minutes for r in rows),
            "explained_minutes": sum(r.explained_minutes for r in rows),
            "gap_rows": sum(r.gap_rows for r in rows),
            "corrupt_segments": sum(r.corrupt_segments for r in rows),
            "missing_segments": sum(r.missing_segments for r in rows),
            "orphans_recovered": sum(r.orphans_recovered for r in rows),
        },
        "verdicts": tally,
        "recorder": recorder,
        "by_symbol": per_symbol,
        # Worst first: the point of the report is the failures, and burying them under 250 clean
        # rows is how a report becomes decorative.
        "failures": [asdict(r) for r in rows if r.verdict == FAIL][:200],
        "degraded": [asdict(r) for r in rows if r.verdict == DEGRADED][:200],
        "days": [asdict(r) for r in rows],
    }


def _recorder_status() -> dict[str, Any]:
    """What the recorder says about itself, beside what its output actually shows.

    THE PAIRING IS THE POINT. A recorder claiming RECORDING while the tape has holes is a
    different and much worse finding than a recorder that says it is paused on a disk floor --
    in the first case something is broken that nobody has noticed, in the second the machine is
    doing exactly what it was told. Reading only the tape cannot tell them apart, and reading
    only the heartbeat is what let a converter on this desk die while everything looked healthy.
    """
    if not RECORDER_STATUS.exists():
        return {"state": "NEVER_RAN",
                "why": (f"{RECORDER_STATUS.name} is absent: the recorder has not completed a "
                        f"single cycle on this host. An empty tape here is expected, not an "
                        f"alarm about the tape -- it is an alarm about the schedule.")}
    try:
        doc = json.loads(RECORDER_STATUS.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"state": "UNREADABLE", "why": f"{type(exc).__name__}: {exc}"}
    age_s: float | None = None
    with suppress(TypeError, ValueError):
        age_s = round((datetime.now(tz=UTC)
                       - datetime.fromisoformat(str(doc.get("at")))).total_seconds(), 1)
    return {"state": doc.get("state"), "at": doc.get("at"), "age_s": age_s,
            "paused_reason": doc.get("paused_reason"),
            "symbols_enrolled": doc.get("symbols_enrolled"),
            "max_lag_s": doc.get("max_lag_s"), "median_lag_s": doc.get("median_lag_s"),
            "free_bytes": doc.get("free_bytes"), "tape_root": doc.get("tape_root")}


def _tally(values: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items()))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Prove the MT5 tick tape is what it claims to be")
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--symbols", type=str, default="")
    ap.add_argument("--days", type=int, default=None, help="only judge the last N days")
    ap.add_argument("--out", type=Path, default=REPORT)
    ap.add_argument("--sealed-only", action="store_true")
    args = ap.parse_args(argv)

    from recorders.tick_recorder import DEFAULT_TAPE_ROOT
    store = TapeStore(args.root or Path(DEFAULT_TAPE_ROOT))
    syms = [s.strip() for s in args.symbols.split(",") if s.strip()] or None
    if not store.ticks_dir.is_dir():
        # NO TAPE IS NOT A PASS. It is the loudest finding this checker can make: the desk
        # believes it is recording and there is nothing on disk.
        print(f"tick_integrity: NO TAPE AT {store.root} -- nothing has been recorded. This is a "
              f"FAILURE, not an empty success: the recorder is not running, or is writing "
              f"somewhere else (MT5_TAPE_ROOT).")
        return 2

    rep = run(store, syms, args.days, include_unsealed=not args.sealed_only)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n", "utf-8")

    t = rep["totals"]
    print(f"tick_integrity: {rep['verdict']}  {t['symbols']} symbols, "
          f"{t['symbol_days_with_ticks']} symbol-days, {t['ticks']:,} ticks, "
          f"{t['bytes']/1e6:.1f} MB  ({t['bytes_per_tick']} B/tick, "
          f"{t['bytes_per_symbol_day']/1e6:.3f} MB per symbol-day)")
    print(f"  verdicts: {rep['verdicts']}")
    print(f"  UNEXPLAINED session minutes: {t['unexplained_minutes']}  "
          f"(explained by a gap row: {t['explained_minutes']})")
    for row in rep["failures"][:10]:
        print(f"  FAIL {row['symbol']}/{row['day']}: {'; '.join(row['reasons'][:2])}")
    print(f"  -> {args.out}")
    return 2 if rep["verdict"] == FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
