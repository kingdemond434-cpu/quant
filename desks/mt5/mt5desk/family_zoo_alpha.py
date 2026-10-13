"""THE ALPHA ZOO AS CLASS BOOKS: 317 published formulaic alphas ranked within an MT5 peer class.

Source: HKUDS/Vibe-Trading `agent/src/factors` (MIT, Copyright 2026 HKUDS contributors),
vendored verbatim under `mt5desk/alpha_zoo/` with only the import root rewritten. It bundles the
Microsoft Qlib Alpha158 definitions (Apache-2.0, NOTICE kept), Guotai Junan's 191 short-period
alphas (国泰君安 2017, formulas), Kakushadze's 101 Formulaic Alphas (2015, formulas), and 12
academic factors. See `alpha_zoo/NOTICE_Vibe-Trading` and each zoo's LICENSE.md.

WHAT THE DESK HAD. `libs/research/adapters/alpha101.py` evaluates six Alpha101 formulas as parent
genomes, and `search_populations` carries four GTJA-style composite shapes. None of the 191 GTJA
alphas, the 158 Qlib features or the other 95 Alpha101 formulas could be run as written.

HOW A CROSS-SECTIONAL EQUITY ALPHA BECOMES AN MT5 CELL. Every zoo alpha is a score on a WIDE panel
(date x instrument) that is meant to be RANKED across instruments on each date. The desk's peer
classes (`universe_policy.peer_class`: fx_usd, metals, indices, energy, equity, ...) are exactly
such cross-sections, so the alpha is computed on the class's DAILY OHLCV panel, ranked on each day,
and the cell is one member's LEG: long while it ranks in the top `quantile`, short while it ranks
in the bottom (times `direction`, because whether a published alpha's sign survives the move from
A-shares to FX is the claim under test, not a convention). USD-quoted fx_usd members are inverted
first, so every member reads as a currency's dollar value, as in `families_cross_sectional`.

NO LOOKAHEAD, BY CONSTRUCTION. Day t's panel is built from each member's H1 bars stamped on UTC
date t. The zoo's own operators forbid negative shifts. Day t's rank is acted on at this symbol's
FIRST bar of a later date, so every member's day-t bars already existed. A member with no bars on
day t is NaN on day t (never carried forward), and a day with fewer than `min_members` scored
members has no cross-section. `volume` is the broker's tick volume and `vwap` is the typical
price (O+H+L+C)/4, which is the zoo's own rule for every market without a traded-value column.
"""
from __future__ import annotations

import ast
import importlib
from collections import OrderedDict
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1

HERE = Path(__file__).resolve().parent
ZOO_DIR = HERE / "alpha_zoo"
ZOOS: tuple[str, ...] = ("gtja191", "qlib158", "alpha101", "academic")
#: The columns an MT5 bar store can supply. An alpha that needs anything else (turnover, sector,
#: fundamentals, a traded-value `amount`) is not offered, rather than approximated.
SUPPLIED = frozenset({"open", "high", "low", "close", "volume", "vwap"})
MIN_MEMBERS = 5
MIN_DAYS = 300
_PANEL_CACHE: OrderedDict[tuple[str, tuple[tuple[str, int], ...]], dict[str, pd.DataFrame]] = (
    OrderedDict())
_PANEL_CACHE_MAX = 16


@lru_cache(maxsize=1)
def catalogue() -> dict[str, dict[str, Any]]:
    """alpha_id -> its `__alpha_meta__`, read by AST (no import) for every alpha an MT5 bar store
    can feed: daily, no sector, no extras, columns within SUPPLIED."""
    out: dict[str, dict[str, Any]] = {}
    for zoo in ZOOS:
        for f in sorted((ZOO_DIR / zoo).glob("*.py")):
            if f.name == "__init__.py":
                continue
            try:
                tree = ast.parse(f.read_text("utf-8"))
            except (OSError, SyntaxError):
                continue
            for node in tree.body:
                if isinstance(node, ast.Assign) and any(
                        getattr(t, "id", "") == "__alpha_meta__" for t in node.targets):
                    try:
                        meta = dict(ast.literal_eval(node.value))
                    except ValueError:
                        break
                    cols = set(meta.get("columns_required") or [])
                    freq = {str(x).lower() for x in meta.get("frequency") or ["1d"]}
                    if (cols <= SUPPLIED and not meta.get("extras_required")
                            and not meta.get("requires_sector") and "1d" in freq):
                        out[f"{zoo}.{f.stem}"] = {**meta, "zoo": zoo, "module": f.stem}
                    break
    return out


