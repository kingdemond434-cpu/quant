"""Boot r23: the box guard holds the pen (zuck 2026-11-27 13:13Z; Audit design notes D1-D4)."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from ops.box_git import box_loop as L
from ops.box_git import guard as G

A, B, C = "a" * 40, "b" * 40, "c" * 40
OK = (True, "ORDINARY", "T unchanged")


def _d(**k):
    base = {"trust": OK, "static": [], "raises": [], "money": [], "risk": None, "smoke": None,
            "merges_today": 0, "rolled_back": set(), "held": False, "guard": "g"}
    base.update(k)
    return G.decide(B, A, **base)


# ------------------------------------------------------------------ decide
def test_a_non_money_ordinary_head_passes_without_any_run() -> None:
    v = _d()
    assert v.ok and v.cls == "PASS" and not v.money


def test_refuse_and_trust_come_first() -> None:
    assert _d(trust=(False, "REFUSE", "cap")).cls == "REFUSE"
    v = _d(trust=(False, "TRUST", "T changed"), money=["x.py"], risk=(True, "r"))
    assert v.cls == "TRUST" and not v.ok


def test_unmeasured_money_is_money_and_needs_risk_and_smoke() -> None:
    assert _d(money=None).cls == "FAIL"
    assert _d(money=None, risk=(True, "r")).why.startswith("smoke")
    v = _d(money=None, risk=(True, "r"), smoke=(True, "s"))
    assert v.ok and v.money


def test_a_red_risk_run_fails() -> None:
    assert not _d(money=["libs/risk/x.py"], risk=(False, "rc=1"), smoke=(True, "s")).ok


def test_static_problem_or_ceiling_raise_is_the_owners() -> None:
    assert _d(static=["x.py: new import requests"]).cls == "TRUST"
    assert _d(raises=["/a: 1 -> 2"]).cls == "TRUST"
    assert _d(raises=None).cls == "FAIL"


def test_hold_cap_and_rollback() -> None:
    assert _d(held=True).cls == "FAIL"
    assert not _d(rolled_back={B}).ok
    assert _d(rolled_back=None).cls == "FAIL"
    m = {"money": ["x.py"], "risk": (True, "r"), "smoke": (True, "s")}
    assert not _d(merges_today=G.MONEY_MERGES_PER_DAY, **m).ok
    assert _d(merges_today=None, **m).cls == "FAIL"
    assert _d(merges_today=G.MONEY_MERGES_PER_DAY - 1, **m).ok


# ------------------------------------------------------------------ the pen
def test_a_verdict_counts_only_for_its_sha_and_its_guard(tmp_path: Path) -> None:
    G.write_verdict(tmp_path, _d())
    assert G.read_verdict(tmp_path, B, "g") is not None
    assert G.read_verdict(tmp_path, B, "other-guard") is None
    assert G.read_verdict(tmp_path, C, "g") is None
    assert G.read_verdict(tmp_path, "../x", "g") is None
    G.write_verdict(tmp_path, _d(held=True))
    assert G.read_verdict(tmp_path, B, "g") is None  # a later FAIL replaces the PASS


def test_the_guard_hash_moves_with_any_byte(tmp_path: Path) -> None:
    f = tmp_path / "guard.py"
    f.write_text("a", encoding="utf-8")
    h1 = G.guard_hash([f])
    f.write_text("b", encoding="utf-8")
    assert G.guard_hash([f]) != h1
    assert G.guard_hash([tmp_path / "missing.py"]) != G.guard_hash([f])


# ------------------------------------------------------------------ D2
def test_static_counts_new_uses_only() -> None:
    base = "import json\n"
    assert G.static_problems([("m.py", base, base + "import requests\n")]) == [
        "m.py: new import requests (base 0 -> head 1)"]
    old = "import subprocess\nsubprocess.run(['x'])\n"
    assert G.static_problems([("m.py", old, old + "x = 1\n")]) == []
    assert G.static_problems([("m.py", None, "eval('1')\n")]) == [
        "m.py: new call eval (base 0 -> head 1)"]
    assert G.static_problems([("m.py", "", "p = r'C:\\ProgramData\\QuantBox\\guard\\v'\n")])
    assert G.static_problems([("m.py", "", "def (:\n")]) == ["m.py: does not parse"]
    assert G.static_problems([("m.py", "x", None), ("doc.md", "", "eval(")]) == []


# ------------------------------------------------------------------ D4
def test_ceiling_raises() -> None:
    b = json.dumps({"rows": [["max", "f.py", "DAILY", 0.05]], "heat": 0.3})
    assert G.ceiling_raises(b, b) == []
    lower = json.dumps({"rows": [["max", "f.py", "DAILY", 0.04]], "heat": 0.3})
    assert G.ceiling_raises(b, lower) == []
    up = json.dumps({"rows": [["max", "f.py", "DAILY", 0.05]], "heat": 0.35})
    assert G.ceiling_raises(b, up) == ["/heat: 0.3 -> 0.35"]
    assert G.ceiling_raises(b, "{") is None


def test_money_merges_and_rollbacks(tmp_path: Path) -> None:
    now = datetime(2026, 11, 27, 13, 0, tzinfo=UTC)
    G.record_merge(tmp_path, 1, B, C, True, now=now - timedelta(hours=1))
    G.record_merge(tmp_path, 2, A, "d" * 40, False, now=now)
    G.record_merge(tmp_path, 3, A, "e" * 40, True, now=now - timedelta(hours=30))
    assert G.money_merges_today(tmp_path, now) == 1
    rb = tmp_path / "rb.jsonl"
    rb.write_text(json.dumps({"bad": C}) + "\n", encoding="utf-8")
    assert G.rolled_back_heads(tmp_path, rb) == {B}
    rb.write_text("{", encoding="utf-8")
    assert G.rolled_back_heads(tmp_path, rb) is None
    (tmp_path / G.LEDGER).write_text("garbled\n", encoding="utf-8")
    assert G.money_merges_today(tmp_path, now) is None


# ------------------------------------------------------------------ wiring
def test_r23_switches() -> None:
    assert L.GUARD_LIVE is True and L.REQUIRE_SEAT_CLEAR is True


def _wire(monkeypatch, tmp_path, *, money, risk=(True, "risk ok"), trust=OK):
    posts = []

    class WT:
        def __init__(self, *a): pass
        def __enter__(self): return tmp_path
        def __exit__(self, *a): return False
    monkeypatch.setattr(L, "worktree", WT)
    monkeypatch.setattr(L, "money_changes", lambda *a: (money, "m"))
    monkeypatch.setattr(L, "pinned_trust", lambda *a: trust)
    monkeypatch.setattr(L, "_show", lambda cfg, sha, path: "import json\n")
    monkeypatch.setattr(L, "risk_job", lambda *a, **k: risk)
    monkeypatch.setattr(L, "smoke_job", lambda *a: (True, "smoke ok"))
    monkeypatch.setattr(L, "_held_by_audit", lambda *a: False)
    monkeypatch.setattr(L, "guard_id", lambda cfg: "g")
    monkeypatch.setattr(L, "post", lambda cfg, sha, st, desc, ctx=None: posts.append((st, ctx)))
    cfg = SimpleNamespace(guard_dir=tmp_path / "guard", work=tmp_path, python="py",
                          ci_jobs=None)
    return cfg, posts


def test_guard_check_writes_the_pen_and_both_statuses(monkeypatch, tmp_path) -> None:
    cfg, posts = _wire(monkeypatch, tmp_path, money=["libs/risk/x.py"])
    out = L.guard_check(cfg, {"number": 5}, A, B, ["libs/risk/x.py"])
    assert "guard PASS" in out
    assert G.read_verdict(cfg.guard_dir, B, "g") is not None
    assert posts == [("success", (G.CONTEXT,)), ("success", (L.RISK_CONTEXT,))]


def test_a_trust_head_keeps_the_owner_path_open(monkeypatch, tmp_path) -> None:
    cfg, posts = _wire(monkeypatch, tmp_path, money=["x.py"],
                       trust=(False, "TRUST", "T changed"))
    L.guard_check(cfg, {"number": 6}, A, B, ["x.py"])
    assert posts == [("failure", (G.CONTEXT,)), ("success", (L.RISK_CONTEXT,))]
    assert G.read_verdict(cfg.guard_dir, B, "g") is None


def test_a_red_risk_run_closes_both_paths(monkeypatch, tmp_path) -> None:
    cfg, posts = _wire(monkeypatch, tmp_path, money=["x.py"], risk=(False, "rc=1"))
    L.guard_check(cfg, {"number": 7}, A, B, ["x.py"])
    assert posts == [("failure", (G.CONTEXT,)), ("failure", (L.RISK_CONTEXT,))]


class _Forge:
    def __init__(self, prs, comments):
        self.prs, self.comments, self.calls = prs, comments, []

    def gh(self, path, *a, data=None):
        if "pulls?state=open" in path:
            return self.prs
        if path.endswith("/comments"):
            return self.comments
        self.calls.append((path, data))
        return {}


def _merge_env(monkeypatch, tmp_path, comments, ancestor=True):
    gd = tmp_path / "guard"
    G.write_verdict(gd, G.decide(B, A, trust=OK, static=[], raises=[], money=["x.py"],
                                 risk=(True, "r"), smoke=(True, "s"), merges_today=0,
                                 rolled_back=set(), held=False, guard="g"))
    f = _Forge([{"number": 9, "head": {"sha": B, "ref": "claude/x"}}], comments)
    monkeypatch.setattr(L, "_forge", lambda cfg, who: f)
    monkeypatch.setattr(L, "guard_id", lambda cfg: "g")
    monkeypatch.setattr(L, "live_head", lambda cfg: C)
    monkeypatch.setattr(L, "_held_by_audit", lambda *a: False)
    monkeypatch.setattr(L, "_run", lambda *a, **k: (0 if ancestor else 1, ""))
    return SimpleNamespace(guard_dir=gd, bare=tmp_path), f


def test_merge_waits_for_the_seat_clear_while_r24_is_not_in(monkeypatch, tmp_path) -> None:
    cfg, f = _merge_env(monkeypatch, tmp_path, [])
    assert "waits for the Auditor" in L.guard_merge_tick(cfg) and f.calls == []


def test_merge_pinned_to_the_head_and_recorded(monkeypatch, tmp_path) -> None:
    cfg, f = _merge_env(monkeypatch, tmp_path, [{"body": f"AUDIT CLEAR {B} merge"}])
    assert "#9 merged (money)" in L.guard_merge_tick(cfg)
    assert f.calls[0][0].endswith("/pulls/9/merge") and f.calls[0][1]["sha"] == B
    assert G.money_merges_today(cfg.guard_dir) == 1


def test_a_money_head_behind_live_is_brought_up_not_merged(monkeypatch, tmp_path) -> None:
    cfg, f = _merge_env(monkeypatch, tmp_path, [{"body": f"AUDIT CLEAR {B} merge"}],
                        ancestor=False)
    assert "brought up" in L.guard_merge_tick(cfg)
    assert f.calls[0][0].endswith("/update-branch")
