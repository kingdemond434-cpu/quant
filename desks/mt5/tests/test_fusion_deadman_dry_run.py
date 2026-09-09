"""The MT5 deadman runs in DRY-RUN, is unit-tested rail by rail, and is registered without `--live`.

MEASURED 2026-09-08: the only deadman on this desk (scripts/run_deadman_switch.py, Tier-3, never
touched here) polls pinned Binance testnet endpoints and protects no live MT5 risk; the drafted
MT5 rail, desks/mt5/proposals/fusion_deadman.py, had sat complete and unscheduled since
2026-08-26 -- grep for `fusion_deadman` across every .ps1/.cmd/.manifest/.py outside the file
returned zero hits.

Three properties, none of which changes a threshold in the rail:

  1. every rule is exercised over synthetic readings against a FAKE terminal: daily loss, equity
     floor (with its hysteresis), weekly loss, position count, free margin, size multiple, stale
     heartbeat, and the confirm-reads gate;
  2. a dry-run pass writes data/fusion_deadman_state.json every time and the stamp STATES what
     the pass would do -- and touches no pause file and no terminal;
  3. the scheduled registration (Install-QuantWindows.ps1 and box_tasks.manifest) carries no
     `--live`. Arming is the principal's decision and is not taken by a table row.

The module is loaded from its file: `proposals/` is not a package, and making it one is not this
test's business.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parent.parent
MODULE = BASE / "proposals" / "fusion_deadman.py"
INSTALLER = BASE / "scripts" / "Install-QuantWindows.ps1"
MANIFEST = BASE / "ops" / "box_tasks.manifest"
TASK = "MT5-FusionDeadmanDryRun"


def _load():
    spec = importlib.util.spec_from_file_location("fusion_deadman_under_test", MODULE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class _NoTerminal:
    """A terminal that refuses to be touched: any attribute access is a test failure."""

    def __getattr__(self, name):
        raise AssertionError(f"the dry-run rail touched the terminal: MetaTrader5.{name}")


@pytest.fixture
def fd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The module, with every path under tmp and the terminal stubbed to refuse."""
    mod = _load()
    data, logs = tmp_path / "data", tmp_path / "logs"
    data.mkdir()
    monkeypatch.setattr(mod, "STATE", data / "gateway_state.json")
    monkeypatch.setattr(mod, "LEDGER", data / "live_ledger.jsonl")
    monkeypatch.setattr(mod, "INTENTS", data / "order_intents.jsonl")
    monkeypatch.setattr(mod, "PAUSED", data / "GATEWAY_PAUSED")
    monkeypatch.setattr(mod, "STAMP", data / "fusion_deadman_state.json")
    monkeypatch.setattr(mod, "BREACH_LOG", logs / "fusion_deadman.log")
    monkeypatch.setitem(sys.modules, "MetaTrader5", _NoTerminal())
    return mod


def _account(equity=20_000.0, margin_free=15_000.0, last_reconcile=None):
    last = last_reconcile if last_reconcile is not None else \
        datetime.now(tz=UTC).isoformat(timespec="seconds")
    return {"equity": equity, "margin_free": margin_free, "last_reconcile": last}


def _pos(ticket: int, volume: float = 0.06, kind: int = 0) -> dict:
    return {"ticket": ticket, "type": kind, "volume": volume, "price_open": 2000.0,
            "sl": 1990.0, "tp": 2020.0, "profit": 0.0, "symbol": "XAUUSD"}


def _closed(pl: float, hours_ago: float = 0.0) -> dict:
    """A closed trade `hours_ago` ago; the default is ONE MINUTE ago, so a "today" row stays
    today whatever the wall clock reads -- an hour-old row is yesterday just after midnight."""
    at = datetime.now(tz=UTC) - (timedelta(hours=hours_ago) if hours_ago
                                 else timedelta(minutes=1))
    return {"time": at.isoformat(timespec="seconds"), "pl_quote": pl, "sleeve": "gold_asia"}


def _codes(breaches) -> list[str]:
    return sorted(c for c, _ in breaches)


# ------------------------------------------------------------------------------ each rule

