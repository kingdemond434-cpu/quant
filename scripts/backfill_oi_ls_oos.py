#!/usr/bin/env python3
"""CROSS-SECTIONAL held-out OOS for the two pre-registered derivative sleeves
(oi_divergence, ls_contrarian) on reconstructed universe history (MAX_SURVIVORS Part 1 #1).

CONSTRUCTION IS LOCKED, line-for-line, from scripts/run_derivative_shadow._forward_returns:
    oi_sig = sign(d_price) * sign(d_OI)                  (confirm-trend vs divergence)
    ls_sig = -cross_sectional_z(ls_ratio)                (fade the crowd)
    w      = demeaned cross-sectionally, gross-normalised; return vs NEXT-day close (no lookahead)
No parameter here was fit on the held-out window: both sleeves were pre-registered 2026-07 from
~30d of API history, so everything before 2026-06 is genuinely unseen.

ANTI-PHANTOM GATES (mandatory, in order):
  1. DIFF-VERIFY: archive daily values vs the forward collector's ground truth
     (data/crypto_metrics.parquet, 2026-06-22 ->). Correlation + relative-diff per field per
     symbol; misalignment (bithumb/timezone class) ABORTS the whole run.
  2. HELD-OUT EMBARGO: OOS ends 2026-05-31, three weeks before forward collection began.
  3. NET-OF-COST: daily cross-sectional rebalance pays turnover * 5e-4/side; verdict is on NET.
  4. ZERO PROMOTION AUTHORITY: even OOS-SURVIVES only says "keep the forward clock running with
     more confidence" -- the two-stage law and the full gauntlet still decide.

Universe: tranche-1 cohort (metrics by 2022-07-01) enumerated from the archive's OWN listing,
including delisted symbols -- the cross-section is what existed then (no survivorship pick).
"""
from __future__ import annotations

import contextlib
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio  # noqa: E402
from libs.validation.forward_stats import nw_tstat  # noqa: E402

ROOT = Path("/home/quant/quant-platform")
MET_DIR = ROOT / "data/lake/bronze/oi_ls_daily"
PX_DIR = ROOT / "data/lake/bronze/futclose_daily"
FWD = ROOT / "data/crypto_metrics.parquet"
OUT = ROOT / "reports/reconstructed_oos/oi_ls_cross_sectional.json"
NTFY = ROOT / "data/secrets/ntfy.json"

HOLDOUT_END = "2026-05-31"     # embargo: 3 weeks before forward collection began (2026-06-22)
MIN_SYMBOLS = 8                # a cross-section needs breadth; drop thinner early dates
COST_PER_SIDE = 5e-4           # same net-of-cost convention as the autodiscovery factory


def _load_panel(dirp: Path, field: str) -> pd.DataFrame:
    cols = {}
    for f in sorted(dirp.glob("*.jsonl")):
        rows = []
        for ln in f.read_text("utf-8").splitlines():
            with contextlib.suppress(Exception):
                r = json.loads(ln)
                rows.append((r["date"], float(r[field])))
        if len(rows) >= 60:
            s = pd.Series(dict(rows), name=f.stem)
            cols[f.stem] = s[~s.index.duplicated()]
    df = pd.DataFrame(cols)
    df.index = pd.to_datetime(df.index)
    return df.sort_index()


