"""Run the canonical sequential 10-gate gauntlet on external discovery survivors.

Reads survivors from external backtest, builds daily R matrix,
rejects failed economic priors at gate 1, then computes program-level PBO + SPA and the
remaining gates for candidates that can still survive. A gate-1 reject is a measured verdict,
not an untested disappearance; doing hours of downstream work after a terminal gate failure is
compute theatre and prevents fresh candidates from reaching the same machinery.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

# DERIVED, NEVER HARDCODED (LAWS anti-hardcode; fixed 2026-08-26). This was the literal string
# "/home/quant/quant-platform" -- a Linux path that does not exist on the Windows desk box, so
# `sys.path.insert(str(BASE))` added nothing and every run there died on
# `ModuleNotFoundError: libs.validation` before judging a single cell. The gauntlet has to run on
# the desk box because the 4GB research box OOM-kills a full sweep, so a hardcoded path for one
# machine meant the gate could not run on the only machine with the memory to run it.
BASE = Path(__file__).resolve().parents[3]
UNI = BASE / "desks" / "mt5" / "data" / "universe"
REPORTS = BASE / "desks" / "mt5" / "reports"
DATA = BASE / "desks" / "mt5" / "data"
HYP = DATA / "hypotheses"

sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "desks" / "mt5"))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402
from mt5desk.universe_registry import TIMEFRAME_MINUTES as _TF_MINUTES  # noqa: E402
from research.frontier_identity import cell_id, economic_prior  # noqa: E402
from research.survivor_publication import (  # noqa: E402
    unrunnable_reason as _certificate_refusal,
)

from libs.data.pit import is_stamped  # noqa: E402
from libs.validation.cpcv import CPCV  # noqa: E402
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio  # noqa: E402
from libs.validation.pbo import probability_backtest_overfitting  # noqa: E402
from libs.validation.reality_check import hansen_spa  # noqa: E402
from libs.validation.revalidation import WalkForwardEngine, WalkForwardStatus  # noqa: E402

TRIALS_MULTIPLIER = 7.0
DSR_THRESHOLD = 0.95
PBO_THRESHOLD = 0.5
SPA_ALPHA = 0.05
WF_SPLITS = 4
WF_MIN_STABILITY = 0.5
COST_SCENARIO = 3.0

#: SECONDS THIS SWEEP MAY SPEND BUILDING *FRESH* CELLS. Cached cells are free and are ALWAYS all
#: loaded; only first-time computation is bounded.
#:
#: WHY A BUDGET AT ALL. A sweep that never finishes publishes nothing, and nothing is exactly
#: what this desk got: measured 2026-08-28, the last report was written at 01:13 and the sweeps
#: after it ran 5-7 hours each and died with their entire buffered log lost. At ~22 seconds per
#: uncached cell and ~3,700 uncached cells, a full cold sweep is roughly 22 hours -- longer than
#: the day after which the cache key rolls over and every cell goes cold again. That race cannot
#: be won by running longer; the sweep was structurally unable to ever complete.
#:
#: A bounded sweep always reaches its gates and always publishes. The cells it did not reach are
#: recorded as UNMEASURED with the reason, exactly as dropped cells already are (L1.28a) -- they
#: are not failures and not verdicts, they are work not yet done. Because the cache is cumulative
#: and content-addressed, every run starts where the last one stopped, so the docket converges
#: over a handful of runs and then every sweep is a pure cache hit: "Cell cache: N/N loaded, 0 to
#: compute", which is the regime that took twelve minutes.
#:
#: Forty-five minutes leaves the hourly cadence intact with room for the gates themselves: the
#: pure-cache regime measured twelve minutes for the gates, so 2700s of building plus the gates
#: fits inside the hour with margin. The previous twenty minutes was sized alongside the 8GB
#: memory floor below and, with the docket at 23,465 and the sweep reaching 42 cells a pass
#: (measured 2026-09-08), would have needed 558 hourly passes -- 23 days -- to judge what the
#: miners had already produced. Throughput, not supply, was binding, and this was the throttle.
FRESH_BUILD_BUDGET_SEC = float(os.environ.get("GAUNTLET_FRESH_BUDGET_SEC", "2700"))

#: THE MEMORY THIS SWEEP IS ALLOWED TO HOLD, in MB. It is the SAME number the job declares at
#: admission (`job_lock.exclusive_job(need_mb=1200)`), and that is the point: a job that asks the
#: box for 1200MB and then takes 4882MB has not been admitted, it has been let in on a false
#: statement.
#:
#: MEASURED 2026-09-05 on the 8GB research box. This sweep was found holding 4882MB ten minutes
#: into a legitimate run, leaving 280MB free. `edge_search` needs 2000MB and `orthogonal_sweep`
#: 1250MB, so neither could start; their artifacts went 28 and 23 hours stale and the canon went
#: 51 hours without a sweep. Every red line on the dashboard that morning was this one process.
#:
#: THE ASYMMETRY DECIDES THE CAP, exactly as it decided the stage order above. A sweep that
#: judges HALF the docket this hour and the rest next hour costs an hour of latency on some
#: cells. A sweep that takes the whole box costs every OTHER leg its entire hour, every hour, and
#: those legs are what feed the docket in the first place -- so the greedy sweep starves its own
#: input. Deferring is cheap here and only here: the cell cache is cumulative and content-
#: addressed, so a deferred cell is computed next hour rather than recomputed.
#:
#: Raise it only with a measurement showing the box has the room, and never above what
#: `exclusive_job` was told to admit on.
#:
#: DERIVED FROM THE ADMISSION FIGURE, NOT RESTATED BESIDE IT (2026-09-06). The block above says
#: this "is the SAME number the job declares at admission", and it was not: both were the literal
#: 1200, while the sweep's measured working set is 1619MB and 1615MB across the runs on record.
#: Two copies of one number is how one of them goes stale, and this one had.
#:
#: THE COST OF THE STALE COPY WAS THROUGHPUT, EVERY HOUR. The budget makes the sweep DEFER cells
#: once its RSS passes the cap, so a cap 400MB below the true working set is reached on every run
#: -- the sweep stopped early, every time, and judged a fraction of the docket it had been given.
#: Measured off the live dashboard 2026-09-05: 8,804 judged and 2,108 unmeasured against a docket
#: of 19,632. Roughly eight thousand candidates were not reached, by a constant.
#:
#: `measured_need_mb` is the one place that knows what this job actually uses: it corrects the
#: declaration upward by the p75 of the recent peaks and never below it. Deriving from it means
#: the throttle and the admission ask cannot disagree again, and both track measurement rather
#: than a figure somebody typed. The declaration is still the FLOOR, so this can only ever rise
#: to what the job has been observed to need -- never to what it would like.
def _measured_budget_mb() -> float:
    override = os.environ.get("GAUNTLET_MEMORY_BUDGET_MB")
    if override:
        return float(override)
    try:
        # `research.job_lock`, matching how `exclusive_job` is imported at the bottom of this
        # file -- sys.path carries `desks/mt5`, not `desks/mt5/research`. A bare `job_lock` here
        # raised ModuleNotFoundError, was swallowed by the fallback, and silently pinned the
        # budget to the declaration: the exact silent-degradation shape this file fences.
        from research.job_lock import free_mb, measured_need_mb
        need = float(measured_need_mb("external_gauntlet", DECLARED_NEED_MB)[0])
        free = free_mb()
        if free is None:
            # An unmeasurable box gets the measured need, never unlimited.
            return need
        # THE ROOM THE BOX ACTUALLY HAS, not a figure anyone typed. See HEADROOM_SHARE.
        return max(need, min(HEADROOM_SHARE * float(free), HEADROOM_CAP_MB))
    except Exception:
        # A budget that cannot be measured falls back to the declaration, never to unlimited:
        # an unmeasurable box must not have its throttle removed.
        return float(DECLARED_NEED_MB)


#: What the sweep DECLARES at admission. The floor for both the ask and the throttle above.
#:
#: 1200 IS THE MEASURED FLOOR, AND IT IS BACK (2026-09-08, the same day it was raised). It went
#: to 8192 this morning on the principal's report of an 80GB box, and 8192 would have stood the
#: sweep down at the door EVERY HOUR on the box the desk actually runs on -- every counter that
#: box has ever published says 8GB: `stall_watch` 2026-08-28 "free RAM cycled 3329 -> 448 ->
#: 3329MB" around a 3.7GB searcher; 2026-09-08 "phys 142MB free / virt 11719MB"; the page file
#: "full at 12,756MB"; and this file's own 2026-09-05 measurement of one 4882MB process "leaving
#: 280MB free". An 80GB box does not run out of memory to a 4.9GB process. (80GB is the size of
#: its DISK.) A floor sized off a claim instead of a counter is a throttle when the claim is
#: high and a permanent refusal when it is low, and this one would have been the refusal --
#: `exclusive_job` fails closed on exactly this number, rc=75, no backtests, no certificates.
#:
#: THE THROUGHPUT PROBLEM THE RAISE WAS FOR IS SOLVED BY MEASURING, NOT BY TYPING. The 1200 was
#: a self-tightening throttle only because the budget was PINNED to it: max(declared, p75 of
#: peaks), and a sweep that defers at the declaration never records a higher peak. The budget
#: now takes the room the box has at start (`_measured_budget_mb`), so on a box with the memory
#: the sweep grows into it, and on this one it stays where it was measured. The number the sweep
#: is admitted on is that same budget (`_cli_main`), so ask and throttle remain ONE number.
DECLARED_NEED_MB = 1200

#: THE SHARE OF FREE MEMORY THE SWEEP MAY TAKE, and a ceiling on it. Half: `edge_search`
#: (2000MB), `orthogonal_sweep` (1250MB) and the live terminal must still fit beside a running
#: sweep, and `exclusive_job` makes a late neighbour WAIT rather than refuse -- so a sweep that
#: takes half of what was free at its start leaves the other half for whoever is admitted next.
#: The ceiling keeps a very large box from handing one sweep more workers than it can use; on
#: an 8GB box neither figure binds and the p75-corrected need is what the sweep gets.
HEADROOM_SHARE = float(os.environ.get("GAUNTLET_HEADROOM_SHARE", "0.5"))
HEADROOM_CAP_MB = float(os.environ.get("GAUNTLET_HEADROOM_CAP_MB", "8192"))

MEMORY_BUDGET_MB = _measured_budget_mb()

#: MEMORY ONE BUILD WORKER IS BUDGETED, in MB. A worker holds its own bounded frame cache ("two
#: dozen frames", `_FRAME_CACHE`) plus ONE cell's signals, released on return -- it never
#: accumulates the way the single-process sweep did when it kept every cell's `sigs` alive
#: between the two cost arms. 768 is headroom over that shape, not a measured peak; override
#: with GAUNTLET_PER_WORKER_MB once a run has been watched.
PER_WORKER_MB = float(os.environ.get("GAUNTLET_PER_WORKER_MB", "768"))


def _worker_count() -> int:
    """How many cells to build at once. THE ARITHMETIC THAT DECIDED THIS WAS NECESSARY:

    the build is ~22s a cell and was single-process. At 45 minutes an hour that is ~123 cells an
    hour, ~3,000 a day -- against a docket of 23,465 whose cache key rolls over with the data
    day, so any cell not rebuilt inside one day goes cold again. A single process cannot converge
    that docket at all; it is not slow, it is structurally unable, exactly the shape the build
    budget's own docstring names for the cold sweep. Workers are the only exit.

    Sized from what the box actually has: one core kept free for the terminal and the other
    legs, and never more workers than the memory budget can hold at PER_WORKER_MB each -- so on
    a box where the measured budget is small this collapses to 1 and the sweep behaves exactly
    as before. GAUNTLET_WORKERS overrides both.
    """
    override = os.environ.get("GAUNTLET_WORKERS")
    if override:
        return max(1, int(float(override)))
    cores = os.cpu_count() or 1
    by_mem = int(MEMORY_BUDGET_MB // PER_WORKER_MB) if PER_WORKER_MB > 0 else 1
    return max(1, min(cores - 1, by_mem))


WORKERS = _worker_count()


def _rss_mb() -> float:
    """This process's CURRENT resident size, or 0.0 where the platform will not say.

    Zero means "cannot measure", and the caller treats it as "do not defer" -- an unmeasurable
    box must not have its gauntlet silently throttled to nothing.
    """
    try:
        for line in Path("/proc/self/status").read_text("utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024.0
    except (OSError, ValueError, IndexError):
        pass
    try:
        import psutil
        return float(psutil.Process().memory_info().rss) / 1048576.0
    except Exception:
        return 0.0



#: The per-hour spread surface, loaded once. Absent -> every cell falls back to the pooled median
#: and the basis is recorded, because a silent fallback here is a systematic undercharge on
#: exactly the families that fill in thin books.
_COST_SURFACE: dict | None = None
_SURFACE_TRIED = False


def _surface() -> dict | None:
    global _COST_SURFACE, _SURFACE_TRIED
    if not _SURFACE_TRIED:
        _SURFACE_TRIED = True
        try:
            _COST_SURFACE = json.loads((DATA / "cost_surface.json").read_text("utf-8"))
        except (OSError, ValueError):
            _COST_SURFACE = None
    return _COST_SURFACE


def _modal_fill_hour(sigs, timeframe: str = "H1") -> int | None:
    """The broker hour this cell actually fills in, or None when it cannot be established.

    A cell is charged the spread of the hour it TRADES, not the median of hours it does not. The
    signal time plus `wait_bars` is the fill bar, and `wait_bars` is counted in bars of the
    CELL'S OWN CHART: on H1 one bar is the hour this used to add, on M5 it is five minutes, and
    on D1 a whole day. Adding 1 to the hour for an M5 cell would charge it the spread of an hour
    it never trades in -- and the fill-hour surface exists precisely because that difference is
    worth thousands of points on the exotic crosses.
    """
    from mt5desk.universe_registry import timeframe_minutes
    try:
        minutes = timeframe_minutes(timeframe)
    except KeyError:
        minutes = 60
    hours: dict[int, int] = {}
    for s in sigs or ():
        ts = getattr(s, "time", None)
        if ts is None:
            continue
        h = int(getattr(ts, "hour", -1))
        if h < 0:
            continue
        offset_minutes = int(getattr(ts, "minute", 0) or 0) + \
            int(getattr(s, "wait_bars", 0) or 0) * minutes
        h = (h + offset_minutes // 60) % 24
        hours[h] = hours.get(h, 0) + 1
    if not hours:
        return None
    return max(hours.items(), key=lambda kv: kv[1])[0]


def costs_for(sym: str, meta: dict, mult: float = 1.0) -> Costs:
    """The gauntlet's cost model. `Costs.from_symbol` is the ONLY correct constructor.

    THE THREE DEFECTS THIS HAD, all live and all in the survivor-manufacturing direction, on the
    one call site that decides who gets a ten-gate certificate (measured 2026-08-27 against
    `from_symbol` on the live universe.json):

      * `0.48 if sym == "XAUUSD"` -- dollars per OUNCE written into a per-LOT field. GAP 110/144's
        original bug, fixed in `shadow_forward.per_symbol_costs` and left standing here. The
        engine divides by contract_oz=100, so gold was charged 0.0048/oz against a measured
        0.16 median: 2.43x undercharged after correction.
      * no `quote_per_account`, so the commission was charged as though every symbol were quoted
        in the account's own currency. On this EUR account: USDJPY 184.31x undercharged, CADJPY
        8.21x, EURJPY 6.19x, GBPJPY 4.12x, EURZAR 2.35x -- every symbol in the live family.
      * `commission_per_lot=3.50 * mult` scaled a CONTRACTUAL fee with market stress, which models
        nothing that happens; `from_symbol` scales the spread alone and is the reason it exists.

    `mult` keeps its meaning (spread multiplier) so no caller changes.

    THE FOURTH UNIT TRAP, and it was in this docstring (2026-09-01). The override read
    "commission stays 3.50 -- Fusion's measured ROUND TURN on this account". But
    `commission_per_lot` is charged PER SIDE: the class docstring above says the engine "adds
    the spread to TWO commissions". A round-turn figure written into a per-side field is
    therefore charged twice -- $7.00 round turn against a stated $3.50 -- which is exactly the
    shape of the three defects this same docstring already lists (dollars-per-ounce into a
    per-lot field; a currency amount divided by contract_size as though it were price).
    A measured number in the wrong unit is not more accurate than a published one.

    So the override is removed and `from_symbol`'s default stands: USD 2.25 per lot per side,
    $4.50 round turn, which is Fusion Zero's published contract and what engine.Costs already
    documents. Principal direction 2026-09-01: charge the official Fusion Zero schedule, not
    less and not more, even where the realized rate is lower.

    THIS MAKES THE GAUNTLET LESS PESSIMISTIC, on the one call site that decides who gets a
    certificate. Commission was being charged at 2x, so candidates whose edge covers the real
    Fusion cost have been rejected for a cost the account never pays. Every certificate issued
    under the old number was issued against a harder bar, so nothing already certified is
    invalidated -- the bar moves to the true one, it does not drop below it.
    """
    return Costs.from_symbol(meta.get(sym, {}), mult=mult)


def daily_series(df: pd.DataFrame, sigs: list, costs: Costs) -> pd.Series:
    res = run_backtest(df, sigs, costs)
    s = pd.Series({pd.Timestamp(t.entry_time).date(): t.r_multiple for t in res.trades},
                  dtype=float)
    return s.groupby(level=0).sum()


#: One H1 frame per SYMBOL, shared by every cell on it. Each cell used to carry its own
#: `pd.read_parquet` result, so a sweep of 900+ cells held that many copies of the same handful
#: of dataframes -- gigabytes of duplicate bars on the box that also runs the MT5 terminal.
#: Sharing is not a memory/accuracy trade: the frames are read-only inputs, every cell sees
#: byte-identical bars, and skipping hundreds of redundant parquet reads makes the sweep FASTER.
#: (Re-applied 2026-08-26 after the first attempt was lost before it reached a commit -- the
#: fence now carries `_H1_CACHE` as a marker so a second loss is caught rather than repeated.)
#: BOUNDED, because breadth broke the assumption above. The sharing cache was written when a
#: sweep touched a handful of FX majors, so an unbounded dict keyed by symbol WAS bounded in
#: practice. Class-balanced rotation across the full 251-symbol offering (2026-08-28) removed
#: that accident: the sweep now walks every class, the dict grows a frame per symbol, and on an
#: 8GB box that also runs the live MT5 terminal it consumed the machine. Measured that night --
#: 0.3GB free, the sweep alive 87 minutes at a trickle of CPU having produced nothing, because a
#: thrashing process still breathes.
#: An LRU keeps the entire benefit (cells on one symbol arrive together, so the hit rate is
#: unchanged) while making peak memory a constant instead of a function of universe size.
#:
#: BUDGETED IN BARS, NOT IN FRAMES (2026-09-05, when the docket gained the M1..D1 ladder). Two
#: caches with two hand-set frame counts -- `_H1_MAX = 24`, `_M5_MAX = 3` -- encoded the same
#: guess twice, and neither survives seven charts: a frame count is a memory budget only while
#: every frame is the same size, and an M1 frame holds SIXTY bars per H1 bar. Twenty-four M1
#: frames would be ~1.4 GB against a 1,200 MB cap this sweep already defers cells rather than
#: exceed. So there is one cache, keyed by (symbol, CHART), bounded by the rows it holds:
#:
#:     24 frames x ~54,000 hourly rows (measured on this tree: EURUSD_H1 = 53,899)
#:                                                            = ~1,300,000 rows
#:
#: which is exactly the residency `_H1_MAX = 24` bought, so the hourly docket sees no change at
#: all. The most-recently-used frame is never evicted for exceeding the budget on its own: on a
#: fine chart one frame can, and evicting it would re-read the parquet for the very next cell on
#: the same symbol -- an under-sized cache here is silent, it only ever looks like a slow box.
FRAME_CACHE_ROWS = 1_300_000
_FRAME_CACHE: OrderedDict[tuple[str, str], object] = OrderedDict()

#: Families PINNED to one chart whatever a candidate's params say. `lvc_asia_london` reproduces a
#: public EA on native M5 bars with defaults pinned to a named blob, so a params `timeframe` must
#: not be able to move it -- that would be a different strategy under the same certificate.
_PINNED_TIMEFRAME = {"lvc_asia_london": "M5"}


def timeframe_of(params: dict | None, family: str = "") -> str:
    """The chart a cell runs on: its family's pin, else its params, else H1.

    H1 BY ABSENCE is the desk-wide spelling (`research/frontier_identity`): every cell, cache
    entry, certificate and clock written before the ladder is an H1 one, and naming H1 explicitly
    would rename all of them at once.
    """
    if family in _PINNED_TIMEFRAME:
        return _PINNED_TIMEFRAME[family]
    return str((params or {}).get("timeframe") or "H1").upper()


def _frame_rows(frame) -> int:
    try:
        return len(frame)
    except TypeError:
        return 0


def _bars_for(sym: str, timeframe: str = "H1"):
    """`<SYM>_<TF>.parquet` normalised to ITS OWN bar clock, or None when the chart is absent."""
    key = (str(sym), str(timeframe).upper())
    if key in _FRAME_CACHE:
        _FRAME_CACHE.move_to_end(key)
        return _FRAME_CACHE[key]
    pq = UNI / f"{key[0]}_{key[1]}.parquet"
    if not pq.exists():
        return None
    # `families._h1` no longer FORCES an hourly clock: it normalises a frame that already is a
    # chart and hands it back on that chart (it used to resample an M15 parquet of 100,000 bars
    # into 25,001 H1 bars, silently). Same call, byte-identical H1 result, M5 stays M5.
    frame = families._h1(pd.read_parquet(pq))
    if not isinstance(frame.index, pd.DatetimeIndex) or len(frame) == 0:
        return None
    _FRAME_CACHE[key] = frame
    # COUNTED, NOT TRACKED. A running total beside the dict it describes is a second record of one
    # fact: a caller that clears the cache without resetting the total leaves it evicting to a
    # single entry forever, which presents as a slow box and nothing else. Two dozen frames.
    while len(_FRAME_CACHE) > 1 and sum(
            _frame_rows(f) for f in _FRAME_CACHE.values()) > FRAME_CACHE_ROWS:
        _FRAME_CACHE.popitem(last=False)
    return frame


def _h1_for(sym: str):
    """The symbol's HOURLY bars. Kept by name: callers outside this module ask for H1 by name."""
    return _bars_for(sym, "H1")


