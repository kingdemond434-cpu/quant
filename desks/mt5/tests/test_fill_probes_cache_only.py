"""The two daily fill probes never touch a terminal, and the Asia refill measures what it says.

`scripts/entry_timing_probe.py` and `scripts/asia_bracket_refill.py` run once a day as steps of
`daily_cycle.py`. `h1_source.fetch_h1` tries the MT5 terminal first, and `from_mt5` calls
`mt5.shutdown()` and initialize on the live terminals, which a box measurement must never do
(Autonomy 2026-11-25). Pinned here: each script replaces `MetaTrader5` with a module that refuses
every attribute, refuses to run when the real one is already loaded, replaces `from_mt5` on both
`research.h1_source` and `h1_source`, and the original `from_mt5` is never called. Then the
refill itself: the pre-fix engine loads from git and still carries the old trigger fill, and a
gapped Asia stop shows up as a gap day with the two engines disagreeing on it.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import types
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
for _p in (str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk.engine import Costs, Signal  # noqa: E402

SCRIPTS = ("entry_timing_probe", "asia_bracket_refill")


def _load(stem: str):
    spec = importlib.util.spec_from_file_location(f"_t_{stem}", ROOT / "scripts" / f"{stem}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Saved:
    """Snapshot sys.modules['MetaTrader5'] and both h1_source modules' sources; restore after."""

    def __init__(self) -> None:
        self.mt5 = sys.modules.get("MetaTrader5")
        self.mods = []
        for name in ("research.h1_source", "h1_source"):
            mod = importlib.import_module(name)
            self.mods.append((mod, mod.from_mt5, mod.from_cache, list(mod.EXTRA_SOURCES)))

    def restore(self) -> None:
        if self.mt5 is None:
            sys.modules.pop("MetaTrader5", None)
        else:
            sys.modules["MetaTrader5"] = self.mt5
        for mod, mt5, cache, extra in self.mods:
            mod.from_mt5, mod.from_cache = mt5, cache
            mod.EXTRA_SOURCES[:] = extra


@pytest.mark.parametrize("stem", SCRIPTS)
def test_each_probe_refuses_the_terminal_and_never_calls_from_mt5(stem, tmp_path) -> None:
    saved = _Saved()
    calls: list[str] = []
    try:
        sys.modules.pop("MetaTrader5", None)
        for mod, *_ in saved.mods:
            mod.from_mt5 = lambda *a, **k: calls.append("from_mt5")  # type: ignore[assignment]
        p = _load(stem)
        state = tmp_path / "shadow_state.json"
        state.write_text("{}", encoding="utf-8")
        p.SHADOW_STATE = state
        out = tmp_path / "out.json"
        args = ["--out", str(out), "--budget-s", "5"]
        if stem == "entry_timing_probe":
            args += ["--per-tf", "0"]
        assert p.main(args) == 0
        fake = sys.modules["MetaTrader5"]
        assert type(fake).__name__ == "_MT5Forbidden"
        with pytest.raises(Exception, match="refused"):
            fake.initialize()
        with pytest.raises(Exception, match="refused"):
            fake.shutdown()
        # both module objects now refuse the terminal route, and a fetch reaches the cache only
        for name in ("research.h1_source", "h1_source"):
            mod = importlib.import_module(name)
            assert mod.from_mt5("XAUUSD", datetime(2026, 1, 1, tzinfo=UTC)) is None
            mod.fetch_h1("NO_SUCH_SYMBOL", datetime(2026, 1, 1, tzinfo=UTC))
        assert calls == []                                   # the real route was never entered
        doc = json.loads(out.read_text(encoding="utf-8"))
        assert doc["bar_source"]["mode"].startswith("CACHE_ONLY")
    finally:
        saved.restore()


@pytest.mark.parametrize("stem", SCRIPTS)
def test_each_probe_exits_when_the_real_terminal_module_is_loaded(stem, tmp_path) -> None:
    saved = _Saved()
    try:
        sys.modules["MetaTrader5"] = types.ModuleType("MetaTrader5")      # a "real" one
        p = _load(stem)
        with pytest.raises(SystemExit, match="MetaTrader5 already imported"):
            p.main(["--out", str(tmp_path / "x.json")])
        assert not (tmp_path / "x.json").exists()
    finally:
        saved.restore()


def test_both_probes_are_daily_steps_with_their_own_process() -> None:
    import daily_cycle
    names = [n for n, _ in daily_cycle.STEPS]
    for stem in SCRIPTS:
        assert stem in names
        # own process: the chain's shadow step imports MetaTrader5, which the guard refuses
        assert stem in daily_cycle.STEP_WALL_S
        assert daily_cycle.STEP_WALL_S[stem] > daily_cycle.PROBE_BUDGET_S
    assert names.index("shadow") < names.index("entry_timing_probe")


def _gapped_asia() -> tuple[pd.DataFrame, list[Signal]]:
    """A buy stop at 2010 that the next bar OPENS above (2015), then a drift to the time exit."""
    idx = pd.date_range("2026-10-01 06:00", periods=12, freq="1h", tz="UTC")
    rows = ([(2000.0, 2001.0, 1999.0, 2000.0)] * 2 + [(2015.0, 2016.0, 2012.0, 2014.0)]
            + [(2014.0, 2015.0, 2013.0, 2014.0)] * 9)
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    sig = Signal(time=idx[1], side=1, stop=1990.0, target=2050.0, ttl_bars=4, tag="asia",
                 trigger=2010.0, wait_bars=4)
    return df, [sig]


def test_the_pre_fix_engine_loads_from_git_and_keeps_the_old_trigger_fill() -> None:
    p = _load("asia_bracket_refill")
    old, why = p.load_engine_at(p.PRE_FIX_REV)
    if old is None and "git show" in why:
        pytest.skip(f"no git history for {p.PRE_FIX_REV} in this checkout: {why}")
    assert old is not None, why
    assert "FILL_RULES" not in vars(old)
    df, sigs = _gapped_asia()
    free = Costs(spread_per_lot=0.0, commission_per_lot=0.0, contract_oz=100.0)
    assert old.run_backtest(df, sigs, free).trades[0].entry == pytest.approx(2010.0)
    from mt5desk.engine import run_backtest
    assert run_backtest(df, sigs, free).trades[0].entry == pytest.approx(2015.0)


def test_a_gapped_asia_stop_is_a_gap_day_and_the_engines_disagree(monkeypatch) -> None:
    p = _load("asia_bracket_refill")
    old, why = p.load_engine_at(p.PRE_FIX_REV)
    if old is None and "git show" in why:
        pytest.skip(f"no git history for {p.PRE_FIX_REV} in this checkout: {why}")
    df, sigs = _gapped_asia()
    costs = Costs(spread_per_lot=10.0, commission_per_lot=0.0, contract_oz=100.0)
    monkeypatch.setattr(p, "rebuild", lambda key, row, meta: (df, sigs, costs, ""))
    from mt5desk.engine import run_backtest
    st = {"forward_start": "2026-10-01T00:00:00+00:00", "broker_offset_h": 0.0, "n": 1}
    row = ("XAUUSD", "asia", {"rr": 2.0}, "session_range_breakout", "LONG")
    rec = p.refill_clock("XAUUSD.asia", st, row, {}, old, run_backtest)
    assert rec["status"] == "MEASURED"
    assert rec["gap_days"] == 1 and rec["gap_dates"] == ["2026-10-01"]
    assert rec["old"]["n"] == rec["fixed"]["n"] == 1
    # bought at the 2015 open, not the 2010 trigger: the fix can only lower a gapped buy's R
    assert rec["delta_exp_r"] < 0
