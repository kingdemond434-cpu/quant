"""The review panel and the theory graph at the promotion door (libs/tiers/door_evidence)."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.tiers import door_evidence as de


def _ch(resolves: str, state: str = "FAILED", sev: str = "HIGH") -> dict[str, Any]:
    return {"reviewer": "r", "kind": "K", "state": state, "severity": sev,
            "resolves_when": resolves}


def test_only_candidate_specific_high_failures_count() -> None:
    row = {"challenges": [_ch("red_queen_survives"), _ch("replication_agrees"),
                          _ch("stress_x5_positive", sev="MEDIUM"),
                          _ch("forward_n_40", state="OPEN")]}
    assert de.review_failed(row) == [], "only candidate-specific HIGH failures"
    assert de.review_failed({"challenges": [_ch("stress_x5_positive")]}) == ["r:K"]


def test_theory_ignores_backtest_and_needs_min_oos() -> None:
    bt = [(False, "backtest")] * 500
    assert de.oos_posterior(bt)["status"] == "UNMEASURED", "backtest failures never refute"
    few = [(False, "forward")] * (de.MIN_OOS - 1)
    assert de.oos_posterior(few)["status"] == "UNMEASURED"
    assert de.oos_posterior([(False, "forward")] * 12)["status"] == "REFUTED"
    assert de.oos_posterior([(True, "live")] * 12)["status"] == "SUPPORTED"


def test_build_and_reason() -> None:
    rows = de.build([{"candidate": "a.EURUSD.x", "verdict": "FAILED",
                      "challenges": [_ch("forward_n_40")]},
                     {"candidate": "b.GBPUSD.y", "verdict": "CLEAR", "challenges": []},
                     {"candidate": "c.AUDUSD.z", "verdict": "CLEAR", "challenges": []}],
                    {"a.EURUSD.x": "f1", "b.GBPUSD.y": "f2", "c.AUDUSD.z": "f3"},
                    {"f2": [(False, "forward")] * 12, "f3": [(False, "backtest")] * 99})
    assert (de.door_reason(rows["a.EURUSD.x"]) or "").startswith("REVIEW_PANEL_FAILED")
    assert (de.door_reason(rows["b.GBPUSD.y"]) or "").startswith("THEORY_REFUTED")
    assert de.door_reason(rows["c.AUDUSD.z"]) is None


def test_door_reads_fresh_verdicts_and_respects_suspension(monkeypatch: Any,
                                                           tmp_path: Path) -> None:
    from libs.tiers import authority
    from libs.tiers import promotion_authority as pa
    dv = tmp_path / "door.json"
    monkeypatch.setattr(pa, "ROOT", tmp_path)
    monkeypatch.setattr(pa, "DOOR_VERDICTS", dv)
    monkeypatch.setattr(pa.firewall, "may", lambda *a, **k: True)
    monkeypatch.setattr(authority, "suspended", lambda organ, *a, **k: False)
    row = {"review_failed": ["execution:X"], "family": "f",
           "theory": {"status": "REFUTED", "n_oos": 12, "confidence": 0.1}}
    assert pa._panel_and_theory("EURUSD.x") is None, "absent file withholds nothing"
    dv.write_text(json.dumps({"generated_utc": "2020-01-01T00:00:00+00:00",
                              "rows": {"ext.EURUSD.x": row}}), "utf-8")
    assert pa._panel_and_theory("EURUSD.x") is None, "a stale file withholds nothing"
    dv.write_text(json.dumps({"generated_utc": datetime.now(UTC).isoformat(),
                              "rows": {"ext.EURUSD.x": row}}), "utf-8")
    assert (pa._panel_and_theory("EURUSD.x") or "").startswith("REVIEW_PANEL_FAILED")
    assert pa._panel_and_theory("GBPUSD.x") is None
    monkeypatch.setattr(authority, "suspended", lambda organ, *a, **k: organ == "review")
    assert (pa._panel_and_theory("EURUSD.x") or "").startswith("THEORY_REFUTED")
    monkeypatch.setattr(authority, "suspended", lambda organ, *a, **k: True)
    assert pa._panel_and_theory("EURUSD.x") is None
