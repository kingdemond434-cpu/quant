"""Portfolio-aware genetic search over the alpha grammar, proposing formula cells to the gauntlet.

WHAT IS SEARCHED. Expressions from `libs.research.alpha_grammar` -- causal operators over the
instrument's own bars and its economic drivers -- traded by `family_formula` with a fixed
threshold recipe. A population per instrument is evolved by mutation and crossover for a few
generations; every distinct expression evaluated is a trial and is charged as one.

FITNESS IS WHAT THE EXPRESSION DOES FOR THE BOOK, not its standalone t:

    fitness = t x (0.5 + 0.5 x stability)          the edge, discounted when one half carries it
            - LAMBDA_CORR x relu(corr_survivors) x |t|  the part of it the desk already owns
            + LAMBDA_NOVEL x novelty                 behaviourally NEW money is worth extra
            - LAMBDA_CX x complexity                 every node is a degree of freedom

`corr_survivors` is the correlation of the expression's daily P&L proxy with the desk's own
shadow P&L on the same instrument (from the shadow ledgers); `novelty` is one minus the largest
absolute correlation of the expression's z-series with the canonical reference alphas and with
the rest of the population (feature-space novelty, so part of the search is always hunting a
different KIND of money rather than a better version of the same one).

SUCCESSIVE HALVING. Each new expression is first screened on the most recent STAGE0_FRAC of the
history -- a thirty-times cheaper falsifier -- and only the better half is run on the full
sample. The culled half still counts in the multiplicity: they were tried.

WHAT LEAVES. The best cell per instrument that clears cost and deflation, as an EXACT_RECIPE
under family `formula`, with `describe()`'s mechanism sentence written AFTER the search from the
tree. The gauntlet judges it like everything else; nothing here has authority.

WHERE NEW INDIVIDUALS COME FROM (2026-09-04). Every individual that is not bred from the elite
-- the whole initial population, and a FRESH_FRAC share of each generation's children -- is
drawn from one of `libs.research.generators.GENERATORS` ("random", "gflow", "symreg"), chosen by
the weights in `data/generator_weights.json` when that file exists and uniformly when it does
not. Each row records its `generator` ("mutate" / "crossover" for bred children), so a yield
ledger can score generators by what their individuals went on to certify and write the weights
back; this module reads the weights and never sets them.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk.family_formula import family_formula  # noqa: E402

from libs.research import alpha_grammar as ag  # noqa: E402
from libs.research import generators as gen  # noqa: E402
from research import proposer_common as pc  # noqa: E402

SOURCE = "alpha_evolution"
REPORT = _DESK / "reports" / "alpha_evolution.json"
#: Generator weights, WRITTEN by the yield ledger and only READ here. Absent -> uniform.
GENERATOR_WEIGHTS = _DESK / "data" / "generator_weights.json"
#: Share of each generation's new children drawn fresh from a generator rather than bred from
#: the elite, so the learned samplers keep contributing after generation zero.
FRESH_FRAC = 0.25
POP, GENS, ELITE, DEPTH = 40, 5, 8, 3
STAGE0_FRAC = 0.35
LAMBDA_CORR, LAMBDA_NOVEL, LAMBDA_CX = 0.8, 0.5, 0.03
RECIPE = {"norm": 240, "entry_z": 1.5, "hold_bars": 8, "atr_n": 20, "stop_atr": 2.0, "rr": 1.5}
SIDE_MODES = ("follow", "fade")


def _book_symbols() -> list[str]:
    try:
        from research.state_vector_build import book_symbols
        return book_symbols()
    except Exception:
        return []


def _drivers_for(sym: str, meta: dict) -> dict[str, pd.DataFrame]:
    """The instrument's economic drivers as role -> bars, from the registry's driver sets."""
    out: dict[str, pd.DataFrame] = {}
    try:
        from mt5desk.economic_drivers import ROLES, driver_sets
        have = {p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet")}
        for ds in driver_sets(sym, meta, have):
            for d in ds.drivers:
                for role, cands in ROLES.items():
                    if d in cands and role.lower() not in out:
                        b = pc.bars(d)
                        if b is not None:
                            out[role.lower()] = b
    except Exception:
        pass
    return out


def _survivor_daily_pnl(sym: str) -> pd.Series | None:
    """The desk's own shadow P&L on this instrument by day: what the book already earns here."""
    try:
        from research.state_admission_run import load_trades
        rows = [(t.when, t.r) for t in load_trades("shadow")
                if str(t.sleeve).split("_")[0].upper() == sym.upper()]
    except Exception:
        return None
    if not rows:
        return None
    s = pd.Series({pd.Timestamp(w).tz_convert("UTC").normalize() if pd.Timestamp(w).tzinfo
                   else pd.Timestamp(w).tz_localize("UTC").normalize(): r for w, r in rows})
    return s.groupby(level=0).sum()


