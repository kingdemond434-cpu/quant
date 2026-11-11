"""The one-time principal exception cannot resurrect a retired funded identity."""
import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK))
import promoter  # noqa: E402
from mt5desk import executables, kelly_sizing, live_policy  # noqa: E402


def test_principal_promotion_is_once_costed_and_retirement_final(tmp_path, monkeypatch):
    old = "audchf_overnight_gap_decay_asia_p_44136fa355b3678a"
    new = old + "_principal_20261007"
    cell = "external.AUDCHF.overnight_gap_decay.p=44136fa355b3678a"
    order = tmp_path / "promotions.json"
    order.write_text(json.dumps({"enabled": True, "by": "principal", "fusion": [{
        "source_name": old, "name": new, "certificate": cell,
        "book_key": "AUDCHF_overnight_gap_decay_asia"}]}), encoding="utf-8")
    book = tmp_path / "book.json"
    book.write_text(json.dumps({"enabled": True, "fusion": {
        "AUDCHF_overnight_gap_decay_asia": 0.1}}), encoding="utf-8")
    monkeypatch.setattr(promoter, "PRINCIPAL_PROMOTIONS", order)
    monkeypatch.setattr(kelly_sizing, "CERT_BOOK_FILE", book)
    monkeypatch.setattr(promoter, "regrade_failures", lambda: {})
    monkeypatch.setattr(promoter, "regrade_block", lambda *_: None)
    monkeypatch.setattr(promoter, "blind_review_veto", lambda *_: None)
    monkeypatch.setattr(promoter, "tier_s_block", lambda *_: None)
    monkeypatch.setattr(promoter, "cost_basis_of", lambda *_: ("cost-digest", "fixture"))
    monkeypatch.setattr(promoter, "note_door", lambda *_, **__: None)
    monkeypatch.setattr(live_policy, "policy", lambda: {})
    monkeypatch.setattr(live_policy, "refuse", lambda *_, **__: None)
    monkeypatch.setattr(executables, "executor_gap", lambda *_: None)
    sleeves = [{"name": old, "symbol": "AUDCHF", "family": "overnight_gap_decay",
                "selector": "asia", "status": "RETIRED", "risk_frac": 0,
                "retire_reason": "principal 2026-09-16: keep only the gold sleeves",
                "certificate": {"cell": cell}}]
    changed, held = promoter.apply_principal_promotions(sleeves)
    assert changed and held == {new} and len(sleeves) == 2
    assert sleeves[0]["status"] == "RETIRED"
    assert sleeves[1]["status"] == "LIVE" and sleeves[1]["cost_hash"] == "cost-digest"
    assert promoter.apply_principal_promotions(sleeves) == (False, {new})
    assert len(sleeves) == 2
    sleeves[1]["status"] = "RETIRED"
    assert promoter.apply_principal_promotions(sleeves) == (False, set())
    assert len(sleeves) == 2


def test_disabled_book_demotes_principal_row(tmp_path, monkeypatch):
    order = tmp_path / "promotions.json"
    order.write_text(json.dumps({"enabled": True, "fusion": [{
        "source_name": "old", "name": "new", "certificate": "cell", "book_key": "KEY"}]}))
    book = tmp_path / "book.json"
    book.write_text(json.dumps({"enabled": False, "fusion": {"KEY": 0.1}}))
    monkeypatch.setattr(promoter, "PRINCIPAL_PROMOTIONS", order)
    monkeypatch.setattr(kelly_sizing, "CERT_BOOK_FILE", book)
    monkeypatch.setattr(live_policy, "policy", lambda: {})
    row = {"name": "new", "status": "LIVE", "risk_frac": 0.1,
           "principal_source": "old", "principal_certificate": "cell"}
    changed, held = promoter.apply_principal_promotions([row])
    assert changed and held == set()
    assert row["status"] == "STANDBY" and row["risk_frac"] == 0
