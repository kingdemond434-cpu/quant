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
     ("desks/mt5/mt5desk/family_coint_pairs.py",), "desks/mt5/reports/BREADTH_SWEEP.json",
     "cells_built", "families.coint_pairs"),
    ("gradient-boosted trees feature-to-label (LightGBM/XGBoost style, numpy)",
     "retail+institutional",
     ("desks/mt5/research/hypgen_engine.py", "desks/mt5/mt5desk/family_hypgen_models.py"),
     "desks/mt5/reports/HYPGEN_GBM_LEARNER.json", "tests_run", "donated"),
    ("learning-to-rank, time series (pairwise RankNet, rolling refit)", "institutional",
     ("desks/mt5/research/hypgen_engine.py", "desks/mt5/mt5desk/family_hypgen_models.py"),
     "desks/mt5/reports/HYPGEN_RANK_LEARNER.json", "tests_run", "donated"),
    ("learning-to-rank, cross-sectional (LambdaRank, Numerai style) over the symbol panel",
     "institutional (US/UK; Numerai, WorldQuant; China 机器学习选股)",
     ("desks/mt5/research/global_methods.py", "desks/mt5/mt5desk/family_global_methods.py"),
     "desks/mt5/reports/GLOBAL_METHOD_XS_LTR.json", "cells_charged_total", "cells_proposed"),
    ("analog / nearest-neighbour pattern matching", "retail+institutional",
     ("desks/mt5/research/hypgen_engine.py", "desks/mt5/mt5desk/family_hypgen_models.py"),
     "desks/mt5/reports/HYPGEN_KNN_ANALOG.json", "tests_run", "donated"),
    ("neuroevolution (NEAT-style topology + weights) of trading policies", "academic",
     ("desks/mt5/research/hypgen_engine.py", "desks/mt5/mt5desk/family_hypgen_models.py"),
     "desks/mt5/reports/HYPGEN_NEAT_EVOLVER.json", "tests_run", "donated"),
    ("grammatical evolution over a full strategy BNF (AND/OR/NOT, filters, partial take, trail)",
     "academic", ("desks/mt5/research/hypgen_engine.py",
                  "desks/mt5/mt5desk/family_hypgen_models.py"),
     "desks/mt5/reports/HYPGEN_GE_BUILDER.json", "tests_run", "donated"),
    ("hyper-heuristic generator selection (the bandit across generators)", "academic",
     ("desks/mt5/research/research_budget.py", "libs/research/bandit.py"),
     None, None, None),
    # ------------------------------------------------------------------------------------------
    # THE WORLD-PRACTICE CATALOGUE (2026-11-25, zuck: "take inspirations from how quants do it
    # globally, China, Asia, wherever ... but for our edges"). Each row is a method as quants in
    # that market practise it, pointed at the code that converts it for the desk's tradables (FX
    # majors/crosses, metals, energy, indices, crypto CFDs; exotics banned; single names only in
    # the class books). A row whose code is absent is MISSING and is a build target.
    # --- China ---
    ("研报复现: broker factor-report replication as published (GTJA-191, Qlib Alpha158)",
     "China (Guotai Junan; Microsoft Research Asia Qlib)",
     ("desks/mt5/research/formula_library.py", "libs/research/formula_catalog.py"),
     "desks/mt5/reports/FORMULA_LIBRARY.json", "trials_charged", None),
    ("高频因子: intraday high-frequency factors aggregated to daily (realised skew, signed jump "
     "variation, MAX), ranked within the class", "China (Haitong, Founder) + academic",
     ("desks/mt5/research/global_methods.py", "desks/mt5/mt5desk/family_global_methods.py"),
     "desks/mt5/reports/GLOBAL_METHOD_HF_MOMENT.json", "cells_charged_total", "cells_proposed"),
    ("Barra CNE5/CNE6-style factor tilts (momentum, reversal, value, volatility, beta, carry) "
     "as within-class long/short books", "China (MSCI Barra China; CICC, Huatai multi-factor)",
     ("desks/mt5/mt5desk/families_cross_sectional.py",
      "desks/mt5/research/cross_sectional_breadth.py"),
     "desks/mt5/reports/CROSS_SECTIONAL_BREADTH.json", "candidates_this_pass",
     "donated_this_pass"),
    ("动量反转: short-term reversal and momentum crossover ranked in the class",
     "China (JoinQuant / RiceQuant / BigQuant communities)",
     ("desks/mt5/mt5desk/families_cross_sectional.py",
      "desks/mt5/research/cross_sectional_breadth.py"),
     "desks/mt5/reports/CROSS_SECTIONAL_BREADTH.json", "candidates_this_pass",
     "donated_this_pass"),
    ("量价: price-volume divergence / correlation factors (CORR(volume, close) family)",
     "China (GTJA-191, Tianfeng, Founder price-volume reports)",
     ("desks/mt5/research/formula_library.py",), "desks/mt5/reports/FORMULA_LIBRARY.json",
     "trials_charged", None),
    ("资金流: money-flow factors from signed tick volume (MFI, net-inflow reversal)",
     "China (Haitong, Guosen money-flow reports)",
     ("desks/mt5/mt5desk/family_money_flow.py",), None, None, None),
    ("CTA 期货: term-structure, roll-yield and basis-momentum factors on commodity curves",
     "China (CITIC/GTJA futures CTA reports) + academic (Szymanowska 2014; Boons & Prado 2019)",
     ("desks/mt5/mt5desk/family_term_structure.py",), None, None, None),
    ("Qlib model zoo over a factor library (LightGBM / DoubleEnsemble / TRA on Alpha158)",
     "China (Microsoft Research Asia)", ("desks/mt5/research/model_search.py",),
     "desks/mt5/reports/MODEL_SEARCH.json", None, None),
    ("WorldQuant Alpha101 as published, cross-sectional panel (rank-based alphas executable)",
     "US (WorldQuant, Kakushadze 2015)",
     ("libs/research/formulaic_alphas.py", "desks/mt5/research/expression_factory.py"),
     None, None, None),
    ("WorldQuant Alpha101 rank alphas as their own executable family (panel RANK on the class)",
     "US (WorldQuant)", ("desks/mt5/mt5desk/family_alpha101.py",), None, None, None),
    # --- Japan ---
    ("ichimoku kinko hyo as systematic rules (tenkan/kijun cross, kumo filter, chikou confirm)",
     "Japan", ("desks/mt5/mt5desk/family_ichimoku.py",), None, None, None),
    ("sakata / candlestick patterns as systematic rules (engulfing, pin bar; 三山 三川 三兵 "
     "三法 still unbuilt)", "Japan", ("desks/mt5/mt5desk/families.py",), None, None, None),
    # --- Korea ---
    ("변동성 돌파: Larry Williams volatility breakout with the noise-ratio k and MA score",
     "Korea (Korean retail-quant school) + US (Larry Williams)",
     ("desks/mt5/research/global_methods.py", "desks/mt5/mt5desk/family_global_methods.py"),
     "desks/mt5/reports/GLOBAL_METHOD_VOL_BREAKOUT.json", "cells_charged_total",
     "cells_proposed"),
    ("외국인 수급: foreign-investor flow following (analogue: CFTC positioning on MT5 contracts)",
     "Korea (KRX investor flow) -> US CFTC analogue",
     ("desks/mt5/mt5desk/families_orthogonal.py",), None, None, None),
    # --- India ---
    ("options open-interest positioning (PCR, max-pain) -> MT5 analogue: COT positioning and the "
     "implied-realised gap", "India (NSE options desks)",
     ("desks/mt5/mt5desk/families_orthogonal.py", "desks/mt5/mt5desk/family_tier1_ideas.py"),
     None, None, None),
    ("opening-range breakout / Supertrend on index CFDs (the NIFTY intraday school)",
     "India", ("desks/mt5/mt5desk/families_orthogonal.py",), None, None, None),
    # --- Russia ---
    ("market profile / volume profile value area (80% rule, acceptance) from yesterday's auction",
     "Russia (volume-profile school) + US (CBOT Market Profile)",
     ("desks/mt5/research/global_methods.py", "desks/mt5/mt5desk/family_global_methods.py"),
     "desks/mt5/reports/GLOBAL_METHOD_VALUE_AREA.json", "cells_charged_total",
     "cells_proposed"),
    ("econophysics regime measures (Hurst exponent, fractal dimension) gating trend vs reversion",
     "Russia (econophysics school) + academic", ("desks/mt5/mt5desk/family_hurst_regime.py",),
     None, None, None),
    # --- Europe / US institutional ---
    ("value-carry-momentum everywhere: time-series style premia (AQR / Asness-Moskowitz-Pedersen)",
     "Europe/US (AQR, Man AHL)", ("desks/mt5/mt5desk/family_style_premia.py",
                                  "desks/mt5/research/style_premia_sweep.py"),
     "desks/mt5/reports/style_premia_sweep.json", "tests_run", "cells_proposed"),
    ("currency carry ranked in the class (HML_FX, crash-filtered)",
     "Europe/US (Lustig-Roussanov-Verdelhan; Menkhoff et al.)",
     ("desks/mt5/mt5desk/families_cross_sectional.py",), None, None, None),
    ("multi-speed CTA trend following (Winton / Man AHL / Aspect)", "Europe (UK CTAs)",
     ("desks/mt5/mt5desk/family_multi_speed_trend.py",), None, None, None),
    ("statistical-factor residual reversal (PCA residual, Avellaneda-Lee)", "US (stat-arb desks)",
     ("desks/mt5/mt5desk/families_orthogonal.py",), None, None, None),
    ("intraday momentum: the session's first window predicts its last (Gao-Han-Li-Zhou 2018)",
     "US + China (index-futures replications)",
     ("desks/mt5/mt5desk/family_tier1_ideas.py", "desks/mt5/research/tier1_idea_proposer.py"),
     "desks/mt5/reports/TIER1_IDEA_PROPOSER.json", "tests_run", "cells_proposed"),
    ("calendar and seasonal anomalies (turn of month, holidays, seasonal windows)", "global",
     ("desks/mt5/mt5desk/families_orthogonal.py", "desks/mt5/mt5desk/families_specialist.py"),
     None, None, None),
]


def _age_h(path: Path) -> float | None:
    try:
        return (time.time() - path.stat().st_mtime) / 3600.0
    except OSError:
        return None


def _num(doc: Any, key: str | None) -> float | None:
    """A number off the report; a dotted key reads one level down (`families.coint_pairs`), so a
    method minted by a shared producer is credited with its own family's cells only."""
    if not key or not isinstance(doc, dict):
        return None
    v: Any = doc
    for part in key.split("."):
        v = v.get(part) if isinstance(v, dict) else None
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


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
