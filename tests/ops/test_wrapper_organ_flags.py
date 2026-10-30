"""Every organ a wrapper or installer launches must accept the flags that wrapper passes it.

MEASURED 2026-10-29 (MT5-FrontierAudit rc 1). `ops/run_frontier_audit.cmd` passed `--apply` to
world_model.py, meta_rnd.py and quantbench.py. None of the three has ever declared `--apply`, so
argparse exited 2 with "unrecognized arguments" on every daily pass, and the quantbench and
meta_rnd lanes were dark from 10-20 / 10-22 behind a lane log that only counted failures. No
test ran the wrapper and no test read it: a .cmd line is a call site that no linter sees.

THE FENCE. Every tracked .cmd / .ps1 / .bat wrapper and installer is read; each Python
invocation in it (`<path>.py ...` or `-m <module> ...`, quoted or inside a scheduled-task
`-Argument` string, `^` / backtick continuations joined) is resolved to the tracked script, and
every `--long` flag passed is checked against that script's own argparse, read STATICALLY from
its AST (every `add_argument` option string, argparse's unique-prefix rule honoured). Nothing is
imported or executed, so the whole tree is checked in seconds and no organ's import side effects
run in CI.

WHAT IS NOT JUDGED. A script that reads `parse_known_args` or REMAINDER accepts anything; a
script with no argparse is held to the weaker rule that the flag appears literally in its source
(the `"--terms-only" in argv` style). Variables (`$x`, `%X%`, `{0}`) and single-dash PowerShell
parameters are never flags. `_retired/` trees run nowhere and are skipped.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.wrapper_invocations import _tokens_after, accepted, flag_ok, mismatches  # noqa: E402


def test_the_extractor_reads_the_measured_shapes() -> None:
    line = 'call :run "desks\\mt5\\research\\quantbench.py" --apply --budget-s 9'
    assert _tokens_after(line, line.index(".py") + 3) == ["--apply", "--budget-s", "9"]
    ps = ("-Argument ('/d /s /c \"cd /d {0} && py -3 -m mt5desk.tape --terms-only >> {1} "
          "2>&1\"' -f $Root, $Log)")
    end = ps.index("mt5desk.tape") + len("mt5desk.tape")
    assert _tokens_after(ps, end) == ["--terms-only"]
    cmd = '"%PY%" -u "C:\\opt\\quant\\ops\\never_stale.py" --apply >>"%LOG%" 2>&1'
    assert _tokens_after(cmd, cmd.index(".py") + 3) == ["--apply"]


def test_the_rule_rejects_the_measured_mismatch() -> None:
    kind, opts = accepted("desks/mt5/research/quantbench.py")
    assert kind == "argparse"
    assert not flag_ok("--apply", kind, opts)
    assert flag_ok("--once", kind, opts) and flag_ok("--budget", kind, opts)


def test_every_wrapper_passes_only_flags_its_organ_accepts() -> None:
    bad = mismatches()
    assert not bad, "wrapper flag the organ's argparse rejects:\n  " + "\n  ".join(bad)


def test_the_shared_helper_is_a_library_not_an_unclocked_executable() -> None:
    """Audit HOLD, 2026-10-29: as scripts/wrapper_invocations.py the helper was read by
    check_birth_obligations as a new executable (it mentions `__main__`) owing a clock and a
    runtime_state row it can never have. It is a library; it must sit outside every EXEC_AREA."""
    from scripts.check_birth_obligations import EXEC_AREAS

    from libs.ops import wrapper_invocations

    rel = Path(wrapper_invocations.__file__).resolve().relative_to(ROOT).as_posix()
    assert rel == "libs/ops/wrapper_invocations.py"
    assert not any(rel.startswith(f"{area}/") for area in EXEC_AREAS), rel
    assert not (ROOT / "scripts" / "wrapper_invocations.py").exists()