def _frame_for(sym: str, family: str, params: dict | None = None):
    """Load the cell's authorized clock; never silently resample an M5 hypothesis to H1."""
    return _bars_for(sym, timeframe_of(params, family))


def build_cell(sym: str, family: str, params: dict, meta: dict,
               h1_override: pd.DataFrame | None = None):
    """Build a Cell from external survivor spec.

    `h1_override` lets a caller supply bars it has already vetted instead of whatever parquet
    happens to be on disk. `external_shadow` needs exactly that: it fetches with
    `prefer_promotion_authority=True`, so its forward clock must run on the source that CARRIES
    that authority -- rebuilding from disk would run the clock on a different tape than the one
    the caller checked, and nothing downstream could tell.

    This parameter was added on 2026-08-26 (6098dcfd) and dropped again by the cache refactor
    that introduced `_frame_for`, which broke `external_shadow` with a TypeError. Because that
    organ is scheduled by NOTHING, the break was silent and the entire `overnight_gap_decay`
    family -- the desk's only certificates outside session_range_breakout, against a
    largest_family_share of 0.87 -- never started a forward clock at all.
    """
    timeframe = timeframe_of(params, family)
    if h1_override is not None:
        # NEVER silently resample: `_frame_for` exists to keep an M5-native hypothesis off an H1
        # clock, and an override must not become the hole in that rule. A caller handing H1 bars
        # for a cell hunted on another chart is a wiring error, and returning None reports it as
        # one. The check used to name `lvc_asia_london` alone because that was the only non-H1
        # cell that existed; it is now the rule for every chart on the ladder, asked of the
        # OVERRIDE ITSELF rather than of a family list, so a caller cannot open the hole by
        # inventing a new family.
        # `.get`, NOT `[...]`: a candidate can carry any string in `timeframe` (a miner spelling
        # it "1h", a hand-edited row), and a KeyError raised HERE is outside every try in this
        # function -- it would take the whole hourly sweep down over one malformed row. An
        # unknown chart cannot be matched, so the override is refused and the cell is
        # unbuildable, which is what it is.
        want = _TF_MINUTES.get(timeframe)
        if timeframe != "H1" and families.bar_minutes(h1_override) != want:
            return None
        h1 = families._h1(h1_override)
    else:
        h1 = _frame_for(sym, family, params)
    if h1 is None:
        return None
    # THE GAUNTLET MUST REACH EVERY FAMILY, not just the breakout module. Looking only in
    # `families` meant the 14 orthogonal generators were unreachable from the one door that grants
    # certificates -- so a carry or positioning edge could be written, tested by hand, and still
    # never certify. That is the same defect as having no generator at all, one layer further in.
    fn = getattr(families, f"family_{family}", None)
    if fn is None:
        try:
            from mt5desk import families_orthogonal as fo
            fn = fo.ORTHOGONAL_FAMILIES.get(family)
        except ImportError:
            fn = None
    if fn is None:
        return None
    # Reconstruct runtime-only data from the serializable candidate identity. Previously the
    # orthogonal sweep persisted `{}` for every peer/tape/macro/COT family, and discovered
    # cross-asset features were rebuilt without `extra`; both paths therefore produced zero
    # signals after apparently successful discovery. One producer -> one exact executable.
    call_params = dict(params or {})
    try:
        from research import orthogonal_sweep as inputs

        if family == "carry":
            call_params.pop("input_symbol", None)
            call_params["symbol"] = sym
        elif family in {"relative_value", "correlation_regime"}:
            peer_symbol = call_params.pop("peer_symbol", None)
            call_params["peer"] = (inputs._bars(str(peer_symbol), timeframe)
                                   if peer_symbol else None)
        # `pca_residual` TAKES THE SAME `factors` ARGUMENT and was absent from this branch, so
        # every one of its cells rebuilt here with factors=None and hit its own four-factor
        # refusal -- the identical defect `family_inputs` records having fixed on ITS side of the
        # same mapping ("301 cells failed to build with 'parquet missing or build failed', a
        # message that names the wrong cause"). Two implementations of one rule, and only one of
        # them was repaired.
        elif family in {"cross_asset_residual", "pca_residual"}:
            factor_symbols = call_params.pop("factor_symbols", [])
            call_params["factors"] = [d for d in (inputs._bars(str(s), timeframe)
                                                  for s in factor_symbols) if d is not None]
        elif family in {"liquidity_regime", "orderflow_imbalance"}:
            call_params.pop("input_source", None)
            spread, flow = inputs._tape_series(sym, h1.index, timeframe)
            call_params["spread_series" if family == "liquidity_regime" else "flow"] = (
                spread if family == "liquidity_regime" else flow
            )
        elif family == "macro_conditional":
            call_params.pop("input_source", None)
            call_params["macro"] = inputs._macro_series(h1.index)
        elif family == "cot_positioning":
            call_params.pop("input_source", None)
            call_params["cot"] = inputs._cot_frame(sym)
        elif family == "event_reaction":
            call_params.pop("input_source", None)
            call_params["events"] = inputs._event_index()
        elif family == "discovered":
            # Price-native discoveries need no external feature universe. Loading all peers for
            # every dd/hour/ru cell caused OOM without changing the selected signal.
            feature = str(call_params.get("feature") or "")
            if "ext_" in feature:
                from research.edge_search import resolve_inputs

                # THE EXTERNAL UNIVERSE IS HOURLY, AND SAYING SO IS THE HONEST OPTION.
                # `edge_search._close` reads `<SYM>_H1.parquet` for every peer it builds a
                # primitive from, so listing the cell's own chart here would name a set of
                # symbols and then quietly load their H1 closes anyway. The primitives are
                # reindexed causally onto this cell's finer index by `_match_clock`, so a
                # sub-hourly `discovered` cell is conditioned on an HOURLY external series --
                # true, coarser than the cell, and now written down instead of implied. Wiring
                # edge_search to the ladder is its own change; nothing here pretends it is done.
                # EVERY SYMBOL IN THE STORE, WHATEVER TIMEFRAME IT IS HELD AT. The glob was
                # `*_H1.parquet`, so a symbol the desk holds only at M5 or M15 was not merely
                # loaded at the wrong resolution -- it was not offered as a peer AT ALL, and no
                # cross-instrument primitive could ever reference it. With the store moving to
                # the full M1..D1 ladder that would have silently excluded most of it.
                #
                # The resolution caveat below still stands and is still the honest thing to say:
                # `edge_search._close` reads the H1 chart for whichever peers it is given.
                all_symbols = sorted({p.stem.rpartition("_")[0] or p.stem
                                      for p in UNI.glob("*.parquet")})
                call_params["extra"] = resolve_inputs(sym, h1.index, all_symbols)
    except Exception as exc:
        print(f"  INPUT-FAIL {sym}.{family}: {type(exc).__name__}: {exc}")
        return None

    # `timeframe` NAMES THE CHART TO LOAD, it is not a family argument -- the same rule
    # `family_inputs.strip_identity_keys` applies to `peer_symbol` and `factor_symbols`. Leaving
    # it in raises TypeError on every family, which the fallback below would then mistake for
    # "this family takes no side" and retry, and the second failure returns None: an entire
    # chart's worth of cells would read as unbuildable.
    call_params.pop("timeframe", None)
    side = 1  # both sides tested externally; use LONG default
    try:
        sigs = fn(h1, side=side, **call_params)
    except TypeError:
        try:
            sigs = fn(h1, **call_params)
        except Exception:
            return None
    # CHARGE THE HOUR THIS CELL FILLS IN. `universe.json` carries ONE median spread per symbol,
    # collapsed at ingest, so every gate has been dividing by a number that averages away the hour
    # structure -- and the families that fill in thin books are exactly the ones that lose by it.
    # Measured 2026-08-29: `overnight_gap_decay` fills at broker hour 01 (signal on the day's first
    # bar, wait_bars=1), where EURZAR spreads measured 1,918 pts against the 310 pooled median. A
    # 3x "stress" on the pooled number is still cheaper than the real fill.
    # The surface is OPTIONAL: without it the pooled median still applies and the basis is
    # recorded, so an undercharge stays visible instead of becoming the silent default.
    hour = _modal_fill_hour(sigs, timeframe)
    surf = _surface()
    spread_at_hour = None
    cost_basis = "pooled_median_spread"
    if surf is not None and hour is not None:
        try:
            from research.cost_surface import spread_pts as _sp

            spread_at_hour = _sp(surf, sym, hour)
        except Exception:
            spread_at_hour = None
        if spread_at_hour is not None:
            cost_basis = f"fill_hour_{hour:02d}_spread"
    # `meta.get(sym, {})`, NOT `meta`. THE WHOLE UNIVERSE DICT WAS BEING PASSED HERE and
    # `from_symbol` reads `contract_size`, `tick_size`, `tick_value` and `median_spread_pts` off
    # the mapping it is given -- a 251-symbol registry has none of those at the top level, so
    # every one fell back to its default. Measured 2026-09-02: with the surface present (it is),
    # EVERY cell priced through this branch got tick_size 0 -> spread max(0, 0.05) = 0.05,
    # contract_size 1e5 and quote_per_account 1.0 -- gold's default contract on a NOK cross, no
    # currency conversion, and essentially no spread, for every symbol.
    #
    # The direction is the worst one. This branch exists to charge the HIGHER fill-hour spread
    # (`from_symbol`'s own docstring: EURZAR 310 pooled against 1,918 on its fill bars, and
    # "both sleeves -- certified, and on live forward clocks -- go from +0.25R to NEGATIVE").
    # The bug made it charge almost NOTHING instead, so the surface that was wired to make these
    # sleeves honest was making them free. `overnight_gap_decay` on the exotic crosses replays at
    # +0.55R per trading DAY under it, which is what sent the allocator's free optimum to 69,783%
    # a year and tripped its plausibility fence.
    #
    # This is the same shape as the three defects `costs_for` lists above -- a value handed to a
    # constructor in the wrong shape, defaulting quietly, in the survivor-manufacturing
    # direction, on the one call site that decides who gets a certificate.
    costs = (Costs.from_symbol(meta.get(sym, {}), spread_pts=spread_at_hour)
             if spread_at_hour is not None else costs_for(sym, meta))
    # `timeframe` ON THE CELL, not only inside params. `cell_id` reads it from either, and a
    # caller that builds a cell without params (the recertification audit rebuilds from
    # `authorized_runs`) would otherwise lose the chart between here and its own verdict lookup.
    return {"sym": sym, "family": family, "params": params, "timeframe": timeframe,
            "df": h1, "sigs": sigs,
            "costs": costs, "_cost_basis": cost_basis, "_fill_hour": hour}


def canonical_symbol(sym: str, meta: dict) -> str:
    """The registry's own spelling of `sym`, or `sym` unchanged when it knows no such symbol.

    MEASURED 2026-09-03: 95 cells were refused as UNTRADEABLE for their CASING. `broker_swaps`
    reads Fusion's symbol table and emits `ACCENTURE`; the registry -- and every parquet on disk
    -- spells it `Accenture`. The symbol is quoted, the bars exist, and the cell was thrown away
    at gate 0 with the message "absent from the universe registry", which is exactly the kind of
    true-sounding, wrong finding that makes a docket smaller for no reason.
    """
    if sym in meta:
        return sym
    folded = {str(k).upper(): str(k) for k in meta}
    return folded.get(sym.upper(), sym)


