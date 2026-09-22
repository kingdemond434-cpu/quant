"""THE ANYTIME-VALID SCIENCE CONTROLLER (LAWS 5m): online FDR wealth per lineage, confidence
sequences and e-processes that stay valid at data-dependent stopping times, and a verdict that
does not depend on when you looked.

WHY A RESEARCH STREAM THAT NEVER STOPS NEEDS THIS. Every fixed-horizon test the desk runs was
derived for ONE test read ONCE. The research organism (LAWS 5k) launches families continuously,
peeks at forward evidence daily, stops early when it likes what it sees and launches follow-ups
because of what it saw. Each of those habits is a licence to lie under a fixed-horizon test: the
type-I rate of "peek until significant" is 1, not 0.05, and the false-discovery rate of "launch a
thousand families and keep the winners" is whatever the winners' curse makes it. Two objects fix
both habits by construction:

  * AN E-PROCESS is a non-negative supermartingale under H0 with E[E_0] = 1, so by Ville's
    inequality P(sup_t E_t >= 1/alpha) <= alpha. That bound holds at EVERY t simultaneously:
    stop the instant it crosses, stop for any data-dependent reason, and the error is still
    <= alpha. `EProcess` below is the self-normalised mixture
        E_t = mean over lambda in a grid of exp(lambda S_t - lambda^2 V_t / 2),   V_t = sum x_s^2
    (de la Pena 1999: for conditionally symmetric increments each component is a supermartingale
    for every lambda; a uniform mixture of supermartingales is a supermartingale). H0 here is
    "the increments are conditionally symmetric about zero" -- which covers a mean-zero return
    stream with any symmetric tail, and is measured in the test suite under Gaussian AND t(3)
    noise. `libs.research.anytime_valid.e_value` is the desk's older betting e-value on a finished
    series; this one is INCREMENTAL, so a stream can be scored as it arrives.
  * A CONFIDENCE SEQUENCE is an interval valid at every t at once. The normal-mixture boundary
    (Howard, Ramdas, McAuliffe, Sekhon 2021) on intrinsic time V_t gives
        |S_t/t - mu| <= sqrt((V_t + rho) log((V_t + rho) / (rho alpha^2))) / t
    with `rho` fixed in advance. A stopping time chosen by looking at the data does not break
    the coverage, which is the whole point.

ONLINE FDR AS STATISTICAL WEALTH (LORD++, Ramdas, Yang, Wainwright, Jordan 2017). A lineage
starts with wealth W0 <= alpha. Launch t is granted the level
    alpha_t = gamma_t W0 + (alpha - W0) gamma_{t - tau_1} + alpha * sum_{j >= 2} gamma_{t - tau_j}
where tau_j is the time of the j-th discovery and gamma is a fixed non-negative sequence summing
to at most one. A launch SPENDS alpha_t; a discovery EARNS (alpha - W0) the first time and alpha
every time after, paid out over the following launches through gamma. Under independent
super-uniform p-values FDR(T) <= alpha for every T. The wealth account
    W_t = W0 - sum_{s <= t} alpha_s + sum_j payout_j
is what the procedure has left to spend; it is never negative under the rule, so an overdraw is
only possible when a launcher DEMANDS a level the rule does not grant. `LineageWealth.launch`
refuses two things and records why: a lineage whose next grant is below `ALPHA_FLOOR` (its wealth
is EXHAUSTED -- sixty-odd discovery-less launches at the defaults -- and only a discovery
replenishes it), and a launcher asking for a level above the grant (OVERDRAW). A refused launch
spends nothing.

EFFECTIVE TRIALS SPEND EFFECTIVE SLOTS. A launch of a family that `libs.research.trial_ledger`
prices at N_effective cells consumes ceil(N_effective) consecutive grants and is tested once at
their sum against the family's Bonferroni-adjusted best p-value (`bonferroni`). N_effective is a
function of the family's descriptors, decided before any p-value is seen, so the grant stays
predictable and the FDR bound stays intact. This is the mechanism by which a search of a million
cells cannot report one winner as one trial: the million costs a million slots of wealth.

WHAT THIS MODULE NEVER DOES. It moves no capital, lowers no sealed gate and retires nothing. The
desk's ten gates run at their sealed levels; this controller publishes the level a lineage can
AFFORD beside the level it was tested at, and refuses new launches for lineages that have nothing
left to spend. UNMEASURED is a value: a stream with no increments has no verdict.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

import numpy as np

#: The program-level FDR budget per lineage.
ALPHA = 0.05
#: A grant below this level cannot be met by any test the desk runs at its sample sizes
#: (DSR on 60-500 daily observations bottoms out near 1e-4 for a Sharpe-3 series); a lineage
#: whose next grant is below it is EXHAUSTED and its launches are refused until a discovery.
ALPHA_FLOOR = 1e-4
#: The gamma sequence is normalised over this many launches per lineage; beyond it gamma is 0.
HORIZON = 10_000
#: The betting grid of the e-process (positive lambdas: evidence FOR a positive mean).
LAMBDA_GRID: tuple[float, ...] = tuple(float(x) for x in np.geomspace(0.02, 0.6, 16))
#: exp() overflow guard: exp(700) is finite and above any threshold a caller could state.
_LOG_CAP = 700.0

DISCOVERY = "DISCOVERY"
REFUTED = "REFUTED"
UNDECIDED = "UNDECIDED"
UNMEASURED = "UNMEASURED"
BLOCKED = "BLOCKED"
GRANTED = "GRANTED"


# ------------------------------------------------------------------ e-process
@dataclass
class EProcess:
    """Incremental self-normalised mixture e-process for H0: increments conditionally symmetric
    about zero (equivalently, no positive drift). `update(x)` returns the running e-value; the
    running MAXIMUM is what an anytime verdict reads, because the first crossing of 1/alpha is a
    stopping time and Ville's inequality bounds the probability of ever reaching it."""

    lambdas: tuple[float, ...] = LAMBDA_GRID
    n: int = 0
    s: float = 0.0
    v: float = 0.0
    max_e: float = 1.0
    first_crossing: dict[float, int] = field(default_factory=dict)

    @property
    def e(self) -> float:
        if self.n == 0:
            return 1.0
        lam = np.asarray(self.lambdas, dtype=float)
        logs = lam * self.s - 0.5 * lam * lam * self.v
        m = float(np.max(logs))
        mix = m + math.log(float(np.mean(np.exp(logs - m))))
        return float(math.exp(min(mix, _LOG_CAP)))

    def update(self, x: float) -> float:
        if not math.isfinite(x):
            return self.e
        self.n += 1
        self.s += x
        self.v += x * x
        e = self.e
        if e > self.max_e:
            self.max_e = e
        return e

    def extend(self, xs: Iterable[float]) -> float:
        e = self.e
        for x in xs:
            e = self.update(float(x))
        return e

    def p_value(self) -> float:
        """min(1, 1/max_t E_t): a p-value valid at every stopping time (Ville)."""
        return min(1.0, 1.0 / self.max_e) if self.max_e > 0 else 1.0


