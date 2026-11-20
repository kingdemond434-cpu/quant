"""GENERATOR COVERAGE: every known way to generate a trading hypothesis, against what runs here.

zuck, 2026-11-20: "add every form of generator ... from firm or retail quants, whatever it is".
This organ is the map. Each row is a METHOD (from institutional practice, retail builders,
academic papers or public tools, any country), the module that carries it on this desk, and the
report that proves it ran. Status per row, measured on the machine the organ runs on:

    LIVE     code present AND its report is fresh (< FRESH_H) with work done (tests/trials > 0)
    PARTIAL  code present, but no fresh report proving it ran (built is not live)
    MISSING  no code carries the method -- a build target, never a silent gap

A row's yield is read from its own report when the report names one (cells proposed per test
run), so `research_budget`'s bandit and a human can both see which generators earn their compute.

    python desks/mt5/research/generator_coverage.py      -> reports/GENERATOR_COVERAGE.json
"""
from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
OUT = BASE / "reports" / "GENERATOR_COVERAGE.json"
FRESH_H = 26.0

#: (method, origin, code paths (any present = carried), report path or None, report key for
#: work done, report key for cells proposed)
METHODS: list[tuple[str, str, tuple[str, ...], str | None, str | None, str | None]] = [
    ("genetic programming over formulas (gplearn, WorldQuant BRAIN)", "retail+institutional",
     ("desks/mt5/research/alpha_evolution.py", "libs/research/search_populations.py"),
     "desks/mt5/reports/alpha_evolution.json", "tests_run", "cells_proposed"),
    ("multi-objective NSGA-II over fitness components", "academic",
     ("libs/research/search_populations.py",), "desks/mt5/reports/alpha_evolution.json",
     "tests_run", None),
    ("GFlowNet sampling in proportion to reward", "academic",
     ("libs/research/generators.py",), "desks/mt5/reports/alpha_evolution.json", "tests_run", None),
    ("symbolic regression (PySR, DSO)", "academic",
     ("libs/research/generators.py", "libs/research/adapters/pysr.py"),
     "desks/mt5/reports/alpha_evolution.json", "tests_run", None),
    ("exhaustive typed program synthesis to a depth bound", "academic",
     ("libs/research/search_populations.py",), "desks/mt5/reports/alpha_evolution.json",
     "tests_run", None),
    ("Bayesian optimisation / TPE surrogate", "academic",
     ("libs/research/search_populations.py", "libs/research/adapters/botorch.py"),
     "desks/mt5/reports/alpha_evolution.json", "tests_run", None),
    ("alpha zoo templates as genetic material (Alpha101, Alpha158, GTJA191)",
     "institutional+China", ("libs/research/search_populations.py",
                             "libs/research/adapters/alpha101.py"),
     "desks/mt5/reports/alpha_evolution.json", "tests_run", None),
    ("quality-diversity / MAP-Elites archive", "academic",
     ("desks/mt5/research/alpha_evolution.py", "desks/mt5/research/qd_frontier.py"),
     "desks/mt5/reports/alpha_evolution.json", "tests_run", None),
    ("reinforcement-learning formula generation (AlphaGen)", "academic+China",
     ("libs/research/alpha_rl.py", "desks/mt5/research/alpha_rl_run.py"), None, None, None),
    ("rule-strategy genetic builder: entries x filters x exits (StrategyQuant, Adaptrade, "
     "EA Studio, Build Alpha)", "retail",
     ("desks/mt5/research/strategy_builder.py", "desks/mt5/mt5desk/family_rule_builder.py"),
     "desks/mt5/reports/STRATEGY_BUILDER.json", "tests_run", "donated"),
    ("LLM-proposed expressions and ideas (RD-Agent, AlphaAgent, QuantaAlpha style)",
     "academic+institutional", ("desks/mt5/research/deepening_worker.py",
                                "libs/research/adapters/rd_agent.py"), None, None, None),
    ("paper / forum / video claim mining, every language", "global",
     ("desks/mt5/research/deep_forest_miner.py",), None, None, None),
    ("graveyard mutation along the recorded failure axis", "desk",
     ("libs/research/search_populations.py",), "desks/mt5/reports/alpha_evolution.json",
     "tests_run", None),
    ("causal-graph-derived hypotheses", "academic", ("desks/mt5/research/causal_discovery.py",),
     None, None, None),
    ("combinatorial feature crosses / feature synthesis (featuretools, tsfresh)", "retail+ML",
     ("desks/mt5/research/feature_compiler.py", "libs/research/adapters/featuretools.py"),
     None, None, None),
    ("parameter grid / mass screen over registered families", "retail",
     ("desks/mt5/research/breadth_sweep.py",), None, None, None),
    ("mechanism descendants (instrument, horizon, session, exit, state, leg)", "desk",
     ("desks/mt5/research/descendants.py",), None, None, None),
    ("alpha recombination / ensembles", "institutional",
     ("desks/mt5/research/alpha_recombination.py",), None, None, None),
    ("trajectory evolution", "academic", ("libs/research/adapters/quantaalpha.py",),
     None, None, None),
    ("co-evolution of factor and model", "academic",
     ("desks/mt5/research/sandboxes/coevolution_cell.py",), None, None, None),
    ("Monte Carlo tree search over formulas", "academic", ("libs/research/alpha_grammar.py",),
     None, None, None),
    ("CMA-ES / evolution strategies for continuous parameters", "academic",
     ("libs/research/adapters/nevergrad.py",), None, None, None),
    ("motif / matrix-profile pattern discovery (stumpy)", "academic",
     ("libs/research/adapters/stumpy.py",), None, None, None),
    ("sparse dynamics discovery (SINDy)", "academic", ("libs/research/adapters/pysindy.py",),
     None, None, None),
    ("cointegration / statistical-arbitrage pair search", "institutional",
     ("desks/mt5/research/cross_asset_graph.py",), None, None, None),
    ("learning-to-rank cross-sectional ML (LambdaRank, Numerai style)", "institutional",
     ("desks/mt5/research/learning_to_rank.py",), None, None, None),
    ("analog / nearest-neighbour day matching", "retail+institutional",
     ("desks/mt5/research/analog_generator.py",), None, None, None),
    ("neuroevolution (NEAT) of trading policies", "academic",
     ("desks/mt5/research/neuroevolution.py",), None, None, None),
    ("grammatical evolution over a full strategy BNF (entry+exit+money mgmt)", "academic",
     ("desks/mt5/research/grammatical_evolution.py",), None, None, None),
    ("hyper-heuristic generator selection (the bandit across generators)", "academic",
     ("desks/mt5/research/research_budget.py", "libs/research/bandit.py"),
     None, None, None),
]


