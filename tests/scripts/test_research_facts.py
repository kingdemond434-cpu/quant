from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), "utf-8")


def test_runnable_certificates_accept_empty_params_and_specialized_runner(
    tmp_path: Path, monkeypatch,
) -> None:
    import scripts.build_research_facts as facts

    desk = tmp_path / "desks" / "mt5"
    out = tmp_path / "data" / "research_facts.json"
    survivors = {
        "external.empty": {"shadow_spec": {"family": "overnight_gap_decay", "params": {}}},
        "external.exact": {"shadow_spec": {"family": "session_range_breakout",
                                             "params": {"rr": 2.0}}},
        "external.lost": {"shadow_spec": {"family": "session_range_breakout"}},
        "qquant.hunt16": {"shadow_spec": {"family": "dav_range_filter_adx"}},
    }
    _write(desk / "reports" / "UNIVERSAL_SURVIVORS.json", {"survivors": survivors})
    _write(desk / "reports" / "shadow" / "qquant_shadow_state.json", {
        "processed_qquant_sleeves": 1,
    })
    _write(desk / "data" / "universe" / "universe.json", {})
    monkeypatch.setattr(facts, "ROOT", tmp_path)
    monkeypatch.setattr(facts, "DESK", desk)
    monkeypatch.setattr(facts, "OUT", out)

    assert facts.main() == 0
    got = json.loads(out.read_text("utf-8"))["certificates"]
    assert got["total"] == 4
    assert got["exact_param_runnable"] == 2
    assert got["specialized_runner_runnable"] == 1
    assert got["runnable"] == 3
    assert got["unrunnable_no_params"] == 1
