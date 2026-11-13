"""FEATURE-DRIFT EARLY WARNING for every live sleeve (hourly pass item 35, 2026-11-03).

WHY. Model-risk teams under SR 11-7 watch a model's INPUTS as well as its PnL: a sleeve whose
inputs have left the distribution it was certified on is trading a market its certificate never
saw, and that shows up in the inputs days or weeks before it shows up in the R the decay monitor
reads. `decay_monitor` judges realised R, so its lead time is bounded by how fast losses
accumulate. This organ measures the inputs.

WHAT. For each live sleeve, per broker date, the inputs its mechanism reads off H1 bars:

  session_range_atr  high - low of the sleeve's session window, in units of ATR(20) on H1 bars
                     (for gold asia: the Asia range the breakout is built on)
  atr_frac           ATR(20) on H1 bars at the session's last bar, over that bar's close
  spread_points      median quoted spread (points) over the session's bars
  session_volume     summed tick volume over the session's bars

The last RECENT_DAYS broker dates are compared with the sleeve's CERTIFIED in-sample dates (the
certificate's own `days` ending at its `gated_at`), by the Population Stability Index over the
reference quintiles (count-smoothed and debiased for the 20-day window, see `psi`) and the
two-sample Kolmogorov-Smirnov statistic with its asymptotic p-value.

THE VERDICT IS A WARNING, NEVER AN ACTION. Any input with PSI above PSI_FLAG (0.25, the
industry's "significant shift" bar) makes the sleeve an EDGE_DECAY_CANDIDATE. Nothing here writes
data/sleeves.json, the allocator's inputs or anything the gateway reads; the regime-aware decay
ruling (`decay_monitor`) still makes every FADE / RETIRE call. A sleeve with too few bars on
either side is UNMEASURED with its counts, never a clean verdict (L1.28a).

LEAD TIME, FOR THE ACCURACY LOOP. The first time a sleeve is flagged is remembered in
data/feature_drift_state.json, and each run publishes, per sleeve, that first-flag time beside the
decay monitor's current verdict, so DECAY_ACCURACY (IDEA_QUEUE 249) can score this input's lead
time against realised drawdowns (`decay_accuracy_lead` in the report). A flag that clears is kept
in the episode history, so false alarms are countable too.

A sleeve with no matching certificate is judged against a fallback reference (the FALLBACK_DAYS
dates ending FALLBACK_GAP_DAYS before now) and says so on its row.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SLEEVES_FILE = BASE / "data" / "sleeves.json"
GOLD_RETIRED = BASE / "data" / "GOLD_RETIRED.json"
CANON = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"
DECAY_LIVE = BASE / "data" / "decay_live.json"
STATE = BASE / "data" / "feature_drift_state.json"
REPORT = BASE / "reports" / "FEATURE_DRIFT.json"
#: First hit wins, like every other bar reader on the desk.
UNIVERSE_DIRS: tuple[Path, ...] = (BASE / "data" / "universe", BASE / "universe")

#: Declared before any result, never searched.
RECENT_DAYS = 20
MIN_RECENT = 10
MIN_REFERENCE = 120
#: Five reference-quantile bins: twenty recent days over ten bins leaves two per bin, which
#: measures sampling noise rather than drift.
PSI_BINS = 5
PSI_FLAG = 0.25
PSI_SMOOTH = 0.5
ATR_N = 20
FALLBACK_DAYS = 750
FALLBACK_GAP_DAYS = 60
FEATURES = ("session_range_atr", "atr_frac", "spread_points", "session_volume")
#: Permutation null for the flag: NULL_DRAWS random RECENT_DAYS blocks of the reference itself,
#: each judged against the rest of the reference exactly as the live block is. Reported beside
#: the fixed PSI_FLAG so the bar's false-alarm rate on THIS sleeve's own history is measured,
#: never assumed. Seeded, so the same history always gives the same null.
NULL_DRAWS = 200
NULL_SEED = 20261103

#: Session windows in broker hours [start, end). The gold book's windows mirror
#: decision_core.GOLD_WINDOWS: asia's range is the night up to its 07:00 signal hour; the two
#: later windows carry their range hours. Any other sleeve is judged on the whole broker day.
WINDOW_HOURS: dict[str, tuple[int, int]] = {
    "asia": (0, 7),
    "london_am": (10, 13),
    "afternoon": (14, 17),
}
#: decision_core.GOLD_WINDOWS labels, mirrored (this organ runs without the terminal bindings).
GOLD_WINDOWS = ("asia", "london_am", "afternoon")


# ============================================================================ statistics
def psi(reference: Sequence[float], recent: Sequence[float], bins: int = PSI_BINS,
        smooth: float = PSI_SMOOTH, debias: bool = True) -> float | None:
    """Population Stability Index of `recent` against `reference`, over the reference's own
    quantile bins (ties collapse bins, never invent them), with `smooth` added to every bin
    count on both sides (an empty bin is not an infinite surprise at n = 20).

    DEBIASED. Under no shift at all, PSI is about chi-square with (B - 1) degrees of freedom
    scaled by (1/n + 1/N), so twenty recent days over ten bins read ~0.45 from sampling alone and
    every sleeve would sit above the 0.25 bar forever. With `debias` that null expectation,
    (B - 1)(1/n + 1/N), is subtracted, so PSI_FLAG keeps its textbook meaning at the window
    this organ is asked to use. None when either side is empty."""
    ref = np.asarray([x for x in reference if np.isfinite(x)], dtype=float)
    rec = np.asarray([x for x in recent if np.isfinite(x)], dtype=float)
    if ref.size == 0 or rec.size == 0:
        return None
    edges = np.unique(np.quantile(ref, np.linspace(0.0, 1.0, bins + 1)))
    if edges.size < 2:
        # a constant reference: two bins, at the value and off it
        p = np.array([ref.size, 0.0])
        q = np.array([float(np.sum(rec == edges[0])), float(np.sum(rec != edges[0]))])
    else:
        inner = edges[1:-1]
        p = np.bincount(np.searchsorted(inner, ref, side="right"),
                        minlength=edges.size - 1).astype(float)
        q = np.bincount(np.searchsorted(inner, rec, side="right"),
                        minlength=edges.size - 1).astype(float)
    pf = (p + smooth) / (p.sum() + smooth * p.size)
    qf = (q + smooth) / (q.sum() + smooth * q.size)
    raw = float(np.sum((qf - pf) * np.log(qf / pf)))
    if not debias:
        return raw
    return raw - (p.size - 1) * (1.0 / rec.size + 1.0 / ref.size)


def ks_2samp(a: Sequence[float], b: Sequence[float]) -> tuple[float | None, float | None]:
    """Two-sample KS statistic and its asymptotic two-sided p-value (Kolmogorov series with the
    Stephens small-sample correction). numpy only: the trading box carries no scipy promise."""
    x = np.sort(np.asarray([v for v in a if np.isfinite(v)], dtype=float))
    y = np.sort(np.asarray([v for v in b if np.isfinite(v)], dtype=float))
    if x.size == 0 or y.size == 0:
        return None, None
    grid = np.concatenate([x, y])
    d = float(np.max(np.abs(np.searchsorted(x, grid, side="right") / x.size
                            - np.searchsorted(y, grid, side="right") / y.size)))
    en = math.sqrt(x.size * y.size / (x.size + y.size))
    lam = (en + 0.12 + 0.11 / en) * d
    if lam < 1e-3:
        return d, 1.0
    p = 2.0 * sum((-1) ** (k - 1) * math.exp(-2.0 * (k * lam) ** 2) for k in range(1, 101))
    return d, float(min(1.0, max(0.0, p)))


# ============================================================================== features
def _atr(df: pd.DataFrame, n: int = ATR_N) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(),
                    (df["low"] - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=n).mean()


def daily_features(bars: pd.DataFrame, window: str | None) -> pd.DataFrame:
    """One row per broker date with the FEATURES, from the bars of the sleeve's session window
    only (stamps are broker time, as every universe parquet stores them). Causal per date: a
    date's row reads that date's session bars and the ATR known at its last session bar."""
    if bars is None or len(bars) == 0:
        return pd.DataFrame(columns=list(FEATURES))
    df = bars.sort_index()
    atr = _atr(df)
    lo, hi = WINDOW_HOURS.get(str(window), (0, 24))
    hours = df.index.hour
    sess = df[(hours >= lo) & (hours < hi)]
    if len(sess) == 0:
        return pd.DataFrame(columns=list(FEATURES))
    dates = sess.index.normalize()
    rows = []
    for dt, g in sess.groupby(dates):
        last = g.index[-1]
        a = float(atr.get(last, np.nan))
        c = float(g["close"].iloc[-1])
        rng = float(g["high"].max() - g["low"].min())
        rows.append({
            "date": dt,
            "session_range_atr": rng / a if a > 0 else np.nan,
            "atr_frac": a / c if c > 0 and np.isfinite(a) else np.nan,
            "spread_points": (float(g["spread"].median()) if "spread" in g else np.nan),
            "session_volume": (float(g["tick_volume"].sum()) if "tick_volume" in g
                               else np.nan),
            "_last_hour": int(last.hour),
        })
    out = pd.DataFrame(rows).set_index("date")
    # The newest date is kept only once its window has printed its final bar: a session still
    # trading has a short range and a partial volume, and judging it would read as drift.
    if len(out) and out["_last_hour"].iloc[-1] < hi - 1:
        out = out.iloc[:-1]
    return out.drop(columns="_last_hour")


# ================================================================================ roster
def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def live_roster(sleeves_doc: Any, retired_gold: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """The gold book's windows (less any the promoter retired) plus every LIVE sleeves.json row
    with a symbol. Mirrors decision_core.roster's gold half; evidence aliases (gold_asia_v2...)
    fold into their canonical window there, so they are not judged twice here."""
    out: list[dict[str, Any]] = []
    retired = retired_gold or {}
    for w in GOLD_WINDOWS:
        name = f"gold_{w}"
        if name not in retired:
            out.append({"name": name, "symbol": "XAUUSD", "window": w})
    rows = (sleeves_doc or {}).get("sleeves") if isinstance(sleeves_doc, dict) else sleeves_doc
    seen = {r["name"] for r in out}
    for r in rows or []:
        if not isinstance(r, dict) or str(r.get("status", "")).upper() != "LIVE":
            continue
        name, sym = str(r.get("name") or ""), r.get("symbol")
        if not name or not sym or name in seen:
            continue
        if name.lower().startswith("gold_") and name.rsplit("_", 1)[-1].startswith("v"):
            continue
        seen.add(name)
        out.append({"name": name, "symbol": str(sym), "window": r.get("window")})
    return out


def cert_reference(canon: Any, symbol: str, window: str | None
                   ) -> tuple[pd.Timestamp, pd.Timestamp, str] | None:
    """(start, end, cell) of the newest matching certificate's in-sample span: shadow_spec
    symbol equal, and selector equal to the window when the sleeve has one."""
    surv = canon.get("survivors") if isinstance(canon, dict) else None
    items: Iterable[Any] = (surv.values() if isinstance(surv, dict)
                            else surv if isinstance(surv, list) else ())
    best: tuple[pd.Timestamp, pd.Timestamp, str] | None = None
    for r in items:
        if not isinstance(r, dict):
            continue
        spec = r.get("shadow_spec") or {}
        if spec.get("symbol") != symbol:
            continue
        if window and spec.get("selector") not in (None, window):
            continue
        try:
            end = pd.Timestamp(r["gated_at"])
            days = int(r["days"])
        except (KeyError, TypeError, ValueError):
            continue
        end = end.tz_convert("UTC") if end.tzinfo else end.tz_localize("UTC")
        if best is None or end > best[1]:
            best = (end - pd.Timedelta(days=days), end, str(r.get("cell")))
    return best


def load_bars(symbol: str, dirs: Sequence[Path] = UNIVERSE_DIRS) -> pd.DataFrame | None:
    for d in dirs:
        p = d / f"{symbol}_H1.parquet"
        if p.exists():
            try:
                df = pd.read_parquet(p)
            except Exception:
                continue
            if not isinstance(df.index, pd.DatetimeIndex):
                for c in ("time", "datetime"):
                    if c in df.columns:
                        df = df.set_index(pd.to_datetime(df[c], utc=True))
                        break
            idx = df.index
            df.index = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
            return df
    return None


# ================================================================================= judge
def judge_sleeve(sleeve: Mapping[str, Any], bars: pd.DataFrame | None, canon: Any,
                 now: pd.Timestamp) -> dict[str, Any]:
    row: dict[str, Any] = {"name": sleeve["name"], "symbol": sleeve["symbol"],
                           "window": sleeve.get("window")}
    if bars is None or len(bars) == 0:
        return {**row, "verdict": f"UNMEASURED: no H1 bars for {sleeve['symbol']}"}
    feats = daily_features(bars, sleeve.get("window"))
    ref_span = cert_reference(canon, str(sleeve["symbol"]), sleeve.get("window"))
    if ref_span is not None:
        r0, r1, cell = ref_span
        row["reference"] = {"source": "certificate", "cell": cell,
                            "start": r0.isoformat(), "end": r1.isoformat()}
    else:
        r1 = now - pd.Timedelta(days=FALLBACK_GAP_DAYS)
        r0 = r1 - pd.Timedelta(days=FALLBACK_DAYS)
        row["reference"] = {"source": "fallback: no matching certificate",
                            "start": r0.isoformat(), "end": r1.isoformat()}
    ref = feats[(feats.index >= r0) & (feats.index <= r1)]
    rec = feats[feats.index <= now].tail(RECENT_DAYS)
    rec = rec[rec.index > r1] if len(rec) else rec
    row["n_reference_days"], row["n_recent_days"] = len(ref), len(rec)
    row["recent_last_date"] = rec.index[-1].isoformat() if len(rec) else None
    if len(ref) < MIN_REFERENCE or len(rec) < MIN_RECENT:
        return {**row, "verdict": (f"UNMEASURED: {len(ref)} reference days (need "
                                   f"{MIN_REFERENCE}), {len(rec)} recent days after the "
                                   f"reference (need {MIN_RECENT})")}
    per: dict[str, Any] = {}
    flagged = []
    for f in FEATURES:
        p = psi(ref[f].to_numpy(), rec[f].to_numpy())
        d, pv = ks_2samp(ref[f].to_numpy(), rec[f].to_numpy())
        per[f] = {"psi": None if p is None else round(p, 4),
                  "ks": None if d is None else round(d, 4),
                  "ks_p": None if pv is None else round(pv, 5),
                  "reference_median": _r(np.nanmedian(ref[f].to_numpy())),
                  "recent_median": _r(np.nanmedian(rec[f].to_numpy()))}
        if p is not None and p > PSI_FLAG:
            flagged.append(f)
    row["features"] = per
    row["max_psi"] = max((v["psi"] for v in per.values() if v["psi"] is not None), default=None)
    row["flagged_features"] = flagged
    nul = row["null"] = permutation_null(ref, row["max_psi"])
    # The fixed bar alone is not a warning on a trending history: on the XAUUSD asia
    # certificate (2,101 days) every 20-day block of the reference itself clears 0.25
    # (p_flag 1.0, measured 2026-11-03). So when the null is measured, the sleeve flags only
    # when its max PSI also beats the null's 95th percentile; the fixed bar is the floor.
    bar = nul.get("p95") if nul.get("draws") else None
    if bar is None:
        # The fixed bar alone was measured as a constant alarm on gold_asia (Auditor, 11-03):
        # with no null to read it against, the honest answer is UNMEASURED, never a flag.
        row["flag_rule"] = f"psi>{PSI_FLAG} and max_psi>null_p95 (null unmeasured)"
        row["verdict"] = f"UNMEASURED: no permutation null ({nul.get('verdict')})"
        return row
    row["flag_rule"] = f"psi>{PSI_FLAG} and max_psi>null_p95={bar}"
    beats_null = row["max_psi"] is not None and row["max_psi"] > bar
    row["verdict"] = "EDGE_DECAY_CANDIDATE" if flagged and beats_null else "STABLE"
    return row


def permutation_null(ref: pd.DataFrame, observed: float | None,
                     draws: int = NULL_DRAWS, seed: int = NULL_SEED) -> dict[str, Any]:
    """Max-over-FEATURES PSI of random RECENT_DAYS blocks of the reference, each against the
    reference with that block removed. Gives the flag's false-alarm rate on this history
    (`p_flag`), the 95th/99th percentiles, and the observed max PSI's empirical p-value."""
    n = len(ref)
    if n < MIN_REFERENCE or n <= RECENT_DAYS:
        return {"draws": 0, "verdict": "UNMEASURED: reference too short for a null"}
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n - RECENT_DAYS + 1, size=draws)
    vals = []
    for s0 in starts:
        blk = ref.iloc[s0:s0 + RECENT_DAYS]
        rest = pd.concat([ref.iloc[:s0], ref.iloc[s0 + RECENT_DAYS:]])
        raw = [psi(rest[f].to_numpy(), blk[f].to_numpy()) for f in FEATURES]
        ps = [p for p in raw if p is not None]
        if ps:
            vals.append(max(ps))
    if not vals:
        return {"draws": 0, "verdict": "UNMEASURED: no feature measurable in the null"}
    arr = np.asarray(vals)
    out: dict[str, Any] = {"draws": len(arr), "p95": _r(np.quantile(arr, 0.95), 4),
                           "p99": _r(np.quantile(arr, 0.99), 4),
                           "p_flag": _r(float((arr > PSI_FLAG).mean()), 4)}
    if observed is not None:
        out["p_value"] = _r(float((1 + (arr >= observed).sum()) / (1 + len(arr))), 4)
    return out


