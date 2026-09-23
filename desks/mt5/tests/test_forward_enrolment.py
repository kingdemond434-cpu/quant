"""FORWARD ENROLMENT -- every certificate gets a clock, immediately, and there is no quota.

What is fenced here, and why each one is the thing that would actually go wrong:

  * A NEW CERTIFICATE IS ENROLLED WITH ZERO LATENCY. The principal's order is "immediate clocks at
    the same time when certified", and the only honest way to hold the desk to it is to measure
    `enrolled_at - gated_at` and assert it is zero. A test that merely asserted "enrolled" would
    pass on a certificate that waited four days.
  * THERE IS NO CAP. The report declares `quota.capped` false, no waiting queue and no ranking
    gate, and 200 certificates produce 200 clocks -- not a page of them.
  * A CLOCKLESS CERTIFICATE IS NAMED, WITH ITS REASON AND ITS AGE, and only becomes OVERDUE after
    one cycle: the hourly repair sweep is allowed exactly its hour.
  * UNMEASURED IS NEVER ZERO (L1.28a). A clock with no `enrolled_at`, or a certificate the canon
    never stamped, reports UNMEASURED latency rather than a flattering zero.
  * THE REPAIR SWEEP RUNS ONLY WHEN THERE IS SOMETHING TO REPAIR, and never past its budget: it
    must not become a second enroller racing the `enrol_clocks` leg, and it must not hang a leg.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import forward_enrolment as fe  # noqa: E402

UNMEASURED = fe.UNMEASURED
NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


def _run(symbol="XAUUSD", family="session_range_breakout", selector="asia", side="LONG"):
    return {"symbol": symbol, "family": family, "selector": selector, "side": side, "params": {}}


def _key(run) -> str:
    return f"{run['symbol']}.{run['family']}.{run['selector']}.{run['side']}"


def _no_heavy_imports(monkeypatch) -> None:
    """Key the census off the run itself, so no test reaches the admission door or the engine."""
    monkeypatch.setattr(fe, "_run_key", _key)


# ------------------------------------------------------- the order: immediate, zero latency
def test_a_new_certificate_is_enrolled_with_zero_latency(monkeypatch) -> None:
    _no_heavy_imports(monkeypatch)
    run = _run()
    stamp = "2026-09-23T03:12:00+00:00"
    body = fe.census([run], {_key(run): {"status": "ACTIVE", "enrolled_at": stamp,
                                         "lane": "shadow_state.json"}},
                     {("XAUUSD", "session_range_breakout", "asia", "LONG"): stamp}, NOW)
    assert body["n_certificates"] == 1
    assert body["n_enrolled"] == 1
    assert body["n_missing"] == 0
    assert body["certificates"][0]["latency_h"] == 0.0
    assert body["latency_h"]["max"] == 0.0
    assert body["latency_h"]["target"] == fe.TARGET_LATENCY_H == 0.0
    assert body["latency_h"]["at_target"] is True


def test_two_hundred_certificates_produce_two_hundred_clocks_with_no_cap(monkeypatch) -> None:
    _no_heavy_imports(monkeypatch)
    runs = [_run(symbol=f"SYM{i:03d}") for i in range(200)]
    stamp = "2026-09-23T03:12:00+00:00"
    clocks = {_key(r): {"status": "ACTIVE", "enrolled_at": stamp} for r in runs}
    stamps = {(r["symbol"], r["family"], r["selector"], r["side"]): stamp for r in runs}
    body = fe.census(runs, clocks, stamps, NOW)
    assert body["n_certificates"] == 200
    assert body["n_enrolled"] == 200, "no cap, no page, no head-of-queue slice"
    assert body["latency_h"]["max"] == 0.0


def test_the_report_declares_no_quota_no_queue_and_no_ranking_gate(tmp_path, monkeypatch) -> None:
    _no_heavy_imports(monkeypatch)
    run = _run()
    stamp = "2026-09-23T03:12:00+00:00"
    monkeypatch.setattr(fe, "OUT", tmp_path / "FORWARD_ENROLMENT.json")
    monkeypatch.setattr(fe, "certificates", lambda: ([run], [], ""))
    monkeypatch.setattr(fe, "clock_rows",
                        lambda *a, **k: {_key(run): {"status": "ACTIVE", "enrolled_at": stamp}})
    monkeypatch.setattr(fe, "certification_stamps",
                        lambda: {("XAUUSD", "session_range_breakout", "asia", "LONG"): stamp})
    payload = fe.run(write=True, now=NOW, budget_s=5.0)
    doc = json.loads((tmp_path / "FORWARD_ENROLMENT.json").read_text(encoding="utf-8"))
    assert doc["quota"]["capped"] is False
    assert doc["quota"]["waiting_queue"] == 0
    assert doc["quota"]["ranking_gate"] is False
    assert "deploys NO CAPITAL" in doc["quota"]["rule"]
    assert "immutable floor is never a knob" in doc["quota"]["statistics_untouched"]
    assert payload["n_enrolled"] == 1
    assert payload["repair"]["status"] == "NOT_NEEDED"


# ------------------------------------------------------------------ the gap, named and aged
def test_a_clockless_certificate_is_named_with_its_reason_and_its_age(monkeypatch) -> None:
    _no_heavy_imports(monkeypatch)
    run = _run(symbol="USDZAR", family="overnight_gap_decay")
    gated = (NOW - timedelta(hours=91)).isoformat()
    body = fe.census([run], {}, {("USDZAR", "overnight_gap_decay", "asia", "LONG"): gated}, NOW)
    assert body["n_missing"] == 1
    row = body["missing"][0]
    assert row["enrolled"] is False
    assert row["clockless_hours"] == 91.0
    assert "NO CLOCK" in row["why"]
    assert body["n_overdue"] == 1


def test_a_certificate_minted_this_hour_is_not_yet_overdue(monkeypatch) -> None:
    _no_heavy_imports(monkeypatch)
    run = _run()
    gated = (NOW - timedelta(minutes=20)).isoformat()
    body = fe.census([run], {},
                     {("XAUUSD", "session_range_breakout", "asia", "LONG"): gated}, NOW)
    assert body["n_missing"] == 1
    assert body["n_overdue"] == 0, "the hourly repair sweep gets its hour before this is a defect"


# ----------------------------------------------------------------- UNMEASURED is never zero
def test_a_clock_without_an_enrolment_stamp_reports_unmeasured_not_zero(monkeypatch) -> None:
    _no_heavy_imports(monkeypatch)
    run = _run()
    body = fe.census([run], {_key(run): {"status": "ACTIVE"}},
                     {("XAUUSD", "session_range_breakout", "asia", "LONG"):
                      "2026-09-23T03:12:00+00:00"}, NOW)
    assert body["certificates"][0]["enrolled"] is True
    assert body["certificates"][0]["latency_h"] == UNMEASURED
    assert body["latency_h"]["max"] == UNMEASURED
    assert body["latency_h"]["at_target"] == UNMEASURED


def test_an_unstamped_certificate_reports_unmeasured_clockless_hours(monkeypatch) -> None:
    _no_heavy_imports(monkeypatch)
    body = fe.census([_run()], {}, {}, NOW)
    assert body["missing"][0]["clockless_hours"] == UNMEASURED
    assert body["n_overdue"] == 0, "a certificate with no stamp is never aged on a guess"


# ---------------------------------------------------------------------------- reading state
def test_every_lane_is_read_so_a_scalp_clock_counts(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(fe, "SHADOW_DIR", tmp_path)
    (tmp_path / "shadow_state.json").write_text(json.dumps({"A": {"status": "ACTIVE"}}), "utf-8")
    (tmp_path / "scalp_shadow_state.json").write_text(
        json.dumps({"scalp.B": {"status": "ACTIVE"}}), "utf-8")
    rows = fe.clock_rows()
    assert set(rows) == {"A", "scalp.B"}
    assert rows["scalp.B"]["lane"] == "scalp_shadow_state.json"


def test_certification_stamps_take_the_earliest_gated_at(tmp_path, monkeypatch) -> None:
    doc = {"survivors": {
        "h1.cell_a": {"gated_at": "2026-09-20T01:00:00+00:00",
                      "shadow_spec": {"symbol": "XAUUSD", "family": "session_range_breakout",
                                      "selector": "asia", "side": "LONG"}},
        "h2.cell_b": {"gated_at": "2026-09-18T01:00:00+00:00",
                      "shadow_spec": {"symbol": "XAUUSD", "family": "session_range_breakout",
                                      "selector": "asia", "side": "LONG"}}}}
    path = tmp_path / "UNIVERSAL_SURVIVORS.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(fe, "SURVIVORS", path)
    stamps = fe.certification_stamps()
    assert stamps[("XAUUSD", "session_range_breakout", "asia", "LONG")] == \
        "2026-09-18T01:00:00+00:00"


# --------------------------------------------------------------------------- the repair sweep
def test_the_repair_sweep_does_not_run_when_nothing_is_missing() -> None:
    out = fe.repair([], deadline=1e9)
    assert out["status"] == "NOT_NEEDED"
    assert out["n_missing"] == 0


def test_the_repair_sweep_defers_rather_than_overrunning_the_leg_budget() -> None:
    import time
    out = fe.repair([{"key": "X"}], deadline=time.monotonic() + 1.0)
    assert out["status"] == "SKIPPED_BUDGET"
    assert "next hourly pass" in out["why"]


def test_a_missing_engine_is_unmeasured_not_a_crash(tmp_path) -> None:
    out = fe.repair([{"key": "X"}], deadline=1e9, engine=tmp_path / "nope.py")
    assert out["status"] == UNMEASURED
