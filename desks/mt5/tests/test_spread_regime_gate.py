"""The spread-regime state and its entry gate (C row 121).

Pinned here: SHADOW sends exactly what the gateway sent before (same requests, same pass state),
and only records; LIVE defers by leaving the bar unmarked and later sends the SAME order; the gate
never raises into the gateway; the scorer and the promoter move the switch on the forward ledger
alone, and leave a pinned switch alone.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import spread_gate as gate  # noqa: E402
from research import spread_regime as sr  # noqa: E402


def _adapter():
    spec = importlib.util.spec_from_file_location(
        "_gw_adapter_harness", _DESK / "tests" / "test_gateway_adapter.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _desk(root: Path, mode: str | None, *, median: float = 10.0) -> Path:
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "reports").mkdir(parents=True, exist_ok=True)
    hours = {str(h): {"status": "MEASURED", "median": median, "scale": 1.0, "n": 500}
             for h in range(24)}
    (root / "reports" / "SPREAD_REGIME.json").write_text(json.dumps({
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "symbols": {"EURUSD": {"basis": "ticks", "point": 0.00001, "hours": hours}}}), "utf-8")
    if mode is not None:
        (root / "data" / "SPREAD_GATE_MODE.json").write_text(json.dumps({"mode": mode}), "utf-8")
    return root


def _ledger(root: Path) -> list[dict]:
    p = root / "data" / "spread_gate_ledger.jsonl"
    return [json.loads(x) for x in p.read_text("utf-8").splitlines()] if p.exists() else []


def _pass(tga, tmp: Path, monkeypatch, base: Path | None, quote=None):
    rows = tga._rows()
    mt5 = tga._fake_mt5(rows)
    if quote is not None:
        mt5.symbol_info_tick = lambda symbol: quote
    ns = tga._family_ns(tmp, mt5, monkeypatch, armed_file=True, sig_hour=tga._sig_hour(rows))
    if base is not None:
        ns["BASE"] = base
    return ns, mt5


def test_shadow_sends_byte_identical_requests_and_only_records(tmp_path, monkeypatch) -> None:
    tga = _adapter()
    # The quote is 20 points wide against a 10-point norm: spread_z = +10, an extreme entry.
    outcomes = []
    for label, mode in (("before", None), ("shadow", "SHADOW"), ("default", "absent")):
        run = tmp_path / label
        run.mkdir()
        base = None if mode is None else _desk(run / "desk", None if mode == "absent" else mode)
        ns, mt5 = _pass(tga, run, monkeypatch, base)
        st = {"armed": True}
        tga._run_family(ns, st, [tga._sleeve()], 10_000.0)
        outcomes.append((label, json.dumps(mt5.sent, sort_keys=True, default=str),
                         json.dumps(st, sort_keys=True, default=str),
                         [x for x in ns["_logs"] if "DEFERRED" in x], base))
    (_, sent0, st0, _, _), *rest = outcomes
    assert json.loads(sent0), "the baseline pass must send for the comparison to mean anything"
    for label, sent, st, deferred, base in rest:
        assert sent == sent0, f"{label}: the order sent differs from the gate-less gateway"
        assert st == st0, f"{label}: the pass state differs from the gate-less gateway"
        assert deferred == []
        (row,) = _ledger(base)
        assert row["kind"] == "would_defer" and row["mode"] == "SHADOW" and row["z"] == 10.0
        assert row["quote"] == 1.1102 and row["side"] == 1 and row["median"] == 10.0


def test_live_defers_by_leaving_the_bar_unmarked_then_sends_the_same_order(tmp_path,
                                                                           monkeypatch) -> None:
    tga = _adapter()
    base = _desk(tmp_path / "desk", "LIVE")
    quote = SimpleNamespace(bid=1.1100, ask=1.1102)
    ns, mt5 = _pass(tga, tmp_path, monkeypatch, base, quote)
    st = {"armed": True}
    tga._run_family(ns, st, [tga._sleeve()], 10_000.0)
    assert mt5.sent == [], "LIVE at spread_z +10 must defer this pass"
    assert not st.get("generic", {}).get(tga._NAME, {}).get("last_signal_bar"), (
        "a deferral consumed the bar: it would be a cancel, not a defer")
    assert any("FAMILY-EXEC DEFERRED" in x for x in ns["_logs"])
    quote.ask = 1.11010                                   # 10 pts: back at the hour's norm
    tga._run_family(ns, st, [tga._sleeve()], 10_000.0)
    assert len(mt5.sent) == 1 and mt5.sent[0]["volume"] == 0.12, "same order, same lot"
    tga._run_family(ns, st, [tga._sleeve()], 10_000.0)
    assert len(mt5.sent) == 1, "the released signal must never send twice"
    kinds = [r["kind"] for r in _ledger(base)]
    assert kinds == ["defer", "release"]
    rel = _ledger(base)[-1]
    assert rel["reason"] == "spread_normal" and rel["improvement_r"] > 0


def _plan(ask: float, last_bar: str = "2026-11-18 09:00:00+00:00") -> dict:
    return {"ok": True, "lot": 0.1, "dist": 0.0050, "entry_ref": ask, "side": 1,
            "tick": SimpleNamespace(bid=1.1000, ask=ask), "sym": SimpleNamespace(),
            "last_bar": last_bar, "tf": "H1"}


def test_live_releases_at_the_horizon_and_on_drift_never_holding_past_them(tmp_path) -> None:
    base = _desk(tmp_path, "LIVE")
    s = {"name": "x", "symbol": "EURUSD", "q_charge": 0.005}
    t0 = datetime.now(tz=UTC)
    assert gate.entry_gate(s, _plan(1.1002), base=base, now=t0)
    assert gate.entry_gate(s, _plan(1.1002), base=base, now=t0 + timedelta(minutes=5))
    assert gate.entry_gate(s, _plan(1.1002), base=base,
                           now=t0 + timedelta(minutes=gate.MAX_DEFER_MIN)) is None
    assert _ledger(base)[-1]["reason"] == "horizon"
    # Drift: the ask runs 0.1 stop distances against the buy -> released at once.
    s2 = {"name": "y", "symbol": "EURUSD"}
    assert gate.entry_gate(s2, _plan(1.1002), base=base, now=t0)
    assert gate.entry_gate(s2, _plan(1.1002 + 0.0006), base=base,
                           now=t0 + timedelta(minutes=1)) is None
    assert _ledger(base)[-1]["reason"] == "drift"
    # An M1 chart's horizon is shorter than one pass: the gate cannot defer there at all.
    assert gate.entry_gate({"name": "z", "symbol": "EURUSD"}, _plan(1.1002), base=base,
                           bar_minutes=1, now=t0) is None


def test_the_gate_never_raises_and_unmeasured_never_defers(tmp_path) -> None:
    base = _desk(tmp_path, "LIVE")
    assert gate.entry_gate({"name": "x"}, {"ok": True, "tick": object()}, base=base) is None
    assert gate.entry_gate(None, None, base=base) is None  # type: ignore[arg-type]
    assert gate.entry_gate({"name": "x", "symbol": "NOPE"}, _plan(1.1002), base=base) is None
    (base / "data" / "SPREAD_GATE_MODE.json").write_text("{ nope", "utf-8")
    assert gate.read_mode(base) == "SHADOW", "an unreadable switch must never read LIVE"
    stale = json.loads((base / "reports" / "SPREAD_REGIME.json").read_text("utf-8"))
    stale["generated_at"] = (datetime.now(tz=UTC) - timedelta(hours=7)).isoformat()
    (base / "reports" / "SPREAD_REGIME.json").write_text(json.dumps(stale), "utf-8")
    (base / "data" / "SPREAD_GATE_MODE.json").write_text('{"mode": "LIVE"}', "utf-8")
    assert gate.entry_gate({"name": "x", "symbol": "EURUSD"}, _plan(1.1002), base=base) is None


def test_norm_is_robust_on_a_flat_administered_spread() -> None:
    n = sr.norm_from_counts(Counter({12.0: 900, 13.0: 50, 40.0: 50}), 200)
    assert n["status"] == "MEASURED" and n["median"] == 12.0 and n["scale"] >= 1.2
    assert sr.norm_from_counts(Counter({12.0: 10}), 200)["status"] == "UNMEASURED"
    assert sr.regime_of(3.2) == "STRESS" and sr.regime_of(-1.5) == "TIGHT"
    assert sr.regime_of(None) == "UNMEASURED"


def test_a_shadow_row_is_scored_on_the_tape_at_the_release_tick() -> None:
    t0 = 1_789_000_000_000
    row = {"kind": "would_defer", "broker_ms": t0, "side": 1, "quote": 1.10020, "dist": 0.0050,
           "median": 10.0, "scale": 1.0, "max_defer_s": 1200.0, "key": "k", "symbol": "EURUSD"}
    ticks = pd.DataFrame({"time_msc": [t0 + 60_000, t0 + 120_000, t0 + 1_300_000],
                          "bid": [1.10000, 1.09990, 1.1],
                          "ask": [1.10020, 1.10001, 1.10011]})
    got = sr.score_would_defer(row, ticks, 0.00001)
    assert got is not None and got["reason"] == "spread_normal"
    assert abs(got["improvement_r"] - (1.10020 - 1.10001) / 0.0050) < 1e-9
    assert sr.score_would_defer(row, ticks.iloc[:2], 0.00001) is None, (
        "a tape that has not reached the end of the window cannot score the row")


def test_promotion_and_reversion_are_automatic_and_a_pin_holds(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sr, "BASE", tmp_path)
    (tmp_path / "data").mkdir()
    good = [{"improvement_r": 0.05 + 0.01 * (i % 3)} for i in range(gate.N_MIN)]
    assert sr.verdict(good[:-1])["promote"] is False, "under N_MIN never promotes"
    v = sr.verdict(good)
    assert v["promote"] is True and v["verdict"] == sr.EARNS
    assert sr.promote(v)["mode"] == "LIVE" and gate.read_mode(tmp_path) == "LIVE"
    bad = [{"improvement_r": -0.05 - 0.01 * (i % 3)} for i in range(gate.N_MIN)]
    vb = sr.verdict(good + bad * 6)                     # the newest WINDOW is all losses
    assert vb["promote"] is False and vb["verdict"] == sr.COSTS
    assert sr.promote(vb)["mode"] == "SHADOW" and gate.read_mode(tmp_path) == "SHADOW"
    (tmp_path / "data" / "SPREAD_GATE_MODE.json").write_text(
        '{"mode": "SHADOW", "pinned": true}', "utf-8")
    assert sr.promote(v)["changed"] is False and gate.read_mode(tmp_path) == "SHADOW"


def test_the_missed_growth_ledger_carries_the_gates_line(tmp_path, monkeypatch) -> None:
    import research.missed_growth as mg
    monkeypatch.setattr(mg, "SPREAD_GATE", tmp_path / "SPREAD_GATE.json")
    assert mg.published_spread_gate_lines()["verdict"] == mg.UNMEASURED
    line = {"gate": "spread_regime_entry_gate", "verdict": "EARNS_ITS_PLACE", "n_window": 40}
    (tmp_path / "SPREAD_GATE.json").write_text(json.dumps({
        "generated_at": datetime.now(tz=UTC).isoformat(), "mode": {"mode": "LIVE"},
        "missed_growth": [line]}), "utf-8")
    got = mg.published_spread_gate_lines()
    assert got["verdict"] == mg.EARNS and got["mode"] == "LIVE" and got["lines"] == [line]
