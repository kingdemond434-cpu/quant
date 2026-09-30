"""EVOLUTION OF PROGRAMS, RESEARCHERS AND GRAMMARS (Tier S layers 5, 6, 7, 22, 44).

One engine, three populations:

  * RESEARCH PROGRAMS / RESEARCHER GENOMES (layers 5, 7). A genome is a dict of discrete and
    continuous genes -- data-selection policy, operator set, mutation probabilities, horizon set,
    falsification order, novelty criterion, exploration ratio, compute policy. Fitness is NOT
    Sharpe: it is validated independent information per unit of compute, penalised for
    complexity, false discoveries, duplicated ideas and live degradation. `step()` is one
    generation: tournament selection, crossover, mutation, elitism.

  * MAP-ELITES (layer 6). `Archive` keeps the best individual per NICHE, a tuple of behaviour
    descriptors (mechanism x horizon x asset class x region x regime x turnover x holding x
    complexity x data dependency x capacity x cluster -- whatever axes the caller passes). Its
    `empty_niches()` and `weak_niches()` are generation REQUESTS: the archive decides where the
    next search goes instead of recording where the last one went.

  * GRAMMARS AND ABSTRACTIONS (layers 22, 44). `operator_yield()` scores each production rule of a
    hypothesis grammar by the survivors it appears in per use; rules below a yield floor are
    RETIRED from sampling weight (never deleted) and new composite rules are ADDED. `abstractions()`
    mines recurring sub-expressions across survivor programs -- a subtree that recurs in several
    independent survivors is a candidate PRIMITIVE, named by its hash, that later researchers can
    use as a single token. That is library learning: the system invents vocabulary.
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from libs.tiers.truth_kernel import canon, sha256

Genome = dict[str, Any]


@dataclass(frozen=True)
class Gene:
    name: str
    choices: tuple[Any, ...] = ()
    lo: float | None = None
    hi: float | None = None


RESEARCHER_GENES: tuple[Gene, ...] = (
    Gene("data_policy", ("bars_only", "bars+macro", "bars+cot", "bars+events", "cross_asset")),
    Gene("operator_set", ("momentum", "reversion", "carry", "seasonal", "breakout",
                          "vol_regime", "lead_lag", "mixed")),
    Gene("horizon", ("M15", "H1", "H4", "D1")),
    Gene("falsify_order", ("cost_first", "lookahead_first", "stability_first", "dsr_first")),
    Gene("novelty", ("species", "exposure", "tail", "ancestry")),
    Gene("mutation_rate", lo=0.02, hi=0.5),
    Gene("exploration", lo=0.05, hi=0.8),
    Gene("complexity_cap", lo=2.0, hi=12.0),
    # what the researcher may LOOK AT (the family's information source, axis_registry's word)
    Gene("feature_language", ("price_only", "seasonality", "positioning", "cross_asset",
                              "microstructure", "any")),
    # where its ideas come from: its own operator draw, the hypothesis graph's unjudged births,
    # the neighbourhood of what already survived, or the region failures have NOT yet mapped
    Gene("source", ("own", "hypothesis_graph", "survivor_neighbourhood", "failure_gap")),
)


def complete(g: Genome, rng: np.random.Generator,
             genes: Sequence[Gene] = RESEARCHER_GENES) -> Genome:
    """A genome from an older gene set, with every gene it lacks drawn fresh."""
    fresh = random_genome(rng, genes)
    return {**fresh, **{k: v for k, v in g.items() if k in fresh}}


def genome_id(g: Genome) -> str:
    return "g" + sha256(canon(g))[:12]


def random_genome(rng: np.random.Generator, genes: Sequence[Gene] = RESEARCHER_GENES) -> Genome:
    out: Genome = {}
    for gene in genes:
        if gene.choices:
            out[gene.name] = gene.choices[int(rng.integers(len(gene.choices)))]
        else:
            lo, hi = float(gene.lo or 0.0), float(gene.hi or 1.0)
            out[gene.name] = round(float(rng.uniform(lo, hi)), 4)
    return out


def mutate(g: Genome, rng: np.random.Generator, rate: float,
           genes: Sequence[Gene] = RESEARCHER_GENES) -> Genome:
    out = dict(g)
    for gene in genes:
        if rng.random() >= rate:
            continue
        if gene.choices:
            out[gene.name] = gene.choices[int(rng.integers(len(gene.choices)))]
        else:
            lo, hi = float(gene.lo or 0.0), float(gene.hi or 1.0)
            v = float(out.get(gene.name, (lo + hi) / 2)) + float(rng.normal(0, (hi - lo) * 0.15))
            out[gene.name] = round(min(hi, max(lo, v)), 4)
    return out


def crossover(a: Genome, b: Genome, rng: np.random.Generator) -> Genome:
    return {k: (a if rng.random() < 0.5 else b).get(k, a.get(k)) for k in set(a) | set(b)}


def fitness(stats: Mapping[str, float]) -> float:
    """Validated independent information per compute, with the principal's penalties."""
    info = float(stats.get("validated_independent", 0.0))
    compute = max(float(stats.get("compute_s", 1.0)), 1.0)
    pen = (1.0 + 0.05 * float(stats.get("complexity", 0.0))
           + 1.0 * float(stats.get("false_discoveries", 0.0))
           + 0.5 * float(stats.get("duplicates", 0.0))
           + 2.0 * float(stats.get("live_degradation", 0.0))
           + 0.2 * float(stats.get("mining_pressure", 0.0)))
    return 3600.0 * info / compute / pen


