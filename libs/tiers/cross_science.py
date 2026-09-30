"""MECHANISMS FROM OTHER SCIENCES, AND NON-LLM INTELLIGENCE (Tier S layers 19 and 43).

Everyone mines the same trading literature. This searches ABSTRACT structures first and asks
whether they map to markets afterwards. Each lab is a deterministic program (no LLM) that reads a
return/price panel and emits structured hypothesis rows only where its structure is measurably
present:

    queueing         Little's law on volume bursts: arrival-rate spikes that outrun the
                     service rate (range) predict congestion (widening) and later release
    control          a Kalman-filtered local level; persistent innovations of one sign are a
                     controller that has lost tracking (trend) -- mean-reverting ones a
                     controller in control
    information      transfer entropy on sign sequences: which series carries information about
                     another's next move beyond its own past (directional, nonlinear lead-lag)
    ecology          Lotka-Volterra style predator/prey: two strategies' (momentum, reversion)
                     returns whose crowding oscillates -- one's past success predicts the other's
    signal           spectral peaks (periodogram vs a red-noise AR(1) null): cycles present at a
                     significant power
    dynamical        recurrence rate / determinism of the delay-embedded path vs shuffled
    network          eigenvector centrality of the correlation network: the hub whose move
                     leads the periphery
    bayesian         a Metropolis sampler of an AR(1) coefficient's posterior -- the MCMC member
                     of the heterogeneous-intelligence set
    operations       (in the researcher market) a MILP allocator -- `scipy.optimize.milp`
    constraint       SAT / constraint satisfaction: a branch-and-bound search for MINIMAL
                     conjunctions of sign literals (last bar up, 5/24-bar trend, above the
                     24-bar mean, wide range, busy tape) that satisfy support, same-sign and
                     strength constraints in BOTH halves of the sample at once, then a Bonferroni
                     bar over every clause it evaluated
    gaussian_process an ARD squared-exponential GP of the next return on four causal return
                     features, hyperparameters by marginal likelihood, judged on a blind next
                     window; its shortest length-scale names the feature it leans on

Every row carries the lab, the measured statistic, its null and a falsifier.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np
import numpy.typing as npt

F = npt.NDArray[np.float64]


def _row(lab: str, symbols: list[str], stat: float, null: str, claim: str, falsifier: str,
         **kw: Any) -> dict[str, Any]:
    return {"kind": "hypothesis", "family": f"xsci_{lab}", "mechanism": f"cross_science_{lab}",
            "symbols": symbols, "lab": lab, "statistic": round(float(stat), 5), "null": null,
            "claim": claim, "falsifier": falsifier, **kw}


def transfer_entropy(x: F, y: F) -> float:
    """TE_{x->y} on sign sequences, lag 1, bits."""
    xs = (x > 0).astype(int)
    ys = (y > 0).astype(int)
    y1, y0, x0 = ys[1:], ys[:-1], xs[:-1]
    n = len(y1)
    if n < 50:
        return 0.0
    te = 0.0
    for a in (0, 1):
        for b in (0, 1):
            for c in (0, 1):
                p_abc = np.mean((y1 == a) & (y0 == b) & (x0 == c))
                if p_abc == 0:
                    continue
                p_bc = np.mean((y0 == b) & (x0 == c))
                p_ab = np.mean((y1 == a) & (y0 == b))
                p_b = np.mean(y0 == b)
                te += p_abc * math.log2((p_abc / p_bc) / (p_ab / p_b))
    return float(te)


def info_lab(panel: Mapping[str, F], top: int = 10, n_shuffle: int = 20,
             seed: int = 0) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    names = sorted(panel)
    rows = []
    for a in names:
        for b in names:
            if a == b:
                continue
            x, y = panel[a], panel[b]
            n = min(len(x), len(y))
            te = transfer_entropy(x[:n], y[:n])
            null = [transfer_entropy(rng.permutation(x[:n]), y[:n]) for _ in range(n_shuffle)]
            thr = float(np.quantile(null, 0.95)) if null else 0.0
            if te > thr and te > 0:
                rows.append(_row("information", [b, a], te, f"shuffle 95% {thr:.5f}",
                                 f"{a}'s sign carries {te:.4f} bits about {b}'s next sign beyond "
                                 f"{b}'s own past", "TE falls inside the shuffle null out of "
                                 "sample", driver=a, target=b))
    rows.sort(key=lambda r: -float(r["statistic"]))
    return rows[:top]


def spectral_lab(panel: Mapping[str, F], top: int = 10) -> list[dict[str, Any]]:
    rows = []
    for s, r in sorted(panel.items()):
        n = len(r)
        if n < 128:
            continue
        x = r - r.mean()
        phi = float(np.corrcoef(x[:-1], x[1:])[0, 1]) if x.std() > 0 else 0.0
        freqs = np.fft.rfftfreq(n)[1:]
        power = (np.abs(np.fft.rfft(x)) ** 2)[1:] / n
        red = x.var() * (1 - phi ** 2) / (1 + phi ** 2 - 2 * phi * np.cos(2 * np.pi * freqs))
        ratio = power / np.maximum(red, 1e-18)
        k = int(np.argmax(ratio))
        # chi-square(2)/2: the 99.9% point, Bonferroni-ish over frequencies
        crit = -math.log(0.001 / len(freqs))
        if ratio[k] > crit:
            period = 1.0 / freqs[k]
            rows.append(_row("signal", [s], float(ratio[k]), f"red-noise AR(1) x{crit:.1f}",
                             f"{s} has a cycle of {period:.1f} bars at {ratio[k]:.1f}x red-noise "
                             "power", "the peak vanishes in the next window", period=period))
    rows.sort(key=lambda r: -float(r["statistic"]))
    return rows[:top]


def kalman_lab(panel: Mapping[str, F], top: int = 10, q: float = 1e-5) -> list[dict[str, Any]]:
    rows = []
    for s, r in sorted(panel.items()):
        if len(r) < 100:
            continue
        lvl, p, rvar = 0.0, 1.0, float(r.var()) or 1e-8
        innov = []
        for v in r:
            p += q
            k = p / (p + rvar)
            e = float(v) - lvl
            innov.append(e)
            lvl += k * e
            p *= 1 - k
        inn = np.asarray(innov[20:])
        ac = float(np.corrcoef(inn[:-1], inn[1:])[0, 1]) if inn.std() > 0 else 0.0
        z = ac * math.sqrt(len(inn))
        if abs(z) > 3.0:
            mode = "lost tracking (persistent trend)" if ac > 0 else "over-correcting (reversion)"
            rows.append(_row("control", [s], z, "innovation ac z under white noise",
                             f"{s}: the local-level controller is {mode}, innovation ac {ac:+.3f}",
                             "innovation autocorrelation insignificant next window", ac=ac))
    rows.sort(key=lambda r: -abs(float(r["statistic"])))
    return rows[:top]


def queue_lab(prices: Mapping[str, F], volumes: Mapping[str, F], top: int = 10
              ) -> list[dict[str, Any]]:
    rows = []
    for s in sorted(set(prices) & set(volumes)):
        v, px = volumes[s], prices[s]
        n = min(len(v), len(px))
        if n < 100:
            continue
        v, px = v[-n:], px[-n:]
        rng_ = np.abs(np.diff(np.log(px)))
        lam = v[1:] / (np.mean(v) or 1.0)
        mu = rng_ / (np.mean(rng_) or 1e-12)
        rho = lam / np.maximum(mu, 1e-6)
        congested = rho > np.quantile(rho, 0.9)
        nxt = rng_[1:]
        if congested[:-1].sum() < 10:
            continue
        lift = float(nxt[congested[:-1]].mean() / (nxt.mean() or 1e-12))
        if lift > 1.2:
            rows.append(_row("queueing", [s], lift, "next-bar range ratio 1.0",
                             f"{s}: when arrivals outrun service (rho top decile) the next bar's "
                             f"range is {lift:.2f}x normal -- a congestion release", "lift < 1.1 "
                             "out of sample"))
    rows.sort(key=lambda r: -float(r["statistic"]))
    return rows[:top]


def ecology_lab(panel: Mapping[str, F], top: int = 10) -> list[dict[str, Any]]:
    rows = []
    for s, r in sorted(panel.items()):
        if len(r) < 200:
            continue
        mom = np.sign(r[:-1]) * r[1:]
        rev = -mom
        w = 20
        k = len(mom) // w
        if k < 8:
            continue
        m = mom[: k * w].reshape(k, w).sum(axis=1)
        v = rev[: k * w].reshape(k, w).sum(axis=1)
        c = float(np.corrcoef(m[:-1], v[1:])[0, 1]) if m.std() > 0 and v.std() > 0 else 0.0
        z = c * math.sqrt(k - 1)
        if abs(z) > 2.5:
            rows.append(_row("ecology", [s], z, "no predator-prey coupling",
                             f"{s}: momentum's success in one 20-bar season predicts reversion's "
                             f"next season (corr {c:+.2f}) -- crowding cycles between the two",
                             "the coupling disappears out of sample", coupling=c))
    rows.sort(key=lambda r: -abs(float(r["statistic"])))
    return rows[:top]


def recurrence_lab(panel: Mapping[str, F], top: int = 10, dim: int = 3, seed: int = 0
                   ) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    rows = []

    def det(x: F) -> float:
        if len(x) < dim + 50:
            return 0.0
        z = np.lib.stride_tricks.sliding_window_view(x[-400:], dim)
        z = (z - z.mean()) / (z.std() or 1.0)
        d = np.sqrt(((z[:, None, :] - z[None, :, :]) ** 2).sum(-1))
        eps = np.quantile(d, 0.1)
        rec = d < eps
        diag = rec[:-1, :-1] & rec[1:, 1:]
        return float(diag.sum() / max(1, rec.sum()))

    for s, r in sorted(panel.items()):
        if len(r) < 200:
            continue
        d0 = det(r)
        null = [det(rng.permutation(r)) for _ in range(5)]
        mu, sd = float(np.mean(null)), float(np.std(null)) or 1e-6
        z = (d0 - mu) / sd
        if z > 3.0:
            rows.append(_row("dynamical", [s], z, "shuffled-path determinism",
                             f"{s}: its delay-embedded path revisits states deterministically "
                             f"(DET {d0:.3f} vs shuffled {mu:.3f})", "determinism excess vanishes "
                             "in the next window"))
    rows.sort(key=lambda r: -float(r["statistic"]))
    return rows[:top]


def network_lab(panel: Mapping[str, F], top: int = 5) -> list[dict[str, Any]]:
    names = sorted(panel)
    if len(names) < 4:
        return []
    n = min(len(panel[s]) for s in names)
    x = np.column_stack([panel[s][-n:] for s in names])
    if n < 60:
        return []
    c = np.abs(np.nan_to_num(np.corrcoef(x, rowvar=False)))
    np.fill_diagonal(c, 0.0)
    _ev, vec = np.linalg.eigh(c)
    cent = np.abs(vec[:, -1])
    hub = int(np.argmax(cent))
    lead = []
    for j in range(len(names)):
        if j == hub:
            continue
        a, b = x[:-1, hub], x[1:, j]
        if a.std() > 0 and b.std() > 0:
            lead.append((names[j], float(np.corrcoef(a, b)[0, 1])))
    lead.sort(key=lambda t: -abs(t[1]))
    rows = []
    for tgt, cc in lead[:top]:
        z = cc * math.sqrt(n - 1)
        if abs(z) > 3.0:
            rows.append(_row("network", [tgt, names[hub]], z, "no hub lead",
                             f"network hub {names[hub]} (centrality {cent[hub]:.2f}) leads "
                             f"{tgt} by one bar (corr {cc:+.3f})", "lead corr insignificant "
                             "next window", hub=names[hub], corr=round(cc, 5)))
    return rows


def mcmc_ar1(r: F, draws: int = 3000, seed: int = 0) -> dict[str, float]:
    """Random-walk Metropolis for phi in r_t = phi r_{t-1} + e, flat prior on (-1, 1)."""
    rng = np.random.default_rng(seed)
    x, y = r[:-1], r[1:]
    s2 = float(y.var()) or 1e-12

    def loglik(phi: float) -> float:
        if not -1 < phi < 1:
            return -math.inf
        e = y - phi * x
        return float(-0.5 * (e @ e) / s2)

    phi, ll = 0.0, loglik(0.0)
    out = []
    step = 1.0 / math.sqrt(max(len(y), 1))
    acc = 0
    for i in range(draws):
        prop = phi + float(rng.normal(0, step))
        lp = loglik(prop)
        if math.log(rng.random() + 1e-300) < lp - ll:
            phi, ll = prop, lp
            acc += 1
        if i >= draws // 4:
            out.append(phi)
    arr = np.asarray(out)
    return {"mean": float(arr.mean()), "lo": float(np.quantile(arr, 0.025)),
            "hi": float(np.quantile(arr, 0.975)), "p_positive": float((arr > 0).mean()),
            "acceptance": acc / draws}


def bayes_lab(panel: Mapping[str, F], top: int = 10) -> list[dict[str, Any]]:
    rows = []
    for s, r in sorted(panel.items()):
        if len(r) < 200:
            continue
        post = mcmc_ar1(r)
        if post["lo"] > 0 or post["hi"] < 0:
            kind = "persistence" if post["mean"] > 0 else "reversion"
            rows.append(_row("bayesian", [s], post["mean"], "95% credible interval covers 0",
                             f"{s}: posterior AR(1) {post['mean']:+.3f} "
                             f"[{post['lo']:+.3f}, {post['hi']:+.3f}] -- {kind}",
                             "the credible interval covers 0 next window", posterior=post))
    rows.sort(key=lambda r: -abs(float(r["statistic"])))
    return rows[:top]


# ------------------------------------------------------------------------------------------------
# CONSTRAINT LAB (SAT / constraint satisfaction) and GAUSSIAN-PROCESS LAB -- 2026-09-30
# ------------------------------------------------------------------------------------------------

#: the constraint lab's literals: name -> grammar expression whose SIGN is the literal. Each is
#: computed here in numpy with the grammar's meaning, and the expression is what the factory
#: re-judges, so a disagreement between the two costs a trial, never a false certificate.
CONSTRAINT_LITERALS: dict[str, str] = {
    "up1": "sign(ret)",
    "trend5": "sign(delta(close, 5))",
    "trend24": "sign(delta(close, 24))",
    "above_mean24": "sign(sub(close, mean(close, 24)))",
    "wide_range": "sign(zscore(range, 120))",
    "busy": "sign(zscore(activity, 120))",
}


def _roll_mean(x: F, w: int) -> F:
    """Trailing w-bar mean; NaN wherever the window holds a NaN (never poisons later bars)."""
    bad = ~np.isfinite(x)
    c = np.cumsum(np.concatenate([[0.0], np.where(bad, 0.0, x)]))
    nb = np.cumsum(np.concatenate([[0], bad.astype(int)]))
    out = np.full(len(x), np.nan)
    if len(x) >= w:
        out[w - 1:] = np.where(nb[w:] - nb[:-w] > 0, np.nan, (c[w:] - c[:-w]) / w)
    return out


def _roll_z(x: F, w: int) -> F:
    m = _roll_mean(x, w)
    m2 = _roll_mean(x * x, w)
    sd = np.sqrt(np.maximum(m2 - m * m, 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        out: F = np.where(sd > 0, (x - m) / sd, np.nan)
    return out


def literal_signs(close: F, volume: F | None = None) -> dict[str, F]:
    """Each literal's sign at every bar t (aligned to close[1:]; NaN where undefined)."""
    lc = np.log(close)
    r = np.diff(lc)
    n = len(r)
    px = close[1:]

    def delta(w: int) -> F:
        d = np.full(n, np.nan)
        d[w - 1:] = px[w - 1:] - close[: n - w + 1]
        return d

    out: dict[str, F] = {"up1": np.sign(r), "trend5": np.sign(delta(5)),
                         "trend24": np.sign(delta(24)),
                         "above_mean24": np.sign(px - _roll_mean(px, 24)),
                         "wide_range": np.sign(_roll_z(np.abs(r), 120))}
    if volume is not None and len(volume) >= len(close):
        out["busy"] = np.sign(_roll_z(np.asarray(volume[-n:], dtype=float), 120))
    return out


