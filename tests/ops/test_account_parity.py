"""ACCOUNT PARITY: every live account runs the same mechanisms, and the report says so honestly.

The grid is judged against the REAL lane sources (copied into a fake root, so every wiring regex
is proved against the code it claims to read) and fabricated log tails, journals and reports.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desks" / "mt5" / "scripts"))
import account_parity as ap  # noqa: E402

NOW = datetime(2026, 11, 3, 18, 0, tzinfo=UTC)
T = (NOW - timedelta(hours=3)).isoformat(timespec="seconds")
CODE = (ap.E8_GOLD, ap.E8_GUARD, ap.FTMO, ap.GATEWAY, ap.PM, ap.DCORE, ap.DEADMAN, ap.LEARNER,
        ap.HOURLY, ap.CERT_BOOK, ap.MINLOT)
COMBINER_LINE = "\n# weak_signal_book: test fixture's combiner hook\n"


def _w(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, "utf-8")


def _edit(root: Path, rel: str, old: str, new: str) -> None:
    p = root / rel
    src = p.read_text("utf-8")
    assert old in src, f"{old!r} not in {rel}: the fixture no longer matches the code"
    p.write_text(src.replace(old, new), "utf-8")


def _jsonl(rows: list[dict]) -> str:
    return "".join(json.dumps(r) + "\n" for r in rows)


@pytest.fixture
def box(tmp_path: Path) -> Path:
    """A box where every mechanism is wired and fired on all three accounts."""
    for rel in CODE:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dst)
    for rel in (ap.E8_GOLD, ap.FTMO, ap.GATEWAY):     # LIVE wires no combiner; the fixture does
        (tmp_path / rel).write_text((tmp_path / rel).read_text("utf-8") + COMBINER_LINE, "utf-8")
    _w(tmp_path, ap.E8_LOG, "\n".join([
        f"{T} [asia] SHADOW would place buy 0.5 XAUUSD @ 4000.00",
        f"{T} [asia] PLACED buy 0.5 XAUUSD @ 4000.00 sl 3990.00 tp 4030.00",
        f"{T} [asia] RATCHET position 7 stop 3990.00 -> 4001.00; break-even floor: net open "
        "profit passed 0.85R",
        f"{T} [asia] RATCHET position 7 stop 4001.00 -> 4010.00; trending: chandelier k=4 x ATR "
        "5.00000 off extreme 4030.00000 -> stop 4010.00000",
        f"{T} [asia] RATCHET position 7 stop 4010.00 -> 4025.00; stalled: chandelier k=1 x ATR "
        "5.00000 off extreme 4030.00000 -> stop 4025.00000"]) + "\n")
    _w(tmp_path, ap.E8_INTENTS, _jsonl([{"at": T, "status": "SENT", "window": "asia"}]))
    _w(tmp_path, ap.FTMO_LOG, f"{T} [asia] SENT buy_stop 0.3 XAUUSD @ 4000.00 -> 10009\n")
    _w(tmp_path, ap.FTMO_INTENTS, _jsonl([{"at": T, "status": "SENT", "lane": "ftmo"}]))
    _w(tmp_path, ap.FTMO_REPORT, json.dumps({"at": T, "actions": [
        {"act": "ratchet_stop", "position": 1, "before": 3990.0, "after": 4025.0, "ok": True}]}))
    _w(tmp_path, ap.GW_LOG, "\n".join([
        f"{T} ORDER [gold_asia] buy -> retcode=10009 Request executed",
        f"{T} MANAGE ticket 5 (XAUUSD): MODIFY [BREAK-EVEN FLOOR] sl 3990.00000 -> 4001.00000 "
        "(protected -1.000R -> +0.050R) retcode=10009 done | break-even floor: net open profit "
        "passed 0.85R; the k=4 trail at 3985.00000 protects less",
        f"{T} MANAGE ticket 5 (XAUUSD): MODIFY sl 4001.00000 -> 4010.00000 (protected +0.050R -> "
        "+0.500R) retcode=10009 done | trending: chandelier k=4 x ATR 5.00000 off extreme",
        f"{T} MANAGE ticket 5 (XAUUSD): MODIFY sl 4010.00000 -> 4025.00000 (protected +0.500R -> "
        "+1.250R) retcode=10009 done | stalled: chandelier k=1 x ATR 5.00000 off extreme"]) + "\n")
    _w(tmp_path, ap.FUSION_RAILS, _jsonl([{"at": T, "rail": "one_gold_at_risk"}]))
    _w(tmp_path, ap.DEADMAN_LOGS[0], f"{T} LIVE all rails clear\n")
    books = dict.fromkeys(("e8", "ftmo", "fusion"), "MEASURED: 3 rows in ledger")
    _w(tmp_path, ap.LEARNER_REPORT, json.dumps({"generated_at": T, "books": books}))
    return tmp_path


def _measure(root: Path, **kw) -> dict:
    return ap.measure(NOW.timestamp(), root=root, **kw)


def _cell(doc: dict, acct: str, mech: str) -> dict:
    return doc["grid"][acct][mech]


def test_every_mechanism_wired_and_fired_everywhere_is_green(box: Path) -> None:
    doc = _measure(box)
    bad = {(a, m): c.get("why") for a, row in doc["grid"].items() for m, c in row.items()
           if c["verdict"] != "GREEN"}
    assert not bad, bad
    assert doc["verdict"] == "GREEN" and doc["red"] == [] and doc["unmeasured"] == []
    assert doc["counts"]["GREEN"] == len(ap.ACCOUNTS) * len(ap.MECHANISMS)
    c = _cell(doc, "e8", "breakeven_floor")
    assert c["present"] is True and c["last_fired"] == T
    assert any(e.startswith(f"{ap.E8_GOLD}:") for e in c["evidence"]["code"])
    assert c["evidence"]["fired_from"] == ap.E8_LOG


def test_firm_caps_differ_and_the_grid_stays_green(box: Path) -> None:
    doc = _measure(box)
    caps = {a: {r["cap"]: r["value"] for r in rows}
            for a, rows in doc["allowed_differences"].items()}
    assert caps["e8"]["DAILY_DRAWDOWN"] == "0.025"
    assert "0.05" in caps["ftmo"]["ACCOUNT_TYPES"]
    assert caps["fusion"]["FUSION_DAILY_LOSS_FRAC"] not in (None, caps["e8"]["DAILY_DRAWDOWN"])
    assert doc["verdict"] == "GREEN"
    assert doc["shared_position_manager"]["BREAKEVEN_TRIGGER_R"] == "0.85"


def test_a_mechanism_absent_on_one_account_is_red(box: Path) -> None:
    _edit(box, ap.GATEWAY, "_xa.opposite_block(", "_xa.not_the_fence(")
    doc = _measure(box)
    assert _cell(doc, "fusion", "opposite_side_fence")["verdict"] == "RED"
    assert _cell(doc, "fusion", "opposite_side_fence")["present"] is False
    assert _cell(doc, "e8", "opposite_side_fence")["verdict"] == "GREEN"
    assert doc["verdict"] == "RED"
    assert (doc["red"][0]["account"], doc["red"][0]["mechanism"]) == (
        "fusion", "opposite_side_fence")


def test_live_has_no_combiner_so_the_column_is_red() -> None:
    """The real tree today: no account's money path references a combiner."""
    for rel in (ap.E8_GOLD, ap.FTMO, ap.GATEWAY):
        ctx = ap.Ctx(ROOT, time.monotonic() + 30)
        present, why = ap.wired(ctx, (rel, ap.COMBINER_RX))
        assert present is False, why


