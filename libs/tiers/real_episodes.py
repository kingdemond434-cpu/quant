"""THE REAL-EPISODE META-BENCHMARK (Tier S layer 34's second suite, 2026-09-30).

The sealed suite (`libs/tiers/meta_benchmark.py`) plants every trap and every genuine edge on
GAUSSIAN noise. A validator can pass it and still be fooled by what Gaussian noise never has:
volatility clustering, fat tails, weekend gaps, the hour-of-day vol profile, the zero-return runs
of a quiet feed. This suite plants the SAME kinds on the desk's own H1 bars.

THE GROUND TRUTH HAS TO SURVIVE THE REAL PATH, so each case starts from a real episode made
DIRECTION-FREE: a window of one instrument's actual H1 log returns, rescaled to the synthetic
suite's sigma (so the kinds' edge-to-cost ratios mean the same thing in both suites) and with
each return's sign flipped by an independent fair coin. The flip keeps every magnitude -- the
clustering, the tails, the gaps, the intraday profile all stay exactly as the market printed
them -- and destroys any directional predictability the real path had, so "this case has no
edge" is TRUE by construction and a planted edge is the only edge there is. Without the flip a
trap on a real trending episode could carry a genuine edge and its label would be a guess.

Every kind of the synthetic suite is built here by the same recipe with the real innovations in
place of `rng.normal(0, sigma)`; the cross-sectional kinds (survivorship, duplicate_factor) draw
their universe and factor from OTHER real instruments' episodes. `RealSuite.seal()` hashes this
module's source, the seeds, the episode identities and every case's price bytes, so a changed
input set is a changed seal, never a silently easier benchmark.
"""
from __future__ import annotations

import hashlib
import inspect
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import numpy.typing as npt

from libs.tiers import traps
from libs.tiers.traps import Case, Truth, _ar_signal_fn, _lohi, _mk_prices

F = npt.NDArray[np.float64]

SIGMA = 0.01                   # the synthetic suite's per-bar sigma


class Innovations:
    """Direction-free real returns: rescaled to SIGMA, signs flipped by a fair coin."""

    def __init__(self, panel: Mapping[str, F], rng: np.random.Generator) -> None:
        self.names = sorted(k for k, v in panel.items() if len(v) >= 64)
        if not self.names:
            raise ValueError("no real episode long enough")
        self.panel = panel
        self.rng = rng
        self.used: list[tuple[str, int, int]] = []

    def draw(self, n: int, scale: float = 1.0) -> F:
        sym = self.names[int(self.rng.integers(len(self.names)))]
        r = np.asarray(self.panel[sym], dtype=float)
        r = r[np.isfinite(r)]
        if len(r) < 64:
            return self.rng.normal(0, SIGMA * scale, size=n)
        start = int(self.rng.integers(0, max(1, len(r) - n))) if len(r) > n else 0
        seg = r[start:start + n]
        while len(seg) < n:                                     # wrap a short history
            seg = np.concatenate([seg, r[: n - len(seg)]])
        sd = float(seg.std()) or 1.0
        signs = self.rng.choice((-1.0, 1.0), size=n)
        self.used.append((sym, start, n))
        out: F = (seg - seg.mean()) / sd * SIGMA * scale * signs
        return out


def _ar(e: F, phi: float | Callable[[int], float]) -> F:
    r = np.zeros(len(e))
    for t in range(1, len(e)):
        p = phi(t) if callable(phi) else phi
        r[t] = p * r[t - 1] + e[t]
    return r


