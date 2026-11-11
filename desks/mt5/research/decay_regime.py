"""REGIME-AWARE DECAY -- is a losing sleeve DEAD, or in a BAD STRETCH? (principal 2026-10-29:
"sometimes false decay can be observed cuz of regime or js bad days and zeroed stays on but not
fr gold asia until we get replacements"; Hourly pass P82 item 55).

decay_monitor's ladder judges a sleeve on its trailing mean and t. It cannot tell two very
different losers apart:

  * an edge that BROKE -- the mechanism stopped working at some trade and every trade since
    has come from a worse distribution. Waiting for t <= -2.5 at n >= 20 costs the trades
    between the break and the verdict;
  * an edge in a BAD STRETCH -- a short run of losses from a sleeve that alternates between a
    good and a bad state and has always come back. A t-rule retirement here sends the sleeve
    through a fresh forward window and forgoes its recovery.

Two detectors, each a textbook model fitted to the sleeve's own R sequence (pure Python, no
bindings: this runs inside the daily chain on either box):

  `bocpd`  Bayesian online change-point detection (Adams & MacKay 2007), a Normal-Gamma
           conjugate model with a constant hazard. Answers: did the R distribution change
           recently, and what is the current run's mean (P(mean < 0))?
  `ms2`    a two-state Markov-switching model of the win rate (Hamilton 1989 with Bernoulli
           emissions -- trade R is near-binary), fitted by EM. Answers:
           is the sleeve in its bad state now, how long does a bad state last (1/(1 - p_bb)),
           and is its long-run, stationary-weighted mean positive?

`classify` combines them into one class per sleeve and `adjust` moves the ladder's verdict ONE
step, TWO-SIDED (GROWTH_GOVERNANCE Rule 1 and Rule 2):

  STRUCTURAL_BREAK       a recent break, the current run is negative (P >= BREAK_P_NEG) and the
                         run before it was positive  -> HEALTHY becomes FADE (earlier)
  PERSISTENT_BAD_REGIME  in the bad state, bad states last, or the long-run mean is not
                         positive                    -> HEALTHY becomes FADE
  TRANSIENT_REGIME       in the bad state, but bad states are short and the long-run mean is
                         positive, with NO break     -> a t-rule RETIRE becomes FADE (half risk,
                                                        not zero: the stretch is priced, the
                                                        recovery is kept)
  STABLE / UNMEASURED    no change

WHAT IS NEVER MOVED. The -25R drawdown rail (survival) is never softened. The pooled verdicts
are untouched. Zeroing stays on everywhere -- this only stops a BAD STRETCH being read as a dead
edge. `EXEMPT` sleeves (gold_asia, principal-pinned until it has a certified replacement) are
reported and never adjusted in either direction.

CALIBRATED, NOT ASSERTED. desks/mt5/tests/test_decay_regime.py simulates i.i.d. positive-edge
sleeves (break false-positive rate), sleeves that break (detection rate) and two-state sleeves
(transient classification), so a threshold change that loosens either side reddens.
"""
from __future__ import annotations

import math
from typing import Any

#: Principal-pinned (2026-10-29): gold_asia is never zeroed or adjusted by decay until a
#: certified replacement or new promotion exists for it. Matched on the sleeve name and on
#: gateway-window keys that carry it (`XAUUSD.asia`, `gold_asia`).
EXEMPT: frozenset[str] = frozenset({"gold_asia", "XAUUSD.asia"})