def _clause_mask(lits: Mapping[str, F], clause: tuple[tuple[str, int], ...]) -> F:
    m = np.ones(len(next(iter(lits.values()))), dtype=bool)
    for name, pol in clause:
        m &= lits[name] == pol
    out: F = m.astype(float)
    return out


def constraint_search(fwd: F, lits: Mapping[str, F], *, max_len: int = 3,
                      min_support: int = 40, t_half: float = 2.0) -> dict[str, Any]:
    """Branch-and-bound search for MINIMAL conjunctions of literals that SATISFY every
    constraint at once:

        support   >= min_support bars in EACH half of the sample
        sign      the mean forward return has the same sign in both halves
        strength  |t| >= t_half in each half, and |t| over the whole sample clears a
                  Bonferroni bar over every clause the search evaluated

    Support is anti-monotone under conjunction, so a clause failing it prunes its whole
    subtree; a clause that is already satisfied is not extended (minimality). Returns the
    satisfying clauses and the count of clauses evaluated (the multiplicity charge)."""
    n = len(fwd)
    half = n // 2
    # the clause must beat the half's own drift: a trending sample makes every clause "positive"
    fwd = np.concatenate([fwd[:half] - fwd[:half].mean(), fwd[half:] - fwd[half:].mean()])
    names = sorted(lits)
    atoms = [(k, p) for k in names for p in (1, -1)]
    sat: list[dict[str, Any]] = []
    evaluated = 0

    def stats(m: F) -> tuple[int, int, float, float, float, float]:
        a, b = m[:half] > 0, m[half:] > 0
        ya, yb = fwd[:half][a], fwd[half:][b]

        def t(y: F) -> float:
            return float(y.mean() / (y.std(ddof=1) / math.sqrt(len(y)))) if len(y) > 2 and \
                y.std() > 0 else 0.0
        return int(a.sum()), int(b.sum()), float(ya.mean()) if len(ya) else 0.0, \
            float(yb.mean()) if len(yb) else 0.0, t(ya), t(yb)

    frontier: list[tuple[tuple[str, int], ...]] = [((k, p),) for k, p in atoms]
    found: list[tuple[tuple[str, int], ...]] = []
    while frontier:
        clause = frontier.pop(0)
        if any(set(f) <= set(clause) for f in found):
            continue                                        # a satisfied subset: not minimal
        evaluated += 1
        m = _clause_mask(lits, clause)
        sa, sb, ma, mb, ta, tb = stats(m)
        if sa < min_support or sb < min_support:
            continue                                        # prune: support only shrinks
        if ma * mb > 0 and abs(ta) >= t_half and abs(tb) >= t_half:
            found.append(clause)
            y = fwd[m > 0]
            sat.append({"clause": [f"{k}{'+' if p > 0 else '-'}" for k, p in clause],
                        "atoms": [[k, p] for k, p in clause], "support": sa + sb,
                        "mean": float(y.mean()), "t_first": ta, "t_second": tb,
                        "t_all": float(y.mean() / (y.std(ddof=1) / math.sqrt(len(y))))})
            continue
        if len(clause) < max_len:
            last = names.index(clause[-1][0])
            for k in names[last + 1:]:
                for p in (1, -1):
                    frontier.append((*clause, (k, p)))
    crit = _bonferroni_z(max(evaluated, 1))
    kept = [s for s in sat if abs(s["t_all"]) >= crit]
    return {"evaluated": evaluated, "bonferroni_z": round(crit, 3), "satisfying": kept,
            "satisfying_before_bonferroni": len(sat)}


