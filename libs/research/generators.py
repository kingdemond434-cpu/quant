"""Generators for the alpha grammar beyond uniform random trees.

WHY MORE THAN ONE GENERATOR. `alpha_grammar.random_expr` draws trees uniformly over the closed
operator set, so every generation of the evolution spends most of its budget re-discovering that
`corr(spread, spread, 5)` is not an alpha. Two published ideas fix different halves of that waste,
and neither needs a neural network to earn its place at one desk's scale:

    GFLOWNET (`GFlowNet`). A generative flow network over the grammar, trained by trajectory
        balance. A tree is built top-down one open slot at a time, and every slot carries the
        KIND set -- dtype AND unit -- the grammar will accept there, so the only actions that
        exist are the ones that can still be completed into a valid, well-typed, well-formed
        tree: no rejection loop, and no way to propose `add(std(close, 24), std(ret, 24))`.
        (Before 2026-09-05 the mask was keyed on the dtype alone and the sampler routinely
        emitted trees the grammar then refused -- a bar count added to a ratio, a price
        dispersion added to a pure number. Nothing rejects those now because nothing proposes
        them; see `_TypeAlgebra`.)
        The forward policy is a softmax over those actions under a linear model on hashed
        (state, action) features, and training drives log Z + sum log P_F(a|s) toward
        log R(x) with R = exp(beta x fitness): at the optimum a tree is drawn with probability
        proportional to its reward, which is what "sample in proportion to what the history
        rewarded" means once it is more than a slogan. Before training every allowed action
        is equally likely, so the untrained network is a random generator with a different
        shape prior; `GENERATORS["gflow"]` is this network, fitted on the history it is handed.

    FLOW TABLE (`FlowSampler`). The earlier, table-only reading of the same idea: a transition's
        weight is exp(temperature x smoothed mean fitness of the trees that contained it), and
        a tree is grown top-down by those weights. Kept because it is legible in a report
        (`table`) and because it is the baseline a trained network has to beat to deserve the
        slot; it no longer sits behind the generator surface.

    SYMBOLIC REGRESSION (`symbolic_regression`). A hill-climb on the grammar's own mutation move
        toward the expression whose z-scored value best fits a supervised target on the FIRST
        70% of the history. The holdout error on the remaining 30% is reported beside the result
        and NEVER used to choose it: the output is an expression the gauntlet then judges on its
        own terms, with the fit slice named so nobody mistakes in-sample fit for edge.

ONE SIGNATURE. Every generator is (rng, frames, ret, history, allow_drivers, max_depth) -> Expr,
so the evolution can pick between them by weight and record which one produced each individual.
`choose_generator` reads a weight table (uniform when there is none). The weights are meant to
be WRITTEN by a yield ledger that scores each generator by what its individuals went on to
certify; this module never scores itself.

NOTHING HERE HAS AUTHORITY. A generated expression is a trial like any other: charged as one,
screened and deflated by the evolution, judged by the gauntlet.
"""
from __future__ import annotations

import json
import math
import zlib
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from libs.research import alpha_grammar as ag

Expr = Any                                      # str | list[Any]; JSON-shaped (alpha_grammar)
History = Sequence[tuple[Any, float]]
Generator = Callable[[np.random.Generator, dict[str, pd.Series], pd.Series, History, bool, int],
                     Any]
RewardFn = Callable[[Any], float]

ROOT_NODE = "<root>"
#: Flow-table defaults. Temperature scales fitness differences into odds; the prior count is
#: how many pseudo-observations at the population mean a transition carries before its own
#: evidence dominates, so one lucky tree cannot own a transition.
TEMPERATURE = 1.0
PRIOR_COUNT = 2.0
MAX_TRIES = 20
EXP_CLIP = 30.0
#: GFlowNet defaults. 4096 signed buckets for a few hundred distinct (state, action) features
#: is sparse enough that collisions are rare and small enough that the whole model is a page
#: of floats, not a file. beta turns a fitness gap into a reward ratio (2.0: one fitness point
#: is e^2 to one); the reward floor keeps log R finite for a tree far below the best.
N_BUCKETS = 4096
EPOCHS, LR, BETA, BATCH_SIZE = 20, 0.05, 2.0, 32
REWARD_EPS = 1e-8
ADAM_BETA1, ADAM_BETA2, ADAM_EPS = 0.9, 0.999, 1e-8
#: Action ids: operators and terminals are their own names (disjoint sets); a window is "w<n>".
WINDOW_ACTIONS: tuple[str, ...] = tuple(f"w{w}" for w in ag.WINDOWS)
N_FEATURES = 5
#: Symbolic-regression defaults: the train slice, and the fewest finite train observations a
#: candidate needs before its error means anything.
TRAIN_FRAC = 0.70
MIN_OBS = 50

#: The last symbolic-regression fit -- train and holdout error, slice sizes -- for the caller
#: that wants them beside the expression (the shared generator signature returns only the tree).
LAST_FIT: dict[str, Any] = {}


# --------------------------------------------------------------------------- flow sampler
def _token(x: Expr) -> str:
    return x if isinstance(x, str) else str(x[0])


def transitions(expr: Expr) -> set[tuple[str, str]]:
    """The (parent -> child token) edges of a tree, plus (root -> first token)."""
    out: set[tuple[str, str]] = {(ROOT_NODE, _token(expr))}

    def _walk(x: Expr) -> None:
        if not isinstance(x, (list, tuple)) or not x:
            return
        op = str(x[0])
        for c in x[1:]:
            if isinstance(c, (str, list, tuple)):
                out.add((op, _token(c)))
                _walk(c)
    _walk(expr)
    return out


