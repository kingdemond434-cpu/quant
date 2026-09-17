"""The live sleeve policy: what may hold the principal's capital, and the two doors that enforce
it. The forex sleeves came back twice after retirement; these tests are why a third time fails."""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK), str(DESK / "research"), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import decision_core as core  # noqa: E402
from mt5desk import live_policy as lp  # noqa: E402

FX = {"name": "chfnok_carry_asia", "symbol": "CHFNOK", "family": "carry", "status": "LIVE"}
GOLD = {"name": "gold_asia_v2", "symbol": "XAUUSD", "family": "session_range_breakout",
        "status": "LIVE"}
GOLD_M15 = {"name": "xau_m15_anti_breakout", "symbol": "XAUUSD", "timeframe": "M15",
            "family": "anti_donchian_breakout", "status": "LIVE"}
GOLD_M5 = {"name": "xau_m5_anti_momentum_ny", "symbol": "XAUUSD", "timeframe": "M5",
           "family": "anti_three_bar_momentum", "status": "LIVE"}


def test_forex_and_m15_gold_are_refused_and_gold_is_not() -> None:
    pol = lp.Policy()
    assert lp.refuse(FX, pol) and "CHFNOK" in lp.refuse(FX, pol)
    assert lp.refuse(GOLD_M15, pol) and "M15" in lp.refuse(GOLD_M15, pol)
    assert lp.refuse(GOLD, pol) is None
    assert lp.refuse(GOLD_M5, pol) is None
    assert lp.refuse({"name": "nameless", "status": "LIVE"}, pol)   # no symbol is not permission


def test_banned_family_never_takes_live_capital() -> None:
    row = {"name": "eurchf_discovered_asia", "symbol": "XAUUSD", "family": "discovered"}
    assert lp.refuse(row) and "discovered" in lp.refuse(row)


def test_an_unreadable_policy_file_falls_back_to_the_ban_not_to_permission(tmp_path) -> None:
    broken = tmp_path / "live_sleeve_policy.json"
    broken.write_text("{ this is not json", encoding="utf-8")
    pol = lp.policy(broken)
    assert pol.live_symbols == lp.DEFAULT_LIVE_SYMBOLS
    assert lp.refuse(FX, pol) is not None
    assert lp.policy(tmp_path / "absent.json").live_symbols == lp.DEFAULT_LIVE_SYMBOLS


def test_the_principal_can_widen_the_universe_only_through_the_file(tmp_path) -> None:
    p = tmp_path / "live_sleeve_policy.json"
    p.write_text(json.dumps({"live_symbols": ["XAUUSD", "CHFNOK"], "by": "principal test"}),
                 encoding="utf-8")
    pol = lp.policy(p)
    assert lp.refuse(FX, pol) is None and lp.refuse(GOLD, pol) is None
    assert lp.refuse(GOLD_M15, pol) is not None       # the M15 ban survives a widened universe


def test_the_gateway_door_drops_refused_rows_and_names_them(tmp_path) -> None:
    f = tmp_path / "sleeves.json"
    f.write_text(json.dumps({"sleeves": [FX, GOLD, GOLD_M15,
                                         {**GOLD, "name": "standby", "status": "STANDBY"}]}),
                 encoding="utf-8")
    kept, notes = core.load_sleeves_verbose(f)
    assert [r["name"] for r in kept] == ["gold_asia_v2"]
    assert len(notes) == 2 and any("chfnok" in n.lower() for n in notes)
    assert core.load_sleeves(f) == kept
    assert core.load_sleeves(tmp_path / "absent.json") == []


def test_the_promoter_writer_retires_a_refused_row_instead_of_writing_it(monkeypatch,
                                                                         tmp_path) -> None:
    import promoter

    monkeypatch.setattr(promoter, "SLEEVES_FILE", tmp_path / "sleeves.json")
    monkeypatch.setattr(promoter, "plog", lambda *a, **k: None)
    rows = [dict(FX), dict(GOLD), dict(GOLD_M15)]
    n = promoter._apply_live_policy(rows)
    assert n == 2
    assert rows[0]["status"] == "RETIRED" and rows[0]["risk_frac"] == 0.0
    assert "retire_reason" in rows[0] and rows[0]["retired_by"] == "live_policy"
    assert rows[1]["status"] == "LIVE"
    assert rows[2]["status"] == "RETIRED"


def test_a_row_the_policy_refuses_cannot_survive_a_promoter_write(monkeypatch, tmp_path) -> None:
    import promoter

    out = tmp_path / "sleeves.json"
    monkeypatch.setattr(promoter, "SLEEVES_FILE", out)
    monkeypatch.setattr(promoter, "plog", lambda *a, **k: None)
    monkeypatch.setattr(promoter, "artifact_of",
                        lambda row: {"version_hash": "h", "ok": True, "problems": []})
    promoter.save_sleeves([dict(FX), dict(GOLD)])
    written = json.loads(out.read_text(encoding="utf-8"))["sleeves"]
    live = [r for r in written if r["status"] == "LIVE"]
    assert [r["name"] for r in live] == ["gold_asia_v2"]
    assert [r["status"] for r in written if r["name"] == FX["name"]] == ["RETIRED"]
