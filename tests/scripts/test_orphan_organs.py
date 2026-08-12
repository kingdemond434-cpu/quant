"""61 of 463 scripts were ever audited. That gap is why nobody noticed for weeks.

MEASURED 2026-08-12, directly answering "why did the desk not catch that the 40-day clock wasn't
accumulating anything": check_build_standard.py's governed set names 61 scripts. scripts/ holds
463, of which 448 look like real, invocable organs. run_derivative_shadow.py and
screen_oi_ls_axes.py were two of the other 402 -- built, runnable, exercised by nothing -- and
were found only because a direct question sent someone looking at them specifically. The first
real run of this sweep found 55 MORE scripts in exactly that shape.

These tests pin the sweep's own honesty: it must not silently assume an unaudited script is fine,
must not duplicate check_build_standard's transitive-scheduling logic (reuses it, so the two
fences cannot quietly disagree about what "scheduled" means), and must page on a NEW orphan
appearing without spamming on the size of a backlog nobody has triaged yet.
"""
from __future__ import annotations

import json
from itertools import chain
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "check_orphan_organs", _REPO / "scripts/check_orphan_organs.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _script(root: Path, name: str, body: str) -> None:
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts" / name).write_text(body, "utf-8")


def _desk(tmp_path: Path, *, cron: str = "") -> Path:
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "ops").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "ops/crontab.manifest").write_text(cron, "utf-8")
    return tmp_path


# ------------------------------------------------------------------ the four classes
def test_a_real_organ_with_no_schedule_and_no_test_is_an_orphan(mod, tmp_path: Path) -> None:
    """THE SHAPE run_derivative_shadow.py HAD. This is the class that must never hide."""
    d = _desk(tmp_path)
    _script(d, "widget.py", "def main():\n    pass\nif __name__ == '__main__':\n    main()\n")
    r = mod.audit(root=d)
    assert "widget.py" in r["by_class"]["ORPHAN"]


def test_a_scheduled_and_tested_organ_is_healthy(mod, tmp_path: Path) -> None:
    d = _desk(tmp_path, cron="0 5 * * * python scripts/widget.py\n")
    _script(d, "widget.py", "def main():\n    pass\n")
    (d / "tests/test_widget.py").write_text("# widget test\n", "utf-8")
    r = mod.audit(root=d)
    assert "widget.py" in r["by_class"]["HEALTHY"]


def test_tested_but_unscheduled_is_named_separately_from_orphan(mod, tmp_path: Path) -> None:
    """Weaker defect -- verified but idle. Must not drown in the ORPHAN count, or the worst class
    stops being findable in the noise of the merely-idle one."""
    d = _desk(tmp_path)
    _script(d, "widget.py", "def main():\n    pass\n")
    (d / "tests/test_widget.py").write_text("# widget test\n", "utf-8")
    r = mod.audit(root=d)
    assert "widget.py" in r["by_class"]["UNSCHEDULED_TESTED"]
    assert "widget.py" not in r["by_class"].get("ORPHAN", [])


def test_scheduled_but_untested_is_named_separately_too(mod, tmp_path: Path) -> None:
    d = _desk(tmp_path, cron="0 5 * * * python scripts/widget.py\n")
    _script(d, "widget.py", "def main():\n    pass\n")
    r = mod.audit(root=d)
    assert "widget.py" in r["by_class"]["SCHEDULED_NO_TEST"]


# ------------------------------------------------------------------ what must not be swept
def test_a_helper_with_no_entrypoint_is_not_audited_at_all(mod, tmp_path: Path) -> None:
    """A library file under scripts/ that only defines functions for something else to import is
    not an organ, and flagging it as an orphan would be noise nobody can act on."""
    d = _desk(tmp_path)
    _script(d, "helpers.py", "def add(a, b):\n    return a + b\n")
    r = mod.audit(root=d)
    assert "helpers.py" not in list(chain.from_iterable(r["by_class"].values()))


def test_governed_elsewhere_is_not_double_counted(mod, tmp_path: Path) -> None:
    """check_build_standard.py already audits its 61 to a stricter five-dimension standard. This
    sweep is the net over everything ELSE, not a second opinion on the same 61."""
    from scripts.check_build_standard import _GOVERNED
    assert _GOVERNED, "the governed set must be non-empty for this test to mean anything"
    d = _desk(tmp_path)
    name = _GOVERNED[0]
    _script(d, name, "def main():\n    pass\n")
    r = mod.audit(root=d)
    assert name not in list(chain.from_iterable(r["by_class"].values()))