def test_never_fired_while_the_others_fired_is_red(box: Path) -> None:
    log = box / ap.E8_LOG
    log.write_text("".join(ln + "\n" for ln in log.read_text("utf-8").splitlines()
                           if "break-even floor" not in ln), "utf-8")
    doc = _measure(box)
    c = _cell(doc, "e8", "breakeven_floor")
    assert c["verdict"] == "RED" and c["last_fired"] is None
    assert "ftmo" in c["why"] and "fusion" in c["why"]
    assert _cell(doc, "fusion", "breakeven_floor")["verdict"] == "GREEN"


def test_a_failed_modify_is_not_a_fire(box: Path) -> None:
    """FTMO's 10025 (no changes) is ok=False in its report: no fire, so RED against E8/Fusion."""
    _w(box, ap.FTMO_REPORT, json.dumps({"at": T, "actions": [
        {"act": "ratchet_stop", "position": 1, "after": 4025.0, "ok": False}]}))
    doc = _measure(box)
    assert _cell(doc, "ftmo", "atr_trail")["verdict"] == "RED"


def test_conditional_rails_are_not_fire_compared(box: Path) -> None:
    _w(box, ap.FUSION_RAILS, _jsonl([{"at": T, "rail": "fusion_daily_loss"}]))
    doc = _measure(box)
    assert _cell(doc, "fusion", "daily_loss_breaker")["last_fired"] == T
    assert _cell(doc, "e8", "daily_loss_breaker")["last_fired"] is None
    assert _cell(doc, "e8", "daily_loss_breaker")["verdict"] == "GREEN"


def test_unreadable_is_unmeasured_never_green(box: Path) -> None:
    (box / ap.FTMO_REPORT).unlink()
    doc = _measure(box)
    for mech in ("breakeven_floor", "atr_trail", "stall_tighten"):
        assert _cell(doc, "ftmo", mech)["verdict"] == "UNMEASURED"
    assert doc["verdict"] == "UNMEASURED"
    assert any(u["account"] == "ftmo" for u in doc["unmeasured"])


def test_unreadable_code_is_unmeasured_not_absent(box: Path) -> None:
    (box / ap.FTMO).unlink()
    doc = _measure(box)
    c = _cell(doc, "ftmo", "entry")
    assert c["present"] is None and c["verdict"] == "UNMEASURED"


def test_a_spent_budget_is_unmeasured(box: Path) -> None:
    doc = _measure(box, budget_s=0.0)
    assert doc["verdict"] == "UNMEASURED" and doc["budget"]["spent"] is True
    assert doc["counts"]["GREEN"] == 0


def _no_ftmo_ratchet(box: Path) -> None:
    _w(box, ap.FTMO_REPORT, json.dumps({"at": T, "actions": []}))


def test_a_manual_close_is_an_event_not_a_defect(box: Path) -> None:
    """zuck closed the FTMO trade by hand (11-03 11:10:55Z at 3910.22): the trail never got to
    act, and that must not read RED."""
    _no_ftmo_ratchet(box)
    _w(box, ap.PROP_LEDGER, _jsonl([
        {"book": "ftmo", "exit_time": "2026-11-03T11:10:55+00:00", "fill_price": 3910.22,
         "exit_reason": "manual", "closed_by": "manual", "account_key": "keyed"}]))
    doc = _measure(box)
    ex = doc["exits"]["ftmo"]
    assert ex["rows"][0] == {"at": "2026-11-03T11:10:55+00:00", "price": 3910.22,
                             "label": "manual"}
    assert ex["all_manual"] is True
    for mech in ap.EXIT_MECHANISMS:
        c = _cell(doc, "ftmo", mech)
        assert c["verdict"] == "GREEN" and c.get("manual_exit") is True, c
    assert doc["verdict"] == "GREEN"
    assert "account_key" not in json.dumps(doc["exits"])


def test_a_venue_close_still_binds_the_rule(box: Path) -> None:
    _no_ftmo_ratchet(box)
    _w(box, ap.PROP_LEDGER, _jsonl([
        {"book": "ftmo", "exit_time": "2026-11-03T11:10:55+00:00", "fill_price": 3910.22,
         "exit_reason": "manual", "closed_by": "manual"},
        {"book": "ftmo", "exit_time": "2026-11-02T03:00:00+00:00", "fill_price": 3950.0,
         "exit_reason": "stop", "closed_by": "venue"}]))
    doc = _measure(box)
    assert doc["exits"]["ftmo"]["manual"] == 1
    assert _cell(doc, "ftmo", "atr_trail")["verdict"] == "RED"


def test_last_fired_is_carried_forward(box: Path) -> None:
    first = _measure(box)
    log = box / ap.E8_LOG
    log.write_text("".join(ln + "\n" for ln in log.read_text("utf-8").splitlines()
                           if "break-even floor" not in ln), "utf-8")
    again = _measure(box, prev=first)
    c = _cell(again, "e8", "breakeven_floor")
    assert c["last_fired"] == T and c["carried"] is True and c["verdict"] == "GREEN"


def test_refresh_writes_throttles_and_never_raises(box: Path, monkeypatch) -> None:
    out = box / "desks/mt5/reports/ACCOUNT_PARITY.json"
    doc = ap.refresh(NOW.timestamp(), out=out, root=box)
    assert json.loads(out.read_text("utf-8"))["verdict"] == doc["verdict"] == "GREEN"
    monkeypatch.setattr(ap, "measure", lambda *a, **k: 1 / 0)
    assert ap.refresh(NOW.timestamp() + 60, out=out, root=box)["verdict"] == "GREEN"  # throttled
    crashed = ap.refresh(NOW.timestamp() + 3600, out=out, root=box)
    assert crashed["verdict"] == "UNMEASURED" and "ZeroDivisionError" in crashed["problems"][0]


def test_it_never_imports_a_lane_or_metatrader(box: Path) -> None:
    import ast
    tree = ast.parse((ROOT / "desks/mt5/scripts/account_parity.py").read_text("utf-8"))
    mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {str(n.module) for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert mods <= {"__future__", "contextlib", "json", "os", "re", "time", "collections.abc",
                    "datetime", "pathlib", "typing"}, mods
    before = "MetaTrader5" in sys.modules
    _measure(box)
    assert ("MetaTrader5" in sys.modules) == before


def test_the_heartbeat_refreshes_it_and_survives_a_crash(monkeypatch) -> None:
    import box_heartbeat as hb
    monkeypatch.setattr(ap, "refresh", lambda now=None: {"verdict": "RED", "red": [1, 2]})
    assert hb.account_parity_refresh()["verdict"] == "RED"
    monkeypatch.setattr(ap, "refresh", lambda now=None: 1 / 0)
    assert hb.account_parity_refresh() == {"verdict": "UNMEASURED", "error": "ZeroDivisionError"}
    assert "account_parity_refresh()" in (ROOT / "desks/mt5/scripts/box_heartbeat.py").read_text(
        "utf-8")


def test_the_report_is_published_and_not_ignored() -> None:
    from libs.ops import state_publication as sp
    rel = "desks/mt5/reports/ACCOUNT_PARITY.json"
    assert rel in sp.published_paths(ROOT)
    r = subprocess.run(["git", "check-ignore", "-q", "--", rel], cwd=ROOT, check=False)
    assert r.returncode != 0, f"{rel} is listed for publication but .gitignore excludes it"