def _r(v: Any, k: int = 6) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f, k) if math.isfinite(f) else None


def _decay_verdicts(doc: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    src = doc.get("sleeves", doc) if isinstance(doc, dict) else {}
    if isinstance(src, dict):
        for k, v in src.items():
            if isinstance(v, dict) and "verdict" in v:
                out[str(k)] = str(v["verdict"])
    return out


def update_state(state: Mapping[str, Any], rows: Sequence[Mapping[str, Any]],
                 now: str) -> dict[str, Any]:
    """Episodes per sleeve: an episode opens on the first EDGE_DECAY_CANDIDATE reading and
    closes on the first STABLE one. UNMEASURED readings neither open nor close an episode."""
    out = {k: {"episodes": [dict(e) for e in v.get("episodes", [])]}
           for k, v in (state or {}).items() if isinstance(v, dict)}
    for r in rows:
        eps = out.setdefault(str(r["name"]), {"episodes": []})["episodes"]
        open_ep = eps[-1] if eps and eps[-1].get("cleared_at") is None else None
        if r["verdict"] == "EDGE_DECAY_CANDIDATE":
            if open_ep is None:
                eps.append({"first_flag_at": now, "features": list(r["flagged_features"]),
                            "max_psi": r.get("max_psi"), "cleared_at": None})
            else:
                open_ep["features"] = sorted(set(open_ep["features"])
                                             | set(r["flagged_features"]))
                if (r.get("max_psi") or 0) > (open_ep.get("max_psi") or 0):
                    open_ep["max_psi"] = r.get("max_psi")
        elif r["verdict"] == "STABLE" and open_ep is not None:
            open_ep["cleared_at"] = now
    return out


def run(now: datetime | None = None, *, sleeves_doc: Any = None, retired_gold: Any = None,
        canon: Any = None, decay_doc: Any = None,
        bars: Mapping[str, pd.DataFrame] | None = None,
        state_path: Path = STATE, report_path: Path = REPORT,
        write_state: bool = True) -> dict[str, Any]:
    stamp = (now or datetime.now(tz=UTC)).astimezone(UTC)
    ts = pd.Timestamp(stamp)
    sleeves_doc = _read_json(SLEEVES_FILE) if sleeves_doc is None else sleeves_doc
    retired_gold = _read_json(GOLD_RETIRED) if retired_gold is None else retired_gold
    canon = _read_json(CANON) if canon is None else canon
    decay_doc = _read_json(DECAY_LIVE) if decay_doc is None else decay_doc
    roster = live_roster(sleeves_doc, retired_gold if isinstance(retired_gold, dict) else {})
    cache: dict[str, pd.DataFrame | None] = {}
    rows = []
    for s in roster:
        sym = s["symbol"]
        if sym not in cache:
            cache[sym] = (bars.get(sym) if bars is not None else load_bars(sym))
        rows.append(judge_sleeve(s, cache[sym], canon, ts))
    prev = _read_json(state_path) or {}
    state = update_state(prev if isinstance(prev, dict) else {}, rows, stamp.isoformat())
    decay = _decay_verdicts(decay_doc)
    lead = {}
    for r in rows:
        eps = state.get(r["name"], {}).get("episodes", [])
        open_ep = eps[-1] if eps and eps[-1].get("cleared_at") is None else None
        lead[r["name"]] = {
            "feature_drift_first_flag_at": open_ep["first_flag_at"] if open_ep else None,
            "feature_drift_episodes": len(eps),
            "feature_drift_false_alarm_candidates": sum(
                1 for e in eps if e.get("cleared_at") is not None
                and decay.get(r["name"], "HEALTHY") == "HEALTHY"),
            "decay_monitor_verdict_now": decay.get(r["name"], "UNMEASURED: no decay row"),
        }
    doc = {
        "generated_at": stamp.isoformat(),
        "rule": (f"PSI over {PSI_BINS} reference-quantile bins and two-sample KS of each "
                 f"input over the last {RECENT_DAYS} broker dates against the certificate's "
                 f"in-sample dates (PSI debiased by its no-shift expectation (B-1)(1/n+1/N)); "
                 f"any PSI > {PSI_FLAG} reads EDGE_DECAY_CANDIDATE. An early "
                 "warning only: this organ changes no sleeve, size or roster; decay_monitor "
                 "makes every FADE / RETIRE call."),
        "features": list(FEATURES),
        "n_sleeves": len(rows),
        "n_candidates": sum(1 for r in rows if r["verdict"] == "EDGE_DECAY_CANDIDATE"),
        "n_unmeasured": sum(1 for r in rows if str(r["verdict"]).startswith("UNMEASURED")),
        "sleeves": rows,
        "decay_accuracy_lead": lead,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = report_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(report_path)
    if write_state:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        stmp = state_path.with_suffix(".tmp")
        stmp.write_text(json.dumps(state, indent=1), "utf-8")
        stmp.replace(state_path)
    try:
        from libs.ops import events
        events.emit("feature_drift", leg="feature_drift", candidates=doc["n_candidates"])
    except Exception:
        pass
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the default)")
    ap.parse_args(argv)
    doc = run()
    print(f"feature_drift: {doc['n_sleeves']} sleeves, {doc['n_candidates']} "
          f"EDGE_DECAY_CANDIDATE, {doc['n_unmeasured']} UNMEASURED")
    # zero live sleeves is a measurement, not a failure; an all-UNMEASURED book is RED
    return 1 if doc["n_sleeves"] and doc["n_unmeasured"] == doc["n_sleeves"] else 0


if __name__ == "__main__":
    sys.exit(main())
