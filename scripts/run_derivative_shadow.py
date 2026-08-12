"""Derivative-data shadow sleeves (Phase 5): OI Divergence + Long/Short Contrarian.

ECONOMIC HYPOTHESES (pre-registered, no peeking):
  * OI Divergence  -- price up + OI up = genuine trend participation (follow); price up + OI DOWN =
                      short-covering (weak, fade). Signal = sign(dPrice)*sign(dOI), cross-sectional.
  * L/S Contrarian -- crowded retail positioning mean-reverts. Signal = -zscore(long/short ratio),
                      cross-sectional (fade the crowd).

We have NO usable history for these (the derivative metrics only exist from when our own archiver
started), so we DO NOT fabricate a backtest. Instead we accumulate forward and report progress. The
moment >= MIN_DAYS distinct days exist, this computes real forward sleeve returns + Sharpe.

NO ACTUATOR EXISTS YET FOR WHAT HAPPENS NEXT, and this line is corrected rather than left to
mislead: the docstring used to say "the discovery gauntlet (CPCV/DSR/PBO) takes over" as though
that were wired. Measured 2026-08-12: nothing consumes `status: "VALIDATING"` or `forward_sharpe`
-- no CPCV/DSR/PBO pass runs, nothing reaches the promotion gate. A clock could clear MIN_DAYS with
a strong Sharpe and sit there, same defect class as an axis-screen sleeve clearing its forward bar
with nothing to receive the verdict (fixed for that pipeline in scripts/run_forward_resolution.py,
NOT yet extended to this one). Until it is, `status == "VALIDATING"` is a finding for a person to
act on, not a promotion.

ALSO MEASURED 2026-08-12: neither this script nor its data source (collect_binance_metrics.py) had
ever been scheduled -- 0 cron/systemd lines for either, anywhere. `days_accumulated` could not
advance regardless of calendar time elapsed since these sleeves were pre-registered in 2026-07.

Writes web/derivative_shadow.json.

    python scripts/run_derivative_shadow.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    # WITHOUT THIS the script dies on `ModuleNotFoundError: No module named 'libs'` when invoked
    # as `python scripts/run_derivative_shadow.py` -- which is exactly how a manifest line would
    # call it. Every other scheduled organ on this desk carries this preamble; this one never did,
    # which is one of the two reasons it could never have completed a scheduled run.
    sys.path.insert(0, str(_ROOT))

from libs.data.crypto_source import fetch_klines  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.anytime_valid import e_value  # noqa: E402

_METRICS = Path("data/crypto_metrics.parquet")
_OUT = Path("web/derivative_shadow.json")
_MIN_DAYS = 40


def _sharpe(r: np.ndarray) -> float:
    sd = float(np.std(r))
    return round(float(np.mean(r)) / sd * (365 ** 0.5), 2) if sd else 0.0


def _forward_returns(df: pd.DataFrame) -> dict[str, float]:
    """Compute OI-divergence + L/S-contrarian forward sleeve Sharpes once enough days exist."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["ts"]).dt.date
    piv_oi = df.pivot_table(index="date", columns="symbol", values="open_interest")
    piv_ls = df.pivot_table(index="date", columns="symbol", values="ls_ratio")
    syms = list(piv_oi.columns)
    start_ms = int((pd.Timestamp(min(df["date"])) - pd.Timedelta(days=2)).timestamp() * 1000)
    px = {}
    for s in syms:
        try:
            k = fetch_klines(s, interval="1d", start_ms=start_ms)
            if not k.empty:
                px[s] = k.set_index(k["timestamp"].dt.date)["close"].astype(float)
        except Exception:
            continue
    prices = pd.DataFrame(px).reindex(piv_oi.index).ffill()
    pr_ret = prices.pct_change().shift(-1)                    # next-day return (no lookahead)
    d_price = prices.pct_change()
    d_oi = piv_oi.pct_change()
    oi_sig = np.sign(d_price) * np.sign(d_oi)                 # +1 confirm trend, -1 divergence
    ls_z = (piv_ls.sub(piv_ls.mean(axis=1), axis=0)).div(piv_ls.std(axis=1) + 1e-9, axis=0)
    ls_sig = -ls_z                                            # fade the crowd
    out = {}
    for name, sig in (("oi_divergence", oi_sig), ("ls_contrarian", ls_sig)):
        w = sig.sub(sig.mean(axis=1), axis=0)                 # market-neutral
        w = w.div(w.abs().sum(axis=1) + 1e-9, axis=0)
        out[name] = (w * pr_ret).sum(axis=1).dropna().to_numpy()
    return out


