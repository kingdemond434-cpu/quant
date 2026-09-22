"""The feed/clock lab on a planted desk: a tmp tape, tmp bars, a tmp sleeve with its shadow
ledger, tmp fills and a tmp registry. Dry-run writes nothing; a live pass stamps feed health,
the roster hook reads it as an input; a sleeve whose edge dies under the tape's own measured
receipt jitter is TIMING_FRAGILE and lands in the registry; the impact pass donates seeds in
the seat shape the compiler reads."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK.parent.parent), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import feed_clock_lab as fcl  # noqa: E402
from mt5desk import decision_core as core  # noqa: E402

from libs.moat import registry as R  # noqa: E402

DAY0 = datetime(2026, 9, 12, 0, 0, tzinfo=UTC)
TAPE_DAY = datetime(2026, 9, 16, 0, 0, tzinfo=UTC)
SLEEVE = {"name": "xau_srb_asia_test", "symbol": "XAUUSD", "family": "session_range_breakout",
          "selector": "asia", "exec": "family_market", "lot": "auto_ramp", "risk_frac": 0.005,
          "status": "LIVE"}


def _bars() -> pd.DataFrame:
    rng = np.random.default_rng(2026)
    idx = pd.date_range(DAY0, periods=24 * 5, freq="1h", tz="UTC")
    close = 4300.0 + np.cumsum(rng.normal(0.0, 3.0, size=idx.size))
    return pd.DataFrame({"open": np.r_[4300.0, close[:-1]], "high": close + 1.0,
                         "low": close - 1.0, "close": close, "tick_volume": 100,
                         "spread": 5, "real_volume": 0.0}, index=idx)


def _write_tape(root: Path, bars: pd.DataFrame, *, delay_hours: float | None) -> float:
    """Ticks every 2 s from 00:00 to 12:00 UTC on the tape day, mid = the containing bar's
    close (so the reference agrees at lag 0). `delay_hours` None plants a 30 s poll receipt;
    a number plants receipt delays uniform on [0, delay_hours] -- the corrupt clock."""
    rng = np.random.default_rng(9)
    t0 = TAPE_DAY.timestamp() * 1000.0
    ms = t0 + np.arange(0, 12 * 3600, 2) * 1000.0
    hours = ((ms - t0) // 3_600_000).astype(int)
    day_bars = bars.loc[bars.index >= TAPE_DAY]
    mid = day_bars["close"].to_numpy()[hours]
    delay = (30_000.0 + rng.uniform(0, 2000, ms.size) if delay_hours is None
             else rng.uniform(0, delay_hours * 3_600_000.0, ms.size))
    recv = pd.to_datetime(ms + delay, unit="ms", utc=True)
    frame = pd.DataFrame({"time": (ms // 1000).astype("int64"), "bid": mid - 0.025,
                          "ask": mid + 0.025, "last": 0.0, "volume": 0,
                          "time_msc": ms.astype("int64"), "flags": 1030, "volume_real": 0.0,
                          "recv_utc": [x.isoformat(timespec="milliseconds") for x in recv],
                          "recv_mono": np.arange(ms.size, dtype=float)})
    out = root / "data" / "tape" / "ticks" / "XAUUSD"
    out.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out / "20260916.parquet", index=False)
    return float(ms[-1])


def _write_ledger(root: Path, bars: pd.DataFrame) -> None:
    """Sixty entries at bar starts whose side is the sign of that bar's return: an edge that
    lives inside the bar, so acting a bar late loses it."""
    close = bars["close"].to_numpy()
    rows = []
    for i in range(1, 61):
        side = 1 if close[i] >= close[i - 1] else -1
        t = bars.index[i]
        rows.append({"entry_time": str(t), "exit_time": str(t + timedelta(hours=1)),
                     "side": side, "entry": float(close[i - 1]), "exit": float(close[i]),
                     "r_multiple": 0.5 * side, "reason": "ttl", "phase": "forward"})
    out = root / "reports" / "shadow"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ledger_XAUUSD_session_range_breakout_asia.json").write_text(json.dumps(rows),
                                                                        encoding="utf-8")


def _write_fills(root: Path) -> int:
    corpus = []
    for i in range(12):
        at = TAPE_DAY + timedelta(hours=1, minutes=10 * i)
        side = "buy" if i % 2 == 0 else "sell"
        corpus.append({"symbol": "XAUUSD", "sleeve": SLEEVE["name"], "decided_at": at.isoformat(),
                       "sent_at": "", "side": side, "lots": 0.01 + 0.01 * (i % 3),
                       "order_type": "market", "requested_price": 4300.0,
                       "fill_price": 4300.0 + (0.05 if side == "buy" else -0.05),
                       "filled_frac": 1.0, "rejected": False, "reject_reason": "",
                       "latency_decision_to_send_ms": 100.0 + i, "status": "FILLED"})
    for i in range(3):
        at = TAPE_DAY + timedelta(hours=4, minutes=5 * i)
        corpus.append({"symbol": "XAUUSD", "sleeve": SLEEVE["name"], "decided_at": at.isoformat(),
                       "side": "buy", "lots": 0.01, "order_type": "pending_stop",
                       "requested_price": 4310.0, "fill_price": None, "filled_frac": 0.0,
                       "rejected": True, "reject_reason": "invalid_stops", "status": "REJECTED"})
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "fill_corpus.jsonl").write_text("\n".join(json.dumps(r) for r in corpus),
                                            encoding="utf-8")
    intents = [{"sleeve": SLEEVE["name"], "symbol": "XAUUSD", "side": "sell", "lot": 0.02,
                "intended": 4301.0, "retcode": 10009, "latency_ms": 90.0,
                "time": (TAPE_DAY + timedelta(hours=6)).isoformat()},
               {"sleeve": SLEEVE["name"], "symbol": "XAUUSD", "side": "buy", "lot": 0.02,
                "intended": 4301.0, "retcode": 10016, "latency_ms": 95.0,
                "time": (TAPE_DAY + timedelta(hours=6, minutes=1)).isoformat()}]
    (data / "order_intents.jsonl").write_text("\n".join(json.dumps(r) for r in intents),
                                              encoding="utf-8")
    ledger = [{"time": (TAPE_DAY + timedelta(hours=7, minutes=i)).isoformat(),
               "sleeve": SLEEVE["name"], "symbol": "XAUUSD", "side": 0, "volume": 0.01,
               "fill_price": 4302.0, "entry_price": 4300.0, "sl": 4295.0, "tp": 4310.0}
              for i in range(4)]
    (data / "live_ledger.jsonl").write_text("\n".join(json.dumps(r) for r in ledger),
                                            encoding="utf-8")
    return len(corpus) + len(intents)


def _plant(root: Path, *, delay_hours: float | None) -> float:
    bars = _bars()
    (root / "data" / "universe").mkdir(parents=True, exist_ok=True)
    bars.to_parquet(root / "data" / "universe" / "XAUUSD_H1.parquet")
    last = _write_tape(root, bars, delay_hours=delay_hours)
    _write_ledger(root, bars)
    _write_fills(root)
    (root / "data" / "sleeves.json").write_text(json.dumps({"sleeves": [
        SLEEVE, {**SLEEVE, "name": "xau_srb_asia_standby", "status": "STANDBY"}]}),
        encoding="utf-8")
    (root / "logs").mkdir(exist_ok=True)
    (root / "logs" / "gateway.log").write_text(
        "2026-09-16T01:00:00+00:00 [x] OPEN ticket 1 -> retcode=10009\n"
        "2026-09-16T01:00:01+00:00 [x] OPEN ticket 2 -> retcode=10016 Invalid stops\n",
        encoding="utf-8")
    return last


@pytest.fixture
def registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    yield
    R.set_path(None)


def test_dry_run_measures_and_writes_nothing(tmp_path: Path, registry) -> None:
    last = _plant(tmp_path, delay_hours=None)
    doc = fcl.run(part="all", dry_run=True, base=tmp_path, now_ms=last + 1000.0)
    assert doc["observatory"]["n_observed"] == 1
    assert doc["impact"]["inputs"]["orders_sent"] == 17
    assert not (tmp_path / "data" / "feed_health.json").exists()
    assert not (tmp_path / "reports" / "FEED_CLOCK_LAB.json").exists()
    assert not (tmp_path / "reports" / "IMPACT_LAB.json").exists()
    assert not (tmp_path / "data" / "intelligence").exists()
    assert R.discoveries() == []
    assert doc["observatory"]["registry"]["status"] == "DRY_RUN"
    assert doc["impact"]["registry"]["status"] == "DRY_RUN"


def test_a_live_pass_stamps_feed_health_that_the_roster_hook_reads_as_input(
        tmp_path: Path, registry) -> None:
    last = _plant(tmp_path, delay_hours=None)
    fcl.run(part="all", dry_run=False, base=tmp_path, now_ms=last + 1000.0)
    health = json.loads((tmp_path / "data" / "feed_health.json").read_text(encoding="utf-8"))
    xau = health["instruments"]["XAUUSD"]
    assert xau["in_session"] is True and xau["status"] in ("MEASURED", "PARTIAL")
    assert xau["p_trustworthy"] is not None and xau["p_trustworthy"] > 0.5
    assert health["p_market_trustworthy"] == xau["p_trustworthy"]
    assert "never a cap" in health["input_not_cap"] and health["consumers"]
    report = json.loads((tmp_path / "reports" / "FEED_CLOCK_LAB.json").read_text("utf-8"))
    inst = report["instruments"]["XAUUSD"]
    assert inst["receipt"]["status"] == "MEASURED" and 30_000 <= inst["receipt"]["p50"] < 32_100
    assert inst["reference"]["status"] == "MEASURED"
    assert inst["reference"]["best_lag_ms"] == 0.0 and inst["reference"]["venue_offset_h"] == 0.0
    assert inst["continuity_venue_stamp"]["inversions"] == 0
    assert report["propagation_graph"]["n_nodes"] == 1          # one instrument: no pairs
    assert report["timing_fragility"][0]["verdict"] == "TIMING_ROBUST"
    assert report["fragility_summary"]["TIMING_FRAGILE"] == 0
    # THE HOOK: the reading rides on the sleeve row as an input and filters nothing.
    rows = [{"symbol": "XAUUSD", "name": "a"}, {"symbol": "EURUSD", "name": "b"}]
    assert core.stamp_feed_health(rows, tmp_path / "data" / "feed_health.json") == 1
    assert rows[0]["feed_health"]["p_trustworthy"] == xau["p_trustworthy"]
    assert rows[0]["feed_health"]["input_not_cap"] is True
    assert "feed_health" not in rows[1]                          # absent, never 0
    assert core.stamp_feed_health(rows, tmp_path / "data" / "absent.json") == 0
    impact = json.loads((tmp_path / "reports" / "IMPACT_LAB.json").read_text("utf-8"))
    assert impact["fill_probability"]["all"]["n"] == 17
    assert impact["fill_probability"]["all"]["filled"] == 13
    assert impact["rejection_behaviour"]["by_reason"]["invalid_stops"] == 4
    assert impact["inputs"]["tape_join_sent"]["joined"] == 17
    assert impact["slippage_by_order_type"]["market"]["n"] == 12
    assert impact["gateway_log_retcodes"]["retcodes"] == {"10009 done": 1, "10016 invalid_stops": 1}


def test_a_timing_fragile_sleeve_is_flagged_and_recorded(tmp_path: Path, registry) -> None:
    last = _plant(tmp_path, delay_hours=8.0)          # receipt delays of hours, measured
    doc = fcl.run(part="observatory", dry_run=False, base=tmp_path, now_ms=last + 1000.0)
    rows = {r["sleeve"]: r for r in doc["observatory"]["timing_fragility"]}
    live = rows["xau_srb_asia_test"]
    assert live["verdict"] == "TIMING_FRAGILE", live
    assert live["noise"]["jitter_ms"] > 3_600_000.0 / 2
    assert live["retained_at_measured_noise"] < 0.5
    assert rows["xau_srb_asia_standby"]["verdict"] == "TIMING_FRAGILE"
    assert doc["observatory"]["registry"]["status"] == "OK"
    assert doc["observatory"]["registry"]["discoveries"] == 2
    disc = R.discoveries()
    assert len(disc) == 2 and all(d["mechanism"].startswith("timing_fragility") for d in disc)
    prior = [m for m in R.memories(category="candidate_prior")
             if m.get("memory_key") == "prior:timing_fragile"]
    assert len(prior) == 1
    payload = json.loads(prior[0]["payload_json"])
    assert len(payload["fragile_specs"]) == 2
    assert "routes" in payload["routes_not_sizes"]


def test_the_impact_pass_donates_seeds_in_the_seat_shape(tmp_path: Path, registry) -> None:
    last = _plant(tmp_path, delay_hours=None)
    doc = fcl.run(part="impact", dry_run=False, base=tmp_path, now_ms=last + 1000.0)
    files = sorted((tmp_path / "data" / "intelligence" / "feed_clock_lab").glob(
        "discoveries_*.json"))
    assert len(files) == 1
    donated = json.loads(files[0].read_text(encoding="utf-8"))
    assert donated["source"] == "feed_clock_lab" and donated["discoveries"]
    seed = donated["discoveries"][0]
    assert seed["symbols"] == ["XAUUSD"] and seed["family"] == "session_range_breakout"
    assert seed["kind"] in ("hypothesis", "execution_cell")
    assert seed["session"] in doc["impact"]["session_cost_curve"]["XAUUSD"]
    cells = doc["impact"]["execution_cells"]
    assert any(c["status"] == "MEASURED" for c in cells)
    assert doc["impact"]["registry"]["discoveries"] >= 1
    assert all(d["mechanism"].startswith("execution_cell") for d in R.discoveries())
    assert doc["impact"]["toxicity"]["short"]["state"] in ("TOXIC", "BENIGN", "MIXED")
