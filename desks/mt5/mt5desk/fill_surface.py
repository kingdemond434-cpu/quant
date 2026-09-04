"""The learned Fusion execution surface: P(fill | state) for resting orders, E[slip | state] for
market ones, from the desk's own intents and deals.

    C = f(symbol, session hour, spread, vol, event, size, direction, order type)
    E[C | X],  Var(C | X)                     -- the cost posterior research and the allocator share
    P(fill | distance, spread, vol, hour)     -- for passive / limit entries

A COST MODEL THE RESEARCH AND THE ALLOCATOR SHARE. The gauntlet charges a modelled round trip;
the allocator carries `cost_r` with the world's cost-uncertainty draw; the gateway's markout
measures what was actually paid. Until this existed those three were three numbers. This fits
one surface on the markout rows and exposes it to all three, with the prior falling back to the
spread model when the box has not filled enough orders to fit anything -- and saying so.

NUMPY ONLY. A ridge regression on a small declared feature set for slippage, a logistic on the
same features for fills. Small, auditable, refit daily; a gradient-boosted surface can be a
challenger later, when there are enough fills for the complexity to pay rent.
"""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parent.parent
INTENTS = BASE / "data" / "order_intents.jsonl"
MARKOUT = BASE / "reports" / "markout.json"
OUT = BASE / "reports" / "FILL_SURFACE.json"
MIN_FILLS = 30
FEATURES = ("spread_frac", "vol", "hour_sin", "hour_cos", "size", "is_buy", "distance")


def _features(row: dict[str, Any]) -> np.ndarray | None:
    try:
        spread = float(row.get("spread_at_decision") or row.get("spread") or 0.0)
        price = float(row.get("intended") or row.get("price") or 0.0)
        vol = float(row.get("atr_frac") or row.get("vol") or 0.0)
        hour = float(datetime.fromisoformat(str(row.get("time"))).hour)
        lot = float(row.get("lot") or 0.0)
        side = str(row.get("side") or "")
        dist = float(row.get("distance_frac") or 0.0)
    except (TypeError, ValueError):
        return None
    if price <= 0:
        return None
    return np.array([spread / price, vol, math.sin(2 * math.pi * hour / 24.0),
                     math.cos(2 * math.pi * hour / 24.0), lot, 1.0 if side.startswith("buy")
                     else 0.0, dist], dtype=float)


def _ridge(x: np.ndarray, y: np.ndarray, lam: float = 1.0) -> np.ndarray:
    xb = np.column_stack([np.ones(x.shape[0]), x])
    a = xb.T @ xb + lam * np.eye(xb.shape[1])
    a[0, 0] -= lam
    return np.linalg.solve(a, xb.T @ y)


def _logistic(x: np.ndarray, y: np.ndarray, lam: float = 1.0, iters: int = 200) -> np.ndarray:
    xb = np.column_stack([np.ones(x.shape[0]), x])
    w = np.zeros(xb.shape[1])
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-xb @ w))
        g = xb.T @ (p - y) + lam * np.r_[0.0, w[1:]]
        h = (xb * (p * (1 - p))[:, None]).T @ xb + lam * np.eye(xb.shape[1])
        h[0, 0] -= lam
        step = np.linalg.solve(h, g)
        w -= step
        if np.max(np.abs(step)) < 1e-8:
            break
    return w