def main() -> None:
    _law_guard()
    now = datetime.now(tz=UTC)
    # REGISTRY-DRIVEN ROSTER (principal 2026-07-23): built-ins plus anything registered in
    # data/shadow_sleeves.json, so a new sleeve starts accruing forward evidence the moment it
    # is registered -- no code edit, nothing silently left off the clocks. Safe to scale now
    # that DSR deflation is per-family and pre-registered (fixed wall), so parallel challengers
    # no longer inflate each other's bar. Order is deterministic for reproducible runs.
    sleeves = ["oi_divergence", "ls_contrarian"]
    try:
        _extra = json.loads(Path("data/shadow_sleeves.json").read_text("utf-8"))
        if isinstance(_extra, list):
            sleeves = sorted({*sleeves, *(str(x) for x in _extra if str(x).strip())})
    except Exception:
        pass
    # UNCONDITIONALLY INITIALISED. This crashed with UnboundLocalError on every run where
    # data/crypto_metrics.parquet did not exist yet -- the peek/e-value line below reads `series`
    # regardless of which branch ran, but `series` was only ever assigned inside the `else`. On a
    # box where the archiver has not written its first row (which is exactly the state this
    # script's own docstring says to expect: "no backtest fabricated" before real history exists),
    # this organ could never complete a single run, so `days_accumulated` could never be observed
    # even once. Discovered 2026-08-12 by actually running it rather than trusting the schedule.
    series: dict[str, np.ndarray] = {}
    if not _METRICS.exists():
        days, quality = 0, "no archive yet"
        result: dict[str, object] = {}
    else:
        df = pd.read_parquet(_METRICS)
        days = int(pd.to_datetime(df["ts"]).dt.date.nunique())
        nsym = int(df["symbol"].nunique())
        nan_ls = float(df["ls_ratio"].isna().mean())
        quality = f"{nsym} symbols/day, L/S NaN {nan_ls:.0%}"
        # PEEK RULE (2026-07-22): the e-process is anytime-valid (Ville) -- reading it
        # daily spends NO alpha, so it may be published while the clock accrues. The
        # interim Sharpe is NOT peek-safe and stays unpublished until min_days.
        series = _forward_returns(df) if days >= 12 else {}
    ready = days >= _MIN_DAYS
    result = {k: _sharpe(v) if len(v) > 5 else 0.0 for k, v in series.items()} if ready else {}
    peek = {k: {"e_value": round(e_value(v), 3), "n": len(v), "threshold": 100.0,
                "decisive": bool(e_value(v) >= 100.0)} for k, v in series.items()}
    eta = (now + timedelta(days=max(0, _MIN_DAYS - days))).date().isoformat()
    out = {
        "updated": now.isoformat(),
        "sleeves": sleeves,
        "days_accumulated": days,
        "min_days": _MIN_DAYS,
        "data_quality": quality,
        "validation_progress_pct": round(100 * min(1.0, days / _MIN_DAYS), 1),
        "expected_ready_date": eta,
        "status": "VALIDATING" if ready else "ACCUMULATING (no backtest fabricated)",
        "forward_sharpe": result,
        "anytime_peek": peek,
        "peek_rule": "e_value is anytime-valid: safe to read daily. decisive=True at "
                     "alpha=0.01 BEFORE day 40 = early evidence; Sharpe stays "
                     "unpublished until min_days (not peek-safe). Promotion still "
                     "requires the full gauntlet.",
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"derivative shadow: {days}/{_MIN_DAYS} days ({out['validation_progress_pct']}%), "
          f"ETA {eta}, status {out['status']}")


if __name__ == "__main__":
    main()
