"""The account snapshot is one authoritative ledger: balance, equity, margin, swap, positions.

The recovery drills grade `account_ledger` on exactly these fields; a restore or reconciliation
must be able to read the open book from this one record."""
from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[2]


def _load(monkeypatch, tmp_path):
    fake = types.ModuleType("MetaTrader5")
    fake.account_info = lambda: NS(login=1, company="Venue", server="S", currency="EUR",
                                   balance=1000.0, equity=990.0, margin_free=900.0,
                                   margin=90.0, margin_level=1100.0)
    fake.history_deals_get = lambda a, b: [NS(profit=5.0, commission=-0.4, swap=-0.1)]
    fake.positions_get = lambda: [NS(ticket=7, symbol="EURUSD", type=1, volume=0.02,
                                     price_open=1.1, sl=1.12, tp=0.0, swap=-0.3, profit=-4.0,
                                     magic=42, time=1_700_000_000)]
    fake.last_error = lambda: (1, "ok")
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    spec = importlib.util.spec_from_file_location("publish_account_state",
                                                  ROOT / "ops" / "publish_account_state.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "attach_or_initialize", lambda m, timeout: True)
    monkeypatch.setattr(mod, "OUT", tmp_path / "account_state.json")
    monkeypatch.setattr(mod, "POSITIONS", tmp_path / "account_positions.json")
    return mod


def test_the_snapshot_carries_every_field_the_account_ledger_drill_grades(monkeypatch, tmp_path):
    mod = _load(monkeypatch, tmp_path)
    assert mod.main() == 0
    rec = json.loads((tmp_path / "account_state.json").read_text("utf-8"))
    rd = importlib.util.spec_from_file_location(
        "_rd", ROOT / "desks" / "mt5" / "research" / "recovery_drills.py")
    assert rd and rd.loader
    drills = importlib.util.module_from_spec(rd)
    rd.loader.exec_module(drills)
    ACCOUNT_FIELDS = drills.ACCOUNT_FIELDS
    assert [f for f in ACCOUNT_FIELDS if f not in rec] == []
    assert rec["margin"] == 90.0 and rec["swap"] == -0.3 and rec["today_swap"] == -0.1
    assert "login" not in rec, "the live login is never written to a tracked file"
    book = json.loads((tmp_path / "account_positions.json").read_text("utf-8"))
    pos = book["positions"][0]
    assert pos["side"] == "sell" and pos["sl"] == 1.12 and pos["tp"] is None
    assert book["open_positions"] == rec["open_positions"] == 1


def test_no_position_detail_reaches_the_tracked_snapshot(monkeypatch, tmp_path):
    """The repository is public: tickets, sizes and stops stay in the untracked book."""
    mod = _load(monkeypatch, tmp_path)
    assert mod.main() == 0
    text = (tmp_path / "account_state.json").read_text("utf-8")
    rec = json.loads(text)
    assert "positions" not in rec
    for leak in ('"ticket"', '"sl"', '"tp"', '"price_open"', '"volume"', '"magic"'):
        assert leak not in text, leak


def test_the_position_book_is_untracked_and_ignored():
    import subprocess
    rel = "desks/mt5/data/account_positions.json"
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=ROOT,
                             capture_output=True).returncode == 0
    assert not tracked, f"{rel} is tracked in a public repository"
    ignored = subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT).returncode == 0
    assert ignored, f"{rel} is not gitignored: a box commit could publish the open book"
    shipped = [p for p in (ROOT / "desks" / "mt5" / "scripts").glob("*.ps1")
               if "account_positions" in p.read_text("utf-8", errors="replace")]
    assert shipped == [], f"a box script names the private book: {shipped}"
    # the snapshot that IS tracked (when present) carries no per-position detail
    snap = ROOT / "desks" / "mt5" / "data" / "account_state.json"
    if snap.exists():
        assert '"ticket"' not in snap.read_text("utf-8", errors="replace")
