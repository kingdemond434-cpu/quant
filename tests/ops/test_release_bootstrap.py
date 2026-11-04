"""The one-time Level 2 bootstrap (ops/release/authority/LEVEL2.md): the release machinery leaves
ROOT only when GitHub itself enforces the authority, master and production move only by CI's
promote, the seal key never reaches an unreviewed branch, and the Apps are created with exactly
the permissions the installers accept."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
AUTH = ROOT / "ops/release/authority"
LIVE = "claude/llm-auto-upgrade-verify-gcjac3"


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


pol = _load("boot_policy", AUTH / "policy.py")
cr = _load("boot_check_ruleset", AUTH / "check_ruleset.py")
man = _load("boot_app_manifest", AUTH / "app_manifest.py")
bg = _load("boot_bootstrap_github", AUTH / "bootstrap_github.py")
POLICY = pol.load_policy()


def _cls(files: list[str], enforced: bool, tier: str = "PROTECTED") -> tuple[str, list[str]]:
    return pol.classify(files, tier, POLICY, lambda n: None, lambda n: None, enforced=enforced)


# ---- the release machinery: ROOT until GitHub enforces, then CONTROLLER ------------------------


@pytest.mark.parametrize("path", ["ops/box/workflow_gate.ps1", "ops/release/merger/merger_env.ps1"])
def test_machinery_is_root_until_github_enforces_the_authority(path: str) -> None:
    assert _cls([path], enforced=False)[0] == "ROOT"
    cls, why = _cls([path], enforced=True)
    assert cls == "CONTROLLER" and "veto" in why[0]
    # the gate's own tier cannot drag it below CONTROLLER
    assert _cls([path], enforced=True, tier="AUTO")[0] == "CONTROLLER"


@pytest.mark.parametrize("path", [
    "ops/release/authority/authority.py",
    "ops/release/authority/ROOT_POLICY.json",
    "ops/release/publisher/publish.py",
    ".github/scripts/audit_gate.py",
    ".github/workflows/trusted-eval.yml",
])  # fmt: skip
def test_the_authority_itself_stays_root_whatever_github_enforces(path: str) -> None:
    assert _cls([path], enforced=True)[0] == "ROOT"
    assert _cls([path, "ops/box/workflow_gate.ps1"], enforced=True)[0] == "ROOT"


def test_a_controller_merge_of_the_machinery_does_not_move_the_root_pin() -> None:
    names = ["ops/box/workflow_gate.ps1", "ops/release/authority/authority.py"]
    a = pol.root_digest(lambda n: b"one", names, POLICY)
    b = pol.root_digest(lambda n: b"one" if "authority" in n else b"two", names, POLICY)
    c = pol.root_digest(lambda n: b"two" if "authority" in n else b"one", names, POLICY)
    assert a == b and a != c


APPS_ONLY = {"enforcement": "active",
             "bypass_actors": [{"actor_type": "Integration", "actor_id": 4242,
                                "bypass_mode": "always"}]}  # fmt: skip


class _Ag:
    def __init__(self, rules: Any, ruleset: Any = None) -> None:
        self.rules, self.ruleset = rules, APPS_ONLY if ruleset is None else ruleset

    def _gh(self, path: str) -> Any:
        got = self.ruleset if path == "repos/o/r/rulesets/9" else self.rules
        assert path == "repos/o/r/rulesets/9" or path.startswith(f"repos/o/r/rules/branches/{LIVE}")
        if isinstance(got, Exception):
            raise got
        return got


def _rule(ctx: str = "release-authority", app: int = 5601819) -> dict[str, Any]:
    return {"type": "required_status_checks", "ruleset_id": 9,
            "parameters": {"required_status_checks": [{"context": ctx, "integration_id": app}]}}


@pytest.fixture(scope="module")
def auth() -> Any:
    pytest.importorskip("cryptography")
    return _load("boot_authority", AUTH / "authority.py")


@pytest.mark.parametrize("rules,want", [
    ([_rule()], True),
    ([{"type": "deletion"}, _rule()], True),
    ([{"type": "deletion"}, {"type": "non_fast_forward"}], False),  # LIVE today
    ([_rule(app=15368)], False),  # GitHub Actions could satisfy it
    ([_rule(ctx="quality")], False),
    ({"message": "Not Found"}, False),
    (RuntimeError("gh api: 502"), False),
])  # fmt: skip
def test_enforcement_is_read_from_github_and_fails_closed(
    auth: Any, rules: Any, want: bool
) -> None:
    assert auth.level2_enforced(_Ag(rules), "o/r", LIVE)[0] is want


def _actors(*bys: dict[str, Any]) -> dict[str, Any]:
    return {"enforcement": "active", "bypass_actors": list(bys)}


APP = {"actor_type": "Integration", "actor_id": 4242, "bypass_mode": "always"}


@pytest.mark.parametrize("ruleset", [
    # #650 audit MF1: the admin's pull_request bypass lets the owner's login merge around the
    # status, so a gate rewritten on the CONTROLLER path could use it
    _actors(APP, {"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "pull_request"}),
    _actors(APP, {"actor_type": "OrganizationAdmin", "actor_id": 1, "bypass_mode": "always"}),
    _actors(APP, {"actor_type": "Team", "actor_id": 3, "bypass_mode": "always"}),
    _actors(APP, {"actor_type": "User", "actor_id": 3, "bypass_mode": "always"}),
    _actors(APP, {"actor_type": "Integration", "actor_id": 15368, "bypass_mode": "always"}),
    _actors(APP, {"actor_type": "Integration", "actor_id": 5601819, "bypass_mode": "always"}),
    {"enforcement": "active"},  # bypass list not visible: never read as empty
    {**APPS_ONLY, "enforcement": "evaluate"},
    RuntimeError("gh api: 403"),
])  # fmt: skip
def test_a_rule_a_person_can_bypass_is_not_enforcement(auth: Any, ruleset: Any) -> None:
    ok, why = auth.level2_enforced(_Ag([_rule()], ruleset), "o/r", LIVE)
    assert ok is False and why


# ---- master and production move only by promotion ----------------------------------------------


def _filled(name: str, app: int = 4242) -> dict[str, Any]:
    return bg.fill(json.loads((AUTH / name).read_text(encoding="utf-8")), app)


def test_both_rulesets_are_safe_once_the_state_app_is_named() -> None:
    assert cr.problems(_filled("ruleset_live.json")) == []
    assert cr.master_problems(_filled("ruleset_master.json"), 4242) == []


@pytest.mark.parametrize("mutate", [
    lambda r: r["conditions"]["ref_name"].update(include=["refs/heads/master"]),
    lambda r: r.update(rules=[x for x in r["rules"] if x["type"] != "update"]),
    lambda r: r["rules"][2]["parameters"].update(update_allows_fetch_and_merge=True),
    lambda r: r["bypass_actors"].append({"actor_type": "RepositoryRole", "actor_id": 5,
                                         "bypass_mode": "always"}),
    lambda r: r["bypass_actors"][0].update(actor_id=15368),
    lambda r: r.update(enforcement="disabled"),
])  # fmt: skip
def test_master_ruleset_refuses_any_other_writer(mutate: Any) -> None:
    rs = _filled("ruleset_master.json")
    mutate(rs)
    assert cr.master_problems(rs, 4242)


def test_the_live_template_lets_no_person_bypass() -> None:
    rs = _filled("ruleset_live.json")
    assert [b["actor_type"] for b in rs["bypass_actors"]] == ["Integration"]
    with_admin = {**rs, "bypass_actors": [*rs["bypass_actors"], {
        "actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "pull_request"}]}
    assert cr.problems(with_admin)


def test_fill_needs_exactly_one_placeholder() -> None:
    rs = _filled("ruleset_live.json")
    with pytest.raises(ValueError):
        bg.fill(rs, 1)


def test_ci_keeps_the_seal_key_on_live_and_promotes_as_the_state_app() -> None:
    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    seal, promote = ci["jobs"]["seal"], ci["jobs"]["promote"]
    assert f"refs/heads/{LIVE}" in seal["environment"]
    assert "desk-sync-clean" not in seal["environment"]
    assert f"refs/heads/{LIVE}" in seal["steps"][0]["if"]
    assert promote["environment"] == "live-seal"
    assert promote["if"].strip().endswith(f"github.ref == 'refs/heads/{LIVE}'")
    for job in (seal, promote):
        co = next(s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout"))
        assert co["with"]["token"] == "${{ steps.app.outputs.token || github.token }}"
    assert frozenset({LIVE}) == cr.SEAL_BRANCHES


# ---- the Apps are created with exactly the installers' permissions -----------------------------


def test_manifests_carry_no_forbidden_permission() -> None:
    m = man.manifest("merger", "http://127.0.0.1:1/done")
    assert m["default_permissions"] == {"contents": "write", "pull_requests": "write",
                                        "workflows": "write", "metadata": "read"}
    assert m["hook_attributes"]["active"] is False and m["public"] is False
    p = man.manifest("publisher", "http://127.0.0.1:1/done")
    assert p["default_permissions"] == {"contents": "write", "metadata": "read"}
    for k in man.KINDS:
        assert not man.FORBIDDEN & set(man.manifest(k, "x")["default_permissions"])


def test_a_widened_app_is_refused() -> None:
    want = man.KINDS["merger"]["permissions"]
    assert man.check_permissions("merger", dict(want)) == []
    assert man.check_permissions("merger", {**want, "administration": "write"})
    assert man.check_permissions("publisher", {"contents": "write", "metadata": "read",
                                               "workflows": "write"})
    assert man.check_permissions("publisher", {"metadata": "read"})


def test_conversion_checks_the_code_and_the_answer() -> None:
    with pytest.raises(ValueError):
        man.convert("../../evil")

    class R:
        def __init__(self, body: dict[str, Any]) -> None:
            self.body = json.dumps(body).encode()

        def read(self) -> bytes:
            return self.body

        def __enter__(self) -> R:
            return self

        def __exit__(self, *a: Any) -> None:
            return None

    seen: list[Any] = []

    def opener(req: Any, timeout: float) -> R:
        seen.append(req)
        return R({"id": 7, "slug": "quant-merger", "pem": "KEY", "permissions": {}})

    assert man.convert("abc123", opener)["id"] == 7
    assert seen[0].full_url.endswith("/app-manifests/abc123/conversions")
    assert seen[0].get_method() == "POST" and "Authorization" not in seen[0].headers
    with pytest.raises(ValueError):
        man.convert("abc", lambda req, timeout: R({"id": 7, "slug": "s"}))


def test_the_form_escapes_the_manifest_and_carries_the_state() -> None:
    page = man.form_page(man.manifest("merger", "http://127.0.0.1:1/done"), "st&ate")
    assert "state=st%26ate" in page and '"' not in page.split("value=")[1].split(">")[0][1:-1]


def test_a_refused_app_leaves_no_key(tmp_path: Path, monkeypatch: Any) -> None:
    """#650 audit SF1: the permission check runs before anything is written."""

    class Flow:
        def __init__(self, kind: str, port: int, suffix: str) -> None:
            self.man = {"name": "quant-merger"}
            self.result = {"id": 7, "slug": "quant-merger", "pem": "KEY",
                           "permissions": {"contents": "write", "administration": "write"}}
            self.error = None
            self.done = type("E", (), {"wait": lambda self, t: True})()

    monkeypatch.setattr(man, "_Flow", Flow)
    monkeypatch.setattr(man, "_handler", lambda flow: man.BaseHTTPRequestHandler)
    pem, out = tmp_path / "app.pem", tmp_path / "merger.json"
    rc = man.main(["--kind", "merger", "--pem", str(pem), "--out", str(out), "--no-browser",
                   "--timeout", "1"])  # fmt: skip
    assert rc == 2 and not pem.exists() and not out.exists()


