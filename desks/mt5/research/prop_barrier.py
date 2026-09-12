"""E8 PRO, $100K, ACCOUNT 2478877 -- the barrier problem this account actually poses.

Bought 2026-09-12 (order 20260977504, $485). The invoice's own numbers:

    Initial balance   $100,000
    Static drawdown   10%      -- a FLOOR at $90,000 that never trails
    Daily drawdown    2.5%     -- $2,500 from the day's starting balance, hard breach
    Platform          TradeLocker
    Execution         no commissions
    Payout            100%

plus the two numbers the invoice does not print, CONFIRMED BY THE PRINCIPAL off the E8 dashboard
on 2026-09-12:

    Profit target     10%      -- $10,000
    Daily profit cap  2%       -- $2,000 counted per day, excess STRIPPED at rollover

The target matters more than anything else here and the invoice does not carry it, so it was
solved as a parameter until the principal read it off the dashboard. Note what it makes this
account: target 10% against a 10% drawdown is a barrier RATIO of 1.0, which is better than E8
One's fixed 1.5x (12% target against an 8% drawdown). The published E8 Pro standard is 8%/8%;
this is a different configuration and the third-party rule pages do not describe it.

THE RULE THAT DOMINATES EVERYTHING IS THE ONE NOT ON THE INVOICE: the 2% DAILY PROFIT CAP.
E8 strips profit above 2% of the initial balance at rollover -- it does not merely stop counting
it, it REMOVES it from the balance between midnight and 1am server time, and splitting a winner
across days by hedging or partial closes is explicitly disallowed. Three consequences, and they
run against the ordinary intuition about prop accounts:

  1. THERE IS A HARD FLOOR ON SPEED. A 10% target at 2% a day is FIVE trading days. No
     portfolio, edge or size can beat it, and a book fast enough to reach it is giving away
     everything above +2% on each of those days. "Pass it fastest" is therefore not an open
     question -- the rules answer it -- and what is left to optimise is P(pass) and the tail.
     E8 publishes no time limit on Pro, so a slow pass is slow and not a loss.

  2. THE PAYOFF IS TRUNCATED ABOVE AND NOT BELOW. A day is capped at +2% and free to run to
     -2.5%. Every unit of daily variance is taxed: the right tail is confiscated and the left
     tail is what kills the account. A book whose good day is +5% does not bank +5%; it banks
     +2% and keeps all of the risk that produced it.

  3. SO THE OPTIMAL SIZE IS THE ONE WHOSE GOOD DAY LANDS NEAR +2%, NOT ABOVE IT. Sizing up is
     doubly punished, which is the opposite of the growth-optimal posture the live book runs.
     This is not a "reduce aggressiveness" argument and it is not applied to the live account:
     it is the same E[log W] logic answering a different question, because on a barrier with a
     confiscated right tail the growth-optimal size and the pass-optimal size are different
     numbers. `mt5desk/account_profile.py` already draws this line between the two venues.

WHAT THIS FILE IS NOT. It is not a decision to trade and it gives no sleeve any capital. It
prices the arena so a portfolio can be chosen against it; the ten gates, a forward clock and
measured rent still decide what runs, exactly as for anything else.

Artifact: desks/mt5/reports/PROP_BARRIER.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "PROP_BARRIER.json"

# ------------------------------------------------------------------ the arena, from the invoice
BALANCE = 100_000.0
STATIC_DD = 0.10          # invoice: "Static drawdown: 10%" -- a floor, never trails
DAILY_DD = 0.025          # invoice: "Daily Drawdown: 2.5%"
DAILY_PROFIT_CAP = 0.02   # E8 Pro published rule; excess STRIPPED at rollover

#: CONFIRMED by the principal from the E8 dashboard, 2026-09-12. The 8% row is kept as the
#: published E8 Pro standard so a future account on the standard configuration is already priced,
#: and so the difference the extra 2% of target costs is visible rather than asserted.
TARGET = 0.10
TARGETS: tuple[tuple[str, float], ...] = (
    ("target_10pct", 0.10),   # THIS ACCOUNT
    ("target_8pct", 0.08),    # E8 Pro's published standard, for comparison
)

#: Hard floor on time, from the profit cap alone. No edge and no size can beat it.
def min_days(target: float) -> int:
    """Ceiling of target / daily cap. The rules' own answer to "how fast can this pass"."""
    return int(np.ceil(target / DAILY_PROFIT_CAP))


