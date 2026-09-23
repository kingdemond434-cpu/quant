"""The capture interface: one thin seam between the broker terminal and everything above it.

WHY A SEAM AT ALL. `MetaTrader5` is a Windows-only binary package. It does not import on the
VPS, it does not import in CI, and it does not import in the container this code was written in.
A recorder written directly against it can therefore only be tested by running it on the trading
box against a live account -- which is to say, it can only be tested by the one execution where a
defect is expensive. Every previous tick collector on this desk was written that way, and the
consequence was visible: `moat_silver.py`'s own docstring records a converter that died silently
while the recorder "recorded perfectly", found only because someone happened to look at a file
date. Nothing could be tested, so nothing was.

This module is the entire Windows surface of the capture layer. It is deliberately small enough
to read in one sitting, because its correctness is the one thing that cannot be proven off the
box. Everything above it -- storage, sealing, gap accounting, integrity, features -- is pure
Python over these five methods and is tested against `FakeTickSource` in this container.

THE CONTRACT, and each clause is here because MT5 violates the obvious assumption:

  * `alive()` is asked EVERY cycle, not once at start. `mt5.initialize()` succeeding at 08:00
    says nothing about 14:00: the terminal restarts on broker updates, loses its connection over
    the weekend roll and is closed by hand when someone RDPs in. A recorder that initialises once
    and then loops on a dead handle records nothing and reports success.
  * `symbols()` is asked every cycle too. The broker adds and removes instruments, and a
    hardcoded list is how the energy and index complexes stayed untested for the life of this
    desk (`mt5desk/universe.py` documents that incident). The universe is whatever the terminal
    says it is, right now.
  * `ticks()` returns the broker's OWN timestamps, untouched. `time_msc` is milliseconds as the
    server reports them; it is NOT necessarily UTC, because an MT5 server stamps in its own
    timezone and the Python API hands the number through unconverted. Converting here would
    destroy the only copy of what the broker actually said. The offset is measured separately by
    `clock_probe()` and recorded beside the tape, so the conversion stays reversible forever.
  * `clock_probe()` exists for exactly that reason and is cheap. The difference between local UTC
    and the server's newest tick stamp is unbuyable after the fact: without it, a tape recorded
    across a DST change cannot be aligned to a macro release later.
  * `symbol_spec()` carries `point` and `digits`, which are part of the tape's UNIT. The store
    encodes prices as integer points, so a segment written under the wrong point is a segment of
    wrong prices. It is recorded per segment rather than looked up at read time for the reason
    `mt5desk/tape.py` already gives: `symbol_info` reports TODAY's value, and re-deriving a past
    day's unit from tomorrow's registry silently re-prices yesterday's tape.

ABSENCE IS NEVER A VALUE (WS-005). Every method returns None or an empty result and says why,
rather than substituting a plausible number. A `ticks()` call that fails raises `TickSourceError`
so the caller can record the failure as a GAP; a call that legitimately has nothing returns an
empty array, which is a different fact and is recorded differently.
"""
from __future__ import annotations

import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

import numpy as np

#: The dtype every source must return. Field names match MT5's own tick struct so the MT5
#: implementation is a zero-copy pass-through and the fake cannot drift from it.
TICK_DTYPE = np.dtype([
    ("time", "<i8"),        # seconds, broker clock -- kept because MT5 gives it
    ("bid", "<f8"),
    ("ask", "<f8"),
    ("last", "<f8"),
    ("volume", "<u8"),
    ("time_msc", "<i8"),    # milliseconds, broker clock -- THE timestamp; `time` collapses bursts
    ("flags", "<u4"),       # which of bid/ask/last/volume actually changed on this tick
    ("volume_real", "<f8"),
])

#: MT5's COPY_TICKS_ALL. Named here so the fake and the tests do not import MetaTrader5.
COPY_TICKS_ALL = 3


class TickSourceError(RuntimeError):
    """The source could not answer. ALWAYS a recorded gap, never a silent zero."""


@dataclass(frozen=True)
class SymbolSpec:
    """The terms that make a tick decodable. `point` is part of the unit, not decoration."""

    symbol: str
    point: float
    digits: int
    trade_mode: int | None = None
    spread: int | None = None
    #: `False` where the terminal reports the symbol but it is not visible in MarketWatch --
    #: ticks for such a symbol may be absent for a reason that is not a market condition.
    visible: bool = True


@runtime_checkable
class TickSource(Protocol):
    """Everything the recorder is allowed to know about the broker."""

    def alive(self) -> bool:
        """Is the terminal connected RIGHT NOW? Asked every cycle."""

    def symbols(self) -> list[str]:
        """The broker's current symbol list. The universe is this, never a stored list."""

    def symbol_spec(self, symbol: str) -> SymbolSpec | None:
        """Point/digits/trade-mode for `symbol`, or None if the terminal will not say."""

    def ticks(self, symbol: str, start_ms: int, end_ms: int) -> np.ndarray:
        """Every tick in [start_ms, end_ms), broker timestamps untouched, TICK_DTYPE.

        Raises TickSourceError if the call fails. Returns an empty array if it succeeds and
        there is nothing there -- a different fact, recorded differently.
        """

    def clock_probe(self, symbol: str) -> tuple[int, int] | None:
        """(local_utc_ms, server_tick_ms) for one reference symbol, or None.

        The skew between these two is unrecoverable after the fact and is what lets a future
        reader align this tape to a UTC-stamped event calendar.
        """