def generate(kind: str, seed: int, panel: Mapping[str, F], n: int = 1500
             ) -> tuple[Case, Truth, list[tuple[str, int, int]]]:
    """One real-episode case of `kind` (every kind of `traps.ALL_KINDS`)."""
    rng = np.random.default_rng(seed)
    src = Innovations(panel, rng)
    leak_mask = rng.random(n + 1) < 1.0
    factor: F = src.draw(n + 1)
    n_univ = 20
    univ: F = np.column_stack([src.draw(n) for _ in range(n_univ)])
    alive = np.ones(n_univ, dtype=bool)
    variants = 1
    cost = 0.0002
    signal_fn: Callable[[F, int], float] = _ar_signal_fn(1)

    if kind == "true_seasonal":
        r = src.draw(n)
        hour = int(rng.integers(24))
        r[np.arange(n) % 24 == hour] += 0.35 * SIGMA
        prices = _mk_prices(rng, r)

        def signal_fn(px: F, t: int, _h: int = hour) -> float:
            return 1.0 if t % 24 == _h else 0.0
    elif kind in ("true_signal", "true_weak_signal", "true_strong_signal"):
        phi = {"true_signal": 0.12, "true_weak_signal": 0.07, "true_strong_signal": 0.25}[kind]
        prices = _mk_prices(rng, _ar(src.draw(n), phi))
    elif kind == "leakage":
        prices = _mk_prices(rng, src.draw(n))

        def signal_fn(px: F, t: int, _m: npt.NDArray[np.bool_] = leak_mask) -> float:
            if t + 1 >= len(px) or t < 1:
                return 0.0
            return float(np.sign(np.log(px[t + 1] / px[t])))
    elif kind == "timezone_shift":
        prices = _mk_prices(rng, src.draw(n))

        def signal_fn(px: F, t: int) -> float:
            if t + 1 >= len(px) or t < 1:
                return 0.0
            return float(np.sign(0.9 * np.sign(np.log(px[t + 1] / px[t]))
                                 + 0.1 * np.sign(np.log(px[t] / px[t - 1]))))
    elif kind == "selection":
        prices = _mk_prices(rng, src.draw(n))
        rets = np.diff(np.log(prices))
        variants = 400
        best_w, best_flip, best_s = 1, 1.0, -np.inf
        lp = np.log(prices)
        for w in range(1, 41):
            mom = np.zeros(len(prices))
            mom[w:] = np.sign(lp[w:] - lp[:-w])
            for flip in (1.0, -1.0):
                pnl = flip * mom[1:-1] * rets[1:]
                s = pnl.mean() / (pnl.std() + 1e-12)
                if s > best_s:
                    best_s, best_w, best_flip = s, w, flip
        base = _ar_signal_fn(best_w)

        def signal_fn(px: F, t: int, _b: Callable[[F, int], float] = base,
                      _f: float = best_flip) -> float:
            return _f * _b(px, t)
    elif kind == "survivorship":
        drift = rng.normal(0, 0.0015, size=n_univ)
        univ = univ + drift
        alive = drift > np.quantile(drift, 0.5)
        prices = _mk_prices(rng, univ[:, alive].mean(axis=1))

        def signal_fn(px: F, t: int) -> float:
            return 1.0
    elif kind == "impossible_fills":
        prices = _mk_prices(rng, src.draw(n))
    elif kind == "cost_fake":
        prices = _mk_prices(rng, _ar(src.draw(n, 0.3), 0.05))
        cost = 0.004
    elif kind == "regime_break":
        cut = int(n * 0.5)
        prices = _mk_prices(rng, _ar(src.draw(n), lambda t: 0.25 if t < cut else 0.0))
    elif kind == "duplicate_factor":
        f = _ar(src.draw(n + 1), 0.12)
        factor = f
        prices = _mk_prices(rng, f[1:] + src.draw(n, 0.15))

        def signal_fn(px: F, t: int, _f: F = f) -> float:
            return float(np.sign(_f[t])) if t < len(_f) else 0.0
    elif kind == "stale_price":
        stale = _mk_prices(rng, src.draw(n))
        for t in range(1, len(stale)):
            if rng.random() < 0.5:
                stale[t] = stale[t - 1]
        prices = stale

        def signal_fn(px: F, t: int) -> float:
            if t < 1:
                return 0.0
            return -float(np.sign(np.log(px[t] / px[t - 1])))
    elif kind == "information_delay":
        prices = _mk_prices(rng, src.draw(n))
        delay = rng.integers(1, 4, size=n + 2)

        def signal_fn(px: F, t: int, _d: npt.NDArray[np.int64] = delay) -> float:
            d = int(_d[t]) if t < len(_d) else 1
            if t < 1 or t + d >= len(px):
                return 0.0
            return float(np.sign(np.log(px[t + d] / px[t])))
    elif kind == "timestamp_scramble":
        prices = _mk_prices(rng, src.draw(n))
        perm = np.arange(n + 2)
        for b in range(0, n + 2, 4):
            blk = perm[b:b + 4].copy()
            rng.shuffle(blk)
            perm[b:b + 4] = blk

        def signal_fn(px: F, t: int, _p: npt.NDArray[np.int64] = perm) -> float:
            k = int(_p[t]) if t < len(_p) else t
            if k < 1 or k + 1 >= len(px) or t + 1 >= len(px):
                return 0.0
            return float(np.sign(np.log(px[k + 1] / px[k])))
    elif kind == "sign_reversal":
        flip = int(n * 0.5)
        prices = _mk_prices(rng, _ar(src.draw(n), lambda t: 0.2 if t < flip else -0.2))
    elif kind == "spread_perturbation":
        prices = _mk_prices(rng, _ar(src.draw(n), 0.07))
        cost = 0.0015
    elif kind == "label_randomization":
        rets = src.draw(n)
        prices = _mk_prices(rng, rets)
        cut = int(n * 0.6)
        bits = (rets > 0).astype(int)
        table = np.zeros(64)
        for t in range(6, cut - 1):
            code = int("".join(str(b) for b in bits[t - 5: t + 1]), 2)
            table[code] += rets[t + 1]
        table = np.sign(table)

        def signal_fn(px: F, t: int, _tb: F = table) -> float:
            if t < 7:
                return 0.0
            r_ = np.diff(np.log(px[t - 6: t + 1]))
            code = int("".join("1" if x > 0 else "0" for x in r_), 2)
            return float(_tb[code])
    else:
        raise ValueError(f"unknown kind {kind!r}")

    lows, highs = _lohi(rng, prices)
    fills = prices.copy()
    if kind == "impossible_fills":
        ar = _ar_signal_fn(1)
        pos = np.array([ar(prices, t) for t in range(len(prices))])
        fills = np.where(pos > 0, lows * (1 - 0.005 - 1e-5),
                         np.where(pos < 0, highs * (1 + 0.005 + 1e-5), prices))
    case_id = "r" + hashlib.sha256(f"real|{kind}|{seed}|{n}".encode()).hexdigest()[:16]
    case = Case(case_id=case_id, prices=prices, signal_fn=signal_fn, fills=fills, lows=lows,
                highs=highs, cost_per_trade=cost, n_variants_tried=variants,
                factor_returns=factor, universe_returns=univ, universe_alive=alive,
                meta={"suite": "real_episode"})
    return case, Truth(case_id, kind, kind in traps.TRUE_KINDS), src.used