class FlowSampler:
    """Transition weights learned from (expression, fitness) history; trees grown by them."""

    def __init__(self, history: History = (), *, temperature: float = TEMPERATURE,
                 prior_count: float = PRIOR_COUNT) -> None:
        self.temperature = float(temperature)
        self.prior_count = float(prior_count)
        self.prior_mean = 0.0
        self.n_history = 0
        self._sum: dict[tuple[str, str], float] = {}
        self._n: dict[tuple[str, str], int] = {}
        self.fit(history)

    def fit(self, history: History) -> FlowSampler:
        """Accumulate per-transition fitness sums and counts. Non-finite fitness is skipped."""
        rows: list[tuple[Expr, float]] = []
        for expr, fit in history:
            try:
                f = float(fit)
            except (TypeError, ValueError):
                continue
            if math.isfinite(f):
                rows.append((expr, f))
        self.n_history += len(rows)
        if rows:
            total = self.prior_mean * (self.n_history - len(rows)) + sum(f for _, f in rows)
            self.prior_mean = total / self.n_history
        for expr, f in rows:
            for t in transitions(expr):
                self._sum[t] = self._sum.get(t, 0.0) + f
                self._n[t] = self._n.get(t, 0) + 1
        return self

    def mean_fitness(self, parent: str, child: str) -> float:
        """Smoothed mean fitness of trees carrying the transition: the population mean counts
        `prior_count` times, so an unseen transition sits at the mean rather than at zero."""
        n = self._n.get((parent, child), 0)
        s = self._sum.get((parent, child), 0.0)
        return (s + self.prior_count * self.prior_mean) / (n + self.prior_count)

    def weight(self, parent: str, child: str) -> float:
        """exp(temperature x mean fitness), centred on the population mean. Centring changes
        no sampling probability (a common factor per parent) and keeps the exponent bounded."""
        x = self.temperature * (self.mean_fitness(parent, child) - self.prior_mean)
        return math.exp(max(-EXP_CLIP, min(EXP_CLIP, x)))

    def _pick(self, rng: np.random.Generator, parent: str, cands: list[str]) -> str:
        w = np.array([self.weight(parent, c) for c in cands], dtype=float)
        p = w / w.sum()
        return str(cands[int(rng.choice(len(cands), p=p))])

    def _grow(self, rng: np.random.Generator, parent: str, depth: int, max_depth: int,
              allow_drivers: bool) -> Expr:
        terms = list(ag.TERMINALS if allow_drivers else ag.BAR_TERMINALS)
        if depth >= max_depth:
            return self._pick(rng, parent, terms)
        # The root is always an operator: a bare terminal is a level, not an alpha.
        cands = list(ag.OPERATORS) + (terms if depth > 0 else [])
        tok = self._pick(rng, parent, cands)
        if tok in terms:
            return tok
        w = int(rng.choice(ag.WINDOWS))
        if tok in ag.UNARY:
            return [tok, self._grow(rng, tok, depth + 1, max_depth, allow_drivers)]
        if tok in ag.WINDOWED:
            return [tok, self._grow(rng, tok, depth + 1, max_depth, allow_drivers), w]
        if tok in ag.BINARY:
            return [tok, self._grow(rng, tok, depth + 1, max_depth, allow_drivers),
                    self._grow(rng, tok, depth + 1, max_depth, allow_drivers)]
        return [tok, self._grow(rng, tok, depth + 1, max_depth, allow_drivers),
                self._grow(rng, tok, depth + 1, max_depth, allow_drivers), w]

    def sample(self, rng: np.random.Generator, max_depth: int = 3,
               allow_drivers: bool = True) -> Expr:
        """A valid tree grown by the learned weights; `random_expr` after MAX_TRIES failures."""
        for _ in range(MAX_TRIES):
            e = self._grow(rng, ROOT_NODE, 0, max_depth, allow_drivers)
            if ag.is_valid(e, allow_drivers):
                return e
        return ag.random_expr(rng, max_depth, allow_drivers)

    def table(self, top: int = 20) -> list[dict[str, Any]]:
        """The strongest transitions, for a report: what the sampler has learned to prefer."""
        rows: list[dict[str, Any]] = [
            {"parent": p, "child": c, "n": n,
             "mean_fitness": round(self.mean_fitness(p, c), 4),
             "weight": round(self.weight(p, c), 4)}
            for (p, c), n in self._n.items()]
        rows.sort(key=lambda r: -float(r["weight"]))
        return rows[:top]


# --------------------------------------------------------------------------- gflownet: types
#: How far the PLANNER follows the unit algebra. `mul` adds unit exponents and `div` subtracts,
#: so the set of units reachable from a price is infinite (quote, quote^2, quote^3, ...) and a
#: sampler that enumerates it never finishes. Two bases with exponents in [-2, 2] holds every
#: unit an alpha on this desk has ever wanted -- a price, a ratio, a price-volume covariance --
#: and nothing that ships needs a price to the fourth power. This bounds the SEARCH, never the
#: grammar: `unit_of` types quote^4 and `is_valid` accepts it; this sampler just never plans one.
UNIT_EXPONENT_CAP = 1
UNIT_BASES_CAP = 2


def _unit_label(expr: Expr) -> str:
    u = ag.unit_of(expr)
    return ag.INVALID if u is None else str(u)


def _bounded_unit(label: str) -> bool:
    """Is this unit inside the planner's bound? Parsed from the label the algebra prints."""
    if label == ag.INVALID:
        return False
    if label == "1":
        return True
    parts = label.split(" ")
    if len(parts) > UNIT_BASES_CAP:
        return False
    for p in parts:
        _base, _, power = p.partition("^")
        try:
            if abs(int(power)) > UNIT_EXPONENT_CAP:
                return False
        except ValueError:
            return False
    return True


