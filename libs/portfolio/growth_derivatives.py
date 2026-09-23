"""WHERE THE NEXT BASIS POINT OF RISK CREATES THE MOST WEALTH -- exactly, not by re-solving.

    "Compute sleeve-level derivatives dG/dh_i, pairwise interaction d2G/dh_i dh_j, and
     factor-level derivatives. Then the allocator can literally answer: where does the next 10
     basis points of risk create the most wealth?"        -- the principal, 2026-09-07

THE DERIVATIVES ARE CLOSED FORM AND THE DESK WAS RE-SOLVING FOR THEM. For

    G(h) = E[ log(1 + h'r) ]        over the sampled worlds

the first two derivatives are exact and cost one pass over the same array the optimiser already
holds:

    dG/dh_i        = E[  r_i / (1 + h'r)        ]
    d2G/dh_i dh_j  = E[ -r_i r_j / (1 + h'r)^2  ]

No finite differences, no re-optimisation, no extra worlds. `pf_allocator.marginal_admission`
spends ~1.2s per candidate re-solving the whole book to learn something the gradient already
knows to first order, and the HESSIAN -- which says how two sleeves interact -- was not computed
at all.

WHAT THE HESSIAN IS ACTUALLY FOR, and it is not decoration. The gradient ranks sleeves by what
the next unit buys; the Hessian says how fast that stops being true and WHICH OTHER SLEEVE it
stops being true because of. A large negative off-diagonal H_ij means i and j compete: they load
the same thing, and buying one makes the other worse. A near-zero off-diagonal means they are
independent at the margin, which is the same statement `breadth_credit` makes from cluster
occupancy -- arrived at from the returns instead, so the two can be checked against each other.

THE SECOND-ORDER STEP IS THE ANSWER TO THE QUESTION AS ASKED. "The next 10 basis points" is a
FINITE step, and a gradient ranking is only right in the limit. The gain from adding delta to
sleeve i is

    dG_i(delta) = delta * g_i + (1/2) * delta^2 * H_ii

and a sleeve with a big gradient and a violently negative curvature can rank first on the
gradient and second on the actual step. `best_next` ranks on the step the caller is really
proposing to take.

WHY THE HESSIAN IS NEGATIVE SEMI-DEFINITE, which is worth knowing because it is a check on the
arithmetic rather than an assumption: H = -E[ (r r') / (1 + h'r)^2 ] is minus the expectation of
an outer product, so v'Hv = -E[ (v'r)^2 / (1+h'r)^2 ] <= 0 for every v. A positive eigenvalue
means the inputs are broken, and `curvature_ok` says so rather than letting a caller step uphill
on a concave surface.

RUIN IS REFUSED, NOT CLIPPED. Where 1 + h'r <= 0 the log is undefined and the derivative is
meaningless; a world containing such a row is dropped from the expectation and COUNTED. Clipping
the denominator to a small positive number would manufacture an enormous finite derivative out of
a wipeout, which is the most dangerous possible direction for a number that ranks where to add
risk.

NOTHING HERE SIZES. It differentiates a function of a book somebody else solved.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

__all__ = [
    "MIN_ROWS",
    "best_next",
    "derivatives",
]

MEASURED, UNMEASURED = "MEASURED", "UNMEASURED"

#: Usable (world, row) pairs the expectation needs before a derivative is a measurement. A
#: gradient averaged over a handful of rows ranks sleeves by which one got lucky.
MIN_ROWS = 200


def derivatives(r: np.ndarray, h: np.ndarray, *, names: Sequence[str] | None = None,
                min_rows: int = MIN_ROWS) -> dict[str, Any]:
    """Exact first and second derivatives of E[log(1 + h'r)] at `h`.

    `r` is the return array -- (worlds, rows, sleeves) or (rows, sleeves) -- and `h` the book's
    per-sleeve heat in the same sleeve order. Returns the gradient, the Hessian, the concavity
    check, and every row the expectation had to drop.
    """
    arr = np.asarray(r, dtype="float64")
    if arr.ndim == 3:
        arr = arr.reshape(-1, arr.shape[-1])
    if arr.ndim != 2:
        return {"status": UNMEASURED, "why": f"returns of shape {np.shape(r)} are not a panel"}
    x = np.asarray(h, dtype="float64").reshape(-1)
    if x.size != arr.shape[1]:
        return {"status": UNMEASURED,
                "why": f"book of {x.size} sleeves against {arr.shape[1]} return columns"}
    nm = list(names) if names is not None else [str(i) for i in range(x.size)]

    port = arr @ x
    denom = 1.0 + port
    # RUIN IS DROPPED, NEVER CLIPPED. Clipping 1 + h'r to a small epsilon turns a wipeout into an
    # enormous finite derivative pointing at whichever sleeve caused it -- a number that ranks
    # where to ADD risk, produced by the world where the book died.
    ok = np.isfinite(denom) & (denom > 1e-12) & np.all(np.isfinite(arr), axis=1)
    n_ok = int(ok.sum())
    n_ruined = int(arr.shape[0] - n_ok)
    if n_ok < int(min_rows):
        return {"status": UNMEASURED, "n_rows": int(arr.shape[0]), "n_usable": n_ok,
                "n_ruined": n_ruined,
                "why": (f"{n_ok} usable rows against a {min_rows} floor; a gradient averaged over "
                        "this many rows ranks sleeves by which one got lucky")}

    a = arr[ok]
    d = denom[ok]
    inv = 1.0 / d
    grad = (a * inv[:, None]).mean(axis=0)
    # H = -E[ r r' / (1+h'r)^2 ]. Formed as a scaled Gram matrix so it is one matmul rather than
    # an n^2 loop, and symmetric by construction rather than by hope.
    w = inv * inv
    hess = -(a * w[:, None]).T @ a / float(a.shape[0])
    hess = 0.5 * (hess + hess.T)

    try:
        eig = np.linalg.eigvalsh(hess)
        max_eig = float(eig.max())
    except np.linalg.LinAlgError:
        max_eig = float("nan")
    # v'Hv = -E[(v'r)^2 / (1+h'r)^2] <= 0 for every v, so a positive eigenvalue is an INPUT
    # defect. The tolerance is relative to the matrix scale: floating point noise on a matrix
    # whose entries are 1e-3 is not a concavity violation.
    scale = float(np.abs(hess).max()) or 1.0
    curvature_ok = bool(math.isfinite(max_eig) and max_eig <= 1e-9 * scale)

    g = {n: float(v) for n, v in zip(nm, grad, strict=True)}
    diag = {n: float(hess[i, i]) for i, n in enumerate(nm)}
    return {
        "status": MEASURED, "names": nm,
        "growth": float(np.log(d).mean()),
        "gradient": g, "hessian_diag": diag,
        "hessian": [[float(v) for v in row] for row in hess],
        "n_rows": int(arr.shape[0]), "n_usable": n_ok, "n_ruined": n_ruined,
        "curvature_ok": curvature_ok, "max_eigenvalue": max_eig,
        "why": (f"exact dG/dh and d2G/dh dh over {n_ok} usable rows"
                + (f"; {n_ruined} row(s) dropped where 1 + h'r <= 0" if n_ruined else "")
                + ("" if curvature_ok else
                   f"; CONCAVITY VIOLATED (max eigenvalue {max_eig:+.3g}) -- the Hessian of a log "
                   "objective cannot be positive definite, so the inputs are broken and this "
                   "ranking must not be stepped on")),
    }


def best_next(d: Mapping[str, Any], delta: float = 0.001, *,
              cap: Mapping[str, float] | None = None,
              held: Mapping[str, float] | None = None) -> dict[str, Any]:
    """Where the next `delta` of heat buys the most growth, to SECOND order.

    "The next 10 basis points" is a finite step and a gradient ranking is only exact in the limit,
    so each sleeve is scored on the step actually proposed:

        dG_i(delta) = delta * g_i + (1/2) * delta^2 * H_ii

    A sleeve with a large gradient and violent curvature ranks first on the gradient and second on
    the step -- which is the entire reason to compute the Hessian rather than sort the gradient.

    `cap` bounds each sleeve's total heat and `held` says what it already holds; a sleeve with no
    room for the step is EXCLUDED rather than ranked, because a ranking whose top entry cannot be
    acted on is not an answer to the question.
    """
    if d.get("status") != MEASURED:
        return {"status": UNMEASURED, "why": d.get("why", "no derivatives")}
    if not d.get("curvature_ok"):
        return {"status": UNMEASURED,
                "why": ("the Hessian is not negative semi-definite, so the second-order step is "
                        "not a bound on anything: " + str(d.get("why", "")))}
    step = float(delta)
    g = d["gradient"]
    hd = d["hessian_diag"]
    rows: list[dict[str, Any]] = []
    blocked: dict[str, str] = {}
    for n in d["names"]:
        room = math.inf
        if cap is not None:
            room = float(cap.get(n, math.inf)) - float((held or {}).get(n, 0.0))
        if room < step - 1e-15:
            blocked[n] = f"only {max(room, 0.0):.4%} of room against a {step:.2%} step"
            continue
        gain = step * float(g[n]) + 0.5 * step * step * float(hd[n])
        rows.append({"sleeve": n, "gain_per_day": gain, "gradient": float(g[n]),
                     "curvature": float(hd[n]),
                     # Where the linear ranking and the real step disagree, that disagreement IS
                     # the finding: it is exactly the sleeve whose marginal value collapses
                     # fastest, and the one a gradient sort would over-buy.
                     "linear_gain": step * float(g[n])})
    rows.sort(key=lambda r: -r["gain_per_day"])
    lin = sorted(rows, key=lambda r: -r["linear_gain"])
    disagree = bool(rows and lin and rows[0]["sleeve"] != lin[0]["sleeve"])
    return {
        "status": MEASURED, "delta": step, "ranked": rows,
        "best": (rows[0]["sleeve"] if rows else ""),
        "best_gain_per_day": (rows[0]["gain_per_day"] if rows else 0.0),
        "linear_best": (lin[0]["sleeve"] if lin else ""),
        "second_order_changes_the_answer": disagree,
        "blocked": blocked,
        "why": (f"second-order gain from adding {step:.2%} to each sleeve, ranked"
                + (f"; the gradient alone would have chosen {lin[0]['sleeve']} and the step says "
                   f"{rows[0]['sleeve']}" if disagree else "")
                + (f"; {len(blocked)} sleeve(s) have no room for the step" if blocked else "")),
    }
