"""The scalp lane's live plan: the replay's own rules, computed on the broker's own bars.

WHY THIS FILE EXISTS. `research/scalp_shadow.py` matures the four gold scalp sleeves on Fusion
M5/M15 bars and `research/promoter.py` can now promote them (principal, 2026-09-04: promotion
to live is automatic, never a person's act). The gateway then needs an executor that trades
EXACTLY what the forward clock replayed -- `scalp_reverse_engineering.simulate` under
`scalp_family_expansion`'s signals -- or nothing at all. Trading a lookalike under a certified
sleeve's name is the defect class the family executor documents; this module is the exact
translation, kept free of MetaTrader5 so it can be tested off the box.

THE REPLAY'S CONTRACT, restated as live rules:

    signal   `_base_signals(bars)[family]` at bar i is built from bars <= i-1 (every input is
             shifted), masked by the session of bar i; so the moment bar i-1 closes, the signal
             for bar i is known and the entry is bar i's OPEN -- the market price right now.
    stop     entry -/+ stop_atr x ATR. The replay reads ATR at bar i, which includes bar i's
             own range and is therefore unknowable at the open; live uses the last CLOSED
             bar's ATR. That is the one deliberate deviation and it is stated here rather
             than hidden: a stop the executor could not have known is not a stop.
    target   average entry +/- target_atr x ATR, recomputed as slices are added.
    slices   bounded_structural: four slices of a quarter of the risk budget each, the first at
             the signal, later ones at the open of any bar inside the hold window whose signal
             agrees and whose open is still on the right side of the stop. A lot too small to
             split falls back to the replay's `single` mode: one slice, full risk.
    exit     stop or target on the bracket, else the close of bar i + max_hold -- the TTL.
"""
from __future__ import annotations

import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

TF_MINUTES: dict[str, int] = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60}
#: Attribute names on the MetaTrader5 module, resolved by the gateway with getattr so this
#: module never imports the Windows-only package.
MT5_TIMEFRAME_ATTR: dict[str, str] = {"M1": "TIMEFRAME_M1", "M5": "TIMEFRAME_M5",
                                      "M15": "TIMEFRAME_M15", "M30": "TIMEFRAME_M30",
                                      "H1": "TIMEFRAME_H1"}
#: Bars to fetch: the signals use 50-bar windows and a 14-bar ATR; 400 leaves the warm-up far
#: behind on every timeframe the lane runs.
BARS_NEEDED = 400
MIN_BARS = 80
MAX_DEPTH = 4
SLICE_FRAC = 0.25
EXEC_KIND = "scalp_market"


@dataclass(frozen=True)
class Plan:
    """One entry the executor may place now, with every level the replay would have used."""

    side: int
    bar_time: str
    entry_ref: float
    atr: float
    stop: float
    target: float
    stop_dist: float
    ttl_until: str
    family: str
    session: str
    tf: str
    max_hold: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def frame_from_rates(rates: Any) -> pd.DataFrame:
    """Broker rates (MetaTrader5 structured array or a list of dicts) -> UTC-indexed OHLC frame."""
    df = pd.DataFrame(rates)
    if "time" not in df.columns:
        raise ValueError("rates carry no 'time' column")
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("time").sort_index()
    for col in ("open", "high", "low", "close"):
        if col not in df.columns:
            raise ValueError(f"rates carry no '{col}' column")
        df[col] = df[col].astype(float)
    if "tick_volume" not in df.columns:
        df["tick_volume"] = 0.0
    return df


def _families() -> Any:
    from desks.mt5.research import scalp_family_expansion as fam
    return fam


def _core() -> Any:
    from desks.mt5.research import scalp_reverse_engineering as core
    return core


def _with_forming_bar(closed: pd.DataFrame, price: float, forming_time: pd.Timestamp,
                      ) -> pd.DataFrame:
    """The closed bars plus a synthetic row for the bar that is opening now.

    Every signal input is shifted, so the synthetic row's OWN prices are never read by the
    signal at its index; only its timestamp is, for the session mask. It is here so the signal
    array has an index i to evaluate, exactly where the replay evaluated it.
    """
    row = pd.DataFrame({"open": [price], "high": [price], "low": [price], "close": [price],
                        "tick_volume": [0.0]}, index=pd.DatetimeIndex([forming_time], name="time"))
    keep = [c for c in ("open", "high", "low", "close", "tick_volume") if c in closed.columns]
    return pd.concat([closed[keep], row[keep]]).sort_index()