def test_the_key_file_is_written_whole(tmp_path: Path) -> None:
    p = tmp_path / "k" / "app.pem"
    man.write_pem(p, "PEM")
    assert p.read_text() == "PEM" and not list(p.parent.glob("*.tmp"))


# ---- #650's own merge: the gate's bar, at the exact head ---------------------------------------


class _Gate:
    GATING_JOBS = ("quality",)
    AUTO_JOBS = ("risk-invariants",)

    def __init__(self, state: str, verdicts: list[dict[str, str]], head: str = "a" * 40) -> None:
        self.state, self.v, self.head = state, verdicts, head

    def _gh(self, path: str, *a: str) -> Any:
        if path.endswith("/pulls/650"):
            return {"state": "open", "merged": False, "head": {"sha": self.head,
                    "repo": {"full_name": "o/r"}}, "base": {"ref": LIVE}}  # fmt: skip
        return {"check_runs": []} if "check-runs" in path else []

    def _flat(self, x: Any) -> Any:
        return x

    def checks(self, runs: Any, jobs: Any, genuine: Any) -> tuple[str, str]:
        assert jobs == ("quality", "risk-invariants")
        return self.state, "w"

    def provenance(self, *a: Any) -> Any:
        return lambda r: True

    def verdicts(self, comments: Any) -> list[dict[str, str]]:
        return self.v