class Mt5TickSource:
    """The real thing. THE ONLY PART OF THIS PACKAGE THAT NEEDS WINDOWS.

    `MetaTrader5` is imported inside methods, never at module scope, so this file imports
    everywhere and the recorder's tests, the integrity checker and the feature builder all run
    in CI. An import at module scope would make the whole package Windows-only for the sake of
    one class.
    """

    def __init__(self, terminal_path: str | None = None) -> None:
        self._terminal_path = terminal_path
        self._initialised = False

    def _mt5(self) -> Any:
        import MetaTrader5 as mt5  # the vendor's own casing
        return mt5

    def initialize(self) -> bool:
        """Connect, or say why not. Idempotent: safe to call every cycle after a restart."""
        mt5 = self._mt5()
        if mt5.terminal_info() is not None:
            self._initialised = True
            return True
        ok = bool(mt5.initialize(path=self._terminal_path) if self._terminal_path
                  else mt5.initialize())
        self._initialised = ok
        return ok

    def alive(self) -> bool:
        try:
            mt5 = self._mt5()
        except ImportError:
            return False
        try:
            info = mt5.terminal_info()
        except Exception:
            return False
        if info is None:
            # A dead handle is RECOVERABLE and the recovery belongs here, not in the loop: the
            # terminal restarting is the normal condition on this box, not an incident.
            try:
                return self.initialize()
            except Exception:
                return False
        return bool(getattr(info, "connected", True))

    def symbols(self) -> list[str]:
        mt5 = self._mt5()
        try:
            got = mt5.symbols_get()
        except Exception as exc:
            raise TickSourceError(f"symbols_get: {type(exc).__name__}: {exc}") from exc
        if not got:
            raise TickSourceError("symbols_get returned nothing -- treated as a source failure, "
                                  "never as an empty universe (a broker with no symbols is not "
                                  "a thing that happens; a dead terminal is)")
        return sorted(str(s.name) for s in got)

    def symbol_spec(self, symbol: str) -> SymbolSpec | None:
        mt5 = self._mt5()
        try:
            info = mt5.symbol_info(symbol)
        except Exception:
            return None
        if info is None:
            return None
        point = float(getattr(info, "point", 0.0) or 0.0)
        if point <= 0:
            return None
        return SymbolSpec(
            symbol=symbol, point=point, digits=int(getattr(info, "digits", 0) or 0),
            trade_mode=(int(info.trade_mode) if getattr(info, "trade_mode", None) is not None
                        else None),
            spread=(int(info.spread) if getattr(info, "spread", None) is not None else None),
            visible=bool(getattr(info, "visible", True)),
        )

    def select(self, symbol: str) -> bool:
        """Put a symbol in MarketWatch. An unselected symbol can return no ticks for a
        reason unrelated to the market, which would otherwise be recorded as a market gap."""
        mt5 = self._mt5()
        try:
            return bool(mt5.symbol_select(symbol, True))
        except Exception:
            return False

    def ticks(self, symbol: str, start_ms: int, end_ms: int) -> np.ndarray:
        mt5 = self._mt5()
        start = datetime.fromtimestamp(start_ms / 1000.0, tz=UTC)
        end = datetime.fromtimestamp(end_ms / 1000.0, tz=UTC)
        try:
            got = mt5.copy_ticks_range(symbol, start, end, COPY_TICKS_ALL)
        except Exception as exc:
            raise TickSourceError(f"copy_ticks_range({symbol}): "
                                 f"{type(exc).__name__}: {exc}") from exc
        if got is None:
            # None is MT5's failure signal and is DISTINCT from an empty array. Collapsing the
            # two is how a broken feed reads as a quiet market.
            err = ""
            with suppress(Exception):
                err = str(mt5.last_error())
            raise TickSourceError(f"copy_ticks_range({symbol}) returned None: {err}")
        arr = np.asarray(got)
        if arr.size == 0:
            return np.empty(0, dtype=TICK_DTYPE)
        return arr

    def clock_probe(self, symbol: str) -> tuple[int, int] | None:
        mt5 = self._mt5()
        try:
            local_ms = int(time.time() * 1000)
            t = mt5.symbol_info_tick(symbol)
        except Exception:
            return None
        if t is None:
            return None
        server_ms = int(getattr(t, "time_msc", 0) or 0)
        if server_ms <= 0:
            return None
        return local_ms, server_ms


