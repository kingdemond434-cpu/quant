"""THE TIER S LOOP, ONCE, END TO END (verifier gap D, 2026-09-30).

candidate -> judge/door -> promotion decision -> allocator tilt -> fills / execution science ->
shadow / rollback -> back into memory (failure_memory + the missed-growth ledger).

Every stage calls the REAL module function on fixture files; nothing in the chain is mocked. The
only substitutions are WHERE files live (a tmp directory and a scratch git repository) and the
firewall/suspension lookups the door makes about this host, which a fixture cannot own.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import execution_science as xs  # noqa: E402

from libs.portfolio import allocator_evidence  # noqa: E402
from libs.tiers import allocator_tilts, failure_memory, regression_stop  # noqa: E402
from research import missed_growth  # noqa: E402

GOOD = "EURUSD.session_range_breakout.asia"
BAD = "GBPUSD.session_range_breakout.asia"
HELD = "XAUUSD.momentum_volgate.london"
LATE = "AUDUSD.session_range_breakout.asia"
T0 = datetime(2026, 9, 1, tzinfo=UTC)
T1 = datetime(2026, 9, 15, tzinfo=UTC)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                          text=True).stdout.strip()


def _box(tmp_path: Path) -> tuple[Path, str, str]:
    """A scratch clone with two sealed releases: B changed an unsealed helper and the (sealed)
    promoter."""
    root = tmp_path / "box"
    (root / "libs" / "x").mkdir(parents=True)
    (root / "desks" / "mt5" / "research").mkdir(parents=True)
    (root / "desks" / "mt5" / "data" / "tier_s").mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "libs" / "x" / "entry_timing.py").write_text("DELAY = 0\n", "utf-8")
    (root / "desks" / "mt5" / "research" / "promoter.py").write_text("P = 1\n", "utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "release A")
    a = _git(root, "rev-parse", "HEAD")
    (root / "libs" / "x" / "entry_timing.py").write_text("DELAY = 3\n", "utf-8")
    (root / "desks" / "mt5" / "research" / "promoter.py").write_text("P = 2\n", "utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "release B")
    b = _git(root, "rev-parse", "HEAD")
    (root / "desks" / "mt5" / "data" / "LIVE_MANIFEST.jsonl").write_text(
        json.dumps({"code": a, "at": T0.isoformat()}) + "\n"
        + json.dumps({"code": b, "at": T1.isoformat()}) + "\n", "utf-8")
    (root / "desks" / "mt5" / "data" / "RELEASE.json").write_text(
        json.dumps({"code_sha": b, "money_path": ["desks/mt5/mt5desk/gateway.py"]}), "utf-8")
    return root, a, b


def _door(monkeypatch: Any, tmp_path: Path, root: Path) -> Any:
    from libs.tiers import authority
    from libs.tiers import promotion_authority as pa
    monkeypatch.setattr(pa, "ROOT", root)
    door = root / "door"                      # untracked, like the box's verdict files
    door.mkdir(exist_ok=True)
    for attr in ("REPLICATION", "FDR_ROWS", "FREEZE", "LEDGER", "DOOR_VERDICTS",
                 "CONSTITUTION"):
        monkeypatch.setattr(pa, attr, door / f"{attr}.json")
    monkeypatch.setattr(pa, "RATIFICATIONS", door / "RATIFICATIONS.jsonl")
    monkeypatch.setattr(pa.firewall, "may", lambda *a, **k: True)
    monkeypatch.setattr(authority, "suspended", lambda organ, *a, **k: False)
    return pa


def test_the_tier_s_loop_runs_once_end_to_end(monkeypatch: Any, tmp_path: Path) -> None:
    root, rel_a, rel_b = _box(tmp_path)
    pa = _door(monkeypatch, tmp_path, root)
    now = datetime.now(UTC).isoformat()

    # ---- 1. CANDIDATES meet the JUDGE at the DOOR -----------------------------------------
    pa.REPLICATION.write_text(json.dumps({"at": now, "verdicts": [
        {"cell": BAD, "verdict": "MISMATCH"}, {"cell": GOOD, "verdict": "MATCH"}]}), "utf-8")
    pa.FDR_ROWS.write_text(json.dumps({"generated_utc": now, "certified": []}), "utf-8")
    pa.FREEZE.write_text(json.dumps({"at": now, "verdict": "OK"}), "utf-8")
    pa.DOOR_VERDICTS.write_text(json.dumps({"generated_utc": now, "rows": {}}), "utf-8")
    verdicts = {name: pa.block(name) for name in (GOOD, BAD)}
    assert verdicts[GOOD] is None
    assert (verdicts[BAD] or "").startswith("REPLICATION_MISMATCH")

    # ---- 2. THE PROMOTION DECISION: admitted rows go LIVE, withheld rows are billed --------
    live_book = {HELD: 0.12}
    for name, why in verdicts.items():
        if why is None:
            live_book[name] = 0.08
        else:
            pa.record(name, why, lane="main", exp_r=0.15, n=40)
    assert set(live_book) == {HELD, GOOD}

    # ---- 3. THE ALLOCATOR TILT: exchange + capture, heat-neutral after the clip ------------
    group = {k: k for k in live_book}
    rows = allocator_tilts.build(live_book, group, {GOOD: 0.40, HELD: 0.05},
                                 {GOOD: {"capture": 1.4, "n": 60}})
    doc = {"kind": "tier_s_tilts", "generated_utc": now, "sleeves": rows}
    factors, why = allocator_evidence.tier_s_factors(doc)
    assert "read" in why and set(factors) == set(live_book)
    heat = sum(live_book.values())
    assert sum(live_book[k] * factors[k] for k in live_book) == pytest.approx(heat, abs=1e-5)
    assert factors[GOOD] > 1.0 > factors[HELD], "capital moved toward the exchange's choice"

    # ---- 4. FILLS -> EXECUTION SCIENCE: the live fills split into alpha and drag -----------
    corpus, ledger, trades = [], [], []
    for i in range(40):
        for rel_t, r_mult in ((T0, 0.6), (T1, -0.4)):
            deal = (1 if rel_t is T0 else 2) * 1000 + i
            t = rel_t + timedelta(hours=6 * (i + 1))
            corpus.append({"status": "FILLED", "sleeve": GOOD, "symbol": "EURUSD",
                           "direction": 1, "requested_price": 1.1000, "fill_price": 1.1001,
                           "deal": deal, "ticket": deal})
            ledger.append({"deal": deal, "position_id": deal, "entry_order": deal,
                           "sleeve": GOOD, "symbol": "EURUSD", "fill_price": 1.1000 + r_mult
                           * 0.002, "entry_price": 1.1001, "sl": 1.0981, "commission": -0.5,
                           "swap": 0.0, "volume": 0.1, "contract_size": 100000.0})
            trades.append({"time": t.isoformat(), "r_multiple": r_mult + 0.05 * ((i % 3) - 1),
                           "_group": GOOD})
    (tmp_path / "corpus.jsonl").write_text("".join(json.dumps(r) + "\n" for r in corpus),
                                           "utf-8")
    (tmp_path / "ledger.jsonl").write_text("".join(json.dumps(r) + "\n" for r in ledger),
                                           "utf-8")
    cal = xs._live_fill_calibration(tmp_path / "corpus.jsonl", tmp_path / "ledger.jsonl")
    assert cal["status"] == "MEASURED" and cal["split"]["n"] == 80
    assert cal["split"]["mean_execution_drag_r"] > 0
    assert cal["by_sleeve"][GOOD]["n"] == 80

    # ---- 5. SHADOW / ROLLBACK: release B regressed forward -> stop, roll back, patch -------
    releases = [{"sha": rel_a, "at": T0.isoformat()}, {"sha": rel_b, "at": T1.isoformat()}]
    stop = regression_stop.run(trades, releases, {GOOD: {"exp_r": 0.2}}, root=root,
                               apply=True)
    assert stop["state"] == "STOPPED" and stop["regression"]["verdict"] == "REGRESSED"
    assert stop["rollback"]["state"] == "APPLIED"
    assert (root / "libs" / "x" / "entry_timing.py").read_text("utf-8") == "DELAY = 0\n"
    assert (root / regression_stop.PATCH_REL).read_text("utf-8").count("promoter.py") >= 1
    # the stop halts further promotion under the regressed release, at the same door
    late = pa.block(LATE)
    assert (late or "").startswith("RELEASE_REGRESSION_STOP"), late
    pa.record(LATE, late or "", lane="main", exp_r=0.1, n=25)

    # ---- 6. BACK INTO MEMORY: the loop's failures become theorems and billed ledger lines --
    mem_rows = [{"mechanism": "session_range_breakout", "asset_class": "FX_MAJOR",
                 "selector": "asia", "passed": False, "terminal_gate": "forward",
                 "cell": f"live:{GOOD}"},
                {"mechanism": "session_range_breakout", "asset_class": "FX_MAJOR",
                 "selector": "asia", "passed": False, "terminal_gate": "forward",
                 "reason": verdicts[BAD] or "", "cell": f"door:{BAD}"}]
    mem = failure_memory.compress(mem_rows, min_trials=2)
    assert mem["theorems"] and mem["theorems"][0]["cause"] == "LIVE_DECAY"
    hood = failure_memory.neighbourhood({"mechanism": "session_range_breakout",
                                         "asset_class": "FX_MAJOR", "selector": "asia"}, mem)
    assert hood["explored"] == 2, "the next candidate in this neighbourhood sees the loop"
    blocks = [json.loads(x) for x in pa.LEDGER.read_text("utf-8").splitlines()]
    assert [b["reason"] for b in blocks] == ["REPLICATION_MISMATCH", "RELEASE_REGRESSION_STOP"]
    monkeypatch.setattr(missed_growth, "BASE", tmp_path / "desk")
    led = tmp_path / "desk" / "data" / "tier_s" / "promotion_blocks.jsonl"
    led.parent.mkdir(parents=True)
    led.write_text(pa.LEDGER.read_text("utf-8"), "utf-8")
    bill = missed_growth.measure_tier_s_block(None, {"book": live_book}, {})
    assert bill["n"] == 2 and bill["by_reason"] == {"REPLICATION_MISMATCH": 1,
                                                    "RELEASE_REGRESSION_STOP": 1}
