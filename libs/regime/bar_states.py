"""MARKET STATES FITTED ON BARS, NOT ON TRADES.

WHY THIS FILE EXISTS. The desk's regime router tried to fit a regime model per sleeve, out of
that sleeve's own trades. Measured on the box 2026-09-24: of 258 sleeves, 208 had no trades at
all, 50 published and ZERO were scored -- 34 were short of the router's 24-trade fold minimum and
16 had no state feature that varied over their trades. No amount of waiting fixes that, because
the blocker is the architecture: a sleeve that has traded five times cannot identify a regime
model, and most sleeves will never trade enough.

A hidden Markov model describes the MARKET, not the sleeve. Unobserved states drive observable
data; the states are fitted on price history by Baum-Welch; the regime then decides which signals
run. That is a property of the tape, so it is estimable from 248 instruments x seven timeframes
whether or not any sleeve has ever traded -- which is what removes both blockers at once.

THREE RULES THIS MODULE KEEPS.

1. CAUSAL LABELS ONLY. `GaussianHMM.predict` is Viterbi and has a BACKWARD pass, so every
   historical label it assigns uses observations from after the bar it describes (desk lesson
   L0307: 27 of 1,200 days carried a label the desk could not have held, concentrated at
   transitions -- exactly where a state-conditional number does the most work). This module
   never calls it. Every label here is the argmax of the forward filter P(state_t | x_1..t).

2. PARAMETERS ARE FITTED STRICTLY BEFORE THE WINDOW THEY LABEL. A state path whose emission
   means were fitted on the evaluation window is not out of sample, however causal the filter
   that reads them. `fit_states` takes `train_end_ns` and fits on bars before it only.

3. STATE NAMES ARE COMPARABLE ACROSS SYMBOLS. EM labels states in whatever order its start
   lands, so state 0 for EURUSD and state 0 for XAUUSD mean nothing to each other and cannot be
   pooled. States are re-ordered by their own realised volatility -- the convention
   `regime_hierarchy` already uses -- so `quiet` is the quiet one everywhere.

HOW MANY STATES: BY EVIDENCE, NOT BY TASTE. `choose_k` fits each candidate k on the first
`TRAIN_FRAC` of the pre-window bars and scores the ONE-STEP-AHEAD PREDICTIVE LOG-DENSITY
    p(x_t | x_1..t-1) = sum_j P(s_t = j | x_1..t-1) N(x_t | mu_j, var_j)
on the held-out remainder. That is a proper score for a sequence model and it is the same
quantity `feature_admission` already uses to decide whether a feature earns its place. A larger
k always fits better in sample and is penalised here only if it fails to predict, which is the
only penalty worth applying.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from libs.regime.hmm import GaussianHMM

#: Candidate state counts. Two (trending/reverting) is the classic; volatility often wants a
#: third; four and five are offered so the evidence can ask for them rather than being told no.
K_GRID: tuple[int, ...] = (2, 3, 4, 5)
#: Fraction of the pre-window bars used to FIT each candidate k; the rest scores it.
TRAIN_FRAC = 0.8
#: Bars a symbol must carry before its own fit is admitted at all.
MIN_TRAIN_BARS = 300
#: EM iterations. The desk's `GaussianHMM` default is 60; k-selection runs many fits and uses
#: fewer, which is a speed choice and is declared rather than hidden.
SELECT_ITERS = 25
FIT_ITERS = 60
#: Most recent bars used to FIT, when more are available. `GaussianHMM._forward_backward` is a
#: Python loop over bars, so cost is linear in the tape and an unbounded fit on a 6,000-bar H1
#: tape, repeated over the k-grid and the book, does not fit in an hourly leg. This is a COMPUTE
#: bound and nothing else: 2,500 H1 bars is over 100 trading days, which identifies a handful of
#: volatility states many times over, and the bound is declared here rather than hidden in a
#: caller. Raise it if a leg has the budget; never size it off a claim, measure the leg.
MAX_TRAIN_BARS = 2500

#: Volatility-ordered names, so a label means the same thing at every k and every symbol.
STATE_NAMES: dict[int, tuple[str, ...]] = {
    1: ("single",),
    2: ("quiet", "stress"),
    3: ("quiet", "normal", "stress"),
    4: ("quiet", "normal", "active", "stress"),
    5: ("quiet", "calm", "normal", "active", "stress"),
}

UNMEASURED = "UNMEASURED"


@dataclass(frozen=True)
class BarStates:
    """One symbol's causal state path, with the evidence that chose its state count."""

    symbol: str
    timeframe: str
    k: int
    #: Bar times in UTC nanoseconds, ascending. Aligned with `labels` and `posterior`.
    times_ns: np.ndarray
    #: Causal argmax of the forward filter, re-ordered so 0 is the quietest state.
    labels: np.ndarray
    #: (T, k) forward-filtered P(state_t | x_1..t), re-ordered to match `labels`.
    posterior: np.ndarray
    #: (k, k) transition matrix, rows re-ordered to match `labels`.
    transmat: np.ndarray
    names: tuple[str, ...]
    #: Bars used to FIT. Everything at or after this index was labelled, never fitted on.
    n_train: int
    #: Mean held-out one-step predictive log-density, nats/bar, for the chosen k.
    heldout_logdens: float
    #: k -> its held-out score, so the choice can be checked rather than believed.
    k_scores: dict[int, float]

    def index_at(self, ns: int) -> int:
        """Index of the last bar at or before `ns`; -1 when `ns` precedes the tape."""
        return int(np.searchsorted(self.times_ns, np.int64(ns), "right")) - 1

    def label_at(self, ns: int) -> str | None:
        """The state NAME in force at `ns`, or None when the tape does not reach back."""
        i = self.index_at(ns)
        if i < 0:
            return None
        return self.names[int(self.labels[i])]

    def probs_at(self, ns: int) -> np.ndarray | None:
        """P(state | data up to `ns`) -- the probabilities a proportionate act needs."""
        i = self.index_at(ns)
        if i < 0:
            return None
        return np.asarray(self.posterior[i], dtype="float64")

    def is_out_of_sample(self, ns: int) -> bool:
        """True when `ns` falls after every bar the emission parameters were fitted on."""
        return self.index_at(ns) >= self.n_train


