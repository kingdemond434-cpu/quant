"""BAYESIAN PARTIAL POOLING for per-sleeve conditioning on a market state.

THE PROBLEM THIS SOLVES. Once hours carry a state label from the tape (`libs.regime.bar_states`),
the question becomes: how does THIS sleeve do in THAT state? The desk's router refused to answer
whenever a sleeve had fewer trades than its fold minimum -- 34 of 50 published sleeves on
2026-09-24. But small n is not "no answer", it is a WIDE answer, and refusing to give it throws
away the one thing that makes it estimable: the sleeve is not alone. It belongs to a family whose
other members trade the same mechanism, and the family belongs to a book.

So the estimate is hierarchical. Three levels for the LEVEL of a sleeve's returns:

    global mean  ->  family mean  ->  sleeve mean

and two for the STATE EFFECT, which is the part a router actually trades on:

    global state effect  ->  family state effect

Each child is shrunk toward its parent by n / (n + k0) -- the desk's standing shrinkage idiom
(`posterior_alpha.PRIOR_N0 = 30`, `state_admission.K_BUCKET = 40`, `robust_elog` k_state = 40),
reused here rather than re-invented so the constants mean the same thing they mean elsewhere.

WHY THE STATE EFFECT POOLS AT THE FAMILY AND NOT AT THE SLEEVE. Measured on the box 2026-09-24:
the whole trade record spans 17 days, and many sleeves fire all of their trades inside a single
day -- so a sleeve's OWN trades frequently sit in one state and carry no within-sleeve contrast
at all. Its family's trades span many days and many states. Estimating the state effect where
the contrast exists, and letting each sleeve inherit it, is the difference between an answer and
a refusal. A sleeve with its own state contrast overrides the family smoothly as its n grows.

WHAT IT REFUSES TO DO. If nothing in the book has been observed in a state, `predict` returns
`basis="UNMEASURED"` and a delta of exactly zero -- never a fabricated state effect. Zero here
means "this model has nothing to say", and the caller must publish the reason, not the number.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

#: Pseudo-trades shrinking a sleeve's mean toward its family's, and a family's toward the book's.
#: `posterior_alpha.PRIOR_N0`.
K_LEVEL = 30.0
#: Pseudo-trades shrinking a family's state effect toward the global one.
#: `state_admission.K_BUCKET` / `robust_elog` k_state.
K_STATE = 40.0
#: Pseudo-trades shrinking the GLOBAL state effect toward zero. The book-wide claim that a state
#: moves returns at all is the one every other level inherits, so it is the one held cheapest.
K_GLOBAL = 40.0

UNMEASURED = "UNMEASURED"


@dataclass(frozen=True)
class Obs:
    """One trade, with the market state that was in force when it was taken."""

    sleeve: str
    family: str
    state: str
    r: float
    ns: int = 0


@dataclass(frozen=True)
class Pooled:
    """A state-conditional prediction, with every level that contributed to it."""

    mu: float
    mu_unconditional: float
    delta: float
    n_sleeve: int
    n_family: int
    n_family_state: int
    n_global_state: int
    shrink_sleeve: float
    shrink_family: float
    shrink_state: float
    #: Where the state effect actually came from: "family", "global", or UNMEASURED.
    basis: str
    why: str = ""


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


@dataclass
class PooledModel:
    """Fitted hierarchy. Build with `fit`, then `predict` any (sleeve, family, state)."""

    global_mu: float = 0.0
    n_global: int = 0
    family_mu: dict[str, float] = field(default_factory=dict)
    family_n: dict[str, int] = field(default_factory=dict)
    sleeve_mu: dict[str, float] = field(default_factory=dict)
    sleeve_n: dict[str, int] = field(default_factory=dict)
    sleeve_family: dict[str, str] = field(default_factory=dict)
    global_delta: dict[str, float] = field(default_factory=dict)
    global_state_n: dict[str, int] = field(default_factory=dict)
    family_delta: dict[tuple[str, str], float] = field(default_factory=dict)
    family_state_n: dict[tuple[str, str], int] = field(default_factory=dict)
    k_level: float = K_LEVEL
    k_state: float = K_STATE
    k_global: float = K_GLOBAL

    def predict(self, sleeve: str, family: str, state: str) -> Pooled:
        """The state-conditional posterior mean for one sleeve, shrunk to what it has earned."""
        n_s = self.sleeve_n.get(sleeve, 0)
        n_f = self.family_n.get(family, 0)
        fam_raw = self.family_mu.get(family, self.global_mu)
        w_f = n_f / (n_f + self.k_level) if n_f else 0.0
        mu_f = w_f * fam_raw + (1.0 - w_f) * self.global_mu
        slv_raw = self.sleeve_mu.get(sleeve, mu_f)
        w_s = n_s / (n_s + self.k_level) if n_s else 0.0
        mu_s = w_s * slv_raw + (1.0 - w_s) * mu_f

        n_gs = self.global_state_n.get(state, 0)
        n_fs = self.family_state_n.get((family, state), 0)
        if not n_gs and not n_fs:
            return Pooled(mu=mu_s, mu_unconditional=mu_s, delta=0.0, n_sleeve=n_s, n_family=n_f,
                          n_family_state=0, n_global_state=0, shrink_sleeve=w_s,
                          shrink_family=w_f, shrink_state=0.0, basis=UNMEASURED,
                          why=f"no trade anywhere in the book has been observed in state "
                              f"{state!r}: the state effect is UNMEASURED, not zero")
        w_g = n_gs / (n_gs + self.k_global) if n_gs else 0.0
        d_g = w_g * self.global_delta.get(state, 0.0)
        w_fs = n_fs / (n_fs + self.k_state) if n_fs else 0.0
        d_f = w_fs * self.family_delta.get((family, state), 0.0) + (1.0 - w_fs) * d_g
        basis = "family" if n_fs else "global"
        return Pooled(mu=mu_s + d_f, mu_unconditional=mu_s, delta=d_f, n_sleeve=n_s,
                      n_family=n_f, n_family_state=n_fs, n_global_state=n_gs,
                      shrink_sleeve=w_s, shrink_family=w_f, shrink_state=w_fs, basis=basis,
                      why=(f"state effect from the {basis} level "
                           f"(n_family_state={n_fs}, n_global_state={n_gs})"))


def fit(observations: list[Obs], *, k_level: float = K_LEVEL, k_state: float = K_STATE,
        k_global: float = K_GLOBAL) -> PooledModel:
    """Fit the hierarchy on the trades given. Feed it ONLY trades the caller may look at."""
    m = PooledModel(k_level=k_level, k_state=k_state, k_global=k_global)
    if not observations:
        return m
    by_sleeve: dict[str, list[float]] = defaultdict(list)
    by_family: dict[str, list[float]] = defaultdict(list)
    by_state: dict[str, list[float]] = defaultdict(list)
    by_fam_state: dict[tuple[str, str], list[float]] = defaultdict(list)
    allr: list[float] = []
    for o in observations:
        allr.append(o.r)
        by_sleeve[o.sleeve].append(o.r)
        by_family[o.family].append(o.r)
        by_state[o.state].append(o.r)
        by_fam_state[(o.family, o.state)].append(o.r)
        m.sleeve_family[o.sleeve] = o.family
    m.global_mu = _mean(allr)
    m.n_global = len(allr)
    m.sleeve_mu = {k: _mean(v) for k, v in by_sleeve.items()}
    m.sleeve_n = {k: len(v) for k, v in by_sleeve.items()}
    m.family_mu = {k: _mean(v) for k, v in by_family.items()}
    m.family_n = {k: len(v) for k, v in by_family.items()}
    # A state effect is a CONTRAST against the level it sits in, never a raw mean: otherwise a
    # state that happens to contain the book's best family would look like a good state.
    m.global_delta = {s: _mean(v) - m.global_mu for s, v in by_state.items()}
    m.global_state_n = {s: len(v) for s, v in by_state.items()}
    for (fam, st), v in by_fam_state.items():
        m.family_delta[(fam, st)] = _mean(v) - m.family_mu.get(fam, m.global_mu)
        m.family_state_n[(fam, st)] = len(v)
    return m


def prequential(observations: list[Obs], *, use_state: bool, min_history: int = 3,
                k_level: float = K_LEVEL, k_state: float = K_STATE,
                k_global: float = K_GLOBAL) -> tuple[list[float], list[float], list[Pooled]]:
    """One-step-ahead predictions: every trade predicted from trades STRICTLY BEFORE it.

    This is the small-n replacement for the router's four expanding folds, and it is not a
    weaker test -- it is a stricter one, because the early predictions are made from almost no
    history and are scored anyway. It has no fold minimum, so a sleeve with six trades gets a
    measured answer instead of a refusal, and the same trades score the routed and the unrouted
    model, so the comparison is like for like.

    Returns (y, mu_hat, detail) in the order the trades arrived.
    """
    ordered = sorted(observations, key=lambda o: (o.ns, o.sleeve))
    y: list[float] = []
    mu: list[float] = []
    detail: list[Pooled] = []
    seen: list[Obs] = []
    for o in ordered:
        if len(seen) >= min_history:
            m = fit(seen, k_level=k_level, k_state=k_state, k_global=k_global)
            p = m.predict(o.sleeve, o.family, o.state)
            y.append(o.r)
            mu.append(p.mu if use_state else p.mu_unconditional)
            detail.append(p)
        seen.append(o)
    return y, mu, detail