def eprocess_path(xs: Sequence[float] | np.ndarray,
                  lambdas: Sequence[float] = LAMBDA_GRID) -> np.ndarray:
    """The whole e-process path of a finished stream, vectorised (for simulation and audit).
    Element t is E_{t+1}; `np.maximum.accumulate` of it is the running maximum."""
    x = np.asarray(xs, dtype=float)
    if x.size == 0:
        return np.ones(0)
    lam = np.asarray(lambdas, dtype=float)[:, None]
    s = np.cumsum(x)[None, :]
    v = np.cumsum(x * x)[None, :]
    logs = lam * s - 0.5 * lam * lam * v
    m = logs.max(axis=0)
    mix = m + np.log(np.mean(np.exp(logs - m), axis=0))
    return np.asarray(np.exp(np.minimum(mix, _LOG_CAP)), dtype=float)


# ------------------------------------------------------------------ confidence sequence
def confidence_sequence(s: float, v: float, n: int, *, alpha: float = ALPHA,
                        rho: float = 1.0) -> tuple[float, float]:
    """Normal-mixture confidence sequence for the mean after n increments with running sum s
    and intrinsic time v = sum x^2. Valid at every n simultaneously, so at any stopping time.
    `rho` (> 0, in the units of v) is fixed in advance; it tunes WHEN the interval is tightest,
    never WHETHER it covers."""
    if n <= 0:
        return (-math.inf, math.inf)
    rho = max(float(rho), 1e-12)
    a = max(min(float(alpha), 0.999999), 1e-12)
    width = math.sqrt((v + rho) * math.log((v + rho) / (rho * a * a))) / n
    centre = s / n
    return (centre - width, centre + width)


