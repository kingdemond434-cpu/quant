"""THE TWO-STAGE JUDGE, STAGE 1: a charged, formal first ruling on EVERY never-judged docket cell.

    "5300 a day isn't enough in our ratio of 1.5M mined, we need judging like 100-500k a day"
                                                                  -- the principal, 2026-09-30

WHY TWO STAGES. The sealed gauntlet (`scripts/external_gauntlet.py`) rules ~5,300 cells a day
against ~8,300 minted and a backlog of ~1.4M. Half of what it does rule comes back UNKNOWN or as a
build failure. Every one of those is a full sweep slot spent on a cell nobody had looked at once.
Stage 1 is the look: it builds each backlog cell with the gauntlet's OWN unsealed builder
(`external_gauntlet.build_cell`, the frame LRU, `daily_series`, `costs_for` -- the functions the
cache warmer already imports) and rules on it from the TRAINING WINDOW ONLY. Only its survivors
go to the full ten gates, at the front of the judge's order.

WHAT IS READ, AND WHAT IS NEVER READ. One replay of the cell's signals at 1x cost gives its
active-day calendar; statistics are then taken only on days strictly before

  * the earliest day the sealed walk-forward TEST region can start. The gauntlet runs its
    walk-forward on the DEVELOPMENT series (after the lockbox carve), whose length is not known
    here, so the bound is the minimum of the WF start rank over every development length the
    cell could have (`wf_start_lb`) -- `mass_screen.wf_start_rank`, pinned against the sealed
    source by test_mass_screen, and
  * a lower bound on the sealed lockbox cut (`lockbox_cut_lb`): the gauntlet reserves the last
    `gate_policy.LOCKBOX_FRAC` of the UNION calendar of a sweep; with trading days at least
    5-of-7 dense that cut can be no earlier than `T - LOCKBOX_FRAC x 7/5 x (T - earliest bar in
    the universe)`.

THE FULL TRAINING WINDOW (audit 2026-09-30). Everything before those two lower bounds is used; an
earlier version also capped the window at mass_screen's TRAIN_FRAC (30%) of the chart calendar,
which left ~16% of history and made the screen blind below t~10. That cap is gone.

THE WINDOW (coordinator's ruling 2026-09-30, REVERSED the same day -- PR143_v3). The default,
"pre_wf", screens only days before BOTH the walk-forward lower bound and the lockbox lower bound,
so the sealed walk-forward test region stays out-of-sample. "pre_lockbox" (STAGE1_WINDOW=
pre_lockbox, opt-in) also reads the walk-forward region, for ORDER only. WHY THE REVERSAL: the
sealed judge takes ~8.3k cells in against ~5.3k out a day, so the backlog grows ~3k/day and the
stage-1 rank decides which cells are EVER judged, not just when; a rank read off ~48% of the
walk-forward test region would then select on the region that is supposed to be held out. A
runtime check (`wf_cut_check`) proves on every run that the bound stage 1 uses is the gauntlet's
actual walk-forward cut; on a mismatch it is loud (event STAGE1_WINDOW_MISMATCH and the artifact's
`window_check`) and the run falls back to pre_wf. The 1x daily-series
VALUES outside the chosen window are never touched and the lockbox is never read in either mode;
the 3x stress arm is replayed on the signal prefix alone. The trial charge (`trial_charge`) and
the set of cells the sealed judge eventually judges are identical under both windows; the ordering
bias is flagged -- and fails `throughput_fence` -- once a stage-1-ranked cell has waited 24h for a
SEALED judgement (`ordering_bias_warning`).
(The in-sample gates -- DSR, CPCV, PBO -- span the series by construction; that overlap is inherent
to any pre-screen and is why stage 1 carries zero promotion authority.)

VECTORISED WHERE THE GRAMMAR ALLOWS. A `mass_screen_*` cell is re-evaluated with
`research.mass_screen.Prepared` (numpy, one symbol prepared once per batch) when its hold, side
and stop sit on the grammar's axes -- the arithmetic `mass_screen` already proves equal to the
engine's. Every other family runs one `engine.run_backtest` pass through `daily_series`.

THE VERDICTS (every cell gets one, logged in `data/stage1/stage1_record.sqlite`):

  PASS_TO_STAGE2  basis BH_SURVIVOR               -- Benjamini-Hochberg at FDR_Q over EVERY cell
                                                     evaluated in the run (m counts the untestable
                                                     ones too), mean > 0, and mean > 0 at the
                                                     gauntlet's 3x spread stress.
                  basis UNSCREENABLE_TRAIN_WINDOW -- >= 60 days in all, but fewer than
                                                     MIN_TRAIN_DAYS before the boundary: stage 1
                                                     cannot test it, so it is forwarded, never
                                                     rejected without evidence.
  REJECT_STAGE1   R_NO_SIGNALS, R_UNDER_60_DAYS (the sealed matrix drops it: UNKNOWN),
                  R_BH_NOT_SIGNIFICANT, R_COST_STRESS_X3, R_GATE1_ECONOMIC_PRIOR (the sealed gate
                  1, restated by calling it).
  UNBUILDABLE     cause from the sealed builder's own `LAST_BUILD_FAILURE` or preflight
                  (MODIFIER_REFUSED, PARAM_SIGNATURE_MISMATCH, NO_CHART_BARS, FACTOR_BASKET_
                  INCOMPLETE, UNTRADEABLE_SYMBOL, BANNED_FAMILY, ...), counted by family x cause;
                  NEVER_FIRES_IN_SESSION for a session variant with zero signals over its whole
                  history (or refused by `libs.research.family_firing` once that oracle lands).

A REJECT IS NEVER A DELETION. The cell stays on the docket and in the record; it is re-screened
when its chart grows by RESCREEN_GROWTH, its first bar moves, or its family's code changes
(`family_version`); an UNBUILDABLE cell is retried after UNBUILDABLE_RETRY_H as well.

EVERY SCREENED CELL IS A CHARGED TRIAL. Per-run, per-family counts go to `data/STAGE1_TRIALS.jsonl`,
which `libs.research.experiment_ledger` adds to EXPERIMENT_LEDGER.json exactly as it adds
MASS_SCREEN_TRIALS.jsonl.

THE ORDER. Never stage-1-ruled cells first, oldest `first_seen` first; then cells due a re-screen.
Survivors are published as `data/hypotheses/priority_stage1.json` (the priority-file pattern of
`priority_remint.json` / `priority_rejudge.json`) and read, through `research.stage1_record`, by
`scripts/warm_gauntlet_cache.py` -- which warms v4 re-mint and evicted re-judges first, stage-1
survivors next, rejects last -- and by the sealed sort key once the desktop patch lands.

STREAMED AND BOUNDED. The docket is read with the sealed `iter_json_array` in one pass, the
judge's seen-cells record with a regex over 4 MB chunks into 8-byte hashes, and only the oldest
`cap` candidates are ever held. No schtasks, no graph read.

Clock: hourly leg `stage1_judge` (research/hourly_cycle.py), `--once --budget-s 600`, workers
from psutil-measured idle cores and free memory. Artifact: `reports/JUDGING_TWO_STAGE.json`
(embedded in JUDGING_THROUGHPUT.json as `two_stage`). Fence: `throughput_fence()`.

    python desks/mt5/research/stage1_judge.py --once --budget-s 600
    python desks/mt5/research/stage1_judge.py --once --dry-run --budget-s 120 --out-dir X
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import inspect
import json
import math
import os
import re
import sys
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import stage1_record as REC  # noqa: E402

DATA = DESK / "data"
HYP = DATA / "hypotheses"
DOCKET = HYP / "external_survivors.json"
SEEN_CELLS = HYP / "gauntlet_seen_cells.json"
REPORT = DESK / "reports" / "JUDGING_TWO_STAGE.json"
BURNDOWN = DESK / "reports" / "JUDGING_BURNDOWN.json"
TRIALS = DATA / "STAGE1_TRIALS.jsonl"
#: THE CHARGE (2026-10-06, ported into the judge lane): one row per distinct cell this screen
#: evaluated, in the SHARED screened ledger `experiment_ledger.lifetime()` reads (stage
#: `stage1`). Each cell is charged ONCE into the union however often it is re-screened, and a cell
#: the sealed gauntlet later RULES is counted by the hypothesis graph instead -- never twice.
#: STAGE1_TRIALS.jsonl stays as the per-run, per-family REPORT; it is no longer a charge source.
SCREENED = DATA / "SCREENED_TRIALS.jsonl"


def _prior_rulings(con: Any, cids: list[str]) -> dict[str, dict[str, Any]]:
    """{cid: {verdict, reason}} for cids the record already holds, BEFORE this run writes. Read
    here (not through `stage1_record.states`, which does not carry `reason`) so the charge rule is
    exactly `_charged`. An unreadable record returns {}: every cell is then charged, the safe
    direction (the lifetime count de-duplicates by cell)."""
    out: dict[str, dict[str, Any]] = {}
    if con is None:
        return out
    ids = [c for c in dict.fromkeys(cids) if c]
    try:
        for i in range(0, len(ids), 900):
            part = ids[i:i + 900]
            q = ("SELECT cid, verdict, reason FROM cells WHERE cid IN "  # noqa: S608
                 f"({','.join('?' * len(part))})")
            for cid, verdict, reason in con.execute(q, part):
                out[cid] = {"verdict": verdict, "reason": reason}
    except Exception:
        return {}
    return out


def _charged(r: dict[str, Any]) -> bool:
    """A ruling that TESTED the cell (the same rule `cells_screened` counts)."""
    return (r.get("verdict") in (REC.PASS, REC.REJECT)
            and r.get("reason") != "R_GATE1_ECONOMIC_PRIOR")


def charge_screened(path: Path, rows: list[tuple[str, str]], prior: dict[str, dict[str, Any]],
                    ts: str, run_id: str) -> int:
    """Append one ledger row per cell (cid, family) not already charged by an earlier ruling.
    `prior` is the record's state BEFORE this run's write. Returns the rows appended."""
    out = []
    for cid, fam in rows:
        before = prior.get(cid)
        if before and _charged(before):
            continue
        out.append(json.dumps({"at": ts, "cell": cid, "family": fam, "run_id": run_id,
                               "stage": "stage1"}, sort_keys=True))
    if out:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")
    return len(out)
RUNS = DATA / "stage1" / "stage1_runs.jsonl"
PRIORITY = HYP / "priority_stage1.json"
#: judge_coverage's build-failure bank, keyed in the JUDGE's cell-id space.
UNRUNNABLE_BANK = HYP / "unrunnable_specs.json"
#: The session-variant fix's sidecar (`research/session_variant_remap.py`, branch
#: claude/session-variant-fix): one row per docket session variant the family-firing oracle found
#: dead, with `cause` NEVER_FIRES_IN_SESSION or SESSION_TZ_MISMATCH. Stage 1 rules every listed
#: cell at preflight with that cause and spends no build on it. Absent: nothing changes.
DEAD_SIDECAR = HYP / "DEAD_SESSION_VARIANTS.jsonl"
SESSION_TZ_MISMATCH = "SESSION_TZ_MISMATCH"
UNMEASURED = "UNMEASURED"
#: THE SCREEN'S WINDOW. "pre_wf" (DEFAULT, coordinator's ruling PR143_v3, 2026-09-30): days
#: before BOTH the walk-forward-test and the lockbox lower bounds (~16% of a typical cell's days;
#: a planted t=4 edge ranks in the top decile ~62% of the time, `planted_edge_control`). The
#: walk-forward test region stays out-of-sample, which matters because the backlog GROWS (~8.3k
#: in, ~5.3k sealed out a day): the rank decides which cells are ever judged.
#: "pre_lockbox" (opt-in, STAGE1_WINDOW=pre_lockbox): everything before the lockbox lower bound
#: (~48%; t=4 top decile ~93%), walk-forward region included, for ORDER only. In both modes the
#: lockbox is never read, stage 1 never drops or parks a cell, and the trial charge is the full
#: union of screened cells (`trial_charge`; the sealed DSR charges it through
#: patches/union_lifetime_trials/, restated as `stage1_record.dsr_charge`), pinned by a test.
#: `ordering_bias_warning` flags a ranked cell that has waited >= 24h for the sealed judge.
#: An unknown value falls back to pre_wf.
WINDOWS = ("pre_wf", "pre_lockbox")
DEFAULT_WINDOW = "pre_wf"
WINDOW = os.environ.get("STAGE1_WINDOW", DEFAULT_WINDOW)
if WINDOW not in WINDOWS:
    WINDOW = DEFAULT_WINDOW
#: Hours a stage-1-ranked cell may wait for a SEALED judgement before the ordering bias is flagged.
ORDERING_BIAS_HOURS = 24.0
#: Sealed-judged cells the rollover trigger collects per run while a change is active.
RR_POPULATION_CAP = 200_000
#: How many head-of-order cells the published priority file lists (the record holds all).
PRIORITY_TOP = 5000
#: THE WRONG-SPACE BUCKET (2026-09-30). `judge_coverage._cell_id` names a docket row with the chart
#: as a separate `timeframe` key; the judge folds a non-H1 row chart into `params` first
#: (`frontier_identity.docket_cell`). Its build-failure bank is keyed in the judge's space, so the
#: coverage filter matches none of it (measured on the box 2026-09-24/25: 78,771 docket rows whose
#: judge key is banked, 0 matched by coverage's key). The hunk that fixes it (`docket_cell_id` in
#: judge_coverage) was stripped from PR #104 and waits for sealed pass 2. Until then those rows
#: inflate the backlog and the UNKNOWN share. Stage 1 COUNTS them in their own bucket, does NOT
#: screen them as real cells and does NOT drop them; they clear when pass 2 lands.
WRONG_SPACE = "WRONG_SPACE"
#: Bumped when stage 1's own evaluator changes, so every cell is re-screened under the new one.
STAGE1_VERSION = 1

#: Within-run false-discovery rate (Benjamini-Hochberg over every evaluated cell).
FDR_Q = 0.05
#: The sealed matrix drops a cell with fewer active days (CPCV/walk-forward floor) -> UNKNOWN.
MIN_DAYS_FULL = 60
#: Fewer training days than this and a t-test says nothing; the gauntlet's own WF minimum test.
MIN_TRAIN_DAYS = 20
#: Lockbox lower bound: the union calendar is at least 5-of-7 dense after any date, so the held-out
#: share of it cannot start earlier than LOCKBOX_FRAC x 7/5 of the span before today. (Measured
#: 2026-09-30 in the container: a further 25% margin on top pushed the bound to 2021-01-22 and
#: made 161 of 417 built cells unscreenable -- a bound that tight forwards more cells unscreened
#: to the full judge, which is the waste stage 1 exists to remove; the density bound is already
#: strict.)
LOCKBOX_DENSITY_MARGIN = 7.0 / 5.0
#: Re-screen a ruled cell once its chart holds this much more history.
RESCREEN_GROWTH = 1.10
UNBUILDABLE_RETRY_H = 24.0
#: THE PRINCIPAL'S TARGET (2026-09-30): >= 100k first rulings a day on day one, ramping to 500k.
TARGET_DAY_ONE = 100_000
TARGET_FULL = 500_000
RAMP_DAYS = 14
#: The projection basis the task names: the box's cores at half duty.
DUTY = 0.5
#: A worker's declared memory need until one has been measured (the gauntlet's DECLARED_NEED_MB).
DECLARED_WORKER_MB = 1200
BATCH_CELLS = 24
#: Survivors whose full sealed build (both cost arms over full history) is timed per run.
STAGE2_COST_SAMPLE = 8


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(t: datetime | None = None) -> str:
    return (t or _now()).isoformat(timespec="seconds")


def h64(s: str) -> int:
    return int.from_bytes(hashlib.blake2b(s.encode("utf-8"), digest_size=8).digest(), "big")


# --------------------------------------------------------------------------------------------
# the boundary: strictly before the sealed walk-forward test region and the lockbox
# --------------------------------------------------------------------------------------------
def wf_start_lb(n_lo: int, n_hi: int) -> int:
    """Smallest walk-forward TEST start rank over every development length in [n_lo, n_hi].

    The sealed gauntlet cuts its WF test region from the DEVELOPMENT series (after the lockbox
    carve), whose length is unknown here; `mass_screen.wf_start_rank` is not monotone in N (it
    steps back by 3 whenever N crosses a multiple of 6), so the bound is taken over the range."""
    from mass_screen import wf_start_rank
    n_lo = max(0, int(n_lo))
    n_hi = max(n_lo, int(n_hi))
    return int(min(wf_start_rank(k) for k in range(n_lo, n_hi + 1))) if n_hi > 0 else 0


def lockbox_frac_in_force() -> float:
    """The lockbox share the SEALED judge applies this sweep: `gate_policy.LOCKBOX_FRAC`, or the
    Tier S constitution's in-force value when that is larger (the sealed
    `constitution_thresholds` may only TIGHTEN it without a ratification). Read from the same
    unsealed kernel the judge calls, never from the sealed file; the larger of the two always
    wins, so the training window can only move EARLIER, never into the held-out share."""
    from research.gate_policy import LOCKBOX_FRAC
    frac = float(LOCKBOX_FRAC)
    try:
        from libs.tiers.truth_kernel import gauntlet_thresholds
        law = gauntlet_thresholds(DESK, dsr_threshold=0.0, gates_required=0.0,
                                  lockbox_min_fraction=frac)
        frac = max(frac, float(law.get("lockbox_min_fraction") or frac))
    except Exception:
        pass
    return frac


def lockbox_cut_lb(earliest: date, today: date, frac: float | None = None) -> date:
    """A date no later than the sealed lockbox cut of ANY sweep whose union calendar starts on or
    after `earliest` (see the module docstring for the density argument)."""
    if frac is None:
        frac = lockbox_frac_in_force()
    span = (today - earliest).days
    back = math.ceil(float(frac) * LOCKBOX_DENSITY_MARGIN * max(span, 0))
    return today - timedelta(days=back)


def train_boundary(days: np.ndarray, first_bar: date, last_bar: date, cut_lb: date,
                   train_frac: float | None = None, window: str | None = None
                   ) -> tuple[date, dict[str, Any]]:
    """The exclusive end of the training window for one cell, and how it was derived.

    `days` are the cell's active days (sorted, unique, numpy datetime64[D]) over its full replay.
    """
    # No calendar cap by default (the full training window); a fraction is honoured only when
    # a caller passes one explicitly (the boundary property tests do).
    cal = (first_bar + timedelta(days=int(train_frac * (last_bar - first_bar).days))
           if train_frac is not None and train_frac < 1.0 else last_bar + timedelta(days=1))
    n = int(days.size)
    n_lo = int(np.searchsorted(days, np.datetime64(cut_lb, "D")))
    r = wf_start_lb(n_lo, n)
    wf_day = (days[r].astype("datetime64[D]").astype(date) if 0 <= r < n
              else last_bar + timedelta(days=1))
    if (window or WINDOW) == "pre_lockbox":
        # OPT-IN: the development series up to the lockbox lower bound, walk-forward region
        # included (for ORDER only). The lockbox is never read in either mode.
        end = min(cal, cut_lb)
        return end, {"calendar": cal.isoformat(), "wf_lb": wf_day.isoformat(),
                     "lockbox_lb": cut_lb.isoformat(), "wf_rank_lb": r,
                     "binding": "calendar" if end == cal else "lockbox", "window": "pre_lockbox"}
    end = min(cal, wf_day, cut_lb)
    return end, {"calendar": cal.isoformat(), "wf_lb": wf_day.isoformat(),
                 "lockbox_lb": cut_lb.isoformat(), "wf_rank_lb": r, "binding": (
                     "calendar" if end == cal else "walk_forward" if end == wf_day
                     else "lockbox"), "window": "pre_wf"}


#: Development lengths the runtime walk-forward check replays (every length up to 3,000 days,
#: then a sparse tail): a mismatch anywhere a real cell can sit is caught.
WF_CHECK_LENGTHS = (*range(1, 3001), 4000, 5000, 7500, 10000)


def wf_cut_check(G: Any = None, lengths: Any = WF_CHECK_LENGTHS) -> dict[str, Any]:
    """PROVE, AT RUNTIME, THAT STAGE 1'S WALK-FORWARD BOUND IS THE GAUNTLET'S ACTUAL CUT.

    The pre_wf window stops at `mass_screen.wf_start_rank`, a restatement of the sealed walk-
    forward call (`WalkForwardEngine().evaluate(arr, n_splits=WF_SPLITS, test_size=max(20,
    len(arr) // 6))`). This replays the SAME splitter the sealed engine calls
    (`libs.validation.walk_forward.walk_forward_splits`) with the sealed module's own WF_SPLITS
    over every length in `lengths`, and checks the sealed source still carries the test-size
    expression the mirror restates. MATCH only when every length agrees; any disagreement,
    unreadable source or import failure is MISMATCH / UNMEASURED -- never a pass by absence."""
    out: dict[str, Any] = {"status": UNMEASURED, "checked_lengths": 0, "mismatches": []}
    try:
        import mass_screen as MS

        from libs.validation.walk_forward import walk_forward_splits
        if G is None:
            import external_gauntlet as G  # type: ignore[no-redef]
        splits = int(G.WF_SPLITS)
        # The WHOLE sealed module: the walk-forward call has moved between functions as the
        # judge was restructured (run_gauntlet -> _cell_local_stages -> _pure_local_stages under
        # the streaming patch); the expression and the split count are what bind, not their host.
        src = inspect.getsource(sys.modules[G.run_gauntlet.__module__])
    except Exception as exc:
        out["why"] = f"{type(exc).__name__}: {exc}"
        return out
    expr = f"test_size=max({MS.WF_MIN_TEST}, len(arr) // {MS.WF_TEST_DIV})"
    out.update(sealed_wf_splits=splits, mirror_wf_splits=MS.WF_SPLITS, sealed_expr=expr,
               sealed_expr_present=expr in src and "n_splits=WF_SPLITS" in src)
    bad: list[dict[str, int]] = []
    n = 0
    for k in lengths:
        n += 1
        try:
            sp = walk_forward_splits(int(k), n_splits=splits,
                                     test_size=max(MS.WF_MIN_TEST, int(k) // MS.WF_TEST_DIV),
                                     anchored=True, embargo=0)
            actual = min(int(s.test[0]) for s in sp)
        except Exception:
            actual = 0      # too short: the sealed WF runs no test region (TOO_SHORT)
        mine = int(MS.wf_start_rank(int(k)))
        if mine != actual:
            bad.append({"n_days": int(k), "sealed_first_test_rank": actual,
                        "stage1_first_test_rank": mine})
    out["checked_lengths"] = n
    out["mismatches"] = bad[:20]
    out["n_mismatches"] = len(bad)
    ok = (not bad and splits == MS.WF_SPLITS and out["sealed_expr_present"])
    out["status"] = "MATCH" if ok else "MISMATCH"
    out["why"] = ("stage 1's walk-forward bound equals the sealed cut at every checked length"
                  if ok else
                  f"{len(bad)} length(s) disagree; sealed WF_SPLITS {splits} vs mirror "
                  f"{MS.WF_SPLITS}; sealed test-size expression present: "
                  f"{out['sealed_expr_present']}")
    return out


def resolve_window(requested: str, check: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """The window this run uses: the requested one when the walk-forward check is MATCH; pre_wf
    (FAIL CLOSED) otherwise, with the reason recorded."""
    rec = {"requested": requested, "wf_cut_check": check.get("status"),
           "why": check.get("why")}
    if check.get("status") == "MATCH":
        rec["used"] = requested
        rec["fell_back"] = False
        return requested, rec
    rec["used"] = DEFAULT_WINDOW
    rec["fell_back"] = requested != DEFAULT_WINDOW
    rec["rule"] = ("the walk-forward bound is not proven equal to the sealed cut: fail closed to "
                   "pre_wf (the tighter window) and say so")
    return DEFAULT_WINDOW, rec


def universe_earliest(uni: Path) -> date | None:
    """Earliest bar across every parquet in the universe store, from parquet statistics only."""
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return None
    best: datetime | None = None
    for p in uni.glob("*.parquet"):
        try:
            md = pq.ParquetFile(p).metadata
            rg = md.row_group(0)
            for i in range(rg.num_columns):
                col = rg.column(i)
                if col.path_in_schema in ("time", "__index_level_0__") and col.statistics \
                        and col.statistics.has_min_max:
                    v = col.statistics.min
                    if isinstance(v, datetime):
                        v = v if v.tzinfo else v.replace(tzinfo=UTC)
                        best = v if best is None or v < best else best
        except Exception:
            continue
    return best.date() if best else None


def chart_stamp(uni: Path, sym: str, tf: str, memo: dict) -> tuple[int, str]:
    """(bars, first bar ISO) of one chart from parquet metadata; (0, '') when unreadable."""
    key = (sym, tf)
    if key in memo:
        return memo[key]
    out = (0, "")
    try:
        import pyarrow.parquet as pq
        md = pq.ParquetFile(uni / f"{sym}_{tf}.parquet").metadata
        first = ""
        rg = md.row_group(0)
        for i in range(rg.num_columns):
            col = rg.column(i)
            if col.path_in_schema == "time" and col.statistics and col.statistics.has_min_max:
                first = str(col.statistics.min)[:19]
        out = (int(md.num_rows), first)
    except Exception:
        pass
    memo[key] = out
    return out


_FAM_VER: dict[str, str] = {}


def family_version(family: str) -> str:
    """Digest of the family's own source (plus STAGE1_VERSION): a code change re-screens."""
    if family in _FAM_VER:
        return _FAM_VER[family]
    src = ""
    try:
        from mt5desk import families
        fn = getattr(families, f"family_{family}", None)
        if fn is None:
            from mt5desk import families_orthogonal as fo
            fn = fo.ORTHOGONAL_FAMILIES.get(family)
        if fn is not None:
            src = inspect.getsource(fn)
    except Exception:
        src = ""
    v = hashlib.sha1(f"{STAGE1_VERSION}|{src}".encode()).hexdigest()[:12] if src else \
        f"v{STAGE1_VERSION}:nosrc"
    _FAM_VER[family] = v
    return v