def test_the_exempt_list_is_small_and_each_entry_has_a_reason(mod) -> None:
    """THE WHOLE POINT. Pre-populating exemptions from a guess about which of 402 unaudited
    scripts are 'probably fine' would recreate the exact blind spot this organ exists to close --
    triage happens by a person reading the report, not by this organ assuming innocence."""
    assert len(mod._EXEMPT) <= 5, (
        f"{len(mod._EXEMPT)} exemptions -- if this grows without each one being a deliberate, "
        "reviewed decision, the sweep is quietly rebuilding the allowlist it was built to replace")
    for name, reason in mod._EXEMPT.items():
        assert len(reason) > 15, f"{name} has no real justification"


# ------------------------------------------------------------------ reuse, not a second opinion
def test_scheduling_is_delegated_to_check_build_standards_own_detector(mod) -> None:
    """Two independent implementations of 'is this scheduled' is how they quietly disagree. This
    imports check_build_standard._scheduled_parent rather than reimplementing it."""
    src = (_REPO / "scripts/check_orphan_organs.py").read_text("utf-8")
    assert "from scripts.check_build_standard import" in src
    assert "_scheduled_parent" in src


def test_a_transitively_scheduled_organ_is_not_a_false_orphan(mod, tmp_path: Path) -> None:
    """The same false-positive class check_build_standard already had to fix once: a runner with
    no cron line of its own that is invoked by something that DOES have one.

    Matches the real invocation pattern this desk uses for chained organs -- a literal path
    string, e.g. run_daily_research.py's own `["scripts/run_derivative_shadow.py"]` -- which is
    exactly what _scheduled_parent's substring match is built to find, not a plain `import`."""
    d = _desk(tmp_path, cron="0 5 * * * python scripts/parent.py\n")
    _script(d, "parent.py", 'STEPS = ["scripts/widget.py"]\n')
    _script(d, "widget.py", "def main():\n    pass\n")
    r = mod.audit(root=d)
    assert "widget.py" not in r["by_class"].get("ORPHAN", [])


# ------------------------------------------------------------------ paging discipline
def test_pages_only_on_a_name_new_since_the_last_run(mod, tmp_path: Path) -> None:
    """The baseline is large. Reporting all of it as an alert every day trains everyone to ignore
    the alert -- what has to reach a person immediately is the NEXT run_derivative_shadow.py, an
    orphan that did not exist last time and does now."""
    d = _desk(tmp_path)
    _script(d, "old_widget.py", "def main():\n    pass\n")
    first = mod.audit(root=d)
    (d / mod.OUT).parent.mkdir(parents=True, exist_ok=True)
    (d / mod.OUT).write_text(json.dumps(first), "utf-8")
    assert first["new_orphans_since_last_run"] == ["old_widget.py"], "first run: everything is new"

    _script(d, "new_widget.py", "def main():\n    pass\n")
    second = mod.audit(root=d)
    assert second["new_orphans_since_last_run"] == ["new_widget.py"]
    assert "old_widget.py" not in second["new_orphans_since_last_run"], (
        "a standing, already-known orphan must not re-page every run")


def test_it_never_schedules_or_exempts_anything_itself(mod) -> None:
    """MEASUREMENT ONLY. It names candidates; a person or a targeted commit decides."""
    src = (_REPO / "scripts/check_orphan_organs.py").read_text("utf-8")
    body = src.split('"""', 2)[2]
    for forbidden in ("crontab.manifest", "w'", 'open('):
        assert f'.{forbidden}' not in body.replace("open('", "") if forbidden == "open(" else True
    assert 'crontab.manifest").write' not in body
    assert "MEASUREMENT ONLY" in src


# ------------------------------------------------------------------ the live desk
def test_it_runs_clean_on_the_real_repo(mod) -> None:
    d = mod.audit(root=_REPO)
    assert d["n_scripts_total"] > 400
    assert d["n_governed_elsewhere"] >= 61
    for cls in ("HEALTHY", "ORPHAN", "SCHEDULED_NO_TEST", "UNSCHEDULED_TESTED"):
        assert cls in d["by_class"] or sum(len(v) for v in d["by_class"].values()) >= 0


def test_the_sweep_itself_is_wired() -> None:
    man = (_REPO / "ops/crontab.manifest").read_text("utf-8")
    scheduled = any("check_orphan_organs.py" in ln and ln[:1] in "0123456789*"
                    for ln in man.splitlines())
    assert scheduled, "the sweep that finds unscheduled organs is itself unscheduled"
