"""Event-sizing triggers (EVENT-SIZING, DECAY-09): equity band, swap regime, cost regime and
sleeve health each re-solve the book; a change is consumed only by a solve that ran."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from research import allocator_trigger as at  # noqa: E402


def test_new_kinds_are_watched() -> None:
    kinds = {s.kind for s in at.sources()}
    assert {"equity_move", "swap_regime", "cost_regime", "sleeve_health"} <= kinds
    keys = [f"{s.kind}:{s.path.name}" for s in at.sources()]
    assert len(keys) == len(set(keys))


def test_equity_band_ignores_noise_and_fires_on_a_band_cross() -> None:
    sig = lambda eq: at._signature({"equity": eq}, ("equity",), at._equity_band)  # noqa: E731
    base = 100_000.0
    lo = math.exp(math.floor(math.log(base) / at.EQUITY_BAND_LOG) * at.EQUITY_BAND_LOG)
    assert sig(lo * 1.001) == sig(lo * 1.002)               # inside one band: no re-solve
    assert sig(lo * 1.001) != sig(lo * 0.99)                # crossed a band
    assert at._signature({"equity": None}, ("equity",), at._equity_band) == "no-watched-key"


def test_swap_signature_moves_on_state_flip_only() -> None:
    def doc(state: str, ratio: float) -> dict[str, Any]:
        return {"symbols": {"EURUSD": {"long": {"state": state, "carry_ratio_vs_spread": ratio},
                                       "short": {"state": "CARRY-PAID"}}}}
    a = at._signature(doc("CARRY-ADVERSE", -1.0), ("symbols",), at._swap_states)
    assert a == at._signature(doc("CARRY-ADVERSE", -2.0), ("symbols",), at._swap_states)
    assert a != at._signature(doc("CARRY-PAID", -1.0), ("symbols",), at._swap_states)


def test_cost_and_health_signatures() -> None:
    c1 = at._signature({"overcharged": [{"symbol": "X", "ratio": 1.3}]}, (), at._overcharged)
    c2 = at._signature({"overcharged": [{"symbol": "X", "ratio": 1.4}]}, (), at._overcharged)
    c3 = at._signature({"overcharged": [{"symbol": "Y", "ratio": 1.3}]}, (), at._overcharged)
    assert c1 == c2 != c3
    h = lambda b: at._signature({"verdict": "OK", "hazard_summary": {"breaking": b}},  # noqa
                                (), at._health)
    assert h(["s1"]) != h([]) and h(["a", "b"]) == h(["b", "a"])


def test_equity_move_fires_the_solver_and_is_consumed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    f = tmp_path / "gateway_state.json"
    f.write_text(json.dumps({"equity": 100_000.0}), encoding="utf-8")
    calls: list[int] = []
    monkeypatch.setattr(at, "ROOT", tmp_path)
    monkeypatch.setattr(at, "sources", lambda: [
        at.Source("equity_move", f, ("equity",), "t", sig_fn=at._equity_band)])
    monkeypatch.setattr(at, "_heat_now", lambda: 0.2)
    monkeypatch.setattr(at, "_allocation_stamp", lambda: (None, None))
    monkeypatch.setattr(at, "_solve", lambda _b: calls.append(1) or
                        {"rc": 0, "wall_s": 0.0, "tail": ""})
    st = at.poll(state={}, write=False)["state"]
    f.write_text(json.dumps({"equity": 96_000.0}), encoding="utf-8")
    st["last_solve_at"] = 0.0
    out = at.poll(state=st, write=False)
    assert calls == [1] and out["fired"][0]["kind"] == "equity_move"
    row = next(iter(out["state"]["seen"].values()))
    assert row["pending"] is None and row["consumed"] == row["observed"]
    out["state"]["last_solve_at"] = 0.0
    assert at.poll(state=out["state"], write=False)["fired"] == []
    assert calls == [1]


def test_legacy_state_rows_are_read_as_consumed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    f = tmp_path / "MACRO_VIEW.json"
    f.write_text(json.dumps({"labels": 1}), encoding="utf-8")
    monkeypatch.setattr(at, "ROOT", tmp_path)
    src = at.Source("macro_surprise", f, ("labels",), "t")
    monkeypatch.setattr(at, "sources", lambda: [src])
    sig = at._signature({"labels": 1}, ("labels",))
    out = at.poll(state={"seen": {"macro_surprise:MACRO_VIEW.json": {"sig": sig}}},
                  write=False, solve=False)
    assert out["fired"] == [] and out["watch"][0]["changed"] is False


def test_failed_solves_back_off_and_a_success_resets(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert at.solve_gap(0) == at.MIN_SOLVE_GAP_S
    assert at.solve_gap(1) == 2 * at.MIN_SOLVE_GAP_S
    assert at.solve_gap(50) == at.MAX_FAILURE_GAP_S
    f = tmp_path / "gateway_state.json"
    f.write_text(json.dumps({"equity": 100_000.0}), encoding="utf-8")
    rc: list[int] = [1]
    monkeypatch.setattr(at, "ROOT", tmp_path)
    monkeypatch.setattr(at, "sources", lambda: [
        at.Source("equity_move", f, ("equity",), "t", sig_fn=at._equity_band)])
    monkeypatch.setattr(at, "_heat_now", lambda: 0.2)
    monkeypatch.setattr(at, "_allocation_stamp", lambda: (None, None))
    monkeypatch.setattr(at, "_solve", lambda _b: {"rc": rc[0], "wall_s": 0.0, "tail": ""})
    st = at.poll(state={}, write=False)["state"]
    f.write_text(json.dumps({"equity": 96_000.0}), encoding="utf-8")
    st["last_solve_at"] = 0.0
    st = at.poll(state=st, write=False)["state"]
    assert st["failure_streak"] == 1
    # 90 s after a failure is past the 60 s debounce but inside the doubled 120 s gap.
    import time as _t
    st["last_solve_at"] = _t.time() - 90.0
    out = at.poll(state=st, write=False)
    assert out["debounced"] and out["state"]["failure_streak"] == 1
    rc[0] = 0
    out["state"]["last_solve_at"] = 0.0
    assert at.poll(state=out["state"], write=False)["state"]["failure_streak"] == 0