@dataclass
class RealSuite:
    """Every kind at `per_kind` seeds, on the given real return panel (symbol -> returns)."""

    panel: Mapping[str, F]
    per_kind: int = 20
    n: int = 1500
    base_seed: int = 20260930
    kinds: Sequence[str] = field(default_factory=lambda: traps.ALL_KINDS)
    episodes: list[tuple[str, int, int]] = field(default_factory=list)

    def cases(self) -> Iterable[tuple[Case, Truth]]:
        self.episodes = []
        for k_i, kind in enumerate(self.kinds):
            for j in range(self.per_kind):
                case, truth, used = generate(kind, self.base_seed + 1000 * k_i + j, self.panel,
                                             self.n)
                self.episodes.extend(used)
                yield case, truth

    def seal(self, rows: Sequence[tuple[Case, Truth]]) -> str:
        h = hashlib.sha256()
        h.update(inspect.getsource(generate).encode())
        h.update(f"{self.per_kind}|{self.n}|{self.base_seed}|{','.join(self.kinds)}".encode())
        for sym in sorted(self.panel):
            h.update(sym.encode())
            h.update(np.asarray(self.panel[sym], dtype=float).tobytes())
        for case, truth in rows:
            h.update(case.prices.tobytes())
            h.update(truth.kind.encode())
        return h.hexdigest()


def compare(real: Mapping[str, Any], synthetic: Mapping[str, Any]) -> dict[str, Any]:
    """Where the validator behaves differently on real episodes than on Gaussian ones: per kind,
    the accept-rate gap. A trap it rejects on noise and admits on real paths is exactly the
    blind spot this suite exists to find."""
    rp, sp = real.get("per_kind") or {}, synthetic.get("per_kind") or {}
    gaps = {}
    for k in sorted(set(rp) & set(sp)):
        gaps[k] = round(float(rp[k]["accept_rate"]) - float(sp[k]["accept_rate"]), 4)
    worse_traps = {k: v for k, v in gaps.items() if k in traps.TRAP_KINDS and v > 0}
    lost_power = {k: v for k, v in gaps.items() if k in traps.TRUE_KINDS and v < 0}
    return {"accept_rate_gap": gaps, "traps_easier_on_real": worse_traps,
            "power_lost_on_real": lost_power,
            "immune_gap": (None if real.get("immune_score") is None
                           or synthetic.get("immune_score") is None
                           else round(float(real["immune_score"])
                                      - float(synthetic["immune_score"]), 4))}
