"""BROKER-STATE EVENTS -- the venue's own published changes to what it costs to hold a symbol.

N7 (2026-10-14). `mt5desk/tape.py` has recorded `margin_initial`, `margin_maintenance`,
`trade_mode` and the two swap fields for every symbol, every hour, point-in-time, since the
contract-terms tape began -- and nothing read them. Each is a dated, published-by-behaviour
instruction to every holder of the symbol:

  margin_hike / margin_cut   the broker raises (or lowers) the capital a lot ties up. A hike is
                             announced deleveraging in a named symbol inside a dated window: the
                             marginal holder (`axis_registry`: forced_liquidation, payer
                             `margin_called_trader`) must cut size or post cash, and the cut is a
                             flow, not information. A cut permits re-expansion.
  closeonly_on / _off        `trade_mode` flips to 3 (CLOSEONLY): every holder may only exit.
                             The revert reopens the symbol to new risk.
  swap_change                the overnight financing differential (long minus short) moved: a
                             carry desk reads that as a rate-expectation shift and reallocates
                             (`carry_rollover`, payer `negative_carry_holder`). GAP_MAP row 52.
  swap_sign_flip             a financed side changed sign -- the held side went from paid to
                             charged or back, the sharpest form of the same shift.
  carry_rank_change          the symbol moved tercile in its asset class's carry ranking (annual
                             percent of notional, from `research/carry_state.money_per_lot_night`).

TWO MODES, NO SIGN SEARCHED BEYOND THEM. `drift` follows the event's direction (for a margin or
trade-mode event, which carries none, the direction of the trailing move into the event: forced
flow continues it); `reversal` fades it (the forced flow was liquidity, not information). Each is
one cell; nothing else about the side is tuned.

POINT-IN-TIME BY CONSTRUCTION. Events come from `research/broker_state_cells.py`'s store, where
each is stamped `knowable_at` = the `observed_at` of the FIRST hourly record that showed the new
value (the change happened at some instant since the previous record; the desk learned it then,
never earlier). That UTC instant is moved onto the bars' broker clock by
`libs.regime.session_clock.utc_to_server` (New York + 7h, DST included) and the signal fires on the
first bar OPENING at or after it, entering at the next open. A stamp that cannot be converted is
dropped, never used raw.

`symbol` AND `event` ARE REQUIRED KEYWORD ARGUMENTS: which rows of the store belong to which cell
is the organ's evidence, not a searched parameter (`orthogonal_sweep._unsuppliable` names them).
No store, no signals -- never a price-only fallback wearing the name.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.engine import Signal
from mt5desk.families import _atr, _h1

#: Written by `research/broker_state_cells.py` every pass, from the contract-terms tape and the
#: broker swap panel. An environment override exists for tests and for a box with a moved tree.
STORE = Path(__file__).resolve().parents[1] / "data" / "broker_state" / "events.jsonl"

MARGIN_EVENTS = ("margin_hike", "margin_cut", "closeonly_on", "closeonly_off")
SWAP_EVENTS = ("swap_change", "swap_sign_flip", "carry_rank_change")
MODES = ("drift", "reversal")

_CACHE: dict[str, Any] = {}


def store_path() -> Path:
    raw = os.environ.get("QUANT_BROKER_STATE_STORE", "")
    return Path(raw) if raw else STORE


def _rows(path: Path) -> list[dict[str, Any]]:
    """The store's rows, cached on (path, mtime, size) so a sweep of cells reads it once."""
    try:
        st = path.stat()
    except OSError:
        return []
    key = f"{path}|{st.st_mtime_ns}|{st.st_size}"
    if _CACHE.get("key") != key:
        rows: list[dict[str, Any]] = []
        try:
            for line in path.read_text("utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    rows.append(r)
        except OSError:
            rows = []
        _CACHE["key"], _CACHE["rows"] = key, rows
    got = _CACHE.get("rows")
    return got if isinstance(got, list) else []


def event_times(symbol: str, event: str, *,
                path: Path | None = None) -> list[tuple[pd.Timestamp, int]]:
    """(knowable instant on the BARS' broker clock, event direction) for `symbol`'s `event` rows,
    oldest first. Direction is +1/-1 where the event carries one, 0 where it does not."""
    from libs.regime.session_clock import utc_to_server
    out: list[tuple[pd.Timestamp, int]] = []
    for r in _rows(path or store_path()):
        if r.get("symbol") != symbol or r.get("kind") != event:
            continue
        moved = utc_to_server(r.get("knowable_at"))
        if moved is None:
            continue                       # an unplaceable stamp is dropped, never used raw
        try:
            direction = int(r.get("direction") or 0)
        except (TypeError, ValueError):
            direction = 0
        out.append((moved, int(np.sign(direction))))
    out.sort(key=lambda x: x[0])
    return out


def replay(df: pd.DataFrame, events: list[tuple[pd.Timestamp, int]], *, mode: str,
           hold_bars: int, lookback_bars: int, atr_n: int, stop_atr: float, rr: float,
           tag: str) -> list[Signal]:
    """Signals at the first bar opening at/after each event, one position per hold.

    The side is the event's direction (or, for a directionless event, the sign of the trailing
    `lookback_bars` move ending on the signal bar), times +1 for `drift` and -1 for `reversal`.
    Everything the side reads is at or before the signal bar's close; the engine enters at the
    next open (`trigger=None`).
    """
    if not events or mode not in MODES or int(hold_bars) < 1 or int(lookback_bars) < 1:
        return []
    d = _h1(df)
    if len(d) < max(atr_n, lookback_bars) + 4:
        return []
    index = pd.DatetimeIndex(d.index)
    atr = _atr(d, atr_n).to_numpy()
    close = d["close"].astype(float).to_numpy()
    sign = 1 if mode == "drift" else -1
    signals: list[Signal] = []
    armed_from = -1
    for ts, direction in events:
        pos = int(index.searchsorted(ts, side="left"))      # first bar OPENING at/after it
        if pos <= armed_from or pos >= len(d) - 1 or pos < max(atr_n, lookback_bars):
            continue
        a = float(atr[pos])
        if not np.isfinite(a) or a <= 0:
            continue
        px = float(close[pos])
        dirn = int(direction)
        if dirn == 0:
            move = px - float(close[pos - int(lookback_bars)])
            if not np.isfinite(move) or move == 0:
                continue
            dirn = 1 if move > 0 else -1
        s = sign * dirn
        signals.append(Signal(time=index[pos], side=s, stop=px - s * stop_atr * a,
                              target=px + s * stop_atr * a * rr, ttl_bars=int(hold_bars),
                              tag=tag, trigger=None, wait_bars=1))
        armed_from = pos + int(hold_bars)
    return signals


def family_broker_margin_event(
    df: pd.DataFrame,
    *,
    symbol: str,
    event: str,
    mode: str = "drift",
    hold_bars: int = 6,
    lookback_bars: int = 24,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
) -> list[Signal]:
    """Drift (follow the move into it) or reversal (fade it) for `hold_bars` after a margin hike
    or cut, or a CLOSEONLY flip or its revert, on `symbol`. No store row, no signal."""
    if event not in MARGIN_EVENTS:
        return []
    return replay(df, event_times(symbol, event), mode=mode, hold_bars=hold_bars,
                  lookback_bars=lookback_bars, atr_n=atr_n, stop_atr=stop_atr, rr=rr,
                  tag=f"broker_margin:{event}:{mode}")


def family_carry_swap_drift(
    df: pd.DataFrame,
    *,
    symbol: str,
    event: str,
    mode: str = "drift",
    hold_bars: int = 24,
    lookback_bars: int = 24,
    atr_n: int = 20,
    stop_atr: float = 2.5,
    rr: float = 1.5,
) -> list[Signal]:
    """Follow (`drift`) or fade (`reversal`) the direction of a swap-differential change, a swap
    sign flip or a carry-rank change on `symbol` for `hold_bars`. No store row, no signal."""
    if event not in SWAP_EVENTS:
        return []
    return replay(df, event_times(symbol, event), mode=mode, hold_bars=hold_bars,
                  lookback_bars=lookback_bars, atr_n=atr_n, stop_atr=stop_atr, rr=rr,
                  tag=f"carry_swap_drift:{event}:{mode}")
