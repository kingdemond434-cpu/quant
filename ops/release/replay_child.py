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
from typing import Any
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


def signal_frame(symbol: str, shape: str) -> Any:
    """SIGNAL_BARS H1 bars for `symbol` in `shape`, deterministic in (symbol, shape), with the
    columns a terminal's rates carry (tick_volume, spread, real_volume)."""
    import pandas as pd

    rng = random.Random(f"signal:{symbol}:{shape}")  # noqa: S311 -- a price path, not a secret
    base = SIGNAL_SYMBOLS[symbol]
    unit = base / 1000.0
    idx = pd.date_range(end=pd.Timestamp(SIGNAL_END, tz="UTC"), periods=SIGNAL_BARS, freq="h")
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
            sigs = fn()
            rec = [signal_record(x) for x in sigs]
            blob = json.dumps(rec, sort_keys=True, default=str)
            calls[key] = {
                "n": len(rec),
                "digest": hashlib.sha256(blob.encode()).hexdigest(),
                "first": rec[:2],
            }
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

    files = (getattr(m, "__file__", None) for m in list(sys.modules.values()))
    imported = sorted(
        {str(Path(f).resolve()) for f in files if f and str(Path(f).resolve()).startswith(root)}
    )
    out_path.write_text(
        json.dumps(
            {
                "names": names,
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
