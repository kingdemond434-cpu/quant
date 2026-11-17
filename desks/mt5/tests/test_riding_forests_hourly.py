"""The two riding forests (Japan, global macro) run hourly on the residents `RIDES` names.

`libs.research.forests.RIDES` has said since the federation was written that Japan rides
MT5-Dept-Japan and global macro rides MT5-Dept-Macro, but no hourly leg ever invoked
`forest_runner` for either, so ALT_DATA_YIELD read both as UNMEASURED. Pinned here: each is a
costed hourly leg (a literal the layer registry and the wiring census can read), it sits in the
department of the resident RIDES names, it has the forest budget rather than the 720 s default,
it has a strategy layer, and the runner it invokes accepts the forest and names its artifact.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import forests as fz  # noqa: E402
from libs.research import layers  # noqa: E402
from research import hourly_cycle as hc  # noqa: E402

RIDING = {"forest_japan": ("japan", "japan", "MT5-Dept-Japan"),
          "forest_global_macro": ("global_macro", "macro", "MT5-Dept-Macro")}


def test_each_riding_forest_is_a_costed_hourly_leg() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    for leg, (fid, _dept, _task) in RIDING.items():
        pat = (rf'forests_out\["{leg}"\] = _costed\("{leg}", lambda: _producer\(\s*'
               rf'"{leg}", "research/forest_runner.py", "--forest", "{fid}",\s*"--once",'
               rf'\s*"--budget-s", "3000", "--mine-grounds"\)\)')
        assert re.search(pat, src), leg
        assert src.count(f'_costed("{leg}"') == 1


def test_each_rides_the_department_registry_names() -> None:
    for leg, (fid, dept, task) in RIDING.items():
        assert fz.RIDES[fid] == task
        assert hc.department_of(leg) == dept
        assert hc.LEG_BUDGET_SEC[leg] == 3_300           # never the 720 s default kill
        assert layers.LEG_LAYER[leg] == "information"


def test_the_runner_knows_both_forests_and_their_artifacts() -> None:
    for _leg, (fid, _d, _t) in RIDING.items():
        spec = fz.forest(fid)
        assert spec.id == fid
        assert spec.report_name == f"FOREST_{fid.upper()}.json"
