"""Written rules for three more families of the independent replication lane (LAWS 5m).

    formula               one expression of the alpha grammar, z-scored, thresholded
    cross_asset_residual  the residual of an instrument after several factor returns, faded
    relative_value        the log spread to one peer, faded

Each family is a plain-English rule (`SPECS[f].text`) and this module's OWN reading of it, built
on the lane's own bars, orders and ATR (`replication_civilization`). THE SAME INDEPENDENCE RULE
BINDS THIS FILE: it never imports the desk's family code, its engine, its expression evaluator
(`libs.research.alpha_grammar`), its modifier layer (`mt5desk.cell_modifiers`) or its residual
regression (`mt5desk.causal_residual`); `FORBIDDEN_IMPORTS` lists them and the lane's test scans
this source. Agreement between two implementations written from one text is the evidence; one
implementation imported twice would agree with itself whatever it does.

THE WRAPPERS A CERTIFICATE CARRIES, as written rules. The desk's call path takes the family's
signals and then, in this order: keeps only signals whose bar hour is inside the cell's
`session`; keeps only signals whose bar is in the named volatility or calendar `regime`; applies
a `side_mode` the family does not take itself; and, for `entry_timing=delayed`, moves each signal
one bar later with the same stop and target. `execution_style=market` is the next-open fill the
lane already simulates, and `representation` is a filing label. ANY OTHER VALUE, AND ANY KEY
THIS BOOK DOES NOT NAME, IS REFUSED BY NAME: the certificate is UNMEASURED with the reason, never
rebuilt as something it does not claim to be. A false REPLICATED from a silently dropped
parameter is the worst outcome this lane can produce.

Inputs from other symbols (the factors, the peer) arrive as the lane's own `Bars`, loaded
through its own `load_bars`, in `p["_inputs"]` in the order the parameters name them.
"""
from __future__ import annotations

import ast
import re
import warnings
from collections.abc import Callable, Mapping
from typing import Any

import numpy as np
import pandas as pd
from replication_civilization import Bars, Order, RuleSpec, atr

HOUR_NS = 3_600_000_000_000

#: Session -> [start, end) bar-clock hours a signal must fall in (`all` keeps every signal).
SESSION_WINDOWS: dict[str, tuple[int, int] | None] = {
    "asia": (0, 8), "london": (8, 16), "ny": (14, 22), "all": None,
}
#: Regime spellings with a written meaning; the empty and unconditional ones change nothing.
NO_OP_REGIMES = frozenset({"", "unconditional", "all", "any"})
VOL_REGIMES = {"high_vol": "high", "high_volatility": "high", "low_vol": "low"}
CALENDAR_REGIMES = frozenset({"month_end", "quarter_end"})
ENTRY_TIMINGS = frozenset({"", "instant", "delayed"})
MARKET_STYLES = frozenset({"", "market"})
#: Keys that only label the coordinate a cell was filed under and change no trade.
LABEL_KEYS = frozenset({"representation", "timeframe"})
#: Wrapper keys the lane interprets; each family's own rule parameters are in its defaults.
WRAPPER_KEYS = frozenset({"session", "regime", "side_mode", "entry_timing", "execution_style",
                          "entry_style"})
SIDE_MODE_MODIFIERS = frozenset({"", "follow", "revert", "long", "short"})

WRAPPER_TEXT = (
    " WRAPPERS, applied after the rule in this order: `session` keeps signals whose bar hour is "
    "in asia [0,8) / london [8,16) / ny [14,22) (all keeps every one); `regime` high_vol "
    "(low_vol) keeps signals where the 20-bar std of close-to-close percent returns is above "
    "(below) its own 100-bar rolling median, month_end keeps bars on day 26 or later, "
    "quarter_end month_end in March/June/September/December; a `side_mode` the rule does not "
    "take itself is follow (nothing), revert (each trade reversed, stop and target mirrored "
    "around the signal bar's close), long or short (that side only); `entry_timing=delayed` "
    "moves each signal one bar later with the same stop and target (dropped on the last bar). "
    "`execution_style=market` is the next-open fill; `representation` is a label. Any other "
    "value or key is refused by name.")