class FillSurface:
    def __init__(self) -> None:
        self.slip_w: np.ndarray | None = None
        self.slip_resid_sd: float = float("nan")
        self.fill_w: np.ndarray | None = None
        self.n_fills = 0
        #: Mean measured slip (fraction of price) over the fills the fit saw, and the mean of the
        #: half-spread prior on the same rows -- the cost term of the growth decomposition.
        self.mean_slip_measured: float | None = None
        self.mean_slip_modelled: float | None = None
        self.n_resting = 0
        self.note = "prior: spread model (no fitted surface)"

    def fit(self, rows: list[dict[str, Any]]) -> FillSurface:
        xs, ys = [], []
        fx, fy = [], []
        priors: list[float] = []
        for r in rows:
            f = _features(r)
            if f is None:
                continue
            if r.get("fill") is not None and r.get("intended") is not None:
                try:
                    slip = (float(r["fill"]) - float(r["intended"])) * \
                        (1.0 if str(r.get("side", "")).startswith("buy") else -1.0)
                    xs.append(f)
                    ys.append(slip / float(r["intended"]))
                    priors.append(0.5 * float(r.get("spread_at_decision") or 0.0)
                                  / float(r["intended"]))
                except (TypeError, ValueError, ZeroDivisionError):
                    pass
            if r.get("order_type") in ("limit", "pending_stop", "passive"):
                fx.append(f)
                fy.append(1.0 if r.get("filled") else 0.0)
        if ys:
            self.mean_slip_measured = float(np.mean(ys))
            self.mean_slip_modelled = float(np.mean(priors)) if priors else None
        if len(ys) >= MIN_FILLS:
            x = np.asarray(xs)
            y = np.asarray(ys)
            self.slip_w = _ridge(x, y)
            pred = np.column_stack([np.ones(x.shape[0]), x]) @ self.slip_w
            self.slip_resid_sd = float(np.std(y - pred, ddof=1))
            self.n_fills = len(ys)
            self.note = f"fitted on {len(ys)} fills"
        if len(fy) >= MIN_FILLS and 0 < sum(fy) < len(fy):
            self.fill_w = _logistic(np.asarray(fx), np.asarray(fy))
            self.n_resting = len(fy)
        return self

    def expected_slip(self, row: dict[str, Any], spread_frac_prior: float) -> tuple[float, float]:
        """E[slip | X] and its sd as fractions of price. Prior: half the spread, wide."""
        f = _features(row)
        if self.slip_w is None or f is None:
            return 0.5 * spread_frac_prior, spread_frac_prior
        mu = float(np.r_[1.0, f] @ self.slip_w)
        return mu, self.slip_resid_sd

    def p_fill(self, row: dict[str, Any]) -> float:
        """P(a resting order at `distance_frac` from the quote fills). Prior: exp(-d / spread)."""
        f = _features(row)
        if self.fill_w is None or f is None:
            try:
                d = float(row.get("distance_frac") or 0.0)
                s = float(row.get("spread_at_decision") or 0.0) / max(float(row.get("intended")
                                                                          or 1.0), 1e-9)
                return float(math.exp(-d / max(s, 1e-6))) if d > 0 else 1.0
            except (TypeError, ValueError):
                return 0.5
        z = float(np.r_[1.0, f] @ self.fill_w)
        return float(1.0 / (1.0 + math.exp(-z)))

    def to_dict(self) -> dict[str, Any]:
        return {"note": self.note, "n_fills": self.n_fills, "n_resting": self.n_resting,
                "mean_slip_measured": self.mean_slip_measured,
                "mean_slip_modelled": self.mean_slip_modelled,
                "features": list(FEATURES),
                "slip_w": (self.slip_w.tolist() if self.slip_w is not None else None),
                "slip_resid_sd": (self.slip_resid_sd if math.isfinite(self.slip_resid_sd)
                                  else None),
                "fill_w": (self.fill_w.tolist() if self.fill_w is not None else None)}


def _rows(path: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(ln) for ln in path.read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        return []


def run(write: bool = True) -> dict[str, Any]:
    """Fit the surface on the box's own markout-joined intents; report the posterior."""
    rows = _rows(INTENTS)
    try:
        mk = json.loads(MARKOUT.read_text("utf-8"))
        joined = {str(m.get("ticket")): m for m in (mk.get("rows") or []) if isinstance(m, dict)}
    except (OSError, ValueError):
        joined = {}
    for r in rows:
        j = joined.get(str(r.get("ticket")))
        if j:
            r.setdefault("fill", j.get("fill"))
    fs = FillSurface().fit(rows)
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "intents": len(rows),
           **fs.to_dict(),
           "gaps": ({} if fs.n_fills >= MIN_FILLS else
                    {"fills": f"{fs.n_fills} joined fills, need {MIN_FILLS}: the spread prior "
                              "stands for research and allocation"})}
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc
