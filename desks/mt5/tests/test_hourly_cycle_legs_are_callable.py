"""Every leg of the hourly cycle must at least be CALLABLE, checked without running the cycle.

WHAT THIS COST. Measured on the box 2026-09-07, mid-cycle:

    TypeError: _producer() takes from 2 to 3 positional arguments but 4 were given

raised from `_producer("pf_allocator", "research/pf_allocator.py", "--mode", "normal")`. The old
signature took the extra arguments as ONE tuple, and two legs were written the natural way
instead. `_costed` wraps a leg's execution, but this TypeError is raised while BUILDING the call,
before any of that -- so it escaped `main` and killed the pass at leg `pf_allocator`.

Everything after that leg never ran: `publish_state`, `issue_board`, and the four research report
producers among them. The board then froze and reported those very reports as STALLED, which is a
defect describing its own symptom -- and the desk spent an afternoon reading the symptom.

A LEG THAT CANNOT BE CALLED IS NOT A SLOW LEG, IT IS A STOPPED CYCLE. Nothing checked arity
because checking it seemed to require running a fifty-five-leg pass with a live terminal. It does
not: the call sites are in the source, and `inspect.Signature.bind` answers the question exactly.
"""
from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parent.parent
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = DESK / "research" / "hourly_cycle.py"
TREE = ast.parse(SOURCE.read_text("utf-8"))


def _producer_calls() -> list[ast.Call]:
    return [n for n in ast.walk(TREE)
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_producer"]


def test_the_file_has_producer_legs_to_check() -> None:
    """Guard against the suite passing because the walk found nothing."""
    assert len(_producer_calls()) > 20


@pytest.mark.parametrize("call", _producer_calls(),
                         ids=lambda c: f"line{c.lineno}")
def test_every_producer_call_binds_to_the_signature(call: ast.Call) -> None:
    """`Signature.bind` is exactly the check the interpreter makes at call time.

    No subprocess, no terminal, no cycle: the arity defect is a property of the source, so it is
    caught in CI on Linux rather than at 12:37 on a Windows box halfway through a pass.
    """
    import hourly_cycle

    sig = inspect.signature(hourly_cycle._producer)
    try:
        sig.bind(*[object() for _ in call.args],
                 **{kw.arg: object() for kw in call.keywords if kw.arg})
    except TypeError as exc:
        src = ast.unparse(call)
        pytest.fail(f"hourly_cycle.py:{call.lineno} cannot be called: {exc}\n  {src[:160]}")


def test_both_argument_shapes_reach_the_subprocess(tmp_path: Path) -> None:
    """Variadic AND tuple, because the file uses both and either must work.

    Two legs pass a tuple (`("--symbol", sym)`) and two pass the arguments directly. Accepting
    only one shape is what broke the cycle; a test that checks only the shape the author happened
    to use would not have noticed.
    """
    import hourly_cycle

    script = tmp_path / "echo_args.py"
    script.write_text("import sys; print('ARGS:' + ' '.join(sys.argv[1:]))\n")

    flat = hourly_cycle._producer("t", str(script), "--mode", "normal")
    grouped = hourly_cycle._producer("t", str(script), ("--mode", "normal"))
    none_ = hourly_cycle._producer("t", str(script))

    assert "ARGS:--mode normal" in flat["tail"], flat
    assert "ARGS:--mode normal" in grouped["tail"], grouped
    assert "ARGS:" in none_["tail"], none_
    assert flat["exit_code"] == grouped["exit_code"] == 0


def test_one_failing_leg_does_not_take_the_pass_with_it() -> None:
    """The deeper defect. A leg that raises used to escape `main` and stop the cycle dead.

    On 2026-09-07 that cost `publish_state`, `issue_board` and the four research report producers
    -- every leg after `pf_allocator` -- from a single bad call. A fifty-five-leg cycle whose
    reliability is the product of fifty-five things going right is not a cycle, it is a fuse.
    """
    import hourly_cycle

    out = hourly_cycle._costed(
        "boom", lambda: (_ for _ in ()).throw(ValueError("simulated leg failure")))
    assert out["status"] == "LEG_FAILED"
    assert "ValueError" in out["error"]
    # and a healthy leg is untouched
    assert hourly_cycle._costed("fine", lambda: {"ok": True}) == {"ok": True}


def test_an_interrupt_is_not_swallowed() -> None:
    """Someone stopping the pass is not the pass failing.

    Catching these too would make the cycle unkillable, which is a worse property than any leg
    failure it would paper over.
    """
    import hourly_cycle

    for exc in (KeyboardInterrupt, SystemExit):
        with pytest.raises(exc):
            hourly_cycle._costed("stop", lambda e=exc: (_ for _ in ()).throw(e()))


def test_a_missing_script_is_reported_not_run() -> None:
    """ABSENCE IS NEVER A PASS (L1.28a) -- the behaviour must survive the signature change."""
    import hourly_cycle

    out = hourly_cycle._producer("nope", "research/definitely_not_here.py", "--flag")
    assert out["status"] == "MISSING"
    assert out["exit_code"] is None