# --------------------------------------------------------------------------------------------
# UNBUILDABLE causes, from the sealed builder's own words
# --------------------------------------------------------------------------------------------
_CAUSES = (
    (re.compile(r"^NOT_RUN_MODIFIER"), "MODIFIER_REFUSED"),
    (re.compile(r"unsupported family parameter|unexpected keyword argument"),
     "PARAM_SIGNATURE_MISMATCH"),
    (re.compile(r"factor basket incomplete"), "FACTOR_BASKET_INCOMPLETE"),
    (re.compile(r"driver", re.IGNORECASE), "MISSING_DRIVER"),
    (re.compile(r"^no [A-Z0-9]+ bars for|has no .*\.parquet|chart this cell was hunted on"),
     "NO_CHART_BARS"),
    (re.compile(r"no implementation of family"), "NO_FAMILY_IMPLEMENTATION"),
    (re.compile(r"input load failed"), "INPUT_LOAD_FAILED"),
    (re.compile(r"absent from the universe registry"), "SYMBOL_NOT_IN_REGISTRY"),
    (re.compile(r"CLOSE_ONLY"), "CLOSE_ONLY_SYMBOL"),
    (re.compile(r" raised "), "FAMILY_RAISED"),
)


#: The sealed judge's UNKNOWN / NOT_RUN share (43% of a week's verdicts on the box), taken apart
#: by what stage 1 found: every fine cause maps to one class, so the share is measured before the
#: build-side fixes land and after.
UNKNOWN_CLASS = {
    "NEVER_FIRES_IN_SESSION": "NEVER_FIRES_IN_SESSION", "MISSING_DRIVER": "MISSING_DRIVER",
    "SESSION_CLOCK_MISMATCH": "SESSION_CLOCK_MISMATCH",
    "SESSION_TZ_MISMATCH": "SESSION_CLOCK_MISMATCH",
    "NO_CHART_BARS": "DATA_MISSING", "FACTOR_BASKET_INCOMPLETE": "DATA_MISSING",
    "INPUT_LOAD_FAILED": "DATA_MISSING", "UNTRADEABLE_SYMBOL": "DATA_MISSING",
    "SYMBOL_NOT_IN_REGISTRY": "DATA_MISSING",
    "MODIFIER_REFUSED": "BUILD_FAILED", "PARAM_SIGNATURE_MISMATCH": "BUILD_FAILED",
    "FAMILY_RAISED": "BUILD_FAILED", "NO_FAMILY_IMPLEMENTATION": "BUILD_FAILED",
    "BUILD_FAILED_UNNAMED": "BUILD_FAILED", "BUILD_FAILED_OTHER": "BUILD_FAILED",
    "EVALUATOR_ERROR": "BUILD_FAILED",
    "CLOSE_ONLY_SYMBOL": "NOT_JUDGEABLE", "BANNED_FAMILY": "NOT_JUDGEABLE",
    "R_UNDER_60_DAYS": "TOO_FEW_DAYS", "R_NO_SIGNALS": "NO_SIGNALS",
}


