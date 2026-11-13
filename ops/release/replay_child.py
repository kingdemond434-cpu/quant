#!/usr/bin/env python3
"""One tree's half of the replay shadow: run the live E8 gold book over one scenario day, and the
FTMO lane (the sleeve executor and the venue reader) at every step of it.

Started by ops/release/replay_shadow.py as `python -I replay_child.py <tree> <scenario.json>
<out.json>` from an empty working directory, once per scenario and per tree. It imports
`prop.e8_gold` from <tree> (the base or the PR head) with the terminal and the venue faked, steps
the server clock through the day, and writes what the book decided at each step. Unarmed, so
nothing it decides is ever sent; there is no terminal, no venue and no key on the runner anyway.

The file names the book writes (state, journal, guard) are pointed into the working directory, so
each scenario starts from a clean day and the two trees never share a file.

THE FTMO LEG (2026-11-03): the prop lane was money path the replay never imported, so every
change to it was UNMEASURED. At each step the leg runs `prop.ftmo_executor.run` UNARMED and
`prop.ftmo_venue_reader.run` on a fake FTMO terminal (one account, no positions, a fresh tick on
the broker clock, closed H1 bars), with every file they read or write sandboxed. The doors that
need the box (the replication store, Tier S, promotion authority, the order door, the family
code) are stubbed identically on both trees; the one sleeve's signal side follows the scenario's
price shape, its other accounts' books follow its positions, and its equity is the scenario's,
so what differs between the trees can only be the lane's own sizing, rails and fence.
"""

from __future__ import annotations

import json
import random
import sys
import traceback
import types
from pathlib import Path
from typing import Any, ClassVar
from unittest import mock

#: Module attributes the book reads and writes its own files through.
SANDBOXED = ("OUT", "INTENTS", "LOG", "STATE", "GUARD", "ARMED_MARKER")
SYMBOL_ID = 6102
CONTRACT = 100.0
SPREAD = 0.4


def bars(shape: str, seed: int, day: Any, now: Any) -> list[dict[str, float]]:
    """Every closed H1 bar up to `now` (never one after it), deterministic in (shape, seed)."""
    import pandas as pd

    rng = random.Random(f"{shape}:{seed}")  # noqa: S311 -- a price path, not a secret
    idx = pd.date_range(end=now.floor("h"), periods=400, freq="h")
    px = 4300.0
    out = []
    for t in idx:
        hour = (t - day).total_seconds() / 3600.0
        today = 0.0 <= hour < 24.0
        step = rng.gauss(0.0, 9.0 if shape == "wide" else 3.0)
        if today and shape == "up_break" and hour >= 8:
            step = abs(step) + 6.0
        elif today and shape == "down_break" and hour >= 8:
            step = -abs(step) - 6.0
        elif today and shape == "gap" and hour == 0:
            step = 45.0
        elif shape == "range" and today:
            step *= 0.3
        o = px
        px = max(100.0, px + step)
        span = abs(rng.gauss(0.0, 4.0 if shape == "wide" else 1.5))
        out.append(
            {
                "time": int(t.timestamp()),
                "open": round(o, 2),
                "high": round(max(o, px) + span, 2),
                "low": round(min(o, px) - span, 2),
                "close": round(px, 2),
            }
        )
    return out


FTMO_LOGIN, FTMO_SERVER, FTMO_MODE = 5100200, "FTMO-Replay", 0
#: The one sleeve the FTMO leg sizes: a non-gold certificate key, its spec and its fraction.
FTMO_KEY = "EURUSD_overnight_gap_decay_asia"
FTMO_SPEC = {
    "key": "external.EURUSD.overnight_gap_decay.p=1",
    "symbol": "EURUSD",
    "family": "overnight_gap_decay",
    "selector": "asia",
    "fingerprint": "replay",
    "params": {"timeframe": "H1"},
}
FTMO_FRAC = 0.003
#: The side each price shape's signal takes (None: no signal).
FTMO_SIDE = {"up_break": 1, "down_break": -1, "gap": 1, "wide": -1, "range": None}
#: Names a refactor may add to a report without changing a decision: never compared.
FTMO_STAMPS = frozenset({"at", "account", "generated_at", "updated_at", "ts"})


def ftmo_norm(doc: Any) -> Any:
    if isinstance(doc, dict):
        return {k: ftmo_norm(v) for k, v in sorted(doc.items()) if k not in FTMO_STAMPS}
    if isinstance(doc, list):
        return [ftmo_norm(x) for x in doc]
    return doc


