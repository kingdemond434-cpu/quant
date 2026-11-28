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


def test_live_defers_by_leaving_the_bar_unmarked_then_sends_the_same_signal(tmp_path,
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
    assert len(mt5.sent) == 1, "the same signal is sent on the release pass"
    tga._run_family(ns, st, [tga._sleeve()], 10_000.0)
    assert len(mt5.sent) == 1, "the released signal must never send twice"
    kinds = [r["kind"] for r in _ledger(base)]
    assert kinds == ["defer", "release"]
    rel = _ledger(base)[-1]
    assert rel["reason"] == "spread_normal" and rel["improvement_r"] > 0
    # The lot is re-sized on the release pass, not frozen: both are ledgered (audit SF2).
    assert rel["lot0"] == 0.12 and rel["lot_sent"] == mt5.sent[0]["volume"]


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


def _row(t0: int) -> dict:
    return {"kind": "would_defer", "broker_ms": t0, "side": 1, "quote": 1.10020, "dist": 0.0050,
            "median": 10.0, "scale": 1.0, "max_defer_s": 1200.0, "key": "k", "symbol": "EURUSD"}


def test_a_shadow_row_is_scored_at_the_gateways_pass_cadence() -> None:
    t0 = 1_789_000_000_000
    # A narrow tick at +30 s falls BETWEEN passes: the LIVE gate would not see it, so the scorer
    # must not release there. The first pass (+60 s) sees 20 pts (z +10); the second (+120 s)
    # sees 11 pts (z +1) and releases at that tick's ask (audit SF1).
    ticks = pd.DataFrame({"time_msc": [t0 + 30_000, t0 + 60_000, t0 + 120_000],
                          "bid": [1.09900, 1.10000, 1.09990],
                          "ask": [1.09901, 1.10020, 1.10001]})
    got = sr.score_would_defer(_row(t0), ticks, 0.00001)
    assert got is not None and got["reason"] == "spread_normal" and got["checks"] == 2
    assert abs(got["improvement_r"] - (1.10020 - 1.10001) / 0.0050) < 1e-9
    assert sr.score_would_defer(_row(t0), ticks.iloc[:2], 0.00001) is None, (
        "a tape that has not reached the next pass's check cannot score the row")
    # A measured pass latency moves every check later by that much.
    late = {**_row(t0), "pass_latency_s": 70.0}
    assert sr.score_would_defer(late, ticks, 0.00001) is None


def test_the_tape_window_reads_both_neighbouring_day_files(tmp_path) -> None:
    from mt5desk import tape
    t0 = int(datetime(2026, 11, 18, 23, 58, tzinfo=UTC).timestamp() * 1000)
    d = tmp_path / "EURUSD"
    d.mkdir()
    # One file per convention, dated a day APART from the decision's broker date on purpose.
    pd.DataFrame({"time_msc": [t0 - 1000, t0 + 60_000], "bid": [1.1, 1.1],
                  "ask": [1.1002, 1.1002]}).to_parquet(d / "2026-11-19.parquet")
    pd.DataFrame({"time_msc": [t0 + 120_000], "bid": [1.1], "ask": [1.10001]}).to_parquet(
        d / "20261117.parquet")
    assert [x for x, _ in tape.day_files("EURUSD", tmp_path)] == ["2026-11-17", "2026-11-19"]
    w = sr._tape_window("EURUSD", t0, tmp_path)
    assert w is not None and list(w["time_msc"]) == [t0 + 60_000, t0 + 120_000]


def _w(vals: list[float]) -> list[dict]:
    return [{"improvement_r": v} for v in vals]


def test_the_dead_band_promotes_past_two_se_demotes_past_one_and_holds_between(
        tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sr, "BASE", tmp_path)
    (tmp_path / "data").mkdir()
    mode = tmp_path / "data" / "SPREAD_GATE_MODE.json"
    good = _w([0.05 + 0.01 * (i % 3) for i in range(gate.N_MIN)])
    assert sr.verdict(good[:-1])["action"] == "HOLD", "under N_MIN never moves"
    v = sr.verdict(good)
    assert v["action"] == "PROMOTE" and v["verdict"] == sr.EARNS
    assert v["bars"]["promote_one_sided_level"] == 0.9772
    assert v["bars"]["demote_one_sided_level"] == 0.8413
    assert sr.promote(v)["mode"] == "LIVE" and gate.read_mode(tmp_path) == "LIVE"
    assert json.loads(mode.read_text("utf-8"))["rule"] == sr.MODE_RULE
    bad = _w([-0.05 - 0.01 * (i % 3) for i in range(gate.N_MIN)])
    vb = sr.verdict(bad)
    assert vb["action"] == "DEMOTE" and vb["verdict"] == sr.COSTS
    assert sr.promote(vb)["mode"] == "SHADOW" and gate.read_mode(tmp_path) == "SHADOW"
    mode.write_text('{"mode": "SHADOW", "pinned": true}', "utf-8")
    assert sr.promote(v)["changed"] is False and gate.read_mode(tmp_path) == "SHADOW"


def test_a_window_clearing_only_one_se_neither_promotes_nor_demotes(tmp_path,
                                                                     monkeypatch) -> None:
    """The audit's MF1 case: mean - 1 SE > 0 but mean - 2 SE <= 0. The old single bar promoted
    on it, and wrote SHADOW on the next pass that missed it; the dead band holds either mode."""
    monkeypatch.setattr(sr, "BASE", tmp_path)
    (tmp_path / "data").mkdir()
    vals = [1.0 if i % 2 else -0.6 for i in range(40)]   # mean 0.2, SE ~0.13
    v = sr.verdict(_w(vals))
    assert v["mean_improvement_r"] - v["se_r"] > 0 and v["promote_bar_r"] <= 0
    assert v["action"] == "HOLD" and not v["promote"] and not v["demote"]
    for held in ("SHADOW", "LIVE"):
        (tmp_path / "data" / "SPREAD_GATE_MODE.json").write_text(
            json.dumps({"mode": held}), "utf-8")
        got = sr.promote(v)
        assert got["changed"] is False and gate.read_mode(tmp_path) == held


def test_live_only_evidence_can_demote_alone(tmp_path, monkeypatch) -> None:
    rows = [{"improvement_r": 0.08 + 0.01 * (i % 3), "mode": "SHADOW"} for i in range(100)]
    rows += [{"improvement_r": -0.05 - 0.01 * (i % 3), "mode": "LIVE"} for i in range(40)]
    v = sr.verdict(rows)
    assert v["mean_improvement_r"] > 0 and v["live_only"]["n_window"] == 40
    assert v["action"] == "DEMOTE"


def test_a_pending_deferral_that_is_never_released_expires_and_is_counted_lost(
        tmp_path, monkeypatch) -> None:
    base = _desk(tmp_path, "LIVE")
    t0 = datetime.now(tz=UTC)
    s = {"name": "x", "symbol": "EURUSD"}
    assert gate.entry_gate(s, _plan(1.1002), base=base, now=t0)
    # Every later pass refuses upstream: the gate only ever sees not-ok plans for OTHER calls.
    later = t0 + timedelta(seconds=1200 + gate.PASS_S + 1)
    assert gate.entry_gate({"name": "other", "symbol": "EURUSD"}, {"ok": False}, base=base,
                           now=later) is None
    st = json.loads((base / "data" / "spread_gate_state.json").read_text("utf-8"))
    assert st["pending"] == {} and "x|2026-11-18 09:00:00+00:00" in st["expired"]
    (row,) = [r for r in _ledger(base) if r["kind"] == "expired"]
    assert row["improvement_r"] == "UNMEASURED" and row["reason"]
    # The key is never deferred again from scratch: an ok plan now SENDS.
    assert gate.entry_gate(s, _plan(1.1002), base=base, now=later) is None
    # The hourly leg sweeps too (a gateway that stopped calling the gate), and counts n_lost.
    assert gate.entry_gate({"name": "y", "symbol": "EURUSD"}, _plan(1.1002), base=base, now=t0)
    assert gate.sweep_expired(base, later) == 1
    assert sr.lost_keys(_ledger(base)) == sorted(["x|2026-11-18 09:00:00+00:00",
                                                  "y|2026-11-18 09:00:00+00:00"])


def test_a_deferral_first_seen_past_horizon_plus_a_pass_is_released_not_expired(
        tmp_path) -> None:
    """Passes run 1 to 7 minutes apart: a horizon release first seen at horizon + 5 min must be
    a scored `release` (reason horizon), never an unscored `expired` (audit MF1, round 2)."""
    base = _desk(tmp_path, "LIVE")
    t0 = datetime.now(tz=UTC)
    s = {"name": "x", "symbol": "EURUSD"}
    assert gate.entry_gate(s, _plan(1.1002), base=base, now=t0)
    late = t0 + timedelta(seconds=gate.max_defer_s(60) + 300)
    assert gate.entry_gate(s, _plan(1.10021), base=base, now=late) is None
    kinds = [r["kind"] for r in _ledger(base)]
    assert kinds == ["defer", "release"], kinds
    rel = _ledger(base)[-1]
    assert rel["reason"] == "horizon" and isinstance(rel["improvement_r"], float)
    assert sr.lost_keys(_ledger(base)) == []


def test_the_hourly_sweep_never_drops_a_pending_entry_written_after_its_read(
        tmp_path, monkeypatch) -> None:
    """The gateway writes the state file without a lock, so the leg's sweep is ledger-only: a
    deferral the gateway writes WHILE the leg is sweeping survives it (audit SF4)."""
    base = _desk(tmp_path, "LIVE")
    t0 = datetime.now(tz=UTC)
    assert gate.entry_gate({"name": "old", "symbol": "EURUSD"}, _plan(1.1002), base=base, now=t0)
    later = t0 + timedelta(seconds=gate.max_defer_s(60) + gate.PASS_S + 1)
    state = base / "data" / "spread_gate_state.json"
    real_append = gate._append

    def gateway_writes_mid_sweep(path, row):          # the gateway's pass lands mid-sweep
        doc = json.loads(state.read_text("utf-8"))
        doc["pending"]["new|bar"] = {"first_at": later.isoformat(), "max_defer_s": 1200.0}
        state.write_text(json.dumps(doc), "utf-8")
        real_append(path, row)
    monkeypatch.setattr(gate, "_append", gateway_writes_mid_sweep)
    assert gate.sweep_expired(base, later) == 1
    doc = json.loads(state.read_text("utf-8"))
    assert "new|bar" in doc["pending"], "the leg's sweep dropped a deferral written after its read"
    assert "old|2026-11-18 09:00:00+00:00" in doc["pending"], "the leg must not write state"
    assert [r["kind"] for r in _ledger(base)] == ["defer", "expired"]
    # If the gateway then releases the key the leg ledgered, it is a release, not a loss.
    monkeypatch.setattr(gate, "_append", real_append)
    assert gate.entry_gate({"name": "old", "symbol": "EURUSD"}, _plan(1.1002), base=base,
                           now=later) is None
    assert _ledger(base)[-1]["kind"] == "release" and sr.lost_keys(_ledger(base)) == []


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