def compute(alpha_id: str, panel: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
    meta = catalogue().get(alpha_id)
    if meta is None:
        return None
    mod = importlib.import_module(f"mt5desk.alpha_zoo.{meta['zoo']}.{meta['module']}")
    out = mod.compute(panel)
    return out.replace([np.inf, -np.inf], np.nan) if isinstance(out, pd.DataFrame) else None


def _xs() -> Any:
    from mt5desk import families_cross_sectional as fcs
    return fcs


def _member_daily(symbol: str, orient: int) -> pd.DataFrame | None:
    fcs = _xs()
    try:
        f = pd.read_parquet(fcs.UNIVERSE_DIR / f"{symbol}_H1.parquet")
    except Exception:
        return None
    if "time" in f.columns:
        f = f.set_index("time")
    idx = pd.to_datetime(f.index, utc=True)
    f = f.set_axis(idx)
    need = {"open", "high", "low", "close"}
    if not need <= set(f.columns) or len(f) == 0:
        return None
    o, h, lo, c = (f[k].astype(float) for k in ("open", "high", "low", "close"))
    if orient < 0:
        o, h, lo, c = 1 / o, 1 / lo, 1 / h, 1 / c
    vol = f["tick_volume"].astype(float) if "tick_volume" in f.columns else \
        pd.Series(np.nan, index=f.index)
    day = idx.normalize()
    g = pd.DataFrame({"open": o, "high": h, "low": lo, "close": c, "volume": vol}).groupby(day)
    return pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(),
                         "low": g["low"].min(), "close": g["close"].last(),
                         "volume": g["volume"].sum(min_count=1)})


def class_panel(symbol: str) -> tuple[dict[str, pd.DataFrame], str, int] | None:
    """(wide daily OHLCV panel of `symbol`'s peer class, the class, `symbol`'s orientation)."""
    fcs = _xs()
    klass = fcs.class_of(symbol)
    if not klass:
        return None
    members = sorted(set(fcs.class_symbols(klass)) | {symbol})
    stamp = []
    for m in members:
        try:
            stamp.append((m, (fcs.UNIVERSE_DIR / f"{m}_H1.parquet").stat().st_mtime_ns))
        except OSError:
            continue
    key = (klass, tuple(stamp))
    hit = _PANEL_CACHE.get(key)
    if hit is None:
        frames = {m: _member_daily(m, fcs.orientation(m, klass)) for m, _ in stamp}
        frames = {m: f for m, f in frames.items() if f is not None and len(f)}
        if len(frames) < MIN_MEMBERS or symbol not in frames:
            return None
        hit = {k: pd.DataFrame({m: f[k] for m, f in frames.items()}).sort_index()
               for k in ("open", "high", "low", "close", "volume")}
        hit["vwap"] = (hit["open"] + hit["high"] + hit["low"] + hit["close"]) / 4.0
        _PANEL_CACHE[key] = hit
        while len(_PANEL_CACHE) > _PANEL_CACHE_MAX:
            _PANEL_CACHE.popitem(last=False)
    else:
        _PANEL_CACHE.move_to_end(key)
    return hit, klass, fcs.orientation(symbol, klass)