# ------------------------------------------------------------------------------- helpers
def _series(b: Bars, x: np.ndarray) -> pd.Series:
    return pd.Series(np.asarray(x, dtype="float64"), index=pd.RangeIndex(len(b)))


def _norm(v: Any) -> str:
    return str(v if v is not None else "").strip().lower()


def _symbols(raw: Any) -> list[str]:
    """`factor_symbols` as a list, whether stored as a list or as its printed repr."""
    if isinstance(raw, str):
        try:
            raw = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            raw = [s for s in re.split(r"[,\s]+", raw.strip("[]() ")) if s]
    if isinstance(raw, (list, tuple)):
        return [str(s).strip().strip("'\"") for s in raw if str(s).strip()]
    return []


# ------------------------------------------------------------------------------ wrappers
def _regime_keep(b: Bars, regime: str) -> np.ndarray:
    """Per bar: is it inside the regime the wrapper names."""
    if regime in VOL_REGIMES:
        c = pd.Series(b.c)
        rv = (c / c.shift(1) - 1.0).rolling(20, min_periods=20).std()
        med = rv.rolling(100, min_periods=100).median()
        keep = rv > med if VOL_REGIMES[regime] == "high" else rv < med
        return keep.fillna(False).to_numpy(dtype=bool)
    stamps = pd.to_datetime(pd.Series(b.t), utc=True)
    keep = (stamps.dt.day >= 26).to_numpy()
    if regime == "quarter_end":
        keep &= stamps.dt.month.isin((3, 6, 9, 12)).to_numpy()
    return np.asarray(keep, dtype=bool)


