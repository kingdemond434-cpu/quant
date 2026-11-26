"""Boot r17 knobs: the trust closure cuts at a proved knob, and every way to abuse one is TRUST.

Audit pre-read TRUST_SHRINK_AUDIT_PREREAD.md items 1-23: a forged knob with a __globals__ chain,
a decorator, a non-literal default, a second assignment, adding and changing a knob in one packet,
a value outside its range, a knob reached from an unnamed caller, a missing knob, a checker crash.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.box_git import trust_check as T  # noqa: E402

LOOP = "ops/box_git/box_loop.py"
CI = "ops/box_git/box_ci.py"


def _real(*a: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True,
                          check=True).stdout


def fake_git(overrides: dict[str, str]):
    """`base` is this checkout's HEAD; `head` is HEAD with `overrides` ({path: new text})."""
    def git(*a: str) -> str:
        if a[0] == "ls-tree":
            return _real("ls-tree", "-r", "--name-only", "HEAD")
        if a[0] == "show":
            ref, _, path = a[1].partition(":")
            if ref == "head" and path in overrides:
                return overrides[path]
            return _real("show", f"HEAD:{path}")
        if a[0] == "diff":
            return "\n".join(overrides)
        raise AssertionError(a)
    return git


def policy() -> dict[str, Any]:
    return T.load_policy(_real("show", "HEAD:ops/box_git/TRUST_SET.json"))


def src(path: str) -> str:
    return _real("show", f"HEAD:{path}")


def classify(over: dict[str, str], pol: dict[str, Any] | None = None) -> tuple[str, str]:
    return T.classify(fake_git(over), "base", "head", list(over), pol or policy())


def test_todays_code_measures_with_every_knob_proved() -> None:
    m = T.measure(fake_git({}), "base", policy())
    assert m[f"{LOOP}::pr_order"] == "KNOB" and m[f"{CI}::DISK_FLOOR_GB"] == "KNOB"
    assert m[f"{LOOP}::checked"] != "KNOB"   # decides whether CI counts as green: core


def test_a_knob_value_inside_its_range_is_ordinary() -> None:
    s = src(LOOP).replace("FAST_REPLAY_TIMEOUT_S = 3600", "FAST_REPLAY_TIMEOUT_S = 7200")
    assert classify({LOOP: s})[0] == "ORDINARY"
    s2 = src(LOOP).replace("ENV_RERUNS = 2", "ENV_RERUNS = 4")
    assert classify({LOOP: s2})[0] == "ORDINARY"


def test_a_pure_knob_function_may_change_freely() -> None:
    s = src(LOOP).replace('return (0 if _TRAIN.search(ref) else 1, int(p.get("number") or 0))',
                          'return (0 if _TRAIN.search(ref) else 1, -int(p.get("number") or 0))')
    assert s != src(LOOP)
    assert classify({LOOP: s})[0] == "ORDINARY"


@pytest.mark.parametrize("old,new", [
    ("FAST_REPLAY_TIMEOUT_S = 3600", "FAST_REPLAY_TIMEOUT_S = 10"),           # below range
    ("DISK_FLOOR_GB = 25.0", "DISK_FLOOR_GB = 5.0"),                           # one-sided floor
])
def test_a_knob_outside_its_range_is_trust(old: str, new: str) -> None:
    path = CI if "DISK" in old else LOOP
    s = src(path).replace(old, new)
    assert s != src(path)
    assert classify({path: s})[0] == "TRUST"


def test_more_workers_than_today_is_trust_and_fewer_is_ordinary() -> None:
    assert classify({CI: src(CI).replace("MAX_WORKERS = 8", "MAX_WORKERS = 12")})[0] == "TRUST"
    assert classify({CI: src(CI).replace("MAX_WORKERS = 8", "MAX_WORKERS = 6")})[0] == "ORDINARY"


KNOB_DEF = "def _cap_now(name: str) -> int:\n"


@pytest.mark.parametrize("evil", [
    # A1: attribute chain off a parameter
    KNOB_DEF + "    name.__class__.__init__.__globals__\n    return FAST_RISK_TIMEOUT_S\n",
    # A1: method outside the whitelist
    KNOB_DEF + "    name.format_map({})\n    return FAST_RISK_TIMEOUT_S\n",
    # A2: decorator
    "@staticmethod\n" + KNOB_DEF + "    return FAST_RISK_TIMEOUT_S\n",
    # A3: non-literal default
    "def _cap_now(name: str, o=open) -> int:\n    return FAST_RISK_TIMEOUT_S\n",
    # A5/A6: a name or call the knob may not reach
    KNOB_DEF + "    os.system('x')\n    return FAST_RISK_TIMEOUT_S\n",
    KNOB_DEF + "    post(None, 'x', 'success', 'y')\n    return FAST_RISK_TIMEOUT_S\n",
    KNOB_DEF + "    import os\n    return FAST_RISK_TIMEOUT_S\n",
    KNOB_DEF + "    global ENV_RERUNS\n    return FAST_RISK_TIMEOUT_S\n",
    KNOB_DEF + "    f = name.get\n    f()\n    return FAST_RISK_TIMEOUT_S\n",
    KNOB_DEF + "    return getattr(name, 'x')\n",
    # Audit r17 MF1: a frame reached from a generator, exec handed to sorted(key=)
    KNOB_DEF + "    return bool(sorted(['print(1)'],\n"
               "        key=(x for x in ()).gi_frame.f_builtins['exec']))\n",
    KNOB_DEF + "    return sorted([name], key=len)[0]\n",
    KNOB_DEF + "    return max([1], key=_env_red)\n",
    KNOB_DEF + "    return len(name.gi_code)\n",
])
def test_an_impure_knob_function_is_trust(evil: str) -> None:
    s = src(LOOP)
    i = s.index(KNOB_DEF)
    j = s.index("\n\n\n", i)
    s = s[:i] + evil.rstrip("\n") + s[j:]
    cls, why = classify({LOOP: s})
    assert cls == "TRUST", why


