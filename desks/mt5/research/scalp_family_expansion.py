"""Search genuinely different XAUUSD scalp mechanisms after screenshot-basket rejection.

This is a bounded second experiment, not a wider parameter fishing expedition.  Seven fixed
families and their explicitly labelled anti-signals are crossed with four economically meaningful
sessions and four exit geometries.  The
first 60% selects one specification per family; the final 40% is untouched until that choice is
frozen.  Both full-risk single entry and four-slice structural baskets are then reported OOS.
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from desks.mt5.research import scalp_reverse_engineering as core  # noqa: E402

DATA = Path(__file__).parents[1] / "data" / "universe"
OUT = Path(__file__).parents[1] / "reports" / "scalp_family_expansion.json"
VERSION = "gold-scalp-expansion-2026-08-22-a"


@dataclass(frozen=True)
class Choice:
    family: str
    session: str
    stop_atr: float
    target_atr: float
    max_hold: int


def _session_mask(index: pd.DatetimeIndex, session: str) -> np.ndarray:
    if session == "all":
        return np.ones(len(index), dtype=bool)
    utc = index.tz_convert("UTC")
    if session == "london":
        local = index.tz_convert("Europe/London")
        minutes = local.hour * 60 + local.minute
        return np.asarray((minutes >= 8 * 60) & (minutes < 12 * 60))
    if session == "new_york":
        local = index.tz_convert("America/New_York")
        minutes = local.hour * 60 + local.minute
        return np.asarray((minutes >= 9 * 60 + 30) & (minutes < 13 * 60))
    # The liquid London/New-York overlap, expressed in UTC and therefore not silently tied to
    # either country's DST transition week.
    minutes = utc.hour * 60 + utc.minute
    return np.asarray((minutes >= 13 * 60) & (minutes < 16 * 60))


def _base_signals(df: pd.DataFrame) -> dict[str, np.ndarray]:
    close, opn, high, low = (df[c].astype(float) for c in ("close", "open", "high", "low"))
    pc, po, ph, pl = close.shift(), opn.shift(), high.shift(), low.shift()
    atr = pd.Series(core._atr(df), index=df.index)
    out: dict[str, np.ndarray] = {}

    fast, slow = close.ewm(span=12, adjust=False).mean(), close.ewm(span=48, adjust=False).mean()
    ema = np.zeros(len(df), dtype=np.int8)
    ema[(fast.shift() > slow.shift()) & (pl <= fast.shift()) & (pc > fast.shift()) & (pc > po)] = 1
    ema[(fast.shift() < slow.shift()) & (ph >= fast.shift()) & (pc < fast.shift()) & (pc < po)] = -1
    out["ema_pullback"] = ema

    prior_hi = high.shift(2).rolling(20).max()
    prior_lo = low.shift(2).rolling(20).min()
    brk = np.zeros(len(df), dtype=np.int8)
    brk[(pc > prior_hi) & (close.shift(2) <= prior_hi)] = 1
    brk[(pc < prior_lo) & (close.shift(2) >= prior_lo)] = -1
    out["donchian_breakout"] = brk

    body = (pc - po).abs().clip(lower=0.01)
    rng = (ph - pl).clip(lower=0.01)
    wick = np.zeros(len(df), dtype=np.int8)
    wick[((po.where(po > pc, pc) - pl) > 2.5 * body) & ((pc - pl) / rng > 0.70)] = 1
    wick[((ph - po.where(po < pc, pc)) > 2.5 * body) & ((ph - pc) / rng > 0.70)] = -1
    out["wick_exhaustion"] = wick

    short_atr = atr.rolling(5).mean()
    long_atr = atr.rolling(50).mean()
    compressed = short_atr.shift(2) < 0.70 * long_atr.shift(2)
    comp = np.zeros(len(df), dtype=np.int8)
    comp[compressed & (pc > prior_hi)] = 1
    comp[compressed & (pc < prior_lo)] = -1
    out["compression_breakout"] = comp

    ret3 = pc - close.shift(4)
    momentum = np.zeros(len(df), dtype=np.int8)
    momentum[(ret3 > 1.25 * atr.shift()) & (pc > po)] = 1
    momentum[(ret3 < -1.25 * atr.shift()) & (pc < po)] = -1
    out["three_bar_momentum"] = momentum

    volume = df.get("tick_volume", df.get("volume", pd.Series(1.0, index=df.index))).astype(float)
    vwap = (close * volume).rolling(50).sum() / volume.rolling(50).sum().replace(0, np.nan)
    scale = close.rolling(50).std().replace(0, np.nan)
    z = (pc - vwap.shift()) / scale.shift()
    revert = np.zeros(len(df), dtype=np.int8)
    revert[(z < -2.0) & (pc > po)] = 1
    revert[(z > 2.0) & (pc < po)] = -1
    out["vwap_exhaustion"] = revert

    # London opening-range break. The range is known in full before the first permitted signal.
    london = df.copy()
    london.index = london.index.tz_convert("Europe/London")
    mins = london.index.hour * 60 + london.index.minute
    opening = london[(mins >= 8 * 60) & (mins < 8 * 60 + 30)]
    keys = pd.Series(london.index.date, index=df.index)
    ranges = opening.groupby(opening.index.date).agg(or_high=("high", "max"), or_low=("low", "min"))
    or_hi = keys.map(ranges.or_high).astype(float)
    or_lo = keys.map(ranges.or_low).astype(float)
    after = (mins >= 8 * 60 + 30) & (mins < 11 * 60)
    opening_sig = np.zeros(len(df), dtype=np.int8)
    opening_sig[after & (pc > or_hi) & (close.shift(2) <= or_hi)] = 1
    opening_sig[after & (pc < or_lo) & (close.shift(2) >= or_lo)] = -1
    out["london_opening_range"] = opening_sig
    # Failure itself is information: public-pattern traders can be the liquidity. These reversed
    # mechanisms are labelled rather than silently flipping a losing backtest. Because the
    # inversion was motivated after the screenshot family failed, a statistical hit is only an
    # exploratory shadow candidate and never capital authority.
    for name, signal in list(out.items()):
        out[f"anti_{name}"] = -signal
    return out


def _geometry(tf: str) -> tuple[tuple[float, float, int], ...]:
    medium, long = {"M1": (10, 15), "M5": (6, 9), "M15": (4, 6)}[tf]
    return ((1.0, 1.0, medium), (1.0, 1.5, long))


def _cfg(choice: Choice, mode: str) -> core.Config:
    return core.Config(choice.family, 20, 1.5, choice.stop_atr, choice.target_atr,
                       choice.max_hold, mode)


def run() -> dict:
    report: dict = {
        "version": VERSION,
        "design": "7 labelled anti-signals x 4 sessions x 2 preregistered exit geometries",
        "prior_base_family_verdict": (
            "All seven ordinary-direction families rejected on the 90k-bar rerun; this artifact "
            "tests the economically distinct anti-crowd hypothesis."
        ),
        "selection": "first 60%; untouched last 40%",
        "cost": "recorded broker spread plus Fusion Zero $4.50/lot round turn",
        "timeframes": {}, "shadow_candidates": [],
    }
    for tf in ("M1", "M5", "M15"):
        path = DATA / f"XAUUSD_{tf}.parquet"
        if not path.exists():
            report["timeframes"][tf] = {"status": "UNMEASURED", "reason": "missing bars"}
            continue
        df = pd.read_parquet(path).sort_index()
        cut = int(len(df) * 0.60)
        train, test = df.iloc[:cut], df.iloc[cut:]
        train_signals = {
            k: v for k, v in _base_signals(train).items() if k.startswith("anti_")
        }
        test_signals = {
            k: v for k, v in _base_signals(test).items() if k.startswith("anti_")
        }
        selected: list[dict] = []
        for family in train_signals:
            ranked: list[tuple[float, Choice]] = []
            for session in ("all", "london", "new_york", "overlap"):
                sig = train_signals[family].copy()
                sig[~_session_mask(train.index, session)] = 0
                for stop, target, hold in _geometry(tf):
                    choice = Choice(family, session, stop, target, hold)
                    rs = core.simulate(train, _cfg(choice, "single"), signal_override=sig)
                    ranked.append((float(rs.mean()) if len(rs) else -math.inf, choice))
            train_mean, winner = max(ranked, key=lambda item: item[0])
            oos_sig = test_signals[family].copy()
            oos_sig[~_session_mask(test.index, winner.session)] = 0
            arms = {}
            for mode in ("single", "bounded_structural"):
                cfg = _cfg(winner, mode)
                costed = core.simulate(test, cfg, signal_override=oos_sig)
                frictionless = core.simulate(
                    test, cfg, cost="frictionless", signal_override=oos_sig,
                )
                stats = core._stats(costed)
                oos_gate = bool(stats["n"] >= 30 and stats["psr"] >= 0.95)
                train_stats = None
                thirds = None
                if oos_gate:
                    train_sig = train_signals[family].copy()
                    train_sig[~_session_mask(train.index, winner.session)] = 0
                    train_mode = core.simulate(train, cfg, signal_override=train_sig)
                    train_stats = core._stats(train_mode)
                    thirds = []
                    for third in range(3):
                        chunk = df.iloc[third * len(df) // 3:(third + 1) * len(df) // 3]
                        chunk_sig = _base_signals(chunk)[family]
                        chunk_sig[~_session_mask(chunk.index, winner.session)] = 0
                        thirds.append(core._stats(core.simulate(
                            chunk, cfg, signal_override=chunk_sig,
                        )))
                # A post-failure anti-signal must work on BOTH chronological sides. Letting a
                # negative discovery half through because only the final half is good would turn
                # inversion into an unconstrained sign-selection trick.
                stable = bool(train_stats and train_stats["n"] >= 30 and
                              train_stats["mean_r"] > 0 and thirds and
                              all(row["mean_r"] > 0 for row in thirds))
                gate = bool(oos_gate and stable)
                arms[mode] = {
                    "train": train_stats, "costed": stats,
                    "frictionless": core._stats(frictionless),
                    "original_gate": oos_gate,
                    "chronological_stability": stable,
                    "chronological_thirds": thirds,
                    "disposition": ("EXPLORATORY_SHADOW_CANDIDATE" if gate and
                                    family.startswith("anti_") else
                                    ("SHADOW_CANDIDATE" if gate else "REJECT")),
                }
                if gate:
                    report["shadow_candidates"].append(
                        {"timeframe": tf, "choice": asdict(winner), "mode": mode, **arms[mode]},
                    )
            selected.append({
                "choice": asdict(winner), "train_mean_r": round(train_mean, 5), "arms": arms,
            })
        report["timeframes"][tf] = {
            "status": "MEASURED", "bars": len(df), "families": len(train_signals),
            "train_trials": len(train_signals) * 8, "selected": selected,
        }
    report["verdict"] = ("SHADOW_CANDIDATES" if report["shadow_candidates"] else
                         "REJECTED: no alternative scalp cleared the original OOS gate")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), "utf-8")
    return report


def main() -> int:
    report = run()
    print(report["verdict"])
    print(f"shadow candidates: {len(report['shadow_candidates'])}")
    for tf, result in report["timeframes"].items():
        for row in result.get("selected", []):
            choice, arm = row["choice"], row["arms"]["single"]
            print(tf, choice["family"], choice["session"], arm["costed"], arm["disposition"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
