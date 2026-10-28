#!/usr/bin/env python3
"""One tree's half of the replay shadow: run the live E8 gold book over one scenario day.

Started by ops/release/replay_shadow.py as `python -I replay_child.py <tree> <scenario.json>
<out.json>` from an empty working directory, once per scenario and per tree. It imports
`prop.e8_gold` from <tree> (the base or the PR head) with the terminal and the venue faked, steps
the server clock through the day, and writes what the book decided at each step. Unarmed, so
nothing it decides is ever sent; there is no terminal, no venue and no key on the runner anyway.

The file names the book writes (state, journal, guard) are pointed into the working directory, so
each scenario starts from a clean day and the two trees never share a file.
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


def main(tree: Path, scenario: dict[str, Any], out_path: Path) -> int:
    stub = types.ModuleType("MetaTrader5")
    stub.__getattr__ = lambda name: mock.MagicMock(name="MetaTrader5." + name)  # type: ignore[method-assign]
    sys.modules["MetaTrader5"] = stub
    sys.path[:0] = [str(tree), str(tree / "desks" / "mt5")]
    import pandas as pd

    work = Path.cwd()
    from prop import e8_gold as g

    for name in SANDBOXED:
        setattr(g, name, work / f"{name.lower()}.json")
    if scenario.get("guard"):  # the guard keys its anchor by the wall clock's server day
        from prop import e8_guard

        guard = {**scenario["guard"], "day": e8_guard.server_day()}
        (work / "guard.json").write_text(json.dumps(guard), "utf-8")
    day = pd.Timestamp(scenario["day"], tz="UTC")
    clock = {"now": day}

    class _Tick:
        @property
        def time(self) -> int:
            return int(clock["now"].timestamp())

    class _Terminal:
        TIMEFRAME_H1 = 16385

        def symbol_info_tick(self, symbol: str) -> Any:
            return _Tick()

        def copy_rates_from_pos(self, symbol: str, tf: int, start: int, count: int) -> list:
            return bars(scenario["shape"], scenario["seed"], day, clock["now"])[-count:]

    class _Api:
        account_id = 31337
        _credentials = {"server": "E8-Replay"}  # noqa: RUF012

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
            return True

        def modify_stop(self, position_id: int, stop: float) -> bool:
            return True

        def close(self, position_id: int, quantity: float = 0) -> bool:
            return True

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
        steps.append({"hour": hour, "doc": doc, "intents": rows, "error": err})
    imported = sorted(
        {
            str(Path(m.__file__).resolve())
            for m in list(sys.modules.values())
            if getattr(m, "__file__", None)
        }
    )
    out_path.write_text(json.dumps({"steps": steps, "imported": imported}, default=str), "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(
        main(
            Path(sys.argv[1]).resolve(),
            json.loads(Path(sys.argv[2]).read_text()),
            Path(sys.argv[3]),
        )
    )
