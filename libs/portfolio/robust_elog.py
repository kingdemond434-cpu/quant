"""Robust posterior E[log W] allocator -- the desk's capital brain.

WHAT THIS REPLACES. `research/allocation.py` maximises mean log growth on the point-estimate
daily-R matrix with weights on the simplex and total risk pinned to a constant. Three things are
wrong with that as a live allocator, and all three cost growth:

  1. IT BETS THE POINT ESTIMATE. Sleeves reach the matrix BECAUSE they measured well, so every
     mean in it carries a winner's curse. Optimising the sample mean allocates hardest to
     whichever sleeve got luckiest, which is the opposite of what maximises log wealth.
  2. IT CANNOT CHOOSE TOTAL EXPOSURE. `q_total` is an input, so the one question a growth
     optimiser exists to answer -- how much to bet in total, right now -- was answered outside it
     by a constant.
  3. IT HAS NO NOTION OF A BAD WORLD. Correlations spike in crises, edges decay, fills get worse.
     A maximiser of the average over ONE history sizes as if none of that can happen.

THE OBJECTIVE. This maximises a robust functional of expected log growth over a population of
sampled WORLDS -- each world a coherent joint draw of posterior means, edge decay, regime,
dependence stress, execution cost and crisis overlay:

    G_robust(h) = (1 - lam) * mean_w G_w(h)  +  lam * CVaR_alpha[ G_w(h) ]        (lam in [0,1])

    G_w(h) = mean_t log(1 + h . r_wt)

The CVaR term is what makes it ROBUST rather than merely Bayesian: it puts real weight on the
worst `alpha` fraction of worlds, so a book that grows well on average but is ruinous when
correlations converge scores below one that gives up a little average growth to survive them.

THE DECISION VARIABLE IS RISK, NOT WEIGHT. `h` is the vector of per-sleeve heat (fraction of
account risked), so `sum(h)` IS total portfolio heat and the optimiser chooses it. Weights and
total exposure are one problem, not two, which is the only way the answer to "should this new
edge get capital?" can be "yes, and everything else shrinks a little" rather than "no, the book
is full". `marginal_delta_elog` computes exactly that comparison by re-solving both books.

WHAT IS NOT IN HERE. No gate thresholds, no promotion decisions, no order placement, no desk
paths. This is a pure optimiser over evidence handed to it, so it can be tested without a
terminal, a broker or a repo layout. The heat POLICY (what total exposure is permitted) lives in
`desks/mt5/research/heat_policy.py`; this module reports what growth wants and obeys the bound
it is given.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np

__all__ = [
    "AllocationResult",
    "SleeveEvidence",
    "WorldConfig",
    "Worlds",
    "marginal_delta_elog",
    "optimise",
    "project_capped_simplex",
    "sample_worlds",
    "score_book",
]


@dataclass(frozen=True)
class SleeveEvidence:
    """One sleeve's return history and the metadata the penalties need.

    `daily_r` is R-multiple per day (already net of modelled costs), NOT account return: the
    optimiser multiplies it by that sleeve's heat to get account P&L, which is what makes
    `sum(h)` mean portfolio heat.
    """

    name: str
    daily_r: np.ndarray
    family: str = ""
    symbol: str = ""
    #: Days of out-of-sample forward evidence. Drives how far the posterior is shrunk toward the
    #: no-edge prior: backtest-only sleeves are shrunk hardest, live-evidenced ones least.
    forward_days: int = 0
    live_days: int = 0
    #: Per-trade cost already charged inside `daily_r`, in R. Used only to size the UNCERTAINTY
    #: around it -- the level is already in the returns and must not be charged twice.
    cost_r: float = 0.0
    #: HOW MANY CANDIDATES WERE SEARCHED TO FIND THIS ONE. The single most important field here
    #: and the one a Bayesian shrinkage by sample size cannot substitute for: a sleeve with 2,000
    #: observations is precisely estimated AND selected out of thousands of trials, so its sample
    #: mean is biased upward by selection no matter how long its history. 1 means "not selected".
    n_trials: int = 1
    #: THIS SLEEVE'S OWN RETURNS IN THE STATE BEING SOLVED FOR -- the session phase, and nothing
    #: else about the moment. Empty is the honest default and costs nothing: the posterior then
    #: uses the unconditional mean exactly as it did before this field existed, so a caller that
    #: does not know the hour is not penalised for saying so.
    state_r: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    #: Which state `state_r` was collected in. Carried for the allocation explanation, never used
    #: in the arithmetic -- a number the desk cannot attribute to an hour is not an explanation.
    state_key: str = ""

    def __post_init__(self) -> None:
        if self.daily_r.ndim != 1:
            raise ValueError(f"{self.name}: daily_r must be 1-D, got {self.daily_r.shape}")


@dataclass(frozen=True)
class WorldConfig:
    """How the scenario population is drawn. Every default is a stated belief, not a tuning knob."""

    #: Worlds in the population. The CVaR tail needs enough of them to be a tail and not a point:
    #: at alpha=0.20 this is 51 worlds in the tail average.
    n_worlds: int = 256
    #: Rows resampled per world. Block-resampled, so common stress days survive the resample --
    #: an i.i.d. shuffle would manufacture exactly the diversification the crisis destroys.
    n_rows: int = 384
    #: Mean block length in days for the stationary bootstrap.
    block_days: float = 5.0
    #: Fraction of worlds carrying a crisis overlay: vol up, means down, a common factor loaded
    #: onto every sleeve so correlations converge toward one.
    crisis_prob: float = 0.06
    #: Crisis severity: multiplies volatility, and the common-factor share of total variance.
    crisis_vol_mult: float = 2.5
    crisis_common_share: float = 0.55
    #: Probability that a given sleeve's edge has decayed in a given world, and how far. Backtest
    #: edges decay; a sizer that assumes they do not is sizing a book that no longer exists.
    decay_prob: float = 0.30
    decay_floor: float = 0.0
    #: Execution-cost uncertainty as a multiple of the modelled cost, drawn per world per sleeve.
    #: The LEVEL is already inside daily_r; this is the spread around it.
    cost_uncertainty: float = 0.50
    #: Robustness blend and tail fraction. lam=0 is plain Bayesian E[log W]; lam=1 optimises the
    #: worst alpha of worlds alone.
    robust_lambda: float = 0.50
    cvar_alpha: float = 0.20
    #: Redundancy price. Charged on correlation-weighted overlap so the optimiser prefers the same
    #: growth from more independent sources -- the worlds already punish crowding through the
    #: crisis common factor, so this is deliberately a light touch on top, not the main defence.
    redundancy_lambda: float = 0.15
    #: Regime label per historical row, and the CURRENT probability of each regime. When both
    #: are given every world draws a regime from `regime_probs` and resamples ONLY days carrying
    #: that label, so a sleeve that works in trend and dies in crisis is scored against the mix
    #: of worlds the desk actually believes it is in right now.
    #:
    #: PROBABILITIES, NEVER A HARD SWITCH. Choosing the single most likely regime and allocating
    #: as if it were certain hands the whole book to a classifier that is wrong some of the time,
    #: and the days it is most wrong are the days the switch costs most. Mixing over the
    #: posterior is the same arithmetic the rest of this module already does for edges.
    regime_labels: tuple[str, ...] = ()
    regime_probs: tuple[tuple[str, float], ...] = ()
    #: A regime needs at least this many historical days before a world may be drawn from it
    #: alone. Below it the world falls back to the full history: resampling 9 days into a 384-day
    #: path is not regime conditioning, it is one week of luck repeated 43 times (L1.28a).
    regime_min_days: int = 60
    seed: int = 0
    #: Ceiling on the sampled tensor in elements. 12M float32 is ~48 MB -- this box has 4 GB, no
    #: swap, and a history of OOM kills, so the population is trimmed to fit rather than sized by
    #: hope. `sample_worlds` reduces n_worlds/n_rows to respect it and says so in `Worlds.note`.
    max_elements: int = 12_000_000


@dataclass(frozen=True)
class Worlds:
    """A drawn scenario population, ready for the objective.

    `r` is (n_worlds, n_rows, n_sleeves) float32: the actual returns of each sleeve in each world
    on each resampled day, with posterior mean shift, decay, crisis overlay and cost draw already
    applied. Everything downstream is arithmetic on this tensor.
    """

    r: np.ndarray
    names: tuple[str, ...]
    crisis: np.ndarray
    mu_draws: np.ndarray
    #: Regime each world was drawn from, "" when unconditioned. Kept so attribution can ask
    #: which regimes a proposed book actually needs to be right about.
    regimes: tuple[str, ...] = ()
    note: str = ""

    @property
    def n_worlds(self) -> int:
        return int(self.r.shape[0])

    @property
    def n_sleeves(self) -> int:
        return int(self.r.shape[2])


@dataclass(frozen=True)
class AllocationResult:
    """The solved book: per-sleeve heat, total heat, and what the optimiser thought of each."""

    heat: dict[str, float]
    total_heat: float
    #: Robust score of the solved book, and the plain (non-robust) posterior mean log growth, so
    #: the price being paid for robustness is visible rather than folded into one number.
    robust_score: float
    mean_log_growth: float
    cvar_log_growth: float
    #: Annualised growth of the solved book under the posterior mean world, for human reading.
    annual_growth_pct: float
    #: P(this book loses money over a year) across worlds -- the number a Sharpe cannot express.
    prob_annual_loss: float
    #: Per-sleeve marginal value of its last unit of heat. Ranks the book by what it is DOING,
    #: which is the ordering `cap_by_heat` must use instead of a fixed gold-first list.
    marginal: dict[str, float] = field(default_factory=dict)
    iterations: int = 0
    converged: bool = False
    note: str = ""


def _stationary_bootstrap_index(n_rows: int, n_obs: int, block_days: float,
                                rng: np.random.Generator) -> np.ndarray:
    """Row indices for one stationary-bootstrap path (Politis-Romano).

    Geometric block lengths with mean `block_days`, wrapping at the end of history. This is the
    dependence-preserving resample: the reason a crisis week stays a crisis week instead of being
    scattered into seven unrelated days that diversify each other away.
    """
    if n_obs <= 0:
        raise ValueError("no observations to resample")
    p = 1.0 / max(block_days, 1.0)
    idx = np.empty(n_rows, dtype=np.int32)
    cur = int(rng.integers(n_obs))
    for t in range(n_rows):
        idx[t] = cur
        cur = int(rng.integers(n_obs)) if rng.random() < p else (cur + 1) % n_obs
    return idx


def _posterior_mu(ev: Sequence[SleeveEvidence], rng: np.random.Generator,
                  n_worlds: int) -> tuple[np.ndarray, np.ndarray]:
    """Hierarchical posterior draws of each sleeve's mean daily R.

    THE PRIOR IS NO EDGE, and that is the whole point. A sleeve is in this matrix because it
    measured well, so its sample mean is biased upward by selection. The posterior mean is the
    sample mean shrunk toward the family mean and the family mean shrunk toward zero, by
    n / (n + k) -- so a sleeve with 40 backtest days and no forward evidence is pulled most of the
    way to zero, and one with a year of live evidence is barely moved. Sizing on the unshrunk
    mean is how a desk ends up with its largest position in its luckiest backtest.

    Returns (draws (W, N), posterior_mean (N,)).
    """
    n = len(ev)
    m = np.array([float(e.daily_r.mean()) if e.daily_r.size else 0.0 for e in ev])
    s = np.array([float(e.daily_r.std(ddof=1)) if e.daily_r.size > 1 else 0.0 for e in ev])
    obs = np.array([float(e.daily_r.size) for e in ev])

    # TWO DIFFERENT CORRECTIONS, EACH APPLIED ONCE. Conflating them is what made the first two
    # attempts at this both wrong, in opposite directions:
    #
    #   BIAS      -- the mean is inflated because this sleeve was CHOSEN out of thousands. That
    #                is the trial deflation below, and more backtest does not cure it.
    #   PRECISION -- how well the (now deflated) mean is measured. That IS a question about
    #                sample size, and 2,455 observations genuinely answer it better than 40.
    #
    # Charging the bias correction through the precision term (by zeroing `obs`) pooled every
    # sleeve completely into its family and put the whole 126-sleeve book at 0.1%/yr -- deleting
    # a library the ten gates had vetted. Charging neither kept 97% of every sample mean and
    # reported 5,272%/yr. Deflate for bias, weight by evidence for precision.
    #
    # Forward and live days still carry 4x and 12x, because they are the only observations the
    # sleeve could not have been selected on -- so size grows as the forward clocks fill, which
    # is the incentive the desk wants.
    eff = obs + 4.0 * np.array([float(e.forward_days) for e in ev]) \
        + 12.0 * np.array([float(e.live_days) for e in ev])
    fam_w = eff

    # TRIAL DEFLATION -- the bias limb, applied to the mean before any pooling. The expected
    # maximum of N null Sharpes is ~sqrt(2 ln N) standard errors and SE(S_daily) ~ 1/sqrt(n), so
    # subtracting that threshold is exactly what the desk's `deflated_sharpe` GATE does to decide
    # whether a sleeve is real at all.
    #
    # HALF THE THRESHOLD, NOT ALL OF IT, and the reason is that the gate has already charged it
    # once: a sleeve holding a certificate is past the full threshold by construction, so what
    # remains is the residual bias of being a search's survivor rather than a fresh observation.
    # Measured 2026-09-02, charging the full threshold a second time took the free optimum from
    # 4.83% heat to 0.08% and the growth estimate from 282%/yr to 1.4% -- not conservatism,
    # deletion of a library the ten gates had vetted. Nothing here changes a gate threshold.
    trials = np.array([max(float(e.n_trials), 1.0) for e in ev])
    sr0 = np.where(trials > 1.0,
                   0.5 * np.sqrt(2.0 * np.log(np.maximum(trials, 1.0000001)))
                   / np.sqrt(np.maximum(obs, 1.0)),
                   0.0)

    # OUT-OF-SAMPLE EVIDENCE RELIEVES THE SELECTION PENALTY, and this is the ONLY place it can
    # do real work. Adding forward days to `eff` above changes nothing once a sleeve has
    # thousands of backtest observations -- lam_s is already 0.976 and saturates -- so the 4x/12x
    # multipliers were decorative: measured 2026-09-02, 250 forward days moved the book's growth
    # estimate from 73.4%/yr to 75.5%.
    #
    # The coupling belongs here because it is the same question: sr0 exists because the sleeve
    # was CHOSEN on its backtest, and an out-of-sample record is evidence the edge is real
    # REGARDLESS of how it was found. A day the sleeve could not have been selected on is a day
    # the winner's curse does not explain. So the penalty is relieved in proportion to how much
    # such evidence exists, against a 250-day scale: three forward days relieve 5% of it, a
    # quarter of live trading relieves half. Filling the forward clocks is what earns size.
    oos = 4.0 * np.array([float(e.forward_days) for e in ev]) \
        + 12.0 * np.array([float(e.live_days) for e in ev])
    sr0 = sr0 * (1.0 - oos / (oos + 250.0))

    sharpe = np.divide(m, s, out=np.zeros_like(m), where=s > 0)
    m = np.sign(sharpe) * np.maximum(np.abs(sharpe) - sr0, 0.0) * s

    families = [e.family or e.name for e in ev]
    fam_mean: dict[str, float] = {}
    for fam in set(families):
        rows = [i for i, f in enumerate(families) if f == fam]
        wts = fam_w[rows]
        fam_mean[fam] = float(np.average(m[rows], weights=wts)) if wts.sum() > 0 else 0.0
    fam_vec = np.array([fam_mean[f] for f in families])

    #: Pseudo-observations of the no-edge prior. 60 days is the scale at which the desk starts
    #: believing a mean: below it the sleeve is mostly its family, above it mostly itself.
    k_sleeve, k_family = 60.0, 120.0
    lam_s = eff / (eff + k_sleeve)
    fam_eff = np.array([fam_w[[i for i, f in enumerate(families) if f == families[j]]].sum()
                        for j in range(n)])
    lam_f = fam_eff / (fam_eff + k_family)

    post_mean = lam_s * m + (1.0 - lam_s) * (lam_f * fam_vec)
    # Posterior sd of the mean, floored so a sleeve with two observations is not treated as
    # certain. Widened by the shrinkage that was applied: pulling an estimate does not make it
    # more certain, and pretending otherwise would let a heavily-shrunk sleeve look precise.
    se = np.where(obs > 1, s / np.sqrt(np.maximum(obs, 1.0)), np.abs(m) + 1e-3)
    se = se * (2.0 - lam_s)

    # ------------------------------------------------------------------ STATE, THE FOURTH LEVEL
    # THE HOUR IS PART OF THE EDGE AND THE BOOK COULD NOT SEE IT. Everything above is measured on
    # the sleeve's whole history, so an edge that lives in the London expansion and dies in the
    # 22:00 roll carries ONE mean into every hour of the day. Measured 2026-09-03: `pf_allocator`
    # contained zero references to hour-of-day or session phase, so the same book was solved at
    # London open and at thin-liquidity roll from identical inputs.
    #
    # This is the shrinkage the three levels above already use, with the state as the narrowest:
    # state -> sleeve -> family -> no edge. `state_r` holds the sleeve's OWN returns observed in
    # the current state, so it is evidence about this sleeve, never a borrowing from another.
    #
    # K_STATE IS DELIBERATELY LARGER THAN A STATE BUCKET USUALLY IS. Conditioning is where
    # overfitting gets in: slice any sleeve by phase and some bucket holds six trades averaging
    # +0.9R, and an allocator that believes it hands that hour the book forever. At k=40 a bucket
    # needs forty observations to outweigh the unconditional posterior, so a lucky week moves the
    # estimate slightly and a real seasonal effect moves it fully. This desk has paid for the
    # class once already: `degenerate_evidence` in the promoter exists because a statistic
    # computed on too little cannot carry a decision.
    #
    # UNCERTAINTY WIDENS, IT NEVER NARROWS. A conditional estimate is measured on less data than
    # the unconditional one it replaces, so `se` grows with the disagreement between them. The
    # objective is CVaR over sampled worlds, so an estimate that admits it is uncertain is sized
    # smaller automatically -- which is what a thin bucket deserves and what makes this safe.
    k_state = 40.0
    n_state = np.array([float(np.asarray(getattr(e, "state_r", ())).size) for e in ev])
    if float(n_state.sum()) > 0.0:
        m_state = np.array([
            float(np.asarray(e.state_r).mean())
            if np.asarray(getattr(e, "state_r", ())).size else 0.0 for e in ev])
        lam_state = n_state / (n_state + k_state)
        conditioned = lam_state * m_state + (1.0 - lam_state) * post_mean
        se = se + np.abs(conditioned - post_mean)
        post_mean = conditioned

    draws = post_mean[None, :] + rng.standard_normal((n_worlds, n)) * se[None, :]
    return draws, post_mean


def sample_worlds(ev: Sequence[SleeveEvidence], cfg: WorldConfig | None = None) -> Worlds:
    """Draw the scenario population the objective is evaluated on.

    Each world is a JOINT draw -- the same world that gives a sleeve a decayed edge also gives it
    a worse fill and puts it in the crisis regime. Drawing these independently and averaging
    afterwards would let good luck on one axis cancel bad luck on another, which is precisely the
    cancellation that does not happen in the event the desk is sizing against.
    """
    cfg = cfg or WorldConfig()
    if not ev:
        raise ValueError("no sleeves to allocate over")
    n = len(ev)
    obs = min(int(e.daily_r.size) for e in ev)
    if obs < 2:
        raise ValueError("a sleeve has fewer than 2 observations; refusing to fabricate a world")

    # Trim the population to the memory budget rather than discovering it with the OOM killer.
    n_worlds, n_rows, note = cfg.n_worlds, min(cfg.n_rows, obs), ""
    while n_worlds * n_rows * n > cfg.max_elements and (n_worlds > 32 or n_rows > 64):
        if n_rows > 64:
            n_rows = max(64, n_rows // 2)
        else:
            n_worlds = max(32, n_worlds // 2)
        note = (f"population trimmed to {n_worlds}x{n_rows} for {n} sleeves "
                f"(<= {cfg.max_elements:,} elements)")

    rng = np.random.default_rng(cfg.seed)
    hist = np.stack([e.daily_r[-obs:].astype(np.float32) for e in ev], axis=1)   # (obs, N)
    sample_mean = hist.mean(axis=0)

    mu_draws, _post = _posterior_mu(ev, rng, n_worlds)

    # Decay: a multiplicative haircut on the EDGE only, never on the noise. An edge that has
    # halved still has its old volatility, and modelling decay as a scale on the whole return
    # series would quietly halve the risk along with the reward.
    decay = np.ones((n_worlds, n), dtype=np.float64)
    hit = rng.random((n_worlds, n)) < cfg.decay_prob
    decay[hit] = rng.uniform(cfg.decay_floor, 1.0, size=int(hit.sum()))

    # Execution cost: spread around the modelled level, in R, charged per day in proportion to
    # how often the sleeve trades (a sleeve flat 90% of days pays 10% of the daily cost draw).
    activity = (hist != 0.0).mean(axis=0)
    cost_lvl = np.array([abs(e.cost_r) for e in ev])
    cost_draw = rng.normal(0.0, cfg.cost_uncertainty, size=(n_worlds, n)) * cost_lvl[None, :]
    cost_draw = cost_draw * activity[None, :]

    crisis = rng.random(n_worlds) < cfg.crisis_prob

    # Regime pools: row positions in `hist` carrying each label, kept only where there are
    # enough of them to resample honestly. Anything thinner stays in the unconditioned pool.
    pools: dict[str, np.ndarray] = {}
    if cfg.regime_labels and cfg.regime_probs:
        labels = np.array(cfg.regime_labels[-obs:]) if len(cfg.regime_labels) >= obs else None
        if labels is not None and labels.size == obs:
            for name in {p[0] for p in cfg.regime_probs}:
                rows = np.flatnonzero(labels == name)
                if rows.size >= cfg.regime_min_days:
                    pools[name] = rows
    world_regime: list[str] = []
    if pools:
        keys = [k for k, _ in cfg.regime_probs if k in pools]
        wts = np.array([dict(cfg.regime_probs)[k] for k in keys], dtype=float)
        wts = wts / wts.sum() if wts.sum() > 0 else np.full(len(keys), 1.0 / len(keys))
        world_regime = list(rng.choice(keys, size=n_worlds, p=wts))
    else:
        world_regime = [""] * n_worlds

    # Each pool's OWN mean, because that is what a regime world must be recentred off. See the
    # comment on `shift` below -- this is the difference between regime conditioning and betting
    # on a subsample chosen for having gone up.
    pool_mean = {k: hist[v].mean(axis=0) for k, v in pools.items()}

    r = np.empty((n_worlds, n_rows, n), dtype=np.float32)
    for w in range(n_worlds):
        pool = pools.get(world_regime[w])
        if pool is None:
            idx = _stationary_bootstrap_index(n_rows, obs, cfg.block_days, rng)
            base_mean = sample_mean
        else:
            # Blocks are drawn inside the regime's own rows, so a regime world is made of days
            # that regime actually produced -- runs and all -- not of scattered singletons.
            idx = pool[_stationary_bootstrap_index(n_rows, pool.size, cfg.block_days, rng)]
            base_mean = pool_mean[world_regime[w]]
        block = hist[idx]                                        # (n_rows, N)
        # Recentre on the world's posterior mean, decayed: keep every higher moment of the real
        # history and move only the first one, which is the only moment the posterior is about.
        #
        # THE SUBTRACTED MEAN IS THE POOL'S, NOT THE FULL HISTORY'S, AND THAT IS LOAD-BEARING.
        # Subtracting the full-history mean from a REGIME block leaves the regime's excess mean
        # in the world at full, unshrunk strength -- and regime labels are derived from the same
        # price series the returns come from, so "bull/high vol" days are literally the days the
        # market went up. A long-biased sleeve earns money on them by construction. Measured
        # 2026-09-02: with the full-history mean subtracted and the classifier posterior sitting
        # at 100% on bull/high_vol, this allocator reported 3,862% annual growth and wanted 20%
        # heat, having been handed a population of worlds selected for having gone up.
        #
        # Recentring on the pool's own mean makes every world's expected mean the POSTERIOR draw,
        # whichever regime it was drawn from. The regime then contributes what it legitimately
        # knows -- volatility, dependence, run structure, fat tails -- and contributes nothing
        # through the one moment that would be contaminated. A sleeve that falls apart in
        # high-vol regimes is still punished, through the variance of those worlds.
        shift = (mu_draws[w] * decay[w] - base_mean - cost_draw[w]).astype(np.float32)
        world = block + shift[None, :]
        if crisis[w]:
            # Correlations converge in a crisis. A common factor carrying `crisis_common_share`
            # of each sleeve's variance reproduces that directly -- no correlation matrix to
            # estimate, no positive-definiteness to repair, and the tails stay the real ones.
            sd = world.std(axis=0)
            common = rng.standard_normal(n_rows).astype(np.float32)
            share = np.float32(cfg.crisis_common_share)
            idio = np.sqrt(np.float32(1.0) - share)
            world = (world - world.mean(axis=0)) * idio \
                + common[:, None] * (sd * np.sqrt(share))[None, :] \
                + world.mean(axis=0)[None, :]
            world = world * np.float32(cfg.crisis_vol_mult)
            # A crisis is not symmetric: the mean goes against the book too, not just the vol up.
            world = world - (np.abs(sd) * np.float32(0.25))[None, :]
        r[w] = world

    if cfg.regime_labels and not pools:
        note = (note + "; " if note else "") + \
            f"regime conditioning INACTIVE: no regime reached {cfg.regime_min_days} days"
    return Worlds(r=r, names=tuple(e.name for e in ev), crisis=crisis, mu_draws=mu_draws,
                  regimes=tuple(world_regime), note=note)


def project_capped_simplex(v: np.ndarray, cap: float, *, exact: bool = False,
                           upper: np.ndarray | None = None) -> np.ndarray:
    """Euclidean projection of `v` onto {0 <= h <= upper, sum(h) <= cap} (or == cap when `exact`).

    THIS IS THE HEAT CONSTRAINT, and expressing it as a projection is what lets the optimiser
    choose total exposure instead of being handed it. `exact=False` is pure growth: the book may
    hold back if nothing is worth betting on. `exact=True` is the full-utilisation mandate: the
    budget is spent, and the only question is on what.

    `upper` IS NOT DECORATION UNDER THE MANDATE. Measured 2026-09-02 on the 109-sleeve matrix,
    forcing total heat to 20% with no per-sleeve bound put 14.4 of those 20 points into
    AUDNZD_asia_TREND_DAY -- a sleeve the free optimiser gives exactly zero. That is not a
    mistake: told to spend a budget it does not believe in, the optimiser correctly parks the
    surplus in the lowest-variance thing it can find, and a near-cash sleeve is the cheapest
    place to lose the argument. The result is one position carrying most of the account's
    risk-at-stop, chosen for having the flattest backtest. A per-sleeve bound is what makes the
    mandate spend on the book rather than on the quietest row in the matrix.
    """
    if cap <= 0:
        return np.zeros_like(v)
    ub = np.full_like(v, np.inf) if upper is None else np.asarray(upper, dtype=float)
    if exact and float(ub.sum()) < cap - 1e-12:
        raise ValueError(f"per-sleeve bounds total {ub.sum():.4f}, below the mandated {cap:.4f}")
    clipped: np.ndarray = np.clip(v, 0.0, ub)
    if not exact and clipped.sum() <= cap:
        return clipped
    # Bisection on the shrink threshold tau: sum(clip(v - tau, 0, ub)) == cap. The sum is
    # monotone decreasing in tau, so the only requirement is a bracket that straddles the root.
    #
    # THE LOWER END MUST ACCOUNT FOR THE BOX. `v.max() - cap` brackets the unbounded problem,
    # where one entry can absorb the whole budget -- with an upper bound it cannot, so at that
    # tau the sum can still be BELOW cap and the bisection converges to the wrong side. Measured:
    # v=[9, .01, .01, .01, .01], cap=0.20, ub=0.05 returned 0.05, silently under-spending a
    # mandate by three quarters. Pushing tau down by cap + max(ub) forces every entry to its own
    # bound, where the sum is sum(ub) >= cap by the feasibility check above.
    finite = ub[np.isfinite(ub)]
    lo = float(v.min()) - float(cap) - (float(finite.max()) if finite.size else 0.0)
    hi = float(v.max())
    for _ in range(80):
        tau = 0.5 * (lo + hi)
        if np.clip(v - tau, 0.0, ub).sum() > cap:
            lo = tau
        else:
            hi = tau
    out: np.ndarray = np.clip(v - hi, 0.0, ub)
    return out


def _redundancy(corr_abs: np.ndarray, h: np.ndarray) -> tuple[float, np.ndarray]:
    """Correlation-weighted overlap of the book, and its gradient.

    `h' |C| h - h' h` is the risk that is DUPLICATED: everything the book holds twice. Charging
    it is what makes the optimiser prefer the same expected growth from more independent sources,
    and it is the term that stops a heat budget being filled with five copies of one dollar bet.
    """
    off = corr_abs @ h - h
    return float(h @ off), 2.0 * off


def _objective(worlds: Worlds, h: np.ndarray, corr_abs: np.ndarray, cfg: WorldConfig,
               ) -> tuple[float, np.ndarray, np.ndarray]:
    """Robust score, its gradient, and the per-world growth vector.

    Returns (-inf, zeros, g) when any world is wiped out by this book: a book that can go to zero
    has no log growth to compare, and reporting a large negative number instead would let the
    optimiser trade a real ruin path against a big enough average.
    """
    port = np.einsum("wtn,n->wt", worlds.r, h.astype(np.float32), optimize=True).astype(np.float64)
    one_plus = 1.0 + port
    if not np.all(one_plus > 1e-9):
        return -np.inf, np.zeros_like(h), np.full(worlds.n_worlds, -np.inf)

    g_w = np.log(one_plus).mean(axis=1)                                    # (W,)
    n_tail = max(1, round(cfg.cvar_alpha * worlds.n_worlds))
    tail = np.argpartition(g_w, n_tail - 1)[:n_tail]

    # World weights: uniform for the mean term, plus the tail worlds again for the CVaR term.
    a = np.full(worlds.n_worlds, (1.0 - cfg.robust_lambda) / worlds.n_worlds)
    a[tail] += cfg.robust_lambda / n_tail

    u = (1.0 / one_plus)                                                   # (W, T)
    uw = (u * a[:, None] / u.shape[1]).astype(np.float32)
    grad = np.einsum("wtn,wt->n", worlds.r, uw, optimize=True).astype(np.float64)

    score = float(a @ g_w)
    red, red_grad = _redundancy(corr_abs, h)
    return score - cfg.redundancy_lambda * red, grad - cfg.redundancy_lambda * red_grad, g_w


def _corr_abs(ev: Sequence[SleeveEvidence]) -> np.ndarray:
    """|correlation| between sleeves on their common history, zeros where it cannot be measured."""
    obs = min(int(e.daily_r.size) for e in ev)
    m = np.stack([e.daily_r[-obs:] for e in ev], axis=1)
    sd = m.std(axis=0)
    live = sd > 0
    c = np.zeros((len(ev), len(ev)))
    if live.sum() > 1:
        sub = np.corrcoef(m[:, live], rowvar=False)
        c[np.ix_(live, live)] = np.abs(np.nan_to_num(sub, nan=0.0))
    np.fill_diagonal(c, 1.0)
    return c


def optimise(ev: Sequence[SleeveEvidence], *, hard_cap: float, target: float | None = None,
             cfg: WorldConfig | None = None, worlds: Worlds | None = None,
             warm_start: Mapping[str, float] | None = None,
             max_per_sleeve: float | Mapping[str, float] | None = None,
             iterations: int = 400, step: float = 0.02) -> AllocationResult:
    """Solve for per-sleeve heat maximising the robust posterior E[log W].

    `hard_cap` is the ceiling total heat may never cross. `target`, when given, is the
    FULL-UTILISATION mandate: total heat is pinned to exactly that and the optimiser answers only
    "on what", not "how much". Pass `target=None` to get what growth actually wants, which is the
    number that certifies whether a mandated target is safe (`heat_policy.certify`).

    `max_per_sleeve` bounds any single sleeve's heat -- a float applied to all, or a per-name
    mapping. It exists for the mandated case; see `project_capped_simplex` for what happens
    without it.

    Projected gradient ascent with backtracking: the objective is concave in `h` on the feasible
    set (log of an affine function, minus a positive-semidefinite quadratic), so a projected
    gradient converges to the global optimum and there is no restart strategy to get wrong.
    """
    cfg = cfg or WorldConfig()
    if not ev:
        raise ValueError("no sleeves to allocate over")
    w_pop = worlds if worlds is not None else sample_worlds(ev, cfg)
    corr_abs = _corr_abs(ev)
    names = [e.name for e in ev]
    n = len(ev)

    exact = target is not None
    cap = float(hard_cap) if target is None else float(target)
    if exact and cap > hard_cap:
        raise ValueError(f"target heat {cap:.4f} exceeds hard cap {hard_cap:.4f}")

    if max_per_sleeve is None:
        ub = np.full(n, np.inf)
    elif isinstance(max_per_sleeve, Mapping):
        ub = np.array([float(max_per_sleeve.get(k, np.inf)) for k in names])
    else:
        ub = np.full(n, float(max_per_sleeve))

    if warm_start:
        h = np.array([float(warm_start.get(k, 0.0)) for k in names])
        h = project_capped_simplex(h, cap, exact=exact, upper=ub)
    else:
        h = project_capped_simplex(np.full(n, cap / n), cap, exact=exact, upper=ub)

    score, grad, g_w = _objective(w_pop, h, corr_abs, cfg)
    # A RUINOUS START MUST BACK OFF UNTIL IT IS NOT, and a single halving is not "until".
    # -inf > -inf is False, so the ascent below cannot move off a ruinous point: it would return
    # whatever heat it started with, carrying a -inf score nobody downstream reads as a refusal.
    # Measured: a sleeve with one -50R day kept 7.5% heat that way.
    #
    # Only the FREE solve may back off. Under the mandate the total is the principal's, so a
    # ruinous mandated book is reported ruinous (mean_log_growth = -inf, prob_annual_loss = 1.0)
    # and `pf_allocator` routes it to the catastrophe layer, which is the one thing allowed to
    # take exposure below target.
    if score == -np.inf and not exact:
        shrink = 1.0
        while score == -np.inf and shrink > 1e-3:
            shrink *= 0.25
            h = project_capped_simplex(np.full(n, cap * shrink / n), cap * shrink,
                                       exact=False, upper=ub)
            score, grad, g_w = _objective(w_pop, h, corr_abs, cfg)
        if score == -np.inf:
            h = np.zeros(n)
            score, grad, g_w = _objective(w_pop, h, corr_abs, cfg)

    lr, converged, done = step, False, 0
    for i in range(iterations):
        done = i + 1
        cand = project_capped_simplex(h + lr * grad, cap, exact=exact, upper=ub)
        c_score, c_grad, c_g = _objective(w_pop, cand, corr_abs, cfg)
        if c_score > score:
            moved = float(np.abs(cand - h).sum())
            h, score, grad, g_w = cand, c_score, c_grad, c_g
            lr *= 1.10
            if moved < 1e-7:
                converged = True
                break
        else:
            lr *= 0.5
            if lr < 1e-9 or score == -np.inf:
                # -inf cannot be improved on by comparison, so an exact solve that starts ruinous
                # would otherwise spin the full iteration budget doing nothing.
                converged = True
                break

    total = float(h.sum())
    # Marginal value of each sleeve's last unit of heat, at the solution. This is the ranking the
    # execution path must trim by when it cannot fit the whole book -- dropping the sleeve with
    # the lowest marginal value costs the least growth, which a fixed name order cannot know.
    marginal = {names[i]: float(grad[i]) for i in range(n)}

    finite = g_w[np.isfinite(g_w)]
    mean_g = float(finite.mean()) if finite.size else float("-inf")
    n_tail = max(1, round(cfg.cvar_alpha * max(finite.size, 1)))
    cvar_g = float(np.sort(finite)[:n_tail].mean()) if finite.size else float("-inf")
    ann = (float(np.exp(mean_g * 252.0)) - 1.0) * 100.0 if np.isfinite(mean_g) else float("-inf")
    p_loss = float((finite <= 0.0).mean()) if finite.size else 1.0

    return AllocationResult(
        heat={names[i]: float(h[i]) for i in range(n)},
        total_heat=total, robust_score=score, mean_log_growth=mean_g, cvar_log_growth=cvar_g,
        annual_growth_pct=round(ann, 2), prob_annual_loss=round(p_loss, 4),
        marginal={k: round(v, 6) for k, v in
                  sorted(marginal.items(), key=lambda kv: -kv[1])},
        iterations=done, converged=converged, note=w_pop.note,
    )


def score_book(ev: Sequence[SleeveEvidence], heat: Mapping[str, float], *,
               cfg: WorldConfig | None = None, worlds: Worlds | None = None) -> dict[str, float]:
    """Growth of a GIVEN book on the world population -- no optimisation, no reweighting.

    This is what a rebalance must be measured against. Comparing a proposed book to the FREE
    optimum answers "how far from ideal is this", which is not the question: the question is
    whether moving from what the desk holds NOW to the proposal buys more than the turnover
    costs, and that needs the current holdings scored on the same worlds.
    """
    cfg = cfg or WorldConfig()
    w_pop = worlds if worlds is not None else sample_worlds(ev, cfg)
    h = np.array([float(heat.get(n, 0.0)) for n in w_pop.names])
    score, _grad, g_w = _objective(w_pop, h, _corr_abs(ev), cfg)
    finite = g_w[np.isfinite(g_w)]
    mean_g = float(finite.mean()) if finite.size else float("-inf")
    n_tail = max(1, round(cfg.cvar_alpha * max(finite.size, 1)))
    return {
        "total_heat": float(h.sum()),
        "robust_score": score,
        "mean_log_growth": mean_g,
        "cvar_log_growth": float(np.sort(finite)[:n_tail].mean()) if finite.size else -np.inf,
        "annual_growth_pct": ((float(np.exp(mean_g * 252.0)) - 1.0) * 100.0
                              if math.isfinite(mean_g) else float("-inf")),
        "prob_annual_loss": float((finite <= 0.0).mean()) if finite.size else 1.0,
    }


def marginal_delta_elog(current: Sequence[SleeveEvidence], candidate: SleeveEvidence, *,
                        hard_cap: float, target: float | None = None,
                        max_per_sleeve: float | Mapping[str, float] | None = None,
                        cfg: WorldConfig | None = None) -> dict[str, float | bool | str]:
    """What admitting `candidate` is worth: dG = G*(current + candidate) - G*(current).

    BOTH BOOKS ARE RE-SOLVED. "The book is full, reject it" is not an answer this function can
    give: if the candidate improves robust growth, the optimiser finds the heat for it by taking
    heat from everything else, and the returned `reallocation` says which sleeves paid for it. A
    candidate that earns near-zero heat has been evaluated and declined on the arithmetic, which
    is a different and much more useful outcome than never having been compared.
    """
    cfg = cfg or WorldConfig()
    if any(c.name == candidate.name for c in current):
        raise ValueError(f"{candidate.name} is already in the book")
    base = optimise(current, hard_cap=hard_cap, target=target, cfg=cfg,
                    max_per_sleeve=max_per_sleeve)
    ext = optimise([*current, candidate], hard_cap=hard_cap, target=target, cfg=cfg,
                   max_per_sleeve=max_per_sleeve)
    realloc = {k: round(ext.heat.get(k, 0.0) - v, 6) for k, v in base.heat.items()}
    got = float(ext.heat.get(candidate.name, 0.0))

    def _delta(a: float, b: float) -> float:
        # -inf minus -inf is nan, and a nan in an artifact reads like a measurement that was
        # taken. Both books ruinous is not "no difference" -- it is a refusal, and the caller
        # sees it as -inf plus admit=False rather than as a number.
        if not (math.isfinite(a) and math.isfinite(b)):
            return float("-inf")
        return a - b

    return {
        "candidate": candidate.name,
        "ruinous": not (math.isfinite(base.mean_log_growth)
                        and math.isfinite(ext.mean_log_growth)),
        "delta_robust": round(_delta(ext.robust_score, base.robust_score), 8),
        "delta_annual_growth_pct": round(
            _delta(ext.annual_growth_pct, base.annual_growth_pct), 3),
        "candidate_heat": round(got, 6),
        "total_heat_before": round(base.total_heat, 6),
        "total_heat_after": round(ext.total_heat, 6),
        "admit": bool(math.isfinite(ext.robust_score)
                      and ext.robust_score > base.robust_score and got > 1e-5),
        "reallocation": realloc,                                   # type: ignore[dict-item]
    }