@pytest.mark.parametrize("state,verdicts,ok", [
    ("pass", [{"verdict": "CLEAR", "sha": "a" * 9}], True),
    ("pending", [{"verdict": "CLEAR", "sha": "a" * 9}], False),
    ("pass", [], False),
    ("pass", [{"verdict": "CLEAR", "sha": "b" * 9}], False),  # a CLEAR of another head
    ("pass", [{"verdict": "CLEAR", "sha": "a" * 9}, {"verdict": "HOLD", "sha": "a" * 9}], False),
])  # fmt: skip
def test_root_pr_merges_only_at_a_cleared_green_head(state: str, verdicts: Any, ok: bool) -> None:
    head, bad = bg.ready(_Gate(state, verdicts), "o/r", 650)
    assert (head == "a" * 40) is ok and (bad == []) is ok


class _Hub:
    """A fake gh() for root_merge: one LIVE ruleset whose bypass list we can watch."""

    def __init__(self, merge_fails: bool = False, extra: Any = None) -> None:
        self.bys: list[Any] = [dict(APP), *(extra or [])]
        self.during: list[Any] = []
        self.merge_fails = merge_fails

    def __call__(self, path: str, *a: str, data: Any = None) -> Any:
        if path.startswith("repos/o/r/rulesets?"):
            return [{"id": 9, "name": "live-requires-release-authority"}, {"id": 8, "name": "x"}]
        if path == "repos/o/r/rulesets/9" and not a:
            return {"name": "live-requires-release-authority", "target": "branch",
                    "enforcement": "active", "conditions": {}, "rules": [],
                    "bypass_actors": [dict(b) for b in self.bys]}  # fmt: skip
        if path == "repos/o/r/rulesets/9":
            self.bys = data["bypass_actors"]
            return {}
        if path.endswith("/merge"):
            self.during = list(self.bys)
            assert data == {"sha": "a" * 40, "merge_method": "merge"}
            if self.merge_fails:
                raise RuntimeError("405 not mergeable")
            return {"merged": True, "sha": "m" * 40}
        raise AssertionError(path)


