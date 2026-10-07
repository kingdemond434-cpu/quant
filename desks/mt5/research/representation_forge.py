"""THE REPRESENTATION FORGE -- a dataset is never one feature, and the ROI of each one is tracked.

THE PRINCIPAL, 2026-09-17: *representation invention mints new features from ingested series and
tracks their ROI.* Between the ingestion ledger and the candidate compiler the desk had nothing:
every ingested series reached the docket as at most its own level, so a monthly print's SURPRISE
against a matched-day expectation, its PACE against the period elapsed, its z against its own
prior dispersion, the REVISION between two vintages, and the ratio or product it forms with a
second dataset -- five to eight real features per series -- were never built, never tested, and
therefore never credited or refuted.

WHAT THIS ORGAN DOES. Reads every PIT series the desk holds (the axes, FRED, the country data
planes, whatever the collectors last wrote), mints representations with
`libs/research/representations` (pure, typed, testable without a desk), stores each one with its
PIT stamps carried from its inputs, and registers it in the canonical registry's `representations`
table where its ROI accrues: how many candidates used it, how many survived, how many forward
rows it reached, what the world model's drop-one refit says it explained, and what live
attribution -- when there is any -- credits it with. The world model reads the store as INPUTS,
which is what closes the loop: a representation that explains residual variance is a
representation that earns next hour's compute.

INVENTION IS BUDGETED, NOT ENUMERATED. The grammar composes two transforms into a third, so the
space is far larger than an hour. `rank_proposals` orders every proposal by NOVELTY (distance to
the representation ids that already exist) times EXPECTED VALUE (Laplace-smoothed candidates per
use for that transform family, prior 0.25 -- an untried family neither outranks a measured one
nor is extinguished before its first trial), and the pass takes the top `--max-new`. The same
tree and the same history select the same representations, so the ROI series is comparable across
hours rather than being a different sample every pass.

EVERY REPRESENTATION IS POINT-IN-TIME BY CONSTRUCTION. A value stamped `available_time = t` is
computed only from inputs whose own availability is <= t: expanding statistics use the STRICT
prefix, `lead_lag` refuses a negative lag, and a cross-dataset interaction joins as-of. That is
enforced in the library, tested there, and re-asserted here on what is actually written --
because a forged feature that peeks is a leak in the CONDITIONING variable, where the return
series stays spotless and every ordinary leak check passes (R0316's class).

UNMEASURED IS A VALUE. A series too short to carry a prior, a transform that produced no points,
a family with no ROI history yet -- each is named in the report with what would measure it.

    python desks/mt5/research/representation_forge.py [--once] [--budget-s 900] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# IMPORTED PACKAGE-QUALIFIED FIRST, AND THE REASON IS NOT STYLE. `import world_model` and
# `from research import world_model` produce TWO DISTINCT MODULE OBJECTS with separate globals:
# a test (or another organ) that repoints `research.world_model.STORE` would leave this module
# reading the real desk's store, and the two would silently disagree about where the residuals
# are. One spelling, everywhere, so there is one module.
try:
    from research import world_model as WM
except ImportError:                                                          # pragma: no cover
    import world_model as WM  # type: ignore[no-redef]

from libs.research import representations as R  # noqa: E402

STORE = DESK / "data" / "representations"
MANIFEST = STORE / "manifest.json"
DONATIONS = DESK / "data" / "intelligence" / "representation_forge"
OUT = DESK / "reports" / "REPRESENTATION_FORGE.json"

#: The single-input transforms every admissible series is offered, in a fixed order so a pass is
#: reproducible. Two-input transforms are proposed only over dataset PAIRS (below).
BASE_TRANSFORMS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("zscore", {"window": 0}),
    ("zscore", {"window": 260}),
    ("surprise", {"control": "weekday"}),
    ("surprise", {"control": "month"}),
    ("seasonal_expectation", {"cycle": "month"}),
    ("pace", {"cycle": "month"}),
    ("diff", {"lag": 1}),
    ("diff", {"lag": 5}),
    ("acceleration", {"lag": 1}),
    ("lead_lag", {"lag": 1}),
    ("lead_lag", {"lag": 5}),
    ("rank_percentile", {"window": 0}),
    ("rolling_volatility", {"window": 20}),
    ("spectral_state", {"window": 32}),
    ("vintage_revision", {}),
    # DATA-33: breaks (statistic, flag and the age of the last flagged break), the AR(1)
    # half-life, and the residual against the series' own-lag expectation.
    ("structural_break", {"window": 60, "output": "stat"}),
    ("structural_break", {"window": 60, "output": "flag"}),
    ("structural_break", {"window": 60, "output": "age"}),
    ("half_life", {"window": 120}),
    ("ar_residual", {"window": 0}),
)
#: The compositions the grammar is allowed to mint: (inner, outer). Held short on purpose -- the
#: space is combinatorial and the budget is an hour on a box that also holds a live terminal.
COMPOSITIONS: tuple[tuple[str, str], ...] = (
    ("surprise", "zscore"), ("diff", "zscore"), ("surprise", "rank_percentile"),
    ("pace", "zscore"), ("diff", "rolling_volatility"), ("vintage_revision", "zscore"),
    ("seasonal_expectation", "diff"), ("lead_lag", "zscore"),
    ("ar_residual", "zscore"), ("structural_break", "diff"),
)
INTERACTIONS: tuple[str, ...] = ("ratio", "product")
#: Two-input transforms proposed over dataset PAIRS, with the parameters the plan asks for.
#: `cross_country_spread` derives its pairing INSIDE the transform, from the region each series
#: was declared with -- there is no country list here and there must never be one: a pair table
#: in this file would have to be edited for every newly ingested country, and the pairs nobody
#: remembered would silently never be built.
PAIR_TRANSFORMS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("ratio", {}),
    ("product", {}),
    ("cross_country_spread", {"mode": "difference"}),
    ("rolling_beta", {"window": 60}),
)
#: PANEL transforms: breadth and a learned coordinate are properties of a PANEL, not of a pair,
#: so they are proposed once per pass over the admissible series (bounded -- the embedding fits
#: a covariance whose width is the panel, and an unbounded panel would spend the hour on it).
PANEL_TRANSFORMS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("diffusion", {"window": 12}),
    ("embedding", {"window": 120, "components": 2, "component": 0}),
    ("embedding", {"window": 120, "components": 2, "component": 1}),
)
MAX_PANEL = 6

MIN_POINTS = 24
MAX_NEW = 60
MAX_PAIRS = 24
MAX_SERIES = 160
#: Proposals ranked per pass. The grammar offers thousands; ranking them all is the cheap part
#: and minting them is not, but an unbounded plan still costs a pass its budget in scoring alone.
MAX_PROPOSALS = 4_000
MAX_DONATIONS = 15

# ---------------------------------------------------------------------------- DATA-33: control
#: A representation whose values are this well explained (R^2, with an intercept) by what the
#: pass already kept for the same input is a re-labelled copy of them, not a new feature.
MAX_R2 = 0.90
#: The information gain a kept representation must add, in nats, per unit of marginal effective
#: trial it costs (floored at a tenth of a trial so a near-clone is still asked for SOME gain).
MIN_GAIN_NATS = 0.005
MIN_CONTROL_ROWS = 30
MAX_CONTROL_ROWS = 1_500
MAX_BASIS = 12
#: NO TRIAL IS CHARGED HERE (principal, 2026-10-07: never inflated, extra or lifetime trial
#: penalties; trial counts stay as originally set). A representation is an INPUT, not a tested
#: cell: the trial is charged once, on the cell that uses it, by the judge. The forge reports how
#: many new representations it kept and writes nothing to any trial ledger.

# ---------------------------------------------------------------------------- DATA-45: vintages
#: The desk's existing revision log (`libs/research/vintage`, `data/vintages/` at the repo root).
VINTAGE_ROOT = ROOT
#: Every input series' tail is recorded into that log under this prefix each pass, so a series a
#: collector overwrites in place still keeps every vintage the desk saw.
VINTAGE_PREFIX = "forge."
VINTAGE_RECORD_TAIL = 64
MAX_VINTAGE_SERIES = 120
MIN_VINTAGE_POINTS = MIN_POINTS
#: Explicit equivalence classes: series ids from DIFFERENT sources that measure one quantity.
EQUIVALENCE = DESK / "data" / "series_equivalence.json"

# ---------------------------------------------------------------------------- DATA-48: graph/ROI
CAUSAL_GRAPH = DESK / "data" / "world_causal_graph.json"
ASIA_TRANSMISSION = DESK / "reports" / "ASIA_TRANSMISSION.json"
#: Append-only: every negative link outcome ever seen. Nothing here ever removes a row.
LINK_OUTCOMES = STORE / "link_outcomes.jsonl"
RESEARCH_ROI = DESK / "reports" / "RESEARCH_ROI.json"
ROI_HISTORY = STORE / "source_roi_history.jsonl"
#: Declared falsifiers, {source_id: {"falsifier": name, "evidence": text, "arrived_at": iso}}.
FALSIFIERS = DESK / "data" / "source_falsifiers.json"
MAX_HOPS = 6
NEGATIVE_OUTCOMES = frozenset({"RECORDED_NOT_ADMITTED", "REFUTED", "NO_EDGE"})
LIFECYCLE_RANK = {"ACTIVE": 0, "DECAYING": 1, "RETIRED_WITH_FALSIFIER": 2}
MIN_LIFECYCLE_READINGS = 3
MIN_RETIRE_READINGS = 6
ROI_HEARTBEAT_S = 86_400.0
RULE =("every ingested series becomes many features, each PIT-stamped, id'd, stored and "
        "credited by what it goes on to earn")


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:
        path.chmod(0o644)
        os.replace(tmp, path)


def dataset_key(series: R.Series) -> str:
    """The id component that identifies WHICH series a representation was built from.

    MEASURED ON THE REAL TREE 2026-09-17: the first build used the series' `dataset` LABEL here,
    and one axis file carries 66 series under the single label `axis:bis`. Every one of them
    produced the id `repr:axis_bis:zscore:window=0`, so 56 minted representations collapsed to 46
    in a store keyed by id -- ten features silently overwriting each other, each one a different
    country's policy rate. The dataset label is still carried (`source_dataset`) and is still what
    ROI groups by; the ID has to name the series, or the store cannot hold the desk's own inputs.
    """
    return str(series.series_id).replace(":", ".")


def _file_name(representation_id: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in representation_id)
    return f"{safe[:120]}.json"


# ---------------------------------------------------------------------------- history and budget
def roi_history() -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    """Per transform FAMILY, what it has earned -- from the registry, never from this file.

    A family with no row yet is ABSENT here rather than zero, which is what makes
    `expected_value` fall back to its prior instead of extinguishing a family nobody has tried.
    """
    history: dict[str, dict[str, float]] = {}
    status: dict[str, Any] = {"source": "registry.representations"}
    try:
        from libs.moat import registry as reg

        rows = reg.representations(limit=5000)
    except Exception as exc:
        return {}, {"source": "UNMEASURED",
                    "why": f"registry unreadable: {type(exc).__name__}",
                    "measured_by": "libs/moat/registry.py representations table"}
    for row in rows:
        family = str(row.get("family") or "unknown")
        bucket = history.setdefault(family, {"uses": 0.0, "candidates": 0.0, "survivors": 0.0,
                                             "forward_rows": 0.0, "explained": 0.0, "n": 0.0})
        bucket["n"] += 1.0
        bucket["uses"] += float(row.get("used_by_candidates") or 0.0)
        bucket["candidates"] += float(row.get("used_by_candidates") or 0.0)
        bucket["survivors"] += float(row.get("survivors") or 0.0)
        bucket["forward_rows"] += float(row.get("forward_rows") or 0.0)
        bucket["explained"] += float(row.get("explained_variance") or 0.0)
    status["families"] = len(history)
    status["rows"] = len(rows)
    return history, status


def world_model_credit() -> dict[str, float]:
    """What the world model's drop-one refit says each representation FAMILY explained.

    This is the ROI signal that arrives without a candidate ever being minted: a feature that
    raises out-of-sample R2 has earned its compute whether or not a family has yet been built on
    it, and crediting only survivors would starve exactly the representations that are working.
    """
    doc = _read_json(WM.OUT)
    if not isinstance(doc, dict):
        return {}
    out: dict[str, float] = {}
    for dataset, row in (doc.get("dataset_credit") or {}).items():
        if not str(dataset).startswith("representation:"):
            continue
        family = str(dataset).split(":", 1)[1]
        try:
            out[family] = float(row.get("mean_delta_r2") or 0.0)
        except (TypeError, ValueError, AttributeError):
            continue
    return out


def existing_manifest() -> dict[str, dict[str, Any]]:
    doc = _read_json(MANIFEST)
    rows = doc.get("representations") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return {}
    return {str(r["id"]): r for r in rows if isinstance(r, dict) and r.get("id")}


# ---------------------------------------------------------------------------- the proposals
def propose(series: list[R.Series], existing: set[str], history: dict[str, dict[str, float]],
            *, budget: int = MAX_NEW, max_pairs: int = MAX_PAIRS,
            causal: CausalIndex | None = None, lifecycles: dict[str, Any] | None = None,
            extra: list[dict[str, Any]] | None = None
            ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Every representation the grammar offers over these series, ranked and cut to the budget.

    Returns (selected, plan) -- the plan carries the id, the transform chain, the series it reads
    and the two scores, so the report can say what was NOT minted this hour and why it lost.
    """
    plan: list[dict[str, Any]] = []
    for one in series:
        if len(one.points) < MIN_POINTS:
            continue
        key = dataset_key(one)
        for name, params in BASE_TRANSFORMS:
            transform = R.Transform(name=name, params=params)
            rid = R.representation_id(key, transform.label,
                                      {**dict(R.TRANSFORMS[name].defaults), **params})
            plan.append({"id": rid, "family": transform.family, "chain": [name],
                         "params": params, "inputs": [one.series_id], "arity": 1})
        for inner_name, outer_name in COMPOSITIONS:
            inner = R.Transform(name=inner_name, params=dict(R.TRANSFORMS[inner_name].defaults))
            outer = R.compose(R.Transform(name=outer_name,
                                          params=dict(R.TRANSFORMS[outer_name].defaults)), inner)
            rid = R.representation_id(key, outer.label,
                                      dict(R.TRANSFORMS[outer_name].defaults))
            plan.append({"id": rid, "family": outer.family, "chain": [inner_name, outer_name],
                         "params": dict(R.TRANSFORMS[outer_name].defaults),
                         "inputs": [one.series_id], "arity": 1, "composed": True})

    # PAIRS IN CAUSAL ORDER (DATA-48). Every admissible pair is enumerated, then ordered by hop
    # distance between the two series' anchors on the causal graph (an unanchored or unreachable
    # pair goes last, never dropped), then by the worse source lifecycle state of the two, then by
    # the old enumeration order -- so the MAX_PAIRS cut keeps the causally closest pairs rather
    # than whichever came first alphabetically.
    lifecycles = lifecycles or {}
    rank_of = {s.series_id: series_lifecycle_rank(s, lifecycles) for s in series} \
        if lifecycles else {}
    candidates: list[tuple[tuple[int, int, int], R.Series, R.Series, dict[str, Any]]] = []
    for i, left in enumerate(series):
        for right in series[i + 1:]:
            if left.dataset == right.dataset or len(left.points) < MIN_POINTS \
                    or len(right.points) < MIN_POINTS:
                continue
            link: dict[str, Any] = causal.pair(left, right) if causal is not None else \
                {"distance": None, "refuted_links": 0, "refuted_strength": 0.0}
            dist = link["distance"]
            pair_key: tuple[int, int, int] = (
                int(dist) if dist is not None else MAX_HOPS + 1,
                max(rank_of.get(left.series_id, 0), rank_of.get(right.series_id, 0)),
                len(candidates))
            candidates.append((pair_key, left, right, link))
    candidates.sort(key=lambda c: c[0])
    for rank_key, left, right, link in candidates[:max_pairs]:
        for name, params in PAIR_TRANSFORMS:
            transform = R.Transform(name=name, params=params)
            merged = {**dict(R.TRANSFORMS[name].defaults), **params}
            rid = R.representation_id(f"{dataset_key(left)}x{dataset_key(right)}", name, merged)
            plan.append({"id": rid, "family": transform.family, "chain": [name],
                         "params": params, "inputs": [left.series_id, right.series_id],
                         "arity": 2, "causal": {**link, "lifecycle_rank": rank_key[1]},
                         "causal_order": rank_key[0]})

    panel = [s for s in series if len(s.points) >= MIN_POINTS][:MAX_PANEL]
    if len(panel) >= 2:
        key = "+".join(dataset_key(s) for s in panel)
        for name, params in PANEL_TRANSFORMS:
            transform = R.Transform(name=name, params=params)
            merged = {**dict(R.TRANSFORMS[name].defaults), **params}
            plan.append({"id": R.representation_id(key, name, merged), "family": transform.family,
                         "chain": [name], "params": params,
                         "inputs": [s.series_id for s in panel], "arity": 2, "panel": True})

    plan.extend(extra or [])
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in plan:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        unique.append(row)
    unique = unique[:MAX_PROPOSALS]
    ranked = R.rank_proposals([(r["id"], r["family"]) for r in unique], existing, history,
                              budget=len(unique))
    order = {str(r["id"]): r for r in ranked}
    for row in unique:
        score = order.get(row["id"], {})
        row["novelty"] = score.get("novelty")
        row["expected_value"] = score.get("expected_value")
        row["score"] = score.get("score", 0.0)
    unique.sort(key=lambda r: (-float(r.get("score") or 0.0), int(r.get("causal_order") or 0),
                               str(r["id"])))
    return diverse(unique, budget), unique


