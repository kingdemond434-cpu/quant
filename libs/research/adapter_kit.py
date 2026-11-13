"""THE ADAPTER KIT -- the numpy the rebuilt federation adapters share, and the one door from a
measured mechanism to an EXACT family recipe.

WHY IT EXISTS (audit 2026-11-13). Twenty-five of the desk's adapters only checked that a package
imports and donated nothing: an `api_probe` row and a sentence. The order of the day was that
every one of them does real work or carries a measured reason it cannot. The research engines
among them (qlib, finrl, rd_agent, kronos, the agent swarms ...) are rebuilt here as their
DETERMINISTIC core -- the part of each upstream that is a computation over prices, not an LLM --
and each rebuilt adapter donates `STRUCTURED_HYPOTHESIS` candidates through the sandbox runner's
ordinary exit, so its cells reach the gauntlet the same way stumpy's and quantaalpha's do.

WHAT IS SHARED. Indicator maths (EMA, RSI, ATR, rolling moments), a causal forward-return
target, an EVIDENCE scorer whose field names carry no verdict (the packet contract raises on
`passed`, `verdict`, `survivor` ...), a chronological train/holdout split, and `recipe()`: the
single mapping from a mechanism kind (trend, momentum, reversion, squeeze, pullback, breakout,
volume) and a measured window/horizon to a family registered in `adapters.FAMILIES` with the
keyword arguments that family's function in `mt5desk/families.py` actually takes. A recipe whose
family name or keyword is not the family's own would compile as prose and lose its instrument,
which is why the mapping lives in one place and a test pins it against the family signatures.

NOTHING HERE IS A JUDGE. Every number is evidence riding on a hypothesis; the ten gates decide.
Third-party code is never imported here: whether an upstream is installed is read with
`importlib.util.find_spec`, which executes nothing.
"""
from __future__ import annotations

import importlib.util
import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

#: The keyword arguments each family function takes (desks/mt5/mt5desk/families.py, read
#: 2026-11-13). `test_adapter_kit` re-reads the signatures from the AST and fails on drift.
FAMILY_KWARGS: dict[str, tuple[str, ...]] = {
    "momentum_volgate": ("mom_n", "atr_n", "vol_gate_q", "ttl_bars", "rr", "mom_thresh"),
    "trend_ma_cross": ("fast_ema", "slow_ema", "atr_n", "ttl_bars", "rr"),
    "mean_reversion_rsi": ("rsi_n", "oversold", "overbought", "atr_n", "ttl_bars", "rr"),
    "mean_reversion_bollinger": ("bb_n", "bb_k", "atr_n", "ttl_bars", "rr"),
    "volatility_squeeze": ("bb_n", "bb_k", "squeeze_lookback", "atr_n", "ttl_bars", "rr"),
    "range_reversion": ("range_n", "threshold_pct", "atr_n", "ttl_bars", "rr"),
    "volume_spike": ("vol_lookback", "vol_mult", "atr_n", "ttl_bars", "rr"),
    "pullback_entry": ("rsi_n", "trend_ema", "rsi_pullback", "rsi_bounce", "atr_n", "ttl_bars",
                       "rr"),
    "level_breakout": ("level", "signal_hour", "wait_bars", "atr_n", "ttl_bars", "rr",
                       "vol_filter", "vol_gate_q", "range_filter", "spread_gate"),
    "failed_breakout": ("level", "signal_hours", "atr_n", "ttl_bars", "rr", "min_pierce_atr",
                        "spread_gate"),
    "overnight_drift": ("anchor_hour", "hold_bars", "atr_n", "ttl_bars", "rr"),
}

#: Mechanism kinds the rebuilt engines speak, each answered by one registered family.
KINDS: tuple[str, ...] = ("trend", "momentum", "reversion", "band_reversion", "range_reversion",
                          "squeeze", "pullback", "breakout", "failed_breakout", "volume",
                          "overnight")


def upstream_installed(module: str) -> bool:
    """Whether the upstream package is installed here, WITHOUT importing (executing) it."""
    if not module:
        return False
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


# ------------------------------------------------------------------------------ arrays

