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
                             "next window", hub=names[hub]))
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


def run_all(panel: Mapping[str, F], prices: Mapping[str, F] | None = None,
            volumes: Mapping[str, F] | None = None) -> dict[str, list[dict[str, Any]]]:
    out = {"information": info_lab(panel), "signal": spectral_lab(panel),
           "control": kalman_lab(panel), "ecology": ecology_lab(panel),
           "dynamical": recurrence_lab(panel), "network": network_lab(panel),
           "bayesian": bayes_lab(panel)}
    if prices and volumes:
        out["queueing"] = queue_lab(prices, volumes)
    return out
