"""Pass item 54: HMM regime posterior conditions the E[log W] solve, in SHADOW only."""
from __future__ import annotations

import sys
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