def _bonferroni_z(k: int, alpha: float = 0.05) -> float:
    from scipy.stats import norm
    return float(norm.isf(alpha / (2.0 * k)))


def constraint_expression(atoms: list[list[Any]], direction: float) -> str | None:
    """The conjunction as a grammar expression, or None when the grammar cannot hold it.

    LONG: min2 of the signed literals is +1 exactly when every literal holds (-1 or 0 when one
    fails), so max2(min2(l...), zero) is 1 inside the clause and flat outside it, where zero is
    sub(ret, ret). SHORT: max2 of the NEGATED literals is -1 exactly when every literal holds,
    so min2(max2(-l...), zero) is -1 inside and flat outside -- the same depth as the long, and a
    negative-polarity literal's negation is the bare literal. The grammar caps a tree at
    MAX_DEPTH; a clause that still does not fit is returned as None and counted by the caller
    as INEXPRESSIBLE, never truncated into a different claim."""
    from libs.research import alpha_grammar as ag

    def lit(k: str, pol: int) -> str:
        return CONSTRAINT_LITERALS[k] if pol > 0 else f"neg({CONSTRAINT_LITERALS[k]})"

    d = 1 if direction > 0 else -1
    lits = [lit(str(k), int(p) * d) for k, p in atoms]
    op = "min2" if d > 0 else "max2"
    m = lits[0]
    for x in lits[1:]:
        m = f"{op}({m}, {x})"
    zero = "sub(ret, ret)"
    text = f"max2({m}, {zero})" if d > 0 else f"min2({m}, {zero})"
    try:
        return text if ag.is_valid(ag.from_str(text)) else None
    except Exception:
        return None