def _lse0(a: np.ndarray) -> np.ndarray:
    """logsumexp along axis 0, without scipy's per-call dispatch overhead.

    The recursion below runs once per bar, and on a few-thousand-bar tape `scipy.special.logsumexp`
    spends more time being called than computing. The arrays here are (k,) and (k, k); the
    max-shift is the same numerical trick scipy uses.
    """
    m = a.max(axis=0)
    return np.asarray(m + np.log(np.exp(a - m).sum(axis=0)), dtype="float64")


def predictive_log_density(hmm: GaussianHMM, x: np.ndarray, start: int) -> float:
    """Mean one-step-ahead predictive log-density over ``x[start:]``, nats per bar.

    The quantity is p(x_t | x_1..t-1), marginalising the state over the PREDICTED distribution
    A' alpha_{t-1} -- never over the filtered one, which would have already seen x_t. A single
    forward pass produces both the prediction and the update, so scoring costs one pass.
    """
    x = np.asarray(x, dtype="float64")
    if x.ndim == 1:
        x = x[:, None]
    n = x.shape[0]
    if n <= start or start < 1:
        return float("nan")
    le = hmm._log_emission(x)
    lt = np.log(hmm.transmat + 1e-300)
    la = np.log(hmm.startprob + 1e-300) + le[0]
    total, count = 0.0, 0
    for t in range(1, n):
        step = _lse0(la[:, None] + lt)
        if t >= start:
            pred = step - _lse0(step)
            total += float(_lse0(pred + le[t]))
            count += 1
        la = le[t] + step
    return total / count if count else float("nan")


def choose_k(x: np.ndarray, *, grid: tuple[int, ...] = K_GRID, seed: int = 0,
             train_frac: float = TRAIN_FRAC) -> tuple[int, dict[int, float]]:
    """Pick the state count by held-out predictive log-density. Returns (k, scores by k).

    `x` must contain ONLY bars the caller is allowed to fit on. The split inside is a second,
    inner split of that training material; nothing here ever sees the window to be labelled.
    """
    x = np.asarray(x, dtype="float64")
    inner = int(x.shape[0] * train_frac)
    scores: dict[int, float] = {}
    if inner < MIN_TRAIN_BARS or inner >= x.shape[0]:
        return (grid[0] if grid else 2), scores
    for k in grid:
        if inner < 10 * k:
            continue
        try:
            hmm = GaussianHMM(n_states=k, seed=seed, n_iter=SELECT_ITERS).fit(x[:inner])
            score = predictive_log_density(hmm, x, inner)
        except (ValueError, np.linalg.LinAlgError, FloatingPointError):
            continue
        if np.isfinite(score):
            scores[k] = float(score)
    if not scores:
        return (grid[0] if grid else 2), scores
    best = max(scores, key=lambda kk: scores[kk])
    return int(best), scores


