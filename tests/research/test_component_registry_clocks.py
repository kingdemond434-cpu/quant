"""A DECLARED CLOCK MUST BE THE FILE THAT RUNS THE ORGAN, checked against its schedule source.

The component registry's reach walk credits a script to whichever file that names it pops first.
For the breadth ledger that was a docstring citation in a library that cannot run a script, so
its runtime row named the wrong clock. The registry now declares it explicitly; these tests pin
the declaration to the two sources that make it true, so it cannot rot silently.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "desks" / "mt5")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_SPEC = importlib.util.spec_from_file_location(
    "components_under_test", ROOT / "desks" / "mt5" / "ops" / "components.py")
assert _SPEC and _SPEC.loader
comp = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("components_under_test", comp)
_SPEC.loader.exec_module(comp)

BREADTH = "scripts/report_breadth.py"


def _spec(component_id: str):  # type: ignore[no-untyped-def]
    return next(s for s in comp.explicit_specs() if s.component_id == component_id)


def test_the_breadth_ledger_is_clocked_by_the_vps_daily_cycle_that_runs_it() -> None:
    spec = _spec(f"executable:{BREADTH}")
    assert spec.schedule == f"invoked:{comp.VPS_DAILY}"
    assert spec.host == "vps" and spec.cadence_s == 86_400
    # (1) the declared invoker really runs it: a step of its own table, run by subprocess
    assert comp.vps_daily_step(BREADTH) == "breadth_ledger"
    assert "subprocess.run" in (ROOT / comp.VPS_DAILY).read_text(encoding="utf-8")
    # (2) the declared invoker is itself on a clock: the VPS crontab and its systemd timer
    manifest = (ROOT / "ops" / "crontab.manifest").read_text(encoding="utf-8")
    cron = [ln for ln in manifest.splitlines()
            if re.match(r"^[0-9*]", ln) and comp.VPS_DAILY in ln]
    timer = [ln for ln in manifest.splitlines()
             if ln.startswith("SYSTEMD ") and f'exec="{comp.VPS_DAILY}"' in ln]
    assert cron and timer, "the VPS daily cycle lost its clock; this declaration is now false"


def test_the_old_credited_namers_cannot_run_a_script() -> None:
    """Why the walk's first reacher was wrong: both files only cite it in prose."""
    for rel in ("desks/mt5/research/docket_keff.py", "desks/mt5/research/alpha_breadth.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert not re.search(r"\b(?:subprocess|Popen|runpy|os\.system)\b", text), rel


def test_the_registry_carries_the_declared_clock_not_the_walks_guess() -> None:
    reg = comp.build_registry()
    rows = [s for s in reg.all() if BREADTH in s.code_paths and s.kind == "executable"]
    assert [s.schedule for s in rows] == [f"invoked:{comp.VPS_DAILY}"]
    assert rows[0].outputs == ("web/breadth_ledger.json",)
