#!/usr/bin/env python3
"""META-LABELING AND BET SIZING FOR EVERY SLEEVE (Lopez de Prado, AFML ch. 3), judged out of sample.

THE QUESTION. The base strategy decides WHEN and WHICH WAY. A secondary model asks, of each
occurrence the base strategy already took: given what the market looked like at the decision,
how likely is THIS one to win -- and should it be pressed, taken normally, or skipped? That is
meta-labeling; mapping the secondary probability to a size is bet sizing.

WHAT IT LEARNS FROM. Every sleeve's own trade history: the forward/shadow ledgers
(`reports/shadow/ledger_*.json` on the box, `backups/moat/shadow_ledgers/` in git) and, for
any LIVE row of `data/sleeves.json`, the same ledger by name. The ledgers carry entry, exit,
side and realised R and NO decision-time features, so the features are RECOMPUTED CAUSALLY from
the H1 bars: only bars whose CLOSE (open + 1h) is at or before the trade's entry_time are read.
A bar still forming at the decision cannot reach the feature, and nothing at or after entry can.

THE FEATURES ARE FIXED BEFORE ANY RESULT (`FEATURES`) and never searched. The sleeve's own
trailing win rate counts only trades that had CLOSED before this entry -- an open trade's
outcome is not knowable at the decision, and counting it is the leak this design exists to
avoid.

THE MODEL is an L2-regularised logistic regression (numpy Newton/IRLS; the trading box has no
sklearn). Per sleeve when the sleeve has `MIN_SLEEVE_TRADES`, else pooled over its FAMILY (the
ledger stem without its symbol: every `*_overnight_gap_decay_asia` sleeve is one family), and
UNMEASURED when neither is thick enough. Evaluation is WALK-FORWARD and PURGED: a test block is
predicted by a model fit only on trades that had EXITED at least `EMBARGO_H` hours before the
block's first entry, so a training trade overlapping the test window is excluded.

THE BET SIZE (AFML 3.7, two-sided). z = (p - p0) / sqrt(p (1 - p)), shrunk by n / (n + K), where
p0 is the TRAINING base win rate -- not 0.5: a 2R-target strategy breaks even near 0.33, and the
size question is "better or worse than this sleeve's usual", not "better than a coin". Then
m = 2 Phi(z) - 1 in [-1, 1] and the multiplier is 1 + m (MAX - 1) above, 1 + m below: 0.0 is a
skip, MAX (2.0, the meta_label harness's own ceiling) is the strongest press.

THE VERDICT IS HEAT-NEUTRAL AND DEFLATED. Sizing up a positive sleeve wins by leverage alone, so
the multipliers are divided by their OOS mean before scoring: the question is only whether the
model moved the SAME heat onto the better occurrences. Per OOS trade,
d = log(1 + f m R) - log(1 + f R) at the sleeve's risk_frac f; the t of mean(d) is deflated by
E[max Z] over the EFFECTIVE trial count (`libs.research.trial_ledger.census` over every sleeve x
model configuration this organ has ever evaluated, lifetime, from `data/meta_label_trials.jsonl`).
GAIN needs t_deflated > 2, OOS AUC > 0.5 and `MIN_OOS` OOS trades. Anything else is NO_GAIN, or
UNMEASURED with its reason. The CURRENT multiplier is published only on GAIN; otherwise 1.0.

GROWTH GOVERNANCE. The modifier is two-sided by construction (0.0 .. 2.0), and every sleeve's
row is its missed-growth line: the OOS dE[log W] per trade the sizing would have added or cost.
Rule 1 (a reduction must prove it raises robust forward E[log W]) is the GAIN test itself.

NOT WIRED TO ANY ORDER. `CONSUMPTION` names exactly where the multiplier would be applied; that
is money-path work for its own protected PR, as is registering the modifier in
`libs/portfolio/capital_modifiers.REGISTRY` (a protected path).

    python desks/mt5/research/meta_labeler.py --once --budget-s 300
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import sys
import time
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SCHEMA = "meta_label/v1"
REPORT = BASE / "reports" / "META_LABEL.json"
TRIALS = BASE / "data" / "meta_label_trials.jsonl"
SLEEVES = BASE / "data" / "sleeves.json"
LEDGER_DIRS: tuple[Path, ...] = (BASE / "reports" / "shadow",
                                 ROOT / "backups" / "moat" / "shadow_ledgers")
BAR_DIRS: tuple[Path, ...] = (BASE / "data" / "universe", BASE / "universe")
BUDGET_S = 300.0

#: THE FEATURE LIST, DECLARED BEFORE ANY RESULT AND NEVER SEARCHED. "signed" = multiplied by the
#: trade side, so "price high in its range" means the same thing to a long and a short.
FEATURES: tuple[str, ...] = (
    "atr_frac",           # ATR(20) / close
    "vol_ratio",          # log( std(6 h log returns) / std(120 h log returns) )
    "range_pos_signed",   # (close - mid of the 20-bar high/low range) / ATR(20), x side
    "ret_1d_z_signed",    # 24 h log return / (sigma_1h sqrt 24), sigma over 240 h, x side
    "ret_5d_z_signed",    # 120 h log return / (sigma_1h sqrt 120), x side
    "hour_sin", "hour_cos",   # hour of day of the entry (UTC)
    "dow_sin", "dow_cos",     # day of week of the entry
    "spread_rel",         # log( last spread / median spread of 240 h ), 0 if no spread column
    "trail_win",          # (wins + 1) / (n + 2) over the sleeve's prior 20 CLOSED trades
)
#: The model configurations. Each sleeve x configuration is a trial and is charged.
MODEL_CONFIGS: tuple[dict[str, float], ...] = ({"l2": 1.0}, {"l2": 10.0})
MIN_SLEEVE_TRADES = 80
MIN_POOL_TRADES = 80
MIN_TRAIN = 40
N_FOLDS = 5
MIN_OOS = 30
EMBARGO_H = 24.0
K_SHRINK = 40.0
MAX_MULT = 2.0
DEFAULT_RISK_FRAC = 0.03   # sizing.BASE_RISK_FRAC; used when a sleeve carries none
T_GAIN = 2.0
MIN_BARS = 260

CONSUMPTION = {
    "wired": False,
    "where": ("desks/mt5/mt5desk/gateway.py resolve_family_order, beside leg_balance.multiplier "
              "and macro_view.multiplier: after promoted_lot / the allocator's lot and BEFORE the "
              "venue lot step (decision_core.implementable_lot), as lot *= sleeves[name]."
              "current_multiplier[side] from this report"),
    "contract": ("read only when generated_utc is under 2 h old and the sleeve's verdict is GAIN; "
                 "any other reading is exactly 1.0. Inside the allocator's heat, never above a "
                 "cap, a daily stop or a ruin rail"),
    "registry": ("libs/portfolio/capital_modifiers.REGISTRY entry "
                 "Modifier('meta_label_bet_size', 0.0, 2.0, 'two_sided', ...) -- a protected "
                 "path, so it lands with the money-path PR that applies the multiplier"),
}


# ------------------------------------------------------------------ one-thread BLAS
@contextlib.contextmanager
def _one_native_thread() -> Iterator[None]:
    """BLAS capped at one thread, as learned_miners does: this runs beside the gateway."""
    try:
        from threadpoolctl import threadpool_limits
    except ImportError:
        yield
        return
    with threadpool_limits(limits=1):
        yield


# ------------------------------------------------------------------ trades
@dataclass(frozen=True)
class Trade:
    entry: pd.Timestamp
    exit: pd.Timestamp
    side: int
    r: float


def _ts(v: Any) -> pd.Timestamp | None:
    if v in (None, ""):
        return None
    try:
        t = pd.Timestamp(v)
    except (TypeError, ValueError):
        return None
    if pd.isna(t):
        return None
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _side(v: Any) -> int | None:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return 1 if v > 0 else (-1 if v < 0 else None)
    s = str(v or "").strip().lower()
    if s in ("long", "buy", "1", "+1"):
        return 1
    if s in ("short", "sell", "-1"):
        return -1
    return None


def parse_trades(rows: Any) -> list[Trade]:
    """Every ledger row shape the desk writes (shadow: entry_time/r_multiple; scalp:
    opened_at/r), sorted by entry. Rows missing a field are dropped, never guessed."""
    out: list[Trade] = []
    if not isinstance(rows, list):
        return out
    for r in rows:
        if not isinstance(r, Mapping):
            continue
        et = _ts(r.get("entry_time", r.get("opened_at")))
        xt = _ts(r.get("exit_time", r.get("closed_at")))
        sd = _side(r.get("side", r.get("direction")))
        try:
            rm = float(r.get("r_multiple", r.get("r")))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if et is None or xt is None or sd is None or not math.isfinite(rm):
            continue
        out.append(Trade(et, max(xt, et), sd, rm))
    out.sort(key=lambda t: (t.entry, t.exit))
    return out


# ------------------------------------------------------------------ causal features
def _bars_before(bars: pd.DataFrame, t: pd.Timestamp) -> pd.DataFrame:
    """Bars COMPLETE at t: open + 1h <= t. A bar forming at the decision is not read."""
    cutoff = t - pd.Timedelta(hours=1)
    idx = bars.index.searchsorted(cutoff, side="right")
    return bars.iloc[:idx]


def bar_features(bars: pd.DataFrame, t: pd.Timestamp, side: int) -> dict[str, float] | None:
    """The market half of FEATURES at decision time t, from complete bars only."""
    b = _bars_before(bars, t).iloc[-MIN_BARS:]
    if len(b) < MIN_BARS:
        return None
    c = b["close"].to_numpy(dtype=float)
    h = b["high"].to_numpy(dtype=float)
    lo = b["low"].to_numpy(dtype=float)
    if not np.all(np.isfinite(c)) or np.any(c <= 0):
        return None
    prev = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - lo, np.maximum(np.abs(h - prev), np.abs(lo - prev)))
    atr = float(tr[-20:].mean())
    lr = np.diff(np.log(c))
    sig = float(lr[-240:].std()) if lr.size >= 240 else float(lr.std())
    s_short, s_long = float(lr[-6:].std()), float(lr[-120:].std())
    if atr <= 0 or sig <= 0 or s_long <= 0:
        return None
    mid = 0.5 * (float(h[-20:].max()) + float(lo[-20:].min()))
    r1 = float(np.log(c[-1] / c[-25]))
    r5 = float(np.log(c[-1] / c[-121]))
    spread_rel = 0.0
    if "spread" in b.columns:
        sp = b["spread"].to_numpy(dtype=float)[-240:]
        med = float(np.nanmedian(sp)) if sp.size else 0.0
        if med > 0 and math.isfinite(float(sp[-1])) and sp[-1] > 0:
            spread_rel = float(np.log(sp[-1] / med))
    hr = t.hour + t.minute / 60.0
    dw = t.dayofweek
    return {
        "atr_frac": atr / c[-1],
        "vol_ratio": float(np.log(max(s_short, 1e-12) / s_long)),
        "range_pos_signed": side * (c[-1] - mid) / atr,
        "ret_1d_z_signed": side * r1 / (sig * math.sqrt(24.0)),
        "ret_5d_z_signed": side * r5 / (sig * math.sqrt(120.0)),
        "hour_sin": math.sin(2 * math.pi * hr / 24.0),
        "hour_cos": math.cos(2 * math.pi * hr / 24.0),
        "dow_sin": math.sin(2 * math.pi * dw / 7.0),
        "dow_cos": math.cos(2 * math.pi * dw / 7.0),
        "spread_rel": spread_rel,
    }


def trail_win(history: Sequence[Trade], t: pd.Timestamp, k: int = 20) -> float:
    """(wins + 1) / (n + 2) over the last k trades that had CLOSED strictly before t."""
    closed = [x for x in history if x.exit < t]
    closed.sort(key=lambda x: x.exit)
    last = closed[-k:]
    wins = sum(1 for x in last if x.r > 0)
    return (wins + 1.0) / (len(last) + 2.0)


def features(trades: Sequence[Trade], bars: pd.DataFrame
             ) -> tuple[np.ndarray, list[int]]:
    """Design matrix (rows in FEATURES order) and the indices of the trades it covers."""
    rows: list[list[float]] = []
    keep: list[int] = []
    for i, tr in enumerate(trades):
        f = bar_features(bars, tr.entry, tr.side)
        if f is None:
            continue
        f["trail_win"] = trail_win(trades, tr.entry)
        rows.append([float(f[k]) for k in FEATURES])
        keep.append(i)
    x = np.asarray(rows, dtype=float).reshape(-1, len(FEATURES))
    return x, keep


# ------------------------------------------------------------------ the model
def fit_logistic(x: np.ndarray, y: np.ndarray, l2: float, iters: int = 30
                 ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """L2 logistic by Newton/IRLS on standardised features; the intercept is unpenalised.
    Returns (weights incl. intercept, mean, std) -- the scaling is the TRAINING fold's."""
    mu = x.mean(axis=0)
    sd = x.std(axis=0)
    sd[sd < 1e-12] = 1.0
    z = np.column_stack([np.ones(len(x)), (x - mu) / sd])
    w = np.zeros(z.shape[1])
    pen = np.full(z.shape[1], float(l2))
    pen[0] = 0.0
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(z @ w, -30, 30)))
        g = z.T @ (p - y) + pen * w
        hm = (z * (p * (1 - p))[:, None]).T @ z + np.diag(pen) + 1e-9 * np.eye(len(w))
        step = np.linalg.solve(hm, g)
        w -= step
        if float(np.abs(step).max()) < 1e-8:
            break
    return w, mu, sd