def diff_verify() -> dict[str, Any]:
    """Archive vs the forward collector -- compared LIKE FOR LIKE.

    The forward collector is a POINT SNAPSHOT: measured 2026-07-26, it writes 1.36 rows per
    symbol-day, every one stamped 00:00-00:08 UTC. The archive carries two different quantities per
    day: `oi`/`ls` are the mean of all 288 5-min buckets, and `oi_first`/`ls_first` are the 00:00
    bucket. Diffing the snapshot against the 24h MEAN therefore compares two different statistics
    and scores their intraday drift as misalignment -- it aborted the whole backfill at ETHUSDT
    oi_corr 0.8403 while the reconstruction was fine. Against the matching `oi_first` field the same
    five symbols score 0.9609-0.9964 (measured, this file's own run).

    The thresholds below are UNCHANGED -- this fixes what is being compared, not how strictly.
    The mean-based numbers are still reported alongside as a drift diagnostic.
    """
    fwd = pd.read_parquet(FWD)
    fwd["date"] = pd.to_datetime(fwd["ts"]).dt.date.astype(str)
    daily = fwd.groupby(["date", "symbol"])[["open_interest", "ls_ratio"]].mean().reset_index()
    checks, worst = [], {"oi_corr": 1.0, "ls_corr": 1.0}
    for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT"):
        f = MET_DIR / f"{sym}.jsonl"
        if not f.exists():
            continue
        arch = {}
        for ln in f.read_text("utf-8").splitlines():
            with contextlib.suppress(Exception):
                r = json.loads(ln)
                # point-in-time first, falling back to the daily mean for older rows that predate
                # the *_first fields (those legitimately have only the mean available)
                arch[r["date"]] = (r.get("oi_first", r["oi"]), r.get("ls_first", r["ls"]),
                                   r["oi"], r["ls"])
        sub = daily[daily["symbol"] == sym]
        join = [(a, b, *arch[d]) for d, a, b in
                zip(sub["date"], sub["open_interest"], sub["ls_ratio"], strict=False)
                if d in arch]
        if len(join) < 10:
            continue
        # cols: fwd_oi, fwd_ls, arch_oi_pit, arch_ls_pit, arch_oi_mean, arch_ls_mean
        j = np.array(join, dtype="float64")
        oi_corr = float(np.corrcoef(j[:, 0], j[:, 2])[0, 1])
        ls_corr = float(np.corrcoef(j[:, 1], j[:, 3])[0, 1])
        oi_rd = float(np.median(np.abs(j[:, 2] - j[:, 0]) / np.abs(j[:, 0])))
        ls_rd = float(np.median(np.abs(j[:, 3] - j[:, 1]) / np.abs(j[:, 1])))
        checks.append({"symbol": sym, "days": len(join),
                       "oi_corr": round(oi_corr, 4), "ls_corr": round(ls_corr, 4),
                       "oi_med_rel_diff": round(oi_rd, 4), "ls_med_rel_diff": round(ls_rd, 4),
                       "compared_against": "archive point-in-time (oi_first/ls_first)",
                       "oi_corr_vs_daily_mean": round(
                           float(np.corrcoef(j[:, 0], j[:, 4])[0, 1]), 4),
                       "ls_corr_vs_daily_mean": round(
                           float(np.corrcoef(j[:, 1], j[:, 5])[0, 1]), 4)})
        worst["oi_corr"] = min(worst["oi_corr"], oi_corr)
        worst["ls_corr"] = min(worst["ls_corr"], ls_corr)
    if not checks:
        raise SystemExit("ABORT: no overlap with the forward collector to diff-verify against")
    if worst["oi_corr"] < 0.90 or worst["ls_corr"] < 0.60:
        raise SystemExit(f"ABORT: reconstruction misaligned vs forward truth {worst} "
                         "(bithumb/timezone class) -- do NOT trust this OOS")
    return {"checks": checks, "worst": worst}


def _sleeve_stats(rets: pd.Series, turnover: pd.Series, name: str) -> dict[str, Any]:
    gross = rets.dropna()
    cost = (turnover.reindex(gross.index).fillna(0.0)) * COST_PER_SIDE
    net = (gross - cost).to_numpy("float64")
    g = gross.to_numpy("float64")
    third = len(net) // 3
    regs = [round(float(sharpe_ratio(net[i * third:(i + 1) * third]) * np.sqrt(365)), 2)
            for i in range(3)] if third > 30 else []
    shp_n = sharpe_ratio(net)
    dsr2 = deflated_sharpe_ratio(net, n_trials=2,
                                 sharpe_estimates=np.array([shp_n, sharpe_ratio(g)]))
    dsr120 = deflated_sharpe_ratio(net, n_trials=120,
                                   sharpe_estimates=np.array([shp_n, sharpe_ratio(g)]))
    ann_net = float(shp_n * np.sqrt(365))
    verdict = "OOS-SURVIVES" if (dsr2.passed and ann_net > 0.5) else "OOS-FAILS"
    return {
        "sleeve": name, "days": len(net),
        "ann_sharpe_gross": round(float(sharpe_ratio(g) * np.sqrt(365)), 3),
        "ann_sharpe_net": round(ann_net, 3),
        "nw_t_net": round(float(nw_tstat(net)), 3),
        "dsr_pre_registered_2trials": round(float(dsr2.dsr), 3),
        "dsr2_passed": bool(dsr2.passed),
        "dsr_stress_120trials": round(float(dsr120.dsr), 3),
        "regime_thirds_net": regs,
        "cum_net": round(float(np.prod(1.0 + net) - 1.0), 4),
        "avg_daily_turnover": round(float(turnover.mean()), 4),
        "verdict": verdict,
    }


