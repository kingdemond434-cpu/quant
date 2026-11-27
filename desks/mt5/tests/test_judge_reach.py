"""Judge reach: every producer's emitted > received > judged, the genuineness of what was judged,
and the page to Claude. Every input is synthetic and redirected into `tmp_path`."""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import family_spec as fs  # noqa: E402
from research import judge_reach as jr  # noqa: E402
from research import producer_loop as pl  # noqa: E402

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)


def _registry(path: Path, rows: list[tuple[str, str, str, str, str | None, dict, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE research_candidates (seq INTEGER PRIMARY KEY AUTOINCREMENT, "
                "producer TEXT, status TEXT, symbol TEXT, family TEXT, judged_at TEXT, "
                "params_json TEXT, exact_rules TEXT)")
    con.executemany("INSERT INTO research_candidates(producer, status, symbol, family, "
                    "judged_at, params_json, exact_rules) VALUES (?,?,?,?,?,?,?)",
                    [(p, s, sym, f, j, json.dumps(par), txt)
                     for p, s, sym, f, j, par, txt in rows])
    con.commit()
    con.close()


def _setup(tmp: Path, monkeypatch: Any, conversion: dict[str, Any],
           rows: list[Any], sandbox: dict[str, Any] | None = None) -> None:
    monkeypatch.setattr(pl, "CONVERSION", tmp / "reports" / "PRODUCER_CONVERSION.json")
    monkeypatch.setattr(jr, "LOOP_REPORT", tmp / "reports" / "PRODUCER_LOOP.json")
    monkeypatch.setattr(jr, "REGISTRY", tmp / "data" / "alpha_registry.sqlite")
    monkeypatch.setattr(jr, "OUT", tmp / "reports" / "JUDGE_REACH.json")
    monkeypatch.setattr(jr, "STATE", tmp / "data" / "judge_reach_state.json")
    monkeypatch.setattr(jr, "EVENTS", tmp / "data" / "events.jsonl")
    monkeypatch.setattr(jr, "SANDBOX_STATE", tmp / "data" / "sandbox_runner_state.json")
    pl.CONVERSION.parent.mkdir(parents=True, exist_ok=True)
    pl.CONVERSION.write_text(json.dumps(conversion), "utf-8")
    _registry(jr.REGISTRY, rows)
    if sandbox is not None:
        jr.SANDBOX_STATE.write_text(json.dumps(sandbox), "utf-8")


def _conv(**rows: tuple[int, int, int]) -> dict[str, Any]:
    return {"producers": [{"producer": k, "discoveries": 0, "candidates": c, "docket": d,
                           "judged": j, "certificates": 0}
                          for k, (c, d, j) in rows.items()]}


def _by(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {r["producer"]: r for r in doc["producers"]}


def _q(n: int, producer: str, params: dict, *, judged: bool = True, text: str = "") -> list:
    return [(producer, "judged" if judged else "queued", "EURUSD", "trend_ma_cross",
             NOW.isoformat() if judged else None, params, text) for _ in range(n)]


def test_family_spec_translates_and_names_every_non_executable() -> None:
    ok = fs.to_executable("trend_ma_cross", {"fast": 8, "slow": 34})
    assert ok["status"] == fs.EXECUTABLE and ok["params"] == {"fast_ema": 8, "slow_ema": 34}
    assert fs.to_executable("trend_ma_cross", {}, prose="a cross")["status"] == fs.PROSE_ONLY
    assert fs.to_executable("trend_ma_cross", {"fast_ema": 12, "slow_ema": 50})["status"] \
        == fs.DEFAULTS_ONLY
    assert fs.to_executable("trend_ma_cross", {"rr": 3.0})["status"] == fs.DEFAULTS_ONLY
    unread = fs.to_executable("trend_ma_cross", {"fast_ema": 7, "alpha": "x"})
    assert unread["status"] == fs.EXECUTABLE and unread["unread"] == ["alpha"]
    assert fs.to_executable("no_such_family", {"a": 1})["status"] == fs.UNREGISTERED_FAMILY
    assert fs.to_executable("mean_reversion_rsi", {"rsi_n": 7.5})["status"] == fs.DEFAULTS_ONLY


def test_the_guardian_flags_emitted_never_judged_and_passes_judged(
        tmp_path: Path, monkeypatch: Any) -> None:
    rows = (_q(30, "sandbox:quiet", {"fast_ema": 5}, judged=False)
            + _q(30, "miner:good", {"fast_ema": 7, "slow_ema": 30}))
    _setup(tmp_path, monkeypatch, _conv(**{"sandbox:quiet": (30, 0, 0),
                                           "miner:good": (30, 30, 30)}), rows)
    first = jr.write(jr.build(now=NOW), now=NOW)
    by = _by(first)
    # inside the grace the never-judged producer is not yet accused
    assert by["sandbox:quiet"]["verdict"] == jr.REACHING
    assert by["sandbox:quiet"]["received"] == 30
    assert by["miner:good"]["verdict"] == jr.REACHING
    later = NOW + timedelta(hours=jr.GRACE_H + 1)
    doc = jr.write(jr.build(now=later), now=later)
    by = _by(doc)
    assert by["sandbox:quiet"]["verdict"] == jr.LEAKING
    assert by["sandbox:quiet"]["stage"] == "JUDGE"
    assert by["miner:good"]["verdict"] == jr.REACHING
    assert doc["paged_this_pass"] == ["sandbox:quiet"]
    events = [json.loads(ln) for ln in jr.EVENTS.read_text("utf-8").splitlines()]
    assert len(events) == 1 and events[0]["kind"] == "PLUMBING_DEFECT"
    assert events[0]["organ"] == "judge_reach" and "sandbox:quiet" in events[0]["detail"]
    # page on change: the same flag an hour later is not paged again
    again = NOW + timedelta(hours=jr.GRACE_H + 2)
    doc = jr.write(jr.build(now=again), now=again)
    assert doc["paged_this_pass"] == []
    assert len(jr.EVENTS.read_text("utf-8").splitlines()) == 1


def test_judged_prose_and_defaults_are_not_genuine_reach(
        tmp_path: Path, monkeypatch: Any) -> None:
    rows = (_q(25, "sandbox:alpha101", {}, text="published formulaic alpha")
            + _q(25, "miner:defaults", {})
            + _q(25, "miner:good", {"fast_ema": 7, "slow_ema": 30}))
    _setup(tmp_path, monkeypatch, _conv(**{"sandbox:alpha101": (25, 25, 25),
                                           "miner:defaults": (25, 25, 25),
                                           "miner:good": (25, 25, 25)}), rows)
    by = _by(jr.write(jr.build(now=NOW), now=NOW, page=False))
    assert by["sandbox:alpha101"]["verdict"] == fs.PROSE_ONLY
    assert by["miner:defaults"]["verdict"] == fs.DEFAULTS_ONLY
    assert by["miner:good"]["verdict"] == jr.REACHING
    assert not jr.EVENTS.exists()


def test_a_loss_before_the_docket_is_named_or_flagged(tmp_path: Path, monkeypatch: Any) -> None:
    sandbox = {"systems": {
        "named": {"rows_emitted": 40, "rows_enqueued": 10,
                  "not_executable_by_reason": {"PROSE_ONLY": 30}, "enqueue_errors": 0},
        "broken": {"rows_emitted": 40, "rows_enqueued": 10,
                   "not_executable_by_reason": {}, "enqueue_errors": 30}}}
    rows = (_q(10, "sandbox:named", {"fast_ema": 7}) + _q(10, "sandbox:broken", {"fast_ema": 7}))
    _setup(tmp_path, monkeypatch, _conv(**{"sandbox:named": (10, 10, 10),
                                           "sandbox:broken": (10, 10, 10)}), rows, sandbox)
    jr.write(jr.build(now=NOW), now=NOW, page=False)
    later = NOW + timedelta(hours=jr.GRACE_H + 1)
    by = _by(jr.write(jr.build(now=later), now=later, page=False))
    assert by["sandbox:named"]["emitted"] == 40
    assert by["sandbox:named"]["lost_by_reason"] == {"PROSE_ONLY": 30}
    assert by["sandbox:named"]["verdict"] == jr.REACHING
    assert by["sandbox:broken"]["verdict"] == jr.LEAKING
    assert by["sandbox:broken"]["stage"] == "RECEIVE"


def test_an_unreadable_conversion_is_unmeasured_never_a_pass(
        tmp_path: Path, monkeypatch: Any) -> None:
    _setup(tmp_path, monkeypatch, {"producers": [{"producer": "x", "candidates": 5,
                                                  "judged": "UNMEASURED"}]},
           _q(5, "x", {"fast_ema": 7}, judged=False))
    by = _by(jr.write(jr.build(now=NOW), now=NOW, page=False))
    assert by["x"]["verdict"] == jr.UNMEASURED
