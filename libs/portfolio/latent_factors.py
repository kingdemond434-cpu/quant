"""Dynamic latent factors, tail dependence and the four heats: what 20% nominal is REALLY made of.

    R_i = B_i f + eps_i

estimated on an exponentially weighted, shrunk covariance so B_t and Sigma_t move with the
market: when stress begins, edges that looked independent collapse onto one latent factor and
the desk must see N_eff fall BEFORE the drawdown teaches it. Alongside the average-state
picture the module carries the bad-state one -- tail dependence per pair and correlations on the
book's own worst days -- because capital should be sized on how the sleeves behave when the
book is hurting, not on how they behave on a Tuesday.

THE FOUR HEATS of a book h (fractions of equity at stop):

    nominal      sum |h_i|                                 what the floor and the ceiling count
    covariance   sqrt(h' rho h)                            the same variance as this many
                                                            perfectly correlated sleeves
    factor       sqrt(h' rho_factor h)                     rho implied by the k-factor model:
                                                            latent common exposure only
    tail         sqrt(h' rho_stress h)                     rho on the worst-decile days

    H_eff = max(covariance, factor, tail)

Between nominal / sqrt(N) (all independent) and nominal (one bet). `effective` reports all four
and N_eff under each, and `drift` says whether the correlation structure has moved away from its
long-run shape -- the change-point signal the allocator's crisis overlay should hear.
`crisis_share_from_drift` is HOW it hears it: the desk-level verdict in `reports/DRIFT.json`
raises the share of crisis worlds the book is scored against, so a fusing market changes the
POPULATION the objective solves over rather than a knob somebody turns.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import numpy as np


def _ew_weights(n: int, halflife: float) -> np.ndarray:
    lam = 0.5 ** (1.0 / max(halflife, 1.0))
    w = lam ** np.arange(n - 1, -1, -1)
    out: np.ndarray = w / w.sum()
    return out


def ew_cov(m: np.ndarray, halflife: float = 60.0, shrink: float = 0.2) -> np.ndarray:
    w = _ew_weights(m.shape[0], halflife)
    mu = w @ m
    x = m - mu
    c = (x * w[:, None]).T @ x
    d = np.diag(np.diag(c))
    out: np.ndarray = (1.0 - shrink) * c + shrink * d + 1e-12 * np.eye(c.shape[0])
    return out


def corr_of(cov: np.ndarray) -> np.ndarray:
    sd = np.sqrt(np.clip(np.diag(cov), 1e-18, None))
    return cov / np.outer(sd, sd)


def factor_model(m: np.ndarray, k: int = 3, halflife: float = 60.0) -> dict[str, Any]:
    """PCA on the EW correlation: loadings B (N x k), factor variances, and the implied rho."""
    cov = ew_cov(m, halflife)
    rho = corr_of(cov)
    vals, vecs = np.linalg.eigh(rho)
    order = np.argsort(vals)[::-1]
    vals, vecs = vals[order], vecs[:, order]
    k = int(min(k, len(vals)))
    b = vecs[:, :k] * np.sqrt(np.clip(vals[:k], 0.0, None))
    common = b @ b.T
    spec = np.clip(1.0 - np.diag(common), 1e-6, None)
    rho_f = common + np.diag(spec)
    explained = float(np.clip(vals[:k], 0, None).sum() / max(vals.clip(0).sum(), 1e-12))
    return {"loadings": b, "factor_var": vals[:k], "rho_factor": rho_f, "rho": rho,
            "explained": explained, "cov": cov}


def stress_corr(m: np.ndarray, q: float = 0.1) -> tuple[np.ndarray, int]:
    """Correlation on the days the equal-weight book was in its worst `q` decile."""
    ew = m.mean(axis=1)
    k = max(5, int(q * m.shape[0]))
    idx = np.argsort(ew)[:k]
    sub = m[idx]
    sd = sub.std(axis=0)
    if sub.shape[0] < 5 or not np.all(sd > 0):
        return corr_of(ew_cov(m)), int(sub.shape[0])
    return np.corrcoef(sub, rowvar=False), int(sub.shape[0])


def tail_dependence(m: np.ndarray, q: float = 0.1) -> np.ndarray:
    """lambda_ij = P(R_i < q_i, R_j < q_j) / q -- 1.0 is perfect lower-tail dependence."""
    n = m.shape[1]
    thr = np.quantile(m, q, axis=0)
    below = m < thr
    out = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            out[i, j] = out[j, i] = float((below[:, i] & below[:, j]).mean() / q)
    return out


def n_eff(rho: np.ndarray, w: np.ndarray) -> float:
    w = w / w.sum() if w.sum() > 0 else np.full_like(w, 1.0 / max(w.size, 1))
    d = float(w @ rho @ w)
    return float(1.0 / d) if d > 0 else float(w.size)


def effective(ev: Sequence[Any], book: Mapping[str, float], *, k: int = 3,
              halflife: float = 60.0) -> dict[str, Any]:
    names = [e.name for e in ev if float(book.get(e.name, 0.0)) > 1e-6]
    if len(names) < 2:
        h1 = float(sum(book.values()))
        return {"nominal": h1, "covariance": h1, "factor": h1, "tail": h1, "effective": h1,
                "n_eff": {"covariance": 1.0, "factor": 1.0, "tail": 1.0}, "note": "single leg"}
    by = {e.name: e for e in ev}
    obs = min(int(by[n].daily_r.size) for n in names)
    m = np.stack([np.asarray(by[n].daily_r[-obs:], dtype=float) for n in names], axis=1)
    h = np.array([float(book[n]) for n in names])
    fm = factor_model(m, k=k, halflife=halflife)
    rho_s, n_stress = stress_corr(m)
    nominal = float(np.abs(h).sum())
    cov_heat = float(np.sqrt(max(float(h @ fm["rho"] @ h), 0.0)))
    fac_heat = float(np.sqrt(max(float(h @ fm["rho_factor"] @ h), 0.0)))
    tail_heat = float(np.sqrt(max(float(h @ rho_s @ h), 0.0)))
    td = tail_dependence(m)
    return {"nominal": round(nominal, 6), "covariance": round(cov_heat, 6),
            "factor": round(fac_heat, 6), "tail": round(tail_heat, 6),
            "effective": round(max(cov_heat, fac_heat, tail_heat), 6),
            "n_eff": {"covariance": round(n_eff(fm["rho"], h), 3),
                      "factor": round(n_eff(fm["rho_factor"], h), 3),
                      "tail": round(n_eff(rho_s, h), 3)},
            "factor_explained": round(fm["explained"], 4), "stress_days": n_stress,
            "max_tail_dependence": round(float(np.max(td - np.eye(len(names)))), 3),
            "top_loading": {names[i]: round(float(fm["loadings"][i, 0]), 3)
                            for i in np.argsort(-np.abs(fm["loadings"][:, 0]))[:5]},
            "rule": "H_eff = max(covariance, factor, tail) heat; 20% nominal on one latent "
                    "factor is 20% effective, 20% across independent mechanisms is far less"}


# --------------------------------------------------------------------------------- crisis share
#: A DRIFT report older than this describes a market that has since moved on, and a stale
#: change-point signal is not a reason to reprice the world population. The same 26h the
#: allocator's proof certificate expires on -- one number for "yesterday's evidence", not two
#: that drift apart.
DRIFT_MAX_AGE_S = 26 * 3600

#: The z lines `research/drift_monitor.py` reports its verdicts on, mirrored here so the response
#: is proportional to the SAME scale the verdict was decided on rather than to a second one.
WATCH_Z = 1.0
DRIFT_Z = 2.0

#: The most the crisis-world share may be multiplied by, reached on a structure break and on a
#: per-instrument hazard of 2x the drift line. Three times the standing share is a large change
#: in what the book is stressed against; more than that would be modelling a crisis the desk has
#: only forecast, not observed.
CRISIS_MULT_MAX = 3.0
#: And the absolute share it may never pass. Above a third of worlds the population stops being
#: "the mix of worlds the desk believes it is in" and becomes a permanent crisis assumption,
#: which prices every edge as if the tail were the base case.
CRISIS_SHARE_MAX = 0.35


def crisis_share_from_drift(drift_doc: Mapping[str, Any] | None, base_share: float, *,
                            now: float | None = None,
                            max_age_s: float = DRIFT_MAX_AGE_S) -> tuple[float, str]:
    """Crisis-world share the drift report argues for, and why. Never lowers it.

    THE CHANGE-POINT SIGNAL WAS WRITTEN AND NOT HEARD. `drift_monitor` measures whether the
    book's correlation topology has moved (`structure_verdict`) and whether any instrument's
    next-window hazard has (`hazard_max`), writes `reports/DRIFT.json`, and names the allocator's
    crisis overlay as a consumer -- and the allocator never opened the file. So the desk knew its
    sleeves were fusing and still drew the same 6% of crisis worlds it draws on a quiet Tuesday.

    THIS IS A BELIEF, NOT A RAIL. It does not cap, veto or shrink anything: it changes the MIX OF
    WORLDS the book is scored against, and E[log W] then sizes whatever it wants under that mix.
    That is where every other uncertainty on this desk enters, and it is why this needs no rail
    entry -- there is no exposure reduction here to bill, only a population the objective solves
    over. If the objective still wants 30% under three times the crisis worlds, it gets 30%.

    IT MAY ONLY RAISE. A calm report never licenses drawing FEWER crisis worlds than the standing
    share: that is how a book discovers its real correlations at the worst possible moment, and it
    is the same ratchet `conditional_covariance` applies to crisis severity. A missing, unreadable
    or stale report changes nothing at all -- and says so, because a silent fallback to the
    standing share is indistinguishable from a report that said "stable" (L1.28a).
    """
    base = float(base_share)
    if base <= 0.0:
        return base, f"the standing crisis share is {base:.1%}; nothing to raise"
    if not isinstance(drift_doc, Mapping) or not drift_doc:
        return base, (f"no readable DRIFT.json: the crisis share stands at {base:.1%} "
                      "(absence is not calm)")
    stamp = str(drift_doc.get("generated_utc") or "")
    try:
        when = datetime.fromisoformat(stamp)
        when = when if when.tzinfo else when.replace(tzinfo=UTC)
        age = (datetime.now(tz=UTC).timestamp() if now is None else float(now)) - when.timestamp()
    except (TypeError, ValueError):
        return base, (f"DRIFT.json carries no readable generated_utc ({stamp!r}): the crisis "
                      f"share stands at {base:.1%}")
    if age > max_age_s:
        return base, (f"DRIFT.json is {age / 3600:.1f}h old (max {max_age_s / 3600:.0f}h): the "
                      f"crisis share stands at {base:.1%}")
    overall = str(drift_doc.get("verdict") or "UNMEASURED")
    structure = str(drift_doc.get("structure_verdict") or "UNMEASURED")
    verdict = "STRUCTURE_SHIFTED" if "STRUCTURE_SHIFTED" in (overall, structure) else overall
    hazard = drift_doc.get("hazard_max")
    try:
        hz = float(hazard) if hazard is not None else None
    except (TypeError, ValueError):
        hz = None

    if verdict == "STRUCTURE_SHIFTED":
        mult, why = CRISIS_MULT_MAX, ("STRUCTURE_SHIFTED: the book's correlation topology moved, "
                                      "which outranks any single instrument's hazard")
    elif verdict == "DRIFT_AHEAD":
        if hz is None:
            return base, ("DRIFT_AHEAD with no hazard_max to scale by: the crisis share stands "
                          f"at {base:.1%} rather than moving on an unread number")
        frac = min(max((hz - WATCH_Z) / (2.0 * DRIFT_Z - WATCH_Z), 0.0), 1.0)
        mult = 1.0 + (CRISIS_MULT_MAX - 1.0) * frac
        why = (f"DRIFT_AHEAD at hazard_max {hz:.2f}: proportional between the watch line "
               f"({WATCH_Z:.0f}) and twice the drift line ({2.0 * DRIFT_Z:.0f})")
    else:
        return base, (f"drift verdict {verdict}"
                      + (f" (hazard_max {hz:.2f})" if hz is not None else "")
                      + f": the crisis share stands at {base:.1%}")

    share = min(max(base, base * mult), CRISIS_SHARE_MAX)
    capped = "" if share < CRISIS_SHARE_MAX - 1e-12 else f", capped at {CRISIS_SHARE_MAX:.0%}"
    return float(share), (f"crisis worlds {base:.1%} -> {share:.1%} (x{mult:.2f}{capped}) -- "
                          f"{why}; the objective still chooses the heat under that mix")


def drift(m: np.ndarray, recent: int = 40, halflife: float = 60.0) -> dict[str, Any]:
    """Has the correlation topology moved? Frobenius distance recent-vs-long-run, in units of
    the long-run's own between-window variation (a z-score a threshold can be set on)."""
    if m.shape[0] < 3 * recent:
        return {"z": None, "why": f"need {3 * recent} rows"}
    rho_long = corr_of(ew_cov(m, halflife=halflife))
    rho_now = np.corrcoef(m[-recent:], rowvar=False)
    dist_now = float(np.linalg.norm(rho_now - rho_long))
    past = []
    for end in range(recent, m.shape[0] - recent, recent):
        blk = m[end - recent:end]
        if np.all(blk.std(axis=0) > 0):
            past.append(float(np.linalg.norm(np.corrcoef(blk, rowvar=False) - rho_long)))
    if len(past) < 3:
        return {"z": None, "distance": dist_now, "why": "not enough past windows"}
    mu, sd = float(np.mean(past)), float(np.std(past, ddof=1))
    z = (dist_now - mu) / sd if sd > 0 else 0.0
    return {"z": round(z, 3), "distance": round(dist_now, 4), "baseline_mean": round(mu, 4),
            "verdict": ("STRUCTURE_SHIFTED" if z > 2.0 else "STABLE"), "windows": len(past)}
