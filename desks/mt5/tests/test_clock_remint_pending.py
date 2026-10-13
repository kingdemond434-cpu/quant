"""A re-seal never retires a forward clock whose certificate is only waiting to be re-judged.

Audit 2026-10-13 (T8 blocker a): a re-seal changes the attestation, `remint_partition` lifts every
old-header row into `pending_rejudge`, `authorized_runs` stops returning them, and the strict
CLOCK-IF-AND-ONLY-IF-CERTIFICATE audit then retired every clock the desk held. A certificate
under re-mint is still a certificate: its clock is kept until the judge rules.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import clock_certificate as cc  # noqa: E402
import clock_liveness as cl  # noqa: E402


def _clock(key: str) -> dict:
    return {"lane": "main", "key": key, "symbol": key.split(".")[0], "timeframe": "H1",
            "verdict": "ACCRUING", "status": "ACTIVE"}


def _audit(tmp_path: Path, clocks: list, roster: set, pending: set | None) -> dict:
    canon = tmp_path / "canon.json"
    canon.write_text(json.dumps({"n": 1, "survivors": {"a": {}}}), encoding="utf-8")
    (tmp_path / "v.jsonl").write_text("", encoding="utf-8")
    return cc.audit(clocks, roster=roster, apply=False, canon_path=canon,
                    verdict_path=tmp_path / "v.jsonl", ledger_path=tmp_path / "b.json",
                    queue_path=tmp_path / "q.jsonl", pending=pending)


def test_a_clock_whose_certificate_is_pending_rejudge_is_kept(tmp_path: Path) -> None:
    out = _audit(tmp_path, [_clock("EURUSD.carry.continuous")], set(),
                 {"EURUSD.carry.continuous"})
    assert out["breached"] == 0 and not out["retire"]
    assert out["remint_pending"] == 1
    assert out["unbacked_live"] == 0 and out["awaiting"] == 0
    assert "pending_rejudge" in out["rows"][0]["why"]


def test_a_clock_with_no_certificate_anywhere_is_still_retired(tmp_path: Path) -> None:
    out = _audit(tmp_path, [_clock("EURUSD.carry.continuous")], set(), {"GBPUSD.carry.x"})
    assert out["breached"] == 1 and len(out["retire"]) == 1
    assert out["remint_pending"] == 0


def test_a_backed_clock_stays_backed(tmp_path: Path) -> None:
    out = _audit(tmp_path, [_clock("EURUSD.carry.continuous")], {"EURUSD.carry.continuous"},
                 {"EURUSD.carry.continuous"})
    assert out["counts"][cc.BACKED] == 1 and out["remint_pending"] == 0


def test_without_a_pending_set_the_strict_rule_is_unchanged(tmp_path: Path) -> None:
    out = _audit(tmp_path, [_clock("EURUSD.carry.continuous")], set(), None)
    assert out["breached"] == 1


def test_pending_roster_keys_match_the_engine_key(tmp_path: Path, monkeypatch) -> None:
    import shadow_forward as sf
    spec = {"symbol": "EURUSD", "selector": "continuous", "family": "carry",
            "params": {"lookback": 20}, "side": "SHORT"}
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps(
        {"survivors": {}, "pending_rejudge": {"external.x": {"shadow_spec": spec}}}),
        encoding="utf-8")
    monkeypatch.setattr(cl, "DESK", tmp_path)
    keys, why = cl.pending_roster()
    assert keys == {sf.sleeve_key("EURUSD", "continuous", {"lookback": 20}, "carry", "SHORT")}
    assert "1 certificate row" in why


def test_an_undeclared_side_contributes_both_directions(tmp_path: Path, monkeypatch) -> None:
    import shadow_forward as sf
    spec = {"symbol": "EURUSD", "selector": "continuous", "family": "carry", "params": {}}
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "UNIVERSAL_SURVIVORS.canon.json").write_text(json.dumps(
        {"pending_rejudge": {"external.x": {"shadow_spec": spec}}}), encoding="utf-8")
    monkeypatch.setattr(cl, "DESK", tmp_path)
    keys, _ = cl.pending_roster()
    assert keys == {sf.sleeve_key("EURUSD", "continuous", {}, "carry", s)
                    for s in ("LONG", "SHORT")}


def test_an_unreadable_canon_keeps_nothing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cl, "DESK", tmp_path)
    keys, _ = cl.pending_roster()
    assert keys == set()