#: Fewer trades than this and neither model is fitted: UNMEASURED with its n.
MIN_N = 12
#: BOCPD prior: expected run length between changes, in trades (hazard = 1 / HAZARD_RUN).
HAZARD_RUN = 60.0
#: Normal-Gamma prior on a run's (mean, precision), in R units: centred on zero, weak.
PRIOR_MU, PRIOR_KAPPA, PRIOR_ALPHA, PRIOR_BETA = 0.0, 1.0, 1.0, 1.0
#: "Recent" break: the posterior mass on a current run shorter than this many trades.
RECENT_K = 12
#: A break is called when that mass is at least BREAK_P_RECENT, the current run's mean is
#: negative with probability at least BREAK_P_NEG, and the run before it averaged above zero.
BREAK_P_RECENT = 0.5
BREAK_P_NEG = 0.9
#: The current run must hold at least this many trades before its mean is read.
BREAK_MIN_RUN = 4
#: Markov switching: EM iterations, the Beta prior on each state's win rate (keeps a state off
#: 0 and 1), the persistence BOTH states need before the fit is a regime at all (an i.i.d.
#: sleeve fits switching probabilities near its win rate, i.e. not sticky), and the bad-state
#: call.
MS_ITERS = 80
MS_BETA_PRIOR = 2.0
MS_MIN_STAY = 0.7
MS_P_BAD = 0.7
#: A bad state lasting at most this many trades on average is a STRETCH, not a regime.
TRANSIENT_MAX_TRADES = 6.0


def _is_exempt(name: str) -> bool:
    n = str(name or "")
    return n in EXEMPT or n.lower() in {e.lower() for e in EXEMPT}


# --------------------------------------------------------------------------- BOCPD
def _student_logpdf(x: float, mu: float, kappa: float, alpha: float, beta: float) -> float:
    """Log predictive density of x under a Normal-Gamma posterior (a Student-t)."""
    nu = 2.0 * alpha
    scale2 = beta * (kappa + 1.0) / (alpha * kappa)
    z = (x - mu) ** 2 / (nu * scale2)
    return (math.lgamma((nu + 1) / 2) - math.lgamma(nu / 2)
            - 0.5 * math.log(nu * math.pi * scale2) - (nu + 1) / 2 * math.log1p(z))


def _t_cdf_neg(mu: float, kappa: float, alpha: float, beta: float) -> float:
    """P(mean < 0) under the Normal-Gamma posterior: the marginal of the mean is a Student-t
    with 2*alpha degrees of freedom, location mu and scale^2 beta/(alpha*kappa)."""
    nu = 2.0 * alpha
    s = math.sqrt(beta / (alpha * kappa))
    t = (0.0 - mu) / s
    # Student-t CDF via the regularized incomplete beta function.
    x = nu / (nu + t * t)
    ib = _betainc(nu / 2, 0.5, x)
    return 1.0 - 0.5 * ib if t > 0 else 0.5 * ib


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b) by Lentz's continued fraction."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log1p(-x))
    if x > (a + 1) / (a + b + 2):
        return 1.0 - _betainc(b, a, 1.0 - x)
    tiny = 1e-300
    f, c, d = 1.0, 1.0, 0.0
    for i in range(400):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        d = tiny if abs(d) < tiny else d
        c = 1.0 + num / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        f *= c * d
        if abs(1.0 - c * d) < 1e-12:
            break
    return front * (f - 1.0) / a


