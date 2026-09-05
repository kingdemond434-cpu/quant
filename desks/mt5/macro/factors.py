"""WHAT AN EVENT TOUCHES, LEARNED -- the factor basis and the category->factor edges.

TWO HARDCODINGS AVOIDED, NOT ONE.

The obvious one is the mapping: "Middle East -> gold up" must not be a table. Less obvious and
just as damaging is hardcoding the FACTORS THEMSELVES. If someone writes down that the world has
a dollar factor, a real-rates factor and a risk factor, then an event that moves a fourth thing
-- a shipping-cost factor, a regional-credit factor, whatever the market is actually trading that
year -- has nowhere to land and is recorded as touching nothing. So the basis here is DISCOVERED
from the covariance of the desk's own instrument returns, and each factor is named after its own
top loadings (`F1[+XAUUSD,+XAGUSD,-USDX]`) rather than after a story. The names are descriptions
of the measurement, not interpretations of it.

THE EDGES ARE MEASURED AND ADMITTED, NOT ASSERTED. For each category, the loading on each factor
is the mean measured factor response across that category's instances, with a bootstrap standard
error. An edge is ADMITTED only when its interval -- widened by a Bonferroni charge over EVERY
(category, factor) cell the desk has ever tested -- excludes zero, and only when n reaches
`ledger.MIN_CATEGORY_N`. Everything else is RECORDED_NOT_ADMITTED with the reason on the edge.

WHY THE MULTIPLICITY LEDGER MUST NEVER SHRINK, in this module specifically. Event conditioning is
the single most fertile source of false discovery on this desk: categories times factors times
horizons times regimes is thousands of cells, and at a five-percent level thousands of cells
produce dozens of beautiful, meaningless edges. The charge is persisted to disk, it counts cells
ever tested rather than cells tested this pass, and re-running the estimator makes admission
HARDER rather than easier. That is the intended incentive: a desk that keeps re-testing until
something passes should find the bar rising as it does.

THIS IS THE SAME DOCTRINE `libs/research/causal_graph.py` USES, deliberately. That module charges
every (pair, lag) cell and widens its block-bootstrap interval by the charge; this one charges
every (category, factor) cell. Two organs measuring different things with one standard of
evidence is worth more than two clever standards.

A FACTOR RESPONSE IS AN OBSERVATION OF THE EVENT WINDOW, and `surprise.py` takes its SIGN from
here. Nothing in this module knows what a category means; it knows what happened when instances
of it arrived.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import NormalDist
from typing import Any

from .ledger import MACRO_DIR, MIN_CATEGORY_N, write_json_atomic
from .prices import PriceReader, move_sigma
from .schema import FactorLoading, Status, now_iso

BASIS_PATH = MACRO_DIR / "factor_basis.json"
MULTIPLICITY_PATH = MACRO_DIR / "multiplicity.json"

#: Two-sided level BEFORE the multiplicity charge. Never raised to admit an edge.
ALPHA = 0.05

#: Bootstrap resamples for the standard error. Enough that the SE is stable to two decimals;
#: the interval itself is a normal approximation ON that SE rather than a raw percentile,
#: because at a Bonferroni-widened level the required percentile lands in the tail where a
#: two-thousand-draw bootstrap has no resolution.
BOOTSTRAP_B = 2000

#: Aligned observations required before a factor basis is fitted at all.
MIN_BASIS_OBS = 250

#: Instruments required before a basis is meaningful. Below this the "factors" are just the
#: instruments wearing different names.
MIN_BASIS_SYMBOLS = 5

__all__ = [
    "ALPHA",
    "MIN_BASIS_OBS",
    "FactorBasis",
    "MultiplicityLedger",
    "category_loadings",
    "factor_basis",
    "measure_response",
]


class MultiplicityLedger:
    """Monotone count of every (category, factor) cell ever tested. It only goes up."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else MULTIPLICITY_PATH
        self.cells: dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text("utf-8"))
        except (OSError, ValueError):
            return
        cells = raw.get("cells")
        if isinstance(cells, dict):
            self.cells = {str(k): int(v) for k, v in cells.items()}

    def charge(self, category: str, factor: str) -> None:
        key = f"{category}|{factor}"
        self.cells[key] = self.cells.get(key, 0) + 1

    @property
    def total(self) -> int:
        """Distinct cells ever charged. The Bonferroni denominator -- distinct cells, not total
        tests, so honest re-measurement of the same edge is not punished twice while EXPLORING a
        new cell always is."""
        return max(1, len(self.cells))

    def save(self) -> None:
        write_json_atomic(self.path, {
            "at": now_iso(), "distinct_cells": self.total, "cells": self.cells,
            "note": ("Never shrinks. Re-running the estimator widens every admission interval; "
                     "an edge cannot be admitted by being tested again."),
        })