def _vol_order(labels: np.ndarray, x: np.ndarray, k: int) -> np.ndarray:
    """Rank each state by its own mean realised volatility (feature column 1, per
    `libs.regime.features`). Returns `remap` with remap[old] = new, quietest first."""
    vol = np.full(k, np.inf)
    for j in range(k):
        m = labels == j
        if m.any():
            v = float(np.nanmean(x[m, 1])) if x.shape[1] > 1 else float(np.nanmean(x[m, 0]))
            if np.isfinite(v):
                vol[j] = v
    remap = np.empty(k, dtype="int64")
    for rank, j in enumerate(np.argsort(vol, kind="stable")):
        remap[int(j)] = rank
    return remap


def fit_states(times_ns: np.ndarray, x: np.ndarray, *, symbol: str, timeframe: str = "H1",
               train_end_ns: int | None = None, k: int | None = None, seed: int = 0,
               grid: tuple[int, ...] = K_GRID,
               max_train_bars: int = MAX_TRAIN_BARS) -> BarStates | None:
    """Fit the state model on bars before `train_end_ns` and label the WHOLE tape causally.

    Returns None when the tape cannot support a fit; that is UNMEASURED, and the caller must
    report it as a reason rather than substituting a state.
    """
    times_ns = np.asarray(times_ns, dtype="int64")
    x = np.asarray(x, dtype="float64")
    if x.ndim == 1:
        x = x[:, None]
    if times_ns.shape[0] != x.shape[0]:
        raise ValueError(f"{times_ns.shape[0]} bar times for {x.shape[0]} feature rows")
    ok = np.isfinite(x).all(axis=1)
    times_ns, x = times_ns[ok], x[ok]
    n = x.shape[0]
    if n < MIN_TRAIN_BARS + 10:
        return None
    n_train = n if train_end_ns is None else int(np.searchsorted(times_ns, np.int64(train_end_ns)))
    n_train = max(min(n_train, n), 0)
    if n_train < MIN_TRAIN_BARS:
        return None

    # The FIT window is the most recent `max_train_bars` of the training material; the LABELLED
    # window is still the whole tape, and `n_train` still marks where out-of-sample begins.
    fit_lo = max(0, n_train - int(max_train_bars)) if max_train_bars else 0
    xtr = x[fit_lo:n_train]

    scores: dict[int, float] = {}
    if k is None:
        k, scores = choose_k(xtr, grid=grid, seed=seed)
    k = int(max(1, min(k, 5)))
    try:
        hmm = GaussianHMM(n_states=k, seed=seed, n_iter=FIT_ITERS).fit(xtr)
        post = hmm.filter_posterior(x)          # CAUSAL. Never `predict` -- see L0307.
    except (ValueError, np.linalg.LinAlgError, FloatingPointError):
        return None
    labels = post.argmax(axis=1)

    remap = _vol_order(labels[fit_lo:n_train], xtr, k)
    order = np.argsort(remap, kind="stable")    # new index -> old index
    post = post[:, order]
    labels = remap[labels]
    transmat = np.asarray(hmm.transmat, dtype="float64")[np.ix_(order, order)]

    inner = int(xtr.shape[0] * TRAIN_FRAC)
    heldout = scores.get(k)
    if heldout is None and inner >= MIN_TRAIN_BARS and inner < xtr.shape[0]:
        heldout = predictive_log_density(hmm, xtr, inner)

    return BarStates(
        symbol=symbol, timeframe=timeframe, k=k, times_ns=times_ns, labels=labels,
        posterior=np.asarray(post, dtype="float64"), transmat=transmat,
        names=STATE_NAMES.get(k, tuple(f"s{i}" for i in range(k))),
        n_train=n_train,
        heldout_logdens=float(heldout) if heldout is not None and np.isfinite(heldout)
        else float("nan"),
        k_scores={int(a): float(b) for a, b in scores.items()},
    )


def run_length_path(states: BarStates, *, since_ns: int | None = None) -> list[dict[str, object]]:
    """The state path as CHANGES, not as one row per bar -- a regime that persists is one row.

    This is what makes the path publishable: a 6,000-bar tape in three states is a few hundred
    runs, not 6,000 rows, and a reader can still answer "what state was in force at t".
    """
    out: list[dict[str, object]] = []
    lab = states.labels
    t = states.times_ns
    if lab.size == 0:
        return out
    start = 0 if since_ns is None else max(states.index_at(since_ns), 0)
    prev = None
    for i in range(start, lab.size):
        cur = int(lab[i])
        if cur != prev:
            out.append({"at_ns": int(t[i]), "state": cur, "name": states.names[cur],
                        "p": round(float(states.posterior[i, cur]), 4),
                        "out_of_sample": bool(i >= states.n_train)})
            prev = cur
    return out
