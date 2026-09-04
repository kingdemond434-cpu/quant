"""One instrument's regime, on one clock, with its age and where it is going.

WHY PER ASSET. `pf_allocator.regime_state` fits XAUUSD daily closes and lets that stand for the
whole book. That was right when the book was gold and is wrong now: EURUSD can be trending while
gold ranges, AUDJPY can be in a carry unwind while gold says nothing, and a sleeve on GBPUSD
scored against gold's regime is scored against a state it does not live in.

WHY THE FACTORS ARE JUST ASSETS. The causal drivers this desk cares about -- the dollar, real
rates, risk appetite, the metals bid, energy, global growth -- are all TRADEABLE INSTRUMENTS on
the Fusion offering, and `economic_drivers.ROLES` already names which one plays each role. So a
"factor regime" here is the regime of the instrument that defines the factor: USD state is USDX's
state, rates state is UST10Y's. No second vocabulary, no synthesised index, and the state is
about something the desk can actually hold.

WHY FITS ARE CACHED AND WINDOWED, WHICH IS NOT AN OPTIMISATION. Measured on this host, a
`RegimeEngine` fit costs ~8.5ms per observation: 17s for 2,000 daily bars, and the full 35,451-bar
XAUUSD H1 history would be minutes. The allocator's fast clock is five minutes. A state vector
built inline would either be stale, wrong, or would eat the clock it is supposed to inform. So:

  * WINDOWED. Each timescale fits a bounded number of its most recent bars. This is also the
    better estimate -- a regime vocabulary learned from 2018 does not describe today's market,
    and the extra history buys precision about states that no longer exist.
  * CACHED BY THE BAR IT WAS FIT ON. A daily regime cannot change within a day, so a daily fit is
    computed once per day and read thereafter. The cache key is the LAST BAR'S TIMESTAMP plus the
    window, so a refreshed parquet invalidates it and a re-run inside the same bar does not.

FAILS CLOSED AND BY NAME. Too little history, a degenerate series, an engine that will not
converge -- each returns None with a reason the caller records. A state vector with a hole in it
is a fact about what the desk knows; a state vector with a guessed entry is a lie about it.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

#: Bars each clock fits on, and the forward horizons it reports, IN BARS OF THAT CLOCK. The
#: horizons are chosen so each clock answers over its own natural holding period: a day and a week
#: for the daily state, a session and a day for H4, an hour to a day for H1.
CLOCKS: dict[str, dict[str, Any]] = {
    "weekly": {"rule": "W", "max_obs": 600, "horizons": (1, 4, 13), "min_obs": 120},
    "daily": {"rule": None, "max_obs": 2000, "horizons": (1, 2, 5, 21), "min_obs": 250},
    "H4": {"rule": "4h", "max_obs": 3000, "horizons": (1, 6, 30), "min_obs": 400},
    "H1": {"rule": "1h", "max_obs": 3000, "horizons": (1, 4, 24), "min_obs": 500},
    # THE INTRADAY TIERS EXIST AND ARE MOSTLY DATA-BLOCKED, WHICH IS A FACT ABOUT THE PARQUETS
    # AND NOT ABOUT THIS TABLE. `_series` resamples from whatever bars it is given, so an M15
    # tier built from H1 bars would be H1 bars wearing a finer label -- `fit_asset_state` refuses
    # rather than upsampling, because a state vector that reports a 15-minute regime derived from
    # hourly closes is worse than one that reports a gap. These light up for a symbol the moment
    # its M15/M5 parquet exists; the desk currently holds three M15 files and no M5.
    "M15": {"rule": "15min", "max_obs": 4000, "horizons": (1, 4, 16, 96), "min_obs": 800,
            "needs_finer_than": "1h"},
    "M5": {"rule": "5min", "max_obs": 6000, "horizons": (1, 3, 12, 60), "min_obs": 1200,
           "needs_finer_than": "15min"},
}


@dataclass(frozen=True)
class AssetState:
    """What one instrument's regime is, how old it is, and where it is likely to go."""

    symbol: str
    clock: str
    labels: tuple[str, ...]
    #: The FORWARD mix at this clock's first horizon -- what a book held over that period faces.
    probs: dict[str, float]
    #: P(Z_t | data now), kept beside it so the size of the forward adjustment stays visible.
    filtered: dict[str, float]
    age_bars: int
    p_leave: dict[int, float]
    entropy: dict[int, float]
    duration_weight: float
    n_obs: int
    last_bar: str
    engine_confidence: float
    note: str = ""

    @property
    def top(self) -> str:
        return max(self.probs, key=lambda k: self.probs[k]) if self.probs else ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["labels"] = list(self.labels)
        d["p_leave"] = {str(k): v for k, v in self.p_leave.items()}
        d["entropy"] = {str(k): v for k, v in self.entropy.items()}
        d["top"] = self.top
        return d


@dataclass
class FitCache:
    """On-disk memo of fitted states, keyed by what the fit actually saw."""

    path: Path
    _mem: dict[str, dict] = field(default_factory=dict)
    loaded: bool = False

    def _load(self) -> None:
        if self.loaded:
            return
        self.loaded = True
        try:
            self._mem = json.loads(self.path.read_text("utf-8"))
        except (OSError, ValueError):
            self._mem = {}

    def get(self, key: str) -> dict | None:
        self._load()
        v = self._mem.get(key)
        return v if isinstance(v, dict) else None

    def put(self, key: str, value: dict) -> None:
        self._load()
        self._mem[key] = value

    def flush(self, keep: int = 400) -> None:
        if not self.loaded:
            return
        items = sorted(self._mem.items(), key=lambda kv: str(kv[1].get("fitted_at", "")))
        self._mem = dict(items[-keep:])
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._mem, default=str), "utf-8")
        except OSError:
            pass