class _TypeAlgebra:
    """`alpha_grammar.kind_of` as lookup tables, derived from it rather than transcribed.

    A KIND is a dtype and a unit together (`"PRICE@quote^1"`), which is exactly what the
    grammar's production screen checks, so planning over kinds is what makes an illegal action
    UNOFFERABLE rather than merely rejectable. Before 2026-09-05 these tables were keyed on the
    dtype alone: `add(bars_since_min(x, 3), body)` -- a bar count plus a pure ratio, same dtype
    family, different units -- was an action the sampler offered and a tree it emitted, and the
    grammar then refused the finished tree. Nothing rejects it now because nothing proposes it.

    DERIVED, NOT TRANSCRIBED, AND FACTORED. `type_of` reads only its children's DTYPES and
    `unit_of` only their UNITS -- no rule in the grammar mixes the two -- so the kind table is
    the exact product of a dtype table and a unit table, and each is built by asking the grammar
    itself about a witness tree. That factoring is not a micro-optimisation: the joint table
    built witness-by-witness costs |kinds|^2 tree walks per round, and with compound units the
    kind universe is in the hundreds. The product costs |dtypes|^2 + |units|^2 walks once and
    then O(1) lookups, and it cannot disagree with the grammar because both halves came from it.

    THE UNIT UNIVERSE IS BOUNDED BY `UNIT_EXPONENT_CAP` AND `UNIT_BASES_CAP`, and it has to be:
    `mul` adds unit exponents, so quote, quote^2, quote^3 ... is an infinite closure and a
    planner that enumerates it never finishes. The bound is a SEARCH bound, not a validity one --
    `unit_of` still types quote^4 and `is_valid` still accepts a tree carrying it; this sampler
    simply never plans one, and `trajectory` reports such a tree as unreplayable (counted in
    `last_fit["skipped"]`) rather than pretending to have built it. Nothing that ships depends
    on a price to the fourth power.
    """

    def __init__(self) -> None:
        w = int(ag.WINDOWS[2])
        # Two independent axes, each derived by asking the grammar about a witness tree.
        _dtypes, self._dt_unary, self._dt_binary = self._closure(
            {ag.DTYPES[t]: t for t in reversed(ag.TERMINALS)}, ag.type_of, w, lambda _o: True)
        _units, self._u_unary, self._u_binary = self._closure(
            {str(ag.TERMINAL_UNITS[t]): t for t in reversed(ag.TERMINALS)},
            _unit_label, w, _bounded_unit)
        # The valid dtype triples per operator, so the joint closure below never enumerates a
        # unit pair under a dtype pair that is already meaningless.
        self._dt_pairs: dict[str, tuple[tuple[str, str, str], ...]] = {
            op: tuple((a, b, o) for (o_op, a, b), o in self._dt_binary.items()
                      if o_op == op and o != ag.INVALID)
            for op in ag.BINARY + ag.BINARY_WINDOWED}
        self._parts: dict[str, tuple[str, str]] = {}
        self._products: dict[tuple[str, frozenset[str], frozenset[str]], frozenset[str]] = {}
        self.all: frozenset[str] = self._joint_closure(
            frozenset(ag.TERMINAL_KINDS.values()))
        self._reach: dict[tuple[int, frozenset[str]], frozenset[str]] = {}
        self._want: dict[tuple[Any, ...], frozenset[str]] = {}
        self._allowed: dict[tuple[Any, ...], tuple[str, ...]] = {}

    # ----------------------------------------------------------------- the two axes
    @staticmethod
    def _closure(seed: dict[str, Expr], label: Callable[[Expr], str], w: int,
                 keep: Callable[[str], bool],
                 ) -> tuple[frozenset[str], dict[tuple[str, str], str],
                            dict[tuple[str, str, str], str]]:
        """One axis of the algebra: every operator's output label on every reachable label.

        The witness for a label is the shallowest tree found carrying it, so the grammar walks
        it cheaply; `keep` is the axis's bound (always true for dtypes, the caps for units).
        """
        witness = dict(seed)
        unary: dict[tuple[str, str], str] = {}
        binary: dict[tuple[str, str, str], str] = {}
        for _round in range(ag.MAX_DEPTH):
            grew = False
            for t in sorted(witness):
                for op in ag.UNARY + ag.WINDOWED:
                    e = [op, witness[t]] if op in ag.UNARY else [op, witness[t], w]
                    o = label(e)
                    unary[(op, t)] = o if keep(o) else ag.INVALID
                    if o != ag.INVALID and o not in witness and keep(o):
                        witness[o], grew = e, True
            for a in sorted(witness):
                for b in sorted(witness):
                    for op in ag.BINARY + ag.BINARY_WINDOWED:
                        e = ([op, witness[a], witness[b]] if op in ag.BINARY
                             else [op, witness[a], witness[b], w])
                        o = label(e)
                        binary[(op, a, b)] = o if keep(o) else ag.INVALID
                        if o != ag.INVALID and o not in witness and keep(o):
                            witness[o], grew = e, True
            if not grew:
                break
        return frozenset(witness), unary, binary

    # ----------------------------------------------------------------- the joint algebra
    def _split(self, kind: str) -> tuple[str, str]:
        hit = self._parts.get(kind)
        if hit is None:
            dtype, _, unit = kind.partition("@")
            hit = self._parts[kind] = (dtype, unit)
        return hit

    def unary_kind(self, op: str, kind: str) -> str:
        """The kind of `op(x)` when x has `kind`; INVALID when either axis refuses."""
        t, u = self._split(kind)
        to = self._dt_unary.get((op, t), ag.INVALID)
        uo = self._u_unary.get((op, u), ag.INVALID)
        return ag.INVALID if ag.INVALID in (to, uo) else f"{to}@{uo}"

    def binary_kind(self, op: str, a: str, b: str) -> str:
        """The kind of `op(x, y)` when x, y have kinds `a`, `b`; INVALID when either refuses."""
        ta, ua = self._split(a)
        tb, ub = self._split(b)
        to = self._dt_binary.get((op, ta, tb), ag.INVALID)
        if to == ag.INVALID:
            return ag.INVALID
        uo = self._u_binary.get((op, ua, ub), ag.INVALID)
        return ag.INVALID if uo == ag.INVALID else f"{to}@{uo}"

    def _by_dtype(self, kinds: Iterable[str]) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {}
        for k in kinds:
            t, u = self._split(k)
            out.setdefault(t, set()).add(u)
        return out

    def _unit_products(self, op: str, a: frozenset[str],
                       b: frozenset[str]) -> frozenset[str]:
        """Every unit `op` can produce from a unit in `a` and one in `b`, memoised.

        The same pair of unit SETS recurs across dozens of dtype pairs -- most dtypes carry the
        same handful of units -- so memoising on the sets rather than recomputing per dtype pair
        is the difference between a table that builds in a second and one that builds in ten.
        """
        key = (op, a, b)
        hit = self._products.get(key)
        if hit is None:
            out = {self._u_binary.get((op, ua, ub), ag.INVALID) for ua in a for ub in b}
            hit = self._products[key] = frozenset(out - {ag.INVALID})
        return hit

    def _grow(self, cur: frozenset[str]) -> frozenset[str]:
        """One level of construction: every kind reachable by applying one operator to `cur`."""
        nxt = set(cur)
        for k in cur:
            for op in ag.UNARY + ag.WINDOWED:
                o = self.unary_kind(op, k)
                if o != ag.INVALID:
                    nxt.add(o)
        by_dtype = {t: frozenset(u) for t, u in self._by_dtype(cur).items()}
        for op in ag.BINARY + ag.BINARY_WINDOWED:
            for ta, tb, to in self._dt_pairs[op]:
                ua_set, ub_set = by_dtype.get(ta), by_dtype.get(tb)
                if not ua_set or not ub_set:
                    continue
                nxt.update(f"{to}@{uo}" for uo in self._unit_products(op, ua_set, ub_set))
        return frozenset(nxt)

    def _joint_closure(self, leaves: frozenset[str]) -> frozenset[str]:
        cur = leaves
        for _ in range(ag.MAX_DEPTH):
            nxt = self._grow(cur)
            if nxt == cur:
                break
            cur = nxt
        return cur

    def reach(self, remaining: int, leaf_types: frozenset[str]) -> frozenset[str]:
        """The kinds a subtree can have when `remaining` more levels may be built under it."""
        key = (remaining, leaf_types)
        if key not in self._reach:
            cur = leaf_types
            for r in range(max(0, remaining)):
                nxt = self._grow(cur)
                self._reach[(r + 1, leaf_types)] = nxt
                if nxt == cur:
                    break
                cur = nxt
            self._reach.setdefault(key, cur)
        return self._reach[key]

    def child_want(self, op: str, index: int, want: frozenset[str], sibling: str | None,
                   sibling_reach: frozenset[str]) -> frozenset[str]:
        """The kinds the `index`-th child of `op` may take so the node's kind lands in `want`.

        A binary node's first child is built before its second exists, so any partner the
        sibling could still become (`sibling_reach`) counts; for the second child the first's
        kind `sibling` is settled and the set is exact.
        """
        key = (op, index, want, sibling, sibling_reach)
        if key not in self._want:
            if op in ag.UNARY or op in ag.WINDOWED:
                out = frozenset(k for k in self.all if self.unary_kind(op, k) in want)
            elif index == 1:
                out = self._first_child_want(op, want, sibling_reach)
            elif sibling in self.all:
                out = frozenset(b for b in self.all
                                if self.binary_kind(op, str(sibling), b) in want)
            else:
                out = frozenset()
            self._want[key] = out
        return self._want[key]

    def _first_child_want(self, op: str, want: frozenset[str],
                          sibling_reach: frozenset[str]) -> frozenset[str]:
        """Which kinds a binary node's FIRST child may take, filtered by dtype before unit.

        The dtype pre-filter is what keeps this affordable: most (op, dtype, dtype) triples are
        already meaningless, so the unit pairs under them never have to be enumerated.
        """
        want_dtypes = {self._split(k)[0] for k in want}
        mine = self._by_dtype(self.all)
        theirs = self._by_dtype(sibling_reach)
        out: set[str] = set()
        for ta, tb, to in self._dt_pairs[op]:
            if to not in want_dtypes or tb not in theirs:
                continue
            for ua in mine.get(ta, ()):
                if f"{ta}@{ua}" in out:
                    continue
                for ub in theirs[tb]:
                    uo = self._u_binary.get((op, ua, ub), ag.INVALID)
                    if uo != ag.INVALID and f"{to}@{uo}" in want:
                        out.add(f"{ta}@{ua}")
                        break
        return frozenset(out)

    def allowed(self, want: frozenset[str], remaining: int, terminals: tuple[str, ...],
                root: bool) -> tuple[str, ...]:
        """Every action a slot accepting `want` may take with `remaining` levels of budget:
        terminals of an accepted kind (never at the root: a bare terminal is a level, not an
        alpha) and operators whose first child can still be completed to an accepted kind."""
        key = (want, remaining, terminals, root)
        if key not in self._allowed:
            leaf = frozenset(ag.TERMINAL_KINDS[t] for t in terminals)
            acts: list[str] = []
            if not root or remaining == 0:
                acts.extend(t for t in terminals if ag.TERMINAL_KINDS[t] in want)
            if remaining >= 1:
                below = self.reach(remaining - 1, leaf)
                acts.extend(op for op in ag.OPERATORS
                            if self.child_want(op, 1, want, None, below) & below)
            self._allowed[key] = tuple(acts)
        return self._allowed[key]