def constraint_lab(prices: Mapping[str, F], volumes: Mapping[str, F] | None = None,
                   top: int = 10) -> list[dict[str, Any]]:
    rows = []
    for s, px in sorted(prices.items()):
        if len(px) < 600:
            continue
        lits = literal_signs(px, (volumes or {}).get(s))
        r = np.diff(np.log(px))
        fwd = np.append(r[1:], np.nan)
        ok = np.isfinite(fwd)
        for v in lits.values():
            ok &= np.isfinite(v)
        if ok.sum() < 400:
            continue
        res = constraint_search(fwd[ok], {k: v[ok] for k, v in lits.items()})
        for c in res["satisfying"]:
            d = 1.0 if c["mean"] > 0 else -1.0
            rows.append(_row("constraint", [s], c["t_all"],
                             f"Bonferroni z {res['bonferroni_z']} over {res['evaluated']} clauses",
                             f"{s}: when {' AND '.join(c['clause'])} the next bar's return is "
                             f"{'positive' if d > 0 else 'negative'} in BOTH halves "
                             f"(t {c['t_first']:+.2f}, {c['t_second']:+.2f}; support "
                             f"{c['support']})", "the clause's sign or strength fails a half "
                             "out of sample", atoms=c["atoms"], direction=d,
                             expr=constraint_expression(c["atoms"], d),
                             evaluated=res["evaluated"]))
    rows.sort(key=lambda r: -abs(float(r["statistic"])))
    return rows[:top]