def arrays(frame: Any) -> dict[str, np.ndarray]:
    """open/high/low/close/volume as float arrays plus the UTC hour of each bar."""
    hours = np.array([_hour(t) for t in frame.time], dtype=int)
    return {"o": np.asarray(frame.open, dtype=float), "h": np.asarray(frame.high, dtype=float),
            "l": np.asarray(frame.low, dtype=float), "c": np.asarray(frame.close, dtype=float),
            "v": np.asarray(frame.volume, dtype=float), "hour": hours}


def _hour(t: str) -> int:
    try:
        return int(str(t)[11:13])
    except ValueError:
        return 0


def ema(x: np.ndarray, n: int) -> np.ndarray:
    a = 2.0 / (n + 1.0)
    out = np.empty_like(x, dtype=float)
    acc = float(x[0]) if x.size else 0.0
    for i, v in enumerate(x):
        acc = a * float(v) + (1.0 - a) * acc if i else float(v)
        out[i] = acc
    return out


def sma(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(x.shape[0], np.nan)
    if x.shape[0] >= n:
        c = np.cumsum(np.insert(x.astype(float), 0, 0.0))
        out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def rolling_std(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(x.shape[0], np.nan)
    if x.shape[0] >= n:
        c = np.cumsum(np.insert(x.astype(float), 0, 0.0))
        c2 = np.cumsum(np.insert(x.astype(float) ** 2, 0, 0.0))
        m = (c[n:] - c[:-n]) / n
        out[n - 1:] = np.sqrt(np.maximum((c2[n:] - c2[:-n]) / n - m * m, 0.0))
    return out


def rolling_max(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(x.shape[0], np.nan)
    for i in range(n - 1, x.shape[0]):
        out[i] = float(np.max(x[i - n + 1:i + 1]))
    return out


def rolling_min(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(x.shape[0], np.nan)
    for i in range(n - 1, x.shape[0]):
        out[i] = float(np.min(x[i - n + 1:i + 1]))
    return out


def rsi(c: np.ndarray, n: int = 14) -> np.ndarray:
    d = np.diff(c, prepend=c[0])
    up = ema(np.maximum(d, 0.0), 2 * n - 1)
    dn = ema(np.maximum(-d, 0.0), 2 * n - 1)
    rs = up / np.maximum(dn, 1e-12)
    return np.asarray(100.0 - 100.0 / (1.0 + rs), dtype=float)


def atr(h: np.ndarray, lo: np.ndarray, c: np.ndarray, n: int = 20) -> np.ndarray:
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - lo, np.maximum(np.abs(h - pc), np.abs(lo - pc)))
    return sma(tr, n)


def zscore(x: np.ndarray, n: int) -> np.ndarray:
    m = sma(x, n)
    s = rolling_std(x, n)
    return np.asarray((x - m) / np.where(s > 0, s, np.nan), dtype=float)


def forward_return(c: np.ndarray, horizon: int) -> np.ndarray:
    """log(c[t+h] / c[t]); NaN where the future is not in the frame (causal by construction)."""
    out = np.full(c.shape[0], np.nan)
    if c.shape[0] > horizon:
        lc = np.log(np.maximum(c, 1e-12))
        out[:-horizon] = lc[horizon:] - lc[:-horizon]
    return out


def cost_frac(bundle: Any, symbol: str, c: np.ndarray) -> float:
    """The bundle's median spread as a fraction of the median price (0 when unknown)."""
    row = bundle.costs.get(symbol)
    if row is None or not math.isfinite(float(row.pooled_median_spread_pts)):
        return 0.0
    px = float(np.nanmedian(c)) if c.size else 0.0
    return float(row.pooled_median_spread_pts) * float(row.tick_size) / px if px > 0 else 0.0


def split(n: int, frac: float = 0.6) -> int:
    """The chronological train/holdout boundary: everything at or after it is unseen."""
    return max(1, min(n - 1, int(n * frac)))


def evidence(signal: np.ndarray, fwd: np.ndarray, cost: float = 0.0,
             lo: int = 0, hi: int | None = None) -> dict[str, float]:
    """How a {-1, 0, +1} signal lined up with the forward return over [lo, hi): mean net return
    per active bar, hit rate, activity count and a t-like ratio. EVIDENCE, never a verdict."""
    s = np.asarray(signal, dtype=float)[lo:hi]
    f = np.asarray(fwd, dtype=float)[lo:hi]
    ok = np.isfinite(s) & np.isfinite(f) & (s != 0)
    if int(ok.sum()) < 5:
        return {"mean_net": 0.0, "hit_rate": 0.0, "n_active": float(ok.sum()), "t_ratio": 0.0}
    pnl = s[ok] * f[ok] - cost
    sd = float(np.std(pnl))
    return {"mean_net": float(np.mean(pnl)), "hit_rate": float(np.mean(pnl > 0)),
            "n_active": float(ok.sum()),
            "t_ratio": float(np.mean(pnl) / sd * math.sqrt(ok.sum())) if sd > 0 else 0.0}


def evidence_turnover(signal: np.ndarray, fwd: np.ndarray, cost: float = 0.0,
                      lo: int = 0, hi: int | None = None) -> dict[str, float]:
    """`evidence` for a HELD position: the round-trip cost is charged when the position changes
    (as a policy trained on turnover pays it), not on every bar the position is held. The same
    four numbers, so a holding policy and a one-bar signal read side by side."""
    s = np.nan_to_num(np.asarray(signal, dtype=float), nan=0.0)
    f = np.asarray(fwd, dtype=float)
    change = np.abs(np.diff(np.concatenate([[0.0], s]))) > 0
    s, f, change = s[lo:hi], f[lo:hi], change[lo:hi]
    ok = np.isfinite(f) & (s != 0)
    if int(ok.sum()) < 5:
        return {"mean_net": 0.0, "hit_rate": 0.0, "n_active": float(ok.sum()), "t_ratio": 0.0}
    pnl = s[ok] * f[ok] - cost * change[ok]
    sd = float(np.std(pnl))
    return {"mean_net": float(np.mean(pnl)), "hit_rate": float(np.mean(pnl > 0)),
            "n_active": float(ok.sum()),
            "t_ratio": float(np.mean(pnl) / sd * math.sqrt(ok.sum())) if sd > 0 else 0.0}


def rank_ic(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman rank correlation over the finite pairs (0 when fewer than 20)."""
    ok = np.isfinite(x) & np.isfinite(y)
    if int(ok.sum()) < 20:
        return 0.0
    a = np.argsort(np.argsort(x[ok])).astype(float)
    b = np.argsort(np.argsort(y[ok])).astype(float)
    sa, sb = float(np.std(a)), float(np.std(b))
    if sa == 0 or sb == 0:
        return 0.0
    return float(np.mean((a - a.mean()) * (b - b.mean())) / (sa * sb))


# ------------------------------------------------------------------------------ recipes

def _clip(v: float, lo: int, hi: int) -> int:
    return int(max(lo, min(hi, round(v))))


def recipe(kind: str, *, window: int = 20, horizon: int = 12, strength: float = 1.0,
           hour: int = 7) -> tuple[str, dict[str, Any]]:
    """The registered family and its EXACT keyword arguments for a measured mechanism.

    `window` is the lookback the engine measured the mechanism at, `horizon` the bars it held
    for, `strength` a dimensionless threshold scale (1.0 = the family default)."""
    w = _clip(window, 3, 200)
    ttl = _clip(horizon, 2, 72)
    st = max(0.25, min(4.0, float(strength)))
    if kind == "trend":
        fast = _clip(w / 3.0, 3, 60)
        return "trend_ma_cross", {"fast_ema": fast, "slow_ema": max(fast + 3, w),
                                  "atr_n": 20, "ttl_bars": ttl, "rr": 1.8}
    if kind == "momentum":
        return "momentum_volgate", {"mom_n": _clip(w, 2, 96), "atr_n": 20,
                                    "vol_gate_q": 0.4, "ttl_bars": ttl, "rr": 1.8,
                                    "mom_thresh": round(0.0012 * st, 6)}
    if kind == "reversion":
        band = _clip(20.0 * st, 10, 35)
        return "mean_reversion_rsi", {"rsi_n": _clip(w, 3, 50), "oversold": band,
                                      "overbought": 100 - band, "atr_n": 20, "ttl_bars": ttl,
                                      "rr": 1.8}
    if kind == "band_reversion":
        return "mean_reversion_bollinger", {"bb_n": _clip(w, 5, 100),
                                            "bb_k": round(max(1.0, min(3.5, 2.0 * st)), 2),
                                            "atr_n": 20, "ttl_bars": ttl, "rr": 1.8}
    if kind == "range_reversion":
        return "range_reversion", {"range_n": _clip(w, 5, 120),
                                   "threshold_pct": round(0.01 * st, 5), "atr_n": 20,
                                   "ttl_bars": ttl, "rr": 1.8}
    if kind == "squeeze":
        return "volatility_squeeze", {"bb_n": _clip(w, 5, 100), "bb_k": 2.0,
                                      "squeeze_lookback": _clip(w, 5, 100), "atr_n": 20,
                                      "ttl_bars": ttl, "rr": 2.0}
    if kind == "pullback":
        return "pullback_entry", {"rsi_n": 14, "trend_ema": _clip(w, 10, 200),
                                  "rsi_pullback": 40, "rsi_bounce": 50, "atr_n": 20,
                                  "ttl_bars": ttl, "rr": 1.8}
    if kind == "breakout":
        return "level_breakout", {"level": "pdh", "signal_hour": _clip(hour, 0, 23),
                                  "wait_bars": _clip(w, 2, 24), "atr_n": 20, "ttl_bars": ttl,
                                  "rr": 2.0}
    if kind == "failed_breakout":
        return "failed_breakout", {"level": "pdh", "signal_hours": [_clip(hour, 0, 23)],
                                   "atr_n": 20, "ttl_bars": ttl, "rr": 1.6,
                                   "min_pierce_atr": 0.05}
    if kind == "volume":
        return "volume_spike", {"vol_lookback": _clip(w, 5, 120),
                                "vol_mult": round(max(1.2, min(5.0, 2.0 * st)), 2),
                                "atr_n": 20, "ttl_bars": ttl, "rr": 1.8}
    if kind == "overnight":
        return "overnight_drift", {"anchor_hour": _clip(hour, 0, 23),
                                   "hold_bars": _clip(w, 2, 24), "atr_n": 20, "ttl_bars": ttl,
                                   "rr": 1.8}
    raise ValueError(f"unknown mechanism kind {kind!r}: {KINDS}")


def donate(A: Any, system: str, kind: str, symbol: str, text: str, *, horizon_label: str,
           ev: Mapping[str, Any], window: int = 20, horizon: int = 12, strength: float = 1.0,
           hour: int = 7) -> dict[str, Any]:
    """One STRUCTURED_HYPOTHESIS row with the exact recipe in `evidence.parameters`, which is
    where the sandbox runner reads a candidate's params from."""
    family, params = recipe(kind, window=window, horizon=horizon, strength=strength, hour=hour)
    row: dict[str, Any] = A.candidate(family, [symbol], text, horizon=horizon_label,
                                      source=system, evidence={**dict(ev), "parameters": params,
                                                               "mechanism_kind": kind})
    return row


def direction_kind(sign: float, *, trend_like: bool = True) -> str:
    """A positive relation between a past move and the next one is persistence (momentum or
    trend); a negative one is reversion."""
    if sign >= 0:
        return "momentum" if trend_like else "trend"
    return "reversion"


def best(rows: Sequence[Mapping[str, Any]], key: str = "holdout_t") -> list[Mapping[str, Any]]:
    """Rows ordered by a finite evidence key, best first."""
    ok = [r for r in rows if isinstance(r.get(key), (int, float)) and math.isfinite(r[key])]
    return sorted(ok, key=lambda r: float(r[key]), reverse=True)


def frames(bundle: Any, *, min_bars: int = 300, limit: int = 12) -> list[Any]:
    """The bundle's H1 frames long enough to split, at most `limit` (the bundle's own rotation
    decides which; an adapter never chooses its symbols by result)."""
    return [f for f in bundle.frames("H1") if len(f) >= min_bars][:limit]


def upstream_row(system: str, module: str, mechanism: str, why_not_driven: str) -> dict[str, Any]:
    """The REBUILT provenance row every rebuilt adapter carries: what upstream mechanism is
    reproduced, whether the upstream package is installed here (find_spec, nothing executed)
    and why the upstream loop itself is not driven."""
    return {"kind": "rebuilt_mechanism", "system": system, "mechanism": mechanism,
            "upstream_module": module, "upstream_installed": upstream_installed(module),
            "upstream_not_driven_because": why_not_driven}


def kind_signal(kind: str, a: Mapping[str, np.ndarray], window: int) -> np.ndarray:
    """A causal {-1, 0, +1} reading of each mechanism kind on bar arrays -- the SAME direction
    the family's recipe takes, so an engine's evidence and its donated recipe agree in sign.
    An approximation for scoring only; the family code is what the gauntlet runs."""
    c, h, lo, v = a["c"], a["h"], a["l"], a["v"]
    n = c.shape[0]
    w = max(3, int(window))
    out = np.zeros(n)
    if kind in ("momentum", "trend"):
        if kind == "trend":
            f, s = ema(c, max(3, w // 3)), ema(c, w)
            out = np.sign(f - s)
        else:
            m = np.full(n, np.nan)
            m[w:] = c[w:] - c[:-w]
            out = np.sign(np.nan_to_num(m))
    elif kind == "reversion":
        r = rsi(c, w)
        out = np.where(r < 30, 1.0, np.where(r > 70, -1.0, 0.0))
    elif kind == "band_reversion":
        z = zscore(c, w)
        out = np.where(z < -2, 1.0, np.where(z > 2, -1.0, 0.0))
    elif kind == "range_reversion":
        z = zscore(c, w)
        out = np.where(z < -1, 1.0, np.where(z > 1, -1.0, 0.0))
    elif kind == "squeeze":
        sd = rolling_std(c, w)
        q = np.nanquantile(sd, 0.2) if np.isfinite(sd).any() else np.nan
        m = np.full(n, np.nan)
        m[1:] = c[1:] - c[:-1]
        out = np.where(sd <= q, np.sign(np.nan_to_num(m)), 0.0)
    elif kind == "pullback":
        e = ema(c, w)
        r = rsi(c, 14)
        out = np.where((c > e) & (r < 40), 1.0, np.where((c < e) & (r > 60), -1.0, 0.0))
    elif kind in ("breakout", "failed_breakout"):
        hi = np.concatenate([[np.nan], rolling_max(h, w)[:-1]])
        lw = np.concatenate([[np.nan], rolling_min(lo, w)[:-1]])
        brk = np.where(c > hi, 1.0, np.where(c < lw, -1.0, 0.0))
        out = brk if kind == "breakout" else -brk
    elif kind == "volume":
        vm = sma(v, w)
        m = np.full(n, np.nan)
        m[1:] = c[1:] - c[:-1]
        out = np.where(v > 2.0 * np.nan_to_num(vm, nan=np.inf), np.sign(np.nan_to_num(m)), 0.0)
    elif kind == "overnight":
        m = np.full(n, np.nan)
        m[w:] = c[w:] - c[:-w]
        out = -np.sign(np.nan_to_num(m)) * (a["hour"] == 0)
    res: np.ndarray = np.nan_to_num(np.asarray(out, dtype=float))
    return res


def corr(x: np.ndarray, y: np.ndarray) -> float:
    """Pearson correlation over finite pairs; 0 for fewer than 30 pairs or a constant side
    (never a RuntimeWarning: the suite treats one as a failure)."""
    ok = np.isfinite(x) & np.isfinite(y)
    if int(ok.sum()) < 30:
        return 0.0
    a, b = x[ok] - x[ok].mean(), y[ok] - y[ok].mean()
    den = float(np.sqrt(np.dot(a, a) * np.dot(b, b)))
    return float(np.dot(a, b) / den) if den > 0 else 0.0


def score_kinds(a: Mapping[str, np.ndarray], specs: Sequence[tuple[str, int]], horizon: int,
                cost: float, cut: int) -> list[dict[str, Any]]:
    """For each (kind, window): the kind's signal, its evidence on train [0, cut) and holdout
    [cut, n). `holdout_t` is NaN unless the train evidence was positive first, so a ranking by it
    never selects on the holdout alone."""
    fwd = forward_return(a["c"], horizon)
    n = a["c"].shape[0]
    rows = []
    for kind, w in specs:
        s = kind_signal(kind, a, w)
        tr = evidence(s, fwd, cost, 0, cut)
        ho = evidence(s, fwd, cost, cut, n)
        rows.append({"kind": kind, "window": int(w), "train": tr, "holdout": ho,
                     "holdout_t": ho["t_ratio"] if tr["mean_net"] > 0 else float("nan")})
    return rows