_TYPES: _TypeAlgebra | None = None


def type_algebra() -> _TypeAlgebra:
    """The grammar's type tables, built once per process from `alpha_grammar.type_of`."""
    global _TYPES
    if _TYPES is None:
        _TYPES = _TypeAlgebra()
    return _TYPES


# --------------------------------------------------------------------------- gflownet: states
#: A slot's feature context: (kind, parent op, child index, accepted dtypes, depth, grandparent).
_Context = tuple[str, str, int, str, int, str]
_Step = tuple[_Context, tuple[str, ...], str]


@dataclass
class _Slot:
    """An open position in a partial tree: where the next token goes and what fits there."""
    holder: list[Any]                 # the list whose `index` entry this slot fills
    index: int
    depth: int                        # depth of the node that will sit here; the root is 0
    parent: str                       # operator of the holder node; ROOT_NODE at the root
    grand: str
    parent_want: frozenset[str]       # dtypes the parent's own slot accepts
    window: bool = False              # a window slot: the action is one of WINDOW_ACTIONS
    target: Any = None                # replay only: the subtree (or window) that must go here
    want: frozenset[str] | None = None  # resolved when the slot is opened


class _Builder:
    """One top-down construction: a stack of open slots over a partial tree.

    Slots are opened depth-first, left to right, and a windowed node's window is chosen right
    after its operator. That fixes ONE construction order per tree, which is why the backward
    policy of `GFlowNet` is trivial. The dtype set a slot accepts is resolved when it is
    opened, not when it is pushed, because a binary node's second child depends on what the
    first child turned out to be.
    """

    def __init__(self, types: _TypeAlgebra, max_depth: int, allow_drivers: bool,
                 target: Expr = None, terminals: Sequence[str] | None = None) -> None:
        self.types = types
        self.max_depth = max_depth
        self.terminals = (tuple(terminals) if terminals is not None
                          else ag.terminal_pool(allow_drivers))
        self.leaf_types = frozenset(ag.TERMINAL_KINDS[t] for t in self.terminals)
        self.root: list[Any] = [None]
        self.stack: list[_Slot] = [_Slot(self.root, 0, 0, ROOT_NODE, ROOT_NODE, types.all,
                                         target=target)]

    @property
    def done(self) -> bool:
        return not self.stack

    @property
    def expr(self) -> Expr:
        return self.root[0]

    def open(self) -> tuple[_Slot, tuple[str, ...], _Context]:
        """The current slot, the actions it allows, and its feature context."""
        s = self.stack[-1]
        if s.window:
            return s, WINDOW_ACTIONS, ("win", s.parent, s.index, "WINDOW", s.depth, s.grand)
        if s.want is None:
            s.want = self._want(s)
        remaining = self.max_depth - s.depth
        allowed = self.types.allowed(s.want, remaining, self.terminals, s.depth == 0)
        label = "ANY" if s.want == self.types.all else "|".join(sorted(s.want))
        return s, allowed, ("expr", s.parent, s.index, label, s.depth, s.grand)

    def _want(self, s: _Slot) -> frozenset[str]:
        if s.parent == ROOT_NODE:
            return self.types.all
        sibling = ag.kind_of(s.holder[1]) if s.index == 2 else None
        reach = self.types.reach(self.max_depth - s.depth, self.leaf_types)
        return self.types.child_want(s.parent, s.index, s.parent_want, sibling, reach)

    def apply(self, action: str) -> None:
        """Fill the current slot: a window, a terminal, or an operator whose child slots (and
        window slot, opened first) are pushed for the following steps."""
        s = self.stack.pop()
        if s.window:
            s.holder[s.index] = int(action[1:])
            return
        if action not in _OPS:
            s.holder[s.index] = action
            return
        n_children = 1 if action in ag.UNARY or action in ag.WINDOWED else 2
        windowed = action in ag.WINDOWED or action in ag.BINARY_WINDOWED
        node: list[Any] = [action, *([None] * (n_children + int(windowed)))]
        s.holder[s.index] = node
        want = s.want if s.want is not None else self.types.all
        tgt = s.target
        for i in range(n_children, 0, -1):
            self.stack.append(_Slot(node, i, s.depth + 1, action, s.parent, want,
                                    target=(tgt[i] if tgt is not None else None)))
        if windowed:
            self.stack.append(_Slot(node, len(node) - 1, s.depth, action, s.parent, want,
                                    window=True, target=(tgt[-1] if tgt is not None else None)))