@dataclass(frozen=True)
class FactorBasis:
    """Factors discovered from the return covariance, named by their own top loadings."""

    symbols: tuple[str, ...]
    #: factor id -> {symbol: loading}
    loadings: dict[str, dict[str, float]]
    explained: dict[str, float]
    n_obs: int
    status: str
    note: str = ""

    def project(self, moves: Mapping[str, float]) -> dict[str, float]:
        """Project a per-symbol move vector (in sigma) onto the factors.

        Symbols the basis does not contain are IGNORED rather than treated as zero: a zero would
        assert the instrument did not move, when the truth is that the desk did not look.
        """
        out: dict[str, float] = {}
        for fid, load in self.loadings.items():
            num = 0.0
            den = 0.0
            for sym, w in load.items():
                v = moves.get(sym)
                if v is None or not math.isfinite(float(v)):
                    continue
                num += w * float(v)
                den += w * w
            if den > 0:
                out[fid] = round(num / math.sqrt(den), 6)
        return out

    def to_dict(self) -> dict[str, Any]:
        return {"symbols": list(self.symbols), "loadings": self.loadings,
                "explained": self.explained, "n_obs": self.n_obs, "status": self.status,
                "note": self.note, "at": now_iso()}


def _name(fid: int, load: Mapping[str, float]) -> str:
    top = sorted(load.items(), key=lambda kv: -abs(kv[1]))[:3]
    body = ",".join(f"{'+' if w >= 0 else '-'}{s}" for s, w in top)
    return f"F{fid + 1}[{body}]"


def factor_basis(panel: Mapping[str, Sequence[float]], *, k: int = 4) -> FactorBasis:
    """Fit factors from an aligned panel of instrument returns. Refuses on thin data.

    Standardised before decomposition so a high-vol instrument does not become factor one by
    virtue of being loud. Signs are canonicalised (largest loading positive) so the same data
    gives the same factor names every run -- otherwise a replay's factor deltas would flip sign
    between runs for no reason.
    """
    syms = sorted(s for s, v in panel.items() if len(v) >= MIN_BASIS_OBS)
    if len(syms) < MIN_BASIS_SYMBOLS:
        return FactorBasis((), {}, {}, 0, Status.UNMEASURED,
                           f"{len(syms)} symbols with >= {MIN_BASIS_OBS} obs "
                           f"< MIN_BASIS_SYMBOLS={MIN_BASIS_SYMBOLS}")
    n = min(len(panel[s]) for s in syms)
    if n < MIN_BASIS_OBS:
        return FactorBasis((), {}, {}, n, Status.UNMEASURED,
                           f"n={n} aligned obs < MIN_BASIS_OBS={MIN_BASIS_OBS}")
    try:
        import numpy as np
    except ImportError:
        return FactorBasis((), {}, {}, 0, Status.UNMEASURED, "numpy unavailable")
    mat = np.array([list(panel[s])[-n:] for s in syms], dtype=float).T
    mat = mat[np.isfinite(mat).all(axis=1)]
    if mat.shape[0] < MIN_BASIS_OBS:
        return FactorBasis((), {}, {}, int(mat.shape[0]), Status.UNMEASURED,
                           "too few finite rows after cleaning")
    mat = mat - mat.mean(axis=0)
    sd = mat.std(axis=0, ddof=1)
    keep = sd > 0
    if int(keep.sum()) < MIN_BASIS_SYMBOLS:
        return FactorBasis((), {}, {}, int(mat.shape[0]), Status.UNMEASURED,
                           "too few instruments with non-zero variance")
    syms = [s for s, ok in zip(syms, keep, strict=True) if ok]
    mat = mat[:, keep] / sd[keep]
    _u, s_vals, vt = np.linalg.svd(mat, full_matrices=False)
    kk = int(min(k, vt.shape[0]))
    var = (s_vals ** 2)
    total = float(var.sum()) or 1.0
    loadings: dict[str, dict[str, float]] = {}
    explained: dict[str, float] = {}
    for i in range(kk):
        vec = vt[i]
        j = int(np.argmax(np.abs(vec)))
        if vec[j] < 0:
            vec = -vec
        load = {sym: round(float(w), 6) for sym, w in zip(syms, vec, strict=True)}
        fid = _name(i, load)
        loadings[fid] = load
        explained[fid] = round(float(var[i]) / total, 4)
    return FactorBasis(tuple(syms), loadings, explained, int(mat.shape[0]), Status.MEASURED,
                       "discovered from the desk's own return covariance; names describe the "
                       "measurement, they do not interpret it")