def _daily_pnl_proxy(z: pd.Series, ret: pd.Series, entry_z: float, hold: int) -> pd.Series:
    """Vectorised sign(z)-when-extreme position held `hold` bars, times next-bar return."""
    pos = np.sign(z.where(z.abs() >= entry_z, 0.0)).fillna(0.0)
    held = pos.rolling(hold, min_periods=1).apply(
        lambda w: w[w != 0][-1] if (w != 0).any() else 0.0, raw=True) if hold > 1 else pos
    pnl = held.shift(1) * ret
    return pnl.groupby(pnl.index.normalize()).sum()


def _corr(a: pd.Series | None, b: pd.Series | None) -> float:
    if a is None or b is None:
        return 0.0
    j = pd.concat([a, b], axis=1, join="inner").dropna()
    if len(j) < 20 or j.iloc[:, 0].std() == 0 or j.iloc[:, 1].std() == 0:
        return 0.0
    return float(j.iloc[:, 0].corr(j.iloc[:, 1]))


class _Evaluator:
    def __init__(self, sym: str, d: pd.DataFrame, cost: float, drivers: dict[str, pd.DataFrame],
                 survivors: pd.Series | None) -> None:
        self.sym, self.d, self.cost, self.drivers = sym, d, cost, drivers
        self.unfillable = pc.artifact_hours(d)
        self.frames = ag.terminal_frames(d, raw=d, drivers=drivers)
        self.ret = self.frames["ret"]
        self.survivors = survivors
        self.canon_z = {k: self._z(ag.evaluate(v, self.frames)) for k, v in ag.CANON.items()}
        self.cut = int(len(d) * (1.0 - STAGE0_FRAC))
        self.rows: dict[str, dict] = {}                    # key -> row (one per expression)
        self.zs: dict[str, pd.Series] = {}
        self.origin: dict[str, str] = {}                   # key -> generator that made it
        self.generator_weights: dict = {}
        self.generator_failures: list[str] = []

    @staticmethod
    def _z(v: pd.Series, norm: int = RECIPE["norm"]) -> pd.Series:
        r = v.rolling(norm, min_periods=norm)
        return (v - r.mean()) / r.std()

    def screen(self, expr: ag.Expr, side_mode: str, stage0: bool) -> dict | None:
        params = {**RECIPE, "expr": expr, "side_mode": side_mode}
        d = self.d.iloc[self.cut:] if stage0 else self.d
        sig = family_formula(d, drivers=self.drivers, **params)
        return pc.screen(d, sig, self.cost, self.unfillable)

    def fitness(self, expr: ag.Expr, side_mode: str, pop_z: list[pd.Series]) -> float:
        k = f"{ag.key(expr)}|{side_mode}"
        if k in self.rows and "fitness" in self.rows[k]:
            return float(self.rows[k]["fitness"])
        base = {"cell": f"{self.sym}.formula.{side_mode}", "symbol": self.sym,
                "params": {**RECIPE, "expr": expr, "side_mode": side_mode},
                "expr": ag.to_str(expr), "complexity": ag.complexity(expr),
                "generator": self.origin.get(k, "unspecified")}
        s0 = self.screen(expr, side_mode, stage0=True)
        if s0 is None:
            self.rows[k] = {**base, "stage": 0, "t_gross": 0.0, "clears_cost": False,
                            "n_independent": 0, "fitness": -9.0}
            return -9.0
        self.rows[k] = {**base, "stage": 0, **s0, "fitness": float(s0["t_gross"]) * 0.5 - 9.0}
        return float(self.rows[k]["fitness"])

    def promote(self, expr: ag.Expr, side_mode: str, pop_z: list[pd.Series]) -> float:
        """Full-sample evaluation for an expression that survived stage 0."""
        k = f"{ag.key(expr)}|{side_mode}"
        row = self.rows.get(k)
        if row is None or row.get("stage") == 1:
            return float(row["fitness"]) if row else -9.0
        full = self.screen(expr, side_mode, stage0=False)
        if full is None:
            row.update({"stage": 1, "fitness": -9.0})
            return -9.0
        half = len(self.d) // 2
        t1 = pc.screen(self.d.iloc[:half],
                       family_formula(self.d.iloc[:half], drivers=self.drivers, **row["params"]),
                       self.cost, self.unfillable)
        t2 = pc.screen(self.d.iloc[half:],
                       family_formula(self.d.iloc[half:], drivers=self.drivers, **row["params"]),
                       self.cost, self.unfillable)
        t = float(full["t_gross"])
        th = [float(x["t_gross"]) for x in (t1, t2) if x]
        stability = (min(th) / max(abs(t), 1e-9)) if len(th) == 2 else 0.0
        stability = float(np.clip(stability * np.sign(t), 0.0, 1.0))
        z = self._z(ag.evaluate(expr, self.frames))
        self.zs[k] = z
        flip = 1.0 if side_mode == "follow" else -1.0
        pnl = _daily_pnl_proxy(z * flip, self.ret, RECIPE["entry_z"], RECIPE["hold_bars"])
        corr_surv = _corr(pnl, self.survivors)
        refs = list(self.canon_z.values()) + pop_z
        novelty = 1.0 - max([abs(_corr(z, r)) for r in refs] or [0.0])
        fit = (t * (0.5 + 0.5 * stability) - LAMBDA_CORR * max(0.0, corr_surv) * abs(t)
               + LAMBDA_NOVEL * novelty - LAMBDA_CX * row["complexity"])
        row.update({"stage": 1, **full, "t_half": th, "stability": round(stability, 3),
                    "corr_survivors": round(corr_surv, 3), "novelty": round(novelty, 3),
                    "fitness": round(float(fit), 4)})
        return float(fit)


