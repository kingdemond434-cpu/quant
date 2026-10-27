"""Run the canonical sequential 10-gate gauntlet on external discovery survivors.

Reads survivors from external backtest, builds daily R matrix,
rejects failed economic priors at gate 1, then computes program-level PBO + SPA and the
remaining gates for candidates that can still survive. A gate-1 reject is a measured verdict,
not an untested disappearance; doing hours of downstream work after a terminal gate failure is
compute theatre and prevents fresh candidates from reaching the same machinery.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import math
import os
import sys
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar, cast

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

from mt5desk import cell_modifiers, families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402
from mt5desk.universe_registry import TIMEFRAME_MINUTES as _TF_MINUTES  # noqa: E402
from research.frontier_identity import cell_id, economic_prior  # noqa: E402
from research.survivor_publication import (  # noqa: E402
    unrunnable_reason as _certificate_refusal,
)

from libs.data.pit import is_stamped  # noqa: E402
from libs.research.hypothesis_graph import (  # noqa: E402
    node_id_for_spec,
    record_gauntlet_verdicts,
)
from libs.validation.cpcv import CPCV  # noqa: E402
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio  # noqa: E402
from libs.validation.errors import ValidationError  # noqa: E402
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
#: THE GAUNTLET'S OWN CONSTANT FOR THE NUMBER OF GATES A CERTIFICATE MUST PASS. With the DSR bar
#: above and the lockbox fraction (research.gate_policy.LOCKBOX_FRAC) it is one of the three rules
#: the Tier S constitution owns (S01); all three stand when the constitution cannot be read.
GATES_REQUIRED = 10


def constitution_thresholds(lockbox_frac: float) -> dict[str, Any]:
    """The thresholds this sweep applies, from the Tier S constitution IN FORCE (S01).

    `libs/tiers/truth_kernel.gauntlet_thresholds` reads docs/research/tier_s_constitution.json
    and tier_s_ratifications.jsonl: the sealed default, or a live file that is SEALED, TIGHTENED
    or principal-RATIFIED. A rule can only TIGHTEN the constant here (a higher DSR bar, more gates,
    a larger held-out share) unless the principal ratified the rule set that loosens it, and an
    unreadable constitution -- or an unimportable kernel -- leaves exactly the current constants:
    DSR_THRESHOLD, GATES_REQUIRED and the gate policy's lockbox fraction `lockbox_frac`."""
    try:
        from libs.tiers.truth_kernel import gauntlet_thresholds
        return gauntlet_thresholds(BASE, dsr_threshold=DSR_THRESHOLD,
                                   gates_required=float(GATES_REQUIRED),
                                   lockbox_min_fraction=float(lockbox_frac))
    except Exception as exc:
        return {"status": "UNREADABLE", "hash": None, "dsr_threshold": DSR_THRESHOLD,
                "gates_required": float(GATES_REQUIRED),
                "lockbox_min_fraction": float(lockbox_frac),
                "why": {"all": f"constants ({type(exc).__name__}: {exc})"}}

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
    # WEEKEND MAX, SESSION MINIMUM (2026-09-16). Friday 21:00 -> Sunday 21:00 UTC nothing trades,
    # the gateway needs no core and no live capital is at risk, so every core goes to the judge.
    # In session the terminal, the gateway and the hourly cycle keep SESSION_RESERVED_CORES for
    # themselves; measured on the trading box (18 cores, 98 GB) that is 15 workers in session
    # and 18 at the weekend, against 12 before. The memory bound still applies to both.
    return max(1, min(cores if market_closed() else cores - SESSION_RESERVED_CORES, by_mem))


#: Cores the gauntlet leaves alone while the market is open: the terminal, the gateway pass and
#: the hourly cycle each need one to stay on their clocks.
SESSION_RESERVED_CORES = int(os.environ.get("GAUNTLET_SESSION_RESERVED_CORES", "3"))


def market_closed(now: datetime | None = None) -> bool:
    """True inside the weekly FX close, Friday 21:00 UTC to Sunday 21:00 UTC."""
    t = now or datetime.now(tz=UTC)
    wd, h = t.weekday(), t.hour
    return (wd == 4 and h >= 21) or wd == 5 or (wd == 6 and h < 21)


WORKERS = _worker_count()

# Joblib/loky otherwise shells out to the removed/deprecated ``wmic`` command from each spawned
# worker to rediscover physical core count. On the production Windows box those probes were
# interleaved hundreds of times into the judge log and some failed at CreateProcess under load.
# The judge has already computed its stricter CPU+memory ceiling; publish it so downstream
# sklearn/joblib calls reuse the same number instead of spawning unrelated hardware probes.
# An explicit operator value still wins.
os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(WORKERS))


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


def _stress_costs(base: Costs, sym: str, row: dict, mult: float) -> Costs:
    """The stress arm on the SAME surface as the base arm (table x mult, floored at hour p90)."""
    from research.entry_hour_cost import stress_costs
    return stress_costs(base, sym, row, mult)


def daily_series(df: pd.DataFrame, sigs: list, costs: Costs) -> pd.Series:
    res = run_backtest(df, sigs, costs)
    # ONE ROW PER TRADE, THEN SUMMED PER DAY. This was a dict keyed by entry date, so a second
    # trade on the same day OVERWROTE the first before the groupby ever saw it: only the last
    # trade of each day survived, and on pure noise a multi-trade family read +0.46 R/day against
    # a true +0.018 R/trade (test_mass_screen.py). Every gate downstream judged that biased series.
    trades = list(res.trades)
    s = pd.Series([float(t.r_multiple) for t in trades],
                  index=[pd.Timestamp(t.entry_time).date() for t in trades], dtype=float)
    daily = s.groupby(level=0).sum()
    daily.attrs["geometry_rejections"] = getattr(res, "geometry_rejections", [])
    daily.attrs["geometry_rejection_count"] = len(daily.attrs["geometry_rejections"])
    daily.attrs["signal_count"] = getattr(res, "signal_count", len(sigs))
    # A shard retains thousands of series. Keep the full count and digest, with
    # bounded examples, rather than retaining every unfilled signal in memory.
    daily.attrs = _cache_series_metadata(daily)
    return daily


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
    """Replay bars on their native clock, from parquet or the promotion-authority terminal.

    The trading box intentionally does not duplicate every broker chart into this checkout.
    Refusing those charts made the gauntlet report zero eligible cells while shadow could replay
    the same rules from Fusion.  The terminal fallback is deliberately strict: only a native
    source carrying promotion authority is accepted, and research hosts without MT5 still fail
    closed.
    """
    key = (str(sym), str(timeframe).upper())
    if key in _FRAME_CACHE:
        _FRAME_CACHE.move_to_end(key)
        return _FRAME_CACHE[key]
    pq = UNI / f"{key[0]}_{key[1]}.parquet"
    if not pq.exists():
        frame = _live_frame(key[0], key[1])
        if frame is None:
            return None
    else:
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


#: (sym, chart) -> the data-day a cell on that chart is keyed to, read ONCE per process.
#:
#: WHY (2026-10-20, box sweep 23324). Every build-loop pass reads the cell's bars only to learn
#: `frame.index[-1]` for the cache key, and the frame cache holds 1.3m rows -- one M1 chart, two
#: M5 ones. The docket order is not symbol-contiguous (bucket and cursor keys come first), so a
#: shard re-read a parquet for nearly every spec: 14 shards spent 4,383-4,579 s each re-loading
#: ~450 cached cells and deferring ~21.5k cells the budget had already ruled out, 4,964 s of
#: wall clock a sweep, every sweep. The key needs a DAY, not a frame. Read once, the same day.
_LAST_DAY: dict[tuple[str, str], object] = {}


def _index_last_day(pq: Path):
    """The last bar's day from the parquet's INDEX COLUMN ALONE, or None whenever that read is not
    exactly `families._h1(pd.read_parquet(pq)).index[-1].normalize()`: a single datetime index
    column, non-empty, already in order (so `_h1`'s sort and de-duplication keep the last stamp
    last, and its resample keeps it inside the same day), converted to UTC as `_h1` converts it."""
    try:
        import pyarrow as _pa
        import pyarrow.parquet as _pq
        pf = _pq.ParquetFile(pq)
        cols = (pf.schema_arrow.pandas_metadata or {}).get("index_columns") or []
        if len(cols) != 1 or not isinstance(cols[0], str):
            return None
        # A TIMESTAMP column only: `_bars_for` refuses an int or string index (it is not a
        # DatetimeIndex), and `pd.DatetimeIndex` would happily parse one into a day.
        if not _pa.types.is_timestamp(pf.schema_arrow.field(cols[0]).type):
            return None
        idx = pd.DatetimeIndex(pf.read(columns=[cols[0]]).column(0).to_pandas())
    except Exception:
        return None
    if len(idx) == 0 or idx.hasnans or not idx.is_monotonic_increasing:
        return None
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    return idx.as_unit("ns")[-1].normalize()


def _cell_last_day(sym: str, timeframe: str = "H1"):
    """`_bars_for(sym, timeframe).index[-1].normalize()`, or None where `_bars_for` finds no bars --
    once per (sym, chart) per process. A frame already in the frame cache is read from there, as
    `_bars_for` would; otherwise the parquet's index column alone; anything else (no parquet, the
    terminal fallback, an unsorted or non-datetime index) goes through `_bars_for` itself."""
    key = (str(sym), str(timeframe).upper())
    if key in _LAST_DAY:
        return _LAST_DAY[key]
    day = None
    pq = UNI / f"{key[0]}_{key[1]}.parquet"
    if key not in _FRAME_CACHE and pq.exists():
        day = _index_last_day(pq)
    if day is None:
        frame = _bars_for(key[0], key[1])
        day = None if frame is None or len(frame) == 0 else frame.index[-1].normalize()
    _LAST_DAY[key] = day
    return day


def _chart_present(sym: str, timeframe: str = "H1") -> bool:
    """`_bars_for(sym, timeframe) is not None`, answered from the parquet's index when it exists.

    GATE 0 ASKED THIS WITH A WHOLE FRAME (2026-10-20, judge plan phase). Every non-H1 spec read
    its chart through `_bars_for` to learn only whether it exists, and the frame cache holds one
    M1 or two M5 charts, so a docket that is not symbol-contiguous re-read a parquet for nearly
    every intraday spec -- serial, before `_build_t0`, in the part of "plan" no budget bounds.
    A parquet on disk is answered by `_cell_last_day` (its index column, once per chart, the
    same None-or-day `_bars_for` gives); no parquet still goes through `_bars_for` exactly as
    before, so the terminal fallback is asked per spec as it always was."""
    if (UNI / f"{sym}_{str(timeframe).upper()}.parquet").exists():
        return _cell_last_day(sym, timeframe) is not None
    return _bars_for(sym, timeframe) is not None


#: WHERE THE PLAN IS, FOR WHOEVER IS WATCHING (2026-10-20). Phase "plan" covered the docket read,
#: gate 0, the preflight, the cache prune, the order, novelty, the yield allocation and the whole
#: pre-warm pool, and said nothing until the pool's closing line -- so a plan two hours in could
#: not be told from a hung one. The launcher sets this to a callable; each long plan loop reports
#: its step and counts through `_plan_progress`. REPORT-ONLY: it reads no outcome, a failing hook
#: is swallowed, and with no hook (every caller but the launcher) it costs one `is None` test.
PLAN_PROGRESS_HOOK: Any = None
#: Seconds between progress reports from inside a loop; a step change always reports.
PLAN_PROGRESS_EVERY_S = 15.0
_PLAN_PROGRESS_LAST: list[float] = [0.0]


def _plan_progress(step: str, *, force: bool = False, **counts: Any) -> None:
    hook = PLAN_PROGRESS_HOOK
    if hook is None:
        return
    now = time.time()
    if not force and now - _PLAN_PROGRESS_LAST[0] < PLAN_PROGRESS_EVERY_S:
        return
    _PLAN_PROGRESS_LAST[0] = now
    try:
        hook(step, **counts)
    except Exception:
        return  # a progress report is a report; planning never stops for it


def _unreadable_chart(exc: BaseException) -> bool:
    """True when `exc` is an input that could not be READ -- an I/O error or pyarrow refusing a
    file's bytes -- rather than a defect in the code that builds a cell, or a resource fault.

    WHY (audit of the plan phase, 2026-10-21). `_chart_present` and `_cell_last_day` answer from
    the parquet's index column alone, so a file whose index is intact and whose body is corrupt
    reads PRESENT, and the first full read is `build_cell` -> `_bars_for` -> `pd.read_parquet`,
    inside the build loop. That raised uncaught and took the whole shard (every spec on it) down
    with one bad file. A read failure is a fact about the cell's DATA, so it is named on that
    cell; anything else still raises exactly as before, so a code defect is never filed as data.

    NEVER A RESOURCE FAULT (audit of 602887dc). Out of memory (`MemoryError`, which pyarrow's
    `ArrowMemoryError` is) and a file another process holds (`PermissionError`, a locked file on
    Windows) say nothing about the data: parking the cell would file a passing fault as a
    verdict, so both raise as they always did.

    NEVER A TRANSIENT FAULT EITHER (v2.2, audit of 25d1fd22). `TimeoutError` and
    `ConnectionError` are OSErrors, so the rule above filed a share timing out or a dropped
    network mount as the chart's data. They are a passing fault: they raise, and the pool's
    worker files them as ERROR, which is not terminal."""
    try:
        import pyarrow as _pa
    except ImportError:                                    # pragma: no cover - the box has it
        _pa = None
    if isinstance(exc, (MemoryError, PermissionError, TimeoutError, ConnectionError)):
        return False
    if _pa is not None and isinstance(exc, getattr(_pa, "ArrowMemoryError", ())):
        return False
    if isinstance(exc, OSError):
        return True
    return _pa is not None and isinstance(exc, _pa.ArrowException)


def _unreadable_why(sym: str, tf: str, exc: BaseException) -> str:
    """The label for a read failure, naming WHICH input failed, never guessing it.

      * a missing file (`FileNotFoundError`, e.g. a COT or events input): INPUT_MISSING, with
        the file it named;
      * the cell's own chart ABSENT when re-checked (v2.2: `pq.exists()` first, so a file gone
        since the plan read it is never re-read into an UNREADABLE_CHART): INPUT_MISSING,
        naming the chart;
      * the cell's own chart, re-read whole here, refusing its bytes: UNREADABLE_CHART;
      * otherwise the chart reads and the failure was another input (a peer chart read for
        residuals, a side file): UNREADABLE_INPUT -- never labelled as this chart's body."""
    detail = f"{type(exc).__name__}: {str(exc)[:200]}"
    if isinstance(exc, FileNotFoundError):
        return f"INPUT_MISSING: {getattr(exc, 'filename', None) or 'an input file'} ({detail})"
    pq = UNI / f"{sym}_{str(tf).upper()}.parquet"
    if not pq.exists():
        return f"INPUT_MISSING: the {tf} chart {pq.name} is absent ({detail})"
    try:
        pd.read_parquet(pq)
    except Exception as own:
        if _unreadable_chart(own):
            return (f"UNREADABLE_CHART: the {tf} parquet {pq.name}'s index reads but its body "
                    f"does not ({type(own).__name__}: {str(own)[:200]})")
        raise
    return (f"UNREADABLE_INPUT: the {tf} chart reads whole, so the failure was another input "
            f"this cell needs ({detail})")


def _built_day(obj: dict, keyed):
    """The day a FRESH build's own frame ends on, else `keyed`.

    `_cell_last_day` answers once per process (and from the pool's plan in a shard), but
    `build_cell` re-reads the chart. If the parquet advanced in between, the cell was built
    through D+k while keyed and trimmed as D -- day-D exits leaking into a series keyed as D.
    The base judge took both from one frame; so does this: a fresh build is keyed and trimmed
    by the frame it was built from. A cache HIT never comes here: its series is the build that
    was stored under its own key."""
    try:
        df = obj.get("df")
        if isinstance(getattr(df, "index", None), pd.DatetimeIndex) and len(df):
            return df.index[-1].normalize()
    except Exception:
        pass
    return keyed


def _h1_for(sym: str):
    """The symbol's HOURLY bars. Kept by name: callers outside this module ask for H1 by name."""
    return _bars_for(sym, "H1")


def _frame_for(sym: str, family: str, params: dict | None = None):
    """Load the cell's authorized clock; never silently resample an M5 hypothesis to H1."""
    return _bars_for(sym, timeframe_of(params, family))


#: Why the last `build_cell` call returned None, when it knows. The sweep prints and records this
#: instead of "parquet missing or build failed", which named the wrong cause for every one of them.
LAST_BUILD_FAILURE: str | None = None


def _build_failed(why: str) -> None:
    global LAST_BUILD_FAILURE
    LAST_BUILD_FAILURE = why
    return None


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
    global LAST_BUILD_FAILURE
    LAST_BUILD_FAILURE = None
    from mt5desk.legacy_family_inputs import RAW_COT_FAMILIES, input_preflight, legacy_inputs
    why = input_preflight(family, params)
    if why:
        return _build_failed(why)
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
        return _build_failed(f"no {timeframe} bars for {sym}")
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
        return _build_failed(f"no implementation of family {family!r} in families or "
                             "families_orthogonal")
    # Reconstruct runtime-only data from the serializable candidate identity. Previously the
    # orthogonal sweep persisted `{}` for every peer/tape/macro/COT family, and discovered
    # cross-asset features were rebuilt without `extra`; both paths therefore produced zero
    # signals after apparently successful discovery. One producer -> one exact executable.
    call_params = dict(params or {})
    try:
        from research import orthogonal_sweep as inputs

        if family == "usd_session_shock" or family in RAW_COT_FAMILIES:
            extra, why = legacy_inputs(sym, family, params, inputs._bars)
            if extra is None:
                return _build_failed(why)
            call_params.pop("fx_symbol", None)
            call_params.pop("input_symbol", None)
            call_params.pop("input_source", None)
            call_params.update(extra)
        elif family == "carry":
            call_params.pop("input_symbol", None)
            call_params["symbol"] = sym
        elif family in {"relative_value", "correlation_regime"}:
            peer_symbol = call_params.pop("peer_symbol", None)
            call_params["peer"] = (inputs._bars(str(peer_symbol), timeframe)
                                   if peer_symbol else None)
            # NO PEER IS A BUILD FAILURE BY NAME, NOT A CELL THAT NEVER FIRES (2026-09-30). The
            # family returns [] on `peer=None`, so a spec naming no peer -- 4,004 docket rows from
            # discovery_compiler -- built "successfully", produced no series, and was filed as
            # UNKNOWN / never_fires, then parked as an unrunnable SPEC. The compiler now names the
            # peer (`complete_inputs`); these refusals name what is missing so the rest route to
            # the bar fetcher (a peer with no bars) or stay parked with the true reason.
            if not peer_symbol:
                return _build_failed(f"{family}: no peer_symbol on the candidate")
            if call_params["peer"] is None:
                return _build_failed(f"no {timeframe} bars for peer {peer_symbol}")
        # A TRIANGLE WITH NO LEGS IS A BUILD FAILURE BY NAME, exactly as the peer case above
        # (2026-09-30). `family_triangle` returns [] when a leg is unnamed or has no bars, so the
        # cell built "successfully", produced no series and was filed as UNKNOWN / never fires.
        # Both legs are loaded here on the cell's own chart and handed over as frames.
        elif family == "triangle":
            for _leg in ("leg_b", "leg_c"):
                _leg_sym = call_params.get(f"{_leg}_symbol")
                if not _leg_sym:
                    return _build_failed(f"triangle: no {_leg}_symbol on the candidate")
                _leg_bars = inputs._bars(str(_leg_sym), timeframe)
                if _leg_bars is None:
                    return _build_failed(f"triangle leg missing: no {timeframe} bars for "
                                         f"{_leg_sym}")
                call_params[_leg] = _leg_bars
        # `pca_residual` TAKES THE SAME `factors` ARGUMENT and was absent from this branch, so
        # every one of its cells rebuilt here with factors=None and hit its own four-factor
        # refusal -- the identical defect `family_inputs` records having fixed on ITS side of the
        # same mapping ("301 cells failed to build with 'parquet missing or build failed', a
        # message that names the wrong cause"). Two implementations of one rule, and only one of
        # them was repaired.
        elif family in {"cross_asset_residual", "pca_residual"}:
            factor_symbols = call_params.pop("factor_symbols", [])
            loaded = [(str(s), inputs._bars(str(s), timeframe)) for s in factor_symbols]
            if not loaded or any(d is None for _s, d in loaded):
                # A partial basket is a different model.  Accepting USDX while silently dropping
                # the named UST10Y leg minted clocks that looked ACTIVE but had never produced a
                # signal even historically.  Fail the build instead of testing/certifying a
                # strategy whose identity differs from the candidate.
                missing = [s for s, d in loaded if d is None] or ["factor_symbols (none named)"]
                return _build_failed(f"factor basket incomplete: no {timeframe} bars for "
                                     f"{', '.join(missing)}")
            call_params["factors"] = [d for _s, d in loaded]
        # THE DRIVER IS DATA, NOT A PARAMETER (2026-09-30). `family_lead_lag` trades the target
        # after the DRIVER moved, and refuses (returns []) without the driver's bars. There was no
        # branch here, so `driver` was never loaded and every lead_lag cell built with ZERO
        # signals and was judged as though the market had said no -- measured on GBPUSD<-EURUSD
        # H1 at the family's defaults: 0 signals, 2,878 with the driver handed over. Same bar
        # store and same chart as the peer and factor branches above; `driver_symbol` stays on
        # the call because the family takes it (it names the driver in the signal tag), and a
        # named driver with no bars is a failed build, never a silent zero.
        elif family == "lead_lag":
            driver_symbol = call_params.get("driver_symbol")
            if not driver_symbol:
                return _build_failed("lead_lag: no driver_symbol on the cell")
            driver = inputs._bars(str(driver_symbol), timeframe)
            if driver is None:
                return _build_failed(f"lead_lag driver missing: no {timeframe} bars for "
                                     f"{driver_symbol}")
            call_params["driver"] = driver
        elif family in {"liquidity_regime", "orderflow_imbalance"}:
            call_params.pop("input_source", None)
            spread, flow = inputs._tape_series(sym, h1.index, timeframe)
            call_params["spread_series" if family == "liquidity_regime" else "flow"] = (
                spread if family == "liquidity_regime" else flow
            )
        # THE VENUE'S SURFACE IS DATA, NOT A PARAMETER (2026-09-30). `family_execution_state`
        # refuses without the per-symbol spread/activity surface by weekday-hour, and there was
        # no branch here, so every execution_state cell built with ZERO signals. Loaded by the
        # same reader `family_inputs.resolve` uses for the forward clock, so the judge and the
        # clock condition on the same map. An absent surface is a failed build BY NAME.
        elif family == "execution_state":
            call_params.pop("input_source", None)
            surface = inputs._surface_for(sym)
            if not surface:
                return _build_failed(f"execution_state: no microstructure surface for {sym} in "
                                     f"{inputs.MICROSTRUCTURE_SURFACES.name}")
            call_params["surface"] = surface
        elif family == "macro_conditional":
            call_params.pop("input_source", None)
            call_params["macro"] = inputs._macro_series(h1.index)
        elif family == "cot_positioning":
            call_params.pop("input_source", None)
            call_params["cot"] = inputs._cot_frame(sym)
        # THE FAMILY READS EVENT MAPPINGS FOR ONE SYMBOL (2026-09-30). `_event_index()` is a bare
        # DatetimeIndex and `symbol` was never passed; `family_event_reaction` skips every element
        # without `.get` and refuses an empty `symbol`, so every event_reaction cell built with
        # ZERO signals. The index is handed over as the {symbol, at} mappings the family's
        # contract names, by the same helper `family_inputs.resolve` uses for the forward clock,
        # with `clock="utc"` because the calendar is UTC and the bar index is broker time: a raw
        # comparison would enter two to three hours BEFORE the release. No calendar is a failed
        # build by name, never a silent zero.
        elif family == "event_reaction":
            from mt5desk.family_inputs import events_for_symbol

            call_params.pop("input_source", None)
            events = inputs._event_index()
            if events is None or len(events) == 0:
                return _build_failed("event_reaction: no event calendar vintages on this box")
            call_params["events"] = events_for_symbol(events, sym)
            call_params["symbol"] = sym
            call_params["clock"] = "utc"
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
        return _build_failed(f"input load failed: {type(exc).__name__}: {str(exc)[:200]}")

    # `timeframe` NAMES THE CHART TO LOAD, it is not a family argument -- the same rule
    # `family_inputs.strip_identity_keys` applies to `peer_symbol` and `factor_symbols`. Leaving
    # it in raises TypeError on every family, which the fallback below would then mistake for
    # "this family takes no side" and retry, and the second failure returns None: an entire
    # chart's worth of cells would read as unbuildable.
    call_params.pop("timeframe", None)
    # THE SESSION IS AN IDENTITY KEY, NEVER A FAMILY ARGUMENT (2026-09-16): the same filter the
    # forward clock and the live executor apply in `family_call.signals`, applied here to the
    # replay, so a cell certified inside a session is judged inside it.
    _session = call_params.pop("session", None)
    # THE MINERS' VARIANT KEYS ARE APPLIED, NOT PASSED (`mt5desk.cell_modifiers`): a `regime`,
    # `side_mode` or `entry_timing` handed to a family that does not take it raised TypeError, and
    # 8,939 of 8,941 fresh cells in one sweep died below as "parquet missing or build failed".
    # What cannot be applied honestly is refused BY NAME here, before any compute is spent.
    call_params, _mods = cell_modifiers.split(fn, call_params)
    _refused = cell_modifiers.refusal(_mods)
    if _refused:
        return _build_failed(f"NOT_RUN_MODIFIER: {_refused}")
    side = 1  # both sides tested externally; use LONG default
    try:
        sigs = fn(h1, side=side, **call_params)
    except TypeError:
        try:
            sigs = fn(h1, **call_params)
        except Exception as exc:
            return _build_failed(f"{family} raised {type(exc).__name__}: {str(exc)[:200]}")
    if _session is not None:
        from mt5desk.family_call import session_filter
        sigs = session_filter(list(sigs or []), _session)
    sigs = cell_modifiers.apply(list(sigs or []), h1, _mods)
    # CHARGE THE HOUR THIS CELL FILLS IN. `universe.json` carries ONE median spread per symbol,
    # collapsed at ingest, so every gate has been dividing by a number that averages away the hour
    # structure -- and the families that fill in thin books are exactly the ones that lose by it.
    # Measured 2026-08-29: `overnight_gap_decay` fills at broker hour 01 (signal on the day's first
    # bar, wait_bars=1), where EURZAR spreads measured 1,918 pts against the 310 pooled median. A
    # 3x "stress" on the pooled number is still cheaper than the real fill.
    # The surface is OPTIONAL: without it the pooled median still applies and the basis is
    # recorded, so an undercharge stays visible instead of becoming the silent default.
    # THE HOUR OF ENTRY AND OF EXIT (2026-10-13), from the ONE cost surface: the cost model
    # carries a per-(weekday, hour) spread table and the engine charges a long its entry slot
    # and a short its exit slot. The modal-hour scalar this replaced charged a cell's other
    # hours at its most common one, and its 3x arm at the pooled median again. The helper is
    # not sealed so the rule can be tested and read by every other consumer; see
    # desks/mt5/research/entry_hour_cost.py for the fallback ladder (never zero, never cheaper).
    from research.entry_hour_cost import gauntlet_costs

    costs, cost_basis, hour = gauntlet_costs(sym, meta, sigs, timeframe)
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


def _live_frame(sym: str, timeframe: str = "H1"):
    """Return verified Fusion-native bars, or None; never substitute an untrusted proxy."""
    if os.name != "nt":
        return None
    try:
        # The full gauntlet is a parquet consumer, not a terminal owner. Holding the Fusion
        # research lease around a 45-minute statistical sweep starved the hourly tail refresher,
        # leaving real files 13+ hours stale and blocking forward clocks. Only this rare
        # missing-parquet fallback needs MT5, so lease the terminal for the read itself.
        from research.job_lock import exclusive_job
        from research.h1_source import fetch_h1
        with exclusive_job("fusion_terminal_research_lane", need_mb=0) as terminal_lane:
            if not terminal_lane:
                return None
            bars = fetch_h1(str(sym), datetime(2018, 1, 1, tzinfo=UTC),
                            prefer="MT5", prefer_promotion_authority=True,
                            require_coverage=True,
                            timeframe=str(timeframe).upper())
        if bars is None or bars.n <= 0 or not bars.promotion_authority:
            return None
        frame = families._h1(bars.df)
        if not isinstance(frame.index, pd.DatetimeIndex) or len(frame) == 0:
            return None
        return frame
    except Exception:
        return None


def modifier_preflight(spec: dict) -> str | None:
    """Name a deterministic modifier refusal without loading bars or runtime inputs."""
    family = str(spec.get("family") or "")
    from mt5desk.legacy_family_inputs import input_preflight

    required_inputs = input_preflight(family, spec.get("params"))
    if required_inputs:
        return required_inputs
    # A MISSING SURFACE IS KNOWN WITHOUT BARS (2026-10-20). `build_cell` loads the cell's chart
    # and only then reads MICROSTRUCTURE_SURFACES.json; sweep 23324 spent 2,441 pre-warm builds
    # learning "no microstructure surface for NOKJPY ..." that one JSON lookup answers. Same
    # reader, same reason text (the converter's NEEDS_MICROSTRUCTURE_SURFACE route matches it),
    # re-read every sweep, so the cell is built the sweep its surface appears.
    if family == "execution_state":
        try:
            from research import orthogonal_sweep as _inputs
            if not _inputs._surface_for(str(spec.get("sym") or "")):
                return (f"BLOCKED_DATA: execution_state: no microstructure surface for "
                        f"{spec.get('sym')} in {_inputs.MICROSTRUCTURE_SURFACES.name}")
        except ImportError:
            pass
    fn = getattr(families, f"family_{family}", None)
    if fn is None:
        try:
            from mt5desk import families_orthogonal as fo
            fn = fo.ORTHOGONAL_FAMILIES.get(family)
        except ImportError:
            fn = None
    if fn is None:
        return (f"BLOCKED_EXECUTOR: no implementation of family {family!r} in families "
                "or families_orthogonal")
    params = dict(spec.get("params") or {})
    try:
        from mt5desk.family_inputs import strip_identity_keys
        params = strip_identity_keys(family, params)
    except ImportError:
        params.pop("timeframe", None)
        params.pop("session", None)
    kwargs, mods = cell_modifiers.split(fn, params)
    refused = cell_modifiers.refusal(mods)
    if refused:
        return refused
    # Plain unsupported kwargs are just as deterministic as unsupported modifiers.  Previously
    # they loaded bars, occupied a pre-warm worker, and only then raised TypeError.  Conserving
    # them here as an explicit NOT_RUN disposition frees the expensive workers for cells that can
    # still reach the ten gates; silently dropping a key would test a different strategy.
    try:
        signature = inspect.signature(fn)
        accepts_kwargs = any(
            p.kind is inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values()
        )
        if not accepts_kwargs:
            unknown = sorted(set(kwargs).difference(signature.parameters))
            if unknown:
                return ("unsupported family parameter(s): " + ", ".join(unknown)
                        + "; refusing rather than testing a different rule")
    except (TypeError, ValueError):
        pass
    return None


_LIVE_H1_AVAILABLE: dict[str, bool] = {}


def _live_h1_available(sym: str) -> bool:
    """True only when the traded Fusion terminal can supply replayable H1 bars.

    The trading box intentionally keeps part of the universe in MT5 rather than duplicating
    every H1 frame under this checkout.  Shadow uses the shared source chain and was replaying
    those bars while gate zero rejected the same symbols solely because a local parquet was
    absent.  A successful broker-native read is equivalent replay evidence; failures remain a
    closed gate.  Non-Windows research hosts never claim this route.
    """
    key = str(sym)
    if key not in _LIVE_H1_AVAILABLE:
        _LIVE_H1_AVAILABLE[key] = _live_frame(key, "H1") is not None
    return _LIVE_H1_AVAILABLE[key]


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
    if not (UNI / f"{sym}_H1.parquet").exists() and not _live_h1_available(sym):
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
    _plan_progress("gate0", force=True, done=0, total=len(specs))
    for _i, spec in enumerate(specs):
        _plan_progress("gate0", done=_i, total=len(specs), eligible=len(eligible),
                       rejected=len(rejected))
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
                if _tf != "H1" and not _chart_present(canon, _tf):
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


#: How strongly the build budget follows measured family yield. 0 spends uniformly (the old
#: behaviour); 1 spends strictly in proportion to the shrunk posterior. Between the two, because
#: a family's yield is an estimate and the desk must keep buying information about the families
#: it has not yet measured well.
YIELD_ALLOCATION_STRENGTH = float(os.environ.get("GAUNTLET_YIELD_STRENGTH", "0.70"))

#: Strength of the Beta prior, in cells. a+b is how many of a family's OWN ruled cells it takes to
#: move it off the house average; a/(a+b) is the house average itself and is MEASURED each sweep
#: rather than declared (`_house_yield`). 100 cells is deliberately slow: `session_range_breakout`
#: earned its 105-per-1,000 on 142 cells, so a family needs a comparable record before the
#: allocator believes an extreme number rather than a lucky one.
YIELD_PRIOR_STRENGTH = 100.0