def test_a_healthy_account_breaches_nothing(fd) -> None:
    assert fd.evaluate(_account(), [_pos(1)], [_closed(+50.0)], 20_000.0) == []


def test_the_daily_loss_rail_trips_past_its_share_of_the_days_reference(fd) -> None:
    peak = 20_000.0
    just_under = [_closed(-(fd.DAILY_LOSS_PCT * peak) + 1.0)]
    assert "DAILY_LOSS" not in _codes(fd.evaluate(_account(), [], just_under, peak))
    over = [_closed(-(fd.DAILY_LOSS_PCT * peak) - 1.0)]
    assert _codes(fd.evaluate(_account(), [], over, peak)) == ["DAILY_LOSS"]
    # Yesterday's loss is not today's.
    old = [_closed(-(fd.DAILY_LOSS_PCT * peak) - 1.0, hours_ago=30.0)]
    assert "DAILY_LOSS" not in _codes(fd.evaluate(_account(), [], old, peak))


def test_the_weekly_loss_rail_sums_the_trailing_week(fd) -> None:
    peak = 20_000.0
    each = -(fd.WEEKLY_LOSS_PCT * peak) / 4 - 1.0
    week = [_closed(each, hours_ago=h) for h in (30.0, 60.0, 90.0, 120.0)]
    codes = _codes(fd.evaluate(_account(), [], week, peak))
    assert "WEEKLY_LOSS" in codes and "DAILY_LOSS" not in codes
    stale = [_closed(each, hours_ago=h) for h in (200.0, 230.0, 260.0, 290.0)]
    assert "WEEKLY_LOSS" not in _codes(fd.evaluate(_account(), [], stale, peak))


def test_the_equity_floor_and_its_hysteresis(fd) -> None:
    floor = fd.EQUITY_FLOOR_EUR
    assert _codes(fd.evaluate(_account(equity=floor - 0.01), [], [], floor)) == ["EQUITY_FLOOR"]
    assert "EQUITY_FLOOR" not in _codes(fd.evaluate(_account(equity=floor + 0.01), [], [], floor))
    # Once halted on the floor the account must climb to floor x hysteresis before it clears.
    band = floor * fd.EQUITY_REARM_HYSTERESIS
    assert "EQUITY_FLOOR" in _codes(fd.evaluate(_account(equity=band - 0.01), [], [], band,
                                                halt_codes=("EQUITY_FLOOR",)))
    assert "EQUITY_FLOOR" not in _codes(fd.evaluate(_account(equity=band + 0.01), [], [], band,
                                                    halt_codes=("EQUITY_FLOOR",)))
    # A zero equity read is a broken read, not a ruin.
    assert "EQUITY_FLOOR" not in _codes(fd.evaluate(_account(equity=0.0), [], [], floor))


def test_the_position_count_is_a_loop_detector(fd) -> None:
    at_cap = [_pos(i) for i in range(1, fd.MAX_OPEN_POSITIONS + 1)]
    assert "POSITION_COUNT" not in _codes(fd.evaluate(_account(), at_cap, [], 20_000.0))
    over = [*at_cap, _pos(fd.MAX_OPEN_POSITIONS + 1)]
    assert "POSITION_COUNT" in _codes(fd.evaluate(_account(), over, [], 20_000.0))


def test_the_free_margin_rail(fd) -> None:
    eq = 20_000.0
    low = _account(equity=eq, margin_free=fd.MIN_FREE_MARGIN_FRAC * eq - 1.0)
    assert _codes(fd.evaluate(low, [], [], eq)) == ["MARGIN"]
    ok = _account(equity=eq, margin_free=fd.MIN_FREE_MARGIN_FRAC * eq + 1.0)
    assert "MARGIN" not in _codes(fd.evaluate(ok, [], [], eq))
    # An unread margin (0.0) is not a breach -- it is an absent reading.
    assert "MARGIN" not in _codes(fd.evaluate(_account(equity=eq, margin_free=0.0), [], [], eq))