def leg_sides(score: pd.DataFrame, symbol: str, *, quantile: float, min_members: int
              ) -> pd.Series:
    """+1 on days `symbol` ranks in the top `quantile` of the scored members, -1 in the bottom."""
    n = score.notna().sum(axis=1)
    pct = score.rank(axis=1, pct=True)
    own = pct[symbol] if symbol in pct.columns else pd.Series(np.nan, index=score.index)
    side = np.where(own >= 1 - quantile, 1, np.where(own <= quantile, -1, 0))
    side = np.where((n >= min_members) & own.notna(), side, 0)
    return pd.Series(side, index=score.index)


def family_zoo_alpha_class(df: pd.DataFrame, *, symbol: str = "", alpha_id: str = "",
                           direction: int = 1, hold_d: int = 5, quantile: float = 1 / 3,
                           min_members: int = MIN_MEMBERS, atr_n: int = 20,
                           stop_atr: float = 2.5, rr: float = 2.0) -> list[Signal]:
    """`symbol`'s leg of a zoo alpha's class book: enter on its first bar of the next date when
    its day-t rank is extreme, re-entering only after `hold_d` days or a change of side."""
    if (direction not in (1, -1) or not 0 < quantile <= 0.5 or hold_d < 1
            or not symbol or alpha_id not in catalogue()):
        return []
    got = class_panel(symbol)
    if got is None:
        return []
    panel, klass, orient = got
    if len(panel["close"]) < MIN_DAYS:
        return []
    try:
        score = compute(alpha_id, panel)
    except Exception:
        return []
    if score is None or symbol not in score.columns:
        return []
    sides = leg_sides(score, symbol, quantile=quantile, min_members=min_members)
    sides = sides * int(direction) * int(orient)
    d = _h1(df)
    day = d.index.normalize()
    first = np.flatnonzero(np.r_[True, day[1:] != day[:-1]])
    atr = _atr(d, atr_n).to_numpy()
    bpd = max(1, round(len(d) / max(1, len(first))))
    by_day = sides.to_dict()
    out: list[Signal] = []
    prev_days = sides.index
    last_side, last_k = 0, -10**9
    for k, i in enumerate(first):
        pos = prev_days.searchsorted(day[i]) - 1         # the latest scored date BEFORE today
        if pos < 0:
            continue
        s = int(by_day.get(prev_days[pos], 0))
        if s == 0:
            last_side = 0
            continue
        if s == last_side and k - last_k < hold_d:
            continue
        a, px = float(atr[i]), float(d["close"].iloc[i])
        if not (np.isfinite(a) and a > 0 and px > 0):
            continue
        out.append(Signal(time=d.index[i], side=s, stop=px - s * stop_atr * a,
                          target=px + s * stop_atr * a * rr, ttl_bars=int(hold_d * bpd),
                          tag=f"zoo:{alpha_id}:{klass}"))
        last_side, last_k = s, k
    return out


ZOO_FAMILIES: dict[str, Callable[..., list[Signal]]] = {"zoo_alpha_class": family_zoo_alpha_class}

#: Culture by zoo: GTJA191 is a Chinese broker's short-horizon A-share research; Qlib158 is
#: Microsoft Research Asia's A-share feature set; Alpha101 is WorldQuant's US book.
ZOO_CULTURE: dict[str, dict[str, str]] = {
    "gtja191": {"source_culture": "CN/zh", "participant_structure": "retail_heavy",
                "crowding_prior": "medium",
                "failure_mode_hypothesis": "an A-share retail-flow pattern that does not transfer "
                                           "to a dealer-quoted FX or CFD cross-section"},
    "qlib158": {"source_culture": "CN/zh", "participant_structure": "mixed",
                "crowding_prior": "high",
                "failure_mode_hypothesis": "a feature set built for ML stacking, weak alone"},
    "alpha101": {"source_culture": "US/en", "participant_structure": "institutional",
                 "crowding_prior": "high",
                 "failure_mode_hypothesis": "published 2015 and arbitraged in its home market"},
    "academic": {"source_culture": "US/en", "participant_structure": "institutional",
                 "crowding_prior": "high",
                 "failure_mode_hypothesis": "an equity anomaly with no FX or commodity analogue"},
}
