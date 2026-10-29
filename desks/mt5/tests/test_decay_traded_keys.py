"""A key that TRADES outside the LIVE roster is judged on its own live record (zuck 2026-10-29).

Every live order since 2026-09-16 has gone out through a BOOK key whose roster row is STANDBY or
RETIRED, so the LIVE-only verdict loop judged nothing and the promoter never re-judges a RETIRED
row: usdnok_carry closed 23 live trades in October for -9.36R and kept sending. What is pinned:

  * the bars are the PROMOTER'S retirement bars, mirrored and pinned equal -- no new threshold;
  * a losing traded key lands in DECAY_ZERO.json, a healthy one does not, a LIVE row is left to
    the LIVE loop, and a key with no trade in the window re-arms;
  * `decision_core.decay_zero` names it by name, unversioned book name or 27-char ledger stem,
    and an absent or torn file names nothing;
  * every sizing door the gateway uses for a book key sends nothing for a zeroed key, with its
    own reason (never a "principal" one), and the gateway bills it on its own rail.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research.regime_coverage as rc  # noqa: E402
from mt5desk import decision_core as dc  # noqa: E402
from research import decay_monitor as D  # noqa: E402

NOW = datetime.now(tz=UTC).replace(microsecond=0)
LOSER = "usdnok_carry_asia_p_ff35bb7c8427d66"        # longer than the 27-char ledger stem


@pytest.fixture
def desk(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "SLEEVES_FILE", tmp_path / "sleeves.json")
    monkeypatch.setattr(D, "OUT", tmp_path / "decay_live.json")
    monkeypatch.setattr(D, "ACTIONS", tmp_path / "decay_actions.jsonl")
    monkeypatch.setattr(D, "LEDGER", tmp_path / "live_ledger.jsonl")
    monkeypatch.setattr(D, "DECAY_ZERO", tmp_path / "DECAY_ZERO.json")
    monkeypatch.setattr(D, "SHADOW_LEDGER_DIRS", (tmp_path / "shadow",))
    monkeypatch.setattr(rc, "QUEUE", tmp_path / "queue.json")
    monkeypatch.setattr(dc, "DECAY_ZERO_FILE", tmp_path / "DECAY_ZERO.json")
    return tmp_path


def _trades(name: str, rs: list[float], days_ago: float = 1.0) -> list[dict]:
    return [{"sleeve": name, "r_multiple": r, "risk_quote": 10.0,
             "time": (NOW - timedelta(days=days_ago, minutes=len(rs) - i)).isoformat()}
            for i, r in enumerate(rs)]


def _write(desk: Path, roster: list[dict], trades: list[dict]) -> None:
    (desk / "sleeves.json").write_text(json.dumps({"sleeves": roster}), "utf-8")
    (desk / "live_ledger.jsonl").write_text("\n".join(json.dumps(t) for t in trades), "utf-8")


def test_the_bars_are_the_promoters_own() -> None:
    src = (_DESK / "research" / "promoter.py").read_text(encoding="utf-8")
    for name, mine in (("RETIRE_MIN_N", D.BOOK_RETIRE_MIN_N), ("RETIRE_MAX_DD", D.BOOK_RETIRE_MAX_DD),
                       ("RETIRE_MIN_EXP", D.BOOK_RETIRE_MIN_EXP)):
        m = re.search(rf"^{name} = (-?[0-9.]+)$", src, re.MULTILINE)
        assert m and float(m.group(1)) == mine, name
    assert 'fs["roll20_exp"] <= 0.0' in src and D.BOOK_RETIRE_ROLL == 20


def test_book_key_verdict_reads_the_three_doors() -> None:
    assert D.book_key_verdict([-0.4] * 10)[0] == "ZERO"
    assert D.book_key_verdict([-0.4] * 9)[0] == "HEALTHY"          # below n=10, no roll door
    assert D.book_key_verdict([-1.0] * 9 + [-17.0])[0] == "ZERO"    # -26R drawdown at any n
    assert D.book_key_verdict([0.04] * 50)[0] == "ZERO"             # n=50, exp < 0.05R
    assert D.book_key_verdict([0.5, -0.3] * 10)[0] == "HEALTHY"


def test_a_losing_retired_key_that_trades_is_zeroed_and_a_healthy_one_is_not(desk) -> None:
    roster = [{"name": LOSER, "status": "RETIRED"}, {"name": "gold_asia", "status": "STANDBY"},
              {"name": "eurusd_live_one", "status": "LIVE"}]
    trades = (_trades(LOSER[:27], [-0.4] * 23) + _trades("gold_asia", [0.6, -0.3] * 6)
              + _trades("eurusd_live_one", [-0.4] * 12))
    _write(desk, roster, trades)
    assert D.main(write_queue=False) == 0
    doc = json.loads((desk / "DECAY_ZERO.json").read_text("utf-8"))
    assert set(doc["zeros"]) == {LOSER[:27]}
    assert "gold_asia" in doc["judged"] and "eurusd_live_one" not in doc["judged"]
    acts = [json.loads(x) for x in (desk / "decay_actions.jsonl").read_text("utf-8").splitlines()]
    assert {(a["sleeve"], a["action"]) for a in acts if a["action"].startswith("BOOK")} \
        == {(LOSER[:27], "BOOK_ZERO")}
    live = json.loads((desk / "decay_live.json").read_text("utf-8"))
    assert live["book_keys"]["zeroed"] == [LOSER[:27]]
    # the zero's `since` survives the next pass, and no second BOOK_ZERO action is written
    since = doc["zeros"][LOSER[:27]]["since"]
    D.main(write_queue=False)
    doc2 = json.loads((desk / "DECAY_ZERO.json").read_text("utf-8"))
    assert doc2["zeros"][LOSER[:27]]["since"] == since
    acts2 = (desk / "decay_actions.jsonl").read_text("utf-8").count("BOOK_ZERO")
    assert acts2 == 1


def test_a_key_whose_losses_left_the_window_re_arms(desk) -> None:
    _write(desk, [{"name": LOSER, "status": "RETIRED"}], _trades(LOSER[:27], [-0.4] * 23))
    D.main(write_queue=False)
    assert LOSER[:27] in json.loads((desk / "DECAY_ZERO.json").read_text("utf-8"))["zeros"]
    _write(desk, [{"name": LOSER, "status": "RETIRED"}],
           _trades(LOSER[:27], [-0.4] * 23, days_ago=D.TRAIL_DAYS + 2))
    D.main(write_queue=False)
    assert json.loads((desk / "DECAY_ZERO.json").read_text("utf-8"))["zeros"] == {}
    assert "BOOK_UNZERO" in (desk / "decay_actions.jsonl").read_text("utf-8")


def test_decay_zero_matches_name_book_name_and_ledger_stem(desk) -> None:
    (desk / "DECAY_ZERO.json").write_text(json.dumps(
        {"zeros": {LOSER[:27]: {"why": "roll20 exp -0.400R <= 0 over n=23"},
                   "gold_london_am": {"why": "w"}}}), "utf-8")
    assert dc.decay_zero(LOSER) == "roll20 exp -0.400R <= 0 over n=23"
    assert dc.decay_zero("gold_london_am_v3") == "w"
    assert dc.decay_zero("gold_asia") is None and dc.decay_zero(None) is None
    (desk / "DECAY_ZERO.json").write_text("{torn", "utf-8")
    assert dc.decay_zero(LOSER) is None
    (desk / "DECAY_ZERO.json").unlink()
    assert dc.decay_zero(LOSER) is None


def test_every_book_door_sends_nothing_for_a_zeroed_key_with_its_own_reason(desk) -> None:
    (desk / "DECAY_ZERO.json").write_text(json.dumps(
        {"zeros": {"gold_asia": {"why": "roll20 exp -0.2R <= 0 over n=12"}}}), "utf-8")
    assert dc.cert_zero_row({"name": "gold_asia"}) is True
    assert dc.cert_zero_row({"name": "xau_row", "book_key": "gold_asia"}) is True
    lot, basis = dc.gold_book_lot(10000.0, 5.0, None, 0.01, name="gold_asia")
    assert lot == 0.0 and basis.startswith("decay zero") and "principal" not in basis
    gw = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    i = gw.index('_dz_fn = globals().get("decay_zero")')
    block = gw[i:gw.index('_rails.line_once("principal_zero_pin"', i)]
    assert '_rails.line_once("decay_zero"' in block and "missed_growth_risk_frac" in block
    assert "elif cert_zero_row(_s):" in block


# ------------------------------------------- allocator liveness: unjudged trading keys go RED

def _liveness_sandbox(tmp_path: Path, monkeypatch) -> tuple[object, Path]:
    from research import allocator_liveness as AL
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(AL, "DATA", data)
    return AL, data


def _close(name: str, hours_ago: float) -> str:
    return json.dumps({"sleeve": name, "r_multiple": -0.4,
                       "time": (NOW - timedelta(hours=hours_ago)).isoformat()})


def test_a_trading_key_the_decay_monitor_never_judged_is_a_liveness_breach(tmp_path,
                                                                          monkeypatch) -> None:
    AL, data = _liveness_sandbox(tmp_path, monkeypatch)
    (data / "live_ledger.jsonl").write_text(_close(LOSER[:27], 5), "utf-8")
    # the Oct 21 shape: the monitor ran after the close and judged nothing
    (data / "decay_live.json").write_text(json.dumps(
        {"checked_at": NOW.isoformat(), "verdicts": {}}), "utf-8")
    j = AL._judge_coverage(NOW.timestamp())
    assert j["status"] == "GAP" and j["unjudged"] == [LOSER[:27]]
    # judged after the close, as a book key: OK
    (data / "DECAY_ZERO.json").write_text(json.dumps({"judged": {LOSER[:27]: {}}}), "utf-8")
    assert AL._judge_coverage(NOW.timestamp())["status"] == "OK"
    # judged, but by a pass that ran BEFORE the close: still a gap
    (data / "decay_live.json").write_text(json.dumps(
        {"checked_at": (NOW - timedelta(hours=6)).isoformat(), "verdicts": {}}), "utf-8")
    assert AL._judge_coverage(NOW.timestamp())["status"] == "GAP"


def test_a_close_inside_the_grace_or_outside_the_window_is_not_yet_a_gap(tmp_path,
                                                                        monkeypatch) -> None:
    AL, data = _liveness_sandbox(tmp_path, monkeypatch)
    (data / "live_ledger.jsonl").write_text(
        "\n".join([_close("a_key", 0.5), _close("b_key", 30)]), "utf-8")
    assert AL._judge_coverage(NOW.timestamp())["status"] == "OK"
    (data / "live_ledger.jsonl").unlink()
    assert AL._judge_coverage(NOW.timestamp())["status"] == "UNMEASURED"
