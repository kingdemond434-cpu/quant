"""A capability the executor probes with `hasattr` must exist on the connector it actually runs.

R0217, found 2026-08-13. `scripts/run_cashcarry_executor.py:30` binds `binance_testnet as fut`, and
`_reconcile_protective_stops` opens with `if not fut.has_keys() or not hasattr(fut,
"place_stop_market"): return []`. `place_stop_market` was defined ONLY on `binance_live`, so on
every environment the desk has ever run, the venue-side protective stop -- the rail that survives
total host death -- returned [] on its first line and did not exist. Its own docstring disclosed
this as a "testnet parity gap"; a caveat disclosed but never converted into a rail is an open
defect, not documentation.

WHY THE TEST IS ABOUT THE PROBE AND NOT ABOUT ONE FUNCTION. A `hasattr` guard degrades silently by
construction: the capability's absence and its presence-and-no-op look identical from outside, and
nothing fails. Pinning `place_stop_market` alone would close this instance and leave the next
`hasattr`-guarded capability free to go missing the same way. So the test DISCOVERS the probes from
the executor's source and requires every one of them to be satisfied by the bound connector.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from libs.execution import binance_live, binance_testnet

_ROOT = Path(__file__).resolve().parents[2]
_EXECUTOR = _ROOT / "scripts/run_cashcarry_executor.py"


def _probed_capabilities() -> set[str]:
    """Names the executor asks `fut` for via hasattr/getattr -- read from source, never a list.

    Parsed rather than grepped so a renamed probe cannot drift past the fence, and so the set is
    whatever the money path actually asks for today.
    """
    tree = ast.parse(_EXECUTOR.read_text("utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id not in {"hasattr", "getattr"} or len(node.args) < 2:
            continue
        target, name = node.args[0], node.args[1]
        if (isinstance(target, ast.Name) and target.id == "fut"
                and isinstance(name, ast.Constant) and isinstance(name.value, str)):
            found.add(name.value)
    return found


def test_the_executor_actually_probes_something():
    """Guards the guard: an empty probe set would make every assertion below vacuous (L1.57)."""
    probes = _probed_capabilities()
    assert probes, (
        f"no hasattr/getattr probes on `fut` found in {_EXECUTOR} -- either the money path stopped "
        "using capability probes (delete this fence) or the parser drifted (fix it). Passing on "
        "an empty set would report parity nobody measured."
    )


def test_the_bound_connector_satisfies_every_capability_the_executor_probes():
    """`binance_testnet` is what `fut` binds to, so it is what must answer the probes."""
    bound = re.search(r"^from libs\.execution import (\w+) as fut$",
                      _EXECUTOR.read_text("utf-8"), re.M)
    assert bound, "could not determine which connector the executor binds as `fut`"
    assert bound.group(1) == "binance_testnet", (
        f"executor now binds {bound.group(1)} as `fut`; point this fence at that module"
    )

    missing = sorted(c for c in _probed_capabilities() if not hasattr(binance_testnet, c))
    assert not missing, (
        f"binance_testnet is missing {missing}, which the executor probes with hasattr/getattr. "
        "The probe degrades SILENTLY: the rail simply returns [] and nothing fails, which is how "
        "the host-death protective stop was absent for the whole life of the desk (R0217)."
    )


@pytest.mark.parametrize("name", sorted(_probed_capabilities()))
def test_probed_capabilities_are_callable_on_both_connectors(name: str):
    """Parity in BOTH directions: a rail validated on paper must be the same rail that goes live."""
    for mod in (binance_testnet, binance_live):
        fn = getattr(mod, name, None)
        assert callable(fn), f"{mod.__name__}.{name} is missing or not callable"


def test_the_stop_reconciler_can_cancel_as_well_as_place():
    """Placement without cancellation is worse than the no-op it replaced.

    `_reconcile_protective_stops` takes its canceller via `getattr(fut, "cancel_order", None)` and
    degrades to placement-only when absent -- so drifted stops would never be cancelled and a
    fresh one would be placed every pass. Unbounded resting stops on the money path.
    """
    assert callable(getattr(binance_testnet, "place_stop_market", None))
    assert callable(getattr(binance_testnet, "cancel_order", None)), (
        "place_stop_market without cancel_order accumulates a new resting stop every reconcile "
        "pass -- the pair is the unit"
    )
