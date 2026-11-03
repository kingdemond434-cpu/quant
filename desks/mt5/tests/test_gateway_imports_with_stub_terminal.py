"""The gateway module IMPORTS -- checked on every CI run, with the terminal stubbed.

MEASURED 2026-10-01 13:58Z -> 10-02 13:51Z: #90 (451a764d2) removed `MIN_RATCHET_IMPROVEMENT_R`
from decision_core while #135 (a179ab3ba) still re-exported it from the gateway, so
`mt5desk.gateway` raised ImportError at import for a day. Nothing caught it: every gateway test
either reads the source (the module imports MetaTrader5, which installs only on Windows) or
`importorskip`s the package, and the adoption gate failed open on LEGACY_TIP.

A stub `MetaTrader5` whose every attribute is a MagicMock lets the real module execute top to
bottom on the CI runner, so a dangling name, a missing re-export or a syntax error in the file
that places orders fails here instead of on the box. It runs in a subprocess so the stub never
leaks into another test's `sys.modules`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent

_PROBE = """
import sys, types
from unittest import mock
stub = types.ModuleType("MetaTrader5")
stub.__getattr__ = lambda name: mock.MagicMock(name="MetaTrader5." + name)
sys.modules["MetaTrader5"] = stub
sys.path[:0] = [sys.argv[1], sys.argv[2]]
import mt5desk.gateway as gateway
for name in ("main", "order_comment", "allocator_book", "place_bracket", "record_trades"):
    assert callable(getattr(gateway, name, None)), name
print("GATEWAY_IMPORTED")
"""


def test_the_gateway_module_imports_against_a_stub_terminal() -> None:
    proc = subprocess.run([sys.executable, "-c", _PROBE, str(_ROOT), str(_DESK)],
                          capture_output=True, text=True, timeout=300, cwd=str(_ROOT))
    assert proc.returncode == 0 and "GATEWAY_IMPORTED" in proc.stdout, (
        f"mt5desk.gateway failed to import:\n{proc.stderr[-4000:]}")


def test_the_probe_would_have_caught_a_dangling_re_export(tmp_path: Path) -> None:
    """The same probe over a copy of the desk with one re-export pointing at nothing fails."""
    import shutil
    desk = tmp_path / "desk"
    shutil.copytree(_DESK / "mt5desk", desk / "mt5desk",
                    ignore=shutil.ignore_patterns("__pycache__"))
    gw = desk / "mt5desk" / "gateway.py"
    src = gw.read_text("utf-8")
    gw.write_text(src.replace("from mt5desk.decision_core import (\n",
                              "from mt5desk.decision_core import (\n    NO_SUCH_NAME_IN_CORE,\n",
                              1), "utf-8")
    proc = subprocess.run([sys.executable, "-c", _PROBE, str(_ROOT), str(desk)],
                          capture_output=True, text=True, timeout=300, cwd=str(_ROOT))
    assert proc.returncode != 0 and "NO_SUCH_NAME_IN_CORE" in proc.stderr