def main() -> None:
    ver = diff_verify()
    print("diff-verify PASSED:", json.dumps(ver["worst"]))

    piv_oi = _load_panel(MET_DIR, "oi")
    piv_ls = _load_panel(MET_DIR, "ls")
    prices = _load_panel(PX_DIR, "close")
    common = piv_oi.columns.intersection(piv_ls.columns).intersection(prices.columns)
    piv_oi, piv_ls, prices = piv_oi[common], piv_ls[common], prices[common]
    # Align the DATE index too, not just the symbol columns. The metric panels and the price panel
    # cover different spans, so a row mask built on one (line below: `enough`) is unalignable
    # against the others -- which crashed this backfill every run, behind the diff-verify abort.
    idx = piv_oi.index.intersection(piv_ls.index).intersection(prices.index).sort_values()
    piv_oi, piv_ls, prices = piv_oi.loc[idx], piv_ls.loc[idx], prices.loc[idx]
    print(f"panel: {len(common)} symbols x {len(piv_oi)} dates")

    cut = pd.Timestamp(HOLDOUT_END)
    piv_oi, piv_ls, prices = piv_oi[piv_oi.index <= cut], piv_ls[piv_ls.index <= cut], \
        prices[prices.index <= cut]
    enough = piv_ls.notna().sum(axis=1) >= MIN_SYMBOLS
    piv_oi, piv_ls, prices = piv_oi[enough], piv_ls[enough], prices[enough]

    # ---- LOCKED construction (mirrors run_derivative_shadow._forward_returns) ---------------
    pr_ret = prices.pct_change().shift(-1)
    d_price = prices.pct_change()
    d_oi = piv_oi.pct_change()
    oi_sig = np.sign(d_price) * np.sign(d_oi)
    ls_z = (piv_ls.sub(piv_ls.mean(axis=1), axis=0)).div(piv_ls.std(axis=1) + 1e-9, axis=0)
    ls_sig = -ls_z

    results = []
    for name, sig in (("oi_divergence", oi_sig), ("ls_contrarian", ls_sig)):
        w = sig.sub(sig.mean(axis=1), axis=0)
        w = w.div(w.abs().sum(axis=1) + 1e-9, axis=0)
        rets = (w * pr_ret).sum(axis=1)
        turnover = (w - w.shift(1)).abs().sum(axis=1)
        st = _sleeve_stats(rets, turnover, name)
        results.append(st)
        print(json.dumps(st, indent=1))

    payload = {
        "generated": datetime.now(tz=UTC).isoformat(),
        "holdout": f"{piv_ls.index.min().date()} .. {HOLDOUT_END}",
        "universe": f"tranche-1 cohort, {len(common)} symbols (archive-enumerated, incl. "
                    "delisted -- no survivorship pick)",
        "construction": "LOCKED from run_derivative_shadow._forward_returns (pre-registered "
                        "2026-07; holdout genuinely unseen)",
        "diff_verify": ver,
        "cost_per_side": COST_PER_SIDE,
        "results": results,
        "authority": "ZERO promotion authority -- forward clock + full gauntlet still decide",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"report -> {OUT}")

    with contextlib.suppress(Exception):
        topic = json.loads(NTFY.read_text("utf-8")).get("topic")
        if topic:
            msg = " | ".join(f"{r['sleeve']}: {r['verdict']} (net Sharpe {r['ann_sharpe_net']})"
                             for r in results)
            urllib.request.urlopen(urllib.request.Request(
                f"https://ntfy.sh/{topic}", data=f"OI/LS held-out OOS done: {msg}".encode(),
                method="POST"), timeout=10)


if __name__ == "__main__":
    main()