def diverse(ranked: list[dict[str, Any]], budget: int) -> list[dict[str, Any]]:
    """The budget cut, with every family that has a proposal guaranteed a share of it.

    Ties on score break on the id, and ids sort by dataset: cut naively, a family whose ids sort
    late (`repr:vint...`, `repr:link_outcomes...`) would never be minted however many hours the
    forge ran. Each family first takes up to ceil(budget / families) of its own best-ranked rows;
    what is left of the budget goes in plain rank order. Deterministic, like the ranking."""
    if budget <= 0:
        return []
    families = sorted({str(r.get("family")) for r in ranked})
    if not families:
        return []
    quota = -(-budget // len(families))
    taken: dict[str, int] = {}
    chosen: set[str] = set()
    for row in ranked:
        fam = str(row.get("family"))
        if taken.get(fam, 0) < quota and len(chosen) < budget:
            taken[fam] = taken.get(fam, 0) + 1
            chosen.add(str(row["id"]))
    for row in ranked:
        if len(chosen) >= budget:
            break
        chosen.add(str(row["id"]))
    return [r for r in ranked if str(r["id"]) in chosen]


def mint(row: dict[str, Any], by_id: dict[str, R.Series],
         prebuilt: dict[str, R.Series] | None = None) -> R.Series | None:
    """Build one proposed representation, or None when its inputs cannot support it.

    The inputs are RELABELLED onto their own `dataset_key` first, so the id the library stamps is
    the id the plan proposed -- one representation per series, not one per dataset label. A
    PREBUILT row (a vintage revision, a cross-source disagreement, a latent link-outcome series)
    was built from the store before ranking and is returned as built.
    """
    if row.get("prebuilt"):
        built = (prebuilt or {}).get(str(row["id"]))
        return built if built is not None and len(built.points) >= MIN_POINTS else None
    found = [by_id.get(sid) for sid in row["inputs"]]
    if any(s is None for s in found):
        return None
    inputs = [s.__class__(series_id=s.series_id, points=s.points, dataset=dataset_key(s),
                          region=s.region, information_type=s.information_type)
              for s in found if s is not None]
    chain = list(row["chain"])
    if row["arity"] == 2:
        transform = R.Transform(name=chain[0], params=dict(row["params"]))
    elif len(chain) == 2:
        inner = R.Transform(name=chain[0], params=dict(R.TRANSFORMS[chain[0]].defaults))
        transform = R.compose(R.Transform(name=chain[1], params=dict(row["params"])), inner)
    else:
        transform = R.Transform(name=chain[0], params=dict(row["params"]))
    try:
        built = R.apply(transform, *[s for s in inputs if s is not None])
    except (ValueError, KeyError, ZeroDivisionError):
        return None
    return built if len(built.points) >= MIN_POINTS else None


# ---------------------------------------------------------------------------- DATA-33: control
def _asof(series: R.Series, times: list[str]) -> list[float | None]:
    """The newest value of `series` knowable at each of `times` (ascending): a merge-scan as-of."""
    pts = series.sorted().points
    out: list[float | None] = []
    j = 0
    cur: float | None = None
    for t in times:
        while j < len(pts) and pts[j].available_time <= t:
            if R._finite(pts[j].value):
                cur = float(pts[j].value)
            j += 1
        out.append(cur)
    return out


def _forward_change(series: R.Series, times: list[str]) -> list[float | None]:
    """The control TARGET: the input's next value after t minus its value knowable at t.

    This is the label the gain is measured against, and only the label looks forward; every
    feature column is joined as-of, so no column at t reads a value later than t."""
    pts = [p for p in series.sorted().points if R._finite(p.value)]
    out: list[float | None] = []
    j = 0
    cur: float | None = None
    for t in times:
        while j < len(pts) and pts[j].available_time <= t:
            cur = float(pts[j].value)
            j += 1
        out.append(None if cur is None or j >= len(pts) else float(pts[j].value) - cur)
    return out


def _r2(y: Any, x: Any) -> float:
    """R^2 of y on [1, x] by least squares; NaN when y has no variance to explain."""
    import numpy as np

    yv = np.asarray(y, dtype=float)
    sst = float(np.sum((yv - yv.mean()) ** 2))
    if sst <= 1e-18:
        return float("nan")
    cols = [np.ones(len(yv))] + ([] if x is None else [np.asarray(c, dtype=float) for c in x])
    design = np.column_stack(cols)
    beta, *_ = np.linalg.lstsq(design, yv, rcond=None)
    ssr = float(np.sum((yv - design @ beta) ** 2))
    return max(0.0, min(1.0, 1.0 - ssr / sst))


def _trial(record_like: dict[str, Any]) -> Any:
    from libs.research import trial_ledger as tl

    return tl.Trial(trial_id=str(record_like["id"]),
                    family=f"representation:{record_like.get('family') or 'unknown'}",
                    descriptors={"transform": str(record_like.get("transform") or ""),
                                 "dataset": str(record_like.get("source_dataset") or ""),
                                 "region": str(record_like.get("region") or ""),
                                 "input": str((record_like.get("inputs") or [""])[0])},
                    params={k: v for k, v in dict(record_like.get("params") or {}).items()
                            if isinstance(v, (int, float, str))})


def _n_effective(trials: list[Any]) -> float:
    if not trials:
        return 0.0
    from libs.research import trial_ledger as tl

    return float(tl.census(trials).n_effective)


def control(candidate: R.Series, primary: R.Series | None, basis: list[R.Series],
            marginal_trials: float) -> dict[str, Any]:
    """Keep a representation only if it adds INFORMATION and is not a copy of what was kept.

    Three tests, in the order they are cheap:

      orthogonality   R^2 of the candidate on the representations already kept this pass for
                      the same input; >= MAX_R2 is near-collinear and refused (the level itself
                      is not in the basis: it is already a world-model input, and a transform
                      that is affine in it is still a different FEATURE for a family);
      information     the partial R^2 it adds for the input's forward change, net of the
                      expected partial R^2 of pure noise (1 / (n - k - 1)), as Gaussian mutual
                      information -0.5 ln(1 - partial), in nats;
      trial cost      that gain must reach MIN_GAIN_NATS per marginal EFFECTIVE trial (the
                      participation-ratio increment `trial_ledger.census` charges for adding it).

    UNMEASURED IS NOT ZERO. Fewer than MIN_CONTROL_ROWS aligned rows, or no input to measure a
    gain against, reads UNMEASURED and the representation is ADMITTED -- the control could not be
    run, which is different from the representation having failed it.
    """
    import math

    import numpy as np

    times = [p.available_time for p in candidate.sorted().points][-MAX_CONTROL_ROWS:]
    cand = _asof(candidate, times)
    cols = [_asof(b, times) for b in basis[-MAX_BASIS:]]
    target = _forward_change(primary, times) if primary is not None else [None] * len(times)
    out: dict[str, Any] = {"marginal_effective_trials": round(marginal_trials, 4),
                           "basis": len(cols), "max_r2": MAX_R2, "min_gain_nats": MIN_GAIN_NATS}
    keep = [i for i in range(len(times))
            if cand[i] is not None and all(c[i] is not None for c in cols)]
    if len(keep) < MIN_CONTROL_ROWS:
        out.update({"status": "UNMEASURED", "admit": True, "n": len(keep),
                    "why": f"{len(keep)} aligned rows < {MIN_CONTROL_ROWS}",
                    "measured_by": "a longer overlap between the representation and its input"})
        return out
    c = np.asarray([cand[i] for i in keep], dtype=float)
    x = [np.asarray([col[i] for i in keep], dtype=float) for col in cols]
    collinear = _r2(c, x) if x else 0.0
    if not math.isfinite(collinear):
        collinear = 1.0                       # a constant carries nothing the intercept lacks
    out["collinear_r2"] = round(collinear, 6)
    out["n"] = len(keep)
    if collinear >= MAX_R2:
        out.update({"status": "REFUSED_COLLINEAR", "admit": False,
                    "why": f"R2={collinear:.3f} on already-kept representations >= {MAX_R2}"})
        return out
    rows = [j for j, i in enumerate(keep) if target[i] is not None]
    if len(rows) < MIN_CONTROL_ROWS:
        out.update({"status": "UNMEASURED", "admit": True,
                    "why": "no forward change of an input to measure a gain against",
                    "measured_by": "a primary input series that keeps printing"})
        return out
    y = np.asarray([target[keep[j]] for j in rows], dtype=float)
    xs = [col[rows] for col in x]
    base = _r2(y, xs) if xs else 0.0
    full = _r2(y, [*xs, c[rows]])
    if not (math.isfinite(base) and math.isfinite(full)):
        out.update({"status": "UNMEASURED", "admit": True,
                    "why": "the input's forward change has no variance on these rows",
                    "measured_by": "a non-constant input"})
        return out
    partial = (full - base) / (1.0 - base) if base < 1.0 else 0.0
    k = len(xs) + 1
    excess = max(0.0, partial - 1.0 / max(1, len(rows) - k - 1))
    gain = -0.5 * math.log(max(1e-12, 1.0 - min(excess, 0.999999)))
    required = MIN_GAIN_NATS * max(marginal_trials, 0.1)
    out.update({"partial_r2": round(partial, 6), "information_gain_nats": round(gain, 6),
                "required_nats": round(required, 6)})
    if gain < required:
        out.update({"status": "REFUSED_NO_GAIN", "admit": False,
                    "why": f"gain {gain:.5f} nats < {required:.5f} for "
                           f"{marginal_trials:.2f} marginal effective trial(s)"})
        return out
    out.update({"status": "ADMITTED", "admit": True})
    return out


def stored_basis(input_key: str, manifest: dict[str, dict[str, Any]],
                 cache: dict[str, list[R.Series]]) -> list[R.Series]:
    """The representations ALREADY IN THE STORE for one input, read back from their files.

    The orthogonality test runs against these as well as against this pass's keeps, so the
    control is the same whichever order a pass happens to rank proposals in: a candidate refused
    as a copy of a stored feature this hour is refused next hour too, and the store does not
    accumulate one collinear twin per pass."""
    if input_key not in cache:
        found: list[R.Series] = []
        for rid, row in sorted(manifest.items()):
            if str((row.get("inputs") or [""])[0]) != input_key or not row.get("file"):
                continue
            doc = _read_json(STORE / str(row["file"]))
            pts = doc.get("points") if isinstance(doc, dict) else None
            if not isinstance(pts, list):
                continue
            points = tuple(R.Point(available_time=str(p.get("available_time")),
                                   period_time=str(p.get("period_time")),
                                   value=float(p.get("value")))
                           for p in pts if isinstance(p, dict)
                           and isinstance(p.get("value"), (int, float)))
            if points:
                found.append(R.Series(series_id=rid, points=points))
            if len(found) >= MAX_BASIS:
                break
        cache[input_key] = found
    return cache[input_key]


def count_new(new_records: list[dict[str, Any]], n_effective: float) -> dict[str, Any]:
    """How many representations this pass kept for the first time, by family. A report only:
    nothing is written to a trial ledger (see the note above `VINTAGE_ROOT`)."""
    by_family: dict[str, int] = {}
    for row in new_records:
        fam = f"representation:{row.get('family') or 'unknown'}"
        by_family[fam] = by_family.get(fam, 0) + 1
    return {"new": len(new_records), "by_family": by_family,
            "n_effective": round(n_effective, 3), "trials_charged": 0,
            "why": "an input, not a tested cell: the judge charges the cell that uses it, once"}


# ---------------------------------------------------------------------------- DATA-45: vintages
def record_input_vintages(series: list[R.Series], *, dry_run: bool) -> dict[str, Any]:
    """Append each input's newest points to the revision log, stamped at THIS pass.

    `vintage.record` appends only a NEW or CHANGED (target, value), so an unchanged input costs
    nothing and a collector that overwrites its file in place no longer destroys the value it
    replaced. The vintage is the desk's clock (when we saw it), never the source's."""
    from libs.research import vintage as V

    if dry_run:
        return {"status": "SKIPPED_DRY_RUN", "series": len(series)}
    stamp = now_iso()
    written = 0
    for one in series[:MAX_SERIES]:
        tail = one.sorted().points[-VINTAGE_RECORD_TAIL:]
        obs = {p.period_time: float(p.value) for p in tail if R._finite(p.value)}
        if obs:
            written += V.record(VINTAGE_ROOT, f"{VINTAGE_PREFIX}{one.series_id}", obs,
                                vintage=stamp)
    return {"status": "RECORDED", "series": min(len(series), MAX_SERIES), "rows": written,
            "store": str(VINTAGE_ROOT / V.STORE_DIR)}


def _aggregate(rows: list[dict[str, Any]], key: str) -> tuple[R.Point, ...]:
    """One point per vintage instant: the mean across targets revised at that instant."""
    grouped: dict[str, list[float]] = {}
    nearest: dict[str, str] = {}
    for row in rows:
        grouped.setdefault(str(row["vintage"]), []).append(float(row[key]))
        nearest.setdefault(str(row["vintage"]), str(row["target"]))
    return tuple(R.Point(available_time=v, period_time=nearest[v],
                         value=sum(vals) / len(vals), vintage_id=v)
                 for v, vals in sorted(grouped.items(), key=lambda kv: kv[0]))


def vintage_candidates(by_id: dict[str, R.Series]) -> tuple[list[tuple[dict[str, Any], R.Series]],
                                                            list[dict[str, str]]]:
    """Forecast-vintage revision and revision-momentum representations at 1h/6h/1d/3d."""
    from libs.research import vintage as V

    out: list[tuple[dict[str, Any], R.Series]] = []
    unmeasured: list[dict[str, str]] = []
    names = V.log_series_names(VINTAGE_ROOT)[:MAX_VINTAGE_SERIES]
    if not names:
        unmeasured.append({"name": "forecast_vintages",
                           "why": "no revision log under data/vintages",
                           "measured_by": "a pass that records input vintages (this leg)"})
    for stem in names:
        rows = V.read_log(VINTAGE_ROOT, stem)
        # The file name is sanitised; the rows carry the series name as it was recorded.
        name = str(rows[0].get("series") or stem) if rows else stem
        origin = name[len(VINTAGE_PREFIX):] if name.startswith(VINTAGE_PREFIX) else name
        primary = by_id.get(origin)
        key = f"vint.{origin.replace(':', '.')}"
        for lag, seconds in V.FORECAST_LAGS_S.items():
            for kind, rows_out, field in (
                    ("forecast_revision", V.forecast_revisions(rows, seconds), "revision"),
                    ("revision_momentum", V.revision_momentum(rows, seconds), "momentum")):
                points = _aggregate(rows_out, field)
                rid = R.representation_id(key, kind, {"lag": lag})
                if len(points) < MIN_VINTAGE_POINTS:
                    unmeasured.append({"name": rid,
                                       "why": f"{len(points)} revision instants < "
                                              f"{MIN_VINTAGE_POINTS}",
                                       "measured_by": "more recorded vintages of this series"})
                    continue
                built = R.Series(series_id=rid, points=points, dataset=key,
                                 region=primary.region if primary is not None else "",
                                 information_type="forecast_vintage")
                out.append(({"id": rid, "family": "vintage", "chain": [kind],
                             "params": {"lag": lag}, "inputs": [origin], "arity": 1,
                             "prebuilt": True, "source_dataset": key}, built))
    return out, unmeasured


def disagreement_candidates(by_id: dict[str, R.Series]
                            ) -> tuple[list[tuple[dict[str, Any], R.Series]], dict[str, Any]]:
    """Cross-source disagreement over the declared equivalence classes: spread, its z, and the
    first member conditioned on the disagreement state."""
    doc = _read_json(EQUIVALENCE)
    classes = doc.get("classes") if isinstance(doc, dict) else None
    status: dict[str, Any] = {"mapping": str(EQUIVALENCE), "classes": 0, "pairs": 0,
                              "absent_members": []}
    out: list[tuple[dict[str, Any], R.Series]] = []
    if not isinstance(classes, dict):
        status["status"] = "UNMEASURED"
        status["why"] = "no equivalence mapping (no equivalence classes exist on this base)"
        return out, status
    status["status"] = "MEASURED"
    for name, spec in sorted(classes.items()):
        members = [str(m) for m in (spec.get("members") or [])] if isinstance(spec, dict) else []
        present = [by_id[m] for m in members if m in by_id]
        status["absent_members"].extend(m for m in members if m not in by_id)
        status["classes"] += 1
        for i, left in enumerate(present):
            for right in present[i + 1:]:
                if left.dataset == right.dataset:
                    continue                       # one source twice is not a disagreement
                status["pairs"] += 1
                key = f"agree.{name}.{dataset_key(left)}x{dataset_key(right)}"
                # The same quantity from two sources, joined as-of on availability (a merge
                # scan: the right-hand value is the newest one knowable at the left's stamp).
                spread = R._pairwise(left, right, R._difference, "disagreement")
                spread = R.Series(series_id=key, points=spread.points, dataset=key,
                                  region=left.region, information_type="disagreement")
                built = {
                    "spread": spread,
                    "spread_z": R.zscore(spread, window=260),
                    "conditioned": R.regime_conditioned(left, spread, buckets=3),
                }
                for kind, series in built.items():
                    rid = R.representation_id(key, f"disagreement_{kind}", {})
                    out.append(({"id": rid, "family": "disagreement",
                                 "chain": [f"disagreement_{kind}"], "params": {"class": name},
                                 "inputs": [left.series_id, right.series_id], "arity": 2,
                                 "prebuilt": True, "source_dataset": key},
                                R.Series(series_id=rid, points=series.points, dataset=key,
                                         region=left.region, information_type="disagreement")))
    status["absent_members"] = status["absent_members"][:20]
    return out, status


# ---------------------------------------------------------------------------- DATA-48: graph
def _tokens(series: R.Series) -> tuple[set[str], str]:
    text = f"{series.series_id} {series.dataset}".upper()
    flat = "".join(ch if ch.isalnum() else "_" for ch in text)
    toks = {t for t in flat.split("_") if t}
    for t in list(toks):
        if len(t) == 6 and t.isalpha():
            toks.update({t[:3], t[3:]})
    if series.region:
        toks.add(series.region.upper())
    return toks, f"_{flat}_"


class CausalIndex:
    """Hop distances between the series' anchor nodes on the desk's causal graph, plus every
    negative link outcome between them as a latent input.

    A series is ANCHORED to the graph nodes its own id names: an MT5 symbol, the two currencies
    of a six-letter FX symbol, a commodity or index name, or its declared region's country and
    central bank. Proximity is the shortest undirected path over edges that are not negative
    outcomes; a refuted edge does not make two series close -- it is recorded as LATENT
    knowledge on the pair instead, and is never deleted."""

    def __init__(self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]],
                 negatives: list[dict[str, Any]], basis: str) -> None:
        self.basis = basis
        self.keys: dict[str, set[str]] = {}
        for node in nodes:
            nid = str(node.get("id") or "")
            if not nid:
                continue
            kind = str(node.get("kind") or "")
            names = {nid.split(":", 1)[-1].upper()}
            if kind in ("country", "central_bank") and node.get("country"):
                names.add(str(node["country"]).upper())
            for nm in names:
                self.keys.setdefault(nm, set()).add(nid)
        self.adj: dict[str, set[str]] = {}
        for e in edges:
            if str(e.get("status") or "") in NEGATIVE_OUTCOMES:
                continue
            a, b = str(e.get("src") or ""), str(e.get("dst") or "")
            if a and b:
                self.adj.setdefault(a, set()).add(b)
                self.adj.setdefault(b, set()).add(a)
        self.negatives = negatives
        self._anchors: dict[str, frozenset[str]] = {}
        self._dist: dict[str, dict[str, int]] = {}

    def anchors(self, series: R.Series) -> frozenset[str]:
        if series.series_id not in self._anchors:
            toks, flat = _tokens(series)
            found: set[str] = set()
            for key, nids in self.keys.items():
                if key in toks or ("_" in key and f"_{key}_" in flat):
                    found |= nids
            self._anchors[series.series_id] = frozenset(found)
        return self._anchors[series.series_id]

    def _bfs(self, series: R.Series) -> dict[str, int]:
        if series.series_id not in self._dist:
            dist = dict.fromkeys(self.anchors(series), 0)
            frontier = list(dist)
            for hop in range(1, MAX_HOPS + 1):
                nxt: list[str] = []
                for node in frontier:
                    for nb in self.adj.get(node, ()):
                        if nb not in dist:
                            dist[nb] = hop
                            nxt.append(nb)
                frontier = nxt
                if not frontier:
                    break
            self._dist[series.series_id] = dist
        return self._dist[series.series_id]

    def pair(self, left: R.Series, right: R.Series) -> dict[str, Any]:
        dist = self._bfs(left)
        hops = [dist[n] for n in self.anchors(right) if n in dist]
        la, ra = self.anchors(left), self.anchors(right)
        refuted = [r for r in self.negatives
                   if (r.get("src") in la and r.get("dst") in ra)
                   or (r.get("src") in ra and r.get("dst") in la)]
        return {"distance": min(hops) if hops else None,
                "refuted_links": len(refuted),
                "refuted_strength": round(sum(float(r.get("strength") or 0.0)
                                              for r in refuted), 6)}