def step(population: Sequence[tuple[Genome, float]], rng: np.random.Generator, *,
         size: int | None = None, elite: int = 2, tournament: int = 3,
         genes: Sequence[Gene] = RESEARCHER_GENES) -> list[Genome]:
    """One generation. population = [(genome, fitness)]. Returns the next genomes."""
    if not population:
        return [random_genome(rng, genes) for _ in range(size or 8)]
    size = size or len(population)
    ranked = sorted(population, key=lambda gf: -gf[1])
    nxt = [dict(g) for g, _f in ranked[:elite]]

    def pick() -> Genome:
        idx = rng.integers(len(ranked), size=min(tournament, len(ranked)))
        return max((ranked[int(i)] for i in idx), key=lambda gf: gf[1])[0]

    while len(nxt) < size:
        child = crossover(pick(), pick(), rng)
        rate = float(child.get("mutation_rate", 0.2))
        nxt.append(mutate(child, rng, rate, genes))
    return nxt


# ------------------------------------------------------------------------------------------------
# MAP-Elites
# ------------------------------------------------------------------------------------------------

@dataclass
class Archive:
    axes: tuple[str, ...]
    cells: dict[tuple[str, ...], dict[str, Any]] = field(default_factory=dict)
    #: every value seen per axis, so empty niches are enumerable
    domain: dict[str, set[str]] = field(default_factory=dict)

    def niche(self, desc: Mapping[str, Any]) -> tuple[str, ...]:
        return tuple(str(desc.get(a, "?")) for a in self.axes)

    def add(self, item_id: str, desc: Mapping[str, Any], quality: float) -> bool:
        key = self.niche(desc)
        for a, v in zip(self.axes, key, strict=True):
            self.domain.setdefault(a, set()).add(v)
        cur = self.cells.get(key)
        if cur is None or quality > float(cur["quality"]):
            self.cells[key] = {"id": item_id, "quality": quality, "desc": dict(desc)}
            return True
        return False

    def coverage(self) -> dict[str, Any]:
        possible = 1
        for a in self.axes:
            possible *= max(1, len(self.domain.get(a, {"?"})))
        return {"filled": len(self.cells), "possible": possible,
                "share": len(self.cells) / possible if possible else None,
                "qd_score": round(sum(max(0.0, float(c["quality"]))
                                      for c in self.cells.values()), 4)}

    def marginal_empty(self, axis_pairs: Sequence[tuple[str, str]] | None = None, top: int = 20
                       ) -> list[dict[str, Any]]:
        """Empty 2-D projections: (axis a value, axis b value) combos no elite occupies. The full
        product is astronomically sparse, so requests are made in pairwise projections."""
        pairs = axis_pairs or [(self.axes[i], self.axes[j]) for i in range(len(self.axes))
                               for j in range(i + 1, len(self.axes))]
        idx = {a: i for i, a in enumerate(self.axes)}
        out: list[dict[str, Any]] = []
        for a, b in pairs:
            have = {(k[idx[a]], k[idx[b]]) for k in self.cells}
            for va in sorted(self.domain.get(a, set())):
                for vb in sorted(self.domain.get(b, set())):
                    if (va, vb) not in have and "?" not in (va, vb):
                        out.append({a: va, b: vb})
        return out[:top]

    def weak(self, top: int = 20) -> list[dict[str, Any]]:
        rows = sorted(self.cells.items(), key=lambda kv: float(kv[1]["quality"]))
        return [{"niche": dict(zip(self.axes, k, strict=True)), "quality": v["quality"]}
                for k, v in rows[:top]]


