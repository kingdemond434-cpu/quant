#!/usr/bin/env python3
"""THE CONTRACT: does regime detection driving allocation raise out-of-sample E[log W]?

    python desks/mt5/research/regime_allocation_contract.py [--step 21] [--train 750] [--out PATH]

Admission rule: a subsystem ships only with a measured contract showing gain. This is the contract
for `libs.regime.control_room` feeding the allocator, and it doubles as the first out-of-sample
measurement of the regime conditioning the allocator ALREADY does (gold's HMM conditioning the
worlds, the macro kernel tilting the posterior), which had never been scored against a book
without it.

THE REVERSE-ENGINEERED MECHANISM. The Korean competition winner's three axes, rebuilt on the
desk's own instruments: (1) volatility and liquidity diagnose trend vs range per instrument;
(2) the diagnosis re-weights STRATEGIES, so every instrument carries two opposite sleeves -- a
trend sleeve (63-day time-series momentum) and a range sleeve (5-day reversal) -- and the regime
has to decide between them; (3) the weights come out of a geometric (max E[log W]) solve, here the
desk's own live solver `libs.portfolio.robust_elog.optimise`, not a re-implementation.

THE BOOKS, all at the same total heat so only COMPOSITION differs, re-solved every `--step` days
on the trailing `--train` days and held on the next `--step` days nobody has seen:

    equal           1/N heat in every sleeve
    geo             the live solver, no regime input
    geo_hmm         + gold daily HMM conditioning the worlds, fitted point-in-time (the live
                      allocator's `regime_state` recipe: filtered labels, posterior blended with
                      history by engine confidence, floored 0.08, capped 0.60)
    geo_asset       + the control room's per-instrument kernel as each sleeve's `macro_w`
    geo_hmm_asset   both
    geo_macro       + the FRED dollar/risk/rates kernel, point-in-time (only where the archive
    geo_macro_asset   exists -- the box; UNMEASURED elsewhere, never a zero)
    switch          the naive rule: fund the trend sleeve where the instrument trends and the
                      range sleeve where it ranges, equal heat -- what a hard regime switch buys

THE UNIVERSE. On the box the books are solved over the allocator's OWN daily-R matrix
(`pf_allocator_cache/daily_r.parquet`, the desk's real sleeves) and only that run can admit the
kernel (`admits`). Off the box it falls back to a bench of trend/range pairs built from bars,
which shows whether the kernel moves composition the right way but cannot license sizing.

WHO READS `admits`. Nothing on this branch. The reader is the allocator, a money-path file, so it
ships as the desktop-pass patch `patches/control_room/control_room_regime_kernel.patch`: once
applied, `pf_allocator._control_room_admitted()` multiplies the kernel in only while this file
says `admits: true` and is under 14 days old. Until that patch lands the switch is MANUAL -- a
GAIN here changes no sizing by itself.

HEADLINE, DECLARED BEFORE THE RUN: geo_asset minus geo, mean daily log growth, stationary block
bootstrap (mean block 10 days). GAIN needs the 90% interval above zero AND geo_asset above equal.
Every arm is reported, the headline is never swapped for the best one, and the arm count is
recorded as the trial count.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(BASE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, optimise  # noqa: E402
from libs.regime import control_room as cr  # noqa: E402

OUT = BASE / "reports" / "REGIME_ALLOCATION_CONTRACT.json"
#: The allocator's own daily-R matrix (`pf_allocator.build_evidence`), present on the box only.
DESK_MATRIX = BASE / "data" / "pf_allocator_cache" / "daily_r.parquet"
MIN_TRAIN_OBS = 40
ASSETS: tuple[str, ...] = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
                           "EURJPY", "GBPJPY", "AUDJPY", "XAUUSD", "XAGUSD")
TOTAL_HEAT = 0.25
#: The share of total heat one sleeve may take -- the live gateway's own bound when importable.
try:
    from mt5desk.gateway_config_fallback import MAX_SLEEVE_HEAT_SHARE as _SHARE  # noqa: E402
    SLEEVE_SHARE = float(_SHARE)
except Exception:  # pragma: no cover - the research snapshot without the desk package
    SLEEVE_SHARE = 0.35
COST_BPS = 1.0
MOM_WIN, REV_WIN, SIG_WIN = 63, 5, 20
#: One R is a stop this many trailing daily sigmas away -- the unit the desk's own sleeves report
#: in, so TOTAL_HEAT means what it means on the box (equity at risk across the book). At one
#: sigma the equal book ran ~8%/day of account volatility and every crisis world wiped out,
#: which left the solver unable to move off its starting point.
R_SIGMAS = 3.0
HEADLINE = ("geo_asset", "geo")
REGIME_MIN_SHARE, REGIME_MAX_SHARE = 0.08, 0.60


def sleeves(labels: dict[str, pd.DataFrame], closes: pd.DataFrame) -> pd.DataFrame:
    """Daily R per sleeve: position chosen at t-1's close, 1R = R_SIGMAS trailing daily sigmas."""
    lr = np.log(closes).diff()
    sig = lr.rolling(SIG_WIN).std().shift(1)
    out = {}
    for s in closes.columns:
        mom = np.sign(lr[s].rolling(MOM_WIN).sum().shift(1))
        rev = -np.sign(lr[s].rolling(REV_WIN).sum().shift(1))
        for kind, pos in (("trend", mom), ("range", rev)):
            turn = pos.diff().abs().fillna(0.0)
            r = (pos * lr[s] - turn * COST_BPS * 1e-4) / (R_SIGMAS * sig[s])
            out[f"{s}_{kind}"] = r
    return pd.DataFrame(out).replace([np.inf, -np.inf], np.nan)


