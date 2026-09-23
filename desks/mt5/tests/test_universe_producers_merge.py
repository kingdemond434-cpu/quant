"""No universe producer may ever shrink the registry.

THE ORIGINAL FAILURE, measured on contabo-mt5 2026-08-27. `fetch_universe.main` built a fresh
`summary` dict from a hardcoded 32-symbol list and wrote it OVER `universe.json`. The trading box
-- the only machine with a terminal, and therefore the only machine that computes forward
evidence -- ended up with a 23-row cost map beside 299 downloaded H1 parquets. `shadow_forward`
then raised `KeyError: 'EURZAR'` on a certified symbol the map did not contain, and the whole
forward pass was discarded every 15 minutes for 5.5 hours.

The registry has three producers on two boxes. The property that has to hold for all of them is
the same one `expand_universe` and `download_all_symbols` already state in their own comments: a
run refreshes what it measured and LEAVES EVERYTHING ELSE ALONE. A missing row is not "no data"
about that symbol -- it is a symbol nothing can cost, which is fatal to the pass that meets it.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]


class _FakeInfo:
    trade_contract_size = 100000.0
    trade_tick_size = 0.001
    trade_tick_value = 0.5
    volume_min = 0.01
    volume_step = 0.01
    spread = 12


def _fake_mt5(offered: set[str]) -> types.ModuleType:
    mod = types.ModuleType("MetaTrader5")
    mod.TIMEFRAME_H1 = 16385

    def copy_rates_range(sym, tf, start, end):
        if sym not in offered:
            return None
        n = 2000
        idx = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
        return pd.DataFrame({
            "time": idx.astype("int64") // 10**9, "open": 1.0, "high": 1.1, "low": 0.9,
            "close": 1.0, "tick_volume": 1, "spread": 14, "real_volume": 0,
        }).to_records(index=False)

    mod.initialize = lambda **kw: True
    mod.terminal_info = lambda: types.SimpleNamespace(name="test")
    mod.account_info = lambda: types.SimpleNamespace(login=1)
    mod.symbol_info = lambda sym: _FakeInfo() if sym in offered else None
    mod.copy_rates_range = copy_rates_range
    mod.last_error = lambda: (0, "")
    return mod


@pytest.fixture
def fetch_universe(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "MetaTrader5", _fake_mt5({"EURUSD", "XAUUSD"}))
    monkeypatch.syspath_prepend(str(DESK / "research"))
    monkeypatch.syspath_prepend(str(DESK))
    sys.modules.pop("fetch_universe", None)
    import fetch_universe as mod
    monkeypatch.setattr(mod, "OUT", tmp_path)
    yield mod
    sys.modules.pop("fetch_universe", None)


def test_a_refresh_never_drops_a_symbol_it_did_not_fetch(fetch_universe, tmp_path) -> None:
    """The exact 2026-08-27 shape: 197 known symbols, a run that can fetch 2, and the cost map
    must still hold 197 afterwards."""
    prior = {f"SYM{i}": {"contract_size": 1.0, "tick_size": 0.1, "tick_value": 1.0,
                         "median_spread_pts": 3.0} for i in range(197)}
    prior["EURUSD"] = {"contract_size": 1.0, "tick_size": 0.1, "tick_value": 1.0,
                       "median_spread_pts": 99.0}
    (tmp_path / "universe.json").write_text(json.dumps(prior), encoding="utf-8")

    fetch_universe.main()

    after = json.loads((tmp_path / "universe.json").read_text("utf-8"))
    assert len(after) >= len(prior), (
        f"registry shrank {len(prior)} -> {len(after)}: a symbol this run did not fetch was "
        f"deleted, which is what made a certified symbol uncostable on the trading box")
    for name in prior:
        assert name in after, f"{name} was dropped by a run that never measured it"
    # What the run DID measure wins.
    assert after["EURUSD"]["median_spread_pts"] == 14.0
    # What it did not measure is untouched.
    assert after["SYM0"]["median_spread_pts"] == 3.0


def test_an_unreadable_registry_refuses_rather_than_rebuilding(fetch_universe, tmp_path) -> None:
    """A read race must not become a blank slate -- the failure mode expand_universe already
    names, arriving here through a different producer."""
    (tmp_path / "universe.json").write_text('{"EURUSD": {"contract', encoding="utf-8")
    fetch_universe.main()
    assert (tmp_path / "universe.json").read_text("utf-8") == '{"EURUSD": {"contract', (
        "an unreadable registry was overwritten from the seed list")


def test_the_seed_list_says_it_is_a_seed() -> None:
    """LAWS §1: a literal list in code is a bootstrap seed, never a limit, and must say so where
    it is declared. The old name `CANDIDATES` read as the universe and was used as one."""
    src = (DESK / "research" / "fetch_universe.py").read_text("utf-8")
    assert "SEED_CANDIDATES" in src, "the seed list is still named as if it were the universe"
    assert "CANDIDATES = [" not in src.replace("SEED_CANDIDATES = [", "")


def test_no_registry_producer_writes_from_a_fresh_dict() -> None:
    """Structural guard over ALL of them: the registry is read, updated, and written back.

    Pinned as a property rather than three instances because the next producer will be the
    fourth, and the desk has already paid for this shape twice (`tick_value` deleted for 197
    symbols on 2026-08-26; the whole registry truncated to 23 on 2026-08-27).
    """
    for rel in ("research/fetch_universe.py", "research/expand_universe.py",
                "scripts/download_all_symbols.py"):
        src = (DESK / rel).read_text("utf-8")
        code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
        assert "universe.json" in src
        reads_first = ("read_text" in code and ("registry" in code or "_merged" in code
                                                or "universe" in code))
        assert reads_first, f"{rel} writes universe.json without reading what is already there"