def symbol_is_tradeable(sym: str, meta: dict) -> tuple[bool, str]:
    """Can this desk ever place an order on `sym`, and hold bars to run a forward clock on it?

    A SYMBOL THE DESK CANNOT TRADE CANNOT PRODUCE A SURVIVOR (L1.49 -- a gate that cannot be
    cashed is not a survivor). Measured 2026-09-02: eight certificates -- six on `AFG`, two on
    `AFL` -- had passed all ten gates on symbols absent from `universe.json` AND with no
    `<sym>_H1.parquet` on the box. They can never enrol a forward clock, so the ten gates were
    spent producing rows that look exactly like tradeable survivors in every artifact that counts
    them, and the desk's certificate count was inflated by things it can never own.

    BOTH CONDITIONS ARE REQUIRED and they answer different questions: registry membership is
    "will the broker quote it", parquet presence is "can the clock replay it". Either missing and
    the cell is UNTRADEABLE, named as such rather than failed -- it is not a bad edge, it is an
    edge on an instrument this desk does not have.
    """
    sym = canonical_symbol(sym, meta)
    if sym not in meta:
        return False, f"symbol {sym!r} is absent from the universe registry"
    if not (UNI / f"{sym}_H1.parquet").exists():
        return False, f"symbol {sym!r} has no {sym}_H1.parquet; no clock can replay it"
    row = meta.get(sym)
    if isinstance(row, dict) and row.get("tradeable") is False:
        # CLOSE_ONLY is not tradeable. The broker will accept an exit and refuse an entry, so a
        # certificate here could never open the position it was certified on. Absent flag =
        # permitted; a registry that predates the field must not refuse the whole universe.
        return False, (f"symbol {sym!r} is CLOSE_ONLY on this account "
                       f"(trade_mode {row.get('trade_mode')}); no new position can be opened")
    return True, ""


def certificate_retirement_reason(sym: str, meta: dict) -> str | None:
    """Retirement needs venue evidence, not absence of this host's parquet cache.

    New research still uses symbol_is_tradeable unchanged. Missing bars block execution
    and testing; they do not invalidate previously measured statistical evidence.
    Unknown registry membership is likewise not proof of permanent delisting.
    """
    sym = canonical_symbol(sym, meta)
    row = meta.get(sym)
    if isinstance(row, dict) and row.get("tradeable") is False:
        return f"symbol {sym!r} explicitly disallows new trades (trade_mode {row.get('trade_mode')})"
    return None


def partition_at_economic_prior(specs: list[dict],
                                meta: dict | None = None) -> tuple[list[dict], list[dict]]:
    """Apply gate 1 before constructing signals and return eligible specs plus exact rejects.

    TRADEABILITY IS CHECKED FIRST, before the mechanism. A cell on a symbol the desk does not
    have is not a weak hypothesis to be judged -- there is nothing to judge it with, and running
    the other nine gates on it spends the sweep's budget manufacturing uncashable certificates.
    `meta` is optional so no existing caller breaks; without it only the mechanism limb runs and
    the artifact says which limbs were applied.
    """
    eligible: list[dict] = []
    rejected: list[dict] = []
    for spec in specs:
        if meta is not None:
            # NORMALISE BEFORE JUDGING, and keep the canonical spelling on the spec: everything
            # downstream (_h1_for, the cache key, the certificate, the forward clock) keys on
            # this string, so a cell admitted under the wrong casing would fail later instead.
            canon = canonical_symbol(str(spec.get("sym") or ""), meta)
            if canon != spec.get("sym"):
                spec["sym"] = canon
            ok, why = symbol_is_tradeable(canon, meta)
            if ok:
                # AND THE CELL'S OWN CHART HAS TO EXIST. Registry membership says the broker
                # quotes it and the H1 parquet says a clock can replay it; neither says this
                # desk holds the M5 bars an M5 cell was hunted on. Without this limb such a cell
                # spends the other nine gates and then fails to build with "parquet missing" --
                # a message about the wrong file, at the wrong stage, after the compute is spent.
                _tf = timeframe_of(spec.get("params"), str(spec.get("family") or ""))
                if _tf != "H1" and not (UNI / f"{canon}_{_tf}.parquet").exists():
                    ok, why = False, (f"symbol {canon!r} has no {canon}_{_tf}.parquet; the chart "
                                      f"this cell was hunted on is not on this box")
            if not ok:
                rejected.append({
                    "cell": cell_id(spec),
                    "sym": spec["sym"],
                    "family": spec["family"],
                    "days": 0,
                    "passed": False,
                    "terminal_gate": "symbol_eligibility",
                    "stages": {"symbol_eligibility": {"passed": False, "message": why}},
                    "downstream_status": "NOT_RUN_UNTRADEABLE_SYMBOL",
                })
                continue
        stage = economic_prior(spec)
        if stage["passed"]:
            eligible.append(spec)
            continue
        rejected.append({
            "cell": cell_id(spec),
            "sym": spec["sym"],
            "family": spec["family"],
            "days": 0,
            "passed": False,
            "terminal_gate": "economic_prior",
            "stages": {"economic_prior": stage},
            "downstream_status": "NOT_RUN_TERMINAL_GATE_1_REJECT",
        })
    return eligible, rejected




# ------------------------------------------------------------------ hourly-sweep series cache
#: The sweep is HOURLY but a cell's daily series can only change when a trading DAY completes.
#: Recomputing 3,000+ signal replays and backtests every hour therefore buys nothing 23 runs out
#: of 24 -- measured: a full docket sweep took the better part of an hour, all of it recomputing
#: byte-identical series. Each cell's 1x and 3x-cost daily series are cached keyed by
#: (cell identity, params, symbol, LAST COMPLETE DAY): a new candidate computes once, everything
#: else loads. This is pure compute caching -- same series, same matrix, same gates.
#:
#: WHY EVERY SERIES ENDS AT THE LAST COMPLETE DAY (fresh and cached alike). The gate matrix
#: aligns columns BY LENGTH from the end, not by date-join, so mixing a series computed at 01:00
#: with one computed at 14:00 would silently compare yesterday's row of one cell against today's
#: partial row of another -- cross-sectional PBO/SPA on misaligned dates. Dropping the partial
#: day makes every column end on the same complete day regardless of computation hour; a partial
#: day was never a day's return to begin with.
CACHE_DIR = REPORTS / "gauntlet_cache"


#: When each symbol's cells were last BUILT (not merely considered). The rotation key.
BUILD_CURSOR = REPORTS.parent / "data" / "hypotheses" / "gauntlet_build_cursor.json"


def _build_cursor() -> dict[str, str]:
    """symbol -> ISO time its cells were last built. Missing reads as "never", which sorts first.

    An unreadable cursor is treated as EMPTY, which puts every symbol at the front rather than
    at the back: the failure mode of losing this file is one wasted rotation, never a symbol
    that stops being built (L1.28a).
    """
    try:
        doc = json.loads(BUILD_CURSOR.read_text("utf-8"))
        return {str(k): str(v) for k, v in doc.items()} if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_build_cursor(cursor: dict[str, str], built: set[str]) -> None:
    """Stamp the symbols this run actually built, so the next run starts past them."""
    if not built:
        return
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    cursor.update(dict.fromkeys(built, now))
    try:
        BUILD_CURSOR.parent.mkdir(parents=True, exist_ok=True)
        BUILD_CURSOR.write_text(json.dumps(cursor, indent=1, sort_keys=True), encoding="utf-8")
    except OSError as exc:
        print(f"  build cursor NOT saved ({exc}); the next sweep repeats this rotation")


def _cache_key(sym: str, family: str, params: dict, last_day: str,
               timeframe: str | None = None) -> str:
    """The content address of one cell's daily series.

    THE CHART IS ITS OWN FIELD, not merely a member of `params` (2026-09-05). It does normally
    ride in params and so would already change this digest -- but this cache is the exact place
    where a lost timeframe becomes an UNDETECTABLE corruption rather than a bug: two cells that
    hash the same SERVE EACH OTHER'S RETURNS, and every number downstream stays internally
    consistent, so no gate, no census and no report can see it. A family pinned to a chart
    (`lvc_asia_london`) carries no `timeframe` in params at all and would collide with an H1 cell
    of the same name on exactly this path. Naming the field costs one key and removes the class.

    `timeframe=None` resolves through `timeframe_of`, so the H1 digest is byte-identical to what
    it has always been and yesterday's cache stays warm.
    """
    import hashlib
    tf = timeframe_of(params, family) if timeframe is None else str(timeframe).upper()
    payload = {"s": sym, "f": family, "p": params, "d": last_day}
    if tf != "H1":
        payload["tf"] = tf
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode()).hexdigest()


def _series_trim_partial(ds, last_day):
    """Drop the current partial day so every column ends on the same COMPLETE day.

    `last_day is None` means NO BOUNDARY IS KNOWN, and the honest response is to trim nothing.
    It used to fall through to `ds.index < None`, which does not raise for a date index -- numpy
    compares elementwise against None and returns all-False -- so the series came back EMPTY.
    Every caller that builds cells without a `_last_day` (the recertification audit) therefore
    saw zero observations on every cell and read it as "too few days to judge" (2026-08-27).
    """
    if ds is None or len(ds) == 0 or last_day is None:
        return ds
    try:
        return ds[ds.index < last_day]
    except Exception:
        return ds


def cache_load(key: str):
    f = CACHE_DIR / f"{key}.npz"
    if not f.exists():
        return None
    try:
        import numpy as _np
        z = _np.load(f, allow_pickle=False)
        idx = pd.to_datetime(z["dates"])
        return (pd.Series(z["v1"], index=idx), pd.Series(z["v3"], index=idx))
    except Exception:
        return None


_CACHE_SAVE_WARNED = [False]


def cache_save(key: str, ds1, ds3) -> None:
    """Persist one cell's series pair. A save failure is REPORTED once, never swallowed.

    The first deployment produced ZERO files on the desk box and nobody knew: every save failed
    inside a bare `except: pass`, the warm sweep ran exactly as slow as the cold one (12.2 vs
    12.4 min), and the only symptom was a missing speedup -- which reads as "the box is slow",
    not "the cache is broken". The loud path then caught the actual bug within one run: some
    families' daily series carry plain datetime.date objects, not a DatetimeIndex, and
    astype("int64") on those raises TypeError, so pd.to_datetime normalizes first.
    """
    try:
        import numpy as _np
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        common = ds1.index.intersection(ds3.index)
        # ATOMIC, because more than one process now writes this directory. A worker killed
        # mid-write must leave either the previous file or nothing -- never a torn `.npz` that a
        # later `cache_load` might read as a cell with a partial series. Written through a file
        # handle on purpose: given a PATH, `savez_compressed` appends `.npz` to anything that
        # does not already end in it, which would turn the temp name into a second cache entry.
        final = CACHE_DIR / f"{key}.npz"
        tmp = CACHE_DIR / f"{key}.{os.getpid()}.tmp"
        with open(tmp, "wb") as fh:
            _np.savez_compressed(fh,
                                 dates=pd.to_datetime(common).astype("int64").to_numpy(),
                                 v1=ds1.reindex(common).to_numpy(float),
                                 v3=ds3.reindex(common).to_numpy(float))
        os.replace(tmp, final)
    except Exception as exc:
        if not _CACHE_SAVE_WARNED[0]:
            _CACHE_SAVE_WARNED[0] = True
            print(f"  CACHE SAVE FAILING ({type(exc).__name__}: {exc}) -- sweeps will run at "
                  f"cold speed until this is fixed; reporting once, not per cell")

def _warm_one(spec: dict, meta: dict) -> dict:
    """Build ONE cell's series pair into the on-disk cache. Runs in a worker process.

    THIS IS THE FRESH PATH OF THE MAIN LOOP AND `run_gauntlet`, EXTRACTED -- `_bars_for`, the
    cell's own data-day, `build_cell`, both cost arms through `daily_series`, `cache_save` --
    and nothing else. The verdict logic is untouched: after the pool runs, the main loop finds
    every warmed key in the cache and takes the branch it has always taken for a cached cell.
    Nothing crosses the process boundary except the spec in and a status out; the frames and
    signals a cell needs stay in the worker and die with the task, which is what keeps a
    worker's memory at ONE cell rather than the sweep's whole history of them.

    A cell whose 3x arm fails is NOT saved: `run_gauntlet` handles that case itself (FAIL-3x, with
    the 1x series kept), and caching half a pair would hide it.
    """
    sym, family = str(spec.get("sym") or ""), str(spec.get("family") or "")
    params = spec.get("params") or {}
    tf = timeframe_of(params, family)
    out: dict = {"sym": sym, "family": family, "tf": tf, "status": "", "why": ""}
    try:
        frame = _bars_for(sym, tf)
        if frame is None or len(frame) == 0:
            out["status"] = "NOT_RUN_DATA_MISSING"
            return out
        last_day = frame.index[-1].normalize()
        ckey = _cache_key(sym, family, params, str(last_day.date()), tf)
        out["ckey"] = ckey
        if cache_load(ckey) is not None:
            out["status"] = "HIT"
            return out
        obj = build_cell(sym, family, params, meta)
        if not obj:
            out["status"] = "NOT_RUN_BUILD_FAILED"
            return out
        ds1 = _series_trim_partial(daily_series(obj["df"], obj["sigs"], obj["costs"]), last_day)
        try:
            ds3 = _series_trim_partial(
                daily_series(obj["df"], obj["sigs"], costs_for(sym, meta, mult=COST_SCENARIO)),
                last_day)
        except Exception as exc3:
            out["status"], out["why"] = "FAIL_3X", f"{type(exc3).__name__}: {exc3}"
            return out
        cache_save(ckey, ds1, ds3)
        out["status"] = "WARMED" if cache_load(ckey) is not None else "SAVE_FAILED"
        return out
    except Exception as exc:
        out["status"], out["why"] = "ERROR", f"{type(exc).__name__}: {exc}"
        return out


def _prewarm_cache(specs: list, meta: dict, deadline: float) -> dict:
    """Warm the cell cache for `specs` in parallel, in their given order, until `deadline`.

    THE ORDER IS THE MAIN LOOP'S ORDER, on purpose. The loop rotates longest-unbuilt symbol first
    so that deferral is self-correcting; a pool that drew from its own queue in another order
    would rebuild the head of the docket every hour and never reach the tail -- the exact
    failure the rotation exists to prevent, back by a different door. Cells are submitted in
    sequence and at most 2x WORKERS are in flight, so that when the deadline arrives the
    not-yet-started queue can actually be cancelled rather than having been handed out already.

    THE DEADLINE IS THE SAME ONE THE MAIN LOOP HONOURS. The pool spends the build budget; the
    loop that follows finds the budget spent and defers what the pool did not reach, exactly as
    it defers today. The hourly cadence is unchanged: this makes the 45 minutes worth WORKERS
    times more cells, it does not make them longer.
    """
    from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

    summary = {"workers": WORKERS, "submitted": 0, "warmed": 0, "hit": 0, "failed": 0,
               "unreached": 0, "seconds": 0.0, "failures": {}}
    t0 = time.time()
    it = iter(specs)
    pending: dict = {}
    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        def _submit_next() -> bool:
            sp = next(it, None)
            if sp is None:
                return False
            pending[pool.submit(_warm_one, sp, meta)] = sp
            summary["submitted"] += 1
            return True

        for _ in range(2 * WORKERS):
            if not _submit_next():
                break
        while pending:
            if time.time() > deadline:
                # Stop handing out work. Cells already running finish (one cell each); cells
                # not yet started are cancelled and counted as unreached -- the main loop then
                # records them DEFERRED with the budget as the reason, as it always has.
                for f in list(pending):
                    if f.cancel():
                        summary["unreached"] += 1
                        pending.pop(f)
            done, _ = wait(list(pending), timeout=5, return_when=FIRST_COMPLETED)
            for f in done:
                pending.pop(f, None)
                try:
                    r = f.result()
                except Exception as exc:
                    r = {"status": "ERROR", "why": f"{type(exc).__name__}: {exc}"}
                st = str(r.get("status") or "ERROR")
                if st == "WARMED":
                    summary["warmed"] += 1
                elif st == "HIT":
                    summary["hit"] += 1
                else:
                    summary["failed"] += 1
                    summary["failures"][st] = summary["failures"].get(st, 0) + 1
                if time.time() <= deadline:
                    _submit_next()
    summary["unreached"] += sum(1 for _ in it)
    summary["seconds"] = round(time.time() - t0, 1)
    print(f"PRE-WARM: {summary['workers']} worker(s) warmed {summary['warmed']} cell(s) in "
          f"{summary['seconds']:.0f}s ({summary['hit']} already cached, {summary['failed']} "
          f"failed, {summary['unreached']} not reached before the build budget)"
          + (f"; failures by kind {summary['failures']}" if summary["failures"] else ""))
    return summary


# ------------------------------------------------------------------ certificate annotations
#: WHAT THIS SECTION IS, AND IS NOT (2026-09-08, Tier-1 wave W1: V1, V5, V8, V13, V15, V19,
#: V21, A8). Every function below is a MEASUREMENT recorded beside a verdict, or a report of what
#: a stage WOULD have decided. None of them sets, moves or reads into a gate: the ten gates, their
#: constants and every pass/fail decision in `run_gauntlet` are byte-identical with or without
#: this section. A failure inside any annotation records UNMEASURED for that annotation and never
#: touches certification; an absent input is recorded as absent (`None`, or a status of
#: UNMEASURED with the reason), never as 0, never as a pass.

#: Seconds the certificate block may spend REBUILDING passing cells for their second-engine
#: replay and trade-level annotations. The sweep releases a cell's bars and signals the moment it
#: is judged, and a cached cell never had them, so the trade-level inputs have to be rebuilt.
#: Passing cells are single digits a sweep at ~22s each, so this is rarely reached; when it is,
#: the remaining certificates carry UNMEASURED with the budget as the reason and are still
#: written -- the hourly cadence is not spent on an annotation.
ANNOTATION_BUDGET_SEC = float(os.environ.get("GAUNTLET_ANNOTATION_BUDGET_SEC", "300"))