class FtmoTerminal:
    """A fake FTMO terminal: the declared account, no positions, a fresh tick, flat H1 bars
    ending in the forming one. Records every order_send (unarmed: there must be none)."""

    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1
    ORDER_TIME_GTC, ORDER_FILLING_FOK, ORDER_FILLING_IOC, ORDER_FILLING_RETURN = 0, 0, 1, 2
    TIMEFRAME_H1 = 16385

    def __init__(self, sc: dict[str, Any], clock: dict[str, Any]) -> None:
        self.sc, self.clock, self.sent = sc, clock, []

    def _epoch(self) -> int:
        from prop.e8_guard import server_offset_hours  # the broker clock, NY+7

        now = self.clock["now"].to_pydatetime()
        return int(now.timestamp() + 3600 * server_offset_hours(now)) - int(
            self.sc.get("tick_lag_s", 0)
        )

    def account_info(self) -> Any:
        eq = float(self.sc["equity"])
        return types.SimpleNamespace(
            login=FTMO_LOGIN,
            server=FTMO_SERVER,
            trade_mode=FTMO_MODE,
            equity=eq,
            balance=eq,
            margin_free=eq,
            currency="USD",
        )

    def symbol_select(self, sym: str, on: bool) -> bool:
        return True

    def symbol_info_tick(self, sym: str) -> Any:
        return types.SimpleNamespace(time=self._epoch(), bid=1.1000, ask=1.1001)

    def symbol_info(self, sym: str) -> Any:
        return types.SimpleNamespace(
            volume_min=0.01,
            volume_step=0.01,
            volume_max=50.0,
            trade_contract_size=100_000.0,
            point=0.00001,
            filling_mode=2,
            name=sym,
            digits=5,
            spread=10,
            swap_long=0.0,
            swap_short=0.0,
            trade_mode=4,
        )

    def symbols_get(self) -> list:
        return [self.symbol_info(s) for s in ("EURUSD", "AUDNZD", "XAUUSD")]

    def order_calc_profit(self, typ: int, sym: str, vol: float, a: float, b: float) -> float:
        return (b - a if typ == 0 else a - b) * 100_000.0 * vol

    def positions_get(self, symbol: str | None = None) -> list:
        return []

    def orders_get(self, symbol: str | None = None) -> list:
        return []

    def history_orders_get(self, a: Any, b: Any) -> list:
        return []

    def history_deals_get(self, a: Any, b: Any) -> list:
        return []

    def copy_rates_from_pos(self, sym: str, tf: int, start: int, n: int) -> list:
        t1 = (self._epoch() // 3600) * 3600
        return [
            {
                "time": t1 - 3600 * (n - 1 - i),
                "open": 1.1,
                "high": 1.101,
                "low": 1.099,
                "close": 1.1,
                "tick_volume": 1,
            }
            for i in range(n)
        ]

    def order_send(self, req: dict) -> Any:
        self.sent.append(req)
        return types.SimpleNamespace(retcode=10009, order=1)

    def last_error(self) -> tuple:
        return (1, "ok")


def _ftmo_key_env(work: Path, scenario: dict[str, Any]) -> str:
    """A throwaway account key, the same for both trees of one comparison (it is derived from the
    comparison's random fingerprint), so the lane can name its account as the box does."""
    key = work / "ftmo_account_key.hmac"
    key.write_text(f"replay-{scenario['server']}-{scenario['account_id']}".ljust(48, "0"), "utf-8")
    return str(key)


def ftmo_setup(work: Path, scenario: dict[str, Any]) -> list[tuple[Any, str, Any]]:
    """Once per scenario: sandbox every file the FTMO lane reads or writes, and return the box
    doors' stubs as (module, name, stub). The stubs are applied ONLY around the FTMO leg
    (`ftmo_step`), so the E8 leg of the same step runs against the real doors as before."""
    import contextlib
    import importlib

    import pandas as pd
    from mt5desk import cross_account as xa
    from mt5desk import decision_core, families, family_call, kelly_sizing, order_door
    from prop import e8_executor
    from prop import ftmo_executor as fx
    from prop import ftmo_follower as ff
    from prop import ftmo_venue_reader as fvr

    from libs.ops import new_risk_hold
    from libs.tiers import promotion_authority

    # importing the lane put desks/mt5/research on the path, as on the box
    admission_integrity = importlib.import_module("admission_integrity")
    # the prop fleet runner, on a tree that has one (a tree without it is the same as one whose
    # fleet runs no account: neither adds a compared field)
    with contextlib.suppress(ImportError):
        importlib.import_module("prop.prop_fleet")

    box = work / "ftmo"
    (box / "xacct").mkdir(parents=True, exist_ok=True)
    decl = box / "FTMO_LIVE_ACCOUNT.json"
    decl.write_text(
        json.dumps(
            {
                "login": FTMO_LOGIN,
                "server": FTMO_SERVER,
                "trade_mode": FTMO_MODE,
                "initial_balance": 100_000.0,
                "account_type": "2-step",
            }
        ),
        "utf-8",
    )
    ff.ACCOUNT_FILE = decl
    xa.XACCT_DIR = box / "xacct"
    for mod, names in (
        (fx, ("ARMED_MARKER", "ALLOCATOR", "STATE", "OUT", "INTENTS", "LOG")),
        (fvr, ("STATE_OUT", "REGISTRY_OUT", "SURFACE_OUT", "BARS_DIR", "PHASES", "LOG")),
    ):
        for n in names:
            setattr(mod, n, box / f"{mod.__name__.rsplit('.', 1)[-1]}_{n.lower()}")
    fvr.SURFACE_OUT.write_text(json.dumps({"built_at": "2999-01-01T00:00:00+00:00"}), "utf-8")
    cert = box / "CERT_BOOK_LIVE.json"
    cert.write_text(
        json.dumps({"enabled": True, "excluded": {}, "ftmo": {FTMO_KEY: FTMO_FRAC}}), "utf-8"
    )
    gate = types.SimpleNamespace(alarm={}, replication=lambda k, f: ("REPLICATED", "ok"))
    side = FTMO_SIDE.get(str(scenario.get("shape")))

    def family(d: Any, **k: Any) -> list:
        if side is None or d is None or len(d) < 2:
            return []
        t = pd.Timestamp(d.index[-2])  # the last CLOSED bar (the frame ends with the forming one)
        return [
            types.SimpleNamespace(
                time=t,
                side=side,
                stop=1.0950 if side > 0 else 1.1050,
                target=1.1100 if side > 0 else 1.0900,
                ttl_bars=6,
            )
        ]

    return [
        (kelly_sizing, "CERT_BOOK_FILE", cert),
        (order_door, "guard", lambda mt5, caller="", log=None: mt5),
        (new_risk_hold, "reason", lambda root=None: None),
        (admission_integrity.IntegrityGate, "load", classmethod(lambda c: gate)),
        (admission_integrity, "REPLICATED", "REPLICATED"),
        (promotion_authority, "block", lambda k: None),
        (families, "get_family_func", lambda f: family),
        (family_call, "certified_session_filter", lambda s, sl: s),
        (family_call, "signal_reference_price", lambda f, b, g: None),
        (
            decision_core,
            "family_bracket",
            lambda g, s, b, a, c: (
                a,
                g.stop,
                g.target,
                abs(a - g.stop),
                "certified",
                0.0,
                "certified",
            ),
        ),
        (e8_executor, "_call_params", lambda s, sym, bars: {}),
    ]


def _ftmo_book(xa: Any, name: str, now: Any, symbols: dict[str, Any]) -> None:
    (xa.XACCT_DIR / f"{name}_book.json").write_text(
        json.dumps(
            {
                "account": name,
                "covers": "all",
                "at": now.isoformat(),
                "symbols": symbols,
                "account_key": "sha256:0123456789abcdef",
            }
        ),
        "utf-8",
    )


class _NoChild:
    """The fleet runner's child process, never started: it reports a clean exit."""

    returncode = 0

    def __init__(self, *a: Any, **k: Any) -> None:
        pass

    def communicate(self, timeout: float | None = None) -> tuple[str, None]:
        return "", None

    def kill(self) -> None:
        pass


def ftmo_step(
    work: Path, scenario: dict[str, Any], clock: dict[str, Any], stubs: list[tuple[Any, str, Any]]
) -> dict[str, Any]:
    """One unarmed FTMO executor pass and one venue-reader pass at this step, normalised, with
    the box doors stubbed for exactly this leg."""
    import contextlib
    import os

    from mt5desk import cross_account as xa
    from prop import ftmo_executor as fx
    from prop import ftmo_venue_reader as fvr

    now = clock["now"].to_pydatetime()
    fx.ALLOCATOR.write_text(
        json.dumps(
            {
                "generated_at": now.isoformat(),
                "deployable": True,
                "status": "OK",
                "specs": {FTMO_KEY: FTMO_SPEC},
                "executable": {FTMO_KEY: FTMO_FRAC},
            }
        ),
        "utf-8",
    )
    other = {"EURUSD": {"long": True, "short": False}} if scenario.get("positions") else {}
    _ftmo_book(xa, "fusion", now, {})
    _ftmo_book(xa, "e8", now, other)
    term = FtmoTerminal(scenario, clock)
    out: dict[str, Any] = {}
    seen = len(fx.INTENTS.read_text("utf-8").splitlines()) if fx.INTENTS.exists() else 0
    was = os.environ.get("QUANT_ACCOUNT_KEY_FILE")
    os.environ["QUANT_ACCOUNT_KEY_FILE"] = _ftmo_key_env(work, scenario)
    try:  # the key and the stubs are the leg's alone: the E8 leg never sees either
        with contextlib.ExitStack() as patched:
            for target, name, stub in stubs:
                patched.enter_context(mock.patch.object(target, name, stub))
            for name, call in (
                ("exec", lambda: fx.run(term, armed=False, now=now)),
                ("reader", lambda: fvr.run(term, now=now)),
            ):
                try:
                    out[name] = ftmo_norm(call())
                except Exception as exc:  # the verdict IS the exception: compared, not hidden
                    out[name] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    finally:
        if was is None:
            os.environ.pop("QUANT_ACCOUNT_KEY_FILE", None)
        else:
            os.environ["QUANT_ACCOUNT_KEY_FILE"] = was
    fleet = sys.modules.get("prop.prop_fleet")
    if fleet is not None:
        # every extra prop account the tree registers would be a child process: none is started
        # here, and the step records only a runner that raised (a tree whose fleet cannot even
        # enumerate its accounts differs from every other tree)
        try:
            fleet.run_role("executor", popen=_NoChild)
        except Exception as exc:
            out["fleet_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    rows = fx.INTENTS.read_text("utf-8").splitlines()[seen:] if fx.INTENTS.exists() else []
    out["intents"] = [ftmo_norm(json.loads(x)) for x in rows if x.strip()]
    out["sent"] = len(term.sent)
    return out


def main(tree: Path, scenario: dict[str, Any], out_path: Path) -> int:
    stub = types.ModuleType("MetaTrader5")
    stub.__getattr__ = lambda name: mock.MagicMock(name="MetaTrader5." + name)  # type: ignore[method-assign]
    sys.modules["MetaTrader5"] = stub
    sys.path[:0] = [str(tree), str(tree / "desks" / "mt5")]
    import os

    os.environ.pop("QUANT_PROP_ACCOUNT", None)  # the FTMO leg replays the FTMO account
    import pandas as pd

    work = Path.cwd()
    from prop import e8_gold as g

    for name in SANDBOXED:
        setattr(g, name, work / f"{name.lower()}.json")
    if scenario.get("own"):  # today's asia bracket filled into the scenario's position
        (work / "state.json").write_text(
            json.dumps(
                {"date": scenario["day"], "carried": {}, "windows": {"asia": scenario["own"]}}
            ),
            "utf-8",
        )
    if scenario.get("guard"):  # the guard keys its anchor by the wall clock's server day
        from prop import e8_guard

        guard = {**scenario["guard"], "day": e8_guard.server_day()}
        (work / "guard.json").write_text(json.dumps(guard), "utf-8")
    day = pd.Timestamp(scenario["day"], tz="UTC")
    clock = {"now": day}

    class _Tick:
        @property
        def time(self) -> int:
            return int(clock["now"].timestamp()) - int(scenario.get("tick_lag_s", 0))

    class _Terminal:
        TIMEFRAME_H1 = 16385

        def symbol_info_tick(self, symbol: str) -> Any:
            return _Tick()

        def copy_rates_from_pos(self, symbol: str, tf: int, start: int, count: int) -> list:
            return bars(scenario["shape"], scenario["seed"], day, clock["now"])[-count:]

    class _Api:
        account_id = int(scenario["account_id"])
        _credentials = {"server": str(scenario["server"])}  # noqa: RUF012

        @staticmethod
        def get_all_orders(history: bool = False, lookback_period: str = "") -> list:
            return []

    def _last() -> float:
        return bars(scenario["shape"], scenario["seed"], day, clock["now"])[-1]["close"]

    class _Venue:
        _api = _Api()

        def account(self) -> dict:
            return {"equity": float(scenario["equity"]), "balance": float(scenario["equity"])}

        def quote(self, symbol: str) -> tuple[float, float]:
            return _last(), round(_last() + SPREAD, 2)

        def instrument_id(self, symbol: str) -> int:
            return SYMBOL_ID

        def positions(self) -> list[dict]:
            return [dict(p) for p in scenario.get("positions", [])]

        def orders(self, symbol: str | None = None) -> list[dict]:
            return [dict(o) for o in scenario.get("orders", [])]

        def min_lot(self, symbol: str) -> float:
            return 0.01

        def details(self, symbol: str) -> dict:
            return {"contractSize": CONTRACT, "currency": "USD", "lotStep": 0.01}

        def cancel(self, order_id: int) -> bool:
            return bool(scenario.get("venue_ok", True))

        def modify_stop(self, position_id: int, stop: float) -> bool:
            return bool(scenario.get("venue_ok", True))

        def close(self, position_id: int, quantity: float = 0) -> bool:
            return bool(scenario.get("venue_ok", True))

    try:
        ftmo_stubs = ftmo_setup(work, scenario)
        ftmo_ready: str | None = None
    except Exception as exc:  # compared: a tree whose lane cannot be set up says so every step
        ftmo_ready = f"{type(exc).__name__}: {str(exc)[:200]}"
        traceback.print_exc()
    steps = []
    seen = 0
    for hour in scenario["hours"]:
        clock["now"] = day + pd.Timedelta(hours=float(hour))
        try:
            doc = g.run(_Venue(), _Terminal(), armed=False)
            err = None
        except Exception as exc:  # the step's verdict IS the exception: compared, not hidden
            doc, err = {}, f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
        rows: list[Any] = []
        intents = work / "intents.json"
        if intents.exists():
            lines = intents.read_text("utf-8").splitlines()
            rows = [json.loads(x) for x in lines[seen:] if x.strip()]
            seen = len(lines)
        if ftmo_ready is None:
            try:
                ftmo = ftmo_step(work, scenario, clock, ftmo_stubs)
            except Exception as exc:
                ftmo = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
                traceback.print_exc()
        else:
            ftmo = {"setup_error": ftmo_ready}
        steps.append({"hour": hour, "doc": doc, "intents": rows, "error": err, "ftmo": ftmo})
    imported = sorted(
        {
            str(Path(m.__file__).resolve())
            for m in list(sys.modules.values())
            if getattr(m, "__file__", None)
        }
    )
    out_path.write_text(json.dumps({"steps": steps, "imported": imported}, default=str), "utf-8")
    return 0


# ---------------------------------------------------------------------------------------------
# THE SIGNAL LEG (2026-11-13). The scenario legs above stub the family code out (the FTMO leg's
# `families.get_family_func` is a fixed stub), so a change to a family module was money path the
# replay never ran: UNMEASURED, every time, whatever it did. This leg runs EVERY family the desk
# can resolve, through the two resolvers the order path uses (`executables.resolve_family`, the
# gateway's; `families.get_family_func`, the prop executors') and the call the forward clock and
# the live executor share (`family_call.signals`, `family_call.hunt16_signals`), over a fixed grid
# of synthetic H1 frames, both sides, with its default parameters and its grid's first point.
# What each call decided (a digest of every signal's time, side, stop, target, ttl and the rest of
# the record) is compared between the trees by replay_shadow.signal_problems.
#
# IT ALSO RECORDS WHICH LINES RAN. Importing a module proves nothing about the change inside it,
# so the parent counts a changed family-path file as measured only when every changed statement
# executed inside a call that returned on BOTH trees and was compared (replay_shadow.
# signal_measured). The lines are traced only in the files the parent names (`trace`), so the
# cost is one cheap global hook per Python call.

#: The frames: symbol x price shape, each SIGNAL_BARS closed H1 bars ending on a fixed day.
SIGNAL_SYMBOLS = {"XAUUSD": 4300.0, "EURUSD": 1.10}
SIGNAL_SHAPES = ("range", "up_break", "down_break", "wide", "gap")
SIGNAL_BARS = 1500
SIGNAL_END = "2026-10-15 23:00"
#: One call's budget. A call past it is recorded as a timeout and none of its lines count.
SIGNAL_CALL_S = 60


#: pandas frequencies of the charts a certificate can name (`timeframe`, absent means H1).
TF_FREQ = {"M1": "min", "M5": "5min", "M15": "15min", "M30": "30min", "H1": "h", "H4": "4h",
           "D1": "D"}  # fmt: skip


def symbol_price(symbol: str) -> float:
    """A plausible, deterministic price level for any symbol (the two grid symbols keep theirs)."""
    import zlib

    if symbol in SIGNAL_SYMBOLS:
        return SIGNAL_SYMBOLS[symbol]
    s = symbol.upper()
    if s.endswith("JPY") or s.endswith("HUF"):
        return 150.0
    if len(s) == 6 and s.isalpha():
        return 0.6 + (zlib.crc32(s.encode()) % 900) / 1000.0
    return 50.0 + zlib.crc32(s.encode()) % 5000


def signal_frame(
    symbol: str, shape: str, *, end: Any = None, n: int = SIGNAL_BARS, tf: str = "H1"
) -> Any:
    """`n` bars of chart `tf` for `symbol` in `shape` ending at `end` (default SIGNAL_END),
    deterministic in (symbol, shape) -- the grid's own frames are exactly what they were -- with
    the columns a terminal's rates carry (tick_volume, spread, real_volume)."""
    import pandas as pd

    rng = random.Random(f"signal:{symbol}:{shape}")  # noqa: S311 -- a price path, not a secret
    base = symbol_price(symbol)
    unit = base / 1000.0
    stop = pd.Timestamp(SIGNAL_END if end is None else end)
    stop = stop.tz_localize("UTC") if stop.tzinfo is None else stop.tz_convert("UTC")
    freq = TF_FREQ.get(str(tf).upper(), "h")
    idx = pd.date_range(end=stop.floor(freq), periods=int(n), freq=freq)
    px, rows = base, []
    for i, t in enumerate(idx):
        step = rng.gauss(0.0, (9.0 if shape == "wide" else 3.0) * unit)
        if shape == "up_break" and i % 120 > 100:
            step = abs(step) + 4.0 * unit
        elif shape == "down_break" and i % 120 > 100:
            step = -abs(step) - 4.0 * unit
        elif shape == "gap" and t.hour == 0 and t.dayofweek == 0:
            step += 40.0 * unit
        elif shape == "range":
            step *= 0.3
        o = px
        px = max(base / 10.0, px + step)
        span = abs(rng.gauss(0.0, 1.5 * unit))
        rows.append(
            {
                "open": round(o, 6),
                "high": round(max(o, px) + span, 6),
                "low": round(min(o, px) - span, 6),
                "close": round(px, 6),
                "tick_volume": rng.randint(100, 5000),
                "spread": rng.randint(1, 30),
                "real_volume": 0,
            }
        )
    return pd.DataFrame(rows, index=idx)


def signal_record(sig: Any) -> Any:
    """One signal as plain data: every field it carries, floats to 8 places, times as text."""
    import dataclasses

    if dataclasses.is_dataclass(sig) and not isinstance(sig, type):
        raw: Any = dataclasses.asdict(sig)
    elif isinstance(sig, dict):
        raw = dict(sig)
    elif hasattr(sig, "__dict__"):
        raw = dict(vars(sig))
    else:
        raw = sig

    def plain(v: Any) -> Any:
        if isinstance(v, dict):
            return {str(k): plain(x) for k, x in sorted(v.items(), key=lambda kv: str(kv[0]))}
        if isinstance(v, list | tuple):
            return [plain(x) for x in v]
        if isinstance(v, bool) or v is None or isinstance(v, str):
            return v
        if isinstance(v, int):
            return int(v)
        try:
            f = float(v)
        except (TypeError, ValueError):
            return str(v)
        return None if f != f else round(f, 8)

    return plain(raw)


# ---------------------------------------------------------------------------------------------
# FIXTURE INPUTS (2026-11-13). An input-hungry family (carry, the macro and COT families, the
# peer/factor/driver families, world_macro_state, ensemble, regime_split) returns [] without its
# inputs, so on bare bars its changed lines never ran and the file stayed UNMEASURED. The loaders
# those families and `family_inputs.resolve` read (the parquet store, FRED, COT, the tape, the swap
# terms, the world series store) are not on the runner, so they are REPLACED, identically on both
# trees, by deterministic series shaped like what each returns. Every series is a function of its
# own name and the index it is asked for, never of the tree. The resolver itself and the families
# run unpatched: only the bottom-most reads are fixtures. A loader the tree does not have is
# skipped (its family then refuses, the same on both trees, and its lines stay UNMEASURED).


def _det(name: str) -> random.Random:
    return random.Random(f"fixture:{name}")  # noqa: S311 -- a fixture series, not a secret


def fixture_daily(name: str, index: Any, lo: float = 0.0, hi: float = 1.0) -> Any:
    """A daily-stepped series on `index`, deterministic in (name, day)."""
    import zlib

    import pandas as pd

    days = pd.DatetimeIndex(index).floor("D")
    vals = [
        lo + (hi - lo) * ((zlib.crc32(f"{name}:{d.date()}".encode()) % 1000) / 999.0) for d in days
    ]
    return pd.Series(vals, index=index, dtype=float)


def fixture_weekly_cot(symbol: str, end: Any) -> Any:
    """Raw weekly COT rows (report_date, commercial and non-commercial longs and shorts) and the
    normalised `net` column, from 2015 to `end`: the two shapes the COT readers return."""
    import pandas as pd

    rng = _det(f"cot:{symbol}")
    dates = pd.date_range("2015-01-02", pd.Timestamp(end).tz_localize(None), freq="W-FRI")
    rows, net = [], 0.0
    for d in dates:
        net = max(-1.0, min(1.0, net + rng.gauss(0.0, 0.08)))
        cl, cs = 100_000 + rng.randint(0, 50_000), 100_000 + rng.randint(0, 50_000)
        nl, ns = 80_000 + rng.randint(0, 60_000), 80_000 + rng.randint(0, 60_000)
        rows.append({"report_date": d.tz_localize("UTC") + pd.Timedelta(days=-3),
                     "comm_positions_long_all": cl, "comm_positions_short_all": cs,
                     "noncomm_positions_long_all": nl, "noncomm_positions_short_all": ns,
                     "net": net})  # fmt: skip
    frame = pd.DataFrame(rows, index=pd.DatetimeIndex(dates, tz="UTC"))
    return frame


def fixture_world_series(key: str) -> Any:
    """A monthly official statistic for `key`, 2010 onwards: a slow cycle plus noise, stamped on
    the instant it became knowable (the store's own shape)."""
    import math

    import pandas as pd

    rng = _det(f"world:{key}")
    idx = pd.date_range("2010-01-15", "2026-10-15", freq="MS", tz="UTC") + pd.Timedelta(days=14)
    vals = [math.sin(i / 7.0) * 2.0 + rng.gauss(0.0, 0.6) for i in range(len(idx))]
    return pd.Series(vals, index=idx, dtype=float, name=key)


def fixture_swap_terms(symbol: str) -> dict[str, Any] | None:
    """Recorded contract terms in POINTS mode (the mode `swap_money_per_lot` resolves): a
    positive long carry on every symbol whose name sorts its legs one way, short otherwise.
    No symbol has no terms (the store has no row for it), as on the box."""
    if not str(symbol or "").strip():
        return None
    up = sum(map(ord, symbol.upper())) % 2 == 0
    price = symbol_price(symbol)
    return {"symbol": symbol.upper(), "swap_mode": 1, "swap_long": 6.5 if up else -9.0,
            "swap_short": -9.0 if up else 6.5, "point": 0.001 if price > 20 else 0.00001,
            "contract_size": 100.0 if price > 500 else 100_000.0, "digits": 5}  # fmt: skip


class Fixtures:
    """The fixture loaders, around one chart end: every peer, factor and driver frame ends where
    the primary frame does, on the chart it is asked for, so the families' inner joins keep it."""

    def __init__(self, end: Any, n: int) -> None:
        self.end, self.n = end, n
        self.installed: list[str] = []

    def bars(self, symbol: str, timeframe: str = "H1") -> Any:
        return signal_frame(str(symbol), "peer", end=self.end, n=self.n, tf=str(timeframe))

    def macro(self, index: Any, name: str | None = None) -> Any:
        return fixture_daily(f"macro:{name}", index)

    def tape(self, symbol: str, index: Any, timeframe: str = "H1") -> tuple[Any, Any]:
        return (fixture_daily(f"spread:{symbol}", index, 0.5, 3.0),
                fixture_daily(f"flow:{symbol}", index, -1.0, 1.0))  # fmt: skip

    def cot(self, symbol: str | None = None) -> Any:
        return fixture_weekly_cot(str(symbol), self.end)[["net"]]

    def raw_cot(self, symbol: str) -> Any:
        return fixture_weekly_cot(str(symbol), self.end).reset_index(drop=True)

    def events(self) -> Any:
        import pandas as pd

        return pd.date_range("2024-01-05 13:30", pd.Timestamp(self.end).tz_localize(None),
                             freq="W-FRI", tz="UTC")  # fmt: skip

    def install(self) -> list[str]:
        """Point every loader the tree has at its fixture. Returns what was installed."""
        import importlib

        plan = (
            ("research.orthogonal_sweep", "_bars", self.bars),
            ("research.orthogonal_sweep", "_macro_series", self.macro),
            ("research.orthogonal_sweep", "_cot_frame", self.cot),
            ("research.orthogonal_sweep", "_tape_series", self.tape),
            ("research.orthogonal_sweep", "_event_index", self.events),
            ("mt5desk.families_orthogonal", "_swap_terms", fixture_swap_terms),
            ("mt5desk.data", "load_cot", self.raw_cot),
            ("research.world_dataset_hunter", "raw_world_series", fixture_world_series),
        )
        for mod_name, attr, fn in plan:
            try:
                mod = importlib.import_module(mod_name)
            except Exception:  # a tree without the loader: its families refuse alike
                continue
            if hasattr(mod, attr):
                setattr(mod, attr, fn)
                self.installed.append(f"{mod_name}.{attr}")
        return self.installed


#: The price shapes a certificate is run on (its own symbol, its own chart, both sides).
CERT_SHAPES = ("up_break", "wide")
#: A certificate's frame: long enough for the slowest warm-ups (an ensemble wants 120 days of
#: bars, a regime label a trailing year of days); the fixture peers are longer still.
CERT_BARS = 6000
FIXTURE_BARS = 8000


def fixture_runner(fixtures: Fixtures) -> Any:
    """An ensemble's member runner when `family_inputs.resolve` cannot build the real one (it
    reads data/universe/, which the runner does not check out): each member is run through the
    desk's own resolver and call, on the member's fixture bars."""

    def run(symbol: str, family: str, params: dict[str, Any], df: Any) -> list[Any]:
        from mt5desk import executables, family_call, family_inputs

        fn = executables.resolve_family(family)
        if fn is None:
            return []
        call = family_inputs.runtime_call_params(family, params)
        extra, _why = family_inputs.resolve(symbol, family, params, df)
        if extra is None:
            return []
        call.update(extra)
        return family_call.signals(fn, df, side=1, params=call)

    return run


def cert_call(
    fixtures: Fixtures, family: str, symbol: str, params: dict[str, Any], df: Any, side: int
) -> tuple[list[Any], dict[str, Any]]:
    """One certified cell, called the way the gateway and the forward clock call it: params
    stripped of identity keys, inputs rebuilt by `family_inputs.resolve` (whose loaders are the
    fixtures), then `family_call.signals`. Returns (signals, how the inputs were built)."""
    from mt5desk import executables, family_call, family_inputs

    fn = executables.resolve_family(family)
    if fn is None:
        raise LookupError(f"no constructor for {family}")
    call = family_inputs.runtime_call_params(family, params)
    extra, why = family_inputs.resolve(symbol, family, params, df)
    how = {"inputs": "resolve", "why": str(why)[:80]}
    if extra is None and family == "ensemble":
        extra, how = {"_runner": fixture_runner(fixtures)}, {"inputs": "fixture_runner"}
    if extra is None:
        return [], {"inputs": "refused", "why": str(why)[:80]}
    call.update(extra)
    return family_call.signals(fn, df, side=side, params=call), how


class _CallTimeout(BaseException):
    """Raised by the alarm inside a family call: a BaseException, so no family's own
    `except Exception` can swallow it."""


def signal_main(tree: Path, spec: dict[str, Any], out_path: Path) -> int:
    import hashlib
    import os
    import signal as _signal

    stub = types.ModuleType("MetaTrader5")
    stub.__getattr__ = lambda name: mock.MagicMock(name="MetaTrader5." + name)  # type: ignore[method-assign]
    sys.modules["MetaTrader5"] = stub
    sys.path[:0] = [str(tree), str(tree / "desks" / "mt5")]
    os.environ.pop("QUANT_PROP_ACCOUNT", None)
    root = str(tree) + os.sep
    traced = {str((tree / p).resolve()): p for p in spec.get("trace") or []}
    lines: dict[str, dict[str, set[int]]] = {}
    bucket: dict[str, Any] = {"key": "<import>"}

    def local(frame: Any, event: str, arg: Any) -> Any:
        if event == "line":
            rel = traced[frame.f_code.co_filename]
            lines.setdefault(bucket["key"], {}).setdefault(rel, set()).add(frame.f_lineno)
        return local

    def hook(frame: Any, event: str, arg: Any) -> Any:
        if frame.f_code.co_filename in traced:
            return local(frame, event, arg)
        return None

    def on_alarm(signum: int, frame: Any) -> None:
        raise _CallTimeout

    _signal.signal(_signal.SIGALRM, on_alarm)
    import pandas  # noqa: F401 -- imported outside the trace: not repository code

    sys.settrace(hook)
    try:
        from mt5desk import executables, families, family_call

        names = sorted(set(families.live_family_names()))
        fixtures = Fixtures(SIGNAL_END, FIXTURE_BARS)
        installed = fixtures.install()
    finally:
        sys.settrace(None)
    frames = {f"{s}/{sh}": signal_frame(s, sh) for s in SIGNAL_SYMBOLS for sh in SIGNAL_SHAPES}
    hunt16 = executables.hunt16_families()
    calls: dict[str, Any] = {}

    def run(key: str, fn: Any) -> None:
        bucket["key"] = key
        _signal.setitimer(_signal.ITIMER_REAL, SIGNAL_CALL_S)
        sys.settrace(hook)
        try:
            got = fn()
            sigs, how = got if isinstance(got, tuple) else (got, None)
            rec = [signal_record(x) for x in sigs]
            # how a certified cell's inputs were built is part of what it decided
            blob = json.dumps([how, rec] if how is not None else rec, sort_keys=True, default=str)
            calls[key] = {
                "n": len(rec),
                "digest": hashlib.sha256(blob.encode()).hexdigest(),
                "first": rec[:2],
            }
            if how is not None:
                calls[key]["how"] = how
        except _CallTimeout:
            calls[key] = {"timeout": True}
            lines.pop(key, None)
        except Exception as exc:  # the verdict IS the exception type: compared, lines dropped
            calls[key] = {"error": type(exc).__name__, "detail": str(exc)[:160]}
            lines.pop(key, None)
        finally:
            sys.settrace(None)
            _signal.setitimer(_signal.ITIMER_REAL, 0)

    for name in names:
        resolvers: dict[str, Any] = {}
        for tag, get in (
            ("gateway", executables.resolve_family),
            ("executor", families.get_family_func),
        ):
            try:
                fn = get(name)
            except Exception as exc:
                calls[f"{name}|{tag}|resolve"] = {"error": type(exc).__name__}
                continue
            if fn is None:
                calls[f"{name}|{tag}|resolve"] = {"error": "None"}
                continue
            if any(fn is f for f in resolvers.values()):
                continue  # the same constructor: one set of calls
            resolvers[tag] = fn
        for tag, fn in resolvers.items():
            is_h16 = hunt16.get(name) is fn
            param_sets: list[dict[str, Any]] = [{}]
            if not is_h16:
                try:
                    grid = families.get_param_grid(name) or {}
                    first = {k: v[0] for k, v in grid.items() if isinstance(v, list) and v}
                except Exception:
                    first = {}
                if first:
                    param_sets.append(first)
            for fk, df in frames.items():
                for side in (1, -1):
                    for params in param_sets:
                        pkey = json.dumps(params, sort_keys=True, default=str)
                        key = f"{name}|{tag}|{fk}|{side}|{pkey}"
                        if is_h16:
                            run(
                                key,
                                lambda f=fn, d=df, s=side: family_call.hunt16_signals(
                                    f, d.copy(), s
                                ),
                            )
                        else:
                            run(
                                key,
                                lambda f=fn, d=df, s=side, p=params: family_call.signals(
                                    f, d.copy(), side=s, params=dict(p)
                                ),
                            )

    # THE CERTIFIED CELLS (2026-11-13): each family with the params its certificates carry
    # (`certs`, read by the parent from the BASE's books, so both trees run the same cells), on
    # its own symbol and chart, with its inputs rebuilt through `family_inputs.resolve` from the
    # fixture loaders. The bare calls above hand an input-hungry family nothing, so it returned []
    # and its changed lines never ran.
    for i, cert in enumerate(spec.get("certs") or []):
        family, sym = str(cert.get("family")), str(cert.get("symbol") or "EURUSD")
        params = dict(cert.get("params") or {})
        tf = str(params.get("timeframe") or "H1").upper()
        try:
            from mt5desk import executables as _ex
            from mt5desk.family_call import accepts_side

            fn0 = _ex.resolve_family(family)
            # a family that takes no side is only ever traded LONG (the gateway refuses the
            # SHORT row by name, `wrong_side`), so its SHORT call would only re-raise TypeError
            sides = (1, -1) if fn0 is not None and accepts_side(fn0) else (1,)
        except Exception:
            sides = (1, -1)
        for shape in CERT_SHAPES:
            df = signal_frame(sym, shape, tf=tf, n=CERT_BARS)
            for side in sides:
                key = f"{family}|cert{i}|{sym}@{tf}/{shape}|{side}"
                run(
                    key,
                    lambda f=family, sy=sym, p=params, d=df, s=side: cert_call(
                        fixtures, f, sy, p, d.copy(), s
                    ),
                )

    files = (getattr(m, "__file__", None) for m in list(sys.modules.values()))
    imported = sorted(
        {str(Path(f).resolve()) for f in files if f and str(Path(f).resolve()).startswith(root)}
    )
    out_path.write_text(
        json.dumps(
            {
                "names": names,
                "fixtures": installed,
                "calls": calls,
                "lines": {k: {f: sorted(v) for f, v in d.items()} for k, d in lines.items()},
                "imported": imported,
            },
            default=str,
        ),
        "utf-8",
    )
    return 0


# ---------------------------------------------------------------------------------------------
# THE FUSION GATEWAY LEG (2026-11-13). The scenario legs replay the E8 book and the FTMO lane;
# the Fusion gateway (`mt5desk/gateway.py`, and `fusion_rails`, `order_door`, `cross_account`,
# `decision_core` as it calls them) turns sleeves into orders on the live account and was money
# path the replay never ran. This leg runs the gateway's own family lane exactly as `main` drives
# it -- `resolve_family_order` for every family sleeve (pricing it before the cap), the heat cap
# (`cap_by_heat`), then `run_family_sleeves`, ARMED, against a FAKE terminal whose `order_send`
# only records -- for a fixed set of sleeves (the certified cells the parent read from the base's
# books, sized at a fixed fraction), over a fixed run of passes on a frozen clock, from two
# account states (flat; holding a long and a short). What each pass intended (every resolved
# plan, what the cap admitted, every request that reached `order_send`) is the pass's decision.
#
# NOTHING TOUCHES THE TREE: the leg runs on a COPY of the files the CI job checks out, in its
# working directory, with MT5_DESK_ROOT pointed at the copy, so every state, journal and ledger
# file the gateway writes lands in the copy. Lines are traced in the copy and reported under
# their repository paths, with the same per-pass buckets the signal leg uses.

#: What the CI job checks out (release-gates.yml): the copy holds exactly this, here and there.
GATEWAY_COPY = (
    "libs", "desks/mt5/mt5desk", "desks/mt5/prop", "desks/mt5/research/*.py", "desks/mt5/*.py",
    "desks/mt5/data/*.json", "desks/mt5/reports/*.json", "data/*.json", "pyproject.toml",
)  # fmt: skip
#: Passes per account state, an hour apart, ending at the parent's anchor (+10 minutes).
GATEWAY_PASSES = 24
#: The fixed account the fake terminal reports, and the fraction every fixture sleeve asks.
GATEWAY_EQUITY = 100_000.0
GATEWAY_RISK_FRAC = 0.005
#: One pass's budget (every sleeve, the cap and the executor).
GATEWAY_PASS_S = 240


def copy_tree(tree: Path, dest: Path) -> Path:
    """The CI job's file set of `tree`, copied to `dest` (no caches)."""
    import glob
    import shutil

    for pat in GATEWAY_COPY:
        for src in sorted(glob.glob(str(tree / pat))):
            rel = Path(src).relative_to(tree)
            to = dest / rel
            if Path(src).is_dir():
                shutil.copytree(src, to, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))  # fmt: skip
            else:
                to.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, to)
    return dest


