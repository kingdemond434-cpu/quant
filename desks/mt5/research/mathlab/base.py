"""The shared scientist interface and the numerics every tradition leans on.

Split out of `scientists.py` so that the second cohort of traditions (`scientists_ext.py`) can
share one base class without a circular import. Nothing here knows any tradition by name.
"""
from __future__ import annotations

import time
from typing import Any

import numpy as np

from . import grammar as G
from .objects import MathObject, Panel, Variable

UNMEASURED = "UNMEASURED"
#: Points above which a pairwise computation is subsampled. Sized for the 8 GB box, not a claim.
CLOUD_CAP = 420
MIN_ROWS = 400


def _quiet() -> Any:
    """`grammar.quiet`, re-exported so every tradition suppresses in exactly one place."""
    return G.quiet()


def _finite(values: np.ndarray) -> np.ndarray:
    out = np.asarray(values, dtype=float).copy()
    bad = ~np.isfinite(out)
    if bad.any():
        out[bad] = 0.0
    return out


def _z(values: np.ndarray) -> np.ndarray:
    v = _finite(values)
    sd = float(np.std(v))
    return (v - float(np.mean(v))) / sd if sd > 1e-12 else np.zeros_like(v)


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    x, y = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    if int(mask.sum()) < 16:
        return 0.0
    x, y = x[mask], y[mask]
    if float(np.std(x)) < 1e-12 or float(np.std(y)) < 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def _nearest_window(value: float) -> int:
    """The legal window closest to a number the numerics produced."""
    return int(min(G.WINDOWS, key=lambda w: abs(w - float(value))))


class Scientist:
    """The shared interface. Subclasses implement `_propose`; this class does the bookkeeping."""

    tradition: str = ""
    #: What this tradition is FOR, in the principal's five-way vocabulary.
    searches_for: tuple[str, ...] = ("relationship",)

    def __init__(self) -> None:
        self.unmeasured: list[str] = []
        self.evaluated: int = 0
        self.distinct: set[str] = set()
        self.minted: list[str] = []

    # ------------------------------------------------------------------ bookkeeping helpers
    def note(self, what: str, why: str) -> None:
        """Name what could not be measured, and what WOULD measure it."""
        self.unmeasured.append(f"{what}: {why}")

    def charge(self, tree: Any) -> None:
        """One evaluated hypothesis. Distinct CANONICAL forms are what the burden charges."""
        self.evaluated += 1
        self.distinct.add(G.to_str(G.simplify(tree)))

    def emit(self, panel: Panel, kind: str, tree: Any, statement: str, *,
             side_mode: str = "follow", diagnostics: dict[str, Any] | None = None,
             notes: list[str] | None = None) -> MathObject | None:
        """Build one object, charging it, or None when the expression cannot be evaluated."""
        self.charge(tree)
        obj = MathObject(kind=kind, tradition=self.tradition, expression=tree,
                         target=panel.target, horizon=panel.horizon, side_mode=side_mode,
                         statement=statement, diagnostics=dict(diagnostics or {}),
                         notes=list(notes or []))
        values = G.evaluate(obj.expression, panel.columns, panel.n)
        if not np.isfinite(values).any():
            self.note(f"object {obj.canonical}", "evaluates to NaN throughout on this panel")
            return None
        obj.variables = [panel.meta.get(name, Variable(name=name, dataset=name, source="derived"))
                         for name in sorted(G.variables_in(obj.expression))]
        return obj

    def propose(self, panel: Panel, budget_s: float, rng: np.random.Generator
                ) -> list[MathObject]:
        """Run this tradition over one panel under a wall-clock budget. Never raises."""
        self.unmeasured = []
        self.evaluated = 0
        self.distinct = set()
        self.minted = []
        if panel.n < MIN_ROWS:
            self.note("panel", f"{panel.n} rows, fewer than the named minimum {MIN_ROWS}; "
                               f"a longer residual store would measure it")
            return []
        deadline = time.monotonic() + max(1.0, float(budget_s))
        out = self._propose(panel, deadline, rng)
        return [o for o in out if o is not None]

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:                      # pragma: no cover - abstract
        raise NotImplementedError

    # ------------------------------------------------------------------- shared numerics
    def top_columns(self, panel: Panel, k: int = 10) -> list[str]:
        """Columns ranked by |corr| with the residual on the training slice. Bars break ties."""
        train, _ = panel.split()
        if train.size < 32:
            return panel.names[:k]
        scored = [(abs(_corr(panel.columns[c][train], panel.epsilon[train])), c)
                  for c in panel.names]
        scored.sort(key=lambda r: (-r[0], r[1]))
        return [c for _, c in scored[:k]]

    def bar_columns(self, panel: Panel) -> list[str]:
        return [c for c in G.BAR_VARIABLES if c in panel.columns]

    def projection(self, panel: Panel, window: int, *, fast: int | None = None,
                   side_mode: str = "follow", why: str = "") -> tuple[Any, list[str]]:
        """The executable projection: a bar-only expression whose parameters THIS tradition chose.

        Momentum over `fast` bars scaled by the residual volatility state over `window` bars --
        the two numbers are the tradition's own output, and `why` records which measurement set
        them. `tradeable()` decides whether it may be donated; nothing is approximated silently.
        """
        bars = self.bar_columns(panel)
        base = "close" if "close" in bars else (bars[0] if bars else "close")
        scale = "range" if "range" in bars else base
        fast_w = _nearest_window(fast if fast is not None else max(2, window // 4))
        tree = ["mul", ["sign", ["diff", base, fast_w]], ["z", scale, _nearest_window(window)]]
        note = (f"executable projection: the {self.tradition} object reads a state variable the "
                f"formula family cannot be handed, so the donated recipe is momentum over "
                f"{fast_w} bars gated by the {_nearest_window(window)}-bar dispersion state. "
                f"{why}".strip())
        _ = side_mode
        return tree, [note]
