"""The replay-shadow research-input leg (ops/release/replay_child.research_step).

It is the measurement #249 is held on: the macro_conditional and cot_positioning inputs built
through family_inputs.resolve, and the allocator's factor model, compared base against head. A
leg that resolves nothing or loads no macro factor would agree with any head, so these tests pin
that it is not vacuous and that it is deterministic. Each run is a subprocess: the leg points
module globals (orthogonal_sweep.BASE, macro_state.ARCHIVE, leg_factors defaults) at a sandbox,
which must never leak into this suite's process.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "ops" / "release"

_PROBE = r"""
import json, sys, types
from pathlib import Path
from typing import Any
from unittest import mock
tree = Path(sys.argv[1])
stub = types.ModuleType("MetaTrader5")
stub.__getattr__ = lambda n: mock.MagicMock()
sys.modules["MetaTrader5"] = stub
sys.path[:0] = [str(tree), str(tree / "desks" / "mt5"), str(tree / "ops" / "release")]
import pandas as pd
import replay_child as rc
import replay_shadow as rs
sc = next(s for s in rs.scenarios() if s.get("research"))
day = pd.Timestamp(sc["day"], tz="UTC")
out = rc.research_step(Path.cwd(), sc, day + pd.Timedelta(hours=23.9), day)
print(json.dumps(out, sort_keys=True, default=str))
"""


def _run(tmp: Path) -> dict[str, Any]:
    tmp.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(
        [sys.executable, "-c", _PROBE, str(ROOT)],
        cwd=tmp,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert p.returncode == 0, p.stderr[-2000:]
    out: dict[str, Any] = json.loads(p.stdout.strip().splitlines()[-1])
    return out


def test_the_grid_owes_the_research_leg_somewhere() -> None:
    spec = importlib.util.spec_from_file_location("_rs_probe", RELEASE / "replay_shadow.py")
    assert spec and spec.loader
    rs = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(RELEASE))
    try:
        spec.loader.exec_module(rs)
    finally:
        sys.path.remove(str(RELEASE))
    assert any(sc.get("research") for sc in rs.scenarios())
    assert "research" in rs.decisions({"research": {"x": 1}})


def test_the_leg_is_not_vacuous_and_is_deterministic(tmp_path: Path) -> None:
    a = _run(tmp_path / "a")
    for family in ("macro_conditional", "cot_positioning"):
        row = a[family]
        assert row["resolved"] == "ok", row
        assert len(row["input"]) > 0, family
        assert row["signals"], f"{family} fired nothing: agreement would be vacuous"
    alloc = a["allocator"]
    assert alloc["factors"]["status"] == "MEASURED"
    assert {"d_vix", "d_r10"} <= set(alloc["factors"]["names"])
    assert all(v is not None for v in alloc["loadings"].values())
    assert any({"d_vix", "d_r10"} & set(v["used"]) for v in alloc["loadings"].values())
    assert _run(tmp_path / "b") == a
