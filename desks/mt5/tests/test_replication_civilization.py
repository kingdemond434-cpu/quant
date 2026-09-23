"""The independent replication civilization: a deliberately mis-specified reimplementation is
quarantined with the divergence named, an honest one is REPLICATED, the lane never imports the
original implementation (by source and at runtime), and --dry-run writes nothing."""
from __future__ import annotations

import json
import re
import sys
import types
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import replication_civilization as rc  # noqa: E402

N_DAYS = 420
META = {"contract_size": 100000.0, "tick_size": 0.00001, "median_spread_pts": 12.0,
        "tick_value": 0.86}


def _gap_bars(seed: int = 5, fade: float = 0.0009, gap: float = 0.002) -> rc.Bars:
    """Hourly bars with a planted overnight gap that decays over the next eight bars.

    THE GAP IS IN THE PATH, NOT ONLY IN THE OPEN. An earlier draft gapped `open_` alone and
    left `close` on the un-gapped cumulative path, so every gap was fully reversed INSIDE its
    own signal bar: the fade rule's entry (the next bar's open = the signal bar's close) already
    sat past its own target, every trade exited at the target for a LOSS, and the honest
    certificate read Sharpe -12. Real data gaps the whole bar, so the gap enters `step`."""
    rng = np.random.default_rng(seed)
    n = N_DAYS * 24
    t0 = np.datetime64("2024-01-01T00:00:00", "ns").astype("int64")
    t = t0 + np.arange(n, dtype="int64") * 3_600_000_000_000
    hours = np.arange(n) % 24
    day_no = np.arange(n) // 24
    gap_sign = np.where(rng.random(N_DAYS) < 0.5, 1.0, -1.0)
    jump = np.zeros(n)
    jump[hours == 0] = gap * gap_sign
    step = rng.normal(0.0, 0.0002, n) + jump
    fade_mask = (hours >= 1) & (hours <= 8)
    step[fade_mask] -= fade * gap_sign[day_no[fade_mask]]
    close = 1.2 * np.exp(np.cumsum(step))
    prev = np.concatenate([[1.2], close[:-1]])
    open_ = prev * np.exp(jump)                 # the open jumps, then the bar trades on from it
    high = np.maximum(open_, close) * 1.0002
    low = np.minimum(open_, close) * 0.9998
    return rc.bars_from_arrays(t, open_, high, low, close)


def _certificate(sharpe: float) -> dict[str, Any]:
    return {"cell": "TESTFX overnight_gap_decay asia", "sym": "TESTFX", "days": N_DAYS,
            "shadow_spec": {"symbol": "TESTFX", "family": "overnight_gap_decay",
                            "selector": "asia", "condition": None, "params": {}},
            "gates": {"in_sample_screen": {"passed": True, "sharpe": sharpe}}}


def test_an_honest_certificate_is_replicated_and_a_misspecified_one_is_quarantined(
        tmp_path: Path) -> None:
    bars = _gap_bars()
    p, _ = rc.resolve_spec("overnight_gap_decay", {}, "asia", None)
    _orders, fills = rc.rebuild("overnight_gap_decay", bars, p, rc.cost_spec(META).price_units)
    ours, _days = rc.sharpe(fills)
    assert fills and ours is not None and ours > 0.5       # the planted edge is real
    honest = rc.replicate_certificate(_certificate(ours * 0.9), meta=META, bars=bars)
    assert honest["verdict"] == rc.REPLICATED, honest
    # THE MIS-SPECIFIED ONE: the first implementation "found" the opposite sign with the
    # same rule text -- a fill, exit or cost that does not do what the specification says.
    wrong = rc.replicate_certificate(_certificate(-ours), meta=META, bars=bars)
    assert wrong["verdict"] == rc.MISMATCH and "SIGN" in wrong["why"][0]
    inflated = rc.replicate_certificate(_certificate(ours * 5.0), meta=META, bars=bars)
    assert inflated["verdict"] == rc.MISMATCH and "MAGNITUDE" in inflated["why"][0]
    unknown = rc.replicate_certificate({"shadow_spec": {"symbol": "TESTFX", "family": "carry"},
                                        "gates": {}}, meta=META, bars=bars)
    assert unknown["verdict"] == rc.UNMEASURED and "spec book" in unknown["why"][0]

    kw: dict[str, Any] = {"certificates": [_certificate(-ours)], "forward": [],
                          "universe_meta": {"TESTFX": META},
                          "bars_loader": lambda s, t: bars,
                          "cursor_path": tmp_path / "cursor.json",
                          "quarantine_path": tmp_path / "quarantine.json",
                          "report": tmp_path / "REPLICATION.json"}
    dry = rc.build(budget_s=60, dry_run=True, conn=None, **kw)
    assert dry["counts"][rc.MISMATCH] == 1 and dry["recorded"]["quarantined"] == 0
    assert not list(tmp_path.iterdir())                     # dry-run writes nothing
    wet = rc.build(budget_s=60, dry_run=False, conn=_NoRegistry(), **kw)
    assert wet["quarantined"] == ["TESTFX overnight_gap_decay asia"]
    q = json.loads((tmp_path / "quarantine.json").read_text("utf-8"))
    assert q["rows"][0]["key"] == "TESTFX overnight_gap_decay asia" and q["rows"][0]["why"]
    assert (tmp_path / "REPLICATION.json").exists() and (tmp_path / "cursor.json").exists()


