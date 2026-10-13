"""LIVE HMM REGIME PROBABILITIES as a point-in-time state series, and the cells they condition.

    python desks/mt5/macro/regime_probabilities.py [--dry-run] [--budget-s 600] [--days 1500]

WHY (completion audit #8, 2026-10-06): the desk fits an HMM per symbol (`research/regime_hierarchy`)
and publishes TODAY's posterior, but no HISTORY of P(state) existed that a cell could be
conditioned on or a contract could judge -- the probabilities were a dashboard, not a state.

WHAT. Per MT5 symbol with H1 bars, a walk-forward Gaussian HMM (`libs.regime.hmm.GaussianHMM`,
three states on `libs.regime.features.raw_regime_features`: return, realised vol, trend):

    refit every REFIT days on the trailing FIT_WINDOW days, standardised with THAT window's own
    mean and sd; the forward filter (never the smoother) gives P(state_t | x_1..t) for the days
    until the next refit. States are named by their own realised-vol mean (quiet < normal <
    stress), so a label means the same thing across refits.

Per day: p_quiet, p_normal, p_stress, entropy (nats), p_switch = 1 - sum_j p_j A_jj (the chance
the regime changes by tomorrow), exp_duration = sum_j p_j / (1 - A_jj) (days), state_age (days
the filtered argmax has held), and var_hat = the one-step-ahead mixture forecast of next-day
return variance sum_j (p A)_j sigma_j^2.

POINT IN TIME. The broker's daily close of day d is knowable at d+1 01:00 UTC (declared lag); a
day's row is computed from bars up to d and parameters fitted on days strictly before the refit
day. data_source "mt5:bars" (the desk's own bars; no terms hold).

THE CONTRACTS (sensor_engines), each against its ungated base with a circular-shift null and the
realised-vol tercile as the control stratum:
    p_stress >= 0.6 -> 20-day trend      (stress persists: moves continue)
    p_quiet  >= 0.6 -> 1-day reversal    (quiet books mean-revert)
    p_switch high   -> |next-day return| rank (a likely change is a bigger move; monotone)
    var_hat vs trailing 252-day variance for the next-5-day realised variance (QLIKE): the
                         regime mixture must beat the long-run estimate it would equal without
                         regimes
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import sensor_engines as se  # noqa: E402

REPORT = DESK / "reports" / "REGIME_PROBABILITIES.json"
UNIVERSE_DIR = DESK / "data" / "universe"
ENGINE = "regime_probabilities"
DATA_SOURCE = "mt5:bars"
UNMEASURED = "UNMEASURED"
K = 3
NAMES = ("quiet", "normal", "stress")
REFIT = 63
FIT_WINDOW = 750
MIN_FIT = 300
WARMUP = 21
N_ITER = 30
SEED = 20261006
SYMBOLS = ("US500", "NAS100", "US30", "GER40", "JP225", "UK100", "HK50", "XAUUSD", "XAGUSD",
           "USOIL", "UKOIL", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF",
           "NZDUSD", "EURJPY", "BTCUSD", "ETHUSD")
SIGNALS = ("p_stress", "p_quiet", "entropy", "p_switch", "exp_duration", "state_age")


def available_at(d: str) -> datetime:
    day = date.fromisoformat(d)
    return datetime(day.year, day.month, day.day, 1, 0, tzinfo=UTC) + timedelta(days=1)


def daily_closes(symbol: str, universe_dir: Path = UNIVERSE_DIR) -> dict[str, float]:
    from macro.vol_conditioner import daily_closes as dc
    return dc(symbol, universe_dir)


def walk_forward(closes: dict[str, float], *, refit: int = REFIT, window: int = FIT_WINDOW,
                 deadline: float | None = None) -> tuple[list[dict[str, Any]], bool]:
    """(one PIT row per day after the first fit, complete?)."""
    import pandas as pd

    from libs.regime.features import raw_regime_features, standardise
    from libs.regime.hmm import GaussianHMM
    days = sorted(closes)
    if len(days) < MIN_FIT + WARMUP + 2:
        return [], True
    s = pd.Series([closes[d] for d in days], index=pd.to_datetime(days))
    raw = raw_regime_features(s)
    rets = raw[:, 0]
    rows: list[dict[str, Any]] = []
    t0 = MIN_FIT + WARMUP
    prev_arg, age = -1, 0
    for start in range(t0, len(days), refit):
        if deadline is not None and time.monotonic() > deadline:
            return rows, False
        lo = max(WARMUP, start - window)
        train = raw[lo:start]
        mu, sd = train.mean(axis=0), train.std(axis=0) + 1e-9
        hmm = GaussianHMM(n_states=K, n_iter=N_ITER, seed=SEED).fit(standardise(train, mu, sd))
        # name the states by their realised-vol mean (column 1, back in raw units)
        vol_mean = hmm.means[:, 1] * sd[1] + mu[1]
        order = list(np.argsort(vol_mean))
        stop = min(len(days), start + refit)
        x = standardise(raw[lo:stop], mu, sd)
        post = hmm.filter_posterior(x)[start - lo:]
        A = np.asarray(hmm.transmat, dtype=float)
        ret_var = np.asarray(hmm.vars[:, 0], dtype=float) * sd[0] ** 2
        stay = np.clip(np.diag(A), 0.0, 1.0 - 1e-6)
        for k, i in enumerate(range(start, stop)):
            p = post[k]
            arg = int(np.argmax(p))
            age = age + 1 if arg == prev_arg else 1
            prev_arg = arg
            nxt = p @ A
            ahead, v5 = p, 0.0
            for _h in range(5):
                ahead = ahead @ A
                v5 += float(ahead @ ret_var) / 5.0
            ent = float(-np.sum(p * np.log(np.clip(p, 1e-12, 1.0))))
            rows.append({
                "event_time": days[i], "available_time": available_at(days[i]).isoformat(),
                "knowable_basis": "declared_lag",
                **{f"p_{NAMES[j]}": round(float(p[order[j]]), 6) for j in range(K)},
                "entropy": round(ent, 6),
                "p_switch": round(float(1.0 - np.sum(p * np.diag(A))), 6),
                "exp_duration": round(float(np.sum(p / (1.0 - stay))), 4),
                "state_age": float(age),
                "state": NAMES[order.index(arg)],
                "var_hat": float(nxt @ ret_var),
                "var_hat_5d": v5,
                "ret": float(rets[i]),
            })
    return rows, True


def _strata(rows: list[dict[str, Any]], closes: dict[str, float]) -> list[int | None]:
    from macro.vol_conditioner import _terciles, rv_series
    rv = rv_series(closes)
    return _terciles([rv.get(r["event_time"]) for r in rows])


def contracts(symbol: str, rows: list[dict[str, Any]], closes: dict[str, float]
              ) -> list[dict[str, Any]]:
    days = sorted(closes)
    pos = {d: i for i, d in enumerate(days)}
    trend, rev, absr, y5, base5, var_hat, gate_rows = [], [], [], [], [], [], []
    for r in rows:
        i = pos[r["event_time"]]
        if i < 253 or i + 6 >= len(days):
            continue
        c = [closes[days[k]] for k in range(i - 20, i + 7)]
        long = [closes[days[k]] for k in range(i - 252, i + 1)]
        r_today = c[20] / c[19] - 1.0
        r_next = c[21] / c[20] - 1.0
        mom = c[20] / c[0] - 1.0
        trend.append(math.copysign(1.0, mom) * r_next if mom else 0.0)
        rev.append(-math.copysign(1.0, r_today) * r_next if r_today else 0.0)
        absr.append(abs(r_next))
        fwd = [math.log(c[k + 1] / c[k]) for k in range(20, 25)]
        past = [math.log(long[k + 1] / long[k]) for k in range(252)]
        y5.append(float(np.mean(np.square(fwd))))
        base5.append(float(np.var(past, ddof=1)))
        var_hat.append(float(r["var_hat_5d"]))
        gate_rows.append(r)
    strata = _strata(gate_rows, closes)
    common = {"engine": ENGINE, "cards": ["AUDIT-8"]}
    out = [
        se.gated_gain(trend, [r["p_stress"] >= 0.6 for r in gate_rows], **common,
                      baseline="20-day trend, ungated", strata=strata,
                      falsifier="trend in the stress state no better than ungated, or gone "
                                "inside realised-vol terciles"),
        se.gated_gain(rev, [r["p_quiet"] >= 0.6 for r in gate_rows], **common,
                      baseline="1-day reversal, ungated", strata=strata,
                      falsifier="reversal in the quiet state no better than ungated"),
        se.monotone_gain([r["p_switch"] for r in gate_rows], absr, **common,
                         falsifier="no rank order between switch probability and the next "
                                   "day's absolute move"),
        se.forecast_gain(y5, var_hat, base5, **common, loss="qlike",
                         baseline="trailing 252-day variance (the long-run estimate)",
                         falsifier="the regime mixture forecast of next-5-day variance is no "
                                   "better than trailing variance"),
    ]
    for c, lbl in zip(out, ("p_stress->trend", "p_quiet->reversal", "p_switch->|move|",
                            "var_hat->next5_variance"), strict=True):
        c.update({"label": lbl, "symbol": symbol})
    return out


def observations(symbol: str, last: dict[str, Any], received_at: datetime) -> list[Any]:
    from libs.research import sensor_contract as sc
    know = last["available_time"]
    rx = max(received_at.isoformat(), str(know))
    out = []
    for metric in ("p_quiet", "p_normal", "p_stress", "entropy", "p_switch", "exp_duration"):
        out.append(sc.make(sensor_id="market:regime_probabilities", source_id=DATA_SOURCE,
                           metric=f"hmm_{metric}", entity=symbol, kind="state",
                           sensor_class="market_state", asset_domain="regime",
                           value=float(last[metric]), event_time=last["event_time"],
                           knowable_at=know, knowable_basis="declared_lag", received_at=rx,
                           parse_complete_at=rx, licence="the desk's own MT5 bars",
                           commercial_rights="own data",
                           attributes={"state": last["state"], "state_age": last["state_age"]}))
    return out


def run(*, dry_run: bool = False, universe_dir: Path = UNIVERSE_DIR, budget_s: float = 600.0,
        days: int = 1500, now: datetime | None = None,
        symbols: tuple[str, ...] = SYMBOLS) -> dict[str, Any]:
    when = now or datetime.now(UTC)
    deadline = time.monotonic() + budget_s
    grounds: dict[str, Any] = {}
    all_c: list[dict[str, Any]] = []
    obs: list[Any] = []
    for sym in symbols:
        closes = daily_closes(sym, universe_dir)
        if not closes:
            grounds[sym] = {"status": "NOT_TRADEABLE_HERE", "why": f"no {sym}_H1.parquet"}
            continue
        keep = sorted(closes)[-(days + MIN_FIT + WARMUP):]
        closes = {d: closes[d] for d in keep}
        rows, complete = walk_forward(closes, deadline=deadline)
        rows = [r for r in rows if datetime.fromisoformat(r["available_time"]) <= when]
        if not rows:
            grounds[sym] = {"status": UNMEASURED,
                            "why": f"{len(closes)} broker days < {MIN_FIT + WARMUP + 2}"
                            if complete else "budget spent before the first fit"}
            continue
        cs = contracts(sym, rows, closes)
        all_c.extend(cs)
        sid = f"ws_regime_prob_{sym.lower()}"
        info: dict[str, Any] = {"status": "COMPUTED" if complete else "PARTIAL",
                                "rows": len(rows), "series_id": sid, "data_source": DATA_SOURCE,
                                "last": {k: rows[-1][k] for k in (*SIGNALS, "p_normal", "state",
                                                                  "event_time")}}
        if not dry_run:
            info["lake"] = se.write_lake_series(sid, [
                {k: v for k, v in r.items() if k not in ("knowable_basis", "state", "ret")}
                for r in rows])
            info["cells"] = se.emit_conditioner_cells(
                sid, list(SIGNALS), [sym],
                mechanism=(f"{sym}'s own filtered HMM regime probabilities: stress persists and "
                           f"trends, quiet books mean-revert, and a likely regime switch is a "
                           f"larger move"),
                falsifier="gate effect indistinguishable from the shuffled-state gate across "
                          "the judged cells", generator=ENGINE, sides=(1, -1),
                data_source=DATA_SOURCE)
            obs.extend(observations(sym, rows[-1], when))
        grounds[sym] = info
    report: dict[str, Any] = {"at": when.isoformat(timespec="seconds"), "engine": ENGINE,
                              "audit_item": 8, "grounds": grounds, "contracts": all_c,
                              "method": f"walk-forward GaussianHMM K={K}, refit every {REFIT} "
                                        f"days on {FIT_WINDOW}, forward filter only",
                              "authority": "NONE"}
    if not dry_run:
        se.publish(ENGINE, all_c)
        if obs:
            try:
                from libs.research import sensor_contract as sc
                report["ledger"] = sc.SensorLedger().append(obs)
            except Exception as exc:
                report["ledger"] = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="walk-forward HMM regime probabilities (audit #8)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--days", type=int, default=1500)
    args = ap.parse_args(argv)
    rep = run(dry_run=args.dry_run, budget_s=args.budget_s, days=args.days)
    text = json.dumps(rep, indent=1, sort_keys=True, default=str)
    if args.dry_run:
        print(text[:4000])
        return 0
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(".tmp")
    tmp.write_text(text + "\n", "utf-8")
    tmp.replace(REPORT)
    v = [c.get("verdict") for c in rep["contracts"]]
    print(f"regime_probabilities: grounds={len(rep['grounds'])} contracts={len(v)} "
          f"GAIN={v.count('GAIN')} NO_GAIN={v.count('NO_GAIN')} UNMEASURED={v.count('UNMEASURED')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
