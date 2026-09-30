"""THE RESEARCH-SEARCH FRONTIER ESTIMATOR (Tier S layer 36): is more exploration still finding
novel mechanisms, and where is the unknown frontier?

"More crawling = more discovery" is a belief, not a measurement. This estimates, per ground and
overall:

    species curve       distinct mechanism species vs candidates examined
    Chao1 / unseen      the species the ground holds that nobody has seen yet
    coverage            Good-Turing sample coverage, 1 - f1/n
    novelty rate        new species per 100 candidates, recent window vs the one before
    yield exponent      survivors ~ compute^b fitted in logs; b < 1 is diminishing return
    alpha growth        effective independent-alpha rank over time (from the topology history)

and classifies each ground OPEN / SLOWING / SATURATING / UNMEASURED. It ranks; it never gates:
SATURATING is where the next hour buys least, not a licence to stop hunting (the standing rule).
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np


def chao1(counts: Mapping[str, int]) -> dict[str, float]:
    f1 = sum(1 for c in counts.values() if c == 1)
    f2 = sum(1 for c in counts.values() if c == 2)
    s_obs = len(counts)
    n = sum(counts.values())
    if n == 0:
        return {"observed": 0.0, "chao1": 0.0, "unseen": 0.0, "coverage": 0.0}
    unseen = (f1 * (f1 - 1) / 2.0) if f2 == 0 else (f1 * f1) / (2.0 * f2)
    unseen *= (n - 1) / n
    return {"observed": float(s_obs), "chao1": s_obs + unseen, "unseen": unseen,
            "coverage": 1.0 - f1 / n}


def novelty_rate(species_seq: Sequence[str], window: int = 300) -> dict[str, Any]:
    seen: set[str] = set()
    firsts: list[int] = []
    for s in species_seq:
        firsts.append(0 if s in seen else 1)
        seen.add(s)
    n = len(firsts)
    w = max(1, n // 2) if n < 2 * window else window
    recent = firsts[-w:]
    prior = firsts[-2 * w:-w] if n >= 2 * w else firsts[: max(1, n - w)]
    r = 100.0 * sum(recent) / max(1, len(recent))
    p = 100.0 * sum(prior) / max(1, len(prior))
    return {"new_per_100_recent": round(r, 3), "new_per_100_prior": round(p, 3),
            "ratio": round(r / p, 4) if p > 0 else None, "n": n}


def yield_exponent(compute: Sequence[float], survivors: Sequence[float]) -> dict[str, Any]:
    """Fit log(cum survivors) = a + b log(cum compute)."""
    c = np.cumsum(np.asarray(compute, dtype=float))
    s = np.cumsum(np.asarray(survivors, dtype=float))
    keep = (c > 0) & (s > 0)
    if keep.sum() < 4:
        return {"b": None, "n": int(keep.sum())}
    x, y = np.log(c[keep]), np.log(s[keep])
    b, a = np.polyfit(x, y, 1)
    return {"b": round(float(b), 4), "a": round(float(a), 4), "n": int(keep.sum()),
            "diminishing": bool(b < 1.0)}


def classify(est: Mapping[str, float], nov: Mapping[str, Any]) -> str:
    if est.get("observed", 0) == 0 or int(nov.get("n", 0)) < 50:
        return "UNMEASURED"
    cov = float(est.get("coverage", 0.0))
    ratio = nov.get("ratio")
    if cov >= 0.9 and (ratio is None or ratio < 0.5):
        return "SATURATING"
    if cov >= 0.6 or (ratio is not None and ratio < 0.7):
        return "SLOWING"
    return "OPEN"


def estimate(sightings: Sequence[tuple[str, str]], *,
             compute_series: Sequence[float] | None = None,
             survivor_series: Sequence[float] | None = None,
             rank_history: Sequence[float] | None = None) -> dict[str, Any]:
    """sightings: time-ordered (ground, species)."""
    by_ground: dict[str, list[str]] = {}
    for g, sp in sightings:
        by_ground.setdefault(g, []).append(sp)
    grounds = {}
    for g, seq in by_ground.items():
        est = chao1(Counter(seq))
        nov = novelty_rate(seq)
        grounds[g] = {**{k: round(v, 3) for k, v in est.items()}, **nov,
                      "state": classify(est, nov)}
    allseq = [sp for _g, sp in sightings]
    est_all = chao1(Counter(allseq))
    nov_all = novelty_rate(allseq)
    ranked = sorted(grounds.items(), key=lambda kv: -float(kv[1]["unseen"]))
    growth = None
    if rank_history and len(rank_history) >= 2:
        growth = round(float(rank_history[-1]) - float(rank_history[0]), 4)
    return {"overall": {**{k: round(v, 3) for k, v in est_all.items()}, **nov_all,
                        "state": classify(est_all, nov_all)},
            "grounds": dict(ranked[:40]),
            "most_unseen": [g for g, _v in ranked[:10]],
            "yield": yield_exponent(compute_series or [], survivor_series or []),
            "alpha_rank_growth": growth,
            "rule": "ranks where exploration still pays; never a licence to stop hunting"}