def predict(model: tuple[np.ndarray, np.ndarray, np.ndarray], x: np.ndarray) -> np.ndarray:
    w, mu, sd = model
    z = np.column_stack([np.ones(len(x)), (x - mu) / sd])
    return np.asarray(1.0 / (1.0 + np.exp(-np.clip(z @ w, -30, 30))), dtype=float)


def auc(y: np.ndarray, p: np.ndarray) -> float | None:
    """Mann-Whitney AUC with tie-averaged ranks; None when one class is absent."""
    pos, neg = int(y.sum()), int(len(y) - y.sum())
    if pos == 0 or neg == 0:
        return None
    ranks = pd.Series(p).rank(method="average").to_numpy()
    return float((ranks[y == 1].sum() - pos * (pos + 1) / 2.0) / (pos * neg))


def bet_multiplier(p: np.ndarray | float, p0: float, n_train: int) -> np.ndarray:
    """AFML bet size, two-sided about the sleeve's own base rate, shrunk by n / (n + K)."""
    pa = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    z = (pa - p0) / np.sqrt(pa * (1 - pa)) * (n_train / (n_train + K_SHRINK))
    from scipy.stats import norm
    m = 2.0 * norm.cdf(z) - 1.0
    return np.asarray(np.where(m >= 0, 1.0 + m * (MAX_MULT - 1.0), 1.0 + m), dtype=float)


