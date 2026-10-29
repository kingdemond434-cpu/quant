"""A key that TRADES outside the LIVE roster is judged on its own live record (zuck 2026-10-29).

Every live order since 2026-09-16 has gone out through a BOOK key whose roster row is STANDBY or
RETIRED, so the LIVE-only verdict loop judged nothing and the promoter never re-judges a RETIRED
row: usdnok_carry closed 23 live trades in October for -9.36R and kept sending. What is pinned:

  * the guard and the bars are the PROMOTER'S (degenerate_evidence, then its three doors),
    mirrored and pinned equal -- no new threshold;
  * zuck's rules (2026-10-29 15:21Z and 15:55Z): every tripped key is ZEROED, pinned books
    included, except gold_asia, which is FLAGGED while no promoted replacement exists on its
    symbol; a zero is ONE-WAY and lifts only on a new certificate; demo rows and unmeasurable
    series move nothing;
  * `decision_core.decay_zero` names a zero by name, book name or 27-char stem, names nothing
    from an absent or torn file or while the kill switch exists, and every sizing door sends
    nothing for a named key with a decay reason, billed on its own registered rail;
  * allocator liveness goes RED on a traded key no pass judged after its close, and on zeros
    no pass has rewritten.
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
LOSER = "usdnok_carry_asia_p_ff35bb7c8427d66"        # on the principal's min-lot book
FREE = "eurgbp_formula_asia_p_1234567890abcdef"      # not pinned; longer than the 27-char stem
LOSSES = [-0.4, -0.55, 0.2, -0.7, -0.35, -0.6, 0.1, -0.45, -0.5, -0.65, -0.3, -0.4]


@pytest.fixture
def desk(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "SLEEVES_FILE", tmp_path / "sleeves.json")
    monkeypatch.setattr(D, "OUT", tmp_path / "decay_live.json")
    monkeypatch.setattr(D, "ACTIONS", tmp_path / "decay_actions.jsonl")
    monkeypatch.setattr(D, "LEDGER", tmp_path / "live_ledger.jsonl")
    monkeypatch.setattr(D, "SHADOW_LEDGER_DIRS", (tmp_path / "shadow",))
    monkeypatch.setattr(rc, "QUEUE", tmp_path / "queue.json")
    monkeypatch.setattr(dc, "DECAY_ZERO_FILE", tmp_path / "DECAY_ZERO.json")
    monkeypatch.setattr(dc, "DECAY_ZERO_DISABLED", tmp_path / "DECAY_ZERO_DISABLED")
    return tmp_path


def _trades(name: str, rs: list[float], days_ago: float = 1.0, **extra) -> list[dict]:
    return [{"sleeve": name, "r_multiple": r, "risk_quote": 10.0, "symbol": "EURGBP",
             "time": (NOW - timedelta(days=days_ago, minutes=len(rs) - i)).isoformat(), **extra}
            for i, r in enumerate(rs)]


def _write(desk: Path, roster: list[dict], trades: list[dict]) -> None:
    (desk / "sleeves.json").write_text(json.dumps({"sleeves": roster}), "utf-8")
    (desk / "live_ledger.jsonl").write_text("\n".join(json.dumps(t) for t in trades), "utf-8")


def _zero(desk: Path) -> dict:
    return json.loads((desk / "DECAY_ZERO.json").read_text("utf-8"))


def test_the_guard_and_bars_are_the_promoters_own() -> None:
    src = (_DESK / "research" / "promoter.py").read_text(encoding="utf-8")
    for name, mine in (("RETIRE_MIN_N", D.BOOK_RETIRE_MIN_N),
                       ("RETIRE_MAX_DD", D.BOOK_RETIRE_MAX_DD),
                       ("RETIRE_MIN_EXP", D.BOOK_RETIRE_MIN_EXP)):
        m = re.search(rf"^{name} = (-?[0-9.]+)$", src, re.MULTILINE)
        assert m and float(m.group(1)) == mine, name
    assert 'fs["roll20_exp"] <= 0.0' in src and D.BOOK_RETIRE_ROLL == 20
    try:
        from research import promoter
    except Exception:                                  # the promoter needs the terminal stubs
        pytest.skip("promoter not importable on this host")
    for rs in ([-1.0] * 12, [0.0] * 9 + [-0.01], [-1.0] * 10 + [0.3, -0.2], LOSSES, [0.0, 0.0]):
        ledger = [{"sleeve": "k", "r_multiple": r} for r in rs]
        assert bool(D.degenerate(rs)) == bool(promoter.degenerate_evidence(ledger, "k")), rs


def test_book_key_verdict_refuses_degenerate_series_then_reads_the_three_doors() -> None:
    assert D.book_key_verdict([-1.0] * 12)[0] == "UNMEASURED"           # constant: a defect
    assert D.book_key_verdict([0.0] * 9 + [-0.01])[0] == "UNMEASURED"   # near-constant
    assert D.book_key_verdict([])[0] == "UNMEASURED"
    assert D.book_key_verdict(LOSSES)[0] == "ZERO"
    assert D.book_key_verdict(LOSSES[:9])[0] == "HEALTHY"               # below n=10
    deep = [-4.1, -3.9, -4.3, -3.7, -4.0, -4.2, -3.8, -4.05]           # -28R past the first
    assert D.book_key_verdict(deep)[0] == "ZERO"
    assert D.book_key_verdict([0.04, 0.03, 0.06, 0.05, 0.045] * 10)[0] == "ZERO"
    assert D.book_key_verdict([0.5, -0.3, 0.6, -0.2] * 5)[0] == "HEALTHY"
    # the drawdown is measured as the promoter measures it: the peak starts at the first trade
    assert D._promoter_dd([-1.0, -2.0]) == -2.0 and D._promoter_dd([1.0, -3.0]) == -3.0


def test_every_tripped_key_is_zeroed_pinned_book_or_not(desk) -> None:
    roster = [{"name": FREE, "status": "RETIRED", "symbol": "EURGBP", "certificate": "c1"},
              {"name": "eurgbp_other_cert", "status": "STANDBY", "symbol": "EURGBP"},
              {"name": LOSER, "status": "RETIRED", "symbol": "USDNOK"},
              {"name": "gold_asia", "status": "STANDBY", "symbol": "XAUUSD"},
              {"name": "eurusd_live_one", "status": "LIVE", "symbol": "EURUSD"}]
    trades = (_trades(FREE[:27], LOSSES) + _trades(LOSER[:27], LOSSES, symbol="USDNOK")
              + _trades("gold_asia", [0.6, -0.3] * 6, symbol="XAUUSD")
              + _trades("eurusd_live_one", LOSSES))
    _write(desk, roster, trades)
    assert D.main(write_queue=False) == 0
    doc = _zero(desk)
    # zuck 15:55Z, "zeroing is allowed": USDNOK carry is zeroed though it is on the principal's
    # min-lot book and has no replacement on its symbol (recorded as None)
    assert set(doc["zeros"]) == {FREE[:27], LOSER[:27]} and doc["flags"] == {}
    assert doc["zeros"][FREE[:27]]["replacement"]
    assert doc["zeros"][LOSER[:27]]["replacement"] is None
    assert "gold_asia" in doc["judged"] and "eurusd_live_one" not in doc["judged"]
    acts = [json.loads(x) for x in (desk / "decay_actions.jsonl").read_text("utf-8").splitlines()]
    assert {(a["sleeve"], a["action"]) for a in acts if a["action"].startswith("BOOK")} \
        == {(FREE[:27], "BOOK_ZERO"), (LOSER[:27], "BOOK_ZERO")}
    live = json.loads((desk / "decay_live.json").read_text("utf-8"))
    assert live["book_keys"]["zeroed"] == sorted([FREE[:27], LOSER[:27]])


def test_gold_asia_alone_is_flagged_until_a_promoted_replacement_exists(desk) -> None:
    roster = [{"name": "gold_asia", "status": "STANDBY", "symbol": "XAUUSD"},
              {"name": "xauusd_range_reversion_p_1", "status": "STANDBY", "symbol": "XAUUSD"}]
    _write(desk, roster, _trades("gold_asia", LOSSES, symbol="XAUUSD"))
    D.main(write_queue=False)
    doc = _zero(desk)
    assert doc["zeros"] == {} and "temporary exemption" in doc["flags"]["gold_asia"]["flag"]
    # a STANDBY row is not a replacement; a promoted (LIVE) one ends the exemption
    roster[1]["status"] = "LIVE"
    _write(desk, roster, _trades("gold_asia", LOSSES, symbol="XAUUSD"))
    D.main(write_queue=False)
    doc = _zero(desk)
    assert "gold_asia" in doc["zeros"] and doc["flags"] == {}
    assert frozenset({"gold_asia"}) == D.TEMPORARY_EXEMPT


def test_a_zero_is_one_way_and_lifts_only_on_a_new_certificate(desk) -> None:
    roster = [{"name": FREE, "status": "RETIRED", "symbol": "EURGBP", "certificate": "c1"},
              {"name": "eurgbp_other_cert", "status": "STANDBY", "symbol": "EURGBP"}]
    _write(desk, roster, _trades(FREE[:27], LOSSES))
    D.main(write_queue=False)
    since = _zero(desk)["zeros"][FREE[:27]]["since"]
    # the losses age out of the window: the zero STANDS (zuck: no re-arm on silence)
    _write(desk, roster, _trades(FREE[:27], LOSSES, days_ago=D.TRAIL_DAYS + 2))
    D.main(write_queue=False)
    assert _zero(desk)["zeros"][FREE[:27]]["since"] == since
    # a fresh certificate on the row is the only way back
    roster[0]["certificate"] = "c2"
    _write(desk, roster, [])
    D.main(write_queue=False)
    doc = _zero(desk)
    assert doc["zeros"] == {} and FREE[:27] in doc["lifted"]
    assert "BOOK_LIFT" in (desk / "decay_actions.jsonl").read_text("utf-8")


def test_demo_rows_and_unmeasurable_keys_move_nothing(desk) -> None:
    roster = [{"name": FREE, "status": "RETIRED", "symbol": "EURGBP"},
              {"name": "eurgbp_other_cert", "status": "STANDBY", "symbol": "EURGBP"}]
    _write(desk, roster, _trades(FREE[:27], LOSSES, account_kind="demo")
           + _trades("gbpusd_constant", [-1.0] * 12))
    D.main(write_queue=False)
    doc = _zero(desk)
    assert doc["zeros"] == {} and doc["flags"] == {}
    assert "gbpusd_constant" in doc["unmeasured"] and FREE[:27] in doc["unmeasured"]


def test_decay_zero_matches_name_book_name_and_stem_and_honours_the_kill_switch(desk) -> None:
    (desk / "DECAY_ZERO.json").write_text(json.dumps(
        {"zeros": {FREE[:27]: {"why": "roll20 exp -0.400R <= 0 over n=12"},
                   "gold_london_am": {"why": "w"}}}), "utf-8")
    assert dc.decay_zero(FREE) == "roll20 exp -0.400R <= 0 over n=12"
    assert dc.decay_zero("gold_london_am_v3") == "w"
    assert dc.decay_zero("gold_asia") is None and dc.decay_zero(None) is None
    (desk / "DECAY_ZERO_DISABLED").write_text("", "utf-8")
    assert dc.decay_zero(FREE) is None
    (desk / "DECAY_ZERO_DISABLED").unlink()
    (desk / "DECAY_ZERO.json").write_text("{torn", "utf-8")
    assert dc.decay_zero(FREE) is None
    (desk / "DECAY_ZERO.json").unlink()
    assert dc.decay_zero(FREE) is None


def test_every_book_door_sends_nothing_for_a_zeroed_key_on_a_registered_rail(desk) -> None:
    (desk / "DECAY_ZERO.json").write_text(json.dumps(
        {"zeros": {"xau_book_key": {"why": "roll20 exp -0.2R <= 0 over n=12"}}}), "utf-8")
    assert dc.cert_zero_row({"name": "xau_book_key"}) is True
    assert dc.cert_zero_row({"name": "xau_row", "book_key": "xau_book_key"}) is True
    lot, basis = dc.gold_book_lot(10000.0, 5.0, None, 0.01, name="xau_book_key")
    assert lot == 0.0 and basis.startswith("decay zero") and "principal" not in basis
    gw = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    i = gw.index('_dz_fn = globals().get("decay_zero")')
    block = gw[i:gw.index('_rails.line_once("principal_zero_pin"', i)]
    assert '_rails.line_once("decay_zero"' in block and "missed_growth_risk_frac" in block
    from mt5desk import fusion_rails
    from research import missed_growth
    assert "decay_zero" in fusion_rails.RAILS and "decay_zero" in missed_growth.FUSION_RAIL_NAMES


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
    # judged after the close, as a book key, by DECAY_ZERO's own clock: OK
    (data / "DECAY_ZERO.json").write_text(json.dumps(
        {"checked_at": NOW.isoformat(), "flags": {LOSER[:27]: {}}}), "utf-8")
    assert AL._judge_coverage(NOW.timestamp())["status"] == "OK"
    # a DECAY_ZERO pass that ran BEFORE the close does not judge it (audit MF4b)
    (data / "DECAY_ZERO.json").write_text(json.dumps(
        {"checked_at": (NOW - timedelta(hours=6)).isoformat(), "judged": {LOSER[:27]: {}}}),
        "utf-8")
    assert AL._judge_coverage(NOW.timestamp())["status"] == "GAP"


def test_zeros_no_pass_rewrote_are_a_breach_even_with_nothing_trading(tmp_path,
                                                                     monkeypatch) -> None:
    AL, data = _liveness_sandbox(tmp_path, monkeypatch)
    (data / "live_ledger.jsonl").write_text("", "utf-8")
    (data / "DECAY_ZERO.json").write_text(json.dumps(
        {"checked_at": (NOW - timedelta(hours=5)).isoformat(), "zeros": {"k": {}}}), "utf-8")
    j = AL._judge_coverage(NOW.timestamp())
    assert j["status"] == "GAP" and "last rewritten" in j["stale"]


def test_a_close_inside_the_grace_or_outside_the_window_is_not_yet_a_gap(tmp_path,
                                                                        monkeypatch) -> None:
    AL, data = _liveness_sandbox(tmp_path, monkeypatch)
    (data / "live_ledger.jsonl").write_text(
        "\n".join([_close("a_key", 0.5), _close("b_key", 30)]), "utf-8")
    assert AL._judge_coverage(NOW.timestamp())["status"] == "OK"
    (data / "live_ledger.jsonl").unlink()
    assert AL._judge_coverage(NOW.timestamp())["status"] == "UNMEASURED"


def test_the_decay_monitor_is_never_rotated_out_of_the_hourly_pass() -> None:
    """It writes DECAY_ZERO, which the gateway reads: the core rotation listed it NEVER RUN from
    2026-10-21 while keys kept closing live trades (hourly pass 22)."""
    from libs.ops import leg_rotation as LR
    assert "decay_monitor" in LR.ALWAYS_RUN