# ------------------------------------------------------------------------------------------------
# Grammar yield and abstraction discovery
# ------------------------------------------------------------------------------------------------

_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def operator_yield(programs: Sequence[tuple[str, bool]], operators: Sequence[str] | None = None,
                   floor: float = 0.25) -> dict[str, Any]:
    """programs: (expression, survived). Yield per operator = survivor rate relative to the
    population's, with a Beta(1,1) prior. Operators below `floor` x baseline are RETIRED from
    sampling weight; the weights are what a grammar sampler should use next."""
    n = len(programs)
    base = (sum(1 for _e, s in programs if s) + 1) / (n + 2)
    uses: Counter[str] = Counter()
    wins: Counter[str] = Counter()
    for expr, ok in programs:
        toks = set(_TOKEN.findall(expr))
        if operators is not None:
            toks &= set(operators)
        for t in toks:
            uses[t] += 1
            wins[t] += int(ok)
    rows = {}
    for t in sorted(uses):
        rate = (wins[t] + 1) / (uses[t] + 2)
        lift = rate / base if base > 0 else 1.0
        rows[t] = {"uses": uses[t], "survivors": wins[t], "lift": round(lift, 4),
                   "weight": round(max(0.05, min(4.0, lift)), 4),
                   "status": "RETIRED" if lift < floor and uses[t] >= 10 else "ACTIVE"}
    return {"baseline_rate": round(base, 6), "operators": rows,
            "retired": [t for t, r in rows.items() if r["status"] == "RETIRED"]}


def _subtrees(expr: str) -> list[str]:
    """Balanced parenthesised sub-expressions, normalised for spacing."""
    out: list[str] = []
    stack: list[int] = []
    for i, ch in enumerate(expr):
        if ch == "(":
            stack.append(i)
        elif ch == ")" and stack:
            j = stack.pop()
            k = j
            while k > 0 and (expr[k - 1].isalnum() or expr[k - 1] == "_"):
                k -= 1
            sub = re.sub(r"\s+", "", expr[k:i + 1])
            if len(sub) >= 6:
                out.append(sub)
    return out


def abstractions(survivors: Sequence[str], min_support: int = 3, top: int = 25,
                 is_independent: Callable[[int, int], bool] | None = None) -> dict[str, Any]:
    """Recurring sub-expressions across DISTINCT survivor programs become named primitives."""
    support: dict[str, set[int]] = {}
    for i, expr in enumerate(survivors):
        for sub in set(_subtrees(expr)):
            support.setdefault(sub, set()).add(i)
    rows: list[dict[str, Any]] = []
    for sub, ids in support.items():
        idl = sorted(ids)
        if is_independent is not None:
            # count only survivors that are pairwise independent (not each other's descendants)
            kept: list[int] = []
            for i in idl:
                if all(is_independent(i, j) for j in kept):
                    kept.append(i)
            idl = kept
        if len(idl) >= min_support:
            rows.append({"primitive": "P_" + sha256(sub)[:8], "expression": sub,
                         "support": len(idl), "size": len(sub),
                         "compression": round(len(idl) * (len(sub) - 10) / 100.0, 3)})
    rows.sort(key=lambda r: (-float(r["compression"]), str(r["primitive"])))
    return {"n_survivors": len(survivors), "primitives": rows[:top],
            "n_primitives": len(rows)}


def complexity(expr: str) -> float:
    return float(len(_TOKEN.findall(expr))) + 0.5 * expr.count("(")


def diversity(genomes: Sequence[Genome]) -> float:
    """Mean pairwise Hamming distance share -- a population that collapsed reads near 0."""
    if len(genomes) < 2:
        return 0.0
    keys = sorted(set().union(*[set(g) for g in genomes]))
    tot = 0.0
    n = 0
    for i in range(len(genomes)):
        for j in range(i + 1, len(genomes)):
            d = sum(1 for k in keys if genomes[i].get(k) != genomes[j].get(k))
            tot += d / max(1, len(keys))
            n += 1
    return round(tot / n, 4) if n else 0.0