#: Stage 0's append-only ledger: the pre-filter module's own default file name, made absolute
#: against BASE rather than the working directory (this file's first rule, line 23).
PRE_FILTER_LEDGER = BASE / "data" / "pre_filter_ledger.jsonl"

#: Params that SHAPE a trade rather than CONDITION its entry. Every other free param a family
#: accepts is counted as an entry condition by `certificate_complexity`; the split is written on
#: the certificate so the count can be argued with rather than trusted.
TRADE_SHAPE_KEYS = frozenset({"rr", "wait_bars", "ttl_bars", "horizon", "side", "hold_bars",
                              "stop_atr", "target_atr"})

#: Exposure-matched monkey draws per certificate. `random_baseline.MIN_BASELINES` is 200; 500
#: permutations of a ~1,000-day position vector cost milliseconds.
MONKEY_BASELINES = 500


def _unmeasured(why: str, **extra: object) -> dict:
    return {"status": "UNMEASURED", "why": str(why)[:300], **extra}


def _safe(fn, what: str) -> dict:
    """Run one annotation; a failure inside it is UNMEASURED for that annotation, nothing more."""
    try:
        out = fn()
        if isinstance(out, dict):
            return out
        return _unmeasured(f"{what} returned {type(out).__name__}")
    except Exception as exc:
        return _unmeasured(f"{what}: {type(exc).__name__}: {exc}")


def _num(x: object) -> float | None:
    """A finite float, or None. `json.dumps` writes NaN as a bare `NaN` token: not JSON."""
    try:
        f = float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def gate_independence(verdicts: list[dict]) -> dict:
    """How many verdicts' gate 9 restates gate 7, and how PBO/SPA are shared (V1). Measurement.

    gate_spec.yaml's lockbox block says in its own comment that gate 9 is not independent of
    gate 7; this COUNTS it per sweep instead of asserting it, over the judged verdicts only (an
    UNMEASURED verdict has no gates to compare). PBO and SPA are computed once per matrix and
    broadcast onto every verdict (`stages["pbo"]`, `stages["reality_check_spa"]`), so the number
    of distinct values across a sweep is the measure of how per-candidate they are: 1 means every
    candidate carries the set's verdict, not its own. Nothing here changes a decision.
    """
    judged = [v for v in verdicts
              if not v.get("unmeasured") and isinstance(v.get("stages"), dict)
              and "lockbox" in v["stages"]]
    restated = 0
    pbo_vals: set = set()
    spa_vals: set = set()
    for v in judged:
        st = v["stages"]
        lb, wf = st.get("lockbox") or {}, st.get("walk_forward") or {}
        if (lb.get("lockbox_sharpe") is not None
                and lb.get("lockbox_sharpe") == wf.get("oos_sharpe")):
            restated += 1
        pbo_vals.add((st.get("pbo") or {}).get("pbo"))
        spa_vals.add((st.get("reality_check_spa") or {}).get("p_value"))
    return {
        "lockbox_restates_walk_forward": {"n": restated, "of": len(judged)},
        "pbo_spa_broadcast": {"per_matrix": True, "verdicts": len(judged),
                              "distinct_pbo_values": len(pbo_vals),
                              "distinct_spa_p_values": len(spa_vals)},
        "note": ("measurement only: gate 9 is passed on the same walk-forward OOS Sharpe as "
                 "gate 7, and PBO/SPA are one matrix-level number written onto every verdict; "
                 "no pass/fail decision is changed by recording this"),
    }


def lifetime_trial_report(families) -> dict:
    """`lifetime_trials` and per-family trials from the experiment ledger (V21), REPORTED beside
    the sealed charge and never substituted for it.

    Read from the ledger file `pf_allocator` writes hourly, through the module's own path, and
    never recomputed here: `experiment_ledger.family_trials` falls back to `lifetime(write=True)`
    when that file is unreadable, and the judge must not write another organ's artifact. An
    absent ledger is UNMEASURED with the writer named; a family the ledger does not list is
    `None`, not 0.
    """
    fams = sorted({str(f) for f in families if f})
    note = ("reported beside the sealed fixed campaign charge (`n_trials` / "
            "`trial_count_basis`); it never sets the bar")
    try:
        from libs.research import experiment_ledger as _el
        doc = json.loads(_el.OUT.read_text("utf-8"))
        if not isinstance(doc, dict):
            raise ValueError("EXPERIMENT_LEDGER.json is not a mapping")
    except Exception as exc:
        return _unmeasured(
            f"{type(exc).__name__}: EXPERIMENT_LEDGER.json unreadable; pf_allocator writes it "
            f"hourly through experiment_ledger.lifetime(write=True)",
            families=fams, lifetime_trials=None, family_trials=dict.fromkeys(fams), note=note)
    by_fam = doc.get("by_family") if isinstance(doc.get("by_family"), dict) else {}
    lt = doc.get("lifetime_trials")
    return {
        "status": "MEASURED",
        "lifetime_trials": int(lt) if isinstance(lt, int | float) else None,
        "family_trials": {f: (int(by_fam[f]) if isinstance(by_fam.get(f), int | float) else None)
                          for f in fams},
        "families_absent_from_ledger": [f for f in fams if f not in by_fam],
        "ledger_generated_utc": doc.get("generated_utc"),
        "note": note,
    }


def _daily_index(ds: pd.Series) -> pd.DatetimeIndex:
    """A series' dates as a tz-naive, day-normalised DatetimeIndex, whatever the cache or a
    family handed back (python dates, naive or aware Timestamps)."""
    idx = pd.DatetimeIndex(pd.to_datetime(list(ds.index)))
    if idx.tz is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    return idx.normalize()


def _calendar_series(ds: pd.Series) -> pd.Series:
    """Daily R on a business-day calendar spanning the series, inactive days 0.0 -- the
    'full-length per-period, 0.0 = flat' shape `pre_filter` and the baselines are written for.
    A weekend entry (FX opens Sunday evening) keeps its own day rather than being dropped."""
    idx = _daily_index(ds)
    per_day = pd.Series(ds.to_numpy(float), index=idx).groupby(level=0).sum()
    cal = pd.bdate_range(idx.min(), idx.max()).union(per_day.index)
    return per_day.reindex(cal, fill_value=0.0)


def stage0_prefilter(cid: str, ds: pd.Series | None) -> dict:
    """What `libs.research.pre_filter` WOULD decide about one cell's cached daily series (V8).

    REPORT-ONLY, and why that is the honest wiring rather than a hedge. The pre-filter judges a
    RETURN STREAM, and before a cell is built there is none: a spec is (symbol, family, params,
    mechanism) and the filter's contract rejects nothing on those. The only cells that carry a
    stream before the build loop are the ones already in the series cache -- exactly the cells
    whose expensive step is already paid, so a rejection there saves no compute and would only
    remove a verdict. So Stage 0 runs on every cached series, its verdict is recorded per cell
    and cross-tabulated against the ten gates, and NO cell leaves the docket on its say-so. The
    cross-tab is the calibration a filter must earn before it is ever allowed to reject.

    Units: the stream is daily R-multiples, not simple returns. The sign, t-statistic and
    window-concentration checks are scale-free; the cost-floor check needs cost in the stream's
    units and is skipped (`rt_cost_per_trade=None` escalates on cost by the filter's own rule).
    """
    try:
        from libs.research.pre_filter import pre_filter
        if ds is None or len(ds) == 0:
            return {"verdict": "UNJUDGED", "why": "empty series"}
        stream = _calendar_series(ds)
        out = pre_filter(stream.to_numpy(float), name=cid, rt_cost_per_trade=None, ledger=None)
        return {"verdict": str(out.get("verdict")), "reason": out.get("reason"),
                "detail": out.get("detail"), "t_insample": out.get("t_insample"),
                "n_active": int(out.get("n_active", 0)), "n_periods": int(out.get("n", 0))}
    except Exception as exc:
        return {"verdict": "UNJUDGED", "why": f"{type(exc).__name__}: {exc}"[:200]}


def stage0_new_summary() -> dict:
    return {"mode": "report-only", "rejected": 0, "escalated": 0, "why_counts": {},
            "unjudged_no_series_before_build": 0, "unjudged_error": 0,
            "cells_removed_from_docket": 0, "by_decision": {}}


def stage0_record(summary: dict, verdicts: dict[str, dict], spec: dict, tf: str,
                  ds: pd.Series | None) -> None:
    """Judge ONE cached cell at Stage 0 and count the decision. Never raises."""
    try:
        cid = cell_id({"sym": spec["sym"], "family": spec["family"],
                       "params": spec.get("params") or {}, "timeframe": tf})
        rec = stage0_prefilter(cid, ds)
        verdicts[cid] = rec
        vd = str(rec.get("verdict"))
        if vd == "REJECT":
            summary["rejected"] += 1
            reason = str(rec.get("reason"))
            summary["why_counts"][reason] = summary["why_counts"].get(reason, 0) + 1
        elif vd == "ESCALATE":
            summary["escalated"] += 1
        else:
            summary["unjudged_error"] += 1
        slot = summary["by_decision"].setdefault(f"{vd}:{rec.get('reason') or '-'}",
                                                 {"n": 0, "sample": []})
        slot["n"] += 1
        if len(slot["sample"]) < 20:
            slot["sample"].append(cid)
    except Exception as exc:
        summary["unjudged_error"] += 1
        summary.setdefault("errors", []).append(f"{type(exc).__name__}: {exc}"[:120])


def _stage0_append_ledger(summary: dict, ledger: Path) -> int:
    """This sweep's Stage 0 decisions, appended by (verdict, reason) with a bounded sample of
    cell ids. One row per cell would be ~20,000 rows an hour once the cache converges -- a ledger
    nobody could read or keep -- so the per-cell verdict rides on the verdict row in
    universal_gates_external.json and the ledger carries the counts (`n`) and samples."""
    ts = datetime.now(UTC).isoformat()
    rows = []
    for key, slot in sorted(summary.get("by_decision", {}).items()):
        vd, _, reason = key.partition(":")
        rows.append({"ts": ts, "stage": "pre-filter (zero promotion authority)",
                     "mode": "report-only", "verdict": vd,
                     "reason": None if reason == "-" else reason, "n": int(slot["n"]),
                     "sample_cells": list(slot["sample"]), "cells_removed_from_docket": 0})
    if not rows:
        return 0
    try:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, separators=(",", ":"), default=str) + "\n")
        return len(rows)
    except OSError as exc:
        print(f"  Stage 0 ledger NOT appended ({exc}); the decisions are still in the report")
        return 0


def stage0_summary(summary: dict, verdicts_by_cell: dict[str, dict], verdicts: list[dict],
                   ledger: Path | None = None) -> dict:
    """Cross-tab Stage 0's would-be verdicts against the ten gates, stamp each verdict row with
    its Stage 0 record, append the ledger, and return the `pre_filter` block for the result."""
    cross = {vd: {"gauntlet_pass": 0, "gauntlet_fail": 0, "unmeasured": 0}
             for vd in ("REJECT", "ESCALATE")}
    for v in verdicts:
        rec = verdicts_by_cell.get(str(v.get("cell")))
        if rec is None:
            continue
        v["stage0"] = {"verdict": rec.get("verdict"), "reason": rec.get("reason")}
        vd = str(rec.get("verdict"))
        if vd not in cross:
            continue
        if v.get("unmeasured"):
            cross[vd]["unmeasured"] += 1
        elif v.get("passed"):
            cross[vd]["gauntlet_pass"] += 1
        else:
            cross[vd]["gauntlet_fail"] += 1
    n_rows = _stage0_append_ledger(summary, ledger) if ledger is not None else 0
    return {
        "mode": "report-only",
        "rejected": int(summary["rejected"]),
        "escalated": int(summary["escalated"]),
        "why_counts": dict(summary["why_counts"]),
        "unjudged_no_series_before_build": int(summary["unjudged_no_series_before_build"]),
        "unjudged_error": int(summary["unjudged_error"]),
        "cells_removed_from_docket": 0,
        "agreement_with_gauntlet": cross,
        "ledger": None if ledger is None else str(ledger),
        "ledger_rows_appended": n_rows,
        "errors": list(summary.get("errors") or [])[:10],
        "note": ("Stage 0 (libs.research.pre_filter) runs in REPORT-ONLY mode. It judges a "
                 "return stream, and before a cell is built there is none, so on the fields a "
                 "spec carries it can reject nothing safely; the cells that DO carry a stream "
                 "(cached series) have already paid their build, so a rejection there would "
                 "save no compute and only remove a verdict. Every cached cell's would-be "
                 "verdict is recorded on its verdict row (`stage0`) and cross-tabulated against "
                 "the ten gates here; `rejected` counts what the filter WOULD have rejected. No "
                 "cell was removed from the docket and every pass/fail decision is the "
                 "gauntlet's own. Ledger rows are per (verdict, reason) with `n` and a sample."),
    }


def certificate_complexity(family: str, params: dict | None, ds: pd.Series | None,
                           trades: list | None = None) -> dict:
    """{n_params, n_conditions, expression_nodes, turnover_per_day} for one certificate (V13).

    No threshold. This is the measurement the fitness function's `complexity` term (node count,
    weight 0.03, search-only) and the adversary's `overfit_params` canary have never had a real
    survivor to be reconciled against. `n_conditions` is the free params outside TRADE_SHAPE_KEYS
    and the keys are listed, so the count is checkable. `expression_nodes` is derivable only when
    the params carry a grammar expression; a feature NAME is a leaf, not an expression, and is
    recorded as None with that reason. Turnover is engine trades per calendar day when the cell
    was rebuilt, else active trading days per calendar day from the daily series (which holds one
    R per day and so cannot count trades) -- and the basis says which.
    """
    try:
        from mt5desk.family_inputs import strip_identity_keys
        free = strip_identity_keys(family, dict(params or {}))
    except Exception:
        free = {k: v for k, v in dict(params or {}).items() if k != "timeframe"}
    cond_keys = sorted(k for k in free if k not in TRADE_SHAPE_KEYS)
    out: dict = {
        "status": "MEASURED", "n_params": len(free), "n_conditions": len(cond_keys),
        "condition_keys": cond_keys,
        "basis": ("free params = params minus input/chart identity keys "
                  "(family_inputs.IDENTITY_KEYS); conditions = free params outside "
                  f"TRADE_SHAPE_KEYS {sorted(TRADE_SHAPE_KEYS)}"),
    }
    expr = next((free[k] for k in ("expr", "expression", "genome", "tree")
                 if isinstance(free.get(k), list | tuple)), None)
    if expr is None:
        out["expression_nodes"] = None
        out["expression_nodes_why"] = ("no grammar expression on params (a feature name is a "
                                       "leaf, not an expression)")
    else:
        try:
            from libs.research.alpha_grammar import complexity as _nodes
            out["expression_nodes"] = int(_nodes(expr))
        except Exception as exc:
            out["expression_nodes"] = None
            out["expression_nodes_why"] = f"{type(exc).__name__}: {exc}"[:120]
    if trades:
        entries = pd.DatetimeIndex([pd.Timestamp(t.entry_time) for t in trades])
        if entries.tz is not None:
            entries = entries.tz_convert("UTC").tz_localize(None)
        span = int((entries.max().normalize() - entries.min().normalize()).days) + 1
        out["turnover_per_day"] = round(len(trades) / span, 6)
        out["turnover_basis"] = (f"{len(trades)} engine trades over {span} calendar days "
                                 f"(rebuilt cell)")
    elif ds is not None and len(ds):
        idx = _daily_index(ds)
        span = int((idx.max() - idx.min()).days) + 1
        out["turnover_per_day"] = round(len(idx.unique()) / span, 6)
        out["turnover_basis"] = (f"{len(idx.unique())} active trading days over {span} calendar "
                                 f"days (trade count unavailable: the cached series carries one "
                                 f"R per day)")
    else:
        out["turnover_per_day"] = None
        out["turnover_basis"] = "no daily series and no trades"
    return out


def _exposure_calendar(trades: list, calendar: pd.DatetimeIndex) -> tuple[np.ndarray, str]:
    """Per-day net position from engine trades (+1 long / -1 short / 0 flat, every calendar day
    a trade was open), on `calendar`."""
    pos = pd.Series(0.0, index=calendar)
    for t in trades:
        a, b = pd.Timestamp(t.entry_time), pd.Timestamp(t.exit_time)
        if a.tzinfo is not None:
            a, b = a.tz_convert("UTC").tz_localize(None), b.tz_convert("UTC").tz_localize(None)
        days = pd.date_range(a.normalize(), b.normalize()).intersection(calendar)
        pos[days] = pos[days] + float(t.side)
    return np.sign(pos.to_numpy(float)), "net side of engine trades open on each day (rebuilt cell)"