def unknown_class(row: dict[str, Any]) -> str | None:
    """The UNKNOWN class a ruled cell would have cost the sealed judge, or None (a real test)."""
    if row.get("verdict") == REC.UNBUILDABLE:
        return UNKNOWN_CLASS.get(str(row.get("cause")), "BUILD_FAILED")
    if row.get("verdict") == REC.REJECT:
        return UNKNOWN_CLASS.get(str(row.get("reason")))
    return None


def unbuildable_cause(why: str | None) -> str:
    w = str(why or "")
    for pat, name in _CAUSES:
        if pat.search(w):
            return name
    return "BUILD_FAILED_UNNAMED" if not w else "BUILD_FAILED_OTHER"


# --------------------------------------------------------------------------------------------
# the worker
# --------------------------------------------------------------------------------------------
_W: dict[str, Any] = {}


def _init_worker(cut_lb_iso: str, train_frac: float | None = None,
                 window: str | None = None) -> None:
    import external_gauntlet as G
    try:
        meta = json.loads((G.UNI / "universe.json").read_text("utf-8"))
    except (OSError, ValueError):
        meta = {}
    _W.update(G=G, meta=meta if isinstance(meta, dict) else {},
              cut_lb=date.fromisoformat(cut_lb_iso),
              train_frac=None if train_frac is None else float(train_frac),
              window=window or WINDOW, prepared={})
    with contextlib.suppress(Exception):
        import psutil
        p = psutil.Process()
        if hasattr(psutil, "BELOW_NORMAL_PRIORITY_CLASS"):
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            p.nice(10)


def _dates(idx) -> np.ndarray:
    import pandas as pd
    return np.asarray(pd.DatetimeIndex(pd.to_datetime(list(idx))).tz_localize(None)
                      .normalize().values.astype("datetime64[D]"))


def _stats(v: np.ndarray) -> tuple[float, float, float]:
    """(mean, t, one-sided p) of a daily series."""
    from scipy.stats import t as student_t
    d = int(v.size)
    mean = float(v.mean())
    sd = float(v.std(ddof=1)) if d > 1 else 0.0
    t = mean / sd * math.sqrt(d) if sd > 0 else 0.0
    p = float(student_t.sf(t, df=d - 1)) if d > 1 else 1.0
    return mean, t, p


def planted_edge_control(values: np.ndarray, days: np.ndarray, end: date, t_full: float, *,
                         m: int, reps: int = 400, seed: int = 0, q: float = FDR_Q
                         ) -> dict[str, Any]:
    """THE END-TO-END CONTROL (audit 2026-09-30): plant an edge of full-history t = `t_full` into
    a REAL cell's daily R series and ask what stage 1 does with it.

    The real series is demeaned and each replicate flips the sign of every day at random (the
    real calendar, variance and tails stay; any real edge is removed), then the drift that makes
    the full-history t equal `t_full` is added. Stage 1 sees ONLY the training window (days before
    `end`, the same boundary it uses in the run). Returned:

      * top_decile_rate -- how often the planted cell's training t beats the 90th percentile of
        null replicates of the same cell: what the stage-2 ORDER does with it;
      * bh_pass_rate    -- how often it survives BH at q among `m` tested cells (m-1 nulls);
      * predicted_bh_pass_rate -- the documented rate, Phi(t_full x sqrt(f) - z_{q/m}), where f is
        the training share of the cell's days: the screen's power is set by f and m, not by t.
    """
    from mass_screen import bh_threshold
    from scipy.stats import norm
    v = np.asarray(values, dtype="float64")
    d = np.asarray(days).astype("datetime64[D]")
    n = int(v.size)
    r0 = v - v.mean()
    sd = float(r0.std(ddof=1))
    mask = d < np.datetime64(end, "D")
    f = float(mask.mean()) if n else 0.0
    if n < 3 or sd <= 0 or mask.sum() < 3:
        return {"status": UNMEASURED, "why": "series too short for the control"}
    mu = float(t_full) * sd / math.sqrt(n)
    rng = np.random.default_rng(seed)
    rt = r0[mask]
    k = rt.size

    def _t(x: np.ndarray) -> np.ndarray:
        mean = x.mean(axis=-1)
        s = x.std(axis=-1, ddof=1)
        return np.where(s > 0, mean / s * math.sqrt(k), 0.0)

    null_t = _t(rng.choice((-1.0, 1.0), size=(max(reps, 1000), k)) * rt)
    thr = float(np.quantile(null_t, 0.9))
    planted = rng.choice((-1.0, 1.0), size=(reps, k)) * rt + mu
    pt = _t(planted)
    from scipy.stats import t as student_t
    pp = student_t.sf(pt, df=k - 1)
    passed = 0
    for i in range(reps):
        n_listed = int(rng.binomial(max(m - 1, 0), q))
        listed = np.r_[rng.uniform(0.0, q, n_listed), pp[i]]
        cut = bh_threshold(listed[listed <= q], max(m, 1), q)
        passed += int(cut > 0 and pp[i] <= cut and planted[i].mean() > 0)
    z = float(norm.isf(q / max(m, 1)))
    return {"t_full": float(t_full), "n_days_full": n, "n_days_train": int(k),
            "train_fraction": round(f, 4), "expected_t_train": round(t_full * math.sqrt(f), 3),
            "top_decile_rate": round(float((pt > thr).mean()), 4),
            "bh_pass_rate": round(passed / reps, 4),
            "predicted_bh_pass_rate": round(float(norm.cdf(t_full * math.sqrt(f) - z)), 4),
            "m_tested": int(m), "q": q, "reps": int(reps)}


def evaluate_engine(spec: dict[str, Any]) -> dict[str, Any]:
    """One cell through the sealed builder: one 1x replay over full history (for its calendar
    only), statistics on the training window, the 3x arm replayed on the signal prefix."""
    import pandas as pd
    G, meta = _W["G"], _W["meta"]
    sym, fam, params, tf = spec["sym"], spec["family"], spec["params"], spec["tf"]
    frame = G._bars_for(sym, tf)
    if frame is None or len(frame) == 0:
        return {"verdict": REC.UNBUILDABLE, "cause": "NO_CHART_BARS",
                "reason": f"no {tf} bars for {sym}"}
    obj = G.build_cell(sym, fam, params, meta)
    if not obj:
        why = G.LAST_BUILD_FAILURE
        return {"verdict": REC.UNBUILDABLE, "cause": unbuildable_cause(why),
                "reason": str(why or "build_cell returned nothing")[:240]}
    try:
        sigs = list(obj.get("sigs") or [])
        if not sigs:
            if fam == "lead_lag" and params.get("driver_symbol"):
                # The sealed build_cell has no lead_lag branch, so the family gets driver=None
                # and returns [] whatever the market did (gauntlet_build_cell_lead_lag.patch
                # fixes it). Not a verdict on the edge: a missing input, named.
                return {"verdict": REC.UNBUILDABLE, "cause": "MISSING_DRIVER",
                        "reason": f"0 signals: driver {params.get('driver_symbol')!r} bars "
                                  "not reached by the build"}
            if session_bound(params):
                # A SESSION VARIANT OF A FAMILY THAT NEVER FIRES IN THAT SESSION (Tier S,
                # 2026-09-30: 21% of the judge's UNKNOWN verdicts). Named, counted, never
                # forwarded; the producers' remap (claude/session-variant-fix) removes the cause.
                # Unless the family DOES fire in that session on the UTC clock and the sealed
                # filter compared UTC session hours with broker-time bars (UTC+2/+3): that is a
                # clock defect (desktop pass 2), not a family that never fires, and is named so.
                cause = session_probe(G, meta, sym, fam, params)
                return {"verdict": REC.UNBUILDABLE, "cause": cause,
                        "reason": (f"0 signals over full history inside session "
                                   f"{params.get('session')!r}" + (
                                       "; the unfiltered family fires there on the UTC clock"
                                       if cause == SESSION_CLOCK_MISMATCH else ""))}
            return {"verdict": REC.REJECT, "reason": "R_NO_SIGNALS", "n_days_full": 0}
        last_day = frame.index[-1].normalize()
        ds1 = G._series_trim_partial(G.daily_series(obj["df"], sigs, obj["costs"]), last_day)
        n_full = 0 if ds1 is None else len(ds1)
        if n_full < MIN_DAYS_FULL:
            return {"verdict": REC.REJECT, "reason": "R_UNDER_60_DAYS", "n_days_full": n_full}
        days = _dates(ds1.index)
        first_bar = frame.index[0].date()
        end, why = train_boundary(days, first_bar, last_day.date(), _W["cut_lb"],
                                  _W["train_frac"], _W.get("window"))
        sel = days < np.datetime64(end, "D")
        vals = ds1.to_numpy(float)[sel]
        out: dict[str, Any] = {"n_days_full": n_full, "n_days_train": int(vals.size),
                               "train_end": end.isoformat(), "boundary": why["binding"],
                               "path": "engine"}
        if vals.size < MIN_TRAIN_DAYS:
            out.update(verdict=REC.PASS, basis="UNSCREENABLE_TRAIN_WINDOW", p=1.0)
            return out
        mean, t, p = _stats(vals)
        end_ts = pd.Timestamp(end, tz="UTC")
        prefix = [s for s in sigs if pd.Timestamp(s.time) < end_ts]
        # A STRESS THAT STRESSES (audit 2026-09-30): a zero-spread symbol's 3x arm charges 3x a
        # measured basis (cost-truth quote + round-turn commission), never 3x zero; no basis ->
        # the stress fails closed. `research/stress_cost_floor` is shared with the sealed patch.
        # THE FILL HOUR (PR143_v3): the 1x arm (`obj["costs"]`) charges the spread of the hour
        # the cell fills in; the stress arm scales THAT measured spread, not the registry's.
        from research.stress_cost_floor import stress_costs_for
        costs3, s_how = stress_costs_for(sym, meta, G.COST_SCENARIO, hour=obj.get("_fill_hour"))
        out["stress_basis"] = s_how.get("basis") or s_how.get("status")
        if costs3 is None:
            out.update(verdict="EVALUATED", p=p, t=t, mean_r=mean, mean_r_x3=None,
                       stress_unmeasured=True)
            return out
        ds3 = G.daily_series(obj["df"], prefix, costs3) if prefix else None
        if ds3 is not None and len(ds3):
            v3 = ds3.to_numpy(float)[_dates(ds3.index) < np.datetime64(end, "D")]
            mean3 = float(v3.mean()) if v3.size else 0.0
        else:
            mean3 = 0.0
        out.update(verdict="EVALUATED", p=p, t=t, mean_r=mean, mean_r_x3=mean3)
        return out
    finally:
        obj["sigs"] = obj["df"] = None


NEVER_FIRES_IN_SESSION = "NEVER_FIRES_IN_SESSION"


SESSION_CLOCK_MISMATCH = "SESSION_CLOCK_MISMATCH"


def session_probe(G: Any, meta: dict, sym: str, fam: str, params: dict[str, Any]) -> str:
    """NEVER_FIRES_IN_SESSION, or SESSION_CLOCK_MISMATCH when the family's UNFILTERED signals do
    land inside the market's own session once their broker stamps are read on the venue clock.

    The conversion is `libs.regime.session_clock` (PR #134): the stamp clock is New York + 7 h,
    DST from US dates, and each session is its market's 08:00-16:00 local time. Never a fixed
    offset and never the box's offset files. Only called for a session cell with zero signals;
    one extra build, never a verdict change. An unknown session reads NEVER_FIRES_IN_SESSION."""
    try:
        from libs.regime.session_clock import in_session
        base = {k: v for k, v in params.items() if k != "session"}
        obj = G.build_cell(sym, fam, base, meta)
        times = [getattr(g, "time", None) for g in list((obj or {}).get("sigs") or [])]
        times = [t for t in times if t is not None]
        if not times:
            return NEVER_FIRES_IN_SESSION
        mask = in_session(pd.DatetimeIndex(times), str(params.get("session")))
        if mask is not None and bool(np.asarray(mask).any()):
            return SESSION_CLOCK_MISMATCH
    except Exception:
        return NEVER_FIRES_IN_SESSION
    return NEVER_FIRES_IN_SESSION


def session_bound(params: dict[str, Any] | None) -> bool:
    """Is the cell a session variant (a `session` identity key other than all)?"""
    ses = (params or {}).get("session")
    return bool(ses) and str(ses).lower() not in ("all", "none", "")


def firing_oracle(family: str, params: dict[str, Any]) -> bool | None:
    """`libs.research.family_firing` (being written on another branch), when it has landed:
    False means the family provably never fires in this cell's session. Any other answer,
    an absent module or an unknown API is None -- the cell is built and measured instead."""
    if not session_bound(params):
        return None
    try:
        from libs.research import family_firing as FF  # type: ignore[attr-defined]
    except ImportError:
        return None
    for name in ("fires_in_session", "fires"):
        fn = getattr(FF, name, None)
        if callable(fn):
            try:
                ans = fn(family, params.get("session"), params)
            except TypeError:
                try:
                    ans = fn(family, params.get("session"))
                except Exception:
                    return None
            except Exception:
                return None
            return ans if isinstance(ans, bool) else None
    return None


def _mass_screen_cond(params: dict[str, Any]) -> tuple[dict[str, Any], int, int, float] | None:
    """(condition, hold, direction, stop) when the cell sits on the grammar's axes, else None."""
    import mass_screen as MS
    from mt5desk import mass_screen_rules as MR
    try:
        hold = int(params["hold"])
        d = int(params["direction"])
        k = float(params["stop_atr"])
    except (KeyError, TypeError, ValueError):
        return None
    if hold not in MS.HORIZONS or (1 if d >= 0 else -1, k) not in MS.VARIANTS or \
            int(params.get("atr_n", 20)) != 20 or str(params.get("timeframe") or "H1") != "H1":
        return None
    cond = {"feat": str(params.get("feat", "")), "op": str(params.get("op", "gt")),
            "thr": float(params.get("thr", 0.0)),
            "cond_feat": str(params.get("cond_feat", "")),
            "cond_lo": float(params.get("cond_lo", -MR.OPEN_BOUND)),
            "cond_hi": float(params.get("cond_hi", MR.OPEN_BOUND)),
            "hour": int(params.get("hour", -1)), "weekday": int(params.get("weekday", -1)),
            "leader": str(params.get("leader", ""))}
    return cond, hold, (1 if d >= 0 else -1), k


