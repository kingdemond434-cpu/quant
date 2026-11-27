"""JOINT E8 + FTMO SIZING: TWO ACCOUNTS ON ONE SIGNAL ARE ONE BET (IDEA_QUEUE row 199, pass 20).

REPORT ONLY. It sizes nothing live and writes no config.

FTMO 2-Step follows the same gold_asia signal as E8, by hand and in the same direction. A
bad night therefore lands on both accounts at once. This report measures:

    P(both hit their daily limit on the same day)    per trading day, from the replay
    P(E8 fails), P(FTMO fails), P(both), P(either)   within 21 and 30 trading days, by block
                                                     bootstrap of the replay's day-R series
    the FTMO risk fraction that holds P(either fails) under a target, with 0.009 checked

THE R DISTRIBUTION. Live E8 fills (joined_fills.json) are not in the repo, so the E8 leg-R history
is UNMEASURED here. The R series comes from `prop_tail_stress.replay_gold_asia` over the repo's
XAUUSD H1 bars (2018-2026), built with the gateway's own bracket arithmetic. There are three
variants:

    base        OCO honoured, no slip
    slip_tail   OCO honoured, the one measured 24.13-point E8 slip (scaled by price) charged on
                EVERY stop exit. This is a bound, not an estimate: there is 1 measured exit and
                fewer than the 20 needed to fit a tail.
    oco_fail    both bracket legs can fill (the duplicate or missed-cancel case), with the slip
                tail as well

The Fusion live gold_asia legs in data/live_ledger.jsonl serve as a cross-check, and only their R
is read.

THE FOLLOWER. FTMO's R equals E8's R, less `follower_lag_r` per filled leg (manual entry lag). The
lag is UNMEASURED, so 0 is the baseline and a sensitivity is published beside it. At a lag of 0
the two accounts are perfectly correlated by construction, which is the point of the row.

THE DAILY RULE includes floating P&L on both venues. The day's loss tested against it is the
replay's `worst_intraday_r`: every leg's worst bar excursion, summed as if simultaneous. The
equity path uses the closed R.

TARGET. The acceptable joint failure probability is the principal's decision and is not in the
repo, so it is UNMEASURED. The pick is published for 1%, 5% and 10%.

Builds on p17 row 207 (`combined_prop_risk`, bundle cbd74bd87): that report's headline was
2 legs x 1R plus a 1.5R gap, so 3.5R. This report replaces that assumed day with the measured
distribution of days.

    python research/prop_joint_breach.py       -> reports/PROP_JOINT_BREACH.json

NO SCRIPT ENTRY GUARD (birth-obligation law, scripts/check_birth_obligations.py).
The hourly leg `prop_joint_breach` (research/hourly_cycle.py) calls `main()`
in-process. By hand, from the repo root:
    python -c "import sys; sys.path[:0]=['desks/mt5'];
        from research import prop_joint_breach as M; M.main()"
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import prop_tail_stress as pts  # noqa: E402

UNMEASURED = pts.UNMEASURED
DESK = pts.DESK
OUT = DESK / "reports" / "PROP_JOINT_BREACH.json"
LIVE_LEDGER = DESK / "data" / "live_ledger.jsonl"

HORIZONS = (21, 30)
TARGETS = (0.01, 0.05, 0.10)
FTMO_SWEEP = tuple(round(x, 4) for x in np.arange(0.003, 0.0151, 0.001))
BLOCK = 5
N_PATHS = 4000
P17_HEADLINE_R = 3.5


@dataclass(frozen=True)
class Rules:
    start: float
    daily: float      # fraction of the day's start balance
    max_dd: float     # static, fraction of start
    target: float     # profit target, fraction of start; trading stops once it is reached



def e8_rules() -> Rules:
    c = pts.parse_constants(pts.E8_GUARD_SRC, ("START_BALANCE", "DAILY_DRAWDOWN",
                                               "STATIC_DRAWDOWN", "PROFIT_TARGET"))
    return Rules(c["START_BALANCE"], c["DAILY_DRAWDOWN"], c["STATIC_DRAWDOWN"],
                 c["PROFIT_TARGET"])


FTMO_RULES = Rules(pts.FTMO_START, pts.FTMO_DAILY, pts.FTMO_MAX, 0.10)


# ------------------------------------------------------------------ per-day joint breach

def same_day_breach(days: pd.DataFrame, e8_risk: float, ftmo_risk: float, e8: Rules,
                    ftmo: Rules, follower_lag_r: float = 0.0) -> dict[str, Any]:
    """Counts of replay days on which each account's floating-inclusive day loss reaches its
    daily limit, from a fresh day-start balance. Zero observed days is reported as a count with a
    rule-of-three 95% upper bound, never as a probability of 0."""
    worst = days["worst_intraday_r"].to_numpy()
    lag = follower_lag_r * days["n_legs"].to_numpy()
    e8_hit = -worst * e8_risk >= e8.daily
    ftmo_hit = -(worst - lag) * ftmo_risk >= ftmo.daily
    n = len(days)

    def rate(mask: np.ndarray) -> dict[str, Any]:
        k = int(mask.sum())
        return {"days": k, "of": n, "p_per_day": (k / n) if k else None,
                "p_per_day_upper95": (3.0 / n) if k == 0 else None,
                "note": "0 observed: bound only" if k == 0 else "observed"}
    both = e8_hit & ftmo_hit
    return {"e8": rate(e8_hit), "ftmo": rate(ftmo_hit), "both": rate(both),
            "p_both_given_e8": (float(both.sum() / e8_hit.sum()) if e8_hit.any() else UNMEASURED),
            "e8_daily_threshold_r": round(e8.daily / e8_risk, 3),
            "ftmo_daily_threshold_r": round(ftmo.daily / ftmo_risk, 3)}


# ------------------------------------------------------------------ path simulation

def block_bootstrap_idx(n: int, horizon: int, paths: int, block: int,
                        rng: np.random.Generator) -> np.ndarray:
    """(paths, horizon) row indices: circular blocks of `block` consecutive days."""
    n_blocks = -(-horizon // block)
    starts = rng.integers(0, n, size=(paths, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % n
    return idx.reshape(paths, -1)[:, :horizon]


def simulate(r: np.ndarray, worst: np.ndarray, n_legs: np.ndarray, risk: float, rules: Rules,
             idx: np.ndarray, lag_r: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """(failed, day_of_daily_breach) per path for one account. Risk is a fraction of the day's
    start equity, the way both lanes size. A path stops at its first failure or once it reaches
    the target. day_of_daily_breach is -1 where it never breached daily."""
    paths, horizon = idx.shape
    eq = np.full(paths, rules.start)
    alive = np.ones(paths, dtype=bool)
    failed = np.zeros(paths, dtype=bool)
    daily_day = np.full(paths, -1)
    floor = rules.start * (1 - rules.max_dd)
    tgt = rules.start * (1 + rules.target)
    for t in range(horizon):
        j = idx[:, t]
        day_r = r[j] - lag_r * n_legs[j]
        day_w = worst[j] - lag_r * n_legs[j]
        risk_ccy = eq * risk
        intraday_low = eq + day_w * risk_ccy
        d_hit = alive & ((eq - intraday_low) >= rules.daily * eq)
        m_hit = alive & (intraday_low <= floor)
        hit = d_hit | m_hit
        daily_day = np.where(d_hit & (daily_day < 0), t, daily_day)
        failed |= hit
        eq = np.where(alive & ~hit, eq + day_r * risk_ccy, eq)
        alive &= ~hit
        alive &= eq < tgt
    return failed, daily_day


def joint_paths(days: pd.DataFrame, e8_risk: float, ftmo_risk: float, e8: Rules, ftmo: Rules,
                horizon: int, *, paths: int = N_PATHS, seed: int = 20, lag_r: float = 0.0
                ) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    idx = block_bootstrap_idx(len(days), horizon, paths, BLOCK, rng)
    r = days["r"].to_numpy()
    w = days["worst_intraday_r"].to_numpy()
    k = days["n_legs"].to_numpy().astype(float)
    f_e8, d_e8 = simulate(r, w, k, e8_risk, e8, idx)
    f_ft, d_ft = simulate(r, w, k, ftmo_risk, ftmo, idx, lag_r=lag_r)
    same = (d_e8 >= 0) & (d_e8 == d_ft)
    return {"p_e8_fail": float(f_e8.mean()), "p_ftmo_fail": float(f_ft.mean()),
            "p_both_fail": float((f_e8 & f_ft).mean()),
            "p_either_fail": float((f_e8 | f_ft).mean()),
            "p_both_daily_same_day": float(same.mean()),
            "p_both_given_either": (float((f_e8 & f_ft).sum() / (f_e8 | f_ft).sum())
                                    if (f_e8 | f_ft).any() else None),
            "paths": paths, "horizon_days": horizon}


def pick_ftmo_risk(sweep: list[dict[str, Any]], target: float, key: str = "p_either_fail"
                   ) -> float | None:
    """The largest swept FTMO fraction whose joint fail probability stays at or under target.
    None if even the smallest one does not."""
    ok = [row["ftmo_risk"] for row in sweep if row[key] <= target]
    return max(ok) if ok else None


# ------------------------------------------------------------------ live cross-check

def live_leg_r(path: Path = LIVE_LEDGER, sleeve: str = "gold_asia") -> dict[str, Any]:
    """R of the Fusion live gold_asia legs: pl / |risk|. Only R leaves this function. No account
    field is read into the report."""
    rs: list[float] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {"n": 0, "status": UNMEASURED}
    for ln in lines:
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if not isinstance(row, dict) or row.get("sleeve") != sleeve:
            continue
        risk = row.get("risk_quote")
        pl = row.get("pl_quote")
        if isinstance(risk, (int, float)) and risk and isinstance(pl, (int, float)):
            rs.append(float(pl) / abs(float(risk)))
    if not rs:
        return {"n": 0, "status": UNMEASURED}
    a = np.array(rs)
    return {"n": int(a.size), "mean_r": round(float(a.mean()), 3),
            "worst_r": round(float(a.min()), 3), "venue": "Fusion (not E8)",
            "status": "MEASURED, small sample"}


def published_rules(rules: Rules) -> dict[str, float]:
    """The rule set as the report publishes it: fractions of the start balance only."""
    return {"daily": rules.daily, "max_dd": rules.max_dd, "target": rules.target}


# ------------------------------------------------------------------ build

def build(*, e8_risk: float = pts.E8_RISK_PER_LEG, ftmo_risk: float = pts.FTMO_RISK_PER_LEG,
          paths: int = N_PATHS, xau: pd.DataFrame | None = None) -> dict[str, Any]:
    xau = pts.load_bars("XAUUSD") if xau is None else xau
    e8 = e8_rules()
    variants = {
        "base": pts.replay_gold_asia(xau, oco=True, slip_frac=0.0),
        "slip_tail": pts.replay_gold_asia(xau, oco=True, slip_frac=pts.SLIP_FRAC),
        "oco_fail": pts.replay_gold_asia(xau, oco=False, slip_frac=pts.SLIP_FRAC),
    }
    out: dict[str, Any] = {}
    for name, days in variants.items():
        v: dict[str, Any] = {
            "days": len(days),
            "mean_day_r": round(float(days["r"].mean()), 4),
            "worst_day_r": round(float(days["r"].min()), 3),
            "worst_intraday_r": round(float(days["worst_intraday_r"].min()), 3),
            "same_day_daily_breach": same_day_breach(days, e8_risk, ftmo_risk, e8, FTMO_RULES),
            "same_day_daily_breach_lag0.1r": same_day_breach(days, e8_risk, ftmo_risk, e8,
                                                             FTMO_RULES, follower_lag_r=0.1),
            "paths": {str(h): joint_paths(days, e8_risk, ftmo_risk, e8, FTMO_RULES, h,
                                          paths=paths) for h in HORIZONS},
        }
        sweep = []
        for f in FTMO_SWEEP:
            jp = joint_paths(days, e8_risk, f, e8, FTMO_RULES, 30, paths=paths)
            sweep.append({"ftmo_risk": f, **{k: round(jp[k], 4) for k in
                                             ("p_ftmo_fail", "p_both_fail", "p_either_fail",
                                              "p_both_daily_same_day")}})
        v["ftmo_sweep_30d"] = sweep
        v["ftmo_pick_by_target"] = {str(t): pick_ftmo_risk(sweep, t) for t in TARGETS}
        live = next(r for r in sweep if abs(r["ftmo_risk"] - ftmo_risk) < 1e-9) \
            if any(abs(r["ftmo_risk"] - ftmo_risk) < 1e-9 for r in sweep) else None
        v["check_ftmo_live_fraction"] = {
            "ftmo_risk": ftmo_risk, "row": live,
            "within_target": ({str(t): (live["p_either_fail"] <= t) for t in TARGETS}
                              if live else UNMEASURED)}
        out[name] = v
    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "idea_queue_row": 199, "report_only": True,
        "e8_risk_per_leg": e8_risk, "ftmo_risk_per_leg": ftmo_risk,
        # Rules as fractions of each account's start; no balance is published.
        "rules": {"E8": published_rules(e8), "FTMO": published_rules(FTMO_RULES)},
        "target": UNMEASURED, "targets_published": list(TARGETS),
        "follower_lag_r": {"baseline": 0.0, "sensitivity": 0.1, "status": UNMEASURED},
        "e8_live_leg_r": {"status": UNMEASURED, "why": "joined_fills.json not in repo"},
        "fusion_live_leg_r": live_leg_r(),
        "p17_row207_headline": {"day_r": P17_HEADLINE_R,
                                "e8_loss_frac_of_start": round(P17_HEADLINE_R * e8_risk, 5),
                                "ftmo_loss_frac_of_start": round(P17_HEADLINE_R * ftmo_risk,
                                                                 5)},
        "bootstrap": {"block_days": BLOCK, "paths": paths, "seed": 20},
        "tail_event_injection": {
            "status": "SENSITIVITY: per-day tail frequency UNMEASURED",
            "note": ("A prop_tail_stress scenario that breaches both daily limits (flash_crash, "
                     "weekend_gap, snb_2015) adds about 1-(1-p)^H to P(both fail)"),
            "p_both_add_30d": {str(p): round(1 - (1 - p) ** 30, 4) for p in (1 / 2000, 1 / 500)}},
        "variants": out,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--paths", type=int, default=N_PATHS)
    ap.add_argument("--ftmo-risk", type=float, default=pts.FTMO_RISK_PER_LEG)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build(ftmo_risk=a.ftmo_risk, paths=a.paths)
    text = json.dumps(doc, indent=1, default=str)
    if a.dry_run:
        print(text)
    else:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text, encoding="utf-8")
        print(a.out)
    return 0

