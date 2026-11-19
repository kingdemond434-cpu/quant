"""The trust-boundary checker (ops/box_git/trust_check.py): pinned tests. Real git commits in a
temporary repository; every class it can answer, and every way it fails closed."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.box_git import trust_check as T  # noqa: E402

POLICY = {
    "files": ["ops/signing/*", "ops/release/protected_paths.txt", "ops/release/ceilings.json",
              "tests/ops/test_trust_pinned*.py"],
    "grow_only": ["ops/release/protected_paths.txt"],
    "symbols": {"gate.py": ["decide", "TRUSTED"]},
}
GATE = '''import json
from helpers import rules

TRUSTED = ("OWNER",)


def _parse(x):
    return x.strip()


def decide(c):
    return _parse(c) in TRUSTED and rules.ok(c)


def plumbing(x):
    return json.dumps(x)
'''
HELPERS = '''def ok(c):
    return bool(c)


def other(c):
    return c
'''


class Repo:
    def __init__(self, path: Path) -> None:
        self.p = path
        path.mkdir()
        self.g("init", "-q", "-b", "main")
        self.g("config", "user.email", "t@x")
        self.g("config", "user.name", "t")

    def g(self, *a: str) -> str:
        return subprocess.run(["git", "-C", str(self.p), *a], check=True, capture_output=True,
                              text=True).stdout

    def put(self, files: dict[str, str | None]) -> str:
        for rel, text in files.items():
            f = self.p / rel
            if text is None:
                self.g("rm", "-q", rel)
                continue
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text)
            self.g("add", rel)
        self.g("commit", "-q", "-m", "c", "--allow-empty")
        return self.g("rev-parse", "HEAD").strip()


def _base(tmp: Path) -> tuple[Repo, str]:
    r = Repo(tmp / "r")
    base = r.put({"gate.py": GATE, "helpers/__init__.py": "", "helpers/rules.py": HELPERS,
                  "ops/signing/allowed_signers": "zuck key\n",
                  "ops/release/protected_paths.txt": "# protected\n.github/*\nops/release/*\n",
                  "ops/release/ceilings.json": '{"daily": 0.02}\n',
                  T.POLICY_PATH: json.dumps(POLICY), "docs/a.md": "a\n"})
    return r, base


def _cls(r: Repo, base: str, head: str) -> tuple[str, str]:
    return T.classify(r.g, base, head, [], policy=POLICY)


def test_ordinary_changes_leave_the_trust_set_alone(tmp_path: Path) -> None:
    r, base = _base(tmp_path)
    plumbing = GATE.replace("json.dumps(x)", "json.dumps(x, indent=1)")
    head = r.put({"docs/a.md": "b\n", "gate.py": plumbing,
                  "helpers/rules.py": HELPERS.replace("return c", "return c or None"),
                  "tests/ops/test_new_thing.py": "def test_x():\n    assert True\n"})
    assert _cls(r, base, head)[0] == "ORDINARY"
    # comments and formatting inside frozen code are not trust
    head2 = r.put({"gate.py": GATE.replace("def decide(c):", "def decide(c):  # the core")})
    assert _cls(r, head, head2)[0] == "ORDINARY"


def test_frozen_code_and_its_call_closure_are_trust(tmp_path: Path) -> None:
    r, base = _base(tmp_path)
    for new in (GATE.replace('("OWNER",)', '("OWNER", "COLLABORATOR")'),     # frozen constant
                GATE.replace("return x.strip()", "return x"),                 # callee of decide
                GATE + "\nTRUSTED = ('ANYONE',)\n",                           # rebinding
                GATE + "\nsetattr(json, 'x', 1)\n"):                         # hazard
        head = r.put({"gate.py": new})
        assert _cls(r, base, head)[0] == "TRUST", new[-60:]
        r.put({"gate.py": GATE})
    head = r.put({"helpers/rules.py": HELPERS.replace("return bool(c)", "return True")})
    assert _cls(r, base, head)[0] == "TRUST"  # across modules: rules.ok is in decide's closure


def test_frozen_files_are_trust_unless_they_only_grow(tmp_path: Path) -> None:
    r, base = _base(tmp_path)
    head = r.put({"ops/signing/allowed_signers": "zuck key\nnew key\n"})
    assert _cls(r, base, head)[0] == "TRUST"
    r.put({"ops/signing/allowed_signers": "zuck key\n"})
    base = r.g("rev-parse", "HEAD").strip()
    grown = r.put({"ops/release/protected_paths.txt":
                   "# protected\n.github/*\nops/box_git/*\nops/release/*\n# more\n"})
    assert _cls(r, base, grown) == ("TIGHTEN", _cls(r, base, grown)[1])
    shrunk = r.put({"ops/release/protected_paths.txt": "# protected\n.github/*\n"})
    assert _cls(r, grown, shrunk)[0] == "TRUST"
    neg = r.put({"ops/release/protected_paths.txt":
                 "# protected\n.github/*\nops/box_git/*\nops/release/*\n# more\n!ops/x\n"})
    assert _cls(r, shrunk, neg)[0] == "TRUST"
    head = r.put({"ops/release/ceilings.json": '{"daily": 0.03}\n'})
    assert _cls(r, neg, head)[0] == "TRUST"


def test_the_policy_may_only_grow_and_new_pinned_tests_tighten(tmp_path: Path) -> None:
    r, base = _base(tmp_path)
    more = {**POLICY, "files": [*POLICY["files"], "ops/more/*"]}
    head = r.put({T.POLICY_PATH: json.dumps(more)})
    assert _cls(r, base, head)[0] == "TIGHTEN"
    less = {**POLICY, "files": POLICY["files"][1:]}
    head2 = r.put({T.POLICY_PATH: json.dumps(less)})
    assert _cls(r, head, head2)[0] == "TRUST"
    loosen = {**POLICY, "grow_only": [*POLICY["grow_only"], "ops/release/ceilings.json"]}
    head3 = r.put({T.POLICY_PATH: json.dumps(loosen)})
    assert _cls(r, head2, head3)[0] == "TRUST"
    test = r.put({"tests/ops/test_trust_pinned_more.py": "def test_y():\n    assert True\n"})
    assert _cls(r, head3, test)[0] == "TIGHTEN"


def test_anything_unmeasured_is_trust_and_the_hash_is_stable(tmp_path: Path) -> None:
    r, base = _base(tmp_path)
    broken = r.put({"gate.py": GATE + "\ndef (:\n"})
    assert _cls(r, base, broken)[0] == "TRUST"
    gone = r.put({"gate.py": None})
    assert _cls(r, base, gone)[0] == "TRUST"
    assert T.t_hash(r.g, base, POLICY) == T.t_hash(r.g, base, POLICY)
    assert len(T.t_hash(r.g, base, POLICY)) == 64


def test_the_real_policy_measures_this_repository() -> None:
    def git(*a: str) -> str:
        return subprocess.run(["git", "-C", str(ROOT), *a], check=True, capture_output=True,
                              text=True).stdout
    pol = T.load_policy((ROOT / T.POLICY_PATH).read_text(encoding="utf-8"))
    m = T.measure(git, "HEAD", pol)
    assert any(k.startswith(".github/scripts/audit_gate.py::run") for k in m)
    assert any(k.startswith("ops/box_git/forge_api.py::Forge") for k in m)


def test_risk_limits_are_ordinary_but_a_prop_firm_limit_is_never_exceeded(tmp_path: Path) -> None:
    caps = {"ops/release/ceilings.json": [["max", "f.py", "DAILY_LOSS_FRAC", 0.05]]}
    pol = {**POLICY, "files": [f for f in POLICY["files"] if "ceilings" not in f],
           "hard_caps": caps}
    r = Repo(tmp_path / "r")
    doc = {"max": {"f.py": {"DAILY_LOSS_FRAC": 0.04}, "s.py": {"RISK": 0.03}}}
    base = r.put({"gate.py": GATE, "helpers/__init__.py": "", "helpers/rules.py": HELPERS,
                  "ops/release/ceilings.json": json.dumps(doc), T.POLICY_PATH: json.dumps(pol)})
    looser = r.put({"ops/release/ceilings.json": json.dumps(
        {"max": {"f.py": {"DAILY_LOSS_FRAC": 0.05}, "s.py": {"RISK": 0.06}}})})
    assert T.classify(r.g, base, looser, [], policy=pol)[0] == "ORDINARY"
    for bad in ({"max": {"f.py": {"DAILY_LOSS_FRAC": 0.051}}}, {"max": {"s.py": {"RISK": 0.01}}},
                {"max": {"f.py": {"DAILY_LOSS_FRAC": "0.01"}}}):
        head = r.put({"ops/release/ceilings.json": json.dumps(bad)})
        cls, why = T.classify(r.g, base, head, [], policy=pol)
        assert cls == "REFUSE" and "published limit" in why
    head = r.put({"ops/release/ceilings.json": "{not json"})
    assert T.classify(r.g, base, head, [], policy=pol)[0] == "REFUSE"