def test_the_stale_heartbeat_rail_only_matters_with_positions_open(fd) -> None:
    old = (datetime.now(tz=UTC) - timedelta(minutes=fd.STALE_HEARTBEAT_MIN + 1)).isoformat()
    assert "STALE_GATEWAY" in _codes(fd.evaluate(_account(last_reconcile=old), [_pos(1)], [],
                                                 20_000.0))
    assert "STALE_GATEWAY" not in _codes(fd.evaluate(_account(last_reconcile=old), [], [],
                                                     20_000.0))
    fresh = (datetime.now(tz=UTC) - timedelta(minutes=fd.STALE_HEARTBEAT_MIN - 1)).isoformat()
    assert "STALE_GATEWAY" not in _codes(fd.evaluate(_account(last_reconcile=fresh), [_pos(1)],
                                                     [], 20_000.0))
    assert "STALE_GATEWAY" in _codes(fd.evaluate(_account(last_reconcile="not a time"),
                                                 [_pos(1)], [], 20_000.0))


def test_the_size_multiple_is_judged_against_the_intents_own_lot_and_never_assumed(fd) -> None:
    """A position over MAX_SIZE_MULTIPLE x the lot on its intent is a defect; a position with no
    intent row is UNMEASURED, counted, and not a breach."""
    expected = fd.expected_lots([{"ticket": 7, "lot": 0.02}, {"ticket": 8, "lot": 0.02},
                                 {"ticket": "bad", "lot": 0.02}, {"ticket": 9, "lot": 0}])
    assert expected == {7: 0.02, 8: 0.02}
    m = fd.MAX_SIZE_MULTIPLE
    positions = [_pos(7, volume=0.02 * m), _pos(8, volume=0.02 * m + 0.01), _pos(99, volume=9.0)]
    breaches, readings = fd.size_guard(positions, expected)
    assert [c for c, _ in breaches] == ["SIZE_GUARD"] and "position 8" in breaches[0][1]
    assert readings == {"judged": 2, "unmeasured": 1}
    assert "SIZE_GUARD" in _codes(fd.evaluate(_account(), positions, [], 20_000.0,
                                              expected=expected))
    # Without an intent ledger no position is judged on size and none is assumed right.
    assert "SIZE_GUARD" not in _codes(fd.evaluate(_account(), positions, [], 20_000.0))
    assert fd.size_guard(positions, None)[1] == {"judged": 0, "unmeasured": 3}


def test_the_thresholds_are_the_drafts(fd) -> None:
    """Pinned so this wave provably changed no number in the rail."""
    assert (fd.DAILY_LOSS_PCT, fd.EQUITY_FLOOR_EUR, fd.WEEKLY_LOSS_PCT, fd.MAX_OPEN_POSITIONS,
            fd.MIN_FREE_MARGIN_FRAC, fd.MAX_SIZE_MULTIPLE, fd.STALE_HEARTBEAT_MIN,
            fd.CONFIRM_READS) == (0.10, 300.0, 0.20, 24, 0.25, 3.0, 45, 2)
    assert fd.rails() == {"DAILY_LOSS_PCT": 0.10, "EQUITY_FLOOR_EUR": 300.0,
                          "WEEKLY_LOSS_PCT": 0.20, "MAX_OPEN_POSITIONS": 24,
                          "MIN_FREE_MARGIN_FRAC": 0.25, "MAX_SIZE_MULTIPLE": 3.0,
                          "STALE_HEARTBEAT_MIN": 45, "CONFIRM_READS": 2}


# --------------------------------------------------------------- the dry-run pass and its stamp

def _write_state(fd, equity=20_000.0, margin_free=15_000.0, positions=None, last=None) -> None:
    fd.STATE.write_text(json.dumps({
        "armed": True, "equity": equity, "margin_free": margin_free,
        "last_reconcile": last or datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "position": positions}), "utf-8")


def _stamp(fd) -> dict:
    return json.loads(fd.STAMP.read_text("utf-8"))


