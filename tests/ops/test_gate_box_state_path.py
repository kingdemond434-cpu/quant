"""The box's state reaches LIVE through the gate (Governance, 2026-11-14).

A `box-state/` PR opened by the box's own app, whose every file is ungoverned box state, merges at
once with no CLEAR, approval or CI. Anything else on that branch -- code, prose, a governed file,
another author -- is refused, never routed elsewhere. This is what lets a GitHub rule refuse every
direct push to LIVE without stopping the box's state.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "audit_gate_box_state", ROOT / ".github/scripts/audit_gate.py"
)
assert _spec is not None and _spec.loader is not None
ag = importlib.util.module_from_spec(_spec)
sys.modules["audit_gate_box_state"] = ag
_spec.loader.exec_module(ag)

H = "a" * 40
STATE = "desks/mt5/data/shadow_health.json"


def _files(*names: str) -> list[dict[str, Any]]:
    return [{"filename": n, "status": "modified"} for n in names]


def _commit(
    login: str = "quant-merger[bot]",
    verified: bool = True,
    committer: str = "quant-merger[bot]",
    reason: str = "valid",
) -> dict[str, Any]:
    return {
        "sha": "c" * 40,
        "author": {"login": login},
        "committer": {"login": committer},
        "commit": {"verification": {"verified": verified, "reason": reason}},
    }


class FakeGH:
    def __init__(self, files: list[dict[str, Any]], author: str = "quant-merger[bot]",
                 ref: str = "box-state/2026-11-14_1400") -> None:  # fmt: skip
        self.pr = {
            "number": 7, "state": "open", "draft": False, "user": {"login": author},
            "head": {"sha": H, "ref": ref, "repo": {"full_name": "o/r"}},
            "base": {"ref": ag.LIVE}, "labels": [], "changed_files": len(files),
        }  # fmt: skip
        self.files = files
        self.comments: list[dict[str, Any]] = []
        self.commits: list[dict[str, Any]] = [_commit()]
        self.writes: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, *args: str, data: Any = None) -> Any:
        path = args[0]
        if "-X" in args:
            self.writes.append((path, dict(data or {})))
            return None
        if "/files?" in path:
            return [self.files]
        if "/commits?" in path:
            return [self.commits]
        if path.endswith("/comments?per_page=100"):
            return [self.comments]
        return self.pr

    def merged(self) -> bool:
        return any(p.endswith("/merge") for p, _ in self.writes)


def _run(gh: FakeGH) -> int:
    saved = ag._gh
    ag._gh = gh
    try:
        return int(ag.run("o/r", 7, ag.LIVE, 0.0, box=True))
    finally:
        ag._gh = saved


def test_ungoverned_box_state_from_the_box_merges_at_once() -> None:
    gh = FakeGH(_files(STATE, "desks/mt5/reports/BOX_STATE_FLOW.json", "logs/x.log"))
    assert _run(gh) == 0
    assert gh.merged()
    data = next(d for p, d in gh.writes if p.endswith("/merge"))
    assert data["sha"] == H and data["merge_method"] == "merge"
    assert "box state" in data["commit_title"]


def test_code_on_a_box_state_branch_is_refused_not_rerouted() -> None:
    for name in ("desks/mt5/gateway.py", "libs/ops/release.py", "desks/mt5/data/run.ps1",
                 "desks/mt5/data/x.py", "docs/cro/CRO_CYCLE.md", "web/index.html",
                 ".github/workflows/ci.yml"):  # fmt: skip
        gh = FakeGH(_files(STATE, name))
        assert _run(gh) == 1, name
        assert not gh.merged(), name


def test_a_rename_out_of_state_into_code_is_refused() -> None:
    gh = FakeGH([{"filename": "desks/mt5/research/x.json", "previous_filename": STATE,
                  "status": "renamed"}])  # fmt: skip
    assert _run(gh) == 1 and not gh.merged()


def test_governed_state_never_takes_this_path() -> None:
    for name in (
        "desks/mt5/data/LIVE_MANIFEST.jsonl",
        "desks/mt5/data/IMMUTABLE_MANIFEST.json",
        "desks/mt5/data/GENERIC_EXEC_ENABLED",
        "desks/mt5/reports/ALLOCATOR_PROOF.json",
    ):
        gh = FakeGH(_files(STATE, name))
        assert _run(gh) == 1, name
        assert not gh.merged(), name


def test_only_the_box_s_app_may_open_one() -> None:
    gh = FakeGH(_files(STATE), author="kingdemond434-cpu")
    assert _run(gh) == 1 and not gh.merged()


def test_a_hold_stops_it_and_a_secret_is_still_refused() -> None:
    gh = FakeGH(_files(STATE))
    gh.comments = [
        {
            "body": f"AUDIT HOLD {H}",
            "created_at": "2026-11-14T00:00:00Z",
            "updated_at": "2026-11-14T00:00:00Z",
            "author_association": "OWNER",
            "performed_via_github_app": None,
            "user": {"login": "kingdemond434-cpu"},
        }
    ]
    assert _run(gh) == 0 and not gh.merged()
    gh = FakeGH(_files(STATE, "data/secrets/key.json"))
    assert _run(gh) == 1 and not gh.merged()


def test_an_incomplete_listing_is_never_box_state() -> None:
    ok, why = ag.box_state_only(_files(STATE), 2)
    assert not ok and "1 of 2" in why


def test_the_branch_and_the_author_are_pinned() -> None:
    assert ag.BOX_STATE_BRANCH == "box-state/"
    assert ag.BOX_STATE_AUTHORS == ("quant-merger[bot]",)
    assert {"docs/", "web/", "context/", ".github/"} <= set(ag.BOX_STATE_NEVER)
    assert set(ag.BOX_STATE_DATA_EXTS) <= {
        ".json", ".jsonl", ".ndjson", ".csv", ".tsv", ".log", ".txt", ".gz", ".parquet"
    }  # fmt: skip


def test_only_data_extensions_and_never_a_switch() -> None:
    """#1218 audit MF2: a code denylist missed MQL5 and more; data extensions are allowlisted."""
    for name in ("desks/mt5/data/x.mq5", "desks/mt5/data/x.mqh", "desks/mt5/data/x.ex5",
                 "desks/mt5/data/x.zip", "desks/mt5/data/x.pyd", "desks/mt5/data/x.xml",
                 "desks/mt5/data/GATEWAY_PAUSED", "desks/mt5/data/PF_ALLOCATOR_ARMED"):  # fmt: skip
        gh = FakeGH(_files(STATE, name))
        assert _run(gh) == 1, name
        assert not gh.merged(), name


