"""Automated adversaries for a certificate: the placebos it must beat before it is believed.

`placebo_test.py` audits the MACHINERY once, on shuffled markets, and is explicitly never a
gate. This is per certificate, runs on every new one, and asks a narrower question: is THIS
cell's result distinguishable from the results of things that cannot have edge?

    entry_shift     the same signals, each moved +-1 bar. An edge that depends on the exact bar
                    is usually a lookahead or a bar-construction artifact
    side_flip       every side reversed. A cell whose mirror also pays is harvesting a
                    stop/target asymmetry, not a direction
    random_entry    random bars, same count, same side mix, same holding. The result an
                    idiot with this many trades would get
    label_shuffle   the signal TIMES permuted among themselves. Same times as the original --
                    it tests whether the pairing of time and side carries anything

A certificate whose R is inside the placebo distribution is not wrong; it is UNDISTINGUISHED,
which is the state the gates were supposed to rule out and which this checks independently.
The verdict is recorded with the certificate. It withdraws nothing on its own: a red-team
finding is a defect report for a human, exactly like a disagreement between replays.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import pandas as pd

N_PLACEBO = 50
#: The certificate must beat this quantile of each placebo family's mean R.
BEAT_Q = 0.95


@dataclass(frozen=True)
class RedTeam:
    real_mean_r: float
    n_trades: int
    placebos: dict[str, dict[str, float]]
    verdict: str
    why: str

    def to_dict(self) -> dict[str, Any]:
        return {"real_mean_r": round(self.real_mean_r, 6), "n_trades": self.n_trades,
                "placebos": self.placebos, "verdict": self.verdict, "why": self.why}


def _geometry(df: pd.DataFrame, signals: Sequence[Any]) -> dict[Any, tuple[float, float]]:
    """Each signal's stop and target distances in ATR units at its own bar.

    THE PLACEBO MUST BE RE-PLACED, NOT JUST RE-TIMED. The first version moved a signal's time and
    kept its absolute stop and target, so a stop set 2 ATR below a 2024 price landed at a 2026
    bar hundreds of dollars away -- or already crossed. Random entries then scored +0.75R mean
    on XAUUSD against the family's +0.12R, and the family read as worse than random when what was
    being compared was two different trades. Distances are carried in ATR units and re-anchored
    to the new bar's close and ATR, so a placebo trade has the SAME risk geometry as the real one
    and differs only in when it was taken.
    """
    c = df["close"].astype(float)
    atr = _atr_series(df)
    out: dict[Any, tuple[float, float]] = {}
    for s in signals:
        if s.time not in c.index:
            continue
        px = float(c.loc[s.time])
        a = float(atr.loc[s.time]) if s.time in atr.index else float("nan")
        if not math.isfinite(a) or a <= 0:
            continue
        out[s.time] = (abs(px - float(s.stop)) / a, abs(float(s.target) - px) / a)
    return out


def _atr_series(df: pd.DataFrame, n: int = 20) -> pd.Series:
    h, lo, c = (df[k].astype(float) for k in ("high", "low", "close"))
    tr = pd.concat([(h - lo), (h - c.shift()).abs(), (lo - c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=1).mean()


def _replace_at(df: pd.DataFrame, atr: pd.Series, s: Any, new_time: Any,
                geom: tuple[float, float], side: int | None = None) -> Any | None:
    if new_time not in df.index:
        return None
    px = float(df["close"].astype(float).loc[new_time])
    a = float(atr.loc[new_time])
    if not math.isfinite(a) or a <= 0:
        return None
    sd, td = geom
    sgn = int(side if side is not None else s.side)
    return replace(s, time=new_time, side=sgn, stop=px - sgn * sd * a, target=px + sgn * td * a)


def _shift(df: pd.DataFrame, atr: pd.Series, geom: dict[Any, tuple[float, float]],
           signals: Sequence[Any], k: int) -> list[Any]:
    index = df.index
    pos = {ts: i for i, ts in enumerate(index)}
    out = []
    for s in signals:
        i = pos.get(s.time)
        if i is None or not (0 <= i + k < len(index)) or s.time not in geom:
            continue
        r = _replace_at(df, atr, s, index[i + k], geom[s.time])
        if r is not None:
            out.append(r)
    return out


def _flip(df: pd.DataFrame, atr: pd.Series, geom: dict[Any, tuple[float, float]],
          signals: Sequence[Any]) -> list[Any]:
    out = []
    for s in signals:
        if s.time not in geom:
            continue
        r = _replace_at(df, atr, s, s.time, geom[s.time], side=-int(s.side))
        if r is not None:
            out.append(r)
    return out


def _random(df: pd.DataFrame, atr: pd.Series, geom: dict[Any, tuple[float, float]],
            signals: Sequence[Any], rng: np.random.Generator) -> list[Any]:
    sig = [s for s in signals if s.time in geom]
    if not sig:
        return []
    picks = np.sort(rng.choice(np.arange(24, len(df.index) - 24), size=len(sig), replace=False))
    out = []
    for s, i in zip(sig, picks, strict=False):
        r = _replace_at(df, atr, s, df.index[int(i)], geom[s.time])
        if r is not None:
            out.append(r)
    return out


def _shuffle_labels(df: pd.DataFrame, atr: pd.Series, geom: dict[Any, tuple[float, float]],
                    signals: Sequence[Any], rng: np.random.Generator) -> list[Any]:
    sig = [s for s in signals if s.time in geom]
    times = [s.time for s in sig]
    perm = rng.permutation(len(times))
    out = []
    for s, j in zip(sig, perm, strict=False):
        r = _replace_at(df, atr, s, times[int(j)], geom[s.time])
        if r is not None:
            out.append(r)
    return out


def run(df: pd.DataFrame, signals: Sequence[Any], score: Callable[[Sequence[Any]], float],
        n_placebo: int = N_PLACEBO, seed: int = 0) -> RedTeam:
    """`score(signals) -> mean R` is the production replay, injected so this never
    re-implements it."""
    sig = list(signals)
    if len(sig) < 20:
        return RedTeam(float("nan"), len(sig), {}, "UNJUDGED", "fewer than 20 signals")
    rng = np.random.default_rng(seed)
    real = float(score(sig))
    atr = _atr_series(df)
    geom = _geometry(df, sig)
    if len(geom) < 20:
        return RedTeam(real, len(sig), {}, "UNJUDGED", "signal geometry could not be recovered")
    fams: dict[str, list[float]] = {"entry_shift": [], "side_flip": [], "random_entry": [],
                                    "label_shuffle": []}
    for k in (-1, 1):
        fams["entry_shift"].append(float(score(_shift(df, atr, geom, sig, k))))
    fams["side_flip"].append(float(score(_flip(df, atr, geom, sig))))
    # LABEL SHUFFLE IS DEGENERATE WHEN EVERY SIDE IS THE SAME. Permuting times among signals
    # that all say "long" reassigns each long to another long's bar -- the same set of trades in
    # a different order -- and the placebo scores exactly the real result. It tests whether the
    # pairing of time and side carries anything, so it needs sides to differ.
    sides = {int(s.side) for s in sig}
    for _ in range(n_placebo):
        fams["random_entry"].append(float(score(_random(df, atr, geom, sig, rng))))
        if len(sides) > 1:
            fams["label_shuffle"].append(float(score(_shuffle_labels(df, atr, geom, sig, rng))))
    if len(sides) <= 1:
        fams.pop("label_shuffle", None)

    summary: dict[str, dict[str, float]] = {}
    beaten = []
    for name, vals in fams.items():
        arr = np.asarray([v for v in vals if math.isfinite(v)], dtype=float)
        if arr.size == 0:
            continue
        q = float(np.quantile(arr, BEAT_Q)) if arr.size >= 5 else float(arr.max())
        summary[name] = {"n": int(arr.size), "mean": round(float(arr.mean()), 6),
                         f"q{int(BEAT_Q * 100)}": round(q, 6), "beaten": bool(real > q)}
        beaten.append(real > q)
    if not summary:
        return RedTeam(real, len(sig), {}, "UNJUDGED", "no placebo could be scored")
    lost = [k for k, v in summary.items() if not v["beaten"]]
    if not lost:
        return RedTeam(real, len(sig), summary, "DISTINGUISHED",
                       "beats every placebo family's 95th percentile")
    return RedTeam(real, len(sig), summary, "UNDISTINGUISHED",
                   f"does not beat {', '.join(lost)}; the result is inside what no-edge "
                   "constructions produce")