def test_a_dry_run_pass_writes_the_stamp_and_states_nothing_to_do(fd) -> None:
    _write_state(fd)
    assert fd.main(dry_run=True) == 0
    s = _stamp(fd)
    assert s["mode"] == "DRY-RUN" and s["breaches"] == []
    assert s["would"] == {"action": "NOTHING", "executed": False, "reasons": [],
                          "confirm": "0/2", "rearm": "no halt of ours to lift"}
    assert s["readings"]["equity"] == 20_000.0 and s["readings"]["open_positions"] == 0
    assert s["readings"]["size_guard"] == {"judged": 0, "unmeasured": 0}
    assert s["rails"] == fd.rails() and s["checked_at"]
    assert not fd.PAUSED.exists()


def test_confirm_reads_one_breach_waits_two_halt_and_dry_run_writes_no_pause_file(fd) -> None:
    """One bad read is noise; the second consecutive read of the same breach is evidence. In
    dry-run the halt is STATED on the stamp and the pause file is never written."""
    _write_state(fd, equity=fd.EQUITY_FLOOR_EUR - 1.0)
    assert fd.main(dry_run=True) == 1
    s = _stamp(fd)
    assert s["breaches"] == ["EQUITY_FLOOR"] and s["consecutive"] == 1
    assert s["would"]["action"] == "WAIT_FOR_CONFIRMATION" and s["would"]["confirm"] == "1/2"
    assert s["halt_codes"] == [] and not fd.PAUSED.exists()

    assert fd.main(dry_run=True) == 1
    s = _stamp(fd)
    assert s["consecutive"] == 2 and s["would"]["action"] == "HALT_AND_FLATTEN"
    assert s["would"]["executed"] is False and s["halt_codes"] == ["EQUITY_FLOOR"]
    assert any("EQUITY FLOOR" in r for r in s["would"]["reasons"])
    assert not fd.PAUSED.exists(), "dry-run must never write the gateway's pause file"
    assert "DRY-RUN would halt" in fd.BREACH_LOG.read_text("utf-8")


def test_the_stamp_reads_the_intent_ledger_for_the_size_guard(fd) -> None:
    fd.INTENTS.write_text(json.dumps({"ticket": 7, "lot": 0.02, "sleeve": "gold_asia"}) + "\n",
                          "utf-8")
    _write_state(fd, positions=[_pos(7, volume=0.02 * fd.MAX_SIZE_MULTIPLE + 0.01), _pos(8)])
    assert fd.main(dry_run=True) == 1
    s = _stamp(fd)
    assert s["breaches"] == ["SIZE_GUARD"]
    assert s["readings"]["size_guard"] == {"judged": 1, "unmeasured": 1}
    assert s["readings"]["open_positions"] == 2


def test_a_dry_run_re_arm_is_stated_not_done(fd, monkeypatch) -> None:
    """The halt is ours, every breach has cleared and the backoff has elapsed: live would
    re-arm; dry-run says so on the stamp and leaves the pause file exactly where it was."""
    _write_state(fd)
    fd.PAUSED.write_text("AUTO-HALTED by the Fusion ruin rail.\n", "utf-8")
    cleared = (datetime.now(tz=UTC) - timedelta(minutes=fd.REARM_COOLDOWN_MIN + 1))
    fd.STAMP.write_text(json.dumps({"peak_equity": 20_000.0, "consecutive": 0,
                                    "halt_codes": ["EQUITY_FLOOR"], "rearm_history": {},
                                    "escalated": [],
                                    "cleared_at": cleared.isoformat(timespec="seconds")}),
                        "utf-8")
    assert fd.main(dry_run=True) == 0
    s = _stamp(fd)
    assert s["would"]["action"] == "RE-ARM" and s["would"]["executed"] is False
    assert s["would"]["rearm"].startswith("WOULD RE-ARM")
    assert fd.PAUSED.exists() and s["halt_codes"] == ["EQUITY_FLOOR"]

    # A pause a HUMAN wrote is never ours to lift, in any mode.
    fd.PAUSED.write_text("Fusion switch in progress - paused by hand.\n", "utf-8")
    fd.main(dry_run=True)
    assert _stamp(fd)["would"]["rearm"] == "no halt of ours to lift"
    assert fd.PAUSED.read_text("utf-8").startswith("Fusion switch in progress")