def _age_h(path: Path) -> float | None:
    try:
        return (time.time() - path.stat().st_mtime) / 3600.0
    except OSError:
        return None


def _num(doc: Any, key: str | None) -> float | None:
    if not key or not isinstance(doc, dict):
        return None
    v = doc.get(key)
    return float(v) if isinstance(v, (int, float)) else None


def build(root: Path = ROOT) -> dict[str, Any]:
    rows = []
    for method, origin, paths, report, work_key, yield_key in METHODS:
        have = [p for p in paths if (root / p).exists()]
        row: dict[str, Any] = {"method": method, "origin": origin, "code": have or list(paths)}
        if not have:
            row["status"] = "MISSING"
            rows.append(row)
            continue
        status, why = "PARTIAL", "no report names this method's work"
        if report:
            rp = root / report
            age = _age_h(rp)
            doc: Any = None
            if age is not None:
                try:
                    doc = json.loads(rp.read_text("utf-8"))
                except (OSError, ValueError):
                    doc = None
            work = _num(doc, work_key)
            cells = _num(doc, yield_key)
            row.update({"report": report, "report_age_h": None if age is None else round(age, 1),
                        "work": work, "cells": cells,
                        "cells_per_1k_tests": (round(1000 * cells / work, 3)
                                               if work and cells is not None else None)})
            if age is None:
                why = "report absent"
            elif age > FRESH_H:
                why = f"report {age:.0f}h old"
            elif not work:
                why = "report fresh but did no work"
            else:
                status, why = "LIVE", "fresh report with work done"
        row["status"], row["why"] = status, why
        rows.append(row)
    counts = {s: sum(r["status"] == s for r in rows) for s in ("LIVE", "PARTIAL", "MISSING")}
    return {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "counts": counts,
            "rule": "built is not live; MISSING is a build target", "methods": rows}


def main(argv: list[str] | None = None) -> int:
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), "utf-8")
    c = doc["counts"]
    print(f"GENERATOR COVERAGE  live {c['LIVE']}  partial {c['PARTIAL']}  missing {c['MISSING']}")
    for r in doc["methods"]:
        if r["status"] != "LIVE":
            print(f"  {r['status']:8s} {r['method'][:80]}  ({r.get('why', 'no code')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
