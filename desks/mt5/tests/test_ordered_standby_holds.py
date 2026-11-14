"""An ordered STANDBY holds against both restorers (measured on the trading box 2026-10-14).

The 2026-10-13 21:30Z stop-the-bleed set the AUDCHF/EURZAR/USDZAR gap-decay principals to STANDBY
with `standby_reason` naming the principal's order. `heal_silent_demotions` read no such field,
called the demotion silent and lifted the rows back to LIVE at 0.10 (EURZAR 21:50Z, USDZAR 23:50Z,
AUDCHF 01:50Z); the promoter's capital reconciliation would have done the same on an admitting
reading from the funded book. Only the CERT_BOOK_LIVE 0.0 overlay stood between them and an order.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import promoter  # noqa: E402

_HOLD = "stop_the_bleed_2026-10-13: zuck removed AUDCHF/ZAR from Fusion live; forward-only"
_NOW = datetime(2026, 10, 14, 2, 0, tzinfo=UTC)


def _ordered(**over) -> dict:
    row = {"name": "audchf_gap", "status": "STANDBY", "risk_frac": 0.0, "standby_reason": _HOLD,
           "standby_ordered_by": "zuck cmsg stop-the-bleed",
           "standby_until": (_NOW + timedelta(days=7)).isoformat()}
    return {**row, **over}


@pytest.fixture()
def healer(tmp_path, monkeypatch):
    path = _DESK / "scripts" / "heal_silent_demotions.py"
    spec = importlib.util.spec_from_file_location("heal_silent_demotions_h", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sleeves = tmp_path / "sleeves.json"
    monkeypatch.setattr(mod, "SLEEVES", sleeves)

    def run(rows: list[dict]) -> dict[str, str]:
        sleeves.write_text(json.dumps({"sleeves": rows}), encoding="utf-8")
        mod.heal(apply=True)
        doc = json.loads(sleeves.read_text(encoding="utf-8"))
        return {r["name"]: r["status"] for r in doc["sleeves"]}
    return run


def test_the_stop_the_bleed_standby_reason_is_never_lifted(healer) -> None:
    got = healer([_ordered()])
    assert got["audchf_gap"] == "STANDBY"


def test_the_reason_list_is_explicit_so_a_stale_key_never_blocks_a_restore(healer) -> None:
    # Audit 2026-11-11: a `*_reason` wildcard let any stale key keep a silently demoted row
    # down for good. Only the named fields count.
    got = healer([{"name": "a", "status": "STANDBY", "hold_reason": "stale note"},
                  {"name": "b", "status": "STANDBY", "restore_reason": "funded at 5.5% heat"}])
    assert got == {"a": "LIVE", "b": "LIVE"}


def _reconcile(monkeypatch, row: dict) -> dict:
    monkeypatch.setattr(promoter, "capital_verdict", lambda *a, **k: {
        "status": "LIVE", "risk_frac": 0.03, "streak": 2, "delta_elogw_per_day": 0.0004,
        "why": "already funded by the allocator at 5.50% heat"})
    monkeypatch.setattr(promoter, "note_door", lambda *a, **k: None)
    monkeypatch.setattr(promoter, "plog", lambda *a, **k: None)
    sleeves = [row]
    promoter.reconcile_capital(sleeves, {"fresh": True, "at": "2026-10-14T00:00:00+00:00",
                                         "admission_at": "2026-10-14T01:00:00+00:00"},
                               now=_NOW)
    return sleeves[0]


def test_the_promoter_records_the_reading_but_keeps_an_ordered_standby(monkeypatch) -> None:
    row = _reconcile(monkeypatch, _ordered())
    assert (row["status"], row["risk_frac"]) == ("STANDBY", 0.0)
    assert row["admission"]["status"] == "LIVE" and row["admit_streak"] == 2
    # Rule 1: the held reading books what it forwent.
    (line,) = row["hold_missed_growth"]
    assert line["delta_elogw_per_day"] == 0.0004 and line["risk_frac_foregone"] == 0.03


@pytest.mark.parametrize("over", [
    {"standby_until": (_NOW - timedelta(minutes=1)).isoformat()},     # expired
    {"standby_ordered_by": ""},                                       # nobody ordered it
    {"standby_until": "next week"},                                   # malformed
    {"standby_until": "2026-10-20T00:00:00"},                         # no timezone
])
def test_an_expired_or_malformed_hold_falls_back_to_promotion(monkeypatch, over) -> None:
    row = _reconcile(monkeypatch, _ordered(**over))
    assert (row["status"], row["risk_frac"]) == ("LIVE", 0.03)
    assert "standby_reason" not in row and row["hold_lapsed"]["standby_reason"] == _HOLD


def test_missed_growth_bills_the_held_rows(tmp_path, monkeypatch) -> None:
    import missed_growth as mg
    row = _reconcile(monkeypatch, _ordered())
    p = tmp_path / "sleeves.json"
    p.write_text(json.dumps({"sleeves": [row, {"name": "free", "status": "LIVE"}]}), "utf-8")
    out = mg.ordered_hold_lines(p)
    assert out["verdict"] == mg.COSTS and out["rows_held_now"] == ["audchf_gap"]
    assert out["lost_elogw_per_day"] == 0.0004
    p.write_text(json.dumps({"sleeves": [{"name": "free", "status": "LIVE"}]}), "utf-8")
    assert mg.ordered_hold_lines(p)["verdict"] == mg.NOT_BINDING
    assert mg.ordered_hold_lines(tmp_path / "absent.json")["verdict"] == mg.UNMEASURED


def test_the_promoters_own_standby_is_still_restored_on_evidence(monkeypatch) -> None:
    row = _reconcile(monkeypatch, {"name": "x", "status": "STANDBY", "risk_frac": 0.0,
                                   "demote_reason": "the optimiser gives it 0.0000% heat"})
    assert (row["status"], row["risk_frac"]) == ("LIVE", 0.03)


def test_a_legacy_hold_is_migrated_not_lapsed_on_landing(monkeypatch) -> None:
    # Audit 2026-11-11: the stop-the-bleed rows on the box carry standby_reason alone. Landing
    # the bounded-hold rule must not lift them; they get an orderer and a 14-day expiry.
    row = _reconcile(monkeypatch, {"name": "audchf_gap", "status": "STANDBY", "risk_frac": 0.0,
                                   "standby_reason": _HOLD})
    assert (row["status"], row["risk_frac"]) == ("STANDBY", 0.0)
    assert _HOLD in row["standby_ordered_by"]
    assert row["standby_until"] == (_NOW + timedelta(days=14)).isoformat(timespec="seconds")
    assert len(row["hold_missed_growth"]) == 1 and "hold_lapsed" not in row
    # Fifteen days on, the expiry ends it and the admitted row promotes.
    monkeypatch.setattr(promoter, "capital_verdict", lambda *a, **k: {
        "status": "LIVE", "risk_frac": 0.03, "streak": 2, "delta_elogw_per_day": 0.0004,
        "why": "funded"})
    promoter.reconcile_capital([row], {"fresh": True, "at": "2026-10-29T00:00:00+00:00",
                                       "admission_at": "2026-10-29T01:00:00+00:00"},
                               now=_NOW + timedelta(days=15))
    assert row["status"] == "LIVE" and "expired" in row["hold_lapsed"]["why"]