def bocpd(rs: list[float], hazard_run: float = HAZARD_RUN) -> dict[str, Any]:
    """Run-length posterior after the last trade, with the current run's mean and the mean of
    the run before it. Exact (no pruning): a sleeve's trailing window is at most a few dozen
    trades."""
    h = 1.0 / hazard_run
    log_h, log_1h = math.log(h), math.log1p(-h)
    # per run length r: (log weight, mu, kappa, alpha, beta, sum of x in the run)
    runs: list[tuple[float, float, float, float, float]] = [
        (0.0, PRIOR_MU, PRIOR_KAPPA, PRIOR_ALPHA, PRIOR_BETA)]
    for x in rs:
        preds = [lw + _student_logpdf(x, mu, k, a, b) for lw, mu, k, a, b in runs]
        cp = _logsumexp([p + log_h for p in preds])
        grown = [p + log_1h for p in preds]
        new = [(cp, PRIOR_MU, PRIOR_KAPPA, PRIOR_ALPHA, PRIOR_BETA)]
        for (lw, mu, k, a, b), g in zip(runs, grown, strict=True):
            k2 = k + 1.0
            mu2 = (k * mu + x) / k2
            a2 = a + 0.5
            b2 = b + k * (x - mu) ** 2 / (2.0 * k2)
            new.append((g, mu2, k2, a2, b2))
        z = _logsumexp([w for w, *_ in new])
        runs = [(w - z, mu, k, a, b) for w, mu, k, a, b in new]
    post = [math.exp(w) for w, *_ in runs]          # post[r] = P(current run length = r)
    n = len(rs)
    map_r = max(range(len(post)), key=post.__getitem__)
    recent = sum(post[r] for r in range(min(RECENT_K, len(post))))
    # The current run's mean and P(mean < 0) at the MAP run length; the run before it is the
    # plain mean of the trades preceding that run.
    _, mu, k, a, b = runs[map_r]
    p_neg = _t_cdf_neg(mu, k, a, b) if map_r > 0 else 0.5
    before = rs[: n - map_r]
    return {"n": n, "map_run": map_r, "p_recent_break": round(recent, 4),
            "run_mean_r": round(sum(rs[n - map_r:]) / map_r, 4) if map_r else None,
            "run_p_neg": round(p_neg, 4),
            "before_mean_r": round(sum(before) / len(before), 4) if before else None,
            "hazard_run": hazard_run}


def _logsumexp(xs: list[float]) -> float:
    m = max(xs)
    return m + math.log(sum(math.exp(x - m) for x in xs))