def apply_wrappers(b: Bars, orders: list[Order], w: Mapping[str, Any]) -> list[Order]:
    """The written wrapper rules, in the order the desk's call path applies them."""
    out = list(orders)
    if not out:
        return out
    win = w.get("session")
    if win is not None:
        lo, hi = win
        out = [o for o in out if lo <= int((o.t_ns // HOUR_NS) % 24) < hi]
    regime = str(w.get("regime") or "")
    if regime and regime not in NO_OP_REGIMES:
        keep = _regime_keep(b, regime)
        pos = np.searchsorted(b.t, np.asarray([o.t_ns for o in out], dtype="int64"))
        out = [o for o, i in zip(out, pos, strict=True)
               if i < len(b) and b.t[i] == o.t_ns and bool(keep[i])]
    mode = str(w.get("side_mode") or "")
    if mode == "revert":
        flipped: list[Order] = []
        for o in out:
            i = int(np.searchsorted(b.t, o.t_ns))
            if i >= len(b) or b.t[i] != o.t_ns or not np.isfinite(b.c[i]):
                continue
            ref = float(b.c[i])
            flipped.append(Order(o.t_ns, -o.side, 2.0 * ref - o.stop, 2.0 * ref - o.target,
                                 o.ttl_bars, o.trigger, o.wait_bars, o.unfilled_if_crossed))
        out = flipped
    elif mode in ("long", "short"):
        want = 1 if mode == "long" else -1
        out = [o for o in out if o.side == want]
    if w.get("delayed"):
        moved: list[Order] = []
        for o in out:
            i = int(np.searchsorted(b.t, o.t_ns))
            if i < len(b) - 1 and b.t[i] == o.t_ns:
                moved.append(Order(int(b.t[i + 1]), o.side, o.stop, o.target, o.ttl_bars,
                                   o.trigger, o.wait_bars, o.unfilled_if_crossed))
        out = moved
    return out


# ------------------------------------------------------------------------- the formula DSL
F_TERMINALS = frozenset({"close", "open", "high", "low", "ret", "range", "body", "atr", "vol",
                         "spread", "activity", "flow"})
F_UNARY = frozenset({"neg", "abs", "sign"})
F_WINDOWED = frozenset({"delay", "delta", "mean", "std", "min", "max", "sum", "ts_rank",
                        "zscore", "decay", "ts_backfill", "bars_since_max", "bars_since_min",
                        "atr_norm", "scale"})
F_BINARY = frozenset({"add", "sub", "mul", "div", "max2", "min2", "trade_when"})
F_BINARY_WINDOWED = frozenset({"corr", "cov", "residual", "group_rank", "group_zscore"})
F_VOL_N = 24

FORMULA_TEXT = (
    "Evaluate the expression (a prefix tree: [op, child, ..., window]) on the bars. Terminals: "
    "close/open/high/low; ret = log-close difference; range = (high-low)/close; body = "
    "(close-open)/close; atr = mean true range over atr_n bars (none until atr_n exist); vol = "
    "24-bar std of ret; spread = the broker spread column; activity = tick volume; flow = "
    "sign(body) x activity. Operators: neg/abs/sign; delay/delta by w bars; rolling "
    "mean/std/min/max/sum over w (full window only); ts_rank = share of the previous w values "
    "<= the current one; zscore over w; decay = linearly weighted mean (weights w..1, newest "
    "heaviest); ts_backfill = forward fill at most w bars; bars_since_max/min within the last w; "
    "atr_norm = x / mean(atr over w); scale = x / sum|x| over w; add/sub/mul; div (NaN where "
    "|denominator| <= 1e-12); max2/min2 (NaN only where both are); trade_when(g, x) = x where "
    "g > 0, else the last such x; corr/cov/residual over w (w >= 3); group_rank/group_zscore of "
    "x among the bars of the last w whose g lies on the same side of its own window mean as the "
    "current bar's. Anything undefined is NaN. Then z = (v - mean_norm(v)) / std_norm(v) over "
    "norm bars; refuse when fewer than 5% of z are finite or the bars are shorter than "
    "max(2 x norm, 300). From bar norm on, at most one signal per hold_bars bars: where |z| >= "
    "entry_z, side = sign(z) (follow) or -sign(z) (fade); stop stop_atr x ATR(atr_n) from the "
    "signal bar's close, target rr x that; entry next open; time exit after hold_bars. "
    "`population` is provenance and changes nothing.")


def parse_call_form(text: str) -> Any:
    """'div(open, bars_since_min(high, 5))' -> ['div', 'open', ['bars_since_min', 'high', 5]]."""
    s = re.sub(r"\s+", "", text)
    pos = 0

    def node() -> Any:
        nonlocal pos
        m = re.match(r"[^(),]+", s[pos:])
        if not m:
            raise ValueError(f"no token at {pos} in {text!r}")
        tok = m.group(0)
        pos += len(tok)
        if pos < len(s) and s[pos] == "(":
            pos += 1
            args = [node()]
            while pos < len(s) and s[pos] == ",":
                pos += 1
                args.append(node())
            if pos >= len(s) or s[pos] != ")":
                raise ValueError(f"unclosed call in {text!r}")
            pos += 1
            return [tok, *args]
        if re.fullmatch(r"-?\d+", tok):
            return int(tok)
        if re.fullmatch(r"-?\d+\.\d*", tok):
            return float(tok)
        return tok

    out = node()
    if pos != len(s):
        raise ValueError(f"trailing input in {text!r}")
    return out


def formula_refusal(expr: Any) -> str | None:
    """The named reason an expression has no written rule here, or None."""
    if isinstance(expr, str):
        return None if expr in F_TERMINALS else (
            f"no written rule for formula terminal {expr!r} (drivers, externals and panels "
            "need inputs this lane is not given)")
    if not isinstance(expr, (list, tuple)) or not expr:
        return f"formula expression {expr!r} is not a prefix tree"
    op = str(expr[0])
    arity = {**dict.fromkeys(F_UNARY, 1), **dict.fromkeys(F_WINDOWED, 2),
             **dict.fromkeys(F_BINARY, 2), **dict.fromkeys(F_BINARY_WINDOWED, 3)}
    if op not in arity:
        return f"no written rule for formula operator {op!r}"
    if len(expr) != arity[op] + 1:
        return f"formula operator {op!r} given {len(expr) - 1} argument(s)"
    kids = expr[1:2] if op in F_UNARY or op in F_WINDOWED else expr[1:3]
    if (op in F_WINDOWED or op in F_BINARY_WINDOWED) and (
            not isinstance(expr[-1], int) or isinstance(expr[-1], bool)):
            return f"formula operator {op!r} window {expr[-1]!r} is not an integer"
    for k in kids:
        why = formula_refusal(k)
        if why:
            return why
    return None


def _terminals(b: Bars, atr_n: int) -> dict[str, pd.Series]:
    c, o, h, lo = (_series(b, x) for x in (b.c, b.o, b.h, b.low))
    out = {"close": c, "open": o, "high": h, "low": lo}
    with np.errstate(all="ignore"):
        out["ret"] = np.log(c).diff()
        out["range"] = (h - lo) / c
        out["body"] = (c - o) / c
        prev = c.shift(1)
        tr = np.fmax(np.fmax((h - lo).to_numpy(), (h - prev).abs().to_numpy()),
                     (lo - prev).abs().to_numpy())
        out["atr"] = pd.Series(tr).rolling(atr_n, min_periods=atr_n).mean()
        out["vol"] = out["ret"].rolling(F_VOL_N, min_periods=F_VOL_N).std()
    if b.spread is not None:
        out["spread"] = _series(b, b.spread)
    if b.tick_volume is not None:
        out["activity"] = _series(b, b.tick_volume)
        out["flow"] = np.sign(out["body"]).fillna(0.0) * out["activity"]
    return out


def _ts_rank(x: np.ndarray, w: int) -> np.ndarray:
    out = np.full(x.size, np.nan)
    for t in range(w, x.size):
        out[t] = float(np.mean(x[t - w:t] <= x[t]))
    return out


def _bars_since(x: np.ndarray, w: int, want_max: bool) -> np.ndarray:
    out = np.full(x.size, np.nan)
    y = np.where(np.isnan(x), -np.inf if want_max else np.inf, x)
    for t in range(w - 1, x.size):
        seg = y[t - w + 1:t + 1]
        k = int(np.argmax(seg) if want_max else np.argmin(seg))
        out[t] = (w - 1) - k
    return out


def _group(x: np.ndarray, g: np.ndarray, w: int, rank: bool) -> np.ndarray:
    out = np.full(x.size, np.nan)
    if w < 2:
        return out
    for t in range(w - 1, x.size):
        xs, gs = x[t - w + 1:t + 1], g[t - w + 1:t + 1]
        fin = np.isfinite(gs)
        if not fin.any():
            continue
        side = np.sign(gs - float(np.mean(gs[fin])))
        peers = (side == side[-1]) & np.isfinite(xs) & fin
        n = int(peers.sum())
        cur = xs[-1]
        if rank:
            if n > 1:
                out[t] = float(np.sum(peers & (xs <= cur))) / n
        else:
            if n > 2:
                vals = xs[peers]
                sd = float(np.std(vals))
                if sd > 1e-12:
                    out[t] = (cur - float(np.mean(vals))) / sd
    return out


def _decay(s: pd.Series, w: int) -> pd.Series:
    acc = pd.Series(0.0, index=s.index)
    for k in range(w):
        acc = acc + s.shift(k) * float(w - k)
    return acc / float(w * (w + 1) / 2)


def evaluate(expr: Any, frames: dict[str, pd.Series], n: int) -> pd.Series:
    nan = pd.Series(np.nan, index=pd.RangeIndex(n))
    try:
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            out = _ev(expr, frames, n, nan)
    except Exception:
        out = nan
    return out.astype(float).replace([np.inf, -np.inf], np.nan)


def _ev(e: Any, f: dict[str, pd.Series], n: int, nan: pd.Series) -> pd.Series:
    if isinstance(e, str):
        return f.get(e, nan)
    op = str(e[0])
    if op in F_UNARY:
        a = evaluate(e[1], f, n)
        return -a if op == "neg" else a.abs() if op == "abs" else np.sign(a)
    if op in F_WINDOWED:
        a, w = evaluate(e[1], f, n), int(e[2])
        if w < 1 or w > n:
            return nan
        if op == "delay":
            return a.shift(w)
        if op == "delta":
            return a - a.shift(w)
        if op in ("mean", "std", "min", "max", "sum"):
            return getattr(a.rolling(w, min_periods=w), op)()
        if op == "zscore":
            r = a.rolling(w, min_periods=w)
            return (a - r.mean()) / r.std()
        if op == "ts_rank":
            return pd.Series(_ts_rank(a.to_numpy(dtype=float), w))
        if op == "decay":
            return _decay(a, w)
        if op == "ts_backfill":
            return a.ffill(limit=w)
        if op in ("bars_since_max", "bars_since_min"):
            return pd.Series(_bars_since(a.to_numpy(dtype=float), w, op == "bars_since_max"))
        if op == "atr_norm":
            at = f.get("atr")
            return nan if at is None else a / at.rolling(w, min_periods=1).mean()
        den = a.abs().rolling(w, min_periods=w).sum()                      # scale
        return a / den.where(den > 1e-12)
    if op in F_BINARY:
        a, c = evaluate(e[1], f, n), evaluate(e[2], f, n)
        if op == "add":
            return a + c
        if op == "sub":
            return a - c
        if op == "mul":
            return a * c
        if op == "div":
            return a / c.where(c.abs() > 1e-12)
        if op in ("max2", "min2"):
            both = np.vstack([a.to_numpy(dtype=float), c.to_numpy(dtype=float)])
            return pd.Series(np.nanmax(both, axis=0) if op == "max2"
                             else np.nanmin(both, axis=0))
        return c.where(a > 0).ffill()                                       # trade_when
    a, c, w = evaluate(e[1], f, n), evaluate(e[2], f, n), int(e[3])
    if w < 3 or w > n:
        return nan
    if op == "corr":
        return a.rolling(w, min_periods=w).corr(c)
    if op == "cov":
        return a.rolling(w, min_periods=w).cov(c)
    if op == "residual":
        beta = a.rolling(w, min_periods=w).cov(c) / c.rolling(w, min_periods=w).var().where(
            lambda v: v > 1e-18)
        return a - beta * c
    return pd.Series(_group(a.to_numpy(dtype=float), c.to_numpy(dtype=float), w,
                            op == "group_rank"))


def _build_formula(b: Bars, p: dict[str, Any]) -> list[Order]:
    norm, hold = int(p["norm"]), int(p["hold_bars"])
    if len(b) < max(2 * norm, 300):
        return []
    frames = _terminals(b, int(p["atr_n"]))
    v = evaluate(p["expr"], frames, len(b))
    r = v.rolling(norm, min_periods=norm)
    z = ((v - r.mean()) / r.std()).to_numpy(dtype=float)
    if np.isfinite(z).sum() < 0.05 * z.size:
        return []
    a = atr(b, int(p["atr_n"]))
    flip = 1 if p["side_mode"] == "follow" else -1
    sa, rr, ez = float(p["stop_atr"]), float(p["rr"]), float(p["entry_z"])
    out: list[Order] = []
    last = -10 ** 9
    for i in range(norm, len(b) - 1):
        if i - last < hold:
            continue
        zi, ai = z[i], a[i]
        if not np.isfinite(zi) or abs(zi) < ez or not np.isfinite(ai) or ai <= 0:
            continue
        side = int(np.sign(zi)) * flip
        if side == 0:
            continue
        px = float(b.c[i])
        out.append(Order(int(b.t[i]), side, px - side * sa * ai, px + side * sa * ai * rr, hold,
                         unfilled_if_crossed=True))
        last = i
    return apply_wrappers(b, out, p["_wrap"])


# ------------------------------------------------------------------- cross-asset residual
RESIDUAL_TEXT = (
    "Join this instrument's closes with each factor's closes on common bar times (rows with any "
    "missing close dropped). Log returns of all; drop rows where any return is undefined. "
    "Regress the target return on a constant and the factor returns by OLS over the beta_win "
    "rows BEFORE each row (beta_win defaults to lookback) and take that row's residual (none "
    "until beta_win rows exist). Cumulate the residuals; z = (cum - its lookback mean) / its "
    "lookback std. Refuse with fewer than beta_win + 2 x lookback joined rows. From row "
    "beta_win + lookback on, where |z| >= entry_z (and, with active_hours, the bar hour is one "
    "of them): side_mode revert trades -sign(z), continue trades sign(z); stop stop_atr x "
    "ATR(atr_n) of this instrument and target rr x that, BOTH LAID FROM THE JOINED CLOSE ONE "
    "ROW BEFORE THE SIGNAL ROW (the desk's implementation indexes the joined frame before its "
    "first return is dropped; written down here because it is what the certificate trades); "
    "entry next open; time exit after ttl_bars.")


def _join(own: Bars, others: list[Bars]) -> tuple[np.ndarray, list[np.ndarray]]:
    """Common bar times and each frame's close on them; rows with any missing close dropped."""
    t = own.t
    for o in others:
        t = np.intersect1d(t, o.t)
    closes = []
    for fr in (own, *others):
        idx = np.searchsorted(fr.t, t)
        closes.append(fr.c[idx])
    keep = np.all(np.isfinite(np.vstack(closes)), axis=0) if len(t) else np.zeros(0, bool)
    return t[keep], [c[keep] for c in closes]


def rolling_ols_residual(y: np.ndarray, x: np.ndarray, win: int) -> np.ndarray:
    """eps[t] = y[t] - [1, x[t]] . beta, beta the OLS fit on rows [t-win, t-1] only."""
    n, k = x.shape
    z = np.column_stack([np.ones(n), x])
    eps = np.full(n, np.nan)
    if win < k + 2 or n <= win:
        return eps
    zz = np.einsum("ti,tj->tij", z, z)
    zy = z * y[:, None]
    czz = np.concatenate([np.zeros((1, k + 1, k + 1)), np.cumsum(zz, axis=0)])
    czy = np.concatenate([np.zeros((1, k + 1)), np.cumsum(zy, axis=0)])
    ts = np.arange(win, n)
    lhs = czz[ts] - czz[ts - win]
    rhs = czy[ts] - czy[ts - win]
    try:
        beta = np.linalg.solve(lhs, rhs[:, :, None])[:, :, 0]
    except np.linalg.LinAlgError:
        beta = np.einsum("tij,tj->ti", np.linalg.pinv(lhs), rhs)
    eps[win:] = y[win:] - np.einsum("tj,tj->t", z[win:], beta)
    return eps


def _build_cross_asset_residual(b: Bars, p: dict[str, Any]) -> list[Order]:
    factors = list(p.get("_inputs") or [])
    if not factors or p["side_mode"] not in ("revert", "continue"):
        return []
    lb = int(p["lookback"])
    bwin = int(p["beta_win"]) if p.get("beta_win") else lb
    t, closes = _join(b, factors)
    if len(t) < bwin + 2 * lb:
        return []
    with np.errstate(all="ignore"):
        rets = [np.concatenate([[np.nan], np.diff(np.log(c))]) for c in closes]
    mat = np.vstack(rets)
    ok = np.all(np.isfinite(mat), axis=0)
    if ok.sum() < bwin + 2 * lb:
        return []
    resid = rolling_ols_residual(mat[0, ok], mat[1:, ok].T, bwin)
    cum = pd.Series(np.where(np.isfinite(resid), resid, 0.0).cumsum()).where(
        pd.Series(np.isfinite(resid)))
    r = cum.rolling(lb, min_periods=lb)
    z = ((cum - r.mean()) / r.std()).to_numpy(dtype=float)
    ct = t[ok]
    a_own = atr(b, int(p["atr_n"]))
    a = a_own[np.searchsorted(b.t, ct)]
    ref = closes[0]                     # indexed by residual row: one joined row early
    hours = ({int(h) for h in p["active_hours"]} if p.get("active_hours") else None)
    revert = p["side_mode"] == "revert"
    sa, rr, ez, ttl = float(p["stop_atr"]), float(p["rr"]), float(p["entry_z"]), \
        int(p["ttl_bars"])
    out: list[Order] = []
    for i in range(bwin + lb, len(ct) - 1):
        zi = z[i]
        if not np.isfinite(zi) or abs(zi) < ez:
            continue
        if hours is not None and int((ct[i] // HOUR_NS) % 24) not in hours:
            continue
        ai = float(a[i])
        if not np.isfinite(ai) or ai <= 0:
            continue
        side = (-1 if zi > 0 else 1) if revert else (1 if zi > 0 else -1)
        px = float(ref[i])
        out.append(Order(int(ct[i]), side, px - side * sa * ai, px + side * sa * ai * rr, ttl,
                         unfilled_if_crossed=True))
    return apply_wrappers(b, out, p["_wrap"])


# ------------------------------------------------------------------------ relative value
RV_TEXT = (
    "Join this instrument's closes with the peer's on common bar times; refuse with fewer than "
    "2 x lookback rows. spread = log(close) - log(peer close); z = (spread - its lookback "
    "mean) / its lookback std. From row lookback on, where |z| >= entry_z: side -sign(z) (rich "
    "-> short this leg); stop stop_atr x ATR(atr_n) of this instrument from this leg's close; "
    "target this close + side x |z - exit_z| x std x close (the absolute value is of z - "
    "exit_z, not |z| - exit_z, as the desk's implementation writes it); entry next open; time "
    "exit after ttl_bars.")


def _build_relative_value(b: Bars, p: dict[str, Any]) -> list[Order]:
    peers = list(p.get("_inputs") or [])
    if not peers:
        return []
    lb = int(p["lookback"])
    t, (ca, cb) = _join(b, peers[:1])
    if len(t) < 2 * lb:
        return []
    with np.errstate(all="ignore"):
        spread = pd.Series(np.log(ca) - np.log(cb))
        r = spread.rolling(lb, min_periods=lb)
        mu, sd = r.mean().to_numpy(), r.std().to_numpy()
        z = (spread.to_numpy() - mu) / sd          # a flat spread has no z: NaN, no signal
    a = atr(b, int(p["atr_n"]))[np.searchsorted(b.t, t)]
    ez, xz, sa, ttl = float(p["entry_z"]), float(p["exit_z"]), float(p["stop_atr"]), \
        int(p["ttl_bars"])
    out: list[Order] = []
    for i in range(lb, len(t) - 1):
        zi = z[i]
        if not np.isfinite(zi) or abs(zi) < ez:
            continue
        ai = float(a[i])
        if not np.isfinite(ai) or ai <= 0:
            continue
        side = -1 if zi > 0 else 1
        px = float(ca[i])
        out.append(Order(int(t[i]), side, px - side * sa * ai,
                         px + side * abs(zi - xz) * float(sd[i]) * px, ttl,
                         unfilled_if_crossed=True))
    return apply_wrappers(b, out, p["_wrap"])


# ---------------------------------------------------------------------------- the book
SPECS: dict[str, RuleSpec] = {
    "formula": RuleSpec(
        "formula", FORMULA_TEXT + WRAPPER_TEXT,
        {"expr": None, "norm": 240, "entry_z": 1.5, "side_mode": "follow", "hold_bars": 8,
         "atr_n": 20, "stop_atr": 2.0, "rr": 1.5}, _build_formula),
    "cross_asset_residual": RuleSpec(
        "cross_asset_residual", RESIDUAL_TEXT + WRAPPER_TEXT,
        {"lookback": 240, "beta_win": None, "entry_z": 2.0, "atr_n": 20, "stop_atr": 2.0,
         "rr": 1.5, "ttl_bars": 72, "side_mode": "revert", "active_hours": None},
        _build_cross_asset_residual),
    "relative_value": RuleSpec(
        "relative_value", RV_TEXT + WRAPPER_TEXT,
        {"lookback": 120, "entry_z": 2.0, "exit_z": 0.5, "atr_n": 20, "stop_atr": 2.5,
         "ttl_bars": 48}, _build_relative_value),
}
#: The parameters that name other symbols' bars, per family, and are not rule parameters.
INPUT_KEYS = {"cross_asset_residual": "factor_symbols", "relative_value": "peer_symbol"}
#: Families whose own rule takes `side_mode` (so it is a rule parameter, not a wrapper).
NATIVE_SIDE_MODES = {"formula": frozenset({"follow", "fade"}),
                     "cross_asset_residual": frozenset({"revert", "continue"})}


def input_symbols(family: str, params: Mapping[str, Any] | None) -> list[str]:
    """The other symbols whose bars this family's rule reads, in the order it reads them."""
    key = INPUT_KEYS.get(str(family or ""))
    if key is None:
        return []
    raw = dict(params or {}).get(key)
    return _symbols(raw) if key == "factor_symbols" else ([str(raw)] if raw else [])


def _resolve(family: str, params: Mapping[str, Any] | None, selector: str | None,
             side: str | int | None) -> tuple[dict[str, Any] | None, str]:
    """Strict: every key is a rule parameter, an input, a written wrapper or a label; any other
    key or value is refused by name. The selector is a label for these families."""
    del selector
    spec = SPECS[family]
    p = dict(spec.defaults)
    raw = dict(params or {})
    wrap: dict[str, Any] = {"session": None, "regime": "", "side_mode": "", "delayed": False}
    if str(side or "").strip().upper() in ("SHORT", "-1"):
        return None, (f"no written rule for a SHORT {family} certificate: the desk's call "
                      "passes side=-1 to a rule that takes no side")
    for k, v in raw.items():
        val = _norm(v)
        if k == "population" and family == "formula":
            continue
        if k == INPUT_KEYS.get(family) or k in LABEL_KEYS:
            continue
        if k == "side_mode" and family in NATIVE_SIDE_MODES:
            if val not in NATIVE_SIDE_MODES[family]:
                return None, f"no written rule for {family} side_mode={v!r}"
            p["side_mode"] = val
            continue
        if k in p:
            p[k] = v
            continue
        if k == "session":
            if val not in SESSION_WINDOWS:
                return None, f"no written rule for wrapper session={v!r}"
            wrap["session"] = SESSION_WINDOWS[val]
        elif k == "regime":
            if val not in NO_OP_REGIMES and val not in VOL_REGIMES \
                    and val not in CALENDAR_REGIMES:
                return None, f"no written rule for wrapper regime={v!r}"
            wrap["regime"] = val
        elif k == "side_mode":
            if val not in SIDE_MODE_MODIFIERS:
                return None, f"no written rule for wrapper side_mode={v!r}"
            wrap["side_mode"] = "" if val == "follow" else val
        elif k == "entry_timing":
            if val not in ENTRY_TIMINGS:
                return None, f"no written rule for wrapper entry_timing={v!r}"
            wrap["delayed"] = val == "delayed"
        elif k in ("execution_style", "entry_style"):
            if val not in MARKET_STYLES:
                return None, f"no written rule for wrapper {k}={v!r}"
        else:
            return None, f"no written rule for parameter {k}={v!r} on family {family!r}"
    key = INPUT_KEYS.get(family)
    if key is not None and not input_symbols(family, raw):
        return None, f"{family}: no {key} named, so the rule has no second series to read"
    if family == "formula":
        expr = p.get("expr")
        if isinstance(expr, str) and "(" in expr:
            try:
                expr = parse_call_form(expr)
            except ValueError as exc:
                return None, f"formula expr is not a readable call form: {exc}"
        if expr is None:
            return None, "formula certificate carries no expression"
        why = formula_refusal(expr)
        if why:
            return None, why
        p["expr"] = expr
    p["_wrap"] = wrap
    p["_side"] = 0
    p["_session"] = None
    return p, "ok"


OWN_RESOLVERS: dict[str, Callable[..., tuple[dict[str, Any] | None, str]]] = {
    f: (lambda params, selector, side, _f=f: _resolve(_f, params, selector, side))
    for f in SPECS}
