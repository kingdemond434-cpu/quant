"""One executable cell, one identity: a param the family never reads is a SPELLING (Auditor ruling
2026-11-04 on alias certificates -- `CHFNOK.carry` under input_symbol eBay, GBPJPY and none read
identical exp and n). Every `IGNORED_INPUTS` entry is pinned against the REAL
`external_gauntlet.build_cell` and the runtime call shape: both spellings must hand the family the
identical call, or the entry is wrong."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK / "research"), str(_DESK / "scripts"), str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cell_equivalence as E  # noqa: E402
from desks.mt5.scripts import external_gauntlet as G  # noqa: E402

ALIASES = {"input_symbol": "EBAY", "input_source": "somewhere_else", "symbol": "GBPJPY"}


@pytest.fixture(scope="module")
def bars() -> pd.DataFrame:
    rng = np.random.default_rng(3)
    idx = pd.date_range("2024-01-01", periods=24 * 60, freq="h", tz="UTC")
    close = 1.1 + np.cumsum(rng.normal(0, 0.001, len(idx)))
    return pd.DataFrame({"open": np.r_[close[0], close[:-1]], "high": close + 0.001,
                         "low": close - 0.001, "close": close,
                         "tick_volume": rng.integers(50, 500, len(idx))}, index=idx)


def _call_seen(family: str, params: dict, bars: pd.DataFrame, monkeypatch) -> dict:
    """What the family is called with when the gauntlet builds `params`."""
    from mt5desk import families
    from mt5desk import family_inputs as fi
    from research import orthogonal_sweep as osw
    seen: list[dict] = []

    def rec(df, **kw):
        seen.append({k: (tuple(np.asarray(v, dtype=float)) if isinstance(v, pd.Series) else v)
                     for k, v in kw.items()})
        return []

    monkeypatch.setattr(E, "_FN_CACHE", {})        # the recorder must not leak into identity
    monkeypatch.setattr(families, f"family_{family}", rec, raising=False)
    tape = pd.Series(1.0, index=bars.index)
    monkeypatch.setattr(osw, "_tape_series", lambda *a, **k: (tape, tape))
    monkeypatch.setattr(osw, "_surface_for", lambda s: {"surface": s})
    monkeypatch.setattr(osw, "_macro_series", lambda *a, **k: tape)
    monkeypatch.setattr(osw, "_cot_frame", lambda *a, **k: "COT")
    monkeypatch.setattr(osw, "_event_index", lambda: pd.DatetimeIndex(bars.index[:3]))
    monkeypatch.setattr(fi, "events_for_symbol", lambda ev, s: [{"symbol": s}])
    G.build_cell("CHFNOK", family, dict(params), {}, h1_override=bars)
    assert seen, f"{family} {params}: the family was never called ({G.LAST_BUILD_FAILURE})"
    return seen[0]


@pytest.mark.parametrize("family", sorted(E.IGNORED_INPUTS))
def test_an_ignored_input_hands_the_family_the_identical_call(family, bars, monkeypatch) -> None:
    keys = E.IGNORED_INPUTS[family]
    alias = {k: ALIASES[k] for k in keys}
    assert _call_seen(family, alias, bars, monkeypatch) == \
        _call_seen(family, {}, bars, monkeypatch)
    # ... and on the forward clock / executor: the runtime call shape, with `resolve`'s own
    # override of `symbol` by the cell's symbol for the two families that take one.
    from mt5desk.family_inputs import runtime_call_params
    over = {"symbol": "CHFNOK"} if "symbol" in keys else {}
    assert {**runtime_call_params(family, alias), **over} == \
        {**runtime_call_params(family, {}), **over}


@pytest.mark.parametrize("family", sorted(E.IGNORED_INPUTS))
def test_an_ignored_input_shares_the_canonical_fingerprint(family) -> None:
    alias = {k: ALIASES[k] for k in E.IGNORED_INPUTS[family]}
    fp = E.canonical_fingerprint(family, "CHFNOK", alias)
    assert fp is not None and fp == E.canonical_fingerprint(family, "CHFNOK", {})


def test_the_carry_alias_set_from_the_ruling_is_one_cell() -> None:
    fps = {E.canonical_fingerprint("carry", "CHFNOK", p)
           for p in ({"input_symbol": "eBay"}, {"input_symbol": "GBPJPY"}, {},
                     {"timeframe": "H1"}, {"session": "all"}, {"session": "nonsense"})}
    assert len(fps) == 1 and None not in fps


def test_a_real_difference_keeps_its_own_identity() -> None:
    base = E.canonical_fingerprint("carry", "CHFNOK", {})
    for other in (E.canonical_fingerprint("carry", "CHFNOK", {"hold_bars": 48}),
                  E.canonical_fingerprint("carry", "CHFNOK", {"session": "asia"}),
                  E.canonical_fingerprint("carry", "CHFNOK", {"timeframe": "M15"}),
                  E.canonical_fingerprint("carry", "EURNOK", {}),
                  E.canonical_fingerprint("relative_value", "CHFNOK",
                                          {"peer_symbol": "EURNOK"})):
        assert other != base
    assert E.canonical_fingerprint("relative_value", "X", {"peer_symbol": "A"}) != \
        E.canonical_fingerprint("relative_value", "X", {"peer_symbol": "B"})


def test_undeclared_keys_name_what_a_generator_must_not_mint() -> None:
    assert E.undeclared_keys("carry", {"input_symbol": "GBPJPY"}) == ["input_symbol"]
    assert E.undeclared_keys("carry", {"hold_bars": 48, "session": "asia", "timeframe": "M5",
                                       "regime": "high_vol", "representation": "x"}) == []
    assert E.undeclared_keys("relative_value", {"peer_symbol": "EURNOK"}) == []
    assert E.undeclared_keys("range_reversion", {"w": 3}) == ["w"]
    assert E.undeclared_keys("overnight_gap_decay", {"mechanism_genome": {}}) == \
        ["mechanism_genome"]
    assert E.undeclared_keys("no_such_family", {"x": 1}) is None


def test_the_compiler_refuses_an_alias_by_name_and_mints_carry_bare() -> None:
    import miner_candidate_compiler as C
    assert C._undeclared({"family": "carry", "params": {"input_symbol": "GBPJPY"}}) == \
        ["input_symbol"]
    assert C._undeclared({"family": "carry", "params": {}}) == []
    assert C._undeclared({"family": "no_such_family", "params": {"x": 1}}) == []
    cells, kind = C.compile_row("broker_swaps", {"kind": "swap_terms", "symbol": "CHFNOK",
                                                 "swap_long": 1.0, "swap_short": -2.0},
                                {"CHFNOK"})
    assert kind == "STRUCTURED_CARRY" and cells
    assert all(c["params"] == {} for c in cells)
