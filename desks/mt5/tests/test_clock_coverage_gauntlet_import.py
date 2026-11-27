"""The sealed gauntlet's certification write reaches `certify_with_clocks` under the gauntlet's OWN
sys.path (repo root + desks/mt5, no research dir pre-inserted), never the plain-write fallback.

Audit HOLD of the clock-coverage SEAL r1: a bare `from clock_coverage import ...` raises
ModuleNotFoundError on that path, the `except Exception` swallows it into the plain write, and
every clock then waits for the hourly backfill."""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
GAUNTLET = DESK / "scripts" / "external_gauntlet.py"
START = "    _surv_text = json.dumps(doc, indent=2, default=str)\n"
END = '              f"the hourly clock_coverage backfill opens them")\n'


def _write_block() -> str | None:
    src = GAUNTLET.read_text("utf-8")
    if "certify_with_clocks" not in src:
        return None                                   # seal not landed: nothing to run
    i = src.index(START)
    return textwrap.dedent(src[i:src.index(END, i) + len(END)])


def test_the_sealed_write_opens_clocks_under_the_gauntlets_own_path(tmp_path):
    block = _write_block()
    if block is None:
        return
    probe = tmp_path / "probe.py"
    probe.write_text(textwrap.dedent(f"""
        import json, sys
        sys.path[:] = [p for p in sys.path if not p.rstrip("/\\\\").endswith("research")]
        sys.path.insert(0, {str(ROOT)!r}); sys.path.insert(0, {str(DESK)!r})
        assert not any(p.rstrip("/\\\\").endswith("research") for p in sys.path)
        from pathlib import Path
        import research.clock_coverage as cc
        calls = []
        def _record(path, doc, fresh=(), text=None):
            calls.append(str(path)); Path(path).write_text(text, encoding="utf-8")
            return {{"clocks_opened": ["k"], "fresh": len(fresh), "excluded": 0}}
        cc.certify_with_clocks = _record
        surv_path = Path({str(tmp_path / "U.json")!r}); doc = {{"survivors": {{}}}}
        _remint_fresh = set()
    """) + block + textwrap.dedent("""
        assert calls, "fell back to the plain write"
        print("CLOCKS_OPENED", len(calls))
    """), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    out = subprocess.run([sys.executable, "-I", str(probe)], capture_output=True, text=True,
                         env=env, cwd=str(tmp_path), timeout=120)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "CLOCKS_OPENED 1" in out.stdout and "NOT opened" not in out.stdout, out.stdout


def test_the_import_is_research_qualified_once_landed():
    src = GAUNTLET.read_text("utf-8")
    if "certify_with_clocks" in src:
        assert "from research.clock_coverage import certify_with_clocks" in src
        assert "\n        from clock_coverage import certify_with_clocks" not in src