def native_step(index: pd.DatetimeIndex) -> pd.Timedelta | None:
    """The bar interval the input actually carries, from its own median gap."""
    if index is None or len(index) < 3:
        return None
    diffs = pd.Series(index[1:]) - pd.Series(index[:-1])
    med = diffs.median()
    return med if pd.notna(med) and med > pd.Timedelta(0) else None


def _series(close: pd.Series, clock: str) -> pd.Series:
    """Resample to the clock, REFUSING to upsample past the bars actually held.

    Resampling H1 closes to "15min" does not produce fifteen-minute bars; it produces hourly bars
    with three quarters of the rows forward-filled or dropped, and a regime fitted on that reports
    an intraday state the desk has no data for. `needs_finer_than` makes the refusal explicit, so
    a missing M15 parquet reads as a recorded gap rather than as a confident answer.
    """
    spec = CLOCKS[clock]
    s = close.dropna()
    need = spec.get("needs_finer_than")
    if need:
        step = native_step(pd.DatetimeIndex(s.index))
        # STRICTLY finer, and the `>=` is the whole guard. With `>`, hourly bars satisfied
        # "finer than 1h" and M15 was accepted: `resample("15min").last().dropna()` keeps only
        # the hourly stamps, so the result is the H1 series with an M15 label on it. Caught by
        # reading a real build's output -- XAUUSD@M15 reported age 5, identical to XAUUSD@H1,
        # which is what an upsampled series looks like when nothing refuses it.
        if step is None or step >= pd.Timedelta(need):
            raise ValueError(
                f"{clock} needs bars strictly finer than {need}; the input carries "
                f"{step if step is not None else 'an unreadable interval'}")
    if clock == "daily":
        s = s.groupby(s.index.date).last()
    elif spec["rule"]:
        s = s.resample(spec["rule"]).last().dropna()
    return s.iloc[-int(spec["max_obs"]):]


def cache_key(symbol: str, clock: str, s: pd.Series) -> str:
    payload = f"{symbol}|{clock}|{len(s)}|{s.index[-1]}|{float(s.iloc[-1]):.10g}"
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def fit_asset_state(close: pd.Series, symbol: str, clock: str,
                    cache: FitCache | None = None) -> tuple[AssetState | None, str]:
    """Fit (or read) one instrument's state on one clock. Returns (state, reason)."""
    if clock not in CLOCKS:
        return None, f"unknown clock {clock!r}"
    spec = CLOCKS[clock]
    try:
        s = _series(close, clock)
    except (TypeError, ValueError) as exc:
        return None, f"cannot resample to {clock}: {type(exc).__name__}: {exc}"
    if s.size < int(spec["min_obs"]):
        return None, f"{s.size} {clock} bars, needs {spec['min_obs']}"
    if not np.isfinite(s.to_numpy(dtype=float)).all() or float(s.std()) <= 0:
        return None, "series is constant or non-finite"

    key = cache_key(symbol, clock, s)
    if cache is not None:
        hit = cache.get(key)
        if hit:
            try:
                return _from_dict(hit), "cached"
            except (KeyError, TypeError, ValueError):
                pass

    try:
        from libs.regime.engine import RegimeEngine
        from libs.regime.transitions import forecast

        eng = RegimeEngine().fit(s)
        lab = {j: str(ch["label"]) for j, ch in eng.hmm_char.items()}
        post = eng.posteriors[-1]
        filtered: dict[str, float] = {}
        for j, pj in enumerate(post):
            filtered[lab[int(j)]] = filtered.get(lab[int(j)], 0.0) + float(pj)
        fc = forecast(eng.hmm.transmat, post, lab, eng.hmm_states,
                      horizons=tuple(spec["horizons"]))
        h0 = int(spec["horizons"][0])
        st = AssetState(
            symbol=symbol, clock=clock, labels=fc.labels,
            probs={k: round(v, 6) for k, v in (fc.p_ahead.get(h0) or filtered).items()},
            filtered={k: round(v, 6) for k, v in filtered.items()},
            age_bars=fc.age_bars,
            p_leave={int(h): round(v, 6) for h, v in fc.p_leave.items()},
            entropy={int(h): round(v, 6) for h, v in fc.entropy.items()},
            duration_weight=round(fc.duration_weight, 6),
            n_obs=int(s.size), last_bar=str(s.index[-1]),
            engine_confidence=round(float(str(eng.current().get("confidence") or 0.0)), 6),
            note=fc.note,
        )
    except Exception as exc:                                    # noqa: BLE001 - fail closed by name
        return None, f"{type(exc).__name__}: {exc}"

    if cache is not None:
        d = st.to_dict()
        d["fitted_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        cache.put(key, d)
    return st, "fitted"


def _from_dict(d: dict) -> AssetState:
    return AssetState(
        symbol=str(d["symbol"]), clock=str(d["clock"]), labels=tuple(d["labels"]),
        probs={str(k): float(v) for k, v in d["probs"].items()},
        filtered={str(k): float(v) for k, v in d["filtered"].items()},
        age_bars=int(d["age_bars"]),
        p_leave={int(k): float(v) for k, v in d["p_leave"].items()},
        entropy={int(k): float(v) for k, v in d["entropy"].items()},
        duration_weight=float(d["duration_weight"]), n_obs=int(d["n_obs"]),
        last_bar=str(d["last_bar"]), engine_confidence=float(d.get("engine_confidence", 0.0)),
        note=str(d.get("note", "")),
    )