def purged_train_index(entries: Sequence[pd.Timestamp], exits: Sequence[pd.Timestamp],
                       test_start: pd.Timestamp, embargo_h: float = EMBARGO_H) -> list[int]:
    """Training rows for a test block beginning at test_start: only trades that had EXITED at
    least embargo_h before it. A trade overlapping the block (or its embargo) is purged."""
    edge = test_start - pd.Timedelta(hours=embargo_h)
    return [i for i, (e, x) in enumerate(zip(entries, exits, strict=True))
            if e < test_start and x <= edge]


def walk_forward(x: np.ndarray, y: np.ndarray, entries: Sequence[pd.Timestamp],
                 exits: Sequence[pd.Timestamp], l2: float
                 ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """OOS P(win) and multiplier for every row a purged, expanding-window model could score.
    Returns (oos row indices, p, multiplier). Rows are chronological by entry."""
    n = len(y)
    idx_out: list[int] = []
    p_out: list[float] = []
    m_out: list[float] = []
    if n <= MIN_TRAIN:
        return np.array([], dtype=int), np.array([]), np.array([])
    edges = np.linspace(MIN_TRAIN, n, N_FOLDS + 1).astype(int)
    for a, b in zip(edges[:-1], edges[1:], strict=True):
        if b <= a:
            continue
        tr = purged_train_index(entries, exits, entries[a])
        if len(tr) < MIN_TRAIN or len(set(y[tr].tolist())) < 2:
            continue
        model = fit_logistic(x[tr], y[tr], l2)
        p = predict(model, x[a:b])
        m = bet_multiplier(p, float(y[tr].mean()), len(tr))
        idx_out.extend(range(a, b))
        p_out.extend(p.tolist())
        m_out.extend(m.tolist())
    return np.asarray(idx_out, dtype=int), np.asarray(p_out), np.asarray(m_out)


def _elog(r: np.ndarray, m: np.ndarray, f: float) -> np.ndarray:
    return np.asarray(np.log(np.maximum(1.0 + f * m * r, 1e-9)), dtype=float)


def score_oos(y: np.ndarray, r: np.ndarray, p: np.ndarray, m: np.ndarray, f: float,
              base_rate: float) -> dict[str, Any]:
    """OOS AUC / Brier and the heat-neutral sized-vs-unsized uplift with its t-statistic."""
    n = len(y)
    mbar = float(m.mean()) if n else 0.0
    mh = m / mbar if mbar > 1e-9 else np.ones_like(m)
    d = _elog(r, mh, f) - _elog(r, np.ones_like(r), f)
    se = float(d.std(ddof=1) / math.sqrt(n)) if n > 1 else 0.0
    t = float(d.mean() / se) if se > 0 else 0.0
    brier = float(np.mean((p - y) ** 2))
    brier0 = float(np.mean((base_rate - y) ** 2))
    return {
        "n_oos": n, "auc": auc(y, p), "brier": round(brier, 5),
        "brier_base_rate": round(brier0, 5),
        "brier_skill": (round(1.0 - brier / brier0, 4) if brier0 > 0 else None),
        "mean_r_unsized": round(float(r.mean()), 5),
        "mean_r_sized_raw": round(float((m * r).mean()), 5),
        "mean_r_sized_heat_neutral": round(float((mh * r).mean()), 5),
        "elogw_unsized_per_trade": float(_elog(r, np.ones_like(r), f).mean()),
        "elogw_sized_raw_per_trade": float(_elog(r, m, f).mean()),
        "elogw_sized_heat_neutral_per_trade": float(_elog(r, mh, f).mean()),
        "delta_elogw_per_trade": float(d.mean()), "t_uplift": round(t, 3),
        "mean_multiplier_raw": round(mbar, 4),
        "share_sized_down": round(float((mh < 1.0).mean()), 4) if n else None,
        "share_skipped": round(float((mh < 0.05).mean()), 4) if n else None,
    }


# ------------------------------------------------------------------ inputs
def _symbol_of(stem: str, sleeves: Mapping[str, Mapping[str, Any]]) -> str:
    row = sleeves.get(stem)
    if row and row.get("symbol"):
        return str(row["symbol"]).upper()
    if stem.startswith("external."):
        return stem.split(".")[1].upper()
    if ".json." in stem:      # qquant.hunt16.json.AUDNZD_...
        stem = stem.rsplit(".json.", 1)[1]
    head = stem.split("_")[0].split(".")[0].upper()
    return _ALIASES.get(head, head)


#: Ledger-name prefixes that are not the registry symbol (the scalp lane's `xau_m5_*`).
_ALIASES = {"XAU": "XAUUSD", "XAG": "XAGUSD"}


def family_of(stem: str, symbol: str, sleeves: Mapping[str, Mapping[str, Any]]) -> str:
    """The pool key: the ledger's spec without its symbol (`CHFDKK_overnight_gap_decay_asia`
    -> `overnight_gap_decay_asia`); a named sleeve row's family|session when it has one."""
    row = sleeves.get(stem) or {}
    if row.get("family"):
        return f"{row.get('family')}|{row.get('session') or 'all'}"
    s = stem
    if s.startswith("external."):
        s = ".".join(s.split(".")[2:]) or s
    else:
        if ".json." in s:
            s = s.rsplit(".json.", 1)[1]
        head = s.split("_")[0]
        if head.upper() == symbol or _ALIASES.get(head.upper()) == symbol:
            s = s[len(head) + 1:]
    return s or stem


def load_sleeves(path: Path = SLEEVES) -> dict[str, dict[str, Any]]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    rows = doc.get("sleeves", []) if isinstance(doc, Mapping) else []
    return {str(r.get("name")): r for r in rows if isinstance(r, Mapping) and r.get("name")}


def load_ledgers(dirs: Sequence[Path] = LEDGER_DIRS) -> dict[str, tuple[Path, list[Trade]]]:
    """stem -> (path, trades); where a stem is in more than one root the fuller ledger wins."""
    out: dict[str, tuple[Path, list[Trade]]] = {}
    for d in dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("ledger_*.json")):
            try:
                rows = json.loads(f.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            tr = parse_trades(rows)
            stem = f.stem.removeprefix("ledger_")
            if stem not in out or len(tr) > len(out[stem][1]):
                out[stem] = (f, tr)
    return out


def load_bars(symbol: str, dirs: Sequence[Path] = BAR_DIRS) -> pd.DataFrame | None:
    for d in dirs:
        p = d / f"{symbol}_H1.parquet"
        if not p.exists():
            continue
        try:
            df = pd.read_parquet(p)
        except (OSError, ValueError, ImportError):
            continue
        if df.empty or not {"high", "low", "close"} <= set(df.columns):
            continue
        df.index = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
        df = df[~df.index.isna()].sort_index()
        return df[~df.index.duplicated(keep="last")]
    return None


# ------------------------------------------------------------------ trials
def _trial_id(sleeve: str, scope: str, cfg: Mapping[str, float]) -> str:
    ck = ",".join(f"{k}={cfg[k]}" for k in sorted(cfg))
    return f"meta_label:{sleeve}:{scope}:{ck}"


def _read_trials(path: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(ln) for ln in path.read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        return []


def charge(new: Sequence[dict[str, Any]], path: Path) -> dict[str, Any]:
    """Append this pass's trials and census the LIFETIME union (distinct trial ids)."""
    from libs.research import trial_ledger as TL
    from research.multiplicity import expected_max_z
    old = _read_trials(path)
    seen = {str(r.get("trial_id")) for r in old}
    fresh = [r for r in new if r["trial_id"] not in seen]
    err = None
    if fresh:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                for r in fresh:
                    fh.write(json.dumps(r, sort_keys=True) + "\n")
        except OSError as exc:
            err = str(exc)
    union: dict[str, dict[str, Any]] = {str(r.get("trial_id")): r for r in old}
    for r in new:
        union[r["trial_id"]] = r
    trials = [TL.Trial(trial_id=k, family=str(v.get("family") or "meta_label"),
                       descriptors={str(a): str(b) for a, b in (v.get("descriptors") or {}).items()},
                       params=dict(v.get("params") or {}))
              for k, v in union.items()]
    cen = TL.census(trials)
    n_eff = max(1.0, float(cen.n_effective))
    return {"n_raw_this_pass": len(new), "n_raw_lifetime": len(union),
            "n_effective": round(n_eff, 3),
            "expected_max_z": round(expected_max_z(max(1, math.ceil(n_eff))), 4),
            "census": cen.to_dict(), "ledger": str(path), "ledger_error": err,
            "rule": ("every sleeve x model configuration evaluated is one trial; the uplift t is "
                     "deflated by E[max Z] over the lifetime effective count")}


# ------------------------------------------------------------------ one scope
def _evaluate_scope(trades: Sequence[tuple[str, Trade]], bars_of: Mapping[str, pd.DataFrame],
                    hist_of: Mapping[str, Sequence[Trade]]
                    ) -> dict[str, Any]:
    """Build the chronological design for a set of (sleeve, trade) and walk every config."""
    rows: list[list[float]] = []
    meta: list[tuple[str, Trade]] = []
    for sl, tr in trades:
        f = bar_features(bars_of[sl], tr.entry, tr.side)
        if f is None:
            continue
        f["trail_win"] = trail_win(hist_of[sl], tr.entry)
        rows.append([float(f[k]) for k in FEATURES])
        meta.append((sl, tr))
    order = sorted(range(len(meta)), key=lambda i: (meta[i][1].entry, meta[i][1].exit))
    x = np.asarray([rows[i] for i in order], dtype=float).reshape(-1, len(FEATURES))
    meta = [meta[i] for i in order]
    y = np.asarray([1.0 if t.r > 0 else 0.0 for _, t in meta])
    r = np.asarray([t.r for _, t in meta])
    entries = [t.entry for _, t in meta]
    exits = [t.exit for _, t in meta]
    by_cfg = {}
    for cfg in MODEL_CONFIGS:
        oi, p, m = walk_forward(x, y, entries, exits, float(cfg["l2"]))
        by_cfg[json.dumps(cfg, sort_keys=True)] = (cfg, oi, p, m)
    return {"x": x, "y": y, "r": r, "meta": meta, "by_cfg": by_cfg}


def _current(x: np.ndarray, y: np.ndarray, cfg: Mapping[str, float], bars: pd.DataFrame,
             hist: Sequence[Trade], oos_mean_mult: float) -> dict[str, Any] | None:
    """The multiplier for the sleeve's NEXT signal, per side, at the latest complete bar."""
    if len(set(y.tolist())) < 2:
        return None
    model = fit_logistic(x, y, float(cfg["l2"]))
    t_now = bars.index[-1] + pd.Timedelta(hours=1)
    out: dict[str, Any] = {"as_of_bar_close": str(t_now)}
    for name, side in (("long", 1), ("short", -1)):
        f = bar_features(bars, t_now, side)
        if f is None:
            return None
        f["trail_win"] = trail_win(hist, t_now)
        p = predict(model, np.asarray([[float(f[k]) for k in FEATURES]]))
        m = float(bet_multiplier(p, float(y.mean()), len(y))[0])
        m = m / oos_mean_mult if oos_mean_mult > 1e-9 else 1.0
        out[name] = round(float(min(MAX_MULT, max(0.0, m))), 3)
        out[f"p_win_{name}"] = round(float(p[0]), 4)
    return out


# ------------------------------------------------------------------ the pass
def run(*, ledger_dirs: Sequence[Path] = LEDGER_DIRS, bar_dirs: Sequence[Path] = BAR_DIRS,
        sleeves_path: Path = SLEEVES, out: Path | None = REPORT,
        trials_path: Path = TRIALS, budget_s: float = BUDGET_S) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + float(budget_s)
    sleeves = load_sleeves(sleeves_path)
    ledgers = load_ledgers(ledger_dirs)
    live = sorted(n for n, r in sleeves.items() if str(r.get("status")) == "LIVE")
    stems = sorted(set(ledgers) | set(live))
    rows: dict[str, dict[str, Any]] = {}
    bars_of: dict[str, pd.DataFrame] = {}
    hist_of: dict[str, list[Trade]] = {}
    fam_of: dict[str, str] = {}
    bars_cache: dict[str, pd.DataFrame | None] = {}
    for st in stems:
        sym = _symbol_of(st, sleeves)
        fam = family_of(st, sym, sleeves)
        trades = ledgers.get(st, (None, []))[1]
        row = sleeves.get(st) or {}
        rf = float(row.get("risk_frac") or 0.0) or DEFAULT_RISK_FRAC
        rows[st] = {"symbol": sym, "family": fam, "live": st in live,
                    "status": row.get("status") or "SHADOW_LEDGER",
                    "ledger": (str(ledgers[st][0].relative_to(ROOT))
                               if st in ledgers and ledgers[st][0].is_relative_to(ROOT)
                               else (str(ledgers[st][0]) if st in ledgers else None)),
                    "n_trades": len(trades), "risk_frac": rf,
                    "risk_frac_source": "sleeves.json" if row.get("risk_frac") else
                    "DEFAULT_RISK_FRAC (sizing.BASE_RISK_FRAC)",
                    "verdict": "UNMEASURED", "multiplier": 1.0, "current_multiplier": None}
        if sym not in bars_cache:
            bars_cache[sym] = load_bars(sym, bar_dirs)
        b = bars_cache[sym]
        if not trades:
            rows[st]["why"] = "no ledger trades"
            continue
        if b is None:
            rows[st]["why"] = f"no H1 bars for {sym}"
            continue
        bars_of[st], hist_of[st], fam_of[st] = b, trades, fam

    # scope: per sleeve when thick, else the family pool
    pools: dict[str, list[str]] = {}
    for st in bars_of:
        pools.setdefault(fam_of[st], []).append(st)
    scope_of: dict[str, str] = {}
    for st in bars_of:
        if len(hist_of[st]) >= MIN_SLEEVE_TRADES:
            scope_of[st] = f"sleeve:{st}"
        elif sum(len(hist_of[s]) for s in pools[fam_of[st]]) >= MIN_POOL_TRADES and \
                len(pools[fam_of[st]]) > 1:
            scope_of[st] = f"family:{fam_of[st]}"
        else:
            rows[st]["why"] = (f"{len(hist_of[st])} trades (< {MIN_SLEEVE_TRADES}) and family "
                               f"'{fam_of[st]}' pools {sum(len(hist_of[s]) for s in pools[fam_of[st]])}"
                               f" over {len(pools[fam_of[st]])} sleeve(s) (< {MIN_POOL_TRADES})")
    scopes: dict[str, dict[str, Any]] = {}
    pending: list[dict[str, Any]] = []
    with _one_native_thread():
        for scope in sorted(set(scope_of.values())):
            if time.monotonic() > deadline:
                scopes[scope] = {"verdict": "UNMEASURED", "why": "budget exhausted"}
                continue
            members = ([scope.split(":", 1)[1]] if scope.startswith("sleeve:")
                       else [s for s in pools[scope.split(":", 1)[1]]
                             if scope_of.get(s) == scope])
            scopes[scope] = _evaluate_scope([(s, t) for s in members for t in hist_of[s]],
                                            bars_of, hist_of)
        for st, scope in sorted(scope_of.items()):
            sc = scopes.get(scope) or {}
            if "by_cfg" not in sc:
                rows[st]["why"] = sc.get("why", "scope not evaluated")
                continue
            rows[st]["scope"] = scope
            for _, (cfg, _oi, _p, _m) in sc["by_cfg"].items():
                pending.append({"trial_id": _trial_id(st, scope, cfg),
                                "family": f"meta_label:{fam_of[st]}",
                                "descriptors": {"symbol": rows[st]["symbol"],
                                                "mechanism": fam_of[st],
                                                "model_family": "l2_logistic",
                                                "representation": scope},
                                "params": dict(cfg),
                                "generated_utc": datetime.now(tz=UTC).isoformat()})
        trials = charge(pending, trials_path)
        emz = float(trials["expected_max_z"])
        for st, scope in sorted(scope_of.items()):
            sc = scopes.get(scope) or {}
            if "by_cfg" not in sc:
                continue
            meta = sc["meta"]
            mine = np.asarray([i for i, (s, _) in enumerate(meta) if s == st], dtype=int)
            best: dict[str, Any] | None = None
            per_cfg: dict[str, Any] = {}
            for ck, (cfg, oi, p, m) in sc["by_cfg"].items():
                sel = np.isin(oi, mine)
                if int(sel.sum()) < 2:
                    per_cfg[ck] = {"n_oos": int(sel.sum()), "verdict": "UNMEASURED"}
                    continue
                ii = oi[sel]
                y, r = sc["y"][ii], sc["r"][ii]
                res = score_oos(y, r, p[sel], m[sel], rows[st]["risk_frac"],
                                float(sc["y"][: max(1, int(ii.min()))].mean()))
                res["t_deflated"] = round(res["t_uplift"] - emz, 3)
                res["config"] = cfg
                res["_mean_mult"] = float(m[sel].mean())
                per_cfg[ck] = {k: v for k, v in res.items() if not k.startswith("_")}
                if best is None or res["t_deflated"] > best["t_deflated"]:
                    best = res
            rows[st]["configs"] = per_cfg
            rows[st]["n_with_features"] = int(mine.size)
            if best is None or best["n_oos"] < MIN_OOS:
                rows[st]["why"] = (f"{0 if best is None else best['n_oos']} OOS trades "
                                   f"(< {MIN_OOS}) after the purged walk-forward")
                continue
            rows[st]["oos"] = {k: v for k, v in best.items() if not k.startswith("_")}
            a = best["auc"]
            gain = bool(best["t_deflated"] > T_GAIN and a is not None and a > 0.5)
            rows[st]["verdict"] = "GAIN" if gain else "NO_GAIN"
            rows[st]["why"] = (f"heat-neutral dE[log W]/trade {best['delta_elogw_per_trade']:.2e}, "
                               f"t {best['t_uplift']:.2f} deflated {best['t_deflated']:.2f} "
                               f"(bar {T_GAIN}), OOS AUC {a if a is None else round(a, 3)}")
            if gain:
                ii = np.asarray([i for i, (s, _) in enumerate(meta) if s == st] if
                                scope.startswith("sleeve:") else range(len(meta)), dtype=int)
                cur = _current(sc["x"][ii], sc["y"][ii], best["config"], bars_of[st],
                               hist_of[st], best["_mean_mult"])
                if cur is None:
                    rows[st]["verdict"] = "UNMEASURED"
                    rows[st]["why"] += "; current features unreadable at the latest bar"
                else:
                    rows[st]["current_multiplier"] = cur
                    rows[st]["multiplier"] = None   # per side: see current_multiplier
    for st in rows:
        if rows[st]["verdict"] != "GAIN":
            rows[st]["multiplier"] = 1.0
            rows[st]["current_multiplier"] = {"long": 1.0, "short": 1.0,
                                              "why": "no GAIN verdict: sizing is never changed "
                                                     "without proof"}
    verdicts = [r["verdict"] for r in rows.values()]
    doc: dict[str, Any] = {
        "schema": SCHEMA, "generated_utc": datetime.now(tz=UTC).isoformat(),
        "runtime_s": round(time.monotonic() - t0, 2), "budget_s": budget_s,
        "features": list(FEATURES), "feature_rule": ("recomputed from H1 bars whose close is at "
                                                     "or before entry_time; trail_win counts "
                                                     "only trades CLOSED before entry"),
        "label": "won = r_multiple > 0",
        "model": "L2 logistic (numpy IRLS), standardised on the training fold",
        "model_configs": list(MODEL_CONFIGS),
        "validation": {"scheme": "expanding walk-forward, purged", "folds": N_FOLDS,
                       "min_train": MIN_TRAIN, "embargo_h": EMBARGO_H, "min_oos": MIN_OOS,
                       "min_sleeve_trades": MIN_SLEEVE_TRADES,
                       "min_pool_trades": MIN_POOL_TRADES},
        "bet_size": {"rule": "m = 2 Phi(z) - 1, z = (p - p0)/sqrt(p(1-p)) * n/(n+K); "
                             "mult = 1 + m(MAX-1) if m >= 0 else 1 + m; heat-neutral "
                             "(divided by the OOS mean) for the verdict and the live reading",
                     "p0": "training base win rate", "K": K_SHRINK, "range": [0.0, MAX_MULT]},
        "verdict_rule": (f"GAIN iff heat-neutral OOS dE[log W] t - E[max Z](n_eff trials) > "
                         f"{T_GAIN}, OOS AUC > 0.5 and n_oos >= {MIN_OOS}"),
        "trials": trials,
        "modifier": {"name": "meta_label_bet_size", "lo": 0.0, "hi": MAX_MULT,
                     "kind": "two_sided", "registered": False,
                     "why_not": CONSUMPTION["registry"]},
        "consumption": CONSUMPTION,
        "missed_growth": [{"sleeve": st, "verdict": r["verdict"],
                           "delta_elogw_per_trade_oos": (r.get("oos") or {}).get(
                               "delta_elogw_per_trade"),
                           "share_sized_down": (r.get("oos") or {}).get("share_sized_down"),
                           "applied": False}
                          for st, r in sorted(rows.items()) if r.get("oos")],
        "summary": {"n_sleeves": len(rows), "live_sleeves": len(live),
                    "n_trades": sum(int(r["n_trades"]) for r in rows.values()),
                    "n_measured": sum(v in ("GAIN", "NO_GAIN") for v in verdicts),
                    "n_gain": verdicts.count("GAIN"), "n_no_gain": verdicts.count("NO_GAIN"),
                    "n_unmeasured": verdicts.count("UNMEASURED"),
                    "scopes": sorted(set(scope_of.values()))},
        "sleeves": rows,
    }
    doc["status"] = ("MEASURED" if doc["summary"]["n_measured"] else
                     "UNMEASURED: no sleeve has enough trades with bars")
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        tmp.replace(out)
    return doc


def digest(doc: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(doc.get("summary"), sort_keys=True).encode()).hexdigest()[:12]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--out", type=Path, default=REPORT)
    a = ap.parse_args(argv)
    doc = run(out=a.out, budget_s=a.budget_s)
    s = doc["summary"]
    print(f"meta_labeler: {doc['status']} sleeves={s['n_sleeves']} live={s['live_sleeves']} "
          f"gain={s['n_gain']} no_gain={s['n_no_gain']} unmeasured={s['n_unmeasured']} "
          f"trials={doc['trials']['n_raw_lifetime']} ({doc['runtime_s']}s) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