def test_the_green_decision_stays_core() -> None:
    """`checked` decides whether a PR's CI counts as green: it is the verdict path, never a knob."""
    assert "checked" not in policy()["knobs"][LOOP]["functions"]
    lines = src(LOOP).splitlines(keepends=True)
    fn = next(n for n in ast.parse(src(LOOP)).body
              if isinstance(n, ast.FunctionDef) and n.name == "checked")
    at = fn.body[0].lineno - 1
    s = "".join([*lines[:at], "    pass\n", *lines[at:]])
    ast.parse(s)
    assert classify({LOOP: s})[0] in ("TRUST", "CONTRACT")


def test_a_second_assignment_of_a_knob_constant_is_trust() -> None:
    s = src(LOOP).replace("ENV_RERUNS = 2\n", "ENV_RERUNS = 2\nENV_RERUNS = 3\n")
    assert classify({LOOP: s})[0] == "TRUST"
    s2 = src(LOOP).replace("ENV_RERUNS = 2\n", "ENV_RERUNS = int('2')\n")
    assert classify({LOOP: s2})[0] == "TRUST"


def test_a_knob_used_by_an_unnamed_caller_is_trust() -> None:
    s = src(LOOP).replace('def gate_tick(cfg: Config, live: str) -> str:\n',
                          'def gate_tick(cfg: Config, live: str) -> str:\n    pr_order({})\n', 1)
    assert s != src(LOOP)
    assert classify({LOOP: s})[0] == "TRUST"


def test_adding_and_changing_a_knob_in_one_packet_is_trust() -> None:
    """The installed policy decides: a head policy naming a new knob cannot cut it the same day."""
    head_pol = policy()
    head_pol["knobs"][LOOP]["constants"]["RISK_CONTEXT"] = [0, 1]
    pol_text = json.dumps(head_pol, indent=1) + "\n"
    loop = src(LOOP).replace('RISK_CONTEXT = "risk-invariants"', 'RISK_CONTEXT = "x"')
    cls, _ = classify({LOOP: loop, "ops/box_git/TRUST_SET.json": pol_text})
    assert cls == "TRUST"


def test_removing_a_knob_or_narrowing_a_range_tightens() -> None:
    head_pol = policy()
    del head_pol["knobs"][LOOP]["constants"]["ENV_RERUNS"]
    head_pol["knobs"][LOOP]["constants"]["ENV_RERUN_AFTER_S"] = [120, 86400]
    pol_text = json.dumps(head_pol, indent=1) + "\n"
    assert classify({"ops/box_git/TRUST_SET.json": pol_text})[0] == "TIGHTEN"
    head_pol["knobs"][LOOP]["constants"]["ENV_RERUN_AFTER_S"] = [1, 86400]   # widened
    pol_text = json.dumps(head_pol, indent=1) + "\n"
    assert classify({"ops/box_git/TRUST_SET.json": pol_text})[0] == "TRUST"


def test_a_missing_knob_fails_closed() -> None:
    s = src(LOOP).replace("UNDERCAP_REDS_MAX = 6\n", "")
    s = s.replace("> UNDERCAP_REDS_MAX}", "> 6}")
    assert classify({LOOP: s})[0] == "TRUST"


def test_a_checker_crash_is_never_ordinary(monkeypatch) -> None:
    def boom(*a: Any, **k: Any) -> None:
        raise RuntimeError("checker crashed")
    monkeypatch.setattr(T, "check_knob", boom)
    s = src(LOOP).replace("FAST_REPLAY_TIMEOUT_S = 3600", "FAST_REPLAY_TIMEOUT_S = 7200")
    assert classify({LOOP: s})[0] == "TRUST"


def test_core_code_still_needs_the_owner() -> None:
    s = src(LOOP).replace('"""The latest verdict line', '"""THE latest verdict line')
    s = s.replace("    last = None\n", "    last = None\n    head = head or ''\n", 1)
    assert s != src(LOOP)
    assert classify({LOOP: s})[0] in ("TRUST", "CONTRACT")


def test_the_mover_cli_prints_one_class_and_fails_closed(tmp_path: Path, capsys) -> None:
    assert T.main(["--classify"]) == 2
    with pytest.raises(T.Unmeasured):
        T.main(["--classify", str(tmp_path), "HEAD", "HEAD"])   # not a repo: an error, no class
    assert capsys.readouterr().out == ""
    assert T.main(["--classify", str(ROOT), "HEAD", "HEAD"]) == 0
    assert json.loads(capsys.readouterr().out)["class"] == "ORDINARY"
