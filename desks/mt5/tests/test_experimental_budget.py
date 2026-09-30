"""Tier-1 audit #18: principal-override sleeves in their own ledger and budget; the separated
book is a shadow behind an OFF switch."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import experimental_budget as xb  # noqa: E402

ROWS = [
    {"name": "cert_a", "symbol": "XAUUSD", "status": "LIVE", "risk_frac": 0.05,
     "certificate": "c1"},
    {"name": "exp_live", "symbol": "XAUUSD", "status": "LIVE", "risk_frac": 0.01,
     "principal_override": {"by": "principal", "why": "second bracket"}},
    {"name": "exp_standby", "symbol": "XAUUSD", "status": "STANDBY", "risk_frac": 0.0,
     "principal_override": {"by": "principal", "why": "third bracket"}},
]


def _point(monkeypatch, tmp_path, rows=ROWS):
    (tmp_path / "sleeves.json").write_text(json.dumps({"sleeves": rows}), "utf-8")
    (tmp_path / "live.jsonl").write_text(
        json.dumps({"sleeve": "exp_live", "r_multiple": -1.0}) + "\n"
        + json.dumps({"sleeve": "exp_live", "r_multiple": 2.0}) + "\n", "utf-8")
    monkeypatch.setattr(xb, "SLEEVES", tmp_path / "sleeves.json")
    monkeypatch.setattr(xb, "LEDGER", tmp_path / "live.jsonl")
    monkeypatch.setattr(xb, "BUDGET", tmp_path / "budget.json")
    monkeypatch.setattr(xb, "POLICY", tmp_path / "policy.json")
    monkeypatch.setattr(xb, "EXP_LEDGER", tmp_path / "exp_ledger.jsonl")
    monkeypatch.setattr(xb, "CODE_ROOTS", (tmp_path,))
    monkeypatch.setattr(xb, "ROOT", tmp_path)


def test_usage_is_measured_and_an_undeclared_budget_says_so(monkeypatch, tmp_path):
    _point(monkeypatch, tmp_path)
    doc, events = xb.build(datetime(2026, 9, 29, tzinfo=UTC))
    u = doc["usage"]
    assert u["experimental_heat"] == 0.01 and u["institutional_heat"] == 0.05
    assert u["n_experimental"] == 2 and u["n_experimental_live"] == 1
    assert u["experimental_realised_r"] == 1.0
    assert doc["budget"]["status"] == "UNDECLARED"
    assert {e["event"] for e in events} == {"APPEARED"} and len(events) == 2


def test_declared_budget_reads_within_or_over(monkeypatch, tmp_path):
    _point(monkeypatch, tmp_path)
    (tmp_path / "budget.json").write_text(json.dumps({"max_heat": 0.005, "by": "p"}), "utf-8")
    assert xb.build()[0]["budget"]["status"] == "OVER"
    (tmp_path / "budget.json").write_text(json.dumps({"max_heat": 0.02, "by": "p"}), "utf-8")
    assert xb.build()[0]["budget"]["status"] == "WITHIN"


def test_ledger_is_append_only_and_records_change_and_removal(monkeypatch, tmp_path):
    _point(monkeypatch, tmp_path)
    now = datetime(2026, 9, 29, tzinfo=UTC)
    _, ev1 = xb.build(now)
    with (tmp_path / "exp_ledger.jsonl").open("a", encoding="utf-8") as fh:
        for e in ev1:
            fh.write(json.dumps(e) + "\n")
    assert xb.build(now)[1] == []                      # nothing changed: nothing appended
    rows = [dict(r) for r in ROWS]
    rows[1]["risk_frac"] = 0.02
    rows = [r for r in rows if r["name"] != "exp_standby"]
    _point(monkeypatch, tmp_path, rows)
    _, ev2 = xb.build(now)
    assert sorted(e["event"] for e in ev2) == ["CHANGED", "REMOVED"]


def test_separated_book_is_a_shadow_behind_an_off_switch(monkeypatch, tmp_path):
    _point(monkeypatch, tmp_path)
    doc, _ = xb.build()
    shadow = doc["separated_book_shadow"]
    assert xb.SEPARATE_EXPERIMENTAL_BOOK is False and shadow["feeds_live"] is False
    assert shadow["institutional_book"] == {"cert_a": 0.05}
    assert shadow["experimental_book"] == {"exp_live": 0.01}
    for rel in ("desks/mt5/mt5desk/gateway.py", "desks/mt5/research/pf_allocator.py",
                "desks/mt5/research/promoter.py"):
        assert "EXPERIMENTAL_BUDGET" not in (ROOT / rel).read_text("utf-8"), rel


def test_code_overrides_are_listed_with_their_rule_path(monkeypatch, tmp_path):
    _point(monkeypatch, tmp_path)
    (tmp_path / "promoter_x.py").write_text("# PRINCIPAL OVERRIDE (2026-09-11): lift a bar\n",
                                            "utf-8")
    rows = xb.code_overrides()
    assert len(rows) == 1 and rows[0]["on_rule_path"] is True
