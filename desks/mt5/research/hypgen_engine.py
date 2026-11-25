"""THE HYPOTHESIS-GENERATOR ENGINE: four more generators on the strategy builder's audited rails.

zuck, 2026-11-20 / 11-24: every form of generator. `generator_coverage` listed four known methods
MISSING; this engine runs all four, each as its own seat with its own persisted populations:

    knn_analog       analog / nearest-neighbour pattern matching        -> family analog_knn
    rank_learner     time-series learning-to-rank (pairwise RankNet)     -> family ranked_linear
    neat_evolver     NEAT-style neuroevolution of topology + weights     -> family neural_policy
    ge_builder       grammatical evolution over a full strategy BNF      -> family ge_strategy
                     (AND / OR / NOT over entry blocks, filters, and an exit with partial take,
                     runner trail and volatility-expansion exit)

THE RAILS ARE THE STRATEGY BUILDER'S, INHERITED, NOT RE-IMPLEMENTED (`strategy_builder.Lineage`,
Auditor CLEAR fe91dd889): reserved 30% tail never read; worst-fold walk-forward fitness on train;
validation read at harvest only, DSR at the lineage's LIFETIME evaluated count + BH-FDR; an
unreadable state file skips the lineage and the count is floored at the claim ledger; a pass
donates ONLY after `claim_selection.register_grid` charged every donated row's lineage; every
candidate is performance-scored into `libs/ops/breadth_allocator`; volume follows the judge's
measured drain (`strategy_builder.intake_budget`); cells are picked least-searched first with the
fill-cost gate (`strategy_builder.pick_cells`). A `Space` supplies only what differs: the genome,
its variation operators, its family params and its mechanism class.

    python desks/mt5/research/hypgen_engine.py --space knn_analog [--budget-s 240] [--symbols 4]
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import sys
import time
from pathlib import Path
from typing import Any, ClassVar

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(ROOT), str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import strategy_builder as sb  # noqa: E402

REPORTS = BASE / "reports"
STATE_ROOT = BASE / "data" / "hypgen"
#: Model families cost more per evaluation than a rule: smaller populations, same rails.
POP = 24
EXIT = {"stop_atr": [1.0, 1.5, 2.0, 3.0], "rr": [1.0, 1.5, 2.0, 3.0]}

FEATURE_CLASS = {"ret_1": "momentum", "ret_2": "momentum", "ret_4": "momentum",
                 "ret_8": "momentum", "ret_24": "momentum", "ret_72": "momentum",
                 "z_20": "reversion", "z_50": "reversion", "z_200": "trend", "rsi_14": "reversion",
                 "rsi_2": "reversion", "chan_pos": "trend", "atr_rank": "volatility",
                 "range_atr": "volatility", "body": "volatility", "vol_z": "flow",
                 "hour_sin": "seasonal", "hour_cos": "seasonal"}
CLASSES = tuple(sorted(set(FEATURE_CLASS.values())))


def _features(rng: random.Random, cls: str | None, lo: int = 2, hi: int = 6) -> list[str]:
    from mt5desk.hypgen_features import FEATURES
    first = [f for f in FEATURES if FEATURE_CLASS.get(f) == cls] if cls else list(FEATURES)
    out = [rng.choice(first or list(FEATURES))]
    rest = [f for f in FEATURES if f not in out]
    out += rng.sample(rest, k=min(len(rest), rng.randint(lo, hi) - 1))
    return out


def _mut_features(rng: random.Random, feats: list[str]) -> list[str]:
    from mt5desk.hypgen_features import FEATURES
    f = list(feats)
    r = rng.random()
    if r < 0.4 and len(f) > 2:
        f.pop(rng.randrange(1, len(f)))                  # the first (class-defining) one stays
    elif r < 0.8 and len(f) < 8:
        f.append(rng.choice([x for x in FEATURES if x not in f] or list(FEATURES)))
    else:
        i = rng.randrange(len(f))
        f[i] = rng.choice([x for x in FEATURES if x not in f] or list(FEATURES))
    return f


# --------------------------------------------------------------------------- spaces
class Space:
    seat = ""
    family = ""
    classes: tuple[str, ...] = CLASSES
    grid: ClassVar[dict[str, list]] = {}

    def random(self, rng: random.Random, cls: str | None = None) -> dict:
        g = {"features": _features(rng, cls)}
        g.update({k: rng.choice(v) for k, v in {**self.grid, **EXIT}.items()})
        return g

    def mutate(self, rng: random.Random, g: dict) -> dict:
        c = copy.deepcopy(g)
        if rng.random() < 0.4:
            c["features"] = _mut_features(rng, c["features"])
        else:
            k = rng.choice(sorted({**self.grid, **EXIT}))
            c[k] = rng.choice({**self.grid, **EXIT}[k])
        return c

    def crossover(self, rng: random.Random, a: dict, b: dict) -> dict:
        c = {k: copy.deepcopy(rng.choice((a, b))[k]) for k in a}
        pool = list(dict.fromkeys(a["features"] + b["features"]))
        c["features"] = [a["features"][0], *rng.sample(pool[1:], k=min(len(pool) - 1,
                                                                        rng.randint(1, 5)))]
        return c

    def params(self, g: dict) -> dict:
        return dict(g)

    def complexity(self, g: dict) -> int:
        return len(g.get("features") or [])

    def mech_class(self, g: dict) -> str:
        return FEATURE_CLASS.get((g.get("features") or [""])[0], "other")

    def describe(self, g: dict) -> str:
        return f"{self.family} on {', '.join(g.get('features') or [])}"

    def valid(self, g: dict) -> bool:
        return bool(g.get("features")) and all(k in g for k in self.grid)


class KnnSpace(Space):
    seat, family = "knn_analog", "analog_knn"
    grid: ClassVar[dict[str, list]] = {
        "k": [10, 20, 40, 80], "h": [4, 8, 12, 24, 48], "library": [1000, 2000, 4000],
        "thr": [1.0, 1.5, 2.0, 2.5], "stride": [2, 3, 4]}


class RankSpace(Space):
    seat, family = "rank_learner", "ranked_linear"
    grid: ClassVar[dict[str, list]] = {
        "h": [4, 8, 12, 24, 48], "window": [1000, 2000, 4000], "refit": [100, 250, 500],
        "q": [0.8, 0.9, 0.95]}


class NeatSpace(Space):
    """NEAT-style: genes are connections keyed by (src, dst) -- the innovation identity -- and
    structure grows by add-connection and add-node (split) mutations; crossover aligns matching
    genes and inherits disjoint ones from the first parent. Diversity is kept by the archive's
    mechanism niches (by the network's first input class) instead of compatibility speciation."""
    seat, family = "neat_evolver", "neural_policy"
    grid: ClassVar[dict[str, list]] = {"thr": [0.2, 0.3, 0.5, 0.7], "hold": [4, 8, 12, 24, 48]}

    def random(self, rng, cls=None):
        feats = _features(rng, cls, 2, 5)
        conns = [[f"i{k}", "out", round(rng.gauss(0, 1), 3), True] for k in range(len(feats))]
        g = {"net": {"inputs": feats, "hidden": {}, "conns": conns}}
        g.update({k: rng.choice(v) for k, v in {**self.grid, **EXIT}.items()})
        return g

    @staticmethod
    def _rank(node: str) -> float:
        if node.startswith("i"):
            return -1.0
        if node == "out":
            return 1e9
        return float(node[1:])

    def mutate(self, rng, g):
        c = copy.deepcopy(g)
        net = c["net"]
        conns, hidden = net["conns"], net["hidden"]
        r = rng.random()
        if r < 0.5 and conns:                              # weight perturbation
            cn = rng.choice(conns)
            cn[2] = round(cn[2] + rng.gauss(0, 0.5) if rng.random() < 0.9 else rng.gauss(0, 1), 3)
        elif r < 0.65:                                     # add connection, kept acyclic
            nodes = [f"i{k}" for k in range(len(net["inputs"]))] + sorted(hidden) + ["out"]
            a, b = rng.choice(nodes), rng.choice(nodes)
            if self._rank(a) > self._rank(b):
                a, b = b, a
            if self._rank(a) < self._rank(b) and not b.startswith("i") \
                    and not any(x[0] == a and x[1] == b for x in conns):
                conns.append([a, b, round(rng.gauss(0, 1), 3), True])
        elif r < 0.75 and conns and len(hidden) < 8:       # add node: split a connection
            cn = rng.choice([x for x in conns if x[3]] or conns)
            lo_r, hi_r = self._rank(cn[0]), self._rank(cn[1])
            new = f"h{(max(lo_r, 0) + min(hi_r, 1000)) / 2:.4f}".rstrip("0").rstrip(".")
            if new not in hidden and new != "h":
                cn[3] = False
                hidden[new] = rng.choice(["tanh", "relu", "sig", "id"])
                conns += [[cn[0], new, 1.0, True], [new, cn[1], cn[2], True]]
        elif r < 0.82 and conns:                           # toggle a gene
            cn = rng.choice(conns)
            cn[3] = not cn[3]
        elif r < 0.9 and hidden:                           # activation
            hidden[rng.choice(sorted(hidden))] = rng.choice(["tanh", "relu", "sig", "id"])
        else:                                              # exit / threshold gene
            k = rng.choice(sorted({**self.grid, **EXIT}))
            c[k] = rng.choice({**self.grid, **EXIT}[k])
        return c

    def crossover(self, rng, a, b):
        if a["net"]["inputs"] != b["net"]["inputs"]:
            return copy.deepcopy(rng.choice((a, b)))       # different input spaces do not align
        c = copy.deepcopy(a)
        theirs = {(x[0], x[1]): x for x in b["net"]["conns"]}
        for cn in c["net"]["conns"]:                       # matching genes: either parent
            m = theirs.get((cn[0], cn[1]))
            if m is not None and rng.random() < 0.5:
                cn[2], cn[3] = m[2], m[3]
        for k in self.grid:
            c[k] = rng.choice((a[k], b[k]))
        return c

    def complexity(self, g):
        return len(g["net"]["hidden"]) + sum(1 for x in g["net"]["conns"] if x[3])

    def mech_class(self, g):
        return FEATURE_CLASS.get((g["net"].get("inputs") or [""])[0], "other")

    def describe(self, g):
        n = g["net"]
        return (f"NEAT network: {len(n['hidden'])} hidden, "
                f"{sum(1 for x in n['conns'] if x[3])} live links over {', '.join(n['inputs'])}")

    def valid(self, g):
        return isinstance(g.get("net"), dict) and bool(g["net"].get("conns"))


class GeSpace(Space):
    """Grammatical evolution: the genome is a list of integer codons; the BNF below decodes it
    (with wrapping) into a `ge_strategy` phenotype. Variation acts on codons, so the grammar --
    not the operator -- decides which strategies are reachable.

        <strategy> ::= <rule> <filters> <exit>
        <rule>     ::= <block> | and(<rule>, <rule>) | or(<rule>, <rule>) | not(<rule>)
        <filters>  ::= () | (<filter>) | (<filter>, <filter>)
        <exit>     ::= stop_atr rr hold bank_frac runner_trail_k expansion_mult
    """
    seat, family = "ge_builder", "ge_strategy"
    N_CODONS = 60
    EXITS: ClassVar[dict[str, list]] = {
        "stop_atr": [0.75, 1.0, 1.5, 2.0, 3.0], "rr": [1.0, 1.5, 2.0, 3.0, 4.0],
        "hold": [4, 8, 12, 24, 48, 96], "bank_frac": [0.0, 0.0, 0.33, 0.5],
        "runner_trail_k": [0.0, 0.0, 2.0, 3.0], "expansion_mult": [0.0, 0.0, 2.0, 4.0]}

    @property
    def classes(self):
        from mt5desk.family_rule_builder import MECH_CLASS
        return tuple(sorted(set(MECH_CLASS.values())))

    def random(self, rng, cls=None):
        codons = [rng.randrange(256) for _ in range(self.N_CODONS)]
        if cls:                                            # steer the first block's class
            from mt5desk.family_rule_builder import BLOCKS, MECH_CLASS
            names = sorted(BLOCKS)
            want = [i for i, n in enumerate(names) if MECH_CLASS.get(n) == cls]
            if want:
                codons[0] = 0                              # <rule> -> <block>
                codons[1] = rng.choice(want)
        return {"codons": codons}

    def mutate(self, rng, g):
        c = list(g["codons"])
        for _ in range(rng.randint(1, 3)):
            c[rng.randrange(len(c))] = rng.randrange(256)
        return {"codons": c}

    def crossover(self, rng, a, b):
        i = rng.randrange(1, len(a["codons"]))
        return {"codons": a["codons"][:i] + b["codons"][i:]}

    def decode(self, codons: list[int]) -> dict | None:
        from mt5desk.family_rule_builder import BLOCKS, FILTERS
        pos = [0]
        budget = len(codons) * 3                           # at most two wraps

        def nxt(n: int) -> int:
            if pos[0] >= budget:
                raise ValueError("codons exhausted")
            v = codons[pos[0] % len(codons)]
            pos[0] += 1
            return v % n

        def block() -> dict:
            names = sorted(BLOCKS)
            b = names[nxt(len(names))]
            p = {k: v[nxt(len(v))] for k, v in sorted(BLOCKS[b][1].items())}
            return {"op": "block", "b": b, "p": p}

        def rule(depth: int) -> dict:
            choice = 0 if depth >= 3 else nxt(4)
            if choice == 0:
                return block()
            if choice == 3:
                return {"op": "not", "a": rule(depth + 1)}
            return {"op": ("and", "or")[choice - 1], "a": rule(depth + 1), "b": rule(depth + 1)}

        try:
            r = rule(0)
            filters = []
            for _ in range(nxt(3)):
                names = sorted(FILTERS)
                f = names[nxt(len(names))]
                filters.append({"f": f, **{k: v[nxt(len(v))]
                                           for k, v in sorted(FILTERS[f][1].items())}})
            ex = {k: v[nxt(len(v))] for k, v in self.EXITS.items()}
        except ValueError:
            return None
        return {"rule": r, "filters": filters, **ex}

    def params(self, g):
        return self.decode(g["codons"]) or {}

    def valid(self, g):
        return isinstance(g.get("codons"), list) and bool(self.params(g))

    def complexity(self, g):
        p = self.params(g)
        return json.dumps(p.get("rule")).count('"op"') + len(p.get("filters") or [])

    def mech_class(self, g):
        from mt5desk.family_rule_builder import MECH_CLASS
        r = self.params(g).get("rule") or {}
        while r.get("op") != "block" and r:
            r = r.get("a") or {}
        return MECH_CLASS.get(str(r.get("b")), "other")

    def describe(self, g):
        def show(r):
            if r.get("op") == "block":
                return r["b"]
            if r.get("op") == "not":
                return f"not({show(r['a'])})"
            return f"{r['op']}({show(r['a'])}, {show(r['b'])})"
        p = self.params(g)
        return (f"GE strategy {show(p['rule'])} | filters "
                f"{', '.join(f['f'] for f in p['filters']) or 'none'} | bank {p['bank_frac']}, "
                f"trail {p['runner_trail_k']}")


SPACES: dict[str, Space] = {s.seat: s for s in (KnnSpace(), RankSpace(), NeatSpace(), GeSpace())}


# --------------------------------------------------------------------------- lineage
class ModelLineage(sb.Lineage):
    """`strategy_builder.Lineage` with the genome supplied by a Space. Every rail method --
    _load's fail-closed read and ledger floor, fitness, harvest, save -- is the audited one."""

    def __init__(self, space: Space, sym: str, chart: str, d: pd.DataFrame, costs: Any,
                 seed: int | None = None, state_dir: Path | None = None):
        self.space = space
        super().__init__(sym, chart, d, costs, seed=seed,
                         state_dir=state_dir or STATE_ROOT / space.seat)

    def _load(self) -> None:
        """The audited fail-closed load (Audit MF-2), with this space's genomes filling the pop."""
        self.unreadable: str | None = None
        st: Any = {}
        if self.path.exists():
            try:
                st = json.loads(self.path.read_text("utf-8"))
            except (OSError, ValueError) as exc:
                self.unreadable = f"state unreadable: {type(exc).__name__}: {exc}"
                return
            if not isinstance(st, dict):
                self.unreadable = "state is not a JSON object"
                return
        self.pop = [g for g in st.get("pop", []) if isinstance(g, dict) and self.space.valid(g)]
        self.archive = [a for a in st.get("archive", []) if isinstance(a, dict)]
        self.evaluated_total = max(int(st.get("evaluated_total") or 0), self._ledger_floor())
        self.proposed = set(st.get("proposed") or [])
        while len(self.pop) < POP:
            self.pop.append(self.space.random(self.rng, self._scarcest_class()))

    @property
    def claim_family(self) -> str:
        from libs.research.claim_selection import claim_family_id
        return claim_family_id(self.space.seat, f"{self.sym}|{self.chart}|{self.space.family}")

    def trades(self, g: dict):
        import numpy as np
        from mt5desk.engine import run_backtest
        from mt5desk.families import get_family_func
        p = self.space.params(g)
        if not p:
            return None
        try:
            sigs = get_family_func(self.space.family)(self.visible, **p)
            res = run_backtest(self.visible, sigs, self.costs)
        except Exception:
            return None
        if not res.trades:
            return np.zeros(0, dtype="int64"), np.zeros(0)
        t = np.array([pd.Timestamp(x.entry_time).value for x in res.trades], dtype="int64")
        r = np.array([x.r_multiple for x in res.trades], dtype=float)
        return t, r

    def fitness(self, g: dict) -> float:
        """The strategy builder's rail-2 fitness verbatim (worst-fold weighted Kelly growth over
        the anchored train folds), with this space's complexity charge."""
        import itertools

        import numpy as np
        k = sb.key(g)
        if k in self._cache:
            return self._cache[k][0]
        self.evaluated_now += 1
        tr = self.trades(g)
        if tr is None:
            self._cache[k] = (-1e9, None)
            return -1e9
        t, r = tr
        vf = pd.Timestamp(self.valid_from).value
        train = t < vf
        if int(train.sum()) < sb.MIN_TRAIN_TRADES:
            self._cache[k] = (-1e6 + float(train.sum()), (t, r))
            return self._cache[k][0]
        edges = [pd.Timestamp(e).value for e in self.fold_edges]
        fold_years = self.train_years / sb.WF_FOLDS
        gs = []
        for a, b in itertools.pairwise(edges):
            m = (t >= a) & (t < b)
            gs.append(sb.kelly_growth(r[m], max(m.sum(), 1) / max(fold_years, 1e-3)))
        f = float(np.mean(gs) - 0.5 * np.std(gs)) - 0.002 * self.space.complexity(g)
        self._cache[k] = (f, (t, r))
        return f

    def evolve(self, deadline: float, max_generations: int | None = None) -> int:
        gens = 0
        while time.monotonic() < deadline and (max_generations is None
                                               or gens < max_generations):
            scored = [(self.fitness(g), g) for g in self.pop]
            scored.sort(key=lambda x: -x[0])
            self._archive(scored)
            nxt = [g for _, g in scored[:sb.ELITE]]
            tries = 0
            while len(nxt) < POP and tries < POP * 20:
                tries += 1
                u = self.rng.random()
                if u < 0.4:
                    child = self.space.crossover(self.rng, self._tour(scored), self._tour(scored))
                elif u < 0.9:
                    child = self.space.mutate(self.rng, self._tour(scored))
                else:
                    child = self.space.random(self.rng, self._scarcest_class())
                if self.space.valid(child):
                    nxt.append(child)
            self.pop = nxt
            gens += 1
        self.evaluated_total += self.evaluated_now
        return gens

    def _scarcest_class(self) -> str:
        counts = dict.fromkeys(self.space.classes, 0)
        for a in self.archive:
            c = self.space.mech_class(a["g"])
            counts[c] = counts.get(c, 0) + 1
        low = min(counts.values())
        return self.rng.choice([c for c, n in counts.items() if n == low])

    def _archive(self, scored) -> None:
        """The strategy builder's archive rule (dedup on train entries, per-class niches), with
        this space's mechanism classes."""
        vf = pd.Timestamp(self.valid_from).value
        for f, g in scored[:10]:
            if f <= 0:
                break
            k = sb.key(g)
            if any(sb.key(a["g"]) == k for a in self.archive):
                continue
            t, _ = self._cache[k][1]
            ent = {int(x) for x in t[t < vf]}
            dup = None
            for a in self.archive:
                other = set(a.get("entries") or [])
                if len(ent & other) / max(1, len(ent | other)) > sb.DUP_JACCARD:
                    dup = a
                    break
            if dup is not None:
                if f > dup["fit"]:
                    self.archive.remove(dup)
                else:
                    continue
            self.archive.append({"g": g, "fit": f, "entries": sorted(ent)})
        self.archive.sort(key=lambda a: -a["fit"])
        kept, per = [], {}
        for a in self.archive:
            c = self.space.mech_class(a["g"])
            if per.get(c, 0) < sb.ARCHIVE_PER_CLASS:
                per[c] = per.get(c, 0) + 1
                kept.append(a)
        self.archive = kept[:sb.ARCHIVE]

    def _row(self, a: dict, rv, dsr: float, p: float, train_n: int, n_trials: int) -> dict:
        g = a["g"]
        params = {**self.space.params(g), "timeframe": self.chart}
        note = (f"{self.space.seat} search on {self.sym} {self.chart}: best of {n_trials} "
                f"searched variations in this lineage; the reserved last "
                f"{int(sb.RESERVE_FRAC * 100)}% of history was never read by the search.")
        return {
            "kind": "hypothesis", "source": self.space.seat, "family": self.space.family,
            "symbol": self.sym, "symbols": [self.sym], "params": params,
            "genome": g, "mechanism": self.space.describe(g), "mechanism_status": "GENERATED",
            "mechanism_note": note, "mechanism_class": self.space.mech_class(g),
            "title": f"{self.space.family} {self.sym} {self.chart}: {self.space.describe(g)}"[:200],
            "url": "", "event_time": None,
            "claim_family": self.claim_family, "claim_selection_trials": int(n_trials),
            "breadth_unit": self.claim_family,
            "evidence": {"train_fitness": round(float(a["fit"]), 6), "train_trades": train_n,
                         "valid_trades": int(rv.size), "valid_mean_r": round(float(rv.mean()), 4),
                         "valid_dsr": round(float(dsr), 4), "valid_p": round(float(p), 6),
                         "search_trials": int(n_trials), "fdr_q": sb.FDR_Q,
                         "valid_from": str(self.valid_from),
                         "reserved_from": str(self.reserved_from),
                         "screen": "walk-forward train folds, validation once, DSR at lifetime "
                                   "lineage trials + BH-FDR; the gauntlet judges"},
        }


def _allocate(space: Space, rows: list[dict], cap: int, cov: dict, cost_bps: dict):
    """The shared breadth allocator, every candidate performance-scored (charged)."""
    try:
        from libs.ops.breadth_allocator import Candidate, Limits, allocate
    except Exception as exc:
        return sb.interleave(rows, cap), {"allocator": f"fallback interleave: {type(exc).__name__}"}
    by_id, cands = {}, []
    for r in rows:
        tf = str(r["params"].get("timeframe"))
        cid = f"{r['symbol']}|{tf}|" + sb.key(r["genome"])
        by_id[cid] = r
        cands.append(Candidate(cell_id=cid, symbol=r["symbol"], timeframe=tf,
                               family=f"{space.family}:{r.get('mechanism_class')}",
                               producer=space.seat, base_score=float(r["evidence"]["valid_dsr"]),
                               cost_bps=cost_bps.get(f"{r['symbol']}|{tf}"),
                               performance_scored=True))
    donated = cov.get("donated") or {}
    coverage = {tuple(k.split("|", 2)): int(v) for k, v in donated.items() if k.count("|") == 2}
    dec = allocate(cands, Limits(budget=cap), coverage=coverage)
    why: dict[str, int] = {}
    for _, reason in dec.deferred:
        why[reason] = why.get(reason, 0) + 1
    return [by_id[c.cell_id] for c in dec.selected], {
        "allocator": "libs.ops.breadth_allocator", "deferred_by_reason": why,
        "charged": len(getattr(dec, "charged", rows) or rows),
        "charged_basis": "whole harvest registered via claim_selection.register_grid"}


def run(space: Space, budget_s: float = 240.0, n_symbols: int = 4, chart: str | None = None,
        dry_run: bool = False, symbols: list[str] | None = None, state_dir: Path | None = None,
        loader=None, meta: dict | None = None, seed: int | None = None,
        max_generations: int | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    state_dir = Path(state_dir or STATE_ROOT / space.seat)
    if meta is None:
        try:
            meta = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))
        except (OSError, ValueError):
            meta = {}
    if symbols is None:
        symbols = sb._legal_symbols()
    if loader is None:
        from htf_anchor_proposer import _bars
        loader = _bars
    charts = (chart,) if chart else sb.CHARTS
    cov = sb._coverage(state_dir / "coverage.json")
    cells, refused = sb.pick_cells(symbols, n_symbols, loader, meta, cov, charts)
    per = max(10.0, budget_s * 0.85 / max(1, len(cells)))
    found: list[dict] = []
    lineages: dict[tuple[str, str], ModelLineage] = {}
    stats: dict[str, Any] = {}
    for sym, ch, d, costs in cells:
        lin = ModelLineage(space, sym, ch, d, costs, seed=seed, state_dir=state_dir)
        if lin.unreadable:
            stats[f"{sym}|{ch}"] = {"skipped": lin.unreadable}
            continue
        gens = lin.evolve(time.monotonic() + per, max_generations)
        rows = lin.harvest()
        lineages[(sym, ch)] = lin
        found += rows
        classes: dict[str, int] = {}
        for a in lin.archive:
            c = space.mech_class(a["g"])
            classes[c] = classes.get(c, 0) + 1
        stats[f"{sym}|{ch}"] = {"generations": gens, "evaluated_pass": lin.evaluated_now,
                                "evaluated_lifetime": lin.evaluated_total,
                                "archive": len(lin.archive), "archive_classes": classes,
                                "survivors": len(rows)}
    budget = sb.intake_budget()
    cost_bps = {f"{s}|{c}": v for s, c, v in
                ((s, c, sb._cost_bps(d, k)) for s, c, d, k in cells) if v is not None}
    donate_rows, alloc = _allocate(space, found, budget["cap"], cov, cost_bps)
    donated = None
    lineage_reg: Any = None
    tests = sum(int(s.get("evaluated_pass") or 0) for s in stats.values())
    if donate_rows and not dry_run:
        registered = False                                 # no charge, no donation (MF-1)
        try:
            from libs.research.claim_selection import register_grid
            lineage_reg = register_grid(found)
            have = set((lineage_reg or {}).get("claim_families") or {})
            need = {r["claim_family"] for r in donate_rows}
            registered = need <= have
            if not registered:
                lineage_reg = {**(lineage_reg or {}),
                               "status": f"INCOMPLETE: {len(need - have)} lineage(s) unregistered"}
        except Exception as exc:
            lineage_reg = {"status": f"FAILED: {type(exc).__name__}: {exc}"}
        if registered:
            from proposer_common import donate
            donated = donate(space.seat, donate_rows, tests_run=tests)
        if donated is not None:
            for r in donate_rows:
                lineages[(r["symbol"], r["params"]["timeframe"])].proposed.add(sb.key(r["genome"]))
    if not dry_run:
        for lin in lineages.values():
            lin.save()
        passes = cov.setdefault("passes", {})
        for (s, c) in lineages:
            passes[f"{s}|{c}"] = int(passes.get(f"{s}|{c}", 0)) + 1
        cov["refused_fill_cost"] = refused
        if donated is not None:
            dn = cov.setdefault("donated", {})
            for r in donate_rows:
                k = (f"{r['symbol']}|{r['params']['timeframe']}|"
                     f"{space.family}:{r.get('mechanism_class')}")
                dn[k] = int(dn.get(k, 0)) + 1
        cov["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "coverage.json").write_text(json.dumps(cov, indent=1), "utf-8")
    rep = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "seat": space.seat,
           "family": space.family, "cells": stats, "refused_fill_cost": refused,
           "tests_run": tests, "survivors": len(found), "intake_budget": budget,
           "allocation": alloc, "donated": len(donate_rows) if donated is not None else 0,
           "donation_path": str(donated) if donated else None,
           "waiting_ranked": max(0, len(found) - len(donate_rows)),
           "lineage_registration": lineage_reg, "seconds": round(time.monotonic() - t0, 1),
           "breadth": {"cells_searched_ever": len(cov.get("passes") or {}),
                       "cells_possible": len(symbols) * len(charts),
                       "survivor_classes": sorted({r.get("mechanism_class") for r in found}),
                       "donated_symbols": len({r["symbol"] for r in donate_rows})},
           "rails": "strategy_builder.Lineage (Auditor CLEAR fe91dd889)"}
    if not dry_run:
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / f"HYPGEN_{space.seat.upper()}.json").write_text(
            json.dumps(rep, indent=1, default=str), "utf-8")
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--space", required=True, choices=sorted(SPACES))
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--symbols", type=int, default=4)
    ap.add_argument("--chart", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    rep = run(SPACES[a.space], budget_s=a.budget_s, n_symbols=a.symbols, chart=a.chart,
              dry_run=a.dry_run)
    print(f"HYPGEN {a.space}  {len(rep['cells'])} cells, {rep['tests_run']} tried, "
          f"{rep['survivors']} survived, {rep['donated']} donated "
          f"({rep['intake_budget']['basis']})")
    print(sb.YIELD_PREFIX + json.dumps({"cells_proposed": rep["donated"],
                                        "candidates": rep["survivors"],
                                        "tests_run": rep["tests_run"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