class FakeTickSource:
    """A deterministic broker for tests. NOT a mock -- it is a small simulator, on purpose.

    A mock that returns whatever the test asked for proves the test, not the code. This produces
    a tape with the properties real quote streams have and the recorder must survive: bursty
    inter-arrival times, a spread that widens and narrows, sessions with real weekend holes,
    occasional out-of-order stamps and exact duplicates. The integrity checker's own thresholds
    are then measured against something that actually contains the pathologies it hunts.
    """

    def __init__(self, symbols: list[str], *, point: float = 1e-5, digits: int = 5,
                 seed: int = 0, ticks_per_day: int = 100_000,
                 start_ms: int = 1_780_000_000_000) -> None:
        self._symbols = sorted(symbols)
        self.point = point
        self.digits = digits
        self.ticks_per_day = ticks_per_day
        self._start_ms = start_ms
        self._rng = np.random.default_rng(seed)
        self.is_alive = True
        #: Set to raise on the next `ticks()` call for a named symbol -- how a test makes the
        #: broker fail without patching anything.
        self.fail_symbols: set[str] = set()
        #: Symbols the source reports but returns nothing for (a delisted-but-listed instrument).
        self.silent_symbols: set[str] = set()
        self.clock_skew_ms = 0
        self.calls: list[tuple[str, int, int]] = []

    def alive(self) -> bool:
        return self.is_alive

    def symbols(self) -> list[str]:
        if not self.is_alive:
            raise TickSourceError("terminal not connected")
        return list(self._symbols)

    def add_symbol(self, symbol: str) -> None:
        self._symbols = sorted({*self._symbols, symbol})

    def remove_symbol(self, symbol: str) -> None:
        self._symbols = [s for s in self._symbols if s != symbol]

    def symbol_spec(self, symbol: str) -> SymbolSpec | None:
        if symbol not in self._symbols:
            return None
        return SymbolSpec(symbol=symbol, point=self.point, digits=self.digits, trade_mode=4)

    def clock_probe(self, symbol: str) -> tuple[int, int] | None:
        if not self.is_alive:
            return None
        local = self._start_ms
        return local, local + self.clock_skew_ms

    def ticks(self, symbol: str, start_ms: int, end_ms: int) -> np.ndarray:
        self.calls.append((symbol, start_ms, end_ms))
        if not self.is_alive:
            raise TickSourceError("terminal not connected")
        if symbol in self.fail_symbols:
            raise TickSourceError(f"synthetic failure for {symbol}")
        if symbol in self.silent_symbols or symbol not in self._symbols:
            return np.empty(0, dtype=TICK_DTYPE)
        return self.generate(symbol, start_ms, end_ms)

    def generate(self, symbol: str, start_ms: int, end_ms: int) -> np.ndarray:
        """A tick tape over [start_ms, end_ms) with weekends genuinely absent.

        Weekends are a HOLE, not a thin patch: a recorder that treats Saturday's silence as an
        outage will alarm every week, and one that treats a Tuesday outage as a weekend will
        never alarm at all. Both mistakes are only findable against a tape that has both.
        """
        if end_ms <= start_ms:
            return np.empty(0, dtype=TICK_DTYPE)
        span_ms = end_ms - start_ms
        n = max(0, int(self.ticks_per_day * span_ms / 86_400_000))
        if n == 0:
            return np.empty(0, dtype=TICK_DTYPE)
        # Deterministic per (symbol, window) so a re-pull of an overlapping window returns the
        # SAME ticks -- which is what makes the recorder's dedup testable.
        rng = np.random.default_rng(abs(hash((symbol, start_ms // 60_000))) % (2**32))
        tms = np.sort(rng.integers(start_ms, end_ms, size=n)).astype(np.int64)
        # Drop the weekend: Saturday 00:00 UTC to Sunday 21:00 UTC, the FX market's own hole.
        dow = ((tms // 86_400_000) + 4) % 7           # 1970-01-01 was a Thursday
        secs = (tms % 86_400_000) // 1000
        weekend = (dow == 6) | ((dow == 0) & (secs < 21 * 3600))
        tms = tms[~weekend]
        n = tms.size
        if n == 0:
            return np.empty(0, dtype=TICK_DTYPE)
        mid_pts = 100_000 + np.cumsum(rng.choice([-1, 0, 1], size=n, p=[0.22, 0.56, 0.22]))
        spread_pts = np.full(n, 12, dtype=np.int64)
        if n > 400:
            i = int(rng.integers(0, n - 200))
            spread_pts[i:i + 200] = 90                # a widening episode the features must see
        bid = (mid_pts - spread_pts // 2) * self.point
        ask = bid + spread_pts * self.point
        out = np.empty(n, dtype=TICK_DTYPE)
        out["time_msc"] = tms
        out["time"] = tms // 1000
        out["bid"] = np.round(bid, self.digits)
        out["ask"] = np.round(ask, self.digits)
        out["last"] = 0.0
        out["volume"] = 0
        out["flags"] = 6                              # BID|ASK changed
        out["volume_real"] = 0.0
        return out
