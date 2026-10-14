"""OPTIONS-IMPLIED STATE AS A POINT-IN-TIME CONDITIONER ON THE MT5 CRYPTO CFDs.

WHAT IS CONVERTED. Until 2026-08-25 a retired organ archived the BTC and ETH option surfaces --
ATM implied vol, a call-minus-put skew proxy, the front-minus-back term slope and IV / realised --
and wrote `data/options_candidates.json`: a field whose value sat beyond |z| 1.5 of its own
archive. The candidates were never converted into anything the gauntlet could judge. They are
now: the surface vintages (recovered read-only from the committed history of
`options_state.json`, the candidates file and, where it still exists on a box, the archive
parquet) sit in `data/options_state/vintages.jsonl`, written by `research/broker_state_cells.py`,
and this family conditions BTCUSD / ETHUSD -- Fusion-executable crypto CFDs, the only instruments
it ever trades -- on that state. Crypto exchange data is used ONLY as a conditioner on an MT5
instrument; nothing here reaches a venue, and nothing here is a hunted crypto universe.

THE STATE AND ITS DIRECTION, written down before any outcome was read:

  skew        calls rich against puts (z > 0) is upside demand in the options book; puts rich
              (z < 0) is crash protection being bought. Direction = sign(z).
  atm_iv, dvol, term_slope
              no direction of their own. Cheap vol (z < 0) is a compressed market that resolves
              by expansion, so the direction is the trailing move's (continuation); rich vol
              (z > 0) has already priced the move, so the direction fades the trailing move.

`mode="follow"` trades the direction, `mode="contrarian"` its negation. Those two are the cell's
whole side search, charged once each.

POINT-IN-TIME. A vintage is knowable at its own collection stamp `ts` (UTC). Its z is computed
against PRIOR vintages only (`min_prior` of them). A candidate row's recorded z is used only when
the store marks it `z_trusted` -- and NONE of the 2026-08 candidates is: the retired archive
switched ATM IV from percent to a fraction on 2026-08-25 (37.14 -> 0.5199), so every z it
recorded that day (ETH atm_iv -7.16, "cheap -> buy") measures the unit change, not the market.
The store normalises the vintages to one unit; the candidates' z cannot be repaired. The stamp is
moved onto the bars' broker clock by `libs.regime.session_clock.utc_to_server`, and the signal
fires on the first bar opening at or after it.
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

STORE = Path(__file__).resolve().parents[1] / "data" / "options_state" / "vintages.jsonl"

#: MT5 crypto CFD -> the options currency whose surface conditions it. Nothing else is traded.
UNDERLYING = {"BTCUSD": "BTC", "ETHUSD": "ETH"}
#: `iv_rv` is NOT here: the retired organ's realised-vol leg (`rv_1w`) changed units between
#: vintages and the ratio is uninterpretable across them. `dvol` (the venue's own 30-day
#: implied-vol index) was recorded in one unit throughout.
FIELDS = ("atm_iv", "skew", "term_slope", "dvol")
MODES = ("follow", "contrarian")

_CACHE: dict[str, Any] = {}


def store_path() -> Path:
    raw = os.environ.get("QUANT_OPTIONS_STATE_STORE", "")
    return Path(raw) if raw else STORE


def _rows(path: Path) -> list[dict[str, Any]]:
    try:
        st = path.stat()
    except OSError:
        return []
    key = f"{path}|{st.st_mtime_ns}|{st.st_size}"
    if _CACHE.get("key") != key:
        rows: list[dict[str, Any]] = []
        try:
            for line in path.read_text("utf-8").splitlines():
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


def state_events(currency: str, field: str, *, z_threshold: float, min_prior: int,
                 path: Path | None = None) -> list[tuple[str, float]]:
    """(UTC stamp, z) for every vintage or candidate whose trailing z on `field` clears
    `z_threshold`, oldest first. A vintage's z uses only vintages stamped BEFORE it."""
    rows = _rows(path or store_path())
    vint = sorted(((str(r.get("ts")), float(r[field])) for r in rows
                   if r.get("kind") == "vintage" and r.get("currency") == currency
                   and isinstance(r.get(field), (int, float)) and np.isfinite(r[field])),
                  key=lambda x: x[0])
    out: dict[str, float] = {}
    seen: list[float] = []
    for ts, x in vint:
        if len(seen) >= int(min_prior):
            mu, sd = float(np.mean(seen)), float(np.std(seen, ddof=1))
            if sd > 0:
                z = (x - mu) / sd
                if abs(z) >= float(z_threshold):
                    out[ts] = z
        seen.append(x)
    for r in rows:
        if (r.get("kind") == "candidate" and r.get("z_trusted") is True
                and r.get("currency") == currency
                and r.get("field") == field and isinstance(r.get("z"), (int, float))
                and abs(float(r["z"])) >= float(z_threshold)):
            out.setdefault(str(r.get("ts")), float(r["z"]))
    return sorted(out.items())


def family_crypto_options_state(
    df: pd.DataFrame,
    *,
    symbol: str,
    field: str,
    mode: str = "follow",
    z_threshold: float = 1.5,
    min_prior: int = 5,
    hold_bars: int = 24,
    lookback_bars: int = 24,
    atr_n: int = 20,
    stop_atr: float = 2.5,
    rr: float = 1.5,
) -> list[Signal]:
    """Trade `symbol` (BTCUSD/ETHUSD only) for `hold_bars` after its underlying's `field` sits
    beyond |z| `z_threshold` of its own trailing vintages (see the module docstring for the side).
    No store, no signals."""
    from libs.regime.session_clock import utc_to_server
    cur = UNDERLYING.get(symbol)
    if cur is None or field not in FIELDS or mode not in MODES or int(hold_bars) < 1:
        return []
    events = state_events(cur, field, z_threshold=z_threshold, min_prior=min_prior)
    if not events:
        return []
    d = _h1(df)
    if len(d) < max(atr_n, lookback_bars) + 4:
        return []
    index = pd.DatetimeIndex(d.index)
    atr = _atr(d, atr_n).to_numpy()
    close = d["close"].astype(float).to_numpy()
    flip = 1 if mode == "follow" else -1
    signals: list[Signal] = []
    armed_from = -1
    for ts, z in events:
        at = utc_to_server(ts)
        if at is None:
            continue
        pos = int(index.searchsorted(at, side="left"))
        if pos <= armed_from or pos >= len(d) - 1 or pos < max(atr_n, int(lookback_bars)):
            continue
        a = float(atr[pos])
        if not np.isfinite(a) or a <= 0:
            continue
        px = float(close[pos])
        if field == "skew":
            direction = 1 if z > 0 else -1
        else:
            move = px - float(close[pos - int(lookback_bars)])
            if not np.isfinite(move) or move == 0:
                continue
            trend = 1 if move > 0 else -1
            direction = trend if z < 0 else -trend
        s = flip * direction
        signals.append(Signal(time=index[pos], side=s, stop=px - s * stop_atr * a,
                              target=px + s * stop_atr * a * rr, ttl_bars=int(hold_bars),
                              tag=f"options_state:{field}:{mode}", trigger=None, wait_bars=1))
        armed_from = pos + int(hold_bars)
    return signals