def test_root_merge_opens_the_admin_bypass_for_one_merge_only() -> None:
    hub = _Hub()
    assert bg.root_merge(hub, "o/r", 650, "a" * 40) == "m" * 40  # the commit to pin
    assert bg.ADMIN_PR_BYPASS in hub.during
    assert hub.bys == [APP]


def test_a_failed_restore_says_the_bypass_may_still_be_on() -> None:
    hub = _Hub()
    real = hub.__call__

    def call(path: str, *a: str, data: Any = None) -> Any:
        if path == "repos/o/r/rulesets/9" and a and data["bypass_actors"] == [APP]:
            raise RuntimeError("502")
        return real(path, *a, data=data)

    with pytest.raises(RuntimeError, match="ADMIN BYPASS MAY STILL BE ON"):
        bg.root_merge(call, "o/r", 650, "a" * 40)


def test_a_reordered_read_back_is_not_a_false_alarm() -> None:
    other = {"actor_type": "Integration", "actor_id": 7, "bypass_mode": "always"}
    hub = _Hub(extra=[other])
    real = hub.__call__

    def call(path: str, *a: str, data: Any = None) -> Any:
        got = real(path, *a, data=data)
        if path == "repos/o/r/rulesets/9" and not a:
            got["bypass_actors"].reverse()
        return got

    assert bg.root_merge(call, "o/r", 650, "a" * 40) == "m" * 40


def test_root_merge_closes_the_bypass_when_the_merge_fails() -> None:
    hub = _Hub(merge_fails=True)
    with pytest.raises(RuntimeError, match="not mergeable"):
        bg.root_merge(hub, "o/r", 650, "a" * 40)
    assert hub.bys == [APP]


def test_root_merge_refuses_a_ruleset_a_person_already_bypasses() -> None:
    hub = _Hub(extra=[{"actor_type": "User", "actor_id": 1, "bypass_mode": "always"}])
    with pytest.raises(RuntimeError, match="already lets a person"):
        bg.root_merge(hub, "o/r", 650, "a" * 40)
    assert hub.during == []
