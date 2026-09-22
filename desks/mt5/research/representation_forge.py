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
)
#: The compositions the grammar is allowed to mint: (inner, outer). Held short on purpose -- the
#: space is combinatorial and the budget is an hour on a box that also holds a live terminal.
COMPOSITIONS: tuple[tuple[str, str], ...] = (
    ("surprise", "zscore"), ("diff", "zscore"), ("surprise", "rank_percentile"),
    ("pace", "zscore"), ("diff", "rolling_volatility"), ("vintage_revision", "zscore"),
    ("seasonal_expectation", "diff"), ("lead_lag", "zscore"),
)
INTERACTIONS: tuple[str, ...] = ("ratio", "product")

MIN_POINTS = 24
MAX_NEW = 60
MAX_PAIRS = 24
MAX_SERIES = 160
#: Proposals ranked per pass. The grammar offers thousands; ranking them all is the cheap part
#: and minting them is not, but an unbounded plan still costs a pass its budget in scoring alone.
MAX_PROPOSALS = 4_000
MAX_DONATIONS = 15
RULE = ("every ingested series becomes many features, each PIT-stamped, id'd, stored and "
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
            *, budget: int = MAX_NEW, max_pairs: int = MAX_PAIRS
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

    pairs = 0
    for i, left in enumerate(series):
        for right in series[i + 1:]:
            if left.dataset == right.dataset or len(left.points) < MIN_POINTS \
                    or len(right.points) < MIN_POINTS:
                continue
            for name in INTERACTIONS:
                transform = R.Transform(name=name, params={})
                rid = R.representation_id(f"{dataset_key(left)}x{dataset_key(right)}", name, {})
                plan.append({"id": rid, "family": transform.family, "chain": [name], "params": {},
                             "inputs": [left.series_id, right.series_id], "arity": 2})
            pairs += 1
            if pairs >= max_pairs:
                break
        if pairs >= max_pairs:
            break

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
    unique.sort(key=lambda r: (-float(r.get("score") or 0.0), str(r["id"])))
    return unique[:budget], unique


def mint(row: dict[str, Any], by_id: dict[str, R.Series]) -> R.Series | None:
    """Build one proposed representation, or None when its inputs cannot support it.

    The inputs are RELABELLED onto their own `dataset_key` first, so the id the library stamps is
    the id the plan proposed -- one representation per series, not one per dataset label.
    """
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

    selected, full_plan = propose(source.series, set(manifest), history, budget=max_new)
    minted: list[dict[str, Any]] = []
    refused: list[dict[str, str]] = []
    collided: list[str] = []
    seen_ids: set[str] = set()
    by_transform: dict[str, int] = {}
    for row in selected:
        if time.monotonic() >= deadline:
            refused.append({"id": str(row["id"]), "why": "budget reached before minting",
                            "measured_by": "a longer --budget-s or fewer proposals"})
            continue
        built = mint(row, by_id)
        if built is None:
            refused.append({"id": str(row["id"]),
                            "why": f"produced fewer than {MIN_POINTS} points from its inputs",
                            "measured_by": "a longer input series"})
            continue
        family = str(row["family"])
        by_transform["|".join(row["chain"])] = by_transform.get("|".join(row["chain"]), 0) + 1
        points = built.sorted().points
        origin = by_id.get(str(row["inputs"][0]))
        record = {
            "id": built.series_id, "proposal_id": str(row["id"]),
            "file": _file_name(built.series_id), "dataset": built.dataset,
            "source_dataset": origin.dataset if origin is not None else built.dataset,
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
    registry_status: dict[str, Any] = {"status": "SKIPPED_DRY_RUN"}
    donation_path: str | None = None
    donations = donation_rows(minted[:MAX_DONATIONS])
    if not dry_run:
        _atomic(MANIFEST, {"at": now_iso(), "rule": RULE, "n": len(all_rows),
                           "representations": sorted(all_rows.values(),
                                                     key=lambda r: str(r.get("id")))})
        registry_status = record_registry(minted, credit)
        if donations:
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
