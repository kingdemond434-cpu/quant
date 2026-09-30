"""The real gateway under a faulty MT5 double, in a sandbox (libs/tiers/gateway_drill)."""
from __future__ import annotations

import tempfile

from libs.tiers import gateway_drill as gd


def test_judge_names_each_invariant() -> None:
    assert gd.judge("healthy", {"sends": 2, "intents": 2, "decisions": ["placed", "placed"],
                                "connect": True}) == []
    b = gd.judge("tick_none", {"sends": 2, "intents": 1, "connect": True})
    assert any(x.startswith("NO_SEND_BLIND") for x in b)
    assert any(x.startswith("EVERY_SEND_JOURNALED") for x in b)
    assert gd.judge("reject_10015", {"sends": 2, "intents": 2,
                                     "decisions": ["placed"]})[0].startswith("REJECTION_COUNTED")
    assert gd.judge("terminal_down", {"connect": True})[0].startswith("DOWN_IS_FALSE")
    assert gd.judge("x", {"sends": 5, "intents": 5})[0].startswith("BOUNDED_SENDS")
    assert gd.judge("x", {"place_exc": "RuntimeError: boom"})[0].startswith("NO_CRASH")


def test_the_real_gateway_runs_in_a_temp_root_against_the_double() -> None:
    row = gd.run_fault("healthy")
    if row["status"] == "UNMEASURED":        # gateway import needs the desk's own deps
        assert "why" in row
        return
    assert row["status"] == "MEASURED", row
    obs = row["observed"]
    assert "gw_drill_" in obs["root"] and obs["root"].startswith(tempfile.gettempdir())
    assert obs["sends"] == 2 and obs["intents"] == 2
    assert row["breaches"] == []
    down = gd.run_fault("terminal_down")
    assert down["observed"]["connect"] is False