class _Unknown:
    """A terminal attribute the fake does not model: a stable constant that, called, answers
    None (the terminal's own "unavailable"). Its text never carries an address, so it cannot
    make two identical trees disagree."""

    def __init__(self, name: str) -> None:
        import zlib

        self.name, self.value = name, 900_000 + zlib.crc32(name.encode()) % 100_000

    def __call__(self, *a: Any, **k: Any) -> None:
        return None

    def __int__(self) -> int:
        return self.value

    def __index__(self) -> int:
        return self.value

    def __eq__(self, other: object) -> bool:
        return other is self or other == self.value

    def __hash__(self) -> int:
        return self.value

    def __repr__(self) -> str:
        return f"<mt5.{self.name}>"


class FusionTerminal:
    """A fake Fusion terminal: one fixed account, fixed contract terms per symbol, the scenario's
    positions, a tick and closed bars on the frozen clock. `order_send` records and answers DONE;
    nothing leaves the process."""

    TIMEFRAMES: ClassVar[dict[str, int]] = {
        "M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 16385, "H4": 16388, "D1": 16408,
    }  # fmt: skip
    CONSTANTS: ClassVar[dict[str, int]] = {
        "ORDER_TYPE_BUY": 0, "ORDER_TYPE_SELL": 1, "ORDER_TYPE_BUY_LIMIT": 2,
        "ORDER_TYPE_SELL_LIMIT": 3, "ORDER_TYPE_BUY_STOP": 4, "ORDER_TYPE_SELL_STOP": 5,
        "TRADE_ACTION_DEAL": 1, "TRADE_ACTION_PENDING": 5, "TRADE_ACTION_SLTP": 6,
        "TRADE_ACTION_MODIFY": 7, "TRADE_ACTION_REMOVE": 8, "TRADE_ACTION_CLOSE_BY": 10,
        "ORDER_TIME_GTC": 0, "ORDER_TIME_DAY": 1, "ORDER_TIME_SPECIFIED": 2,
        "ORDER_FILLING_FOK": 0, "ORDER_FILLING_IOC": 1, "ORDER_FILLING_RETURN": 2,
        "POSITION_TYPE_BUY": 0, "POSITION_TYPE_SELL": 1, "DEAL_ENTRY_IN": 0, "DEAL_ENTRY_OUT": 1,
        "DEAL_TYPE_BUY": 0, "DEAL_TYPE_SELL": 1, "TRADE_RETCODE_DONE": 10009,
        "TRADE_RETCODE_PLACED": 10008, "SYMBOL_TRADE_MODE_FULL": 4,
        "ACCOUNT_TRADE_MODE_DEMO": 0, "ACCOUNT_TRADE_MODE_REAL": 2,
        "SYMBOL_FILLING_FOK": 1, "SYMBOL_FILLING_IOC": 2,
    }  # fmt: skip

    def __init__(self, clock: dict[str, Any], positions: list[dict[str, Any]]) -> None:
        self.clock, self.positions, self.sent = clock, positions, []
        self.last_close: dict[tuple[int, str], float] = {}

    def module(self) -> types.ModuleType:
        mod = types.ModuleType("MetaTrader5")
        for k, v in self.CONSTANTS.items():
            setattr(mod, k, v)
        for k, v in self.TIMEFRAMES.items():
            setattr(mod, f"TIMEFRAME_{k}", v)
        for k in dir(self):
            if not k.startswith("_") and callable(getattr(self, k)) and k != "module":
                setattr(mod, k, getattr(self, k))
        mod.__getattr__ = _Unknown  # type: ignore[method-assign]
        return mod

    def _now(self) -> Any:
        return self.clock["now"]

    def initialize(self, *a: Any, **k: Any) -> bool:
        return True

    def shutdown(self) -> None:
        return None

    def last_error(self) -> tuple[int, str]:
        return (1, "ok")

    def terminal_info(self) -> Any:
        return types.SimpleNamespace(connected=True, trade_allowed=True, name="Fusion Replay",
                                     company="Fusion Markets Replay", path="replay")  # fmt: skip

    def account_info(self) -> Any:
        return types.SimpleNamespace(login=7700001, server="FusionMarkets-Replay", currency="USD",
                                     equity=GATEWAY_EQUITY, balance=GATEWAY_EQUITY,
                                     margin=0.0, margin_free=GATEWAY_EQUITY, margin_level=0.0,
                                     leverage=500, trade_mode=2, trade_allowed=True,
                                     name="replay", company="Fusion Markets Replay")  # fmt: skip

    def symbol_info(self, symbol: str) -> Any:
        px = symbol_price(symbol)
        big = px > 20
        point = 0.01 if big else 0.00001
        return types.SimpleNamespace(
            name=symbol, visible=True, select=True, digits=2 if big else 5, point=point,
            trade_contract_size=100.0 if px > 500 else 100_000.0, volume_min=0.01,
            volume_step=0.01, volume_max=50.0, trade_tick_size=point,
            trade_tick_value=1.0, trade_tick_value_loss=1.0,
            trade_tick_value_profit=1.0, currency_profit="USD", currency_base=symbol[:3],
            currency_margin=symbol[:3], spread=12, trade_stops_level=0, trade_freeze_level=0,
            filling_mode=3, trade_mode=4, swap_mode=1, swap_long=-3.0, swap_short=1.0,
            bid=self._mid(symbol) - point * 6, ask=self._mid(symbol) + point * 6,
            trade_calc_mode=0, margin_initial=0.0,
        )  # fmt: skip

    def symbols_get(self, *a: Any, **k: Any) -> list[Any]:
        return [self.symbol_info(s) for s in ("EURUSD", "XAUUSD", "GBPUSD", "USDJPY", "AUDJPY")]

    def symbol_select(self, symbol: str, on: bool = True) -> bool:
        return True

    def _frame(self, symbol: str, tf: str, n: int) -> Any:
        shape = SIGNAL_SHAPES[self.clock["pass"] % len(SIGNAL_SHAPES)]
        return signal_frame(symbol, shape, end=self._now(), n=n, tf=tf)

    def _mid(self, symbol: str) -> float:
        """The close of the last bar this pass served for `symbol` (any chart), so the tick
        agrees with the frame the signal was computed on; H1 before any was served."""
        got = self.last_close.get((self.clock["pass"], symbol))
        return got if got is not None else float(self._frame(symbol, "H1", 50)["close"].iloc[-1])

    def symbol_info_tick(self, symbol: str) -> Any:
        info_point = 0.01 if symbol_price(symbol) > 20 else 0.00001
        mid = self._mid(symbol)
        t = int(self._now().timestamp())
        return types.SimpleNamespace(time=t, time_msc=t * 1000, bid=round(mid - 6 * info_point, 6),
                                     ask=round(mid + 6 * info_point, 6), last=mid,
                                     volume=1)  # fmt: skip

    def copy_rates_from_pos(self, symbol: str, timeframe: int, start: int, count: int) -> Any:
        import numpy as np

        tf = next((k for k, v in self.TIMEFRAMES.items() if v == timeframe), "H1")
        df = self._frame(symbol, tf, int(count) + int(start))
        if start:
            df = df.iloc[: -int(start)]
        if len(df):
            self.last_close[(self.clock["pass"], symbol)] = float(df["close"].iloc[-1])
        rec = np.zeros(len(df), dtype=[("time", "<i8"), ("open", "<f8"), ("high", "<f8"),
                                       ("low", "<f8"), ("close", "<f8"), ("tick_volume", "<u8"),
                                       ("spread", "<i4"), ("real_volume", "<u8")])  # fmt: skip
        rec["time"] = (df.index.asi8 // 10**9).astype("int64")
        for c in ("open", "high", "low", "close", "tick_volume", "spread", "real_volume"):
            rec[c] = df[c].to_numpy()
        return rec

    def copy_rates_range(self, symbol: str, timeframe: int, a: Any, b: Any) -> Any:
        return self.copy_rates_from_pos(symbol, timeframe, 0, 400)

    def positions_get(
        self, symbol: str | None = None, group: str | None = None, ticket: int | None = None
    ) -> tuple[Any, ...]:
        out = [types.SimpleNamespace(**p) for p in self.positions]
        if symbol:
            out = [p for p in out if p.symbol == symbol]
        if ticket:
            out = [p for p in out if p.ticket == ticket]
        return tuple(out)

    def positions_total(self) -> int:
        return len(self.positions)

    def orders_get(self, *a: Any, **k: Any) -> tuple[Any, ...]:
        return ()

    def orders_total(self) -> int:
        return 0

    def history_deals_get(self, *a: Any, **k: Any) -> tuple[Any, ...]:
        return ()

    def history_orders_get(self, *a: Any, **k: Any) -> tuple[Any, ...]:
        return ()

    def order_calc_margin(self, typ: int, symbol: str, lot: float, price: float) -> float:
        return float(lot) * symbol_price(symbol) * 1000.0 / 500.0

    def order_calc_profit(self, typ: int, symbol: str, lot: float, a: float, b: float) -> float:
        size = 100.0 if symbol_price(symbol) > 500 else 100_000.0
        return (b - a if typ == 0 else a - b) * size * float(lot)

    def order_check(self, req: dict[str, Any]) -> Any:
        return types.SimpleNamespace(retcode=0, comment="Done", margin_free=GATEWAY_EQUITY)

    def order_send(self, req: dict[str, Any]) -> Any:
        self.sent.append(dict(req))
        n = 50_000 + len(self.sent)
        return types.SimpleNamespace(retcode=10009, order=n, deal=n, price=req.get("price"),
                                     volume=req.get("volume"), comment="replay",
                                     request_id=n)  # fmt: skip


def gateway_positions(state: str, anchor: Any) -> list[dict[str, Any]]:
    """The account state's open positions (none, or a long EURUSD and a short XAUUSD that no
    fixture sleeve owns), opened a day before the anchor."""
    if state == "flat":
        return []
    t = int(anchor.timestamp()) - 86_400
    return [
        {"ticket": 7001, "identifier": 7001, "symbol": "EURUSD", "type": 0, "volume": 0.05,
         "price_open": 1.1, "sl": 1.095, "tp": 1.11, "price_current": 1.1, "profit": 0.0,
         "swap": 0.0, "magic": 341953, "comment": "replay_other", "time": t,
         "time_msc": t * 1000},
        {"ticket": 7002, "identifier": 7002, "symbol": "XAUUSD", "type": 1, "volume": 0.02,
         "price_open": 4300.0, "sl": 4340.0, "tp": 4240.0, "price_current": 4300.0,
         "profit": 0.0, "swap": 0.0, "magic": 341953, "comment": "replay_other", "time": t,
         "time_msc": t * 1000},
    ]  # fmt: skip


def gateway_sleeves(certs: list[dict[str, Any]], takes_side: Any) -> list[dict[str, Any]]:
    """One LONG family-market sleeve per certified cell, and a SHORT one where the family takes
    a side (`takes_side(family)`), at a fixed fraction (never the allocator's book, which the
    runner does not hold)."""
    out = []
    for i, c in enumerate(certs):
        params = dict(c.get("params") or {})
        for side in ("LONG", "SHORT") if takes_side(str(c["family"])) else ("LONG",):
            out.append({
                "name": f"replay_{c['family']}_{i}_{side[0]}",
                "symbol": str(c.get("symbol") or "EURUSD"), "family": str(c["family"]),
                "params": params, "exec": "family_market", "lot": "auto_ramp",
                "risk_frac": GATEWAY_RISK_FRAC, "status": "LIVE", "side": side,
                "selector": "all", "timeframe": str(params.get("timeframe") or "H1"),
            })  # fmt: skip
    return out


def _takes_side(family: str) -> bool:
    try:
        from mt5desk import executables
        from mt5desk.family_call import accepts_side

        fn = executables.resolve_family(family)
        return fn is not None and bool(accepts_side(fn))
    except Exception:
        return False


class _FROZEN_BASE:
    """Marks the frozen datetime class (installed once per process)."""


def _freeze(root: str, clock: dict[str, Any]) -> None:
    """Every repository module's `datetime` and `time` read the pass's frozen instant."""
    import datetime as _dt
    import time as _time

    real = _dt.datetime.__mro__[1] if issubclass(_dt.datetime, _FROZEN_BASE) else _dt.datetime

    class Frozen(real, _FROZEN_BASE):  # type: ignore[misc,valid-type]
        @classmethod
        def now(cls, tz: Any = None) -> Any:  # type: ignore[override]
            t = clock["now"].to_pydatetime()
            return t.astimezone(tz) if tz is not None else t.replace(tzinfo=None)

        @classmethod
        def utcnow(cls) -> Any:  # type: ignore[override]
            return clock["now"].to_pydatetime().replace(tzinfo=None)

        @classmethod
        def today(cls) -> Any:  # type: ignore[override]
            return cls.now()

    # a module the pass imports lazily (cross_account, fusion_rails) binds the frozen class too
    if not issubclass(_dt.datetime, _FROZEN_BASE):
        _dt.datetime = Frozen  # type: ignore[misc]
    shim = types.SimpleNamespace(
        **{k: getattr(_time, k) for k in dir(_time) if not k.startswith("__")}
    )
    shim.time = lambda: float(clock["now"].timestamp())
    for m in list(sys.modules.values()):
        f = getattr(m, "__file__", None)
        if not isinstance(f, str) or not f.startswith(root):
            continue
        if getattr(m, "datetime", None) in (real, _dt.datetime):
            m.datetime = Frozen  # type: ignore[attr-defined]
        if getattr(m, "time", None) is _time:
            m.time = shim  # type: ignore[attr-defined]


def plan_record(plan: dict[str, Any]) -> dict[str, Any]:
    """A resolved plan as decisions: prose (why, note, basis) and the live objects (sym, tick)
    out; the signal as its record."""
    import datetime as _dt

    drop = {"why", "note", "basis", "sym", "tick", "leg_why", "macro_why", "sep"}
    out = {
        k: str(v) if isinstance(v, _dt.datetime) else signal_record(v)
        for k, v in sorted(plan.items())
        if k not in drop
    }
    if "signal" in plan:
        out["signal"] = signal_record(plan["signal"])
    return out


def gateway_main(tree: Path, spec: dict[str, Any], out_path: Path) -> int:
    import hashlib
    import os
    import signal as _signal
    from collections import Counter

    import pandas as pd

    work = Path.cwd()
    copy = copy_tree(tree, work / "tree")
    desk = copy / "desks" / "mt5"
    (desk / "logs").mkdir(parents=True, exist_ok=True)
    (desk / "data" / "GENERIC_EXEC_ENABLED").write_text("replay", "utf-8")
    os.environ["MT5_DESK_ROOT"] = str(desk)
    # a throwaway account key, so the gateway can stamp the Fusion book it publishes
    key_file = work / "fusion_account_key.hmac"
    key_file.write_text("replay-fusion-gateway-leg".ljust(48, "0"), "utf-8")
    os.environ["QUANT_ACCOUNT_KEY_FILE"] = str(key_file)
    os.environ.pop("QUANT_PROP_ACCOUNT", None)
    anchor = pd.Timestamp(spec["anchor"]).tz_convert("UTC")
    clock: dict[str, Any] = {"now": anchor, "pass": 0}
    term = FusionTerminal(clock, [])
    sys.modules["MetaTrader5"] = term.module()
    sys.path[:0] = [str(copy), str(desk)]
    root = str(copy) + os.sep
    traced = {str((copy / p).resolve()): p for p in spec.get("trace") or []}
    lines: dict[str, dict[str, set[int]]] = {}
    bucket: dict[str, Any] = {"key": "<import>"}

    def local(frame: Any, event: str, arg: Any) -> Any:
        if event == "line":
            rel = traced[frame.f_code.co_filename]
            lines.setdefault(bucket["key"], {}).setdefault(rel, set()).add(frame.f_lineno)
        return local

    def hook(frame: Any, event: str, arg: Any) -> Any:
        if frame.f_code.co_filename in traced:
            return local(frame, event, arg)
        return None

    def on_alarm(signum: int, frame: Any) -> None:
        raise _CallTimeout

    _signal.signal(_signal.SIGALRM, on_alarm)
    fixtures = Fixtures(anchor, FIXTURE_BARS)
    calls: dict[str, Any] = {}
    sys.settrace(hook)
    try:
        from mt5desk import gateway as g

        installed = fixtures.install()
    except Exception as exc:  # compared: a tree whose gateway cannot import says so
        sys.settrace(None)
        calls["gateway|import"] = {"error": type(exc).__name__, "detail": str(exc)[:160]}
        out_path.write_text(json.dumps({"names": [], "calls": calls, "lines": {},
                                        "imported": []}), "utf-8")  # fmt: skip
        return 0
    finally:
        sys.settrace(None)
    sleeves0 = gateway_sleeves(spec.get("certs") or [], _takes_side)
    for state in ("flat", "held"):
        term.positions = gateway_positions(state, anchor)
        st: dict[str, Any] = {"armed": True, "generic": {}, "brackets": {}}
        for k in range(GATEWAY_PASSES):
            clock["now"] = anchor - pd.Timedelta(hours=GATEWAY_PASSES - 1 - k)
            clock["pass"] = k
            _freeze(root, clock)
            # the other accounts' books, fresh at the pass: E8 holds a GBPUSD long when the
            # account is `held` (so the opposite-side fence has something to refuse)
            xacct = desk / "data" / "xacct"
            xacct.mkdir(parents=True, exist_ok=True)
            for acct, syms in (("e8", {"GBPUSD": {"long": True, "short": False}}
                                if state == "held" else {}), ("ftmo", {})):  # fmt: skip
                (xacct / f"{acct}_book.json").write_text(
                    json.dumps(
                        {
                            "account": acct,
                            "covers": "all",
                            "at": clock["now"].isoformat(),
                            "symbols": syms,
                            "account_key": "sha256:0123456789abcdef",
                        }
                    ),
                    "utf-8",
                )
            key = f"gateway|{state}|pass{k}"
            bucket["key"] = key
            sent0 = len(term.sent)
            _signal.setitimer(_signal.ITIMER_REAL, GATEWAY_PASS_S)
            sys.settrace(hook)
            try:
                g.NEW_RISK_OK = True
                g._DESK_STALE = None
                sleeves = [json.loads(json.dumps(s)) for s in sleeves0]
                pending: dict[str, float] = {}
                plans: dict[str, Any] = {}
                for s in sleeves:
                    try:
                        plan = g.resolve_family_order(st, s, GATEWAY_EQUITY, pending=pending)
                    except Exception as exc:
                        plan = {"ok": False, "stage": "resolve_failed",
                                "error": type(exc).__name__}  # fmt: skip
                    if plan.get("ok"):
                        pending[s["symbol"]] = pending.get(s["symbol"], 0.0) + float(
                            plan["side"]
                        ) * float(plan["lot"])
                        s["q_charge"] = g.realised_q(GATEWAY_EQUITY, plan["dist"], s["symbol"],
                                                     plan["sym"], lot=plan["lot"])  # fmt: skip
                        s["dist"] = plan["dist"]
                    else:
                        s["q_charge"] = 0.0
                    s["pending_order"] = plan
                    plans[s["name"]] = plan_record(plan)
                admitted, _note = g.cap_by_heat(sleeves, GATEWAY_EQUITY)
                g.run_family_sleeves(st, admitted, GATEWAY_EQUITY)
                sent = [signal_record(r) for r in term.sent[sent0:]]
                ok = [n for n, p in plans.items() if p.get("ok")]
                rec = {
                    "plans": plans,
                    "admitted": sorted(str(s.get("name")) for s in admitted),
                    "sent": sent,
                }
                blob = json.dumps(rec, sort_keys=True, default=str)
                calls[key] = {
                    "n": len(sent) + len(ok),
                    "digest": hashlib.sha256(blob.encode()).hexdigest(),
                    "first": (sent or [plans[n] for n in ok])[:2],
                    # what the pass's sleeves came to, by stage (for the report, not compared)
                    "stages": dict(
                        sorted(Counter(str(p.get("stage")) for p in plans.values()).items())
                    ),
                }
            except _CallTimeout:
                calls[key] = {"timeout": True}
                lines.pop(key, None)
            except Exception as exc:  # the pass's verdict IS the exception: compared
                calls[key] = {"error": type(exc).__name__, "detail": str(exc)[:160]}
                lines.pop(key, None)
            finally:
                sys.settrace(None)
                _signal.setitimer(_signal.ITIMER_REAL, 0)
    files = (
        f for m in list(sys.modules.values())
        if isinstance(f := getattr(m, "__file__", None), str)
    )  # fmt: skip
    imported = sorted(
        {
            # reported under the TREE's path, so the parent reads it as the tree's file
            str(tree / Path(f).resolve().relative_to(copy.resolve()))
            for f in files
            if f and str(Path(f).resolve()).startswith(str(copy.resolve()) + os.sep)
        }
    )
    out_path.write_text(
        json.dumps(
            {
                "names": [s["name"] for s in sleeves0],
                "fixtures": installed,
                "calls": calls,
                "lines": {k: {f: sorted(v) for f, v in d.items()} for k, d in lines.items()},
                "imported": imported,
            },
            default=str,
        ),
        "utf-8",
    )
    return 0


if __name__ == "__main__":
    if sys.argv[1] == "--gateway":
        raise SystemExit(
            gateway_main(
                Path(sys.argv[2]).resolve(),
                json.loads(Path(sys.argv[3]).read_text()),
                Path(sys.argv[4]),
            )
        )
    if sys.argv[1] == "--signals":
        raise SystemExit(
            signal_main(
                Path(sys.argv[2]).resolve(),
                json.loads(Path(sys.argv[3]).read_text()),
                Path(sys.argv[4]),
            )
        )
    raise SystemExit(
        main(
            Path(sys.argv[1]).resolve(),
            json.loads(Path(sys.argv[2]).read_text()),
            Path(sys.argv[3]),
        )
    )