def certificate_baselines(sym: str, ds: pd.Series | None, frame: pd.DataFrame | None,
                          trades: list | None = None, *, seed: int = 0) -> dict:
    """Buy-and-hold of the cell's own symbol, and the exposure-matched monkey (V15). Recorded.

    The strategy stream is daily R on a calendar (inactive days 0); buy-and-hold is the symbol's
    daily close-to-close fractional return on the same days. Sharpe is scale-free, so the Sharpe
    comparison is legitimate; the scorecard's total-return excess is NOT (an R is not a
    fraction) and is deliberately not recorded. The monkey keeps the rule's exposure calendar and
    permutes WHEN, so the beat-rate isolates timing from being in the market.
    """
    from libs.validation.baselines import baseline_scorecard
    from libs.validation.random_baseline import monkey_test, partition_return
    if ds is None or len(ds) == 0:
        return _unmeasured("no daily series for this cell")
    if frame is None or len(frame) == 0 or "close" not in frame:
        return _unmeasured(f"no bars for {sym} in the frame cache")
    close = frame["close"].astype(float)
    if not isinstance(close.index, pd.DatetimeIndex):
        return _unmeasured("bars carry no DatetimeIndex")
    daily_close = close.resample("1D").last().dropna()
    if daily_close.index.tz is not None:
        daily_close.index = daily_close.index.tz_convert("UTC").tz_localize(None)
    daily_close.index = daily_close.index.normalize()
    bh = daily_close.pct_change().dropna()
    strat_cal = _calendar_series(ds)
    first, last = strat_cal.index.min(), strat_cal.index.max()
    span = bh[(bh.index >= first) & (bh.index <= last)]
    if len(span) < 30:
        return _unmeasured(f"only {len(span)} aligned daily bars for {sym} over the series' span")
    strat = strat_cal.reindex(span.index, fill_value=0.0)
    sc = baseline_scorecard(strat.to_numpy(float), buy_hold_returns=span.to_numpy(float))
    if trades:
        pos, pos_basis = _exposure_calendar(trades, span.index)
    else:
        pos = (strat.to_numpy(float) != 0.0).astype(float)
        pos_basis = "active-day indicator, long (build_cell passes side=1; trades unavailable)"
    mkt = span.to_numpy(float)
    mt = monkey_test(pos, mkt, rng=np.random.default_rng(seed), n_baselines=MONKEY_BASELINES)
    part = partition_return(pos, mkt)
    return {
        "status": "MEASURED", "symbol": sym, "n_days": len(span),
        "buy_and_hold": {
            "strategy_sharpe": _num(round(sc.strategy_sharpe, 4)),
            "buy_hold_sharpe": _num(round(sc.buy_hold_sharpe, 4)),
            "beats_buy_hold_sharpe": bool(sc.strategy_sharpe > sc.buy_hold_sharpe),
            "units": ("calendar-day Sharpe; strategy in daily R (0 when flat), buy-and-hold in "
                      "daily fractional close-to-close; total-return excess omitted as "
                      "incommensurable"),
        },
        "monkey": {
            "beat_rate": _num(mt.get("beat_rate")), "p_value": _num(mt.get("p_value")),
            "n_baselines": mt.get("n_baselines"), "real_statistic": _num(mt.get("real_statistic")),
            "baseline_median": _num(mt.get("baseline_median")),
            "clears_target": mt.get("clears_target"), "target": mt.get("target"),
            "reading": mt.get("reading"), "unmeasurable": mt.get("unmeasurable"),
            "positions_basis": pos_basis,
        },
        "exposure_timing": {k: _num(part.get(k)) for k in
                            ("exposure_share", "timing_share", "time_in_market")},
    }


def _rebuild_for_annotation(cell: dict, meta: dict) -> dict:
    """ONE rebuild of a passing cell, shared by every trade-level annotation, or why not.

    Same bars (`_frame_for`), same signal function and same cost model as the judged series --
    `build_cell` is the one constructor -- so the trades it yields are the ones the certificate
    was earned on, not a second opinion about them.
    """
    try:
        obj = build_cell(str(cell["sym"]), str(cell["family"]), dict(cell.get("params") or {}),
                         meta)
        if not obj:
            return {"ok": False,
                    "why": "build_cell returned no executable cell (bars or inputs missing)"}
        res = run_backtest(obj["df"], obj["sigs"], obj["costs"])
        return {"ok": True, "df": obj["df"], "sigs": obj["sigs"], "costs": obj["costs"],
                "trades": list(res.trades)}
    except Exception as exc:
        return {"ok": False, "why": f"{type(exc).__name__}: {exc}"[:200]}


def replay2_agreement(ctx: dict) -> dict:
    """Per-trade agreement between `mt5desk.engine.run_backtest` and the second engine (V5).

    `libs.validation.replay2` is written from the contract, not the engine's source; the cost it
    subtracts is the engine's own per-unit round trip in price units (engine.run_backtest:
    `per_oz_cost = costs.per_oz_roundtrip() / costs.contract_oz`). Signals that use trigger,
    bank, trail or pyramid fields are outside replay2's stated contract; they are counted so a
    gap on such a cell reads as expected rather than as a defect. Recorded, not gating.
    """
    if not ctx.get("ok"):
        return _unmeasured(f"no rebuilt cell to replay: {ctx.get('why')}")
    from libs.validation import replay2
    costs, df, sigs = ctx["costs"], ctx["df"], ctx["sigs"]
    cost_px = float(costs.per_oz_roundtrip()) / float(costs.contract_oz)
    r2 = replay2.replay(df, sigs, cost_price_units=cost_px)
    cmp = replay2.compare([t.r_multiple for t in ctx["trades"]], [t.r for t in r2])
    outside = sum(1 for s in sigs
                  if getattr(s, "trigger", None) is not None
                  or float(getattr(s, "bank_frac", 0) or 0) > 0
                  or float(getattr(s, "runner_trail_k", 0) or 0) > 0
                  or int(getattr(s, "add_max", 0) or 0) > 0)
    return {
        "status": "MEASURED",
        "max_abs_r_gap": _num(cmp.get("max_abs_diff_r")),
        "n_trades_both": min(int(cmp.get("n_engine", 0)), int(cmp.get("n_replay", 0))),
        "n_engine": int(cmp.get("n_engine", 0)), "n_replay": int(cmp.get("n_replay", 0)),
        "n_disagree": cmp.get("n_disagree"),
        "agree_within_tolerance": bool(cmp.get("ok")), "why": cmp.get("why"),
        "cost_price_units": round(cost_px, 8),
        "signals_outside_replay2_contract": int(outside), "n_signals": len(sigs),
        "contract_note": ("replay2 models next-open fills, intrabar stop/target with stop first, "
                          "TTL exits and one position at a time; trigger/bank/trail/pyramid "
                          "signals are outside that contract and a gap on them is expected"),
    }


def forward_success_priors(base: Path) -> dict:
    """Per-family Beta posteriors from the funnel census (V19), read ONCE per sweep.

    `funnel_census.build` reads the docket, the canon and the shadow states -- not this sweep's
    report -- so the posterior is what the desk believed BEFORE this sweep's certificates joined
    the canon. `forward_survived` is the pass rate into forward survival from forward enrolment,
    which is what a forward-success prediction is; the `certified` stage (the posterior
    `deepening_worker.voi_order` reads) rides beside it for the record.
    """
    try:
        from libs.research import funnel_census as fc
        recs = fc.build(base)
    except Exception as exc:
        return {"_error": f"{type(exc).__name__}: {exc}"[:200]}
    out: dict = {}
    for fam, r in recs.items():
        try:
            a_f, b_f = r.posterior("forward_survived")
            a_c, b_c = r.posterior("certified")
            out[str(fam)] = {
                "p": _num(a_f / (a_f + b_f)) if (a_f + b_f) > 0 else None,
                "beta": [round(a_f, 4), round(b_f, 4)], "stage": "forward_survived",
                "denominator_known": bool(r.denominator_known("forward_survived")),
                "counts": {k: int(v) for k, v in dict(r.counts).items()},
                "p_certified_stage": {"p": _num(a_c / (a_c + b_c)) if (a_c + b_c) > 0 else None,
                                      "beta": [round(a_c, 4), round(b_c, 4)]},
            }
        except Exception:
            continue
    return out


def p_forward_success(family: str, priors: dict) -> dict:
    """The recorded prediction for one certificate; scored later, never a gate."""
    if "_error" in priors:
        return _unmeasured(f"funnel census unreadable: {priors['_error']}", family=family)
    rec = priors.get(family)
    if rec is None:
        return _unmeasured(f"family {family!r} has no funnel record, so no posterior exists "
                           f"for it; absence is not a probability", family=family)
    return {"status": "RECORDED_PREDICTION", "family": family, **rec,
            "basis": ("libs.research.funnel_census Beta posterior (empirical-Bayes prior fitted "
                      "to the desk's own yield, plus this family's funnel counts), taken at "
                      "certificate time before this sweep's certificates joined the canon. A "
                      "prediction to be scored against the forward outcome; not a gate")}


def release_stamp() -> dict:
    """`release_id` and `canon_sha256` of the release this certificate is minted under (A8).

    `release.load()` is one JSON read of the sealed record -- the cheapest read there is and
    the one the gateway stamps on every intent. Without a sealed record the working tree is
    described (`build(write=False)`, git plus a few file hashes); without either, None with why.
    """
    out: dict = {"release_id": None, "canon_sha256": None,
                 "release_basis": {"source": None, "why": None}}
    try:
        from libs.ops import release as _rel
        doc = _rel.load()
        source = "desks/mt5/data/RELEASE.json via libs.ops.release.load (sealed record)"
        if doc is None:
            doc = _rel.build(write=False)
            source = "libs.ops.release.build(write=False) on the working tree (no RELEASE.json)"
        out["release_id"] = doc.get("release_id")
        out["canon_sha256"] = doc.get("canon_sha256")
        out["release_basis"] = {
            "source": source, "sealed": bool(doc.get("sealed")),
            "code_sha": doc.get("code_sha") or doc.get("live_sha"),
            "running_sha": _rel.git_head(),
            "canon_note": ("canon_sha256 is the digest of UNIVERSAL_SURVIVORS.canon.json the "
                           "release names -- the canon this certificate was minted UNDER, not "
                           "the one it joins"),
            "why": None if doc.get("release_id") else "release record carries no release_id",
        }
    except Exception as exc:
        out["release_basis"]["why"] = f"{type(exc).__name__}: {exc}"[:200]
    return out


def certificate_annotations(v: dict, cell: dict | None, meta: dict, *, priors: dict,
                            release: dict, deadline: float) -> dict:
    """Every recorded-not-gating annotation for ONE passing verdict, each wrapped so a failure
    in one records UNMEASURED for that one and the certificate is still written."""
    out = dict(release)
    fam = str(v.get("family") or (cell or {}).get("family") or "")
    sym = str(v.get("sym") or (cell or {}).get("sym") or "")
    params = dict((cell or {}).get("params") or {})
    ds = None
    if cell is not None:
        ds = cell.get("_cached_ds") if cell.get("_cached_ds") is not None else cell.get("_fresh_ds")
    out["p_forward_success"] = _safe(lambda: p_forward_success(fam, priors), "p_forward_success")
    if cell is None:
        ctx = {"ok": False, "why": "the verdict's cell object is not in this sweep's docket"}
    elif time.time() > deadline:
        ctx = {"ok": False, "why": (f"annotation budget ({ANNOTATION_BUDGET_SEC:.0f}s) exhausted "
                                    f"before this cell was rebuilt; the certificate is written "
                                    f"and the trade-level annotations are UNMEASURED")}
    else:
        ctx = _rebuild_for_annotation(cell, meta)
    trades = ctx.get("trades") if ctx.get("ok") else None
    out["replay2_agreement"] = _safe(lambda: replay2_agreement(ctx), "replay2_agreement")
    out["complexity"] = _safe(lambda: certificate_complexity(fam, params, ds, trades),
                              "complexity")
    seed = int(hashlib.sha1(str(v.get("cell")).encode()).hexdigest()[:8], 16)

    def _baselines() -> dict:
        frame = ctx.get("df") if ctx.get("ok") else _bars_for(sym, timeframe_of(params, fam))
        return certificate_baselines(sym, ds, frame, trades, seed=seed)
    out["baselines"] = _safe(_baselines, "baselines")
    ctx.clear()          # release the rebuilt frame and signals before the next certificate
    return out


