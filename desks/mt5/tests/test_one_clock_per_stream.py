"""Keys that took identical forward entries are one bet: one promotion candidate per stream.

Auditor HOLD_gbpchf_formula_promotion (2026-11-05), must-fix 2.
"""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK))

import shadow_forward as sf  # noqa: E402

PC = "PROMOTION CANDIDATE"


def _row(sid, status=PC, exp=0.1):
    return {"status": status, "exp_r": exp, "entry_stream": {"id": sid, "n": 29}}


def _reg(live=(), retired=None):
    return lambda: (set(live), dict(retired or {}))


def test_one_stream_keeps_one_candidate_under_its_best_key():
    state = {"a": _row("s1", exp=0.1), "b": _row("s1", exp=0.3), "c": _row("s1", exp=0.3),
             "d": _row("s2"), "e": _row(None), "last_run": "x"}
    sf.apply_stream_peers(state, registry=_reg())
    assert state["b"]["status"] == PC
    assert state["a"]["status"] == state["c"]["status"] == sf.STREAM_PEER
    assert state["a"]["stream_peer_of"] == "b"
    assert state["d"]["status"] == state["e"]["status"] == PC


def test_a_stream_with_a_live_key_keeps_that_key_and_never_relabels_live():
    state = {"live": _row("s1", exp=0.0), "live2": _row("s1", exp=0.0), "x": _row("s1", exp=9.0)}
    sf.apply_stream_peers(state, registry=_reg({"live", "live2"}))
    assert state["live"]["status"] == state["live2"]["status"] == PC
    assert state["x"]["status"] == sf.STREAM_PEER and state["x"]["stream_peer_of"] == "live"


def test_a_peer_gets_its_verdict_back_when_its_stream_becomes_its_own():
    state = {"a": _row("s1", exp=0.1), "b": _row("s1", exp=0.3)}
    sf.apply_stream_peers(state, registry=_reg())
    assert state["a"]["status"] == sf.STREAM_PEER
    state["a"]["entry_stream"] = {"id": "s9", "n": 30}           # its entries diverged
    sf.apply_stream_peers(state, registry=_reg())
    assert state["a"]["status"] == PC and state["a"]["stream_peer_of"] is None


def test_a_retired_representative_decides_its_stream_and_no_twin_comes_back():
    state = {"a": _row("s1", exp=0.1), "b": _row("s1", exp=0.3), "c": _row("s1", exp=0.2)}
    sf.apply_stream_peers(state, registry=_reg())
    state["b"]["status"] = "KILL"                                 # the promoter retired it
    sf.apply_stream_peers(state, registry=_reg())
    assert state["a"]["status"] == state["c"]["status"] == sf.STREAM_PEER
    assert state["a"]["stream_peer_of"] == "b"


def test_a_registry_or_gateway_retirement_decides_the_stream_too():
    for retired in ({"r": "registry RETIRED"}, {"r": "GATEWAY_RETIRED"}):
        state = {"r": _row("s1", status="ACTIVE"), "x": _row("s1", exp=5.0)}
        sf.apply_stream_peers(state, registry=_reg(retired=retired))
        assert state["x"]["status"] == sf.STREAM_PEER and state["x"]["stream_peer_of"] == "r"


def test_a_live_key_outside_the_verdict_still_anchors_its_stream():
    state = {"live": _row("s1", status="ACTIVE"), "x": _row("s1", exp=9.0)}
    sf.apply_stream_peers(state, registry=_reg({"live"}))
    assert state["x"]["status"] == sf.STREAM_PEER and state["live"]["status"] == "ACTIVE"


def test_an_unreadable_registry_changes_nothing():
    state = {"a": _row("s1"), "b": _row("s1")}
    lines = sf.apply_stream_peers(state, registry=lambda: None)
    assert state["a"]["status"] == state["b"]["status"] == PC and "UNMEASURED" in lines[0]


def test_the_peer_status_is_decided_terminal_and_never_promoted():
    assert sf._is_terminal(sf.STREAM_PEER)
    import forward_enrolment as fe
    assert any(sf.STREAM_PEER.startswith(d + "_") for d in fe.DECIDED_STATUSES)
    promoter_src = (DESK / "research" / "promoter.py").read_text(encoding="utf-8")
    assert 'if st.get("status") != "PROMOTION CANDIDATE":' in promoter_src


def test_the_pass_applies_it_before_the_final_save():
    src = (DESK / "research" / "shadow_forward.py").read_text(encoding="utf-8")
    i = src.index("for _line in apply_stream_peers(state):")
    assert i < src.index("_persist_state(state_path, state, final=True)")