# ------------------------------------------------------------------ the book being simulated
@dataclass(frozen=True)
class Book:
    """A portfolio as the barrier sees it: how often it fires, how big, how good, how correlated.

    `exp_r` is expectancy per trade in R and `win_rate`/`rr` reconstruct the SHAPE, because the
    barrier cares about the path and not only the mean. A +0.20R book that wins 70% of the time
    at 1:1 and one that wins 30% at 4:1 have the same drift and completely different daily
    distributions, and on a rule that truncates the right tail that difference is the answer.
    """
    sleeves: int
    risk_frac: float          # per trade, as a fraction of the INITIAL balance
    exp_r: float              # expectancy per trade, in R
    rr: float                 # reward:risk on a win
    trades_per_day_per_sleeve: float
    rho: float                # correlation between sleeves firing in the SAME session
    #: Independent sessions per day. The desk's windows are asia / london_am / afternoon, and the
    #: count matters because it is what stops a within-day stop-loss rule from reading the whole
    #: day's regime off its first trade. Measured structure, not a tuning knob.
    sessions: int = 3

    @property
    def win_rate(self) -> float:
        """p such that p*rr - (1-p)*1 == exp_r."""
        return float((self.exp_r + 1.0) / (self.rr + 1.0))

    @property
    def trades_per_day(self) -> float:
        return self.sleeves * self.trades_per_day_per_sleeve


@dataclass
class Outcome:
    n_paths: int
    passed: int = 0
    failed_daily: int = 0
    failed_static: int = 0
    timed_out: int = 0
    days: list[int] = field(default_factory=list)
    worst_dd: list[float] = field(default_factory=list)
    stripped: list[float] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        d = np.array(self.days, dtype=float) if self.days else np.array([np.nan])
        dd = np.array(self.worst_dd, dtype=float) if self.worst_dd else np.array([np.nan])
        st = np.array(self.stripped, dtype=float) if self.stripped else np.array([0.0])
        return {
            "p_pass": round(self.passed / self.n_paths, 4),
            "p_fail_daily": round(self.failed_daily / self.n_paths, 4),
            "p_fail_static": round(self.failed_static / self.n_paths, 4),
            "p_timeout": round(self.timed_out / self.n_paths, 4),
            "days_median": None if not self.days else int(np.median(d)),
            "days_p25": None if not self.days else int(np.percentile(d, 25)),
            "days_p90": None if not self.days else int(np.percentile(d, 90)),
            "worst_dd_median_pct": round(float(np.median(dd)) * 100, 2),
            "worst_dd_p90_pct": round(float(np.percentile(dd, 90)) * 100, 2),
            "profit_stripped_median_usd": int(np.median(st)),
        }


