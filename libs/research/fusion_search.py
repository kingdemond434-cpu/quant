"""FUSION SEARCH ENGINE -- combinatorial dataset search that cannot quietly buy itself a lottery
ticket (EXECUTION_QUEUE.md RANK 5).

DISTINCT FROM ``scripts/fusion_engine.py``, which TRANSFORMS a known set of inputs. This SEARCHES:
enumerate combinations of the desk's datasets, build candidate representations, screen each one.
The queue's own warning is the entire design constraint -- *"combinatorial search is a trial-count
explosion, and the desk's own law says breadth is EARNED per axis after a single-axis screen shows
signal. So the search must be mechanism-prior-gated, not exhaustive-by-default."*

An ungated version of this module is the single most dangerous thing the desk could build. 20
datasets taken 3 at a time is 1,140 combinations; times 3 representations times 3 horizons is
10,260 trials. At that width the best cell has an expected Sharpe near 1.0 **on pure noise**, so it
would hand back a beautiful, entirely fake survivor every single run, and every downstream gate
would be evaluating a number that was selected precisely for being extreme. Three rules keep it
honest, and all three had to be structural rather than advisory:

1. BREADTH IS EARNED, NOT ASSUMED. An axis may enter combination search only if it has ALREADY
   returned SCREEN-INTERESTING on its own. Combining axes that individually carry nothing is not
   discovery, it is fishing with more hooks: the graveyard is full of axes that failed single-axis
   screens (exchange_netflow's residual IC flipped sign; aggregate positioning t=+0.15), and
   pairing three of those cannot manufacture information none of them has.

2. THE BUDGET IS CHARGED ON ENUMERATION, NOT EXECUTION. This is ``libs/research/pre_filter.py``'s
   rule applied to combinatorics: *"a pre-filter REJECT still counts in the trial ledger. The filter
   saves COMPUTE, never multiplicity budget -- a candidate we looked at is a candidate we tested,
   however cheaply."* So ``effective_n_trials`` is the size of the ENUMERATED grid. Pruning 900 of
   1,000 cells cheaply still costs 1,000 trials, and stopping early after a hit costs the full grid
   too -- otherwise the stopping rule itself becomes the overfit.

3. THE GRID IS PRE-REGISTERED AND HASHED. ``FusionPlan.grid_hash`` covers every cell before any
   compute runs, so a grid cannot be grown after results are seen and then reported at the smaller
   count. Garden-of-forking-paths by grid extension is otherwise undetectable after the fact.

WHAT IT WILL DO ON THIS DESK TODAY: nothing, loudly. Zero axes have earned breadth, so
``plan_search`` returns an empty grid with the reason per axis. That is the correct output, not a
failure -- an engine that searched anyway would be the failure.

REPRESENTATIONS CARRY MECHANISMS, not just arithmetic; see ``REPRESENTATIONS``. A representation
without a stated mechanism is a free parameter, and free parameters are what the trial count is
supposed to be pricing.

Pure numpy. Import from ``libs.research.fusion_search``; CLI is ``scripts/run_fusion_search.py``.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]

#: Verdict from ``libs.research.axis_screen`` that earns an axis the right to be combined. Nothing
#: weaker qualifies -- TIMING-ARTIFACT and SUSPECT-LOOKAHEAD are artifacts, and a plain miss is a
#: miss. This constant IS rule 1.
EARNING_VERDICT = "SCREEN-INTERESTING"

#: Hard ceiling on enumerated cells. Not a performance guard -- a MULTIPLICITY guard. Above this the
#: deflated-Sharpe hurdle is so high that no real edge this desk can measure would clear it, so
#: enumerating more cells cannot produce a promotable result and can only produce a lucky-looking
#: one. Refusing is strictly better than searching and then failing to promote.
MAX_CELLS = 240

#: Combination width. Triples per the queue; pairs are cheaper and are searched first when allowed.
DEFAULT_K = 3


def _z(x: np.ndarray, win: int = 20) -> np.ndarray:
    """Causal rolling z-score. Uses only data at or before t -- never a full-sample mean."""
    x = np.asarray(x, dtype=float)
    out = np.full(x.shape, np.nan)
    for t in range(len(x)):
        lo = max(0, t - win + 1)
        w = x[lo:t + 1]
        w = w[np.isfinite(w)]
        if len(w) >= max(5, win // 4):
            sd = float(np.std(w))
            out[t] = (x[t] - float(np.mean(w))) / sd if sd > 0 else 0.0
    return out


def _col_mean(rows: np.ndarray) -> np.ndarray:
    """Column-wise mean ignoring NaN, NaN where a column is entirely NaN.

    Not ``np.nanmean``: the z-score warmup leaves whole columns NaN, and nanmean emits "Mean of
    empty slice" there. The repo turns warnings into errors, and silencing the warning would also
    silence real ones -- so the count guard is explicit instead.
    """
    finite = np.isfinite(rows)
    cnt = finite.sum(axis=0)
    tot = np.where(finite, rows, 0.0).sum(axis=0)
    return np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan)


def _composite(cols: Sequence[np.ndarray]) -> np.ndarray:
    """Mean of z-scores. MECHANISM: these series measure ONE latent pressure, so averaging them
    cancels idiosyncratic noise and leaves the common component."""
    return np.asarray(_col_mean(np.vstack([_z(c) for c in cols])), dtype=float)


def _divergence(cols: Sequence[np.ndarray]) -> np.ndarray:
    """z(first) minus the mean z of the rest. MECHANISM: the first series is out of line with
    series that normally track it, and the gap is the information -- the kimchi/premium shape."""
    zs = [_z(c) for c in cols]
    peers = _col_mean(np.vstack(zs[1:])) if len(zs) > 1 else np.zeros_like(zs[0])
    return np.asarray(zs[0] - peers, dtype=float)


def _conditioned(cols: Sequence[np.ndarray]) -> np.ndarray:
    """z(first), zeroed unless the others AGREE in sign. MECHANISM: the signal is only meaningful
    in a confirming regime; disagreement means the state is ambiguous, so take no view."""
    zs = [_z(c) for c in cols]
    if len(zs) < 2:
        return np.asarray(zs[0], dtype=float)
    others = np.vstack(zs[1:])
    agree = np.all(np.sign(others) == np.sign(others[0]), axis=0) & np.isfinite(others[0])
    return np.asarray(np.where(agree, zs[0], 0.0), dtype=float)


#: name -> (builder, stated mechanism). A representation with no mechanism is a free parameter.
REPRESENTATIONS: dict[str, tuple[Callable[[Sequence[np.ndarray]], np.ndarray], str]] = {
    "composite": (_composite, "the series share one latent pressure; averaging cancels noise"),
    "divergence": (_divergence,
                   "the first series is out of line with peers that normally track it"),
    "conditioned": (_conditioned,
                    "the first series only informs when the others confirm the state"),
}


@dataclass(frozen=True)
class AxisEligibility:
    """Whether one axis has EARNED the right to be combined, with the reason either way."""

    axis: str
    earned: bool
    reason: str
    single_axis_verdict: str | None = None


@dataclass(frozen=True)
class FusionCell:
    """One pre-registered trial. Immutable: a cell cannot be edited after the grid is hashed."""

    axes: tuple[str, ...]
    representation: str
    horizon_days: int

    @property
    def cell_id(self) -> str:
        return f"{'+'.join(self.axes)}|{self.representation}|h{self.horizon_days}"


@dataclass
class FusionPlan:
    """The grid, declared BEFORE compute and hashed so it cannot grow afterwards."""

    cells: list[FusionCell] = field(default_factory=list)
    eligible: list[str] = field(default_factory=list)
    excluded: list[AxisEligibility] = field(default_factory=list)
    refused_reason: str | None = None

    @property
    def grid_hash(self) -> str:
        payload = json.dumps(sorted(c.cell_id for c in self.cells))
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    @property
    def effective_n_trials(self) -> int:
        """The multiplicity owed: the ENUMERATED grid, not the cells that survived pruning."""
        return len(self.cells)


@dataclass
class CellResult:
    cell_id: str
    verdict: str
    ic: float | None = None
    sharpe: float | None = None
    pruned: bool = False
    note: str = ""


@dataclass
class FusionResult:
    """Every enumerated cell is accounted for -- survivors AND the ones nobody wants to report."""

    grid_hash: str
    effective_n_trials: int
    results: list[CellResult] = field(default_factory=list)
    survivors: list[str] = field(default_factory=list)
    dsr_hurdle_sharpe: float | None = None
    refused_reason: str | None = None

    @property
    def n_pruned(self) -> int:
        return sum(1 for r in self.results if r.pruned)


def eligibility_from_registry(screens: Mapping[str, str],
                              root: Path | None = None) -> list[AxisEligibility]:
    """Eligibility over the RANK 4 registry's assets -- the queue's "triples from the registry".

    TWO gates, and the registry supplies the one screens cannot. A verdict says an axis carries
    signal; the registry says the data actually EXISTS and how long it is. Combining an axis whose
    span is unmeasured on this box would enumerate trials against data that is not there, and the
    resulting NO-INPUT cells would still be charged to the multiplicity budget -- paying real
    trials for cells that were never testable.
    """
    try:
        from libs.research.data_registry import build
        assets = {a.id: a for a in build(root)}
    except Exception:
        return eligibility_from_screens(screens)

    out: list[AxisEligibility] = []
    for axis, verdict in sorted(screens.items()):
        asset = assets.get(axis)
        earned = verdict == EARNING_VERDICT
        if not earned:
            reason = (f"single-axis verdict was {verdict!r}, not {EARNING_VERDICT!r} -- breadth is "
                      "EARNED per axis; combining axes that individually carry nothing is fishing "
                      "with more hooks, not discovery")
        elif asset is None:
            earned, reason = False, (
                f"passed its screen but no registry asset is named {axis!r} -- enumerating cells "
                "against data the registry cannot find would charge real trials for untestable "
                "cells")
        elif not asset.span.measured:
            earned, reason = False, (
                f"passed its screen but its span is {asset.span.status!r} on this box, so cells "
                "built from it would be NO-INPUT and still cost multiplicity")
        else:
            reason = (f"passed its own single-axis screen; registry span {asset.span.days}d "
                      f"({asset.span.first}->{asset.span.last})")
        out.append(AxisEligibility(axis=axis, earned=earned, reason=reason,
                                   single_axis_verdict=verdict))
    return out


def log_trials(plan: FusionPlan, ledger: Path | None = None) -> int:
    """Append EVERY enumerated cell to the trial ledger. Returns the number written.

    The queue's "log EVERY cell as a DSR-counted trial", made literal. Written at PLAN time, before
    a single cell is computed, because that is when the multiplicity is actually incurred -- logging
    after execution would silently omit whatever got pruned, which is the exact leak rule 2 exists
    to close. Append-only: a trial that can be un-logged is a budget that can be gamed.
    """
    ledger = ledger or (_ROOT / "data/fusion_trials.jsonl")
    if not plan.cells:
        return 0
    from datetime import UTC, datetime
    stamp = datetime.now(tz=UTC).isoformat()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        for c in plan.cells:
            fh.write(json.dumps({
                "ts": stamp, "grid_hash": plan.grid_hash, "cell_id": c.cell_id,
                "axes": list(c.axes), "representation": c.representation,
                "horizon_days": c.horizon_days,
                "grid_size": plan.effective_n_trials,
                "note": "enumerated -- charged to the DSR budget whether or not it was computed",
            }) + "\n")
    return len(plan.cells)


def record_survivors(res: FusionResult, graph: Path | None = None) -> int:
    """Record surviving cells in the knowledge graph as CORRELATION-grade edges, never mechanisms.

    The graph's own rule is that an edge carries its EVIDENCE STATE so a correlation cannot quietly
    become a mechanism (``scripts/knowledge_engine.py``:13-16). A fusion survivor is the weakest
    evidence class there is -- it survived a screen inside a grid that was selected over -- so it
    lands as ``correlational`` with its grid size attached. Anything stronger would be laundering
    a search result into a claim.
    """
    graph = graph or (_ROOT / "data/knowledge_graph_edges.jsonl")
    if not res.survivors:
        return 0
    from datetime import UTC, datetime
    stamp = datetime.now(tz=UTC).isoformat()
    graph.parent.mkdir(parents=True, exist_ok=True)
    with graph.open("a", encoding="utf-8") as fh:
        for cid in res.survivors:
            fh.write(json.dumps({
                "ts": stamp, "source": "fusion_search", "edge": cid,
                "evidence_state": "correlational",
                "n_trials_when_found": res.effective_n_trials,
                "dsr_hurdle_sharpe": res.dsr_hurdle_sharpe,
                "caveat": "survived a screen inside a grid of "
                          f"{res.effective_n_trials} enumerated cells -- selection over that grid "
                          "is priced into the hurdle, and this edge is NOT a mechanism until an "
                          "independent test names the constraint that produces it",
            }) + "\n")
    return len(res.survivors)


def eligibility_from_screens(screens: Mapping[str, str]) -> list[AxisEligibility]:
    """Map ``axis -> single-axis screen verdict`` into combination eligibility.

    RULE 1 lives here. An axis with no single-axis signal cannot buy signal by being combined; the
    graveyard records several that failed alone and would otherwise be recycled as "novel" triples.
    """
    out = []
    for axis, verdict in sorted(screens.items()):
        earned = verdict == EARNING_VERDICT
        out.append(AxisEligibility(
            axis=axis, earned=earned, single_axis_verdict=verdict,
            reason=("passed its own single-axis screen" if earned else
                    f"single-axis verdict was {verdict!r}, not {EARNING_VERDICT!r} -- breadth is "
                    "EARNED per axis; combining axes that individually carry nothing is fishing "
                    "with more hooks, not discovery")))
    return out


def plan_search(eligibility: Sequence[AxisEligibility], *,
                representations: Sequence[str] = (),
                horizons: Sequence[int] = (1, 5),
                k: int = DEFAULT_K,
                max_cells: int = MAX_CELLS) -> FusionPlan:
    """Enumerate the grid, or REFUSE with a reason. Nothing is computed here."""
    reps = list(representations) or list(REPRESENTATIONS)
    unknown = [r for r in reps if r not in REPRESENTATIONS]
    if unknown:
        raise ValueError(f"unknown representation(s): {unknown}")

    earned = [e.axis for e in eligibility if e.earned]
    excluded = [e for e in eligibility if not e.earned]
    plan = FusionPlan(eligible=earned, excluded=excluded)

    if len(earned) < k:
        plan.refused_reason = (
            f"{len(earned)} axis/axes have earned breadth; a width-{k} search needs {k}. "
            "This is the designed outcome, not a bug: searching combinations of axes that failed "
            "their own single-axis screens manufactures survivors from noise. Earn an axis first.")
        return plan

    cells = [FusionCell(tuple(combo), rep, h)
             for combo in itertools.combinations(sorted(earned), k)
             for rep in sorted(reps)
             for h in sorted(horizons)]
    if len(cells) > max_cells:
        plan.refused_reason = (
            f"the grid would enumerate {len(cells)} cells (>{max_cells}). Refused on MULTIPLICITY, "
            "not compute: at that width the deflated-Sharpe hurdle exceeds anything this desk can "
            "measure, so the search could only ever return a lucky-looking cell. Narrow the axes "
            "or the representations and re-plan.")
        return plan
    plan.cells = cells
    return plan


def run_search(
    plan: FusionPlan,
    series_for: Callable[[str], np.ndarray | None],
    target_for: Callable[[int], np.ndarray | None],
    *,
    screen: Callable[..., dict[str, Any]] | None = None,
    pre_filter_fn: Callable[..., dict[str, Any]] | None = None,
) -> FusionResult:
    """Run the pre-registered grid. Every cell is accounted for, pruned or screened.

    The DSR hurdle is computed from ``plan.effective_n_trials`` -- the full enumerated grid -- so a
    cheap prune buys compute and never multiplicity, and an early hit does not shrink the bill.
    """
    res = FusionResult(grid_hash=plan.grid_hash,
                       effective_n_trials=plan.effective_n_trials,
                       refused_reason=plan.refused_reason)
    if plan.refused_reason or not plan.cells:
        return res

    # The hurdle is fixed BEFORE any cell is judged, from the grid size alone.
    try:
        from libs.validation.dsr import expected_max_sharpe
        res.dsr_hurdle_sharpe = float(expected_max_sharpe(plan.effective_n_trials, 1.0))
    except Exception:
        res.dsr_hurdle_sharpe = None

    for cell in plan.cells:
        cols = [series_for(a) for a in cell.axes]
        target = target_for(cell.horizon_days)
        if any(c is None for c in cols) or target is None:
            res.results.append(CellResult(cell.cell_id, "NO-INPUT", pruned=True,
                                          note="a constituent series or the target is unavailable"))
            continue
        build, _mech = REPRESENTATIONS[cell.representation]
        n = min(min(len(c) for c in cols if c is not None), len(target))
        sig = build([np.asarray(c)[:n] for c in cols])
        tgt = np.asarray(target)[:n]

        if pre_filter_fn is not None:
            pf = pre_filter_fn(np.sign(np.nan_to_num(sig)) * tgt, name=cell.cell_id)
            if not pf.get("pass", True):
                # STILL A TRIAL. Charged to the budget above; only compute was saved.
                res.results.append(CellResult(cell.cell_id, "PRE-FILTER-REJECT", pruned=True,
                                              note=str(pf.get("reason", ""))[:160]))
                continue
        if screen is None:
            res.results.append(CellResult(cell.cell_id, "UNSCREENED", pruned=True,
                                          note="no screen function supplied"))
            continue
        out = screen(sig, tgt, name=cell.cell_id, horizon_days=float(cell.horizon_days))
        verdict = str(out.get("verdict", "?"))
        r = CellResult(cell.cell_id, verdict,
                       ic=_maybe_float(out.get("ic")), sharpe=_maybe_float(out.get("sharpe")))
        res.results.append(r)
        if verdict == EARNING_VERDICT:
            res.survivors.append(cell.cell_id)
    return res


def _maybe_float(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