def evolve(sym: str, d: pd.DataFrame, cost: float, drivers: dict[str, pd.DataFrame],
           survivors: pd.Series | None, *, seed: int = 0, budget_s: float = 240.0,
           pop: int = POP, gens: int = GENS) -> _Evaluator:
    rng = np.random.default_rng(seed)
    ev = _Evaluator(sym, d, cost, drivers, survivors)
    allow_drivers = bool(drivers)
    weights, weights_basis = gen.load_weights(GENERATOR_WEIGHTS)
    ev.generator_weights = {"weights": weights, "basis": weights_basis}

    def _history() -> list[tuple[ag.Expr, float]]:
        return [(r["params"]["expr"], float(r["fitness"])) for r in ev.rows.values()
                if "fitness" in r]

    def _fresh() -> tuple[ag.Expr, str]:
        """A new individual from the chosen generator; a generator that raises is recorded and
        replaced by the random draw, so a broken sampler costs one individual, not the sweep."""
        name = gen.choose_generator(rng, weights)
        if name == "random":
            return random_or_canon(rng, allow_drivers), name
        try:
            return gen.GENERATORS[name](rng, ev.frames, ev.ret, _history(), allow_drivers,
                                        DEPTH), name
        except Exception as exc:
            ev.generator_failures.append(f"{name}: {type(exc).__name__}: {exc}")
            return random_or_canon(rng, allow_drivers), "random"

    population: list[tuple[ag.Expr, str]] = []
    seen: set[str] = set()
    while len(population) < pop:
        e, origin = _fresh()
        sm = str(rng.choice(SIDE_MODES))
        k = f"{ag.key(e)}|{sm}"
        if k not in seen:
            seen.add(k)
            ev.origin[k] = origin
            population.append((e, sm))
    started = time.monotonic()
    for _g in range(gens):
        if time.monotonic() - started > budget_s:
            break
        # Stage 0 for everyone new, full sample for the better half.
        s0 = sorted(population, key=lambda es: -ev.fitness(es[0], es[1], []))
        keep = s0[: max(ELITE, len(s0) // 2)]
        pop_z = list(ev.zs.values())
        scored = sorted(keep, key=lambda es: -ev.promote(es[0], es[1], pop_z))
        elite = scored[:ELITE]
        children: list[tuple[ag.Expr, str]] = list(elite)
        while len(children) < pop and time.monotonic() - started <= budget_s:
            a = elite[int(rng.integers(len(elite)))]
            move = rng.random()
            if move < FRESH_FRAC:
                e, origin = _fresh()
                sm = str(rng.choice(SIDE_MODES))
            else:
                if rng.random() < 0.5 and len(elite) > 1:
                    b = elite[int(rng.integers(len(elite)))]
                    e, origin = ag.crossover(a[0], b[0], rng, allow_drivers), "crossover"
                else:
                    e, origin = ag.mutate(a[0], rng, allow_drivers), "mutate"
                sm = a[1] if rng.random() < 0.8 else str(rng.choice(SIDE_MODES))
            k = f"{ag.key(e)}|{sm}"
            if k in seen or ag.complexity(e) > 14:
                continue
            seen.add(k)
            ev.origin[k] = origin
            children.append((e, sm))
        population = children
    # Final full evaluation of whatever is still only stage-0 in the last generation's elite.
    for e, sm in population[:ELITE]:
        ev.promote(e, sm, list(ev.zs.values()))
    return ev


def random_or_canon(rng: np.random.Generator, allow_drivers: bool) -> ag.Expr:
    if rng.random() < 0.15:
        return json.loads(json.dumps(list(ag.CANON.values())[int(rng.integers(len(ag.CANON)))]))
    return ag.random_expr(rng, DEPTH, allow_drivers)


def generator_yield(rows: list[dict]) -> dict[str, dict]:
    """Per generator: how many individuals it made, how many went full-sample, how many were
    proposed, and its best fitness. The raw material for the yield ledger that sets the weights;
    reported here so the number exists, decided nowhere here."""
    out: dict[str, dict] = {}
    for r in rows:
        g = str(r.get("generator") or "unspecified")
        row = out.setdefault(g, {"tried": 0, "full": 0, "proposed": 0, "best_fitness": None})
        row["tried"] += 1
        if r.get("stage") == 1:
            row["full"] += 1
        if r.get("proposed"):
            row["proposed"] += 1
        f = r.get("fitness")
        if isinstance(f, (int, float)) and (row["best_fitness"] is None or f > row["best_fitness"]):
            row["best_fitness"] = float(f)
    return out


def run(symbols: list[str] | None = None, budget_s: float = 1500.0, seed: int = 0,
        pop: int = POP, gens: int = GENS) -> dict:
    meta = pc.universe_meta()
    have = {p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet")}
    todo = [s for s in (symbols or _book_symbols()) if s in have]
    rows: list[dict] = []
    skipped: dict[str, str] = {}
    per_symbol: dict[str, dict] = {}
    generator_weights: dict = {}
    generator_failures: list[str] = []
    started = time.monotonic()
    per_sym_budget = max(60.0, budget_s / max(1, len(todo)))
    for sym in sorted(set(todo)):
        if time.monotonic() - started > budget_s:
            skipped[sym] = "sweep budget exhausted"
            continue
        d = pc.bars(sym)
        if d is None or len(d) < 3000:
            skipped[sym] = "under 3000 H1 bars"
            continue
        cost = pc.cost_frac(sym, meta, d["close"])
        if cost is None:
            skipped[sym] = "no contract terms to price the round trip"
            continue
        ev = evolve(sym, d, cost, _drivers_for(sym, meta), _survivor_daily_pnl(sym), seed=seed,
                    budget_s=per_sym_budget, pop=pop, gens=gens)
        sym_rows = list(ev.rows.values())
        rows.extend(sym_rows)
        full = [r for r in sym_rows if r.get("stage") == 1]
        per_symbol[sym] = {"expressions_tried": len(sym_rows), "full_evaluations": len(full),
                           "best": (max(full, key=lambda r: r["fitness"])["expr"] if full
                                    else None),
                           "drivers": sorted(ev.drivers),
                           "generators": generator_yield(sym_rows)}
        generator_weights = ev.generator_weights
        generator_failures.extend(f"{sym}: {f}" for f in ev.generator_failures)
    # Every distinct expression tried is a trial; stage-0-only rows may not be proposed.
    rows = pc.deflate(rows)
    for r in rows:
        if r.get("stage") != 1:
            r["proposed"] = False
    proposals = pc.best_per_cell(rows)
    cands = [pc.candidate(
        SOURCE, r["symbol"], "formula", dict(r["params"]),
        mechanism=ag.describe(r["params"]["expr"], r["params"]["side_mode"]),
        title=f"{r['cell']} {r['expr']}",
        # `generator` rides in the evidence so `mutation_yield` can join each proposal's fate
        # back to the generator that made it and write the weights this module reads.
        evidence={k: r.get(k) for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                        "cost_frac", "t_gross", "t_deflated_sweep",
                                        "n_tests_sweep", "stability", "corr_survivors",
                                        "novelty", "fitness", "generator")},
    ) for r in proposals]
    report = {"generated_at": datetime.now(tz=UTC).isoformat(), "symbols_swept": len(todo),
              "tests_run": len(rows), "cells_proposed": len(proposals), "skipped": skipped,
              "per_symbol": per_symbol, "proposals": proposals,
              # THE GENERATOR YIELD LEDGER'S INPUT: which generator's individuals were tried,
              # went full-sample and were proposed, sweep-wide, beside the weights that were
              # read. Whatever writes data/generator_weights.json reads this.
              "generator_yield": generator_yield(rows),
              "generator_weights": generator_weights,
              "generator_failures": generator_failures,
              "top": sorted((r for r in rows if r.get("stage") == 1
                             and int(r.get("n_independent", 0)) > 0),
                            key=lambda r: -r["fitness"])[:25]}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    if cands:
        report["donated"] = str(pc.donate(SOURCE, cands, len(rows)))
    # THE LLM AS A FOURTH GENERATOR. One task per swept instrument asks the deepening seat for an
    # expression the grammar search did NOT find, with the terminals it may use and the best
    # expressions already tried; the worker validates the tree structurally (kind
    # alpha_expression) and the compiler admits it as a formula cell like any GP survivor. The
    # seat has no more authority than the random generator -- its output is charged and gated.
    try:
        report["llm_tasks"] = len(_expression_tasks(per_symbol, rows))
    except Exception as exc:
        report["llm_tasks_error"] = f"{type(exc).__name__}: {exc}"
    return report


def _expression_tasks(per_symbol: dict, rows: list[dict], *, top: int = 5) -> list[dict]:
    tasks = []
    for sym, info in sorted(per_symbol.items()):
        tried = sorted((r for r in rows if r.get("symbol") == sym and r.get("stage") == 1),
                       key=lambda r: -float(r.get("fitness") or -9.0))[:top]
        terminals = list(ag.BAR_TERMINALS) + sorted(info.get("drivers") or [])
        tasks.append({
            "source": SOURCE, "kind": "alpha_expression", "symbols": [sym],
            "title": f"{sym}: one formulaic alpha the grammar search has not found",
            "url": "",
            "description": (f"Available terminals: {terminals}. Best expressions already tried "
                            f"(do not return these): {[r.get('expr') for r in tried]}. Windows: "
                            f"{list(ag.WINDOWS)}. Return family 'formula' with a well-typed "
                            "expression, side_mode, entry_z and hold_bars, and the economic "
                            "mechanism it expresses."),
            "tried": [r.get("expr") for r in tried], "status": None,
            "consumer": "deepening_worker (alpha_expression) -> compiler -> gauntlet"})
    if tasks:
        from research.regime_coverage import _merge_into_queue
        _merge_into_queue(tasks, source=SOURCE)
    return tasks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=1500.0)
    ap.add_argument("--pop", type=int, default=POP)
    ap.add_argument("--gens", type=int, default=GENS)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rep = run(symbols=a.symbol, budget_s=a.budget_s, seed=a.seed, pop=a.pop, gens=a.gens)
    print(f"ALPHA EVOLUTION  {rep['symbols_swept']} symbols, {rep['tests_run']} expressions tried, "
          f"{rep['cells_proposed']} proposed")
    for r in rep["top"][:10]:
        print(f"  {r['symbol']:8s} fit={r['fitness']:+6.2f} t={r['t_gross']:+5.2f} "
              f"t_defl={r.get('t_deflated_sweep', 0):+5.2f} n={r['n_independent']:4d} "
              f"stab={r.get('stability', 0):.2f} corr_surv={r.get('corr_survivors', 0):+.2f} "
              f"nov={r.get('novelty', 0):.2f}  {r['params']['side_mode']}  {r['expr']}")
    for k, v in rep["skipped"].items():
        print(f"  skipped {k}: {v}")
    print("generators: " + ", ".join(
        f"{g}={y['tried']}/{y['full']}/{y['proposed']}" for g, y in rep["generator_yield"].items())
        + f"  (weights: {rep['generator_weights'].get('basis')})")
    for f in rep["generator_failures"]:
        print(f"  generator failed: {f}")
    print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