# ------------------------------------------------------------------ the verdict
@dataclass(frozen=True)
class Verdict:
    verdict: str
    n: int
    e_value: float
    max_e: float
    p_value: float
    interval: tuple[float, float]
    decided_at: int | None
    alpha: float

    def to_dict(self) -> dict[str, object]:
        return {"verdict": self.verdict, "n": self.n, "e_value": round(self.e_value, 6),
                "max_e": round(self.max_e, 6), "p_value": round(self.p_value, 8),
                "interval": [round(self.interval[0], 8), round(self.interval[1], 8)],
                "decided_at": self.decided_at, "alpha": self.alpha}


def verdict_at_any_time(evidence_stream: Iterable[float], *, alpha: float = ALPHA,
                        rho: float = 1.0) -> Verdict:
    """The verdict on a stream of increments, identical whenever it is read.

    DISCOVERY the moment the running e-process reaches 1/alpha (evidence of positive drift);
    REFUTED the moment the confidence sequence's upper end falls below zero (the mean is
    negative at confidence 1 - alpha); UNDECIDED otherwise; UNMEASURED on an empty stream. A
    decision, once reached, is final: reading more of the stream never reverses it, and reading
    less of it cannot manufacture it -- which is what "never depends on when you looked" means.
    """
    ep = EProcess()
    thr = 1.0 / alpha
    verdict, decided_at = UNDECIDED, None
    for x in evidence_stream:
        e = ep.update(float(x))
        if decided_at is None:
            if e >= thr:
                verdict, decided_at = DISCOVERY, ep.n
            else:
                _lo, hi = confidence_sequence(ep.s, ep.v, ep.n, alpha=alpha, rho=rho)
                if hi < 0.0:
                    verdict, decided_at = REFUTED, ep.n
    if ep.n == 0:
        return Verdict(UNMEASURED, 0, 1.0, 1.0, 1.0, (-math.inf, math.inf), None, alpha)
    return Verdict(verdict, ep.n, ep.e, ep.max_e, ep.p_value(),
                   confidence_sequence(ep.s, ep.v, ep.n, alpha=alpha, rho=rho), decided_at, alpha)


def indicator_e_value(passed: Sequence[bool], level: float) -> float:
    """The e-value of a run of pass/fail verdicts judged at a fixed level: the average of
    1[pass]/level. Under the null that each verdict passes with probability <= level every
    term has expectation <= 1, and an average of e-values is an e-value. Its anytime p-value
    is min(1, 1/e). Zero verdicts is UNMEASURED and returns 1.0 (no evidence either way)."""
    if not passed or not 0.0 < level <= 1.0:
        return 1.0
    return float(sum(1.0 for p in passed if p) / (level * len(passed)))


def bonferroni(p_min: float, n_effective: float) -> float:
    """The family's p-value from its best member: min(1, N_effective * p_min)."""
    return float(min(1.0, max(0.0, p_min) * max(1.0, n_effective)))


# ------------------------------------------------------------------ LORD++ wealth
def gamma_sequence(horizon: int = HORIZON) -> np.ndarray:
    """The LORD paper's default spending sequence, gamma_t ~ log(max(t,2)) / (t e^sqrt(log t)),
    normalised to sum to one over `horizon` launches (zero beyond, so the sum never exceeds
    one, which is the condition the FDR proof needs). Index 0 is gamma_1."""
    t = np.arange(1, max(int(horizon), 1) + 1, dtype=float)
    g = np.log(np.maximum(t, 2.0)) / (t * np.exp(np.sqrt(np.log(t))))
    return np.asarray(g / g.sum(), dtype=float)


_GAMMA_CACHE: dict[int, np.ndarray] = {}


def _gamma(horizon: int) -> np.ndarray:
    g = _GAMMA_CACHE.get(horizon)
    if g is None:
        g = gamma_sequence(horizon)
        _GAMMA_CACHE[horizon] = g
    return g


@dataclass(frozen=True)
class Launch:
    lineage: str
    state: str
    reason: str
    t_start: int
    slots: int
    alpha_granted: float
    wealth_before: float

    @property
    def granted(self) -> bool:
        return self.state == GRANTED

    def to_dict(self) -> dict[str, object]:
        return {"lineage": self.lineage, "state": self.state, "reason": self.reason,
                "t_start": self.t_start, "slots": self.slots,
                "alpha_granted": self.alpha_granted, "wealth_before": self.wealth_before}