# --------------------------------------------------------------------------- Markov switching
def ms2(rs: list[float], iters: int = MS_ITERS) -> dict[str, Any]:
    """Two-state Markov-switching model of the sleeve's WIN RATE, fitted by EM (Baum-Welch,
    scaled, MAP under a Beta(MS_BETA_PRIOR, MS_BETA_PRIOR) prior on each state's win rate).

    WHY WINS AND NOT A GAUSSIAN ON R. Trade R is close to binary (a stop or a target). A
    Gaussian switching model on it explains every loss by a zero-variance "loss state" and every
    losing trade reads as a regime -- measured on simulated i.i.d. sleeves before this was
    written. A regime is a stretch of a DIFFERENT WIN RATE that PERSISTS, so that is the model.
    State 0 is the lower-win-rate ("bad") state; each state's mean R is the posterior-weighted
    mean of the trades it holds."""
    n = len(rs)
    w = [1.0 if r > 0 else 0.0 for r in rs]
    base = sum(w) / n
    q = [max(base * 0.5, 0.02), min(base + (1 - base) * 0.5, 0.98)]
    P = [[0.8, 0.2], [0.2, 0.8]]
    pi = [0.5, 0.5]
    alpha: list[list[float]] = []
    gamma: list[list[float]] = []
    loglik = -math.inf
    k0 = MS_BETA_PRIOR - 1.0
    for _ in range(iters):
        def emit(t: int) -> list[float]:
            return [q[s] if w[t] else 1.0 - q[s] for s in (0, 1)]
        alpha, scale = [], []
        for t in range(n):
            e = emit(t)
            if t == 0:
                a = [pi[s] * e[s] for s in (0, 1)]
            else:
                pr = alpha[-1]
                a = [e[s] * (pr[0] * P[0][s] + pr[1] * P[1][s]) for s in (0, 1)]
            c = sum(a)
            alpha.append([v / c for v in a])
            scale.append(c)
        beta = [[1.0, 1.0] for _ in range(n)]
        for t in range(n - 2, -1, -1):
            e = emit(t + 1)
            beta[t] = [sum(P[i][j] * e[j] * beta[t + 1][j] for j in (0, 1)) / scale[t + 1]
                       for i in (0, 1)]
        gamma = []
        for t in range(n):
            g = [alpha[t][s] * beta[t][s] for s in (0, 1)]
            z = sum(g)
            gamma.append([v / z for v in g])
        xi = [[0.0, 0.0], [0.0, 0.0]]
        for t in range(n - 1):
            e = emit(t + 1)
            m = [[alpha[t][i] * P[i][j] * e[j] * beta[t + 1][j] for j in (0, 1)] for i in (0, 1)]
            z = sum(sum(row) for row in m)
            for i in (0, 1):
                for j in (0, 1):
                    xi[i][j] += m[i][j] / z
        pi = gamma[0][:]
        for i in (0, 1):
            row = sum(xi[i])
            if row > 0:
                P[i] = [min(max(xi[i][j] / row, 1e-4), 1 - 1e-4) for j in (0, 1)]
                tot = sum(P[i])
                P[i] = [v / tot for v in P[i]]
        for s in (0, 1):
            ws = sum(g[s] for g in gamma)
            q[s] = (sum(g[s] * x for g, x in zip(gamma, w, strict=True)) + k0) / (ws + 2 * k0)
        new_ll = sum(math.log(c) for c in scale)
        if abs(new_ll - loglik) < 1e-8:
            loglik = new_ll
            break
        loglik = new_ll
    if q[0] > q[1]:                                    # state 0 is always the bad state
        q = [q[1], q[0]]
        P = [[P[1][1], P[1][0]], [P[0][1], P[0][0]]]
        alpha = [[a[1], a[0]] for a in alpha]
        gamma = [[g[1], g[0]] for g in gamma]

    def _mean(s: int) -> float:
        ws = sum(g[s] for g in gamma)
        return sum(g[s] * r for g, r in zip(gamma, rs, strict=True)) / ws if ws > 1e-9 else 0.0

    mu = [_mean(0), _mean(1)]
    p_bb, p_gg = P[0][0], P[1][1]
    denom = (1 - p_bb) + (1 - p_gg)
    st_bad = (1 - p_gg) / denom if denom > 0 else 0.5
    return {"win_bad": round(q[0], 4), "win_good": round(q[1], 4),
            "mean_bad_r": round(mu[0], 4), "mean_good_r": round(mu[1], 4),
            "p_bad_bad": round(p_bb, 4), "p_good_good": round(p_gg, 4),
            "sticky": p_bb >= MS_MIN_STAY and p_gg >= MS_MIN_STAY,
            "bad_duration_trades": round(1.0 / max(1.0 - p_bb, 1e-9), 2),
            "stationary_bad": round(st_bad, 4),
            "longrun_mean_r": round(st_bad * mu[0] + (1 - st_bad) * mu[1], 4),
            "p_bad_now": round(alpha[-1][0], 4) if alpha else None,
            "loglik": round(loglik, 3)}