def test_state_that_grants_authority_keeps_its_own_route() -> None:
    """#1218 audit MF1: a clearance row on LIVE is trusted by the adopt guard and the seal."""
    for name in ("desks/mt5/data/ADOPT_CLEARS.jsonl", "desks/mt5/data/SEAL_CLEARS.jsonl",
                 "desks/mt5/data/RELEASE.json", "desks/mt5/data/live_sleeve_policy.json",
                 "desks/mt5/data/sleeve_registry.json", "desks/mt5/data/x_armed.json",
                 "desks/mt5/data/ADOPT_POLICY.json", "desks/mt5/reports/ADOPT_ROLLBACKS.jsonl",
                 "desks/mt5/data/release_identity.json",
                 "desks/mt5/data/GATEWAY_LOADED.json"):  # fmt: skip
        gh = FakeGH(_files(STATE, name))
        assert _run(gh) == 1, name
        assert not gh.merged(), name


def test_every_commit_must_be_the_app_s_and_signed_by_github() -> None:
    """#1218 audit: the opener says nothing about who pushed to the branch since."""
    for bad in (
        _commit(login="kingdemond434-cpu"),
        _commit(verified=False),
        _commit(login=""),
        # #1218 audit MF3: the app's address declared as author, signed as the session's commit
        _commit(committer="kingdemond434-cpu"),
        _commit(reason="unknown_key"),
    ):
        gh = FakeGH(_files(STATE))
        gh.commits = [_commit(), bad]
        assert _run(gh) == 1
        assert not gh.merged()
    gh = FakeGH(_files(STATE))
    gh.commits = []
    assert _run(gh) == 1 and not gh.merged()