class _NoRegistry:
    """A connection whose every query fails: the registry effect is measured as zero rows,
    never as an exception that takes the pass with it."""

    def execute(self, *a: Any, **k: Any) -> Any:
        raise RuntimeError("no registry in this test")

    def close(self) -> None:
        pass


def test_a_forward_row_whose_ledger_disagrees_is_quarantined_by_name() -> None:
    bars = _gap_bars()
    p, _ = rc.resolve_spec("overnight_gap_decay", {}, "asia", "LONG")
    _orders, fills = rc.rebuild("overnight_gap_decay", bars, p, rc.cost_spec(META).price_units)
    start = int(bars.t[len(bars) // 2])
    window = [f for f in fills if f.entry_t >= start]
    assert len(window) >= 20

    def stamp(ns: int) -> str:
        return str(np.datetime64(ns, "ns")).replace("T", " ")[:19] + "+00:00"

    honest_ledger = [{"entry_time": stamp(f.entry_t), "exit_time": stamp(f.exit_t),
                      "side": f.side, "r_multiple": f.r, "reason": f.reason} for f in window]
    row = {"key": "TESTFX.overnight_gap_decay.asia", "forward_start": stamp(start),
           "identity": {"family": "overnight_gap_decay", "symbol": "TESTFX",
                        "direction": "LONG", "timeframe": "H1", "selector": "asia",
                        "params": {}},
           "cost_fields": {"spread_per_lot": 12.0, "commission_per_lot": 2.25,
                           "quote_per_account": 1.1627}}
    ok = rc.replicate_forward(row, meta=META, bars=bars, ledger=honest_ledger)
    assert ok["verdict"] == rc.REPLICATED, ok
    # the first implementation booked every trade a whole R better than the rule allows
    drifted = [dict(r, r_multiple=float(r["r_multiple"]) + 1.0) for r in honest_ledger]
    bad = rc.replicate_forward(row, meta=META, bars=bars, ledger=drifted)
    assert bad["verdict"] == rc.MISMATCH and any("per-trade R" in w for w in bad["why"])
    # and a cost term frozen at ten times the registry's is a divergence of its own
    costly = dict(row, cost_fields={"spread_per_lot": 120.0})
    off = rc.replicate_forward(costly, meta=META, bars=bars, ledger=honest_ledger)
    assert off["verdict"] == rc.MISMATCH and any("COST" in w for w in off["why"])
    none = rc.replicate_forward(row, meta=META, bars=bars, ledger=[])
    assert none["verdict"] == rc.UNMEASURED


def test_the_lane_never_imports_the_original_implementation() -> None:
    src = (DESK / "research" / "replication_civilization.py").read_text("utf-8")
    imports = re.findall(r"^\s*(?:from|import)\s+([\w.]+)", src, re.M)
    for name in imports:
        for banned in rc.FORBIDDEN_IMPORTS:
            assert not (name == banned or name.startswith(banned + ".")
                        or name.endswith("." + banned.split(".")[-1])), (name, banned)
    assert "families" not in imports and "engine" not in imports
    # AT RUNTIME TOO: every door is replaced by a module that explodes on any attribute read,
    # and a full pass still completes on its own code path.
    bars = _gap_bars()
    poisoned = {}
    for name in ("mt5desk.families", "mt5desk.families_orthogonal", "mt5desk.engine",
                 "mt5desk.family_call", "research.proposer_common", "proposer_common",
                 "external_gauntlet", "lead_replication", "shadow_forward"):
        mod = types.ModuleType(name)
        mod.__getattr__ = lambda attr, _n=name: (_ for _ in ()).throw(  # type: ignore[assignment]
            AssertionError(f"{_n}.{attr} was reached by the replication lane"))
        poisoned[name] = sys.modules.get(name)
        sys.modules[name] = mod
    try:
        p, _ = rc.resolve_spec("overnight_gap_decay", {}, "asia", None)
        _orders, fills = rc.rebuild("overnight_gap_decay", bars, p, 0.0)
        ours, _ = rc.sharpe(fills)
        doc = rc.build(budget_s=30, dry_run=True, certificates=[_certificate(ours or 1.0)],
                       forward=[], universe_meta={"TESTFX": META},
                       bars_loader=lambda s, t: bars)
        assert doc["counts"][rc.REPLICATED] == 1
    finally:
        for name, old in poisoned.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old


def test_the_leg_is_wired_into_the_hourly_cycle() -> None:
    import hourly_cycle as hc

    from libs.research import layers
    assert hc.department_of("replication_civilization") == "validate"
    assert hc.LEG_BUDGET_SEC["replication_civilization"] > 900
    assert layers.LEG_LAYER["replication_civilization"] == "meta"
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("replication_civilization"' in src