_OPS = frozenset(ag.OPERATORS)


@dataclass
class _Batch:
    """A replayed history, padded for vectorised training: S steps over T trajectories."""
    idx: np.ndarray        # (S, A, F) feature buckets; 0 on padding
    sgn: np.ndarray        # (S, A, F) feature signs; 0 on padding
    mask: np.ndarray       # (S, A) True where the action exists
    chosen: np.ndarray     # (S,) index of the action taken
    traj: np.ndarray       # (S,) trajectory id
    log_r: np.ndarray      # (T,) log reward


# --------------------------------------------------------------------------- gflownet
class GFlowNet:
    """A trainable generative flow network over the alpha grammar.

    STATE. A partial tree with a stack of open slots (`_Builder`). Each slot knows the KIND set
    the grammar will accept there, its depth, and its parent and grandparent operators.

    ACTIONS. For an expression slot: a terminal (from the pool the caller says it has) of an
    accepted KIND, or an operator that can still be completed within the depth budget to an
    accepted kind; for a window slot: one of WINDOWS. A kind is a dtype AND a unit, and
    feasibility is decided from the grammar's own `kind_of` (see `_TypeAlgebra`), so a
    trajectory can only end in a tree the production screen accepts -- structure, type AND units.

    FORWARD POLICY. P_F(a | s) = softmax over the allowed actions of theta . phi(s, a). phi
    hashes five descriptors -- the action; parent op and child index with the action; the
    slot's kind set with the action; depth with the action; grandparent and parent with the
    action -- into `n_buckets` signed buckets, so preferences generalise across trees that
    share a context. theta starts at zero: the untrained policy is uniform over allowed actions.

    BACKWARD POLICY. Slots are opened in one fixed order (depth-first, left to right, window
    right after its operator), so a tree has exactly one construction trajectory and every
    non-initial state exactly one parent: P_B(s | s') = 1 throughout. Trajectory balance then
    reduces to  log Z + sum_t log P_F(a_t | s_t) = log R(x),  and the loss is the squared
    residual averaged over the replayed history.

    REWARD. R(x) = exp(beta x (f - f_max)) + eps from the history's fitness: centred on the
    best so the exponent cannot overflow, floored so log R cannot diverge. `reward_fn` replaces
    f with a caller's own score in fitness units (portfolio-aware, tail-conditioned; see
    `tail_diversity_reward`) BEFORE that map, so any real number is a legal reward.

    TRAINING. Adam on theta over minibatches of trajectories. log Z is solved, not stepped: at
    fixed theta the loss is quadratic in log Z with minimiser mean(log R - sum log P_F), and a
    slowly stepped log Z would leave every residual negative for the first epochs -- every
    trajectory pushed up, the rewarded ones only slightly more -- instead of the rewarded ones
    up and the rest down, which is the whole point.

    DEPTH. Histories are replayed under `max_depth` (the grammar's ceiling by default, so every
    valid history tree is replayable). `sample` may use a smaller budget, which only removes
    operators from deep slots and renormalises: the learned preferences carry over.
    """

    def __init__(self, *, n_buckets: int = N_BUCKETS, max_depth: int = ag.MAX_DEPTH,
                 reward_fn: RewardFn | None = None) -> None:
        self.n_buckets = int(n_buckets)
        self.max_depth = max(0, min(int(max_depth), ag.MAX_DEPTH))
        self.reward_fn = reward_fn
        self.types = type_algebra()
        self.theta = np.zeros(self.n_buckets, dtype=float)
        self.log_z = 0.0
        self.fit_log: list[float] = []
        self.last_fit: dict[str, Any] = {}
        self._m = np.zeros(self.n_buckets, dtype=float)
        self._v = np.zeros(self.n_buckets, dtype=float)
        self._t = 0
        self._features_cache: dict[tuple[_Context, tuple[str, ...]],
                                   tuple[np.ndarray, np.ndarray]] = {}

    # ----------------------------------------------------------------- features & policy
    def _features(self, ctx: _Context, allowed: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray]:
        """(A, F) bucket ids and signs for every allowed action in a context. crc32 is stable
        across processes, unlike `hash`, so a saved theta means the same thing tomorrow."""
        key = (ctx, allowed)
        hit = self._features_cache.get(key)
        if hit is not None:
            return hit
        kind, parent, index, want, depth, grand = ctx
        idx = np.zeros((len(allowed), N_FEATURES), dtype=np.int64)
        sgn = np.zeros((len(allowed), N_FEATURES), dtype=float)
        for i, a in enumerate(allowed):
            feats = (f"a={a}", f"p={parent}#{index}|a={a}", f"{kind}:t={want}|a={a}",
                     f"d={depth}|a={a}", f"g={grand}|p={parent}|a={a}")
            for j, f in enumerate(feats):
                h = zlib.crc32(f.encode("utf-8"))
                idx[i, j] = h % self.n_buckets
                sgn[i, j] = 1.0 if h & 0x80000000 else -1.0
        self._features_cache[key] = (idx, sgn)
        return idx, sgn

    def _log_policy(self, idx: np.ndarray, sgn: np.ndarray) -> np.ndarray:
        logits = (self.theta[idx] * sgn).sum(axis=1)
        logits = logits - logits.max()
        out: np.ndarray = logits - math.log(float(np.exp(logits).sum()))
        return out

    def _budget(self, max_depth: int) -> int:
        return max(0, min(int(max_depth), ag.MAX_DEPTH))

    # ----------------------------------------------------------------- sampling
    def sample(self, rng: np.random.Generator, max_depth: int = 3,
               allow_drivers: bool = True, terminals: Sequence[str] | None = None) -> Expr:
        """One tree drawn from P_F. Valid, well typed AND well formed by construction: the
        action mask is the grammar's own kind algebra, so nothing invalid is ever offered."""
        b = _Builder(self.types, self._budget(max_depth), allow_drivers, terminals=terminals)
        while not b.done:
            _slot, allowed, ctx = b.open()
            p = np.exp(self._log_policy(*self._features(ctx, allowed)))
            b.apply(allowed[int(rng.choice(len(allowed), p=p / p.sum()))])
        return b.expr

    def sample_batch(self, rng: np.random.Generator, n: int, max_depth: int = 3,
                     allow_drivers: bool = True, *, distinct: bool = True,
                     terminals: Sequence[str] | None = None) -> list[Expr]:
        """`n` trees; with `distinct`, a repeat is redrawn up to MAX_TRIES times before it is
        accepted, so a peaked policy still yields a spread rather than one tree n times."""
        out: list[Expr] = []
        seen: set[str] = set()
        for _ in range(int(n)):
            e = self.sample(rng, max_depth, allow_drivers, terminals)
            if distinct:
                for _ in range(MAX_TRIES):
                    if ag.key(e) not in seen:
                        break
                    e = self.sample(rng, max_depth, allow_drivers, terminals)
            seen.add(ag.key(e))
            out.append(e)
        return out

    # ----------------------------------------------------------------- replay
    def trajectory(self, expr: Expr, allow_drivers: bool = True,
                   terminals: Sequence[str] | None = None) -> list[_Step] | None:
        """The one construction trajectory of a tree as (context, allowed, action) steps, or
        None when the policy could not have built it: invalid (structure, type OR units), too
        deep, a bare terminal at the root, or a terminal outside the pool it may draw from."""
        if not ag.is_valid(expr, allow_drivers) or ag.depth(expr) > self.max_depth:
            return None
        b = _Builder(self.types, self.max_depth, allow_drivers, target=expr,
                     terminals=terminals)
        steps: list[_Step] = []
        while not b.done:
            slot, allowed, ctx = b.open()
            action = f"w{int(slot.target)}" if slot.window else _token(slot.target)
            if action not in allowed:
                return None
            steps.append((ctx, allowed, action))
            b.apply(action)
        return steps

    def actions(self, expr: Expr, allow_drivers: bool = True) -> list[str] | None:
        """The action ids of a tree's trajectory, for a reader; None where `trajectory` is."""
        steps = self.trajectory(expr, allow_drivers)
        return None if steps is None else [a for _, _, a in steps]

    def log_prob(self, expr: Expr, allow_drivers: bool = True) -> float:
        """log P_F of the tree's trajectory; -inf for a tree the policy cannot build."""
        steps = self.trajectory(expr, allow_drivers)
        if steps is None:
            return -math.inf
        total = 0.0
        for ctx, allowed, action in steps:
            lp = self._log_policy(*self._features(ctx, allowed))
            total += float(lp[allowed.index(action)])
        return total

    def _replay(self, history: History, beta: float, reward_fn: RewardFn | None,
                allow_drivers: bool) -> tuple[_Batch | None, int]:
        """The history as a padded batch of trajectories, and how many rows were skipped
        (non-finite score, or a tree the policy cannot build)."""
        rows: list[tuple[list[_Step], float]] = []
        skipped = 0
        for expr, fit in history:
            try:
                f = float(reward_fn(expr) if reward_fn is not None else fit)
            except (TypeError, ValueError):
                skipped += 1
                continue
            steps = self.trajectory(expr, allow_drivers) if math.isfinite(f) else None
            if steps is None:
                skipped += 1
                continue
            rows.append((steps, f))
        if not rows:
            return None, skipped
        f_max = max(f for _, f in rows)
        log_r = np.logaddexp(beta * (np.array([f for _, f in rows]) - f_max),
                             math.log(REWARD_EPS))
        n_steps = sum(len(s) for s, _ in rows)
        width = max(len(allowed) for s, _ in rows for _, allowed, _ in s)
        idx = np.zeros((n_steps, width, N_FEATURES), dtype=np.int64)
        sgn = np.zeros((n_steps, width, N_FEATURES), dtype=float)
        mask = np.zeros((n_steps, width), dtype=bool)
        chosen = np.zeros(n_steps, dtype=np.int64)
        traj = np.zeros(n_steps, dtype=np.int64)
        k = 0
        for j, (steps, _) in enumerate(rows):
            for ctx, allowed, action in steps:
                fi, fs = self._features(ctx, allowed)
                idx[k, :len(allowed)] = fi
                sgn[k, :len(allowed)] = fs
                mask[k, :len(allowed)] = True
                chosen[k] = allowed.index(action)
                traj[k] = j
                k += 1
        return _Batch(idx, sgn, mask, chosen, traj, log_r), skipped

    # ----------------------------------------------------------------- training
    def _forward(self, b: _Batch, steps: np.ndarray | None = None,
                 ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Per-trajectory sum log P_F (T,), the policy over actions (S', A) and the (S', A)
        step rows used, for all steps or the given step indices."""
        rows = np.arange(len(b.chosen)) if steps is None else steps
        logits = (self.theta[b.idx[rows]] * b.sgn[rows]).sum(axis=2)
        logits = np.where(b.mask[rows], logits, -np.inf)
        m = logits.max(axis=1, keepdims=True)
        p = np.exp(logits - m)
        z = p.sum(axis=1, keepdims=True)
        p = p / z
        logp = (logits - m - np.log(z))[np.arange(len(rows)), b.chosen[rows]]
        total = np.bincount(b.traj[rows], weights=logp, minlength=len(b.log_r))
        return total, p, rows

    def _solve_log_z(self, b: _Batch) -> float:
        """Set log Z to its closed-form minimiser at the current theta; return the loss."""
        total, _, _ = self._forward(b)
        self.log_z = float(np.mean(b.log_r - total))
        return float(np.mean((self.log_z + total - b.log_r) ** 2))

    def _gradient(self, b: _Batch, trajs: np.ndarray) -> np.ndarray:
        """d loss / d theta over a minibatch of trajectory ids. d log softmax / d theta is
        phi(s, a_t) - E_p[phi(s, .)], which for hashed features is a signed scatter-add."""
        rows = np.flatnonzero(np.isin(b.traj, trajs))
        total, p, rows = self._forward(b, rows)
        delta = self.log_z + total[trajs] - b.log_r[trajs]
        coef = np.zeros(len(b.log_r), dtype=float)
        coef[trajs] = 2.0 * delta / len(trajs)
        w = -p
        w[np.arange(len(rows)), b.chosen[rows]] += 1.0
        g = coef[b.traj[rows]][:, None, None] * w[:, :, None] * b.sgn[rows]
        out: np.ndarray = np.bincount(b.idx[rows].ravel(), weights=g.ravel(),
                                      minlength=self.n_buckets)
        return out

    def _adam(self, grad: np.ndarray, lr: float) -> None:
        self._t += 1
        self._m = ADAM_BETA1 * self._m + (1.0 - ADAM_BETA1) * grad
        self._v = ADAM_BETA2 * self._v + (1.0 - ADAM_BETA2) * grad * grad
        m_hat = self._m / (1.0 - ADAM_BETA1 ** self._t)
        v_hat = self._v / (1.0 - ADAM_BETA2 ** self._t)
        self.theta -= lr * m_hat / (np.sqrt(v_hat) + ADAM_EPS)

    def loss(self, history: History, beta: float = BETA, *, reward_fn: RewardFn | None = None,
             allow_drivers: bool = True) -> float:
        """The trajectory-balance loss of the history at the current theta and log Z; NaN
        when nothing in the history is replayable."""
        b, _ = self._replay(history, beta, reward_fn or self.reward_fn, allow_drivers)
        if b is None:
            return math.nan
        total, _, _ = self._forward(b)
        return float(np.mean((self.log_z + total - b.log_r) ** 2))

    def fit(self, history: History, epochs: int = EPOCHS, lr: float = LR, beta: float = BETA,
            *, batch_size: int = BATCH_SIZE, reward_fn: RewardFn | None = None,
            allow_drivers: bool = True, rng: np.random.Generator | None = None) -> GFlowNet:
        """Minimise the trajectory-balance loss over the history for `epochs` passes. The loss
        at the start of every epoch and after the last is in `fit_log`; `last_fit` says what
        was trained on and what was skipped. Fitting again continues from the current theta."""
        fn = reward_fn if reward_fn is not None else self.reward_fn
        b, skipped = self._replay(history, beta, fn, allow_drivers)
        self.fit_log = []
        if b is None:
            self.last_fit = {"n": 0, "skipped": skipped, "epochs": 0,
                             "why": "no replayable finite-score history: untrained"}
            return self
        shuffle = rng if rng is not None else np.random.default_rng(0)
        n = len(b.log_r)
        size = max(1, int(batch_size))
        for _ in range(int(epochs)):
            self.fit_log.append(self._solve_log_z(b))
            order = shuffle.permutation(n)
            for start in range(0, n, size):
                self._adam(self._gradient(b, order[start:start + size]), lr)
        self.fit_log.append(self._solve_log_z(b))
        self.last_fit = {"n": n, "skipped": skipped, "epochs": int(epochs), "beta": beta,
                         "reward": "reward_fn" if fn is not None else "fitness",
                         "loss_start": self.fit_log[0], "loss_end": self.fit_log[-1],
                         "log_z": self.log_z}
        return self


def tail_diversity_reward(history: History, *, quantile: float = 0.8,
                          penalty: float = 1.0) -> RewardFn:
    """A `GFlowNet` reward hook: fitness, with a tail member's excess over the tail floor
    discounted by how much of its structure the rest of the tail already has.

    WHY. Trained on fitness alone the network concentrates on the single best motif, and the
    evolution then pays for twenty near-copies of it. Sampling in proportion to reward is only
    diverse if the reward is: this one shares the tail's credit among its structurally distinct
    members (overlap = mean Jaccard similarity of transition sets with the other tail members),
    leaves the body of the history at plain fitness, and never pushes a tail member below the
    floor -- being in the tail is still worth exactly the floor. A tree the history has not
    scored gets the history's minimum: no evidence, no credit.
    """
    rows: list[tuple[Expr, float]] = []
    for expr, fit in history:
        try:
            f = float(fit)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            rows.append((expr, f))
    if not rows:
        return lambda _expr: 0.0
    fits = np.array([f for _, f in rows], dtype=float)
    floor = float(np.quantile(fits, min(1.0, max(0.0, quantile))))
    lowest = float(fits.min())
    by_key = {ag.key(e): f for e, f in rows}
    tail = [(ag.key(e), transitions(e)) for e, f in rows if f >= floor]
    pen = min(1.0, max(0.0, float(penalty)))

    def reward(expr: Expr) -> float:
        k = ag.key(expr)
        f = by_key.get(k, lowest)
        if f < floor or len(tail) < 2:
            return f
        mine = transitions(expr)
        sims = [len(mine & t) / len(mine | t) for kk, t in tail if kk != k]
        overlap = float(np.mean(sims)) if sims else 0.0
        return floor + (f - floor) * (1.0 - pen * overlap)
    return reward


# --------------------------------------------------------------------------- symbolic regression
def _zscore_train(v: np.ndarray, cut: int) -> np.ndarray | None:
    """z-score with TRAIN-slice statistics only, applied to the whole series."""
    tr = v[:cut]
    ok = np.isfinite(tr)
    if int(ok.sum()) < MIN_OBS:
        return None
    m, s = float(tr[ok].mean()), float(tr[ok].std())
    if not math.isfinite(s) or s <= 1e-12:
        return None
    out: np.ndarray = (v - m) / s
    return out


def _mse(z: np.ndarray, y: np.ndarray, sl: slice) -> float:
    """Sign-free squared error: the evolution trades an expression followed OR faded, so a
    perfectly anti-correlated fit is as good as a perfectly correlated one."""
    a, b = z[sl], y[sl]
    ok = np.isfinite(a) & np.isfinite(b)
    if int(ok.sum()) < MIN_OBS:
        return math.inf
    a, b = a[ok], b[ok]
    return float(min(np.mean((a - b) ** 2), np.mean((-a - b) ** 2)))


def symbolic_regression(rng: np.random.Generator, frames: dict[str, pd.Series],
                        target: pd.Series, *, iters: int = 60, allow_drivers: bool = True,
                        max_depth: int = 3, train_frac: float = TRAIN_FRAC,
                        terminals: Sequence[str] | None = None) -> Expr:
    """Hill-climb from a random tree by `mutate`, accepting a move when the train-slice error
    falls. The holdout error is measured for the report and never consulted for a decision.

    `terminals` narrows the leaf pool to what the caller actually has a series for -- a driver
    the frames do not carry evaluates to NaN, so a hill-climb that may reach it spends its
    iterations on trees that cannot score."""
    LAST_FIT.clear()
    if not frames:
        LAST_FIT["why"] = "no frames: fell back to random_expr"
        return ag.random_expr(rng, max_depth, allow_drivers, terminals=terminals)
    idx = next(iter(frames.values())).index
    n = len(idx)
    cut = int(n * train_frac)
    y = pd.Series(target).reindex(idx).to_numpy(dtype=float)
    yz = _zscore_train(y, cut)
    if yz is None:
        LAST_FIT["why"] = f"target has under {MIN_OBS} finite train observations: random_expr"
        return ag.random_expr(rng, max_depth, allow_drivers, terminals=terminals)
    memo: dict[str, pd.Series] = {}

    def score(expr: Expr) -> tuple[float, float]:
        v = ag.evaluate(expr, frames, memo).to_numpy(dtype=float)
        z = _zscore_train(v, cut)
        if z is None:
            return math.inf, math.inf
        return _mse(z, yz, slice(0, cut)), _mse(z, yz, slice(cut, n))

    best = ag.random_expr(rng, max_depth, allow_drivers, terminals=terminals)
    best_s = score(best)
    accepted = 0
    for _ in range(int(iters)):
        cand = ag.mutate(best, rng, allow_drivers, terminals=terminals)
        s = score(cand)
        if s[0] < best_s[0]:
            best, best_s, accepted = cand, s, accepted + 1
    LAST_FIT.update({
        "expr": ag.to_str(best),
        "train_mse": (best_s[0] if math.isfinite(best_s[0]) else None),
        "holdout_mse": (best_s[1] if math.isfinite(best_s[1]) else None),
        "n_train": cut, "n_holdout": n - cut, "iters": int(iters), "accepted": accepted,
        "rule": "fitted on the first 70% of the index only; the holdout error is reported and "
                "never used to choose",
    })
    return best


# --------------------------------------------------------------------------- the shared surface
def _gen_random(rng: np.random.Generator, frames: dict[str, pd.Series], ret: pd.Series,
                history: History, allow_drivers: bool, max_depth: int) -> Expr:
    return ag.random_expr(rng, max_depth, allow_drivers)


#: The network fitted on the last history seen, keyed by a fingerprint of that history. The
#: evolution's history is fixed while a generation is bred and grows once it is scored, so
#: one fit per generation is the whole cost; the fingerprint (length, finite count, fitness
#: sum, last tree, driver flag) is what keeps one symbol's network from serving another's
#: history of the same length.
_GFLOW_CACHE: dict[str, Any] = {"key": None, "net": None}


def _history_key(history: History, allow_drivers: bool) -> tuple[Any, ...]:
    total, n = 0.0, 0
    for _, fit in history:
        try:
            f = float(fit)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            total += f
            n += 1
    last = ag.key(history[-1][0]) if len(history) else ""
    return (len(history), n, round(total, 6), last, bool(allow_drivers))


def _gen_gflow(rng: np.random.Generator, frames: dict[str, pd.Series], ret: pd.Series,
               history: History, allow_drivers: bool, max_depth: int) -> Expr:
    key = _history_key(history, allow_drivers)
    net = _GFLOW_CACHE["net"]
    if net is None or _GFLOW_CACHE["key"] != key:
        net = GFlowNet().fit(history, allow_drivers=allow_drivers)
        _GFLOW_CACHE.update(key=key, net=net)
    return net.sample(rng, max_depth, allow_drivers)


def _gen_symreg(rng: np.random.Generator, frames: dict[str, pd.Series], ret: pd.Series,
                history: History, allow_drivers: bool, max_depth: int) -> Expr:
    # NEXT-bar return: the expression at bar t is fitted to what happens from t to t+1. That is
    # a supervised target forward of the expression's own causal inputs, not a leak into them.
    target = pd.Series(ret).shift(-1)
    return symbolic_regression(rng, frames, target, allow_drivers=allow_drivers,
                               max_depth=max_depth)


GENERATORS: dict[str, Generator] = {
    "random": _gen_random,
    "gflow": _gen_gflow,
    "symreg": _gen_symreg,
}


def choose_generator(rng: np.random.Generator, weights: dict[str, float] | None = None) -> str:
    """A generator name drawn by weight. No weights, all-zero, unknown-only or non-finite
    weights all mean uniform -- a bad table degrades to the flat prior, never to a crash."""
    names = list(GENERATORS)
    w = np.ones(len(names), dtype=float)
    if weights:
        cand = np.array([max(0.0, float(weights.get(n, 0.0) or 0.0)) for n in names], dtype=float)
        if np.isfinite(cand).all() and cand.sum() > 0:
            w = cand
    return str(names[int(rng.choice(len(names), p=w / w.sum()))])


def load_weights(path: Path) -> tuple[dict[str, float] | None, str]:
    """The generator weight table and where it came from. `{"weights": {...}}` or a flat table;
    (None, reason) -- uniform -- when the file is absent or unreadable. Never raises."""
    try:
        doc = json.loads(Path(path).read_text("utf-8"))
    except OSError:
        return None, f"{Path(path).name} absent: uniform"
    except ValueError as exc:
        return None, f"{Path(path).name} unreadable ({type(exc).__name__}): uniform"
    table = doc.get("weights", doc) if isinstance(doc, dict) else None
    if not isinstance(table, dict):
        return None, f"{Path(path).name} carries no weight table: uniform"
    out: dict[str, float] = {}
    for k, v in table.items():
        try:
            out[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    known = {k: v for k, v in out.items() if k in GENERATORS}
    if not known:
        return None, f"{Path(path).name} names no known generator: uniform"
    return known, f"{Path(path).name}: {json.dumps(known, sort_keys=True)}"
