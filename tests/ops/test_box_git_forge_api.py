"""The audit gate's facts from the box forge: same rules, trust re-anchored, fail closed."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.box_git import forge_api as F  # noqa: E402

SHA = "a" * 40


def _gate():
    spec = importlib.util.spec_from_file_location("_t_gate", ROOT / ".github/scripts/audit_gate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Fake:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, method, path, body):
        self.calls.append((method, path, body))
        for (m, prefix), val in self.routes.items():
            if m == method and path.startswith(prefix):
                return val(path, body) if callable(val) else val
        raise AssertionError(f"unexpected {method} {path}")


def _forge(routes):
    g = _gate()
    return F.Forge(Fake(routes), workflow_of=g.WORKFLOW_OF, git=lambda *a: "0"), g


STATUSES = [
    {"id": 11, "context": "quality", "status": "success", "created_at": "2026-11-19T10:00:00Z",
     "creator": {"login": "box-ci"}},
    {"id": 12, "context": "mt5-money-path", "status": "success",
     "created_at": "2026-11-19T10:00:00Z", "creator": {"login": "box-ci"}},
    {"id": 13, "context": "coverage-floor", "status": "success",
     "created_at": "2026-11-19T10:00:00Z", "creator": {"login": "box-ci"}},
]


def test_box_ci_statuses_pass_the_gates_own_checks_and_provenance() -> None:
    f, g = _forge({("GET", f"/repos/quant/quant/commits/{SHA}/statuses"): STATUSES})
    runs = f.gh(f"repos/x/y/commits/{SHA}/check-runs?per_page=100")["check_runs"]
    g._gh = f.gh
    genuine = g.provenance("x/y", 7, SHA)
    assert all(genuine(r) for r in runs)
    assert g.checks(runs, genuine=genuine)[0] == "pass"


def test_a_thread_cannot_post_its_own_green() -> None:
    forged = [{**s, "creator": {"login": "claude"}} for s in STATUSES]
    f, g = _forge({("GET", f"/repos/quant/quant/commits/{SHA}/statuses"): forged})
    runs = f.gh(f"repos/x/y/commits/{SHA}/check-runs")["check_runs"]
    assert runs == []
    assert g.checks(runs)[0] == "pending"


def test_a_failed_box_ci_status_fails_the_gate() -> None:
    bad = [dict(STATUSES[0], status="failure"), *STATUSES[1:]]
    f, g = _forge({("GET", f"/repos/quant/quant/commits/{SHA}/statuses"): bad})
    assert g.checks(f.gh(f"repos/x/y/commits/{SHA}/check-runs")["check_runs"])[0] == "fail"


def test_only_the_owner_account_reads_as_zucks_own_typing() -> None:
    rows = [{"id": 1, "user": {"login": "quant-admin"}, "body": "APPROVE MERGES",
             "created_at": "2026-11-19T10:00:00Z", "updated_at": "2026-11-19T10:00:00Z"},
            {"id": 2, "user": {"login": "claude"}, "body": "APPROVE MERGES",
             "created_at": "2026-11-19T10:00:00Z", "updated_at": "2026-11-19T10:00:00Z"}]
    f, g = _forge({("GET", "/repos/quant/quant/issues/5/comments"): rows})
    f.approvals_issue = 5
    got = f.gh("repos/x/y/issues/453/comments?per_page=100", "--paginate", "--slurp")[0]
    assert [g._zuck_typed(c) for c in got] == [True, False]


def test_merges_stay_pinned_to_the_head() -> None:
    f, _ = _forge({("POST", "/repos/quant/quant/pulls/7/merge"): None})
    f.gh("repos/x/y/pulls/7/merge", "-X", "PUT", data={"sha": SHA, "merge_method": "merge"})
    assert f.t.calls[-1][2]["head_commit_id"] == SHA
    with pytest.raises(RuntimeError):
        f.gh("repos/x/y/pulls/7/merge", "-X", "PUT", data={"merge_method": "merge"})


def test_anything_without_a_truthful_answer_fails_closed() -> None:
    f, _ = _forge({})
    with pytest.raises(RuntimeError):
        f.gh("repos/x/y/actions/workflows/trusted-eval.yml/runs?head_sha=" + SHA)


def test_the_gate_uses_the_forge_only_when_configured(monkeypatch) -> None:
    g = _gate()
    seen = []

    class Stub:
        def gh(self, *a, data=None):
            seen.append(a)
            return {"ok": True}
    monkeypatch.setenv("QUANT_FORGE_URL", "https://127.0.0.1:3443")
    monkeypatch.setattr(g, "_FORGE", Stub())
    assert g._gh("repos/x/y/pulls/1") == {"ok": True} and seen