def test_the_live_path_only_flattens_and_cancels_against_a_fake_terminal(fd, monkeypatch) -> None:
    """`--live` is the principal's switch and is NOT registered anywhere; this proves what it
    would do if thrown: write the pause file first, then close every position with the opposite
    side and cancel every pending. It can never open, resize or reverse anything."""
    calls: list = []
    pos = SimpleNamespace(ticket=7, symbol="XAUUSD", volume=0.06, type=0)
    fake = SimpleNamespace(
        TRADE_ACTION_DEAL=1, ORDER_TYPE_SELL=1, ORDER_TYPE_BUY=0, POSITION_TYPE_BUY=0,
        positions_get=lambda: [pos],
        orders_get=lambda: [SimpleNamespace(ticket=71)],
        symbol_info_tick=lambda s: SimpleNamespace(bid=2001.0, ask=2001.3),
        order_send=lambda req: (calls.append(("send", dict(req)))
                                or SimpleNamespace(retcode=10009)),
        order_delete=lambda t: calls.append(("delete", t)))
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    fd.flatten_and_halt(["EQUITY FLOOR: test"], dry_run=False)
    assert fd.PAUSED.exists() and "Fusion ruin rail" in fd.PAUSED.read_text("utf-8")
    assert fd.halted_by_us() is not None
    (send,) = [c for c in calls if c[0] == "send"]
    (delete,) = [c for c in calls if c[0] == "delete"]
    assert send[1]["type"] == fake.ORDER_TYPE_SELL and send[1]["position"] == 7
    assert send[1]["volume"] == 0.06 and send[1]["comment"] == "DEADMAN"
    assert delete[1] == 71
    # And the same call in dry-run touches nothing at all.
    fd.PAUSED.unlink()
    monkeypatch.setitem(sys.modules, "MetaTrader5", _NoTerminal())
    fd.flatten_and_halt(["EQUITY FLOOR: test"], dry_run=True)
    assert not fd.PAUSED.exists()


# ------------------------------------------------------------------ the registration is dry-run

def _installer_block() -> str:
    text = INSTALLER.read_text("utf-8")
    m = re.search(rf'@\{{\s*Name\s*=\s*"{re.escape(TASK)}"(.*?)(?=@\{{\s*Name\s*=|\n\)\n)',
                  text, re.S)
    assert m, f"{TASK} is not in the installer's $tasks table"
    return m.group(0)


def test_the_installer_registers_the_rail_every_five_minutes_without_live() -> None:
    block = _installer_block()
    assert 'Script = "proposals\\\\fusion_deadman.py"' in block
    assert "New-TimeSpan -Minutes 5" in block
    assert "--live" not in block, "the scheduled rail must be dry-run; arming is the principal's"
    assert not re.search(r"\bArgs\s*=", block), "no Args at all: the default is dry-run"
    assert 'Kind = "ps1"' not in block, "it is a Python script"
    assert (BASE / "proposals" / "fusion_deadman.py").exists()


def test_the_manifest_declares_the_rail_with_its_cadence_and_no_live() -> None:
    rows = [ln for ln in MANIFEST.read_text("utf-8").splitlines()
            if ln.startswith("TASK") and f'name="{TASK}"' in ln]
    assert len(rows) == 1, rows
    (row,) = rows
    assert 'trigger="every 5 minutes"' in row
    assert 'runs="desks/mt5/proposals/fusion_deadman.py"' in row
    assert 'installer="desks/mt5/scripts/Install-QuantWindows.ps1"' in row
    assert "--live" not in row
    # The Tier-3 rail's own row is untouched: same name, same script, still undeclared.
    crypto = [ln for ln in MANIFEST.read_text("utf-8").splitlines()
              if ln.startswith("TASK") and 'name="MT5-FusionDeadman"' in ln]
    assert len(crypto) == 1 and 'runs="scripts/run_deadman_switch.py"' in crypto[0]


def test_the_main_entry_point_defaults_to_dry_run() -> None:
    src = MODULE.read_text("utf-8")
    assert 'main(dry_run="--live" not in sys.argv)' in src
    assert "def main(dry_run: bool = True)" in src