def load(assets: tuple[str, ...]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    closes, labels = {}, {}
    for s in assets:
        p = cr.bar_path(s)
        if p is None:
            continue
        d = cr.daily_frame(pd.read_parquet(p))
        closes[s] = d["close"]
        labels[s] = cr.label_days(d)
    panel = pd.DataFrame(closes).sort_index()
    panel = panel.ffill().dropna()
    return panel, labels


def load_desk(path: Path | None = None) -> tuple[pd.DataFrame, dict[str, pd.DataFrame],
                                                 pd.DataFrame] | None:
    """The desk's REAL sleeves: the allocator's daily-R matrix, NaN before a sleeve was born.

    Returns (sleeve matrix, labels per symbol, gold closes) or None when the matrix is absent.
    A sleeve's instrument is the first `_` part of its name, the allocator's own convention.
    """
    path = path or DESK_MATRIX
    if not path.exists():
        return None
    m = pd.read_parquet(path)
    m.index = [str(x)[:10] for x in m.index]
    m = m.sort_index()
    syms = sorted({str(c).split("_")[0] for c in m.columns} | {"XAUUSD"})
    labels, closes = {}, {}
    for s in syms:
        p = cr.bar_path(s)
        if p is None:
            continue
        d = cr.daily_frame(pd.read_parquet(p))
        labels[s] = cr.label_days(d)
        closes[s] = d["close"]
    return m, labels, pd.DataFrame(closes).sort_index().ffill()


def hmm_conditioning(gold: pd.Series, train_days: list[str]) -> tuple[tuple[str, ...],
                                                                        tuple[tuple[str, float],
                                                                              ...]] | None:
    """Gold-HMM regime labels on the training days and the tempered probability now, PIT."""
    try:
        from libs.regime.engine import RegimeEngine
    except Exception:
        return None
    g = gold[gold.index <= train_days[-1]].iloc[-max(len(train_days) + 60, 500):]
    try:
        eng = RegimeEngine().fit(g)
    except Exception:
        return None
    lab = {j: str(ch["label"]) for j, ch in eng.hmm_char.items()}
    by_day = {d: lab[int(j)] for d, j in zip(g.index, eng.filtered_states, strict=True)}
    labels = tuple(by_day.get(d, "") for d in train_days)
    if sum(1 for x in labels if x) < 0.5 * len(labels):
        return None
    post: dict[str, float] = {}
    for j, pj in enumerate(eng.posteriors[-1]):
        post[lab[j]] = post.get(lab[j], 0.0) + float(pj)
    freq: dict[str, float] = {}
    for v in by_day.values():
        freq[v] = freq.get(v, 0.0) + 1.0
    tot = sum(freq.values()) or 1.0
    conf = float(str(eng.current().get("confidence") or 0.0))
    keys = sorted(set(post) | set(freq))
    probs = {k: max(conf * post.get(k, 0.0) + (1 - conf) * freq.get(k, 0.0) / tot,
                    REGIME_MIN_SHARE) for k in keys}
    z = sum(probs.values())
    probs = {k: v / z for k, v in probs.items()}
    top = max(probs, key=lambda k: probs[k])
    if probs[top] > REGIME_MAX_SHARE:
        spill, rest = probs[top] - REGIME_MAX_SHARE, sum(v for k, v in probs.items() if k != top)
        probs = {k: REGIME_MAX_SHARE if k == top else v + spill * v / (rest or 1.0)
                 for k, v in probs.items()}
    return labels, tuple(sorted(probs.items(), key=lambda kv: -kv[1]))


def macro_weights(train_days: list[str], asof: str) -> np.ndarray | None:
    """The FRED dollar/risk/rates kernel with TODAY = the newest print on or before `asof`."""
    try:
        from libs.portfolio import macro_state as ms
        doc = ms.daily_states()
    except Exception:
        return None
    states = doc.get("states") or {}
    use = [d for d in ms.KERNEL_DIMS if states.get(d)]
    if not use:
        return None
    # KNOWN, NOT VALID, DATES, READ THROUGH THE BITEMPORAL STORE (data_os, Tier S AC3): each
    # FRED state becomes `BitemporalStore` rows (knowledge = `data_os.knowledge_at` for that
    # state's own FRED series). TODAY is `latest_known` at the start of `asof` -- the newest
    # print published before that day opened -- and a training day reads only the print whose knowledge time first falls
    # inside it, so neither "today" nor any training day's kernel reads a print that did not yet
    # exist.
    from datetime import UTC as _UTC
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    from libs.tiers import data_os

    def _known_day(kt: str) -> str:
        at = _dt.fromisoformat(kt)
        return (at.date() + _td(days=1) if at.time() != _dt.min.time() else at.date()).isoformat()

    asof_open = _dt.fromisoformat(str(asof)[:10]).replace(tzinfo=_UTC)
    w = np.ones(len(train_days))
    for d in use:
        raw = states[d]
        try:
            ser = pd.Series([float(v) for v in raw.values()],
                            index=pd.to_datetime([str(k)[:10] for k in raw], utc=True))
        except (TypeError, ValueError):
            return None
        # THE DIMENSION'S OWN FRED SERIES, so its own release timing applies (2026-10-07): with
        # no `series_id` every state read the flat 27h daily lag, and the WEEKLY-posted dollar
        # index (DTWEXBGS, H.10) entered the kernel about a week before it was published.
        store = data_os.store_from_series(ser, source="fred_macro", entity=d, attribute="state",
                                          series_id=ms.SERIES.get(d))
        by = {_known_day(r.knowledge_time): r.value for r in store.rows}
        now = store.latest_known(d, "state", [asof_open])[0]
        if now is None:
            return None
        today = float(now.value)
        for i, day in enumerate(train_days):
            r = by.get(day)
            if r is None:
                w[i] = np.nan
                continue
            z = (float(r) - today) / ms.BANDWIDTH
            w[i] *= math.exp(-0.5 * z * z)
    return w


def _evidence(train: pd.DataFrame, kern: dict[str, np.ndarray] | None,
              macro: np.ndarray | None) -> list[SleeveEvidence]:
    ev = []
    for c in train.columns:
        sym = str(c).split("_")[0]
        kind = str(c).rsplit("_", 1)[-1]
        w = np.array([], dtype=float)
        if kern is not None and sym in kern and kern[sym].size == len(train):
            w = kern[sym].copy()
        if macro is not None:
            w = macro.copy() if w.size == 0 else w * macro
        ev.append(SleeveEvidence(name=str(c), daily_r=train[c].to_numpy(float), family=kind,
                                 symbol=sym, cost_r=0.02, macro_w=w,
                                 mechanism=f"{kind}_following" if kind == "trend"
                                 else "short_term_reversal"))
    return ev


def _solve(ev: list[SleeveEvidence], cfg: WorldConfig) -> dict[str, float]:
    res = optimise(ev, hard_cap=TOTAL_HEAT, target=TOTAL_HEAT, cfg=cfg,
                   max_per_sleeve=SLEEVE_SHARE * TOTAL_HEAT, iterations=250)
    return dict(res.heat)


def block_bootstrap_ci(x: np.ndarray, *, block: float = 10.0, reps: int = 2000,
                       alpha: float = 0.10, seed: int = 7) -> tuple[float, float]:
    """Stationary (Politis-Romano) bootstrap interval for the mean of a daily series."""
    rng = np.random.default_rng(seed)
    n = x.size
    p = 1.0 / block
    means = np.empty(reps)
    for b in range(reps):
        idx = np.empty(n, dtype=int)
        i = rng.integers(n)
        for t in range(n):
            if t == 0 or rng.random() < p:
                i = rng.integers(n)
            else:
                i = (i + 1) % n
            idx[t] = i
        means[b] = x[idx].mean()
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


def summarise(logg: np.ndarray) -> dict[str, float]:
    eq = np.cumsum(logg)
    dd = float((eq - np.maximum.accumulate(eq)).min()) if eq.size else 0.0
    sd = float(logg.std(ddof=1)) if logg.size > 1 else 0.0
    return {"days": int(logg.size), "mean_log_per_day": round(float(logg.mean()), 8),
            "annual_log_growth": round(float(logg.mean()) * 252, 5),
            "sharpe": round(float(logg.mean()) / sd * math.sqrt(252), 4) if sd > 0 else 0.0,
            "max_drawdown_log": round(dd, 5)}


def run(step: int = 21, train_n: int = 750, n_worlds: int = 128, n_rows: int = 256,
        assets: tuple[str, ...] = ASSETS, with_hmm: bool = True,
        max_steps: int | None = None, universe: str = "auto") -> dict[str, Any]:
    """`universe`: "desk" = the allocator's real sleeves (box), "bars" = the trend/range pairs
    built from bars, "auto" = desk when the matrix exists, else bars."""
    t0 = time.time()
    desk = load_desk() if universe in ("auto", "desk") else None
    if universe == "desk" and desk is None:
        raise FileNotFoundError(f"{DESK_MATRIX} absent: the desk universe runs on the box")
    if desk is not None:
        r, labels, closes = desk
        used = "desk"
    else:
        closes, labels = load(assets)
        r = sleeves(labels, closes).dropna(how="all")
        r = r.iloc[MOM_WIN + SIG_WIN:]
        used = "bars"
    days = list(r.index)
    macro_live = macro_weights(days[:5], days[4]) is not None
    arms = ["equal", "geo", "geo_asset", "switch"]
    if with_hmm:
        arms += ["geo_hmm", "geo_hmm_asset"]
    if macro_live:
        arms += ["geo_macro", "geo_macro_asset"]
    cfg0 = WorldConfig(n_worlds=n_worlds, n_rows=n_rows)
    realised: dict[str, list[float]] = {a: [] for a in arms}
    oos_days: list[str] = []
    books: list[dict[str, Any]] = []
    starts = list(range(train_n, len(days) - 1, step))
    if max_steps:
        starts = starts[:max_steps]
    for k, s in enumerate(starts):
        # NaN KEPT IN TRAINING: a day before a sleeve was born is not a zero-return day
        # (`SleeveEvidence.own_r`). Flat only for the book's realised P&L, where it is true.
        train = r.iloc[s - train_n: s]
        train = train.loc[:, train.notna().sum() >= MIN_TRAIN_OBS]
        if train.shape[1] < 2:
            continue
        test = r.iloc[s: s + step][train.columns].fillna(0.0)
        tdays = list(train.index)
        asof = tdays[-1]
        kern = {}
        now_state = {}
        for sym in labels:
            w, meta = cr.sleeve_weights(sym, tdays, asof=asof, labels=labels[sym])
            if w.size:
                kern[sym] = w
                now_state[sym] = meta["now"]
        ev_plain = _evidence(train, None, None)
        ev_asset = _evidence(train, kern, None)
        heat: dict[str, dict[str, float]] = {}
        names = list(train.columns)
        heat["equal"] = {c: TOTAL_HEAT / len(names) for c in names}
        heat["geo"] = _solve(ev_plain, cfg0)
        heat["geo_asset"] = _solve(ev_asset, cfg0)
        if used == "bars":
            funded = [f"{sym}_{st['trend']}" for sym, st in now_state.items()]
        else:
            # On real sleeves the hard switch funds only sleeves whose instrument is in the state
            # the sleeve earned most in over the training window -- the rule a regime filter is.
            funded = []
            for c in names:
                sym = str(c).split("_")[0]
                if sym not in kern:
                    continue
                w = kern[sym]
                x = train[c].to_numpy(float)
                ok = np.isfinite(x) & np.isfinite(w)
                if ok.sum() >= MIN_TRAIN_OBS and (w[ok] * x[ok]).sum() / max(w[ok].sum(), 1e-12) \
                        > x[ok].mean():
                    funded.append(c)
        heat["switch"] = {c: TOTAL_HEAT / len(funded) for c in funded} if funded else heat["equal"]
        if with_hmm:
            cond = hmm_conditioning(closes["XAUUSD"], tdays) if "XAUUSD" in closes else None
            if cond is not None:
                cfg_h = WorldConfig(n_worlds=n_worlds, n_rows=n_rows, regime_labels=cond[0],
                                    regime_probs=cond[1])
                heat["geo_hmm"] = _solve(ev_plain, cfg_h)
                heat["geo_hmm_asset"] = _solve(ev_asset, cfg_h)
            else:
                heat["geo_hmm"], heat["geo_hmm_asset"] = heat["geo"], heat["geo_asset"]
        if macro_live:
            mw = macro_weights(tdays, asof)
            heat["geo_macro"] = _solve(_evidence(train, None, mw), cfg0)
            heat["geo_macro_asset"] = _solve(_evidence(train, kern, mw), cfg0)
        for a in arms:
            h = np.array([heat[a].get(c, 0.0) for c in names])
            acct = test.to_numpy(float) @ h
            realised[a].extend(np.log1p(np.maximum(acct, -0.99)).tolist())
        oos_days.extend(test.index)
        books.append({"asof": asof, "state": {s: "|".join(v.values()) for s, v in now_state.items()},
                      "trend_share_geo_asset": round(sum(v for c, v in heat["geo_asset"].items()
                                                         if c.endswith("_trend")) / TOTAL_HEAT, 4),
                      "trend_share_geo": round(sum(v for c, v in heat["geo"].items()
                                                   if c.endswith("_trend")) / TOTAL_HEAT, 4)})
        print(f"[{k + 1}/{len(starts)}] {asof} {time.time() - t0:.0f}s", flush=True)

    arr = {a: np.asarray(v) for a, v in realised.items()}
    per_arm = {a: summarise(x) for a, x in arr.items()}
    diffs = {}
    for a in arms:
        if a == "geo":
            continue
        d = arr[a] - arr["geo"]
        lo, hi = block_bootstrap_ci(d)
        diffs[f"{a}_minus_geo"] = {"mean_per_day": round(float(d.mean()), 9),
                                   "annual": round(float(d.mean()) * 252, 5),
                                   "ci90": [round(lo, 9), round(hi, 9)]}
    for a in ("geo", "geo_asset"):
        d = arr[a] - arr["equal"]
        lo, hi = block_bootstrap_ci(d)
        diffs[f"{a}_minus_equal"] = {"mean_per_day": round(float(d.mean()), 9),
                                     "annual": round(float(d.mean()) * 252, 5),
                                     "ci90": [round(lo, 9), round(hi, 9)]}
    head = diffs[f"{HEADLINE[0]}_minus_{HEADLINE[1]}"]
    gain = head["ci90"][0] > 0 and diffs["geo_asset_minus_equal"]["mean_per_day"] > 0
    verdict = "GAIN" if gain else ("NO_GAIN" if head["ci90"][1] < 0 else "INCONCLUSIVE")
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "contract": "regime_allocation", "verdict": verdict,
        # ONLY THE DESK'S OWN SLEEVES CAN ADMIT. The bar-built bench shows whether the kernel
        # moves composition the right way on sleeves with a known regime dependence; the
        # allocator sizes real sleeves, so only a GAIN on their matrix licenses the kernel.
        "admits": bool(used == "desk" and verdict == "GAIN"),
        "headline": {"arm": HEADLINE[0], "against": HEADLINE[1], **head},
        "rule": ("GAIN iff the 90% stationary-bootstrap interval of (geo_asset - geo) daily log "
                 "growth is above zero AND geo_asset beats equal heat; headline declared before "
                 "the run, never swapped for the best arm"),
        "trials": len(arms), "arms": per_arm, "differences": diffs,
        "design": {"universe": used,
                   "universe_note": ("the allocator's own daily-R matrix: the desk's real sleeves"
                                     if used == "desk" else
                                     "trend (63d TSMOM) and range (5d reversal) sleeves built from "
                                     "bars: a regime-sensitivity bench, not the desk's edges; the "
                                     "box re-runs this on its real sleeves and that verdict rules"),
                   "assets": list(closes.columns), "sleeves": [str(c) for c in r.columns][:200],
                   "total_heat": TOTAL_HEAT, "sleeve_share": SLEEVE_SHARE, "step_days": step,
                   "train_days": train_n, "n_worlds": n_worlds, "n_rows": n_rows,
                   "oos_first": str(oos_days[0]) if oos_days else None,
                   "oos_last": str(oos_days[-1]) if oos_days else None,
                   "macro_arm": "MEASURED" if macro_live else
                   "UNMEASURED: no FRED archive on this host (data/fred_macro*.json)",
                   "cost_bps_per_turnover": COST_BPS},
        "rebalances": books[-6:],
        "runtime_s": round(time.time() - t0, 1),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=int, default=21)
    ap.add_argument("--train", type=int, default=750)
    ap.add_argument("--worlds", type=int, default=128)
    ap.add_argument("--rows", type=int, default=256)
    ap.add_argument("--no-hmm", action="store_true")
    ap.add_argument("--max-steps", type=int, default=None)
    ap.add_argument("--universe", choices=("auto", "desk", "bars"), default="auto")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = run(step=a.step, train_n=a.train, n_worlds=a.worlds, n_rows=a.rows,
              with_hmm=not a.no_hmm, max_steps=a.max_steps, universe=a.universe)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"verdict": doc["verdict"], "headline": doc["headline"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