def evaluate_vector(spec: dict[str, Any]) -> dict[str, Any] | None:
    """A mass-screen grammar cell on the symbol's prepared numpy arrays; None -> engine path."""
    import mass_screen as MS
    from mt5desk import mass_screen_rules as MR
    got = _mass_screen_cond(spec["params"])
    if got is None:
        return None
    cond, hold, d, k = got
    sym = spec["sym"]
    P = _W["prepared"].get(sym)
    if P is None:
        df = MR.load_bars(sym)
        if df is None or len(df) < 2000:
            return None
        meta = _W["meta"].get(sym) or {}
        leaders = MS._load_leaders([sym]) if cond.get("leader") else {}
        P = MS.Prepared(sym, df, meta, leaders)
        _W["prepared"].clear()           # one symbol resident per worker: bounded memory
        _W["prepared"][sym] = P
    if cond.get("leader") and cond["leader"] not in P.lead:
        return None
    vi = MS.VARIANTS.index((d, k))
    pos = np.flatnonzero(P.mask(cond))
    kept = MR.thin(pos[pos <= P.n - 2 - hold], hold, P.entry_day)
    if kept.size == 0:
        return {"verdict": REC.REJECT, "reason": "R_NO_SIGNALS", "n_days_full": 0,
                "path": "vector"}
    day_num = P.entry_day[kept]
    uniq = np.unique(day_num)
    n_full = int(uniq.size)
    if n_full < MIN_DAYS_FULL:
        return {"verdict": REC.REJECT, "reason": "R_UNDER_60_DAYS", "n_days_full": n_full,
                "path": "vector"}
    days = uniq.astype("datetime64[D]")
    t_last = datetime.fromtimestamp(int(P.t_ns[-1]) / 1e9, tz=UTC).date()
    t_first = datetime.fromtimestamp(int(P.t_ns[0]) / 1e9, tz=UTC).date()
    end, why = train_boundary(days, t_first, t_last, _W["cut_lb"], _W["train_frac"],
                              _W.get("window"))
    end_num = (np.datetime64(end, "D") - np.datetime64("1970-01-01", "D")).astype(int)
    sel = day_num < end_num
    k_tr = kept[sel]
    out: dict[str, Any] = {"n_days_full": n_full, "train_end": end.isoformat(),
                           "boundary": why["binding"], "path": "vector"}
    if k_tr.size == 0:
        out.update(verdict=REC.PASS, basis="UNSCREENABLE_TRAIN_WINDOW", p=1.0, n_days_train=0)
        return out
    dd = P.entry_day[k_tr]
    last = np.flatnonzero(np.r_[dd[1:] != dd[:-1], True])
    s1 = P.R1[hold][vi, k_tr[last]]
    s3 = P.R3[hold][vi, k_tr[last]]
    s1 = np.where(np.isfinite(s1), s1, 0.0)
    s3 = np.where(np.isfinite(s3), s3, 0.0)
    out["n_days_train"] = int(s1.size)
    if s1.size < MIN_TRAIN_DAYS:
        out.update(verdict=REC.PASS, basis="UNSCREENABLE_TRAIN_WINDOW", p=1.0)
        return out
    mean, t, p = _stats(s1)
    out.update(verdict="EVALUATED", p=p, t=t, mean_r=mean, mean_r_x3=float(s3.mean()))
    return out


def _zero_spread(sym: str) -> bool:
    from research.stress_cost_floor import is_zero_spread
    return is_zero_spread((_W.get("meta") or {}).get(sym) or {})


def _evaluate(spec: dict[str, Any]) -> dict[str, Any]:
    """One cell, never raising. `cost_s` is the cell's CPU time in this process -- core-seconds,
    which a busy host cannot inflate the way it inflates wall time -- and `wall_s` its wall."""
    t0 = time.monotonic()
    c0 = time.process_time()
    try:
        res = None
        if str(spec["family"]).startswith("mass_screen_") and not _zero_spread(spec["sym"]):
            # the grammar's prepared 3x arm multiplies a zero spread too; zero-spread symbols
            # take the engine path, whose stress arm has a measured basis
            res = evaluate_vector(spec)
        if res is None:
            res = evaluate_engine(spec)
    except Exception as exc:
        res = {"verdict": REC.UNBUILDABLE, "cause": "EVALUATOR_ERROR",
               "reason": f"{type(exc).__name__}: {str(exc)[:200]}"}
    res["cid"] = spec["cid"]
    res["cost_s"] = round(time.process_time() - c0, 5)
    res["wall_s"] = round(time.monotonic() - t0, 5)
    return res


def evaluate_batch(specs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], float]:
    """One (symbol, chart) batch on one worker: results and the worker's peak RSS in MB."""
    out = [_evaluate(sp) for sp in specs]
    rss = 0.0
    with contextlib.suppress(Exception):
        import psutil
        rss = psutil.Process().memory_info().rss / 2**20
    return out, rss


def stage2_cost(spec: dict[str, Any]) -> float | None:
    """The sealed judge's own per-cell build for this cell: `build_cell` plus BOTH cost arms over
    full history (`external_gauntlet._warm_one`'s arithmetic). CPU seconds, or None."""
    G, meta = _W["G"], _W["meta"]
    c0 = time.process_time()
    try:
        obj = G.build_cell(spec["sym"], spec["family"], spec["params"], meta)
        if not obj:
            return None
        G.daily_series(obj["df"], obj["sigs"], obj["costs"])
        G.daily_series(obj["df"], obj["sigs"],
                       G.costs_for(spec["sym"], meta, mult=G.COST_SCENARIO))
    except Exception:
        return None
    return time.process_time() - c0


# --------------------------------------------------------------------------------------------
# the backlog, streamed
# --------------------------------------------------------------------------------------------
_SEEN_RE = re.compile(r'"((?:[^"\\]|\\.)*)"\s*:\s*"((?:[^"\\]|\\.)*)"')


def stream_seen(path: Path, watch: set[str] | None = None, since: str = ""
                ) -> tuple[set[int], dict[str, str], str]:
    """(hashes of every cell the sealed judge has judged, {watched cid: judged-at}, status).

    `gauntlet_seen_cells.json` is a flat {cell id: ISO time} object; it is read in 4 MB chunks
    with a regex so memory is 8 bytes a cell, never the decoded dict."""
    out: set[int] = set()
    hit: dict[str, str] = {}
    if not path.exists():
        return out, hit, f"{UNMEASURED}: {path.name} absent (every cell reads never-judged)"
    w = watch or set()
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            tail = ""
            while True:
                chunk = fh.read(1 << 22)
                if not chunk:
                    break
                buf = tail + chunk
                cut = buf.rfind(",")
                if cut < 0:
                    tail = buf
                    continue
                head, tail = buf[:cut + 1], buf[cut + 1:]
                for m in _SEEN_RE.finditer(head):
                    out.add(h64(m.group(1)))
                    if m.group(1) in w and m.group(2) >= since:
                        hit[m.group(1)] = m.group(2)
            for m in _SEEN_RE.finditer(tail):
                out.add(h64(m.group(1)))
                if m.group(1) in w and m.group(2) >= since:
                    hit[m.group(1)] = m.group(2)
    except OSError as exc:
        return set(), {}, f"{UNMEASURED}: {type(exc).__name__}: {exc}"
    return out, hit, "MEASURED"


def _due(state: dict[str, Any], bars: tuple[int, str], fam_ver: str, now: datetime) -> bool:
    """Is a stage-1-ruled cell due a re-screen? Never deletes, only re-opens."""
    if str(state.get("family_ver") or "") != fam_ver:
        return True
    n_then = int(state.get("n_bars") or 0)
    if bars[0] and n_then and bars[0] >= n_then * RESCREEN_GROWTH:
        return True
    if bars[1] and state.get("first_bar") and str(state["first_bar"]) != bars[1]:
        return True
    if state.get("verdict") == REC.UNBUILDABLE:
        try:
            at = datetime.fromisoformat(str(state.get("ruled_at")))
            return (now - at).total_seconds() >= UNBUILDABLE_RETRY_H * 3600
        except ValueError:
            return True
    return False


def load_bank_hashes(path: Path | None = None) -> tuple[set[int], str]:
    """8-byte hashes of the build-failure bank's keys (judge space), and a status string. An
    absent or unreadable bank is an EMPTY set with an UNMEASURED status, never a guess."""
    p = Path(path or UNRUNNABLE_BANK)
    try:
        doc = json.loads(p.read_text("utf-8"))
    except FileNotFoundError:
        return set(), f"{UNMEASURED}: {p.name} absent on this host"
    except (OSError, ValueError) as exc:
        return set(), f"{UNMEASURED}: {p.name} unreadable ({type(exc).__name__})"
    if not isinstance(doc, dict):
        return set(), f"{UNMEASURED}: {p.name} is not a map"
    out = {h64(str(k)) for k, v in doc.items() if isinstance(v, dict)}
    return out, f"MEASURED: {len(out)} banked cell(s)"


def _ident_key(symbol: Any, family: Any, params: Any) -> int:
    """The sidecar's fallback identity: symbol / family / params, canonical JSON."""
    raw = json.dumps([symbol, family, params or {}], sort_keys=True, default=str,
                     separators=(",", ":"))
    return h64(raw)


def load_dead_sidecar(path: Path | None = None
                      ) -> tuple[dict[int, str], dict[int, str], str]:
    """({h64(genome_id): cause}, {h64(symbol/family/params): cause}, status), streamed line by
    line. An absent sidecar is two empty maps: nothing changes. A row whose cause is not one of
    the two session causes is read as NEVER_FIRES_IN_SESSION only when its verdict says DEAD."""
    p = Path(path or DEAD_SIDECAR)
    by_gid: dict[int, str] = {}
    by_ident: dict[int, str] = {}
    try:
        fh = p.open(encoding="utf-8")
    except FileNotFoundError:
        return by_gid, by_ident, f"ABSENT: {p.name} not on this host (nothing changes)"
    except OSError as exc:
        return by_gid, by_ident, f"{UNMEASURED}: {p.name} unreadable ({type(exc).__name__})"
    bad = 0
    with fh:
        for ln in fh:
            try:
                r = json.loads(ln)
            except ValueError:
                bad += 1
                continue
            if not isinstance(r, dict):
                continue
            cause = str(r.get("cause") or "")
            if cause not in (NEVER_FIRES_IN_SESSION, SESSION_TZ_MISMATCH):
                if str(r.get("verdict") or "") != "DEAD":
                    continue
                cause = NEVER_FIRES_IN_SESSION
            if r.get("genome_id"):
                by_gid[h64(str(r["genome_id"]))] = cause
            if r.get("symbol") and r.get("family"):
                by_ident[_ident_key(r["symbol"], r["family"], r.get("params"))] = cause
    return by_gid, by_ident, (f"MEASURED: {len(by_gid)} genome id(s), {len(by_ident)} "
                              f"symbol/family/params key(s), {bad} unreadable line(s)")


def dead_cause(h: dict[str, Any], sym: str, by_gid: dict[int, str],
               by_ident: dict[int, str]) -> str | None:
    """The sidecar's cause for a docket row: genome_id first, then symbol/family/params (the raw
    row symbol and the registry's spelling)."""
    if not by_gid and not by_ident:
        return None
    gid = h.get("genome_id")
    if gid and h64(str(gid)) in by_gid:
        return by_gid[h64(str(gid))]
    for s_ in dict.fromkeys((h.get("symbol"), sym)):
        c = by_ident.get(_ident_key(s_, h.get("family"), h.get("params")))
        if c:
            return c
    return None


def coverage_space_id(G: Any, h: dict[str, Any]) -> str | None:
    """The id `judge_coverage._cell_id` gives a docket row TODAY (chart beside params, raw row
    symbol) -- the wrong key space, reproduced only to count the rows it misses."""
    try:
        return str(G.cell_id({"sym": h.get("symbol") or h.get("sym"), "family": h.get("family"),
                              "params": h.get("params") or {},
                              "timeframe": h.get("timeframe")}))
    except Exception:
        return None