def signal_at_open(closed: pd.DataFrame, *, tf: str, family: str, session: str, price: float,
                   forming_time: pd.Timestamp | None = None) -> int:
    """The replay's signal for the bar opening now: -1, 0 or +1."""
    if tf not in TF_MINUTES:
        raise ValueError(f"unknown timeframe {tf!r}")
    if len(closed) < MIN_BARS:
        return 0
    fam = _families()
    ft = forming_time if forming_time is not None else (
        closed.index[-1] + pd.Timedelta(minutes=TF_MINUTES[tf]))
    ext = _with_forming_bar(closed, price, pd.Timestamp(ft))
    signals = fam._base_signals(ext)
    if family not in signals:
        raise KeyError(f"family {family!r} has no exact executable in scalp_family_expansion")
    sig = np.asarray(signals[family]).copy()
    sig[~fam._session_mask(ext.index, session)] = 0
    return int(sig[-1])


def last_closed_atr(closed: pd.DataFrame) -> float:
    """ATR of the last CLOSED bar -- the stop's scale the executor can actually know."""
    a = _core()._atr(closed)
    v = float(a[-1]) if len(a) else float("nan")
    return v if math.isfinite(v) else float("nan")


def ttl_deadline(forming_time: pd.Timestamp, tf: str, max_hold: int) -> str:
    """The close of bar i + max_hold, as the replay's time exit."""
    return (pd.Timestamp(forming_time) + pd.Timedelta(minutes=TF_MINUTES[tf] * (int(max_hold) + 1))
            ).isoformat()


def plan_entry(closed: pd.DataFrame, *, tf: str, family: str, session: str, stop_atr: float,
               target_atr: float, max_hold: int, bid: float, ask: float,
               forming_time: pd.Timestamp | None = None) -> Plan | None:
    """The entry the replay would take at this bar's open, or None. Never approximates."""
    if not (math.isfinite(bid) and math.isfinite(ask) and bid > 0 and ask > 0):
        return None
    ft = pd.Timestamp(forming_time) if forming_time is not None else (
        closed.index[-1] + pd.Timedelta(minutes=TF_MINUTES[tf]))
    mid = 0.5 * (bid + ask)
    side = signal_at_open(closed, tf=tf, family=family, session=session, price=mid,
                          forming_time=ft)
    if side == 0:
        return None
    atr = last_closed_atr(closed)
    if not (math.isfinite(atr) and atr > 0):
        return None
    entry_ref = ask if side == 1 else bid
    stop_dist = float(stop_atr) * atr
    stop = entry_ref - side * stop_dist
    target = entry_ref + side * float(target_atr) * atr
    if not (stop_dist > 0):
        return None
    return Plan(side=side, bar_time=ft.isoformat(), entry_ref=float(entry_ref), atr=float(atr),
                stop=float(stop), target=float(target), stop_dist=float(stop_dist),
                ttl_until=ttl_deadline(ft, tf, max_hold), family=family, session=session,
                tf=tf, max_hold=int(max_hold))


def addon_allowed(closed: pd.DataFrame, *, tf: str, family: str, session: str, side: int,
                  stop: float, depth: int, price: float,
                  forming_time: pd.Timestamp | None = None) -> bool:
    """May a further slice be added at this bar's open? The replay's own three conditions."""
    if depth >= MAX_DEPTH:
        return False
    if side * (float(price) - float(stop)) <= 0:
        return False
    return signal_at_open(closed, tf=tf, family=family, session=session, price=price,
                          forming_time=forming_time) == int(side)


def basket_target(entries: list[tuple[float, float]], side: int, target_atr: float,
                  atr: float) -> float:
    """Target from the lot-weighted average entry, as the replay recomputes it per slice."""
    total = sum(float(u) for _, u in entries)
    if total <= 0:
        raise ValueError("a basket needs positive size")
    avg = sum(float(p) * float(u) for p, u in entries) / total
    return float(avg + side * float(target_atr) * float(atr))


def slice_lot(lot: float, volume_min: float, volume_step: float) -> tuple[float, str]:
    """(lot per slice, mode). A lot that cannot be quartered trades the replay's `single` mode."""
    step = float(volume_step) if volume_step and volume_step > 0 else 0.01
    vmin = float(volume_min) if volume_min and volume_min > 0 else step
    per = math.floor((float(lot) * SLICE_FRAC) / step + 1e-9) * step
    if per + 1e-12 >= vmin:
        return round(per, 8), "bounded_structural"
    whole = math.floor(float(lot) / step + 1e-9) * step
    if whole + 1e-12 >= vmin:
        return round(whole, 8), "single"
    return 0.0, "too_small"