#: the GP lab's inputs: name -> grammar expression; each is a causal feature of past returns
GP_FEATURES: dict[str, str] = {
    "mean2": "mean(ret, 2)",
    "mean5": "mean(ret, 5)",
    "mean24": "mean(ret, 24)",
    "dev24": "zscore(sub(close, mean(close, 24)), 120)",
}


def gp_features(close: F) -> tuple[list[str], F, F]:
    """(names, X aligned to bar t, next-bar return y)."""
    r = np.diff(np.log(close))
    px = close[1:]
    feats = {"mean2": _roll_mean(r, 2), "mean5": _roll_mean(r, 5), "mean24": _roll_mean(r, 24),
             "dev24": _roll_z(px - _roll_mean(px, 24), 120)}
    names = list(feats)
    x = np.column_stack([feats[k] for k in names])
    y = np.append(r[1:], np.nan)
    ok = np.isfinite(x).all(axis=1) & np.isfinite(y)
    return names, x[ok], y[ok]


def _gp_nll(theta: F, sq: F, y: F) -> tuple[float, F]:
    """Negative log marginal likelihood and its analytic gradient. `sq`: (d, n, n) per-feature
    squared differences, precomputed once per fit."""
    d = sq.shape[0]
    inv2 = np.exp(-2.0 * theta[:d])
    sf2, sn2 = math.exp(2 * theta[-2]), math.exp(2 * theta[-1])
    base = np.exp(-0.5 * np.tensordot(inv2, sq, axes=1))
    n = len(y)
    k = sf2 * base + (sn2 + 1e-9) * np.eye(n)
    try:
        c = np.linalg.cholesky(k)
    except np.linalg.LinAlgError:
        return 1e12, np.zeros_like(theta)
    ci = np.linalg.solve(c, np.eye(n))
    kinv = ci.T @ ci
    a = kinv @ y
    nll = float(0.5 * y @ a + np.log(np.diag(c)).sum() + 0.5 * n * math.log(2 * math.pi))
    w = np.outer(a, a) - kinv                              # dNLL/dK = -0.5 * w
    g = np.empty_like(theta)
    kf = sf2 * base
    for i in range(d):
        g[i] = -0.5 * float(np.sum(w * kf * sq[i] * inv2[i]))
    g[-2] = -0.5 * float(np.sum(w * 2.0 * kf))
    g[-1] = -0.5 * float(np.trace(w) * 2.0 * sn2)
    return nll, g


