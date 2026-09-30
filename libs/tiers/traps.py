"""PLANTED SCIENTIFIC TRAPS (Tier S layers 10 and 34): synthetic cases with a known answer.

Each case is what a validator sees of a candidate -- a price path, a causal signal FUNCTION (so a
truncation test can actually run it), the fills it claims, a cost model, the number of variants
tried to find it, a factor it may secretly be, and the universe it was drawn from -- and nothing
else. The KIND and the LABEL (genuine or false) are held outside the case, so the validator under
test cannot be told which datasets are poisoned.

    leakage            the signal reads the next bar's return
    timezone_shift     the signal is stamped one bar early (a stale-clock lookahead)
    selection          the best of N pure-noise variants, reported as one
    survivorship       a long book over assets that survived, drawn from a universe that died
    impossible_fills   fills outside the bar's traded range
    cost_fake          gross positive, net negative once realistic costs are charged
    regime_break       the whole edge sits in the first half and is gone after
    duplicate_factor   a levered copy of a factor the desk already holds
    stale_price        a stale quote manufactures reversion out of nothing
    true_signal        a genuine, modest, persistent predictable component (must PASS)
    true_weak_signal   genuine but small; a validator that rejects it is too strict

Everything is generated from an integer seed, so the suite is reproducible bit for bit and its
hash can be sealed.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import numpy.typing as npt

F = npt.NDArray[np.float64]

TRAP_KINDS: tuple[str, ...] = ("leakage", "timezone_shift", "selection", "survivorship",
                               "impossible_fills", "cost_fake", "regime_break",
                               "duplicate_factor", "stale_price",
                               # 2026-09-30, the verifier's missing placebos:
                               "information_delay", "timestamp_scramble", "sign_reversal",
                               "spread_perturbation", "label_randomization")
#: POSITIVE CONTROLS: genuine edges a validator must ACCEPT, so a gate that rejects everything
#: scores zero power instead of a perfect immune score.
TRUE_KINDS: tuple[str, ...] = ("true_signal", "true_weak_signal", "true_seasonal",
                               "true_strong_signal")
ALL_KINDS: tuple[str, ...] = TRAP_KINDS + TRUE_KINDS

#: HOW A KIND REACHES THE PRODUCTION GAUNTLET. The ten-gate certifier sees a cell as a signal
#: stamped on a bar and the return that follows -- nothing else. So:
#:   * a kind whose signal READS information from after its bar is docketed at the honest stamp
#:     of that information (`adversary.docket_cell(stamp_offset=1)`): stamped on bar t with bar
#:     t+1's information, the leak would be a real predictor in the docket's world and no engine
#:     could ever reject it -- the caller would have cheated before the harness saw it;
#:   * a kind whose trap lives in fills, the universe, a factor series or stale quotes carries
#:     nothing the certifier is shown, so it is INEXPRESSIBLE there and is scored by the
#:     reference validator only -- counted apart, never as a production pass or fail.
LATE_INFORMATION_KINDS: frozenset[str] = frozenset(
    {"leakage", "timezone_shift", "information_delay", "timestamp_scramble"})
INEXPRESSIBLE_TO_GAUNTLET: frozenset[str] = frozenset(
    {"survivorship", "impossible_fills", "duplicate_factor", "stale_price"})


@dataclass
class Case:
    """What a validator may see. No kind, no label."""

    case_id: str
    prices: F
    #: signal_fn(prices, t) -> position in [-1, 1] held from bar t to t+1. It is GIVEN the whole
    #: path, exactly like real code handed a whole frame; a causal one reads prices[: t + 1] only.
    signal_fn: Callable[[F, int], float]
    #: claimed fill prices per bar (NaN where no trade), and each bar's low/high
    fills: F
    lows: F
    highs: F
    cost_per_trade: float
    n_variants_tried: int
    factor_returns: F
    #: returns of every asset in the universe the book was drawn from (T x N), incl. dead ones
    universe_returns: F
    universe_alive: npt.NDArray[np.bool_]
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Truth:
    case_id: str
    kind: str
    genuine: bool


def _returns(prices: F) -> F:
    out: F = np.diff(np.log(prices))
    return out


def _mk_prices(rng: np.random.Generator, r: F) -> F:
    p: F = 100.0 * np.exp(np.concatenate([[0.0], np.cumsum(r)]))
    return p


def _lohi(rng: np.random.Generator, p: F) -> tuple[F, F]:
    spread = np.abs(rng.normal(0, 0.002, size=p.shape)) * p + 1e-6 * p
    lo: F = p - spread
    hi: F = p + spread
    return lo, hi


def _ar_signal_fn(window: int = 1) -> Callable[[F, int], float]:
    """Causal momentum of the last `window` returns: reads px[: t + 1] only."""
    def fn(px: F, t: int) -> float:
        if t < window + 1:
            return 0.0
        seg = px[t - window: t + 1]
        return float(np.sign(np.log(seg[-1] / seg[0])))
    return fn


def generate(kind: str, seed: int, n: int = 1500, subtlety: float = 0.0) -> tuple[Case, Truth]:
    """One case. `subtlety` in [0, 1] makes a trap HARDER to see (the Red Queen's attackers
    evolve it); 0 is the sealed suite's setting and genuine kinds ignore it."""
    rng = np.random.default_rng(seed)
    s_ = min(1.0, max(0.0, float(subtlety)))
    leak_mask = rng.random(n + 1) < (1.0 - 0.9 * s_)
    sigma = 0.01
    factor: F = rng.normal(0, sigma, size=n + 1)
    n_univ = 20
    univ: F = rng.normal(0, sigma, size=(n, n_univ))
    alive = np.ones(n_univ, dtype=bool)
    variants = 1
    cost = 0.0002
    signal_fn: Callable[[F, int], float] = _ar_signal_fn(1)

    if kind == "true_seasonal":
        # a genuine hour-of-day drift: +mu on one stamp-hour in 24, noise elsewhere
        r = rng.normal(0, sigma, size=n)
        hour = int(rng.integers(24))
        r[np.arange(n) % 24 == hour] += 0.35 * sigma
        prices = _mk_prices(rng, r)

        def signal_fn(px: F, t: int, _h: int = hour) -> float:
            return 1.0 if t % 24 == _h else 0.0
    elif kind in ("true_signal", "true_weak_signal", "true_strong_signal"):
        # the strong control exists to CALIBRATE a judge: an AR(0.25) edge any sound certifier
        # must accept even on a short sample, so zero power there is a defect, not caution
        phi = {"true_signal": 0.12, "true_weak_signal": 0.07, "true_strong_signal": 0.25}[kind]
        e = rng.normal(0, sigma, size=n)
        r = np.zeros(n)
        for t in range(1, n):
            r[t] = phi * r[t - 1] + e[t]
        prices = _mk_prices(rng, r)
    elif kind == "leakage":
        prices = _mk_prices(rng, rng.normal(0, sigma, size=n))

        def signal_fn(px: F, t: int, _m: npt.NDArray[np.bool_] = leak_mask) -> float:
            if t + 1 >= len(px) or t < 1:
                return 0.0
            if t < len(_m) and not _m[t]:
                return float(np.sign(np.log(px[t] / px[t - 1])))
            return float(np.sign(np.log(px[t + 1] / px[t])))
    elif kind == "timezone_shift":
        prices = _mk_prices(rng, rng.normal(0, sigma, size=n))

        def signal_fn(px: F, t: int) -> float:
            if t + 1 >= len(px) or t < 1:
                return 0.0
            return float(np.sign(0.9 * np.sign(np.log(px[t + 1] / px[t]))
                                 + 0.1 * np.sign(np.log(px[t] / px[t - 1]))))
    elif kind == "selection":
        prices = _mk_prices(rng, rng.normal(0, sigma, size=n))
        rets = np.diff(np.log(prices))
        variants = max(1, round(400 * (1.0 - s_)))  # hidden trials = the attack
        best_w, best_flip, best_s = 1, 1.0, -np.inf
        for w in range(1, 41):
            mom = np.zeros(len(prices))
            lp = np.log(prices)
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
        univ = rng.normal(0, sigma, size=(n, n_univ)) + drift
        alive = drift > np.quantile(drift, 0.5 - 0.4 * s_)
        prices = _mk_prices(rng, univ[:, alive].mean(axis=1))

        def signal_fn(px: F, t: int) -> float:
            return 1.0
    elif kind == "impossible_fills":
        prices = _mk_prices(rng, rng.normal(0, sigma, size=n))
    elif kind == "cost_fake":
        e = rng.normal(0, sigma * 0.3, size=n)
        r = np.zeros(n)
        for t in range(1, n):
            r[t] = 0.05 * r[t - 1] + e[t]
        prices = _mk_prices(rng, r)
        cost = 0.004 * (1.0 - s_) + 0.0006 * s_
    elif kind == "regime_break":
        e = rng.normal(0, sigma, size=n)
        r = np.zeros(n)
        for t in range(1, n):
            r[t] = (0.25 if t < int(n * (0.5 + 0.4 * s_)) else 0.0) * r[t - 1] + e[t]
        prices = _mk_prices(rng, r)
    elif kind == "duplicate_factor":
        f = np.zeros(n + 1)
        fe = rng.normal(0, sigma, size=n + 1)
        for t in range(1, n + 1):
            f[t] = 0.12 * f[t - 1] + fe[t]
        factor = f
        prices = _mk_prices(rng, f[1:] + rng.normal(0, sigma * (0.15 + 0.6 * s_), size=n))

        def signal_fn(px: F, t: int, _f: F = f) -> float:
            return float(np.sign(_f[t])) if t < len(_f) else 0.0
    elif kind == "stale_price":
        true = _mk_prices(rng, rng.normal(0, sigma, size=n))
        stale = true.copy()
        for t in range(1, len(stale)):
            if rng.random() < 0.5 - 0.35 * s_:
                stale[t] = stale[t - 1]
        prices = stale

        def signal_fn(px: F, t: int) -> float:
            if t < 1:
                return 0.0
            return -float(np.sign(np.log(px[t] / px[t - 1])))
    elif kind == "information_delay":
        # a series published with a delay, read as if known on time: the signal uses bar
        # t + d's close, d in 1..3, on a pure-noise path
        prices = _mk_prices(rng, rng.normal(0, sigma, size=n))
        delay = rng.integers(1, 4, size=n + 2)

        def signal_fn(px: F, t: int, _d: npt.NDArray[np.int64] = delay,
                      _m: npt.NDArray[np.bool_] = leak_mask) -> float:
            d = int(_d[t]) if t < len(_d) else 1
            if t < 1 or t + d >= len(px):
                return 0.0
            if t < len(_m) and not _m[t]:
                return float(np.sign(np.log(px[t] / px[t - 1])))
            return float(np.sign(np.log(px[t + d] / px[t])))
    elif kind == "timestamp_scramble":
        # bars shuffled within blocks of four: "the previous bar" is sometimes a later one
        prices = _mk_prices(rng, rng.normal(0, sigma, size=n))
        perm = np.arange(n + 2)
        for b in range(0, n + 2, 4):
            blk = perm[b:b + 4].copy()
            if rng.random() < (1.0 - 0.8 * s_):
                rng.shuffle(blk)
            perm[b:b + 4] = blk

        def signal_fn(px: F, t: int, _p: npt.NDArray[np.int64] = perm) -> float:
            k = int(_p[t]) if t < len(_p) else t
            if k < 1 or k + 1 >= len(px) or t + 1 >= len(px):
                return 0.0
            return float(np.sign(np.log(px[k + 1] / px[k])))
    elif kind == "sign_reversal":
        # momentum that pays in the first half and costs in the second: the edge flipped sign
        e = rng.normal(0, sigma, size=n)
        r = np.zeros(n)
        flip = int(n * (0.5 + 0.35 * s_))
        for t in range(1, n):
            r[t] = (0.2 if t < flip else -0.2) * r[t - 1] + e[t]
        prices = _mk_prices(rng, r)
    elif kind == "spread_perturbation":
        # a REAL weak edge that does not survive a realistic spread: gross positive, net negative
        e = rng.normal(0, sigma, size=n)
        r = np.zeros(n)
        for t in range(1, n):
            r[t] = 0.07 * r[t - 1] + e[t]
        prices = _mk_prices(rng, r)
        cost = 0.0015 * (1.0 - s_) + 0.0006 * s_
    elif kind == "label_randomization":
        # A LOOKUP TABLE FITTED TO THE LABELS. The position for each pattern of the last six
        # return signs (64 patterns) is the sign that pattern's NEXT return had on the first 60%
        # of a pure-noise path. Every input is causal -- only past signs are read -- so nothing
        # leaks; all of its in-sample edge is the fit, and out of sample it is a coin.
        rets = rng.normal(0, sigma, size=n)
        prices = _mk_prices(rng, rets)
        cut = int(n * (0.6 + 0.3 * s_))
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
        # buys fill at the bar low minus a gap, sells at the high plus: outside the range
        fills = np.where(pos > 0, lows * (1 - 0.005 * (1 - s_) - 1e-5),
                         np.where(pos < 0, highs * (1 + 0.005 * (1 - s_) + 1e-5), prices))
    case_id = "c" + hashlib.sha256(f"{kind}|{seed}|{n}|{s_}".encode()).hexdigest()[:16]
    case = Case(case_id=case_id, prices=prices, signal_fn=signal_fn, fills=fills, lows=lows,
                highs=highs, cost_per_trade=cost, n_variants_tried=variants,
                factor_returns=factor, universe_returns=univ, universe_alive=alive)
    genuine = kind in TRUE_KINDS
    return case, Truth(case_id, kind, genuine)