# --------------------------------------------------------------------------- classify / adjust
def classify(rs: list[float]) -> dict[str, Any]:
    """One class for a sleeve's trailing R series, with both models' evidence."""
    rs = [float(r) for r in rs if r is not None and math.isfinite(float(r))]
    if len(rs) < MIN_N:
        return {"class": "UNMEASURED", "n": len(rs),
                "why": f"{len(rs)} trade(s) < {MIN_N}: neither model is fitted"}
    cp = bocpd(rs)
    ms = ms2(rs)
    out: dict[str, Any] = {"n": len(rs), "bocpd": cp, "ms": ms}
    broke = (cp["p_recent_break"] >= BREAK_P_RECENT and cp["map_run"] >= BREAK_MIN_RUN
             and cp["map_run"] < len(rs) and cp["run_p_neg"] >= BREAK_P_NEG
             and (cp["before_mean_r"] or 0.0) > 0.0)
    if broke:
        out.update({"class": "STRUCTURAL_BREAK",
                    "why": (f"break {cp['map_run']} trade(s) ago (P(run<{RECENT_K})="
                            f"{cp['p_recent_break']}); run mean {cp['run_mean_r']}R, "
                            f"P(mean<0)={cp['run_p_neg']}; before it {cp['before_mean_r']}R")})
        return out
    bad_now = (ms["sticky"] and (ms["p_bad_now"] or 0.0) >= MS_P_BAD
               and ms["mean_bad_r"] < 0.0)
    if bad_now and ms["mean_good_r"] > 0.0 and ms["bad_duration_trades"] <= TRANSIENT_MAX_TRADES \
            and ms["longrun_mean_r"] > 0.0:
        out.update({"class": "TRANSIENT_REGIME",
                    "why": (f"bad state now (P={ms['p_bad_now']}), but bad states last "
                            f"{ms['bad_duration_trades']} trade(s) on average and the long-run "
                            f"mean is {ms['longrun_mean_r']}R; no change-point")})
    elif bad_now:
        out.update({"class": "PERSISTENT_BAD_REGIME",
                    "why": (f"bad state now (P={ms['p_bad_now']}, mean {ms['mean_bad_r']}R), "
                            f"lasting {ms['bad_duration_trades']} trade(s) on average; long-run "
                            f"mean {ms['longrun_mean_r']}R")})
    else:
        out.update({"class": "STABLE", "why": (f"no recent break (P={cp['p_recent_break']}) "
                                               f"and not in a bad state "
                                               f"(P={ms['p_bad_now']})")})
    return out


def adjust(name: str, verdict: str, why: str, s: dict[str, Any], rc: dict[str, Any],
           dd_hard_r: float = -25.0) -> tuple[str, str, str | None]:
    """(verdict, why, the step taken or None). One step, two-sided; see the module docstring.
    `dd_hard_r` is the ladder's survival rail; decay_monitor passes its own DD_HARD_R so the
    two can never drift apart."""
    if _is_exempt(name):
        return verdict, why, None
    cls = rc.get("class")
    dd_rail = float(s.get("max_dd_r") or 0.0) <= dd_hard_r
    if cls == "TRANSIENT_REGIME" and verdict == "RETIRE" and not dd_rail:
        return "FADE", (f"regime-aware: {rc['why']} -- the t-rule RETIRE ({why}) is a bad "
                        f"stretch, not a dead edge; half risk, not zero"), "RETIRE->FADE"
    if cls in ("STRUCTURAL_BREAK", "PERSISTENT_BAD_REGIME") and verdict == "HEALTHY":
        return "FADE", (f"regime-aware: {cls.lower()}: {rc['why']}; half risk until the record "
                        f"turns (the ladder alone: {why})"), "HEALTHY->FADE"
    return verdict, why, None


# --------------------------------------------------------------------------- what a step was worth
def step_value(step: str, r_after: list[float], fade_factor: float = 0.5) -> dict[str, Any]:
    """The realised value of one step, in R at the sleeve's full risk, from the trades it closed
    AFTER the step (GROWTH_GOVERNANCE Rules 1 and 2: a risk modifier proves itself or is billed).

    RETIRE->FADE kept `fade_factor` of the risk the ladder would have zeroed: worth
    fade_factor * sum(R after) (positive = growth kept, negative = loss taken).
    HEALTHY->FADE removed (1 - fade_factor) of the risk: worth -(1 - fade_factor) * sum(R after)
    (positive = loss avoided, negative = growth forgone). Fewer than one trade after: UNMEASURED.
    """
    if not r_after:
        return {"value_r": None, "n_after": 0, "status": "UNMEASURED"}
    tot = sum(r_after)
    if step == "RETIRE->FADE":
        v = fade_factor * tot
    elif step == "HEALTHY->FADE":
        v = -(1.0 - fade_factor) * tot
    else:
        return {"value_r": None, "n_after": len(r_after), "status": "UNKNOWN_STEP"}
    return {"value_r": round(v, 4), "n_after": len(r_after), "status": "MEASURED"}