#: No family may take more than this share of one sweep, however well it has done. The capital
#: allocator has `hard_ceiling` for the same reason and it is not timidity: a yield estimate is
#: drawn from the cells the desk CHOSE to build, so letting the leader take everything closes the
#: loop that would have told it it was wrong. The desk also cannot certify a portfolio out of one
#: family -- n_eff collapses to 1/rho and the E8 barrier is priced on INDEPENDENT mechanisms, so
#: a sweep that produced only session_range_breakout survivors would buy certificates it cannot
#: diversify with.
YIELD_MAX_SHARE = 0.45

#: No family may be squeezed below this share of its own docket, however badly it has done.
#: EXPLORATION IS NOT CHARITY HERE: a family that has ruled 200 cells for zero survivors may still
#: be one parameterisation away from working, and the desk cannot learn that from cells it never
#: builds. It is also the fence against a feedback loop -- starve a family completely and its
#: yield can never update, so a single bad epoch would condemn it permanently.
YIELD_MIN_SHARE = 0.15


#: Gate failures that mean UNDER-POWERED rather than REFUTED. A cell failing only these cleared
#: pbo, cpcv, walk_forward, lockbox, reality_check_spa and stress_costs -- it is a real effect
#: measured on too few observations to clear a bar charging 597 trials.
POWER_ONLY_GATES = frozenset({"deflated_sharpe", "expected_value", "in_sample_screen"})

#: What a power-deficient cell is worth when it has a downstream consumer but that consumer has
#: not yet produced a survivor to measure against.
#:
#: THIS NUMBER IS A BOOTSTRAP AND SAYS SO. It is replaced by measurement the moment the weak-signal
#: lane reports its own conversion (`_combination_credit` reads it), because a declared constant
#: deciding allocation is exactly what `_family_yield`'s own prior comment warns against. A half
#: credit is the deliberate middle: crediting 1.0 would claim combination converts as reliably as
#: solo certification, which is unmeasured; crediting 0.0 is what the desk did until today, and
#: that is the bug this replaces, not a safe default.
COMBINATION_CREDIT_BOOTSTRAP = 0.5


def _combination_credit(root: Path | None = None) -> float:
    """What one power-deficient cell is worth, MEASURED from the weak-signal lane where possible.

    Survivors the combination lane produced, per power-deficient member it consumed. Until that
    lane has run and reported, the bootstrap stands and the caller is told which it used.
    """
    base = root or REPORTS.parent
    try:
        w = json.loads((base / "reports" / "weak_signal_compiler.json").read_text("utf-8"))
    except (OSError, ValueError):
        return COMBINATION_CREDIT_BOOTSTRAP
    members = float(w.get("n_members") or 0.0)
    won = float(w.get("cells_proposed") or 0.0)
    if members <= 0:
        return COMBINATION_CREDIT_BOOTSTRAP
    return max(0.0, min(1.0, won / members))


def _family_yield(root: Path | None = None) -> dict[str, float]:
    """Survivors per RULED cell, per family, shrunk toward the desk's own average.

    Ruled, not judged: a cell the gates could not rule on (`unmeasured` -- under the 60 trading
    days they need) says nothing about the family's productivity, and counting it as a failure
    would condemn exactly the families whose parameterisations need widening rather than
    discarding.
    """
    base = root or REPORTS.parent
    _facts = _report_facts(base)
    if _facts is not None:
        ruled, power_def = dict(_facts["ruled"]), dict(_facts["power_def"])
    else:
        try:
            g = json.loads((base / "reports" / "universal_gates_external.json").read_text("utf-8"))
        except (OSError, ValueError):
            return {}
        ruled, power_def = _yield_counts(g.get("verdicts") or [])
    return _yield_from_counts(base, root, ruled, power_def)


def _yield_counts(rows: Any) -> tuple[dict[str, int], dict[str, int]]:
    """(ruled cells, power-deficient cells) per family from the report's verdict rows."""
    ruled: dict[str, int] = {}
    # POWER-DEFICIENT CELLS ARE OUTPUT, NOT WASTE -- AS OF THE HOUR weak_signals GOT A CLOCK.
    #
    # THIS ALLOCATOR WAS STARVING ITS OWN BEST SUPPLIER. Yield was survivors-per-ruled-cell, and a
    # survivor meant a cell passing all ten gates ALONE. By that definition `pca_residual` scores
    # 0.0 (0 of 230) and `cross_asset_residual` 0.0 (0 of 816), so both were trimmed to the floor.
    # Measured on the trading box 2026-09-14, those same two families are the RICHEST source of
    # cells that failed only on power: pca_residual 131 of 230, the highest rate on the desk.
    #
    # That zero was correct while nothing consumed a power-deficient cell. `weak_signals` now runs
    # hourly and consumes exactly them, so the numerator was measuring the wrong thing the moment
    # that leg landed: it asked "did this family certify alone", when the question allocation turns
    # on is "did this family produce anything a downstream consumer can use". Leaving it would have
    # had the gauntlet defund the combination lane's raw material at the same hour the lane opened.
    #
    # THIS RAISES ALLOCATION, IT DOES NOT CAP ANYTHING (Rule 1). No family's share falls by fiat;
    # the numerator gains a term that was always positive, so families with power-deficient output
    # rise and the total docket built is unchanged. More independent positive-Elog bets inside the
    # same budget is the whole point.
    power_def: dict[str, int] = {}
    for v in rows:
        if not isinstance(v, dict) or v.get("unmeasured"):
            continue
        fam = str(v.get("family") or "")
        if not fam:
            continue
        ruled[fam] = ruled.get(fam, 0) + 1
        stages = v.get("stages") or v.get("gates") or {}
        if not isinstance(stages, dict) or not stages:
            continue
        failed = {k for k, gg in stages.items()
                  if isinstance(gg, dict) and gg.get("passed") is False}
        if failed and failed <= POWER_ONLY_GATES:
            power_def[fam] = power_def.get(fam, 0) + 1
    return ruled, power_def


def _yield_from_counts(base: Path, root: Path | None, ruled: dict[str, int],
                       power_def: dict[str, int]) -> dict[str, float]:
    """The rest of `_family_yield`, unchanged: survivors, combination credit, shrinkage."""
    try:
        s = json.loads((base / "reports" / "UNIVERSAL_SURVIVORS.json").read_text("utf-8"))
    except (OSError, ValueError):
        s = {}
    surv: dict[str, int] = {}
    for val in (s.get("survivors") or {}).values():
        fam = str(((val or {}).get("shadow_spec") or {}).get("family") or "")
        if fam:
            surv[fam] = surv.get(fam, 0) + 1
    credit = _combination_credit(root)
    fams = set(ruled) | set(surv) | set(power_def)

    def _num(f: str) -> float:
        return surv.get(f, 0) + credit * power_def.get(f, 0)
    # THE PRIOR IS THE DESK'S OWN AGGREGATE, MEASURED NOW. A declared constant would go stale the
    # moment the desk got better or worse at converting cells, and would quietly become the thing
    # deciding allocation on a day when every family underperformed it.
    tot_s = sum(_num(f) for f in fams)
    tot_r = sum(ruled.values())
    house = (tot_s / tot_r) if tot_r else 0.0
    pa = max(house, 1e-6) * YIELD_PRIOR_STRENGTH
    pb = YIELD_PRIOR_STRENGTH - pa
    return {f: (_num(f) + pa) / (ruled.get(f, 0) + pa + pb) for f in fams}


def _house_yield() -> float:
    """Survivors per ruled cell across every family -- what an unmeasured family is credited."""
    y = _family_yield()
    return (sum(y.values()) / len(y)) if y else 0.0


#: CELLS PER UNMEASURED AXIS THE SWEEP BUILDS NO MATTER WHAT ITS YIELD SAYS.
#:
#: WHY A YIELD ALLOCATOR CANNOT FIX BREADTH ON ITS OWN, and this is the whole argument. Yield is
#: survivors per ruled cell. Measured 2026-09-14, every one of the desk's 58 certificates is H1
#: and asia -- one chart, one session -- and the per-chart record reads:
#:
#:     judged   H1 7,193 | H4 40  D1 39  M15 36  M30 34  M5 33  M1 30
#:     passed   H1    10 | everything else 0
#:
#: So every non-H1 chart has a measured yield of EXACTLY ZERO, and a yield-keyed allocator hands
#: zero-yield axes the floor and moves on. They have produced no survivor because they have barely
#: been built, and they will barely be built because they have produced no survivor. Exploitation
#: cannot discover an axis it has no data on; it is the same self-sealing trap as a live sleeve
#: held at zero heat because "capital requires a measured marginal".
#:
#: THIS FLOOR IS ADDITIVE AND TAKES FROM NOBODY (Rule 1, and the standing order on
#: aggressiveness). It APPENDS cells the family trim did not already keep; no family's share is
#: reduced, and nothing currently earning loses a single build. That is affordable because the
#: build budget is not binding -- the sweep reports `n_cells_deferred_build_budget: 0` -- so an
#: unmeasured axis costs compute that was otherwise idle rather than compute that was earning.
#:
#: FORTY IS A SAMPLE, NOT A GESTURE. Below roughly this many cells an axis cannot distinguish "no
#: edge here" from "not asked", so a smaller floor would buy the appearance of exploration and
#: none of its information. An axis that reaches a survivor stops being unmeasured and is
#: thereafter allocated on its measured yield like everything else -- the floor is a door, not a
#: subsidy.
EXPLORATION_MIN_CELLS = int(os.environ.get("GAUNTLET_EXPLORATION_MIN_CELLS", "40"))


def _axis_of(spec: dict) -> tuple[str, str]:
    """(chart, session anchor) -- the two axes on which this desk has no diversity at all.

    Read through `timeframe_of`, the same function `cell_id` uses, so an axis label can never
    disagree with the identity the docket and the gauntlet already share.
    """
    params = dict(spec.get("params") or {})
    try:
        chart = str(timeframe_of(params, str(spec.get("family") or ""))).upper()
    except Exception:
        chart = str(params.get("timeframe") or "H1").upper()
    anchor = "-"
    for k in ("range_start", "selector", "session", "hour", "anchor_hour"):
        if k in params and params[k] is not None:
            anchor = f"{k}={params[k]}"
            break
    if anchor == "-":
        anchor = str(spec.get("selector") or "-")
    return chart, anchor