def measure_response(reader: PriceReader, basis: FactorBasis, *, t0: datetime,
                     t1: datetime) -> tuple[dict[str, float], dict[str, str]]:
    """Observed factor move over [t0, t1], plus the per-symbol reasons any of it was missing."""
    moves: dict[str, float] = {}
    gaps: dict[str, str] = {}
    for sym in basis.symbols:
        val, why = move_sigma(reader, sym, t0, t1)
        if val is None:
            gaps[sym] = why
        else:
            moves[sym] = val
    return basis.project(moves), gaps


def _bootstrap_se(sample: Sequence[float], b: int = BOOTSTRAP_B, seed: int = 0) -> float | None:
    if len(sample) < 3:
        return None
    try:
        import numpy as np
    except ImportError:
        return None
    rng = np.random.default_rng(seed)
    arr = np.asarray(sample, dtype=float)
    draws = rng.integers(0, arr.size, size=(b, arr.size))
    means = arr[draws].mean(axis=1)
    se = float(means.std(ddof=1))
    return se if se > 0 and math.isfinite(se) else None


def category_loadings(samples: Mapping[str, Sequence[float]], *, category: str,
                      ledger: MultiplicityLedger, min_n: int = MIN_CATEGORY_N,
                      seed: int = 0) -> list[FactorLoading]:
    """Admit or refuse each category->factor edge. `samples` is factor id -> per-instance moves.

    Every cell is CHARGED before it is measured, so a test that is run is a test that is paid
    for whether or not it produces an edge. Charging only on success is how a multiplicity
    ledger becomes decorative.
    """
    for fid in samples:
        ledger.charge(category, fid)
    cells = ledger.total
    # Bonferroni over distinct cells ever charged. NormalDist on the bootstrap SE rather than a
    # raw bootstrap percentile: at alpha/cells the required percentile is far into the tail,
    # where a 2000-draw bootstrap has no resolution and would report an interval narrower than
    # its own sampling noise.
    z_crit = NormalDist().inv_cdf(1.0 - ALPHA / (2.0 * cells))
    out: list[FactorLoading] = []
    for fid, vals in sorted(samples.items()):
        clean = [float(v) for v in vals if isinstance(v, int | float) and math.isfinite(float(v))]
        n = len(clean)
        if n < min_n:
            out.append(FactorLoading(fid, 0.0, 0.0, 0.0, n, cells, False, Status.UNMEASURED,
                                     f"n={n} < MIN_CATEGORY_N={min_n}"))
            continue
        mean = sum(clean) / n
        se = _bootstrap_se(clean, seed=seed)
        if se is None:
            out.append(FactorLoading(fid, round(mean, 6), 0.0, 0.0, n, cells, False,
                                     Status.UNMEASURED, "bootstrap standard error unavailable"))
            continue
        lo, hi = mean - z_crit * se, mean + z_crit * se
        admitted = (lo > 0.0) or (hi < 0.0)
        out.append(FactorLoading(
            fid, round(mean, 6), round(lo, 6), round(hi, 6), n, cells, admitted,
            Status.MEASURED if admitted else Status.RECORDED_ONLY,
            "" if admitted else (f"interval [{lo:.4f}, {hi:.4f}] includes zero at "
                                 f"alpha={ALPHA}/{cells} cells -- RECORDED_NOT_ADMITTED")))
    return out


def save_basis(basis: FactorBasis, path: Path | str | None = None) -> None:
    write_json_atomic(Path(path) if path is not None else BASIS_PATH, basis.to_dict())


def load_basis(path: Path | str | None = None) -> FactorBasis:
    p = Path(path) if path is not None else BASIS_PATH
    if not p.exists():
        return FactorBasis((), {}, {}, 0, Status.UNMEASURED, "no basis fitted yet")
    try:
        raw = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return FactorBasis((), {}, {}, 0, Status.UNMEASURED, "basis file unreadable")
    return FactorBasis(
        tuple(raw.get("symbols") or ()),
        {k: {s: float(w) for s, w in v.items()} for k, v in (raw.get("loadings") or {}).items()},
        {k: float(v) for k, v in (raw.get("explained") or {}).items()},
        int(raw.get("n_obs", 0)), str(raw.get("status", Status.UNMEASURED)),
        str(raw.get("note", "")))