def run_gauntlet(cells: list, hunt_name: str, meta: dict) -> dict:
    """Run full 10-gate gauntlet on a list of cells."""
    print(f"\n=== GAUNTLET: {hunt_name} ({len(cells)} cells) ===")

    # Build daily series
    daily = []
    hits = 0
    for c in cells:
        try:
            if c.get("_cached_ds") is not None:
                daily.append(c["_cached_ds"])
                hits += 1
                continue
            last_day = c.get("_last_day")
            ds = _series_trim_partial(daily_series(c["df"], c["sigs"], c["costs"]), last_day)
            c["_fresh_ds"] = ds
            daily.append(ds)
            # BOTH COST ARMS IN ONE PASS, so a cell's signals can be released the moment it is
            # done with. The 3x arm used to run as a SECOND loop over every cell, which meant
            # every built cell had to keep its `sigs` alive from the first loop to the second.
            # MEASURED 2026-09-02 on the desk box: the gauntlet held 3,942 MB and left 658 MB
            # free, so `edge_search` (needs ~2000 MB) could not start at all -- which is why
            # edge_search_results.json went 21.6 hours stale and orthogonal_candidates.json 9.3,
            # and the docket ran on miners alone. The cells are independent, so nothing about any
            # verdict changes; only the peak does.
            if c.get("_cached_ds3") is None:
                try:
                    costs3 = costs_for(c["sym"], meta, mult=COST_SCENARIO)
                    c["_fresh_ds3"] = _series_trim_partial(
                        daily_series(c["df"], c["sigs"], costs3), last_day)
                except Exception as exc3:
                    print(f"  FAIL-3x {c['sym']}.{c['family']}: {exc3}")
                    c["_fresh_ds3"] = None
        except Exception as e:
            print(f"  FAIL {c['sym']}.{c['family']}: {e}")
            daily.append(None)
        finally:
            # RELEASE. `df` is a shared LRU frame and costs nothing to drop; `sigs` is this
            # cell's own signal list and is the thing that accumulates.
            c["df"] = c["sigs"] = c["costs"] = None
    if hits:
        print(f"  series cache: {hits}/{len(cells)} cell(s) loaded (unchanged data-day); "
              f"{len(cells) - hits} computed fresh")

    # Build matrix from valid series
    # WHERE CELLS DIE, BY FAMILY. A cell that builds but yields fewer than 60 trading days has
    # no series the gates can judge, and until now it vanished silently -- 575 `discovered` cells
    # were built, dropped here, and reported nowhere, so the sweep looked like it had simply not
    # found them. A drop is a measurement and belongs in the log with its reason (L1.28a).
    _drop: dict[str, dict[str, int]] = {}
    for _i, _d in enumerate(daily):
        _fam = str(cells[_i].get("family", "?"))
        _row = _drop.setdefault(_fam, {"built": 0, "no_series": 0, "too_few_days": 0, "kept": 0})
        _row["built"] += 1
        if _d is None:
            _row["no_series"] += 1
        elif len(_d) < 60:
            _row["too_few_days"] += 1
        else:
            _row["kept"] += 1
    for _fam, _row in sorted(_drop.items(), key=lambda kv: -kv[1]["built"]):
        if _row["kept"] != _row["built"]:
            print(f"  cells {_fam}: built={_row['built']} kept={_row['kept']} "
                  f"no_series={_row['no_series']} under_60_days={_row['too_few_days']}")

    valid = [(i, d) for i, d in enumerate(daily) if d is not None and len(d) >= 60]
    if not valid:
        print("  NO cells with >= 60 days")
        return {"hunt": hunt_name, "error": "no valid cells", "verdicts": []}

    cols = [d.to_numpy(float) for _, d in valid]
    min_len = min(len(a) for a in cols)
    matrix = np.column_stack([a[-min_len:] for a in cols])

    # Program-level tests
    # THE CANONICAL TRIAL BASIS, AND NOTHING ELSE (principal 2026-08-26: "we don't count trials
    # of deflation, we don't use any harsh gates -- it's direct discovery, backtest, 10 gates,
    # certification, forward, then live"). The sealed attestation DEFINES this basis and it is not
    # mine to substitute. An earlier revision raised n_trials to the width a search declared
    # (43,512 instead of 378), which made `deflated_sharpe` dramatically harsher -- the same
    # unsanctioned bar I had just deleted from the searcher, moved INSIDE the gate where it was
    # less visible. The ten gates run exactly as defined.
    sharpes = np.array([sharpe_ratio(matrix[:, k]) for k in range(matrix.shape[1])])
    sh_var_measured = float(sharpes.var(ddof=1)) if len(sharpes) > 1 else 0.0
    # THE SECOND DOOR THE BAR CAME THROUGH. The deflated-Sharpe hurdle is
    # expected_max_sharpe(n_trials, variance_of_sharpes), and this used the variance ACROSS THE
    # CURRENT SWEEP -- so pinning the trial count alone did not fix the bar. Measured 2026-08-29
    # with trials already pinned at 597: sr0 still rose to 2.4523, because a wider and more
    # diverse batch has wider Sharpe dispersion (0.0149 at 460 cells, 0.6238 at 1,985). Same
    # candidate, same policy, a bar four times higher for being scheduled into a bigger sweep.
    # Both inputs are constants now, so the bar is a property of the policy rather than of the
    # hour. The MEASURED dispersion is still computed and still reported: hiding the input would
    # make it impossible to check the constant was not chosen to suit a result.
    sh_var = sh_var_measured
    _var_basis = "measured_batch_dispersion"
    try:
        from research.gate_policy import FIXED_VARIANCE_OF_SHARPES
        if isinstance(FIXED_VARIANCE_OF_SHARPES, (int, float)) and FIXED_VARIANCE_OF_SHARPES > 0:
            sh_var = float(FIXED_VARIANCE_OF_SHARPES)
            _var_basis = f"fixed_variance_of_sharpes({sh_var})"
    except Exception as _exc:                      # policy unreadable: fail to the measured value
        _var_basis = f"measured_batch_dispersion (policy unreadable: {type(_exc).__name__})"
    # THE SEALED TRIAL CHARGE, EXACTLY (gate_spec.yaml deflated_sharpe.params):
    #   trial_count_basis: ceil(null_calibrated_participation_ratio_effective_cells * 7)
    #   fail_closed_to:    raw_cells * 7
    # This door charged raw*7 UNCONDITIONALLY -- no census -- so a batch of correlated
    # parameterizations (dozens of variants of related strategies, effectively FEW independent
    # bets) was charged as fully independent: a HARSHER bar than the sealed policy, hidden
    # inside the gate, on the one door every hourly candidate walks through (found 2026-08-27
    # when the principal asked "are you sure we use the same tests for all of these").
    # `charged_trial_count` fails closed to raw*7 whenever the census cannot measure.
    try:
        from mt5desk.canonical import calibrated_census_report
        from research.gate_policy import charged_trial_count
        _census = calibrated_census_report(
            [matrix[:, k] for k in range(matrix.shape[1])],
            sd_sharpe=float(sharpes.std(ddof=1)) if len(sharpes) > 1 else 0.0)
        n_trials, _trial_basis = charged_trial_count(
            matrix.shape[1], _census.get("n_effective"), _census.get("method"))
    except Exception as _exc:
        n_trials = max(2, math.ceil(matrix.shape[1] * TRIALS_MULTIPLIER))
        _trial_basis = f"raw_cells_x7_fail_closed ({type(_exc).__name__})"
        _census = {"unavailable": str(_exc)[:120]}

    print(f"  Matrix: {matrix.shape}, n_trials={n_trials} ({_trial_basis}), "
          f"var_of_sharpes={sh_var} ({_var_basis}; measured this sweep {sh_var_measured:.6f})")
    t0 = time.time()

    if matrix.shape[1] < 2:
        # PBO and SPA are program-level relative-performance tests. One surviving series is not
        # evidence that it passes them, but it is also not an exception that should abort the
        # entire hourly certifier. Record the two gates as conservative measured failures so the
        # candidate remains visible and the authority file is still published intact.
        pbo_val, pbo_ok = 1.0, False
        spa_p, spa_ok = 1.0, False
        print("  PBO: 1.0000 (FAIL: requires >=2 strategies)")
        print("  SPA: p=1.0000 (FAIL: requires >=2 strategies)")
    else:
        pbo = probability_backtest_overfitting(matrix)
        pbo_val = float(pbo.pbo)
        pbo_ok = pbo_val <= PBO_THRESHOLD
        print(f"  PBO: {pbo_val:.4f} ({'PASS' if pbo_ok else 'FAIL'})")

        spa = hansen_spa(matrix)
        spa_p = float(spa.p_value)
        spa_ok = spa_p < SPA_ALPHA
        print(f"  SPA: p={spa_p:.4f} ({'PASS' if spa_ok else 'FAIL'})")

    # 3x cost series
    # ALREADY COMPUTED ABOVE, in the same pass that had the frames in hand. This loop now only
    # collects and caches; it holds no bars and builds no signals.
    daily_x3 = []
    for c in cells:
        try:
            if c.get("_cached_ds3") is not None:
                daily_x3.append(c["_cached_ds3"])
                continue
            ds3 = c.get("_fresh_ds3")
            daily_x3.append(ds3)
            if c.get("_fresh_ds") is not None and ds3 is not None and c.get("_ckey"):
                cache_save(c["_ckey"], c["_fresh_ds"], ds3)
        except Exception:
            daily_x3.append(None)

    # Per-cell verdicts
    verdicts = []
    for _idx, (orig_i, ds) in enumerate(valid):
        c = cells[orig_i]
        arr = ds.to_numpy(float)
        cid = cell_id(c)

        # In-sample
        sr = sharpe_ratio(arr)
        stages = {
            "economic_prior": economic_prior(c),
            "in_sample_screen": {"passed": bool(sr > 0.0), "sharpe": round(float(sr), 4)},
        }

        # Deflated Sharpe
        dsr = deflated_sharpe_ratio(arr, n_trials=n_trials,
                                    variance_of_sharpes=sh_var, threshold=DSR_THRESHOLD)
        stages["deflated_sharpe"] = {
            "passed": bool(dsr.passed), "dsr": round(float(dsr.dsr), 4),
            "sr0": round(float(dsr.sr0_threshold), 4), "n_trials": n_trials,
            "variance_of_sharpes": round(sh_var, 6),
            "variance_basis": _var_basis,
            "variance_measured_this_sweep": round(sh_var_measured, 6),
        }

        # PBO + SPA (program-level)
        stages["pbo"] = {"passed": pbo_ok, "pbo": round(pbo_val, 4)}
        stages["reality_check_spa"] = {"passed": spa_ok, "p_value": round(spa_p, 4)}

        # CPCV
        cpcv = CPCV(n_groups=6, n_test_groups=2)
        oos = []
        for split in cpcv.split(len(arr)):
            te = np.asarray(split.test)
            if len(te) >= 30:
                oos.append(sharpe_ratio(arr[te]))
        cpcv_mean = float(np.mean(oos)) if oos else 0.0
        stages["cpcv"] = {"passed": bool(cpcv_mean > 0.0),
                          "mean_oos_sharpe": round(cpcv_mean, 4), "folds": len(oos)}

        # Walk Forward
        try:
            wf = WalkForwardEngine().evaluate(arr, n_splits=WF_SPLITS,
                                              test_size=max(20, len(arr) // 6),
                                              min_oos_sharpe=0.0,
                                              min_stability=WF_MIN_STABILITY)
            wf_status = wf.status
            wf_oos = float(wf.oos_sharpe)
            wf_stab = float(wf.stability)
        except Exception:
            wf_status, wf_oos, wf_stab = "TOO_SHORT", float("-inf"), 0.0
        stages["walk_forward"] = {
            "passed": bool(wf_status is WalkForwardStatus.PASSED),
            "oos_sharpe": round(wf_oos, 4), "stability": round(wf_stab, 4)
        }

        # Stress costs (3x)
        x3_ds = daily_x3[orig_i]
        exp3 = float(x3_ds.to_numpy(float).mean()) if x3_ds is not None and len(x3_ds) > 0 else 0.0
        stages["stress_costs"] = {"passed": bool(exp3 > 0.0), "exp_x3": round(exp3, 4)}

        # Lockbox
        stages["lockbox"] = {"passed": bool(wf_oos >= 0.0),
                             "lockbox_sharpe": round(wf_oos, 4)}

        # Expected Value
        ev = float(arr.mean())
        stages["expected_value"] = {"passed": bool(ev > 0.0), "ev": round(ev, 4)}

        passed = all(s["passed"] for s in stages.values())
        verdicts.append({
            "cell": cid, "sym": c["sym"], "family": c["family"],
            "days": len(arr), "passed": passed, "stages": stages
        })

    # A DROPPED CELL IS A MEASURED OUTCOME, NOT A DISAPPEARANCE (L1.28a / WS-005). Cells whose
    # daily series is absent or shorter than the 60 observations CPCV+walk-forward require never
    # entered the matrix above -- and used to leave no trace in the report at all: measured
    # 2026-08-27, 122 cells were submitted and 4 verdicts were written, so 118 candidates read
    # as "tested, no pass" to every consumer when in truth they were never judged. They are
    # recorded here as UNMEASURED verdicts (passed=False, never a pass) carrying the reason and
    # the observation count, so the funnel is honest and a search producing untestable
    # candidates is VISIBLE rather than looking like a search producing failures.
    _judged = {i for i, _ in valid}
    for _i, _c in enumerate(cells):
        if _i in _judged:
            continue
        _d = daily[_i] if _i < len(daily) else None
        _n = 0 if _d is None else len(_d)
        verdicts.append({
            "cell": cell_id({"sym": _c["sym"], "family": _c["family"],
                             "params": _c.get("params") or {}}),
            "sym": _c["sym"], "family": _c["family"], "days": _n,
            "passed": False, "unmeasured": True,
            "stages": {"observations": {
                "passed": False, "days": _n, "required": 60,
                "why": ("no daily series could be built from this cell's signals"
                        if _d is None else
                        f"only {_n} daily observations; CPCV with purge+embargo and the "
                        f"walk-forward folds require 60. This is UNMEASURED, not a failure: "
                        f"the cell fires too rarely to be judged, which is a fact about the "
                        f"SEARCH that proposed it, not evidence against the edge")}},
        })

    elapsed = time.time() - t0
    n_pass = sum(1 for v in verdicts if v.get("passed"))
    n_unmeasured = sum(1 for v in verdicts if v.get("unmeasured"))
    gate_fails = {}
    for v in verdicts:
        if v.get("unmeasured"):
            continue          # never judged: counting it as a gate failure would be a lie
        for name, s in v.get("stages", {}).items():
            if not s["passed"]:
                gate_fails[name] = gate_fails.get(name, 0) + 1

    n_real = len(verdicts) - n_unmeasured
    print(f"\n  RESULT: {n_pass}/{n_real} pass all 10 gates ({elapsed:.0f}s); "
          f"{n_unmeasured} UNMEASURED (too few observations to judge)")
    if gate_fails:
        print(f"  Gate failures: {gate_fails}")

    for v in verdicts:
        if v.get("unmeasured"):
            continue                      # summarised in the RESULT line and the report file
        status = "PASS" if v["passed"] else "FAIL"
        print(f"  {status} {v['cell']:<50} n={v['days']}")
        if not v["passed"]:
            for name, s in v["stages"].items():
                if not s["passed"]:
                    print(f"         FAIL {name}: {s}")

    return {
        "hunt": hunt_name,
        "n_cells": len(cells),
        "n_trials": n_trials,
        "trial_count_basis": _trial_basis,
        "trial_census": _census,
        # THE LIFETIME COUNT, BESIDE THE SEALED CHARGE (V21). `n_trials` above is the policy's
        # fixed campaign charge and stays exactly that; this records what the experiment ledger
        # holds for every family in the sweep so the two counters can be read side by side.
        "trial_ledger": _safe(lambda: lifetime_trial_report(c.get("family") for c in cells),
                              "trial_ledger"),
        # GATE INDEPENDENCE, COUNTED (V1): how many verdicts' lockbox restates walk-forward,
        # and that PBO/SPA are one matrix-level number on every verdict. Measurement only.
        "gate_independence": _safe(lambda: gate_independence(verdicts), "gate_independence"),
        "program_level": {"pbo": round(pbo_val, 4), "spa_p": round(spa_p, 4)},
        "survivors_passing_all": n_pass,
        "n_judged": n_real,
        "n_unmeasured": n_unmeasured,
        "unmeasured_note": ("cells whose signals produced fewer than 60 daily observations were "
                            "NOT judged; they are recorded as UNMEASURED verdicts, never as "
                            "failures. A high count is a fact about the SEARCH (candidates that "
                            "fire too rarely to test), not evidence against the edges."),
        "gate_fails": gate_fails,
        "verdicts": verdicts,
        "swept_at": datetime.now(UTC).isoformat(),
    }


#: Set ONLY by `--only`. None means the ordinary whole-docket run, byte-for-byte as before --
#: every branch below is guarded on this being non-None, so the certifying path is untouched.
_REPRO: dict[str, object] | None = None


def _repro_active() -> bool:
    return _REPRO is not None


def main():
    meta = json.loads((UNI / "universe.json").read_text("utf-8"))

    # Load external backtest survivors
    surv_file = HYP / "external_survivors.json"
    if not surv_file.exists():
        print("No external survivors found")
        return
    survivors = json.loads(surv_file.read_text("utf-8"))
    print(f"Loaded {len(survivors)} external survivors")
    # EMPTY INPUT IS A HALT, NOT A SWEEP (2026-08-26, measured). The hourly merge briefly wrote
    # a 0-row input; this gauntlet then ran "normally" on nothing and rewrote the AUTHORITY file
    # to n=0 -- wiping 21 certificates with exit code 0. Zero candidates means there is nothing
    # to judge, and a judge with an empty docket must not touch the records of past verdicts.
    if not survivors:
        print("HALT: 0 candidates in the input -- nothing to judge. Refusing to write any "
              "report or touch UNIVERSAL_SURVIVORS.json; an empty docket does not revoke past "
              "verdicts.")
        return

    # POINT-IN-TIME OR NO CERTIFICATE (2026-09-05), AS A RATCHET AND NOT A CLIFF.
    #
    # `proposer_common.donate` now refuses to WRITE an unstamped candidate. This is the same rule
    # at the JUDGE, so a row that reached the docket by another path -- a hand-edited merge, an
    # older intelligence file, an organ that does not donate through the proposer contract --
    # cannot be certified either. A certificate is a claim about what was knowable when, and a
    # row that cannot say when it became knowable cannot support one.
    #
    # WHY IT RATCHETS. Measured 2026-09-05: 0 of 4,768 docket rows carry a stamp, because the
    # stamp was optional until today. Excluding every unstamped row RIGHT NOW would empty the
    # docket and halt certification entirely -- turning a data-quality rule into an outage, and
    # the desk is already short of certificates. So the exclusion switches on the moment ANY
    # stamped row exists and then only tightens: while the docket is wholly unstamped the rows
    # are judged and the gap is named loudly, and from the first stamped donation onward every
    # unstamped row is refused. The rule can only get stricter, never looser, and the desk never
    # goes dark to enforce it.
    stamped = [h for h in survivors if isinstance(h, dict) and is_stamped(h)]
    unstamped = [h for h in survivors if isinstance(h, dict) and not is_stamped(h)]
    if unstamped and stamped:
        print(f"REFUSED {len(unstamped)} unstamped candidate(s) of {len(survivors)}: no "
              f"available_time / ingested_time / source_version / payload_hash. Re-donate "
              f"through proposer_common.donate. First: "
              f"{[str(h.get('family') or h.get('title'))[:40] for h in unstamped[:5]]}")
        survivors = stamped
    elif unstamped:
        print(f"PIT GAP: all {len(unstamped)} candidates are unstamped, so the refusal is "
              f"DEFERRED this pass -- judging them rather than halting certification. The "
              f"exclusion switches on with the first stamped donation and only tightens after.")

    # Group by unique (sym, CHART, family, params) combos. A proposer that carries the chart on
    # the ROW rather than in params (the orthogonal sweep writes both) must not have it dropped
    # here: two rows differing only by chart are two cells, and folding them would hand one
    # verdict to both.
    cells = {}
    for h in survivors:
        sym = h.get("symbol")
        fam = h.get("family")
        params = dict(h.get("params") or {})
        if not sym or not fam:
            continue
        row_tf = str(h.get("timeframe") or "").upper()
        if row_tf and row_tf != "H1" and "timeframe" not in params:
            params["timeframe"] = row_tf
        key = f"{sym}.{fam}.{json.dumps(params, sort_keys=True)}"
        if key not in cells:
            cells[key] = {
                "sym": sym,
                "family": fam,
                "params": params,
                "timeframe": timeframe_of(params, str(fam)),
                "mechanism_status": h.get("mechanism_status"),
                "mechanism_note": h.get("mechanism_note"),
            }

    # REPRODUCTION RESTRICTS THE DOCKET, NOTHING ELSE. Every gate below runs exactly as it does
    # on the full sweep -- same code, same costs, same data -- on one named cell. That identity is
    # the point: a reproducer judging by its own second implementation would prove only that two
    # programs agree, which is what "one canonical validator" exists to forbid.
    if _repro_active():
        want = str((_REPRO or {}).get("only") or "")
        cells = {k: v for k, v in cells.items() if want in k}
        if not cells:
            print(f"REPRODUCE: no cell matches {want!r} in this docket -- "
                  f"UNMEASURED, not a refutation (L1.28a)")
            return
        print(f"REPRODUCE: {len(cells)} cell(s) matching {want!r}")

    print(f"Unique cells to evaluate: {len(cells)}")
    families_submitted: dict[str, int] = {}
    for spec in cells.values():
        fam = str(spec.get("family") or "UNKNOWN")
        families_submitted[fam] = families_submitted.get(fam, 0) + 1
    print(f"Submitted families: {families_submitted}")

    # GATES ARE SEQUENTIAL. A statistical pattern with no falsifiable economic mechanism fails
    # the first canonical gate. Before this partition, 2,760 such rows consumed days of signal
    # construction, CPCV and walk-forward work despite having zero path to a certificate. Record
    # each exact reject, but reserve downstream compute for candidates still capable of passing.
    # `meta` IS PASSED so the tradeability limb runs. Without it the sweep spends the other nine
    # gates on symbols the desk does not have and mints certificates that can never enrol a
    # forward clock -- eight of them existed when this was wired (6x AFG, 2x AFL).
    eligible_specs, prior_rejections = partition_at_economic_prior(list(cells.values()), meta)
    _untradeable = sum(1 for r in prior_rejections
                       if r.get("terminal_gate") == "symbol_eligibility")
    print(f"Gate 0: {len(eligible_specs)} advance; {len(prior_rejections)} terminal reject "
          f"({_untradeable} untradeable symbol, "
          f"{len(prior_rejections) - _untradeable} no economic prior)")

    # Build cell objects -- CACHE FIRST. A cell whose (identity, params, last complete data-day)
    # was already computed loads its 1x and 3x daily series and skips signal generation AND both
    # backtests entirely; only genuinely new candidates, or a new trading day, pay for compute.
    # This is what makes an hourly sweep of a 3,000+ docket take minutes instead of the hour.
    cell_objs = []
    cache_hits = 0
    built_fresh = 0
    deferred: list[dict] = []
    _mem_deferred = 0
    blocked_build: list[dict] = []
    _build_t0 = time.time()
    # Yesterday's keys die with yesterday's data-day; prune so the cache never grows unbounded.
    try:
        import time as _t
        for _f in CACHE_DIR.glob("*.npz"):
            if _t.time() - _f.stat().st_mtime > 3 * 86400:
                _f.unlink(missing_ok=True)
    except OSError:
        pass
    # SYMBOL ORDER IS A PERFORMANCE CONTRACT, NOT A PREFERENCE. build_cell -> resolve_inputs
    # rebuilds residuals and rolling correlations against EVERY other registry instrument, and it
    # is memoised only two entries deep because the full universe for one symbol is hundreds of
    # series and this box has 8GB beside a live terminal. Two entries convert ~99% of those calls
    # into hits WHEN a symbol's cells are consecutive, and ~0% when they are interleaved.
    # Measured 2026-09-01: 14,060 of 20,341 `discovered` cells use an `ext_` feature across just
    # 137 symbols, so unsorted iteration was rebuilding the same universe 13,923 redundant times.
    # Cells are independent -- each is built from its own bars and judged by the same matrix
    # afterwards -- so ordering changes nothing about any verdict. It does change WHICH cells the
    # fresh-build budget reaches first, and grouping means the budget buys more cells per second,
    # which is the point.
    # SYMBOL GROUPS STAY CONTIGUOUS -- that is the frame-cache win above and it is preserved --
    # but WHICH group goes first now rotates by starvation instead of by the alphabet.
    #
    # A LIST ORDER STARVES ITS OWN TAIL, and this one did. The budget builds ~20 minutes of cells
    # per hour against a docket that goes cold daily when the cache key rolls, so a full cold
    # sweep cannot finish in a day -- measured 2026-09-02, 7,648 cells came back
    # NOT_RUN_BUILD_BUDGET_DEFERRED. Under a fixed alphabetical order those are always the SAME
    # 7,648: AUDCAD is rebuilt every hour and the far end of the alphabet is never reached at
    # all, so "deferred" quietly means "never" for a third of the docket while the report calls
    # it work not yet done.
    #
    # Longest-unbuilt symbol first makes deferral self-correcting: whatever an hour misses is at
    # the front of the next one, and the docket rotates completely instead of the head being
    # rebuilt forever. Same rule `fetch_universe._refresh_order` applies to bars, for the same
    # reason. Verdicts are unaffected -- cells are independent and judged by the same matrix.
    _cursor = _build_cursor()
    _built_syms: set[str] = set()
    # CHART GROUPS STAY CONTIGUOUS INSIDE SYMBOL GROUPS, for the same reason symbol groups stay
    # contiguous at all: the frame cache is what makes the build cheap, and one symbol's M5 and
    # H1 frames are two different entries in it.
    eligible_specs = sorted(
        eligible_specs,
        key=lambda sp: (_cursor.get(str(sp.get("sym") or ""), ""),
                        str(sp.get("sym") or ""),
                        timeframe_of(sp.get("params"), str(sp.get("family") or "")),
                        str(sp.get("family") or "")))
    # PARALLEL PRE-WARM, BEFORE THE LOOP THAT HAS ALWAYS RUN. Workers build the uncached cells
    # into the on-disk cache in this exact order until the build budget is spent; the loop
    # below then finds them and takes its cached branch, and defers whatever the pool did not
    # reach -- the same deferral, with the same reason, that a single process produced. The
    # deadline is `_build_t0 + FRESH_BUILD_BUDGET_SEC`, the loop's own clock, so the two share
    # one budget rather than stacking to ninety minutes and breaking the hourly cadence.
    # With WORKERS == 1 this block is skipped and the sweep is byte-for-byte what it was.
    _prewarm = None
    if WORKERS > 1 and len(eligible_specs) > 1:
        _prewarm = _prewarm_cache(eligible_specs, meta, _build_t0 + FRESH_BUILD_BUDGET_SEC)
    # STAGE 0, REPORT-ONLY (V8). `stage0_prefilter` says why it cannot be more than that here:
    # a spec carries no return stream, and the cells that do (cached series) have already paid
    # their build. It judges every cached series on the loop's cached branch below, counts what
    # it WOULD have rejected, and removes nothing; the result's `pre_filter` block and the
    # append-only ledger carry the decisions. Fresh builds are counted as unjudged-before-build.
    _stage0 = stage0_new_summary()
    _stage0_verdicts: dict[str, dict] = {}
    for spec in eligible_specs:
        key = f"{spec['sym']}.{spec['family']}.{json.dumps(spec['params'], sort_keys=True)}"
        spec_tf = timeframe_of(spec.get("params"), str(spec.get("family") or ""))
        # THE CELL'S OWN CHART DECIDES ITS DATA-DAY. `last_day` is both the cache key's rollover
        # and the boundary `_series_trim_partial` drops the partial day at; taking it from H1 for
        # an M5 cell would key the cell to a day its own tape may not have reached and trim its
        # series at a boundary from a different feed.
        frame = _bars_for(spec["sym"], spec_tf)
        if frame is None or len(frame) == 0:
            print(f"  SKIP {key}: {spec_tf} parquet missing")
            blocked_build.append({**spec, "downstream_status": "NOT_RUN_DATA_MISSING",
                                  "why": f"point-in-time {spec_tf} parquet is missing or empty"})
            continue
        last_day = frame.index[-1].normalize()
        ckey = _cache_key(spec["sym"], spec["family"], spec["params"] or {}, str(last_day.date()),
                          spec_tf)
        cached = cache_load(ckey)
        if cached is not None:
            ds1, ds3 = cached
            stage0_record(_stage0, _stage0_verdicts, spec, spec_tf, ds1)
            cell_objs.append({
                "sym": spec["sym"], "family": spec["family"], "params": spec["params"],
                "timeframe": spec_tf,
                "df": None, "sigs": None, "costs": None,
                "_cached_ds": ds1, "_cached_ds3": ds3, "_ckey": ckey, "_last_day": last_day,
                "mechanism_status": spec.get("mechanism_status"),
                "mechanism_note": spec.get("mechanism_note"),
            })
            cache_hits += 1
            continue
        if time.time() - _build_t0 > FRESH_BUILD_BUDGET_SEC:
            # Out of build budget: defer, never drop. The next sweep finds everything this run
            # cached and starts from here, so the docket converges instead of restarting.
            deferred.append(spec)
            continue
        _rss = _rss_mb()
        if _rss and _rss > MEMORY_BUDGET_MB:
            # Out of MEMORY budget, and the same rule applies: defer, never drop. Building one
            # more cell here is what took the box to 280MB free and stopped every other leg.
            if not _mem_deferred:
                print(f"MEMORY BUDGET reached at {_rss:.0f}MB (cap {MEMORY_BUDGET_MB:.0f}MB) "
                      f"after {built_fresh} fresh cell(s): the rest of the docket is DEFERRED to "
                      f"the next sweep. The cache is cumulative, so they are computed next hour "
                      f"rather than recomputed -- and edge_search and orthogonal_sweep get the "
                      f"room they need to run at all.")
            _mem_deferred += 1
            deferred.append(spec)
            continue
        _built_syms.add(str(spec["sym"]))
        obj = build_cell(spec["sym"], spec["family"], spec["params"], meta)
        if obj:
            obj["mechanism_status"] = spec.get("mechanism_status")
            obj["mechanism_note"] = spec.get("mechanism_note")
            obj["_ckey"], obj["_last_day"] = ckey, last_day
            cell_objs.append(obj)
            built_fresh += 1
            _stage0["unjudged_no_series_before_build"] += 1
        else:
            print(f"  SKIP {key}: parquet missing or build failed")
            blocked_build.append({**spec, "downstream_status": "NOT_RUN_BUILD_FAILED",
                                  "why": "signal construction returned no executable cell"})
    if cache_hits:
        print(f"Cell cache: {cache_hits}/{len(eligible_specs)} loaded (same data-day), "
              f"{len(eligible_specs) - cache_hits} to compute")
    if deferred:
        print(f"BUILD BUDGET reached after {built_fresh} fresh cell(s) in "
              f"{time.time() - _build_t0:.0f}s: {len(deferred)} cell(s) DEFERRED to the next "
              f"sweep and recorded UNMEASURED. They are not failures -- the cache is cumulative, "
              f"so the next run resumes from here and the docket converges.")

    # Run the remaining gates, or still emit the complete gate-1 rejection ledger when none can
    # advance. A no-mechanism discovery batch is a valid negative result, not a missing report.
    if cell_objs:
        result = run_gauntlet(cell_objs, "external_discoveries", meta)
    else:
        print("No candidates advanced beyond the economic-prior gate")
        result = {
            "hunt": "external_discoveries",
            "n_cells": 0,
            "n_trials": 0,
            "program_level": {"status": "NOT_RUN_NO_GATE_1_ELIGIBLE_CELLS"},
            "survivors_passing_all": 0,
            "gate_fails": {},
            "verdicts": [],
            "swept_at": datetime.now(UTC).isoformat(),
        }
    result["n_cells_discovered"] = len(cells)
    result["n_cells_advanced_beyond_economic_prior"] = len(cell_objs)
    result["n_cells_rejected_at_economic_prior"] = len(prior_rejections)
    # DEFERRED CELLS ARE IN THE RECORD, NOT MISSING FROM IT. A cell the build budget did not
    # reach is UNMEASURED -- not a pass, not a fail, and emphatically not absent. Leaving it out
    # would make the report describe a smaller docket than the desk actually holds, which is the
    # silent-shrinkage failure this desk has been burned by before. It carries its own reason so
    # nobody has to guess why a cell has no verdict (L1.28a).
    deferred_verdicts = [{
        "cell": cell_id({"sym": s["sym"], "family": s["family"], "params": s.get("params") or {}}),
        "sym": s["sym"], "family": s["family"], "days": 0, "passed": None,
        "stages": {},
        "downstream_status": "NOT_RUN_BUILD_BUDGET_DEFERRED",
        "why": ("the sweep's fresh-build budget was exhausted before this cell was computed. "
                "The per-cell cache is cumulative and content-addressed, so the next sweep "
                "resumes here rather than restarting; this is work not yet done, never a "
                "verdict."),
    } for s in deferred]
    blocked_verdicts = [{
        "cell": cell_id({"sym": s["sym"], "family": s["family"],
                         "params": s.get("params") or {}}),
        "sym": s["sym"], "family": s["family"], "days": 0, "passed": None,
        "stages": {}, "downstream_status": s["downstream_status"], "why": s["why"],
    } for s in blocked_build]
    result["n_cells_deferred_build_budget"] = len(deferred)
    # WHICH budget deferred them, because "deferred" with no reason is how a cap becomes
    # invisible and a docket quietly stops converging.
    result["n_cells_deferred_memory_budget"] = _mem_deferred
    result["memory_budget_mb"] = MEMORY_BUDGET_MB
    # WHAT THE POOL DID, in the report beside the budgets that bounded it -- so "42 judged" can
    # be read against "N workers warmed M cells" rather than guessed at from wall time.
    result["workers"] = WORKERS
    result["prewarm"] = _prewarm
    result["peak_rss_mb"] = round(_rss_mb(), 1)
    _save_build_cursor(_cursor, _built_syms)
    result["build_rotation"] = {
        "symbols_built_this_run": len(_built_syms),
        "symbols_in_cursor": len(_cursor),
        "note": "symbol groups are ordered longest-unbuilt first, so a deferred cell is at the "
                "front of the next sweep rather than behind the same alphabetical head forever",
    }
    result["n_cells_blocked_build_or_data"] = len(blocked_build)
    result["verdicts"] = (prior_rejections + deferred_verdicts + blocked_verdicts
                          + list(result.get("verdicts", [])))
    # STAGE 0's RECORD (V8): counts, the cross-tab against the ten gates, and the ledger append.
    # Reproduction writes its own file and nothing else, so it does not touch the ledger.
    result["pre_filter"] = _safe(
        lambda: stage0_summary(_stage0, _stage0_verdicts, result["verdicts"],
                               None if _repro_active() else PRE_FILTER_LEDGER),
        "pre_filter")
    result.setdefault("gate_fails", {})["economic_prior"] = (
        int(result.get("gate_fails", {}).get("economic_prior", 0)) + len(prior_rejections)
    )

    # Save. REPRODUCTION WRITES ITS OWN FILE AND NOTHING ELSE. This report is read by the
    # research-health fence and the funnel census; a one-cell re-run overwriting it would make the
    # whole docket look like it had shrunk to a single candidate.
    if not _repro_active():
        out = REPORTS / "universal_gates_external.json"
        out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        print(f"\nSaved to {out}")

    # Update UNIVERSAL_SURVIVORS.json -- FULL AUTHORITY OR NOTHING. An earlier revision of this
    # block wrote certificates without the top-level `gate_policy` attestation and without a
    # per-survivor `shadow_spec`; `shadow_admission.is_exact_policy` fails closed on the missing
    # attestation, so one run of this script would have stripped promotion authority from EVERY
    # certificate in the file while printing "Updated". A certifier that demotes what it did not
    # examine is the certifier-wipe defect again, one layer up.
    # A REPRODUCER THAT CAN WRITE CERTIFICATES IS NOT A REPRODUCER. Its verdict must be able to
    # DISAGREE with the record without altering it, or the check and the thing checked are one
    # act. So it exits before the authority block entirely, having written its findings to the
    # path the caller named.
    if _repro_active():
        out = Path(str((_REPRO or {}).get("report_to") or ""))
        payload = {
            "reproduced_at": datetime.now(UTC).isoformat(),
            "only": (_REPRO or {}).get("only"),
            "n_cells": int(result.get("cells_evaluated") or 0),
            "result": result,
            "note": ("Independent re-run of the canonical ten gates on a restricted docket. "
                     "Wrote no certificate and touched no authority file."),
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
        print(f"REPRODUCE: wrote {payload['n_cells']} cell result(s) -> {out}")
        return

    sys.path.insert(0, str(BASE / "desks" / "mt5" / "research"))
    from gate_policy import ATTESTATION, all_ten_pass

    surv_path = REPORTS / "UNIVERSAL_SURVIVORS.json"
    survivors_all, old_doc = {}, {}
    if surv_path.exists():
        try:
            old_doc = json.loads(surv_path.read_text("utf-8"))
            survivors_all = old_doc.get("survivors", {})
        except Exception:
            pass
    n_before = len(survivors_all)

    WINDOWS_KNOWN = {
        "asia": {"range_start": 7},
        "london_am": {"range_start": 10, "range_end": 13, "signal_at": 13},
        "ny_open": {"range_start": 13, "range_end": 14, "signal_at": 14},
        "afternoon": {"range_start": 14, "range_end": 17, "signal_at": 17},
    }

    def _selector(params: dict) -> str | None:
        """Map a cell's params to the ONE forward engine's window name -- or None, visibly.

        A certificate whose selector cannot be named cannot be enrolled, and an un-enrollable
        certificate trips the same-day fence (CERTIFIED-NOT-ENROLLED) rather than silently
        running under guessed hours. The default family session (range_start=7) IS "asia"."""
        if params.get("window") in WINDOWS_KNOWN:
            return params["window"]
        keys = {k: params[k] for k in ("range_start", "range_end", "signal_at") if k in params}
        if not keys or keys == {"range_start": 7}:
            return "asia"
        for name, w in WINDOWS_KNOWN.items():
            if all(w.get(k) == v for k, v in keys.items()):
                return name
        return None


    def _cure_selector(family: str, params: dict) -> str | None:
        """A truthful selector: the SESSION for window families, "continuous" for the rest.

        `_selector` answers "which trading window do these params describe" and falls back to "asia"
        when they describe none. That fallback is correct for a session family whose params omit the
        default window, and a LIE for every family that has no window at all: carry earns a nightly
        rollover, turn_of_month is a calendar effect, cross_asset_residual is a relationship between
        instruments. Measured 2026-08-29 -- all 615 power-cure candidates were stamped `asia`, 344 of
        them from families with no session semantics whatsoever.

        It is currently cosmetic, because the forward engine enrols non-session families on their own
        params and only looks the selector up in WINDOWS for session_range_breakout. It stops being
        cosmetic the moment anything keys on it -- a dedupe by (family, selector, symbol), a coverage
        count by session, a sleeve identity. A false label that is harmless today is a defect waiting
        for its first consumer, and this desk has already been bitten by exactly that with params.
        """
        session_families = {"session_range_breakout", "asia_momentum", "lvc_asia_london"}
        if family in session_families:
            return _selector(params)
        # No window semantics: say so, rather than borrowing a session this mechanism never uses.
        return "continuous"

    _params_by_cell = {cell_id(c): dict(c.get("params") or {}) for c in cell_objs}
    # ANNOTATION INPUTS, READ ONCE PER SWEEP (see the certificate-annotations section): the
    # funnel posteriors (V19) and the release record (A8) are the same for every certificate
    # this sweep writes, and the rebuild budget is shared across them.
    _cells_by_id = {cell_id(c): c for c in cell_objs}
    _priors = _safe(lambda: forward_success_priors(BASE), "forward_success_priors")
    if _priors.get("status") == "UNMEASURED":
        _priors = {"_error": str(_priors.get("why"))}
    _release = release_stamp()
    _annot_deadline = time.time() + ANNOTATION_BUDGET_SEC
    for v in result.get("verdicts", []):
        if not v.get("passed"):
            continue
        key = f"external.{v['cell']}"
        # EXACT MATCH ON THE CELL ID, not a prefix. `f"{sym}.{family}" in cell` matched the FIRST
        # cell sharing that prefix, so every CADJPY certificate inherited rr=1.5 from whichever
        # variant was built first -- wrong params on 14 of 15 certificates, which is worse than
        # none. The cid formula in run_gauntlet encodes rr and wait_bars, so it is a unique key.
        params = _params_by_cell.get(v["cell"], {})
        sel = _selector(params or {})
        row = {
            "hunt": "external_discoveries",
            "cell": v["cell"],
            "sym": v["sym"],
            "days": v["days"],
            "gates": v["stages"],
            "gated_at": datetime.now(UTC).isoformat(),
        }
        if sel is not None:
            # PARAMS ARE PART OF THE IDENTITY. Without them the spec says only "XAUUSD asia",
            # so five separately-gauntleted parameterizations collapse to ONE runnable spec and
            # the forward engine runs its own default for all of them -- four certificates
            # describing strategies that are never forward-tested. The two-stage law requires
            # that the thing which passed the gauntlet IS the thing that goes forward, and that
            # identity is the params, not the session label.
            row["shadow_spec"] = {"symbol": v["sym"], "selector": sel,
                                  "family": v.get("family", "session_range_breakout"),
                                  "is_universe": True, "hunt": "external_discoveries",
                                  "condition": None, "params": dict(params or {})}
        else:
            print(f"  NO-SPEC {key}: params {params} match no known window; no shadow_spec "
                  f"can be built for it")
        # REFUSED RATHER THAN SEALED, and this used to store the row regardless. A certificate
        # with no shadow_spec is unrunnable for ever -- it cannot enrol, cannot be funded and
        # cannot be falsified -- while still counting in every survivor total, so the desk
        # believes it holds an edge it cannot express. The NO-SPEC line above was printed and
        # the row written anyway, which is why 18 of them accumulated unnoticed. One judge for
        # every publisher, so a fourth pen inherits the refusal instead of reinventing it.
        _why = _certificate_refusal(row)
        if _why:
            print(f"  REFUSED-UNRUNNABLE {key}: {_why}")
            continue
        # MEASUREMENT BESIDE THE VERDICT (V5 replay2, V13 complexity, V15 baselines, V19
        # p_forward_success, A8 release stamp). `gates` above is the verdict and is untouched;
        # every key added here is recorded, never gating, and a failure inside any one of them
        # is UNMEASURED for that key with the reason -- the certificate is written regardless.
        row.update(certificate_annotations(v, _cells_by_id.get(v["cell"]), meta,
                                           priors=_priors, release=_release,
                                           deadline=_annot_deadline))
        survivors_all[key] = row

    # THE SCALP LANE'S CERTIFICATES (scripts/scalp_gauntlet.py): same ten gates, same
    # attestation, judged by run_gauntlet on M5/M15 bars. Merged HERE because this block is the
    # one pen on UNIVERSAL_SURVIVORS.json -- never-shrink, never-empty, the purge and the ledger
    # claim apply to these rows exactly as to `external.*`. canon_rows() returns only exact
    # ten-gate passes under the exact policy; an absent report merges and revokes nothing.
    try:
        sys.path.insert(0, str(BASE / "desks" / "mt5" / "scripts"))
        import scalp_gauntlet as _sg
        _scalp_rows = _sg.canon_rows(REPORTS / "SCALP_GAUNTLET.json")
        survivors_all.update(_scalp_rows)
        if _scalp_rows:
            print(f"  scalp certificates merged: {len(_scalp_rows)} ({', '.join(_scalp_rows)})")
    except Exception as _exc:
        print(f"  scalp certificates NOT merged ({type(_exc).__name__}: {_exc}); canon unchanged")

    # ---------------------------------------------------------------- power-cure candidates
    # THE CURE THE POLICY PROMISES NEEDS AN ARTIFACT TO ACT ON. gate_spec marks five gates POWER
    # with cure_by_forward: true, and the promoter implements that cure -- but a cell can only be
    # cured once it is on a forward clock, and nothing published the cells that qualify. So a
    # sleeve that cleared every VALIDITY gate (the five with no cure) and missed only on a power
    # gate had no way to begin gathering the evidence its failing gate is explicitly allowed to
    # be settled by. Measured 2026-08-28: 506 such cells, the best at out-of-sample Sharpe 0.7771
    # over 426 days, and CHFNOK carry passing NINE of ten.
    #
    # This file is SEPARATE from UNIVERSAL_SURVIVORS.json on purpose. That file is the
    # certificate authority and nothing uncertified may appear in it. These rows are candidates
    # for EVIDENCE GATHERING ONLY -- they carry no promotion authority, and the promoter still
    # applies the forward cure thresholds before anything is promoted.
    #
    # VALIDITY IS ABSOLUTE. One validity miss and the cell is dead, never cured, never listed.
    try:
        from research.gate_policy import get_power_gates, get_validity_gates
        _validity, _power = set(get_validity_gates()), set(get_power_gates())
    except Exception:
        _validity = {"economic_prior", "pbo", "reality_check_spa", "stress_costs", "lockbox"}
        _power = {"in_sample_screen", "deflated_sharpe", "cpcv", "walk_forward", "expected_value"}

    cure_rows = {}
    for v in result.get("verdicts", []):
        st = v.get("stages") or {}
        if not st or v.get("passed"):
            continue
        if not all(isinstance(st.get(gname), dict) and st[gname].get("passed") is True
                   for gname in _validity):
            continue
        failed_power = sorted(gname for gname in _power
                              if not (isinstance(st.get(gname), dict)
                                      and st[gname].get("passed") is True))
        if not failed_power:
            continue
        params = _params_by_cell.get(v["cell"], {})
        sel = _cure_selector(str(v.get("family") or ""), params or {})
        if sel is None:
            continue          # never guess a selector; an unnamed window cannot be enrolled
        cure_rows[f"external.{v['cell']}"] = {
            "hunt": "external_discoveries",
            "cell": v["cell"], "sym": v["sym"], "days": v["days"],
            "failed_power_gates": failed_power,
            "validity_pass": True,
            "promotion_authority": False,
            "gates": st,
            "listed_at": datetime.now(UTC).isoformat(),
            "shadow_spec": {"symbol": v["sym"], "selector": sel,
                            "family": v.get("family", "session_range_breakout"),
                            "is_universe": True, "hunt": "external_discoveries",
                            "condition": None, "params": dict(params or {})},
        }
    (REPORTS / "POWER_CURE_CANDIDATES.json").write_text(json.dumps({
        "gate_policy": ATTESTATION,
        "note": ("validity-pass, power-deficient cells eligible to gather forward evidence. "
                 "NOT certificates and never promotable on their own: the promoter applies the "
                 "forward cure thresholds before anything is promoted."),
        "swept_at": datetime.now(UTC).isoformat(),
        "n": len(cure_rows),
        "candidates": cure_rows,
    }, indent=1, default=str), "utf-8")
    print(f"power-cure candidates: {len(cure_rows)} validity-pass cell(s) eligible to gather "
          f"forward evidence -> POWER_CURE_CANDIDATES.json")

    # NEVER SHRINK (2026-08-26, the certifier wipe): merging can only grow this file; a sweep
    # that certified nothing preserves what stands, because re-running a gauntlet is not
    # revoking a pass.
    if len(survivors_all) < n_before:
        print(f"REFUSING to write: merge would shrink {n_before} -> {len(survivors_all)}")
        return
    # NEVER WRITE EMPTY (2026-08-27): a zeroed input file sails through the shrink check as
    # 0 -> 0, and this run then re-publishes the wipe with its own signature -- observed on the
    # desk box, healed only because the moneypath fence restored canon between runs. An empty
    # survivors file is never a verdict; if nothing has ever certified there is nothing to write.
    if not survivors_all:
        print("REFUSING to write an EMPTY canon: 0 survivors is a missing input, not a verdict.")
        return

    # PURGE UNCASHABLE ROWS ON EVERY WRITE, NOT ONCE BY HAND (L1.49).
    #
    # This block MERGES into the survivor dict it loaded, so a row minted before gate 0 learned to
    # refuse untradeable symbols lives forever -- nothing here ever removes one. Eight such rows
    # (six AFG, two AFL, one 13:07 pass on symbols absent from the registry with no H1 parquet)
    # were retired BY HAND on 2026-09-03 and came back FIVE times: the authority ratchet sees the
    # count fall below its floor and restores the file from canon or git, which is exactly what
    # that ratchet is for and exactly wrong here, because these rows are not lost evidence -- they
    # are certificates the desk can never cash. Retiring downstream of a writer that re-merges
    # them is a race the writer always wins.
    #
    # Doing it HERE ends it: the gauntlet runs hourly and holds the pen, so no restorer outlasts
    # it. `symbol_is_tradeable` is the same predicate gate 0 already applies to new candidates --
    # this simply stops the file grandfathering rows that predate it.
    #
    # NOT A DELETION. They move to `retired_certificates` with the reason that disqualified them,
    # which is the explicit revocation record the authority ratchet accepts as grounds for a floor
    # to fall (check_authority_ratchet.REVOCATION_KEYS). Dropping them silently would read to that
    # ratchet as evidence vanishing -- the alarm it exists to raise.
    # Correction: eligibility for a NEW test is not proof for revoking an EXISTING result.
    # A missing host cache must not erase every certificate on the Windows box. Require explicit
    # venue restriction below; native data and promotion guards still govern execution.
    retired = dict(old_doc.get("retired_certificates") or {})
    if meta:
        stamp = datetime.now(UTC).isoformat()
        for key in list(survivors_all):
            sym = str((survivors_all[key] or {}).get("sym") or "")
            why = certificate_retirement_reason(sym, meta)
            if why:
                row = dict(survivors_all.pop(key) or {})
                row["retired_at"] = stamp
                row["retired_reason"] = why
                retired[key] = row
        if retired:
            print(f"purged {len(retired)} uncashable certificate(s) to retired_certificates")

        # THE SAME PREDICATE, THE OTHER WAY. A certificate retired because its symbol was not
        # tradeable is retired on a fact about the UNIVERSE, not about the certificate -- and the
        # universe is a file that has already been measured collapsing to a 23-symbol stump
        # (2026-09-04; `universe.json.stump-20260904` is still on the box). On that day this
        # block found ~60 certificates on symbols the stump did not carry and retired every one,
        # correctly by its rule; the registry was restored the same day and the certificates
        # never were. MEASURED 2026-09-08: canon 66 rows in the repo, 5 on the box's board, 40
        # forward clocks RETIRED_ORPHAN because "no engine enrols" a certificate that is sitting
        # in `retired_certificates` with a reason that stopped being true four days ago.
        #
        # A purge with no restore turns a transient outage in one input into a permanent loss of
        # evidence that took weeks of forward time to earn. So: every retired row is re-asked the
        # question that retired it, on every pass, and one whose reason no longer holds goes
        # back -- with its gates record intact, and stamped, so the round trip is visible. The
        # recertify step re-judges the library under the CURRENT policy, so a restored row that
        # only ever passed on an older cost model fails there, at the door, as it should.
        # `forward_reconcile` revives an orphaned clock whose certificate returns, so the clocks
        # follow the certificates back without a hand on anything.
        #
        # Only rows retired by THIS predicate are restored. A row retired for any other reason
        # stays retired; a row without a full gates record stays retired.
        restored: list[str] = []
        for key, row in list(retired.items()):
            if not isinstance(row, dict) or not all_ten_pass(row.get("gates")):
                continue
            why_retired = str(row.get("retired_reason") or "")
            sym = str(row.get("sym") or "")
            if not sym or key in survivors_all:
                continue
            ok_now, _why_now = symbol_is_tradeable(sym, meta)
            if not ok_now:
                continue
            back = dict(row)
            back["restored_at"] = stamp
            back["restored_from"] = {"retired_at": back.pop("retired_at", None),
                                     "retired_reason": back.pop("retired_reason", None)}
            survivors_all[key] = back
            del retired[key]
            restored.append(f"{key} ({why_retired[:40]})")
        if restored:
            print(f"restored {len(restored)} certificate(s) whose retirement reason no longer "
                  f"holds: {', '.join(restored[:8])}" + (" ..." if len(restored) > 8 else ""))

    doc = dict(old_doc)
    if retired:
        doc["retired_certificates"] = retired
        doc["revoked_at"] = datetime.now(UTC).isoformat()
    doc.update({
        "n": len(survivors_all),
        "gate_policy": ATTESTATION,
        "survivors": survivors_all,
        "note": "UNIVERSAL 10-GATE PASS ONLY.",
        "swept_at": datetime.now(UTC).isoformat(),
    })
    surv_path.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
    print(f"Updated UNIVERSAL_SURVIVORS.json: {len(survivors_all)} total "
          f"({len(survivors_all) - n_before:+d})")

    # FILE THE CLAIM. Every other certified producer writes SURVIVORS_LEDGER.json alongside the
    # survivor file (universal_gate, survivor_publication, ug_remote); this one never did, and it
    # is the producer of the `external.*` lane. Measured 2026-08-27: 23 survivors, 1 claim -- 22
    # `external.*` passes with no ledger row, the ledger two days stale while the survivor file
    # was rewritten that morning. desks/mt5/CLAUDE.md makes this ledger a binding session-start
    # read ("count them and act"), so a session obeying it saw ONE pipeline claim while
    # twenty-three certificates stood and seventeen were already on forward clocks. A survivor
    # invisible to the ledger is a survivor nobody is required to action.
    # Merge, never replace: another producer may have published while this sweep was running,
    # exactly as the survivor merge above already guards.
    ledger_path = REPORTS / "SURVIVORS_LEDGER.json"
    claims: dict = {}
    if ledger_path.exists():
        try:
            loaded = json.loads(ledger_path.read_text("utf-8")).get("claims")
            claims = loaded if isinstance(loaded, dict) else {}
        except (OSError, ValueError):
            # A torn ledger must not be silently replaced by this run's rows alone -- that would
            # erase every other lane's claims. Report and leave it for repair.
            print("REFUSING to file claims: SURVIVORS_LEDGER.json exists but is unreadable")
            return
    now_iso = datetime.now(UTC).isoformat()
    for k, v in survivors_all.items():
        claims[k] = {**v, "status": "UNIVERSAL", "updated_at": now_iso}
    ledger_path.write_text(json.dumps({"n": len(claims), "claims": claims},
                                      indent=2, default=str), encoding="utf-8")
    print(f"SURVIVORS_LEDGER.json: {len(claims)} claim(s)")


def _cli_main() -> int:
    global _REPRO
    import argparse

    ap = argparse.ArgumentParser(
        description="The canonical ten-gate sweep. With --only it re-runs ONE cell and writes no "
                    "certificate -- the independent-reproduction path.")
    ap.add_argument("--only", default=None,
                    help="substring of a cell key (SYM.family.params-json) restricting the "
                         "docket. Implies reproduction: no authority file is written.")
    ap.add_argument("--report-to", default=None,
                    help="where reproduction writes findings "
                         "(default reports/reproduction_<stamp>.json)")
    args = ap.parse_args()

    if args.only:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        _REPRO = {"only": args.only,
                  "report_to": args.report_to or str(REPORTS / f"reproduction_{stamp}.json")}

    from research.job_lock import exclusive_job

    # Headroom from the MEASURED peak on 2026-08-28 (1926MB RSS), not a guess -- but a
    # FIRST estimate all the same: tighten it from observed successful runs, never from
    # another guess. Below this the box cannot fit the job beside the live terminal.
    # A SEPARATE LOCK NAME. Reproduction writes no authority file, so it is not a duplicate of
    # the certifying sweep and must not be refused while one runs -- but it is still heavy.
    # ONE CELL IS NOT A DOCKET: 1200MB is the measured peak of a sweep over thousands of cells,
    # and asking for it made every reproduction stand down on admission and report UNMEASURED
    # (rc=75) -- honest, and useless, because a reproducer that is never admitted checks nothing.
    _job = "external_gauntlet_repro" if _REPRO is not None else "external_gauntlet"
    # THE ASK IS THE THROTTLE. MEMORY_BUDGET_MB is what the sweep will hold; asking the box for
    # anything less lets it in on a false statement, anything more refuses it for room it will
    # not use. (`exclusive_job` still corrects the ask upward by the p75 of recorded peaks.)
    _need = 300 if _REPRO is not None else int(MEMORY_BUDGET_MB)
    with exclusive_job(_job, need_mb=_need) as acquired:
        if not acquired:
            return 75
        main()
        return 0


if __name__ == "__main__":
    raise SystemExit(_cli_main())