@dataclass
class LineageWealth:
    """One lineage's LORD++ account. `t` counts granted slots; `rejections` holds the slot
    indices (1-based) at which discoveries were recorded."""

    lineage: str
    alpha: float = ALPHA
    w0: float | None = None
    horizon: int = HORIZON
    floor: float = ALPHA_FLOOR
    t: int = 0
    rejections: list[int] = field(default_factory=list)
    spent: float = 0.0
    earned: float = 0.0
    launches: int = 0
    refused: int = 0

    def __post_init__(self) -> None:
        if self.w0 is None:
            self.w0 = self.alpha / 2.0
        self.w0 = float(min(max(self.w0, 0.0), self.alpha))

    @property
    def wealth(self) -> float:
        return float((self.w0 or 0.0) - self.spent + self.earned)

    def alpha_at(self, t: int) -> float:
        """The grant for slot t (1-based) given the discoveries recorded so far."""
        if t < 1:
            return 0.0
        g = _gamma(self.horizon)

        def gam(k: int) -> float:
            return float(g[k - 1]) if 1 <= k <= g.size else 0.0

        w0 = self.w0 or 0.0
        out = gam(t) * w0
        for j, tau in enumerate(self.rejections):
            out += (self.alpha - w0 if j == 0 else self.alpha) * gam(t - tau)
        return float(out)

    def next_alpha(self) -> float:
        return self.alpha_at(self.t + 1)

    def grant_for(self, n_effective: float = 1.0) -> tuple[int, float]:
        slots = max(1, math.ceil(max(float(n_effective), 1.0)))
        return slots, float(sum(self.alpha_at(self.t + i) for i in range(1, slots + 1)))

    def launch(self, n_effective: float = 1.0, level: float | None = None) -> Launch:
        """Spend the grant for a launch of N_effective cells, or refuse it and spend nothing.

        EXHAUSTED when the next single-slot grant is below `floor`: the lineage has spent its
        wealth on discovery-less launches and only a recorded discovery replenishes it.
        OVERDRAW when the launcher demands `level` above what the rule grants: the desk's sealed
        gates test at their own levels, and a lineage that cannot afford that level is told so
        here rather than being allowed to run and count the pass as a discovery."""
        before = self.wealth
        nxt = self.next_alpha()
        slots, total = self.grant_for(n_effective)
        if nxt < self.floor:
            self.refused += 1
            return Launch(self.lineage, BLOCKED,
                          f"EXHAUSTED: next grant {nxt:.2e} below floor {self.floor:.0e} after "
                          f"{self.t} slots and {len(self.rejections)} discoveries; a discovery "
                          f"replenishes it", self.t, slots, 0.0, before)
        if level is not None and level > total:
            self.refused += 1
            return Launch(self.lineage, BLOCKED,
                          f"OVERDRAW: level {level:.4g} demanded, {total:.2e} granted over "
                          f"{slots} slot(s); wealth {before:.4g}", self.t, slots, 0.0, before)
        launch = Launch(self.lineage, GRANTED, "", self.t, slots, total, before)
        self.t += slots
        self.spent += total
        self.launches += 1
        return launch

    def record(self, launch: Launch, p_value: float) -> bool:
        """Judge a granted launch: a discovery iff p <= the granted level; the payout is spread
        over the following slots by gamma. Returns whether it was a discovery."""
        if not launch.granted or launch.alpha_granted <= 0.0:
            return False
        if p_value <= launch.alpha_granted:
            first = not self.rejections
            self.rejections.append(launch.t_start + launch.slots)
            self.earned += (self.alpha - (self.w0 or 0.0)) if first else self.alpha
            return True
        return False

    def to_dict(self) -> dict[str, object]:
        nxt = self.next_alpha()
        return {"lineage": self.lineage, "alpha": self.alpha, "w0": self.w0,
                "slots_spent": self.t, "launches": self.launches, "refused": self.refused,
                "discoveries": len(self.rejections), "spent": round(self.spent, 8),
                "earned": round(self.earned, 8), "wealth": round(self.wealth, 8),
                "next_alpha": nxt, "state": "EXHAUSTED" if nxt < self.floor else "OPEN"}