def select_backlog(G: Any, meta: dict, con, *, cap: int, now: datetime,
                   docket: Path, seen: set[int], bank: set[int] | None = None,
                   dead: tuple[dict[int, str], dict[int, str]] | None = None,
                   collect_judged: int = 0
                   ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """One streaming pass over the docket. Returns (the `cap` highest-priority cells to rule this
    run, the backlog census). Priority: never stage-1-ruled first, then due re-screens; oldest
    `first_seen` first within each. Memory: `cap` candidates plus 8 bytes per docket cell."""
    census: dict[str, Any] = {"rows": 0, "stamped": 0, "unstamped": 0, "cells": 0,
                              "sealed_judged": 0, "backlog": 0, "oldest_first_seen": None,
                              "tiers": dict.fromkeys(REC.TIER_NAMES.values(), 0),
                              "due_rescreen": 0, "created_24h": 0, "created_7d": 0,
                              "wrong_space": 0, "key_space_mismatch_rows": 0,
                              "dead_session_variants": 0,
                              "ranked_unsealed": 0, "oldest_ranked_unsealed_at": None}
    bank = bank or set()
    dead_gid, dead_ident = dead or ({}, {})
    judged_specs: list[dict[str, Any]] = []
    cut24 = (now - timedelta(hours=24)).isoformat(timespec="seconds")
    cut7d = (now - timedelta(days=7)).isoformat(timespec="seconds")
    from libs.data.pit import is_stamped
    dedup: set[int] = set()
    cands: list[tuple[int, str, int, dict[str, Any]]] = []
    pending: list[tuple[str, dict[str, Any]]] = []
    bars_memo: dict = {}
    priority = REC.priority_cells()
    oldest = [None]
    seq = [0]
    unstamped_ids: set[int] = set()

    def _flush() -> None:
        if not pending:
            return
        known = REC.states(con, [c for c, _ in pending]) if con is not None else {}
        for cid, sp in pending:
            st = known.get(cid)
            if st is not None and REC.tier_of_state(st) == REC.TIER_SCORED:
                # RANKED BY STAGE 1 AND NOT YET SEALED-JUDGED (pending holds backlog cells only):
                # the ordering-bias clock, in the same stream.
                census["ranked_unsealed"] += 1
                ra = str(st.get("ruled_at") or "")
                if ra and (census["oldest_ranked_unsealed_at"] is None
                           or ra < census["oldest_ranked_unsealed_at"]):
                    census["oldest_ranked_unsealed_at"] = ra
            tier = REC.TIER_PRIORITY if cid in priority else REC.tier_of_state(st)
            census["tiers"][REC.TIER_NAMES[tier]] += 1
            dc = sp.get("dead_cause")
            if dc:
                # Listed dead by the session-variant sidecar: ruled at preflight, first, with
                # no build. Already ruled with that cause -> nothing to do until the list drops it.
                if st is not None and st.get("verdict") == REC.UNBUILDABLE and \
                        st.get("cause") == dc:
                    continue
                rank = -1
            elif st is None:
                rank = 0
            else:
                if not _due(st, chart_stamp(G.UNI, sp["sym"], sp["tf"], bars_memo),
                            family_version(sp["family"]), now):
                    continue
                census["due_rescreen"] += 1
                rank = 1
            seq[0] += 1
            cands.append((rank, sp["first_seen"], seq[0], sp))
        pending.clear()
        if len(cands) > 2 * cap:
            cands.sort(key=lambda x: x[:3])
            del cands[cap:]

    for h in G.iter_json_array(docket):
        census["rows"] += 1
        if not isinstance(h, dict):
            continue
        stamped = bool(is_stamped(h))
        census["stamped" if stamped else "unstamped"] += 1
        sym, fam = h.get("symbol"), h.get("family")
        if not sym or not fam:
            continue
        params = dict(h.get("params") or {})
        row_tf = str(h.get("timeframe") or "").upper()
        if row_tf and row_tf != "H1" and "timeframe" not in params:
            params["timeframe"] = row_tf
        sym = G.canonical_symbol(str(sym), meta)
        try:
            cid = G.cell_id({"sym": sym, "family": fam, "params": params})
        except Exception:
            continue
        hh = h64(cid)
        if hh in dedup:
            continue
        dedup.add(hh)
        census["cells"] += 1
        # THE CREATION RATE, from the docket's own clock: distinct cells first seen in the window.
        fs0 = str(h.get("first_seen") or "")
        if fs0 >= cut7d:
            census["created_7d"] += 1
            if fs0 >= cut24:
                census["created_24h"] += 1
        if hh in seen:
            census["sealed_judged"] += 1
            if collect_judged and len(judged_specs) < collect_judged:
                # the rollover re-judge trigger's population (only while a change is active)
                judged_specs.append({"cid": cid, "sym": sym, "family": str(fam),
                                     "params": params,
                                     "tf": G.timeframe_of(params, str(fam))})
            continue
        census["backlog"] += 1
        # WRONG SPACE: banked in the judge's key space, missed by coverage's key. Counted, kept
        # on the docket, not screened as a real cell (see WRONG_SPACE above).
        cov = coverage_space_id(G, h)
        if cov is not None and cov != cid:
            census["key_space_mismatch_rows"] += 1
        if hh in bank and (cov is None or h64(cov) not in bank):
            census["wrong_space"] += 1
            continue
        fs = str(h.get("first_seen") or "")
        if fs and (oldest[0] is None or fs < oldest[0]):
            oldest[0] = fs
        if not stamped:
            unstamped_ids.add(hh)
        dc_row = dead_cause(h, sym, dead_gid, dead_ident)
        if dc_row:
            census["dead_session_variants"] += 1
        pending.append((cid, {"cid": cid, "sym": sym, "family": str(fam), "params": params,
                              "tf": G.timeframe_of(params, str(fam)), "first_seen": fs,
                              "stamped": stamped,
                              "priority": h.get("priority") if isinstance(
                                  h.get("priority"), str) else None,
                              "mechanism_status": h.get("mechanism_status"),
                              "mechanism_note": h.get("mechanism_note"),
                              "dead_cause": dc_row}))
        if len(pending) >= 2000:
            _flush()
    _flush()
    census["oldest_first_seen"] = oldest[0]
    census["judged_specs"] = judged_specs
    # THE POINT-IN-TIME RATCHET, as the sealed docket applies it: once any row is stamped, an
    # unstamped row is not on the judge's docket at all, so it is not stage-1 work either.
    stamped_only = bool(census["stamped"] and census["unstamped"])
    census["stamped_only_ratchet"] = stamped_only
    if stamped_only:
        cands = [c for c in cands if c[3]["stamped"]]
        census["unstamped_backlog_not_on_judges_docket"] = len(unstamped_ids)
    cands.sort(key=lambda x: x[:3])
    return [c[3] for c in cands[:cap]], census


def preflight(G: Any, meta: dict, sp: dict[str, Any]) -> dict[str, Any] | None:
    """The rulings that need no build: ban, tradeability, the sealed gate 1, the sealed modifier
    preflight. Returns a result row, or None when the cell must be built."""
    fam = sp["family"]
    if sp.get("dead_cause"):
        return {"verdict": REC.UNBUILDABLE, "cause": sp["dead_cause"],
                "reason": (f"DEAD_SESSION_VARIANTS.jsonl lists {fam} in session "
                           f"{sp['params'].get('session')!r} as {sp['dead_cause']}; no build")}
    with contextlib.suppress(Exception):
        from research.family_policy import ban_reason, family_banned
        if family_banned(fam):
            return {"verdict": REC.UNBUILDABLE, "cause": "BANNED_FAMILY",
                    "reason": str(ban_reason(fam))[:240]}
    ok, why = G.symbol_is_tradeable(sp["sym"], meta)
    if not ok:
        return {"verdict": REC.UNBUILDABLE, "reason": why[:240], "cause": (
            "SYMBOL_NOT_IN_REGISTRY" if "registry" in why else
            "CLOSE_ONLY_SYMBOL" if "CLOSE_ONLY" in why else "UNTRADEABLE_SYMBOL")}
    if sp["tf"] != "H1" and not (G.UNI / f"{sp['sym']}_{sp['tf']}.parquet").exists() and \
            os.name != "nt":
        return {"verdict": REC.UNBUILDABLE, "cause": "NO_CHART_BARS",
                "reason": f"no {sp['tf']} bars for {sp['sym']}"}
    stage = G.economic_prior(sp)
    if not stage.get("passed"):
        return {"verdict": REC.REJECT, "reason": "R_GATE1_ECONOMIC_PRIOR",
                "detail": str(stage.get("message") or stage.get("why") or "")[:240]}
    if firing_oracle(fam, sp["params"]) is False:
        return {"verdict": REC.UNBUILDABLE, "cause": NEVER_FIRES_IN_SESSION,
                "reason": f"family_firing oracle: {fam} never fires in session "
                          f"{sp['params'].get('session')!r}"}
    why = G.modifier_preflight(sp)
    if why:
        return {"verdict": REC.UNBUILDABLE, "cause": unbuildable_cause(why) if
                "unsupported family parameter" in why else "MODIFIER_REFUSED",
                "reason": str(why)[:240]}
    return None


# --------------------------------------------------------------------------------------------
# run-level statistics
# --------------------------------------------------------------------------------------------
def bh_cut(pvals: list[float], m: int, q: float) -> float:
    """Benjamini-Hochberg p cut over m hypotheses (0.0 when nothing is rejected)."""
    from mass_screen import bh_threshold
    listed = np.array([p for p in pvals if p <= q], dtype="float64")
    return bh_threshold(listed, m, q)


def score_of(r: dict[str, Any]) -> float | None:
    """The stage-2 ORDER score: the training-window t-statistic of a TESTED cell, else None.
    None is stored for an UNSCREENABLE_TRAIN_WINDOW cell too (it was not tested, and the record's
    `score` means "tested"), but `stage1_record.rank_of_state` ranks that basis at the NEUTRAL
    t = 0 -- ahead of every negative-t cell (audit R2). Untested-for-other-reasons and
    unbuildable cells sort after every ranked cell and are never dropped."""
    if r.get("verdict") == REC.UNBUILDABLE or r.get("basis") == "UNSCREENABLE_TRAIN_WINDOW":
        return None
    t = r.get("t")
    try:
        return None if t is None or not math.isfinite(float(t)) else float(t)
    except (TypeError, ValueError):
        return None


def finalise(results: list[dict[str, Any]], q: float = FDR_Q) -> dict[str, Any]:
    """Turn EVALUATED rows into PASS / REJECT under one BH cut over the run.

    m COUNTS ONLY TESTED CELLS (audit 2026-09-30): a cell with no training-window statistic
    (no signals, under 60 days, too few training days) is not a hypothesis tested in this run,
    and counting it in m only raised the bar for the cells that were. Every tested cell is still
    charged as a trial (STAGE1_TRIALS.jsonl)."""
    ps = [float(r["p"]) for r in results if r.get("verdict") == "EVALUATED"]
    m = len(ps)
    cut = bh_cut(ps, m, q)
    for r in results:
        if r.get("verdict") != "EVALUATED":
            continue
        sig = cut > 0 and float(r["p"]) <= cut and float(r.get("mean_r") or 0) > 0
        if not sig:
            r.update(verdict=REC.REJECT, reason="R_BH_NOT_SIGNIFICANT")
        elif r.get("stress_unmeasured"):
            r.update(verdict=REC.REJECT, reason="R_COST_STRESS_UNMEASURED")
        elif float(r.get("mean_r_x3") or 0.0) <= 0.0:
            r.update(verdict=REC.REJECT, reason="R_COST_STRESS_X3")
        else:
            r.update(verdict=REC.PASS, basis="BH_SURVIVOR")
    return {"method": "benjamini_hochberg", "q": q, "m": m, "p_cut": cut,
            "testable": len(ps), "rejected_null": sum(1 for p in ps if cut > 0 and p <= cut)}


def trial_charge(results: list[dict[str, Any]]) -> dict[str, Any]:
    """WHAT THE DESK CHARGES, over the FULL UNION of cells this run screened -- window-invariant.

    Every ruled cell that is not UNBUILDABLE and not refused by the sealed economic prior is a
    charged trial (STAGE1_TRIALS.jsonl `cells_screened`, read by the lifetime experiment ledger),
    whether or not the training window gave it a statistic. Neither the unbuildable cause nor the
    economic prior reads the training window, so this m is identical under every WINDOW; so is
    the set of cells the sealed gauntlet eventually judges, because stage 1 only reorders. The
    BH `m` in `finalise` (tested cells only) labels survivors and is NOT the charge.

    WHERE THE CHARGE LANDS. Every run's per-family `cells_screened` sums to this m; the experiment
    ledger adds them into `stage1_cells` -- the union the sealed deflated Sharpe charges as
    max(campaign, family, union) once /mnt/project-files/patches/union_lifetime_trials/ lands
    (restated unsealed as `stage1_record.dsr_charge`), not max(campaign, family), which
    under-charged by union/family (audit PR143_v3)."""
    charged = [r for r in results if r.get("verdict") in REC.VERDICTS
               and r.get("verdict") != REC.UNBUILDABLE
               and r.get("reason") != "R_GATE1_ECONOMIC_PRIOR"]
    charged_ids = {id(r) for r in charged}
    ranked = [r for r in results if score_of(r) is not None
              or r.get("basis") in REC.NEUTRAL_BASES]
    return {"m_charged": len(charged), "cells_ruled": sum(
                1 for r in results if r.get("verdict") in REC.VERDICTS),
            "cells_ranked": len(ranked),
            "every_ranked_cell_charged": all(id(r) in charged_ids for r in ranked),
            "basis": ("full union of screened cells (ruled, not unbuildable, not refused by the "
                      "sealed economic prior); window-invariant by construction")}


def ordering_bias_warning(oldest_ranked_at: str | None, ranked_unsealed: Any,
                          now: datetime, window: str,
                          hours: float = ORDERING_BIAS_HOURS) -> dict[str, Any]:
    """TRUE when a cell stage 1 RANKED has waited `hours` or more without a SEALED judgement.

    WHAT IT MEASURES AND WHY (audit PR143_v3). The earlier version read stage 1's own RULED
    backlog, which stage 1 drains by construction, so it could never fire. The bias that matters is
    on the SEALED side: the gauntlet takes ~8.3k cells in against ~5.3k out a day, and once a
    ranked cell sits unjudged the rank -- read off the window -- is deciding which cells are ever
    judged. So the input is the oldest stage-1 ranking (group 1: scored, or neutral) among docket
    cells the sealed seen-cells record does not hold, collected in `select_backlog`'s one stream.
    Its time is the cell's LATEST stage-1 ruling (a re-screen resets it), so the age is a LOWER
    bound. No ranked unsealed cell: False. A count or time this run could not read: UNMEASURED,
    never False (L1.28a)."""
    rule = (f"a stage-1-ranked cell unjudged by the sealed gauntlet for >= {hours:g}h: the "
            f"{window} window's rank is deciding which cells are ever judged")
    out: dict[str, Any] = {"window": window, "threshold_hours": hours,
                           "ranked_unsealed": ranked_unsealed,
                           "oldest_ranked_unsealed_at": oldest_ranked_at,
                           "basis": "sealed: stage-1-ranked docket cells absent from the sealed "
                                    "seen-cells record; age from their latest stage-1 ruling",
                           "rule": rule}
    if not isinstance(ranked_unsealed, int) or isinstance(ranked_unsealed, bool):
        out.update(ordering_bias_warning=UNMEASURED, oldest_age_hours=UNMEASURED)
        return out
    if ranked_unsealed == 0:
        out.update(ordering_bias_warning=False, oldest_age_hours=0.0)
        return out
    try:
        since = datetime.fromisoformat(str(oldest_ranked_at))
        since = since if since.tzinfo else since.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        out.update(ordering_bias_warning=UNMEASURED, oldest_age_hours=UNMEASURED)
        return out
    age_h = round(max(0.0, (now - since).total_seconds()) / 3600.0, 2)
    out.update(ordering_bias_warning=age_h >= hours, oldest_age_hours=age_h)
    return out


# --------------------------------------------------------------------------------------------
# workers, the run
# --------------------------------------------------------------------------------------------
def derive_workers(override: int | None, worker_mb: float) -> tuple[int, dict[str, Any]]:
    """Worker count from MEASURED idle cores and free memory on THIS machine."""
    info: dict[str, Any] = {}
    try:
        import psutil
        cores = int(psutil.cpu_count(logical=True) or 1)
        busy_pct = float(psutil.cpu_percent(interval=1.0))
        avail_mb = float(psutil.virtual_memory().available) / 2**20
        busy = round(busy_pct / 100.0 * cores)
        free = max(1, cores - busy - 1)
        mem_cap = max(1, int(avail_mb * 0.5 // max(worker_mb, 1.0)))
        w = max(1, min(free, mem_cap))
        info = {"cores": cores, "busy_pct": busy_pct, "free_cores_less_one": free,
                "available_mb": round(avail_mb), "worker_mb": round(worker_mb),
                "memory_cap_workers": mem_cap, "basis": "psutil, measured this run"}
    except Exception as exc:
        w = 1
        info = {"basis": f"{UNMEASURED}: psutil unavailable ({type(exc).__name__}); one worker"}
    if override:
        w = max(1, int(override))
        info["override"] = w
    info["workers"] = w
    return w, info


def _read_json(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, p)


def _append(p: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, separators=(",", ":"), default=str) + "\n")


def _tail_runs(p: Path, hours: float = 168.0) -> list[dict[str, Any]]:
    """Run rows of the trailing window, streamed (the ledger is one small row per run)."""
    floor = (_now() - timedelta(hours=hours)).isoformat(timespec="seconds")
    out: list[dict[str, Any]] = []
    try:
        with p.open("r", encoding="utf-8") as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(r, dict) and str(r.get("ts") or "") >= floor:
                    out.append(r)
    except OSError:
        return []
    return out


def batches(specs: list[dict[str, Any]], size: int = BATCH_CELLS) -> list[list[dict[str, Any]]]:
    """Group by (symbol, chart) so a worker's frame cache hits; groups keep the order of their
    oldest member, so the budget still reaches the oldest backlog first."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for sp in specs:
        groups.setdefault((sp["sym"], sp["tf"]), []).append(sp)
    out: list[list[dict[str, Any]]] = []
    for rows in groups.values():
        for i in range(0, len(rows), max(1, size)):
            out.append(rows[i:i + size])
    return out


def target_for(first_run: str | None, now: datetime) -> int:
    """The day's stage-1 target: TARGET_DAY_ONE on the first day, linear to TARGET_FULL."""
    try:
        d0 = datetime.fromisoformat(str(first_run)) if first_run else now
    except ValueError:
        d0 = now
    days = max(0.0, (now - d0).total_seconds() / 86400.0)
    return int(min(TARGET_FULL, TARGET_DAY_ONE + (TARGET_FULL - TARGET_DAY_ONE)
                   * days / RAMP_DAYS))


def throughput_fence(doc: dict[str, Any]) -> dict[str, Any]:
    """FAIL when the stage-1 per-day figure projected from the MEASURED rate is under the day's
    target while the backlog is above zero. UNMEASURED when either number is missing -- never a
    pass by absence (L1.28a)."""
    s1 = doc.get("stage1") or {}
    proj = s1.get("projected_per_day_18c_50pct")
    target = s1.get("target_per_day")
    backlog = (doc.get("backlog") or {}).get("cells")
    net = (doc.get("net_backlog_change_per_day") or {}).get("projected_18c_50pct")
    if not isinstance(proj, (int, float)) or not isinstance(target, (int, float)) or \
            not isinstance(backlog, int) or not isinstance(net, (int, float)):
        return {"status": UNMEASURED,
                "why": "projected rate, target, creation rate or backlog unmeasured"}
    if backlog <= 0:
        return {"status": "PASS", "why": "backlog is empty"}
    fails = []
    if proj < target:
        fails.append(f"stage 1 projects {int(proj):,} TESTED/day against a "
                     f"{int(target):,}/day target")
    if net >= 0:
        fails.append(f"the backlog does not shrink: net {int(net):+,}/day")
    # THE ORDERING BIAS IS A FENCE, NOT A NOTE (PR143_v3): a ranked cell unjudged by the sealed
    # gauntlet for 24h means the stage-1 window is choosing what is ever judged.
    ob = doc.get("ordering_bias") if isinstance(doc.get("ordering_bias"), dict) else {}
    if ob.get("ordering_bias_warning") is True:
        fails.append(f"ordering bias: a stage-1-ranked cell has waited "
                     f"{ob.get('oldest_age_hours')}h for the sealed judge "
                     f"({ob.get('ranked_unsealed')} ranked and unjudged, window "
                     f"{ob.get('window')})")
    return {"status": "FAIL" if fails else "PASS", "projected_per_day": int(proj),
            "target_per_day": int(target), "net_backlog_change_per_day": int(net),
            "backlog": backlog, "ordering_bias_warning": ob.get("ordering_bias_warning",
                                                                UNMEASURED),
            "why": ("; ".join(fails) + f" with {backlog:,} cells waiting") if fails else (
                f"stage 1 projects {int(proj):,}/day (target {int(target):,}); the backlog of "
                f"{backlog:,} shrinks {int(-net):,}/day")}


def _loud(kind: str, msg: str, *, quiet: bool, **fields: Any) -> None:
    """Print to stderr always; append the typed event unless this is a dry/out-dir run."""
    print(msg, file=sys.stderr, flush=True)
    if quiet:
        return
    with contextlib.suppress(Exception):
        from libs.ops import events as EV
        EV.emit(kind, producer="stage1_judge", **fields)


def run(*, budget_s: float = 600.0, workers: int | None = None, cap: int | None = None,
        q: float = FDR_Q, dry_run: bool = False, out_dir: Path | None = None,
        docket: Path | None = None, seen_path: Path | None = None,
        db: Path | None = None, bank_path: Path | None = None,
        dead_path: Path | None = None, window: str | None = None) -> dict[str, Any]:
    started = time.monotonic()
    win = window or WINDOW
    if win not in WINDOWS:
        raise ValueError(f"stage-1 window {win!r} is not one of {WINDOWS}")
    now = _now()
    run_id = f"s1_{now.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}"
    report = (out_dir / REPORT.name) if out_dir else REPORT
    trials_p = (out_dir / TRIALS.name) if out_dir else TRIALS
    screened_p = (out_dir / SCREENED.name) if out_dir else SCREENED
    runs_p = (out_dir / RUNS.name) if out_dir else RUNS
    prio_p = (out_dir / PRIORITY.name) if out_dir else PRIORITY
    db_p = db or ((out_dir / REC.DB.name) if out_dir else REC.DB)
    docket = docket or DOCKET
    seen_path = seen_path or SEEN_CELLS
    import external_gauntlet as G
    # THE WINDOW IS PROVEN, NOT ASSUMED (PR143_v3): stage 1's walk-forward bound must equal the
    # sealed cut on this tree, or the run falls back to pre_wf -- loudly.
    wf_check = wf_cut_check(G)
    win, window_rec = resolve_window(win, wf_check)
    window_rec["check"] = wf_check
    if wf_check.get("status") != "MATCH":
        _loud("STAGE1_WINDOW_MISMATCH",
              f"stage1_judge WINDOW CHECK {wf_check.get('status')}: {wf_check.get('why')}; "
              f"running {win} (requested {window_rec['requested']})",
              quiet=dry_run or out_dir is not None, window=win,
              requested=window_rec["requested"], check=wf_check.get("status"),
              n_mismatches=wf_check.get("n_mismatches"))
    meta = _read_json(G.UNI / "universe.json", {})
    meta = meta if isinstance(meta, dict) else {}
    prev_runs = _tail_runs(runs_p)
    last = prev_runs[-1] if prev_runs else {}
    worker_mb = max(float(last.get("worker_peak_mb") or 0.0), 0.0) or DECLARED_WORKER_MB
    w, winfo = derive_workers(workers, worker_mb)
    # HOW MANY TO HOLD: what the budget can rule at the last measured rate, x1.5. Unmeasured:
    # the hour's share of the day-one target x4 -- a candidate bound, never a stop.
    rate = float(last.get("cells_per_core_sec") or 0.0)
    if cap is None:
        est = int(rate * w * budget_s * 1.5) if rate > 0 else int(TARGET_DAY_ONE / 24 * 4)
        cap = max(2_000, est)
    con = REC.connect(db_p)
    first_run = REC.get_meta(con, "first_run_utc")
    if not first_run and not dry_run:
        REC.set_meta(con, "first_run_utc", _iso(now))
        con.commit()
        first_run = _iso(now)
    t_seen = time.monotonic()
    watch = {r[0] for r in con.execute("SELECT cid FROM cells WHERE verdict=?", (REC.PASS,))}
    seen, seen_hit, seen_status = stream_seen(seen_path, watch, "")
    t_sel = time.monotonic()
    cpu_parent0 = time.process_time()
    bank, bank_status = load_bank_hashes(bank_path)
    d_gid, d_ident, dead_status = load_dead_sidecar(dead_path)
    from research import rollover_rejudge as RR
    from research import zero_spread_rejudge as ZR
    try:
        rr_active = bool(RR.detect_change(con, RR.fingerprint(), write=False).get("active"))
    except Exception:
        rr_active = False
    chosen, census = select_backlog(G, meta, con, cap=cap, now=now, docket=docket, seen=seen,
                                    bank=bank, dead=(d_gid, d_ident),
                                    collect_judged=RR_POPULATION_CAP if rr_active else 0)
    census["bank_status"] = bank_status
    census["dead_sidecar_status"] = dead_status
    select_s = time.monotonic() - t_sel
    seen_s = t_sel - t_seen
    earliest = universe_earliest(G.UNI) or date(2000, 1, 1)
    TRAIN_FRAC = None  # the full training window: no calendar cap
    cut_lb = lockbox_cut_lb(earliest, now.date())

    # ---- re-judge queues that go ahead of stage 1 (named priority, after v4 re-mint) ---------
    requeue: dict[str, Any] = {}
    try:
        requeue["zero_spread_stress"] = ZR.run(
            con, G, meta, dry_run=dry_run,
            list_path=(out_dir / ZR.LIST.name) if out_dir else None)
    except Exception as exc:
        requeue["zero_spread_stress"] = {"status": f"{UNMEASURED}: {type(exc).__name__}: {exc}"}
    try:
        requeue["engine_rollover"] = RR.run(
            con, list(census.get("judged_specs") or []), workers=w,
            budget_s=RR.BUDGET_SHARE * budget_s if rr_active else 0.0, dry_run=dry_run,
            queue_path=(out_dir / RR.QUEUE.name) if out_dir else None)
    except Exception as exc:
        requeue["engine_rollover"] = {"status": f"{UNMEASURED}: {type(exc).__name__}: {exc}"}
    census["judged_specs"] = []

    # ---- preflight (no build) --------------------------------------------------------------
    results: list[dict[str, Any]] = []
    to_build: list[dict[str, Any]] = []
    by_cid = {sp["cid"]: sp for sp in chosen}
    for sp in chosen:
        pre = preflight(G, meta, sp)
        if pre is None:
            to_build.append(sp)
        else:
            pre.update(cid=sp["cid"], cost_s=0.0)
            results.append(pre)

    # the parent's CPU for the docket stream and the no-build preflight: part of what a RULED
    # cell costs (the re-judge queues' own measurement is excluded -- it runs in its own pool)
    parent_cpu_s = time.process_time() - cpu_parent0

    # ---- the build pool ---------------------------------------------------------------------
    peak_mb = 0.0
    worker_s = 0.0
    bl = batches(to_build)
    per_batch: list[float] = []

    def _left() -> float:
        return budget_s - (time.monotonic() - started)

    if w <= 1:
        _init_worker(cut_lb.isoformat(), TRAIN_FRAC, win)
        for b in bl:
            if per_batch and _left() < float(np.median(per_batch)):
                break
            t0 = time.monotonic()
            rows, rss = evaluate_batch(b)
            per_batch.append(time.monotonic() - t0)
            results.extend(rows)
            peak_mb = max(peak_mb, rss)
    else:
        ex = ProcessPoolExecutor(max_workers=w, initializer=_init_worker,
                                 initargs=(cut_lb.isoformat(), TRAIN_FRAC, win))
        try:
            it = iter(bl)
            live: dict[Any, float] = {}
            for b in it:
                live[ex.submit(evaluate_batch, b)] = time.monotonic()
                if len(live) >= 2 * w:
                    break
            while live:
                fin, _ = wait(list(live), timeout=max(1.0, _left()), return_when=FIRST_COMPLETED)
                if not fin:
                    break
                for f in fin:
                    t0 = live[f]
                    try:
                        rows, rss = f.result()
                    except Exception:
                        continue
                    per_batch.append(time.monotonic() - t0)
                    results.extend(rows)
                    peak_mb = max(peak_mb, rss)
                    est = float(np.median(per_batch)) if per_batch else 0.0
                    if _left() > est:
                        nxt = next(it, None)
                        if nxt is not None:
                            live[ex.submit(evaluate_batch, nxt)] = time.monotonic()
                # finished futures leave the in-flight map (a rebuild, not a removal of records)
                live = {k: v for k, v in live.items() if k not in fin}
        finally:
            # THE BUDGET IS A WALL, NOT A SUGGESTION: a batch still running at the deadline is
            # killed rather than joined (its cells stay unruled and head the next run). The
            # process handles are taken BEFORE shutdown, which clears them.
            procs = list((getattr(ex, "_processes", None) or {}).values())
            ex.shutdown(wait=False, cancel_futures=True)
            for proc in procs:
                with contextlib.suppress(Exception):
                    proc.terminate()
    worker_s = float(sum(float(r.get("cost_s") or 0.0) for r in results))
    fdr = finalise(results, q)
    fdr["charge"] = trial_charge(results)
    fdr["window"] = win

    # ---- stage-2 cost: the sealed judge's full build on a sample of this run's survivors ---
    survivors = [r for r in results if r.get("verdict") == REC.PASS
                 and r.get("basis") == "BH_SURVIVOR"]
    s2_costs: list[float] = []
    if survivors and _left() > 30:
        if "G" not in _W:
            _init_worker(cut_lb.isoformat(), TRAIN_FRAC, win)
        for r in survivors[:STAGE2_COST_SAMPLE]:
            if _left() < 10:
                break
            c = stage2_cost(by_cid[r["cid"]])
            if c is not None:
                s2_costs.append(c)

    # ---- the record: every ruled cell, one row, one history line ----------------------------
    ts = _iso()
    bars_memo: dict = {}
    ruled = [r for r in results if r.get("verdict") in REC.VERDICTS]
    n_charged_cells = 0
    if not dry_run:
        _prior = _prior_rulings(con, [r["cid"] for r in ruled])
        n_charged_cells = charge_screened(
            screened_p, [(r["cid"], by_cid[r["cid"]]["family"]) for r in ruled if _charged(r)],
            _prior, ts, run_id)
        for r in ruled:
            sp = by_cid[r["cid"]]
            nb, fb = chart_stamp(G.UNI, sp["sym"], sp["tf"], bars_memo)
            con.execute(
                "INSERT INTO cells(cid, sym, family, tf, verdict, basis, reason, cause, p, t, "
                "mean_r, mean_r_x3, n_days_full, n_days_train, train_end, n_bars, first_bar, "
                "family_ver, first_seen, run_id, ruled_at, forwarded_at, score) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(cid) DO UPDATE SET verdict=excluded.verdict, basis=excluded.basis, "
                "reason=excluded.reason, cause=excluded.cause, p=excluded.p, t=excluded.t, "
                "mean_r=excluded.mean_r, mean_r_x3=excluded.mean_r_x3, "
                "n_days_full=excluded.n_days_full, n_days_train=excluded.n_days_train, "
                "train_end=excluded.train_end, n_bars=excluded.n_bars, "
                "first_bar=excluded.first_bar, family_ver=excluded.family_ver, "
                "run_id=excluded.run_id, ruled_at=excluded.ruled_at, "
                "times_ruled=cells.times_ruled+1, score=excluded.score, "
                "forwarded_at=COALESCE(cells.forwarded_at, excluded.forwarded_at)",
                (r["cid"], sp["sym"], sp["family"], sp["tf"], r["verdict"], r.get("basis"),
                 r.get("reason"), r.get("cause"), r.get("p"), r.get("t"), r.get("mean_r"),
                 r.get("mean_r_x3"), r.get("n_days_full"), r.get("n_days_train"),
                 r.get("train_end"), nb, fb, family_version(sp["family"]), sp["first_seen"],
                 run_id, ts, ts if r["verdict"] == REC.PASS else None, score_of(r)))
            con.execute(
                "INSERT INTO rulings(cid, run_id, ruled_at, verdict, basis, reason, cause, "
                "family, p, cost_s) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (r["cid"], run_id, ts, r["verdict"], r.get("basis"), r.get("reason"),
                 r.get("cause"), sp["family"], r.get("p"), r.get("cost_s")))
        con.commit()

    # ---- trials: every evaluated cell, per family ------------------------------------------
    fam_rows: dict[str, dict[str, Any]] = {}
    for r in ruled:
        fam = by_cid[r["cid"]]["family"]
        a = fam_rows.setdefault(fam, {"cells_ruled": 0, "cells_screened": 0, "testable": 0,
                                      "pass_bh": 0, "forward_unscreened": 0, "reject": 0,
                                      "unbuildable": 0, "cost_s": 0.0, "engine_cells": 0,
                                      "vector_cells": 0, "causes": {}})
        a["cells_ruled"] += 1
        a["cost_s"] += float(r.get("cost_s") or 0.0)
        if r.get("path") in ("engine", "vector"):
            a[f"{r['path']}_cells"] += 1
        v = r["verdict"]
        if v == REC.UNBUILDABLE:
            a["unbuildable"] += 1
            a["causes"][r.get("cause") or "?"] = a["causes"].get(r.get("cause") or "?", 0) + 1
            continue
        if r.get("reason") != "R_GATE1_ECONOMIC_PRIOR":
            a["cells_screened"] += 1
        if r.get("p") is not None and r.get("basis") != "UNSCREENABLE_TRAIN_WINDOW":
            a["testable"] += 1
        if v == REC.PASS:
            a["pass_bh" if r.get("basis") == "BH_SURVIVOR" else "forward_unscreened"] += 1
        else:
            a["reject"] += 1
    trial_rows = [{"ts": ts, "run_id": run_id, "family": f, "cells_screened": a["cells_screened"],
                   "cells_testable": a["testable"], "fdr_q": q, "fdr_m": fdr["m"],
                   "m_charged": fdr["charge"]["m_charged"], "window": win,
                   "pass_to_stage2": a["pass_bh"], "forward_unscreened": a["forward_unscreened"],
                   "dry_run": bool(dry_run)}
                  for f, a in sorted(fam_rows.items()) if a["cells_screened"]]
    if not dry_run or out_dir is not None:
        _append(trials_p, trial_rows)

    # ---- the survivors' priority file (read by the warmer and the sealed patch) ------------
    top_rows = con.execute(
        "SELECT cid, basis, score FROM cells WHERE score IS NOT NULL "
        "ORDER BY score DESC LIMIT ?", (4 * PRIORITY_TOP,)).fetchall()
    top_open = [row for row in top_rows if h64(row[0]) not in seen][:PRIORITY_TOP]
    if not dry_run or out_dir is not None:
        _write_json(prio_p, {
            "at": ts, "source": "research/stage1_judge.py",
            "rule": ("the head of the stage-2 order: tested cells not yet sealed-judged, by "
                     "training-window t DESCENDING (BH survivors and the rest alike -- stage 1 "
                     "only reorders). Named priorities (v4 re-mint, re-judge queues) stay ahead; "
                     "untested and unbuildable cells sort after every scored cell, never dropped. "
                     "The full order is the record (stage1_record.rank_of_state)"),
            "cells": [row[0] for row in top_open],
            "n_bh_survivors": sum(1 for row in top_open if row[1] == "BH_SURVIVOR")})

    # ---- throughput -------------------------------------------------------------------------
    wall = time.monotonic() - started
    n_ruled = len(ruled)
    built = [r for r in ruled if float(r.get("cost_s") or 0) > 0]
    cps_core = (len(built) / worker_s) if worker_s > 0 else 0.0
    # TESTED != RULED (audit 2026-09-30): only a cell with a training-window statistic was
    # tested; the rest were ruled untestable or unbuildable, mostly at no build cost.
    n_tested = sum(1 for r in ruled if score_of(r) is not None)
    by_fam_rate = {f: {"cells": a["cells_ruled"], "core_s": round(a["cost_s"], 3),
                       "cells_per_core_sec": (round(a["cells_ruled"] / a["cost_s"], 2)
                                              if a["cost_s"] > 0 else None),
                       "unbuildable": a["unbuildable"], "reject": a["reject"],
                       "pass_bh": a["pass_bh"], "forward_unscreened": a["forward_unscreened"],
                       "vector_cells": a["vector_cells"], "engine_cells": a["engine_cells"]}
                   for f, a in sorted(fam_rows.items(), key=lambda kv: -kv[1]["cells_ruled"])}
    run_row = {"ts": ts, "run_id": run_id, "ruled": n_ruled,
               "cells_charged_new": n_charged_cells, "built": len(built),
               "preflight_ruled": n_ruled - len(built),
               "pass_bh": len(survivors),
               "forward_unscreened": sum(1 for r in ruled if r.get("basis") ==
                                         "UNSCREENABLE_TRAIN_WINDOW"),
               "reject": sum(1 for r in ruled if r["verdict"] == REC.REJECT),
               "unbuildable": sum(1 for r in ruled if r["verdict"] == REC.UNBUILDABLE),
               "wall_s": round(wall, 2), "worker_s": round(worker_s, 2), "workers": w,
               "select_s": round(select_s, 2), "seen_s": round(seen_s, 2),
               "cells_per_core_sec": round(cps_core, 3),
               "tested": n_tested,
               "tested_per_core_sec": round(n_tested / worker_s, 4) if worker_s > 0 else 0.0,
               "parent_cpu_s": round(parent_cpu_s, 2),
               "ruled_per_core_sec": (round(n_ruled / (worker_s + parent_cpu_s), 4)
                                      if worker_s + parent_cpu_s > 0 else 0.0),
               "cells_per_wall_sec": round(n_ruled / wall, 3) if wall > 0 else 0.0,
               "worker_peak_mb": round(peak_mb, 1),
               "stage2_build_s_per_cell": (round(float(np.median(s2_costs)), 4)
                                           if s2_costs else None),
               "backlog": census["backlog"], "dry_run": bool(dry_run)}
    run_row["window"] = win
    doc = build_report(run_row, census, fdr, by_fam_rate, results, winfo, [*prev_runs, run_row],
                       first_run, seen_status, cut_lb, earliest, con, seen_hit, dry_run,
                       window=win)
    # the net the BOX saw: measured over the trailing 24h, else at the scheduled pace
    nb = doc.get("net_backlog_change_per_day") or {}
    n_meas = nb.get("measured_trailing_24h")
    run_row["net_backlog_change"] = (n_meas if isinstance(n_meas, int)
                                     else nb.get("scheduled_pace")
                                     if isinstance(nb.get("scheduled_pace"), int) else UNMEASURED)
    obw = ordering_bias_warning(census.get("oldest_ranked_unsealed_at"),
                                census.get("ranked_unsealed") if con is not None else UNMEASURED,
                                now, win)
    doc["ordering_bias"] = obw
    doc["ordering_bias_warning"] = obw["ordering_bias_warning"]
    # THE FENCE READS IT (PR143_v3): re-derived now that the ordering bias is on the document.
    doc["fence"] = throughput_fence(doc)
    doc["window"] = win
    doc["window_check"] = window_rec
    if obw["ordering_bias_warning"] is True:
        _loud("STAGE1_ORDERING_BIAS",
              f"stage1_judge ORDERING BIAS: a ranked cell has waited {obw['oldest_age_hours']}h "
              f"for the sealed judge ({obw['ranked_unsealed']:,} ranked and unjudged, window "
              f"{win}); the rank now decides which cells are ever judged",
              quiet=dry_run or out_dir is not None, window=win,
              oldest_age_hours=obw["oldest_age_hours"], ranked_unsealed=obw["ranked_unsealed"])
    if not dry_run or out_dir is not None:
        _append(runs_p, [run_row])
    doc["requeue"] = requeue
    con.close()
    _write_json(report, doc)
    return doc


def _stage2_measured(con, hit: dict[str, str], seen_status: str, since: str) -> dict[str, Any]:
    """Forwarded cells the sealed judge has since ruled on, from its own seen-cells record: the
    judged-at stamp of every forwarded cell found there (`hit`, collected in the one stream)."""
    n_fwd = int(con.execute("SELECT COUNT(*) FROM cells WHERE verdict=?",
                            (REC.PASS,)).fetchone()[0])
    if not seen_status.startswith("MEASURED"):
        return {"status": seen_status, "forwarded_total": n_fwd}
    return {"status": "MEASURED", "forwarded_total": n_fwd, "judged_total": len(hit),
            "judged_24h": sum(1 for v in hit.values() if v >= since)}


def build_report(run_row, census, fdr, by_fam_rate, results, winfo, runs, first_run,
                 seen_status, cut_lb, earliest, con, seen_hit, dry_run,
                 window: str | None = None) -> dict[str, Any]:
    now = _now()
    floor24 = (now - timedelta(hours=24)).isoformat(timespec="seconds")
    day_runs = [r for r in runs if str(r.get("ts") or "") >= floor24 and not r.get("dry_run")]
    ruled_24h = int(sum(int(r.get("ruled") or 0) for r in day_runs))
    fwd_24h = int(sum(int(r.get("pass_bh") or 0) + int(r.get("forward_unscreened") or 0)
                      for r in day_runs))
    rates = [float(r.get("cells_per_core_sec") or 0) for r in runs if r.get("cells_per_core_sec")]
    rate = float(np.median(rates)) if rates else 0.0
    t_rates = [float(r["tested_per_core_sec"]) for r in runs if r.get("tested_per_core_sec")]
    r_rates = [float(r["ruled_per_core_sec"]) for r in runs if r.get("ruled_per_core_sec")]
    rate_t = float(np.median(t_rates)) if t_rates else 0.0
    rate_r = float(np.median(r_rates)) if r_rates else 0.0
    cores = int(winfo.get("cores") or 0)
    # PROJECTIONS, labelled as such: TESTED cells per day from the measured tested rate (the
    # headline), and RULED cells per day (what shrinks the backlog) from the ruled rate.
    proj18 = int(rate_t * 18 * DUTY * 86400) if rate_t else UNMEASURED
    proj_here = int(rate_t * cores * DUTY * 86400) if rate_t and cores else UNMEASURED
    proj18_ruled = int(rate_r * 18 * DUTY * 86400) if rate_r else UNMEASURED
    # the CONSERVATIVE bound: as if every backlog cell needed a build (no free preflight
    # ruling), at the measured built-cells rate
    proj18_built = int(rate * 18 * DUTY * 86400) if rate else UNMEASURED
    # the SCHEDULED pace: what one hourly leg rules (and tests) per run, x24
    per_run = [int(r.get("ruled") or 0) for r in runs[-6:] if not r.get("dry_run")]
    scheduled = int(np.median(per_run) * 24) if per_run else UNMEASURED
    per_run_t = [int(r["tested"]) for r in runs[-6:] if not r.get("dry_run") and "tested" in r]
    scheduled_t = int(np.median(per_run_t) * 24) if per_run_t else UNMEASURED
    tested_24h = int(sum(int(r.get("tested") or 0) for r in day_runs))
    target = target_for(first_run, now)
    backlog_total = int(census.get("backlog") or 0)
    wrong_space = int(census.get("wrong_space") or 0)
    # Days to clear are counted on the REAL backlog: the wrong-space rows clear when sealed
    # pass 2 lands, not by stage-1 work. Both sizes are published.
    backlog = backlog_total - wrong_space
    s2_build = [float(r["stage2_build_s_per_cell"]) for r in runs
                if r.get("stage2_build_s_per_cell")]
    s2_b = float(np.median(s2_build)) if s2_build else None
    bd = _read_json(BURNDOWN, {})
    gate_s = ((bd.get("sweep") or {}).get("post_build_s_per_cell")
              if isinstance(bd, dict) else None)
    stage2_proj: Any = UNMEASURED
    stage2_why = "no stage-1 survivor has been timed through the sealed build yet"
    if s2_b:
        build_cap = 18 * DUTY * 86400 / s2_b
        if isinstance(gate_s, (int, float)) and gate_s > 0:
            gate_cap = 86400 * DUTY / float(gate_s)
            stage2_proj = int(min(build_cap, gate_cap))
            stage2_why = (f"min(build limb {int(build_cap):,}/day at {s2_b:.3f} s/cell on 18 "
                          f"cores x {DUTY}, gate limb {int(gate_cap):,}/day at {gate_s} s/cell "
                          f"single-threaded x {DUTY}) -- gate s/cell from JUDGING_BURNDOWN")
        else:
            stage2_proj = int(build_cap)
            stage2_why = (f"build limb only ({s2_b:.3f} s/cell, 18 cores x {DUTY}); the gate "
                          f"phase per cell is UNMEASURED here (JUDGING_BURNDOWN.sweep)")
    unb: dict[str, int] = {}
    unb_fam: dict[str, dict[str, int]] = {}
    rej: dict[str, int] = {}
    for r in results:
        if r.get("verdict") == REC.UNBUILDABLE:
            c = str(r.get("cause") or "?")
            unb[c] = unb.get(c, 0) + 1
        elif r.get("verdict") == REC.REJECT:
            rej[str(r.get("reason"))] = rej.get(str(r.get("reason")), 0) + 1
    try:
        for fam, cause, n in con.execute(
                "SELECT family, cause, COUNT(*) FROM cells WHERE verdict=? GROUP BY family, cause",
                (REC.UNBUILDABLE,)):
            unb_fam.setdefault(str(fam), {})[str(cause)] = int(n)
        record = {str(v): int(n) for v, n in con.execute(
            "SELECT verdict || ':' || COALESCE(basis, reason, cause, ''), COUNT(*) FROM cells "
            "GROUP BY 1")}
        s2 = _stage2_measured(con, seen_hit, seen_status, floor24)
    except Exception as exc:
        record, s2 = {}, {"status": f"{UNMEASURED}: {type(exc).__name__}: {exc}"}
    oldest = census.get("oldest_first_seen")
    age_d = None
    with contextlib.suppress(Exception):
        age_d = round((now - datetime.fromisoformat(str(oldest))).total_seconds() / 86400, 2)
    measured_per_day = ruled_24h if day_runs else UNMEASURED
    # THE CREATION RATE: distinct docket cells first seen in the window (the docket's own clock),
    # the larger of the last 24h and the 7-day daily mean -- the conservative side for "shrinking".
    c24, c7 = int(census.get("created_24h") or 0), int(census.get("created_7d") or 0)
    creation = max(c24, round(c7 / 7.0)) if census.get("cells") else UNMEASURED
    bd_in = ((bd.get("inflow") or {}).get("created_per_hour") or {}) if isinstance(bd, dict) \
        else {}

    def _net(rate_: Any) -> Any:
        if isinstance(rate_, (int, float)) and isinstance(creation, int):
            return int(creation - rate_)
        return UNMEASURED

    def _clear(rate_: Any, size: int | None = None) -> Any:
        n = _net(rate_)
        b = backlog if size is None else size
        if not isinstance(n, int):
            return UNMEASURED
        if b == 0:
            return 0.0
        return round(b / -n, 2) if n < 0 else "GROWING"

    net = {"measured_trailing_24h": _net(measured_per_day), "scheduled_pace": _net(scheduled),
           "projected_18c_50pct": _net(proj18_ruled),
           "basis": "creation minus RULED cells per day (a ruled cell leaves the unruled backlog)"}
    ucls: dict[str, int] = {}
    for r in results:
        k = unknown_class(r)
        if k:
            ucls[k] = ucls.get(k, 0) + 1
    n_r = sum(1 for r in results if r.get("verdict") in REC.VERDICTS)
    fwd_unknown = sum(1 for r in results if r.get("verdict") == REC.PASS and unknown_class(r))
    n_unknown = sum(ucls.values())
    # Every wrong-space row is a banked build failure the sealed judge re-submits and rules
    # UNKNOWN/NOT_RUN, so WITH them the share adds them to both sides.
    share_without = round(n_unknown / n_r, 4) if n_r else UNMEASURED
    share_with = (round((n_unknown + wrong_space) / (n_r + wrong_space), 4)
                  if (n_r + wrong_space) else UNMEASURED)
    doc: dict[str, Any] = {
        "at": _iso(now), "status": "MEASURED" if results else UNMEASURED,
        "dry_run": bool(dry_run),
        "law": ("stage 1 rules on EVERY never-judged docket cell from its training window only "
                "(before the sealed walk-forward test region and a lower bound on the lockbox "
                "cut), BH at q over every cell evaluated in the run, 3x spread stress; every "
                "evaluated cell charged in STAGE1_TRIALS.jsonl; only survivors go to the sealed "
                "gauntlet, at the front of its order, behind v4 re-mint and evicted re-judges; "
                "a reject is re-screenable and never deleted; stage 1 has no promotion authority"),
        "run": run_row,
        "stage1_per_day": measured_per_day,
        "stage1_tested_per_day": tested_24h if day_runs else UNMEASURED,
        "stage1_tested_share_of_ruled": (round(tested_24h / ruled_24h, 4)
                                         if day_runs and ruled_24h else UNMEASURED),
        "stage1_per_day_projected_18c_50pct": proj18,
        "stage1_per_day_projected_basis": ("PROJECTION from the measured TESTED rate (cells with "
                                           "a training-window statistic per core-second) x 18 "
                                           f"cores x {DUTY} duty x 86,400 s; not a measurement"),
        "stage1_ruled_per_day_projected_18c_50pct": proj18_ruled,
        "stage1_built_per_day_projected_18c_50pct": proj18_built,
        "stage1_ruled_projection_note": ("the RULED rate counts no-build preflight rulings "
                                         "(untradeable, modifier-refused, dead session), whose "
                                         "share depends on the host's bars; the built-rate "
                                         "projection is the bound if every cell needs a build"),
        "stage1_per_day_scheduled": scheduled,
        "stage1_tested_per_day_scheduled": scheduled_t,
        "stage2_per_day": s2.get("judged_24h", UNMEASURED) if isinstance(s2, dict) else UNMEASURED,
        "creation_per_day": creation,
        "creation": {"created_24h": c24, "created_7d": c7, "basis": (
            "distinct docket cells by first_seen; the larger of the last 24h and the 7-day mean"),
            "burndown_inflow_per_hour": bd_in or UNMEASURED},
        "net_backlog_change_per_day": net,
        "backlog_cells": backlog_total,
        "backlog_total": backlog_total,
        "backlog_excluding_wrong_space": backlog,
        "wrong_space": {
            "rows": wrong_space, "bucket": WRONG_SPACE,
            "key_space_mismatch_rows": census.get("key_space_mismatch_rows"),
            "bank": census.get("bank_status", UNMEASURED),
            "rule": ("docket rows whose judge-space cell id is in judge_coverage's build-failure "
                     "bank while judge_coverage's own key (chart beside params) misses it; "
                     "counted, kept on the docket, NOT screened as real cells; they clear when "
                     "sealed pass 2 lands the stripped judge_coverage docket_cell_id hunk")},
        "days_to_clear": {"measured_trailing_24h": _clear(measured_per_day),
                          "scheduled_pace": _clear(scheduled),
                          "projected_18c_50pct": _clear(proj18_ruled),
                          "projected_18c_50pct_including_wrong_space":
                              _clear(proj18_ruled, backlog_total),
                          "projected_18c_50pct_if_every_cell_is_built": _clear(proj18_built),
                          "rule": "backlog_excluding_wrong_space / (stage-1 per day - creation "
                                  "per day); GROWING when creation is not outrun"},
        "unknown_causes": {
            "this_run": dict(sorted(ucls.items(), key=lambda kv: -kv[1])),
            "share_of_ruled_that_the_sealed_judge_would_rule_unknown": share_without,
            "share_excluding_wrong_space": share_without,
            "share_including_wrong_space": share_with,
            "wrong_space_rows": wrong_space,
            "dead_session_variants_on_backlog": census.get("dead_session_variants"),
            "dead_session_sidecar": census.get("dead_sidecar_status", UNMEASURED),
            "forwarded_to_stage2_with_an_unknown_class": fwd_unknown,
            "rule": ("before: the share of ruled cells the sealed judge would have spent a slot "
                     "on and returned UNKNOWN/NOT_RUN (no data, no driver, never fires in its "
                     "session, build failure, under 60 days, no signals); after: forwarded "
                     "cells in those classes, 0 by construction")},
        "stage1": {
            "measured_per_day_trailing_24h": measured_per_day,
            "scheduled_pace_per_day": scheduled,
            "cells_per_core_sec_median": round(rate, 3) if rate else UNMEASURED,
            "tested_per_core_sec_median": round(rate_t, 4) if rate_t else UNMEASURED,
            "ruled_per_core_sec_median": round(rate_r, 4) if rate_r else UNMEASURED,
            "projected_per_day_18c_50pct": proj18,
            "projected_per_day_this_host_50pct": proj_here,
            "target_per_day": target,
            "target_rule": (f"{TARGET_DAY_ONE:,}/day on day one ({first_run}), linear to "
                            f"{TARGET_FULL:,}/day by day {RAMP_DAYS}"),
            "by_family": by_fam_rate,
            "fdr": fdr,
            "rejects_by_reason": rej,
        },
        "stage2": {
            "forwarded_per_day_trailing_24h": fwd_24h if day_runs else UNMEASURED,
            "survivors_forwarded_this_run": run_row["pass_bh"],
            "forwarded_unscreened_this_run": run_row["forward_unscreened"],
            "sealed_rulings_on_forwarded": s2,
            "build_s_per_cell_measured": round(s2_b, 4) if s2_b else UNMEASURED,
            "gate_s_per_cell_from_burndown": gate_s if gate_s is not None else UNMEASURED,
            "projected_capacity_per_day": stage2_proj,
            "projection_basis": stage2_why,
        },
        "backlog": {"cells": backlog_total, "excluding_wrong_space": backlog,
                    "wrong_space": wrong_space, "docket_cells": census.get("cells"),
                    "sealed_judged": census.get("sealed_judged"),
                    "oldest_first_seen": oldest, "oldest_age_days": age_d,
                    "tiers": census.get("tiers"), "due_rescreen": census.get("due_rescreen"),
                    "stamped_only_ratchet": census.get("stamped_only_ratchet"),
                    "seen_cells": seen_status},
        "unbuildable_by_cause_this_run": dict(sorted(unb.items(), key=lambda kv: -kv[1])),
        "unbuildable_by_family_and_cause": unb_fam,
        "record_census": record,
        "days_to_clear_backlog": {
            "basis": "backlog_excluding_wrong_space",
            "at_measured_pace": (round(backlog / ruled_24h, 2)
                                 if day_runs and ruled_24h else UNMEASURED),
            "at_scheduled_pace": (round(backlog / scheduled, 2)
                                  if isinstance(scheduled, int) and scheduled else UNMEASURED),
            "at_projected_18c_50pct": (round(backlog / proj18_ruled, 2)
                                       if isinstance(proj18_ruled, int) and proj18_ruled
                                       else UNMEASURED)},
        "boundary": {"lockbox_cut_lower_bound": cut_lb.isoformat(),
                     "universe_earliest_bar": earliest.isoformat(),
                     "min_days_full": MIN_DAYS_FULL, "min_train_days": MIN_TRAIN_DAYS,
                     "window": window or WINDOW},
        "workers": winfo,
        "priority_file": str(PRIORITY.relative_to(DESK)),
    }
    doc["fence"] = throughput_fence(doc)
    return doc


def summary(path: Path | None = None) -> dict[str, Any]:
    """The small block `judging_throughput` embeds into JUDGING_THROUGHPUT.json."""
    d = _read_json(path or REPORT, {})
    if not isinstance(d, dict) or not d:
        return {"status": UNMEASURED, "why": f"{REPORT.name} absent: stage 1 has not run here"}
    s1, s2, bl = d.get("stage1") or {}, d.get("stage2") or {}, d.get("backlog") or {}
    return {"status": d.get("status"), "at": d.get("at"), "source": REPORT.name,
            "stage1_per_day": d.get("stage1_per_day"), "stage2_per_day": d.get("stage2_per_day"),
            "creation_per_day": d.get("creation_per_day"),
            "net_backlog_change_per_day": d.get("net_backlog_change_per_day"),
            "days_to_clear": d.get("days_to_clear"),
            "unknown_causes": (d.get("unknown_causes") or {}).get("this_run"),
            "stage1_projected_per_day_18c_50pct": s1.get("projected_per_day_18c_50pct"),
            "stage1_target_per_day": s1.get("target_per_day"),
            "stage2_projected_capacity_per_day": s2.get("projected_capacity_per_day"),
            "survivors_forwarded_per_day": s2.get("forwarded_per_day_trailing_24h"),
            "backlog": bl.get("cells"), "backlog_total": d.get("backlog_total"),
            "backlog_excluding_wrong_space": d.get("backlog_excluding_wrong_space"),
            "wrong_space": d.get("wrong_space"),
            "unknown_share": {k: (d.get("unknown_causes") or {}).get(k) for k in (
                "share_excluding_wrong_space", "share_including_wrong_space")},
            "oldest_age_days": bl.get("oldest_age_days"),
            "unbuildable_by_cause": d.get("unbuildable_by_cause_this_run"),
            "days_to_clear_backlog": d.get("days_to_clear_backlog"),
            "fence": d.get("fence"),
            "window": d.get("window") or (d.get("boundary") or {}).get("window"),
            "ordering_bias_warning": d.get("ordering_bias_warning", UNMEASURED),
            "ordering_bias": d.get("ordering_bias")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true", help="one bounded run (the hourly leg)")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--workers", type=int, default=None, help="override the measured count")
    ap.add_argument("--cap", type=int, default=None, help="cells held this run (default derived)")
    ap.add_argument("--q", type=float, default=FDR_Q)
    ap.add_argument("--dry-run", action="store_true", help="rule but record nothing")
    ap.add_argument("--out-dir", type=Path, default=None, help="write artifacts here instead")
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, workers=a.workers, cap=a.cap, q=a.q, dry_run=a.dry_run,
              out_dir=a.out_dir)
    r = doc.get("run") or {}
    s1 = doc.get("stage1") or {}
    print(f"stage1_judge {doc.get('status')}: ruled {r.get('ruled')} ({r.get('built')} built) "
          f"in {r.get('wall_s')}s on {r.get('workers')} worker(s) = "
          f"{r.get('cells_per_core_sec')} cells/core-s; pass {r.get('pass_bh')}, forwarded "
          f"unscreened {r.get('forward_unscreened')}, reject {r.get('reject')}, unbuildable "
          f"{r.get('unbuildable')}; projected {s1.get('projected_per_day_18c_50pct')}/day "
          f"(18 cores x {DUTY}); fence {(doc.get('fence') or {}).get('status')}")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONHASHSEED", "0")
    raise SystemExit(main())
