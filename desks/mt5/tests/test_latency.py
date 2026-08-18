"""221.4: eBPF and DPDK are NOT SCHEDULED FOR CONSTRUCTION. 221.3 says the only
admission criterion is the latency value curve. This tests the curve.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.latency import (  # noqa: E402
    FLAT_TOLERANCE, GRID_MS, Curve, Point, admission, build_curve)


def flat_replay(ms):
    return 0.25, 200, 0


def decaying_replay(ms):
    """Edge halves by 100ms — a genuinely latency-sensitive sleeve."""
    return 0.25 * (0.5 ** (ms / 100.0)), 200, int(ms / 50)


def dead_replay(ms):
    return -0.05, 200, 0


# ------------------------------------------------------------------ the grid

def test_the_grid_is_the_one_the_constitution_names():
    assert GRID_MS == (0, 10, 50, 100, 250, 1_000, 5_000)


def test_the_grid_is_fixed_not_chosen_after_seeing_the_curve():
    src = (_DESK / "mt5desk" / "latency.py").read_text(encoding="utf-8")
    assert "cannot be evaluated on a grid chosen after seeing its curve" in src


def test_every_grid_point_is_replayed():
    c = build_curve("gold_asia", flat_replay)
    assert {p.latency_ms for p in c.points} == set(GRID_MS)


def test_a_failed_replay_is_dropped_with_its_reason_not_scored_as_zero():
    """A failed replay is not a strategy that made no money."""
    def flaky(ms):
        if ms == 250:
            raise RuntimeError("simulator blew up")
        return 0.25, 100, 0
    c = build_curve("x", flaky)
    assert 250 not in {p.latency_ms for p in c.points}
    assert "250ms: replay failed" in c.why


def test_a_non_finite_edge_is_dropped():
    c = build_curve("x", lambda ms: (float("nan"), 100, 0))
    assert c.points == ()


# ------------------------------------------------- the answer is usually flat

def test_a_flat_curve_says_do_not_accelerate():
    c = build_curve("gold_asia", flat_replay)
    v = c.verdict()
    assert c.flat and not v["accelerate"]


def test_a_flat_curve_is_reported_as_a_licence_not_a_null_result():
    """It removes an entire category of engineering from the roadmap
    permanently, which is worth more than a fast path."""
    v = build_curve("gold_asia", flat_replay).verdict()
    assert "cheap infrastructure" in v["why"]
    assert "pure loss" in v["why"]


def test_a_sensitive_curve_finds_the_knee():
    c = build_curve("news_scalp", decaying_replay)
    assert not c.flat
    assert c.knee() in (10, 50)


def test_a_sensitive_curve_still_does_not_authorise_a_fast_path():
    """221.3 requires the recovered edge to beat cost and operational risk. A
    non-flat curve says the curve is not flat, nothing more."""
    v = build_curve("news_scalp", decaying_replay).verdict()
    assert v["accelerate"]
    assert "not that a fast path is justified" in v["why"]


def test_a_sleeve_with_no_edge_at_zero_latency_is_not_a_latency_problem():
    """Latency cannot be the problem with a strategy that does not work when it
    is infinitely fast."""
    v = build_curve("broken", dead_replay).verdict()
    assert not v["accelerate"]
    assert "infinitely fast" in v["why"]


def test_no_baseline_means_no_measurement():
    c = Curve("x", (Point(50, 0.2, 100),))
    assert not c.verdict()["accelerate"]
    assert "nothing to measure decay against" in c.verdict()["why"]


def test_sampling_noise_does_not_make_every_sleeve_look_sensitive():
    """Demanding an exactly flat curve would."""
    noisy = Curve("x", tuple(
        Point(ms, 0.25 * (1 + (0.02 if ms % 3 else -0.02)), 200)
        for ms in GRID_MS))
    assert noisy.flat


# ------------------------------------------------------------- the admission

def test_admission_refuses_when_the_curve_is_flat():
    c = build_curve("gold_asia", flat_replay)
    a = admission(c, r_value=100.0, trades_per_year=250,
                  engineering_cost=20_000, annual_infra_cost=3_000)
    assert not a["admit"] and a["recovered_per_year"] == 0.0


def test_admission_compares_recovered_edge_against_real_cost():
    c = build_curve("news_scalp", decaying_replay)
    cheap = admission(c, 100.0, 5_000, engineering_cost=1_000,
                      annual_infra_cost=500)
    dear = admission(c, 100.0, 5_000, engineering_cost=500_000,
                     annual_infra_cost=100_000)
    assert cheap["admit"] and not dear["admit"]


def test_the_improvement_is_measured_from_the_WORST_point():
    """Assuming the desk already runs near zero would credit the improvement
    with an edge it never lost."""
    c = build_curve("news_scalp", decaying_replay)
    a = admission(c, 100.0, 1_000, 1_000, 100)
    assert a["measured_from"] == "5000ms"


def test_operational_risk_is_named_rather_than_priced():
    """Pretending to price it would be worse than naming it."""
    c = build_curve("news_scalp", decaying_replay)
    a = admission(c, 100.0, 5_000, 1_000, 500)
    assert "OPERATIONAL RISK IS NOT IN THIS NUMBER" in a["unpriced"]


def test_admission_has_no_default_costs():
    """A test with a guessed engineering cost admits whatever the guesser
    wanted."""
    import inspect
    sig = inspect.signature(admission)
    for p in ("engineering_cost", "annual_infra_cost", "r_value",
              "trades_per_year"):
        assert sig.parameters[p].default is inspect.Parameter.empty


# --------------------------------------------------- no fast path was built

def test_no_low_latency_stack_is_shipped():
    """221.4: they are in the inventory and NOT SCHEDULED FOR CONSTRUCTION."""
    src = (_DESK / "mt5desk" / "latency.py").read_text(encoding="utf-8")
    for banned in ("import socket", "AF_PACKET", "dpdk", "bpf", "SO_REUSEPORT"):
        assert banned not in src.lower().replace("ebpf and dpdk", "")


def test_the_module_states_why_kernel_bypass_cannot_help_here():
    # Whitespace-normalised: the phrase spans a line wrap in the docstring.
    src = " ".join((_DESK / "mt5desk" / "latency.py")
                   .read_text(encoding="utf-8").split())
    assert "cannot remove layers that are not in the kernel" in src
    assert "broker gateway, an MT5 server, broker risk controls" in src