def load_graph() -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    """The measured world causal graph when this box has one; the base's seeded priors if not."""
    doc = _read_json(CAUSAL_GRAPH)
    if isinstance(doc, dict) and isinstance(doc.get("edges"), list):
        return list(doc.get("nodes") or []), list(doc["edges"]), str(CAUSAL_GRAPH)
    try:
        from libs.research import causal_graph as cg

        graph = cg.seed_priors(cg.CausalGraph(), cg.instrument_nodes())
        seeded = graph.to_json()
        return (list(seeded.get("nodes") or []), list(seeded.get("edges") or []),
                "causal_graph.PRIOR_EDGES (no measured graph on this box)")
    except Exception as exc:
        return [], [], f"UNMEASURED: no causal graph ({type(exc).__name__})"


def negative_outcomes(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every negative link outcome the graph and the Asian transmission organ currently report."""
    out: list[dict[str, Any]] = []
    for e in edges:
        if str(e.get("status") or "") not in NEGATIVE_OUTCOMES:
            continue
        out.append({"origin": "world_causal_graph", "src": str(e.get("src")),
                    "dst": str(e.get("dst")), "lag": int(e.get("lag") or 0),
                    "outcome": str(e.get("status")), "strength": abs(float(e.get("strength")
                                                                           or 0.0)),
                    "measured_at": str(e.get("measured_at") or ""),
                    "reason": str(e.get("reason") or "")[:200]})
    asia = _read_json(ASIA_TRANSMISSION)
    if isinstance(asia, dict):
        at = str(asia.get("generated_utc") or asia.get("at") or "")
        for row in asia.get("rows") or []:
            if not isinstance(row, dict) or str(row.get("verdict")) not in NEGATIVE_OUTCOMES:
                continue
            raw = row.get("asia_hours")
            leg: dict[str, Any] = raw if isinstance(raw, dict) else {}
            out.append({"origin": "asia_transmission", "src": str(row.get("driver")),
                        "dst": str(row.get("target")), "lag": int(leg.get("lag") or 0),
                        "outcome": str(row.get("verdict")),
                        "strength": abs(float(leg.get("t") or 0.0)),
                        "measured_at": at, "reason": str(row.get("why") or "")[:200]})
    return [r for r in out if r["measured_at"]]


def _outcome_key(row: dict[str, Any]) -> str:
    return "|".join(str(row.get(k)) for k in ("origin", "src", "dst", "lag", "outcome",
                                              "measured_at"))


def persist_outcomes(current: list[dict[str, Any]], *, dry_run: bool
                     ) -> tuple[list[dict[str, Any]], int]:
    """Append the outcomes not yet in the ledger; return (every outcome ever seen, appended).

    APPEND-ONLY BY CONSTRUCTION: a link the graph later re-measures, or an organ that stops
    reporting, never takes a recorded negative out of the ledger -- a refutation is knowledge."""
    seen: list[dict[str, Any]] = []
    try:
        for line in LINK_OUTCOMES.read_text("utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                seen.append(row)
    except OSError:
        pass
    keys = {_outcome_key(r) for r in seen}
    fresh = [r for r in current if _outcome_key(r) not in keys]
    if fresh and not dry_run:
        LINK_OUTCOMES.parent.mkdir(parents=True, exist_ok=True)
        with LINK_OUTCOMES.open("a", encoding="utf-8") as fh:
            for row in fresh:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
    return seen + fresh, len(fresh)


def latent_candidates(outcomes: list[dict[str, Any]]
                      ) -> tuple[list[tuple[dict[str, Any], R.Series]], list[dict[str, str]]]:
    """Negative link outcomes as PIT latent inputs: the cumulative count and strength of refuted
    links, each value stamped at the instant the latest refutation in it was measured."""
    ordered = sorted(outcomes, key=lambda r: str(r.get("measured_at")))
    count_pts: dict[str, R.Point] = {}
    strength_pts: dict[str, R.Point] = {}
    total = 0.0
    for n, row in enumerate(ordered, start=1):
        at = str(row.get("measured_at"))
        total += float(row.get("strength") or 0.0)
        count_pts[at] = R.Point(available_time=at, period_time=at, value=float(n))
        strength_pts[at] = R.Point(available_time=at, period_time=at, value=total)
    out: list[tuple[dict[str, Any], R.Series]] = []
    unmeasured: list[dict[str, str]] = []
    for kind, pts in (("refuted_link_count", count_pts), ("refuted_link_strength", strength_pts)):
        rid = R.representation_id("link_outcomes", kind, {})
        if len(pts) < MIN_POINTS:
            unmeasured.append({"name": rid, "why": f"{len(pts)} measured refutation instants < "
                                                   f"{MIN_POINTS}",
                               "measured_by": "more measured link outcomes in the ledger"})
            continue
        series = R.Series(series_id=rid, points=tuple(pts[k] for k in sorted(pts)),
                          dataset="link_outcomes", region="GLOBAL",
                          information_type="negative_knowledge")
        out.append(({"id": rid, "family": "latent", "chain": [kind], "params": {},
                     "inputs": [], "arity": 1, "prebuilt": True,
                     "source_dataset": "link_outcomes"}, series))
    return out, unmeasured


# ---------------------------------------------------------------------------- DATA-48: lifecycle
def lifecycle(readings: list[dict[str, Any]], declared: dict[str, Any] | None = None
              ) -> dict[str, Any]:
    """ACTIVE, DECAYING or RETIRED_WITH_FALSIFIER, from MEASURED ROI readings only.

    Decay is the ROI half-life: log ROI regressed on time (days) over measured readings; a negative
    slope k gives ln 2 / -k. RETIREMENT NEEDS A NAMED FALSIFIER THAT ARRIVED -- a declared one with
    its evidence, or the computed `roi_collapse_after_three_half_lives` (>= MIN_RETIRE_READINGS
    measured readings, the latest at or below an eighth of the peak, three half-lives after it).
    An UNMEASURED reading, an empty history or a source that stopped reporting never retires
    anything: absence is not evidence (LAWS 7, scripts/check_no_retirement_on_absence.py)."""
    import math

    from libs.research import vintage as V

    measured: list[tuple[float, float]] = []
    unmeasured = 0
    for r in readings:
        stamp = V._stamp(r.get("at"))
        roi = r.get("roi")
        if str(r.get("roi_status") or "MEASURED") != "MEASURED" or stamp is None \
                or not isinstance(roi, (int, float)) or not math.isfinite(float(roi)):
            unmeasured += 1
            continue
        measured.append((stamp / 86_400.0, float(roi)))
    measured.sort()
    out: dict[str, Any] = {"state": "ACTIVE", "measured_readings": len(measured),
                           "unmeasured_readings": unmeasured, "half_life_days": None,
                           "latest_roi": measured[-1][1] if measured else None,
                           "falsifier": None}
    if isinstance(declared, dict) and str(declared.get("falsifier") or "").strip() \
            and str(declared.get("evidence") or "").strip():
        out.update({"state": "RETIRED_WITH_FALSIFIER",
                    "falsifier": {"name": str(declared["falsifier"]),
                                  "evidence": str(declared["evidence"]),
                                  "arrived_at": declared.get("arrived_at"),
                                  "declared": True}})
        return out
    if len(measured) < MIN_LIFECYCLE_READINGS:
        out["why"] = (f"{len(measured)} measured ROI readings < {MIN_LIFECYCLE_READINGS}: no decay "
                      "estimate, and absence never retires")
        return out
    peak_t, peak = max(measured, key=lambda m: (m[1], -m[0]))
    if peak <= 0:
        out["why"] = "no positive ROI measured yet: nothing to decay from"
        return out
    floor = peak * 1e-3
    ts = [m[0] for m in measured]
    ys = [math.log(max(m[1], floor)) for m in measured]
    mt, my = sum(ts) / len(ts), sum(ys) / len(ys)
    sxx = sum((t - mt) ** 2 for t in ts)
    slope = sum((t - mt) * (y - my) for t, y in zip(ts, ys, strict=True)) / sxx if sxx > 0 else 0.0
    out["roi_log_slope_per_day"] = round(slope, 6)
    if slope >= 0:
        out["why"] = "ROI not decaying"
        return out
    hl = math.log(2.0) / -slope
    out["half_life_days"] = round(hl, 3)
    out["state"] = "DECAYING"
    last_t, last = measured[-1]
    if len(measured) >= MIN_RETIRE_READINGS and last <= peak / 8.0 \
            and (last_t - peak_t) >= 3.0 * hl:
        out["state"] = "RETIRED_WITH_FALSIFIER"
        out["falsifier"] = {
            "name": "roi_collapse_after_three_half_lives", "declared": False,
            "evidence": (f"{len(measured)} measured readings; ROI {last:.6g} <= peak "
                         f"{peak:.6g} / 8, {last_t - peak_t:.1f} days after the peak >= 3 x "
                         f"half-life {hl:.2f} days")}
    return out


def source_lifecycle(*, dry_run: bool) -> dict[str, Any]:
    """Record this hour's source and dataset ROI readings and derive each one's lifecycle.

    RESEARCH_ROI.json is rewritten every hour, so a decay can only be measured from a history the
    forge keeps: a reading is appended when its ROI CHANGED or a day has passed since the last
    one, which keeps the log bounded and still dates every move."""
    from libs.research import vintage as V

    doc = _read_json(RESEARCH_ROI)
    history: list[dict[str, Any]] = []
    try:
        for line in ROI_HISTORY.read_text("utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                history.append(row)
    except OSError:
        pass
    last: dict[tuple[str, str], dict[str, Any]] = {}
    for row in history:
        last[(str(row.get("kind")), str(row.get("id")))] = row
    fresh: list[dict[str, Any]] = []
    status = "MEASURED"
    if isinstance(doc, dict):
        at = str(doc.get("at") or doc.get("generated_utc") or now_iso())
        for kind in ("source", "dataset"):
            block = doc.get(f"{kind}_roi")
            for rid, row in (block.items() if isinstance(block, dict) else []):
                if not isinstance(row, dict):
                    continue
                reading = {"at": at, "kind": kind, "id": str(rid), "roi": row.get("roi"),
                           "roi_status": row.get("roi_status") or "UNMEASURED"}
                prev = last.get((kind, str(rid)))
                prev_t = V._stamp(prev.get("at")) if prev else None
                now_t = V._stamp(at)
                if prev is not None and prev.get("roi") == reading["roi"] \
                        and prev.get("roi_status") == reading["roi_status"] \
                        and prev_t is not None and now_t is not None \
                        and now_t - prev_t < ROI_HEARTBEAT_S:
                    continue
                if prev is not None and prev.get("at") == at:
                    continue
                fresh.append(reading)
    else:
        status = "UNMEASURED"
    if fresh and not dry_run:
        ROI_HISTORY.parent.mkdir(parents=True, exist_ok=True)
        with ROI_HISTORY.open("a", encoding="utf-8") as fh:
            for row in fresh:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
    declared_doc = _read_json(FALSIFIERS)
    declared = declared_doc if isinstance(declared_doc, dict) else {}
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in history + fresh:
        grouped.setdefault((str(row.get("kind")), str(row.get("id"))), []).append(row)
    sources: dict[str, Any] = {}
    for (kind, rid), rows in sorted(grouped.items()):
        state = lifecycle(rows, declared.get(rid))
        state["kind"] = kind
        sources[f"{kind}:{rid}"] = state
    counts: dict[str, int] = {}
    for row in sources.values():
        counts[str(row["state"])] = counts.get(str(row["state"]), 0) + 1
    return {"status": status if sources or status == "UNMEASURED" else "UNMEASURED",
            "why": None if isinstance(doc, dict) else f"{RESEARCH_ROI.name} absent",
            "history": str(ROI_HISTORY), "appended": len(fresh), "counts": counts,
            "sources": sources,
            "rule": "retirement needs a named falsifier that arrived; absence never retires"}


def series_lifecycle_rank(series: R.Series, lifecycles: dict[str, Any]) -> int:
    """The worst lifecycle state among the sources this series' id or dataset names."""
    text = f"{series.series_id} {series.dataset}".lower()
    worst = 0
    for key, row in lifecycles.items():
        rid = key.split(":", 1)[-1].lower()
        if len(rid) >= 3 and rid in text:
            worst = max(worst, LIFECYCLE_RANK.get(str(row.get("state")), 0))
    return worst


# ---------------------------------------------------------------------------- the pass
def run(*, budget_s: float = 900.0, dry_run: bool = False, max_new: int = MAX_NEW,
        inputs: WM.Inputs | None = None) -> dict[str, Any]:
    started = time.monotonic()
    deadline = started + budget_s
    source = inputs if inputs is not None else WM.load_inputs(max_series=MAX_SERIES)
    history, history_status = roi_history()
    credit = world_model_credit()
    manifest = existing_manifest()
    by_id = {s.series_id: s for s in source.series}

    # DATA-45 / DATA-48 inputs, built BEFORE ranking so they compete for the same budget.
    vintages_recorded = record_input_vintages(source.series, dry_run=dry_run)
    vint_rows, vint_unmeasured = vintage_candidates(by_id)
    agree_rows, agree_status = disagreement_candidates(by_id)
    nodes, edges, graph_basis = load_graph()
    outcomes, appended = persist_outcomes(negative_outcomes(edges), dry_run=dry_run)
    latent_rows, latent_unmeasured = latent_candidates(outcomes)
    lifecycles = source_lifecycle(dry_run=dry_run)
    causal = CausalIndex(nodes, edges, outcomes, graph_basis)
    prebuilt = {str(r["id"]): s for r, s in (*vint_rows, *agree_rows, *latent_rows)}
    extra = [r for r, _s in (*vint_rows, *agree_rows, *latent_rows)]

    selected, full_plan = propose(source.series, set(manifest), history, budget=max_new,
                                  causal=causal, lifecycles=lifecycles["sources"], extra=extra)
    minted: list[dict[str, Any]] = []
    refused: list[dict[str, str]] = []
    controlled: list[dict[str, Any]] = []
    collided: list[str] = []
    seen_ids: set[str] = set()
    by_transform: dict[str, int] = {}
    kept_by_input: dict[str, list[R.Series]] = {}
    stored_cache: dict[str, list[R.Series]] = {}
    kept_trials: list[Any] = []
    n_eff = 0.0
    for row in selected:
        if time.monotonic() >= deadline:
            refused.append({"id": str(row["id"]), "why": "budget reached before minting",
                            "measured_by": "a longer --budget-s or fewer proposals"})
            continue
        built = mint(row, by_id, prebuilt)
        if built is None:
            refused.append({"id": str(row["id"]),
                            "why": f"produced fewer than {MIN_POINTS} points from its inputs",
                            "measured_by": "a longer input series"})
            continue
        family = str(row["family"])
        points = built.sorted().points
        origin = by_id.get(str(row["inputs"][0])) if row["inputs"] else None
        # DATA-33 CONTROL: information gain, orthogonality and effective-trial cost, against what
        # this pass already kept for the same input.
        input_key = str(row["inputs"][0]) if row["inputs"] else str(row["id"])
        probe = {"id": built.series_id, "family": family, "transform": "|".join(row["chain"]),
                 "source_dataset": row.get("source_dataset")
                 or (origin.dataset if origin is not None else built.dataset),
                 "region": built.region, "inputs": row["inputs"], "params": row["params"]}
        trial = _trial(probe)
        marginal = _n_effective([*kept_trials, trial]) - n_eff
        basis = [b for b in kept_by_input.get(input_key, []) if b.series_id != built.series_id]
        basis += [b for b in stored_basis(input_key, manifest, stored_cache)
                  if b.series_id != built.series_id
                  and all(b.series_id != k.series_id for k in basis)]
        verdict = control(built, origin, basis[:MAX_BASIS], marginal)
        if not verdict["admit"]:
            controlled.append({"id": built.series_id, **verdict})
            continue
        kept_by_input.setdefault(input_key, []).append(built)
        kept_trials.append(trial)
        n_eff += marginal
        by_transform["|".join(row["chain"])] = by_transform.get("|".join(row["chain"]), 0) + 1
        record = {
            "id": built.series_id, "proposal_id": str(row["id"]),
            "file": _file_name(built.series_id), "dataset": built.dataset,
            "source_dataset": probe["source_dataset"],
            "control": verdict,
            "transform": "|".join(row["chain"]), "family": family,
            "params": row["params"], "region": built.region,
            "information_type": built.information_type or "representation",
            "n": len(points),
            "first_available": points[0].available_time if points else None,
            "last_available": points[-1].available_time if points else None,
            "inputs": row["inputs"],
            "novelty": row.get("novelty"), "expected_value": row.get("expected_value"),
            "score": row.get("score"),
            "explained_variance": credit.get(family),
            "pit": {"carried_from": row["inputs"],
                    "rule": "a value stamped available_time t uses only inputs available at t"},
            "minted_at": now_iso(),
        }
        if row.get("causal"):
            record["causal"] = row["causal"]
        record["genome"] = genome_of(record, origin)
        if record["id"] in seen_ids:
            # THE ONE INVARIANT OF A STORE KEYED BY ID. A collision means two different features
            # would occupy one row, and the count would say 56 while the store held 46. It is
            # reported, never silently merged.
            collided.append(str(record["id"]))
            continue
        seen_ids.add(str(record["id"]))
        minted.append(record)
        if not dry_run:
            _atomic(STORE / record["file"], json.loads(R.to_json(built)))

    all_rows = {**manifest, **{r["id"]: r for r in minted}}
    new_records = [r for r in minted if r["id"] not in manifest]
    new_kept = count_new(new_records, _n_effective([_trial(r) for r in new_records]))
    registry_status: dict[str, Any] = {"status": "SKIPPED_DRY_RUN"}
    donation_path: str | None = None
    donations = donation_rows(minted[:MAX_DONATIONS])
    if not dry_run:
        _atomic(MANIFEST, {"at": now_iso(), "rule": RULE, "n": len(all_rows),
                           "representations": sorted(all_rows.values(),
                                                     key=lambda r: str(r.get("id")))})
        registry_status = record_registry(minted, credit)
        if donations:
            from libs.data.pit import stamp_or_refuse

            donations, refused = stamp_or_refuse(donations, "representation_forge")
            if refused:
                raise ValueError(f"Representation forge refused {len(refused)} unstamped donations")
            stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
            path = DONATIONS / f"discoveries_{stamp}.json"
            _atomic(path, donations)
            donation_path = str(path)

    roi_table = build_roi_table(all_rows, history, credit)
    report = {
        "at": now_iso(), "rule": RULE, "budget_s": budget_s,
        "elapsed_s": round(time.monotonic() - started, 2), "dry_run": dry_run,
        "inputs": {"series": len(source.series), "datasets": source.datasets,
                   "unmeasured": source.unmeasured},
        "grammar": {"base_transforms": len(BASE_TRANSFORMS), "compositions": len(COMPOSITIONS),
                    "interactions": list(INTERACTIONS),
                    "pair_transforms": [n for n, _ in PAIR_TRANSFORMS],
                    "panel_transforms": [n for n, _ in PANEL_TRANSFORMS],
                    "max_panel": MAX_PANEL,
                    "registered": sorted(R.TRANSFORMS),
                    "proposals": len(full_plan), "selected": len(selected),
                    "budget": max_new,
                    "why": "novelty x expected value, ties broken on the id so the same tree and "
                           "history select the same representations"},
        "minted": len(minted), "refused": len(refused),
        "id_collisions": collided[:20], "n_id_collisions": len(collided),
        "counts_by_transform": dict(sorted(by_transform.items())),
        "store": {"n_total": len(all_rows), "path": str(STORE),
                  "manifest": str(MANIFEST)},
        "newest_ids": [r["id"] for r in minted[:20]],
        "roi": roi_table,
        "roi_history": history_status,
        "world_model_credit": credit,
        "control": {"rule": "keep a representation only if it adds information gain per "
                            "marginal effective trial and is not near-collinear with what was "
                            "kept for the same input; no trial is charged here (the cell that "
                            "uses it is charged once by the judge)",
                    "max_r2": MAX_R2, "min_gain_nats": MIN_GAIN_NATS,
                    "kept": len(minted), "refused": len(controlled),
                    "refused_by_status": _count(controlled, "status"),
                    "unmeasured_admitted": sum(1 for r in minted
                                               if r["control"].get("status") == "UNMEASURED"),
                    "n_effective_kept": round(n_eff, 3),
                    "refused_sample": controlled[:20],
                    "new_kept": new_kept},
        "vintages": {"recorded": vintages_recorded, "lags": list(_lags()),
                     "candidates": len(vint_rows), "unmeasured": vint_unmeasured[:20]},
        "disagreement": {**agree_status, "candidates": len(agree_rows)},
        "causal_order": {"basis": graph_basis, "nodes": len(nodes), "edges": len(edges),
                         "anchored_series": sum(1 for s in source.series if causal.anchors(s)),
                         "pairs_with_distance": sum(1 for r in full_plan
                                                    if (r.get("causal") or {}).get("distance")
                                                    is not None)},
        "link_outcomes": {"ledger": str(LINK_OUTCOMES), "total": len(outcomes),
                          "appended": appended, "latent_candidates": len(latent_rows),
                          "unmeasured": latent_unmeasured,
                          "rule": "negative link outcomes are latent inputs, never deleted"},
        "source_lifecycle": lifecycles,
        "donations": {"rows": len(donations), "path": donation_path,
                      "seat": "data/intelligence/representation_forge"},
        "registry": registry_status,
        "unmeasured": ([{"item": "representation ROI", "why": "no candidate has yet cited a "
                                                              "representation id",
                         "measured_by": "the compiler stamping representation ids onto the "
                                        "candidates it builds from donated rows"}]
                       if not any(float(r.get("used_by_candidates") or 0) > 0
                                  for r in roi_table.get("rows", [])) else [])
                      + [{"item": r["id"], "why": r["why"], "measured_by": r["measured_by"]}
                         for r in refused[:40]],
    }
    if not dry_run:
        _atomic(OUT, report)
    return report


def _count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        out[str(row.get(key))] = out.get(str(row.get(key)), 0) + 1
    return dict(sorted(out.items()))


def _lags() -> tuple[str, ...]:
    from libs.research import vintage as V

    return tuple(V.FORECAST_LAGS_S)


def build_roi_table(rows: dict[str, dict[str, Any]], history: dict[str, dict[str, float]],
                    credit: dict[str, float]) -> dict[str, Any]:
    """Per family: how many representations exist, and what they have actually earned."""
    by_family: dict[str, dict[str, Any]] = {}
    for row in rows.values():
        family = str(row.get("family") or "unknown")
        bucket = by_family.setdefault(family, {"family": family, "n": 0, "used_by_candidates": 0.0,
                                               "survivors": 0.0, "forward_rows": 0.0,
                                               "explained_variance": credit.get(family),
                                               "expected_value": None})
        bucket["n"] += 1
        earned = history.get(family) or {}
        bucket["used_by_candidates"] = earned.get("candidates", 0.0)
        bucket["survivors"] = earned.get("survivors", 0.0)
        bucket["forward_rows"] = earned.get("forward_rows", 0.0)
        bucket["expected_value"] = R.expected_value(family, history)
    table = sorted(by_family.values(), key=lambda r: (-float(r["n"]), str(r["family"])))
    return {"rows": table, "families": len(table),
            "rule": "a representation is paid by what it goes on to earn -- candidates, "
                    "survivors, forward rows, live attribution -- never by having been minted"}


def genome_of(record: dict[str, Any], origin: R.Series | None) -> dict[str, Any] | None:
    """THE FEATURE GENOME HOOK (LAWS 5m), GUARDED. A minted representation carries its chain --
    data origin, the PIT rule it inherited, the region it is about, the transform chain and the
    forge as researcher -- so the candidate compiler and the world model can read which dataset
    two features share. An absent genome library costs the record nothing but this field."""
    try:
        from libs.research import feature_genome as FG
    except Exception:
        return None
    try:
        pit = record.get("pit") if isinstance(record.get("pit"), dict) else {}
        return FG.genome(
            str(record["id"]),
            data_origin=[str(record.get("source_dataset") or record.get("dataset") or "")],
            pit_normalisation=[str(pit.get("rule") or "")],
            entity_alignment=[f"region:{record.get('region') or 'UNKNOWN'}"],
            representation=[f"representation:{record.get('family') or 'unknown'}"],
            transform=str(record.get("transform") or "").split("|"),
            researcher=["representation_forge"],
            meta={"inputs": list(record.get("inputs") or []), "n": record.get("n"),
                  "information_type": origin.information_type if origin is not None else ""},
        ).to_json()
    except Exception:
        return None


def donation_rows(minted: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Structured donations announcing new representations to the compiler's intake.

    A representation is NOT a hypothesis and is not donated as one: no `family` field, so the
    compiler reads it as evidence rather than compiling a cell out of a feature. What it carries
    is the id, the dataset, the transform and the PIT rule -- the things a later organ needs in
    order to build a hypothesis ON it and to credit it when that hypothesis survives.
    """
    rows: list[dict[str, Any]] = []
    for row in minted:
        rows.append({
            "kind": "representation",
            "source": "representation_forge",
            # THE COMPILER'S OWN "NOT AN EXTRACTION TARGET" FLAG, and it is here to protect the
            # deepening queue rather than to dodge the compiler. A representation row has prose
            # and no instrument, so `compile_row` would label it NEEDS_SYMBOL_EXTRACTION and
            # queue an LLM call that cannot possibly succeed -- there is no instrument in the row
            # to find. That is the exact failure the compiler documents at length: a collector
            # defect hidden inside a research backlog, where it looks like work in progress
            # forever. Flagged, the row dispositions as OPERATIONAL_ROW and is what it actually
            # is: an INPUT announced to whoever builds hypotheses, not a hypothesis.
            "needs_selector_work": True,
            "representation_id": row["id"],
            "dataset": row["dataset"],
            "transform": row["transform"],
            "title": f"representation {row['transform']} over {row['dataset']}",
            "text": (f"{row['transform']} over {row['dataset']} as a point-in-time feature "
                     f"({row['n']} points, {row['first_available']} .. {row['last_available']}). "
                     f"Every value uses only inputs knowable at its own stamp. This is an INPUT "
                     f"for hypothesis generation, not a claim about returns."),
            "n": row["n"],
            "pit": row["pit"],
            "novelty": row.get("novelty"),
            "expected_value": row.get("expected_value"),
            "genome": row.get("genome"),
            "public_source": "desks/mt5/reports/REPRESENTATION_FORGE.json",
        })
    return rows


def record_registry(minted: list[dict[str, Any]], credit: dict[str, float]) -> dict[str, Any]:
    """One row per representation in the registry's `representations` table, plus the pass KPI."""
    out: dict[str, Any] = {"upserted": 0, "new": 0, "kpis": 0}
    try:
        from libs.moat import registry as reg
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"registry unimportable: {type(exc).__name__}"}
    try:
        conn = reg.connect()
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"registry unopenable: {type(exc).__name__}"}
    try:
        for row in minted:
            created = reg.representation_upsert(
                str(row["id"]), dataset=str(row["dataset"]), transform=str(row["transform"]),
                family=str(row["family"]), params=row["params"], region=str(row["region"]),
                information_type=str(row["information_type"]), n_points=int(row["n"]),
                first_available=row["first_available"], last_available=row["last_available"],
                pit=row["pit"], novelty=row.get("novelty"),
                expected_value=row.get("expected_value"),
                explained_variance=credit.get(str(row["family"])), origin="representation_forge",
                genome_json=row.get("genome"),
                payload={"inputs": row["inputs"], "file": row["file"]}, conn=conn)
            out["upserted"] += 1
            out["new"] += int(created)
        reg.kpi(now_iso()[:10], "representation_forge.minted", float(len(minted)),
                detail={"families": sorted({str(r["family"]) for r in minted})}, conn=conn)
        out["kpis"] += 1
    except Exception as exc:
        out["status"] = f"PARTIAL: {type(exc).__name__}"
    finally:
        conn.close()
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly cycle is the clock)")
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--dry-run", action="store_true", help="propose and print; write nothing")
    ap.add_argument("--max-new", type=int, default=MAX_NEW)
    args = ap.parse_args(argv)

    report = run(budget_s=args.budget_s, dry_run=args.dry_run, max_new=args.max_new)
    print(f"representation forge: {report['minted']} minted of "
          f"{report['grammar']['proposals']} proposal(s) over {report['inputs']['series']} "
          f"series, {report['store']['n_total']} in the store, {report['refused']} refused, "
          f"{report['elapsed_s']}s")
    for row in report["roi"]["rows"][:8]:
        print(f"    {row['family']:<18}n={row['n']:<5} used={row['used_by_candidates']:<6} "
              f"survivors={row['survivors']:<5} EV={row['expected_value']}")
    if args.dry_run:
        print("--dry-run: nothing written, nothing registered, nothing donated")
        return 0
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
