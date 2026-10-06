"""ADAPTIVE-INFERENCE ACCOUNTING (Tier S layer 11): online FDR over the desk's lifetime stream.

The desk chooses what to test next from what it has already seen, so its tests do not arrive as
one pre-declared family. A fixed Bonferroni/DSR charge per campaign treats each campaign as if it
were the first; an online procedure spends ONE lifetime error budget across the whole ordered
stream and stays valid when the next test was chosen because of the last result.

    LORD++   (Ramdas, Yang, Wainwright, Jordan 2017) -- valid under independence / PRDS; the
             test level earns wealth back on each discovery
    e-LOND   (Xu & Ramdas 2024) -- takes e-values and is valid under ARBITRARY dependence, which
             is the honest assumption for a desk whose candidates share bars, families and
             parents

Both are pure functions of the ordered stream: `replay()` reproduces every level the desk would
have used at every point in its history, so a certificate issued under a level the lifetime budget
could not afford is visible as `over_budget`. p-values are converted to e-values with the
calibrator e = kappa * p^(kappa-1) (kappa in (0,1)), which is admissible and needs no model.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

DEFAULT_ALPHA = 0.05


def gamma_seq(n: int) -> list[float]:
    """The LORD++ default spending sequence, normalised to sum to 1 over a long horizon."""
    raw = [math.log(max(j, 2)) / (j * math.exp(math.sqrt(math.log(j)))) for j in
           range(1, max(n, 1) + 1)]
    # normaliser computed over a long fixed horizon so levels do not depend on stream length
    horizon = 1_000_000
    z = 0.0
    j = 1
    while j <= horizon:
        step = 1 if j < 10_000 else 97
        z += step * math.log(max(j, 2)) / (j * math.exp(math.sqrt(math.log(j))))
        j += step
    return [g / z for g in raw]


_GAMMA_CACHE: list[float] = []


def _gamma(n: int) -> list[float]:
    global _GAMMA_CACHE
    if len(_GAMMA_CACHE) < n:
        _GAMMA_CACHE = gamma_seq(max(n, 2 * len(_GAMMA_CACHE), 1024))
    return _GAMMA_CACHE[:n]


@dataclass(frozen=True)
class Test:
    test_id: str
    at: str
    p: float | None = None
    e: float | None = None
    family: str = ""
    #: was this test acted on (certified) by the desk's own fixed gates?
    certified: bool = False


def p_to_e(p: float, kappa: float = 0.5) -> float:
    p = min(max(p, 1e-300), 1.0)
    return float(kappa * p ** (kappa - 1.0))


def lord_pp(ps: Sequence[float], alpha: float = DEFAULT_ALPHA, w0: float | None = None
            ) -> tuple[list[float], list[bool]]:
    w0 = alpha / 2 if w0 is None else w0
    n = len(ps)
    g = _gamma(n + 1)
    levels: list[float] = []
    rej: list[bool] = []
    taus: list[int] = []
    for t in range(1, n + 1):
        a = g[t - 1] * w0
        if taus:
            a += (alpha - w0) * g[t - taus[0] - 1]
            a += alpha * sum(g[t - tj - 1] for tj in taus[1:])
        levels.append(a)
        r = ps[t - 1] <= a
        rej.append(r)
        if r:
            taus.append(t)
    return levels, rej


def e_lond(es: Sequence[float], alpha: float = DEFAULT_ALPHA) -> tuple[list[float], list[bool]]:
    n = len(es)
    g = _gamma(n)
    levels: list[float] = []
    rej: list[bool] = []
    r_count = 0
    for t in range(n):
        a = alpha * g[t] * (r_count + 1)
        levels.append(a)
        ok = es[t] >= 1.0 / a if a > 0 else False
        rej.append(ok)
        r_count += int(ok)
    return levels, rej


def replay(tests: Iterable[Test], alpha: float = DEFAULT_ALPHA) -> dict[str, Any]:
    """Run the lifetime stream (sorted by time) through both procedures."""
    ordered = sorted(tests, key=lambda t: (t.at, t.test_id))
    ps = [1.0 if t.p is None else min(max(float(t.p), 0.0), 1.0) for t in ordered]
    es = [float(t.e) if t.e is not None else p_to_e(p) for t, p in zip(ordered, ps,
                                                                        strict=True)]
    l_lev, l_rej = lord_pp(ps, alpha)
    e_lev, e_rej = e_lond(es, alpha)
    rows = []
    over = 0
    for i, t in enumerate(ordered):
        admitted = l_rej[i] or e_rej[i]
        if t.certified and not admitted:
            over += 1
        rows.append({"test_id": t.test_id, "at": t.at, "family": t.family, "p": ps[i],
                     "e": es[i], "lord_level": l_lev[i], "lord_reject": l_rej[i],
                     "elond_level": e_lev[i], "elond_reject": e_rej[i],
                     "certified": t.certified, "over_budget": t.certified and not admitted})
    n_cert = sum(1 for t in ordered if t.certified)
    return {"alpha": alpha, "n_tests": len(ordered), "lord_discoveries": sum(l_rej),
            "elond_discoveries": sum(e_rej), "certified": n_cert, "over_budget": over,
            "over_budget_share": (over / n_cert) if n_cert else None,
            "next_level": {"lord": (lord_pp([*ps, 1.0], alpha)[0][-1]) if ps else alpha / 2,
                           "elond": (e_lond([*es, 0.0], alpha)[0][-1]) if es else alpha},
            "rows": rows}


def charge_null_fpr(tests: Iterable[Test], charges: Mapping[str, float]
                    ) -> tuple[list[Test], dict[str, Any]]:
    """Each test's p multiplied by its FAMILY's measured null false-positive charge.

    THE HONEST PRICE OF AN EASY GATE. `desks/mt5/research/null_lab.py` runs every hunted family's
    own cell builder on block-shuffled, random-walk and sign-permuted data and measures how often
    the deflated-Sharpe gate passes where no edge can exist. A family that passes its null at 15%
    against a nominal 5% has a p-value that is three times too small, so its p is multiplied by
    `charge` = posterior null rate / nominal (never below 1, capped at p = 1) BEFORE the lifetime
    replay -- it spends more alpha-wealth per test and a certificate that could no longer afford
    its level reads `over_budget`. A test that already carries an e-value is divided by the same
    charge (an e-value is a likelihood ratio against the null the lab just showed is easier).

    A family with no charge (unmeasured, or at or below nominal) is untouched, so this can only
    tighten the stream it is given."""
    out: list[Test] = []
    touched: dict[str, int] = {}
    for t in tests:
        c = float(charges.get(t.family, 1.0) or 1.0)
        if c <= 1.0 or not t.family:
            out.append(t)
            continue
        p = None if t.p is None else min(1.0, float(t.p) * c)
        e = None if t.e is None else float(t.e) / c
        out.append(Test(test_id=t.test_id, at=t.at, p=p, e=e, family=t.family,
                        certified=t.certified))
        touched[t.family] = touched.get(t.family, 0) + 1
    return out, {"families_charged": dict(sorted(touched.items())),
                 "tests_charged": sum(touched.values()),
                 "charges": {f: float(charges[f]) for f in sorted(touched)}}


def tests_from_survivors(survivors: Mapping[str, Any]) -> list[Test]:
    """Certificates in UNIVERSAL_SURVIVORS carry their gates; draw a p per certificate from the
    reality-check p when present, else 1 - DSR (the DSR is a probability the Sharpe exceeds the
    selection-adjusted benchmark)."""
    out: list[Test] = []
    for key, row in survivors.items():
        if not isinstance(row, Mapping):
            continue
        gates = row.get("gates") or {}
        p: float | None = None
        spa = gates.get("reality_check_spa") or {}
        if isinstance(spa, Mapping) and spa.get("p_value") is not None:
            p = float(spa["p_value"])
        dsr = gates.get("deflated_sharpe") or {}
        if isinstance(dsr, Mapping) and dsr.get("dsr") is not None:
            pd_ = max(0.0, 1.0 - float(dsr["dsr"]))
            p = pd_ if p is None else max(p, pd_)
        out.append(Test(test_id=str(key), at=str(row.get("gated_at") or ""), p=p,
                        family=str((row.get("shadow_spec") or {}).get("family") or ""),
                        certified=True))
    return out
