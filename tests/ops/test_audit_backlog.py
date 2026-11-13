"""scripts/audit_backlog.py: what the Auditor owes, in order, with ages and an alarm."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "audit_backlog", ROOT / "scripts" / "audit_backlog.py"
)
assert _spec and _spec.loader
ab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ab)

NOW = datetime(2026, 11, 13, 20, 0, tzinfo=UTC)
HEAD = "a" * 40
OLD = "b" * 40
MONEY = frozenset({"desks/mt5/mt5desk/gateway.py"})


def _pr(n: int = 1, draft: bool = False, head: str = HEAD) -> dict:
    return {
        "number": n,
        "title": f"pr {n}",
        "draft": draft,
        "head": {"sha": head},
        "updated_at": NOW.isoformat(),
    }


def _v(verdict: str, sha: str, at: str, by: str = "auditor") -> dict:
    return {"verdict": verdict, "sha": sha, "at": at, "method": "merge", "by": by}


def _never(_: str) -> bool:
    return False


def _item(files, verdicts=(), hours=1.0, draft=False, protected=_never):
    pushed = (NOW - timedelta(hours=hours)).isoformat()
    return ab.item(
        _pr(draft=draft), list(files), list(verdicts), pushed, NOW, MONEY, True, protected
    )


def test_a_verdict_on_an_older_head_does_not_count() -> None:
    it = _item(["libs/x.py"], [_v("CLEAR", OLD, "2026-11-13T10:00:00Z")])
    assert it["state"] == "OWED"


def test_a_clear_on_the_head_is_not_owed_and_a_hold_is_held() -> None:
    assert _item(["a.py"], [_v("CLEAR", HEAD, "2026-11-13T10:00:00Z")])["state"] == "CLEARED"
    assert _item(["a.py"], [_v("HOLD", HEAD, "2026-11-13T10:00:00Z")])["state"] == "HELD"


def test_an_edit_after_the_clear_makes_it_owed_again() -> None:
    vs = [
        _v("CLEAR", HEAD, "2026-11-13T10:00:00Z"),
        _v("HOLD", "0" * 40, "2026-11-13T11:00:00Z", by="x (an edited comment)"),
    ]
    assert _item(["a.py"], vs)["state"] == "OWED"


def test_priority_money_path_then_protected_then_ready_then_draft() -> None:
    assert _item(["desks/mt5/mt5desk/gateway.py"])["priority"] == "P1"
    assert _item(["ops/x.txt"], protected=lambda f: f == "ops/x.txt")["priority"] == "P1"
    assert _item(["libs/x.py"])["priority"] == "P2"
    assert _item(["libs/x.py"], draft=True)["priority"] == "P3"
    assert _item([])["priority"] == "P1"  # unreadable file list never ranks lower


def test_an_unreadable_release_falls_back_to_the_money_dirs() -> None:
    p, _ = ab.priority(["libs/portfolio/rails.py"], True, frozenset(), False, _never)
    assert p == "P1"


def test_sla_breach_and_alarm() -> None:
    late = _item(["desks/mt5/mt5desk/gateway.py"], hours=7)  # P1, SLA 6 h
    fresh = _item(["libs/x.py"], hours=1)
    assert late["breach"] and not fresh["breach"]
    snap = ab.summarise([fresh, late], NOW, {"measured": True, "uncovered": []})
    assert snap["verdict"] == "ALARM" and snap["breaches"] == 1
    assert snap["next"][0]["priority"] == "P1"  # strictest first


def test_clean_backlog_is_ok_and_depth_counts_only_owed() -> None:
    a = _item(["libs/x.py"], hours=1)
    b = _item(["libs/x.py"], [_v("CLEAR", HEAD, "2026-11-13T10:00:00Z")])
    snap = ab.summarise([a, b], NOW, {"measured": True, "uncovered": []})
    assert snap["verdict"] == "OK" and snap["depth"] == 1 and snap["cleared_unmerged"] == 1


def test_unvouched_live_code_is_p0_and_alarms() -> None:
    snap = ab.summarise([], NOW, {"measured": True, "uncovered": ["libs/ops/x.py"], "age_h": 3})
    assert snap["by_priority"]["P0"] == 1 and snap["breaches"] == 1
    assert snap["verdict"] == "ALARM"


def test_an_unmeasured_p0_is_said_not_hidden() -> None:
    snap = ab.summarise([], NOW, {"measured": False, "error": "shallow clone"})
    assert snap["verdict"] == "ALARM" and any("P0 unmeasured" in w for w in snap["why"])


def test_depth_over_the_cap_alarms_even_when_every_item_is_young() -> None:
    items = [_item(["libs/x.py"], hours=0.1) for _ in range(ab.MAX_DEPTH + 1)]
    snap = ab.summarise(items, NOW, {"measured": True, "uncovered": []})
    assert snap["verdict"] == "ALARM" and not snap["breaches"]


def test_the_script_never_writes_to_github() -> None:
    src = (ROOT / "scripts" / "audit_backlog.py").read_text("utf-8")
    for verb in ("-X", "--method", "POST", "PATCH", "-f ", "--field"):
        assert f'"{verb}"' not in src, verb