def gp_fit_predict(x_tr: F, y_tr: F, x_te: F) -> tuple[F, F]:
    """ARD squared-exponential GP; hyperparameters by maximum marginal likelihood (L-BFGS-B).
    Returns (predictive mean on x_te, fitted length-scales)."""
    from scipy.optimize import minimize
    mu, sd = x_tr.mean(0), x_tr.std(0)
    sd = np.where(sd > 0, sd, 1.0)
    xs, xt = (x_tr - mu) / sd, (x_te - mu) / sd
    ym, ys = float(y_tr.mean()), float(y_tr.std()) or 1.0
    yn = (y_tr - ym) / ys
    th0 = np.concatenate([np.zeros(xs.shape[1]), [math.log(0.3), 0.0]])
    bounds = [(-2.0, 4.0)] * xs.shape[1] + [(-5.0, 2.0), (-3.0, 1.0)]
    sq = (xs.T[:, :, None] - xs.T[:, None, :]) ** 2
    res = minimize(_gp_nll, th0, args=(sq, yn), jac=True, method="L-BFGS-B", bounds=bounds,
                   options={"maxiter": 40})
    th = res.x
    ell = np.exp(th[: xs.shape[1]])
    sf2, sn2 = math.exp(2 * th[-2]), math.exp(2 * th[-1])

    def kern(a: F, b: F) -> F:
        za, zb = a / ell, b / ell
        d2 = np.sum(za * za, 1)[:, None] + np.sum(zb * zb, 1)[None, :] - 2 * za @ zb.T
        out: F = sf2 * np.exp(-0.5 * np.maximum(d2, 0.0))
        return out

    k = kern(xs, xs) + (sn2 + 1e-9) * np.eye(len(yn))
    alpha = np.linalg.solve(k, yn)
    pred: F = kern(xt, xs) @ alpha * ys + ym
    return pred, ell