def _axis_yield(root: Path | None = None) -> dict[tuple[str, str], int]:
    """Survivors per (chart, anchor). An axis absent here has never produced one."""
    base = root or REPORTS.parent
    try:
        s = json.loads((base / "reports" / "UNIVERSAL_SURVIVORS.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[tuple[str, str], int] = {}
    for val in (s.get("survivors") or {}).values():
        spec = (val or {}).get("shadow_spec") or {}
        if not spec:
            continue
        ax = _axis_of(spec)
        out[ax] = out.get(ax, 0) + 1
    return out


def _explore_unmeasured_axes(specs: list[dict], keep: list[dict]) -> tuple[list[dict], dict]:
    """Top `keep` up so every UNMEASURED (chart, anchor) axis gets a real sample this sweep.

    Never removes. Returns the appended cells and a per-axis record of what was added and why,
    which is the missed-growth line the governance requires of any allocation decision.
    """
    measured = _axis_yield()
    kept_ids = {id(s) for s in keep}
    by_axis: dict[tuple[str, str], list[dict]] = {}
    for sp in specs:
        by_axis.setdefault(_axis_of(sp), []).append(sp)
    added: list[dict] = []
    record: dict[str, dict] = {}
    for ax, rows in sorted(by_axis.items(), key=lambda kv: -len(kv[1])):
        have = sum(1 for r in rows if id(r) in kept_ids)
        if measured.get(ax, 0) > 0:
            continue                       # this axis has a survivor: yield governs it
        short = EXPLORATION_MIN_CELLS - have
        if short <= 0:
            continue
        spare = [r for r in rows if id(r) not in kept_ids][:short]
        if not spare:
            continue
        added.extend(spare)
        record[f"{ax[0]}|{ax[1]}"] = {
            "docket": len(rows), "already_kept": have, "added_by_floor": len(spare),
            "survivors_on_this_axis": 0,
            "why": ("unmeasured axis: no survivor has ever been minted here, so its yield is 0 "
                    "and the yield allocator would never build it. Floored so the desk can tell "
                    "'no edge' from 'never asked'."),
        }
    return added, record


#: Families that are ORTHOGONAL BY CONSTRUCTION. A PCA residual is, by definition, the part the
#: common factors do not explain; a relative-value spread is two legs whose shared factor has been
#: differenced away. They are the only families on this desk that attack rho directly.
ORTHOGONAL_FAMILIES = ("cross_asset_residual", "relative_value", "correlation_regime",
                       "pca_residual", "triangle")
#: Cells from those families that MUST be judged each sweep, whatever their yield says.
ORTHOGONALITY_MIN_CELLS = int(os.environ.get("GAUNTLET_ORTHOGONALITY_MIN_CELLS", "60"))


def _stamped_but_unjudged() -> set[str]:
    """Cell ids the sweep STAMPED as seen while recording no verdict for them.

    Read from `universal_gates_external.json`: a verdict row with empty `stages` was never
    computed -- the build budget died before it -- whatever its seen-stamp says. Returning these
    as NEW puts them back at the front of the build order, which is the only way a cell trapped
    behind its own stamp is ever reached again.

    Fails OPEN (empty set) on any read problem: an unreadable report must not silently re-promote
    the whole docket to the front and starve the genuinely-new cells instead.
    """
    _facts = _report_facts(REPORTS.parent)
    if _facts is not None:
        return set(_facts["unjudged"])
    try:
        doc = json.loads((REPORTS / "universal_gates_external.json").read_text("utf-8"))
    except (OSError, ValueError):
        return set()
    return _unjudged_cells(doc.get("verdicts") or [])


def _unjudged_cells(rows: Any) -> set[str]:
    """`_stamped_but_unjudged`'s rule over the report's verdict rows."""
    out: set[str] = set()
    for v in rows:
        if not isinstance(v, dict) or v.get("stages"):
            continue
        try:
            out.add(cell_id({"sym": v.get("sym"), "family": v.get("family"),
                             "params": v.get("params") or {}}))
        except Exception:
            continue
        cid = v.get("cell_id") or v.get("id")
        if isinstance(cid, str) and cid:
            out.add(cid)
    return out


# ---------------------------------------------------------- the report's digest (2026-10-14)
#: THE GATES REPORT IS READ FOR TWO SMALL FACTS AND IT IS 625 MB. `_stamped_but_unjudged` and
#: `_family_yield` (reached twice a sweep through `_house_yield` and `allocate_by_yield`) each
#: `json.loads` the whole of `universal_gates_external.json` -- the previous sweep's report --
#: for a set of cell ids and two per-family counts. The sweep that WRITES the report now derives
#: those facts from the very rows it wrote (each row round-tripped through JSON, so they are what
#: a reader would parse) and records them beside it with the report's SHA-256, size and the
#: identity of the code that derived them. A reader uses the digest only when the report on disk
#: hashes to that SHA-256 and the code is the same; anything else -- no digest, an edited or
#: rewritten report, a release -- falls back to reading the report exactly as before.
REPORT_DIGEST_NAME = "universal_gates_external.digest.json"


def _report_digest_code() -> str:
    """The code the facts are a function of: this file and `cell_id`'s module."""
    h = hashlib.sha256()
    for f in (Path(__file__), BASE / "desks" / "mt5" / "research" / "frontier_identity.py"):
        try:
            h.update(f.read_bytes().replace(b"\r\n", b"\n"))
        except OSError:
            h.update(b"<unreadable>")
    return h.hexdigest()


def _file_sha256(path: Path) -> str:
    with open(path, "rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()


def _report_facts(base: Path) -> dict[str, Any] | None:
    """The digest's facts when it provably describes the report now on disk, else None."""
    report = base / "reports" / "universal_gates_external.json"
    try:
        dg = json.loads((base / "reports" / "gauntlet_cache" / REPORT_DIGEST_NAME)
                        .read_text("utf-8"))
        if (not isinstance(dg, dict) or dg.get("code") != _report_digest_code()
                or dg.get("report_bytes") != report.stat().st_size
                or dg.get("report_sha256") != _file_sha256(report)):
            return None
        facts = dg["facts"]
        if (isinstance(facts.get("unjudged"), list) and isinstance(facts.get("ruled"), dict)
                and isinstance(facts.get("power_def"), dict)):
            return cast(dict[str, Any], facts)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass
    return None


def _write_report_digest(report: Path, result: dict[str, Any]) -> None:
    """Derive the facts from the rows just written and record them beside the report."""
    try:
        # Row by row (audit on b879ac50): one round-tripped row at a time, never a second copy
        # of the report. Both rules are single passes; counts merge in first-seen order, which
        # is the order one pass over every row gives.
        unjudged: set[str] = set()
        ruled: dict[str, int] = {}
        power_def: dict[str, int] = {}
        for v in result.get("verdicts") or []:
            r = (json.loads(json.dumps(v, default=str)),)
            unjudged |= _unjudged_cells(r)
            r_ruled, r_power = _yield_counts(r)
            for k, n in r_ruled.items():
                ruled[k] = ruled.get(k, 0) + n
            for k, n in r_power.items():
                power_def[k] = power_def.get(k, 0) + n
        facts = {"unjudged": sorted(unjudged), "ruled": ruled, "power_def": power_def}
        doc = {"report_sha256": _file_sha256(report), "report_bytes": report.stat().st_size,
               "code": _report_digest_code(), "facts": facts}
        dest = report.parent / "gauntlet_cache" / REPORT_DIGEST_NAME
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(f"{dest.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc), encoding="utf-8")
        os.replace(tmp, dest)
    except Exception as exc:              # a missing digest only costs the next sweep a read
        print(f"  report digest not written ({type(exc).__name__}: {exc})")


# ------------------------------------------------------------------ attestation re-mint (v4)
#: THE RE-MINT QUEUE, written hourly by `research/attestation_remint.py` (unsealed). When
#: gate_policy.ATTESTATION changes, every certificate judged under the old attestation is refused
#: whole by `shadow_admission.authorized_runs` -- and before this patch the way out was a RE-STAMP:
#: the survivor block below merged the old rows and wrote `gate_policy: ATTESTATION` over them,
#: while the sort put every already-judged cell (`_is_new` = 1) behind the never-judged backlog.
#: Measured 2026-09-30 (lockbox v4): 0 of 58 authorized, 58 report rows and 52 canon rows judged
#: under `...-v2-calibrated-inputs`.
#:
#: WITH THIS FILE PRESENT AND ITS `attestation` EQUAL TO THE ONE IN FORCE, and only then:
#:   * the listed cells are judged FIRST, are not set aside by the novelty screen as twins of
#:     themselves, and are not trimmed by the yield allocation;
#:   * the survivor block re-mints honestly: a stale row re-judged and passed is replaced by its
#:     new row; re-judged and failed is RETIRED carrying the NEW failing gates (so the restore
#:     loop can never bring it back); not reached this sweep waits in `pending_rejudge`, OUTSIDE
#:     the survivor set, never under the new header.
#: Every re-judge is an ordinary docket cell: counted in the trial census and the gate ledger.
PRIORITY_REMINT = HYP / "priority_remint.json"


def canon_remint_cells(doc: object, is_exact) -> tuple[set[str], set[str]]:
    """(cells, certificate keys) the CANON ITSELF says await re-judgement (audit 2026-10-13).

    Every row in `pending_rejudge`, and -- in the re-seal window, before the first sweep under a
    new attestation has run -- every survivor under a header that is no longer exact. Read from
    the survivor file the gauntlet writes, so the front of the queue needs no second organ to
    author `priority_remint.json` (none does)."""
    if not isinstance(doc, dict):
        return set(), set()
    rows: dict = {}
    pending = doc.get("pending_rejudge")
    if isinstance(pending, dict):
        rows.update(pending)
    survivors = doc.get("survivors")
    if isinstance(survivors, dict) and survivors and not is_exact(doc.get("gate_policy")):
        rows.update(survivors)
    cells: set[str] = set()
    for row in rows.values():
        if isinstance(row, dict):
            cells |= _row_cells(row)
    return cells, {str(k) for k in rows}


def remint_cells(path: Path | None = None,
                 canon_path: Path | None = None) -> tuple[set[str], set[str]]:
    """(cell ids to judge first, certificate keys judged before the attestation in force).

    The union of `priority_remint.json` (when present and current) and the canon's own
    re-judge set (`canon_remint_cells`)."""
    try:
        from research.gate_policy import ATTESTATION as _att
        from research.gate_policy import is_exact_policy as _exact
    except ImportError:
        return set(), set()
    cells: set[str] = set()
    stale: set[str] = set()
    try:
        doc = json.loads((path or PRIORITY_REMINT).read_text("utf-8"))
    except (OSError, ValueError):
        doc = None
    if isinstance(doc, dict) and doc.get("attestation") == _att:
        cells |= {str(c) for c in (doc.get("cells") or []) if c}
        stale |= {str(k) for k in (doc.get("stale_certificate_keys") or []) if k}
    try:
        canon = json.loads((canon_path or REPORTS / "UNIVERSAL_SURVIVORS.json")
                           .read_text("utf-8"))
    except (OSError, ValueError):
        canon = None
    c_cells, c_keys = canon_remint_cells(canon, _exact)
    return cells | c_cells, stale | c_keys


def restore_would_restamp(row: dict, attestation: dict) -> bool:
    """True when restoring a retired row would stamp `attestation` over gates never judged
    under it: the attestation reserves a lockbox and the row's gate 9 carries no carve, or a
    carve under another basis. Such a row goes to `pending_rejudge`, never back to survivors."""
    basis = attestation.get("lockbox_basis") if isinstance(attestation, dict) else None
    if not basis:
        return False
    gates = row.get("gates") if isinstance(row, dict) else None
    lb = (gates or {}).get("lockbox") if isinstance(gates, dict) else None
    lb = lb if isinstance(lb, dict) else {}
    return not lb.get("cut") or lb.get("basis") != basis


def remint_front(specs: list[dict], is_remint) -> list[dict]:
    """Stable partition: re-mint cells first, every other cell in the order it already had."""
    front = [sp for sp in specs if is_remint(sp)]
    if not front:
        return specs
    return front + [sp for sp in specs if not is_remint(sp)]


def _row_cells(row: dict) -> set[str]:
    out = {str(row["cell"])} if row.get("cell") else set()
    spec = row.get("shadow_spec") if isinstance(row.get("shadow_spec"), dict) else {}
    if spec.get("symbol") and spec.get("family") and isinstance(spec.get("params"), dict):
        try:
            out.add(cell_id({"sym": spec["symbol"], "family": spec["family"],
                             "params": spec["params"]}))
        except Exception:
            return out
    return out


#: Stage statuses that say the gate could not rule, never that it ruled against the cell.
_UNRULED_STATUSES = ("UNMEASURED", "UNKNOWN")


def _stage_unruled(name: str, st: object) -> bool:
    """Whether a stage that did not pass was a gate that COULD NOT RULE, not a failure.

    A stage with no recorded result, an explicit `unmeasured` flag or an UNMEASURED/UNKNOWN
    status is no evidence, nor is a stage stamped `measured: False` (an UNMEASURED cost fails
    closed for CERTIFICATION, but it is not a ruling against a certificate already held); so is a
    lockbox with no held-out Sharpe at all ("no lockbox evidence
    exists", `gate_policy.lockbox_stage` under its day floor), with or without the frequency-
    aware `unmeasured` flag."""
    if not isinstance(st, dict):
        return True
    if st.get("passed") is None or st.get("unmeasured") or st.get("measured") is False:
        return True     # `swap_cost` writes measured False when the cost could not be priced
    if str(st.get("status") or "").upper() in _UNRULED_STATUSES:
        return True
    return name == "lockbox" and st.get("lockbox_sharpe") is None


def remint_unruled(v: dict) -> bool:
    """A re-judge that measured nothing: it may not retire a certificate (audit 2026-10-13).

    An UNMEASURED verdict (too few observations, no series, a lockbox the history cannot supply)
    or one whose terminal gate is UNKNOWN is a fact about what the sweep could see, not evidence
    against the edge -- the gauntlet's own observations text says so. Retiring on it revoked
    certificates on absence, the one thing L1.28a forbids. A re-judge retires only when at least
    one gate RULED against the cell."""
    if v.get("unmeasured") or v.get("passed") is None:
        return True
    if str(v.get("terminal_gate") or "").upper() in _UNRULED_STATUSES:
        return True
    failing = [(g, st) for g, st in (v.get("stages") or {}).items()
               if not (isinstance(st, dict) and st.get("passed") is True)]
    return bool(failing) and all(_stage_unruled(str(g), st) for g, st in failing)


def remint_partition(old_doc: dict, survivors_all: dict, verdicts: list, fresh_keys: set,
                     stale_hint: set, is_exact, version: str, now_iso: str) -> dict:
    """Take every row judged under another attestation OUT of `survivors_all` (in place).

    Returns {"pending", "retired", "superseded", "accounted", "record"}. `accounted` is how many
    rows left `survivors_all`, so the never-shrink check counts a re-mint as the revocation it
    is rather than as lost evidence.
    """
    old_doc = old_doc if isinstance(old_doc, dict) else {}
    old_pending = old_doc.get("pending_rejudge")
    old_pending = dict(old_pending) if isinstance(old_pending, dict) else {}
    header_stale = bool(old_doc) and not is_exact(old_doc.get("gate_policy"))
    stale = set(old_pending) | set(stale_hint)
    if header_stale:
        stale |= set(old_doc.get("survivors") or {})
    empty = {"pending": {}, "retired": {}, "superseded": {}, "accounted": 0,
             "record": {"active": False}}
    if not stale:
        return empty
    judged: dict[str, dict] = {}
    for v in verdicts or []:
        # A verdict about the UNIVERSE (symbol_eligibility) is not a verdict about the
        # certificate: a transient registry stump must not retire it.
        if (isinstance(v, dict) and v.get("stages") and v.get("cell")
                and v.get("terminal_gate") != "symbol_eligibility"):
            judged[str(v["cell"])] = v
    pending: dict[str, dict] = {}
    retired: dict[str, dict] = {}
    superseded: dict[str, str] = {}
    accounted = 0
    unruled = 0
    for key in sorted(stale):
        if key in fresh_keys:
            old_pending.pop(key, None)
            continue                  # re-judged and passed this sweep: its row IS new evidence
        row = survivors_all.pop(key, None)
        if row is not None:
            accounted += 1
        else:
            row = old_pending.get(key)
        if not isinstance(row, dict):
            continue
        v = next((judged[c] for c in sorted(_row_cells(row)) if c in judged), None)
        if v is None:
            back = dict(row)
            back.setdefault("pending_since", now_iso)
            back["pending_reason"] = (f"gates predate attestation {version}; not reached by "
                                      f"this sweep -- judged first on the next")
            pending[key] = back
        elif not v.get("passed") and remint_unruled(v):
            back = dict(row)
            back.setdefault("pending_since", now_iso)
            back["pending_reason"] = (
                f"re-judged under attestation {version} but the gates could not rule "
                f"({v.get('unknown_reason') or v.get('terminal_gate') or 'UNMEASURED'}): no "
                f"evidence against the certificate, so it waits and is judged first again")
            back["last_rejudge_unmeasured"] = now_iso
            pending[key] = back
            unruled += 1
        elif v.get("passed"):
            new_key = f"external.{v['cell']}"
            if new_key in survivors_all:
                superseded[key] = new_key
            else:
                back = dict(row)
                back.setdefault("pending_since", now_iso)
                back["pending_reason"] = ("re-judged PASS but the writer refused its row; "
                                          "waits, never carried under the new header")
                pending[key] = back
        else:
            failed = sorted(g for g, st in (v.get("stages") or {}).items()
                            if not (isinstance(st, dict) and st.get("passed") is True))
            gone = dict(row)
            gone["gates_superseded"] = row.get("gates")
            gone["gates"] = v.get("stages")
            gone["retired_at"] = now_iso
            gone["retired_reason"] = (f"RE-JUDGED under attestation {version}: failed "
                                      f"{', '.join(failed) or v.get('terminal_gate')}")
            retired[key] = gone
    record = {"active": True, "at": now_iso, "to_version": version,
              "header_was_stale": header_stale,
              "from_version": (old_doc.get("gate_policy") or {}).get("version")
              if isinstance(old_doc.get("gate_policy"), dict) else None,
              "stale_rows": len(stale), "rejudged_passed": len(stale) - len(pending)
              - len(retired) - len(superseded),
              "rejudged_failed_retired": len(retired), "superseded": superseded,
              "rejudged_unmeasured_kept_pending": unruled,
              "pending_rejudge": len(pending), "left_survivor_set": accounted}
    return {"pending": pending, "retired": retired, "superseded": superseded,
            "accounted": accounted, "record": record}


def _orthogonality_floor(specs: list[dict], keep: list[dict], *,
                         saturated: set[str] | frozenset[str] = frozenset()
                         ) -> tuple[list[dict], dict]:
    """Guarantee the rho-reducing families a sample, because their yield is 0 and always will be.

    WHAT THE MEASUREMENT ACTUALLY SAID, 2026-09-15, after two wrong readings of it. The docket
    holds 1,596 residual and relative-value candidates and ZERO have certified. The first reading
    was "never judged" -- taken from the docket, which carries no verdict field at all. The second
    was "judged and failed". Both were wrong, and the gates report says so plainly: 1,544 of 1,598
    carry `stages: {}`, `days: 0`, `passed: null` and
    `downstream_status: NOT_RUN_BUILD_BUDGET_DEFERRED`. They were QUEUED AND NEVER REACHED. Only
    54 were ever computed (34 failed in_sample_screen, 19 deflated_sharpe, 1 observations).

    The allocator is not the cause: it already keeps 1,339 of them. The cause was the seen-stamp
    trap `_is_new` now closes. This floor is the SECOND line rather than the fix -- it guarantees
    the rho-reducing families a sample if the yield trim ever does stop keeping them, which is
    exactly what the trim is designed to do once a family has been ruled on and produced nothing.
    It appends and takes from nobody, and when the trim already keeps enough it adds zero and says
    so.

    WHY THAT TERM IS THE ONLY ONE THAT MATTERS. n_eff = N / (1 + (N-1)rho). At the book's measured
    rho ~= 0.165, n_eff is 5.59 on 61 sleeves and the CEILING is 1/rho = 6.1. Adding 939 more
    sleeves at the same correlation buys 0.49 of one effective bet. No number of sources, cells or
    certificates moves past 6.1; only rho does. Every certified family this desk holds is a
    directional price-pattern family -- session_range_breakout 20, discovered 24,
    overnight_gap_decay 12, carry 1 -- which is six kinds of structural sameness and is precisely
    what rho measures.

    So this floor is not fairness between families. It is the only lever on the binding constraint
    that the desk already owns, sitting unjudged in its own docket.
    """
    kept_ids = {id(s) for s in keep}
    # A family the breadth steer measures SATURATED (its mechanism holds a certified or live
    # sleeve: cross_asset_residual 346 certificates on 2026-10-13) is no longer "never judged,
    # yield 0" -- forcing it is the opposite of breadth. Empty set (no steer): legacy behaviour.
    rows = [s for s in specs if str(s.get("family") or "") in ORTHOGONAL_FAMILIES
            and str(s.get("family") or "") not in saturated]
    have = sum(1 for r in rows if id(r) in kept_ids)
    short = ORTHOGONALITY_MIN_CELLS - have
    if not rows or short <= 0:
        return [], {"docket": len(rows), "already_kept": have, "added_by_floor": 0,
                    "why": "the yield trim already keeps enough orthogonal-family cells"}
    spare = [r for r in rows if id(r) not in kept_ids][:short]
    return spare, {
        "docket": len(rows), "already_kept": have, "added_by_floor": len(spare),
        "families": list(ORTHOGONAL_FAMILIES),
        "why": ("orthogonal-by-construction families have never been judged, so their yield is 0 "
                "and the allocator would never build them. n_eff is capped at 1/rho = 6.1 and "
                "only rho moves it; these are the only families that attack rho directly."),
    }


#: THE BREADTH STEER (desks/mt5/research/breadth_enforcer.py, principal 2026-10-13). Resolved at
#: CALL time from `REPORTS` (or GAUNTLET_BREADTH_STEER), never bound at import: a test that points
#: `REPORTS` at a tmp tree must not read the host's live steer.
BREADTH_STEER_MAX_AGE_H = 6.0


def _breadth_steer_path() -> Path:
    env = os.environ.get("GAUNTLET_BREADTH_STEER", "").strip()
    return Path(env) if env else REPORTS / "BREADTH_ENFORCER.json"


def _breadth_steer() -> dict | None:
    """The enforcer's MEASURED steer <= BREADTH_STEER_MAX_AGE_H old, or None (legacy behaviour).
    Read through the enforcer's own `load_steer`, so the staleness rule has one definition."""
    try:
        from research.breadth_enforcer import load_steer
        return load_steer(_breadth_steer_path(), max_age_h=BREADTH_STEER_MAX_AGE_H)
    except Exception:
        return None


#: THE FAMILY FLOOR REACHES THE BUILD (2026-10-14). The build budget walks `keep` front to back,
#: so whatever order `keep` has IS the allocation the budget actually reaches. These bound the
#: interleave that sets that order: a unit is at most this many consecutive same-symbol cells of
#: one family (the frame cache's contiguity holds inside it; no family's run can hold the head
#: for thousands of cells), and a published quota is clamped to [lo, hi] x the median weight, so
#: one malformed or extreme number in JUDGE_COVERAGE.json can neither freeze a family out of the
#: head nor hand it the whole of it.
FLOOR_INTERLEAVE_MAX_RUN = 32
FLOOR_WEIGHT_CLAMP = (0.01, 100.0)
#: What the last interleave used, published in RESEARCH_ALLOCATION.json (never a silent weight).
_FLOOR_INTERLEAVE_NOTE: dict[str, Any] = {}


def _coverage_quota() -> dict[str, int]:
    """The per-family quota `research/judge_coverage.py` published for this hour, or {}.

    Read, never recomputed: one allocation, written by intake, consumed here. An entry that is not
    a positive integer is skipped on its own (one bad row never discards the rest); an unreadable
    file returns {} and the interleave falls back to each family's own take size as its weight,
    which is still family-fair -- never the block order this replaced."""
    try:
        doc = json.loads((REPORTS / "JUDGE_COVERAGE.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    raw = doc.get("quota") if isinstance(doc, dict) else None
    out: dict[str, int] = {}
    for k, v in (raw.items() if isinstance(raw, dict) else ()):
        try:
            n = int(v)
        except (TypeError, ValueError, OverflowError):
            continue
        if n > 0:
            out[str(k)] = n
    return out


def _floor_weights(takes: dict[str, list[dict[str, Any]]]) -> dict[str, float]:
    """Each family's interleave weight: its published quota (at least 1), or its own take size
    when no quota is readable; clamped to FLOOR_WEIGHT_CLAMP x the median weight. The source and
    every clamped family are recorded in `_FLOOR_INTERLEAVE_NOTE` and printed once."""
    quota = _coverage_quota()
    fams = [f for f, rows in takes.items() if rows]
    raw = {f: float(max(quota.get(f, 0), 1)) if quota else float(max(len(takes[f]), 1))
           for f in fams}
    if not raw:
        return {}
    vals = sorted(raw.values())
    med = vals[len(vals) // 2] if len(vals) % 2 else 0.5 * (vals[len(vals) // 2 - 1]
                                                            + vals[len(vals) // 2])
    lo, hi = FLOOR_WEIGHT_CLAMP[0] * med, FLOOR_WEIGHT_CLAMP[1] * med
    w = {f: min(max(v, lo), hi) for f, v in raw.items()}
    clamped = {f: {"published": raw[f], "used": round(w[f], 4)} for f in fams if w[f] != raw[f]}
    _FLOOR_INTERLEAVE_NOTE.clear()
    _FLOOR_INTERLEAVE_NOTE.update({
        "weight_source": "JUDGE_COVERAGE.quota" if quota else "take_size (quota unreadable)",
        "median_weight": med, "clamp_relative": list(FLOOR_WEIGHT_CLAMP),
        "max_run_cells": FLOOR_INTERLEAVE_MAX_RUN, "families": len(fams), "clamped": clamped})
    if clamped:
        print(f"[floor-interleave] {len(clamped)} family weight(s) clamped to "
              f"[{lo:g}, {hi:g}] (median {med:g}): "
              + ", ".join(f"{f} {c['published']:g}->{c['used']:g}"
                          for f, c in sorted(clamped.items())[:12]), flush=True)
    return w


def _floor_interleave(takes: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Start-time weighted fair interleave of the family takes; every row kept once, each
    family's own order kept.

    A family's stream is cut into UNITS: runs of consecutive same-symbol cells, each at most
    FLOOR_INTERLEAVE_MAX_RUN long (so the frame cache's symbol contiguity holds inside every unit).
    Each family advances a virtual clock by len(unit)/weight; the unit with the EARLIEST START goes
    next, ties to the family that appeared first. Ordering by start (not finish) time puts every
    family's first unit inside the first sum-of-one-unit-each cells, whatever its weight -- a
    finish-time order let a light family with one long run wait behind thousands of a heavy
    family's cells, which is the starvation this exists to end."""
    import heapq
    weight = _floor_weights(takes)
    units: dict[str, list[list[dict[str, Any]]]] = {}
    heap: list[tuple[float, int, str, int]] = []
    for order, (fam, rows) in enumerate(takes.items()):
        if not rows:
            continue
        us: list[list[dict[str, Any]]] = []
        for sp in rows:
            if (us and len(us[-1]) < FLOOR_INTERLEAVE_MAX_RUN
                    and us[-1][0].get("sym") == sp.get("sym")):
                us[-1].append(sp)
            else:
                us.append([sp])
        units[fam] = us
        heapq.heappush(heap, (0.0, order, fam, 0))
    out: list[dict[str, Any]] = []
    while heap:
        start, order, fam, i = heapq.heappop(heap)
        unit = units[fam][i]
        out.extend(unit)
        if i + 1 < len(units[fam]):
            heapq.heappush(heap, (start + len(unit) / weight[fam], order, fam, i + 1))
    return out


def _floor_interleave_steered(head: list[dict[str, Any]], steer: dict[str, Any]) -> list[dict[str, Any]]:
    """The floor interleave INSIDE the breadth steer's head, without moving the steer's tiers.

    `steered_yield_order` fixes WHICH cells are in the head and its tier order (UNKNOWN ground,
    the rest of the frontier, explored; the saturated set spread through it by its own WFQ). Each
    non-saturated tier keeps exactly its slots; only the cells inside a tier's slots are re-dealt
    by `_floor_interleave` across that tier's families, so an H1-only frontier family is no longer
    held behind every intraday frontier cell. Saturated slots are untouched. Same multiset, same
    per-family head counts, same tiers: only the order inside a tier changes."""
    try:
        from research.breadth_enforcer import SATURATED, class_of
    except Exception:
        return head
    out = list(head)
    slots: dict[str, list[int]] = {}
    for i, sp in enumerate(head):
        tier = class_of(str(sp.get("family") or "?"), steer)
        if tier != SATURATED:
            slots.setdefault(str(tier), []).append(i)
    tiers: dict[str, Any] = {}
    for tier, idx in slots.items():
        takes: dict[str, list[dict[str, Any]]] = {}
        for i in idx:
            takes.setdefault(str(head[i].get("family") or "?"), []).append(head[i])
        for i, sp in zip(idx, _floor_interleave(takes), strict=True):
            out[i] = sp
        tiers[tier] = {"slots": len(idx), **_FLOOR_INTERLEAVE_NOTE}
    _FLOOR_INTERLEAVE_NOTE.clear()
    _FLOOR_INTERLEAVE_NOTE.update({"steered": True, "saturated_slots_untouched": True,
                                   "tiers": tiers})
    return out


def allocate_by_yield(specs: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    """Trim the docket so the build budget lands on the families that produce survivors.

    THE BUDGET WAS BEING SPENT WHERE THE CELLS WERE, NOT WHERE THE SURVIVORS WERE. Measured on
    the live desk 2026-09-14, survivors per 1,000 RULED cells:

        session_range_breakout  105.6   (15 of 142)
        overnight_gap_decay      60.9   (12 of 197)
        carry                     8.7   (1 of 115)
        discovered                2.0   (33 of 16,270)
        cross_asset_residual      0.0   (0 of 816)
        relative_value            0.0   (0 of 363)
        vol_transition            0.0   (0 of 249)
        correlation_regime        0.0   (0 of 249)
        pca_residual              0.0   (0 of 230)
        turn_of_month             0.0   (0 of 146)

    `session_range_breakout` is fifty-two times more productive per cell than `discovered`, and
    `discovered` was taking 84% of every sweep. The two families that produced 27 of the desk's
    66 survivors shared 339 cells between them. Nothing chose that: the sweep builds in symbol-
    rotation order and `discovered` simply has the most cells, so the docket's SHAPE was the
    allocation policy.

    WHY A QUOTA AND NOT A REORDER. Cells are sorted so one symbol's charts stay contiguous,
    because the frame cache is what makes a build cheap; sorting by family first would reload
    frames once per yield band. Trimming each family's share leaves that ordering exactly as it
    is and changes only how much of each family the hour reaches.

    THE SHARES ARE DERIVED, NEVER DECLARED. Each family's share is its shrunk posterior yield
    blended with a uniform share at `YIELD_ALLOCATION_STRENGTH`, floored at `YIELD_MIN_SHARE`
    of its own docket. A family with no record is credited with the house average, so a new
    family is neither condemned nor privileged before it has evidence.

    This does not reduce the sweep's total work; it redirects it. Nothing is dropped from the
    docket -- a trimmed cell keeps its place for a later hour, exactly as a deferred one does.
    """
    if not specs:
        return specs, {}
    yields = _family_yield()
    by_fam: dict[str, list[dict]] = {}
    for sp in specs:
        by_fam.setdefault(str(sp.get("family") or "?"), []).append(sp)
    # A FAMILY WITH NO RECORD IS CREDITED WITH THE HOUSE AVERAGE, measured from the same artifacts
    # in the same breath. Crediting it with zero would starve every new family at birth; crediting
    # it with the best family's rate would let an untested one displace a proven one.
    prior = _house_yield()
    raw = {f: max(yields.get(f, prior), 1e-9) for f in by_fam}
    tot = sum(raw.values()) or 1.0
    n_fam = len(by_fam)
    keep: list[dict] = []
    takes: dict[str, list[dict[str, Any]]] = {}
    report: dict[str, dict] = {}
    wants: dict[str, int] = {}
    for fam, rows in by_fam.items():
        share = (YIELD_ALLOCATION_STRENGTH * (raw[fam] / tot)
                 + (1.0 - YIELD_ALLOCATION_STRENGTH) / n_fam)
        # A share is of the WHOLE docket; a family holding fewer cells than its share simply
        # keeps all of them and the surplus flows to the others through the floor below.
        share = min(share, YIELD_MAX_SHARE)
        want = max(int(round(share * len(specs))), int(YIELD_MIN_SHARE * len(rows)), 1)
        wants[fam] = want
        take = rows[:want]
        takes[fam] = take
        report[fam] = {"docket": len(rows), "built_this_sweep": len(take),
                       "yield_per_1k_ruled": round(raw[fam] * 1000, 2),
                       "share_of_budget": round(share, 4),
                       "capped_by_ceiling": bool(share >= YIELD_MAX_SHARE),
                       "held_by_floor": bool(len(take) <= int(YIELD_MIN_SHARE * len(rows)))}
    # THE FAMILY FLOOR REACHES THE BUILD (2026-10-14). `keep` was the family takes CONCATENATED,
    # in the order each family first appeared in the sorted docket, and the build budget walks it
    # front to back -- so the first two or three families' takes (tens of thousands of cells
    # each) spent the whole budget and every later family was NOT_RUN_BUILD_BUDGET_DEFERRED,
    # every sweep. Measured on the box's 2026-10-12 05:31 sweep: 9 of 60 listed families
    # received every named verdict; 51 received none. The takes are now INTERLEAVED by start-time
    # weighted fair queueing on the per-family quota `research/judge_coverage.py` publishes, in
    # same-symbol units of at most FLOOR_INTERLEAVE_MAX_RUN cells. Same cells, same counts, same
    # trim: only the order the budget walks changes.
    keep = _floor_interleave(takes)
    # THE EXPLORATION FLOOR, APPLIED AFTER THE TRIM AND TAKING FROM NOBODY. The family split above
    # is exploitation: it sends budget where survivors have come from. That is correct and it is
    # why every certificate this desk holds is H1/asia -- the axes it has never sampled score zero
    # and are never sampled again. This appends cells on UNMEASURED (chart, anchor) axes so the
    # desk can distinguish "no edge there" from "never asked".
    # THE BREADTH STEER. With a fresh MEASURED steer the yield takes above set the BUDGET (their
    # sum: what the split would build) and the ORDER comes from the enforcer's one shared
    # definition, `steered_yield_order`: frontier first, explored next, the saturated set
    # INTERLEAVED through the head at the exploration floor and spread across its families by
    # their yield takes -- so the highest-yield saturated families are built from the first slice
    # -- and every cell past the budget waits at the tail instead of being trimmed (work-
    # conserving; the sweep's total never falls). No steer: the legacy trim, byte for byte.
    steer = _breadth_steer()
    steered: dict | None = None
    # WHY THE STEER IS NOT IN FORCE, published instead of a silent null (III.16): a desk that
    # adopts this before the enforcer's `steered_yield_order` lands must not look steered.
    steer_off: dict = {"in_force": False, "path": str(_breadth_steer_path()),
                       "why": (f"no MEASURED steer <= {BREADTH_STEER_MAX_AGE_H}h old at the "
                               f"path (absent, unmeasured, stale or the enforcer is not "
                               f"importable): legacy trim")}
    if steer:
        try:
            from research.breadth_enforcer import SATURATED, class_of, steered_yield_order
            order, budget, steered = steered_yield_order(specs, wants, steer)
        except Exception as exc:
            steer, steered = None, None
            steer_off["why"] = (f"a MEASURED steer is present but unusable "
                                f"({type(exc).__name__}: {exc}): legacy trim")
    if steer and steered is not None:
        head, tail = order[:budget], order[budget:]
        # The steer orders by tier and ignores `keep`, so the floor interleave runs here too:
        # inside each non-saturated tier's slots, never across tiers (`_floor_interleave_steered`).
        head = _floor_interleave_steered(head, steer)
        sat_set = {f for f in by_fam if class_of(f, steer) == SATURATED}
        built = steered.get("built_in_budget") or {}
        for fam in report:
            report[fam]["built_this_sweep"] = int(built.get(fam, 0))
            report[fam]["queued_to_tail"] = int((steered.get("queued_to_tail") or {}).get(fam, 0))
            report[fam]["breadth_class"] = class_of(fam, steer)
        explored, axes = _explore_unmeasured_axes(specs, head)
        orthogonal, ortho_record = _orthogonality_floor(specs, head + explored, saturated=sat_set)
        _added = {id(s) for s in head + explored + orthogonal}
        keep = head + explored + orthogonal + [s for s in tail if id(s) not in _added]
    else:
        explored, axes = _explore_unmeasured_axes(specs, keep)
        keep.extend(explored)
        # THE ORTHOGONALITY FLOOR, on the same footing and for a sharper reason. The exploration
        # floor above buys AXES the desk has never sampled; this buys the only families that
        # attack rho, which is the single term n_eff is capped by (1/rho = 6.1 on this book).
        # Also takes from nobody: it appends.
        orthogonal, ortho_record = _orthogonality_floor(specs, keep)
        keep.extend(orthogonal)
    # PUBLISHED, because an allocation nobody can read is not an allocation anyone can argue with
    # -- the capital side has pf_allocation.json for exactly this and the research side had
    # nothing. Best effort: a research sweep must never die because a report file is unwritable.
    try:
        out = REPORTS / "RESEARCH_ALLOCATION.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "rule": ("share of the build budget per family: shrunk posterior survivors-per-ruled-"
                     "cell, blended with uniform at YIELD_ALLOCATION_STRENGTH, floored at "
                     "YIELD_MIN_SHARE of the family's own docket and capped at YIELD_MAX_SHARE"),
            "strength": YIELD_ALLOCATION_STRENGTH,
            "floor_share": YIELD_MIN_SHARE, "ceiling_share": YIELD_MAX_SHARE,
            "prior_strength_cells": YIELD_PRIOR_STRENGTH,
            "docket_total": len(specs), "built_this_sweep": len(keep),
            "by_family": report,
            "floor_interleave": dict(_FLOOR_INTERLEAVE_NOTE),
            "breadth_steer": ({"in_force": True, **{k: v for k, v in steered.items()
                                                     if k != "built_in_budget"}}
                              if steer and steered is not None else steer_off),
            # THE MISSED-GROWTH LINE, INVERTED: what exploitation alone would NOT have built.
            "exploration": {
                "rule": ("an axis (chart, session anchor) that has never produced a survivor has "
                         "a measured yield of exactly zero, so the yield split would never build "
                         "it again. These cells are APPENDED after the trim -- no family's share "
                         "is reduced and nothing earning loses a build. Affordable because the "
                         "build budget is not binding."),
                "min_cells_per_unmeasured_axis": EXPLORATION_MIN_CELLS,
                "orthogonality_floor": ortho_record,
                "min_cells_orthogonal_families": ORTHOGONALITY_MIN_CELLS,
                "n_axes_floored": len(axes),
                "n_cells_added": len(explored),
                "by_axis": axes,
            },
        }, indent=1), encoding="utf-8")
    except OSError:
        pass
    return keep, report


#: When each symbol's cells were last BUILT (not merely considered). The rotation key.
BUILD_CURSOR = REPORTS.parent / "data" / "hypotheses" / "gauntlet_build_cursor.json"

#: Every cell id this desk has ever JUDGED, and when it was first judged. The NEW-FIRST key.
#:
#: WHY A SECOND CURSOR. The build cursor rotates by SYMBOL, which is right for converging a
#: standing docket: whatever an hour misses is at the front of the next one. It is wrong for a
#: NEW cell, because a freshly converted candidate on an already-built symbol inherits that
#: symbol's recent timestamp and sorts to the BACK -- behind ~20,000 cells the desk has already
#: judged, in a rotation that takes ~6.4 hours to come round.
#:
#: That is the wrong trade. Re-judging a cell whose daily series gained one point since
#: yesterday reproduces yesterday's verdict; judging a cell for the FIRST time is the only thing
#: a sweep does that can change what the desk knows. So never-judged cells go first, always, and
#: the symbol rotation orders everything behind them exactly as before.
SEEN_CELLS = REPORTS.parent / "data" / "hypotheses" / "gauntlet_seen_cells.json"


#: WHICH GATE KILLED WHICH CELL, kept across sweeps (2026-09-12).
#:
#: The verdicts already carry `terminal_gate`. They were written to universal_gates_external.json
#: and OVERWRITTEN every sweep, so the desk held this hour's rejections and no history at all --
#: which is why `negative_knowledge` had to report "likely failure gate: UNMEASURED, no artifact
#: on this box records which gate rejected which cell". It was there and it was being thrown away
#: once an hour.
#:
#: APPEND ONLY ON CHANGE, which is what keeps this bounded. Re-judging 21,000 cells an hour and
#: appending every verdict would write half a million rows a day to say nothing new; a cell whose
#: verdict is unchanged is not information. The index below holds the last recorded verdict per
#: cell, and a row is written only when the verdict differs from it -- so the ledger's growth is
#: the rate at which the desk CHANGES ITS MIND, which is exactly the quantity worth storing.
GATE_LEDGER = REPORTS.parent / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
GATE_INDEX = REPORTS.parent / "data" / "hypotheses" / "gate_verdict_index.json"


def _graph_ids_for(specs: list | None) -> dict[str, str]:
    """cell id -> `hypothesis_graph` node id, for the specs this sweep judged.

    TWO NAMES FOR ONE CELL, AND NOTHING JOINED THEM. This ledger calls a cell
    `EURAUD.overnight_gap_decay.p=<sha of params>`; the hypothesis graph calls the same rule
    `f668ed18...` (`node_id` over symbol/family/params). So a trial could never be joined to the
    candidate it tested, and `libs/moat/registry.sync_from_desk` recorded both as separate ids.
    The spec is in hand HERE, where both names can be computed from it, so the join is written
    down once rather than guessed at later.
    """
    out: dict[str, str] = {}
    for s in specs or []:
        if not isinstance(s, dict):
            continue
        try:
            out[cell_id(s)] = node_id_for_spec(s)
        except (KeyError, TypeError, ValueError):
            continue          # a spec too malformed to name is UNMEASURED, never a wrong id
    return out


#: The UNKNOWN causes the judge can see for itself. `run_gauntlet` sets one on every unmeasured
#: verdict; `unknown_row_reason` falls back to the last two for a row written without one.
UNKNOWN_REASONS = ("series_exception", "no_series", "lockbox_consumed_history",
                   "screened_past_cut", "short_history_after_cut", "no_signals",
                   "signals_no_trades", "no_trades", "too_rare", "observations_under_60_days",
                   "no_terminal_gate_recorded")


def cell_lockbox_cut(series, need: int = 60, frac: float | None = None):
    """A cell's OWN lockbox cut: its last `LOCKBOX_FRAC` of days, never fewer than the lockbox
    floor, or None when that would leave under `need` development days. Used only for a cell the
    campaign-wide cut leaves unjudgeable because its chart's history begins after it."""
    from research.gate_policy import LOCKBOX_FRAC, LOCKBOX_MIN_DAYS
    cal = sorted(set(series.index))
    n = len(cal)
    # `frac` is the held-out share of the law in force (S01); the policy's own when none is given.
    tail = max(int(LOCKBOX_MIN_DAYS),
               math.ceil(n * float(LOCKBOX_FRAC if frac is None else frac)))
    if n - tail < need:
        return None
    return cal[n - tail]


def cell_dev_cut(full, campaign_cut, need: int = 60, frac: float | None = None):
    """The cut that ends ONE cell's development window: the campaign cut, unless that leaves the
    cell under `need` development days AND the cell's own tail cut (`cell_lockbox_cut`) lies later
    -- then the cell's own. One function, so the unsharded sweep and a shard's `rule` phase carve
    every cell identically and the merge can verify the cut a shard used."""
    if full is None or campaign_cut is None:
        return campaign_cut
    if int((full.index < campaign_cut).sum()) >= need:
        return campaign_cut
    own = cell_lockbox_cut(full, need, frac=frac)
    return campaign_cut if own is None or own <= campaign_cut else own


def classify_unknown(dev, pre_carve_days: int | None, n_signals: int | None, *,
                     errored: bool = False, need: int = 60) -> str:
    """Why a cell short of `need` development days is UNKNOWN, from what the sweep held."""
    if dev is None:
        return "series_exception" if errored else "no_series"
    if (pre_carve_days or 0) >= need:
        return "lockbox_consumed_history"
    if len(dev) == 0 and (pre_carve_days or 0) > 0:
        # IT TRADED, ON FEWER THAN `need` DAYS, ALL AFTER THE CUT (2026-09-30). The pre-carve
        # series is non-empty, so this is a short history the carve took whole, never a fill
        # problem; the census (`unknown_share_census`) found 42 such cells read as
        # "signals_no_trades" on this scale.
        return "short_history_after_cut"
    if len(dev) == 0:
        return ("no_trades" if n_signals is None else
                "no_signals" if n_signals == 0 else "signals_no_trades")
    return "too_rare"


def unknown_row_reason(v: dict) -> dict:
    """The reason fields an UNKNOWN row carries: `unknown_reason` and a NON-EMPTY `failed_gates`.

    Whatever the verdict holds, the result names a cause -- the writer's own when it gave one,
    the observations gate when the verdict is the unmeasured branch, and an explicit
    `no_terminal_gate_recorded` otherwise, so an unnamed UNKNOWN cannot be written at all.
    """
    reason = str(v.get("unknown_reason") or "") or (
        "observations_under_60_days" if v.get("unmeasured") else "no_terminal_gate_recorded")
    failed = [str(g) for g in (v.get("failed_gates") or []) if str(g)]
    if not failed:
        failed = ["observations"] if v.get("unmeasured") else [reason]
    out: dict = {"unknown_reason": reason, "failed_gates": failed, "days": v.get("days")}
    if v.get("series_error"):
        out["series_error"] = str(v.get("series_error"))[:200]
    return out


#: THE TERMINAL STAMP: WHICH GATE STOPPED A CELL, AND WHY, ON EVERY ROW (2026-10-20).
#:
#: GATE_VERDICT_DIGEST 10-20 19:40Z: 587,075 of 963,604 ledger rejections (61%) and 885,556 of
#: the newest sweep's 900,500 verdicts read terminal gate UNKNOWN. `terminal_gate` is set only on
#: a verdict whose gates RULED, so every row the judge could not rule on -- too few observations,
#: no series, a build the budget never reached -- carried no gate at all, and every reader folded
#: the absence into one bucket. The mutation arms read that bucket and could not tell "never
#: fired" from "the lockbox took its history" from "the backtest raised".
#:
#: `terminal_gate` KEEPS ITS MEANING. Readers across the desk (clock certificates, the prereg
#: join, the re-mint partition, the converter) read UNKNOWN or an absent gate as UNMEASURED and
#: never as a rejection; renaming those rows' gate would retire certificates on absence (L1.28a).
#: So the stamp rides BESIDE it, on every row, and is never empty:
#:
#:   terminal_kind     PASSED | RULED | UNMEASURED | NOT_RUN | DEFECT
#:   terminal_gate_id  the gate that stopped the row: a ruled gate's name, `observations` for
#:                     the unmeasured branch, the NOT_RUN_* status for a row never built, PASSED
#:   terminal_reason   that gate's own words (its stage's why/message, or its measured fields)
#:
#: A row no rule can name is DEFECT with gate id `no_terminal_gate_recorded`: counted, sampled and
#: printed by the sweep, never folded into a silent UNKNOWN.
TERMINAL_KINDS = ("PASSED", "RULED", "UNMEASURED", "NOT_RUN", "DEFECT")
TERMINAL_DEFECT = "no_terminal_gate_recorded"
TERMINAL_REASON_CHARS = 200


def _stage_reason(name: str, st: object) -> str:
    """A gate's own words: its why/reason/message, else its measured scalar fields, in order."""
    if not isinstance(st, dict):
        return f"{name}: no stage record"
    for key in ("why", "reason", "message", "detail"):
        if st.get(key):
            return str(st.get(key))[:TERMINAL_REASON_CHARS]
    parts = [f"{k}={st[k]}" for k in st
             if k != "passed" and isinstance(st[k], (bool, int, float, str))][:4]
    return (f"{name}: " + ", ".join(parts) if parts
            else f"{name}: failed")[:TERMINAL_REASON_CHARS]


def terminal_stamp(v: dict[str, Any]) -> dict[str, str]:
    """(`terminal_kind`, `terminal_gate_id`, `terminal_reason`) for ONE verdict row; never empty.

    Reads only the row. Deterministic, so a row stamped in a shard and the same row stamped by
    the merge carry the same three values."""
    passed = v.get("passed")
    _raw = v.get("stages")
    stages: dict[str, Any] = _raw if isinstance(_raw, dict) else {}
    gate = str(v.get("terminal_gate") or "")

    def _out(kind: str, gid: str, why: str) -> dict[str, str]:
        return {"terminal_kind": kind, "terminal_gate_id": gid or TERMINAL_DEFECT,
                "terminal_reason": (why or gid or TERMINAL_DEFECT)[:TERMINAL_REASON_CHARS]}

    if passed is True:
        return _out("PASSED", "PASSED", "passed every gate")
    status = str(v.get("downstream_status") or "")
    if passed is None and status.startswith("NOT_RUN"):
        return _out("NOT_RUN", status, str(v.get("why") or status))
    if v.get("unmeasured"):
        return _out("UNMEASURED", "observations", unknown_row_reason(v)["unknown_reason"])
    if gate and gate.upper() not in ("UNKNOWN", "PASSED"):
        st = stages.get(gate)
        return _out("RULED", gate,
                    _stage_reason(gate, st) if st is not None else str(v.get("why") or gate))
    failed = [k for k, s in stages.items() if isinstance(s, dict) and s.get("passed") is False]
    if passed is False and failed:
        return _out("RULED", str(failed[0]), _stage_reason(str(failed[0]), stages[failed[0]]))
    return _out("DEFECT", TERMINAL_DEFECT,
                f"{TERMINAL_DEFECT}: passed={passed!r}, terminal_gate={gate or None!r}, "
                f"downstream_status={status or None!r}, stages={len(stages)}")


def stamp_terminal(rows: list[Any]) -> dict[str, Any]:
    """Stamp every dict row in place; return the defect count and a bounded sample of cells."""
    defects: list[str] = []
    for v in rows:
        if isinstance(v, dict):
            v.update(terminal_stamp(v))
            if v["terminal_kind"] == "DEFECT":
                defects.append(str(v.get("cell") or ""))
    return {"n": len(defects), "sample": defects[:20]}


def _append_gate_ledger(verdicts: list, specs: list | None = None) -> dict:
    """Record each cell's terminal gate, once per change. Never raises -- this is bookkeeping."""
    try:
        idx = json.loads(GATE_INDEX.read_text("utf-8"))
        if not isinstance(idx, dict):
            idx = {}
    except (OSError, ValueError):
        idx = {}
    graph_ids = _graph_ids_for(specs)
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    rows = []
    defects = 0
    for v in verdicts:
        if not isinstance(v, dict):
            continue
        cell = str(v.get("cell") or "")
        if not cell:
            continue
        gate = str(v.get("terminal_gate") or ("PASSED" if v.get("passed") else "UNKNOWN"))
        key = f"{gate}|{1 if v.get('passed') else 0}"
        if idx.get(cell) == key:
            continue
        idx[cell] = key
        # THE GRAPH'S NAME FOR THE SAME CELL, from the verdict's own params when it carries them
        # and from the judged spec otherwise. Written as "" rather than omitted when neither can
        # name it: a reader can then tell "this writer knew about graph_id and could not resolve
        # this cell" from a row written before the field existed (L1.28a).
        gid = (node_id_for_spec(v) if isinstance(v.get("params"), dict)
               else graph_ids.get(cell, ""))
        row = {"at": now, "cell": cell, "graph_id": gid, "sym": v.get("sym"),
               "family": v.get("family"),
               "passed": bool(v.get("passed")), "terminal_gate": gate,
               "downstream_status": v.get("downstream_status")}
        # THE STAMP, from the verdict when the sweep set it and derived from the row otherwise.
        _ts = (v if v.get("terminal_kind") in TERMINAL_KINDS and v.get("terminal_gate_id")
               else terminal_stamp(v))
        row.update({k: _ts[k] for k in ("terminal_kind", "terminal_gate_id", "terminal_reason")})
        if row["terminal_kind"] == "DEFECT":
            defects += 1
        if gate == "UNKNOWN":
            # NO UNKNOWN ROW WITHOUT ITS REASON (2026-09-30). 53,460 of a week's 124,342 rows read
            # UNKNOWN and not one said why, so the week could not be split into "never fired",
            # "too rare", "history eaten by the lockbox" and "the backtest raised". The terminal
            # gate stays UNKNOWN -- every reader treats it as unmeasured, never as a rejection --
            # and the reason rides beside it, never empty.
            row.update(unknown_row_reason(v))
        # THE PRE-REGISTRATION JOIN, carried from the verdict when this sweep stamped it
        # (`record_gauntlet_verdicts`). Omitted, not defaulted, on a verdict nobody stamped: the
        # docket writer's fallback reads the absence as "record this one" (one graph writer).
        if v.get("prereg_status"):
            row["prereg_hash"] = v.get("prereg_hash")
            row["prereg_status"] = v.get("prereg_status")
        rows.append(row)
    if not rows:
        return {"appended": 0, "known": len(idx), "terminal_defects": 0}
    try:
        GATE_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with GATE_LEDGER.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, default=str) + chr(10))
        GATE_INDEX.write_text(json.dumps(idx, indent=0, sort_keys=True), encoding="utf-8")
    except OSError as exc:
        return {"appended": 0, "known": len(idx), "error": str(exc)[:120],
                "terminal_defects": defects}
    return {"appended": len(rows), "known": len(idx), "terminal_defects": defects}


def _seen_cells() -> dict[str, str]:
    """cell id -> ISO time it was first judged. Unreadable reads as EMPTY, which is the safe
    direction: every cell then looks new, the sweep judges in cursor order as it always did, and
    one rotation is spent -- never a cell that stops being judged (L1.28a)."""
    try:
        doc = json.loads(SEEN_CELLS.read_text("utf-8"))
        return {str(k): str(v) for k, v in doc.items()} if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_seen_cells(seen: dict[str, str], judged: set[str]) -> None:
    """Record the cells this sweep actually judged, so they stop counting as new."""
    fresh = {c for c in judged if c and c not in seen}
    if not fresh:
        return
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    seen.update(dict.fromkeys(fresh, now))
    try:
        SEEN_CELLS.parent.mkdir(parents=True, exist_ok=True)
        SEEN_CELLS.write_text(json.dumps(seen, indent=0, sort_keys=True), encoding="utf-8")
        print(f"  seen-cells: +{len(fresh)} first-judged this sweep ({len(seen)} known)")
    except OSError as exc:
        print(f"  seen-cells NOT saved ({exc}); next sweep re-prioritises these as new")


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


@lru_cache(maxsize=1)
def _replay_code_identity() -> str:
    """Loaded-process replay semantics; a release starts a new process and identity."""
    digest = hashlib.sha256()
    desk = BASE / "desks" / "mt5"
    paths = [desk / "scripts" / "external_gauntlet.py",
             desk / "research" / "orthogonal_sweep.py",
             # The cost a cached series was charged is part of what it IS.
             desk / "research" / "entry_hour_cost.py", desk / "data" / "cost_surface.json"]
    paths.extend(desk / "mt5desk" / name for name in
                 ("engine.py", "cell_modifiers.py", "data.py", "legacy_family_inputs.py"))
    paths.extend((desk / "mt5desk").glob("famil*.py"))
    for path in sorted(set(paths)):
        name = path.relative_to(BASE).as_posix()
        digest.update(name.encode("utf-8") + b"\0"
                      + path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()


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

    `timeframe=None` resolves through `timeframe_of`. Replay-code identity prevents a repaired
    engine or family from judging cached returns produced by its superseded implementation.
    """
    import hashlib
    tf = timeframe_of(params, family) if timeframe is None else str(timeframe).upper()
    payload = {"s": sym, "f": family, "p": params, "d": last_day,
               "replay_code": _replay_code_identity()}
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
        pair = (pd.Series(z["v1"], index=idx), pd.Series(z["v3"], index=idx))
        for series, name in zip(pair, ("attrs1", "attrs3"), strict=True):
            if name in z:
                series.attrs.update(json.loads(str(z[name].item())))
        return pair
    except Exception:
        return None


_CACHE_SAVE_WARNED = [False]


def _cache_series_metadata(series) -> dict:
    """Bounded receipts with total count and full digest; raw replay remains reproducible."""
    attrs = series.attrs
    rejected = attrs.get("geometry_rejections") or []
    count = int(attrs.get("geometry_rejection_count", len(rejected)))
    digest = attrs.get("geometry_receipt_sha256")
    if count and not digest:
        digest = hashlib.sha256(json.dumps(rejected, sort_keys=True,
                                          default=str).encode("utf-8")).hexdigest()
    return {"signal_count": attrs.get("signal_count"),
            "geometry_rejection_count": count, "geometry_receipt_sha256": digest,
            "geometry_rejections": rejected[:3]}


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
                                 v3=ds3.reindex(common).to_numpy(float),
                                 attrs1=_np.array(json.dumps(_cache_series_metadata(ds1),
                                                           default=str)),
                                 attrs3=_np.array(json.dumps(_cache_series_metadata(ds3),
                                                           default=str)))
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
        last_day = _cell_last_day(sym, tf)
        if last_day is None:
            out["status"] = "NOT_RUN_DATA_MISSING"
            return out
        # The day this cell was keyed to goes back with it, so the shards key the same cell to the
        # same day and find what the pool built (`_run_shards` carries it in the plan).
        out["last_day"] = last_day
        ckey = _cache_key(sym, family, params, str(last_day.date()), tf)
        out["ckey"] = ckey
        if cache_load(ckey) is not None:
            out["status"] = "HIT"
            return out
        try:
            obj = build_cell(sym, family, params, meta)
        except Exception as exc_read:
            if not _unreadable_chart(exc_read):
                raise
            # The verdict the build loop now gives the same spec (`_build_specs`), so the pool
            # stands in for it exactly as it does for any BUILD_FAILED.
            out["status"], out["why"] = ("NOT_RUN_BUILD_FAILED",
                                         _unreadable_why(sym, tf, exc_read))
            return out
        if not obj:
            out["status"] = "NOT_RUN_BUILD_FAILED"
            out["why"] = LAST_BUILD_FAILURE or "UNMEASURED: build_cell returned no cell"
            return out
        _day = _built_day(obj, last_day)
        if _day != last_day:
            # Re-keyed to the frame it was built from (`_built_day`). `out["last_day"]` keeps the
            # chart's first day for the plan, so a shard may miss this one cell: it is then built
            # or deferred again, never served under the wrong day.
            last_day = _day
            ckey = _cache_key(sym, family, params, str(last_day.date()), tf)
            out["ckey"] = ckey
        ds1 = _series_trim_partial(daily_series(obj["df"], obj["sigs"], obj["costs"]), last_day)
        try:
            ds3 = _series_trim_partial(
                daily_series(obj["df"], obj["sigs"],
                             _stress_costs(obj["costs"], sym, meta.get(sym, {}), COST_SCENARIO)),
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


def _spec_key(spec: dict) -> str:
    """The build loop's own spec key (`_build_specs`), shared so the pool's outcome finds it."""
    params = json.dumps(spec.get("params"), sort_keys=True)
    return f"{spec.get('sym')}.{spec.get('family')}.{params}"


def _apply_prewarm_failures(specs: list, failed: dict, blocked_build: list) -> list:
    """Give each cell the pool failed the outcome the serial loop would have given it.

    A pool BUILD_FAILED ran `build_cell` on the same spec, bars and meta the loop would, so the
    loop's verdict is known: it is BLOCKED with the same status and reason, and leaves the specs
    (the coverage organ then parks it and re-admits it on bar growth or after its retry days).
    DATA_MISSING stays: the loop names it before any budget check. Every other kind (FAIL_3X,
    ERROR, SAVE_FAILED) is not a verdict the pool can stand in for, so the spec stays and, if
    deferred, carries `prewarm_status`/`prewarm_why` on its record -- never a silent deferral."""
    keep = []
    for sp in specs:
        fr = failed.get(_spec_key(sp))
        if fr and fr.get("status") == "NOT_RUN_BUILD_FAILED":
            why = str(fr.get("why") or "signal construction returned no executable cell")
            blocked_build.append({**sp, "downstream_status": (
                "NOT_RUN_MODIFIER" if why.startswith("NOT_RUN_MODIFIER") else
                "NOT_RUN_BUILD_FAILED"), "why": why})
            continue
        if fr and fr.get("status") not in (None, "NOT_RUN_DATA_MISSING"):
            sp = {**sp, "prewarm_status": fr.get("status"), "prewarm_why": fr.get("why")}
        keep.append(sp)
    return keep


#: CONSECUTIVE CELLS ON ONE CHART GO TO ONE WORKER (2026-10-21, desk health on the box at 23:47Z:
#: 15 pool workers at 0.5-0.6 core each under 21k-33k page faults a second EACH, 1.8-2.1 GB
#: private each). The pool handed out one cell at a time, so a run of cells on one chart --
#: which the docket order makes common (symbol and chart are sort keys, and the allocation keeps
#: each family's order) -- was dealt across all fifteen workers, and every one of them read and
#: normalised that chart's whole parquet into its own frame cache (1.3m rows: one M1 or two M5
#: charts) and then evicted it for the next run. The work was the same; the reads were fifteen.
#: A task is now up to this many consecutive specs on the same (symbol, chart), run in order in
#: one worker against the same deadline, so the chart is read once per run. Same specs, same
#: order of starts, same per-cell function (`_warm_one`), same outcome rows.
PREWARM_CHUNK = max(1, int(os.environ.get("GAUNTLET_PREWARM_CHUNK", "8") or 8))


def _chart_of(spec: dict) -> tuple[str, str]:
    return (str(spec.get("sym") or ""),
            timeframe_of(spec.get("params"), str(spec.get("family") or "")))


def _warm_run(specs: list, meta: dict, deadline: float) -> list[dict]:
    """`_warm_one` over consecutive same-chart specs, in order, in ONE worker. A spec whose turn
    comes after `deadline` is not started and comes back UNREACHED -- exactly what the parent's
    cancel makes of a spec it had not yet handed out."""
    out: list[dict] = []
    for sp in specs:
        if time.time() > deadline:
            out.append({"sym": str(sp.get("sym") or ""), "status": "UNREACHED"})
            continue
        out.append(_warm_one(sp, meta))
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

    # `built_symbols` IS THE ROTATION KEY, and its absence broke the rotation completely.
    # MEASURED 2026-09-11: the pool warmed 2,012 cells while the serial loop reported
    # `built_fresh = 0`, so `_built_syms` stayed EMPTY, so `_save_build_cursor` returned at its
    # `if not built` guard and the cursor was never stamped. The next sweep therefore sorted by
    # an unchanged cursor, put the same head of the docket first again, and left the same 11,146
    # cells deferred -- 20,352 unique cells with only 7,923 ever reaching the matrix, every hour,
    # forever. The docstring above worries about precisely this ("rebuild the head of the docket
    # every hour and never reach the tail") and guards the pool's ORDER, which was never the
    # problem: the pool built in the right order and nothing recorded that it had.
    summary = {"workers": WORKERS, "submitted": 0, "warmed": 0, "hit": 0, "failed": 0,
               "unreached": 0, "seconds": 0.0, "failures": {}, "failure_reasons": {},
               "built_symbols": set(), "failed_cells": {}, "last_days": {}}
    t0 = time.time()
    it = iter(specs)
    pending: dict = {}
    #: future -> spec, kept past the `pending.pop` so the completion handler can still name the
    #: symbol it just built. `pending` is popped before the result is read.
    pending_spec: dict = {}
    #: future -> when it was handed out: the oldest one still out is what a stuck worker looks
    #: like (the pool waits on it past the deadline), so the plan reports it while it waits.
    _sent_at: dict = {}
    print(f"PRE-WARM START: {len(specs)} cell(s) in docket order, {WORKERS} worker(s), "
          f"build budget ends in {deadline - t0:.0f}s", flush=True)

    def _progress(force: bool = False) -> None:
        _now = time.time()
        _plan_progress("prewarm", force=force, total=len(specs), submitted=summary["submitted"],
                       warmed=summary["warmed"], hit=summary["hit"], failed=summary["failed"],
                       unreached=summary["unreached"], in_flight=len(pending),
                       oldest_in_flight_s=round(max((_now - _sent_at.get(f, _now)
                                                     for f in pending), default=0.0), 1),
                       deadline_in_s=round(deadline - _now, 1), elapsed_s=round(_now - t0, 1))

    #: The next spec, read from `it` but not yet handed out (it opened a new chart's run).
    _held: list = []
    summary["chunk"] = PREWARM_CHUNK

    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        def _submit_next() -> bool:
            run = _held[:1] or [sp for sp in (next(it, None),) if sp is not None]
            _held.clear()
            if not run:
                return False
            chart = _chart_of(run[0])
            while len(run) < PREWARM_CHUNK:
                sp = next(it, None)
                if sp is None:
                    break
                if _chart_of(sp) != chart:
                    _held.append(sp)
                    break
                run.append(sp)
            _fut = pool.submit(_warm_run, run, meta, deadline)
            pending[_fut] = run
            pending_spec[_fut] = run
            _sent_at[_fut] = time.time()
            summary["submitted"] += len(run)
            return True

        def _count_one(_sp: dict, r: dict) -> None:
            st = str(r.get("status") or "ERROR")
            if st == "UNREACHED":
                summary["unreached"] += 1
                return
            if r.get("last_day") is not None:
                summary["last_days"].setdefault((str(r.get("sym") or ""),
                                                 str(r.get("tf") or "H1").upper()),
                                                r["last_day"])
            if st == "WARMED":
                summary["warmed"] += 1
                # WARMED only, never HIT: the cursor records when a symbol's cells were last
                # BUILT, and a cache hit spends no build budget. Stamping hits would push
                # cheap symbols to the back and starve the expensive ones that need the slot.
                _sp = _sp or {}
                _s = str(_sp.get("sym") or "")
                if _s:
                    summary["built_symbols"].add(_s)
            elif st == "HIT":
                summary["hit"] += 1
            else:
                summary["failed"] += 1
                summary["failures"][st] = summary["failures"].get(st, 0) + 1
                reason = str(r.get("why") or f"UNMEASURED: {st}")[:300]
                reasons = summary["failure_reasons"]
                reasons[reason] = reasons.get(reason, 0) + 1
                # PER CELL, so the loop can give the cell its own outcome. Without it a
                # pool failure reached the report as BUDGET_DEFERRED (the pool had spent
                # the budget), was never parked, and came back first every sweep: measured
                # 2026-10-13, 55.6% of pre-warm builds failed while the rows named none.
                _fsp = _sp or {}
                summary["failed_cells"][_spec_key(_fsp)] = {"status": st, "why": reason}

        for _ in range(2 * WORKERS):
            if not _submit_next():
                break
        while pending:
            if time.time() > deadline:
                # Stop handing out work. A run already in a worker starts no cell after the
                # deadline (`_warm_run`: the rest come back UNREACHED); runs
                # not yet started are cancelled and counted as unreached -- the main loop then
                # records them DEFERRED with the budget as the reason, as it always has.
                for f in list(pending):
                    if f.cancel():
                        summary["unreached"] += len(pending[f])
                        pending.pop(f)
                        _sent_at.pop(f, None)
            done, _ = wait(list(pending), timeout=5, return_when=FIRST_COMPLETED)
            _progress()
            for f in done:
                pending.pop(f, None)
                _sent_at.pop(f, None)
                _run = pending_spec.get(f) or []
                try:
                    _rows = list(f.result())
                except Exception as exc:
                    _rows = [{"status": "ERROR", "why": f"{type(exc).__name__}: {exc}"}
                             for _ in _run]
                for _sp, r in zip(_run, _rows, strict=True):
                    _count_one(_sp, r)
                if time.time() <= deadline:
                    _submit_next()
    if _held:
        summary["unreached"] += len(_held)
    summary["unreached"] += sum(1 for _ in it)
    summary["seconds"] = round(time.time() - t0, 1)
    _progress(force=True)
    print(f"PRE-WARM: {summary['workers']} worker(s) warmed {summary['warmed']} cell(s) in "
          f"{summary['seconds']:.0f}s ({summary['hit']} already cached, {summary['failed']} "
          f"failed, {summary['unreached']} not reached before the build budget)"
          + (f"; failures by kind {summary['failures']}" if summary["failures"] else ""))
    if summary["failure_reasons"]:
        print(f"PRE-WARM failure reasons: {summary['failure_reasons']}", flush=True)
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


def structural_trial_census(cells) -> dict:
    """The effective-trial ledger's census of this sweep's cells (family, symbol, timeframe,
    params), raw beside effective; the per-family rows are capped so the report stays small."""
    from libs.research.trial_ledger import census, trial_from_record
    doc = census(trial_from_record(c, index=i) for i, c in enumerate(cells)).to_dict()
    fams = sorted(doc.get("families", {}).values(), key=lambda f: -int(f.get("n_raw", 0)))
    doc["families"] = fams[:50]
    doc["note"] = ("descriptor/parameter participation ratio per family; reported beside the "
                   "sealed fixed charge (n_trials), never in place of it")
    return doc


def lifetime_trial_report(families) -> dict:
    """`lifetime_trials` and per-family trials from the experiment ledger (V21), A REPORT ONLY.

    NO TRIAL COUNT FROM THIS LEDGER EVER REACHES A VERDICT (principal, 2026-10-07: "we never
    charge trials like that ... no extra penalty trials inflated charges anything ever"). The
    deflated-Sharpe hurdle is the fixed per-cell bar `gate_policy.dsr_hurdle_inputs`; this count
    is published beside the verdicts so the desk's search volume stays visible, nothing more.

    Read from the ledger file `pf_allocator` writes hourly, through the module's own path, and
    never recomputed here: `experiment_ledger.family_trials` falls back to `lifetime(write=True)`
    when that file is unreadable, and the judge must not write another organ's artifact. An
    absent ledger is UNMEASURED with the writer named; a family the ledger does not list is
    `None`, not 0.
    """
    fams = sorted({str(f) for f in families if f})
    note = ("REPORTED ONLY: no lifetime, union or per-family count enters any verdict; the "
            "deflated-Sharpe hurdle is the fixed per-cell bar (gate_policy.dsr_hurdle_inputs)")
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
    if (isinstance(ds.index, pd.DatetimeIndex) and ds.index.tz is None
            and ds.index.dtype == np.dtype("datetime64[ns]")):
        # Already tz-naive NANOSECOND datetimes (every cached series): the same values in the
        # same unit, with no Python object per date. `to_datetime(list(...))` of such an index
        # returns ns on every pandas. Any other unit takes the original path below, which is
        # ns on pandas 2 and the index's own unit on pandas 3 (audit on b879ac50).
        return pd.DatetimeIndex(ds.index.to_numpy()).normalize()
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


#: Registry fields without which the engine's cost for a symbol is a default, not a measurement.
COST_BASIS_FIELDS = ("median_spread_pts", "tick_size", "tick_value", "contract_size",
                     "swap_long", "swap_short")


def registry_cost_basis(sym: str, meta: dict) -> dict:
    """Whether the engine priced `sym` from measured registry numbers. UNMEASURED otherwise.

    `Costs.from_symbol` silently falls back on absent fields (swap 0, quote_per_account 1.0, a
    0.05 spread floor), which prices an unknown cost as zero. This names every missing field so
    the swap_cost stage can fail closed on it instead.
    """
    row = (meta or {}).get(sym) or {}
    missing = []
    for f in COST_BASIS_FIELDS:
        v = row.get(f)
        if v is None or isinstance(v, bool):
            missing.append(f)
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            missing.append(f)
            continue
        if f in ("median_spread_pts", "tick_size", "tick_value", "contract_size") and not fv > 0:
            missing.append(f)
    if not row:
        return {"measured": False, "why": f"{sym or '?'} is absent from the universe registry"}
    if missing:
        return {"measured": False, "why": f"{sym} registry lacks {', '.join(missing)}"}
    return {"measured": True, "why": "spread, commission conversion and swap from the registry"}


#: THE LOOK-AHEAD GUARD BINDS HERE (2026-10-13). A cell an LLM proposed or labelled was proposed
#: by a model that has READ the history it is about to be judged on, so the days before that
#: model's evidence start are contaminated: they may be built, never counted. Two sources name
#: the start: the cell's own `lookahead_guard.evidence_from` (carried from the docket spec), and
#: the unsealed lab's map (`research/llm_lab_roles.record_evidence_start`): cell id -> {"from",
#: "sym", "family", "params"}, which still binds after a dedup or an alias drops the stamp. The
#: LATEST start wins and every earlier day is dropped from BOTH cost arms before any gate reads
#: the series, so in-sample screen, CPCV, walk-forward, DSR, PBO, SPA and the lockbox all see
#: only post-guard data. A cell with too few days left is judged on what it has.
#:
#: IT FAILS CLOSED (audit must-fix 3). A cell that carries LLM provenance (a `lookahead_guard`
#: stamp, or an llm_lab producer) but no readable start -- an unparseable date, or an unreadable
#: map -- is HELD: its series is emptied, so the observations gate records it UNMEASURED with the
#: reason, and nothing it built counts. Only a cell with no LLM provenance at all and no map
#: entry is untouched.
EVIDENCE_START = DATA / "llm_lab" / "evidence_start.json"
_EVIDENCE_CACHE: dict[str, Any] = {"mtime": None, "map": {}, "by_cell": {}, "error": ""}
EVIDENCE_HOLD = "HOLD"
#: Spec keys every cell-dict rebuild in `_build_specs` carries onto the cell (cached and fresh).
CARRIED_SPEC_KEYS = ("screen_read_until", "lookahead_guard", "producer", "source")


def merge_llm_provenance(spec: dict[str, Any], row: dict[str, Any]) -> None:
    """Fold one docket row's LLM provenance into its cell's spec, failing CLOSED across
    duplicate rows: the LATEST guard start wins, an unreadable one wins over any readable one
    (so the cell is held), and an llm_lab producer or source is never overwritten by a row
    without one."""
    guard = row.get("lookahead_guard")
    if isinstance(guard, dict):
        have = spec.get("lookahead_guard")
        if not isinstance(have, dict):
            spec["lookahead_guard"] = dict(guard)
        else:
            old, new = _day(have.get("evidence_from")), _day(guard.get("evidence_from"))
            if old is not None and (new is None or new > old):
                spec["lookahead_guard"] = dict(guard)
    for k in ("producer", "source"):
        v = row.get(k)
        if v is None:
            continue
        if spec.get(k) is None or ("llm_lab" in str(v) and "llm_lab" not in str(spec[k])):
            spec[k] = v


def _evidence_starts() -> tuple[dict[str, Any], dict[tuple[str, str], list[Any]], str]:
    """(map, rows by (sym, family), error). An ABSENT map is no error; an unreadable one is."""
    try:
        mtime = EVIDENCE_START.stat().st_mtime
    except OSError:
        return {}, {}, ""
    if _EVIDENCE_CACHE["mtime"] != mtime:
        err = ""
        try:
            raw = json.loads(EVIDENCE_START.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            err = f"evidence-start map unreadable ({type(exc).__name__})"
            print(f"  {err}: every LLM-born cell is HELD")
            raw = {}
        if not isinstance(raw, dict):
            err = err or "evidence-start map is not an object"
            raw = {}
        by_cell: dict[tuple[str, str], list[Any]] = {}
        for row in raw.values():
            if isinstance(row, dict) and row.get("sym") and row.get("family"):
                by_cell.setdefault((str(row["sym"]), str(row["family"])), []).append(row)
        _EVIDENCE_CACHE.update({"mtime": mtime, "map": raw, "by_cell": by_cell, "error": err})
    return _EVIDENCE_CACHE["map"], _EVIDENCE_CACHE["by_cell"], _EVIDENCE_CACHE["error"]


def llm_born(c: dict[str, Any]) -> bool:
    """The cell carries LLM provenance: a look-ahead stamp, or an llm_lab producer."""
    if isinstance(c.get("lookahead_guard"), dict):
        return True
    return any("llm_lab" in str(c.get(k) or "") for k in ("producer", "source", "origin"))


def _day(raw: Any) -> str | None:
    s = str(raw or "")[:10]
    try:
        pd.Timestamp(s)
    except (ValueError, TypeError):
        return None
    return s if len(s) == 10 else None


def evidence_from(c: dict[str, Any]) -> str | None:
    """The cell's evidence start, EVIDENCE_HOLD, or None (no LLM provenance, no map entry).

    Matches by the cell's own stamp, by exact id, and by (symbol, family) with the donated params
    a subset of the cell's own (the compiler may have filled in defaults); the LATEST date wins.
    """
    starts, by_cell, err = _evidence_starts()
    params = dict(c.get("params") or {})
    hits: list[str | None] = []
    guard = c.get("lookahead_guard")
    if isinstance(guard, dict):
        hits.append(_day(guard.get("evidence_from")))
    try:
        row = starts.get(cell_id({"sym": c["sym"], "family": c["family"], "params": params}))
    except Exception:
        row = None
    if row is not None:
        hits.append(_day(row.get("from") if isinstance(row, dict) else row))
    for cand in by_cell.get((str(c.get("sym")), str(c.get("family"))), []):
        donated = cand.get("params") or {}
        if donated and all(params.get(k) == v for k, v in donated.items()):
            hits.append(_day(cand.get("from")))
    if any(h is None for h in hits) or (err and llm_born(c)):
        return EVIDENCE_HOLD
    if not hits:
        return EVIDENCE_HOLD if llm_born(c) else None
    return max(h for h in hits if h)


def evidence_trim(c: dict[str, Any], ds: Any) -> Any:
    """`ds` without the days before the cell's evidence start; empty when the cell is HELD;
    unchanged when it has no LLM provenance and no map entry."""
    if ds is None or len(ds) == 0:
        return ds
    ev = evidence_from(c)
    if not ev:
        return ds
    if ev == EVIDENCE_HOLD:
        c["_evidence_from"] = "UNMEASURED"
        c["_series_error"] = ("look-ahead guard: LLM-born cell with no readable evidence start "
                              "(stamp unparseable or map unreadable); held, not judged")
        c["_evidence_dropped_days"] = len(ds)
        return ds.iloc[0:0]
    try:
        idx = pd.DatetimeIndex(ds.index)
        cut = pd.Timestamp(ev)
        if idx.tz is not None:
            cut = cut.tz_localize(idx.tz)
        kept = ds[idx >= cut]
    except Exception as exc:
        # A start that cannot be applied is a start that is not honoured: hold, never pass.
        print(f"  evidence trim failed for {c.get('sym')}.{c.get('family')}: {exc}: HELD")
        c["_evidence_from"] = "UNMEASURED"
        c["_series_error"] = f"look-ahead guard: trim failed ({type(exc).__name__}); held"
        return ds.iloc[0:0]
    c["_evidence_from"] = ev
    c["_evidence_dropped_days"] = int(len(ds) - len(kept))
    if len(kept) == 0:
        # A start at or after the last day leaves nothing the model had not read: held with
        # the reason, never judged on an empty series that reads as a quiet pass.
        c["_series_error"] = (f"look-ahead guard: evidence start {ev} is after the last day; "
                              f"no post-guard days; held, not judged")
    return kept


def _cell_series(cells: list, meta: dict) -> tuple[list, int]:
    """Each cell's FULL 1x daily series, and its 3x arm stashed on the cell, in ONE pass per cell.

    PER-CELL AND MATRIX-FREE: nothing here reads another cell, so it may run inside a shard of
    a sharded sweep (`shard_worker`) and give exactly what the unsharded sweep computes. Returns
    the series in the order of `cells` (None where none could be built) and the cache-hit count.
    The lockbox carve happens after, on the union, in `run_gauntlet`.
    """
    daily = []
    hits = 0
    for c in cells:
        try:
            # SHARDED SWEEP: the owning shard already computed this cell's FULL series (possibly
            # None) with this same function, and the merge takes it exactly as computed.
            if "_shard_ds" in c:
                daily.append(c["_shard_ds"])
                continue
            # Signals are counted before they are released below, so "fired but never traded"
            # and "never fired" are two causes; a cached cell has no signals in hand and reads
            # None. Kept ON THE CELL, with any series exception below, so a shard's count and
            # error ride its pickle into the merge exactly as the unsharded sweep records them.
            c["_n_signals"] = None if c.get("sigs") is None else len(c.get("sigs") or [])
            if c.get("_cached_ds") is not None:
                daily.append(evidence_trim(c, c["_cached_ds"]))
                hits += 1
                continue
            last_day = c.get("_last_day")
            ds = _series_trim_partial(daily_series(c["df"], c["sigs"], c["costs"]), last_day)
            c["_fresh_ds"] = ds          # cached FULL; the guard is applied on every read
            daily.append(evidence_trim(c, ds))
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
                    costs3 = _stress_costs(c["costs"], c["sym"], meta.get(c["sym"], {}),
                                           COST_SCENARIO)
                    c["_fresh_ds3"] = _series_trim_partial(
                        daily_series(c["df"], c["sigs"], costs3), last_day)
                except Exception as exc3:
                    print(f"  FAIL-3x {c['sym']}.{c['family']}: {exc3}")
                    c["_fresh_ds3"] = None
        except Exception as e:
            print(f"  FAIL {c['sym']}.{c['family']}: {e}")
            # WHY A SERIES IS MISSING: the exception used to reach stdout only, and the verdict
            # read "no daily series", which `name_unknowns` then filed as a spec that never fires.
            c["_series_error"] = f"{type(e).__name__}: {str(e)[:200]}"
            daily.append(None)
        finally:
            # RELEASE. `df` is a shared LRU frame and costs nothing to drop; `sigs` is this
            # cell's own signal list and is the thing that accumulates.
            c["df"] = c["sigs"] = c["costs"] = None
    return daily, hits


def _cell_series_x3(cells: list) -> list:
    """The FULL 3x-cost series collected from `_cell_series`'s pass, caching fresh pairs."""
    # 3x cost series
    # ALREADY COMPUTED ABOVE, in the same pass that had the frames in hand. This loop now only
    # collects and caches; it holds no bars and builds no signals.
    daily_x3 = []
    for c in cells:
        try:
            if "_shard_ds3" in c:
                daily_x3.append(c["_shard_ds3"])
                continue
            if c.get("_cached_ds3") is not None:
                daily_x3.append(evidence_trim(c, c["_cached_ds3"]))
                continue
            ds3 = c.get("_fresh_ds3")
            daily_x3.append(evidence_trim(c, ds3))
            if c.get("_fresh_ds") is not None and ds3 is not None and c.get("_ckey"):
                cache_save(c["_ckey"], c["_fresh_ds"], ds3)
        except Exception:
            daily_x3.append(None)
    return daily_x3


#: ------------------------------------------------------------------ JUDGE SPEED (2026-10-14)
#: VERDICT-PRESERVING ONLY. Everything in this block computes exactly what the line it replaced
#: computed -- the same arrays, the same summation order, the same calendar key -- and is proven
#: on a >=300-cell batch by `judging/gauntlet_speed/gauntlet_speed_harness.py`, which asserts the
#: full result JSON of the old and new judge equal. No threshold, trial charge or gate moves.


def _cpcv_test_sets(n: int) -> list[np.ndarray]:
    """`[np.asarray(sp.test) for sp in CPCV(n_groups=6, n_test_groups=2).split(n)]`, test side only.

    A split's TEST set is a function of `n` alone -- purge and embargo only ever remove TRAIN
    rows -- yet `CPCV.split` also rebuilds every split's train set as a Python set of n ints and
    walks it, for every cell: 3.5 ms a cell, the largest single cost of judging one (cProfile,
    2026-10-14). These are `CPCV.split`'s own test lines, verbatim (same groups, same order of
    combinations, same concatenate + sort), with the train side dropped; the splitter's guard
    is kept so a short series raises exactly what it raised."""
    from itertools import combinations
    splitter = CPCV(n_groups=6, n_test_groups=2)
    if n < splitter.n_groups:
        raise ValidationError("n_samples must be >= n_groups")
    groups = np.array_split(np.arange(n), splitter.n_groups)
    return [np.sort(np.concatenate([groups[i] for i in test_ids]))
            for test_ids in combinations(range(splitter.n_groups), splitter.n_test_groups)]


def _fast_dates(s: Any) -> bool:
    """True when `s.index` is a tz-naive DatetimeIndex with no NaT, sorted ascending: the one
    shape for which a positional slice at `searchsorted(cut)` IS the boolean mask `< cut`."""
    idx = getattr(s, "index", None)
    return (isinstance(idx, pd.DatetimeIndex) and idx.tz is None and not idx.hasnans
            and idx.is_monotonic_increasing)


#: Datetime units, coarsest first: a cut converts losslessly into an index unit at or above it.
_UNIT_RANK = {"s": 0, "ms": 1, "us": 2, "ns": 3}


def _split_at(s: pd.Series, cut: Any) -> tuple[pd.Series, pd.Series]:
    """`(s[s.index < cut], s[s.index >= cut])`, by one binary search when the index allows it.

    Any other index (python dates from a fresh build, tz-aware, unsorted, NaT), a cut that is
    not a tz-naive Timestamp, or a cut FINER than the index's unit takes the boolean masks
    exactly as before, including any error they raise. pandas 3 `searchsorted` refuses a cut it
    cannot convert losslessly ("Cannot losslessly convert units") where the masks compare it
    fine (audit HOLD on b879ac50), so that case never reaches the search, and any error the
    search raises falls back to the masks."""
    if (isinstance(cut, pd.Timestamp) and cut.tz is None and cut is not pd.NaT
            and _fast_dates(s)
            and _UNIT_RANK.get(str(getattr(cut, "unit", "")), 99)
            <= _UNIT_RANK.get(str(getattr(s.index, "unit", "")), -1)):
        try:
            k = int(s.index.searchsorted(cut, side="left"))
        except (ValueError, TypeError, OverflowError):
            pass
        else:
            return s.iloc[:k], s.iloc[k:]
    return s[s.index < cut], s[s.index >= cut]


class _UnionDates:
    """The union of every series' dates as ONE index, for `gate_policy.lockbox_cut`.

    `lockbox_cut` takes `sorted({d for s in series for d in s.index})`, iterating every date of
    every cell as a Python object (1.4 ms a cell). It reads nothing but `.index`, so handing it
    one object whose index is already that sorted, de-duplicated union yields the same list and
    the same key -- the pattern `_run_shards` already uses for the sharded sweep's cut. Built
    only when every index is a tz-naive DatetimeIndex of ONE dtype with no NaT (equal values are
    then equal Timestamps); otherwise `of` returns None and the caller passes the series."""

    def __init__(self, index: pd.DatetimeIndex) -> None:
        self.index = index

    @classmethod
    def of(cls, series: list[Any]) -> _UnionDates | None:
        idxs = [s.index for s in series if s is not None]
        if not idxs or not all(isinstance(i, pd.DatetimeIndex) for i in idxs):
            return None
        dtype = idxs[0].dtype
        if any(i.dtype != dtype or i.tz is not None or i.hasnans for i in idxs):
            return None
        return cls(pd.DatetimeIndex(np.unique(np.concatenate([i.to_numpy() for i in idxs]))))


#: THE PURE PER-CELL READS, MEMOISED BY CONTENT. Each entry is a function of the exact bytes of
#: a cell's development (and held-out) series and of constants -- never of a cell's identity, the
#: sweep, a file or the live terminal -- so a repeat of the same bytes in this process (a clone
#: cell, or a later batch in one process) is answered without recomputing it. The key is the
#: series' shape plus a 128-bit BLAKE2b of its float64 bytes, so a hit is an identical input and
#: the answer is the one already computed. Bounded LRU; values are immutable tuples and every
#: caller receives fresh dicts. `economic_prior` and `swap_cost` read the cell, the registry and
#: the live cost fence and are NEVER memoised.
_PURE_MEMO: OrderedDict[tuple[Any, ...], Any] = OrderedDict()
_T = TypeVar("_T")
#: `_local_pure`'s reads: (sr, cpcv mean, folds, wf passed, wf oos, wf stability, ev).
_LocalReads = tuple[float, float, int, bool, float, float, float]
_PURE_MEMO_MAX = 50_000


def _fp(a: Any) -> tuple[Any, ...] | None:
    """(shape, BLAKE2b-128 of the float64 bytes) of an array or Series; None for None."""
    if a is None:
        return None
    v = np.ascontiguousarray(np.asarray(a, dtype=float))
    return (v.shape, hashlib.blake2b(v.tobytes(), digest_size=16).digest())


def _memo(key: tuple[Any, ...], compute: Callable[[], _T]) -> _T:
    """`compute()`, or the value it returned for this exact key earlier in this process."""
    try:
        hit = _PURE_MEMO[key]
    except KeyError:
        pass
    else:
        _PURE_MEMO.move_to_end(key)
        return cast(_T, hit)
    val = compute()
    _PURE_MEMO[key] = val
    if len(_PURE_MEMO) > _PURE_MEMO_MAX:
        _PURE_MEMO.popitem(last=False)
    return val


def _local_pure(arr: np.ndarray) -> _LocalReads:
    """(in-sample Sharpe, CPCV mean OOS Sharpe, CPCV folds, walk-forward passed, its OOS Sharpe,
    its stability, EV): `_cell_local_stages`'s arithmetic on the development series, unchanged."""
    def compute() -> _LocalReads:
        sr = sharpe_ratio(arr)
        oos = []
        for te in _cpcv_test_sets(len(arr)):
            if len(te) >= 30:
                oos.append(sharpe_ratio(arr[te]))
        cpcv_mean = float(np.mean(oos)) if oos else 0.0
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
        return (float(sr), cpcv_mean, len(oos), bool(wf_status is WalkForwardStatus.PASSED),
                wf_oos, wf_stab, float(arr.mean()))
    return _memo(("local", _fp(arr)), compute)


def _dsr_read(arr: np.ndarray, dsr_bar: float) -> tuple[bool, float, float]:
    """(passed, dsr, sr0) of `deflated_sharpe_ratio` at the fixed per-cell bar -- the call
    `run_gauntlet` makes, on `dsr_hurdle_inputs(len(arr))` and the law's `dsr_bar`."""
    from research.gate_policy import dsr_hurdle_inputs

    def compute() -> tuple[bool, float, float]:
        n_cell, cell_var, _basis = dsr_hurdle_inputs(len(arr))
        d = deflated_sharpe_ratio(arr, n_trials=n_cell, variance_of_sharpes=cell_var,
                                  threshold=dsr_bar)
        return (bool(d.passed), float(d.dsr), float(d.sr0_threshold))
    return _memo(("dsr", _fp(arr), float(dsr_bar)), compute)


def _lockbox_read(held: Any, arr: np.ndarray, sr0: float) -> dict[str, Any]:
    """`lockbox_stage(held, sharpe_ratio, dev=arr, sr0=sr0)`, as a fresh dict every call."""
    from research.gate_policy import lockbox_stage
    key = ("lockbox", _fp(held), _fp(arr), float(sr0))
    return dict(_memo(key, lambda: tuple(
        lockbox_stage(held, sharpe_ratio, dev=arr, sr0=sr0).items())))


def _program_reads(arr: np.ndarray, held: Any, pre: dict[str, Any] | None, *, threshold: float
                   ) -> tuple[tuple[bool, float, float], dict[str, Any]]:
    """The deflated-Sharpe read and the lockbox stage of ONE cell, both pure functions of its
    development series, its held-out tail and the law's DSR bar (T8: no sweep quantity enters
    either). `pre` is what the cell's shard computed with these same functions; it is used only
    when it was computed at this bar on a series of this length and tail, and otherwise the
    merge computes both itself -- a mismatch costs time, never a verdict. `threshold` is the
    law's DSR bar."""
    dsr_bar = threshold
    n_held = 0 if held is None else len(held)
    if (isinstance(pre, dict) and pre.get("dsr_bar") == float(dsr_bar)
            and pre.get("n") == len(arr) and pre.get("n_held") == n_held
            and isinstance(pre.get("dsr"), tuple) and isinstance(pre.get("lockbox"), dict)):
        return pre["dsr"], dict(pre["lockbox"])
    dsr = _dsr_read(arr, dsr_bar)
    return dsr, _lockbox_read(held, arr, dsr[2])


def _screen_read_clean(ru: Any, cut: Any) -> bool:
    """Whether a proposer's screen stamp `ru` lies strictly before the cell's cut (never on error).

    The ONE rule, read by `run_gauntlet` and by a shard's publication (`_shard_verdict`)."""
    try:
        _seen = pd.Timestamp(str(ru))
        if cut is not None and getattr(cut, "tzinfo", None) is not None:
            _seen = _seen.tz_localize(cut.tzinfo) if _seen.tzinfo is None else _seen
        return bool(cut is not None and _seen < cut)
    except (TypeError, ValueError):
        return False


def _dsr_stage(n_obs: int, dsr: tuple[Any, Any, Any]) -> dict[str, Any]:
    """The `deflated_sharpe` stage's cell-local fields, in the verdict's key order: a pure
    function of the cell's own length and its read at the fixed per-cell bar (T8). The reported
    sweep-level fields are appended by `run_gauntlet` after these, never read by a verdict."""
    from research.gate_policy import dsr_hurdle_inputs
    _n_cell, _cell_var, _n_basis = dsr_hurdle_inputs(n_obs)
    _dsr_passed, _dsr_val, _dsr_sr0 = dsr
    return {"passed": bool(_dsr_passed), "dsr": round(float(_dsr_val), 4),
            "sr0": round(float(_dsr_sr0), 4), "n_trials": _n_cell,
            "trial_basis": _n_basis,
            "variance_of_sharpes": round(_cell_var, 6),
            "variance_basis": "per_cell_null_1/(T-1)"}


def _unmeasured_verdict(_c: dict[str, Any], _d: Any, _pre: int | None, *,
                        screened: bool) -> dict[str, Any]:
    """The UNMEASURED verdict of one cell the gates could not rule on (under 60 development
    days, no series, or refused by the screen). The ONE builder, read by `run_gauntlet` and by a
    shard's publication, so the row a shard publishes is the row the merge writes."""
    _n = 0 if _d is None else len(_d)
    _nsig = _c.get("_n_signals")
    # THE CAUSE, NAMED BY THE ONE ORGAN THAT CAN SEE IT (2026-09-30). Every UNKNOWN carries
    # it, and `failed_gates` is never empty: the observations gate is the gate that stopped it.
    _err = _c.get("_series_error")
    _why_unknown = ("screened_past_cut" if screened
                    else classify_unknown(_d, _pre, _nsig, errored=bool(_err)))
    return {
        "cell": cell_id({"sym": _c["sym"], "family": _c["family"],
                         "params": _c.get("params") or {}}),
        "sym": _c["sym"], "family": _c["family"], "days": _n,
        "params": _c.get("params") or {}, "timeframe": _c.get("timeframe"),
        "days_before_lockbox": _pre, "n_signals": _nsig,
        "unknown_reason": _why_unknown,
        "failed_gates": ["observations"], "n_failed_gates": 1,
        **({"series_error": _err} if _err else {}),
        "passed": False, "unmeasured": True,
        "stages": {"observations": {
            "passed": False, "days": _n, "required": 60,
            "why": ("no daily series could be built from this cell's signals"
                    if _d is None else
                    f"only {_n} daily observations; CPCV with purge+embargo and the "
                    f"walk-forward folds require 60. This is UNMEASURED, not a failure: "
                    f"the cell fires too rarely to be judged, which is a fact about the "
                    f"SEARCH that proposed it, not evidence against the edge")}},
    }


#: THE PER-CELL GATES, IN THE ORDER THEY SIT IN A VERDICT'S `stages`. `stages` is
#: insertion-ordered and `terminal_gate` is its FIRST failure, so this order is part of the
#: verdict: `run_gauntlet` rebuilds `stages` as HEAD, deflated_sharpe, pbo, reality_check_spa,
#: MID, lockbox, TAIL -- exactly the sequence the gates were always evaluated in.
CELL_LOCAL_HEAD = ("economic_prior", "in_sample_screen")
CELL_LOCAL_MID = ("cpcv", "walk_forward", "stress_costs")
CELL_LOCAL_TAIL = ("expected_value", "swap_cost")


def _cell_local_stages(c: dict, arr: np.ndarray, x3_ds, meta: dict) -> dict:
    """Every gate that reads ONE cell's own development-window series and nothing of the sweep.

    THE LINE THE SHARDED SWEEP IS DRAWN ON. `deflated_sharpe` (the trial charge, the lifetime
    ledger and the variance of Sharpes), `pbo`, `reality_check_spa` and `lockbox` (judged at the
    union's DSR hurdle `sr0`, on the tail after the union's calendar cut) are PROGRAM-LEVEL: they
    are never computed here and never inside a shard -- `run_gauntlet` computes them once, on the
    union. Everything returned here is a function of (cell, its 1x development series, its 3x
    development series, meta) alone, which is what lets a shard compute it and the merge use it
    unchanged.
    """
    # In-sample, CPCV, walk-forward and EV: the pure reads of the development series.
    sr, cpcv_mean, n_folds, wf_passed, wf_oos, wf_stab, ev = _local_pure(arr)
    stages = {
        "economic_prior": economic_prior(c),
        "in_sample_screen": {"passed": bool(sr > 0.0), "sharpe": round(float(sr), 4)},
    }

    # CPCV
    stages["cpcv"] = {"passed": bool(cpcv_mean > 0.0),
                      "mean_oos_sharpe": round(cpcv_mean, 4), "folds": n_folds}

    # Walk Forward
    stages["walk_forward"] = {
        "passed": wf_passed,
        "oos_sharpe": round(wf_oos, 4), "stability": round(wf_stab, 4)
    }

    # Stress costs (3x)
    # x3_ds: this cell's 3x-cost series on the development window (argument)
    exp3 = float(x3_ds.to_numpy(float).mean()) if x3_ds is not None and len(x3_ds) > 0 else 0.0
    stages["stress_costs"] = {"passed": bool(exp3 > 0.0), "exp_x3": round(exp3, 4)}

    # Expected Value
    stages["expected_value"] = {"passed": bool(ev > 0.0), "ev": round(ev, 4)}

    # SWAP, WHICH THE ENGINE DOES NOT MODEL AT ALL (added 2026-09-14).
    #
    # `mt5desk.engine.Costs` carries spread_per_lot, commission_per_lot, contract_oz and
    # quote_per_account -- and nothing else. Grep it for "swap" and it is empty. So every
    # certificate this desk has ever minted was judged with ZERO overnight financing cost,
    # and `stress_costs` above stresses that model at 3x, which stresses a cost that was
    # never counted rather than the one that dominates.
    #
    # For an intraday cell that is correct and this gate does nothing. For a family that
    # holds through rollover BY CONSTRUCTION it is the whole ballgame. Measured on the four
    # live overnight_gap_decay sleeves, round-trip cost as a fraction of a 2xATR20 stop:
    # CHFDKK 0.105R, EURNOK 0.127R, GBPNOK 0.202R, GBPMXN 0.246R -- against a +0.135R
    # expectancy assumption, the last two cost MORE THAN THE ENTIRE EDGE. EURUSD is 0.025R
    # for scale. All four carry the same parameter hash: one hypothesis replicated onto four
    # instruments whose cost structure destroys it, at the thinnest liquidity hour of the day.
    #
    # A CERTIFICATE JUDGED AT COSTS THE BROKER DOES NOT CHARGE IS NOT EVIDENCE. It is a
    # well-documented opinion.
    #
    # UNKNOWN COST IS UNKNOWN EDGE (principal, 2026-09-29). This stage used to PASS whenever
    # the live terminal could not be read, which is every host the gauntlet runs on without
    # one -- so an unpriced instrument certified as though financing were free. Two readings
    # now, and the cell needs one of them to be a real measurement:
    #   1. the REGISTRY basis the engine itself charged: `Costs.from_symbol` prices spread,
    #      commission (via tick_value) and swap (worse side, per night held) from
    #      universe.json, so a symbol carrying all of those was backtested net of them;
    #   2. the live-terminal cost-to-edge fence, which can still REFUSE on a measured cost.
    # A symbol missing any registry field is UNMEASURED, and UNMEASURED fails closed.
    _basis = registry_cost_basis(str(c.get("sym") or c.get("symbol") or ""), meta)
    try:
        from research.cost_to_edge import verdict as _cost_verdict
        _refuse, _why, _cost = _cost_verdict(
            str(c.get("sym") or c.get("symbol") or ""),
            str(c.get("family") or ""), ev)
    except Exception as _exc:
        _refuse, _why, _cost = False, "", {
            "measured": False, "why": f"terminal unreadable ({type(_exc).__name__})"}
    _live_measured = bool(_cost.get("measured"))
    stages["swap_cost"] = {
        "passed": bool((_basis["measured"] or _live_measured) and not _refuse),
        "measured": bool(_basis["measured"] or _live_measured),
        "registry_basis": _basis,
        "live_measured": _live_measured,
        "total_cost_r": _cost.get("total_cost_r"),
        "swap_r": _cost.get("swap_r"),
        "holds_overnight": _cost.get("holds_overnight"),
        "why": (_why if _refuse else
                "cost within the bar" if _live_measured else
                "priced by the registry basis the engine charged" if _basis["measured"] else
                f"UNMEASURED cost fails closed: {_basis['why']}; "
                f"live: {_cost.get('why') or 'unread'}"),
    }
    return stages


def _eff_result(thread: threading.Thread, box: dict[str, Any]) -> dict[str, Any]:
    """The census thread's `_safe` result; it is joined, so this is never a partial value."""
    thread.join()
    return box.get("v") or _unmeasured("effective_trials: census thread returned nothing")


def run_gauntlet(cells: list, hunt_name: str, meta: dict) -> dict:
    """Run full 10-gate gauntlet on a list of cells."""
    print(f"\n=== GAUNTLET: {hunt_name} ({len(cells)} cells) ===")
    # The content memo is keyed on the series' bytes, not on the module's constants (WF_*,
    # LOCKBOX_*, ...): it lives for one judging call, so nothing set between calls goes stale.
    _PURE_MEMO.clear()

    # Build daily series
    daily, hits = _cell_series(cells, meta)
    if hits:
        print(f"  series cache: {hits}/{len(cells)} cell(s) loaded (unchanged data-day); "
              f"{len(cells) - hits} computed fresh")

    # ------------------------------------------------------------------ THE LOCKBOX, CARVED FIRST
    # GATE 9 WAS GATE 7 READ TWICE until v3 of the policy: `lockbox` passed on `wf_oos >= 0`,
    # the walk-forward gate's own OOS Sharpe, and 58/58 authority certificates carried
    # lockbox_sharpe == walk_forward.oos_sharpe exactly. The cut happens HERE, before the drop
    # census and the program matrix, so PBO/SPA/DSR/CPCV/walk-forward/stress/EV all see the
    # development window only, and the held-out tail is read by the lockbox gate alone. One
    # calendar cut for the whole sweep (gate_policy.lockbox_cut), so every column holds out the
    # same period. The FULL series stays in the cache: the carve is re-derived every sweep.
    from research.gate_policy import LOCKBOX_FRAC, carve_lockbox, lockbox_cut
    # THE LAW THIS SWEEP IS JUDGED UNDER, resolved once and published with the verdicts (S01):
    # the DSR bar, the gate count and the held-out share, each never looser than the constant
    # above unless the principal ratified the rule set that loosens it.
    law = constitution_thresholds(LOCKBOX_FRAC)
    dsr_bar = float(law["dsr_threshold"])
    gates_required = math.ceil(float(law["gates_required"]))
    lockbox_frac = float(law["lockbox_min_fraction"])
    print(f"  constitution {law.get('status')}: dsr>={dsr_bar} gates>={gates_required} "
          f"lockbox>={lockbox_frac:.0%}")
    # One pre-built union index in place of every series (`_UnionDates`): the same key.
    _union = _UnionDates.of(daily)
    _lock_cut = (lockbox_cut(daily, frac=lockbox_frac) if _union is None
                 else lockbox_cut([_union], frac=lockbox_frac))
    # The history each cell HAD before the carve, so an UNKNOWN can say whether the cell fired
    # too rarely or fired plenty and lost its development window to the campaign-wide cut.
    _pre_carve_days = [None if d is None else len(d) for d in daily]
    _full_daily = list(daily)
    if _lock_cut is None:
        daily, lock_daily = carve_lockbox(daily, _lock_cut)
    else:
        # `carve_lockbox`'s two masks per series, by one binary search where exact (`_split_at`).
        _carved = [(None, None) if _s is None else _split_at(_s, _lock_cut) for _s in daily]
        daily, lock_daily = [_d for _d, _ in _carved], [_h for _, _h in _carved]
        del _carved
    # A CHART WHOSE HISTORY BEGINS AFTER THE CUT HAS NO DEVELOPMENT WINDOW (2026-09-30). The cut is
    # taken from the union of every cell's days, which the long H1 histories dominate (2018 on),
    # so it lands ~20% from the end: 2024-12-19 on this tree. A cell on a chart whose parquet
    # starts after that -- XAUUSD M15 from 2025-11, M5 from 2026-06, every M1 file -- keeps ZERO
    # development days however often it fires (XAUUSD M15 mean_reversion_rsi: 219 trading days,
    # 0 after the carve), and it was reported UNKNOWN with days == 0, named "never_fires" and
    # parked as an unrunnable spec. Such a cell is carved at ITS OWN tail instead: the same
    # fraction, never under the lockbox floor, and only when that leaves the 60 development days
    # CPCV needs. The development/held-out separation is the same one every cell gets; only the
    # calendar position differs, and the verdict records which basis it was judged on. A cell
    # the campaign cut already leaves judgeable is never touched, so no existing verdict moves.
    # `cell_dev_cut` is the ONE rule, shared with a shard's `rule` phase (`_shard_rule`).
    _cell_cut = [cell_dev_cut(_s, _lock_cut, frac=lockbox_frac) for _s in _full_daily]
    for _k, _s in enumerate(_full_daily):
        if _s is not None and _cell_cut[_k] != _lock_cut:
            daily[_k], lock_daily[_k] = _split_at(_s, _cell_cut[_k])
    # A CELL WHOSE PROPOSER'S SCREEN READ PAST THIS CUT IS NOT JUDGED (2026-10-14, audit on
    # #392). The LLM lab's style screen reads a cell's signals before a lockbox it can only
    # estimate from bar days, and stamps the last day it read (`screen_read_until`). This sweep
    # knows the real cut; a cell whose development window does not END AFTER that day has had its
    # held-out data seen by the screen, so it fails closed exactly as a cell with no series does.
    _peeked = 0
    for _k, _c in enumerate(cells):
        _ru = _c.get("screen_read_until") if isinstance(_c, dict) else None
        if not _ru or daily[_k] is None:
            continue
        _clean = _screen_read_clean(_ru, _cell_cut[_k])
        if not _clean:
            daily[_k] = lock_daily[_k] = None
            _c["_screened_past_cut"] = True
            _peeked += 1
    if _peeked:
        print(f"  lockbox: {_peeked} cell(s) refused -- the style screen read past their cut")
    _own_cut_n = sum(1 for _c in _cell_cut if _c is not None and _c != _lock_cut)
    print(f"  lockbox: reserved from {_lock_cut} onward"
          + (f"; {_own_cut_n} short-history cell(s) carved at their own tail" if _own_cut_n
             else "") if _lock_cut is not None else
          "  lockbox: NONE -- campaign too short to reserve; every cell's gate 9 fails closed")

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

    # THE EFFECTIVE-TRIAL CENSUS, STARTED NOW AND READ AT THE END. It is a REPORT (it never sets
    # a bar) and a pure function of the cells' identities -- family, symbol, chart, params --
    # which nothing below writes. Its cost is one LAPACK `eigvalsh` per family (up to 2,500
    # members), 17 s of a 77 s 6,000-cell sweep (cProfile, 2026-10-14), and LAPACK releases the
    # GIL, so it runs beside the per-cell loop instead of after it. Same call, same `_safe`
    # wrapper, same result; only when it runs moves.
    _eff_box: dict[str, Any] = {}

    def _eff_census() -> None:
        _eff_box["v"] = _safe(lambda: structural_trial_census(cells), "effective_trials")

    _eff_thread = threading.Thread(target=_eff_census, name="gauntlet-effective-trials",
                                   daemon=True)
    _eff_thread.start()

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
    from research.gate_policy import fail_closed_trial_count
    # `charged_trial_count` fails closed to POLICY's number whenever the census cannot measure.
    try:
        from mt5desk.canonical import calibrated_census_report
        from research.gate_policy import charged_trial_count
        _census = calibrated_census_report(
            [matrix[:, k] for k in range(matrix.shape[1])],
            sd_sharpe=float(sharpes.std(ddof=1)) if len(sharpes) > 1 else 0.0)
        n_trials, _trial_basis = charged_trial_count(
            matrix.shape[1], _census.get("n_effective"), _census.get("method"))
    except Exception as _exc:
        n_trials = fail_closed_trial_count(matrix.shape[1])  # spec: fail_closed_to fixed_campaign_trials(597), NOT the batch tax
        _trial_basis = f"raw_cells_x7_fail_closed ({type(_exc).__name__})"
        _census = {"unavailable": str(_exc)[:120]}

    print(f"  Matrix: {matrix.shape}, n_trials={n_trials} ({_trial_basis}), "
          f"var_of_sharpes={sh_var} ({_var_basis}; measured this sweep {sh_var_measured:.6f})")
    t0 = time.time()

    # PBO AND SPA RUN BESIDE THE PER-CELL LOOP (2026-10-14). Both read only `matrix`, which nothing
    # below writes, and each draws its own fixed-seed RNG, so a thread computes exactly the number
    # the inline call did; most of their time is numpy on the whole matrix, which releases the
    # GIL. Their values enter each verdict only in the assembly pass after the loop, so every
    # verdict, its stage order and its terminal gate are as before. An exception in either is
    # re-raised at the join, PBO's first, as the inline order raised it.
    _prog_box: dict[str, object] = {}
    _prog_threads: list[threading.Thread] = []
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
        def _program_test(name: str, fn: Callable[[Any], Any]) -> None:
            try:
                _prog_box[name] = fn(matrix)
            except BaseException as exc:          # re-raised in the merging thread at the join
                _prog_box[name + "_exc"] = exc

        for _name, _fn in (("pbo", probability_backtest_overfitting), ("spa", hansen_spa)):
            _t = threading.Thread(target=_program_test, args=(_name, _fn), daemon=True,
                                  name=f"gauntlet-{_name}")
            _t.start()
            _prog_threads.append(_t)

    # 3x cost series
    daily_x3 = _cell_series_x3(cells)

    # The stress arm is judged on the same development window as the baseline, never the tail.
    if _lock_cut is not None:
        daily_x3 = [None if x is None or _cell_cut[_k] is None else _split_at(x, _cell_cut[_k])[0]
                    for _k, x in enumerate(daily_x3)]

    # THE DEFLATED-SHARPE HURDLE IS A FIXED PER-CELL BAR (principal, 2026-10-07: "everything is
    # always fixed n no extra penalty trials inflated charges anything ever"). No lifetime, union,
    # per-family, docket or census count enters it and EXPERIMENT_LEDGER.json is not read on this
    # path: until 2026-10-07 the charge was max(campaign, family lifetime, lifetime union) from
    # that ledger, and on any host without the ledger every cell failed closed.
    from research.gate_policy import TRIAL_COUNT_BASIS as _DSR_BASIS
    from research.gate_policy import dsr_hurdle_inputs

    # Per-cell stages (pass 1). The two program-level stage dicts are placed in their slot now
    # and filled in pass 2, once PBO and SPA have joined.
    _staged: list[tuple[dict[str, Any], str, int, dict[str, Any]]] = []
    for _idx, (orig_i, ds) in enumerate(valid):
        c = cells[orig_i]
        arr = ds.to_numpy(float)
        cid = cell_id(c)
        # THE CELL-LOCAL GATES: computed here, or -- in a sharded sweep -- by the shard that owned
        # the cell, with the same function on the same development window (`_cell_local_stages`).
        # A shard's stages are used only when it carved at THIS sweep's cut; anything else is a
        # merge fault and refuses the sweep before a single record is written.
        _local = c.get("_local_stages")
        if _local is not None and c.get("_local_cut") != _cell_cut[orig_i]:
            raise ShardMergeError(f"{cid}: shard ruled at cut {c.get('_local_cut')!r}, "
                                  f"this cell's cut is {_cell_cut[orig_i]!r} "
                                  f"(the union's is {_lock_cut!r})")
        # The shard's deflated-Sharpe and lockbox reads ride with its verified local stages.
        _pre = c.get("_local_program") if _local is not None else None
        if _local is None:
            _local = _cell_local_stages(c, arr, daily_x3[orig_i], meta)

        # In-sample
        stages = {k: _local[k] for k in CELL_LOCAL_HEAD}

        # Deflated Sharpe at the FIXED per-cell bar: the cell's own null variance 1/(T-1) at a
        # constant N (gate_spec `fixed_dsr_trials`), PSR >= 0.95 -- a per-cell t of about 2.8.
        # The lockbox reads use the same sr0.
        _n_cell, _cell_var, _n_basis = dsr_hurdle_inputs(len(arr))
        (_dsr_passed, _dsr_val, _dsr_sr0), _lock_st = _program_reads(
            arr, lock_daily[orig_i], _pre, threshold=dsr_bar)
        stages["deflated_sharpe"] = {
            **_dsr_stage(len(arr), (_dsr_passed, _dsr_val, _dsr_sr0)),
            # REPORTED ONLY, never an input to this verdict.
            "campaign_trials_reported": n_trials,
            "spec_variance_reported": round(sh_var, 6),
            "variance_measured_this_sweep": round(sh_var_measured, 6),
        }

        # PBO + SPA (program-level): their slots, filled in pass 2.
        stages["pbo"] = {}
        stages["reality_check_spa"] = {}

        # CPCV, walk-forward, stress costs (cell-local)
        for _k in CELL_LOCAL_MID:
            stages[_k] = _local[_k]

        # Lockbox: the reserved tail, which no gate above has read (policy v3).
        stages["lockbox"] = _lock_st
        stages["lockbox"]["cut"] = str(_cell_cut[orig_i])
        stages["lockbox"]["cut_basis"] = ("campaign" if _cell_cut[orig_i] == _lock_cut
                                          else "cell_own_tail (history begins after the "
                                               "campaign cut)")

        # Expected value, swap (cell-local)
        for _k in CELL_LOCAL_TAIL:
            stages[_k] = _local[_k]
        _staged.append((c, cid, len(arr), stages))

    for _t in _prog_threads:
        _t.join()
    if _prog_threads:
        for _name in ("pbo", "spa"):
            if _name + "_exc" in _prog_box:
                raise _prog_box[_name + "_exc"]  # type: ignore[misc]
        pbo = _prog_box["pbo"]
        pbo_val = float(pbo.pbo)  # type: ignore[attr-defined]
        pbo_ok = pbo_val <= PBO_THRESHOLD
        print(f"  PBO: {pbo_val:.4f} ({'PASS' if pbo_ok else 'FAIL'})")

        spa = _prog_box["spa"]
        spa_p = float(spa.p_value)  # type: ignore[attr-defined]
        spa_ok = spa_p < SPA_ALPHA
        print(f"  SPA: p={spa_p:.4f} ({'PASS' if spa_ok else 'FAIL'})")

    # Per-cell verdicts (pass 2), in the order of the cells.
    verdicts = []
    for c, cid, _days, stages in _staged:
        stages["pbo"].update({"passed": pbo_ok, "pbo": round(pbo_val, 4)})
        stages["reality_check_spa"].update({"passed": spa_ok, "p_value": round(spa_p, 4)})

        passed = all(s["passed"] for s in stages.values())
        # AND AT LEAST AS MANY GATES AS THE LAW IN FORCE REQUIRES (S01): a gate count the
        # constitution raises above what this sweep ran refuses rather than passes.
        if passed and sum(1 for s in stages.values() if s["passed"]) < gates_required:
            passed = False
        # WHICH GATE ACTUALLY STOPPED IT, AND WITHOUT THIS THE FUNNEL IS INVISIBLE.
        #
        # `stages` has carried every gate's verdict all along and the row never said which one
        # was terminal, so `_append_gate_ledger` fell through to its "UNKNOWN" default. Measured
        # 2026-09-13 on the box: 20,806 of 21,663 ledger rows read UNKNOWN. The desk could not
        # answer "why did this cell fail" for 96% of everything it has ever judged.
        #
        # THAT IS NOT A REPORTING NICETY, IT IS THE BOTTLENECK ITSELF. `gate_fails` counts how
        # often each gate refused ANY cell -- deflated_sharpe 18,372, cpcv 15,848,
        # in_sample_screen 15,787 -- and a cell can fail several, so those counts cannot say
        # which cells would pass everything ELSE. Only the terminal gate can, and it is the
        # question every throughput decision turns on: a cell whose sole obstacle is the
        # multiplicity charge is a candidate for the forward cure the gate spec already grants
        # (`cure_by_forward: true`), while a cell that also fails cpcv and walk_forward is not.
        #
        # `stages` is insertion-ordered in evaluation order, so the FIRST failure is the one that
        # stopped it. Recorded as `failed_gates` too, because "died at deflated_sharpe having
        # passed everything else" and "died at deflated_sharpe and four others" are the same
        # terminal gate and completely different prospects.
        _failed = [k for k, v in stages.items() if not v.get("passed")]
        verdicts.append({
            "cell": cid, "sym": c["sym"], "family": c["family"],
            "days": _days, "passed": passed, "stages": stages,
            "terminal_gate": ("PASSED" if passed
                              else _failed[0] if _failed else "constitution.gates_required"),
            "failed_gates": _failed,
            "n_failed_gates": len(_failed),
            # THE CURE LANE'S ELIGIBILITY, computed where the evidence is rather than re-derived
            # by a reader. The gate spec grants `cure_by_forward` on deflated_sharpe, so a cell
            # that fails ONLY that one has cleared every other test this desk applies and is
            # exactly what forward evidence was meant to adjudicate.
            "curable_by_forward": (not passed and len(_failed) == 1
                                   and _failed[0] == "deflated_sharpe"),
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
        _pre = _pre_carve_days[_i] if _i < len(_pre_carve_days) else None
        verdicts.append(_unmeasured_verdict(_c, _d, _pre,
                                            screened=bool(_c.get("_screened_past_cut"))))

    # EVERY VERDICT NAMES THE GATE THAT STOPPED IT (`terminal_stamp`), ruled or unmeasured.
    _terminal_defects = stamp_terminal(verdicts)
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
        # THE TIER S CONSTITUTION THIS SWEEP WAS JUDGED UNDER (S01): status, hash, and the three
        # thresholds it bound, each with the reason it is the value it is.
        "constitution": law,
        "n_trials": n_trials,
        "trial_count_basis": _trial_basis,
        "trial_census": _census,
        # WHAT THE DEFLATED-SHARPE GATE ACTUALLY APPLIED: the fixed per-cell bar. `n_trials` and
        # `trial_count_basis` above are the campaign count, REPORTED; neither enters a verdict.
        "dsr_bar": {"fixed_trials": dsr_hurdle_inputs(2)[0], "null_variance": "1/(T-1)",
                    "basis": _DSR_BASIS},
        # THE LIFETIME COUNT, A REPORT ONLY (V21). It never enters a verdict: the hurdle is the
        # fixed per-cell bar above. A missing ledger leaves this UNMEASURED and fails nothing.
        "trial_ledger": _safe(lambda: lifetime_trial_report(c.get("family") for c in cells),
                              "trial_ledger"),
        # N_EFFECTIVE BESIDE THE SEALED CHARGE (LAWS 5k; libs/research/trial_ledger.py): this
        # sweep's cells priced by their descriptors and parameters, so clones of one family
        # collapse and distinct mechanisms count in full. Reported so the reader can see what
        # the charge would be if it followed the family; it never sets the bar.
        "effective_trials": _eff_result(_eff_thread, _eff_box),
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
        "terminal_defects_judged": _terminal_defects,
        "verdicts": verdicts,
        "swept_at": datetime.now(UTC).isoformat(),
    }


#: Set ONLY by `--only`. None means the ordinary whole-docket run, byte-for-byte as before --
#: every branch below is guarded on this being non-None, so the certifying path is untouched.
_REPRO: dict[str, object] | None = None


def _repro_active() -> bool:
    return _REPRO is not None


def iter_json_array(path: Path, chunk_chars: int = 1 << 20):
    """Yield a top-level JSON array without materialising its million-row docket.

    `external_survivors.json` exceeded 1.5m rows on the live desk. `json.loads(read_text())`
    held the source text, the whole decoded list and two filtered copies at once, then died with
    MemoryError before gate one. This incremental decoder preserves every row and the exact
    ordering; callers make two bounded passes when they need a census before filtering.
    """
    decoder = json.JSONDecoder()
    with Path(path).open("r", encoding="utf-8") as handle:
        buf = ""
        pos = 0
        eof = False

        def refill() -> bool:
            nonlocal buf, pos, eof
            if pos:
                buf = buf[pos:]
                pos = 0
            more = handle.read(chunk_chars)
            if not more:
                eof = True
                return False
            buf += more
            return True

        refill()
        while True:
            while pos < len(buf) and buf[pos].isspace():
                pos += 1
            if pos < len(buf):
                break
            if not refill():
                raise ValueError(f"{path} is empty; expected a JSON array")
        if buf[pos] != "[":
            raise ValueError(f"{path} is not a top-level JSON array")
        pos += 1
        while True:
            while True:
                while pos < len(buf) and (buf[pos].isspace() or buf[pos] == ","):
                    pos += 1
                if pos < len(buf) or eof:
                    break
                refill()
            if pos < len(buf) and buf[pos] == "]":
                return
            if eof and pos >= len(buf):
                raise ValueError(f"{path} ended before the JSON array closed")
            try:
                value, end = decoder.raw_decode(buf, pos)
            except json.JSONDecodeError:
                if eof:
                    raise
                refill()
                continue
            pos = end
            yield value


def judge_refusal(verb: str, target: Path | str) -> str | None:
    """THE JUDGE'S RUNTIME FIREWALL (Tier S layer 12, `libs/tiers/firewall.judge_refusal`): None
    when this gauntlet may `verb` `target`, else why it refuses. The judge reads the compiled
    docket and the bars, never a raw hypothesis or a sealed lockbox store. FAIL CLOSED: a
    firewall that cannot be imported or cannot run is a refusal, never a pass."""
    try:
        from libs.tiers.firewall import judge_refusal as _judge_refusal
    except Exception as exc:
        return f"FIREWALL_UNAVAILABLE: {type(exc).__name__}: {exc}"
    try:
        rel = Path(target).resolve().relative_to(BASE).as_posix()
    except (ValueError, OSError):
        rel = str(target)
    return _judge_refusal(verb, rel)


def _docket_key(h: dict[str, Any]) -> tuple[str, Any, Any, dict[str, Any]] | None:
    """One docket row's (cell key, sym, family, params), or None when it names no symbol or
    family -- `main`'s grouping body, verbatim, raising whatever it raised."""
    sym = h.get("symbol")
    fam = h.get("family")
    params = dict(h.get("params") or {})
    if not sym or not fam:
        return None
    row_tf = str(h.get("timeframe") or "").upper()
    if row_tf and row_tf != "H1" and "timeframe" not in params:
        params["timeframe"] = row_tf
    key = f"{sym}.{fam}.{json.dumps(params, sort_keys=True)}"
    return key, sym, fam, params


def _docket_spec(h: dict[str, Any], sym: Any, fam: Any, params: dict[str, Any]) -> dict[str, Any]:
    """The spec `main` records for a key's FIRST row (built only then, as before)."""
    return {
        "sym": sym,
        "family": fam,
        "params": params,
        "timeframe": timeframe_of(params, str(fam)),
        "mechanism_status": h.get("mechanism_status"),
        "mechanism_note": h.get("mechanism_note"),
        # Tier S pre-judge screen (libs/tiers/prejudge_screen.py): a cell a Red Queen
        # defender rule or a ratified invented test flagged is judged after the clean
        # cells of its bucket. Order only: nothing is dropped.
        "prejudge_flagged": bool(((h.get("prejudge") or {}).get("flags"))),
        # The last day the LLM lab's style screen read (`lab_style`), refused below when
        # the cell's lockbox cut is not after it. Absent on every other row.
        **({"screen_read_until": str(h["screen_read_until"])}
           if h.get("screen_read_until") else {}),
    }


def _docket_fold(cells: dict[str, dict[str, Any]], key: str, h: dict[str, Any],
                 kc: tuple[Any, ...], first: dict[str, Any] | None = None
                 ) -> dict[str, Any] | None:
    """`main`'s grouping body for one row already keyed, verbatim, on one grouping. `first` is
    a spec this same row already built for the other grouping (copied, never shared: each
    grouping folds its own rows' provenance). Returns the spec it built for a new key."""
    built = None
    if key in cells and h.get("screen_read_until"):
        # The LATEST day any proposer's screen read is the one the cut must clear.
        _was = str(cells[key].get("screen_read_until") or "")
        cells[key]["screen_read_until"] = max(_was, str(h["screen_read_until"]))
    if key in cells:
        merge_llm_provenance(cells[key], h)
    if key not in cells:
        built = _docket_spec(h, *kc[1:]) if first is None else dict(first)
        cells[key] = dict(built) if first is None else built
        # LLM provenance (`lookahead_guard`, `producer`, `source`) rides from the row onto
        # the docket spec, or the look-ahead guard below never sees it and fails OPEN
        # (audit HOLD on e7547165).
        merge_llm_provenance(cells[key], h)
    return built


def main():
    # THE FIREWALL BEFORE THE FIRST READ: every input the sweep judges from and the authority
    # file it writes. A refusal halts the sweep with the certificates untouched -- the gate
    # refuses, it never passes on an input it was not allowed to see.
    surv_file = HYP / "external_survivors.json"
    for _verb, _target in (("read", UNI / "universe.json"), ("read", surv_file),
                           ("write", REPORTS / "UNIVERSAL_SURVIVORS.json"),
                           ("write", REPORTS / "universal_gates_external.json")):
        _refused = judge_refusal(_verb, _target)
        if _refused:
            print(f"HALT: the judge's firewall refused to {_verb} {_target}: {_refused}. "
                  f"No sweep, no certificate written.")
            return
    meta = json.loads((UNI / "universe.json").read_text("utf-8"))

    # Load external backtest survivors
    if not surv_file.exists():
        print("No external survivors found")
        return
    total = stamped_n = unstamped_n = 0
    unstamped_sample: list[str] = []
    # ONE PASS OVER THE DOCKET, NOT TWO (2026-10-14). The census below decides `stamped_only`,
    # which the grouping pass used to need first, so the docket (1.5m+ rows) was decoded twice
    # a sweep. Both groupings are now built in the one pass -- every row, and stamped rows only --
    # each in first-seen order, and the census picks one: exactly the dict the second pass built.
    # A row that would have raised in the second pass raises at the same point of the sweep.
    _cells_all: dict[str, dict[str, Any]] = {}
    _cells_stamped: dict[str, dict[str, Any]] = {}
    _raise_all: list[BaseException] = []
    _raise_stamped: list[BaseException] = []
    _plan_progress("docket", force=True, rows=0)
    for h in iter_json_array(surv_file):
        total += 1
        _plan_progress("docket", rows=total, cells=len(_cells_all))
        _st = False
        if isinstance(h, dict) and is_stamped(h):
            stamped_n += 1
            _st = True
        elif isinstance(h, dict):
            unstamped_n += 1
            if len(unstamped_sample) < 5:
                unstamped_sample.append(str(h.get("family") or h.get("title"))[:40])
        if not isinstance(h, dict) or (_raise_all and (_raise_stamped or not _st)):
            continue
        _need_all = not _raise_all
        _need_st = _st and not _raise_stamped
        try:
            _kc = _docket_key(h)
        except Exception as _exc:
            if _need_all:
                _raise_all.append(_exc)
            if _need_st:
                _raise_stamped.append(_exc)
            continue
        if _kc is None:
            continue
        _built = None
        if _need_all:
            try:
                _built = _docket_fold(_cells_all, _kc[0], h, _kc)
            except Exception as _exc:
                _raise_all.append(_exc)
        if _need_st:
            try:
                _docket_fold(_cells_stamped, _kc[0], h, _kc, _built)
            except Exception as _exc:
                _raise_stamped.append(_exc)
    print(f"Loaded {total} external survivors by streaming census")
    _ack_docket(surv_file)
    # EMPTY INPUT IS A HALT, NOT A SWEEP (2026-08-26, measured). The hourly merge briefly wrote
    # a 0-row input; this gauntlet then ran "normally" on nothing and rewrote the AUTHORITY file
    # to n=0 -- wiping 21 certificates with exit code 0. Zero candidates means there is nothing
    # to judge, and a judge with an empty docket must not touch the records of past verdicts.
    if not total:
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
    stamped_only = bool(unstamped_n and stamped_n)
    if stamped_only:
        print(f"REFUSED {unstamped_n} unstamped candidate(s) of {total}: no "
              f"available_time / ingested_time / source_version / payload_hash. Re-donate "
              f"through proposer_common.donate. First: "
              f"{unstamped_sample}")
    elif unstamped_n:
        print(f"PIT GAP: all {unstamped_n} candidates are unstamped, so the refusal is "
              f"DEFERRED this pass -- judging them rather than halting certification. The "
              f"exclusion switches on with the first stamped donation and only tightens after.")

    # Group by unique (sym, CHART, family, params) combos. A proposer that carries the chart on
    # the ROW rather than in params (the orthogonal sweep writes both) must not have it dropped
    # here: two rows differing only by chart are two cells, and folding them would hand one
    # verdict to both.
    _raised = _raise_stamped if stamped_only else _raise_all
    if _raised:
        raise _raised[0]
    cells = _cells_stamped if stamped_only else _cells_all
    del _cells_all, _cells_stamped

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

    # THE PLAN, RESUMED OR MADE (2026-10-20, IDEA_QUEUE 159). The 10-20 sweep spent 9,729 s
    # planning before its first shard ran; a sweep killed after that re-planned from nothing. A
    # sharded sweep now persists the plan it made (`_persist_plan`) and a restart RESUMES it
    # when the code, the law and the universe are unchanged -- re-planning only the docket cells
    # whose spec changed (`_replan_changed`) -- instead of re-planning the whole docket.
    _sweep = _resume_plan(cells, meta, surv_file)
    if _sweep is None:
        _t_plan = time.time()
        _sweep = _plan_phase(cells, meta)
        _persist_plan(_sweep, surv_file, plan_s=time.time() - _t_plan)
    return _judge_phase(_sweep)


def _plan_phase(cells: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    """THE PLAN, MOVED VERBATIM OUT OF `main` (2026-10-20): gate 0, the build preflight, the
    order, novelty, the yield allocation and the pre-warm pool. Returns every name the judging
    half reads, so `_judge_phase` runs on a made plan and on a resumed one alike."""
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

    # These descriptions cannot execute as claimed. Conserve every refusal, but discover it
    # before novelty, allocation and parallel pre-warm so scarce build/gate compute is reserved
    # for cells that can actually reach the ten gates.
    _modifier_ready, _modifier_blocked = _preflight_split(eligible_specs)
    eligible_specs = _modifier_ready
    if _modifier_blocked:
        print(f"Build preflight: {len(_modifier_blocked)} incomplete input/variant(s) conserved "
              f"without spending build/gate compute; {len(eligible_specs)} executable cell(s) "
              "remain")

    # Build cell objects -- CACHE FIRST. A cell whose (identity, params, last complete data-day)
    # was already computed loads its 1x and 3x daily series and skips signal generation AND both
    # backtests entirely; only genuinely new candidates, or a new trading day, pay for compute.
    # This is what makes an hourly sweep of a 3,000+ docket take minutes instead of the hour.
    cell_objs: list[dict[str, Any]] = []
    cache_hits = 0
    built_fresh = 0
    deferred: list[dict] = []
    _mem_deferred = 0
    blocked_build: list[dict] = list(_modifier_blocked)
    _build_t0 = time.time()
    _LAST_DAY.clear()       # one sweep's data-days, never a previous sweep's
    # Yesterday's keys die with yesterday's data-day; prune so the cache never grows unbounded.
    # ONE DIRECTORY READ, NOT ONE STAT PER FILE (2026-10-20): `os.scandir` hands back each entry's
    # mtime from the listing itself on Windows, where `Path.stat` opened every one of the cache's
    # files again. Same names (`fnmatch` normalises case exactly as the glob did), same age rule,
    # same stop on the first OSError -- and the plan now says how long it took.
    _pr_t0, _pr_seen, _pr_gone = time.time(), 0, 0
    try:
        import fnmatch as _fn
        import time as _t
        with os.scandir(CACHE_DIR) as _it:
            for _e in _it:
                if not _fn.fnmatch(_e.name, "*.npz"):
                    continue
                _pr_seen += 1
                _plan_progress("cache_prune", scanned=_pr_seen, removed=_pr_gone)
                if _t.time() - _e.stat().st_mtime > 3 * 86400:
                    Path(_e.path).unlink(missing_ok=True)
                    _pr_gone += 1
    except OSError:
        pass
    print(f"CACHE PRUNE: {_pr_seen} cached cell(s) scanned, {_pr_gone} older than 3 days removed "
          f"in {time.time() - _pr_t0:.0f}s", flush=True)
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
    _seen = _seen_cells()

    _unjudged = _stamped_but_unjudged()

    def _is_new(sp: dict) -> int:
        """0 for a cell this desk has never JUDGED, 1 otherwise. Cheap: no frame is loaded.

        A SEEN-STAMP IS NOT A VERDICT, AND CONFLATING THEM STARVED 1,544 CELLS FOREVER.
        Measured 2026-09-15: every `cross_asset_residual`, `relative_value`, `correlation_regime`
        and `pca_residual` row in the gates report carries `stages: {}`, `days: 0`,
        `passed: null` and `downstream_status: NOT_RUN_BUILD_BUDGET_DEFERRED` -- the sweep's
        build budget was exhausted before the cell was computed. 1,544 of 1,598.

        That is a SELF-SUSTAINING trap, and it is GAP #27's residue. Until 4a3b7bb05460 the sweep
        wrote the seen-stamp BEFORE the verdict was durable, so a cell the budget never reached
        still got stamped. The stamp makes `_is_new` return 1, which sorts the cell behind every
        genuinely-new one, which guarantees the budget never reaches it, which leaves it
        unjudged -- forever, with the report calling it "work not yet done". Fixing the write
        ORDER stops new instances; it cannot free the ones already stamped.

        So newness is now measured against the VERDICT LEDGER as well as the stamp: a cell whose
        recorded verdict has no stages is treated as never judged, because it was never judged.
        This is the same distinction the desk draws everywhere else tonight -- a status asserted
        where it could be read.
        """
        try:
            cid = cell_id({"sym": sp.get("sym"), "family": sp.get("family"),
                           "params": sp.get("params") or {}})
        except Exception:
            return 0
        if cid not in _seen:
            return 0
        return 0 if cid in _unjudged else 1
    # CHART GROUPS STAY CONTIGUOUS INSIDE SYMBOL GROUPS, for the same reason symbol groups stay
    # contiguous at all: the frame cache is what makes the build cheap, and one symbol's M5 and
    # H1 frames are two different entries in it.
    # BANNED FAMILIES ARE SET ASIDE BEFORE ANYTHING IS ORDERED (2026-09-16): the hour they would
    # have taken goes to every other mechanism, which is the principal's order verbatim.
    try:
        from research.family_policy import ban_reason, family_banned
        _set_aside = [sp for sp in eligible_specs if family_banned(sp.get("family"))]
        if _set_aside:
            eligible_specs = [sp for sp in eligible_specs if not family_banned(sp.get("family"))]
            _fams = sorted({str(sp.get("family") or "") for sp in _set_aside})
            print(f"  banned families: {len(_set_aside)} cell(s) set aside "
                  f"({'; '.join(ban_reason(f) for f in _fams)})")
    except Exception as _exc:
        print(f"  banned families: policy unreadable ({type(_exc).__name__}); nothing set aside")
    # BREADTH FIRST AMONG THE NEVER-JUDGED (2026-09-16, principal: "all sessions, all charts,
    # not tons of H1 Asia"). Never-judged cells are ordered by how many cells of the same
    # (chart, session) bucket the desk has already judged, fewest first, so the least-covered
    # chart x session is reached before the hundredth H1 Asia cell. Symbol rotation still
    # orders cells inside a bucket, so the frame cache keeps a symbol's cells adjacent there.
    def _bucket(sp: dict) -> tuple[str, str]:
        _p = sp.get("params") or {}
        return (timeframe_of(_p, str(sp.get("family") or "")),
                str(_p.get("session") or _p.get("selector") or sp.get("selector") or "all").lower())

    _judged_in_bucket: dict[tuple[str, str], int] = {}
    for _sp in eligible_specs:
        if _is_new(_sp) == 1:
            _judged_in_bucket[_bucket(_sp)] = _judged_in_bucket.get(_bucket(_sp), 0) + 1

    # INTRADAY BEFORE H1 AND D1 (principal 2026-09-16: "more priority to intraday than h1s").
    def _tf_rank(sp: dict) -> int:
        _tf = timeframe_of(sp.get("params"), str(sp.get("family") or ""))
        return 0 if _tf in ("M1", "M5", "M15", "M30") else (1 if _tf == "H4" else 2)

    # THE CEO DOCKET IS AUTHORITATIVE OVER THE ORDER (closed-loop
    # `research.frontier_scheduler_authoritative`, 2026-09-16). Its proposals name families;
    # never-judged cells of a proposed family are reached before the rest of their chart rank,
    # and how many were served is written for `frontier_ceo` to read back -- the claim is
    # measured on the next run's order, never asserted by the proposer.
    _ceo_fams: set[str] = set()
    try:
        _ceo = json.loads((BASE / "desks" / "mt5" / "reports" / "CEO_DOCKET.json").read_text("utf-8"))
        for _p in (_ceo.get("proposals") or []):
            _f = str((_p.get("family") if isinstance(_p, dict) else _p) or "").strip()
            if _f:
                _ceo_fams.add(_f)
    except Exception:
        _ceo_fams = set()

    def _ceo_rank(sp: dict) -> int:
        return 0 if str(sp.get("family") or "") in _ceo_fams else 1

    eligible_specs = sorted(
        eligible_specs,
        key=lambda sp: (_is_new(sp),
                        _tf_rank(sp),
                        _ceo_rank(sp),
                        bool(sp.get("prejudge_flagged")),
                        _judged_in_bucket.get(_bucket(sp), 0),
                        _cursor.get(str(sp.get("sym") or ""), ""),
                        str(sp.get("sym") or ""),
                        timeframe_of(sp.get("params"), str(sp.get("family") or "")),
                        str(sp.get("family") or "")))
    try:
        _served = sum(1 for sp in eligible_specs if _is_new(sp) == 0 and _ceo_rank(sp) == 0)
        _order_doc = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                      "ceo_families": sorted(_ceo_fams), "ceo_cells_first": _served,
                      "never_judged": sum(1 for sp in eligible_specs if _is_new(sp) == 0),
                      "buckets_judged": {f"{k[0]}/{k[1]}": v for k, v in _judged_in_bucket.items()},
                      "order": "never-judged, intraday first, CEO-proposed families first, "
                               "least-covered chart x session bucket first, symbol rotation"}
        (BASE / "desks" / "mt5" / "reports" / "GAUNTLET_ORDER.json").write_text(
            json.dumps(_order_doc, indent=1), encoding="utf-8")
    except Exception as _exc:
        print(f"  gauntlet order record unwritten ({type(_exc).__name__}: {_exc})")
    if _judged_in_bucket:
        _cov = sorted(_judged_in_bucket.items(), key=lambda kv: kv[1])
        print(f"  breadth: {len(_judged_in_bucket)} chart x session bucket(s) judged so far; "
              f"least covered {_cov[0][0]} ({_cov[0][1]}), most {_cov[-1][0]} ({_cov[-1][1]})")
    # RE-MINT FIRST (v4 remint patch; see PRIORITY_REMINT). Ahead of the never-judged tier: while
    # the attestation in force has no certificate store, no clock enrols and nothing promotes.
    _remint_ids, _remint_stale = remint_cells()

    def _remint_is(sp: dict) -> bool:
        if not _remint_ids:
            return False
        try:
            return cell_id({"sym": sp.get("sym"), "family": sp.get("family"),
                            "params": sp.get("params") or {}}) in _remint_ids
        except Exception:
            return False
    eligible_specs = remint_front(eligible_specs, _remint_is)
    if _remint_ids:
        print(f"  re-mint: {sum(1 for sp in eligible_specs if _remint_is(sp))} of "
              f"{len(_remint_ids)} certificate cell(s) under re-judgement first "
              f"(priority_remint.json + the canon's pending_rejudge)")
    # ALLOCATE THE HOUR BY MEASURED YIELD, AFTER the never-judged cells are already at the front.
    # Order decides what gets reached; the quota decides how much of each family the hour spends
    # itself on. Applied here rather than before the sort so a never-judged cell keeps its
    # priority -- judging a cell for the first time is still the only thing a sweep does that can
    # change what the desk knows, whatever family it belongs to.
    # NOVELTY BEFORE TESTING (AlphaAgent anti-homogeneity, principal 2026-09-16). The cells
    # about to be judged are screened against the desk's library by `research/novelty_gate`:
    # a cell that is a twin of an existing member on every MEASURABLE economic dimension is
    # set aside with the twin named, and never spends a trial of the family-wise error budget.
    # Novelty in at least one measured dimension admits; an unmeasurable dimension never
    # convicts. The screen is bounded so it costs seconds, not the sweep.
    try:
        _rp = str(BASE / "desks" / "mt5" / "research")
        if _rp not in sys.path:
            sys.path.insert(0, _rp)
        import novelty_gate as _ng
        _head_n = int(os.environ.get("GAUNTLET_NOVELTY_SCREEN", "1500"))
        _head = eligible_specs[:_head_n]
        _cands = [{"symbol": sp.get("sym"), "family": sp.get("family"),
                   "params": sp.get("params") or {},
                   "timeframe": timeframe_of(sp.get("params"), str(sp.get("family") or "")),
                   "session": (sp.get("params") or {}).get("session")} for sp in _head]
        _verd = _ng.screen(_cands)
        _drop = {i for i, v in enumerate(_verd) if getattr(v, "verdict", "") == "REDUNDANT"
                 and not _remint_is(_head[i])}
        _aside = [{"sym": _head[i].get("sym"), "family": _head[i].get("family"),
                   "twin": getattr(_verd[i], "twin", None),
                   "why": str(getattr(_verd[i], "why", ""))[:160]} for i in sorted(_drop)]
        if _drop:
            eligible_specs = [sp for i, sp in enumerate(eligible_specs) if i not in _drop]
        (BASE / "desks" / "mt5" / "reports" / "NOVELTY_SET_ASIDE.json").write_text(json.dumps(
            {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "screened": len(_head),
             "set_aside": len(_drop), "rows": _aside[:300],
             "rule": "REDUNDANT on every measurable economic dimension, twin named"}, indent=1),
            encoding="utf-8")
        print(f"  novelty: {len(_drop)} of {len(_head)} screened cell(s) set aside as REDUNDANT "
              f"(twins named) -> NOVELTY_SET_ASIDE.json")
    except Exception as _exc:
        print(f"  novelty screen unavailable ({type(_exc).__name__}: {_exc}); nothing set aside")
    _before = len(eligible_specs)
    _remint_front = [sp for sp in eligible_specs if _remint_is(sp)]
    eligible_specs, _alloc = allocate_by_yield(eligible_specs)
    if _remint_front:
        eligible_specs = _remint_front + [sp for sp in eligible_specs if not _remint_is(sp)]
    _n_new = sum(1 for sp in eligible_specs if _is_new(sp) == 0)
    print(f"  docket order: {_n_new} never-judged cell(s) first, then "
          f"{len(eligible_specs) - _n_new} in symbol-rotation order")
    if _alloc:
        print(f"  yield allocation: {len(eligible_specs)} of {_before} cell(s) this sweep "
              f"(strength {YIELD_ALLOCATION_STRENGTH:.2f}, floor {YIELD_MIN_SHARE:.0%})")
        for _f, _r in sorted(_alloc.items(), key=lambda kv: -kv[1]["yield_per_1k_ruled"])[:8]:
            print(f"    {_f:26} {_r['built_this_sweep']:6}/{_r['docket']:<6} "
                  f"yield/1k {_r['yield_per_1k_ruled']:8.2f}  share {_r['share_of_budget']:.3f}")
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
        # THE POOL'S BUILDS COUNT AS BUILDS. Without this the cursor never advances and the
        # docket never rotates -- see `_prewarm_cache.summary["built_symbols"]`.
        _built_syms |= set(_prewarm.get("built_symbols") or ())
        # THE POOL'S DATA-DAYS SEED THIS PROCESS AND THE SHARDS' (`_run_shards`): a cell is looked
        # up under the day the pool keyed it to. Popped: it is a working map, not a report field.
        _LAST_DAY.update(_prewarm.pop("last_days", None) or {})
        eligible_specs = _apply_prewarm_failures(eligible_specs,
                                                 _prewarm.pop("failed_cells", None) or {},
                                                 blocked_build)
    return {"cells": cells, "meta": meta, "n_cells": len(cells),
            "eligible_specs": eligible_specs, "prior_rejections": prior_rejections,
            "blocked_build": blocked_build, "cell_objs": cell_objs, "deferred": deferred,
            "cache_hits": cache_hits, "built_fresh": built_fresh, "_mem_deferred": _mem_deferred,
            "_build_t0": _build_t0, "_built_syms": _built_syms, "_cursor": _cursor,
            "_seen": _seen, "_prewarm": _prewarm, "_remint_stale": _remint_stale}


def _judge_phase(st: dict[str, Any]) -> None:
    """THE JUDGING HALF OF `main`, MOVED VERBATIM: build (or shards), the ten gates, every
    record and every authority file -- on the plan `_plan_phase` made or `_resume_plan` kept."""
    cells, meta, _n_cells = st["cells"], st["meta"], int(st["n_cells"])
    eligible_specs, prior_rejections = st["eligible_specs"], st["prior_rejections"]
    blocked_build, cell_objs, deferred = st["blocked_build"], st["cell_objs"], st["deferred"]
    cache_hits, built_fresh, _mem_deferred = (st["cache_hits"], st["built_fresh"],
                                              st["_mem_deferred"])
    _build_t0, _built_syms, _cursor = st["_build_t0"], st["_built_syms"], st["_cursor"]
    _seen, _prewarm, _remint_stale = st["_seen"], st["_prewarm"], st["_remint_stale"]
    # STAGE 0, REPORT-ONLY (V8). `stage0_prefilter` says why it cannot be more than that here:
    # a spec carries no return stream, and the cells that do (cached series) have already paid
    # their build. It judges every cached series on the loop's cached branch below, counts what
    # it WOULD have rejected, and removes nothing; the result's `pre_filter` block and the
    # append-only ledger carry the decisions. Fresh builds are counted as unjudged-before-build.
    _stage0 = stage0_new_summary()
    _stage0_verdicts: dict[str, dict] = {}
    _sharding = None
    if _SHARD is not None:
        # THE SHARDED SWEEP (`run_sharded`). The pool above has warmed the docket exactly as it
        # always does; the docket -- ordered, allocated, final -- is then written as ONE plan,
        # and N shards build their stable-hash share of it, the union's lockbox cut is taken
        # from every shard's dates, and the shards then rule their cells' cell-local gates on
        # the development window. This process verifies every planned cell came back from
        # exactly one shard and restores the plan's order. No shard computes a program-level
        # number: `run_gauntlet` below does, once, on the union.
        _sh = _run_shards(eligible_specs, meta, _build_t0,
                          pre_rows=[*prior_rejections,
                                    *(_blocked_verdict(s) for s in blocked_build)])
        cell_objs, deferred = _sh["cell_objs"], _sh["deferred"]
        blocked_build.extend(_sh["blocked"])
        cache_hits, built_fresh = _sh["cache_hits"], _sh["built_fresh"]
        _mem_deferred = _sh["mem_deferred"]
        _built_syms |= _sh["built_syms"]
        _sharding = _sh["report"]
        _stage0_fold(_stage0, _stage0_verdicts, _sh["stage0_parts"])
    else:
        _b = _build_specs(eligible_specs, meta, _build_t0, _stage0, _stage0_verdicts,
                          _built_syms, blocked_build)
        cell_objs, deferred = _b["cell_objs"], _b["deferred"]
        cache_hits, built_fresh, _mem_deferred = (_b["cache_hits"], _b["built_fresh"],
                                                  _b["mem_deferred"])
    if cache_hits:
        print(f"Cell cache: {cache_hits}/{len(eligible_specs)} loaded (same data-day), "
              f"{len(eligible_specs) - cache_hits} to compute")
    if deferred:
        # THE POOL'S BUILDS ARE FRESH CELLS TOO (2026-10-20). With the pre-warm on, the loop finds
        # the budget spent and `built_fresh` is 0 by construction; sweep 23324 printed "after 0
        # fresh cell(s) in 14782s" while the pool had warmed 11,394. The seconds are the time
        # since the budget clock started, which includes the shard dispatch, not the build alone.
        _warmed = int((_prewarm or {}).get("warmed") or 0)
        print(f"BUILD BUDGET reached after {built_fresh} fresh cell(s) built in the loop and "
              f"{_warmed} warmed by the pre-warm pool, {time.time() - _build_t0:.0f}s after "
              f"the build clock started (budget {FRESH_BUILD_BUDGET_SEC:.0f}s): "
              f"{len(deferred)} cell(s) DEFERRED to the next "
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
    result["n_cells_discovered"] = _n_cells
    if st.get("plan_resume"):
        result["plan_resume"] = st["plan_resume"]
    result["n_cells_advanced_beyond_economic_prior"] = len(cell_objs)
    result["n_cells_rejected_at_economic_prior"] = len(prior_rejections)
    # DEFERRED CELLS ARE IN THE RECORD, NOT MISSING FROM IT. A cell the build budget did not
    # reach is UNMEASURED -- not a pass, not a fail, and emphatically not absent. Leaving it out
    # would make the report describe a smaller docket than the desk actually holds, which is the
    # silent-shrinkage failure this desk has been burned by before. It carries its own reason so
    # nobody has to guess why a cell has no verdict (L1.28a).
    deferred_verdicts = [_deferred_verdict(s) for s in deferred]
    blocked_verdicts = [_blocked_verdict(s) for s in blocked_build]
    # The rows the ten gates never reached are stamped too: gate 0 by its gate, the rest NOT_RUN.
    stamp_terminal([*prior_rejections, *deferred_verdicts, *blocked_verdicts])
    result["n_cells_deferred_build_budget"] = len(deferred)
    # WHICH budget deferred them, because "deferred" with no reason is how a cap becomes
    # invisible and a docket quietly stops converging.
    result["n_cells_deferred_memory_budget"] = _mem_deferred
    result["memory_budget_mb"] = MEMORY_BUDGET_MB
    # WHAT THE POOL DID, in the report beside the budgets that bounded it -- so "42 judged" can
    # be read against "N workers warmed M cells" rather than guessed at from wall time.
    result["workers"] = WORKERS
    result["prewarm"] = _prewarm
    if _sharding is not None:
        result["sharding"] = _sharding
    result["peak_rss_mb"] = round(_rss_mb(), 1)
    _save_build_cursor(_cursor, _built_syms)
    # A CELL COUNTS AS SEEN ONLY WHEN IT WAS JUDGED, never when it was deferred or blocked.
    # `deferred_verdicts` and `blocked_verdicts` carry `passed: None` and a reason precisely
    # because they are work not yet done; stamping those would drop them out of the new-first
    # queue without anyone having looked at them, which is the exact shape of a cell that
    # silently stops being tested.
    # THE VERDICT IS MADE DURABLE BEFORE THE CELL IS CALLED JUDGED, and the order used to be the
    # other way round. `_save_seen_cells` stamped here while `_append_gate_ledger` ran 33 lines
    # later inside a `_safe(...)`, so a sweep that died, was killed by the memory guard, or simply
    # raised between the two left cells marked JUDGED with no verdict anywhere -- which is exactly
    # what the conservation ledger calls LOST.
    #
    # MEASURED 2026-09-14: 10 lost cells, every one `discovered`, and all ten carrying the SAME
    # seen-stamp `2026-09-12T03:19:08+00:00`. One interrupted sweep, one instant, ten cells that
    # can never be re-judged (they are no longer new) and can never be accounted for (they hold no
    # verdict). `lost` is the desk's only alarm for a dropped record, and this ordering was
    # manufacturing the very thing it watches for.
    #
    # Stamping AFTER means the worst case is a cell judged twice, which costs one rotation slot.
    # Stamping BEFORE meant the worst case was a cell lost forever. Those are not symmetric.
    # EVERY VERDICT IS STAMPED AND REACHES THE GRAPH, BEFORE IT IS MADE DURABLE (2026-09-30).
    # `record_verdicts` had no production caller, so the hypothesis graph's last fate was a
    # hand-run backfill on 2026-09-03 and 0 of 108,189 rows named a pre-registration card.
    # Each verdict -- gate-0 rejects, the ten-gate verdicts, and the deferred / blocked rows
    # (stamped, never given a fate) -- is stamped PREREGISTERED with the card that fixed its
    # exact spec before the cell was first judged, or `prereg_hash: null` + POST_HOC. The
    # stamps land on the SAME dicts the report and the gate ledger are written from. Inside
    # `_safe` ENTIRELY, naming included: bookkeeping may cost its own record, never the sweep.
    _prereg_result = _safe(lambda: record_gauntlet_verdicts(
        [*prior_rejections, *deferred_verdicts, *blocked_verdicts,
         *(result.get("verdicts") or [])],
        {cell_id(s): s for s in [*cells.values(), *cell_objs] if isinstance(s, dict)},
        first_judged=_seen),
        "prereg_graph")
    result["preregistration"] = _prereg_result
    _gate_ledger_result = _safe(lambda: _append_gate_ledger(result.get("verdicts") or [],
                                                            cell_objs),
                                "gate_ledger")
    _save_seen_cells(_seen, {str(v.get("cell") or "")
                             for v in (result.get("verdicts") or [])
                             if isinstance(v, dict) and v.get("passed") is not None})
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
    # THE GATE LEDGER (2026-09-12). Reproduction writes its own file and touches no shared
    # record, exactly as the report and the cursors already do.
    if not _repro_active():
        # THE FUNNEL'S OWN ANSWER, on the report rather than only in the ledger: where cells
        # died, and how many died at ONE gate only -- which is the population the forward cure
        # was written for and which nothing could count before today.
        import collections as _c
        _v = result.get("verdicts") or []
        result["terminal_gates"] = dict(_c.Counter(
            str(v.get("terminal_gate")) for v in _v if isinstance(v, dict)).most_common())
        # THE SAME FUNNEL, NAMED: by kind and by the gate that stopped each row. A DEFECT is a
        # row no rule could name; it is counted and sampled here and printed, never silent.
        result["terminal_kinds"] = dict(_c.Counter(
            str(v.get("terminal_kind")) for v in _v if isinstance(v, dict)).most_common())
        result["terminal_gate_ids"] = dict(_c.Counter(
            str(v.get("terminal_gate_id")) for v in _v
            if isinstance(v, dict) and v.get("terminal_kind") != "PASSED").most_common())
        _defect_cells = [str(v.get("cell") or "") for v in _v if isinstance(v, dict)
                         and v.get("terminal_kind") not in TERMINAL_KINDS[:4]]
        result["terminal_defects"] = {"n": len(_defect_cells), "sample": _defect_cells[:20]}
        if _defect_cells:
            print(f"TERMINAL GATE DEFECT: {len(_defect_cells)} verdict row(s) name no gate that "
                  f"stopped them ({TERMINAL_DEFECT}); first: {_defect_cells[:5]}")
        result["n_curable_by_forward"] = sum(
            1 for v in _v if isinstance(v, dict) and v.get("curable_by_forward"))
        # Written above, BEFORE the seen-cells stamp -- see the note there. Reported here so the
        # artifact's shape is unchanged for every consumer.
        result["gate_ledger"] = _gate_ledger_result

    # Save. REPRODUCTION WRITES ITS OWN FILE AND NOTHING ELSE. This report is read by the
    # research-health fence and the funnel census; a one-cell re-run overwriting it would make the
    # whole docket look like it had shrunk to a single candidate.
    if not _repro_active():
        out = REPORTS / "universal_gates_external.json"
        out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        _write_report_digest(out, result)
        print(f"\nSaved to {out}")
        # THE SHARDS' EARLY COPY, CHECKED AGAINST THE RECORD JUST WRITTEN (never the reverse).
        if _sharding is not None:
            _sharding_pub = _safe(lambda: _seal_shard_publication(result["verdicts"]),
                                  "shard_publication")
            print(f"  shard publication: {_sharding_pub.get('final_rows_agree')} final row(s) "
                  f"agree, {_sharding_pub.get('final_rows_disagree')} disagree, "
                  f"{_sharding_pub.get('absent_from_merge')} absent")
            # THE VERDICTS ARE DURABLE: nothing is left to resume.
            _safe(_sweep_cleanup, "sweep_cleanup")

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
    _remint_fresh: set[str] = set()
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
        _remint_fresh.add(key)

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
        _remint_fresh.update(_scalp_rows)
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
    from gate_policy import is_exact_policy as _is_exact
    _remint = remint_partition(old_doc, survivors_all, result.get("verdicts") or [],
                               _remint_fresh, _remint_stale, _is_exact,
                               str(ATTESTATION.get("version") or ""),
                               datetime.now(UTC).isoformat())
    if _remint["record"].get("active"):
        _r = _remint["record"]
        print(f"  re-mint under {_r['to_version']}: {_r['stale_rows']} stale row(s) -> "
              f"{_r['rejudged_passed']} re-judged PASS, {_r['rejudged_failed_retired']} "
              f"re-judged FAIL (retired), {len(_r['superseded'])} superseded, "
              f"{_r['pending_rejudge']} pending (outside the survivor set)")
    if len(survivors_all) + _remint["accounted"] < n_before:
        print(f"REFUSING to write: merge would shrink {n_before} -> {len(survivors_all)}")
        return
    # NEVER WRITE EMPTY (2026-08-27): a zeroed input file sails through the shrink check as
    # 0 -> 0, and this run then re-publishes the wipe with its own signature -- observed on the
    # desk box, healed only because the moneypath fence restored canon between runs. An empty
    # survivors file is never a verdict; if nothing has ever certified there is nothing to write.
    if not survivors_all and not (_remint["accounted"] or _remint["pending"]):
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
    retired.update(_remint["retired"])
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
            # NO RESTORE UNDER A HEADER THE ROW WAS NEVER JUDGED UNDER (2026-10-20). A row retired
            # before the reserved lockbox carries gate 9 == gate 7 (no `cut`); restoring it into
            # the survivor set re-stamps it with ATTESTATION. It waits for a re-judge instead.
            if restore_would_restamp(row, ATTESTATION):
                back = dict(row)
                back.setdefault("pending_since", stamp)
                back["pending_reason"] = ("retirement reason no longer holds, but its gates "
                                          "predate the reserved lockbox: re-judge, never restore")
                _remint["pending"][key] = back
                del retired[key]
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
    elif "retired_certificates" in old_doc:
        # every retired row moved out (restored, or sent to pending_rejudge): the stale block
        # must not survive, or `lockbox_recert.locate` reads those keys as RETIRED
        doc["retired_certificates"] = {}
    doc.pop("pending_rejudge", None)
    if _remint["pending"]:
        doc["pending_rejudge"] = _remint["pending"]
    if _remint["record"].get("active"):
        doc["reattestation"] = _remint["record"]
        if _remint["accounted"]:
            doc["revocation"] = {"kind": "reattestation", "at": datetime.now(UTC).isoformat(),
                                 "left_survivor_set": _remint["accounted"],
                                 "why": "rows judged under another attestation are re-judged, "
                                        "never re-stamped"}
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
    _progress_watermark(_n_cells, len(claims))


def _preflight_split(specs: list[dict[str, Any]]
                     ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(ready, blocked): the build preflight, one rule for the plan and for a re-planned cell.

    These descriptions cannot execute as claimed; every refusal is conserved with its reason."""
    _modifier_blocked: list[dict] = []
    _modifier_ready: list[dict] = []
    _plan_progress("preflight", force=True, done=0, total=len(specs))
    for _i, _spec in enumerate(specs):
        _plan_progress("preflight", done=_i, total=len(specs), blocked=len(_modifier_blocked))
        _why = modifier_preflight(_spec)
        if _why:
            _modifier_blocked.append({**_spec,
                                      "downstream_status": ("NOT_RUN_BUILD_FAILED"
                                          if _why.startswith("BLOCKED_") else "NOT_RUN_MODIFIER"),
                                      "why": (f"NOT_RUN_BUILD_FAILED: {_why}"
                                          if _why.startswith("BLOCKED_")
                                          else f"NOT_RUN_MODIFIER: {_why}")})
        else:
            _modifier_ready.append(_spec)
    return _modifier_ready, _modifier_blocked


def _deferred_verdict(s: dict[str, Any]) -> dict[str, Any]:
    """The row of a cell the build budget did not reach: work not yet done, never a verdict."""
    return {
        "cell": cell_id({"sym": s["sym"], "family": s["family"], "params": s.get("params") or {}}),
        "sym": s["sym"], "family": s["family"], "days": 0, "passed": None,
        "stages": {},
        "downstream_status": "NOT_RUN_BUILD_BUDGET_DEFERRED",
        "why": ("the sweep's fresh-build budget was exhausted before this cell was computed. "
                "The per-cell cache is cumulative and content-addressed, so the next sweep "
                "resumes here rather than restarting; this is work not yet done, never a "
                "verdict."),
        **({"prewarm_status": s["prewarm_status"], "prewarm_why": s.get("prewarm_why")}
           if s.get("prewarm_status") else {}),
    }


def _blocked_verdict(s: dict[str, Any]) -> dict[str, Any]:
    """The row of a cell whose data or build blocked it before any gate ran."""
    return {
        "cell": cell_id({"sym": s["sym"], "family": s["family"],
                         "params": s.get("params") or {}}),
        "sym": s["sym"], "family": s["family"], "days": 0, "passed": None,
        "stages": {}, "downstream_status": s["downstream_status"], "why": s["why"],
    }


def _ack_docket(path) -> None:
    """LINEAGE IS ACKNOWLEDGED, NEVER INFERRED (LAWS 7): the judge names the docket it read, by
    the docket's own producer run id, so `merge_docket -> external_gauntlet` is an observed edge
    rather than two nearby timestamps."""
    try:
        import sys as _sys
        if str(BASE) not in _sys.path:
            _sys.path.insert(0, str(BASE))
        from libs.ops.control_plane.lease import ack_artifact
        ack_artifact("leg:external_gauntlet", path)
    except Exception as exc:
        print(f"docket acknowledgement not recorded: {type(exc).__name__}: {exc}")


def _progress_watermark(cells_judged: int, claims: int) -> None:
    """THE GAUNTLET'S PROGRESS WATERMARK (LAWS.md 7): the trial cursor, not the process.

    A judging process that is alive and whose trial id has not moved is STALLED, and it looked
    identical to a healthy one on every dashboard this desk had. The monotone counter is the
    number of cells this lane has ever judged; `libs/ops/control_plane/watermarks.py` keeps the
    high-water mark, so a restart that resets the count leaves a recorded regression rather than
    erasing the evidence.
    """
    try:
        import sys as _sys
        root = str(BASE)
        if root not in _sys.path:
            _sys.path.insert(0, root)
        from libs.ops.control_plane import watermarks as wm
        prev = wm.read("leg:external_gauntlet") or {}
        wm.progress("leg:external_gauntlet", "trial_id",
                    int(prev.get("value") or 0) + int(cells_judged), claims=claims)
    except Exception as exc:
        print(f"gauntlet watermark not recorded: {type(exc).__name__}: {exc}")


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
    # BOTH CERTIFIERS SHARE ONE HEAVY LANE.  The Windows scheduler can legitimately launch the
    # legacy qquant battery while this resumable judge is building a docket.  Before this lease,
    # each process was individually non-duplicated but the pair spawned independent worker pools;
    # the live task then failed with 0x800705AF (insufficient system resources).  A five-minute
    # trigger makes deferral cheap; overlapping two authorities is never useful.
    # Normal judging reads local parquets and frozen cost artifacts. It must not monopolize the
    # terminal and prevent those parquets from being refreshed. `_live_frame` takes the Fusion
    # lease narrowly when a missing-parquet fallback is genuinely required.
    with exclusive_job("certification_lane", need_mb=_need) as lane:
        if not lane:
            print("external_gauntlet: DEFERRED -- another canonical certifier owns the lane")
            return 0
        with exclusive_job(_job, need_mb=0) as acquired:
            if not acquired:
                return 0
            main()
            return 0


# ------------------------------------------------------------------------ the sharded sweep
#: THE SHARDED SWEEP (2026-09-30). One sweep held `certification_lane` and ruled the whole docket
#: in ONE process: the pre-warm pool parallelised the BUILD, and everything after it -- loading
#: every cached pair, both cost arms, CPCV, walk-forward, the swap price -- ran on one core of an
#: 18-core box. This splits that per-cell work across N processes and changes no verdict.
#:
#: THE STATISTICAL CONSTRAINT IS THE DESIGN, not a caveat on it:
#:   * the trial census is the UNSHARDED UNION -- one plan, one matrix, one census;
#:   * every planned cell is ruled by EXACTLY ONE shard (a stable sha256 of its cell id, mod N),
#:     and the merge refuses (`ShardMergeError`) unless each came back exactly once;
#:   * `deflated_sharpe` (n_trials, variance of Sharpes), `pbo` and `reality_check_spa`, and every
#:     program-level number, are computed ONCE, by `run_gauntlet` in the merging process, on the
#:     union matrix in the plan's own column order -- no shard is ever judged against a smaller
#:     family, because no shard judges anything that reads the family at all.
#: THE LOCKBOX CUT IS PROGRAM-LEVEL TOO (policy v3/v4). `gate_policy.lockbox_cut` is one calendar
#: key derived from the UNION of every cell's dates, and every cell-local gate reads only the
#: development window before it; the lockbox itself is judged at the union's DSR hurdle `sr0`.
#: So a shard runs in TWO PHASES: `build` (series for its cells, and their dates), then -- after
#: the merge has computed the one cut from the union of all shards' dates -- `rule` (the
#: cell-local gates on the carved series). The lockbox gate is computed in the merge, never in a
#: shard, and `run_gauntlet` re-derives the cut itself and recomputes any cell whose shard used a
#: different one.
#:
#: A cell passes only when its cell-local gates (computed in its shard) AND the union's
#: program-level gates pass, which is the unsharded rule verbatim: the verdict row is assembled by
#: the same code in the same stage order either way.
#:
#: THE POOL IS NOT SHARDED. `main` runs the pre-warm pool over the whole plan first, exactly as
#: the unsharded sweep does (same order, same deadline, same deferrals); the shards then split the
#: serial work that followed it: loading each cached pair, any fresh build the pool did not reach,
#: both cost arms and the cell-local gates.
#:
#: ONE PEN. Shards write the content-addressed series cache (atomic, as the pre-warm pool already
#: does) and their own intermediate file, nothing else. The plan, the merge and every write the
#: sweep makes -- seen cells, the gate ledger and index, the report, UNIVERSAL_SURVIVORS.json, the
#: power-cure list, the claims ledger, the build cursor -- happen once, in `main`, inside the
#: certification lane `run_sharded` holds for the whole sweep. A shard that dies, is killed or
#: writes a stale file fails the merge closed: nothing is published and the next trigger retries.
#:
#: Its presence is the feature flag an unsealed launcher tests for (`SHARD_PROTOCOL`). Version 2 is
#: the two-phase protocol (`dispatch(shard_dir, n, phase)`); a launcher must refuse any other.
SHARD_PROTOCOL = 2

#: Set ONLY by `run_sharded`. None means the ordinary sweep, byte-for-byte as before.
_SHARD: dict[str, object] | None = None

#: Where a sharded sweep keeps its plan and the shards' intermediate files. Under the cache
#: directory, so it is ignored by git and pruned with it; the merge clears stale shard files.
SHARD_DIR = CACHE_DIR / "shards"


class ShardMergeError(RuntimeError):
    """A shard's output is missing, stale, duplicated or inconsistent with the plan."""


def shard_of(spec: dict, n_shards: int) -> int:
    """The ONE shard that rules `spec`: sha256 of its cell id, mod N. Stable across processes,
    hosts and Python hash seeds, so every shard computes the same partition from the same plan."""
    try:
        name = cell_id({"sym": spec.get("sym"), "family": spec.get("family"),
                        "params": spec.get("params") or {}})
    except Exception:
        name = (f"{spec.get('sym')}.{spec.get('family')}."
                f"{json.dumps(spec.get('params') or {}, sort_keys=True, default=str)}")
    return int(hashlib.sha256(str(name).encode("utf-8")).hexdigest()[:16], 16) % int(n_shards)


def _pickle_atomic(path: Path, obj: object) -> None:
    """Write-then-rename, so a reader sees the previous file or the whole new one, never half."""
    import pickle
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    with open(tmp, "wb") as fh:
        pickle.dump(obj, fh, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)


def _unpickle(path: Path):
    # Our own files only: written by this module under SHARD_DIR, inside the lane's lifetime,
    # and bound to the plan by its token. Pickle, because the merge must receive the series and
    # the stage dicts EXACTLY -- a JSON round-trip would coerce types a verdict row carries.
    import pickle
    with open(path, "rb") as fh:
        return pickle.load(fh)  # noqa: S301


def shard_worker(shard_dir: Path | str, k: int, phase: str = "build") -> dict:
    """Phase `build` or `rule` of shard `k` of the plan in `shard_dir`; writes `shard_<k>.pkl`.

    No lock: the merging process holds the lane for the whole sweep. `build` needs only the
    plan; `rule` needs the union's lockbox cut, which the merge writes to `cut.pkl` in between.

    Runs the SAME code the unsharded sweep runs after its pre-warm pool, on its share of the plan
    and in the plan's order: `_build_specs` (one spec at a time, so the outcome of each is known),
    `_cell_series`, `_cell_series_x3` (phase `build`) and `_cell_local_stages` (phase `rule`). It
    computes NO program-level quantity and writes no shared record; the merging `main` does both.
    """
    shard_dir = Path(shard_dir)
    t0 = time.time()
    plan = _unpickle(shard_dir / "plan.pkl")
    if plan.get("protocol") != SHARD_PROTOCOL:
        raise ShardMergeError(f"plan protocol {plan.get('protocol')!r} != {SHARD_PROTOCOL}")
    n = int(plan["n"])
    k = int(k)
    if not 0 <= k < n:
        raise ValueError(f"shard {k} outside 0..{n - 1}")
    meta = plan["meta"]
    if phase == "rule":
        return _shard_rule(shard_dir, plan, k, meta, t0)
    if phase != "build":
        raise ValueError(f"unknown shard phase {phase!r}")
    build_t0 = float(plan["build_t0"])
    _LAST_DAY.clear()
    _LAST_DAY.update(plan.get("last_days") or {})
    mine = [(i, sp) for i, sp in enumerate(plan["specs"]) if shard_of(sp, n) == k]
    basis = _shard_basis(plan, mine)
    if plan.get("resume"):
        _resumed = _resume_shard_build(shard_dir, plan, k, mine, basis)
        if _resumed is not None:
            return _resumed
    # NO POOL HERE. The merging process ran the pre-warm pool over the WHOLE plan before any shard
    # started, in the plan's order and against the same deadline, exactly as the unsharded sweep
    # does -- so a shard finds the pool's cells cached and defers what the pool did not reach, for
    # the same reason and with the same status. Only the per-cell work after the pool is split.
    built_syms: set[str] = set()
    acc: dict = {"cell_objs": [], "deferred": [], "cache_hits": 0, "built_fresh": 0,
                 "mem_deferred": 0}
    blocked: list[dict] = []
    rows: list[dict] = []
    for i, sp in mine:
        n_cells, n_def, n_blk = len(acc["cell_objs"]), len(acc["deferred"]), len(blocked)
        hits0, fresh0, mem0 = acc["cache_hits"], acc["built_fresh"], acc["mem_deferred"]
        s0, s0v = stage0_new_summary(), {}
        acc = _build_specs([sp], meta, build_t0, s0, s0v, built_syms, blocked,
                           cell_objs=acc["cell_objs"], deferred=acc["deferred"],
                           cache_hits=acc["cache_hits"], built_fresh=acc["built_fresh"],
                           _mem_deferred=acc["mem_deferred"])
        if len(acc["cell_objs"]) > n_cells:
            kind, obj = "cell", acc["cell_objs"][-1]
        elif len(acc["deferred"]) > n_def:
            kind, obj = "deferred", acc["deferred"][-1]
        elif len(blocked) > n_blk:
            kind, obj = "blocked", blocked[-1]
        else:
            raise ShardMergeError(f"spec {i} left the build loop in no list")
        rows.append({"idx": i, "kind": kind, "obj": obj, "stage0": (s0, s0v),
                     "cache_hits": acc["cache_hits"] - hits0,
                     "built_fresh": acc["built_fresh"] - fresh0,
                     "mem_deferred": acc["mem_deferred"] - mem0})
    cells = acc["cell_objs"]
    daily, _hits = _cell_series(cells, meta)
    daily_x3 = _cell_series_x3(cells)
    dates: set = set()
    for c, d, d3 in zip(cells, daily, daily_x3, strict=True):
        c["_shard_ds"] = d
        c["_shard_x3_full"] = d3            # carved and dropped in phase `rule`
        c.pop("_cached_ds3", None)
        c.pop("_fresh_ds3", None)
        if d is not None:
            dates.update(d.index)
    out = {"protocol": SHARD_PROTOCOL, "token": plan["token"], "k": k, "n": n, "pid": os.getpid(),
           "phase": "build", "rows": rows, "built_syms": sorted(built_syms),
           "dates": list(dates), "build_seconds": round(time.time() - t0, 3), "basis": basis}
    _pickle_atomic(shard_dir / f"shard_{k}.pkl", out)
    print(f"SHARD {k}/{n} build: {len(rows)} planned cell(s), {len(cells)} built in "
          f"{out['build_seconds']:.1f}s")
    return {"k": k, "n": n, "phase": "build", "seconds": out["build_seconds"]}


def _shard_rule(shard_dir: Path, plan: dict, k: int, meta: dict, t0: float) -> dict:
    """Phase `rule`: the cell-local gates on each cell's DEVELOPMENT window, cut at the union's
    lockbox key exactly as `run_gauntlet` cuts it."""
    _PURE_MEMO.clear()                 # one judging call's memo, as in `run_gauntlet`
    got = _unpickle(shard_dir / "cut.pkl")
    if got.get("token") != plan["token"]:
        raise ShardMergeError("cut.pkl belongs to another plan")
    cut = got["cut"]
    # THE LAW'S DSR BAR, resolved here as `run_gauntlet` resolves it, so this shard can take the
    # deflated-Sharpe and lockbox reads off the merge: since T8 both are pure functions of the
    # cell's own series and that bar. The merge uses them only at an equal bar (`_program_reads`).
    try:
        from research.gate_policy import LOCKBOX_FRAC
        _dsr_bar: float | None = float(constitution_thresholds(LOCKBOX_FRAC)["dsr_threshold"])
    except Exception:
        _dsr_bar = None
    out = _unpickle(shard_dir / f"shard_{k}.pkl")
    if out.get("token") == plan["token"] and out.get("phase") == "rule":
        # RESUMED: ruled already, for this plan. Only at the same cut; its publication is
        # written again (idempotent), because a kill may have come between the two.
        if out.get("cut") != cut:
            raise ShardMergeError(f"shard {k} was ruled at another lockbox cut; rebuild it")
        _publish_shard(plan, k, [dict(r) for r in out.get("published_rows") or []])
        print(f"SHARD {k}/{plan['n']} rule: RESUMED ({out.get('cells_ruled')} cell(s))")
        return {"k": k, "phase": "rule", "cells_ruled": out.get("cells_ruled"), "resumed": True}
    if out.get("token") != plan["token"] or out.get("phase") != "build":
        raise ShardMergeError(f"shard {k} has no build output for this plan")
    n_local = 0
    pub_rows: list[dict[str, Any]] = []
    for row in out["rows"]:
        if row["kind"] != "cell":
            continue
        c = row["obj"]
        full, x3 = c.get("_shard_ds"), c.pop("_shard_x3_full", None)
        # The union's cut, or the cell's own tail when the union leaves it no development window:
        # `cell_dev_cut`, the same rule `run_gauntlet` applies, so the merge's check holds.
        cell_cut = cell_dev_cut(full, cut, frac=plan.get("lockbox_frac"))
        dev, held = (full, None) if (full is None or cell_cut is None) else _split_at(full,
                                                                                      cell_cut)
        if x3 is not None and cell_cut is not None:
            x3 = x3[x3.index < cell_cut]
        # `valid` in run_gauntlet is exactly this predicate on the carved series, so the merge
        # finds local stages on every cell it judges and on no other.
        if dev is not None and len(dev) >= 60:
            _arr = dev.to_numpy(float)
            c["_local_stages"] = _cell_local_stages(c, _arr, x3, meta)
            c["_local_cut"] = cell_cut
            if _dsr_bar is not None:
                _dsr = _dsr_read(_arr, _dsr_bar)
                c["_local_program"] = {"dsr_bar": _dsr_bar, "n": len(_arr),
                                       "n_held": 0 if held is None else len(held), "dsr": _dsr,
                                       "lockbox": _lockbox_read(held, _arr, _dsr[2])}
            n_local += 1
        # The 3x arm is read only by the cell-local stress gate, which is now computed; the cache
        # holds the pair. Dropped so the file carries one series a cell into the merge.
        c["_shard_ds3"] = None
        # WHAT THIS SHARD ALREADY KNOWS, published below the moment the shard is done.
        pub_rows.append(_shard_verdict(c, full, dev, cell_cut))
    pub_rows.extend(_deferred_verdict(r["obj"]) if r["kind"] == "deferred"
                    else _blocked_verdict(r["obj"])
                    for r in out["rows"] if r["kind"] in ("deferred", "blocked"))
    out.update(phase="rule", cut=cut, cells_ruled=n_local,
               seconds=round(out.get("build_seconds", 0.0) + time.time() - t0, 3),
               peak_rss_mb=round(_rss_mb(), 1),
               published_rows=[_final_published(dict(r)) if "verdict_status" not in r
                               else r for r in pub_rows])
    _pickle_atomic(shard_dir / f"shard_{k}.pkl", out)
    print(f"SHARD {k}/{plan['n']} rule: {n_local} cell(s) ruled cell-locally")
    # AFTER the merge's own input is durable: a publication can never stand in for it.
    _publish_shard(plan, k, [dict(r) for r in out["published_rows"]])
    return {"k": k, "phase": "rule", "cells_ruled": n_local}


#: ------------------------------------------------------------ PER-SHARD PUBLICATION (2026-10-20)
#: VERDICTS LANDED ONLY AT THE END OF A SWEEP (IDEA_QUEUE 159). The 10-20 sweep spent 9,729 s in
#: the plan and 4,964 s building before its first cut, and the merge that publishes ran 51,198 s
#: on the box, so a cell ruled by its shard in the first hours was invisible for most of a day.
#:
#: Each shard now PUBLISHES what it already knows when its `rule` phase ends, to
#: `SHARD_PUBLISH_DIR/<plan token>/shard_<k>.json` (write-then-rename, one file per shard, so a
#: shard published twice -- a retry, a resumed sweep -- REPLACES its file and is never counted
#: twice). The merge is untouched: it reads the shards' pickles exactly as before and writes every
#: authority file exactly as before; the publication is a second, read-only copy of what is final.
#:
#: WHAT IS FINAL IN A SHARD, AND WHAT IS NOT. `pbo` and `reality_check_spa` are program-level:
#: computed once, by the merge, on the union matrix. Everything else a verdict holds is a function
#: of the cell alone (`_cell_local_stages`, the fixed per-cell DSR bar of T8, the lockbox read at
#: the cell's own sr0, the union's cut that every shard already holds). So a published row is:
#:   FINAL                      unmeasured (the observations gate), or stopped by a gate that sits
#:                              BEFORE the program-level gates in `stages` order (economic_prior,
#:                              in_sample_screen, deflated_sharpe), or never built (NOT_RUN): its
#:                              `passed` and terminal gate are the merge's, and the merge checks so
#:   REJECTED_TERMINAL_PENDING  failed a cell-local gate that sits AFTER pbo/spa: `passed: false`
#:                              is final, but pbo or spa may yet be its terminal gate
#:   PROVISIONAL                every cell-local gate passed: `passed: null` until the merge has
#:                              PBO and SPA. A provisional row NEVER carries `passed: true`, is
#:                              never a certificate, and nothing that promotes reads this directory
#: No trial is charged here and no program-level number is computed: the DSR bar is the fixed
#: per-cell bar the shard already applied, and the census, PBO, SPA and every sweep-level count
#: stay in the merge, over the whole sweep.
SHARD_PUBLISH_DIR = HYP / "shard_verdicts"
SHARD_PUBLISH_SCHEMA = "shard_verdicts/1"
#: Plans kept on disk; older plan directories are removed by the merge that seals a newer one.
SHARD_PUBLISH_KEEP = 4
PROGRAM_LEVEL_GATES = ("pbo", "reality_check_spa")
#: The stages a verdict holds BEFORE the program-level gates (its `stages` order).
PRE_PROGRAM_GATES = (*CELL_LOCAL_HEAD, "deflated_sharpe")
VERDICT_FINAL = "FINAL"
VERDICT_REJECTED_PENDING = "REJECTED_TERMINAL_PENDING"
VERDICT_PROVISIONAL = "PROVISIONAL"
#: The fields a FINAL published row shares with the merge's verdict, which the merge checks.
PUBLISHED_FINAL_FIELDS = ("passed", "terminal_gate", "terminal_kind", "terminal_gate_id",
                          "terminal_reason", "unknown_reason", "downstream_status", "days")


def _shard_verdict(c: dict[str, Any], full: Any, dev: Any, cell_cut: Any) -> dict[str, Any]:
    """The row a shard publishes for one built cell, from what the shard holds and nothing else.

    `dev` is the development window the shard carved at `cell_cut`; the screen refusal and the
    60-day floor are applied here exactly as `run_gauntlet` applies them, by the same helpers."""
    _ru = c.get("screen_read_until")
    screened = bool(_ru) and dev is not None and not _screen_read_clean(_ru, cell_cut)
    if screened:
        dev = None
    if dev is None or len(dev) < 60:
        v = _unmeasured_verdict(c, dev, None if full is None else len(full), screened=screened)
        v.update(terminal_stamp(v))
        return {**{k: v.get(k) for k in ("cell", "sym", "family", *PUBLISHED_FINAL_FIELDS)},
                "verdict_status": VERDICT_FINAL, "unmeasured": True}
    local = c.get("_local_stages") or {}
    prog = c.get("_local_program")
    stages: dict[str, Any] = {g: local[g] for g in CELL_LOCAL_HEAD if g in local}
    if isinstance(prog, dict) and isinstance(prog.get("dsr"), tuple):
        stages["deflated_sharpe"] = _dsr_stage(len(dev), prog["dsr"])
    for g in CELL_LOCAL_MID:
        if g in local:
            stages[g] = local[g]
    if isinstance(prog, dict) and isinstance(prog.get("lockbox"), dict):
        stages["lockbox"] = prog["lockbox"]
    for g in CELL_LOCAL_TAIL:
        if g in local:
            stages[g] = local[g]
    failed = [g for g, s in stages.items() if not s.get("passed")]
    row: dict[str, Any] = {"cell": cell_id(c), "sym": c["sym"], "family": c["family"],
                           "days": len(dev), "local_failed_gates": failed,
                           "pending_gates": list(PROGRAM_LEVEL_GATES)}
    # A FINAL terminal gate needs every gate before the program-level ones to have been read
    # here; without the shard's DSR read (an unreadable law) only the HEAD can decide it.
    first = failed[0] if failed else None
    if first is not None and first in PRE_PROGRAM_GATES and all(
            g in stages for g in PRE_PROGRAM_GATES[:PRE_PROGRAM_GATES.index(first) + 1]):
        v = {"passed": False, "terminal_gate": first, "stages": {first: stages[first]}}
        row.update({"passed": False, "terminal_gate": first, **terminal_stamp(v),
                    "verdict_status": VERDICT_FINAL})
    elif first is not None:
        row.update({"passed": False, "terminal_gate": None,
                    "terminal_kind": "PENDING", "terminal_gate_id": "PENDING_PROGRAM_GATES",
                    "terminal_reason": (f"rejected by {first}; pbo or reality_check_spa may "
                                        f"still be its terminal gate"),
                    "verdict_status": VERDICT_REJECTED_PENDING})
    else:
        row.update({"passed": None, "terminal_gate": None,
                    "terminal_kind": "PENDING", "terminal_gate_id": "PENDING_PROGRAM_GATES",
                    "terminal_reason": "every cell-local gate passed; PBO and SPA are computed "
                                       "by the merge over the whole sweep",
                    "verdict_status": VERDICT_PROVISIONAL})
    return row


def _final_published(v: dict[str, Any]) -> dict[str, Any]:
    """A row the plan or a shard's build settled for good (gate 0, NOT_RUN): stamped, FINAL."""
    v.update(terminal_stamp(v))
    return {**{k: v.get(k) for k in ("cell", "sym", "family", *PUBLISHED_FINAL_FIELDS)},
            "verdict_status": VERDICT_FINAL}


def _publish_shard(plan: dict[str, Any], k: int | str, rows: list[dict[str, Any]]) -> Path | None:
    """Write one shard's publication, atomically. Bookkeeping: it never fails the shard.

    `k` is the shard index, or "plan" for the rows the plan itself settled (gate 0 and the
    build preflight). A row that would claim `passed: true` is refused here, not published."""
    pub = plan.get("publication") if isinstance(plan, dict) else None
    if not isinstance(pub, dict) or not pub.get("dir"):
        return None
    try:
        out_rows = []
        for r in rows:
            if "verdict_status" not in r:
                r = _final_published(r)
            if r.get("passed") is True:
                raise ShardMergeError(f"{r.get('cell')}: a shard publication may never pass a "
                                      f"cell; PBO and SPA are the merge's")
            out_rows.append(r)
        d = Path(pub["dir"]) / str(plan["token"])
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"shard_{k}.json"
        tmp = f.with_name(f"{f.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps({
            "schema": SHARD_PUBLISH_SCHEMA, "token": plan["token"], "k": k, "n": plan.get("n"),
            "published_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "status_note": "FINAL rows are the merge's verdict; PROVISIONAL and "
                           "REJECTED_TERMINAL_PENDING wait for PBO and SPA; nothing here passes",
            "rows": out_rows}, default=str), encoding="utf-8")
        os.replace(tmp, f)
        print(f"SHARD {k} published {len(out_rows)} row(s) -> {f}")
        return f
    except ShardMergeError:
        raise
    except Exception as exc:  # the merge is the record; this copy may fail
        print(f"SHARD {k} publication not written ({type(exc).__name__}: {exc})")
        return None


def _seal_shard_publication(verdicts: list[Any]) -> dict[str, Any]:
    """After the merge wrote its records: check every FINAL published row against the merge's
    verdict, write `MERGED.json` beside the shard files and prune old plans. Report only."""
    pub = (_SHARD or {}).get("publication")
    if not isinstance(pub, dict) or not pub.get("token"):
        return _unmeasured("no sharded publication this sweep")
    d = Path(str(pub["dir"])) / str(pub["token"])
    final = {str(v.get("cell")): v for v in verdicts if isinstance(v, dict) and v.get("cell")}
    agree = disagree = absent = provisional = pending = rows = 0
    sample: list[dict[str, Any]] = []
    seen: set[str] = set()
    for f in sorted(d.glob("shard_*.json")):
        try:
            doc = json.loads(f.read_text("utf-8"))
        except (OSError, ValueError) as exc:
            sample.append({"file": f.name, "unreadable": type(exc).__name__})
            continue
        for r in doc.get("rows") or []:
            cid = str(r.get("cell"))
            if cid in seen:
                continue                 # one row per cell per plan: never counted twice
            seen.add(cid)
            rows += 1
            st = r.get("verdict_status")
            v = final.get(cid)
            if v is None:
                absent += 1
                if len(sample) < 20:
                    sample.append({"cell": cid, "absent_from_merge": True})
                continue
            if st == VERDICT_PROVISIONAL:
                provisional += 1
                continue
            if st == VERDICT_REJECTED_PENDING:
                pending += 1
                ok = v.get("passed") is False
            else:
                ok = all(r.get(k) == v.get(k) for k in PUBLISHED_FINAL_FIELDS)
            agree += ok
            disagree += not ok
            if not ok and len(sample) < 20:
                sample.append({"cell": cid, "status": st, **{
                    k: [r.get(k), v.get(k)] for k in PUBLISHED_FINAL_FIELDS
                    if r.get(k) != v.get(k)}})
    doc = {"schema": SHARD_PUBLISH_SCHEMA, "token": pub["token"],
           "merged_at": datetime.now(UTC).isoformat(timespec="seconds"),
           "published_rows": rows, "final_rows_agree": agree, "final_rows_disagree": disagree,
           "rejected_pending_rows": pending, "provisional_rows": provisional,
           "absent_from_merge": absent, "sample": sample,
           "rule": "the merge's verdicts are the record; these files were a provisional copy"}
    try:
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / f"MERGED.json.{os.getpid()}.tmp"
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, d / "MERGED.json")
        import shutil
        plans = sorted((p for p in Path(str(pub["dir"])).iterdir() if p.is_dir()),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        for old in plans[SHARD_PUBLISH_KEEP:]:
            if old.name != str(pub["token"]):
                shutil.rmtree(old, ignore_errors=True)
    except OSError as exc:
        doc["write_error"] = str(exc)[:160]
    if disagree or absent:
        print(f"SHARD PUBLICATION DISAGREES WITH THE MERGE: {disagree} final row(s) differ, "
              f"{absent} absent from the merge; first: {sample[:3]}")
    return doc


#: ------------------------------------------------------------ THE PERSISTED PLAN (2026-10-20)
#: A RESTART RESUMES; IT DOES NOT RE-PLAN (IDEA_QUEUE 159). Two levels, both fail-safe -- any doubt
#: re-plans or rebuilds, exactly as every sweep did before:
#:   * THE SWEEP PLAN (`sweep_plan.pkl` in the shard directory): what `_plan_phase` made, with the
#:     code identity (the replay code, the gate policy, the gate spec), the universe and the
#:     docket it was made from. A restart reuses it while code, law and universe are unchanged and
#:     it is younger than `PLAN_RESUME_MAX_AGE_S`. A changed docket does not discard it: only the
#:     cells whose SPEC changed are re-planned (gate 0 and the preflight, in place), removed cells
#:     leave, and cells new to the docket wait for the next full plan. A changed DATA-day is the
#:     build's business: a cell's series cache key carries it, and a shard whose cells' keys moved
#:     is rebuilt (below). Deleted once the merge's verdicts are durable.
#:   * EACH SHARD'S OUTPUT: kept until the merge is durable, and reused by a later plan for the
#:     same shard when its basis -- code, law, universe and its own specs in order -- is equal and
#:     every cell's series key is still the one it was built under. A shard already ruled at the
#:     same lockbox cut is not ruled again; one ruled at another cut is rebuilt.
#: Reuse never changes a verdict: the same cells, built from the same data by the same code, go
#: through the same merge; the equality harness (judge_funnel_shards) compares a killed-and-
#: resumed sweep's records with an uninterrupted one's.
SWEEP_PLAN_NAME = "sweep_plan.pkl"
SWEEP_PLAN_PROTOCOL = 1
PLAN_RESUME_MAX_AGE_S = float(os.environ.get("GAUNTLET_PLAN_RESUME_MAX_AGE_S", str(24 * 3600)))
#: A plan whose lockbox cut keeps moving after this many shard rebuilds is rebuilt whole.
CUT_SETTLE_ROUNDS = 3


def _digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
                          ).hexdigest()


def _plan_code_identity() -> str:
    """The replay code identity plus the law: the gate policy and the gate spec."""
    h = hashlib.sha256(_replay_code_identity().encode("utf-8"))
    desk = BASE / "desks" / "mt5"
    for p in (desk / "research" / "gate_policy.py", desk / "policy" / "gate_spec.yaml"):
        try:
            h.update(p.read_bytes().replace(b"\r\n", b"\n"))
        except OSError:
            h.update(b"<absent>")
    return h.hexdigest()


def _docket_signature(path: Path) -> dict[str, Any]:
    st = path.stat()
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return {"size": st.st_size, "sha256": h.hexdigest()}


def _sweep_plan_path() -> Path | None:
    if _SHARD is None or not _SHARD.get("resume") or _repro_active():
        return None
    return Path(str(_SHARD.get("dir") or SHARD_DIR)) / SWEEP_PLAN_NAME


def _cid(spec: dict[str, Any]) -> str:
    try:
        return str(cell_id({"sym": spec.get("sym"), "family": spec.get("family"),
                            "params": spec.get("params") or {}}))
    except Exception:
        return ""


def _persist_plan(st: dict[str, Any], surv_file: Path, plan_s: float | None = None) -> None:
    """Write the plan a restart may resume. Bookkeeping: a failure only costs the resume.
    `plan_s` is the plan's measured wall: what a resume of it does not spend again."""
    path = _sweep_plan_path()
    if path is None:
        return
    try:
        ids = {_cid(s) for s in [*st["eligible_specs"], *st["blocked_build"]]}
        ids |= {str(r.get("cell") or "") for r in st["prior_rejections"]}
        # Only the docket cells this plan gives a row: the record's spec lookup needs no other.
        keep = {k: s for k, s in st["cells"].items() if _cid(s) in ids}
        doc = {"protocol": SWEEP_PLAN_PROTOCOL, "created_at": time.time(),
               "plan_seconds": None if plan_s is None else round(float(plan_s), 1),
               "code": _plan_code_identity(), "meta": _digest(st["meta"]),
               "docket": _docket_signature(surv_file),
               "spec_digests": {k: _digest(s) for k, s in keep.items()},
               "state": {**st, "cells": keep}}
        _pickle_atomic(path, doc)
        print(f"PLAN PERSISTED: {len(st['eligible_specs'])} planned cell(s) -> {path}")
    except Exception as exc:
        print(f"PLAN not persisted ({type(exc).__name__}: {exc}); a restart re-plans")


def _resume_plan(cells: dict[str, Any], meta: dict[str, Any],
                 surv_file: Path) -> dict[str, Any] | None:
    """The persisted plan, if a restart may resume it; None means: plan from scratch."""
    _PLAN_RESUME_DOC.clear()
    path = _sweep_plan_path()
    if path is None or not path.exists():
        return None
    try:
        doc = _unpickle(path)
        why = None
        if not isinstance(doc, dict) or doc.get("protocol") != SWEEP_PLAN_PROTOCOL:
            why = "another plan protocol"
        elif doc.get("code") != _plan_code_identity():
            why = "the judge's code or law changed"
        elif doc.get("meta") != _digest(meta):
            why = "the universe changed"
        elif time.time() - float(doc.get("created_at") or 0.0) > PLAN_RESUME_MAX_AGE_S:
            why = f"older than {PLAN_RESUME_MAX_AGE_S:.0f}s"
        if why is not None:
            print(f"PLAN RE-MADE: the persisted plan is not resumable ({why})")
            path.unlink(missing_ok=True)
            return None
        st = dict(doc["state"])
        same = _docket_signature(surv_file) == doc.get("docket")
        report: dict[str, Any] = {"resumed": True,
                                  "plan_age_s": round(time.time() - float(doc["created_at"]), 1),
                                  "docket_unchanged": same}
        if not same:
            st, diff = _replan_changed(st, doc.get("spec_digests") or {}, cells, meta)
            report.update(diff)
        # A FRESH BUILD BUDGET for whatever the interrupted sweep did not reach.
        st["_build_t0"] = time.time()
        # THE SEEN-CELLS MAP AND THE BUILD CURSOR ARE READ FROM DISK, never the pickled copies
        # (audit of b94babf39). A kill between the ledger append and the cleanup had already
        # stamped them; the pickle's older maps made the resumed sweep move `first_judged` later
        # and re-stamp cells the killed one recorded. The plan's ORDER is unchanged: it was set
        # from the maps the plan was made with, and only the stamps read these.
        st["_seen"], st["_cursor"] = _seen_cells(), _build_cursor()
        st["plan_resume"] = report
        _note_plan_resume(**report, planned_at=datetime.fromtimestamp(
            float(doc["created_at"]), UTC).isoformat(timespec="seconds"),
            max_age_s=PLAN_RESUME_MAX_AGE_S, plan_seconds_saved=doc.get("plan_seconds"))
        print(f"PLAN RESUMED: {len(st['eligible_specs'])} planned cell(s), {report}")
        return st
    except Exception as exc:
        print(f"PLAN RE-MADE: the persisted plan is unreadable ({type(exc).__name__}: {exc})")
        return None


#: WHAT THIS SWEEP'S RESUME DID, for the launcher's two-sided missed-growth line (audit HOLD of
#: b94babf39): the cells it set aside against the plan and build wall it did not spend again.
#: Stamped with this process's pid and the time, so the launcher never bills an older record.
PLAN_RESUME_NAME = "plan_resume.json"
_PLAN_RESUME_DOC: dict[str, Any] = {}


def _note_plan_resume(**fields: Any) -> None:
    """Merge `fields` into this sweep's resume record and write it beside the plan.
    Bookkeeping: a failure costs only the missed-growth line, which then reads absent."""
    if _SHARD is None:
        return
    _PLAN_RESUME_DOC.update(fields, pid=os.getpid(),
                            at=datetime.now(UTC).isoformat(timespec="seconds"))
    try:
        dest = Path(str(_SHARD.get("dir") or SHARD_DIR)) / PLAN_RESUME_NAME
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(f"{dest.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(_PLAN_RESUME_DOC, default=str), encoding="utf-8")
        os.replace(tmp, dest)
    except Exception as exc:
        print(f"  plan-resume record not written ({type(exc).__name__}: {exc})")


def _replan_changed(st: dict[str, Any], digests: dict[str, str], cells: dict[str, Any],
                    meta: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Re-plan ONLY the cells whose spec changed; drop removed ones; leave new ones to the next
    full plan. A changed cell keeps its slot when it still advances, and joins the tail when it
    advances for the first time."""
    old = st["cells"]
    changed = [k for k in old if k in cells and _digest(cells[k]) != digests.get(k)]
    removed = [k for k in old if k not in cells]
    gone = {_cid(old[k]) for k in [*changed, *removed]}
    new_specs = [cells[k] for k in changed]
    elig, rej = partition_at_economic_prior(new_specs, meta)
    ready, blocked = _preflight_split(elig)
    ready_by_id = {_cid(s): s for s in ready}
    # A changed spec may carry a new cell id (its params moved): its slot is found by docket key.
    new_of_old = {_cid(old[k]): _cid(cells[k]) for k in changed}
    out = dict(st)
    planned: list[dict[str, Any]] = []
    for sp in st["eligible_specs"]:
        cid = _cid(sp)
        if cid not in gone:
            planned.append(sp)
        elif new_of_old.get(cid) in ready_by_id:
            planned.append(ready_by_id.pop(new_of_old[cid]))  # re-planned in place
    planned.extend(ready_by_id.values())                    # newly advancing: the tail
    out["eligible_specs"] = planned
    out["n_cells"] = len(cells)                             # the docket in hand, as main counts it
    out["prior_rejections"] = [r for r in st["prior_rejections"]
                               if str(r.get("cell") or "") not in gone] + rej
    out["blocked_build"] = [b for b in st["blocked_build"] if _cid(b) not in gone] + blocked
    out["cells"] = {k: (cells[k] if k in changed else s) for k, s in old.items()
                    if k not in removed}
    waiting = sum(1 for k in cells if k not in old)
    return out, {"cells_changed_replanned": len(changed), "cells_removed": len(removed),
                 "cells_not_in_this_plan": waiting,
                 "note": "cells not in this plan (new, or set aside by the plan's own order and "
                         "allocation) are judged by the next full plan"}


def _sweep_cleanup() -> dict[str, Any]:
    """The merge's verdicts are durable: drop the plan and the shard outputs kept for a resume."""
    if _SHARD is None or not _SHARD.get("resume"):
        return {"cleaned": 0}
    d = Path(str(_SHARD.get("dir") or SHARD_DIR))
    gone = 0
    for f in [*d.glob("shard_*.pkl"), d / "cut.pkl", d / SWEEP_PLAN_NAME]:
        if f.exists():
            f.unlink(missing_ok=True)
            gone += 1
    return {"cleaned": gone}


def _shard_basis(plan: dict[str, Any], mine: list[Any]) -> dict[str, Any]:
    """What a shard's output was made from: reusable only when every part is equal."""
    return {"code": plan.get("code"), "lockbox_frac": plan.get("lockbox_frac"),
            "meta": plan.get("meta_digest"), "n": plan.get("n"),
            "specs": _digest([sp for _, sp in mine])}


def _rows_current(rows: list[dict[str, Any]], mine: list[Any]) -> bool:
    """Every built cell's series key is still the one it was built under; no cell blocked for
    missing bars now has them. Reads only the frames (the build's own first step).

    THE DAY IS READ FRESH, ONCE PER CHART (stack resolution, 2026-10-20). Never from `_LAST_DAY`:
    that memo is seeded from the plan's pool days, and this check exists to see the data MOVE.
    And not one `_bars_for` per row: that is the per-spec parquet re-read that cost each build
    shard ~4,400 s on box sweep 23324. `_index_last_day`, else `_bars_for`, the same answer."""
    days: dict[tuple[str, str], object] = {}

    def _day(sym: str, tf: str):
        key = (str(sym), str(tf).upper())
        if key not in days:
            pq = UNI / f"{key[0]}_{key[1]}.parquet"
            d = _index_last_day(pq) if pq.exists() else None
            if d is None:
                frame = _bars_for(key[0], key[1])
                d = None if frame is None or len(frame) == 0 else frame.index[-1].normalize()
            days[key] = d
        return days[key]

    for row, (_i, sp) in zip(rows, mine, strict=True):
        tf = timeframe_of(sp.get("params"), str(sp.get("family") or ""))
        if row["kind"] == "cell":
            day = _day(sp["sym"], tf)
            if day is None:
                return False
            key = _cache_key(sp["sym"], sp["family"], sp["params"] or {},
                             str(day.date()), tf)
            if key != row["obj"].get("_ckey"):
                return False
        elif row["kind"] == "blocked" and \
                row["obj"].get("downstream_status") == "NOT_RUN_DATA_MISSING":
            if _day(sp["sym"], tf) is not None:
                return False
    return True


def _resume_shard_build(shard_dir: Path, plan: dict[str, Any], k: int, mine: list[Any],
                        basis: dict[str, Any]) -> dict[str, Any] | None:
    """Reuse shard `k`'s previous output for this plan, re-stamped, or None to build it."""
    f = shard_dir / f"shard_{k}.pkl"
    if not f.exists():
        return None
    try:
        out = _unpickle(f)
    except Exception:
        return None
    if (not isinstance(out, dict) or out.get("protocol") != SHARD_PROTOCOL
            or out.get("basis") != basis or out.get("phase") not in ("build", "rule")
            or len(out.get("rows") or []) != len(mine) or not _rows_current(out["rows"], mine)):
        return None
    for (i, _sp), row in zip(mine, out["rows"], strict=True):
        row["idx"] = i
    out.update(token=plan["token"], k=k, n=plan["n"], resumed=True)
    _pickle_atomic(f, out)
    print(f"SHARD {k}/{plan['n']} build: RESUMED ({out['phase']} output for the same "
          f"{len(mine)} cell(s), code, law and data)")
    return {"k": k, "n": plan["n"], "phase": "build", "seconds": 0.0, "resumed": True}


def _stage0_fold(summary: dict, verdicts: dict, parts: list) -> None:
    """Replay per-spec Stage 0 records into one summary in plan order -- the same counts, key
    order and bounded samples `stage0_record` produces when it runs over the docket in sequence."""
    for s0, s0v in parts:
        for key in ("rejected", "escalated", "unjudged_no_series_before_build", "unjudged_error"):
            summary[key] += int(s0.get(key, 0))
        for reason, cnt in (s0.get("why_counts") or {}).items():
            summary["why_counts"][reason] = summary["why_counts"].get(reason, 0) + cnt
        for key, slot in (s0.get("by_decision") or {}).items():
            dst = summary["by_decision"].setdefault(key, {"n": 0, "sample": []})
            dst["n"] += slot["n"]
            for cid in slot["sample"]:
                if len(dst["sample"]) < 20:
                    dst["sample"].append(cid)
        if s0.get("errors"):
            summary.setdefault("errors", []).extend(s0["errors"])
        verdicts.update(s0v)


def _shard_collect(shard_dir: Path, plan: dict, phase: str = "rule") -> dict:
    """Read every shard's file and restore the plan's order, or refuse. Fails CLOSED."""
    n, specs = int(plan["n"]), list(plan["specs"])
    rows_by_idx: dict[int, dict] = {}
    reports: list[dict] = []
    phases: dict[int, tuple[Any, Any]] = {}
    built_syms: set[str] = set()
    dates: set = set()
    resumed_s: dict[int, float] = {}
    kept_deferred: dict[int, int] = {}
    for k in range(n):
        f = shard_dir / f"shard_{k}.pkl"
        if not f.exists():
            raise ShardMergeError(f"shard {k}/{n} wrote no output; nothing is published")
        out = _unpickle(f)
        if (out.get("protocol") != SHARD_PROTOCOL or out.get("token") != plan["token"]
                or int(out.get("k", -1)) != k or int(out.get("n", -1)) != n
                or not (out.get("phase") == phase
                        or (phase == "build" and out.get("phase") == "rule"))):
            raise ShardMergeError(f"shard {k}/{n} output is stale, unfinished ({out.get('phase')}"
                                  f" != {phase}) or belongs to another plan")
        if phase == "rule" and out.get("cut") != plan.get("cut"):
            raise ShardMergeError(f"shard {k} ruled on a different lockbox cut")
        for row in out["rows"]:
            i = int(row["idx"])
            if not 0 <= i < len(specs) or shard_of(specs[i], n) != k:
                raise ShardMergeError(f"shard {k} returned cell {i}, which it does not own")
            if i in rows_by_idx:
                raise ShardMergeError(f"cell {i} was ruled twice")
            if row["kind"] == "cell" and (str(row["obj"].get("sym")) != str(specs[i]["sym"])
                                          or str(row["obj"].get("family"))
                                          != str(specs[i]["family"])):
                raise ShardMergeError(f"cell {i} came back as a different cell")
            rows_by_idx[i] = row
        built_syms |= set(out.get("built_syms") or ())
        dates.update(out.get("dates") or ())
        reports.append({"k": k, "planned": len(out["rows"]), "ruled": out.get("cells_ruled"),
                        "seconds": out.get("seconds"), "peak_rss_mb": out.get("peak_rss_mb")})
        phases[k] = (out.get("phase"), out.get("cut"))
        if out.get("resumed"):
            resumed_s[k] = float(out.get("build_seconds") or 0.0)
            # A REUSED SHARD KEEPS ITS DEFERRALS (audit of b94babf39): the killed sweep's budget
            # deferred them, and rebuilding every shard that holds one would end reuse outright
            # (measured: no shard reused in any harness resume). Counted, so the resume's
            # missed-growth line bills them against the build wall the reuse saved.
            kept_deferred[k] = sum(1 for r in out["rows"] if r.get("kind") == "deferred")
    missing = len(specs) - len(rows_by_idx)
    if missing:
        raise ShardMergeError(f"{missing} planned cell(s) came back from no shard")
    cell_objs: list[dict] = []
    deferred: list[dict] = []
    blocked: list[dict] = []
    parts: list = []
    hits = fresh = mem = 0
    for i in range(len(specs)):
        row = rows_by_idx[i]
        {"cell": cell_objs, "deferred": deferred, "blocked": blocked}[row["kind"]].append(
            row["obj"])
        parts.append(row["stage0"])
        hits += int(row["cache_hits"])
        fresh += int(row["built_fresh"])
        mem += int(row["mem_deferred"])
    return {"cell_objs": cell_objs, "deferred": deferred, "blocked": blocked,
            "stage0_parts": parts, "cache_hits": hits, "built_fresh": fresh,
            "mem_deferred": mem, "built_syms": built_syms, "dates": dates,
            "shard_phases": phases, "resumed_build_s": resumed_s,
            "resumed_kept_deferred": kept_deferred,
            "report": {"protocol": SHARD_PROTOCOL, "n_shards": n, "planned_cells": len(specs),
                       "each_cell_ruled_once": True,
                       "program_level": "computed once on the union matrix by the merge",
                       "shards": reports}}


def _run_shards(eligible_specs: list, meta: dict, build_t0: float,
                pre_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Write the plan, hand it to the launcher's dispatcher, and collect. Called from `main`.

    `pre_rows` are the verdict rows the plan itself settled before any shard ran (gate 0, the
    build preflight); they are published with the plan, under the same token as the shards."""
    cfg = _SHARD or {}
    n = int(cfg["n"])
    shard_dir = Path(cfg.get("dir") or SHARD_DIR)
    shard_dir.mkdir(parents=True, exist_ok=True)
    _resume = bool(cfg.get("resume"))
    # A RESUMING SWEEP KEEPS EACH SHARD'S OUTPUT: `shard_worker` reuses the one whose basis and
    # data are unchanged and rebuilds the rest. Otherwise every stale file goes, as before.
    for f in (list(shard_dir.glob("*.tmp")) + [shard_dir / "cut.pkl"]
              + [f for f in shard_dir.glob("shard_*.pkl")
                 if not _resume or not f.stem.removeprefix("shard_").isdigit()
                 or int(f.stem.removeprefix("shard_")) >= n]):
        f.unlink(missing_ok=True)
    token = hashlib.sha256(f"{os.getpid()}:{time.time_ns()}:{len(eligible_specs)}".encode()
                           ).hexdigest()[:16]
    # THE HELD-OUT SHARE OF THE LAW IN FORCE (S01), resolved once for the plan: the union cut
    # here and every shard's per-cell cut use it, and `run_gauntlet` resolves the same law in the
    # merge -- a law that changed in between moves its cut, and the merge refuses the sweep.
    from research.gate_policy import LOCKBOX_FRAC
    _lock_frac = float(constitution_thresholds(LOCKBOX_FRAC)["lockbox_min_fraction"])
    _pub_dir = cfg.get("publish_dir")
    plan = {"protocol": SHARD_PROTOCOL, "n": n, "token": token, "build_t0": float(build_t0),
            "owner_pid": os.getpid(), "meta": meta, "specs": list(eligible_specs),
            "lockbox_frac": _lock_frac, "last_days": dict(_LAST_DAY),
            "publication": {"dir": str(_pub_dir)} if _pub_dir else None,
            "resume": _resume, "code": _plan_code_identity(), "meta_digest": _digest(meta)}
    _pickle_atomic(shard_dir / "plan.pkl", plan)
    if _SHARD is not None and _pub_dir:
        _SHARD["publication"] = {"dir": str(_pub_dir), "token": token}
    if pre_rows:
        _publish_shard(plan, "plan", [dict(r) for r in pre_rows])
    print(f"SHARDED SWEEP: {len(eligible_specs)} planned cell(s) across {n} shard(s)")
    t0 = time.time()
    dispatch = cfg["dispatch"]
    dispatch(shard_dir, n, "build")  # type: ignore[operator]
    t_build = time.time() - t0
    built = _shard_collect(shard_dir, plan, phase="build")
    # THE ONE LOCKBOX CUT, from the union of every shard's dates -- the same calendar
    # `run_gauntlet` builds from the same series (`lockbox_cut` reads only each series' index).
    from research.gate_policy import lockbox_cut

    class _Dates:
        def __init__(self, index: list) -> None:
            self.index = index

    plan["cut"] = lockbox_cut([_Dates(list(built["dates"]))], frac=_lock_frac)
    # A RESUMED SHARD RULED AT ANOTHER CUT cannot be re-ruled (its 3x arm is gone): rebuild it,
    # then take the cut again, until no ruled output disagrees -- or rebuild the plan whole.
    for _round in range(CUT_SETTLE_ROUNDS + 1):
        stale = [k for k, (ph, ct) in built.get("shard_phases", {}).items()
                 if ph == "rule" and ct != plan["cut"]]
        if not stale:
            break
        if _round == CUT_SETTLE_ROUNDS:
            stale = list(range(n))
        print(f"SHARDED SWEEP: {len(stale)} resumed shard(s) ruled at another cut: rebuilt")
        for k in stale:
            (shard_dir / f"shard_{k}.pkl").unlink(missing_ok=True)
        dispatch(shard_dir, n, "build")  # type: ignore[operator]
        built = _shard_collect(shard_dir, plan, phase="build")
        plan["cut"] = lockbox_cut([_Dates(list(built["dates"]))], frac=_lock_frac)
    _pickle_atomic(shard_dir / "cut.pkl", {"token": token, "cut": plan["cut"]})
    if _PLAN_RESUME_DOC:
        _saved = built.get("resumed_build_s") or {}
        _note_plan_resume(shards_reused=sorted(_saved),
                          build_seconds_saved=round(sum(_saved.values()), 1),
                          cells_kept_deferred=sum(
                              (built.get("resumed_kept_deferred") or {}).values()))
    dispatch(shard_dir, n, "rule")  # type: ignore[operator]
    got = _shard_collect(shard_dir, plan, phase="rule")
    got["report"].update(dispatch_seconds=round(time.time() - t0, 3),
                         build_phase_seconds=round(t_build, 3), lockbox_cut=str(plan["cut"]))
    if not _resume:                  # a resuming sweep keeps them until its merge is durable
        for f in [*shard_dir.glob("shard_*.pkl"), shard_dir / "cut.pkl"]:
            f.unlink(missing_ok=True)
    return got


def run_sharded(n_shards: int, dispatch, shard_dir: Path | str | None = None,
                need_mb: int | None = None, resume: bool | None = None) -> int:
    """The certifying sweep, sharded N ways, under the SAME two locks `_cli_main` takes.

    `dispatch(shard_dir, n, phase)` must run `shard_worker(shard_dir, k, phase)` for every k in
    0..n-1 (in any order, concurrently or not) and return when all have finished. It is called
    twice, `build` then `rule`; the merge verifies the
    result rather than trusting it. Returns 0 after a sweep and 75 when the lane was not granted.
    `need_mb` is the admission ask for the whole sharded sweep (default: this process's budget).
    """
    global _SHARD
    if int(n_shards) < 1:
        raise ValueError("n_shards must be >= 1")
    if _repro_active():
        raise RuntimeError("reproduction (--only) is never sharded")
    from research.job_lock import exclusive_job
    _need = int(MEMORY_BUDGET_MB) if need_mb is None else int(need_mb)
    with exclusive_job("certification_lane", need_mb=_need) as lane:
        if not lane:
            print("external_gauntlet (sharded): DEFERRED -- another canonical certifier owns "
                  "the lane")
            return 75
        with exclusive_job("external_gauntlet", need_mb=0) as acquired:
            if not acquired:
                return 75
            _SHARD = {"n": int(n_shards), "dispatch": dispatch,
                      "dir": Path(shard_dir) if shard_dir else SHARD_DIR,
                      # Every production sweep publishes per shard; a caller that drives
                      # `_run_shards` itself (a harness, a test) opts in with its own dir.
                      "publish_dir": SHARD_PUBLISH_DIR,
                      # THE PERSISTED PLAN: on unless GAUNTLET_PLAN_RESUME=0 or the caller says.
                      "resume": (os.environ.get("GAUNTLET_PLAN_RESUME", "1") != "0"
                                 if resume is None else bool(resume))}
            try:
                main()
            finally:
                _SHARD = None
            return 0


def _build_specs(eligible_specs: list, meta: dict, _build_t0: float, _stage0: dict,
                 _stage0_verdicts: dict, _built_syms: set, blocked_build: list, *,
                 cell_objs: list | None = None, deferred: list | None = None,
                 cache_hits: int = 0, built_fresh: int = 0, _mem_deferred: int = 0) -> dict:
    """THE BUILD LOOP, MOVED VERBATIM OUT OF `main` so a shard runs the same lines.

    Every spec leaves in exactly one of three places -- `cell_objs` (cached or freshly built),
    `deferred` (build or memory budget) or `blocked_build` (data missing, build failed) -- and
    the lists and counters are passed in and handed back, so a caller may drive it over the
    whole docket (the unsharded sweep) or one spec at a time (`shard_worker`) and read which
    list grew. Nothing in the loop reads another spec's outcome.
    """
    cell_objs = [] if cell_objs is None else cell_objs
    deferred = [] if deferred is None else deferred
    for spec in eligible_specs:
        key = f"{spec['sym']}.{spec['family']}.{json.dumps(spec['params'], sort_keys=True)}"
        spec_tf = timeframe_of(spec.get("params"), str(spec.get("family") or ""))
        # THE CELL'S OWN CHART DECIDES ITS DATA-DAY. `last_day` is both the cache key's rollover
        # and the boundary `_series_trim_partial` drops the partial day at; taking it from H1 for
        # an M5 cell would key the cell to a day its own tape may not have reached and trim its
        # series at a boundary from a different feed.
        last_day = _cell_last_day(spec["sym"], spec_tf)
        if last_day is None:
            print(f"  SKIP {key}: {spec_tf} parquet missing")
            blocked_build.append({**spec, "downstream_status": "NOT_RUN_DATA_MISSING",
                                  "why": f"point-in-time {spec_tf} parquet is missing or empty"})
            continue
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
                # Provenance rides onto the cell: the screen's read-until stamp and the LLM
                # look-ahead guard's inputs, so neither gate can be bypassed by the cache.
                **{k: spec[k] for k in CARRIED_SPEC_KEYS if spec.get(k) is not None},
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
        try:
            obj = build_cell(spec["sym"], spec["family"], spec["params"], meta)
        except Exception as exc_read:
            if not _unreadable_chart(exc_read):
                raise
            # ONE BAD FILE BLOCKS ITS OWN CELLS, NEVER THE SHARD: named, blocked, not judged, so
            # no trial is charged; the coverage organ re-admits the cell when the chart changes.
            _why = _unreadable_why(str(spec["sym"]), spec_tf, exc_read)
            print(f"  SKIP {key}: {_why}")
            blocked_build.append({**spec, "downstream_status": "NOT_RUN_BUILD_FAILED",
                                  "why": _why})
            continue
        if obj:
            _day = _built_day(obj, last_day)
            if _day != last_day:
                last_day = _day           # keyed and trimmed by the frame it was built from
                ckey = _cache_key(spec["sym"], spec["family"], spec["params"] or {},
                                  str(last_day.date()), spec_tf)
            obj["mechanism_status"] = spec.get("mechanism_status")
            obj["mechanism_note"] = spec.get("mechanism_note")
            for _k in CARRIED_SPEC_KEYS:
                if spec.get(_k) is not None:
                    obj[_k] = spec[_k]
            obj["_ckey"], obj["_last_day"] = ckey, last_day
            cell_objs.append(obj)
            built_fresh += 1
            _stage0["unjudged_no_series_before_build"] += 1
        else:
            _why = LAST_BUILD_FAILURE or "parquet missing or build failed"
            print(f"  SKIP {key}: {_why}")
            blocked_build.append({**spec, "downstream_status": (
                                      "NOT_RUN_MODIFIER" if _why.startswith("NOT_RUN_MODIFIER")
                                      else "NOT_RUN_BUILD_FAILED"),
                                  "why": LAST_BUILD_FAILURE
                                  or "signal construction returned no executable cell"})
    return {"cell_objs": cell_objs, "deferred": deferred, "cache_hits": cache_hits,
            "built_fresh": built_fresh, "mem_deferred": _mem_deferred}


if __name__ == "__main__":
    raise SystemExit(_cli_main())