@dataclass
class ScienceController:
    """Every lineage's wealth in one place; a launch goes through `launch` and is either
    GRANTED (and later `record`ed) or BLOCKED with its reason kept."""

    alpha: float = ALPHA
    w0: float | None = None
    floor: float = ALPHA_FLOOR
    horizon: int = HORIZON
    lineages: dict[str, LineageWealth] = field(default_factory=dict)
    blocked: list[Launch] = field(default_factory=list)

    def lineage(self, name: str) -> LineageWealth:
        lw = self.lineages.get(name)
        if lw is None:
            lw = LineageWealth(name, alpha=self.alpha, w0=self.w0, horizon=self.horizon,
                               floor=self.floor)
            self.lineages[name] = lw
        return lw

    def launch(self, lineage: str, n_effective: float = 1.0,
               level: float | None = None) -> Launch:
        out = self.lineage(lineage).launch(n_effective, level)
        if not out.granted:
            self.blocked.append(out)
        return out

    def record(self, launch: Launch, p_value: float) -> bool:
        return self.lineage(launch.lineage).record(launch, p_value)

    def summary(self) -> dict[str, object]:
        rows = [lw.to_dict() for lw in self.lineages.values()]
        return {"alpha": self.alpha, "lineages": len(rows),
                "launches": sum(lw.launches for lw in self.lineages.values()),
                "discoveries": sum(len(lw.rejections) for lw in self.lineages.values()),
                "wealth_spent": round(sum(lw.spent for lw in self.lineages.values()), 8),
                "wealth_earned": round(sum(lw.earned for lw in self.lineages.values()), 8),
                "exhausted": sum(1 for r in rows if r["state"] == "EXHAUSTED"),
                "blocked": len(self.blocked)}


# ------------------------------------------------------------------ the all-null audit
def simulate_all_null_stream(*, lineages: int = 8, launches: int = 60, obs: int = 150,
                             reps: int = 200, alpha: float = ALPHA, follow_ups: int = 2,
                             heavy_tails: bool = False, seed: int = 20260922,
                             naive_level: float | None = None) -> dict[str, float]:
    """An autonomous all-null research stream: every lineage launches tests, each test peeks
    at an e-process and stops the moment it crosses the granted 1/alpha_t (or at `obs`), and a
    discovery triggers `follow_ups` extra launches in the same lineage. Returns the empirical
    FDR (= P(any false discovery) under the global null) of the LORD++ controller and of a
    NAIVE fixed-level rule with the same peeking, so the audit shows the controller is
    load-bearing rather than merely present.

    The e-process maximum over a path is computed once per launch, vectorised; adaptive
    stopping at the first crossing rejects iff that maximum reaches the threshold, so the
    sequential walk only needs the scalar maxima."""
    rng = np.random.default_rng(seed)
    naive = float(naive_level if naive_level is not None else alpha)
    pool = launches * (1 + follow_ups)        # the most a lineage can ever launch here
    fdr_lord, fdr_naive = [], []
    for _ in range(reps):
        if heavy_tails:
            x = rng.standard_t(3, size=(lineages, pool, obs)) / math.sqrt(3.0)
        else:
            x = rng.standard_normal(size=(lineages, pool, obs))
        lam = np.asarray(LAMBDA_GRID, dtype=float)[None, None, None, :]
        s = np.cumsum(x, axis=2)[..., None]
        v = np.cumsum(x * x, axis=2)[..., None]
        logs = lam * s - 0.5 * lam * lam * v
        m = logs.max(axis=3)
        mix = m + np.log(np.mean(np.exp(logs - m[..., None]), axis=3))
        max_e = np.exp(np.minimum(mix, _LOG_CAP)).max(axis=2)     # (lineages, pool)
        ctrl = ScienceController(alpha=alpha)
        v_lord = v_naive = 0
        for li in range(lineages):
            name = f"L{li}"
            queue = launches
            k = 0
            while queue > 0 and k < pool:
                queue -= 1
                me = float(max_e[li, k])
                k += 1
                # the naive rule: same peeking, a fixed level, no accounting
                if me >= 1.0 / naive:
                    v_naive += 1
                launch = ctrl.launch(name, 1.0)
                if not launch.granted:
                    continue
                if ctrl.record(launch, min(1.0, 1.0 / me)):
                    v_lord += 1
                    queue += follow_ups
        fdr_lord.append(1.0 if v_lord > 0 else 0.0)
        fdr_naive.append(1.0 if v_naive > 0 else 0.0)
    return {"reps": float(reps), "alpha": alpha,
            "fdr_lord": float(np.mean(fdr_lord)), "fdr_naive": float(np.mean(fdr_naive)),
            "se": float(math.sqrt(alpha * (1 - alpha) / reps))}
