"""Pass item 54: HMM regime posterior conditions the E[log W] solve, in SHADOW only."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK))

import hmm_regime_elog_shadow as hs  # noqa: E402


def _two_state(n: int = 160, seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out, state = [], 0
    for _ in range(n):
        if rng.random() < 0.05:
            state = 1 - state
        mu = 0.6 if state == 0 else -0.6
        out.append(mu + 0.3 * rng.standard_normal())
    return np.asarray(out)


def test_conditioning_helps_on_persistent_two_state_series() -> None:
    r = _two_state()
    wf = hs.walk_forward(r)
    assert wf["status"] == "MEASURED"
    assert wf["measured_steps"] > 0
    assert wf["conditioned_logw"] > wf["plain_logw"]


def test_degenerate_fit_is_unmeasured_and_falls_back_to_plain() -> None:
    for r in (np.full(80, 0.5), np.array([0.5, -1.0, 1.0] * 5)):
        s = hs.solve_pair(r)
        assert s["status"] == "UNMEASURED"
        assert s["conditioned_fraction"] == s["plain_fraction"]
    res = hs.evaluate({"a": [0.1, -0.2]})
    assert res["verdict"] == "UNMEASURED" and res["win_rate_vs_plain"] is None


def test_never_auto_promotes(tmp_path: Path) -> None:
    led = tmp_path / "l.jsonl"
    led.write_text("")
    doc = hs.build(led)
    assert doc["auto_promote"] is False and doc["live_sizing_changed"] is False
    assert doc["mode"] == "SHADOW"


def test_leg_is_wired() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '_producer("hmm_regime_elog_shadow", "research/hmm_regime_elog_shadow.py")' in src
    assert '_costed("hmm_regime_elog_shadow", hmm_regime_elog_shadow)' in src
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["hmm_regime_elog_shadow"] == "sizing"


def test_refit_every_k_is_faster_and_still_helps() -> None:
    r = _two_state(220)
    t0 = time.perf_counter()
    every = hs.walk_forward(r, refit_every=1)
    t1 = time.perf_counter()
    sparse = hs.walk_forward(r)
    t2 = time.perf_counter()
    assert sparse["refits"] < every["refits"] and sparse["refits"] == -(-(220 - hs.MIN_FIT_N) // 10)
    assert sparse["conditioned_logw"] > sparse["plain_logw"]
    assert (t2 - t1) < (t1 - t0)
    res = hs.evaluate({"a": r})
    assert res["sleeves"]["a"]["wall_s"] >= 0


def test_verdict_needs_share_sum_and_sign_test() -> None:
    assert hs.sign_test_p(5, 5) == 1 / 32
    assert abs(hs.sign_test_p(3, 4) - 5 / 16) < 1e-12
    assert hs.sign_test_p(0, 0) is None
    assert hs.verdict_of(2, 2, 1.0)[0] == "UNMEASURED"
    assert hs.verdict_of(5, 5, 1.0)[0] == "PROMOTE_CANDIDATE"
    assert hs.verdict_of(5, 5, -0.1)[0] == "NOT_PROMOTE"      # summed delta must be positive
    assert hs.verdict_of(3, 4, 1.0)[0] == "NOT_PROMOTE"       # 75% wins but p = 0.3125
    assert hs.verdict_of(3, 5, 1.0)[0] == "NOT_PROMOTE"


def test_ledger_keys_by_account_and_dedupes(tmp_path: Path) -> None:
    rows = [
        {"account": 1, "sleeve": "s", "signal_time": "t1", "time": "t1", "r_multiple": 1.0},
        {"account": 1, "sleeve": "s", "signal_time": "t1", "time": "t1", "r_multiple": 1.0},
        {"account": 1, "sleeve": "s", "signal_time": "t2", "time": "t2", "r_multiple": -0.5},
        {"account": 2, "sleeve": "s", "signal_time": "t1", "time": "t1", "r_multiple": 2.0},
        {"sleeve": "s", "open_time": "t3", "time": "t3", "r_multiple": 0.3},
        {"sleeve": "s", "open_time": "t3", "time": "t3", "r_multiple": 0.3},
    ]
    led = tmp_path / "l.jsonl"
    led.write_text("\n".join(json.dumps(x) for x in rows), encoding="utf-8")
    out = hs.load_ledger(led)
    assert out == {("1", "s"): [1.0, -0.5], ("2", "s"): [2.0], "s": [0.3]}
    assert set(hs.evaluate(out)["sleeves"]) == {"1|s", "2|s", "s"}
