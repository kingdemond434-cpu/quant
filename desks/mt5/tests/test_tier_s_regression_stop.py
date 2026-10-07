"""THE AUTOMATIC REGRESSION STOP AND ROLLBACK (verifier gap B) and THE BILL FOR FAILING CLOSED
(gap E), driven over a scratch git repository -- never the live checkout, never the terminal."""
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

from libs.tiers import regression_stop as rs  # noqa: E402

T0 = datetime(2026, 9, 1, tzinfo=UTC)
T1 = datetime(2026, 9, 15, tzinfo=UTC)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                          text=True).stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, str, str]:
    root = tmp_path / "box"
    (root / "libs" / "x").mkdir(parents=True)
    (root / "desks" / "mt5" / "research").mkdir(parents=True)
    (root / "desks" / "mt5" / "data" / "tier_s").mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "libs" / "x" / "sizing_helper.py").write_text("K = 1\n", "utf-8")
    (root / "desks" / "mt5" / "research" / "promoter.py").write_text("P = 1\n", "utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "release A")
    a = _git(root, "rev-parse", "HEAD")
    (root / "libs" / "x" / "sizing_helper.py").write_text("K = 2  # the regression\n", "utf-8")
    (root / "desks" / "mt5" / "research" / "promoter.py").write_text("P = 2\n", "utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "release B")
    b = _git(root, "rev-parse", "HEAD")
    # the box's state: sealed releases and the running release (untracked, like the box's)
    (root / "desks" / "mt5" / "data" / "LIVE_MANIFEST.jsonl").write_text(
        json.dumps({"code": a, "at": T0.isoformat()}) + "\n"
        + json.dumps({"code": b, "at": T1.isoformat()}) + "\n", "utf-8")
    (root / "desks" / "mt5" / "data" / "RELEASE.json").write_text(
        json.dumps({"code_sha": b, "money_path": ["desks/mt5/mt5desk/gateway.py"]}), "utf-8")
    return root, a, b


def _trades(prev_mean: float, cur_mean: float, n: int = 40) -> list[dict[str, Any]]:
    out = []
    for i in range(n):
        jitter = 0.1 * ((i % 5) - 2)
        out.append({"time": (T0 + timedelta(hours=6 * (i + 1))).isoformat(),
                    "r_multiple": prev_mean + jitter, "_group": "EURUSD.orb"})
        out.append({"time": (T1 + timedelta(hours=6 * (i + 1))).isoformat(),
                    "r_multiple": cur_mean + jitter, "_group": "EURUSD.orb"})
    return out


EXP = {"EURUSD.orb": {"exp_r": 0.2, "n": 50}}


def _releases(a: str, b: str) -> list[dict[str, Any]]:
    return [{"sha": a, "at": T0.isoformat(), "sealed": True},
            {"sha": b, "at": T1.isoformat(), "sealed": True}]


def test_forward_regression_definition() -> None:
    rel = _releases("a" * 40, "b" * 40)
    assert rs.forward_regression(_trades(0.5, -0.3), rel, EXP)["verdict"] == "REGRESSED"
    assert rs.forward_regression(_trades(0.5, 0.6), rel, EXP)["verdict"] == "HOLDING"
    few = rs.forward_regression(_trades(0.5, -0.3, n=10), rel, EXP)
    assert few["verdict"] == "UNMEASURED" and few["n_current"] == 10
    assert rs.forward_regression(_trades(0.5, -0.3), rel[:1], EXP)["verdict"] == "UNMEASURED"
    # unpriced trades (no forward expectancy for the group) are counted, never guessed
    res = rs.forward_regression(_trades(0.5, -0.3), rel, {})
    assert res["verdict"] == "UNMEASURED" and res["unpriced_trades"] == 80


def test_regression_stops_rolls_back_unsealed_and_patches_sealed(tmp_path: Path) -> None:
    root, a, b = _repo(tmp_path)
    doc = rs.run(_trades(0.5, -0.3), _releases(a, b), EXP, root=root, apply=True)
    assert doc["state"] == "STOPPED" and doc["release"] == b
    rb = doc["rollback"]
    assert rb["state"] == "APPLIED", rb
    assert rb["unsealed_paths"] == ["libs/x/sizing_helper.py"]
    assert rb["sealed_paths"] == ["desks/mt5/research/promoter.py"]
    # the unsealed code is back to release A, in ONE new commit on top of B (no rewrite)
    assert (root / "libs" / "x" / "sizing_helper.py").read_text("utf-8") == "K = 1\n"
    assert _git(root, "rev-parse", "HEAD~1") == b
    # the sealed file is untouched by the organ; its return is a patch that applies cleanly
    assert (root / "desks" / "mt5" / "research" / "promoter.py").read_text("utf-8") == "P = 2\n"
    patch = root / rs.PATCH_REL
    assert "promoter.py" in patch.read_text("utf-8")
    _git(root, "apply", "--check", str(patch))
    # the stop is on disk and the door reads it while the stopped release runs
    assert json.loads((root / rs.STOP_REL).read_text("utf-8"))["state"] == "STOPPED"
    why = rs.stop_reason(root)
    assert why and why.startswith("RELEASE_REGRESSION_STOP")
    # a second pass never applies twice, and a quiet window does not clear the stop
    again = rs.run(_trades(0.5, -0.3), _releases(a, b), EXP, root=root, apply=True)
    assert again["rollback"]["commit"] == rb["commit"]
    quiet = rs.run([], _releases(a, b), EXP, root=root, apply=True)
    assert quiet["state"] == "STOPPED"
    # the running release moves off the stopped one: the stop clears and the door opens
    rel_json = root / "desks" / "mt5" / "data" / "RELEASE.json"
    rel_json.write_text(json.dumps({"code_sha": rb["commit"]}), "utf-8")
    assert rs.stop_reason(root) is None
    cleared = rs.run([], _releases(a, b), EXP, root=root, apply=True)
    assert cleared["state"] == "CLEARED"


def test_apply_never_clobbers_an_uncommitted_edit(tmp_path: Path) -> None:
    root, a, b = _repo(tmp_path)
    (root / "libs" / "x" / "sizing_helper.py").write_text("K = 3  # work in progress\n", "utf-8")
    doc = rs.run(_trades(0.5, -0.3), _releases(a, b), EXP, root=root, apply=True)
    assert doc["state"] == "STOPPED"
    assert doc["rollback"]["state"] == "APPLY_DEFERRED"
    assert "work in progress" in (root / "libs" / "x" / "sizing_helper.py").read_text("utf-8")


def test_holding_release_writes_a_clear_artifact(tmp_path: Path) -> None:
    root, a, b = _repo(tmp_path)
    doc = rs.run(_trades(0.5, 0.6), _releases(a, b), EXP, root=root, apply=True)
    assert doc["state"] == "CLEAR"
    assert rs.stop_reason(root) is None
    assert _git(root, "rev-parse", "HEAD") == b


def _door(monkeypatch: Any, tmp_path: Path) -> Any:
    from libs.tiers import authority
    from libs.tiers import promotion_authority as pa
    monkeypatch.setattr(pa, "ROOT", tmp_path)
    for attr in ("REPLICATION", "FDR_ROWS", "FREEZE", "LEDGER", "DOOR_VERDICTS",
                 "CONSTITUTION"):
        monkeypatch.setattr(pa, attr, tmp_path / f"{attr}.json")
    monkeypatch.setattr(pa, "RATIFICATIONS", tmp_path / "RATIFICATIONS.jsonl")
    monkeypatch.setattr(pa.firewall, "may", lambda *a, **k: True)
    monkeypatch.setattr(authority, "suspended", lambda organ, *a, **k: False)
    return pa


def _fresh(pa: Any, now: str) -> None:
    pa.REPLICATION.write_text(json.dumps({"at": now}), "utf-8")
    pa.FDR_ROWS.write_text(json.dumps({"generated_utc": now}), "utf-8")
    pa.FREEZE.write_text(json.dumps({"at": now, "verdict": "OK"}), "utf-8")
    pa.DOOR_VERDICTS.write_text(json.dumps({"generated_utc": now, "rows": {}}), "utf-8")


def test_the_door_withholds_under_a_stopped_release_and_fails_closed_on_damage(
        monkeypatch: Any, tmp_path: Path) -> None:
    pa = _door(monkeypatch, tmp_path)
    _fresh(pa, datetime.now(UTC).isoformat())
    assert pa.block("EURUSD.x") is None
    stop = tmp_path / rs.STOP_REL
    stop.parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / rs.RELEASE_REL).write_text(json.dumps({"code_sha": "b" * 40}), "utf-8")
    stop.write_text(json.dumps({"state": "STOPPED", "release": "b" * 40, "why": "t"}), "utf-8")
    assert (pa.block("EURUSD.x") or "").startswith("RELEASE_REGRESSION_STOP")
    (tmp_path / rs.RELEASE_REL).write_text(json.dumps({"code_sha": "c" * 40}), "utf-8")
    assert pa.block("EURUSD.x") is None, "the running release moved on"
    stop.write_text("{torn", "utf-8")
    assert (pa.block("EURUSD.x") or "").startswith("DOOR_ERROR")


def test_every_door_error_withhold_is_billed_to_its_input_and_window(
        monkeypatch: Any, tmp_path: Path) -> None:
    """Gap E: first adoption -- REPLICATION.json stale -- every row withheld (fail closed stays),
    and every withheld row is a missed-growth line naming the input and the window."""
    from research import missed_growth as mg
    pa = _door(monkeypatch, tmp_path)
    now = datetime.now(UTC)
    _fresh(pa, now.isoformat())
    stale_at = now - timedelta(hours=30)
    pa.REPLICATION.write_text(json.dumps({"at": stale_at.isoformat()}), "utf-8")
    for i, exp_r in enumerate([0.3, 0.1, -0.05]):
        name = f"EURUSD.cert{i}"
        why = pa.block(name)
        assert why and why.startswith("DOOR_ERROR"), why       # fail-closed not relaxed
        pa.record(name, why, lane="main", exp_r=exp_r, n=40)
    pa.REPLICATION.unlink()                                    # never written at all
    why = pa.block("XAUUSD.cert9")
    assert why and why.startswith("DOOR_ERROR")
    pa.record("XAUUSD.cert9", why, lane="main", exp_r=0.2, n=12)
    rows = [json.loads(x) for x in pa.LEDGER.read_text("utf-8").splitlines()]
    assert len(rows) == 4 and all(r["reason"] == "DOOR_ERROR" for r in rows)
    first = rows[0]["door_error"]
    assert first["input"] == "replication" and first["state"] == "STALE"
    assert first["input_file"].endswith("REPLICATION.json")
    assert first["window_start"] == (stale_at + timedelta(hours=pa.MAX_AGE_H)).isoformat(
        timespec="seconds")
    assert rows[-1]["door_error"]["state"] == "ABSENT"
    # the existing missed-growth mechanism bills them, per input, over the window
    monkeypatch.setattr(mg, "BASE", tmp_path / "desk")
    ledger = tmp_path / "desk" / "data" / "tier_s" / "promotion_blocks.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(pa.LEDGER.read_text("utf-8"), "utf-8")
    out = mg.measure_tier_s_block(None, {"book": {"a": 0.05, "b": 0.05}}, {})
    bill = out["door_error"]
    assert bill["n"] == 4
    line = bill["lines"][0]
    assert line["input"] == "replication" and line["n_withheld"] == 4
    assert line["window"]["from"] == first["window_start"]
    assert line["sum_withheld_r"] == pytest.approx(0.55)
    assert line["logw_forgone"] == pytest.approx(0.55 * 0.05)
    assert line["verdict"] == mg.COSTS
