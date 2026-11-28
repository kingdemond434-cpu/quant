"""Decay re-search for hand-specified families (2026-11-13).

Pinned: keys parse to specs and back; triggers are KILL, flat (n>=20, t<=0) and a one-sided
CUSUM; only a clock whose edge LIVED then broke is re-searched (never-worked and unreadable are
counted, not re-searched); moves are one axis at a time, capped, and skip existing clocks; every
donated variant is pre-registered first and the donation charges one trial per variant.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

import hand_refit as H  # noqa: E402

KEY = "AUDNZD.macro_conditional.asia@M5#atr_n=20_regime_high=0.5_side_in_high=1_ttl_bars=96"
LIVED = [0.6, -0.2, 0.8, 0.5, -0.3, 0.7] * 5 + [-1.0] * 15
NEVER = [-1.0, 0.2, -1.0, -0.8] * 10


def test_a_key_parses_and_round_trips() -> None:
    spec = H.parse_key(KEY)
    assert spec is not None and spec["family"] == "macro_conditional"
    assert spec["timeframe"] == "M5" and spec["params"]["regime_high"] == 0.5
    assert H.spec_key(spec) == KEY
    lst = H.parse_key("AUDNZD.cross_asset_residual.asia@M15#factor_symbols=['USDZAR', 'USDJPY']"
                      "_lookback=240")
    assert lst is not None and lst["params"]["factor_symbols"] == ["USDZAR", "USDJPY"]


def test_triggers_and_history() -> None:
    assert H.trigger(KEY, {"status": "KILL", "n": 30, "forward_t": -3}, [])[0] == "kill"
    assert H.trigger(KEY, {"status": "ACTIVE", "n": 25, "forward_t": -0.1}, [])[0] == "flat"
    assert H.trigger(KEY, {"status": "ACTIVE", "n": 45, "forward_t": 1.0}, LIVED)[0] == "cusum"
    assert H.trigger(KEY, {"status": "ACTIVE", "n": 5, "forward_t": 1.0}, [0.5] * 5)[0] is None
    assert H.history(LIVED)[0] == "DECAYED"
    assert H.history(NEVER)[0] == "NEVER_WORKED"
    assert H.history([])[0] == "UNMEASURED"


def test_moves_are_one_axis_capped_and_skip_clocked() -> None:
    spec = H.parse_key(KEY)
    assert spec is not None
    vs = H.variants(spec)
    assert 0 < len(vs) <= H.MAX_VARIANTS
    assert all(len(v["moved"]) == 1 for v in vs)
    clocked = H.spec_key(vs[0])
    state = {KEY: {"status": "KILL", "n": 45, "forward_t": -2.0}, clocked: {"n": 0}}
    out = H.plan(state, datetime.now(tz=UTC), forward_rs={KEY: LIVED})
    assert out["parents"] == 1 and out["variants_already_clocked"] == 1
    assert clocked not in {p["variant_key"] for p in out["proposals"]}
    never = H.plan({KEY: state[KEY]}, datetime.now(tz=UTC), forward_rs={KEY: NEVER})
    assert never["parents"] == 0 and never["triggered_by_history"] == {"NEVER_WORKED": 1}


def test_preregistered_before_donation_and_charged(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "shadow_state.json").write_text(json.dumps(
        {KEY: {"status": "KILL", "n": 45, "forward_t": -2.0}}), "utf-8")
    monkeypatch.setattr(H, "SHADOW", tmp_path / "shadow_state.json")
    monkeypatch.setattr(H, "OUT", tmp_path / "HAND_REFIT.json")
    monkeypatch.setattr(H, "PREREG", tmp_path / "prereg.jsonl")
    monkeypatch.setattr(H, "_forward_rs", lambda k: LIVED)
    calls: list[tuple[str, int, int]] = []

    def fake_donate(source: str, cands: list, tests_run: int, *a: object, **k: object) -> Path:
        assert (tmp_path / "prereg.jsonl").exists()          # written BEFORE the donation
        calls.append((source, len(cands), tests_run))
        return tmp_path / "discoveries_x.json"

    from research import proposer_common as pc
    monkeypatch.setattr(pc, "donate", fake_donate)
    monkeypatch.setattr(H, "PREREG", tmp_path / "prereg.jsonl")
    doc = H.run()
    n = doc["proposals_n"]
    assert n > 0 and calls == [("hand_refit", n, n)]
    assert len((tmp_path / "prereg.jsonl").read_text("utf-8").splitlines()) == n
    again = H.run()                                       # inside REPROPOSE_DAYS: nothing new
    assert again["proposals_n"] == 0 and again["variants_proposed_within_window"] == n


def test_the_daily_cycle_runs_it() -> None:
    src = (_DESK / "research" / "daily_cycle.py").read_text("utf-8")
    assert '("hand_refit", _hand_refit)' in src
