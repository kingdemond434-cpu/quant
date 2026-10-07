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
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

__all__ = [
    "AllocationResult",
    "SleeveEvidence",
    "WorldConfig",
    "Worlds",
    "crisis_share_vector",
    "decay_prob_of",
    "fw_gap",
    "fw_vertex",
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
    #: THE COST THE REPLAY DID NOT CHARGE, in R per trade, MEASURED (`libs.portfolio.
    #: execution_cost`). Not a second charge of the modelled cost: the modelled cost was applied
    #: at the POOLED median spread, and `cost_surface` measured that the spread at some sleeves'
    #: OWN FILL HOUR is up to six times that -- USDZAR 329 pts pooled against 2,028 pts on its
    #: own fill bars, on a live certified sleeve. This is the DIFFERENCE, and it shifts the
    #: posterior mean down deterministically in proportion to how often the sleeve trades.
    #:
    #: THIS IS WHAT "EXECUTION IS AUTHORITY-BEARING" MEANS IN ARITHMETIC. There is no rule about
    #: spreads and no veto: a sleeve whose edge does not survive its own fill hour simply stops
    #: being profitable, and an optimiser maximising E[log W] stops funding it without being told
    #: to. 0.0 is the honest default and means "unpriced", never "cheap".
    cost_bias_r: float = 0.0
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
    #: THIS SLEEVE'S OWN DECAY PROBABILITY, or None for the blanket `WorldConfig.decay_prob`.
    #: Until 2026-09-08 every sleeve paid the same 30% chance of a decayed edge in every world,
    #: whatever the drift monitor had measured about it, and the only per-sleeve decay input was
    #: a separate post-hoc shrink of the posterior mean. This is the per-sleeve posterior the
    #: decay haircut is drawn from instead.
    #:
    #: TWO-SIDED SINCE 2026-10-06 (principal's spec of that date). Until then the blanket was the
    #: CEILING -- `min(decay_prob_i, cfg.decay_prob)` -- so a sleeve the drift monitor measured at
    #: a 90% chance of its mechanism breaking was charged exactly the 30% an unwatched sleeve
    #: paid: relief-only, and a breaking edge kept its heat. Now `decay_prob_of` uses the
    #: sleeve's own probability in BOTH directions: below the blanket it relieves, above it it
    #: charges more, so a breaking sleeve is sized down before any retirement threshold.
    #:
    #: WHAT MAY BE IN IT. Only MECHANISM decay (and signal expiry on its own horizon) --
    #: `perishability.hazard_by_cause` keeps execution-cost drift (routed to `cost_bias_r`),
    #: regime mismatch (transient) and data failure (integrity) out of this number, so no fact
    #: is charged here AND somewhere else. None, non-finite or negative is the blanket (an
    #: unpriced decay is the blanket, never zero); above 1 is clamped to 1. `cfg.decay_prob == 0`
    #: still switches decay OFF for the whole population: that is how the decay-free reference
    #: (`kelly_fraction`'s full-Kelly yardstick) is drawn, whatever the sleeves carry.
    #:
    #: SLEEVES SHARING A MECHANISM DECAY TOGETHER. `sample_worlds` correlates the decay draw
    #: across sleeves with the same `mechanism` (else `family`): a mechanism that stops being
    #: true stops for every instrument it is traded on (`DECAY_MECHANISM_SHARE`).
    decay_prob_i: float | None = None
    #: THE MACRO REGIME, AS A WEIGHT PER DAY OF `daily_r` (2026-09-16). Each entry in [0, 1] is
    #: how much that day's macro state (dollar / risk / rates rank, `libs.portfolio.macro_state`)
    #: resembled TODAY's. `_posterior_mu` forms the sleeve's regime-weighted mean as a CONTRAST
    #: against its unconditional mean on the same days, shrinks it, bounds it, and tilts the
    #: posterior by it. Empty (the default) or mismatched in length means "no regime
    #: information", and the posterior is exactly what it was before this field existed. Uniform
    #: weights mean the same thing arithmetically: the contrast is zero.
    macro_w: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    #: WHITENED FACTOR LOADINGS (`libs.portfolio.leg_factors.fit_loadings`): `u = L' b` with
    #: `F = L L'` the factor correlation, so the dot product of two sleeves' loadings IS their
    #: factor covariance. `_corr_abs` uses it as the correlation TARGET for every pair whose
    #: realised history is too short to measure -- the covariance the book has on day one, before
    #: any two sleeves have twenty common days. Empty means no structure is claimed.
    factor_load: tuple[float, ...] = ()
    #: Residual (idiosyncratic) variance left by the factors, in (R/day)^2; the denominator that
    #: turns a factor covariance into a factor correlation.
    factor_resid_var: float = 0.0
    #: THE THREE DIMENSIONS OF SAMENESS THE RETURNS CANNOT SHOW (Tier-1 B13). Covariance, factor
    #: and tail breadth are measured; two sleeves can still be the same bet for reasons no return
    #: series carries. Each is EMPTY by default, and empty means the pair is scored exactly as it
    #: was before these fields existed -- a caller that cannot say is never charged for saying so.
    #:
    #: `inputs`   the data the sleeve reads, as opaque keys ("bars:XAUUSD:H1", "tape:XAUUSD").
    #:            Two sleeves reading one file cannot be two independent draws on the world.
    #: `trade_hours` the UTC hours its trades were actually ENTERED in, measured from its own
    #:            fills. This one is TWO-SIDED and that is the point: it raises the floor for
    #:            pairs that trade together and LOWERS the same-instrument prior for pairs whose
    #:            hours are disjoint, because two sleeves that never trade at the same time
    #:            cannot be taking the same trade whatever their family says.
    #: `mechanism` the causal story, as declared. Same mechanism on two instruments is one bet
    #:            on that mechanism being true.
    inputs: tuple[str, ...] = ()
    trade_hours: tuple[int, ...] = ()
    mechanism: str = ""

    def __post_init__(self) -> None:
        if self.daily_r.ndim != 1:
            raise ValueError(f"{self.name}: daily_r must be 1-D, got {self.daily_r.shape}")

    @property
    def own_r(self) -> np.ndarray:
        """The days this sleeve ACTUALLY LIVED -- NaN dropped, never zero-filled.

        THE TWO READINGS OF `daily_r`, AND WHY CONFUSING THEM IS DEFECT #4. `daily_r` is aligned
        onto the whole book's calendar so the bootstrap can draw a day across every sleeve at
        once; on that calendar a sleeve carries NaN before it was born. Those NaNs answer two
        different questions and must not be filled the same way:

          * "what is THIS SLEEVE's mean / dispersion / sample size?"  -> `own_r`. A day it did
            not exist is not an observation of zero return. Filling it divided a fortnight-old
            clock's mean by 2,260, flattened its std, and told the shrinkage it had 2,260
            observations -- diluted toward zero AND falsely confident, the worst possible pair.
          * "what did the BOOK earn that day?"  -> `np.nan_to_num(daily_r)`. A sleeve that did
            not exist contributed no P&L, which is genuinely 0.0. That is the protocol's "flat
            only at portfolio level, explicitly", and every cross-sleeve stack does it locally.

        Use `own_r` for anything describing one sleeve; fill for anything summing across them.
        """
        a = np.asarray(self.daily_r, dtype=float)
        out: np.ndarray = a[np.isfinite(a)]
        return out


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
    #: PER-SLEEVE common-factor share in crisis worlds, `((name, share), ...)`; a name absent
    #: here carries `crisis_common_share`. A one-factor overlay at shares s_i, s_j has pairwise
    #: crisis correlation sqrt(s_i s_j), so a metals sleeve measured at 0.30 and a USD-leg sleeve
    #: at 0.55 converge to 0.41 in a crisis instead of both being fused at 0.55.
    #:
    #: THE BOOK-WIDE SCALAR IS THE CEILING. Each entry is applied at `min(share, crisis_common_
    #: share)`: the scalar is the RATCHETED number (`conditional_covariance.calibrate` only ever
    #: raises it), and this vector may say a factor block is LESS fused than the book, never more
    #: -- so no sleeve is ever stressed harder than it is today by this field.
    crisis_common_share_by_sleeve: tuple[tuple[str, float], ...] = ()
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
    #: True when `optimise` stopped on its wall-clock `deadline` rather than on convergence or
    #: the iteration budget. A partial solve is still a feasible book with a real score; the flag
    #: is what lets a caller carry it forward warm-started instead of calling it an answer.
    budget_hit: bool = False
    #: Frank-Wolfe gap at the returned book: zero at a KKT point of the heat set. inf when the
    #: book is ruinous. `converged` means gap <= tolerance -- a LOCAL certificate only.
    optimality_gap: float = float("inf")
    gap_tolerance: float = 0.0
    #: Best minus worst robust score across the starts tried; > tolerance means a start stalled.
    multistart_spread: float = 0.0
    n_starts: int = 1
    #: What is certified. "local_kkt_multistart" when only stationarity is shown;
    #: "global_bound" when `global_gap` (a TRUE bound on the distance to the global optimum, see
    #: `optimise`) is within tolerance.
    certificate: str = "local_kkt_multistart"
    #: Upper bound on the global optimum of the real objective, and score's distance below it.
    upper_bound: float = float("inf")
    global_gap: float = float("inf")


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


def _asset_class(symbol: str) -> str:
    """The desk's own classifier, imported -- never a second spelling of it.

    `mt5desk.universe.asset_class` already knows that XAUUSD is a metal before it is FX and that
    the bond roots are prefix-only (a contains-test once made the Euro Stoxx 50 a bond). This
    library is importable from hosts that do not carry the desk package, so a failure falls back
    to one bucket, which makes the class level inert rather than wrong.
    """
    try:
        from mt5desk.universe import asset_class
    except Exception:
        try:
            import sys
            desk = str(Path(__file__).resolve().parents[2] / "desks" / "mt5")
            if desk not in sys.path:
                sys.path.insert(0, desk)
            from mt5desk.universe import asset_class
        except Exception:
            return "unknown"
    # NO SYMBOL IS NOT A CLASS. A sleeve that carries no instrument gets "", and "" never pools:
    # the desk's classifier falls back to `equity` for an unrecognised ticker, so an empty symbol
    # would have put every metadata-less sleeve into ONE group and let them borrow each other's
    # means. Measured while building this: two unrelated test sleeves with no symbols were pooled
    # and the short one stopped being shrunk toward no-edge -- the exact protection this file
    # exists to provide. No metadata, no borrowing.
    if not str(symbol or "").strip():
        return ""
    try:
        c = str(asset_class(symbol) or "")
    except Exception:
        return ""
    # "unknown" IS NOT A CLASS EITHER, for the same reason: it is the classifier's way of saying
    # it could not place the ticker, and pooling everything it could not place would let unrelated
    # instruments borrow each other's means under a label that means "we do not know".
    return "" if c == "unknown" else c


def _posterior_mu(ev: Sequence[SleeveEvidence], rng: np.random.Generator,
                  n_worlds: int, diag: dict[str, Any] | None = None,
                  ) -> tuple[np.ndarray, np.ndarray]:
    """Hierarchical posterior draws of each sleeve's mean daily R.

    `diag`, when a dict is passed, is filled with the macro-regime tilt per sleeve and the final
    posterior mean and standard error -- for the allocation artifact, never for the arithmetic.

    THE PRIOR IS NO EDGE, and that is the whole point. A sleeve is in this matrix because it
    measured well, so its sample mean is biased upward by selection. The posterior mean is the
    sample mean shrunk toward the family mean and the family mean shrunk toward zero, by
    n / (n + k) -- so a sleeve with 40 backtest days and no forward evidence is pulled most of the
    way to zero, and one with a year of live evidence is barely moved. Sizing on the unshrunk
    mean is how a desk ends up with its largest position in its luckiest backtest.

    Returns (draws (W, N), posterior_mean (N,)).
    """
    n = len(ev)
    # NaN IS "THIS SLEEVE DID NOT EXIST THAT DAY", AND IT IS NOT A ZERO RETURN. This is the
    # desk's shipped defect #4 (UNIVERSAL_PROMOTION_PROTOCOL: "absent trade -> NaN day (never 0);
    # flat only at portfolio level, explicitly"), and it lands hardest exactly where the desk can
    # least afford it -- on a NEW sleeve, the only kind that can still be promoted.
    #
    # A sleeve aligned onto the book's 2,260-day union carries a real value on the days it has
    # lived and NaN on the rest. Reading those as 0.0 corrupted all three statistics at once:
    #   mean -- divided by 2,260 instead of its own day count (a 173x dilution at 13 days)
    #   std  -- computed over a spike of zeros, understating its true dispersion
    #   obs  -- 2,260, so the shrinkage treated a fortnight-old clock as PRECISELY ESTIMATED
    # Diluted toward zero AND falsely confident about it, which is the worst pair: the posterior
    # then shrinks a sleeve to nothing and reports high certainty that nothing is right.
    #
    # MEASURED 2026-09-10 on the three matured scalp clocks: standalone Sharpe 3.71 / 11.86 /
    # 3.94 on their own days, reported to the optimiser as 0.285 / 0.766 / 0.312 -- understated
    # 13.0x / 15.5x / 12.6x -- and refused at "0.0000% heat, the book does not want it at any
    # size" against a book holding sleeves at 3.1-3.2. The allocator was not being conservative;
    # it was answering correctly on a corrupted input.
    #
    # The portfolio level is UNCHANGED and still treats an absent day as flat -- see the
    # `nan_to_num` at each stacking site, which is where "flat, explicitly" belongs.
    own = [e.own_r for e in ev]
    m = np.array([float(a.mean()) if a.size else 0.0 for a in own])
    s = np.array([float(a.std(ddof=1)) if a.size > 1 else 0.0 for a in own])
    obs = np.array([float(a.size) for a in own])

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

    # ------------------------------------------------ ASSET CLASS, THE LEVEL ABOVE THE MECHANISM
    # MEASURED 2026-09-08 (Tier-1 item P11): the hierarchy was sleeve -> family -> ZERO, and
    # `family` is the MECHANISM. So evidence on XAUUSD reached XAGUSD only if both carried the
    # same mechanism string, and a new instrument in a proven asset class inherited nothing at
    # all: its outer prior was no-edge. That is the right prior for a new MECHANISM and the wrong
    # one for a new INSTRUMENT of a mechanism the desk already trades.
    #
    # ONE-SIDED, BY THE PRINCIPAL'S STANDING ORDER. The class mean enters through max(., 0): it
    # can only RELIEVE the pull toward zero, never deepen it. A negative class mean leaves the
    # posterior exactly where it is today, so no sleeve is ever sized smaller than it is now by
    # this level -- proven element-wise by test_asset_class_pooling_never_shrinks.
    classes = [_asset_class(e.symbol) for e in ev]
    cls_mean: dict[str, float] = {}
    cls_w: dict[str, float] = {}
    for c in set(classes):
        rows = [i for i, x in enumerate(classes) if x == c]
        wts = fam_w[rows]
        cls_mean[c] = float(np.average(m[rows], weights=wts)) if wts.sum() > 0 else 0.0
        cls_w[c] = float(wts.sum())
    cls_vec = np.array([max(cls_mean[c], 0.0) if c else 0.0 for c in classes])
    cls_eff = np.array([cls_w[c] if c else 0.0 for c in classes])
    #: An asset class needs more evidence than a mechanism to speak, because it is a weaker claim:
    #: "metals work" is a broader statement than "this mechanism works", and the wider the group
    #: the more of its mean is other instruments' luck.
    k_class = 240.0
    lam_c = cls_eff / (cls_eff + k_class)

    post_mean = lam_s * m + (1.0 - lam_s) * (
        lam_f * fam_vec + (1.0 - lam_f) * (lam_c * cls_vec))
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

    # ------------------------------------------------------------ THE MACRO REGIME, FIFTH LEVEL
    # THE WORLD OUTSIDE THE PRICE SERIES WAS NOT IN THE ESTIMATE. Every level above conditions
    # on the sleeve's own history and on the hour; none asks whether the desk is in a strong-
    # dollar year or a weak one, a risk-on tape or a risk-off one. So a dollar-bull sleeve and a
    # dollar-bear sleeve on the same pair carried the same expectancy into a regime that can only
    # pay one of them, and the only thing that could tell them apart was a per-ORDER multiplier
    # at the venue (`mt5desk.macro_view`), which cannot move heat between sleeves at all.
    #
    # THE ESTIMATE IS A CONTRAST, NOT A CONDITIONAL MEAN, and that is what keeps it honest under
    # the deflation above. `macro_w` weights each of the sleeve's OWN days by how much that day's
    # macro state resembled today's; the regime-weighted mean minus the plain mean OVER THE SAME
    # DAYS is the sleeve's excess return in regimes like this one. A conditional mean used raw
    # would walk around the winner's-curse deflation (a backtest bucket at lam 0.9 is the
    # unshrunk backtest again); a contrast cancels the selection bias and every pooling above it
    # to first order, because both sides carry them equally.
    #
    # SHRUNK AT k=60 EFFECTIVE DAYS -- `n_eff = (sum w)^2 / sum w^2`, the Kish count, so a kernel
    # that puts most of its mass on a handful of days is treated as the handful it is -- and
    # BOUNDED by the larger of the posterior's own magnitude and half its standard error: a
    # regime may double a sleeve's expectancy or take it to zero, and may move a heavily-shrunk
    # new sleeve within its own uncertainty, but it cannot manufacture an edge the evidence does
    # not carry. Uncertainty widens by the tilt, as at the state level; the CVaR objective then
    # sizes the doubt. TWO-SIDED (registered `macro_regime`): sleeves that earned LESS in
    # regimes like this one are tilted down by the same rule, and the total heat is untouched --
    # what moves is which sleeves the heat buys.
    k_macro = 60.0
    macro_tilt = np.zeros(n)
    macro_meta: list[dict[str, float]] = []
    for i, e in enumerate(ev):
        w = np.asarray(getattr(e, "macro_w", ()), dtype=float)
        a = np.asarray(e.daily_r, dtype=float)
        if w.size == 0 or w.size != a.size:
            continue
        # A day with a KNOWN weight is on the unconditional side whatever its weight; only a day
        # with no state (NaN) leaves the contrast. Keeping only w > 0 compared the regime days
        # with themselves and returned exactly zero (the first test of this level caught it).
        keep = np.isfinite(a) & np.isfinite(w)
        if int(keep.sum()) < 2:
            continue
        ww, aa = w[keep], a[keep]
        sw = float(ww.sum())
        if sw <= 0.0:
            continue
        m_regime = float((ww * aa).sum() / sw)
        n_eff_w = sw * sw / float((ww * ww).sum())
        delta = m_regime - float(aa.mean())
        lam_m = n_eff_w / (n_eff_w + k_macro)
        tilt = lam_m * delta
        bound = max(abs(float(post_mean[i])), 0.5 * float(se[i]))
        tilt = float(min(bound, max(-bound, tilt)))
        macro_tilt[i] = tilt
        macro_meta.append({"i": float(i), "n_eff": n_eff_w, "delta": delta, "lam": lam_m,
                           "tilt": tilt, "bound": bound})
    if np.any(macro_tilt != 0.0):
        post_mean = post_mean + macro_tilt
        se = se + np.abs(macro_tilt)
    if diag is not None:
        diag["macro"] = {ev[int(m["i"])].name: {k: round(float(v), 8) for k, v in m.items()
                                                if k != "i"} for m in macro_meta}
        diag["post_mean"] = {e.name: float(post_mean[i]) for i, e in enumerate(ev)}
        diag["se"] = {e.name: float(se[i]) for i, e in enumerate(ev)}

    draws = post_mean[None, :] + rng.standard_normal((n_worlds, n)) * se[None, :]
    return draws, post_mean


#: HOW MUCH OF A SLEEVE'S DECAY RISK IS ITS MECHANISM'S, not its own (2026-10-06). In each world a
#: sleeve's decay uniform is, with this probability, its mechanism's COMMON uniform, else its own:
#: every sleeve keeps exactly its own marginal P(decay) -- the one fact `decay_prob_i` states is
#: charged once, unchanged -- while siblings decay together. At 0.7 and p = 0.30 two siblings
#: decay jointly in 0.49p + 0.51p^2 = 19% of worlds instead of 9%, so given one has decayed the
#: other has a 64% chance, not 30%. DECLARED, not fitted: the desk's retirement history holds no
#: co-retirement of siblings to fit it to (`perishability.calibrate_from_history`); the one
#: pooled family retirement it ordered (decay_monitor, 2026-09-16, the `discovered` family) is
#: exactly the event this models and is not in the ledger this host can read.
DECAY_MECHANISM_SHARE = 0.7


def decay_group_of(e: SleeveEvidence) -> str:
    """The shared-failure key: the declared mechanism, else the family, else no group ("")."""
    return str(getattr(e, "mechanism", "") or getattr(e, "family", "") or "")


def decay_prob_of(e: SleeveEvidence, cfg: WorldConfig) -> float:
    """The decay probability THIS sleeve is charged: its own posterior, in BOTH directions.

    TWO-SIDED (2026-10-06; it was `min(own, blanket)` -- relief-only -- from 2026-09-08). A
    measured probability above the blanket now charges MORE than the blanket, so a breaking
    mechanism is sized down; below it, it relieves. None, a non-finite or a negative value falls
    back to the blanket -- an unpriced or malformed decay is the blanket, never zero, and a
    negative is not clamped to 0 because that would turn a corrupt number into full relief. Above
    1 is clamped to 1. A population drawn with `cfg.decay_prob == 0` is decay-free whatever the
    sleeves carry: that switch is how the decay-free reference is drawn.
    """
    blanket = float(cfg.decay_prob)
    if blanket <= 0.0:
        return 0.0
    p = getattr(e, "decay_prob_i", None)
    if p is None:
        return blanket
    try:
        v = float(p)
    except (TypeError, ValueError):
        return blanket
    if not math.isfinite(v) or v < 0.0:
        return blanket
    return min(v, 1.0)


def crisis_share_vector(names: Sequence[str], cfg: WorldConfig) -> np.ndarray:
    """Per-sleeve crisis common-factor share as float32, each entry <= the book-wide scalar."""
    scalar = float(cfg.crisis_common_share)
    by_name = {}
    for k, v in (cfg.crisis_common_share_by_sleeve or ()):
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            by_name[str(k)] = min(max(f, 0.0), scalar)
    return np.array([by_name.get(str(n), scalar) for n in names], dtype=np.float32)


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
    # FLAT AT PORTFOLIO LEVEL, EXPLICITLY (protocol rule for defect #4). A day this sleeve did
    # not exist for contributes no P&L to the book, which IS 0.0 here -- the bootstrap draws whole
    # days across sleeves and needs a rectangular history to keep co-occurrence real. The sleeve's
    # OWN mean/std/n are taken from its own days in `_posterior_mu`; only this joint matrix fills.
    hist = np.stack([np.nan_to_num(e.daily_r[-obs:], nan=0.0).astype(np.float32) for e in ev],
                    axis=1)                                                     # (obs, N)
    sample_mean = hist.mean(axis=0)

    mu_draws, _post = _posterior_mu(ev, rng, n_worlds)

    # Decay: a multiplicative haircut on the EDGE only, never on the noise. An edge that has
    # halved still has its old volatility, and modelling decay as a scale on the whole return
    # series would quietly halve the risk along with the reward.
    #
    # PER SLEEVE, TWO-SIDED (2026-10-06). `decay_prob_of` is the sleeve's own probability of its
    # mechanism having broken, above or below the blanket; the blanket is what an unmeasured
    # sleeve pays. The main random stream is the same one the scalar draw used, so a population
    # in which every sleeve carries the blanket and no two share a mechanism is byte-identical
    # to the one drawn before either change.
    #
    # SHARED MECHANISM, SHARED FAILURE. Sleeves with the same `decay_group_of` key take, with
    # probability DECAY_MECHANISM_SHARE, their group's COMMON uniform instead of their own, so
    # when a mechanism stops being true it stops in the same world for every instrument it is
    # traded on -- independent draws would let ten sleeves of one mechanism diversify away a
    # failure that is in fact one event. The common uniforms and the coin come from a SIDE
    # stream seeded off `cfg.seed`, so the main stream (posterior, cost, crisis, bootstrap) is
    # untouched by grouping, and each sleeve's marginal P(decay) is still exactly its own.
    decay = np.ones((n_worlds, n), dtype=np.float64)
    p_decay = np.array([decay_prob_of(e, cfg) for e in ev], dtype=np.float64)
    u_decay = rng.random((n_worlds, n))
    groups: dict[str, list[int]] = {}
    for i, e in enumerate(ev):
        key = decay_group_of(e)
        if key:
            groups.setdefault(key, []).append(i)
    shared = [m for m in groups.values() if len(m) >= 2]
    if shared and DECAY_MECHANISM_SHARE > 0.0:
        side = np.random.default_rng([abs(int(cfg.seed)), 0xDECA])
        common = side.random((n_worlds, len(shared)))
        for g, members in enumerate(shared):
            take = side.random((n_worlds, len(members))) < DECAY_MECHANISM_SHARE
            u_decay[:, members] = np.where(take, common[:, [g]], u_decay[:, members])
    hit = u_decay < p_decay[None, :]
    # ONE DEPTH PER CELL, DRAWN WHETHER OR NOT THE CELL DECAYS (2026-10-06). The depth used to be
    # drawn only for the cells that hit, so the number of uniforms consumed depended on the
    # sleeves' probabilities and every later draw -- cost, crisis, the bootstrap itself -- moved
    # whenever one sleeve's decay_prob_i did. The with/without-hazard billing pair and every
    # "relief earns at least as much heat" comparison were then two different populations, not
    # one population differing only in which sleeves decay where. A fixed-size draw makes them
    # common random numbers, which is what both comparisons always claimed to be.
    depth = rng.uniform(cfg.decay_floor, 1.0, size=(n_worlds, n))
    decay = np.where(hit, depth, decay)

    # Execution cost: spread around the modelled level, in R, charged per day in proportion to
    # how often the sleeve trades (a sleeve flat 90% of days pays 10% of the daily cost draw).
    activity = (hist != 0.0).mean(axis=0)
    cost_lvl = np.array([abs(e.cost_r) for e in ev])
    cost_draw = rng.normal(0.0, cfg.cost_uncertainty, size=(n_worlds, n)) * cost_lvl[None, :]
    # THE MEASURED UNDER-CHARGE, added to the ZERO-MEAN spread above. The draw says "the cost is
    # uncertain by this much"; the bias says "and it is this much larger than the returns claim".
    # They are different statements and only the second can make a sleeve unprofitable, which is
    # exactly what it is for. Deterministic, not drawn: it is a measurement, so treating it as
    # noise would let half the worlds pretend it is not there.
    cost_bias = np.array([max(0.0, float(getattr(e, "cost_bias_r", 0.0))) for e in ev])
    cost_draw = (cost_draw + cost_bias[None, :]) * activity[None, :]

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

    # The crisis common-factor share, per sleeve, with the book-wide scalar as the ceiling (see
    # `WorldConfig.crisis_common_share_by_sleeve`). One vector, built once, outside the loop.
    share_vec = crisis_share_vector(tuple(e.name for e in ev), cfg)
    idio_vec = np.sqrt(np.float32(1.0) - share_vec)
    root_share_vec = np.sqrt(share_vec)

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
            # The share is a per-sleeve vector (a factor block measured less fused than the book
            # loads less on the common factor); with every entry at the scalar the arithmetic
            # is exactly the scalar overlay.
            sd = world.std(axis=0)
            common = rng.standard_normal(n_rows).astype(np.float32)
            world = (world - world.mean(axis=0)) * idio_vec[None, :] \
                + common[:, None] * (sd * root_share_vec)[None, :] \
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


def fw_vertex(grad: np.ndarray, cap: float, *, exact: bool = False,
              upper: np.ndarray | None = None) -> np.ndarray:
    """argmax over {0 <= s <= upper, sum(s) <= cap (== cap when exact)} of grad . s.

    The linear oracle of the heat set: fill the highest-gradient sleeves to their bound until the
    budget is spent; a free solve stops at the first non-positive gradient, a mandated one does not.
    """
    g = np.asarray(grad, dtype=float)
    ub = np.full_like(g, np.inf) if upper is None else np.asarray(upper, dtype=float)
    s = np.zeros_like(g)
    left = float(max(cap, 0.0))
    for i in np.argsort(-g):
        if left <= 0.0:
            break
        if not exact and g[i] <= 0.0:
            break
        take = min(left, float(ub[i]))
        s[i] = take
        left -= take
    return s


def fw_gap(grad: np.ndarray, h: np.ndarray, cap: float, *, exact: bool = False,
           upper: np.ndarray | None = None) -> float:
    """Frank-Wolfe gap max_s g.(s - h) >= 0. Zero means `h` is a KKT point of the heat set; for a
    concave objective it would also bound f* - f(h), but `optimise`'s objective is NOT concave
    (see `_redundancy`), so there it certifies stationarity only."""
    s = fw_vertex(grad, cap, exact=exact, upper=upper)
    return float(max(0.0, float(np.dot(grad, s - np.asarray(h, dtype=float)))))


def _redundancy(corr_abs: np.ndarray, h: np.ndarray) -> tuple[float, np.ndarray]:
    """Correlation-weighted overlap of the book, and its gradient.

    `h' |C| h - h' h` is the risk that is DUPLICATED: everything the book holds twice. Charging
    it is what makes the optimiser prefer the same expected growth from more independent sources,
    and it is the term that stops a heat budget being filled with five copies of one dollar bet.

    IT IS NOT CONCAVE, AND THE SOLVER NO LONGER PRETENDS IT IS (2026-10-06). |C| - I has a zero
    diagonal and a non-negative off-diagonal, so it is indefinite: for two identical streams the
    charge is 2*h1*h2, a saddle. The ascent used to start at the equal split, find a symmetric
    gradient, shrink its step to nothing and report `converged=True` at a point a feasible book
    beat on the solver's own objective. A PSD replacement was built and MEASURED before being
    discarded: any PSD form charges the diagonal through a book-wide eigenvalue shift, so adding
    one diversifier raised the charge on every held sleeve and the admission test that pins "a
    low-Sharpe diversifier beats a high-Sharpe copy" turned over. The charge is therefore kept
    as designed and the PROBLEM is treated as non-convex in `optimise`: several starts, the best
    feasible book kept, stationarity checked, and the certificate says local, never global.
    """
    off = corr_abs @ h - h
    return float(h @ off), 2.0 * off


def _objective(worlds: Worlds, h: np.ndarray, corr_abs: np.ndarray, cfg: WorldConfig,
               ) -> tuple[float, np.ndarray, np.ndarray]:
    """Robust score, its (super)gradient, and the per-world growth vector.

    The growth part (mean and lower-tail CVaR of per-world log growth) is concave; the redundancy
    charge is an indefinite quadratic (`_redundancy`), so the whole is not.

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


#: Common days at which the REALISED correlation of a pair carries half the weight against the
#: structured target. Sixty: three months of overlap before the measurement outranks the model.
CORR_BLEND_K = 60.0
#: The structural prior for pairs the factor model cannot see inside. Two sleeves running the
#: same mechanism on the same instrument take the same trades with different parameters; two
#: mechanisms on one instrument share its path. Neither is measurable from a fortnight of
#: returns, and both were being scored as independent.
SAME_SYMBOL_FAMILY_CORR = 0.80
SAME_SYMBOL_CORR = 0.35
#: THE THREE DIMENSIONS THE RETURNS CANNOT SHOW (Tier-1 B13), each a FLOOR at full similarity and
#: proportional below it -- the same shape as the same-instrument prior above, for the same
#: reason: a fortnight of returns cannot measure any of them, and scoring them as zero scores two
#: copies of one bet as two bets.
#: Shared input DATA: identical inputs is a stronger statement than the same instrument, because
#: it includes the same file, the same vintage and the same revision error.
SHARED_INPUT_CORR = 0.50
#: Same declared causal MECHANISM across instruments: one bet on the mechanism being true.
SAME_MECHANISM_CORR = 0.45
#: Trade-time overlap between two sleeves on ONE instrument, as a share of entry hours.
TRADE_TIME_CORR = 0.40
#: THE RELAXATION FLOOR, and the reason this change is two-sided. The same-instrument prior
#: assumes two sleeves take the same trades; disjoint entry hours are evidence that they do not.
#: The prior is scaled by the measured hour overlap but never below this, because two sleeves on
#: one instrument still share its path, its gaps and its regime even when they never trade
#: together. Raising breadth on measured evidence is what lets the same heat hold MORE
#: independent bets (the principal's standing order: never a smaller book).
TIME_DISJOINT_FLOOR = 0.25
#: Both sleeves must have this many measured entry hours before the relaxation is allowed to act;
#: below it the pair keeps the unrelaxed prior, because "no hours recorded" is not "no overlap".
MIN_HOURS_FOR_RELAX = 3


def _jaccard(a: Sequence[str] | Sequence[int], b: Sequence[str] | Sequence[int]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return float(len(sa & sb)) / float(len(sa | sb))


def _mechanism_sim(a: str, b: str) -> float:
    """Token Jaccard over the declared mechanism. Exact equality is 1.0; unrelated stories 0.0.
    Declared prose, tokenised -- never an embedding, because a similarity nobody can read cannot
    be argued with when it charges a sleeve."""
    ta = {t for t in re.split(r"[^a-z0-9]+", a.lower()) if len(t) > 3}
    tb = {t for t in re.split(r"[^a-z0-9]+", b.lower()) if len(t) > 3}
    if not ta or not tb:
        return 0.0
    return float(len(ta & tb)) / float(len(ta | tb))


def _structured_corr(ev: Sequence[SleeveEvidence]) -> tuple[np.ndarray, dict[str, int]]:
    """|corr| from the loadings, floored by the structural prior; zeros where nothing is known.

    B13 -- EFFECTIVE BREADTH, NOT RAW COUNT. Three dimensions of sameness join the factor model
    and the same-instrument prior: shared INPUT DATA, TRADE-TIME overlap and declared MECHANISM.
    Each raises the floor for pairs that are one bet wearing two names. The trade-time channel
    also RELAXES the same-instrument prior for pairs whose entry hours are disjoint -- measured
    evidence that they are not taking the same trade -- so this file can now both charge and
    credit independence, which is what a two-sided modifier means (GROWTH_GOVERNANCE Rule 1).
    """
    n = len(ev)
    t = np.zeros((n, n))
    loads = [np.asarray(getattr(e, "factor_load", ()), dtype=float) for e in ev]
    rv = np.array([max(0.0, float(getattr(e, "factor_resid_var", 0.0) or 0.0)) for e in ev])
    ok = [i for i in range(n) if loads[i].size]
    n_factor = 0
    if len(ok) > 1:
        k = max(loads[i].size for i in ok)
        m = np.zeros((len(ok), k))
        for row, i in enumerate(ok):
            m[row, : loads[i].size] = loads[i]
        g = m @ m.T
        d = np.diag(g) + rv[ok]
        den = np.sqrt(np.outer(d, d))
        with np.errstate(divide="ignore", invalid="ignore"):
            f = np.where(den > 0, np.abs(g) / den, 0.0)
        t[np.ix_(ok, ok)] = np.minimum(1.0, f)
        n_factor = len(ok)
    n_struct = 0
    n_input = n_mech = n_time = n_relaxed = 0
    syms = [str(e.symbol or "") for e in ev]
    fams = [str(e.family or "") for e in ev]
    ins = [tuple(getattr(e, "inputs", ()) or ()) for e in ev]
    hrs = [tuple(getattr(e, "trade_hours", ()) or ()) for e in ev]
    mechs = [str(getattr(e, "mechanism", "") or "") for e in ev]
    for i in range(n):
        for j in range(i + 1, n):
            floors: list[float] = []
            # SAME INSTRUMENT -- the prior that already existed, now scaled by measured overlap.
            if syms[i] and syms[i] == syms[j]:
                s = SAME_SYMBOL_FAMILY_CORR if fams[i] == fams[j] else SAME_SYMBOL_CORR
                overlap = _jaccard(hrs[i], hrs[j])
                if (len(hrs[i]) >= MIN_HOURS_FOR_RELAX and len(hrs[j]) >= MIN_HOURS_FOR_RELAX
                        and overlap < 1.0):
                    relaxed = max(TIME_DISJOINT_FLOOR, s * overlap)
                    if relaxed < s:
                        n_relaxed += 1
                    s = relaxed
                floors.append(s)
                n_struct += 1
            # SHARED INPUT DATA -- across instruments too: two sleeves reading one file are not
            # two independent draws on the world, whatever they trade.
            ji = _jaccard(ins[i], ins[j])
            if ji > 0.0:
                floors.append(SHARED_INPUT_CORR * ji)
                n_input += 1
            # SAME DECLARED MECHANISM -- one bet on that story being true.
            jm = _mechanism_sim(mechs[i], mechs[j])
            if jm > 0.0:
                floors.append(SAME_MECHANISM_CORR * jm)
                n_mech += 1
            # TRADE-TIME OVERLAP across instruments: same hour, same liquidity regime, same
            # news, and the same chance of being stopped by one move.
            if syms[i] != syms[j] and hrs[i] and hrs[j]:
                jh = _jaccard(hrs[i], hrs[j])
                if jh > 0.0:
                    floors.append(TRADE_TIME_CORR * jh)
                    n_time += 1
            if floors:
                s = max(floors)
                if s > t[i, j]:
                    t[i, j] = t[j, i] = s
    np.fill_diagonal(t, 1.0)
    return t, {"n_with_loadings": n_factor, "n_structural_pairs": n_struct,
               "n_shared_input_pairs": n_input, "n_same_mechanism_pairs": n_mech,
               "n_trade_time_pairs": n_time, "n_time_relaxed_pairs": n_relaxed}


def breadth_channels(ev: Sequence[SleeveEvidence]) -> dict[str, Any]:
    """The B13 census: which sameness channel each pair was scored on, and what the trade-time
    evidence CREDITED. Pure, report-only -- `_structured_corr` does the arithmetic; this names it
    so the allocation report can show the channels instead of one blended number."""
    _t, meta = _structured_corr(ev)
    declared = {"inputs": sum(1 for e in ev if getattr(e, "inputs", ())),
                "trade_hours": sum(1 for e in ev if getattr(e, "trade_hours", ())),
                "mechanism": sum(1 for e in ev if str(getattr(e, "mechanism", "") or ""))}
    n_pairs = len(ev) * (len(ev) - 1) // 2
    return {
        "n_sleeves": len(ev), "n_pairs": n_pairs, "declared": declared, **meta,
        "rule": ("shared input data, declared mechanism and trade-time overlap each FLOOR a "
                 "pair's |corr| in proportion to their Jaccard similarity; disjoint entry hours "
                 "RELAX the same-instrument prior toward TIME_DISJOINT_FLOOR, which raises "
                 "effective breadth and therefore the number of independent bets the same heat "
                 "can hold"),
        "unmeasured": ("a sleeve declaring none of the three is scored exactly as it was before "
                       "these channels existed -- absence is never charged as sameness"),
    }


def _corr_abs(ev: Sequence[SleeveEvidence]) -> np.ndarray:
    """Duplication between sleeves: realised POSITIVE correlation where measured (a hedge is
    charged nothing), factor-structured where not.

    THE REALISED NUMBER NEEDS COMMON DAYS AND A NEW SLEEVE HAS NONE. Measured 2026-09-16: the
    gateway reported `k_eff UNMEASURED: no sleeve pair has 20 overlapping trading days yet` on
    every pass, and here every such pair read as 0.0 -- independent -- so the redundancy charge
    that exists to stop five copies of one dollar bet was switched off for precisely the sleeves
    it was written for. Each pair is now the overlap-weighted blend of its realised |corr| and a
    structured target (`_structured_corr`: the factor model's implied |corr|, floored by the
    same-instrument prior). At 60 common days the two carry equal weight; a pair with a year in
    common is 86% measurement, a pair with a fortnight is 81% model, and a pair with no common
    day at all is the model alone -- which is a claim the sleeves' own loadings support, never a
    convenient zero.
    """
    n = len(ev)
    obs = min(int(e.daily_r.size) for e in ev)
    raw = np.stack([np.asarray(e.daily_r[-obs:], dtype=float) for e in ev], axis=1)
    fin = np.isfinite(raw)
    # Absent days are flat for a CO-MOVEMENT measure: correlation is a portfolio-level statistic
    # over the shared calendar, so the zero-fill here is the protocol's "flat only at portfolio
    # level, explicitly" -- not the sleeve-level zero-fill that defect #4 names.
    m = np.where(fin, raw, 0.0)
    sd = m.std(axis=0)
    live = sd > 0
    c = np.zeros((n, n))
    if live.sum() > 1:
        sub = np.corrcoef(m[:, live], rowvar=False)
        # POSITIVE CO-MOVEMENT ONLY (2026-09-25). This took |corr|, so a measured HEDGE -- two
        # sleeves that lose on different days -- was charged as duplicated risk exactly like
        # two copies of one bet, and the optimiser was paid to hold less of the pair that makes
        # the book's growth smoother. Duplication is a positive-correlation property; a
        # negative one is diversification the worlds already credit, never a cost to charge.
        c[np.ix_(live, live)] = np.clip(np.nan_to_num(sub, nan=0.0), 0.0, None)
    np.fill_diagonal(c, 1.0)
    target, _meta = _structured_corr(ev)
    if not np.any(target - np.eye(n)):
        return c
    f = fin.astype(float)
    overlap = f.T @ f                                              # common days per pair
    w = overlap / (overlap + CORR_BLEND_K)
    out: np.ndarray = w * c + (1.0 - w) * target
    np.fill_diagonal(out, 1.0)
    return out


def optimise(ev: Sequence[SleeveEvidence], *, hard_cap: float, target: float | None = None,
             cfg: WorldConfig | None = None, worlds: Worlds | None = None,
             warm_start: Mapping[str, float] | None = None,
             max_per_sleeve: float | Mapping[str, float] | None = None,
             iterations: int = 400, step: float = 0.02,
             deadline: float | None = None) -> AllocationResult:
    """Solve for per-sleeve heat maximising the robust posterior E[log W].

    `hard_cap` is the ceiling total heat may never cross. `target`, when given, is the
    FULL-UTILISATION mandate: total heat is pinned to exactly that and the optimiser answers only
    "on what", not "how much". Pass `target=None` to get what growth actually wants, which is the
    number that certifies whether a mandated target is safe (`heat_policy.certify`).

    `max_per_sleeve` bounds any single sleeve's heat -- a float applied to all, or a per-name
    mapping. It exists for the mandated case; see `project_capped_simplex` for what happens
    without it.

    `deadline` is a wall-clock instant (`time.time()` seconds) after which the ascent stops and
    returns the best FEASIBLE point it has -- every iterate is a projected, scored book, so a
    partial solve is a real book with a real score, flagged `budget_hit=True` and
    `converged=False` so the caller can warm-start the next attempt from it rather than treat
    it as the optimum. None means no wall-clock bound, which is what every caller had before.

    Projected gradient ascent with backtracking, run as a NON-CONVEX problem (2026-10-06). The
    growth part is concave but the redundancy charge is an indefinite quadratic (`_redundancy`),
    so a single ascent can stop on a saddle; until that day this docstring claimed concavity and
    the solver reported `converged=True` on one.

    WHAT IS CERTIFIED, AND WHAT IS NOT. The ascent runs from the equal split (or warm start),
    then from the midpoint toward the Frank-Wolfe vertex of the first solve (which breaks any
    symmetry the first start sat on), a seeded random point of the heat set, and -- with a warm
    start -- the equal split. The best feasible book across starts is returned (best-known
    feasible), `multistart_spread` publishes how far the starts disagreed, and `converged` means
    the returned book is a KKT point (Frank-Wolfe gap `optimality_gap` within `gap_tolerance`).
    That is a LOCAL certificate: `certificate` says so, and nothing here claims a global optimum.
    A step size shrinking to nothing is not convergence and is no longer reported as one.
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

    def _ascend(h0: np.ndarray, s0: float, gr0: np.ndarray, gw0: np.ndarray, n_it: int
                ) -> tuple[np.ndarray, float, np.ndarray, np.ndarray, int, bool]:
        hh, sc, gr, gw = h0, s0, gr0, gw0
        lr, done_, hit = step, 0, False
        for i in range(n_it):
            if deadline is not None and time.time() > deadline:
                hit = True
                break
            done_ = i + 1
            cand = project_capped_simplex(hh + lr * gr, cap, exact=exact, upper=ub)
            c_score, c_grad, c_g = _objective(w_pop, cand, corr_abs, cfg)
            if c_score > sc:
                moved = float(np.abs(cand - hh).sum())
                hh, sc, gr, gw = cand, c_score, c_grad, c_g
                lr *= 1.10
                if moved < 1e-7:
                    break
            else:
                lr *= 0.5
                # -inf cannot be improved on by comparison, so an exact solve that starts ruinous
                # would otherwise spin the full iteration budget doing nothing.
                if lr < 1e-9 or sc == -np.inf:
                    break
        return hh, sc, gr, gw, done_, hit

    h, score, grad, g_w, done, budget_hit = _ascend(h, score, grad, g_w, iterations)
    starts = [score]
    # MULTI-START. The objective is non-convex (`_redundancy`), so one ascent can stop on a saddle
    # -- measured on two identical streams, where the equal split is exactly that. The
    # Frank-Wolfe vertex breaks the symmetry, a seeded random start samples elsewhere, and the
    # equal split checks a warm start; the best feasible book wins and the spread is published.
    alt_starts: list[np.ndarray] = []
    if math.isfinite(score):
        alt_starts.append(fw_vertex(grad, cap, exact=exact, upper=ub))
    _rng = np.random.default_rng(int(cfg.seed) + 104729)
    alt_starts.append(project_capped_simplex(_rng.dirichlet(np.ones(n)) * cap, cap, exact=exact,
                                             upper=ub))
    if warm_start:
        alt_starts.append(project_capped_simplex(np.full(n, cap / n), cap, exact=exact, upper=ub))
    for h0 in alt_starts:
        if budget_hit or (deadline is not None and time.time() > deadline):
            budget_hit = True
            break
        h0 = project_capped_simplex(0.5 * (h0 + h), cap, exact=exact, upper=ub)
        s0, gr0, gw0 = _objective(w_pop, h0, corr_abs, cfg)
        if s0 == -np.inf:
            continue
        hb, sb, grb, gwb, d_b, hit_b = _ascend(h0, s0, gr0, gw0, max(1, iterations // 2))
        done += d_b
        budget_hit = budget_hit or hit_b
        starts.append(sb)
        if sb > score:
            h, score, grad, g_w = hb, sb, grb, gwb

    gap = fw_gap(grad, h, cap, exact=exact, upper=ub) if math.isfinite(score) else float("inf")
    #: The tolerance is ECONOMIC and RELATIVE (audit of PR #261): 1e-4 of the book's own robust
    #: E[log W], floored at 1e-10/day so a near-zero book is not certified on rounding.
    tol = max(1e-10, 1e-4 * abs(score)) if math.isfinite(score) else 0.0
    local_ok = bool(math.isfinite(gap) and gap <= tol and not budget_hit)
    fin_starts = [x for x in starts if math.isfinite(x)]
    spread = (max(fin_starts) - min(fin_starts)) if len(fin_starts) > 1 else 0.0

    # A GLOBAL BOUND, BESIDE THE LOCAL CERTIFICATE (audit of PR #261). The redundancy charge
    # h'(|C| - I)h is a sum of A_ij h_i h_j with A_ij >= 0 on 0 <= h <= u, and each product is
    # bounded BELOW by its McCormick envelope max(0, u_j h_i + u_i h_j - u_i u_j), which is
    # CONVEX. So the relaxation
    #     R(h) = growth(h) - lambda * sum_ij A_ij max(0, u_j h_i + u_i h_j - u_i u_j)
    # is CONCAVE and R >= f everywhere on the heat set: its Frank-Wolfe gap bounds its own
    # optimum, hence
    #     f* <= R(h_r) + FW_gap_R(h_r) =: upper_bound
    # and `global_gap = upper_bound - score` bounds how far the returned book is from the GLOBAL
    # optimum of the real non-convex problem. Tight where a sleeve's bound u is small; loose by
    # at most the charge the optimum pays. `converged` means THIS gap is within tolerance.
    upper_bound, global_gap = float("inf"), float("inf")
    if math.isfinite(score) and not budget_hit:
        from dataclasses import replace as _dc_replace
        cfg0 = _dc_replace(cfg, redundancy_lambda=0.0)
        u = np.minimum(np.where(np.isfinite(ub), ub, cap), cap)
        a_off = corr_abs - np.diag(np.diag(corr_abs))
        lam_r = float(cfg.redundancy_lambda)

        def _relaxed(hh: np.ndarray) -> tuple[float, np.ndarray]:
            g0, gr0, _gw0 = _objective(w_pop, hh, corr_abs, cfg0)
            if not math.isfinite(g0) or lam_r == 0.0:
                return g0, gr0
            env = u[None, :] * hh[:, None] + u[:, None] * hh[None, :] - np.outer(u, u)
            act = (env > 0.0) & (a_off > 0.0)
            m_val = float((a_off * np.where(act, env, 0.0)).sum())
            # d/dh_k of sum_ij A_ij (u_j h_i + u_i h_j - u_i u_j) over active pairs.
            w_act = a_off * act
            m_grad = (w_act * u[None, :]).sum(axis=1) + (w_act * u[:, None]).sum(axis=0)
            return g0 - lam_r * m_val, gr0 - lam_r * m_grad

        hr = h.copy()
        r_score, r_grad = _relaxed(hr)
        lr0 = step
        for _ in range(max(1, iterations // 2)):
            if deadline is not None and time.time() > deadline:
                break
            cand = project_capped_simplex(hr + lr0 * r_grad, cap, exact=exact, upper=ub)
            c_s, c_g = _relaxed(cand)
            if c_s > r_score:
                moved = float(np.abs(cand - hr).sum())
                hr, r_score, r_grad = cand, c_s, c_g
                lr0 *= 1.10
                if moved < 1e-7:
                    break
            else:
                lr0 *= 0.5
                if lr0 < 1e-9:
                    break
        if math.isfinite(r_score):
            upper_bound = r_score + fw_gap(r_grad, hr, cap, exact=exact, upper=ub)
            global_gap = max(0.0, upper_bound - score)
    # CONVERGED MEANS GLOBAL (audit ruling): the returned book is within `tol` of the global
    # optimum by the bound above. A KKT point the bound cannot certify is reported LOCAL --
    # `converged=False`, `certificate="local_kkt_multistart"` -- and is still the best feasible
    # book found, which the desk keeps trading; an honest gap is not a reason to stand down.
    converged = bool(local_ok and global_gap <= tol)

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
        iterations=done, converged=converged, note=w_pop.note, budget_hit=budget_hit,
        optimality_gap=float(gap), gap_tolerance=float(tol), multistart_spread=float(spread),
        n_starts=len(starts),
        certificate=("global_bound" if converged else
                     "local_kkt_multistart" if local_ok else "best_known_feasible"),
        upper_bound=float(upper_bound), global_gap=float(global_gap),
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
