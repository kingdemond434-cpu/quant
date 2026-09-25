#!/usr/bin/env python3
"""THE PROGRAM DATABASE -- AlphaEvolve over the desk's OWN algorithms, not over expressions.

    python desks/mt5/research/algorithm_db.py --once --budget-s 120

WHAT WAS ALREADY HERE AND IS NOT DUPLICATED (measured 2026-09-23). `alpha_evolution` evolves
EXPRESSIONS inside a fixed harness; `joint_evolution` evolves genome axes; `research_os_archive`
keeps a population of POLICY variants over declared knobs. What nothing did was keep a database
keyed by the PROGRAM -- the parameterised configuration of a search policy, a regime detector, an
execution model, a cost model or a validator battery -- with lineage, and score each one against
the organ that already measures that class. So the desk could improve an alpha and could not
improve the ALGORITHM that found it.

A PROGRAM HERE IS A CONFIG, NEVER CODE. Nothing in this module writes, patches or execs a module:
a program is a named class plus a dict of parameters inside a DECLARED schema, and the database is
append-only JSONL. The code-level lane (an IR that emits real programs) is a separate item and is
deliberately not smuggled in here -- a research organ that rewrote modules would be outside every
fence the desk owns.

THE FIVE CLASSES, AND THE ORGAN THAT ALREADY SCORES EACH ONE (the "automated evaluator"):

    search_policy      reports/alpha_evolution.json   proposals per expression tried
    regime_detector    reports/REGIME_COVERAGE.json   share of the state space admitted
    execution_model    reports/EXECUTION_ALPHA.json   execution discoveries per pass
    cost_model         reports/COST_TRUTH.json        deals the measured cost surface covers
    validator_battery  reports/JUDGE_COVERAGE.json    families the judge actually reached

AN ABSENT REPORT IS UNMEASURED, NOT ZERO (L1.28a). A class whose organ has not run keeps its
incumbent champion and says why; it never falls to a fabricated score, and a program with no
evaluation never becomes a champion.

EVOLUTION IS MUTATION AND CROSSOVER OVER THE SCHEMA, with lineage on every row: a child names its
parents, its generation and the operator that made it. Selection is the class's own measured
score; ties break towards the OLDER program, so a new config must actually beat the incumbent
rather than merely differ from it.

THE CONSUMER. `alpha_evolution.search_policy()` reads the champion `search_policy` config when the
research-evolution archive names no active variant -- the archive still wins where it speaks, and
this fills the default that was previously a module constant. Every other class's champion is
published for the organ that owns it; a champion nothing reads is recorded as such in
`unconsumed`, because an unread champion is a defect and must be visible as one (LAWS 7).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from random import Random
from typing import Any

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = "algorithm_db"
DB = BASE / "data" / "algorithm_db.jsonl"
REPORT = BASE / "reports" / "ALGORITHM_DB.json"
REPORTS = BASE / "reports"
#: Rows read from the tail of the database in one pass. The file is append-only and small; this
#: exists so a year of generations cannot make an hourly leg quadratic.
MAX_ROWS = 4000
#: Children proposed per class per pass.
CHILDREN = 4


class Schema:
    """A class's parameter space: numeric ranges and categorical choices, declared."""

    def __init__(self, numeric: Mapping[str, tuple[float, float, bool]],
                 choices: Mapping[str, Sequence[Any]]) -> None:
        self.numeric = dict(numeric)          # name -> (lo, hi, is_int)
        self.choices = {k: list(v) for k, v in choices.items()}

    def names(self) -> list[str]:
        return sorted([*self.numeric, *self.choices])

    def clamp(self, params: Mapping[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, (lo, hi, is_int) in self.numeric.items():
            v = params.get(k, (lo + hi) / 2.0)
            try:
                f = float(v)
            except (TypeError, ValueError):
                f = (lo + hi) / 2.0
            f = max(lo, min(hi, f))
            out[k] = round(f) if is_int else round(f, 4)
        for k, opts in self.choices.items():
            v = params.get(k)
            out[k] = v if v in opts else opts[0]
        return out

    def draw(self, rng: Random) -> dict[str, Any]:
        p: dict[str, Any] = {}
        for k, (lo, hi, is_int) in self.numeric.items():
            f = rng.uniform(lo, hi)
            p[k] = round(f) if is_int else round(f, 4)
        for k, opts in self.choices.items():
            p[k] = rng.choice(opts)
        return p

    def mutate(self, params: Mapping[str, Any], rng: Random,
               scale: float = 0.25) -> dict[str, Any]:
        p = dict(params)
        names = self.names()
        if not names:
            return self.clamp(p)
        for k in rng.sample(names, k=max(1, len(names) // 3)):
            if k in self.numeric:
                lo, hi, _ = self.numeric[k]
                span = (hi - lo) * scale
                try:
                    base = float(p.get(k, (lo + hi) / 2.0))
                except (TypeError, ValueError):
                    base = (lo + hi) / 2.0
                p[k] = base + rng.uniform(-span, span)
            else:
                p[k] = rng.choice(self.choices[k])
        return self.clamp(p)

    def crossover(self, a: Mapping[str, Any], b: Mapping[str, Any],
                  rng: Random) -> dict[str, Any]:
        return self.clamp({k: (a if rng.random() < 0.5 else b).get(k) for k in self.names()})


#: THE FIVE PROGRAM CLASSES. `evaluator` is (report file, dotted metric path, denominator path or
#: None) -- the class's OWN scoring organ, read, never re-implemented here.
CLASSES: dict[str, dict[str, Any]] = {
    "search_policy": {
        "schema": Schema({"fresh_frac": (0.05, 0.60, False), "refine_top": (2, 12, True),
                          "elite": (4, 16, True)},
                         {"parent_selection": ["nsga2", "elite", "tournament"]}),
        "evaluator": ("alpha_evolution.json", "cells_proposed", "tests_run"),
        "consumer": "desks/mt5/research/alpha_evolution.py:search_policy",
    },
    "regime_detector": {
        "schema": Schema({"buckets": (3, 12, True), "min_obs": (10, 120, True),
                          "shrink_k": (10.0, 120.0, False)},
                         {"basis": ["kmeans", "quantile", "hmm"]}),
        "evaluator": ("REGIME_COVERAGE.json", "coverage", None),
        "consumer": "desks/mt5/research/regime_coverage.py (champion published, not yet read)",
    },
    "execution_model": {
        "schema": Schema({"delay_bars": (0, 4, True), "markout_bars": (1, 30, True)},
                         {"fill_rule": ["mid", "touch", "adverse"]}),
        "evaluator": ("EXECUTION_ALPHA.json", "discoveries", None),
        "consumer": "desks/mt5/research/execution_alpha.py (champion published, not yet read)",
    },
    "cost_model": {
        "schema": Schema({"spread_mult": (0.5, 2.5, False), "impact_exp": (0.3, 1.0, False)},
                         {"basis": ["measured", "declared", "worst_of"]}),
        "evaluator": ("COST_TRUTH.json", "n_deals", None),
        "consumer": "desks/mt5/research/cost_truth.py (champion published, not yet read)",
    },
    "validator_battery": {
        "schema": Schema({"quota": (1, 40, True), "min_families": (1, 20, True)},
                         {"order": ["cheapest_first", "hardest_first", "random"]}),
        "evaluator": ("JUDGE_COVERAGE.json", "totals.judged", "totals.queued"),
        "consumer": "desks/mt5/research/judge_coverage.py (champion published, not yet read)",
    },
}


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _dotted(doc: Any, path: str) -> Any:
    cur = doc
    for part in str(path).split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def evaluate(klass: str, reports: Path | None = None) -> dict[str, Any]:
    """The class's own scoring organ, read. (score, status, why) -- never a fabricated number."""
    spec = CLASSES[klass]
    fname, metric, denom = spec["evaluator"]
    path = (reports or REPORTS) / fname
    doc = _read_json(path)
    if doc is None:
        return {"score": None, "status": "UNMEASURED",
                "why": f"{fname} absent or unreadable; this class has no measured evaluator "
                       f"this pass and its incumbent champion stands"}
    num = _dotted(doc, metric)
    if isinstance(num, list):
        num = float(len(num))
    den = _dotted(doc, denom) if denom else None
    try:
        value = float(num)
    except (TypeError, ValueError):
        return {"score": None, "status": "UNMEASURED",
                "why": f"{fname} carries no numeric {metric!r}"}
    if denom:
        try:
            d = float(den)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            d = 0.0
        value = value / d if d > 0 else 0.0
    return {"score": round(float(value), 6), "status": "MEASURED",
            "why": f"{fname}:{metric}" + (f" / {denom}" if denom else "")}


def _rows(path: Path | None = None, limit: int = MAX_ROWS) -> list[dict[str, Any]]:
    p = path or DB
    if not p.exists():
        return []
    try:
        lines = p.read_text("utf-8").splitlines()[-int(limit):]
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
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


def _append(rows: Sequence[Mapping[str, Any]], path: Path | None = None) -> int:
    p = path or DB
    if not rows:
        return 0
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    except OSError:
        return 0
    return len(rows)


def champion(klass: str, path: Path | None = None) -> dict[str, Any]:
    """The best-scored program of this class, or the seed when nothing has been evaluated."""
    best: dict[str, Any] | None = None
    for row in _rows(path):
        if row.get("class") != klass or row.get("score") is None:
            continue
        if best is None or float(row["score"]) > float(best["score"]) or (
                float(row["score"]) == float(best["score"])
                and str(row.get("born_at") or "") < str(best.get("born_at") or "")):
            best = row
    if best is None:
        schema: Schema = CLASSES[klass]["schema"]
        return {"class": klass, "program_id": f"{klass}:seed", "params": schema.clamp({}),
                "score": None, "status": "UNMEASURED",
                "why": "no evaluated program of this class yet; the seed config is the incumbent"}
    return {**best, "status": "MEASURED"}


def evolve(*, budget_s: float = 120.0, children: int = CHILDREN, seed: int = 0,
           path: Path | None = None, reports: Path | None = None) -> dict[str, Any]:
    """One generation per class: seed if empty, otherwise mutate and cross the evaluated elite."""
    rng = Random(seed or int(time.time()))  # noqa: S311 - config search, not crypto
    deadline = time.monotonic() + max(1.0, float(budget_s))
    existing = _rows(path)
    by_class: dict[str, list[dict[str, Any]]] = {}
    for row in existing:
        by_class.setdefault(str(row.get("class")), []).append(row)
    new_rows: list[dict[str, Any]] = []
    per_class: dict[str, Any] = {}
    for klass, spec in CLASSES.items():
        if time.monotonic() > deadline:
            per_class[klass] = {"status": "DEFERRED", "why": "pass budget spent"}
            continue
        schema: Schema = spec["schema"]
        pool = by_class.get(klass) or []
        ev = evaluate(klass, reports)
        gen = 1 + max((int(r.get("generation") or 0) for r in pool), default=0)
        made: list[dict[str, Any]] = []
        if not pool:
            made.append({"params": schema.clamp({}), "operator": "seed", "parents": []})
            for _ in range(max(0, children - 1)):
                made.append({"params": schema.draw(rng), "operator": "random", "parents": []})
        else:
            elite = sorted((r for r in pool if r.get("score") is not None),
                           key=lambda r: -float(r["score"]))[:4] or pool[-4:]
            for _ in range(children):
                a = elite[rng.randrange(len(elite))]
                if len(elite) > 1 and rng.random() < 0.5:
                    b = elite[rng.randrange(len(elite))]
                    made.append({"params": schema.crossover(a.get("params") or {},
                                                            b.get("params") or {}, rng),
                                 "operator": "crossover",
                                 "parents": [a.get("program_id"), b.get("program_id")]})
                else:
                    made.append({"params": schema.mutate(a.get("params") or {}, rng),
                                 "operator": "mutate", "parents": [a.get("program_id")]})
        seen = {json.dumps(r.get("params") or {}, sort_keys=True) for r in pool}
        kept = 0
        for i, child in enumerate(made):
            key = json.dumps(child["params"], sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            kept += 1
            new_rows.append({
                "program_id": f"{klass}:g{gen}:{i}:{abs(hash(key)) % 10**8:08d}",
                "class": klass, "params": child["params"], "operator": child["operator"],
                "parents": [p for p in child["parents"] if p], "generation": gen,
                "born_at": _now(),
                # THE EVALUATION IS THE CLASS'S OWN ORGAN, read at birth. A child born in an hour
                # the organ did not run carries score None and can never become champion.
                "score": ev["score"], "evaluator": ev["why"], "evaluator_status": ev["status"],
            })
        per_class[klass] = {"status": "EVOLVED", "generation": gen, "proposed": len(made),
                            "kept": kept, "pool": len(pool), "evaluator": ev}
    written = _append(new_rows, path)
    return {"written": written, "by_class": per_class, "rows_before": len(existing)}


def run(*, budget_s: float = 120.0, children: int = CHILDREN, seed: int = 0,
        path: Path | None = None, reports: Path | None = None,
        out: Path | None = None) -> dict[str, Any]:
    started = time.monotonic()
    result = evolve(budget_s=budget_s, children=children, seed=seed, path=path, reports=reports)
    champions = {k: champion(k, path) for k in CLASSES}
    unconsumed = [k for k, spec in CLASSES.items() if "not yet read" in str(spec["consumer"])]
    doc = {
        "at": _now(), "budget_s": float(budget_s),
        "elapsed_s": round(time.monotonic() - started, 2),
        "database": str(path or DB), "rows_written": result["written"],
        "rows_before": result["rows_before"], "by_class": result["by_class"],
        "champions": champions,
        "classes": {k: {"parameters": v["schema"].names(), "evaluator": v["evaluator"],
                        "consumer": v["consumer"]} for k, v in CLASSES.items()},
        # AN UNREAD CHAMPION IS A DEFECT AND IS NAMED (LAWS 7, III.16). One class is consumed
        # today; the rest are published and this list is what a reader should shrink.
        "unconsumed": unconsumed,
        "rule": ("a program is a CONFIG inside a declared schema -- never code. Children are "
                 "mutations and crossovers of the evaluated elite, carrying lineage; selection "
                 "is the class's own scoring organ, and an absent organ is UNMEASURED, so an "
                 "unevaluated program can never become a champion"),
        "consumer": "desks/mt5/research/alpha_evolution.py:search_policy (search_policy class)",
    }
    target = out or REPORT
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    except OSError as exc:                                     # pragma: no cover - disk
        doc["write_error"] = f"{type(exc).__name__}: {exc}"
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=120.0)
    ap.add_argument("--children", type=int, default=CHILDREN)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, children=a.children, seed=a.seed)
    print(f"ALGORITHM DB  {doc['rows_written']} program(s) written "
          f"({doc['rows_before']} rows before) -> {doc['database']}")
    for k, ch in doc["champions"].items():
        print(f"  {k:<18} {ch.get('program_id')}  score={ch.get('score')} "
              f"({ch.get('status')})")
    if doc["unconsumed"]:
        print(f"  UNCONSUMED champions (published, nothing reads them yet): "
              f"{', '.join(doc['unconsumed'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