# ------------------------------------------------------------------ the simulation
def simulate(book: Book, target: float, *, n_paths: int = 20_000, max_days: int = 250,
             seed: int = 20260912, stand_down: float | None = None) -> Outcome:
    """Walk `n_paths` accounts through the real rule set, trade by trade.

    THE BARRIERS ARE CHECKED INTRADAY, NOT AT ROLLOVER, because that is how they are enforced:
    an equity touch of either floor ends the account at the moment it happens. Checking at end of
    day would let a path dip through a floor and recover, which flatters every result.

    THE CAP IS APPLIED AT ROLLOVER, which is when E8 applies it. Within a day the equity really
    does rise above +2%, and that equity genuinely cushions a later loss in the SAME day, so it
    must be there while it is there. Applying the cap intraday would understate the daily floor's
    bite; never applying it would hand the book profit it does not keep.

    CORRELATION IS A GAUSSIAN COPULA ON ONE COMMON FACTOR PER **SESSION**, AND THE DIFFERENCE
    BETWEEN THAT AND ONE PER DAY IS THE LARGEST SINGLE RESULT IN THIS FILE.

    A first version drew one common factor per DAY, so every trade a book placed between midnight
    and midnight shared it. That conflates two unrelated things: sleeves firing at the SAME MOMENT
    are correlated (they are the same mechanism on correlated instruments -- rho 0.70 measured),
    while the same sleeve at 03:00 and at 14:00 is very nearly independent. Under a daily factor
    the regime is fixed at midnight and the first trade of the day REVEALS it, so a rule that
    stops after one loss becomes a regime detector -- and the simulation duly reported a 98% pass
    rate on a book with ZERO edge, which is impossible for any rule applied to a driftless walk
    that also has its right tail confiscated. The tell was that a driftless book could not
    plausibly reach +10% in a median 56 days at $720 of daily sigma: that is 1.9 sigma of
    cumulative luck, and 98% of paths do not get it.

    A separate, deliberately naive day-by-day reimplementation with independent trades measured
    E[day P&L] at -0.000015 (uncapped) and -0.000125 (capped) with the stop, against -0.000004
    and -0.000153 without it -- i.e. the stop moves variance and not drift, which is what a stop
    on a driftless process must do. The daily-factor result was the model, not the market.

    So the day is now split into `sessions` clusters. Within a cluster the sleeves share a factor
    at `rho`; across clusters the factors are independent, because the desk's own windows are
    asia / london_am / afternoon and a London reversal is not an Asian one. Three is the desk's
    measured number of windows, not a tuning knob.

    The win/loss threshold is `Phi^-1(win_rate)` computed ONCE, so the latent normal maps to the
    right Bernoulli with no per-trade special function.
    """
    #: A VOLUNTARY DAILY STOP, SET INSIDE E8'S. `stand_down` is the fraction of the day's
    #: starting balance at which the book stops opening for the rest of the session. It cannot
    #: help a path that is already through the floor -- it exists to stop the LAST trade of a bad
    #: day being the one that breaches -- so whether it is worth having is an empirical question
    #: about how often a day arrives at the floor in small steps rather than one gap. Measured,
    #: not assumed: at the recommended size the binding failure is TIMEOUT, not breach, and the
    #: rule buys almost nothing there; it earns its keep only at sizes this file does not
    #: recommend. Reported either way rather than adopted because it sounds prudent.
    rng = np.random.default_rng(seed)
    unit = book.risk_frac * BALANCE
    static_floor = BALANCE * (1.0 - STATIC_DD)
    cap_usd = BALANCE * DAILY_PROFIT_CAP
    target_equity = BALANCE * (1.0 + target)
    thresh = NormalDist().inv_cdf(book.win_rate)
    a, b = float(np.sqrt(book.rho)), float(np.sqrt(1.0 - book.rho))

    P = n_paths
    equity = np.full(P, BALANCE)
    peak = np.full(P, BALANCE)
    worst = np.zeros(P)
    stripped = np.zeros(P)
    days = np.zeros(P, dtype=np.int32)
    # 0 running, 1 pass, 2 fail_daily, 3 fail_static
    state = np.zeros(P, dtype=np.int8)

    for day in range(1, max_days + 1):
        live = state == 0
        if not live.any():
            break
        days[live] = day
        day_start = equity.copy()
        daily_floor = day_start * (1.0 - DAILY_DD)
        halt = None if stand_down is None else day_start * (1.0 - stand_down)
        n = rng.poisson(book.trades_per_day, P)
        # One factor per SESSION, assigned to trades in blocks: trade t belongs to session
        # t // trades_per_session, so consecutive trades share a regime and distant ones do not.
        per_session = max(1.0, book.trades_per_day / max(1, book.sessions))
        factors = rng.standard_normal((book.sessions + 2, P))
        for t in range(int(n.max()) if n.size else 0):
            common = factors[min(int(t // per_session), book.sessions + 1)]
            act = live & (state == 0) & (n > t)
            if halt is not None:
                act = act & (equity > halt)
            if not act.any():
                break
            z = a * common + b * rng.standard_normal(P)
            pnl = np.where(z < thresh, unit * book.rr, -unit)
            equity = np.where(act, equity + pnl, equity)
            peak = np.maximum(peak, equity)
            worst = np.maximum(worst, (peak - equity) / BALANCE)
            # STATIC FIRST, then daily: on a path that breaches both in one trade the account is
            # gone either way, and attributing it to the floor that can never be reset is the
            # honest reading of which rule ended it.
            state = np.where(act & (equity <= static_floor), 3, state)
            state = np.where(act & (state == 0) & (equity <= daily_floor), 2, state)

        roll = live & (state == 0)
        gain = equity - day_start
        over = roll & (gain > cap_usd)
        stripped = np.where(over, stripped + (gain - cap_usd), stripped)
        equity = np.where(over, day_start + cap_usd, equity)
        peak = np.minimum(peak, np.maximum(equity, BALANCE))
        state = np.where(roll & (equity >= target_equity), 1, state)

    out = Outcome(n_paths=P)
    out.passed = int((state == 1).sum())
    out.failed_daily = int((state == 2).sum())
    out.failed_static = int((state == 3).sum())
    out.timed_out = int((state == 0).sum())
    out.days = days[state == 1].tolist()
    out.worst_dd = worst.tolist()
    out.stripped = stripped.tolist()
    return out


# ------------------------------------------------------------------ the sweep
#: Risk per trade, as a fraction of the initial balance. The live desk's own figure is far above
#: this range; that is the point of `account_profile`, not an inconsistency -- the live book is
#: solving for growth and this one is solving a barrier with its right tail confiscated.
RISK_GRID = (0.0015, 0.0025, 0.0035, 0.0050, 0.0075)

#: A VOLUNTARY DAILY STOP SET INSIDE E8'S. `None` is "no rule beyond the firm's own".
STAND_DOWN_GRID: tuple[float | None, ...] = (None, 0.0100, 0.0075, 0.0050)

#: What the desk can actually field, and what it would be if the two enrolled-but-unfired
#: mechanisms accrue evidence. rho 0.70 is the measured same-mechanism figure.
#: (name, sleeves, rho). `rr` and the firing rate are the desk's measured figures and are the
#: same in every row, so they are named once at the call site rather than repeated four times.
BOOKS: tuple[tuple[str, int, float], ...] = (
    ("1 mechanism, 4 correlated sleeves (what the desk has TODAY)", 4, 0.70),
    ("3 independent mechanisms, 4 sleeves", 4, 0.20),
    ("3 independent mechanisms, 8 sleeves", 8, 0.20),
    ("8 independent sleeves (the aspiration)", 8, 0.00),
)

#: EXPECTANCY NET OF COST, which is the only kind that pays a target.
#:
#: The account is "no commissions", which on E8 means the cost is in a WIDER SPREAD rather than
#: absent -- the raw configuration is quoted around 0.8 pips plus $5/lot round turn on EURUSD and
#: about $0.26 plus $6/lot on gold, and the commission-free option widens the quote to recover it.
#: Call it ~1.3 pips all-in on a major and ~$0.32/oz on gold, which on a 20-pip stop is a haircut
#: of roughly 0.065R per trade and on a $20 gold stop about 0.016R. SWAPS apply on anything held
#: through rollover: irrelevant to the session sleeves that close intraday, and NOT a cost at all
#: to `carry`, whose edge IS the swap -- but a real one to `overnight_gap_decay`.
#:
#: NONE OF THAT IS MEASURED ON THIS ACCOUNT and the numbers above are third-party reports of a
#: different account type. So cost is not modelled as a separate parameter pretending to a
#: precision it does not have: it is folded into `exp_r`, every table is read at the NET figure,
#: and the desk's own +0.20 is a GROSS replay number from a book whose `matched_fills` is 0. The
#: honest reading of a +0.20 gross claim on a 20-pip stop is about +0.135 net, and if the gross
#: is really +0.10 the net is +0.035. That is why the grid runs down to zero.
EXP_R_GRID = (0.30, 0.20, 0.15, 0.10, 0.05, 0.00)


def sweep(n_paths: int = 8_000) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for tname, target in TARGETS:
        for bname, sleeves, rho in BOOKS:
            for exp_r in EXP_R_GRID:
                for risk in RISK_GRID:
                    for sd in STAND_DOWN_GRID:
                        book = Book(sleeves=sleeves, rho=rho, rr=1.5,
                                    trades_per_day_per_sleeve=0.64,
                                    risk_frac=risk, exp_r=exp_r)
                        res = simulate(book, target, n_paths=n_paths, stand_down=sd)
                        rows.append({
                            "target": tname, "target_frac": target, "book": bname,
                            "sleeves": book.sleeves, "rho": book.rho, "exp_r_net": exp_r,
                            "risk_frac": risk, "risk_pct": round(risk * 100, 3),
                            "stand_down_pct": None if sd is None else round(sd * 100, 3),
                            "trades_per_day": round(book.trades_per_day, 2),
                            "win_rate": round(book.win_rate, 4),
                            **res.summary(),
                        })
    return {
        "generated_utc": datetime.now(UTC).isoformat(),
        "account": {
            "firm": "E8 Markets", "product": "E8 Pro", "balance_usd": BALANCE,
            "profit_target": TARGET, "static_drawdown": STATIC_DD,
            "daily_drawdown": DAILY_DD, "daily_profit_cap": DAILY_PROFIT_CAP,
            "platform": "TradeLocker", "commissions": "none (cost is in a wider spread)",
            "source": "purchase invoice 2026-09-12; target and cap confirmed by the principal "
                      "from the E8 dashboard the same day",
        },
        "speed_floor_days": {t: min_days(f) for t, f in TARGETS},
        "rule": (
            "the 2% daily profit cap strips excess at rollover, so target/0.02 trading days is a "
            "HARD floor on speed that no portfolio can beat, and every unit of daily variance is "
            "taxed: the right tail is confiscated and the left tail is what ends the account"),
        "cost": (
            "exp_r_net is NET of spread and swap. The account is commission-free, which on E8 "
            "means a wider quote rather than no cost; nothing here is measured on this account, "
            "so cost is folded into the expectancy rather than modelled separately"),
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--paths", type=int, default=20_000)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    doc = sweep(args.paths)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    live = [r for r in doc["rows"]
            if r["exp_r_net"] == 0.10 and r["target"] == "target_10pct"
            and r["book"].endswith("TODAY)")]
    best = max(live, key=lambda r: r["p_pass"])
    print(f"{len(doc['rows'])} cells -> {args.out}")
    print(f"speed floor: {doc['speed_floor_days']} trading days")
    print(f"best for TODAY's book at net exp_R +0.10: {best['risk_pct']}% risk, "
          f"stand-down {best['stand_down_pct']}% -> p_pass {best['p_pass']}, "
          f"median {best['days_median']}d")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
