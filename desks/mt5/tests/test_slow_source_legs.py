"""The organs that were built and scheduled by nothing, now on the hourly cycle (2026-09-25).

COT (stopped 2026-08-11), the broker-clock measurement, certificate hygiene, the registry's
cost model, the terminal's tick values, the refused-clock re-enrolment and the orthogonal
frontier. Each slow source runs on its OWN clock (`LEG_CADENCE_S`), marks itself only on a
completed run, and names why it wrote nothing when it is not due.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK / "scripts"), str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hourly_cycle as hc  # noqa: E402

NEW_LEGS = ("cot_fetch", "broker_clock", "fetch_universe", "refresh_cost_fields",
            "certificate_hygiene", "universe_reenrol", "orthogonal_frontier")


def test_every_new_leg_is_costed_layered_and_placed():
    from libs.research import layers
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    for leg in NEW_LEGS:
        assert f'_costed("{leg}"' in src, leg
        assert leg in layers.LEG_LAYER, leg
    assert layers.unassigned() == []
    for leg in ("cot_fetch", "broker_clock", "fetch_universe", "refresh_cost_fields"):
        assert hc.department_of(leg) == "data"
    assert hc.department_of("certificate_hygiene") == "validate"
    assert hc.department_of("orthogonal_frontier") == "discovery"
    assert "universe_reenrol" in hc.CORE_LEGS
    assert hc.in_plan("universe_reenrol", "core")
    assert hc.in_plan("cot_fetch", "dept:data") and not hc.in_plan("cot_fetch", "core")


def test_the_live_desk_liveness_page_runs_every_core_pass():
    from libs.research import layers
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("live_alive"' in src and "scripts/check_live_desk_alive.py" in src
    assert "live_alive" in hc.CORE_LEGS and hc.in_plan("live_alive", "core")
    assert layers.LEG_LAYER["live_alive"] == "meta"


def test_the_frontier_is_compiled_in_the_same_pass():
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert src.index('_costed("orthogonal_frontier"') < src.index('_costed("compile_candidates"')


def test_a_cadenced_leg_runs_marks_and_then_names_why_it_rests(tmp_path):
    path = tmp_path / "leg_cadence.json"
    ran: list[int] = []

    def ok() -> dict:
        ran.append(1)
        return {"exit_code": 0}

    first = hc._cadenced("broker_clock", ok, path)
    assert first == {"exit_code": 0} and ran == [1]
    assert "broker_clock" in json.loads(path.read_text("utf-8"))
    second = hc._cadenced("broker_clock", ok, path)
    assert ran == [1] and second["status"] == "FRESH" and second["noop_reason"]


def test_a_failed_run_is_retried_on_the_next_pass(tmp_path):
    path = tmp_path / "leg_cadence.json"
    ran: list[int] = []

    def bad() -> dict:
        ran.append(1)
        return {"exit_code": 1}

    hc._cadenced("cot_fetch", bad, path)
    hc._cadenced("cot_fetch", bad, path)
    assert ran == [1, 1] and not path.exists()
    hc._cadenced("cot_fetch", lambda: {"exit_code": None, "timeout_s": 5}, path)
    assert not path.exists(), "a timeout is not a completed run"


def test_the_cot_source_clock_catches_every_weekly_release():
    assert hc.LEG_CADENCE_S["cot_fetch"] <= 4 * 86400
    for leg in ("broker_clock", "certificate_hygiene", "fetch_universe", "refresh_cost_fields"):
        assert hc.LEG_CADENCE_S[leg] <= 86400


def test_terminal_legs_name_why_they_skip_off_the_box(monkeypatch):
    monkeypatch.setattr(hc, "_terminal_available", lambda: False)
    for fn in (hc.fetch_universe, hc.refresh_cost_fields):
        out = fn()
        assert out["status"] == "SKIPPED" and "MetaTrader5" in out["noop_reason"]


def test_cot_fetchers_run_as_modules_from_the_desk_root(monkeypatch):
    calls: list[tuple[list[str], str]] = []

    class _R:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(cmd, **kw):
        calls.append((cmd, kw.get("cwd")))
        return _R()

    monkeypatch.setattr(hc, "_run_tree", fake_run)
    out = hc._module_leg("cot_fetch", ("mt5desk.fetch_cot", "mt5desk.fetch_tff",
                                       "mt5desk.fetch_cot_disagg"))
    assert out["exit_code"] == 0 and len(calls) == 3
    for cmd, cwd in calls:
        assert "-m" in cmd and cwd == str(hc.BASE)
    for mod in ("fetch_cot", "fetch_tff", "fetch_cot_disagg"):
        assert (DESK / "mt5desk" / f"{mod}.py").exists()


def test_reenrolment_frees_fx_and_leaves_equities_refused(tmp_path, monkeypatch):
    """The lane-vocabulary defect froze FX clocks; the policy now admits FX, never equities."""
    import reenrol_universe_refused as rr
    from research.universe_policy import may_hypothesise
    assert may_hypothesise("EURUSD") and may_hypothesise("EURNOK")
    assert not may_hypothesise("Apple")
    state = tmp_path / "shadow_state.json"
    state.write_text(json.dumps({
        "EURUSD.asia": {"status": rr.REFUSED, "n": 9, "exp_r": 0.4},
        "Apple.asia": {"status": rr.REFUSED, "n": 3, "exp_r": 0.1},
        "GBPUSD.asia": {"status": "ACTIVE", "n": 2},
    }), "utf-8")
    monkeypatch.setattr(rr, "STATE", state)
    doc = rr.measure()
    assert doc["n_eligible"] == 1 and doc["n_still_refused"] == 1
    assert rr.apply(doc) == 1
    after = json.loads(state.read_text("utf-8"))
    assert after["EURUSD.asia"]["status"] == "ACTIVE"
    assert after["Apple.asia"]["status"] == rr.REFUSED
    assert "promotion_authority" not in after["EURUSD.asia"]
