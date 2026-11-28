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
    fake.account_info = lambda: NS(login=1, company="Venue", server="FusionMarkets-Live",
                                   currency="EUR",
                                   balance=1000.0, equity=990.0, margin_free=900.0,
                                   margin=90.0, margin_level=1100.0)
    fake.history_deals_get = lambda a, b: [NS(profit=5.0, commission=-0.4, swap=-0.1)]
    fake.positions_get = lambda: [NS(ticket=7, symbol="EURUSD", type=1, volume=0.02,
                                     price_open=1.1, sl=1.12, tp=0.0, swap=-0.3, profit=-4.0,
                                     magic=42, time=1_700_000_000)]
    fake.last_error = lambda: (1, "ok")
    fake.terminal_info = lambda: NS(path=r"C:\Program Files\Fusion Markets MetaTrader 5")
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    spec = importlib.util.spec_from_file_location("publish_account_state",
                                                  ROOT / "ops" / "publish_account_state.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    seen: dict = {}
    monkeypatch.setattr(mod, "attach_or_initialize",
                        lambda m, **kw: seen.update(kw) or True)
    mod._attach_kwargs = seen
    term = tmp_path / "terminal_path.txt"
    term.write_text("C:/Program Files/Fusion Markets MetaTrader 5/terminal64.exe\n", "utf-8")
    monkeypatch.setattr(mod, "TERMINAL_FILE", term)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
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


def test_the_publisher_attaches_to_terminal_path_txt(monkeypatch, tmp_path):
    """No path meant 'whatever terminal the bridge sees': with Fusion AND FTMO logged in on the
    box, restart order alone decided whose balance this file published."""
    mod = _load(monkeypatch, tmp_path)
    assert mod.main() == 0
    assert mod._attach_kwargs["path"] == (
        "C:/Program Files/Fusion Markets MetaTrader 5/terminal64.exe")


def test_a_non_fusion_server_is_refused_and_paged(monkeypatch, tmp_path):
    mod = _load(monkeypatch, tmp_path)
    prior = '{"balance": 266.01}'
    (tmp_path / "account_state.json").write_text(prior, "utf-8")
    ftmo = NS(login=1, company="FTMO Global Markets Ltd", server="FTMO-Server2", currency="USD",
              balance=99666.72, equity=99666.72, margin_free=1.0, margin=0.0, margin_level=None)
    monkeypatch.setattr(sys.modules["MetaTrader5"], "account_info", lambda: ftmo)
    assert mod.main() == 1
    assert (tmp_path / "account_state.json").read_text("utf-8") == prior, "fail closed"
    assert not (tmp_path / "account_positions.json").exists()
    pagef = (tmp_path / "data" / "PRINCIPAL_ACTION.md").read_text("utf-8")
    assert pagef.startswith("ACCOUNT STATE REFUSED:") and "FTMO-Server2" in pagef
    assert "99666" not in pagef and "login" not in pagef.lower()


def test_a_different_attached_terminal_is_refused(monkeypatch, tmp_path):
    """Right broker, wrong terminal (a second Fusion install, a demo) is still not the desk's."""
    mod = _load(monkeypatch, tmp_path)
    monkeypatch.setattr(sys.modules["MetaTrader5"], "terminal_info",
                        lambda: NS(path=r"C:\Program Files\FTMO Global Markets MT5 Terminal"))
    assert mod.main() == 1
    assert not (tmp_path / "account_state.json").exists()
    assert "terminal_path.txt" in (tmp_path / "data" / "PRINCIPAL_ACTION.md").read_text("utf-8")


def test_the_terminal_match_ignores_case_slashes_and_the_exe():
    import importlib.util as u
    spec = u.spec_from_file_location("_pas", ROOT / "ops" / "publish_account_state.py")
    assert spec and spec.loader
    m = u.module_from_spec(spec)
    spec.loader.exec_module(m)
    same = m._same_terminal
    assert same("C:/Program Files/Fusion Markets MetaTrader 5/terminal64.exe",
                r"c:\program files\fusion markets metatrader 5")
    assert same("C:\\X\\", "C:\\X")
    assert not same("C:/A/terminal64.exe", r"C:\B")
    assert not same("C:/A/terminal64.exe", None)