def gp_lab(prices: Mapping[str, F], top: int = 10, n_train: int = 300, n_test: int = 400,
           max_symbols: int = 8) -> list[dict[str, Any]]:
    """Fit a GP of the next return on four causal return features over one window, predict the
    NEXT window blind, and keep a symbol only where the out-of-sample correlation between the
    GP's predictive mean and the realised return is significant (z > 3). The feature with the
    shortest ARD length-scale is the one the GP says the next return depends on most; its
    out-of-sample sign against the prediction orients the grammar expression."""
    rows = []
    for s, px in sorted(prices.items(), key=lambda kv: -len(kv[1]))[:max_symbols]:
        names, x, y = gp_features(px)
        if len(y) < n_train + n_test:
            continue
        x_tr, y_tr = x[-(n_train + n_test):-n_test], y[-(n_train + n_test):-n_test]
        x_te, y_te = x[-n_test:], y[-n_test:]
        try:
            pred, ell = gp_fit_predict(x_tr, y_tr, x_te)
        except (np.linalg.LinAlgError, ValueError):
            continue
        if pred.std() <= 0 or y_te.std() <= 0:
            continue
        c = float(np.corrcoef(pred, y_te)[0, 1])
        z = c * math.sqrt(n_test - 1)
        if z <= 3.0:
            continue
        k = int(np.argmin(ell))
        fx = x_te[:, k]
        sgn = float(np.sign(np.corrcoef(fx, pred)[0, 1])) if fx.std() > 0 else 0.0
        if sgn == 0:
            continue
        rows.append(_row("gaussian_process", [s], z, "OOS corr z under no predictability",
                         f"{s}: a GP on past returns predicts the next {n_test} bars blind "
                         f"(OOS corr {c:+.3f}); it leans most on {names[k]} "
                         f"(length-scale {ell[k]:.2f})", "OOS correlation insignificant in "
                         "the next window", feature=names[k], direction=sgn,
                         length_scales={n: round(float(v), 4) for n, v in zip(names, ell,
                                                                               strict=True)},
                         oos_corr=round(c, 5)))
    rows.sort(key=lambda r: -float(r["statistic"]))
    return rows[:top]


def gp_expression(feature: str, direction: float) -> str | None:
    e = GP_FEATURES.get(feature)
    if e is None:
        return None
    return e if direction > 0 else f"neg({e})"


def run_all(panel: Mapping[str, F], prices: Mapping[str, F] | None = None,
            volumes: Mapping[str, F] | None = None) -> dict[str, list[dict[str, Any]]]:
    out = {"information": info_lab(panel), "signal": spectral_lab(panel),
           "control": kalman_lab(panel), "ecology": ecology_lab(panel),
           "dynamical": recurrence_lab(panel), "network": network_lab(panel),
           "bayesian": bayes_lab(panel)}
    if prices and volumes:
        out["queueing"] = queue_lab(prices, volumes)
    if prices:
        out["constraint"] = constraint_lab(prices, volumes)
        out["gaussian_process"] = gp_lab(prices)
    return out
